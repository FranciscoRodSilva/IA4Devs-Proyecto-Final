"""Respuestas HTTP del contrato de error (TKT-005, fila 6): TC-40 a TC-59, TC-61 y TC-62.

Sin Docker (CA-R4): ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa
de él. `servidor` y `contrato_error` se importan dentro de las ayudas, con `importlib`, no al
principio del archivo, como en las filas anteriores.

La aplicación de cada prueba sale de `crear_aplicacion(destino_registro=io.StringIO())` más un
`APIRouter` de la suite (prefijo `/prueba`), con una ruta `def` por caso que lanza la excepción del
contrato o declara el DTO. Los roles de quien llama los fija una dependencia de la ruta que escribe
`request.state.roles_de_quien_llama` a partir de la cabecera de prueba `X-Roles-De-Prueba`: una
misma aplicación atiende a dos usuarios con roles distintos, y sin la cabecera el atributo no se
fija nunca (el fallo seguro de CA-9 esc. 4). Todo `TestClient` se crea con
`raise_server_exceptions=False`, para que el `500` se observe como respuesta.

Cada respuesta de error comprueba el contrato completo: código HTTP, `tipo`, `regla` o `codigo`,
cifras como cadena, acciones filtradas, el conjunto exacto de claves (el borrador no declara
`additionalProperties: false`, así que el esquema solo no rechaza un campo de más), las cabeceras y
la validación contra el esquema del borrador OpenAPI.

Rojo esperado de la fila: la respuesta es la de FastAPI por omisión (`{"detail": ...}`, un `422`
con `loc`, un `500` de texto plano sin cabecera de correlación) porque `servidor/manejadores.py`
todavía no existe. Los `500` se comprueban además con su forma mínima de JSON (`mensaje` y
`correlacion_id`): sin eso, «el cuerpo no contiene tal texto» pasaría por el texto plano de Starlette.
"""

import functools
import importlib
import io
import json
import re
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import pytest
import yaml
from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, ValidationError
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import PlainValidator

from tipos_base import Cantidad, Dinero

RAIZ = Path(__file__).resolve().parents[2]

# La respuesta del `TestClient`: su tipo es de `httpx2`, dependencia transitiva de FastAPI que el
# proyecto no declara, así que no se importa para anotar.
Respuesta = Any

CABECERA = "X-Correlacion-Id"
CABECERA_DE_ROLES = "X-Roles-De-Prueba"

MENSAJE_RN03 = "La requisición excede el importe presupuestado del tipo de partida."
RUTA_SOLICITUD = "/api/v1/solicitudes-autorizacion/9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b"
RUTA_TOPE = "/api/v1/obras/7b6a5c4d-3e2f-4a1b-8c9d-0e1f2a3b4c5d/presupuesto-control"
RUTA_REQUISICION = "/api/v1/requisiciones/4d2a9f1c-3b7e-4e5a-8c6d-2f1e0a9b8c7d"
RUTA_PAGO = "/api/v1/pagos/6c5d4e3f-2a1b-4c9d-8e7f-0a1b2c3d4e5f"

SEIS_ROLES = frozenset(
    {"DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"}
)

# clave -> (método, ruta, roles que pueden ejecutarla)
ACCIONES_CONOCIDAS: dict[str, tuple[str, str, frozenset[str]]] = {
    "VER_SOLICITUD_AUTORIZACION": (
        "GET",
        RUTA_SOLICITUD,
        frozenset({"COMPRAS", "DIRECCION_GENERAL"}),
    ),
    "CAPTURAR_PRESUPUESTO_CONTROL": ("PUT", RUTA_TOPE, frozenset({"DIRECCION_GENERAL"})),
    "VER_REQUISICION": ("GET", RUTA_REQUISICION, SEIS_ROLES),
    "REINTENTAR": ("POST", "/api/v1/requisiciones", SEIS_ROLES),
    "REVISAR_PAGO": ("GET", RUTA_PAGO, frozenset({"ADMINISTRACION"})),
}

CIFRAS_RN03 = {
    "presupuestado": "45000.0000",
    "consumido": "33000.0000",
    "disponible": "12000.0000",
    "solicitado": "15000.0000",
    "excedente": "3000.0000",
}

ESQUEMAS_DE_ERROR = [
    "ErrorReglaNegocio",
    "ErrorConflictoEstado",
    "ErrorConcurrencia",
    "ErrorValidacion",
    "ErrorPermiso",
    "ErrorSesion",
    "ErrorLimiteIntentos",
    "ErrorNoEncontrado",
]

CLAVES_REGLA = {"tipo", "regla", "mensaje", "detalle", "acciones", "correlacion_id"}
CLAVES_CONFLICTO = {"tipo", "codigo", "mensaje", "detalle", "acciones", "correlacion_id"}
CLAVES_VALIDACION = {"tipo", "mensaje", "errores", "correlacion_id"}
CLAVES_MINIMAS_500 = {"mensaje", "correlacion_id"}


# ---------------------------------------------------------------------------------- ayudas


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


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


def texto_del_evento(evento: dict[str, Any]) -> str:
    """El evento del registro tal como se escribió, sin depender de qué campo lleva la traza."""
    return json.dumps(evento, ensure_ascii=False)


def ce(nombre: str) -> Any:
    """Un nombre de `contrato_error`, importado al usarlo."""
    return getattr(importlib.import_module("contrato_error"), nombre)


def accion(clave: str) -> Any:
    metodo, ruta, roles = ACCIONES_CONOCIDAS[clave]
    return ce("Accion")(clave, metodo, ruta, roles)


def con_roles(*roles: str) -> dict[str, str]:
    """Cabecera de prueba con la que `fijar_roles_de_quien_llama` escribe los roles en la petición."""
    return {CABECERA_DE_ROLES: ",".join(roles)}


def fijar_roles_de_quien_llama(request: Request) -> None:
    """Hace el papel de la dependencia de sesión de TKT-006: escribe los roles en `request.state`."""
    cabecera = request.headers.get(CABECERA_DE_ROLES)
    if cabecera is not None:
        request.state.roles_de_quien_llama = frozenset(r for r in cabecera.split(",") if r)


def aplicacion_de_prueba(
    rutas: dict[str, Callable[..., Any]],
) -> tuple[TestClient, io.StringIO]:
    """La aplicación de la fábrica con una ruta POST `def` por entrada y el registro capturado."""
    fabrica = importlib.import_module("servidor.fabrica")
    registro = io.StringIO()
    aplicacion = fabrica.crear_aplicacion(destino_registro=registro)
    router = APIRouter(prefix="/prueba", dependencies=[Depends(fijar_roles_de_quien_llama)])
    for ruta, endpoint in rutas.items():
        router.add_api_route(ruta, endpoint, methods=["POST"])
    aplicacion.include_router(router)
    return TestClient(aplicacion, raise_server_exceptions=False), registro


