"""TKT-003 · Roles de PostgreSQL, privilegios por omisión y esquema de identidad.

Revisión: 0001
Anterior: ninguna

La ejecuta solo cimenta_migracion (lo exige env.py). Los roles son del clúster:
la subida los crea si no existen y la bajada no los elimina (PA-T8).
Cada sentencia va en su propia llamada a op.execute: con parámetros vacíos,
psycopg usa el protocolo extendido, que no admite varias sentencias juntas.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    # §1 · Roles, idempotente porque son del clúster
    """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'cimenta_aplicacion') THEN
        CREATE ROLE cimenta_aplicacion;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'cimenta_lectura') THEN
        CREATE ROLE cimenta_lectura;
    END IF;
END
$$
""",
    "ALTER ROLE cimenta_aplicacion WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
    "ALTER ROLE cimenta_lectura WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
    # §2 · Tiempos máximos, RNF-16 (D-2): en el rol, no en cada conexión
    "ALTER ROLE cimenta_aplicacion SET lock_timeout = '5s'",
    "ALTER ROLE cimenta_aplicacion SET statement_timeout = '15s'",
    "ALTER ROLE cimenta_lectura SET lock_timeout = '5s'",
    "ALTER ROLE cimenta_lectura SET statement_timeout = '60s'",
    # §3 · Esquema
    "GRANT USAGE ON SCHEMA public TO cimenta_aplicacion, cimenta_lectura",
    # §4 · Privilegios por omisión, antes de cualquier tabla
    "ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cimenta_aplicacion",
    "ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public GRANT SELECT ON TABLES TO cimenta_lectura",
    # §5 · Tablas de identidad
    """
CREATE TABLE usuario (
    id                 uuid        NOT NULL,
    nombre             text        NOT NULL,
    email              text        NOT NULL,
    password_hash      text        NOT NULL,
    activo             boolean     NOT NULL DEFAULT true,
    ultimo_acceso      timestamptz,
    bloqueado_hasta    timestamptz,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    creado_por_id      uuid,
    actualizado_en     timestamptz NOT NULL DEFAULT now(),
    actualizado_por_id uuid,
    CONSTRAINT pk_usuario PRIMARY KEY (id),
    CONSTRAINT uq_usuario_email UNIQUE (email),
    CONSTRAINT fk_usuario_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id)
)
""",
    """
CREATE TABLE rol (
    id     uuid NOT NULL,
    clave  text NOT NULL,
    nombre text NOT NULL,
    CONSTRAINT pk_rol PRIMARY KEY (id),
    CONSTRAINT uq_rol_clave UNIQUE (clave)
)
""",
    """
CREATE TABLE usuario_rol (
    id                 uuid        NOT NULL,
    usuario_id         uuid        NOT NULL,
    rol_id             uuid        NOT NULL,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    creado_por_id      uuid,
    actualizado_en     timestamptz NOT NULL DEFAULT now(),
    actualizado_por_id uuid,
    CONSTRAINT pk_usuario_rol PRIMARY KEY (id),
    CONSTRAINT uq_usuario_rol_usuario_id_rol_id UNIQUE (usuario_id, rol_id),
    CONSTRAINT fk_usuario_rol_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_rol_rol_id FOREIGN KEY (rol_id) REFERENCES rol (id),
    CONSTRAINT fk_usuario_rol_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_rol_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id)
)
""",
    """
CREATE TABLE sesion (
    id               uuid        NOT NULL,
    usuario_id       uuid        NOT NULL,
    creada_en        timestamptz NOT NULL DEFAULT now(),
    expira_en        timestamptz NOT NULL,
    ultima_actividad timestamptz NOT NULL DEFAULT now(),
    revocada_en      timestamptz,
    origen_ip        text,
    agente_usuario   text,
    CONSTRAINT pk_sesion PRIMARY KEY (id),
    CONSTRAINT fk_sesion_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id)
)
""",
    """
CREATE TABLE intento_acceso (
    id          uuid        NOT NULL,
    email       text        NOT NULL,
    usuario_id  uuid,
    exitoso     boolean     NOT NULL,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    origen_ip   text,
    CONSTRAINT pk_intento_acceso PRIMARY KEY (id),
    CONSTRAINT fk_intento_acceso_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id)
)
""",
    # §6 · Lo que la tabla no admite, invariante 20
    "REVOKE UPDATE, DELETE ON intento_acceso FROM cimenta_aplicacion",
    # §7 · PA-T4: el rol de lectura no ve la credencial de la cookie ni el hash
    "REVOKE SELECT ON sesion FROM cimenta_lectura",
    "REVOKE SELECT ON usuario FROM cimenta_lectura",
    "GRANT SELECT (id, nombre, email, activo, ultimo_acceso, bloqueado_hasta, creado_en, creado_por_id, actualizado_en, actualizado_por_id) ON usuario TO cimenta_lectura",
)

_BAJADA: tuple[str, ...] = (
    "DROP TABLE intento_acceso",
    "DROP TABLE sesion",
    "DROP TABLE usuario_rol",
    "DROP TABLE rol",
    "DROP TABLE usuario",
    "ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public REVOKE SELECT ON TABLES FROM cimenta_lectura",
    "ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM cimenta_aplicacion",
    "REVOKE USAGE ON SCHEMA public FROM cimenta_aplicacion, cimenta_lectura",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
