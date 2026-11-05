"""TKT-015a · Análisis de contenido sin base (fila A5): TC-19 a TC-23."""

from __future__ import annotations

import json
import pickle
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, NodoLeido, Profundidad, Ruta
from cimenta.presupuesto.dominio.importacion import TipoErrorImportacion
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from cimenta.presupuesto.infraestructura.preparacion_json import (
    FORMATO_PREPARACION,
    preparacion_a_json,
)
from herramientas.soporte_tkt015 import CampoConcepto, libro_sintetico
from tipos_base import Cantidad, Dinero, Rendimiento

if TYPE_CHECKING:
    from conftest import LibroCatalogo


def _sin_float(obj: object) -> None:
    if isinstance(obj, float):
        raise AssertionError("el árbol JSON contiene un float")
    if isinstance(obj, dict):
        for valor in obj.values():
            _sin_float(valor)
    elif isinstance(obj, list):
        for valor in obj:
            _sin_float(valor)


def test_tkt015_analizar_contenido_libro_valido(libro_catalogo: LibroCatalogo) -> None:
    """TC-19 · CA-1 — libro válido: sin errores y preparación con veinte conceptos."""
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    contenido = libro_sintetico(libro_catalogo, conceptos=20)
    resultado = analizar_contenido(contenido, {})

    assert resultado.errores == ()
    assert resultado.filas_leidas == 20
    assert resultado.filas_validas == 20
    assert resultado.filas_rechazadas == 0
    prep = resultado.preparacion
    assert prep["formato"] == FORMATO_PREPARACION
    assert len(cast(list[Any], prep["conceptos"])) == 20
    assert len(cast(list[Any], prep["analisis"])) == 2
    assert len(cast(list[Any], prep["asociaciones"])) == 2
    assert len(cast(list[Any], prep["insumos_por_crear"])) == 3


