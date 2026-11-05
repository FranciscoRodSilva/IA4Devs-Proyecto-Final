"""Clasificación de libro TKT-015a, fila A2b: SIN_APU, DUPLICADO y clasificar_libro."""

from __future__ import annotations

from cimenta.presupuesto.dominio.analisis import AnalisisDelLibro
from cimenta.presupuesto.dominio.asociacion_analisis import asociar_analisis
from cimenta.presupuesto.dominio.catalogo import (
    ERRORES_DE_FORMULA,
    CatalogoLeido,
    CausaHallazgo,
)
from cimenta.presupuesto.dominio.clasificacion_importacion import (
    _enumerar,
    clasificar_libro,
    detectar_duplicados,
    errores_sin_apu,
)
from cimenta.presupuesto.dominio.importacion import TipoErrorImportacion
from herramientas.soporte_tkt014 import catalogo_con_codigos, leer_apu_en_memoria
from herramientas.soporte_tkt015 import catalogo_con_descripciones, hallazgo


def test_hdu001_esc07_codigo_sin_apu() -> None:
    """TC-10 · HDU-001 esc. 7 · CA-4 — un SIN_APU por código sin hoja de APU."""
    catalogo = catalogo_con_codigos([(10, "P-001"), (20, "P-001"), (30, "P-003"), (40, "P-003")])
    catalogo = CatalogoLeido(
        hoja=catalogo.hoja,
        fila_encabezado=catalogo.fila_encabezado,
        nodos=catalogo.nodos,
        conceptos=catalogo.conceptos,
        hallazgos=(),
    )
    errores = errores_sin_apu(catalogo, ("P-003",))
    assert len(errores) == 1
    e = errores[0]
    assert e.tipo is TipoErrorImportacion.SIN_APU
    assert e.hoja == "CATALOGO"
    assert e.fila == 30
    assert e.columna == "A"
    assert e.valor_original == "P-003"
    assert e.mensaje == (
        "El concepto con código «P-003» no tiene hoja de análisis de precio unitario. "
        "Sin ese análisis no se puede calcular la explosión de insumos de ese concepto."
    )


def test_hdu001_esc09_duplicado_con_descripciones_distintas() -> None:
    """TC-11 · HDU-001 esc. 9 · CA-7 — un DUPLICADO por código con descripciones distintas."""
    catalogo = catalogo_con_descripciones(
        [
            (12, "620001", "MURO STD"),
            (45, "620001", "MURO STD"),
            (90, "620001", "PLAFON"),
        ]
    )
    errores = detectar_duplicados(catalogo)
    assert len(errores) == 1
    e = errores[0]
    assert e.tipo is TipoErrorImportacion.DUPLICADO
    assert e.fila == 12 and e.columna == "A" and e.valor_original == "620001"
    assert e.mensaje == (
        "El código «620001» aparece con descripciones distintas en las filas 12, 45 y 90: "
        "«MURO STD» en las filas 12 y 45 y «PLAFON» en la fila 90. "
        "Un código identifica un solo concepto."
    )


def test_hdu001_esc09_misma_descripcion_normalizada_no_es_duplicado() -> None:
    """TC-12 · HDU-001 esc. 9 · CA-8 — misma clave normalizada no es DUPLICADO."""
    catalogo = catalogo_con_descripciones(
        [
            (1, "P-001", " muro  std"),
            (2, "P-001", "MURO STD"),
            (3, "P-001", "Muro\tStd "),
        ]
    )
    assert detectar_duplicados(catalogo) == ()
    catalogo_ref = catalogo_con_descripciones(
        [(1, "#REF!", "A"), (2, "#REF!", "B")],
    )
    assert detectar_duplicados(catalogo_ref) == ()
    assert "#REF!" in ERRORES_DE_FORMULA


