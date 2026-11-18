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
from collections.abc import Mapping
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import Row, and_, delete, func, insert, select, text, update
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


# ---------------------------------------------------------------------------- TKT-012b · fila A3


class ConteosHistorialPropio(NamedTuple):
    """Lo que `presupuesto` cuenta de una obra por su cuenta, tabla por tabla (RN-01, HDU-001 esc. 20).

    `lineas_base` cuenta las filas de `linea_base` de cualquier estado; `linea_base_congelada` es
    verdadero solo si alguna está `CONGELADA`. El caso de uso suma `niveles`, `conceptos`,
    `precios_insumo` y `rendimientos_observados` en `filas_propias` al armar el `ConteosHistorial`
    del dominio, y agrega los `movimientos` de las fuentes inyectadas.
    """

    lineas_base: int
    linea_base_congelada: bool
    importaciones: int
    niveles: int
    conceptos: int
    precios_insumo: int
    rendimientos_observados: int


def bloquear_obra_completa(sesion_bd: Session, obra_id: uuid.UUID) -> FilaObraCompleta | None:
    """La obra con su línea base vigente, con `SELECT ... FOR UPDATE` sobre `obra`.

    El bloqueo se limita a `obra` (`of=obra`): PostgreSQL rechaza `FOR UPDATE` sobre el lado nulable
    de un `OUTER JOIN`. Quien inserta una hija de la obra espera a que esta transacción termine.
    """
    sentencia = (
        select(*_COLUMNAS_OBRA)
        .select_from(_OBRA_CON_VIGENTE)
        .where(obra.c.id == obra_id)
        .with_for_update(of=obra)
    )
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _fila_obra(fila)


def _valor_de_columna(valor: object) -> object:
    """Un `Porcentaje` se guarda cuantizado a la escala de su columna; cualquier otro valor, tal cual."""
    return valor.cuantizar().valor if isinstance(valor, Porcentaje) else valor


def actualizar_obra(
    sesion_bd: Session,
    obra_id: uuid.UUID,
    campos: Mapping[str, object],
    ahora: datetime,
    usuario_id: uuid.UUID,
) -> None:
    """Escribe solo las columnas de `campos` y sella quién y cuándo. No confirma."""
    valores = {nombre: _valor_de_columna(valor) for nombre, valor in campos.items()}
    sesion_bd.execute(
        update(obra)
        .where(obra.c.id == obra_id)
        .values(**valores, actualizado_en=ahora, actualizado_por_id=usuario_id)
    )


def cambiar_estado_obra(
    sesion_bd: Session,
    obra_id: uuid.UUID,
    estado: str,
    ahora: datetime,
    usuario_id: uuid.UUID,
) -> None:
    """Escribe el estado y sella quién y cuándo. No valida el origen: lo hizo el dominio."""
    sesion_bd.execute(
        update(obra)
        .where(obra.c.id == obra_id)
        .values(estado=estado, actualizado_en=ahora, actualizado_por_id=usuario_id)
    )


def eliminar_obra(sesion_bd: Session, obra_id: uuid.UUID) -> None:
    """Borra la fila. Con una hija, el motor responde `23001` y el error sale tal cual."""
    sesion_bd.execute(delete(obra).where(obra.c.id == obra_id))


# `precio_insumo` y `rendimiento_observado` no se mapean en `tablas.py`: solo se cuentan aquí.
_CONTEO_HISTORIAL = text(
    """
    SELECT
        (SELECT count(*) FROM linea_base WHERE obra_id = :obra_id) AS lineas_base,
        (SELECT count(*) FROM linea_base
            WHERE obra_id = :obra_id AND estado = 'CONGELADA') AS congeladas,
        (SELECT count(*) FROM importacion WHERE obra_id = :obra_id) AS importaciones,
        (SELECT count(*) FROM nivel WHERE obra_id = :obra_id) AS niveles,
        (SELECT count(*) FROM concepto WHERE obra_id = :obra_id) AS conceptos,
        (SELECT count(*) FROM precio_insumo WHERE obra_id = :obra_id) AS precios_insumo,
        (SELECT count(*) FROM rendimiento_observado
            WHERE obra_id = :obra_id) AS rendimientos_observados
    """
)


def contar_historial_propio(sesion_bd: Session, obra_id: uuid.UUID) -> ConteosHistorialPropio:
    """Cuenta, en un solo `SELECT`, lo que cuelga de la obra en las tablas de `presupuesto`."""
    fila = sesion_bd.execute(_CONTEO_HISTORIAL, {"obra_id": obra_id}).one()
    return ConteosHistorialPropio(
        lineas_base=int(fila.lineas_base),
        linea_base_congelada=int(fila.congeladas) > 0,
        importaciones=int(fila.importaciones),
        niveles=int(fila.niveles),
        conceptos=int(fila.conceptos),
        precios_insumo=int(fila.precios_insumo),
        rendimientos_observados=int(fila.rendimientos_observados),
    )
