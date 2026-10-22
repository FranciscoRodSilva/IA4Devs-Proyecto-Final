"""Fábrica de la aplicación FastAPI: raíz de composición (ADR-018, CA-12, CA-14).

Monta los enrutadores de `cimenta.<modulo>.api` y ningún módulo importa este paquete. Desde TKT-006
solo monta `cimenta.identidad.api.montaje`: nada de `aplicacion/` ni de `infraestructura/` de
ningún módulo. Los manejadores de error se registran con `registrar_manejadores` (TKT-005, fila 6).
El motor del rol de aplicación es perezoso: construir la aplicación no exige variables de base ni
abre conexión.
"""

import functools
import os
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import TextIO

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from cimenta.identidad.api.montaje import montar_identidad
from herramientas.conexion import crear_motor_aplicacion
from servidor.correlacion import MiddlewareCorrelacion
from servidor.manejadores import registrar_manejadores
from servidor.registro import configurar_registro


def crear_aplicacion(
    *,
    destino_registro: TextIO | None = None,
    motor: Engine | None = None,
    reloj: Callable[[], datetime] | None = None,
    entorno: Mapping[str, str] | None = None,
) -> FastAPI:
    """CA-14: depuración desactivada, para que un error nunca devuelva una traza al cliente."""
    configurar_registro(destino_registro if destino_registro is not None else sys.stdout)
    aplicacion = FastAPI(title="CIMENTA", version="0.1.0", debug=False)
    registrar_manejadores(aplicacion)
    aplicacion.add_middleware(MiddlewareCorrelacion)
    montar_identidad(
        aplicacion,
        proveedor_motor=(lambda: motor)
        if motor is not None
        else functools.cache(crear_motor_aplicacion),
        reloj=reloj,
        entorno=os.environ if entorno is None else entorno,
    )
    return aplicacion
