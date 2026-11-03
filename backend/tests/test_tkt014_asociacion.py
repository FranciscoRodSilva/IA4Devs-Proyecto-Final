"""Asociación e insumos por crear (TKT-014b): TC-23 a TC-33."""

from __future__ import annotations

import ast
from pathlib import Path

from cimenta.presupuesto.dominio.analisis import TipoInsumo
from cimenta.presupuesto.dominio.asociacion_analisis import (
    asociar_analisis,
    consolidar_libro,
    proponer_insumos,
)
from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo, ValorCelda
from cimenta.presupuesto.dominio.lectura_analisis import analizar_hoja_apu, rotulo_normalizado
from herramientas.soporte_tkt014 import (
    catalogo_con_codigos,
    hoja_apu_sintetica,
    leer_apu_en_memoria,
)


def _expect(hallazgo: Hallazgo, esperado: Hallazgo) -> None:
    assert hallazgo == esperado


def test_hdu001_esc05_asocia_por_codigo() -> None:
    """TC-23 · HDU-001 esc. 5 · CA-5."""
    catalogo = catalogo_con_codigos(
        [(10, "P-001"), (20, " p-001 "), (30, "P-001"), (40, "P-040-A")]
    )
    a1 = leer_apu_en_memoria("APU-1", codigo="P-001")
    a2 = leer_apu_en_memoria("APU-2", codigo="P-040-A")
    asociaciones, sin_analisis, hallazgos = asociar_analisis((a1, a2), catalogo)
    assert hallazgos == ()
    assert sin_analisis == ()
    assert len(asociaciones) == 2
    assert asociaciones[0].hoja == "APU-1"
    assert asociaciones[0].codigo == "P-001"
    assert asociaciones[0].filas_catalogo == (10, 20, 30)
    assert asociaciones[1].codigo == "P-040-A"
    assert asociaciones[1].filas_catalogo == (40,)


def test_hdu001_esc05_codigos_del_catalogo_sin_analisis() -> None:
    """TC-24 · HDU-001 esc. 5 · CA-5."""
    catalogo = catalogo_con_codigos([(1, "P-001"), (2, "P-002"), (3, "P-003")])
    a1 = leer_apu_en_memoria("H1", codigo="P-001")
    asociaciones, sin_analisis, hallazgos = asociar_analisis((a1,), catalogo)
    assert hallazgos == ()
    assert asociaciones[0].codigo == "P-001"
    assert sin_analisis == ("P-002", "P-003")


def test_hdu001_esc07_analisis_sin_codigo() -> None:
    """TC-25 · HDU-001 esc. 7 · CA-7."""
    a_vacio = leer_apu_en_memoria("H-VACIO", codigo="")
    _, _, h1 = asociar_analisis((a_vacio,), catalogo_con_codigos([(1, "P-001")]))
    assert len(h1) == 1
    _expect(
        h1[0],
        Hallazgo(
            CausaHallazgo.ANALISIS_SIN_CODIGO,
            "H-VACIO",
            a_vacio.cabecera.fila_codigo,
            "C",
            None,
        ),
    )

    filas_sin_rotulo = [
        (n, f)
        for n, f in hoja_apu_sintetica()
        if not (f and rotulo_normalizado(str(f[0])) == "codigo")
    ]
    a_sin_rotulo = analizar_hoja_apu("SIN-ROTULO", filas_sin_rotulo)
    assert a_sin_rotulo is not None
    _, _, h2 = asociar_analisis((a_sin_rotulo,), catalogo_con_codigos([(1, "P-001")]))
    _expect(
        h2[0],
        Hallazgo(
            CausaHallazgo.ANALISIS_SIN_CODIGO,
            "SIN-ROTULO",
            None,
            None,
            None,
            "sin rótulo «código»",
        ),
    )

    catalogo = catalogo_con_codigos([(5, "P-001")])
    a_nombre = leer_apu_en_memoria("P-001", codigo="")
    asociaciones, _, hallazgos = asociar_analisis((a_nombre,), catalogo)
    assert asociaciones == ()
    assert any(h.causa == CausaHallazgo.ANALISIS_SIN_CODIGO for h in hallazgos)
    assert a_nombre.insumos  # contenido conservado


