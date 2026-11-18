"""TKT-012b · El verbo `ELIMINAR` de la bitácora (RN-04, invariante 10).

Revisión: 0017 · Anterior: 0016

La subida añade `ELIMINAR` al final del tipo `accion_bitacora` con `ALTER TYPE ... ADD VALUE`, sin
`IF NOT EXISTS` (un valor ya presente es un defecto que debe fallar) y sin `BEFORE` ni `AFTER`, para
que quede último y el orden del tipo coincida con el de `AccionBitacora` y el del borrador.

Un valor de enumerado añadido no se puede usar en la transacción que lo añade: PostgreSQL responde
`55P04` (`unsafe use of new value`). `env.py` corre todas las migraciones de un `upgrade head` en
una sola transacción, así que ninguna migración posterior a `0017` que se aplique en esa misma
ejecución puede usar `ELIMINAR`. Esta migración no lo usa.

PostgreSQL no permite quitar un valor de un enumerado: la bajada recrea el tipo con los 23 verbos de
`0016`, en su orden. Reescribe físicamente la columna `bitacora.accion` con el rol de migración, sin
cambiar ningún valor ni ningún privilegio de la tabla (el tipo nuevo conserva el `USAGE` por omisión
y `ALTER COLUMN ... TYPE` no toca la ACL de `bitacora`). Antes de nada, la guarda bloquea la tabla y
se niega con `RAISE EXCEPTION` si hay asientos `ELIMINAR`, porque RN-04 declara la bitácora
permanente y la conversión los perdería. Plan de reversa con asientos `ELIMINAR`: respaldar con
`pg_dump` y decidir con la persona dueña antes de cualquier intervención manual. La bajada de `0017`
se ejecuta antes que la de `0016`, por el orden de Alembic.

Cada sentencia va en su propia llamada a op.execute, igual que en 0003 y 0016.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = ("ALTER TYPE accion_bitacora ADD VALUE 'ELIMINAR'",)

# La guarda va primero: con asientos ELIMINAR la bajada se niega antes de tocar el tipo.
_BAJADA: tuple[str, ...] = (
    """
DO $$
BEGIN
    LOCK TABLE bitacora IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM bitacora WHERE accion::text = 'ELIMINAR') THEN
        RAISE EXCEPTION 'La bitácora tiene asientos ELIMINAR y es permanente (RN-04): la bajada de 0017 no puede quitar el verbo. Respáldala antes de bajar.';
    END IF;
END
$$
""",
    "ALTER TYPE accion_bitacora RENAME TO accion_bitacora_0017",
    """
CREATE TYPE accion_bitacora AS ENUM (
    'CREAR', 'ACTUALIZAR', 'EVALUAR', 'BLOQUEAR', 'AUTORIZAR', 'RECHAZAR', 'CANCELAR', 'EMITIR',
    'AJUSTAR', 'REPROGRAMAR', 'CONGELAR', 'RECAPTURAR', 'DESCARTAR', 'CONFIRMAR', 'ANULAR',
    'SUSPENDER', 'REACTIVAR', 'CERRAR', 'DESACTIVAR', 'LIBERAR', 'VALIDAR', 'DENEGAR', 'DAR_BAJA'
)
""",
    "ALTER TABLE bitacora ALTER COLUMN accion TYPE accion_bitacora USING accion::text::accion_bitacora",
    "DROP TYPE accion_bitacora_0017",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
