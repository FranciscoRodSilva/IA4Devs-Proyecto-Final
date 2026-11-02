# Design · TKT-011 · Esquema y migraciones del módulo presupuesto

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

El ticket crea solo esquema: diecinueve tablas del módulo `presupuesto`, sus restricciones con nombre, dos funciones de disparador que imponen el invariante 14 y el reparto de privilegios por rol, sin modelos ORM, sin casos de uso y sin datos. Todo lo que la base puede sostener lo sostiene la base: los conjuntos cerrados y los rangos son `CHECK` con nombre, la unicidad es `UNIQUE` o índice único parcial, y la inmutabilidad de la línea base la imponen dos disparadores `BEFORE … FOR EACH ROW` que rechazan con un `SQLSTATE` propio, `IN001`, y un mensaje que empieza por `RN-01:`. El privilegio mínimo se obtiene revocando sobre los privilegios por omisión de la migración `0001`, nunca concediendo tabla por tabla.

El orden suma unas 2,175 líneas (unas 595 de migración y documentación, y unas 1,580 de pruebas), más del triple del tope de unas 400 por cambio: es la **condición de parada 3**. Se recomienda partir el ticket en dos tickets hermanos con un PR cada uno, igual que TKT-062: **TKT-011a** (migración `0006`, estructura y catálogos) y **TKT-011b** (migración `0007`, línea base, control, importación, disparadores y permisos). Este diseño cubre los dos y numera sus filas `A` y `B`.

## Partición propuesta (condición de parada 3)

| Ticket | Musts | Contenido | Migración | Líneas estimadas | Depende de | Filas |
|---|---|---|---|---|---|---|
| TKT-011a | `M1`, `M4` en su parte, `M7` en su parte, `M8` en su parte, `S1` en su parte | `empresa`, `obra`, `nivel`, `area`, `tipo_partida`, `partida`, `concepto`, `insumo`, `precio_insumo`, `apu`, `apu_insumo`, `apu_cargo` | `0006`, cuelga de `0005` | ~965 (≈ 215 de migración, ≈ 70 de documentación, ≈ 680 de pruebas) | TKT-003 (archivado) | A0 a A7 |
| TKT-011b | `M2`, `M3`, `M5`, `M6`, `M4`, `M7`, `M8` y `S1` en su parte | `linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error`, `rendimiento_observado`, los dos disparadores, la revocación y la bajada con guarda | `0007`, cuelga de `0006` | ~1,210 (≈ 220 de migración, ≈ 90 de documentación, ≈ 900 de pruebas) | TKT-011a | B1 a B8 |

**El orden de fusión es fijo: a → b.** La rama de TKT-011b se crea desde `Produccion` con TKT-011a ya fusionado. TKT-011 queda como ticket paraguas: conserva la spec y este diseño, y se cierra cuando se cierran los dos. Por las claves foráneas del propio diseño, TKT-010, TKT-019, TKT-042, TKT-046 y TKT-049 solo necesitan TKT-011a (apuntan a `empresa`, `obra`, `area`, `tipo_partida` o `insumo`); TKT-012 y TKT-013 a TKT-018 y TKT-039 necesitan TKT-011b. TKT-012 depende de la mitad b porque `Obra.linea_base_vigente_id` del borrador OpenAPI se lee de `linea_base` y su ficha exige el rechazo `OBRA_CON_HISTORIAL` para una obra con línea base congelada (hallazgo H2 de `revisor-impacto`).

**La alternativa descartada** es una sola entrega con dos migraciones en un único PR: respeta «una migración por mitad», pero el PR seguiría en ~2,175 líneas y la metodología pone el tope por cambio, no por migración.

### Criterios de la spec que hay que ajustar si se aprueba la partición

| Criterio | Dice hoy | Debe decir |
|---|---|---|
| Contexto y problema | «en una migración nueva (`0006`)» | «en dos migraciones nuevas, `0006` (TKT-011a) y `0007` (TKT-011b)» |
| `CA-1` | «la migración crea las 19 tablas» | doce tablas en `0006` y siete en `0007`; el escenario se verifica por mitad |
| `CA-8` | seis filas en un solo esquema de escenario | igual, pero TKT-011a prueba las tres filas de sus tablas (obra, insumo y cargo de APU) y TKT-011b prueba las seis juntas, para afirmar el mismo `SQLSTATE` en todas |
| `CA-13` y `CA-14` | una sola tabla de ejemplos | cada mitad prueba las columnas de sus tablas |
| `CA-17` | sobre las tablas del módulo | TKT-011a prueba lectura y `TRUNCATE` sobre sus doce tablas; TKT-011b, los cuatro escenarios sobre las diecinueve |
| `CA-18` | `downgrade 0005` | TKT-011a: `upgrade 0006`, `downgrade 0005`, `upgrade 0006`. TKT-011b: `upgrade 0007`, `downgrade 0006`, `upgrade 0007` |
| `CA-19` | `downgrade 0005` | `downgrade 0006`: la guarda vive en la bajada de `0007` |
| `CA-R4` | «`alembic heads` devuelve una sola revisión `0006`» y «las pruebas de migración de TKT-003, TKT-007 y TKT-057 pasan **sin cambios**» | una sola cabeza; `0006` cuelga de `0005` y `0007` de `0006`; las pruebas de TKT-003 y TKT-007 pasan sin cambios y las de TKT-057 pasan con el ajuste de la fila A1 (ver abajo) |
| Definition of Done | «Los 20 criterios `[M]`… » y «añade la migración `0006`» | reparto por ticket hermano y «añade las migraciones `0006` y `0007`» |

**`CA-R4` es falso aunque no se parta el ticket.** `test_tkt057_ca08_las_filas_de_la_version_anterior_quedan_verificadas` (TC-12 de TKT-057, `test_tkt057_migracion.py:240` y `:249`) y `test_tkt057_ca08_la_migracion_se_revierte_y_vuelve_a_subir` (TC-13, `:267`, `:285` y `:290`) suben con `migrar(base_vacia)`, es decir a la cabeza, y después afirman que la versión es `0005`. Con cualquier migración nueva la cabeza deja de ser `0005` y las dos pruebas se ponen rojas. El ajuste mínimo, que conserva su intención («sube hasta `0005`»), es pasar `REVISION_NUEVA` como destino en esas tres llamadas. Es la fila A1 y necesita la aprobación de la persona dueña, porque toca pruebas de otro ticket y contradice la redacción actual de `CA-R4`. Precedente: la fila 2 del diseño de TKT-057 adaptó así las pruebas de TKT-003 que su columna rompía.

**Regla para que TKT-011b no repita el problema:** ninguna prueba de TKT-011a afirma la cabeza por su número. Las que suben y comprueban versión suben a `"0006"` explícito; las que necesitan la cabeza la leen con `ScriptDirectory.get_current_head()`, como `test_identidad_migracion.py:69`.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Las diecinueve tablas | 5 · objeto nuevo | Las exige `M1`, `M2` y `M3`; no existe ninguna tabla del módulo. Forma tomada del modelo de datos §4.1 a §4.3 y §11 y del borrador OpenAPI, sin columnas de más salvo las de auditoría que fija `PA-T11` |
| Columnas de auditoría de `obra` (`creado_en`, `creado_por_id`, `actualizado_en`, `actualizado_por_id`), de `linea_base` (`creado_en`, `creado_por_id`) y de `importacion` (`creado_en`) | 5 · objeto nuevo | `PA-T11` las confirma y el borrador las devuelve (`Obra.creado_en`, `Obra.actualizado_en`, `Importacion.creado_en`). El modelo de datos §4.2 y §11 no las dibuja: `M8` lo alinea |
| `empresa.dias_semana_laboral` | 5 · objeto nuevo | `PA-T2`: `personal` no puede alterar una tabla de `presupuesto` sin cruzar la frontera |
| Conjuntos cerrados (`estado`, `tipo`, `unidad`, `tipo_contrato`) | 2 · nativo, `CHECK` con nombre | Ver «Catálogos cerrados: `CHECK`, no `ENUM`» |
| Rangos y no negatividad (34 restricciones) | 2 · nativo, `CHECK` con nombre | `M4`, invariante 8 ampliado y `PA-T5`. Una validación en Python se salta con un `psql` |
| `uq_obra_codigo`, `uq_tipo_partida_clave`, `uq_insumo_codigo`, `uq_concepto_obra_id_codigo`, `uq_presupuesto_control_linea_base_id_tipo_partida_id`, `uq_explosion_presupuesto_linea_tipo_insumo` | 2 · nativo, `UNIQUE` | Invariantes 6 y 13, `CA-3`, `PA-T9`, y las claves de catálogo que el modelo marca `UK` |
| `uq_linea_base_obra_id_congelada` | 2 · nativo, índice único parcial | Invariante 5. Un `UNIQUE` sin `WHERE` no admite las versiones `SUPERSEDIDA` |
| Doce índices `ix_` sobre claves foráneas | 2 · nativo, índice | `conv-sql-postgres` §6 y §8 exigen índice por cada clave foránea que se filtra o se une; sin el de `linea_base_concepto.linea_base_id`, borrar un borrador recorre la tabla entera para comprobar el `RESTRICT`. Solo las claves que un consumidor conocido filtra (lista en la tabla de índices); las de `usuario`, `tipo_partida` y `rendimiento_observado` no llevan índice: nadie filtra por ellas en la fase 1 |
| `presupuesto_proteger_copia_congelada()` y sus dos disparadores | 5 · objeto nuevo, lo más pequeño posible | El invariante 14 no se puede expresar de forma declarativa (modelo de datos §13, ADR de copia física). El privilegio no basta: `explosion_presupuesto` necesita `UPDATE` para `FOR UPDATE` |
| `presupuesto_proteger_linea_base()` y `trg_linea_base_solo_avanza` | 5 · objeto nuevo | `M5` ampliado y `PA-T14`: el rol de aplicación necesita `UPDATE` sobre `linea_base` para congelar, y sin este disparador podría devolverla a `BORRADOR` y reabrir sus copias |
| `SQLSTATE` `IN001` | 2 · nativo, `RAISE … USING ERRCODE` | PL/pgSQL admite un código de cinco caracteres. Ver «El código del rechazo» |
| `REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion` | 4 · cambio mínimo sobre los privilegios por omisión de `0001` | `M6` e invariante 14. No toca ningún invariante registrado: lo cumple |
| Ningún `REVOKE` sobre `explosion_presupuesto`, `presupuesto_control` ni `linea_base` | 3 · reuso de los privilegios por omisión | Los privilegios por omisión ya dan `UPDATE`, que exige `FOR UPDATE` (ADR-004) y el congelado (TKT-017) |
| Guarda de la bajada de `0007` | 3 · reuso del patrón de `0003` | Bloque `DO` que lanza si hay datos que la regla declara permanentes, ya probado en `test_tkt007_ca10_la_bajada_no_borra_asientos` |
| Fábrica de datos de prueba `DatosPresupuesto` en `conftest.py` | 5 · objeto nuevo, código de prueba | `conv-pruebas` §8: los datos se construyen con fixtures con nombre del dominio. Va en `conftest.py`, como `SembrarUsuario`, para que mypy la resuelva sin tocar su configuración |
| Ajuste de TC-12 y TC-13 de TKT-057 | 4 · cambio mínimo | Ver «Partición». Necesita la aprobación de la persona dueña |
| `BEFORE TRUNCATE` sobre las copias | 1 · YAGNI, fuera | `PA-T15` acepta el límite. Solo lo usaría el rol de migración, que es dueño de las tablas y puede deshabilitar o borrar cualquier disparador; no cierra nada que el rol de migración no pueda reabrir |
| `CHECK` de `area.tipo_unidad` y de `tipo_partida.clave` | 1 · YAGNI, fuera | El modelo los declara `string`, no `enum`; la spec no los pide. `tipo_partida` es tabla de catálogo que siembra TKT-010 |
| `UNIQUE (rendimiento_observado.obra_id, insumo_id)`, `CHECK (vigente_hasta >= vigente_desde)`, `CHECK (version >= 1)`, rango de `dias_semana_laboral` | 1 · YAGNI, fuera | Ninguno lo pide un Must ni un criterio. Quedan como ticket futuro sugerido, igual que los cuatro Won't de `PA-T3` |
| Revocar escritura sobre `rendimiento_observado` | 1 · YAGNI, fuera | «Sin escritor» es una propiedad del código (`CA-10`), no del privilegio; la spec no lo pide |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la escalera no se rompe.

### Catálogos cerrados: `CHECK`, no `ENUM`

`CA-8` exige un único `SQLSTATE` para los seis conjuntos cerrados, y el diseño elige **`CHECK (columna IN (…))` con nombre `ck_<tabla>_<columna>`**, que responde `23514`. Columna `text NOT NULL`.

