"""TKT-017a1 · Deserialización de preparación (TC-A03)."""

from __future__ import annotations

import pytest

from cimenta.presupuesto.infraestructura.preparacion_json import (
    FORMATO_PREPARACION,
    FormatoPreparacionDesconocido,
    preparacion_a_json,
    preparacion_desde_json,
)
from herramientas.soporte_tkt017 import preparacion_sintetica


def test_tkt017_caa05_preparacion_ida_y_vuelta() -> None:
    """TC-A03 · CA-A5 esc. 1 — `preparacion_desde_json(preparacion_a_json(p)) == p` con hallazgos vacíos."""
    original = preparacion_sintetica()
    documento = preparacion_a_json(original)
    reconstruida = preparacion_desde_json(documento)
    assert reconstruida == original


@pytest.mark.parametrize(
    "caso",
    [
        pytest.param({"formato": 2}, id="formato_2"),
        pytest.param({}, id="sin_formato"),
        pytest.param({"conceptos": "no_es_lista"}, id="conceptos_no_lista"),
    ],
)
def test_tkt017_caa05_formato_desconocido(caso: dict[str, object]) -> None:
    """TC-A03 · CA-R1 — formato distinto o estructura ilegible."""
    base = preparacion_a_json(preparacion_sintetica())
    documento: dict[str, object] = {**base, **caso}
    if caso == {}:
        documento.pop("formato", None)
    with pytest.raises(FormatoPreparacionDesconocido) as error:
        preparacion_desde_json(documento)
    if "formato" in caso and caso["formato"] == 2:
        assert error.value.formato == 2
    else:
        assert error.value.formato is not FORMATO_PREPARACION


@pytest.mark.parametrize("fecha", ["2026-13-45", "2026-02-30"], ids=["mes_13", "30_de_febrero"])
def test_tkt017_caa05_fecha_de_analisis_imposible_es_formato_desconocido(fecha: str) -> None:
    """TC-A03 · CA-A5 esc. 1 — una fecha de análisis que no existe en el calendario es una preparación ilegible.

    `apu.fecha_analisis` es un `date`: la fecha se valida al leer la preparación, no al escribir la
    base, donde sería un `ValueError` y un `500`.
    """
    base = preparacion_a_json(preparacion_sintetica())
    analisis = base["analisis"]
    assert isinstance(analisis, list)
    documento: dict[str, object] = {
        **base,
        "analisis": [{**analisis[0], "fecha": fecha}, *analisis[1:]],
    }

    with pytest.raises(FormatoPreparacionDesconocido):
        preparacion_desde_json(documento)
