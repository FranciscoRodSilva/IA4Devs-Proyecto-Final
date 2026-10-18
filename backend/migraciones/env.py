"""Entorno de Alembic de CIMENTA (TKT-003).

Solo migra cimenta_migracion: ALTER DEFAULT PRIVILEGES se declara para ese rol,
y una tabla creada por otro nacería sin los permisos de la aplicación.
"""

from alembic import context
from sqlalchemy import Connection, create_engine, pool, text

from herramientas.conexion import ROL_MIGRACION, url_migracion


def _exigir_rol_de_migracion(conexion: Connection) -> None:
    actual = conexion.execute(text("SELECT current_user")).scalar_one()
    if actual != ROL_MIGRACION:
        raise RuntimeError(
            f"Las migraciones de CIMENTA las ejecuta solo {ROL_MIGRACION}, y esta conexión es "
            f"{actual}. Los privilegios por omisión no cubrirían las tablas que cree otro rol."
        )


def _migrar(conexion: Connection) -> None:
    _exigir_rol_de_migracion(conexion)
    context.configure(connection=conexion, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError(
        "CIMENTA no genera SQL sin conexión: las migraciones se aplican contra la base."
    )

_externa = context.config.attributes.get("connection")
if _externa is not None:
    _migrar(_externa)
else:
    _motor = create_engine(url_migracion(), poolclass=pool.NullPool)
    with _motor.connect() as _conexion:
        _migrar(_conexion)
        # La guarda ya abrió la transacción implícita (SQLAlchemy 2.0), así que Alembic
        # no es dueño de ella y no confirma. Esta rama es dueña de su conexión: confirma.
        _conexion.commit()
