"""DTO de la API de presupuesto (TKT-017b1, fila B3). Entrada y salida son modelos distintos.

Los importes salen como cadena de cuatro decimales (`Dinero.serializar()`), nunca como número JSON.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    StrictBool,
    StringConstraints,
    WithJsonSchema,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from cimenta.identidad.interfaz import UsuarioResumen
from cimenta.presupuesto.aplicacion.consulta_linea_base import (
    ConceptosConsultados,
    ControlConsultado,
    ExplosionConsultada,
    LineaBaseConsultada,
    TipoPartidaConsultado,
)
from cimenta.presupuesto.aplicacion.obras import ObrasConsultadas
from cimenta.presupuesto.infraestructura.repositorio_obra import FilaObraCompleta
from tipos_base import Dinero, Porcentaje


def _sin_nul(texto: str) -> str:
    if "\x00" in texto:
        raise ValueError("El motivo no admite el carácter NUL.")
    return texto


LARGO_MAXIMO_MOTIVO = 2000

MotivoTexto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_MOTIVO),
    AfterValidator(_sin_nul),
]

# El motivo de la captura del tope: nulo y en blanco llegan al dominio, que decide si lo exige (RN-04).
MotivoLibre = Annotated[
    str,
    StringConstraints(max_length=LARGO_MAXIMO_MOTIVO),
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


_PATRON_IMPORTE = re.compile(r"[0-9]{1,14}(\.[0-9]{1,4})?")


def _importe_no_negativo(valor: object) -> Dinero:
    """Acepta solo una cadena de importe no negativo (`ImporteNoNegativo` del borrador); lo demás es `ValueError`."""
    if not isinstance(valor, str) or _PATRON_IMPORTE.fullmatch(valor) is None:
        raise ValueError("El importe debe ser una cadena decimal no negativa.")
    return Dinero(valor)


class _EsquemaImporteNoNegativo:
    """Valida la cadena de importe y publica solo `type: string`; no construye el esquema de `Dinero`.

    Con `PlainValidator` Pydantic aún recorre el tipo anotado y publicaría `Dinero` como componente huérfano.
    """

    def __get_pydantic_core_schema__(
        self, _origen: object, _manejador: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(_importe_no_negativo)

    def __get_pydantic_json_schema__(
        self, _esquema: core_schema.CoreSchema, _manejador: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "pattern": r"^\d{1,14}(\.\d{1,4})?$", "format": "decimal"}


ImporteNoNegativo = Annotated[Dinero, _EsquemaImporteNoNegativo()]


class CapturaPresupuestoControl(BaseModel):
    """Cuerpo de la captura del tope (RN-03): lo que no declara se ignora."""

    importe_tope: ImporteNoNegativo
    motivo: MotivoLibre | None = None
    confirmar_superior_a_venta: StrictBool = False


class PresupuestoControl(BaseModel):
    tipo_partida: TipoPartida
    importe_venta: ImporteTexto
    importe_sugerido: ImporteTexto
    importe_tope: ImporteTexto | None
    capturado_por: UsuarioResumen | None = None
    capturado_en: datetime | None = None
    actualizado_por: UsuarioResumen | None = None
    actualizado_en: datetime | None = None
    motivo_ultimo_cambio: str | None = None

    @classmethod
    def desde(cls, control: ControlConsultado) -> PresupuestoControl:
        return cls(
            tipo_partida=TipoPartida.desde(control.tipo_partida),
            importe_venta=control.importe_venta.serializar(),
            importe_sugerido=control.importe_sugerido.serializar(),
            importe_tope=None
            if control.importe_tope is None
            else control.importe_tope.serializar(),
            capturado_por=control.capturado_por,
            capturado_en=control.capturado_en,
            actualizado_por=control.actualizado_por,
            actualizado_en=control.actualizado_en,
            motivo_ultimo_cambio=control.motivo_ultimo_cambio,
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


_PATRON_PORCENTAJE = re.compile(r"-?[0-9]{1,3}(\.[0-9]{1,6})?")


def _porcentaje_de_entrada(valor: object) -> Porcentaje:
    """Acepta solo una cadena de porcentaje (`Porcentaje` del borrador); el rango lo decide el dominio."""
    if not isinstance(valor, str) or _PATRON_PORCENTAJE.fullmatch(valor) is None:
        raise ValueError("El porcentaje debe ser una cadena decimal.")
    return Porcentaje(valor)


class _EsquemaPorcentaje:
    """Valida la cadena de porcentaje y publica solo `type: string`, con el patrón del borrador."""

    def __get_pydantic_core_schema__(
        self, _origen: object, _manejador: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(_porcentaje_de_entrada)

    def __get_pydantic_json_schema__(
        self, _esquema: core_schema.CoreSchema, _manejador: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "pattern": r"^-?\d{1,3}(\.\d{1,6})?$", "format": "decimal"}


PorcentajeEntrada = Annotated[Porcentaje, _EsquemaPorcentaje()]

LARGO_MAXIMO_CODIGO_OBRA = 40
LARGO_MAXIMO_NOMBRE_OBRA = 200
LARGO_MAXIMO_DOMICILIO = 500


CodigoObra = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_CODIGO_OBRA),
    AfterValidator(_sin_nul),
]
NombreObra = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE_OBRA),
    AfterValidator(_sin_nul),
]
DomicilioObra = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_DOMICILIO),
    AfterValidator(_sin_nul),
]

TipoContrato = Literal["PRECIO_ALZADO_MAXIMO_GARANTIZADO"]
_ENUM_TIPO_CONTRATO = Field(json_schema_extra={"enum": list(get_args(TipoContrato))})


class EstadoObra(StrEnum):
    PLANEACION = "PLANEACION"
    ACTIVA = "ACTIVA"
    SUSPENDIDA = "SUSPENDIDA"
    CERRADA = "CERRADA"


class ObraNueva(BaseModel):
    """Cuerpo del alta de obra: lo que no declara (`estado`, `empresa_id`…) se ignora."""

    codigo: CodigoObra
    nombre: NombreObra
    domicilio: DomicilioObra
    tipo_contrato: Annotated[TipoContrato, _ENUM_TIPO_CONTRATO]
    retencion_destajo_pct: PorcentajeEntrada
    fondo_garantia_pct: PorcentajeEntrada
    iva_acreditable: StrictBool
    umbral_alerta_pct: PorcentajeEntrada | None = None


PorcentajeTexto = Annotated[str, Field(json_schema_extra={"format": "decimal"})]


class Obra(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    domicilio: str
    tipo_contrato: Annotated[str, _ENUM_TIPO_CONTRATO]
    retencion_destajo_pct: PorcentajeTexto
    fondo_garantia_pct: PorcentajeTexto
    iva_acreditable: bool
    umbral_alerta_pct: PorcentajeTexto | None
    estado: EstadoObra
    linea_base_vigente_id: uuid.UUID | None
    creado_en: datetime
    # El borrador lo declara cadena no nula y no obligatoria: sin valor no se asigna y las rutas usan
    # `response_model_exclude_unset`, así que se omite en lugar de salir `null`.
    actualizado_en: Annotated[
        datetime | None, WithJsonSchema({"type": "string", "format": "date-time"})
    ] = None

    @classmethod
    def desde(cls, fila: FilaObraCompleta) -> Obra:
        extra = {} if fila.actualizado_en is None else {"actualizado_en": fila.actualizado_en}
        return cls(
            id=fila.id,
            codigo=fila.codigo,
            nombre=fila.nombre,
            domicilio=fila.domicilio,
            tipo_contrato=fila.tipo_contrato,
            retencion_destajo_pct=fila.retencion_destajo_pct.cuantizar().serializar(),
            fondo_garantia_pct=fila.fondo_garantia_pct.cuantizar().serializar(),
            iva_acreditable=fila.iva_acreditable,
            umbral_alerta_pct=None
            if fila.umbral_alerta_pct is None
            else fila.umbral_alerta_pct.cuantizar().serializar(),
            estado=EstadoObra(fila.estado),
            linea_base_vigente_id=fila.linea_base_vigente_id,
            creado_en=fila.creado_en,
            **extra,
        )


class ListaObras(BaseModel):
    elementos: list[Obra]
    paginacion: MetaPagina

    @classmethod
    def desde(cls, pagina: ObrasConsultadas) -> ListaObras:
        return cls(
            elementos=[Obra.desde(fila) for fila in pagina.elementos],
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
