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
| `CA-A12` (documentación y borrador TKT-017a completo) | `[M]` | Parcial en a1 | Modelo de datos + glosario; OpenAPI/ADR/Historia en entregas posteriores |
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
| CA-A12 | Sí | Parcial | Modelo + glosario; faltan OpenAPI, marca PA-T13/PA-T17 en fichas, corrección HDU-001 esc. 12 → entregas posteriores; ver hallazgo D001 |

### Resultado `/sdd-revisar`

- [x] Criterios `[M]` **pertinentes a TKT-017a1** (`CA-A11` y la parte documental de `CA-A12` alcanzada) con evidencia
- [x] Suite `uv run pytest` en verde: **2062 passed, 26 skipped** (334.31 s) con Docker en marcha
- [x] `ruff check .`, `mypy cimenta/`, `lint-imports`, `verificar_docs.py` en verde (salidas pegadas arriba)
- [x] Tests de rechazo de migración: aserciones sobre `P0001`, mensaje y versión no revertida (no son API HTTP)
- [x] Mutación M-A8 / M-A9 documentada (manual, revertida)
- [x] Auditorías arquitectura / SQL / código / docs: **APROBADO** (docs con reserva D001 menor)
- [ ] CI completo de GitHub Actions: se verifica en `/sdd-completar` al abrir PR
- [ ] `CA-A12` completo en el paraguas: entregas posteriores (OpenAPI, ADR-036 ya existe; checklist PA-T13/PA-T17)

**Veredicto:** **LISTO PARA PR** · entrega **TKT-017a1**, con reserva menor D001 (documentación de supuestos resueltos).

---

## TKT-017a2 · Dominio: explosión materializada y planificación (`/sdd-ejecutar` 2026-11-06 · `/sdd-revisar` 2026-11-08)

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta](delta.md) al cerrar la entrega con `/sdd-completar`

Entrega **TKT-017a2** (filas **A3**, **A4**, **A4c**): `explosion_materializada.explotar_filas`, `materializacion.planificar_materializacion` con objetos de valor y rechazos del diseño, extensiones de `herramientas/soporte_tkt017.py` y pruebas `TC-A04` a `TC-A09`. Los mutantes **M-A2** y **M-A3** se ejecutaron en manual y se revirtieron. La revisión del 2026-11-08 devolvió la entrega a corrección cinco veces: tres ciclos de corrección, un ciclo extra autorizado por la persona dueña y un quinto, pedido por ella al ver los hallazgos de `code-review` (ver «Ciclo de corrección de `/sdd-revisar`»); lo que sigue describe el estado final.

### Qué se implementó

- **`explosion_materializada`:** `FilaExplotable`, `InsumoDeApu`, `CargoDeApu`; `explotar_filas` arma `ConceptoAExplotar` y un `AnalisisLeido` sintético según `design.md` § Dominio y devuelve `calcular_explosion(…).cuantizar()` o `RechazoExplosion`. No cambió durante la revisión.
- **`materializacion`:** `planificar_materializacion` valida y cuantiza en un solo sitio (`_validar_conceptos`, `_validar_valores`, `_validar_insumo`, `_validar_cargo`) y rechaza por fases globales: estructura y valores de todos los conceptos, asignación de tipos, insumos de todos los conceptos y explosión. Después arma el plan (`_armar_jerarquia`, `_armar_conceptos`, `_armar_partidas_concepto`, `_armar_apus`) con **un `ApuNuevo` por código de concepto**, según [el ADR del concepto único](../../../docs/adr/20261105-concepto-unico-y-concepto-de-partida.md). Ya no hay `assert` ni `# type: ignore` en el módulo. Devuelve la unión `ResultadoMaterializacion`.
- **Soporte de prueba:** variantes del libro sintético para `TC-A04` a `TC-A08`, los ayudantes `preparacion_con_*` (basados en `dataclasses.replace`), `insumos_registrados_sinteticos`, `contar_filas_de_obra` (lo usa a3) y la clave del panel alineada con `insumo_por_crear` (`PANEL YESO 1/2`).
- **Pruebas:** `test_tkt017_explosion_materializada.py` (3 tests) y `test_tkt017_plan.py` (88 tests, 43 de ellos casos de `test_tkt017_caa05_preparacion_inconsistente`).

### Decisiones de la persona dueña durante la revisión (2026-11-08)

Todas con la recomendación del orquestador aceptada.

| # | Decisión |
|---|---|
| D1 | El código repetido (invariante 39) se detecta **por nodo de partida**, con la clave (fila del nivel, fila del área, fila de la partida, código). El mismo código bajo dos partidas homónimas de áreas distintas es válido |
| D2 | Si coinciden una preparación malformada y una asignación incompleta, gana la estructura (`409`); se corrige `design.md` línea 60 |
| D3 | `AsignacionInvalida.faltantes` e `inexistentes` devuelven los **nombres de partida** normalizados, ordenados y sin repetir, no los UUID |
| D4 | Una preparación sin conceptos es `PreparacionInconsistente` con «la importación debe analizarse de nuevo» y `codigo_concepto` nulo |
| D5 | Dos claves de la asignación que normalizan igual con distinto tipo (`ambiguas`) se rechazan **solo si afectan a una partida requerida**; una ambigua sobrante se ignora (`P-12`) |
| D6 | El desborde de `NUMERIC` en los agregados es `PreparacionInconsistente` con `motivo` `explosion_presupuesto` (explosión) o `linea_base.importe_venta` (suma), `codigo_concepto` nulo |
| D7 | `insumo.unidad` no nula se exige a todo tipo de insumo, también a la mano de obra |
| D8 | Un mismo código de concepto en varias filas del catálogo con distinta **unidad** es `PreparacionInconsistente` con `motivo` `concepto.unidad`; la descripción distinta se tolera y gana la primera aparición (hallazgo de `code-review`, decisión del 2026-11-08 tras tu pregunta) |
| D9 | Toda alta de insumo de la importación se contrasta con la unidad y el tipo del insumo del análisis en **toda** aparición, también en la primera (`P-6`, ya aprobada; hallazgo de `code-review`) |

### Ajustes respecto al design

Sustantivos, todos reflejados en `design.md` en este mismo cambio (líneas 60, 166, 171, 172, 175, 191, 380, 381, 384, 385 y la fila `P-12`).

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-06 | Un solo `ApuNuevo` por `codigo` de concepto compartido | Coherencia con una hoja de análisis, con la explosión por concepto y con el ADR del concepto único |
| 2026-11-06 | `herramientas/soporte_tkt017.py`: clave del panel `TBR-015` → `PANEL YESO 1/2` | Alinea el ayudante de A2 (entrega a1) con `design.md` (A2) y con `CA-A1` |
| 2026-11-08 | Retorno `ResultadoMaterializacion` (unión de cinco tipos) en lugar de `RechazoMaterializacion` | El diseño nombraba un tipo que el código no necesita |
| 2026-11-08 | Orden de rechazos por fases globales: estructura, asignación, insumos, explosión | D2; el código intercalaba las fases por concepto |
| 2026-11-08 | `AsignacionInvalida` gana `ambiguas`; `faltantes` e `inexistentes` pasan a nombres | D5 y D3. a3 mapea `ambiguas` a `422` `VALOR_NO_PERMITIDO` en `asignacion_tipos_partida.{nombre}` (opción que la persona dueña aceptó el 2026-11-08; `design.md` línea 157 lo recoge) |
| 2026-11-08 | Motivo con el nombre de la columna para cada nulo o valor que no cabe; `totales.precio_unitario` deja de exigirse | El mapeo del diseño toma `apu.precio_unitario` del pie del análisis |
| 2026-11-08 | Rechazos nuevos: cero conceptos, `insumo.unidad` nula, desborde de agregados | D4, D7 y D6 |
| 2026-11-08 | Rechazo nuevo `concepto.unidad` y contraste de la alta de insumo con el análisis en toda aparición; un solo total de importes (`_Validados`); búsqueda de registrados por código en un diccionario | D8, D9 y los hallazgos Menores de `code-review` |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `cimenta/presupuesto/dominio/explosion_materializada.py` | nuevo | dominio |
| `cimenta/presupuesto/dominio/materializacion.py` | nuevo | dominio |
| `herramientas/soporte_tkt017.py` | modificado | herramientas |
| `tests/test_tkt017_explosion_materializada.py` | nuevo | pruebas |
| `tests/test_tkt017_plan.py` | nuevo | pruebas |
| `sdd/tickets/tkt-017/design.md` | modificado | SDD |
| `sdd/tickets/tkt-017/_index.md` | modificado | SDD |
| `sdd/tickets/tkt-017/delta.md` | modificado (una errata: «posteriors») | SDD |

### Pruebas

| # | Tests | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-A04 | `test_hdu001_esc11_el_plan_crea_un_concepto_con_dos_apariciones`, `test_hdu001_esc11_variante_733335`, `test_hdu001_esc11_niveles_areas_y_partidas_siguen_el_orden_del_catalogo` (10 repeticiones con `uuid4`), `test_hdu001_esc11_mismo_codigo_en_partidas_homonimas_de_areas_distintas_es_valido`, `test_hdu001_esc11_los_identificadores_del_plan_no_se_repiten` | feliz | `CA-A1` | FALLA | PASA |
| TC-A05 | `test_tkt017_caa03_*` (asignación incompleta o inexistente, orden, normalización, clave sobrante, ambiguas, estructura gana a asignación) | **rechazo** | `CA-A3` | FALLA | PASA |
| TC-A06 | `test_tkt017_caa06_*` (reutilización por alta y por descripción, conflicto por unidad y por tipo con los dos lados, alta compartida por dos conceptos) | feliz y **rechazo** | `CA-A6` | FALLA | PASA |
| TC-A07 | `test_tkt017_caa05_explosion_rechazada` | **rechazo** | `CA-A5` esc. 2 | FALLA | PASA |
| TC-A08 | `test_tkt017_caa05_preparacion_inconsistente` (43 casos con `motivo` y `codigo_concepto` literales) | **rechazo** | `CA-A5` | FALLA | PASA |
| TC-A09 | `test_tkt017_cab01_explotar_filas_mismo_resultado_distinto_orden`, `test_tkt017_cab01_explotar_filas_devuelve_valores_en_la_escala_de_su_columna`, `test_tkt017_cab01_sin_analisis_rechaza` | feliz y **rechazo** | `CA-B1` (determinismo de `explotar_filas`) | FALLA | PASA |

#### Ciclo TDD por fila

**Aviso de proceso.** `/sdd-ejecutar` del 2026-11-06 no guardó la salida en rojo de las filas A3 y A4: el rojo quedó descrito en prosa. Esa salida no se reconstruye. Para dejar rastro real, `/sdd-revisar` apartó el 2026-11-08 los dos módulos de producción, corrió los tests de cada fila y los volvió a colocar:

**Fila A3 · `explotar_filas` · rojo (2026-11-08, sin el módulo):**

```text
tests\test_tkt017_explosion_materializada.py:11: in <module>
    from cimenta.presupuesto.dominio.explosion_materializada import (
E   ModuleNotFoundError: No module named 'cimenta.presupuesto.dominio.explosion_materializada'
ERROR tests/test_tkt017_explosion_materializada.py
1 error in 0.22s
```

**Verde:** se implementó `explotar_filas` y pasaron los tests de `TC-A09`. **Refactor:** se alinearon con el dominio los tipos de retorno de `ExplosionRechazada.causas`.

**Fila A4 · `planificar_materializacion` · rojo (2026-11-08, sin el módulo):**

```text
tests\test_tkt017_plan.py:10: in <module>
    from cimenta.presupuesto.dominio.materializacion import (
E   ModuleNotFoundError: No module named 'cimenta.presupuesto.dominio.materializacion'
ERROR tests/test_tkt017_plan.py
1 error in 0.19s
```

**Verde:** se implementó `planificar_materializacion` y pasó `test_tkt017_plan.py`. **Refactor:** el módulo se reestructuró por completo en el ciclo de corrección 1.

**Fila A4c · mutantes `M-A2` y `M-A3`.** Se ejecutaron dos veces. La primera, en `/sdd-ejecutar`, con `M-A3` acotado a la cantidad. La segunda, sobre el código final, con el mutante tal como lo define el diseño (importe calculado con la cantidad y el precio sin cuantizar):

| Mutante | Cambio temporal (código final) | Tests en rojo | Revertido |
|---|---|---|---|
| M-A2 | El precio unitario del concepto de partida sale del catálogo (`concepto.precio_unitario`) en lugar del pie del análisis | `8 failed, 80 passed in 0.33s`: `test_hdu001_esc11_el_plan_crea_un_concepto_con_dos_apariciones`, `test_hdu001_esc11_variante_733335`, `test_tkt017_caa05_el_precio_de_los_totales_no_se_exige` y cinco casos de `test_tkt017_caa05_preparacion_inconsistente` (`precio_del_pie_nulo`, `precio_del_pie_que_no_cabe`, `importe_que_no_cabe` y los dos de `importe_de_venta_que_no_cabe`) | sí · md5 idéntico |
| M-A3 | `importe` = `concepto.cantidad × analisis.precio_unitario` sin cuantizar antes ninguno de los dos | `1 failed, 87 passed in 0.28s`: `test_hdu001_esc11_variante_733335` | sí · md5 idéntico |

#### Ciclo de corrección de `/sdd-revisar` (2026-11-08)

Cada ciclo escribió primero los tests y los corrió contra el código anterior.

- **Ciclo 1** (`corrector-revision`, `sonnet`): contra el código anterior, `test_tkt017_plan.py` terminó con `37 failed, 31 passed`. Los fallos se agruparon en estas causas: el código lanzaba `AssertionError` ante cantidad nula y ante mano de obra sin rendimiento o sin cargo; lanzaba `ValueError` porque la cantidad no cabía en `NUMERIC(14,4)`; el código repetido en áreas distintas devolvía `PreparacionInconsistente` en lugar de un plan; el orden del catálogo fallaba las diez veces con `uuid4`; los motivos citaban la columna equivocada; el código lanzaba `TypeError` porque el campo `ambiguas` no existía; `inexistentes` devolvía UUID; cero conceptos devolvía un plan vacío; una unidad nula se volvía cadena vacía. El mutante de `.cuantizar()` en `explotar_filas` dejó `1 failed, 2 passed`: lo mató el test nuevo de escala.
- **Ciclo 2** (`corrector-revision`, `sonnet`): contra el código anterior, el archivo terminó con `4 failed, 75 passed`; fallaron los casos de ambigua sobrante, `importe_venta` que no cabe en dos conceptos y en doce partidas, y explosión que no cabe. Los demás tests del ciclo (conflictos, orden de fases, alta compartida, normalización del catálogo, orden con seis nombres) ya pasaban y se comprobaron con mutantes que los ponen en rojo (M4b, M6, M7, M9, M16 y el intercambio de fases).
- **Ciclo 3** (`corrector-revision`, `haiku`): el test nuevo `test_tkt017_caa03_las_ambiguas_van_ordenadas` pasaba contra el código anterior. Con el mutante M35 (`tuple(sorted(ambiguas))` → `tuple(ambiguas)`) falla con `PYTHONHASHSEED` 1, 5 y 7 y pasa con 2, 3, 4, 6 y 8; el refactor posterior (derivar `ambiguas` de `requeridas`, ya ordenada) elimina la dependencia del orden de un conjunto.
- **Ciclo 5** (tras `code-review`; `corrector-revision`, `sonnet`): contra el código anterior, `test_tkt017_plan.py` terminó con `5 failed, 83 passed`; los cinco fallos devolvían un plan donde debía haber un rechazo: la alta con otra unidad o tipo en la primera aparición (2), la alta compartida con otra unidad o tipo en la segunda (2) y el mismo código con otra unidad (`concepto.unidad`). El test de «gana el primero» del diccionario por código y el de descripción distinta ya pasaban y se probaron con mutantes que los ponen en rojo.

