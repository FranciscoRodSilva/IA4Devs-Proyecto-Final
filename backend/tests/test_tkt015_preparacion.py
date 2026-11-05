"""Preparación TKT-015a, fila A3: armar_preparacion excluye lo rechazado."""

from __future__ import annotations

from cimenta.presupuesto.dominio.analisis import AnalisisDelLibro
from cimenta.presupuesto.dominio.asociacion_analisis import asociar_analisis, proponer_insumos
from cimenta.presupuesto.dominio.catalogo import CatalogoLeido, CausaHallazgo
from cimenta.presupuesto.dominio.clasificacion_importacion import clasificar_libro
from cimenta.presupuesto.dominio.preparacion_importacion import armar_preparacion
from herramientas.soporte_tkt014 import leer_apu_en_memoria
from herramientas.soporte_tkt015 import catalogo_con_descripciones, hallazgo


def _libro_como_tc14() -> AnalisisDelLibro:
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
    insumos, _ = proponer_insumos((a_doble1, a_doble2, a_siroc), {})
    return AnalisisDelLibro(
        catalogo=CatalogoLeido(
            hoja=catalogo.hoja,
            fila_encabezado=8,
            nodos=(),
            conceptos=catalogo.conceptos,
            hallazgos=(
                hallazgo(CausaHallazgo.NOMBRE_ILEGIBLE, fila=5, columna="B", valor="#REF!"),
                hallazgo(CausaHallazgo.ERROR_DE_FORMULA, fila=40, columna="F", valor="#REF!"),
            ),
        ),
        analisis=(a_doble1, a_doble2, a_siroc),
        asociaciones=(),
        codigos_sin_analisis=("P-003",),
        insumos_por_crear=insumos,
        hallazgos=hall_doble,
    )


def test_hdu001_esc06_preparacion_excluye_lo_rechazado() -> None:
    """TC-16 · HDU-001 esc. 6 · CA-11 · CA-S1 — preparación sin filas ni hojas rechazadas."""
    libro = _libro_como_tc14()
    clas = clasificar_libro(libro)
    prep = armar_preparacion(libro, clas)

    assert prep.filas_leidas == 4
    assert prep.filas_rechazadas == 3
    assert prep.filas_validas == 1
    assert [c.fila for c in prep.conceptos] == [30]
    assert prep.analisis == ()
    assert prep.asociaciones == ()
    assert len(prep.insumos_por_crear) > 0
    assert prep.nodos == libro.catalogo.nodos
