# TKT-001 · Estructura del repositorio y herramientas base

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilado a Funcionalidad sin criterios de negocio) |
| **Historia** | Épica 0 · Fundación |
| **Épica / sprint** | Épica 0 · Sprint 0 |
| **Puntos** | Talla S |
| **Reglas implicadas** | Ninguna `RN-xx`. Requisitos `RNF-07` y, de forma indirecta, `RNF-08` |
| **Invariantes en riesgo** | Ninguno del modelo de datos. Garantías existentes que deben sobrevivir: `CA-R1` a `CA-R4` |
| **Módulos en alcance** | Ninguno. Solo andamiaje de `backend/` y `frontend/` |
| **Capas en alcance** | Ninguna. Configuración y documentación |
| **Depende de** | — |
| **Rama** | `tkt-001-estructura-repositorio` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita, pendiente de aprobación |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-17 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-17 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-17 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario |
| 2026-10-17 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito: 9 filas, ~350 líneas, sin ADR |
| 2026-10-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño |
| 2026-10-17 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Nueve filas ejecutadas con TDD, nueve mutantes, auditorías de arquitectura y seguridad; sin commit |
| 2026-10-17 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada en verde; seguridad aprobada; arquitectura aprobada tras tres ciclos de corrección |
| 2026-10-17 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos, `verificar_docs.py` sin problemas, commit local; el PR lo abre una persona |

## Decisiones registradas

- 2026-10-17 · El usuario decidió que el proyecto `uv` vive en `backend/`, que `frontend/` solo lleva `package.json`, TypeScript strict y ESLint sin Vite ni React, que el arranque verificado es `uv sync`, `npm ci` y los comandos de calidad en verde sobre una copia limpia, y que el `.editorconfig` fija UTF-8 sin BOM con LF y excepción con BOM para `*.ps1`.
- 2026-10-17 · El usuario validó el Must (M1 a M6) y el Should S1. Los non-goals de la sección «Won't» quedan fijados.

- 2026-10-17 · El usuario aprobó el diseño con dos desviaciones respecto al encargo: el verificador de codificación se prueba con `unittest` (no pytest) y la comprobación vive dentro de `tools/verificar_docs.py` (no en un script nuevo).
- Pendiente de escalar: `verificar_docs.py` falla mientras el hub enlace `impl.md` y `delta.md` inexistentes. Afecta a todos los tickets del toolkit.

## Tickets futuros sugeridos

- **TKT-002 (criterio de regresión):** al crear los `dominio/` reales, comprobar que el patrón de mypy estricto de `backend/pyproject.toml` sigue aplicando a sus rutas.
- **TKT-009 (criterio de integración):** invocar en CI la verificación de codificación de `tools/`, auditar con `pip-audit` y decidir la política de versiones de `eslint` y `@eslint/js`.
- **TKT-003:** resolver la tensión entre `.env.example` sin valores y «valores de desarrollo evidentes» de `conv-docker`.
- **Cada `/sdd-completar` de TKT-002, 003, 004, 005, 008 y 059:** quitar la marca «desde TKT-xxx» del comando que habilita. Detalle en [delta.md](delta.md).
