"""Lector de APU contra libros reales (TKT-014b): TC-40 a TC-49.

Requieren `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`; si faltan, `pytest.skip` (PA-T3).
"""

from __future__ import annotations

from decimal import Decimal

from cimenta.presupuesto.dominio.analisis import TipoCargo, TipoInsumo
from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo
from herramientas.soporte_tkt014 import leer_libro_presupuesto_bytes
from tipos_base import Dinero, Porcentaje, Rendimiento

HOJA_MURO_UNION = "MURO STD-635-STD "
HOJAS_ENITI_REF_PU = ("14", "15", "16", "18", "19")
CODIGOS_DUPLICADOS_ENITI = ("620014", "620045", "620050")
CLAVE_CANAL = "CANAL 635X3.05 CAL.26"
TOLERANCIA_PU_EXACTO = Decimal("1E-9")


def _analisis_por_hoja(libro, hoja: str):
    return next(a for a in libro.analisis if a.hoja == hoja)


def _hallazgos_de_analisis(libro) -> list[Hallazgo]:
    return [h for apu in libro.analisis for h in apu.hallazgos]


def test_hdu001_esc05_analisis_reales_de_eniti(archivo_eniti: bytes) -> None:
    """TC-40 · HDU-001 esc. 5 · CA-1 — 24 hojas APU en ENITI."""
    libro = leer_libro_presupuesto_bytes(archivo_eniti)
    assert libro.catalogo.hoja is not None
    assert libro.catalogo.hoja not in {a.hoja for a in libro.analisis}
    assert len(libro.analisis) == 24
    assert [a.hoja for a in libro.analisis][0] == "01"
    primero = libro.analisis[0]
    assert primero.cabecera.codigo == "620001"
    assert primero.cabecera.unidad == "M2"
    assert primero.cabecera.fecha == "2026-08-25"
    pu = Dinero("668.6929342319413")
    assert primero.cabecera.precio_unitario == pu
    assert primero.precio_unitario == pu
    materiales = [i for i in primero.insumos if i.tipo == TipoInsumo.MATERIAL]
    mano = [i for i in primero.insumos if i.tipo == TipoInsumo.MANO_OBRA]
    assert len(materiales) == 8
    assert len(mano) == 2


def test_hdu001_esc05_analisis_reales_de_union_square(archivo_union: bytes) -> None:
    """TC-41 · HDU-001 esc. 5 · CA-2 — 20 hojas APU en Union Square."""
    libro = leer_libro_presupuesto_bytes(archivo_union)
    assert len(libro.analisis) == 20
    hojas_apu = {a.hoja for a in libro.analisis}
    for ajena in (
        "RESUMEN US F2",
        "BORRADOR DE GENERADORES",
        "REFUERZOS",
        "CATALOGO DE CONCEPTOS",
    ):
        assert ajena not in hojas_apu
    assert HOJA_MURO_UNION in hojas_apu


