"""Arranque de la aplicación (TKT-005, fila 5): TC-60, TC-75, TC-76, TC-78 y TC-104.

Sin Docker (CA-R4). `servidor` se importa dentro de cada prueba, con `importlib`: mientras el paquete
no exista, cada prueba que lo necesita falla con su propio `ModuleNotFoundError` y no con un error
de colección. TC-104 es análisis estático de los archivos de prueba y no importa `servidor`.

`corrutinas_registradas` es la ayuda que comparten TC-77 y TC-78 (regla 11 de `CLAUDE.md`, `PA-T9`):
solo mira rutas y manejadores de excepción. El *middleware* de correlación es ASGI por construcción
y queda fuera del recorrido.

TC-77 necesita los manejadores de la fila 6. TC-79 (fila 7) lanza el comando real `fastapi dev`
en un subproceso, con puerto libre y sin recargador, y es la única prueba de este archivo que
abre un puerto.
"""

import ast
import importlib
import inspect
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

BACKEND = Path(__file__).resolve().parents[1]
TESTS = BACKEND / "tests"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8"}

# Los archivos de prueba del ticket. `test_contrato_error_http.py` llega con la fila 6: el patrón
# lo recoge solo, y los cinco de abajo son los que ya deben existir.
PATRONES_DEL_TICKET = ("test_contrato_error_*.py", "test_servidor_*.py", "test_tkt005_*.py")
ARCHIVOS_YA_ESCRITOS = {
    "test_contrato_error_catalogos.py",
    "test_contrato_error_construccion.py",
    "test_tkt005_fronteras.py",
    "test_servidor_correlacion.py",
    "test_servidor_arranque.py",
}
FIXTURES_CON_BASE = {
    "contenedor_postgres",
    "conectar",
    "migrar",
    "base_de_prueba",
    "base_vacia",
    "plantilla_migrada",
    "credenciales",
}

# El proceso limpio construye la aplicación, atiende una petición a una ruta que no existe y mira
# lo que se cargó: el camino del error no toca la base (CA-11 esc. 3, D-3).
PROGRAMA_SIN_BASE = """
import io
import json
import sys

from servidor.fabrica import crear_aplicacion
from fastapi.testclient import TestClient

aplicacion = crear_aplicacion(destino_registro=io.StringIO())
respuesta = TestClient(aplicacion, raise_server_exceptions=False).get("/api/v1/no-existe")

raices = {nombre.partition(".")[0] for nombre in sys.modules}
print(json.dumps({
    "estado": respuesta.status_code,
    "fastapi_cargado": "fastapi" in raices,
    "con_base": sorted(raices & {"sqlalchemy", "psycopg", "psycopg2", "asyncpg", "alembic"}),
}))
"""


