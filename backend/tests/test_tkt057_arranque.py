"""Ajustes del servidor y arranque sin su secreto (TKT-057, filas 11 y 12, criterios CA-14, CA-15, CA-16 y CA-R8).

TC-50 a TC-54 de `design.md` (fila 11): sin Docker, se llama a `servidor.ajustes.cargar_ajustes` con un
mapa como entorno. TC-55 a TC-58 (fila 12): `crear_aplicacion` en proceso y en proceso hijo, `fastapi dev`
y `alembic`. Tampoco piden Docker: ningún caso abre una conexión (RNF-07: la aplicación no necesita la
base para arrancar, y los procesos hijos nunca llegan a ella). Los símbolos de producción se importan
dentro de cada caso, para que cada uno falle por su cuenta y la recolección no se caiga.

Los procesos hijos parten de un entorno sin ninguna variable `CIMENTA_*` (`ENTORNO_BASE`), para que la
`.env` o el entorno del desarrollador no decidan el resultado.
"""

import importlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

VARIABLE_APLICACION = "CIMENTA_DB_CONTRASENA_APLICACION"
VARIABLE_MIGRACION = "CIMENTA_DB_CONTRASENA_MIGRACION"
VARIABLE_LECTURA = "CIMENTA_DB_CONTRASENA_LECTURA"
VARIABLE_ALMACEN = "CIMENTA_ALMACEN_ORIGEN"

CONTRASENA_APLICACION = "secreto-aplicacion-tkt057-9f3a"
CONTRASENA_MIGRACION = "secreto-migracion-tkt057-77c1"
CONTRASENA_LECTURA = "secreto-lectura-tkt057-b402"

BACKEND = Path(__file__).resolve().parents[1]
# Entorno de los procesos hijos: el del test sin ninguna variable `CIMENTA_*`.
ENTORNO_BASE = {
    nombre: valor
    for nombre, valor in {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}.items()
    if not nombre.startswith("CIMENTA_")
}
PLAZO_DE_ARRANQUE = 30.0  # segundos: espera de un proceso externo, no sincronización entre tests


def test_tkt057_ca15_esc1_sin_la_contrasena_de_aplicacion_no_arranca() -> None:
    """TC-50 · CA-15 esc. 1 · RNF-07 — el error nombra la variable que falta y ninguna otra."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({})

    mensaje = str(excepcion.value)
    assert VARIABLE_APLICACION in mensaje
    assert VARIABLE_MIGRACION not in mensaje
    assert VARIABLE_LECTURA not in mensaje
    assert VARIABLE_ALMACEN not in mensaje


def test_tkt057_ca15_esc1_el_error_no_conserva_la_excepcion_original() -> None:
    """TC-50 · CA-15 esc. 1 — `from None` corta la cadena: ni causa ni contexto arrastran la validación."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({})

    assert excepcion.value.__cause__ is None
    assert excepcion.value.__suppress_context__ is True


def test_tkt057_ca15_esc1_la_configuracion_invalida_es_un_runtime_error() -> None:
    """TC-50 · CA-15 esc. 1 — `ConfiguracionInvalida` es un `RuntimeError` que el arranque propaga."""
    from servidor.ajustes import ConfiguracionInvalida

    assert issubclass(ConfiguracionInvalida, RuntimeError)


def test_tkt057_ca16_una_contrasena_vacia_se_trata_como_ausente() -> None:
    """TC-51 · CA-16 · RNF-07 — la variable definida como cadena vacía produce el mismo error que si faltara."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as ausente:
        cargar_ajustes({})
    with pytest.raises(ConfiguracionInvalida) as vacia:
        cargar_ajustes({VARIABLE_APLICACION: ""})

    assert VARIABLE_APLICACION in str(vacia.value)
    assert str(vacia.value) == str(ausente.value)


def test_tkt057_ca16_un_origen_vacio_cuenta_como_no_configurado() -> None:
    """TC-51 · CA-16 — `CIMENTA_ALMACEN_ORIGEN` vacío no es un valor: el origen queda sin configurar."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION, VARIABLE_ALMACEN: ""})

    assert ajustes.almacen_origen is None