### Modelo por paso

| Paso | Agente previsto | Modelo previsto | Modelo usado | Motivo |
|---|---|---|---|---|
| A3 rojo y verde | `tester-backend` → `desarrollador-dominio` | `sonnet` | Composer 2.5 (orquestador de Cursor), un solo agente para tests y código | Ejecución desde Cursor; **no hubo separación entre quien escribe los tests y quien escribe el código** |
| A4 rojo y verde | `tester-backend` → `desarrollador-dominio` | `sonnet` | Ídem | Ídem |
| A4c | `tester-backend` | `sonnet` | Ídem | Mutación manual |
| Corrección, ciclos 1 y 2 | `corrector-revision` | `haiku` por omisión | `sonnet` | El hallazgo raíz (validación duplicada) pedía reestructurar el módulo, no solo parchar |
| Corrección, ciclo 3 | `corrector-revision` | `haiku` por omisión | `haiku` | Texto literal del auditor |
| Corrección, ciclo 5 | `corrector-revision` | `haiku` por omisión | `sonnet` | Dos reglas de negocio de dominio con tests nuevos y un refactor del resolutor de insumos |

### Resultado contra criterios de aceptación (alcance a2)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-A1` (plan de `HDU-001` esc. 11, en dominio) | `[M]` | Cumplido | TC-A04: precio `420.0000` en ambos conceptos de partida, importes `5250.0000` y `3079.9860`, importe de venta `8329.9860`, variante `7.33335` → `3080.0280`, orden del catálogo, un solo concepto con dos apariciones. La escritura transaccional y la bitácora son de a3 |
| `CA-A3` | `[M]` | Cumplido en dominio | TC-A05. El `422` con el campo es de a3 |
| `CA-A5` (formato desconocido y explosión imposible) | `[M]` | Cumplido en dominio | TC-A07, TC-A08. El formato desconocido ya se rechaza en a1 (`FormatoPreparacionDesconocido`) |
| `CA-A6` | `[M]` | Cumplido en dominio | TC-A06 |
| `CA-B1` | `[M]` | **Parcial**: solo el determinismo y la escala de `explotar_filas`. El congelado, las copias y la bitácora son de TKT-017b | TC-A09 |

### Auditorías (`/sdd-revisar`, 2026-11-08)

La auditoría que `/sdd-ejecutar` anotó el 2026-11-06 («`auditor-arquitectura` · APROBADO», sin la sección «Qué verifiqué») queda sustituida por estos informes. `auditor-sql` no aplica: la entrega no trae migración, esquema ni consulta. `auditor-seguridad` no aplica: no hay endpoint, entrada externa, archivo, sesión, Dockerfile, Compose, flujo de CI ni dependencia nueva.

| Pasada | `auditor-arquitectura` | `auditor-codigo` | `auditor-docs` |
|---|---|---|---|
| Primera | **REQUIERE CAMBIOS** · `A-001` a `A-011` | **REQUIERE CAMBIOS** · `C-001` a `C-018` | **REQUIERE CAMBIOS** · `D-001` a `D-014` |
| Ciclo 1 | **REQUIERE CAMBIOS** · `N-001` a `N-005` (`A-001` a `A-010` resueltos) | **REQUIERE CAMBIOS** · `N-1`, `N-2`, `N-3` (`C-001` a `C-018` resueltos) | — |
| Ciclo 2 | **APROBADO** · tres observaciones de `design.md`, aplicadas | **REQUIERE CAMBIOS** · `N-4` (`N-1`, `N-2` y `N-3` resueltos) | — |
| Ciclo 3 | — | **REQUIERE CAMBIOS** · `N-4` persiste (el test con dos ambiguas solo mata el mutante con la mitad de las semillas) | — |
| Ciclo 4 (extra, autorizado) | — | `N-4` y `N-5` **resueltos**; `F-001` Menor (docstring) | Reauditoría 1: resueltos `D-002`, `D-003`, `D-005` a `D-010`, `D-013`, `D-014`, `O-001` y `O-003`; quedaron `D-004`, `D-012`, `O-004` y hallazgos nuevos `F001` a `F006` y `F009`, que se corrigieron. Reauditoría 2: **REQUIERE CAMBIOS** solo por redacción (`H-01`, `O-04`, `O-N1`, `O-N2`, `O-N3`), aplicada con el texto literal del auditor; todo lo demás **resuelto** |
| Ciclo 5 (tras `code-review`) | **APROBADO** · observación `F001` (trazabilidad de la alta en `design.md`) aplicada | **APROBADO** · observaciones `O2` y `O3` aplicadas; mutantes (a) a (f) muertos, el (g) equivalente | — |

El ciclo 4 se abrió porque los tres ciclos de corrección ya estaban gastados con un Menor vivo: la persona dueña autorizó, el 2026-11-08, un ciclo extra acotado a ese test. `F-001` es un docstring del test que prometía más de lo que comprobaba; lo resolvió el orquestador con el texto literal del auditor (opción A: «seis ambiguas salen ordenadas aunque el catálogo las lea de mayor a menor») y no abrió otra reauditoría, por el criterio de parada de redacción de `/sdd-revisar`.

#### Hallazgos y su resolución

| ID | Auditor | Severidad | Hallazgo | Resolución |
|---|---|---|---|---|
| `A-001`, `C-001`, `C-002`, `C-003`, `C-009`, `C-011` | arquitectura, código | Mayor | `assert` como control de flujo sobre la preparación; mano de obra sin rendimiento o sin cargo; cantidad nula; valores que no caben en su columna; validación duplicada | Resuelto: una sola validación (`_validar_conceptos`) con motivo por columna |
| `A-002`, `C-007`, `N-001` | arquitectura, código | Mayor | La asignación se normalizaba de tres maneras; las ambiguas se rechazaban aun siendo sobrantes | Resuelto: un solo mapa normalizado y `ambiguas` acotada a las partidas requeridas (`D5`) |
| `A-003`, `C-004` | arquitectura, código | Mayor | El duplicado se detectaba por nombre de partida y rechazaba el caso de `CA-A1` | Resuelto por `D1` |
| `A-004`, `C-008` | arquitectura, código | Menor y Mayor | `inexistentes` sin orden, con repetidos y con UUID | Resuelto por `D3` |
| `A-009`, `C-005` | arquitectura, código | Menor y Mayor | Orden de áreas y partidas por UUID aleatorio | Resuelto: orden por filas del catálogo, con prueba de diez repeticiones y `uuid4` |
| `A-006`, `C-016`, `C-017`, `C-018`, `N-2`, `N-003`, `N-004`, `N-4` | arquitectura, código | Mayor y Menor | Pruebas circulares o sin el dato del rechazo; mutantes supervivientes | Resuelto: literales de `CA-A1`, rechazos con `motivo` y `codigo_concepto`, mutantes M1 a M37 |
| `N-1`, `N-002` | código, arquitectura | Menor y Mayor | Desborde de `NUMERIC` en los agregados | Resuelto por `D6` |
| `A-007`, `C-006` | arquitectura, código | Menor y Mayor | Motivo con la columna equivocada | Resuelto |
| `A-005`, `A-008`, `C-010`, `C-012`, `C-013`, `C-014`, `C-015`, `N-3` | arquitectura, código | Menor | Ramas muertas, `type: ignore`, complejidad, nombres, docstring, `_IDS`, `Any` sin justificar | Resuelto |
| `A-010`, `A-011` | arquitectura | Observación | Docstring sin identificadores; sección de auditoría sin «Qué verifiqué» | Resuelto: esta sección |
| `D-001` | docs | Mayor | Sin salida real en rojo por fila ni para los mutantes | Resuelto en lo que se puede: el rojo de A3 y A4 se capturó el 2026-11-08 (sección «Ciclo TDD por fila»); el de `/sdd-ejecutar` no se guardó y se declara; los mutantes tienen su salida. La falta de separación entre tester y desarrollador queda declarada en «Modelo por paso» |
| `D-002` | docs | Mayor | `design.md` se contradecía en el orden de rechazos | Resuelto por `D2` |
| `D-003`, `D-013` | docs | Mayor y Menor | `TC-A08`, `TC-A05` y `TC-A06` con menos casos que el diseño | Resuelto: 43 casos, clave sobrante, id reutilizado, conflicto por tipo |
| `D-004`, `D-005`, `D-006`, `D-007`, `D-014` | docs | Menor | Nombres de test, tipo de retorno, ADR, nivel y docstring del diseño | Resuelto en `design.md` y en el docstring |
| `D-008`, `D-009`, `D-010`, `D-012` | docs | Menor | Ajuste de `soporte_tkt017.py` sin registrar, mutante `M-A3` distinto del diseño, `CA-B1` marcado como cumplido, prosa | Resuelto en esta sección |
| `D-011` | docs | Menor | `PA-T13` ambiguo entre tickets | Resuelto: esta sección no lo cita sin su ticket |
| `O-001` | docs | Observación | Archivos nuevos en CRLF | Resuelto: LF |
| `O-002` | docs | Observación | «posteriors» en la sección de a1 | Corregido a «posteriores» |
| `CR-1` a `CR-5` | `code-review` | Mayor y Menor | Alta de insumo sin contraste con el análisis (`CR-1`); código de concepto repetido con otra unidad (`CR-2`); búsqueda lineal de registrados (`CR-3`); suma de importes duplicada (`CR-4`); `except ValueError` amplio (`CR-5`) | `CR-1` a `CR-4` resueltos en el ciclo 5 (D8, D9); `CR-5` queda como deuda para a3 |
| `N-005`, `N-5`, `F-001` | arquitectura, código | Observación y Menor | Supuestos del diseño sin marca `(asumido)`; ambigua con tipos inválidos; docstring | Resuelto: marcados con la confirmación del 2026-11-08 |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `migraciones/versions/v0006_…py:178-183` y `tipos_base/numericos.py:216` | Las columnas `apu.costo_material`, `costo_mano_obra`, `costo_directo`, `total_cargos`, `total_indirectos` y `precio_unitario` son `numeric(14,4)` y `Dinero` cuantiza a `NUMERIC(18,4)`: un valor entre 10^10 y 10^14 pasa el dominio y lo rechaza PostgreSQL (`22003`). Anotarlo en la fila A5 (traductor) o A6a de a3 | Media |
| a3, fila A6a | El orden de `insumos_registrados` por `codigo` decide qué insumo gana en la resolución por descripción: fijar el `ORDER BY` | Media |
| a3, API | Definir cómo se traducen `ambiguas` y los motivos `explosion_presupuesto`, `linea_base.importe_venta` y `concepto.unidad` al contrato de error | Media |
| `materializacion.py` | El `except ValueError` alrededor de `explotar_filas` es amplio: hoy solo lo dispara el desborde de `cuantizar()`; vigilarlo en a3 | Baja |
| `migraciones` | El `CHECK >= 0` de `apu_insumo` no tiene contraparte en el dominio: un costo negativo pasaría el plan y fallaría en la base | Baja |
| `herramientas/soporte_tkt017.py` | Los ayudantes de prueba viven en un paquete de producción (patrón heredado de A2) | Baja |

### Preguntas para la persona dueña (respondidas el 2026-11-08)

| # | Pregunta | Recomendación |
|---|---|---|
| 1 | `D-001` (rastro de rojo y separación de roles): el rojo de A3 y A4 que consta es el de un módulo ausente (`ModuleNotFoundError`), obtenido en la revisión, y quien escribió los tests de A3 y A4 escribió también el código. ¿Se acepta como está declarado o se exige repetir A3 y A4 con roles separados? | Aceptarlo: los ciclos 1 y 2 registraron la salida en rojo (`37 failed, 31 passed` y `4 failed, 75 passed`); el ciclo 3 no tuvo rojo, porque su test nuevo ya pasaba contra el código anterior, y ningún ciclo guardó salida de verde ni de refactor. Los mutantes de dos auditores y del orquestador muestran que los tests prueban comportamiento. **Respuesta de la persona dueña (2026-11-08): aceptado como está declarado** |
| 2 | `F007`: la decisión `D1` (duplicado por nodo de partida, descartando el nombre) tiene una alternativa descartada con su porqué. ¿Merece un ADR o basta la regla de `design.md`? | Basta la regla de diseño: es una interpretación de invariante 39, no una decisión de arquitectura. **Respuesta de la persona dueña (2026-11-08): basta `design.md`** |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `sdd/tickets/tkt-017/design.md` | Orden de rechazos, retorno `ResultadoMaterializacion`, `AsignacionInvalida` con nombres y `ambiguas`, un `ApuNuevo` por código, motivos por columna, nombres de los tests de `TC-A05`, `TC-A08` y `TC-A09`, `P-12`; los supuestos nuevos marcados `(asumido: confirmado por la persona dueña el 2026-11-08)` |
| `docs/` y `CLAUDE.md` | Sin cambios: es dominio puro, sin endpoint, tabla ni migración (confirmado por `auditor-docs`) |

### Verificación final

Salida real de los comandos, desde `backend/` salvo `verificar_docs`, sobre el estado final (cinco ciclos de corrección). `docker info`: Docker 29.9.2 con el servidor en marcha. Una corrida anterior de la suite se descartó porque el demonio de Docker se cayó a mitad de la ejecución (los `E` eran de fixtures, no del código); se volvió a levantar Docker Desktop y se repitió.

```text
uv run ruff format --check .      → 246 files already formatted
uv run ruff check .               → All checks passed!
uv run mypy .                     → Success: no issues found in 246 source files
uv run lint-imports               → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → verificar_float: archivos revisados: 31; hallazgos: 0
uv run pytest tests/test_tkt017_plan.py tests/test_tkt017_explosion_materializada.py tests/test_tkt017_preparacion.py -q --no-cov → 95 passed
uv run pytest -q -ra --tb=short   → 2153 passed, 26 skipped in 356.70s (0:05:56)
python tools/verificar_docs.py    → ✓ Sin problemas.
```

Los 26 omitidos son las pruebas contra el archivo real del catálogo (`CIMENTA_CATALOGO_UNION` y `CIMENTA_CATALOGO_ENITI` sin definir; `PA-T3` de TKT-013 y de TKT-014, archivos reales). La suite completa se corrió con el estado final del código; después solo cambiaron documentos. El módulo `materializacion.py` queda con md5 `0c3c3639f457e1b659b9ff0abb79136d`. Antes de esa corrida, la corrección del quinto ciclo se verificó con `ruff`, `mypy`, `lint-imports`, `verificar_float` y los 95 tests de los tres archivos de a2.

