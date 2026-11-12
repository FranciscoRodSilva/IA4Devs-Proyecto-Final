"""Ninguna ruta de archivos es binaria (TKT-059, fila 16): TC-43.

ADR-016 y la regla 15 del proyecto: los archivos no pasan por el API. Las rutas son `def`, así que servir
un video retendría un hilo del grupo mientras dura la descarga; por eso el API solo entrega metadatos y una
URL prefirmada, y el servidor se aparta. Esta prueba lo comprueba sobre la aplicación real **sin base**
(solo la contraseña de aplicación, como en `test_servidor_arranque.py`): las rutas de archivos se publican
aunque no haya base ni almacén (CA-2, `TC-06`).

El conjunto esperado de rutas **sale del borrador OpenAPI**, no se escribe a mano: las operaciones bajo
`/archivos` con `TKT-059` en `x-tickets`. `crear_importacion` también cita `TKT-059`, pero cuelga de
`/obras/{obra_id}/importaciones` y es de TKT-018.

El comprobador es una función reutilizable que devuelve hallazgos con un código cada uno. El caso de
control (M-17) lo ejecuta sobre una aplicación con una ruta extra bajo `/api/v1/archivos` que transmite
bytes y exige que el hallazgo concreto aparezca. Un comprobador que solo mirase la `response_class`
declarada dejaría pasar la ruta que devuelve un `StreamingResponse` sin declararlo: por eso el comprobador
mira además la anotación de retorno, el contrato publicado en `/openapi.json` y la respuesta realmente
devuelta por una petición.

Sin base de datos ni Docker: nada de esta prueba abre una conexión.
"""

from __future__ import annotations

import inspect
import io
import json
import re
import secrets
import typing
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import APIRouter, FastAPI
from fastapi.datastructures import DefaultPlaceholder
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute, BaseRoute
from fastapi.testclient import TestClient

from cimenta.identidad.interfaz import verificar_origen

BORRADOR = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml"
PREFIJO = "/api/v1/archivos"
TICKET = "TKT-059"
METODOS_HTTP = ("get", "post", "put", "patch", "delete")
UUID_DE_SONDA = "00000000-0000-4000-8000-000000000059"
TIPO_JSON = "application/json"

# Códigos de los hallazgos del comprobador.
RUTA_NO_ESPERADA = "RUTA_NO_ESPERADA"
RUTA_FALTANTE = "RUTA_FALTANTE"
CORRUTINA = "CORRUTINA"
CLASE_NO_JSON = "CLASE_NO_JSON"
ANOTACION_BINARIA = "ANOTACION_BINARIA"
ANOTACION_ILEGIBLE = "ANOTACION_ILEGIBLE"
OPENAPI_AUSENTE = "OPENAPI_AUSENTE"
OPENAPI_BINARIO = "OPENAPI_BINARIO"
RESPUESTA_BINARIA = "RESPUESTA_BINARIA"
DEPENDENCIA_AUSENTE = "DEPENDENCIA_AUSENTE"
ORDEN_DE_DEPENDENCIAS = "ORDEN_DE_DEPENDENCIAS"


@dataclass(frozen=True, order=True)
class Operacion:
    """Una operación HTTP: método, ruta completa y `operationId`."""

    metodo: str
    ruta: str
    operacion_id: str


@dataclass(frozen=True)
class Hallazgo:
    """Un incumplimiento: qué código, en qué operación y el detalle para entender el fallo."""

    codigo: str
    metodo: str
    ruta: str
    detalle: str = ""


# --------------------------------------------------------------------------- el borrador


def operaciones_del_borrador() -> frozenset[Operacion]:
    """Las operaciones bajo `/archivos` cuyo `x-tickets` incluye `TKT-059`, con la ruta completa."""
    borrador = yaml.safe_load(BORRADOR.read_text(encoding="utf-8"))
    base = borrador["servers"][0]["url"].rstrip("/")
    operaciones: set[Operacion] = set()
    for ruta, elemento in borrador["paths"].items():
        completa = f"{base}{ruta}"
        if not _bajo_el_prefijo(completa):
            continue
        for metodo in METODOS_HTTP:
            operacion = elemento.get(metodo)
            if operacion is not None and TICKET in operacion.get("x-tickets", []):
                operaciones.add(Operacion(metodo.upper(), completa, operacion["operationId"]))
    return frozenset(operaciones)


