"""Configuración de identidad leída del entorno (TKT-006, CA-8 y PA-T2).

Un valor presente que no es un entero positivo en ASCII detiene el arranque (PA-T8).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

_ENTERO_POSITIVO = re.compile(r"[1-9][0-9]{0,8}")

_CADUCIDAD = "CIMENTA_SESION_CADUCIDAD_MINUTOS"
_INACTIVIDAD = "CIMENTA_SESION_INACTIVIDAD_MINUTOS"
_ARGON2_TIEMPO = "CIMENTA_ARGON2_TIEMPO"
_ARGON2_MEMORIA = "CIMENTA_ARGON2_MEMORIA_KIB"
_ARGON2_PARALELISMO = "CIMENTA_ARGON2_PARALELISMO"

_CADUCIDAD_POR_OMISION_MINUTOS = 720
_INACTIVIDAD_POR_OMISION_MINUTOS = 30


def _leer_entero(entorno: Mapping[str, str], nombre: str) -> int | None:
    """Devuelve el entero de la variable, o None si no está. Rechaza cualquier otra forma."""
    if nombre not in entorno:
        return None
    valor = entorno[nombre]
    if _ENTERO_POSITIVO.fullmatch(valor) is None:
        raise ValueError(f"{nombre} debe ser un entero positivo; se recibió {valor!r}")
    return int(valor)


@dataclass(frozen=True, slots=True)
class ConfiguracionIdentidad:
    """CA-8 · PA-T2 · PA-T8. Los costes de Argon2 en None usan el valor por omisión de la biblioteca."""

    caducidad_absoluta: timedelta
    caducidad_inactividad: timedelta
    argon2_tiempo: int | None
    argon2_memoria_kib: int | None
    argon2_paralelismo: int | None

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str]) -> ConfiguracionIdentidad:
        """CA-8 esc. 4 · lee las cinco variables de identidad; las ausentes toman su valor por omisión."""
        caducidad = _leer_entero(entorno, _CADUCIDAD)
        inactividad = _leer_entero(entorno, _INACTIVIDAD)
        return cls(
            caducidad_absoluta=timedelta(
                minutes=_CADUCIDAD_POR_OMISION_MINUTOS if caducidad is None else caducidad
            ),
            caducidad_inactividad=timedelta(
                minutes=_INACTIVIDAD_POR_OMISION_MINUTOS if inactividad is None else inactividad
            ),
            argon2_tiempo=_leer_entero(entorno, _ARGON2_TIEMPO),
            argon2_memoria_kib=_leer_entero(entorno, _ARGON2_MEMORIA),
            argon2_paralelismo=_leer_entero(entorno, _ARGON2_PARALELISMO),
        )