def cuerpo_json(respuesta: Respuesta) -> dict[str, Any]:
    """El cuerpo como objeto JSON. Un cuerpo que no es JSON (el texto plano de Starlette) falla aquí."""
    tipo_de_contenido = respuesta.headers.get("content-type", "")
    assert tipo_de_contenido.startswith("application/json"), (
        f"El cuerpo no es JSON ({tipo_de_contenido!r}): {respuesta.text!r}"
    )
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, dict)
    return cuerpo


def afirmar_correlacion(respuesta: Respuesta, cuerpo: dict[str, Any]) -> None:
    """Una sola cabecera de correlación, un UUID v4, igual al `correlacion_id` del cuerpo (CA-10)."""
    cabeceras = respuesta.headers.get_list(CABECERA)
    assert cabeceras == [cuerpo["correlacion_id"]]
    assert es_uuid4(cabeceras[0])


def afirmar_error(
    respuesta: Respuesta, estado: int, esquema: str, claves: set[str]
) -> dict[str, Any]:
    """Código HTTP, conjunto exacto de claves, correlación y validación contra el esquema del borrador."""
    assert respuesta.status_code == estado, respuesta.text
    cuerpo = cuerpo_json(respuesta)
    assert set(cuerpo) == claves
    afirmar_correlacion(respuesta, cuerpo)
    validar_contra(esquema, cuerpo)
    return cuerpo


def afirmar_500_minimo(respuesta: Respuesta) -> dict[str, Any]:
    """S1: `500` con `mensaje` genérico y `correlacion_id`, sin `tipo` y con la cabecera del cuerpo."""
    assert respuesta.status_code == 500
    cuerpo = cuerpo_json(respuesta)
    assert set(cuerpo) == CLAVES_MINIMAS_500
    assert isinstance(cuerpo["mensaje"], str)
    assert cuerpo["mensaje"].strip()
    afirmar_correlacion(respuesta, cuerpo)
    return cuerpo


def detalle_rn03() -> dict[str, object]:
    return {
        "obra": "AP-058-25 · Union Square F2",
        "tipo_partida": "MUROS",
        "presupuestado": Dinero("45000").cuantizar(),
        "consumido": Dinero("33000").cuantizar(),
        "disponible": Dinero("12000").cuantizar(),
        "solicitado": Dinero("15000").cuantizar(),
        "excedente": Dinero("3000").cuantizar(),
    }


def detalle_rn03_esperado() -> dict[str, str]:
    return {"obra": "AP-058-25 · Union Square F2", "tipo_partida": "MUROS", **CIFRAS_RN03}


def accion_esperada(clave: str) -> dict[str, str]:
    metodo, ruta, _ = ACCIONES_CONOCIDAS[clave]
    return {"clave": clave, "metodo": metodo, "ruta": ruta}


# ------------------------------------------------------------ rutas de prueba (todas `def`)


def lanzar(construir: Callable[[], Exception]) -> Callable[[], None]:
    """Una ruta `def` que lanza lo que construya `construir` al atender la petición."""

    def ruta() -> None:
        raise construir()

    return ruta


def regla_rn03(*claves_de_acciones: str) -> Callable[[], None]:
    """Ruta que lanza el rechazo de RN-03 con las acciones candidatas que se le pidan."""
    return lanzar(
        lambda: ce("RechazoRegla")(
            regla="RN-03",
            mensaje=MENSAJE_RN03,
            detalle=detalle_rn03(),
            acciones=[accion(clave) for clave in claves_de_acciones],
        )
    )


def lanzar_rechazo_sin_cuantizar() -> None:
    raise ce("RechazoRegla")(
        regla="RN-03",
        mensaje=MENSAJE_RN03,
        detalle={"disponible": Dinero("12000.00005")},
        acciones=[],
    )


MENSAJE_INTERNO = (
    "fallo con detalle" + " interno"
)  # armado aquí: ninguna línea de código lo contiene entero


def lanzar_error_interno() -> None:
    raise RuntimeError(MENSAJE_INTERNO)


def lanzar_runtime_con_texto_de_regla() -> None:
    raise RuntimeError("RN-03 excedida")


def sumar_dinero_y_cantidad() -> None:
    Dinero("1") + Cantidad("1")  # type: ignore[operator]  # el defecto del programa que la ruta simula


# Valores sensibles que una excepción real lleva en su mensaje (CA-14, seguridad F001). Se arman
# en tiempo de ejecución y las rutas los leen de estas constantes: así ninguna línea de código
# fuente de un marco de la traza contiene el valor, y solo `str(exc)` podría llevarlo al registro.
SECRETO = "S3cr3t" + "!"
SECRETO_DE_BASE = "SESION-SECRETA-" + "123"
SECRETO_LOCAL = "LOCAL-SECRETO-" + "777"


class ErrorDePrueba(Exception):
    """Excepción propia de la suite: su tipo calificado lleva el módulo de la prueba."""


class ErrorDeCausaDePrueba(Exception):
    """Segunda excepción propia, para las cadenas `raise ... from ...`."""


def lanzar_con_contrasena_en_el_mensaje() -> None:
    raise ValueError(f"contrasena={SECRETO}")


def lanzar_con_clave_de_base_en_el_mensaje() -> None:
    raise ErrorDePrueba(f"duplicate key: Key (token)=({SECRETO_DE_BASE}) already exists.")


def lanzar_con_causa() -> None:
    causa = ErrorDeCausaDePrueba(f"Key (token)=({SECRETO_DE_BASE}) already exists.")
    raise ErrorDePrueba(f"contrasena={SECRETO}") from causa


def lanzar_con_contexto() -> None:
    try:
        raise KeyError(f"token={SECRETO_DE_BASE}")
    except KeyError:
        raise RuntimeError(f"contrasena={SECRETO}")  # noqa: B904  # el __context__ implícito es lo que se prueba


def lanzar_cadena_de_tres() -> None:
    try:
        try:
            raise KeyError(f"token={SECRETO_DE_BASE}")
        except KeyError as clave:
            raise ErrorDeCausaDePrueba(f"Key (token)=({SECRETO_DE_BASE})") from clave
    except ErrorDeCausaDePrueba as causa:
        raise ErrorDePrueba(f"contrasena={SECRETO}") from causa


def lanzar_con_variable_local() -> None:
    clave_local = SECRETO_LOCAL
    raise RuntimeError(f"fallo con {len(clave_local)} caracteres de contexto")


def lanzar_validacion_con_regla() -> None:
    raise ce("ValidacionRechazada")(
        errores=[
            ce("ErrorDeCampo")(
                campo="tipo_partida_id",
                codigo="OBLIGATORIO",
                mensaje="El tipo de partida es obligatorio.",
                regla="RN-02",
            )
        ]
    )


