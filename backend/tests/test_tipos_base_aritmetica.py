"""Aritmética exacta de los tipos base (TKT-004, fila 2): TC-20 a TC-35.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-13). Todo importe se construye desde cadena. `sumar` se importa dentro de cada prueba
que lo usa, para que su ausencia ponga en rojo solo esas pruebas y no el archivo entero.
"""

import decimal
from collections.abc import Callable, Iterator
from decimal import Decimal
from fractions import Fraction

import pytest

from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

TIPOS = (Dinero, Cantidad, Rendimiento, Porcentaje)


def test_tkt004_ca03_cantidad_por_rendimiento_conserva_decimales() -> None:
    """TC-20 · CA-3 esc. 1 — Cantidad × Rendimiento da una Cantidad sin redondear a la escala 14,4."""
    producto = Cantidad("3.1234") * Rendimiento("0.673400")

    assert type(producto) is Cantidad
    assert producto.valor == Decimal("2.10329756")
    assert producto.valor.as_tuple().exponent == -10


def test_tkt004_ca03_productos_conmutativos() -> None:
    """TC-21 · D-6 — los tres productos admitidos dan el mismo tipo y valor en los dos órdenes."""
    cantidad = Cantidad("3.1234")
    rendimiento = Rendimiento("0.673400")
    dinero = Dinero("539.6300")
    porcentaje = Porcentaje("0.150000")

    rendimiento_por_cantidad = rendimiento * cantidad
    cantidad_por_dinero = cantidad * dinero
    porcentaje_por_dinero = porcentaje * dinero

    assert type(rendimiento_por_cantidad) is Cantidad
    assert rendimiento_por_cantidad == cantidad * rendimiento
    assert type(cantidad_por_dinero) is Dinero
    assert cantidad_por_dinero == dinero * cantidad
    assert type(porcentaje_por_dinero) is Dinero
    assert porcentaje_por_dinero == dinero * porcentaje
    assert porcentaje_por_dinero.valor == Decimal("80.94450000")


def test_tkt004_ca03_dinero_por_cantidad_y_por_porcentaje() -> None:
    """TC-22 · CA-3 esc. 2 — Dinero × Cantidad y Dinero × Porcentaje dan Dinero."""
    por_cantidad = Dinero("1000.0000") * Cantidad("2.5000")
    por_porcentaje = Dinero("1000.0000") * Porcentaje("0.150000")

    assert type(por_cantidad) is Dinero
    assert por_cantidad == Dinero("2500")
    assert type(por_porcentaje) is Dinero
    assert por_porcentaje == Dinero("150")


def test_tkt004_ca03_suma_resta_y_coleccion_vacia() -> None:
    """TC-23 · CA-3 esc. 3, PA-T16 — suma y resta exactas; la colección vacía da el cero del tipo."""
    from tipos_base import sumar

    a = Dinero("100.1001")
    b = Dinero("0.0009")
    c = Dinero("-50.5")

    assert a + b + c == Dinero("49.601")
    assert a - b == Dinero("100.0992")
    assert sumar([a, b, c], Dinero) == Dinero("49.601")
    vacia = sumar([], Dinero)
    assert type(vacia) is Dinero
    assert vacia.valor == 0


def test_tkt004_ca03_sumar_rechaza_tipos_mezclados() -> None:
    """TC-24 · PA-T16 — sumar no mezcla tipos y sum() no suma objetos de valor."""
    from tipos_base import sumar

    with pytest.raises(TypeError, match="Cantidad"):
        sumar([Dinero("1"), Cantidad("1")], Dinero)  # type: ignore[list-item]
    with pytest.raises(TypeError):
        sum([Dinero("1")])  # type: ignore[list-item]


def test_tkt004_ca03_sin_redondeo_intermedio() -> None:
    """TC-25 · CA-3 esc. 4 — Dinero × (Cantidad × Rendimiento) conserva todos los decimales."""
    resultado = Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857"))

    assert type(resultado) is Dinero
    assert resultado.valor == Decimal("1000.4989995")


