"""Regla pura del límite de intentos (TKT-057, fila 3): TC-01 a TC-08, más TC-08a y TC-08b.

Sin Docker. Prueba `cimenta/identidad/dominio/limite_intentos.py` (`RNF-04`): `EstadoLimite`,
`instante_de_disparo` y `evaluar_limite`. El dominio decide con enteros: cada instante es un número
de microsegundos relativo a `ahora`, que vale 0 (los fallos pasados son negativos o cero), y la
ventana es de 15 minutos expresada también en microsegundos. La hora y la conversión desde
`datetime` las pone `aplicacion/`.

Semántica que fijan estos casos (diseño de TKT-057, sección «Dominio»):

- La ventana de un disparo es estricta por abajo e inclusiva por arriba: cuentan los fallos `g` con
  `f - ventana < g <= f`.
- Un disparo `d` está vigente si `d + ventana > 0`; en `d + ventana == 0` el bloqueo ya venció.
- `reintentar_en_s` es el techo en segundos de `max(d) + ventana` sobre los disparos vigentes.
- Solo los fallos posteriores (`>`) al último éxito de la cuenta cuentan para la cuenta; el origen
  no se reinicia con ningún éxito.

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: mientras el
archivo no exista, cada caso falla por sí solo con el `ModuleNotFoundError` de
`cimenta.identidad.dominio.limite_intentos` (la razón esperada) y la recolección no se cae.

Ninguna de estas reglas tiene `RN-xx` en el PRD: se trazan con `CA-n`, `TC-nn`, `D-n` y `RNF-04`.
"""

from __future__ import annotations

import pytest

SEGUNDO = 1_000_000
MINUTO = 60 * SEGUNDO
VENTANA = 15 * MINUTO
UMBRAL_CUENTA = 5
UMBRAL_ORIGEN = 20


def _racha(ultimo: int, cantidad: int, *, separacion: int = SEGUNDO) -> list[int]:
    """`cantidad` instantes separados por `separacion` µs, en orden cronológico, el último en `ultimo`."""
    return [ultimo - separacion * (cantidad - 1 - i) for i in range(cantidad)]


def _evaluar(
    *,
    fallos_cuenta: list[int] | None = None,
    ultimo_exito_cuenta: int | None = None,
    fallos_origen: list[int] | None = None,
):
    from cimenta.identidad.dominio.limite_intentos import evaluar_limite

    return evaluar_limite(
        fallos_cuenta=fallos_cuenta or [],
        ultimo_exito_cuenta=ultimo_exito_cuenta,
        fallos_origen=fallos_origen or [],
        umbral_cuenta=UMBRAL_CUENTA,
        umbral_origen=UMBRAL_ORIGEN,
        ventana=VENTANA,
    )


def test_tkt057_ca01_tc01_cinco_fallos_en_la_ventana_disparan_en_el_quinto() -> None:
    """CA-1 · TC-01 · RNF-04 — cinco fallos dentro de la ventana: el disparo es el instante del quinto.

    Los fallos llegan desordenados: la función los ordena, el quinto es el más reciente (0).
    """
    from cimenta.identidad.dominio.limite_intentos import instante_de_disparo

    fallos = [-2 * SEGUNDO, -4 * SEGUNDO, 0, -1 * SEGUNDO, -3 * SEGUNDO]

    assert instante_de_disparo(fallos, umbral=UMBRAL_CUENTA, ventana=VENTANA) == 0


