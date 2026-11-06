"""TKT-017a1 · Columnas sin fuente en el Excel (`0011`).

Revisión: 0011 · Anterior: 0010

Cinco columnas que la hoja de análisis puede traer vacías pasan a admitir `NULL` hasta que la
fase 2 capture `area.tipo_unidad` y el lector exija cabecera completa (`PA-T17.11`):
`area.tipo_unidad`, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y
`apu_cargo.base_calculo`.

La bajada se niega con `P0001` si hay `NULL` en alguna (`CA-A11` esc. 2): toma
`LOCK TABLE area, apu, apu_cargo IN ACCESS EXCLUSIVE MODE` antes de comprobar.

Cada sentencia va en su propia llamada a `op.execute`, igual que en `0007`, `0009` y `0010`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GUARDA_BAJADA = """
DO $guarda$
DECLARE
    con_nulos text[] := ARRAY[]::text[];
BEGIN
    LOCK TABLE area, apu, apu_cargo IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM area WHERE tipo_unidad IS NULL) THEN con_nulos := con_nulos || 'area.tipo_unidad'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu WHERE fecha_analisis IS NULL) THEN con_nulos := con_nulos || 'apu.fecha_analisis'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu WHERE analista IS NULL) THEN con_nulos := con_nulos || 'apu.analista'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu_cargo WHERE porcentaje IS NULL) THEN con_nulos := con_nulos || 'apu_cargo.porcentaje'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu_cargo WHERE base_calculo IS NULL) THEN con_nulos := con_nulos || 'apu_cargo.base_calculo'::text; END IF;
    IF cardinality(con_nulos) > 0 THEN
        RAISE EXCEPTION USING MESSAGE = format(
            'La bajada de 0011 se niega: hay nulos en %s. El esquema de 0010 no los admite: '
            'rellena o retira esas filas fuera de esta migración, previo respaldo con pg_dump.',
            array_to_string(con_nulos, ', '));
    END IF;
END
$guarda$
"""


def upgrade() -> None:
    op.execute("ALTER TABLE area ALTER COLUMN tipo_unidad DROP NOT NULL")
    op.execute("ALTER TABLE apu ALTER COLUMN fecha_analisis DROP NOT NULL")
    op.execute("ALTER TABLE apu ALTER COLUMN analista DROP NOT NULL")
    op.execute("ALTER TABLE apu_cargo ALTER COLUMN porcentaje DROP NOT NULL")
    op.execute("ALTER TABLE apu_cargo ALTER COLUMN base_calculo DROP NOT NULL")


def downgrade() -> None:
    op.execute(_GUARDA_BAJADA)
    op.execute("ALTER TABLE area ALTER COLUMN tipo_unidad SET NOT NULL")
    op.execute("ALTER TABLE apu ALTER COLUMN fecha_analisis SET NOT NULL")
    op.execute("ALTER TABLE apu ALTER COLUMN analista SET NOT NULL")
    op.execute("ALTER TABLE apu_cargo ALTER COLUMN porcentaje SET NOT NULL")
    op.execute("ALTER TABLE apu_cargo ALTER COLUMN base_calculo SET NOT NULL")
