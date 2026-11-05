"""Adaptador openpyxl del lector de catálogo (TKT-013b) y libro APU (TKT-014b).

Único módulo que importa openpyxl.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from decimal import Decimal
from io import BytesIO
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet._read_only import ReadOnlyWorksheet

from cimenta.presupuesto.dominio.analisis import AnalisisDelLibro, AnalisisLeido
from cimenta.presupuesto.dominio.asociacion_analisis import consolidar_libro
from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    CausaHallazgo,
    Hallazgo,
    ValorCelda,
)
from cimenta.presupuesto.dominio.lectura_analisis import analizar_hoja_apu
from cimenta.presupuesto.dominio.lectura_catalogo import (
    analizar_hoja,
    catalogo_sin_conceptos,
    elegir_hoja,
)


def _a_valor_celda(valor: object) -> ValorCelda:
    if valor is None or isinstance(valor, str):
        return valor
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return Decimal(repr(valor))
    return str(valor)


def _filas(hoja: ReadOnlyWorksheet) -> Iterator[tuple[int, tuple[ValorCelda, ...]]]:
    hoja.reset_dimensions()
    for numero, valores in enumerate(
        hoja.iter_rows(values_only=True),  # type: ignore[misc]  # stubs: Worksheet, no ReadOnlyWorksheet
        start=1,
    ):
        yield numero, tuple(_a_valor_celda(v) for v in valores)


def _catalogo_archivo_invalido() -> CatalogoLeido:
    return catalogo_sin_conceptos(
        Hallazgo(
            causa=CausaHallazgo.HOJA_NO_LOCALIZADA,
            hoja=None,
            fila=None,
            columna=None,
            valor_original=None,
            detalle="el contenido no es un libro Excel válido",
        )
    )


def _leer_catalogo_de_libro(libro: Workbook) -> CatalogoLeido:
    eleccion = elegir_hoja(libro.sheetnames)
    if isinstance(eleccion, Hallazgo):
        return catalogo_sin_conceptos(eleccion)

    hoja = libro[eleccion]
    if not isinstance(hoja, ReadOnlyWorksheet):
        return catalogo_sin_conceptos(
            Hallazgo(
                causa=CausaHallazgo.HOJA_NO_LOCALIZADA,
                hoja=eleccion,
                fila=None,
                columna=None,
                valor_original=None,
                detalle="no es una hoja de cálculo",
            )
        )

    return analizar_hoja(eleccion, _filas(hoja))


def _libro_presupuesto_vacio(catalogo: CatalogoLeido) -> AnalisisDelLibro:
    return AnalisisDelLibro(
        catalogo=catalogo,
        analisis=(),
        asociaciones=(),
        codigos_sin_analisis=(),
        insumos_por_crear=(),
        hallazgos=(),
    )


def leer_catalogo(contenido: bytes) -> CatalogoLeido:
    """Abre el libro, entrega filas al dominio y cierra (HDU-001 esc. 5)."""
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError):
        return _catalogo_archivo_invalido()
    try:
        return _leer_catalogo_de_libro(libro)
    finally:
        libro.close()


def leer_libro_presupuesto(
    contenido: bytes,
    insumos_existentes: Mapping[str, str],
    *,
    al_avanzar: Callable[[int, int], None] | None = None,
) -> AnalisisDelLibro:
    """Lee catálogo y hojas APU en una sola apertura (HDU-001 esc. 5; TKT-014b)."""
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError):
        return _libro_presupuesto_vacio(_catalogo_archivo_invalido())
    try:
        catalogo = _leer_catalogo_de_libro(libro)
        total = len(libro.sheetnames)
        contador = 0
        if catalogo.hoja is not None and al_avanzar is not None:
            al_avanzar(1, total)
            contador = 1
        analisis_leidos: list[AnalisisLeido] = []
        for nombre in libro.sheetnames:
            if nombre == catalogo.hoja:
                continue
            hoja = libro[nombre]
            if isinstance(hoja, ReadOnlyWorksheet):
                resultado = analizar_hoja_apu(nombre, _filas(hoja))
                if resultado is not None:
                    analisis_leidos.append(resultado)
            contador += 1
            if al_avanzar is not None:
                al_avanzar(contador, total)
        return consolidar_libro(catalogo, analisis_leidos, insumos_existentes)
    finally:
        libro.close()
