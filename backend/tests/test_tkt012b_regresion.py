"""Regresión del mantenimiento y del ciclo de vida de la obra, fila A9 de TKT-012b (TC-61, TC-62, TC-INV-2 a TC-INV-5).

Lo que las cinco operaciones nuevas **no** deben romper (`CA-R1` a `CA-R4`), probado contra PostgreSQL real
con el esquema de `alembic upgrade head`:

- `TC-61` y `TC-62` (`CA-R4`, invariante 14): borrar una obra sin historial no toca la línea base congelada
  de otra obra ni deja huérfanos, y el disparador de inmutabilidad sigue rechazando `UPDATE` y `DELETE`
  sobre las copias congeladas aunque la obra pase por suspensión, reactivación y cierre.
- `TC-INV-2` y `TC-INV-3` (`CA-R1`, `PA-T17.8`): el congelado de TKT-017 sigue pasando `PLANEACION` a
  `ACTIVA`, y sigue rechazando una obra `SUSPENDIDA` o `CERRADA` como antes, con la máquina de estados
  nueva en el código.
- `TC-INV-4` (`CA-R2`): la suite de TKT-012a no se toca (la comprueba `git status` y la corrida de sus
  archivos, pegada en `rojo/fila-A9.txt`); aquí solo se ancla lo que 012b podría romper de ella: `GET`
  sigue abierto a los seis roles, también sobre una obra que ya pasó por el ciclo de vida.
- `TC-INV-5`: un alta con un código recién liberado por un borrado funciona.

Mutantes que esta fila pone en rojo: un `DELETE` de la obra sin `WHERE`, o con el `WHERE` de otra
columna (`TC-61`); una transición que escribe sobre la línea base (`TC-62`); una máquina de estados que
admite `PLANEACION → ACTIVA` por una de las tres operaciones o que relaja el congelado (`TC-INV-2`,
`TC-INV-3`); un `eliminar_obra` que no asienta el borrado o que deja ocupado el código (`TC-INV-5`).
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como
# F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`; aquí se exime en el archivo.
# ruff: noqa: F811

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from cimenta.presupuesto.aplicacion.ciclo_vida_obra import (
    cerrar_obra,
    reactivar_obra,
    suspender_obra,
)
from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from cimenta.presupuesto.aplicacion.mantenimiento_obras import eliminar_obra
from contrato_error.excepciones import ConflictoEstado
from herramientas.soporte_tkt017_api import (
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    cabeceras_de,
    exigir_error,
)
from herramientas.soporte_tkt017_entorno import (
    NOMBRE_COMPLETO_OBRA,
    Base,
    Contexto,
    Entorno,
    congelar,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt012b-a9-regresion"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
CODIGO = "AP-058-25"
MOTIVO = "Decisión de la dirección por falta de anticipo"
MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
RUTA = "/api/v1/obras"
TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
SEIS_ROLES = [
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "COMPRAS",
    "RESIDENTE",
    "ALMACEN",
    "ADMINISTRACION",
]

# Las tablas que cuelgan de una obra con clave foránea y las de la línea base y sus copias.
TABLAS_CON_OBRA = [
    "linea_base",
    "importacion",
    "nivel",
    "concepto",
    "requisicion",
    "orden_compra",
    "solicitud_autorizacion",
    "precio_insumo",
    "rendimiento_observado",
]
TABLAS_DE_LA_LINEA_BASE = [
    "linea_base",
    "linea_base_concepto",
    "explosion_presupuesto",
    "presupuesto_control",
]


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto real del rol de aplicación, construido al primer uso."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`)."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def usuario(datos_presupuesto: DatosPresupuesto) -> uuid.UUID:
    return datos_presupuesto.usuario()


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID, usuario: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra en el estado pedido, con la empresa de la migración."""
    contador = iter(range(1, 1000))

    def fabricar(*, codigo: str | None = None, estado: str = "ACTIVA") -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo if codigo is not None else f"AP-{next(contador):03d}-26",
            empresa_id=empresa_de_la_migracion,
            creado_por_id=usuario,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=Decimal("0.100000"),
            iva_acreditable=True,
        )

    return fabricar


