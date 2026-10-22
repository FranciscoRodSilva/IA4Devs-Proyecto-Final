"""Enrutador y lista cerrada de rutas sin sesión (TKT-006, fila 7, tanda 2): TC-47 a TC-53, sin Docker.

`CA-14` pide que ninguna ruta del producto quede sin sesión por descuido. La prueba recorre el
enrutador de la aplicación real, baja por cada `APIRoute` hasta su cadena de dependencias y compara
las rutas cuya cadena **no** contiene `sesion_vigente` con una lista cerrada de dos entradas:
`GET /api/v1/sesion/csrf` y `POST /api/v1/sesion`. Una ruta nueva sin protección rompe la prueba y
la nombra; quitar una entrada de la lista, también.

Sin Docker (`CA-R4`). La aplicación es `crear_aplicacion(destino_registro=..., entorno={})` y no
recibe motor: el motor del rol de aplicación es perezoso, así que construirla no abre conexión. Cada
caso borra del entorno las variables `CIMENTA_DB_*` antes de construirla: si una ruta de las que aquí
se ejercen intentara crear el motor, `leer_variable` lanzaría y la respuesta sería `500`.

Los símbolos de producción se importan **dentro de cada caso o de cada ayuda**: mientras no existan,
cada caso falla con su propio error y la recolección no se cae.

Las ayudas `rutas_de` y `corrutinas_registradas` son las de `test_servidor_arranque.py` (TKT-005),
copiadas aquí como hace `test_tkt007_consulta.py`. Desde FastAPI 0.159 `include_router` deja una ruta
perezosa con `original_router`: sin bajar por ella no se vería ninguna ruta de un enrutador incluido.

Límite conocido del recorrido: lee `original_router.routes` y no el contexto de la inclusión, así que
una ruta montada con `include_router(prefix=...)` se nombra sin ese prefijo, y una protegida solo por
`include_router(dependencies=[...])` se cuenta como sin proteger. Los dos errores caen del lado
seguro (la prueba falla), nunca dejan pasar una ruta abierta.
"""

import functools
import inspect
import io
import os
import re
import uuid
from collections.abc import Callable, Iterable, Iterator
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import Annotated, Any

import pytest
import yaml
from fastapi import APIRouter, Cookie, Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from starlette.applications import Starlette
from starlette.routing import BaseRoute

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_CSRF = "/api/v1/sesion/csrf"
COOKIE_CSRF = "cimenta_csrf"
COOKIE_SESION = "cimenta_sesion"
TOKEN_URL_SEGURO = re.compile(r"[A-Za-z0-9_-]+")

# La lista cerrada de `CA-14`: las dos únicas rutas del producto que se atienden sin sesión.
LISTA_CERRADA = frozenset({"GET /api/v1/sesion/csrf", "POST /api/v1/sesion"})

# Las cuatro rutas de identidad y su `operationId` del borrador.
RUTAS_DE_IDENTIDAD = frozenset(
    {
        "GET /api/v1/sesion/csrf",
        "POST /api/v1/sesion",
        "GET /api/v1/sesion",
        "POST /api/v1/sesion/cierre",
    }
)
FUNCIONES_DE_IDENTIDAD = frozenset(
    {"obtener_token_csrf", "iniciar_sesion", "obtener_sesion_actual", "cerrar_sesion"}
)
# Rutas que FastAPI registra por sí mismo y que no son `APIRoute`.
RUTAS_DEL_MARCO = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})

SIN_PROTEGER = "sin proteger: "
FUERA_DE_LA_LISTA = "en la lista pero protegida o inexistente: "
NO_INSPECCIONABLE = "no inspeccionable: "


