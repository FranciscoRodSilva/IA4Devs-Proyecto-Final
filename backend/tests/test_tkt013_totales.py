"""Totales del catálogo leído (TKT-013b · S1): TC-41 a TC-43."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cimenta.presupuesto.dominio.catalogo import CatalogoLeido, ConceptoLeido, Ruta
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    encabezado_eniti,
    leer_catalogo_bytes,
    metadatos_siete_filas,
)

if TYPE_CHECKING:
    from conftest import LibroCatalogo


def _totalizar(catalogo: CatalogoLeido):
    from cimenta.presupuesto.dominio.totales_catalogo import totalizar

    return totalizar(catalogo)


def _importe_calculado(concepto: ConceptoLeido):
    from cimenta.presupuesto.dominio.totales_catalogo import importe_calculado

    return importe_calculado(concepto)


def test_hdu001_esc05_importe_de_concepto_es_cantidad_por_precio() -> None:
    """TC-43 · HDU-001 esc. 5 · CA-13 — producto exacto y None si falta dato."""
    from tipos_base import Cantidad, Dinero

    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    concepto = ConceptoLeido(
        fila=1,
        codigo="P-001",
        descripcion="x",
        unidad="M2",
        cantidad=Cantidad("16.089"),
        precio_unitario=Dinero("668.69"),
        importe=None,
        ruta=ruta,
    )
    assert _importe_calculado(concepto) == Dinero("10758.55341")

    sin_precio = ConceptoLeido(
        fila=2,
        codigo="P-002",
        descripcion="y",
        unidad="M2",
        cantidad=Cantidad("1"),
        precio_unitario=None,
        importe=None,
        ruta=ruta,
    )
    assert _importe_calculado(sin_precio) is None


def test_hdu001_esc05_importe_no_calculable_nunca_es_cero(
    archivo_union: bytes, libro_catalogo: LibroCatalogo
) -> None:
    """TC-42 · HDU-001 esc. 5 · CA-13 · P7 — Union y un concepto sin P.U."""
    cat_union = leer_catalogo_bytes(archivo_union)
    totales_union = _totalizar(cat_union)
    assert totales_union.importe is None

    libro = libro_catalogo
    libro.nueva_hoja(HOJA_ENITI)
    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "R"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "N"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "A"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "P"))
    for fila in range(13, 18):
        libro.escribir_fila(
            HOJA_ENITI,
            fila,
            (f"P-{fila}", "ok", "M2", 1, 10, 10),
        )
    libro.escribir_fila(HOJA_ENITI, 18, ("P-SIN-PU", "sin pu", "M2", 1, None, None))
    for fila in range(19, 23):
        libro.escribir_fila(
            HOJA_ENITI,
            fila,
            (f"P-{fila}", "ok", "M2", 1, 10, 10),
        )

    cat_parcial = leer_catalogo_bytes(libro.bytes())
    totales_parcial = _totalizar(cat_parcial)
    assert totales_parcial.importe is None
    assert totales_parcial.conceptos == 10


def test_hdu001_esc05_totales_de_eniti(archivo_eniti: bytes) -> None:
    """TC-41 · HDU-001 esc. 5 · CA-13 — conteos E-8 e importe cuantizado."""
    from cimenta.presupuesto.dominio.catalogo import Profundidad
    from cimenta.presupuesto.dominio.totales_catalogo import importe_calculado
    from tipos_base import Dinero, sumar

    cat = leer_catalogo_bytes(archivo_eniti)
    totales = _totalizar(cat)

    assert totales.conceptos == 5028
    assert totales.niveles == sum(1 for n in cat.nodos if n.profundidad is Profundidad.NIVEL)
    assert totales.areas == sum(1 for n in cat.nodos if n.profundidad is Profundidad.AREA)
    assert totales.partidas == sum(1 for n in cat.nodos if n.profundidad is Profundidad.PARTIDA)

    assert totales.importe is not None
    importes = []
    for concepto in cat.conceptos:
        calculado = importe_calculado(concepto)
        assert calculado is not None
        importes.append(calculado)
    esperado = sumar(importes, Dinero)
    assert totales.importe.cuantizar() == esperado.cuantizar()
