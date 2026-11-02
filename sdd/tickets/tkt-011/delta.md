# Delta · TKT-011a · Esquema del módulo presupuesto: estructura y catálogos

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket. Cubre solo la entrega **TKT-011a** (migración `0006`); la entrega TKT-011b (migración `0007`) tiene su propio apartado al final de este documento.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0006` con las doce tablas de estructura y catálogos: `empresa`, `obra`, `nivel`, `area`, `tipo_partida`, `partida`, `concepto`, `insumo`, `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo` | `backend/migraciones/versions/v0006_presupuesto_estructura_y_catalogos.py` | Dar a HDU-001 y a todo lo que lee o escribe presupuesto un esquema con sus garantías: unicidad, rangos, conjuntos cerrados y no negatividad en la base |
| `empresa.dias_semana_laboral` (`smallint NOT NULL DEFAULT 6`) | Misma migración | Que el módulo `personal` de la fase 2 la consuma sin alterar una tabla de `presupuesto` (`PA-T2`) |
| 123 pruebas de estructura y 2 del borde de `fondo_garantia_pct` | `backend/tests/test_tkt011_estructura.py` y `test_tkt011_regresion.py` | Demostrar cada garantía con su rechazo (`SQLSTATE`, nombre de la restricción y tabla intacta), el ciclo de subir, bajar y volver a subir, los nombres de restricciones e índices y la regresión de los invariantes 10, 20 y 21 |
| Fábrica `DatosPresupuesto` y fuente única `ESTRUCTURA_ESPERADA` | `backend/tests/conftest.py`, sección «TKT-011» | Construir filas válidas con los padres que falten y compartir la estructura esperada entre pruebas (no se puede importar de otro archivo de pruebas por `--import-mode=importlib`) |
| ADR-030, catálogos cerrados por `CHECK` con nombre | `docs/adr/20261101-catalogos-cerrados-por-check.md` y su fila en `docs/adr/README.md` | Dejar escrito por qué el módulo usa `CHECK` y no `ENUM`, con la evidencia del experimento E-7 |
| Partición del ticket en TKT-011a y TKT-011b | `docs/05-tickets-trabajo.md`, ficha de TKT-011 | Registrar la partición aprobada en el gate del diseño y qué tickets dependen de cada mitad |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| TC-12 y TC-13 de TKT-057 | `backend/tests/test_tkt057_migracion.py` (tres llamadas) | Subían a la cabeza y afirmaban `0005` → suben a `0005` explícito (`REVISION_NUEVA`); conservan todo lo que afirman |
| Prueba del conteo de ADR | `tools/tests/test_definicion_revision.py` | Fijaba «29» → cuenta los archivos de `docs/adr/` y exige que `CLAUDE.md`, `README.md` y `llms.txt` citen ese número |
| Conteo de decisiones | `CLAUDE.md`, `README.md`, `llms.txt` | 29 → 30 |
| Modelo de datos | `docs/03-modelo-datos.md` §2, §4.1 y §13 | «Enumeraciones» pasa a `CHECK` con nombre (con `accion_bitacora` como excepción histórica); `obra` con auditoría; `APU.concepto_id` sin `UNIQUE` (lo sostiene el caso de uso); `concepto.obra_id` sin restricción de coherencia; ocho unidades; invariante 8 ampliado a todo importe, precio, cantidad y rendimiento |
| Dependencias de los tickets | `docs/05-tickets-trabajo.md` | «Depende de TKT-011» pasa a TKT-011a (TKT-010, 019, 042, 046 y 049) o TKT-011b (TKT-012, 013 y la trazabilidad de TKT-039); la ficha de TKT-049 dice que solo consume `dias_semana_laboral` |
| Fichas de referencia y notas de sprint | `docs/05-tickets-trabajo.md` (ficha de TKT-010, nota del sprint 2, alerta de HDU-006) y `docs/03-modelo-datos.md` §2 (escala `NUMERIC(14,4)` de los importes del APU y excepción de las columnas de auditoría) | Citaban «TKT-011» a secas o no recogían estas escalas y excepciones → citan TKT-011a o las recogen |
| Atribución de pruebas a la mitad que las escribe | `docs/02-arquitectura.md` §7.6, `docs/03-modelo-datos.md` §13 | «TKT-011» → «TKT-011b» para las pruebas de `linea_base_concepto` y `explosion_presupuesto` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Nada | — | — |

## Comportamiento observable nuevo

- Ninguno para una persona usuaria ni para un integrador: no hay ruta, caso de uso ni dato nuevo. La base de datos tiene doce tablas vacías que antes no existían.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema PostgreSQL | Doce tablas nuevas; privilegios `SELECT`, `INSERT`, `UPDATE` y `DELETE` para el rol de aplicación y `SELECT` para el de lectura | No: solo se añade |
| Borrador OpenAPI (`docs/api/openapi.yaml`) | Sin cambios | No |
| Códigos de error del motor | Borrar un padre con hijos responde `23001` (`restrict_violation`); insertar un hijo sin padre, `23503`. Los casos de uso de TKT-012 a TKT-018 deben traducir ambos | No |

## Decisiones (ADR)

### 2026-11-01 — Catálogos cerrados por `CHECK` con nombre

**Contexto:** `CA-8` pide un único `SQLSTATE` para los seis conjuntos cerrados y la Definition of Done exige el nombre de la restricción en cada rechazo.
**Opciones consideradas:** `CHECK` con nombre; tipo `ENUM`; tabla de catálogo.
**Decisión:** `CHECK (columna IN (…))` con nombre `ck_<tabla>_<columna>` sobre columnas `text NOT NULL`.
**Evidencia:** el experimento E-7 de la fila A0: un valor ajeno en un `ENUM` responde `22P02` sin nombre de restricción, y en un `CHECK` responde `23514` con él.
**Consecuencias:** el modelo de datos §2 deja de pedir `ENUM` salvo `accion_bitacora`, que queda como excepción histórica.

→ Registrada como ADR-030 en `docs/adr/20261101-catalogos-cerrados-por-check.md`, con su fila en el índice.

La clase del `SQLSTATE` del disparador de TKT-011b (`IN001`, elegida frente a `CM001` porque la clase `CM` cae en el rango que el estándar SQL reserva) se registra en el ADR-031 de TKT-011b, junto con el disparador.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `ON DELETE RESTRICT` responde `23001` al borrar un padre con hijos, no `23503`; el `23503` es el de insertar un hijo huérfano | Prueba de TC-02 en la fila A2 y experimento en un contenedor `postgres:18.6` | Pruebas de rechazo de TKT-011b, y la traducción a errores en TKT-012 a TKT-018 |
| PostgreSQL 18 registra las restricciones `NOT NULL` en `pg_constraint` con nombre automático; hay que filtrar `contype <> 'n'` al comparar restricciones por nombre | Tests TC-16 y TC-17 | Cualquier prueba de catálogo del esquema |
| El estándar SQL reserva las clases de `SQLSTATE` que empiezan por 0 a 4 o por una letra entre la A y la H; las de la implementación empiezan por 5 a 9 o por I a Z, y PostgreSQL 18.6 solo usa `P0` y `XX` entre estas últimas | Apéndice A de la documentación de PostgreSQL, consultado con Context7 en la fila A0, y experimento E-4 | Cualquier `SQLSTATE` propio del proyecto |
| Con `--import-mode=importlib` un archivo de pruebas no puede importar de otro; lo compartido va en `conftest.py` | `ModuleNotFoundError` al probarlo en la corrección F004 | Estructuras esperadas compartidas entre pruebas |
| `tools/verificar_docs.py` no comprueba el conteo de ADR; lo fija una prueba de `tools/tests` | Hallazgo H1 de `revisor-impacto` | Cualquier ticket que añada un ADR |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | El pipeline no tiene noción de una entrega parcial de un ticket partido: `/sdd-ejecutar` y `/sdd-completar` asumen un PR por ticket y el estado `ARCHIVADO` del hub; hubo que improvisar la rama (`tkt-011a-…`), los estados del hub y qué sección de `impl.md` es de cada mitad | Alta |
| `agente` | `corrector-revision` marcó un hallazgo (F006 de `auditor-codigo`) como «ya corregido» leyendo mal el texto esperado; solo lo detectó el orquestador al comprobarlo con `grep` | Media |
| `guardrail` | Las dos comprobaciones previas funcionaron: el experimento de la fila A0 refutó `CM001` antes de construir nada sobre ese código, y `revisor-impacto` encontró que la premisa «`verificar_docs.py` comprueba los conteos» era falsa | Baja |
| `convención` | Ninguna convención de `conv-pruebas` ni de `conv-sql-postgres` decía que PostgreSQL 18 registra los `NOT NULL` en `pg_constraint`; el tester lo supo porque el orquestador se lo dijo en el encargo | Media |
| `herramienta` | El límite de uso de la sesión cortó dos reauditorías; se reanudaron con `SendMessage` y continuaron donde se quedaron, sin repetir el trabajo | Baja |
| `herramienta` | markdownlint-cli2, Vale y lychee no estaban instalados en la máquina local, así que `auditor-docs` no los ejecutaba; lychee 0.24.2 se instaló el 2026-11-01 | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Índices sobre `partida.tipo_partida_id`, `precio_insumo.obra_id`, `apu_insumo.insumo_id`, `obra.empresa_id`, `obra.creado_por_id` y `obra.actualizado_por_id` | El diseño los dejó fuera por YAGNI; con catálogos de decenas de filas es despreciable. `partida.tipo_partida_id` es el candidato real si la fase 1 filtra partidas por tipo | Ticket futuro de índices |
| `CHECK` sobre `area.tipo_unidad` | La spec no lo pide y el modelo lo declara `string` | Ticket futuro |
| `GRANT` explícito por tabla en `0006`, redundante con los privilegios por omisión de `0001` | Lo añadió el desarrollador; queda a decisión de la persona dueña si se quita | Decisión de la persona dueña; se puede resolver en TKT-011b |
| Las cuatro restricciones que quedaron fuera (`UNIQUE (apu.concepto_id)`, `UNIQUE (linea_base.obra_id, version)`, el `CHECK` de congelado y la coherencia de `concepto.obra_id`) | Decisión de la persona dueña (`PA-T3`) | «Protección de base» en `_index.md` |
| `Obra.actualizado_en` no admite `null` en el borrador OpenAPI y la columna sí | Fuera del alcance de un ticket de esquema | TKT-012 |
| TKT-011b: línea base, copias, explosión, control, importación, `rendimiento_observado`, disparadores, `REVOKE`, bajada con guarda, ADR-031 y el cambio de la regla 4 de `CLAUDE.md`, la arquitectura §7.6 y §9, `.claude/` | Es la segunda mitad aprobada del ticket | TKT-011b (filas B1 a B8 del diseño) |

## Pull request

**Título:** `TKT-011a · Esquema del módulo presupuesto: estructura y catálogos`
**Origen:** `agent+human-review`
**Cuerpo:** qué (migración `0006`, doce tablas, 125 pruebas, ADR-030, documentación y ajustes a pruebas de TKT-057 y `tools/tests`), por qué (HDU-001 y todo lo que lee o escribe presupuesto necesita su esquema con garantías en la base), criterios cubiertos (`CA-1` a `CA-3`, `CA-8`, `CA-11` a `CA-14`, `CA-17` esc. 3 y 4, `CA-18` de `0006`, `CA-20` y `CA-R1` a `CA-R6`, en su parte a) y cómo verificarlo (`uv run pytest`, `ruff`, `mypy`, `lint-imports`, `verificar_float`, `verificar_docs.py`, `lychee`). Señala a quien aprueba que añade una migración y reparte privilegios sobre tablas nuevas.

**Fusión con omisión:** la fusión a `Produccion` será con omisión de la protección. El registro va en un comentario del PR que deja el orquestador justo después de `gh pr merge --admin`, con la aprobación explícita de la persona dueña en la sesión.

---

## Delta · TKT-011b · Línea base, importación, disparadores y permisos del módulo presupuesto

Este apartado cubre la entrega **TKT-011b** (migración `0007`); lo anterior de este documento es de la entrega TKT-011a, ya fusionada (PR 31). Con las dos entregas, el ticket TKT-011 queda completo: el módulo `presupuesto` tiene sus 19 tablas.

### Añadido (TKT-011b)

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0007` con las siete tablas restantes: `linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error` y `rendimiento_observado` | `backend/migraciones/versions/v0007_presupuesto_linea_base_e_importacion.py` | Dar la base física a la línea base inmutable, al control por tipo de partida, a la importación del Excel y al rendimiento observado |
| Índice único parcial `uq_linea_base_obra_id_congelada` | Misma migración | Una sola línea base `CONGELADA` por obra (invariante 5) |
| Funciones `presupuesto_proteger_linea_base()` y `presupuesto_proteger_copia_congelada()` y los disparadores `trg_linea_base_solo_avanza`, `trg_linea_base_concepto_inmutable` y `trg_explosion_presupuesto_inmutable` | Misma migración | Imponer en el motor el invariante 14: las copias de una línea base que no es `BORRADOR` rechazan `INSERT`, `UPDATE` y `DELETE`, y la fila `linea_base` solo avanza `BORRADOR` → `CONGELADA` → `SUPERSEDIDA` y desde `CONGELADA` solo cambia su estado. El rechazo lleva el `SQLSTATE` propio `IN001` y un mensaje que empieza por `RN-01:` |
| `REVOKE UPDATE, DELETE, TRUNCATE ON linea_base_concepto FROM cimenta_aplicacion` | Misma migración | Doble barrera del invariante 14: la aplicación solo anexa a la copia de conceptos |
| Bajada con guarda | Misma migración | La bajada se niega con una línea base `CONGELADA` o `SUPERSEDIDA`, toma `LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` antes de comprobar y no borra nada si se niega |
| 160 casos de prueba (56 funciones) en cuatro archivos y las pruebas de concurrencia | `backend/tests/test_tkt011_linea_base.py`, `test_tkt011_importacion.py`, `test_tkt011_permisos.py`, `test_tkt011_migracion_linea_base.py` | Demostrar cada garantía con su rechazo, la carrera del congelado, el bloqueo pesimista con el rol de aplicación y la bajada con guarda |
| Ampliación de la fábrica `DatosPresupuesto` | `backend/tests/conftest.py` | Construir líneas base, copias, renglones, controles, importaciones, errores y rendimientos observados |
| ADR-031, inmutabilidad de la línea base en el motor | `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` y su fila en `docs/adr/README.md` | Dejar escrito el porqué de los disparadores, de `IN001`, del `FOR SHARE` y de la doble barrera |
| Sección 9, «Comportamientos del motor que sorprenden» | `.claude/skills/conv-sql-postgres/SKILL.md` | Registrar cuatro hechos comprobados de PostgreSQL 18 para quien escriba el siguiente esquema |