def test_tkt004_ca03_operandos_maximos_exactos() -> None:
    """TC-26 · CA-3 esc. 5 — el producto de los máximos de columna tiene sus 32 dígitos, exactos."""
    producto = Cantidad("9999999999.9999") * Rendimiento("999999999999.999999")

    assert producto.valor == Decimal("9999999999999899990000.0000000001")
    assert len(producto.valor.as_tuple().digits) == 32


def _calculos_de_los_escenarios() -> dict[str, Decimal]:
    """Los cálculos de TC-20, TC-22, TC-23, TC-25, TC-26 y TC-31, con el valor de cada uno."""
    from tipos_base import sumar

    a = Dinero("100.1001")
    b = Dinero("0.0009")
    c = Dinero("-50.5")
    return {
        "TC-20": (Cantidad("3.1234") * Rendimiento("0.673400")).valor,
        "TC-22 cantidad": (Dinero("1000.0000") * Cantidad("2.5000")).valor,
        "TC-22 porcentaje": (Dinero("1000.0000") * Porcentaje("0.150000")).valor,
        "TC-23 suma": (a + b + c).valor,
        "TC-23 resta": (a - b).valor,
        "TC-23 sumar": sumar([a, b, c], Dinero).valor,
        "TC-25": (Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857"))).valor,
        "TC-26": (Cantidad("9999999999.9999") * Rendimiento("999999999999.999999")).valor,
        "TC-31": (Cantidad("1") / Cantidad("3")).valor,
    }


# Los mismos literales de TC-20, TC-22, TC-23, TC-25, TC-26 y TC-31, escritos a mano.
_VALORES_ESPERADOS = {
    "TC-20": Decimal("2.10329756"),
    "TC-22 cantidad": Decimal("2500"),
    "TC-22 porcentaje": Decimal("150"),
    "TC-23 suma": Decimal("49.601"),
    "TC-23 resta": Decimal("100.0992"),
    "TC-23 sumar": Decimal("49.601"),
    "TC-25": Decimal("1000.4989995"),
    "TC-26": Decimal("9999999999999899990000.0000000001"),
    "TC-31": Decimal("0." + "3" * 28),
}


@pytest.fixture
def contexto_de_decimal_hostil() -> Iterator[decimal.Context]:
    """Contexto del proceso con precisión 5 y sin trampas de redondeo; se restaura siempre."""
    with decimal.localcontext() as contexto:
        contexto.prec = 5
        contexto.traps[decimal.Inexact] = False
        contexto.traps[decimal.Rounded] = False
        yield contexto


def test_tkt004_ca03_contexto_del_proceso_no_altera_nada(
    contexto_de_decimal_hostil: decimal.Context,
) -> None:
    """TC-27 · CA-3 esc. 6 — con precisión 5 y sin trampas, los resultados son los mismos literales."""
    assert decimal.getcontext().prec == 5
    assert Decimal("3.1234") * Decimal("0.673400") != Decimal("2.10329756"), (
        "el contexto hostil debe redondear: si no, esta prueba no detecta nada"
    )

    obtenidos = _calculos_de_los_escenarios()

    assert obtenidos == _VALORES_ESPERADOS
    assert decimal.getcontext().prec == 5, "la aritmética no debe alterar el contexto del proceso"


_COMBINACIONES_SIN_SENTIDO: list[tuple[str, Callable[[], object]]] = [
    ("cantidad_por_cantidad", lambda: Cantidad("1") * Cantidad("1")),  # type: ignore[operator]
    ("dinero_por_dinero", lambda: Dinero("1") * Dinero("1")),  # type: ignore[operator]
    ("rendimiento_mas_dinero", lambda: Rendimiento("1") + Dinero("1")),  # type: ignore[operator]
    ("dinero_por_float", lambda: Dinero("1") * 0.5),  # type: ignore[operator]
    ("dinero_por_entero", lambda: Dinero("1") * 2),  # type: ignore[operator]
    ("entero_por_dinero", lambda: 2 * Dinero("1")),  # type: ignore[operator]
    ("dinero_mas_entero", lambda: Dinero("1") + 1),  # type: ignore[operator]
    ("negacion_de_dinero", lambda: -Dinero("1")),  # type: ignore[operator]
    ("rendimiento_por_dinero", lambda: Rendimiento("1") * Dinero("1")),  # type: ignore[operator]
]


@pytest.mark.parametrize(
    "operacion",
    [caso[1] for caso in _COMBINACIONES_SIN_SENTIDO],
    ids=[caso[0] for caso in _COMBINACIONES_SIN_SENTIDO],
)
def test_tkt004_ca03_combinaciones_sin_sentido(operacion: Callable[[], object]) -> None:
    """TC-28 · CA-3 esc. 7, PA-T15 — solo existen las operaciones listadas: el resto es TypeError."""
    with pytest.raises(TypeError):
        operacion()


def test_tkt004_ca04_cantidad_entre_cantidad() -> None:
    """TC-29 · CA-4 esc. 1 — Cantidad ÷ Cantidad da un Porcentaje exacto."""
    razon = Cantidad("30.0000") / Cantidad("120.0000")

    assert type(razon) is Porcentaje
    assert razon.valor == Decimal("0.25")


def test_tkt004_ca04_dinero_entre_dinero() -> None:
    """TC-30 · CA-4 esc. 2 — Dinero ÷ Dinero da un Porcentaje con signo."""
    razon = Dinero("-50.0000") / Dinero("200.0000")

    assert type(razon) is Porcentaje
    assert razon.valor == Decimal("-0.25")


def test_tkt004_ca04_division_no_exacta_con_28_digitos() -> None:
    """TC-31 · CA-4 esc. 3 — 1 ÷ 3 conserva 28 dígitos y no se cuantiza a la escala 9,6."""
    razon = Cantidad("1") / Cantidad("3")

    assert razon.valor == Decimal("0." + "3" * 28)
    assert razon.valor.as_tuple().exponent == -28


@pytest.mark.parametrize(
    ("dividendo", "divisor"),
    [
        (Cantidad("12.0000"), Cantidad("0.0000")),
        (Dinero("1"), Dinero("0")),
        (Cantidad("0"), Cantidad("0")),
    ],
    ids=["cantidad_entre_cero", "dinero_entre_cero", "cero_entre_cero"],
)
def test_tkt004_ca04_division_entre_cero(
    dividendo: Cantidad | Dinero, divisor: Cantidad | Dinero
) -> None:
    """TC-32 · CA-4 esc. 4, regla 12 — dividir entre cero no devuelve cero ni infinito."""
    with pytest.raises(ZeroDivisionError, match="regla 12"):
        dividendo / divisor  # type: ignore[operator]


@pytest.mark.parametrize(
    "operacion",
    [
        pytest.param(
            lambda: Cantidad("1") / Dinero("1"),  # type: ignore[operator]
            id="cantidad_entre_dinero",
        ),
        pytest.param(
            lambda: Rendimiento("1") / Rendimiento("1"),  # type: ignore[operator]
            id="rendimiento_entre_rendimiento",
        ),
        pytest.param(
            lambda: Porcentaje("1") / Porcentaje("1"),  # type: ignore[operator]
            id="porcentaje_entre_porcentaje",
        ),
    ],
)
def test_tkt004_ca04_division_entre_tipos_no_admitida(operacion: Callable[[], object]) -> None:
    """TC-33 · PA-T11 — solo existen Cantidad ÷ Cantidad y Dinero ÷ Dinero."""
    with pytest.raises(TypeError):
        operacion()


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca07_cero_uno_mas_cero_dos(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-34 · CA-7 esc. 1 — 0.1 + 0.2 da exactamente 0.3 en los cuatro tipos."""
    assert tipo("0.1") + tipo("0.2") == tipo("0.3")  # type: ignore[operator]


def test_tkt004_ca07_oraculo_float() -> None:
    """TC-35 · CA-7 esc. 2 — el oráculo: con flotantes, 0.1 + 0.2 no es 0.3."""
    assert 0.1 + 0.2 != 0.3


def test_tkt004_ca03_resultado_de_mas_de_56_digitos_exacto() -> None:
    """TC-26b · CA-3 esc. 5 — productos y sumas de más de 56 dígitos siguen exactos, contra fractions."""
    from tipos_base import sumar

    grande = "99999999999999999999.99999999999999999999"  # 41 dígitos, exponente -20
    otro = "88888888888888888888.77777777777777777777"
    cantidad = Cantidad(grande)
    rendimiento = Rendimiento(otro)
    dinero = Dinero(grande)

    producto = cantidad * rendimiento
    encadenado = dinero * producto
    suma = sumar([producto, producto, producto], Cantidad)

    esperado_producto = Fraction(grande) * Fraction(otro)
    assert len(producto.valor.as_tuple().digits) > 56
    assert Fraction(producto.valor) == esperado_producto
    assert len(encadenado.valor.as_tuple().digits) > 56
    assert Fraction(encadenado.valor) == Fraction(grande) * esperado_producto
    assert len(suma.valor.as_tuple().digits) > 56
    assert Fraction(suma.valor) == 3 * esperado_producto


def test_tkt004_ca03_contexto_del_proceso_no_altera_cuantizar_ni_serializar(
    contexto_de_decimal_hostil: decimal.Context,
) -> None:
    """TC-27b · CA-3 esc. 6, CA-5, CA-6 — con precisión 5 y sin trampas, cuantizar y serializar dan lo mismo."""
    casos = [
        (Dinero, "123456789012.34565", "123456789012.3457"),
        (Dinero, "-123456789012.34565", "-123456789012.3457"),
        (Dinero, "99999999999999.99994", "99999999999999.9999"),
        (Cantidad, "1234567890.12345", "1234567890.1235"),
        (Rendimiento, "123456789012.1234565", "123456789012.123457"),
        (Porcentaje, "123.1234565", "123.123457"),
    ]
    assert decimal.getcontext().prec == 5

    for tipo, origen, esperado in casos:
        cuantizado = tipo(origen).cuantizar()
        assert cuantizado.valor == Decimal(esperado), (tipo.__name__, origen)
        assert cuantizado.serializar() == esperado, (tipo.__name__, origen)
        assert tipo(esperado).serializar() == esperado, (tipo.__name__, esperado)

    assert decimal.getcontext().prec == 5, (
        "cuantizar y serializar no deben alterar el contexto del proceso"
    )


def test_tkt004_ca06_contexto_del_proceso_no_altera_los_rechazos_de_serializar_y_cuantizar(
    contexto_de_decimal_hostil: decimal.Context,
) -> None:
    """TC-27c · CA-5 esc. 4, CA-6 esc. 4 y 6 — los rechazos por escala y por columna siguen siendo ValueError."""
    with pytest.raises(ValueError, match="4 decimales"):
        Dinero("123456789012.34565").serializar()
    with pytest.raises(ValueError, match=r"NUMERIC\(18,4\)"):
        Dinero("99999999999999.99995").cuantizar()
    with pytest.raises(ValueError, match=r"NUMERIC\(9,6\)"):
        Porcentaje("1000.000000").cuantizar()


@pytest.mark.parametrize(
    "operacion",
    [
        pytest.param(lambda: Dinero("1") / Cantidad("1"), id="dinero_entre_cantidad"),  # type: ignore[operator]
        pytest.param(lambda: Dinero("1") / Porcentaje("1"), id="dinero_entre_porcentaje"),  # type: ignore[operator]
        pytest.param(lambda: Cantidad("1") / Porcentaje("1"), id="cantidad_entre_porcentaje"),  # type: ignore[operator]
        pytest.param(lambda: Porcentaje("1") / Dinero("1"), id="porcentaje_entre_dinero"),  # type: ignore[operator]
    ],
)
def test_tkt004_ca04_division_entre_tipos_no_admitida_cruces_con_dinero_y_porcentaje(
    operacion: Callable[[], object],
) -> None:
    """TC-33b · PA-T11 — Dinero y Cantidad solo se dividen entre su propio tipo; Porcentaje no es divisor ni dividendo."""
    with pytest.raises(TypeError):
        operacion()
