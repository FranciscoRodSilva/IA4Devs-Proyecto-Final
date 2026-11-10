"""Verificación del token CSRF por doble envío (TKT-057, fila 7): `par_csrf_valido` y `verificar_origen`.

Cubre TC-38 a TC-41 y TC-47 del diseño (`CA-9`, `CA-10`, `CA-11`, `CA-R2`, `CA-R6`) sobre
`POST /api/v1/sesion/cierre`, con Docker salvo TC-47. Los casos de `POST /api/v1/sesion` (TC-42 a TC-44 y
TC-49, `CA-5` esc. 2, `CA-9`, `CA-11` esc. 3, `CA-R2`, `CA-R7`, `CA-R8`) son de la fila 8 y están al final
del archivo; la rotación del token (TC-45 y TC-46, `CA-12`, fila 9) está después de ellos y el recorrido
del enrutador (TC-48, `CA-18`, `CA-R5`, `CA-R6`, fila 10) está al final.

Un rechazo por origen comprueba el contrato de error completo: `403`, `tipo` `PERMISO`, `motivo`
`ORIGEN_NO_VERIFICADO`, el `mensaje` literal del diseño, `roles_requeridos` vacío, las claves exactas de
`ErrorPermiso` del borrador, `correlacion_id` igual a `X-Correlacion-Id` y ninguna cifra ni el valor del
token en el cuerpo. Las peticiones llevan siempre una cabecera `Cookie` explícita (la cookie de sesión y,
si el caso lo pide, la `cimenta_csrf`): así la prueba controla cada combinación sin depender del almacén
de cookies del cliente ni de que el servidor rote el token en el inicio de sesión (fila 9).

Rojo esperado en esta fila, y por qué:

* TC-38, TC-41 y el caso de la cabecera no ASCII: `cerrar_sesion` aún no exige el par, así que responde
  `204` donde se espera `403`; la aserción de código falla.
* El caso de TC-41 con transacción propia y todo TC-47: `verificar_origen` y `par_csrf_valido` no existen
  todavía (`ImportError` dentro del cuerpo del caso, que no tumba la recolección).

Nacen en verde, a propósito:

* TC-40, porque el `401` sin sesión ya existe desde TKT-006: fija el orden «la sesión se evalúa antes que
  el token», que la implementación nueva no puede invertir. Un `verificar_origen` que mirara el token
  primero respondería `403` aquí y lo pondría en rojo.
* TC-39, porque hoy el cierre ignora el token y con un par válido ya responde `204`: es la regresión del
  camino feliz, que debe seguir verde cuando se exija el par.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
import io
import json
import re
import secrets
import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import timedelta
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import Annotated, Any, cast

import psycopg
import pytest
import yaml
from fastapi import APIRouter, Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.routing import BaseRoute

from cimenta.identidad.api.dependencias import (
    credenciales_con_origen_verificado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.identidad.api.esquemas import CredencialesInicio
from contrato_error import PermisoDenegado

RAIZ = Path(__file__).resolve().parents[2]
CABECERA_CORRELACION = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
RUTA_CIERRE = "/api/v1/sesion/cierre"
RUTA_TOKEN = "/api/v1/sesion/csrf"
RUTA_CON_TRANSACCION = "/api/v1/prueba/origen-con-transaccion"
COOKIE_SESION = "cimenta_sesion"
COOKIE_CSRF = "cimenta_csrf"
CABECERA_CSRF = "X-CSRF-Token"
CORREO_DE_ANA = "ana@cimenta.test"
CONTRASENA_DE_ANA = "Clave-Correcta-1"
ROLES_DE_ANA = ("RESIDENTE", "COMPRAS")
CORREO_DE_LA_PETICION = "transaccion-de-la-peticion@cimenta.test"
TOKEN_DE_COOKIE = "csrf-cookie-0f3a9c71"
TOKEN_DE_CABECERA = "csrf-cabecera-7b21d4e8"
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
CLAVES_DE_ERROR_DE_SESION = {"tipo", "motivo", "mensaje", "correlacion_id"}
CLAVES_DE_DATOS_DE_LA_DENEGACION = {"metodo", "ruta", "roles_requeridos"}
COLUMNAS_DEL_ASIENTO = (
    "id",
    "accion",
    "usuario_id",
    "ocurrido_en",
    "motivo",
    "regla_negocio",
    "entidad_tipo",
    "entidad_id",
    "obra_id",
    "datos_antes_es_nulo",
    "datos_despues",
)
# Las cuatro combinaciones de CA-9: (identificador, valor de la cookie, valor de la cabecera).
COMBINACIONES_DE_CA9 = [
    pytest.param(None, None, id="ambos_ausentes"),
    pytest.param(TOKEN_DE_COOKIE, None, id="solo_cookie"),
    pytest.param(None, TOKEN_DE_CABECERA, id="solo_cabecera"),
    pytest.param(TOKEN_DE_COOKIE, TOKEN_DE_CABECERA, id="distintos"),
]

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


def cabeceras_de(
    sesion_id: object | None, cookie_csrf: str | None, cabecera_csrf: str | None
) -> dict[str, str]:
    """La cabecera `Cookie` (sesión y, si se pide, `cimenta_csrf`) y, si se pide, `X-CSRF-Token`."""
    cookies = []
    if sesion_id is not None:
        cookies.append(f"{COOKIE_SESION}={sesion_id}")
    if cookie_csrf is not None:
        cookies.append(f"{COOKIE_CSRF}={cookie_csrf}")
    cabeceras: dict[str, str] = {}
    if cookies:
        cabeceras["Cookie"] = "; ".join(cookies)
    if cabecera_csrf is not None:
        cabeceras[CABECERA_CSRF] = cabecera_csrf
    return cabeceras


def id_de_sesion(respuesta: Respuesta) -> uuid.UUID:
    """El valor de `cimenta_sesion` entre los `Set-Cookie` de la respuesta (puede haber más de uno)."""
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        if COOKIE_SESION in galleta:
            return uuid.UUID(galleta[COOKIE_SESION].value)
    pytest.fail(f"La respuesta no fija {COOKIE_SESION}: {respuesta.headers.get_list('set-cookie')}")


def iniciar_sesion_de_ana(cliente: TestClient) -> uuid.UUID:
    """Inicia sesión por HTTP con un par CSRF coincidente y vacía el almacén de cookies del cliente.

    `POST /sesion` exige el par desde la fila 8, y la cabecera `Cookie` es explícita para no depender del
    almacén de cookies del cliente.
    """
    token = "csrf-del-inicio-5d2e8a90"
    respuesta = cliente.post(
        RUTA_SESION,
        json={"email": CORREO_DE_ANA, "contrasena": CONTRASENA_DE_ANA},
        headers=cabeceras_de(None, token, token),
    )
    assert respuesta.status_code == 200, respuesta.text
    sesion_id = id_de_sesion(respuesta)
    cliente.cookies.clear()
    return sesion_id


def exigir_origen_no_verificado(respuesta: Respuesta, *textos_ausentes: str) -> None:
    """El contrato de error completo de un `403 PERMISO ORIGEN_NO_VERIFICADO` (CA-9, CA-11, CA-R2)."""
    assert respuesta.status_code == 403, respuesta.text
    cuerpo = respuesta.json()
    esquema = borrador()["components"]["schemas"]["ErrorPermiso"]
    assert "detail" not in cuerpo
    assert "detalle" not in cuerpo
    assert set(cuerpo) == set(esquema["properties"]) == set(esquema["required"])
    assert cuerpo["tipo"] == "PERMISO"
    assert cuerpo["motivo"] == "ORIGEN_NO_VERIFICADO"
    assert cuerpo["mensaje"] == MENSAJE_ORIGEN_NO_VERIFICADO
    assert cuerpo["roles_requeridos"] == []
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    validar_contra("ErrorPermiso", cuerpo)
    for ausente in textos_ausentes:
        assert ausente not in respuesta.text


def exigir_error_de_sesion_ausente(respuesta: Respuesta) -> None:
    """El contrato de error completo de `401 SESION SIN_SESION` (CA-11 esc. 1)."""
    assert respuesta.status_code == 401, respuesta.text
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == "SIN_SESION"
    assert cuerpo["mensaje"] == "No hay una sesión iniciada."
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    validar_contra("ErrorSesion", cuerpo)


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


def revocada_en(conexion: Conexion, sesion_id: uuid.UUID) -> object:
    fila = conexion.execute("SELECT revocada_en FROM sesion WHERE id = %s", (sesion_id,)).fetchone()
    assert fila is not None, f"No existe la fila de sesion {sesion_id}."
    return fila[0]


def asientos(conexion: Conexion) -> list[dict[str, Any]]:
    """Todos los asientos de la bitácora por nombre de columna. `datos_antes` solo dice si es NULL de SQL."""
    filas = conexion.execute(
        "SELECT id, accion::text, usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, "
        "entidad_id, obra_id, datos_antes IS NULL, datos_despues FROM bitacora ORDER BY ocurrido_en, id"
    ).fetchall()
    return [dict(zip(COLUMNAS_DEL_ASIENTO, fila, strict=True)) for fila in filas]


def existe_usuario(conexion: Conexion, correo: str) -> bool:
    fila = conexion.execute("SELECT count(*) FROM usuario WHERE email = %s", (correo,)).fetchone()
    assert fila is not None
    return int(fila[0]) == 1


def agregar_ruta_que_muta_con_transaccion_propia(
    aplicacion: FastAPI, motor: Engine
) -> tuple[list[str], list[str]]:
    """`POST /api/v1/prueba/origen-con-transaccion`: la petición abre una transacción y la deshace.

    La primera dependencia abre una `Session`, escribe un usuario y, al terminar la petición, hace
    `rollback`. La segunda es `verificar_origen`, tomada de `cimenta.identidad.interfaz`, que lanza el
    `403`. Devuelve las escrituras de la petición y las veces que se ejecutó el cuerpo de la ruta.
    """
    from cimenta.identidad.interfaz import verificar_origen

    escritas: list[str] = []
    ejecutadas: list[str] = []

    def transaccion_de_la_peticion() -> Iterator[Session]:
        with Session(motor) as sesion:
            sesion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
                    "VALUES (:id, 'De la petición', :email, 'sin-hash', true)"
                ),
                {"id": uuid.uuid4(), "email": CORREO_DE_LA_PETICION},
            )
            escritas.append(CORREO_DE_LA_PETICION)
            try:
                yield sesion
            finally:
                sesion.rollback()

    def atender() -> dict[str, bool]:
        ejecutadas.append(f"POST {RUTA_CON_TRANSACCION}")
        return {"ok": True}

    enrutador = APIRouter()
    enrutador.add_api_route(
        RUTA_CON_TRANSACCION,
        atender,
        methods=["POST"],
        dependencies=[Depends(transaccion_de_la_peticion), Depends(verificar_origen)],
    )
    aplicacion.include_router(enrutador)
    return escritas, ejecutadas


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


# --------------------------------------------------------------------------- TC-38


@pytest.mark.parametrize(("cookie", "cabecera"), COMBINACIONES_DE_CA9)
def test_tkt057_ca09_cierre_sin_par_valido_es_403_origen_no_verificado(
    cookie: str | None,
    cabecera: str | None,
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-38 · CA-9 · RNF-05 — rechazo: con sesión y sin par de token válido, `403 PERMISO ORIGEN_NO_VERIFICADO`.

    Las cuatro combinaciones del escenario: cookie y cabecera ausentes, solo la cookie, solo la cabecera
    y valores distintos. El contrato de error es completo (código, `tipo`, `motivo`, `mensaje` literal,
    `roles_requeridos` vacío, claves exactas de `ErrorPermiso`, `correlacion_id`) y el cuerpo no repite
    el valor de ninguno de los dos tokens. La operación no se ejecutó: la sesión sigue sin `revocada_en`
    y la respuesta no expira `cimenta_sesion`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, cookie, cabecera))

    exigir_origen_no_verificado(respuesta, TOKEN_DE_COOKIE, TOKEN_DE_CABECERA)
    assert COOKIE_SESION not in "; ".join(respuesta.headers.get_list("set-cookie"))
    assert revocada_en(lector(), sesion_id) is None


def test_tkt057_ca09_cierre_con_cabecera_no_ascii_es_403_y_no_500(
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-38 · TC-47 · CA-9 · M4 — rechazo: una cabecera con caracteres no ASCII es `403`, nunca `500`.

    `secrets.compare_digest` con cadenas no ASCII lanza `TypeError`, y eso sería un `500` que filtra el
    fallo; el diseño compara en bytes UTF-8. La cabecera viaja como bytes UTF-8 de «ñandú»: Starlette la
    entrega decodificada y no coincide con la cookie.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)
    cabeceras = [
        (b"Cookie", f"{COOKIE_SESION}={sesion_id}; {COOKIE_CSRF}=aaa".encode()),
        (CABECERA_CSRF.encode(), "ñandú".encode()),
    ]

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras)

    exigir_origen_no_verificado(respuesta)
    assert revocada_en(lector(), sesion_id) is None


# --------------------------------------------------------------------------- TC-39


def test_tkt057_ca10_cierre_con_par_valido_se_ejecuta(
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-39 · CA-10 · RNF-05 — con la cookie y la cabecera iguales, `204` y `sesion.revocada_en` escrito.

    El token sale de `GET /api/v1/sesion/csrf`, como en el escenario. Nace en verde: hoy el cierre
    ignora el token. Es la regresión del camino feliz que debe seguir en verde cuando se exija el par.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)
    token = cliente.get(RUTA_TOKEN).json()["token"]
    cliente.cookies.clear()
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, token, token))

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert revocada_en(lector(), sesion_id) == reloj_de_prueba.ahora


# --------------------------------------------------------------------------- TC-40


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt057_ca11_esc1_sin_sesion_ni_token_es_401_y_la_bitacora_sigue_vacia(
    sesion: str,
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-40 · CA-11 esc. 1 · CA-R2 · RNF-13 — rechazo: sin sesión ni token, `401 SESION`, nunca `403`.

    Sin cookie de sesión y con una cookie que no corresponde a ninguna fila: la sesión se evalúa antes
    que el token. La bitácora no recibe ningún asiento (un rechazo anónimo no es un `DENEGAR`, invariante
    10). Nace en verde a propósito: el `401` sin sesión ya existe desde TKT-006 y este caso fija el
    orden, de modo que un `verificar_origen` que mirara el token primero lo pondría en rojo.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    iniciar_sesion_de_ana(cliente)
    desconocida = uuid.uuid4() if sesion == "sesion_inexistente" else None

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(desconocida, None, None))

    exigir_error_de_sesion_ausente(respuesta)
    assert contar(lector(), "bitacora") == 0


# --------------------------------------------------------------------------- TC-41


@pytest.mark.parametrize(
    ("cookie", "cabecera"),
    [
        pytest.param(None, None, id="ambos_ausentes"),
        pytest.param(TOKEN_DE_COOKIE, None, id="solo_cookie"),
        pytest.param(TOKEN_DE_COOKIE, TOKEN_DE_CABECERA, id="distintos"),
    ],
)
def test_tkt057_ca11_esc2_el_rechazo_con_sesion_se_asienta_como_denegar_de_ana(
    cookie: str | None,
    cabecera: str | None,
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-41 · CA-11 esc. 2 · RN-04 — rechazo: el `403` con sesión deja un `DENEGAR` a nombre de Ana.

    Hay **una** fila: acción `DENEGAR`, `usuario_id` y `entidad_id` de Ana, el momento del reloj, `motivo`
    `ORIGEN_NO_VERIFICADO`, sin `regla_negocio`, sin obra y `datos_antes` NULL de SQL; `datos_despues`
    tiene exactamente `{metodo, ruta, roles_requeridos}` con la lista vacía. Ninguna columna contiene el
    valor de los tokens enviados ni el identificador de la sesión (credencial de la cookie).
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, cookie, cabecera))

    exigir_origen_no_verificado(respuesta)
    (fila,) = asientos(lector())
    assert fila["accion"] == "DENEGAR"
    assert fila["usuario_id"] == ana
    assert fila["ocurrido_en"] == reloj_de_prueba.ahora
    assert fila["motivo"] == "ORIGEN_NO_VERIFICADO"
    assert fila["regla_negocio"] is None
    assert fila["entidad_tipo"] == "usuario"
    assert fila["entidad_id"] == ana
    assert fila["obra_id"] is None
    assert fila["datos_antes_es_nulo"] is True
    assert set(fila["datos_despues"]) == CLAVES_DE_DATOS_DE_LA_DENEGACION
    assert fila["datos_despues"] == {"metodo": "POST", "ruta": RUTA_CIERRE, "roles_requeridos": []}
    texto = json.dumps(fila, default=str, ensure_ascii=False)
    for secreto in (TOKEN_DE_COOKIE, TOKEN_DE_CABECERA, str(sesion_id)):
        assert secreto not in texto
    assert respuesta.headers[CABECERA_CORRELACION] not in texto


def test_tkt057_ca11_esc2_el_denegar_persiste_aunque_la_peticion_deshaga_la_suya(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-41 · CA-11 esc. 2 — la petición escribe un usuario, el `403` salta y deshace; el asiento sigue.

    La ruta de la suite es un `POST` que declara, antes de `verificar_origen` (tomado de
    `cimenta.identidad.interfaz`), una dependencia que abre una transacción, escribe y la deshace al
    terminar. Tras el `403`: el asiento `DENEGAR` con `ORIGEN_NO_VERIFICADO` persiste, el usuario de la
    petición no existe y el cuerpo de la ruta no se ejecutó. El asiento se escribe en una transacción
    propia, no en la de la petición.
    """
    escritas, ejecutadas = agregar_ruta_que_muta_con_transaccion_propia(
        aplicacion_identidad, motor_aplicacion
    )
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)

    respuesta = cliente.post(RUTA_CON_TRANSACCION, headers=cabeceras_de(sesion_id, None, None))

    exigir_origen_no_verificado(respuesta)
    assert escritas == [CORREO_DE_LA_PETICION]
    assert ejecutadas == []
    conexion = lector()
    filas = asientos(conexion)
    assert [(fila["accion"], fila["motivo"], fila["usuario_id"]) for fila in filas] == [
        ("DENEGAR", "ORIGEN_NO_VERIFICADO", ana)
    ]
    assert existe_usuario(conexion, CORREO_DE_LA_PETICION) is False


