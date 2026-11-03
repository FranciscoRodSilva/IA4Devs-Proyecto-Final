"""Objetos de valor del catálogo leído en memoria (TKT-013a).

HDU-001 esc. 5, 6, 8 y 27. Sin reglas RN-xx: solo lectura, sin persistencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tipos_base import Cantidad, Dinero

type ValorCelda = str | int | Decimal | None

UNIDADES_ADMITIDAS: frozenset[str] = frozenset(
    {"M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"}
)

ERRORES_DE_FORMULA: frozenset[str] = frozenset(
    {"#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A"}
)


class Profundidad(StrEnum):
    RAIZ = "RAIZ"
    NIVEL = "NIVEL"
    AREA = "AREA"
    PARTIDA = "PARTIDA"


class CausaHallazgo(StrEnum):
    HOJA_NO_LOCALIZADA = "HOJA_NO_LOCALIZADA"
    HOJA_AMBIGUA = "HOJA_AMBIGUA"
    ENCABEZADO_NO_LOCALIZADO = "ENCABEZADO_NO_LOCALIZADO"
    COLUMNA_NO_LOCALIZADA = "COLUMNA_NO_LOCALIZADA"
    NINGUN_CONCEPTO = "NINGUN_CONCEPTO"
    ERROR_DE_FORMULA = "ERROR_DE_FORMULA"
    NO_ES_NUMERO = "NO_ES_NUMERO"
    VALOR_AUSENTE = "VALOR_AUSENTE"
    UNIDAD_NO_RECONOCIDA = "UNIDAD_NO_RECONOCIDA"
    NOMBRE_ILEGIBLE = "NOMBRE_ILEGIBLE"
    CONCEPTO_SIN_PARTIDA = "CONCEPTO_SIN_PARTIDA"
    PROFUNDIDAD_EXCEDIDA = "PROFUNDIDAD_EXCEDIDA"
    VALOR_NEGATIVO = "VALOR_NEGATIVO"
    FECHA_NO_RECONOCIDA = "FECHA_NO_RECONOCIDA"
    CARGO_DESCONOCIDO = "CARGO_DESCONOCIDO"
    PU_NO_CUADRA = "PU_NO_CUADRA"
    PU_NO_VERIFICABLE = "PU_NO_VERIFICABLE"


@dataclass(frozen=True, slots=True)
class NodoLeido:
    fila: int
    profundidad: Profundidad
    nombre: str | None


@dataclass(frozen=True, slots=True)
class Ruta:
    raiz: NodoLeido | None
    nivel: NodoLeido | None
    area: NodoLeido | None
    partida: NodoLeido | None


@dataclass(frozen=True, slots=True)
class ConceptoLeido:
    fila: int
    codigo: str
    descripcion: str | None
    unidad: str | None
    cantidad: Cantidad | None
    precio_unitario: Dinero | None
    importe: Dinero | None
    ruta: Ruta


@dataclass(frozen=True, slots=True)
class Hallazgo:
    causa: CausaHallazgo
    hoja: str | None
    fila: int | None
    columna: str | None
    valor_original: str | None
    detalle: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogoLeido:
    hoja: str | None
    fila_encabezado: int | None
    nodos: tuple[NodoLeido, ...]
    conceptos: tuple[ConceptoLeido, ...]
    hallazgos: tuple[Hallazgo, ...]
