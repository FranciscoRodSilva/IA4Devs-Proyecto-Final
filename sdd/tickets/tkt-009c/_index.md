# TKT-009c · Verificador de escenarios sin test

> Hub del ticket. Se lee **primero**, siempre. Es una de las cuatro partes de [TKT-009](../tkt-009/_index.md).

## Estado

LISTO PARA PR

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
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-29 |
| Delta | delta.md | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-28 | — | `LISTO PARA EJECUTAR` | partición de TKT-009 | Nace de la decisión del gate de diseño de TKT-009. Spec repartida: M5 y su parte de M12; `CA-6`, `CA-7`, `CA-8` y `CA-R4`. No se ejecuta hasta que TKT-009a esté `ARCHIVADO` o `LISTO PARA PR`. Segunda parte en fusionar |
| 2026-10-29 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas C1 a C6 hechas con ciclo TDD sobre la rama de TKT-009a. Verificador con 171 pruebas de `tools/`, mutación de 110 mutantes y ensayo en el pipeline que mostró un defecto real (el paso del verificador se omitía si fallaban las pruebas), corregido con `if: ${{ !cancelled() }}`. Auditoría de arquitectura `APROBADO` tras un ciclo. Detalle en [impl.md](impl.md) |
| 2026-10-29 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Cinco criterios `[M]` cumplidos. Suite ejecutada: 1138 pruebas de backend, `ruff`, `mypy`, `lint-imports`, `verificar_docs.py`, `zizmor` y 178 pruebas de `tools/` en verde. Dos ciclos de corrección de código (tres Mayores en el primero y un Mayor de pruebas que no discriminaban en el segundo) y tres de documentación. Cierre con una excepción del gate, a aceptar al archivar: la última reauditoría de documentación quedó en `REQUIERE CAMBIOS` por dos Menores que se aplicaron con el texto del auditor sin una cuarta reauditoría. Detalle en [impl.md](impl.md) |

## Decisiones registradas

Las de [TKT-009](../tkt-009/_index.md#decisiones-registradas), que valen para las cuatro partes. En esta: el verificador solo cuenta escenarios HDU, y la fase 2 y el retiro se marcan con la línea `fase 2` y el segmento ` · retirado por TKT-0NN`.
