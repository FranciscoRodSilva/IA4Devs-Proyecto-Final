"""Repositorio del catálogo de proveedores (TKT-029a, fila A3).

Cada función recibe la sesión del caso de uso y no confirma la transacción. Las cifras llegan como
`Dinero` ya validado y se escriben cuantizadas a la escala de la columna; lo que se lee se envuelve en
`Dinero` al salir. La unicidad del RFC la decide el índice `uq_proveedor_rfc`, no esta capa.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, NamedTuple

from sqlalchemy import ColumnElement, Row, func, insert, or_, select, update
from sqlalchemy.orm import Session

from cimenta.proveedores.dominio.proveedor import EstadoProveedor
from cimenta.proveedores.infraestructura.tablas import proveedor
from tipos_base import Dinero

# Claves que `actualizar_proveedor` admite. Otra clave es un defecto del llamador, no del cliente.
CLAVES_ACTUALIZABLES: frozenset[str] = frozenset(
    {"nombre", "tope_consignacion", "dia_corte", "dia_pago", "estado"}
)


class FilaProveedor(NamedTuple):
    id: uuid.UUID
    nombre: str
    rfc: str
    estado: str
    tope_consignacion: Dinero | None
    dia_corte: int
    dia_pago: int
    creado_en: datetime


class PaginaProveedores(NamedTuple):
    filas: list[FilaProveedor]
    total: int


_COLUMNAS_PROVEEDOR = (
    proveedor.c.id,
    proveedor.c.nombre,
    proveedor.c.rfc,
    proveedor.c.estado,
    proveedor.c.tope_consignacion,
    proveedor.c.dia_corte,
    proveedor.c.dia_pago,
    proveedor.c.creado_en,
)


def _dinero_o_nulo(valor: Decimal | None) -> Dinero | None:
    return None if valor is None else Dinero(valor)


def _a_columna(valor: object) -> object:
    """Un `Dinero` se escribe cuantizado a la escala de su columna; lo demás pasa tal cual."""
    return valor.cuantizar().valor if isinstance(valor, Dinero) else valor


def _fila_proveedor(fila: Row[*tuple[Any, ...]]) -> FilaProveedor:
    return FilaProveedor(
        id=fila.id,
        nombre=fila.nombre,
        rfc=fila.rfc,
        estado=fila.estado,
        tope_consignacion=_dinero_o_nulo(fila.tope_consignacion),
        dia_corte=fila.dia_corte,
        dia_pago=fila.dia_pago,
        creado_en=fila.creado_en,
    )


def insertar_proveedor(
    sesion_bd: Session,
    *,
    proveedor_id: uuid.UUID,
    nombre: str,
    rfc: str,
    tope_consignacion: Dinero | None,
    dia_corte: int,
    dia_pago: int,
    creado_en: datetime,
    creado_por_id: uuid.UUID,
) -> None:
    """El proveedor nace `ACTIVO`; el tope se escribe en la escala de la columna."""
    sesion_bd.execute(
        insert(proveedor).values(
            id=proveedor_id,
            nombre=nombre,
            rfc=rfc,
            estado=EstadoProveedor.ACTIVO.value,
            tope_consignacion=_a_columna(tope_consignacion),
            dia_corte=dia_corte,
            dia_pago=dia_pago,
            creado_en=creado_en,
            creado_por_id=creado_por_id,
        )
    )


def leer_proveedor(
    sesion_bd: Session, proveedor_id: uuid.UUID, *, para_cambio: bool = False
) -> FilaProveedor | None:
    """Lectura por id. Con `para_cambio`, `FOR UPDATE`: serializa cambios y desactivaciones."""
    sentencia = select(*_COLUMNAS_PROVEEDOR).where(proveedor.c.id == proveedor_id)
    if para_cambio:
        sentencia = sentencia.with_for_update()
    fila = sesion_bd.execute(sentencia).one_or_none()
    return None if fila is None else _fila_proveedor(fila)


def leer_proveedor_por_rfc(sesion_bd: Session, rfc: str) -> FilaProveedor | None:
    """Lectura por RFC, sin bloqueo: la búsqueda de un duplicado tras un `23505`."""
    fila = sesion_bd.execute(
        select(*_COLUMNAS_PROVEEDOR).where(proveedor.c.rfc == rfc)
    ).one_or_none()
    return None if fila is None else _fila_proveedor(fila)


def listar_proveedores(
    sesion_bd: Session,
    *,
    estados: frozenset[str],
    q: str | None,
    desplazamiento: int,
    limite: int,
) -> PaginaProveedores:
    """Una página del catálogo y el total del mismo filtro.

    `q` se busca sin distinguir mayúsculas en nombre y en RFC, con `%` y `_` literales
    (`autoescape=True`). Orden: `nombre`, `id` (D-8). Si la página es inalcanzable, devuelve la
    lista vacía sin consultar las filas (D20, mismo corte que `conceptos_de_linea_base`).
    """
    condiciones: list[ColumnElement[bool]] = [proveedor.c.estado.in_(sorted(estados))]
    if q is not None:
        condiciones.append(
            or_(
                proveedor.c.nombre.icontains(q, autoescape=True),
                proveedor.c.rfc.icontains(q, autoescape=True),
            )
        )
    total = sesion_bd.scalar(select(func.count()).select_from(proveedor).where(*condiciones)) or 0
    if desplazamiento >= total:
        return PaginaProveedores(filas=[], total=total)
    sentencia = (
        select(*_COLUMNAS_PROVEEDOR)
        .where(*condiciones)
        .order_by(proveedor.c.nombre, proveedor.c.id)
        .offset(desplazamiento)
        .limit(limite)
    )
    filas = [_fila_proveedor(f) for f in sesion_bd.execute(sentencia)]
    return PaginaProveedores(filas=filas, total=total)


def actualizar_proveedor(
    sesion_bd: Session, proveedor_id: uuid.UUID, valores: Mapping[str, object]
) -> None:
    """`UPDATE` solo de las columnas dadas. Un `Dinero` se escribe cuantizado a su escala."""
    no_admitidas = set(valores) - CLAVES_ACTUALIZABLES
    if no_admitidas:
        raise ValueError(f"Columnas de proveedor no actualizables: {sorted(no_admitidas)}")
    if not valores:
        return
    escritura: dict[str, object] = {clave: _a_columna(valor) for clave, valor in valores.items()}
    sesion_bd.execute(update(proveedor).where(proveedor.c.id == proveedor_id).values(escritura))
