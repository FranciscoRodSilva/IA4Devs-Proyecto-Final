"""Lector del contenido de un archivo para el ejecutor del análisis (TKT-059, fila 15 · CA-11 · RNF-06).

`crear_lector_contenido` devuelve la función que el ejecutor llama con el identificador de un archivo.
Solo se lee lo `DISPONIBLE`: cualquier otro estado, o un identificador sin fila, lanza `ArchivoNoLegible`
sin llamar al almacén. Una transacción de lectura por llamada, sin bloqueo.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.archivos.dominio.confirmacion import EstadoArchivo
from cimenta.archivos.infraestructura import repositorio


class ArchivoNoLegible(RuntimeError):
    """El archivo no está `DISPONIBLE`, así que su contenido no se puede leer."""


def crear_lector_contenido(contexto: ContextoArchivos) -> Callable[[uuid.UUID], bytes]:
    """Lector por archivo: lee su fila y, si está `DISPONIBLE`, devuelve los bytes de su objeto."""

    def leer_contenido(archivo_id: uuid.UUID) -> bytes:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            fila = repositorio.leer(sesion_bd, archivo_id)
            if fila is None or fila.estado is not EstadoArchivo.DISPONIBLE:
                raise ArchivoNoLegible(f"el archivo {archivo_id} no está DISPONIBLE")
            return contexto.almacen().leer_todo(fila.clave_objeto)

    return leer_contenido
