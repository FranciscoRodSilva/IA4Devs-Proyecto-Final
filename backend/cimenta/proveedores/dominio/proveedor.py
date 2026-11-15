"""Reglas puras del proveedor (TKT-029a, fila A1). Sin efectos secundarios.

Implementa RN-17 (días de corte y de pago por omisión), CA-9 (solo un proveedor ACTIVO admite la
desactivación) y la normalización del RFC aprobada como D-1 del diseño.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class EstadoProveedor(StrEnum):
    ACTIVO = "ACTIVO"
    DESACTIVADO = "DESACTIVADO"
    BAJA = "BAJA"


# Implementa RN-17: el corte de facturación es el jueves (ISO 8601, lunes = 1) y el pago, el sábado.
DIA_CORTE_POR_OMISION: Final = 4
DIA_PAGO_POR_OMISION: Final = 6


def normalizar_rfc(rfc: str) -> str:
    """Implementa D-1 (supuesto 1 de la spec). Sin efectos secundarios.

    Solo recorta espacios ASCII. Un `strip()` sin argumento quitaría también el salto de línea
    final, y el patrón de la forma del RFC tendría que rechazar por 422 (CA-4) lo que el cliente
    envió; por eso el recorte es explícito y el resto de los espacios queda para la validación.
    """
    return rfc.strip(" ").upper()


def admite_desactivacion(estado: EstadoProveedor) -> bool:
    """Implementa CA-9. Sin efectos secundarios.

    Solo un proveedor ACTIVO puede desactivarse; un DESACTIVADO o un BAJA se rechazan.
    """
    return estado is EstadoProveedor.ACTIVO
