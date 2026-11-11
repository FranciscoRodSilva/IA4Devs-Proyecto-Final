"""TKT-018a · entrega c · fila C1 — la herramienta `herramientas.semilla_linea_base_local` (CA-S1, Should).

Cubre TC-S1 (la semilla deja una línea base `BORRADOR` y una segunda corrida con otro código también
termina: comprobación E-7), TC-S2 (la guarda de base local se niega antes de abrir ninguna conexión, y
un entorno sin `CIMENTA_DB_HOST` se niega con `SystemExit`, no con `RuntimeError`) y TC-S3 (un código
repetido se niega sin escribir nada). PostgreSQL real con testcontainers, esquema por
`alembic upgrade head` y rol de aplicación: la semilla recibe el motor del rol de aplicación.

El módulo bajo prueba se importa dentro de cada prueba, como pide `conftest`, para que la recolección
no dependa de un símbolo de producción que todavía puede no existir.
"""

from __future__ import annotations

import importlib
import re
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

import psycopg
import pytest

if TYPE_CHECKING:
    from types import ModuleType

    from conftest import Conectar, DatosPresupuesto, RelojDePrueba
    from sqlalchemy.engine import Engine

NOMBRE_DEL_MODULO: Final = "herramientas.semilla_linea_base_local"

# Los únicos destinos que la guarda admite. Se repiten aquí a propósito: la prueba no toma del módulo
# bajo prueba el dato contra el que lo juzga.
HOST_REMOTO: Final = "db.ejemplo.com"
HOST_LOCAL: Final = "127.0.0.1"


# --------------------------------------------------------------------------- ayudas


def semilla() -> ModuleType:
    """El módulo bajo prueba, importado al primer uso."""
    return importlib.import_module(NOMBRE_DEL_MODULO)


class MotorProhibido:
    """Sustituye a `herramientas.conexion.create_engine`: registra la llamada y falla.

    Es el `create_engine` que usa `crear_motor_aplicacion()`. Si la guarda de base local funciona, la
    semilla se niega antes de llegar aquí y `llamadas` queda vacía.
    """

    def __init__(self) -> None:
        self.llamadas: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.llamadas.append(args)
        raise RuntimeError("La semilla abrió un motor de base de datos cuando debía negarse")


def entorno_de_aplicacion(monkeypatch: pytest.MonkeyPatch, *, host: str | None) -> MotorProhibido:
    """Deja el entorno como lo tendría quien siembra y sustituye `create_engine` por uno que falla.

    Define todo lo demás que `crear_motor_aplicacion()` leería (puerto, nombre y contraseña del rol de
    aplicación), para que lo que se niegue sea el destino y no una variable ajena. `host=None` borra
    `CIMENTA_DB_HOST`. Borra `PGHOSTADDR` y `PGSERVICE`, que redirigen libpq.
    """
    for variable in ("PGHOSTADDR", "PGSERVICE"):
        monkeypatch.delenv(variable, raising=False)
    if host is None:
        monkeypatch.delenv("CIMENTA_DB_HOST", raising=False)
    else:
        monkeypatch.setenv("CIMENTA_DB_HOST", host)
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "5432")
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "postgres")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_APLICACION", "contrasena-de-prueba")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", "contrasena-de-prueba")
    espia = MotorProhibido()
    monkeypatch.setattr("herramientas.conexion.create_engine", espia)
    return espia


def contar(conexion: psycopg.Connection[tuple[Any, ...]], tabla: str) -> int:
    # `tabla` sale de las constantes de esta prueba, nunca de una entrada externa.
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # type: ignore[arg-type]  # noqa: S608
    assert fila is not None
    return int(fila[0])


def filas_por_tabla(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, int]:
    """Cuántas filas hay en las tablas que una semilla fallida no puede tocar."""
    return {
        tabla: contar(conexion, tabla)
        for tabla in ("obra", "importacion", "linea_base", "insumo", "bitacora")
    }


# --------------------------------------------------------------------------- TC-S1


