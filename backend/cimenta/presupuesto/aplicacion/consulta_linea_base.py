"""Lecturas de la línea base (TKT-017b1, fila B3, y TKT-017b2, fila B4).

Cada función abre una transacción de lectura, sin bloqueo, y la cierra al volver. No decide reglas:
traduce lo que no existe a `NoEncontrado` y entrega al borde HTTP datos ya leídos. Los importes de una
línea base `CONGELADA` salen de las copias, nunca de `partida_concepto` (`RN-01`).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from cimenta.identidad.interfaz import UsuarioResumen, nombres_de_usuarios
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from cimenta.presupuesto.infraestructura.repositorio_linea_base import (
    FilaConceptoCopiado,
    FilaControl,
    FilaLineaBaseLeida,
    FilaRenglonExplosion,
    FilaTipoPartida,
)
from contrato_error import NoEncontrado
from tipos_base import Cantidad, Dinero, Rendimiento

MENSAJE_LINEA_BASE_NO_EXISTE = "La línea base no existe."
MENSAJE_OBRA_NO_EXISTE = "La obra no existe."


@dataclass(frozen=True, slots=True)
class TipoPartidaConsultado:
    id: uuid.UUID
    clave: str
    nombre: str


@dataclass(frozen=True, slots=True)
class ImporteDeTipo:
    tipo_partida: TipoPartidaConsultado
    importe_venta: Dinero


@dataclass(frozen=True, slots=True)
class ConceptoConsultado:
    id: uuid.UUID
    codigo: str
    descripcion: str
    unidad: str
    cantidad: Cantidad
    precio_unitario: Dinero
    importe: Dinero
    nivel: str
    area: str
    tipo_partida: TipoPartidaConsultado


@dataclass(frozen=True, slots=True)
class InsumoConsultado:
    id: uuid.UUID
    codigo: str
    descripcion: str
    unidad: str


@dataclass(frozen=True, slots=True)
class RenglonConsultado:
    tipo_partida: TipoPartidaConsultado
    insumo: InsumoConsultado
    cantidad_presupuestada: Cantidad
    rendimiento_congelado: Rendimiento
    costo_unitario: Dinero
    importe_costo: Dinero


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


@dataclass(frozen=True, slots=True)
class ConceptosConsultados:
    elementos: tuple[ConceptoConsultado, ...]
    pagina: int
    tamano_pagina: int
    total: int


@dataclass(frozen=True, slots=True)
class ControlConsultado:
    id: uuid.UUID
    tipo_partida: TipoPartidaConsultado
    importe_venta: Dinero
    importe_sugerido: Dinero
    importe_tope: Dinero | None
    capturado_por: UsuarioResumen | None
    capturado_en: datetime | None
    actualizado_por: UsuarioResumen | None
    actualizado_en: datetime | None
    motivo_ultimo_cambio: str | None


@dataclass(frozen=True, slots=True)
class ExplosionConsultada:
    linea_base_id: uuid.UUID
    renglones: tuple[RenglonConsultado, ...]
    importe_total: Dinero


def listar_lineas_base(
    contexto: ContextoPresupuesto, obra_id: uuid.UUID
) -> tuple[LineaBaseConsultada, ...]:
    """Las versiones de la obra, la más reciente primero."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        if repositorio_linea_base.leer_obra(sesion_bd, obra_id) is None:
            raise NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)
        filas = repositorio_linea_base.lineas_base_completas_de_obra(sesion_bd, obra_id)
        nombres = _nombres_de_quien_congelo(sesion_bd, filas)
        return tuple(_consultada(sesion_bd, fila, nombres) for fila in filas)


def obtener_linea_base(
    contexto: ContextoPresupuesto, *, linea_base_id: uuid.UUID
) -> LineaBaseConsultada:
    """La línea base con quién la congeló y el importe de venta de cada tipo de partida."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = _leer_o_no_existe(sesion_bd, linea_base_id)
        return _consultada(sesion_bd, fila, _nombres_de_quien_congelo(sesion_bd, [fila]))


def listar_conceptos(
    contexto: ContextoPresupuesto,
    linea_base_id: uuid.UUID,
    *,
    tipo_partida_id: uuid.UUID | None,
    nivel: str | None,
    q: str | None,
    pagina: int,
    tamano_pagina: int,
) -> ConceptosConsultados:
    """Una página de las copias de conceptos; vacía mientras la línea base está en `BORRADOR`."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        _leer_o_no_existe(sesion_bd, linea_base_id)
        resultado = repositorio_linea_base.conceptos_de_linea_base(
            sesion_bd,
            linea_base_id,
            tipo_partida_id=tipo_partida_id,
            nivel_nombre=nivel,
            texto=q,
            desplazamiento=(pagina - 1) * tamano_pagina,
            limite=tamano_pagina,
        )
        return ConceptosConsultados(
            elementos=tuple(_concepto_consultado(f) for f in resultado.filas),
            pagina=pagina,
            tamano_pagina=tamano_pagina,
            total=resultado.total,
        )


