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
