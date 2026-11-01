"""TKT-057 · Marca de credenciales verificadas en intento_acceso (CA-8, PA-T9, PA-T11).

Revisión: 0005 · Anterior: 0004

Añade intento_acceso.credenciales_verificadas, que distingue un fallo de credenciales (la
contraseña se verificó y falló) de un rechazo por bloqueo o por CSRF (no se verificó nada).
La columna nace con DEFAULT true para que las filas existentes valgan true, que es lo que
eran (TKT-006 siempre verificó), sin reescritura ni UPDATE; el DEFAULT se quita en la misma
migración, de modo que toda inserción posterior la declara. Añade
ck_intento_acceso_exito_verificado (un éxito siempre verificó) y tres índices **parciales**
que sirven a las lecturas del límite: fallos verificados por (email, ocurrido_en), fallos
verificados por (origen_ip, ocurrido_en) y éxitos por (email, ocurrido_en). Son parciales
porque los rechazos por bloqueo (exitoso = false, credenciales_verificadas = false) no cuentan
para el límite y no deben engordar el rango que se recorre al leer: con índices completos, cada
lectura recorrería también el historial adversario (auditoría F001).
No toca el invariante 20: no hay GRANT ni REVOKE nuevos.

Reversible: sí. Destructiva: solo en la bajada, que pierde la distinción entre fallo y
rechazo de las filas escritas desde la subida. Plan de reversa: alembic downgrade 0004.
Cada sentencia va en su propia llamada a op.execute, igual que en 0001, 0003 y 0004.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    "ALTER TABLE intento_acceso ADD COLUMN credenciales_verificadas boolean NOT NULL DEFAULT true",
    "ALTER TABLE intento_acceso ALTER COLUMN credenciales_verificadas DROP DEFAULT",
    "ALTER TABLE intento_acceso ADD CONSTRAINT ck_intento_acceso_exito_verificado "
    "CHECK (credenciales_verificadas OR NOT exitoso)",
    "CREATE INDEX ix_intento_acceso_email_fallo_verificado ON intento_acceso (email, ocurrido_en) "
    "WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE",
    "CREATE INDEX ix_intento_acceso_origen_ip_fallo_verificado ON intento_acceso (origen_ip, ocurrido_en) "
    "WHERE exitoso IS FALSE AND credenciales_verificadas IS TRUE",
    "CREATE INDEX ix_intento_acceso_email_exito ON intento_acceso (email, ocurrido_en) "
    "WHERE exitoso IS TRUE",
)

_BAJADA: tuple[str, ...] = (
    "DROP INDEX ix_intento_acceso_email_exito",
    "DROP INDEX ix_intento_acceso_origen_ip_fallo_verificado",
    "DROP INDEX ix_intento_acceso_email_fallo_verificado",
    "ALTER TABLE intento_acceso DROP CONSTRAINT ck_intento_acceso_exito_verificado",
    "ALTER TABLE intento_acceso DROP COLUMN credenciales_verificadas",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