def test_hdu001_esc06_ningun_hallazgo_se_pierde() -> None:
    """TC-13 · HDU-001 esc. 6 · CA-10 — seis errores en el orden declarado."""
    conceptos = catalogo_con_descripciones(
        [
            (10, "P-001", "A"),
            (20, "P-002", "B"),
            (30, "P-002", "C"),
            (40, "P-004", "D"),
        ]
    )
    h_cat1 = hallazgo(CausaHallazgo.ERROR_DE_FORMULA, fila=10, columna="F", valor="#REF!")
    h_cat2 = hallazgo(CausaHallazgo.UNIDAD_NO_RECONOCIDA, fila=20, columna="C", valor="ZZZ")
    a1 = leer_apu_en_memoria("APU-1", codigo="P-001", siroc=True)
    h_libro = hallazgo(
        CausaHallazgo.CODIGO_EN_VARIAS_HOJAS,
        hoja="APU-X",
        fila=12,
        columna="C",
        valor="P-009",
        detalle="APU-Y",
    )
    libro = AnalisisDelLibro(
        catalogo=CatalogoLeido(
            hoja=conceptos.hoja,
            fila_encabezado=8,
            nodos=(),
            conceptos=conceptos.conceptos,
            hallazgos=(h_cat1, h_cat2),
        ),
        analisis=(a1,),
        asociaciones=(),
        codigos_sin_analisis=("P-004",),
        insumos_por_crear=(),
        hallazgos=(h_libro,),
    )
    clas = clasificar_libro(libro)
    assert len(clas.errores) == 6
    tipos = [e.tipo for e in clas.errores]
    assert tipos == [
        TipoErrorImportacion.REF_ROTA,
        TipoErrorImportacion.UNIDAD_DESCONOCIDA,
        TipoErrorImportacion.DUPLICADO,
        TipoErrorImportacion.SIN_APU,
        TipoErrorImportacion.UNIDAD_DESCONOCIDA,
        TipoErrorImportacion.DUPLICADO,
    ]


def test_tkt015_filas_y_hojas_rechazadas() -> None:
    """TC-14 · CA-11 · CA-S1 · P3 — filas y hojas rechazadas según el tipo de error."""
    catalogo = catalogo_con_descripciones(
        [
            (10, "P-001", "DESC A"),
            (20, "P-001", "DESC B"),
            (30, "P-002", "SOLO"),
            (40, "P-003", "X"),
        ]
    )
    cat_base = catalogo_con_descripciones([(10, "P-010", "UNICO")])
    a_doble1 = leer_apu_en_memoria("APU-D1", codigo="P-010")
    a_doble2 = leer_apu_en_memoria("APU-D2", codigo="P-010")
    _, _, hall_doble = asociar_analisis((a_doble1, a_doble2), cat_base)
    a_siroc = leer_apu_en_memoria("APU-SIROC", siroc=True)
    h_titulo = hallazgo(CausaHallazgo.NOMBRE_ILEGIBLE, fila=5, columna="B", valor="#REF!")
    libro = AnalisisDelLibro(
        catalogo=CatalogoLeido(
            hoja=catalogo.hoja,
            fila_encabezado=8,
            nodos=(),
            conceptos=catalogo.conceptos,
            hallazgos=(
                h_titulo,
                hallazgo(CausaHallazgo.ERROR_DE_FORMULA, fila=40, columna="F", valor="#REF!"),
            ),
        ),
        analisis=(a_doble1, a_doble2, a_siroc),
        asociaciones=(),
        codigos_sin_analisis=("P-003",),
        insumos_por_crear=(),
        hallazgos=hall_doble,
    )
    clas = clasificar_libro(libro)
    assert 10 in clas.filas_rechazadas and 20 in clas.filas_rechazadas
    assert 40 in clas.filas_rechazadas
    assert 5 not in clas.filas_rechazadas
    assert 30 not in clas.filas_rechazadas
    assert "APU-D1" in clas.hojas_rechazadas and "APU-D2" in clas.hojas_rechazadas
    assert "APU-SIROC" in clas.hojas_rechazadas
    for fila in clas.filas_rechazadas:
        assert fila in {c.fila for c in catalogo.conceptos}


def test_hdu001_esc09_mensaje_de_duplicado_en_espanol() -> None:
    """TC-15 · HDU-001 esc. 9 · CA-7 — _enumerar y mensaje de tres grupos."""
    assert _enumerar(["a"]) == "a"
    assert _enumerar(["a", "b"]) == "a y b"
    assert _enumerar(["a", "b", "c"]) == "a, b y c"
    assert _enumerar(["a", "b", "c", "d"]) == "a, b, c y d"
    catalogo = catalogo_con_descripciones(
        [
            (20, "620002", "MURO"),
            (50, "620002", "MURO"),
            (30, "620002", "PLAFON"),
            (40, "620002", "CAJILLO"),
        ]
    )
    errores = detectar_duplicados(catalogo)
    assert len(errores) == 1
    assert errores[0].mensaje == (
        "El código «620002» aparece con descripciones distintas en las filas 20, 30, 40 y 50: "
        "«MURO» en las filas 20 y 50, «PLAFON» en la fila 30 y «CAJILLO» en la fila 40. "
        "Un código identifica un solo concepto."
    )
