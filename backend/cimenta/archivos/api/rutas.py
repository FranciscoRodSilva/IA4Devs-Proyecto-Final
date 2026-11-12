"""Rutas de archivos (TKT-059, fila 12a). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso y su resultado a HTTP; no decide nada. Los rechazos
los lanza el caso de uso con las clases de `contrato_error` y los serializa el manejador global. Ningún
archivo pasa por una ruta: los archivos van por URL prefirmada (ADR-016).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from cimenta.archivos.api.dependencias import contexto_de_archivos
from cimenta.archivos.api.esquemas import Archivo, UrlDescarga
from cimenta.archivos.aplicacion.confirmacion import ROL_DE_CONFIRMACION, confirmar_archivo
from cimenta.archivos.aplicacion.consulta import emitir_url_descarga, obtener_archivo
from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)

enrutador = APIRouter(prefix="/api/v1/archivos", tags=["archivos"])


ROLES_DE_CONSULTA = ("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")


@enrutador.get(
    "/{archivo_id}",
    operation_id="obtener_archivo",
    response_model=Archivo,
    dependencies=[Depends(exigir_rol(*ROLES_DE_CONSULTA))],
)
def obtener(
    archivo_id: uuid.UUID,
    contexto: Annotated[ContextoArchivos, Depends(contexto_de_archivos)],
) -> Archivo:
    """Metadatos del archivo, sin la clave del objeto."""
    return Archivo.desde(obtener_archivo(contexto, archivo_id=archivo_id))


@enrutador.get(
    "/{archivo_id}/descarga",
    operation_id="obtener_url_descarga_archivo",
    response_model=UrlDescarga,
    dependencies=[Depends(exigir_rol(*ROLES_DE_CONSULTA))],
)
def obtener_url_descarga(
    archivo_id: uuid.UUID,
    contexto: Annotated[ContextoArchivos, Depends(contexto_de_archivos)],
) -> UrlDescarga:
    """ADR-016: una URL prefirmada de lectura de vida corta; los bytes no pasan por la API."""
    return UrlDescarga.desde(emitir_url_descarga(contexto, archivo_id=archivo_id))


@enrutador.post(
    "/{archivo_id}/confirmacion",
    operation_id="confirmar_archivo",
    response_model=Archivo,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(ROL_DE_CONFIRMACION))],
)
def confirmar(
    archivo_id: uuid.UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoArchivos, Depends(contexto_de_archivos)],
) -> Archivo:
    """RNF-19: comprueba el objeto almacenado y, si coincide, deja el archivo `DISPONIBLE`."""
    return Archivo.desde(
        confirmar_archivo(contexto, archivo_id=archivo_id, usuario_id=usuario.usuario_id)
    )