| Criterio | `CHECK` (elegido) | `ENUM` (descartado) |
|---|---|---|
| Lo que la prueba puede afirmar | `23514` y `diag.constraint_name`: la Definition of Done exige el nombre de la restricción en cada rechazo | `22P02` sin nombre de restricción, y el código depende de cómo envía el cliente el parámetro `(sin ejecutar, E-7)` |
| Coherencia con el invariante 27 | La unidad ya es `CHECK` por el invariante 27; un solo mecanismo para todos los conjuntos del módulo | Mezclaría `ENUM` en estados y `CHECK` en unidades |
| Reversibilidad | Sustituir la restricción es reversible dentro de una migración | `ALTER TYPE … ADD VALUE` no tiene inverso: PostgreSQL no admite `DROP VALUE` |
| ORM futuro | `text` se mapea sin tipo propio | Exige declarar el tipo en SQLAlchemy y no recrearlo |

**Choca con una convención escrita, no con un invariante.** El modelo de datos §2 dice «Tipos `ENUM` de PostgreSQL cuando el conjunto es cerrado y estable», y la migración `0003` usa `ENUM` para `accion_bitacora`. El diseño propone actualizar esa fila en `M8` («`CHECK` con nombre cuando el rechazo debe nombrar la restricción; `accion_bitacora` es la excepción histórica») y registrarlo en ADR-030. Es una pregunta para el gate (P2).

### El código del rechazo: `IN001`

Los dos disparadores rechazan con `RAISE EXCEPTION USING ERRCODE = 'IN001'`, y además rellenan `CONSTRAINT = TG_NAME`, `TABLE = TG_TABLE_NAME` y `SCHEMA = TG_TABLE_SCHEMA`, de modo que el cliente recibe `diag.constraint_name` con el nombre del disparador, igual que con una restricción (comprobado en el experimento E-4 de la fila A0, el 2026-11-01).

La persona dueña eligió `IN001` el 2026-11-01. El diseño original proponía `CM001`, pero el experimento de A0 confirmó que la clase `CM` empieza por una letra entre la A y la H, rango que el estándar SQL se reserva; las clases definidas por la implementación empiezan por 5 a 9 o por I a Z, y PostgreSQL 18.6 solo usa `P0` y `XX` entre las que empiezan por I a Z.

| Opción | Por qué no |
|---|---|
| `P0001`, el de `RAISE EXCEPTION` sin código | Lo emite cualquier bloque `DO` y cualquier función: TKT-017 tendría que distinguir por el texto del mensaje |
| Un código de la clase `23` (por ejemplo `23C01`) | La clase pertenece a PostgreSQL y puede ganar códigos en una versión futura |
| `CM001`, clase `CM` | Descartado tras la fila A0: la `C` cae en el rango de la A hasta la H que reserva el estándar SQL; hoy ninguna clase de PostgreSQL empieza por `CM`, pero eso no protege de una clase estándar futura |
| **`IN001`, clase `IN` (de «inmutable»), elegido** | La `I` está en el rango de la implementación y ninguna clase de PostgreSQL 18.6 empieza por `IN`; psycopg lo entrega como `psycopg.DatabaseError` con `sqlstate == "IN001"` y `diag.constraint_name` y `diag.table_name` (E-4 confirmado) y SQLAlchemy como `DBAPIError` con `orig.sqlstate` |

TKT-017 traduce `IN001` a `409` `REGLA_NEGOCIO` con `regla = "RN-01"` `(asumido)`. Queda documentado en el modelo de datos §13 (invariante 14) y en ADR-031 (pendiente de TKT-011b).

## Capas afectadas

### Infraestructura y esquema

Toda columna `id` es `uuid NOT NULL`, clave primaria `pk_<tabla>`, sin valor por omisión: la genera la aplicación (modelo de datos §2). Toda clave foránea se llama `fk_<tabla>_<columna>` y se declara `ON DELETE RESTRICT` (`PA-T8`), con `ON UPDATE` por omisión. Ningún tipo es `real` ni `double precision`. Los únicos valores por omisión son `empresa.dias_semana_laboral DEFAULT 6` (`PA-T2`) y `creado_en DEFAULT now()` en `obra`, `linea_base` e `importacion`, como en `usuario` y `sesion`; ningún booleano lleva valor por omisión, para que quien inserta lo declare (precedente: `v0005`).

#### Tabla de nulabilidad (`PA-T10`)

Columna «Nulo»: **no** es `NOT NULL`; **sí** admite nulo. Las restricciones se listan en la tabla siguiente.

**`empresa`** (TKT-011a)

| Columna | Tipo | Nulo | Por omisión | Restricción |
|---|---|---|---|---|
| `id` | `uuid` | no | — | `pk_empresa` |
| `nombre` | `text` | no | — | — |
| `rfc` | `text` | no | — | — |
| `activa` | `boolean` | no | — | — |
| `dias_semana_laboral` | `smallint` | no | `6` | — |

**`obra`** (TKT-011a)

| Columna | Tipo | Nulo | Por omisión | Restricción |
|---|---|---|---|---|
| `id` | `uuid` | no | — | `pk_obra` |
| `empresa_id` | `uuid` | no | — | `fk_obra_empresa_id` → `empresa` |
| `codigo` | `text` | no | — | `uq_obra_codigo` |
| `nombre` | `text` | no | — | — |
| `domicilio` | `text` | no | — | — |
| `tipo_contrato` | `text` | no | — | `ck_obra_tipo_contrato` |
| `retencion_destajo_pct` | `numeric(9,6)` | no | — | `ck_obra_retencion_destajo_pct_rango` |
| `fondo_garantia_pct` | `numeric(9,6)` | no | — | `ck_obra_fondo_garantia_pct_rango` |
| `iva_acreditable` | `boolean` | no | — | — |
| `umbral_alerta_pct` | `numeric(9,6)` | sí | — | `ck_obra_umbral_alerta_pct_no_negativo` |
| `estado` | `text` | no | — | `ck_obra_estado` |
| `creado_en` | `timestamptz` | no | `now()` | — |
| `creado_por_id` | `uuid` | no | — | `fk_obra_creado_por_id` → `usuario` |
| `actualizado_en` | `timestamptz` | sí | — | — |
| `actualizado_por_id` | `uuid` | sí | — | `fk_obra_actualizado_por_id` → `usuario` |

`actualizado_*` admiten nulo porque la obra recién creada no tiene cambio, igual que `presupuesto_control` y que `Obra.actualizado_en`, que el borrador no marca obligatorio.

**`nivel`**, **`area`**, **`tipo_partida`** y **`partida`** (TKT-011a)

| Tabla | Columna | Tipo | Nulo | Restricción |
|---|---|---|---|---|
| `nivel` | `id` | `uuid` | no | `pk_nivel` |
| `nivel` | `obra_id` | `uuid` | no | `fk_nivel_obra_id` → `obra` |
| `nivel` | `nombre` | `text` | no | — |
| `nivel` | `orden` | `integer` | no | — |
| `area` | `id` | `uuid` | no | `pk_area` |
| `area` | `nivel_id` | `uuid` | no | `fk_area_nivel_id` → `nivel` |
| `area` | `nombre` | `text` | no | — |
| `area` | `tipo_unidad` | `text` | no | — |
| `tipo_partida` | `id` | `uuid` | no | `pk_tipo_partida` |
| `tipo_partida` | `clave` | `text` | no | `uq_tipo_partida_clave` |
| `tipo_partida` | `nombre` | `text` | no | — |
| `partida` | `id` | `uuid` | no | `pk_partida` |
| `partida` | `area_id` | `uuid` | no | `fk_partida_area_id` → `area` |
| `partida` | `tipo_partida_id` | `uuid` | no | `fk_partida_tipo_partida_id` → `tipo_partida` |
| `partida` | `orden` | `integer` | no | — |

**`concepto`**, **`insumo`** y **`precio_insumo`** (TKT-011a)

| Tabla | Columna | Tipo | Nulo | Restricción |
|---|---|---|---|---|
| `concepto` | `id` | `uuid` | no | `pk_concepto` |
| `concepto` | `obra_id` | `uuid` | no | `fk_concepto_obra_id` → `obra` |
| `concepto` | `partida_id` | `uuid` | no | `fk_concepto_partida_id` → `partida` |
| `concepto` | `codigo` | `text` | no | `uq_concepto_obra_id_codigo` con `obra_id` |
| `concepto` | `descripcion` | `text` | no | — |
| `concepto` | `unidad` | `text` | no | `ck_concepto_unidad` |
| `concepto` | `cantidad` | `numeric(14,4)` | no | `ck_concepto_cantidad_no_negativo` |
| `concepto` | `precio_unitario` | `numeric(14,4)` | no | `ck_concepto_precio_unitario_no_negativo` |
| `concepto` | `importe` | `numeric(18,4)` | no | `ck_concepto_importe_no_negativo` |
| `insumo` | `id` | `uuid` | no | `pk_insumo` |
| `insumo` | `codigo` | `text` | no | `uq_insumo_codigo` |
| `insumo` | `descripcion` | `text` | no | — |
| `insumo` | `tipo` | `text` | no | `ck_insumo_tipo` |
| `insumo` | `unidad` | `text` | no | `ck_insumo_unidad` |
| `insumo` | `activo` | `boolean` | no | — |
| `insumo` | `creado_en_importacion` | `boolean` | no | — |
| `precio_insumo` | `id` | `uuid` | no | `pk_precio_insumo` |
| `precio_insumo` | `insumo_id` | `uuid` | no | `fk_precio_insumo_insumo_id` → `insumo` |
| `precio_insumo` | `obra_id` | `uuid` | sí | `fk_precio_insumo_obra_id` → `obra` |
| `precio_insumo` | `costo_unitario` | `numeric(14,4)` | no | `ck_precio_insumo_costo_unitario_no_negativo` |
| `precio_insumo` | `vigente_desde` | `date` | no | — |
| `precio_insumo` | `vigente_hasta` | `date` | sí | — |

**`apu`**, **`apu_insumo`** y **`apu_cargo`** (TKT-011a). Todo importe dentro del APU es **por unidad del concepto**, así que lleva la escala de precio, `numeric(14,4)`, no la de importe.

| Tabla | Columna | Tipo | Nulo | Restricción |
|---|---|---|---|---|
| `apu` | `id` | `uuid` | no | `pk_apu` |
| `apu` | `concepto_id` | `uuid` | no | `fk_apu_concepto_id` → `concepto` (sin `UNIQUE`, `PA-T3`) |
| `apu` | `fecha_analisis` | `date` | no | — |
| `apu` | `analista` | `text` | no | — |
| `apu` | `costo_material` | `numeric(14,4)` | no | `ck_apu_costo_material_no_negativo` |
| `apu` | `costo_mano_obra` | `numeric(14,4)` | no | `ck_apu_costo_mano_obra_no_negativo` |
| `apu` | `costo_directo` | `numeric(14,4)` | no | `ck_apu_costo_directo_no_negativo` |
| `apu` | `total_cargos` | `numeric(14,4)` | no | `ck_apu_total_cargos_no_negativo` |
| `apu` | `total_indirectos` | `numeric(14,4)` | no | `ck_apu_total_indirectos_no_negativo` |
| `apu` | `precio_unitario` | `numeric(14,4)` | no | `ck_apu_precio_unitario_no_negativo` |
| `apu_insumo` | `id` | `uuid` | no | `pk_apu_insumo` |
| `apu_insumo` | `apu_id` | `uuid` | no | `fk_apu_insumo_apu_id` → `apu` |
| `apu_insumo` | `insumo_id` | `uuid` | no | `fk_apu_insumo_insumo_id` → `insumo` |
| `apu_insumo` | `costo_unitario` | `numeric(14,4)` | no | `ck_apu_insumo_costo_unitario_no_negativo` |
| `apu_insumo` | `rendimiento` | `numeric(18,6)` | no | `ck_apu_insumo_rendimiento_no_negativo` |
| `apu_insumo` | `cargo` | `numeric(14,4)` | no | `ck_apu_insumo_cargo_no_negativo` |
| `apu_cargo` | `id` | `uuid` | no | `pk_apu_cargo` |
| `apu_cargo` | `apu_id` | `uuid` | no | `fk_apu_cargo_apu_id` → `apu` |
| `apu_cargo` | `tipo` | `text` | no | `ck_apu_cargo_tipo` |
| `apu_cargo` | `porcentaje` | `numeric(9,6)` | no | `ck_apu_cargo_porcentaje_no_negativo` |
| `apu_cargo` | `base_calculo` | `numeric(14,4)` | no | `ck_apu_cargo_base_calculo_no_negativo` |
| `apu_cargo` | `importe` | `numeric(14,4)` | no | `ck_apu_cargo_importe_no_negativo` |

**`linea_base`**, **`linea_base_concepto`**, **`explosion_presupuesto`** y **`presupuesto_control`** (TKT-011b)

