"""Consulta y descarga de un archivo (TKT-059, fila 14).

Implementa RNF-06 y ADR-016. `obtener_archivo` devuelve los metadatos de la fila tal cual está, sin la
clave del objeto. `emitir_url_descarga` firma una URL de lectura de vida corta solo si el archivo está
`DISPONIBLE`; los bytes nunca pasan por la API. Una transacción de lectura, sin bloqueo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from cimenta.archivos.aplicacion.confirmacion import ArchivoLeido, leido_de
from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.archivos.dominio.confirmacion import EstadoArchivo
from cimenta.archivos.dominio.tipos import disposicion_de
from cimenta.archivos.infraestructura import repositorio
from contrato_error.excepciones import ConflictoEstado, NoEncontrado

__all__ = ["UrlDescargaEmitida", "emitir_url_descarga", "obtener_archivo"]

_MENSAJE_NO_EXISTE = "El archivo no existe."
_MENSAJE_NO_DISPONIBLE = "El archivo todavía no está disponible."
_MENSAJE_CADUCADO = "La subida del archivo caducó y no se puede descargar."


@dataclass(frozen=True, slots=True)
class UrlDescargaEmitida:
    """La URL prefirmada de lectura y lo que el cliente necesita para mostrarla."""

    url: str
    expira_en: datetime
    tipo_mime: str
    nombre_original: str
    disposicion: str


def _fila(sesion_bd: Session, archivo_id: uuid.UUID) -> repositorio.FilaArchivo:
    fila = repositorio.leer(sesion_bd, archivo_id)
    if fila is None:
        raise NoEncontrado(recurso="archivo", mensaje=_MENSAJE_NO_EXISTE)
    return fila


def obtener_archivo(contexto: ContextoArchivos, *, archivo_id: uuid.UUID) -> ArchivoLeido:
    """Los metadatos del archivo en cualquier estado; no consulta el almacén."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        return leido_de(sesion_bd, _fila(sesion_bd, archivo_id))


def _no_descargable(fila: repositorio.FilaArchivo) -> ConflictoEstado:
    caducado = fila.estado is EstadoArchivo.CADUCADO
    return ConflictoEstado(
        codigo="ARCHIVO_CADUCADO" if caducado else "ARCHIVO_NO_DISPONIBLE",
        mensaje=_MENSAJE_CADUCADO if caducado else _MENSAJE_NO_DISPONIBLE,
        detalle={"archivo_id": str(fila.id), "estado_archivo": fila.estado.value},
    )


def emitir_url_descarga(contexto: ContextoArchivos, *, archivo_id: uuid.UUID) -> UrlDescargaEmitida:
    """Firma la URL de lectura de un archivo `DISPONIBLE`; cualquier otro estado es un `409`."""
    ahora = contexto.reloj()
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = _fila(sesion_bd, archivo_id)
    if fila.estado is not EstadoArchivo.DISPONIBLE:
        raise _no_descargable(fila)
    if fila.tipo_mime is None:
        raise RuntimeError("un archivo disponible siempre tiene tipo")
    disposicion = disposicion_de(fila.tipo_mime)
    if disposicion is None:
        raise RuntimeError("un archivo disponible siempre tiene un tipo admitido")
    vida = contexto.configuracion.vida_url_lectura
    url = contexto.almacen().url_lectura(
        fila.clave_objeto,
        vida=vida,
        tipo_mime=fila.tipo_mime,
        nombre_original=fila.nombre_original,
        disposicion=disposicion,
    )
    return UrlDescargaEmitida(
        url=url,
        expira_en=ahora + vida,
        tipo_mime=fila.tipo_mime,
        nombre_original=fila.nombre_original,
        disposicion=disposicion,
    )
