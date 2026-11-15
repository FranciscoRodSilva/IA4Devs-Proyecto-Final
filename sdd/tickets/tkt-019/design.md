# Design · TKT-019 · Esquema y migraciones del módulo compras

> [← index](_index.md) | [← spec](spec.md) | Siguiente: impl (se enlaza en `/sdd-ejecutar`)

## Estrategia

Dos migraciones nuevas sobre la cabeza `0013`: `0014` crea las siete tablas de `compras` con sus restricciones nombradas, sus índices, dos disparadores que solo dejan borrar una requisición en `BORRADOR` y los privilegios por tabla y por rol; `0015` siembra las dos series de `folio_consecutivo`, porque la convención del proyecto separa la semilla del esquema (`0002` y `0008` lo hacen así). Todo lo que el modelo de datos declara como invariante —centro de costos, cifras no negativas, recepción dentro de lo autorizado, resolución con motivo— lo sostiene el motor con `NOT NULL` y `CHECK` con nombre, y cada rechazo se prueba con su `sqlstate` y su `constraint_name`, con su control positivo en el borde. No hay código Python de producción en `cimenta/`: ni modelos Core ni repositorios, que crea TKT-021.

El segundo objetivo, subir `dnspython`, es una fila aparte e independiente: `uv lock --upgrade-package dnspython` sin tocar `pyproject.toml`, comprobado con el mismo `pip-audit` y el mismo filtro que corre el trabajo «Dependencias». Si la versión nueva no corrige el aviso, se aplica `CA-13` con la excepción fechada que la persona dueña ya decidió.

El orden suma unas 330 líneas de producción (la migración `0014` con su docstring, unas 280; `0015`, unas 50; `ci.yml`, cuatro solo si se aplica `CA-13`). No hace falta partir el ticket: va en una sola entrega, sobre la rama `tkt-019-esquema-compras` y un solo PR. Las pruebas suman unas 1,000 líneas en tres archivos nuevos.

## Decisiones para el gate

Las preguntas 4b y 5 a 17 de la spec, y cinco que aparecieron al diseñar (`D-15` a `D-19`). **La persona dueña las aprobó todas el 2026-11-15**, con la recomendación de cada una; cada fila lleva `(aprobada · D-n)`, y la columna derecha dice qué cambia en este diseño si elige otra cosa. Salvo donde se indica la evidencia en contra (`D-6` y `D-13`), la recomendación es la de la spec.

