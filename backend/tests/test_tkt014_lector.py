"""Adaptador del libro de presupuesto (TKT-014b): TC-34 a TC-39."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cimenta.presupuesto.dominio.lectura_analisis import analizar_hoja_apu
from herramientas.soporte_tkt013 import HOJA_ENITI, leer_catalogo_bytes
from herramientas.soporte_tkt014 import (
    escribir_hoja_apu_sintetica,
    hoja_apu_sintetica,
    leer_libro_presupuesto_bytes,
    libro_eniti_con_apu_y_resumen,
)

if TYPE_CHECKING:
    from conftest import Conectar, LibroCatalogo


def test_hdu001_esc05_libro_sintetico_con_catalogo_y_apu(libro_catalogo: LibroCatalogo) -> None:
    """TC-34 · HDU-001 esc. 5 · CA-1, CA-2, CA-R3."""
    contenido = libro_eniti_con_apu_y_resumen(libro_catalogo)
    cat_solo = leer_catalogo_bytes(contenido)
    libro = leer_libro_presupuesto_bytes(contenido)
    assert libro.catalogo == cat_solo
    assert len(libro.analisis) == 2
    assert libro.analisis[0].hoja == "APU X "
    assert libro.analisis[1].hoja == "APU-2"
    assert libro.analisis[0].cabecera.codigo == "P-001"
    assert len(libro.asociaciones) == 2
    resumen = [a for a in libro.analisis if a.hoja == "RESUMEN"]
    assert resumen == []


def test_hdu001_esc05_el_libro_se_abre_una_vez(
    libro_catalogo: LibroCatalogo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-35 · HDU-001 esc. 5 · CA-R3."""
    from openpyxl.worksheet._read_only import ReadOnlyWorksheet

    import cimenta.presupuesto.infraestructura.lector_catalogo as mod

    cargas: list[int] = []
    load_real = mod.load_workbook

    def load_rastreado(*args: Any, **kwargs: Any):
        cargas.append(1)
        return load_real(*args, **kwargs)

    hojas_leidas: list[str] = []
    iter_original = ReadOnlyWorksheet.iter_rows

    def iter_rastreado(self: ReadOnlyWorksheet, *args: Any, **kwargs: Any) -> Iterator[Any]:
        hojas_leidas.append(self.title)
        return iter_original(self, *args, **kwargs)  # type: ignore[call-overload]  # ReadOnlyWorksheet en runtime

    monkeypatch.setattr(mod, "load_workbook", load_rastreado)
    monkeypatch.setattr(ReadOnlyWorksheet, "iter_rows", iter_rastreado)

    contenido = libro_eniti_con_apu_y_resumen(libro_catalogo)
    leer_libro_presupuesto_bytes(contenido)
    assert len(cargas) == 1
    assert hojas_leidas.count(HOJA_ENITI) == 1
    assert "APU X " in hojas_leidas
    assert "APU-2" in hojas_leidas
    assert "RESUMEN" in hojas_leidas


def test_hdu001_esc05_fecha_y_flotantes_del_libro(libro_catalogo: LibroCatalogo) -> None:
    """TC-36 · HDU-001 esc. 5 · CA-15."""
    from tipos_base import Rendimiento

    libro = libro_catalogo
    escribir_hoja_apu_sintetica(libro, "APU-F", fecha="ignored")
    libro.nueva_hoja(HOJA_ENITI)
    from herramientas.soporte_tkt013 import encabezado_eniti, metadatos_siete_filas

    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "R"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "N"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "A"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "P"))
    libro.escribir_fila(HOJA_ENITI, 13, ("P-001", "X", "M2", 1, 1, 1))

    ws = libro._libro["APU-F"]  # noqa: SLF001 — prueba
    ws.cell(row=4, column=3, value=datetime(2025, 9, 1))
    ws.cell(row=8, column=6, value=0.3278)

    resultado = leer_libro_presupuesto_bytes(libro.bytes())
    apu = next(a for a in resultado.analisis if a.hoja == "APU-F")
    assert apu.cabecera.fecha == "2025-09-01"
    insumo = next(i for i in apu.insumos if i.descripcion == "MATERIAL UNO")
    assert insumo.rendimiento == Rendimiento("0.3278")


