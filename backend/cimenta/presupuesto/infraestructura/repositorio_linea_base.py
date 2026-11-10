"""Repositorio de la jerarquía y la línea base de una obra (TKT-017, entrega a3, fila A6a).

Cada función recibe la sesión del caso de uso y no confirma la transacción. Las inserciones usan
`insert(tabla)` con una lista de diccionarios. Las cifras llegan ya cuantizadas por el dominio y
se pasan como `Decimal`; nada se redondea aquí.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import Uuid, delete, func, insert, literal, select, update
from sqlalchemy.orm import Session

from cimenta.presupuesto.dominio.analisis import TipoCargo, TipoInsumo
from cimenta.presupuesto.dominio.explosion import ExplosionCalculada
from cimenta.presupuesto.dominio.explosion_materializada import (
    CargoDeApu,
    FilaExplotable,
    InsumoDeApu,
)
from cimenta.presupuesto.dominio.importacion import EstadoImportacion
from cimenta.presupuesto.dominio.materializacion import (
    ApuNuevo,
    AreaNueva,
    ConceptoNuevo,
    InsumoNuevo,
    InsumoRegistrado,
    NivelNuevo,
    PartidaConceptoNueva,
    PartidaNueva,
)
from cimenta.presupuesto.infraestructura.tablas import (
    apu,
    apu_cargo,
    apu_insumo,
    area,
    concepto,
    explosion_presupuesto,
    importacion,
    insumo,
    linea_base,
    linea_base_concepto,
    nivel,
    obra,
    partida,
    partida_concepto,
    presupuesto_control,
    tipo_partida,
)
from tipos_base import Cantidad, Dinero, Rendimiento


class FilaObra(NamedTuple):
    id: uuid.UUID
    codigo: str
    nombre: str
    estado: str


class FilaLineaBase(NamedTuple):
    id: uuid.UUID
    version: int
    estado: str


class FilaLineaBaseLeida(NamedTuple):
    id: uuid.UUID
    obra_id: uuid.UUID
    version: int
    estado: str
    importe_venta: Dinero


def bloquear_obra(sesion_bd: Session, obra_id: uuid.UUID) -> FilaObra | None:
    """Bloqueo pesimista de la fila de la obra: serializa confirmar y congelar (ADR-004)."""
    return _leer_obra(sesion_bd, obra_id, bloquear=True)


def leer_obra(sesion_bd: Session, obra_id: uuid.UUID) -> FilaObra | None:
    """Lectura de la obra sin bloqueo, para las transacciones cortas de solo lectura."""
    return _leer_obra(sesion_bd, obra_id, bloquear=False)


def _leer_obra(sesion_bd: Session, obra_id: uuid.UUID, *, bloquear: bool) -> FilaObra | None:
    sentencia = select(obra.c.id, obra.c.codigo, obra.c.nombre, obra.c.estado).where(
        obra.c.id == obra_id
    )
    if bloquear:
        sentencia = sentencia.with_for_update()
    fila = sesion_bd.execute(sentencia).one_or_none()
    if fila is None:
        return None
    return FilaObra(id=fila.id, codigo=fila.codigo, nombre=fila.nombre, estado=fila.estado)


def obra_de_importacion(sesion_bd: Session, importacion_id: uuid.UUID) -> uuid.UUID | None:
    return sesion_bd.scalar(select(importacion.c.obra_id).where(importacion.c.id == importacion_id))


def lineas_base_de_obra(sesion_bd: Session, obra_id: uuid.UUID) -> list[FilaLineaBase]:
    sentencia = (
        select(linea_base.c.id, linea_base.c.version, linea_base.c.estado)
        .where(linea_base.c.obra_id == obra_id)
        .order_by(linea_base.c.version.desc())
    )
    return [
        FilaLineaBase(id=f.id, version=f.version, estado=f.estado)
        for f in sesion_bd.execute(sentencia)
    ]


def tipos_partida(sesion_bd: Session) -> frozenset[uuid.UUID]:
    return frozenset(sesion_bd.scalars(select(tipo_partida.c.id)))


def insumos_registrados(sesion_bd: Session) -> list[InsumoRegistrado]:
    """Todos los insumos; `ORDER BY codigo` fija cuál gana cuando dos comparten descripción."""
    sentencia = select(
        insumo.c.id, insumo.c.codigo, insumo.c.descripcion, insumo.c.unidad, insumo.c.tipo
    ).order_by(insumo.c.codigo)
    return [
        InsumoRegistrado(
            id=f.id,
            codigo=f.codigo,
            descripcion=f.descripcion,
            unidad=f.unidad,
            tipo=TipoInsumo(f.tipo),
        )
        for f in sesion_bd.execute(sentencia)
    ]


def insertar_insumos(sesion_bd: Session, insumos: Sequence[InsumoNuevo]) -> None:
    if not insumos:
        return
    sesion_bd.execute(
        insert(insumo),
        [
            {
                "id": i.id,
                "codigo": i.codigo,
                "descripcion": i.descripcion,
                "tipo": i.tipo.value,
                "unidad": i.unidad,
                "activo": True,
                "creado_en_importacion": i.creado_en_importacion,
            }
            for i in insumos
        ],
    )


def insertar_niveles(sesion_bd: Session, obra_id: uuid.UUID, niveles: Sequence[NivelNuevo]) -> None:
    if not niveles:
        return
    sesion_bd.execute(
        insert(nivel),
        [{"id": n.id, "obra_id": obra_id, "nombre": n.nombre, "orden": n.orden} for n in niveles],
    )


def insertar_areas(sesion_bd: Session, areas: Sequence[AreaNueva]) -> None:
    if not areas:
        return
    sesion_bd.execute(
        insert(area),
        [{"id": a.id, "nivel_id": a.nivel_id, "nombre": a.nombre} for a in areas],
    )


def insertar_partidas(sesion_bd: Session, partidas: Sequence[PartidaNueva]) -> None:
    if not partidas:
        return
    sesion_bd.execute(
        insert(partida),
        [
            {
                "id": p.id,
                "area_id": p.area_id,
                "tipo_partida_id": p.tipo_partida_id,
                "orden": p.orden,
            }
            for p in partidas
        ],
    )


def insertar_conceptos(
    sesion_bd: Session, obra_id: uuid.UUID, conceptos: Sequence[ConceptoNuevo]
) -> None:
    if not conceptos:
        return
    sesion_bd.execute(
        insert(concepto),
        [
            {
                "id": c.id,
                "obra_id": obra_id,
                "codigo": c.codigo,
                "descripcion": c.descripcion,
                "unidad": c.unidad,
            }
            for c in conceptos
        ],
    )


def insertar_partidas_concepto(
    sesion_bd: Session, apariciones: Sequence[PartidaConceptoNueva]
) -> None:
    if not apariciones:
        return
    sesion_bd.execute(
        insert(partida_concepto),
        [
            {
                "id": a.id,
                "concepto_id": a.concepto_id,
                "partida_id": a.partida_id,
                "cantidad": a.cantidad.valor,
                "precio_unitario": a.precio_unitario.valor,
                "importe": a.importe.valor,
            }
            for a in apariciones
        ],
    )


def insertar_apus(sesion_bd: Session, apus: Sequence[ApuNuevo]) -> None:
    """Los análisis con sus insumos y sus cargos; el padre se inserta antes que los hijos."""
    if not apus:
        return
    sesion_bd.execute(
        insert(apu),
        [
            {
                "id": a.id,
                "concepto_id": a.concepto_id,
                "fecha_analisis": _fecha(a.fecha_analisis),
                "analista": a.analista,
                "costo_material": a.costo_material.valor,
                "costo_mano_obra": a.costo_mano_obra.valor,
                "costo_directo": a.costo_directo.valor,
                "total_cargos": a.total_cargos.valor,
                "total_indirectos": a.total_indirectos.valor,
                "precio_unitario": a.precio_unitario.valor,
            }
            for a in apus
        ],
    )
    insumos_filas = [
        {
            "id": uuid.uuid4(),
            "apu_id": a.id,
            "insumo_id": i.insumo_id,
            "costo_unitario": i.costo_unitario.valor,
            "rendimiento": i.rendimiento.valor,
            "cargo": i.cargo.valor,
        }
        for a in apus
        for i in a.insumos
    ]
    if insumos_filas:
        sesion_bd.execute(insert(apu_insumo), insumos_filas)
    cargos_filas = [
        {
            "id": uuid.uuid4(),
            "apu_id": a.id,
            "tipo": c.tipo.value,
            "porcentaje": None if c.porcentaje is None else c.porcentaje.valor,
            "base_calculo": None if c.base_calculo is None else c.base_calculo.valor,
            "importe": c.importe.valor,
        }
        for a in apus
        for c in a.cargos
    ]
    if cargos_filas:
        sesion_bd.execute(insert(apu_cargo), cargos_filas)


def _fecha(texto: str | None) -> date | None:
    return None if texto is None else date.fromisoformat(texto)


def insertar_linea_base(
    sesion_bd: Session,
    *,
    linea_base_id: uuid.UUID,
    obra_id: uuid.UUID,
    version: int,
    importe_venta: Dinero,
    creado_en: datetime,
    creado_por_id: uuid.UUID,
) -> None:
    """La línea base nace `BORRADOR`; solo el congelado la pasa a `CONGELADA`."""
    sesion_bd.execute(
        insert(linea_base).values(
            id=linea_base_id,
            obra_id=obra_id,
            version=version,
            estado="BORRADOR",
            importe_venta=importe_venta.valor,
            creado_en=creado_en,
            creado_por_id=creado_por_id,
        )
    )


def confirmar_importacion(sesion_bd: Session, importacion_id: uuid.UUID) -> None:
    sesion_bd.execute(
        update(importacion)
        .where(importacion.c.id == importacion_id)
        .values(estado=EstadoImportacion.CONFIRMADO.value)
    )


def version_siguiente(sesion_bd: Session, obra_id: uuid.UUID) -> int:
    """`MAX(version) + 1` de la obra; se calcula después de borrar el borrador que se reemplaza."""
    maxima = sesion_bd.scalar(
        select(func.coalesce(func.max(linea_base.c.version), 0)).where(
            linea_base.c.obra_id == obra_id
        )
    )
    return int(maxima or 0) + 1


def borrar_jerarquia(sesion_bd: Session, obra_id: uuid.UUID, linea_base_id: uuid.UUID) -> None:
    """Borra de las hojas a la raíz, siempre por obra (diseño «Orden de borrado del reemplazo»).

    Nunca toca `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `insumo` ni
    `precio_insumo`: un borrador no tiene copias ni control y los insumos sobreviven al reemplazo.
    """
    conceptos_de_obra = select(concepto.c.id).where(concepto.c.obra_id == obra_id)
    apus_de_obra = select(apu.c.id).where(apu.c.concepto_id.in_(conceptos_de_obra))
    niveles_de_obra = select(nivel.c.id).where(nivel.c.obra_id == obra_id)
    areas_de_obra = select(area.c.id).where(area.c.nivel_id.in_(niveles_de_obra))
    sentencias = (
        delete(apu_cargo).where(apu_cargo.c.apu_id.in_(apus_de_obra)),
        delete(apu_insumo).where(apu_insumo.c.apu_id.in_(apus_de_obra)),
        delete(apu).where(apu.c.concepto_id.in_(conceptos_de_obra)),
        delete(partida_concepto).where(partida_concepto.c.concepto_id.in_(conceptos_de_obra)),
        delete(concepto).where(concepto.c.obra_id == obra_id),
        delete(partida).where(partida.c.area_id.in_(areas_de_obra)),
        delete(area).where(area.c.nivel_id.in_(niveles_de_obra)),
        delete(nivel).where(nivel.c.obra_id == obra_id),
        delete(linea_base).where(linea_base.c.id == linea_base_id, linea_base.c.obra_id == obra_id),
    )
    for sentencia in sentencias:
        sesion_bd.execute(sentencia)


def leer_linea_base(sesion_bd: Session, linea_base_id: uuid.UUID) -> FilaLineaBaseLeida | None:
    """Lectura de la línea base sin bloqueo, para conocer su obra antes de bloquearla."""
    return _leer_linea_base(sesion_bd, linea_base_id, bloquear=False)


def bloquear_linea_base(sesion_bd: Session, linea_base_id: uuid.UUID) -> FilaLineaBaseLeida | None:
    """`FOR UPDATE` de la fila; sin fila si un reemplazo la borró mientras se esperaba la obra."""
    return _leer_linea_base(sesion_bd, linea_base_id, bloquear=True)


def _leer_linea_base(
    sesion_bd: Session, linea_base_id: uuid.UUID, *, bloquear: bool
) -> FilaLineaBaseLeida | None:
    sentencia = select(
        linea_base.c.id,
        linea_base.c.obra_id,
        linea_base.c.version,
        linea_base.c.estado,
        linea_base.c.importe_venta,
    ).where(linea_base.c.id == linea_base_id)
    if bloquear:
        sentencia = sentencia.with_for_update()
    fila = sesion_bd.execute(sentencia).one_or_none()
    if fila is None:
        return None
    return FilaLineaBaseLeida(
        id=fila.id,
        obra_id=fila.obra_id,
        version=fila.version,
        estado=fila.estado,
        importe_venta=Dinero(fila.importe_venta),
    )


class FilaLineaBaseCompleta(NamedTuple):
    id: uuid.UUID
    obra_id: uuid.UUID
    version: int
    estado: str
    importe_venta: Dinero
    congelada_en: datetime | None
    congelada_por_id: uuid.UUID | None
    motivo: str | None


class FilaImporteTipo(NamedTuple):
    tipo_partida_id: uuid.UUID
    clave: str
    nombre: str
    importe_venta: Dinero


def leer_linea_base_completa(
    sesion_bd: Session, linea_base_id: uuid.UUID
) -> FilaLineaBaseCompleta | None:
    """La fila de la línea base con los datos de su congelado, sin bloqueo."""
    fila = sesion_bd.execute(
        select(
            linea_base.c.id,
            linea_base.c.obra_id,
            linea_base.c.version,
            linea_base.c.estado,
            linea_base.c.importe_venta,
            linea_base.c.congelada_en,
            linea_base.c.congelada_por_id,
            linea_base.c.motivo,
        ).where(linea_base.c.id == linea_base_id)
    ).one_or_none()
    if fila is None:
        return None
    return FilaLineaBaseCompleta(
        id=fila.id,
        obra_id=fila.obra_id,
        version=fila.version,
        estado=fila.estado,
        importe_venta=Dinero(fila.importe_venta),
        congelada_en=fila.congelada_en,
        congelada_por_id=fila.congelada_por_id,
        motivo=fila.motivo,
    )


def importes_venta_por_tipo(sesion_bd: Session, linea_base_id: uuid.UUID) -> list[FilaImporteTipo]:
    """Las filas de `tipo_partida`, por `id`, con su importe de venta.

    Una línea base que ya no es `BORRADOR` suma sus copias de `linea_base_concepto`: lo congelado no
    se entera de lo que cambie después en `partida_concepto`. Un `BORRADOR` suma los conceptos de la
    obra. Donde no hay conceptos, `0.0000`.
    """
    leida = leer_linea_base(sesion_bd, linea_base_id)
    if leida is None:
        return []
    if leida.estado == "BORRADOR":
        sumas = (
            select(
                partida.c.tipo_partida_id.label("tipo_id"),
                func.sum(partida_concepto.c.importe).label("total"),
            )
            .select_from(partida_concepto)
            .join(concepto, concepto.c.id == partida_concepto.c.concepto_id)
            .join(partida, partida.c.id == partida_concepto.c.partida_id)
            .where(concepto.c.obra_id == leida.obra_id)
            .group_by(partida.c.tipo_partida_id)
        )
    else:
        sumas = (
            select(
                partida.c.tipo_partida_id.label("tipo_id"),
                func.sum(linea_base_concepto.c.importe).label("total"),
            )
            .select_from(linea_base_concepto)
            .join(
                partida_concepto, partida_concepto.c.id == linea_base_concepto.c.partida_concepto_id
            )
            .join(partida, partida.c.id == partida_concepto.c.partida_id)
            .where(linea_base_concepto.c.linea_base_id == linea_base_id)
            .group_by(partida.c.tipo_partida_id)
        )
    totales = {f.tipo_id: f.total for f in sesion_bd.execute(sumas)}
    tipos = sesion_bd.execute(
        select(tipo_partida.c.id, tipo_partida.c.clave, tipo_partida.c.nombre).order_by(
            tipo_partida.c.id
        )
    )
    return [
        FilaImporteTipo(
            tipo_partida_id=t.id,
            clave=t.clave,
            nombre=t.nombre,
            importe_venta=Dinero(totales.get(t.id, Decimal("0.0000"))).cuantizar(),
        )
        for t in tipos
    ]


def filas_explotables(sesion_bd: Session, obra_id: uuid.UUID) -> list[FilaExplotable]:
    """Una fila por aparición de concepto de la obra, lo que consume `explotar_filas` (RN-24).

    Orden: `nivel.orden`, `area.id`, `partida.orden`, `partida.id`, `concepto.codigo`. Solo los insumos de tipo
    `MATERIAL` entran a la explosión, igual que al confirmar. Sin análisis, `insumos` es `None`.
    """
    apariciones = sesion_bd.execute(
        select(
            concepto.c.codigo,
            partida.c.tipo_partida_id,
            partida_concepto.c.cantidad,
            partida_concepto.c.precio_unitario,
            apu.c.id.label("apu_id"),
        )
        .select_from(partida_concepto)
        .join(concepto, concepto.c.id == partida_concepto.c.concepto_id)
        .join(partida, partida.c.id == partida_concepto.c.partida_id)
        .join(area, area.c.id == partida.c.area_id)
        .join(nivel, nivel.c.id == area.c.nivel_id)
        .outerjoin(apu, apu.c.concepto_id == concepto.c.id)
        .where(concepto.c.obra_id == obra_id)
        .order_by(nivel.c.orden, area.c.id, partida.c.orden, partida.c.id, concepto.c.codigo)
    ).all()
    apus = list({a.apu_id for a in apariciones if a.apu_id is not None})
    insumos_por_apu: dict[uuid.UUID, list[InsumoDeApu]] = {}
    for fila in sesion_bd.execute(
        select(
            apu_insumo.c.apu_id,
            insumo.c.codigo,
            insumo.c.tipo,
            insumo.c.unidad,
            apu_insumo.c.costo_unitario,
            apu_insumo.c.rendimiento,
        )
        .join(insumo, insumo.c.id == apu_insumo.c.insumo_id)
        .where(apu_insumo.c.apu_id.in_(apus), insumo.c.tipo == TipoInsumo.MATERIAL.value)
        .order_by(insumo.c.codigo, apu_insumo.c.id)
    ):
        insumos_por_apu.setdefault(fila.apu_id, []).append(
            InsumoDeApu(
                codigo=fila.codigo,
                tipo=TipoInsumo(fila.tipo),
                unidad=fila.unidad,
                costo_unitario=Dinero(fila.costo_unitario),
                rendimiento=Rendimiento(fila.rendimiento),
            )
        )
    cargos_por_apu: dict[uuid.UUID, list[CargoDeApu]] = {}
    for cargo in sesion_bd.execute(
        select(apu_cargo.c.apu_id, apu_cargo.c.tipo, apu_cargo.c.importe)
        .where(apu_cargo.c.apu_id.in_(apus))
        .order_by(apu_cargo.c.id)
    ):
        cargos_por_apu.setdefault(cargo.apu_id, []).append(
            CargoDeApu(tipo=TipoCargo(cargo.tipo), importe=Dinero(cargo.importe))
        )
    return [
        FilaExplotable(
            codigo_concepto=a.codigo,
            tipo_partida_id=a.tipo_partida_id,
            cantidad=Cantidad(a.cantidad),
            precio_unitario=Dinero(a.precio_unitario),
            insumos=None if a.apu_id is None else tuple(insumos_por_apu.get(a.apu_id, ())),
            cargos=() if a.apu_id is None else tuple(cargos_por_apu.get(a.apu_id, ())),
        )
        for a in apariciones
    ]


def copiar_conceptos(sesion_bd: Session, linea_base_id: uuid.UUID, obra_id: uuid.UUID) -> None:
    """Copia cada aparición de concepto de la obra a `linea_base_concepto` (invariante 14)."""
    origen = (
        select(
            func.gen_random_uuid(),
            literal(linea_base_id, Uuid),
            partida_concepto.c.id,
            concepto.c.codigo,
            partida_concepto.c.cantidad,
            partida_concepto.c.precio_unitario,
            partida_concepto.c.importe,
        )
        .select_from(partida_concepto)
        .join(concepto, concepto.c.id == partida_concepto.c.concepto_id)
        .where(concepto.c.obra_id == obra_id)
    )
    sesion_bd.execute(
        insert(linea_base_concepto).from_select(
            [
                "id",
                "linea_base_id",
                "partida_concepto_id",
                "codigo",
                "cantidad",
                "precio_unitario",
                "importe",
            ],
            origen,
        )
    )


def insertar_explosion(
    sesion_bd: Session, linea_base_id: uuid.UUID, explosion: ExplosionCalculada
) -> None:
    """Guarda los renglones tal como los devolvió `explotar_filas`: lo validado es lo congelado."""
    if not explosion.renglones:
        return
    claves = {r.clave_insumo for r in explosion.renglones}
    insumo_por_codigo = {
        f.codigo: f.id
        for f in sesion_bd.execute(
            select(insumo.c.id, insumo.c.codigo).where(insumo.c.codigo.in_(claves))
        )
    }
    sesion_bd.execute(
        insert(explosion_presupuesto),
        [
            {
                "id": uuid.uuid4(),
                "linea_base_id": linea_base_id,
                "tipo_partida_id": r.tipo_partida_id,
                "insumo_id": insumo_por_codigo[r.clave_insumo],
                "cantidad_presupuestada": r.cantidad_presupuestada.valor,
                "rendimiento_congelado": r.rendimiento_congelado.valor,
                "costo_unitario": r.costo_unitario.valor,
                "importe_venta": r.importe.valor,
            }
            for r in explosion.renglones
        ],
    )


def insertar_controles(
    sesion_bd: Session, linea_base_id: uuid.UUID, explosion: ExplosionCalculada
) -> None:
    """Una fila por tipo de partida: el sugerido de la explosión o `0.0000`, y tope nulo."""
    sugerido = {i.tipo_partida_id: i.importe_sugerido.valor for i in explosion.importes}
    tipos = sesion_bd.scalars(select(tipo_partida.c.id).order_by(tipo_partida.c.id)).all()
    sesion_bd.execute(
        insert(presupuesto_control),
        [
            {
                "id": uuid.uuid4(),
                "linea_base_id": linea_base_id,
                "tipo_partida_id": tipo_id,
                "importe_tope": None,
                "importe_sugerido": sugerido.get(tipo_id, Decimal("0.0000")),
            }
            for tipo_id in tipos
        ],
    )


def congelar(
    sesion_bd: Session,
    linea_base_id: uuid.UUID,
    ahora: datetime,
    usuario_id: uuid.UUID,
    motivo: str,
) -> None:
    """Pasa la línea base de `BORRADOR` a `CONGELADA` con fecha, usuario y motivo (RN-01)."""
    sesion_bd.execute(
        update(linea_base)
        .where(linea_base.c.id == linea_base_id)
        .values(estado="CONGELADA", congelada_en=ahora, congelada_por_id=usuario_id, motivo=motivo)
    )


def activar_obra(
    sesion_bd: Session, obra_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID
) -> None:
    """La obra pasa a `ACTIVA`; fija también quién y cuándo la actualizó."""
    sesion_bd.execute(
        update(obra)
        .where(obra.c.id == obra_id)
        .values(estado="ACTIVA", actualizado_en=ahora, actualizado_por_id=usuario_id)
    )
