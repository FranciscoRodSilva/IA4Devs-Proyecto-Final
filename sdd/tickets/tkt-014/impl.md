# Impl · TKT-014 · Lector de análisis de precios unitarios

> [← index](_index.md) | [← design](design.md) | [← delta](delta.md) | Entrega **TKT-014a** (TKT-014b pendiente)

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

## Siguiente entrega

- **TKT-014b** sin iniciar (asociación, adaptador, reales, ADR-034).
