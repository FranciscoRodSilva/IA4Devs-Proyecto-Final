"""Correlación y registro técnico de la aplicación (TKT-005, fila 5): TC-70 a TC-74.

Sin Docker (CA-R4): ninguna prueba pide `contenedor_postgres` ni nada que dependa de él. `servidor`
se importa dentro de cada prueba, con `importlib`, no al principio del archivo: mientras el paquete
no exista cada prueba falla con su propio `ModuleNotFoundError` y no con un error de colección.

La aplicación de cada prueba sale de `crear_aplicacion(destino_registro=io.StringIO())`, así que
las líneas del registro técnico se leen tal como las escribiría `structlog`. Las rutas de prueba
son `def` y viven en un `APIRouter` de la suite, no del producto. Todo `TestClient` se crea con
`raise_server_exceptions=False`.

Esta fila no registra todavía los manejadores de error (fila 6): ninguna prueba de este archivo
depende de la forma del cuerpo de un `422`, solo de su estado y del registro.
"""

import asyncio
import importlib
import io
import json
import uuid
from collections.abc import MutableMapping
from datetime import datetime
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

CABECERA = "X-Correlacion-Id"
CLIENTE_VALOR = b"valor-arbitrario\nlinea-inyectada"


class CuerpoConNombre(BaseModel):
    nombre: str


def ruta_ok() -> dict[str, bool]:
    return {"ok": True}


def ruta_exige_nombre(cuerpo: CuerpoConNombre) -> dict[str, str]:
    return {"nombre": cuerpo.nombre}


def aplicacion_de_prueba() -> tuple[FastAPI, io.StringIO]:
    """Aplicación de la fábrica con sus rutas de prueba y el registro capturado."""
    fabrica = importlib.import_module("servidor.fabrica")
    registro = io.StringIO()
    aplicacion: FastAPI = fabrica.crear_aplicacion(destino_registro=registro)
    router = APIRouter(prefix="/prueba")
    router.add_api_route("/ok", ruta_ok, methods=["GET", "POST"])
    router.add_api_route("/exige-nombre", ruta_exige_nombre, methods=["POST"])
    aplicacion.include_router(router)
    return aplicacion, registro


def es_uuid4(valor: str) -> bool:
    """UUID v4 en su forma canónica: minúsculas, con guiones, nada antes ni después."""
    try:
        return uuid.UUID(valor).version == 4 and str(uuid.UUID(valor)) == valor
    except ValueError:
        return False


def lineas_json(registro: io.StringIO) -> list[dict[str, Any]]:
    """Cada línea no vacía del registro, como JSON. Una que no lo sea falla la prueba."""
    lineas = [linea for linea in registro.getvalue().splitlines() if linea.strip()]
    return [json.loads(linea) for linea in lineas]


