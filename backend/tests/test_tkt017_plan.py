"""TKT-017a2 fila A4 · planificar_materializacion (TC-A04 a TC-A08)."""

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from cimenta.presupuesto.dominio.analisis import (
    AsociacionLeida,
    TipoCargo,
    TipoInsumo,
)
from cimenta.presupuesto.dominio.catalogo import NodoLeido, Profundidad
from cimenta.presupuesto.dominio.explosion import MotivoRechazoExplosion
from cimenta.presupuesto.dominio.materializacion import (
    ApuCargoNuevo,
    ApuInsumoNuevo,
    AsignacionInvalida,
    ConceptoNuevo,
    ExplosionRechazada,
    InsumoEnConflicto,
    InsumoNuevo,
    InsumoRegistrado,
    PlanMaterializacion,
    PreparacionInconsistente,
    ResultadoMaterializacion,
    planificar_materializacion,
)
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from herramientas.soporte_tkt017 import (
    UUID_MO,
    UUID_MUROS,
    UUID_OTRO,
    UUID_PLAFON,
    UUID_TBR,
    asignacion_tipos_hdu001_esc11,
    insumos_registrados_sinteticos,
    preparacion_alta_compartida_con_segundo_insumo,
    preparacion_codigo_duplicado_en_misma_partida,
    preparacion_con_alta,
    preparacion_con_analisis,
    preparacion_con_cargo,
    preparacion_con_concepto,
    preparacion_con_insumo,
    preparacion_con_partidas,
    preparacion_con_ruta,
    preparacion_con_totales,
    preparacion_dos_conceptos_con_alta_compartida,
    preparacion_dos_niveles,
    preparacion_insumo_sin_registro_ni_alta,
    preparacion_mano_obra_sin_costo,
    preparacion_sintetica,
    preparacion_sintetica_cantidad_plafon,
    preparacion_sintetica_cargos_utilidad_indirectos_altos,
    preparacion_sintetica_sin_cargo_utilidad,
    preparacion_totales_material_nulo,
    tipos_partida_hdu001_esc11,
)
from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

_MSJ_PREPARACION = "la importación debe analizarse de nuevo"
_CODIGO = "620040-A"


def _planificar(
    preparacion: Preparacion,
    *,
    asignacion: dict[str, UUID] | None = None,
    tipos_partida: frozenset[UUID] | None = None,
    insumos_registrados: tuple[InsumoRegistrado, ...] | None = None,
) -> ResultadoMaterializacion:
    return planificar_materializacion(
        preparacion,
        asignacion=asignacion_tipos_hdu001_esc11() if asignacion is None else asignacion,
        tipos_partida=tipos_partida_hdu001_esc11() if tipos_partida is None else tipos_partida,
        insumos_registrados=(
            insumos_registrados_sinteticos() if insumos_registrados is None else insumos_registrados
        ),
        nuevo_id=uuid4,
    )


def _plan(resultado: ResultadoMaterializacion) -> PlanMaterializacion:
    assert isinstance(resultado, PlanMaterializacion)
    return resultado


def _todos_los_ids(plan: PlanMaterializacion) -> list[UUID]:
    return [
        *(n.id for n in plan.niveles),
        *(a.id for a in plan.areas),
        *(p.id for p in plan.partidas),
        *(c.id for c in plan.conceptos),
        *(pc.id for pc in plan.partidas_concepto),
        *(i.id for i in plan.insumos_insertar),
        *(a.id for a in plan.apus),
    ]


