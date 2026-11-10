"""Reglas de decisión del congelado de la línea base (TKT-017b1, fila B2).

Sin efectos secundarios. El caso de uso carga los estados y traduce la causa a su contrato de error.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from cimenta.presupuesto.dominio.materializacion import LineaBaseDeObra

_ESTADO_LINEA_BASE_ADMITIDO = "BORRADOR"
_ESTADO_OBRA_ADMITIDO = "PLANEACION"


class CausaRechazoCongelado(StrEnum):
    LINEA_BASE_EN_OTRO_ESTADO = "LINEA_BASE_EN_OTRO_ESTADO"
    OBRA_CON_CONGELADA = "OBRA_CON_CONGELADA"
    OBRA_FUERA_DE_PLANEACION = "OBRA_FUERA_DE_PLANEACION"


@dataclass(frozen=True, slots=True)
class CongeladoAdmitido:
    """La línea base puede congelarse."""


@dataclass(frozen=True, slots=True)
class CongeladoRechazado:
    """Causa del rechazo y los valores de dominio que el caso de uso vuelve contrato de error."""

    causa: CausaRechazoCongelado
    datos: Mapping[str, object]


type ResultadoCongelado = CongeladoAdmitido | CongeladoRechazado


def evaluar_congelado(
    *, estado_linea_base: str, otra_congelada: LineaBaseDeObra | None, estado_obra: str
) -> ResultadoCongelado:
    """Implementa RN-01 (CA-B2, CA-B3): solo un `BORRADOR` de una obra en planeación se congela.

    Orden: estado de la línea base, otra congelada vigente, estado de la obra. La congelada va antes
    que la obra porque una obra con congelada ya está `ACTIVA`.
    """
    if estado_linea_base != _ESTADO_LINEA_BASE_ADMITIDO:
        return CongeladoRechazado(
            causa=CausaRechazoCongelado.LINEA_BASE_EN_OTRO_ESTADO,
            datos={"estado": estado_linea_base},
        )
    if otra_congelada is not None:
        return CongeladoRechazado(
            causa=CausaRechazoCongelado.OBRA_CON_CONGELADA,
            datos={
                "linea_base_vigente_id": otra_congelada.id,
                "version_vigente": otra_congelada.version,
            },
        )
    if estado_obra != _ESTADO_OBRA_ADMITIDO:
        return CongeladoRechazado(
            causa=CausaRechazoCongelado.OBRA_FUERA_DE_PLANEACION,
            datos={"estado_obra": estado_obra},
        )
    return CongeladoAdmitido()


__all__ = [
    "CausaRechazoCongelado",
    "CongeladoAdmitido",
    "CongeladoRechazado",
    "ResultadoCongelado",
    "evaluar_congelado",
]
