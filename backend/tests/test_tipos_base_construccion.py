"""Construcción, inmutabilidad e igualdad de los tipos base (TKT-004, fila 1): TC-01 a TC-12.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-13). Todo importe se construye desde cadena; donde un caso necesita la construcción
prohibida, la escribe y la silencia con el motivo.
"""

import re
import time
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

TIPOS = (Dinero, Cantidad, Rendimiento, Porcentaje)
TIPOS_CON_SIGNO = (Dinero, Cantidad, Porcentaje)


def test_tkt004_ca01_construye_desde_cadena_entero_y_decimal() -> None:
    """TC-01 · CA-1 esc. 1 — los tres orígenes dan un valor exacto y el de «12.10» conserva 12.10."""
    desde_cadena = Dinero("12.10")
    desde_entero = Dinero(12)
    desde_decimal = Dinero(Decimal("12.10"))

    assert desde_cadena.valor == Decimal("12.10")
    assert str(desde_cadena.valor) == "12.10"
    assert desde_entero.valor == Decimal(12)
    assert desde_decimal.valor == desde_cadena.valor
    assert str(desde_decimal.valor) == "12.10"


@pytest.mark.parametrize("tipo", TIPOS_CON_SIGNO, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_admite_signo_sin_validar_rangos(
    tipo: type[Dinero] | type[Cantidad] | type[Porcentaje],
) -> None:
    """TC-02 · CA-1 esc. 2 — el signo lo valida cada caso de uso, no el tipo."""
    valor = tipo("-250.0000")

    assert valor.valor == Decimal("-250.0000")


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_rechaza_float(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-03 · CA-1 esc. 3 — un float no se acepta y el error nombra lo recibido."""
    with pytest.raises(TypeError, match="float"):
        tipo(0.1)  # type: ignore[arg-type]


def test_tkt004_ca01_rechaza_decimal_construido_desde_float() -> None:
    """TC-04 · CA-1 esc. 3, D-1 — Decimal(0.1) arrastra el error binario y no entra."""
    desde_float = Decimal(0.1)  # noqa: RUF032 — el caso necesita exactamente la construcción prohibida

    with pytest.raises(TypeError, match="float"):
        Dinero(desde_float)


def test_tkt004_ca01_admite_decimal_exacto_de_dieciocho_digitos() -> None:
    """TC-05 · D-1 — un double exacto de 18 dígitos no lleva huella de float: es el borde."""
    exacto = Decimal("12345678901234.5625")

    assert Dinero(exacto).valor == exacto


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "cadena",
    ["0.5000000000000000000", "100000000000000.0000"],
    ids=["medio_con_19_digitos", "cien_billones_con_19_digitos"],
)
def test_tkt004_ca01_admite_decimal_legitimo_con_ceros_finales(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
    cadena: str,
) -> None:
    """TC-05b · D-1 — los ceros finales no son huella de float: 19 dígitos, pero solo 1 significativo."""
    legitimo = Decimal(cadena)

    construido = tipo(legitimo)

    assert construido.valor == legitimo
    assert str(construido.valor) == cadena


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_rechaza_decimal_de_float_potencia_negativa_de_dos(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-05c · CA-1 esc. 3, D-1 — Decimal(2**-30) tiene 21 dígitos sin ceros finales y es un double exacto."""
    desde_float = Decimal(2**-30)  # noqa: RUF032 — el caso necesita exactamente la construcción prohibida

    with pytest.raises(TypeError, match="float"):
        tipo(desde_float)


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_rechaza_double_exacto_de_diecinueve_digitos_significativos(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-05d · CA-1 esc. 3, D-1 — borde de rechazo: 19 dígitos significativos y double exacto."""
    desde_float = Decimal(2**-27)  # noqa: RUF032 — el caso necesita exactamente la construcción prohibida
    assert len(desde_float.as_tuple().digits) == 19

    with pytest.raises(TypeError, match="float"):
        tipo(desde_float)


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_admite_decimal_de_diecinueve_digitos_que_no_es_double(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-05e · D-1 — 19 dígitos significativos pero no es un double: sin huella de float, se admite."""
    legitimo = Decimal("0.1234567890123456789")
    assert Decimal.from_float(float(legitimo)) != legitimo

    construido = tipo(legitimo)

    assert construido.valor == legitimo
    assert str(construido.valor) == "0.1234567890123456789"


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_admite_double_exacto_de_dieciocho_digitos_significativos(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
) -> None:
    """TC-05f · D-1 — borde de aceptación: 18 dígitos significativos y double exacto caben en la columna."""
    exacto = Decimal(2**-25)  # noqa: RUF032 — el caso necesita un double exacto de 18 dígitos
    assert len(exacto.as_tuple().digits) == 18
    assert Decimal.from_float(float(exacto)) == exacto

    construido = tipo(exacto)

    assert construido.valor == exacto


@pytest.mark.parametrize("booleano", [True, False])
def test_tkt004_ca01_rechaza_booleano(booleano: bool) -> None:
    """TC-06 · CA-1 esc. 4 — bool es subclase de int en Python, y aun así no es un número."""
    with pytest.raises(TypeError, match="bool"):
        Dinero(booleano)


@pytest.mark.parametrize("cadena", ["NaN", "Infinity", "1e3", "1,234.50", " 12.10", "+12.10", ""])
def test_tkt004_ca01_rechaza_cadena_que_no_es_decimal_llano(cadena: str) -> None:
    """TC-07 · CA-1 esc. 5 — el mensaje cita la cadena recibida, tal como llegó."""
    with pytest.raises(ValueError, match=re.escape(repr(cadena))):
        Dinero(cadena)


@pytest.mark.parametrize("no_finito", ["NaN", "Infinity", "-Infinity"])
def test_tkt004_ca01_rechaza_decimal_no_finito(no_finito: str) -> None:
    """TC-08 · CA-1 esc. 6 — un Decimal que no es finito no se construye."""
    with pytest.raises(ValueError, match="finitos"):
        Dinero(Decimal(no_finito))


@pytest.mark.parametrize(
    ("recibido", "nombre"),
    [(None, "NoneType"), (Fraction(1, 3), "Fraction")],
    ids=["None", "Fraction"],
)
def test_tkt004_ca01_rechaza_otros_tipos(recibido: object, nombre: str) -> None:
    """TC-09 · M1 — solo se construye desde str, int o Decimal; el mensaje nombra el tipo recibido."""
    with pytest.raises(TypeError, match=re.escape(nombre)):
        Dinero(recibido)  # type: ignore[arg-type]


def test_tkt004_ca02_valor_inmutable() -> None:
    """TC-10 · CA-2 esc. 1 — ni se reasigna ni se añade un atributo, y el valor sigue igual."""
    dinero = Dinero("10.0000")

    with pytest.raises(AttributeError):
        dinero.valor = Decimal("99")  # type: ignore[misc]
    # En Python 3.14 o posterior un atributo nuevo sobre una dataclass frozen con slots lanza
    # TypeError («super(type, obj)…») en lugar de AttributeError: el fallo es de la plataforma, y lo que
    # exige CA-2 es que la asignación falle y que el atributo no exista después.
    with pytest.raises((AttributeError, TypeError)):
        dinero.otro = 1  # type: ignore[attr-defined]

    assert dinero.valor == Decimal("10.0000")
    assert not hasattr(dinero, "otro")


def test_tkt004_ca02_igualdad_y_hash_por_valor() -> None:
    """TC-11 · CA-2 esc. 2 — mismo número, igualdad, mismo hash y misma clave."""
    uno = Dinero("1.0")
    otro = Dinero("1.0000")

    assert uno == otro
    assert hash(uno) == hash(otro)
    assert {uno: "x"}[otro] == "x"
    assert len({uno, otro}) == 1


def test_tkt004_ca02_sin_conversion_a_float_ni_redondeo() -> None:
    """TC-12a · CA-2 esc. 3 — el valor no se convierte en float ni se redondea por la puerta de atrás."""
    dinero = Dinero("10.0000")

    with pytest.raises(TypeError):
        float(dinero)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        round(dinero, 2)  # type: ignore[call-overload]


def test_tkt004_ca02_dinero_y_cantidad_no_se_mezclan() -> None:
    """TC-12b · CA-2 esc. 4 — suma, resta y orden fallan; la igualdad entre tipos distintos es falsa."""
    dinero = Dinero("5.0000")
    cantidad = Cantidad("5.0000")

    with pytest.raises(TypeError):
        _ = dinero + cantidad  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = dinero - cantidad  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = dinero < cantidad  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = dinero > cantidad  # type: ignore[operator]

    assert (dinero == cantidad) is False


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "cadena",
    ["١٢", "١٢.٥", "12.10\n", "\n12.10", "12.10 "],
    ids=[
        "digitos_arabigo_indicos",
        "decimal_arabigo_indico",
        "salto_final",
        "salto_inicial",
        "espacio_final",
    ],
)
def test_tkt004_ca01_rechaza_digitos_unicode_y_saltos_de_linea(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje], cadena: str
) -> None:
    """TC-07b · CA-1 esc. 5 — solo dígitos ASCII 0-9: los de otros alfabetos y el salto final no entran."""
    with pytest.raises(ValueError, match=re.escape(repr(cadena))):
        tipo(cadena)


_FUERA_DE_RANGO: list[tuple[str, Callable[[], str | int | Decimal]]] = [
    ("decimal_1E_mas_999999999", lambda: Decimal("1E+999999999")),
    ("cero_0E_menos_999999999", lambda: Decimal("0E-999999999")),
    ("decimal_1E_menos_999999999", lambda: Decimal("1E-999999999")),
    ("cadena_de_200000_nueves", lambda: "9" * 200000),
    ("decimal_de_200000_digitos", lambda: Decimal("9" * 200000)),
    ("entero_10_a_la_1000", lambda: 10**1000),
    ("decimal_1E_mas_41", lambda: Decimal("1E+41")),
    ("decimal_negativo_1E_mas_41", lambda: Decimal("-1E+41")),
    ("decimal_1E_menos_41", lambda: Decimal("1E-41")),
    ("cero_0E_mas_41", lambda: Decimal("0E+41")),
    ("cero_0E_menos_41", lambda: Decimal("0E-41")),
    ("cadena_de_42_digitos_enteros", lambda: "9" * 42),
    ("cadena_con_41_decimales", lambda: "0." + "0" * 40 + "1"),
    ("entero_10_a_la_41", lambda: 10**41),
]

_EN_EL_LIMITE: list[tuple[str, Callable[[], str | int | Decimal]]] = [
    ("decimal_1E_mas_40", lambda: Decimal("1E+40")),
    ("decimal_1E_menos_40", lambda: Decimal("1E-40")),
    ("cero_0E_mas_40", lambda: Decimal("0E+40")),
    ("cero_0E_menos_40", lambda: Decimal("0E-40")),
    ("cadena_de_41_digitos_enteros", lambda: "9" * 41),
    ("cadena_con_40_decimales", lambda: "0." + "0" * 39 + "1"),
    ("entero_10_a_la_40", lambda: 10**40),
]


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "fabrica", [caso[1] for caso in _FUERA_DE_RANGO], ids=[caso[0] for caso in _FUERA_DE_RANGO]
)
def test_tkt004_ca01_rechaza_exponente_fuera_de_rango_rapido_y_con_mensaje_corto(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
    fabrica: Callable[[], str | int | Decimal],
) -> None:
    """TC-07c · CA-1 esc. 5, M-01 — magnitud de 10^41 o más, o más de 40 decimales: ValueError en menos de 1 s y sin volcar el valor."""
    valor = fabrica()

    inicio = time.perf_counter()
    with pytest.raises(ValueError, match=tipo.__name__) as excepcion:
        tipo(valor)
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 1.0
    assert len(str(excepcion.value)) < 300


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "cadena",
    ["x" * 200000, "1" * 100000 + ".5x", " " * 200000],
    ids=["x_200000", "numero_largo_con_basura", "espacios_200000"],
)
def test_tkt004_ca01_cadena_malformada_larga_no_se_vuelca_en_el_mensaje(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje], cadena: str
) -> None:
    """TC-07d · CA-1 esc. 5, M-01 — el mensaje trunca el repr de la cadena recibida a unos 60 caracteres."""
    with pytest.raises(ValueError, match=tipo.__name__) as excepcion:
        tipo(cadena)

    assert len(str(excepcion.value)) < 300


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "fabrica", [caso[1] for caso in _EN_EL_LIMITE], ids=[caso[0] for caso in _EN_EL_LIMITE]
)
def test_tkt004_ca01_admite_exponente_en_el_limite(
    tipo: type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje],
    fabrica: Callable[[], str | int | Decimal],
) -> None:
    """TC-07e · CA-1 esc. 1, M-01 — el borde de aceptación: exponente ajustado 40 y exponente -40 entran tal cual."""
    origen = fabrica()
    esperado = origen if isinstance(origen, Decimal) else Decimal(origen)

    construido = tipo(origen)

    assert construido.valor.as_tuple() == esperado.as_tuple()


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca02_orden_total_dentro_de_cada_tipo(
    tipo: Callable[
        [str], Any
    ],  # Any: mypy no ve que ambos operandos son del mismo tipo de la unión
) -> None:
    """TC-11b · CA-2 esc. 2 — <, <=, >, >=, sorted y max comparan el valor numérico, no el texto."""
    nueve = tipo("9")
    diez = tipo("10")
    menor = tipo("-3")

    assert nueve < diez
    assert nueve <= diez
    assert diez > nueve
    assert diez >= nueve
    assert not diez < nueve
    assert not diez <= nueve
    assert not nueve > diez
    assert not nueve >= diez
    assert menor < nueve
    assert sorted([diez, menor, nueve]) == [menor, nueve, diez]
    assert max([nueve, diez, menor]) == diez
    assert min([nueve, diez, menor]) == menor


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca02_orden_e_igualdad_no_dependen_de_la_escala(
    tipo: Callable[
        [str], Any
    ],  # Any: mypy no ve que ambos operandos son del mismo tipo de la unión
) -> None:
    """TC-11c · CA-2 esc. 2 — 1.0 y 1.0000 son el mismo valor: iguales, ni menor ni mayor, y <= y >= valen."""
    corto = tipo("1.0")
    largo = tipo("1.0000")

    assert corto == largo
    assert corto <= largo
    assert corto >= largo
    assert not corto < largo
    assert not corto > largo
    assert max([corto, largo]) == corto