| # | Pregunta | Recomendación | Qué cambia si se elige otra cosa |
|---|---|---|---|
| D-1 | **Cancelación de la orden** (pregunta 4b) | `orden_compra.cancelada_en timestamptz` nulable y `motivo_cancelacion text` nulable, con `ck_orden_compra_cancelacion_con_motivo CHECK ((cancelada_en IS NULL) = (motivo_cancelacion IS NULL))`. El `comprometido` de §15 pasa a filtrar `oc.cancelada_en IS NULL` en lugar de `oc.estado IN ('ABIERTA','PARCIAL')`: una orden `CERRADA` ya aporta cero por el `GREATEST`, así que el resultado es el mismo. TKT-021 lo hereda del modelo de datos reconciliado | «Una columna `cancelada boolean`»: se pierde el momento y el `CHECK` pasa a `cancelada = (motivo_cancelacion IS NOT NULL)`; TC-20 cambia de columna. «Sin `CHECK`»: se borra la restricción, TC-20 y el mutante `M-17` |
| D-2 | **`solicitud_autorizacion.entidad_id` polimórfica** (pregunta 5) | Sin clave foránea, añadida a la lista cerrada de referencias lógicas de modelo de datos §2 y §13 con su motivo: la solicitud es genérica (`RN-03`, `RN-07`, `RN-15`) y apunta a una requisición o a una orden. `ck_solicitud_autorizacion_entidad_tipo CHECK (entidad_tipo IN ('REQUISICION', 'ORDEN_COMPRA'))`, en mayúsculas como el borrador (la bitácora usa minúsculas; TC-17 prueba que `'requisicion'` se rechaza) | «Dos columnas con clave foránea» (`requisicion_id` y `orden_compra_id`, nulables, con `CHECK` de exactamente una): integridad real, sin referencia lógica nueva, pero el modelo y el borrador hablan de `entidad_tipo` y `entidad_id`, y el API tendría que derivarlos. Cambian la tabla, TC-04, TC-17 y la reconciliación de §2 (que ya no haría falta) |
| D-3 | **`DELETE` sobre `requisicion`** (pregunta 6). Un privilegio no distingue estados: concedido, el rol de aplicación podría borrar una requisición `EVALUADA` y con ella su peso en el `consumido` (regla 5 de `CLAUDE.md`). Revocado, no existiría el `DELETE` de un borrador que el borrador del API publica (`eliminar_borrador_requisicion`, `204`, HDU-002 esc. 2) | **Opción B (recomendada): disparadores.** El rol de aplicación conserva `DELETE` sobre `requisicion` y `requisicion_renglon`, y dos disparadores `BEFORE DELETE` lo rechazan con `SQLSTATE` `IN002` si la requisición no está en `BORRADOR` (`trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador`; el del renglón lee la requisición con `FOR SHARE`, como el invariante 14). Protegen estructura, no deciden ninguna regla: el caso de uso de TKT-023 sigue comprobando el estado y respondiendo `409`, y el disparador solo detiene lo que llegue por otra vía. Se elige porque respeta el contrato publicado, HDU-002 esc. 2 y la máquina de estados, y porque el borrador no consume | **Opción A: revocar `DELETE` en las dos tablas y que el borrador se cancele.** Se quitan los dos disparadores, sus dos funciones, TC-25, TC-26 y los mutantes `M-11` a `M-13`; las dos tablas pasan a `GRANT SELECT, INSERT, UPDATE` y `REVOKE DELETE`, y TC-24 las añade. Fuera de este ticket, exige cambiar el borrador del API (quitar `eliminar_borrador_requisicion`), HDU-002 esc. 2 y la máquina de estados de §14, que hoy no tiene `BORRADOR → CANCELADA`; y `D-15` deja de hacer falta, porque un borrador cancelado conserva su folio. Tampoco hacen falta la transición `BORRADOR --> [*]` de §14, el criterio `IN002` de TKT-023 ni las filas nuevas de `conv-sql-postgres` y `desarrollador-sql.md` |
| D-4 | **`ON DELETE` de las claves foráneas** (pregunta 7) | `ON DELETE RESTRICT` explícito en todas, como `presupuesto`. Borrar una obra con requisiciones responde `23001` | «`CASCADE` en los renglones»: borrar una requisición arrastraría sus renglones; con `D-3` opción B el disparador del renglón seguiría protegiendo los no borradores. Cambian dos restricciones y TC-04 |
| D-5 | **Órdenes por requisición** (pregunta 8) | Índice único parcial `uq_orden_compra_requisicion_id_vigente ON orden_compra (requisicion_id) WHERE cancelada_en IS NULL`: como mucho una orden viva por requisición, y una cancelada no impide reconvertir | «Sin índice»: la unicidad queda solo en el caso de uso de TKT-030; se borran el índice, TC-21 y `M-15`. «`UNIQUE` simple»: impediría reconvertir tras cancelar, contra §14 (`CONVERTIDA → EVALUADA`) |
| D-6 | **`fecha_compromiso` del renglón** (pregunta 9). **Hay evidencia contra la recomendación de la spec** (`NULL`): el borrador del API exige `fecha_compromiso` general en `OrdenCompraNueva` y la publica no nula en `RenglonOrdenCompra`, junto con `primera_fecha_compromiso`; y TKT-030 («`fecha_compromiso` opcional por renglón al emitir») se refiere a la fecha **por renglón** cuando difiere de la general, no a que falte | `fecha_compromiso date NOT NULL`. `primera_fecha_compromiso` no lleva columna: es la `fecha_anterior` de la primera reprogramación del renglón o, sin reprogramaciones, la propia `fecha_compromiso`. `RN-06` distingue «reprogramada» por la existencia de filas en `reprogramacion_entrega` | «Nulable», la de la spec: la columna pierde `NOT NULL`, TC-04 cambia su nulabilidad y el borrador del API quedaría prometiendo una fecha que el esquema no garantiza |
| D-7 | **Índices** (pregunta 10) | Sí, en este ticket. `ix_requisicion_obra_id_tipo_partida_id_estado` (§15, también sirve las búsquedas por obra) y un índice por cada clave foránea por la que se lee de padre a hijo: `ix_requisicion_renglon_requisicion_id`, `ix_orden_compra_obra_id` (el `comprometido` filtra `oc.obra_id`), `ix_orden_compra_renglon_orden_compra_id`, `ix_reprogramacion_entrega_orden_compra_renglon_id` y `ix_solicitud_autorizacion_entidad_tipo_entidad_id`. Sobre `orden_compra_renglon` va el índice **completo** por `orden_compra_id`, no el parcial que dibuja §15: el completo sirve al `comprometido` y al detalle de la orden, y un parcial además sería redundante. §15 se actualiza | «Solo los de §15»: se quitan los cuatro índices de clave foránea y el completo se sustituye por `ix_orden_compra_renglon_orden_compra_id_con_saldo ... WHERE cantidad_recibida < cantidad_ordenada`. «Ninguno»: se quitan los seis y la lista de TC-04 |
| D-8 | **Siembra de `folio_consecutivo`** (pregunta 11) | Una migración propia, `0015` (`v0015_semilla_folios_de_compras.py`), que inserta `ORDEN_COMPRA` y `REQUISICION` con `ultimo = 0` y `ON CONFLICT DO NOTHING`, como `0008`. La convención (`conv-sql-postgres` §4) prohíbe mezclar semilla con DDL. El formato del folio (`REQ-AP05825-0042`) lo arma el caso de uso de TKT-021 y TKT-030; el consecutivo es global por serie | «En `0014`»: una sentencia más al final de `_SUBIDA` de `0014`, sin `0015`; la cabeza vuelve a ser `0014` como dice `CA-R1`, y TC-29 y la fila F4 se funden en F2. Con la recomendación, la cabeza es `0015` y `CA-R1` se lee «`0014` cuelga de `0013` y `0015` de `0014`» |
| D-9 | **Columnas que el API publica y el modelo no tiene** (pregunta 12) | Se añaden: `requisicion.observaciones text`, `requisicion.creado_en` y `actualizado_en`, `orden_compra.creado_en` (sin `actualizado_en`: `OrdenCompra` del borrador no lo publica, hallazgo H-2 de `revisor-impacto`), `solicitud_autorizacion.obra_id` (con clave foránea a `obra`) y `solicitud_autorizacion.creado_en`, todas `timestamptz NOT NULL` salvo `observaciones`. **No** llevan columna, porque se derivan: `Requisicion.solicitud_autorizacion_id` y `orden_compra_id`, `OrdenCompra.tipo_partida` y `solicitud_autorizacion_id` (por la requisición), `saldo_pendiente`, `reprogramaciones` y `primera_fecha_compromiso` del renglón, `reprogramaciones_acumuladas`, `SolicitudAutorizacion.sin_efecto` y `motivo_sin_efecto` (una solicitud `PENDIENTE` cuya requisición está `CANCELADA`, con el `motivo_cancelacion` de esta), y `SolicitudAutorizacion.importe_solicitado`, `excedente`, `tipo_partida` y sus renglones, que salen de la requisición de `entidad_id` o de `contexto`. Ninguna tabla lleva `creado_por_id` ni `actualizado_por_id`: el actor ya está en `solicitante_id`, `registrado_por_id` y en la bitácora (excepción `PA-T11` de §2) | «Columna `sin_efecto`»: `solicitud_autorizacion` gana `sin_efecto boolean NOT NULL DEFAULT false` y `motivo_sin_efecto text`, con un `CHECK` de que van juntos; TC-04 y TC-15 los añaden. «Columnas de auditoría completas»: cuatro columnas más por tabla transaccional y sus claves foráneas a `usuario`. «Conservar `orden_compra.actualizado_en` por uniformidad con `requisicion` (asumido)»: una columna más en el DDL de la orden, en TC-04 y en el diagrama de §5 |
| D-10 | **Nombre del costo del renglón de requisición** (pregunta 13) | `costo_unitario_estimado`, como el modelo y el borrador | Solo cambia el nombre de la columna, de su `CHECK` y de TC-04 y TC-09 |
| D-11 | **Invariante 9 completo** (pregunta 14) | `ck_solicitud_autorizacion_resolucion_completa CHECK (estado = 'PENDIENTE' OR (motivo_resolucion IS NOT NULL AND resuelta_por_id IS NOT NULL AND resuelta_en IS NOT NULL))`. La fila del invariante 9 en §13 se actualiza | «Solo el motivo», el texto actual del invariante: el `CHECK` pierde las dos últimas condiciones y TC-15 pierde dos casos; `M-9` desaparece |
| D-12 | **`cantidad_excedente` de la solicitud** (pregunta 15) | `ck_solicitud_autorizacion_cantidad_excedente_positiva CHECK (cantidad_excedente > 0)` | «`>= 0`»: se renombra a `_no_negativo` y TC-17 pasa a admitir el cero |
| D-13 | **Valores de `regla_bloqueo`, `regla_negocio` y `rol_autorizador`** (pregunta 16). **Hay evidencia contra la lista cerrada para `regla_negocio`**: `TRABAJO_EXTRA` no tiene regla en el PRD (RN-18 habla de su presupuesto, no de esta autorización), y una lista la tendría que inventar | `ck_requisicion_regla_bloqueo CHECK (regla_bloqueo IN ('RN-03'))` (nulable: `NULL` si la requisición pasó); `ck_solicitud_autorizacion_regla_negocio_formato CHECK (regla_negocio ~ '^RN-[0-9]{2}$')`, el mismo de la bitácora; y `fk_solicitud_autorizacion_rol_autorizador FOREIGN KEY (rol_autorizador) REFERENCES rol (clave) ON DELETE RESTRICT`, que se apoya en `uq_rol_clave` | «Lista cerrada»: `ck_solicitud_autorizacion_regla_negocio CHECK (regla_negocio IN ('RN-03', 'RN-07', 'RN-15'))` y `TRABAJO_EXTRA` queda sin regla admisible hasta su ticket (v1.1). «Texto libre en `rol_autorizador`»: se quita la clave foránea y TC-17 pierde su caso |
| D-14 | **Glosario de «Orden de compra»** (pregunta 17) | «Documento en firme emitido al proveedor. Nace de una requisición que cupo en el presupuesto (`EVALUADA`) o cuya excepción autorizó Dirección General (`AUTORIZADA`).» | Otro texto solo cambia la línea 125 del glosario |
| D-15 | **Folio de una requisición en `BORRADOR`** (nueva). Con `D-3` opción B un borrador se borra; si ya tuviera folio, dejaría un hueco, contra modelo de datos §5 («los folios no tienen huecos»). TKT-021 numera «en la transacción que crea el documento», y el borrador del API publica `folio` no nulo también en borrador: los dos textos chocan | `requisicion.folio text` **nulable**, con `uq_requisicion_folio UNIQUE (folio)` y `ck_requisicion_folio_fuera_de_borrador CHECK (estado = 'BORRADOR' OR folio IS NOT NULL)`. El esquema admite las dos políticas —numerar al crear o al enviar— y garantiza que nada evaluado quede sin folio. **Cuándo se numera lo decide TKT-021 o TKT-023**, no este ticket; si se numera al enviar, el borrador del API tendrá que publicar `folio` nulable en `BORRADOR` (aviso de cambio de contrato para ese ticket) | «`folio NOT NULL`»: el borrador siempre lleva folio, el `CHECK` desaparece, TC-08 y TC-12 cambian, y con `D-3` opción B borrar un borrador deja un hueco que habría que aceptar por escrito |
| D-16 | **Motivo al cancelar una requisición** (nueva; el borrador del API exige `MotivoObligatorio` en `cancelar_requisicion`) | `ck_requisicion_cancelacion_con_motivo CHECK (estado <> 'CANCELADA' OR motivo_cancelacion IS NOT NULL)`, por la misma razón que `D-1` en la orden | «Sin `CHECK`»: se borra la restricción y su caso de TC-08 |
| D-17 | **Privilegios de `folio_consecutivo` y `reprogramacion_entrega`** (nueva; la spec solo fija el `DELETE`) | `folio_consecutivo`: el rol de aplicación tiene `SELECT` y `UPDATE` (el `FOR UPDATE` exige `UPDATE`), sin `INSERT` ni `DELETE`: las series las siembra `0015` y no cambian. `reprogramacion_entrega`: `SELECT` e `INSERT`, sin `UPDATE` ni `DELETE`: es el rastro de cada aplazamiento (`RN-06`) y no se corrige | «Solo `REVOKE DELETE`», lo mínimo de `CA-11`: cada tabla conserva `INSERT` o `UPDATE`; TC-23 y TC-24 cambian sus conjuntos y TC-14 pierde el `42501` del `INSERT` |
| D-18 | **Bajadas que se niegan** (nueva) | La bajada de `0014` se niega con `RAISE EXCEPTION` si `solicitud_autorizacion` tiene filas, como la de `0003` con la bitácora: `RN-04` las declara permanentes. La de `0015` se niega si algún contador tiene `ultimo > 0`: borrarlo y volver a sembrarlo en cero reutilizaría folios. Ambas guardas toman `LOCK TABLE … IN ACCESS EXCLUSIVE MODE` antes de consultar, como `0012`, para que una inserción concurrente no se pierda entre la comprobación y el borrado. Fuera de eso, el plan de reversa es `pg_dump` antes de bajar | «Bajadas sin guarda», como `0013`: se quitan los dos bloques `DO` y TC-28 |
| D-19 | **Fecha de revisión de la excepción** (nueva; solo si se aplica `CA-13`) | `--ignore-vuln GHSA-vvf4-9x63-8xvv` con revisión el **2026-12-14**, treinta días después de la decisión, o antes si `dnspython` publica la corrección | Otra fecha solo cambia el comentario de `ci.yml` |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Siete tablas de `compras` | 5 · objeto nuevo | No existe ninguna; el modelo de datos §5 las define y el Must las exige |
| `NOT NULL` en `obra_id` y `tipo_partida_id` (invariante 1) | 2 · nativo | Restricción de columna; ninguna validación en código |
| `CHECK ... >= 0` con nombre `_no_negativo` (invariante 8) | 2 · nativo | Uno por importe, precio y cantidad; `importe_disponible` y `cantidad_disponible` exentos por decisión de la persona dueña |
| `ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado` (invariante 2) | 2 · nativo | El texto exacto del invariante; `cantidad_excedente_autorizada` con `DEFAULT 0` y su propio `CHECK` |
| `ck_solicitud_autorizacion_resolucion_completa` (invariante 9) | 2 · nativo | `CHECK` de varias columnas `(aprobada · D-11)` |
| `ck_solicitud_autorizacion_excede_ordenado_con_renglon` (`RN-07`, `PA-16`) | 2 · nativo | Un `CHECK` de doble sentido: con `EXCEDE_ORDENADO` los dos valores, con otro motivo ninguno |
| Enumeraciones (`estado`, `motivo`, `entidad_tipo`, `serie`) | 2 · nativo | `CHECK ... IN` con nombre `ck_<tabla>_<columna>` ([ADR-030](../../../docs/adr/20261101-catalogos-cerrados-por-check.md)); ningún `ENUM` |
| `uq_requisicion_folio`, `uq_orden_compra_folio` | 2 · nativo | `UNIQUE`; el folio nulable del borrador no choca porque los `NULL` son distintos `(aprobada · D-15)` |
| `uq_orden_compra_requisicion_id_vigente` | 2 · nativo | Único parcial `(aprobada · D-5)` |
| `orden_compra.cancelada_en` y su `CHECK` | 4 · cambio mínimo | La persona dueña decidió no guardar el estado; la cancelación es lo único que no se deriva `(aprobada · D-1)` |
| Disparadores `trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador` | 2 · nativo | Un privilegio no distingue estados; un disparador sí, en el motor, como el invariante 14. Patrón y forma del rechazo de `0007` `(aprobada · D-3)` |
| Privilegios por tabla | 2 · nativo | `GRANT` y `REVOKE` explícitos sobre los privilegios por omisión de `0001` `(aprobada · D-17)` |
| `orden_compra.proveedor_id` sin clave foránea | 1 · regla registrada | Modelo de datos §2 y §5: una clave invertiría la arista `proveedores → compras` |
| Columna de estado de la orden, motivo de cierre, `sin_efecto`, `primera_fecha_compromiso`, contadores de reprogramación | 1 · YAGNI | Se derivan; una columna que se puede escribir se desincroniza (modelo de datos §1) `(aprobada · D-9)` |
| Seis índices | 2 · nativo | Índices de PostgreSQL; ninguna vista materializada `(aprobada · D-7)` |
| `v0015_semilla_folios_de_compras.py` | 5 · objeto nuevo | La convención separa semilla y esquema; sin las dos filas, el primer alta no tiene qué bloquear `(aprobada · D-8)` |
| `CHECK (fecha_nueva >= fecha_anterior)` en la reprogramación | 1 · YAGNI, descartado | Ningún Must lo pide; la fecha anterior a la vigente es un `422` del API (`FECHA_ANTERIOR_A_VIGENTE`, TKT-054) |
| Clave foránea compuesta para que la orden tenga la misma obra que su requisición | 1 · YAGNI, descartado | Ningún Must lo pide; TKT-030 copia la obra de la requisición. Queda en «Riesgos» |
| `dnspython` en `backend/uv.lock` | 4 · cambio mínimo | `uv lock --upgrade-package dnspython`: solo cambia su bloque, sin tocar `pyproject.toml` ni otra versión |
| `--ignore-vuln` en `ci.yml` | 4 · cambio mínimo, condicional | Solo si `CA-13`: una opción en el paso existente y su comentario `(aprobada · D-19)` |

