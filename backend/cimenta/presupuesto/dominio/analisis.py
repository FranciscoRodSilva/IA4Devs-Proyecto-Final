"""Objetos de valor del análisis de precios unitarios leído en memoria (TKT-014a).

HDU-001 esc. 5, 6, 7, 9 y 10; invariante 27; regla 1. Sin reglas RN-xx.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cimenta.presupuesto.dominio.catalogo import Hallazgo
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


__all__ = [
    "AnalisisLeido",
    "CabeceraLeida",
    "CargoLeido",
    "Hallazgo",
    "InsumoLeido",
    "TipoCargo",
    "TipoInsumo",
    "TotalesAnalisis",
]
