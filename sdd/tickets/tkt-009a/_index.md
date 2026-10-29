# TKT-009a · Pipeline de pruebas y fronteras

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA PR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla S; unas 265 líneas según el diseño común |
| **Reglas implicadas** | Reglas 1, 2 y 3 de `CLAUDE.md` convertidas en compuertas; `RNF-07` por los permisos y la ausencia de secretos en los workflows |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R1`, `CA-R2` y `CA-R4` |
| **Módulos en alcance** | `.github/workflows/ci.yml`, `tools/tests/test_definicion_ci.py`, `backend/pyproject.toml` (`pytest-cov`), `.gitignore` y las marcas «desde TKT-009» de las reglas 1 a 3 |
| **Capas en alcance** | Entrega continua. Ninguna capa de la aplicación |
| **Depende de** | TKT-002 (ARCHIVADO) · TKT-008a, TKT-008b y TKT-008c (ARCHIVADOS) |
| **Bloquea a** | TKT-009b, TKT-009c y TKT-009d; TKT-061 y TKT-062 |
| **Rama** | `tkt-009a-pipeline-pruebas` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-28 |
| Design | [design.md común](../tkt-009/design.md), filas A0 a A8 | `/sdd-disenar` | Aprobado el 2026-10-28 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-29 |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009, aprobado por el usuario con todas las recomendaciones. Spec repartida: M1, M2, M3, M4, M6, M9 y su parte de M12; `CA-1` a `CA-5`, `CA-9`, `CA-12`, `CA-R1`, `CA-R2` y `CA-R4`. Primera parte en fusionar |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas A0 a A8 hechas con ciclo TDD. Pipeline de ocho trabajos en verde en el PR #2; rondas de ensayo 1 y 2 en rojo como se esperaba. Cuatro auditorías `APROBADO` (código tras un ciclo de corrección por un hallazgo Mayor). Se corrigió de paso una prueba de TKT-008b que fallaba en Linux. Detalle en [impl.md](impl.md) |
| 2026-10-29 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Once criterios `[M]` (CA-1 a CA-5, CA-9, CA-12, CA-R1, CA-R2, CA-R4 y CA-15) cumplidos con evidencia. Suite ejecutada: 1138 pruebas de backend, `ruff`, `mypy`, `lint-imports` y `verificar_docs.py` en verde, y 77 pruebas de `tools/`. Cuatro auditorías sin hallazgos Mayores ni Críticos tras tres ciclos de corrección de registro y documentación (solo Menores). Una frase de `CLAUDE.md` se aplicó sin reauditar por límite de ciclos |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: MinIO queda fuera del trabajo `backend` hasta TKT-059.

- **2026-10-29 · Excepción de alcance: `Armazon.test.tsx` de TKT-008b.** Durante la revisión del PR #2, el pipeline mostró que la prueba `tkt008_ca07_esc07` de TKT-008b falla en Linux con CPU escasa: el doble de sesión respondía siempre 200 y repoblaba la caché tras el cierre. La persona dueña eligió arreglarla en este ticket («Arreglar aquí»). El cambio solo toca el doble de pruebas (`dobleSesionQueTermina`), sin relajar aserciones ni tiempos. Lo hizo `tester-frontend` (commit `968519b`) y no hay defecto de producción.
