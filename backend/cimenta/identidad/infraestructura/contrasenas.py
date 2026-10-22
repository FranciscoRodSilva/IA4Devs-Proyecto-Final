"""Contraseñas con Argon2id mediante pwdlib (TKT-006, CA-15 y CA-3).

El adaptador no importa la configuración de la aplicación: pide solo los tres costes por
propiedad, para respetar la capa de `infraestructura` (que no importa `aplicacion`).
"""

from __future__ import annotations

import secrets
from typing import Protocol, TypedDict

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher


class _CostesDeclarados(TypedDict, total=False):
    """Solo los costes fijados; los que faltan los pone la biblioteca."""

    time_cost: int
    memory_cost: int
    parallelism: int


class CostesArgon2(Protocol):
    """Los tres costes que el adaptador acepta. `ConfiguracionIdentidad` los cumple."""

    @property
    def argon2_tiempo(self) -> int | None: ...

    @property
    def argon2_memoria_kib(self) -> int | None: ...

    @property
    def argon2_paralelismo(self) -> int | None: ...


class ContrasenasArgon2:
    """CA-15 esc. 1 · CA-3 esc. 3. Deriva y verifica con Argon2id; el hash de descarte usa el mismo
    `PasswordHash` y los mismos costes, para que un correo inexistente cueste lo mismo que uno real."""

    def __init__(self, configuracion: CostesArgon2) -> None:
        costes: _CostesDeclarados = {}
        if configuracion.argon2_tiempo is not None:
            costes["time_cost"] = configuracion.argon2_tiempo
        if configuracion.argon2_memoria_kib is not None:
            costes["memory_cost"] = configuracion.argon2_memoria_kib
        if configuracion.argon2_paralelismo is not None:
            costes["parallelism"] = configuracion.argon2_paralelismo
        self._hash = PasswordHash((Argon2Hasher(**costes),))
        self.hash_de_descarte: str = self._hash.hash(secrets.token_urlsafe(32))

    def derivar(self, contrasena: str) -> str:
        """Devuelve el hash Argon2id de la contraseña, con sal propia."""
        return self._hash.hash(contrasena)

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        """Verdadero solo si la contraseña corresponde al hash guardado.

        Un hash guardado que no es Argon2 (formato desconocido) no verifica: devuelve falso."""
        try:
            return self._hash.verify(contrasena, hash_guardado)
        except UnknownHashError:
            return False