def test_tkt057_ca15_esc2_el_servidor_solo_recibe_la_contrasena_de_aplicacion() -> None:
    """TC-52 · CA-15 esc. 2 · RNF-09 — los ajustes no tienen campo de migración ni de lectura."""
    from servidor.ajustes import AjustesServidor, cargar_ajustes

    ajustes = cargar_ajustes(
        {
            VARIABLE_APLICACION: CONTRASENA_APLICACION,
            VARIABLE_MIGRACION: CONTRASENA_MIGRACION,
            VARIABLE_LECTURA: CONTRASENA_LECTURA,
        }
    )

    campos = set(AjustesServidor.model_fields)
    assert campos == {"db_contrasena_aplicacion", "almacen_origen"}
    assert not any("migracion" in campo or "lectura" in campo for campo in campos)
    assert ajustes.db_contrasena_aplicacion.get_secret_value() == CONTRASENA_APLICACION
    assert ajustes.almacen_origen is None


def test_tkt057_ca15_esc2_ninguna_contrasena_aparece_en_repr_ni_en_el_volcado() -> None:
    """TC-52 · CA-15 esc. 2 · RNF-07 — ni `repr` ni `model_dump_json()` contienen las tres contraseñas."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(
        {
            VARIABLE_APLICACION: CONTRASENA_APLICACION,
            VARIABLE_MIGRACION: CONTRASENA_MIGRACION,
            VARIABLE_LECTURA: CONTRASENA_LECTURA,
        }
    )

    for texto in (repr(ajustes), str(ajustes), ajustes.model_dump_json()):
        assert CONTRASENA_APLICACION not in texto
        assert CONTRASENA_MIGRACION not in texto
        assert CONTRASENA_LECTURA not in texto


def test_tkt057_ca15_esc2_sin_las_otras_dos_contrasenas_arranca() -> None:
    """TC-52 · CA-15 esc. 2 — solo con la de aplicación se cargan los ajustes."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION})

    assert ajustes.db_contrasena_aplicacion.get_secret_value() == CONTRASENA_APLICACION


@pytest.mark.parametrize(
    "origen",
    [
        "*",
        "https://a.test/ruta",
        "https://a.test; script-src *",
        "ftp://a.test",
        "https://a.test/",
        "https://a.test:99999999",
        "https://",
        "a.test",
        "https://a.test https://b.test",
        "http://almacen.cimenta.test",
        "http://203.0.113.9:9000",
        "http://localhost.evil.test",
    ],
)
def test_tkt057_ca14_un_origen_que_no_es_http_sin_ruta_se_rechaza(origen: str) -> None:
    """TC-53 · CA-14 · RNF-06 — el error nombra la variable y no contiene el valor.

    Auditoría de seguridad F005: `http` solo se acepta para `localhost` y `127.0.0.1`, con o sin puerto.
    Un origen `http` de cualquier otro host (un nombre o una dirección pública) viajaría sin cifrar hacia
    el almacén de objetos, y `localhost.evil.test` no es `localhost`.
    """
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION, VARIABLE_ALMACEN: origen})

    mensaje = str(excepcion.value)
    assert VARIABLE_ALMACEN in mensaje
    assert VARIABLE_APLICACION not in mensaje
    assert origen not in mensaje
    assert CONTRASENA_APLICACION not in mensaje
    assert excepcion.value.__cause__ is None


@pytest.mark.parametrize(
    "origen",
    [
        "https://almacen.cimenta.test",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost",
        "http://127.0.0.1",
    ],
)
def test_tkt057_ca14_un_origen_http_sin_ruta_se_acepta(origen: str) -> None:
    """TC-53 · CA-14 · RNF-06 — esquema, host y puerto opcional se guardan tal cual.

    `https` vale para cualquier host; `http`, solo para `localhost` y `127.0.0.1` (MinIO local), con o sin puerto.
    """
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION, VARIABLE_ALMACEN: origen})

    assert ajustes.almacen_origen == origen


def test_tkt057_ca14_sin_la_variable_el_origen_del_almacen_es_nulo() -> None:
    """TC-53 · CA-14 esc. 2 — la variable es opcional: sin ella no hay origen externo."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION})

    assert ajustes.almacen_origen is None


def test_tkt057_ca15_con_un_mapa_explicito_no_se_lee_el_entorno_del_proceso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-54 · CA-15 — una variable presente en `os.environ` pero ausente del mapa no entra en los ajustes."""
    from servidor.ajustes import cargar_ajustes

    monkeypatch.setenv(VARIABLE_ALMACEN, "https://del-proceso.test")

    ajustes = cargar_ajustes({VARIABLE_APLICACION: CONTRASENA_APLICACION})

    assert ajustes.almacen_origen is None


