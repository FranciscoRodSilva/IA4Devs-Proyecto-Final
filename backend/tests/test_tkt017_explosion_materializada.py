"""TKT-017a2 fila A3 · explosión materializada (TC-A09, CA-B1)."""

from uuid import UUID

from cimenta.presupuesto.dominio.analisis import TipoCargo, TipoInsumo
from cimenta.presupuesto.dominio.explosion import (
    ExplosionCalculada,
    ImportesTipoPartida,
    MotivoRechazoExplosion,
    RechazoExplosion,
    RenglonExplosion,
)
from cimenta.presupuesto.dominio.explosion_materializada import (
    CargoDeApu,
    FilaExplotable,
    InsumoDeApu,
    explotar_filas,
)
from tipos_base import Cantidad, Dinero, Rendimiento

_TIPO = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_tkt017_cab01_explotar_filas_mismo_resultado_distinto_orden() -> None:
    """TC-A09 · CA-B1 — orden de filas no altera explosión ni importes por tipo."""
    f1 = FilaExplotable(
        codigo_concepto="A",
        tipo_partida_id=_TIPO,
        cantidad=Cantidad("10.0000"),
        precio_unitario=Dinero("100.0000"),
        insumos=(
            InsumoDeApu(
                codigo="K1",
                tipo=TipoInsumo.MATERIAL,
                unidad="PZA",
                costo_unitario=Dinero("5.0000"),
                rendimiento=Rendimiento("1.000000"),
            ),
        ),
        cargos=(
            CargoDeApu(tipo=TipoCargo.UTILIDAD, importe=Dinero("10.0000")),
            CargoDeApu(tipo=TipoCargo.INDIRECTOS, importe=Dinero("5.0000")),
        ),
    )
    f2 = FilaExplotable(
        codigo_concepto="B",
        tipo_partida_id=_TIPO,
        cantidad=Cantidad("5.0000"),
        precio_unitario=Dinero("200.0000"),
        insumos=(
            InsumoDeApu(
                codigo="K1",
                tipo=TipoInsumo.MATERIAL,
                unidad="PZA",
                costo_unitario=Dinero("8.0000"),
                rendimiento=Rendimiento("2.000000"),
            ),
        ),
        cargos=(
            CargoDeApu(tipo=TipoCargo.UTILIDAD, importe=Dinero("15.0000")),
            CargoDeApu(tipo=TipoCargo.INDIRECTOS, importe=Dinero("3.0000")),
        ),
    )
    r1 = explotar_filas((f1, f2))
    r2 = explotar_filas((f2, f1))
    assert isinstance(r1, ExplosionCalculada) and isinstance(r2, ExplosionCalculada)
    assert r1.renglones == r2.renglones
    assert r1.importes == r2.importes
    assert all(
        r.cantidad_conceptos == r.cantidad_conceptos.cuantizar()
        and r.importe == r.importe.cuantizar()
        for r in r1.renglones
    )


def test_tkt017_cab01_explotar_filas_devuelve_valores_en_la_escala_de_su_columna() -> None:
    """TC-A09 · CA-B1 · PA-23 — el rendimiento y el costo no exactos se cuantizan una sola vez."""
    f1 = FilaExplotable(
        codigo_concepto="A",
        tipo_partida_id=_TIPO,
        cantidad=Cantidad("1.0001"),
        precio_unitario=Dinero("100.0001"),
        insumos=(
            InsumoDeApu(
                codigo="K1",
                tipo=TipoInsumo.MATERIAL,
                unidad="PZA",
                costo_unitario=Dinero("5.0000"),
                rendimiento=Rendimiento("0.333333"),
            ),
        ),
        cargos=(
            CargoDeApu(tipo=TipoCargo.UTILIDAD, importe=Dinero("10.0000")),
            CargoDeApu(tipo=TipoCargo.INDIRECTOS, importe=Dinero("5.0000")),
        ),
    )
    f2 = FilaExplotable(
        codigo_concepto="B",
        tipo_partida_id=_TIPO,
        cantidad=Cantidad("2.0001"),
        precio_unitario=Dinero("200.0001"),
        insumos=(
            InsumoDeApu(
                codigo="K1",
                tipo=TipoInsumo.MATERIAL,
                unidad="PZA",
                costo_unitario=Dinero("8.0000"),
                rendimiento=Rendimiento("0.500000"),
            ),
        ),
        cargos=(
            CargoDeApu(tipo=TipoCargo.UTILIDAD, importe=Dinero("15.0000")),
            CargoDeApu(tipo=TipoCargo.INDIRECTOS, importe=Dinero("3.0000")),
        ),
    )
    resultado = explotar_filas((f1, f2))
    assert isinstance(resultado, ExplosionCalculada)
    assert resultado.renglones == (
        RenglonExplosion(
            tipo_partida_id=_TIPO,
            clave_insumo="K1",
            cantidad_conceptos=Cantidad("3.0002"),
            cantidad_presupuestada=Cantidad("1.3334"),
            rendimiento_congelado=Rendimiento("0.444442"),
            costo_unitario=Dinero("7.2500"),
            importe=Dinero("9.6672"),
        ),
    )
    assert resultado.importes == (
        ImportesTipoPartida(
            tipo_partida_id=_TIPO,
            importe_venta=Dinero("500.0303"),
            importe_sugerido=Dinero("449.0270"),
        ),
    )


def test_tkt017_cab01_sin_analisis_rechaza() -> None:
    """TC-A09 · rechazo SIN_ANALISIS."""
    f = FilaExplotable(
        codigo_concepto="X",
        tipo_partida_id=_TIPO,
        cantidad=Cantidad("1.0000"),
        precio_unitario=Dinero("1.0000"),
        insumos=None,
        cargos=(),
    )
    r = explotar_filas((f,))
    assert isinstance(r, RechazoExplosion)
    assert any(c.motivo == MotivoRechazoExplosion.SIN_ANALISIS for c in r.causas)
