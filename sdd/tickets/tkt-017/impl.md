# Impl · TKT-017a1 · Migración 0011 y preparación JSON

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta](delta.md)

Entrega **TKT-017a1** (filas **A0**, **A1**, **A2**, **A2d**, **A2c**): migración `v0011` (cinco columnas anulables con guarda en bajada), `preparacion_desde_json` con `FormatoPreparacionDesconocido`, libro sintético para pruebas, ajustes de regresión TKT-011/072 y documentación acordada para esta entrega.

## Qué se implementó

- **Migración `0011`:** subida con `DROP NOT NULL` en las cinco columnas del diseño; bajada con bloque `DO` + `LOCK TABLE area, apu, apu_cargo IN ACCESS EXCLUSIVE MODE` y `RAISE` con mensaje que cita «La bajada de 0011 se niega» si hay nulos.
- **Infraestructura:** `preparacion_desde_json` inverso de `preparacion_a_json` (formato 1), reconstrucción de rutas vía mapa `fila` → nodos y cabecera de análisis; cifras con tipos de `tipos_base`.
- **Herramientas:** `preparacion_sintetica()` para el libro de pruebas; `esperar_hasta` en `herramientas/tiempo_de_prueba.py` para el caso de bloqueo sin empaquetar `tests/`.
- **Pruebas:** `test_tkt017_migracion.py` (`TC-A01`, `TC-A02` + bloqueo), `test_tkt017_preparacion.py` (`TC-A03`); actualización de expectativas en `test_tkt011_estructura`, `test_tkt072_migracion` y `conftest` según cabeza `0011`.
- **Documentación:** `docs/03-modelo-datos.md` y `docs/glosario.md` alineados con migración, columnas anulables y P.U. del pie del análisis.

## Ajustes respecto al design

