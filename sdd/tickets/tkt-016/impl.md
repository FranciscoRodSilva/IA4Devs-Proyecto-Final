# Impl · TKT-016a · Cálculo de la explosión (regla pura)

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta.md](delta.md)

## Qué se implementó

TKT-016a entrega la regla pura `calcular_explosion` en `presupuesto/dominio/explosion.py`, los cocientes con nombre en `tipos_base`, rechazo todo-o-nada con causas enumeradas (`M4`), redondeo solo en `cuantizar()` (`PA-23` cerrada en documentación) y 29 pruebas de dominio (TC-01–TC-23). TKT-016b (`CA-8`, `CA-10`) queda pendiente.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-05 | Implementación A2–A5 en un solo módulo `explosion.py` completo | Mismo algoritmo; evita estados intermedios no compilables entre filas |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/tipos_base/numericos.py` | modificado | tipos_base |
| `backend/tipos_base/__init__.py` | modificado | tipos_base |
| `backend/cimenta/presupuesto/dominio/explosion.py` | nuevo | dominio |
| `backend/herramientas/soporte_tkt016.py` | nuevo | pruebas |
| `backend/tests/test_tkt016_*.py` (4 archivos) | nuevo | pruebas |
| `backend/tests/test_tipos_base_redondeo.py` | modificado | pruebas |
| `docs/adr/20261103-explosion-por-tipo-de-partida.md` | nuevo | docs |
| `docs/adr/README.md`, `docs/02-arquitectura.md`, `docs/01-descripcion-producto.md`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `README.md`, `llms.txt`, `CLAUDE.md`, `.claude/skills/conv-dominio-python/SKILL.md`, `docs/adr/20261019-tipos-numericos-base.md` | modificado | docs |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01–04 | `test_tkt016_cocientes.py` | feliz/rechazo | `CA-2`, `CA-7`, `CA-R1` | FALLA | PASA |
| TC-05–12 | `test_tkt016_explosion.py` | feliz | `CA-1`–`CA-5` | FALLA | PASA |
| TC-13–20 | `test_tkt016_rechazos.py` | **rechazo** | `CA-6`, `CA-7`, `M4` | FALLA | PASA |
| TC-21–22 | `test_tkt016_fronteras.py` | regresión | `CA-9`, `CA-R1` | FALLA | PASA |
| TC-23 | suites TKT-013/014/tipos_base | regresión | `CA-R2` | PASA | PASA |

### Ciclo TDD por fila

#### Fila A0 · línea base

**Rojo:** no aplica.

**Verde:**

```text
179 passed in 14.43s (regresión TKT-013/014/tipos_base)
ruff, mypy, lint-imports (16 kept), verificar_float: 0 hallazgos
```

#### Filas A1–A6 · regla y rechazos

**Rojo:** `ModuleNotFoundError: explosion`, `ImportError: cociente_rendimiento`.

**Verde:**

```text
29 passed in 0.09s (test_tkt016_*)
```

**Refactor:** extracción `_dividir`; renombre `grupo` en agregación para no sombrear `clave_insumo`.

**Mutación (A8):** verificados en sesión M-4 (quitar filtro MATERIAL → TC-07 rojo) y M-10 (primera causa sola → TC-13 rojo); revertidos. Resto cubierto por la tabla de mutación del design y tests nombrados.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A0–A8 | orquestador Cursor | según design | Composer 2.5 | Ejecución directa en `/sdd-ejecutar` |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1`–`CA-7` | `[M]` | Cumplido | TC-05–TC-20 |
| `CA-9` | `[M]` | Cumplido | TC-21 |
| `CA-R1`, `CA-R2` | regresión | Cumplido | TC-04, TC-22, TC-23 |
| `CA-8`, `CA-10` | `[M]` | Cumplido en TKT-016b | TC-24–TC-27 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | APROBADO (ciclo 1; A8 parcial documentado en delta) | F001–F007 cerrados o en deuda | 1 |
| `auditor-codigo` | APROBADO (F001 resuelto; F002–F009 menores en deuda delta) | F001–F009, O1–O3 | 1 |
| `auditor-docs` | APROBADO (ciclo 1) | F001, F002 | 1 |
| `auditor-sql` | N/A | Sin esquema | — |
| `auditor-seguridad` | N/A | Sin superficie externa | — |

### Ciclo de corrección 1

| ID | Acción |
|---|---|
| F001 | `_tipos_con_causas_de_importe` excluye por `fila`, no por `codigo`; test `test_hdu001_esc15_codigo_repetido_en_dos_tipos_no_oculta_sugerido_negativo` |
| F002 / M-14 | Test `test_hdu001_esc14_mismo_insumo_en_dos_tipos_partida_da_dos_filas` |
| F004 docs | Enlace explosión sin ordinal ADR-036 conflictivo en `docs/03-modelo-datos.md` |
| F001 docs | `README.md:264` → 38 ADR |

