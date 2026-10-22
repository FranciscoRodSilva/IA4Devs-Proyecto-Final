"""Token CSRF por HTTP (TKT-006, fila 7, tanda 1): `GET /api/v1/sesion/csrf`, con Docker.

Cubre `CA-1` (TC-50 y TC-51 del diseño): el token se emite sin sesión, la cookie `cimenta_csrf` es
legible desde JavaScript (sin `HttpOnly`) y el cuerpo lleva el mismo valor; dos emisiones nunca
comparten token. Solo la **emisión**: verificar el token en `iniciar_sesion` y `cerrar_sesion` es de
TKT-057 y aquí esas rutas no lo exigen.

La aplicación es la de la *fixture* `cliente` (`crear_aplicacion` con el motor del rol de aplicación, el
reloj de prueba y costes baratos de Argon2) sobre `https://testserver`: con `http://`, `httpx` no
devolvería una cookie `Secure`. Cada respuesta se valida contra `TokenCsrf` del borrador OpenAPI.

Rojo esperado: `crear_aplicacion` aún no acepta `motor`, `reloj` ni `entorno`, así que la *fixture*
`aplicacion_identidad` falla con `TypeError` al construirse. Con la firma pedida y sin la ruta, la
respuesta sería `404 NO_ENCONTRADO`.
"""

from __future__ import annotations

import functools
import re
import uuid
from collections.abc import Callable
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_CSRF = "/api/v1/sesion/csrf"
COOKIE_CSRF = "cimenta_csrf"
COOKIE_SESION = "cimenta_sesion"
TOKEN_URL_SEGURO = re.compile(r"[A-Za-z0-9_-]+")

Conexion = psycopg.Connection[tuple[Any, ...]]
Respuesta = Any


# --------------------------------------------------------------------------- ayudas de la prueba


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def cookies_fijadas(respuesta: Respuesta) -> list[tuple[str, Morsel[str]]]:
    """Cada `Set-Cookie` de la respuesta, interpretado con la biblioteca estándar."""
    resultado: list[tuple[str, Morsel[str]]] = []
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        resultado.extend(galleta.items())
    return resultado


def una_cookie(respuesta: Respuesta, nombre: str) -> Morsel[str]:
    """La única cookie con ese nombre que fija la respuesta; dos o ninguna es un fallo."""
    encontradas = [morsel for clave, morsel in cookies_fijadas(respuesta) if clave == nombre]
    assert len(encontradas) == 1, (
        f"Se esperaba exactamente un Set-Cookie de {nombre}; hay {len(encontradas)}: "
        f"{respuesta.headers.get_list('set-cookie')}"
    )
    return encontradas[0]


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


# --------------------------------------------------------------------------- TC-50


def test_tkt006_ca01_token_csrf_sin_sesion(cliente: TestClient) -> None:
    """TC-50 · CA-1 esc. 1 · M1 — 200 con `TokenCsrf`, cookie `cimenta_csrf` igual al cuerpo y sin `HttpOnly`.

    La petición no lleva ninguna cookie. La cookie lleva `Secure`, `SameSite=Lax` y `Path=/`; no lleva
    `HttpOnly` porque el cliente la lee para reenviarla en `X-CSRF-Token` (doble envío). El cuerpo tiene
    exactamente la clave `token`, de al menos 32 caracteres y alfabeto seguro para una URL.
    """
    assert len(cliente.cookies) == 0

    respuesta = cliente.get(RUTA_CSRF)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"token"}
    validar_contra("TokenCsrf", cuerpo)
    token = cuerpo["token"]
    assert len(token) >= 32
    assert TOKEN_URL_SEGURO.fullmatch(token)
    cookie = una_cookie(respuesta, COOKIE_CSRF)
    assert cookie.value == token
    assert cookie["secure"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"
    assert not cookie["httponly"]


def test_tkt006_ca01_el_token_lleva_correlacion_y_no_abre_sesion(cliente: TestClient) -> None:
    """TC-50 · CA-1 esc. 1 — la respuesta lleva `X-Correlacion-Id` y no fija ninguna cookie de sesión.

    Emitir el token no es iniciar sesión: la única cookie que fija es la del token.
    """
    respuesta = cliente.get(RUTA_CSRF)

    assert respuesta.status_code == 200
    assert uuid.UUID(respuesta.headers[CABECERA]).version == 4
    nombres = [clave for clave, _ in cookies_fijadas(respuesta)]
    assert nombres == [COOKIE_CSRF]
    assert COOKIE_SESION not in cliente.cookies


def test_tkt006_ca01_emitir_el_token_no_escribe_en_la_base(
    cliente: TestClient, lector: Callable[[], Conexion]
) -> None:
    """CA-1 · M1 — el token no tiene estado en el servidor: ninguna fila en `sesion`, `intento_acceso` ni `bitacora`."""
    cliente.get(RUTA_CSRF)
    cliente.get(RUTA_CSRF)

    lectura = lector()
    assert contar(lectura, "sesion") == 0
    assert contar(lectura, "intento_acceso") == 0
    assert contar(lectura, "bitacora") == 0


# --------------------------------------------------------------------------- TC-51


def test_tkt006_ca01_dos_emisiones_consecutivas_dan_tokens_distintos(cliente: TestClient) -> None:
    """TC-51 · CA-1 esc. 2 — rechazo: dos peticiones seguidas no comparten token, ni en el cuerpo ni en la cookie.

    La segunda petición ya lleva la cookie de la primera: aun así el servidor emite uno nuevo.
    """
    primera = cliente.get(RUTA_CSRF)
    segunda = cliente.get(RUTA_CSRF)

    token_1 = primera.json()["token"]
    token_2 = segunda.json()["token"]
    assert token_1 != token_2
    assert una_cookie(primera, COOKIE_CSRF).value == token_1
    assert una_cookie(segunda, COOKIE_CSRF).value == token_2
    assert primera.headers[CABECERA] != segunda.headers[CABECERA]


def test_tkt006_ca01_cien_emisiones_no_repiten_ningun_token(cliente: TestClient) -> None:
    """TC-51 · CA-1 esc. 2 — rechazo: en una muestra de cien emisiones no hay un solo token repetido.

    Cada uno, además, cumple el mínimo del esquema y coincide con su propia cookie.
    """
    tokens: list[str] = []
    for _ in range(100):
        respuesta = cliente.get(RUTA_CSRF)
        assert respuesta.status_code == 200
        token = respuesta.json()["token"]
        assert len(token) >= 32
        assert una_cookie(respuesta, COOKIE_CSRF).value == token
        tokens.append(token)

    assert len(set(tokens)) == 100
