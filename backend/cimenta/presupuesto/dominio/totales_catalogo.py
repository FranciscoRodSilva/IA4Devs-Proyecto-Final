"""Totales de previsualización del catálogo leído (TKT-013b · S1 · HDU-001 esc. 5)."""

from __future__ import annotations

from dataclasses import dataclass

from cimenta.presupuesto.dominio.catalogo import CatalogoLeido, ConceptoLeido, Profundidad
from tipos_base import Dinero, sumar


@dataclass(frozen=True, slots=True)
class TotalesCatalogo:
    niveles: int
    areas: int
    partidas: int
    conceptos: int
    importe: Dinero | None


def importe_calculado(concepto: ConceptoLeido) -> Dinero | None:
    """cantidad × precio unitario, exacto y sin cuantizar; None si falta cualquiera de los dos."""
    if concepto.cantidad is None or concepto.precio_unitario is None:
        return None
    return concepto.cantidad * concepto.precio_unitario


def totalizar(catalogo: CatalogoLeido) -> TotalesCatalogo:
    """Cuenta nodos por profundidad y suma importes calculables."""
    niveles = sum(1 for n in catalogo.nodos if n.profundidad is Profundidad.NIVEL)
    areas = sum(1 for n in catalogo.nodos if n.profundidad is Profundidad.AREA)
    partidas = sum(1 for n in catalogo.nodos if n.profundidad is Profundidad.PARTIDA)
    conceptos = len(catalogo.conceptos)

    importes: list[Dinero] = []
    for concepto in catalogo.conceptos:
        calculado = importe_calculado(concepto)
        if calculado is None:
            return TotalesCatalogo(
                niveles=niveles,
                areas=areas,
                partidas=partidas,
                conceptos=conceptos,
                importe=None,
            )
        importes.append(calculado)

    importe_total = sumar(importes, Dinero) if importes else None
    return TotalesCatalogo(
        niveles=niveles,
        areas=areas,
        partidas=partidas,
        conceptos=conceptos,
        importe=importe_total,
    )
