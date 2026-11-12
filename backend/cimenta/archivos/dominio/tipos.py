"""Lista blanca de tipos MIME del almacén de archivos.

Implementa RNF-06 y PA-15: solo entran los tipos de esta lista, en este orden, y cada uno pertenece a
una categoría que fija su límite de tamaño. La disposición de descarga (`inline` o `attachment`) se
deriva de la categoría: el SVG y los tipos fuera de la lista no tienen categoría ni disposición. La
comparación es exacta: los alias se rechazan (PA-T59.5, P-12). Sin efectos secundarios.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

TIPO_XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CategoriaArchivo(StrEnum):
    IMAGEN = "IMAGEN"
    VIDEO = "VIDEO"
    DOCUMENTO = "DOCUMENTO"


TIPOS_ADMITIDOS: Final[tuple[tuple[str, CategoriaArchivo], ...]] = (
    ("image/jpeg", CategoriaArchivo.IMAGEN),
    ("image/png", CategoriaArchivo.IMAGEN),
    ("image/heic", CategoriaArchivo.IMAGEN),
    ("image/webp", CategoriaArchivo.IMAGEN),
    ("video/mp4", CategoriaArchivo.VIDEO),
    ("application/pdf", CategoriaArchivo.DOCUMENTO),
    ("application/xml", CategoriaArchivo.DOCUMENTO),
    (TIPO_XLSX, CategoriaArchivo.DOCUMENTO),
)

_CATEGORIA_POR_TIPO: Final = dict(TIPOS_ADMITIDOS)
_CATEGORIAS_INLINE: Final = frozenset({CategoriaArchivo.IMAGEN, CategoriaArchivo.VIDEO})


def tipos_admitidos() -> tuple[str, ...]:
    return tuple(tipo for tipo, _ in TIPOS_ADMITIDOS)


def tipo_admitido(tipo_mime: str) -> bool:
    return tipo_mime in _CATEGORIA_POR_TIPO


def categoria_de(tipo_mime: str) -> CategoriaArchivo | None:
    return _CATEGORIA_POR_TIPO.get(tipo_mime)


def disposicion_de(tipo_mime: str) -> str | None:
    categoria = categoria_de(tipo_mime)
    if categoria is None:
        return None
    return "inline" if categoria in _CATEGORIAS_INLINE else "attachment"
