"""Permisos por rol y la regla de que nadie resuelve lo que solicitó."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


def rol_suficiente(roles_de_quien_llama: frozenset[str], roles_requeridos: frozenset[str]) -> bool:
    """M7 · arquitectura §7.1: el permiso efectivo es la unión de los roles; basta uno."""
    return not roles_requeridos.isdisjoint(roles_de_quien_llama)


class MotivoNegacion(StrEnum):
    AUTO_RESOLUCION = "AUTO_RESOLUCION"


@dataclass(frozen=True, slots=True)
class ResultadoResolucion:
    permitida: bool
    motivo: MotivoNegacion | None


def evaluar_resolucion(
    *, solicitante_id: uuid.UUID, resolutor_id: uuid.UUID
) -> ResultadoResolucion:
    """M8 · arquitectura §7.1 · HDU-003 esc. 8. Sin RN-xx (PA-T1, asumido).
    Nadie resuelve lo que solicitó, tenga el rol que tenga: por eso la función no recibe roles.
    La falta de rol es ROL_INSUFICIENTE y la decide api/. Nunca lanza."""
    if solicitante_id == resolutor_id:
        return ResultadoResolucion(permitida=False, motivo=MotivoNegacion.AUTO_RESOLUCION)
    return ResultadoResolucion(permitida=True, motivo=None)
