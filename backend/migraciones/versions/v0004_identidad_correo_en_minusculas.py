"""TKT-006 · Correo en minúsculas por restricción de la base (CA-17, S2, PA-T10).

Revisión: 0004 · Anterior: 0003

Añade ck_usuario_email_minusculas: la base rechaza un correo con mayúsculas aunque el código
lo omita. La subida no normaliza filas existentes: si las hubiera con mayúsculas, PostgreSQL
rechaza la restricción y la migración falla, y el caso se escala (no se reescribe en silencio).
La bajada quita la restricción y no toca datos. Cada sentencia va en su propia llamada a
op.execute, igual que en 0001 y 0003.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    "ALTER TABLE usuario ADD CONSTRAINT ck_usuario_email_minusculas CHECK (email = lower(email))",
)

_BAJADA: tuple[str, ...] = ("ALTER TABLE usuario DROP CONSTRAINT ck_usuario_email_minusculas",)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
