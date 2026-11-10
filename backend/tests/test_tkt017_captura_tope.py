"""Regla pura de la captura del tope, TKT-017c (CA-C2 a CA-C5 · PA-03 · RN-03 · RN-04): `evaluar_captura_tope`.

Pytest puro, sin Docker ni base: la regla decide solo con los hechos que recibe (el tope anterior si lo
hay, el tope nuevo, el importe de venta del tipo de partida, el motivo y si se confirmó que el tope supera
la venta) y devuelve la admisión o la causa del rechazo. Los casos de uso y la API comprueban el contrato
de error completo contra PostgreSQL; aquí se ancla la decisión y, sobre todo, su precedencia: primero el
tope superior a la venta sin confirmar y después el motivo obligatorio.

Rojo esperado: el módulo `cimenta.presupuesto.dominio.captura_tope` aún no existe, así que la colección
falla con `ModuleNotFoundError` (desviación R-2, ya aceptada por la persona dueña). Mutantes que debe
poner en rojo: `>` por `>=` en la comparación con la venta (M-C1) y tratar como recaptura solo la subida
del tope (M-C2).
"""

from __future__ import annotations

import pytest
from cimenta.presupuesto.dominio.captura_tope import (
    CapturaAdmitida,
    CapturaRechazada,
    CausaRechazoCaptura,
    evaluar_captura_tope,
)

from tipos_base import Dinero

VENTA = Dinero("480000.0000")
SUPERIOR = Dinero("500000.0000")
MOTIVO = "Subcontrato de bastidor más caro"
MOTIVOS_AUSENTES = [None, "", "   "]


def _rechazo(resultado: object) -> CapturaRechazada:
    assert isinstance(resultado, CapturaRechazada), resultado
    return resultado


def test_hdu001_esc15_dominio_primera_captura_sin_motivo_se_admite() -> None:
    """HDU-001 esc. 15 · CA-C2 · PA-03 — la primera captura por debajo de la venta se admite sin motivo."""
    resultado = evaluar_captura_tope(
        tope_anterior=None,
        tope_nuevo=Dinero("450000.0000"),
        importe_venta=VENTA,
        motivo=None,
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=False)


def test_hdu001_esc22_dominio_recaptura_con_motivo_se_admite() -> None:
    """HDU-001 esc. 22 · CA-C4 · RN-03 · RN-04 — recapturar con motivo se admite y es recaptura."""
    resultado = evaluar_captura_tope(
        tope_anterior=Dinero("450000.0000"),
        tope_nuevo=Dinero("470000.0000"),
        importe_venta=VENTA,
        motivo="Se subestimó el bastidor de los cubos de escalera",
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=True)


@pytest.mark.parametrize("motivo", MOTIVOS_AUSENTES)
def test_hdu001_esc23_dominio_recaptura_sin_motivo(motivo: str | None) -> None:
    """HDU-001 esc. 23 · CA-C5 · RN-04 — una recaptura sin motivo (nulo, vacío o en blanco) se rechaza."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=Dinero("450000.0000"),
            tope_nuevo=Dinero("470000.0000"),
            importe_venta=VENTA,
            motivo=motivo,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.MOTIVO_OBLIGATORIO


def test_hdu001_esc17_dominio_tope_superior_sin_confirmar() -> None:
    """HDU-001 esc. 17 · CA-C3 esc. 1 · RN-03 — un tope mayor que la venta sin confirmar se rechaza."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=None,
            tope_nuevo=SUPERIOR,
            importe_venta=VENTA,
            motivo=None,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR


def test_hdu001_esc17_dominio_tope_superior_sin_confirmar_se_rechaza_aunque_traiga_motivo() -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — el motivo no sustituye la confirmación de que supera la venta."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=None,
            tope_nuevo=SUPERIOR,
            importe_venta=VENTA,
            motivo=MOTIVO,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR


