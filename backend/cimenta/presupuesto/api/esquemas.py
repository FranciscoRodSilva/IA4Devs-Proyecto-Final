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
from cimenta.presupuesto.aplicacion.consulta_linea_base import (
    ConceptosConsultados,
    ExplosionConsultada,
    LineaBaseConsultada,
    TipoPartidaConsultado,
)


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


class Unidad(StrEnum):
    M2 = "M2"
    ML = "ML"
    PZA = "PZA"
    KG = "KG"
    CAJA = "CAJA"
    SACO = "SACO"
    ROLLO = "ROLLO"
    JORNAL = "JORNAL"


class TipoPartida(BaseModel):
    id: uuid.UUID
    clave: ClaveTipoPartida
    nombre: str

    @classmethod
    def desde(cls, tipo: TipoPartidaConsultado) -> TipoPartida:
        return cls(id=tipo.id, clave=ClaveTipoPartida(tipo.clave), nombre=tipo.nombre)


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
                    tipo_partida=TipoPartida.desde(t.tipo_partida),
                    importe_venta=t.importe_venta.serializar(),
                )
                for t in linea.por_tipo_partida
            ],
        )


class MetaPagina(BaseModel):
    pagina: Annotated[int, Field(ge=1)]
    tamano_pagina: Annotated[int, Field(ge=1)]
    total: Annotated[int, Field(ge=0)]


class ConceptoLineaBase(BaseModel):
    id: uuid.UUID
    codigo: str
    descripcion: str
    unidad: Unidad
    cantidad: ImporteTexto
    precio_unitario: ImporteTexto
    importe: ImporteTexto
    nivel: str
    area: str
    tipo_partida: TipoPartida


class ListaConceptosLineaBase(BaseModel):
    elementos: list[ConceptoLineaBase]
    paginacion: MetaPagina

    @classmethod
    def desde(cls, pagina: ConceptosConsultados) -> ListaConceptosLineaBase:
        return cls(
            elementos=[
                ConceptoLineaBase(
                    id=c.id,
                    codigo=c.codigo,
                    descripcion=c.descripcion,
                    unidad=Unidad(c.unidad),
                    cantidad=c.cantidad.serializar(),
                    precio_unitario=c.precio_unitario.serializar(),
                    importe=c.importe.serializar(),
                    nivel=c.nivel,
                    area=c.area,
                    tipo_partida=TipoPartida.desde(c.tipo_partida),
                )
                for c in pagina.elementos
            ],
            paginacion=MetaPagina(
                pagina=pagina.pagina, tamano_pagina=pagina.tamano_pagina, total=pagina.total
            ),
        )


class InsumoResumen(BaseModel):
    id: uuid.UUID
    codigo: str
    descripcion: str
    unidad: Unidad


class RenglonExplosion(BaseModel):
    tipo_partida: TipoPartida
    insumo: InsumoResumen
    cantidad_presupuestada: ImporteTexto
    rendimiento_congelado: ImporteTexto
    costo_unitario: ImporteTexto
    importe_costo: ImporteTexto


class ExplosionInsumos(BaseModel):
    linea_base_id: uuid.UUID
    renglones: list[RenglonExplosion]
    importe_total: ImporteTexto

    @classmethod
    def desde(cls, explosion: ExplosionConsultada) -> ExplosionInsumos:
        return cls(
            linea_base_id=explosion.linea_base_id,
            renglones=[
                RenglonExplosion(
                    tipo_partida=TipoPartida.desde(r.tipo_partida),
                    insumo=InsumoResumen(
                        id=r.insumo.id,
                        codigo=r.insumo.codigo,
                        descripcion=r.insumo.descripcion,
                        unidad=Unidad(r.insumo.unidad),
                    ),
                    cantidad_presupuestada=r.cantidad_presupuestada.serializar(),
                    rendimiento_congelado=r.rendimiento_congelado.serializar(),
                    costo_unitario=r.costo_unitario.serializar(),
                    importe_costo=r.importe_costo.serializar(),
                )
                for r in explosion.renglones
            ],
            importe_total=explosion.importe_total.serializar(),
        )