## Verificación final (`/sdd-revisar` 2026-11-05)

**Must TKT-016a:** M1–M4 cubiertos (TC-01–TC-23). **M5** diferido a TKT-016b (partición P-3 aprobada).

**Suite (ejecutada en revisión):**

```text
2017 passed, 25 skipped in 374.21s (0:06:14)
ruff check . → All checks passed!
mypy cimenta/ tipos_base/ → Success
lint-imports → 16 kept, 0 broken
verificar_float → 0 hallazgos
python tools/verificar_docs.py → ✓ Sin problemas (adrs 38)
python -m unittest discover -s tools/tests → OK
test_tkt016_* → 31 passed in 0.12s (post-corrección)
```

**Pendiente menor (no bloquea PR de 016a):** endurecer TC-01/TC-12; TC-10 más semántico; barrido mutantes M-1…M-15 restantes antes de fusionar (A8 ⚠).

## Fuera de alcance (TKT-016a)

- Filas B1–B4 (libro sintético, oráculo `AP-058-25`, `arranque-local.md`).
- API, persistencia, `interfaz.py` (TKT-017).

---

# Impl · TKT-016b · Libro sintético y reconciliación Union

> Entrega hermana; cierra el paraguas TKT-016 tras `/sdd-completar TKT-016b`.

## Qué se implementó

- `libro_explosion_sintetico`, `conceptos_a_explotar`, `cargar_oraculo_explosion_union` en `herramientas/soporte_tkt016.py` (sin código de producción).
- `tests/test_tkt016_libro_sintetico.py` (TC-24, TC-25).
- `tests/test_tkt016_archivo_real.py` (TC-26, TC-27); fixture `oraculo_explosion_union` en el mismo módulo.
- `docs/arranque-local.md`: variable `CIMENTA_EXPLOSION_UNION` y formato CSV (B3).

## Criterios TKT-016b

| Criterio | Estado | Evidencia |
|---|---|---|
| `CA-8` | Cumplido | TC-24, TC-25 |
| `CA-10` esc. 1 | Cumplido con skip condicional | TC-26 (`PA-T3` / variables) |
| `CA-10` esc. 2 | Cumplido | TC-27 |

## Verificación B1–B3 (2026-11-05)

```text
uv run pytest tests/test_tkt016_libro_sintetico.py tests/test_tkt016_archivo_real.py -q -ra
→ 3 passed, 1 skipped (CIMENTA_CATALOGO_UNION no definida en entorno local)
```

**B4 (2026-11-05):** `2022 passed, 26 skipped in 401s`; `lint-imports` 16 kept; `verificar_float` 0 hallazgos; `verificar_docs.py` ✓.

## Ajuste revisión ciclo 1

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-05 | `leer_oraculo_explosion_union(Path)` en soporte; `pytest.skip` solo en tests | Evitar `pytest` en `herramientas/` (paridad con `conftest._bytes_catalogo_real`) |

## Verificación final (`/sdd-revisar` · TKT-016b · 2026-11-05)

**Must (paraguas completo):** M1–M4 en 016a; **M5** en 016b (TC-24–27). **CA-8**, **CA-10** cumplidos con skip documentado (`PA-T3`, variables).

```text
uv run pytest tests/test_tkt016_*.py -q -ra → 34 passed, 1 skipped
uv run pytest -q --tb=no → 2022 passed, 26 skipped (~402s)
ruff check . → All checks passed!
mypy cimenta/ tipos_base/ → Success
lint-imports → 16 kept, 0 broken
verificar_float → 0 hallazgos
python tools/verificar_docs.py → ✓ Sin problemas
```

**Deuda heredada (no bloquea 016b):** A8 mutación parcial (016a); menores TC-10/aserciones; `dinero.ts` (P-7).

## Auditorías (TKT-016b · ciclo 1)

| Auditor | Veredicto | Notas |
|---|---|---|
| `auditor-arquitectura` | APROBADO | Sin código de producción nuevo; dominio intacto |
| `auditor-codigo` | APROBADO | Tras quitar `pytest` de soporte |
| `auditor-docs` | APROBADO | `arranque-local.md` alineado |
| `auditor-sql` | N/A | |
| `auditor-seguridad` | N/A | CSV local vía env; sin endpoint |

## Siguiente

[`delta.md`](delta.md) se actualiza en `/sdd-completar TKT-016b`.