Ninguno en el alcance de las filas a1. La persona dueña autorizó en `_index.md` incluir en el mismo PR los cambios de plan en `sdd/tickets/tkt-059/*` y la ficha TKT-073 en `docs/05-tickets-trabajo.md` (fuera del núcleo 017 pero en la misma rama).

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-06 | Inclusión de artefactos TKT-059 y ficha TKT-073 en el mismo PR | Decisión registrada en `_index.md` («Alcance del PR de TKT-017a1») |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0011_presupuesto_campos_sin_fuente.py` | nuevo | migración |
| `backend/cimenta/presupuesto/infraestructura/preparacion_json.py` | modificado | infraestructura |
| `backend/herramientas/soporte_tkt017.py` | nuevo | herramientas |
| `backend/herramientas/tiempo_de_prueba.py` | nuevo | herramientas |
| `backend/tests/test_tkt017_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt017_preparacion.py` | nuevo | pruebas |
| `backend/tests/conftest.py` | modificado | pruebas |
| `backend/tests/test_tkt011_estructura.py` | modificado | pruebas |
| `backend/tests/test_tkt072_migracion.py` | modificado | pruebas |
| `docs/03-modelo-datos.md` | modificado | documentación |
| `docs/glosario.md` | modificado | documentación |
| `docs/05-tickets-trabajo.md` | modificado | documentación (TKT-073, conteo; acuerdo de alcance) |
| `sdd/tickets/tkt-059/spec.md` | modificado | SDD (fuera del núcleo 017) |
| `sdd/tickets/tkt-059/design.md` | modificado | SDD |
| `sdd/tickets/tkt-059/_index.md` | modificado | SDD |
| `sdd/tickets/tkt-017/design.md` | modificado | SDD |
| `sdd/tickets/tkt-017/_index.md` | modificado | SDD |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-A01 | `test_tkt017_caa11_sube_y_baja_sin_nulos` | feliz | `CA-A11` esc. 1 | FALLA | PASA |
| TC-A02 | `test_tkt017_caa11_la_bajada_se_niega_con_nulos` (+ bloqueo) | **rechazo** | `CA-A11` esc. 2 | FALLA | PASA |
| TC-A03 | pruebas en `test_tkt017_preparacion.py` (round-trip / formato) | feliz + rechazo infra | Objetivo A2 / preparación formato 1 | FALLA | PASA |

### Ciclo TDD por fila

#### Fila A0 · Línea base de herramientas

**Rojo** — no aplica como suite dedicada: comandos de verificación ejecutados tras tener código de A1–A2 en marcha.

**Verde** — misma corrida que el cierre (linters + suite completa + documentación).

**Refactor:** sin refactor en esta fila.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar:**

```text
uv run ruff format --check .  → 242 files already formatted
uv run ruff check .  → All checks passed!
uv run mypy .  → Success: no issues found in 242 source files
uv run lint-imports  → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float  → hallazgos: 0
uv run alembic heads  → 0011 (head)
python tools/verificar_docs.py  → ✓ Sin problemas.
python tools/extraer_mermaid.py  → 30 diagramas encontrados
python -m unittest discover -s tools/tests -v  → Ran 510 tests ... OK
```

**Mutación en rutas críticas:** cubierta en A2c.

#### Fila A1 · Migración `0011`

**Rojo** — los tests nuevos y los ajustes TKT-011/072 fallaron hasta existir `v0011` y las expectativas de nulabilidad / cabeza (detalle en transcript de la sesión previa).

**Verde** — tras migración y tests:

```text
uv run pytest tests/test_tkt017_migracion.py tests/test_tkt011_estructura.py tests/test_tkt072_migracion.py -q
... passed ...
```

(En cierre se sustituyó por la suite completa, ver abajo.)

**Refactor:** helpers de tipado en lectura JSON compartidos con mypy; orden de imports (ruff).

**Tests devueltos al tester:** ninguno.

**Mutación en rutas críticas:** ver A2c (M-A8).

#### Fila A2 · `preparacion_desde_json`

**Rojo** — tests `test_tkt017_preparacion.py` sin implementación satisfactoria hasta alinear cabecera, rutas por `fila` y cifras.

**Verde:**

```text
uv run pytest tests/test_tkt017_preparacion.py -q
... passed ...
```

**Refactor:** funciones por tipo para deserialización de cifras (evitar genéricos que confunden a mypy).

**Tests devueltos al tester:** ninguno.

**Mutación en rutas críticas:** ver A2c (M-A9).

#### Fila A2d · Documentación

**Rojo** — no aplica (solo documentación).

**Verde** — `python tools/verificar_docs.py` → ✓ Sin problemas (incluido en evidencia A0).

**Refactor:** —

**Mutación en rutas críticas:** no aplica.

#### Fila A2c · Mutantes M-A8 y M-A9

**Mutación:** ejecutados **manualmente** según diseño (uno a uno, revertidos):

- **M-A8:** retirar el `LOCK TABLE` de la guarda de bajada → el rechazo por nulos deja de coincidir con `P0001` / mensaje esperado; **TC-A02** (y escenarios relacionados) pasan a rojo.
- **M-A9:** alterar comprobación de `formato` en deserialización → **TC-A03** / rechazo de formato pasa a rojo.

Tras revertir, el código queda como en producción y la suite completa en verde.

## Suite completa (cierre A0 / A2c)

`docker info` respondió con sección **Server** (Docker Desktop / WSL2).

```text
uv run pytest -q -ra
2062 passed, 26 skipped in 357.58s (0:05:57)
```

## Modelo por paso

Orquestación en **Cursor (Composer 2.5)**; la tabla del `design.md` citaba `haiku`/`sonnet` para agentes de Claude Code.

| Paso | Agente (lógico) | Modelo previsto (design) | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A0–A2c | orquestador / implementación | varios | Composer 2.5 | Ejecución desde Cursor |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-A11` (migración 0011, subida/bajada, rechazo con nulos) | `[M]` | Cumplido | TC-A01, TC-A02 |
| Preparación JSON reversible / formato (objetivo fila A2) | `[M]` implícito en diseño | Cumplido | TC-A03 |
| `CA-A12` (documentación y borrador TKT-017a completo) | `[M]` | Parcial en a1 | Modelo de datos + glosario; OpenAPI/ADR/Historia en entregas posteriors |
| Resto del paraguas TKT-017 (materialización, API, …) | — | Pendiente otras entregas (a2–c) | — |

## Auditorías

### `/sdd-revisar` · 2026-11-06 · evidencia ejecutada

Comandos (desde `backend/` salvo `verificar_docs` en la raíz):

