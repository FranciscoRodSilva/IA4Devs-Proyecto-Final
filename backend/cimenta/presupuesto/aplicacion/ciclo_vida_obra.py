"""Casos de uso de las tres transiciones de la obra (TKT-012b, fila A6): suspender, reactivar y cerrar.

Orquesta; no decide. La tabla de transiciones (D-2) vive en `dominio/ciclo_vida_obra.py`. Las tres operaciones
comparten una transacción con `SELECT ... FOR UPDATE` de la obra **antes** de leer su estado (CA-13), y el
asiento de bitácora en la misma sesión (regla 8). La máquina de estados vive en las decisiones D-2 y D-3 de
la spec de TKT-012b y no tiene `RN` en el PRD: el asiento no cita regla (F002a), igual que `actualizar_obra`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Final

from sqlalchemy.exc import DBAPIError

from cimenta.auditoria.interfaz import asentar
from cimenta.presupuesto.aplicacion.consulta_linea_base import MENSAJE_OBRA_NO_EXISTE
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.obras import ROLES_ALTA
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_fallo_de_obra
from cimenta.presupuesto.dominio.ciclo_vida_obra import (
    EstadoObraDominio,
    OperacionObra,
    TransicionRechazada,
    evaluar_transicion,
)
from cimenta.presupuesto.infraestructura import repositorio_obra
from contrato_error.acciones import Accion
from contrato_error.excepciones import ConflictoEstado, NoEncontrado

MENSAJE_ESTADO_NO_PERMITE: Final = "La obra {codigo} está en {estado} y no admite esta operación."
# F002a: la máquina de estados no tiene RN en el PRD; sus asientos no citan regla.
_REGLA_DE_LAS_TRANSICIONES: Final[str | None] = None

# Operación -> (clave de la acción del `409`, segmento de la ruta).
_ACCION_POR_OPERACION: Final[dict[OperacionObra, tuple[str, str]]] = {
    OperacionObra.SUSPENDER: ("SUSPENDER_OBRA", "suspension"),
    OperacionObra.REACTIVAR: ("REACTIVAR_OBRA", "reactivacion"),
    OperacionObra.CERRAR: ("CERRAR_OBRA", "cierre"),
}


def ruta_de_operacion(obra_id: uuid.UUID, operacion: OperacionObra) -> str:
    """Ruta `POST` de la operación sobre la obra: la de su acción en el `409` y la de su reintento."""
    _, segmento = _ACCION_POR_OPERACION[operacion]
    return f"/api/v1/obras/{obra_id}/{segmento}"


def acciones_de_operaciones(
    obra_id: uuid.UUID,
    operaciones: Iterable[OperacionObra],
    *,
    solo: frozenset[OperacionObra] = frozenset(OperacionObra),
) -> tuple[Accion, ...]:
    """Acciones `POST` de las operaciones dadas, en su orden, filtradas por `solo`. Única fuente de las `acciones`."""
    return tuple(
        Accion(
            _ACCION_POR_OPERACION[operacion][0],
            "POST",
            ruta_de_operacion(obra_id, operacion),
            ROLES_ALTA,
        )
        for operacion in operaciones
        if operacion in solo
    )


def suspender_obra(
    contexto: ContextoPresupuesto, obra_id: uuid.UUID, motivo: str, usuario_id: uuid.UUID
) -> None:
    """`ACTIVA → SUSPENDIDA`, asentando `SUSPENDER` (D-2)."""
    _transicionar(OperacionObra.SUSPENDER, contexto, obra_id, motivo, usuario_id)


def reactivar_obra(
    contexto: ContextoPresupuesto, obra_id: uuid.UUID, motivo: str, usuario_id: uuid.UUID
) -> None:
    """`SUSPENDIDA → ACTIVA`, asentando `REACTIVAR` (D-2)."""
    _transicionar(OperacionObra.REACTIVAR, contexto, obra_id, motivo, usuario_id)


def cerrar_obra(
    contexto: ContextoPresupuesto, obra_id: uuid.UUID, motivo: str, usuario_id: uuid.UUID
) -> None:
    """`PLANEACION`, `ACTIVA` o `SUSPENDIDA` `→ CERRADA`, asentando `CERRAR` (D-2)."""
    _transicionar(OperacionObra.CERRAR, contexto, obra_id, motivo, usuario_id)


def _transicionar(
    operacion: OperacionObra,
    contexto: ContextoPresupuesto,
    obra_id: uuid.UUID,
    motivo: str,
    usuario_id: uuid.UUID,
) -> None:
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            obra = repositorio_obra.bloquear_obra_completa(sesion_bd, obra_id)
            if obra is None:
                raise NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)
            ahora = contexto.reloj()
            estado = EstadoObraDominio(obra.estado)
            resultado = evaluar_transicion(estado, operacion)
            if isinstance(resultado, TransicionRechazada):
                raise ConflictoEstado(
                    codigo="ESTADO_NO_PERMITE_OPERACION",
                    mensaje=MENSAJE_ESTADO_NO_PERMITE.format(
                        codigo=obra.codigo, estado=estado.value
                    ),
                    detalle={
                        "estado": estado.value,
                        "operaciones_admitidas": [
                            op.value for op in resultado.operaciones_admitidas
                        ],
                    },
                    acciones=acciones_de_operaciones(obra_id, resultado.operaciones_admitidas),
                )
            repositorio_obra.cambiar_estado_obra(
                sesion_bd, obra_id, resultado.estado_destino.value, ahora, usuario_id
            )
            asentar(
                sesion_bd,
                accion=operacion.value,
                entidad_tipo="obra",
                entidad_id=obra_id,
                usuario_id=usuario_id,
                ocurrido_en=ahora,
                obra_id=obra_id,
                regla_negocio=_REGLA_DE_LAS_TRANSICIONES,
                motivo=motivo,
                datos_antes={"estado": estado.value},
                datos_despues={"estado": resultado.estado_destino.value},
            )
    except DBAPIError as error:
        traducido = traducir_fallo_de_obra(
            error,
            ruta_reintento=ruta_de_operacion(obra_id, operacion),
            metodo_reintento="POST",
            roles_reintento=ROLES_ALTA,
        )
        if traducido is None:
            raise
        raise traducido from error
