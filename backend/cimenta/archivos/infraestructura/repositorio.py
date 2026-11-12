"""Repositorio de `archivo` (TKT-059, fila 9): la tabla Core y las cinco operaciones del módulo.

Cada función recibe la sesión del caso de uso y no confirma ni abre la transacción: quien llama
decide el alcance (RNF-19). La tabla la crea `alembic upgrade head` (migración 0012); aquí solo se
declara su forma para Core. Ninguna regla vive en este archivo: el estado llega ya decidido.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    Uuid,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from cimenta.archivos.dominio.confirmacion import EstadoArchivo

CONVENCION_NOMBRES: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=CONVENCION_NOMBRES)

archivo = Table(
    "archivo",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("obra_id", Uuid, nullable=False),
    Column("referencia_tipo", Text, nullable=False),
    Column("referencia_id", Uuid),
    Column("estado", Text, nullable=False),
    Column("clave_objeto", Text, nullable=False),
    Column("nombre_original", Text, nullable=False),
    Column("tipo_mime", Text),
    Column("tamano_bytes", BigInteger),
    Column("hash_sha256", CHAR(64)),
    Column("subido_por_id", Uuid, ForeignKey("usuario.id"), nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False),
    Column("confirmado_en", DateTime(timezone=True)),
    Column("anulado_por_id", Uuid, ForeignKey("usuario.id")),
    Column("motivo_anulacion", Text),
    Column("anulado_en", DateTime(timezone=True)),
)


@dataclass(frozen=True, slots=True)
class FilaArchivo:
    """Una fila de `archivo` con todas sus columnas."""

    id: uuid.UUID
    obra_id: uuid.UUID
    referencia_tipo: str
    referencia_id: uuid.UUID | None
    estado: EstadoArchivo
    clave_objeto: str
    nombre_original: str
    tipo_mime: str | None
    tamano_bytes: int | None
    hash_sha256: str | None
    subido_por_id: uuid.UUID
    creado_en: datetime
    confirmado_en: datetime | None
    anulado_por_id: uuid.UUID | None
    motivo_anulacion: str | None
    anulado_en: datetime | None


def _desde_fila(fila: Row[Any]) -> FilaArchivo:
    """Convierte una fila de `select(archivo)` en `FilaArchivo`, por el nombre de cada columna."""
    return FilaArchivo(
        id=fila.id,
        obra_id=fila.obra_id,
        referencia_tipo=fila.referencia_tipo,
        referencia_id=fila.referencia_id,
        estado=EstadoArchivo(fila.estado),
        clave_objeto=fila.clave_objeto,
        nombre_original=fila.nombre_original,
        tipo_mime=fila.tipo_mime,
        tamano_bytes=fila.tamano_bytes,
        hash_sha256=fila.hash_sha256,
        subido_por_id=fila.subido_por_id,
        creado_en=fila.creado_en,
        confirmado_en=fila.confirmado_en,
        anulado_por_id=fila.anulado_por_id,
        motivo_anulacion=fila.motivo_anulacion,
        anulado_en=fila.anulado_en,
    )


def insertar(sesion_bd: Session, fila: FilaArchivo) -> None:
    """Inserta la fila en la transacción de quien llama. No confirma."""
    sesion_bd.execute(
        insert(archivo).values(
            id=fila.id,
            obra_id=fila.obra_id,
            referencia_tipo=fila.referencia_tipo,
            referencia_id=fila.referencia_id,
            estado=fila.estado.value,
            clave_objeto=fila.clave_objeto,
            nombre_original=fila.nombre_original,
            tipo_mime=fila.tipo_mime,
            tamano_bytes=fila.tamano_bytes,
            hash_sha256=fila.hash_sha256,
            subido_por_id=fila.subido_por_id,
            creado_en=fila.creado_en,
            confirmado_en=fila.confirmado_en,
            anulado_por_id=fila.anulado_por_id,
            motivo_anulacion=fila.motivo_anulacion,
            anulado_en=fila.anulado_en,
        )
    )


def bloquear(sesion_bd: Session, archivo_id: uuid.UUID) -> FilaArchivo | None:
    """La fila con `SELECT ... FOR UPDATE`: dos confirmaciones del mismo archivo no pasan las dos."""
    sentencia = select(archivo).where(archivo.c.id == archivo_id).with_for_update()
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _desde_fila(fila)


def leer(sesion_bd: Session, archivo_id: uuid.UUID) -> FilaArchivo | None:
    """La fila sin bloqueo, para las lecturas."""
    sentencia = select(archivo).where(archivo.c.id == archivo_id)
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _desde_fila(fila)


def marcar_disponible(
    sesion_bd: Session, archivo_id: uuid.UUID, *, tipo_mime: str, confirmado_en: datetime
) -> None:
    """Pasa a `DISPONIBLE` con el tipo leído de los bytes y la hora de confirmación (invariante 23)."""
    sesion_bd.execute(
        update(archivo)
        .where(archivo.c.id == archivo_id)
        .values(
            estado=EstadoArchivo.DISPONIBLE.value,
            tipo_mime=tipo_mime,
            confirmado_en=confirmado_en,
        )
    )


def marcar_caducado(sesion_bd: Session, archivo_id: uuid.UUID) -> None:
    """Pasa a `CADUCADO`: la subida venció sin confirmarse."""
    sesion_bd.execute(
        update(archivo)
        .where(archivo.c.id == archivo_id)
        .values(estado=EstadoArchivo.CADUCADO.value)
    )
