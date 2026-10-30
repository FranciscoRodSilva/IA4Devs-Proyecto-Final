# TKT-062b · Revisión automatizada

> Hub del ticket. Se lee **primero**, siempre. Es la segunda de las dos partes de [TKT-062](../tkt-062/_index.md).

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1, o el 4 si se usa la costura del sprint 1 |
| **Puntos** | Talla S en el backlog; unas 920 líneas según el diseño común (≈ 400 de flujo, script, instrucciones, documentación y ADR y ≈ 520 de pruebas). Queda por encima del tope orientativo y no se parte más: el flujo sin el filtro de publicación no comenta nada |
| **Reglas implicadas** | `RNF-07`, `RNF-08`; `CLAUDE.md` (la revisión comenta y no aprueba); convenciones §12. Ninguna `RN-xx` |
| **Invariantes en riesgo** | Ninguna tabla. De proceso: `comprobar_tc13`, `comprobar_tc21`, `comprobar_tc22` y `test_tc18_ningun_workflow_declara_secrets` de TKT-009, que aquí se acotan con la excepción nombrada de `revision-ia.yml`. Regresión `CA-R1` a `CA-R4` |
| **Módulos en alcance** | `.github/workflows/revision-ia.yml`, `.claude/revision-pr.md`, `tools/publicar_revision.py`, `tools/tests/test_definicion_revision.py` y `test_definicion_ci.py`, `test_definicion_dependabot.py`, ADR-028 y la documentación de la revisión. Ningún archivo de `backend/` ni de `frontend/` |
| **Capas en alcance** | Entrega continua. Ninguna capa de la aplicación |
| **Depende de** | TKT-062a (la protección de `Produccion` y la etiqueta requerida) |
| **Bloquea a** | Nada de la fase 1; el informe de calidad por etiqueta lo usa más adelante |
| **Rama** | `tkt-062b-revision-automatizada-pr`, creada desde `Produccion` con TKT-062a ya fusionado |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-29 |
| Design | [design.md común](../tkt-062/design.md), filas B1 a B8 | `/sdd-disenar` | Aprobado el 2026-10-29 |
| Impl | `impl.md` | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-29 | — | `LISTO PARA EJECUTAR` | partición de TKT-062 | Nace del gate de diseño de TKT-062, aprobado por la persona responsable del proyecto. Spec repartida: M1 a M4, M6, M7, M9, M10, su parte de M8 y de M11, y el Should S1; `CA-1` a `CA-5`, `CA-7`, `CA-8`, `CA-10`, `CA-11`, `CA-S1`, su parte de `CA-9` y `CA-12`, y `CA-R1` a `CA-R4`. Se ejecuta con TKT-062a ya fusionado |

## Decisiones registradas

Las de [TKT-062](../tkt-062/_index.md#decisiones-registradas), que valen para las dos partes. En esta parte:

- **La clave de API es dedicada**, en un espacio de trabajo propio de Anthropic y con un tope de gasto mensual que fija la persona dueña (`D-3`); el valor queda en `impl.md`.
- **El riesgo residual de la clave se acepta** con las cinco mitigaciones del diseño (`D-1`); su revisión y la rotación quedan en ADR-028.
- **El PR de esta parte puede quedar sin comentario de revisión**: la rama base todavía no tiene el flujo ni las instrucciones. No bloquea nada porque la revisión no es una comprobación requerida.

## Tickets futuros sugeridos

Los del [paraguas](../tkt-062/_index.md#tickets-futuros-sugeridos).
