#!/usr/bin/env python3
"""Comprobación de la etiqueta de origen de un pull request (TKT-062a, CA-6).

Todo PR lleva exactamente una etiqueta de origen entre `human`, `human+copilot`, `agent` y `agent+human-review`.
La entrada es la variable de entorno `ETIQUETAS`, con la lista JSON de los nombres de etiqueta del PR. Los datos
del evento llegan por variable de entorno y nunca se interpolan en una orden del flujo de trabajo.

Códigos de salida:
    0  hay exactamente una etiqueta de origen.
    1  no hay ninguna, o hay más de una.
    2  `ETIQUETAS` falta o no es una lista JSON de cadenas (fallo cerrado).

Uso, desde la raíz del repositorio:
    ETIQUETAS='["agent"]' python tools/etiqueta_origen.py
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence

ETIQUETAS_DE_ORIGEN: tuple[str, ...] = ("human", "human+copilot", "agent", "agent+human-review")

_LAS_CUATRO = ", ".join(ETIQUETAS_DE_ORIGEN)
_MENSAJE_ENTRADA_INVALIDA = "::error::ETIQUETAS ausente o inválida"


def evaluar(etiquetas: Sequence[str]) -> tuple[bool, str]:
    """Cuenta las etiquetas que coinciden exactamente con una de origen y devuelve `(aceptado, mensaje)`.

    La coincidencia distingue mayúsculas y espacios. Las etiquetas halladas se listan en el orden de
    `ETIQUETAS_DE_ORIGEN`, no en el de llegada.
    """
    presentes = set(etiquetas)
    halladas = [etiqueta for etiqueta in ETIQUETAS_DE_ORIGEN if etiqueta in presentes]
    if len(halladas) == 1:
        return True, f"Etiqueta de origen: {halladas[0]}."
    if not halladas:
        return False, f"El PR no tiene etiqueta de origen. Añade exactamente una de: {_LAS_CUATRO}."
    return False, (
        f"El PR tiene {len(halladas)} etiquetas de origen ({', '.join(halladas)}); "
        f"debe haber exactamente una de: {_LAS_CUATRO}."
    )


def _leer_etiquetas(texto: str | None) -> list[str] | None:
    """Interpreta `ETIQUETAS`; devuelve `None` si falta o no es una lista JSON de cadenas."""
    if not texto:
        return None
    try:
        valor = json.loads(texto)
    except ValueError:
        return None
    if isinstance(valor, list) and all(isinstance(elemento, str) for elemento in valor):
        return valor
    return None


def main(entorno: Mapping[str, str] | None = None) -> int:
    """Lee `ETIQUETAS` del entorno indicado (o del real si es `None`) e imprime el veredicto."""
    if entorno is None:
        entorno = os.environ
    etiquetas = _leer_etiquetas(entorno.get("ETIQUETAS"))
    if etiquetas is None:
        print(_MENSAJE_ENTRADA_INVALIDA)
        return 2
    aceptado, mensaje = evaluar(etiquetas)
    if aceptado:
        print(mensaje)
        return 0
    print(f"::error::{mensaje}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
