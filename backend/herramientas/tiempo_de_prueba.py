"""Ayudantes de tiempo para pruebas de migración y concurrencia."""

from __future__ import annotations

import time
from collections.abc import Callable


def esperar_hasta(condicion: Callable[[], bool], limite: float = 30.0) -> None:
    """Sondea `condicion` cada 50 ms hasta que se cumple o vence `limite` segundos.

    No decide si la condición debía cumplirse: quien llama afirma después lo que observó.
    """
    vence = time.monotonic() + limite
    while time.monotonic() < vence and not condicion():
        time.sleep(0.05)
