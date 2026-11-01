"""Configuración de los límites de intentos de inicio de sesión (TKT-057, fila 4, criterio S2).

TC-14 a TC-16 de `design.md`. Sin Docker: solo se lee `ConfiguracionIdentidad.desde_entorno` con un
diccionario como entorno. Los símbolos de producción se importan dentro de cada caso, para que cada
uno falle por su cuenta y la recolección no se caiga.
"""

from datetime import timedelta

import pytest

VARIABLES_DE_LIMITE = (
    "CIMENTA_LIMITE_FALLOS_CUENTA",
    "CIMENTA_LIMITE_FALLOS_ORIGEN",
    "CIMENTA_LIMITE_MINUTOS",
)


def test_tkt057_s02_limites_por_omision() -> None:
    """TC-14 · S2 — sin variables, 5 fallos por cuenta, 20 por origen y una ventana de 15 minutos."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno({})

    assert configuracion.limite_fallos_cuenta == 5
    assert configuracion.limite_fallos_origen == 20
    assert configuracion.limite_ventana == timedelta(minutes=15)
    assert type(configuracion.limite_fallos_cuenta) is int
    assert type(configuracion.limite_fallos_origen) is int


def test_tkt057_s02_limites_desde_el_entorno() -> None:
    """TC-15 · S2 — cada variable llena su campo, con el tipo y la unidad correctos."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno(
        {
            "CIMENTA_LIMITE_FALLOS_CUENTA": "3",
            "CIMENTA_LIMITE_FALLOS_ORIGEN": "40",
            "CIMENTA_LIMITE_MINUTOS": "7",
        }
    )

    assert configuracion.limite_fallos_cuenta == 3
    assert configuracion.limite_fallos_origen == 40
    assert configuracion.limite_ventana == timedelta(minutes=7)
    assert type(configuracion.limite_fallos_cuenta) is int
    assert type(configuracion.limite_fallos_origen) is int


def test_tkt057_s02_una_variable_de_limite_no_arrastra_a_las_otras() -> None:
    """TC-15 (complemento) · S2 — con una sola variable, las demás conservan su valor por omisión,
    y las cinco variables de TKT-006 no se alteran."""
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    configuracion = ConfiguracionIdentidad.desde_entorno({"CIMENTA_LIMITE_MINUTOS": "30"})

    assert configuracion.limite_ventana == timedelta(minutes=30)
    assert configuracion.limite_fallos_cuenta == 5
    assert configuracion.limite_fallos_origen == 20
    assert configuracion.caducidad_absoluta == timedelta(hours=12)
    assert configuracion.caducidad_inactividad == timedelta(minutes=30)


@pytest.mark.parametrize("valor", ["0", "-5", "abc", "1.5", "", " 30", "１２"])
@pytest.mark.parametrize("variable", VARIABLES_DE_LIMITE)
def test_tkt057_s02_limites_rechazan_valores_invalidos(variable: str, valor: str) -> None:
    """TC-16 · S2 — rechazo: un valor que no es un entero positivo en ASCII detiene el arranque.

    El mensaje nombra la variable y muestra el valor con `repr`, como en TC-15 de TKT-006.
    Un límite de 0 o negativo bloquearía a todos o a nadie: no se acepta.
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad

    with pytest.raises(ValueError) as excepcion:
        ConfiguracionIdentidad.desde_entorno({variable: valor})

    mensaje = str(excepcion.value)
    assert variable in mensaje
    assert repr(valor) in mensaje
