"""Dominio del lector de APU (TKT-014a): TC-01 a TC-22."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from cimenta.presupuesto.dominio.analisis import (
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo, ValorCelda
from cimenta.presupuesto.dominio.lectura_analisis import (
    analizar_hoja_apu,
    interpretar_fecha,
    normalizar_clave_insumo,
    normalizar_codigo,
    tipo_de_cargo,
    verificar_precio_unitario,
)
from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
from herramientas.soporte_tkt014 import fila_apu, hoja_apu_sintetica
from tipos_base import Dinero, Porcentaje, Rendimiento


def _expect(hallazgo: Hallazgo, esperado: Hallazgo) -> None:
    assert hallazgo == esperado


@pytest.mark.parametrize(
    ("entrada", "esperada"),
    [
        (" canal  635x3.05 cal.26 ", "CANAL 635X3.05 CAL.26"),
        ("CANAL\t635X3.05\xa0CAL.26", "CANAL 635X3.05 CAL.26"),
        ("CANAL 635X3.05 CAL.26", "CANAL 635X3.05 CAL.26"),
    ],
)
def test_hdu001_esc10_clave_de_insumo_normalizada(entrada: str, esperada: str) -> None:
    assert normalizar_clave_insumo(entrada) == esperada


def test_hdu001_esc05_codigo_de_analisis_normalizado() -> None:
    assert normalizar_codigo("620001") == "620001"
    assert normalizar_codigo(Decimal("620001.0")) == "620001"
    assert normalizar_codigo(" 620040-a ") == "620040-A"
    assert normalizar_codigo(None) is None
    assert normalizar_codigo("  ") is None


@pytest.mark.parametrize(
    ("rotulo", "tipo"),
    [
        ("HERRAMIENTA MENOR", TipoCargo.HERRAMIENTA_MENOR),
        ("Herramienta  Menor:", TipoCargo.HERRAMIENTA_MENOR),
        ("ANDAMIAJE", TipoCargo.ANDAMIAJE),
        ("DESPERDICIO", TipoCargo.DESPERDICIO),
        ("INDIRECTOS", TipoCargo.INDIRECTOS),
        ("UTILIDAD", TipoCargo.UTILIDAD),
        ("IVA", TipoCargo.IVA),
        (" iva ", TipoCargo.IVA),
        ("IVA 16% MATERIALES", TipoCargo.IVA),
    ],
)
def test_hdu001_esc05_rotulos_de_cargo_se_tipifican(rotulo: str, tipo: TipoCargo) -> None:
    assert tipo_de_cargo(rotulo) == tipo


@pytest.mark.parametrize(
    "rotulo",
    ["SIROC", "INDIRECTO", "OTROS CARGOS"],
)
def test_hdu001_esc06_rotulo_ajeno_no_recibe_tipo(rotulo: str) -> None:
    assert tipo_de_cargo(rotulo) is None


def test_hdu001_esc05_rendimiento_y_porcentaje_exactos() -> None:
    rend = interpretar_numero(Decimal("0.3278"), Rendimiento)
    assert isinstance(rend, Rendimiento)
    assert rend.valor == Decimal("0.3278")
    pct = interpretar_numero(Decimal("0.16"), Porcentaje)
    assert isinstance(pct, Porcentaje)
    assert interpretar_numero("#REF!", Rendimiento) == CausaHallazgo.ERROR_DE_FORMULA


def test_hdu001_esc06_fecha_de_la_cabecera() -> None:
    assert interpretar_fecha("2025-09-01 00:00:00") == "2025-09-01"
    assert interpretar_fecha("01/09/2025") == CausaHallazgo.FECHA_NO_RECONOCIDA
    assert interpretar_fecha("2025-09-01 10:30:00") == CausaHallazgo.FECHA_NO_RECONOCIDA
    assert interpretar_fecha(45901) == CausaHallazgo.FECHA_NO_RECONOCIDA
    assert interpretar_fecha(None) == CausaHallazgo.VALOR_AUSENTE
    assert interpretar_fecha("#REF!") == CausaHallazgo.ERROR_DE_FORMULA


def test_hdu001_esc05_hoja_sin_estructura_de_apu_no_es_analisis() -> None:
    assert analizar_hoja_apu("X", [fila_apu(1, "Solo texto")]) is None
    assert analizar_hoja_apu("X", [fila_apu(1, "MATERIAL")]) is None
    assert (
        analizar_hoja_apu(
            "X",
            [fila_apu(1, "PRECIO UNITARIO"), fila_apu(2, "MATERIAL")],
        )
        is None
    )
    assert (
        analizar_hoja_apu(
            "X",
            [
                fila_apu(8, "Código", "ENCHAPES", "Unidad", "Cantidad", "P.U.", "IMPORTE"),
            ],
        )
        is None
    )


def test_hdu001_esc05_analisis_sintetico_completo() -> None:
    hoja = "APU SINTETICO"
    resultado = analizar_hoja_apu(hoja, hoja_apu_sintetica())
    assert resultado is not None
    assert resultado.cabecera.codigo == "P-001"
    assert resultado.cabecera.unidad == "M2"
    assert resultado.cabecera.fecha == "2025-09-01"
    assert resultado.cabecera.analista == "Analista Prueba"
    assert resultado.cabecera.precio_unitario == Dinero("158.93")
    assert len([i for i in resultado.insumos if i.tipo == TipoInsumo.MATERIAL]) == 2
    assert len([i for i in resultado.insumos if i.tipo == TipoInsumo.MANO_OBRA]) == 1
    assert len(resultado.cargos) == 6
    assert resultado.totales.material == Dinero("27.5")
    assert resultado.totales.mano_obra == Dinero("100")
    assert resultado.totales.costo_directo == Dinero("127.5")
    assert resultado.totales.cargos == Dinero("31.43")
    assert resultado.totales.precio_unitario == Dinero("158.93")
    assert resultado.hallazgos == ()


@pytest.mark.parametrize(
    "rotulo_material",
    ["MATERIAL:", "MATERIAL ", "Material"],
)
def test_hdu001_esc05_variantes_de_rotulo_de_bloque(rotulo_material: str) -> None:
    filas = hoja_apu_sintetica()
    filas = [(n, (rotulo_material,) + f[1:]) if n == 6 else (n, f) for n, f in filas]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    assert len(resultado.insumos) == 3
    assert resultado.hallazgos == ()


def test_hdu001_esc05_variantes_rotulo_mano_de_obra_y_fila_kg() -> None:
    filas = list(hoja_apu_sintetica())
    filas = [(n, ("MANO DE OBRA:",) + f[1:]) if n == 10 else (n, f) for n, f in filas]
    filas.append((95, ("KG", None, None, "KG")))
    filas.sort(key=lambda x: x[0])
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    assert len(resultado.insumos) == 3
    assert resultado.hallazgos == ()


def test_hdu001_esc05_viaticos_por_rol_son_cargos_viaticos() -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica())
    assert resultado is not None
    viaticos = [c for c in resultado.cargos if c.tipo == TipoCargo.VIATICOS]
    assert len(viaticos) == 2
    assert {c.rotulo for c in viaticos} == {"OFICIAL TABLAROQUERO", "AYUDANTE TABLAROQUERO"}
    assert not any(h.causa == CausaHallazgo.CARGO_DESCONOCIDO for h in resultado.hallazgos)
    indirectos = next(c for c in resultado.cargos if c.tipo == TipoCargo.INDIRECTOS)
    assert indirectos.rotulo == "INDIRECTOS"


def test_hdu001_esc05_encabezado_cargos_indirectos_tras_viaticos_no_es_cargo() -> None:
    """E-2 · fila «CARGOS INDIRECTOS» con «%» en D tras viáticos (hoja `01` ENITI)."""
    filas = list(hoja_apu_sintetica())
    insertadas: list[tuple[int, tuple[ValorCelda, ...]]] = [
        (18, (None, None, None, "TOTAL VIATICOS  Y HOSPEDAJE ", None, None, Decimal("0"))),
        (19, ("CARGOS INDIRECTOS ", None, None, "%")),
    ]
    desplazadas = [(n + 2, f) if n >= 18 else (n, f) for n, f in filas]
    desplazadas.extend(insertadas)
    desplazadas.sort(key=lambda x: x[0])
    resultado = analizar_hoja_apu("01", desplazadas)
    assert resultado is not None
    assert not any(c.rotulo.startswith("CARGOS INDIRECTOS") for c in resultado.cargos)
    assert not any(h.causa == CausaHallazgo.PU_NO_VERIFICABLE for h in resultado.hallazgos)


def test_hdu001_esc05_filas_de_subtotal_se_ignoran() -> None:
    filas: list[tuple[int, tuple[ValorCelda, ...]]] = []
    for numero, fila in hoja_apu_sintetica():
        filas.append((numero + 3, fila) if numero >= 21 else (numero, fila))
    filas.extend(
        [
            (20, ("SUBTOTAL", None, None, None, None, None, Decimal("999"))),
            (21, ("TOTAL MATERIAL", None, None, None, None, None, Decimal("888"))),
            (22, (None, None, None, None, None, None, Decimal("777"))),
        ]
    )
    filas.sort(key=lambda x: x[0])
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    assert len(resultado.insumos) == 3
    assert len(resultado.cargos) == 6
    assert resultado.hallazgos == ()
    assert all(c.rotulo != "SUBTOTAL" for c in resultado.cargos)


def test_hdu001_esc06_cargo_desconocido_se_conserva_sin_tipo() -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica(siroc=True))
    assert resultado is not None
    siroc = next(c for c in resultado.cargos if c.rotulo == "SIROC")
    assert siroc.tipo is None
    assert siroc.porcentaje == Porcentaje("0.01")
    assert siroc.base == Dinero("127.5")
    assert siroc.importe == Dinero("1.275")
    desconocidos = [h for h in resultado.hallazgos if h.causa == CausaHallazgo.CARGO_DESCONOCIDO]
    assert len(desconocidos) == 1
    _expect(
        desconocidos[0],
        Hallazgo(
            causa=CausaHallazgo.CARGO_DESCONOCIDO,
            hoja="H",
            fila=15,
            columna="A",
            valor_original="SIROC",
            detalle=None,
        ),
    )
    assert resultado.totales.precio_unitario == Dinero("160.205")
    assert not any(h.causa == CausaHallazgo.PU_NO_CUADRA for h in resultado.hallazgos)


def test_hdu001_esc06_pu_de_cabecera_con_ref() -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica(pu_cabecera="#REF!"))
    assert resultado is not None
    assert resultado.cabecera.precio_unitario is None
    _expect(
        next(h for h in resultado.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=5,
            columna="C",
            valor_original="#REF!",
            detalle=None,
        ),
    )
    assert not any(h.causa == CausaHallazgo.PU_NO_VERIFICABLE for h in resultado.hallazgos)


def test_hdu001_esc06_celdas_de_insumo_ilegibles() -> None:
    filas = hoja_apu_sintetica(celdas_rotas={(8, "F"): "#REF!", (9, "E"): "veinte"})
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    insumo_ref = next(i for i in resultado.insumos if i.fila == 8)
    assert insumo_ref.rendimiento is None
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 8 and h.columna == "F"),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=8,
            columna="F",
            valor_original="#REF!",
            detalle=None,
        ),
    )
    insumo_veinte = next(i for i in resultado.insumos if i.fila == 9)
    assert insumo_veinte.costo_unitario is None
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 9 and h.columna == "E"),
        Hallazgo(
            causa=CausaHallazgo.NO_ES_NUMERO,
            hoja="H",
            fila=9,
            columna="E",
            valor_original="veinte",
            detalle=None,
        ),
    )
    filas2 = hoja_apu_sintetica(celdas_rotas={(8, "F"): Decimal("-1")})
    insumo_neg = analizar_hoja_apu("H", filas2)
    assert insumo_neg is not None
    assert next(i for i in insumo_neg.insumos if i.fila == 8).rendimiento is None
    _expect(
        next(h for h in insumo_neg.hallazgos if h.fila == 8 and h.columna == "F"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_NEGATIVO,
            hoja="H",
            fila=8,
            columna="F",
            valor_original="-1",
            detalle=None,
        ),
    )
    filas3 = hoja_apu_sintetica(celdas_rotas={(9, "F"): None})
    insumo_vacio = analizar_hoja_apu("H", filas3)
    assert insumo_vacio is not None
    assert next(i for i in insumo_vacio.insumos if i.fila == 9).rendimiento is None
    _expect(
        next(h for h in insumo_vacio.hallazgos if h.fila == 9 and h.columna == "F"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=9,
            columna="F",
            valor_original=None,
            detalle=None,
        ),
    )


def test_hdu001_esc06_pu_no_verificable() -> None:
    filas = hoja_apu_sintetica(celdas_rotas={(8, "G"): "#REF!"})
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    _expect(
        next(h for h in resultado.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=8,
            columna="G",
            valor_original="#REF!",
            detalle=None,
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.causa == CausaHallazgo.PU_NO_VERIFICABLE),
        Hallazgo(
            causa=CausaHallazgo.PU_NO_VERIFICABLE,
            hoja="H",
            fila=21,
            columna="G",
            valor_original="158.93",
            detalle="valores ilegibles en las filas: 8",
        ),
    )
    assert resultado.totales.material is None
    assert resultado.totales.costo_directo is None
    assert resultado.totales.precio_unitario is None
    assert not any(h.causa == CausaHallazgo.PU_NO_CUADRA for h in resultado.hallazgos)

    filas_pie = hoja_apu_sintetica(pie="#REF!")
    resultado2 = analizar_hoja_apu("H", filas_pie)
    assert resultado2 is not None
    _expect(
        next(h for h in resultado2.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=21,
            columna="G",
            valor_original="#REF!",
            detalle=None,
        ),
    )
    _expect(
        next(h for h in resultado2.hallazgos if h.causa == CausaHallazgo.PU_NO_VERIFICABLE),
        Hallazgo(
            causa=CausaHallazgo.PU_NO_VERIFICABLE,
            hoja="H",
            fila=21,
            columna="G",
            valor_original="#REF!",
            detalle="valores ilegibles en las filas: 21",
        ),
    )


@pytest.mark.parametrize(
    ("pie", "debe_cuadrar"),
    [
        (Decimal("158.94"), True),
        (Decimal("158.92"), True),
        (Decimal("158.9400001"), False),
        (Decimal("158.9199999"), False),
    ],
)
def test_hdu001_esc06_frontera_de_tolerancia(pie: Decimal, debe_cuadrar: bool) -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica(pie=pie))
    assert resultado is not None
    if debe_cuadrar:
        assert resultado.hallazgos == ()
    else:
        detalle = (
            "archivo 158.9400001; reconstruido 158.930; diferencia -0.0100001"
            if pie == Decimal("158.9400001")
            else "archivo 158.9199999; reconstruido 158.930; diferencia 0.0100001"
        )
        _expect(
            next(h for h in resultado.hallazgos if h.causa == CausaHallazgo.PU_NO_CUADRA),
            Hallazgo(
                causa=CausaHallazgo.PU_NO_CUADRA,
                hoja="H",
                fila=21,
                columna="G",
                valor_original=str(pie),
                detalle=detalle,
            ),
        )


def test_hdu001_esc06_pu_que_no_cuadra_reporta_cifras() -> None:
    totales = TotalesAnalisis(
        material=Dinero(0),
        mano_obra=Dinero(0),
        costo_directo=Dinero(0),
        cargos=Dinero(0),
        precio_unitario=Dinero("641.3608310977561"),
    )
    hallazgo = verificar_precio_unitario(
        "H",
        60,
        Dinero("641.38"),
        "641.38",
        totales,
        (),
    )
    assert hallazgo is not None
    _expect(
        hallazgo,
        Hallazgo(
            causa=CausaHallazgo.PU_NO_CUADRA,
            hoja="H",
            fila=60,
            columna="G",
            valor_original="641.38",
            detalle=("archivo 641.38; reconstruido 641.3608310977561; diferencia -0.0191689022439"),
        ),
    )


@pytest.mark.parametrize(
    ("unidad", "esperada"),
    [
        ("CAJA ", "CAJA"),
        ("pza", "PZA"),
    ],
)
def test_hdu001_esc10_unidad_de_insumo_normalizada_sin_hallazgo(unidad: str, esperada: str) -> None:
    filas = list(hoja_apu_sintetica())
    filas = [
        (n, f)
        if n != 8
        else (8, ("MATERIAL UNO", None, None, unidad, Decimal("1"), Decimal("1"), Decimal("1")))
        for n, f in filas
    ]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    insumo = next(i for i in resultado.insumos if i.fila == 8)
    assert insumo.unidad == esperada
    assert not any(
        h.fila == 8 and h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA for h in resultado.hallazgos
    )


def test_hdu001_esc10_unidad_de_insumo_fuera_del_catalogo() -> None:
    filas = hoja_apu_sintetica()
    filas = [
        (n, f) if n != 8 else (8, ("X", None, None, "LT", Decimal("1"), Decimal("1"), Decimal("1")))
        for n, f in filas
    ]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    insumo = next(i for i in resultado.insumos if i.fila == 8)
    assert insumo.unidad == "LT"
    _expect(
        next(h for h in resultado.hallazgos if h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA),
        Hallazgo(
            causa=CausaHallazgo.UNIDAD_NO_RECONOCIDA,
            hoja="H",
            fila=8,
            columna="D",
            valor_original="LT",
            detalle=None,
        ),
    )


def test_hdu001_esc06_cabecera_incompleta() -> None:
    filas = hoja_apu_sintetica(analista="  ")
    filas = [f for f in filas if f[0] not in (3, 4)]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    _expect(
        next(
            h
            for h in resultado.hallazgos
            if h.causa == CausaHallazgo.VALOR_AUSENTE
            and h.detalle == "sin rótulo «fecha» en la cabecera"
        ),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=None,
            columna=None,
            valor_original=None,
            detalle="sin rótulo «fecha» en la cabecera",
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.detalle == "sin rótulo «unidad» en la cabecera"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=None,
            columna=None,
            valor_original=None,
            detalle="sin rótulo «unidad» en la cabecera",
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 1 and h.columna == "B"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=1,
            columna="B",
            valor_original="  ",
            detalle=None,
        ),
    )


def test_hdu001_esc06_cabecera_campos_ilegibles() -> None:
    filas = [
        (n, ("ANALISTA:", "#REF!") + f[1:]) if n == 1 else (n, f) for n, f in hoja_apu_sintetica()
    ]
    filas = [(n, ("UNIDAD:", None, "LT")) if n == 3 else (n, f) for n, f in filas]
    filas = [(n, ("FECHA:", None, "")) if n == 4 else (n, f) for n, f in filas]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    assert resultado.cabecera.unidad == "LT"
    assert resultado.cabecera.fecha is None
    assert resultado.cabecera.analista is None
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 3 and h.columna == "C"),
        Hallazgo(
            causa=CausaHallazgo.UNIDAD_NO_RECONOCIDA,
            hoja="H",
            fila=3,
            columna="C",
            valor_original="LT",
            detalle=None,
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 4 and h.columna == "C"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=4,
            columna="C",
            valor_original="",
            detalle=None,
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 1 and h.columna == "B"),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=1,
            columna="B",
            valor_original="#REF!",
            detalle=None,
        ),
    )


def test_hdu001_esc06_cargo_con_base_o_importe_ausente() -> None:
    filas = list(hoja_apu_sintetica())
    filas = [
        (n, f)
        if n != 14
        else (14, ("HERRAMIENTA MENOR", None, None, Decimal("0.01"), None, None, None))
        for n, f in filas
    ]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 14 and h.columna == "E"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=14,
            columna="E",
            valor_original=None,
            detalle=None,
        ),
    )
    _expect(
        next(h for h in resultado.hallazgos if h.fila == 14 and h.columna == "G"),
        Hallazgo(
            causa=CausaHallazgo.VALOR_AUSENTE,
            hoja="H",
            fila=14,
            columna="G",
            valor_original=None,
            detalle=None,
        ),
    )


def test_hdu001_esc05_totales_con_precision_completa() -> None:
    filas = list(hoja_apu_sintetica())
    filas = [
        (n, f)
        if n != 14
        else (
            14,
            (
                "HERRAMIENTA MENOR",
                None,
                None,
                Decimal("0.01"),
                Decimal("127.5"),
                None,
                Decimal("14.613323999999999"),
            ),
        )
        for n, f in filas
    ]
    resultado = analizar_hoja_apu("H", filas)
    assert resultado is not None
    assert resultado.totales.cargos is not None
    assert resultado.totales.cargos.valor == Decimal("44.768323999999999")


def test_hdu001_esc05_resultado_inmutable_y_en_decimal() -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica())
    assert resultado is not None
    with pytest.raises(FrozenInstanceError):
        resultado.hoja = "otro"  # type: ignore[misc]
    insumo = resultado.insumos[0]
    with pytest.raises(FrozenInstanceError):
        insumo.descripcion = "x"  # type: ignore[misc]
    assert isinstance(insumo.costo_unitario, Dinero)
    assert isinstance(insumo.costo_unitario.valor, Decimal)
    for cargo in resultado.cargos:
        if cargo.importe is not None:
            assert isinstance(cargo.importe.valor, Decimal)
        if cargo.porcentaje is not None:
            assert isinstance(cargo.porcentaje.valor, Decimal)


def test_hdu001_esc05_codigo_de_cabecera() -> None:
    resultado = analizar_hoja_apu("H", hoja_apu_sintetica(codigo="620001"))
    assert resultado is not None
    assert resultado.cabecera.codigo == "620001"
    assert resultado.cabecera.fila_codigo == 2
    resultado2 = analizar_hoja_apu("H", hoja_apu_sintetica(codigo=""))
    assert resultado2 is not None
    assert resultado2.cabecera.codigo is None
    assert not any(h.causa == CausaHallazgo.ERROR_DE_FORMULA for h in resultado2.hallazgos)
    resultado3 = analizar_hoja_apu("H", hoja_apu_sintetica(codigo="#REF!"))
    assert resultado3 is not None
    assert resultado3.cabecera.codigo is None
    _expect(
        next(h for h in resultado3.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA),
        Hallazgo(
            causa=CausaHallazgo.ERROR_DE_FORMULA,
            hoja="H",
            fila=2,
            columna="C",
            valor_original="#REF!",
            detalle=None,
        ),
    )
