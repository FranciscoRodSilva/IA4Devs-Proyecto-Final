"""Explosión sintética de 27 insumos (TKT-004, fila 2): TC-40 a TC-43.

El fixture es el producto cartesiano de tres cantidades, tres rendimientos y tres precios, sin
datos de ninguna obra. Por la propiedad distributiva, la suma de los 27 importes es el producto
de las tres sumas, que se calcula a mano con enteros y es independiente del código que se
prueba. La reconciliación con el total real del Excel es de TKT-016.

Sin Docker (CA-13). `sumar` se importa dentro de la prueba que lo usa.
"""

import itertools
import random
from decimal import Decimal
from fractions import Fraction

import pytest

from tipos_base import Cantidad, Dinero, Rendimiento

CANTIDADES = ("1459.5600", "16.0890", "237.4125")  # suma 1713.0615
RENDIMIENTOS = ("0.673400", "0.017000", "2.437153")  # suma 3.127553
PRECIOS = ("539.6300", "0.2500", "87.1237")  # suma 627.0037
# 17130615 × 3127553 × 6270037 = 335,929,185,066,580,048,515, con 4 + 6 + 4 = 14 decimales.
TOTAL_ESPERADO = "3359291.85066580048515"


@pytest.fixture
def explosion_sintetica() -> list[tuple[Cantidad, Rendimiento, Dinero]]:
    """27 renglones (cantidad de concepto, rendimiento del insumo, precio del insumo)."""
    return [
        (Cantidad(cantidad), Rendimiento(rendimiento), Dinero(precio))
        for cantidad, rendimiento, precio in itertools.product(CANTIDADES, RENDIMIENTOS, PRECIOS)
    ]


def test_tkt004_ca08_explosion_sintetica_sin_desviacion(
    explosion_sintetica: list[tuple[Cantidad, Rendimiento, Dinero]],
) -> None:
    """TC-40 · CA-8 esc. 1 — los 27 importes suman el literal exacto, sin cuantizar los renglones."""
    from tipos_base import sumar

    importes = [c * r * p for c, r, p in explosion_sintetica]
    total = sumar(importes, Dinero)

    assert len(explosion_sintetica) == 27
    assert total == Dinero(TOTAL_ESPERADO)
    assert total.valor == Decimal(TOTAL_ESPERADO)
    assert total.valor.as_tuple().exponent == -14


def test_tkt004_ca08_el_orden_no_importa(
    explosion_sintetica: list[tuple[Cantidad, Rendimiento, Dinero]],
) -> None:
    """TC-41 · CA-8 esc. 2 — invertidos o barajados, los mismos renglones dan el mismo total."""
    from tipos_base import sumar

    invertidos = list(reversed(explosion_sintetica))
    barajados = list(explosion_sintetica)
    random.Random(20261019).shuffle(barajados)

    assert barajados != explosion_sintetica, "el barajado debe cambiar el orden"
    for renglones in (invertidos, barajados):
        total = sumar([c * r * p for c, r, p in renglones], Dinero)
        assert total == Dinero(TOTAL_ESPERADO)


def test_tkt004_ca08_el_mismo_calculo_en_float_se_desvia(
    explosion_sintetica: list[tuple[Cantidad, Rendimiento, Dinero]],
) -> None:
    """TC-42 · CA-8 esc. 3 — el control negativo: en flotante el total no coincide con el literal."""
    esperado = Decimal(TOTAL_ESPERADO)
    assert len(esperado.as_tuple().digits) > 17, "un double no puede representar este total"

    total_en_float = sum(
        float(c.valor) * float(r.valor) * float(p.valor) for c, r, p in explosion_sintetica
    )

    assert Decimal(repr(total_en_float)) != esperado


def test_tkt004_ca08_total_esperado_independiente(
    explosion_sintetica: list[tuple[Cantidad, Rendimiento, Dinero]],
) -> None:
    """TC-43 · CA-8 esc. 1 — el literal se recalcula con Fraction, sin pasar por los tipos base."""
    total = sum(
        (
            Fraction(c.valor) * Fraction(r.valor) * Fraction(p.valor)
            for c, r, p in explosion_sintetica
        ),
        start=Fraction(0),
    )
    producto_de_sumas = Fraction(17130615 * 3127553 * 6270037, 10**14)

    assert len(explosion_sintetica) == 27
    assert total == Fraction(TOTAL_ESPERADO)
    assert producto_de_sumas == Fraction(TOTAL_ESPERADO)
