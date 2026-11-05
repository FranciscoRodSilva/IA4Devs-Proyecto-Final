"""Análisis síncrono del contenido de una importación (TKT-015a).

Orquesta lectura, clasificación y serialización de la preparación para el trabajador
y las pruebas en hilo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cimenta.presupuesto.dominio.clasificacion_importacion import clasificar_libro
from cimenta.presupuesto.dominio.importacion import ErrorImportacion
from cimenta.presupuesto.dominio.preparacion_importacion import armar_preparacion
from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto
from cimenta.presupuesto.infraestructura.preparacion_json import preparacion_a_json


@dataclass(frozen=True, slots=True)
class ResultadoAnalisis:
    errores: tuple[ErrorImportacion, ...]
    preparacion: dict[str, object]
    filas_leidas: int
    filas_validas: int
    filas_rechazadas: int


def analizar_contenido(
    contenido: bytes,
    insumos_existentes: Mapping[str, str],
) -> ResultadoAnalisis:
    """Lee el libro, clasifica hallazgos y devuelve errores y preparación serializada."""
    libro = leer_libro_presupuesto(contenido, insumos_existentes)
    clasificacion = clasificar_libro(libro)
    preparacion = armar_preparacion(libro, clasificacion)
    return ResultadoAnalisis(
        errores=clasificacion.errores,
        preparacion=preparacion_a_json(preparacion),
        filas_leidas=preparacion.filas_leidas,
        filas_validas=preparacion.filas_validas,
        filas_rechazadas=preparacion.filas_rechazadas,
    )
