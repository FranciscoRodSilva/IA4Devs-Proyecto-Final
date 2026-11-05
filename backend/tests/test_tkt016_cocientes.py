"""Cocientes con nombre de tipos_base (TKT-016, fila A1)."""

from decimal import Decimal

import pytest

from tipos_base import Cantidad, Dinero, Rendimiento, cociente_precio_unitario, cociente_rendimiento


def test_hdu001_esc14_cociente_rendimiento_da_rendimiento_con_28_digitos() -> None:
    """TC-01 · CA-2, M3 — cociente_rendimiento devuelve Rendimiento con precisión de división."""
    assert cociente_rendimiento(Cantidad("3"), Cantidad("2")) == Rendimiento("1.5")
    r = cociente_rendimiento(Cantidad("30"), Cantidad("14"))
    assert isinstance(r, Rendimiento)
    assert len(r.valor.as_tuple().digits) == 28 or r.valor.as_tuple().exponent == -28
    assert r.cuantizar() == Rendimiento("2.142857")


def test_hdu001_esc14_cociente_precio_unitario_da_dinero() -> None:
    """TC-02 · CA-2 — cociente_precio_unitario devuelve Dinero."""
    r = cociente_precio_unitario(Dinero("27100"), Cantidad("325"))
    assert isinstance(r, Dinero)
    assert r.cuantizar() == Dinero("83.3846")
    assert cociente_precio_unitario(Dinero("10"), Cantidad("4")).valor == Decimal("2.5")


@pytest.mark.parametrize(
    ("funcion", "a", "b"),
    [
        (cociente_rendimiento, Cantidad("1"), Cantidad("0")),
        (cociente_rendimiento, Cantidad("1"), Cantidad("0.0000")),
        (cociente_precio_unitario, Dinero("1"), Cantidad("0")),
        (cociente_precio_unitario, Dinero("1"), Cantidad("0.0000")),
    ],
)
def test_hdu001_esc14_cociente_entre_cero_falla(
    funcion: object,
    a: Cantidad | Dinero,
    b: Cantidad,
) -> None:
    """TC-03 · CA-7 — división entre cero menciona regla 12."""
    with pytest.raises(ZeroDivisionError, match="regla 12"):
        funcion(a, b)  # type: ignore[operator]


def test_hdu001_esc14_cociente_rechaza_tipos_ajenos() -> None:
    """TC-04 · CA-R1 — tipos ajenos dan TypeError; Dinero/Cantidad sigue prohibido."""
    with pytest.raises(TypeError):
        cociente_rendimiento(Dinero("1"), Cantidad("1"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cociente_precio_unitario(Rendimiento("1"), Cantidad("1"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Dinero("1") / Cantidad("1")  # type: ignore[operator]
