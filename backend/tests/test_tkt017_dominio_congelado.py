"""Regla pura del congelado, TKT-017b1 (CA-B2 y CA-B3 · RN-01): `evaluar_congelado`.

Pytest puro, sin Docker ni base: la regla decide solo con los tres hechos que recibe (el estado de la
línea base, la otra congelada vigente si la hay y el estado de la obra) y devuelve la causa con los
valores que el caso de uso vuelve contrato de error. Los casos de uso y la API ya comprueban el
contrato completo contra PostgreSQL; aquí se ancla la decisión y, sobre todo, su precedencia:
primero el estado de la línea base, después la otra congelada y al final el estado de la obra.

Nace en verde: la regla ya existe cuando se escribe este archivo (los criterios los cubría solo el
caso de uso a través de la base). Mutantes que debe poner en rojo: invertir dos comprobaciones de
`evaluar_congelado`, o aceptar un estado de la línea base o de la obra que no sea `BORRADOR` o
`PLANEACION`.
"""

from __future__ import annotations

import uuid

import pytest

from cimenta.presupuesto.dominio.congelado import (
    CausaRechazoCongelado,
    CongeladoAdmitido,
    CongeladoRechazado,
    evaluar_congelado,
)
from cimenta.presupuesto.dominio.materializacion import LineaBaseDeObra

VIGENTE = LineaBaseDeObra(id=uuid.UUID("11111111-1111-4111-8111-111111111111"), version=3)
ESTADOS_DE_OBRA_NO_ADMITIDOS = ["ACTIVA", "SUSPENDIDA", "CERRADA"]


def _rechazo(resultado: object) -> CongeladoRechazado:
    assert isinstance(resultado, CongeladoRechazado), resultado
    return resultado


def test_tkt017_cab01_dominio_borrador_de_obra_en_planeacion_sin_otra_congelada_se_admite() -> None:
    """CA-B1 · RN-01 — un `BORRADOR` en una obra en `PLANEACION` y sin otra congelada se puede congelar."""
    resultado = evaluar_congelado(
        estado_linea_base="BORRADOR", otra_congelada=None, estado_obra="PLANEACION"
    )

    assert resultado == CongeladoAdmitido()


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt017_cab03_dominio_linea_base_en_otro_estado(estado: str) -> None:
    """CA-B3 esc. 1 · RN-01 — una línea base que no es `BORRADOR` se rechaza con su estado como dato."""
    resultado = _rechazo(
        evaluar_congelado(estado_linea_base=estado, otra_congelada=None, estado_obra="PLANEACION")
    )

    assert resultado.causa == CausaRechazoCongelado.LINEA_BASE_EN_OTRO_ESTADO
    assert dict(resultado.datos) == {"estado": estado}


def test_tkt017_cab02_dominio_otra_congelada_vigente() -> None:
    """CA-B2 · RN-01 — con otra congelada vigente se rechaza con su id y su versión como datos."""
    resultado = _rechazo(
        evaluar_congelado(
            estado_linea_base="BORRADOR", otra_congelada=VIGENTE, estado_obra="PLANEACION"
        )
    )

    assert resultado.causa == CausaRechazoCongelado.OBRA_CON_CONGELADA
    assert dict(resultado.datos) == {
        "linea_base_vigente_id": VIGENTE.id,
        "version_vigente": 3,
    }


@pytest.mark.parametrize("estado_obra", ESTADOS_DE_OBRA_NO_ADMITIDOS)
def test_tkt017_cab03_dominio_obra_fuera_de_planeacion(estado_obra: str) -> None:
    """CA-B3 esc. 2 · RN-01 — sin otra congelada, una obra que no está en `PLANEACION` se rechaza con su estado."""
    resultado = _rechazo(
        evaluar_congelado(
            estado_linea_base="BORRADOR", otra_congelada=None, estado_obra=estado_obra
        )
    )

    assert resultado.causa == CausaRechazoCongelado.OBRA_FUERA_DE_PLANEACION
    assert dict(resultado.datos) == {"estado_obra": estado_obra}


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt017_cab03_dominio_el_estado_de_la_linea_base_va_antes_que_la_otra_congelada(
    estado: str,
) -> None:
    """CA-B3 · RN-01 — una línea base que no es `BORRADOR` se responde por su estado aunque haya otra congelada y la obra no esté en `PLANEACION`."""
    resultado = _rechazo(
        evaluar_congelado(estado_linea_base=estado, otra_congelada=VIGENTE, estado_obra="ACTIVA")
    )

    assert resultado.causa == CausaRechazoCongelado.LINEA_BASE_EN_OTRO_ESTADO
    assert dict(resultado.datos) == {"estado": estado}


@pytest.mark.parametrize("estado_obra", ESTADOS_DE_OBRA_NO_ADMITIDOS)
def test_tkt017_cab02_dominio_la_otra_congelada_va_antes_que_el_estado_de_la_obra(
    estado_obra: str,
) -> None:
    """CA-B2 · RN-01 — una obra con congelada ya está `ACTIVA`: la respuesta es `RN-01` y no la de la obra fuera de `PLANEACION`."""
    resultado = _rechazo(
        evaluar_congelado(
            estado_linea_base="BORRADOR", otra_congelada=VIGENTE, estado_obra=estado_obra
        )
    )

    assert resultado.causa == CausaRechazoCongelado.OBRA_CON_CONGELADA
    assert dict(resultado.datos) == {
        "linea_base_vigente_id": VIGENTE.id,
        "version_vigente": 3,
    }