def test_hdu001_esc11_el_plan_crea_un_concepto_con_dos_apariciones() -> None:
    """TC-A04 · CA-A1 · HDU-001 esc. 11."""
    plan = _plan(_planificar(preparacion_sintetica()))

    assert [(n.nombre, n.orden) for n in plan.niveles] == [("NIVEL 3", 1)]
    assert [a.nombre for a in plan.areas] == ["ZONA MUROS", "ZONA PLAFÓN"]
    assert {a.nivel_id for a in plan.areas} == {plan.niveles[0].id}
    assert [(p.tipo_partida_id, p.orden) for p in plan.partidas] == [
        (UUID_MUROS, 1),
        (UUID_PLAFON, 1),
    ]
    assert [p.area_id for p in plan.partidas] == [a.id for a in plan.areas]

    assert len(plan.conceptos) == 1
    concepto = plan.conceptos[0]
    assert (concepto.codigo, concepto.descripcion, concepto.unidad) == (
        _CODIGO,
        "Tablaroca en muros",
        "M2",
    )

    assert len(plan.partidas_concepto) == 2
    muros, plafon = plan.partidas_concepto
    assert muros.concepto_id == plafon.concepto_id == concepto.id
    assert [muros.partida_id, plafon.partida_id] == [p.id for p in plan.partidas]
    assert (muros.cantidad, muros.precio_unitario, muros.importe) == (
        Cantidad("12.5000"),
        Dinero("420.0000"),
        Dinero("5250.0000"),
    )
    assert (plafon.cantidad, plafon.precio_unitario, plafon.importe) == (
        Cantidad("7.3333"),
        Dinero("420.0000"),
        Dinero("3079.9860"),
    )
    assert plan.importe_venta == Dinero("8329.9860")

    assert len(plan.insumos_insertar) == 1
    panel = plan.insumos_insertar[0]
    assert panel == InsumoNuevo(
        id=panel.id,
        codigo="PANEL YESO 1/2",
        descripcion="Panel de yeso 1/2",
        unidad="PZA",
        tipo=TipoInsumo.MATERIAL,
        creado_en_importacion=True,
    )

    assert len(plan.apus) == 1
    apu = plan.apus[0]
    assert apu.concepto_id == concepto.id
    assert (apu.hoja, apu.fecha_analisis, apu.analista) == ("40-A", "2026-01-15", "Analista ENITI")
    assert (
        apu.costo_material,
        apu.costo_mano_obra,
        apu.costo_directo,
        apu.total_cargos,
        apu.total_indirectos,
        apu.precio_unitario,
    ) == (
        Dinero("200.0000"),
        Dinero("100.0000"),
        Dinero("300.0000"),
        Dinero("50.0000"),
        Dinero("60.0000"),
        Dinero("420.0000"),
    )
    assert apu.insumos == (
        ApuInsumoNuevo(
            insumo_id=panel.id,
            costo_unitario=Dinero("85.5000"),
            rendimiento=Rendimiento("0.673400"),
            cargo=Dinero("57.5622"),
        ),
        ApuInsumoNuevo(
            insumo_id=UUID_MO,
            costo_unitario=Dinero("450.0000"),
            rendimiento=Rendimiento("0.080000"),
            cargo=Dinero("36.0000"),
        ),
    )
    assert apu.cargos == (
        ApuCargoNuevo(TipoCargo.UTILIDAD, None, None, Dinero("50.0000")),
        ApuCargoNuevo(TipoCargo.INDIRECTOS, None, None, Dinero("60.0000")),
        ApuCargoNuevo(TipoCargo.IVA, None, None, Dinero("40.0000")),
    )


def test_hdu001_esc11_variante_733335() -> None:
    """TC-A04 · variante cantidad 7.33335 → 7.3334 y importe 3080.0280."""
    plan = _plan(_planificar(preparacion_sintetica_cantidad_plafon("7.33335")))
    plafon = plan.partidas_concepto[1]
    assert plafon.cantidad == Cantidad("7.3334")
    assert plafon.importe == Dinero("3080.0280")
    assert plan.importe_venta == Dinero("8330.0280")


def test_hdu001_esc11_los_identificadores_del_plan_no_se_repiten() -> None:
    """TC-A04 · CA-A1 — cada fila del plan lleva un identificador propio."""
    ids = _todos_los_ids(_plan(_planificar(preparacion_sintetica())))
    assert len(ids) == 1 + 2 + 2 + 1 + 2 + 1 + 1
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("repeticion", range(10))
def test_hdu001_esc11_niveles_areas_y_partidas_siguen_el_orden_del_catalogo(
    repeticion: int,
) -> None:
    """TC-A04 · CA-A1 — el orden sale de las filas del catálogo y no de identificadores aleatorios."""
    plan = _plan(_planificar(preparacion_dos_niveles()))

    assert [(n.nombre, n.orden) for n in plan.niveles] == [("SOTANO", 1), ("AZOTEA", 2)]
    nombre_nivel = {n.id: n.nombre for n in plan.niveles}
    assert [(nombre_nivel[a.nivel_id], a.nombre) for a in plan.areas] == [
        (nivel, area) for nivel in ("SOTANO", "AZOTEA") for area in ("ZONA Z", "ZONA M", "ZONA A")
    ]
    nombre_area = {a.id: a.nombre for a in plan.areas}
    indice_area = {a.id: i for i, a in enumerate(plan.areas)}
    assert [
        (indice_area[p.area_id], nombre_area[p.area_id], p.tipo_partida_id, p.orden)
        for p in plan.partidas
    ] == [
        (indice, area, tipo, orden)
        for indice, area in enumerate(["ZONA Z", "ZONA M", "ZONA A"] * 2)
        for orden, tipo in ((1, UUID_PLAFON), (2, UUID_MUROS))
    ]
    assert len(plan.conceptos) == 1
    assert len(plan.partidas_concepto) == 12
    assert [pc.partida_id for pc in plan.partidas_concepto] == [p.id for p in plan.partidas]