#### Resultado `/sdd-revisar`

- [x] Criterios `[M]` de a2 con evidencia (tabla «Resultado contra criterios de aceptación»); `CA-B1` solo en lo que le toca a a2
- [x] Suite completa en verde: **2153 passed, 26 skipped**
- [x] `ruff`, `mypy`, `lint-imports`, `verificar_float` y `verificar_docs` en verde
- [x] Cada test de rechazo de dominio afirma el rechazo completo (`motivo` y `codigo_concepto`, o el objeto de valor entero con `==`); el contrato de error HTTP es de a3
- [x] Mutantes `M-A2` y `M-A3` en rojo con el código final; mutantes de los auditores M1 a M37 muertos, salvo el equivalente M25
- [x] Rastro de rojo por fila: real para A3 y A4 desde 2026-11-08; el de 2026-11-06 no se guardó y está declarado
- [x] Auditorías: `auditor-arquitectura` **APROBADO** (ciclo 5, tras `code-review`); `auditor-codigo` **APROBADO** (ciclo 5; antes, `N-4` y `N-5` resueltos en el ciclo 4 y `F-001` resuelto por el orquestador); `auditor-docs` sin más hallazgos que de redacción, aplicados con el texto literal del auditor y sin tercera reauditoría, por el criterio de parada de redacción de `/sdd-revisar`
- [x] `D-001` (rastro de rojo y roles) aceptado como está declarado por la persona dueña el 2026-11-08
- [ ] CI completo de GitHub Actions: se verifica en `/sdd-completar` al abrir el PR
- [ ] `CA-A1`, `CA-A3`, `CA-A5` y `CA-A6` de punta a punta (transacción, bitácora, `422` con el campo, `409`): son de TKT-017a3

**Veredicto:** **LISTO PARA PR** · entrega **TKT-017a2**. Cinco ciclos de corrección (tres, uno extra autorizado y uno posterior a `code-review`). Riesgo aceptado por la persona dueña: `D-001` (rastro de rojo y separación de roles de A3 y A4). Supuestos confirmados el 2026-11-08 y marcados en `design.md`: `D1` a `D7`. Deuda anotada para a3: mapeo de `ambiguas`, `explosion_presupuesto` y `linea_base.importe_venta` al contrato de error, `numeric(14,4)` frente a `Dinero` `(18,4)`, `ORDER BY` de `insumos_registrados`.

---

## TKT-017a3 · Traductor del motor, repositorio y confirmación de la importación (`/sdd-ejecutar` 2026-11-09)

> [← index](_index.md) | [← design](design.md) | Siguiente: `/sdd-revisar`. `/sdd-completar` no corre al cerrar esta entrega: según la regla de un solo PR por ticket, corre una vez, al aprobarse la última entrega (TKT-017c).

Entrega **TKT-017a3** (filas **A5**, **A6a**, **A6b**, **A6c**, **A7** y **A8**): el traductor de errores del motor, las tablas y el repositorio de la jerarquía, el caso de uso `materializar_importacion` con su bloqueo de la obra, el reemplazo del borrador, la documentación de la entrega y el cierre con mutación. Se ejecutó en la rama `tkt-017a3-materializacion`, que acumula también las entregas siguientes, y por primera vez con tester, desarrollador y auditor separados en cada fila. La entrega pasó por un ciclo de corrección de `auditor-arquitectura` (ver «Auditorías»).

### Qué se implementó

- **`aplicacion/traduccion_motor.py`:** `traducir_error_del_motor` convierte un `DBAPIError` del motor en el contrato de error, según la tabla del diseño: `IN001` en `RN-01`; `23505` de `uq_linea_base_obra_id_congelada` en el rechazo de la vigente; otro `23505`, `23503` y `23001` en `ESTADO_NO_PERMITE_OPERACION`; `55P03` en `BLOQUEO_VENCIDO`; `57014` en `TIEMPO_EJECUCION_VENCIDO`; `22003` en `ESTADO_NO_PERMITE_OPERACION`; cualquier otro, incluido `42501`, sin traducir.
- **`infraestructura/tablas.py` y `repositorio_linea_base.py`:** once tablas Core y las lecturas, el bloqueo `FOR UPDATE` de la obra, las inserciones, `borrar_jerarquia` (los nueve borrados de las hojas a la raíz) y `version_siguiente`. `insumos_registrados` se ordena por `codigo`.
- **`aplicacion/contexto.py` y `aplicacion/materializacion.py`:** `ContextoPresupuesto`, `construir_contexto` y `materializar_importacion`, con una sola transacción, el bloqueo en el orden importación → obra, la bitácora (`CONFIRMAR` y `DESCARTAR`) en la misma transacción y el reemplazo del borrador. `interfaz.py` publica los tres nombres.
- **`dominio/materializacion.py`:** `evaluar_importacion_confirmable` y `evaluar_confirmacion_en_obra`, las reglas de estado de la confirmación (`RN-01`), movidas al dominio por el hallazgo `F002`; un valor negativo en `apu_insumo.costo_unitario`, `rendimiento` o `cargo` es `PreparacionInconsistente`. `dominio/explosion_materializada.py` gana `ExplosionFueraDeEscala`, que acota el `except` que dejó a2.
- **`contrato_error/excepciones.py`:** el `detalle` admite `None` como valor.
- **`infraestructura/preparacion_json.py`:** una clave ausente o un tipo inesperado con `formato` 1 lanza `FormatoPreparacionDesconocido`, no `KeyError`.
- **Documentación (A7):** el ADR del ciclo de la línea base serializado por la obra y los cambios de las filas «a3» de «Documentación afectada» de `design.md`.

### Decisiones de la persona dueña durante la ejecución (2026-11-09)

Todas con la recomendación del orquestador aceptada.

| # | Decisión |
|---|---|
| D1 | Un solo texto para los `409` `ESTADO_NO_PERMITE_OPERACION` de `23505` (otra restricción), `23503` y `23001`: «La operación entra en conflicto con el estado actual de los datos.» |
| D2 | `57014` lleva un texto propio: «La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo.» |
| D3 | El traductor también traduce `22003` (valor fuera del rango de una columna `apu.*`) a `ESTADO_NO_PERMITE_OPERACION`, con el texto de «analizarse de nuevo» y detalle vacío (deuda de a2) |
| D4 | El `422` por claves ambiguas dice «Hay dos claves con distinto tipo para esta partida; deja una sola.»; el rechazo de preparación inconsistente lleva `importacion_id`, `motivo` y `codigo_concepto` en el detalle |
| D5 | El `detalle` del contrato de error admite `None` (se conserva como `null`), y se ajusta el caso `none` de TKT-005; `float` y `Decimal` sueltos siguen prohibidos |
| D6 | Las causas idénticas de una explosión rechazada se deduplican; el orden de los `422` de la asignación es faltantes, inexistentes y ambiguas, cada grupo por nombre; una preparación `NULL` en una importación `VALIDADO` es `409` con `formato` nulo |
| D7 | La regla de valores negativos se limita a `apu_insumo`; las demás columnas con `CHECK >= 0` quedan como riesgo declarado (ver `R-1`) |
| D8 | Las reglas de estado de la confirmación pasan de `aplicacion/` a `dominio/` (hallazgo `F002`) |
| D9 | Una sola rama y un único PR para las entregas restantes de TKT-017 (regla de un PR por ticket; ver el hub) |

### Riesgo declarado

| # | Riesgo | Por qué se acepta | Quién y cuándo |
|---|---|---|---|
| `R-1` | Un valor negativo en `apu.costo_material`, `costo_mano_obra`, `costo_directo`, `total_cargos`, `total_indirectos` o `precio_unitario`, o en `apu_cargo.porcentaje`, `base_calculo` o `importe`, pasa el dominio y la base lo rechaza con `23514`, que el traductor no traduce: la respuesta es `500` sin `tipo`. `auditor-arquitectura` lo reportó como `F001` Mayor | El lector del catálogo no produce negativos en esas columnas, y la persona dueña eligió, informada del `500`, no ampliar la regla de dominio en a3. Queda como deuda hacia TKT-018, que medirá el archivo real | Persona dueña, 2026-11-09 |
| `R-2` | **Desviación del rojo.** Los tests de A5, A6a y A6b nacieron en rojo por `ModuleNotFoundError` del módulo que la fila debía crear (A5: 15 casos; A6a: 55 de 61) o por el `NotImplementedError` provisional de la rama de reemplazo (A6b, que sí es de comportamiento). `/sdd-ejecutar` dice que un módulo ausente no cuenta como rojo por la razón esperada cuando el test debe fallar por comportamiento | Un módulo que no existe no admite otro fallo sin escribir producción. Los tests importan el módulo dentro del caso o de una fixture, después de provocar el error real, y se comprobó que son satisfacibles y que atrapan errores con una implementación de referencia fuera del repositorio y con mutantes sobre ella. El orquestador lo aceptó al ejecutar y la persona dueña lo confirmó el 2026-11-09, al cerrar `/sdd-ejecutar` | Orquestador, 2026-11-09; confirmado por la persona dueña, 2026-11-09 |

### Ajustes respecto al design

Reflejados en `design.md` en este mismo cambio (sección «Ajustes de la ejecución de TKT-017a3» y las filas A5 a A8).

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-09 | Fila `22003` y mensajes de `23505`, `23503`, `23001` y `57014` en «Traducción del motor» | D1, D2 y D3 |
| 2026-11-09 | `evaluar_importacion_confirmable` y `evaluar_confirmacion_en_obra` en dominio | D8; el diseño las ubicaba en `aplicacion/` |
| 2026-11-09 | `borrar_jerarquia(sesion_bd, obra_id, linea_base_id)` y borrado después de planificar | El último paso borra por `id`; nada se rechaza con escrituras hechas |
| 2026-11-09 | `esperar_hasta` y `motor_espera_corta` son fixtures de `tests/conftest.py`; `contar_filas_en_base` y `foto_de_base` en `herramientas/soporte_tkt017.py` | La fila A1 no dejó `esperar_hasta` en `conftest.py`; `contar_filas_de_obra` cuenta lo que insertaría un plan, no lo que hay en la base |
| 2026-11-09 | `ExplosionFueraDeEscala` acota el `except` alrededor de `explotar_filas` | Deuda de a2 (`CR-5`) |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/aplicacion/traduccion_motor.py` | nuevo | aplicación |
| `backend/cimenta/presupuesto/aplicacion/contexto.py` | nuevo | aplicación |
| `backend/cimenta/presupuesto/aplicacion/materializacion.py` | nuevo | aplicación |
| `backend/cimenta/presupuesto/infraestructura/repositorio_linea_base.py` | nuevo | infraestructura |
| `backend/cimenta/presupuesto/infraestructura/tablas.py` | modificado | infraestructura |
| `backend/cimenta/presupuesto/infraestructura/preparacion_json.py` | modificado | infraestructura |
| `backend/cimenta/presupuesto/dominio/materializacion.py` | modificado | dominio |
| `backend/cimenta/presupuesto/dominio/explosion_materializada.py` | modificado | dominio |
| `backend/cimenta/presupuesto/interfaz.py` | modificado | aplicación |
| `backend/contrato_error/excepciones.py` | modificado | contrato de error |
| `backend/herramientas/soporte_tkt017.py` | modificado | herramientas |
| `backend/tests/conftest.py` | modificado | pruebas |
| `backend/tests/test_contrato_error_construccion.py` | modificado (el caso `none` de TKT-005 pasa a admitir `None`) | pruebas |
| `backend/tests/test_tkt017_traduccion.py`, `test_tkt017_materializacion.py`, `test_tkt017_materializacion_concurrencia.py`, `test_tkt017_confirmacion.py` | nuevos | pruebas |
| `docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md` y su fila en `docs/adr/README.md` | nuevo | documentación |
| `docs/adr/20261105-preparacion-de-importacion-en-jsonb.md`, `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | modificados | documentación |
| `docs/api/openapi.yaml`, `docs/04-historias-usuario.md`, `docs/05-tickets-trabajo.md` | modificados | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificados (conteo de ADR de 39 a 40) | documentación |
| `sdd/tickets/tkt-011/spec.md`, `sdd/tickets/tkt-014/spec.md`, `sdd/tickets/tkt-017/design.md`, `sdd/tickets/tkt-017/_index.md` | modificados | SDD |

Además, antes de esta entrega, el commit `cf56ac3` de la misma rama cambió el toolkit (un solo PR por ticket partido en entregas): `git-entrega`, las skills `sdd-completar`, `sdd-revisar`, `sdd-ejecutar` y `sdd-disenar`, la metodología, las plantillas y una frase de `CLAUDE.md`. No es del alcance de a3 y viaja en el mismo PR.

### Pruebas

| # | Tests | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-A24 | `test_tkt017_cab06_traduccion_de_sqlstate` (12 casos: `IN001` ×2, `23505` ×3, `23503`, `23001`, `55P03`, `57014`, `42501`, `22P02`, `22003`) y `test_tkt017_cab06_la_accion_reintentar_repite_la_operacion_que_recibio_el_traductor` (4) | **rechazo** | `CA-B6` esc. 1 | FALLA | PASA |
| TC-A10 | `test_hdu001_esc11_confirmar_materializa_la_jerarquia` y cinco compañeras con el mismo prefijo | feliz | `CA-A1` | FALLA | PASA |
| TC-A11 a TC-A17 | `test_hdu001_esc11_confirmar_con_errores_responde_importacion_con_errores`, `test_tkt017_caa02_*`, `caa03_*`, `caa04_*`, `caa05_*` y `caa06_*` de `test_tkt017_materializacion.py` | feliz y **rechazo** | `CA-A2` a `CA-A6` | FALLA | PASA |
| Nota sobre `CA-A2` | `test_hdu001_esc11_confirmar_con_errores_responde_importacion_con_errores` cubre el escenario 11 y el rechazo `IMPORTACION_CON_ERRORES` de `CA-A2`. Los escenarios 6 a 9 de HDU-001 (fórmula rota, concepto sin análisis, unidad desconocida y código duplicado) son los errores que produce el análisis, que prueban los tests de TKT-014, TKT-015 y TKT-016; a3 solo comprueba que una importación con errores no se confirma. Ningún test de a3 lleva el número de esos escenarios en su nombre, y la cobertura por nombre se decide al activar HDU-001 en la fila C4 (`P-13`). Decisión de la persona dueña del 2026-11-09 | — | `CA-A2` | — | — |
| TC-A19, TC-A20 | `test_hdu001_esc13_reemplazo_sin_confirmar` (con motivo y con `reemplazar_borrador` falso), `test_hdu001_esc13_reemplazo_sin_motivo` (`None`, vacío y en blanco) | **rechazo** | `CA-A8` | FALLA | PASA |
| TC-A18, TC-A21 | `test_hdu001_esc12_fallo_a_mitad_no_deja_nada` (nace en verde: la transacción única de A6a ya lo cumple), `..._del_reemplazo_no_deja_nada` y los nueve `test_hdu001_esc13_reemplazo_confirmado*` | **rechazo** y feliz | `CA-A7`, `CA-A9` | FALLA (11 de 14) | PASA |
| TC-A22, TC-A23 | `test_tkt017_caa10_dos_confirmaciones_simultaneas`, `..._la_confirmacion_espera_el_bloqueo_de_la_obra`, `..._y_vence`, `..._motor_espera_corta_es_del_rol_de_aplicacion_con_200_ms` | concurrencia y **rechazo** | `CA-A10` | **Nacen en verde**: el bloqueo ya existía desde A6a; los protege el mutante `M-A1` (ver «Mutantes») | PASA, tres corridas seguidas |
| `F002` | `test_tkt017_confirmacion.py` (30 casos de las dos funciones de dominio) | **rechazo** | `CA-A2`, `CA-A4`, `CA-A8` | FALLA | PASA |