def test_hdu001_esc05_muro_std_635_std(archivo_union: bytes) -> None:
    """TC-42 · HDU-001 esc. 5 · CA-3, CA-4, CA-16 — hoja MURO STD-635-STD."""
    libro = leer_libro_presupuesto_bytes(archivo_union)
    apu = _analisis_por_hoja(libro, HOJA_MURO_UNION)
    cab = apu.cabecera
    assert cab.unidad == "M2"
    assert cab.fecha == "2025-09-01"
    assert cab.analista == "ARQ.MAXIMILIANO QUEZADA GARCIA"
    assert cab.precio_unitario == Dinero("641.3608310977561")

    materiales = [i for i in apu.insumos if i.tipo == TipoInsumo.MATERIAL]
    assert len(materiales) == 8
    canal = next(i for i in materiales if i.descripcion == CLAVE_CANAL)
    assert canal.unidad == "PZA"
    assert canal.costo_unitario == Dinero("44.58")
    assert canal.rendimiento == Rendimiento("0.3278")
    assert canal.cargo == Dinero("14.613323999999999")

    pintor = next(i for i in apu.insumos if i.descripcion == "CUADRILLA DE PINTOR")
    assert pintor.unidad == "JORNAL"
    assert pintor.costo_unitario == Dinero("1152.39")
    assert pintor.rendimiento == Rendimiento("4.1")
    assert pintor.cargo == Dinero("281.0707317073171")

    limpieza = next(i for i in apu.insumos if i.descripcion == "CUADRILLA DE LIMPIEZA")
    assert limpieza.costo_unitario == Dinero("864.4")
    assert limpieza.rendimiento == Rendimiento("5")
    assert limpieza.cargo == Dinero("5")

    t = apu.totales
    assert t.material == Dinero("201.669152000000003")
    assert t.mano_obra == Dinero("286.0707317073171")
    assert t.costo_directo == Dinero("487.739883707317103")
    assert t.cargos == Dinero("153.620947390439033")
    assert apu.precio_unitario is not None
    assert t.precio_unitario is not None
    diff = abs(t.precio_unitario.valor - apu.precio_unitario.valor)
    assert diff < TOLERANCIA_PU_EXACTO

    def _cargo(rotulo: str):
        return next(c for c in apu.cargos if c.rotulo.strip().upper() == rotulo.upper())

    hm = _cargo("HERRAMIENTA MENOR")
    assert hm.tipo == TipoCargo.HERRAMIENTA_MENOR
    assert hm.porcentaje == Porcentaje("0.01")
    assert hm.base == Dinero("487.7398837073171")
    assert hm.importe == Dinero("4.877398837073171")

    assert _cargo("ANDAMIAJE").tipo == TipoCargo.ANDAMIAJE
    desp = _cargo("DESPERDICIO")
    assert desp.tipo == TipoCargo.DESPERDICIO
    assert desp.porcentaje == Porcentaje("0.05")
    assert desp.base == Dinero("201.669152")
    assert desp.importe == Dinero("10.083457600000001")

    for rotulo in ("OFICIAL TABLAROQUERO", "AYUDANTE TABLAROQUERO"):
        v = _cargo(rotulo)
        assert v.tipo == TipoCargo.VIATICOS
        assert v.porcentaje == Porcentaje("0")
        assert v.importe == Dinero("0")

    iva = _cargo("IVA")
    assert iva.tipo == TipoCargo.IVA
    assert iva.porcentaje == Porcentaje("0.16")

    ind = _cargo("INDIRECTOS")
    assert ind.tipo == TipoCargo.INDIRECTOS
    assert ind.porcentaje == Porcentaje("0.08")
    assert ind.base == Dinero("507.57813898146344")

    util = _cargo("UTILIDAD")
    assert util.tipo == TipoCargo.UTILIDAD
    assert util.porcentaje == Porcentaje("0.12")


def test_hdu001_esc06_siroc_real(archivo_eniti: bytes) -> None:
    """TC-43 · HDU-001 esc. 6 · CA-6 — SIROC sin tipo, un hallazgo por hoja."""
    libro = leer_libro_presupuesto_bytes(archivo_eniti)
    hallazgos = [
        h for h in _hallazgos_de_analisis(libro) if h.causa == CausaHallazgo.CARGO_DESCONOCIDO
    ]
    assert len(hallazgos) == 20
    for h in hallazgos:
        assert h.columna == "A"
        assert h.valor_original is not None
        assert h.valor_original.strip().upper().startswith("SIROC")
    for apu in libro.analisis:
        for cargo in apu.cargos:
            if "SIROC" in cargo.rotulo.upper():
                assert cargo.tipo is None


def test_hdu001_esc07_analisis_reales_sin_codigo(
    archivo_eniti: bytes, archivo_union: bytes
) -> None:
    """TC-44 · HDU-001 esc. 7 · CA-7 — 21 análisis sin código."""
    le = leer_libro_presupuesto_bytes(archivo_eniti)
    lu = leer_libro_presupuesto_bytes(archivo_union)
    sin_codigo = [
        h for h in le.hallazgos + lu.hallazgos if h.causa == CausaHallazgo.ANALISIS_SIN_CODIGO
    ]
    assert len(sin_codigo) == 21
    for h in sin_codigo:
        assert h.fila == 12
        assert h.columna == "C"
    assert lu.asociaciones == ()
    assert len([h for h in le.hallazgos if h.causa == CausaHallazgo.ANALISIS_SIN_CODIGO]) == 1
    assert len([h for h in lu.hallazgos if h.causa == CausaHallazgo.ANALISIS_SIN_CODIGO]) == 20


