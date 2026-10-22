"""Manejadores de excepción de la aplicación (TKT-005, fila 6; CA-6, CA-9, CA-10, CA-13).

Hay un manejador por familia, nunca uno por regla: la familia `ErrorContrato`, el error de forma
de Pydantic, el `HTTPException` de Starlette y la excepción no controlada. Todos son `def`
(ADR-013) y serializan por el mismo camino: el cuerpo lo construye la propia excepción del
contrato, con las acciones filtradas por los roles de quien llama. El `msg`, el `type`, el `input`
y el `ctx` de Pydantic nunca llegan al cliente.
"""

import uuid
from collections.abc import Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from contrato_error import (
    CodigoValidacion,
    ErrorContrato,
    ErrorDeCampo,
    NoEncontrado,
    ValidacionRechazada,
)
from servidor.correlacion import CABECERA_CORRELACION

_UBICACIONES = frozenset({"body", "query", "path", "header", "cookie"})
MENSAJE_ERROR_NO_CONTROLADO = (
    "Ocurrió un error inesperado. Cita el identificador de correlación si pides ayuda."
)

MENSAJES: dict[CodigoValidacion, str] = {
    CodigoValidacion.OBLIGATORIO: "El campo es obligatorio.",
    CodigoValidacion.NO_POSITIVO: "El valor debe ser mayor que cero.",
    CodigoValidacion.FUERA_DE_RANGO: "El valor está fuera del rango permitido.",
    CodigoValidacion.DEMASIADO_LARGO: "El valor excede la longitud máxima.",
    CodigoValidacion.VALOR_NO_PERMITIDO: "El valor no está entre los permitidos.",
    CodigoValidacion.FORMATO: "El valor no tiene el formato esperado.",
    CodigoValidacion.FECHA_ANTERIOR_A_VIGENTE: "La fecha es anterior a la vigente.",
}


def campo_de_ubicacion(ubicacion: Sequence[str | int]) -> str:
    """Convierte la ubicación de Pydantic en el nombre de campo del contrato (CA-6).

    `('body', 'renglones', 1, 'cantidad')` pasa a `renglones[1].cantidad`; una ubicación sin campo
    pasa a `cuerpo` `(asumido)`.
    """
    partes = ubicacion[1:] if ubicacion and ubicacion[0] in _UBICACIONES else ubicacion
    texto = ""
    for parte in partes:
        if isinstance(parte, int):
            texto += f"[{parte}]"
        else:
            texto += f".{parte}" if texto else str(parte)
    return texto or "cuerpo"


def codigo_de_error_pydantic(tipo: str, ctx: Mapping[str, object] | None) -> CodigoValidacion:
    """Traduce un tipo de error de Pydantic a uno de los siete códigos de validación (CA-6, PA-T6).

    Todo tipo sin correspondencia conocida cae en `FORMATO` `(asumido)`. Un `ctx` ausente se trata
    como vacío.
    """
    contexto: Mapping[str, object] = ctx or {}
    if tipo == "missing":
        return CodigoValidacion.OBLIGATORIO
    if tipo in {"string_too_short", "too_short"}:
        if contexto.get("min_length") == 1:
            return CodigoValidacion.OBLIGATORIO
        return CodigoValidacion.FUERA_DE_RANGO
    if tipo == "greater_than" and contexto.get("gt") == 0:
        return CodigoValidacion.NO_POSITIVO
    if tipo in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}:
        return CodigoValidacion.FUERA_DE_RANGO
    if tipo in {"string_too_long", "too_long"}:
        return CodigoValidacion.DEMASIADO_LARGO
    if tipo in {"enum", "literal_error", "extra_forbidden"}:
        return CodigoValidacion.VALOR_NO_PERMITIDO
    return CodigoValidacion.FORMATO


def _roles(request: Request) -> frozenset[str]:
    """Roles de quien llama; sin ellos el conjunto es vacío y no se ofrece ninguna acción (CA-9 esc. 4)."""
    return frozenset(getattr(request.state, "roles_de_quien_llama", frozenset()))


def _correlacion(request: Request) -> str:
    return str(getattr(request.state, "correlacion_id", "") or uuid.uuid4())


def _responder(request: Request, error: ErrorContrato) -> JSONResponse:
    return JSONResponse(
        error.cuerpo(_roles(request), _correlacion(request)),
        status_code=error.estado_http,
        headers=error.cabeceras(),
    )


def manejar_error_contrato(request: Request, exc: Exception) -> JSONResponse:
    """CA-13: un solo manejador serializa toda la familia `ErrorContrato`."""
    if not isinstance(exc, ErrorContrato):
        raise exc
    return _responder(request, exc)


def manejar_validacion(request: Request, exc: Exception) -> JSONResponse:
    """CA-6: el `422` de Pydantic sale como `VALIDACION`, sin reflejar `input`, `msg` ni `ctx`."""
    if not isinstance(exc, RequestValidationError):
        raise exc
    errores = []
    for e in exc.errors():
        codigo = codigo_de_error_pydantic(e["type"], e.get("ctx"))
        # `json_invalid` ubica el error en `('body', <desplazamiento>)`: ese entero es la posición
        # del fallo de análisis, no un índice de lista, y no debe llegar al cliente.
        campo = "cuerpo" if e["type"] == "json_invalid" else campo_de_ubicacion(e["loc"])
        errores.append(ErrorDeCampo(campo=campo, codigo=codigo, mensaje=MENSAJES[codigo]))
    return _responder(request, ValidacionRechazada(errores=errores))


def manejar_http(request: Request, exc: Exception) -> Response:
    """El `404` de enrutado es `NO_ENCONTRADO` con la ruta como recurso `(asumido, PA-T4)`; el resto, como FastAPI."""
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    if exc.status_code == 404:
        return _responder(
            request, NoEncontrado(recurso=request.url.path, mensaje="La ruta pedida no existe.")
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


def manejar_error_no_controlado(request: Request, exc: Exception) -> JSONResponse:
    """CA-10, S1: ni traza, ni texto, ni nombre de la excepción; la traza la registra el middleware.

    Este manejador queda fuera del middleware de correlación, así que pone él mismo la cabecera.
    """
    correlacion_id = _correlacion(request)
    return JSONResponse(
        {"mensaje": MENSAJE_ERROR_NO_CONTROLADO, "correlacion_id": correlacion_id},
        status_code=500,
        headers={CABECERA_CORRELACION: correlacion_id},
    )


def registrar_manejadores(aplicacion: FastAPI) -> None:
    """Registra los cuatro manejadores de la aplicación (CA-13)."""
    aplicacion.add_exception_handler(ErrorContrato, manejar_error_contrato)
    aplicacion.add_exception_handler(RequestValidationError, manejar_validacion)
    aplicacion.add_exception_handler(StarletteHTTPException, manejar_http)
    aplicacion.add_exception_handler(Exception, manejar_error_no_controlado)