Ningún objeto paró en el peldaño 4 sobre un invariante registrado: la escalera no se rompe. El disparador de `D-3` no toca el invariante 14: es un mecanismo nuevo y separado, con su propio `SQLSTATE`.

## Capas afectadas

### Infraestructura y esquema

**Migración:** `0014` (`backend/migraciones/versions/v0014_compras_esquema.py`, `down_revision = "0013"`) y `0015` (`backend/migraciones/versions/v0015_semilla_folios_de_compras.py`, `down_revision = "0014"`) — reversibles: sí · destructivas: solo las bajadas, que borran tablas y filas · plan de reversa: respaldar con `pg_dump` y `alembic downgrade 0013` con el rol de migración; las bajadas se niegan con solicitudes o con folios ya usados `(aprobada · D-18)`. Cada sentencia en su propia llamada a `op.execute`, en tuplas `_SUBIDA` y `_BAJADA`, como `0013`. El docstring de cada una nombra revisión, anterior, garantías, privilegios, reversibilidad y plan de reversa, como `0013`.

#### `0014` · sentencias de subida, en este orden

Las sentencias 1 a 14 son de la fila F2; de la 15 a la 30, de la fila F3.

**1 · `requisicion`**

```sql
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
```

`importe_disponible` no lleva `CHECK` (decisión de la persona dueña, 2026-11-14): es la cifra del momento de evaluar y puede ser negativa si una excepción autorizada dejó el consumido por encima del tope.

**2 · `requisicion_renglon`**

```sql
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
```

`cantidad_disponible` no lleva `CHECK`, por la misma decisión.

**3 · `orden_compra`**

```sql
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
```

`proveedor_id` no tiene clave foránea (modelo de datos §2). No existe columna `estado` ni de motivo de cierre.

**4 · `orden_compra_renglon`**

```sql
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
```

`ck_orden_compra_renglon_excedente_autorizado_no_negativo` se aparta del patrón `ck_<tabla>_<columna>_no_negativo` a propósito: el nombre completo tendría 65 caracteres y PostgreSQL lo truncaría a 63.

**5 · `solicitud_autorizacion`**

```sql
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
```

`entidad_id` no tiene clave foránea `(aprobada · D-2)`.

**6 · `reprogramacion_entrega`**

```sql
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
```

**7 · `folio_consecutivo`**

```sql
CREATE TABLE folio_consecutivo (
    serie  text   NOT NULL,
    ultimo bigint NOT NULL DEFAULT 0,
    CONSTRAINT pk_folio_consecutivo PRIMARY KEY (serie),
    CONSTRAINT ck_folio_consecutivo_serie CHECK (serie IN ('REQUISICION', 'ORDEN_COMPRA')),
    CONSTRAINT ck_folio_consecutivo_ultimo_no_negativo CHECK (ultimo >= 0)
)
```

**8 a 14 · índices** `(aprobada · D-5, D-7)`, una sentencia cada uno:

```sql
CREATE UNIQUE INDEX uq_orden_compra_requisicion_id_vigente ON orden_compra (requisicion_id) WHERE cancelada_en IS NULL
CREATE INDEX ix_requisicion_obra_id_tipo_partida_id_estado ON requisicion (obra_id, tipo_partida_id, estado)
CREATE INDEX ix_requisicion_renglon_requisicion_id ON requisicion_renglon (requisicion_id)
CREATE INDEX ix_orden_compra_obra_id ON orden_compra (obra_id)
CREATE INDEX ix_orden_compra_renglon_orden_compra_id ON orden_compra_renglon (orden_compra_id)
CREATE INDEX ix_solicitud_autorizacion_entidad_tipo_entidad_id ON solicitud_autorizacion (entidad_tipo, entidad_id)
CREATE INDEX ix_reprogramacion_entrega_orden_compra_renglon_id ON reprogramacion_entrega (orden_compra_renglon_id)
```

**15 a 18 · disparadores** `(aprobada · D-3, opción B)`. Mismo patrón que `presupuesto_proteger_copia_congelada` de `0007` (`SECURITY INVOKER`, `RAISE ... USING ERRCODE, MESSAGE, CONSTRAINT = TG_NAME, TABLE, SCHEMA`). El `SQLSTATE` `IN002` está libre en el repositorio (solo existe `IN001`, de `RN-01`). Son dos funciones, una por tabla, para que ninguna lea una columna que su tabla no tiene.

```sql
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
```

```sql
CREATE TRIGGER trg_requisicion_borrado_solo_borrador
BEFORE DELETE ON requisicion
FOR EACH ROW EXECUTE FUNCTION compras_proteger_borrado_de_requisicion()
```

```sql
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
```

```sql
CREATE TRIGGER trg_requisicion_renglon_borrado_solo_borrador
BEFORE DELETE ON requisicion_renglon
FOR EACH ROW EXECUTE FUNCTION compras_proteger_borrado_de_renglon()
```

El `FOR SHARE` espera a una transacción que esté cambiando el estado de la requisición y lee el estado confirmado; exige `UPDATE` sobre `requisicion`, que el rol de aplicación tiene. Un `TRUNCATE` no dispara disparadores de fila: lo impide que nadie reciba `TRUNCATE` (TC-24).

**19 a 30 · privilegios** `(aprobada · D-3, D-17)`, una sentencia cada uno. El rol de lectura recibe `SELECT` por los privilegios por omisión de `0001` y nada más; nadie recibe `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN`.

| # | Sentencia |
|---|---|
| 19 | `GRANT SELECT, INSERT, UPDATE, DELETE ON requisicion TO cimenta_aplicacion` |
| 20 | `GRANT SELECT, INSERT, UPDATE, DELETE ON requisicion_renglon TO cimenta_aplicacion` |
| 21 | `GRANT SELECT, INSERT, UPDATE ON solicitud_autorizacion TO cimenta_aplicacion` |
| 22 | `REVOKE DELETE ON solicitud_autorizacion FROM cimenta_aplicacion` |
| 23 | `GRANT SELECT, INSERT, UPDATE ON orden_compra TO cimenta_aplicacion` |
| 24 | `REVOKE DELETE ON orden_compra FROM cimenta_aplicacion` |
| 25 | `GRANT SELECT, INSERT, UPDATE ON orden_compra_renglon TO cimenta_aplicacion` |
| 26 | `REVOKE DELETE ON orden_compra_renglon FROM cimenta_aplicacion` |
| 27 | `GRANT SELECT, INSERT ON reprogramacion_entrega TO cimenta_aplicacion` |
| 28 | `REVOKE UPDATE, DELETE ON reprogramacion_entrega FROM cimenta_aplicacion` |
| 29 | `GRANT SELECT, UPDATE ON folio_consecutivo TO cimenta_aplicacion` |
| 30 | `REVOKE INSERT, DELETE ON folio_consecutivo FROM cimenta_aplicacion` |

Privilegios resultantes del rol de aplicación, que TC-23 compara exactos: `requisicion` y `requisicion_renglon` `{SELECT, INSERT, UPDATE, DELETE}`; `solicitud_autorizacion`, `orden_compra` y `orden_compra_renglon` `{SELECT, INSERT, UPDATE}`; `reprogramacion_entrega` `{SELECT, INSERT}`; `folio_consecutivo` `{SELECT, UPDATE}`. Rol de lectura: `{SELECT}` en las siete. `PUBLIC`: nada.

#### `0014` · sentencias de bajada, en este orden

| # | Sentencia | Fila |
|---|---|---|
| 1 | Bloque `DO $$ BEGIN LOCK TABLE solicitud_autorizacion IN ACCESS EXCLUSIVE MODE; IF EXISTS (SELECT 1 FROM solicitud_autorizacion) THEN RAISE EXCEPTION 'Hay solicitudes de autorización y son permanentes (RN-04): la bajada de 0014 no las elimina. Respáldalas y vacíalas como propietario si de verdad hay que bajar.'; END IF; END $$` `(aprobada · D-18)` | F2 |
| 2 a 8 | `DROP TABLE reprogramacion_entrega`, `DROP TABLE solicitud_autorizacion`, `DROP TABLE orden_compra_renglon`, `DROP TABLE orden_compra`, `DROP TABLE requisicion_renglon`, `DROP TABLE requisicion`, `DROP TABLE folio_consecutivo`, cada una en su `op.execute`. `DROP TABLE` se lleva restricciones, índices, disparadores y privilegios | F2 |
| 9 | `DROP FUNCTION compras_proteger_borrado_de_renglon()` | F3 |
| 10 | `DROP FUNCTION compras_proteger_borrado_de_requisicion()` | F3 |

#### `0015` · semilla de los folios

- Subida, una sentencia: `INSERT INTO folio_consecutivo (serie, ultimo) VALUES ('ORDEN_COMPRA', 0), ('REQUISICION', 0) ON CONFLICT DO NOTHING`. Solo datos, sin DDL ni `GRANT`, como `0008`.
- Bajada, dos sentencias: el bloque `DO $$ BEGIN LOCK TABLE folio_consecutivo IN ACCESS EXCLUSIVE MODE; IF EXISTS (SELECT 1 FROM folio_consecutivo WHERE ultimo > 0) THEN RAISE EXCEPTION 'Ya se emitieron folios: la bajada de 0015 los reiniciaría y se repetirían. Respalda la base antes de bajar.'; END IF; END $$` `(aprobada · D-18)`, y `DELETE FROM folio_consecutivo WHERE serie IN ('ORDEN_COMPRA', 'REQUISICION')`.

