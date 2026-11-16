"""Reglas puras del proveedor (TKT-029a, fila A1). Sin efectos secundarios.

Implementa RN-17 (días de corte y de pago por omisión), CA-9 (solo un proveedor ACTIVO admite la
desactivación) y la normalización del RFC aprobada como D-1 del diseño. La baja (TKT-029b) añade
`RechazoBaja` y `rechazo_de_baja`, que decide su rechazo.
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


class RechazoBaja(StrEnum):
    """Por qué un proveedor no admite la baja.

    `ESTADO_TERMINAL`: ya está en `BAJA`. `ORDENES_PENDIENTES`: hay órdenes `ABIERTA` o `PARCIAL`.
    """

    ESTADO_TERMINAL = "ESTADO_TERMINAL"
    ORDENES_PENDIENTES = "ORDENES_PENDIENTES"


def rechazo_de_baja(estado: EstadoProveedor, ordenes_pendientes: int) -> RechazoBaja | None:
    """Implementa CA-1, CA-2, CA-3, CA-4 y CA-7 de TKT-029b. Sin efectos secundarios.

    BAJA es terminal y se evalúa antes que las órdenes pendientes: un proveedor ya dado de baja
    se rechaza por su estado aunque conserve órdenes abiertas.
    """
    if estado is EstadoProveedor.BAJA:
        return RechazoBaja.ESTADO_TERMINAL
    if ordenes_pendientes > 0:
        return RechazoBaja.ORDENES_PENDIENTES
    return None
