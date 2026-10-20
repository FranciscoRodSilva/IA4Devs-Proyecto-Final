"""Redondeo explícito y serialización de los tipos base (TKT-004, fila 3): TC-50 a TC-61.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-13). Todo importe se construye desde cadena. El redondeo es `ROUND_HALF_UP` (asumido,
PA-T5) y `serializar` no redondea nunca: rechaza lo que no se ha cuantizado (PA-T7).
"""

import json
from decimal import Decimal

import pytest

from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento


def test_tkt004_ca05_cuantizar_a_la_escala_de_cada_tipo() -> None:
    """TC-50 · CA-5 esc. 1 — cada tipo se lleva a la escala de su columna y el original no cambia."""
    dinero = Dinero("2.12345")
    cantidad = Cantidad("2.12345")
    rendimiento = Rendimiento("2.1234565")
    porcentaje = Porcentaje("0.1234565")

    cuantizado_dinero = dinero.cuantizar()
    cuantizada_cantidad = cantidad.cuantizar()
    cuantizado_rendimiento = rendimiento.cuantizar()
    cuantizado_porcentaje = porcentaje.cuantizar()

    assert type(cuantizado_dinero) is Dinero
    assert cuantizado_dinero.valor == Decimal("2.1235")
    assert cuantizado_dinero.valor.as_tuple().exponent == -4
    assert type(cuantizada_cantidad) is Cantidad
    assert cuantizada_cantidad.valor == Decimal("2.1235")
    assert cuantizada_cantidad.valor.as_tuple().exponent == -4
    assert type(cuantizado_rendimiento) is Rendimiento
    assert cuantizado_rendimiento.valor == Decimal("2.123457")
    assert cuantizado_rendimiento.valor.as_tuple().exponent == -6
    assert type(cuantizado_porcentaje) is Porcentaje
    assert cuantizado_porcentaje.valor == Decimal("0.123457")
    assert cuantizado_porcentaje.valor.as_tuple().exponent == -6
    assert dinero.valor == Decimal("2.12345")
    assert cantidad.valor == Decimal("2.12345")
    assert rendimiento.valor == Decimal("2.1234565")
    assert porcentaje.valor == Decimal("0.1234565")


@pytest.mark.parametrize(
    ("original", "esperado"),
    [("0.00005", "0.0001"), ("-0.00005", "-0.0001")],
    ids=["empate_positivo", "empate_negativo"],
)
def test_tkt004_ca05_empate_se_aleja_del_cero(original: str, esperado: str) -> None:
    """TC-51 · CA-5 esc. 2 — ROUND_HALF_UP: el empate se redondea alejándose del cero."""
    assert Dinero(original).cuantizar().valor == Decimal(esperado)


def test_tkt004_ca05_ya_en_escala_no_cambia() -> None:
    """TC-52 · CA-5 esc. 3 — un valor que ya está en escala sale igual."""
    cuantizado = Dinero("12.3400").cuantizar()

    assert type(cuantizado) is Dinero
    assert cuantizado == Dinero("12.34")
    assert cuantizado.valor == Decimal("12.3400")


@pytest.mark.parametrize(
    ("tipo", "valor", "precision"),
    [
        (Dinero, "100000000000000.0000", r"NUMERIC\(18,4\)"),
        (Porcentaje, "1000.000000", r"NUMERIC\(9,6\)"),
        (Cantidad, "10000000000", r"NUMERIC\(14,4\)"),
        (Rendimiento, "1000000000000", r"NUMERIC\(18,6\)"),
        (Dinero, "99999999999999.99995", r"NUMERIC\(18,4\)"),
        (Dinero, "-100000000000000.0000", r"NUMERIC\(18,4\)"),
    ],
    ids=[
        "dinero_15_enteros",
        "porcentaje_4_enteros",
        "cantidad_11_enteros",
        "rendimiento_13_enteros",
        "dinero_el_redondeo_lo_lleva_a_15_enteros",
        "dinero_negativo_15_enteros",
    ],
)
def test_tkt004_ca05_no_cabe_en_la_columna(
    tipo: type[Dinero | Cantidad | Rendimiento | Porcentaje], valor: str, precision: str
) -> None:
    """TC-53 · CA-5 esc. 4 — un valor que no cabe en la columna no se trunca: falla e indica la precisión."""
    with pytest.raises(ValueError, match=precision):
        tipo(valor).cuantizar()


@pytest.mark.parametrize(
    ("tipo", "maximo"),
    [
        (Dinero, "99999999999999.9999"),
        (Cantidad, "9999999999.9999"),
        (Rendimiento, "999999999999.999999"),
        (Porcentaje, "999.999999"),
    ],
    ids=["dinero", "cantidad", "rendimiento", "porcentaje"],
)
def test_tkt004_ca05_el_maximo_que_cabe_se_cuantiza(
    tipo: type[Dinero | Cantidad | Rendimiento | Porcentaje], maximo: str
) -> None:
    """TC-53b · CA-5 esc. 4 — el borde: el valor máximo de cada columna sí se cuantiza, y negativo también."""
    assert tipo(maximo).cuantizar().valor == Decimal(maximo)
    assert tipo(f"-{maximo}").cuantizar().valor == Decimal(f"-{maximo}")


