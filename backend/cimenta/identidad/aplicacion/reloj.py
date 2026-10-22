"""Reloj inyectable de identidad (TKT-006). Es la única pieza de identidad que toca `datetime`."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

type Reloj = Callable[[], datetime]


def reloj_del_sistema() -> datetime:
    """Devuelve el instante actual en UTC. Las pruebas inyectan otro reloj."""
    return datetime.now(UTC)
