"""Límite de intentos de inicio de sesión (RNF-04). Sin RN-xx.

Los instantes son enteros en microsegundos relativos a `ahora`, que vale 0: los fallos pasados son
negativos o cero. El dominio no importa `datetime`; la hora y la conversión las pone `aplicacion/`.
"""

from __future__ import annotations

from dataclasses import dataclass

MICROSEGUNDOS_POR_SEGUNDO = 1_000_000


@dataclass(frozen=True, slots=True)
class EstadoLimite:
    """Bloqueos vigentes de la cuenta y del origen (RNF-04).

    La ventana y el bloqueo miden lo mismo; un rechazo por bloqueo no es un fallo y no llega aquí.
    """

    disparo_cuenta: int | None
    disparo_origen: int | None
    reintentar_en_s: int

    @property
    def bloqueado(self) -> bool:
        return self.reintentar_en_s > 0


def instante_de_disparo(
    fallos: tuple[int, ...] | list[int], *, umbral: int, ventana: int
) -> int | None:
    """Implementa RNF-04: el último fallo que completa `umbral` fallos dentro de la ventana.

    Cuentan los fallos `g` con `f - ventana < g <= f`: el límite inferior es estricto y el
    superior inclusivo. Devuelve el mayor `f` que cumple, o `None`. La ventana y el bloqueo miden
    lo mismo; un rechazo por bloqueo no es un fallo y no llega aquí.
    """
    for candidato in sorted(fallos, reverse=True):
        en_ventana = sum(1 for g in fallos if candidato - ventana < g <= candidato)
        if en_ventana >= umbral:
            return candidato
    return None


def _disparo_vigente(disparo: int | None, ventana: int) -> int | None:
    if disparo is not None and disparo + ventana > 0:
        return disparo
    return None


def _segundos_de_espera(disparos: tuple[int, ...] | list[int], ventana: int) -> int:
    if not disparos:
        return 0
    restante = max(disparos) + ventana
    return -(-restante // MICROSEGUNDOS_POR_SEGUNDO)


def evaluar_limite(
    *,
    fallos_cuenta: tuple[int, ...] | list[int],
    ultimo_exito_cuenta: int | None,
    fallos_origen: tuple[int, ...] | list[int],
    umbral_cuenta: int,
    umbral_origen: int,
    ventana: int,
) -> EstadoLimite:
    """Implementa RNF-04: decide si la cuenta o el origen están bloqueados y por cuánto.

    Solo los fallos de la cuenta posteriores al último éxito cuentan; el origen no se reinicia con
    ningún éxito. Un disparo está vigente si `disparo + ventana > 0`. La ventana y el bloqueo miden
    lo mismo; un rechazo por bloqueo no es un fallo y no llega aquí.
    """
    desde_el_exito = [
        f for f in fallos_cuenta if ultimo_exito_cuenta is None or f > ultimo_exito_cuenta
    ]
    disparo_cuenta = _disparo_vigente(
        instante_de_disparo(desde_el_exito, umbral=umbral_cuenta, ventana=ventana), ventana
    )
    disparo_origen = _disparo_vigente(
        instante_de_disparo(fallos_origen, umbral=umbral_origen, ventana=ventana), ventana
    )
    vigentes = [d for d in (disparo_cuenta, disparo_origen) if d is not None]
    return EstadoLimite(
        disparo_cuenta=disparo_cuenta,
        disparo_origen=disparo_origen,
        reintentar_en_s=_segundos_de_espera(vigentes, ventana),
    )