def test_hdu001_esc11_mismo_codigo_en_partidas_homonimas_de_areas_distintas_es_valido() -> None:
    """TC-A08 · CA-A1 — la unicidad del código es por nodo de partida, no por nombre."""
    resultado = _planificar(preparacion_dos_niveles())
    assert isinstance(resultado, PlanMaterializacion)


def test_tkt017_caa03_asignacion_incompleta_o_inexistente() -> None:
    """TC-A05 · CA-A3."""
    r1 = _planificar(preparacion_sintetica(), asignacion={"MUROS EXTERIORES": UUID_MUROS})
    assert isinstance(r1, AsignacionInvalida)
    assert r1.faltantes == ("PLAFON",)
    assert r1.inexistentes == ()

    r2 = _planificar(
        preparacion_sintetica(),
        asignacion={**asignacion_tipos_hdu001_esc11(), "PLAFON": UUID_OTRO},
    )
    assert isinstance(r2, AsignacionInvalida)
    assert r2.faltantes == ()
    assert r2.inexistentes == ("PLAFON",)


def test_tkt017_caa03_faltantes_e_inexistentes_van_ordenados_y_sin_repetir() -> None:
    """TC-A05 · CA-A3 — dos partidas homónimas aparecen una sola vez."""
    r1 = _planificar(preparacion_dos_niveles(), asignacion={})
    assert isinstance(r1, AsignacionInvalida)
    assert r1.faltantes == ("MUROS EXTERIORES", "PLAFON")

    r2 = _planificar(preparacion_dos_niveles(), tipos_partida=frozenset())
    assert isinstance(r2, AsignacionInvalida)
    assert r2.faltantes == ()
    assert r2.inexistentes == ("MUROS EXTERIORES", "PLAFON")


_NOMBRES_EN_ORDEN_INVERSO = ("PLAFON", "MUROS", "DUCTOS", "CIELO", "BARDA", "ACABADO")


def test_tkt017_caa03_faltantes_e_inexistentes_salen_ordenados_si_el_catalogo_no_lo_esta() -> None:
    """TC-A05 · CA-A3 — seis partidas leídas de mayor a menor nombre salen de menor a mayor."""
    preparacion = preparacion_con_partidas(_NOMBRES_EN_ORDEN_INVERSO)
    ordenados = tuple(sorted(_NOMBRES_EN_ORDEN_INVERSO))

    r1 = _planificar(preparacion, asignacion={})
    assert isinstance(r1, AsignacionInvalida)
    assert r1.faltantes == ordenados

    r2 = _planificar(
        preparacion,
        asignacion=dict.fromkeys(_NOMBRES_EN_ORDEN_INVERSO, UUID_OTRO),
        tipos_partida=frozenset(),
    )
    assert isinstance(r2, AsignacionInvalida)
    assert r2.inexistentes == ordenados


def test_tkt017_caa03_el_nombre_de_la_partida_del_catalogo_tambien_se_normaliza() -> None:
    """TC-A05 · CA-A3 — espacios y minúsculas del catálogo no impiden hallar su tipo."""
    partida = NodoLeido(fila=8, profundidad=Profundidad.PARTIDA, nombre="  muros exteriores ")
    plan = _plan(_planificar(preparacion_con_ruta(partida=partida)))
    assert UUID_MUROS in {p.tipo_partida_id for p in plan.partidas}


def test_tkt017_caa03_una_clave_sobrante_de_la_asignacion_se_ignora() -> None:
    """TC-A05 · CA-A3 · P-12 — una clave sin partida no rechaza ni entra al plan."""
    plan = _plan(
        _planificar(
            preparacion_sintetica(),
            asignacion={**asignacion_tipos_hdu001_esc11(), "OTRA": UUID_OTRO},
        )
    )
    assert {p.tipo_partida_id for p in plan.partidas} == {UUID_MUROS, UUID_PLAFON}
    assert all(r.tipo_partida_id != UUID_OTRO for r in plan.explosion.renglones)


def test_tkt017_caa03_la_asignacion_se_normaliza_igual_en_todo_el_plan() -> None:
    """TC-A05 · CA-A3 — dos claves que normalizan igual con distinto tipo son ambiguas."""
    r = _planificar(
        preparacion_sintetica(),
        asignacion={"MUROS EXTERIORES": UUID_MUROS, "plafon": UUID_OTRO, " PLAFON ": UUID_PLAFON},
        tipos_partida=frozenset({UUID_MUROS, UUID_PLAFON, UUID_OTRO}),
    )
    assert r == AsignacionInvalida(faltantes=(), inexistentes=(), ambiguas=("PLAFON",))