| Tabla | Columna | Tipo | Nulo | Por omisión | Restricción |
|---|---|---|---|---|---|
| `linea_base` | `id` | `uuid` | no | — | `pk_linea_base` |
| `linea_base` | `obra_id` | `uuid` | no | — | `fk_linea_base_obra_id` → `obra` |
| `linea_base` | `version` | `integer` | no | — | — (sin `UNIQUE`, `PA-T3`) |
| `linea_base` | `estado` | `text` | no | — | `ck_linea_base_estado` |
| `linea_base` | `congelada_en` | `timestamptz` | sí | — | — |
| `linea_base` | `congelada_por_id` | `uuid` | sí | — | `fk_linea_base_congelada_por_id` → `usuario` |
| `linea_base` | `motivo` | `text` | sí | — | — (`LineaBase.motivo` admite nulo en el borrador) |
| `linea_base` | `importe_venta` | `numeric(18,4)` | no | — | `ck_linea_base_importe_venta_no_negativo` |
| `linea_base` | `creado_en` | `timestamptz` | no | `now()` | — |
| `linea_base` | `creado_por_id` | `uuid` | no | — | `fk_linea_base_creado_por_id` → `usuario` |
| `linea_base_concepto` | `id` | `uuid` | no | — | `pk_linea_base_concepto` |
| `linea_base_concepto` | `linea_base_id` | `uuid` | no | — | `fk_linea_base_concepto_linea_base_id` → `linea_base` |
| `linea_base_concepto` | `concepto_id` | `uuid` | no | — | `fk_linea_base_concepto_concepto_id` → `concepto` |
| `linea_base_concepto` | `codigo` | `text` | no | — | — |
| `linea_base_concepto` | `cantidad` | `numeric(14,4)` | no | — | `ck_linea_base_concepto_cantidad_no_negativo` |
| `linea_base_concepto` | `precio_unitario` | `numeric(14,4)` | no | — | `ck_linea_base_concepto_precio_unitario_no_negativo` |
| `linea_base_concepto` | `importe` | `numeric(18,4)` | no | — | `ck_linea_base_concepto_importe_no_negativo` |
| `explosion_presupuesto` | `id` | `uuid` | no | — | `pk_explosion_presupuesto` |
| `explosion_presupuesto` | `linea_base_id` | `uuid` | no | — | `fk_explosion_presupuesto_linea_base_id` → `linea_base` |
| `explosion_presupuesto` | `tipo_partida_id` | `uuid` | no | — | `fk_explosion_presupuesto_tipo_partida_id` → `tipo_partida` |
| `explosion_presupuesto` | `insumo_id` | `uuid` | no | — | `fk_explosion_presupuesto_insumo_id` → `insumo` |
| `explosion_presupuesto` | `cantidad_presupuestada` | `numeric(14,4)` | no | — | `ck_explosion_presupuesto_cantidad_presupuestada_no_negativo` |
| `explosion_presupuesto` | `rendimiento_congelado` | `numeric(18,6)` | no | — | `ck_explosion_presupuesto_rendimiento_congelado_no_negativo` |
| `explosion_presupuesto` | `costo_unitario` | `numeric(14,4)` | no | — | `ck_explosion_presupuesto_costo_unitario_no_negativo` |
| `explosion_presupuesto` | `importe_venta` | `numeric(18,4)` | no | — | `ck_explosion_presupuesto_importe_venta_no_negativo` |
| `presupuesto_control` | `id` | `uuid` | no | — | `pk_presupuesto_control` |
| `presupuesto_control` | `linea_base_id` | `uuid` | no | — | `fk_presupuesto_control_linea_base_id` → `linea_base` |
| `presupuesto_control` | `tipo_partida_id` | `uuid` | no | — | `fk_presupuesto_control_tipo_partida_id` → `tipo_partida` |
| `presupuesto_control` | `importe_tope` | `numeric(18,4)` | sí | — | `ck_presupuesto_control_importe_tope_no_negativo` |
| `presupuesto_control` | `importe_sugerido` | `numeric(18,4)` | no | — | `ck_presupuesto_control_importe_sugerido_no_negativo` |
| `presupuesto_control` | `capturado_por_id` | `uuid` | sí | — | `fk_presupuesto_control_capturado_por_id` → `usuario` |
| `presupuesto_control` | `capturado_en` | `timestamptz` | sí | — | — |
| `presupuesto_control` | `actualizado_por_id` | `uuid` | sí | — | `fk_presupuesto_control_actualizado_por_id` → `usuario` |
| `presupuesto_control` | `actualizado_en` | `timestamptz` | sí | — | — |
| `presupuesto_control` | `motivo_ultimo_cambio` | `text` | sí | — | — |

**`importacion`**, **`importacion_error`** y **`rendimiento_observado`** (TKT-011b)

| Tabla | Columna | Tipo | Nulo | Por omisión | Restricción |
|---|---|---|---|---|---|
| `importacion` | `id` | `uuid` | no | — | `pk_importacion` |
| `importacion` | `obra_id` | `uuid` | no | — | `fk_importacion_obra_id` → `obra` |
| `importacion` | `archivo_id` | `uuid` | no | — | **ninguna**: identificador lógico (modelo de datos §2) |
| `importacion` | `estado` | `text` | no | — | `ck_importacion_estado` |
| `importacion` | `progreso` | `numeric(9,6)` | sí | — | `ck_importacion_progreso_rango` |
| `importacion` | `filas_leidas` | `integer` | sí | — | — |
| `importacion` | `filas_validas` | `integer` | sí | — | — |
| `importacion` | `filas_rechazadas` | `integer` | sí | — | — |
| `importacion` | `resumen` | `jsonb` | sí | — | — |
| `importacion` | `importado_por_id` | `uuid` | no | — | `fk_importacion_importado_por_id` → `usuario` |
| `importacion` | `creado_en` | `timestamptz` | no | `now()` | — |
| `importacion` | `latido` | `timestamptz` | sí | — | — |
| `importacion_error` | `id` | `uuid` | no | — | `pk_importacion_error` |
| `importacion_error` | `importacion_id` | `uuid` | no | — | `fk_importacion_error_importacion_id` → `importacion` |
| `importacion_error` | `hoja` | `text` | sí | — | — |
| `importacion_error` | `fila` | `integer` | sí | — | — |
| `importacion_error` | `columna` | `text` | sí | — | — |
| `importacion_error` | `tipo` | `text` | no | — | `ck_importacion_error_tipo` |
| `importacion_error` | `mensaje` | `text` | no | — | — |
| `importacion_error` | `valor_original` | `text` | sí | — | — |
| `rendimiento_observado` | `id` | `uuid` | no | — | `pk_rendimiento_observado` |
| `rendimiento_observado` | `obra_id` | `uuid` | no | — | `fk_rendimiento_observado_obra_id` → `obra` |
| `rendimiento_observado` | `insumo_id` | `uuid` | no | — | `fk_rendimiento_observado_insumo_id` → `insumo` |
| `rendimiento_observado` | `consumo_acumulado` | `numeric(14,4)` | no | — | `ck_rendimiento_observado_consumo_acumulado_no_negativo` |
| `rendimiento_observado` | `avance_acumulado` | `numeric(14,4)` | no | — | `ck_rendimiento_observado_avance_acumulado_no_negativo` |
| `rendimiento_observado` | `rendimiento` | `numeric(18,6)` | no | — | `ck_rendimiento_observado_rendimiento_no_negativo` |
| `rendimiento_observado` | `rendimiento_congelado` | `numeric(18,6)` | no | — | `ck_rendimiento_observado_rendimiento_congelado_no_negativo` |
| `rendimiento_observado` | `divergencia_pct` | `numeric(9,6)` | no | — | — (una divergencia puede ser negativa) |
| `rendimiento_observado` | `muestra` | `integer` | no | — | — |
| `rendimiento_observado` | `calculado_en` | `timestamptz` | no | — | — |

#### Restricciones `CHECK`

Conjuntos cerrados (9), todos `CHECK (<columna> IN (…))`:

| Nombre | Valores | Ticket |
|---|---|---|
| `ck_obra_tipo_contrato` | `PRECIO_ALZADO_MAXIMO_GARANTIZADO` | a |
| `ck_obra_estado` | `PLANEACION`, `ACTIVA`, `SUSPENDIDA`, `CERRADA` | a |
| `ck_concepto_unidad` | `M2`, `ML`, `PZA`, `KG`, `CAJA`, `SACO`, `ROLLO`, `JORNAL` | a |
| `ck_insumo_unidad` | las mismas ocho (`PA-T7`) | a |
| `ck_insumo_tipo` | `MATERIAL`, `MANO_OBRA`, `HERRAMIENTA`, `CONSUMIBLE` | a |
| `ck_apu_cargo_tipo` | `HERRAMIENTA_MENOR`, `ANDAMIAJE`, `DESPERDICIO`, `VIATICOS`, `IVA`, `INDIRECTOS`, `UTILIDAD` | a |
| `ck_linea_base_estado` | `BORRADOR`, `CONGELADA`, `SUPERSEDIDA` | b |
| `ck_importacion_estado` | `RECIBIDO`, `ANALIZANDO`, `VALIDADO`, `CON_ERRORES`, `CONFIRMADO`, `DESCARTADO` | b |
| `ck_importacion_error_tipo` | `REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO`, `SIN_CONCEPTOS`, `PROCESO_INTERRUMPIDO` | b |

Rangos (3), `CHECK (<columna> >= 0 AND <columna> <= 1)`, `PA-T5`: `ck_obra_retencion_destajo_pct_rango` y `ck_obra_fondo_garantia_pct_rango` (a), `ck_importacion_progreso_rango` (b). Con `progreso` nulo el `CHECK` se evalúa a nulo y la fila pasa, que es lo que pide `CA-14`.

No negatividad (31), `CHECK (<columna> >= 0)`, con nombre `ck_<tabla>_<columna>_no_negativo`. TKT-011a: las tres de `concepto`, la de `precio_insumo`, las seis de `apu`, las tres de `apu_insumo`, las tres de `apu_cargo` (`porcentaje`, `base_calculo`, `importe`) y `obra.umbral_alerta_pct` (17). TKT-011b: `linea_base.importe_venta`, las tres de `linea_base_concepto`, las cuatro de `explosion_presupuesto`, las dos de `presupuesto_control` y las cuatro de `rendimiento_observado` (14). La lista exacta está en la tabla de nulabilidad.

#### Unicidad e índices

| Nombre | Tipo | Columnas | Ticket |
|---|---|---|---|
| `uq_obra_codigo` | `UNIQUE` | `obra (codigo)` | a |
| `uq_tipo_partida_clave` | `UNIQUE` | `tipo_partida (clave)` | a |
| `uq_insumo_codigo` | `UNIQUE` | `insumo (codigo)` | a |
| `uq_concepto_obra_id_codigo` | `UNIQUE` | `concepto (obra_id, codigo)` | a |
| `ix_nivel_obra_id` · `ix_area_nivel_id` · `ix_partida_area_id` · `ix_concepto_partida_id` · `ix_precio_insumo_insumo_id` · `ix_apu_concepto_id` · `ix_apu_insumo_apu_id` · `ix_apu_cargo_apu_id` | índice | la clave foránea de su nombre | a |
| `uq_linea_base_obra_id_congelada` | índice único parcial | `linea_base (obra_id) WHERE estado = 'CONGELADA'` | b |
| `uq_explosion_presupuesto_linea_tipo_insumo` | `UNIQUE` | `explosion_presupuesto (linea_base_id, tipo_partida_id, insumo_id)` | b |
| `uq_presupuesto_control_linea_base_id_tipo_partida_id` | `UNIQUE` | `presupuesto_control (linea_base_id, tipo_partida_id)` | b |
| `ix_linea_base_obra_id` · `ix_linea_base_concepto_linea_base_id` · `ix_importacion_obra_id` · `ix_importacion_error_importacion_id` | índice | la clave foránea de su nombre | b |

`uq_explosion_presupuesto_linea_tipo_insumo` es abreviado a propósito: el nombre largo por columnas tiene 64 caracteres y PostgreSQL trunca a 63 sin error, solo con un aviso `(sin ejecutar, E-10)`. La prueba de `CA-20` compara el conjunto exacto de nombres, así que un truncado se vería. `uq_concepto_obra_id_codigo` y los dos únicos de TKT-011b ya cubren con su columna inicial el filtro por `obra_id` o por `linea_base_id`.

#### Disparadores del invariante 14 (TKT-011b)

Dos funciones `LANGUAGE plpgsql`, `SECURITY INVOKER` (el valor por omisión), creadas por `cimenta_migracion`, que nombran la tabla con su esquema (`public.linea_base`). Ninguna implementa una regla de negocio: protegen la estructura que `RN-01` declara inmutable (`conv-sql-postgres` §1).

**`presupuesto_proteger_copia_congelada()`**, disparada por:

- `trg_linea_base_concepto_inmutable` — `BEFORE INSERT OR UPDATE OR DELETE ON linea_base_concepto FOR EACH ROW`
- `trg_explosion_presupuesto_inmutable` — `BEFORE INSERT OR UPDATE OR DELETE ON explosion_presupuesto FOR EACH ROW`

Lógica, en este orden:

1. Reúne las líneas base afectadas: `NEW.linea_base_id` en `INSERT`; `OLD.linea_base_id` en `DELETE`; las dos en `UPDATE` (mover una copia de una línea base a otra también cuenta).
2. Para cada una lee `estado` con `SELECT estado FROM public.linea_base WHERE id = … FOR SHARE`. El `FOR SHARE` espera a una transacción que esté congelando esa línea base y, en `READ COMMITTED`, relee la fila ya confirmada; sin él, una inserción concurrente leería `BORRADOR` y entraría después del congelado `(sin ejecutar, E-9)`. El rol de aplicación puede tomar `FOR SHARE` porque tiene `UPDATE` sobre `linea_base` `(sin ejecutar, E-1)`.
3. Si el estado leído es distinto de `BORRADOR` (`CONGELADA` o `SUPERSEDIDA`, `PA-T6`), lanza `IN001` con el mensaje `RN-01: la línea base <id> está <estado>; <TG_OP> sobre <TG_TABLE_NAME> no se admite`. Si la línea base no existe, el estado es nulo y la función deja pasar la fila: la clave foránea la rechaza después con `23503`.
4. Devuelve `OLD` en `DELETE` y `NEW` en los demás casos.

