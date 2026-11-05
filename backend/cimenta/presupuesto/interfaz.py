"""Interfaz publicada de presupuesto: lo único que otro módulo puede importar.

Quién la importa lo fija el contrato grafo-presupuesto de pyproject.toml.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.aplicacion.analisis_importacion import SeguimientoImportacion
from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion
from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorAnalisis

__all__ = [
    "EjecutorAnalisis",
    "crear_ejecutor_analisis",
    "definicion_barrido_importacion",
    "leer_contenido_no_configurado",
]


def crear_ejecutor_analisis(
    fabrica_sesiones: sessionmaker[Session],
    leer_contenido: Callable[[UUID], bytes],
    intervalo: timedelta,
) -> EjecutorAnalisis:
    """Arma el ejecutor del análisis de importación con su seguimiento en base (TKT-015b)."""
    return EjecutorAnalisis(
        seguimiento=SeguimientoImportacion(fabrica_sesiones),
        leer_contenido=leer_contenido,
        intervalo_latido=intervalo,
    )


def leer_contenido_no_configurado(archivo_id: UUID) -> bytes:
    """Origen de bytes por omisión: el almacén de archivos no existe hasta TKT-059.

    El ejecutor lo trata como un archivo ilegible y lleva la importación a `ARCHIVO_ILEGIBLE`.
    """
    raise RuntimeError("el almacén de archivos no está configurado")
