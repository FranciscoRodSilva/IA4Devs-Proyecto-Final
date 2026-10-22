"""Casos de uso de escritura de la bitácora (TKT-007, RN-04). Sin transacción propia: ver `asentar`."""

import datetime as dt
import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from cimenta.auditoria.dominio.asiento import (
    MENSAJE_OBLIGATORIO,
    AccionBitacora,
    DefectoDeCampo,
    revisar_asiento,
)
from cimenta.auditoria.infraestructura import repositorio
from contrato_error import ErrorDeCampo, ValidacionRechazada

MENSAJE_SIN_ZONA = "El momento lleva zona horaria."


def defectos_de_momento(
    campo: str, valor: object, *, obligatorio: bool
) -> tuple[DefectoDeCampo, ...]:
    """Un instante sin zona se guardaría en la zona de la sesión de PostgreSQL: se rechaza."""
    if valor is None:
        return (DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO),) if obligatorio else ()
    if not isinstance(valor, dt.datetime) or valor.utcoffset() is None:
        return (DefectoDeCampo(campo, "FORMATO", MENSAJE_SIN_ZONA),)
    return ()


def rechazar_si_hay_defectos(defectos: Sequence[DefectoDeCampo]) -> None:
    if defectos:
        raise ValidacionRechazada(
            errores=[
                ErrorDeCampo(campo=d.campo, codigo=d.codigo, mensaje=d.mensaje) for d in defectos
            ]
        )


def asentar(
    sesion_bd: Session,
    *,
    accion: str,
    entidad_tipo: str,
    entidad_id: uuid.UUID,
    usuario_id: uuid.UUID,
    ocurrido_en: dt.datetime,
    motivo: str | None = None,
    regla_negocio: str | None = None,
    obra_id: uuid.UUID | None = None,
    datos_antes: Mapping[str, object] | None = None,
    datos_despues: Mapping[str, object] | None = None,
) -> uuid.UUID:
    """RN-04 · arquitectura §7.2 · regla 8 de CLAUDE.md. Escribe un asiento en la sesión recibida,
    dentro de la transacción que abrió quien llama, y devuelve su id. Nunca confirma ni abre otra
    transacción: si quien llama deshace, el asiento se deshace con el cambio, y si el INSERT falla,
    la transacción entera queda abortada. Un asiento mal formado lanza ValidacionRechazada antes de
    emitir ninguna sentencia."""
    resultado = revisar_asiento(
        accion=accion,
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        usuario_id=usuario_id,
        regla_negocio=regla_negocio,
        obra_id=obra_id,
        motivo=motivo,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
    )
    rechazar_si_hay_defectos(
        (*resultado.defectos, *defectos_de_momento("ocurrido_en", ocurrido_en, obligatorio=True))
    )
    if resultado.asiento is None:  # inalcanzable: sin defectos hay asiento; lo exige mypy
        raise RuntimeError("revisar_asiento no devolvió ni asiento ni defectos")
    asiento_id = uuid.uuid4()
    repositorio.insertar_asiento(
        sesion_bd, asiento_id=asiento_id, ocurrido_en=ocurrido_en, asiento=resultado.asiento
    )
    return asiento_id


def asentar_denegacion(
    sesion_bd: Session,
    *,
    usuario_id: uuid.UUID,
    ocurrido_en: dt.datetime,
    motivo: str,
    datos: Mapping[str, object],
) -> uuid.UUID:
    """RN-04 · modelo de datos §10 · C-1 enmendado (decisión del usuario del 2026-10-21). Un 403 de
    un usuario autenticado, atribuido a quien se le denegó: entidad_tipo 'usuario' y entidad_id su
    usuario_id. Sin regla_negocio, sin obra, sin datos_antes; los datos van a datos_despues. No
    recibe la sesión web ni la correlación: la primera es la credencial de la cookie y el rol de
    lectura lee esta tabla (invariante 21); la segunda va al registro técnico (API §2.7).
    «Transacción propia» la abre quien llama, separada de la de la petición; aquí no se confirma."""
    return asentar(
        sesion_bd,
        accion=AccionBitacora.DENEGAR,
        entidad_tipo="usuario",
        entidad_id=usuario_id,
        usuario_id=usuario_id,
        ocurrido_en=ocurrido_en,
        motivo=motivo,
        datos_despues=datos,
    )