### Cadena de dependencias

| Objeto | Tipo | Detalle |
|---|---|---|
| `backend/uv.lock` | lock | `uv lock --upgrade-package dnspython` desde `backend/`. Solo cambian `version`, `sdist` y `wheels` del bloque `name = "dnspython"`. `backend/pyproject.toml` no cambia. Hoy: `2.9.0`; candidata comprobada con `--dry-run`: `2.9.2` |
| `.github/workflows/ci.yml` | pipeline | **Solo si se aplica `CA-13`**. En el paso «Auditar Python con pip-audit» se añade `--ignore-vuln GHSA-vvf4-9x63-8xvv` a la orden de `pip-audit`, y en el comentario de las líneas 291 y 292 «Excepciones: ninguna al arrancar.» pasa a la lista de excepciones vigentes, con este texto: «`GHSA-vvf4-9x63-8xvv` (`dnspython`, severidad alta): decidida por la persona dueña, Juan Francisco Rodriguez Silva, el 2026-11-14, porque no existe una versión de `dnspython` que la corrija y solo la arrastra `email-validator`. Revisar el 2026-12-14 o al publicarse la corrección.» `(aprobada · D-19)`. Ninguna otra vulnerabilidad se ignora |

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Comandos desde `backend/` salvo que se diga otra cosa; `uv run pytest` necesita Docker en marcha. Las pruebas viven en tres archivos nuevos: `tests/test_tkt019_migracion.py` (cadena, ciclo y regresión), `tests/test_tkt019_restricciones.py` (`CA-1` a `CA-10`) y `tests/test_tkt019_privilegios.py` (`CA-11` y disparadores).

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| F1 | Subir `dnspython` en `backend/uv.lock`; si no hay versión corregida, la excepción de `CA-13` en `ci.yml` | TC-D1 a TC-D3 (comprobaciones por comando, sin `pytest`). **Rojo**: con el lock actual, el filtro sale con **1** y nombra `GHSA-vvf4-9x63-8xvv` `(sin ejecutar)` | `ingeniero-devsecops` | `haiku` · tarea mecánica y verificable por comando, «fijar una versión» (§14.2) | Rojo, desde `backend/`: `uv export --locked --all-groups --no-emit-project --format requirements.txt -o <tmp>/req.txt`; `uv run pip-audit -r <tmp>/req.txt --require-hashes --disable-pip --strict -f json -o <tmp>/pip-audit.json` (termina en 1 con hallazgos; se ignora su código); desde la raíz, `python tools/severidad_pip_audit.py <tmp>/pip-audit.json` → **1**. Verde: `uv lock --upgrade-package dnspython`; `git diff -- backend/uv.lock` solo muestra el bloque de `dnspython` (TC-D3); `uv sync --locked --python 3.14`; se repiten la exportación, `pip-audit` y el filtro → **0** (TC-D1). Si el filtro sigue en 1 y la versión instalada es la más nueva que publica PyPI: se aplica `CA-13` (TC-D2) con el texto de «Cadena de dependencias», se repite la corrida con `--ignore-vuln` y el filtro sale con 0; además, desde la raíz, `python -m unittest tools.tests.test_definicion_ci -v` y `python tools/verificar_docs.py` en verde. En los dos caminos, la exportación `uv export --locked …` del pipeline (`ci.yml:286`) tiene que pasar con el lock nuevo. Si existe una versión corregida que `uv` no alcanza sin cambiar otra dependencia: **se detiene y se escala**, porque el ticket no sube otras dependencias. Un código **2** del filtro es un informe ausente o ilegible, no un hallazgo: se corrige la corrida, no el lock. La suite completa con la versión nueva corre al cerrar F4 (`CA-R3`). La comprobación en el pipeline queda para `/sdd-completar` (`CA-12`) | Pendiente |
| F2 | `v0014_compras_esquema.py`: sentencias de subida 1 a 14 y de bajada 1 a 8 | TC-01 a TC-12 y TC-15 a TC-22, TC-28a | `tester-backend` · `desarrollador-sql` | `sonnet` · «regla de dinero o de límite» (§14.2): los invariantes 2 (`RN-07`) y 8 | `uv run --env-file ../.env alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` sobre la base local; `uv run pytest tests/test_tkt019_migracion.py tests/test_tkt019_restricciones.py`; mutantes `M-1` a `M-10` y `M-14` a `M-17` | Pendiente |
| F3 | `v0014_compras_esquema.py`: sentencias de subida 15 a 30 y de bajada 9 y 10 | TC-23 a TC-26 | `tester-backend` · `desarrollador-sql` | `sonnet` · «un disparador de inmutabilidad» y «los permisos de un rol» (§14.2) | `uv run pytest tests/test_tkt019_privilegios.py tests/test_tkt019_migracion.py`; mutantes `M-11` a `M-13` y `M-18` | Pendiente |
| F4 | `v0015_semilla_folios_de_compras.py`. **Actualización declarada** de `tests/test_tkt010_semilla_local.py::test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` (TC-B15) por `tester-backend`, citando este diseño en `impl.md`: `requisicion`, `requisicion_renglon`, `solicitud_autorizacion`, `orden_compra`, `orden_compra_renglon` y `reprogramacion_entrega` entran en `tablas_vacias`, y se añade la aserción de que `folio_consecutivo` tiene exactamente `[("ORDEN_COMPRA", 0), ("REQUISICION", 0)]` ordenado por serie. La afirmación sigue siendo «la siembra no escribe fuera de su alcance» | TC-13, TC-14, TC-27, TC-28b, TC-29 | `tester-backend` · `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt019_migracion.py tests/test_tkt019_restricciones.py tests/test_tkt010_semilla_local.py`; mutante `M-19`; después, **`uv run pytest` completo** en verde (`CA-R3`: la suite corre ya con la versión nueva de `dnspython`), `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` | Pendiente |
| F5 | Documentación de «Documentación afectada» | Sin prueba de `pytest`. Rojo: en `docs/03-modelo-datos.md` el bloque `ORDEN_COMPRA` del diagrama de §5 todavía contiene `enum estado` y §2 no nombra `solicitud_autorizacion.entidad_id` (se comprueba con `Grep`) | `desarrollador-sql` | `haiku` | Desde la raíz: `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py`; `Grep` de `enum estado "ABIERTA` en `docs/03-modelo-datos.md` sin resultados; `Grep` de `solicitud_autorizacion.entidad_id` con resultados en §2 y §13; `Grep` de `oc.estado IN` sin resultados en §15; `Grep` de `IN002` con resultados en §14 de `docs/03-modelo-datos.md`, en TKT-023 de `docs/05-tickets-trabajo.md`, en `.claude/skills/conv-sql-postgres/SKILL.md` y en `.claude/agents/desarrollador-sql.md`; `python tools/agentes_cursor.py --generar` y `python -m unittest discover -s tools/tests -v` en verde | Pendiente |

**Modelo:** `haiku` por omisión; `sonnet` solo en F2 y F3, por el disparador citado. Nunca `opus` en una fila de ejecución.

Notas de ejecución que no admiten otra lectura:

- **Roles.** Los datos se escriben con `conectar("aplicacion", base_de_prueba)`; el catálogo y las migraciones, con `conectar("migracion", …)`. Excepciones declaradas, para aislar un mecanismo del otro (modelo de datos §13): la serie desconocida de TC-14 se inserta con el rol de migración, porque el de aplicación ya no tiene `INSERT` sobre `folio_consecutivo`; y TC-28 inserta la solicitud con el rol de migración sobre `base_vacia`.
- **Fábricas.** `test_tkt019_restricciones.py` y `test_tkt019_privilegios.py` definen sus propias ayudas, sin importarse entre sí: `insertar(conexion, tabla, valores)` con `psycopg.sql.Identifier`, igual que `insertar` de `test_tkt029a_migracion.py`, y una función `fila_<tabla>(…, **cambios) -> dict[str, Any]` por tabla con estos valores válidos por omisión: requisición `EVALUADA` con `folio = f"REQ-{n:04d}"` único por llamada, `importe_solicitado = Decimal("8000.0000")` y `creado_en = actualizado_en = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)`; renglón de requisición con `cantidad = Decimal("10.0000")`, `costo_unitario_estimado = Decimal("800.0000")`, `importe = Decimal("8000.0000")`; orden con `folio = f"OC-{n:04d}"`, `proveedor_id = uuid.uuid4()` (no existe ningún proveedor: prueba la ausencia de clave foránea) e `importe = Decimal("8000.0000")`; renglón de orden con `cantidad_ordenada = Decimal("10.0000")`, `costo_unitario = Decimal("800.0000")`, `importe = Decimal("8000.0000")`, `fecha_compromiso = date(2026, 11, 20)` y sin `cantidad_recibida` ni `cantidad_excedente_autorizada` (decide el motor); solicitud `PENDIENTE` con `motivo = "EXCEDE_PRESUPUESTO"`, `entidad_tipo = "REQUISICION"`, `regla_negocio = "RN-03"`, `rol_autorizador = "DIRECCION_GENERAL"` y `contexto = psycopg.types.json.Jsonb({"disponible": "12000.0000"})`; reprogramación con `fecha_anterior = date(2026, 11, 20)`, `fecha_nueva = date(2026, 11, 27)`, `saldo_pendiente = Decimal("5.0000")`, `motivo = "El proveedor aplazó la entrega."`. Las claves foráneas salen de `datos_presupuesto` (`usuario()`, `obra()`, `tipo_partida()`, `insumo()`). Los importes se construyen siempre desde cadena.
- **Precondición del rojo.** Cada archivo tiene `exigir_revision(revision)` (recorre `walk_revisions()`, como `exigir_revision_nueva` de `test_tkt029a_migracion.py`) y `exigir_tabla(conexion, tabla)` (`to_regclass`). Así el rojo es un fallo de aserción con el motivo escrito, no un `ResolutionError` ni un `UndefinedTable`.
- **Rechazos.** Cada rechazo: `with pytest.raises(psycopg.Error) as error`, y después `error.value.sqlstate == <código>` y `error.value.diag.constraint_name == <nombre>`; en los `23502`, `error.value.diag.column_name == <columna>`. Después del rechazo, `count(*)` de la tabla no cambió. Cada caso abre su propia transacción: la conexión de `conectar` no queda en estado abortado entre casos parametrizados porque cada caso es un test.
- **Concurrencia determinista (TC-26).** Sin `sleep`. El método de `test_tkt017_congelado_concurrencia.py` y de TC-20 de TKT-029a: la transacción A (rol de aplicación) hace `UPDATE requisicion SET estado = 'EVALUADA', folio = 'REQ-9001' WHERE id = :r` y no confirma; el hilo B intenta `DELETE FROM requisicion_renglon WHERE requisicion_id = :r`; la prueba espera con `esperar_hasta` (de `herramientas.tiempo_de_prueba`) a que `pg_stat_activity` muestre a B con `wait_event_type = 'Lock'` y `cardinality(pg_blocking_pids(pid)) > 0`; A confirma; B falla con `IN002` y `constraint_name = 'trg_requisicion_renglon_borrado_solo_borrador'`, y el renglón sigue ahí. Se usan `Hilo` y `LIMITE_DE_HILO` de `herramientas.soporte_tkt017_entorno`, y todo hilo se libera en `finally`.
- **Fotografía.** `fotografia(conexion)` se copia de `test_tkt029a_migracion.py` sin cambios; `TABLAS_COMPRAS` es la tupla de las siete tablas y `FUNCIONES_COMPRAS` la de las dos funciones. «Lo anterior» de TC-03 es la fotografía de `0013` contra la de la cabeza **sin** las filas cuya tabla (primer campo) está en `TABLAS_COMPRAS`, y sin las funciones de `FUNCIONES_COMPRAS`.