def test_tkt017_caa03_una_clave_sobrante_ambigua_se_ignora() -> None:
    """TC-A05 · CA-A3 · P-12 — la ambigüedad solo cuenta en las partidas que el catálogo alcanza."""
    plan = _plan(
        _planificar(
            preparacion_sintetica(),
            asignacion={**asignacion_tipos_hdu001_esc11(), "otra": UUID_OTRO, "OTRA": UUID_MUROS},
        )
    )
    assert {p.tipo_partida_id for p in plan.partidas} == {UUID_MUROS, UUID_PLAFON}


def test_tkt017_caa03_una_clave_ambigua_sobre_una_partida_requerida_se_rechaza() -> None:
    """TC-A05 · CA-A3 — la ambigua no se reporta además como inexistente."""
    r = _planificar(
        preparacion_sintetica(),
        asignacion={**asignacion_tipos_hdu001_esc11(), "plafon": UUID_OTRO},
        tipos_partida=frozenset({UUID_MUROS, UUID_OTRO}),
    )
    assert r == AsignacionInvalida(faltantes=(), inexistentes=(), ambiguas=("PLAFON",))


def test_tkt017_caa03_una_ambigua_con_tipos_invalidos_se_reporta_solo_como_ambigua() -> None:
    """TC-A05 · CA-A3 — una ambigua cuyos tipos no están en el catálogo no se reporta también como inexistente."""
    r = _planificar(
        preparacion_sintetica(),
        asignacion={"MUROS EXTERIORES": UUID_MUROS, "plafon": UUID_OTRO, "PLAFON": UUID_PLAFON},
        tipos_partida=frozenset({UUID_MUROS}),
    )
    assert r == AsignacionInvalida(faltantes=(), inexistentes=(), ambiguas=("PLAFON",))


def test_tkt017_caa03_claves_que_normalizan_igual_con_el_mismo_tipo_no_son_ambiguas() -> None:
    """TC-A05 · CA-A3 — la normalización por sí sola no rechaza."""
    plan = _plan(
        _planificar(
            preparacion_sintetica(),
            asignacion={
                "MUROS EXTERIORES": UUID_MUROS,
                "plafon": UUID_PLAFON,
                "PLAFON": UUID_PLAFON,
            },
        )
    )
    assert {p.tipo_partida_id for p in plan.partidas} == {UUID_MUROS, UUID_PLAFON}


def test_tkt017_caa03_las_ambiguas_van_ordenadas() -> None:
    """TC-A05 · CA-A3 — seis ambiguas salen ordenadas aunque el catálogo las lea de mayor a menor."""
    asignacion: dict[str, UUID] = {}
    for nombre in _NOMBRES_EN_ORDEN_INVERSO:
        asignacion[nombre] = UUID_MUROS
        asignacion[nombre.lower()] = UUID_OTRO
    r = _planificar(
        preparacion_con_partidas(_NOMBRES_EN_ORDEN_INVERSO),
        asignacion=asignacion,
        tipos_partida=frozenset({UUID_MUROS, UUID_OTRO}),
    )
    assert r == AsignacionInvalida(
        faltantes=(), inexistentes=(), ambiguas=tuple(sorted(_NOMBRES_EN_ORDEN_INVERSO))
    )


def test_tkt017_caa03_la_estructura_gana_a_la_asignacion() -> None:
    """TC-A05 · CA-A3 — con ambos defectos responde la preparación inconsistente (409)."""
    r = _planificar(preparacion_con_concepto(0, descripcion=None), asignacion={})
    assert r == PreparacionInconsistente(motivo=_MSJ_PREPARACION, codigo_concepto=_CODIGO)


def test_tkt017_caa06_insumo_existente_se_reutiliza() -> None:
    """TC-A06 · CA-A6 — el insumo registrado con mismo código, unidad y tipo conserva su id."""
    reg_panel = InsumoRegistrado(
        id=UUID_TBR,
        codigo="PANEL YESO 1/2",
        descripcion="PANEL YESO 1/2",
        unidad="PZA",
        tipo=TipoInsumo.MATERIAL,
    )
    plan = _plan(
        _planificar(
            preparacion_sintetica(),
            insumos_registrados=insumos_registrados_sinteticos() + (reg_panel,),
        )
    )
    assert plan.insumos_insertar == ()
    assert [i.insumo_id for i in plan.apus[0].insumos] == [UUID_TBR, UUID_MO]


def test_tkt017_caa06_insumo_registrado_por_descripcion_se_reutiliza() -> None:
    """TC-A06 · CA-A6 — sin alta, el insumo se localiza por su descripción normalizada."""
    registrado = InsumoRegistrado(
        id=UUID_TBR,
        codigo="PNL-01",
        descripcion="panel  yeso 1/2",
        unidad="PZA",
        tipo=TipoInsumo.MATERIAL,
    )
    plan = _plan(
        _planificar(
            replace(preparacion_sintetica(), insumos_por_crear=()),
            insumos_registrados=insumos_registrados_sinteticos() + (registrado,),
        )
    )
    assert plan.insumos_insertar == ()
    assert plan.apus[0].insumos[0].insumo_id == UUID_TBR


