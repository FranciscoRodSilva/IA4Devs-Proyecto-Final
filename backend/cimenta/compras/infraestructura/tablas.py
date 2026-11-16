"""Tablas Core de `compras` usadas por el repositorio de órdenes (TKT-029b, fila F3).

Solo las columnas que consulta el repositorio; no emite DDL (Alembic manda: `0014` crea estas tablas).
Sin `ForeignKey`: el módulo no importa tablas de otros módulos ni declara el esquema que ya está en
Alembic. TKT-030 amplía estas tablas cuando las necesite.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

metadata = MetaData()

orden_compra = Table(
    "orden_compra",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("folio", Text, nullable=False),
    Column("proveedor_id", Uuid, nullable=False),
    Column("cancelada_en", TIMESTAMP(timezone=True)),
)

orden_compra_renglon = Table(
    "orden_compra_renglon",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("orden_compra_id", Uuid, nullable=False),
    Column("cantidad_ordenada", Numeric(14, 4), nullable=False),
    Column("cantidad_recibida", Numeric(14, 4), nullable=False),
)
