"""Montaje de `identidad` en la aplicación (TKT-006): lo único de `api/` que importa `servidor/`."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.identidad.api.rutas import enrutador
from cimenta.identidad.aplicacion.contexto import construir_contexto


def montar_identidad(
    aplicacion: FastAPI,
    *,
    proveedor_motor: Callable[[], Engine],
    reloj: Callable[[], datetime] | None,
    entorno: Mapping[str, str],
) -> None:
    """Construye el contexto de identidad (perezoso) y monta el enrutador de sesión."""
    aplicacion.state.identidad = construir_contexto(
        proveedor_motor=proveedor_motor, reloj=reloj, entorno=entorno
    )
    aplicacion.include_router(enrutador)
