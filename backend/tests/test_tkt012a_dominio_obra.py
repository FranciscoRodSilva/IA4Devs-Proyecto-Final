"""Dominio de la obra (TKT-012a, fila A1): TC-01 a TC-04.

Sin Docker ni base de datos. Prueba `cimenta/presupuesto/dominio/obra.py`:
`normalizar_codigo_obra` (D-1, aprobado: recortar y pasar a mayúsculas), `ParametroObra` y
`porcentajes_fuera_de_rango` (PA-02: retención y fondo entre 0 y 1; PA-18: umbral no negativo).

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: mientras
`obra.py` no exista, cada caso falla por sí solo con `ModuleNotFoundError` de
`cimenta.presupuesto.dominio.obra` (la razón esperada) y la recolección no se cae. Los nombres
de los parámetros de la regla van como cadenas y se resuelven dentro del caso.
"""

from __future__ import annotations

import pytest

from tipos_base import Porcentaje


def test_hdu001_esc02_dominio_normaliza_el_codigo() -> None:
    """TC-01 · HDU-001 esc. 2 · CA-1 — feliz: el código se recorta y se pasa a mayúsculas (D-1)."""
    from cimenta.presupuesto.dominio.obra import normalizar_codigo_obra

    assert normalizar_codigo_obra("  ap-058-25 ") == "AP-058-25"


def test_hdu001_esc02_dominio_porcentajes_en_rango_y_bordes() -> None:
    """TC-02 · HDU-001 esc. 2 · CA-5 — feliz y borde: los extremos del rango se admiten.

    Retención y fondo admiten 0.000000 y 1.000000; el umbral admite 0.000000; el umbral
    ausente (`None`) no es un rango que comprobar. Ninguno de estos casos rechaza.
    """
    from cimenta.presupuesto.dominio.obra import porcentajes_fuera_de_rango

    assert (
        porcentajes_fuera_de_rango(
            retencion_destajo=Porcentaje("0.000000"),
            fondo_garantia=Porcentaje("1.000000"),
            umbral_alerta=Porcentaje("0.000000"),
        )
        == ()
    )
    assert (
        porcentajes_fuera_de_rango(
            retencion_destajo=Porcentaje("1.000000"),
            fondo_garantia=Porcentaje("0.000000"),
            umbral_alerta=None,
        )
        == ()
    )


CASOS_FUERA_DE_RANGO = [
    pytest.param("retencion_destajo", "-0.010000", "RETENCION_DESTAJO", id="retencion-bajo-cero"),
    pytest.param("retencion_destajo", "1.000001", "RETENCION_DESTAJO", id="retencion-sobre-uno"),
    pytest.param("fondo_garantia", "-0.010000", "FONDO_GARANTIA", id="fondo-bajo-cero"),
    pytest.param("fondo_garantia", "1.000001", "FONDO_GARANTIA", id="fondo-sobre-uno"),
    pytest.param("umbral_alerta", "-0.000001", "UMBRAL_ALERTA", id="umbral-negativo"),
]


@pytest.mark.parametrize(("parametro", "valor", "afectado"), CASOS_FUERA_DE_RANGO)
def test_hdu001_esc02_dominio_porcentaje_fuera_de_rango(
    parametro: str, valor: str, afectado: str
) -> None:
    """TC-03 · HDU-001 esc. 2 · CA-5 — rechazo: devuelve exactamente el parámetro afectado.

    Los demás parámetros quedan en rango; por eso la tupla debe ser exactamente el único
    parámetro fuera, sin ninguno de más.
    """
    from cimenta.presupuesto.dominio.obra import ParametroObra, porcentajes_fuera_de_rango

    valores = {
        "retencion_destajo": "0.150000",
        "fondo_garantia": "0.050000",
        "umbral_alerta": "0.150000",
    }
    valores[parametro] = valor

    resultado = porcentajes_fuera_de_rango(
        retencion_destajo=Porcentaje(valores["retencion_destajo"]),
        fondo_garantia=Porcentaje(valores["fondo_garantia"]),
        umbral_alerta=Porcentaje(valores["umbral_alerta"]),
    )

    assert resultado == (ParametroObra[afectado],)


def test_hdu001_esc02_dominio_varios_fuera_de_rango_en_orden() -> None:
    """TC-04 · HDU-001 esc. 2 · CA-5 — rechazo: con tres fuera, la tupla sale en orden fijo.

    El orden es RETENCION_DESTAJO, FONDO_GARANTIA, UMBRAL_ALERTA; cada uno aparece una vez.
    """
    from cimenta.presupuesto.dominio.obra import ParametroObra, porcentajes_fuera_de_rango

    resultado = porcentajes_fuera_de_rango(
        retencion_destajo=Porcentaje("1.000001"),
        fondo_garantia=Porcentaje("-0.010000"),
        umbral_alerta=Porcentaje("-0.000001"),
    )

    assert resultado == (
        ParametroObra.RETENCION_DESTAJO,
        ParametroObra.FONDO_GARANTIA,
        ParametroObra.UMBRAL_ALERTA,
    )
