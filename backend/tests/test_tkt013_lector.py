"""Infraestructura del lector de catálogo (TKT-013b): TC-31 a TC-40 y TC-INV-4."""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from cimenta.presupuesto.dominio.catalogo import (
    ERRORES_DE_FORMULA,
    UNIDADES_ADMITIDAS,
    CausaHallazgo,
    ConceptoLeido,
    Hallazgo,
)
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    HOJA_UNION,
    encabezado_eniti,
    leer_catalogo_bytes,
    libro_forma_eniti,
    libro_forma_union,
    metadatos_siete_filas,
)

if TYPE_CHECKING:
    from conftest import Conectar, LibroCatalogo

BACKEND = Path(__file__).resolve().parents[1]
MODULOS_NUEVOS_TKT013B = (
    BACKEND / "cimenta/presupuesto/infraestructura/lector_catalogo.py",
    BACKEND / "cimenta/presupuesto/dominio/totales_catalogo.py",
)


def _assert_hallazgo(
    hallazgo: Hallazgo,
    *,
    causa: CausaHallazgo,
    hoja: str | None,
    fila: int | None,
    columna: str | None,
    valor_original: str | None,
) -> None:
    assert hallazgo.causa == causa
    assert hallazgo.hoja == hoja
    assert hallazgo.fila == fila
    assert hallazgo.columna == columna
    assert hallazgo.valor_original == valor_original


def _nombres_ruta(concepto: ConceptoLeido) -> tuple[str | None, str | None, str | None, str | None]:
    r = concepto.ruta

    def _n(nodo: object) -> str | None:
        if nodo is None:
            return None
        nombre = getattr(nodo, "nombre", None)
        return None if nombre is None else str(nombre)

    return (_n(r.raiz), _n(r.nivel), _n(r.area), _n(r.partida))


def test_hdu001_esc05_libro_sintetico_con_la_forma_de_eniti(libro_catalogo: LibroCatalogo) -> None:
    """TC-31 · HDU-001 esc. 5 · CA-1, CA-3 — hoja, rutas y float 16.089."""
    from tipos_base import Cantidad

    cat = leer_catalogo_bytes(libro_forma_eniti(libro_catalogo))
    assert cat.hoja == HOJA_ENITI
    assert cat.fila_encabezado == 8
    assert [c.codigo for c in cat.conceptos] == ["P-001", "P-040-A"]
    primero = cat.conceptos[0]
    assert primero.fila == 13
    assert primero.unidad == "M2"
    assert primero.cantidad == Cantidad(Decimal(repr(16.089)))
    assert _nombres_ruta(primero) == ("RAIZ SYN", "NIVEL A", "ZONA 1", "TRABAJO X")
    assert cat.conceptos[1].codigo == "P-040-A"