### Modificado (TKT-011b)

| Qué | Dónde | Antes → después |
|---|---|---|
| Regla 4 y conteo de decisiones | `CLAUDE.md`, `README.md`, `llms.txt` | El disparador rechazaba «`UPDATE` y `DELETE`» y había 30 decisiones → rechaza `INSERT`, `UPDATE` y `DELETE` sobre las copias, la fila `linea_base` solo avanza, y hay 31 decisiones |
| Modelo de datos | `docs/03-modelo-datos.md` §4.2, §11, §13 (invariante 14), §14 y §15 | Sin `creado_*` en `linea_base` ni unicidad de la explosión; invariante 14 solo con `UPDATE` y `DELETE` → recoge `INSERT`, la fila que solo avanza, `FOR SHARE` y `IN001` |
| Arquitectura | `docs/02-arquitectura.md` §7.6 y §9 | El estado `DESCARTADO` faltaba en el diagrama de la importación → `VALIDADO` y `CON_ERRORES` pasan a `DESCARTADO`; §7.6 cita los permisos y las pruebas reales |
| Tickets | `docs/05-tickets-trabajo.md` | Criterio del disparador con `UPDATE` y `DELETE` → con `INSERT` y las transiciones; la ficha de TKT-017 recoge las restricciones que nacen del esquema |
| ADR del snapshot | `docs/adr/20260918-snapshot-linea-base.md` | Solo `UPDATE` y `DELETE` → nota que enlaza a ADR-031 |
| Agentes SQL | `.claude/agents/desarrollador-sql.md` y `auditor-sql.md` | Invariante 14 con `UPDATE` y `DELETE`; la fila de la bitácora se leía como si exigiera rechazar `INSERT` → texto alineado con el disparador y con la bitácora |
| Spec y diseño del ticket | `sdd/tickets/tkt-011/spec.md`, `design.md` | CA-19 solo con `CONGELADA`, medición E-13 en B8, `SQLSTATE` `CM001` → CA-19 con `CONGELADA` o `SUPERSEDIDA`, medición en B2, `IN001`, estados de las filas, `PA-T17` |
| Registro de evolución | `sdd/_evolucion.md` | Seis filas de TKT-011b (`comando`, `guardrail`, `convención`, `herramienta` y `modelo`) y la sección de patrones revisada por `meta-sdd` |
| Hub y registro de la entrega | `sdd/tickets/tkt-011/_index.md`, `impl.md` | Estado de la entrega b y apartado «Entrega TKT-011b» con sus ajustes, pruebas, mutación y auditorías |

