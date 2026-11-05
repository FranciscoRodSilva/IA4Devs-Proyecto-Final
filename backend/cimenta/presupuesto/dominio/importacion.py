"""Estados, errores y reglas puras de la importación de línea base (TKT-015a).

HDU-001 esc. 4, 6 y 29; RNF-17. Sin persistencia ni framework.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cimenta.presupuesto.dominio.lectura_analisis import normalizar_clave_insumo


class TipoErrorImportacion(StrEnum):
    REF_ROTA = "REF_ROTA"
    UNIDAD_DESCONOCIDA = "UNIDAD_DESCONOCIDA"
    SIN_APU = "SIN_APU"
    RENDIMIENTO_AUSENTE = "RENDIMIENTO_AUSENTE"
    DUPLICADO = "DUPLICADO"
    SIN_CONCEPTOS = "SIN_CONCEPTOS"
    PROCESO_INTERRUMPIDO = "PROCESO_INTERRUMPIDO"


class EstadoImportacion(StrEnum):
    RECIBIDO = "RECIBIDO"
    ANALIZANDO = "ANALIZANDO"
    VALIDADO = "VALIDADO"
    CON_ERRORES = "CON_ERRORES"
    CONFIRMADO = "CONFIRMADO"
    DESCARTADO = "DESCARTADO"


class MotivoInterrupcion(StrEnum):
    REINICIO = "REINICIO"
    EXCEPCION = "EXCEPCION"
    TRABAJADOR_TERMINADO = "TRABAJADOR_TERMINADO"
    ARCHIVO_ILEGIBLE = "ARCHIVO_ILEGIBLE"


_MENSAJES_INTERRUPCION: Mapping[MotivoInterrupcion, str] = {
    MotivoInterrupcion.REINICIO: (
        "El análisis se interrumpió porque el servidor se reinició o dejó de responder "
        "mientras analizaba. El archivo no tiene la culpa: puedes reintentar el análisis."
    ),
    MotivoInterrupcion.EXCEPCION: (
        "El análisis terminó por un error inesperado del analizador. Puedes reintentar el "
        "análisis; si se repite, el archivo puede traer algo que el analizador no sabe leer: "
        "avisa con el identificador de esta importación."
    ),
    MotivoInterrupcion.TRABAJADOR_TERMINADO: (
        "El proceso que analizaba el archivo terminó de forma abrupta. Puedes reintentar el "
        "análisis; se hará con un proceso nuevo."
    ),
    MotivoInterrupcion.ARCHIVO_ILEGIBLE: (
        "No se pudo obtener el archivo de la importación para analizarlo. Puedes reintentar el "
        "análisis; si se repite, vuelve a subir el archivo como una importación nueva."
    ),
}


@dataclass(frozen=True, slots=True)
class ErrorImportacion:
    tipo: TipoErrorImportacion
    hoja: str | None
    fila: int | None
    columna: str | None
    mensaje: str
    valor_original: str | None


@dataclass(frozen=True, slots=True)
class TrabajoAnalisis:
    importacion_id: UUID
    archivo_id: UUID
    insumos_existentes: Mapping[str, str]


def puede_analizarse(
    estado: EstadoImportacion,
    tipos_de_error: frozenset[TipoErrorImportacion],
) -> bool:
    """HDU-001 esc. 18 · PA-15.7 — cuándo admite un nuevo análisis."""
    if estado is EstadoImportacion.RECIBIDO:
        return True
    if estado is EstadoImportacion.CON_ERRORES:
        return tipos_de_error == frozenset({TipoErrorImportacion.PROCESO_INTERRUMPIDO})
    return False


def estado_tras_analisis(errores: Sequence[ErrorImportacion]) -> EstadoImportacion:
    """HDU-001 esc. 4 y 6 · M2 — VALIDADO sin errores, CON_ERRORES si hay uno."""
    if len(errores) == 0:
        return EstadoImportacion.VALIDADO
    return EstadoImportacion.CON_ERRORES


def error_de_interrupcion(motivo: MotivoInterrupcion) -> ErrorImportacion:
    """HDU-001 esc. 29 · RNF-17 — un único PROCESO_INTERRUMPIDO por causa."""
    return ErrorImportacion(
        tipo=TipoErrorImportacion.PROCESO_INTERRUMPIDO,
        hoja=None,
        fila=None,
        columna=None,
        mensaje=_MENSAJES_INTERRUPCION[motivo],
        valor_original=None,
    )


def mapa_de_insumos_existentes(insumos: Iterable[tuple[str, str]]) -> dict[str, str]:
    """HDU-001 esc. 4 · P6 — clave normalizada a unidad; gana la primera aparición."""
    resultado: dict[str, str] = {}
    for descripcion, unidad in insumos:
        clave = normalizar_clave_insumo(descripcion)
        if clave not in resultado:
            resultado[clave] = unidad
    return resultado
