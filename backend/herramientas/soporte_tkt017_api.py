"""Ayudas de las pruebas HTTP de TKT-017 que comparten el congelado (b1), las lecturas (b2) y el control (c).

Reúne lo que cualquier prueba de contrato de `presupuesto` necesita: el borrador OpenAPI cargado y los
validadores contra sus esquemas, el inicio de sesión real por HTTP, el contrato de error completo, el
recorrido de rutas de la aplicación, la comparación de la forma publicada con la del borrador y las
fixtures `base`, `entorno`, `contexto` y `abrir_sesion`. Los módulos de prueba no se importan entre sí:
importan de aquí, y cada definición vive solo aquí.

Las fixtures viven en este módulo y no en `conftest.py` para no ofrecérselas a toda la suite; cada módulo
de prueba que las usa las importa por nombre (`# noqa: F401`), que es como pytest las descubre.

Son ayudantes de prueba: ningún código de producción los importa.
"""

from __future__ import annotations

import functools
import io
import os
import secrets
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, cast

import pytest
import yaml
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy.engine import Engine
from starlette.routing import BaseRoute

from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from herramientas.soporte_tkt017_entorno import Base, Contexto, Entorno

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba, SembrarUsuario

RAIZ = Path(__file__).resolve().parents[2]
CABECERA_CORRELACION = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
COOKIE_SESION = "cimenta_sesion"
COOKIE_CSRF = "cimenta_csrf"
CABECERA_CSRF = "X-CSRF-Token"
TOKEN_CSRF = "csrf-de-la-prueba-0f3a9c71"
OTRO_TOKEN_CSRF = "csrf-otro-7b21d4e8"
CONTRASENA_DE_PRUEBA = "Clave-Del-Director-1"
NOMBRE_DEL_DIRECTOR = "Diana Directora"
# Seis apariciones de 12.5 × 420.0000 en cada uno de MUROS y PLAFONES_Y_CAJILLOS (`preparacion_dos_niveles`).
VENTA_POR_TIPO = {
    "MUROS": "31500.0000",
    "PLAFONES_Y_CAJILLOS": "31500.0000",
    "ENCHAPES": "0.0000",
    "GENERALES": "0.0000",
}


class Sesion(NamedTuple):
    usuario_id: uuid.UUID
    sesion_id: uuid.UUID


# --------------------------------------------------------------------------- el borrador y el HTTP


@functools.cache
def borrador() -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")),
    )


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def cabeceras_de(
    sesion_id: uuid.UUID | None, cookie_csrf: str | None = None, cabecera_csrf: str | None = None
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


def iniciar_sesion(cliente: TestClient, correo: str, contrasena: str) -> uuid.UUID:
    """Inicia sesión por HTTP con un par CSRF coincidente y vacía el almacén de cookies del cliente."""
    respuesta = cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers=cabeceras_de(None, TOKEN_CSRF, TOKEN_CSRF),
    )
    assert respuesta.status_code == 200, respuesta.text
    cliente.cookies.clear()
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        if COOKIE_SESION in galleta:
            return uuid.UUID(galleta[COOKIE_SESION].value)
    pytest.fail(f"La respuesta no fija {COOKIE_SESION}: {respuesta.headers.get_list('set-cookie')}")


def leer(
    cliente: TestClient,
    ruta: str,
    sesion_id: uuid.UUID | None,
    **consulta: object,
) -> Any:
    """`GET` con la cookie de sesión y los parámetros de consulta que se pasen por nombre."""
    return cliente.get(
        ruta,
        params={nombre: str(valor) for nombre, valor in consulta.items()} or None,
        headers=cabeceras_de(sesion_id),
    )


def leer_con_par_csrf(
    cliente: TestClient,
    ruta: str,
    sesion_id: uuid.UUID | None,
    *,
    cookie_csrf: str | None,
    cabecera_csrf: str | None,
) -> Any:
    """`GET` con la cookie de sesión y un par CSRF, que una lectura debe ignorar."""
    return cliente.get(ruta, headers=cabeceras_de(sesion_id, cookie_csrf, cabecera_csrf))


def exigir_error(
    respuesta: Any,
    *,
    estado: int,
    esperado: dict[str, Any],
    esquema: str,
    cabeceras: dict[str, str] | None = None,
) -> dict[str, Any]:
    """El contrato de error completo: código, cuerpo exacto con la correlación de la cabecera, esquema del
    borrador, cabeceras propias, y ninguna traza ni nombre interno."""
    assert respuesta.status_code == estado, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = cast("dict[str, Any]", respuesta.json())
    assert cuerpo == {**esperado, "correlacion_id": respuesta.headers[CABECERA_CORRELACION]}
    validar_contra(esquema, cuerpo)
    for clave, valor in (cabeceras or {}).items():
        assert respuesta.headers[clave] == valor
    for pista in ("Traceback", "sqlalchemy", "psycopg", "cimenta."):
        assert pista not in respuesta.text
    return cuerpo


