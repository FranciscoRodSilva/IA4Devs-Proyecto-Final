"""Contexto de presupuesto: lo que sus casos de uso reciben por inyección (TKT-017, fila A6a).

Mismo patrón que `ContextoIdentidad`: la fábrica de sesiones es perezosa, así que construir el
contexto no abre el motor, y el reloj se inyecta para que ningún caso de uso llame a `datetime.now()`.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class ContextoPresupuesto:
    """Dependencias del módulo `presupuesto` para sus casos de uso."""

    fabrica_sesiones: Callable[[], sessionmaker[Session]]
    reloj: Callable[[], datetime]


def _reloj_del_sistema() -> datetime:
    return datetime.now(UTC)


def construir_contexto(
    *, proveedor_motor: Callable[[], Engine], reloj: Callable[[], datetime] | None = None
) -> ContextoPresupuesto:
    """La fábrica de sesiones pide el motor una sola vez, al primer uso."""

    @functools.cache
    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=proveedor_motor(), expire_on_commit=False)

    return ContextoPresupuesto(
        fabrica_sesiones=fabrica,
        reloj=reloj if reloj is not None else _reloj_del_sistema,
    )
