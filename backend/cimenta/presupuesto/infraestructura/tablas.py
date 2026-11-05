"""Tablas Core de `presupuesto` usadas por el repositorio (TKT-015a).

Solo las columnas que consulta el repositorio; no emiten DDL (Alembic manda).
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

CONVENCION_NOMBRES: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=CONVENCION_NOMBRES)

importacion = Table(
    "importacion",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("obra_id", Uuid, ForeignKey("obra.id"), nullable=False),
    Column("archivo_id", Uuid, nullable=False),
    Column("estado", Text, nullable=False),
    Column("progreso", Numeric(9, 6)),
    Column("filas_leidas", Integer),
    Column("filas_validas", Integer),
    Column("filas_rechazadas", Integer),
    Column("latido", TIMESTAMP(timezone=True)),
    Column("preparacion", JSONB),
)

importacion_error = Table(
    "importacion_error",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "importacion_id",
        Uuid,
        ForeignKey("importacion.id"),
        nullable=False,
    ),
    Column("hoja", Text),
    Column("fila", Integer),
    Column("columna", Text),
    Column("tipo", Text, nullable=False),
    Column("mensaje", Text, nullable=False),
    Column("valor_original", Text),
)

insumo = Table(
    "insumo",
    metadata,
    Column("codigo", Text, nullable=False),
    Column("descripcion", Text, nullable=False),
    Column("unidad", Text, nullable=False),
)
