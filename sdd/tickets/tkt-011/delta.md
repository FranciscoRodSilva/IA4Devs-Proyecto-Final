# Delta · TKT-011a · Esquema del módulo presupuesto: estructura y catálogos

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket. Cubre solo la entrega **TKT-011a** (migración `0006`); la entrega TKT-011b (migración `0007`) tendrá su propio apartado cuando se ejecute.

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

La clase del `SQLSTATE` del disparador de TKT-011b (`IN001`, elegida frente a `CM001` porque la clase `CM` cae en el rango que el estándar SQL reserva) se registrará en el ADR-031 que escribe TKT-011b, junto con el disparador.

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