@pytest.mark.parametrize(
    ("unidad", "tipo"),
    [("KG", TipoInsumo.MATERIAL), ("PZA", TipoInsumo.MANO_OBRA)],
    ids=["otra_unidad", "otro_tipo"],
)
def test_tkt017_caa06_insumo_en_conflicto_por_alta(unidad: str, tipo: TipoInsumo) -> None:
    """TC-A06 · CA-A6 — mismo código con otra unidad o tipo se rechaza con los dos lados."""
    r = _planificar(
        preparacion_sintetica(),
        insumos_registrados=insumos_registrados_sinteticos()
        + (
            InsumoRegistrado(
                id=UUID_TBR,
                codigo="PANEL YESO 1/2",
                descripcion="PANEL YESO 1/2",
                unidad=unidad,
                tipo=tipo,
            ),
        ),
    )
    assert r == InsumoEnConflicto(
        codigo="PANEL YESO 1/2",
        unidad_importacion="PZA",
        tipo_importacion=TipoInsumo.MATERIAL,
        unidad_registrada=unidad,
        tipo_registrado=tipo,
    )


@pytest.mark.parametrize(
    ("unidad", "tipo"),
    [("KG", TipoInsumo.MATERIAL), ("PZA", TipoInsumo.MANO_OBRA)],
    ids=["otra_unidad", "otro_tipo"],
)
def test_tkt017_caa06_insumo_en_conflicto_por_descripcion(unidad: str, tipo: TipoInsumo) -> None:
    """TC-A06 · CA-A6 — el conflicto del insumo hallado por descripción trae su código registrado."""
    r = _planificar(
        replace(preparacion_sintetica(), insumos_por_crear=()),
        insumos_registrados=insumos_registrados_sinteticos()
        + (
            InsumoRegistrado(
                id=UUID_TBR,
                codigo="PNL-01",
                descripcion="Panel yeso 1/2",
                unidad=unidad,
                tipo=tipo,
            ),
        ),
    )
    assert r == InsumoEnConflicto(
        codigo="PNL-01",
        unidad_importacion="PZA",
        tipo_importacion=TipoInsumo.MATERIAL,
        unidad_registrada=unidad,
        tipo_registrado=tipo,
    )


def _panel_en_conflicto() -> tuple[InsumoRegistrado, ...]:
    return insumos_registrados_sinteticos() + (
        InsumoRegistrado(
            id=UUID_TBR,
            codigo="PANEL YESO 1/2",
            descripcion="PANEL YESO 1/2",
            unidad="KG",
            tipo=TipoInsumo.MATERIAL,
        ),
    )


def test_tkt017_caa03_la_asignacion_gana_al_conflicto_de_insumos() -> None:
    """TC-A05 · CA-A3 — con ambos defectos responde la asignación inválida (409)."""
    r = _planificar(
        preparacion_sintetica(), asignacion={}, insumos_registrados=_panel_en_conflicto()
    )
    assert isinstance(r, AsignacionInvalida)


def test_tkt017_caa06_el_conflicto_de_insumos_gana_a_la_explosion_rechazada() -> None:
    """TC-A06 · CA-A6 — con ambos defectos responde el insumo en conflicto (409)."""
    r = _planificar(
        preparacion_sintetica_sin_cargo_utilidad(), insumos_registrados=_panel_en_conflicto()
    )
    assert isinstance(r, InsumoEnConflicto)


def test_tkt017_caa06_dos_conceptos_comparten_el_insumo_dado_de_alta_una_sola_vez() -> None:
    """TC-A06 · CA-A6 — la segunda hoja reutiliza el insumo nuevo de la primera."""
    plan = _plan(_planificar(preparacion_dos_conceptos_con_alta_compartida()))
    assert len(plan.insumos_insertar) == 1
    assert len(plan.apus) == 2
    assert [apu.insumos[0].insumo_id for apu in plan.apus] == [plan.insumos_insertar[0].id] * 2


@pytest.mark.parametrize(
    ("unidad", "tipo"),
    [("KG", TipoInsumo.MATERIAL), ("PZA", TipoInsumo.MANO_OBRA)],
    ids=["otra_unidad", "otro_tipo"],
)
def test_tkt017_caa06_alta_que_no_coincide_con_el_insumo_del_analisis(
    unidad: str, tipo: TipoInsumo
) -> None:
    """TC-A06 · CA-A6 — la alta se contrasta con el insumo del análisis desde su primera aparición."""
    r = _planificar(preparacion_con_alta(unidad=unidad, tipo=tipo))
    assert r == InsumoEnConflicto(
        codigo="PANEL YESO 1/2",
        unidad_importacion="PZA",
        tipo_importacion=TipoInsumo.MATERIAL,
        unidad_registrada=unidad,
        tipo_registrado=tipo,
    )


