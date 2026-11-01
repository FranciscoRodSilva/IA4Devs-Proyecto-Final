"""Cabeceras de seguridad (TKT-057, fila 13): TC-59 a TC-63, `CA-13` y `CA-14`.

Cubre `servidor.cabeceras` (`cabeceras_de_seguridad`, `cabeceras_para_ruta` y
`MiddlewareCabecerasSeguridad`), su registro en la fábrica y las cabeceras del `500`, que sale por fuera
de los middleware (el manejador de `Exception` lo atiende `ServerErrorMiddleware`).

Con Docker: TC-59 (los siete casos de `CA-13` salen de la aplicación real con `cliente`, porque el `401`, el
`403` anónimo y el `429` de `POST /sesion` escriben en `intento_acceso`). Sin Docker: TC-60 a TC-63 y las
pruebas del módulo, que construyen la aplicación con `crear_aplicacion(entorno=...)` y solo piden rutas que
no tocan la base (`GET /api/v1/sesion/csrf`, `/openapi.json`, el `404` y las rutas de prueba de la suite).

Los valores esperados están escritos aquí en literal, no calculados con el código de producción: la prueba
no puede coincidir con una constante equivocada. El orden de las directivas de la política es el del diseño.
Cada cabecera debe aparecer **una sola vez** (`get_list`), para que un middleware que añade sin quitar o un
manejador del `500` que duplica el trabajo del middleware queden en rojo.

El símbolo de producción (`servidor.cabeceras`) se importa **dentro** de cada caso que lo necesita, así
cada uno falla por sí solo y la recolección no se cae.

Rojo esperado en esta fila, y por qué:

* TC-59, TC-60, TC-61, TC-62 y el caso de `Cache-Control` fuera de `/api/`: la respuesta aún no lleva
  ninguna de las cuatro cabeceras; la aserción de presencia falla.
* Las pruebas del módulo y la del middleware crudo: `servidor.cabeceras` no existe (`ModuleNotFoundError`
  dentro del cuerpo del caso, que no tumba la recolección).
* La de `aplicacion.state.cabeceras_seguridad`: la fábrica aún no la guarda.

Nace en verde, a propósito: TC-63, porque hoy el manejador del `500` ya pone `X-Correlacion-Id` y el cuerpo
de TKT-005. Es la regresión que debe seguir verde cuando el manejador añada las cabeceras de seguridad.
"""

from __future__ import annotations

import asyncio
import io
import secrets
import uuid
from collections.abc import Callable, MutableMapping
from datetime import timedelta
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

ALMACEN = "https://almacen.cimenta.test"
RUTA_TOKEN = "/api/v1/sesion/csrf"
RUTA_SESION = "/api/v1/sesion"
RUTA_INEXISTENTE = "/api/v1/ruta-inexistente"
RUTA_QUE_EXPLOTA = "/api/v1/prueba/explota"
RUTA_QUE_REBAJA = "/api/v1/prueba/rebaja"
RUTA_OPENAPI = "/openapi.json"
CABECERA_CORRELACION = "X-Correlacion-Id"
COOKIE_CSRF = "cimenta_csrf"
CABECERA_CSRF = "X-CSRF-Token"
TOKEN_CSRF = "token-csrf-de-la-prueba"
DETALLE_INTERNO = "detalle-interno-que-no-debe-salir"
MENSAJE_ERROR_NO_CONTROLADO = (
    "Ocurrió un error inesperado. Cita el identificador de correlación si pides ayuda."
)

HSTS = "Strict-Transport-Security"
NOSNIFF = "X-Content-Type-Options"
REFERRER = "Referrer-Policy"
CSP = "Content-Security-Policy"
CACHE = "Cache-Control"

VALOR_HSTS = "max-age=31536000"
VALOR_NOSNIFF = "nosniff"
VALOR_REFERRER = "no-referrer"
VALOR_CACHE = "no-store"
# Las cuatro cabeceras que llevan todas las respuestas, de cualquier ruta.
FIJAS = {HSTS: VALOR_HSTS, NOSNIFF: VALOR_NOSNIFF, REFERRER: VALOR_REFERRER}


def csp_esperada(almacen: str | None) -> str:
    """La política exacta del diseño: `{A}` es `' ' + almacen` si está configurado y vacío si no."""
    a = f" {almacen}" if almacen else ""
    return (
        f"default-src 'self'; base-uri 'none'; connect-src 'self'{a}; font-src 'self'; "
        f"form-action 'self'; frame-ancestors 'none'; img-src 'self'{a}; media-src 'self'{a}; "
        "object-src 'none'; script-src 'self'; style-src 'self'"
    )