def exigir_denegacion(
    base: Base,
    *,
    usuario_id: uuid.UUID,
    ocurrido_en: datetime,
    metodo: str,
    ruta: str,
    roles_requeridos: list[str],
    motivo: str = "ROL_INSUFICIENTE",
) -> None:
    """Un solo asiento `DENEGAR`, a nombre de quien llamó, con método, ruta y roles exigidos.

    `metodo` es el de la petición denegada (`"POST"` en las rutas que mutan, `"GET"` en las lecturas).
    """
    assert base.filas(
        "SELECT accion::text, usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, entidad_id, "
        "obra_id, datos_antes IS NULL, datos_despues FROM bitacora WHERE accion = 'DENEGAR'"
    ) == [
        (
            "DENEGAR",
            usuario_id,
            ocurrido_en,
            motivo,
            None,
            "usuario",
            usuario_id,
            None,
            True,
            {"metodo": metodo, "ruta": ruta, "roles_requeridos": roles_requeridos},
        )
    ]


# --------------------------------------------------------------------------- el entorno


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def entorno(datos_presupuesto: DatosPresupuesto, base: Base) -> Entorno:
    """La obra en planeación, los cuatro tipos sembrados, el usuario que confirma y la mano de obra."""
    entorno = Entorno(datos_presupuesto, base)
    entorno.registrar_mano_obra()
    return entorno


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El `ContextoPresupuesto` con el que la prueba confirma y congela, sobre el reloj de la aplicación."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def abrir_sesion(cliente: TestClient, sembrar_usuario: SembrarUsuario) -> Callable[..., Sesion]:
    """Siembra un usuario con los roles pedidos e inicia sesión con él por HTTP (un correo distinto cada vez)."""

    def abrir(
        roles: tuple[str, ...] = ("DIRECTOR_PROYECTOS",), *, nombre: str = "Lector de prueba"
    ) -> Sesion:
        correo = f"{'-'.join(roles).lower().replace('_', '-')}-{uuid.uuid4().hex[:8]}@cimenta.test"
        usuario_id = sembrar_usuario(correo, CONTRASENA_DE_PRUEBA, roles=roles, nombre=nombre)
        return Sesion(usuario_id, iniciar_sesion(cliente, correo, CONTRASENA_DE_PRUEBA))

    return abrir


def tipos_de_partida(base: Base) -> list[tuple[uuid.UUID, str, str]]:
    """Las cuatro filas de `tipo_partida`, ordenadas por `id` como las devuelve el borrador."""
    filas = base.conexion.execute(
        "SELECT id, clave, nombre FROM tipo_partida ORDER BY id"
    ).fetchall()
    assert len(filas) == 4
    return [(f[0], f[1], f[2]) for f in filas]


# --------------------------------------------------------------------------- el recorrido de rutas


