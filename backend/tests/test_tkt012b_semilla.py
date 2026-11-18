"""TKT-012b · fila B5 — la semilla `herramientas.semilla_linea_base_local` admite congelar la línea base.

Cubre TC-80 (CA-18): con la opción de congelar, la obra sembrada queda `ACTIVA` con su línea base
`CONGELADA`; sin ella, `PLANEACION` con `BORRADOR` exactamente como hoy. Es la preparación de datos de
la prueba E2E (fila B6): `M1` `ACTIVA` con línea base congelada y `M2` en `PLANEACION` con `BORRADOR`.

Contrato que fija esta prueba, y que el desarrollador implementa sin cambiarla:

- `sembrar_linea_base(motor, *, codigo, usuario_id, reloj, congelar=False)` devuelve el `obra_id`; con
  `congelar=True` congela la línea base recién materializada con el caso de uso `congelar_linea_base`
  de `cimenta.presupuesto.aplicacion.congelado`, importado en el módulo con ese nombre (no se amplía
  `presupuesto/interfaz.py`).
- `main(argv)` recibe la bandera `--congelar` (asumido: la bandera de línea de comandos, no una variable
  de entorno) y deja `OBRA_ID=<uuid>` en la última línea de stdout. La guarda de base local corre antes
  de cualquier otra cosa, también con la bandera.
- Si el congelado falla (asumido: el diseño no fija el comportamiento), la semilla termina con
  `SystemExit` cuyo mensaje empieza por «No se pudo congelar» y nombra el código de la obra; la obra
  queda como la deja la semilla sin opción (`PLANEACION` con `BORRADOR`, consistente, sin asiento
  `CONGELAR`) y `main()` no imprime `OBRA_ID=`: la preparación del E2E falla en voz alta.
- Un código que ya existe se niega con «Ya existe la obra» sin escribir nada y sin congelar la obra
  existente, esté en `PLANEACION` o ya `ACTIVA`.

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` y rol de aplicación.
El módulo bajo prueba se importa dentro de cada prueba, como en `test_tkt018a_semilla_linea_base`.
"""

from __future__ import annotations

import importlib
import re
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

import psycopg
import pytest

from contrato_error import ConflictoEstado

if TYPE_CHECKING:
    from types import ModuleType

    from conftest import Conectar, DatosPresupuesto, RelojDePrueba
    from sqlalchemy.engine import Engine

