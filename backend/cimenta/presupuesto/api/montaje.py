"""Montaje de `presupuesto` en la aplicación (TKT-017b): lo único de `api/` que `servidor/` importa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.presupuesto.api.rutas_linea_base import enrutador
from cimenta.presupuesto.aplicacion.contexto import construir_contexto


def montar_presupuesto(
    aplicacion: FastAPI,
    *,
    proveedor_motor: Callable[[], Engine],
    reloj: Callable[[], datetime] | None,
) -> None:
    """Construye el contexto de presupuesto (perezoso) y monta el enrutador de línea base."""
    aplicacion.state.presupuesto = construir_contexto(proveedor_motor=proveedor_motor, reloj=reloj)
    aplicacion.include_router(enrutador)
