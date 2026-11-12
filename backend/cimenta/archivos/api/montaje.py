"""Montaje de `archivos` en la aplicación (TKT-059, fila 12a): lo único de `api/` que `servidor/` importa."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.archivos.api.rutas import enrutador
from cimenta.archivos.aplicacion.contexto import ConfiguracionArchivos, construir_contexto
from cimenta.archivos.aplicacion.puertos import AlmacenObjetos


def montar_archivos(
    aplicacion: FastAPI,
    *,
    proveedor_motor: Callable[[], Engine],
    proveedor_almacen: Callable[[], AlmacenObjetos],
    configuracion: ConfiguracionArchivos,
    reloj: Callable[[], datetime] | None,
) -> None:
    """Construye el contexto de archivos (perezoso) y monta el enrutador."""
    aplicacion.state.archivos = construir_contexto(
        proveedor_motor=proveedor_motor,
        proveedor_almacen=proveedor_almacen,
        configuracion=configuracion,
        reloj=reloj,
    )
    aplicacion.include_router(enrutador)
