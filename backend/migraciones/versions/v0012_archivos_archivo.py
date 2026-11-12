"""TKT-059 · Registro de archivos adjuntos: la tabla `archivo` (invariantes 23 a 26).

Revisión: 0012 · Anterior: 0011

Crea `archivo`, el registro de lo que el almacén de objetos guarda (modelo de datos §12). Las
garantías que el motor sostiene por sí mismo son cuatro: un archivo `DISPONIBLE` tiene hash, tamaño
y fecha de confirmación (invariante 23); uno `ANULADO` tiene autor y motivo (invariante 24); dos
filas no comparten objeto (invariante 25); y todo adjunto señala a un documento, salvo los del
expediente general de la obra (invariante 26). Los dominios de `estado` y `referencia_tipo` son
cerrados. No hay clave foránea sobre `obra_id` ni sobre `referencia_id`: la obra y el documento
viven en módulos que `archivos` no puede importar, y un documento puede ser de cualquiera de seis
tablas.

Privilegios: ningún `GRANT`; la tabla hereda los de `0001` (`SELECT`, `INSERT`, `UPDATE` y `DELETE`
para el rol de aplicación, `SELECT` para el de lectura). Un único `REVOKE` quita `DELETE` al rol de
aplicación, porque un archivo se anula con motivo y nunca se borra. `TRUNCATE` no lo concede ningún
privilegio por omisión. El `UPDATE` se conserva porque `SELECT ... FOR UPDATE` lo exige.

Reversibilidad: sí, mientras la tabla esté vacía. Destructiva: no, porque la bajada se niega con
`P0001` si hay filas, ya que los objetos del almacén perderían su rastro.

Plan de reversa: `alembic downgrade 0011` con el rol de migración deja el catálogo idéntico al de
`0011`. Con filas en `archivo`, respáldalas con `pg_dump` y retíralas fuera de esta migración antes
de bajar.

Cada sentencia va en su propia llamada a `op.execute`, igual que en `0003`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TABLE archivo (
    id               uuid        NOT NULL,
    obra_id          uuid        NOT NULL,
    referencia_tipo  text        NOT NULL,
    referencia_id    uuid,
    estado           text        NOT NULL DEFAULT 'PENDIENTE',
    clave_objeto     text        NOT NULL,
    nombre_original  text        NOT NULL,
    tipo_mime        text,
    tamano_bytes     bigint,
    hash_sha256      char(64),
    subido_por_id    uuid        NOT NULL,
    creado_en        timestamptz NOT NULL DEFAULT now(),
    confirmado_en    timestamptz,
    anulado_por_id   uuid,
    motivo_anulacion text,
    anulado_en       timestamptz,
    CONSTRAINT pk_archivo PRIMARY KEY (id),
    CONSTRAINT fk_archivo_subido_por_id FOREIGN KEY (subido_por_id) REFERENCES usuario (id),
    CONSTRAINT fk_archivo_anulado_por_id FOREIGN KEY (anulado_por_id) REFERENCES usuario (id),
    CONSTRAINT uq_archivo_clave_objeto UNIQUE (clave_objeto),
    CONSTRAINT ck_archivo_referencia_tipo CHECK (
        referencia_tipo IN (
            'AVANCE', 'ENTRADA_ALMACEN', 'MERMA', 'FACTURA_PROVEEDOR', 'IMPORTACION', 'OBRA'
        )
    ),
    CONSTRAINT ck_archivo_estado CHECK (
        estado IN ('PENDIENTE', 'DISPONIBLE', 'CADUCADO', 'ANULADO')
    ),
    CONSTRAINT ck_archivo_disponible_verificado CHECK (
        estado <> 'DISPONIBLE'
        OR (hash_sha256 IS NOT NULL AND tamano_bytes IS NOT NULL AND confirmado_en IS NOT NULL)
    ),
    CONSTRAINT ck_archivo_anulado_con_motivo CHECK (
        estado <> 'ANULADO' OR (anulado_por_id IS NOT NULL AND motivo_anulacion IS NOT NULL)
    ),
    CONSTRAINT ck_archivo_referencia_obligatoria CHECK (
        referencia_tipo = 'OBRA' OR referencia_id IS NOT NULL
    )
)
""",
    "CREATE INDEX ix_archivo_obra_id_estado_creado_en ON archivo (obra_id, estado, creado_en DESC)",
    "CREATE INDEX ix_archivo_referencia_tipo_referencia_id ON archivo (referencia_tipo, referencia_id)",
    "CREATE INDEX ix_archivo_creado_en_pendiente ON archivo (creado_en) WHERE estado = 'PENDIENTE'",
    # PA-T59.10: un archivo se anula con motivo, nunca se borra. TRUNCATE no lo concede ningún
    # privilegio por omisión de 0001.
    "REVOKE DELETE ON archivo FROM cimenta_aplicacion",
)

_GUARDA_BAJADA = """
DO $guarda$
BEGIN
    LOCK TABLE archivo IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM archivo) THEN
        RAISE EXCEPTION USING MESSAGE =
            'La bajada de 0012 se niega: hay filas en archivo, y los objetos del almacén '
            'perderían su rastro. Respáldalas con pg_dump y retíralas fuera de esta migración.';
    END IF;
END
$guarda$
"""

# DROP TABLE se lleva índices, restricciones y privilegios, incluido el REVOKE de la subida.
_BAJADA: tuple[str, ...] = (
    _GUARDA_BAJADA,
    "DROP TABLE archivo",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