# --------------------------------------------------------------------------- ayudas


def valor_unico(respuesta: Any, nombre: str) -> str:
    """El único valor de la cabecera: ausente o repetida falla con un mensaje que lo dice."""
    valores = respuesta.headers.get_list(nombre)
    assert len(valores) == 1, (
        f"{nombre} debe aparecer una vez en la respuesta {respuesta.status_code} y aparece "
        f"{len(valores)} ({valores!r})."
    )
    return str(valores[0])


def exigir_cabeceras_fijas(respuesta: Any, *, almacen: str | None = None) -> None:
    """Las cuatro cabeceras de toda respuesta, con su valor exacto y una sola vez cada una."""
    for nombre, valor in FIJAS.items():
        assert valor_unico(respuesta, nombre) == valor
    assert valor_unico(respuesta, CSP) == csp_esperada(almacen)


def directivas(politica: str) -> dict[str, list[str]]:
    """`default-src 'self'; img-src 'self' x` → `{'default-src': ["'self'"], 'img-src': [...]}`."""
    resultado: dict[str, list[str]] = {}
    for parte in politica.split(";"):
        palabras = parte.split()
        if palabras:
            assert palabras[0] not in resultado, f"Directiva repetida: {palabras[0]}"
            resultado[palabras[0]] = palabras[1:]
    return resultado


def politica_de(respuesta: Any) -> dict[str, list[str]]:
    return directivas(valor_unico(respuesta, CSP))


def rutas_de_prueba() -> APIRouter:
    """Rutas de la suite (no del producto): una que explota y una que intenta rebajar las cabeceras."""
    enrutador = APIRouter()

    def explota() -> dict[str, bool]:
        raise RuntimeError(DETALLE_INTERNO)

    def rebaja() -> Response:
        return Response(
            content="{}",
            media_type="application/json",
            headers={
                CACHE: "public, max-age=3600",
                CSP: "default-src *",
                HSTS: "max-age=0",
                NOSNIFF: "sniff",
                REFERRER: "unsafe-url",
            },
        )

    enrutador.add_api_route(RUTA_QUE_EXPLOTA, explota, methods=["GET"])
    enrutador.add_api_route(RUTA_QUE_REBAJA, rebaja, methods=["GET"])
    return enrutador


def aplicacion_sin_base(almacen: str | None = None) -> FastAPI:
    """La aplicación real sin motor ni Docker: construirla no abre conexión (el motor es perezoso)."""
    from servidor.fabrica import crear_aplicacion

    entorno = {"CIMENTA_DB_CONTRASENA_APLICACION": secrets.token_urlsafe(16)}
    if almacen is not None:
        entorno["CIMENTA_ALMACEN_ORIGEN"] = almacen
    aplicacion = crear_aplicacion(destino_registro=io.StringIO(), entorno=entorno)
    aplicacion.include_router(rutas_de_prueba())
    return aplicacion


def cliente_sin_base(almacen: str | None = None) -> TestClient:
    return TestClient(
        aplicacion_sin_base(almacen),
        base_url="https://testserver",
        raise_server_exceptions=False,
    )


def sesion_con_par_csrf(cliente: TestClient, correo: str, contrasena: str) -> Any:
    """`POST /api/v1/sesion` con el par de token CSRF coincidente."""
    return cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers={"Cookie": f"{COOKIE_CSRF}={TOKEN_CSRF}", CABECERA_CSRF: TOKEN_CSRF},
    )


# --------------------------------------------------------------------------- TC-59


def peticion_200(cliente: TestClient, reloj: Any) -> Any:
    return cliente.get(RUTA_TOKEN)


def peticion_401(cliente: TestClient, reloj: Any) -> Any:
    return sesion_con_par_csrf(cliente, "nadie@cimenta.test", "Clave-Equivocada-9")


def peticion_403(cliente: TestClient, reloj: Any) -> Any:
    return cliente.post(
        RUTA_SESION, json={"email": "nadie@cimenta.test", "contrasena": "Clave-Equivocada-9"}
    )


def peticion_422(cliente: TestClient, reloj: Any) -> Any:
    return cliente.post(RUTA_SESION, json={"email": "nadie@cimenta.test"})


def peticion_404(cliente: TestClient, reloj: Any) -> Any:
    return cliente.get(RUTA_INEXISTENTE)


def peticion_429(cliente: TestClient, reloj: Any) -> Any:
    for _ in range(5):
        assert peticion_401(cliente, reloj).status_code == 401
    reloj.avanzar(timedelta(seconds=30))
    return sesion_con_par_csrf(cliente, "nadie@cimenta.test", "Clave-Equivocada-9")


