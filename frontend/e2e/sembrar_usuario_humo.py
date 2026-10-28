"""Siembra el usuario del recorrido de humo de TKT-008 (CA-14) en la base local. Idempotente.

Se ejecuta desde backend/ con PYTHONPATH=. para importar herramientas.conexion. Usa el rol de
migración: es una herramienta de preparación, no una prueba de permisos. El hash es Argon2id de
pwdlib; el backend lo verifica con los parámetros que el propio hash declara.

Se niega a sembrar si el host de la base no es local: el usuario de humo con contraseña conocida
no debe escribirse nunca en una base remota. Comprueba el host antes de conectar.
"""

import os
import uuid

from pwdlib import PasswordHash
from sqlalchemy import create_engine, text

from herramientas.conexion import url_migracion

HOSTS_LOCALES = frozenset({"127.0.0.1", "localhost", "::1"})
# Los mensajes de salida van sin tildes: la consola de Windows no siempre emite UTF-8.
# libpq toma estas variables por encima del host de la URL: con cualquiera definida, la comprobación
# del host no dice a dónde se conecta de verdad.
VARIABLES_QUE_REDIRIGEN = ("PGHOSTADDR", "PGSERVICE")


def main() -> None:
    for variable in VARIABLES_QUE_REDIRIGEN:
        if os.environ.get(variable):
            raise SystemExit(
                f"Negado: {variable} esta definida y libpq la usa en lugar del host de la URL. "
                "Quitala del entorno para sembrar. No se ha conectado."
            )
    host = url_migracion().host
    if host not in HOSTS_LOCALES:
        raise SystemExit(
            f"Negado: CIMENTA_DB_HOST apunta a '{host}', que no es local. "
            "La siembra del humo solo escribe en la base local (127.0.0.1, localhost o ::1). No se ha conectado."
        )
    # El humo de Playwright fija CIMENTA_HUMO_*; la prueba manual toma CIMENTA_PRUEBA_* del `.env`.
    correo = os.environ.get("CIMENTA_HUMO_CORREO") or os.environ["CIMENTA_PRUEBA_CORREO"]
    contrasena = os.environ.get("CIMENTA_HUMO_CONTRASENA") or os.environ["CIMENTA_PRUEBA_CONTRASENA"]
    huella = PasswordHash.recommended().hash(contrasena)
    motor = create_engine(url_migracion())
    try:
        with motor.begin() as conexion:
            rol_id = conexion.execute(
                text("SELECT id FROM rol WHERE clave = 'COMPRAS'")
            ).scalar_one_or_none()
            if rol_id is None:
                raise SystemExit("Falta el rol COMPRAS: aplica `alembic upgrade head`.")
            usuario_id = conexion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash) "
                    "VALUES (:id, 'Humo Compras', :email, :huella) "
                    "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, "
                    "activo = true, bloqueado_hasta = NULL RETURNING id"
                ),
                {"id": uuid.uuid4(), "email": correo, "huella": huella},
            ).scalar_one()
            conexion.execute(
                text("DELETE FROM usuario_rol WHERE usuario_id = :u AND rol_id <> :r"),
                {"u": usuario_id, "r": rol_id},
            )
            conexion.execute(
                text(
                    "INSERT INTO usuario_rol (id, usuario_id, rol_id) "
                    "VALUES (:id, :u, :r) "
                    "ON CONFLICT (usuario_id, rol_id) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "u": usuario_id, "r": rol_id},
            )
    finally:
        motor.dispose()


if __name__ == "__main__":
    main()
