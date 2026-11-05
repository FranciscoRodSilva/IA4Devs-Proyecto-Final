# TKT-015 · Validaciones y reporte de errores por fila

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · TKT-015b

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 4 a 9 y 27 (la clasificación en tipos de error y el estado de la importación). `RENDIMIENTO_AUSENTE` y `PROCESO_INTERRUMPIDO` no tienen escenario (`PA-15.11`) |
| **Épica / sprint** | Sprint 2 · cuarto ticket del análisis de la importación (TKT-013 a TKT-015) |
| **Puntos** | Talla M; el diseño evalúa partirlo en TKT-015a y TKT-015b |
| **Reglas implicadas** | Ninguna `RN-xx` gobierna la clasificación. `RNF-17`, `RNF-06`; `RN-01` por omisión; regla 1 de `CLAUDE.md` |
| **Invariantes en riesgo** | Ninguno modificado. Regresión: reglas 1 a 3 de `CLAUDE.md`, resultado de los lectores de TKT-013 y TKT-014. Roza el invariante 13 (`PA-T1`, sin resolver) |
| **Módulos en alcance** | `presupuesto`; el mecanismo de barrido y `servidor/` para el arranque |
| **Capas en alcance** | dominio · aplicación · infraestructura. Sin API ni frontend |
| **Depende de** | TKT-014b (ARCHIVADO), TKT-011b (tablas `importacion` e `importacion_error`) |
| **Rama** | `tkt-015a-…` y después `tkt-015b-…`, apilada a `Produccion` tras fusionar la a (las abre `/sdd-ejecutar`) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-03 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-03 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | TKT-015a filas A-pre–A9 cerradas (2026-11-05) |
| Delta | [delta.md](delta.md) | `/sdd-completar` | TKT-015a (2026-11-05) |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-03 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M7 y Should S1 validados por la persona dueña. 22 criterios: 18 `[M]`, uno `[S]` y tres de regresión; doce de rechazo (CA-2 a CA-10, CA-14, CA-16 y CA-18). Medidos los hallazgos reales de los dos archivos. INVEST sin fallos y con dos reservas (E y S). Cinco objeciones adversariales incorporadas |
| 2026-11-03 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus). Condición de parada 3: ~2,960 líneas; se propone partir en TKT-015a (clasificación, preparación, migración `0009` y caso de uso síncrono, ~1,660) y TKT-015b (ejecutor en proceso aparte, latido, barrido reutilizable en `trabajos/` y arranque, ~1,300), con fusión a → b. `revisor-impacto`: sin frontera cruzada, diseño incompleto; nueve omisiones incorporadas, entre ellas un choque de P11 con tres tests de servidor real (P16). Dos objeciones del orquestador: tres causas pasan de `SIN_CONCEPTOS` a `REF_ROTA` y la partición en tres sigue como alternativa. Dieciséis preguntas (P1 a P16) esperan a la persona dueña; los experimentos E-1 a E-10 quedan `(sin ejecutar)` hasta A0 y B0 |
| 2026-11-03 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones del arquitecto en P1 a P16. Spec ajustada en el mismo acto: sección «Partición en dos entregas» y `PA-15.1`, `PA-15.2`, `PA-15.11` y `PA-15.12` resueltas. Siguiente: `/sdd-ejecutar TKT-015` (entrega a) |
| 2026-11-03 | `LISTO PARA EJECUTAR` | `LISTO PARA EJECUTAR` | persona dueña | Aprobación del diseño revisado, con P17 incluida (el progreso se cuantiza con `ROUND_DOWN`, excepción `(asumido)` a la regla 1) y la partición a/b con las cifras finales: 21 filas, unas 3,170 líneas (~1,790 en a y ~1,380 en b). Siguiente: `/sdd-ejecutar TKT-015` (entrega a, fila A-pre) |
| 2026-11-05 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` (A9) | TKT-015a cerrado en ejecución: mutantes M-01…M-12, ADR-036, suite 81+5 skip, CAR2 en verde. Siguiente: `/sdd-revisar TKT-015a` |
| 2026-11-05 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` (TKT-015a) | Auditorías + ciclo de corrección; veredicto en `impl.md`. Siguiente: `/sdd-completar TKT-015a` |
| 2026-11-05 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` (TKT-015a) | `delta.md`, PR abierto; archivos reales verificados localmente (5/5). Siguiente: fusión tras aprobación |
| 2026-11-05 | `PENDIENTE FUSIÓN` | `LISTO PARA EJECUTAR · TKT-015b` | fusión PR #44 | Entrega a en `Produccion`. Siguiente: `/sdd-ejecutar TKT-015b` |

## Decisiones registradas

- 2026-11-03 · persona dueña: TKT-015 no expone rutas. Entrega la clasificación, el caso de uso de análisis, el trabajo en proceso aparte con latido y progreso, y el barrido de arranque reutilizable. Las tres rutas del OpenAPI que también citan a TKT-015 las implementa TKT-018, que ya las declara suyas.
- 2026-11-03 · persona dueña: `DUPLICADO` se detecta al pie de la letra del esc. 9 de HDU-001: el mismo código con descripción normalizada distinta, señalando las filas en conflicto. El mismo código con la misma descripción en varias áreas no es error en este ticket. `PA-T1` de TKT-013 sigue abierta para TKT-017.
- 2026-11-03 · persona dueña: las 18 causas crudas sin tipo propio se persisten en el tipo más cercano de los siete, con la causa cruda en el `mensaje`; las estructurales (hoja o encabezado no localizado) van como `SIN_CONCEPTOS`. El mapa causa por causa lo propone el diseño y ella lo aprueba. No se amplía el CHECK.
- 2026-11-03 · persona dueña: el resultado válido del análisis se persiste en este ticket como preparación. El mecanismo lo decide el diseño y puede traer migración y ADR.
- 2026-11-03 · persona dueña: validado el Must M1 a M7 y el Should S1 tal como se propusieron. El ticket no depende de ningún servicio externo de pago ni de claves de API.
- 2026-11-03 · orquestador: el `resumen` de previsualización sale del Should y pasa a TKT-018 (`PA-15.10`), porque su campo `por_tipo_partida` depende de `PA-T8`. Se avisa a la persona dueña en el reporte de cierre.

- 2026-11-03 · persona dueña: aprobadas P1 a P16 del diseño. Partir en TKT-015a y TKT-015b con fusión a → b (la alternativa de tres entregas queda descartada). Mapa de las 22 causas con la corrección del orquestador: `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` van a `REF_ROTA`, y `SIN_CONCEPTOS` queda para las cinco causas de hoja. `SIN_APU` y `DUPLICADO` rechazan todas las filas del código. Preparación en la columna `importacion.preparacion jsonb` (migración `0009`, ADR-036). Latido escrito por el proceso del API, cada 5 s, con vencimiento a 60 s configurables. `progreso` queda en 1 al terminar y se corrige `docs/03`. Un error por celda.
- 2026-11-03 · persona dueña: aprobada la excepción del `lifespan` `async def` a la regla 11 (solo delega a `run_in_threadpool`), el paquete `trabajos/` fuera de `cimenta/` con la edición de «Estructura del backend» de `CLAUDE.md` en la entrega b, y los escenarios 28 y 29 de HDU-001 en un cambio de documentación aparte antes de la fila A1. No se añade tiempo máximo por análisis (P12).
- 2026-11-03 · persona dueña: barrido y ejecutor solo arrancan con la base configurada; sin ella se omiten con el aviso `trabajos_omitidos`, y con ella un fallo del barrido impide arrancar (P16 y P11). Conserva el invariante de TKT-006 CA-R4.
- 2026-11-03 · persona dueña: aprobada P17. El progreso del análisis se cuantiza con `ROUND_DOWN` a mano, fuera de `Porcentaje.cuantizar()`, como excepción `(asumido)` a la regla 1: no es dinero, y redondear hacia arriba un trabajo sin terminar sería mentir.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- Resolver los códigos repetidos con descripción igual dentro de una obra (`PA-T1` de TKT-013): cambia el invariante 13 o el modelo de `concepto`. Previo a TKT-017; sin eso ninguno de los dos archivos reales se puede confirmar.
- Escenarios 28 y 29 de HDU-001 para `RENDIMIENTO_AUSENTE` y `PROCESO_INTERRUMPIDO` (`PA-15.11`).
- Asociar el nombre de una partida con un `tipo_partida` (`PA-T8`, `ENCHAPES Y PINTURAS`): previo al `resumen` de TKT-018.
- Un tiempo máximo por análisis que termine al trabajador colgado con `terminate_workers()`, que sube el mínimo de Python a 3.14 (P12): un análisis colgado mantiene su latido mientras viva el API.
- Un octavo tipo de `importacion_error` para los errores de formato que hoy se mapean al tipo más cercano, si la lectura del Director de Proyectos resulta confusa.