def construir_aplicacion(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """La aplicación real completa, sin motor y sin variables de base en el entorno (sin Docker)."""
    for nombre in [n for n in os.environ if n.startswith("CIMENTA_DB_")]:
        monkeypatch.delenv(nombre)
    from servidor.fabrica import crear_aplicacion

    return crear_aplicacion(
        destino_registro=io.StringIO(),
        entorno={"CIMENTA_DB_CONTRASENA_APLICACION": secrets.token_urlsafe(16)},
    )


def publicado(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """El `/openapi.json` que publica la aplicación real."""
    aplicacion = construir_aplicacion(monkeypatch)
    return cast(
        "dict[str, Any]",
        TestClient(aplicacion, base_url="https://testserver").get("/openapi.json").json(),
    )


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido."""
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


# --------------------------------------------------------------------------- la forma de un esquema


def aplanar(
    documento: Mapping[str, Any],
    nodo: Mapping[str, Any],
    ruta: str,
    salida: dict[str, object],
    componentes: set[str],
) -> None:
    """Vuelca la forma de un esquema (con sus `$ref` resueltos) en `salida`, ruta a ruta.

    Cada hoja es un hecho comparable: el `type`, el `format`, el `enum` ordenado, el conjunto de
    propiedades y el de `required`. `oneOf`/`anyOf` con `null` y `type: [x, 'null']` se normalizan
    a `nulable`, porque OpenAPI 3.1 admite las dos formas y Pydantic escribe la segunda. Los
    nombres de los componentes de objeto o enumerado que se cruzan se acumulan en `componentes`.
    """
    if "$ref" in nodo:
        nombre = nodo["$ref"].rsplit("/", 1)[-1]
        resuelto = documento["components"]["schemas"][nombre]
        if resuelto.get("type") == "object" or "enum" in resuelto:
            componentes.add(nombre)
        aplanar(documento, resuelto, ruta, salida, componentes)
        return
    variantes = nodo.get("oneOf") or nodo.get("anyOf")
    if variantes is not None:
        no_nulas = [v for v in variantes if v.get("type") != "null"]
        salida[f"{ruta}.nulable"] = len(no_nulas) != len(variantes)
        for variante in no_nulas:
            aplanar(documento, variante, ruta, salida, componentes)
        return
    tipo = nodo.get("type")
    if isinstance(tipo, list):
        salida[f"{ruta}.nulable"] = "null" in tipo
        tipo = next(t for t in tipo if t != "null")
    salida[f"{ruta}.type"] = tipo
    if "format" in nodo:
        salida[f"{ruta}.format"] = nodo["format"]
    if "enum" in nodo:
        salida[f"{ruta}.enum"] = sorted(nodo["enum"])
    if tipo == "object":
        propiedades = nodo.get("properties", {})
        salida[f"{ruta}.propiedades"] = sorted(propiedades)
        salida[f"{ruta}.required"] = sorted(nodo.get("required", []))
        for nombre, hijo in propiedades.items():
            aplanar(documento, hijo, f"{ruta}.{nombre}", salida, componentes)
    elif tipo == "array":
        aplanar(documento, nodo["items"], f"{ruta}[]", salida, componentes)


def forma_de(
    documento: Mapping[str, Any], nodo: Mapping[str, Any], etiqueta: str
) -> tuple[dict[str, object], set[str]]:
    """La forma aplanada de un nodo de esquema y los componentes de objeto o enumerado que cruza."""
    salida: dict[str, object] = {}
    componentes: set[str] = set()
    aplanar(documento, nodo, etiqueta, salida, componentes)
    return salida, componentes


def forma_de_componente(
    documento: Mapping[str, Any], nombre: str
) -> tuple[dict[str, object], set[str]]:
    return forma_de(documento, {"$ref": f"#/components/schemas/{nombre}"}, nombre)


def diferencias_de_forma(
    del_borrador: Mapping[str, object], publicada: Mapping[str, object]
) -> list[str]:
    """Una línea por cada hecho que difiere; vacía si las dos formas coinciden."""
    return [
        f"{ruta}: borrador={del_borrador.get(ruta)!r} publicado={publicada.get(ruta)!r}"
        for ruta in sorted(del_borrador.keys() | publicada.keys())
        if del_borrador.get(ruta) != publicada.get(ruta)
    ]


def componentes_duplicados(
    documento: Mapping[str, Any], nombres: Iterable[str]
) -> list[tuple[str, str]]:
    """Pares de componentes publicados con otro nombre y la misma forma (el cliente generado los duplicaría)."""
    formas: dict[str, str] = {}
    duplicados: list[tuple[str, str]] = []
    for nombre in sorted(nombres):
        forma: dict[str, object] = {}
        aplanar(documento, {"$ref": f"#/components/schemas/{nombre}"}, "", forma, set())
        huella = repr(sorted(forma.items(), key=lambda par: par[0]))
        if huella in formas:
            duplicados.append((formas[huella], nombre))
        formas[huella] = nombre
    return duplicados


def _resolver(documento: Mapping[str, Any], nodo: Mapping[str, Any]) -> Mapping[str, Any]:
    while "$ref" in nodo:
        actual: Any = documento
        for parte in nodo["$ref"].removeprefix("#/").split("/"):
            actual = actual[parte]
        nodo = actual
    return nodo


def parametros_de(
    documento: Mapping[str, Any], ruta: str, metodo: str
) -> dict[str, dict[str, Any]]:
    """Los parámetros de una operación (también los del nivel de la ruta), por nombre y normalizados.

    Cada uno queda como `in`, `required`, `type`, `format`, `minimum`, `maximum` y `default` de su esquema,
    con los `$ref` resueltos y el `anyOf` con `null` de Pydantic reducido a su variante no nula.
    """
    elemento = documento["paths"][ruta]
    crudos = [*elemento.get("parameters", []), *elemento[metodo].get("parameters", [])]
    normalizados: dict[str, dict[str, Any]] = {}
    for crudo in crudos:
        parametro = _resolver(documento, crudo)
        esquema = _resolver(documento, parametro.get("schema", {}))
        variantes = esquema.get("anyOf") or esquema.get("oneOf")
        if variantes is not None:
            esquema = _resolver(documento, next(v for v in variantes if v.get("type") != "null"))
        normalizados[parametro["name"]] = {
            "in": parametro["in"],
            "required": bool(parametro.get("required", False)),
            "type": esquema.get("type"),
            "format": esquema.get("format"),
            "minimum": esquema.get("minimum"),
            "maximum": esquema.get("maximum"),
            "default": esquema.get("default"),
        }
    return normalizados


def esquema_de_respuesta_200(
    documento: Mapping[str, Any], ruta: str, metodo: str
) -> Mapping[str, Any]:
    """El esquema JSON de la respuesta `200` de una operación (sin resolver su `$ref`)."""
    respuesta = _resolver(documento, documento["paths"][ruta][metodo]["responses"]["200"])
    return cast("Mapping[str, Any]", respuesta["content"]["application/json"]["schema"])