def _bajo_el_prefijo(ruta: str) -> bool:
    return ruta == PREFIJO or ruta.startswith(f"{PREFIJO}/")


# --------------------------------------------------------------------------- el comprobador


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido.

    Desde FastAPI 0.159 `include_router` deja una ruta perezosa con el enrutador original en
    `original_router`: sin bajar por ella no se vería ninguna ruta de un módulo.
    """
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from rutas_de(original.routes)
        elif isinstance(ruta, APIRoute):
            yield ruta


def _metodos(ruta: APIRoute) -> list[str]:
    return sorted(ruta.methods or ())


def _operaciones_de(ruta: APIRoute) -> list[Operacion]:
    return [
        Operacion(metodo, ruta.path, ruta.operation_id or ruta.name) for metodo in _metodos(ruta)
    ]


def clase_efectiva(ruta: APIRoute) -> type[Response]:
    """La clase de respuesta que FastAPI usará: la del decorador o, si no hay, la del valor por omisión."""
    declarada = ruta.response_class
    if isinstance(declarada, DefaultPlaceholder):
        return typing.cast("type[Response]", declarada.value)
    return declarada


def _hallazgos_de_conjunto(
    rutas: list[APIRoute], esperadas: frozenset[Operacion]
) -> list[Hallazgo]:
    presentes = {operacion for ruta in rutas for operacion in _operaciones_de(ruta)}
    sobrantes = [
        Hallazgo(RUTA_NO_ESPERADA, o.metodo, o.ruta, o.operacion_id)
        for o in sorted(presentes - esperadas)
    ]
    faltantes = [
        Hallazgo(RUTA_FALTANTE, o.metodo, o.ruta, o.operacion_id)
        for o in sorted(esperadas - presentes)
    ]
    return sobrantes + faltantes


def _hallazgos_de_forma(ruta: APIRoute) -> list[Hallazgo]:
    """Corrutina y clase efectiva: lo que se ve en el objeto de la ruta."""
    hallazgos: list[Hallazgo] = []
    for operacion in _operaciones_de(ruta):
        if inspect.iscoroutinefunction(ruta.endpoint):
            hallazgos.append(
                Hallazgo(CORRUTINA, operacion.metodo, ruta.path, ruta.endpoint.__name__)
            )
        if clase_efectiva(ruta) is not JSONResponse:
            hallazgos.append(
                Hallazgo(CLASE_NO_JSON, operacion.metodo, ruta.path, clase_efectiva(ruta).__name__)
            )
    return hallazgos


def _hallazgos_de_anotacion(ruta: APIRoute) -> list[Hallazgo]:
    """La anotación de retorno no puede ser una respuesta distinta de la JSON (`StreamingResponse`…)."""
    try:
        retorno = typing.get_type_hints(ruta.endpoint).get("return")
    except (NameError, TypeError) as error:
        return [Hallazgo(ANOTACION_ILEGIBLE, m, ruta.path, repr(error)) for m in _metodos(ruta)]
    if (
        inspect.isclass(retorno)
        and issubclass(retorno, Response)
        and not issubclass(retorno, JSONResponse)
    ):
        return [Hallazgo(ANOTACION_BINARIA, m, ruta.path, retorno.__name__) for m in _metodos(ruta)]
    return []


def _hallazgos_de_openapi(ruta: APIRoute, publicado: dict[str, Any]) -> list[Hallazgo]:
    """En `/openapi.json` cada respuesta de la operación tiene solo `application/json`, y nada binario."""
    hallazgos: list[Hallazgo] = []
    for metodo in _metodos(ruta):
        operacion = publicado.get("paths", {}).get(ruta.path, {}).get(metodo.lower())
        if operacion is None:
            hallazgos.append(
                Hallazgo(OPENAPI_AUSENTE, metodo, ruta.path, "no está en /openapi.json")
            )
            continue
        for codigo, respuesta in operacion.get("responses", {}).items():
            tipos = set(respuesta.get("content", {}))
            if tipos - {TIPO_JSON}:
                hallazgos.append(
                    Hallazgo(OPENAPI_BINARIO, metodo, ruta.path, f"{codigo}: {sorted(tipos)}")
                )
        texto = json.dumps(operacion)
        if "octet-stream" in texto or '"format": "binary"' in texto:
            hallazgos.append(
                Hallazgo(OPENAPI_BINARIO, metodo, ruta.path, "octet-stream o format binary")
            )
    return hallazgos


def _hallazgos_de_respuesta(ruta: APIRoute, cliente: TestClient) -> list[Hallazgo]:
    """La respuesta realmente devuelta por una petición sin sesión: JSON, sin `Content-Disposition`.

    Es lo que pilla un `StreamingResponse` o un `FileResponse` que la ruta devuelve sin declararlo.
    """
    url = re.sub(r"\{[^}]+\}", UUID_DE_SONDA, ruta.path)
    hallazgos: list[Hallazgo] = []
    for metodo in _metodos(ruta):
        respuesta = cliente.request(metodo, url)
        tipo = respuesta.headers.get("content-type", "")
        if not tipo.startswith(TIPO_JSON) or "content-disposition" in respuesta.headers:
            hallazgos.append(
                Hallazgo(RESPUESTA_BINARIA, metodo, ruta.path, f"{respuesta.status_code} {tipo}")
            )
    return hallazgos


def _es_exigir_rol(llamable: Callable[..., Any]) -> bool:
    return getattr(llamable, "__qualname__", "").startswith("exigir_rol.<locals>.")


def _posicion(
    llamables: list[Callable[..., Any]], buscado: Callable[[Callable[..., Any]], bool]
) -> int | None:
    return next((i for i, llamable in enumerate(llamables) if buscado(llamable)), None)


def _hallazgos_de_dependencias(ruta: APIRoute, operacion: Operacion) -> list[Hallazgo]:
    """`POST`: `verificar_origen` antes que `exigir_rol`. `GET`: `exigir_rol`.

    Se mira en dos sitios: `ruta.dependencies` (el orden en que se declararon) y
    `ruta.dependant.dependencies` (lo que FastAPI resolverá, en su orden de resolución).
    """
    declaradas = [
        dependencia.dependency
        for dependencia in ruta.dependencies
        if dependencia.dependency is not None
    ]
    resueltas = [
        dependencia.call
        for dependencia in ruta.dependant.dependencies
        if dependencia.call is not None
    ]
    hallazgos: list[Hallazgo] = []
    for nombre, llamables in (("declaradas", declaradas), ("resueltas", resueltas)):
        rol = _posicion(llamables, _es_exigir_rol)
        if rol is None:
            hallazgos.append(
                Hallazgo(DEPENDENCIA_AUSENTE, operacion.metodo, ruta.path, f"exigir_rol ({nombre})")
            )
        if operacion.metodo == "GET":
            continue
        origen = _posicion(llamables, lambda llamable: llamable is verificar_origen)
        if origen is None:
            hallazgos.append(
                Hallazgo(
                    DEPENDENCIA_AUSENTE, operacion.metodo, ruta.path, f"verificar_origen ({nombre})"
                )
            )
        elif rol is not None and origen > rol:
            hallazgos.append(
                Hallazgo(
                    ORDEN_DE_DEPENDENCIAS,
                    operacion.metodo,
                    ruta.path,
                    f"exigir_rol antes ({nombre})",
                )
            )
    return hallazgos


def comprobar_rutas_de_archivos(
    aplicacion: FastAPI, esperadas: frozenset[Operacion]
) -> list[Hallazgo]:
    """Comprueba que lo publicado bajo `/api/v1/archivos` son exactamente `esperadas` y ninguna es binaria.

    Las comprobaciones de contenido (anotación, `/openapi.json` y respuesta real) se aplican a **toda** ruta
    bajo el prefijo, esperada o no; las de dependencias, solo a las esperadas, que son las que el borrador
    define. Devuelve la lista de hallazgos; vacía, todo en orden.
    """
    rutas = [ruta for ruta in rutas_de(aplicacion.routes) if _bajo_el_prefijo(ruta.path)]
    publicado = aplicacion.openapi()
    cliente = TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)
    hallazgos = _hallazgos_de_conjunto(rutas, esperadas)
    for ruta in rutas:
        hallazgos += _hallazgos_de_forma(ruta)
        hallazgos += _hallazgos_de_anotacion(ruta)
        hallazgos += _hallazgos_de_openapi(ruta, publicado)
        hallazgos += _hallazgos_de_respuesta(ruta, cliente)
        for operacion in _operaciones_de(ruta):
            if operacion in esperadas:
                hallazgos += _hallazgos_de_dependencias(ruta, operacion)
    return hallazgos


# --------------------------------------------------------------------------- la aplicación sin base


def crear_aplicacion_sin_base() -> FastAPI:
    """La aplicación real con solo la contraseña de aplicación: sin base, sin almacén, sin `lifespan`."""
    from servidor.fabrica import crear_aplicacion

    return crear_aplicacion(
        destino_registro=io.StringIO(),
        entorno={"CIMENTA_DB_CONTRASENA_APLICACION": secrets.token_urlsafe(16)},
    )


@pytest.fixture
def esperadas() -> frozenset[Operacion]:
    return operaciones_del_borrador()


# --------------------------------------------------------------------------- TC-43 · la aplicación real


def test_tkt059_ca12_el_borrador_declara_tres_operaciones_de_archivos(
    esperadas: frozenset[Operacion],
) -> None:
    """TC-43 · CA-12 — anti-verde vacío: el conjunto derivado del borrador no está vacío ni arrastra otra ruta.

    `crear_importacion` cita `TKT-059` pero cuelga de `/obras/...`: no entra en el conjunto.
    """
    assert {o.operacion_id for o in esperadas} == {
        "obtener_archivo",
        "confirmar_archivo",
        "obtener_url_descarga_archivo",
    }
    assert {(o.metodo, o.ruta) for o in esperadas} == {
        ("GET", "/api/v1/archivos/{archivo_id}"),
        ("POST", "/api/v1/archivos/{archivo_id}/confirmacion"),
        ("GET", "/api/v1/archivos/{archivo_id}/descarga"),
    }


def test_tkt059_ca12_ninguna_ruta_de_archivos_es_binaria(esperadas: frozenset[Operacion]) -> None:
    """TC-43 · CA-12 · ADR-016 · RNF-06 — las rutas de archivos son las del borrador y ninguna transmite bytes.

    Sobre la aplicación real sin base: exactamente las tres operaciones con `TKT-059` (sin
    `crear_importacion`), ninguna `async def`, `response_class` efectiva `JSONResponse`, anotación de
    retorno que no es una respuesta binaria, solo `application/json` en `/openapi.json`, respuesta real en
    JSON y las dependencias de protección en su orden: `verificar_origen` antes que `exigir_rol` en la
    `POST`, `exigir_rol` en las `GET`.
    """
    aplicacion = crear_aplicacion_sin_base()

    hallazgos = comprobar_rutas_de_archivos(aplicacion, esperadas)

    assert hallazgos == []
    # anti-verde vacío: el comprobador vio de verdad las tres rutas
    vistas = {
        operacion
        for ruta in rutas_de(aplicacion.routes)
        if _bajo_el_prefijo(ruta.path)
        for operacion in _operaciones_de(ruta)
    }
    assert vistas == esperadas


# --------------------------------------------------------------------------- TC-43 · el control (M-17)

RUTA_DE_CONTROL = "/api/v1/archivos/{archivo_id}/control"


def _flujo() -> StreamingResponse:
    return StreamingResponse(iter([b"bytes del archivo"]), media_type="application/octet-stream")


def _agregar_flujo_sin_declarar(enrutador: APIRouter) -> None:
    # Sin anotación de retorno ni `response_class`: solo la respuesta real delata los bytes.
    @enrutador.get("/{archivo_id}/control", operation_id="control_flujo_sin_declarar")
    def control(archivo_id: uuid.UUID):  # type: ignore[no-untyped-def]  # noqa: ANN202
        return _flujo()


def _agregar_flujo_anotado(enrutador: APIRouter) -> None:
    @enrutador.get("/{archivo_id}/control", operation_id="control_flujo_anotado")
    def control(archivo_id: uuid.UUID) -> StreamingResponse:
        return _flujo()


def _agregar_clase_response(enrutador: APIRouter) -> None:
    @enrutador.get(
        "/{archivo_id}/control", operation_id="control_clase_response", response_class=Response
    )
    def control(archivo_id: uuid.UUID) -> Response:
        return Response(content=b"bytes", media_type="application/octet-stream")


def _agregar_clase_fileresponse(enrutador: APIRouter) -> None:
    @enrutador.get(
        "/{archivo_id}/control",
        operation_id="control_clase_fileresponse",
        response_class=FileResponse,
    )
    def control(archivo_id: uuid.UUID) -> FileResponse:
        return FileResponse(__file__)


def _agregar_corrutina(enrutador: APIRouter) -> None:
    @enrutador.get("/{archivo_id}/control", operation_id="control_corrutina")
    async def control(archivo_id: uuid.UUID) -> dict[str, str]:
        return {"archivo": str(archivo_id)}


def _agregar_flujo_fuera_del_esquema(enrutador: APIRouter) -> None:
    @enrutador.get(
        "/{archivo_id}/control", operation_id="control_flujo_oculto", include_in_schema=False
    )
    def control(archivo_id: uuid.UUID) -> StreamingResponse:
        return _flujo()


CASOS_DE_CONTROL: dict[str, tuple[Callable[[APIRouter], None], set[str]]] = {
    # nombre: (cómo se añade la ruta extra, códigos que el comprobador debe señalar en ella)
    "flujo_sin_declarar": (_agregar_flujo_sin_declarar, {RESPUESTA_BINARIA}),
    "flujo_anotado": (_agregar_flujo_anotado, {ANOTACION_BINARIA, RESPUESTA_BINARIA}),
    "clase_response": (_agregar_clase_response, {CLASE_NO_JSON}),
    "clase_fileresponse": (_agregar_clase_fileresponse, {CLASE_NO_JSON}),
    "corrutina": (_agregar_corrutina, {CORRUTINA}),
    "flujo_fuera_del_esquema": (
        _agregar_flujo_fuera_del_esquema,
        {OPENAPI_AUSENTE, ANOTACION_BINARIA},
    ),
}


@pytest.mark.parametrize("caso", sorted(CASOS_DE_CONTROL))
def test_tkt059_ca12_el_control_senala_la_ruta_que_transmite_bytes(
    caso: str, esperadas: frozenset[Operacion]
) -> None:
    """TC-43 (control) · M-17 · CA-12 — una ruta extra bajo `/api/v1/archivos` que transmite bytes se señala.

    La aplicación real más un enrutador de prueba con una ruta que devuelve un `StreamingResponse` (con y
    sin anotarlo), declara `response_class=Response` o `FileResponse`, es `async def` o queda fuera de
    `/openapi.json`. El comprobador debe señalar esa ruta con el código concreto (no solo «ruta no
    esperada») y no señalar nada en las tres rutas reales. Un comprobador que solo mire la `response_class`
    declarada deja pasar el flujo no declarado y el oculto: así cae con M-17.
    """
    agregar, codigos_esperados = CASOS_DE_CONTROL[caso]
    aplicacion = crear_aplicacion_sin_base()
    enrutador = APIRouter(prefix=PREFIJO)
    agregar(enrutador)
    aplicacion.include_router(enrutador)

    hallazgos = comprobar_rutas_de_archivos(aplicacion, esperadas)

    de_la_extra = {h.codigo for h in hallazgos if h.ruta == RUTA_DE_CONTROL}
    de_las_reales = [h for h in hallazgos if h.ruta != RUTA_DE_CONTROL]
    assert RUTA_NO_ESPERADA in de_la_extra
    assert codigos_esperados <= de_la_extra, hallazgos
    assert de_las_reales == []