def obtener_explosion(
    contexto: ContextoPresupuesto,
    linea_base_id: uuid.UUID,
    *,
    tipo_partida_id: uuid.UUID | None,
) -> ExplosionConsultada:
    """La explosión congelada; `importe_total` es la suma de los renglones devueltos (RN-24)."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        _leer_o_no_existe(sesion_bd, linea_base_id)
        renglones = repositorio_linea_base.renglones_de_explosion(
            sesion_bd, linea_base_id, tipo_partida_id
        )
        total = Dinero("0.0000")
        for renglon in renglones:
            total = total + renglon.importe_costo
        return ExplosionConsultada(
            linea_base_id=linea_base_id,
            renglones=tuple(_renglon_consultado(r) for r in renglones),
            importe_total=total,
        )


def listar_presupuesto_control(
    contexto: ContextoPresupuesto, linea_base_id: uuid.UUID
) -> tuple[ControlConsultado, ...]:
    """Una fila por tipo de partida; vacía mientras la línea base está en `BORRADOR` (P-9)."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        linea = _leer_o_no_existe(sesion_bd, linea_base_id)
        filas = repositorio_linea_base.controles(sesion_bd, linea_base_id)
        if not filas:
            return ()
        ventas = {
            f.tipo_partida_id: f.importe_venta
            for f in repositorio_linea_base.importes_venta_de(sesion_bd, linea)
        }
        ids = {
            quien
            for f in filas
            for quien in (f.capturado_por_id, f.actualizado_por_id)
            if quien is not None
        }
        nombres = nombres_de_usuarios(sesion_bd, ids)
        return tuple(_control_consultado(f, ventas[f.tipo_partida.id], nombres) for f in filas)


def _usuario_resumen(
    quien: uuid.UUID | None, nombres: dict[uuid.UUID, str]
) -> UsuarioResumen | None:
    if quien is None or quien not in nombres:
        return None
    return UsuarioResumen(id=quien, nombre=nombres[quien])


def _control_consultado(
    fila: FilaControl, importe_venta: Dinero, nombres: dict[uuid.UUID, str]
) -> ControlConsultado:
    return ControlConsultado(
        id=fila.id,
        tipo_partida=_tipo_consultado(fila.tipo_partida),
        importe_venta=importe_venta,
        importe_sugerido=fila.importe_sugerido,
        importe_tope=fila.importe_tope,
        capturado_por=_usuario_resumen(fila.capturado_por_id, nombres),
        capturado_en=fila.capturado_en,
        actualizado_por=_usuario_resumen(fila.actualizado_por_id, nombres),
        actualizado_en=fila.actualizado_en,
        motivo_ultimo_cambio=fila.motivo_ultimo_cambio,
    )


def _tipo_consultado(tipo: FilaTipoPartida) -> TipoPartidaConsultado:
    return TipoPartidaConsultado(id=tipo.id, clave=tipo.clave, nombre=tipo.nombre)


def _concepto_consultado(fila: FilaConceptoCopiado) -> ConceptoConsultado:
    return ConceptoConsultado(
        id=fila.id,
        codigo=fila.codigo,
        descripcion=fila.descripcion,
        unidad=fila.unidad,
        cantidad=fila.cantidad,
        precio_unitario=fila.precio_unitario,
        importe=fila.importe,
        nivel=fila.nivel,
        area=fila.area,
        tipo_partida=_tipo_consultado(fila.tipo_partida),
    )


def _renglon_consultado(fila: FilaRenglonExplosion) -> RenglonConsultado:
    return RenglonConsultado(
        tipo_partida=_tipo_consultado(fila.tipo_partida),
        insumo=InsumoConsultado(
            id=fila.insumo.id,
            codigo=fila.insumo.codigo,
            descripcion=fila.insumo.descripcion,
            unidad=fila.insumo.unidad,
        ),
        cantidad_presupuestada=fila.cantidad_presupuestada,
        rendimiento_congelado=fila.rendimiento_congelado,
        costo_unitario=fila.costo_unitario,
        importe_costo=fila.importe_costo,
    )


def _leer_o_no_existe(sesion_bd: Session, linea_base_id: uuid.UUID) -> FilaLineaBaseLeida:
    fila = repositorio_linea_base.leer_linea_base(sesion_bd, linea_base_id)
    if fila is None:
        raise NoEncontrado(recurso="linea_base", mensaje=MENSAJE_LINEA_BASE_NO_EXISTE)
    return fila


def _nombres_de_quien_congelo(
    sesion_bd: Session, filas: Sequence[FilaLineaBaseLeida]
) -> dict[uuid.UUID, str]:
    ids = {f.congelada_por_id for f in filas if f.congelada_por_id is not None}
    return nombres_de_usuarios(sesion_bd, ids)


def _consultada(
    sesion_bd: Session, fila: FilaLineaBaseLeida, nombres: dict[uuid.UUID, str]
) -> LineaBaseConsultada:
    por_tipo = repositorio_linea_base.importes_venta_de(sesion_bd, fila)
    return LineaBaseConsultada(
        id=fila.id,
        obra_id=fila.obra_id,
        version=fila.version,
        estado=fila.estado,
        importe_venta=fila.importe_venta,
        congelada_en=fila.congelada_en,
        congelada_por=_usuario_resumen(fila.congelada_por_id, nombres),
        motivo=fila.motivo,
        por_tipo_partida=tuple(
            ImporteDeTipo(
                TipoPartidaConsultado(id=f.tipo_partida_id, clave=f.clave, nombre=f.nombre),
                f.importe_venta,
            )
            for f in por_tipo
        ),
    )