@pytest.mark.parametrize(
    ("unidad", "tipo"),
    [("KG", TipoInsumo.MATERIAL), ("PZA", TipoInsumo.MANO_OBRA)],
    ids=["otra_unidad", "otro_tipo"],
)
def test_tkt017_caa06_alta_compartida_con_otra_unidad_o_tipo_en_la_segunda_aparicion(
    unidad: str, tipo: TipoInsumo
) -> None:
    """TC-A06 · CA-A6 — el segundo concepto que usa la alta también se contrasta con ella."""
    r = _planificar(preparacion_alta_compartida_con_segundo_insumo(unidad=unidad, tipo=tipo))
    assert r == InsumoEnConflicto(
        codigo="PANEL YESO 1/2",
        unidad_importacion=unidad,
        tipo_importacion=tipo,
        unidad_registrada="PZA",
        tipo_registrado=TipoInsumo.MATERIAL,
    )


def test_tkt017_caa06_con_dos_registrados_del_mismo_codigo_gana_el_primero() -> None:
    """TC-A06 · CA-A6 — el insumo registrado se localiza por código y la primera fila manda."""
    primero = InsumoRegistrado(
        id=UUID_TBR,
        codigo="PANEL YESO 1/2",
        descripcion="PANEL YESO 1/2",
        unidad="PZA",
        tipo=TipoInsumo.MATERIAL,
    )
    segundo = replace(primero, id=UUID_OTRO, unidad="KG")
    plan = _plan(
        _planificar(
            preparacion_sintetica(),
            insumos_registrados=insumos_registrados_sinteticos() + (primero, segundo),
        )
    )
    assert plan.insumos_insertar == ()
    assert plan.apus[0].insumos[0].insumo_id == UUID_TBR


def test_tkt017_caa05_explosion_rechazada() -> None:
    """TC-A07 · CA-A5 esc. 2."""
    r1 = _planificar(preparacion_sintetica_cargos_utilidad_indirectos_altos())
    assert isinstance(r1, ExplosionRechazada)
    assert any(
        c.motivo == MotivoRechazoExplosion.SUGERIDO_NEGATIVO
        and c.codigo_concepto is None
        and c.tipo_partida_id == UUID_MUROS
        for c in r1.causas
    )

    r2 = _planificar(preparacion_sintetica_sin_cargo_utilidad())
    assert isinstance(r2, ExplosionRechazada)
    causa = next(c for c in r2.causas if c.motivo == MotivoRechazoExplosion.CARGO_AUSENTE)
    assert causa.codigo_concepto == _CODIGO


def _ruta_sin(**cambios: NodoLeido | None) -> Preparacion:
    return preparacion_con_ruta(**cambios)


_NIVEL_SIN_NOMBRE = NodoLeido(fila=6, profundidad=Profundidad.NIVEL, nombre=None)
_AREA_SIN_NOMBRE = NodoLeido(fila=7, profundidad=Profundidad.AREA, nombre=None)
_PARTIDA_SIN_NOMBRE = NodoLeido(fila=8, profundidad=Profundidad.PARTIDA, nombre=None)
_MIL_MILLONES = "100000000000000"


def _con_cantidad_uno_y_precio_maximo(preparacion: Preparacion) -> Preparacion:
    """Cada importe cabe en NUMERIC(18,4); la suma de la línea base, no."""
    return replace(
        preparacion,
        conceptos=tuple(replace(c, cantidad=Cantidad("1")) for c in preparacion.conceptos),
        analisis=preparacion_con_analisis(precio_unitario=Dinero("99999999999999")).analisis,
    )


def _con_explosion_que_no_cabe() -> Preparacion:
    """El importe de venta cabe; la cantidad de material explotada no."""
    base = preparacion_con_insumo(0, rendimiento=Rendimiento("99999999999.999999"))
    concepto = replace(base.conceptos[0], cantidad=Cantidad("9999999999.9999"))
    return replace(base, conceptos=(concepto, *base.conceptos[1:]))


