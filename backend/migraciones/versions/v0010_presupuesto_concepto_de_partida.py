"""TKT-072 · Concepto único por obra y concepto de partida (`partida_concepto`).

Revisión: 0010 · Anterior: 0009

Separa el concepto de obra (código, descripción, unidad) de su aparición en una partida
(cantidad, precio unitario, importe). Renombra `linea_base_concepto.concepto_id` a
`partida_concepto_id` y apunta a `partida_concepto`. Conserva el disparador
`trg_linea_base_concepto_inmutable` y la revocación de `UPDATE`/`DELETE`/`TRUNCATE` sobre
`linea_base_concepto` para el rol de aplicación.

La subida se niega con `P0001` si hay filas en `concepto` o en `linea_base_concepto`
(`PA-T72.8`): toma `LOCK TABLE concepto, linea_base_concepto IN ACCESS EXCLUSIVE MODE` antes
de comprobar. La bajada se niega con `P0001` si hay filas en `partida_concepto` o en
`concepto` (`PA-T72.7`): bloquea `partida_concepto` y `concepto` igual que la subida.

La bajada recrea `concepto` con el texto literal de `0006` (posiciones de columna incluidas),
no con `ADD COLUMN`, porque `DROP COLUMN` deja huecos en `ordinal_position`.

Reversible: sí, solo con `concepto`, `partida_concepto` y `linea_base_concepto` vacías.
Plan de reversa: respaldar con `pg_dump --table=concepto --table=partida_concepto
--table=linea_base_concepto --table=apu` y retirar filas fuera de esta migración si hace falta;
luego `alembic downgrade 0009`.

Privilegios de `partida_concepto`: los de omisión de `0001` (aplicación
`SELECT, INSERT, UPDATE, DELETE`; lectura `SELECT`); sin `GRANT` explícito, como en `0007`.

Cada sentencia va en su propia llamada a `op.execute`, igual que en `0007` y `0009`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GUARDA_SUBIDA = """
DO $guarda$
DECLARE
    con_filas text[] := ARRAY[]::text[];
BEGIN
    LOCK TABLE concepto, linea_base_concepto IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM concepto) THEN
        con_filas := con_filas || 'concepto'::text;
    END IF;
    IF EXISTS (SELECT 1 FROM linea_base_concepto) THEN
        con_filas := con_filas || 'linea_base_concepto'::text;
    END IF;
    IF cardinality(con_filas) > 0 THEN
        RAISE EXCEPTION USING MESSAGE = format(
            'La subida de 0010 se niega: hay filas en %s. TKT-072 separa el concepto de sus apariciones '
            'y no migra datos (PA-T72.8): respalda esas tablas con pg_dump y decide qué hacer con ellas antes de subir.',
            array_to_string(con_filas, ' y '));
    END IF;
END
$guarda$
"""

_GUARDA_BAJADA = """
DO $guarda$
DECLARE
    con_filas text[] := ARRAY[]::text[];
BEGIN
    LOCK TABLE partida_concepto, concepto IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM partida_concepto) THEN
        con_filas := con_filas || 'partida_concepto'::text;
    END IF;
    IF EXISTS (SELECT 1 FROM concepto) THEN
        con_filas := con_filas || 'concepto'::text;
    END IF;
    IF cardinality(con_filas) > 0 THEN
        RAISE EXCEPTION USING MESSAGE = format(
            'La bajada de 0010 se niega: hay filas en %s. El esquema de 0009 no puede guardar un concepto '
            'sin partida ni un concepto de partida (PA-T72.7): respalda esas tablas con pg_dump y retira '
            'las filas fuera de esta migración antes de bajar.',
            array_to_string(con_filas, ' y '));
    END IF;
