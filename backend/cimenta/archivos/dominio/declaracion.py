"""Validación de la declaración de un archivo antes de iniciar la subida.

Implementa RNF-06 y PA-15: el tamaño se compara con el límite de la categoría del tipo declarado, y
un tamaño igual al límite se admite (P-4: los límites son mebibytes). El tipo se normaliza con
`strip()` y `lower()` antes de compararlo con la lista blanca (P-12). El nombre se rechaza si trae
un NUL o un sustituto Unicode (U+D800 a U+DFFF): es regla de forma de RNF-06, sin RN en el PRD.
Devuelve todos los defectos en el orden de la tabla de campos del diseño; no lanza excepciones ni
consulta nada externo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cimenta.archivos.dominio.tipos import CategoriaArchivo, categoria_de

LONGITUD_MAXIMA_NOMBRE = 255
BYTES_POR_MIB = 1048576
_PATRON_HASH = re.compile(r"[0-9a-f]{64}")
_NOMBRE_DE_CATEGORIA = {
    CategoriaArchivo.IMAGEN: "imágenes",
    CategoriaArchivo.VIDEO: "videos",
    CategoriaArchivo.DOCUMENTO: "documentos",
}
_MENSAJE_OBLIGATORIO = "El campo es obligatorio."
_MENSAJE_DEMASIADO_LARGO = f"El nombre admite hasta {LONGITUD_MAXIMA_NOMBRE} caracteres."
_MENSAJE_CARACTERES_NO_PERMITIDOS = "El nombre contiene caracteres no permitidos."
_NUL = "\x00"
_PRIMER_SUSTITUTO = "\ud800"
_ULTIMO_SUSTITUTO = "\udfff"
_MENSAJE_NO_POSITIVO = "El tamaño debe ser mayor que cero."
_MENSAJE_FORMATO_HASH = "El SHA-256 son 64 caracteres hexadecimales en minúsculas."
_MENSAJE_VALOR_NO_PERMITIDO = (  # Debe coincidir con TIPOS_ADMITIDOS (tipos.py)
    "El tipo de archivo no está permitido. Se admiten JPEG, PNG, HEIC, WebP, MP4, PDF, XML y XLSX."
)


@dataclass(frozen=True, slots=True)
class LimitesArchivo:
    imagen_bytes: int
    video_bytes: int
    documento_bytes: int

    def de(self, categoria: CategoriaArchivo) -> int:
        match categoria:
            case CategoriaArchivo.IMAGEN:
                return self.imagen_bytes
            case CategoriaArchivo.VIDEO:
                return self.video_bytes
            case CategoriaArchivo.DOCUMENTO:
                return self.documento_bytes


@dataclass(frozen=True, slots=True)
class DefectoDeclaracion:
    campo: str
    codigo: str
    mensaje: str


def evaluar_declaracion(
    *,
    nombre_original: str,
    tamano_bytes: int,
    hash_sha256: str,
    tipo_declarado: str,
    limites: LimitesArchivo,
    campo_raiz: str,
) -> tuple[DefectoDeclaracion, ...]:
    """Implementa PA-15 y RNF-06 (forma del nombre, sin RN). Sin efectos secundarios."""
    tipo = tipo_declarado.strip().lower()
    categoria = categoria_de(tipo)
    defectos = list(_defectos_nombre(nombre_original, campo_raiz))
    if tamano_bytes < 1:
        defectos.append(_defecto(campo_raiz, "tamano_bytes", "NO_POSITIVO", _MENSAJE_NO_POSITIVO))
    if _PATRON_HASH.fullmatch(hash_sha256) is None:
        defectos.append(_defecto(campo_raiz, "hash_sha256", "FORMATO", _MENSAJE_FORMATO_HASH))
    if categoria is None:
        defectos.append(
            _defecto(
                campo_raiz, "tipo_declarado", "VALOR_NO_PERMITIDO", _MENSAJE_VALOR_NO_PERMITIDO
            )
        )
    else:
        limite = limites.de(categoria)
        if tamano_bytes > limite:
            defectos.append(
                _defecto(
                    campo_raiz,
                    "tamano_bytes",
                    "FUERA_DE_RANGO",
                    _mensaje_fuera_de_rango(limite, categoria),
                )
            )
    return tuple(defectos)


def _defectos_nombre(nombre: str, campo_raiz: str) -> tuple[DefectoDeclaracion, ...]:
    if not nombre.strip():
        return (_defecto(campo_raiz, "nombre_original", "OBLIGATORIO", _MENSAJE_OBLIGATORIO),)
    defectos: list[DefectoDeclaracion] = []
    if len(nombre) > LONGITUD_MAXIMA_NOMBRE:
        defectos.append(
            _defecto(campo_raiz, "nombre_original", "DEMASIADO_LARGO", _MENSAJE_DEMASIADO_LARGO)
        )
    if _tiene_caracteres_no_permitidos(nombre):
        defectos.append(
            _defecto(campo_raiz, "nombre_original", "FORMATO", _MENSAJE_CARACTERES_NO_PERMITIDOS)
        )
    return tuple(defectos)


def _tiene_caracteres_no_permitidos(nombre: str) -> bool:
    return any(_es_caracter_no_permitido(caracter) for caracter in nombre)


def _es_caracter_no_permitido(caracter: str) -> bool:
    return caracter == _NUL or _PRIMER_SUSTITUTO <= caracter <= _ULTIMO_SUSTITUTO


def _mensaje_fuera_de_rango(limite: int, categoria: CategoriaArchivo) -> str:
    mebibytes = limite // BYTES_POR_MIB
    return (
        f"El archivo excede el límite de {limite} bytes ({mebibytes} MB) "
        f"para {_NOMBRE_DE_CATEGORIA[categoria]}."
    )


def _defecto(campo_raiz: str, campo: str, codigo: str, mensaje: str) -> DefectoDeclaracion:
    return DefectoDeclaracion(campo=f"{campo_raiz}.{campo}", codigo=codigo, mensaje=mensaje)
