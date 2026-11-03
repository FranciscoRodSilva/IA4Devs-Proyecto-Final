# Impl · TKT-014 · Lector de análisis de precios unitarios

> [← index](_index.md) | [← design](design.md) | [← delta](delta.md) | Entregas **TKT-014a** (PR #38) + **TKT-014b**

## Qué se implementó

**TKT-014a** — dominio de la hoja de APU en memoria: objetos en `analisis.py`, lectura y cuadre en `lectura_analisis.py`, cinco causas nuevas en `CausaHallazgo`, ampliación de `interpretar_numero` a `Rendimiento` y `Porcentaje`, ayudante `herramientas/soporte_tkt014.py` y **44** pruebas en `tests/test_tkt014_hoja.py`. Sin adaptador openpyxl ni asociación (TKT-014b).

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-03 | E-1: pie `PRECIO UNITARIO` en columna **D** (44/44 hojas), valor en **G**; cargos D/E/G | Medición ENITI y Union Square |
| 2026-11-03 | Cabecera C/B; reconocimiento pie en cualquier columna tras `material` | E-1 |
| 2026-11-03 | `"viaticos" in rotulo`; fixture `CARGOS VIATICOS Y HOSPEDAJE` + 2 roles | E-2 / revisión ciclo 2–3 |
| 2026-11-03 | Tests con `Hallazgo` completo (`_expect`); TC cabecera sin rótulo vs campos ilegibles | Revisión ciclo 3 |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/analisis.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/lectura_analisis.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/catalogo.py` | modificado | dominio |
| `backend/cimenta/presupuesto/dominio/lectura_catalogo.py` | modificado | dominio |
| `backend/herramientas/soporte_tkt014.py` | nuevo | herramientas |
| `backend/tests/test_tkt014_hoja.py` | nuevo | pruebas |
| `docs/05-tickets-trabajo.md` | modificado | documentación |
| `sdd/tickets/tkt-014/design.md` | modificado | diseño |
| `sdd/tickets/tkt-014/_index.md` | modificado | documentación |
| `sdd/tickets/tkt-014/impl.md` | nuevo | documentación |
| `sdd/_evolucion.md` | modificado | documentación |

## A0 · Experimentos (TKT-014a)

| Exp | Estado | Resultado |
|---|---|---|
| E-1 | Hecho | Insumos D/E/F/G; cargos D/E/G; cabecera C/B; pie D/G |
| E-2 | Hecho | 44 hojas; `cargosviaticosyhospedaje` |
| E-3 | Hecho | 24 + 20 hojas APU |
| E-4, E-5 | Diferido 014b | — |
| E-6 | Hecho | Fecha → `AAAA-MM-DD` |
| E-7 | No ejecutado | `'A\t B\xa0 C'.split()` → `['A','B','C']`; TC-01 cubre |

## Mutación (M-01…M-13)

13/13 en rojo con test indicado (ver ciclo 1). M-14, M-18: ejecutados en reauditoría ciclo 3 (mutación temporal); caen TC-01 y viáticos. Registro ampliado en ciclo 3 auditoría arquitectura.

## Resultado contra criterios (alcance TKT-014a)

| Criterio / Must | Nivel | Estado | Evidencia |
|---|---|---|---|
| M1–M4, M7, M8, S1 | `[M]`/`[S]` | Cumplido | `test_tkt014_hoja.py` |
| M5, M6 | `[M]` | Fuera de 014a | TKT-014b |
| M9 (Decimal) | `[M]` | Parcial | Dominio + tests; reales en 014b |
| CA-3, CA-4, CA-6, CA-16 | `[M]` | Cumplido sintético | TC-08, TC-10, TC-12, TC-20 |
| CA-10, CA-11, CA-13 | `[M]` | Cumplido sintético | TC-14–TC-19, TC-16/15 |
| CA-15 | `[M]` | Parcial | Decimal; determinismo 014b |
| CA-R1, CA-R2 | regresión | Cumplido | lint-imports, verificar_float, TKT-013 |
| CA-R3 | regresión | 014b | — |

## Verificación final (`/sdd-revisar` TKT-014a · ciclo 3 · 2026-11-03)

**Gate:** `_index.md` en `EN REVISIÓN`. `impl.md` presente.

**Docker:**

```text
Client:
 Version:    29.9.2
 Context:    desktop-linux
 Debug Mode: false
```

**Suite y comprobaciones (salida real):**

```text
uv run pytest tests/test_tkt014_hoja.py -ra --tb=no -q  → 44 passed in 0.10s
uv run pytest -q --tb=no                              → 1853 passed in 301.20s (0:05:01)
uv run ruff check .                                   → All checks passed!
uv run ruff format --check .                          → 192 files already formatted
uv run mypy cimenta/                                  → Success: no issues found in 90 source files
uv run lint-imports                                   → Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float         → hallazgos: 0 (24 archivos)
python tools/verificar_docs.py                        → ✓ Sin problemas.
```

**OpenAPI:** sin cambios en 014a.

**TDD:** deuda aceptada — sin salida rojo pegada por fila (observación arquitectura).

## Auditorías · ciclo 3

| Auditor | Veredicto inicial | Tras F012 + docs |
|---|---|---|
| `auditor-arquitectura` | **APROBADO** | APROBADO |
| `auditor-codigo` | REQUIERE CAMBIOS (F012) | F012 resuelto en mismo turno |
| `auditor-docs` | REQUIERE CAMBIOS (F001–F003) | Tabla sintética y `impl` actualizados |
| `auditor-sql` / `auditor-seguridad` | — | — |

**Veredicto de revisión TKT-014a:** **LISTO PARA PR** (entrega 014a).

**Menores no bloqueantes:** imports privados `lectura_catalogo` (F014), ramas `filas_ilegibles` mano de obra/cargo (F013), `M²` sin normalizar (TKT-013), duplicación `_leer_unidad`.

**Cierre:** `/sdd-completar TKT-014a` — ver [delta.md](delta.md) y PR en GitHub. **TKT-014** (paraguas) sigue abierto hasta **TKT-014b**.

## TKT-014b · qué se implementó

Asociación catálogo ↔ hojas APU (`M5`), insumos por crear (`M6`), objetos de libro en `analisis.py`, refactor de `lector_catalogo.py` con `leer_libro_presupuesto`, pruebas sintéticas (openpyxl) y **10** pruebas contra archivos reales (TC-40…TC-49). **ADR-035** documenta clave por descripción, lectura por rótulos y cuadre por suma. Rama: `tkt-014b-asociacion-lector`.

### Ajustes respecto al design (014b)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-03 | Tras viáticos, `cargosindirectos` / `cargosporcentuales` fijan bloque CARGOS y se omiten (no cargo) | TC-47: hoja `01` ENITI fila 52 |
| 2026-11-03 | `# type: ignore[misc]` en `_filas` con comentario de stubs | E-10 / mypy |
| 2026-11-03 | En docs, **ADR-035** (no «ADR-034» del design: el 034 ya era VPS) | Índice ADR existente |
| 2026-11-03 | TC-29: dos hojas (`H-LT`, `H-M2`) en lugar de `extend([-1:])` | Hallazgo auditor-código F001 |

### Archivos tocados (014b)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/asociacion_analisis.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/analisis.py` | modificado | dominio |
| `backend/cimenta/presupuesto/dominio/catalogo.py` | modificado | dominio |
| `backend/cimenta/presupuesto/dominio/lectura_analisis.py` | modificado | dominio |
| `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | modificado | infraestructura |
| `backend/tests/test_tkt014_asociacion.py` | nuevo | pruebas |
| `backend/tests/test_tkt014_lector.py` | nuevo | pruebas |
| `backend/tests/test_tkt014_archivos_reales.py` | nuevo | pruebas |
| `backend/tests/test_tkt014_hoja.py` | modificado | pruebas |
| `backend/tests/conftest.py` | modificado | pruebas |
| `backend/tests/test_tkt010_semilla_local.py` | modificado (docstring) | pruebas |
| `docs/adr/20261103-clave-de-insumo-y-lectura-de-apu.md` | nuevo | documentación |
| `docs/adr/README.md` | modificado | documentación |
| `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `docs/arranque-local.md` | modificado | documentación |
| `docs/adr/20261102-semilla-en-migracion-y-herramienta-local.md` | modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificado (35 ADR) | documentación |
| `sdd/_evolucion.md` | modificado | documentación |

### Experimentos E-4 y E-5 (014b)

| Exp | Estado | Resultado |
|---|---|---|
| E-4 | Hecho | Claves de insumo: descripción normalizada; 35 insumos distintos unión ENITI + Union |
| E-5 | Hecho | Totales medidos para CA-3/CA-16; cuadre reconstruido vs pie con tolerancia `1E-9` en TC-42 |

### Mutación M-14…M-18 (B5)

Mutación temporal, test en rojo, revertida en el mismo turno.

| Mutante | Cambio | Test que cae |
|---|---|---|
| M-14 | `normalizar_clave_insumo` sin colapsar espacios | TC-01, TC-28 |
| M-15 | Conflicto de unidad: quedarse con la primera | TC-30 |
| M-16 | Código en dos hojas: asociar solo la primera | TC-26 |
| M-17 | `leer_libro_presupuesto` doble apertura del libro | TC-35 |
| M-18 | Viáticos no cierran ante rótulo con tipo de cargo | TC-10 |

### Resultado contra criterios (alcance TKT-014b)

| Criterio / Must | Nivel | Estado | Evidencia |
|---|---|---|---|
| M5 | `[M]` | Cumplido | TC-23…TC-27, TC-40…TC-41 |
| M6 | `[M]` | Cumplido | TC-28…TC-33 |
| M1–M4, M7, M8, M9 (libro real) | `[M]` | Cumplido | TC-40…TC-49 |
| S1 (reales) | `[S]` | Cumplido | TC-42, TC-43 |
| CA-1, CA-2, CA-5, CA-7…CA-14 | `[M]` | Cumplido | `test_tkt014_*` según design |
| CA-3, CA-4, CA-6, CA-16 (reales) | `[M]` | Cumplido | TC-42, TC-43, TC-45, TC-46 |
| CA-10 (44 hojas) | `[M]` | Cumplido | TC-44 |
| CA-15 (determinismo / sin BD) | `[M]` | Cumplido | TC-33, TC-49 |
| CA-R3 | regresión | Cumplido | TKT-013 + lectura catálogo intacta en TC-48 |
| E-4, E-5 | design | Cumplido | Tabla arriba; TC-40…49 |

### Pruebas 014b (resumen)

74 pruebas en `test_tkt014_hoja.py`, `test_tkt014_asociacion.py`, `test_tkt014_lector.py`, `test_tkt014_archivos_reales.py`.

**Archivos reales** (requieren `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`):

```text
uv run pytest tests/test_tkt014_archivos_reales.py -q --tb=no  → 10 passed in 5.16s
```

### B4 · verificación documentación

```text
python tools/verificar_docs.py                        → ✓ Sin problemas.
python -m unittest discover -s tools/tests -v         → Ran 509 tests … OK
rg "33 (decisiones|ADRs)" CLAUDE.md README.md llms.txt → (sin coincidencias; conteo 35 ADR)
```

### Auditorías de cierre de fase (014b · `/sdd-ejecutar` paso 6)

Pendientes de la **segunda** pasada formal en `/sdd-revisar` (esta sesión).

## Verificación final · `/sdd-ejecutar` TKT-014b · 2026-11-03

**Gate:** `_index.md` → `EN REVISIÓN · TKT-014b`.

**Docker:**

```text
Client:
 Version:    29.9.2
```

**Suite y comprobaciones (salida real):**

```text
uv run pytest -q --tb=no                              → 1884 passed in 353.37s (0:05:53)
uv run ruff check .                                   → All checks passed!
uv run ruff format --check .                          → 196 files already formatted
uv run mypy .                                         → Success: no issues found in 196 source files
uv run lint-imports                                   → Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float         → (incluido en CAR2; 0 hallazgos)
python tools/verificar_docs.py                        → ✓ Sin problemas.
```

**OpenAPI:** sin cambios en 014b.

## `/sdd-revisar` TKT-014b · 2026-11-03

**Gate:** `_index.md` en `EN REVISIÓN` → cumplido.

### Auditorías (ciclo 1 → corrector → ciclo 2)

| Auditor | Ciclo 1 | Ciclo 2 |
|---|---|---|
| `auditor-arquitectura` | APROBADO (O001 histórico ADR-034 en log; O002 reales con env) | — |
| `auditor-docs` | APROBADO | — |
| `auditor-codigo` | REQUIERE CAMBIOS (F001–F004) | **APROBADO** (F001–F003 Resuelto; F004 Menor persiste) |

**Correcciones ciclo 1:** Vale ADR-035; enlaces ADR-035; TC-29/32; TC-38 AST + determinismo; `**variantes: Any` en soporte; TC-29 hallazgos `UNIDAD_NO_RECONOCIDA`.

### Verificación final · `/sdd-revisar` TKT-014b

```text
uv run pytest -q --tb=no                              → 1884 passed in 344.02s (0:05:44)
uv run ruff check .                                   → All checks passed!
uv run ruff format --check .                          → 196 files already formatted
uv run mypy .                                         → Success: no issues found in 196 source files
uv run lint-imports                                   → Contracts: 15 kept, 0 broken.
uv run python -m herramientas.verificar_float         → hallazgos: 0 (25 archivos)
python tools/verificar_docs.py                        → ✓ Sin problemas.
uv run pytest tests/test_tkt014_archivos_reales.py -q → 10 passed in 5.16s (con CIMENTA_CATALOGO_*)
```

**Veredicto de revisión TKT-014b:** **LISTO PARA PR**. CI completa de `ci.yml` → `/sdd-completar`.

**Siguiente:** [`delta.md`](delta.md) (`/sdd-completar TKT-014b`).
