"""Fija las contraseñas de los roles de aplicación y de solo lectura (TKT-003, RNF-07).

La migración crea los roles sin contraseña; este script las fija por entorno, ya cifradas
en SCRAM, y nunca imprime ni registra una contraseña. Se ejecuta desde backend/ con:
uv run --env-file ../.env python -m herramientas.contrasenas_roles
"""

from typing import Any

import psycopg
from psycopg import sql

from herramientas.conexion import ROL_APLICACION, ROL_LECTURA, ROL_MIGRACION, leer_variable


def fijar_contrasenas(conexion: psycopg.Connection[Any], *, aplicacion: str, lectura: str) -> None:
    """Fija por entorno las contraseñas que la migración no pone (RNF-07, decisión del 2026-10-17)."""
    pares = ((ROL_APLICACION, aplicacion), (ROL_LECTURA, lectura))
    for rol, contrasena in pares:
        if not contrasena:
            raise ValueError(f"La contraseña de {rol} está vacía")
    for rol, contrasena in pares:
        cifrada = conexion.pgconn.encrypt_password(
            contrasena.encode(), rol.encode(), b"scram-sha-256"
        ).decode()
        conexion.execute(
            sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                sql.Identifier(rol), sql.Literal(cifrada)
            )
        )


def main() -> int:
    host = leer_variable("CIMENTA_DB_HOST")
    puerto = int(leer_variable("CIMENTA_DB_PUERTO"))
    base = leer_variable("CIMENTA_DB_NOMBRE")
    contrasena_migracion = leer_variable("CIMENTA_DB_CONTRASENA_MIGRACION")
    contrasena_aplicacion = leer_variable("CIMENTA_DB_CONTRASENA_APLICACION")
    contrasena_lectura = leer_variable("CIMENTA_DB_CONTRASENA_LECTURA")
    with psycopg.connect(
        host=host,
        port=puerto,
        dbname=base,
        user=ROL_MIGRACION,
        password=contrasena_migracion,
        autocommit=True,
    ) as conexion:
        fijar_contrasenas(conexion, aplicacion=contrasena_aplicacion, lectura=contrasena_lectura)
    print(f"Contraseñas fijadas para {ROL_APLICACION} y {ROL_LECTURA}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