NOMBRE_DEL_MODULO: Final = "herramientas.semilla_linea_base_local"
HOST_REMOTO: Final = "db.ejemplo.com"
HOST_LOCAL: Final = "127.0.0.1"
PATRON_OBRA_ID: Final = re.compile(
    r"OBRA_ID=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


# --------------------------------------------------------------------------- ayudas


def semilla() -> ModuleType:
    return importlib.import_module(NOMBRE_DEL_MODULO)


def contar(conexion: psycopg.Connection[tuple[Any, ...]], tabla: str) -> int:
    # `tabla` sale de las constantes de esta prueba, nunca de una entrada externa.
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # type: ignore[arg-type]  # noqa: S608
    assert fila is not None
    return int(fila[0])


def filas_por_tabla(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, int]:
    """Cuántas filas hay en las tablas que una semilla rechazada no puede tocar."""
    return {
        tabla: contar(conexion, tabla)
        for tabla in (
            "obra",
            "importacion",
            "linea_base",
            "linea_base_concepto",
            "explosion_presupuesto",
            "presupuesto_control",
            "insumo",
            "bitacora",
        )
    }


def estados_de(
    conexion: psycopg.Connection[tuple[Any, ...]], obra_id: uuid.UUID
) -> tuple[str, list[tuple[str, int]]]:
    """El estado de la obra y los `(estado, version)` de todas sus líneas base."""
    obra = conexion.execute("SELECT estado FROM obra WHERE id = %s", (obra_id,)).fetchone()
    assert obra is not None
    lineas = conexion.execute(
        "SELECT estado, version FROM linea_base WHERE obra_id = %s ORDER BY version", (obra_id,)
    ).fetchall()
    return obra[0], [(estado, version) for estado, version in lineas]


def acciones_de_bitacora(
    conexion: psycopg.Connection[tuple[Any, ...]], obra_id: uuid.UUID
) -> list[str]:
    """Las acciones asentadas, ordenadas por nombre.

    No se ordena por `ocurrido_en, id`: con el reloj de prueba fijo los asientos comparten instante y su
    `id` es un `uuid4`, así que ese orden es aleatorio. Se afirma el multiconjunto exacto de asientos.
    """
    filas = conexion.execute(
        "SELECT accion::text FROM bitacora WHERE obra_id = %s AND entidad_tipo = 'linea_base'",
        (obra_id,),
    ).fetchall()
    return sorted(fila[0] for fila in filas)


# --------------------------------------------------------------------------- TC-80 · feliz


def test_tkt012b_tc80_ca18_semilla_con_congelar_deja_obra_activa_con_linea_base_congelada(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-80 · CA-18 · RN-01 — con la opción, la obra queda ACTIVA y su línea base CONGELADA.

    Es el estado de la obra `M1` del E2E. La línea base es la versión 1 con el mismo importe de venta que
    deja la semilla sin opción; el congelado la firma con la hora del reloj recibido y con el usuario
    que siembra, y deja la copia física (`linea_base_concepto`, `explosion_presupuesto`,
    `presupuesto_control`) y el asiento `CONGELAR` después del asiento `CONFIRMAR`.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()

    obra_id = modulo.sembrar_linea_base(
        motor_aplicacion,
        codigo="DEMO-M1",
        usuario_id=usuario_id,
        reloj=reloj_de_prueba,
        congelar=True,
    )

    assert isinstance(obra_id, uuid.UUID)
    with conectar("aplicacion", base_de_prueba) as base:
        assert estados_de(base, obra_id) == ("ACTIVA", [("CONGELADA", 1)])
        linea = base.execute(
            "SELECT id, importe_venta, congelada_en, congelada_por_id, motivo "
            "FROM linea_base WHERE obra_id = %s",
            (obra_id,),
        ).fetchall()
        assert len(linea) == 1
        linea_id, importe, congelada_en, congelada_por_id, motivo = linea[0]
        assert importe > Decimal(0)
        assert congelada_en == reloj_de_prueba.ahora
        assert congelada_por_id == usuario_id
        assert isinstance(motivo, str)
        assert motivo.strip() != "", "El congelado exige un motivo y la semilla lo trae"
        for tabla in ("linea_base_concepto", "explosion_presupuesto", "presupuesto_control"):
            copiadas = base.execute(
                f"SELECT count(*) FROM {tabla} WHERE linea_base_id = %s",  # noqa: S608
                (linea_id,),
            ).fetchone()
            assert copiadas is not None
            assert copiadas[0] > 0, f"El congelado copia físicamente {tabla}"
        assert acciones_de_bitacora(base, obra_id) == ["CONFIRMAR", "CONGELAR"]


def test_tkt012b_tc80_ca18_semilla_sin_congelar_sigue_en_planeacion_con_borrador(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-80 · CA-18 — sin regresión: sin la opción (o con `congelar=False`) todo queda como hoy.

    La obra `M2` del E2E: `PLANEACION` con una línea base `BORRADOR` versión 1 sin datos de congelado,
    solo el asiento `CONFIRMAR` y ninguna copia congelada.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()

    por_omision = modulo.sembrar_linea_base(
        motor_aplicacion, codigo="DEMO-M2", usuario_id=usuario_id, reloj=reloj_de_prueba
    )
    explicita = modulo.sembrar_linea_base(
        motor_aplicacion,
        codigo="DEMO-M2B",
        usuario_id=usuario_id,
        reloj=reloj_de_prueba,
        congelar=False,
    )

    with conectar("aplicacion", base_de_prueba) as base:
        for obra_id in (por_omision, explicita):
            assert estados_de(base, obra_id) == ("PLANEACION", [("BORRADOR", 1)])
            datos = base.execute(
                "SELECT lb.congelada_en, lb.congelada_por_id, lb.motivo, "
                "(SELECT count(*) FROM linea_base_concepto WHERE linea_base_id = lb.id) "
                "FROM linea_base lb WHERE lb.obra_id = %s",
                (obra_id,),
            ).fetchall()
            assert datos == [(None, None, None, 0)]
            assert acciones_de_bitacora(base, obra_id) == ["CONFIRMAR"]


def test_tkt012b_tc80_ca18_dos_obras_una_congelada_y_otra_borrador_no_se_afectan(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-80 · CA-18 · RN-01 — `M1` congelada y `M2` en borrador conviven; congelar `M1` no toca `M2`.

    Es exactamente lo que siembra `preparacion-global.ts` (fila B5) para el E2E: dos obras con código
    distinto, y la segunda siembra reutiliza el insumo de mano de obra de la primera (comprobación E-7).
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()

    m2 = modulo.sembrar_linea_base(
        motor_aplicacion, codigo="DEMO-M2", usuario_id=usuario_id, reloj=reloj_de_prueba
    )
    with conectar("aplicacion", base_de_prueba) as base:
        antes_de_m2 = base.execute(
            "SELECT id, estado, version, importe_venta, congelada_en FROM linea_base "
            "WHERE obra_id = %s",
            (m2,),
        ).fetchall()

        m1 = modulo.sembrar_linea_base(
            motor_aplicacion,
            codigo="DEMO-M1",
            usuario_id=usuario_id,
            reloj=reloj_de_prueba,
            congelar=True,
        )

        assert m1 != m2
        assert estados_de(base, m1) == ("ACTIVA", [("CONGELADA", 1)])
        assert estados_de(base, m2) == ("PLANEACION", [("BORRADOR", 1)])
        despues_de_m2 = base.execute(
            "SELECT id, estado, version, importe_venta, congelada_en FROM linea_base "
            "WHERE obra_id = %s",
            (m2,),
        ).fetchall()
        assert despues_de_m2 == antes_de_m2
        mano_de_obra = base.execute(
            "SELECT count(*) FROM insumo WHERE codigo = 'MO-001'"
        ).fetchone()
        assert mano_de_obra == (1,), "La segunda siembra reutiliza el insumo de la primera"


# --------------------------------------------------------------------------- TC-80 · rechazos


def test_tkt012b_tc80_ca18_codigo_de_obra_activa_congelada_se_niega_sin_escribir(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-80 · CA-18 · RN-01 — rechazo: sembrar con congelar sobre el código de una obra ya ACTIVA se niega.

    «Ya existe la obra DEMO-M1» con `SystemExit`: no se crea otra línea base ni se congela una segunda
    vez; el conteo de las ocho tablas que la semilla toca no cambia y la obra existente conserva su
    línea base `CONGELADA` versión 1 y su estado `ACTIVA`.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()
    obra_id = modulo.sembrar_linea_base(
        motor_aplicacion,
        codigo="DEMO-M1",
        usuario_id=usuario_id,
        reloj=reloj_de_prueba,
        congelar=True,
    )
    with conectar("aplicacion", base_de_prueba) as base:
        antes = filas_por_tabla(base)
        assert estados_de(base, obra_id) == ("ACTIVA", [("CONGELADA", 1)])

        with pytest.raises(SystemExit) as salida:
            modulo.sembrar_linea_base(
                motor_aplicacion,
                codigo="DEMO-M1",
                usuario_id=usuario_id,
                reloj=reloj_de_prueba,
                congelar=True,
            )

        assert isinstance(salida.value.code, str), salida.value.code
        assert "Ya existe la obra" in salida.value.code
        assert "DEMO-M1" in salida.value.code
        assert filas_por_tabla(base) == antes
        assert estados_de(base, obra_id) == ("ACTIVA", [("CONGELADA", 1)])


def test_tkt012b_tc80_ca18_codigo_de_obra_en_planeacion_no_se_congela_a_posteriori(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-80 · CA-18 · RN-01 — rechazo: la opción no congela una obra que ya existe en PLANEACION.

    La semilla solo congela lo que ella misma acaba de sembrar. Con el código de una obra existente en
    `PLANEACION` con `BORRADOR`, sale con «Ya existe la obra» y la deja intacta: sigue en `PLANEACION`
    con su `BORRADOR`, sin asiento `CONGELAR` y sin que cambie ninguna tabla.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()
    obra_id = modulo.sembrar_linea_base(
        motor_aplicacion, codigo="DEMO-M2", usuario_id=usuario_id, reloj=reloj_de_prueba
    )
    with conectar("aplicacion", base_de_prueba) as base:
        antes = filas_por_tabla(base)

        with pytest.raises(SystemExit) as salida:
            modulo.sembrar_linea_base(
                motor_aplicacion,
                codigo="DEMO-M2",
                usuario_id=usuario_id,
                reloj=reloj_de_prueba,
                congelar=True,
            )

        assert isinstance(salida.value.code, str), salida.value.code
        assert "Ya existe la obra" in salida.value.code
        assert "DEMO-M2" in salida.value.code
        assert filas_por_tabla(base) == antes
        assert estados_de(base, obra_id) == ("PLANEACION", [("BORRADOR", 1)])
        assert acciones_de_bitacora(base, obra_id) == ["CONFIRMAR"]


def test_tkt012b_tc80_ca18_si_el_congelado_falla_la_semilla_no_queda_a_medias(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-80 · CA-18 · RN-01 — rechazo: si el congelado se niega, `SystemExit` y la obra queda consistente.

    El caso de uso `congelar_linea_base` (que el módulo importa con ese nombre) se sustituye por uno que
    lanza el `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` del contrato. La semilla lo traduce a
    `SystemExit` «No se pudo congelar» con el código de la obra; no lo deja escapar como traza ni lo traga.
    La obra queda en `PLANEACION` con su `BORRADOR` versión 1 —el estado de la semilla sin opción,
    nunca una obra `ACTIVA` sin línea base congelada— y sin asiento `CONGELAR`.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()
    llamadas: list[uuid.UUID] = []

    def congelar_que_se_niega(*_: object, linea_base_id: uuid.UUID, **__: object) -> uuid.UUID:
        llamadas.append(linea_base_id)
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje="La obra DEMO-FALLA no admite esta operación.",
            detalle={"linea_base_id": linea_base_id},
        )

    monkeypatch.setattr(modulo, "congelar_linea_base", congelar_que_se_niega)

    with pytest.raises(SystemExit) as salida:
        modulo.sembrar_linea_base(
            motor_aplicacion,
            codigo="DEMO-FALLA",
            usuario_id=usuario_id,
            reloj=reloj_de_prueba,
            congelar=True,
        )

    assert isinstance(salida.value.code, str), salida.value.code
    assert salida.value.code.startswith("No se pudo congelar")
    assert "DEMO-FALLA" in salida.value.code
    assert len(llamadas) == 1, "La semilla intentó congelar la línea base una sola vez"
    with conectar("aplicacion", base_de_prueba) as base:
        obra = base.execute("SELECT id FROM obra WHERE codigo = 'DEMO-FALLA'").fetchall()
        assert len(obra) == 1
        obra_id = obra[0][0]
        assert estados_de(base, obra_id) == ("PLANEACION", [("BORRADOR", 1)])
        assert acciones_de_bitacora(base, obra_id) == ["CONFIRMAR"]
        copiadas = base.execute(
            "SELECT count(*) FROM linea_base_concepto lbc "
            "JOIN linea_base lb ON lb.id = lbc.linea_base_id WHERE lb.obra_id = %s",
            (obra_id,),
        ).fetchone()
        assert copiadas == (0,), "Un congelado fallido no deja copias a medias"
        linea = base.execute("SELECT id FROM linea_base WHERE obra_id = %s", (obra_id,)).fetchall()
        assert llamadas == [fila[0] for fila in linea], (
            "Intentó congelar la línea base de la obra sembrada, no otra"
        )


# --------------------------------------------------------------------------- TC-80 · main()


def entorno_de_main(monkeypatch: pytest.MonkeyPatch, motor: Engine) -> ModuleType:
    """Entorno de una siembra local; solo `crear_motor_aplicacion` apunta al contenedor de la prueba."""
    for variable in ("PGHOSTADDR", "PGSERVICE"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("CIMENTA_DB_HOST", HOST_LOCAL)
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "5432")
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "postgres")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_APLICACION", "contrasena-de-prueba")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", "contrasena-de-prueba")
    monkeypatch.delenv("CIMENTA_SEMILLA_LB_CODIGO", raising=False)
    monkeypatch.delenv("CIMENTA_SEMILLA_LB_CORREO", raising=False)
    modulo = semilla()
    monkeypatch.setattr(modulo, "crear_motor_aplicacion", lambda: motor)
    return modulo


def obra_id_de_la_ultima_linea(capsys: pytest.CaptureFixture[str]) -> uuid.UUID:
    lineas = [linea for linea in capsys.readouterr().out.splitlines() if linea.strip()]
    assert lineas, "main() no imprimió nada"
    coincide = PATRON_OBRA_ID.fullmatch(lineas[-1])
    assert coincide is not None, f"La última línea no es OBRA_ID=<uuid>: {lineas[-1]!r}"
    return uuid.UUID(coincide.group(1))


def test_tkt012b_tc80_ca18_main_con_bandera_congelar_deja_obra_activa_y_su_obra_id(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-80 · CA-18 — `main(["--congelar"])` devuelve 0, congela y la última línea es `OBRA_ID=<uuid>`.

    Es la invocación de `preparacion-global.ts`. La obra con ese `OBRA_ID` y el código de
    `CIMENTA_SEMILLA_LB_CODIGO` queda `ACTIVA` con su línea base `CONGELADA`; la misma llamada sin la
    bandera deja `PLANEACION` con `BORRADOR` (mismo contrato que `COD-3` de TKT-018a).
    """
    correo = "director-semilla@cimenta.test"
    datos_presupuesto.usuario(correo)
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", correo)

    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-MAIN-M1")
    assert modulo.main(["--congelar"]) == 0
    congelada = obra_id_de_la_ultima_linea(capsys)

    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-MAIN-M2")
    assert modulo.main([]) == 0
    borrador = obra_id_de_la_ultima_linea(capsys)

    with conectar("aplicacion", base_de_prueba) as base:
        assert base.execute("SELECT id FROM obra WHERE codigo = 'DEMO-MAIN-M1'").fetchall() == [
            (congelada,)
        ]
        assert estados_de(base, congelada) == ("ACTIVA", [("CONGELADA", 1)])
        assert base.execute("SELECT id FROM obra WHERE codigo = 'DEMO-MAIN-M2'").fetchall() == [
            (borrador,)
        ]
        assert estados_de(base, borrador) == ("PLANEACION", [("BORRADOR", 1)])


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("CIMENTA_DB_HOST", HOST_REMOTO),
        ("PGHOSTADDR", "10.0.0.5"),
        ("PGSERVICE", "produccion"),
    ],
    ids=["host_remoto", "pghostaddr", "pgservice"],
)
def test_tkt012b_tc80_ca18_main_con_bandera_congelar_sigue_negando_bases_que_no_son_locales(
    variable: str, valor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-80 · CA-18 · RNF-07 — rechazo: la opción de congelar no abre ninguna puerta a una base remota.

    Con la bandera y un destino que no es local, `main()` termina con `SystemExit` «Negado» que nombra lo
    negado, y `herramientas.conexion.create_engine` no se llama: no se conectó, así que no se sembró
    ni se congeló nada.
    """
    llamadas: list[tuple[Any, ...]] = []

    def motor_prohibido(*args: Any, **_: Any) -> Any:
        llamadas.append(args)
        raise RuntimeError("La semilla abrió un motor de base de datos cuando debía negarse")

    for nombre in ("PGHOSTADDR", "PGSERVICE"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("CIMENTA_DB_HOST", HOST_LOCAL)
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "5432")
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "postgres")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_APLICACION", "contrasena-de-prueba")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", "contrasena-de-prueba")
    monkeypatch.setattr("herramientas.conexion.create_engine", motor_prohibido)
    monkeypatch.setenv(variable, valor)
    modulo = semilla()

    with pytest.raises(SystemExit) as salida:
        modulo.main(["--congelar"])

    assert isinstance(salida.value.code, str), salida.value.code
    assert "Negado" in salida.value.code
    assert (valor if variable == "CIMENTA_DB_HOST" else variable) in salida.value.code
    assert llamadas == []


def test_tkt012b_tc80_ca18_main_si_el_congelado_falla_no_imprime_obra_id(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-80 · CA-18 — rechazo: con el congelado fallido `main(["--congelar"])` sale con `SystemExit` y sin `OBRA_ID=`.

    La preparación del E2E lee la última línea de stdout: si el congelado falla, no debe recibir un
    `OBRA_ID` de una obra que no está congelada. El mensaje empieza por «No se pudo congelar».
    """
    correo = "director-semilla@cimenta.test"
    datos_presupuesto.usuario(correo)
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-MAIN-FALLA")
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", correo)

    def congelar_que_se_niega(*_: object, linea_base_id: uuid.UUID, **__: object) -> uuid.UUID:
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje="La obra DEMO-MAIN-FALLA no admite esta operación.",
            detalle={"linea_base_id": linea_base_id},
        )

    monkeypatch.setattr(modulo, "congelar_linea_base", congelar_que_se_niega)

    with pytest.raises(SystemExit) as salida:
        modulo.main(["--congelar"])

    assert isinstance(salida.value.code, str), salida.value.code
    assert salida.value.code.startswith("No se pudo congelar")
    assert "OBRA_ID=" not in capsys.readouterr().out
    with conectar("aplicacion", base_de_prueba) as base:
        obra = base.execute("SELECT id FROM obra WHERE codigo = 'DEMO-MAIN-FALLA'").fetchall()
        assert len(obra) == 1
        assert estados_de(base, obra[0][0]) == ("PLANEACION", [("BORRADOR", 1)])