```text
docker info  →  Client / Server (Docker Desktop, WSL2)
uv run pytest -q --tb=line
2062 passed, 26 skipped in 334.31s (0:05:34)
uv run ruff check .
All checks passed!
uv run mypy cimenta/
Success: no issues found in 102 source files
uv run lint-imports
Contracts: 16 kept, 0 broken.
python tools/verificar_docs.py
✓ Sin problemas.
```

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | **APROBADO** | Ninguno | 1 |
| `auditor-sql` | **APROBADO** | Ninguno | 1 |
| `auditor-codigo` | **APROBADO** | Ninguno | 1 |
| `auditor-seguridad` | **APROBADO** (no aplica superficie nueva de esta entrega) | Sin endpoint, sesión, workflow ni dependencia nueva en el núcleo 017a1 | 0 |
| `auditor-docs` | **APROBADO con reserva** | Menor: el bullet de `CA-A12` en `spec.md` pide marcar `PA-T13` (TKT-014) y `PA-T17` (TKT-011) como resueltas en documentación; no hay casillas explícitas actualizadas en esas fichas (p. ej. `docs/05-tickets-trabajo.md`). Queda para TKT-017a2+ o un ajuste documental breve | 1 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| D001 | `auditor-docs` | Menor | `spec.md` CA-A12 vs `docs/05-tickets-trabajo.md` TKT-014/011 | Las preguntas abiertas `PA-T13` y `PA-T17` no están marcadas como resueltas en las fichas de ticket como describe la lista de `CA-A12` | **Persiste** · fuera del cierre estricto de a1 o seguimiento documental |
| — | resto | — | — | Sin otros hallazgos | — |

#### Informes sintéticos de auditoría (diff vs `Produccion`)

**`auditor-arquitectura`:** Migración y deserializador en capas previstas; `dominio/` sin imports prohibidos; módulos sin cruces fuera de `interfaz`; dinero vía `tipos_base` en la deserialización. **APROBADO.**

**`auditor-sql`:** Migración `0011` con `op.execute` por sentencia, reversa con guarda `DO`, `LOCK … ACCESS EXCLUSIVE`, mensaje explícito y `SET NOT NULL` solo si no hay nulos; alineado con `design.md` y pruebas TC-A01/TC-A02. **APROBADO.**

**`auditor-codigo`:** Estilo y tipado coherentes; tests de migración aserten `P0001`, texto de guarda y versión de alembic; prueba de preparación infraestructura pura (`FormatoPreparacionDesconocido`). **APROBADO.**

**`auditor-docs`:** Modelo de datos y glosario actualizados; `verificar_docs` en verde. Reserva D001. **APROBADO con reserva.**

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/tickets/tkt-059/*`, `docs/05-tickets-trabajo.md` (TKT-073) | Incluidos en el PR por decisión explícita en `_index.md` | Operativa de entrega |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/03-modelo-datos.md` | Migración 0011, columnas anulables, P.U. del pie del análisis, diagramas según acuerdo |
| `docs/glosario.md` | *Concepto de partida* y precio unitario del pie |
| `docs/05-tickets-trabajo.md` | Ficha TKT-073 y conteo (alcance acordado del PR) |

`python tools/verificar_docs.py` → **✓ Sin problemas.** (salida resumida en evidencia A0)

## Verificación final

### Completitud frente a `spec.md` (entrega TKT-017a1)

| Criterio | `[M]` | Estado en a1 | Notas |
|---|---|---|---|
| CA-A1 … CA-A10 | Sí | Pendiente entregas a2–a3 | Fuera de alcance a1 |
| CA-A11 | Sí | Cumplido | TC-A01, TC-A02 (+ bloqueo de guarda) |
| CA-A12 | Sí | Parcial | Modelo + glosario; faltan OpenAPI, marca PA-T13/PA-T17 en fichas, corrección HDU-001 esc. 12 → entregas posteriors; ver hallazgo D001 |

### Resultado `/sdd-revisar`

- [x] Criterios `[M]` **pertinentes a TKT-017a1** (`CA-A11` y la parte documental de `CA-A12` alcanzada) con evidencia
- [x] Suite `uv run pytest` en verde: **2062 passed, 26 skipped** (334.31 s) con Docker en marcha
- [x] `ruff check .`, `mypy cimenta/`, `lint-imports`, `verificar_docs.py` en verde (salidas pegadas arriba)
- [x] Tests de rechazo de migración: aserciones sobre `P0001`, mensaje y versión no revertida (no son API HTTP)
- [x] Mutación M-A8 / M-A9 documentada (manual, revertida)
- [x] Auditorías arquitectura / SQL / código / docs: **APROBADO** (docs con reserva D001 menor)
- [ ] CI completo de GitHub Actions: se verifica en `/sdd-completar` al abrir PR
- [ ] `CA-A12` completo en el paraguas: entregas posteriors (OpenAPI, ADR-036 ya existe; checklist PA-T13/PA-T17)

**Veredicto:** **LISTO PARA PR** · entrega **TKT-017a1**, con reserva menor D001 (documentación de supuestos resueltos).
