"""Modelos SQLAlchemy de identidad (TKT-006). Mapa de las tablas de v0001: ninguna regla de negocio vive aquí.

`Base` es propia de identidad: su `MetaData` declara las mismas convenciones de nombre que el resto de
módulos, para que lo que se escriba a mano y lo que se genere lleven el mismo prefijo. Ningún modelo
define `relationship`, `@validates` ni `event.listen`: las consultas se escriben en `repositorio.py`
con `select()` de estilo 2.0 y el esquema lo construye solo `alembic upgrade head`.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import Boolean, DateTime, ForeignKey, MetaData, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CONVENCION_NOMBRES: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean)
    ultimo_acceso: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    bloqueado_hasta: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuario.id"))
    actualizado_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    actualizado_por_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuario.id"))


class Rol(Base):
    __tablename__ = "rol"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    clave: Mapped[str] = mapped_column(Text, unique=True)
    nombre: Mapped[str] = mapped_column(Text)


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuario.id"))
    rol_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rol.id"))
    creado_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuario.id"))
    actualizado_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    actualizado_por_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuario.id"))


class Sesion(Base):
    __tablename__ = "sesion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuario.id"))
    creada_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    expira_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    ultima_actividad: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    origen_ip: Mapped[str | None] = mapped_column(Text)
    agente_usuario: Mapped[str | None] = mapped_column(Text)


class IntentoAcceso(Base):
    __tablename__ = "intento_acceso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuario.id"))
    exitoso: Mapped[bool] = mapped_column(Boolean)
    ocurrido_en: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    origen_ip: Mapped[str | None] = mapped_column(Text)
