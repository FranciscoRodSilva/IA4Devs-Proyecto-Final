"""Rutas del catálogo de proveedores (TKT-029a, fila B1). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso; no decide nada. Los rechazos (RFC duplicado,
proveedor inexistente, estado que no admite la desactivación) los lanza el caso de uso con las clases
de `contrato_error` y los serializa el manejador global. No existe ninguna ruta `DELETE` (CA-10).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Query, Request, Response

from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.proveedores.api.esquemas import (
    ListaProveedores,
    Motivo,
    Proveedor,
    ProveedorCambios,
    ProveedorNuevo,
)
from cimenta.proveedores.aplicacion import proveedores
from cimenta.proveedores.aplicacion.contexto import ContextoProveedores
from cimenta.proveedores.aplicacion.proveedores import (
    CAMPOS_CAMBIABLES,
    ROLES_GESTION,
    ROLES_LECTURA,
    CambiosProveedor,
    DatosProveedorNuevo,
)
from cimenta.proveedores.dominio.proveedor import EstadoProveedor

enrutador = APIRouter(prefix="/api/v1", tags=["proveedores"])

# Constante de módulo: una lista literal en la firma la marca Ruff `B006`.
ESTADOS_POR_OMISION: Final = [EstadoProveedor.ACTIVO]
SIN_NUL: Final = r"^[^\x00]*$"


def contexto_de(request: Request) -> ContextoProveedores:
    contexto: ContextoProveedores = request.app.state.proveedores
    return contexto


@enrutador.post(
    "/proveedores",
    operation_id="crear_proveedor",
    status_code=201,
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_GESTION))],
)
def crear_proveedor(
    cuerpo: ProveedorNuevo,
    respuesta: Response,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoProveedores, Depends(contexto_de)],
) -> Proveedor:
    """RN-17, CA-1: da de alta un proveedor `ACTIVO` y lo devuelve ya guardado."""
    proveedor_id = proveedores.crear_proveedor(
        contexto,
        datos=DatosProveedorNuevo(
            nombre=cuerpo.nombre,
            rfc=cuerpo.rfc,
            tope_consignacion=cuerpo.tope_consignacion,
            dia_corte=cuerpo.dia_corte,
            dia_pago=cuerpo.dia_pago,
        ),
        usuario_id=usuario.usuario_id,
    )
    respuesta.headers["Location"] = f"/api/v1/proveedores/{proveedor_id}"
    return Proveedor.desde(proveedores.obtener_proveedor(contexto, proveedor_id))


@enrutador.get(
    "/proveedores",
    operation_id="listar_proveedores",
    dependencies=[Depends(exigir_rol(*ROLES_LECTURA))],
)
def listar_proveedores(
    contexto: Annotated[ContextoProveedores, Depends(contexto_de)],
    estado: Annotated[list[EstadoProveedor], Query()] = ESTADOS_POR_OMISION,
    q: Annotated[str | None, Query(pattern=SIN_NUL, max_length=200)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListaProveedores:
    """El catálogo por nombre, con filtro repetible por estado, búsqueda y paginación."""
    return ListaProveedores.desde(
        proveedores.listar_proveedores(
            contexto,
            estados=frozenset(e.value for e in estado),
            q=q,
            pagina=pagina,
            tamano_pagina=tamano_pagina,
        )
    )


@enrutador.get(
    "/proveedores/{proveedor_id}",
    operation_id="obtener_proveedor",
    dependencies=[Depends(exigir_rol(*ROLES_LECTURA))],
)
def obtener_proveedor(
    proveedor_id: uuid.UUID,
    contexto: Annotated[ContextoProveedores, Depends(contexto_de)],
) -> Proveedor:
    """Un proveedor, también si está desactivado."""
    return Proveedor.desde(proveedores.obtener_proveedor(contexto, proveedor_id))


@enrutador.patch(
    "/proveedores/{proveedor_id}",
    operation_id="actualizar_proveedor",
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_GESTION))],
)
def actualizar_proveedor(
    proveedor_id: uuid.UUID,
    cuerpo: ProveedorCambios,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoProveedores, Depends(contexto_de)],
) -> Proveedor:
    """CA-8: cambia solo los datos enviados y devuelve el proveedor releído."""
    proveedores.actualizar_proveedor(
        contexto,
        proveedor_id=proveedor_id,
        cambios=CambiosProveedor(
            presentes=frozenset(cuerpo.model_fields_set & CAMPOS_CAMBIABLES),
            nombre=cuerpo.nombre,
            tope_consignacion=cuerpo.tope_consignacion,
            dia_corte=cuerpo.dia_corte,
            dia_pago=cuerpo.dia_pago,
        ),
        usuario_id=usuario.usuario_id,
    )
    return Proveedor.desde(proveedores.obtener_proveedor(contexto, proveedor_id))


@enrutador.post(
    "/proveedores/{proveedor_id}/desactivacion",
    operation_id="desactivar_proveedor",
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_GESTION))],
)
def desactivar_proveedor(
    proveedor_id: uuid.UUID,
    cuerpo: Motivo,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    contexto: Annotated[ContextoProveedores, Depends(contexto_de)],
) -> Proveedor:
    """CA-9: pasa un proveedor `ACTIVO` a `DESACTIVADO` con motivo y lo devuelve releído."""
    proveedores.desactivar_proveedor(
        contexto,
        proveedor_id=proveedor_id,
        motivo=cuerpo.motivo,
        usuario_id=usuario.usuario_id,
    )
    return Proveedor.desde(proveedores.obtener_proveedor(contexto, proveedor_id))
