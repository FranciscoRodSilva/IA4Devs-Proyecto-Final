"""TKT-019 · Esquema del módulo compras: siete tablas, restricciones nombradas e índices.

Revisión: 0014 · Anterior: 0013

Crea las siete tablas de `compras` (modelo de datos §5): `requisicion`, `requisicion_renglon`,
`orden_compra`, `orden_compra_renglon`, `solicitud_autorizacion`, `reprogramacion_entrega` y
`folio_consecutivo`. Todo lo que el modelo declara como invariante lo sostiene el motor con
`NOT NULL` y `CHECK` con nombre, no el código de aplicación.

Garantías: toda requisición y toda orden llevan `obra_id`, y la requisición además
`tipo_partida_id`, ambos `NOT NULL` (invariante 1, `RN-02`). Los importes, precios y cantidades no
son negativos (invariante 8); `importe_disponible` y `cantidad_disponible` quedan exentos porque
son la cifra del momento de evaluar y pueden ser negativos tras una excepción autorizada (`RN-03`).
La cantidad recibida de un renglón de orden no excede lo ordenado más el excedente autorizado
(invariante 2, `RN-07`). Una solicitud de autorización resuelta lleva motivo, resolutor e instante
(invariante 9, D-11, `RN-04`); un excedente de lo ordenado exige renglón y cantidad, y cualquier
otro motivo ninguno (`RN-07`, `PA-16`). La cancelación de una orden o de una requisición exige
motivo (D-1, D-16), y una requisición fuera de `BORRADOR` tiene folio (D-15). A lo sumo existe una
orden viva por requisición (D-5, índice único parcial). `fecha_compromiso` del renglón no es
nula (D-6) y cada aplazamiento queda como fila de `reprogramacion_entrega` (`RN-06`). Las claves
foráneas son `ON DELETE RESTRICT` (D-4). `orden_compra.proveedor_id` y
`solicitud_autorizacion.entidad_id` no llevan clave foránea (D-2, modelo de datos §2).

Índices (D-5, D-7): uno único parcial por requisición viva, el compuesto
`(obra_id, tipo_partida_id, estado)` que usa el control presupuestal, y uno por cada clave foránea
por la que se lee de padre a hijo.

Disparadores (D-3): una requisición y sus renglones solo se eliminan en `BORRADOR`; en otro
estado el motor responde `SQLSTATE` `IN002`, distinto del `IN001` de la línea base. Son dos
funciones `SECURITY INVOKER`, una por tabla; la del renglón lee el estado con `FOR SHARE`, que
espera a quien esté cambiándolo. `TRUNCATE` no dispara disparadores de fila: lo impide que nadie
lo reciba.

Privilegios (D-17): el rol de aplicación recibe `SELECT, INSERT, UPDATE, DELETE` sobre
`requisicion` y `requisicion_renglon`; `SELECT, INSERT, UPDATE` sobre `solicitud_autorizacion`,
`orden_compra` y `orden_compra_renglon`; `SELECT, INSERT` sobre `reprogramacion_entrega`; y
`SELECT, UPDATE` sobre `folio_consecutivo`. Nadie recibe `TRUNCATE`, `REFERENCES` ni `TRIGGER`. El
rol de lectura conserva solo `SELECT` por los privilegios por omisión de `0001`.

Reversibilidad: sí. Destructiva: solo la bajada, que borra las tablas, sus filas y las dos funciones. La bajada se
niega si hay solicitudes de autorización, porque `RN-04` las declara permanentes (D-18). La guarda bloquea la tabla antes de consultarla, para que una inserción concurrente no se pierda entre la comprobación y el borrado.

Plan de reversa: respaldar con `pg_dump` y ejecutar `alembic downgrade 0013` con el rol de
migración. Para bajar con solicitudes hay que respaldarlas y vaciarlas antes, como propietario.

Cada sentencia va en su propia llamada a `op.execute`, igual que en `0013`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TABLE requisicion (
    id                 uuid          NOT NULL,
    folio              text,
    obra_id            uuid          NOT NULL,
    tipo_partida_id    uuid          NOT NULL,
    solicitante_id     uuid          NOT NULL,
    estado             text          NOT NULL,
    regla_bloqueo      text,
    importe_solicitado numeric(18,4) NOT NULL,
    importe_disponible numeric(18,4),
    importe_excedente  numeric(18,4),
    evaluada_en        timestamptz,
    motivo_cancelacion text,
    observaciones      text,
    creado_en          timestamptz   NOT NULL,
    actualizado_en     timestamptz   NOT NULL,
    CONSTRAINT pk_requisicion PRIMARY KEY (id),
    CONSTRAINT fk_requisicion_obra_id FOREIGN KEY (obra_id)
        REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_requisicion_tipo_partida_id FOREIGN KEY (tipo_partida_id)
        REFERENCES tipo_partida (id) ON DELETE RESTRICT,
    CONSTRAINT fk_requisicion_solicitante_id FOREIGN KEY (solicitante_id)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT uq_requisicion_folio UNIQUE (folio),
    CONSTRAINT ck_requisicion_estado CHECK (estado IN (
        'BORRADOR', 'EVALUADA', 'BLOQUEADA', 'AUTORIZADA', 'RECHAZADA', 'CANCELADA', 'CONVERTIDA'
    )),
    CONSTRAINT ck_requisicion_regla_bloqueo CHECK (regla_bloqueo IN ('RN-03')),
    CONSTRAINT ck_requisicion_importe_solicitado_no_negativo CHECK (importe_solicitado >= 0),
    CONSTRAINT ck_requisicion_importe_excedente_no_negativo CHECK (importe_excedente >= 0),
    CONSTRAINT ck_requisicion_folio_fuera_de_borrador CHECK (estado = 'BORRADOR' OR folio IS NOT NULL),
    CONSTRAINT ck_requisicion_cancelacion_con_motivo CHECK (
        estado <> 'CANCELADA' OR motivo_cancelacion IS NOT NULL
    )
)
""",
    """
CREATE TABLE requisicion_renglon (
    id                      uuid          NOT NULL,
    requisicion_id          uuid          NOT NULL,
    insumo_id               uuid          NOT NULL,
    cantidad                numeric(14,4) NOT NULL,
    costo_unitario_estimado numeric(14,4) NOT NULL,
    importe                 numeric(18,4) NOT NULL,
    cantidad_disponible     numeric(14,4),
    CONSTRAINT pk_requisicion_renglon PRIMARY KEY (id),
    CONSTRAINT fk_requisicion_renglon_requisicion_id FOREIGN KEY (requisicion_id)
        REFERENCES requisicion (id) ON DELETE RESTRICT,
    CONSTRAINT fk_requisicion_renglon_insumo_id FOREIGN KEY (insumo_id)
        REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT ck_requisicion_renglon_cantidad_no_negativo CHECK (cantidad >= 0),
    CONSTRAINT ck_requisicion_renglon_costo_unitario_estimado_no_negativo CHECK (costo_unitario_estimado >= 0),
    CONSTRAINT ck_requisicion_renglon_importe_no_negativo CHECK (importe >= 0)
)
""",
    """
CREATE TABLE orden_compra (
    id                 uuid          NOT NULL,
    folio              text          NOT NULL,
    requisicion_id     uuid          NOT NULL,
    obra_id            uuid          NOT NULL,
    proveedor_id       uuid          NOT NULL,
    importe            numeric(18,4) NOT NULL,
    cancelada_en       timestamptz,
    motivo_cancelacion text,
    creado_en          timestamptz   NOT NULL,
    CONSTRAINT pk_orden_compra PRIMARY KEY (id),
    CONSTRAINT fk_orden_compra_requisicion_id FOREIGN KEY (requisicion_id)
        REFERENCES requisicion (id) ON DELETE RESTRICT,
    CONSTRAINT fk_orden_compra_obra_id FOREIGN KEY (obra_id)
        REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT uq_orden_compra_folio UNIQUE (folio),
    CONSTRAINT ck_orden_compra_importe_no_negativo CHECK (importe >= 0),
    CONSTRAINT ck_orden_compra_cancelacion_con_motivo CHECK (
        (cancelada_en IS NULL) = (motivo_cancelacion IS NULL)
    )
)
""",
    """
CREATE TABLE orden_compra_renglon (
    id                            uuid          NOT NULL,
    orden_compra_id               uuid          NOT NULL,
    insumo_id                     uuid          NOT NULL,
    cantidad_ordenada             numeric(14,4) NOT NULL,
    cantidad_recibida             numeric(14,4) NOT NULL DEFAULT 0,
    cantidad_excedente_autorizada numeric(14,4) NOT NULL DEFAULT 0,
    fecha_compromiso              date          NOT NULL,
    costo_unitario                numeric(14,4) NOT NULL,
    importe                       numeric(18,4) NOT NULL,
    CONSTRAINT pk_orden_compra_renglon PRIMARY KEY (id),
    CONSTRAINT fk_orden_compra_renglon_orden_compra_id FOREIGN KEY (orden_compra_id)
        REFERENCES orden_compra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_orden_compra_renglon_insumo_id FOREIGN KEY (insumo_id)
        REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT ck_orden_compra_renglon_cantidad_ordenada_no_negativo CHECK (cantidad_ordenada >= 0),
    CONSTRAINT ck_orden_compra_renglon_cantidad_recibida_no_negativo CHECK (cantidad_recibida >= 0),
    CONSTRAINT ck_orden_compra_renglon_excedente_autorizado_no_negativo CHECK (cantidad_excedente_autorizada >= 0),
    CONSTRAINT ck_orden_compra_renglon_costo_unitario_no_negativo CHECK (costo_unitario >= 0),
    CONSTRAINT ck_orden_compra_renglon_importe_no_negativo CHECK (importe >= 0),
    CONSTRAINT ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado CHECK (
        cantidad_recibida <= cantidad_ordenada + cantidad_excedente_autorizada
    )
)
""",
    """
CREATE TABLE solicitud_autorizacion (
    id                      uuid          NOT NULL,
    motivo                  text          NOT NULL,
    entidad_tipo            text          NOT NULL,
    entidad_id              uuid          NOT NULL,
    obra_id                 uuid          NOT NULL,
    regla_negocio           text          NOT NULL,
    orden_compra_renglon_id uuid,
    cantidad_excedente      numeric(14,4),
    solicitante_id          uuid          NOT NULL,
    rol_autorizador         text          NOT NULL,
    estado                  text          NOT NULL,
    resuelta_por_id         uuid,
    resuelta_en             timestamptz,
    motivo_resolucion       text,
    contexto                jsonb         NOT NULL,
    creado_en               timestamptz   NOT NULL,
    CONSTRAINT pk_solicitud_autorizacion PRIMARY KEY (id),
    CONSTRAINT fk_solicitud_autorizacion_obra_id FOREIGN KEY (obra_id)
        REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT fk_solicitud_autorizacion_orden_compra_renglon_id FOREIGN KEY (orden_compra_renglon_id)
        REFERENCES orden_compra_renglon (id) ON DELETE RESTRICT,
    CONSTRAINT fk_solicitud_autorizacion_solicitante_id FOREIGN KEY (solicitante_id)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_solicitud_autorizacion_rol_autorizador FOREIGN KEY (rol_autorizador)
        REFERENCES rol (clave) ON DELETE RESTRICT,
    CONSTRAINT fk_solicitud_autorizacion_resuelta_por_id FOREIGN KEY (resuelta_por_id)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT ck_solicitud_autorizacion_motivo CHECK (motivo IN (
        'EXCEDE_PRESUPUESTO', 'EXCEDE_ORDENADO', 'EXCEDE_CONSIGNACION', 'TRABAJO_EXTRA'
    )),
    CONSTRAINT ck_solicitud_autorizacion_entidad_tipo CHECK (entidad_tipo IN ('REQUISICION', 'ORDEN_COMPRA')),
    CONSTRAINT ck_solicitud_autorizacion_estado CHECK (estado IN ('PENDIENTE', 'AUTORIZADA', 'RECHAZADA')),
    CONSTRAINT ck_solicitud_autorizacion_regla_negocio_formato CHECK (regla_negocio ~ '^RN-[0-9]{2}$'),
    CONSTRAINT ck_solicitud_autorizacion_cantidad_excedente_positiva CHECK (cantidad_excedente > 0),
    CONSTRAINT ck_solicitud_autorizacion_excede_ordenado_con_renglon CHECK (
        (motivo = 'EXCEDE_ORDENADO'
            AND orden_compra_renglon_id IS NOT NULL AND cantidad_excedente IS NOT NULL)
        OR (motivo <> 'EXCEDE_ORDENADO'
            AND orden_compra_renglon_id IS NULL AND cantidad_excedente IS NULL)
    ),
    CONSTRAINT ck_solicitud_autorizacion_resolucion_completa CHECK (
        estado = 'PENDIENTE'
        OR (motivo_resolucion IS NOT NULL AND resuelta_por_id IS NOT NULL AND resuelta_en IS NOT NULL)
    )
)
""",
    """
CREATE TABLE reprogramacion_entrega (
    id                      uuid          NOT NULL,
    orden_compra_renglon_id uuid          NOT NULL,
    fecha_anterior          date          NOT NULL,
    fecha_nueva             date          NOT NULL,
    saldo_pendiente         numeric(14,4) NOT NULL,
    motivo                  text          NOT NULL,
    registrado_por_id       uuid          NOT NULL,
    ocurrido_en             timestamptz   NOT NULL,
    CONSTRAINT pk_reprogramacion_entrega PRIMARY KEY (id),
    CONSTRAINT fk_reprogramacion_entrega_orden_compra_renglon_id FOREIGN KEY (orden_compra_renglon_id)
        REFERENCES orden_compra_renglon (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reprogramacion_entrega_registrado_por_id FOREIGN KEY (registrado_por_id)
        REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT ck_reprogramacion_entrega_saldo_pendiente_no_negativo CHECK (saldo_pendiente >= 0),
    CONSTRAINT ck_reprogramacion_entrega_motivo_no_vacio CHECK (btrim(motivo) <> '')
)
""",
    """
CREATE TABLE folio_consecutivo (
    serie  text   NOT NULL,
    ultimo bigint NOT NULL DEFAULT 0,
    CONSTRAINT pk_folio_consecutivo PRIMARY KEY (serie),
    CONSTRAINT ck_folio_consecutivo_serie CHECK (serie IN ('REQUISICION', 'ORDEN_COMPRA')),
    CONSTRAINT ck_folio_consecutivo_ultimo_no_negativo CHECK (ultimo >= 0)
)
""",
    "CREATE UNIQUE INDEX uq_orden_compra_requisicion_id_vigente "
    "ON orden_compra (requisicion_id) WHERE cancelada_en IS NULL",
    "CREATE INDEX ix_requisicion_obra_id_tipo_partida_id_estado "
    "ON requisicion (obra_id, tipo_partida_id, estado)",
    "CREATE INDEX ix_requisicion_renglon_requisicion_id ON requisicion_renglon (requisicion_id)",
    "CREATE INDEX ix_orden_compra_obra_id ON orden_compra (obra_id)",
    "CREATE INDEX ix_orden_compra_renglon_orden_compra_id ON orden_compra_renglon (orden_compra_id)",
    "CREATE INDEX ix_solicitud_autorizacion_entidad_tipo_entidad_id "
    "ON solicitud_autorizacion (entidad_tipo, entidad_id)",
    "CREATE INDEX ix_reprogramacion_entrega_orden_compra_renglon_id "
    "ON reprogramacion_entrega (orden_compra_renglon_id)",
    """
CREATE FUNCTION compras_proteger_borrado_de_requisicion() RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
AS $funcion$
BEGIN
    IF OLD.estado <> 'BORRADOR' THEN
        RAISE EXCEPTION USING
            ERRCODE = 'IN002',
            MESSAGE = format('compras: la requisición %s está %s; solo se elimina en BORRADOR',
                             OLD.id, OLD.estado),
            CONSTRAINT = TG_NAME,
            TABLE = TG_TABLE_NAME,
            SCHEMA = TG_TABLE_SCHEMA;
    END IF;
    RETURN OLD;
END;
$funcion$
""",
    """
CREATE TRIGGER trg_requisicion_borrado_solo_borrador
BEFORE DELETE ON requisicion
FOR EACH ROW EXECUTE FUNCTION compras_proteger_borrado_de_requisicion()
""",
    """
CREATE FUNCTION compras_proteger_borrado_de_renglon() RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
AS $funcion$
DECLARE
    situacion text;
BEGIN
    SELECT estado INTO situacion FROM public.requisicion WHERE id = OLD.requisicion_id FOR SHARE;
    IF situacion IS NOT NULL AND situacion <> 'BORRADOR' THEN
        RAISE EXCEPTION USING
            ERRCODE = 'IN002',
            MESSAGE = format('compras: la requisición %s está %s; sus renglones solo se eliminan en BORRADOR',
                             OLD.requisicion_id, situacion),
            CONSTRAINT = TG_NAME,
            TABLE = TG_TABLE_NAME,
            SCHEMA = TG_TABLE_SCHEMA;
    END IF;
    RETURN OLD;
END;
$funcion$
""",
    """
CREATE TRIGGER trg_requisicion_renglon_borrado_solo_borrador
BEFORE DELETE ON requisicion_renglon
FOR EACH ROW EXECUTE FUNCTION compras_proteger_borrado_de_renglon()
""",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON requisicion TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON requisicion_renglon TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE ON solicitud_autorizacion TO cimenta_aplicacion",
    "REVOKE DELETE ON solicitud_autorizacion FROM cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE ON orden_compra TO cimenta_aplicacion",
    "REVOKE DELETE ON orden_compra FROM cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE ON orden_compra_renglon TO cimenta_aplicacion",
    "REVOKE DELETE ON orden_compra_renglon FROM cimenta_aplicacion",
    "GRANT SELECT, INSERT ON reprogramacion_entrega TO cimenta_aplicacion",
    "REVOKE UPDATE, DELETE ON reprogramacion_entrega FROM cimenta_aplicacion",
    "GRANT SELECT, UPDATE ON folio_consecutivo TO cimenta_aplicacion",
    "REVOKE INSERT, DELETE ON folio_consecutivo FROM cimenta_aplicacion",
)

# DROP TABLE se lleva restricciones, índices, disparadores y privilegios. Las funciones de los
# disparadores no dependen de la tabla, así que se sueltan aparte. Se baja en orden inverso
# a las claves foráneas. La guarda inicial protege las solicitudes, que son permanentes (RN-04).
_BAJADA: tuple[str, ...] = (
    """
DO $$
BEGIN
    LOCK TABLE solicitud_autorizacion IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM solicitud_autorizacion) THEN
        RAISE EXCEPTION 'Hay solicitudes de autorización y son permanentes (RN-04): la bajada de 0014 no las elimina. Respáldalas y vacíalas como propietario si de verdad hay que bajar.';
    END IF;
END
$$
""",
    "DROP TABLE reprogramacion_entrega",
    "DROP TABLE solicitud_autorizacion",
    "DROP TABLE orden_compra_renglon",
    "DROP TABLE orden_compra",
    "DROP TABLE requisicion_renglon",
    "DROP TABLE requisicion",
    "DROP TABLE folio_consecutivo",
    "DROP FUNCTION compras_proteger_borrado_de_renglon()",
    "DROP FUNCTION compras_proteger_borrado_de_requisicion()",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
