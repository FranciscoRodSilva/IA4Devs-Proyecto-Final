# TKT-009a · Pipeline de pruebas y fronteras

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA EJECUTAR

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
| Impl | impl.md | `/sdd-ejecutar` | Pendiente |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009, aprobado por el usuario con todas las recomendaciones. Spec repartida: M1, M2, M3, M4, M6, M9 y su parte de M12; `CA-1` a `CA-5`, `CA-9`, `CA-12`, `CA-R1`, `CA-R2` y `CA-R4`. Primera parte en fusionar |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: MinIO queda fuera del trabajo `backend` hasta TKT-059.
