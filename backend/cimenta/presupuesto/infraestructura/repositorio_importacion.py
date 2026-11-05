"""Repositorio de importación de línea base (TKT-015a).

Cada función recibe la sesión del caso de uso y no confirma la transacción.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import NamedTuple, cast

from sqlalchemy import delete, func, insert, null, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from cimenta.presupuesto.dominio.importacion import (
    ErrorImportacion,
    EstadoImportacion,
    TipoErrorImportacion,
)
from cimenta.presupuesto.infraestructura.tablas import importacion, importacion_error, insumo
from tipos_base import Porcentaje


class FilaImportacion(NamedTuple):
    id: uuid.UUID
    obra_id: uuid.UUID
    archivo_id: uuid.UUID
    estado: EstadoImportacion


def bloquear_importacion(sesion_bd: Session, importacion_id: uuid.UUID) -> FilaImportacion | None:
    sentencia = (
        select(
            importacion.c.id,
            importacion.c.obra_id,
            importacion.c.archivo_id,
            importacion.c.estado,
        )
        .where(importacion.c.id == importacion_id)
        .with_for_update()
    )
    fila = sesion_bd.execute(sentencia).one_or_none()
    if fila is None:
        return None
    identificador, obra_id, archivo_id, estado_texto = fila
    return FilaImportacion(
        id=identificador,
        obra_id=obra_id,
        archivo_id=archivo_id,
        estado=EstadoImportacion(estado_texto),
    )


def tipos_de_error(
    sesion_bd: Session, importacion_id: uuid.UUID
) -> frozenset[TipoErrorImportacion]:
    sentencia = (
        select(importacion_error.c.tipo)
        .where(importacion_error.c.importacion_id == importacion_id)
        .distinct()
    )
    return frozenset(TipoErrorImportacion(tipo) for tipo in sesion_bd.scalars(sentencia))


def borrar_errores(sesion_bd: Session, importacion_id: uuid.UUID) -> int:
    resultado = sesion_bd.execute(
        delete(importacion_error).where(importacion_error.c.importacion_id == importacion_id)
    )
    return int(cast(CursorResult, resultado).rowcount)


def pasar_a_analizando(sesion_bd: Session, importacion_id: uuid.UUID) -> None:
    sesion_bd.execute(
        update(importacion)
        .where(importacion.c.id == importacion_id)
        .values(
            estado=EstadoImportacion.ANALIZANDO.value,
            progreso=0,
            latido=func.now(),
            preparacion=null(),
            filas_leidas=null(),
            filas_validas=null(),
            filas_rechazadas=null(),
        )
    )


def insumos_existentes(sesion_bd: Session) -> list[tuple[str, str]]:
    sentencia = select(insumo.c.descripcion, insumo.c.unidad).order_by(insumo.c.codigo)
    return [(str(d), str(u)) for d, u in sesion_bd.execute(sentencia).all()]


def cerrar_analisis(
    sesion_bd: Session,
    importacion_id: uuid.UUID,
    *,
    estado: EstadoImportacion,
    filas_leidas: int,
    filas_validas: int,
    filas_rechazadas: int,
    preparacion: dict[str, object],
) -> bool:
    sentencia = (
        update(importacion)
        .where(
            importacion.c.id == importacion_id,
            importacion.c.estado == EstadoImportacion.ANALIZANDO.value,
        )
        .values(
            estado=estado.value,
            progreso=1,
            latido=func.now(),
            filas_leidas=filas_leidas,
            filas_validas=filas_validas,
            filas_rechazadas=filas_rechazadas,
            preparacion=preparacion,
        )
        .returning(importacion.c.id)
    )
    return sesion_bd.execute(sentencia).one_or_none() is not None


def interrumpir(sesion_bd: Session, importacion_id: uuid.UUID) -> bool:
    sentencia = (
        update(importacion)
        .where(
            importacion.c.id == importacion_id,
            importacion.c.estado == EstadoImportacion.ANALIZANDO.value,
        )
        .values(
            estado=EstadoImportacion.CON_ERRORES.value,
            latido=func.now(),
        )
        .returning(importacion.c.id)
    )
    return sesion_bd.execute(sentencia).one_or_none() is not None


def insertar_errores(
    sesion_bd: Session,
    importacion_id: uuid.UUID,
    errores: Sequence[ErrorImportacion],
) -> None:
    if not errores:
        return
    filas = [
        {
            "id": uuid.uuid4(),
            "importacion_id": importacion_id,
            "hoja": error.hoja,
            "fila": error.fila,
            "columna": error.columna,
            "tipo": str(error.tipo),
            "mensaje": error.mensaje,
            "valor_original": error.valor_original,
        }
        for error in errores
    ]
    sesion_bd.execute(insert(importacion_error), filas)


def refrescar_latido(sesion_bd: Session, ids: Sequence[uuid.UUID]) -> None:
    """TKT-015b · CA-13 — renueva el latido de las importaciones que siguen `ANALIZANDO`."""
    if not ids:
        return
    sesion_bd.execute(
        update(importacion)
        .where(
            importacion.c.id.in_(list(ids)),
            importacion.c.estado == EstadoImportacion.ANALIZANDO.value,
        )
        .values(latido=func.now())
    )


def registrar_progreso(sesion_bd: Session, importacion_id: uuid.UUID, progreso: Porcentaje) -> None:
    """TKT-015b · CA-13 — el progreso nunca baja: `GREATEST` con el valor guardado."""
    sesion_bd.execute(
        update(importacion)
        .where(
            importacion.c.id == importacion_id,
            importacion.c.estado == EstadoImportacion.ANALIZANDO.value,
        )
        .values(
            progreso=func.greatest(func.coalesce(importacion.c.progreso, 0), progreso.valor),
            latido=func.now(),
        )
    )


def leer_preparacion(sesion_bd: Session, importacion_id: uuid.UUID) -> dict[str, object] | None:
    sentencia = select(importacion.c.preparacion).where(importacion.c.id == importacion_id)
    valor = sesion_bd.scalar(sentencia)
    if valor is None:
        return None
    return dict(valor) if isinstance(valor, dict) else None
