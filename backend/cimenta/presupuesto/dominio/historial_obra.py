"""Regla pura de «¿tiene historial?», TKT-012b (fila A2). RN-01 · HDU-001 esc. 20.

RN-01 protege el presupuesto congelado: una obra con historial no se borra. La lista de fuentes es
la de HDU-001 esc. 20 y la decisión D-1 de la spec. `linea_base_congelada` solo alimenta el detalle
del `409`; no decide, porque una congelada implica al menos una línea base.

`(asumido)` D-DIS-5: una línea base de cualquier estado, incluida `BORRADOR`, ya es historial. La
persona dueña no lo ha confirmado; si lo cambia, cambia el caso `lineas_base-borrador` de los tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConteosHistorial:
    lineas_base: int
    linea_base_congelada: bool
    importaciones: int
    filas_propias: int
    movimientos: int


def hay_historial(conteos: ConteosHistorial) -> bool:
    """Implementa RN-01 (HDU-001 esc. 20). Sin efectos secundarios.

    Basta con que cualquier conteo sea mayor que cero. La bandera de línea base congelada no entra.
    """
    return (
        conteos.lineas_base > 0
        or conteos.importaciones > 0
        or conteos.filas_propias > 0
        or conteos.movimientos > 0
    )