### Eliminado (TKT-011b)

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Nada | — | — |

### Comportamiento observable nuevo (TKT-011b)

- Ninguno para una persona usuaria ni para un integrador: no hay ruta, caso de uso ni dato nuevo. Sí lo nota quien desarrolla: una escritura sobre una línea base que no es `BORRADOR` ya no es posible ni siquiera desde `psql` con el rol de aplicación, y la base responde con `IN001`.

### Contrato público tocado (TKT-011b)

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema PostgreSQL | Siete tablas nuevas, tres disparadores, dos funciones y un `REVOKE` | No: solo se añade |
| Borrador OpenAPI (`docs/api/openapi.yaml`) | Sin cambios | No |
| Códigos de error del motor | Nuevo `SQLSTATE` propio `IN001` para el rechazo del invariante 14; TKT-017 lo traduce a `409` `REGLA_NEGOCIO` con `RN-01` `(asumido)`, junto con `23505`, `23503` y `23001`. La guarda de la bajada también usa `IN001`, pero no llega a la API | No |

### Decisiones (ADR) (TKT-011b)

#### 2026-11-01 — Inmutabilidad de la línea base en el motor

**Contexto:** el invariante 14 pedía que una línea base congelada no se altere, pero el ADR de copia física solo nombra `UPDATE` y `DELETE`, y la aplicación conserva `INSERT` y `UPDATE` sobre varias tablas.
**Opciones consideradas:** dos funciones de disparador frente a una sola; `P0001` con texto frente a un `SQLSTATE` propio; privilegios sin disparador; `FOR SHARE` frente a aceptar la carrera; `BEFORE TRUNCATE`; `CM001`, `RN001` e `IN001` como código.
**Decisión:** dos funciones con tres disparadores, `SQLSTATE` `IN001`, lectura del estado con `FOR SHARE` y un `REVOKE` como segunda barrera.
**Evidencia:** los experimentos E-2, E-3, E-4, E-9 y E-11 de la fila A0; la medición E-13 (`total 0.070 s` para 5,000 copias, 300 renglones y el congelado); las pruebas de concurrencia TC-C2 y la del bloqueo de la guarda; y quince mutantes de cierre.
**Consecuencias:** el `FOR SHARE` exige `UPDATE` sobre `linea_base` para el rol de aplicación; las copias solo se escriben en la transacción del congelado porque la aplicación no puede borrarlas; `TRUNCATE` por el rol de migración queda como límite aceptado (`PA-T15`).