def construir_los_ocho_tipos() -> dict[str, Callable[[], Exception]]:
    """Un constructor por `tipo` del borrador. Se evalúan al atender la petición, no al importar."""
    return {
        "REGLA_NEGOCIO": lambda: ce("RechazoRegla")(
            regla="RN-03", mensaje=MENSAJE_RN03, detalle=detalle_rn03(), acciones=[]
        ),
        "CONFLICTO": lambda: ce("ConflictoEstado")(
            codigo="SIN_LINEA_BASE_CONGELADA",
            mensaje="La obra no tiene línea base congelada.",
            detalle={},
            acciones=[],
        ),
        "CONCURRENCIA": lambda: ce("ConcurrenciaVencida")(
            codigo="BLOQUEO_VENCIDO",
            mensaje="El presupuesto está en uso; vuelve a intentarlo.",
            espera_maxima_ms=5000,
            reintentar_en_s=1,
            acciones=[accion("REINTENTAR")],
        ),
        "VALIDACION": lambda: ce("ValidacionRechazada")(
            errores=[
                ce("ErrorDeCampo")(
                    campo="nombre", codigo="OBLIGATORIO", mensaje="El campo es obligatorio."
                )
            ]
        ),
        "PERMISO": lambda: ce("PermisoDenegado")(
            motivo="ROL_INSUFICIENTE",
            mensaje="Tu rol no puede hacer esto.",
            roles_requeridos=["DIRECCION_GENERAL"],
        ),
        "SESION": lambda: ce("SesionInvalida")(
            motivo="SIN_SESION", mensaje="No has iniciado sesión."
        ),
        "LIMITE_INTENTOS": lambda: ce("LimiteIntentosExcedido")(
            mensaje="Demasiados intentos; espera un momento.", reintentar_en_s=30
        ),
        "NO_ENCONTRADO": lambda: ce("NoEncontrado")(
            recurso="requisicion", mensaje="La requisición no existe."
        ),
    }


# DTO de prueba. Viven en el módulo de la suite, no en el producto.


class CuerpoDosCampos(BaseModel):
    nombre: str
    nota: str | None = None


class Renglon(BaseModel):
    cantidad: int


class CuerpoConRenglones(BaseModel):
    renglones: list[Renglon]


class CuerpoNombreYCantidad(BaseModel):
    nombre: str
    cantidad: int


class CuerpoContrasenaEntera(BaseModel):
    contrasena: int


class CuerpoTodosLosCodigos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligatorio: str
    positivo: int = Field(1, gt=0)
    no_negativo: int = Field(0, ge=0)
    tope: int = Field(0, le=10)
    corto: str = Field("", max_length=3)
    motivo: str = Field("x", min_length=1)
    opcion: Literal["A", "B"] = "A"
    fecha: date | None = None


class CuerpoImporte(BaseModel):
    importe: Annotated[Dinero, PlainValidator(Dinero, json_schema_input_type=str)]


def ruta_dos_campos(cuerpo: CuerpoDosCampos) -> dict[str, str]:
    return {"nombre": cuerpo.nombre}


def ruta_con_renglones(cuerpo: CuerpoConRenglones) -> dict[str, int]:
    return {"renglones": len(cuerpo.renglones)}


def ruta_nombre_y_cantidad(cuerpo: CuerpoNombreYCantidad) -> dict[str, str]:
    return {"nombre": cuerpo.nombre}


def ruta_contrasena_entera(cuerpo: CuerpoContrasenaEntera) -> dict[str, bool]:
    return {"ok": True}


def ruta_todos_los_codigos(cuerpo: CuerpoTodosLosCodigos) -> dict[str, bool]:
    return {"ok": True}


def ruta_importe(cuerpo: CuerpoImporte) -> dict[str, bool]:
    return {"ok": True}


# -------------------------------------------------------------------------------- CA-1 a CA-5