@pytest.fixture
def entorno(datos_presupuesto: DatosPresupuesto, base: Base) -> Entorno:
    """La obra `AP-058-25` en planeación, los cuatro tipos sembrados, el director y la mano de obra."""
    entorno = Entorno(datos_presupuesto, base)
    entorno.registrar_mano_obra()
    return entorno


# --------------------------------------------------------------------------- ayudas


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _foto_ajena(base: Base, obra_ajena: uuid.UUID) -> dict[str, object]:
    """Todas las columnas de todo lo que NO es de `obra_ajena`: obras, líneas base, copias, control, jerarquía."""
    return {
        "obras": base.filas("SELECT * FROM obra WHERE id <> %s ORDER BY id", obra_ajena),
        "linea_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "copias": base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        "explosion": base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
        "control": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
        "nivel": base.filas("SELECT * FROM nivel ORDER BY id"),
        "concepto": base.filas("SELECT * FROM concepto ORDER BY id"),
        "importacion": base.filas("SELECT * FROM importacion ORDER BY id"),
    }


def _huerfanos(base: Base) -> dict[str, int]:
    """Filas cuya obra (o línea base) ya no existe, por tabla: todo debe ser cero."""
    cuentas = {
        tabla: _cuenta(
            base,
            f"SELECT count(*) FROM {tabla} t "  # type: ignore[arg-type]
            "WHERE NOT EXISTS (SELECT 1 FROM obra o WHERE o.id = t.obra_id)",
        )
        for tabla in TABLAS_CON_OBRA
    }
    for tabla in TABLAS_DE_LA_LINEA_BASE[1:]:
        cuentas[tabla] = _cuenta(
            base,
            f"SELECT count(*) FROM {tabla} t "  # type: ignore[arg-type]
            "WHERE NOT EXISTS (SELECT 1 FROM linea_base l WHERE l.id = t.linea_base_id)",
        )
    return cuentas


# --------------------------------------------------------------------------- TC-61 · CA-R4


