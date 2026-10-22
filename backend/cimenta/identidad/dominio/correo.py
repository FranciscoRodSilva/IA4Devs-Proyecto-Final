"""Normalización del correo de una persona usuaria."""

from __future__ import annotations


def normalizar_correo(correo: str) -> str:
    """M11 · PA-T10: el correo se compara en minúsculas. Sin RN-xx."""
    return correo.lower()