### Ciclo TDD por fila

Cada fila tuvo tester y desarrollador distintos. Salida del rojo, literal salvo el recorte con puntos suspensivos:

**Fila A5 · rojo** (`uv run pytest tests/test_tkt017_traduccion.py -q -ra`, antes de `traduccion_motor.py`):

```text
FAILED ...test_tkt017_cab06_traduccion_de_sqlstate[in001_copia_de_concepto]
... (los 15 casos)
15 failed in 17.56s
     15 E   ModuleNotFoundError: No module named 'cimenta.presupuesto.aplicacion.traduccion_motor'
```

Experimentos previos `E-6` y `E-7`, con el rol de aplicación sobre una base migrada por `alembic upgrade head`: `IN001` llega como `DatabaseError` (no `IntegrityError`) con `constraint_name='trg_linea_base_concepto_inmutable'`; `23505` como `IntegrityError` con `uq_linea_base_obra_id_congelada`; `55P03` y `57014` como `OperationalError` sin `constraint_name`; `23503` y `23001` como `IntegrityError`; `42501` como `ProgrammingError`; `22P02` como `DataError`; `SHOW lock_timeout` devuelve `200ms` con `connect_args={"options": "-c lock_timeout=200ms"}`. **Verde:** `15 passed in 5.15s`. Tras la decisión D3 se añadió el caso `22003`: rojo `1 failed, 15 passed in 6.46s` (el traductor devolvía `None`), verde `16 passed in 6.07s`.

**Fila A6a · rojo** (`tests/test_tkt017_materializacion.py`): `61 failed in 11.15s`, sin errores; 55 por `ModuleNotFoundError: No module named 'cimenta.presupuesto.aplicacion.contexto'` y 6 por `AssertionError` de dominio (un valor negativo en `apu_insumo` devolvía un plan). Tras las decisiones D4 a D6: `68 failed, 123 passed` en los dos archivos (4 de `test_contrato_error_construccion.py` por `TypeError: detalle.formato no admite NoneType`). **Verde:** `191 passed in 20.76s`.

**Fila A6b · rojo:** `11 failed, 67 passed in 21.96s`; los 11 lanzaban el `NotImplementedError("El reemplazo del borrador llega con la fila A6b...")` provisional de la rama de reemplazo, y el de `..._fallo_a_mitad_del_reemplazo_no_deja_nada` fallaba además por `Regex pattern did not match`. **Verde:** `78 passed`.

**Fila A6c:** los cuatro tests nacen en verde. Se investigó cada uno: `M-A1` los pone en rojo (ver «Mutantes»). Un primer intento de la variante `..._y_vence` pasaba también con el mutante porque la segunda importación fallaba por el índice de `insumo.codigo`; se corrigió registrando el insumo de antemano. Tres corridas seguidas del archivo: `4 passed` cada una.

**Fila A7 · documentación:** `python tools/verificar_docs.py` → «✓ Sin problemas.»; 40 ADR.

**Ciclo de corrección (hallazgo `F002`):** rojo `30 failed in 0.27s` (`AttributeError`: las funciones de dominio no existían) y `3 failed, 79 passed in 22.24s` por la clave `obra` del detalle (`F005`); verde `255 passed in 26.82s`.

### Mutantes

La fila A8 los ejecutó uno a uno, con copia previa fuera del repositorio y la huella SHA-256 de todo el árbol `.py` idéntica tras cada reversión.

| Mutante | Cambio | Tests que cayeron |
|---|---|---|
| `M-A1` | Quitar `with_for_update()` de `bloquear_obra` | `test_tkt017_caa10_dos_confirmaciones_simultaneas`, `..._la_confirmacion_espera_el_bloqueo_de_la_obra`, `..._y_vence` (`3 failed, 1 passed`; el primero cayó en cuatro de cuatro corridas) |
| `M-A4` | Calcular la versión antes del borrado | `test_hdu001_esc13_reemplazo_confirmado`, `..._asienta_descartar_y_confirmar`, `..._la_version_se_calcula_despues_del_borrado` (`3 failed, 75 passed`) |
| `M-A5` | Comprobar el estado de la obra antes que la línea base congelada | En A8, `test_tkt017_caa04_obra_que_no_admite_linea_base_con_congelada`. Tras mover la regla al dominio se repitió sobre `evaluar_confirmacion_en_obra`: seis tests (`6 failed, 102 passed`), cinco de `test_tkt017_confirmacion.py` y el de caja negra |
| `M-A6` | Añadir `DELETE FROM linea_base_concepto` a `borrar_jerarquia` | Nueve tests de reemplazo (`9 failed, 69 passed`), por `InsufficientPrivilege` |
| `M-A7` | `23505` de cualquier restricción en el rechazo de `RN-01` | `test_tkt017_cab06_traduccion_de_sqlstate[23505_codigo_de_insumo]` y `[23505_clave_de_tipo_de_partida]` (`2 failed, 14 passed`) |

Además, el auditor ejecutó por su cuenta `M-A9` (borrar `concepto` sin filtrar por obra), que cae en dos tests. Los tests `test_hdu001_esc12_fallo_a_mitad_no_deja_nada` y los dos de versión sin borrador nacieron en verde y solo los protege el comportamiento que cubren: no se les probó un mutante.

### Modelo por paso

| Paso | Agente previsto | Modelo previsto | Modelo usado | Motivo |
|---|---|---|---|---|
| A5, A6a, A6b, A6c, A8 (rojo y mutación) | `tester-backend` | `sonnet` | `sonnet` | Valor de la fila |
| A5, A6a y A6b (verde) | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparadores de la fila: concurrencia, bloqueo pesimista y disparador de inmutabilidad |
| Dominio de A6a (negativos y `except`) | `desarrollador-dominio` | `haiku` | `sonnet` | Regla de dinero de la explosión y refactor de una excepción |
| A7 | El orquestador, con `conv-documentacion` | — | Agente `general-purpose` en `sonnet` | Trabajo documental extenso, con un encargo literal y revisión del orquestador (quitó una viñeta no pedida del ADR) |
| Ciclo de corrección, dominio y aplicación de `F002` | `desarrollador-dominio` y `desarrollador-aplicacion` | `haiku` | `sonnet` | Mueve una regla de negocio entre capas |
| Ciclo de corrección, `N1` y `N2` | `corrector-revision` | `haiku` | `haiku` | Texto literal del auditor |
| Auditoría de cierre y reauditoría | `auditor-arquitectura` | `sonnet` | `sonnet` | Valor de la tabla |

### Resultado contra criterios de aceptación (alcance a3)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-A1` | `[M]` | Cumplido | TC-A10 con los literales `5250.0000`, `3079.9860` y `8329.9860` del plan de a2, escritos contra la base: jerarquía, línea base `BORRADOR` versión 1, importación `CONFIRMADO` y asiento `CONFIRMAR` |
| `CA-A2`, `CA-A3`, `CA-A4`, `CA-A5`, `CA-A6` | `[M]` | Cumplido | TC-A11 a TC-A17 con el contrato de error completo y la comprobación de que no se escribió nada (`foto_de_base`) |
| `CA-A7` | `[M]` | Cumplido | TC-A18: el `RuntimeError` provocado a mitad de la inserción se propaga y no queda ninguna fila ni asiento |
| `CA-A8`, `CA-A9` | `[M]` | Cumplido | TC-A19 a TC-A21: `REEMPLAZO_NO_CONFIRMADO` con acciones por rol, `422` de motivo, reemplazo con `DESCARTAR` y versión posterior al borrado |
| `CA-A10` | `[M]` | Cumplido | TC-A22 y TC-A23, y `M-A1` |
| `CA-A11` | `[M]` | Cumplido en a1 | `test_tkt017_migracion.py` |
| `CA-A12` | `[M]` | Cumplido | Las filas «a3» de «Documentación afectada» aplicadas; `verificar_docs` en verde |
| `CA-R1` | `[M]` | Cumplido | Suite completa en verde con `lint-imports` en 16 contratos mantenidos |
| `CA-B1` y `CA-B6` | `[M]` | **Parcial** | Solo el traductor (TC-A24, `CA-B6` esc. 1). El congelado y los escenarios 2 y 3 son de TKT-017b1 |

### Auditorías

`auditor-sql` no aplica: la entrega no trae migración ni esquema, y las consultas son Core sin DDL (`auditor-arquitectura` las revisó). `auditor-seguridad` no aplica: no hay ruta, entrada externa, archivo, sesión, Dockerfile, Compose, flujo de CI ni dependencia nueva. Las auditorías de código y de documentación corresponden a `/sdd-revisar`.

| Pasada | `auditor-arquitectura` |
|---|---|
| Primera (`/sdd-ejecutar`, paso 6) | **REQUIERE CAMBIOS** · `F001` Mayor, `F002` y `F003` Menores, `F004` a `F006` Observaciones |
| Ciclo 1 de corrección y reauditoría | **APROBADO** · `F002`, `F004` y `F005` resueltos, `F003` resuelto con esta sección y `design.md`, `F001` aceptado como riesgo declarado `R-1`; observaciones `N1` y `N2` aplicadas con el texto literal del auditor, `N3` y `F006` sin aplicar |

#### Hallazgos y su resolución

| ID | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| `F001` | Mayor | Los negativos de las otras columnas con `CHECK >= 0` llegan a la base como `23514` y responden `500` | **Riesgo declarado `R-1`**: decisión de la persona dueña del 2026-11-09, deuda hacia TKT-018 |
| `F002` | Menor | La capa de aplicación decidía reglas de estado de la confirmación | Resuelto: `evaluar_importacion_confirmable` y `evaluar_confirmacion_en_obra` en dominio, con 30 tests y `M-A5` repetido |
| `F003` | Menor | El `detalle` con `None` y el `22003` sin respaldo escrito | Resuelto: decisiones `D3` y `D5` de esta sección, `design.md` y el ADR de inmutabilidad |
| `F004`, `N1` | Observación | Andamiaje de fase roja (`importlib`, `Any`) en los tests | Resuelto en los cuatro archivos de pruebas |
| `F005` | Observación | La clave `obra` del detalle tenía dos formatos | Resuelto: `«{codigo} · {nombre}»` en los dos rechazos |
| `N2` | Observación | `_rechazar_si_obra_no_admite` terminaba en un `raise` sin comprobar la causa | Resuelto: comprobación explícita y `AssertionError` para una causa no mapeada |
| `F006` | Observación | `delete(linea_base)` no filtra por `estado = 'BORRADOR'` | Sin aplicar: el disparador `IN001` es la barrera; a considerar en TKT-017b1 |
| `N3` | Observación | La aplicación selecciona por la cadena `"CONGELADA"` y `"BORRADOR"` y construye el detalle de la congelada en dos sitios | Sin aplicar: clasificación de datos, no decisión |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `aplicacion/traduccion_motor.py` (`22003`) | El mensaje de «analizarse de nuevo» no aplica cuando el congelado (TKT-017b1) reciba un `22003`: ajustar entonces | Media |
| `interfaz.py` | Publica `ContextoPresupuesto` pero no `construir_contexto`: `montar_presupuesto` (b1) decidirá cómo se construye desde `servidor/` | Baja |
| `aplicacion/materializacion.py` (`_rechazo_vigente`) | Si el `23505` de la vigente llega y la congelada ya no existe al releer, el rechazo cae en `NoEncontrado(importacion)`, engañoso. Carrera extrema detrás del índice único | Baja |
| `tests/test_tkt017_materializacion.py` | `Entorno` y `Base` son clases de soporte de unas 300 líneas dentro del archivo de pruebas: extraer si b1 las necesita | Baja |
| `tools/historias_activas.txt` | `verificar_escenarios.py` da «exigidos 0 · cubiertos 0 · pendientes 164» porque HDU-001 sigue `PENDIENTE`: su verde no prueba la cobertura de escenarios de este ticket; la prueba la tabla de «Pruebas» y la activación es `P-13` en la fila C4 | Media |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md` y `docs/adr/README.md` | ADR nuevo y su fila en el índice |
| `CLAUDE.md`, `README.md` (dos sitios) y `llms.txt` | Conteo de ADR de 39 a 40 (edición de `CLAUDE.md` autorizada por `P-11`) |
| `docs/api/openapi.yaml` | `ConfirmacionImportacion` con `asignacion_tipos_partida`, `requestBody` obligatorio y descripción del `409` de `confirmar_importacion` |
| `docs/04-historias-usuario.md` | HDU-001 esc. 12: la importación nunca sale de `VALIDADO` |
| `docs/adr/20261105-preparacion-de-importacion-en-jsonb.md`, `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | Formato desconocido en `409`; tabla de `SQLSTATE` del traductor |
| `sdd/tickets/tkt-011/spec.md`, `sdd/tickets/tkt-014/spec.md` | `PA-T17` y `PA-T13` resueltas el 2026-11-05 |
| `docs/05-tickets-trabajo.md` | Fichas de TKT-017 y TKT-018 |
| `sdd/tickets/tkt-017/design.md` | Filas A5 a A8, traducción del motor y la sección «Ajustes de la ejecución de TKT-017a3» |

### Verificación final

Salida real de los comandos, desde `backend/` salvo los de documentación, sobre el estado final (un ciclo de corrección). `docker info`: Docker 29.9.2 con el servidor en marcha.

```text
uv run ruff format --check .      → 254 files already formatted
uv run ruff check .               → All checks passed!
uv run mypy .                     → Success: no issues found in 254 source files
uv run lint-imports               → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → verificar_float: archivos revisados: 31; hallazgos: 0
uv run pytest tests/test_tkt017_traduccion.py tests/test_tkt017_materializacion.py tests/test_tkt017_materializacion_concurrencia.py tests/test_tkt017_confirmacion.py -q → 128 passed in 37.14s
uv run pytest -q -ra --tb=short   → 2283 passed, 26 skipped in 376.00s (0:06:16)
python tools/verificar_docs.py    → ✓ Sin problemas.
python tools/verificar_escenarios.py → Escenarios: 164 · exigidos 0 · cubiertos 0 · faltan 0 · pendientes 164 · retirados 0
python -m unittest discover -s tools/tests → Ran 510 tests in 20.615s · OK
```

