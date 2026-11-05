# TKT-016 · Cálculo de la explosión por tipo de partida

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenario 14 (cantidad presupuestada y rendimiento congelado de la explosión) y escenario 15 (importe sugerido) |
| **Épica / sprint** | Sprint 2 · cálculo previo al congelado de la línea base (TKT-017) |
| **Puntos** | Talla S |
| **Reglas implicadas** | `RN-24`; supuestos `PA-01`, `PA-03` y `PA-23` (cerrado el 2026-11-03 con `ROUND_HALF_UP`). Produce el dato que consume `RN-03` |
| **Invariantes en riesgo** | Ninguno modificado. Produce datos para el 8 y el 19 de modelo de datos §13 y para la unicidad `(linea_base_id, tipo_partida_id, insumo_id)`. Regresión: reglas 1 y 2 de `CLAUDE.md` y lectores de TKT-013 y TKT-014b |
| **Módulos en alcance** | `presupuesto` |
| **Capas en alcance** | dominio. Sin aplicación, API, infraestructura ni frontend |
| **Depende de** | TKT-014b (ARCHIVADO) |
| **Rama** | `tkt-016a-…` y después `tkt-016b-…`, apilada a `Produccion` tras fusionar la a (las abre `/sdd-ejecutar`) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-03 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-03 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | 016a + 016b · 2026-11-05 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | TKT-016b · 2026-11-05 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-03 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must M1 a M5 validados por la persona dueña. Doce criterios `[M]`, dos de ellos de regresión; tres criterios de rechazo (`CA-6`, `CA-7` y `CA-9`) con seis escenarios. INVEST sin fallos y con dos reservas (V y T). Cuatro objeciones adversariales resueltas por la persona dueña |
| 2026-11-03 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): función pura `calcular_explosion` en `presupuesto/dominio/explosion.py` y dos cocientes con nombre en `tipos_base`. 13 filas (A0 a A8, B1 a B4), ~1,080 líneas (~300 de producción); condición de parada 3, se propone partir en TKT-016a y TKT-016b. `revisor-impacto`: sin frontera cruzada, `lint-imports` 15 contratos en verde; once omisiones de documentación incorporadas. Siete preguntas (P-1 a P-7) esperan a la persona dueña; B2 no se ejecuta sin `P-1` |
| 2026-11-03 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las respuestas a P-1 a P-7 (ver «Decisiones registradas»). Partición en TKT-016a (filas A0 a A8) y TKT-016b (B1 a B4), fusión a → b. Siguiente: `/sdd-ejecutar TKT-016` (entrega a, fila A0) |
| 2026-11-05 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | TKT-016a implementado en rama `tkt-016a-explosion-dominio`: `calcular_explosion`, cocientes, 29 tests, `PA-23` y ADR explosión. Pendiente TKT-016b y `/sdd-revisar` |
| 2026-11-05 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite 2017 passed; auditorías con REQUIERE CAMBIOS; ciclo 1 corrige F001 (sugerido por fila), F002/M-14 (test dos tipos), docs ADR/README. Menores abiertos (TC-10, aserciones laxas). A8 mutación parcial documentada. Siguiente: `/sdd-completar` |
| 2026-11-05 | `LISTO PARA PR` | `PENDIENTE FUSIÓN · TKT-016a` | `/sdd-completar` | `delta.md`, evolución; PR pendiente de apertura |
| 2026-11-05 | `PENDIENTE FUSIÓN · TKT-016a` | `LISTO PARA EJECUTAR · TKT-016b` | `/sdd-completar` | Entrega **TKT-016a** fusionada · [PR #47](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/47) · registro en comentario del PR. Siguiente: `/sdd-ejecutar TKT-016` (entrega b, filas B1–B4) |
| 2026-11-05 | `LISTO PARA EJECUTAR · TKT-016b` | `EN REVISIÓN · TKT-016b` | `/sdd-ejecutar` | Filas B1–B4: libro sintético TC-24/25, CA-10 TC-26/27, arranque-local, suite 2022 passed. Siguiente: `/sdd-revisar TKT-016` |
| 2026-11-05 | `EN REVISIÓN · TKT-016b` | `LISTO PARA PR · TKT-016b` | `/sdd-revisar` | 34 tests TKT-016; suite 2022 passed; auditorías APROBADO; ciclo 1 quitó pytest de soporte. Siguiente: `/sdd-completar TKT-016b` |
| 2026-11-05 | `LISTO PARA PR · TKT-016b` | `PENDIENTE FUSIÓN · TKT-016b` | `/sdd-completar` | `delta.md` 016b; PR pendiente |
| 2026-11-05 | `PENDIENTE FUSIÓN · TKT-016b` | `ARCHIVADO` | `/sdd-completar` | Entrega **TKT-016b** fusionada · [PR #48](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/48) · [registro](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/48#issuecomment-6666080506). Planificación del paraguas cerrada (#47 + #48). |

## Decisiones registradas

- 2026-11-03 · persona dueña: la ruta `GET /lineas-base/{linea_base_id}/explosion` es de TKT-017. TKT-016 es una regla pura del dominio, sin ruta ni persistencia.
- 2026-11-03 · persona dueña: el tipo de partida de cada concepto llega como dato de entrada; el mapeo desde el nombre de la partida (`PA-T8` de TKT-013) sigue abierto.
- 2026-11-03 · persona dueña: importe sugerido por tipo de partida = `Σ cantidad × (P.U. − cargo UTILIDAD − cargo INDIRECTOS)`, con el precio unitario y los cargos del análisis. El IVA no se resta.
- 2026-11-03 · persona dueña: rendimiento congelado y costo unitario de cada fila son promedios ponderados; el costo sale del análisis leído, no de `precio_insumo`.
- 2026-11-03 · persona dueña: la explosión solo incluye insumos `MATERIAL` (`PA-T6` sigue abierta).
- 2026-11-03 · persona dueña: `PA-23` se cierra con `ROUND_HALF_UP`.
- 2026-11-03 · persona dueña: pruebas con libro sintético en CI y reconciliación contra el archivo real `AP-058-25` con `skip` explícito.
- 2026-11-03 · persona dueña: rechazo todo o nada con todas las causas; se rechazan el cargo `UTILIDAD` o `INDIRECTOS` ausente, la cantidad o el rendimiento menores o iguales que cero, y la misma clave de insumo con dos unidades.
- 2026-11-03 · persona dueña: los hallazgos del borrador OpenAPI (`x-tickets` de `obtener_explosion_insumos` y el nombre `RenglonExplosion.importe_venta`, que vale un costo) los corrige TKT-017. El ticket no depende de ningún servicio externo de pago ni de claves de API.

- 2026-11-03 · persona dueña, preguntas del diseño: `P-1` opción A (el oráculo `AP-058-25` se lee de un CSV `clave,cantidad,importe` extraído a mano y guardado fuera del repositorio, al que apunta `CIMENTA_EXPLOSION_UNION`); `P-3` partir en TKT-016a (filas A0 a A8) y TKT-016b (B1 a B4) con fusión a → b; `P-2` sumar los renglones repetidos de `UTILIDAD` o `INDIRECTOS`; `P-4` escribir ADR-036; `P-5` ignorar el insumo `MATERIAL` sin unidad en el conflicto de unidades; `P-6` quitar `(asumido)` de `ROUND_HALF_UP` en `CLAUDE.md` y en `conv-dominio-python` en la fila A7; `P-7` editar el comentario de `test_tipos_base_redondeo.py` y dejar `dinero.ts` como residuo anotado. Diseño aprobado el mismo día.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- Asociar el nombre de una partida con un `tipo_partida` (`PA-T8`): sin él, TKT-017 no puede invocar el cálculo con datos reales.
- Incluir la mano de obra en la explosión cuando se resuelva el sentido de su rendimiento (`PA-T6` de TKT-014).
- En TKT-017: corregir `x-tickets` de `obtener_explosion_insumos` a `[TKT-017]` y renombrar `RenglonExplosion.importe_venta`, que vale cantidad × costo.
- Versionar fuera del repositorio, con su variable de entorno documentada en el arranque local, el archivo `AP-058-25 EXPLOSION DE INSUMOS` que sirve de oráculo.
