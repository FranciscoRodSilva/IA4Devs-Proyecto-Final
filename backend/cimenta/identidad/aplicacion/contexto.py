"""Contexto de identidad: lo que los casos de uso de sesión reciben por inyección (TKT-006, CA-R4 y D-2).

`construir_contexto` es perezoso: no abre el motor hasta que un caso de uso pide una sesión, así que
`fastapi dev` y `uvicorn` pueden construir la aplicación sin variables de base. El hash de descarte se
calcula al construir el adaptador de contraseñas, no en el primer intento de inicio de sesión.
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
from cimenta.identidad.aplicacion.reloj import Reloj, reloj_del_sistema
from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2


class Contrasenas(Protocol):
    hash_de_descarte: str

    def derivar(self, contrasena: str) -> str: ...

    def verificar(self, contrasena: str, hash_guardado: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class UsuarioAutenticado:
    """Quien llama, tal como lo deja una sesión vigente. Inmutable durante la petición (CA-R4 · M7)."""

    usuario_id: uuid.UUID
    sesion_id: uuid.UUID
    nombre: str
    email: str
    roles: frozenset[str]
    expira_en: datetime
    expira_por_inactividad_en: datetime


@dataclass(frozen=True, slots=True)
class ContextoIdentidad:
    """Dependencias del módulo `identidad` para sus casos de uso (CA-R4 · M7)."""

    fabrica_sesiones: Callable[[], sessionmaker[Session]]
    configuracion: ConfiguracionIdentidad
    contrasenas: Contrasenas
    reloj: Reloj


def construir_contexto(
    *, proveedor_motor: Callable[[], Engine], reloj: Reloj | None, entorno: Mapping[str, str]
) -> ContextoIdentidad:
    """CA-R4 · D-2. La fábrica de sesiones pide el motor una sola vez, al primer uso."""
    configuracion = ConfiguracionIdentidad.desde_entorno(entorno)

    @functools.cache
    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=proveedor_motor(), expire_on_commit=False)

    return ContextoIdentidad(
        fabrica_sesiones=fabrica,
        configuracion=configuracion,
        contrasenas=ContrasenasArgon2(configuracion),
        reloj=reloj if reloj is not None else reloj_del_sistema,
    )
