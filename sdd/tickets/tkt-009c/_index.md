# TKT-009c · Verificador de escenarios sin test

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla M; unas 440 líneas según el diseño común |
| **Reglas implicadas** | [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md); regla 14 de `CLAUDE.md` por los escenarios de rechazo |
| **Invariantes en riesgo** | Ninguna tabla. Regresión `CA-R4` |
| **Módulos en alcance** | `tools/verificar_escenarios.py`, `tools/historias_activas.txt`, `tools/tests/`, el trabajo `herramientas` de `ci.yml` y las prosas de retiro de la documentación |
| **Capas en alcance** | Herramientas de verificación. Ninguna capa de la aplicación |
| **Depende de** | TKT-009a |
| **Bloquea a** | TKT-009b y TKT-009d (por el orden de fusión); TKT-069 |
| **Rama** | `tkt-009c-verificador-escenarios` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-28 |
| Design | [design.md común](../tkt-009/design.md), filas C1 a C6 | `/sdd-disenar` | Aprobado el 2026-10-28 |
| Impl | impl.md | `/sdd-ejecutar` | Pendiente |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009. Spec repartida: M5 y su parte de M12; `CA-6`, `CA-7`, `CA-8` y `CA-R4`. No se ejecuta hasta que TKT-009a esté `ARCHIVADO` o `LISTO PARA PR`. Segunda parte en fusionar |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: el verificador solo cuenta escenarios HDU, y la fase 2 y el retiro se marcan con la línea `fase 2` y el segmento ` · retirado por TKT-0NN`.