# --------------------------------------------------------------------------- ayudas de la prueba


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def construir_aplicacion(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """La aplicación real con `identidad` montada, sin motor y sin variables de base en el entorno."""
    for nombre in [n for n in os.environ if n.startswith("CIMENTA_DB_")]:
        monkeypatch.delenv(nombre)
    from servidor.fabrica import crear_aplicacion

    return crear_aplicacion(destino_registro=io.StringIO(), entorno={})


def cliente_de(aplicacion: FastAPI) -> TestClient:
    """Cliente HTTPS: con `http://`, httpx no devolvería una cookie `Secure`."""
    return TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido (ayuda de TKT-005)."""
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from rutas_de(original.routes)
        elif isinstance(ruta, APIRoute):
            yield ruta


def rutas_no_inspeccionables(rutas: Iterable[BaseRoute]) -> list[str]:
    """«Tipo ruta» de lo registrado que no es una `APIRoute` ni una de las rutas del marco.

    Un `Mount` o una `Route` suelta no tienen `dependant`: el recorrido no puede decir si exigen
    sesión, y callarlo dejaría pasar una ruta abierta.
    """
    resultado: list[str] = []
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            resultado += rutas_no_inspeccionables(original.routes)
            continue
        camino = getattr(ruta, "path", "?")
        if not isinstance(ruta, APIRoute) and camino not in RUTAS_DEL_MARCO:
            resultado.append(f"{type(ruta).__name__} {camino}")
    return resultado


def operaciones_de(ruta: APIRoute) -> set[str]:
    """«MÉTODO ruta» de cada método que atiende la ruta."""
    return {f"{metodo} {ruta.path}" for metodo in ruta.methods or ()}


def llamadas(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    """Cada `call` de la cadena de dependencias de una ruta, bajando por las sub-dependencias."""
    for sub in dependant.dependencies:
        if sub.call is not None:
            yield sub.call
        yield from llamadas(sub)


def rutas_sin_sesion(aplicacion: FastAPI) -> set[str]:
    """«MÉTODO ruta» de cada `APIRoute` cuya cadena de llamadas no contiene `sesion_vigente`."""
    from cimenta.identidad.api.dependencias import sesion_vigente

    return {
        operacion
        for ruta in rutas_de(aplicacion.routes)
        if not any(llamada is sesion_vigente for llamada in llamadas(ruta.dependant))
        for operacion in operaciones_de(ruta)
    }


def violaciones(aplicacion: FastAPI, lista_cerrada: Iterable[str]) -> list[str]:
    """Lo que sobra y lo que falta respecto de la lista cerrada, más lo que no se puede inspeccionar."""
    cerrada = set(lista_cerrada)
    sin_sesion = rutas_sin_sesion(aplicacion)
    return [
        *(f"{SIN_PROTEGER}{ruta}" for ruta in sorted(sin_sesion - cerrada)),
        *(f"{FUERA_DE_LA_LISTA}{ruta}" for ruta in sorted(cerrada - sin_sesion)),
        *(f"{NO_INSPECCIONABLE}{ruta}" for ruta in rutas_no_inspeccionables(aplicacion.routes)),
    ]


def corrutinas_registradas(aplicacion: FastAPI) -> list[str]:
    """Nombres de las rutas y de los manejadores propios declarados con `async def` (ayuda de TKT-005)."""
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


def dependencias_corrutina(aplicacion: FastAPI) -> list[str]:
    """Funciones `async def` de la cadena de dependencias de alguna ruta.

    Solo funciones: `APIKeyCookie` es un objeto del marco con un `__call__` asíncrono sin E/S, y no
    cuenta. Una dependencia propia `async def` correría en el bucle de eventos y bloquearía con su
    llamada a SQLAlchemy síncrono (ADR-013).
    """
    return sorted(
        {
            llamada.__name__
            for ruta in rutas_de(aplicacion.routes)
            for llamada in llamadas(ruta.dependant)
            if inspect.isfunction(llamada) and inspect.iscoroutinefunction(llamada)
        }
    )


def ruta_sin_sesion_de_prueba() -> dict[str, bool]:
    return {"ok": True}


def enrutador_de_prueba(ruta: str, **opciones: Any) -> APIRouter:
    """Un enrutador con un único `GET` síncrono en `ruta`; `opciones` van a `add_api_route`."""
    enrutador = APIRouter()
    enrutador.add_api_route(ruta, ruta_sin_sesion_de_prueba, methods=["GET"], **opciones)
    return enrutador


def cookies_fijadas(respuesta: Any) -> list[tuple[str, Morsel[str]]]:
    """Cada `Set-Cookie` de la respuesta, interpretado con la biblioteca estándar."""
    resultado: list[tuple[str, Morsel[str]]] = []
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        resultado.extend(galleta.items())
    return resultado


def una_cookie(respuesta: Any, nombre: str) -> Morsel[str]:
    """La única cookie con ese nombre que fija la respuesta; dos o ninguna es un fallo."""
    encontradas = [morsel for clave, morsel in cookies_fijadas(respuesta) if clave == nombre]
    assert len(encontradas) == 1, (
        f"Se esperaba exactamente un Set-Cookie de {nombre}; hay {len(encontradas)}: "
        f"{respuesta.headers.get_list('set-cookie')}"
    )
    return encontradas[0]


# --------------------------------------------------------------------------- TC-47


def test_tkt006_ca14_la_lista_cerrada_coincide_con_el_enrutador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-47 · CA-14 esc. 1 — las rutas sin `sesion_vigente` son exactamente las dos de la lista cerrada.

    Anti-verde vacío: el recorrido encuentra las cuatro rutas de identidad y sus cuatro funciones;
    sin ellas, `violaciones == []` podría cumplirse por no haber recorrido nada.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    recorridas = {
        operacion for ruta in rutas_de(aplicacion.routes) for operacion in operaciones_de(ruta)
    }
    assert recorridas >= RUTAS_DE_IDENTIDAD
    assert {
        ruta.endpoint.__name__ for ruta in rutas_de(aplicacion.routes)
    } >= FUNCIONES_DE_IDENTIDAD
    encontradas = violaciones(aplicacion, LISTA_CERRADA)
    assert encontradas == [], "Rutas fuera de la lista cerrada de CA-14:\n" + "\n".join(encontradas)
    assert rutas_sin_sesion(aplicacion) == LISTA_CERRADA


# --------------------------------------------------------------------------- TC-48


def test_tkt006_ca14_una_ruta_nueva_sin_proteger_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-48 · CA-14 esc. 2 — una ruta nueva sin `sesion_vigente` rompe la prueba y se nombra.

    La violación es exactamente una: la de la ruta de prueba, con su método y su ruta.
    """
    aplicacion = construir_aplicacion(monkeypatch)
    aplicacion.include_router(enrutador_de_prueba("/api/v1/prueba/sin-sesion"))

    assert violaciones(aplicacion, LISTA_CERRADA) == [
        f"{SIN_PROTEGER}GET /api/v1/prueba/sin-sesion"
    ]


def test_tkt006_ca14_una_ruta_con_otra_dependencia_no_cuenta_como_protegida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-14 esc. 2 — una dependencia que no es `sesion_vigente` (la cookie leída con `Cookie()`) no protege.

    Es el caso de quien «protege» su ruta leyendo la cookie a mano, como en MT-15.
    """

    def leer_cookie_a_mano(cimenta_sesion: Annotated[str | None, Cookie()] = None) -> None:
        return None

    aplicacion = construir_aplicacion(monkeypatch)
    aplicacion.include_router(
        enrutador_de_prueba(
            "/api/v1/prueba/cookie-a-mano", dependencies=[Depends(leer_cookie_a_mano)]
        )
    )

    assert violaciones(aplicacion, LISTA_CERRADA) == [
        f"{SIN_PROTEGER}GET /api/v1/prueba/cookie-a-mano"
    ]


def test_tkt006_ca14_una_ruta_que_no_es_apiroute_se_reporta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-14 — un `Mount` no tiene cadena de dependencias: se reporta, no se calla.

    Sin esto, `aplicacion.mount("/x", ...)` abriría una ruta sin sesión que el recorrido no vería.
    """
    aplicacion = construir_aplicacion(monkeypatch)
    aplicacion.mount("/estatico", Starlette())

    assert violaciones(aplicacion, LISTA_CERRADA) == [f"{NO_INSPECCIONABLE}Mount /estatico"]


@pytest.mark.parametrize("forma", ["en_el_decorador", "en_un_parametro", "en_una_sub_dependencia"])
def test_tkt006_ca14_una_ruta_con_sesion_vigente_cuenta_como_protegida(
    monkeypatch: pytest.MonkeyPatch, forma: str
) -> None:
    """CA-14 — `sesion_vigente` protege venga como venga: en el decorador, en un parámetro o dentro de otra dependencia.

    La tercera forma es la de `exigir_rol` (fila 10): la ruta depende de una función que a su vez
    depende de `sesion_vigente`. Sin bajar por `dependant.dependencies` recursivamente, saldría como
    ruta abierta. Es el anti-falso-positivo del recorrido.
    """
    from cimenta.identidad.api.dependencias import sesion_vigente

    aplicacion = construir_aplicacion(monkeypatch)

    def pasarela(usuario: Annotated[Any, Depends(sesion_vigente)]) -> None:
        return None

    def ruta_con_parametro(usuario: Annotated[Any, Depends(sesion_vigente)]) -> dict[str, bool]:
        return {"ok": True}

    enrutador = APIRouter()
    camino = f"/api/v1/prueba/protegida-{forma}"
    if forma == "en_el_decorador":
        enrutador.add_api_route(
            camino,
            ruta_sin_sesion_de_prueba,
            methods=["GET"],
            dependencies=[Depends(sesion_vigente)],
        )
    elif forma == "en_un_parametro":
        enrutador.add_api_route(camino, ruta_con_parametro, methods=["GET"])
    else:
        enrutador.add_api_route(
            camino, ruta_sin_sesion_de_prueba, methods=["GET"], dependencies=[Depends(pasarela)]
        )
    aplicacion.include_router(enrutador)

    assert violaciones(aplicacion, LISTA_CERRADA) == []
    assert f"GET {camino}" in {
        operacion for ruta in rutas_de(aplicacion.routes) for operacion in operaciones_de(ruta)
    }


# --------------------------------------------------------------------------- TC-49


def test_tkt006_ca14_una_ruta_de_la_lista_pierde_su_excepcion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-49 · CA-14 esc. 3 — quitar una ruta de la lista cerrada rompe la prueba y la nombra.

    Con `GET /api/v1/sesion/csrf` fuera de la lista, la ruta queda como «sin proteger». Es lo que
    hace falta para que una de las dos excepciones no se pueda retirar sin que alguien lo decida.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    resultado = violaciones(aplicacion, LISTA_CERRADA - {"GET /api/v1/sesion/csrf"})

    assert resultado == [f"{SIN_PROTEGER}GET /api/v1/sesion/csrf"]


def test_tkt006_ca14_una_entrada_inventada_en_la_lista_se_reporta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-49 · CA-14 esc. 3 — una entrada de la lista que no existe se nombra como «en la lista pero … inexistente»."""
    aplicacion = construir_aplicacion(monkeypatch)

    resultado = violaciones(aplicacion, LISTA_CERRADA | {"GET /api/v1/no-existe"})

    assert resultado == [f"{FUERA_DE_LA_LISTA}GET /api/v1/no-existe"]


def test_tkt006_ca14_una_ruta_protegida_en_la_lista_se_reporta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-14 esc. 3 — listar una ruta que sí exige sesión es una excepción de más: se nombra.

    Sin este caso, ampliar la lista para «hacer pasar» una ruta protegida no dejaría rastro.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    resultado = violaciones(aplicacion, LISTA_CERRADA | {"GET /api/v1/sesion"})

    assert resultado == [f"{FUERA_DE_LA_LISTA}GET /api/v1/sesion"]


# --------------------------------------------------------------------------- TC-50


def test_tkt006_ca01_token_csrf_sin_sesion(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-50 · CA-1 esc. 1 · M1 — 200 con `TokenCsrf`, cookie `cimenta_csrf` igual al cuerpo y sin `HttpOnly`.

    Sin Docker y sin variables de base: el camino del token no toca la base. La cookie lleva
    `Secure`, `SameSite=Lax` y `Path=/`, y no `HttpOnly`, porque el cliente la lee para reenviarla
    en `X-CSRF-Token` (doble envío). La respuesta lleva `X-Correlacion-Id`.
    """
    cliente = cliente_de(construir_aplicacion(monkeypatch))
    assert len(cliente.cookies) == 0

    respuesta = cliente.get(RUTA_CSRF)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/json")
    assert uuid.UUID(respuesta.headers[CABECERA]).version == 4
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
    assert [clave for clave, _ in cookies_fijadas(respuesta)] == [COOKIE_CSRF]


# --------------------------------------------------------------------------- TC-51


def test_tkt006_ca01_los_tokens_no_se_repiten(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-51 · CA-1 esc. 2 — dos emisiones seguidas dan tokens distintos, y cien no repiten ninguno.

    La segunda petición ya lleva la cookie de la primera: aun así el servidor emite uno nuevo. Cada
    token coincide con su propia cookie y cumple el mínimo del esquema.
    """
    cliente = cliente_de(construir_aplicacion(monkeypatch))

    primera = cliente.get(RUTA_CSRF)
    segunda = cliente.get(RUTA_CSRF)
    assert primera.json()["token"] != segunda.json()["token"]
    assert una_cookie(primera, COOKIE_CSRF).value == primera.json()["token"]
    assert una_cookie(segunda, COOKIE_CSRF).value == segunda.json()["token"]

    tokens: list[str] = []
    for _ in range(100):
        respuesta = cliente.get(RUTA_CSRF)
        assert respuesta.status_code == 200
        token = respuesta.json()["token"]
        assert len(token) >= 32
        assert una_cookie(respuesta, COOKIE_CSRF).value == token
        tokens.append(token)
    assert len(set(tokens)) == 100


# --------------------------------------------------------------------------- TC-52


def test_tkt006_ca07_el_contrato_publica_la_seguridad_de_sesion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-52 · CA-7 · M7 — `/openapi.json` declara el esquema `sesion` y `GET /api/v1/sesion` lo exige.

    `components.securitySchemes.sesion` es `apiKey` en `cookie` llamada `cimenta_sesion`, como el
    borrador. Lo exigen `GET /api/v1/sesion` y `POST /api/v1/sesion/cierre`; no lo declaran las dos
    rutas de la lista cerrada. El `csrf` del borrador es de TKT-057 y aquí no se afirma.
    """
    cliente = cliente_de(construir_aplicacion(monkeypatch))

    respuesta = cliente.get("/openapi.json")

    assert respuesta.status_code == 200
    contrato = respuesta.json()
    esquema = contrato["components"]["securitySchemes"]["sesion"]
    assert {clave: esquema[clave] for clave in ("type", "in", "name")} == {
        "type": "apiKey",
        "in": "cookie",
        "name": COOKIE_SESION,
    }
    declaradas = {
        f"{metodo.upper()} {ruta}": operacion
        for ruta, elemento in contrato["paths"].items()
        for metodo, operacion in elemento.items()
    }
    assert set(declaradas) >= RUTAS_DE_IDENTIDAD
    exigen_sesion = {
        clave
        for clave in RUTAS_DE_IDENTIDAD
        if any("sesion" in requisito for requisito in declaradas[clave].get("security", []))
    }
    assert exigen_sesion == {"GET /api/v1/sesion", "POST /api/v1/sesion/cierre"}


def test_tkt006_ca07_los_operation_id_coinciden_con_el_borrador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-52 · M7 — cada ruta de identidad publica el `operationId` de su operación en el borrador.

    El borrador es el contrato que se implementa: el cliente TypeScript se genera de los
    `operationId`, y un nombre distinto cambiaría la función que generan.
    """
    esperados = {
        f"{metodo.upper()} /api/v1{ruta}": operacion["operationId"]
        for ruta, elemento in borrador()["paths"].items()
        for metodo, operacion in elemento.items()
        if metodo in {"get", "post"} and "TKT-006" in operacion.get("x-tickets", [])
    }
    assert set(esperados) == RUTAS_DE_IDENTIDAD  # anti-verde vacío: el borrador tiene las cuatro
    cliente = cliente_de(construir_aplicacion(monkeypatch))

    contrato = cliente.get("/openapi.json").json()

    publicados = {
        f"{metodo.upper()} {ruta}": operacion["operationId"]
        for ruta, elemento in contrato["paths"].items()
        for metodo, operacion in elemento.items()
        if f"{metodo.upper()} {ruta}" in RUTAS_DE_IDENTIDAD
    }
    assert publicados == esperados


# --------------------------------------------------------------------------- TC-53


def test_tkt006_car6_rutas_de_identidad_sincronas(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-53 · CA-R6 — ninguna ruta ni manejador es `async def` y las cuatro funciones de identidad están en el recorrido.

    Regla 11 de CLAUDE.md: SQLAlchemy es síncrono y una corrutina con una llamada bloqueante congela
    el bucle entero. Las cuatro funciones, además, son funciones y no objetos invocables.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    de_identidad = [
        ruta
        for ruta in rutas_de(aplicacion.routes)
        if ruta.endpoint.__name__ in FUNCIONES_DE_IDENTIDAD
    ]
    assert {ruta.endpoint.__name__ for ruta in de_identidad} == FUNCIONES_DE_IDENTIDAD
    assert all(inspect.isfunction(ruta.endpoint) for ruta in de_identidad)
    assert corrutinas_registradas(aplicacion) == []
    assert dependencias_corrutina(aplicacion) == []


def test_tkt006_car6_el_recorrido_detecta_una_corrutina_y_una_dependencia_asincrona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-R6 — oráculo de TC-53: una ruta `async def` y una dependencia `async def` se detectan y se nombran.

    Sin este caso, `corrutinas_registradas(...) == []` podría cumplirse porque el recorrido no ve
    nada. La dependencia asíncrona se añade a la cadena de una ruta síncrona.
    """

    async def ruta_asincrona_de_prueba() -> dict[str, bool]:
        return {"ok": True}

    async def dependencia_asincrona_de_prueba() -> None:
        return None

    aplicacion = construir_aplicacion(monkeypatch)
    enrutador = APIRouter()
    enrutador.add_api_route("/api/v1/prueba/asincrona", ruta_asincrona_de_prueba, methods=["GET"])
    enrutador.add_api_route(
        "/api/v1/prueba/dependencia-asincrona",
        ruta_sin_sesion_de_prueba,
        methods=["GET"],
        dependencies=[Depends(dependencia_asincrona_de_prueba)],
    )
    aplicacion.include_router(enrutador)

    assert corrutinas_registradas(aplicacion) == ["ruta_asincrona_de_prueba"]
    assert dependencias_corrutina(aplicacion) == ["dependencia_asincrona_de_prueba"]


# --------------------------------------------------------------------------- TC-65 (fila 10, entrega B)

# Los casos que siguen son de la entrega B (`exigir_rol` y la interfaz publicada) y no necesitan Docker.
# Importan `exigir_rol` **desde `cimenta.identidad.interfaz`**, que es lo que importará cualquier otro
# módulo; mientras no lo publique, cada uno falla con su propio `ImportError`.


@pytest.mark.parametrize("forma", ["en_el_decorador", "en_un_parametro"])
def test_tkt006_ca14_una_ruta_con_exigir_rol_cuenta_como_protegida(
    monkeypatch: pytest.MonkeyPatch, forma: str
) -> None:
    """TC-65 · CA-14 — una ruta protegida con `exigir_rol` no aparece en `violaciones`, venga como venga.

    `exigir_rol` se apoya en `sesion_vigente`: la cadena de la ruta contiene `comprobar_rol` y, debajo,
    `sesion_vigente`. El recorrido recursivo de TC-47 tiene que verla; si `exigir_rol` leyera la cookie por
    su cuenta, la ruta saldría como «sin proteger». Anti-verde vacío: la ruta sí está en el recorrido y
    la `sesion_vigente` de la cadena es la de `cimenta.identidad.api.dependencias`.
    """
    from cimenta.identidad.api.dependencias import sesion_vigente as de_dependencias
    from cimenta.identidad.interfaz import exigir_rol, sesion_vigente

    assert sesion_vigente is de_dependencias
    aplicacion = construir_aplicacion(monkeypatch)
    camino = f"/api/v1/prueba/con-rol-{forma}"
    enrutador = APIRouter()
    if forma == "en_el_decorador":
        enrutador.add_api_route(
            camino,
            ruta_sin_sesion_de_prueba,
            methods=["GET"],
            dependencies=[Depends(exigir_rol("COMPRAS"))],
        )
    else:

        def ruta_con_parametro(
            usuario: Annotated[Any, Depends(exigir_rol("COMPRAS"))],
        ) -> dict[str, bool]:
            return {"ok": True}

        enrutador.add_api_route(camino, ruta_con_parametro, methods=["GET"])
    aplicacion.include_router(enrutador)

    assert violaciones(aplicacion, LISTA_CERRADA) == []
    assert f"GET {camino}" in {
        operacion for ruta in rutas_de(aplicacion.routes) for operacion in operaciones_de(ruta)
    }
    ruta = next(r for r in rutas_de(aplicacion.routes) if r.path == camino)
    assert sesion_vigente in list(llamadas(ruta.dependant))


def test_tkt006_ca14_exigir_rol_no_abre_una_ruta_sin_sesion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-65 · CA-14 — rechazo: con tres rutas de `exigir_rol` montadas, las rutas sin sesión siguen siendo las dos de la lista cerrada.

    Protege contra una implementación de `exigir_rol` que, al fallar la cookie, devolviera un usuario
    anónimo en vez de depender de `sesion_vigente`: la ruta saldría en `rutas_sin_sesion`.
    """
    from cimenta.identidad.interfaz import exigir_rol

    aplicacion = construir_aplicacion(monkeypatch)
    enrutador = APIRouter()
    for camino, roles in (
        ("/api/v1/prueba/compras", ("COMPRAS",)),
        ("/api/v1/prueba/almacen", ("ALMACEN",)),
        ("/api/v1/prueba/direccion", ("DIRECCION_GENERAL",)),
    ):
        enrutador.add_api_route(
            camino,
            ruta_sin_sesion_de_prueba,
            methods=["GET"],
            dependencies=[Depends(exigir_rol(*roles))],
        )
    aplicacion.include_router(enrutador)

    assert rutas_sin_sesion(aplicacion) == LISTA_CERRADA


# --------------------------------------------------------------------------- TC-66


def test_tkt006_ca07_exigir_rol_mal_declarado_falla_al_declarar() -> None:
    """TC-66 · M7 — rechazo: `exigir_rol()` sin roles y con un rol que no existe fallan al declarar la ruta, no en la petición.

    Sin roles: `ValueError` con «al menos un rol». Con `GERENTE`, que no está entre los seis de `Rol`:
    `ValueError` que nombra `GERENTE`. Un error de declaración tiene que salir al arrancar la aplicación.
    """
    from cimenta.identidad.interfaz import exigir_rol

    with pytest.raises(ValueError, match="al menos un rol"):
        exigir_rol()
    with pytest.raises(ValueError, match="GERENTE"):
        exigir_rol("GERENTE")


@pytest.mark.parametrize(
    "roles",
    [
        ("compras",),
        ("Compras",),
        ("",),
        (" COMPRAS",),
        ("COMPRAS", "GERENTE"),
        ("GERENTE", "COMPRAS"),
    ],
    ids=[
        "minusculas",
        "capitalizado",
        "vacio",
        "con_espacio",
        "valido_e_invalido",
        "invalido_y_valido",
    ],
)
def test_tkt006_ca07_exigir_rol_rechaza_cualquier_nombre_que_no_sea_un_rol_exacto(
    roles: tuple[str, ...],
) -> None:
    """TC-66 · M7 — rechazo: un nombre que no es exactamente uno de los seis valores de `Rol` falla, aunque otro sea válido.

    La comparación de roles es por cadena exacta: `compras` no es `COMPRAS`, y un rol inválido no se
    tolera por ir junto a uno válido.
    """
    from cimenta.identidad.interfaz import exigir_rol

    with pytest.raises(ValueError):
        exigir_rol(*roles)


def test_tkt006_ca07_exigir_rol_acepta_los_seis_roles_del_contrato() -> None:
    """TC-66 · M7 — `exigir_rol` acepta cada uno de los seis roles de `contrato_error.Rol`, solo o todos juntos.

    Anti-verde vacío del rechazo: sin este caso, una `exigir_rol` que lanzara siempre pasaría TC-66.
    Devuelve una función invocable, que es lo que `Depends` necesita.
    """
    from cimenta.identidad.interfaz import exigir_rol
    from contrato_error import Rol

    claves = [rol.value for rol in Rol]
    assert len(claves) == 6
    for clave in claves:
        assert callable(exigir_rol(clave))
    assert callable(exigir_rol(*claves))


# --------------------------------------------------------------------------- CA-13 · interfaz publicada


def test_tkt006_ca13_la_interfaz_publica_exigir_rol_y_evaluar_resolucion() -> None:
    """CA-13 · M12 — `cimenta.identidad.interfaz` publica `exigir_rol` y `evaluar_resolucion`, y son los de sus capas.

    Un módulo solo habla con otro por su interfaz publicada: si estos nombres no están en `__all__` y
    como atributos del módulo, TKT-020, TKT-021 y TKT-026 tendrían que importar de `api/` o de `dominio/`
    y romperían el contrato de fronteras. `__all__` es exactamente el de seis nombres del diseño.
    """
    import cimenta.identidad.interfaz as interfaz
    from cimenta.identidad.api import dependencias
    from cimenta.identidad.aplicacion import contexto
    from cimenta.identidad.dominio import autorizacion
    from cimenta.identidad.interfaz import evaluar_resolucion, exigir_rol  # noqa: F401

    assert set(interfaz.__all__) == {
        "sesion_vigente",
        "exigir_rol",
        "UsuarioAutenticado",
        "evaluar_resolucion",
        "ResultadoResolucion",
        "MotivoNegacion",
    }
    assert all(hasattr(interfaz, nombre) for nombre in interfaz.__all__)
    assert interfaz.exigir_rol is dependencias.exigir_rol
    assert interfaz.sesion_vigente is dependencias.sesion_vigente
    assert interfaz.UsuarioAutenticado is contexto.UsuarioAutenticado
    assert interfaz.evaluar_resolucion is autorizacion.evaluar_resolucion
    assert interfaz.ResultadoResolucion is autorizacion.ResultadoResolucion
    assert interfaz.MotivoNegacion is autorizacion.MotivoNegacion


def test_tkt006_ca13_la_interfaz_se_importa_con_asterisco_y_se_documenta() -> None:
    """CA-13 · M12 — `from cimenta.identidad.interfaz import *` entrega los seis nombres, y el docstring dice cómo usarlos.

    El docstring nombra `exigir_rol`, `evaluar_resolucion` y `AUTO_RESOLUCION`: es la guía de quien
    escriba la siguiente ruta protegida o resuelva una solicitud (TKT-026).
    """
    import cimenta.identidad.interfaz as interfaz
    from cimenta.identidad.interfaz import exigir_rol  # noqa: F401

    espacio: dict[str, Any] = {}
    exec("from cimenta.identidad.interfaz import *", espacio)  # noqa: S102
    publicados = {nombre for nombre in espacio if not nombre.startswith("__")}
    assert publicados == set(interfaz.__all__)
    documento = interfaz.__doc__ or ""
    for nombre in ("exigir_rol", "evaluar_resolucion", "AUTO_RESOLUCION"):
        assert nombre in documento
