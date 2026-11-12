"""Puerto del almacén de objetos: lo que la aplicación de archivos necesita del almacén.

Implementa RNF-06 y ADR-016: el archivo no pasa por el API. El almacén firma URL prefirmadas para
subir y para leer, confirma metadatos, lee rangos y reescribe el tipo MIME dentro del propio almacén.
El puerto es un `Protocol` estructural: el adaptador real vive en `infraestructura/almacen_s3.py` y
no lo importa, así que `aplicacion/` no depende de ninguna librería de almacenamiento. Las URL de
subida llevan la suma SHA-256 firmada (E-1): si el cuerpo no coincide, el almacén rechaza el PUT
(PA-T59.6). `UrlFirmada` se define en `dominio/url_firmada.py` y aquí solo se re-exporta. Sin efectos
secundarios en este módulo.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from cimenta.archivos.dominio.confirmacion import ObjetoAlmacenado
from cimenta.archivos.dominio.url_firmada import UrlFirmada

__all__ = ["AlmacenObjetos", "UrlFirmada"]


class AlmacenObjetos(Protocol):
    """Operaciones del almacén de objetos que usa la aplicación de archivos (RNF-06, ADR-016)."""

    def url_subida(
        self, clave: str, *, tamano_bytes: int, sha256_hex: str, vida: timedelta
    ) -> UrlFirmada:
        """Firma una URL de subida con el tamaño y la suma declarados (RNF-19, PA-T59.6)."""
        ...

    def metadatos(self, clave: str) -> ObjetoAlmacenado | None:
        """Tamaño y suma del objeto; `None` si la clave no tiene objeto (ausencia, no error)."""
        ...

    def leer_rango(self, clave: str, inicio: int, fin: int) -> bytes:
        """Bytes `inicio` a `fin`, ambos inclusivos. Una clave sin objeto propaga el error del almacén."""
        ...

    def leer_todo(self, clave: str) -> bytes:
        """Contenido completo del objeto. Solo lo usa el lector del ejecutor, nunca una ruta del API."""
        ...

    def reescribir_tipo(self, clave: str, tipo_mime: str) -> None:
        """Fija el tipo MIME del objeto con una copia dentro del almacén, conservando su suma."""
        ...

    def url_lectura(
        self,
        clave: str,
        *,
        vida: timedelta,
        tipo_mime: str,
        nombre_original: str,
        disposicion: str,
    ) -> str:
        """Firma una URL de lectura con el tipo y la disposición de descarga (ADR-016, regla 3)."""
        ...
