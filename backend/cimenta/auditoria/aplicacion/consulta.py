"""Consulta de la bitácora (TKT-007, M6). Sin transacción propia: lee en la de quien llama."""

import datetime as dt
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from cimenta.auditoria.aplicacion.asentar import defectos_de_momento, rechazar_si_hay_defectos
from cimenta.auditoria.dominio.asiento import AccionBitacora
from cimenta.auditoria.dominio.consulta import (
    PAGINA_POR_OMISION,
    TAMANO_PAGINA_POR_OMISION,
    revisar_filtros,
)
from cimenta.auditoria.infraestructura import repositorio


@dataclass(frozen=True, slots=True)
class AsientoLeido:
    id: uuid.UUID
    entidad_tipo: str
    entidad_id: uuid.UUID
    accion: AccionBitacora
    usuario_id: uuid.UUID
    ocurrido_en: dt.datetime
    datos_antes: Mapping[str, object] | None
    datos_despues: Mapping[str, object] | None
    motivo: str | None
    regla_negocio: str | None
    obra_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class PaginaBitacora:
    elementos: tuple[AsientoLeido, ...]
    pagina: int
    tamano_pagina: int
    total: int


def consultar_bitacora(
    sesion_bd: Session,
    *,
    obra_id: uuid.UUID | None = None,
    regla_negocio: str | None = None,
    entidad_tipo: str | None = None,
    entidad_id: uuid.UUID | None = None,
    accion: Sequence[str] = (),
    usuario_id: uuid.UUID | None = None,
    desde: dt.datetime | None = None,
    hasta: dt.datetime | None = None,
    pagina: int = PAGINA_POR_OMISION,
    tamano_pagina: int = TAMANO_PAGINA_POR_OMISION,
) -> PaginaBitacora:
    """M6 · borrador consultar_bitacora · HDU-003 esc. 11. Valida todo antes de emitir ninguna
    sentencia; después cuenta y lee la página, el más reciente primero con desempate por id
    (PA-T7). Devuelve usuario_id: el nombre lo completa TKT-027 por la interfaz de identidad."""
    rechazar_si_hay_defectos(
        (
            *defectos_de_momento("desde", desde, obligatorio=False),
            *defectos_de_momento("hasta", hasta, obligatorio=False),
        )
    )
    rechazar_si_hay_defectos(
        revisar_filtros(
            pagina=pagina,
            tamano_pagina=tamano_pagina,
            regla_negocio=regla_negocio,
            entidad_tipo=entidad_tipo,
            acciones=accion,
            desde=desde,
            hasta=hasta,
        )
    )
    criterios = repositorio.CriteriosBitacora(
        obra_id=obra_id,
        regla_negocio=regla_negocio,
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        acciones=tuple(AccionBitacora(a) for a in accion),
        usuario_id=usuario_id,
        desde=desde,
        hasta=hasta,
    )
    total = repositorio.contar_asientos(sesion_bd, criterios)
    filas = repositorio.leer_asientos(
        sesion_bd,
        criterios,
        limite=tamano_pagina,
        desplazamiento=(pagina - 1) * tamano_pagina,
    )
    return PaginaBitacora(
        elementos=tuple(AsientoLeido(**fila) for fila in filas),
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        total=total,
    )
