# TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación, sin historia de usuario. Va en el bloque «Endurecimiento y operación» de `docs/05-tickets-trabajo.md` |
| **Épica / sprint** | Sin sprint asignado |
| **Puntos** | Ninguno de historia. Talla S |
| **Reglas implicadas** | Ninguna `RN-xx`. Requisito `RNF-08`, por mantenimiento y no por obligación: la alerta que corrige es de severidad baja |
| **Invariantes en riesgo** | Los 38 del esquema por el cambio de SQLAlchemy y Alembic, sobre todo 10, 14, 20 y 21; los 15 contratos de `import-linter`; `verificar_float` y `RUF032` |
| **Módulos en alcance** | Ninguno de `backend/cimenta/`. Lock de dependencias, una prueba de `tools/tests/` y documentación |
| **Capas en alcance** | Cadena de suministro y documentación. Ni dominio, ni aplicación, ni api, ni frontend |
| **Depende de** | TKT-009b (estado: archivado), TKT-009d (estado: archivado) |
| **Rama** | `tkt-071-mantenimiento-dependencias` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-03 |
| Impl | `impl.md` (se enlaza en `/sdd-ejecutar`) | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-03 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada con 12 criterios `[M]`, 6 de ellos con escenario de rechazo; la persona dueña validó el Must |
| 2026-11-03 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño de 10 filas en `haiku`, apoyado en cinco experimentos ejecutados al diseñar; la revisión de impacto no encontró omisiones |
| 2026-11-03 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | Aprobación humana | La persona dueña aprobó el diseño, incluida la excepción E-1 del lock del frontend |

## Decisiones registradas

- 2026-11-03 · La persona dueña decidió el identificador TKT-071, un solo ticket que reúne la corrección de `katex` y los parches de Dependabot, la talla S y su ubicación en el bloque «Endurecimiento y operación».
- 2026-11-03 · La persona dueña decidió no subir los mínimos de `backend/pyproject.toml`: la versión real la fija `uv.lock`.
- 2026-11-03 · La persona dueña decidió que los PR de Dependabot #22, #16, #13 y #12 los cierre Dependabot al detectar las versiones al día, sin `gh` a mano; `/sdd-completar` lo comprueba.
- 2026-11-03 · Las alertas de `minimatch` (GHSA-g3hv-75wg-m249) y `deepmerge` (GHSA-gcqx-w48m-w2h4) se aceptan con su motivo: herramientas de desarrollo, sin entrada externa y sin camino de actualización por los paquetes que las traen. Descartarlas en GitHub lo decide la persona dueña.

## Tickets futuros sugeridos

- Decidir los saltos de versión mayor que Dependabot propuso: `typescript` 7 (#14, rompe el pipeline), `react-router` 8 (#11), `@types/node` 26 (#15) y `@testing-library/jest-dom` 7 (#9).
