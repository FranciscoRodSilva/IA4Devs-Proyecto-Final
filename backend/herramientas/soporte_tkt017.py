"""Ayudantes de prueba para TKT-017 (materialización y línea base)."""

from __future__ import annotations

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    AsociacionLeida,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    InsumoPorCrear,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, NodoLeido, Profundidad, Ruta
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from tipos_base import Cantidad, Dinero, Rendimiento

_HOJA_APU = "40-A"


def preparacion_sintetica() -> Preparacion:
    """Libro de `CA-A1` · HDU-001 esc. 11 — dos apariciones de `620040-A`, pie 420 y un insumo por crear."""
    raiz = NodoLeido(fila=5, profundidad=Profundidad.RAIZ, nombre="RAIZ")
    nivel = NodoLeido(fila=6, profundidad=Profundidad.NIVEL, nombre="NIVEL 3")
    area_muros = NodoLeido(fila=7, profundidad=Profundidad.AREA, nombre="ZONA MUROS")
    partida_muros = NodoLeido(fila=8, profundidad=Profundidad.PARTIDA, nombre="MUROS EXTERIORES")
    area_plafon = NodoLeido(fila=9, profundidad=Profundidad.AREA, nombre="ZONA PLAFÓN")
    partida_plafon = NodoLeido(fila=10, profundidad=Profundidad.PARTIDA, nombre="PLAFON")

    ruta_muros = Ruta(raiz=raiz, nivel=nivel, area=area_muros, partida=partida_muros)
    ruta_plafon = Ruta(raiz=raiz, nivel=nivel, area=area_plafon, partida=partida_plafon)

    conceptos = (
        ConceptoLeido(
            fila=11,
            codigo="620040-A",
            descripcion="Tablaroca en muros",
            unidad="M2",
            cantidad=Cantidad("12.5000"),
            precio_unitario=Dinero("414.9300"),
            importe=None,
            ruta=ruta_muros,
        ),
        ConceptoLeido(
            fila=12,
            codigo="620040-A",
            descripcion="Tablaroca en plafón",
            unidad="M2",
            cantidad=Cantidad("7.3333"),
            precio_unitario=Dinero("428.1900"),
            importe=None,
            ruta=ruta_plafon,
        ),
    )

    insumo_panel = InsumoLeido(
        fila=8,
        tipo=TipoInsumo.MATERIAL,
        descripcion="PANEL YESO 1/2",
        clave="TBR-015",
        unidad="PZA",
        costo_unitario=Dinero("85.5000"),
        rendimiento=Rendimiento("0.673400"),
        cargo=Dinero("57.5622"),
    )
    insumo_mo = InsumoLeido(
        fila=11,
        tipo=TipoInsumo.MANO_OBRA,
        descripcion="OFICIAL TABLAROQUERO",
        clave="MO-001",
        unidad="JORNAL",
        costo_unitario=Dinero("450.0000"),
        rendimiento=Rendimiento("0.080000"),
        cargo=Dinero("36.0000"),
    )

    cargos = (
        CargoLeido(
            fila=20,
            rotulo=TipoCargo.UTILIDAD.value,
            tipo=TipoCargo.UTILIDAD,
            porcentaje=None,
            base=None,
            importe=Dinero("50.0000"),
        ),
        CargoLeido(
            fila=21,
            rotulo=TipoCargo.INDIRECTOS.value,
            tipo=TipoCargo.INDIRECTOS,
            porcentaje=None,
            base=None,
            importe=Dinero("60.0000"),
        ),
        CargoLeido(
            fila=22,
            rotulo=TipoCargo.IVA.value,
            tipo=TipoCargo.IVA,
            porcentaje=None,
            base=None,
            importe=Dinero("40.0000"),
        ),
    )

    totales = TotalesAnalisis(
        material=Dinero("200.0000"),
        mano_obra=Dinero("100.0000"),
        costo_directo=Dinero("300.0000"),
        cargos=Dinero("50.0000"),
        precio_unitario=Dinero("420.0000"),
    )

    analisis = (
        AnalisisLeido(
            hoja=_HOJA_APU,
            cabecera=CabeceraLeida(
                fila_codigo=2,
                codigo="620040-A",
                unidad="M2",
                fecha="2026-01-15",
                analista="Analista ENITI",
                precio_unitario=Dinero("420.0000"),
            ),
            insumos=(insumo_panel, insumo_mo),
            cargos=cargos,
            fila_precio_unitario=25,
            precio_unitario=Dinero("420.0000"),
            totales=totales,
            hallazgos=(),
        ),
    )

    asociaciones = (AsociacionLeida(hoja=_HOJA_APU, codigo="620040-A", filas_catalogo=(11, 12)),)

    insumos_por_crear = (
        InsumoPorCrear(
            clave="PANEL YESO 1/2",
            descripcion="Panel de yeso 1/2",
            unidad="PZA",
            tipo=TipoInsumo.MATERIAL,
            creado_en_importacion=True,
        ),
    )

    return Preparacion(
        hoja_catalogo="CATALOGO",
        nodos=(raiz, nivel, area_muros, partida_muros, area_plafon, partida_plafon),
        conceptos=conceptos,
        analisis=analisis,
        asociaciones=asociaciones,
        insumos_por_crear=insumos_por_crear,
        filas_leidas=12,
        filas_validas=2,
        filas_rechazadas=0,
    )
