"""Conexión a PostgreSQL desde el entorno (TKT-003, RNF-07).

Los nombres de rol son constantes, no variables de entorno: no son secretos, y que cambiaran
por entorno rompería la guarda de las migraciones y las pruebas. Las contraseñas y el destino
solo salen del entorno, y nunca hay un valor por omisión.
"""

import os
from typing import Final

from sqlalchemy import URL

ROL_MIGRACION: Final[str] = "cimenta_migracion"
ROL_APLICACION: Final[str] = "cimenta_aplicacion"
ROL_LECTURA: Final[str] = "cimenta_lectura"


def leer_variable(nombre: str) -> str:
    """Devuelve la variable de entorno `nombre`; si falta o está vacía, falla nombrándola."""
    valor = os.environ.get(nombre, "")
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            "Cópiala de .env.example a .env y ejecuta con: uv run --env-file ../.env …"
        )
    return valor


def url_migracion() -> URL:
    """URL del rol de migración. `URL.create` escapa la contraseña, que va como parte y no en una URL."""
    return URL.create(
        "postgresql+psycopg",
        username=ROL_MIGRACION,
        password=leer_variable("CIMENTA_DB_CONTRASENA_MIGRACION"),
        host=leer_variable("CIMENTA_DB_HOST"),
        port=int(leer_variable("CIMENTA_DB_PUERTO")),
        database=leer_variable("CIMENTA_DB_NOMBRE"),
    )