def test_hdu001_esc06_libro_sintetico_con_la_forma_de_union_square(
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-32 · HDU-001 esc. 5 y 6 · CA-7, CA-9, CA-11 — #REF! y sin partida."""
    cat = leer_catalogo_bytes(libro_forma_union(libro_catalogo))
    assert cat.hoja == HOJA_UNION
    refs = [h for h in cat.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA]
    assert len(refs) == 6
    for h in refs:
        assert h.hoja == HOJA_UNION
        assert h.columna in ("E", "F")
        assert h.valor_original == "#REF!"
    sin_partida = [h for h in cat.hallazgos if h.causa == CausaHallazgo.CONCEPTO_SIN_PARTIDA]
    assert [h.fila for h in sin_partida] == [12, 13]
    ilegibles = [h for h in cat.hallazgos if h.causa == CausaHallazgo.NOMBRE_ILEGIBLE]
    assert len(ilegibles) == 1
    _assert_hallazgo(
        ilegibles[0],
        causa=CausaHallazgo.NOMBRE_ILEGIBLE,
        hoja=HOJA_UNION,
        fila=14,
        columna="B",
        valor_original="#REF!",
    )
    con_partida = next(c for c in cat.conceptos if c.fila == 16)
    assert con_partida.ruta.partida is not None


@pytest.mark.parametrize(
    ("constructor", "causa"),
    [
        ("sin_hoja_catalogo", CausaHallazgo.HOJA_NO_LOCALIZADA),
        ("sin_encabezado", CausaHallazgo.ENCABEZADO_NO_LOCALIZADO),
        ("sin_conceptos", CausaHallazgo.NINGUN_CONCEPTO),
        ("hoja_ambigua", CausaHallazgo.HOJA_AMBIGUA),
    ],
)
def test_hdu001_esc27_libro_sintetico_sin_catalogo_ni_encabezado_ni_conceptos(
    libro_catalogo: LibroCatalogo, constructor: str, causa: CausaHallazgo
) -> None:
    """TC-38 · HDU-001 esc. 27 · CA-10 — rechazo de estructura sin excepción."""
    libro = libro_catalogo
    if constructor == "sin_hoja_catalogo":
        libro.nueva_hoja("APU 1")
        libro.escribir_fila("APU 1", 1, ("x",))
        contenido = libro.bytes()
    elif constructor == "sin_encabezado":
        libro.nueva_hoja(HOJA_ENITI)
        metadatos_siete_filas(libro, HOJA_ENITI)
        libro.escribir_fila(HOJA_ENITI, 8, (None, "sin codigo"))
        contenido = libro.bytes()
    elif constructor == "sin_conceptos":
        libro.nueva_hoja(HOJA_ENITI)
        metadatos_siete_filas(libro, HOJA_ENITI)
        encabezado_eniti(libro, HOJA_ENITI)
        libro.escribir_fila(HOJA_ENITI, 9, (None, "solo grupo"))
        contenido = libro.bytes()
    else:
        libro.nueva_hoja("CATALOGO")
        libro.nueva_hoja("CATALOGO (2)")
        metadatos_siete_filas(libro, "CATALOGO")
        encabezado_eniti(libro, "CATALOGO")
        contenido = libro.bytes()

    cat = leer_catalogo_bytes(contenido)
    assert cat.conceptos == ()
    assert len(cat.hallazgos) == 1
    assert cat.hallazgos[0].causa == causa


def test_hdu001_esc06_valores_de_celda_que_no_son_numero(libro_catalogo: LibroCatalogo) -> None:
    """TC-39 · HDU-001 esc. 6 · CA-8 — bool, datetime y hueco de filas."""
    libro = libro_catalogo
    libro.nueva_hoja(HOJA_ENITI)
    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "RAIZ"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "NIVEL"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "AREA"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "PART"))
    # filas 13 vacías: hueco hasta 14
    libro.escribir_fila(
        HOJA_ENITI,
        15,
        ("P-BOOL", "x", "M2", True, datetime(2026, 1, 1), 1),
    )
    libro.escribir_fila(HOJA_ENITI, 16, ("P-OK", "y", "M2", 1, 2, 2))

    cat = leer_catalogo_bytes(libro.bytes())
    numeros = [h for h in cat.hallazgos if h.causa == CausaHallazgo.NO_ES_NUMERO]
    assert len(numeros) == 2
    valores = {(h.columna, h.valor_original) for h in numeros}
    assert ("D", "TRUE") in valores
    assert any(col == "E" and val is not None and "2026" in val for col, val in valores)
    filas_concepto = {c.fila for c in cat.conceptos}
    assert filas_concepto == {15, 16}


def _contar_tablas_presupuesto(conectar: Conectar, base_de_prueba: str) -> dict[str, int]:
    tablas = ("nivel", "area", "partida", "concepto")
    with conectar("aplicacion", base_de_prueba) as conn:
        cuentas: dict[str, int] = {}
        for tabla in tablas:
            fila = conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
            assert fila is not None
            cuentas[tabla] = int(fila[0])
        return cuentas


def _todos_decimales(objeto: object) -> None:
    if isinstance(objeto, Decimal):
        return
    if hasattr(objeto, "valor"):
        valor = objeto.valor
        assert isinstance(valor, Decimal)
        assert not isinstance(valor, float)
    if isinstance(objeto, tuple):
        for item in objeto:
            _todos_decimales(item)
    elif hasattr(objeto, "__dataclass_fields__"):
        for campo in objeto.__dataclass_fields__:
            _todos_decimales(getattr(objeto, campo))


