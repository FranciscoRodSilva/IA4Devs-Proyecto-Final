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
from cimenta.archivos.api.esquemas import Archivo
from cimenta.archivos.aplicacion.confirmacion import ROL_DE_CONFIRMACION, confirmar_archivo
from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)

enrutador = APIRouter(prefix="/api/v1/archivos", tags=["archivos"])


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
