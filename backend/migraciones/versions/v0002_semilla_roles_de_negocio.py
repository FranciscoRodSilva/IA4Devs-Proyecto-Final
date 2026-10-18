"""TKT-003 · Los seis roles de negocio del PRD §4, con identificadores fijos.

Revisión: 0002 · Anterior: 0001

Los identificadores son fijos para que todos los entornos tengan las mismas filas. El código no
los usa como constantes mágicas: un rol se busca siempre por `clave`, nunca por `id`.
Cada sentencia va en su propia llamada a op.execute, igual que en 0001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
INSERT INTO rol (id, clave, nombre) VALUES
    ('c1e0a000-0000-4000-8000-000000000001', 'DIRECCION_GENERAL', 'Dirección General'),
    ('c1e0a000-0000-4000-8000-000000000002', 'DIRECTOR_PROYECTOS', 'Director de Proyectos'),
    ('c1e0a000-0000-4000-8000-000000000003', 'RESIDENTE', 'Residente de obra'),
    ('c1e0a000-0000-4000-8000-000000000004', 'COMPRAS', 'Compras'),
    ('c1e0a000-0000-4000-8000-000000000005', 'ALMACEN', 'Almacén'),
    ('c1e0a000-0000-4000-8000-000000000006', 'ADMINISTRACION', 'Administración')
""",
)

_BAJADA: tuple[str, ...] = (
    "DELETE FROM rol WHERE id IN ('c1e0a000-0000-4000-8000-000000000001', 'c1e0a000-0000-4000-8000-000000000002', 'c1e0a000-0000-4000-8000-000000000003', 'c1e0a000-0000-4000-8000-000000000004', 'c1e0a000-0000-4000-8000-000000000005', 'c1e0a000-0000-4000-8000-000000000006')",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
