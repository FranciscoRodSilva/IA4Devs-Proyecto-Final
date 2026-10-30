# TKT-062a · Etiqueta de origen obligatoria

> Hub del ticket. Se lee **primero**, siempre. Es la primera de las dos partes de [TKT-062](../tkt-062/_index.md).

## Estado

LISTO PARA PR

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla S; unas 490 líneas según el diseño común (≈ 170 de flujo, script y configuración y ≈ 320 de pruebas) |
| **Reglas implicadas** | `RNF-07` por la ausencia de secretos en el flujo de etiqueta; `CLAUDE.md` («Cómo se trabaja»: etiqueta de origen); convenciones §6 y §11. Ninguna `RN-xx` |
| **Invariantes en riesgo** | Ninguna tabla. De proceso: `comprobar_tc13`, `comprobar_tc21`, `comprobar_tc22` y `test_tc18_ningun_workflow_declara_secrets` de TKT-009, y los cuatro apartados de Dependabot. Regresión `CA-R1`, `CA-R2` y `CA-R4` |
| **Módulos en alcance** | `.github/workflows/etiqueta-origen.yml`, `.github/dependabot.yml`, `tools/etiqueta_origen.py`, `tools/tests/test_definicion_etiqueta.py` y `test_definicion_ci.py`, y la documentación de las etiquetas. Ningún archivo de `backend/` ni de `frontend/` |
| **Capas en alcance** | Entrega continua. Ninguna capa de la aplicación |
| **Depende de** | TKT-009 (ARCHIVADO) |
| **Bloquea a** | TKT-062b |
| **Rama** | `tkt-062a-etiqueta-origen` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Repartida de la spec común el 2026-10-29 |
| Design | [design.md común](../tkt-062/design.md), filas A0 a A8 | `/sdd-disenar` | Aprobado el 2026-10-29 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-30 |
| Delta | `delta.md` | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-29 | — | `LISTO PARA EJECUTAR` | partición de TKT-062 | Nace del gate de diseño de TKT-062, aprobado por la persona responsable del proyecto. Spec repartida: M5, su parte de M8 y de M11; `CA-6`, su parte de `CA-9` y `CA-12`, `CA-R1`, `CA-R2` y `CA-R4`. Primera parte en fusionar |
| 2026-10-30 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Filas A0 a A8 hechas: ciclo TDD en A2, A3, A4 y A7, ajustes del repositorio de A5 aplicados y verificados, ensayo A6 (rondas R0a y R1) con el PR #20 cerrado sin fusionar. 389 pruebas de `tools/` en verde, 48 nuevas. `auditor-arquitectura` `APROBADO` tras tres ciclos (F001 a F003 y F008, Menores). Pendientes para `/sdd-revisar`: las auditorías de código, seguridad y documentación, `CA-6` esc. 5 en vivo y la segunda mitad de `CA-R4`. Detalle en [impl.md](impl.md) |
| 2026-10-30 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite ejecutada por el orquestador: 398 pruebas de `tools/`, `verificar_docs.py`, `verificar_escenarios.py`, `zizmor`, `lint-imports`, Vale y markdownlint en verde. Cuatro auditorías `APROBADO` (arquitectura en 3 ciclos, código en 2, seguridad en 1, documentación en 3; SQL no aplica). Hallazgos: F101 (Mayor) y F102 a F107 de código, F201 y F202 de seguridad, F301, F302 y F401 (Mayores) y F303 a F305, F402 y F403 de documentación, todos resueltos. D-2 pasó a [ADR-027](../../../docs/adr/20261030-proteccion-de-produccion-y-fusion-con-omision.md) y la revisión por IA de 062b a ADR-028. **Condición para `/sdd-completar`:** el PR real debe mostrar los nueve trabajos de `ci.yml` y «Etiqueta de origen» en verde (`CA-R4`); `CA-6` esc. 5 se observa con el primer PR de Dependabot tras fusionar. Detalle en [impl.md](impl.md) |

## Decisiones registradas

Las de [TKT-062](../tkt-062/_index.md#decisiones-registradas), que valen para las dos partes. En esta parte:

- **La protección de `Produccion` se aplica aquí**, con `enforce_admins: false` y una aprobación requerida (`D-2`). El PR de esta parte es el primero que se fusiona con la omisión de la protección, y su comentario de fusión es el modelo de los siguientes.
- **Todo cambio a `Produccion` entra por PR** desde la fusión de esta parte, cierres de ticket incluidos.

## Tickets futuros sugeridos

Los del [paraguas](../tkt-062/_index.md#tickets-futuros-sugeridos).