def test_tkt004_ca05_nada_cuantiza_por_su_cuenta() -> None:
    """TC-54 · CA-5 esc. 5 — las operaciones conservan más decimales que la escala de su tipo."""
    producto_cantidad = Cantidad("3.1234") * Rendimiento("0.673400")
    producto_dinero = Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857"))

    assert producto_cantidad.valor.as_tuple().exponent == -10
    assert producto_dinero.valor.as_tuple().exponent == -7


def test_tkt004_ca03_cuantizar_una_sola_vez_al_final() -> None:
    """TC-55 · CA-3 esc. 4 — el redondeo intermedio cambia el importe: se cuantiza una vez, al final."""
    una_sola_vez = (Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857"))).cuantizar()
    intermedio = (
        Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857")).cuantizar()
    ).cuantizar()

    assert una_sola_vez == Dinero("1000.4990")
    assert intermedio == Dinero("1000.5000")
    assert una_sola_vez != intermedio


def test_tkt004_ca06_serializa_con_la_escala_de_la_columna() -> None:
    """TC-56 · CA-6 esc. 1 — cada tipo da una cadena de escala completa, y JSON la lleva entre comillas."""
    importe = Dinero("1234.5").serializar()
    cantidad = Cantidad("8").serializar()
    rendimiento = Rendimiento("0.6734").serializar()
    porcentaje = Porcentaje("0.05").serializar()

    assert importe == "1234.5000"
    assert cantidad == "8.0000"
    assert rendimiento == "0.673400"
    assert porcentaje == "0.050000"
    assert all(type(cadena) is str for cadena in (importe, cantidad, rendimiento, porcentaje))
    assert '"1234.5000"' in json.dumps({"importe": importe})


def test_tkt004_ca06_sin_redondeo_ni_notacion_cientifica() -> None:
    """TC-57 · CA-6 esc. 2 — la cadena es llana, sin exponente, aun con valores muy pequeños o muy largos."""
    cero = Dinero("0.00000001").cuantizar().serializar()
    largo = Dinero("123456789012.3456789").cuantizar().serializar()
    minimo = Porcentaje("0.000001").serializar()

    assert cero == "0.0000"
    assert largo == "123456789012.3457"
    assert minimo == "0.000001"
    assert all("E" not in cadena and "e" not in cadena for cadena in (cero, largo, minimo))


def test_tkt004_ca06_cero_negativo_sin_signo() -> None:
    """TC-58 · CA-6 esc. 3 — el cero negativo se serializa sin signo, venga de donde venga."""
    directo = Dinero("-0.0000").serializar()
    cuantizado = Dinero("-0.00001").cuantizar().serializar()

    assert directo == "0.0000"
    assert cuantizado == "0.0000"


def test_tkt004_ca06_mas_decimales_que_la_escala() -> None:
    """TC-59 · CA-6 esc. 4 — serializar no redondea en silencio: un valor sin cuantizar se rechaza."""
    with pytest.raises(ValueError, match="4 decimales"):
        Dinero("1234.56789").serializar()


def test_tkt004_ca06_el_criterio_es_de_valor_no_de_exponente() -> None:
    """TC-59b · CA-6 esc. 4 — un cero de más no es un decimal de más: 1.50000 cabe en cuatro decimales."""
    assert Dinero("1.50000").serializar() == "1.5000"


@pytest.mark.parametrize(
    ("tipo", "valor"),
    [
        (Dinero, "1234.5"),
        (Dinero, "-99999999999999.9999"),
        (Cantidad, "8"),
        (Rendimiento, "0.6734"),
        (Porcentaje, "-0.05"),
    ],
    ids=["dinero", "dinero_minimo", "cantidad", "rendimiento", "porcentaje_negativo"],
)
def test_tkt004_ca06_ida_y_vuelta(
    tipo: type[Dinero | Cantidad | Rendimiento | Porcentaje], valor: str
) -> None:
    """TC-60 · CA-6 esc. 5 — la cadena serializada se lee de vuelta y recupera el mismo valor."""
    cuantizado = tipo(valor).cuantizar()

    recuperado = type(cuantizado)(cuantizado.serializar())

    assert recuperado == cuantizado


def test_tkt004_ca06_no_serializa_lo_que_no_cabe() -> None:
    """TC-61 · CA-6 esc. 6 — un valor que PostgreSQL rechazaría no se emite como cadena."""
    with pytest.raises(ValueError, match=r"NUMERIC\(18,4\)"):
        Dinero("100000000000000.0000").serializar()
