"""Historial de la obra por puerto inyectado (TKT-012b, fila A4).

`presupuesto` no importa a los módulos que cuelgan de la obra: el contrato `grafo-compras` lo prohíbe.
Por eso el conteo de movimientos llega por `FuenteHistorialObra`, que cada módulo posterior implementará
y que `servidor/` inyectará en el contexto. Decisión y alternativas descartadas en
`docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

from sqlalchemy.orm import Session

from cimenta.presupuesto.dominio.historial_obra import ConteosHistorial
from cimenta.presupuesto.infraestructura.repositorio_obra import contar_historial_propio

if TYPE_CHECKING:
    from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto


class FuenteHistorialObra(Protocol):
    """Lo que un módulo posterior publica para decir cuántos movimientos cuelgan de una obra."""

    nombre: str

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int: ...


def contar_historial(
    sesion_bd: Session, contexto: ContextoPresupuesto, obra_id: uuid.UUID
) -> ConteosHistorial:
    """Reúne los conteos de RN-01 (HDU-001 esc. 20) para decidir si la obra se puede borrar.

    Garantiza: lo propio sale del repositorio de `presupuesto`; cada fuente inyectada se consulta una
    vez, con la misma sesión y la misma obra, y su conteo se suma en `movimientos`.
    Asume: el llamador ya tomó el `FOR UPDATE` de la obra en esa transacción. No abre otra sesión,
    no confirma y no traga el fallo de una fuente: si una falla, el error sale tal cual y el borrado no
    llega a ocurrir.
    """
    propio = contar_historial_propio(sesion_bd, obra_id)
    movimientos = sum(fuente.contar(sesion_bd, obra_id) for fuente in contexto.fuentes_historial)
    return ConteosHistorial(
        lineas_base=propio.lineas_base,
        linea_base_congelada=propio.linea_base_congelada,
        importaciones=propio.importaciones,
        filas_propias=(
            propio.niveles
            + propio.conceptos
            + propio.precios_insumo
            + propio.rendimientos_observados
        ),
        movimientos=movimientos,
    )
