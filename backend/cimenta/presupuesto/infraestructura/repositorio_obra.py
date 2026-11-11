"""Repositorio de la obra (TKT-012a, entrega a, fila A2).

Lectura y escritura de la tabla `obra` para el alta y la consulta. Cada función recibe la sesión
del caso de uso y no confirma la transacción. Los porcentajes llegan como `Porcentaje` y se guardan
cuantizados a la escala de su columna; al leer, se envuelven de nuevo en `Porcentaje`.

La unicidad del código no se comprueba aquí: la garantiza `uq_obra_codigo` y el caso de uso traduce
su violación. Las consultas de obra leen la línea base vigente (`CONGELADA`) con un `LEFT OUTER JOIN`;
el índice parcial `uq_linea_base_obra_id_congelada` garantiza a lo sumo una fila por obra.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import Row, and_, func, insert, select
from sqlalchemy.orm import Session

from cimenta.presupuesto.infraestructura.tablas import empresa, linea_base, obra
from tipos_base import Porcentaje

_LIMITE_EMPRESAS_ACTIVAS = 2


class FilaObraCompleta(NamedTuple):
    """La obra con sus parámetros y la línea base que hoy es vigente (la `CONGELADA`), si la hay."""

    id: uuid.UUID
    codigo: str
    nombre: str
    domicilio: str
    tipo_contrato: str
    retencion_destajo_pct: Porcentaje
    fondo_garantia_pct: Porcentaje
    iva_acreditable: bool
    umbral_alerta_pct: Porcentaje | None
    estado: str
    linea_base_vigente_id: uuid.UUID | None
    creado_en: datetime
    actualizado_en: datetime | None


class PaginaObras(NamedTuple):
    """Una ventana de la lista de obras, con el total que cumple el filtro."""

    filas: list[FilaObraCompleta]
    total: int


def empresas_activas(sesion_bd: Session) -> list[uuid.UUID]:
    """Hasta dos empresas activas, por orden de id. El caso de uso exige exactamente una (A9)."""
    sentencia = (
        select(empresa.c.id)
        .where(empresa.c.activa.is_(True))
        .order_by(empresa.c.id)
        .limit(_LIMITE_EMPRESAS_ACTIVAS)
    )
    return [fila.id for fila in sesion_bd.execute(sentencia)]


def insertar_obra(
    sesion_bd: Session,
    *,
    obra_id: uuid.UUID,
    empresa_id: uuid.UUID,
    codigo: str,
    nombre: str,
    domicilio: str,
    tipo_contrato: str,
    retencion_destajo_pct: Porcentaje,
    fondo_garantia_pct: Porcentaje,
    iva_acreditable: bool,
    umbral_alerta_pct: Porcentaje | None,
    creado_en: datetime,
    creado_por_id: uuid.UUID,
) -> None:
    """Inserta la obra en `PLANEACION`. Una violación de `uq_obra_codigo` sale como error del motor."""
    sesion_bd.execute(
        insert(obra).values(
            id=obra_id,
            empresa_id=empresa_id,
            codigo=codigo,
            nombre=nombre,
            domicilio=domicilio,
            tipo_contrato=tipo_contrato,
            retencion_destajo_pct=retencion_destajo_pct.cuantizar().valor,
            fondo_garantia_pct=fondo_garantia_pct.cuantizar().valor,
            iva_acreditable=iva_acreditable,
            umbral_alerta_pct=(
                None if umbral_alerta_pct is None else umbral_alerta_pct.cuantizar().valor
            ),
            estado="PLANEACION",
            creado_en=creado_en,
            creado_por_id=creado_por_id,
        )
    )


_COLUMNAS_OBRA = (
    obra.c.id,
    obra.c.codigo,
    obra.c.nombre,
    obra.c.domicilio,
    obra.c.tipo_contrato,
    obra.c.retencion_destajo_pct,
    obra.c.fondo_garantia_pct,
    obra.c.iva_acreditable,
    obra.c.umbral_alerta_pct,
    obra.c.estado,
    linea_base.c.id.label("linea_base_vigente_id"),
    obra.c.creado_en,
    obra.c.actualizado_en,
)

# `obra` unida a su línea base `CONGELADA`: sin fila de línea base, la vigente sale `NULL`.
_OBRA_CON_VIGENTE = obra.outerjoin(
    linea_base,
    and_(linea_base.c.obra_id == obra.c.id, linea_base.c.estado == "CONGELADA"),
)


def _fila_obra(fila: Row[*tuple[Any, ...]]) -> FilaObraCompleta:
    umbral = fila.umbral_alerta_pct
    return FilaObraCompleta(
        id=fila.id,
        codigo=fila.codigo,
        nombre=fila.nombre,
        domicilio=fila.domicilio,
        tipo_contrato=fila.tipo_contrato,
        retencion_destajo_pct=Porcentaje(fila.retencion_destajo_pct),
        fondo_garantia_pct=Porcentaje(fila.fondo_garantia_pct),
        iva_acreditable=fila.iva_acreditable,
        umbral_alerta_pct=None if umbral is None else Porcentaje(umbral),
        estado=fila.estado,
        linea_base_vigente_id=fila.linea_base_vigente_id,
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
    )


def leer_obra_completa(sesion_bd: Session, obra_id: uuid.UUID) -> FilaObraCompleta | None:
    """La obra por su id, con su línea base vigente. Sin bloqueo: es una lectura."""
    sentencia = select(*_COLUMNAS_OBRA).select_from(_OBRA_CON_VIGENTE).where(obra.c.id == obra_id)
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _fila_obra(fila)


def leer_obra_por_codigo(sesion_bd: Session, codigo: str) -> FilaObraCompleta | None:
    """La obra por su código, con su línea base vigente. Sin bloqueo: es una lectura."""
    sentencia = (
        select(*_COLUMNAS_OBRA).select_from(_OBRA_CON_VIGENTE).where(obra.c.codigo == codigo)
    )
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _fila_obra(fila)


def listar_obras(
    sesion_bd: Session,
    *,
    estados: frozenset[str] | None,
    desplazamiento: int,
    limite: int,
) -> PaginaObras:
    """Una ventana de obras ordenadas por código y luego por id, con el total que cumple el filtro.

    Si el desplazamiento alcanza el total, devuelve la página vacía sin pedir filas (D20): así una
    página inalcanzable nunca llega al motor con un `OFFSET` enorme.
    """
    condicion = obra.c.estado.in_(estados) if estados is not None else None

    cuenta = select(func.count()).select_from(obra)
    if condicion is not None:
        cuenta = cuenta.where(condicion)
    total = int(sesion_bd.execute(cuenta).scalar_one())
    if desplazamiento >= total:
        return PaginaObras(filas=[], total=total)

    filas = select(*_COLUMNAS_OBRA).select_from(_OBRA_CON_VIGENTE)
    if condicion is not None:
        filas = filas.where(condicion)
    filas = filas.order_by(obra.c.codigo, obra.c.id).offset(desplazamiento).limit(limite)
    return PaginaObras(
        filas=[_fila_obra(fila) for fila in sesion_bd.execute(filas)],
        total=total,
    )
