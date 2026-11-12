"""Pasos de la confirmación de un archivo: estado previo y cotejo con el objeto almacenado.

Implementa PA-T59.8 (solo quien subió el archivo confirma: el solicitante se evalúa antes que el
estado, para que un 403 no revele el estado), PA-T59.13 (un PENDIENTE vencido se trata como caducado
al confirmar) y RNF-19 (el tamaño y el hash del objeto deben coincidir con los declarados; una suma
ausente cuenta como distinta, P-11). El instante llega como argumento: el dominio no importa
`datetime` ni lee el reloj (regla 2 de CLAUDE.md). Sin efectos secundarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self
from uuid import UUID


class Ordenable(Protocol):
    """Instante comparable: el dominio no importa `datetime`, la hora la pone `aplicacion/`."""

    def __lt__(self, otro: Self, /) -> bool: ...


class EstadoArchivo(StrEnum):
    PENDIENTE = "PENDIENTE"
    DISPONIBLE = "DISPONIBLE"
    CADUCADO = "CADUCADO"
    ANULADO = "ANULADO"


class PasoPrevio(StrEnum):
    NO_ES_SOLICITANTE = "NO_ES_SOLICITANTE"
    YA_DISPONIBLE = "YA_DISPONIBLE"
    CADUCADO = "CADUCADO"
    NO_CONFIRMABLE = "NO_CONFIRMABLE"
    VENCIDO = "VENCIDO"
    CONFIRMABLE = "CONFIRMABLE"


class Discrepancia(StrEnum):
    NO_SUBIDO = "NO_SUBIDO"
    TAMANO_DISTINTO = "TAMANO_DISTINTO"
    HASH_DISTINTO = "HASH_DISTINTO"


@dataclass(frozen=True, slots=True)
class ObjetoAlmacenado:
    tamano_bytes: int
    sha256_hex: str | None


def evaluar_previa[T: Ordenable](
    *,
    estado: EstadoArchivo,
    subido_por_id: UUID,
    usuario_id: UUID,
    ahora: T,
    vence_en: T,
) -> PasoPrevio:
    """Implementa PA-T59.8 y PA-T59.13. Sin efectos secundarios.

    En el instante exacto `ahora == vence_en` el archivo todavía se confirma.
    """
    if subido_por_id != usuario_id:
        return PasoPrevio.NO_ES_SOLICITANTE
    if estado is EstadoArchivo.DISPONIBLE:
        return PasoPrevio.YA_DISPONIBLE
    if estado is EstadoArchivo.CADUCADO:
        return PasoPrevio.CADUCADO
    if estado is EstadoArchivo.ANULADO:
        return PasoPrevio.NO_CONFIRMABLE
    if vence_en < ahora:
        return PasoPrevio.VENCIDO
    return PasoPrevio.CONFIRMABLE


def comparar_objeto(
    *, tamano_declarado: int, hash_declarado: str, objeto: ObjetoAlmacenado | None
) -> Discrepancia | None:
    """Implementa RNF-19 y P-11. El tamaño se compara antes que el hash. Sin efectos secundarios."""
    if objeto is None:
        return Discrepancia.NO_SUBIDO
    if objeto.tamano_bytes != tamano_declarado:
        return Discrepancia.TAMANO_DISTINTO
    if objeto.sha256_hex != hash_declarado:
        return Discrepancia.HASH_DISTINTO
    return None