**`presupuesto_proteger_linea_base()`**, disparada por `trg_linea_base_solo_avanza` — `BEFORE UPDATE OR DELETE ON linea_base FOR EACH ROW`. No interviene en `INSERT`: `CA-4` inserta líneas base `CONGELADA` y `SUPERSEDIDA` directamente.

1. `DELETE`: si `OLD.estado` no es `BORRADOR`, lanza `IN001` con `RN-01: la línea base <id> está <estado> y no se borra`. Un `BORRADOR` con copias lo rechaza antes la clave foránea con `23001` (`restrict_violation`), porque `RESTRICT` se comprueba en la propia sentencia; uno sin copias se borra.
2. `UPDATE` desde `BORRADOR`: admite `NEW.estado` en `BORRADOR` o `CONGELADA`, con cualquier cambio de columnas en la misma sentencia (TKT-017 fija `congelada_en`, `congelada_por_id` e `importe_venta` al congelar, `PA-T14`). Si `NEW.estado = 'SUPERSEDIDA'`, lanza `IN001` con `RN-01: la línea base <id> no pasa de BORRADOR a SUPERSEDIDA`.
3. `UPDATE` desde `CONGELADA` o `SUPERSEDIDA`: primero compara la fila sin su estado, `(to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado')`; si difiere, lanza `IN001` con `RN-01: la línea base <id> está <estado>; solo su estado puede cambiar`. La comparación cubre también las columnas que añada una migración futura sin tocar la función `(sin ejecutar, E-11)`. Después, la única transición admitida es `CONGELADA` → `SUPERSEDIDA`; cualquier otra, incluido el `UPDATE` que no cambia nada, lanza `IN001` con `RN-01: la línea base <id> no pasa de <OLD.estado> a <NEW.estado>`.
4. Devuelve `OLD` en `DELETE` y `NEW` en `UPDATE`.

Todos los `RAISE` llevan `ERRCODE = 'IN001'`, `CONSTRAINT = TG_NAME`, `TABLE = TG_TABLE_NAME` y `SCHEMA = TG_TABLE_SCHEMA`. Los textos son exactamente los de arriba, con los marcadores sustituidos por `format()`; las pruebas afirman el `SQLSTATE`, el prefijo `RN-01:`, `diag.constraint_name` y `diag.table_name`.

**El congelado en una transacción.** TKT-017 inserta las copias con la línea base en `BORRADOR` y, en la misma transacción, la pasa a `CONGELADA`. Las inserciones pasan porque cada una lee `BORRADOR`; desde el `UPDATE`, la propia transacción ve `CONGELADA` y cualquier escritura posterior sobre las copias se rechaza. `SELECT … FOR UPDATE` sobre `explosion_presupuesto` no dispara `trg_explosion_presupuesto_inmutable`, porque bloquear una fila no es un `UPDATE` `(sin ejecutar, E-2)`: el bloqueo pesimista de ADR-004 funciona sobre una línea base congelada.

#### Privilegios

| Rol | Tablas | Privilegios tras la migración | Cómo |
|---|---|---|---|
| `cimenta_aplicacion` | las doce de TKT-011a, `linea_base`, `explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error`, `rendimiento_observado` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` | Privilegios por omisión de `0001` (ya probados por TC-31 de TKT-003). En la ejecución, `v0006` añadió además un `GRANT SELECT, INSERT, UPDATE, DELETE` explícito por tabla, redundante con los privilegios por omisión y con el mismo resultado (ver «Ajustes respecto al design» de `impl.md`) |
| `cimenta_aplicacion` | `linea_base_concepto` | `SELECT`, `INSERT` | `REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion` en `0007`. `TRUNCATE` no lo concede ningún privilegio por omisión; se nombra para que la intención sobreviva a un cambio de `0001`, como en `0003` |
| `cimenta_aplicacion` | las diecinueve | sin `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN` | No los concede `0001` (TC-32 de TKT-003) |
| `cimenta_lectura` | las diecinueve | `SELECT` | Privilegio por omisión; ninguna tabla nueva guarda credenciales ni secretos |

#### Migraciones

**Migración `0006`** (TKT-011a) — `backend/migraciones/versions/v0006_presupuesto_estructura_y_catalogos.py`, `down_revision = "0005"`, mismo formato que `v0003` y `v0005`: tuplas `_SUBIDA` y `_BAJADA`, una sentencia por `op.execute`, docstring con revisión, anterior, reversibilidad y plan de reversa. Reversible: sí. Destructiva: solo en la bajada, que elimina las doce tablas y sus filas. Plan de reversa: `alembic downgrade 0005` tras respaldar la base con `pg_dump` si tiene datos; la bajada no se niega porque la spec solo protege la línea base congelada, que no existe en `0006`. Orden de la bajada: `apu_cargo`, `apu_insumo`, `apu`, `precio_insumo`, `concepto`, `partida`, `insumo`, `tipo_partida`, `area`, `nivel`, `obra`, `empresa`.

**Migración `0007`** (TKT-011b) — `backend/migraciones/versions/v0007_presupuesto_linea_base_e_importacion.py`, `down_revision = "0006"`. Orden de la subida: las siete tablas (`linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error`, `rendimiento_observado`), sus índices, las dos funciones, los tres disparadores y el `REVOKE`. Reversible: sí, salvo con una línea base `CONGELADA` o `SUPERSEDIDA`. Destructiva: en la bajada. Plan de reversa: `alembic downgrade 0006`; la bajada empieza con un bloque `DO` que toma `LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` antes de comprobar y, si existe alguna fila con `estado <> 'BORRADOR'`, lanza `IN001` con el mensaje `Hay al menos una línea base CONGELADA o SUPERSEDIDA (RN-01, invariante 14): la bajada de 0007 no la elimina. Respáldala con pg_dump; el retiro de una línea base que no es borrador lo decide la persona dueña y se hace fuera de esta migración.` y, como `env.py` ejecuta toda la cadena en una transacción, no se elimina nada `(sin ejecutar, E-12)`. Sin línea base `CONGELADA` ni `SUPERSEDIDA`, elimina `rendimiento_observado`, `importacion_error`, `importacion`, `presupuesto_control`, `explosion_presupuesto`, `linea_base_concepto` y `linea_base` (los disparadores caen con su tabla) y después las dos funciones.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Todas las órdenes `uv run` se ejecutan desde `backend/` con Docker en marcha. Los archivos de prueba nuevos son `backend/tests/test_tkt011_estructura.py` y `test_tkt011_regresion.py` (TKT-011a), y `test_tkt011_linea_base.py`, `test_tkt011_permisos.py`, `test_tkt011_importacion.py` y `test_tkt011_migracion_linea_base.py` (TKT-011b). La fábrica `DatosPresupuesto` vive en una sección «TKT-011» de `backend/tests/conftest.py`, sin `autouse`, con un método por tabla que inserta una fila válida con los valores mínimos y devuelve su `id` (`empresa()`, `obra(codigo=…)`, `tipo_partida(clave=…)`, `insumo(…)`, `concepto(…)`, y en TKT-011b `linea_base(estado=…)`, `copia_concepto(…)`, `renglon_explosion(…)`, `control(…)`, `importacion(…)`, `error_importacion(…)`, `rendimiento_observado(…)`) y un `usuario()` que inserta en `usuario` con `password_hash = 'hash-de-prueba'`. Los importes se pasan como `Decimal` construido desde cadena.

### Entrega TKT-011a · estructura y catálogos (`0006`)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | **Experimentos `(sin ejecutar)`** E-1 a E-12 de la tabla «Experimentos previos», en guiones del directorio temporal contra un contenedor `postgres:18.6` desechable, sin tocar el repositorio. Si alguno contradice el diseño, `/sdd-escalar` antes de A1 | — | `desarrollador-sql` | `sonnet` · permisos de un rol y disparador de inmutabilidad | Salida de cada guion pegada en `impl.md`, con lo esperado y lo observado por experimento | ✓ Hecho |
| A1 | Solo con la aprobación de P3: en `test_tkt057_migracion.py`, `migrar(base_vacia)` pasa a `migrar(base_vacia, REVISION_NUEVA)` en las líneas 240, 267 y 285. Sin código de producción. ~3 líneas | TC-12 y TC-13 de TKT-057, sin cambiar lo que afirman | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt057_migracion.py` en verde antes de crear `0006` | ✓ Hecho |
| A2 | `v0006` con `empresa`, `obra`, `tipo_partida` e `insumo`, sus `CHECK` y sus `UNIQUE`; fábrica `DatosPresupuesto` (parte a) en `conftest.py`. ~80 líneas de migración | TC-01 (sus cuatro tablas), TC-02, TC-03, TC-04, TC-05, TC-06, TC-07, TC-08, TC-09 (obra e insumo), TC-10 (insumo), TC-14 | `desarrollador-sql` | `haiku` | `uv run --env-file ../.env alembic upgrade head` sobre la base local; `uv run pytest tests/test_tkt011_estructura.py -k "ca01 or ca02 or ca03 or ca08 or ca11 or ca14"` | ✓ Hecho |
| A3 | `nivel`, `area`, `partida` y `concepto` con `ck_concepto_unidad`, sus tres `CHECK` de no negatividad, `uq_concepto_obra_id_codigo` y los cuatro índices. ~55 líneas | TC-01 (sus cuatro tablas), TC-10 (concepto), TC-11, TC-12, TC-13 (concepto) | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt011_estructura.py` | ✓ Hecho |
| A4 | `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo` con `ck_apu_cargo_tipo`, sus trece `CHECK` de no negatividad y los cuatro índices. ~60 líneas | TC-01 (completo para las doce tablas), TC-08 y TC-09 (cargo de APU), TC-13 (completo para las diecisiete columnas de a), TC-15 (`apu_cargo.porcentaje`; movido desde A3 durante la ejecución porque `apu_cargo` nace en A4) | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt011_estructura.py` | ✓ Hecho |
| A5 | `_BAJADA` de `v0006` y docstring con el plan de reversa. ~25 líneas | TC-16, TC-17, TC-18, TC-INV-1 a TC-INV-6 (parte a) | `desarrollador-sql` | `sonnet` · permisos de un rol (TC-18, TC-INV-1 a TC-INV-3) | `uv run --env-file ../.env alembic upgrade 0006`, `downgrade 0005` y `upgrade 0006` en local; `uv run pytest tests/test_tkt011_regresion.py tests/test_tkt057_migracion.py tests/test_tkt007_esquema.py tests/test_tkt006_esquema.py tests/test_identidad_migracion.py tests/test_identidad_migracion_ciclo.py tests/test_identidad_migracion_cli.py` | ⚠ Ajustado |
| A6 | Documentación `M8` parte a y ADR-030 (ver «Documentación afectada»). Sin código | `CA-21` parte a | `desarrollador-sql` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; la tabla de nulabilidad de este diseño coincide con `COLUMNAS_ESPERADAS` de TC-01 | ⚠ Ajustado |
| A7 | Cierre: los mutantes MA-1 a MA-6 y la suite completa | `CA-1` a `CA-3`, `CA-8`, `CA-11` a `CA-14`, `CA-17`, `CA-18`, `CA-20`, `CA-R1` a `CA-R6` en su parte | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante se aplica, se ve el test en rojo, se revierte; la salida va a `impl.md`. Después `uv run pytest`, `ruff check .`, `ruff format --check .`, `mypy .`, `lint-imports`, `python -m herramientas.verificar_float` en verde | ✓ Hecho |

**Notas de estado:** A5 y A6 se ajustan según lo anotado en `sdd/tickets/tkt-011/impl.md`: la bajada de `v0006` ya existía desde A4, y A6 incluyó la edición de una prueba de otro ticket (conteo de ADR).