_CASOS_INCONSISTENTES: list[tuple[str, Callable[[], Preparacion], str, str | None]] = [
    (
        "codigo_repetido_en_la_misma_partida",
        preparacion_codigo_duplicado_en_misma_partida,
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "insumo_sin_registro_ni_alta",
        preparacion_insumo_sin_registro_ni_alta,
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "sin_conceptos",
        lambda: replace(preparacion_sintetica(), conceptos=()),
        _MSJ_PREPARACION,
        None,
    ),
    ("sin_nivel", lambda: _ruta_sin(nivel=None), _MSJ_PREPARACION, _CODIGO),
    ("nivel_sin_nombre", lambda: _ruta_sin(nivel=_NIVEL_SIN_NOMBRE), _MSJ_PREPARACION, _CODIGO),
    ("sin_area", lambda: _ruta_sin(area=None), _MSJ_PREPARACION, _CODIGO),
    ("area_sin_nombre", lambda: _ruta_sin(area=_AREA_SIN_NOMBRE), _MSJ_PREPARACION, _CODIGO),
    ("sin_partida", lambda: _ruta_sin(partida=None), _MSJ_PREPARACION, _CODIGO),
    (
        "partida_sin_nombre",
        lambda: _ruta_sin(partida=_PARTIDA_SIN_NOMBRE),
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "sin_descripcion",
        lambda: preparacion_con_concepto(0, descripcion=None),
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    ("sin_unidad", lambda: preparacion_con_concepto(0, unidad=None), _MSJ_PREPARACION, _CODIGO),
    (
        "sin_asociacion",
        lambda: replace(preparacion_sintetica(), asociaciones=()),
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "dos_asociaciones",
        lambda: replace(
            preparacion_sintetica(),
            asociaciones=preparacion_sintetica().asociaciones
            + (AsociacionLeida(hoja="41-A", codigo=_CODIGO, filas_catalogo=(11,)),),
        ),
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "hoja_inexistente",
        lambda: replace(preparacion_sintetica(), analisis=()),
        _MSJ_PREPARACION,
        _CODIGO,
    ),
    (
        "cantidad_nula",
        lambda: preparacion_con_concepto(0, cantidad=None),
        "partida_concepto.cantidad",
        _CODIGO,
    ),
    ("totales_material_nulo", preparacion_totales_material_nulo, "apu.costo_material", _CODIGO),
    (
        "totales_mano_obra_nulo",
        lambda: preparacion_con_totales(mano_obra=None),
        "apu.costo_mano_obra",
        _CODIGO,
    ),
    (
        "totales_costo_directo_nulo",
        lambda: preparacion_con_totales(costo_directo=None),
        "apu.costo_directo",
        _CODIGO,
    ),
    (
        "totales_cargos_nulo",
        lambda: preparacion_con_totales(cargos=None),
        "apu.total_cargos",
        _CODIGO,
    ),
    (
        "precio_del_pie_nulo",
        lambda: preparacion_con_analisis(precio_unitario=None),
        "apu.precio_unitario",
        _CODIGO,
    ),
    ("mano_obra_sin_costo", preparacion_mano_obra_sin_costo, "apu_insumo.costo_unitario", _CODIGO),
    (
        "mano_obra_sin_rendimiento",
        lambda: preparacion_con_insumo(1, rendimiento=None),
        "apu_insumo.rendimiento",
        _CODIGO,
    ),
    (
        "mano_obra_sin_cargo",
        lambda: preparacion_con_insumo(1, cargo=None),
        "apu_insumo.cargo",
        _CODIGO,
    ),
    (
        "material_sin_costo",
        lambda: preparacion_con_insumo(0, costo_unitario=None),
        "apu_insumo.costo_unitario",
        _CODIGO,
    ),
    (
        "material_sin_rendimiento",
        lambda: preparacion_con_insumo(0, rendimiento=None),
        "apu_insumo.rendimiento",
        _CODIGO,
    ),
    (
        "material_sin_cargo",
        lambda: preparacion_con_insumo(0, cargo=None),
        "apu_insumo.cargo",
        _CODIGO,
    ),
    (
        "material_sin_unidad",
        lambda: preparacion_con_insumo(0, unidad=None),
        "insumo.unidad",
        _CODIGO,
    ),
    ("cargo_sin_tipo", lambda: preparacion_con_cargo(0, tipo=None), "apu_cargo.tipo", _CODIGO),
    (
        "cargo_sin_importe",
        lambda: preparacion_con_cargo(0, importe=None),
        "apu_cargo.importe",
        _CODIGO,
    ),
    (
        "cantidad_que_no_cabe",
        lambda: preparacion_con_concepto(0, cantidad=Cantidad("99999999999")),
        "partida_concepto.cantidad",
        _CODIGO,
    ),
    (
        "precio_del_pie_que_no_cabe",
        lambda: preparacion_con_analisis(precio_unitario=Dinero(_MIL_MILLONES)),
        "apu.precio_unitario",
        _CODIGO,
    ),
    (
        "importe_que_no_cabe",
        lambda: replace(
            preparacion_con_concepto(0, cantidad=Cantidad("9999999999.9999")),
            analisis=preparacion_con_analisis(precio_unitario=Dinero("99999999999999")).analisis,
        ),
        "partida_concepto.importe",
        _CODIGO,
    ),
    (
        "importe_de_venta_que_no_cabe_en_dos_conceptos",
        lambda: _con_cantidad_uno_y_precio_maximo(preparacion_sintetica()),
        "linea_base.importe_venta",
        None,
    ),
    (
        "importe_de_venta_que_no_cabe_en_doce_partidas",
        lambda: _con_cantidad_uno_y_precio_maximo(preparacion_dos_niveles()),
        "linea_base.importe_venta",
        None,
    ),
    ("explosion_que_no_cabe", _con_explosion_que_no_cabe, "explosion_presupuesto", None),
    (
        "mano_obra_sin_unidad",
        lambda: preparacion_con_insumo(1, unidad=None),
        "insumo.unidad",
        _CODIGO,
    ),
    (
        "costo_del_insumo_que_no_cabe",
        lambda: preparacion_con_insumo(0, costo_unitario=Dinero(_MIL_MILLONES)),
        "apu_insumo.costo_unitario",
        _CODIGO,
    ),
    (
        "rendimiento_que_no_cabe",
        lambda: preparacion_con_insumo(1, rendimiento=Rendimiento("1000000000000")),
        "apu_insumo.rendimiento",
        _CODIGO,
    ),
    (
        "cargo_del_insumo_que_no_cabe",
        lambda: preparacion_con_insumo(1, cargo=Dinero(_MIL_MILLONES)),
        "apu_insumo.cargo",
        _CODIGO,
    ),
    (
        "importe_del_cargo_que_no_cabe",
        lambda: preparacion_con_cargo(0, importe=Dinero(_MIL_MILLONES)),
        "apu_cargo.importe",
        _CODIGO,
    ),
    (
        "porcentaje_del_cargo_que_no_cabe",
        lambda: preparacion_con_cargo(0, porcentaje=Porcentaje("1000")),
        "apu_cargo.porcentaje",
        _CODIGO,
    ),
    (
        "base_del_cargo_que_no_cabe",
        lambda: preparacion_con_cargo(0, base=Dinero(_MIL_MILLONES)),
        "apu_cargo.base_calculo",
        _CODIGO,
    ),
    (
        "total_que_no_cabe",
        lambda: preparacion_con_totales(material=Dinero(_MIL_MILLONES)),
        "apu.costo_material",
        _CODIGO,
    ),
]


@pytest.mark.parametrize(
    ("prep_factory", "motivo_esperado", "codigo"),
    [pytest.param(f, m, c, id=nombre) for nombre, f, m, c in _CASOS_INCONSISTENTES],
)
def test_tkt017_caa05_preparacion_inconsistente(
    prep_factory: Callable[[], Preparacion],
    motivo_esperado: str,
    codigo: str | None,
) -> None:
    """TC-A08 · CA-A5 — el rechazo nombra la columna y el concepto."""
    r = _planificar(prep_factory())
    assert r == PreparacionInconsistente(motivo=motivo_esperado, codigo_concepto=codigo)


def test_tkt017_caa05_el_precio_de_los_totales_no_se_exige() -> None:
    """TC-A08 · CA-A5 — `apu.precio_unitario` sale del pie del análisis, no de los totales."""
    plan = _plan(_planificar(preparacion_con_totales(precio_unitario=None)))
    assert plan.apus[0].precio_unitario == Dinero("420.0000")


def test_tkt017_caa05_concepto_nuevo_conserva_la_descripcion_de_la_primera_aparicion() -> None:
    """TC-A04 · CA-A1 — un solo `ConceptoNuevo` por código."""
    plan = _plan(_planificar(preparacion_sintetica()))
    assert plan.conceptos == (
        ConceptoNuevo(
            id=plan.conceptos[0].id,
            codigo=_CODIGO,
            descripcion="Tablaroca en muros",
            unidad="M2",
        ),
    )


def test_tkt017_caa05_el_mismo_codigo_con_otra_unidad_es_inconsistente() -> None:
    """TC-A08 · CA-A5 — la unidad del concepto es del código: otra unidad en otra fila se rechaza."""
    r = _planificar(preparacion_con_concepto(1, unidad="PZA"))
    assert r == PreparacionInconsistente(motivo="concepto.unidad", codigo_concepto=_CODIGO)


def test_tkt017_caa05_el_mismo_codigo_con_otra_descripcion_se_tolera() -> None:
    """TC-A04 · CA-A5 — la descripción distinta no rechaza: gana la primera aparición."""
    plan = _plan(_planificar(preparacion_con_concepto(1, descripcion="Otra descripción")))
    assert [c.descripcion for c in plan.conceptos] == ["Tablaroca en muros"]
    assert [c.unidad for c in plan.conceptos] == ["M2"]
