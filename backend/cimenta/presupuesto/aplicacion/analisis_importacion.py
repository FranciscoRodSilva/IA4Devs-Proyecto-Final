"""Casos de uso del análisis síncrono de importación (TKT-015a)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import structlog
from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.dominio.importacion import (
    MotivoInterrupcion,
    TrabajoAnalisis,
    error_de_interrupcion,
    estado_tras_analisis,
    mapa_de_insumos_existentes,
    progreso_de_lectura,
    puede_analizarse,
)
from cimenta.presupuesto.infraestructura import repositorio_importacion as repositorio
from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorAnalisis, EjecutorCerrado
from cimenta.presupuesto.infraestructura.trabajo_analisis import ResultadoAnalisis
from contrato_error import ConflictoEstado, NoEncontrado

_registro = structlog.get_logger("cimenta.presupuesto")

_MENSAJE_ESTADO_NO_PERMITE = (
    "La importación está en {estado} y no admite el análisis. Solo se analiza una importación "
    "RECIBIDO o una CON_ERRORES interrumpida."
)


def iniciar_analisis(
    fabrica_sesiones: sessionmaker[Session],
    importacion_id: uuid.UUID,
) -> TrabajoAnalisis:
    """Reserva la importación, limpia errores previos y devuelve el trabajo a analizar."""
    with fabrica_sesiones.begin() as sesion_bd:
        fila = repositorio.bloquear_importacion(sesion_bd, importacion_id)
        if fila is None:
            raise NoEncontrado(
                recurso="importacion",
                mensaje="La importación no existe.",
            )
        tipos = repositorio.tipos_de_error(sesion_bd, importacion_id)
        if not puede_analizarse(fila.estado, tipos):
            raise ConflictoEstado(
                codigo="ESTADO_NO_PERMITE_OPERACION",
                mensaje=_MENSAJE_ESTADO_NO_PERMITE.format(estado=fila.estado.value),
                detalle={
                    "importacion_id": str(importacion_id),
                    "estado": fila.estado.value,
                },
            )
        repositorio.borrar_errores(sesion_bd, importacion_id)
        repositorio.pasar_a_analizando(sesion_bd, importacion_id)
        insumos = mapa_de_insumos_existentes(repositorio.insumos_existentes(sesion_bd))
        return TrabajoAnalisis(
            importacion_id=fila.id,
            archivo_id=fila.archivo_id,
            insumos_existentes=insumos,
        )


def registrar_resultado(
    fabrica_sesiones: sessionmaker[Session],
    importacion_id: uuid.UUID,
    resultado: ResultadoAnalisis,
) -> bool:
    """Cierra el análisis e inserta errores en la misma transacción."""
    with fabrica_sesiones.begin() as sesion_bd:
        estado = estado_tras_analisis(resultado.errores)
        if not repositorio.cerrar_analisis(
            sesion_bd,
            importacion_id,
            estado=estado,
            filas_leidas=resultado.filas_leidas,
            filas_validas=resultado.filas_validas,
            filas_rechazadas=resultado.filas_rechazadas,
            preparacion=resultado.preparacion,
        ):
            _registro.warning(
                "resultado_descartado",
                importacion_id=str(importacion_id),
            )
            return False
        repositorio.insertar_errores(sesion_bd, importacion_id, resultado.errores)
        return True


def registrar_interrupcion(
    fabrica_sesiones: sessionmaker[Session],
    importacion_id: uuid.UUID,
    motivo: MotivoInterrupcion,
) -> bool:
    """Marca la importación interrumpida e inserta PROCESO_INTERRUMPIDO."""
    with fabrica_sesiones.begin() as sesion_bd:
        if not repositorio.interrumpir(sesion_bd, importacion_id):
            return False
        repositorio.insertar_errores(
            sesion_bd,
            importacion_id,
            (error_de_interrupcion(motivo),),
        )
        return True


def obtener_preparacion(
    fabrica_sesiones: sessionmaker[Session],
    importacion_id: uuid.UUID,
) -> dict[str, object] | None:
    """Lee la preparación persistida sin abrir el archivo."""
    with fabrica_sesiones.begin() as sesion_bd:
        return repositorio.leer_preparacion(sesion_bd, importacion_id)


def solicitar_analisis(
    fabrica_sesiones: sessionmaker[Session],
    ejecutor: EjecutorAnalisis,
    importacion_id: uuid.UUID,
) -> None:
    """Reserva la importación y encola su análisis sin esperarlo (CA-12).

    Si el ejecutor ya se cerró, la importación queda `CON_ERRORES` con `REINICIO` y se relanza
    `EjecutorCerrado`.
    """
    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    try:
        ejecutor.encolar(trabajo)
    except EjecutorCerrado:
        registrar_interrupcion(fabrica_sesiones, importacion_id, MotivoInterrupcion.REINICIO)
        raise


class SeguimientoImportacion:
    """Persistencia del avance del ejecutor: una transacción corta por llamada."""

    def __init__(self, fabrica_sesiones: sessionmaker[Session]) -> None:
        self._fabrica_sesiones = fabrica_sesiones

    def latir(self, ids: Sequence[uuid.UUID]) -> None:
        if not ids:
            return
        with self._fabrica_sesiones.begin() as sesion_bd:
            repositorio.refrescar_latido(sesion_bd, ids)

    def avanzar(self, importacion_id: uuid.UUID, hojas_leidas: int, hojas_totales: int) -> None:
        with self._fabrica_sesiones.begin() as sesion_bd:
            repositorio.registrar_progreso(
                sesion_bd,
                importacion_id,
                progreso_de_lectura(hojas_leidas, hojas_totales),
            )

    def terminar(self, importacion_id: uuid.UUID, resultado: ResultadoAnalisis) -> None:
        registrar_resultado(self._fabrica_sesiones, importacion_id, resultado)

    def interrumpir(self, importacion_id: uuid.UUID, motivo: MotivoInterrupcion) -> None:
        registrar_interrupcion(self._fabrica_sesiones, importacion_id, motivo)