def peticion_500(cliente: TestClient, reloj: Any) -> Any:
    return cliente.get(RUTA_QUE_EXPLOTA)


CASOS_DE_CA13: list[Any] = [
    pytest.param(peticion_200, 200, id="200_token_csrf"),
    pytest.param(peticion_401, 401, id="401_credenciales_falsas"),
    pytest.param(peticion_403, 403, id="403_sin_token"),
    pytest.param(peticion_422, 422, id="422_mal_formado"),
    pytest.param(peticion_404, 404, id="404_ruta_inexistente"),
    pytest.param(peticion_500, 500, id="500_excepcion_no_controlada"),
    pytest.param(peticion_429, 429, id="429_bloqueo"),
]


@pytest.mark.parametrize(("peticion", "estado"), CASOS_DE_CA13)
def test_tkt057_ca13_toda_respuesta_lleva_las_cuatro_cabeceras_y_no_store_bajo_api(
    peticion: Callable[[TestClient, Any], Any],
    estado: int,
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: Any,
) -> None:
    """TC-59 · CA-13 · RNF-05 · RNF-06 — rechazo: éxito y seis rechazos llevan las cuatro cabeceras exactas.

    `Strict-Transport-Security: max-age=31536000` (sin `includeSubDomains` ni `preload`),
    `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, la política de contenido completa y,
    por ser una ruta `/api/`, `Cache-Control: no-store`. Cada una aparece una sola vez. El `500` sale por
    fuera de los middleware: lo añade el manejador.
    """
    aplicacion_identidad.include_router(rutas_de_prueba())

    respuesta = peticion(cliente, reloj_de_prueba)

    assert respuesta.status_code == estado, respuesta.text
    exigir_cabeceras_fijas(respuesta)
    assert valor_unico(respuesta, CACHE) == VALOR_CACHE


# --------------------------------------------------------------------------- TC-60


@pytest.mark.parametrize("ruta", [RUTA_TOKEN, RUTA_INEXISTENTE], ids=["200", "404"])
def test_tkt057_ca14_esc1_con_almacen_solo_ese_origen_se_suma_a_self(ruta: str) -> None:
    """TC-60 · CA-14 esc. 1 · RNF-06 — rechazo: `img-src`, `media-src` y `connect-src` admiten `'self'` y el almacén.

    Con `CIMENTA_ALMACEN_ORIGEN=https://almacen.cimenta.test`: esas tres directivas son exactamente
    `'self'` y ese origen, en cualquier respuesta (un `200` y un `404`); el resto de los orígenes de la
    política es `'self'` o `'none'`.
    """
    respuesta = cliente_sin_base(ALMACEN).get(ruta)

    politica = politica_de(respuesta)
    for directiva in ("img-src", "media-src", "connect-src"):
        assert politica[directiva] == ["'self'", ALMACEN], directiva
    for nombre, fuentes in politica.items():
        if nombre not in {"img-src", "media-src", "connect-src"}:
            assert set(fuentes) <= {"'self'", "'none'"}, (nombre, fuentes)
    assert valor_unico(respuesta, CSP) == csp_esperada(ALMACEN)


@pytest.mark.parametrize("ruta", [RUTA_TOKEN, RUTA_INEXISTENTE], ids=["200", "404"])
def test_tkt057_ca14_esc1_ninguna_directiva_admite_comodin_ni_inline_ni_eval(ruta: str) -> None:
    """TC-60 · CA-14 esc. 1 · RNF-06 — rechazo: sin `*`, sin `unsafe-inline`, sin `unsafe-eval`; `object-src 'none'`."""
    politica_completa = valor_unico(cliente_sin_base(ALMACEN).get(ruta), CSP)

    assert "*" not in politica_completa
    assert "unsafe-inline" not in politica_completa
    assert "unsafe-eval" not in politica_completa
    assert directivas(politica_completa)["object-src"] == ["'none'"]
    assert directivas(politica_completa)["frame-ancestors"] == ["'none'"]


# --------------------------------------------------------------------------- TC-61


