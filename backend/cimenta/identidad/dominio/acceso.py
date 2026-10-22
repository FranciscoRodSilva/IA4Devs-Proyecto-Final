"""Decisión de aceptar o rechazar unas credenciales."""

from __future__ import annotations


def credenciales_aceptadas(*, existe: bool, activo: bool, coincide: bool) -> bool:
    """M2 · PA-T4: un desactivado se rechaza igual que una contraseña errónea. Sin RN-xx."""
    return existe and activo and coincide
