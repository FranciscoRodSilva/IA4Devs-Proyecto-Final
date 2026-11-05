"""Barrido genérico de filas en estado intermedio vencidas (TKT-015b · ADR-037).

Solo depende de SQLAlchemy y la biblioteca estándar; no importa `cimenta` ni `servidor`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import column, func, or_, table, update
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class DefinicionBarrido:
    """Parámetros de un barrido sobre una tabla con estado y marca temporal."""

    nombre: str
    tabla: str
    estado_intermedio: str
    estado_vencido: str
    columna_marca: str
    umbral: timedelta
    al_vencer: Callable[[Session, tuple[uuid.UUID, ...]], None]
    columna_id: str = "id"
    columna_estado: str = "estado"


def barrer(sesion_bd: Session, definicion: DefinicionBarrido) -> tuple[uuid.UUID, ...]:
    """Marca vencidas las filas en estado intermedio y ejecuta `al_vencer` si hubo cambios."""
    t = table(
        definicion.tabla,
        column(definicion.columna_id),
        column(definicion.columna_estado),
        column(definicion.columna_marca),
    )
    limite = func.now() - definicion.umbral
    sentencia = (
        update(t)
        .where(
            t.c[definicion.columna_estado] == definicion.estado_intermedio,
            or_(
                t.c[definicion.columna_marca].is_(None),
                t.c[definicion.columna_marca] < limite,
            ),
        )
        .values({definicion.columna_estado: definicion.estado_vencido})
        .returning(t.c[definicion.columna_id])
    )
    identificadores = tuple(sesion_bd.scalars(sentencia))
    if identificadores:
        definicion.al_vencer(sesion_bd, identificadores)
    return identificadores


def barrer_todas(
    fabrica_sesiones: sessionmaker[Session],
    definiciones: Sequence[DefinicionBarrido],
) -> dict[str, int]:
    """Ejecuta cada definición en su propia transacción; devuelve `{nombre: cantidad}`."""
    cuentas: dict[str, int] = {}
    for definicion in definiciones:
        sesion = fabrica_sesiones()
        try:
            identificadores = barrer(sesion, definicion)
            sesion.commit()
            cuentas[definicion.nombre] = len(identificadores)
        except Exception:
            sesion.rollback()
            raise
        finally:
            sesion.close()
    return cuentas
