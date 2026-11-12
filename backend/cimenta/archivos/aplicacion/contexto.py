"""Contexto de archivos: lo que los casos de uso del módulo reciben por inyección (TKT-059, fila 8).

`construir_contexto` es perezoso, como el de identidad: no abre el motor ni crea el cliente del
almacén hasta que un caso de uso los pide, así que la aplicación puede construirse sin variables de
base ni del almacén. El reloj se inyecta; sin él, la hora del sistema en UTC.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cimenta.archivos.aplicacion.puertos import AlmacenObjetos
from cimenta.archivos.dominio.declaracion import LimitesArchivo


class AlmacenNoConfigurado(RuntimeError):
    """El almacén de objetos no tiene sus variables: un caso de uso que lo necesita no puede seguir."""


@dataclass(frozen=True, slots=True)
class ConfiguracionArchivos:
    """Plazos y límites de los archivos, leídos de los ajustes del servidor (TKT-059, CA-2)."""

    vida_url_subida: timedelta
    vida_url_lectura: timedelta
    umbral_pendiente: timedelta
    limites: LimitesArchivo


@dataclass(frozen=True, slots=True)
class ContextoArchivos:
    """Dependencias del módulo `archivos` para sus casos de uso.

    `almacen` es perezoso: la primera llamada crea el adaptador y las siguientes reciben el mismo.
    """

    fabrica_sesiones: Callable[[], sessionmaker[Session]]
    almacen: Callable[[], AlmacenObjetos]
    configuracion: ConfiguracionArchivos
    reloj: Callable[[], datetime]


def _reloj_del_sistema() -> datetime:
    """Instante actual en UTC. Solo se usa si nadie inyecta un reloj."""
    return datetime.now(UTC)


def construir_contexto(
    *,
    proveedor_motor: Callable[[], Engine],
    proveedor_almacen: Callable[[], AlmacenObjetos],
    configuracion: ConfiguracionArchivos,
    reloj: Callable[[], datetime] | None,
) -> ContextoArchivos:
    """La fábrica de sesiones pide el motor una sola vez, al primer uso (como en identidad)."""

    @functools.cache
    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=proveedor_motor(), expire_on_commit=False)

    return ContextoArchivos(
        fabrica_sesiones=fabrica,
        almacen=proveedor_almacen,
        configuracion=configuracion,
        reloj=reloj if reloj is not None else _reloj_del_sistema,
    )
