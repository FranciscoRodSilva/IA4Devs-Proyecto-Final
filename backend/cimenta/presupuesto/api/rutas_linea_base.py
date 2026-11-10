"""Rutas de la línea base (TKT-017b1, fila B3). Todas `def`, nunca `async def`.

La ruta traduce HTTP a una llamada al caso de uso y su resultado a HTTP; no decide nada. Los rechazos
los lanza el caso de uso con las clases de `contrato_error` y los serializa el manejador global.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from cimenta.identidad.interfaz import (
    UsuarioAutenticado,
    exigir_rol,
    sesion_vigente,
    verificar_origen,
)
from cimenta.presupuesto.api.esquemas import (
    ExplosionInsumos,
    LineaBase,
    ListaConceptosLineaBase,
    Motivo,
)
from cimenta.presupuesto.aplicacion import consulta_linea_base
from cimenta.presupuesto.aplicacion.congelado import ROLES_CONGELADO
from cimenta.presupuesto.aplicacion.congelado import congelar_linea_base as congelar
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto

enrutador = APIRouter(prefix="/api/v1", tags=["presupuesto"])

ROLES_DE_LECTURA = ("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "COMPRAS")
SIN_NUL = r"^[^\x00]*$"


def contexto_de(request: Request) -> ContextoPresupuesto:
    contexto: ContextoPresupuesto = request.app.state.presupuesto
    return contexto


@enrutador.post(
    "/lineas-base/{linea_base_id}/congelacion",
    operation_id="congelar_linea_base",
    dependencies=[Depends(verificar_origen), Depends(exigir_rol(*ROLES_CONGELADO))],
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
    return LineaBase.desde(
        consulta_linea_base.obtener_linea_base(contexto, linea_base_id=linea_base_id)
    )


@enrutador.get(
    "/obras/{obra_id}/lineas-base",
    operation_id="listar_lineas_base",
    dependencies=[Depends(exigir_rol(*ROLES_DE_LECTURA))],
)
def listar_lineas_base(
    obra_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> list[LineaBase]:
    """RN-01: las versiones de línea base de la obra, la más reciente primero."""
    return [
        LineaBase.desde(linea)
        for linea in consulta_linea_base.listar_lineas_base(contexto, obra_id)
    ]


@enrutador.get(
    "/lineas-base/{linea_base_id}",
    operation_id="obtener_linea_base",
    dependencies=[Depends(exigir_rol(*ROLES_DE_LECTURA))],
)
def obtener_linea_base(
    linea_base_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
) -> LineaBase:
    """RN-01: una línea base con sus totales por tipo de partida."""
    return LineaBase.desde(
        consulta_linea_base.obtener_linea_base(contexto, linea_base_id=linea_base_id)
    )


@enrutador.get(
    "/lineas-base/{linea_base_id}/conceptos",
    operation_id="listar_conceptos_linea_base",
    dependencies=[Depends(exigir_rol(*ROLES_DE_LECTURA))],
)
def listar_conceptos_linea_base(
    linea_base_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
    tipo_partida_id: uuid.UUID | None = None,
    nivel: Annotated[str | None, Query(pattern=SIN_NUL)] = None,
    q: Annotated[str | None, Query(pattern=SIN_NUL)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListaConceptosLineaBase:
    """RN-01: una página de los conceptos copiados a la línea base; vacía en `BORRADOR`."""
    return ListaConceptosLineaBase.desde(
        consulta_linea_base.listar_conceptos(
            contexto,
            linea_base_id,
            tipo_partida_id=tipo_partida_id,
            nivel=nivel,
            q=q,
            pagina=pagina,
            tamano_pagina=tamano_pagina,
        )
    )


@enrutador.get(
    "/lineas-base/{linea_base_id}/explosion",
    operation_id="obtener_explosion_insumos",
    dependencies=[Depends(exigir_rol(*ROLES_DE_LECTURA))],
)
def obtener_explosion_insumos(
    linea_base_id: uuid.UUID,
    contexto: Annotated[ContextoPresupuesto, Depends(contexto_de)],
    tipo_partida_id: uuid.UUID | None = None,
) -> ExplosionInsumos:
    """RN-24: la explosión de insumos congelada; vacía en `BORRADOR`."""
    return ExplosionInsumos.desde(
        consulta_linea_base.obtener_explosion(
            contexto, linea_base_id, tipo_partida_id=tipo_partida_id
        )
    )
