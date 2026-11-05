"""Libro sintético CA-8 (TKT-016b, fila B1)."""

from __future__ import annotations

from cimenta.presupuesto.dominio.explosion import ExplosionCalculada, calcular_explosion
from herramientas.soporte_tkt014 import leer_libro_presupuesto_bytes
from herramientas.soporte_tkt016 import (
    MUROS,
    PLAFONES,
    TIPO_POR_FILA_LIBRO_SINTETICO,
    conceptos_a_explotar,
    libro_explosion_sintetico,
)
from tipos_base import Cantidad, Dinero, Rendimiento, sumar


def _calcular_libro_sintetico(libro_catalogo) -> ExplosionCalculada:
    contenido = libro_explosion_sintetico(libro_catalogo)
    leido = leer_libro_presupuesto_bytes(contenido)
    conceptos = conceptos_a_explotar(leido, TIPO_POR_FILA_LIBRO_SINTETICO)
    resultado = calcular_explosion(conceptos)
    assert isinstance(resultado, ExplosionCalculada)
    return resultado.cuantizar()


def test_hdu001_esc14_libro_sintetico_reproduce_su_total(libro_catalogo) -> None:
    """TC-24 · CA-8 — cifras del design TKT-016."""
    explosion = _calcular_libro_sintetico(libro_catalogo)
    assert len(explosion.renglones) == 5

    esperado = {
        (MUROS, "MATERIAL DOS"): (
            Cantidad("10"),
            Rendimiento("1.500000"),
            Dinero("75.0000"),
            Dinero("5.0000"),
        ),
        (MUROS, "MATERIAL TRES"): (
            Cantidad("4"),
            Rendimiento("0.400000"),
            Dinero("11.2000"),
            Dinero("7.0000"),
        ),
        (MUROS, "MATERIAL UNO"): (
            Cantidad("14"),
            Rendimiento("2.142857"),
            Dinero("320.0000"),
            Dinero("10.6667"),
        ),
        (PLAFONES, "MATERIAL DOS"): (
            Cantidad("11"),
            Rendimiento("1.500000"),
            Dinero("82.5000"),
            Dinero("5.0000"),
        ),
        (PLAFONES, "MATERIAL UNO"): (
            Cantidad("11"),
            Rendimiento("2.454545"),
            Dinero("285.0000"),
            Dinero("10.5556"),
        ),
    }
    for renglon in explosion.renglones:
        clave = (renglon.tipo_partida_id, renglon.clave_insumo)
        assert clave in esperado
        q_con, rend, imp, costo = esperado[clave]
        assert renglon.cantidad_conceptos == q_con
        assert renglon.rendimiento_congelado == rend
        assert renglon.importe == imp
        assert renglon.costo_unitario == costo

    total = sumar((r.importe for r in explosion.renglones), Dinero)
    assert total == Dinero("773.7000")

    por_tipo = {i.tipo_partida_id: i for i in explosion.importes}
    assert por_tipo[MUROS].importe_venta == Dinero("2389.3000")
    assert por_tipo[MUROS].importe_sugerido == Dinero("2028.7300")
    assert por_tipo[PLAFONES].importe_venta == Dinero("1748.2300")
    assert por_tipo[PLAFONES].importe_sugerido == Dinero("1464.9250")


def test_hdu001_esc14_mismo_insumo_en_dos_tipos_da_dos_filas(libro_catalogo) -> None:
    """TC-25 · CA-8, CA-3 — MATERIAL UNO/DOS en MUROS y PLAFONES; sin mano de obra."""
    explosion = _calcular_libro_sintetico(libro_catalogo)
    claves_muros = {r.clave_insumo for r in explosion.renglones if r.tipo_partida_id == MUROS}
    claves_plaf = {r.clave_insumo for r in explosion.renglones if r.tipo_partida_id == PLAFONES}
    assert "MATERIAL UNO" in claves_muros and "MATERIAL UNO" in claves_plaf
    assert "MATERIAL DOS" in claves_muros and "MATERIAL DOS" in claves_plaf
    todas = {r.clave_insumo for r in explosion.renglones}
    assert "CUADRILLA X" not in todas
