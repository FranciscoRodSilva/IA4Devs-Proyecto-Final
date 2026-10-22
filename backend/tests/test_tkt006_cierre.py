"""Cierre de sesión por HTTP (TKT-006, fila 7, tanda 1): `POST /api/v1/sesion/cierre`, con Docker.

Cubre `CA-9` (TC-43 a TC-46 del diseño): cerrar revoca sin borrar, la sesión cerrada ya no sirve, cerrar
sin sesión es `401 SIN_SESION` sin tocar ninguna fila y el rol de aplicación nunca emite un `DELETE`
sobre `sesion` ni un `UPDATE` o `DELETE` sobre `intento_acceso`. No se envía token CSRF: exigirlo en
`cerrar_sesion` es de TKT-057.

Cada rechazo comprueba el contrato de error completo: código `401`, `tipo` `SESION`, `motivo`, el
`mensaje` literal del diseño, el conjunto exacto de claves (`tipo`, `motivo`, `mensaje`,
`correlacion_id`), la ausencia de `detail`, `correlacion_id` igual a la cabecera `X-Correlacion-Id` y la
validación contra `ErrorSesion` del borrador. La base se lee con una conexión **nueva** del rol de
aplicación. Una cookie que ya no está en el almacén del cliente se envía con la cabecera `Cookie`.

Rojo esperado: `crear_aplicacion` aún no acepta `motor`, `reloj` ni `entorno`, así que la *fixture*
`aplicacion_identidad` falla con `TypeError`. Con la firma pedida y sin las rutas, serían `404`.
"""

from __future__ import annotations

import functools
import re
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import event
from sqlalchemy.engine import Engine

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
RUTA_CIERRE = "/api/v1/sesion/cierre"
COOKIE_SESION = "cimenta_sesion"
CORREO_DE_ANA = "ana@cimenta.test"
CONTRASENA_DE_ANA = "Clave-Correcta-1"
CORREO_DE_LUIS = "luis@cimenta.test"
CONTRASENA_DE_LUIS = "Clave-De-Luis-2"
ROLES_DE_ANA = ("RESIDENTE", "COMPRAS")
MENSAJES_LITERALES = {
    "SIN_SESION": "No hay una sesión iniciada.",
    "SESION_CADUCADA": "La sesión caducó. Inicia sesión de nuevo.",
    "SESION_REVOCADA": "La sesión ya no es válida. Inicia sesión de nuevo.",
}
CLAVES_DE_ERROR_DE_SESION = {"tipo", "motivo", "mensaje", "correlacion_id"}

Conexion = psycopg.Connection[tuple[Any, ...]]
SembrarUsuario = Callable[..., uuid.UUID]
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


def exigir_error_de_sesion(respuesta: Respuesta, motivo: str) -> None:
    """El contrato de error completo de un `401` de sesión (CA-7, CA-9, CA-R5)."""
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == motivo
    assert cuerpo["mensaje"] == MENSAJES_LITERALES[motivo]
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorSesion", cuerpo)


def con_cookie(valor: str) -> dict[str, str]:
    """La cabecera `Cookie` con la sesión indicada, para una cookie que el almacén del cliente ya no tiene."""
    return {"Cookie": f"{COOKIE_SESION}={valor}"}


def iniciar(cliente: TestClient, correo: str, contrasena: str) -> uuid.UUID:
    """Inicia sesión por HTTP (`POST /api/v1/sesion`) y devuelve el identificador de la cookie."""
    respuesta = cliente.post(RUTA_SESION, json={"email": correo, "contrasena": contrasena})
    assert respuesta.status_code == 200, respuesta.text
    return uuid.UUID(una_cookie(respuesta, COOKIE_SESION).value)


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


def filas_de_sesion(conexion: Conexion) -> list[dict[str, Any]]:
    """Todas las filas de `sesion`, por nombre de columna y ordenadas por id."""
    filas = conexion.execute(
        "SELECT id, usuario_id, creada_en, expira_en, ultima_actividad, revocada_en, origen_ip, "
        "agente_usuario FROM sesion ORDER BY id"
    ).fetchall()
    nombres = (
        "id",
        "usuario_id",
        "creada_en",
        "expira_en",
        "ultima_actividad",
        "revocada_en",
        "origen_ip",
        "agente_usuario",
    )
    return [dict(zip(nombres, fila, strict=True)) for fila in filas]


def fila_de_sesion(conexion: Conexion, sesion_id: uuid.UUID) -> dict[str, Any]:
    """La fila de `sesion`; falla con nombre si no existe (la fila nunca se borra)."""
    coincidencias = [fila for fila in filas_de_sesion(conexion) if fila["id"] == sesion_id]
    assert len(coincidencias) == 1, f"Se esperaba una fila de sesion con id {sesion_id}."
    return coincidencias[0]


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