def test_hdu001_esc09_codigos_reales_en_dos_hojas(archivo_eniti: bytes) -> None:
    """TC-45 · HDU-001 esc. 9 · CA-8 — códigos duplicados en dos hojas."""
    libro = leer_libro_presupuesto_bytes(archivo_eniti)
    dup = [h for h in libro.hallazgos if h.causa == CausaHallazgo.CODIGO_EN_VARIAS_HOJAS]
    assert len(dup) == 6
    por_codigo: dict[str, list[Hallazgo]] = {}
    for h in dup:
        assert h.valor_original is not None
        por_codigo.setdefault(h.valor_original, []).append(h)
    assert set(por_codigo) == set(CODIGOS_DUPLICADOS_ENITI)
    for codigo in CODIGOS_DUPLICADOS_ENITI:
        assert len(por_codigo[codigo]) == 2
        detalles = {h.detalle for h in por_codigo[codigo]}
        assert len(detalles) == 2
    codigos_asociados = {a.codigo for a in libro.asociaciones}
    for codigo in CODIGOS_DUPLICADOS_ENITI:
        assert codigo not in codigos_asociados


def test_hdu001_esc06_ref_real_en_pu_de_cabecera(archivo_eniti: bytes) -> None:
    """TC-46 · HDU-001 esc. 6 · CA-9 — #REF! en P.U. de cabecera."""
    libro = leer_libro_presupuesto_bytes(archivo_eniti)
    for nombre in HOJAS_ENITI_REF_PU:
        apu = _analisis_por_hoja(libro, nombre)
        refs = [
            h
            for h in apu.hallazgos
            if h.causa == CausaHallazgo.ERROR_DE_FORMULA and h.fila == 15 and h.columna == "C"
        ]
        assert len(refs) == 1
        assert refs[0].valor_original == "#REF!"
        assert not any(
            h.causa in (CausaHallazgo.PU_NO_CUADRA, CausaHallazgo.PU_NO_VERIFICABLE)
            for h in apu.hallazgos
        )


def test_hdu001_esc06_las_44_hojas_reales_cuadran(
    archivo_eniti: bytes, archivo_union: bytes
) -> None:
    """TC-47 · HDU-001 esc. 6 · CA-10 — sin PU_NO_CUADRA ni PU_NO_VERIFICABLE."""
    for contenido in (archivo_eniti, archivo_union):
        libro = leer_libro_presupuesto_bytes(contenido)
        for apu in libro.analisis:
            for h in apu.hallazgos:
                assert h.causa not in (
                    CausaHallazgo.PU_NO_CUADRA,
                    CausaHallazgo.PU_NO_VERIFICABLE,
                )


def test_hdu001_esc05_asociacion_real_de_eniti(archivo_eniti: bytes) -> None:
    """TC-48 · HDU-001 esc. 5 · CA-5 — asociación por código en ENITI."""
    libro = leer_libro_presupuesto_bytes(archivo_eniti)
    _analisis_por_hoja(libro, "01")
    enlace_01 = next(a for a in libro.asociaciones if a.hoja == "01")
    assert enlace_01.codigo == "620001"
    assert len(enlace_01.filas_catalogo) == 162
    enlace_40 = next(a for a in libro.asociaciones if a.hoja == "40-A")
    assert enlace_40.codigo == "620040-A"
    assert len(libro.codigos_sin_analisis) == 16


def test_hdu001_esc10_insumos_reales_por_crear(archivo_eniti: bytes, archivo_union: bytes) -> None:
    """TC-49 · HDU-001 esc. 10 · CA-12 — insumos por crear en los reales."""
    le = leer_libro_presupuesto_bytes(archivo_eniti)
    lu = leer_libro_presupuesto_bytes(archivo_union)
    assert len(le.insumos_por_crear) == 29
    assert sum(1 for i in le.insumos_por_crear if i.tipo == TipoInsumo.MATERIAL) == 26
    assert sum(1 for i in le.insumos_por_crear if i.tipo == TipoInsumo.MANO_OBRA) == 3
    assert len(lu.insumos_por_crear) == 23
    assert sum(1 for i in lu.insumos_por_crear if i.tipo == TipoInsumo.MATERIAL) == 21
    assert sum(1 for i in lu.insumos_por_crear if i.tipo == TipoInsumo.MANO_OBRA) == 2
    ke = {i.clave for i in le.insumos_por_crear}
    ku = {i.clave for i in lu.insumos_por_crear}
    assert len(ke | ku) == 35
    assert len(ke & ku) == 17

    le_filtrado = leer_libro_presupuesto_bytes(archivo_eniti, {CLAVE_CANAL: "PZA"})
    assert len(le_filtrado.insumos_por_crear) == 28
    assert CLAVE_CANAL not in {i.clave for i in le_filtrado.insumos_por_crear}
