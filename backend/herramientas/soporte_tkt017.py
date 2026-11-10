"""Ayudantes de prueba para TKT-017 (materialización y línea base)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql

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
from cimenta.presupuesto.dominio.materializacion import InsumoRegistrado, PlanMaterializacion
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from tipos_base import Cantidad, Dinero, Rendimiento

_HOJA_APU = "40-A"

UUID_MUROS = UUID("11111111-1111-1111-1111-111111111101")
UUID_PLAFON = UUID("11111111-1111-1111-1111-111111111102")
UUID_TBR = UUID("22222222-2222-2222-2222-222222222201")
UUID_MO = UUID("22222222-2222-2222-2222-222222222202")
UUID_OTRO = UUID("33333333-3333-3333-3333-333333333399")


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
        clave="PANEL YESO 1/2",
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


def _reemplazar_en_tuple[T](tupla: tuple[T, ...], indice: int, valor: T) -> tuple[T, ...]:
    lst = list(tupla)
    lst[indice] = valor
    return tuple(lst)


def preparacion_sintetica_cantidad_plafon(cantidad: str) -> Preparacion:
    """Variante de `preparacion_sintetica` con otra cantidad en la fila del plafón (TC-A04)."""
    base = preparacion_sintetica()
    c1 = base.conceptos[1]
    assert c1.fila == 12
    nuevo = ConceptoLeido(
        fila=c1.fila,
        codigo=c1.codigo,
        descripcion=c1.descripcion,
        unidad=c1.unidad,
        cantidad=Cantidad(cantidad),
        precio_unitario=c1.precio_unitario,
        importe=c1.importe,
        ruta=c1.ruta,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=(base.conceptos[0], nuevo),
        analisis=base.analisis,
        asociaciones=base.asociaciones,
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_sintetica_cargos_utilidad_indirectos_altos() -> Preparacion:
    """Cargos de utilidad e indirectos que hacen negativo el importe sugerido (TC-A07)."""
    base = preparacion_sintetica()
    a0 = base.analisis[0]
    cargos = (
        CargoLeido(
            fila=20,
            rotulo=TipoCargo.UTILIDAD.value,
            tipo=TipoCargo.UTILIDAD,
            porcentaje=None,
            base=None,
            importe=Dinero("400.0000"),
        ),
        CargoLeido(
            fila=21,
            rotulo=TipoCargo.INDIRECTOS.value,
            tipo=TipoCargo.INDIRECTOS,
            porcentaje=None,
            base=None,
            importe=Dinero("50.0000"),
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
    nuevo_analisis = AnalisisLeido(
        hoja=a0.hoja,
        cabecera=a0.cabecera,
        insumos=a0.insumos,
        cargos=cargos,
        fila_precio_unitario=a0.fila_precio_unitario,
        precio_unitario=a0.precio_unitario,
        totales=a0.totales,
        hallazgos=a0.hallazgos,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=base.conceptos,
        analisis=(nuevo_analisis,),
        asociaciones=base.asociaciones,
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_sintetica_sin_cargo_utilidad() -> Preparacion:
    """Solo indirectos e IVA: falta UTILIDAD en el análisis (TC-A07)."""
    base = preparacion_sintetica()
    a0 = base.analisis[0]
    cargos = (
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
    nuevo_analisis = AnalisisLeido(
        hoja=a0.hoja,
        cabecera=a0.cabecera,
        insumos=a0.insumos,
        cargos=cargos,
        fila_precio_unitario=a0.fila_precio_unitario,
        precio_unitario=a0.precio_unitario,
        totales=a0.totales,
        hallazgos=a0.hallazgos,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=base.conceptos,
        analisis=(nuevo_analisis,),
        asociaciones=base.asociaciones,
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_codigo_duplicado_en_misma_partida() -> Preparacion:
    """Dos filas de catálogo con el mismo código en la misma partida (TC-A08)."""
    base = preparacion_sintetica()
    muro1 = base.conceptos[0]
    dup = ConceptoLeido(
        fila=99,
        codigo=muro1.codigo,
        descripcion="Copia",
        unidad=muro1.unidad,
        cantidad=Cantidad("1.0000"),
        precio_unitario=muro1.precio_unitario,
        importe=muro1.importe,
        ruta=muro1.ruta,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=(muro1, dup),
        analisis=base.analisis,
        asociaciones=base.asociaciones
        + (AsociacionLeida(hoja=_HOJA_APU, codigo=muro1.codigo, filas_catalogo=(99,)),),
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_insumo_sin_registro_ni_alta() -> Preparacion:
    """Insumo material cuya clave no está en altas ni en el mapa de registrados (TC-A08)."""
    base = preparacion_sintetica()
    a0 = base.analisis[0]
    insumos = _reemplazar_en_tuple(
        a0.insumos,
        0,
        InsumoLeido(
            fila=8,
            tipo=TipoInsumo.MATERIAL,
            descripcion="DESCONOCIDO",
            clave="XYZ-999",
            unidad="PZA",
            costo_unitario=Dinero("85.5000"),
            rendimiento=Rendimiento("0.673400"),
            cargo=Dinero("57.5622"),
        ),
    )
    nuevo = AnalisisLeido(
        hoja=a0.hoja,
        cabecera=a0.cabecera,
        insumos=insumos,
        cargos=a0.cargos,
        fila_precio_unitario=a0.fila_precio_unitario,
        precio_unitario=a0.precio_unitario,
        totales=a0.totales,
        hallazgos=a0.hallazgos,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=base.conceptos,
        analisis=(nuevo,),
        asociaciones=base.asociaciones,
        insumos_por_crear=(),  # sin alta para XYZ-999
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_totales_material_nulo() -> Preparacion:
    base = preparacion_sintetica()
    a0 = base.analisis[0]
    totales = TotalesAnalisis(
        material=None,
        mano_obra=a0.totales.mano_obra,
        costo_directo=a0.totales.costo_directo,
        cargos=a0.totales.cargos,
        precio_unitario=a0.totales.precio_unitario,
    )
    nuevo = AnalisisLeido(
        hoja=a0.hoja,
        cabecera=a0.cabecera,
        insumos=a0.insumos,
        cargos=a0.cargos,
        fila_precio_unitario=a0.fila_precio_unitario,
        precio_unitario=a0.precio_unitario,
        totales=totales,
        hallazgos=a0.hallazgos,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=base.conceptos,
        analisis=(nuevo,),
        asociaciones=base.asociaciones,
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def preparacion_mano_obra_sin_costo() -> Preparacion:
    base = preparacion_sintetica()
    a0 = base.analisis[0]
    insumo_mo = InsumoLeido(
        fila=11,
        tipo=TipoInsumo.MANO_OBRA,
        descripcion="OFICIAL TABLAROQUERO",
        clave="MO-001",
        unidad="JORNAL",
        costo_unitario=None,
        rendimiento=Rendimiento("0.080000"),
        cargo=Dinero("36.0000"),
    )
    insumos = (a0.insumos[0], insumo_mo)
    nuevo = AnalisisLeido(
        hoja=a0.hoja,
        cabecera=a0.cabecera,
        insumos=insumos,
        cargos=a0.cargos,
        fila_precio_unitario=a0.fila_precio_unitario,
        precio_unitario=a0.precio_unitario,
        totales=a0.totales,
        hallazgos=a0.hallazgos,
    )
    return Preparacion(
        hoja_catalogo=base.hoja_catalogo,
        nodos=base.nodos,
        conceptos=base.conceptos,
        analisis=(nuevo,),
        asociaciones=base.asociaciones,
        insumos_por_crear=base.insumos_por_crear,
        filas_leidas=base.filas_leidas,
        filas_validas=base.filas_validas,
        filas_rechazadas=base.filas_rechazadas,
    )


def insumos_registrados_sinteticos() -> tuple[InsumoRegistrado, ...]:
    """Mano de obra ya registrada; el panel nuevo sale de `insumos_por_crear` (CA-A1)."""
    return (
        InsumoRegistrado(
            id=UUID_MO,
            codigo="MO-001",
            descripcion="OFICIAL TABLAROQUERO",
            unidad="JORNAL",
            tipo=TipoInsumo.MANO_OBRA,
        ),
    )


def asignacion_tipos_hdu001_esc11() -> dict[str, UUID]:
    return {"MUROS EXTERIORES": UUID_MUROS, "PLAFON": UUID_PLAFON}


def tipos_partida_hdu001_esc11() -> frozenset[UUID]:
    return frozenset({UUID_MUROS, UUID_PLAFON})


def contar_filas_de_obra(plan: PlanMaterializacion) -> dict[str, int]:
    """Recuento de filas a insertar por tabla (TC-A04, verificación auxiliar)."""
    n_apu_ins = sum(len(a.insumos) for a in plan.apus)
    n_apu_cargos = sum(len(a.cargos) for a in plan.apus)
    return {
        "nivel": len(plan.niveles),
        "area": len(plan.areas),
        "partida": len(plan.partidas),
        "concepto_catalogo": len(plan.conceptos),
        "partida_concepto": len(plan.partidas_concepto),
        "apu": len(plan.apus),
        "apu_insumo": n_apu_ins,
        "apu_cargo": n_apu_cargos,
        "insumo_insertar": len(plan.insumos_insertar),
    }


# Any: se reenvía tal cual a dataclasses.replace(**cambios), que también es Any
def preparacion_con_concepto(indice: int, **cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros valores en el concepto `indice` (TC-A08)."""
    base = preparacion_sintetica()
    conceptos = _reemplazar_en_tuple(
        base.conceptos, indice, replace(base.conceptos[indice], **cambios)
    )
    return replace(base, conceptos=conceptos)


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_ruta(**cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otra ruta en el primer concepto (TC-A08)."""
    base = preparacion_sintetica()
    primero = base.conceptos[0]
    return preparacion_con_concepto(0, ruta=replace(primero.ruta, **cambios))


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_analisis(**cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros valores en el único análisis (TC-A08)."""
    base = preparacion_sintetica()
    return replace(base, analisis=(replace(base.analisis[0], **cambios),))


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_totales(**cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros totales en el análisis (TC-A08)."""
    totales = replace(preparacion_sintetica().analisis[0].totales, **cambios)
    return preparacion_con_analisis(totales=totales)


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_insumo(indice: int, **cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros valores en el insumo `indice` del análisis (TC-A08)."""
    insumos = preparacion_sintetica().analisis[0].insumos
    return preparacion_con_analisis(
        insumos=_reemplazar_en_tuple(insumos, indice, replace(insumos[indice], **cambios))
    )


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_cargo(indice: int, **cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros valores en el cargo `indice` del análisis (TC-A08)."""
    cargos = preparacion_sintetica().analisis[0].cargos
    return preparacion_con_analisis(
        cargos=_reemplazar_en_tuple(cargos, indice, replace(cargos[indice], **cambios))
    )


def preparacion_dos_niveles() -> Preparacion:
    """Dos niveles de tres áreas con dos partidas cada una, fuera de orden alfabético (CA-A1).

    Todas las partidas llevan el mismo código `620040-A`. Las filas del catálogo van de la 100 a la
    111 y la tupla de conceptos viene invertida: el orden del plan sale de las filas, no de la tupla.
    """
    raiz = NodoLeido(fila=5, profundidad=Profundidad.RAIZ, nombre="RAIZ")
    niveles = ((6, "SOTANO"), (20, "AZOTEA"))
    nodos: list[NodoLeido] = [raiz]
    conceptos: list[ConceptoLeido] = []
    for fila_nivel, nombre_nivel in niveles:
        nivel = NodoLeido(fila=fila_nivel, profundidad=Profundidad.NIVEL, nombre=nombre_nivel)
        nodos.append(nivel)
        for desplazamiento, nombre_area in ((1, "ZONA Z"), (4, "ZONA M"), (7, "ZONA A")):
            area = NodoLeido(
                fila=fila_nivel + desplazamiento, profundidad=Profundidad.AREA, nombre=nombre_area
            )
            nodos.append(area)
            for paso, nombre_partida in ((1, "PLAFON"), (2, "MUROS EXTERIORES")):
                partida = NodoLeido(
                    fila=area.fila + paso, profundidad=Profundidad.PARTIDA, nombre=nombre_partida
                )
                nodos.append(partida)
                conceptos.append(
                    ConceptoLeido(
                        fila=100 + len(conceptos),
                        codigo="620040-A",
                        descripcion="Tablaroca",
                        unidad="M2",
                        cantidad=Cantidad("12.5000"),
                        precio_unitario=Dinero("420.0000"),
                        importe=None,
                        ruta=Ruta(raiz=raiz, nivel=nivel, area=area, partida=partida),
                    )
                )
    base = preparacion_sintetica()
    return replace(
        base,
        nodos=tuple(nodos),
        conceptos=tuple(reversed(conceptos)),
        asociaciones=(
            AsociacionLeida(
                hoja=_HOJA_APU,
                codigo="620040-A",
                filas_catalogo=tuple(c.fila for c in conceptos),
            ),
        ),
        filas_leidas=len(conceptos),
        filas_validas=len(conceptos),
    )


def preparacion_dos_conceptos_con_alta_compartida() -> Preparacion:
    """Dos códigos de concepto, cada uno con su hoja, que comparten el alta `PANEL YESO 1/2` (CA-A1)."""
    base = preparacion_sintetica()
    analisis_base = base.analisis[0]
    analisis_segundo = replace(
        analisis_base,
        hoja="41-A",
        cabecera=replace(analisis_base.cabecera, codigo="620041-A"),
    )
    return replace(
        base,
        conceptos=(base.conceptos[0], replace(base.conceptos[1], codigo="620041-A")),
        analisis=(analisis_base, analisis_segundo),
        asociaciones=(
            AsociacionLeida(hoja=_HOJA_APU, codigo="620040-A", filas_catalogo=(11,)),
            AsociacionLeida(hoja="41-A", codigo="620041-A", filas_catalogo=(12,)),
        ),
    )


def preparacion_con_partidas(nombres: tuple[str, ...]) -> Preparacion:
    """Un nivel y un área con una partida por nombre, en el orden dado y un concepto en cada una."""
    raiz = NodoLeido(fila=5, profundidad=Profundidad.RAIZ, nombre="RAIZ")
    nivel = NodoLeido(fila=6, profundidad=Profundidad.NIVEL, nombre="NIVEL 1")
    area = NodoLeido(fila=7, profundidad=Profundidad.AREA, nombre="ZONA")
    partidas = [
        NodoLeido(fila=8 + i, profundidad=Profundidad.PARTIDA, nombre=nombre)
        for i, nombre in enumerate(nombres)
    ]
    conceptos = tuple(
        ConceptoLeido(
            fila=100 + i,
            codigo="620040-A",
            descripcion="Tablaroca",
            unidad="M2",
            cantidad=Cantidad("1.0000"),
            precio_unitario=Dinero("420.0000"),
            importe=None,
            ruta=Ruta(raiz=raiz, nivel=nivel, area=area, partida=partida),
        )
        for i, partida in enumerate(partidas)
    )
    return replace(
        preparacion_sintetica(),
        nodos=(raiz, nivel, area, *partidas),
        conceptos=conceptos,
        asociaciones=(
            AsociacionLeida(
                hoja=_HOJA_APU, codigo="620040-A", filas_catalogo=tuple(c.fila for c in conceptos)
            ),
        ),
    )


# Any: ver el comentario de preparacion_con_concepto
def preparacion_con_alta(**cambios: Any) -> Preparacion:
    """`preparacion_sintetica` con otros valores en el alta del insumo `PANEL YESO 1/2` (CA-A6)."""
    base = preparacion_sintetica()
    return replace(base, insumos_por_crear=(replace(base.insumos_por_crear[0], **cambios),))


# Any: ver el comentario de preparacion_con_concepto
def preparacion_alta_compartida_con_segundo_insumo(**cambios: Any) -> Preparacion:
    """Alta compartida por dos hojas; el panel de la segunda lleva otros valores (CA-A6)."""
    base = preparacion_dos_conceptos_con_alta_compartida()
    segundo = base.analisis[1]
    insumos = _reemplazar_en_tuple(segundo.insumos, 0, replace(segundo.insumos[0], **cambios))
    return replace(base, analisis=(base.analisis[0], replace(segundo, insumos=insumos)))


def preparacion_solo_muros(preparacion: Preparacion | None = None) -> Preparacion:
    """Solo la primera aparición de `620040-A` (`MUROS EXTERIORES`), sin los nodos del plafón (TC-A16).

    Con dos apariciones, cada causa de la explosión sale repetida (una por fila) y `causas` no es una
    lista de un elemento. `preparacion` es la variante del libro que se quiere reducir; por omisión,
    `preparacion_sintetica()`.
    """
    base = preparacion if preparacion is not None else preparacion_sintetica()
    muros = base.conceptos[0]
    ruta = muros.ruta
    filas_de_muros = {
        nodo.fila for nodo in (ruta.raiz, ruta.nivel, ruta.area, ruta.partida) if nodo
    }
    return replace(
        base,
        nodos=tuple(nodo for nodo in base.nodos if nodo.fila in filas_de_muros),
        conceptos=(muros,),
        asociaciones=(
            AsociacionLeida(hoja=_HOJA_APU, codigo=muros.codigo, filas_catalogo=(muros.fila,)),
        ),
        filas_leidas=1,
        filas_validas=1,
    )


# Tablas que una materialización o un congelado escriben o podrían escribir por error (TC-A10 a TC-A20).
TABLAS_DE_LA_JERARQUIA: tuple[str, ...] = (
    "nivel",
    "area",
    "partida",
    "concepto",
    "partida_concepto",
    "apu",
    "apu_insumo",
    "apu_cargo",
    "insumo",
    "precio_insumo",
    "linea_base",
    "linea_base_concepto",
    "explosion_presupuesto",
    "presupuesto_control",
    "bitacora",
)


def contar_filas_en_base(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, int]:
    """Filas de cada tabla de `TABLAS_DE_LA_JERARQUIA`, de toda la base de la prueba.

    No confundir con `contar_filas_de_obra`, que cuenta lo que un `PlanMaterializacion` insertaría
    (a2, `TC-A04`): esta lee lo que la base tiene de verdad.
    """
    cuentas: dict[str, int] = {}
    for tabla in TABLAS_DE_LA_JERARQUIA:
        fila = conexion.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
        ).fetchone()
        assert fila is not None
        cuentas[tabla] = int(fila[0])
    return cuentas


def foto_de_base(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: los recuentos, el estado de importaciones y obras, las
    líneas base completas y los insumos completos (incluida su marca `creado_en_importacion`)."""
    return {
        "filas": contar_filas_en_base(conexion),
        "importaciones": conexion.execute(
            "SELECT id, estado FROM importacion ORDER BY id"
        ).fetchall(),
        "obras": conexion.execute("SELECT id, estado FROM obra ORDER BY id").fetchall(),
        "lineas_base": conexion.execute(
            "SELECT id, obra_id, version, estado, importe_venta, congelada_en, motivo "
            "FROM linea_base ORDER BY id"
        ).fetchall(),
        "insumos": conexion.execute(
            "SELECT id, codigo, descripcion, unidad, tipo, activo, creado_en_importacion "
            "FROM insumo ORDER BY id"
        ).fetchall(),
    }
