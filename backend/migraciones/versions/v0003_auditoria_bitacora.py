"""TKT-007 · Bitácora transversal de solo-anexado (RN-04, invariante 10).

Revisión: 0003 · Anterior: 0002

Crea el tipo accion_bitacora con los 22 verbos del borrador y la tabla bitacora. La
inmutabilidad es un permiso del motor: al rol de aplicación se le revocan UPDATE, DELETE y
TRUNCATE. La bajada se niega si la bitácora tiene asientos, porque RN-04 la declara permanente.
Cada sentencia va en su propia llamada a op.execute, igual que en 0001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TYPE accion_bitacora AS ENUM (
    'CREAR', 'ACTUALIZAR', 'EVALUAR', 'BLOQUEAR', 'AUTORIZAR', 'RECHAZAR', 'CANCELAR', 'EMITIR',
    'AJUSTAR', 'REPROGRAMAR', 'CONGELAR', 'RECAPTURAR', 'DESCARTAR', 'CONFIRMAR', 'ANULAR',
    'SUSPENDER', 'REACTIVAR', 'CERRAR', 'DESACTIVAR', 'LIBERAR', 'VALIDAR', 'DENEGAR'
)
""",
    """
CREATE TABLE bitacora (
    id            uuid            NOT NULL,
    entidad_tipo  text            NOT NULL,
    entidad_id    uuid            NOT NULL,
    accion        accion_bitacora NOT NULL,
    usuario_id    uuid            NOT NULL,
    ocurrido_en   timestamptz     NOT NULL,
    datos_antes   jsonb,
    datos_despues jsonb,
    motivo        text,
    regla_negocio text,
    obra_id       uuid,
    CONSTRAINT pk_bitacora PRIMARY KEY (id),
    CONSTRAINT fk_bitacora_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT ck_bitacora_regla_negocio_formato CHECK (regla_negocio ~ '^RN-[0-9]{2}$')
)
""",
    "CREATE INDEX ix_bitacora_obra_id_ocurrido_en ON bitacora (obra_id, ocurrido_en DESC)",
    "CREATE INDEX ix_bitacora_regla_negocio ON bitacora (regla_negocio) WHERE regla_negocio IS NOT NULL",
    # Invariante 10. TRUNCATE no lo concede ningún privilegio por omisión; se nombra para que la
    # intención quede escrita y sobreviva a un cambio de v0001. El rol de lectura conserva el
    # SELECT por omisión (PA-T4).
    "REVOKE UPDATE, DELETE, TRUNCATE ON bitacora FROM cimenta_aplicacion",
)

_BAJADA: tuple[str, ...] = (
    """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM bitacora) THEN
        RAISE EXCEPTION 'La bitácora tiene asientos y es permanente (RN-04): la bajada de 0003 no la elimina. Respáldala y vacíala como propietario si de verdad hay que bajar.';
    END IF;
END
$$
""",
    "DROP TABLE bitacora",
    "DROP TYPE accion_bitacora",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
