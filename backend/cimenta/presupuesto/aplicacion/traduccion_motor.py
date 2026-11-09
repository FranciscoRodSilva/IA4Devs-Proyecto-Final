"""Traducción de los `SQLSTATE` del motor al contrato de error (TKT-017, fila A5, ADR-031).

Implementa `RN-01` en su frontera con PostgreSQL: lo que el dominio no alcanzó a impedir, el
disparador de inmutabilidad (`IN001`) y el índice parcial de línea base congelada lo detienen, y este
módulo lo convierte en el mismo `409` que habría dado la regla. Sigue «Traducción del motor» y
«Mensajes y detalles exactos» del diseño de TKT-017. No abre transacción: `rechazo_vigente` abre la
suya cuando hace falta. Lo que el diseño no nombra devuelve `None` y el caso de uso relanza.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import DBAPIError

from contrato_error.acciones import Accion
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    RechazoRegla,
)

_RESTRICCION_CONGELADA_VIGENTE = "uq_linea_base_obra_id_congelada"
_MENSAJE_IN001 = "La línea base congelada no se modifica."
_MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
_MENSAJE_TIEMPO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."
_MENSAJE_CONFLICTO = "La operación entra en conflicto con el estado actual de los datos."
MENSAJE_PREPARACION_ILEGIBLE = (
    "La preparación de la importación no se puede leer; la importación debe analizarse de nuevo."
)
_ESPERA_BLOQUEO_MS = 5000
_ESPERA_EJECUCION_MS = 15000


def traducir_error_del_motor(
    error: DBAPIError,
    *,
    ruta_reintento: str,
    metodo_reintento: str,
    roles_reintento: tuple[str, ...],
    rechazo_vigente: Callable[[], ErrorContrato],
) -> ErrorContrato | None:
    """Traduce un `DBAPIError` a su `ErrorContrato`, o `None` si el diseño no lo contempla (RN-01)."""
    sqlstate = getattr(error.orig, "sqlstate", None)
    diag = getattr(error.orig, "diag", None)
    restriccion = getattr(diag, "constraint_name", None)

    if sqlstate == "IN001":
        return RechazoRegla(
            regla="RN-01",
            mensaje=_MENSAJE_IN001,
            detalle={"tabla": getattr(diag, "table_name", None)},
            acciones=(),
        )
    if sqlstate == "23505" and restriccion == _RESTRICCION_CONGELADA_VIGENTE:
        return rechazo_vigente()
    if sqlstate in {"23505", "23503", "23001"}:
        return ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_CONFLICTO,
            detalle={"restriccion": restriccion},
            acciones=(),
        )
    if sqlstate == "22003":
        return ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=MENSAJE_PREPARACION_ILEGIBLE,
            detalle={},
            acciones=(),
        )
    if sqlstate == "55P03":
        return _concurrencia(
            "BLOQUEO_VENCIDO",
            _MENSAJE_BLOQUEO,
            _ESPERA_BLOQUEO_MS,
            Accion("REINTENTAR", metodo_reintento, ruta_reintento, roles_reintento),
        )
    if sqlstate == "57014":
        return _concurrencia(
            "TIEMPO_EJECUCION_VENCIDO",
            _MENSAJE_TIEMPO,
            _ESPERA_EJECUCION_MS,
            Accion("REINTENTAR", metodo_reintento, ruta_reintento, roles_reintento),
        )
    return None


def _concurrencia(
    codigo: str, mensaje: str, espera_maxima_ms: int, reintentar: Accion
) -> ConcurrenciaVencida:
    return ConcurrenciaVencida(
        codigo=codigo,
        mensaje=mensaje,
        espera_maxima_ms=espera_maxima_ms,
        reintentar_en_s=1,
        acciones=(reintentar,),
    )
