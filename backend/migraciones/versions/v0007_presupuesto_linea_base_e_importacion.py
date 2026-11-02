"""TKT-011b · Línea base, copias congeladas, control, importación y rendimiento observado, con los disparadores del invariante 14 (invariantes 5 y 14, RN-01, PA-T3, PA-T14).

Revisión: 0007 · Anterior: 0006

Crea las siete tablas de TKT-011b: linea_base, linea_base_concepto, explosion_presupuesto, presupuesto_control, importacion, importacion_error y rendimiento_observado; sus restricciones, índices y las dos funciones con sus tres disparadores. Los párrafos siguientes explican cada parte y su fila del diseño.

linea_base no lleva UNIQUE sobre (obra_id, version) ni CHECK de congelado (PA-T3). Solo una línea base
CONGELADA por obra: índice único parcial con WHERE estado = 'CONGELADA', porque un UNIQUE sin WHERE no
admitiría las versiones SUPERSEDIDA. Las claves foráneas son ON DELETE RESTRICT.

El disparador protege estructura, no implementa reglas: rechaza el DELETE de una línea base que no es
BORRADOR y fija las transiciones del estado (BORRADOR a CONGELADA, CONGELADA a SUPERSEDIDA). Una línea
base CONGELADA o SUPERSEDIDA solo puede cambiar su estado; la comparación de la fila sin el estado usa
to_jsonb, así que cubre las columnas que añada una migración futura. No interviene en INSERT, porque
las pruebas de CA-4 insertan líneas base CONGELADA y SUPERSEDIDA directamente. Todos los rechazos llevan
SQLSTATE IN001 y el prefijo RN-01:. La función es SECURITY INVOKER y nombra la tabla con su esquema.

Fila B2: linea_base_concepto y explosion_presupuesto, y presupuesto_proteger_copia_congelada() con sus
disparadores trg_linea_base_concepto_inmutable y trg_explosion_presupuesto_inmutable (invariante 14).
Cada escritura sobre una copia lee la línea base con FOR SHARE y rechaza con IN001 si no es BORRADOR.

Fila B3: presupuesto_control, con su unicidad por (linea_base_id, tipo_partida_id) y sus dos CHECK de
no negatividad. Fila B5: importacion, importacion_error y rendimiento_observado, con sus CHECK con nombre
y los dos índices por clave foránea. Ninguna de estas tablas tiene disparador.

Privilegios: ningún GRANT; las tablas heredan los privilegios por omisión de 0001. Un único REVOKE:
UPDATE, DELETE y TRUNCATE sobre linea_base_concepto para cimenta_aplicacion (invariante 14, doble
barrera con el disparador: aunque alguien desactive el disparador, el rol de aplicación no puede
modificar la copia congelada). TRUNCATE no se concede por omisión, pero se nombra para que la
intención sobreviva a un cambio de 0001. Se conserva el UPDATE sobre explosion_presupuesto,
presupuesto_control y linea_base: el bloqueo pesimista (ADR-004) usa SELECT ... FOR UPDATE, que lo
exige, y el congelado actualiza linea_base. Además, el disparador de copias lee la línea base con
FOR SHARE, que también exige UPDATE sobre linea_base para el rol de aplicación. La inmutabilidad de
explosion_presupuesto y linea_base la garantiza el disparador, no la ausencia de UPDATE.

Fila B6: la bajada empieza con una guarda (RN-01, invariante 14). Si existe alguna línea base que no es
BORRADOR, es decir, CONGELADA o SUPERSEDIDA, la guarda lanza IN001 antes de cualquier DROP y la bajada se
niega. La guarda toma un LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE dentro del mismo bloque DO, antes
de consultar. Así otra sesión no puede congelar una línea base entre la comprobación y el DROP: el
bloqueo espera a que termine cualquier transacción que tenga linea_base abierta y, después, la consulta
ve lo confirmado. env.py ejecuta la cadena de la bajada en una sola transacción, así que el rechazo
deshace todo y no se elimina nada.

Reversible: sí, con una condición. La bajada es la inversa de la subida cuando no hay ninguna línea base
que no sea BORRADOR: elimina las siete tablas y las dos funciones, y deja el esquema como lo dejó 0006
(TC-47 lo prueba). Si hay una línea base CONGELADA o SUPERSEDIDA, la bajada se niega (TC-48) y no borra
nada. Destructiva: sí, solo en la bajada. Borra las filas de las siete tablas, en particular las de las
líneas base BORRADOR y sus copias. La subida no destruye nada. El LOCK TABLE de la guarda evita que otra
sesión congele una línea base entre la comprobación y el borrado, así que la decisión se toma sobre el
estado real.

Plan de reversa. La bajada no se completa mientras exista una línea base CONGELADA o SUPERSEDIDA, y el
procedimiento para retirar una línea base que no es BORRADOR no está definido: lo decide la persona dueña
fuera de esta migración. Antes de cualquier intento, respaldar las siete tablas con pg_dump (linea_base,
linea_base_concepto, explosion_presupuesto, presupuesto_control, importacion, importacion_error y
rendimiento_observado). El disparador trg_linea_base_solo_avanza rechaza el DELETE y el UPDATE de una
línea base que no es BORRADOR, y el de las copias rechaza tocar una copia de una línea base que no es
BORRADOR; por eso el retiro no es un paso de esta migración. Cuando no quede ninguna línea base que no
sea BORRADOR, ejecutar alembic downgrade 0006.
Para volver a subir, alembic upgrade 0007 recrea la estructura vacía. Los datos se restauran desde el
respaldo, con pg_restore, solo si se decide reponerlos.

Cada sentencia va en su propia llamada a op.execute, igual que en 0003 y 0006.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TABLE linea_base (
    id               uuid          NOT NULL,
    obra_id          uuid          NOT NULL,
    version          integer       NOT NULL,
    estado           text          NOT NULL,
    congelada_en     timestamptz,
    congelada_por_id uuid,
    motivo           text,
    importe_venta    numeric(18,4) NOT NULL,
    creado_en        timestamptz   NOT NULL DEFAULT now(),
    creado_por_id    uuid          NOT NULL,
    CONSTRAINT pk_linea_base PRIMARY KEY (id),
    CONSTRAINT fk_linea_base_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_linea_base_congelada_por_id FOREIGN KEY (congelada_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_linea_base_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT ck_linea_base_estado CHECK (estado IN ('BORRADOR', 'CONGELADA', 'SUPERSEDIDA')),
    CONSTRAINT ck_linea_base_importe_venta_no_negativo CHECK (importe_venta >= 0)
)
""",
    "CREATE UNIQUE INDEX uq_linea_base_obra_id_congelada ON linea_base (obra_id) WHERE estado = 'CONGELADA'",
    "CREATE INDEX ix_linea_base_obra_id ON linea_base (obra_id)",
    """
CREATE FUNCTION presupuesto_proteger_linea_base() RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
AS $funcion$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.estado <> 'BORRADOR' THEN
            RAISE EXCEPTION USING
                ERRCODE = 'IN001',
                MESSAGE = format('RN-01: la línea base %s está %s y no se borra', OLD.id, OLD.estado),
                CONSTRAINT = TG_NAME,
                TABLE = TG_TABLE_NAME,
                SCHEMA = TG_TABLE_SCHEMA;
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.estado = 'BORRADOR' THEN
        IF NEW.estado = 'SUPERSEDIDA' THEN
            RAISE EXCEPTION USING
                ERRCODE = 'IN001',
                MESSAGE = format('RN-01: la línea base %s no pasa de BORRADOR a SUPERSEDIDA', OLD.id),
                CONSTRAINT = TG_NAME,
                TABLE = TG_TABLE_NAME,
                SCHEMA = TG_TABLE_SCHEMA;
        END IF;
        RETURN NEW;
    END IF;

    IF (to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado') THEN
        RAISE EXCEPTION USING
            ERRCODE = 'IN001',
            MESSAGE = format('RN-01: la línea base %s está %s; solo su estado puede cambiar', OLD.id, OLD.estado),
            CONSTRAINT = TG_NAME,
            TABLE = TG_TABLE_NAME,
            SCHEMA = TG_TABLE_SCHEMA;
    END IF;

    IF OLD.estado = 'CONGELADA' AND NEW.estado = 'SUPERSEDIDA' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = 'IN001',
        MESSAGE = format('RN-01: la línea base %s no pasa de %s a %s', OLD.id, OLD.estado, NEW.estado),
        CONSTRAINT = TG_NAME,
        TABLE = TG_TABLE_NAME,
        SCHEMA = TG_TABLE_SCHEMA;
END;
$funcion$
""",
    """
CREATE TRIGGER trg_linea_base_solo_avanza
BEFORE UPDATE OR DELETE ON linea_base
FOR EACH ROW EXECUTE FUNCTION presupuesto_proteger_linea_base()
""",
    # Fila B2: copias congeladas (invariante 14).
    """
CREATE TABLE linea_base_concepto (
    id              uuid          NOT NULL,
    linea_base_id   uuid          NOT NULL,
    concepto_id     uuid          NOT NULL,
    codigo          text          NOT NULL,
    cantidad        numeric(14,4) NOT NULL,
    precio_unitario numeric(14,4) NOT NULL,
    importe         numeric(18,4) NOT NULL,
    CONSTRAINT pk_linea_base_concepto PRIMARY KEY (id),
    CONSTRAINT fk_linea_base_concepto_linea_base_id FOREIGN KEY (linea_base_id) REFERENCES linea_base (id) ON DELETE RESTRICT,
    CONSTRAINT fk_linea_base_concepto_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT,
    CONSTRAINT ck_linea_base_concepto_cantidad_no_negativo CHECK (cantidad >= 0),
    CONSTRAINT ck_linea_base_concepto_precio_unitario_no_negativo CHECK (precio_unitario >= 0),
    CONSTRAINT ck_linea_base_concepto_importe_no_negativo CHECK (importe >= 0)
)
""",
    "CREATE INDEX ix_linea_base_concepto_linea_base_id ON linea_base_concepto (linea_base_id)",
    """
CREATE TABLE explosion_presupuesto (
    id                     uuid          NOT NULL,
    linea_base_id          uuid          NOT NULL,
    tipo_partida_id        uuid          NOT NULL,
    insumo_id              uuid          NOT NULL,
    cantidad_presupuestada numeric(14,4) NOT NULL,
    rendimiento_congelado  numeric(18,6) NOT NULL,
    costo_unitario         numeric(14,4) NOT NULL,
    importe_venta          numeric(18,4) NOT NULL,
    CONSTRAINT pk_explosion_presupuesto PRIMARY KEY (id),
    CONSTRAINT fk_explosion_presupuesto_linea_base_id FOREIGN KEY (linea_base_id) REFERENCES linea_base (id) ON DELETE RESTRICT,
    CONSTRAINT fk_explosion_presupuesto_tipo_partida_id FOREIGN KEY (tipo_partida_id) REFERENCES tipo_partida (id) ON DELETE RESTRICT,
    CONSTRAINT fk_explosion_presupuesto_insumo_id FOREIGN KEY (insumo_id) REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT uq_explosion_presupuesto_linea_tipo_insumo UNIQUE (linea_base_id, tipo_partida_id, insumo_id),
    CONSTRAINT ck_explosion_presupuesto_cantidad_presupuestada_no_negativo CHECK (cantidad_presupuestada >= 0),
    CONSTRAINT ck_explosion_presupuesto_rendimiento_congelado_no_negativo CHECK (rendimiento_congelado >= 0),
    CONSTRAINT ck_explosion_presupuesto_costo_unitario_no_negativo CHECK (costo_unitario >= 0),
    CONSTRAINT ck_explosion_presupuesto_importe_venta_no_negativo CHECK (importe_venta >= 0)
)
""",
    """
CREATE FUNCTION presupuesto_proteger_copia_congelada() RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
AS $funcion$
DECLARE
    afectadas uuid[];
    afectada  uuid;
    situacion text;
BEGIN
    IF TG_OP = 'INSERT' THEN
        afectadas := ARRAY[NEW.linea_base_id];
    ELSIF TG_OP = 'DELETE' THEN
        afectadas := ARRAY[OLD.linea_base_id];
    ELSE
        afectadas := ARRAY[OLD.linea_base_id, NEW.linea_base_id];
    END IF;

    FOREACH afectada IN ARRAY afectadas LOOP
        SELECT estado INTO situacion FROM public.linea_base WHERE id = afectada FOR SHARE;
        IF situacion IS NOT NULL AND situacion <> 'BORRADOR' THEN
            RAISE EXCEPTION USING
                ERRCODE = 'IN001',
                MESSAGE = format('RN-01: la línea base %s está %s; %s sobre %s no se admite',
                                 afectada, situacion, TG_OP, TG_TABLE_NAME),
                CONSTRAINT = TG_NAME,
                TABLE = TG_TABLE_NAME,
                SCHEMA = TG_TABLE_SCHEMA;
        END IF;
    END LOOP;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$funcion$
""",
    """
CREATE TRIGGER trg_linea_base_concepto_inmutable
BEFORE INSERT OR UPDATE OR DELETE ON linea_base_concepto
FOR EACH ROW EXECUTE FUNCTION presupuesto_proteger_copia_congelada()
""",
    """
CREATE TRIGGER trg_explosion_presupuesto_inmutable
BEFORE INSERT OR UPDATE OR DELETE ON explosion_presupuesto
FOR EACH ROW EXECUTE FUNCTION presupuesto_proteger_copia_congelada()
""",
    # Fila B3: control presupuestal por línea base y tipo de partida (invariantes 6 y 8).
    """
CREATE TABLE presupuesto_control (
    id                   uuid          NOT NULL,
    linea_base_id        uuid          NOT NULL,
    tipo_partida_id      uuid          NOT NULL,
    importe_tope         numeric(18,4),
    importe_sugerido     numeric(18,4) NOT NULL,
    capturado_por_id     uuid,
    capturado_en         timestamptz,
    actualizado_por_id   uuid,
    actualizado_en       timestamptz,
    motivo_ultimo_cambio text,
    CONSTRAINT pk_presupuesto_control PRIMARY KEY (id),
    CONSTRAINT fk_presupuesto_control_linea_base_id FOREIGN KEY (linea_base_id) REFERENCES linea_base (id) ON DELETE RESTRICT,
    CONSTRAINT fk_presupuesto_control_tipo_partida_id FOREIGN KEY (tipo_partida_id) REFERENCES tipo_partida (id) ON DELETE RESTRICT,
    CONSTRAINT fk_presupuesto_control_capturado_por_id FOREIGN KEY (capturado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_presupuesto_control_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT uq_presupuesto_control_linea_base_id_tipo_partida_id UNIQUE (linea_base_id, tipo_partida_id),
    CONSTRAINT ck_presupuesto_control_importe_tope_no_negativo CHECK (importe_tope >= 0),
    CONSTRAINT ck_presupuesto_control_importe_sugerido_no_negativo CHECK (importe_sugerido >= 0)
)
""",
    # Fila B5: importación y rendimiento observado. `archivo_id` es un identificador lógico, sin
    # clave foránea ni columnas de nombre o URL (CA-7, ADR-016). El rendimiento observado no se une
    # a explosion_presupuesto (CA-10, RN-24).
    """
CREATE TABLE importacion (
    id               uuid        NOT NULL,
    obra_id          uuid        NOT NULL,
    archivo_id       uuid        NOT NULL,
    estado           text        NOT NULL,
    progreso         numeric(9,6),
    filas_leidas     integer,
    filas_validas    integer,
    filas_rechazadas integer,
    resumen          jsonb,
    importado_por_id uuid        NOT NULL,
    creado_en        timestamptz NOT NULL DEFAULT now(),
    latido           timestamptz,
    CONSTRAINT pk_importacion PRIMARY KEY (id),
    CONSTRAINT fk_importacion_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_importacion_importado_por_id FOREIGN KEY (importado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT ck_importacion_estado CHECK (estado IN ('RECIBIDO', 'ANALIZANDO', 'VALIDADO', 'CON_ERRORES', 'CONFIRMADO', 'DESCARTADO')),
    CONSTRAINT ck_importacion_progreso_rango CHECK (progreso >= 0 AND progreso <= 1)
)
""",
    "CREATE INDEX ix_importacion_obra_id ON importacion (obra_id)",
    """
CREATE TABLE importacion_error (
    id             uuid NOT NULL,
    importacion_id uuid NOT NULL,
    hoja           text,
    fila           integer,
    columna        text,
    tipo           text NOT NULL,
    mensaje        text NOT NULL,
    valor_original text,
    CONSTRAINT pk_importacion_error PRIMARY KEY (id),
    CONSTRAINT fk_importacion_error_importacion_id FOREIGN KEY (importacion_id) REFERENCES importacion (id) ON DELETE RESTRICT,
    CONSTRAINT ck_importacion_error_tipo CHECK (tipo IN ('REF_ROTA', 'UNIDAD_DESCONOCIDA', 'SIN_APU', 'RENDIMIENTO_AUSENTE', 'DUPLICADO', 'SIN_CONCEPTOS', 'PROCESO_INTERRUMPIDO'))
)
""",
    "CREATE INDEX ix_importacion_error_importacion_id ON importacion_error (importacion_id)",
    """
CREATE TABLE rendimiento_observado (
    id                    uuid          NOT NULL,
    obra_id               uuid          NOT NULL,
    insumo_id             uuid          NOT NULL,
    consumo_acumulado     numeric(14,4) NOT NULL,
    avance_acumulado      numeric(14,4) NOT NULL,
    rendimiento           numeric(18,6) NOT NULL,
    rendimiento_congelado numeric(18,6) NOT NULL,
    divergencia_pct       numeric(9,6)  NOT NULL,
    muestra               integer       NOT NULL,
    calculado_en          timestamptz   NOT NULL,
    CONSTRAINT pk_rendimiento_observado PRIMARY KEY (id),
    CONSTRAINT fk_rendimiento_observado_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_rendimiento_observado_insumo_id FOREIGN KEY (insumo_id) REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT ck_rendimiento_observado_consumo_acumulado_no_negativo CHECK (consumo_acumulado >= 0),
    CONSTRAINT ck_rendimiento_observado_avance_acumulado_no_negativo CHECK (avance_acumulado >= 0),
    CONSTRAINT ck_rendimiento_observado_rendimiento_no_negativo CHECK (rendimiento >= 0),
    CONSTRAINT ck_rendimiento_observado_rendimiento_congelado_no_negativo CHECK (rendimiento_congelado >= 0)
)
""",
    # Invariante 14, doble barrera: la copia congelada no admite modificación para el rol de aplicación.
    "REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion",
)