def test_tkt015_analizar_contenido_ref_rota_197_en_preparacion(
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-20 · CA-2, CA-S1 — filas rotas fuera de la preparación; seis REF_ROTA."""
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    _campos_rotos: tuple[CampoConcepto, ...] = ("precio_unitario", "importe")
    rotos: dict[tuple[int, CampoConcepto], str] = {
        (fila, campo): "#REF!" for fila in (20, 30, 40) for campo in _campos_rotos
    }
    contenido = libro_sintetico(libro_catalogo, rotos=rotos)
    resultado = analizar_contenido(contenido, {})

    refs = [e for e in resultado.errores if e.tipo is TipoErrorImportacion.REF_ROTA]
    assert len(refs) == 6
    conceptos_prep = cast(list[dict[str, Any]], resultado.preparacion["conceptos"])
    filas_en_prep = {c["fila"] for c in conceptos_prep}
    assert len(conceptos_prep) == 197
    assert filas_en_prep.isdisjoint({20, 30, 40})


def test_tkt015_preparacion_json_decimal_como_cadena_sin_cuantizar() -> None:
    """TC-21 · CA-11 — cifras como cadena con precisión completa, sin float."""
    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    concepto = ConceptoLeido(
        fila=10,
        codigo="X",
        descripcion="Prueba",
        unidad="M2",
        cantidad=Cantidad(Decimal("16.089")),
        precio_unitario=Dinero(Decimal("641.3608310977561")),
        importe=Dinero(Decimal("641.3608310977561")),
        ruta=ruta,
    )
    insumo = InsumoLeido(
        fila=8,
        tipo=TipoInsumo.MATERIAL,
        descripcion="M",
        clave="M",
        unidad="PZA",
        costo_unitario=None,
        rendimiento=Rendimiento(Decimal("0.3278")),
        cargo=None,
    )
    analisis = AnalisisLeido(
        hoja="APU X",
        cabecera=CabeceraLeida(
            fila_codigo=2,
            codigo="X",
            unidad="M2",
            fecha=None,
            analista=None,
            precio_unitario=None,
        ),
        insumos=(insumo,),
        cargos=(),
        fila_precio_unitario=21,
        precio_unitario=None,
        totales=TotalesAnalisis(None, None, None, None, None),
        hallazgos=(),
    )
    prep = Preparacion(
        hoja_catalogo="CATALOGO",
        nodos=(),
        conceptos=(concepto,),
        analisis=(analisis,),
        asociaciones=(),
        insumos_por_crear=(),
        filas_leidas=1,
        filas_validas=1,
        filas_rechazadas=0,
    )

    documento = preparacion_a_json(prep)
    c = cast(list[dict[str, Any]], documento["conceptos"])[0]
    assert c["precio_unitario"] == "641.3608310977561"
    assert c["cantidad"] == "16.089"
    assert isinstance(c["precio_unitario"], str)
    analisis_doc = cast(list[dict[str, Any]], documento["analisis"])
    insumos_doc = cast(list[dict[str, Any]], analisis_doc[0]["insumos"])
    ins = insumos_doc[0]
    assert ins["rendimiento"] == "0.3278"
    assert isinstance(ins["rendimiento"], str)
    json.dumps(documento)
    _sin_float(documento)


def test_tkt015_preparacion_json_none_a_null() -> None:
    """TC-22 · CA-11 — ausentes serializados como null en el formato."""
    nodo = NodoLeido(fila=5, profundidad=Profundidad.AREA, nombre=None)
    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    concepto = ConceptoLeido(
        fila=9,
        codigo="P-1",
        descripcion=None,
        unidad="M2",
        cantidad=None,
        precio_unitario=None,
        importe=None,
        ruta=ruta,
    )
    cargo = CargoLeido(
        fila=14,
        rotulo="X",
        tipo=None,
        porcentaje=None,
        base=None,
        importe=None,
    )
    analisis = AnalisisLeido(
        hoja="APU P-1",
        cabecera=CabeceraLeida(
            fila_codigo=2,
            codigo="P-1",
            unidad="M2",
            fecha=None,
            analista=None,
            precio_unitario=None,
        ),
        insumos=(),
        cargos=(cargo,),
        fila_precio_unitario=21,
        precio_unitario=None,
        totales=TotalesAnalisis(None, None, None, None, None),
        hallazgos=(),
    )
    prep = Preparacion(
        hoja_catalogo="CATALOGO",
        nodos=(nodo,),
        conceptos=(concepto,),
        analisis=(analisis,),
        asociaciones=(),
        insumos_por_crear=(),
        filas_leidas=1,
        filas_validas=1,
        filas_rechazadas=0,
    )
    documento = preparacion_a_json(prep)
    conceptos_doc = cast(list[dict[str, Any]], documento["conceptos"])
    nodos_doc = cast(list[dict[str, Any]], documento["nodos"])
    analisis_doc = cast(list[dict[str, Any]], documento["analisis"])
    assert conceptos_doc[0]["descripcion"] is None
    assert conceptos_doc[0]["importe"] is None
    assert nodos_doc[0]["nombre"] is None
    assert cast(list[dict[str, Any]], analisis_doc[0]["cargos"])[0]["tipo"] is None
    assert cast(dict[str, Any], conceptos_doc[0]["ruta"])["area"] is None


def test_tkt015_resultado_sobrevive_a_pickle(libro_catalogo: LibroCatalogo) -> None:
    """TC-23 · CA-12 — ResultadoAnalisis sobrevive a pickle (mismo escenario que TC-20)."""
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    _campos_rotos: tuple[CampoConcepto, ...] = ("precio_unitario", "importe")
    rotos: dict[tuple[int, CampoConcepto], str] = {
        (fila, campo): "#REF!" for fila in (20, 30, 40) for campo in _campos_rotos
    }
    contenido = libro_sintetico(libro_catalogo, rotos=rotos)
    original = analizar_contenido(contenido, {})
    recuperado = pickle.loads(pickle.dumps(original))
    assert recuperado == original