→ Registrada como ADR-031 en `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md`, con su fila en el índice.

### Aprendizajes (TKT-011b)

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Sin `FOR SHARE`, una inserción concurrente con el congelado lee `BORRADOR` y entra después | Experimento E-9 y mutante MB-4 | Cualquier disparador que decida según el estado de otra fila |
| `SELECT … FOR UPDATE` no dispara un disparador `BEFORE UPDATE`, así que el bloqueo pesimista de ADR-004 funciona sobre una línea base congelada | Experimento E-2 y TC-44 | Casos de uso de TKT-019 en adelante |
| Una guarda de bajada debe ir al principio y tomar el bloqueo antes de comprobar, o una sesión concurrente puede congelar entre la comprobación y el `DROP` | Prueba `test_tkt011_ca19_la_guarda_toma_el_bloqueo_antes_de_comprobar` y su mutante «sin bloqueo» | Cualquier migración con una bajada condicionada a datos |
| Con dos tablas hijas violadas, PostgreSQL informa solo la primera clave foránea | Prueba de TC-42 con copias | Pruebas de rechazo con varias claves |
| `TRUNCATE` no dispara disparadores de fila: se protege quitando el privilegio, no con un disparador | Experimento E-3 y TC-45 | Cualquier tabla de solo anexado |

