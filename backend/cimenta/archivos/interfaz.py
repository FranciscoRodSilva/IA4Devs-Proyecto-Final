"""Interfaz publicada de archivos: lo único que otro módulo puede importar.

Quién la importa lo fija el contrato grafo-archivos de pyproject.toml. Desde TKT-059 fila 8 la
publica la composición de `servidor/fabrica.py`: el contexto, sus ajustes y el adaptador del almacén.
Desde la fila 9 publica también el alta (`registrar_archivo`) y la dependencia de la ruta.
"""

from __future__ import annotations

from cimenta.archivos.api.dependencias import contexto_de_archivos
from cimenta.archivos.aplicacion.alta import AltaArchivo, registrar_archivo
from cimenta.archivos.aplicacion.contexto import (
    AlmacenNoConfigurado,
    ConfiguracionArchivos,
    ContextoArchivos,
    construir_contexto,
)
from cimenta.archivos.aplicacion.puertos import AlmacenObjetos
from cimenta.archivos.dominio.declaracion import LimitesArchivo
from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

__all__ = [
    "AlmacenNoConfigurado",
    "AlmacenObjetos",
    "AltaArchivo",
    "ConfiguracionArchivos",
    "ContextoArchivos",
    "LimitesArchivo",
    "construir_contexto",
    "contexto_de_archivos",
    "crear_almacen_s3",
    "registrar_archivo",
]