def llamar_asgi(
    aplicacion: FastAPI, ruta: str, cabeceras: list[tuple[bytes, bytes]]
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """GET por el protocolo ASGI, sin cliente HTTP: este no deja pasar un salto de línea en una cabecera."""
    mensajes: list[dict[str, Any]] = []

    async def recibir() -> MutableMapping[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def enviar(mensaje: MutableMapping[str, Any]) -> None:
        mensajes.append(dict(mensaje))

    alcance: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": ruta,
        "raw_path": ruta.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": cabeceras,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    asyncio.run(aplicacion(alcance, recibir, enviar))
    inicio = next(m for m in mensajes if m["type"] == "http.response.start")
    cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
    return inicio["status"], list(inicio["headers"]), cuerpo


def test_tkt005_ca10_respuesta_exitosa_lleva_cabecera() -> None:
    """TC-70 · CA-10 esc. 1 — una respuesta 200 lleva X-Correlacion-Id con un UUID v4."""
    aplicacion, _ = aplicacion_de_prueba()
    cliente = TestClient(aplicacion, raise_server_exceptions=False)

    respuesta = cliente.get("/prueba/ok")

    assert respuesta.status_code == 200
    assert CABECERA in respuesta.headers
    assert es_uuid4(respuesta.headers[CABECERA])


def test_tkt005_ca10_dos_peticiones_dos_identificadores() -> None:
    """TC-71 · CA-10 esc. 3 — dos peticiones consecutivas reciben identificadores distintos."""
    aplicacion, _ = aplicacion_de_prueba()
    cliente = TestClient(aplicacion, raise_server_exceptions=False)

    primera = cliente.get("/prueba/ok")
    segunda = cliente.get("/prueba/ok")

    assert es_uuid4(primera.headers[CABECERA])
    assert es_uuid4(segunda.headers[CABECERA])
    assert primera.headers[CABECERA] != segunda.headers[CABECERA]


def test_tkt005_ca10_cabecera_del_cliente_se_descarta() -> None:
    """TC-72 · CA-10 esc. 4 · PA-T7 — el identificador que envía el cliente no se acepta ni se refleja."""
    aplicacion, registro = aplicacion_de_prueba()

    estado, cabeceras, cuerpo = llamar_asgi(
        aplicacion, "/prueba/ok", [(b"x-correlacion-id", CLIENTE_VALOR)]
    )

    assert estado == 200
    identificadores = [v for k, v in cabeceras if k.lower() == b"x-correlacion-id"]
    assert len(identificadores) == 1
    assert es_uuid4(identificadores[0].decode("ascii"))
    for fragmento in ("valor-arbitrario", "linea-inyectada"):
        assert fragmento.encode() not in cuerpo
        assert all(fragmento.encode() not in valor for _, valor in cabeceras)
        assert fragmento not in registro.getvalue()
    # El registro sí existe y lleva el identificador generado por el servidor, no el del cliente.
    lineas = lineas_json(registro)
    assert [linea["correlacion_id"] for linea in lineas] == [identificadores[0].decode("ascii")]


def test_tkt005_ca11_registro_sin_secretos() -> None:
    """TC-73 · CA-11 esc. 2 — ni cuerpo, ni cookie, ni Authorization llegan al registro técnico."""
    aplicacion, registro = aplicacion_de_prueba()
    cliente = TestClient(aplicacion, raise_server_exceptions=False)
    secretos = ("secreta-123", "cookie-secreta-xyz", "token-secreto-abc")
    cabeceras = {
        "Cookie": "cimenta_sesion=cookie-secreta-xyz",
        "Authorization": "Bearer token-secreto-abc",
    }
    cuerpo = {"contrasena": "secreta-123"}

    con_exito = cliente.post("/prueba/ok", json=cuerpo, headers=cabeceras)
    rechazada = cliente.post("/prueba/exige-nombre", json=cuerpo, headers=cabeceras)

    assert con_exito.status_code == 200
    assert rechazada.status_code == 422
    lineas = lineas_json(registro)
    assert [linea["estado"] for linea in lineas] == [200, 422]
    for secreto in secretos:
        assert secreto not in registro.getvalue()


def test_tkt005_ca11_linea_json_con_correlacion() -> None:
    """TC-74 · CA-11 esc. 1 — cada petición deja una línea JSON con su correlación y sin la consulta."""
    aplicacion, registro = aplicacion_de_prueba()
    cliente = TestClient(aplicacion, raise_server_exceptions=False)

    respuesta = cliente.get("/prueba/ok?token=abc")

    lineas = [x for x in lineas_json(registro) if x["event"] == "peticion_atendida"]
    assert len(lineas) == 1
    linea = lineas[0]
    assert linea["metodo"] == "GET"
    assert linea["ruta"] == "/prueba/ok"
    assert linea["estado"] == 200
    assert isinstance(linea["duracion_ms"], int)
    assert linea["duracion_ms"] >= 0
    assert linea["level"] == "info"
    assert isinstance(linea["timestamp"], str)
    datetime.fromisoformat(linea["timestamp"])
    assert linea["correlacion_id"] == respuesta.headers[CABECERA]
    # «token» no puede salir por azar de un UUID hexadecimal; «abc» sí, y haría la prueba inestable.
    assert "token" not in registro.getvalue()
