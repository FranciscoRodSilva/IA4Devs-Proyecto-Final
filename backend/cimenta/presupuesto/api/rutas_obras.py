"""Rutas de la obra (TKT-012a, fila A4). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso; no decide nada. Los rechazos (rango de los
porcentajes, código duplicado, obra inexistente) los lanza el caso de uso con las clases de
`contrato_error` y los serializa el manejador global.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.presupuesto.api.esquemas import (
    EstadoObra,
    ListaObras,
    Motivo,
    Obra,
    ObraCambios,
    ObraNueva,
)
from cimenta.presupuesto.api.rutas_linea_base import contexto_de
from cimenta.presupuesto.aplicacion import ciclo_vida_obra, mantenimiento_obras, obras
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.obras import ROLES_ALTA, ROLES_LECTURA_OBRA, DatosObraNueva

enrutador = APIRouter(prefix="/api/v1", tags=["presupuesto"])


@enrutador.post(
    "/obras",
    operation_id="crear_obra",
    status_code=201,
    response_model_exclude_unset=True,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def crear_obra(
    cuerpo: ObraNueva,
    respuesta: Response,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """RN-25, PA-02, PA-18: da de alta una obra en `PLANEACION` y la devuelve ya guardada."""
    obra_id = obras.crear_obra(
        contexto,
        datos=DatosObraNueva(
            codigo=cuerpo.codigo,
            nombre=cuerpo.nombre,
            domicilio=cuerpo.domicilio,
            tipo_contrato=cuerpo.tipo_contrato,
            retencion_destajo_pct=cuerpo.retencion_destajo_pct,
            fondo_garantia_pct=cuerpo.fondo_garantia_pct,
            iva_acreditable=cuerpo.iva_acreditable,
            umbral_alerta_pct=cuerpo.umbral_alerta_pct,
        ),
        usuario_id=usuario.usuario_id,
    )
    respuesta.headers["Location"] = f"/api/v1/obras/{obra_id}"
    return Obra.desde(obras.obtener_obra(contexto, obra_id))


@enrutador.get(
    "/obras",
    operation_id="listar_obras",
    response_model_exclude_unset=True,
    dependencies=[Depends(exigir_rol(*ROLES_LECTURA_OBRA))],
)
def listar_obras(
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
    estado: Annotated[list[EstadoObra] | None, Query()] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListaObras:
    """Las obras, por código, con filtro repetible por estado y paginación."""
    estados = frozenset(e.value for e in estado) if estado else None
    return ListaObras.desde(
        obras.listar_obras(contexto, estados=estados, pagina=pagina, tamano_pagina=tamano_pagina)
    )


@enrutador.get(
    "/obras/{obra_id}",
    operation_id="obtener_obra",
    response_model_exclude_unset=True,
    dependencies=[Depends(exigir_rol(*ROLES_LECTURA_OBRA))],
)
def obtener_obra(
    obra_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """Una obra con su línea base vigente, si la hay."""
    return Obra.desde(obras.obtener_obra(contexto, obra_id))


@enrutador.patch(
    "/obras/{obra_id}",
    operation_id="actualizar_obra",
    response_model_exclude_unset=True,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def actualizar_obra(
    obra_id: uuid.UUID,
    cuerpo: ObraCambios,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """RN-25, PA-02, PA-18: edita los campos que trae el cuerpo y devuelve la obra ya guardada."""
    mantenimiento_obras.actualizar_obra(contexto, obra_id, cuerpo.cambios(), usuario.usuario_id)
    return Obra.desde(obras.obtener_obra(contexto, obra_id))


@enrutador.delete(
    "/obras/{obra_id}",
    operation_id="eliminar_obra",
    status_code=204,
    response_model=None,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def eliminar_obra(
    obra_id: uuid.UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> None:
    """RN-01, HDU-001 esc. 20: borra la obra sin historial; con historial, `409` `OBRA_CON_HISTORIAL`."""
    mantenimiento_obras.eliminar_obra(contexto, obra_id, usuario.usuario_id)


@enrutador.post(
    "/obras/{obra_id}/suspension",
    operation_id="suspender_obra",
    response_model_exclude_unset=True,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def suspender_obra(
    obra_id: uuid.UUID,
    cuerpo: Motivo,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """D-2: `ACTIVA → SUSPENDIDA`, con motivo obligatorio."""
    ciclo_vida_obra.suspender_obra(contexto, obra_id, cuerpo.motivo, usuario.usuario_id)
    return Obra.desde(obras.obtener_obra(contexto, obra_id))


@enrutador.post(
    "/obras/{obra_id}/reactivacion",
    operation_id="reactivar_obra",
    response_model_exclude_unset=True,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def reactivar_obra(
    obra_id: uuid.UUID,
    cuerpo: Motivo,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """D-2: `SUSPENDIDA → ACTIVA`, con motivo obligatorio."""
    ciclo_vida_obra.reactivar_obra(contexto, obra_id, cuerpo.motivo, usuario.usuario_id)
    return Obra.desde(obras.obtener_obra(contexto, obra_id))


@enrutador.post(
    "/obras/{obra_id}/cierre",
    operation_id="cerrar_obra",
    response_model_exclude_unset=True,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_ALTA))],
)
def cerrar_obra(
    obra_id: uuid.UUID,
    cuerpo: Motivo,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> Obra:
    """D-2: `PLANEACION`, `ACTIVA` o `SUSPENDIDA → CERRADA`, con motivo obligatorio."""
    ciclo_vida_obra.cerrar_obra(contexto, obra_id, cuerpo.motivo, usuario.usuario_id)
    return Obra.desde(obras.obtener_obra(contexto, obra_id))