def test_tkt057_ca01_tc02_cuatro_fallos_no_disparan() -> None:
    """CA-1 · TC-02 · RNF-04 — rechazo: cuatro fallos no abren el bloqueo, ni en la función ni en el estado.

    Comprueba el dato: no hay instante de disparo y el estado no reporta bloqueo ni tiempo de espera.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite, instante_de_disparo

    fallos = _racha(0, 4)

    assert instante_de_disparo(fallos, umbral=UMBRAL_CUENTA, ventana=VENTANA) is None
    estado = _evaluar(fallos_cuenta=fallos)
    assert estado == EstadoLimite(disparo_cuenta=None, disparo_origen=None, reintentar_en_s=0)
    assert estado.bloqueado is False


def test_tkt057_ca01_tc03_primer_fallo_exactamente_una_ventana_antes_no_cuenta() -> None:
    """CA-1 · TC-03 · RNF-04 — borde: el límite inferior de la ventana es estricto.

    Con el primero de cinco fallos a exactamente `ventana` del quinto solo cuentan cuatro: no hay
    disparo. Un microsegundo más cerca, los cinco caben y el disparo es el quinto.
    """
    from cimenta.identidad.dominio.limite_intentos import instante_de_disparo

    en_el_limite = [-VENTANA, -3 * MINUTO, -2 * MINUTO, -1 * MINUTO, 0]
    un_microsegundo_dentro = [-VENTANA + 1, -3 * MINUTO, -2 * MINUTO, -1 * MINUTO, 0]

    assert instante_de_disparo(en_el_limite, umbral=UMBRAL_CUENTA, ventana=VENTANA) is None
    assert instante_de_disparo(un_microsegundo_dentro, umbral=UMBRAL_CUENTA, ventana=VENTANA) == 0


def test_tkt057_ca03_tc04_el_bloqueo_vence_exactamente_a_la_ventana() -> None:
    """CA-3 · TC-04 · RNF-04 — borde: vigente a `ventana - 1 µs` (1 s de espera), vencido a `ventana`.

    Con el disparo hace `ventana - 1 µs` quedan 1 µs de bloqueo y el techo da `reintentar_en_s = 1`.
    Con el disparo hace exactamente `ventana` el bloqueo ya venció: ningún disparo ni espera.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    disparo_casi_vencido = -(VENTANA - 1)
    casi_vencido = _evaluar(fallos_cuenta=_racha(disparo_casi_vencido, UMBRAL_CUENTA))
    disparo_vencido = -VENTANA
    vencido = _evaluar(fallos_cuenta=_racha(disparo_vencido, UMBRAL_CUENTA))

    assert casi_vencido == EstadoLimite(
        disparo_cuenta=disparo_casi_vencido, disparo_origen=None, reintentar_en_s=1
    )
    assert casi_vencido.bloqueado is True
    assert vencido == EstadoLimite(disparo_cuenta=None, disparo_origen=None, reintentar_en_s=0)
    assert vencido.bloqueado is False


