# Impl · TKT-072 · Concepto único por obra y sus apariciones por área

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta.md](delta.md)

## Qué se implementó

Migración Alembic `0010`: tabla `partida_concepto`, `concepto` reducido a código/descripción/unidad, `linea_base_concepto.partida_concepto_id`, guardas de subida y bajada con `LOCK TABLE`, fábricas de prueba y tres suites nuevas (`test_tkt072_*`). Regresión de TKT-010 a TKT-016 ajustada. Documentación, ADR-20261105, invariante 39 y conteos actualizados.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-05 | A1 y A2 en un solo cambio de migración (con guardas desde el inicio) | Evitar estado intermedio roto entre filas |
| 2026-11-05 | `test_tkt011_ca01_claves_foraneas_sin_cascada` filtra tablas por `estructura_esperada` | `partida_concepto` añade dos FK; TC-17 de TKT-072 las cubre |
| 2026-11-05 | NO_NEGATIVOS de `concepto` no movidos a `partida_concepto` en TKT-011 | Quedan 14 columnas en `0006`; negatividad de aparición en TC-07/TC-08 de TKT-072 |
| 2026-11-05 | Sin salida TDD en rojo pegada por fila | Migración y fábricas precedieron a la captura; mutación en revisión valida los tests |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0010_presupuesto_concepto_de_partida.py` | nuevo | infraestructura |
| `backend/tests/conftest.py` | modificado | pruebas |
| `backend/tests/test_tkt072_esquema.py` | nuevo | pruebas |
| `backend/tests/test_tkt072_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt072_preparacion.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_estructura.py` | modificado | pruebas |
| `backend/tests/test_tkt011_linea_base.py` | modificado | pruebas |
| `backend/tests/test_tkt011_migracion_linea_base.py` | modificado | pruebas |
| `docs/03-modelo-datos.md`, `docs/glosario.md`, ADR, índices, specs | modificado | documentación |

## Pruebas

34 casos nuevos en `test_tkt072_*` (TC-01…TC-22). Regresión TKT-011 ajustada; `TC-48`, `TC-49` y CA-19 esc. 3 usan base en `0009` sembrada con `linea_base_con_copias_anterior_a_0010`.

### Ciclo TDD por fila

#### Fila A0

**Rojo:** no aplica (línea base sobre `0009`).

**Verde:**

```text
0009 (head) antes del cambio; pytest baseline del repo en verde.
```

#### Fila A1–A2

**Rojo:** no capturado en disco (migración y fábricas ya existían al abrir pruebas).

**Verde:**

```text
2051 passed, 26 skipped in 337.54s (0:05:37)
```

**Refactor:** sin refactor adicional.

**Tests devueltos al tester:** ninguno.

**Mutación en rutas críticas** (revisión 2026-11-05, revertido tras cada uno):

| Mutante | Test que cayó |
|---|---|
| M-1 · sin `uq_partida_concepto_*` | `test_tkt072_ca04_aparicion_repetida…`, `test_tkt072_car1_restricciones…` |
| M-3 · sin guarda de subida | `test_tkt072_ca08_la_subida_se_niega…` (×2) |
| M-4 · sin guarda de bajada | `test_tkt072_ca08_la_bajada_se_niega…` (×3) |
| M-5 · `CASCADE` en `fk_partida_concepto_concepto_id` | `test_tkt072_ca05…[concepto-…]` |
| M-11 · sin `fk_linea_base_concepto_partida_concepto_id` | `test_hdu001_esc14_copia_sin_aparicion…`, `test_tkt072_car1…` |
| M-12 · deduplicar conceptos en `preparacion_json` | `test_tkt072_car3_la_preparacion…` |

M-2, M-6, M-7, M-8, M-9 y M-10 no se aplicaron en esta revisión (mismo patrón que M-1/M-3); anotado para spot-check opcional en `/sdd-completar`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A0 | orquestador | `haiku` | Composer | Verificación local |
| A1 rojo/verde | `tester-backend` | `sonnet` | Sonnet | Disparadores permisos/disparador |
| A1 verde | orquestador + SQL | `sonnet` | Composer | Migración `0010` |
| A4 | generalPurpose | `haiku` | Composer fast | Documentación y conteos |
| A6 | orquestador | `sonnet` | Composer | Suite completa |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` … `CA-9` | `[M]` | Cumplido | TC-01…TC-23 |
| `CA-R1` … `CA-R3` | regresión | Cumplido | TC-16, TC-17, TC-22, suites TKT-010…016 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO | Ninguno. Solo migración y pruebas; sin cruce de fronteras; invariante 14 intacto; fase 1 | 1 |
| `auditor-sql` | APROBADO | Guardas, `NUMERIC`, nombres de restricción, bajada recrea `concepto` como `0006` | 1 |
| `auditor-docs` | APROBADO | `verificar_docs.py` 39/39; ADR e invariante 39 presentes | 1 |

## Verificación final (`/sdd-revisar` 2026-11-05)

```text
docker info → Client 29.9.2 (OK)
uv run pytest → 2051 passed, 26 skipped in 353.98s (0:05:53)
uv run ruff check . → All checks passed!
uv run mypy . → Success: no issues found in 237 source files
uv run lint-imports → Contracts: 16 kept, 0 broken
uv run python -m herramientas.verificar_float → hallazgos: 0
python tools/verificar_docs.py → ✓ Sin problemas (39 invariantes, 39 ADR)
python -m unittest discover -s tools/tests -v → Ran 510 tests OK
tests/test_tkt072_*.py → 34 passed
```

**Criterios `[M]`:** 12/12 cubiertos (CA-1…CA-9, CA-R1…CA-R3) vía TC-01…TC-22 y regresión TKT-010…016.

**Desviaciones abiertas (Menor):** salida TDD en rojo no archivada; mutantes M-2, M-6, M-7, M-8, M-9, M-10 sin spot-check en revisión.

**OpenAPI:** sin cambios en este ticket.

Siguiente: `/sdd-completar TKT-072`.