def test_hdu001_esc09_codigo_en_dos_hojas() -> None:
    """TC-26 · HDU-001 esc. 9 · CA-8."""
    catalogo = catalogo_con_codigos([(1, "P-014")])
    a1 = leer_apu_en_memoria("Hoja-A", codigo="P-014")
    a2 = leer_apu_en_memoria("Hoja-B", codigo="P-014")
    asociaciones, _, hallazgos = asociar_analisis((a1, a2), catalogo)
    assert asociaciones == ()
    assert len(hallazgos) == 2
    for h in hallazgos:
        assert h.causa == CausaHallazgo.CODIGO_EN_VARIAS_HOJAS
        assert h.valor_original == "P-014"
        assert h.columna == "C"
    assert {h.detalle for h in hallazgos} == {"Hoja-B", "Hoja-A"}
    assert len(a1.insumos) > 0 and len(a2.insumos) > 0


def test_hdu001_esc05_codigo_sin_concepto() -> None:
    """TC-27 · HDU-001 esc. 5 · M5."""
    catalogo = catalogo_con_codigos([(1, "P-001")])
    a = leer_apu_en_memoria("HUERFANA", codigo="P-999")
    asociaciones, _, hallazgos = asociar_analisis((a,), catalogo)
    assert asociaciones == ()
    _expect(
        hallazgos[0],
        Hallazgo(
            CausaHallazgo.CODIGO_SIN_CONCEPTO,
            "HUERFANA",
            a.cabecera.fila_codigo,
            "C",
            "P-999",
        ),
    )


def _filas_con_insumo_extra(desc: str, unidad: str, fila: int = 12) -> list:
    base = list(hoja_apu_sintetica())
    base.insert(
        8,
        (
            fila,
            (desc, None, None, unidad, 1, 1, 1),
        ),
    )
    return base


def test_hdu001_esc10_insumos_por_crear_por_clave() -> None:
    """TC-28 · HDU-001 esc. 10 · CA-12."""
    existentes = {"CANAL 635X3.05 CAL.26": "PZA"}
    filas1 = _filas_con_insumo_extra("canal 635x3.05  cal.26 ", "PZA")
    filas2 = _filas_con_insumo_extra("CANAL 635X3.05 CAL.26 ", "PZA", fila=13)
    filas3 = _filas_con_insumo_extra("TORNILLO S-1", "PZA", fila=14)
    a1 = analizar_hoja_apu("A", filas1)
    a2 = analizar_hoja_apu("B", filas2)
    a3 = analizar_hoja_apu("C", filas3)
    assert a1 and a2 and a3
    propuestos, hallazgos = proponer_insumos((a1, a2, a3), existentes)
    assert hallazgos == ()
    claves = {p.clave for p in propuestos}
    assert "CANAL 635X3.05 CAL.26" not in claves
    assert "TORNILLO S-1" in claves
    t = next(p for p in propuestos if p.clave == "TORNILLO S-1")
    assert t.descripcion == "TORNILLO S-1"
    assert t.unidad == "PZA"
    assert t.tipo == TipoInsumo.MATERIAL
    assert t.creado_en_importacion is True


def test_hdu001_esc10_unidad_fuera_del_catalogo_no_se_propone() -> None:
    """TC-29 · HDU-001 esc. 10 · CA-13."""
    a_lt = analizar_hoja_apu("H-LT", _filas_con_insumo_extra("ITEM LT", "LT"))
    a_m2 = analizar_hoja_apu("H-M2", _filas_con_insumo_extra("ITEM M2", "M²", fila=13))
    assert a_lt and a_m2
    assert "ITEM LT" in {i.clave for i in a_lt.insumos}
    assert "ITEM M2" in {i.clave for i in a_m2.insumos}
    assert any(h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA for h in a_lt.hallazgos)
    assert any(h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA for h in a_m2.hallazgos)
    propuestos, _ = proponer_insumos((a_lt, a_m2), {})
    claves = {p.clave for p in propuestos}
    assert "ITEM LT" not in claves
    assert "ITEM M2" not in claves


