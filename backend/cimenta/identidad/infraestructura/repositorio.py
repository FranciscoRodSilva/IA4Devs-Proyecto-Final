"""Repositorio de identidad (TKT-006, fila 4). Acceso a `usuario`, `rol`, `usuario_rol`, `sesion` e `intento_acceso`.

Cada función recibe la `Session` que abrió el caso de uso y **ninguna confirma ni deshace**: la
transacción es de quien llama (regla 8 de CLAUDE.md). El repositorio no decide nada: compara el
correo tal como llega (normalizar es del dominio, `normalizar_correo`), guarda lo que se le pasa y
solo informa si una actualización tocó fila. Las reglas de vigencia y de revocación viven en
`dominio/vigencia.py` y `dominio/autorizacion.py`.
"""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from cimenta.identidad.infraestructura.modelos import (
    IntentoAcceso,
    Rol,
    Sesion,
    Usuario,
    UsuarioRol,
)


@dataclass(frozen=True)
class CredencialAlmacenada:
    """Lo que el inicio de sesión necesita del usuario. El hash no sale de esta capa."""

    id: uuid.UUID
    nombre: str
    email: str
    password_hash: str
    activo: bool


@dataclass(frozen=True)
class SesionAlmacenada:
    """Una fila de `sesion` unida a su usuario, tal como está en la base."""

    usuario_id: uuid.UUID
    nombre: str
    email: str
    expira_en: dt.datetime
    ultima_actividad: dt.datetime
    revocada_en: dt.datetime | None
    usuario_activo: bool


def buscar_credencial(bd: Session, correo: str) -> CredencialAlmacenada | None:
    """Devuelve la credencial del usuario con ese correo exacto, también si está desactivado.

    Compara `email` tal como llega: normalizar el correo es del dominio. Rechazar al desactivado
    también es del dominio (`credenciales_aceptadas`), no de esta consulta.
    """
    sentencia = select(
        Usuario.id, Usuario.nombre, Usuario.email, Usuario.password_hash, Usuario.activo
    ).where(Usuario.email == correo)
    fila = bd.execute(sentencia).one_or_none()
    if fila is None:
        return None
    identificador, nombre, email, password_hash, activo = fila
    return CredencialAlmacenada(
        id=identificador,
        nombre=nombre,
        email=email,
        password_hash=password_hash,
        activo=activo,
    )


def roles_de(bd: Session, usuario_id: uuid.UUID) -> frozenset[str]:
    """Las claves de rol del usuario. Un usuario sin roles, o inexistente, da un conjunto vacío."""
    sentencia = (
        select(Rol.clave)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(UsuarioRol.usuario_id == usuario_id)
    )
    return frozenset(bd.scalars(sentencia))


def insertar_intento(
    bd: Session,
    *,
    email: str,
    usuario_id: uuid.UUID | None,
    exitoso: bool,
    ocurrido_en: dt.datetime,
    origen_ip: str | None,
) -> None:
    """Añade un intento de acceso con el correo tal como se escribió, exista o no el usuario."""
    bd.execute(
        insert(IntentoAcceso).values(
            id=uuid.uuid4(),
            email=email,
            usuario_id=usuario_id,
            exitoso=exitoso,
            ocurrido_en=ocurrido_en,
            origen_ip=origen_ip,
        )
    )


def insertar_sesion(
    bd: Session,
    *,
    sesion_id: uuid.UUID,
    usuario_id: uuid.UUID,
    ahora: dt.datetime,
    expira_en: dt.datetime,
    origen_ip: str | None,
    agente_usuario: str | None,
) -> None:
    """Añade una sesión viva: `creada_en` y `ultima_actividad` valen `ahora`, `revocada_en` queda nulo."""
    bd.execute(
        insert(Sesion).values(
            id=sesion_id,
            usuario_id=usuario_id,
            creada_en=ahora,
            expira_en=expira_en,
            ultima_actividad=ahora,
            revocada_en=None,
            origen_ip=origen_ip,
            agente_usuario=agente_usuario,
        )
    )


def leer_sesion(bd: Session, sesion_id: uuid.UUID) -> SesionAlmacenada | None:
    """La sesión con los datos de su usuario, o None si no existe. No decide si está vigente."""
    sentencia = (
        select(
            Sesion.usuario_id,
            Usuario.nombre,
            Usuario.email,
            Sesion.expira_en,
            Sesion.ultima_actividad,
            Sesion.revocada_en,
            Usuario.activo,
        )
        .join(Usuario, Usuario.id == Sesion.usuario_id)
        .where(Sesion.id == sesion_id)
    )
    fila = bd.execute(sentencia).one_or_none()
    if fila is None:
        return None
    usuario_id, nombre, email, expira_en, ultima_actividad, revocada_en, activo = fila
    return SesionAlmacenada(
        usuario_id=usuario_id,
        nombre=nombre,
        email=email,
        expira_en=expira_en,
        ultima_actividad=ultima_actividad,
        revocada_en=revocada_en,
        usuario_activo=activo,
    )


def marcar_ultimo_acceso(bd: Session, usuario_id: uuid.UUID, ahora: dt.datetime) -> None:
    """Registra el último acceso sin tocar `actualizado_en`: no es un cambio de datos del usuario (asumido)."""
    bd.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(ultimo_acceso=ahora)
        .execution_options(synchronize_session=False)
    )


def tocar_sesion(bd: Session, sesion_id: uuid.UUID, ahora: dt.datetime) -> bool:
    """Desliza `ultima_actividad` solo si la sesión no está revocada (ADR-014, CA-6 y CA-9).

    La guarda `revocada_en IS NULL` va dentro del `UPDATE`: una revocación que llega entre la
    lectura y esta escritura gana. Devuelve False si no hubo fila que actualizar.
    """
    sentencia = (
        update(Sesion)
        .where(Sesion.id == sesion_id, Sesion.revocada_en.is_(None))
        .values(ultima_actividad=ahora)
        .returning(Sesion.id)
        .execution_options(synchronize_session=False)
    )
    return bd.execute(sentencia).scalar_one_or_none() is not None


def revocar_sesion(bd: Session, sesion_id: uuid.UUID, ahora: dt.datetime) -> bool:
    """Escribe `revocada_en` una sola vez (ADR-014, CA-9). La fila y su actividad se conservan.

    Si ya estaba revocada no pisa la hora original y devuelve False. Sin fila, también False.
    """
    sentencia = (
        update(Sesion)
        .where(Sesion.id == sesion_id, Sesion.revocada_en.is_(None))
        .values(revocada_en=ahora)
        .returning(Sesion.id)
        .execution_options(synchronize_session=False)
    )
    return bd.execute(sentencia).scalar_one_or_none() is not None
