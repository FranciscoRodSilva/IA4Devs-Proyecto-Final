"""Caso de uso del congelado de la línea base (TKT-017b1, fila B2).

Orquesta; no decide. La decisión de si una línea base se puede congelar vive en
`dominio/congelado.py` (`RN-01`). Aquí se abre una sola transacción, se bloquea la obra y después la
línea base, se comprueban las precondiciones en el orden de «Orden de comprobaciones del congelado»
del diseño, se copian los conceptos de la obra, se guarda la explosión que `explotar_filas` calculó (lo validado es
lo congelado: invariante 19), se crean los controles, se pasa la línea base a `CONGELADA` y la obra a
`ACTIVA`, y se asienta `CONGELAR` en la misma transacción. Los rechazos salen por el contrato de error.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import asentar
from cimenta.presupuesto.aplicacion.causas_explosion import detalle_de_causas
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_error_del_motor
from cimenta.presupuesto.dominio.congelado import (
    CausaRechazoCongelado,
    CongeladoAdmitido,
    CongeladoRechazado,
    evaluar_congelado,
)
from cimenta.presupuesto.dominio.explosion import RechazoExplosion
from cimenta.presupuesto.dominio.explosion_materializada import explotar_filas
from cimenta.presupuesto.dominio.materializacion import LineaBaseDeObra
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from cimenta.presupuesto.infraestructura.repositorio_linea_base import (
    FilaLineaBase,
    FilaLineaBaseLeida,
    FilaObra,
)
from contrato_error import ConflictoEstado, ErrorContrato, NoEncontrado, RechazoRegla

_ROLES_CONGELADO = ("DIRECTOR_PROYECTOS",)

_MENSAJE_NO_EXISTE = "La línea base no existe."
_MENSAJE_ESTADO_LINEA_BASE = (
    "La línea base está en {estado}; solo se congela una línea base en BORRADOR."
)
_MENSAJE_RN01 = (
    "La obra {codigo} ya tiene una línea base congelada; para sustituirla hay que crear una "
    "versión nueva que marque la anterior como SUPERSEDIDA."
)
_MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
_MENSAJE_EXPLOSION = "La explosión de insumos de la importación no se puede calcular."


def congelar_linea_base(
    contexto: ContextoPresupuesto,
    *,
    linea_base_id: uuid.UUID,
    motivo: str,
    usuario_id: uuid.UUID,
) -> uuid.UUID:
    """Congela una línea base `BORRADOR` y activa la obra (RN-01)."""
    fabrica = contexto.fabrica_sesiones()
    try:
        with fabrica.begin() as sesion_bd:
            return _congelar(
                sesion_bd,
                contexto,
                linea_base_id=linea_base_id,
                motivo=motivo,
                usuario_id=usuario_id,
            )
    except DBAPIError as error:
        traducido = traducir_error_del_motor(
            error,
            ruta_reintento=f"/api/v1/lineas-base/{linea_base_id}/congelacion",
            metodo_reintento="POST",
            roles_reintento=_ROLES_CONGELADO,
            rechazo_vigente=lambda: _rechazo_vigente(contexto, linea_base_id),
        )
        if traducido is None:
            raise
        raise traducido from error


def _congelar(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    linea_base_id: uuid.UUID,
    motivo: str,
    usuario_id: uuid.UUID,
) -> uuid.UUID:
    repositorio = repositorio_linea_base
    previa = repositorio.leer_linea_base(sesion_bd, linea_base_id)
    if previa is None:
        raise NoEncontrado(recurso="linea_base", mensaje=_MENSAJE_NO_EXISTE)
    obra = repositorio.bloquear_obra(sesion_bd, previa.obra_id)
    linea = repositorio.bloquear_linea_base(sesion_bd, linea_base_id)
    if obra is None or linea is None:
        raise NoEncontrado(recurso="linea_base", mensaje=_MENSAJE_NO_EXISTE)

    lineas = repositorio.lineas_base_de_obra(sesion_bd, obra.id)
    _rechazar_si_no_se_congela(obra, linea, _vigente(lineas))

    resultado = explotar_filas(repositorio.filas_explotables(sesion_bd, obra.id))
    if isinstance(resultado, RechazoExplosion):
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_EXPLOSION,
            detalle={
                "linea_base_id": linea_base_id,
                "causas": detalle_de_causas(resultado.causas),
            },
        )

    ahora = contexto.reloj()
    repositorio.copiar_conceptos(sesion_bd, linea_base_id, obra.id)
    repositorio.insertar_explosion(sesion_bd, linea_base_id, resultado)
    repositorio.insertar_controles(sesion_bd, linea_base_id, resultado)
    repositorio.congelar(sesion_bd, linea_base_id, ahora, usuario_id, motivo)
    repositorio.activar_obra(sesion_bd, obra.id, ahora, usuario_id)
    asentar(
        sesion_bd,
        accion="CONGELAR",
        entidad_tipo="linea_base",
        entidad_id=linea_base_id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        regla_negocio="RN-01",
        motivo=motivo,
        obra_id=obra.id,
        datos_antes={"estado": "BORRADOR"},
        datos_despues={
            "estado": "CONGELADA",
            "version": linea.version,
            "importe_venta": linea.importe_venta.serializar(),
        },
    )
    return linea_base_id


def _vigente(lineas: list[FilaLineaBase]) -> LineaBaseDeObra | None:
    vigente = next((linea for linea in lineas if linea.estado == "CONGELADA"), None)
    return None if vigente is None else LineaBaseDeObra(id=vigente.id, version=vigente.version)


def _rechazar_si_no_se_congela(
    obra: FilaObra, linea: FilaLineaBaseLeida, vigente: LineaBaseDeObra | None
) -> None:
    """Traduce la causa del dominio a su contrato de error; no decide ninguna regla."""
    resultado = evaluar_congelado(
        estado_linea_base=linea.estado,
        otra_congelada=vigente,
        estado_obra=obra.estado,
    )
    if isinstance(resultado, CongeladoAdmitido):
        return
    if resultado.causa == CausaRechazoCongelado.LINEA_BASE_EN_OTRO_ESTADO:
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_ESTADO_LINEA_BASE.format(estado=linea.estado),
            detalle={"linea_base_id": linea.id, "estado": linea.estado},
        )
    if resultado.causa == CausaRechazoCongelado.OBRA_CON_CONGELADA:
        raise _rechazo_congelada_vigente(obra, resultado.datos)
    raise _conflicto_obra(obra, resultado)


def _conflicto_obra(obra: FilaObra, rechazo: CongeladoRechazado) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje=_MENSAJE_FUERA_DE_PLANEACION.format(
            codigo=obra.codigo, estado=rechazo.datos["estado_obra"]
        ),
        detalle={"obra": f"{obra.codigo} · {obra.nombre}", **rechazo.datos},
    )


def _rechazo_congelada_vigente(obra: FilaObra, datos: Mapping[str, object]) -> RechazoRegla:
    return RechazoRegla(
        regla="RN-01",
        mensaje=_MENSAJE_RN01.format(codigo=obra.codigo),
        detalle={
            "obra": f"{obra.codigo} · {obra.nombre}",
            "linea_base_vigente_id": datos["linea_base_vigente_id"],
            "version_vigente": datos["version_vigente"],
        },
        acciones=(),
    )


def _rechazo_vigente(contexto: ContextoPresupuesto, linea_base_id: uuid.UUID) -> ErrorContrato:
    """Transacción corta de solo lectura: el rechazo de la congelada vigente tras perder la carrera."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        linea = repositorio_linea_base.leer_linea_base(sesion_bd, linea_base_id)
        obra = None if linea is None else repositorio_linea_base.leer_obra(sesion_bd, linea.obra_id)
        if obra is not None:
            vigente = _vigente(repositorio_linea_base.lineas_base_de_obra(sesion_bd, obra.id))
            if vigente is not None:
                return _rechazo_congelada_vigente(
                    obra,
                    {"linea_base_vigente_id": vigente.id, "version_vigente": vigente.version},
                )
    return NoEncontrado(recurso="linea_base", mensaje=_MENSAJE_NO_EXISTE)
