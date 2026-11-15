"""TKT-029a · Catálogo de proveedores: la tabla `proveedor` (invariantes 8 y 28, `RN-17`).

Revisión: 0013 · Anterior: 0012

Crea `proveedor`, el catálogo de proveedores (modelo de datos §9). Las garantías que el motor
sostiene por sí mismo son cuatro: el RFC es único (invariante 28, `uq_proveedor_rfc`); el estado
pertenece a un dominio cerrado de tres valores (`ck_proveedor_estado`); el tope de consignación, si
existe, no es negativo (invariante 8, `ck_proveedor_tope_consignacion_no_negativo`); y los días de
corte y de pago de la semana caen entre 1 y 7 (`RN-17`, `ck_proveedor_dias_semana_rango`), con 4 y 6
por omisión. El tope es `NUMERIC(18,4)` y es anulable: sin tope, no hay consignación. `creado_por_id`
referencia a `usuario` con `ON DELETE RESTRICT`. No hay más índices que los de la llave primaria y el
RFC único.

Privilegios: el rol de aplicación recibe `SELECT`, `INSERT` y `UPDATE`, y un `REVOKE` le quita
`DELETE` (D-4): un proveedor se desactiva o se da de baja, nunca se borra. El `UPDATE` es el de las
actualizaciones y el que exige `SELECT ... FOR UPDATE`. El rol de lectura recibe `SELECT` por los
privilegios por omisión de `0001`. Nadie recibe `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN`.

Reversibilidad: sí. Destructiva: solo la bajada, que borra la tabla y sus filas. Hoy ninguna tabla
referencia a `proveedor` (la orden de compra lo hará sin clave foránea, modelo de datos §5), así que
la bajada no se niega.

Plan de reversa: `alembic downgrade 0012` con el rol de migración deja el catálogo idéntico al de
`0012`. Si la base ya tiene proveedores, respáldalos con `pg_dump` antes de bajar.

Cada sentencia va en su propia llamada a `op.execute`, igual que en `0006`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TABLE proveedor (
    id                uuid          NOT NULL,
    nombre            text          NOT NULL,
    rfc               text          NOT NULL,
    estado            text          NOT NULL,
    tope_consignacion numeric(18,4),
    dia_corte         smallint      NOT NULL DEFAULT 4,
    dia_pago          smallint      NOT NULL DEFAULT 6,
    creado_en         timestamptz   NOT NULL,
    creado_por_id     uuid          NOT NULL,
    CONSTRAINT pk_proveedor PRIMARY KEY (id),
    CONSTRAINT fk_proveedor_creado_por_id FOREIGN KEY (creado_por_id)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT uq_proveedor_rfc UNIQUE (rfc),
    CONSTRAINT ck_proveedor_estado CHECK (estado IN ('ACTIVO', 'DESACTIVADO', 'BAJA')),
    CONSTRAINT ck_proveedor_tope_consignacion_no_negativo CHECK (tope_consignacion >= 0),
    CONSTRAINT ck_proveedor_dias_semana_rango CHECK (
        dia_corte BETWEEN 1 AND 7 AND dia_pago BETWEEN 1 AND 7
    )
)
""",
    "GRANT SELECT, INSERT, UPDATE ON proveedor TO cimenta_aplicacion",
    # D-4: un proveedor se desactiva o se da de baja, nunca se borra. Los privilegios por omisión
    # de 0001 conceden DELETE a toda tabla nueva.
    "REVOKE DELETE ON proveedor FROM cimenta_aplicacion",
)

# DROP TABLE se lleva restricciones, índices y privilegios, incluidos el GRANT y el REVOKE.
_BAJADA: tuple[str, ...] = ("DROP TABLE proveedor",)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
