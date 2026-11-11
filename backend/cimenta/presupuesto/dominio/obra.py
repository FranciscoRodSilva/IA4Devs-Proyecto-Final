"""Reglas de la obra (TKT-012a, fila A1). Escenario: HDU-001 esc. 2 (CA-1, CA-5).

PA-02: la retención de destajo y el fondo de garantía son dos porcentajes distintos, cada uno
entre 0 y 1; los `CHECK` de la migración 0006 fijan el mismo rango en la base. PA-18: el umbral
de alerta no es negativo y, cuando falta, no hay rango que comprobar. Sin efectos secundarios.
"""

from __future__ import annotations

from enum import StrEnum

from tipos_base import Porcentaje

_CERO = Porcentaje("0")
_UNO = Porcentaje("1")


class ParametroObra(StrEnum):
    RETENCION_DESTAJO = "retencion_destajo_pct"
    FONDO_GARANTIA = "fondo_garantia_pct"
    UMBRAL_ALERTA = "umbral_alerta_pct"


def normalizar_codigo_obra(codigo: str) -> str:
    """Recorta los espacios y pasa a mayúsculas (D-1, aprobado). HDU-001 esc. 2 (CA-1).

    `ap-058-25 ` es `AP-058-25`; así la unicidad del código no depende de cómo se escriba.
    """
    return codigo.strip().upper()


def porcentajes_fuera_de_rango(
    *,
    retencion_destajo: Porcentaje,
    fondo_garantia: Porcentaje,
    umbral_alerta: Porcentaje | None,
) -> tuple[ParametroObra, ...]:
    """Implementa PA-02 y PA-18. HDU-001 esc. 2 (CA-5). Sin efectos secundarios.

    Devuelve, en orden fijo (retención, fondo, umbral), cada parámetro fuera de rango. El
    rechazo lo lanza el caso de uso, no esta función.
    """
    fuera: list[ParametroObra] = []
    if not _entre_cero_y_uno(retencion_destajo):
        fuera.append(ParametroObra.RETENCION_DESTAJO)
    if not _entre_cero_y_uno(fondo_garantia):
        fuera.append(ParametroObra.FONDO_GARANTIA)
    if _umbral_negativo(umbral_alerta):
        fuera.append(ParametroObra.UMBRAL_ALERTA)
    return tuple(fuera)


def _entre_cero_y_uno(valor: Porcentaje) -> bool:
    return _CERO <= valor <= _UNO


def _umbral_negativo(umbral: Porcentaje | None) -> bool:
    return umbral is not None and umbral < _CERO