def aplicacion_de_la_fabrica() -> FastAPI:
    fabrica = importlib.import_module("servidor.fabrica")
    aplicacion: FastAPI = fabrica.crear_aplicacion(destino_registro=io.StringIO())
    return aplicacion


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido.

    Desde FastAPI 0.159 `include_router` ya no copia las rutas a `app.routes`: deja una ruta
    perezosa que guarda el enrutador original en `original_router`. Sin bajar por ella, una
    `async def` declarada en un enrutador pasaría inadvertida.
    """
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from rutas_de(original.routes)
        elif isinstance(ruta, APIRoute):
            yield ruta


def corrutinas_registradas(aplicacion: FastAPI) -> list[str]:
    """Nombres de las rutas y de los manejadores propios declarados con `async def`.

    Rutas primero y manejadores después. Los manejadores por omisión de FastAPI (módulo `fastapi.`)
    son del framework y no cuentan.
    """
    rutas = [
        ruta.endpoint.__name__
        for ruta in rutas_de(aplicacion.routes)
        if inspect.iscoroutinefunction(ruta.endpoint)
    ]
    manejadores = [
        manejador.__name__
        for manejador in aplicacion.exception_handlers.values()
        if not getattr(manejador, "__module__", "").startswith("fastapi.")
        and inspect.iscoroutinefunction(manejador)
    ]
    return rutas + manejadores


def test_tkt005_ca14_la_aplicacion_no_esta_en_depuracion() -> None:
    """TC-60 · CA-14 — con debug activo Starlette respondería la traza: la fábrica lo fija en False."""
    assert aplicacion_de_la_fabrica().debug is False


def test_tkt005_ca11_el_camino_del_error_no_toca_la_base() -> None:
    """TC-75 · CA-11 esc. 3 (asumido) — construir la aplicación y un 404 no cargan SQLAlchemy ni psycopg."""
    proceso = subprocess.run(
        [sys.executable, "-c", PROGRAMA_SIN_BASE],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )

    assert proceso.returncode == 0, proceso.stderr
    resultado = json.loads(proceso.stdout.strip().splitlines()[-1])
    assert resultado["estado"] == 404
    assert resultado["fastapi_cargado"] is True  # anti-verde vacío: la aplicación sí se construyó
    assert resultado["con_base"] == []


def test_tkt005_ca12_la_fabrica_publica_el_contrato() -> None:
    """TC-76 · CA-12 esc. 1 — GET /openapi.json responde 200 con un OpenAPI 3.x titulado CIMENTA."""
    cliente = TestClient(aplicacion_de_la_fabrica(), raise_server_exceptions=False)

    respuesta = cliente.get("/openapi.json")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["openapi"].startswith("3.")
    assert "paths" in cuerpo
    assert cuerpo["info"]["title"] == "CIMENTA"


def test_tkt005_ca12_una_corrutina_se_detecta() -> None:
    """TC-78 · CA-12 esc. 4 — una ruta o un manejador async def se detectan y se nombran."""
    aplicacion = aplicacion_de_la_fabrica()

    async def ruta_asincrona_de_prueba() -> dict[str, bool]:
        return {"ok": True}

    async def manejador_asincrono_de_prueba(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({}, status_code=500)

    router = APIRouter()
    router.add_api_route("/prueba/asincrona", ruta_asincrona_de_prueba, methods=["GET"])
    aplicacion.include_router(router)
    aplicacion.add_exception_handler(KeyError, manejador_asincrono_de_prueba)

    assert corrutinas_registradas(aplicacion) == [
        "ruta_asincrona_de_prueba",
        "manejador_asincrono_de_prueba",
    ]


def archivos_de_prueba_del_ticket() -> list[Path]:
    encontrados = {ruta for patron in PATRONES_DEL_TICKET for ruta in TESTS.glob(patron)}
    return sorted(encontrados)


def parametros_prohibidos(arbol: ast.AST) -> list[str]:
    """«función:parámetro» de cada función que pide una fixture que depende de la base."""
    hallazgos: list[str] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        argumentos = nodo.args
        todos = [*argumentos.posonlyargs, *argumentos.args, *argumentos.kwonlyargs]
        todos += [a for a in (argumentos.vararg, argumentos.kwarg) if a is not None]
        hallazgos += [f"{nodo.name}:{a.arg}" for a in todos if a.arg in FIXTURES_CON_BASE]
        # `@pytest.mark.usefixtures("contenedor_postgres")` pide la fixture sin ser un parámetro.
        for decorador in nodo.decorator_list:
            if isinstance(decorador, ast.Call) and "usefixtures" in ast.unparse(decorador.func):
                hallazgos += [
                    f"{nodo.name}:{a.value}"
                    for a in decorador.args
                    if isinstance(a, ast.Constant) and a.value in FIXTURES_CON_BASE
                ]
    return hallazgos


def test_tkt005_car4_pruebas_sin_base() -> None:
    """TC-104 · CA-R4 esc. 2 — ninguna prueba de este ticket pide una fixture que abra la base."""
    archivos = archivos_de_prueba_del_ticket()
    assert {a.name for a in archivos} >= ARCHIVOS_YA_ESCRITOS  # anti-verde vacío

    funciones = 0
    hallazgos: list[str] = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        funciones += sum(isinstance(n, ast.FunctionDef) for n in ast.walk(arbol))
        hallazgos += [f"{archivo.name}::{h}" for h in parametros_prohibidos(arbol)]

    assert funciones > 0
    assert hallazgos == []


def ruta_sincrona_de_prueba() -> dict[str, bool]:
    return {"ok": True}


def test_tkt005_ca12_ninguna_ruta_ni_manejador_es_corrutina() -> None:
    """TC-77 · CA-12 esc. 3 — ninguna ruta ni manejador propio de la aplicación se declara con async def."""
    aplicacion = aplicacion_de_la_fabrica()
    router = APIRouter()
    router.add_api_route("/prueba/sincrona", ruta_sincrona_de_prueba, methods=["GET"])
    aplicacion.include_router(router)

    # Anti-verde vacío: el recorrido ve la ruta de prueba y, al menos, los cuatro manejadores del
    # diseño (familia del contrato, 422 de Pydantic, 404 de enrutado y 500), todos de servidor.manejadores.
    assert "ruta_sincrona_de_prueba" in [r.endpoint.__name__ for r in rutas_de(aplicacion.routes)]
    propios = [
        manejador
        for manejador in aplicacion.exception_handlers.values()
        if getattr(manejador, "__module__", "") == "servidor.manejadores"
    ]
    assert len(propios) >= 4

    assert corrutinas_registradas(aplicacion) == []


PLAZO_DE_ARRANQUE = 30.0  # segundos: espera de un proceso externo, no sincronización entre tests


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


def test_tkt005_ca12_comando_de_desarrollo_arranca() -> None:
    """TC-79 · CA-12 esc. 2 — `fastapi dev` desde backend/ queda escuchando y publica /openapi.json."""
    puerto = puerto_libre()
    entorno = {**ENTORNO, "COLUMNS": "250"}
    # `--no-reload` (asumido): el recargador crea procesos hijos que en Windows no se terminan
    # con el padre. La salida va a un archivo temporal: una tubería sin lector se llenaría.
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

    assert respuesta is not None, (
        f"fastapi dev no respondió 200 en /openapi.json "
        f"(terminó antes de tiempo: {codigo_de_salida is not None}, código {codigo_de_salida}).\n"
        f"--- salida del subproceso ---\n{registro}"
    )
    contrato = respuesta.json()
    assert contrato["openapi"].startswith("3.")
    assert "paths" in contrato


def test_tkt005_ca14_uvicorn_real_no_imprime_el_secreto_de_una_excepcion() -> None:
    """CA-14 · CA-11 esc. 2 · seguridad F002 — con uvicorn real, un 500 no deja el valor sensible en stdout ni en stderr.

    Con `add_exception_handler(Exception, ...)` Starlette responde y vuelve a lanzar: uvicorn imprime
    `ERROR: Exception in ASGI application` con el texto de la excepción, en texto plano, fuera de
    structlog y sin `correlacion_id`. El `TestClient` no lo ve porque no es un servidor ASGI.
    La aplicación de la prueba (`aplicacion_con_secreto`) lanza `ValueError("contrasena=...")`.
    """
    secreto = "S3cr3t" + "!"
    puerto = puerto_libre()
    entorno = {**ENTORNO, "SECRETO_DE_PRUEBA": secreto, "PYTHONUNBUFFERED": "1"}
    comando = [
        sys.executable,
        "-m",
        "uvicorn",
        "--app-dir",
        str(TESTS),
        "aplicacion_con_secreto:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(puerto),
    ]
    with tempfile.TemporaryFile() as salida, tempfile.TemporaryFile() as errores:
        proceso = subprocess.Popen(
            comando,
            cwd=BACKEND,
            env=entorno,
            stdin=subprocess.DEVNULL,
            stdout=salida,
            stderr=errores,
        )
        try:
            listo = esperar_openapi(proceso, puerto)
            respuesta = None
            if listo is not None:
                respuesta = httpx.post(f"http://127.0.0.1:{puerto}/prueba/falla", timeout=10)
                # Barrera sin `sleep`: el servidor atiende en un solo bucle, así que cuando esta
                # segunda petición responde, el registro de la primera ya se escribió.
                httpx.get(f"http://127.0.0.1:{puerto}/openapi.json", timeout=10)
        finally:
            terminar(proceso)
        salida.seek(0)
        errores.seek(0)
        stdout = salida.read().decode("utf-8", errors="replace")
        stderr = errores.read().decode("utf-8", errors="replace")

    assert listo is not None and respuesta is not None, (
        f"uvicorn no respondió 200 en /openapi.json.\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    )
    # El 500 sigue siendo el mínimo y no lleva el valor.
    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "correlacion_id"}
    assert respuesta.headers["X-Correlacion-Id"] == cuerpo["correlacion_id"]
    assert secreto not in respuesta.text
    # F002: la salida de uvicorn, fuera de structlog.
    assert secreto not in stderr, f"El valor sensible llegó a stderr:\n{stderr}"
    # F001 de extremo a extremo: ni siquiera el registro estructurado de la aplicación lo lleva.
    assert secreto not in stdout, f"El valor sensible llegó a stdout:\n{stdout}"
    # Anti-verde vacío: el fallo sí se registró, con la correlación de la respuesta.
    eventos = [json.loads(x) for x in stdout.splitlines() if x.startswith("{")]
    fallidas = [e for e in eventos if e.get("event") == "peticion_fallida"]
    assert [e["correlacion_id"] for e in fallidas] == [cuerpo["correlacion_id"]]