def test_tkt057_ca05_tc05_un_exito_reinicia_el_recuento_de_la_cuenta() -> None:
    """CA-5 · TC-05 · RNF-04 — rechazo: cuatro fallos, un éxito y un fallo no bloquean.

    Sin el filtro por último éxito los cinco fallos caben en la ventana y la cuenta quedaría
    bloqueada con 900 s de espera; con él, solo el último fallo cuenta.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    fallos_antes_del_exito = _racha(-2 * SEGUNDO, 4)
    exito = -1 * SEGUNDO
    fallo_despues = 0

    estado = _evaluar(
        fallos_cuenta=[*fallos_antes_del_exito, fallo_despues], ultimo_exito_cuenta=exito
    )

    assert estado == EstadoLimite(disparo_cuenta=None, disparo_origen=None, reintentar_en_s=0)
    assert estado.bloqueado is False


def test_tkt057_ca06_tc06_el_exito_no_reinicia_el_recuento_del_origen() -> None:
    """CA-6 · TC-06 · D-3 · RNF-04 — veinte fallos de origen con un éxito de la cuenta entre ellos bloquean.

    El último éxito de la cuenta (a mitad de la racha) solo filtra los fallos de la cuenta: el
    origen sigue en 20 fallos, el disparo es el último y la espera es la ventana completa (900 s).
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    fallos_origen = _racha(0, UMBRAL_ORIGEN)
    exito_a_mitad = fallos_origen[UMBRAL_ORIGEN // 2] + 1

    estado = _evaluar(fallos_origen=fallos_origen, ultimo_exito_cuenta=exito_a_mitad)

    assert estado == EstadoLimite(disparo_cuenta=None, disparo_origen=0, reintentar_en_s=900)
    assert estado.bloqueado is True


def test_tkt057_ca06_tc07_con_cuenta_y_origen_bloqueados_se_espera_el_mayor_plazo() -> None:
    """CA-1 · CA-6 · TC-07 · RNF-04 — dos bloqueos vigentes: `reintentar_en_s` es el del que vence más tarde.

    La cuenta se bloqueó hace 10 min (quedan 300 s) y el origen hace 1 min (quedan 840 s): la
    respuesta lleva 840 y ambos disparos aparecen en el estado.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    disparo_cuenta = -10 * MINUTO
    disparo_origen = -1 * MINUTO

    estado = _evaluar(
        fallos_cuenta=_racha(disparo_cuenta, UMBRAL_CUENTA),
        fallos_origen=_racha(disparo_origen, UMBRAL_ORIGEN),
    )

    assert estado == EstadoLimite(
        disparo_cuenta=disparo_cuenta, disparo_origen=disparo_origen, reintentar_en_s=840
    )
    assert estado.bloqueado is True


@pytest.mark.parametrize(
    ("disparo", "esperado"),
    [
        pytest.param(0, 900, id="disparo-en-ahora"),
        pytest.param(-1, 900, id="un-microsegundo-despues-sigue-900-por-el-techo"),
        pytest.param(-SEGUNDO, 899, id="un-segundo-exacto-no-redondea-hacia-arriba"),
        pytest.param(-(VENTANA - 1), 1, id="queda-un-microsegundo-y-es-un-segundo"),
    ],
)
def test_tkt057_ca01_tc08_reintentar_en_s_es_el_techo_en_segundos_y_nunca_cero(
    disparo: int, esperado: int
) -> None:
    """CA-1 · TC-08 · RNF-04 — borde: con el disparo en `ahora` la espera es 900 s y, mientras hay bloqueo, nunca 0.

    La espera es el techo de los segundos que quedan, así que ningún bloqueo vigente se anuncia
    con `reintentar_en_s = 0` y `Retry-After` nunca invita a reintentar antes de tiempo.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    estado = _evaluar(fallos_cuenta=_racha(disparo, UMBRAL_CUENTA))

    assert estado == EstadoLimite(
        disparo_cuenta=disparo, disparo_origen=None, reintentar_en_s=esperado
    )
    assert estado.bloqueado is True


def test_tkt057_ca03_tc08a_un_disparo_de_hace_mas_de_una_ventana_no_bloquea() -> None:
    """CA-3 · TC-08a · RNF-04 — rechazo: cinco fallos que ya vencieron no bloquean la cuenta.

    Hay cinco fallos de la cuenta con el último hace `ventana + 1 s`: el umbral se alcanzó, pero el
    bloqueo caducó solo. El estado no reporta disparo, ni espera, ni bloqueo.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    disparo_viejo = -(VENTANA + SEGUNDO)

    estado = _evaluar(fallos_cuenta=_racha(disparo_viejo, UMBRAL_CUENTA))

    assert estado == EstadoLimite(disparo_cuenta=None, disparo_origen=None, reintentar_en_s=0)
    assert estado.bloqueado is False


def test_tkt057_ca05_tc08b_el_fallo_en_el_instante_del_exito_no_cuenta() -> None:
    """CA-5 · TC-08b · RNF-04 — rechazo: solo cuentan los fallos estrictamente posteriores al último éxito.

    Cinco fallos recientes, el último en el mismo instante que el éxito de la cuenta: quedan cuatro
    tras el filtro (`f > ultimo_exito`), no se alcanza el umbral y la cuenta no está bloqueada. Si
    el filtro fuera `>=` o faltara, serían cinco y la espera, 900 s.
    """
    from cimenta.identidad.dominio.limite_intentos import EstadoLimite

    fallos = _racha(-1 * SEGUNDO, UMBRAL_CUENTA)

    estado = _evaluar(fallos_cuenta=fallos, ultimo_exito_cuenta=fallos[-1])

    assert estado == EstadoLimite(disparo_cuenta=None, disparo_origen=None, reintentar_en_s=0)
    assert estado.bloqueado is False
