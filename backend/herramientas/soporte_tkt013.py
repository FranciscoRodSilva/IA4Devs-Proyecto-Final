"""Utilidades compartidas de las pruebas TKT-013 (lector de catálogo)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from cimenta.presupuesto.dominio.catalogo import CatalogoLeido, NodoLeido, Ruta

HOJA_ENITI = "CATALOGO"
HOJA_UNION = "CATALOGO DE CONCEPTOS"

RutaNombres = tuple[str | None, str | None, str | None, str | None]

RUTAS_ESPERADAS_ENITI: dict[int, RutaNombres] = {
    13: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_MUROS"),
    14: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_MUROS"),
    16: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_PLAFONES"),
    17: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_PLAFONES"),
    18: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_PLAFONES"),
    19: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_PLAFONES"),
    21: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_GENERALES"),
    22: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_GENERALES"),
    23: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_GENERALES"),
    25: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_ENCHAPES_LOBBY"),
    26: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_LOBBY", "TRABAJO_ENCHAPES_LOBBY"),
    29: ("RAIZ_NEUTRA", "NIVEL 1", "ZONA_ESCALERAS", "TRABAJO_ENCHAPES_CUBO"),
    32: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    33: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    34: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    35: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    36: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    37: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_MUROS"),
    39: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_PLAFONES"),
    40: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_PLAFONES"),
    41: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_PLAFONES"),
    42: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_PLAFONES"),
    43: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_PLAFONES"),
    45: ("RAIZ_NEUTRA", "NIVEL 1", "DEPT_101", "TRABAJO_GENERALES"),
}


def nombres_desde_ruta(ruta: Ruta) -> RutaNombres:
    def _n(nodo: NodoLeido | None) -> str | None:
        return None if nodo is None else nodo.nombre

    return (_n(ruta.raiz), _n(ruta.nivel), _n(ruta.area), _n(ruta.partida))


def leer_catalogo_bytes(contenido: bytes) -> CatalogoLeido:
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_catalogo

    return leer_catalogo(contenido)


class LibroCatalogoPrueba(Protocol):
    def nueva_hoja(self, nombre: str) -> None: ...

    def escribir_fila(self, hoja: str, numero: int, valores: Sequence[Any]) -> None: ...

    def bytes(self) -> bytes: ...


def metadatos_siete_filas(libro: LibroCatalogoPrueba, hoja: str) -> None:
    for fila in range(1, 8):
        libro.escribir_fila(hoja, fila, (None,))


def encabezado_eniti(libro: LibroCatalogoPrueba, hoja: str) -> None:
    libro.escribir_fila(
        hoja,
        8,
        ("Código", "ENCHAPES", "Unidad", "Cantidad", "P.U.", "IMPORTE"),
    )


def encabezado_union(libro: LibroCatalogoPrueba, hoja: str) -> None:
    libro.escribir_fila(
        hoja,
        8,
        (
            "CODIGO",
            "DESCRIPCION COMPLETA",
            "UNIDAD",
            "CANTIDAD",
            "P.U.",
            "IMPORTE",
            "NOTAS",
        ),
    )


def libro_forma_eniti(libro: LibroCatalogoPrueba) -> bytes:
    libro.nueva_hoja("APU 1")
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


def libro_forma_union(libro: LibroCatalogoPrueba) -> bytes:
    libro.nueva_hoja(HOJA_UNION)
    metadatos_siete_filas(libro, HOJA_UNION)
    encabezado_union(libro, HOJA_UNION)
    libro.escribir_fila(HOJA_UNION, 9, (None, "RAIZ U"))
    libro.escribir_fila(HOJA_UNION, 10, (None, "Nivel 1"))
    libro.escribir_fila(HOJA_UNION, 11, (None, "Zona sin partida"))
    for fila, codigo in [(12, "C-001"), (13, "C-002")]:
        libro.escribir_fila(
            HOJA_UNION,
            fila,
            (codigo, f"Desc {codigo}", "M2", 1, "#REF!", "#REF!", None),
        )
    libro.escribir_fila(HOJA_UNION, 14, (None, "#REF!"))
    libro.escribir_fila(HOJA_UNION, 15, (None, "TRABAJO Y"))
    libro.escribir_fila(
        HOJA_UNION,
        16,
        ("C-003", "Con partida", "M2", 1, "#REF!", "#REF!", None),
    )
    return libro.bytes()
