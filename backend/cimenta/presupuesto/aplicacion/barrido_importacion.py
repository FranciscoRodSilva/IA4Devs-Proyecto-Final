"""Definición del barrido de importaciones en ANALIZANDO vencidas (TKT-015b)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from cimenta.presupuesto.dominio.importacion import MotivoInterrupcion, error_de_interrupcion
from cimenta.presupuesto.infraestructura import repositorio_importacion as repositorio
from trabajos.barrido import DefinicionBarrido


def definicion_barrido_importacion(umbral: timedelta) -> DefinicionBarrido:
    """Barrido de filas `ANALIZANDO` cuyo `latido` es nulo o anterior al umbral."""
    return DefinicionBarrido(
        nombre="importacion",
        tabla="importacion",
        estado_intermedio="ANALIZANDO",
        estado_vencido="CON_ERRORES",
        columna_marca="latido",
        umbral=umbral,
        al_vencer=_al_vencer,
    )


def _al_vencer(sesion_bd: Session, identificadores: tuple[uuid.UUID, ...]) -> None:
    for importacion_id in identificadores:
        repositorio.insertar_errores(
            sesion_bd,
            importacion_id,
            (error_de_interrupcion(MotivoInterrupcion.REINICIO),),
        )
