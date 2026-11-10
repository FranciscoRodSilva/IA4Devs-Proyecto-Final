"""DTO de la API de presupuesto (TKT-017b1, fila B3). Entrada y salida son modelos distintos.

Los importes salen como cadena de cuatro decimales (`Dinero.serializar()`), nunca como número JSON.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from cimenta.identidad.interfaz import UsuarioResumen
from cimenta.presupuesto.aplicacion.consulta_linea_base import LineaBaseConsultada


def _sin_nul(texto: str) -> str:
    if "\x00" in texto:
        raise ValueError("El motivo no admite el carácter NUL.")
    return texto


MotivoTexto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    AfterValidator(_sin_nul),
]


class Motivo(BaseModel):
    """Cuerpo de la congelación: el motivo es obligatorio y se guarda sin espacios en los extremos."""

    motivo: MotivoTexto


ImporteTexto = Annotated[str, Field(json_schema_extra={"format": "decimal"})]


class EstadoLineaBase(StrEnum):
    BORRADOR = "BORRADOR"
    CONGELADA = "CONGELADA"
    SUPERSEDIDA = "SUPERSEDIDA"


class ClaveTipoPartida(StrEnum):
    MUROS = "MUROS"
    PLAFONES_Y_CAJILLOS = "PLAFONES_Y_CAJILLOS"
    ENCHAPES = "ENCHAPES"
    GENERALES = "GENERALES"


class TipoPartida(BaseModel):
    id: uuid.UUID
    clave: ClaveTipoPartida
    nombre: str


class ImporteDeTipoPartida(BaseModel):
    tipo_partida: TipoPartida
    importe_venta: ImporteTexto


class LineaBase(BaseModel):
    id: uuid.UUID
    obra_id: uuid.UUID
    version: int
    estado: EstadoLineaBase
    importe_venta: ImporteTexto
    congelada_en: datetime | None = None
    congelada_por: UsuarioResumen | None = None
    motivo: str | None = None
    por_tipo_partida: list[ImporteDeTipoPartida]

    @classmethod
    def desde(cls, linea: LineaBaseConsultada) -> LineaBase:
        return cls(
            id=linea.id,
            obra_id=linea.obra_id,
            version=linea.version,
            estado=EstadoLineaBase(linea.estado),
            importe_venta=linea.importe_venta.serializar(),
            congelada_en=linea.congelada_en,
            congelada_por=linea.congelada_por,
            motivo=linea.motivo,
            por_tipo_partida=[
                ImporteDeTipoPartida(
                    tipo_partida=TipoPartida(
                        id=t.tipo_partida_id, clave=ClaveTipoPartida(t.clave), nombre=t.nombre
                    ),
                    importe_venta=t.importe_venta.serializar(),
                )
                for t in linea.por_tipo_partida
            ],
        )
