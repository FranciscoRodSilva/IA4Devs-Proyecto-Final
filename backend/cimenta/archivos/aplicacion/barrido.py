"""Barrido de arranque de los archivos `PENDIENTE` vencidos (TKT-059, fila 15 · CA-10 · ADR-037).

Caduca la subida que no se confirmó a tiempo con el `UPDATE` genérico de `trabajos.barrido`. No
toca el almacén y no tiene efecto al vencer: la fila pasa a `CADUCADO` y nada más.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from trabajos.barrido import DefinicionBarrido


def definicion_barrido_archivo(umbral: timedelta) -> DefinicionBarrido:
    """Barrido de filas `PENDIENTE` cuyo `creado_en` es anterior al umbral. Sin efecto al vencer."""
    return DefinicionBarrido(
        nombre="archivo",
        tabla="archivo",
        estado_intermedio="PENDIENTE",
        estado_vencido="CADUCADO",
        columna_marca="creado_en",
        umbral=umbral,
        al_vencer=_sin_efecto,
    )


def _sin_efecto(sesion_bd: Session, identificadores: tuple[uuid.UUID, ...]) -> None:
    """Un archivo caducado no necesita nada más que su fila: no se toca el almacén ni la bitácora."""
