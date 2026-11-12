"""Contexto de proveedores: lo que sus casos de uso reciben por inyección (TKT-029a, fila A4).

Mismo patrón que `ContextoPresupuesto`: la fábrica de sesiones es perezosa, así que construir el
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
class ContextoProveedores:
    """Dependencias del módulo `proveedores` para sus casos de uso."""

    fabrica_sesiones: Callable[[], sessionmaker[Session]]
    reloj: Callable[[], datetime]


def _reloj_del_sistema() -> datetime:
    return datetime.now(UTC)


def construir_contexto(
    *, proveedor_motor: Callable[[], Engine], reloj: Callable[[], datetime] | None = None
) -> ContextoProveedores:
    """La fábrica de sesiones pide el motor una sola vez, al primer uso."""

    @functools.cache
    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=proveedor_motor(), expire_on_commit=False)

    return ContextoProveedores(
        fabrica_sesiones=fabrica,
        reloj=reloj if reloj is not None else _reloj_del_sistema,
    )