Los 26 omitidos son las pruebas contra el archivo real del catálogo (`CIMENTA_CATALOGO_UNION` y `CIMENTA_CATALOGO_ENITI` sin definir; `PA-T3` de TKT-013 y de TKT-014, archivos reales). `verificar_escenarios.py` no exige ningún test de HDU-001 mientras `tools/historias_activas.txt` la deje `PENDIENTE`: su verde no prueba la cobertura de los escenarios de este ticket.

#### Resultado `/sdd-ejecutar`

- [x] Filas A5, A6a, A6b, A6c, A7 y A8 hechas, cada una con su rojo, su verde y su refactor
- [x] Mutantes `M-A1` y `M-A4` a `M-A7` en rojo, revertidos con huella idéntica
- [x] Suite completa, `ruff`, `mypy`, `lint-imports`, `verificar_float` y `verificar_docs` en verde
- [x] `auditor-arquitectura` **APROBADO** tras un ciclo de corrección
- [ ] Auditorías de código y de documentación y revisión criterio por criterio: son de `/sdd-revisar`
- [x] `R-2` (rojo por módulo ausente): aceptado por la persona dueña el 2026-11-09
- [ ] CI completo de GitHub Actions: se verifica en `/sdd-completar`, al abrir el PR único de TKT-017

### Revisión (`/sdd-revisar`, 2026-11-09) · entrega TKT-017a3

La revisión corrió la suite completa, los linters y los verificadores de documentación, y despachó cuatro auditorías sobre el diff de la entrega (arquitectura, SQL, código y documentación). `auditor-seguridad` no aplica: la entrega no trae ruta, entrada externa, archivo, sesión, Dockerfile, Compose, flujo de CI ni dependencia nueva.

#### Auditorías y ciclos de corrección

| Auditor | Primera pasada | Ciclo 1 | Ciclo 2 | Estado final |
|---|---|---|---|---|
| `auditor-arquitectura` | **APROBADO** (observaciones `N4` y `N5` nuevas; `F001` sigue aceptado como `R-1`) | **APROBADO** (`N4` y `N5` resueltos; observación `N6`) | — | **APROBADO** |
| `auditor-sql` | **REQUIERE CAMBIOS** (`F101` Mayor, `F102` y `F103` Menores) | **APROBADO** (`F101` y `F102` resueltos; `F103` queda como deuda; observación `F104`) | — | **APROBADO** |
| `auditor-codigo` | **REQUIERE CAMBIOS** (tres Mayores y siete Menores) | **REQUIERE CAMBIOS** (los diez resueltos; dos Menores nuevos) | **APROBADO** (los dos Menores resueltos) | **APROBADO** |
| `auditor-docs` | **REQUIERE CAMBIOS** (cuatro Mayores y cinco Menores) | **REQUIERE CAMBIOS** (los de la primera pasada resueltos; dos Mayores y dos Menores nuevos) | **REQUIERE CAMBIOS** (un Menor vivo, `F012`) | **APROBADO CON MENORES RESUELTOS SIN REAUDITAR** |

Los identificadores de cada auditor son independientes entre sí: `F101`, `F102` y `F103` de `auditor-sql` no son los de `auditor-codigo` ni los de `auditor-docs`.

| Auditor y ID | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| SQL `F101` | Mayor | `insumos_registrados` construía `TipoInsumo(f.tipo)` con un enum de dos valores, mientras que `ck_insumo_tipo` admite también `HERRAMIENTA` y `CONSUMIBLE`: un insumo de esos tipos daba `500` en toda confirmación | Decisión de la persona dueña: `TipoInsumo` con los cuatro valores. Dos tests nuevos (`test_tkt017_caa06_*herramienta*`) y el mutante `M-F101` |
| SQL `F102` y código `F006` | Menor | Una `fecha_analisis` calendario-imposible (`2026-02-30`) pasa el lector, deja la importación en `VALIDADO` y al confirmar da `500` | Decisión de la persona dueña: `preparacion_desde_json` valida la fecha y lanza `FormatoPreparacionDesconocido` (`409`, «analizarse de nuevo»). Cuatro tests nuevos y el mutante `M-F102`. Deuda hacia TKT-018: que el lector rechace fechas imposibles (hoy, volver a analizar el mismo archivo reproduce la fecha) |
| SQL `F103` | Menor | `linea_base_concepto.partida_concepto_id` no tiene índice; cada fila borrada de `partida_concepto` obliga a recorrer esa tabla | Deuda hacia la migración de TKT-017b1 (`CREATE INDEX ix_linea_base_concepto_partida_concepto_id ON linea_base_concepto (partida_concepto_id)`). a3 no lleva migración |
| Código `F001`, arquitectura `N4` y docs `F001` | Mayor y Observación | `_rechazo_vigente` y `_rechazo_congelada` eran código sin test y el diseño y el ADR decían `RN-01` mientras el código devuelve `ESTADO_NO_PERMITE_OPERACION` | Decisión de la persona dueña: un solo `_conflicto_obra_con_congelada`, un test que fuerza el `23505` real (`test_tkt017_caa04_congelada_que_aparece_durante_la_confirmacion_responde_lo_mismo_que_la_vigente`), y `design.md`, el ADR de inmutabilidad y `spec.md` dicen que en la confirmación es `CONFLICTO` y en el congelado (TKT-017b1) será `RN-01`. Mutante `M-F001` |
| Código `F002` | Mayor | Ningún test pasaba un cero a `_no_negativa`; el mutante `<` por `<=` sobrevivía | `test_tkt017_caa05_cero_en_apu_insumo_es_valido`, cinco casos. Mutante `M-F002` |
| Código `F003` | Mayor | `bloquear_importacion` no tenía test que lo protegiera | `test_tkt017_caa10_dos_confirmaciones_de_la_misma_importacion_se_serializan`. Mutante `M-F003`, tres corridas de tres |
| Código `F004` a `F010` y ciclo 2 | Menores | Aserciones circulares, `409` sin contrato completo, docstring obsoleto, nombre de test, mensaje duplicado, `cast` sobre `datos` y `esperar_hasta` duplicado | Aplicados con el texto literal del auditor. `esperar_hasta` queda en `herramientas/tiempo_de_prueba.py` y devuelve `bool` |
| Docs `F001` a `F013` | Mayores y Menores | Descripción del `409` de `openapi.yaml` sin `CONCURRENCIA`; `PA-T17.10` en el ADR; citas de `RN-18` por `F1.6`; `spec.md` con `RN-01` en la confirmación; cuenta de casos; ADR del ciclo | Aplicados con el texto literal. `F003` (escenarios 6 a 9) se resuelve con la nota «Nota sobre `CA-A2`» de la tabla de pruebas, por decisión de la persona dueña |
| Docs `F012` (ciclo 2) | Menor | Tres citas más de `RN-18` para el versionado (`spec.md:70`, `spec.md:87` y `_index.md:71`) | Resuelto por el orquestador con el texto literal del auditor, sin tercera reauditoría (criterio de parada de `/sdd-revisar`, paso 4): `F1.6`, v1.1 |

#### Decisiones de la persona dueña durante la revisión (2026-11-09)

| # | Decisión |
|---|---|
| `D10` | `TipoInsumo` con los cuatro valores del `CHECK` de la base |
| `D11` | Un solo constructor del `ConflictoEstado` de la congelada y un test que fuerza el `23505` real; en la confirmación el rechazo es `CONFLICTO`, en el congelado será `RN-01` |
| `D12` | La fecha de análisis ilegible es un `409` desde la preparación; el lector de TKT-018 recibe la deuda de rechazar fechas imposibles |
| `D13` | Los escenarios 6 a 9 de HDU-001 los cubren los tests del análisis; la cobertura por nombre se decide al activar HDU-001 en la fila C4 |
| `D14` | `F104` (`issubset` por igualdad en `test_tkt014_lector.py:202`) queda como deuda; no se toca un test de otro ticket en esta entrega |

#### Riesgo declarado de la revisión

| # | Riesgo | Por qué se acepta | Quién y cuándo |
|---|---|---|---|
| `R-3` | La fila A6c y `test_hdu001_esc12_fallo_a_mitad_no_deja_nada` nacieron en verde y no registran salida de rojo por comportamiento, porque el bloqueo y la transacción única ya existían desde A6a | Los protegen mutantes: `M-A1` (tres de cuatro tests caen), `M-F003` (tres de tres corridas) y, para `TC-A18`, el mutante de la transacción (`commit` tras `insertar_conceptos`) que ejecutó `auditor-codigo` | Persona dueña, 2026-11-09 |

#### Deuda y observaciones fuera de alcance

| Dónde | Observación | Hacia |
|---|---|---|
| Índice de `linea_base_concepto` | `F103` de `auditor-sql`: índice sobre `partida_concepto_id` | Migración de TKT-017b1 |
| Lector del análisis | Fecha calendario-imposible (`2026-02-30`) llega a `VALIDADO`; reanalizar no sale del `409` | TKT-018 |
| `tests/test_tkt014_lector.py:202` | `issubset` no detecta un valor del `CHECK` que falte en el enum (`F104`) | Ticket de pruebas o TKT-018 |
| `tests/test_tkt011_migracion_linea_base.py:350` | Copia local de `esperar_hasta` (`O-N4`) | Cuando se toque ese archivo |
| `aplicacion/materializacion.py` (`_rechazo_vigente`) | Las ramas de «no encontrado» no tienen test (`O-N3`) y falta registrar con `structlog` la causa de una preparación ilegible (`O-N2`) | TKT-017b1 |
| `repositorio_linea_base.py:333` | `delete(linea_base)` sin filtro de estado `BORRADOR` (`F006` de arquitectura), con la comprobación `rowcount == 1` | TKT-017b1 |
| `docs/04-historias-usuario.md` | Líneas 39, 484 y 2121 citan `RN-18` como versionado por trabajo extra (`O006`) | Revisión del PRD y las historias |
| CRLF | Los archivos de la entrega tienen CRLF aunque `.gitattributes` declara `eol=lf` (`O003`); ya ocurría en `HEAD` | Normalización aparte |

#### Señal para quien aprueba el pull request

Esta entrega modifica `docs/api/openapi.yaml` (`requestBody` obligatorio de `confirmar_importacion`, el esquema `ConfirmacionImportacion` con `asignacion_tipos_partida` y la descripción del `409`) y, durante la revisión, `sdd/tickets/tkt-017/spec.md` (cabecera de `CA-A4`, `CA-B6` esc. 1 y las citas de `F1.6`) para alinearlo con la decisión `D11`. Los documentos afectados constan en el diff. También cambió `docs/08-wireframes.md` (esc. 12: la importación sigue en `VALIDADO`).

#### Verificación final (entrega TKT-017a3)

Salida real de los comandos, desde `backend/` salvo los de documentación, sobre el estado final tras dos ciclos de corrección. `docker info`: Docker 29.9.3 con el servidor en marcha.

```text
uv run ruff format --check .      → 254 files already formatted
uv run ruff check .               → All checks passed!
uv run mypy .                     → Success: no issues found in 254 source files
uv run lint-imports               → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → verificar_float: archivos revisados: 31; hallazgos: 0
uv run pytest -q -ra --tb=short   → 2297 passed, 26 skipped in 354.99s (0:05:54)
python tools/verificar_docs.py    → ✓ Sin problemas.
python tools/verificar_escenarios.py → Escenarios: 164 · exigidos 0 · cubiertos 0 · faltan 0 · pendientes 164 · retirados 0
python -m unittest discover -s tools/tests → OK (510 tests)
```

Mutantes del ciclo 1, uno a uno, con copia previa y huella SHA-256 idéntica (212 archivos `.py`) tras cada reversión: `M-F002` (cinco casos en rojo), `M-F003` (`1 failed` en tres de tres corridas), `M-F001` (dos tests, por aserción real con un código válido del catálogo), `M-F101` (dos de tres casos) y `M-F102` (cuatro casos).

Los 26 omitidos son las pruebas contra el archivo real del catálogo. `verificar_escenarios.py` no exige ningún test de HDU-001 mientras `tools/historias_activas.txt` la deje `PENDIENTE`: su verde no prueba la cobertura por nombre de los escenarios de este ticket.

##### Resultado por criterio (alcance a3)

Todos los criterios `[M]` de a3 (`CA-A1` a `CA-A10`, `CA-A12` y `CA-R1`) quedan cumplidos con la evidencia de «Resultado contra criterios de aceptación (alcance a3)» y los tests nuevos de este ciclo. `CA-A11` se cumplió en a1. `CA-B1` y `CA-B6` quedan parciales: solo el traductor, y el congelado es de TKT-017b1. El CI completo de GitHub Actions del pull request único se verifica en `/sdd-completar`, no en este comando.

##### Veredicto

**LISTO PARA EJECUTAR · TKT-017b1.** La entrega TKT-017a3 queda revisada y acumulada en la rama `tkt-017a3-materializacion`, sin pull request.

## TKT-017b1 · Congelado de la línea base (`/sdd-ejecutar` y `/sdd-revisar` 2026-11-09)

> [← index](_index.md) | [← design](design.md) | Siguiente: `/sdd-ejecutar` sobre TKT-017b2. `/sdd-completar` no corre al cerrar esta entrega: según la regla de un solo PR por ticket, corre una vez, al aprobarse la última entrega (TKT-017c).

Entrega **TKT-017b1** (filas **B0**, **B1**, **B2**, **B3**, **B3d** y **B3c**): el congelado de la línea base de extremo a extremo, desde las copias y la explosión hasta la ruta `POST /api/v1/lineas-base/{linea_base_id}/congelacion`. Se ejecutó en la rama `tkt-017a3-materializacion`, con tester y desarrollador separados en cada fila. La entrega pasó por un ciclo de corrección de `auditor-seguridad`, `auditor-sql`, `auditor-codigo` y `auditor-docs` (ver «Revisión»).

### Qué se implementó

