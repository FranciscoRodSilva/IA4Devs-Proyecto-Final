# Delta · TKT-016b · Libro sintético y reconciliación Union

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-016b** del paraguas [TKT-016](_index.md). **TKT-016a** ya está en `Produccion` ([PR #47](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/47): regla `calcular_explosion`, cocientes, ADR explosión, `PA-23`). Con la fusión de este PR **cierra la planificación del paraguas TKT-016** (hub → `ARCHIVADO`).

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Libro sintético CA-8 y emparejamiento catálogo↔APU | `backend/herramientas/soporte_tkt016.py` | `M5`, TC-24/25 |
| Lectura CSV oráculo AP-058-25 | `leer_oraculo_explosion_union` en soporte | `CA-10` (P-1 opción A) |
| Pruebas libro sintético | `backend/tests/test_tkt016_libro_sintetico.py` | TC-24, TC-25 |
| Pruebas reconciliación real | `backend/tests/test_tkt016_archivo_real.py` | TC-26, TC-27 |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Soporte TKT-016 | `soporte_tkt016.py` | Solo ayudantes manuales → **+ libro, `conceptos_a_explotar`, oráculo** |
| Arranque local | `docs/arranque-local.md` | **+ `CIMENTA_EXPLOSION_UNION`** y formato CSV |
| Hub, design, impl SDD | `sdd/tickets/tkt-016/*` | Cierre 016b |

## Eliminado

Ninguno.

## Comportamiento observable nuevo

Ninguno en producción (sin API). El paraguas TKT-016 deja en el repo la **regla pura** de explosión (016a) y **evidencia automatizada**: libro sintético que recorre lectores TKT-013/014b y reconciliación opcional contra Union cuando existan variables y asociaciones (`PA-T3`).

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / esquema | Sin cambio | No |
| `tipos_base` / dominio en este PR | Sin cambio (016a ya fusionada) | No |

## Decisiones (ADR)

Sin ADR nuevo en 016b. Sigue vigente [explosión por tipo de partida](../../../docs/adr/20261103-explosion-por-tipo-de-partida.md) (016a).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `pytest.skip` en **`tests/`**, no en `herramientas/` | Revisión 016b quitó import de `pytest` del soporte | Cualquier helper de oráculo/archivo real |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `guardrail` | Importar `pytest` en `herramientas/soporte_*` pasó en ejecución; la revisión lo corrigió antes del PR | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| TC-26 en verde contra Union real | `PA-T3` (cero asociaciones) + oráculo fuera del repo | Ticket futuro / resolver `PA-T8`+`PA-T3` |
| Mutación A8 parcial, menores TC-10 | Heredado 016a | Opcional |
| `dinero.ts` / `PA-T5` | P-7 | Anotado |
| Mapeo partida → `tipo_partida` | `PA-T8` | Hub «tickets futuros» |

## Pull request

**PR:** [#48](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/48) (fusionado el 2026-11-05)
**Origen:** `agent+human-review`
**Registro:** [comentario de fusión](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/48#issuecomment-6666080506)
