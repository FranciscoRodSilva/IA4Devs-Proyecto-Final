"""DTO de la API de archivos (TKT-059, fila 12a): la salida `Archivo` del borrador OpenAPI.

Ningún esquema lleva la clave del objeto en el almacén: es interna (ADR-016).

El `Literal` de `Archivo.referencia_tipo` repite a mano los seis valores de `TIPOS_DE_REFERENCIA`
(`cimenta.archivos.aplicacion.alta`) y los de `ck_archivo_referencia_tipo` (migración v0012). Deben
coincidir: un `Literal` no puede construirse desde un conjunto, y se mantiene porque el esquema
OpenAPI publica esos valores. Un test compara ambos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel

from cimenta.archivos.aplicacion.confirmacion import ArchivoLeido
from cimenta.archivos.aplicacion.consulta import UrlDescargaEmitida
from cimenta.archivos.dominio.confirmacion import EstadoArchivo
from cimenta.identidad.interfaz import UsuarioResumen


class Archivo(BaseModel):
    id: uuid.UUID
    obra_id: uuid.UUID
    referencia_tipo: Literal[
        "AVANCE", "ENTRADA_ALMACEN", "MERMA", "FACTURA_PROVEEDOR", "IMPORTACION", "OBRA"
    ]
    referencia_id: uuid.UUID | None
    estado: EstadoArchivo
    nombre_original: str
    tipo_mime: str | None
    tamano_bytes: int
    hash_sha256: str
    subido_por: UsuarioResumen
    creado_en: datetime
    confirmado_en: datetime | None

    @classmethod
    def desde(cls, leido: ArchivoLeido) -> Self:
        return cls.model_validate(
            {
                "id": leido.id,
                "obra_id": leido.obra_id,
                "referencia_tipo": leido.referencia_tipo,
                "referencia_id": leido.referencia_id,
                "estado": leido.estado,
                "nombre_original": leido.nombre_original,
                "tipo_mime": leido.tipo_mime,
                "tamano_bytes": leido.tamano_bytes,
                "hash_sha256": leido.hash_sha256,
                "subido_por": {"id": leido.subido_por_id, "nombre": leido.subido_por_nombre},
                "creado_en": leido.creado_en,
                "confirmado_en": leido.confirmado_en,
            }
        )


class UrlDescarga(BaseModel):
    url: str
    expira_en: datetime
    tipo_mime: str
    nombre_original: str
    disposicion: Literal["inline", "attachment"]

    @classmethod
    def desde(cls, emitida: UrlDescargaEmitida) -> Self:
        return cls.model_validate(
            {
                "url": emitida.url,
                "expira_en": emitida.expira_en,
                "tipo_mime": emitida.tipo_mime,
                "nombre_original": emitida.nombre_original,
                "disposicion": emitida.disposicion,
            }
        )