def test_tkt012b_ca_r4_borrar_una_obra_sin_historial_no_toca_la_linea_base_congelada_de_otra(
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
) -> None:
    """TC-61 · CA-R4 · RN-01 · invariante 14 — el borrado de la obra B no cambia ni una columna de la línea base de A.

    La obra A está `ACTIVA` con una línea base `CONGELADA`, su copia de concepto, su renglón de explosión,
    su control presupuestal, su jerarquía y una importación. La obra B no tiene historial. Tras borrar B,
    todas las filas de A (y las del resto de la base) son idénticas columna por columna; B ya no existe,
    su código queda libre y no queda ninguna fila hija huérfana en ninguna tabla.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    datos_presupuesto.control(
        linea_base_id=copias.linea_base_id, tipo_partida_id=copias.tipo_partida_id
    )
    datos_presupuesto.importacion(obra_id=copias.obra_id)
    base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", copias.obra_id)
    obra_b = fabricar_obra(codigo="AP-099-26", estado="PLANEACION")
    antes = _foto_ajena(base, obra_b)
    assert len(antes["linea_base"]) == 1  # type: ignore[arg-type]
    assert len(antes["control"]) == 1  # type: ignore[arg-type]

    eliminar_obra(contexto(), obra_b, usuario)

    assert base.filas("SELECT id FROM obra WHERE id = %s", obra_b) == []
    assert _foto_ajena(base, obra_b) == antes, "El borrado de B no altera nada que no sea de B"
    assert _huerfanos(base) == dict.fromkeys(_huerfanos(base), 0), _huerfanos(base)
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", copias.linea_base_id) == [
        ("CONGELADA",)
    ]
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE codigo = 'AP-099-26'") == 0
    assert base.filas(
        "SELECT accion::text, entidad_id, obra_id FROM bitacora WHERE accion = 'ELIMINAR'"
    ) == [("ELIMINAR", obra_b, obra_b)], "Un solo asiento, el de B"


# --------------------------------------------------------------------------- TC-62 · CA-R4 · invariante 14


# (nombre, tabla afectada, sentencia con `%s` para el identificador de la fila y, si lo hay, el importe).
SENTENCIAS_SOBRE_COPIAS = [
    pytest.param(
        "linea_base_concepto",
        "UPDATE linea_base_concepto SET cantidad = %s WHERE id = %s",
        "copia_id",
        Decimal("999.0000"),
        id="update_sobre_la_copia",
    ),
    pytest.param(
        "linea_base_concepto",
        "DELETE FROM linea_base_concepto WHERE id = %s",
        "copia_id",
        None,
        id="delete_sobre_la_copia",
    ),
    pytest.param(
        "explosion_presupuesto",
        "UPDATE explosion_presupuesto SET cantidad_presupuestada = %s WHERE id = %s",
        "renglon_id",
        Decimal("999.0000"),
        id="update_sobre_el_renglon",
    ),
    pytest.param(
        "explosion_presupuesto",
        "DELETE FROM explosion_presupuesto WHERE id = %s",
        "renglon_id",
        None,
        id="delete_sobre_el_renglon",
    ),
]


@pytest.mark.parametrize(
    ("tabla", "sentencia", "campo_de_la_fila", "importe"), SENTENCIAS_SOBRE_COPIAS
)
def test_tkt012b_ca_r4_el_disparador_de_inmutabilidad_sigue_rechazando_tras_el_ciclo_de_vida(
    tabla: str,
    sentencia: str,
    campo_de_la_fila: str,
    importe: Decimal | None,
    datos_presupuesto: DatosPresupuesto,
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-62 · CA-R4 · RN-01 · invariante 14 — `UPDATE` y `DELETE` sobre copias congeladas siguen respondiendo `IN001`.

    La obra con la línea base `CONGELADA` y sus copias recorre `ACTIVA → SUSPENDIDA → ACTIVA → CERRADA` por
    los casos de uso nuevos; ninguno relaja el disparador. Después, el rol de migración (con el de
    aplicación rechazaría antes el privilegio) intenta cada sentencia sobre las copias y el motor las
    rechaza con el `SQLSTATE` propio `IN001`, el prefijo `RN-01:` y el nombre del disparador, sin cambiar
    una sola fila.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", copias.obra_id)
    for transicion in (suspender_obra, reactivar_obra, cerrar_obra):
        reloj_de_prueba.avanzar(timedelta(minutes=10))
        transicion(contexto(), copias.obra_id, MOTIVO, usuario)
    fila = getattr(copias, "copia_id" if campo_de_la_fila == "copia_id" else "renglon_id")
    argumentos = (fila,) if importe is None else (importe, fila)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = _copias_y_linea_base(migracion)
        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute(sentencia, argumentos)  # type: ignore[arg-type]
        despues = _copias_y_linea_base(migracion)

    assert rechazo.value.sqlstate == "IN001", str(rechazo.value)
    mensaje = rechazo.value.diag.message_primary
    assert mensaje is not None and mensaje.startswith("RN-01:"), mensaje
    assert rechazo.value.diag.constraint_name == f"trg_{tabla}_inmutable"
    assert rechazo.value.diag.table_name == tabla
    assert despues == antes, "El disparador rechaza sin cambiar ninguna fila"
    assert base.filas("SELECT estado FROM obra WHERE id = %s", copias.obra_id) == [("CERRADA",)]
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", copias.linea_base_id) == [
        ("CONGELADA",)
    ], "Cerrar la obra no supersede ni toca la línea base"


def _copias_y_linea_base(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, list[Any]]:
    """Todas las columnas de las copias, el explosionado y la línea base, para compararlas antes y después."""
    return {
        "linea_base_concepto": conexion.execute(
            "SELECT * FROM linea_base_concepto ORDER BY id"
        ).fetchall(),
        "explosion_presupuesto": conexion.execute(
            "SELECT * FROM explosion_presupuesto ORDER BY id"
        ).fetchall(),
        "linea_base": conexion.execute("SELECT * FROM linea_base ORDER BY id").fetchall(),
    }


def test_tkt012b_ca_r4_la_obra_con_linea_base_congelada_no_se_puede_borrar_ni_por_sql(
    datos_presupuesto: DatosPresupuesto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-62 · CA-R4 · RN-01 — un `DELETE FROM obra` saltándose el API choca con la clave foránea `RESTRICT`.

    La última barrera del invariante 14: aunque alguien llegue al motor sin pasar por `eliminar_obra`, la
    obra con una línea base `CONGELADA`, su jerarquía y sus copias no desaparece (`23001`, la restricción
    de la primera hija que el motor revisa) y las copias no se mueven.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    antes = base.filas("SELECT * FROM linea_base_concepto ORDER BY id")

    with (
        conectar("aplicacion", base_de_prueba) as aplicacion,
        pytest.raises(psycopg.errors.RestrictViolation) as rechazo,
    ):
        aplicacion.execute("DELETE FROM obra WHERE id = %s", (copias.obra_id,))

    assert rechazo.value.sqlstate == "23001"
    restriccion = rechazo.value.diag.constraint_name
    assert restriccion in {"fk_linea_base_obra_id", "fk_nivel_obra_id", "fk_concepto_obra_id"}, (
        restriccion
    )
    assert base.filas("SELECT id FROM obra WHERE id = %s", copias.obra_id) == [(copias.obra_id,)]
    assert base.filas("SELECT * FROM linea_base_concepto ORDER BY id") == antes


# --------------------------------------------------------------------------- TC-INV-2 · CA-R1 · PA-T17.8


def test_tkt012b_ca_r1_el_congelado_de_una_obra_en_planeacion_sigue_pasandola_a_activa(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-INV-2 · CA-R1 · PA-T17.8 — con la máquina de estados nueva en el código, congelar activa la obra.

    La arista `PLANEACION → ACTIVA` no es ninguna de las tres operaciones (`evaluar_transicion` no la
    conoce): solo la produce el congelado. Aquí se prueba que el congelado de TKT-017 la sigue haciendo,
    con su asiento `CONGELAR`, y que la obra recién activada ya admite las operaciones nuevas.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("PLANEACION",)]

    congelada = congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    assert congelada == borrador.linea_base_id
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("ACTIVA",)]
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", congelada) == [("CONGELADA",)]
    assert base.filas(
        "SELECT entidad_id FROM bitacora WHERE obra_id = %s AND accion = 'CONGELAR'",
        entorno.obra_id,
    ) == [(congelada,)]
    suspender_obra(contexto(), entorno.obra_id, MOTIVO, entorno.usuario_id)
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("SUSPENDIDA",)]


# --------------------------------------------------------------------------- TC-INV-3 · CA-R1


@pytest.mark.parametrize("estado_obra", ["SUSPENDIDA", "CERRADA"])
def test_tkt012b_ca_r1_el_congelado_de_una_obra_suspendida_o_cerrada_se_rechaza_como_hoy(
    estado_obra: str, entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-INV-3 · CA-R1 — congelar una obra `SUSPENDIDA` o `CERRADA` responde `ESTADO_NO_PERMITE_OPERACION`, sin escribir.

    La `CERRADA` se alcanza por la operación nueva (`cerrar_obra` desde `PLANEACION`, D-2); la `SUSPENDIDA`,
    por SQL, porque ninguna operación la produce desde `PLANEACION`. El congelado la rechaza con el mismo
    mensaje y el mismo detalle que fija `test_tkt017_cab03_obra_en_otro_estado`: la línea base sigue
    `BORRADOR`, la obra no cambia y no hay asiento `CONGELAR`.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    if estado_obra == "CERRADA":
        cerrar_obra(contexto(), entorno.obra_id, MOTIVO, entorno.usuario_id)
    else:
        entorno.poner_obra_en("SUSPENDIDA")
    antes = (base.foto(), base.filas("SELECT * FROM obra ORDER BY id"))

    with pytest.raises(ConflictoEstado) as rechazo:
        congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    assert rechazo.value.estado_http == 409
    assert rechazo.value.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_FUERA_DE_PLANEACION.format(codigo=CODIGO, estado=estado_obra),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"obra": NOMBRE_COMPLETO_OBRA, "estado_obra": estado_obra},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert (base.foto(), base.filas("SELECT * FROM obra ORDER BY id")) == antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        ("BORRADOR",)
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CONGELAR'") == 0


# --------------------------------------------------------------------------- TC-INV-4 · CA-R2


@pytest.mark.parametrize("rol", SEIS_ROLES)
def test_tkt012b_ca_r2_la_consulta_de_obras_sigue_abierta_a_los_seis_roles(
    rol: str,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-INV-4 · CA-R2 — `GET` de la lista y de la obra responde `200` a cada uno de los seis roles, tras el ciclo de vida.

    Las cinco operaciones nuevas exigen Director de Proyectos o Dirección General; la consulta no cambia.
    Una obra que ya pasó por suspensión y cierre se lee igual, con su estado nuevo. La suite completa de
    TKT-012a (alta, lista, consulta, `CODIGO_OBRA_DUPLICADO`) se ejecuta sin tocarla: no se copia aquí.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    suspender_obra(contexto(), obra_id, MOTIVO, usuario)
    cerrar_obra(contexto(), obra_id, MOTIVO, usuario)
    sesion = abrir_sesion((rol,))

    lista = cliente.get(RUTA, headers=cabeceras_de(sesion.sesion_id))
    una = cliente.get(f"{RUTA}/{obra_id}", headers=cabeceras_de(sesion.sesion_id))

    assert lista.status_code == 200, lista.text
    assert [o["id"] for o in lista.json()["elementos"]] == [str(obra_id)]
    assert una.status_code == 200, una.text
    assert una.json()["estado"] == "CERRADA"


# --------------------------------------------------------------------------- TC-INV-5


def test_tkt012b_ca5_un_alta_con_un_codigo_liberado_por_un_borrado_funciona(
    cliente: TestClient, abrir_sesion: Callable[..., Sesion], base: Base
) -> None:
    """TC-INV-5 · CA-5 · HDU-001 esc. 20 — dar de alta, borrar y dar de alta otra vez con el mismo código.

    Por la API real: el borrado es físico y libera `uq_obra_codigo`, así que el segundo alta con
    `AP-099-26` responde `201` con otra obra distinta. La bitácora cuenta la historia completa: dos
    `CREAR` y el `ELIMINAR` de la primera, con su código y su nombre.
    """
    director = abrir_sesion()
    cabeceras = cabeceras_de(director.sesion_id, TOKEN_CSRF, TOKEN_CSRF)
    cuerpo = {
        "codigo": "AP-099-26",
        "nombre": "Obra que se da de alta dos veces",
        "domicilio": "Calle de prueba 1",
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": True,
        "umbral_alerta_pct": "0.100000",
    }
    primera = cliente.post(RUTA, json=cuerpo, headers=cabeceras)
    assert primera.status_code == 201, primera.text
    primera_id = uuid.UUID(primera.json()["id"])
    # El código está ocupado mientras la obra exista: el control de que el alta sí lo detecta.
    ocupado = cliente.post(RUTA, json=cuerpo, headers=cabeceras)
    exigir_error(
        ocupado,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "CODIGO_OBRA_DUPLICADO",
            "mensaje": "Ya existe una obra con el código AP-099-26.",
            "detalle": {
                "obra_existente_id": str(primera_id),
                "obra_existente": "AP-099-26 · Obra que se da de alta dos veces",
            },
            "acciones": [{"clave": "VER_OBRA", "metodo": "GET", "ruta": f"{RUTA}/{primera_id}"}],
        },
        esquema="ErrorConflictoEstado",
    )

    borrada = cliente.delete(f"{RUTA}/{primera_id}", headers=cabeceras)
    assert borrada.status_code == 204, borrada.text
    segunda = cliente.post(RUTA, json=cuerpo, headers=cabeceras)

    assert segunda.status_code == 201, segunda.text
    segunda_id = uuid.UUID(segunda.json()["id"])
    assert segunda_id != primera_id
    assert base.filas("SELECT id, codigo FROM obra") == [(segunda_id, "AP-099-26")]
    asientos = base.filas(
        "SELECT accion::text, entidad_id FROM bitacora "
        "WHERE accion IN ('CREAR', 'ELIMINAR') AND entidad_tipo = 'obra'"
    )
    assert sorted(asientos, key=lambda fila: (fila[0], str(fila[1]))) == sorted(
        [("CREAR", primera_id), ("CREAR", segunda_id), ("ELIMINAR", primera_id)],
        key=lambda fila: (fila[0], str(fila[1])),
    )
    eliminar = base.filas(
        "SELECT datos_antes ->> 'codigo', datos_antes ->> 'nombre' FROM bitacora "
        "WHERE accion = 'ELIMINAR' AND entidad_id = %s",
        primera_id,
    )
    assert eliminar == [("AP-099-26", "Obra que se da de alta dos veces")]