- **`identidad` (B1):** `nombres_de_usuarios(sesion_bd, ids)` (repositorio `nombres_por_id`, caso `aplicacion/usuarios.py`) y `UsuarioResumen {id, nombre}` en `api/esquemas.py`, publicados en `interfaz.py` (nueve nombres en `__all__`). Ninguno de los dos existía.
- **`dominio/congelado.py`:** `evaluar_congelado(estado_linea_base, otra_congelada, estado_obra)` con el orden del diseño (estado de la línea base, otra congelada, estado de la obra), `CongeladoAdmitido` y `CongeladoRechazado(causa, datos)`. Solo biblioteca estándar y `dominio`.
- **`infraestructura/tablas.py` y `repositorio_linea_base.py` (B2 y B3):** tablas Core `linea_base_concepto`, `explosion_presupuesto` y `presupuesto_control`; columnas nuevas en `linea_base` y `obra`; `leer_linea_base`, `leer_linea_base_completa`, `bloquear_linea_base` (`FOR UPDATE`), `filas_explotables`, `copiar_conceptos` (`INSERT … SELECT gen_random_uuid()`), `insertar_explosion`, `insertar_controles`, `congelar`, `activar_obra` e `importes_venta_por_tipo`.
- **`aplicacion/congelado.py`:** `congelar_linea_base(contexto, *, linea_base_id, motivo, usuario_id) -> UUID`, con una sola transacción, el bloqueo obra → línea base, las comprobaciones del dominio, la explosión desde las filas materializadas, la escritura en el orden del diseño y el asiento `CONGELAR` con `RN-01`, y el traductor del motor. `aplicacion/causas_explosion.py` comparte con la confirmación el detalle de las causas. `aplicacion/consulta_linea_base.py` trae `obtener_linea_base`, mínimo, para la respuesta del congelado; B4 lo reutiliza.
- **`api/` (B3):** `Motivo` (con `strip`, de 1 a 2000 caracteres y sin `NUL`), `LineaBase` (con los enums `EstadoLineaBase` y `ClaveTipoPartida`), `rutas_linea_base.py` con la ruta de congelación (`verificar_origen` antes que `exigir_rol("DIRECTOR_PROYECTOS")`) y `montaje.py`. `servidor/fabrica.py` monta `presupuesto` con `montar_presupuesto`, perezoso, y su docstring lo dice.
- **Cliente:** `frontend/src/api/generado/servidor.ts` regenerado con `npm run tipos:generar`; `npm run tipos:verificar` en verde.
- **Soporte de pruebas:** `herramientas/soporte_tkt017_entorno.py` recibe `Base`, `Entorno` y `materializar` (movidos de `test_tkt017_materializacion.py` sin cambiar ninguna aserción) y `congelar()`.

### Decisiones de la persona dueña durante la ejecución (2026-11-09)

| # | Decisión |
|---|---|
| `D15` | El caso de uso `congelar_linea_base` no valida por sí mismo el motivo en blanco: lo rechazan el DTO en la ruta (`422`) y `asentar` (`OBLIGATORIO`, con rollback) en el caso de uso. Un test lo ancla y `M-B16` lo mata |
| `D16` | `R-2` (rojo por nombre ausente) se extiende a las filas B1, B2 y B3 de b1 |

### Riesgo declarado

| # | Riesgo | Por qué se acepta | Quién y cuándo |
|---|---|---|---|
| `R-2` (extendido a b1) | **Desviación del rojo.** Los tests de B1 (7), B2 (38) y B3 (36) nacieron en rojo por el nombre ausente (el módulo `cimenta.presupuesto.aplicacion.congelado`, las funciones del repositorio, la ruta o `nombres_de_usuarios`), importando dentro del cuerpo del test | Un nombre que no existe no admite otro fallo sin escribir producción. El tester validó las expectativas de B2 contra una implementación de referencia fuera del repositorio (38 de 38 en verde, 3 de 3 corridas de concurrencia) y los mutantes `M-B1` a `M-B12` la protegen | Orquestador, 2026-11-09; confirmado por la persona dueña, 2026-11-09 |
| `R-3` (extendido a b1) | Los tests nacidos en verde (`T4` del motivo en blanco, `T5` del `23505`, `T6` de dominio puro, y partes de `TC-B17`) | Los protegen mutantes (`M-B13a` a `M-B13c`, `M-B16`) y, para `T6`, tres mutantes en memoria del auditor | Persona dueña, 2026-11-09 (criterio de `R-3` de a3) |

### Ajustes respecto al design

Reflejados en `design.md` en este mismo cambio (sección «Ajustes de la ejecución de TKT-017b1», las filas B0 a B3c y `TC-B20`).

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-09 | `E-1` y `E-9`: la cabeza real era `0011` y el escape de `icontains` es `/` | Resultado de B0 |
| 2026-11-09 | `nombres_de_usuarios` y `UsuarioResumen` se escriben en b1 | No existían ni en `identidad` ni en TKT-059 |
| 2026-11-09 | `evaluar_congelado` vive en dominio | Mismo criterio que `F002` de a3 |
| 2026-11-09 | `obtener_linea_base` e `importes_venta_por_tipo` llegan en B3 | La respuesta del congelado exige la forma completa de `LineaBase` |
| 2026-11-09 | Esquema `LineaBase` publicado igual al borrador (enums, opcionales, `format: decimal`) y `TC-B20` | Regla: el borrador es el contrato |
| 2026-11-09 | `Motivo` rechaza `NUL` | Hallazgo `F001` de seguridad y de código |
| 2026-11-09 | `filas_explotables` desempata por `partida.id` y deduplica los `apu_id` | Hallazgos `F001` y `F003` de SQL |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/identidad/{api/esquemas.py, infraestructura/repositorio.py, interfaz.py}`, `backend/cimenta/identidad/aplicacion/usuarios.py` | modificados y nuevo | identidad (por su interfaz) |
| `backend/cimenta/presupuesto/dominio/congelado.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/aplicacion/{congelado,causas_explosion,consulta_linea_base}.py` | nuevos | aplicación |
| `backend/cimenta/presupuesto/aplicacion/materializacion.py` | modificado (usa `detalle_de_causas`) | aplicación |
| `backend/cimenta/presupuesto/api/{esquemas,rutas_linea_base,montaje}.py` | nuevos | api |
| `backend/cimenta/presupuesto/infraestructura/{tablas,repositorio_linea_base}.py` | modificados | infraestructura |
| `backend/servidor/fabrica.py` | modificado (`montar_presupuesto` y su docstring) | composición |
| `backend/herramientas/soporte_tkt017_entorno.py` | nuevo | herramientas |
| `backend/tests/test_tkt017_{congelado,congelado_concurrencia,dominio_congelado,api_congelado,identidad_nombres}.py` | nuevos | pruebas |
| `backend/tests/{test_tkt006_enrutador,test_tkt057_csrf,test_tkt017_materializacion}.py` | modificados (`__all__` de identidad, una entrada de `CUERPOS_VALIDOS`, soporte extraído) | pruebas |
| `frontend/src/api/generado/servidor.ts` | regenerado | cliente |
| `docs/api/openapi.yaml`, `docs/03-modelo-datos.md`, `docs/04-historias-usuario.md`, `docs/05-tickets-trabajo.md` | modificados | documentación |
| `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | modificado | documentación |
| `sdd/tickets/tkt-017/{design,spec,impl,_index}.md` | modificados | SDD |

### Pruebas

| # | Tests | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-B18 | `test_tkt017_nombres_de_usuarios` y cinco más (`test_tkt017_identidad_nombres.py`) | feliz y borde | `CA-B1` | FALLA (7 con el de `__all__`) | PASA |
| TC-B02, TC-B07, TC-B12, TC-B15 y camino feliz | `test_tkt017_congelado.py` (37 al cerrar) | feliz y **rechazo** | `CA-B1`, `CA-B3`, `CA-B5`, `CA-B7` | FALLA (33 de 33) | PASA |
| TC-B08, TC-B09, TC-B10 | `test_tkt017_congelado_concurrencia.py` (5) | concurrencia y **rechazo** | `CA-B6` | FALLA (5 de 5) | PASA, tres corridas seguidas |
| TC-B01, TC-B03, TC-B04, TC-B05, TC-B06, TC-B11, TC-B17, TC-B19 | `test_tkt017_api_congelado.py` (40 al cerrar) | feliz y **rechazo** | `CA-B1` a `CA-B4`, `CA-B6`, `CA-R1` | FALLA (36 de 36) | PASA |
| TC-B20 | dos tests `cab08_*` de forma publicada | regresión | `CA-B8`, `CA-R1` | FALLA (2 de 2) | PASA |
| `F001` de revisión | `test_tkt017_cab04_congelar_motivo_con_nul` (2 casos) | **rechazo** | `CA-B4` | FALLA (2 de 2, `500`) | PASA |
| SQL `F001` y `F003` | `…filas_explotables_desempata_las_apariciones_por_partida_id` y `…no_repite_el_apu_en_los_in` | regresión | `CA-B1` | FALLA (2 de 2) | PASA |
| `T4`, `T5`, `T6` | `…congelar_sin_motivo_en_el_caso_de_uso`, `…esc19_el_indice_de_congelada_vigente_responde_rn01`, `test_tkt017_dominio_congelado.py` (12) | **rechazo** | `CA-B2`, `CA-B3`, `CA-B4` | Nacen en verde | PASA (ver `R-3`) |

### Ciclo TDD por fila

Salida del rojo, recortada a su resumen literal:

**Fila B0 · apertura y experimentos** (sin código): `ruff check`, `mypy`, `lint-imports` (16 contratos), `verificar_float` y `alembic heads` (`0011 (head)`) en verde. `E-5` cumple: el `INSERT … SELECT` en `linea_base_concepto` pasa el `FOR SHARE` del disparador en 2.0 ms con `lock_timeout` de 200 ms; una segunda sesión sobre la misma línea base falla con `55P03` a los 203 ms. `E-8` cumple: `"   "` da `string_too_short` con `ctx.min_length == 1`, que el manejador traduce a `OBLIGATORIO`. `E-9` cumple: `icontains(autoescape=True)` escapa `%` y `_`, con `/` como carácter de escape.

**Fila B1 · rojo** (`uv run pytest tests/test_tkt017_identidad_nombres.py tests/test_tkt006_enrutador.py -q`): `7 failed, 28 passed`; seis con `ImportError: cannot import name 'nombres_de_usuarios'` o `'UsuarioResumen'` de `cimenta.identidad.interfaz` y uno por la lista cerrada de `__all__`. **Verde:** `35 passed in 4.48s` (6 del archivo nuevo y 29 del enrutador).

**Fila B2 · rojo** (`uv run pytest tests/test_tkt017_congelado.py tests/test_tkt017_congelado_concurrencia.py -q -ra --tb=no`): `38 failed in 26.16s`, 32 por `ModuleNotFoundError` de `cimenta.presupuesto.aplicacion.congelado` y 6 por `AttributeError` del `monkeypatch` sobre funciones del repositorio ausentes. **Verde:** `test_tkt017_congelado.py` `33 passed` y el de concurrencia `5 passed` en tres corridas seguidas (`5.68 s`, `5.56 s`, `5.57 s`); `test_tkt011_linea_base.py`, `test_tkt017_materializacion.py` y su concurrencia, `224 passed`.

**Fila B3 · rojo** (`uv run pytest tests/test_tkt017_api_congelado.py -q -ra`): `36 failed in 21.76s`: 30 porque la ruta no existe (`404`), uno por contenido del `404`, dos del recorrido, uno del OpenAPI publicado, `TC-B19` y el docstring de `fabrica.py`. **Verde:** `36 passed in 15.67s`; `test_tkt006_enrutador.py` y `test_tkt057_csrf.py`, `102 passed`. Contrato publicado: `2 failed, 36 passed` (diferencias de enum, `required` y `format: decimal`), después `38 passed`.

**Fila B3d · documentación:** `python tools/verificar_docs.py` → «✓ Sin problemas.».

**Ciclo de corrección de `/sdd-revisar`:** rojo `4 failed` (`T1` dos casos con `assert 500 == 422`, `T2` y `T3` por el `ORDER BY` y el `IN` de `filas_explotables`); verde `40 passed` (API), `37 passed` (congelado), `12 passed` (dominio puro) y `5 passed` en tres corridas de concurrencia.

### Mutantes

La fila B3c los ejecutó uno a uno, con copia previa fuera del repositorio y huella SHA-256 idéntica (239 archivos `.py`) tras cada reversión.

| Mutante | Cambio | Tests que cayeron |
|---|---|---|
| `M-B1` | Sustituir `bloquear_obra` por una lectura sin bloqueo en `congelar_linea_base` | `cab06_congelado_gana_al_reemplazo`, `cab06_reemplazo_gana_al_congelado` y `cab06_congelado_espera_el_bloqueo_de_la_obra_y_continua` (`3 failed, 2 passed`, a la primera) |
| `M-B2` | Rendimiento ponderado por el del primer concepto | `esc14_la_explosion_congelada_es_la_validada[alta_compartida_en_muros]` (`0.500000` frente a `0.673400`) |
| `M-B3` | No pasar la obra a `ACTIVA` | `esc14_congelar_pasa_la_obra_a_activa`, `cab07_…[activar_obra]` y el de la API (`3 failed`) |
| `M-B4` | Asentar `CONGELAR` sin `RN-01` | Dos tests, caso de uso y API |
| `M-B5` | `insertar_controles` solo para los tipos con conceptos | Siete tests |
| `M-B6` | Comprobar la otra congelada después del estado de la obra | `esc19_segunda_linea_base_vigente` (API y caso de uso) |
| `M-B7` | Quitar el `try/except DBAPIError` | `cab06_congelado_con_bloqueo_vencido` (API y caso de uso) |
| `M-B8` | `importes_venta_por_tipo` suma `partida_concepto` también si está `CONGELADA` | `esc14_el_importe_por_tipo_de_una_congelada_es_la_suma_de_las_copias` |
| `M-B9` | Quitar `verificar_origen` de la ruta | Siete tests de CSRF y de orden |
| `M-B10` | Exigir `COMPRAS` en lugar de `DIRECTOR_PROYECTOS` | `23 failed` |
| `M-B11b` | `nombres_de_usuarios` no ignora los ids ajenos | `2 failed` |
| `M-B11a` | Quitar `list(set(ids))` | **Sobrevive**: mutante equivalente, la consulta usa `IN` y el resultado es un diccionario |
| `M-B12` | Cuantizar antes de multiplicar en la explosión | `esc14_la_explosion_congelada_es_la_validada[alta_compartida_en_muros]` y `cab01_explotar_filas_devuelve_valores_en_la_escala_de_su_columna` |
| `M-B13a` a `M-B13c` | `RN-03` en lugar de `RN-01`; `version` en lugar de `version_vigente`; `ConflictoEstado` en la rama del `23505` | Los tres de `esc19` (`3 failed`, `3 failed`, y solo `T5`: `1 failed`) |
| `M-B16` | Quitar la validación del texto en blanco de `asentar` | `T4` (`1 failed`) y cuatro tests de `test_tkt007_dominio.py` |

Además, `auditor-codigo` mutó `evaluar_congelado` en memoria (tres mutantes, los tres con test en rojo).

### Modelo por paso

| Paso | Agente | Modelo |
|---|---|---|
| B0 | `tester-backend` | `haiku` |
| B1 (rojo y verde) | `tester-backend` y `desarrollador-aplicacion` | `sonnet` y `haiku` |
| B2 (rojo y verde) | `tester-backend` y `desarrollador-aplicacion` | `sonnet` (disparadores: inmutabilidad y bloqueo pesimista) |
| B3 (rojo, verde y contrato publicado) | `tester-api` y `desarrollador-api` | `sonnet` (disparador: permisos de un rol) |
| B3c y mutantes del ciclo | `tester-backend` | `sonnet` |
| Correcciones | `tester-api`, `corrector-revision` | `sonnet` |
| Auditorías | `auditor-arquitectura`, `-sql`, `-codigo`, `-seguridad` | `sonnet`; `auditor-docs` en `haiku`; reauditorías de `-sql`, `-codigo` y `-docs` en `haiku` |

