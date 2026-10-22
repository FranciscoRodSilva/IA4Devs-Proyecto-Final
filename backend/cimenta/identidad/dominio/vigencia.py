"""Vigencia de una sesión con estado en el servidor."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, Self


class Ordenable(Protocol):
    """Instante comparable: el dominio no importa `datetime`, la hora la pone `aplicacion/`."""

    def __lt__(self, otro: Self, /) -> bool: ...


class EstadoSesion(StrEnum):
    VIGENTE = "VIGENTE"
    CADUCADA = "CADUCADA"
    REVOCADA = "REVOCADA"


def evaluar_vigencia[T: Ordenable](
    *, ahora: T, expira_en: T, vence_por_inactividad_en: T, revocada: bool, usuario_activo: bool
) -> EstadoSesion:
    """RNF-01 · ADR-014. Sin RN-xx. Precedencia: revocada, usuario desactivado (PA-T3),
    caducidad absoluta, inactividad. En el instante exacto del límite la sesión ya caducó."""
    if revocada or not usuario_activo:
        return EstadoSesion.REVOCADA
    if not ahora < expira_en:
        return EstadoSesion.CADUCADA
    if not ahora < vence_por_inactividad_en:
        return EstadoSesion.CADUCADA
    return EstadoSesion.VIGENTE
