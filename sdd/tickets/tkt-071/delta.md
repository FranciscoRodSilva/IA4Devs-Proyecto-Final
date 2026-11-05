# Delta · TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Nota fechada TKT-071 sobre `katex` y `mermaid-cli` 12.2.0 | `docs/adr/20261029-vale-para-prosa-en-espanol.md` | Registrar la corrección sin reescribir el texto histórico del ADR |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Lock de `mermaid-cli` | `.github/mermaid/package.json` y `package-lock.json` | 12.0.0 → **12.2.0** exacto; `katex` 0.16.47 → **0.18.10** (fuera de GHSA-238p-pmpm-9mq7) |
| Parches de backend | `backend/uv.lock` | `sqlalchemy` 2.1.5 → **2.1.6**, `alembic` 1.20.0 → **1.20.1**, `ruff` 0.17.1 → **0.17.3** |
| ESLint del frontend | `frontend/package.json` y `package-lock.json` | 10.0.1 → **10.13.0** (transitivas de eslint y entradas E-1 bajo `@tailwindcss/oxide-wasm32-wasi`, aprobadas en diseño) |
| TC-65 | `tools/tests/test_definicion_documentacion.py` | Versión exacta exigida **12.2.0** (antes 12.0.0) |
| Documentación de versiones | `docs/06-stack-tecnologico.md`, `tools/README.md`, `.claude/skills/conv-documentacion/SKILL.md` | Citas de `mermaid-cli` y SQLAlchemy al día |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Copia vulnerable de `katex` 0.16.47 en el lock de mermaid | `.github/mermaid/package-lock.json` | Sustituida por la cadena de `mermaid-cli` 12.2.0 |

## Comportamiento observable nuevo

Ninguno para usuarios del producto. Para quien mantiene el repositorio: la auditoría de `.github/mermaid/` deja de reportar `katex`; el pipeline documental exige `mermaid-cli` **12.2.0** exacto (TC-65).

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoint, DTO, OpenAPI, esquema PostgreSQL | Ninguno | No |
| Pipeline | Mismos pasos; versiones subyacentes de herramientas de CI/dev | No para la aplicación |
| Tipos generados del cliente | Sin cambio | No |

## Decisiones (ADR)

No se creó ADR nuevo. La excepción **E-1** del lock del frontend (entradas bajo `@tailwindcss/oxide-wasm32-wasi/node_modules/*`) y la verificación **K** sobre todas las rutas `katex` del lock quedan documentadas en `design.md` D-1 y D-2 y en `impl.md`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `npm install --package-lock-only --save-exact <pkg>@<ver>` acotado al paquete evita una regeneración libre que viola CA-5 | H-1…H-3 del diseño; diff U/D en ejecución | Tickets de bump de dependencias |
| En Windows, redirecciones de PowerShell a lock JSON corrompen UTF-16; los comandos de verificación del diseño deben ir en Git Bash o pipe a Python UTF-8 | Fallo de `u.py` sobre copia con BOM | Ejecución local de tickets de locks |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | Tickets de solo locks en Windows: quoting de rutas con espacio obliga scripts `.sh` fuera del repo o `working_directory` del shell; el diseño ya decía bash (D-6) | Baja |
| `documentación` | La spec cita «15 contratos» de `import-linter`; el repo ya reporta **16 kept** — conviene alinear fichas de tickets de mantenimiento con el conteo real | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Saltos mayor: `typescript` 7, `react-router` 8, `@types/node` 26, `@testing-library/jest-dom` 7 | Non-goals de la spec; Dependabot los propone aparte | Decisión explícita (lista en `_index.md`) |
| Alertas `minimatch` y `deepmerge` en frontend (severidad moderada/baja) | Aceptadas con motivo en spec; `--audit-level=high` sigue en 0 | Ninguno hasta haya camino limpio |
| Cierre de alerta `katex` y PR Dependabot #22, #16, #13, #12 en GitHub | Dependabot cierra al detectar versiones al día tras fusión (A-1) | Seguimiento en comentario de fusión |

## Pull request

**Título:** `TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot`
**Origen:** `agent`
**Cuerpo:** ver PR abierto por `/sdd-completar`.

**Fusión con omisión:** registro en comentario del PR tras aprobación explícita y diez comprobaciones en verde.
