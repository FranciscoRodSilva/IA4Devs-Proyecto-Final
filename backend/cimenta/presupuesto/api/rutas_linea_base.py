"""Rutas de la línea base (TKT-017b1, fila B3). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso y su resultado a HTTP; no decide nada. Los rechazos
los lanza el caso de uso con las clases de `contrato_error` y los serializa el manejador global.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.presupuesto.api.esquemas import LineaBase, Motivo
from cimenta.presupuesto.aplicacion.congelado import congelar_linea_base as congelar
from cimenta.presupuesto.aplicacion.consulta_linea_base import obtener_linea_base
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto

enrutador = APIRouter(prefix="/api/v1/lineas-base", tags=["presupuesto"])


def contexto_de(request: Request) -> ContextoPresupuesto:
    contexto: ContextoPresupuesto = request.app.state.presupuesto
    return contexto


@enrutador.post(
    "/{linea_base_id}/congelacion",
    operation_id="congelar_linea_base",
    dependencies=[Depends(verificar_origen), Depends(exigir_rol("DIRECTOR_PROYECTOS"))],
)
def congelar_linea_base(
    linea_base_id: uuid.UUID,
    cuerpo: Motivo,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> LineaBase:
    """RN-01: congela la línea base `BORRADOR` y devuelve la línea base ya congelada."""
    congelar(
        contexto,
        linea_base_id=linea_base_id,
        motivo=cuerpo.motivo,
        usuario_id=usuario.usuario_id,
    )
    return LineaBase.desde(obtener_linea_base(contexto, linea_base_id=linea_base_id))