def test_tkt057_ca15_esc1_con_un_mapa_explicito_la_contrasena_del_proceso_no_sirve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-54 · CA-15 esc. 1 — la contraseña en `os.environ` no sustituye a la que falta en el mapa."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    monkeypatch.setenv(VARIABLE_APLICACION, CONTRASENA_APLICACION)

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({})

    assert VARIABLE_APLICACION in str(excepcion.value)


def test_tkt057_ca15_sin_mapa_se_lee_el_entorno_del_proceso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-54 · CA-15 — con `None` se lee `os.environ`, y una variable vacía cuenta como ausente."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    monkeypatch.setenv(VARIABLE_APLICACION, CONTRASENA_APLICACION)
    monkeypatch.setenv(VARIABLE_ALMACEN, "http://localhost:9000")

    ajustes = cargar_ajustes(None)

    assert ajustes.db_contrasena_aplicacion.get_secret_value() == CONTRASENA_APLICACION
    assert ajustes.almacen_origen == "http://localhost:9000"

    monkeypatch.setenv(VARIABLE_APLICACION, "")
    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(None)
    assert VARIABLE_APLICACION in str(excepcion.value)


# --------------------------------------------------------------------------- ayudas de los procesos hijos


def ejecutar_programa(programa: str, entorno: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """`python -c programa` desde `backend/` con exactamente `entorno`."""
    return subprocess.run(
        [sys.executable, "-c", programa],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def informe(proceso: subprocess.CompletedProcess[str]) -> str:
    return (
        f"código={proceso.returncode}\n--- stdout ---\n{proceso.stdout}\n"
        f"--- stderr ---\n{proceso.stderr}"
    )


def ultima_linea(texto: str) -> str:
    """La última línea no vacía: en una traza de Python es la excepción con su mensaje."""
    lineas = [linea for linea in texto.splitlines() if linea.strip()]
    return lineas[-1] if lineas else ""


def puerto_libre() -> int:
    """Un puerto que el sistema operativo acaba de asignar y que se libera antes de usarlo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidato:
        candidato.bind(("127.0.0.1", 0))
        return int(candidato.getsockname()[1])


def esperar_openapi(proceso: subprocess.Popen[bytes], puerto: int) -> httpx.Response | None:
    """`GET /openapi.json` hasta que responde 200, el proceso muere o vence el plazo."""
    vence = time.monotonic() + PLAZO_DE_ARRANQUE
    while time.monotonic() < vence and proceso.poll() is None:
        try:
            respuesta = httpx.get(f"http://127.0.0.1:{puerto}/openapi.json", timeout=1)
        except httpx.TransportError:
            time.sleep(0.25)
            continue
        if respuesta.status_code == 200:
            return respuesta
        time.sleep(0.25)
    return None


def terminar(proceso: subprocess.Popen[bytes]) -> None:
    """Termina el proceso del servidor; si no cede en 10 s, lo mata."""
    if proceso.poll() is not None:
        return
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()
        proceso.wait(timeout=10)


# El proceso imprime primero lo que ve de la variable (anti-verde vacío: una variable vacía debe llegar
# vacía, no desaparecer) y después construye la aplicación igual que `servidor.principal`: con
# `os.environ` y sin pasar `entorno`.
PROGRAMA_CREAR_APLICACION = f"""
import io
import os

print("VARIABLE=" + repr(os.environ.get("{VARIABLE_APLICACION}")))

from servidor.fabrica import crear_aplicacion

crear_aplicacion(destino_registro=io.StringIO())
print("ARRANCO")
"""


def crear_en_proceso(**variables: str) -> subprocess.CompletedProcess[str]:
    """`crear_aplicacion()` en un proceso con migración y lectura reconocibles más las `variables` dadas."""
    entorno = {
        **ENTORNO_BASE,
        VARIABLE_MIGRACION: CONTRASENA_MIGRACION,
        VARIABLE_LECTURA: CONTRASENA_LECTURA,
        **variables,
    }
    return ejecutar_programa(PROGRAMA_CREAR_APLICACION, entorno)


# --------------------------------------------------------------------------- TC-55


def test_tkt057_ca15_esc1_proceso_sin_la_contrasena_de_aplicacion_no_arranca() -> None:
    """TC-55 · CA-15 esc. 1 · RNF-07 — `crear_aplicacion()` termina con error que nombra la variable y ningún valor.

    El proceso tiene las contraseñas de migración y lectura con valores reconocibles: el error no
    puede nombrarlas ni mostrarlas, y su presencia no sustituye a la que falta.
    """
    proceso = crear_en_proceso()

    assert "VARIABLE=None" in proceso.stdout, informe(proceso)  # anti-verde vacío: de verdad falta
    assert proceso.returncode != 0, informe(proceso)
    assert "ARRANCO" not in proceso.stdout, informe(proceso)
    error = ultima_linea(proceso.stderr)
    assert "ConfiguracionInvalida" in error, informe(proceso)
    assert VARIABLE_APLICACION in error, informe(proceso)
    assert VARIABLE_MIGRACION not in error
    assert VARIABLE_LECTURA not in error
    for valor in (CONTRASENA_MIGRACION, CONTRASENA_LECTURA):
        assert valor not in proceso.stdout + proceso.stderr, informe(proceso)


def test_tkt057_ca16_proceso_con_la_contrasena_vacia_falla_con_el_mismo_error() -> None:
    """TC-55 · CA-16 · RNF-07 — definida pero vacía: el mismo error que si faltara, sin ningún valor."""
    ausente = crear_en_proceso()
    vacia = crear_en_proceso(**{VARIABLE_APLICACION: ""})

    assert "VARIABLE=''" in vacia.stdout, informe(
        vacia
    )  # anti-verde vacío: llegó vacía, no ausente
    assert vacia.returncode != 0, informe(vacia)
    assert "ARRANCO" not in vacia.stdout, informe(vacia)
    assert VARIABLE_APLICACION in ultima_linea(vacia.stderr), informe(vacia)
    assert ultima_linea(vacia.stderr) == ultima_linea(ausente.stderr), (
        f"--- ausente ---\n{informe(ausente)}\n--- vacía ---\n{informe(vacia)}"
    )
    for valor in (CONTRASENA_MIGRACION, CONTRASENA_LECTURA):
        assert valor not in vacia.stdout + vacia.stderr, informe(vacia)


def test_tkt057_ca15_esc1_sin_la_contrasena_no_se_configura_el_registro_ni_se_crea_el_motor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-55 · CA-15 esc. 1 — `crear_aplicacion(entorno={})` lanza antes del registro y de cualquier motor.

    `cargar_ajustes` es la primera línea de la fábrica (diseño, «Configuración del servidor»): con
    espías en `configurar_registro` y en `crear_motor_aplicacion`, ninguno se llama. Una contraseña
    presente en `os.environ` no cuenta: el mapa explícito manda.
    """
    from servidor.ajustes import ConfiguracionInvalida

    fabrica = importlib.import_module("servidor.fabrica")
    llamadas: list[str] = []
    monkeypatch.setattr(fabrica, "crear_motor_aplicacion", lambda *a, **k: llamadas.append("motor"))
    monkeypatch.setattr(fabrica, "configurar_registro", lambda *a, **k: llamadas.append("registro"))
    monkeypatch.setenv(VARIABLE_APLICACION, CONTRASENA_APLICACION)
    registro = io.StringIO()

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        fabrica.crear_aplicacion(destino_registro=registro, entorno={})

    assert VARIABLE_APLICACION in str(excepcion.value)
    assert CONTRASENA_APLICACION not in str(excepcion.value)
    assert llamadas == []
    assert registro.getvalue() == ""


def test_tkt057_ca15_el_motor_se_crea_con_la_contrasena_de_los_ajustes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-55 · CA-15 · RNF-07 — el proveedor perezoso pasa a `crear_motor_aplicacion` la contraseña de los ajustes.

    Construir la aplicación no crea el motor (es perezoso); el primer uso del proveedor sí, con la
    contraseña que salió del mapa `entorno` y una sola vez (`functools.cache`).
    """
    fabrica = importlib.import_module("servidor.fabrica")
    recibidas: list[object] = []
    motor_falso = object()

    def motor_espia(contrasena: str | None = None) -> object:
        recibidas.append(contrasena)
        return motor_falso

    montaje: dict[str, object] = {}
    montar_original = fabrica.montar_identidad

    def montar_espia(aplicacion: object, **opciones: object) -> object:
        montaje.update(opciones)
        return montar_original(aplicacion, **opciones)

    monkeypatch.setattr(fabrica, "crear_motor_aplicacion", motor_espia)
    monkeypatch.setattr(fabrica, "montar_identidad", montar_espia)

    fabrica.crear_aplicacion(
        destino_registro=io.StringIO(), entorno={VARIABLE_APLICACION: CONTRASENA_APLICACION}
    )

    assert recibidas == []  # perezoso: construir la aplicación no crea el motor
    proveedor = montaje["proveedor_motor"]
    assert callable(proveedor)
    assert proveedor() is motor_falso
    assert proveedor() is motor_falso
    assert recibidas == [CONTRASENA_APLICACION]


# --------------------------------------------------------------------------- conexión (`herramientas/conexion.py`)


def fijar_destino_de_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """Destino de base de pruebas, sin la contraseña de aplicación: la contraseña la decide cada caso."""
    monkeypatch.delenv(VARIABLE_APLICACION, raising=False)
    monkeypatch.setenv("CIMENTA_DB_HOST", "bd.test")
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "5432")
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "cimenta")


def test_tkt057_ca15_url_aplicacion_usa_la_contrasena_recibida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-15 · RNF-07 — `url_aplicacion(contrasena)` usa el argumento y no lee la variable de la contraseña."""
    from herramientas.conexion import url_aplicacion

    fijar_destino_de_base(monkeypatch)

    url = url_aplicacion(CONTRASENA_APLICACION)

    assert url.password == CONTRASENA_APLICACION
    assert url.username == "cimenta_aplicacion"
    assert (url.host, url.port, url.database) == ("bd.test", 5432, "cimenta")


def test_tkt057_ca15_url_aplicacion_sin_argumento_lee_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-15 · RNF-07 — sin argumento, `url_aplicacion()` conserva su comportamiento: lee la variable (regresión)."""
    from herramientas.conexion import url_aplicacion

    fijar_destino_de_base(monkeypatch)
    monkeypatch.setenv(VARIABLE_APLICACION, CONTRASENA_APLICACION)

    assert url_aplicacion().password == CONTRASENA_APLICACION


def test_tkt057_ca15_url_aplicacion_sin_argumento_y_sin_variable_nombra_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-15 · RNF-07 — sin argumento y sin variable, el error nombra `CIMENTA_DB_CONTRASENA_APLICACION` (regresión)."""
    from herramientas.conexion import url_aplicacion

    fijar_destino_de_base(monkeypatch)

    with pytest.raises(RuntimeError, match=VARIABLE_APLICACION):
        url_aplicacion()


def test_tkt057_ca15_crear_motor_aplicacion_usa_la_contrasena_recibida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-15 · RNF-07 — `crear_motor_aplicacion(contrasena)` se la pasa a la URL; crear el motor no conecta."""
    from herramientas.conexion import crear_motor_aplicacion

    fijar_destino_de_base(monkeypatch)

    motor = crear_motor_aplicacion(CONTRASENA_APLICACION)
    try:
        assert motor.url.password == CONTRASENA_APLICACION
        assert motor.url.username == "cimenta_aplicacion"
    finally:
        motor.dispose()


# --------------------------------------------------------------------------- CA-15 esc. 2


def test_tkt057_ca15_esc2_en_proceso_arranca_sin_las_contrasenas_de_migracion_y_lectura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-15 esc. 2 · RNF-09 — con solo la contraseña de aplicación, `crear_aplicacion` arranca y publica el contrato.

    NACE EN VERDE a propósito: hoy la fábrica ya arranca sin ninguna variable de base. Fija que, cuando
    `cargar_ajustes` exija la de aplicación, el servidor no pida además la de migración ni la de lectura.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    for nombre in (VARIABLE_MIGRACION, VARIABLE_LECTURA):
        monkeypatch.delenv(nombre, raising=False)
    fabrica = importlib.import_module("servidor.fabrica")

    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(), entorno={VARIABLE_APLICACION: CONTRASENA_APLICACION}
    )

    assert isinstance(aplicacion, FastAPI)
    respuesta = TestClient(aplicacion, raise_server_exceptions=False).get("/openapi.json")
    assert respuesta.status_code == 200


# --------------------------------------------------------------------------- TC-56

PROGRAMA_CA_R8 = """
import io
import json

from fastapi.testclient import TestClient

from servidor.fabrica import crear_aplicacion

aplicacion = crear_aplicacion(destino_registro=io.StringIO())
cliente = TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)
no_existe = cliente.get("/api/v1/no-existe")
csrf = cliente.get("/api/v1/sesion/csrf")
sesion = cliente.get("/api/v1/sesion")
print(json.dumps({
    "estados": [no_existe.status_code, csrf.status_code, sesion.status_code],
    "token": csrf.json().get("token"),
    "cookie": cliente.cookies.get("cimenta_csrf"),
    "tipo_sesion": sesion.json().get("tipo"),
}))
"""


def test_tkt057_car8_proceso_con_solo_la_contrasena_de_aplicacion_atiende_sin_tocar_la_base() -> (
    None
):
    """TC-56 · CA-R8 · CA-15 esc. 2 — TC-75 reescrito: solo `CIMENTA_DB_CONTRASENA_APLICACION`, sin host, puerto ni base.

    NACE EN VERDE a propósito: es regresión, hoy la fábrica ya atiende estas tres rutas sin base.
    Cubre lo que TC-75 (`test_servidor_arranque.py`) no afirma: el token del cuerpo es el mismo valor
    de la cookie `cimenta_csrf`.
    """
    entorno = {**ENTORNO_BASE, VARIABLE_APLICACION: CONTRASENA_APLICACION}
    assert [n for n in entorno if n.startswith("CIMENTA_")] == [VARIABLE_APLICACION]

    proceso = ejecutar_programa(PROGRAMA_CA_R8, entorno)

    assert proceso.returncode == 0, informe(proceso)
    resultado = json.loads(proceso.stdout.strip().splitlines()[-1])
    assert resultado["estados"] == [404, 200, 401]
    assert resultado["token"]
    assert resultado["cookie"] == resultado["token"]
    assert resultado["tipo_sesion"] == "SESION"
    assert CONTRASENA_APLICACION not in proceso.stdout + proceso.stderr


# --------------------------------------------------------------------------- TC-57


def test_tkt057_ca15_fastapi_dev_sin_la_contrasena_de_aplicacion_no_arranca() -> None:
    """TC-57 · CA-15 esc. 1 · CA-R8 — `fastapi dev` sin la variable termina con error que la nombra.

    La mitad «arranca con la variable» de TC-57 la cubren, reescritos en `test_servidor_arranque.py`,
    `test_tkt005_ca12_comando_de_desarrollo_arranca` y
    `test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad`. El proceso tiene las
    contraseñas de migración y lectura con valores reconocibles: no sustituyen a la que falta.
    """
    puerto = puerto_libre()
    entorno = {
        **ENTORNO_BASE,
        "COLUMNS": "250",
        VARIABLE_MIGRACION: CONTRASENA_MIGRACION,
        VARIABLE_LECTURA: CONTRASENA_LECTURA,
    }
    with tempfile.TemporaryFile() as salida:
        proceso = subprocess.Popen(
            [sys.executable, "-m", "fastapi", "dev", "--no-reload", "--port", str(puerto)],
            cwd=BACKEND,
            env=entorno,
            stdin=subprocess.DEVNULL,
            stdout=salida,
            stderr=subprocess.STDOUT,
        )
        try:
            respuesta = esperar_openapi(proceso, puerto)
            codigo_de_salida = proceso.poll()
        finally:
            terminar(proceso)
        salida.seek(0)
        registro = salida.read().decode("utf-8", errors="replace")

    assert respuesta is None, f"fastapi dev arrancó sin la contraseña de aplicación.\n{registro}"
    assert codigo_de_salida not in (None, 0), registro
    assert VARIABLE_APLICACION in registro
    for valor in (CONTRASENA_MIGRACION, CONTRASENA_LECTURA):
        assert valor not in registro


# --------------------------------------------------------------------------- TC-58


def test_tkt057_ca15_esc3_alembic_sin_la_contrasena_de_migracion_falla_nombrandola() -> None:
    """TC-58 · CA-15 esc. 3 · RNF-07 — `alembic upgrade head` sin `CIMENTA_DB_CONTRASENA_MIGRACION` falla nombrándola.

    NACE EN VERDE a propósito: `leer_variable` ya lo hace. Es la prueba de regresión de la parte de
    `M6` que no cambia (la migración sigue exigiendo su propia credencial) y fija que el cambio de la
    fábrica no la relaja. No necesita Docker: falla antes de abrir ninguna conexión.
    """
    entorno = {
        **ENTORNO_BASE,
        "CIMENTA_DB_HOST": "127.0.0.1",
        "CIMENTA_DB_PUERTO": "5432",
        "CIMENTA_DB_NOMBRE": "cimenta",
        VARIABLE_APLICACION: CONTRASENA_APLICACION,
        VARIABLE_LECTURA: CONTRASENA_LECTURA,
    }
    assert VARIABLE_MIGRACION not in entorno

    proceso = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    assert proceso.returncode != 0, informe(proceso)
    assert VARIABLE_MIGRACION in ultima_linea(proceso.stderr), informe(proceso)
    for valor in (CONTRASENA_APLICACION, CONTRASENA_LECTURA):
        assert valor not in proceso.stdout + proceso.stderr, informe(proceso)
