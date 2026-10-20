"""Límites de entrada de los tipos base (TKT-004, ciclo 2 de corrección): TC-07f a TC-07l.

Sin Docker (CA-13). Complementan a TC-07c, TC-07d y TC-07e de `test_tipos_base_construccion.py`:
aquellas fijan que la entrada fuera de rango se rechaza rápido y con mensaje corto; estas fijan
que el mensaje **distingue la causa** (magnitud o decimales), que un entero enorme no filtra el
mensaje de CPython y que las dos guardas previas (100 caracteres de cadena, 140 bits de entero)
tienen su frontera comprobada por ambos lados.

Las palabras que el mensaje debe contener quedan fijadas aquí: «magnitud», «decimales» y
«100 caracteres».
"""

import time
from collections.abc import Callable
from decimal import Decimal

import pytest

from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

TIPOS = (Dinero, Cantidad, Rendimiento, Porcentaje)
Tipo = type[Dinero] | type[Cantidad] | type[Rendimiento] | type[Porcentaje]

# Entradas cuyo adjusted() pasa de 40: la causa es la magnitud.
_POR_MAGNITUD: list[tuple[str, Callable[[], str | int | Decimal]]] = [
    ("cadena_de_42_nueves", lambda: "9" * 42),
    ("cadena_negativa_de_42_nueves", lambda: "-" + "9" * 42),
    ("decimal_1E_mas_41", lambda: Decimal("1E+41")),
    ("cero_0E_mas_41", lambda: Decimal("0E+41")),
    ("entero_10_a_la_41", lambda: 10**41),
    ("entero_10_a_la_1000", lambda: 10**1000),
]

# Entradas cuyo exponente baja de -40: la causa son los decimales.
_POR_DECIMALES: list[tuple[str, Callable[[], str | int | Decimal]]] = [
    ("cadena_con_41_decimales", lambda: "0." + "0" * 40 + "1"),
    ("cadena_de_1_con_41_decimales", lambda: "1." + "0" * 41),
    ("decimal_1E_menos_41", lambda: Decimal("1E-41")),
    ("cero_0E_menos_41", lambda: Decimal("0E-41")),
]


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "fabrica", [caso[1] for caso in _POR_MAGNITUD], ids=[caso[0] for caso in _POR_MAGNITUD]
)
def test_tkt004_ca01_el_rechazo_por_magnitud_lo_dice(
    tipo: Tipo, fabrica: Callable[[], str | int | Decimal]
) -> None:
    """TC-07f · CA-1 esc. 5, M-01 — pasar de 10^41 es un problema de «magnitud», no de «decimales»."""
    with pytest.raises(ValueError, match=tipo.__name__) as excepcion:
        tipo(fabrica())

    mensaje = str(excepcion.value)
    assert "magnitud" in mensaje
    assert "decimales" not in mensaje


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "fabrica", [caso[1] for caso in _POR_DECIMALES], ids=[caso[0] for caso in _POR_DECIMALES]
)
def test_tkt004_ca01_el_rechazo_por_decimales_lo_dice(
    tipo: Tipo, fabrica: Callable[[], str | int | Decimal]
) -> None:
    """TC-07g · CA-1 esc. 5, M-01 — pasar de 40 decimales es un problema de «decimales», no de «magnitud»."""
    with pytest.raises(ValueError, match=tipo.__name__) as excepcion:
        tipo(fabrica())

    mensaje = str(excepcion.value)
    assert "decimales" in mensaje
    assert "magnitud" not in mensaje


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize("signo", [1, -1], ids=["positivo", "negativo"])
@pytest.mark.parametrize("digitos", [4400, 5000, 100_000], ids=["4400", "5000", "100000"])
def test_tkt004_ca01_entero_enorme_no_filtra_el_mensaje_de_cpython(
    tipo: Tipo, signo: int, digitos: int
) -> None:
    """TC-07h · CA-1 esc. 5, M-01 — un int de más de 4300 dígitos da el ValueError del tipo, no el de CPython."""
    enorme = signo * 10**digitos

    with pytest.raises(ValueError) as excepcion:  # noqa: PT011 — el mensaje se comprueba abajo, cláusula por cláusula
        tipo(enorme)

    mensaje = str(excepcion.value)
    assert tipo.__name__ in mensaje
    assert "4300" not in mensaje
    assert "Exceeds the limit" not in mensaje
    assert len(mensaje) < 300


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_cadena_de_cien_caracteres_se_admite_y_vale_lo_mismo(tipo: Tipo) -> None:
    """TC-07i · CA-1 esc. 1, M-01 — frontera de aceptación de la guarda de largo: 100 caracteres entran."""
    cadena = "0" * 95 + "1.234"
    assert len(cadena) == 100

    construido = tipo(cadena)

    assert construido.valor == Decimal("1.234")


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
def test_tkt004_ca01_cadena_negativa_de_cien_caracteres_se_admite(tipo: Tipo) -> None:
    """TC-07j · CA-1 esc. 1, M-01 — el signo cuenta dentro de los 100 caracteres y aun así entra."""
    cadena = "-" + "0" * 94 + "1.234"
    assert len(cadena) == 100

    construido = tipo(cadena)

    assert construido.valor == Decimal("-1.234")


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize(
    "cadena",
    ["0" * 101, "0" * 96 + "1.234", "-" + "0" * 95 + "1.234", "1." + "0" * 99],
    ids=["ceros_101", "valor_legitimo_de_101", "negativo_de_101", "uno_con_99_ceros_decimales"],
)
def test_tkt004_ca01_cadena_de_ciento_un_caracteres_se_rechaza_y_dice_el_limite(
    tipo: Tipo, cadena: str
) -> None:
    """TC-07k · CA-1 esc. 5, M-01 — frontera de rechazo: 101 caracteres no entran aunque valgan poco."""
    assert len(cadena) == 101

    with pytest.raises(ValueError, match=tipo.__name__) as excepcion:
        tipo(cadena)

    assert "100 caracteres" in str(excepcion.value)
    assert len(str(excepcion.value)) < 300


@pytest.mark.parametrize("tipo", TIPOS, ids=lambda tipo: tipo.__name__)
@pytest.mark.parametrize("bits", [2_000_000, 4_000_000], ids=["2M_bits", "4M_bits"])
def test_tkt004_ca01_entero_de_millones_de_bits_se_rechaza_sin_construir_un_decimal(
    tipo: Tipo, bits: int
) -> None:
    """TC-07l · CA-1 esc. 5, M-01 — la guarda de 140 bits corta antes de la conversión cuadrática a Decimal."""
    enorme = 1 << bits  # se construye fuera del cronómetro: lo medido es el rechazo

    inicio = time.perf_counter()
    with pytest.raises(ValueError):  # noqa: PT011 — el mensaje lo fija TC-07h; aquí solo cuenta el tiempo
        tipo(enorme)
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 1.0
