"""Objetos de valor del análisis de precios unitarios leído en memoria (TKT-014a).

HDU-001 esc. 5, 6, 7, 9 y 10; invariante 27; regla 1. Sin reglas RN-xx.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cimenta.presupuesto.dominio.catalogo import CatalogoLeido, Hallazgo
from tipos_base import Dinero, Porcentaje, Rendimiento


class TipoInsumo(StrEnum):
    MATERIAL = "MATERIAL"
    MANO_OBRA = "MANO_OBRA"


class TipoCargo(StrEnum):
    HERRAMIENTA_MENOR = "HERRAMIENTA_MENOR"
    ANDAMIAJE = "ANDAMIAJE"
    DESPERDICIO = "DESPERDICIO"
    VIATICOS = "VIATICOS"
    IVA = "IVA"
    INDIRECTOS = "INDIRECTOS"
    UTILIDAD = "UTILIDAD"


@dataclass(frozen=True, slots=True)
class CabeceraLeida:
    fila_codigo: int | None
    codigo: str | None
    unidad: str | None
    fecha: str | None
    analista: str | None
    precio_unitario: Dinero | None


@dataclass(frozen=True, slots=True)
class InsumoLeido:
    fila: int
    tipo: TipoInsumo
    descripcion: str
    clave: str
    unidad: str | None
    costo_unitario: Dinero | None
    rendimiento: Rendimiento | None
    cargo: Dinero | None


@dataclass(frozen=True, slots=True)
class CargoLeido:
    fila: int
    rotulo: str
    tipo: TipoCargo | None
    porcentaje: Porcentaje | None
    base: Dinero | None
    importe: Dinero | None


@dataclass(frozen=True, slots=True)
class TotalesAnalisis:
    material: Dinero | None
    mano_obra: Dinero | None
    costo_directo: Dinero | None
    cargos: Dinero | None
    precio_unitario: Dinero | None


@dataclass(frozen=True, slots=True)
class AnalisisLeido:
    hoja: str
    cabecera: CabeceraLeida
    insumos: tuple[InsumoLeido, ...]
    cargos: tuple[CargoLeido, ...]
    fila_precio_unitario: int
    precio_unitario: Dinero | None
    totales: TotalesAnalisis
    hallazgos: tuple[Hallazgo, ...]


@dataclass(frozen=True, slots=True)
class InsumoPorCrear:
    clave: str
    descripcion: str
    unidad: str
    tipo: TipoInsumo
    creado_en_importacion: bool = True


@dataclass(frozen=True, slots=True)
class AsociacionLeida:
    hoja: str
    codigo: str
    filas_catalogo: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AnalisisDelLibro:
    catalogo: CatalogoLeido
    analisis: tuple[AnalisisLeido, ...]
    asociaciones: tuple[AsociacionLeida, ...]
    codigos_sin_analisis: tuple[str, ...]
    insumos_por_crear: tuple[InsumoPorCrear, ...]
    hallazgos: tuple[Hallazgo, ...]


__all__ = [
    "AnalisisDelLibro",
    "AnalisisLeido",
    "AsociacionLeida",
    "CabeceraLeida",
    "CargoLeido",
    "InsumoPorCrear",
    "InsumoLeido",
    "TipoCargo",
    "TipoInsumo",
    "TotalesAnalisis",
]