# --------------------------------------------------------------------------- TC-47


@pytest.mark.parametrize(
    ("cookie", "cabecera"),
    [
        pytest.param(None, None, id="ambos_none"),
        pytest.param(None, "abc", id="cookie_none"),
        pytest.param("abc", None, id="cabecera_none"),
        pytest.param("", "", id="ambos_vacios"),
        pytest.param("", "abc", id="cookie_vacia"),
        pytest.param("abc", "", id="cabecera_vacia"),
        pytest.param("aaa", "bbb", id="distintos"),
        pytest.param("abc", "abcd", id="prefijo"),
        pytest.param("abc", "ABC", id="distinta_capitalizacion"),
        pytest.param("ñandú", "nandu", id="no_ascii_distintos"),
    ],
)
def test_tkt057_m4_par_csrf_valido_rechaza_ausentes_vacios_y_distintos(
    cookie: str | None, cabecera: str | None
) -> None:
    """TC-47 · M4 · CA-9 — rechazo: `par_csrf_valido` es `False` si falta uno, si está vacío o si difieren."""
    from cimenta.identidad.api.dependencias import par_csrf_valido

    assert par_csrf_valido(cookie, cabecera) is False


@pytest.mark.parametrize(
    "token",
    ["abc", "9f2c-A_zZ09-token-urlsafe", "ñandú-üñ-日本語"],
    ids=["corto", "urlsafe", "no_ascii"],
)
def test_tkt057_m4_par_csrf_valido_acepta_dos_valores_iguales(token: str) -> None:
    """TC-47 · M4 · CA-10 — `par_csrf_valido` es `True` si cookie y cabecera son el mismo valor, incluso no ASCII."""
    from cimenta.identidad.api.dependencias import par_csrf_valido

    assert par_csrf_valido(token, token) is True


