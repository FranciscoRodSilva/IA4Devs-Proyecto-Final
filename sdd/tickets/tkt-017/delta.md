# Delta · TKT-017a1 · Migración 0011 y preparación JSON

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-017a1** del paraguas **TKT-017**. Quedan pendientes **TKT-017a2**, **TKT-017a3**, **TKT-017b1**, **TKT-017b2** y **TKT-017c**. El hub **no** se archiva hasta cerrar la última entrega.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración Alembic `0011` (`v0011_presupuesto_campos_sin_fuente.py`) | `backend/migraciones/versions/` | Anular `NOT NULL` en cinco columnas que el Excel puede no llenar; bajada con guarda `DO` + `LOCK … ACCESS EXCLUSIVE` + `RAISE` si hay nulos |
| `preparacion_desde_json`, `FormatoPreparacionDesconocido` | `cimenta/presupuesto/infraestructura/preparacion_json.py` | Inversa de `preparacion_a_json` (formato 1); base para materialización posterior |
| `preparacion_sintetica()`, libro de prueba | `backend/herramientas/soporte_tkt017.py` | Datos con forma de CA-A1 para tests |
| `esperar_hasta` | `backend/herramientas/tiempo_de_prueba.py` | Bloqueo TC-A02 sin hacer paquete de `tests/` |
| Tests TC-A01, TC-A02, TC-A03 | `backend/tests/test_tkt017_migracion.py`, `test_tkt017_preparacion.py` | Migración y round-trip / formato ilegible |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Expectativas de nulabilidad y cabeza `0011` | `test_tkt011_estructura.py`, `test_tkt072_migracion.py`, `conftest.py` | Catálogo y migración 072 alineados con nueva cabeza |
| Modelo de datos y glosario | `docs/03-modelo-datos.md`, `docs/glosario.md` | Columnas `0011`, P.U. del pie del análisis, ejemplo `620040-A` |
| Plan TKT-059 y ficha TKT-073 (alcance acordado del PR) | `sdd/tickets/tkt-059/*`, `docs/05-tickets-trabajo.md` | Ajustes de plan MinIO/VPS y registro de ticket nuevo |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Módulo `tests` como paquete | `backend/tests/__init__.py`, `backend/tests/tiempo_de_prueba.py` (si aplica) | Evitar shadowing y mypy; utilidades en `herramientas/` |

## Comportamiento observable nuevo

- Tras aplicar migraciones hasta **0011**, las columnas `area.tipo_unidad`, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y `apu_cargo.base_calculo` **admiten `NULL`** en PostgreSQL.
- La **bajada** de `0011` a `0010` **se niega** (`P0001`, mensaje explícito) si queda algún `NULL` en esas columnas; con **bloqueo** primero (`ACCESS EXCLUSIVE`) para coordinar con sesiones de aplicación.
- **No** hay nuevas rutas HTTP ni cambios en el borrador OpenAPI en esta entrega; la confirmación de importación sigue en tickets posteriors.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema PostgreSQL (migración `0011`) | Cinco columnas pasan a nullable hacia arriba; bajada condicionada | No en sentido API; reversa exige datos sin nulos en esas columnas |
| OpenAPI / tipos generados | Sin cambio en esta entrega | — |

## Decisiones (ADR)

Ninguna ADR nueva en a1: la migración y la deserialización están cubiertas por el diseño y por documentación en modelo de datos; el formato JSON y rechazo de formato desconocido ya figuran en ADR-036 (TKT-015a).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Reconstruir `Ruta` desde JSON requiere mapa `fila` → nodos más cabecera de análisis, no solo la lista de rutas | Round-trip en TC-A03 | Otros serializadores de grafo jerárquico |
| Guarda de bajada con `LOCK` + tests de bloqueo detectan regresiones si se quita el lock | Mutante M-A8 / `test_tkt017_*_bloqueo` | Migraciones con `SET NOT NULL` condicionado |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `documentación` | El bullet **CA-A12** de `spec.md` pide marcar `PA-T13` y `PA-T17` resueltos en fichas de ticket (`docs/05-tickets-trabajo.md`); la revisión dejó hallazgo menor D001 sin cerrar en a1 — conviene una fila explícita en delta o cerrarlo en el mismo PR si cabe | Baja |
| `comando` | `/sdd-completar` gate «ningún [M] pendiente»: en paraguas partido hay que interpretar como **criterios [M] del alcance de la entrega**, no del ticket completo; si no, ninguna entrega intermedia podría completarse | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| CA-A12 completo (OpenAPI `ConfirmacionImportacion`, corrección HDU-001 esc. 12, marcas PA-T13/PA-T17 en fichas) | Alcance de TKT-017a2–a3 y TKT-018 | TKT-017a2+ / TKT-018 |
| Materialización, congelado, API, control | Fuera de a1 | TKT-017a2 a c |
| Cerrar hallazgo **D001** (documentación) | Reserva menor en auditor-docs | Misma rama o seguimiento rápido |

## Pull request

**Título:** `TKT-017a1 · Migración 0011 y preparación JSON`

**Origen:** `agent` (código del agente en sesión Cursor; revisión humana según proceso del equipo)

**Cuerpo (resumen):**

- Migración `0011`: cinco columnas nullable; bajada con guarda y pruebas de rechazo y bloqueo.
- `preparacion_desde_json` + libro sintético + tests TC-A01–TC-A03.
- Documentación modelo de datos y glosario; ajustes TKT-011/072.
- **Incluido por decisión registrada en hub:** actualizaciones `sdd/tickets/tkt-059/*` y ficha TKT-073 en `docs/05-tickets-trabajo.md`.

**Cómo verificar:** `docker info`; desde `backend/` `uv run pytest -q`; `uv run ruff check .`, `uv run mypy cimenta/`, `uv run lint-imports`; desde raíz `python tools/verificar_docs.py`.

**Fusión con omisión:** según política del repo (`gh pr merge --admin`); el registro va en comentario del PR tras aprobación explícita de la persona dueña.

## Siguiente entrega

**TKT-017a2** (`tkt-017a2-dominio-materializacion`): filas A3, A4, A4c del `design.md` — dominio `explosion_materializada` y `materializacion`.