def test_tkt005_ca01_regla_responde_409() -> None:
    """TC-40 · CA-1 esc. 1 · RN-03 — la regla rechazada responde 409 REGLA_NEGOCIO con regla, cifras y acciones."""
    cliente, _ = aplicacion_de_prueba({"/rn03": regla_rn03("VER_SOLICITUD_AUTORIZACION")})

    respuesta = cliente.post("/prueba/rn03", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_error(respuesta, 409, "ErrorReglaNegocio", CLAVES_REGLA)
    assert cuerpo == {
        "tipo": "REGLA_NEGOCIO",
        "regla": "RN-03",
        "mensaje": MENSAJE_RN03,
        "detalle": detalle_rn03_esperado(),
        "acciones": [accion_esperada("VER_SOLICITUD_AUTORIZACION")],
        "correlacion_id": respuesta.headers[CABECERA],
    }
    assert "Retry-After" not in respuesta.headers


def _prohibido(texto: str) -> Any:
    raise AssertionError(f"Un importe viajó como número JSON: {texto}")


def test_tkt005_ca03_importes_como_cadena_en_json() -> None:
    """TC-41 · CA-3 esc. 1 y 2 — en el JSON crudo las cinco cifras van entre comillas y ninguna es número."""
    cliente, _ = aplicacion_de_prueba({"/rn03": regla_rn03("VER_SOLICITUD_AUTORIZACION")})

    respuesta = cliente.post("/prueba/rn03", headers=con_roles("COMPRAS"))

    assert respuesta.status_code == 409
    for nombre, cifra in CIFRAS_RN03.items():
        patron = rf'"{nombre}"\s*:\s*"{re.escape(cifra)}"'
        assert re.search(patron, respuesta.text), f"{nombre} no viaja como la cadena {cifra!r}"
    # Un número JSON cualquiera —entero, decimal o constante— hace fallar el análisis.
    analizado = json.loads(
        respuesta.text, parse_float=_prohibido, parse_int=_prohibido, parse_constant=_prohibido
    )
    for nombre in CIFRAS_RN03:
        assert type(analizado["detalle"][nombre]) is str


def test_tkt005_ca03_sin_cuantizar_es_error_del_programa() -> None:
    """TC-42 · CA-3 esc. 3 — un importe sin cuantizar responde 500 mínimo, sin cifra redondeada ni tipo."""
    cliente, registro = aplicacion_de_prueba({"/sin-cuantizar": lanzar_rechazo_sin_cuantizar})

    respuesta = cliente.post("/prueba/sin-cuantizar", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_500_minimo(respuesta)
    assert "tipo" not in cuerpo
    assert "12000" not in respuesta.text
    assert "cuantizar" not in respuesta.text
    fallidas = [x for x in lineas_json(registro) if x["event"] == "peticion_fallida"]
    assert len(fallidas) == 1
    assert fallidas[0]["correlacion_id"] == cuerpo["correlacion_id"]
    # La causa real es la de serializar(): el registro conserva el tipo y el marco, no el texto (F001).
    linea = texto_del_evento(fallidas[0])
    assert "ValueError" in linea
    assert "serializar" in linea


def test_tkt005_ca04_conflicto_responde_409() -> None:
    """TC-43 · CA-4 esc. 1 — una obra sin línea base responde CONFLICTO con su codigo y sin regla."""
    construir = lambda: ce("ConflictoEstado")(  # noqa: E731
        codigo="SIN_LINEA_BASE_CONGELADA",
        mensaje="La obra no tiene línea base congelada.",
        detalle={"obra": "AP-058-25 · Union Square F2"},
        acciones=[],
    )
    cliente, _ = aplicacion_de_prueba({"/conflicto": lanzar(construir)})

    respuesta = cliente.post("/prueba/conflicto", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_error(respuesta, 409, "ErrorConflictoEstado", CLAVES_CONFLICTO)
    assert cuerpo["tipo"] == "CONFLICTO"
    assert cuerpo["codigo"] == "SIN_LINEA_BASE_CONGELADA"
    assert "regla" not in cuerpo
    assert cuerpo["detalle"] == {"obra": "AP-058-25 · Union Square F2"}
    assert cuerpo["acciones"] == []


def test_tkt005_ca05_concurrencia_responde_409_con_retry_after() -> None:
    """TC-44 · CA-5 esc. 1 · RNF-16 — el vencimiento responde CONCURRENCIA con Retry-After y REINTENTAR."""
    construir = lambda: ce("ConcurrenciaVencida")(  # noqa: E731
        codigo="BLOQUEO_VENCIDO",
        mensaje="El presupuesto está en uso; vuelve a intentarlo.",
        espera_maxima_ms=5000,
        reintentar_en_s=1,
        acciones=[accion("REINTENTAR")],
    )
    cliente, _ = aplicacion_de_prueba({"/concurrencia": lanzar(construir)})

    respuesta = cliente.post("/prueba/concurrencia", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_error(respuesta, 409, "ErrorConcurrencia", CLAVES_CONFLICTO)
    assert cuerpo["tipo"] == "CONCURRENCIA"
    assert cuerpo["codigo"] == "BLOQUEO_VENCIDO"
    assert respuesta.headers["Retry-After"] == "1"
    assert cuerpo["detalle"] == {"espera_maxima_ms": 5000}
    assert cuerpo["acciones"] == [accion_esperada("REINTENTAR")]
    assert "regla" not in cuerpo


def concurrencia_con_reintentar_de_compras(*claves_previas: str) -> Callable[[], None]:
    """Ruta que lanza un vencimiento cuyo `REINTENTAR` lista solo a COMPRAS, tras las acciones previas."""
    reintentar_de_compras = ce("Accion")(
        "REINTENTAR", "POST", "/api/v1/requisiciones", frozenset({"COMPRAS"})
    )
    return lanzar(
        lambda: ce("ConcurrenciaVencida")(
            codigo="BLOQUEO_VENCIDO",
            mensaje="El presupuesto está en uso; vuelve a intentarlo.",
            espera_maxima_ms=5000,
            reintentar_en_s=1,
            acciones=[*(accion(c) for c in claves_previas), reintentar_de_compras],
        )
    )


@pytest.mark.parametrize(
    "cabeceras",
    [
        pytest.param({}, id="sin_roles_en_la_peticion"),
        pytest.param(con_roles("ALMACEN"), id="rol_ajeno_al_de_la_accion"),
        pytest.param(con_roles("GERENTE"), id="rol_fuera_del_catalogo"),
        pytest.param(con_roles("COMPRAS"), id="control_rol_listado_nace_en_verde"),
    ],
)
def test_tkt005_ca05_el_vencimiento_nunca_llega_sin_reintentar(cabeceras: dict[str, str]) -> None:
    """CA-5 esc. 1 · RNF-16 · F001 — REINTENTAR repite lo que quien llama acaba de invocar: no se filtra por rol.

    Decisión de diseño del orquestador (ciclo de corrección 1): sin `roles_de_quien_llama` en la
    petición, o con un rol que la acción no lista, el 409 CONCURRENCIA sigue trayendo REINTENTAR.
    «Ningún vencimiento llega al cliente sin una salida documentada.»
    """
    cliente, _ = aplicacion_de_prueba({"/concurrencia": concurrencia_con_reintentar_de_compras()})

    respuesta = cliente.post("/prueba/concurrencia", headers=cabeceras)

    cuerpo = afirmar_error(respuesta, 409, "ErrorConcurrencia", CLAVES_CONFLICTO)
    assert cuerpo == {
        "tipo": "CONCURRENCIA",
        "codigo": "BLOQUEO_VENCIDO",
        "mensaje": "El presupuesto está en uso; vuelve a intentarlo.",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [accion_esperada("REINTENTAR")],
        "correlacion_id": respuesta.headers[CABECERA],
    }
    assert respuesta.headers["Retry-After"] == "1"


def test_tkt005_ca05_la_segunda_accion_de_la_concurrencia_si_se_filtra() -> None:
    """CA-5 · CA-9 · F001 — junto a REINTENTAR, la acción restringida de la misma concurrencia solo la ve su rol."""
    cliente, _ = aplicacion_de_prueba(
        {"/concurrencia": concurrencia_con_reintentar_de_compras("CAPTURAR_PRESUPUESTO_CONTROL")}
    )

    ajeno = cliente.post("/prueba/concurrencia", headers=con_roles("ALMACEN"))
    sin_roles = cliente.post("/prueba/concurrencia")
    direccion = cliente.post("/prueba/concurrencia", headers=con_roles("DIRECCION_GENERAL"))

    cuerpos = [
        afirmar_error(r, 409, "ErrorConcurrencia", CLAVES_CONFLICTO) for r in (ajeno, sin_roles)
    ]
    assert [c["acciones"] for c in cuerpos] == [[accion_esperada("REINTENTAR")]] * 2
    completo = afirmar_error(direccion, 409, "ErrorConcurrencia", CLAVES_CONFLICTO)
    assert completo["acciones"] == [
        accion_esperada("CAPTURAR_PRESUPUESTO_CONTROL"),
        accion_esperada("REINTENTAR"),
    ]


# ------------------------------------------------------------------------------------- CA-6


def test_tkt005_ca06_campo_obligatorio() -> None:
    """TC-45 · CA-6 esc. 1 — un campo ausente responde VALIDACION con su campo y OBLIGATORIO, sin detail ni loc."""
    cliente, _ = aplicacion_de_prueba({"/dos-campos": ruta_dos_campos})
    # Guarda contra un falso rojo: el DTO y la ruta funcionan con un cuerpo válido.
    assert cliente.post("/prueba/dos-campos", json={"nombre": "x"}).status_code == 200

    respuesta = cliente.post("/prueba/dos-campos", json={"nota": "x"})

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["tipo"] == "VALIDACION"
    assert cuerpo["mensaje"] == "La petición tiene 1 campo inválido."
    assert cuerpo["errores"] == [
        {"campo": "nombre", "codigo": "OBLIGATORIO", "mensaje": "El campo es obligatorio."}
    ]
    assert "detail" not in cuerpo
    assert "loc" not in respuesta.text


def test_tkt005_ca06_campo_anidado_con_su_ruta() -> None:
    """TC-46 · CA-6 esc. 2 — el campo anidado se nombra con su ruta: renglones[1].cantidad."""
    cliente, _ = aplicacion_de_prueba({"/renglones": ruta_con_renglones})
    assert (
        cliente.post("/prueba/renglones", json={"renglones": [{"cantidad": 1}]}).status_code == 200
    )

    respuesta = cliente.post(
        "/prueba/renglones", json={"renglones": [{"cantidad": 1}, {"cantidad": "abc"}]}
    )

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert [(e["campo"], e["codigo"]) for e in cuerpo["errores"]] == [
        ("renglones[1].cantidad", "FORMATO")
    ]
    assert "loc" not in respuesta.text


def test_tkt005_ca06_varios_errores() -> None:
    """TC-47 · CA-6 esc. 3 — dos campos inválidos devuelven dos elementos y «La petición tiene 2 campos inválidos.»"""
    cliente, _ = aplicacion_de_prueba({"/nombre-y-cantidad": ruta_nombre_y_cantidad})

    respuesta = cliente.post("/prueba/nombre-y-cantidad", json={"nombre": 5, "cantidad": "abc"})

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["mensaje"] == "La petición tiene 2 campos inválidos."
    assert {e["campo"]: e["codigo"] for e in cuerpo["errores"]} == {
        "nombre": "FORMATO",
        "cantidad": "FORMATO",
    }
    assert len(cuerpo["errores"]) == 2


@pytest.mark.parametrize(
    "contenido",
    [
        pytest.param('{"nombre": ', id="truncado"),
        pytest.param('{"nombre": "x",}', id="coma_final"),
        pytest.param("esto no es json", id="texto_plano"),
    ],
)
def test_tkt005_ca06_json_malformado_se_nombra_cuerpo(contenido: str) -> None:
    """CA-6 esc. 4 · F003 — un cuerpo que no es JSON responde campo «cuerpo» con FORMATO, no el desplazamiento «[11]».

    Pydantic ubica el error `json_invalid` en `('body', <desplazamiento>)`: ese entero es la posición
    del fallo de análisis, no un índice de lista, y no debe llegar al cliente como campo.
    """
    cliente, _ = aplicacion_de_prueba({"/dos-campos": ruta_dos_campos})
    # Guarda contra un falso rojo: la ruta atiende un JSON válido.
    assert cliente.post("/prueba/dos-campos", json={"nombre": "x"}).status_code == 200

    respuesta = cliente.post(
        "/prueba/dos-campos", content=contenido, headers={"Content-Type": "application/json"}
    )

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["mensaje"] == "La petición tiene 1 campo inválido."
    assert cuerpo["errores"] == [
        {
            "campo": "cuerpo",
            "codigo": "FORMATO",
            "mensaje": "El valor no tiene el formato esperado.",
        }
    ]
    assert not re.search(r"\[\d+\]", respuesta.text)
    assert "json_invalid" not in respuesta.text


# (tipo de error de Pydantic, ctx, código esperado): una fila por regla de la tabla de traducción
# del diseño (PA-T6), más los tipos sin correspondencia conocida, que caen en FORMATO.
TRADUCCION_DE_PYDANTIC = [
    pytest.param("missing", None, "OBLIGATORIO", id="missing"),
    pytest.param("string_too_short", {"min_length": 1}, "OBLIGATORIO", id="string_too_short_1"),
    pytest.param("too_short", {"min_length": 1}, "OBLIGATORIO", id="too_short_1"),
    pytest.param("string_too_short", {"min_length": 3}, "FUERA_DE_RANGO", id="string_too_short_3"),
    pytest.param("too_short", {"min_length": 2}, "FUERA_DE_RANGO", id="too_short_2"),
    pytest.param("greater_than", {"gt": 0}, "NO_POSITIVO", id="greater_than_cero"),
    pytest.param("greater_than", {"gt": 5}, "FUERA_DE_RANGO", id="greater_than_otro"),
    pytest.param("greater_than_equal", {"ge": 0}, "FUERA_DE_RANGO", id="greater_than_equal"),
    pytest.param("less_than", {"lt": 10}, "FUERA_DE_RANGO", id="less_than"),
    pytest.param("less_than_equal", {"le": 10}, "FUERA_DE_RANGO", id="less_than_equal"),
    pytest.param("string_too_long", {"max_length": 3}, "DEMASIADO_LARGO", id="string_too_long"),
    pytest.param("too_long", {"max_length": 3}, "DEMASIADO_LARGO", id="too_long"),
    pytest.param("enum", {"expected": "'A' o 'B'"}, "VALOR_NO_PERMITIDO", id="enum"),
    pytest.param("literal_error", {"expected": "'A' o 'B'"}, "VALOR_NO_PERMITIDO", id="literal"),
    pytest.param("extra_forbidden", None, "VALOR_NO_PERMITIDO", id="extra_forbidden"),
    pytest.param("value_error", {"error": "x"}, "FORMATO", id="value_error"),
    pytest.param("xyz_desconocido", None, "FORMATO", id="tipo_desconocido"),
    pytest.param("json_invalid", None, "FORMATO", id="json_invalid"),
    pytest.param("model_attributes_type", None, "FORMATO", id="model_attributes_type"),
]


@pytest.mark.parametrize(("tipo", "ctx", "esperado"), TRADUCCION_DE_PYDANTIC)
def test_tkt005_ca06_traduccion_de_pydantic_a_los_siete_codigos(
    tipo: str, ctx: dict[str, object] | None, esperado: str
) -> None:
    """TC-48 (a) · CA-6 esc. 4 · PA-T6 — cada tipo de error de Pydantic cae en uno de los siete códigos.

    Prueba unitaria de la función del diseño: su rojo es que `servidor.manejadores` no existe.
    """
    manejadores = importlib.import_module("servidor.manejadores")

    codigo = manejadores.codigo_de_error_pydantic(tipo, ctx)

    assert codigo == esperado
    assert codigo in {m.value for m in ce("CodigoValidacion")}


def test_tkt005_ca06_todo_error_cae_en_el_enum() -> None:
    """TC-48 (b) · CA-6 esc. 4 · PA-T6 — nueve errores reales de Pydantic, cada uno con su código y sin texto interno."""
    cliente, _ = aplicacion_de_prueba({"/codigos": ruta_todos_los_codigos})
    assert cliente.post("/prueba/codigos", json={"obligatorio": "x"}).status_code == 200

    respuesta = cliente.post(
        "/prueba/codigos",
        json={
            "positivo": 0,
            "no_negativo": -1,
            "tope": 11,
            "corto": "abcd",
            "motivo": "",
            "opcion": "C",
            "fecha": "no-fecha",
            "sobra": 1,
        },
    )

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["mensaje"] == "La petición tiene 9 campos inválidos."
    assert len(cuerpo["errores"]) == 9
    assert {e["campo"]: e["codigo"] for e in cuerpo["errores"]} == {
        "obligatorio": "OBLIGATORIO",
        "positivo": "NO_POSITIVO",
        "no_negativo": "FUERA_DE_RANGO",
        "tope": "FUERA_DE_RANGO",
        "corto": "DEMASIADO_LARGO",
        "motivo": "OBLIGATORIO",
        "opcion": "VALOR_NO_PERMITIDO",
        "fecha": "FORMATO",
        "sobra": "VALOR_NO_PERMITIDO",
    }
    catalogo = {m.value for m in ce("CodigoValidacion")}
    assert {e["codigo"] for e in cuerpo["errores"]} <= catalogo
    for interno in (
        "greater_than",
        "literal_error",
        "missing",
        "Field required",
        "Input should",
        '"input"',
    ):
        assert interno not in respuesta.text


def test_tkt005_ca06_regla_que_impone_la_forma() -> None:
    """TC-49 · CA-6 esc. 5 · RN-02 — un caso de uso que rechaza la forma con su regla la lleva en el elemento."""
    cliente, _ = aplicacion_de_prueba({"/forma": lanzar_validacion_con_regla})

    respuesta = cliente.post("/prueba/forma", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["errores"] == [
        {
            "campo": "tipo_partida_id",
            "codigo": "OBLIGATORIO",
            "mensaje": "El tipo de partida es obligatorio.",
            "regla": "RN-02",
        }
    ]
    assert cuerpo["mensaje"] == "La petición tiene 1 campo inválido."


# ------------------------------------------------------------------------------- CA-7 y CA-8


def test_tkt005_ca07_permiso_responde_403() -> None:
    """TC-50 · CA-7 esc. 1 y 2 — un rol insuficiente responde PERMISO con los roles requeridos y sin detalle."""
    construir = lambda: ce("PermisoDenegado")(  # noqa: E731
        motivo="ROL_INSUFICIENTE",
        mensaje="Tu rol no puede capturar el presupuesto de control.",
        roles_requeridos=["DIRECCION_GENERAL"],
    )
    cliente, _ = aplicacion_de_prueba({"/solo-direccion": lanzar(construir)})

    respuesta = cliente.post("/prueba/solo-direccion", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_error(
        respuesta,
        403,
        "ErrorPermiso",
        {"tipo", "motivo", "mensaje", "roles_requeridos", "correlacion_id"},
    )
    assert cuerpo["tipo"] == "PERMISO"
    assert cuerpo["motivo"] == "ROL_INSUFICIENTE"
    assert cuerpo["roles_requeridos"] == ["DIRECCION_GENERAL"]
    assert "detalle" not in cuerpo


@pytest.mark.parametrize(
    ("construir", "estado", "esquema", "claves", "esperado", "reintentar"),
    [
        pytest.param(
            lambda: ce("SesionInvalida")(motivo="SIN_SESION", mensaje="No has iniciado sesión."),
            401,
            "ErrorSesion",
            {"tipo", "motivo", "mensaje", "correlacion_id"},
            {"tipo": "SESION", "motivo": "SIN_SESION"},
            None,
            id="sin_sesion_401",
        ),
        pytest.param(
            lambda: ce("LimiteIntentosExcedido")(
                mensaje="Demasiados intentos; espera un momento.", reintentar_en_s=30
            ),
            429,
            "ErrorLimiteIntentos",
            {"tipo", "mensaje", "reintentar_en_s", "correlacion_id"},
            {"tipo": "LIMITE_INTENTOS", "reintentar_en_s": 30},
            "30",
            id="limite_de_intentos_429",
        ),
        pytest.param(
            lambda: ce("NoEncontrado")(recurso="requisicion", mensaje="La requisición no existe."),
            404,
            "ErrorNoEncontrado",
            {"tipo", "recurso", "mensaje", "correlacion_id"},
            {"tipo": "NO_ENCONTRADO", "recurso": "requisicion"},
            None,
            id="no_encontrado_404",
        ),
    ],
)
def test_tkt005_ca08_sesion_limite_no_encontrado(
    construir: Callable[[], Exception],
    estado: int,
    esquema: str,
    claves: set[str],
    esperado: dict[str, object],
    reintentar: str | None,
) -> None:
    """TC-51 · CA-8 esc. 1 a 3 — 401 SESION, 429 LIMITE_INTENTOS con Retry-After y 404 NO_ENCONTRADO con su recurso."""
    cliente, _ = aplicacion_de_prueba({"/error": lanzar(construir)})

    respuesta = cliente.post("/prueba/error")

    cuerpo = afirmar_error(respuesta, estado, esquema, claves)
    assert {k: cuerpo[k] for k in esperado} == esperado
    assert respuesta.headers.get("Retry-After") == reintentar


def test_tkt005_ca08_ruta_inexistente() -> None:
    """TC-52 · CA-8 esc. 4 · PA-T4 — una ruta que no existe responde NO_ENCONTRADO con la ruta como recurso."""
    cliente, _ = aplicacion_de_prueba({})

    respuesta = cliente.get("/api/v1/no-existe")

    cuerpo = afirmar_error(
        respuesta, 404, "ErrorNoEncontrado", {"tipo", "recurso", "mensaje", "correlacion_id"}
    )
    assert cuerpo["tipo"] == "NO_ENCONTRADO"
    assert cuerpo["recurso"] == "/api/v1/no-existe"
    assert "detail" not in cuerpo


# ------------------------------------------------------------------------------------- CA-9


@pytest.mark.parametrize(
    ("cabeceras", "candidatas", "ofrecidas"),
    [
        pytest.param(
            con_roles("DIRECCION_GENERAL"),
            ("CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"),
            ["CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"],
            id="direccion_general_ve_las_dos",
        ),
        pytest.param(
            con_roles("COMPRAS"),
            ("CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"),
            ["VER_REQUISICION"],
            id="compras_solo_ve_la_de_todos",
        ),
        pytest.param(
            con_roles("COMPRAS", "ADMINISTRACION"),
            ("REVISAR_PAGO",),
            ["REVISAR_PAGO"],
            id="union_de_roles_ofrece_la_accion",
        ),
        pytest.param(
            con_roles("RESIDENTE"),
            ("CAPTURAR_PRESUPUESTO_CONTROL",),
            [],
            id="residente_no_ve_ninguna_que_daria_403",
        ),
        pytest.param(
            {},
            ("CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"),
            [],
            id="sin_roles_conocidos_ni_la_de_todos",
        ),
        pytest.param(
            con_roles("GERENTE"),
            ("CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"),
            [],
            id="rol_desconocido_no_ofrece_nada",
        ),
    ],
)
def test_tkt005_ca09_acciones_segun_quien_llama(
    cabeceras: dict[str, str], candidatas: tuple[str, ...], ofrecidas: list[str]
) -> None:
    """TC-53 · CA-9 esc. 1 a 4 — el mismo rechazo ofrece solo las acciones que quien llama puede ejecutar."""
    cliente, _ = aplicacion_de_prueba({"/rn03": regla_rn03(*candidatas)})

    respuesta = cliente.post("/prueba/rn03", headers=cabeceras)

    cuerpo = afirmar_error(respuesta, 409, "ErrorReglaNegocio", CLAVES_REGLA)
    assert [a["clave"] for a in cuerpo["acciones"]] == ofrecidas
    assert cuerpo["acciones"] == [accion_esperada(clave) for clave in ofrecidas]
    # El rechazo conserva su regla, su detalle y su mensaje aunque no quede ninguna acción.
    assert cuerpo["regla"] == "RN-03"
    assert cuerpo["detalle"] == detalle_rn03_esperado()
    assert cuerpo["mensaje"] == MENSAJE_RN03


def test_tkt005_ca09_dos_usuarios_en_la_misma_aplicacion() -> None:
    """TC-53 · CA-9 esc. 1 — dos usuarios seguidos, en la misma aplicación, ven acciones distintas."""
    cliente, _ = aplicacion_de_prueba(
        {"/rn03": regla_rn03("CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION")}
    )

    direccion = cliente.post("/prueba/rn03", headers=con_roles("DIRECCION_GENERAL"))
    compras = cliente.post("/prueba/rn03", headers=con_roles("COMPRAS"))
    sin_sesion = cliente.post("/prueba/rn03")

    claves = [
        [a["clave"] for a in cuerpo_json(r)["acciones"]] for r in (direccion, compras, sin_sesion)
    ]
    assert claves == [["CAPTURAR_PRESUPUESTO_CONTROL", "VER_REQUISICION"], ["VER_REQUISICION"], []]


# ------------------------------------------------------------------------------- CA-10, CA-11


@pytest.mark.parametrize(
    ("tipo", "estado"),
    [
        ("REGLA_NEGOCIO", 409),
        ("CONFLICTO", 409),
        ("CONCURRENCIA", 409),
        ("VALIDACION", 422),
        ("PERMISO", 403),
        ("SESION", 401),
        ("LIMITE_INTENTOS", 429),
        ("NO_ENCONTRADO", 404),
    ],
)
def test_tkt005_ca10_correlacion_en_cuerpo_y_cabecera(tipo: str, estado: int) -> None:
    """TC-54 · CA-10 esc. 2 — el correlacion_id de cada uno de los ocho tipos es el de la cabecera y un UUID v4."""
    cliente, _ = aplicacion_de_prueba({"/error": lanzar(construir_los_ocho_tipos()[tipo])})

    respuesta = cliente.post("/prueba/error", headers=con_roles("COMPRAS"))

    assert respuesta.status_code == estado
    cuerpo = cuerpo_json(respuesta)
    assert cuerpo["tipo"] == tipo
    afirmar_correlacion(respuesta, cuerpo)


def test_tkt005_ca11_rechazo_deja_su_linea() -> None:
    """TC-55 · CA-11 esc. 1 — el rechazo de regla deja una línea JSON con método, ruta, estado 409 y su correlación."""
    cliente, registro = aplicacion_de_prueba({"/rn03": regla_rn03("VER_SOLICITUD_AUTORIZACION")})

    respuesta = cliente.post("/prueba/rn03", headers=con_roles("COMPRAS"))

    assert respuesta.status_code == 409
    atendidas = [x for x in lineas_json(registro) if x["event"] == "peticion_atendida"]
    assert len(atendidas) == 1
    linea = atendidas[0]
    assert linea["metodo"] == "POST"
    assert linea["ruta"] == "/prueba/rn03"
    assert linea["estado"] == 409
    assert linea["correlacion_id"] == respuesta.headers[CABECERA]


@pytest.mark.parametrize(
    ("ruta", "endpoint"),
    [
        pytest.param("/contrasena-entera", ruta_contrasena_entera, id="valor_de_tipo_incorrecto"),
        pytest.param("/dos-campos", ruta_dos_campos, id="campo_obligatorio_ausente"),
    ],
)
def test_tkt005_ca11_el_422_no_refleja_el_cuerpo(ruta: str, endpoint: Callable[..., Any]) -> None:
    """TC-73b · CA-11 esc. 2 — un valor sensible de un cuerpo inválido no sale en el 422 ni en el registro."""
    cliente, registro = aplicacion_de_prueba({ruta: endpoint})
    secreto = "secreta-123"

    respuesta = cliente.post(
        f"/prueba{ruta}",
        json={"contrasena": secreto},
        headers={
            "Cookie": "cimenta_sesion=cookie-secreta-xyz",
            "Authorization": "Bearer token-secreto-abc",
        },
    )

    assert respuesta.status_code == 422
    assert secreto not in respuesta.text
    assert all(secreto not in valor for valor in respuesta.headers.values())
    assert secreto not in registro.getvalue()
    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["tipo"] == "VALIDACION"


# ------------------------------------------------------------------------- CA-13, CA-14, CA-15


def test_tkt005_ca13_un_manejador_por_familia() -> None:
    """TC-56 · CA-13 esc. 1 — hay un manejador por familia del contrato, todos de servidor.manejadores, y ninguno por regla."""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    fabrica = importlib.import_module("servidor.fabrica")
    aplicacion = fabrica.crear_aplicacion(destino_registro=io.StringIO())
    error_contrato = ce("ErrorContrato")

    propios = {
        clave
        for clave, manejador in aplicacion.exception_handlers.items()
        if getattr(manejador, "__module__", "") == "servidor.manejadores"
    }

    assert propios == {error_contrato, RequestValidationError, StarletteHTTPException, Exception}
    for clave in aplicacion.exception_handlers:
        subclase_propia = (
            isinstance(clave, type)
            and issubclass(clave, error_contrato)
            and clave is not error_contrato
        )
        assert not subclase_propia, f"Hay un manejador propio para {clave.__name__}"


def test_tkt005_ca13_excepcion_sin_contrato_no_es_regla() -> None:
    """TC-57 · CA-13 esc. 2 — un RuntimeError con texto «RN-03 excedida» no se disfraza de regla."""
    cliente, _ = aplicacion_de_prueba({"/texto-de-regla": lanzar_runtime_con_texto_de_regla})

    respuesta = cliente.post("/prueba/texto-de-regla", headers=con_roles("COMPRAS"))

    assert respuesta.status_code == 500  # ni 409
    cuerpo = afirmar_500_minimo(respuesta)
    assert "tipo" not in cuerpo
    assert "regla" not in cuerpo
    assert "RN-03" not in respuesta.text
    assert "REGLA_NEGOCIO" not in respuesta.text


def test_tkt005_ca14_error_no_controlado_minimo() -> None:
    """TC-58 · CA-14 esc. 1 · S1 — el 500 no filtra traza ni texto, repite la correlación y deja la traza en el registro."""
    cliente, registro = aplicacion_de_prueba({"/interno": lanzar_error_interno})

    respuesta = cliente.post("/prueba/interno", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_500_minimo(respuesta)
    for filtrado in (MENSAJE_INTERNO, "RuntimeError", "Traceback", "File "):
        assert filtrado not in respuesta.text
    fallidas = [x for x in lineas_json(registro) if x["event"] == "peticion_fallida"]
    assert len(fallidas) == 1
    assert fallidas[0]["correlacion_id"] == cuerpo["correlacion_id"]
    # La traza queda en el registro como tipo y marcos; el texto de la excepción no (seguridad F001).
    linea = texto_del_evento(fallidas[0])
    assert "RuntimeError" in linea
    assert lanzar_error_interno.__name__ in linea
    assert Path(__file__).name in linea
    assert MENSAJE_INTERNO not in registro.getvalue()


def tipo_calificado(tipo: type[BaseException]) -> str:
    """`modulo.NombreCalificado`; para los propios de Python basta el nombre, que `builtins.X` también contiene."""
    if tipo.__module__ == "builtins":
        return tipo.__qualname__
    return f"{tipo.__module__}.{tipo.__qualname__}"


@pytest.mark.parametrize(
    ("endpoint", "cadena", "secretos"),
    [
        pytest.param(
            lanzar_con_contrasena_en_el_mensaje,
            [ValueError],
            [SECRETO],
            id="contrasena_en_el_mensaje",
        ),
        pytest.param(
            lanzar_con_clave_de_base_en_el_mensaje,
            [ErrorDePrueba],
            [SECRETO_DE_BASE],
            id="clave_de_base_en_el_mensaje",
        ),
        pytest.param(
            lanzar_con_causa,
            [ErrorDePrueba, ErrorDeCausaDePrueba],
            [SECRETO, SECRETO_DE_BASE],
            id="cadena_raise_from",
        ),
        pytest.param(
            lanzar_con_contexto,
            [RuntimeError, KeyError],
            [SECRETO, SECRETO_DE_BASE],
            id="contexto_implicito",
        ),
        pytest.param(
            lanzar_cadena_de_tres,
            [ErrorDePrueba, ErrorDeCausaDePrueba, KeyError],
            [SECRETO, SECRETO_DE_BASE],
            id="cadena_de_tres_excepciones",
        ),
    ],
)
def test_tkt005_ca14_el_registro_no_lleva_el_mensaje_de_la_excepcion(
    endpoint: Callable[[], None],
    cadena: list[type[BaseException]],
    secretos: list[str],
) -> None:
    """CA-14 · CA-11 esc. 2 · seguridad F001 — el registro conserva tipo y marcos de cada excepción de la cadena, no su texto.

    `format_exc_info` vuelca `str(exc)` y la cadena `__cause__`/`__context__`: un
    `contrasena=...` o un `Key (token)=(...)` de la base llegaría al registro. La traza sigue
    siendo útil (CA-14: contiene la traza y el mismo `correlacion_id`) sin el valor.
    """
    cliente, registro = aplicacion_de_prueba({"/secreto": endpoint})

    respuesta = cliente.post("/prueba/secreto", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_500_minimo(respuesta)
    fallidas = [x for x in lineas_json(registro) if x["event"] == "peticion_fallida"]
    assert len(fallidas) == 1  # anti-verde vacío: el fallo se registró
    assert fallidas[0]["correlacion_id"] == cuerpo["correlacion_id"]
    linea = texto_del_evento(fallidas[0])
    for tipo in cadena:
        assert tipo_calificado(tipo) in linea, f"falta el tipo {tipo_calificado(tipo)} de la cadena"
    assert endpoint.__name__ in linea  # el marco de la ruta
    assert Path(__file__).name in linea
    for secreto in secretos:
        assert secreto not in registro.getvalue()
        assert secreto not in respuesta.text


def test_tkt005_ca14_el_registro_no_lleva_variables_locales() -> None:
    """CA-14 · seguridad F001 (control, nace en verde) — la corrección no puede volcar las variables locales de los marcos."""
    cliente, registro = aplicacion_de_prueba({"/local": lanzar_con_variable_local})

    respuesta = cliente.post("/prueba/local", headers=con_roles("COMPRAS"))

    afirmar_500_minimo(respuesta)
    fallidas = [x for x in lineas_json(registro) if x["event"] == "peticion_fallida"]
    assert len(fallidas) == 1  # anti-verde vacío
    assert "RuntimeError" in texto_del_evento(fallidas[0])
    assert SECRETO_LOCAL not in registro.getvalue()


def test_tkt005_ca15_importe_mal_formado_es_422() -> None:
    """TC-59 · CA-15 esc. 1 · S2 — un importe «1e3» validado con Dinero responde 422 VALIDACION FORMATO."""
    cliente, _ = aplicacion_de_prueba({"/importe": ruta_importe})
    # Guarda contra un falso rojo: el DTO con Dinero acepta una cadena que sí es un decimal llano.
    assert cliente.post("/prueba/importe", json={"importe": "1000"}).status_code == 200

    respuesta = cliente.post("/prueba/importe", json={"importe": "1e3"})

    cuerpo = afirmar_error(respuesta, 422, "ErrorValidacion", CLAVES_VALIDACION)
    assert cuerpo["tipo"] == "VALIDACION"
    assert [(e["campo"], e["codigo"]) for e in cuerpo["errores"]] == [("importe", "FORMATO")]
    for interno in ("Dinero", "Value error", "value_error", "detail"):
        assert interno not in respuesta.text


def test_tkt005_ca15_typeerror_de_un_validador_no_es_422() -> None:
    """TC-59 · CA-15 · D-4 — un TypeError dentro de un validador de Dinero (un float) termina en 500, no en 422."""
    cliente, _ = aplicacion_de_prueba({"/importe": ruta_importe})

    respuesta = cliente.post("/prueba/importe", json={"importe": 1.5})

    assert respuesta.status_code == 500
    cuerpo = afirmar_500_minimo(respuesta)
    assert "tipo" not in cuerpo
    assert "errores" not in cuerpo


@pytest.mark.parametrize("esquema", ESQUEMAS_DE_ERROR)
def test_tkt005_ca14_el_500_no_es_un_tipo(esquema: str) -> None:
    """TC-61 · CA-14 esc. 2 · PA-T5 — el cuerpo del 500 no tiene tipo y ninguno de los ocho esquemas lo valida."""
    cliente, _ = aplicacion_de_prueba({"/interno": lanzar_error_interno})

    respuesta = cliente.post("/prueba/interno", headers=con_roles("COMPRAS"))

    cuerpo = afirmar_500_minimo(respuesta)
    assert "tipo" not in cuerpo
    with pytest.raises(ValidationError):
        validar_contra(esquema, cuerpo)


def test_tkt005_ca15_error_del_programa_no_es_422() -> None:
    """TC-62 · CA-15 esc. 2 — sumar un Dinero y una Cantidad es un defecto del programa: 500, nunca 422."""
    cliente, registro = aplicacion_de_prueba({"/suma": sumar_dinero_y_cantidad})

    respuesta = cliente.post("/prueba/suma", headers=con_roles("COMPRAS"))

    assert respuesta.status_code != 422
    cuerpo = afirmar_500_minimo(respuesta)
    assert "tipo" not in cuerpo
    assert "errores" not in cuerpo
    fallidas = [x for x in lineas_json(registro) if x["event"] == "peticion_fallida"]
    assert len(fallidas) == 1
    assert "TypeError" in texto_del_evento(fallidas[0])