def test_tkt057_m4_par_csrf_valido_no_lanza_con_cabecera_no_ascii() -> None:
    """TC-47 · M4 — rechazo: una cabecera no ASCII frente a una cookie ASCII da `False`, no `TypeError`.

    `secrets.compare_digest` con `str` no ASCII lanza `TypeError`, y eso sería un `500` (pasada
    adversarial, riesgo 7). Se prueba en los dos sentidos.
    """
    from cimenta.identidad.api.dependencias import par_csrf_valido

    assert par_csrf_valido("abc", "ñandú") is False
    assert par_csrf_valido("ñandú", "abc") is False
    assert par_csrf_valido("ñandú", "ñandú!") is False


def test_tkt057_m4_par_csrf_valido_compara_con_compare_digest_en_bytes_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-47 · M4 — `par_csrf_valido` llama a `secrets.compare_digest` con los dos valores en bytes UTF-8.

    Un espía sobre `secrets.compare_digest` que delega en el original: se llamó una vez y con `bytes`,
    no con `str` (que con un carácter no ASCII lanzaría `TypeError`) y no con `==`, que no es de tiempo
    constante.
    """
    from cimenta.identidad.api.dependencias import par_csrf_valido

    original = secrets.compare_digest
    llamadas: list[tuple[object, object]] = []

    def espia(a: Any, b: Any) -> bool:
        llamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(secrets, "compare_digest", espia)

    assert par_csrf_valido("ñandú", "ñandú") is True

    assert llamadas == [("ñandú".encode(), "ñandú".encode())]
    assert all(isinstance(lado, bytes) for lado in llamadas[0])


# =========================================================================== Fila 8
# TC-42 a TC-44 y TC-49: `POST /api/v1/sesion` con la prueba de origen (`credenciales_con_origen_verificado`).
#
# Rojo esperado en esta fila, y por qué:
#
# * TC-42, TC-43 y el caso no ASCII: `iniciar_sesion` aún no mira el token, así que con credenciales
#   correctas y sin par válido responde `200` y abre una sesión donde se espera `403`; la aserción de
#   código falla antes de llegar a la fila de `intento_acceso`, a la línea del registro y al contador.
# * TC-49 de `POST /api/v1/sesion`: la operación aún no depende de `_esquema_csrf`, así que el borrador
#   que publica la aplicación no le declara `security`.
#
# Nacen en verde, a propósito:
#
# * TC-44: hoy el `422` tampoco asienta intento ni mira el token. Fija el orden de `D-5`: el cuerpo
#   inválido responde `422` antes que el par CSRF, sin fila en `intento_acceso`. Un
#   `credenciales_con_origen_verificado` que mirara el token antes de validar el cuerpo lo pondría en rojo.
# * CA-R7 (`401` con par válido) y CA-R8 (`200` con par válido): hoy el token se ignora. Son la
#   regresión del camino feliz y del `401`, que deben seguir en verde cuando se exija el par.
# * Del TC-49: el esquema `csrf` (lo publica `verificar_origen` desde la fila 7), el cierre que lo exige,
#   los `GET` que no y el `requestBody` sin envolver. Son regresiones de contrato (`M4`, `M8`): la fila 8
#   no puede envolver el cuerpo de `iniciar_sesion` al mover la validación a una dependencia.

RUTA_OPENAPI = "/openapi.json"
CORREO_ESCRITO_POR_ANA = "Ana@Cimenta.TEST"
ORIGEN_DE_LA_PRUEBA = "testclient"
MENSAJE_CREDENCIALES_INVALIDAS = "El correo o la contraseña no son correctos."
EVENTO_DEL_RECHAZO = "origen_no_verificado"
CLAVES_DE_ERROR_DE_VALIDACION = {"tipo", "mensaje", "errores", "correlacion_id"}
CLAVES_DE_USUARIO_ACTUAL = {"id", "nombre", "email", "roles", "sesion"}
COLUMNAS_DEL_INTENTO = (
    "email",
    "usuario_id",
    "exitoso",
    "credenciales_verificadas",
    "ocurrido_en",
    "origen_ip",
)
# Las tres combinaciones de CA-9 que no son «ambos ausentes» (esa es TC-42).
OTRAS_COMBINACIONES_DE_CA9 = COMBINACIONES_DE_CA9[1:]


class ContadorDeContrasenas:
    """Envuelve las contraseñas reales y anota cada derivación y cada verificación de hash (TC-42)."""

    def __init__(self, interior: Any) -> None:
        self._interior = interior
        self.hash_de_descarte: str = interior.hash_de_descarte
        self.verificaciones: list[tuple[str, str]] = []
        self.derivaciones: list[str] = []

    def derivar(self, contrasena: str) -> str:
        self.derivaciones.append(contrasena)
        return str(self._interior.derivar(contrasena))

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        self.verificaciones.append((contrasena, hash_guardado))
        return bool(self._interior.verificar(contrasena, hash_guardado))


def con_contador(aplicacion: FastAPI) -> ContadorDeContrasenas:
    """Coloca un contador sobre las contraseñas del contexto de la aplicación en marcha."""
    contexto = aplicacion.state.identidad
    contador = ContadorDeContrasenas(contexto.contrasenas)
    aplicacion.state.identidad = dataclasses.replace(contexto, contrasenas=contador)
    return contador


def iniciar_con(
    cliente: TestClient,
    cookie: str | None,
    cabecera: str | None,
    *,
    correo: str = CORREO_DE_ANA,
    contrasena: str = CONTRASENA_DE_ANA,
) -> Respuesta:
    """`POST /api/v1/sesion` con credenciales y la combinación de cookie y cabecera CSRF que se indica."""
    return cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers=cabeceras_de(None, cookie, cabecera),
    )


def intentos(conexion: Conexion) -> list[dict[str, Any]]:
    """Las filas de `intento_acceso` por nombre de columna, sin su `id`."""
    filas = conexion.execute(
        "SELECT email, usuario_id, exitoso, credenciales_verificadas, ocurrido_en, origen_ip "
        "FROM intento_acceso ORDER BY ocurrido_en, id"
    ).fetchall()
    return [dict(zip(COLUMNAS_DEL_INTENTO, fila, strict=True)) for fila in filas]


def lineas_json(registro: io.StringIO) -> list[dict[str, Any]]:
    """Cada línea no vacía del registro técnico, como JSON. Una que no lo sea falla la prueba."""
    lineas = [linea for linea in registro.getvalue().splitlines() if linea.strip()]
    return [json.loads(linea) for linea in lineas]


def lineas_del_rechazo(registro: io.StringIO) -> list[dict[str, Any]]:
    return [linea for linea in lineas_json(registro) if linea["event"] == EVENTO_DEL_RECHAZO]


def exigir_rechazo_anonimo_asentado(
    respuesta: Respuesta,
    *,
    lectura: Conexion,
    registro: io.StringIO,
    contador: ContadorDeContrasenas,
    ahora: object,
    textos_ausentes: tuple[str, ...],
) -> None:
    """Lo que deja el `403` anónimo de `POST /sesion`: una fila, una línea técnica y nada más (CA-11 esc. 3)."""
    assert respuesta.headers.get_list("set-cookie") == []
    (fila,) = intentos(lectura)
    assert fila == {
        "email": CORREO_DE_ANA,
        "usuario_id": None,
        "exitoso": False,
        "credenciales_verificadas": False,
        "ocurrido_en": ahora,
        "origen_ip": ORIGEN_DE_LA_PRUEBA,
    }
    assert contar(lectura, "bitacora") == 0
    assert contar(lectura, "sesion") == 0
    assert contador.verificaciones == []
    assert contador.derivaciones == []
    (linea,) = lineas_del_rechazo(registro)
    assert linea["level"] == "warning"
    assert linea["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    assert linea["metodo"] == "POST"
    assert linea["ruta"] == RUTA_SESION
    tecnico = registro.getvalue().lower()
    for ausente in (
        CORREO_DE_ANA,
        CONTRASENA_DE_ANA.lower(),
        *(t.lower() for t in textos_ausentes),
    ):
        assert ausente not in tecnico


# --------------------------------------------------------------------------- TC-42


def test_tkt057_ca11_esc3_inicio_sin_token_es_403_y_asienta_el_rechazo_anonimo(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    registro_tecnico: io.StringIO,
    reloj_de_prueba: Any,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-42 · CA-11 esc. 3 · CA-R2 · RNF-05 — rechazo: `POST /sesion` sin token es `403 ORIGEN_NO_VERIFICADO`.

    Ana existe y envía su contraseña correcta, con el correo escrito `Ana@Cimenta.TEST`. El contrato de
    error es completo (`tipo` `PERMISO`, `roles_requeridos` vacío, claves exactas de `ErrorPermiso`,
    `correlacion_id`). Deja **una** fila en `intento_acceso`, con el correo normalizado, sin usuario,
    `exitoso` y `credenciales_verificadas` falsos, el momento del reloj y el origen; **una** línea
    `origen_no_verificado` de nivel `warning` con el `correlacion_id`, el método y la ruta y sin el correo
    ni la contraseña; la `bitacora` y `sesion` vacías; y ninguna derivación ni verificación de hash. No
    fija ninguna cookie: con credenciales correctas no abre sesión.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contador = con_contador(aplicacion_identidad)
    reloj_de_prueba.avanzar(timedelta(minutes=4))

    respuesta = iniciar_con(cliente, None, None, correo=CORREO_ESCRITO_POR_ANA)

    exigir_origen_no_verificado(respuesta, CONTRASENA_DE_ANA, CORREO_DE_ANA, CORREO_ESCRITO_POR_ANA)
    exigir_rechazo_anonimo_asentado(
        respuesta,
        lectura=lector(),
        registro=registro_tecnico,
        contador=contador,
        ahora=reloj_de_prueba.ahora,
        textos_ausentes=(CORREO_ESCRITO_POR_ANA,),
    )


def test_tkt057_ca11_esc3_inicio_con_correo_inexistente_sin_token_tambien_asienta_el_intento(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    registro_tecnico: io.StringIO,
    reloj_de_prueba: Any,
    lector: Callable[[], Conexion],
) -> None:
    """TC-42 · CA-11 esc. 3 · CA-R2 — rechazo: el rechazo anónimo es igual con un correo que no existe.

    Ninguna cuenta se sembró: la respuesta, la fila y la línea técnica son las mismas que con Ana, de modo
    que el `403` no revela si la cuenta existe. Tampoco se deriva ni se verifica ningún hash.
    """
    contador = con_contador(aplicacion_identidad)

    respuesta = iniciar_con(cliente, None, None)

    exigir_origen_no_verificado(respuesta, CONTRASENA_DE_ANA, CORREO_DE_ANA)
    exigir_rechazo_anonimo_asentado(
        respuesta,
        lectura=lector(),
        registro=registro_tecnico,
        contador=contador,
        ahora=reloj_de_prueba.ahora,
        textos_ausentes=(),
    )


def test_tkt057_ca11_esc3_el_rechazo_de_origen_registra_el_metodo_y_la_ruta_que_recibe(
    aplicacion_identidad: FastAPI,
    registro_tecnico: io.StringIO,
    reloj_de_prueba: Any,
    lector: Callable[[], Conexion],
) -> None:
    """CA-11 esc. 3 · CA-R2 · auditoría de código F002 — la línea `origen_no_verificado` no fija `POST` ni la ruta de sesión.

    `registrar_rechazo_de_origen` recibe `metodo` y `ruta` de quien la llama (la dependencia pasa
    `request.method` y `request.url.path`). Llamada directamente con `PUT` y `/api/v1/otra`, la línea
    técnica lleva esos dos valores y no `POST` ni `/api/v1/sesion`; la fila anónima de
    `intento_acceso` queda igual que la de TC-42.
    """
    from cimenta.identidad.aplicacion.sesiones import registrar_rechazo_de_origen

    registrar_rechazo_de_origen(
        aplicacion_identidad.state.identidad,
        correo_escrito=CORREO_ESCRITO_POR_ANA,
        origen_ip=ORIGEN_DE_LA_PRUEBA,
        metodo="PUT",
        ruta="/api/v1/otra",
    )

    (linea,) = lineas_del_rechazo(registro_tecnico)
    assert linea["level"] == "warning"
    assert linea["metodo"] == "PUT"
    assert linea["ruta"] == "/api/v1/otra"
    assert RUTA_SESION not in registro_tecnico.getvalue()
    assert CORREO_DE_ANA not in registro_tecnico.getvalue().lower()
    (fila,) = intentos(lector())
    assert fila == {
        "email": CORREO_DE_ANA,
        "usuario_id": None,
        "exitoso": False,
        "credenciales_verificadas": False,
        "ocurrido_en": reloj_de_prueba.ahora,
        "origen_ip": ORIGEN_DE_LA_PRUEBA,
    }


def test_tkt057_car8_inicio_con_par_valido_responde_200_y_abre_la_sesion(
    cliente: TestClient,
    registro_tecnico: io.StringIO,
    reloj_de_prueba: Any,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-42 · CA-R8 · CA-10 — con cookie y cabecera iguales, `POST /sesion` sigue siendo `200` con `UsuarioActual`.

    Es la regresión del camino feliz: el cuerpo valida contra `UsuarioActual`, se fija `cimenta_sesion`,
    queda una fila de `intento_acceso` exitosa con las credenciales verificadas, existe la fila de `sesion`
    y el registro técnico no tiene ninguna línea `origen_no_verificado`. Nace en verde: hoy el token se
    ignora.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    reloj_de_prueba.avanzar(timedelta(minutes=2))

    respuesta = iniciar_con(cliente, TOKEN_DE_COOKIE, TOKEN_DE_COOKIE)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == CLAVES_DE_USUARIO_ACTUAL
    assert cuerpo["id"] == str(ana)
    assert cuerpo["email"] == CORREO_DE_ANA
    validar_contra("UsuarioActual", cuerpo)
    sesion_id = id_de_sesion(respuesta)
    lectura = lector()
    (fila,) = intentos(lectura)
    assert fila["usuario_id"] == ana
    assert fila["exitoso"] is True
    assert fila["credenciales_verificadas"] is True
    assert fila["ocurrido_en"] == reloj_de_prueba.ahora
    assert contar(lectura, "sesion") == 1
    assert revocada_en(lectura, sesion_id) is None
    assert lineas_del_rechazo(registro_tecnico) == []


def test_tkt057_car7_inicio_con_par_valido_y_contrasena_erronea_sigue_siendo_401(
    cliente: TestClient,
    registro_tecnico: io.StringIO,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-42 · CA-R7 — rechazo: con el par válido, la contraseña errónea es `401 SESION CREDENCIALES_INVALIDAS`.

    El contrato de TKT-006 no cambia: el token solo antecede a la verificación de credenciales, nunca la
    sustituye. La fila de `intento_acceso` es un fallo **con** credenciales verificadas (cuenta para el
    límite de intentos), no el rechazo anónimo del `403`. Nace en verde: hoy el token se ignora.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)

    respuesta = iniciar_con(
        cliente, TOKEN_DE_COOKIE, TOKEN_DE_COOKIE, contrasena="Clave-Equivocada-9"
    )

    assert respuesta.status_code == 401, respuesta.text
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == "CREDENCIALES_INVALIDAS"
    assert cuerpo["mensaje"] == MENSAJE_CREDENCIALES_INVALIDAS
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    validar_contra("ErrorSesion", cuerpo)
    assert respuesta.headers.get_list("set-cookie") == []
    (fila,) = intentos(lector())
    assert fila["exitoso"] is False
    assert fila["credenciales_verificadas"] is True
    assert lineas_del_rechazo(registro_tecnico) == []


# --------------------------------------------------------------------------- TC-43


@pytest.mark.parametrize(("cookie", "cabecera"), OTRAS_COMBINACIONES_DE_CA9)
def test_tkt057_ca09_inicio_sin_par_valido_es_403_origen_no_verificado(
    cookie: str | None,
    cabecera: str | None,
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    registro_tecnico: io.StringIO,
    reloj_de_prueba: Any,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-43 · CA-9 · CA-11 esc. 3 — rechazo: con cuerpo válido y sin par válido, `403` y el mismo contrato que TC-38.

    Las otras tres combinaciones de CA-9: solo la cookie, solo la cabecera y valores distintos. El contrato
    de error es completo (claves exactas de `ErrorPermiso`, `roles_requeridos` vacío, `correlacion_id`) y el
    cuerpo no repite el valor de ningún token. Cada una deja la misma fila, la misma línea técnica y la misma
    ausencia de verificación de hash que TC-42, aunque la contraseña sea correcta.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contador = con_contador(aplicacion_identidad)

    respuesta = iniciar_con(cliente, cookie, cabecera)

    exigir_origen_no_verificado(respuesta, TOKEN_DE_COOKIE, TOKEN_DE_CABECERA, CONTRASENA_DE_ANA)
    exigir_rechazo_anonimo_asentado(
        respuesta,
        lectura=lector(),
        registro=registro_tecnico,
        contador=contador,
        ahora=reloj_de_prueba.ahora,
        textos_ausentes=(TOKEN_DE_COOKIE, TOKEN_DE_CABECERA),
    )


def test_tkt057_ca09_inicio_con_cabecera_no_ascii_es_403_y_no_500(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-43 · TC-47 · CA-9 · M4 — rechazo: una cabecera con caracteres no ASCII es `403` en `POST /sesion`, nunca `500`.

    La cabecera viaja como bytes UTF-8 de «ñandú» frente a una cookie ASCII. Tampoco se verifica la contraseña
    y queda la fila del rechazo anónimo.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contador = con_contador(aplicacion_identidad)
    cabeceras = [
        (b"Cookie", f"{COOKIE_CSRF}=aaa".encode()),
        (CABECERA_CSRF.encode(), "ñandú".encode()),
    ]

    respuesta = cliente.post(
        RUTA_SESION,
        json={"email": CORREO_DE_ANA, "contrasena": CONTRASENA_DE_ANA},
        headers=cabeceras,
    )

    exigir_origen_no_verificado(respuesta, CONTRASENA_DE_ANA)
    assert [fila["exitoso"] for fila in intentos(lector())] == [False]
    assert contador.verificaciones == []


# --------------------------------------------------------------------------- TC-44


@pytest.mark.parametrize(
    ("cookie", "cabecera"),
    [
        pytest.param(None, None, id="sin_token"),
        pytest.param(TOKEN_DE_COOKIE, TOKEN_DE_CABECERA, id="par_distinto"),
    ],
)
def test_tkt057_ca05_esc2_cuerpo_sin_contrasena_es_422_antes_que_el_token(
    cookie: str | None,
    cabecera: str | None,
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    registro_tecnico: io.StringIO,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-44 · CA-5 esc. 2 · D-5 — rechazo: sin `contrasena` y sin par válido, `422 VALIDACION`, no `403`.

    El cuerpo inválido se rechaza antes de mirar el token: el contrato es `tipo` `VALIDACION` con el campo
    `contrasena` y el código `OBLIGATORIO`, sin `detail`, y no queda ninguna fila en `intento_acceso`, ni
    asiento, ni sesión, ni línea `origen_no_verificado`, ni verificación de hash. Nace en verde: hoy el `422`
    tampoco asienta intento. Fija que el token no adelanta al `422` (un `credenciales_con_origen_verificado`
    que rechazara por origen antes de validar el cuerpo lo pondría en rojo).
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contador = con_contador(aplicacion_identidad)

    respuesta = cliente.post(
        RUTA_SESION, json={"email": CORREO_DE_ANA}, headers=cabeceras_de(None, cookie, cabecera)
    )

    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_VALIDACION
    assert cuerpo["tipo"] == "VALIDACION"
    assert [(error["campo"], error["codigo"]) for error in cuerpo["errores"]] == [
        ("contrasena", "OBLIGATORIO")
    ]
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    validar_contra("ErrorValidacion", cuerpo)
    assert respuesta.headers.get_list("set-cookie") == []
    lectura = lector()
    assert intentos(lectura) == []
    assert contar(lectura, "bitacora") == 0
    assert contar(lectura, "sesion") == 0
    assert contador.verificaciones == []
    assert lineas_del_rechazo(registro_tecnico) == []


# --------------------------------------------------------------------------- TC-49


def borrador_publicado(cliente: TestClient) -> dict[str, Any]:
    """El `/openapi.json` que publica la aplicación en marcha."""
    respuesta = cliente.get(RUTA_OPENAPI)
    assert respuesta.status_code == 200, respuesta.text
    publicado: dict[str, Any] = respuesta.json()
    return publicado


def esquemas_de_seguridad(operacion: dict[str, Any]) -> set[str]:
    """Los nombres de esquema que exige una operación, unidos entre todas sus alternativas de `security`."""
    return {nombre for requisito in operacion.get("security", []) for nombre in requisito}


def test_tkt057_m4_openapi_publica_el_esquema_csrf_como_cabecera(cliente: TestClient) -> None:
    """TC-49 · M4 — `securitySchemes.csrf` es una `apiKey` en la cabecera `X-CSRF-Token`.

    Nace en verde: `verificar_origen` ya declara el esquema desde la fila 7. Es la regresión del contrato.
    """
    publicado = borrador_publicado(cliente)

    assert publicado["components"]["securitySchemes"]["csrf"] == {
        "type": "apiKey",
        "in": "header",
        "name": CABECERA_CSRF,
    }


@pytest.mark.parametrize("ruta", [RUTA_SESION, RUTA_CIERRE])
def test_tkt057_m4_openapi_las_operaciones_que_mutan_exigen_csrf(
    ruta: str, cliente: TestClient
) -> None:
    """TC-49 · M4 · M8 — `POST /api/v1/sesion` y `POST /api/v1/sesion/cierre` declaran `security` con `csrf`.

    El cierre nace en verde (fila 7); `POST /api/v1/sesion` es el rojo de la fila 8, porque aún no depende de
    la cabecera.
    """
    operacion = borrador_publicado(cliente)["paths"][ruta]["post"]

    assert "csrf" in esquemas_de_seguridad(operacion), operacion.get("security")


def test_tkt057_m4_openapi_las_rutas_get_no_exigen_csrf(cliente: TestClient) -> None:
    """TC-49 · M4 — rechazo: ninguna operación `GET` del contrato declara el esquema `csrf`.

    Nace en verde. Una dependencia puesta por error en una ruta de lectura (`GET /sesion` o
    `GET /sesion/csrf`, que debe poder emitir el token sin tenerlo) la pondría en rojo.
    """
    publicado = borrador_publicado(cliente)

    lecturas = {
        ruta: operaciones["get"]
        for ruta, operaciones in publicado["paths"].items()
        if "get" in operaciones
    }
    assert {RUTA_SESION, RUTA_TOKEN} <= set(lecturas)
    for ruta, operacion in lecturas.items():
        assert "csrf" not in esquemas_de_seguridad(operacion), ruta


def test_tkt057_m8_openapi_el_cuerpo_de_iniciar_sesion_sigue_siendo_credenciales_inicio(
    cliente: TestClient,
) -> None:
    """TC-49 · M8 · E1 — el `requestBody` de `iniciar_sesion` es `$ref` a `CredencialesInicio`, sin envolver.

    Mover la validación del cuerpo a una dependencia no debe convertirlo en un objeto con una clave extra ni
    en un `allOf`. Nace en verde: es la regresión del contrato que el cliente generado del frontend usa.
    """
    publicado = borrador_publicado(cliente)
    operacion = publicado["paths"][RUTA_SESION]["post"]

    assert operacion["operationId"] == "iniciar_sesion"
    contenido = operacion["requestBody"]["content"]
    assert set(contenido) == {"application/json"}
    assert contenido["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CredencialesInicio"
    }
    assert set(publicado["components"]["schemas"]["CredencialesInicio"]["properties"]) == {
        "email",
        "contrasena",
    }


# --------------------------------------------------------------------------- TC-45 y TC-46 (fila 9)
#
# Rotación del token (CA-12, RNF-05). El servidor no guarda el token: «el anterior deja de valer» porque la
# cookie vigente ya no coincide con él (PA-T7, D-10). Todas las peticiones llevan la cabecera `Cookie`
# explícita, de modo que el almacén de cookies del cliente no influye en el resultado.
#
# Rojo esperado: ni `iniciar_sesion` ni `cerrar_sesion` fijan hoy `cimenta_csrf`; la respuesta solo trae
# `cimenta_sesion` (o su expiración), así que `cookie_csrf_fijada` falla con «no fija cimenta_csrf». Los
# casos que parten del `T2` fijado por el inicio fallan por lo mismo antes de llegar a su petición.


def cookie_fijada(respuesta: Respuesta, nombre: str) -> Morsel[str]:
    """La única cookie `nombre` entre los `Set-Cookie` de la respuesta; ninguna o dos es un fallo."""
    encontradas: list[Morsel[str]] = []
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        if nombre in galleta:
            encontradas.append(galleta[nombre])
    assert len(encontradas) == 1, (
        f"Se esperaba exactamente un Set-Cookie de {nombre}; hay {len(encontradas)}: "
        f"{respuesta.headers.get_list('set-cookie')}"
    )
    return encontradas[0]


def exigir_cookie_csrf_rotada(respuesta: Respuesta, anterior: str) -> str:
    """`cimenta_csrf` nueva y distinta de `anterior`, con las banderas de la de `GET /sesion/csrf`. Devuelve su valor."""
    cookie = cookie_fijada(respuesta, COOKIE_CSRF)
    assert cookie.value != anterior
    assert len(cookie.value) >= 32
    assert cookie["secure"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"
    assert not cookie["httponly"]
    return cookie.value


def iniciar_con_t1(cliente: TestClient) -> tuple[str, Respuesta]:
    """Ana inicia sesión enviando `T1`, obtenido con `GET /sesion/csrf`. Devuelve `T1` y la respuesta del inicio."""
    t1 = cliente.get(RUTA_TOKEN).json()["token"]
    cliente.cookies.clear()
    respuesta = cliente.post(
        RUTA_SESION,
        json={"email": CORREO_DE_ANA, "contrasena": CONTRASENA_DE_ANA},
        headers=cabeceras_de(None, t1, t1),
    )
    assert respuesta.status_code == 200, respuesta.text
    cliente.cookies.clear()
    return t1, respuesta


def test_tkt057_ca12_esc1_el_inicio_de_sesion_fija_un_token_csrf_nuevo(
    cliente: TestClient, sembrar_usuario: Callable[..., uuid.UUID]
) -> None:
    """TC-45 · CA-12 esc. 1 · CA-R4 · RNF-05 — el `200` de `POST /sesion` fija `cimenta_csrf` T2 distinto de T1.

    T1 sale de `GET /api/v1/sesion/csrf` y se envía en el par. La cookie nueva conserva las banderas de la
    emitida en `GET /sesion/csrf` (`Secure`, `SameSite=Lax`, `Path=/`, sin `HttpOnly`) y la respuesta sigue
    fijando también `cimenta_sesion`, con `HttpOnly`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)

    t1, respuesta = iniciar_con_t1(cliente)

    exigir_cookie_csrf_rotada(respuesta, t1)
    assert cookie_fijada(respuesta, COOKIE_SESION)["httponly"]
    assert id_de_sesion(respuesta)