def test_tkt018a_semilla_crea_linea_base_borrador(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-S1 · CA-S1 · HDU-001 esc. 14 · RN-01 — la semilla deja la obra en PLANEACION con una línea base BORRADOR.

    `sembrar_linea_base(…, codigo="DEMO-1")` devuelve el `obra_id` de una obra en `PLANEACION` con su
    código, su empresa activa y su autor; una `linea_base` `BORRADOR` versión 1 con `importe_venta > 0`;
    una importación `CONFIRMADO` y un asiento `CONFIRMAR` de la línea base en la bitácora, con la hora
    del reloj recibido. Una segunda llamada con `codigo="DEMO-2"` también termina (comprobación E-7: el
    insumo de mano de obra que dejó la primera no choca con la segunda) y deja su propia línea base con
    el mismo importe, porque la preparación sintética es la misma.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()

    primera = modulo.sembrar_linea_base(
        motor_aplicacion, codigo="DEMO-1", usuario_id=usuario_id, reloj=reloj_de_prueba
    )

    assert isinstance(primera, uuid.UUID)
    with conectar("aplicacion", base_de_prueba) as base:
        obra = base.execute(
            "SELECT o.codigo, o.estado, o.creado_por_id, o.nombre, o.tipo_contrato, e.activa "
            "FROM obra o JOIN empresa e ON e.id = o.empresa_id WHERE o.id = %s",
            (primera,),
        ).fetchall()
        lineas = base.execute(
            "SELECT estado, version, importe_venta FROM linea_base WHERE obra_id = %s", (primera,)
        ).fetchall()
        importaciones = base.execute(
            "SELECT estado, importado_por_id FROM importacion WHERE obra_id = %s", (primera,)
        ).fetchall()
        asientos = base.execute(
            "SELECT b.accion::text, b.entidad_tipo, b.usuario_id, b.ocurrido_en, "
            "(b.entidad_id = lb.id) FROM bitacora b "
            "JOIN linea_base lb ON lb.obra_id = b.obra_id WHERE b.obra_id = %s",
            (primera,),
        ).fetchall()

        assert obra == [
            (
                "DEMO-1",
                "PLANEACION",
                usuario_id,
                "Obra de demostracion DEMO-1",
                "PRECIO_ALZADO_MAXIMO_GARANTIZADO",
                True,
            )
        ]
        assert [(estado, version) for estado, version, _ in lineas] == [("BORRADOR", 1)]
        importe_primera = lineas[0][2]
        assert importe_primera > Decimal(0)
        assert importaciones == [("CONFIRMADO", usuario_id)]
        assert asientos == [
            ("CONFIRMAR", "linea_base", usuario_id, reloj_de_prueba.ahora, True),
        ]

        segunda = modulo.sembrar_linea_base(
            motor_aplicacion, codigo="DEMO-2", usuario_id=usuario_id, reloj=reloj_de_prueba
        )

        assert segunda != primera
        lineas_segunda = base.execute(
            "SELECT estado, version, importe_venta FROM linea_base WHERE obra_id = %s", (segunda,)
        ).fetchall()
        assert lineas_segunda == [("BORRADOR", 1, importe_primera)]
        mano_de_obra = base.execute(
            "SELECT count(*) FROM insumo WHERE codigo = 'MO-001'"
        ).fetchone()
        assert mano_de_obra == (1,), "La segunda corrida reutiliza el insumo de la primera"
        assert contar(base, "obra") == 2, "Las únicas obras son DEMO-1 y DEMO-2"


# --------------------------------------------------------------------------- TC-S2


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("CIMENTA_DB_HOST", HOST_REMOTO),
        ("PGHOSTADDR", "10.0.0.5"),
        ("PGSERVICE", "produccion"),
    ],
    ids=["host_remoto", "pghostaddr", "pgservice"],
)
def test_tkt018a_semilla_se_niega_contra_base_remota(
    variable: str, valor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-S2 · CA-S1 esc. 2 · RNF-07 — rechazo: la semilla no corre contra una base que no es local.

    Con `CIMENTA_DB_HOST=db.ejemplo.com`, y aparte con `PGHOSTADDR` o `PGSERVICE` definidas (libpq las
    usaría en lugar del host de la URL), `main()` termina con `SystemExit` cuyo mensaje empieza por «Negado» y nombra
    lo negado, y `herramientas.conexion.create_engine` no se llama: no se abrió ninguna conexión, así
    que no se escribió nada.
    """
    espia = entorno_de_aplicacion(monkeypatch, host=HOST_LOCAL)
    monkeypatch.setenv(variable, valor)
    modulo = semilla()

    with pytest.raises(SystemExit) as salida:
        modulo.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert "Negado" in salida.value.code
    assert (valor if variable == "CIMENTA_DB_HOST" else variable) in salida.value.code
    assert espia.llamadas == []


def test_tkt018a_semilla_sin_host_se_niega_con_el_nombre_de_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-S2 (variante) · CA-S1 esc. 2 · RNF-07 — rechazo: sin `CIMENTA_DB_HOST` sale `SystemExit`, no `RuntimeError`.

    `leer_variable` lanza `RuntimeError` con el nombre de la variable; `main()` lo traduce a
    `SystemExit` con el mismo texto, como `semilla_local.main()`, y no abre ninguna conexión.
    """
    espia = entorno_de_aplicacion(monkeypatch, host=None)
    modulo = semilla()

    with pytest.raises(SystemExit) as salida:
        modulo.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert "CIMENTA_DB_HOST" in salida.value.code
    assert espia.llamadas == []


# --------------------------------------------------------------------------- TC-S3


def test_tkt018a_semilla_codigo_repetido(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-S3 · CA-S1 · RN-01 — rechazo: un código repetido se niega y no escribe nada.

    Tras una primera siembra de `DEMO-1`, una segunda con el mismo código termina con `SystemExit`
    «Ya existe la obra DEMO-1» y no cambia el conteo de `obra`, `importacion`, `linea_base`, `insumo`
    ni `bitacora`: la comprobación va dentro de la transacción y antes de cualquier escritura.
    """
    usuario_id = datos_presupuesto.usuario()
    modulo = semilla()
    modulo.sembrar_linea_base(
        motor_aplicacion, codigo="DEMO-1", usuario_id=usuario_id, reloj=reloj_de_prueba
    )
    with conectar("aplicacion", base_de_prueba) as base:
        antes = filas_por_tabla(base)
        assert antes["obra"] == 1, "La precondición es la obra de la primera siembra"
        assert antes["linea_base"] == 1, "La precondición es la línea base de la primera siembra"

        with pytest.raises(SystemExit) as salida:
            modulo.sembrar_linea_base(
                motor_aplicacion, codigo="DEMO-1", usuario_id=usuario_id, reloj=reloj_de_prueba
            )

        assert isinstance(salida.value.code, str), salida.value.code
        assert "Ya existe la obra" in salida.value.code
        assert "DEMO-1" in salida.value.code
        assert filas_por_tabla(base) == antes


# --------------------------------------------------------------------------- COD-3 · SEG-4: main()

# Los valores por omisión se repiten aquí a propósito: la prueba no toma del módulo bajo prueba el
# dato contra el que lo juzga.
CODIGO_POR_OMISION: Final = "DEMO-018A"
CORREO_POR_OMISION: Final = "director_proyectos@cimenta.test"
PATRON_OBRA_ID: Final = re.compile(
    r"OBRA_ID=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def entorno_de_main(monkeypatch: pytest.MonkeyPatch, motor: Engine) -> ModuleType:
    """Deja el entorno de una siembra local y entrega a `main()` el motor del rol de aplicación de la prueba.

    La guarda `exigir_base_local()` corre de verdad, con `CIMENTA_DB_HOST` local y sin `PGHOSTADDR` ni
    `PGSERVICE`. Solo se sustituye `crear_motor_aplicacion`, el punto por el que la semilla abre su
    conexión, para que apunte al contenedor de la prueba y no a ninguna base real. Borra las dos
    variables de la semilla; cada prueba define las que necesita.
    """
    entorno_de_aplicacion(monkeypatch, host=HOST_LOCAL)
    monkeypatch.delenv("CIMENTA_SEMILLA_LB_CODIGO", raising=False)
    monkeypatch.delenv("CIMENTA_SEMILLA_LB_CORREO", raising=False)
    modulo = semilla()
    monkeypatch.setattr(modulo, "crear_motor_aplicacion", lambda: motor)
    return modulo


def obra_id_de_la_ultima_linea(capsys: pytest.CaptureFixture[str]) -> uuid.UUID:
    """El `obra_id` de la última línea no vacía de stdout, que debe ser exactamente `OBRA_ID=<uuid>`."""
    lineas = [linea for linea in capsys.readouterr().out.splitlines() if linea.strip()]
    assert lineas, "main() no imprimió nada"
    coincide = PATRON_OBRA_ID.fullmatch(lineas[-1])
    assert coincide is not None, f"La última línea no es OBRA_ID=<uuid>: {lineas[-1]!r}"
    return uuid.UUID(coincide.group(1))


def obras_con_el_codigo(
    conexion: psycopg.Connection[tuple[Any, ...]], codigo: str
) -> list[uuid.UUID]:
    filas = conexion.execute("SELECT id FROM obra WHERE codigo = %s", (codigo,)).fetchall()
    return [fila[0] for fila in filas]


def test_tkt018a_semilla_main_imprime_obra_id_en_la_ultima_linea(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """COD-3 · CA-S1 · HDU-001 esc. 14 — la última línea de stdout es `OBRA_ID=<uuid>` y es la obra sembrada.

    Es el contrato que lee la preparación del E2E. Con `CIMENTA_SEMILLA_LB_CODIGO` y
    `CIMENTA_SEMILLA_LB_CORREO` definidas, `main()` devuelve 0 y la última línea no vacía de stdout es
    exactamente `OBRA_ID=` y un UUID válido; ese UUID es el de la única fila de `obra` con ese código.
    """
    correo = "residente-semilla@cimenta.test"
    datos_presupuesto.usuario(correo)
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-MAIN")
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", correo)

    resultado = modulo.main()

    assert resultado == 0
    obra_id = obra_id_de_la_ultima_linea(capsys)
    with conectar("aplicacion", base_de_prueba) as base:
        assert obras_con_el_codigo(base, "DEMO-MAIN") == [obra_id]


def test_tkt018a_semilla_main_codigo_vacio_usa_el_codigo_por_omision(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """COD-3 · CA-S1 — una `CIMENTA_SEMILLA_LB_CODIGO` vacía cae al código `DEMO-018A`, no a una obra sin código.

    Un `.env` que deja la variable en blanco no es un código: `main()` siembra la obra `DEMO-018A` y
    su `OBRA_ID` es el de esa fila.
    """
    correo = "residente-semilla@cimenta.test"
    datos_presupuesto.usuario(correo)
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "")
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", correo)

    resultado = modulo.main()

    assert resultado == 0
    obra_id = obra_id_de_la_ultima_linea(capsys)
    with conectar("aplicacion", base_de_prueba) as base:
        assert obras_con_el_codigo(base, CODIGO_POR_OMISION) == [obra_id]
        assert contar(base, "obra") == 1


def test_tkt018a_semilla_main_correo_vacio_usa_al_director_de_proyectos(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """COD-3 · CA-S1 — una `CIMENTA_SEMILLA_LB_CORREO` vacía cae a `director_proyectos@cimenta.test`.

    La obra queda a nombre del usuario con ese correo (`obra.creado_por_id`), no de otro.
    """
    director_id = datos_presupuesto.usuario(CORREO_POR_OMISION)
    datos_presupuesto.usuario("otro-usuario@cimenta.test")
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-CORREO")
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", "")

    resultado = modulo.main()

    assert resultado == 0
    obra_id = obra_id_de_la_ultima_linea(capsys)
    with conectar("aplicacion", base_de_prueba) as base:
        autor = base.execute("SELECT creado_por_id FROM obra WHERE id = %s", (obra_id,)).fetchone()
        assert autor == (director_id,)


def test_tkt018a_semilla_main_sin_el_usuario_se_niega_sin_escribir(
    motor_aplicacion: Engine,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """COD-3 · CA-S1 — rechazo: un correo que no existe termina con `SystemExit` «Falta el usuario» y no escribe nada.

    El mensaje nombra el correo y manda a `herramientas.semilla_local`. No se creó ninguna obra,
    importación, línea base, insumo ni asiento de bitácora, y stdout no lleva `OBRA_ID=`.
    """
    correo = "no-existe@cimenta.test"
    modulo = entorno_de_main(monkeypatch, motor_aplicacion)
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CODIGO", "DEMO-SIN-USUARIO")
    monkeypatch.setenv("CIMENTA_SEMILLA_LB_CORREO", correo)
    with conectar("aplicacion", base_de_prueba) as base:
        antes = filas_por_tabla(base)

        with pytest.raises(SystemExit) as salida:
            modulo.main()

        assert isinstance(salida.value.code, str), salida.value.code
        assert salida.value.code.startswith("Falta el usuario")
        assert correo in salida.value.code
        assert "semilla_local" in salida.value.code
        assert "OBRA_ID=" not in capsys.readouterr().out
        assert filas_por_tabla(base) == antes


def test_tkt018a_semilla_puerto_no_numerico_se_niega_sin_traza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEG-4 · CA-S1 · RNF-07 — rechazo: un `CIMENTA_DB_PUERTO` que no es un número sale con `SystemExit`, no con `ValueError`.

    Con `CIMENTA_DB_PUERTO=no-es-un-numero` y el host local, `int()` en `url_aplicacion` lanza
    `ValueError`; `main()` lo traduce a `SystemExit` con un mensaje que empieza por «Negado» y nombra
    la variable, como `semilla_local.main()`, y no llama a `create_engine`: no se conectó.
    """
    espia = entorno_de_aplicacion(monkeypatch, host=HOST_LOCAL)
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "no-es-un-numero")
    modulo = semilla()

    with pytest.raises(SystemExit) as salida:
        modulo.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert salida.value.code.startswith("Negado")
    assert "CIMENTA_DB_PUERTO" in salida.value.code
    assert espia.llamadas == []
