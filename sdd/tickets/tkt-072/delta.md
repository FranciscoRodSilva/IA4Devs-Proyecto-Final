# Delta · TKT-072 · Concepto único por obra y sus apariciones por área

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Tabla `partida_concepto` (*concepto de partida*) | PostgreSQL, migración `0010` | Cantidad, precio unitario e importe por aparición en una partida de un área |
| Migración Alembic `0010` con guardas de subida y bajada | `backend/migraciones/versions/v0010_presupuesto_concepto_de_partida.py` | Separar concepto de aparición sin migrar datos existentes |
| Invariante 39 · `UNIQUE (concepto_id, partida_id)` | `docs/03-modelo-datos.md` §13 | Una aparición por partida |
| ADR concepto único vs aparición | `docs/adr/20261105-concepto-unico-y-concepto-de-partida.md` | Opciones descartadas y decisión del 2026-11-05 |
| Entrada de glosario *Concepto de partida* | `docs/glosario.md` | Vocabulario alineado al esquema |
| Suites de prueba TKT-072 (34 casos) | `backend/tests/test_tkt072_*.py` | Criterios CA-1…CA-9 y regresión CA-R1…CA-R3 |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Tabla `concepto` | PostgreSQL | Nueve columnas con partida y montos → cinco columnas (código, descripción, unidad por obra) |
| `linea_base_concepto` | PostgreSQL | `concepto_id` → `partida_concepto_id` (mismo disparador y revocación del invariante 14) |
| Fábricas de prueba | `backend/tests/conftest.py` | `concepto()` sin partida; `partida_concepto()`; semilla esquema `0009` para guardas de `0007` |
| Regresión TKT-011 | tres archivos de tests | Columnas y FK alineadas al modelo nuevo |
| Conteos documentales | `CLAUDE.md`, `README.md`, `llms.txt`, agentes | 38 → 39 invariantes y ADR |
| `PA-T1` de TKT-013 / TKT-015 | specs de ticket | Marcada resuelta por TKT-072 |
| Fichas TKT-017 y TKT-047 | `docs/05-tickets-trabajo.md` | Redacción «concepto de partida» donde aplica |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Columnas `partida_id`, `cantidad`, `precio_unitario`, `importe` de `concepto` | PostgreSQL | Pasan a `partida_concepto`; guarda de subida exige tablas vacías |
| Índice `ix_concepto_partida_id` | PostgreSQL | Sustituido por `ix_partida_concepto_partida_id` |

## Comportamiento observable nuevo

Ninguno en la aplicación: no hay pantallas ni API nuevas. **Operadores de base de datos** ven la migración `0010` rechazada con mensaje explícito si hay filas en `concepto` o `linea_base_concepto` al subir, o en `partida_concepto`/`concepto` al bajar. TKT-017 materializará concepto y aparición al confirmar la línea base.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema PostgreSQL | Nuevo modelo concepto / concepto de partida | Sí para cualquier cliente SQL que asumía columnas en `concepto`; no hay API publicada que las expusiera |
| OpenAPI / DTO | Sin cambio | No |
| `importacion.preparacion` (JSON) | Sin cambio de formato | No |

## Decisiones (ADR)

→ [ADR-20261105 · El concepto es único por obra; su cantidad y su precio viven en el concepto de partida](../../../docs/adr/20261105-concepto-unico-y-concepto-de-partida.md)

**Contexto:** Los Excel reales repiten cada código en muchas áreas; el invariante 13 sobre filas monolíticas impedía confirmar la línea base (`PA-T1`).

**Opciones consideradas:** ampliar la unicidad sobre `concepto`; concepto + `partida_concepto` (elegida); fusionar apariciones; precio en el concepto; copia con área denormalizada.

**Decisión:** Concepto único por obra; aparición en `partida_concepto`; copia congelada apunta a la aparición.

**Evidencia:** Medición ENITI/Union Square en la spec; `620040-A` con dos precios; tests TC-01…TC-22.

**Consecuencias:** TKT-017 escribe dos tablas; `UNIQUE (apu.concepto_id)` y coherencia obra/partida en motor quedan como ticket futuro.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Las pruebas de bajada de `0007` desde la cabeza pasan a chocar con la guarda de `0010`; sembrar en `0009` con fábrica «anterior» | TC-48/49 movidos en TKT-011 | Migraciones encadenadas con guardas |
| `ESTRUCTURA_ESPERADA` en conftest no debe incluir tablas post-migración si TC-17 de regresión solo lista las doce de `0006` | Ajuste en test de FK sin cascada | Tickets que parten tablas existentes |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | `/sdd-ejecutar` dejó mutación M-2…M-10 sin barrido; `/sdd-revisar` cerró con spot-check parcial | Media |
| `comando` | Salida TDD en rojo no archivada cuando migración y fábricas preceden a los tests | Baja |
| `documentación` | Actualizar conteos 38→39 exige regenerar `.cursor/agents/` y tocar skills; P-3 del diseño lo listó explícitamente | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `UNIQUE (apu.concepto_id)` y coherencia obra/partida en motor | Fuera de alcance (`PA-T3`) | Ticket futuro en `_index.md` |
| Conteo `ResumenImportacion.conceptos` (únicos vs apariciones) | TKT-018 | TKT-018 |
| Comprobar tablas vacías antes de desplegar `0010` en VPS test | Operación | Sugerido en `_index.md` (`PA-T72.8`) |
| Spot-check mutantes M-2, M-6…M-10 | Tiempo en revisión | Opcional post-fusión |

## Pull request

**Título:** `TKT-072 · Concepto único por obra y sus apariciones por área`

**Origen:** `agent`

**Cuerpo:** ver descripción en GitHub al abrir el PR.

**Fusión con omisión:** pendiente de aprobación explícita de la persona dueña; registro en comentario del PR tras fusión.