### Observaciones para `_evolucion.md` (TKT-011b)

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | Dos correctores lanzados en paralelo sobre archivos que dependen uno del otro (migración y documentación de la misma decisión) produjeron un informe sobre un estado obsoleto: el corrector de documentación avisó de que la migración seguía con la guarda antigua cuando el desarrollador ya la había cambiado. Hay que ordenar las correcciones que comparten una decisión | Media |
| `guardrail` | Validar los tests en rojo contra una implementación de ensayo en una copia fuera del repositorio funcionó otra vez (B1, B2, B3 y B5, B6): el desarrollador recibió tests ya demostrados satisfacibles y con mutantes que mordían. Tres tickets seguidos lo usan sin que esté escrito en `conv-pruebas` | Media |
| `comando` | Los tests que nacen en verde por orden de las filas (B4 y B6) exigen mutantes para demostrar que no son vacuos; el pipeline lo pide solo para rutas críticas. Convendría decir en `/sdd-ejecutar` qué hacer cuando un test nace en verde | Baja |
| `convención` | Los identificadores `PA-T` son locales a cada ticket y chocan: `backend/tipos_base/numericos.py` cita un `PA-T16` de otro ticket y `PA-T16` ya existía en la spec de TKT-011. El corrector tuvo que detectar la colisión antes de registrar una pregunta | Baja |
| `herramienta` | Un agente que no tiene límite de bloqueo (`lock_timeout`) en el rol de migración puede dejar `alembic downgrade` esperando sin fin; ninguna convención dice si las migraciones con `LOCK` deben fijar su propio `lock_timeout` | Baja |
| `modelo` | `haiku` cerró las filas B3 y B5 y B7 a la primera y B6 en verde (la guarda se amplió después, en el ciclo de corrección); `sonnet` fue necesario por disparador en B1, B2 y B4 y salió sin reintentos. Ningún paso necesitó subir de nivel | Baja |

