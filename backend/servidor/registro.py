"""Registro técnico estructurado de la aplicación (RNF-13, TKT-005 fila 5).

Una excepción se registra como tipo y marcos, nunca con su texto: el mensaje de una excepción puede
llevar un valor sensible (una contraseña en una cadena de conexión, el `Key (token)=(...)` de un
error de la base), y `str(exc)` y las variables locales de los marcos no entran al registro.
"""

import logging
import sys
import traceback
from types import TracebackType
from typing import TextIO

import structlog
from structlog.typing import EventDict, WrappedLogger

_LIMITE_DE_CADENA = 20
_REGISTRO_DE_UVICORN = "uvicorn.error"


def _tipo_calificado(exc: BaseException) -> str:
    """`modulo.Qualname` para los tipos propios; para los integrados basta el nombre."""
    tipo = type(exc)
    if tipo.__module__ == "builtins":
        return tipo.__qualname__
    return f"{tipo.__module__}.{tipo.__qualname__}"


def _marcos(trazado: TracebackType | None) -> list[str]:
    return [
        f"{marco.f_code.co_filename}:{linea} {marco.f_code.co_name}"
        for marco, linea in traceback.walk_tb(trazado)
    ]


def resumir_excepcion(exc: BaseException) -> list[dict[str, object]]:
    """Tipo y marcos de cada excepción de la cadena `__cause__`/`__context__`, sin `str(exc)`.

    La cadena se recorre de la más externa a la más interna y se corta si es cíclica o muy larga.
    """
    resumen: list[dict[str, object]] = []
    vistas: set[int] = set()
    actual: BaseException | None = exc
    while actual is not None and id(actual) not in vistas and len(resumen) < _LIMITE_DE_CADENA:
        vistas.add(id(actual))
        resumen.append({"tipo": _tipo_calificado(actual), "marcos": _marcos(actual.__traceback__)})
        actual = actual.__cause__ or actual.__context__
    return resumen


def texto_de_resumen(resumen: list[dict[str, object]]) -> str:
    """El resumen como texto plano de varias líneas, para el registro de uvicorn."""
    lineas: list[str] = []
    for elemento in resumen:
        lineas.append(str(elemento["tipo"]))
        marcos = elemento["marcos"]
        if isinstance(marcos, list):
            lineas.extend(f"  {marco}" for marco in marcos)
    return "\n".join(lineas)


def _excepcion_de(exc_info: object) -> BaseException | None:
    if exc_info is True:
        return sys.exc_info()[1]
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        return exc_info[1] if isinstance(exc_info[1], BaseException) else None
    return None


def resumir_excepcion_del_evento(
    _registro: WrappedLogger, _metodo: str, evento: EventDict
) -> EventDict:
    """Procesador de structlog que sustituye `exc_info` por `excepciones`: tipo y marcos, sin texto."""
    exc_info = evento.pop("exc_info", None)
    if exc_info:
        exc = _excepcion_de(exc_info)
        if exc is not None:
            evento["excepciones"] = resumir_excepcion(exc)
    return evento


class FiltroSinTextoDeExcepcion(logging.Filter):
    """Deja en el registro de uvicorn solo el tipo y los marcos de la excepción, sin su mensaje.

    Starlette responde el 500 y vuelve a lanzar la excepción; uvicorn la imprime en texto plano con
    `str(exc)`. Se eligió este filtro y no capturar en `MiddlewareCorrelacion` porque no mueve quién
    emite el 500 ni duplica su manejador: el comportamiento observable no cambia.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exc = _excepcion_de(record.exc_info)
        if exc is not None:
            texto = texto_de_resumen(resumir_excepcion(exc))
            record.msg = f"{record.getMessage().rstrip()}\n{texto}"
            record.args = None
            record.exc_info = None
            record.exc_text = None
        return True


def _instalar_filtro_de_uvicorn() -> None:
    """Idempotente: llamarla otra vez no añade un segundo filtro."""
    registro = logging.getLogger(_REGISTRO_DE_UVICORN)
    if not any(isinstance(f, FiltroSinTextoDeExcepcion) for f in registro.filters):
        registro.addFilter(FiltroSinTextoDeExcepcion())


def configurar_registro(destino: TextIO) -> None:
    """RNF-13: una línea JSON por evento, con la correlación de la petición. Nunca cuerpos ni cabeceras.

    `cache_logger_on_first_use=False` es obligatorio: cada prueba reconfigura el destino.
    `logging` solo aporta la constante del nivel y el filtro del registro de uvicorn.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            resumir_excepcion_del_evento,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(destino),
        cache_logger_on_first_use=False,
    )
    _instalar_filtro_de_uvicorn()
