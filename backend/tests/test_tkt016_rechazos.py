"""Rechazos todo-o-nada de calcular_explosion (TKT-016, filas A4–A5)."""

import pytest

from cimenta.presupuesto.dominio.analisis import InsumoLeido, TipoCargo, TipoInsumo
from cimenta.presupuesto.dominio.explosion import (
    ConceptoAExplotar,
    ExplosionCalculada,
    MotivoRechazoExplosion,
    RechazoExplosion,
    calcular_explosion,
)
from herramientas.soporte_tkt016 import (
    MUROS,
    PLAFONES,
    analisis,
    concepto,
    insumo_material,
)
from tipos_base import Dinero, Rendimiento


def _rechazo(*items: ConceptoAExplotar) -> RechazoExplosion:
    resultado = calcular_explosion(items)
    assert isinstance(resultado, RechazoExplosion)
    return resultado


def _insumo_sin_rendimiento(clave: str, fila: int = 8) -> InsumoLeido:
    return InsumoLeido(
        fila=fila,
        tipo=TipoInsumo.MATERIAL,
        descripcion=clave,
        clave=clave,
        unidad="PZA",
        costo_unitario=Dinero("10"),
        rendimiento=None,
        cargo=None,
    )


def _insumo_sin_costo(clave: str, fila: int = 8) -> InsumoLeido:
    return InsumoLeido(
        fila=fila,
        tipo=TipoInsumo.MATERIAL,
        descripcion=clave,
        clave=clave,
        unidad="PZA",
        costo_unitario=None,
        rendimiento=Rendimiento("1"),
        cargo=None,
    )


def test_hdu001_esc14_rechaza_conceptos_incompletos_con_todas_sus_causas() -> None:
    """TC-13 · CA-6 esc. 1, M4 — enumera todas las causas de concepto incompleto."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="MURO-OK", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=12, codigo="MURO-X", cantidad="1"),
            tipo_partida_id=None,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=30, codigo="PLAF-Y", cantidad="1"),
            tipo_partida_id=PLAFONES,
            analisis=None,
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=31, codigo="PLAF-Z", cantidad=None),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(panel,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=32, codigo="PLAF-W", cantidad="0"),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(panel,)),
        ),
    )
    causas = _rechazo(*items).causas
    esperadas = (
        (MotivoRechazoExplosion.SIN_TIPO_PARTIDA, "MURO-X", 12),
        (MotivoRechazoExplosion.SIN_ANALISIS, "PLAF-Y", 30),
        (MotivoRechazoExplosion.CANTIDAD_AUSENTE, "PLAF-Z", 31),
        (MotivoRechazoExplosion.CANTIDAD_NO_POSITIVA, "PLAF-W", 32),
    )
    assert len(causas) == len(esperadas)
    for causa, (motivo, codigo, fila) in zip(causas, esperadas, strict=True):
        assert causa.motivo == motivo
        assert causa.codigo_concepto == codigo
        assert causa.fila == fila


def test_hdu001_esc14_rechaza_cantidad_negativa() -> None:
    """TC-14 · CA-6 — cantidad negativa."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="-1"),
        tipo_partida_id=MUROS,
        analisis=analisis(insumos=(panel,)),
    )
    causas = _rechazo(item).causas
    assert len(causas) == 1
    assert causas[0].motivo == MotivoRechazoExplosion.CANTIDAD_NO_POSITIVA


