"""Configuración de identidad leída del entorno (TKT-006, CA-8 y PA-T2; TKT-057, S2 y RNF-04).

Un valor presente que no es un entero positivo en ASCII detiene el arranque (PA-T8).
Los límites de intentos de inicio de sesión (RNF-04) se leen igual. La ventana y el bloqueo
miden lo mismo: `CIMENTA_LIMITE_MINUTOS` es una sola variable que fija las dos cosas.
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
_LIMITE_CUENTA = "CIMENTA_LIMITE_FALLOS_CUENTA"
_LIMITE_ORIGEN = "CIMENTA_LIMITE_FALLOS_ORIGEN"
_LIMITE_VENTANA = "CIMENTA_LIMITE_MINUTOS"

_CADUCIDAD_POR_OMISION_MINUTOS = 720
_INACTIVIDAD_POR_OMISION_MINUTOS = 30
_LIMITE_CUENTA_POR_OMISION = 5
_LIMITE_ORIGEN_POR_OMISION = 20
_LIMITE_VENTANA_POR_OMISION_MINUTOS = 15


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
    """CA-8 · PA-T2 · PA-T8 · RNF-04 · TKT-057 S2. Los costes de Argon2 en None usan el valor por omisión de la biblioteca.

    `limite_ventana` es la ventana de conteo de fallos y, a la vez, la duración del bloqueo: la ventana
    y el bloqueo miden lo mismo, y `CIMENTA_LIMITE_MINUTOS` las fija juntas.
    """

    caducidad_absoluta: timedelta
    caducidad_inactividad: timedelta
    argon2_tiempo: int | None
    argon2_memoria_kib: int | None
    argon2_paralelismo: int | None
    limite_fallos_cuenta: int
    limite_fallos_origen: int
    limite_ventana: timedelta

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str]) -> ConfiguracionIdentidad:
        """CA-8 esc. 4 · RNF-04 · TKT-057 S2 · lee las variables de identidad y de límites; las ausentes toman su valor por omisión."""
        caducidad = _leer_entero(entorno, _CADUCIDAD)
        inactividad = _leer_entero(entorno, _INACTIVIDAD)
        cuenta = _leer_entero(entorno, _LIMITE_CUENTA)
        origen = _leer_entero(entorno, _LIMITE_ORIGEN)
        ventana = _leer_entero(entorno, _LIMITE_VENTANA)
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
            limite_fallos_cuenta=_LIMITE_CUENTA_POR_OMISION if cuenta is None else cuenta,
            limite_fallos_origen=_LIMITE_ORIGEN_POR_OMISION if origen is None else origen,
            limite_ventana=timedelta(
                minutes=_LIMITE_VENTANA_POR_OMISION_MINUTOS if ventana is None else ventana
            ),
        )