## Plan de pruebas

Ninguna prueba lleva el nombre `test_hduXXX_escYY`: el ticket no prueba escenarios de historia (spec, «Historia de usuario»).

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_tkt019_car1_0014_cuelga_de_0013_y_la_cabeza_es_unica`: una sola cabeza y `0014.down_revision == "0013"`. Sin base; no afirma cuál es la cabeza | regresión de invariante | `CA-R1` | — |
| TC-02 | `test_tkt019_car1_sube_baja_y_vuelve_a_subir`: sobre `base_vacia`, `migrar(…, "0013")` (fotografía A, sin ninguna tabla de compras); `migrar(…, "0014")` (B, con las siete); `migrar(…, "0013", "downgrade")` (C == A y ninguna fila de `TABLAS_COMPRAS` en columnas, restricciones, índices, privilegios ni disparadores); `migrar(…, "0014")` (D == B) | regresión de invariante | `CA-R1` | — |
| TC-03 | `test_tkt019_car2_el_esquema_anterior_no_cambia`: «lo anterior» de la fotografía de `0013` y de la de la cabeza son idénticos (nota «Fotografía») | regresión de invariante | `CA-R2` | — |
| TC-04 | `test_tkt019_ca01_tablas_columnas_restricciones_e_indices`: por tabla, las columnas en orden con tipo, precisión, escala, nulabilidad y valor por omisión exactos de «Infraestructura y esquema» (`numeric` 18,4 en importes, 14,4 en precios y cantidades; `date` en `fecha_compromiso`, `fecha_anterior` y `fecha_nueva`; `timestamp with time zone` en los instantes; `bigint` en `ultimo`; `jsonb` en `contexto`; `DEFAULT 0` en `cantidad_recibida`, `cantidad_excedente_autorizada` y `ultimo`); el mapa exacto `conname → contype` de cada tabla; cada `FOREIGN KEY` con su tabla destino y `ON DELETE RESTRICT`; ninguna columna `USER-DEFINED` (ningún `ENUM`); el conjunto exacto de índices de las siete tablas con su `indexdef` (el único parcial con `WHERE (cancelada_en IS NULL)`) | feliz | `CA-1`, `CA-10` | — |
| TC-05 | `test_tkt019_ca01_borrar_una_obra_con_requisicion_responde_23001`: con el rol de aplicación, `DELETE FROM obra` con una requisición colgada → `23001` `fk_requisicion_obra_id`; la obra sigue | **rechazo** | `CA-1` | — |
| TC-06 | `test_tkt019_ca02_el_motor_exige_el_centro_de_costos` (parametrizada): `requisicion.obra_id` nulo, `requisicion.tipo_partida_id` nulo y `orden_compra.obra_id` nulo → `23502` con `column_name` exacto. Controles positivos: la requisición y la orden con los dos valores entran | **rechazo** | `CA-2` | — |
| TC-07 | `test_tkt019_ca03_estados_de_la_requisicion` (parametrizada): los siete estados entran (`BORRADOR` con `folio` nulo; `CANCELADA` con motivo); `"SIN_EFECTO"` → `23514` `ck_requisicion_estado`; estado nulo → `23502` `column_name = "estado"`; `"evaluada"` en minúsculas → `23514` `ck_requisicion_estado` | **rechazo** · feliz | `CA-3` | — |
| TC-08 | `test_tkt019_ca03_folio_motivo_y_regla_segun_estado` (parametrizada): `EVALUADA` sin folio → `23514` `ck_requisicion_folio_fuera_de_borrador` `(aprobada · D-15)`; `CANCELADA` sin motivo → `23514` `ck_requisicion_cancelacion_con_motivo` `(aprobada · D-16)`; `regla_bloqueo` con un valor distinto de `RN-03`, por ejemplo `"REGLA"` → `23514` `ck_requisicion_regla_bloqueo`. Controles: `BORRADOR` sin folio, `CANCELADA` con motivo, `BLOQUEADA` con `regla_bloqueo = "RN-03"` y `EVALUADA` con `regla_bloqueo` nulo entran | **rechazo** | `CA-3` | — |
| TC-09 | `test_tkt019_ca04_ninguna_cifra_es_negativa` (parametrizada por tabla y columna): `-0.0001` en `requisicion.importe_solicitado` e `importe_excedente`, `requisicion_renglon.cantidad`, `costo_unitario_estimado` e `importe`, `orden_compra.importe`, `orden_compra_renglon.cantidad_ordenada`, `cantidad_recibida`, `cantidad_excedente_autorizada`, `costo_unitario` e `importe`, y `reprogramacion_entrega.saldo_pendiente` → `23514` con su `ck_…_no_negativo` (el del excedente autorizado, `ck_orden_compra_renglon_excedente_autorizado_no_negativo`). Control positivo por columna: `Decimal("0.0000")` entra | **rechazo** · borde | `CA-4` | — |
| TC-10 | `test_tkt019_ca04_el_disponible_admite_negativos`: `importe_disponible = Decimal("-1500.0000")` y `cantidad_disponible = Decimal("-3.5000")` entran y se leen iguales (decisión de la persona dueña) | feliz · borde | `CA-4` | — |
| TC-11 | `test_tkt019_ca04_cantidad_fuera_de_escala`: `requisicion_renglon.cantidad = Decimal("10000000000.0000")` → `22003`; `Decimal("9999999999.9999")` entra; `Decimal("-0.00004")` se guarda como `0.0000` (la escala redondea: lo documenta y lo deja a la validación del API de TKT-021) | borde | `CA-4` | — |
| TC-12 | `test_tkt019_ca05_folio_unico`: dos requisiciones con el mismo folio → `23505` `uq_requisicion_folio`; dos órdenes con el mismo folio → `23505` `uq_orden_compra_folio`. Control: dos requisiciones `BORRADOR` con folio nulo entran | **rechazo** | `CA-5` | — |
| TC-13 | `test_tkt019_ca05_series_sembradas_y_bloqueables`: `0015` deja exactamente `ORDEN_COMPRA` y `REQUISICION` con `ultimo = 0`; con el rol de aplicación, en una transacción, `SELECT ultimo FROM folio_consecutivo WHERE serie = 'REQUISICION' FOR UPDATE` devuelve `(0,)` y `UPDATE … SET ultimo = ultimo + 1 … RETURNING ultimo` devuelve `(1,)` | feliz | `CA-5` | — |
| TC-14 | `test_tkt019_ca05_serie_desconocida_y_ultimo_negativo`: con el rol de migración, `INSERT` de la serie `ENTRADA_ALMACEN` → `23514` `ck_folio_consecutivo_serie`; con el de aplicación, `UPDATE … SET ultimo = -1` → `23514` `ck_folio_consecutivo_ultimo_no_negativo` e `INSERT` de cualquier serie → `42501` `(aprobada · D-17)` | **rechazo** | `CA-5`, `CA-11` | — |
| TC-15 | `test_tkt019_ca06_la_resolucion_exige_motivo_actor_y_momento` (parametrizada): `AUTORIZADA` y `RECHAZADA` sin `motivo_resolucion`, sin `resuelta_por_id` o sin `resuelta_en` → `23514` `ck_solicitud_autorizacion_resolucion_completa` `(aprobada · D-11)`; estado `"CANCELADA"` → `23514` `ck_solicitud_autorizacion_estado`. Controles: `PENDIENTE` sin nada de resolución entra; `AUTORIZADA` y `RECHAZADA` con los tres entran | **rechazo** | `CA-6` | — |
| TC-16 | `test_tkt019_ca07_excede_ordenado_apunta_a_su_renglon` (parametrizada): `EXCEDE_ORDENADO` sin `orden_compra_renglon_id`, sin `cantidad_excedente` o sin los dos → `23514` `ck_solicitud_autorizacion_excede_ordenado_con_renglon`; `EXCEDE_PRESUPUESTO` con renglón, con cantidad o con los dos → el mismo `23514`. Controles: `EXCEDE_ORDENADO` con los dos y `cantidad_excedente = Decimal("0.0001")` entra; `EXCEDE_PRESUPUESTO` sin ninguno entra | **rechazo** | `CA-7` | — |
| TC-17 | `test_tkt019_ca07_valores_cerrados_de_la_solicitud` (parametrizada): `motivo = "OTRO"` → `23514` `ck_solicitud_autorizacion_motivo`; `entidad_tipo = "requisicion"` (minúsculas, como la bitácora) → `23514` `ck_solicitud_autorizacion_entidad_tipo`; `regla_negocio = "RN3"` → `23514` `ck_solicitud_autorizacion_regla_negocio_formato`; `rol_autorizador = "GERENTE"` → `23503` `fk_solicitud_autorizacion_rol_autorizador`; `EXCEDE_ORDENADO` con `cantidad_excedente = Decimal("0.0000")` → `23514` `ck_solicitud_autorizacion_cantidad_excedente_positiva`; `contexto` nulo → `23502`. Controles: los cuatro motivos y las dos entidades entran | **rechazo** | `CA-7` | — |
| TC-18 | `test_tkt019_ca08_recibir_de_mas_solo_con_excedente_autorizado` (parametrizada, por `UPDATE` sobre un renglón con `cantidad_ordenada` 10): recién insertado, `cantidad_recibida` y `cantidad_excedente_autorizada` valen `0.0000`; recibida `10.0001` con excedente 0 → `23514` `ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado`; recibida `10.0000` entra; excedente 2 y recibida `12.0000` entra; excedente 2 y recibida `12.0001` → el mismo `23514`; excedente `-0.0001` con recibida 0 → `23514` `ck_orden_compra_renglon_excedente_autorizado_no_negativo` | **rechazo** · borde | `CA-8` | — |
| TC-19 | `test_tkt019_ca09_la_orden_sin_clave_al_proveedor_ni_estado`: en `pg_constraint` ninguna `FOREIGN KEY` de `orden_compra` cubre `proveedor_id`; `orden_compra` no tiene columna `estado` ni ninguna cuyo nombre contenga `cierre`; sí tiene `cancelada_en` y `motivo_cancelacion`; una orden con un `proveedor_id` que no existe entra | feliz | `CA-9` | — |
| TC-20 | `test_tkt019_ca09_cancelacion_con_motivo` (parametrizada): solo `cancelada_en` o solo `motivo_cancelacion` → `23514` `ck_orden_compra_cancelacion_con_motivo` `(aprobada · D-1)`. Controles: ninguno de los dos y los dos entran | **rechazo** | `CA-9` | — |
| TC-21 | `test_tkt019_ca09_una_orden_vigente_por_requisicion`: una segunda orden viva de la misma requisición → `23505` `uq_orden_compra_requisicion_id_vigente`; tras cancelar la primera (`UPDATE` con `cancelada_en` y motivo), la segunda entra `(aprobada · D-5)` | **rechazo** | `CA-9` | — |
| TC-22 | `test_tkt019_ca10_la_reprogramacion_exige_motivo` (parametrizada): `motivo` nulo → `23502` `column_name = "motivo"`; `""` y `"   "` → `23514` `ck_reprogramacion_entrega_motivo_no_vacio`. Control: la reprogramación completa entra y se lee igual | **rechazo** | `CA-10` | — |
| TC-23 | `test_tkt019_ca11_privilegios_exactos_por_rol`: por `aclexplode(relacl)`, los conjuntos exactos de la aplicación y de la lectura en cada una de las siete tablas, y ninguna fila para `PUBLIC` (`grantee = 0`); `has_table_privilege` de `TRUNCATE`, `REFERENCES`, `TRIGGER` y `MAINTAIN` es `false` para los dos roles en las siete | **rechazo** | `CA-11` | — |
| TC-24 | `test_tkt019_ca11_el_rol_de_aplicacion_no_borra_lo_permanente` (parametrizada): con el rol de aplicación, `DELETE` real sobre una fila de `solicitud_autorizacion`, `reprogramacion_entrega`, `orden_compra`, `orden_compra_renglon` y `folio_consecutivo` → `42501`; `UPDATE` sobre `reprogramacion_entrega` → `42501`; `TRUNCATE` de cada una de las siete → `42501`. La fila sigue idéntica (`SELECT t::text`) | **rechazo** | `CA-11` | — |
| TC-25 | `test_tkt019_ca11_solo_se_borra_un_borrador` (parametrizada por estado): un `BORRADOR` se borra con sus renglones (primero los renglones, después la requisición) y no queda nada; para cada uno de los seis estados restantes, `DELETE` del renglón → `IN002` `trg_requisicion_renglon_borrado_solo_borrador` y `DELETE` de la requisición sin renglones → `IN002` `trg_requisicion_borrado_solo_borrador`; la fila sigue `(aprobada · D-3)` | **rechazo** | `CA-11` | — |
| TC-26 | `test_tkt019_ca11_el_borrado_del_renglon_espera_al_cambio_de_estado`: el método de la nota «Concurrencia determinista» | **concurrencia** | `CA-11` | — |
| TC-27 | Actualización declarada de TC-B15 de TKT-010 (fila F4): la siembra local deja vacías las seis tablas de documentos y `folio_consecutivo` con sus dos filas en cero | regresión de invariante | `CA-R2` | — |
| TC-28 | `test_tkt019_car1_las_bajadas_se_niegan_con_datos_permanentes`: (a, fila F2) en `base_vacia` en `0014`, con una solicitud insertada por el rol de migración, `migrar(…, "0013", "downgrade")` falla con el mensaje de `RN-04` y la versión sigue en `0014`; (b, fila F4) en `0015` con `ultimo = 1` en `REQUISICION`, `migrar(…, "0014", "downgrade")` falla y la versión sigue en `0015`. Control: sin datos, las dos bajadas pasan (lo cubren TC-02 y TC-29) `(aprobada · D-18)` | **rechazo** | `CA-R1` | — |
| TC-29 | `test_tkt019_car1_0015_cuelga_de_0014_y_sube_baja_y_vuelve_a_subir`: `0015.down_revision == "0014"` y una sola cabeza; `migrar(…, "0014")` deja `folio_consecutivo` vacío; `"0015"` lo siembra; bajar a `"0014"` lo vacía; volver a subir lo siembra igual | regresión de invariante | `CA-R1` | — |
| TC-D1 | El filtro `tools/severidad_pip_audit.py` sale con 0 tras subir `dnspython` (comando de F1) | **rechazo** (antes del cambio, sale con 1) | `CA-12` | — |
| TC-D2 | Solo si no hay versión corregida: sin la excepción el filtro sale con 1; con `--ignore-vuln GHSA-vvf4-9x63-8xvv` y su comentario sale con 0, y la orden de `pip-audit` no tiene otro `--ignore-vuln` | **rechazo** | `CA-13` | — |
| TC-D3 | `git diff -- backend/uv.lock` solo cambia el bloque de `dnspython`; `uv sync --locked` funciona; la suite completa de F4 en verde | regresión de invariante | `CA-R3` | — |

**Mutación** en las rutas críticas (invariantes 1, 2, 8 y 9, y el borrado de la requisición, que protege el `consumido`). Cada mutante se aplica a mano sobre la migración, se corre la prueba y se deshace; `impl.md` registra la tabla «mutante · test que cae».

| Mutante | Cambio | Test que debe ponerse rojo |
|---|---|---|
| `M-1` | Se quita `NOT NULL` de `requisicion.tipo_partida_id` (invariante 1) | TC-06 y TC-04 |
| `M-2` | Se quita `NOT NULL` de `orden_compra.obra_id` (invariante 1) | TC-06 y TC-04 |
| `M-3` | `<=` pasa a `<` en `ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado` (invariante 2) | TC-18 (recibida 10 con excedente 0 y recibida 12 con excedente 2) |
| `M-4` | Se quita `+ cantidad_excedente_autorizada` del mismo `CHECK` (invariante 2) | TC-18 (recibida 12 con excedente 2) |
| `M-5` | Se quita `ck_orden_compra_renglon_excedente_autorizado_no_negativo` (invariante 2) | TC-18 (excedente negativo) y TC-09 |
| `M-6` | `>= 0` pasa a `> 0` en `ck_requisicion_importe_solicitado_no_negativo` (invariante 8) | TC-09 (control en cero) |
| `M-7` | Se quita `ck_orden_compra_renglon_costo_unitario_no_negativo` (invariante 8) | TC-09 y TC-04 |
| `M-8` | Se añade `CHECK (importe_disponible >= 0)` a `requisicion` (contra la excepción decidida) | TC-10 y TC-04 |
| `M-9` | `ck_solicitud_autorizacion_resolucion_completa` solo exige `motivo_resolucion` (invariante 9) | TC-15 (sin actor y sin momento) |
| `M-10` | El mismo `CHECK` pasa a `estado <> 'RECHAZADA' OR …` (invariante 9) | TC-15 (`AUTORIZADA` sin motivo) |
| `M-11` | Se quita `trg_requisicion_borrado_solo_borrador` | TC-25 |
| `M-12` | Se quita `trg_requisicion_renglon_borrado_solo_borrador` | TC-25 |
| `M-13` | Se quita `FOR SHARE` de `compras_proteger_borrado_de_renglon` | TC-26 (B no espera y borra el renglón) |
| `M-14` | `ck_solicitud_autorizacion_excede_ordenado_con_renglon` pierde la segunda rama (solo un sentido) | TC-16 (`EXCEDE_PRESUPUESTO` con renglón) |
| `M-15` | `uq_orden_compra_requisicion_id_vigente` sin `WHERE` | TC-21 (la orden tras cancelar) y TC-04 |
| `M-16` | `ck_requisicion_folio_fuera_de_borrador` se quita | TC-08 |
| `M-17` | `ck_orden_compra_cancelacion_con_motivo` pasa a `cancelada_en IS NULL OR motivo_cancelacion IS NOT NULL` (un solo sentido) | TC-20 (motivo sin cancelación) |
| `M-18` | Se quita `REVOKE DELETE ON solicitud_autorizacion` | TC-23 y TC-24 |
| `M-19` | `0015` siembra solo `REQUISICION` | TC-13, TC-27 y TC-29 |

## Entradas hostiles y datos inesperados

El ticket no abre ninguna ruta: estas son las entradas que pueden llegar al motor por cualquier vía y lo que el esquema hace con ellas.

| Campo | Qué se rechaza | Código | Test |
|---|---|---|---|
| `obra_id`, `tipo_partida_id`, `estado`, `contexto`, `motivo` de la reprogramación | Nulo | `23502` | TC-06, TC-07, TC-17, TC-22 |
| Importes, precios y cantidades | `-0.0001`; el cero se admite | `23514` | TC-09 |
| Cantidades `numeric(14,4)` | Más de diez dígitos enteros | `22003` | TC-11 |
| Cantidades e importes | Más de cuatro decimales: el motor **redondea** (`-0.00004` queda en `0.0000`) y no rechaza. Lo rechaza el API de TKT-021 y siguientes, como ya hace `ImporteNoNegativo` | — (documentado) | TC-11 |
| `estado`, `motivo`, `entidad_tipo` | Valor fuera del conjunto, incluidas las minúsculas (`"evaluada"`, `"requisicion"`) | `23514` | TC-07, TC-17 |
| `regla_negocio`, `regla_bloqueo` | Forma distinta de `RN-NN`; `regla_bloqueo` distinto de `RN-03` | `23514` | TC-08, TC-17 |
| `rol_autorizador` | Clave que no existe en `rol` | `23503` | TC-17 |
| `motivo` de la reprogramación | Vacío o solo espacios | `23514` | TC-22 |
| `cantidad_excedente` | Cero | `23514` | TC-17 |
| `folio` | Repetido; nulo fuera de `BORRADOR` | `23505`, `23514` | TC-08, TC-12 |
| `serie` | Fuera de las dos series | `23514` | TC-14 |
| Texto con `NUL` | `psycopg` lo rechaza antes de llegar al motor; el tope de longitud y el `NUL` son del API de cada ticket que escriba (TKT-007, TKT-017) | — | — |

Comprobaciones que el diseño afirma y aún no se ejecutaron; cada una tiene su fila:

| # | Afirmación | Evidencia | Fila que la comprueba |
|---|---|---|---|
| E-1 | `dnspython` 2.9.2 corrige `GHSA-vvf4-9x63-8xvv` | **Sin ejecutar**: solo se comprobó que `uv lock --dry-run --upgrade-package dnspython` propone `2.9.0 → 2.9.2` | F1 (TC-D1); si es falso, TC-D2 |
| E-2 | `pip-audit --ignore-vuln <ID>` omite el hallazgo del informe JSON y el filtro sale con 0 | **Sin ejecutar** | F1 (TC-D2), solo si se aplica `CA-13` |
| E-3 | `pip-audit` corre en local con la misma orden que el pipeline (necesita red) | **Sin ejecutar** | F1 |
| E-4 | Un `23502` trae `diag.column_name` | Comportamiento documentado de PostgreSQL; **sin ejecutar** aquí | F2 (TC-06) |
| E-5 | Un `23505` sobre un índice único parcial trae como `constraint_name` el nombre del índice | Comportamiento documentado de PostgreSQL; **sin ejecutar** aquí | F2 (TC-21) |
| E-6 | `RAISE … CONSTRAINT = TG_NAME` llega como `diag.constraint_name`, y el `FOR SHARE` dentro de un disparador `SECURITY INVOKER` funciona con el `UPDATE` del rol de aplicación | **Ejecutado en el repositorio** para `IN001` (`0007`, TKT-011b) | F3 (TC-25, TC-26) |
| E-7 | Una clave foránea hacia `rol (clave)` se admite porque `uq_rol_clave` existe | Regla de PostgreSQL (la columna destino debe tener `UNIQUE` o `PRIMARY KEY`); **sin ejecutar** | F2 (TC-04, TC-17) |
| E-8 | `numeric(14,4)` redondea `-0.00004` a `0.0000` | Comportamiento documentado de PostgreSQL; **sin ejecutar** | F2 (TC-11) |
| E-9 | Bajar `0015` y `0014` desde la cabeza no rompe las suites que bajan desde ella: `test_identidad_migracion_ciclo.py`, `test_tkt059_migracion.py`, `test_tkt006_esquema.py:153-171`, `test_tkt007_esquema.py:534-580`, `test_tkt010_migracion.py:221-364`, `test_tkt017_migracion.py:123-152` y `test_tkt072_migracion.py:324-334`. Las tablas de compras están vacías, los contadores en cero y las bajadas no se niegan | **Sin ejecutar** | F4 (suite completa) |

## Impacto

Resultado de `revisor-impacto` (2026-11-14): **diseño incompleto, sin frontera cruzada**, con 16 contratos de `lint-imports` en verde («16 kept»). Sus siete hallazgos (H-1 a H-7) ya están incorporados en este diseño y en la spec, sin reabrir ninguna decisión.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Migraciones `0014` y `0015` | Toda suite que construye el esquema con `alembic upgrade head` (la plantilla `plantilla_migrada` de `conftest.py`). Leen la cabeza del guion, sin cadena literal: `test_tkt059_migracion.py:102-112`, `test_tkt010_migracion.py:105-109`, `test_tkt011_migracion_linea_base.py:188-193`, `test_tkt007_esquema.py:210-214` y `test_identidad_migracion*.py`. Bajan desde la cabeza las suites de `E-9` | Bajo: tablas nuevas, sin cambios en las existentes; las bajadas no se niegan sin datos | TC-03 y la suite completa en F4 |
| `tests/test_tkt010_semilla_local.py:1336-1383` (TC-B15, `tablas_vacias` en 1353-1362) | TKT-010 | Seguro: no se pone en rojo solo, pero `CA-R2` exige ampliar su lista | Actualización declarada en F4 |
| Fotografías de catálogo (`test_tkt029a_migracion.py:105-153`) | TKT-029a | Ninguno: comparan revisiones concretas (`0012` y `0013`) sobre `base_vacia` | F4 corre la suite completa |
| Privilegios por omisión | `test_tkt011_regresion.py:395-401` (la lectura no tiene nada más que `SELECT` en todo `public`) y `test_identidad_privilegios_por_omision.py:17,56-70` | Ninguno: las siete tablas los cumplen por los privilegios por omisión de `0001`; los `REVOKE` solo quitan al rol de aplicación | F4 corre la suite completa |
| Otras pruebas de privilegios (`test_identidad_permisos_tablas.py`, `test_tkt029a_migracion.py`) | TKT-003, TKT-029a | Ninguno: comparan solo sus tablas | F4 |
| `fk_solicitud_autorizacion_rol_autorizador` hacia `rol (clave)`, con `ON DELETE RESTRICT` y sin `ON UPDATE` `(aprobada · D-13)` | `0002` (siembra de roles) y cualquier cambio futuro de la `clave` de un rol | Bajo: la bajada de `0002` se detendría con solicitudes, pero `0014` baja antes. Cambiar la `clave` de un rol queda bloqueado en cuanto exista una solicitud que la cite; las claves de `0002` son fijas y el código busca por ellas, así que hoy no es un riesgo | Si algún día se renombra un rol, su ticket decide entre `ON UPDATE CASCADE` y migrar las solicitudes |
| `SQLSTATE` `IN002` de los disparadores `(aprobada · D-3)` | TKT-021 o TKT-023, el primero que borre un borrador | Medio: sin traducción, un `IN002` que llegue por una carrera saldría como `500` | Criterio nuevo en `docs/05` (F5): `IN002` se traduce a `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`. Lo escribe el traductor propio de `compras`; el de `presupuesto` (`presupuesto/aplicacion/traduccion_motor.py:38-66`, que solo conoce `IN001`) no se reutiliza, porque `compras` solo habla con otro módulo por su interfaz publicada |
| `backend/uv.lock` | Todo el backend; compuerta del PR | Bajo: una dependencia transitiva de `email-validator` | TC-D3 y la suite completa; el resumen de fusión nombra la compuerta |
| `.github/workflows/ci.yml` (solo con `CA-13`) | Trabajo «Dependencias»; compuerta del PR | Medio: una excepción mal escrita ocultaría otras vulnerabilidades | TC-D2 exige un solo `--ignore-vuln`; el resumen de fusión nombra la compuerta |
| `requisicion.folio` nulable `(aprobada · D-15)` | TKT-021, TKT-023 y el borrador del API (`Requisicion.folio` requerido) | Medio: el contrato publica un folio no nulo también en borrador | Aviso escrito en `D-15` para el ticket que decida cuándo se numera |
| `comprometido` de §15 con `cancelada_en IS NULL` `(aprobada · D-1)` | TKT-021, TKT-039 | Medio: una consulta escrita con el texto viejo filtraría por una columna que no existe | La consulta de §15 y TKT-021 en `docs/05` se reconcilian en F5 |

**Fronteras entre módulos:** No. El ticket no escribe Python en `cimenta/`. Las claves foráneas cruzan solo hacia módulos ancestros de `compras`, lo que el grafo permite (`presupuesto`: `obra`, `tipo_partida`, `insumo`; `identidad`: `usuario`, `rol`). Ninguna apunta a `archivo`, `bitacora` ni `proveedor`: `orden_compra.proveedor_id` no tiene clave foránea y `entidad_id` es lógica. `revisor-impacto` corrió `lint-imports` con 16 contratos en verde; F4 lo repite.

## Documentación afectada

| Documento | Qué cambia |
|---|---|
| `docs/03-modelo-datos.md` §1 | El principio «el estado derivable se deriva» añade «salvo la cancelación de la orden, que se guarda en `cancelada_en` porque no sale de ninguna cantidad» `(aprobada · D-1)` |
| `docs/03-modelo-datos.md` §2 | La lista cerrada de referencias sin clave foránea añade `solicitud_autorizacion.entidad_id`, polimórfica (`REQUISICION` u `ORDEN_COMPRA`) `(aprobada · D-2)` |
| `docs/03-modelo-datos.md` §5 | Diagrama: `ORDEN_COMPRA` pierde `enum estado` y gana `timestamptz cancelada_en` y `creado_en`; `REQUISICION` gana `observaciones`, `creado_en` y `actualizado_en`, y `folio` pasa a «UK · nulo solo en BORRADOR»; `SOLICITUD_AUTORIZACION` gana `obra_id FK`, `creado_en`, `entidad_tipo` con los valores `REQUISICION` u `ORDEN_COMPRA` y `rol_autorizador FK`; `ORDEN_COMPRA_RENGLON.fecha_compromiso` «NOT NULL · vigente». Prosa nueva: el estado de la orden se deriva y solo la cancelación se guarda; la excepción del disponible al invariante 8; el borrado de un borrador y sus disparadores (con `IN002`); los privilegios por tabla de `D-17`; lo que se deriva y no lleva columna (`D-9`) |
| `docs/03-modelo-datos.md` §13 | Invariante 8: «salvo `importe_disponible` y `cantidad_disponible`, cifras del momento de evaluar que pueden ser negativas», y la excepción de nombre `ck_orden_compra_renglon_excedente_autorizado_no_negativo`, que se aparta de `ck_<tabla>_<columna>_no_negativo` porque el nombre completo pasaría del límite de 63 caracteres. Invariante 9: el mecanismo pasa al `CHECK` completo de `D-11`. La lista cerrada de la prosa añade `solicitud_autorizacion.entidad_id`. La nota «el invariante 14 … es el único que necesita un disparador» deja de ser cierta con `D-3` opción B y se reescribe nombrando los dos disparadores de `compras`, que protegen estructura sin numerarse como invariante (así no cambian los «39 invariantes» de `CLAUDE.md`) |
| `docs/03-modelo-datos.md` §14 | Requisición: el diagrama añade `BORRADOR --> [*]: se elimina (solo en BORRADOR; lo exige el disparador con SQLSTATE IN002)` `(aprobada · D-3, opción B)`. Orden de compra: `CANCELADA` es el único estado persistido, en `cancelada_en` |
| `docs/03-modelo-datos.md` §15 | La CTE `comprometido` cambia `oc.estado IN ('ABIERTA','PARCIAL')` por `oc.cancelada_en IS NULL`, con el comentario de por qué basta; la tabla de índices de `orden_compra_renglon` pasa a `(orden_compra_id)` completo y añade los índices de `D-7` |
| `docs/glosario.md` línea 125 | El texto de `D-14` |
| `docs/05-tickets-trabajo.md` TKT-019 | Criterios técnicos reconciliados: siete tablas (con `reprogramacion_entrega`), `costo_unitario_estimado` en el renglón de requisición, `cancelada_en` de la orden, migraciones `0014` y `0015`, índices, privilegios y disparadores, y el bump de `dnspython` |
| `docs/05-tickets-trabajo.md` TKT-021 | El criterio del `comprometido` añade «sin columna de estado: las órdenes vivas son las de `cancelada_en IS NULL`» y el aviso de `D-15` sobre cuándo se numera |
| `docs/05-tickets-trabajo.md` TKT-023 | Criterio nuevo `(aprobada · D-3, opción B)`: el `SQLSTATE` `IN002` de `trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador` se traduce a `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` en el traductor propio de `compras` (lo escribe TKT-023, o TKT-021 si llega antes). El de `presupuesto` (`traduccion_motor.py:38-66`, solo `IN001`) no se reutiliza: `compras` no puede importarlo |
| `sdd/tickets/tkt-019/spec.md` | `CA-R1`: «`0014` cuelga de `0013` y `0015` de `0014`; hay una sola cabeza, `0015`» `(aprobada · D-8)`. `CA-11`: los privilegios exactos de `D-17` y el rechazo `IN002` de los disparadores de `D-3`. **Ya aplicado** con este diseño |
| `.claude/skills/conv-sql-postgres/SKILL.md` §1 | Fila nueva en la tabla de mecanismos: «Una requisición solo se borra en `BORRADOR` → disparadores `trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador`, `SQLSTATE` `IN002`», con la aclaración de que protegen estructura —lo que ya consume del presupuesto no desaparece por un borrado, como la copia congelada del invariante 14— y no calculan ninguna regla: el estado lo decide el caso de uso `(aprobada · D-3, opción B)` |
| `.claude/agents/desarrollador-sql.md` líneas 32 y 37 | La misma fila en la tabla «El esquema sostiene los invariantes» (línea 32) y, en la línea 37, «Los disparadores protegen **estructura**, no implementan reglas» gana el ejemplo de la requisición como protección de estructura. Tras editarlo, `python tools/agentes_cursor.py --generar` regenera `.cursor/agents/` y `python -m unittest discover -s tools/tests -v` sigue en verde |
| `.github/workflows/ci.yml` | Solo con `CA-13`: el comentario de excepciones vigentes |
| `sdd/tickets/tkt-019/_index.md` | Enlace a este diseño, estado y las decisiones aprobadas |
| `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/` | Conteo de ADR de 43 a 44 en los tres índices, y el ADR nuevo `20261115-disparadores-de-borrado-en-compras.md` con su fila en `docs/adr/README.md` (añadido en la revisión, por decisión de la persona dueña) |
| `docs/02-arquitectura.md` §8.2 | Diagramas de recepción: el estado de la orden se deriva de las cantidades y no se escribe con un `UPDATE` (hallazgo de `auditor-docs` en la revisión) |
| `docs/api/openapi.yaml` | Sin cambios. `EstadoOrdenCompra` ya dice «derivado de las cantidades, salvo `CANCELADA`». El folio nulable en borrador (`D-15`) es un aviso para TKT-023, no un cambio de este ticket |

## ¿Merece ADR?

Sí, uno: el de `D-3`. El diseño original lo descartó porque el mecanismo reutiliza el de [ADR-031](../../../docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md), pero `auditor-docs` observó en la revisión que `D-3` descartó una alternativa real (revocar `DELETE` y cancelar el borrador) y cambia una convención transversal de `conv-sql-postgres`. La persona dueña decidió el 2026-11-15 crearlo: [el ADR de las requisiciones que solo se borran en borrador](../../../docs/adr/20261115-disparadores-de-borrado-en-compras.md), con su fila en el índice y el conteo de ADR en 44. Las demás decisiones ya tienen el suyo: catálogos cerrados por `CHECK` ([ADR-030](../../../docs/adr/20261101-catalogos-cerrados-por-check.md)) y folios sin secuencia y estado derivado (modelo de datos §1 y §5).

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Con `D-3` opción B, borrar un borrador que ya tuviera folio dejaría un hueco, contra «los folios no tienen huecos» | `D-15`: el folio es nulable en `BORRADOR` y obligatorio fuera de él; cuándo se numera lo decide TKT-021 o TKT-023, con el aviso del contrato |
| 2 | Alta | El disparador del renglón lee el estado sin bloquear: una transacción que pasa la requisición a `EVALUADA` mientras otra borra sus renglones dejaría una requisición evaluada sin renglones | `FOR SHARE` sobre la requisición, como el invariante 14; TC-26 lo prueba con dos transacciones y `M-13` demuestra que sin él la carrera pasa |
| 3 | Media | ¿Un disparador que decide por estado es lógica de negocio en el esquema? La convención dice que los disparadores nunca implementan reglas de negocio (`conv-sql-postgres` §1, `desarrollador-sql.md:37`) | No calcula ninguna regla: protege una propiedad estructural (lo que consume no desaparece), como el invariante 14. El caso de uso sigue decidiendo y respondiendo el `409`; el disparador solo detiene otra vía. **La tensión queda expuesta al gate** con `D-3`: con la opción B se documenta en la skill y en el agente (ver «Documentación afectada»); con la opción A no hace falta nada de esto |
| 4 | Media | `numeric(14,4)` redondea en silencio un quinto decimal: `-0.00004` entra como cero y el `CHECK` no lo ve | Documentado y probado en TC-11; el rechazo de decimales de más es del API (ya lo hace `ImporteNoNegativo` en TKT-017 y TKT-029a) |
| 5 | Media | La orden guarda su propia `obra_id` y podría no coincidir con la de su requisición | Fuera del Must: TKT-030 la copia de la requisición. Queda en «Riesgos»; una clave compuesta `(requisicion_id, obra_id)` es el remedio si se quiere en el motor |
| 6 | Media | Un `CHECK` de un solo sentido en `EXCEDE_ORDENADO` dejaría colgar un renglón de una solicitud de otro motivo | El `CHECK` es de doble sentido; TC-16 prueba los dos y `M-14` lo vigila |
| 7 | Media | Quitar `INSERT` sobre `folio_consecutivo` al rol de aplicación haría que TC-14 «pase» por el privilegio y no por el `CHECK` de la serie | La serie desconocida se inserta con el rol de migración, que sí tiene el privilegio, y el `42501` del rol de aplicación es otro caso; como la prueba del invariante 14 (modelo de datos §13) |
| 8 | Baja | `motivo_resolucion` y `motivo_cancelacion` admiten cadena vacía, a diferencia del motivo de la reprogramación | El Must solo pide no nulo (invariante 9, `CA-6`); el vacío lo rechaza el API con `MotivoObligatorio` (`minLength: 1`). Si se quiere en el motor, es un `btrim(...) <> ''` por columna en su ticket |
| 9 | Baja | La fotografía de TC-03 podría ocultar un cambio en una tabla vieja si el filtro por `TABLAS_COMPRAS` fuera demasiado ancho | El filtro es por igualdad del primer campo con los siete nombres exactos, no por prefijo |
| 10 | Media | El comentario de `ci.yml` de `D-19` escribiría el nombre completo de la persona dueña en un archivo de un repositorio público, y quedaría como firma permanente de una decisión de riesgo | Pregunta para el gate: se firma con el nombre de usuario de git, con el nombre completo o solo con «la persona dueña del proyecto». Recomiendo la última, porque lo que importa es la fecha y el motivo, y el nombre ya consta en el historial del PR |
| 11 | Media | `F1` depende de la red (`uv lock` y `pip-audit` consultan índices y OSV): si falla la red, el rojo y el verde de la fila no son reproducibles y se podría concluir mal que no hay versión corregida | El diseño distingue ya el código 2 del filtro (informe ausente o ilegible) del 1 (hallazgo); se añade que un fallo de red no cuenta como «no hay versión corregida»: se repite la corrida antes de aplicar `CA-13` |
| 12 | Baja | El diseño pasa de dos migraciones por separar semilla y esquema, y con ello la cabeza deja de ser `0014`, como decían la spec y TKT-029a (`impl.md` reservó `0014` para TKT-019, y TKT-029b o cualquiera que se ejecute en paralelo tomaría `0016`) | Aceptada: `D-8` lo declara y `CA-R1` ya se corrigió; la alternativa de una sola migración queda en la columna derecha |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| `dnspython` 2.9.2 no corrige el aviso (`E-1`) | Media | Medio | `CA-13` con la excepción decidida y fechada `(aprobada · D-19)` |
| La corrección existe pero exige subir `email-validator` u otra dependencia | Baja | Medio | F1 se detiene y escala: el ticket no sube otras dependencias |
| La persona dueña elige `D-3` opción A | Media | Medio | El diseño ya escribe qué se quita; el cambio del contrato y de HDU-002 esc. 2 sería un ticket aparte, porque sale del alcance de TKT-019 |
| `D-15` choca con el `folio` requerido del borrador del API en `BORRADOR` | Media | Bajo | Aviso para TKT-021 y TKT-023; el esquema admite las dos políticas |
| Un `IN002` sin traducir sale como `500` en el primer ticket que borre borradores | Media | Medio | Criterio en `docs/05` para TKT-021 o TKT-023: traducción a `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` en el traductor propio de `compras` |
| Cambiar la `clave` de un rol citado por una solicitud queda bloqueado (`ON DELETE RESTRICT`, sin `ON UPDATE`) | Baja | Bajo | Hoy no aplica: las claves de `0002` son fijas. Lo decide el ticket que algún día renombre un rol |
| Una orden con obra distinta de la de su requisición | Baja | Medio | TKT-030 copia la obra; si la persona dueña lo quiere en el motor, una clave compuesta en su propio ticket |
| `pip-audit` no corre en local (sin red o sin la herramienta) | Media | Bajo | La comprobación definitiva es la del pipeline en `/sdd-completar` (`CA-12`) |
| La prueba de concurrencia TC-26 queda frágil | Baja | Medio | Sincronización por `pg_blocking_pids`, sin `sleep`; el mismo método ya estable en TKT-017 y TKT-029a |

## Ajustes de la ejecución

Se llena durante `/sdd-ejecutar` y `/sdd-revisar`, con la decisión de la persona dueña cuando el ajuste no estaba escrito en este diseño. Vacío mientras no haya ninguno.