def test_hdu001_esc05_leer_no_escribe_ni_usa_float(
    libro_catalogo: LibroCatalogo,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: object,
) -> None:
    """TC-40 · HDU-001 esc. 5 · CA-12 — firma, imports, base intacta, Decimal."""
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_catalogo

    parametros = inspect.signature(leer_catalogo).parameters
    assert tuple(parametros) == ("contenido",)

    for ruta in MODULOS_NUEVOS_TKT013B:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    assert "sqlalchemy" not in alias.name
                    assert "psycopg" not in alias.name
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                assert "sqlalchemy" not in nodo.module
                assert "psycopg" not in nodo.module

    antes = _contar_tablas_presupuesto(conectar, base_de_prueba)
    assert all(cuenta == 0 for cuenta in antes.values())

    contenido = libro_forma_eniti(libro_catalogo)
    cat1 = leer_catalogo(contenido)
    cat2 = leer_catalogo(contenido)
    assert cat1 == cat2

    for concepto in cat1.conceptos:
        if concepto.cantidad is not None:
            assert isinstance(concepto.cantidad.valor, Decimal)
        if concepto.precio_unitario is not None:
            assert isinstance(concepto.precio_unitario.valor, Decimal)
        if concepto.importe is not None:
            assert isinstance(concepto.importe.valor, Decimal)
    _todos_decimales(cat1)

    despues = _contar_tablas_presupuesto(conectar, base_de_prueba)
    assert despues == antes
    _ = datos_presupuesto  # fixture asegura rol de aplicación sobre la misma base


def test_tkt013_car1_constantes_sincronizadas(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-INV-4 · CA-5, CA-7 · invariante 27 — unidades y ERROR_CODES."""
    import openpyxl.cell.cell

    with conectar("migracion", base_de_prueba) as conn:
        fila = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'concepto'::regclass AND conname = 'ck_concepto_unidad'"
        ).fetchone()
    assert fila is not None
    definicion = str(fila[0])
    coincidencias = re.findall(r"'([^']+)'", definicion)
    assert coincidencias
    unidades_pg = frozenset(coincidencias)
    assert unidades_pg == UNIDADES_ADMITIDAS

    assert frozenset(openpyxl.cell.cell.ERROR_CODES) == ERRORES_DE_FORMULA


@pytest.mark.parametrize("contenido", [b"", b"no es un libro xlsx"])
def test_hdu001_esc27_contenido_invalido_devuelve_hallazgo_sin_excepcion(contenido: bytes) -> None:
    """TC-38b · HDU-001 esc. 27 · CA-10 — bytes que no son .xlsx no propagan excepción de zip."""
    cat = leer_catalogo_bytes(contenido)
    assert cat.conceptos == ()
    assert len(cat.hallazgos) == 1
    assert cat.hallazgos[0].causa == CausaHallazgo.HOJA_NO_LOCALIZADA
    assert cat.hallazgos[0].detalle == "el contenido no es un libro Excel válido"


def test_tkt013_defusedxml_activo_y_rechaza_entidades_externas() -> None:
    """O004 · seguridad — openpyxl usa defusedxml y rechaza DOCTYPE con entidad externa."""
    from io import BytesIO
    from zipfile import ZipFile

    import openpyxl

    assert openpyxl.DEFUSEDXML is True

    xlsx = BytesIO()
    with ZipFile(xlsx, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheets/></workbook>",
        )
    with pytest.raises(ValueError):
        leer_catalogo_bytes(xlsx.getvalue())


def test_hdu001_esc05_solo_se_lee_la_hoja_catalogo(
    libro_catalogo: LibroCatalogo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-35 (parte sintética) · CA-1 — iter_rows solo en la hoja del catálogo."""
    from openpyxl.worksheet._read_only import ReadOnlyWorksheet

    hojas_leidas: list[str] = []

    iter_original = ReadOnlyWorksheet.iter_rows

    def iter_rastreado(self: ReadOnlyWorksheet, *args: object, **kwargs: object) -> Iterator[Any]:
        hojas_leidas.append(self.title)
        return iter_original(self, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(ReadOnlyWorksheet, "iter_rows", cast(Any, iter_rastreado))
    cat = leer_catalogo_bytes(libro_forma_eniti(libro_catalogo))
    assert cat.hoja == HOJA_ENITI
    assert hojas_leidas == [HOJA_ENITI]
