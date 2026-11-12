"""Tabla Core de `proveedores` usada por el repositorio (TKT-029a, fila A3).

Solo las columnas que consulta el repositorio; no emite DDL (Alembic manda, migración `0013`).
Sin `ForeignKey`: `usuario` no está en este `MetaData`, y el módulo no importa tablas de otros módulos.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    MetaData,
    Numeric,
    SmallInteger,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP

metadata = MetaData()

proveedor = Table(
    "proveedor",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("nombre", Text, nullable=False),
    Column("rfc", Text, nullable=False),
    Column("estado", Text, nullable=False),
    Column("tope_consignacion", Numeric(18, 4)),
    Column("dia_corte", SmallInteger, nullable=False),
    Column("dia_pago", SmallInteger, nullable=False),
    Column("creado_en", TIMESTAMP(timezone=True), nullable=False),
    Column("creado_por_id", Uuid, nullable=False),
)