### Resultado contra criterios de aceptación (alcance b1)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-B1` | `[M]` | Cumplido | `TC-B01`, `TC-B02` y `TC-B18` |
| `CA-B2`, `CA-B3` | `[M]` | Cumplido | `TC-B03`, `TC-B04` y `T5` con el contrato de error completo y la base sin cambios |
| `CA-B4` | `[M]` | Cumplido | `TC-B05` y `TC-B06` (cinco roles, `DENEGAR`), sin sesión, sin par CSRF y `NUL` |
| `CA-B5` | `[M]` | Cumplido | `TC-B07`: `IN001` y `42501` sobre las copias, con el rol de aplicación |
| `CA-B6` | `[M]` | Cumplido | `TC-B08` a `TC-B11` y el traductor de a3 |
| `CA-B7` | `[M]` | Cumplido | `TC-B12`: el fallo a mitad del congelado no deja nada |
| `CA-B8` | `[M]` | **Parcial** | Solo la forma de `LineaBase` publicada (`TC-B20`); las cuatro lecturas son de TKT-017b2 |
| `CA-B9` | `[M]` | **Parcial** | `TC-B16` completo en b2 |
| `CA-R1` | `[M]` | Cumplido | `TC-B17`, `TC-B19` y `lint-imports` con 16 contratos |

### Auditorías

`auditor-arquitectura` **APROBADO** en la primera pasada (cinco observaciones). `auditor-sql`, `auditor-codigo`, `auditor-seguridad` y `auditor-docs` devolvieron **REQUIERE CAMBIOS** y, tras un ciclo de corrección, **APROBADO** los cuatro.

| Auditor | Primera pasada | Ciclo 1 |
|---|---|---|
| `auditor-arquitectura` | **APROBADO** (`F001` a `F005` observaciones) | — |
| `auditor-sql` | **REQUIERE CAMBIOS** (`F001` Menor, tres observaciones) | **APROBADO** (`F001` y `F003` resueltos; observación nueva `N001`) |
| `auditor-codigo` | **REQUIERE CAMBIOS** (`F001` Mayor, seis Menores) | **APROBADO** (`F001` a `F004`, `F006` y `F007` resueltos; `F005` diferido) |
| `auditor-seguridad` | **REQUIERE CAMBIOS** (`F001` Media) | **APROBADO** |
| `auditor-docs` | **REQUIERE CAMBIOS** (cuatro Mayores, un Menor) | **APROBADO** (cuatro observaciones) |

#### Hallazgos y su resolución

| Auditor y ID | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| Seguridad `F001` y código `F001` | Media y Mayor | `{"motivo":"\u0000"}` pasa el DTO y psycopg lanza `DataError` sin `sqlstate`: `500` sin `tipo` | `AfterValidator(_sin_nul)` en `MotivoTexto` (`422` `FORMATO`); test `cab04_congelar_motivo_con_nul` y mutante |
| SQL `F001` | Menor | El `ORDER BY` de `filas_explotables` no era determinista (`partida` sin `UNIQUE (area_id, orden)`) | `partida.id` entre `partida.orden` y `concepto.codigo`; test que captura la sentencia |
| SQL `F003` | Observación | `apu_id` repetidos en el `IN` | Deduplicados con un conjunto; test |
| Código `F002` | Menor | El caso `motivo="   "` en el caso de uso lo rechaza `asentar` sin test | `T4` y decisión `D15` |
| Código `F003` | Menor | Guarda `and vigente is not None` solo para mypy | El rechazo se construye desde `resultado.datos` |
| Código `F004` | Menor | `_rechazo_vigente` (`23505` → `RN-01`) sin test | `T5`, con espía sobre el traductor; `M-B13c` |
| Código `F006`, `F007` y arquitectura `F001` | Menores | Docstrings obsoletos, aserciones redundantes y falta de un test puro de dominio | Limpieza de tests y docstrings; `test_tkt017_dominio_congelado.py` (12 casos) |
| Docs `F001` a `F004` | Mayores | §4.2 sin el control ni la obra `ACTIVA`; fórmula de `importe_venta`; ADR de inmutabilidad (`23505` en el congelado y sustitución de la `CONGELADA`) | Texto literal del auditor |
| Docs `F005` | Menor | Descripción del `409` de `congelar_linea_base` incompleta | Texto literal del auditor |
| Código `F005` | Menor | Duplicación de constantes, alias y dos `SELECT` casi idénticos | **Diferido** a TKT-017b2, que reutiliza `consulta_linea_base.py` |

### Hallazgos fuera de alcance y deuda

| Dónde | Observación | Hacia |
|---|---|---|
| `aplicacion/materializacion.py` (`motivo_reemplazo`) | Misma exposición al `NUL` que `F001`, con una ruta que construye TKT-018 (severidad Media) | TKT-018: reutilizar `MotivoTexto` o equivalente, con un test igual |
| Migración posterior | Índice `ix_linea_base_concepto_partida_concepto_id` y `UNIQUE (concepto_id)` en `apu` (el `LEFT JOIN` de `filas_explotables` duplicaría apariciones con dos análisis por concepto) | Migración de TKT-017c o de un ticket de esquema |
| `repositorio_linea_base.py` (`filas_explotables` e `importes_venta_por_tipo`) | Filtran solo por `concepto.obra_id`, y la copia no guarda `tipo_partida_id` (`N001` y `F004` de SQL) | Defensa en profundidad en TKT-017b2 o la migración posterior |
| `consulta_linea_base.py` | `obtener_linea_base` lee la fila y `importes_venta_por_tipo` la vuelve a leer sin bloqueo (`F003` de arquitectura) | TKT-017b2: pasar `estado` y `obra_id` ya leídos |
| `traduccion_motor.py` | `detalle` con `tabla` y `restriccion` (`O1` de seguridad); la defensa en profundidad del manejador global ante un `DataError` sin `sqlstate` | Cuando se endurezca |
| `repositorio_linea_base.py` (`congelar` y `activar_obra`) | Los `UPDATE` no llevan guardia de estado ni comprueban `rowcount` (defensa en profundidad) | TKT-017b2 |
| `herramientas/soporte_tkt017_entorno.py` | Primer soporte de `herramientas/` con `import pytest` a nivel de módulo; no entrará en una imagen con `uv sync --no-dev` | Ticket de despliegue |
| `identidad/api/montaje.py` | Su docstring dice «lo único de `api/` que importa `servidor/`» al revés; es de TKT-006 | Cuando se toque ese archivo |
| `insertar_controles` | Sin guarda de lista vacía; hoy `tipo_partida` está sembrada en `0008` | Cuando cambie el catálogo |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/api/openapi.yaml` | `409` de `congelar_linea_base`: `ErrorConflicto` y una descripción de todos los casos (**señalar a quien apruebe el PR**) |
| `docs/03-modelo-datos.md` §4.2 | `importe_venta` de la explosión y lo que crea el congelado |
| `docs/04-historias-usuario.md` | HDU-001 esc. 18: el intento no se asienta (`PA-T17.4`) |
| `docs/05-tickets-trabajo.md` | Ficha de TKT-012: hereda `PLANEACION` → `ACTIVA` (`PA-T17.8`) |
| `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | `23505` de la vigente en el congelado y la sustitución de la `CONGELADA` como versionado de `F1.6` |
| `sdd/tickets/tkt-017/{design,spec,_index}.md` | Filas B0 a B3c hechas, `TC-B20`, ajustes de b1 y `PA-T17.4` |

### Verificación final (entrega TKT-017b1)

Salida real de los comandos, desde `backend/` salvo los de documentación, sobre el estado final tras un ciclo de corrección. `docker info`: Docker 29.9.3 con el servidor en marcha.

```text
uv run ruff format --check .      → 268 files already formatted
uv run ruff check .               → All checks passed!
uv run mypy .                     → Success: no issues found in 268 source files
uv run lint-imports               → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → verificar_float: archivos revisados: 32; hallazgos: 0
uv run pytest -q -ra --tb=short   → 2397 passed, 26 skipped in 440.92s (0:07:20)
npm run tipos:verificar (frontend) → Tipos al día.
python tools/verificar_docs.py    → ✓ Sin problemas.
python tools/verificar_escenarios.py → Escenarios: 164 · exigidos 0 · cubiertos 0 · faltan 0 · pendientes 164 · retirados 0
python -m unittest discover -s tools/tests → OK (510 tests)
```

Los 26 omitidos son las pruebas contra el archivo real del catálogo. `verificar_escenarios.py` no exige ningún test de HDU-001 mientras `tools/historias_activas.txt` la deje `PENDIENTE`: su verde no prueba la cobertura por nombre de los escenarios de este ticket; la prueba la tabla de «Pruebas» y la activación es `P-13` en la fila C4. Una primera suite de cierre dio `993 errors` porque el motor de Docker Desktop se había detenido con un reinicio; se repitió con Docker en marcha y es la de arriba. El CI completo de GitHub Actions se verifica en `/sdd-completar`, al abrir el PR único.

##### Resultado por criterio (alcance b1)

Todos los criterios `[M]` de b1 (`CA-B1` a `CA-B7` y `CA-R1`) quedan cumplidos con la evidencia de «Resultado contra criterios de aceptación (alcance b1)». `CA-B8` y `CA-B9` quedan parciales y se completan en TKT-017b2.

##### Veredicto

**LISTO PARA EJECUTAR · TKT-017b2.** La entrega TKT-017b1 queda revisada y acumulada en la rama `tkt-017a3-materializacion`, sin pull request.

## TKT-017b2 · Lecturas de la línea base (`/sdd-ejecutar` y `/sdd-revisar` 2026-11-10)

> [← index](_index.md) | [← design](design.md) | Siguiente: `/sdd-ejecutar` sobre TKT-017c. `/sdd-completar` no corre al cerrar esta entrega: según la regla de un solo PR por ticket, corre una vez, al aprobarse la última entrega (TKT-017c).

Entrega **TKT-017b2** (filas **B4**, **B5** y **B6**): las cuatro lecturas de la línea base (`listar_lineas_base`, `obtener_linea_base`, `listar_conceptos_linea_base` y `obtener_explosion_insumos`), con sus filtros y su paginación, y la corrección del borrador de `PA-16.7`. Se ejecutó en la rama `tkt-017a3-materializacion`, con tester y desarrollador separados. La entrega pasó por un ciclo de corrección de los cinco auditores (ver «Revisión»).

### Qué se implementó

- **`infraestructura/repositorio_linea_base.py`:** `lineas_base_completas_de_obra` (versión descendente y, a igual versión, `id`), `conceptos_de_linea_base` (filtros por tipo de partida, por nivel con igualdad exacta y por texto con `icontains(autoescape=True)`; paginación con `total`; orden `nivel.orden`, `area.nombre`, `partida.orden`, `concepto.codigo`, `linea_base_concepto.id`; página vacía cuando el desplazamiento no alcanza filas), `renglones_de_explosion` (orden por tipo de partida y código de insumo; `importe_costo` es la columna `explosion_presupuesto.importe_venta`) y `importes_venta_de`, que calcula los importes por tipo sobre la fila ya leída. `importes_venta_por_tipo` lee la fila y delega. Hay un solo `SELECT` de línea base.
- **`aplicacion/consulta_linea_base.py`:** `listar_lineas_base`, `obtener_linea_base`, `listar_conceptos` y `obtener_explosion`, una transacción de lectura por llamada, sin bloqueo. Entregan tipos propios de la capa (`TipoPartidaConsultado`, `ConceptoConsultado`, `InsumoConsultado`, `RenglonConsultado`). `MENSAJE_LINEA_BASE_NO_EXISTE` es único.
- **`api/esquemas.py` y `api/rutas_linea_base.py`:** los esquemas `ListaConceptosLineaBase`, `ConceptoLineaBase`, `MetaPagina`, `InsumoResumen`, `ExplosionInsumos` y `RenglonExplosion` (con `importe_costo`) y las cuatro rutas `GET`, con `exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "COMPRAS")` en el orden de `x-roles`, sin `verificar_origen`, `pagina` mínima 1, `tamano_pagina` de 1 a 200 y `q` y `nivel` sin el carácter `NUL`. `api/` ya no importa nada de `infraestructura/`.
- **Cliente:** `frontend/src/api/generado/servidor.ts` regenerado; `npm run tipos:verificar`, `typecheck` y `lint` en verde.
- **Soporte de pruebas:** `herramientas/soporte_tkt017_api.py` reúne los ayudantes, las fixtures y las constantes de las pruebas de la API; `test_tkt017_api_congelado.py` y `test_tkt017_api_lecturas.py` los importan.
- **Borrador (B5):** `RenglonExplosion.importe_venta` pasó a `importe_costo`; `obtener_explosion_insumos` quedó en `x-tickets: [TKT-017]`; las dos lecturas con filtros declaran el `422` y el patrón sin `NUL`; las tres lecturas describen su comportamiento en `BORRADOR`. `PA-16.7` de TKT-016 consta como resuelta.

### Decisiones de la persona dueña durante la ejecución (2026-11-10)

| # | Decisión |
|---|---|
| `D17` | `x-tickets` de `obtener_explosion_insumos` queda en `[TKT-017]`, como pedían `CA-B9` y la decisión del 2026-11-03 |
| `D18` | El filtro `nivel` es igualdad exacta sensible a mayúsculas; `nivel=""` da cero conceptos y `q=""` da todos |
| `D19` | Se unifican en este ciclo los ayudantes de las pruebas de la API (hallazgo `F003` de código) |
| `D20` | Una `pagina` cuyo desplazamiento no alcanza filas responde `200` con la página vacía y el `total`, sin tope y sin tocar el borrador; el tope general lo decide TKT-027 |
| `D21` | `R-2` (rojo por ruta o nombre ausente) se extiende a la fila B4 de b2 |

### Riesgo declarado

| # | Riesgo | Por qué se acepta | Quién y cuándo |
|---|---|---|---|
| `R-2` (extendido a b2) | **Desviación del rojo.** Los 90 tests de B4 nacieron en rojo (88 fallos, dos regresiones del borrador en verde) porque las cuatro rutas `GET` no existían: el enrutador respondía `404` | Una ruta que no existe no admite otro fallo sin escribir producción. Los tests cayeron por la razón esperada y los protegen los mutantes `M-B8` y `M-B14` a `M-B24` | Orquestador, 2026-11-10; confirmado por la persona dueña, 2026-11-10 |
| `R-3` (extendido a b2) | Los tests nacidos en verde (`T4`, `T6`, `T7`, el test del `NUL` en `q` y `nivel`, el del orden de la explosión) | Los protegen mutantes (`M-B16`, `M-B19`, `M-B21a` a `M-B22`) | Persona dueña, 2026-11-09 (criterio de `R-3` de a3) |
| Publicado frente al borrador | La aplicación publica el `422` como `HTTPValidationError` de FastAPI y no publica `401`, `403` ni `404` | Es sistémico (también pasa en `congelar_linea_base`) y TKT-005 lo dejó diferido a TKT-061 | Auditoría de arquitectura y de pruebas; sin cambio |

### Ajustes respecto al design

