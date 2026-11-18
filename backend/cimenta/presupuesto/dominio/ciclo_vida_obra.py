"""Máquina de estados y edición de la obra, TKT-012b (fila A2).

Los parámetros de la obra son por obra y editables (PA-02, PA-18): ninguno es constante del
código. La máquina de estados no tiene regla propia en el PRD: su tabla es la decisión D-2 de la
spec de TKT-012b, confirmada por la persona dueña el 2026-11-17. Sin efectos secundarios: el caso
de uso lee la obra bajo bloqueo, llama a estas funciones y traduce el resultado a su contrato.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Final

from tipos_base import Porcentaje

type ValorEditable = str | bool | Porcentaje | None


class EstadoObraDominio(StrEnum):
    PLANEACION = "PLANEACION"
    ACTIVA = "ACTIVA"
    SUSPENDIDA = "SUSPENDIDA"
    CERRADA = "CERRADA"


class OperacionObra(StrEnum):
    SUSPENDER = "SUSPENDER"
    REACTIVAR = "REACTIVAR"
    CERRAR = "CERRAR"


@dataclass(frozen=True, slots=True)
class TransicionAdmitida:
    estado_destino: EstadoObraDominio


@dataclass(frozen=True, slots=True)
class TransicionRechazada:
    estado_actual: EstadoObraDominio
    operaciones_admitidas: tuple[OperacionObra, ...]


type ResultadoTransicion = TransicionAdmitida | TransicionRechazada


@dataclass(frozen=True, slots=True)
class DatosObraEditables:
    nombre: str
    domicilio: str
    retencion_destajo_pct: Porcentaje
    fondo_garantia_pct: Porcentaje
    iva_acreditable: bool
    umbral_alerta_pct: Porcentaje | None


@dataclass(frozen=True, slots=True)
class CambiosEfectivos:
    antes: Mapping[str, ValorEditable]
    despues: Mapping[str, ValorEditable]


# Única fuente de la tabla D-2: origen y operación -> destino. `PLANEACION -> ACTIVA` no figura a
# propósito: solo lo produce el congelado, nunca una de las tres operaciones.
_DESTINO_POR_TRANSICION: Final[
    Mapping[tuple[EstadoObraDominio, OperacionObra], EstadoObraDominio]
] = {
    (EstadoObraDominio.ACTIVA, OperacionObra.SUSPENDER): EstadoObraDominio.SUSPENDIDA,
    (EstadoObraDominio.SUSPENDIDA, OperacionObra.REACTIVAR): EstadoObraDominio.ACTIVA,
    (EstadoObraDominio.PLANEACION, OperacionObra.CERRAR): EstadoObraDominio.CERRADA,
    (EstadoObraDominio.ACTIVA, OperacionObra.CERRAR): EstadoObraDominio.CERRADA,
    (EstadoObraDominio.SUSPENDIDA, OperacionObra.CERRAR): EstadoObraDominio.CERRADA,
}

_CAMPOS_EDITABLES: Final[tuple[str, ...]] = tuple(f.name for f in fields(DatosObraEditables))


def evaluar_transicion(estado: EstadoObraDominio, operacion: OperacionObra) -> ResultadoTransicion:
    """Implementa la tabla D-2 de la spec de TKT-012b (PA-02, PA-18; sin RN en el PRD). Sin efectos secundarios.

    El rechazo trae el estado actual y las operaciones que sí admite: es el dato del `409`.
    """
    destino = _DESTINO_POR_TRANSICION.get((estado, operacion))
    if destino is None:
        return TransicionRechazada(
            estado_actual=estado, operaciones_admitidas=operaciones_admitidas(estado)
        )
    return TransicionAdmitida(estado_destino=destino)


def operaciones_admitidas(estado: EstadoObraDominio) -> tuple[OperacionObra, ...]:
    """Operaciones que admite el estado, en el orden de `OperacionObra`. Fuente de las `acciones`."""
    return tuple(
        operacion for operacion in OperacionObra if (estado, operacion) in _DESTINO_POR_TRANSICION
    )


def admite_edicion(estado: EstadoObraDominio) -> bool:
    """Implementa D-3 de la spec de TKT-012b (sin RN en el PRD). Solo `CERRADA` bloquea la edición."""
    return estado is not EstadoObraDominio.CERRADA


def cambios_efectivos(
    actuales: DatosObraEditables, propuestos: Mapping[str, ValorEditable]
) -> CambiosEfectivos:
    """Implementa CA-1 de la spec de TKT-012b (PA-02, PA-18; sin RN en el PRD). Sin efectos secundarios.

    Una clave ausente de `propuestos` no cambia nada. La comparación es por valor: dos porcentajes
    iguales en valor no son un cambio, y `None` distinto de `0` sí lo es.
    """
    vigentes = _valores_vigentes(actuales)
    antes: dict[str, ValorEditable] = {}
    despues: dict[str, ValorEditable] = {}
    for campo in _CAMPOS_EDITABLES:
        if campo not in propuestos:
            continue
        nuevo = propuestos[campo]
        if nuevo != vigentes[campo]:
            antes[campo] = vigentes[campo]
            despues[campo] = nuevo
    return CambiosEfectivos(antes=antes, despues=despues)


def _valores_vigentes(actuales: DatosObraEditables) -> dict[str, ValorEditable]:
    return {campo: getattr(actuales, campo) for campo in _CAMPOS_EDITABLES}
