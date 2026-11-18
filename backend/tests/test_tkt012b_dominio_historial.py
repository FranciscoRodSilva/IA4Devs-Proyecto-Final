"""Regla pura de «¿tiene historial?», TKT-012b (fila A2, TC-12). RN-01 · HDU-001 esc. 20.

Pytest puro, sin Docker ni base. Define la API que el desarrollador implementa en
`cimenta/presupuesto/dominio/historial_obra.py`:

* `ConteosHistorial` (dataclass congelado), cinco campos, todos con nombre:
  `lineas_base: int` (filas de `linea_base` de la obra, de cualquier estado),
  `linea_base_congelada: bool`, `importaciones: int`,
  `filas_propias: int` (suma de filas de `nivel`, `concepto`, `precio_insumo` y
  `rendimiento_observado` de la obra) y `movimientos: int` (suma de lo que reportan las fuentes
  de los módulos posteriores; hoy, cero).
* `hay_historial(conteos) -> bool`: verdadero si **cualquier** conteo entero es mayor que cero.

`(asumido)` D-DIS-5: «línea base no vacía de cualquier estado» se decide por la existencia de **alguna
fila** de `linea_base` (`lineas_base > 0`), sin contar sus hijas. Una línea base `BORRADOR` ya es
historial. La persona dueña no ha confirmado la lectura; si la cambia, cambia el caso
`lineas_base-borrador` de este archivo. `linea_base_congelada` solo alimenta el detalle del `409`;
no decide: una congelada implica `lineas_base >= 1`, y ese caso no se prueba aisladamente.

Nace en rojo: `hay_historial` del esqueleto lanza `NotImplementedError`.
"""

from __future__ import annotations

import pytest

from cimenta.presupuesto.dominio.historial_obra import ConteosHistorial, hay_historial


def _conteos(
    *,
    lineas_base: int = 0,
    linea_base_congelada: bool = False,
    importaciones: int = 0,
    filas_propias: int = 0,
    movimientos: int = 0,
) -> ConteosHistorial:
    return ConteosHistorial(
        lineas_base=lineas_base,
        linea_base_congelada=linea_base_congelada,
        importaciones=importaciones,
        filas_propias=filas_propias,
        movimientos=movimientos,
    )


def test_hdu001_esc20_obra_recien_dada_de_alta_no_tiene_historial() -> None:
    """TC-12 · CA-5 · RN-01 — todo en cero (obra recién creada): no hay historial y se puede borrar."""
    assert hay_historial(_conteos()) is False


@pytest.mark.parametrize(
    "conteos",
    [
        pytest.param(_conteos(lineas_base=1), id="lineas_base-borrador"),
        pytest.param(
            _conteos(lineas_base=1, linea_base_congelada=True), id="lineas_base-congelada"
        ),
        pytest.param(_conteos(lineas_base=3, linea_base_congelada=True), id="lineas_base-varias"),
        pytest.param(_conteos(importaciones=1), id="importaciones"),
        pytest.param(_conteos(filas_propias=1), id="filas_propias"),
        pytest.param(_conteos(movimientos=1), id="movimientos-externos"),
        pytest.param(_conteos(movimientos=12), id="movimientos-externos-varios"),
    ],
)
def test_hdu001_esc20_cada_fuente_por_separado_basta_para_tener_historial(
    conteos: ConteosHistorial,
) -> None:
    """TC-12 · CA-6 · RN-01 — con una sola fuente en uno y el resto en cero ya hay historial.

    Cubre la línea base de cualquier estado (D-DIS-5, asumido), la importación sin línea base
    congelada (CA-6 ejemplo 2), las filas propias y los movimientos de módulos posteriores.
    """
    assert hay_historial(conteos) is True


def test_tkt012b_ca6_todas_las_fuentes_a_la_vez_tienen_historial() -> None:
    """TC-12 · CA-6 — el caso de HDU-001 esc. 20: congelada, importaciones, filas propias y movimientos."""
    conteos = _conteos(
        lineas_base=2,
        linea_base_congelada=True,
        importaciones=4,
        filas_propias=300,
        movimientos=7,
    )

    assert hay_historial(conteos) is True


@pytest.mark.parametrize(
    "con_historial",
    [
        pytest.param(_conteos(lineas_base=1), id="lineas_base"),
        pytest.param(_conteos(importaciones=1), id="importaciones"),
        pytest.param(_conteos(filas_propias=1), id="filas_propias"),
        pytest.param(_conteos(movimientos=1), id="movimientos"),
    ],
)
def test_tkt012b_ca5_ninguna_fuente_se_ignora_ni_depende_de_las_otras(
    con_historial: ConteosHistorial,
) -> None:
    """TC-12 · CA-5, CA-6 — poner en uno cualquiera de los cuatro conteos cambia el resultado de falso a verdadero.

    Mutantes que mata: ignorar una fuente, o exigir dos a la vez.
    """
    assert hay_historial(_conteos()) is False
    assert hay_historial(con_historial) is True
