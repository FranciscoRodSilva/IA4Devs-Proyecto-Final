"""Casos de uso de la obra (TKT-012a, fila A3): TC-09 a TC-13 y tres pruebas de apoyo.

Prueba `cimenta/presupuesto/aplicacion/obras.py` (`crear_obra`, `obtener_obra`, `listar_obras`,
`DatosObraNueva`, `ObrasConsultadas`, `ROLES_ALTA` y `ROLES_LECTURA_OBRA`) contra PostgreSQL real, con el
esquema de `alembic upgrade head` y el rol de aplicación. Nada de SQLite, nada de `sleep` para sincronizar.

Rojo de la fila A3: el módulo `cimenta.presupuesto.aplicacion.obras` no existe todavía. Cada prueba lo
importa dentro de su cuerpo, así que la recolección no se cae y cada caso falla solo con
`ModuleNotFoundError`, la razón esperada. Los fixtures solo usan lo que ya existe.

Empresa única (nota de ejecución del diseño): la migración `0008` siembra la única empresa activa y
`crear_obra` la toma. `DatosPresupuesto.obra()` sin `empresa_id` crearía otra empresa activa y el alta
respondería `RuntimeError` (A9), así que aquí las obras previas se dan de alta por `crear_obra`, y
`TC-13` crea la segunda empresa a propósito.

Qué cubre cada prueba:

- `TC-09` (`CA-1`): la obra y su asiento `CREAR` exactos, con las variantes de `CA-1`.
- `TC-10` (`CA-1`, regla 8): la bitácora se escribe en la misma transacción que la obra (`M-6`).
- `TC-11` (`CA-2`): el código duplicado, con el contrato de error completo (`M-3`, `M-7`).
- `TC-12` (`CA-3`): dos altas simultáneas con el mismo código; pasa una sola (`M-3`).
- `TC-13` (`CA-1`, `A9`): sin exactamente una empresa activa no se crea nada.
- Apoyo (no están en el plan de pruebas del diseño): el rango de los porcentajes en el caso de uso
  (`CA-5`, `M-4`: sin él la fila A3 no tendría ningún test que mate ese mutante), y `obtener_obra` y
  `listar_obras` (`CA-7`, `CA-8`), que el plan solo prueba por la API en la fila A4.

Mutantes de la fila: `M-3` (quitar la rama del `23505`) debe poner en rojo `TC-11` y `TC-12`; `M-4` (dejar
de llamar a `porcentajes_fuera_de_rango`), la prueba del rango; `M-6` (asentar con otra sesión tras
confirmar), `TC-10`; `M-7` (no pasar el código a mayúsculas), `TC-11`.
"""

from __future__ import annotations

import functools
import threading
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from cimenta.presupuesto.infraestructura import repositorio_obra
from contrato_error.excepciones import ConflictoEstado, NoEncontrado, ValidacionRechazada
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Base, Contexto, Hilo
from herramientas.tiempo_de_prueba import esperar_hasta
from tipos_base import Porcentaje

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt012a-a3"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
ROLES_ALTA_ESPERADOS = ("DIRECTOR_PROYECTOS", "DIRECCION_GENERAL")
ROLES_LECTURA_ESPERADOS = (
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
)
MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."
MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."
MENSAJE_OBRA_NO_EXISTE = "La obra no existe."

COLUMNAS_DE_OBRA = (
    "SELECT codigo, nombre, domicilio, tipo_contrato, retencion_destajo_pct, fondo_garantia_pct, "
    "iva_acreditable, umbral_alerta_pct, estado, empresa_id, creado_en, creado_por_id "
    "FROM obra WHERE id = %s"
)
COLUMNAS_DE_BITACORA = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, obra_id, "
    "datos_antes, datos_despues FROM bitacora WHERE accion = 'CREAR' AND entidad_id = %s"
)


# --------------------------------------------------------------------------- el entorno


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto del rol de aplicación con su reloj de prueba, construido al primer uso."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008): la que toma el alta."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return filas[0][0]


