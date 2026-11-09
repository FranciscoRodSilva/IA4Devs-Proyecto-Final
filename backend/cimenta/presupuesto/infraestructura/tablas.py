"""Tablas Core de `presupuesto` usadas por los repositorios (TKT-015a y TKT-017a3).

Solo las columnas que consulta el repositorio; no emiten DDL (Alembic manda).
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
    Column("id", Uuid, primary_key=True),
    Column("codigo", Text, nullable=False),
    Column("descripcion", Text, nullable=False),
    Column("tipo", Text, nullable=False),
    Column("unidad", Text, nullable=False),
    Column("activo", Boolean, nullable=False),
    Column("creado_en_importacion", Boolean, nullable=False),
)

obra = Table(
    "obra",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("codigo", Text, nullable=False),
    Column("nombre", Text, nullable=False),
    Column("estado", Text, nullable=False),
)

tipo_partida = Table(
    "tipo_partida",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("clave", Text, nullable=False),
)

nivel = Table(
    "nivel",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("obra_id", Uuid, ForeignKey("obra.id"), nullable=False),
    Column("nombre", Text, nullable=False),
    Column("orden", Integer, nullable=False),
)

area = Table(
    "area",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("nivel_id", Uuid, ForeignKey("nivel.id"), nullable=False),
    Column("nombre", Text, nullable=False),
    Column("tipo_unidad", Text),
)

partida = Table(
    "partida",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("area_id", Uuid, ForeignKey("area.id"), nullable=False),
    Column("tipo_partida_id", Uuid, ForeignKey("tipo_partida.id"), nullable=False),
    Column("orden", Integer, nullable=False),
)

concepto = Table(
    "concepto",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("obra_id", Uuid, ForeignKey("obra.id"), nullable=False),
    Column("codigo", Text, nullable=False),
    Column("descripcion", Text, nullable=False),
    Column("unidad", Text, nullable=False),
)

partida_concepto = Table(
    "partida_concepto",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("concepto_id", Uuid, ForeignKey("concepto.id"), nullable=False),
    Column("partida_id", Uuid, ForeignKey("partida.id"), nullable=False),
    Column("cantidad", Numeric(14, 4), nullable=False),
    Column("precio_unitario", Numeric(14, 4), nullable=False),
    Column("importe", Numeric(18, 4), nullable=False),
)

apu = Table(
    "apu",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("concepto_id", Uuid, ForeignKey("concepto.id"), nullable=False),
    Column("fecha_analisis", Date),
    Column("analista", Text),
    Column("costo_material", Numeric(14, 4), nullable=False),
    Column("costo_mano_obra", Numeric(14, 4), nullable=False),
    Column("costo_directo", Numeric(14, 4), nullable=False),
    Column("total_cargos", Numeric(14, 4), nullable=False),
    Column("total_indirectos", Numeric(14, 4), nullable=False),
    Column("precio_unitario", Numeric(14, 4), nullable=False),
)

apu_insumo = Table(
    "apu_insumo",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("apu_id", Uuid, ForeignKey("apu.id"), nullable=False),
    Column("insumo_id", Uuid, ForeignKey("insumo.id"), nullable=False),
    Column("costo_unitario", Numeric(14, 4), nullable=False),
    Column("rendimiento", Numeric(18, 6), nullable=False),
    Column("cargo", Numeric(14, 4), nullable=False),
)

apu_cargo = Table(
    "apu_cargo",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("apu_id", Uuid, ForeignKey("apu.id"), nullable=False),
    Column("tipo", Text, nullable=False),
    Column("porcentaje", Numeric(9, 6)),
    Column("base_calculo", Numeric(14, 4)),
    Column("importe", Numeric(14, 4), nullable=False),
)

linea_base = Table(
    "linea_base",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("obra_id", Uuid, ForeignKey("obra.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("estado", Text, nullable=False),
    Column("importe_venta", Numeric(18, 4), nullable=False),
    Column("creado_en", TIMESTAMP(timezone=True), nullable=False),
    Column("creado_por_id", Uuid, nullable=False),
)