def test_tkt057_ca12_esc1_tras_el_inicio_la_cookie_nueva_con_la_cabecera_vieja_se_rechaza(
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-45 · CA-12 esc. 1 · CA-R4 · PA-T7 — rechazo: cookie T2 y cabecera T1 en el cierre es `403 ORIGEN_NO_VERIFICADO`.

    T2 es el valor que fijó el inicio de sesión. Sin estado en el servidor, T1 deja de valer porque ya no
    coincide con la cookie vigente. El contrato de error es completo y no repite ninguno de los dos
    tokens; la sesión sigue sin `revocada_en`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    t1, inicio = iniciar_con_t1(cliente)
    t2 = exigir_cookie_csrf_rotada(inicio, t1)
    sesion_id = id_de_sesion(inicio)

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, t2, t1))

    exigir_origen_no_verificado(respuesta, t1, t2)
    assert revocada_en(lector(), sesion_id) is None


def test_tkt057_ca12_esc1_tras_el_inicio_la_cookie_nueva_con_la_cabecera_nueva_cierra(
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-45 · CA-12 esc. 1 · CA-10 — con T2 en la cookie y en la cabecera, el cierre responde `204`.

    Es la contraparte del rechazo: el par vigente, el que el cliente reenvía tras iniciar sesión, vale.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    t1, inicio = iniciar_con_t1(cliente)
    t2 = exigir_cookie_csrf_rotada(inicio, t1)
    sesion_id = id_de_sesion(inicio)

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, t2, t2))

    assert respuesta.status_code == 204, respuesta.text
    assert revocada_en(lector(), sesion_id) is not None


