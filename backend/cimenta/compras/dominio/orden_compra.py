"""Estado derivado de una orden de compra (TKT-029b, fila F2). Sin efectos secundarios.

Implementa la derivación de `docs/03` §1 y §14 (orden de compra): el estado de una orden sale de
comparar lo ordenado con lo recibido en sus renglones, no de una columna que alguien pueda escribir.
La definición de «pendiente» es el supuesto 1 del diseño (D-1) y el caso de la secuencia vacía, el
supuesto 2 (D-2). El contexto de la regla es `RN-06`: la orden es el documento que el almacén recibe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from tipos_base import Cantidad

_CERO: Final = Cantidad("0")


class EstadoOrden(StrEnum):
    ABIERTA = "ABIERTA"
    PARCIAL = "PARCIAL"
    CERRADA = "CERRADA"


@dataclass(frozen=True, slots=True)
class CantidadesRenglon:
    ordenada: Cantidad
    recibida: Cantidad


def estado_derivado(renglones: Sequence[CantidadesRenglon]) -> EstadoOrden:
    """Implementa CA-5 y CA-12 de TKT-029b (D-1 y D-2). Sin efectos secundarios.

    Deriva el estado de una orden a partir de sus renglones.

    Un renglón con `recibida` por debajo de `ordenada` deja saldo. Sin saldo la orden está CERRADA,
    también sin renglones: no hay material por recibir. Con saldo, es PARCIAL si algo ya se recibió
    y ABIERTA si no. Un excedente autorizado (`recibida` mayor que `ordenada`) no deja saldo.
    """
    if not any(_tiene_saldo(renglon) for renglon in renglones):
        return EstadoOrden.CERRADA
    if any(_tiene_recibido(renglon) for renglon in renglones):
        return EstadoOrden.PARCIAL
    return EstadoOrden.ABIERTA


def esta_pendiente(estado: EstadoOrden) -> bool:
    """Implementa la definición de pendiente de D-1 y `CA-12`. Sin efectos secundarios.

    Pendiente es lo que todavía espera material: ABIERTA y PARCIAL. Una orden CERRADA no bloquea.
    """
    return estado in (EstadoOrden.ABIERTA, EstadoOrden.PARCIAL)


def _tiene_saldo(renglon: CantidadesRenglon) -> bool:
    return renglon.recibida < renglon.ordenada


def _tiene_recibido(renglon: CantidadesRenglon) -> bool:
    return renglon.recibida > _CERO
