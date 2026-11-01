"""TKT-011a · Estructura y catálogos del módulo presupuesto (PA-T10, CA-1 a CA-3, CA-8, CA-11 a CA-14, CA-17, CA-18, CA-20).

Revisión: 0006 · Anterior: 0005

Crea las doce tablas que entrega TKT-011a: empresa, obra, tipo_partida, insumo, nivel, area, partida,
concepto, precio_insumo, apu, apu_insumo y apu_cargo. Cada columna sigue la tabla de nulabilidad
de sdd/tickets/tkt-011/design.md (PA-T10).

Las restricciones llevan nombre: pk_, fk_ con ON DELETE RESTRICT (PA-T8), uq_ y ck_. Los conjuntos
cerrados (tipo_contrato, estado, tipo y unidad) son CHECK con nombre y no ENUM, para que el rechazo
nombre la restricción que lo produce. Los porcentajes de retención y de fondo de garantía van de 0 a
1 (PA-T5); el umbral de alerta solo exige no negatividad y admite nulo. Ninguna columna de dinero es
de punto flotante: los importes llevan numeric(14,4) o numeric(18,4), los porcentajes numeric(9,6) y
el rendimiento de apu_insumo numeric(18,6). Los importes dentro del APU van a escala de precio,
numeric(14,4), porque son por unidad del concepto.

No hay datos semilla ni disparadores: ningún invariante de estas tablas lo exige. El único valor por
omisión es empresa.dias_semana_laboral (6, PA-T2), más creado_en de obra con now().

El rol de aplicación recibe SELECT, INSERT, UPDATE y DELETE sobre cada tabla nueva, con su GRANT
explícito; los privilegios por omisión de 0001 darían lo mismo, y el GRANT lo deja escrito en esta
migración. El rol de lectura hereda SELECT por esos mismos privilegios por omisión. Ningún rol recibe
TRUNCATE, REFERENCES, TRIGGER ni MAINTAIN.

Reversible: sí. Destructiva: solo en la bajada, que elimina las doce tablas y sus filas. Plan de
reversa: si la base tiene datos, respaldarla con pg_dump antes de bajar, y después alembic downgrade
0005. La bajada no se niega porque la spec solo protege la línea base congelada, que llega en 0007.
Cada sentencia va en su propia llamada a op.execute, igual que en 0003 y 0005.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    """
CREATE TABLE empresa (
    id                  uuid      NOT NULL,
    nombre              text      NOT NULL,
    rfc                 text      NOT NULL,
    activa              boolean   NOT NULL,
    dias_semana_laboral smallint  NOT NULL DEFAULT 6,
    CONSTRAINT pk_empresa PRIMARY KEY (id)
)
""",
    """
CREATE TABLE obra (
    id                    uuid         NOT NULL,
    empresa_id            uuid         NOT NULL,
    codigo                text         NOT NULL,
    nombre                text         NOT NULL,
    domicilio             text         NOT NULL,
    tipo_contrato         text         NOT NULL,
    retencion_destajo_pct numeric(9,6) NOT NULL,
    fondo_garantia_pct    numeric(9,6) NOT NULL,
    iva_acreditable       boolean      NOT NULL,
    umbral_alerta_pct     numeric(9,6),
    estado                text         NOT NULL,
    creado_en             timestamptz  NOT NULL DEFAULT now(),
    creado_por_id         uuid         NOT NULL,
    actualizado_en        timestamptz,
    actualizado_por_id    uuid,
    CONSTRAINT pk_obra PRIMARY KEY (id),
    CONSTRAINT fk_obra_empresa_id FOREIGN KEY (empresa_id) REFERENCES empresa (id) ON DELETE RESTRICT,
    CONSTRAINT fk_obra_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_obra_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id) ON DELETE RESTRICT,
    CONSTRAINT uq_obra_codigo UNIQUE (codigo),
    CONSTRAINT ck_obra_tipo_contrato CHECK (tipo_contrato IN ('PRECIO_ALZADO_MAXIMO_GARANTIZADO')),
    CONSTRAINT ck_obra_estado CHECK (estado IN ('PLANEACION', 'ACTIVA', 'SUSPENDIDA', 'CERRADA')),
    CONSTRAINT ck_obra_retencion_destajo_pct_rango CHECK (retencion_destajo_pct >= 0 AND retencion_destajo_pct <= 1),
    CONSTRAINT ck_obra_fondo_garantia_pct_rango CHECK (fondo_garantia_pct >= 0 AND fondo_garantia_pct <= 1),
    CONSTRAINT ck_obra_umbral_alerta_pct_no_negativo CHECK (umbral_alerta_pct >= 0)
)
""",
    """