@pytest.mark.parametrize("ruta", [RUTA_TOKEN, RUTA_INEXISTENTE], ids=["200", "404"])
def test_tkt057_ca14_esc2_sin_almacen_ninguna_directiva_admite_un_origen_externo(ruta: str) -> None:
    """TC-61 · CA-14 esc. 2 · RNF-06 — rechazo: sin la variable, todo valor es `'self'` o `'none'`.

    La política existe y trae las directivas de recursos (no se cumple por vacuidad), y ninguna lleva el
    origen del almacén ni otro host.
    """
    respuesta = cliente_sin_base(None).get(ruta)

    politica = politica_de(respuesta)
    assert {"img-src", "media-src", "connect-src", "object-src"} <= set(politica)
    for nombre, fuentes in politica.items():
        assert fuentes, f"La directiva {nombre} no tiene fuentes."
        assert set(fuentes) <= {"'self'", "'none'"}, (nombre, fuentes)
    assert valor_unico(respuesta, CSP) == csp_esperada(None)
    assert "almacen" not in valor_unico(respuesta, CSP)


# --------------------------------------------------------------------------- TC-62


@pytest.mark.parametrize(
    ("nombre", "esperado", "rebajado"),
    [
        pytest.param(CACHE, VALOR_CACHE, "public, max-age=3600", id="cache_control"),
        pytest.param(CSP, csp_esperada(None), "default-src *", id="content_security_policy"),
        pytest.param(HSTS, VALOR_HSTS, "max-age=0", id="hsts"),
        pytest.param(NOSNIFF, VALOR_NOSNIFF, "sniff", id="x_content_type_options"),
        pytest.param(REFERRER, VALOR_REFERRER, "unsafe-url", id="referrer_policy"),
    ],
)
def test_tkt057_ca13_una_ruta_no_puede_rebajar_las_cabeceras_del_middleware(
    nombre: str, esperado: str, rebajado: str
) -> None:
    """TC-62 · CA-13 · RNF-06 — rechazo: la ruta que fija su propia cabecera sale con una sola, la del middleware.

    Una ruta bajo `/api/` fija `Cache-Control: public`, su `Content-Security-Policy` y las otras tres
    cabeceras con valores más laxos. Cada una llega al cliente una sola vez y con el valor del middleware:
    ni duplicada ni rebajada.
    """
    respuesta = cliente_sin_base(None).get(RUTA_QUE_REBAJA)

    assert respuesta.status_code == 200
    assert valor_unico(respuesta, nombre) == esperado
    assert rebajado not in respuesta.headers.get_list(nombre)


