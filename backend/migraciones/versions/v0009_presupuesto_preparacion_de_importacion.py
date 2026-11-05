"""TKT-015a · Columna `preparacion` en `importacion` y su CHECK de coherencia con el estado.

Revisión: 0009 · Anterior: 0008

Añade `importacion.preparacion` (`jsonb`, anulable) y
`ck_importacion_preparacion_tras_analisis`:
`preparacion IS NULL OR estado NOT IN ('RECIBIDO', 'ANALIZANDO')`.
La subida no toca filas existentes: todas quedan con `preparacion` nula y cumplen el CHECK.

Reversible: sí · destructiva en la bajada (borra la columna y el JSON guardado).
Plan de reversa: antes de bajar, respaldar
`COPY (SELECT id, preparacion FROM importacion WHERE preparacion IS NOT NULL) TO …`
o un `pg_dump --table=importacion`. Una importación `VALIDADO` o `CON_ERRORES` con preparación
no puede reconstruirse solo con el esquema anterior. Sin `GRANT` ni `REVOKE`: la columna hereda
los privilegios de la tabla.

Cada sentencia va en su propia llamada a `op.execute`, igual que en 0004 y 0007.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    "ALTER TABLE importacion ADD COLUMN preparacion jsonb",
    """
ALTER TABLE importacion ADD CONSTRAINT ck_importacion_preparacion_tras_analisis
    CHECK (preparacion IS NULL OR estado NOT IN ('RECIBIDO', 'ANALIZANDO'))
""",
)

_BAJADA: tuple[str, ...] = (
    "ALTER TABLE importacion DROP CONSTRAINT ck_importacion_preparacion_tras_analisis",
    "ALTER TABLE importacion DROP COLUMN preparacion",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