# La guarda va la primera: si fuera la última, linea_base ya no existiría. Los disparadores caen con
# sus tablas: primero las que referencian a otras, luego las copias, linea_base y las dos funciones.
# El REVOKE de la subida no se deshace: la tabla linea_base_concepto se elimina y con ella sus privilegios.
_BAJADA: tuple[str, ...] = (
    # Guarda (fila B6, RN-01, invariante 14). El LOCK va dentro del mismo bloque para que la comprobación
    # y los DROP vean la misma tabla.
    """
DO $guarda$
BEGIN
    LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM linea_base WHERE estado <> 'BORRADOR') THEN
        RAISE EXCEPTION USING
            ERRCODE = 'IN001',
            MESSAGE = 'Hay al menos una línea base CONGELADA o SUPERSEDIDA (RN-01, invariante 14): la bajada de 0007 no la elimina. Respáldala con pg_dump; el retiro de una línea base que no es borrador lo decide la persona dueña y se hace fuera de esta migración.';
    END IF;
END
$guarda$
""",
    "DROP TABLE rendimiento_observado",
    "DROP TABLE importacion_error",
    "DROP TABLE importacion",
    "DROP TABLE presupuesto_control",
    "DROP TABLE explosion_presupuesto",
    "DROP TABLE linea_base_concepto",
    "DROP TABLE linea_base",
    "DROP FUNCTION presupuesto_proteger_copia_congelada()",
    "DROP FUNCTION presupuesto_proteger_linea_base()",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