def _datos(**cambios: Any) -> Any:
    """Un `DatosObraNueva` válido; `cambios` sustituye campos. Se importa aquí para que el rojo sea de módulo."""
    from cimenta.presupuesto.aplicacion.obras import DatosObraNueva

    valores: dict[str, Any] = {
        "codigo": "AP-058-25",
        "nombre": "Union Square F2",
        "domicilio": "Calle de prueba 1",
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": Porcentaje("0.150000"),
        "fondo_garantia_pct": Porcentaje("0.050000"),
        "iva_acreditable": False,
        "umbral_alerta_pct": Porcentaje("0.100000"),
    }
    valores.update(cambios)
    return DatosObraNueva(**valores)


def _cuenta(base: Base, consulta: LiteralString, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _cuerpo_de_duplicado(*, codigo: str, nombre: str, existente_id: uuid.UUID) -> dict[str, object]:
    """El cuerpo completo del `409` de `CODIGO_OBRA_DUPLICADO` que ve el Director de Proyectos."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": f"Ya existe una obra con el código {codigo}.",
        "codigo": "CODIGO_OBRA_DUPLICADO",
        "detalle": {
            "obra_existente_id": str(existente_id),
            "obra_existente": f"{codigo} · {nombre}",
        },
        "acciones": [
            {"clave": "VER_OBRA", "metodo": "GET", "ruta": f"/api/v1/obras/{existente_id}"}
        ],
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-09 · CA-1


def test_hdu001_esc02_alta_guarda_la_obra_y_asienta_crear(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-09 · HDU-001 esc. 2 · CA-1 · RN-25 — una fila en `obra` y un asiento `CREAR` con el dato exacto.

    Tres porcentajes distintos (retención, fondo y umbral) para que un intercambio no pase; el reloj
    avanzado para que `ocurrido_en` y `creado_en` sean los del reloj inyectado y no la hora de la base.
    Variantes de `CA-1`: umbral ausente guarda `NULL`, `iva_acreditable` `true` se guarda como `true`, y
    un código con espacios y minúsculas se guarda recortado y en mayúsculas (D-1).
    """
    from cimenta.presupuesto.aplicacion.obras import crear_obra

    usuario = datos_presupuesto.usuario()
    reloj_de_prueba.avanzar(timedelta(hours=3))
    ahora = reloj_de_prueba()

    obra_id = crear_obra(contexto(), datos=_datos(), usuario_id=usuario)

    assert isinstance(obra_id, uuid.UUID)
    assert base.filas(COLUMNAS_DE_OBRA, obra_id) == [
        (
            "AP-058-25",
            "Union Square F2",
            "Calle de prueba 1",
            TIPO_CONTRATO,
            "0.150000",
            "0.050000",
            False,
            "0.100000",
            "PLANEACION",
            empresa_de_la_migracion,
            ahora,
            usuario,
        )
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, obra_id) == [
        (
            "CREAR",
            "obra",
            obra_id,
            usuario,
            ahora,
            obra_id,
            None,
            {
                "codigo": "AP-058-25",
                "nombre": "Union Square F2",
                "domicilio": "Calle de prueba 1",
                "tipo_contrato": TIPO_CONTRATO,
                "retencion_destajo_pct": "0.150000",
                "fondo_garantia_pct": "0.050000",
                "iva_acreditable": False,
                "umbral_alerta_pct": "0.100000",
                "estado": "PLANEACION",
            },
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Un alta, un solo asiento"
    assert _cuenta(base, "SELECT count(*) FROM linea_base WHERE obra_id = %s", obra_id) == 0

    # Variante: umbral ausente, IVA acreditable y un código por normalizar. Cuantiza a la escala de la columna.
    segunda = crear_obra(
        contexto(),
        datos=_datos(
            codigo="  ap-059-25 ",
            nombre="Obra con IVA acreditable",
            retencion_destajo_pct=Porcentaje("0.2"),
            fondo_garantia_pct=Porcentaje("0"),
            iva_acreditable=True,
            umbral_alerta_pct=None,
        ),
        usuario_id=usuario,
    )
    assert base.filas(COLUMNAS_DE_OBRA, segunda) == [
        (
            "AP-059-25",
            "Obra con IVA acreditable",
            "Calle de prueba 1",
            TIPO_CONTRATO,
            "0.200000",
            "0.000000",
            True,
            None,
            "PLANEACION",
            empresa_de_la_migracion,
            ahora,
            usuario,
        )
    ]
    asiento = base.filas("SELECT datos_despues FROM bitacora WHERE entidad_id = %s", segunda)
    assert asiento == [
        (
            {
                "codigo": "AP-059-25",
                "nombre": "Obra con IVA acreditable",
                "domicilio": "Calle de prueba 1",
                "tipo_contrato": TIPO_CONTRATO,
                "retencion_destajo_pct": "0.200000",
                "fondo_garantia_pct": "0.000000",
                "iva_acreditable": True,
                "umbral_alerta_pct": None,
                "estado": "PLANEACION",
            },
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 2


# --------------------------------------------------------------------------- TC-10 · CA-1, regla 8


def test_hdu001_esc02_alta_bitacora_en_la_misma_transaccion(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-10 · HDU-001 esc. 2 · CA-1 · regla 8 — si asentar falla, no queda la obra (`M-6`).

    `asentar` se sustituye por uno que, antes de lanzar, comprueba que corre en la sesión del alta y que
    ve la obra todavía sin confirmar: la bitácora se escribe en la misma transacción que el cambio. Al
    lanzar, la transacción se deshace y no queda fila en `obra` ni en `bitacora`. Con `asentar` en una
    sesión nueva tras confirmar (`M-6`) la obra quedaría guardada y la prueba cae.
    """
    from cimenta.presupuesto.aplicacion import obras

    class FallaDeBitacora(Exception):
        pass

    visto: dict[str, object] = {}

    def asentar_que_falla(*args: Any, **kwargs: Any) -> None:
        sesion_bd = args[0] if args else kwargs["sesion_bd"]
        visto["en_transaccion"] = sesion_bd.in_transaction()
        visto["obras_vistas"] = sesion_bd.execute(
            text("SELECT count(*) FROM obra WHERE codigo = 'AP-058-25'")
        ).scalar_one()
        raise FallaDeBitacora

    monkeypatch.setattr(obras, "asentar", asentar_que_falla)
    usuario = datos_presupuesto.usuario()
    antes = base.foto()

    with pytest.raises(FallaDeBitacora):
        obras.crear_obra(contexto(), datos=_datos(), usuario_id=usuario)

    assert visto == {"en_transaccion": True, "obras_vistas": 1}, (
        "asentar debe correr en la misma sesión, con la obra insertada y sin confirmar"
    )
    assert _cuenta(base, "SELECT count(*) FROM obra") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    assert base.foto() == antes, "Una alta que falla no deja ninguna fila"


# --------------------------------------------------------------------------- TC-11 · CA-2


def test_hdu001_esc03_alta_codigo_duplicado(
    contexto: Contexto, base: Base, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-11 · HDU-001 esc. 3 · CA-2 — `409` `CODIGO_OBRA_DUPLICADO` con la obra existente y `VER_OBRA` (`M-3`, `M-7`).

    El contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, el detalle
    con el id y el «código · nombre» de la obra existente y la acción `VER_OBRA` con método, ruta y los
    seis roles de lectura. La unicidad es del motor: sin la rama del `23505` (`M-3`) el rechazo saldría
    `ESTADO_NO_PERMITE_OPERACION`. Con D-1, `ap-058-25` y `  ap-058-25 ` también chocan (`M-7`). Un
    rechazo no escribe: ni una fila en `obra` ni un segundo `CREAR`.
    """
    from cimenta.presupuesto.aplicacion.obras import (
        ROLES_ALTA,
        ROLES_LECTURA_OBRA,
        crear_obra,
    )

    assert ROLES_ALTA == ROLES_ALTA_ESPERADOS
    assert ROLES_LECTURA_OBRA == ROLES_LECTURA_ESPERADOS

    usuario = datos_presupuesto.usuario()
    existente_id = crear_obra(contexto(), datos=_datos(), usuario_id=usuario)
    antes = base.foto()
    esperado = _cuerpo_de_duplicado(
        codigo="AP-058-25", nombre="Union Square F2", existente_id=existente_id
    )

    for intento in ("AP-058-25", "ap-058-25", "  ap-058-25 "):
        with pytest.raises(ConflictoEstado) as rechazo:
            crear_obra(
                contexto(),
                datos=_datos(codigo=intento, nombre="Otra obra con el mismo código"),
                usuario_id=usuario,
            )
        error = rechazo.value
        assert error.estado_http == 409, intento
        assert error.cuerpo(ROLES_DP, CORRELACION) == esperado, intento
        (accion,) = error.acciones
        assert accion.roles_permitidos == frozenset(ROLES_LECTURA_ESPERADOS), intento
        # Quien solo lee la obra (el residente) también recibe la acción: `VER_OBRA` es de lectura.
        assert error.cuerpo(frozenset({"RESIDENTE"}), CORRELACION) == esperado, intento
        assert base.foto() == antes, f"El rechazo no escribe ({intento!r})"

    assert _cuenta(base, "SELECT count(*) FROM obra WHERE codigo = 'AP-058-25'") == 1
    assert _cuenta(base, "SELECT count(*) FROM obra") == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 1
    assert base.filas("SELECT nombre FROM obra") == [("Union Square F2",)]


# --------------------------------------------------------------------------- TC-12 · CA-3


def test_hdu001_esc03_dos_altas_concurrentes_mismo_codigo(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-12 · HDU-001 esc. 3 · CA-3 · `uq_obra_codigo` — dos altas con el mismo código: pasa una sola (`M-3`).

    Determinista y sin `sleep`. El hilo A se pausa dentro de `repositorio_obra.insertar_obra`, con la
    fila ya insertada y sin confirmar; el hilo B arranca y su `INSERT` queda detenido en el índice único
    (la prueba lo espera con `esperar_hasta` sobre `pg_blocking_pids`); entonces se libera a A, que
    confirma. B recibe la violación `23505` y responde `CODIGO_OBRA_DUPLICADO` con la obra de A, no
    `500` ni `ESTADO_NO_PERMITE_OPERACION`. El hilo pausado se libera siempre en `finally`.

    Requiere que el caso de uso llame a `repositorio_obra.insertar_obra` por el módulo, no por un
    nombre importado: es lo que permite la envoltura (mismo patrón que `repositorio_linea_base` en
    TKT-017).
    """
    from cimenta.presupuesto.aplicacion import obras

    codigo = "AP-070-26"
    usuario = datos_presupuesto.usuario()
    ctx = contexto()
    original = repositorio_obra.insertar_obra
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A":
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_obra, "insertar_obra", envoltura)
    if hasattr(obras, "insertar_obra"):  # por si el caso de uso importó el nombre y no el módulo
        monkeypatch.setattr(obras, "insertar_obra", envoltura)

    a = Hilo(
        "A",
        lambda: obras.crear_obra(
            ctx, datos=_datos(codigo=codigo, nombre="Obra del hilo A"), usuario_id=usuario
        ),
    )
    b = Hilo(
        "B",
        lambda: obras.crear_obra(
            ctx, datos=_datos(codigo=codigo, nombre="Obra del hilo B"), usuario_id=usuario
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), "El hilo A no llegó a insertar la obra"
        b.start()
        espera = esperar_hasta(
            lambda: bool(
                base.filas(
                    "SELECT 1 FROM pg_stat_activity WHERE datname = current_database() "
                    "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
                    "%INSERT INTO obra (%",
                )
            ),
            5.0,
        )
        assert espera, (
            f"B no quedó detenido en el índice único mientras A tenía la fila sin confirmar: {b.error!r}"
        )
        assert b.is_alive()
        assert _cuenta(base, "SELECT count(*) FROM obra") == 0, (
            "La fila de A no se ve mientras no confirma"
        )
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    obra_de_a = a.exito()
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_de_duplicado(
        codigo=codigo, nombre="Obra del hilo A", existente_id=obra_de_a
    )
    assert base.filas("SELECT id, codigo, nombre FROM obra") == [
        (obra_de_a, codigo, "Obra del hilo A")
    ]
    assert base.filas("SELECT entidad_id FROM bitacora WHERE accion = 'CREAR'") == [(obra_de_a,)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1


# --------------------------------------------------------------------------- TC-13 · CA-1 (A9)


@pytest.mark.usefixtures("empresa_de_la_migracion")
def test_tkt012a_alta_sin_una_unica_empresa_activa(
    contexto: Contexto, base: Base, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-13 · CA-1 (A9) — con dos empresas activas o con ninguna, `RuntimeError` y ninguna fila.

    No es contrato de error: es un fallo de despliegue que responde `500` con su traza. Se comprueba
    el mensaje con la cuenta real (2 y 0) y que ni `obra` ni `bitacora` recibieron nada.
    """
    from cimenta.presupuesto.aplicacion.obras import crear_obra

    usuario = datos_presupuesto.usuario()

    datos_presupuesto.empresa(activa=True)
    antes = base.foto()
    with pytest.raises(RuntimeError) as dos:
        crear_obra(contexto(), datos=_datos(), usuario_id=usuario)
    assert str(dos.value) == (
        "Se esperaba exactamente una empresa activa y hay 2; revise el despliegue (A9)."
    )
    assert base.foto() == antes, "Con dos empresas activas no se escribe nada"
    assert _cuenta(base, "SELECT count(*) FROM obra") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0

    base.ejecutar("UPDATE empresa SET activa = false")
    antes = base.foto()
    with pytest.raises(RuntimeError) as ninguna:
        crear_obra(contexto(), datos=_datos(), usuario_id=usuario)
    assert str(ninguna.value) == (
        "Se esperaba exactamente una empresa activa y hay 0; revise el despliegue (A9)."
    )
    assert base.foto() == antes, "Sin empresa activa no se escribe nada"
    assert _cuenta(base, "SELECT count(*) FROM obra") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- apoyo · CA-5 (M-4)


def test_hdu001_esc02_alta_porcentaje_fuera_de_rango(
    contexto: Contexto, base: Base, datos_presupuesto: DatosPresupuesto
) -> None:
    """Apoyo de `M-4` · HDU-001 esc. 2 · CA-5 · PA-02 — el rango se rechaza en el caso de uso, no en el motor.

    Las cinco filas de `CA-5`, cada una con su `ErrorDeCampo` `FUERA_DE_RANGO` y el mensaje del diseño;
    y los tres fuera de rango a la vez, en el orden fijo retención, fondo, umbral. La validación corre
    **antes de abrir la transacción**: la prueba deja dos empresas activas, que haría fallar la
    transacción con `RuntimeError` (A9), y aun así el rechazo es `ValidacionRechazada`. Sin la llamada a
    `porcentajes_fuera_de_rango` (`M-4`) el `CHECK` del motor daría `23514` y la prueba cae.
    """
    from cimenta.presupuesto.aplicacion.obras import crear_obra

    usuario = datos_presupuesto.usuario()
    datos_presupuesto.empresa(
        activa=True
    )  # con dos activas, llegar a la transacción es RuntimeError
    antes = base.foto()

    filas = [
        ("retencion_destajo_pct", "-0.010000", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("retencion_destajo_pct", "1.000001", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("fondo_garantia_pct", "-0.010000", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("fondo_garantia_pct", "1.000001", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("umbral_alerta_pct", "-0.000001", MENSAJE_UMBRAL_NEGATIVO),
    ]
    for campo, valor, mensaje in filas:
        with pytest.raises(ValidacionRechazada) as rechazo:
            crear_obra(contexto(), datos=_datos(**{campo: Porcentaje(valor)}), usuario_id=usuario)
        error = rechazo.value
        assert error.estado_http == 422, (campo, valor)
        assert error.cuerpo(ROLES_DP, CORRELACION) == {
            "tipo": "VALIDACION",
            "mensaje": "La petición tiene 1 campo inválido.",
            "errores": [{"campo": campo, "codigo": "FUERA_DE_RANGO", "mensaje": mensaje}],
            "correlacion_id": CORRELACION,
        }, (campo, valor)
        assert base.foto() == antes, f"El rechazo no escribe ({campo}={valor})"

    with pytest.raises(ValidacionRechazada) as varios:
        crear_obra(
            contexto(),
            datos=_datos(
                retencion_destajo_pct=Porcentaje("1.5"),
                fondo_garantia_pct=Porcentaje("-0.5"),
                umbral_alerta_pct=Porcentaje("-1"),
            ),
            usuario_id=usuario,
        )
    assert varios.value.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 3 campos inválidos.",
        "errores": [
            {
                "campo": "retencion_destajo_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            },
            {
                "campo": "fondo_garantia_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            },
            {
                "campo": "umbral_alerta_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_UMBRAL_NEGATIVO,
            },
        ],
        "correlacion_id": CORRELACION,
    }
    assert base.foto() == antes
    assert _cuenta(base, "SELECT count(*) FROM obra") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- apoyo · CA-7, CA-8


def test_tkt012a_alta_obtener_y_listar_obras(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """Apoyo · CA-7 · CA-8 — `obtener_obra` y `listar_obras` leen lo que `crear_obra` guardó.

    Tres obras dadas de alta fuera de orden de código: la lista las devuelve por código, con la ventana
    y el total correctos, con el filtro por estado, y una página inalcanzable —aun una enorme— da una
    página vacía con el total real (`D20`). `obtener_obra` devuelve la obra completa, con
    `linea_base_vigente_id` nulo y los tres porcentajes distintos.
    """
    from cimenta.presupuesto.aplicacion.obras import (
        ObrasConsultadas,
        crear_obra,
        listar_obras,
        obtener_obra,
    )

    usuario = datos_presupuesto.usuario()
    ahora = reloj_de_prueba()
    c = crear_obra(contexto(), datos=_datos(codigo="AP-003", nombre="Tercera"), usuario_id=usuario)
    a = crear_obra(contexto(), datos=_datos(codigo="AP-001", nombre="Primera"), usuario_id=usuario)
    b = crear_obra(contexto(), datos=_datos(codigo="AP-002", nombre="Segunda"), usuario_id=usuario)
    base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", c)

    obra = obtener_obra(contexto(), a)
    assert obra.id == a
    assert (obra.codigo, obra.nombre, obra.domicilio) == ("AP-001", "Primera", "Calle de prueba 1")
    assert obra.tipo_contrato == TIPO_CONTRATO
    assert obra.retencion_destajo_pct.serializar() == "0.150000"
    assert obra.fondo_garantia_pct.serializar() == "0.050000"
    assert obra.umbral_alerta_pct is not None
    assert obra.umbral_alerta_pct.serializar() == "0.100000"
    assert obra.iva_acreditable is False
    assert obra.estado == "PLANEACION"
    assert obra.linea_base_vigente_id is None
    assert obra.creado_en == ahora
    assert obra.actualizado_en is None

    todas = listar_obras(contexto(), estados=None, pagina=1, tamano_pagina=50)
    assert isinstance(todas, ObrasConsultadas)
    assert [o.id for o in todas.elementos] == [a, b, c]
    assert (todas.pagina, todas.tamano_pagina, todas.total) == (1, 50, 3)

    primera = listar_obras(contexto(), estados=None, pagina=1, tamano_pagina=2)
    assert [o.codigo for o in primera.elementos] == ["AP-001", "AP-002"]
    assert (primera.pagina, primera.tamano_pagina, primera.total) == (1, 2, 3)
    segunda = listar_obras(contexto(), estados=None, pagina=2, tamano_pagina=2)
    assert [o.codigo for o in segunda.elementos] == ["AP-003"]
    assert (segunda.pagina, segunda.tamano_pagina, segunda.total) == (2, 2, 3)

    activas = listar_obras(contexto(), estados=frozenset({"ACTIVA"}), pagina=1, tamano_pagina=50)
    assert [o.codigo for o in activas.elementos] == ["AP-003"]
    assert activas.total == 1
    dos = listar_obras(
        contexto(), estados=frozenset({"ACTIVA", "PLANEACION"}), pagina=1, tamano_pagina=50
    )
    assert [o.codigo for o in dos.elementos] == ["AP-001", "AP-002", "AP-003"]

    for pagina in (1000, 10**30):
        vacia = listar_obras(contexto(), estados=None, pagina=pagina, tamano_pagina=50)
        assert vacia.elementos == (), pagina
        assert vacia.total == 3, pagina
        assert vacia.pagina == pagina, pagina


def test_tkt012a_obtener_obra_inexistente(contexto: Contexto, base: Base) -> None:
    """Apoyo · CA-8 — la obra que no existe responde `NO_ENCONTRADO` con `recurso` `obra` y no escribe."""
    from cimenta.presupuesto.aplicacion.obras import obtener_obra

    antes = base.foto()
    with pytest.raises(NoEncontrado) as rechazo:
        obtener_obra(contexto(), uuid.uuid4())

    error = rechazo.value
    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_OBRA_NO_EXISTE,
        "recurso": "obra",
        "correlacion_id": CORRELACION,
    }
    assert base.foto() == antes