def test_tkt057_ca12_esc2_el_cierre_de_sesion_fija_un_token_csrf_nuevo(
    cliente: TestClient,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-46 · CA-12 esc. 2 · RNF-05 — el `204` de `POST /sesion/cierre` fija `cimenta_csrf` T3 distinto de T2.

    T2 es el valor que fijó el inicio de sesión y se envía en el par. La respuesta fija T3 con las mismas
    banderas, no lleva cuerpo, y además expira `cimenta_sesion` (`Max-Age=0`, valor vacío) con los
    atributos con que se fijó. La sesión queda revocada.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    t1, inicio = iniciar_con_t1(cliente)
    t2 = exigir_cookie_csrf_rotada(inicio, t1)
    sesion_id = id_de_sesion(inicio)

    respuesta = cliente.post(RUTA_CIERRE, headers=cabeceras_de(sesion_id, t2, t2))

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    t3 = exigir_cookie_csrf_rotada(respuesta, t2)
    assert t3 != t1
    expirada = cookie_fijada(respuesta, COOKIE_SESION)
    assert expirada.value == ""
    assert expirada["max-age"] == "0"
    assert expirada["path"] == "/"
    assert expirada["secure"]
    assert expirada["httponly"]
    assert revocada_en(lector(), sesion_id) is not None


# =========================================================================== Fila 10
# TC-48: el enrutador no deja mutaciones sin verificar (CA-18, RNF-05), más CA-R5 y CA-R6.
#
# Esta fila no lleva código de producción: las filas 7 y 8 ya pusieron `verificar_origen` en el cierre y
# `credenciales_con_origen_verificado` en el inicio, así que los casos sobre la aplicación real **nacen en
# verde**. Lo que demuestra que prueban algo son los oráculos, que montan una ruta de prueba que muta sin
# verificación (o con una verificación que no es la de origen) y exigen que el detector la señale y la
# nombre. Sin ellos, «ninguna ruta sin verificar» podría cumplirse porque el recorrido no ve nada.
#
# Dos cosas se reusan de TKT-006 en vez de repetirse aquí:
#
# * CA-R6 (la lista cerrada de rutas sin sesión) la prueba `test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador`
#   (TC-47 de TKT-006) y sus oráculos, que recorren la aplicación real. `POST /api/v1/sesion` depende de
#   `credenciales_con_origen_verificado` y no de `sesion_vigente`, de modo que sigue en la lista; no se duplica.
# * CA-R5 en la aplicación entera (ninguna ruta, manejador o dependencia es `async def`) la prueba
#   `test_tkt006_car6_rutas_de_identidad_sincronas` (TC-53) con su oráculo. Como recorre las cadenas de
#   dependencias, ya ve `verificar_origen` y `credenciales_con_origen_verificado`. Aquí solo se añade lo que
#   ese recorrido no alcanza: `par_csrf_valido` y `_fijar_cookie_csrf` se llaman desde el cuerpo, no son
#   dependencias.
#
# `rutas_de` y `llamadas` son las ayudas de `test_tkt006_enrutador.py`, copiadas como hacen los demás
# archivos de la suite (los módulos de prueba no se importan entre sí). Mismo límite conocido: una ruta
# protegida solo por `include_router(dependencies=[...])` se cuenta como sin proteger, lo que cae del lado
# seguro (la prueba falla).

METODOS_QUE_MUTAN = frozenset({"POST", "PUT", "PATCH", "DELETE"})
RUTA_DE_PRUEBA = "/api/v1/prueba/muta"
SIN_ENTRADA = "sin entrada en CUERPOS_VALIDOS"
# (identificador, valor de la cookie, valor de la cabecera) de las cuatro combinaciones de CA-9.
CUATRO_COMBINACIONES: list[tuple[str, str | None, str | None]] = [
    (
        str(combinacion.id),
        cast("str | None", combinacion.values[0]),
        cast("str | None", combinacion.values[1]),
    )
    for combinacion in COMBINACIONES_DE_CA9
]


@dataclasses.dataclass(frozen=True)
class PeticionValida:
    """La petición bien formada de una ruta que muta: la comprobación de origen va después del cuerpo (D-5)."""

    cuerpo: dict[str, Any] | None = None
    ruta: str | None = None  # la ruta concreta, si la plantilla tiene parámetros


# El cuerpo válido de cada ruta que muta de la aplicación real. Una ruta nueva que muta y no tenga entrada
# aquí hace fallar TC-48 con un mensaje que lo dice: quien la añade decide su cuerpo válido, la prueba no lo
# adivina.
CUERPOS_VALIDOS: dict[str, PeticionValida] = {
    "POST /api/v1/sesion": PeticionValida(
        {"email": CORREO_DE_ANA, "contrasena": CONTRASENA_DE_ANA}
    ),
    "POST /api/v1/sesion/cierre": PeticionValida(),
    # TKT-017b1, fila B3 (TC-B17): la congelación de la línea base. Un identificador cualquiera basta, porque
    # `verificar_origen` va antes que `exigir_rol` y que cualquier consulta: el `403` sale sin tocar la base.
    "POST /api/v1/lineas-base/{linea_base_id}/congelacion": PeticionValida(
        {"motivo": "Firma de contrato 2026-11-04"},
        ruta="/api/v1/lineas-base/7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e/congelacion",
    ),
}


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido (ayuda de TKT-005)."""
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from rutas_de(original.routes)
        elif isinstance(ruta, APIRoute):
            yield ruta


def llamadas(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    """Cada `call` de la cadena de dependencias de una ruta, bajando por las sub-dependencias."""
    for sub in dependant.dependencies:
        if sub.call is not None:
            yield sub.call
        yield from llamadas(sub)


def rutas_que_mutan(aplicacion: FastAPI) -> list[tuple[str, APIRoute]]:
    """(método, ruta) de cada operación `POST`, `PUT`, `PATCH` o `DELETE` de la aplicación."""
    return [
        (metodo, ruta)
        for ruta in rutas_de(aplicacion.routes)
        for metodo in sorted(METODOS_QUE_MUTAN & set(ruta.methods or ()))
    ]


def cadena_verifica_origen(ruta: APIRoute) -> bool:
    """Si la cadena de la ruta contiene `verificar_origen` o `credenciales_con_origen_verificado`."""
    return any(
        llamada is verificar_origen or llamada is credenciales_con_origen_verificado
        for llamada in llamadas(ruta.dependant)
    )


def requiere_sesion(ruta: APIRoute) -> bool:
    return any(llamada is sesion_vigente for llamada in llamadas(ruta.dependant))


def mutaciones_sin_verificar(aplicacion: FastAPI) -> list[str]:
    """«MÉTODO ruta» de cada operación que muta y no tiene la comprobación de origen en su cadena."""
    return sorted(
        f"{metodo} {ruta.path}"
        for metodo, ruta in rutas_que_mutan(aplicacion)
        if not cadena_verifica_origen(ruta)
    )


def nuevas_sin_verificar(aplicacion: FastAPI, antes: list[str]) -> list[str]:
    """Lo que `mutaciones_sin_verificar` señala ahora y no señalaba `antes`.

    Los oráculos miden solo el efecto de la ruta de prueba que añaden, de modo que no dependen de que la
    aplicación real esté limpia: si lo dejara de estar, caería TC-48 sobre la aplicación real, no ellos.
    """
    return [
        operacion for operacion in mutaciones_sin_verificar(aplicacion) if operacion not in antes
    ]


def probar_las_cuatro_combinaciones(
    cliente: TestClient,
    aplicacion: FastAPI,
    sesion_id: uuid.UUID | None,
    cuerpos: dict[str, PeticionValida],
) -> tuple[list[str], list[str]]:
    """Para cada operación que muta, las cuatro combinaciones de CA-9. Devuelve (probadas, fallos).

    Cada combinación debe responder el contrato completo de `403 PERMISO ORIGEN_NO_VERIFICADO`; cualquier
    otra cosa —`200`, `204`, un `403` por otro motivo, un `422`— es un fallo que nombra la operación y la
    combinación. Una operación sin entrada en `cuerpos` es un fallo, no se salta.
    """
    probadas: list[str] = []
    fallos: list[str] = []
    for metodo, ruta in rutas_que_mutan(aplicacion):
        operacion = f"{metodo} {ruta.path}"
        peticion = cuerpos.get(operacion)
        if peticion is None:
            fallos.append(
                f"{operacion}: {SIN_ENTRADA}; añade el cuerpo válido de la ruta para que TC-48 "
                "pueda probar sus cuatro combinaciones"
            )
            continue
        con_sesion = requiere_sesion(ruta)
        if con_sesion and sesion_id is None:
            fallos.append(f"{operacion}: exige sesión y la prueba no recibió ninguna")
            continue
        probadas.append(operacion)
        for identificador, cookie, cabecera in CUATRO_COMBINACIONES:
            respuesta = cliente.request(
                metodo,
                peticion.ruta or ruta.path,
                json=peticion.cuerpo,
                headers=cabeceras_de(sesion_id if con_sesion else None, cookie, cabecera),
            )
            try:
                exigir_origen_no_verificado(respuesta, TOKEN_DE_COOKIE, TOKEN_DE_CABECERA)
            except (AssertionError, KeyError, ValueError, ValidationError) as error:
                motivo = str(error).splitlines()[0][:160]
                fallos.append(
                    f"{operacion} [{identificador}]: respondió {respuesta.status_code} y no el "
                    f"403 ORIGEN_NO_VERIFICADO completo ({motivo})"
                )
    return probadas, fallos


def ruta_que_muta_de_prueba() -> dict[str, bool]:
    return {"ok": True}


def agregar_ruta_de_prueba(
    aplicacion: FastAPI,
    metodo: str = "POST",
    ruta: str = RUTA_DE_PRUEBA,
    endpoint: Callable[..., Any] = ruta_que_muta_de_prueba,
    **opciones: Any,
) -> str:
    """Añade a la aplicación una ruta de prueba y devuelve «MÉTODO ruta»."""
    enrutador = APIRouter()
    enrutador.add_api_route(ruta, endpoint, methods=[metodo], **opciones)
    aplicacion.include_router(enrutador)
    return f"{metodo} {ruta}"


def ruta_que_rechaza_por_rol() -> dict[str, bool]:
    """Un `403 PERMISO` que no es de origen: el motivo es `ROL_INSUFICIENTE`."""
    raise PermisoDenegado(
        motivo="ROL_INSUFICIENTE",
        mensaje="Tu rol no permite esta operación.",
        roles_requeridos=("COMPRAS",),
    )


# --------------------------------------------------------------------------- TC-48 · la aplicación real


def test_tkt057_ca18_toda_ruta_que_muta_de_la_aplicacion_verifica_el_origen(
    aplicacion_identidad: FastAPI,
) -> None:
    """TC-48 · CA-18 · RNF-05 — toda operación `POST`, `PUT`, `PATCH` o `DELETE` tiene la comprobación de origen en su cadena.

    El recorrido baja por `route.dependant`, así que también ve lo que llega por `dependencies=[...]` y por
    sub-dependencias. Anti-verde vacío: el recorrido encuentra las dos operaciones que mutan hoy, las dos
    de `identidad`; sin ellas, `[] == []` se cumpliría por no haber recorrido nada. La asignación de cada
    una es la del diseño: el cierre por `verificar_origen` y el inicio por `credenciales_con_origen_verificado`.
    """
    sin_verificar = mutaciones_sin_verificar(aplicacion_identidad)

    assert sin_verificar == [], "Rutas que mutan sin comprobar el origen (CA-18):\n" + "\n".join(
        sin_verificar
    )
    mutan = {f"{metodo} {ruta.path}" for metodo, ruta in rutas_que_mutan(aplicacion_identidad)}
    assert mutan >= {"POST /api/v1/sesion", "POST /api/v1/sesion/cierre"}
    cierre = next(r for r in rutas_de(aplicacion_identidad.routes) if r.path == RUTA_CIERRE)
    inicio = next(
        r
        for r in rutas_de(aplicacion_identidad.routes)
        if r.path == RUTA_SESION and "POST" in (r.methods or ())
    )
    assert verificar_origen in list(llamadas(cierre.dependant))
    assert credenciales_con_origen_verificado in list(llamadas(inicio.dependant))


def test_tkt057_ca18_cada_ruta_que_muta_rechaza_las_cuatro_combinaciones_con_403(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-48 · CA-18 · CA-9 — rechazo: para cada operación que muta, ninguna combinación sin par válido se ejecuta.

    Las cuatro combinaciones de CA-9 (ambos ausentes, solo la cookie, solo la cabecera, valores distintos)
    responden `403 PERMISO ORIGEN_NO_VERIFICADO` con el contrato completo, con sesión válida donde la ruta
    la exige. El cuerpo válido de cada ruta sale de `CUERPOS_VALIDOS`. Anti-verde vacío: se probaron las
    dos operaciones de `identidad` y `fallos` está vacío. La sesión de Ana sigue sin revocar: el cierre no
    se ejecutó en ninguna de las cuatro.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_sesion_de_ana(cliente)

    probadas, fallos = probar_las_cuatro_combinaciones(
        cliente, aplicacion_identidad, sesion_id, CUERPOS_VALIDOS
    )

    assert set(probadas) >= {"POST /api/v1/sesion", "POST /api/v1/sesion/cierre"}
    assert fallos == [], "Combinaciones de CA-9 que no responden 403 (CA-18):\n" + "\n".join(fallos)
    assert revocada_en(lector(), sesion_id) is None


# --------------------------------------------------------------------------- TC-48 · oráculos del detector


@pytest.mark.parametrize("metodo", sorted(METODOS_QUE_MUTAN))
def test_tkt057_ca18_oraculo_una_ruta_que_muta_sin_verificacion_se_detecta_y_se_nombra(
    metodo: str, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — oráculo: una ruta nueva que muta sin `verificar_origen` se señala, con su método y su ruta.

    Uno por cada método que muta. La lista es exactamente la ruta de prueba: ni más (la aplicación real no
    se marca) ni menos. Si el detector no la ve, este caso cae.
    """
    antes = mutaciones_sin_verificar(aplicacion_identidad)
    operacion = agregar_ruta_de_prueba(aplicacion_identidad, metodo)

    assert nuevas_sin_verificar(aplicacion_identidad, antes) == [operacion]


@pytest.mark.parametrize("proteccion", ["solo_sesion", "solo_rol"])
def test_tkt057_ca18_oraculo_la_sesion_o_el_rol_solos_no_son_verificacion_de_origen(
    proteccion: str, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — oráculo: exigir sesión o rol no sustituye al par CSRF; la ruta se señala igual.

    Es el caso de quien «protege» una ruta que muta con `sesion_vigente` o `exigir_rol` y olvida el
    doble envío: la sesión por cookie sin CSRF es justo el hueco que CA-18 cierra.
    """
    dependencia = sesion_vigente if proteccion == "solo_sesion" else exigir_rol("COMPRAS")
    antes = mutaciones_sin_verificar(aplicacion_identidad)
    operacion = agregar_ruta_de_prueba(aplicacion_identidad, dependencies=[Depends(dependencia)])

    assert nuevas_sin_verificar(aplicacion_identidad, antes) == [operacion]


@pytest.mark.parametrize(
    "forma",
    ["en_el_decorador", "en_un_parametro", "en_una_sub_dependencia", "credenciales_de_inicio"],
)
def test_tkt057_ca18_oraculo_una_ruta_con_verificar_origen_no_se_senala(
    forma: str, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — anti-falso-positivo: la comprobación de origen cuenta venga como venga.

    En el decorador, en un parámetro, dentro de otra dependencia (la cadena se baja recursivamente) o,
    en `POST /sesion`, como `credenciales_con_origen_verificado`. Anti-verde vacío: la ruta de prueba sí
    está en el recorrido de las que mutan.
    """

    def pasarela(usuario: Annotated[Any, Depends(verificar_origen)]) -> None:
        return None

    def con_parametro(usuario: Annotated[Any, Depends(verificar_origen)]) -> dict[str, bool]:
        return {"ok": True}

    def con_credenciales(
        credenciales: Annotated[CredencialesInicio, Depends(credenciales_con_origen_verificado)],
    ) -> dict[str, bool]:
        return {"ok": True}

    antes = mutaciones_sin_verificar(aplicacion_identidad)
    if forma == "en_el_decorador":
        agregar_ruta_de_prueba(aplicacion_identidad, dependencies=[Depends(verificar_origen)])
    elif forma == "en_un_parametro":
        agregar_ruta_de_prueba(aplicacion_identidad, endpoint=con_parametro)
    elif forma == "en_una_sub_dependencia":
        agregar_ruta_de_prueba(aplicacion_identidad, dependencies=[Depends(pasarela)])
    else:
        agregar_ruta_de_prueba(aplicacion_identidad, endpoint=con_credenciales)

    assert ("POST", RUTA_DE_PRUEBA) in {
        (metodo, ruta.path) for metodo, ruta in rutas_que_mutan(aplicacion_identidad)
    }
    assert nuevas_sin_verificar(aplicacion_identidad, antes) == []


def test_tkt057_ca18_oraculo_las_lecturas_no_se_senalan(aplicacion_identidad: FastAPI) -> None:
    """TC-48 · CA-18 — un `GET` sin verificación no muta y no se señala; no entra en el recorrido de las que mutan."""
    antes = mutaciones_sin_verificar(aplicacion_identidad)
    agregar_ruta_de_prueba(aplicacion_identidad, "GET")

    assert nuevas_sin_verificar(aplicacion_identidad, antes) == []
    assert ("GET", RUTA_DE_PRUEBA) not in {
        (metodo, ruta.path) for metodo, ruta in rutas_que_mutan(aplicacion_identidad)
    }


# --------------------------------------------------------------------------- TC-48 · oráculos de las cuatro combinaciones


def test_tkt057_ca18_oraculo_una_ruta_que_ejecuta_sin_par_valido_falla_las_cuatro_combinaciones(
    cliente: TestClient, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — oráculo: una ruta que muta sin verificación responde `200` en las cuatro y cada una se nombra.

    Si `probar_las_cuatro_combinaciones` diera por buena una respuesta que no es el `403` de origen, este
    caso quedaría con `fallos == []` y cae. Los cuatro fallos nombran la operación y la combinación. Las
    dos rutas reales no están en el mapa de este caso y se reportan aparte; aquí solo cuenta la de prueba.
    """
    operacion = agregar_ruta_de_prueba(aplicacion_identidad)
    cuerpos = {operacion: PeticionValida()}

    probadas, todos = probar_las_cuatro_combinaciones(cliente, aplicacion_identidad, None, cuerpos)

    fallos = [fallo for fallo in todos if fallo.startswith(f"{operacion} [")]
    assert probadas == [operacion]
    assert len(fallos) == 4
    for (identificador, _, _), fallo in zip(CUATRO_COMBINACIONES, fallos, strict=True):
        assert fallo.startswith(f"{operacion} [{identificador}]: respondió 200")


def test_tkt057_ca18_oraculo_un_403_por_otro_motivo_no_cuenta_como_rechazo_de_origen(
    cliente: TestClient, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — oráculo: un `403 PERMISO ROL_INSUFICIENTE` no es `ORIGEN_NO_VERIFICADO` y se reporta.

    Un detector que comprobara solo el código de estado daría por buena una ruta que rechaza por rol y
    nunca mira el token. El fallo conserva el código `403` y dice que no es el contrato de origen.
    """
    operacion = agregar_ruta_de_prueba(aplicacion_identidad, endpoint=ruta_que_rechaza_por_rol)
    cuerpos = {operacion: PeticionValida()}

    probadas, todos = probar_las_cuatro_combinaciones(cliente, aplicacion_identidad, None, cuerpos)

    fallos = [fallo for fallo in todos if fallo.startswith(f"{operacion} [")]
    assert probadas == [operacion]
    assert len(fallos) == 4
    assert all("respondió 403" in fallo and "ROL_INSUFICIENTE" in fallo for fallo in fallos)


def test_tkt057_ca18_oraculo_una_ruta_que_muta_sin_entrada_en_el_mapa_falla_y_lo_dice(
    cliente: TestClient, aplicacion_identidad: FastAPI
) -> None:
    """TC-48 · CA-18 — oráculo: una ruta que muta y no está en `CUERPOS_VALIDOS` falla con un mensaje que lo dice.

    La prueba no adivina el cuerpo de una ruta ajena: quien la añade lo declara. El mapa que se le pasa
    solo trae el inicio de sesión, y la ruta de prueba aparece como un fallo con ese texto.
    """
    operacion = agregar_ruta_de_prueba(aplicacion_identidad, ruta="/api/v1/prueba/sin-cuerpo")
    solo_el_inicio = {"POST /api/v1/sesion": CUERPOS_VALIDOS["POST /api/v1/sesion"]}

    probadas, fallos = probar_las_cuatro_combinaciones(
        cliente, aplicacion_identidad, None, solo_el_inicio
    )

    assert operacion not in probadas
    nombrados = [fallo for fallo in fallos if fallo.startswith(f"{operacion}: {SIN_ENTRADA}")]
    assert len(nombrados) == 1, fallos
    assert "añade el cuerpo válido" in nombrados[0]


# --------------------------------------------------------------------------- CA-R5 · CA-R6


def test_tkt057_car5_las_piezas_nuevas_son_funciones_sincronas_y_estan_en_el_recorrido(
    aplicacion_identidad: FastAPI,
) -> None:
    """CA-R5 · regla 11 de CLAUDE.md — `par_csrf_valido`, `verificar_origen`, `credenciales_con_origen_verificado` y `_fijar_cookie_csrf` son `def`.

    La aplicación entera (ninguna ruta, manejador o dependencia `async def`) la comprueba TC-53 de TKT-006
    (`test_tkt006_car6_rutas_de_identidad_sincronas`) con su oráculo, y ya recorre las cadenas de las dos
    dependencias nuevas. Aquí se añade lo que ese recorrido no alcanza: `par_csrf_valido` y
    `_fijar_cookie_csrf` se llaman desde el cuerpo y no son dependencias. Una `async def` con una llamada a
    SQLAlchemy síncrono congelaría el bucle (ADR-013). Anti-verde vacío: las dos dependencias nuevas están
    en las cadenas de `cerrar_sesion` e `iniciar_sesion`, que el recorrido de TC-53 sí ve.
    """
    from cimenta.identidad.api import rutas
    from cimenta.identidad.api.dependencias import par_csrf_valido

    piezas: dict[str, Callable[..., Any]] = {
        "par_csrf_valido": par_csrf_valido,
        "verificar_origen": verificar_origen,
        "credenciales_con_origen_verificado": credenciales_con_origen_verificado,
        "_fijar_cookie_csrf": rutas._fijar_cookie_csrf,
    }
    for nombre, pieza in piezas.items():
        assert inspect.isfunction(pieza), nombre
        assert not inspect.iscoroutinefunction(pieza), f"{nombre} es async def"
    cadenas = {
        ruta.endpoint.__name__: list(llamadas(ruta.dependant))
        for ruta in rutas_de(aplicacion_identidad.routes)
    }
    assert verificar_origen in cadenas["cerrar_sesion"]
    assert credenciales_con_origen_verificado in cadenas["iniciar_sesion"]
    assert not [
        llamada.__name__
        for nombre in ("cerrar_sesion", "iniciar_sesion")
        for llamada in cadenas[nombre]
        if inspect.isfunction(llamada) and inspect.iscoroutinefunction(llamada)
    ]


# --------------------------------------------------------------------------- TC-67 · el borrador (fila 15)
#
# Rojo esperado y por qué: el borrador `docs/api/openapi.yaml` aún no recoge TKT-057 (lo cambia la fila 15, que es
# documentación). `cerrar_sesion` lleva solo `TKT-006`, el `Set-Cookie` de las dos respuestas apunta a
# `SetCookieSesion` (que declara solo la cookie de sesión), no existe `SetCookieSesionYCsrf`, el esquema `csrf` no
# habla de rotación y `DemasiadosIntentos` no cita los valores por omisión. Ninguno de estos casos necesita Docker
# ni la aplicación: leen el YAML, así que el rojo es siempre una aserción y nunca un error de entorno.
#
# Nace en verde, a propósito, el control de anti-verde-vacío del componente `SetCookieCsrf`, que TKT-057 no toca.

REFERENCIA_SET_COOKIE_NUEVA = "#/components/headers/SetCookieSesionYCsrf"
REFERENCIA_SET_COOKIE_VIEJA = "#/components/headers/SetCookieSesion"
ROTACION = re.compile(
    r"rotaci[oó]n|\brota\b|\brotar\b|\brotado\b|\brotan\b|\bse rota\b", re.IGNORECASE
)


def referencias_del_borrador(nodo: object) -> Iterator[str]:
    """Todo valor de un `$ref` del borrador, recorrido en profundidad."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "$ref" and isinstance(valor, str):
                yield valor
            else:
                yield from referencias_del_borrador(valor)
    elif isinstance(nodo, list):
        for elemento in nodo:
            yield from referencias_del_borrador(elemento)


def set_cookie_de(ruta: str, codigo: str) -> object:
    """El `Set-Cookie` declarado en la respuesta `codigo` de `POST ruta`, tal como está escrito en el borrador."""
    respuesta = borrador()["paths"][ruta]["post"]["responses"][codigo]
    return respuesta["headers"]["Set-Cookie"]


def texto_plano(descripcion: str) -> str:
    """La descripción en una sola línea, para buscar frases sin depender de los saltos del YAML."""
    return " ".join(descripcion.split())


def test_tkt057_m8_borrador_cerrar_sesion_lleva_tkt057_en_x_tickets() -> None:
    """TKT-057 · M8 · TC-67 — `cerrar_sesion` declara `TKT-006` y `TKT-057` en `x-tickets`."""
    operacion = borrador()["paths"]["/sesion/cierre"]["post"]

    assert operacion["operationId"] == "cerrar_sesion"
    assert operacion["x-tickets"] == ["TKT-006", "TKT-057"]


def test_tkt057_m8_borrador_iniciar_sesion_sigue_declarando_tkt057_en_x_tickets() -> None:
    """TKT-057 · M8 · TC-67 (control) — `iniciar_sesion` ya cita `TKT-057`: el rojo de `cerrar_sesion` no es un YAML mal leído."""
    operacion = borrador()["paths"]["/sesion"]["post"]

    assert operacion["operationId"] == "iniciar_sesion"
    assert operacion["x-tickets"] == ["TKT-006", "TKT-057"]


def test_tkt057_m8_borrador_el_200_de_iniciar_sesion_declara_las_cookies_de_sesion_y_csrf() -> None:
    """TKT-057 · M8 · TC-67 — el `Set-Cookie` del `200` de `iniciar_sesion` es `SetCookieSesionYCsrf`."""
    assert set_cookie_de("/sesion", "200") == {"$ref": REFERENCIA_SET_COOKIE_NUEVA}


def test_tkt057_m8_borrador_el_204_de_cerrar_sesion_declara_las_cookies_de_sesion_y_csrf() -> None:
    """TKT-057 · M8 · TC-67 — el `Set-Cookie` del `204` de `cerrar_sesion` es `SetCookieSesionYCsrf`."""
    assert set_cookie_de("/sesion/cierre", "204") == {"$ref": REFERENCIA_SET_COOKIE_NUEVA}


def test_tkt057_m8_borrador_set_cookie_sesion_y_csrf_describe_las_dos_cookies_y_la_rotacion() -> (
    None
):
    """TKT-057 · M8 · TC-67 — el componente existe y su descripción nombra `cimenta_sesion`, `cimenta_csrf` y la rotación."""
    cabeceras = borrador()["components"]["headers"]

    assert "SetCookieSesionYCsrf" in cabeceras
    componente = cabeceras["SetCookieSesionYCsrf"]
    descripcion = texto_plano(componente["description"])
    assert "cimenta_sesion" in descripcion
    assert "cimenta_csrf" in descripcion
    assert ROTACION.search(descripcion), descripcion
    assert componente["schema"] == {"type": "string"}


def test_tkt057_m8_borrador_el_componente_set_cookie_sesion_ya_no_queda_huerfano() -> None:
    """TKT-057 · M8 · TC-67 — `SetCookieSesion` se borra: ninguna respuesta lo usa tras sustituirlo."""
    documento = borrador()
    referencias = list(referencias_del_borrador(documento))

    # Sin referencias vivas a `SetCookieSesion`, el componente no debe seguir declarado; si alguien lo vuelve a
    # usar, la prueba exige entonces que siga existiendo (nunca una referencia colgante).
    usado = REFERENCIA_SET_COOKIE_VIEJA in referencias
    declarado = "SetCookieSesion" in documento["components"]["headers"]
    assert declarado == usado, f"declarado={declarado}, referenciado={usado}"
    assert not usado, (
        "`SetCookieSesion` sigue referenciado: las dos respuestas deben usar SetCookieSesionYCsrf"
    )
    assert REFERENCIA_SET_COOKIE_NUEVA in referencias


def test_tkt057_m8_borrador_set_cookie_csrf_sigue_declarado_y_referenciado() -> None:
    """TKT-057 · M8 · TC-67 (control) — `SetCookieCsrf` de `obtener_token_csrf` no se toca y sigue en uso."""
    documento = borrador()

    assert "SetCookieCsrf" in documento["components"]["headers"]
    assert "#/components/headers/SetCookieCsrf" in list(referencias_del_borrador(documento))


def test_tkt057_m8_borrador_el_esquema_csrf_dice_que_el_token_rota_al_iniciar_y_al_cerrar_sesion() -> (
    None
):
    """TKT-057 · M8 · TC-67 — `securitySchemes.csrf` menciona la rotación al iniciar y al cerrar sesión."""
    esquema = borrador()["components"]["securitySchemes"]["csrf"]
    descripcion = texto_plano(esquema["description"]).lower()

    assert esquema["type"] == "apiKey"
    assert esquema["name"] == "X-CSRF-Token"
    assert ROTACION.search(descripcion), descripcion
    assert "iniciar" in descripcion
    assert "cerrar" in descripcion


def test_tkt057_m8_borrador_demasiados_intentos_cita_cinco_veinte_y_quince_minutos() -> None:
    """TKT-057 · M8 · TC-67 · RNF-04 — la respuesta `429` cita 5 por cuenta, 20 por origen, 15 minutos y que se configuran."""
    respuesta = borrador()["components"]["responses"]["DemasiadosIntentos"]
    descripcion = texto_plano(respuesta["description"]).lower()

    assert re.search(r"\b5\b", descripcion), descripcion
    assert re.search(r"\b20\b", descripcion), descripcion
    assert re.search(r"\b15 minutos\b", descripcion), descripcion
    assert "configur" in descripcion, descripcion
