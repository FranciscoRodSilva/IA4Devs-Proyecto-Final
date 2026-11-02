"""Adaptador openpyxl del lector de catálogo (TKT-013b). Único módulo que importa openpyxl."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet._read_only import ReadOnlyWorksheet

from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    CausaHallazgo,
    Hallazgo,
    ValorCelda,
)
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


def leer_catalogo(contenido: bytes) -> CatalogoLeido:
    """Abre el libro, entrega filas al dominio y cierra (HDU-001 esc. 5)."""
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError):
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
    try:
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

        hoja.reset_dimensions()
        filas = (
            (numero, tuple(_a_valor_celda(v) for v in valores))
            for numero, valores in enumerate(hoja.iter_rows(values_only=True), start=1)
        )
        return analizar_hoja(eleccion, filas)
    finally:
        libro.close()
