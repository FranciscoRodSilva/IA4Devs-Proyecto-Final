"""Consulta de nombres de usuario para otros módulos (TKT-017b1, P-8).

`presupuesto` resuelve `congelada_por`, `capturado_por` y `actualizado_por` con esta función, a través de
`cimenta.identidad.interfaz`, sin tocar las tablas de `identidad`. Es una lectura: usa la `Session` que
recibe de quien llama y no abre ni confirma transacción; la transacción es la del caso de uso que la pide.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy.orm import Session

from cimenta.identidad.infraestructura import repositorio


def nombres_de_usuarios(sesion_bd: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Devuelve el nombre de cada id que existe. Los ids ajenos se ignoran; sin ids, no consulta."""
    return repositorio.nombres_por_id(sesion_bd, ids)
