"""Reconciliación AP-058-25 (TKT-016b, fila B2 · CA-10)."""

from __future__ import annotations

from uuid import UUID

import pytest

from cimenta.presupuesto.dominio.explosion import (
    RechazoExplosion,
    calcular_explosion,
)
from herramientas.soporte_tkt014 import leer_libro_presupuesto_bytes
from herramientas.soporte_tkt016 import (
    VARIABLE_ORACULO_EXPLOSION,
    conceptos_a_explotar,
    leer_oraculo_explosion_union,
)
from tipos_base import Dinero, sumar

_TIPO_UNICO_ORACULO = UUID("00000000-0000-0000-0000-000000000099")


@pytest.fixture
def oraculo_explosion_union() -> tuple:
    import os
    from pathlib import Path

    ruta_texto = os.environ.get(VARIABLE_ORACULO_EXPLOSION)
    if not ruta_texto:
        pytest.skip(
            f"{VARIABLE_ORACULO_EXPLOSION} no está definida: "
            "la reconciliación AP-058-25 se omite (CA-10 esc. 2)"
        )
    ruta = Path(ruta_texto)
    if not ruta.is_file():
        pytest.skip(
            f"{VARIABLE_ORACULO_EXPLOSION}={ruta_texto!r} no existe: "
            "la reconciliación AP-058-25 se omite"
        )
    return leer_oraculo_explosion_union(ruta)


def test_hdu001_esc14_reconcilia_con_la_explosion_real(
    archivo_union: bytes,
    oraculo_explosion_union: tuple,
) -> None:
    """TC-26 · CA-10 esc. 1 — CSV oráculo + libro Union (skip si PA-T3)."""
    libro = leer_libro_presupuesto_bytes(archivo_union)
    if libro.asociaciones == ():
        pytest.skip("PA-16.6 · PA-T3: el libro de análisis de Union no asocia ningún concepto")

    tipo_por_fila = {c.fila: _TIPO_UNICO_ORACULO for c in libro.catalogo.conceptos if c.cantidad}
    conceptos = conceptos_a_explotar(libro, tipo_por_fila)
    resultado = calcular_explosion(conceptos)
    if isinstance(resultado, RechazoExplosion):
        causas = ", ".join(f"{c.motivo.value}@{c.fila}" for c in resultado.causas)
        pytest.fail(f"calcular_explosion rechazó la obra real: {causas}")

    explosion = resultado.cuantizar()
    oraculo = oraculo_explosion_union
    assert len(explosion.renglones) == len(oraculo)

    por_clave = {r.clave_insumo: r for r in explosion.renglones}
    for fila in oraculo:
        renglon = por_clave.get(fila.clave)
        assert renglon is not None, f"clave {fila.clave!r} ausente en la explosión calculada"
        assert renglon.cantidad_presupuestada.cuantizar() == fila.cantidad.cuantizar()

    suma_calc = sumar((r.importe for r in explosion.renglones), Dinero)
    suma_oraculo = sumar((f.importe for f in oraculo), Dinero)
    assert suma_calc == suma_oraculo.cuantizar()


def test_hdu001_esc14_sin_variable_la_reconciliacion_se_omite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-27 · CA-10 esc. 2 — falta CIMENTA_EXPLOSION_UNION."""
    monkeypatch.delenv(VARIABLE_ORACULO_EXPLOSION, raising=False)

    def _exigir_variable() -> None:
        import os

        if not os.environ.get(VARIABLE_ORACULO_EXPLOSION):
            pytest.skip(
                f"{VARIABLE_ORACULO_EXPLOSION} no está definida: "
                "la reconciliación AP-058-25 se omite (CA-10 esc. 2)"
            )

    with pytest.raises(pytest.skip.Exception) as excinfo:
        _exigir_variable()
    assert VARIABLE_ORACULO_EXPLOSION in str(excinfo.value)
