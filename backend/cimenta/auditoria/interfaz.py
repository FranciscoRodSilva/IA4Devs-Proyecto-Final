"""Interfaz publicada de auditoria: lo único que otro módulo puede importar.

Quién la importa lo fija el contrato grafo-auditoria de pyproject.toml.
"""

from cimenta.auditoria.aplicacion.asentar import asentar, asentar_denegacion
from cimenta.auditoria.aplicacion.consulta import AsientoLeido, PaginaBitacora, consultar_bitacora
from cimenta.auditoria.dominio.asiento import AccionBitacora

__all__ = [
    "AccionBitacora",
    "AsientoLeido",
    "PaginaBitacora",
    "asentar",
    "asentar_denegacion",
    "consultar_bitacora",
]
