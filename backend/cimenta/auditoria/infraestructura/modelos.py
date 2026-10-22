"""Modelos SQLAlchemy de auditoria (TKT-007). Mapa de la tabla: ninguna regla de negocio vive aquí.

`Base` es propia de auditoria: su `MetaData` no conoce `usuario`, así que la clave foránea al actor
no se declara aquí; la emite la migración v0003 (ver `design.md`, «Infraestructura y esquema»).
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import DateTime, MetaData, Text, Uuid
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cimenta.auditoria.dominio.asiento import AccionBitacora

CONVENCION_NOMBRES: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class FilaBitacora(Base):
    __tablename__ = "bitacora"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    entidad_tipo: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    accion: Mapped[AccionBitacora] = mapped_column(
        postgresql.ENUM(
            AccionBitacora,
            name="accion_bitacora",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    ocurrido_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    datos_antes: Mapped[dict[str, object] | None] = mapped_column(
        postgresql.JSONB(none_as_null=True)
    )
    datos_despues: Mapped[dict[str, object] | None] = mapped_column(
        postgresql.JSONB(none_as_null=True)
    )
    motivo: Mapped[str | None] = mapped_column(Text)
    regla_negocio: Mapped[str | None] = mapped_column(Text)
    obra_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
