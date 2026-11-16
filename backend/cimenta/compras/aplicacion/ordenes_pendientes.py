"""Órdenes pendientes de un proveedor (TKT-029b, fila F3). Solo lee.

Lo consume `proveedores` para decidir la baja (CA-12), por `cimenta.compras.interfaz`. No abre
transacción ni confirma: usa la sesión que recibe, como `asentar`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from cimenta.compras.dominio.orden_compra import (
    CantidadesRenglon,
    EstadoOrden,
    esta_pendiente,
    estado_derivado,
)
from cimenta.compras.infraestructura.repositorio_orden_compra import (
    leer_renglones_de_ordenes_vivas,
)


@dataclass(frozen=True, slots=True)
class OrdenPendiente:
    id: uuid.UUID
    folio: str
    estado: EstadoOrden


@dataclass(slots=True)
class _Grupo:
    folio: str
    renglones: list[CantidadesRenglon] = field(default_factory=list)


def ordenes_pendientes_de_proveedor(
    sesion_bd: Session, proveedor_id: uuid.UUID
) -> tuple[OrdenPendiente, ...]:
    """Implementa CA-12 de TKT-029b. Solo lee.

    Agrupa los renglones por orden, conservando el orden de llegada (folio), deriva el estado de cada
    orden y devuelve solo las pendientes (`ABIERTA` y `PARCIAL`).
    """
    grupos: dict[uuid.UUID, _Grupo] = {}
    for fila in leer_renglones_de_ordenes_vivas(sesion_bd, proveedor_id):
        grupo = grupos.setdefault(fila.orden_id, _Grupo(folio=fila.folio))
        grupo.renglones.append(
            CantidadesRenglon(ordenada=fila.cantidad_ordenada, recibida=fila.cantidad_recibida)
        )

    pendientes: list[OrdenPendiente] = []
    for orden_id, grupo in grupos.items():
        estado = estado_derivado(grupo.renglones)
        if esta_pendiente(estado):
            pendientes.append(OrdenPendiente(id=orden_id, folio=grupo.folio, estado=estado))
    return tuple(pendientes)
