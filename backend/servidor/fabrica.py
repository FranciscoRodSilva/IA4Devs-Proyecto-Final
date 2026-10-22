"""Fábrica de la aplicación FastAPI: raíz de composición (ADR-018, CA-12, CA-14).

Los enrutadores de `cimenta.<modulo>.api` se montan aquí desde TKT-006; ningún módulo importa este
paquete. Los manejadores de error se registran con `registrar_manejadores` (TKT-005, fila 6).
"""

import sys
from typing import TextIO

from fastapi import FastAPI

from servidor.correlacion import MiddlewareCorrelacion
from servidor.manejadores import registrar_manejadores
from servidor.registro import configurar_registro


def crear_aplicacion(*, destino_registro: TextIO | None = None) -> FastAPI:
    """CA-14: depuración desactivada, para que un error nunca devuelva una traza al cliente."""
    configurar_registro(destino_registro if destino_registro is not None else sys.stdout)
    aplicacion = FastAPI(title="CIMENTA", version="0.1.0", debug=False)
    registrar_manejadores(aplicacion)
    aplicacion.add_middleware(MiddlewareCorrelacion)
    return aplicacion