Reflejados en `design.md` en este mismo cambio (sección «Ajustes de la ejecución de TKT-017b2» y las filas B4 a B6).

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-10 | `RenglonExplosion.importe_costo` con descripción exacta; `422` y patrón sin `NUL` en el borrador; descripciones de `BORRADOR` | Hallazgos de documentación y de arquitectura |
| 2026-11-10 | `x-tickets` a `[TKT-017]` | `D17` |
| 2026-11-10 | Página vacía para un desplazamiento inalcanzable | Hallazgos de seguridad, SQL y código; `D20` |
| 2026-11-10 | Orden total de las líneas base (`version` e `id`) y de los renglones de la explosión | Hallazgos de SQL y mutante `M-B19` |
| 2026-11-10 | Tipos propios de `aplicacion` para `api/` | Hallazgos de arquitectura y de código |
| 2026-11-10 | `per-file-ignores` de `F811` para `tests/test_tkt017_api_*.py` en `backend/pyproject.toml` | Las fixtures importadas y pedidas por parámetro disparan `F811`; alternativa descartada: enlazarlas con una asignación |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/infraestructura/repositorio_linea_base.py` | modificado | infraestructura |
| `backend/cimenta/presupuesto/aplicacion/{consulta_linea_base,congelado}.py` | modificados | aplicación |
| `backend/cimenta/presupuesto/api/{esquemas,rutas_linea_base}.py` | modificados | api |
| `backend/herramientas/soporte_tkt017_api.py` | nuevo | herramientas |
| `backend/tests/test_tkt017_api_lecturas.py` | nuevo | pruebas |
| `backend/tests/test_tkt017_api_congelado.py` | modificado (importa el soporte, `IMPLEMENTADAS_DE_PRESUPUESTO`) | pruebas |
| `backend/pyproject.toml` | modificado (`per-file-ignores` de `F811`) | configuración |
| `frontend/src/api/generado/servidor.ts` | regenerado | cliente |
| `docs/api/openapi.yaml`, `docs/07-especificacion-api.md`, `docs/glosario.md` | modificados | documentación |
| `sdd/tickets/tkt-016/spec.md`, `sdd/tickets/tkt-017/{design,impl,_index}.md` | modificados | SDD |

### Pruebas

| # | Tests | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-B13 | `test_hdu001_esc14_lecturas_de_la_linea_base` y los de filtros, paginación, comodines, explosión y `BORRADOR` | feliz | `CA-B8` esc. 1 | FALLA (ruta ausente) | PASA |
| TC-B14 | `test_tkt017_cab08_lecturas_sin_rol` y compañeros (rol antes que existencia, `404`, `401`, CSRF, `422`) | **rechazo** | `CA-B8` esc. 2 | FALLA (ruta ausente) | PASA |
| TC-B16 | Borrador con `importe_costo`, `x-tickets` exacto, enums y forma publicada igual a la del borrador | regresión | `CA-B9` | Dos nacen en verde; el resto FALLA | PASA |
| TC-B17, TC-B19 | Recorrido de rutas, OpenAPI publicado y `IMPLEMENTADAS_DE_PRESUPUESTO` con las cuatro lecturas | regresión | `CA-R1` | FALLA | PASA |
| Ciclo de revisión | Página enorme (5 casos), orden total de líneas base, códigos y patrón del borrador, `x-tickets` exacto | **rechazo** y regresión | `CA-B8`, `CA-B9` | FALLA (12 de 12) | PASA |
| Nacen en verde | `NUL` en `q` y `nivel` (4), orden de la explosión, `nivel` y `q` vacíos o con mayúsculas, `Unidad` frente al dominio | **rechazo** | `CA-B8` | Nacen en verde | PASA (ver `R-3`) |

### Ciclo TDD por fila

Salida del rojo, recortada a su resumen literal:

**Fila B4 · rojo** (`uv run pytest tests/test_tkt017_api_lecturas.py -q -ra --tb=line`): `88 failed, 2 passed in 55.60s`; unos 37 esperaban `200` y recibían el `404` del enrutador, unos 38 contratos de error recibían el mismo `404`, 13 fallaban sobre `/openapi.json` y el recorrido de rutas, y los dos que pasan son las regresiones del borrador (nacen en verde porque el orquestador renombró el campo antes del rojo). **Verde:** `90 passed in 43.85s`. Con el test del `NUL` en `q` y `nivel`, `94 passed`; con el del orden de la explosión, `95 passed`.

**Fila B5 · documentación:** `python tools/verificar_docs.py` → «✓ Sin problemas.».

**Ciclo de corrección de `/sdd-revisar`:** rojo `12 failed, 100 passed in 61.51s` (página enorme: 4 casos con `500`; orden total de líneas base; `x-tickets`; el `422` y el patrón del borrador); verde `112 passed`.

### Mutantes

La fila B6 y el cierre del ciclo los ejecutaron uno a uno, con copia previa fuera del repositorio y huella SHA-256 idéntica (242 archivos `.py`) tras cada reversión.

| Mutante | Cambio | Tests que cayeron |
|---|---|---|
| `M-B8` (variante b2) | `importes_venta_por_tipo` suma `partida_concepto` también si está `CONGELADA` | `2 failed` (lecturas y congelado) |
| `M-B14` | Quitar `autoescape=True` de los dos `icontains` | `4 failed`, los de `%` y `_` |
| `M-B15` | Añadir `RESIDENTE` a los roles de `listar_conceptos_linea_base` | `4 failed` |
| `M-B16` | Quitar el patrón sin `NUL` de `q` y, aparte, de `nivel` | `2 failed` cada uno |
| `M-B17` | `importe_total` suma todos los renglones y no los devueltos | `4 failed` |
| `M-B18` | `total` ignora los filtros | `17 failed` |
| `M-B19` | Invertir el `ORDER BY` de la explosión | **Sobrevivía**; se añadió `test_tkt017_cab08_la_explosion_sale_ordenada_por_tipo_y_codigo_de_insumo`, que cae con la inversión total y con la del código de insumo (`1 failed, 1 passed` cada una) |
| `M-B20` | Orden ascendente de las líneas base | `1 failed` |
| `M-B21a` y `M-B21b` | `ilike` y `startswith` en el filtro `nivel` | `1 failed` y `2 failed` |
| `M-B21c` | `nivel=""` sin filtro; `q=""` con cero resultados | `1 failed` cada uno |
| `M-B22` | Quitar `JORNAL` del enum `Unidad` | `8 failed` |
| `M-B23` | Quitar el guard de página vacía | `4 failed` |
| `M-B24` | Quitar `id` del `ORDER BY` de las líneas base | `1 failed` |

### Modelo por paso

| Paso | Agente | Modelo |
|---|---|---|
| B4 (rojo, NUL y orden de la explosión) | `tester-api` | `sonnet` (disparador: permisos de un rol) |
| B4 (verde) | `desarrollador-api` | `sonnet` (mismo disparador) |
| B5 | El orquestador | — |
| B6 y mutantes del ciclo | `tester-backend` y `tester-api` | `sonnet` |
| Correcciones | `tester-api`, `corrector-revision` | `sonnet` |
| Auditorías | `auditor-arquitectura`, `-sql`, `-codigo`, `-seguridad` y `-docs` | `sonnet`; `-docs` en `haiku`; reauditorías de `-sql` y `-docs` en `haiku` |

### Resultado contra criterios de aceptación (alcance b2)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-B8` | `[M]` | Cumplido | `TC-B13` y `TC-B14`: las cuatro lecturas con los tres roles, sus formas validadas contra el borrador, los filtros, la paginación y las cadenas con su escala; `403` sin importes, `404`, `401` y `422` |
| `CA-B9` | `[M]` | Cumplido | `TC-B16`: `x-tickets: [TKT-017]`, `importe_costo` en el borrador, el modelo de datos y el cliente generado |
| `CA-R1` | `[M]` | Cumplido | `TC-B17`, `TC-B19` y `lint-imports` con 16 contratos |
| `CA-B1` y `CA-B6` | `[M]` | Cumplido en b1 y a3 | Sin cambio |

### Auditorías

| Auditor | Primera pasada | Ciclo 1 |
|---|---|---|
| `auditor-arquitectura` | **REQUIERE CAMBIOS** (`F001` Mayor, dos Menores) | **APROBADO** |
| `auditor-sql` | **REQUIERE CAMBIOS** (dos Menores) | **APROBADO** (seis observaciones) |
| `auditor-codigo` | **REQUIERE CAMBIOS** (tres Mayores, cuatro Menores) | **REQUIERE CAMBIOS** (`F007` Menor); resuelto por el orquestador con el texto literal, sin reauditar: **APROBADO CON MENORES RESUELTOS SIN REAUDITAR** |
| `auditor-seguridad` | **REQUIERE CAMBIOS** (`F001` Media) | **APROBADO** |
| `auditor-docs` | **REQUIERE CAMBIOS** (tres Mayores) | **APROBADO** (observaciones `F004` y `F005` aplicadas) |

#### Hallazgos y su resolución

| Auditor y ID | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| Seguridad `F001`, código `F001` y SQL `F002` | Media y Mayor | `pagina` sin tope superior: un `OFFSET` que desborda `bigint` daba `500` | Página vacía con el `total` cuando el desplazamiento no alcanza filas; cinco casos de test (`D20`) y mutante `M-B23` |
| Arquitectura `F001` y docs `F001` | Mayor | `x-tickets` de `obtener_explosion_insumos` era `[TKT-016, TKT-017]` y `CA-B9` pide `[TKT-017]` | `D17`; el test exige igualdad exacta |
| Código `F002` | Mayor | Falso fallo de ~0,9 % por corrida: los tests de `403` buscaban cifras de cuatro dígitos en un texto con un UUID aleatorio | La correlación se quita del texto antes de buscar |
| Código `F003` | Mayor | El soporte de pruebas copiaba ayudantes y fixtures de `test_tkt017_api_congelado.py` | Unificados en `soporte_tkt017_api.py` (`D19`); mismos recuentos antes y después |
| Docs `F002` y `F003`, arquitectura `F002` | Mayor y Menor | El borrador no decía qué devuelven las lecturas en `BORRADOR` ni declaraba el `422` y el patrón sin `NUL` | Texto literal de los auditores en `openapi.yaml` |
| SQL `F001` | Menor | El orden de las líneas base no era total | `version DESC, id`; test que captura la sentencia |
| Arquitectura `F003` y código `F005` | Menor | `api/` importaba `infraestructura/` | `TipoPartidaConsultado` y compañía en `aplicacion/` |
| Código `F004`, `F006` y `F007` | Menores | `Any` suelto; faltaban tests de `nivel` y de vacíos; `importes_venta_por_tipo` con dos fuentes de verdad | `Row[*tuple[Any, ...]]`; tests y mutantes de `D18`; separada en dos funciones |
| SQL `N1` y `N2` | Observaciones | Dos docstrings de test inexactos (una restricción inexistente y una atribución errónea) | Corregidos |
| Docs `F004` y `F005` | Observaciones | Texto de `design.md` ambiguo y fórmula de la explosión sin el costo unitario | Corregidos en `design.md`, el borrador y `docs/glosario.md` |

### Hallazgos fuera de alcance y deuda

| Dónde | Observación | Hacia |
|---|---|---|
| `repositorio_linea_base.py` (`lineas_base_de_obra`) | Ordena solo por `version DESC`; lo usan el congelado y la confirmación (`N4` de SQL) | TKT-017c o la próxima pasada de a3 |
| `consulta_linea_base.py` (`listar_lineas_base`) | N+1 con pocas versiones por obra | Cuando crezcan las versiones |
| `repositorio_linea_base.py` (`conceptos_de_linea_base`) | Ordena por `concepto.codigo` vivo y no por la copia; la descripción y la unidad salen del concepto vivo | Cuando se permita editar la jerarquía |
| `api/esquemas.py` (`MetaPagina.pagina`) | Devuelve enteros enormes como JSON entero; un cliente JavaScript perdería precisión | TKT-027, con el tope de `pagina` |
| `rutas_linea_base.py` | `q` y `nivel` sin `max_length` (`F002` de seguridad, Baja) | Cuando se endurezca |
| `aplicacion/materializacion.py` | Repite el literal «La obra no existe.» en lugar de importar `MENSAJE_OBRA_NO_EXISTE` | Cuando se toque ese archivo |
| Copias de `rutas_de` y `llamadas` | `test_tkt006_enrutador.py`, `test_tkt007_consulta.py`, `test_tkt057_csrf.py` y `test_servidor_arranque.py` las repiten | Ticket de pruebas |
| Fixtures `base`, `entorno` y `contexto` | `test_tkt017_congelado.py`, su concurrencia y `test_tkt017_materializacion.py` las definen por su cuenta | TKT-017c |
| `backend/.coverage` | Sigue versionado | Higiene del repositorio |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/api/openapi.yaml` | `RenglonExplosion.importe_costo`; `x-tickets`; `422` y patrón sin `NUL`; descripciones de `BORRADOR`; fórmula de la explosión; ejemplo de `importe_total` (**señalar a quien apruebe el PR**) |
| `docs/07-especificacion-api.md` | Columna de tickets de la explosión |
| `docs/glosario.md` | La explosión suma también el costo unitario |
| `sdd/tickets/tkt-016/spec.md` | `PA-16.7` resuelta |
| `sdd/tickets/tkt-017/design.md` | Filas B4 a B6 y los ajustes de b2 |

### Verificación final (entrega TKT-017b2)

Salida real de los comandos, desde `backend/` salvo los de documentación y el cliente, sobre el estado final tras un ciclo de corrección. `docker info`: Docker 29.9.3 con el servidor en marcha.

```text
uv run ruff format --check .      → 270 files already formatted
uv run ruff check .               → All checks passed!
uv run mypy .                     → Success: no issues found in 270 source files
uv run lint-imports               → Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → verificar_float: archivos revisados: 32; hallazgos: 0
uv run pytest -q -ra --tb=short   → 2509 passed, 26 skipped in 490.06s (0:08:10)
npm run tipos:verificar (frontend) → Tipos al día.
npm run typecheck y npm run lint (frontend) → sin errores
python tools/verificar_docs.py    → ✓ Sin problemas.
python tools/verificar_escenarios.py → Escenarios: 164 · exigidos 0 · cubiertos 0 · faltan 0 · pendientes 164 · retirados 0
python -m unittest discover -s tools/tests → OK (510 tests)
```

Los 26 omitidos son las pruebas contra el archivo real del catálogo. `verificar_escenarios.py` no exige ningún test de HDU-001 mientras `tools/historias_activas.txt` la deje `PENDIENTE`: su verde no prueba la cobertura por nombre; la prueba la tabla de «Pruebas» y la activación es `P-13` en la fila C4. El CI completo de GitHub Actions se verifica en `/sdd-completar`, al abrir el PR único.

##### Resultado por criterio (alcance b2)

Todos los criterios `[M]` de b2 (`CA-B8`, `CA-B9` y `CA-R1`) quedan cumplidos con la evidencia de «Resultado contra criterios de aceptación (alcance b2)». Con esta entrega queda completo el alcance de TKT-017b; solo falta TKT-017c (presupuesto de control).

##### Veredicto

**LISTO PARA EJECUTAR · TKT-017c.** La entrega TKT-017b2 queda revisada y acumulada en la rama `tkt-017a3-materializacion`, sin pull request.