### Entrega TKT-011b · línea base, importación, disparadores y permisos (`0007`)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B1 | `v0007` con `linea_base`, `ck_linea_base_estado`, `ck_linea_base_importe_venta_no_negativo`, `uq_linea_base_obra_id_congelada`, `ix_linea_base_obra_id`, `presupuesto_proteger_linea_base()` y `trg_linea_base_solo_avanza`; fábrica `DatosPresupuesto` (parte b). ~65 líneas | TC-20 (`linea_base`), TC-21, TC-22, TC-28 (línea base), TC-33 (`linea_base`), TC-40, TC-41, TC-42 | `desarrollador-sql` | `sonnet` · disparador de inmutabilidad | `uv run pytest tests/test_tkt011_linea_base.py -k "ca04 or ca16 or ca01"` | ✓ Hecho |
| B2 | `linea_base_concepto` y `explosion_presupuesto` con sus `CHECK`, `uq_explosion_presupuesto_linea_tipo_insumo`, `ix_linea_base_concepto_linea_base_id`, `presupuesto_proteger_copia_congelada()` y sus dos disparadores. ~70 líneas | TC-20 (las dos tablas), TC-25, TC-33 (las dos tablas), TC-35, TC-36, TC-37, TC-38, TC-39, TC-C2 | `desarrollador-sql` | `sonnet` · disparador de inmutabilidad y concurrencia | `uv run pytest tests/test_tkt011_linea_base.py`; medición E-13 anotada en `impl.md` | ✓ Hecho |
| B3 | `presupuesto_control` con sus `CHECK` y su `UNIQUE`. ~20 líneas | TC-20 (`presupuesto_control`), TC-23, TC-24, TC-33 (`presupuesto_control`) | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt011_linea_base.py -k "ca05 or ca13"` | ⚠ Ajustado |
| B4 | `REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion`. ~3 líneas | TC-43, TC-44, TC-45, TC-46, TC-C1, TC-INV-3 (parte b) | `desarrollador-sql` | `sonnet` · permisos de un rol y bloqueo pesimista | `uv run pytest tests/test_tkt011_permisos.py tests/test_identidad_permisos_tablas.py tests/test_identidad_privilegios_por_omision.py` | ✓ Hecho |
| B5 | `importacion`, `importacion_error` y `rendimiento_observado` con sus `CHECK` y sus dos índices. ~50 líneas | TC-20 (completo para las siete tablas), TC-26, TC-27, TC-28 y TC-29 (completos, las seis filas), TC-30, TC-31, TC-32, TC-33 (completo), TC-34 | `desarrollador-sql` | `haiku` | `uv run pytest tests/test_tkt011_importacion.py tests/test_tkt011_estructura.py` | ⚠ Ajustado |
| B6 | `_BAJADA` de `v0007` con la guarda (`LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` antes de comprobar; `estado <> 'BORRADOR'`, con `IN001` y el mensaje `Hay al menos una línea base CONGELADA o SUPERSEDIDA (RN-01, invariante 14): la bajada de 0007 no la elimina. Respáldala con pg_dump; el retiro de una línea base que no es borrador lo decide la persona dueña y se hace fuera de esta migración.`) y docstring con el plan de reversa. ~25 líneas | TC-47, TC-48, TC-49, TC-50, TC-INV-4, TC-INV-5 y TC-INV-6 (parte b) | `desarrollador-sql` | `haiku` | `uv run --env-file ../.env alembic upgrade 0007`, `downgrade 0006` y `upgrade 0007` en local; `uv run pytest tests/test_tkt011_migracion_linea_base.py tests/test_tkt011_regresion.py tests/test_tkt006_esquema.py tests/test_tkt007_esquema.py tests/test_tkt057_migracion.py tests/test_identidad_migracion_cli.py` (estas dos últimas bajan desde la cabeza: `test_tkt006_esquema.py:149-174` a `0003` y `test_identidad_migracion_cli.py:121-144` a `base`) | ⚠ Ajustado |
| B7 | Documentación `M8` parte b y ADR-031 (ver «Documentación afectada»). Sin código | `CA-21` | `desarrollador-sql` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py` (el diagrama de §9 con `DESCARTADO`) | ✓ Hecho |
| B8 | Cierre: los mutantes MB-1 a MB-15 y la suite completa | Todos los de TKT-011b y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante se aplica, se ve el test en rojo, se revierte; la salida va a `impl.md`. Después todo el trabajo `backend` en verde | ✓ Hecho |

**Notas de estado:** B3 y B5 se ejecutaron agrupadas en un mismo ciclo TDD, en lugar de uno por fila. B6 se ajustó por la guarda ampliada (`CONGELADA` o `SUPERSEDIDA`, con `estado <> 'BORRADOR'`) y el `LOCK TABLE` previo a la comprobación.

**Modelo:** `haiku` por omisión; `sonnet` solo donde la fila cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo), citado en la columna. Ninguna fila va en `opus`.

## Experimentos previos

Ninguno se ejecutó al diseñar: esta sesión no tiene intérprete de órdenes. Los ejecuta `desarrollador-sql` en la fila A0, contra `docker run --rm -e POSTGRES_USER=cimenta_migracion -e POSTGRES_PASSWORD=… postgres:18.6` y un guion `psql` o psycopg en el directorio temporal. Los respaldados por documentación de PostgreSQL consultada con Context7 lo dicen; la documentación no sustituye al experimento.

| # | Afirmación | Experimento | Resultado esperado | Fuente |
|---|---|---|---|---|
| E-1 | `SELECT … FOR UPDATE` y `FOR SHARE` exigen `UPDATE` además de `SELECT` | Tabla `t`; rol `r` con solo `SELECT`; `SELECT * FROM t FOR UPDATE` y `FOR SHARE` como `r`; después `GRANT UPDATE` y repetir | `42501` las dos primeras; funcionan tras el `GRANT` | Documentación de `SELECT`, cláusula de bloqueo |
| E-2 | `SELECT … FOR UPDATE` no dispara un disparador `BEFORE UPDATE … FOR EACH ROW` | Disparador que lanza en todo `UPDATE`; `SELECT … FOR UPDATE` sobre una fila | El `SELECT` termina sin error | `(sin ejecutar)` |
| E-3 | `TRUNCATE` no dispara disparadores `ON DELETE` de fila | Disparador `BEFORE DELETE` que lanza; `TRUNCATE t` como propietario | La tabla queda vacía sin error | Documentación de `TRUNCATE` |
| E-4 | `RAISE EXCEPTION USING ERRCODE = 'IN001', CONSTRAINT = TG_NAME, TABLE = TG_TABLE_NAME` llega a psycopg con `sqlstate == "IN001"`, `diag.constraint_name` y `diag.table_name`, como `psycopg.DatabaseError` | Disparador con ese `RAISE`; capturar la excepción e imprimir clase, `sqlstate`, `diag.message_primary`, `diag.constraint_name` y `diag.table_name` | `IN001`, el nombre del disparador, el de la tabla, y la clase base `DatabaseError` | Documentación de PL/pgSQL §41.9 para `ERRCODE` y `CONSTRAINT`; la clase en psycopg `(sin ejecutar)` |
| E-5 | `cimenta_migracion` es superusuario en la suite | `SELECT rolsuper FROM pg_roles WHERE rolname = 'cimenta_migracion'` en el contenedor de testcontainers | `true` | ADR de roles de PostgreSQL |
| E-6 | Una tabla creada por `cimenta_migracion` tras `0001` nace con `SELECT, INSERT, UPDATE, DELETE` para la aplicación y `SELECT` para la lectura, sin `TRUNCATE` | Ya ejecutado: TC-31 y TC-32 de TKT-003 están en verde en `Produccion` | Lo que afirman esas pruebas | `test_identidad_privilegios_por_omision.py` |
| E-7 | Un valor fuera de un `ENUM` responde `22P02` sin `constraint_name`, y un `CHECK` responde `23514` con él | Columna `ENUM` y columna `text` con `CHECK`; insertar un valor ajeno con parámetro de psycopg | `22P02` con `constraint_name` nulo; `23514` con el nombre. El `23514` con nombre ya lo prueba TC-10 de TKT-057 | `(sin ejecutar)` para el `ENUM` |
| E-8 | Un índice único parcial que se viola responde `23505` con `diag.constraint_name` igual al nombre del índice | Índice `uq_x … WHERE estado = 'CONGELADA'`; dos inserciones | `23505` y `constraint_name = 'uq_x'` | `(sin ejecutar)` |
| E-9 | Con `FOR SHARE` en el disparador, una inserción concurrente espera a la transacción que congela y, al confirmar esta, lee `CONGELADA` | Conexión A: `BEGIN; UPDATE linea_base SET estado = 'CONGELADA'`. Conexión B: `SET lock_timeout = '200ms'` e inserción de copia → `55P03`. A confirma; B inserta de nuevo → `IN001`. Repetir sin `FOR SHARE`: B inserta sin esperar | `55P03` y después `IN001` con `FOR SHARE`; inserción aceptada sin él | `(sin ejecutar)` |
| E-10 | Un identificador de 64 caracteres se trunca a 63 con un aviso y sin error | `CREATE TABLE t (a int CONSTRAINT <64 caracteres> CHECK (a > 0))` | Aviso `42622` y nombre truncado | `(sin ejecutar)` |
| E-11 | `(to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado')` es falso si solo cambia `estado` y verdadero si cambia una columna `numeric`, `timestamptz` o `uuid` | Disparador de prueba que registra el resultado en un `RAISE NOTICE` | Falso y verdadero, respectivamente | `(sin ejecutar)` |
| E-12 | Con el `env.py` del proyecto, toda la cadena de una bajada corre en una transacción: un `RAISE` en `0007` no deja ninguna tabla borrada y `alembic_version` sigue en la cabeza | Ya lo demuestra TC-17 de TKT-007, en verde; se repite en TC-48 | Lo que afirma esa prueba | Documentación de Alembic, «Sharing a Connection» |
| E-13 | El `FOR SHARE` de cada fila no encarece el congelado de una obra real | En B2, con el rol de aplicación, una transacción inserta 5,000 copias de concepto y 300 renglones de explosión y congela; se anota la duración | Se registra la cifra en `impl.md`; si supera los 15 s de `statement_timeout`, `/sdd-escalar` | `(sin ejecutar)` |

## Plan de pruebas

Toda prueba se conecta con `conectar("aplicacion" | "migracion" | "lectura", base)` de `conftest.py`, nunca con el propietario por otra vía. Las de catálogo leen con el rol de migración, que ve todo. Todo rechazo comprueba el `SQLSTATE`, `diag.constraint_name` (o `diag.column_name` en `23502`), `diag.table_name` y que la tabla no cambió (recuento o fotografía de la fila antes y después).

### TKT-011a

