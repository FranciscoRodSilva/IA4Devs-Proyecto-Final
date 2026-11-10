"""Caso de uso de la captura del tope del presupuesto de control (TKT-017c, fila C2).

Orquesta; no decide. La decisión de si un tope se admite vive en `dominio/captura_tope.py` (`RN-03`,
`RN-04`, `PA-03`). Aquí se abre una sola transacción, se comprueba que la línea base exista y esté
`CONGELADA`, se bloquea la fila de control con `FOR UPDATE` antes de evaluar (ADR-004), se llama a la
regla con el tope anterior y el importe de venta del tipo, se guarda el tope y se asienta la bitácora en
la misma transacción. Los rechazos salen por el contrato de error.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import asentar
from cimenta.presupuesto.aplicacion.consulta_linea_base import MENSAJE_LINEA_BASE_NO_EXISTE
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_error_del_motor
from cimenta.presupuesto.dominio.captura_tope import (
    CapturaAdmitida,
    CapturaRechazada,
    CausaRechazoCaptura,
    evaluar_captura_tope,
    sin_blanco,
)
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from contrato_error import (
    Accion,
    ConflictoEstado,
    ErrorContrato,
    ErrorDeCampo,
    NoEncontrado,
    ValidacionRechazada,
)
from tipos_base import Dinero

ROLES_CAPTURA = ("DIRECCION_GENERAL",)

_MENSAJE_SIN_CONGELADA = (
    "La línea base está en {estado}; el tope solo se captura sobre una línea base congelada."
)
_MENSAJE_TOPE_SUPERIOR = (
    "El tope de {clave} supera su importe de venta; implicaría vender por debajo del costo tope."
)
_MENSAJE_TIPO_NO_EXISTE = "El tipo de partida no existe."
_MENSAJE_SIN_CONTROL = "La línea base no tiene presupuesto de control para ese tipo de partida."
_MENSAJE_OBLIGATORIO = "El campo es obligatorio."


def _ruta(linea_base_id: uuid.UUID, tipo_partida_id: uuid.UUID) -> str:
    return f"/api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}"


def capturar_tope(
    contexto: ContextoPresupuesto,
    *,
    linea_base_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    importe_tope: Dinero,
    motivo: str | None,
    confirmar_superior_a_venta: bool,
    usuario_id: uuid.UUID,
) -> uuid.UUID:
    """Captura o recaptura el tope de un tipo de partida (RN-03, RN-04, PA-03)."""
    fabrica = contexto.fabrica_sesiones()
    try:
        with fabrica.begin() as sesion_bd:
            return _capturar(
                sesion_bd,
                contexto,
                linea_base_id=linea_base_id,
                tipo_partida_id=tipo_partida_id,
                importe_tope=importe_tope,
                motivo=motivo,
                confirmar_superior_a_venta=confirmar_superior_a_venta,
                usuario_id=usuario_id,
            )
    except DBAPIError as error:
        traducido = traducir_error_del_motor(
            error,
            ruta_reintento=_ruta(linea_base_id, tipo_partida_id),
            metodo_reintento="PUT",
            roles_reintento=ROLES_CAPTURA,
            rechazo_vigente=lambda: NoEncontrado(
                recurso="linea_base", mensaje=MENSAJE_LINEA_BASE_NO_EXISTE
            ),
        )
        if traducido is None:
            raise
        raise traducido from error


def _capturar(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    linea_base_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    importe_tope: Dinero,
    motivo: str | None,
    confirmar_superior_a_venta: bool,
    usuario_id: uuid.UUID,
) -> uuid.UUID:
    linea = repositorio_linea_base.leer_linea_base(sesion_bd, linea_base_id)
    if linea is None:
        raise NoEncontrado(recurso="linea_base", mensaje=MENSAJE_LINEA_BASE_NO_EXISTE)
    if linea.estado != "CONGELADA":
        raise ConflictoEstado(
            codigo="SIN_LINEA_BASE_CONGELADA",
            mensaje=_MENSAJE_SIN_CONGELADA.format(estado=linea.estado),
            detalle={"linea_base_id": linea.id, "estado": linea.estado},
        )
    tipo = repositorio_linea_base.leer_tipo_partida(sesion_bd, tipo_partida_id)
    if tipo is None:
        raise NoEncontrado(recurso="tipo_partida", mensaje=_MENSAJE_TIPO_NO_EXISTE)
    control = repositorio_linea_base.bloquear_control(sesion_bd, linea_base_id, tipo_partida_id)
    if control is None:
        raise NoEncontrado(recurso="presupuesto_control", mensaje=_MENSAJE_SIN_CONTROL)

    venta = next(
        f.importe_venta
        for f in repositorio_linea_base.importes_venta_de(sesion_bd, linea)
        if f.tipo_partida_id == tipo_partida_id
    )
    tope = importe_tope.cuantizar()
    motivo = sin_blanco(motivo)
    resultado = evaluar_captura_tope(
        tope_anterior=control.importe_tope,
        tope_nuevo=tope,
        importe_venta=venta,
        motivo=motivo,
        confirmar_superior_a_venta=confirmar_superior_a_venta,
    )
    if isinstance(resultado, CapturaRechazada):
        raise _rechazo(
            resultado.causa,
            linea_base_id=linea_base_id,
            tipo_partida_id=tipo_partida_id,
            clave=tipo.clave,
            venta=venta,
            tope=tope,
        )
    _persistir(
        sesion_bd,
        contexto,
        control_id=control.id,
        anterior=control.importe_tope,
        resultado=resultado,
        tope=tope,
        motivo=motivo,
        usuario_id=usuario_id,
        obra_id=linea.obra_id,
        clave=tipo.clave,
    )
    return control.id


def _persistir(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    control_id: uuid.UUID,
    anterior: Dinero | None,
    resultado: CapturaAdmitida,
    tope: Dinero,
    motivo: str | None,
    usuario_id: uuid.UUID,
    obra_id: uuid.UUID,
    clave: str,
) -> None:
    ahora = contexto.reloj()
    repositorio_linea_base.actualizar_tope(
        sesion_bd,
        control_id,
        importe_tope=tope,
        motivo=motivo,
        usuario_id=usuario_id,
        ahora=ahora,
        es_recaptura=resultado.es_recaptura,
    )
    if resultado.es_recaptura:
        assert anterior is not None, "una recaptura siempre tiene tope anterior"
        asentar(
            sesion_bd,
            accion="RECAPTURAR",
            entidad_tipo="presupuesto_control",
            entidad_id=control_id,
            usuario_id=usuario_id,
            ocurrido_en=ahora,
            regla_negocio="RN-03",
            motivo=motivo,
            obra_id=obra_id,
            datos_antes={"importe_tope": anterior.serializar()},
            datos_despues={"importe_tope": tope.serializar()},
        )
        return
    asentar(
        sesion_bd,
        accion="CREAR",
        entidad_tipo="presupuesto_control",
        entidad_id=control_id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        motivo=motivo,
        obra_id=obra_id,
        datos_despues={"tipo_partida": clave, "importe_tope": tope.serializar()},
    )


def _rechazo(
    causa: CausaRechazoCaptura,
    *,
    linea_base_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    clave: str,
    venta: Dinero,
    tope: Dinero,
) -> ErrorContrato:
    """Traduce la causa del dominio a su contrato de error; no decide ninguna regla."""
    if causa == CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR:
        return ConflictoEstado(
            codigo="TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR",
            mensaje=_MENSAJE_TOPE_SUPERIOR.format(clave=clave),
            detalle={"tipo_partida": clave, "importe_venta": venta, "importe_tope": tope},
            acciones=(
                Accion(
                    "CONFIRMAR_TOPE_SUPERIOR",
                    "PUT",
                    _ruta(linea_base_id, tipo_partida_id),
                    ROLES_CAPTURA,
                ),
            ),
        )
    return ValidacionRechazada(
        errores=[ErrorDeCampo(campo="motivo", codigo="OBLIGATORIO", mensaje=_MENSAJE_OBLIGATORIO)]
    )
