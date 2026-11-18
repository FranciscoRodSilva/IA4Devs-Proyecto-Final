"""Montaje de `presupuesto` en la aplicación (TKT-017b): lo único de `api/` que `servidor/` importa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.presupuesto.api.rutas_linea_base import enrutador
from cimenta.presupuesto.api.rutas_obras import enrutador as enrutador_obras
from cimenta.presupuesto.api.rutas_presupuesto_control import enrutador as enrutador_control
from cimenta.presupuesto.aplicacion.contexto import construir_contexto

if TYPE_CHECKING:
    from cimenta.presupuesto.aplicacion.historial_obra import FuenteHistorialObra


def montar_presupuesto(
    aplicacion: FastAPI,
    *,
    proveedor_motor: Callable[[], Engine],
    reloj: Callable[[], datetime] | None,
    fuentes_historial: tuple[FuenteHistorialObra, ...] = (),
) -> None:
    """Construye el contexto de presupuesto (perezoso) y monta el enrutador de línea base."""
    aplicacion.state.presupuesto = construir_contexto(
        proveedor_motor=proveedor_motor,
        reloj=reloj,
        fuentes_historial=fuentes_historial,
    )
    aplicacion.include_router(enrutador)
    aplicacion.include_router(enrutador_control)
    aplicacion.include_router(enrutador_obras)