def test_hdu001_esc06_libro_sintetico_con_rechazos(libro_catalogo: LibroCatalogo) -> None:
    """TC-37 · HDU-001 esc. 6 · CA-6, CA-9, CA-11."""
    libro = libro_catalogo
    escribir_hoja_apu_sintetica(
        libro,
        "APU-R",
        siroc=True,
        pu_cabecera="#REF!",
        celdas_rotas={(8, "F"): "#REF!", (8, "E"): "veinte"},
    )
    libro.nueva_hoja(HOJA_ENITI)
    from herramientas.soporte_tkt013 import encabezado_eniti, metadatos_siete_filas

    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "R"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "N"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "A"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "P"))
    libro.escribir_fila(HOJA_ENITI, 13, ("P-001", "X", "M2", 1, 1, 1))

    esperado = analizar_hoja_apu(
        "APU-R",
        hoja_apu_sintetica(
            siroc=True,
            pu_cabecera="#REF!",
            celdas_rotas={(8, "F"): "#REF!", (8, "E"): "veinte"},
        ),
    )
    assert esperado is not None
    obtenido = leer_libro_presupuesto_bytes(libro.bytes())
    apu = next(a for a in obtenido.analisis if a.hoja == "APU-R")
    assert apu.hallazgos == esperado.hallazgos


def test_hdu001_esc05_leer_libro_no_escribe(libro_catalogo: LibroCatalogo) -> None:
    """TC-38 · HDU-001 esc. 5 · CA-15."""
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto

    firma = inspect.signature(leer_libro_presupuesto)
    assert tuple(firma.parameters) == (
        "contenido",
        "insumos_existentes",
        "al_avanzar",
    )
    parametro_avance = firma.parameters["al_avanzar"]
    assert parametro_avance.default is None
    assert parametro_avance.kind is inspect.Parameter.KEYWORD_ONLY

    raiz = Path(__file__).resolve().parents[1] / "cimenta" / "presupuesto" / "infraestructura"
    fuente = (raiz / "lector_catalogo.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert "sqlalchemy" not in alias.name
                assert "psycopg" not in alias.name
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            assert "sqlalchemy" not in nodo.module
            assert "psycopg" not in nodo.module

    contenido = libro_eniti_con_apu_y_resumen(libro_catalogo)
    r1 = leer_libro_presupuesto_bytes(contenido)
    r2 = leer_libro_presupuesto_bytes(contenido)
    assert r1.catalogo == r2.catalogo
    assert len(r1.analisis) == len(r2.analisis)


@pytest.mark.parametrize("contenido", [b"", b"no es un libro xlsx"])
def test_hdu001_esc27_contenido_invalido_en_libro_presupuesto(contenido: bytes) -> None:
    """TC-39 · HDU-001 esc. 27 · CA-15."""
    cat_esperado = leer_catalogo_bytes(contenido)
    libro = leer_libro_presupuesto_bytes(contenido)
    assert libro.catalogo == cat_esperado
    assert libro.analisis == ()
    assert libro.asociaciones == ()
    assert libro.hallazgos == ()


def test_tkt014_car1_tipos_sincronizados(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-INV-4 · CA-4, M3 — TipoCargo y TipoInsumo vs restricciones PostgreSQL."""
    import re

    from cimenta.presupuesto.dominio.analisis import TipoCargo, TipoInsumo

    with conectar("migracion", base_de_prueba) as conn:
        fila_cargo = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'apu_cargo'::regclass AND conname = 'ck_apu_cargo_tipo'"
        ).fetchone()
        fila_insumo = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'insumo'::regclass AND conname = 'ck_insumo_tipo'"
        ).fetchone()
    assert fila_cargo is not None and fila_insumo is not None
    cargos_pg = frozenset(re.findall(r"'([^']+)'", str(fila_cargo[0])))
    insumos_pg = frozenset(re.findall(r"'([^']+)'", str(fila_insumo[0])))
    assert {m.value for m in TipoCargo} == cargos_pg
    assert {m.value for m in TipoInsumo}.issubset(insumos_pg)