### Deuda que queda abierta (TKT-011b)

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Editar `.claude/agents/auditor-arquitectura.md` (~36), que aún dice «sin disparador que rechace `UPDATE` y `DELETE`» | La aprobación P10 de la persona dueña nombraba otros textos | Pedir la aprobación en el siguiente ticket que toque `.claude/` |
| Procedimiento para retirar una línea base `CONGELADA` o `SUPERSEDIDA` antes de bajar la migración | El mensaje de la guarda lo declara sin definir; lo decide la persona dueña | Decisión de la persona dueña |
| Valor con el que nace `importe_venta` en un `BORRADOR` (`PA-T17`), flujo de reimportación sin `DELETE` para la aplicación y traducción de `IN001`, `23505`, `23503` y `23001` | Corresponde al caso de uso de congelado | TKT-017 |
| Índices sobre `presupuesto_control.tipo_partida_id` y `rendimiento_observado.obra_id`; `SET LOCAL lock_timeout` antes del `LOCK` de la guarda | YAGNI del diseño; conviene confirmarlos con la consulta del semáforo (modelo de datos §15) | Ticket futuro de índices |
| `GRANT` explícitos por tabla de `0006`, asimétricos con `0007` | Pendiente de la persona dueña | Decisión de la persona dueña |
| Helpers repetidos entre archivos de prueba (`afirmar_rechazo`, `contar`, `fotografia`) y `copia_concepto` sin padres que crea un concepto de otra obra | Observaciones F009 y F010 de `auditor-codigo`, no pedidas | Ticket futuro de limpieza de pruebas |

### Pull request (TKT-011b)

**Título:** `TKT-011b · Línea base, importación, disparadores y permisos del módulo presupuesto`
**Origen:** `agent+human-review`
**Cuerpo:** qué (migración `0007` con las siete tablas restantes, tres disparadores `IN001`, un `REVOKE` y la bajada con guarda; 160 casos de prueba; ADR-031 y documentación alineada), por qué (completar el esquema de `presupuesto` para que TKT-012 a TKT-018 y el semáforo lean una línea base que ninguna ruta de código puede alterar), criterios cubiertos (`CA-1`, `CA-4` a `CA-10`, `CA-13` a `CA-21` y `CA-R3` a `CA-R6`, en su parte b) y cómo verificarlo (`uv run pytest`, `ruff`, `mypy`, `lint-imports`, `verificar_float`, `python tools/verificar_docs.py`, lychee). Señala a quien aprueba que añade una migración, reparte privilegios sobre tablas nuevas, revoca privilegios y toca `.claude/` y `docs/adr/`.

**Fusión con omisión:** la fusión a `Produccion` será con omisión de la protección. El registro va en un comentario del PR que deja el orquestador justo después de `gh pr merge --admin`, con la aprobación explícita de la persona dueña en la sesión.
