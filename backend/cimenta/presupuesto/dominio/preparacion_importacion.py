"""Preparación del análisis antes de confirmar (TKT-015a).

HDU-001 esc. 6 · PA-15.9. Excluye conceptos y análisis rechazados; conserva nodos e insumos por crear.
"""

from __future__ import annotations

from dataclasses import dataclass

from cimenta.presupuesto.dominio.analisis import (
    AnalisisDelLibro,
    AnalisisLeido,
    AsociacionLeida,
    InsumoPorCrear,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, NodoLeido
from cimenta.presupuesto.dominio.clasificacion_importacion import Clasificacion


@dataclass(frozen=True, slots=True)
class Preparacion:
    hoja_catalogo: str | None
    nodos: tuple[NodoLeido, ...]
    conceptos: tuple[ConceptoLeido, ...]
    analisis: tuple[AnalisisLeido, ...]
    asociaciones: tuple[AsociacionLeida, ...]
    insumos_por_crear: tuple[InsumoPorCrear, ...]
    filas_leidas: int
    filas_validas: int
    filas_rechazadas: int


def armar_preparacion(libro: AnalisisDelLibro, clasificacion: Clasificacion) -> Preparacion:
    """Arma la preparación excluyendo filas y hojas rechazadas por la clasificación."""
    catalogo = libro.catalogo
    filas_rechazadas = clasificacion.filas_rechazadas
    hojas_rechazadas = clasificacion.hojas_rechazadas

    conceptos = tuple(c for c in catalogo.conceptos if c.fila not in filas_rechazadas)
    analisis = tuple(a for a in libro.analisis if a.hoja not in hojas_rechazadas)
    asociaciones = tuple(a for a in libro.asociaciones if a.hoja not in hojas_rechazadas)

    filas_leidas = len(catalogo.conceptos)
    n_rechazadas = len(filas_rechazadas)
    filas_validas = filas_leidas - n_rechazadas

    return Preparacion(
        hoja_catalogo=catalogo.hoja,
        nodos=catalogo.nodos,
        conceptos=conceptos,
        analisis=analisis,
        asociaciones=asociaciones,
        insumos_por_crear=libro.insumos_por_crear,
        filas_leidas=filas_leidas,
        filas_validas=filas_validas,
        filas_rechazadas=n_rechazadas,
    )
