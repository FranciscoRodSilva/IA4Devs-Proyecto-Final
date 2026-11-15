"""TKT-019 · Semilla de las dos series de `folio_consecutivo` del módulo `compras` (D-8, D-18). Revisión: 0015 · Anterior: 0014. Solo datos, sin DDL ni `GRANT`, como `0008`: la siembra va en su propia migración, separada del esquema de `0014` (D-8). Las dos filas, `ORDEN_COMPRA` y `REQUISICION`, nacen con `ultimo = 0`; sin ellas el primer alta no tiene contador que bloquear. `ON CONFLICT DO NOTHING`: una fila que ya existe se deja intacta. El formato del folio lo arma el caso de uso (TKT-021), no esta migración. Reversible con una guarda: la bajada se niega con `RAISE EXCEPTION` si algún contador tiene `ultimo > 0` (D-18). La guarda bloquea la tabla antes de consultarla, para que una inserción concurrente no se pierda entre la comprobación y el borrado. Borrar un contador emitido y volver a sembrarlo en cero reutilizaría folios, y `RN-02` prohíbe repetirlos. Mientras todos estén en cero, la bajada borra las dos filas sin pérdida. Plan de reversa si hay folios emitidos: respaldar con `pg_dump` antes de bajar. Cada sentencia va en su propia llamada a op.execute, igual que en 0008 y 0014."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
INSERT INTO folio_consecutivo (serie, ultimo) VALUES
    ('ORDEN_COMPRA', 0),
    ('REQUISICION', 0)
ON CONFLICT DO NOTHING
""",
)

# La guarda va primero: si hay un contador emitido, la bajada se niega antes de borrar nada.
_BAJADA: tuple[str, ...] = (
    """
DO $$
BEGIN
    LOCK TABLE folio_consecutivo IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM folio_consecutivo WHERE ultimo > 0) THEN
        RAISE EXCEPTION 'Ya se emitieron folios: la bajada de 0015 los reiniciaría y se repetirían. Respalda la base antes de bajar.';
    END IF;
END
$$
""",
    "DELETE FROM folio_consecutivo WHERE serie IN ('ORDEN_COMPRA', 'REQUISICION')",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