| # | Caso | Tipo | Criterio | Rol |
|---|---|---|---|---|
| TC-01 | `test_tkt011_ca01_tablas_de_estructura_con_su_forma`: para cada una de las doce tablas, `information_schema.columns` (`column_name`, `data_type`, `numeric_precision`, `numeric_scale`, `is_nullable`, `column_default`) es igual a `COLUMNAS_ESPERADAS`, copia literal de la tabla de nulabilidad | feliz | `CA-1` esc. 1 | migración |
| TC-02 | `test_tkt011_ca01_claves_foraneas_sin_cascada`: toda clave foránea de las doce tablas tiene `confdeltype = 'r'`; borrar una `obra` con un `nivel` responde `23001` (`restrict_violation`, el que emite `ON DELETE RESTRICT`; el `23503` es el de insertar un hijo huérfano) con `fk_nivel_obra_id` y la obra sigue | **rechazo** | `CA-1`, `PA-T8` | aplicación |
| TC-03 | `test_tkt011_ca01_obra_sin_empresa_la_rechaza_not_null`: `23502` con `column_name = 'empresa_id'`; cero obras | **rechazo** | `CA-1` esc. 2 | aplicación |
| TC-04 | `test_tkt011_ca02_dias_semana_laboral_vale_seis_por_omision`: insertada sin la columna, se lee `6`; catálogo `smallint`, `NO` | feliz | `CA-2` esc. 1 | aplicación |
| TC-05 | `test_tkt011_ca02_obra_con_empresa_inexistente_la_rechaza_la_clave_foranea`: `23503` con `fk_obra_empresa_id`; cero obras | **rechazo** | `CA-2` esc. 2 | aplicación |
| TC-06 | `test_tkt011_ca03_codigo_de_obra_repetido_lo_rechaza_la_base`: segunda `AP-058-25`, `23505` con `uq_obra_codigo`; sigue una sola fila con ese código | **rechazo** | `CA-3` esc. 1 · `HDU-001 esc. 3` | aplicación |
| TC-07 | `test_tkt011_ca03_otro_codigo_de_obra_se_acepta`: `AP-059-25` entra | feliz | `CA-3` esc. 2 | aplicación |
| TC-08 | `test_tkt011_ca08_valor_fuera_del_conjunto_cerrado_lo_rechaza_la_base`, parametrizada: obra `BORRADA` (`ck_obra_estado`), obra con `tipo_contrato = 'OTRO'` (`ck_obra_tipo_contrato`), insumo `EQUIPO` (`ck_insumo_tipo`), cargo `PROPINA` (`ck_apu_cargo_tipo`); `23514` en todas y cero filas nuevas | **rechazo** | `CA-8` esc. 1 | aplicación |
| TC-09 | `test_tkt011_ca08_valores_admitidos_se_aceptan`: los cuatro estados de obra, los cuatro tipos de insumo y los siete de cargo entran | feliz | `CA-8` esc. 2 | aplicación |
| TC-10 | `test_tkt011_ca11_unidad_fuera_del_catalogo_la_rechaza_la_base` (concepto `M3` → `ck_concepto_unidad`, insumo `LITRO` → `ck_insumo_unidad`, `23514`) y `test_tkt011_ca11_las_ocho_unidades_se_aceptan_en_concepto_e_insumo` | **rechazo** y feliz | `CA-11` · `HDU-001 esc. 8` | aplicación |
| TC-11 | `test_tkt011_ca12_concepto_repetido_en_la_obra_lo_rechaza_la_base`: `620001` dos veces en la obra A, `23505` con `uq_concepto_obra_id_codigo`; sigue uno | **rechazo** | `CA-12` esc. 1 · `HDU-001 esc. 9` | aplicación |
| TC-12 | `test_tkt011_ca12_el_mismo_codigo_en_otra_obra_se_acepta` | feliz | `CA-12` esc. 2 | aplicación |
| TC-13 | `test_tkt011_ca13_negativo_lo_rechaza_la_base`, parametrizada por las diecisiete columnas de a: con `Decimal("-0.0001")`, `23514` con `ck_<tabla>_<columna>_no_negativo` y cero filas; con `Decimal("0")`, la fila entra. `obra.umbral_alerta_pct` usa `-0.000001` por su escala | **rechazo** y borde | `CA-13` | aplicación |
| TC-14 | `test_tkt011_ca14_porcentaje_de_obra_fuera_de_rango`, parametrizada con las filas de obra de `CA-14` (`0.150000` entra, `1.500000` y `-0.01` en `retencion` y `fondo` dan `23514` con su `ck_…_rango`, `umbral` nulo entra, `-0.5` da `23514`), más `umbral = 1.500000` entra y `fondo = 1.000000` entra (borde superior) | **rechazo** y borde | `CA-14` · `PA-T5` | aplicación |
| TC-15 | `test_tkt011_ca14_porcentaje_de_cargo_sin_tope`: `apu_cargo.porcentaje = 2.500000` entra y `-0.000001` da `23514` con `ck_apu_cargo_porcentaje_no_negativo` | **rechazo** y borde | `CA-14` | aplicación |
| TC-16 | `test_tkt011_ca18_0006_sube_baja_y_vuelve_a_subir`: sobre `base_vacia`, `upgrade 0006`, fotografía (tablas, columnas, restricciones con `pg_get_constraintdef`, índices con `indexdef`, `relacl`), `downgrade 0005` (ninguna de las doce tablas, versión `0005`), `upgrade 0006` y fotografía igual a la primera. La precondición exige que la fotografía tenga las doce tablas | feliz | `CA-18` | migración |
| TC-17 | `test_tkt011_ca20_restricciones_e_indices_con_nombre`: el conjunto de `conname` y de `indexname` de las doce tablas es exactamente el de este diseño, y cada nombre empieza por el prefijo de su tipo | feliz | `CA-20` | migración |
| TC-18 | `test_tkt011_ca17_privilegios_de_las_tablas_de_estructura`: por `aclexplode(relacl)`, la aplicación tiene exactamente `SELECT, INSERT, UPDATE, DELETE` y la lectura exactamente `SELECT` en las doce; `has_table_privilege` sin `TRUNCATE` para la aplicación; un `INSERT` real en `empresa` con el rol de lectura responde `42501` y la tabla sigue vacía | **rechazo** | `CA-17` esc. 3 y 4 en su parte | migración y lectura |
| TC-INV-1 | `test_tkt011_car1_bitacora_sigue_permanente`: aplicación con exactamente `INSERT, SELECT` sobre `bitacora`; `usuario_id` `NO` | regresión | `CA-R1` | migración |
| TC-INV-2 | `test_tkt011_car2_intento_acceso_solo_se_anexa`: exactamente `SELECT, INSERT` | regresión | `CA-R2` | migración |
| TC-INV-3 | `test_tkt011_car3_lectura_sin_secretos_ni_escritura`: `SELECT * FROM sesion` y `SELECT password_hash FROM usuario` con lectura responden `42501`; ninguna tabla del módulo concede a la lectura algo distinto de `SELECT` | regresión | `CA-R3` | lectura y migración |
| TC-INV-4 | `test_tkt011_car4_una_sola_cabeza_y_0006_cuelga_de_0005`: `ScriptDirectory.get_heads()` tiene un elemento; la revisión `0006` existe y su `down_revision` es `"0005"`. No afirma qué revisión es la cabeza | regresión | `CA-R4` | sin base |
| TC-INV-5 | `test_tkt011_car5_claves_foraneas_externas_solo_a_usuario`: toda clave foránea de las doce tablas apunta a una de ellas o a `usuario` | regresión | `CA-R5` | migración |
| TC-INV-6 | `test_tkt011_car6_ningun_flotante`: ninguna columna de las doce es `real` ni `double precision` | regresión | `CA-R6` | migración |

### TKT-011b

| # | Caso | Tipo | Criterio | Rol |
|---|---|---|---|---|
| TC-20 | `test_tkt011_ca01_tablas_de_linea_base_e_importacion_con_su_forma`: igual que TC-01 para las siete tablas, y `timestamptz` en `congelada_en`, `capturado_en`, `actualizado_en`, `creado_en`, `latido` y `calculado_en` | feliz | `CA-1` | migración |
| TC-21 | `test_tkt011_ca04_segunda_linea_base_congelada_la_rechaza_la_base`: `23505` con `uq_linea_base_obra_id_congelada`; la obra sigue con una `CONGELADA` | **rechazo** | `CA-4` esc. 1 · `HDU-001 esc. 19` | aplicación |
| TC-22 | `test_tkt011_ca04_congelada_junto_a_supersedida_y_borrador`: las tres entran en la obra A y una `CONGELADA` entra en la obra B | feliz | `CA-4` esc. 2 | aplicación |
| TC-23 | `test_tkt011_ca05_control_repetido_lo_rechaza_la_base`: `(L, MUROS)` dos veces, `23505` con `uq_presupuesto_control_linea_base_id_tipo_partida_id`; `(L, ENCHAPES)` entra | **rechazo** | `CA-5` esc. 1 | aplicación |
| TC-24 | `test_tkt011_ca05_tope_y_auditoria_admiten_nulo` | feliz | `CA-5` esc. 2 | aplicación |
| TC-25 | `test_tkt011_ca06_explosion_repetida_la_rechaza_la_base`: `(L, MUROS, I)` dos veces, `23505` con `uq_explosion_presupuesto_linea_tipo_insumo`; `(L, ENCHAPES, I)` entra. Sobre una `BORRADOR`, para que el disparador no intervenga | **rechazo** | `CA-6` | aplicación |
| TC-26 | `test_tkt011_ca07_importacion_sin_clave_foranea_al_archivo`: `archivo_id` es `uuid` sin restricción en `pg_constraint`; ninguna columna contiene `nombre` ni `url`; `latido` y `progreso` con su tipo y nulables | feliz | `CA-7` esc. 1 | migración |
| TC-27 | `test_tkt011_ca07_archivo_inexistente_se_acepta` | feliz | `CA-7` esc. 2 | aplicación |
| TC-28 | `test_tkt011_ca08_los_siete_conjuntos_cerrados_responden_23514`, parametrizada con las seis filas de `CA-8` más `tipo_contrato`; cada una `23514` con su `ck_…` y cero filas, y el conjunto de `SQLSTATE` observados es `{"23514"}` | **rechazo** | `CA-8` esc. 1 | aplicación |
| TC-29 | `test_tkt011_ca08_estados_y_tipos_admitidos_se_aceptan`: los seis estados de importación, los siete tipos de error y los tres estados de línea base | feliz | `CA-8` esc. 2 | aplicación |
| TC-30 | `test_tkt011_ca09_sin_conceptos_sin_fila_ni_columna` (entra) y `test_tkt011_ca09_error_sin_mensaje_lo_rechaza_not_null` (`23502`, `column_name = 'mensaje'`, cero filas) | feliz y **rechazo** | `CA-9` · `HDU-001 esc. 27` | aplicación |
| TC-31 | `test_tkt011_ca10_rendimiento_observado_vacio_y_separado`: cero filas; ninguna clave foránea entre las dos tablas en ningún sentido; `relkind = 'r'` en las dos; `attgenerated = ''` en `rendimiento_congelado` | feliz | `CA-10` esc. 1 · `RN-24` | migración |
| TC-32 | `test_tkt011_ca10_escribir_el_observado_no_toca_la_explosion`: fotografía de `explosion_presupuesto` igual antes y después de insertar en `rendimiento_observado` | feliz | `CA-10` esc. 2 | aplicación |
| TC-33 | `test_tkt011_ca13_negativo_lo_rechaza_la_base`, parametrizada por las catorce columnas de b, igual que TC-13. Las copias, sobre una línea base `BORRADOR` | **rechazo** y borde | `CA-13` | aplicación |
| TC-34 | `test_tkt011_ca14_progreso_de_cero_a_uno_se_acepta` y `test_tkt011_ca14_progreso_fuera_de_cero_a_uno_lo_rechaza_la_base`: `1.000000` y nulo entran; `1.000001` y `-0.000001` dan `23514` con `ck_importacion_progreso_rango` | **rechazo** y borde | `CA-14` | aplicación |
| TC-35 | `test_tkt011_ca15_copia_de_linea_base_congelada_la_rechaza_el_disparador`, parametrizada por las seis sentencias de `CA-15`: `IN001`, mensaje que empieza por `RN-01:`, `diag.constraint_name` igual a `trg_linea_base_concepto_inmutable` o `trg_explosion_presupuesto_inmutable`, `diag.table_name`; las filas iguales que antes | **rechazo** | `CA-15` esc. 1 · `RN-01` · `HDU-001 esc. 18` | **migración** |
| TC-36 | `test_tkt011_ca15_copia_de_linea_base_supersedida_la_rechaza_el_disparador`: las mismas seis sobre una `SUPERSEDIDA` | **rechazo** | `CA-15` esc. 2 · `PA-T6` | migración |
| TC-37 | `test_tkt011_ca15_mover_una_copia_entre_lineas_base_lo_rechaza_el_disparador`: `UPDATE … SET linea_base_id` de una congelada a un borrador, y de un borrador a una congelada; `IN001` en las dos | **rechazo** | `CA-15` esc. 1 | migración |
| TC-38 | `test_tkt011_ca15_borrador_se_prepara_sin_el_disparador`: `INSERT`, `UPDATE` y `DELETE` sobre copias de un `BORRADOR` terminan sin error | feliz | `CA-15` esc. 3 | migración |
| TC-39 | `test_tkt011_ca15_el_congelado_ocurre_en_una_transaccion`: con el rol de aplicación y `autocommit=False`, se insertan dos copias y dos renglones en un `BORRADOR`, se pasa a `CONGELADA`, un `SAVEPOINT`, una tercera copia responde `IN001`, `ROLLBACK TO SAVEPOINT`, `COMMIT`; otra conexión lee `CONGELADA` y dos copias | feliz y **rechazo** | `CA-15` esc. 4 | aplicación |
| TC-40 | `test_tkt011_ca16_transicion_de_la_linea_base_se_acepta` y `test_tkt011_ca16_transicion_de_la_linea_base_se_rechaza`, parametrizadas por las seis filas de `CA-16`, más `CONGELADA` → `CONGELADA` sin cambios (rechazo): los rechazos con `IN001`, prefijo `RN-01:` y `trg_linea_base_solo_avanza`; la fila igual que antes | **rechazo** y feliz | `CA-16` esc. 1 · `PA-T14` | migración |
| TC-41 | `test_tkt011_ca16_una_congelada_no_cambia_mas_que_su_estado`, parametrizada por `obra_id`, `version`, `motivo`, `importe_venta`, `congelada_en`, `congelada_por_id`, `creado_en` y `creado_por_id`, más `CONGELADA` → `SUPERSEDIDA` cambiando `importe_venta` en la misma sentencia: `IN001` y la fila intacta | **rechazo** | `CA-16` esc. 2 | migración |
| TC-42 | `test_tkt011_ca16_no_se_borra_una_linea_base_que_no_es_borrador`: `DELETE` de una `CONGELADA` y de una `SUPERSEDIDA` **sin copias** responde `IN001` (no `23503`); `DELETE` de un `BORRADOR` sin copias se acepta; el de un `BORRADOR` con copias responde `23001` con `fk_linea_base_concepto_linea_base_id` | **rechazo** y feliz | `CA-16` esc. 3 | migración |
| TC-43 | `test_tkt011_ca17_la_copia_de_conceptos_solo_se_anexa`: `relacl` de la aplicación sobre `linea_base_concepto` es exactamente `{SELECT, INSERT}`; sobre una copia de un **`BORRADOR`**, `UPDATE` y `DELETE` con la aplicación responden `42501` y la fila sigue; la misma sentencia con el rol de migración sí cambia la fila (control de que el `42501` es del privilegio y no del disparador) | **rechazo** | `CA-17` esc. 1 · invariante 14 | aplicación y migración |
| TC-44 | `test_tkt011_ca17_el_bloqueo_pesimista_funciona_con_la_aplicacion`: con el rol de aplicación, `SELECT … FOR UPDATE` sobre `presupuesto_control` y sobre `explosion_presupuesto` de una línea base **`CONGELADA`** devuelve sus filas; `relacl` de la aplicación incluye `UPDATE` en las dos | feliz | `CA-17` esc. 2 · ADR-004 · `HDU-002 esc. 9` | aplicación |
| TC-C1 | `test_tkt011_ca17_el_bloqueo_pesimista_excluye_a_la_segunda_transaccion`: la conexión A toma `FOR UPDATE` sobre `(L, MUROS)` en las dos tablas; la conexión B, con el rol de aplicación, pide lo mismo con `NOWAIT` y recibe `55P03`; A confirma y B lo obtiene | concurrencia | `CA-17` esc. 2 · ADR-004 | aplicación × 2 |
| TC-45 | `test_tkt011_ca17_la_aplicacion_congela_pero_no_vacia`: la aplicación tiene `UPDATE` sobre `linea_base`; `has_table_privilege(…, 'TRUNCATE')` es falso en las diecinueve; `TRUNCATE linea_base_concepto` con la aplicación responde `42501` y la tabla conserva sus filas | **rechazo** | `CA-17` esc. 3 · `PA-T15` | aplicación y migración |
| TC-46 | `test_tkt011_ca17_el_rol_de_lectura_no_escribe`: la lectura tiene exactamente `{SELECT}` en las diecinueve; `INSERT` real en `linea_base` con lectura responde `42501` y la tabla sigue vacía | **rechazo** | `CA-17` esc. 4 · `CA-R3` | lectura y migración |
| TC-C2 | `test_tkt011_ca15_una_copia_concurrente_no_entra_tras_el_congelado`: conexión A (aplicación, transacción abierta) pasa L de `BORRADOR` a `CONGELADA` sin confirmar; conexión B (aplicación) con `SET lock_timeout = '200ms'` intenta insertar una copia de L y recibe `55P03`; A confirma; B lo intenta otra vez y recibe `IN001`; L conserva sus copias originales | concurrencia y **rechazo** | `CA-15` esc. 4 · `M5` | aplicación × 2 |
| TC-47 | `test_tkt011_ca18_0007_sube_baja_y_vuelve_a_subir`: como TC-16 entre `0006` y `0007`, con la fotografía ampliada a `pg_trigger` (nombre, tabla, `tgtype`, función) y a `pg_proc` (`prosrc` de las dos funciones) | feliz | `CA-18` | migración |
| TC-48 | `test_tkt011_ca19_no_se_baja_con_una_linea_base_congelada`, parametrizada por `CONGELADA` y `SUPERSEDIDA`: `downgrade 0006` lanza `IN001` con un texto que contiene `línea base CONGELADA o SUPERSEDIDA`; la versión sigue en la cabeza leída de `ScriptDirectory`, las siete tablas existen y las filas son las mismas | **rechazo** | `CA-19` esc. 1 | migración |
| TC-49 | `test_tkt011_ca19_solo_con_borradores_la_bajada_elimina_las_tablas`: con solo `BORRADOR` (ninguna `CONGELADA` ni `SUPERSEDIDA`), `downgrade 0006` termina y ninguna de las siete tablas ni las dos funciones existen | feliz | `CA-19` esc. 2 | migración |
| TC-50 | `test_tkt011_ca20_restricciones_indices_y_disparadores_con_nombre`: como TC-17 para las siete tablas, más los tres `tgname` con prefijo `trg_` | feliz | `CA-20` | migración |
| TC-INV-4b · 5b · 6b | `test_tkt011_car4_0007_cuelga_de_0006`, `test_tkt011_car5_…` y `test_tkt011_car6_…` para las siete tablas | regresión | `CA-R4` a `CA-R6` | migración |

