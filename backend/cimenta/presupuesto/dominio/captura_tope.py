"""Regla de decisión de la captura del tope de un tipo de partida (TKT-017c, fila C1).

Sin efectos secundarios. El caso de uso carga el tope anterior y el importe de venta, y traduce la
causa a su contrato de error.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tipos_base import Dinero

__all__ = [
    "CapturaAdmitida",
    "CapturaRechazada",
    "CausaRechazoCaptura",
    "ResultadoCaptura",
    "evaluar_captura_tope",
    "sin_blanco",
]


class CausaRechazoCaptura(StrEnum):
    TOPE_SUPERIOR_SIN_CONFIRMAR = "TOPE_SUPERIOR_SIN_CONFIRMAR"
    MOTIVO_OBLIGATORIO = "MOTIVO_OBLIGATORIO"


@dataclass(frozen=True, slots=True)
class CapturaAdmitida:
    """La captura se admite; `es_recaptura` indica que sustituye a un tope anterior."""

    es_recaptura: bool


@dataclass(frozen=True, slots=True)
class CapturaRechazada:
    """Causa del rechazo, que el caso de uso vuelve contrato de error."""

    causa: CausaRechazoCaptura


type ResultadoCaptura = CapturaAdmitida | CapturaRechazada


def sin_blanco(motivo: str | None) -> str | None:
    """Devuelve el motivo tal cual, o `None` si falta o solo tiene espacios en blanco."""
    return motivo if motivo is not None and motivo.strip() else None


def _motivo_ausente(motivo: str | None) -> bool:
    return sin_blanco(motivo) is None


def evaluar_captura_tope(
    *,
    tope_anterior: Dinero | None,
    tope_nuevo: Dinero,
    importe_venta: Dinero,
    motivo: str | None,
    confirmar_superior_a_venta: bool,
) -> ResultadoCaptura:
    """Implementa RN-03, RN-04, PA-03 (CA-C2 a CA-C5). Sin efectos secundarios.

    Orden: primero el tope superior a la venta sin confirmar y después el motivo, que se exige al
    superar la venta (confirmado) y en toda recaptura. Un tope igual a la venta no supera nada.
    """
    supera_la_venta = tope_nuevo.valor > importe_venta.valor
    if supera_la_venta and not confirmar_superior_a_venta:
        return CapturaRechazada(CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR)
    es_recaptura = tope_anterior is not None
    if (supera_la_venta or es_recaptura) and _motivo_ausente(motivo):
        return CapturaRechazada(CausaRechazoCaptura.MOTIVO_OBLIGATORIO)
    return CapturaAdmitida(es_recaptura=es_recaptura)
