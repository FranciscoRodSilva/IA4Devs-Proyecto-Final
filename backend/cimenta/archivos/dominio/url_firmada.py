"""URL prefirmada de subida y sus cabeceras obligatorias (RNF-06, RNF-19, ADR-016).

Objeto de valor sin comportamiento. Vive en `dominio/` y no en `aplicacion/puertos.py` porque el
adaptador del almacén (`infraestructura/almacen_s3.py`) lo construye, y la capa de infraestructura
no puede importar la de aplicación. `aplicacion/puertos.py` lo re-exporta para quien lo use desde
la capa de aplicación. La suma `x-amz-checksum-sha256` va firmada (E-1): el navegador no puede
cambiarla sin invalidar la firma. Sin efectos secundarios.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UrlFirmada:
    """Una URL prefirmada de subida y las cabeceras que el cliente debe enviar con el PUT.

    `cabeceras` lleva `x-amz-checksum-sha256` con el SHA-256 en base64. `Content-Length` no se
    devuelve porque el navegador lo fija y JavaScript no puede asignarlo.
    """

    url: str
    cabeceras: dict[str, str]
