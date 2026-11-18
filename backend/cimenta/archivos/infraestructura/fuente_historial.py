"""Fuente de historial de obra de `archivos` (TKT-012b, F001 de la auditoría de cierre).

Cuenta las filas de `archivo` de una obra para el conteo de RN-01 de `presupuesto`. Cuenta **todas** las
filas, en cualquier estado: un adjunto se anula con motivo y nunca se borra (regla 15, ADR-016), así que
cada fila, también la `ANULADA`, cuelga de la obra sin clave foránea que la detenga. `(asumido)` hasta que
la persona dueña confirme que los `CADUCADO` tampoco cuentan.

Usa la sesión del llamador: ve lo que esa transacción ve, no confirma y no abre otra conexión.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cimenta.archivos.infraestructura.repositorio import archivo


class FuenteHistorialArchivos:
    """Cuenta las filas de `archivo` de una obra para el conteo de RN-01 de `presupuesto`."""

    nombre: str = "archivos"

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        """Número de filas de `archivo` de la obra, en cualquier estado. No confirma."""
        sentencia = select(func.count()).select_from(archivo).where(archivo.c.obra_id == obra_id)
        return int(sesion_bd.execute(sentencia).scalar_one())
