"""Regla calcular_explosion — camino feliz y cuantizar (TKT-016, filas A2–A3)."""

from dataclasses import fields
from decimal import Decimal

import pytest

from cimenta.presupuesto.dominio.explosion import (
    ConceptoAExplotar,
    ExplosionCalculada,
    ImportesTipoPartida,
    calcular_explosion,
)
from herramientas.soporte_tkt016 import (
    MUROS,
    PLAFONES,
    analisis,
    concepto,
    insumo_mano_obra,
    insumo_material,
)
from tipos_base import Cantidad, Dinero, Rendimiento, cociente_rendimiento


def _explotar(*items: ConceptoAExplotar) -> ExplosionCalculada:
    resultado = calcular_explosion(items)
    assert isinstance(resultado, ExplosionCalculada)
    return resultado


def test_hdu001_esc14_agrega_por_tipo_de_partida_en_toda_la_obra() -> None:
    """TC-05 · CA-1 — un insumo en dos áreas del mismo tipo da una fila."""
    panel = insumo_material(clave="PANEL", rendimiento="1.05", costo="80.00")
    panel_b = insumo_material(clave="PANEL", rendimiento="1.10", costo="85.00")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="MURO-A", cantidad="100", area_nombre="Área 1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="MURO-B", cantidad="200", area_nombre="Área 2"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel_b,)),
        ),
    )
    explosion = _explotar(*items)
    assert len(explosion.renglones) == 1
    r = explosion.renglones[0]
    assert r.tipo_partida_id == MUROS and r.clave_insumo == "PANEL"
    assert r.cantidad_presupuestada == Cantidad("325")


def test_hdu001_esc14_rendimiento_y_costo_ponderados() -> None:
    """TC-06 · CA-2 — promedios ponderados e importe exacto sin pasar por la división."""
    panel = insumo_material(clave="PANEL", rendimiento="1.05", costo="80.00")
    panel_b = insumo_material(clave="PANEL", rendimiento="1.10", costo="85.00")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="MURO-A", cantidad="100"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="MURO-B", cantidad="200"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel_b,)),
        ),
    )
    r = _explotar(*items).renglones[0]
    rq = r.cuantizar()
    assert rq.rendimiento_congelado == Rendimiento("1.083333")
    assert rq.costo_unitario == Dinero("83.3846")
    assert rq.importe == Dinero("27100.0000")
    assert r.importe.valor == Decimal("27100")
    assert (r.rendimiento_congelado * r.cantidad_conceptos).cuantizar() == Cantidad("325.0000")


def test_hdu001_esc14_solo_material_entra_en_la_explosion() -> None:
    """TC-07 · CA-3 — mano de obra no produce fila ni rechazo."""
    insumos = (
        insumo_material(clave="PANEL", rendimiento="1", costo="10"),
        insumo_mano_obra(clave="CUADRILLA"),
    )
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="1"),
        tipo_partida_id=MUROS,
        analisis=analisis(insumos=insumos),
    )
    explosion = _explotar(item)
    assert len(explosion.renglones) == 1
    assert explosion.renglones[0].clave_insumo == "PANEL"


def test_hdu001_esc14_concepto_cuenta_una_vez_por_insumo() -> None:
    """TC-08 · CA-2 — la misma clave dos veces no duplica cantidad_conceptos."""
    insumos = (
        insumo_material(clave="PANEL", rendimiento="1", costo="10", fila=8),
        insumo_material(clave="PANEL", rendimiento="0.5", costo="10", fila=9),
    )
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="10"),
        tipo_partida_id=MUROS,
        analisis=analisis(insumos=insumos),
    )
    r = _explotar(item).renglones[0]
    assert r.cantidad_presupuestada == Cantidad("15")
    assert r.cantidad_conceptos == Cantidad("10")
    assert r.rendimiento_congelado == Rendimiento("1.5")


@pytest.mark.parametrize("precio_catalogo", ["999.99", None])
def test_hdu001_esc15_importe_de_venta_y_sugerido_desde_el_analisis(
    precio_catalogo: str | None,
) -> None:
    """TC-09 · CA-4 — venta y sugerido desde el análisis, no el catálogo."""
    c = concepto(
        fila=10,
        codigo="X",
        cantidad="100",
        precio_catalogo=precio_catalogo,
    )
    item = ConceptoAExplotar(
        concepto=c,
        tipo_partida_id=MUROS,
        analisis=analisis(),
    )
    imp = _explotar(item).cuantizar().importes[0]
    assert imp.importe_venta == Dinero("64136.0000")
    assert imp.importe_sugerido == Dinero("53136.0000")


def test_hdu001_esc15_sugerido_es_sugerencia_sin_tope() -> None:
    """TC-10 · CA-4 — nombres de campos de ImportesTipoPartida."""
    nombres = {f.name for f in fields(ImportesTipoPartida)}
    assert nombres == {"tipo_partida_id", "importe_venta", "importe_sugerido"}


def test_hdu001_esc14_sin_redondeo_intermedio() -> None:
    """TC-11 · CA-5, PA-23 — sin redondeo intermedio; cuantizar al final."""
    insumo = insumo_material(clave="X", rendimiento="0.000050", costo="10")
    analisis_cero = analisis(
        precio_unitario="10.00005",
        insumos=(insumo,),
        utilidad="0",
        indirectos="0",
    )
    items = tuple(
        ConceptoAExplotar(
            concepto=concepto(fila=10 + i, codigo=f"C{i}", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis_cero,
        )
        for i in range(5)
    )
    explosion = _explotar(*items)
    r = explosion.renglones[0].cuantizar()
    assert r.cantidad_presupuestada == Cantidad("0.0003")
    assert r.rendimiento_congelado == Rendimiento("0.000050")
    assert explosion.cuantizar().importes[0].importe_venta == Dinero("50.0003")
    assert explosion.renglones[0].cantidad_presupuestada.valor == Decimal("0.00025")


def test_hdu001_esc14_cuantizar_lleva_cada_cifra_a_su_escala() -> None:
    """TC-12 · CA-5 — escalas de columna tras cuantizar."""
    r = cociente_rendimiento(Cantidad("30"), Cantidad("14"))
    exp = r.valor.as_tuple().exponent
    assert isinstance(exp, int) and (exp <= -28 or len(r.valor.as_tuple().digits) >= 20)
    panel = insumo_material(clave="PANEL", rendimiento="1.05", costo="80.00")
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="100"),
        tipo_partida_id=MUROS,
        analisis=analisis(insumos=(panel,)),
    )
    cq = _explotar(item).cuantizar()
    assert cq.renglones[0].cantidad_presupuestada.valor.as_tuple().exponent == -4
    assert cq.renglones[0].rendimiento_congelado.valor.as_tuple().exponent == -6
    assert cq.renglones[0].costo_unitario.valor.as_tuple().exponent == -4


def test_hdu001_esc14_mismo_insumo_en_dos_tipos_partida_da_dos_filas() -> None:
    """TC-25 parcial · CA-1, M-14 — la agregación no mezcla tipos de partida."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="A", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="B", cantidad="2"),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(panel,)),
        ),
    )
    explosion = _explotar(*items)
    assert len(explosion.renglones) == 2
    assert {r.tipo_partida_id for r in explosion.renglones} == {MUROS, PLAFONES}
    assert all(r.clave_insumo == "PANEL" for r in explosion.renglones)


def test_hdu001_esc14_entrada_vacia() -> None:
    """Borde — obra sin conceptos devuelve explosión vacía."""
    assert calcular_explosion(()) == ExplosionCalculada((), ())
