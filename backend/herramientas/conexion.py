"""Conexión a PostgreSQL desde el entorno (TKT-003, RNF-07).

Los nombres de rol son constantes, no variables de entorno: no son secretos, y que cambiaran
por entorno rompería la guarda de las migraciones y las pruebas. Las contraseñas y el destino
solo salen del entorno, y nunca hay un valor por omisión.
"""

import os
from typing import Final

from sqlalchemy import URL, Engine, create_engine

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


def url_aplicacion() -> URL:
    """URL del rol de aplicación, igual que url_migracion con su propia contraseña."""
    return URL.create(
        "postgresql+psycopg",
        username=ROL_APLICACION,
        password=leer_variable("CIMENTA_DB_CONTRASENA_APLICACION"),
        host=leer_variable("CIMENTA_DB_HOST"),
        port=int(leer_variable("CIMENTA_DB_PUERTO")),
        database=leer_variable("CIMENTA_DB_NOMBRE"),
    )


def crear_motor_aplicacion() -> Engine:
    """Motor síncrono del rol de aplicación (ADR-013). create_engine no conecta: la primera conexión
    se abre con la primera consulta. Quien lo necesite perezoso lo envuelve en functools.cache."""
    return create_engine(url_aplicacion(), pool_pre_ping=True)