END
$guarda$
"""

_CREATE_PARTIDA_CONCEPTO = """
CREATE TABLE partida_concepto (
    id              uuid          NOT NULL,
    concepto_id     uuid          NOT NULL,
    partida_id      uuid          NOT NULL,
    cantidad        numeric(14,4) NOT NULL,
    precio_unitario numeric(14,4) NOT NULL,
    importe         numeric(18,4) NOT NULL,
    CONSTRAINT pk_partida_concepto PRIMARY KEY (id),
    CONSTRAINT fk_partida_concepto_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT,
    CONSTRAINT fk_partida_concepto_partida_id FOREIGN KEY (partida_id) REFERENCES partida (id) ON DELETE RESTRICT,
    CONSTRAINT uq_partida_concepto_concepto_id_partida_id UNIQUE (concepto_id, partida_id),
    CONSTRAINT ck_partida_concepto_cantidad_no_negativo CHECK (cantidad >= 0),
    CONSTRAINT ck_partida_concepto_precio_unitario_no_negativo CHECK (precio_unitario >= 0),
    CONSTRAINT ck_partida_concepto_importe_no_negativo CHECK (importe >= 0)
)
"""

_CREATE_CONCEPTO_0006 = """
CREATE TABLE concepto (
    id              uuid          NOT NULL,
    obra_id         uuid          NOT NULL,
    partida_id      uuid          NOT NULL,
    codigo          text          NOT NULL,
    descripcion     text          NOT NULL,
    unidad          text          NOT NULL,
    cantidad        numeric(14,4) NOT NULL,
    precio_unitario numeric(14,4) NOT NULL,
    importe         numeric(18,4) NOT NULL,
    CONSTRAINT pk_concepto PRIMARY KEY (id),
    CONSTRAINT fk_concepto_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_concepto_partida_id FOREIGN KEY (partida_id) REFERENCES partida (id) ON DELETE RESTRICT,
    CONSTRAINT uq_concepto_obra_id_codigo UNIQUE (obra_id, codigo),
    CONSTRAINT ck_concepto_unidad CHECK (unidad IN ('M2', 'ML', 'PZA', 'KG', 'CAJA', 'SACO', 'ROLLO', 'JORNAL')),
    CONSTRAINT ck_concepto_cantidad_no_negativo CHECK (cantidad >= 0),
    CONSTRAINT ck_concepto_precio_unitario_no_negativo CHECK (precio_unitario >= 0),
    CONSTRAINT ck_concepto_importe_no_negativo CHECK (importe >= 0)
)
"""

_SUBIDA: tuple[str, ...] = (
    _GUARDA_SUBIDA,
    "ALTER TABLE linea_base_concepto DROP CONSTRAINT fk_linea_base_concepto_concepto_id",
    "ALTER TABLE linea_base_concepto RENAME COLUMN concepto_id TO partida_concepto_id",
    "DROP INDEX ix_concepto_partida_id",
    "ALTER TABLE concepto DROP CONSTRAINT fk_concepto_partida_id",
    "ALTER TABLE concepto DROP CONSTRAINT ck_concepto_cantidad_no_negativo",
    "ALTER TABLE concepto DROP CONSTRAINT ck_concepto_precio_unitario_no_negativo",
    "ALTER TABLE concepto DROP CONSTRAINT ck_concepto_importe_no_negativo",
    "ALTER TABLE concepto DROP COLUMN partida_id",
    "ALTER TABLE concepto DROP COLUMN cantidad",
    "ALTER TABLE concepto DROP COLUMN precio_unitario",
    "ALTER TABLE concepto DROP COLUMN importe",
    _CREATE_PARTIDA_CONCEPTO,
    "CREATE INDEX ix_partida_concepto_partida_id ON partida_concepto (partida_id)",
    "ALTER TABLE linea_base_concepto ADD CONSTRAINT fk_linea_base_concepto_partida_concepto_id "
    "FOREIGN KEY (partida_concepto_id) REFERENCES partida_concepto (id) ON DELETE RESTRICT",
)

_BAJADA: tuple[str, ...] = (
    _GUARDA_BAJADA,
    "ALTER TABLE linea_base_concepto DROP CONSTRAINT fk_linea_base_concepto_partida_concepto_id",
    "ALTER TABLE linea_base_concepto RENAME COLUMN partida_concepto_id TO concepto_id",
    "DROP TABLE partida_concepto",
    "ALTER TABLE apu DROP CONSTRAINT fk_apu_concepto_id",
    "DROP TABLE concepto",
    _CREATE_CONCEPTO_0006,
    "CREATE INDEX ix_concepto_partida_id ON concepto (partida_id)",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON concepto TO cimenta_aplicacion",
    "ALTER TABLE apu ADD CONSTRAINT fk_apu_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT",
    "ALTER TABLE linea_base_concepto ADD CONSTRAINT fk_linea_base_concepto_concepto_id "
    "FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