CREATE TABLE tipo_partida (
    id     uuid NOT NULL,
    clave  text NOT NULL,
    nombre text NOT NULL,
    CONSTRAINT pk_tipo_partida PRIMARY KEY (id),
    CONSTRAINT uq_tipo_partida_clave UNIQUE (clave)
)
""",
    """
CREATE TABLE insumo (
    id                    uuid    NOT NULL,
    codigo                text    NOT NULL,
    descripcion           text    NOT NULL,
    tipo                  text    NOT NULL,
    unidad                text    NOT NULL,
    activo                boolean NOT NULL,
    creado_en_importacion boolean NOT NULL,
    CONSTRAINT pk_insumo PRIMARY KEY (id),
    CONSTRAINT uq_insumo_codigo UNIQUE (codigo),
    CONSTRAINT ck_insumo_tipo CHECK (tipo IN ('MATERIAL', 'MANO_OBRA', 'HERRAMIENTA', 'CONSUMIBLE')),
    CONSTRAINT ck_insumo_unidad CHECK (unidad IN ('M2', 'ML', 'PZA', 'KG', 'CAJA', 'SACO', 'ROLLO', 'JORNAL'))
)
""",
    """
CREATE TABLE nivel (
    id      uuid    NOT NULL,
    obra_id uuid    NOT NULL,
    nombre  text    NOT NULL,
    orden   integer NOT NULL,
    CONSTRAINT pk_nivel PRIMARY KEY (id),
    CONSTRAINT fk_nivel_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT
)
""",
    "CREATE INDEX ix_nivel_obra_id ON nivel (obra_id)",
    """
CREATE TABLE area (
    id          uuid NOT NULL,
    nivel_id    uuid NOT NULL,
    nombre      text NOT NULL,
    tipo_unidad text NOT NULL,
    CONSTRAINT pk_area PRIMARY KEY (id),
    CONSTRAINT fk_area_nivel_id FOREIGN KEY (nivel_id) REFERENCES nivel (id) ON DELETE RESTRICT
)
""",
    "CREATE INDEX ix_area_nivel_id ON area (nivel_id)",
    """
CREATE TABLE partida (
    id              uuid    NOT NULL,
    area_id         uuid    NOT NULL,
    tipo_partida_id uuid    NOT NULL,
    orden           integer NOT NULL,
    CONSTRAINT pk_partida PRIMARY KEY (id),
    CONSTRAINT fk_partida_area_id FOREIGN KEY (area_id) REFERENCES area (id) ON DELETE RESTRICT,
    CONSTRAINT fk_partida_tipo_partida_id FOREIGN KEY (tipo_partida_id) REFERENCES tipo_partida (id) ON DELETE RESTRICT
)
""",
    "CREATE INDEX ix_partida_area_id ON partida (area_id)",
    """
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
""",
    "CREATE INDEX ix_concepto_partida_id ON concepto (partida_id)",
    """
CREATE TABLE precio_insumo (
    id             uuid          NOT NULL,
    insumo_id      uuid          NOT NULL,
    obra_id        uuid,
    costo_unitario numeric(14,4) NOT NULL,
    vigente_desde  date          NOT NULL,
    vigente_hasta  date,
    CONSTRAINT pk_precio_insumo PRIMARY KEY (id),
    CONSTRAINT fk_precio_insumo_insumo_id FOREIGN KEY (insumo_id) REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT fk_precio_insumo_obra_id FOREIGN KEY (obra_id) REFERENCES obra (id) ON DELETE RESTRICT,
    CONSTRAINT ck_precio_insumo_costo_unitario_no_negativo CHECK (costo_unitario >= 0)
)
""",
    "CREATE INDEX ix_precio_insumo_insumo_id ON precio_insumo (insumo_id)",
    """