### Mutación

Cada mutante se aplica a mano sobre la migración, se ejecuta la prueba indicada, se ve en rojo y se revierte. Lo que se mutó y qué cayó se pega en `impl.md`.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| MA-1 | `ck_concepto_cantidad_no_negativo` con `> 0` en lugar de `>= 0` | TC-13 (`concepto.cantidad`, borde 0) |
| MA-2 | `ck_obra_fondo_garantia_pct_rango` con `< 1` en lugar de `<= 1` | TC-14 (`fondo = 1.000000`) |
| MA-3 | Quitar `ck_insumo_unidad` | TC-10 |
| MA-4 | `uq_concepto_obra_id_codigo` sobre `(codigo)` solo | TC-12 |
| MA-5 | `fk_nivel_obra_id` con `ON DELETE CASCADE` | TC-02 |
| MA-6 | `obra.umbral_alerta_pct` `NOT NULL` | TC-01 y TC-14 |
| MB-1 | La condición de la copia es `= 'CONGELADA'` en lugar de `<> 'BORRADOR'` | TC-36 |
| MB-2 | El disparador de copias sin `INSERT` (`BEFORE UPDATE OR DELETE`) | TC-35 (dos `INSERT`) y TC-39 |
| MB-3 | En `UPDATE` de una copia se comprueba solo `NEW.linea_base_id` | TC-37 (de congelada a borrador) |
| MB-4 | Sin `FOR SHARE` en la lectura del estado | TC-C2 |
| MB-5 | `presupuesto_proteger_linea_base` admite `CONGELADA` → `BORRADOR` | TC-40 |
| MB-6 | Sin la comparación de columnas | TC-41 |
| MB-7 | El `DELETE` se admite en cualquier estado | TC-42 (`IN001` esperado en una `CONGELADA` sin copias) |
| MB-8 | `ERRCODE` omitido (sale `P0001`) | TC-35, TC-40 |
| MB-9 | Sin el `REVOKE` sobre `linea_base_concepto` | TC-43 |
| MB-10 | `REVOKE UPDATE ON explosion_presupuesto FROM cimenta_aplicacion` añadido | TC-44 y TC-C1 (`42501`) |
| MB-11 | La bajada sin la guarda | TC-48 |
| MB-12 | `uq_linea_base_obra_id_congelada` sin `WHERE` | TC-22 |
| MB-13 | `GRANT TRUNCATE ON linea_base_concepto TO cimenta_aplicacion` | TC-45 |
| MB-14 | Sin el disparador de `explosion_presupuesto` (queda el de conceptos) | TC-35 y TC-36, filas de explosión |
| MB-15 | Leer `OLD.linea_base_id` en `INSERT` | TC-35 |

## Impacto

Análisis del arquitecto; `revisor-impacto` lo revisa antes del gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Cadena de migraciones: `0006` y `0007` | TC-12 y TC-13 de TKT-057 fijan la cabeza en `0005` | Se ponen rojas con cualquier migración nueva | Fila A1, con aprobación (P3); regla de no afirmar la cabeza por número |
| Bajadas de TKT-006, TKT-007 y TKT-057 (`downgrade 0003`, `0002`, `0004` desde la cabeza) | `test_tkt006_ca17_la_migracion_se_revierte`, `test_tkt007_ca10_*`, TC-13 de TKT-057 | Ahora atraviesan las bajadas de `0007` y `0006` | Sobre bases sin línea base `CONGELADA` ni `SUPERSEDIDA`, que es lo que usan: la guarda no salta. TC-17 de TKT-007 sigue confiando en la transacción única (E-12) |
| `conftest.py`: sección «TKT-011» con `DatosPresupuesto` | Todas las pruebas | Una fixture con `autouse` cambiaría pruebas ajenas | Sin `autouse` (TC-13 de TKT-004) |
| Privilegios por omisión de `0001` | Las diecinueve tablas | Ninguno: no se modifican | Solo un `REVOKE` sobre una tabla nueva |
| Esquema de `presupuesto` | TKT-010, TKT-012 a TKT-018, TKT-019 y siguientes, TKT-039 | La nulabilidad elegida rechaza datos que un ticket futuro considere válidos | Gate de la tabla de nulabilidad (P5); una columna se relaja con una migración propia |
| `linea_base_concepto.concepto_id` con `RESTRICT` | TKT-017 al reimportar un borrador | Un `concepto` copiado en una línea base no se puede borrar | Es lo deseado: las copias congeladas no pierden su origen. TKT-017 reemplaza el borrador, no los conceptos de una línea base ya congelada |
| Disparador `FOR SHARE` | TKT-017 | Dos congelados concurrentes del mismo borrador pueden interbloquearse (`40P01`) | PostgreSQL aborta uno; un congelado doble del mismo borrador es un error de uso. E-13 mide el coste |

**Revisión de `revisor-impacto` (veredicto: diseño incompleto, frontera cruzada: no).** Seis hallazgos, ya incorporados arriba: H1 (alta) el conteo de ADR lo fija una prueba de `tools/tests`, no `verificar_docs.py`; H2 (alta) TKT-012 depende de la mitad b y las fichas «Depende de TKT-011» necesitan reasignarse; H3 (media) textos «`UPDATE` y `DELETE`» desfasados en `CLAUDE.md`, arquitectura, ADR de snapshot, skill y agentes; H4 (media) la ficha de TKT-049 parece crear `dias_semana_laboral`; H5 (media-baja) las interacciones con TKT-017 (copias solo en la transacción de congelado, orden `SUPERSEDIDA` antes de `CONGELADA`, `importe_venta` en `BORRADOR`, traducción de `IN001`, `23505` y `23503`); H6 (baja) `Obra.actualizado_en` no admite `null` en el borrador OpenAPI, así que TKT-012 debe omitir el campo, y `verificar_float` no recorre migraciones: la garantía de `CA-R6` es TC-INV-6 contra `information_schema`. Comprobado por el revisor: `lint-imports` con 15 contratos mantenidos, `verificar_float` con 0 hallazgos, identificadores de 59 caracteres o menos, 34 `CHECK`, 12 índices y 32 claves foráneas (siete hacia `usuario`).

**Fronteras entre módulos:** No. Las únicas claves foráneas que salen del módulo apuntan a `usuario`, de `identidad`, que es ancestro de `presupuesto`; `importacion.archivo_id` no lleva clave foránea. No se escribe código de `cimenta/` y los quince contratos de `import-linter` no cambian.

## Documentación afectada

| Documento | Qué cambia | Ticket |
|---|---|---|
| `docs/03-modelo-datos.md` §2 | Fila «Enumeraciones»: `CHECK` con nombre cuando el rechazo debe nombrar la restricción; `accion_bitacora` queda como `ENUM` (P2) | a |
| `docs/03-modelo-datos.md` §4.1 | `obra` con `creado_*` y `actualizado_*`; `APU.concepto_id` deja de decir «único · 1:1» y dice que lo sostiene el caso de uso (`PA-T3`); el párrafo de `concepto.obra_id` deja de prometer una restricción de coherencia y remite al ticket futuro; `unidad` en `concepto` admite las ocho (`PA-T7`); el invariante 8 alcanza a todo importe, precio, cantidad y rendimiento | a |
| `docs/03-modelo-datos.md` §4.2 y §11 | `linea_base` con `creado_en` y `creado_por_id`; `explosion_presupuesto` con su `UNIQUE`; `importacion` con `creado_en` | b |
| `docs/03-modelo-datos.md` §13 | Invariante 8 ampliado; invariante 14 con `INSERT` en las copias, la fila `linea_base` que solo avanza, `FOR SHARE`, el `SQLSTATE` `IN001` y el prefijo `RN-01:`; nota de que `IN001` lo traduce TKT-017 | a (8) y b (14) |
| `docs/03-modelo-datos.md` §14, línea base | `trg_linea_base_solo_avanza` es quien impide volver a `BORRADOR` | b |
| `docs/03-modelo-datos.md` §15, índices | `explosion_presupuesto (linea_base_id, tipo_partida_id, insumo_id)` es único | b |
| `docs/05-tickets-trabajo.md`, ficha de TKT-011 | Subsección «Partición en dos tickets hermanos» con la tabla de este diseño; criterios técnicos alineados (`obra.codigo` único, `dias_semana_laboral`, `INSERT` en el disparador, fila `linea_base`, unicidad de la explosión) | a (partición) y b (criterios del disparador) |
| `docs/02-arquitectura.md` §9 | El diagrama de estados de la importación añade `DESCARTADO`: `VALIDADO --> DESCARTADO` y `CON_ERRORES --> DESCARTADO` («se descarta»), y `DESCARTADO --> [*]`, en lugar de `CON_ERRORES --> [*]`; coincide con `descartar_importacion` del borrador (`PA-T13`) | b |
| `docs/adr/` y `docs/adr/README.md` | ADR-030 (a) y ADR-031 (b), con su fila en el índice | a y b |
| `CLAUDE.md`, `README.md` y `llms.txt` | El conteo «29 decisiones» (o «29 ADRs») pasa a 30 y a 31. La premisa de la versión anterior de este diseño era falsa: `tools/verificar_docs.py` (líneas 201 a 211) solo compara los archivos de `docs/adr/` con el índice. Quien fija el «29» es `tools/tests/test_definicion_revision.py` (líneas 1875, 1927, 1957, 1986, 2012, 2062 a 2113), que corre en el trabajo de CI de `tools/tests` y se pondría rojo en cada PR. El cambio de `CLAUDE.md` lo aprueba la persona dueña | a y b |
| `tools/tests/test_definicion_revision.py` | Prueba de otro ticket, como A1. Dos opciones para el gate (P9): actualizar el número en cada PR, o generalizar la expresión regular una sola vez para que no dependa del número | a |
| `docs/05-tickets-trabajo.md`, líneas «Depende de TKT-011» | TKT-010, TKT-019, TKT-042, TKT-046 y TKT-049 pasan a depender de TKT-011a; TKT-012 y TKT-013 pasan a depender de TKT-011b; de 014 a 018 dependen de ellas. Sin esta fila, quien tome TKT-013 no sabrá qué mitad necesita | a |
| `docs/05-tickets-trabajo.md`, ficha de TKT-049 | Una línea que diga que TKT-049 solo consume `empresa.dias_semana_laboral` (`PA-T2`), porque hoy parece que la crea | a |
| `docs/05-tickets-trabajo.md`, ficha de TKT-017 | Tres restricciones que nacen del esquema: las copias de `linea_base_concepto` solo se escriben en la transacción de congelado (la aplicación no tiene `DELETE`), la `CONGELADA` anterior pasa a `SUPERSEDIDA` antes de congelar la nueva (si no, `23505`; `BORRADOR` → `SUPERSEDIDA` está prohibido), y debe traducir el `SQLSTATE` del disparador, `23505`, `23503` y `23001`. Pregunta abierta para TKT-017: con qué valor nace `importe_venta` en un `BORRADOR`, que es `NOT NULL` | b |
| `CLAUDE.md` regla 4, `docs/02-arquitectura.md` §7.6, `docs/adr/20260918-snapshot-linea-base.md`, `.claude/skills/conv-sql-postgres/SKILL.md` y `.claude/agents/desarrollador-sql.md` y `auditor-sql.md` | Textos que describen el disparador como «`UPDATE` y `DELETE`» y quedan desfasados al sumar `INSERT` y la fila `linea_base`. El ADR de snapshot recibe una nota que enlaza a ADR-031. Editar `.claude/` es meta-SDD: lo aprueba la persona dueña (P10) | b |
| `sdd/tickets/tkt-011/spec.md` | Los ajustes de «Criterios de la spec que hay que ajustar», si se aprueban P1 y P3 | a |