@pytest.mark.parametrize("motivo", MOTIVOS_AUSENTES)
def test_hdu001_esc17_dominio_confirmacion_sin_motivo(motivo: str | None) -> None:
    """HDU-001 esc. 17 · CA-C3 esc. 2 · RN-03 — confirmar que supera la venta sin motivo se rechaza."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=None,
            tope_nuevo=SUPERIOR,
            importe_venta=VENTA,
            motivo=motivo,
            confirmar_superior_a_venta=True,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.MOTIVO_OBLIGATORIO


def test_hdu001_esc17_dominio_tope_superior_confirmado_con_motivo() -> None:
    """HDU-001 esc. 17 · CA-C3 esc. 3 · RN-03 — superar la venta confirmándolo y con motivo se admite."""
    resultado = evaluar_captura_tope(
        tope_anterior=None,
        tope_nuevo=SUPERIOR,
        importe_venta=VENTA,
        motivo=MOTIVO,
        confirmar_superior_a_venta=True,
    )

    assert resultado == CapturaAdmitida(es_recaptura=False)


def test_hdu001_esc17_dominio_tope_igual_a_la_venta_no_pide_confirmacion() -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — un tope exactamente igual a la venta no supera nada (mata M-C1)."""
    resultado = evaluar_captura_tope(
        tope_anterior=None,
        tope_nuevo=Dinero("480000.0000"),
        importe_venta=VENTA,
        motivo=None,
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=False)


def test_hdu001_esc22_dominio_bajar_el_tope_tambien_es_recaptura() -> None:
    """HDU-001 esc. 22 · CA-C4 esc. 2 · RN-03 — bajar el tope con motivo es recaptura igual que subirlo (mata M-C2)."""
    resultado = evaluar_captura_tope(
        tope_anterior=Dinero("450000.0000"),
        tope_nuevo=Dinero("440000.0000"),
        importe_venta=VENTA,
        motivo="Se renegoció el subcontrato",
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=True)


def test_hdu001_esc23_dominio_bajar_el_tope_sin_motivo_se_rechaza() -> None:
    """HDU-001 esc. 23 · CA-C5 · RN-04 — bajar el tope sin motivo exige motivo igual que subirlo (M-C2)."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=Dinero("450000.0000"),
            tope_nuevo=Dinero("440000.0000"),
            importe_venta=VENTA,
            motivo=None,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.MOTIVO_OBLIGATORIO


def test_hdu001_esc22_dominio_recapturar_el_mismo_valor_es_recaptura() -> None:
    """HDU-001 esc. 22 · CA-C4 esc. 3 · RN-03 — recapturar el mismo valor con motivo sigue siendo recaptura."""
    resultado = evaluar_captura_tope(
        tope_anterior=Dinero("470000.0000"),
        tope_nuevo=Dinero("470000.0000"),
        importe_venta=VENTA,
        motivo=MOTIVO,
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=True)


@pytest.mark.parametrize("anterior", [None, Dinero("450000.0000")])
def test_hdu001_esc17_dominio_sin_confirmar_y_sin_motivo_manda_la_confirmacion(
    anterior: Dinero | None,
) -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — precedencia: superior sin confirmar y sin motivo es la causa de la confirmación."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=anterior,
            tope_nuevo=SUPERIOR,
            importe_venta=VENTA,
            motivo=None,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR


def test_hdu001_esc17_dominio_diferencia_de_una_diezmilesima_ya_es_superior() -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — la comparación con la venta es exacta, sin redondeo."""
    resultado = _rechazo(
        evaluar_captura_tope(
            tope_anterior=None,
            tope_nuevo=Dinero("480000.0001"),
            importe_venta=VENTA,
            motivo=None,
            confirmar_superior_a_venta=False,
        )
    )

    assert resultado.causa == CausaRechazoCaptura.TOPE_SUPERIOR_SIN_CONFIRMAR


def test_hdu001_esc17_dominio_una_diezmilesima_bajo_la_venta_no_pide_confirmacion() -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — la comparación exacta también deja pasar lo que no supera la venta."""
    resultado = evaluar_captura_tope(
        tope_anterior=None,
        tope_nuevo=Dinero("479999.9999"),
        importe_venta=VENTA,
        motivo=None,
        confirmar_superior_a_venta=False,
    )

    assert resultado == CapturaAdmitida(es_recaptura=False)


def test_hdu001_esc17_dominio_confirmar_sin_superar_no_exige_motivo_en_primera_captura() -> None:
    """HDU-001 esc. 17 · CA-C2 · RN-03 — confirmar sin superar la venta no cambia nada: el motivo no se exige."""
    resultado = evaluar_captura_tope(
        tope_anterior=None,
        tope_nuevo=Dinero("450000.0000"),
        importe_venta=VENTA,
        motivo=None,
        confirmar_superior_a_venta=True,
    )

    assert resultado == CapturaAdmitida(es_recaptura=False)