CREATE TABLE apu (
    id               uuid          NOT NULL,
    concepto_id      uuid          NOT NULL,
    fecha_analisis   date          NOT NULL,
    analista         text          NOT NULL,
    costo_material   numeric(14,4) NOT NULL,
    costo_mano_obra  numeric(14,4) NOT NULL,
    costo_directo    numeric(14,4) NOT NULL,
    total_cargos     numeric(14,4) NOT NULL,
    total_indirectos numeric(14,4) NOT NULL,
    precio_unitario  numeric(14,4) NOT NULL,
    CONSTRAINT pk_apu PRIMARY KEY (id),
    CONSTRAINT fk_apu_concepto_id FOREIGN KEY (concepto_id) REFERENCES concepto (id) ON DELETE RESTRICT,
    CONSTRAINT ck_apu_costo_material_no_negativo CHECK (costo_material >= 0),
    CONSTRAINT ck_apu_costo_mano_obra_no_negativo CHECK (costo_mano_obra >= 0),
    CONSTRAINT ck_apu_costo_directo_no_negativo CHECK (costo_directo >= 0),
    CONSTRAINT ck_apu_total_cargos_no_negativo CHECK (total_cargos >= 0),
    CONSTRAINT ck_apu_total_indirectos_no_negativo CHECK (total_indirectos >= 0),
    CONSTRAINT ck_apu_precio_unitario_no_negativo CHECK (precio_unitario >= 0)
)
""",
    "CREATE INDEX ix_apu_concepto_id ON apu (concepto_id)",
    """
CREATE TABLE apu_insumo (
    id             uuid          NOT NULL,
    apu_id         uuid          NOT NULL,
    insumo_id      uuid          NOT NULL,
    costo_unitario numeric(14,4) NOT NULL,
    rendimiento    numeric(18,6) NOT NULL,
    cargo          numeric(14,4) NOT NULL,
    CONSTRAINT pk_apu_insumo PRIMARY KEY (id),
    CONSTRAINT fk_apu_insumo_apu_id FOREIGN KEY (apu_id) REFERENCES apu (id) ON DELETE RESTRICT,
    CONSTRAINT fk_apu_insumo_insumo_id FOREIGN KEY (insumo_id) REFERENCES insumo (id) ON DELETE RESTRICT,
    CONSTRAINT ck_apu_insumo_costo_unitario_no_negativo CHECK (costo_unitario >= 0),
    CONSTRAINT ck_apu_insumo_rendimiento_no_negativo CHECK (rendimiento >= 0),
    CONSTRAINT ck_apu_insumo_cargo_no_negativo CHECK (cargo >= 0)
)
""",
    "CREATE INDEX ix_apu_insumo_apu_id ON apu_insumo (apu_id)",
    """
CREATE TABLE apu_cargo (
    id           uuid          NOT NULL,
    apu_id       uuid          NOT NULL,
    tipo         text          NOT NULL,
    porcentaje   numeric(9,6)  NOT NULL,
    base_calculo numeric(14,4) NOT NULL,
    importe      numeric(14,4) NOT NULL,
    CONSTRAINT pk_apu_cargo PRIMARY KEY (id),
    CONSTRAINT fk_apu_cargo_apu_id FOREIGN KEY (apu_id) REFERENCES apu (id) ON DELETE RESTRICT,
    CONSTRAINT ck_apu_cargo_tipo CHECK (tipo IN ('HERRAMIENTA_MENOR', 'ANDAMIAJE', 'DESPERDICIO', 'VIATICOS', 'IVA', 'INDIRECTOS', 'UTILIDAD')),
    CONSTRAINT ck_apu_cargo_porcentaje_no_negativo CHECK (porcentaje >= 0),
    CONSTRAINT ck_apu_cargo_base_calculo_no_negativo CHECK (base_calculo >= 0),
    CONSTRAINT ck_apu_cargo_importe_no_negativo CHECK (importe >= 0)
)
""",
    "CREATE INDEX ix_apu_cargo_apu_id ON apu_cargo (apu_id)",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON empresa TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON obra TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON tipo_partida TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON insumo TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON nivel TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON area TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON partida TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON concepto TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON precio_insumo TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON apu TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON apu_insumo TO cimenta_aplicacion",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON apu_cargo TO cimenta_aplicacion",
)

# Orden inverso de dependencias: cada tabla se borra antes que las que referencia.
_BAJADA: tuple[str, ...] = (
    "DROP TABLE apu_cargo",
    "DROP TABLE apu_insumo",
    "DROP TABLE apu",
    "DROP TABLE precio_insumo",
    "DROP TABLE concepto",
    "DROP TABLE partida",
    "DROP TABLE area",
    "DROP TABLE nivel",
    "DROP TABLE insumo",
    "DROP TABLE tipo_partida",
    "DROP TABLE obra",
    "DROP TABLE empresa",
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
