"""Ayudantes de tiempo para pruebas de migración y concurrencia."""

from __future__ import annotations

import time
from collections.abc import Callable


def esperar_hasta(condicion: Callable[[], bool], limite: float = 30.0) -> bool:
    """Sondea `condicion` cada 50 ms hasta que se cumple o vence `limite` segundos.

    Devuelve si se cumplió dentro del límite. No decide si la condición debía cumplirse: quien llama
    afirma después lo que observó.
    """
    vence = time.monotonic() + limite
    while True:
        if condicion():
            return True
        if time.monotonic() >= vence:
            return False
        time.sleep(0.05)
