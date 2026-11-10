"""Rutas del presupuesto de control (TKT-017c, fila C3). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso; no decide nada. Los rechazos (`RN-03`, `RN-04`) los
lanza el caso de uso con las clases de `contrato_error` y los serializa el manejador global.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.presupuesto.api.esquemas import CapturaPresupuestoControl, PresupuestoControl
from cimenta.presupuesto.api.rutas_linea_base import ROLES_DE_LECTURA, contexto_de
from cimenta.presupuesto.aplicacion import consulta_linea_base
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.presupuesto_control import ROLES_CAPTURA, capturar_tope

enrutador = APIRouter(prefix="/api/v1", tags=["presupuesto"])


@enrutador.get(
    "/lineas-base/{linea_base_id}/presupuesto-control",
    operation_id="listar_presupuesto_control",
    dependencies=[Depends(exigir_rol(*ROLES_DE_LECTURA))],
)
def listar_presupuesto_control(
    linea_base_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> list[PresupuestoControl]:
    """RN-03: una fila por tipo de partida con su venta, su sugerido y su tope; vacía en `BORRADOR`."""
    return [
        PresupuestoControl.desde(fila)
        for fila in consulta_linea_base.listar_presupuesto_control(contexto, linea_base_id)
    ]


@enrutador.put(
    "/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}",
    operation_id="capturar_presupuesto_control",
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_CAPTURA))],
)
def capturar_presupuesto_control(
    linea_base_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    cuerpo: CapturaPresupuestoControl,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> PresupuestoControl:
    """RN-03, RN-04: captura o recaptura el tope de control y devuelve la fila ya guardada."""
    control_id = capturar_tope(
        contexto,
        linea_base_id=linea_base_id,
        tipo_partida_id=tipo_partida_id,
        importe_tope=cuerpo.importe_tope,
        motivo=cuerpo.motivo,
        confirmar_superior_a_venta=cuerpo.confirmar_superior_a_venta,
        usuario_id=usuario.usuario_id,
    )
    guardada = next(
        fila
        for fila in consulta_linea_base.listar_presupuesto_control(contexto, linea_base_id)
        if fila.id == control_id
    )
    return PresupuestoControl.desde(guardada)
