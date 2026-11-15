"""DTO de la API de proveedores (TKT-029a, fila B1). Entrada y salida son modelos distintos.

El tope de consignación sale como cadena de cuatro decimales (`Dinero.serializar()`), nunca como número JSON.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    Strict,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from cimenta.proveedores.aplicacion.proveedores import CAMPOS_CAMBIABLES, ProveedoresConsultados
from cimenta.proveedores.dominio.proveedor import (
    DIA_CORTE_POR_OMISION,
    DIA_PAGO_POR_OMISION,
    EstadoProveedor,
    normalizar_rfc,
)
from cimenta.proveedores.infraestructura.repositorio_proveedor import FilaProveedor
from tipos_base import Dinero


# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42).
def sin_nul(texto: str) -> str:
    if "\x00" in texto:
        raise ValueError("El motivo no admite el carácter NUL.")
    return texto


# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42).
LARGO_MAXIMO_MOTIVO = 2000

# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42).
MotivoTexto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_MOTIVO),
    AfterValidator(sin_nul),
]


# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42).
class Motivo(BaseModel):
    """Cuerpo con motivo obligatorio: se guarda sin espacios en los extremos."""

    motivo: MotivoTexto


# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma y docstring (TC-42).
class MetaPagina(BaseModel):
    pagina: Annotated[int, Field(ge=1)]
    tamano_pagina: Annotated[int, Field(ge=1)]
    total: Annotated[int, Field(ge=0)]


LARGO_MAXIMO_NOMBRE_PROVEEDOR = 200

NombreProveedor = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE_PROVEEDOR
    ),
    AfterValidator(sin_nul),
]

# `[0-9]`, nunca `\d`: este admite dígitos no ASCII.
_PATRON_RFC = re.compile(r"[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}")


def _rfc(valor: object) -> str:
    """Normaliza (D-1) y exige la forma del RFC; lo demás es `ValueError`.

    Antes de pasar a mayúsculas se rechaza todo lo que no sea ASCII, `Ñ`, `ñ` o `&`,
    porque `str.upper()` reescribiría `ß` como `SS`, `ı` como `I` y `ſ` como `S`.
    `fullmatch` rechaza `NUL` y `\\n`.
    """
    if not isinstance(valor, str):
        raise ValueError("El RFC debe ser una cadena.")
    # Rangos literales sin IGNORECASE: solo cubren ASCII, así que `ß`, `ı` y `ſ` no pasan.
    if re.fullmatch(r"[A-Za-zÑñ&0-9]+", valor.strip(" ")) is None:
        raise ValueError("El RFC no tiene la forma de un RFC válido.")
    normalizado = normalizar_rfc(valor)
    if _PATRON_RFC.fullmatch(normalizado) is None:
        raise ValueError("El RFC no tiene la forma de un RFC válido.")
    return normalizado


class _EsquemaRfc:
    """Valida y normaliza el RFC; publica el patrón del borrador."""

    def __get_pydantic_core_schema__(
        self, _origen: object, _manejador: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(_rfc)

    def __get_pydantic_json_schema__(
        self, _esquema: core_schema.CoreSchema, _manejador: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "pattern": r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"}


Rfc = Annotated[str, _EsquemaRfc()]

_PATRON_IMPORTE = re.compile(r"[0-9]{1,14}(\.[0-9]{1,4})?")


# Copia de `presupuesto/api/esquemas.py`; debe publicar la misma forma (TC-42).
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

DiaSemana = Annotated[int, Strict(), Field(ge=1, le=7)]

# Un campo opcional que no se publica como anulable: el tipo no admite `None` pero la ausencia es válida (E-6).
_AUSENTE: Any = cast("Any", None)

ImporteTexto = Annotated[str, Field(json_schema_extra={"format": "decimal"})]


class ProveedorNuevo(BaseModel):
    """Cuerpo del alta: lo que no declara se ignora (D-6)."""

    nombre: NombreProveedor
    rfc: Rfc
    tope_consignacion: ImporteNoNegativo | None = None
    dia_corte: DiaSemana = DIA_CORTE_POR_OMISION
    dia_pago: DiaSemana = DIA_PAGO_POR_OMISION


class ProveedorCambios(BaseModel):
    """Cambio parcial: solo lo enviado se aplica; el RFC y el estado no se cambian por aquí."""

    model_config = ConfigDict(json_schema_extra={"minProperties": 1})

    nombre: NombreProveedor = Field(default=_AUSENTE)
    tope_consignacion: ImporteNoNegativo | None = None
    dia_corte: DiaSemana = Field(default=_AUSENTE)
    dia_pago: DiaSemana = Field(default=_AUSENTE)

    @model_validator(mode="after")
    def _al_menos_un_dato(self) -> ProveedorCambios:
        if not (self.model_fields_set & CAMPOS_CAMBIABLES):
            raise ValueError("Indica al menos un dato a cambiar.")
        return self


class Proveedor(BaseModel):
    id: uuid.UUID
    nombre: str
    rfc: str
    tope_consignacion: ImporteTexto | None = None
    dia_corte: int
    dia_pago: int
    estado: EstadoProveedor
    creado_en: datetime

    @classmethod
    def desde(cls, fila: FilaProveedor) -> Proveedor:
        return cls(
            id=fila.id,
            nombre=fila.nombre,
            rfc=fila.rfc,
            tope_consignacion=None
            if fila.tope_consignacion is None
            else fila.tope_consignacion.serializar(),
            dia_corte=fila.dia_corte,
            dia_pago=fila.dia_pago,
            estado=EstadoProveedor(fila.estado),
            creado_en=fila.creado_en,
        )


class ListaProveedores(BaseModel):
    elementos: list[Proveedor]
    paginacion: MetaPagina

    @classmethod
    def desde(cls, pagina: ProveedoresConsultados) -> ListaProveedores:
        return cls(
            elementos=[Proveedor.desde(fila) for fila in pagina.elementos],
            paginacion=MetaPagina(
                pagina=pagina.pagina, tamano_pagina=pagina.tamano_pagina, total=pagina.total
            ),
        )