def test_tkt057_ca13_el_middleware_quita_sin_distinguir_mayusculas_y_conserva_las_ajenas() -> None:
    """TC-62 · CA-13 — rechazo: nombres en mayúsculas y minúsculas mezcladas también se reemplazan.

    ASGI puro, sin Starlette de por medio (que ya pasa los nombres a minúsculas): la aplicación interna
    envía `Cache-Control`, `CONTENT-security-policy` y `strict-transport-security` con mayúsculas
    arbitrarias, más una cabecera ajena que debe conservarse.
    """
    from servidor.cabeceras import MiddlewareCabecerasSeguridad, cabeceras_de_seguridad

    async def interna(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"Cache-Control", b"public"),
                    (b"CONTENT-security-policy", b"default-src *"),
                    (b"strict-transport-security", b"max-age=0"),
                    (b"X-Ajena", b"1"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    fijas = cabeceras_de_seguridad(None)
    middleware = MiddlewareCabecerasSeguridad(interna, cabeceras=fijas + ((CACHE, VALOR_CACHE),))
    mensajes: list[dict[str, Any]] = []

    async def recibir() -> MutableMapping[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def enviar(mensaje: MutableMapping[str, Any]) -> None:
        mensajes.append(dict(mensaje))

    alcance = {"type": "http", "method": "GET", "path": "/api/v1/x", "headers": []}
    asyncio.run(middleware(alcance, recibir, enviar))

    inicio = next(m for m in mensajes if m["type"] == "http.response.start")
    cabeceras = [(k.decode().lower(), v.decode()) for k, v in inicio["headers"]]
    nombres = [k for k, _ in cabeceras]
    for nombre in (CACHE, CSP, HSTS):
        assert nombres.count(nombre.lower()) == 1, (nombre, cabeceras)
    assert dict(cabeceras)[CSP.lower()] == csp_esperada(None)
    assert dict(cabeceras)[HSTS.lower()] == VALOR_HSTS
    assert dict(cabeceras)["x-ajena"] == "1"


# --------------------------------------------------------------------------- fuera de /api/


def test_tkt057_ca13_cache_control_no_se_anade_fuera_de_api() -> None:
    """CA-13 — rechazo: `/openapi.json` lleva las cuatro cabeceras pero no `Cache-Control`.

    `Cache-Control: no-store` es solo de las rutas que empiezan por `/api/`; las otras respuestas no lo
    reciben del middleware.
    """
    respuesta = cliente_sin_base(None).get(RUTA_OPENAPI)

    assert respuesta.status_code == 200
    exigir_cabeceras_fijas(respuesta)
    assert respuesta.headers.get_list(CACHE) == []


# --------------------------------------------------------------------------- TC-63


def test_tkt057_car8_el_500_conserva_la_correlacion_y_su_cuerpo_de_tkt005() -> None:
    """TC-63 · CA-R8 · CA-10 de TKT-005 — regresión: el `500` sigue trayendo su cuerpo y `X-Correlacion-Id`.

    La cabecera es un UUID v4 único y coincide con `correlacion_id` del cuerpo; el cuerpo tiene solo
    `mensaje` y `correlacion_id`, con el texto de TKT-005, y ni la traza ni el nombre de la excepción ni su
    mensaje llegan al cliente. Nace en verde: es lo que el manejador del `500` ya hace y no debe perderse
    al añadirle las cabeceras de seguridad.
    """
    respuesta = cliente_sin_base(None).get(RUTA_QUE_EXPLOTA)

    assert respuesta.status_code == 500
    identificador = valor_unico(respuesta, CABECERA_CORRELACION)
    assert uuid.UUID(identificador).version == 4
    cuerpo = respuesta.json()
    assert cuerpo == {"mensaje": MENSAJE_ERROR_NO_CONTROLADO, "correlacion_id": identificador}
    for filtrado in ("RuntimeError", DETALLE_INTERNO, "Traceback", "explota"):
        assert filtrado not in respuesta.text


# --------------------------------------------------------------------------- el módulo y la fábrica


def test_tkt057_ca13_cabeceras_de_seguridad_trae_las_cuatro_fijas_sin_cache_control() -> None:
    """CA-13 · CA-14 — `cabeceras_de_seguridad(None)` y con almacén: las cuatro fijas, sin `Cache-Control`."""
    from servidor.cabeceras import cabeceras_de_seguridad

    sin_almacen = cabeceras_de_seguridad(None)
    con_almacen = cabeceras_de_seguridad(ALMACEN)

    assert {k.lower(): v for k, v in sin_almacen} == {
        HSTS.lower(): VALOR_HSTS,
        NOSNIFF.lower(): VALOR_NOSNIFF,
        REFERRER.lower(): VALOR_REFERRER,
        CSP.lower(): csp_esperada(None),
    }
    assert {k.lower(): v for k, v in con_almacen}[CSP.lower()] == csp_esperada(ALMACEN)
    assert len(sin_almacen) == len(con_almacen) == 4


@pytest.mark.parametrize(
    ("ruta", "lleva_no_store"),
    [
        pytest.param("/api/v1/sesion/csrf", True, id="api_v1"),
        pytest.param("/api/", True, id="api_raiz"),
        pytest.param("/openapi.json", False, id="openapi"),
        pytest.param("/", False, id="raiz"),
        pytest.param("/apiario", False, id="prefijo_sin_barra"),
    ],
)
def test_tkt057_ca13_cabeceras_para_ruta_anade_no_store_solo_bajo_api(
    ruta: str, lleva_no_store: bool
) -> None:
    """CA-13 — rechazo: `cabeceras_para_ruta` suma `Cache-Control: no-store` solo si la ruta empieza por `/api/`."""
    from servidor.cabeceras import cabeceras_de_seguridad, cabeceras_para_ruta

    fijas = cabeceras_de_seguridad(None)

    resultado = {k.lower(): v for k, v in cabeceras_para_ruta(ruta, fijas)}

    assert {k.lower(): v for k, v in fijas}.items() <= resultado.items()
    if lleva_no_store:
        assert resultado[CACHE.lower()] == VALOR_CACHE
    else:
        assert CACHE.lower() not in resultado


@pytest.mark.parametrize("almacen", [None, ALMACEN], ids=["sin_almacen", "con_almacen"])
def test_tkt057_ca13_la_fabrica_guarda_las_cabeceras_en_el_estado_de_la_aplicacion(
    almacen: str | None,
) -> None:
    """CA-13 — `aplicacion.state.cabeceras_seguridad` guarda las cuatro fijas, para el manejador del `500`."""
    guardadas = aplicacion_sin_base(almacen).state.cabeceras_seguridad

    assert {k.lower(): v for k, v in guardadas} == {
        HSTS.lower(): VALOR_HSTS,
        NOSNIFF.lower(): VALOR_NOSNIFF,
        REFERRER.lower(): VALOR_REFERRER,
        CSP.lower(): csp_esperada(almacen),
    }
