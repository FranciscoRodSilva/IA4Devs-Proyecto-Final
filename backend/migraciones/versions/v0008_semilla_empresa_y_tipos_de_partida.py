"""TKT-010 · Semilla de la empresa única y de los cuatro tipos de partida (`M1`, `PA-01`, ADR-008). Revisión: 0008 · Anterior: 0007. Solo datos, sin DDL ni `GRANT`. Identificadores fijos, iguales en todo entorno; el código busca por `clave`. `ON CONFLICT DO NOTHING`: una fila que ya existe se deja intacta (`M5`). Los usuarios y los insumos no van aquí: los siembra `herramientas.semilla_local` (TKT-010b), solo en una base local. Reversible: la bajada borra por identificador y la clave foránea `RESTRICT` la detiene, sin borrar nada, si una obra o una partida usa lo sembrado (`S2`). RFC genérico del SAT (asumido). Cada sentencia va en su propia llamada a op.execute, igual que en 0002."""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
INSERT INTO empresa (id, nombre, rfc, activa) VALUES
    ('c1e0a010-0000-4000-8000-000000000001', 'Constructora Celsius', 'XAXX010101000', true)
ON CONFLICT DO NOTHING
""",
    """
INSERT INTO tipo_partida (id, clave, nombre) VALUES
    ('c1e0a010-0001-4000-8000-000000000001', 'MUROS', 'MUROS'),
    ('c1e0a010-0001-4000-8000-000000000002', 'PLAFONES_Y_CAJILLOS', 'PLAFONES Y CAJILLOS'),
    ('c1e0a010-0001-4000-8000-000000000003', 'ENCHAPES', 'ENCHAPES'),
    ('c1e0a010-0001-4000-8000-000000000004', 'GENERALES', 'GENERALES')
ON CONFLICT DO NOTHING
""",
)

_BAJADA: tuple[str, ...] = (
    "DELETE FROM tipo_partida WHERE id IN ('c1e0a010-0001-4000-8000-000000000001', 'c1e0a010-0001-4000-8000-000000000002', 'c1e0a010-0001-4000-8000-000000000003', 'c1e0a010-0001-4000-8000-000000000004')",
    "DELETE FROM empresa WHERE id = 'c1e0a010-0000-4000-8000-000000000001'",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