# --------------------------------------------------------------------------- TC-43


def test_tkt006_ca09_cerrar_revoca_sin_borrar(
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-43 · CA-9 esc. 1 · M4 — 204 sin cuerpo; la fila sigue y `revocada_en` es la hora del reloj.

    Tres minutos después de abrir. No hay otra fila: nunca se borra (ADR-014). La respuesta lleva
    `X-Correlacion-Id`.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    respuesta = cliente.post(RUTA_CIERRE)

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert uuid.UUID(respuesta.headers[CABECERA]).version == 4
    lectura = lector()
    assert contar(lectura, "sesion") == 1
    fila = fila_de_sesion(lectura, sesion_id)
    assert fila["usuario_id"] == ana
    assert fila["revocada_en"] == reloj_de_prueba.ahora
    assert fila["creada_en"] == inicio
    assert fila["expira_en"] == inicio + timedelta(hours=12)


def test_tkt006_ca09_cerrar_expira_la_cookie_de_sesion(
    cliente: TestClient, sembrar_usuario: SembrarUsuario
) -> None:
    """TC-43 · CA-9 esc. 1 · RNF-02 — el `Set-Cookie` expira `cimenta_sesion` con `Path=/`, `Secure` y `HttpOnly`.

    Expirar es `Max-Age=0` o una `expires` en el pasado. Con los mismos atributos que la fijaron, el
    navegador la reconoce como la misma cookie y la borra. El almacén del cliente ya no la conserva.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    assert COOKIE_SESION in cliente.cookies

    respuesta = cliente.post(RUTA_CIERRE)

    cookie = una_cookie(respuesta, COOKIE_SESION)
    caduca_con_max_age = cookie["max-age"] == "0"
    caduca_en_el_pasado = bool(cookie["expires"]) and parsedate_to_datetime(
        cookie["expires"]
    ) < datetime.now(UTC)
    assert caduca_con_max_age or caduca_en_el_pasado
    assert cookie["path"] == "/"
    assert cookie["secure"]
    assert cookie["httponly"]
    assert cookie["samesite"].lower() == "lax"
    assert COOKIE_SESION not in cliente.cookies


# --------------------------------------------------------------------------- TC-44


def test_tkt006_ca09_la_sesion_cerrada_ya_no_sirve(
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-44 · CA-9 esc. 2 — rechazo: la misma cookie, enviada por cabecera, responde `401 SESION_REVOCADA`.

    La cookie ya no está en el almacén del cliente tras el cierre, así que se envía a mano. El rechazo
    conserva la hora del cierre y no desliza la actividad.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    reloj_de_prueba.avanzar(timedelta(minutes=3))
    assert cliente.post(RUTA_CIERRE).status_code == 204
    cerrada_en = reloj_de_prueba.ahora
    ultima_actividad = fila_de_sesion(lector(), sesion_id)["ultima_actividad"]
    reloj_de_prueba.avanzar(timedelta(minutes=1))

    respuesta = cliente.get(RUTA_SESION, headers=con_cookie(str(sesion_id)))

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")
    fila = fila_de_sesion(lector(), sesion_id)
    assert fila["revocada_en"] == cerrada_en
    assert fila["ultima_actividad"] == ultima_actividad


def test_tkt006_ca09_cerrar_dos_veces_la_segunda_es_revocada(
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-44 · CA-9 esc. 2 — rechazo: cerrar con una cookie ya cerrada es `401 SESION_REVOCADA` y no pisa la hora.

    La segunda hora del reloj es distinta; `revocada_en` conserva la del primer cierre.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    reloj_de_prueba.avanzar(timedelta(minutes=3))
    assert cliente.post(RUTA_CIERRE).status_code == 204
    primera_hora = reloj_de_prueba.ahora
    reloj_de_prueba.avanzar(timedelta(minutes=7))

    respuesta = cliente.post(RUTA_CIERRE, headers=con_cookie(str(sesion_id)))

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")
    assert fila_de_sesion(lector(), sesion_id)["revocada_en"] == primera_hora


def test_tkt006_ca09_cerrar_una_sesion_no_revoca_las_demas(
    cliente: TestClient,
    reloj_de_prueba: Any,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-43 · CA-9 — cerrar la sesión de Ana no revoca ni otra sesión de Ana ni la de Luis: siguen respondiendo 200."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sembrar_usuario(CORREO_DE_LUIS, CONTRASENA_DE_LUIS, nombre="Luis Mena")
    cerrada = iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    otra_de_ana = iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    de_luis = iniciar(cliente, CORREO_DE_LUIS, CONTRASENA_DE_LUIS)
    cliente.cookies.clear()
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    respuesta = cliente.post(RUTA_CIERRE, headers=con_cookie(str(cerrada)))

    assert respuesta.status_code == 204
    lectura = lector()
    assert fila_de_sesion(lectura, cerrada)["revocada_en"] == reloj_de_prueba.ahora
    assert fila_de_sesion(lectura, otra_de_ana)["revocada_en"] is None
    assert fila_de_sesion(lectura, de_luis)["revocada_en"] is None
    for viva in (otra_de_ana, de_luis):
        assert cliente.get(RUTA_SESION, headers=con_cookie(str(viva))).status_code == 200
    exigir_error_de_sesion(
        cliente.get(RUTA_SESION, headers=con_cookie(str(cerrada))), "SESION_REVOCADA"
    )


# --------------------------------------------------------------------------- TC-45


def test_tkt006_ca09_cerrar_sin_sesion(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-45 · CA-9 esc. 3 — rechazo: sin cookie, `401 SIN_SESION` con el contrato completo y `sesion` intacta.

    Hay una sesión real de otro usuario: la tabla `sesion`, con todas sus columnas, es idéntica antes y
    después. La bitácora no recibe ningún asiento (un rechazo anónimo no es un `DENEGAR`).
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    cliente.cookies.clear()
    antes = filas_de_sesion(lector())
    assert len(antes) == 1

    respuesta = cliente.post(RUTA_CIERRE)

    exigir_error_de_sesion(respuesta, "SIN_SESION")
    lectura = lector()
    assert filas_de_sesion(lectura) == antes
    assert contar(lectura, "bitacora") == 0


@pytest.mark.parametrize(
    "valor", [str(uuid.uuid4()), "abc", ""], ids=["uuid_inexistente", "mal_formada", "vacia"]
)
def test_tkt006_ca09_cerrar_con_una_cookie_que_no_corresponde_a_nada(
    valor: str,
    cliente: TestClient,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-45 · CA-9 esc. 3 · CA-7 esc. 2 — rechazo: una cookie inexistente o mal formada es `SIN_SESION`, sin tocar `sesion`.

    No se distingue «no existe» de «mal formada». La sesión real de Ana conserva todas sus columnas.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    cliente.cookies.clear()
    antes = filas_de_sesion(lector())

    respuesta = cliente.post(RUTA_CIERRE, headers=con_cookie(valor))

    exigir_error_de_sesion(respuesta, "SIN_SESION")
    assert filas_de_sesion(lector()) == antes


# --------------------------------------------------------------------------- TC-46


@pytest.fixture
def sentencias(motor_aplicacion: Engine) -> Iterator[list[str]]:
    """Cada sentencia SQL que emite el motor del rol de aplicación mientras dura la prueba."""
    emitidas: list[str] = []

    def anotar(
        conexion: Any, cursor: Any, sentencia: str, parametros: Any, contexto: Any, varias: bool
    ) -> None:
        emitidas.append(sentencia)

    event.listen(motor_aplicacion, "before_cursor_execute", anotar)
    try:
        yield emitidas
    finally:
        event.remove(motor_aplicacion, "before_cursor_execute", anotar)


def test_tkt006_ca09_sin_delete_sobre_sesion(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, sentencias: list[str]
) -> None:
    """TC-46 · CA-9 esc. 4 · CA-R1 — rechazo: iniciar, consultar y cerrar no emiten `DELETE` sobre `sesion`.

    Tampoco `UPDATE` ni `DELETE` sobre `intento_acceso`, que solo recibe `INSERT` (invariante 20). Para
    que la ausencia signifique algo, el flujo sí emitió el `INSERT` de la sesión y del intento y el
    `UPDATE` que escribe `revocada_en`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    del sentencias[:]

    iniciar(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    assert cliente.get(RUTA_SESION).status_code == 200
    assert cliente.post(RUTA_CIERRE).status_code == 204

    emitidas = "\n".join(sentencias)
    assert re.search(r"INSERT\s+INTO\s+sesion\b", emitidas, re.IGNORECASE)
    assert re.search(r"INSERT\s+INTO\s+intento_acceso\b", emitidas, re.IGNORECASE)
    assert re.search(r"UPDATE\s+sesion\s+SET\s+revocada_en\b", emitidas, re.IGNORECASE)
    assert not re.search(r"DELETE\s+FROM\s+sesion\b", emitidas, re.IGNORECASE)
    assert not re.search(r"UPDATE\s+intento_acceso\b", emitidas, re.IGNORECASE)
    assert not re.search(r"DELETE\s+FROM\s+intento_acceso\b", emitidas, re.IGNORECASE)
