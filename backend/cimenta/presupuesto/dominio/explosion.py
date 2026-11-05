"""Cálculo de la explosión de insumos por tipo de partida (TKT-016).

Implementa RN-24 (rendimiento congelado), PA-01 (agregado en toda la obra), PA-03 (importe
sugerido) y PA-23 (redondeo solo en cuantizar()). Sin efectos secundarios; TKT-017 persiste
explosion.cuantizar().
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    TipoCargo,
    TipoInsumo,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido
from tipos_base import (
    Cantidad,
    Dinero,
    Rendimiento,
    cociente_precio_unitario,
    cociente_rendimiento,
    sumar,
)


class MotivoRechazoExplosion(StrEnum):
    SIN_TIPO_PARTIDA = "SIN_TIPO_PARTIDA"
    SIN_ANALISIS = "SIN_ANALISIS"
    CANTIDAD_AUSENTE = "CANTIDAD_AUSENTE"
    CANTIDAD_NO_POSITIVA = "CANTIDAD_NO_POSITIVA"
    SIN_PRECIO_UNITARIO = "SIN_PRECIO_UNITARIO"
    CARGO_AUSENTE = "CARGO_AUSENTE"
    CARGO_SIN_IMPORTE = "CARGO_SIN_IMPORTE"
    INSUMO_SIN_COSTO = "INSUMO_SIN_COSTO"
    RENDIMIENTO_AUSENTE = "RENDIMIENTO_AUSENTE"
    RENDIMIENTO_NO_POSITIVO = "RENDIMIENTO_NO_POSITIVO"
    UNIDAD_EN_CONFLICTO = "UNIDAD_EN_CONFLICTO"
    SUGERIDO_NEGATIVO = "SUGERIDO_NEGATIVO"


@dataclass(frozen=True, slots=True)
class ConceptoAExplotar:
    concepto: ConceptoLeido
    tipo_partida_id: UUID | None
    analisis: AnalisisLeido | None


@dataclass(frozen=True, slots=True)
class RenglonExplosion:
    tipo_partida_id: UUID
    clave_insumo: str
    cantidad_conceptos: Cantidad
    cantidad_presupuestada: Cantidad
    rendimiento_congelado: Rendimiento
    costo_unitario: Dinero
    importe: Dinero

    def cuantizar(self) -> RenglonExplosion:
        return RenglonExplosion(
            tipo_partida_id=self.tipo_partida_id,
            clave_insumo=self.clave_insumo,
            cantidad_conceptos=self.cantidad_conceptos.cuantizar(),
            cantidad_presupuestada=self.cantidad_presupuestada.cuantizar(),
            rendimiento_congelado=self.rendimiento_congelado.cuantizar(),
            costo_unitario=self.costo_unitario.cuantizar(),
            importe=self.importe.cuantizar(),
        )


@dataclass(frozen=True, slots=True)
class ImportesTipoPartida:
    tipo_partida_id: UUID
    importe_venta: Dinero
    importe_sugerido: Dinero


@dataclass(frozen=True, slots=True)
class ExplosionCalculada:
    renglones: tuple[RenglonExplosion, ...]
    importes: tuple[ImportesTipoPartida, ...]

    def cuantizar(self) -> ExplosionCalculada:
        return ExplosionCalculada(
            renglones=tuple(r.cuantizar() for r in self.renglones),
            importes=tuple(
                ImportesTipoPartida(
                    tipo_partida_id=i.tipo_partida_id,
                    importe_venta=i.importe_venta.cuantizar(),
                    importe_sugerido=i.importe_sugerido.cuantizar(),
                )
                for i in self.importes
            ),
        )


@dataclass(frozen=True, slots=True)
class CausaRechazoExplosion:
    motivo: MotivoRechazoExplosion
    codigo_concepto: str | None
    fila: int | None
    clave_insumo: str | None = None
    cargo: TipoCargo | None = None
    tipo_partida_id: UUID | None = None
    unidades: tuple[str, ...] = ()
    importe_sugerido: Dinero | None = None


@dataclass(frozen=True, slots=True)
class RechazoExplosion:
    causas: tuple[CausaRechazoExplosion, ...]


@dataclass
class _AcumuladorRenglon:
    cantidad_presupuestada: Cantidad
    importe: Dinero
    indices_concepto: set[int]


def calcular_explosion(
    conceptos: Sequence[ConceptoAExplotar],
) -> ExplosionCalculada | RechazoExplosion:
    """Implementa RN-24 (rendimiento congelado) y PA-01 (agregado por tipo de partida en
    toda la obra); importe sugerido de PA-03 y redondeo de PA-23. Sin efectos secundarios."""
    if not conceptos:
        return ExplosionCalculada((), ())

    causas = _causas_de_concepto(conceptos)
    causas += _causas_de_unidad(conceptos)
    causas += _causas_de_sugerido(conceptos, causas)

    if causas:
        return RechazoExplosion(causas=causas)

    renglones = _agregar(conceptos)
    importes = _importes(conceptos)
    return ExplosionCalculada(renglones=renglones, importes=importes)


def _causa(
    motivo: MotivoRechazoExplosion,
    concepto: ConceptoLeido,
    *,
    clave_insumo: str | None = None,
    cargo: TipoCargo | None = None,
    tipo_partida_id: UUID | None = None,
    unidades: tuple[str, ...] = (),
    importe_sugerido: Dinero | None = None,
) -> CausaRechazoExplosion:
    return CausaRechazoExplosion(
        motivo=motivo,
        codigo_concepto=concepto.codigo,
        fila=concepto.fila,
        clave_insumo=clave_insumo,
        cargo=cargo,
        tipo_partida_id=tipo_partida_id,
        unidades=unidades,
        importe_sugerido=importe_sugerido,
    )


def _causas_cargo(
    concepto: ConceptoLeido,
    analisis: AnalisisLeido,
    tipo: TipoCargo,
) -> tuple[CausaRechazoExplosion, ...]:
    cargos = [c for c in analisis.cargos if c.tipo == tipo]
    if not cargos:
        return (_causa(MotivoRechazoExplosion.CARGO_AUSENTE, concepto, cargo=tipo),)
    causas: list[CausaRechazoExplosion] = []
    for cargo in cargos:
        if cargo.importe is None:
            causas.append(_causa(MotivoRechazoExplosion.CARGO_SIN_IMPORTE, concepto, cargo=tipo))
    return tuple(causas)


def _causas_de_concepto(
    conceptos: Sequence[ConceptoAExplotar],
) -> tuple[CausaRechazoExplosion, ...]:
    causas: list[CausaRechazoExplosion] = []
    for item in conceptos:
        concepto = item.concepto
        if item.tipo_partida_id is None:
            causas.append(_causa(MotivoRechazoExplosion.SIN_TIPO_PARTIDA, concepto))
        if concepto.cantidad is None:
            causas.append(_causa(MotivoRechazoExplosion.CANTIDAD_AUSENTE, concepto))
        elif concepto.cantidad.valor <= 0:
            causas.append(_causa(MotivoRechazoExplosion.CANTIDAD_NO_POSITIVA, concepto))

        analisis = item.analisis
        if analisis is None:
            causas.append(_causa(MotivoRechazoExplosion.SIN_ANALISIS, concepto))
            continue

        if analisis.precio_unitario is None:
            causas.append(_causa(MotivoRechazoExplosion.SIN_PRECIO_UNITARIO, concepto))

        causas.extend(_causas_cargo(concepto, analisis, TipoCargo.UTILIDAD))
        causas.extend(_causas_cargo(concepto, analisis, TipoCargo.INDIRECTOS))

        for insumo in analisis.insumos:
            if insumo.tipo != TipoInsumo.MATERIAL:
                continue
            if insumo.costo_unitario is None:
                causas.append(
                    _causa(
                        MotivoRechazoExplosion.INSUMO_SIN_COSTO,
                        concepto,
                        clave_insumo=insumo.clave,
                    )
                )
            if insumo.rendimiento is None:
                causas.append(
                    _causa(
                        MotivoRechazoExplosion.RENDIMIENTO_AUSENTE,
                        concepto,
                        clave_insumo=insumo.clave,
                    )
                )
            elif insumo.rendimiento.valor <= 0:
                causas.append(
                    _causa(
                        MotivoRechazoExplosion.RENDIMIENTO_NO_POSITIVO,
                        concepto,
                        clave_insumo=insumo.clave,
                    )
                )
    return tuple(causas)


def _causas_de_unidad(conceptos: Sequence[ConceptoAExplotar]) -> tuple[CausaRechazoExplosion, ...]:
    unidades_por_clave: dict[str, set[str]] = {}
    ocurrencias: list[tuple[ConceptoLeido, str, str]] = []

    for item in conceptos:
        if item.analisis is None:
            continue
        for insumo in item.analisis.insumos:
            if insumo.tipo != TipoInsumo.MATERIAL or insumo.unidad is None:
                continue
            clave = insumo.clave
            unidad = insumo.unidad
            unidades_por_clave.setdefault(clave, set()).add(unidad)
            ocurrencias.append((item.concepto, clave, unidad))

    conflictivas = {k for k, u in unidades_por_clave.items() if len(u) > 1}
    if not conflictivas:
        return ()

    causas: list[CausaRechazoExplosion] = []
    for concepto, clave, _ in ocurrencias:
        if clave not in conflictivas:
            continue
        unidades = tuple(sorted(unidades_por_clave[clave]))
        causas.append(
            _causa(
                MotivoRechazoExplosion.UNIDAD_EN_CONFLICTO,
                concepto,
                clave_insumo=clave,
                unidades=unidades,
            )
        )
    return tuple(causas)


def _tipos_con_causas_de_importe(
    causas: Sequence[CausaRechazoExplosion],
    conceptos: Sequence[ConceptoAExplotar],
) -> set[UUID]:
    tipo_por_fila: dict[int, UUID] = {
        item.concepto.fila: item.tipo_partida_id
        for item in conceptos
        if item.tipo_partida_id is not None
    }
    motivos_importe = {
        MotivoRechazoExplosion.CANTIDAD_AUSENTE,
        MotivoRechazoExplosion.CANTIDAD_NO_POSITIVA,
        MotivoRechazoExplosion.SIN_ANALISIS,
        MotivoRechazoExplosion.SIN_PRECIO_UNITARIO,
        MotivoRechazoExplosion.CARGO_AUSENTE,
        MotivoRechazoExplosion.CARGO_SIN_IMPORTE,
    }
    tipos_excluidos: set[UUID] = set()
    for causa in causas:
        if causa.motivo not in motivos_importe or causa.fila is None:
            continue
        tipo = tipo_por_fila.get(causa.fila)
        if tipo is not None:
            tipos_excluidos.add(tipo)
    return tipos_excluidos


def _suma_cargos(analisis: AnalisisLeido, tipo: TipoCargo) -> Dinero:
    importes = [c.importe for c in analisis.cargos if c.tipo == tipo and c.importe is not None]
    return sumar(importes, Dinero)


def _importe_sugerido_concepto(concepto: ConceptoAExplotar) -> Dinero:
    assert concepto.analisis is not None and concepto.concepto.cantidad is not None
    assert concepto.analisis.precio_unitario is not None
    pu = concepto.analisis.precio_unitario
    utilidad = _suma_cargos(concepto.analisis, TipoCargo.UTILIDAD)
    indirectos = _suma_cargos(concepto.analisis, TipoCargo.INDIRECTOS)
    neto = pu - utilidad - indirectos
    return concepto.concepto.cantidad * neto


def _causas_de_sugerido(
    conceptos: Sequence[ConceptoAExplotar],
    causas_previas: Sequence[CausaRechazoExplosion],
) -> tuple[CausaRechazoExplosion, ...]:
    tipos_excluidos = _tipos_con_causas_de_importe(causas_previas, conceptos)
    por_tipo: dict[UUID, list[ConceptoAExplotar]] = {}
    for item in conceptos:
        if item.tipo_partida_id is None:
            continue
        por_tipo.setdefault(item.tipo_partida_id, []).append(item)

    causas: list[CausaRechazoExplosion] = []
    for tipo_id in sorted(por_tipo, key=str):
        if tipo_id in tipos_excluidos:
            continue
        items = por_tipo[tipo_id]
        sugerido = sumar(
            (_importe_sugerido_concepto(i) for i in items),
            Dinero,
        )
        if sugerido.valor < 0:
            causas.append(
                CausaRechazoExplosion(
                    motivo=MotivoRechazoExplosion.SUGERIDO_NEGATIVO,
                    codigo_concepto=None,
                    fila=None,
                    tipo_partida_id=tipo_id,
                    importe_sugerido=sugerido,
                )
            )
    return tuple(causas)


def _agregar(conceptos: Sequence[ConceptoAExplotar]) -> tuple[RenglonExplosion, ...]:
    acumuladores: dict[tuple[UUID, str], _AcumuladorRenglon] = {}
    cantidades_por_indice: dict[int, Cantidad] = {}

    for indice, item in enumerate(conceptos):
        assert item.tipo_partida_id is not None
        assert item.analisis is not None
        assert item.concepto.cantidad is not None
        cantidades_por_indice[indice] = item.concepto.cantidad

        for insumo in item.analisis.insumos:
            if insumo.tipo != TipoInsumo.MATERIAL:
                continue
            assert insumo.rendimiento is not None and insumo.costo_unitario is not None
            grupo = (item.tipo_partida_id, insumo.clave)
            q_r = item.concepto.cantidad * insumo.rendimiento
            importe_parcial = q_r * insumo.costo_unitario

            if grupo not in acumuladores:
                acumuladores[grupo] = _AcumuladorRenglon(
                    cantidad_presupuestada=Cantidad("0"),
                    importe=Dinero("0"),
                    indices_concepto=set(),
                )
            acc = acumuladores[grupo]
            acc.cantidad_presupuestada = acc.cantidad_presupuestada + q_r
            acc.importe = acc.importe + importe_parcial
            acc.indices_concepto.add(indice)

    renglones: list[RenglonExplosion] = []
    for (tipo_id, clave), acc in sorted(
        acumuladores.items(), key=lambda x: (str(x[0][0]), x[0][1])
    ):
        cantidad_conceptos = sumar(
            (cantidades_por_indice[i] for i in sorted(acc.indices_concepto)),
            Cantidad,
        )
        rendimiento = cociente_rendimiento(acc.cantidad_presupuestada, cantidad_conceptos)
        costo = cociente_precio_unitario(acc.importe, acc.cantidad_presupuestada)
        renglones.append(
            RenglonExplosion(
                tipo_partida_id=tipo_id,
                clave_insumo=clave,
                cantidad_conceptos=cantidad_conceptos,
                cantidad_presupuestada=acc.cantidad_presupuestada,
                rendimiento_congelado=rendimiento,
                costo_unitario=costo,
                importe=acc.importe,
            )
        )
    return tuple(renglones)


def _importes(conceptos: Sequence[ConceptoAExplotar]) -> tuple[ImportesTipoPartida, ...]:
    por_tipo: dict[UUID, list[ConceptoAExplotar]] = {}
    for item in conceptos:
        if item.tipo_partida_id is None:
            continue
        por_tipo.setdefault(item.tipo_partida_id, []).append(item)

    resultado: list[ImportesTipoPartida] = []
    for tipo_id in sorted(por_tipo, key=str):
        items = por_tipo[tipo_id]
        ventas = []
        sugeridos = []
        for item in items:
            assert item.analisis is not None and item.concepto.cantidad is not None
            assert item.analisis.precio_unitario is not None
            ventas.append(item.concepto.cantidad * item.analisis.precio_unitario)
            sugeridos.append(_importe_sugerido_concepto(item))
        resultado.append(
            ImportesTipoPartida(
                tipo_partida_id=tipo_id,
                importe_venta=sumar(ventas, Dinero),
                importe_sugerido=sumar(sugeridos, Dinero),
            )
        )
    return tuple(resultado)


__all__ = [
    "CausaRechazoExplosion",
    "ConceptoAExplotar",
    "ExplosionCalculada",
    "ImportesTipoPartida",
    "MotivoRechazoExplosion",
    "RechazoExplosion",
    "RenglonExplosion",
    "calcular_explosion",
]
