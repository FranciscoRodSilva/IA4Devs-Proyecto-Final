"""Utilidades compartidas de las pruebas TKT-014 (lector de APU)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cimenta.presupuesto.dominio.analisis import AnalisisDelLibro, AnalisisLeido
from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    ConceptoLeido,
    Ruta,
    ValorCelda,
)
from cimenta.presupuesto.dominio.lectura_analisis import analizar_hoja_apu
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    LibroCatalogoPrueba,
    encabezado_eniti,
    metadatos_siete_filas,
)


def hoja_apu_sintetica(
    *,
    codigo: ValorCelda = "P-001",
    unidad_cab: str = "M2",
    fecha: str = "2025-09-01",
    analista: str = "Analista Prueba",
    pu_cabecera: ValorCelda = Decimal("158.93"),
    pie: ValorCelda | None = None,
    siroc: bool = False,
    celdas_rotas: dict[tuple[int, str], ValorCelda] | None = None,
) -> list[tuple[int, tuple[ValorCelda, ...]]]:
    """Construye filas en memoria con la disposición medida en E-1 (TKT-014a)."""
    pie_valor = pie if pie is not None else (Decimal("160.205") if siroc else Decimal("158.93"))
    pu_c = pu_cabecera

    cuerpo: list[tuple[int, tuple[ValorCelda, ...]]] = [
        (1, ("ANALISTA:", analista)),
        (2, ("CODIGO:", None, codigo)),
        (3, ("UNIDAD:", None, unidad_cab)),
        (4, ("FECHA:", None, fecha)),
        (5, ("P.U:", None, pu_c)),
        (6, ("MATERIAL ", None, None, "UNIDAD", "COSTO", "REND.", "CARGO")),
        (7, ("SACO",)),
        (8, ("MATERIAL UNO", None, None, "PZA", Decimal("10"), Decimal("2"), Decimal("20"))),
        (9, ("MATERIAL DOS", None, None, "KG", Decimal("5"), Decimal("1.5"), Decimal("7.5"))),
        (10, ("MANO DE OBRA",)),
        (11, ("CUADRILLA X", None, None, "JORNAL", Decimal("1000"), Decimal("10"), Decimal("100"))),
        (
            12,
            ("COSTO DIRECTO", None, None, "MATERIAL Y MANO DE OBRA", None, None, Decimal("127.5")),
        ),
        (13, ("CARGOS PORCENTUALES ", None, None, "%")),
        (
            14,
            (
                "HERRAMIENTA MENOR",
                None,
                None,
                Decimal("0.01"),
                Decimal("127.5"),
                None,
                Decimal("1.275"),
            ),
        ),
    ]
    if siroc:
        cuerpo.append(
            (
                15,
                (
                    "SIROC",
                    None,
                    None,
                    Decimal("0.01"),
                    Decimal("127.5"),
                    None,
                    Decimal("1.275"),
                ),
            )
        )
    offset = 1 if siroc else 0
    cuerpo.extend(
        [
            (15 + offset, ("CARGOS VIATICOS Y HOSPEDAJE", None, None, "%")),
            (
                16 + offset,
                (
                    "OFICIAL TABLAROQUERO",
                    None,
                    None,
                    Decimal("0"),
                    Decimal("0"),
                    None,
                    Decimal("0"),
                ),
            ),
            (
                17 + offset,
                (
                    "AYUDANTE TABLAROQUERO",
                    None,
                    None,
                    Decimal("0"),
                    Decimal("0"),
                    None,
                    Decimal("0"),
                ),
            ),
            (
                18 + offset,
                (
                    "INDIRECTOS",
                    None,
                    None,
                    Decimal("0.08"),
                    Decimal("128.775"),
                    None,
                    Decimal("10.302"),
                ),
            ),
            (
                19 + offset,
                (
                    "UTILIDAD ",
                    None,
                    None,
                    Decimal("0.12"),
                    Decimal("128.775"),
                    None,
                    Decimal("15.453"),
                ),
            ),
            (
                20 + offset,
                ("IVA ", None, None, Decimal("0.16"), Decimal("27.5"), None, Decimal("4.4")),
            ),
            (21 + offset, (None, None, None, "PRECIO UNITARIO ", None, None, pie_valor)),
        ]
    )
    filas = cuerpo
    if celdas_rotas:
        columnas = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}
        corregidas: list[tuple[int, tuple[ValorCelda, ...]]] = []
        for numero, fila in filas:
            lista = list(fila)
            for (fila_n, col), valor in celdas_rotas.items():
                if fila_n != numero:
                    continue
                idx = columnas[col]
                while len(lista) <= idx:
                    lista.append(None)
                lista[idx] = valor
            corregidas.append((numero, tuple(lista)))
        return corregidas
    return filas


def fila_apu(numero: int, *valores: ValorCelda) -> tuple[int, tuple[ValorCelda, ...]]:
    return (numero, valores)


def catalogo_con_codigos(pares: Sequence[tuple[int, str]]) -> CatalogoLeido:
    """Catálogo mínimo con conceptos en las filas indicadas (pruebas TKT-014b)."""
    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    conceptos = tuple(
        ConceptoLeido(
            fila=fila,
            codigo=codigo,
            descripcion=None,
            unidad="M2",
            cantidad=None,
            precio_unitario=None,
            importe=None,
            ruta=ruta,
        )
        for fila, codigo in pares
    )
    return CatalogoLeido(
        hoja="CATALOGO",
        fila_encabezado=8,
        nodos=(),
        conceptos=conceptos,
        hallazgos=(),
    )


def leer_apu_en_memoria(hoja: str, **variantes: Any) -> AnalisisLeido:
    """Analiza la hoja sintética con el nombre de hoja dado."""
    filas = hoja_apu_sintetica(**variantes)
    resultado = analizar_hoja_apu(hoja, filas)
    assert resultado is not None
    return resultado


def escribir_hoja_apu_sintetica(
    libro: LibroCatalogoPrueba,
    nombre: str,
    **variantes: Any,
) -> None:
    """Materializa `hoja_apu_sintetica` en una hoja del libro de prueba."""
    libro.nueva_hoja(nombre)
    for numero, fila in hoja_apu_sintetica(**variantes):
        celdas = list(fila)
        while len(celdas) < 7:
            celdas.append(None)
        libro.escribir_fila(nombre, numero, tuple(celdas[:7]))


def libro_eniti_con_apu_y_resumen(libro: LibroCatalogoPrueba) -> bytes:
    """Catálogo ENITI sintético con dos APU y hoja RESUMEN (TC-34)."""
    escribir_hoja_apu_sintetica(libro, "APU X ", codigo="P-001")
    escribir_hoja_apu_sintetica(libro, "APU-2", codigo="P-040-A")
    libro.nueva_hoja("RESUMEN")
    libro.nueva_hoja(HOJA_ENITI)
    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "RAIZ SYN"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "NIVEL A"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "ZONA 1"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "TRABAJO X"))
    libro.escribir_fila(
        HOJA_ENITI,
        13,
        ("P-001", "Concepto uno", "M2", 16.089, 668.69, 10758.55341),
    )
    libro.escribir_fila(
        HOJA_ENITI,
        14,
        ("P-040-A", "Con sufijo", "M2", 1, 10, 10),
    )
    return libro.bytes()


def leer_libro_presupuesto_bytes(
    contenido: bytes,
    insumos_existentes: Mapping[str, str] | None = None,
) -> AnalisisDelLibro:
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto

    return leer_libro_presupuesto(contenido, insumos_existentes or {})