def test_hdu001_esc15_rechaza_analisis_sin_precio_o_sin_cargos() -> None:
    """TC-15 · CA-6 esc. 2 — precio y cargos obligatorios."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="MURO-A", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,), sin_precio=True),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="MURO-B", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel,), sin_utilidad=True),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=12, codigo="PLAF-C", cantidad="1"),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(panel,), indirectos_sin_importe=True),
        ),
    )
    causas = _rechazo(*items).causas
    assert (causas[0].motivo, causas[0].codigo_concepto) == (
        MotivoRechazoExplosion.SIN_PRECIO_UNITARIO,
        "MURO-A",
    )
    assert causas[1].motivo == MotivoRechazoExplosion.CARGO_AUSENTE
    assert causas[1].cargo == TipoCargo.UTILIDAD and causas[1].codigo_concepto == "MURO-B"
    assert causas[2].motivo == MotivoRechazoExplosion.CARGO_SIN_IMPORTE
    assert causas[2].cargo == TipoCargo.INDIRECTOS and causas[2].codigo_concepto == "PLAF-C"


def test_hdu001_esc14_rechaza_insumos_sin_rendimiento_o_sin_costo() -> None:
    """TC-16 · CA-7 esc. 1 — insumos MATERIAL incompletos en tres conceptos."""
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="MURO-A", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(_insumo_sin_rendimiento("PANEL"),)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="MURO-B", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(_insumo_sin_costo("TORNILLO", 9),)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=12, codigo="MURO-C", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(
                insumos=(insumo_material(clave="CINTA", rendimiento="0", costo="1", fila=10),)
            ),
        ),
    )
    causas = _rechazo(*items).causas
    assert len(causas) == 3
    assert causas[0].motivo == MotivoRechazoExplosion.RENDIMIENTO_AUSENTE
    assert causas[0].clave_insumo == "PANEL"
    assert causas[1].motivo == MotivoRechazoExplosion.INSUMO_SIN_COSTO
    assert causas[1].clave_insumo == "TORNILLO"
    assert causas[2].motivo == MotivoRechazoExplosion.RENDIMIENTO_NO_POSITIVO


@pytest.mark.parametrize("rendimiento", ["-0.5"])
def test_hdu001_esc14_rechaza_rendimiento_negativo(rendimiento: str) -> None:
    """TC-16 · CA-7 — rendimiento negativo."""
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="MURO-C", cantidad="1"),
        tipo_partida_id=MUROS,
        analisis=analisis(
            insumos=(insumo_material(clave="CINTA", rendimiento=rendimiento, costo="1"),)
        ),
    )
    causas = _rechazo(item).causas
    assert causas[0].motivo == MotivoRechazoExplosion.RENDIMIENTO_NO_POSITIVO


def test_hdu001_esc14_rechaza_la_misma_clave_con_dos_unidades() -> None:
    """TC-17 · CA-7 esc. 2 — conflicto de unidades."""
    panel_m2 = insumo_material(clave="PANEL", rendimiento="1", costo="10", unidad="M2")
    panel_pza = insumo_material(clave="PANEL", rendimiento="1", costo="10", unidad="PZA", fila=9)
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="A", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel_m2,)),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="B", cantidad="1"),
            tipo_partida_id=MUROS,
            analisis=analisis(insumos=(panel_pza,)),
        ),
    )
    causas = _rechazo(*items).causas
    assert len(causas) == 2
    for causa in causas:
        assert causa.motivo == MotivoRechazoExplosion.UNIDAD_EN_CONFLICTO
        assert causa.clave_insumo == "PANEL"
        assert causa.unidades == ("M2", "PZA")


def test_hdu001_esc15_rechaza_sugerido_negativo() -> None:
    """TC-18 · CA-7 esc. 3 — sugerido negativo."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="10"),
        tipo_partida_id=MUROS,
        analisis=analisis(
            insumos=(panel,), precio_unitario="100.00", utilidad="70.00", indirectos="40.00"
        ),
    )
    causas = _rechazo(item).causas
    assert len(causas) == 1
    c = causas[0]
    assert c.motivo == MotivoRechazoExplosion.SUGERIDO_NEGATIVO
    assert c.tipo_partida_id == MUROS
    assert c.importe_sugerido == Dinero("-100")


def test_hdu001_esc15_sugerido_cero_se_acepta() -> None:
    """TC-19 · CA-7 esc. 3 — sugerido cero es válido."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="10"),
        tipo_partida_id=MUROS,
        analisis=analisis(
            insumos=(panel,), precio_unitario="100.00", utilidad="60.00", indirectos="40.00"
        ),
    )
    resultado = calcular_explosion((item,))
    assert isinstance(resultado, ExplosionCalculada)
    assert resultado.cuantizar().importes[0].importe_sugerido == Dinero("0.0000")


def test_hdu001_esc15_codigo_repetido_en_dos_tipos_no_oculta_sugerido_negativo() -> None:
    """M4 · el mismo código en dos tipos no excluye el sugerido del otro tipo."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="X", cantidad="10"),
            tipo_partida_id=MUROS,
            analisis=analisis(
                insumos=(panel,),
                precio_unitario="100.00",
                utilidad="70.00",
                indirectos="40.00",
            ),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="X", cantidad=None),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(panel,)),
        ),
    )
    causas = _rechazo(*items).causas
    motivos = [c.motivo for c in causas]
    assert MotivoRechazoExplosion.SUGERIDO_NEGATIVO in motivos
    assert MotivoRechazoExplosion.CANTIDAD_AUSENTE in motivos
    assert len(causas) == 2


def test_hdu001_esc15_sugerido_negativo_se_enumera_con_otras_causas() -> None:
    """TC-20 · M4 — sugerido negativo junto con otras causas."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    sin_costo = _insumo_sin_costo("X", 9)
    items = (
        ConceptoAExplotar(
            concepto=concepto(fila=10, codigo="M1", cantidad="10"),
            tipo_partida_id=MUROS,
            analisis=analisis(
                insumos=(panel,),
                precio_unitario="100.00",
                utilidad="70.00",
                indirectos="40.00",
            ),
        ),
        ConceptoAExplotar(
            concepto=concepto(fila=11, codigo="P1", cantidad="1"),
            tipo_partida_id=PLAFONES,
            analisis=analisis(insumos=(sin_costo,)),
        ),
    )
    causas = _rechazo(*items).causas
    assert len(causas) == 2
    assert causas[0].motivo == MotivoRechazoExplosion.INSUMO_SIN_COSTO
    assert causas[1].motivo == MotivoRechazoExplosion.SUGERIDO_NEGATIVO
