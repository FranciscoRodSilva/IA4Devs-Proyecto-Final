"""Repositorio de la bitácora (TKT-007). Ninguna función confirma: la transacción es de quien llama."""

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import ColumnElement

from cimenta.auditoria.dominio.asiento import AccionBitacora, Asiento
from cimenta.auditoria.infraestructura.modelos import FilaBitacora


@dataclass(frozen=True, slots=True)
class CriteriosBitacora:
    obra_id: uuid.UUID | None
    regla_negocio: str | None
    entidad_tipo: str | None
    entidad_id: uuid.UUID | None
    acciones: tuple[AccionBitacora, ...]
    usuario_id: uuid.UUID | None
    desde: dt.datetime | None
    hasta: dt.datetime | None


def insertar_asiento(
    sesion_bd: Session, *, asiento_id: uuid.UUID, ocurrido_en: dt.datetime, asiento: Asiento
) -> None:
    """Una sola sentencia INSERT en la transacción abierta por quien llama (RN-04)."""
    sesion_bd.execute(
        insert(FilaBitacora).values(
            id=asiento_id,
            entidad_tipo=asiento.entidad_tipo,
            entidad_id=asiento.entidad_id,
            accion=asiento.accion,
            usuario_id=asiento.usuario_id,
            ocurrido_en=ocurrido_en,
            datos_antes=asiento.datos_antes,
            datos_despues=asiento.datos_despues,
            motivo=asiento.motivo,
            regla_negocio=asiento.regla_negocio,
            obra_id=asiento.obra_id,
        )
    )


def _condiciones(c: CriteriosBitacora) -> list[ColumnElement[bool]]:
    t = FilaBitacora.__table__.c
    condiciones: list[ColumnElement[bool]] = []
    if c.obra_id is not None:
        condiciones.append(t.obra_id == c.obra_id)
    if c.regla_negocio is not None:
        condiciones.append(t.regla_negocio == c.regla_negocio)
    if c.entidad_tipo is not None:
        condiciones.append(t.entidad_tipo == c.entidad_tipo)
    if c.entidad_id is not None:
        condiciones.append(t.entidad_id == c.entidad_id)
    if c.acciones:
        condiciones.append(t.accion.in_(c.acciones))
    if c.usuario_id is not None:
        condiciones.append(t.usuario_id == c.usuario_id)
    if c.desde is not None:
        condiciones.append(t.ocurrido_en >= c.desde)
    if c.hasta is not None:
        condiciones.append(t.ocurrido_en < c.hasta)
    return condiciones


def contar_asientos(sesion_bd: Session, criterios: CriteriosBitacora) -> int:
    return sesion_bd.execute(
        select(func.count()).select_from(FilaBitacora.__table__).where(*_condiciones(criterios))
    ).scalar_one()


def leer_asientos(
    sesion_bd: Session, criterios: CriteriosBitacora, *, limite: int, desplazamiento: int
) -> list[dict[str, Any]]:
    # Any: son las once columnas de la tabla; AsientoLeido(**fila) vuelve a tiparlas.
    t = FilaBitacora.__table__
    filas = (
        sesion_bd.execute(
            select(t)
            .where(*_condiciones(criterios))
            .order_by(t.c.ocurrido_en.desc(), t.c.id.desc())
            .limit(limite)
            .offset(desplazamiento)
        )
        .mappings()
        .all()
    )
    return [dict(fila) for fila in filas]