## ¿Merece ADR?

Sí, dos, en formato MADR, creados en `/sdd-ejecutar`:

- **ADR-030** · `docs/adr/20261101-catalogos-cerrados-por-check.md` (fila A6). Opciones: `CHECK` con nombre, `ENUM`, tabla de catálogo. Un recién llegado verá `ENUM` en `accion_bitacora` y `CHECK` en `presupuesto` y se preguntará por qué.
- **ADR-031** · `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` (fila B7). Opciones: dos disparadores con `SQLSTATE` propio frente a uno solo, frente a `P0001` con texto, frente a privilegios sin disparador; `FOR SHARE` frente a aceptar la carrera; `BEFORE TRUNCATE` descartado. Completa el ADR de copia física, que solo nombra `UPDATE` y `DELETE`.

La partición en dos tickets no necesita ADR: queda en la ficha de `docs/05`, como TKT-062.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-R4` promete que las pruebas de TKT-057 pasan «sin cambios», y TC-12 y TC-13 afirman la cabeza `0005` | Fila A1 con aprobación (P3) y ajuste de la redacción de `CA-R4`; regla de no afirmar la cabeza por número en las pruebas nuevas |
| 2 | Alta | Sin bloqueo, una inserción de copia concurrente con el congelado lee `BORRADOR` y entra después: `M5` solo valdría en serie | `FOR SHARE` en la lectura del estado, TC-C2 y el mutante MB-4 |
| 3 | Alta | La prueba del `DELETE` de una `CONGELADA` con copias quedaría verde por la clave foránea (`23503`) aunque el disparador no existiera | TC-42 borra una `CONGELADA` **sin copias** y exige `IN001`; MB-7 lo ata |
| 4 | Media | `CA-17` esc. 1 con el rol de aplicación queda verde por el privilegio, pero sobre una copia congelada no distinguiría privilegio de disparador | TC-43 usa una copia de un `BORRADOR` y comprueba que el rol de migración sí la cambia |
| 5 | Media | El `FOR UPDATE` probado sobre una línea base en borrador no demuestra que funcione en el caso real, que es una línea base congelada | TC-44 y TC-C1 bloquean filas de una `CONGELADA` (E-2) |
| 6 | Media | Comparar columnas una por una deja mutable cualquier columna que añada una migración futura | La comparación de la fila sin su estado por `to_jsonb` (E-11) |
| 7 | Media | La convención del modelo §2 dice `ENUM`; elegir `CHECK` en silencio la contradice | Se declara, se pregunta (P2) y se registra en ADR-030 |
| 8 | Baja | El rol de migración puede vaciar o desactivar los disparadores (`TRUNCATE`, `ALTER TABLE … DISABLE TRIGGER`, `session_replication_role`) | Se acepta como `PA-T15`: el dueño del esquema siempre puede retirar sus garantías; lo cubre la disciplina de acceso al rol de migración |

Pasada independiente de `abogado-del-diablo` (modo A, «diseñar»), sobre el diseño ya escrito. Las objeciones se resolvieron durante la ejecución: la resolución de cada una consta en `impl.md` y en `_index.md`. Las cinco objeciones son sustantivas y quedan abiertas para el gate.

| # | Severidad | Objeción | Acción propuesta |
|---|---|---|---|
| 9 | Alta | **`CM001` (el código original) podía caer en una clase que el estándar SQL reserva.** El estándar reserva para sí las clases que empiezan por un dígito de 0 a 4 o por una letra entre la A y la H; las clases definidas por la implementación empiezan por 5 a 9 o por I a Z. La `C` de `IN001` queda en el rango reservado. El diseño descarta `23C01` por el mismo motivo (la clase pertenece a PostgreSQL) pero acepta `CM` con el argumento «ninguna clase de PostgreSQL 18 empieza por `CM`», que es cierto hoy y no protege de una clase estándar futura. Es una inferencia desde el estándar, no un hecho comprobado en este proyecto | Antes de P4, que A0 compruebe el apéndice A de PostgreSQL y elija una clase en el rango de la implementación (por ejemplo `RN001`, que además cita la regla). Si se cambia, se cambia en toda la spec, el modelo de datos §13, ADR-031 y TC-35 a TC-42 |
| 10 | Media | **La partición deja sin dueño la reescritura de las dependencias.** «Documentación afectada» cambia la ficha de TKT-011 en `docs/05`, pero ningún renglón actualiza las fichas que hoy dicen «depende de TKT-011» (TKT-010, TKT-012 a TKT-018 y siguientes). El diseño afirma en una frase que TKT-010 y TKT-012 solo necesitan 011a y los demás 011b, pero esa afirmación no está en ningún documento que lea quien tome TKT-013. Además, `tools/verificar_docs.py` comprueba identificadores: el sufijo `a`/`b` ya existe en TKT-062b, pero hay que comprobar que acepta un paraguas `TKT-011` con hijos `TKT-011a` y `TKT-011b` | Añadir un renglón a «Documentación afectada» con las dependencias corregidas en `docs/05`, y que A6 corra `verificar_docs.py` antes de dar la fila por cerrada (ya lo hace) con el paraguas y los hijos presentes |
| 11 | Media | **`E-13` (el coste del `FOR SHARE` por fila) se mide en la última fila (B8), cuando el disparador ya está escrito, documentado en ADR-031 y probado.** Si 5,000 copias superan el `statement_timeout` de 15 s, hay que rediseñar el disparador y rehacer B1, B2, B7 y los mutantes. Además, el `FOR SHARE` ata la inserción de copias al privilegio `UPDATE` sobre `linea_base` y al `lock_timeout` del rol: cualquier transacción larga que modifique esa fila hace fallar la inserción de copias | Mover la medición de `E-13` a la fila B2, justo después del verde, con el escenario de volumen en una prueba. Añadir al ADR-031 que el `FOR SHARE` exige `UPDATE` sobre `linea_base` para el rol de aplicación y que `lock_timeout` aplica |
| 12 | Media | **Faltan mutantes sobre los privilegios y sobre el segundo disparador.** `MB-9` quita el `REVOKE` y `MB-10` añade uno, pero ninguno concede de más: un `GRANT TRUNCATE` (o `DELETE` sobre `linea_base_concepto` por una migración posterior que reabra el privilegio) no pone en rojo ninguna prueba que se haya nombrado. Tampoco hay un mutante que quite solo `trg_explosion_presupuesto_inmutable` dejando el de conceptos | Añadir `MB-13` (`GRANT TRUNCATE ON linea_base_concepto TO cimenta_aplicacion`, rojo en TC-45), `MB-14` (sin el disparador de `explosion_presupuesto`, rojo en TC-35 y TC-36 por su fila de explosión) y `MB-15` (`OLD` en lugar de `NEW` al leer `linea_base_id` en `INSERT`, rojo en TC-35) |
| 13 | Media | **El diseño introduce tres decisiones que la spec no confirmó y que se presentan como diseño, no como supuesto.** El `FOR SHARE` (la spec no lo pide), la regla de que `UPDATE` desde `BORRADOR` puede cambiar columnas en la misma sentencia que congela (parte de `PA-T14`, pero con efecto sobre TKT-017) y la abreviatura de `uq_explosion_presupuesto_linea_tipo_insumo` no están marcadas `(asumido)`. Las reglas del proyecto piden marcar lo que la persona no confirmó | Marcar las tres `(asumido)` en el cuerpo del diseño y añadirlas como P8 al gate para que la persona dueña las confirme |

Veredicto de la pasada independiente: cinco objeciones sustantivas. Ninguna rompe un invariante registrado; la 9 puede obligar a cambiar el `SQLSTATE` en cuatro documentos, por eso conviene decidirla antes de aprobar.

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Un experimento de A0 contradice el diseño (por ejemplo, `IN001` no llega con `constraint_name`, o `FOR SHARE` no espera) | Baja | Alto: cambia el disparador o lo que afirman las pruebas | `/sdd-escalar` antes de A1; ninguna fila avanza sobre una afirmación sin ejecutar |
| La nulabilidad estricta (`apu.fecha_analisis` y `analista`, `area.tipo_unidad`, todo `rendimiento_observado`, en especial `divergencia_pct` cuando `rendimiento_congelado` es cero) rechaza datos reales del Excel o del cálculo de la v1.1 | Media | Medio | Gate de la tabla (P5); una migración posterior relaja la columna sobre una tabla vacía o pequeña |
| La escala de precio en los importes del APU (`numeric(14,4)`) se queda corta | Baja | Bajo | Admite hasta 9,999,999,999.9999 por unidad de concepto; se amplía con `ALTER … TYPE` sin pérdida |
| TKT-017 necesita escribir una columna de `linea_base` después de congelar | Baja | Medio | `PA-T14`: debe hacerlo en la misma sentencia que congela; si no basta, se escala en TKT-017 |
| El `FOR SHARE` por fila encarece el congelado de 5,000 copias | Baja | Medio | E-13 en B2 con la cifra real; el límite es el `statement_timeout` de 15 s del rol de aplicación |
| Una prueba de TKT-011a fija la cabeza y se rompe al llegar `0007` | Media | Bajo | Regla explícita de la sección «Partición»; TC-INV-4 no afirma la cabeza |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P1 | ¿Se parte en TKT-011a (`0006`) y TKT-011b (`0007`), con un PR cada uno y fusión a → b? | Sí: ~2,175 líneas en un PR triplican el tope; el precedente es TKT-062 |
| P2 | ¿`CHECK` con nombre en lugar de `ENUM` para los conjuntos cerrados, y cambiar la fila «Enumeraciones» del modelo de datos §2? | Sí: es lo único que deja nombrar la restricción en cada rechazo, como pide la Definition of Done |
| P3 | ¿Se ajustan TC-12 y TC-13 de TKT-057 para subir a `0005` explícito, y se reescribe `CA-R4`? | Sí: no hay forma de añadir una migración sin tocarlas, y el ajuste conserva lo que afirman |
| P4 | ¿`IN001` (antes `CM001`) como `SQLSTATE` del rechazo del invariante 14? | Sí, frente a `P0001` con texto, que obligaría a TKT-017 a leer el mensaje |
| P5 | ¿Se aprueba la tabla de nulabilidad (`PA-T10`), en particular los puntos de la fila de riesgo? | Sí, tal como está, y relajar por migración cuando un ticket lo pida con datos |
| P6 | ¿Se confirman los rangos de `PA-T5` (de 0 a 1 en retención, fondo y progreso; solo no negativos en umbral y cargo)? | Sí |
| P8 | ¿Se confirman como `(asumido)` el `FOR SHARE` en el disparador de copias, el `UPDATE` desde `BORRADOR` que cambia columnas en la sentencia que congela y el nombre abreviado de la unicidad de la explosión? (objeción 13) | Sí, y que A0 confirme antes la clase del `SQLSTATE` (objeción 9) |
| P9 | ¿Se edita `tools/tests/test_definicion_revision.py` (prueba de otro ticket) para que el conteo de ADR no dependa del número, o se actualiza el número en cada PR? (hallazgo H1) | Generalizar la expresión regular una sola vez; el número volvería a atarse en cada ADR futuro |
| P10 | ¿Se aprueba editar `CLAUDE.md`, `README.md`, `llms.txt`, `.claude/skills/conv-sql-postgres` y los agentes `desarrollador-sql` y `auditor-sql` para alinear los textos del disparador y el conteo de ADR? (hallazgos H1 y H3) | Sí, en TKT-011b, como hizo TKT-007 |
| P7 | `spec.md` cita «la de un ticket de fundación (`sdd/metodologia.md` §8)», pero §8 no tiene esa fila y el ticket es de tipo funcionalidad. ¿Se corrige a «funcionalidad»? | Sí, en el mismo ajuste de la spec |
