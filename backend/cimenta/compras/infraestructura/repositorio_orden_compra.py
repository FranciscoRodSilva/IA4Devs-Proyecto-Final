"""Repositorio de órdenes de compra (TKT-029b, fila F3).

Lectura de los renglones de las órdenes vivas de un proveedor, para que la aplicación derive el estado
de cada orden. Recibe la sesión del caso de uso y no confirma la transacción: no escribe nada.
Las cantidades salen envueltas en `Cantidad` al leerse.
"""

from __future__ import annotations

import uuid
from typing import Any, NamedTuple

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from cimenta.compras.infraestructura.tablas import orden_compra, orden_compra_renglon
from tipos_base import Cantidad


class FilaRenglonDeOrden(NamedTuple):
    orden_id: uuid.UUID
    folio: str
    cantidad_ordenada: Cantidad
    cantidad_recibida: Cantidad


def _fila_renglon_de_orden(fila: Row[*tuple[Any, ...]]) -> FilaRenglonDeOrden:
    return FilaRenglonDeOrden(
        orden_id=fila.id,
        folio=fila.folio,
        cantidad_ordenada=Cantidad(fila.cantidad_ordenada),
        cantidad_recibida=Cantidad(fila.cantidad_recibida),
    )


def leer_renglones_de_ordenes_vivas(
    sesion_bd: Session, proveedor_id: uuid.UUID
) -> list[FilaRenglonDeOrden]:
    """Renglones de las órdenes no canceladas del proveedor, por folio.

    Unión interna: una orden sin renglones no devuelve filas. El orden es `folio` en `COLLATE "C"`
    (igual que el `sorted()` de Python), y luego `id` de la orden y del renglón, para que el desempate
    sea estable.
    """
    sentencia = (
        select(
            orden_compra.c.id,
            orden_compra.c.folio,
            orden_compra_renglon.c.cantidad_ordenada,
            orden_compra_renglon.c.cantidad_recibida,
        )
        .select_from(
            orden_compra.join(
                orden_compra_renglon,
                orden_compra_renglon.c.orden_compra_id == orden_compra.c.id,
            )
        )
        .where(
            orden_compra.c.proveedor_id == proveedor_id,
            orden_compra.c.cancelada_en.is_(None),
        )
        .order_by(
            orden_compra.c.folio.collate("C"),
            orden_compra.c.id,
            orden_compra_renglon.c.id,
        )
    )
    return [_fila_renglon_de_orden(fila) for fila in sesion_bd.execute(sentencia)]
