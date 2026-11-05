# TKT-072 · Concepto único por obra y sus apariciones por área

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 14 y 18 (qué copia la línea base y su inmutabilidad); resuelve `PA-T1` de TKT-013 |
| **Épica / sprint** | Sin sprint asignado ni puntos de historia; previo a TKT-017 |
| **Puntos** | Talla M |
| **Reglas implicadas** | Ninguna `RN-xx` propia. Invariantes 8, 13, 14 y 27, y un invariante nuevo para la unicidad de concepto y partida; `RN-01` y `PA-01` como consumidores |
| **Invariantes en riesgo** | 13 (se conserva, aplicado solo al concepto), 8 (se reparte entre concepto y aparición), 14 (la copia cambia de referencia), 27; permisos por rol |
| **Módulos en alcance** | `presupuesto` |
| **Capas en alcance** | infraestructura (esquema y migración) y documentación. Sin dominio, aplicación, API ni frontend |
| **Depende de** | TKT-011b (ARCHIVADO), TKT-015b (ARCHIVADO) |
| **Rama** | `tkt-072-concepto-de-partida` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-05 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-05 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-11-05 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-05 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-05 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M6 validados por la persona dueña. Doce criterios `[M]`, tres de ellos de regresión; seis con escenarios de rechazo (`CA-2`, `CA-4`, `CA-5`, `CA-6`, `CA-7` y `CA-8`). Medidos los dos Excel reales: ningún código se repite dentro de una partida ni de un área; en ENITI, `620040-A` tiene dos precios. INVEST sin fallos y con dos reservas (N y V). Cuatro objeciones adversariales, dos resueltas por la persona dueña |
| 2026-11-05 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): migración `0010` con `partida_concepto`, renombrado de `linea_base_concepto.concepto_id` y guardas con bloqueo en las dos direcciones. Siete filas (A0 a A6), ~1,225 líneas (~165 de producción); se propone no partir. `revisor-impacto`: completo, sin frontera cruzada (`lint-imports`, 16 contratos en verde); cinco omisiones menores incorporadas. Seis preguntas (P-1 a P-6) esperan a la persona dueña |
| 2026-11-05 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las respuestas a P-1 a P-6 (ver «Decisiones registradas»); spec ajustada en el mismo acto (`M4`, `CA-5`, `CA-8`, `PA-T72.7`). Un solo ticket. Siguiente: `/sdd-ejecutar TKT-072` (fila A0) |
| 2026-11-05 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Migración `0010`, fábricas, 34 pruebas TKT-072, regresión TKT-011, documentación y ADR. Suite: 2051 passed, 26 skipped. Mutación M-1…M-11 y auditorías formales pendientes en `/sdd-revisar` |
| 2026-11-05 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite 2051 passed; mutación M-1,M-3,M-4,M-5,M-11,M-12 verificada; auditorías arquitectura/SQL/docs APROBADO. Menor: sin rojo TDD archivado; M-2,M-6–M-10 sin spot-check |
| 2026-11-05 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | `delta.md`, evolución; PR abierto; espera CI y aprobación de fusión |
| 2026-11-05 | `PENDIENTE FUSIÓN` | `ARCHIVADO` | `/sdd-completar` | PR [#50](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/50) fusionado; planificación archivada. Registro: [#6670630517](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/50#issuecomment-6670630517) |

## Decisiones registradas

- 2026-11-05 · persona dueña: `PA-T1` de TKT-013 se resuelve separando el concepto único por obra de sus apariciones, en un ticket propio (este) previo a TKT-017.
- 2026-11-05 · persona dueña: el concepto lleva código, descripción y unidad; la aparición, cantidad, precio unitario e importe, porque en ENITI `620040-A` tiene dos precios según el área.
- 2026-11-05 · persona dueña: la aparición se llama `partida_concepto` y su término de glosario es *concepto de partida*.
- 2026-11-05 · persona dueña: `linea_base_concepto` apunta a la aparición, para conservar el área que necesita TKT-047.
- 2026-11-05 · persona dueña: `UNIQUE (concepto, partida)` en el motor, registrado como invariante nuevo de §13 (el número 39 al crearlo), con los conteos de invariantes al día en `CLAUDE.md`, `README.md` y `llms.txt`.
- 2026-11-05 · persona dueña: la aparición no lleva `obra_id`; `UNIQUE (apu.concepto_id)` sigue fuera.
- 2026-11-05 · persona dueña: la subida de la migración se niega si hay filas en `concepto` o en `linea_base_concepto`, y la bajada, si hay filas en `partida_concepto`.
- 2026-11-05 · persona dueña: el ticket no depende de ningún servicio externo de pago ni de claves de API.

- 2026-11-05 · persona dueña, preguntas del diseño: `P-1` la guarda de bajada cuenta también `concepto` (spec ajustada: `M4`, `CA-8`, `PA-T72.7`); `P-2` `CA-5` espera `23001`, no `23503` (spec ajustada); `P-3` y `P-4` el conteo de invariantes pasa a 39 también en metodología, propuesta del toolkit, `docs/06`, agentes, skills y `.cursor/agents` regenerado, y `tools/publicar_revision.py` acepta citas hasta el 39, todo en la fila A4; `P-5` un solo ticket sin partir; `P-6` `TC-48`, `TC-49` y `CA-19` esc. 3 de TKT-011 bajan desde una base en `0009`. Diseño aprobado el mismo día.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- `UNIQUE (apu.concepto_id)` y la coherencia de `concepto.obra_id` en el motor (`PA-T3` de TKT-011), ahora que el concepto es único por obra.
- En TKT-018: decidir si el escenario 5 de HDU-001 y `ResumenImportacion.conceptos` cuentan conceptos únicos o apariciones.
- Comprobar en el entorno `test` de la VPS que `concepto` y `linea_base_concepto` están vacías antes de desplegar la migración (`PA-T72.8`).
