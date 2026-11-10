"""Lectura de una línea base con sus importes por tipo de partida (TKT-017b1, fila B3).

Una sola transacción de lectura, sin bloqueo. La respuesta del congelado la usa para devolver la línea
base ya congelada; la ruta de lectura (fila B4) reutiliza esta misma función.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from cimenta.identidad.interfaz import UsuarioResumen, nombres_de_usuarios
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from contrato_error import NoEncontrado
from tipos_base import Dinero

_MENSAJE_NO_EXISTE = "La línea base no existe."


@dataclass(frozen=True, slots=True)
class ImporteDeTipo:
    tipo_partida_id: uuid.UUID
    clave: str
    nombre: str
    importe_venta: Dinero


@dataclass(frozen=True, slots=True)
class LineaBaseConsultada:
    id: uuid.UUID
    obra_id: uuid.UUID
    version: int
    estado: str
    importe_venta: Dinero
    congelada_en: datetime | None
    congelada_por: UsuarioResumen | None
    motivo: str | None
    por_tipo_partida: tuple[ImporteDeTipo, ...]


def obtener_linea_base(
    contexto: ContextoPresupuesto, *, linea_base_id: uuid.UUID
) -> LineaBaseConsultada:
    """La línea base con quién la congeló y el importe de venta de cada tipo de partida."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio_linea_base.leer_linea_base_completa(sesion_bd, linea_base_id)
        if fila is None:
            raise NoEncontrado(recurso="linea_base", mensaje=_MENSAJE_NO_EXISTE)
        por_tipo = repositorio_linea_base.importes_venta_por_tipo(sesion_bd, linea_base_id)
        congelada_por = None
        if fila.congelada_por_id is not None:
            nombres = nombres_de_usuarios(sesion_bd, [fila.congelada_por_id])
            if fila.congelada_por_id in nombres:
                congelada_por = UsuarioResumen(
                    id=fila.congelada_por_id, nombre=nombres[fila.congelada_por_id]
                )
        return LineaBaseConsultada(
            id=fila.id,
            obra_id=fila.obra_id,
            version=fila.version,
            estado=fila.estado,
            importe_venta=fila.importe_venta,
            congelada_en=fila.congelada_en,
            congelada_por=congelada_por,
            motivo=fila.motivo,
            por_tipo_partida=tuple(
                ImporteDeTipo(f.tipo_partida_id, f.clave, f.nombre, f.importe_venta)
                for f in por_tipo
            ),
        )
