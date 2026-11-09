"""Adaptador de explosión sobre valores ya cuantizados (TKT-017a2, fila A3).

Arma `ConceptoAExplotar` desde `FilaExplotable` y delega en `calcular_explosion`; si no
rechaza, devuelve `.cuantizar()`. Sin efectos secundarios.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, Ruta
from cimenta.presupuesto.dominio.explosion import (
    ConceptoAExplotar,
    ExplosionCalculada,
    RechazoExplosion,
    calcular_explosion,
)
from tipos_base import Cantidad, Dinero, Rendimiento


class ExplosionFueraDeEscala(Exception):
    """Un total de la explosión no cabe en la escala de su columna al cuantizar (PA-23)."""


@dataclass(frozen=True, slots=True)
class InsumoDeApu:
    codigo: str
    tipo: TipoInsumo
    unidad: str
    costo_unitario: Dinero
    rendimiento: Rendimiento


@dataclass(frozen=True, slots=True)
class CargoDeApu:
    tipo: TipoCargo
    importe: Dinero


@dataclass(frozen=True, slots=True)
class FilaExplotable:
    codigo_concepto: str
    tipo_partida_id: UUID
    cantidad: Cantidad | None
    precio_unitario: Dinero | None
    insumos: tuple[InsumoDeApu, ...] | None
    cargos: tuple[CargoDeApu, ...]


def explotar_filas(
    filas: Sequence[FilaExplotable],
) -> ExplosionCalculada | RechazoExplosion:
    """Validación de explosión sobre filas ya cuantizadas (RN-24, PA-01, PA-03, PA-23)."""
    conceptos: list[ConceptoAExplotar] = []
    vacia = Ruta(raiz=None, nivel=None, area=None, partida=None)
    for indice, fila in enumerate(filas):
        n = indice + 1
        concepto = ConceptoLeido(
            fila=n,
            codigo=fila.codigo_concepto,
            descripcion=None,
            unidad=None,
            cantidad=fila.cantidad,
            precio_unitario=fila.precio_unitario,
            importe=None,
            ruta=vacia,
        )
        if fila.insumos is None:
            analisis = None
        else:
            insumos_leidos = tuple(
                InsumoLeido(
                    fila=0,
                    tipo=i.tipo,
                    descripcion=i.codigo,
                    clave=i.codigo,
                    unidad=i.unidad,
                    costo_unitario=i.costo_unitario,
                    rendimiento=i.rendimiento,
                    cargo=None,
                )
                for i in fila.insumos
            )
            cargos_leidos = tuple(
                CargoLeido(
                    fila=0,
                    rotulo=c.tipo.value,
                    tipo=c.tipo,
                    porcentaje=None,
                    base=None,
                    importe=c.importe,
                )
                for c in fila.cargos
            )
            analisis = AnalisisLeido(
                hoja=fila.codigo_concepto,
                cabecera=CabeceraLeida(
                    fila_codigo=None,
                    codigo=None,
                    unidad=None,
                    fecha=None,
                    analista=None,
                    precio_unitario=None,
                ),
                insumos=insumos_leidos,
                cargos=cargos_leidos,
                fila_precio_unitario=0,
                precio_unitario=fila.precio_unitario,
                totales=TotalesAnalisis(
                    material=None,
                    mano_obra=None,
                    costo_directo=None,
                    cargos=None,
                    precio_unitario=None,
                ),
                hallazgos=(),
            )
        conceptos.append(
            ConceptoAExplotar(
                concepto=concepto,
                tipo_partida_id=fila.tipo_partida_id,
                analisis=analisis,
            )
        )

    resultado = calcular_explosion(conceptos)
    if isinstance(resultado, RechazoExplosion):
        return resultado
    try:
        return resultado.cuantizar()
    except ValueError as error:
        raise ExplosionFueraDeEscala from error


__all__ = [
    "CargoDeApu",
    "ExplosionFueraDeEscala",
    "FilaExplotable",
    "InsumoDeApu",
    "explotar_filas",
]