def test_hdu001_esc10_unidad_en_conflicto_entre_hojas() -> None:
    """TC-30 · HDU-001 esc. 10 · CA-14."""
    f1 = _filas_con_insumo_extra("TORNILLO S-1", "PZA")
    f2 = _filas_con_insumo_extra("TORNILLO S-1", "CAJA", fila=13)
    a1 = analizar_hoja_apu("H1", f1)
    a2 = analizar_hoja_apu("H2", f2)
    assert a1 and a2
    propuestos, hallazgos = proponer_insumos((a1, a2), {})
    assert "TORNILLO S-1" not in {p.clave for p in propuestos}
    conflictos = [h for h in hallazgos if h.causa == CausaHallazgo.UNIDAD_EN_CONFLICTO]
    assert len(conflictos) == 2
    for h in conflictos:
        assert h.columna == "D"
        assert "TORNILLO S-1" in (h.detalle or "")


def test_hdu001_esc10_unidad_distinta_de_la_existente() -> None:
    """TC-31 · HDU-001 esc. 10 · CA-14."""
    filas = _filas_con_insumo_extra("TORNILLO S-1", "CAJA")
    a = analizar_hoja_apu("H", filas)
    assert a
    propuestos, hallazgos = proponer_insumos((a,), {"TORNILLO S-1": "PZA"})
    assert "TORNILLO S-1" not in {p.clave for p in propuestos}
    h = next(h for h in hallazgos if "TORNILLO S-1" in (h.detalle or ""))
    _expect(
        h,
        Hallazgo(
            CausaHallazgo.UNIDAD_EN_CONFLICTO,
            "H",
            h.fila,
            "D",
            "CAJA",
            "TORNILLO S-1: existente PZA",
        ),
    )


def test_hdu001_esc10_tipo_en_conflicto() -> None:
    """TC-32 · HDU-001 esc. 10 · M6."""
    filas: list[tuple[int, tuple[ValorCelda, ...]]] = []
    for numero, fila in hoja_apu_sintetica():
        if numero == 8 or numero == 11:
            filas.append((numero, ("CLAVO X", None, None, "PZA", 1, 1, 1)))
        else:
            filas.append((numero, fila))
    a = analizar_hoja_apu("H", filas)
    assert a
    propuestos, hallazgos = proponer_insumos((a,), {})
    assert "CLAVO X" not in {p.clave for p in propuestos}
    tipo_h = [h for h in hallazgos if h.causa == CausaHallazgo.TIPO_EN_CONFLICTO]
    assert len(tipo_h) == 2
    assert {h.valor_original for h in tipo_h} == {"MATERIAL", "MANO_OBRA"}
    assert all(h.columna == "A" for h in tipo_h)
    assert all(h.detalle is not None and h.detalle.startswith("CLAVO X:") for h in tipo_h)


def test_hdu001_esc10_el_lector_no_consulta_la_base() -> None:
    """TC-33 · HDU-001 esc. 10 · CA-12, CA-15."""
    import inspect

    sig_a = inspect.signature(asociar_analisis)
    sig_p = inspect.signature(proponer_insumos)
    sig_c = inspect.signature(consolidar_libro)
    assert "insumos_existentes" in sig_p.parameters
    assert "insumos_existentes" in sig_c.parameters
    assert len(sig_a.parameters) == 2

    raiz = Path(__file__).resolve().parents[1] / "cimenta" / "presupuesto" / "dominio"
    for nombre in ("asociacion_analisis.py", "analisis.py"):
        fuente = (raiz / nombre).read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    assert "sqlalchemy" not in alias.name
                    assert "psycopg" not in alias.name
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                assert "sqlalchemy" not in nodo.module
                assert "psycopg" not in nodo.module
