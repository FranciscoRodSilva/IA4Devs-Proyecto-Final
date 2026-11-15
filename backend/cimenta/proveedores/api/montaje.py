"""Montaje de `proveedores` en la aplicación (TKT-029a): lo único de `api/` que `servidor/` importa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.proveedores.api.rutas import enrutador
from cimenta.proveedores.aplicacion.contexto import construir_contexto


def montar_proveedores(
    aplicacion: FastAPI,
    *,
    proveedor_motor: Callable[[], Engine],
    reloj: Callable[[], datetime] | None,
) -> None:
    """Construye el contexto de proveedores (perezoso) y monta su enrutador."""
    aplicacion.state.proveedores = construir_contexto(proveedor_motor=proveedor_motor, reloj=reloj)
    aplicacion.include_router(enrutador)
