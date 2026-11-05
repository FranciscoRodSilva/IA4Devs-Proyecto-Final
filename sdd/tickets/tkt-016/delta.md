# Delta · TKT-016a · Regla pura de explosión por tipo de partida

> [← index](_index.md) | [← impl](impl.md)

Entrega **intermedia** del paraguas TKT-016. Pendiente **TKT-016b** (`M5`, `CA-8`, `CA-10`: libro sintético y reconciliación `AP-058-25`). El hub **no** se archiva hasta fusionar 016b.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| `calcular_explosion` y objetos de valor (entrada, salida, rechazo) | `backend/cimenta/presupuesto/dominio/explosion.py` | Implementar `RN-24`, `PA-01`, `PA-03`; datos que consumirá TKT-017 |
| `cociente_rendimiento`, `cociente_precio_unitario` | `backend/tipos_base/numericos.py` | Promedios ponderados sin mezclar `Cantidad/Cantidad` con `Rendimiento` |
| Ayudantes de prueba | `backend/herramientas/soporte_tkt016.py` | Construir `ConceptoLeido` / `AnalisisLeido` en memoria |
| 31 tests de dominio | `backend/tests/test_tkt016_*.py` | TC-01–TC-23 de la parte a |
| ADR explosión por tipo de partida | `docs/adr/20261103-explosion-por-tipo-de-partida.md` | Promedio ponderado, P.U. del análisis, rechazo todo-o-nada |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Redondeo documentado | `CLAUDE.md`, PRD, arquitectura §7.4, ADR-020, `conv-dominio-python` | `ROUND_HALF_UP (asumido)` → **`PA-23` cerrada** (2026-11-03) |
| Cocientes en arquitectura §7.4 | `docs/02-arquitectura.md` | Solo operadores → **+ dos funciones con nombre** |
| Fórmula sugerido y promedios | `docs/03-modelo-datos.md` | Texto genérico → fórmula explícita y enlace al ADR de explosión |
| Partición 016a/016b | `docs/05-tickets-trabajo.md` | Nota de entrega hermana |
| Conteos ADR / preguntas | `README.md`, `llms.txt`, `CLAUDE.md` | 37 → **38 ADR**; `PA-23` en respondidas; **3** preguntas abiertas |

## Eliminado

Ninguno.

## Comportamiento observable nuevo

Ninguno en esta entrega: no hay API ni pantalla. TKT-017 expondrá la explosión al congelar la línea base.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `tipos_base` exporta dos funciones nuevas | Sí, aditivo | No |
| OpenAPI / esquema PostgreSQL | Sin cambio | No |

## Decisiones (ADR)

→ [20261103-explosion-por-tipo-de-partida.md](../../../docs/adr/20261103-explosion-por-tipo-de-partida.md) (índice ADR). Opciones: detalle por concepto vs promedio ponderado; P.U. catálogo vs análisis; cargos ausentes como cero vs rechazo.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Excluir tipos del sugerido por **`fila`**, no por `codigo_concepto` | Códigos repetidos en catálogos reales y en libro sintético 016b | Cualquier agregación por tipo con rechazo parcial |
| Test de agregación debe usar **dos `tipo_partida_id`** | Mutante M-14 sobrevivía con solo MUROS | Reglas `PA-01` |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | A8 mutación M-1…M-15 no barrida completa; design marcado ⚠ con M-4, M-10, M-14 cubiertos | Media |
| `documentación` | P-4 del diseño decía «ADR-036» pero **036** ya es preparación JSONB (TKT-015a); el ADR de explosión va por **fecha/slug**, no reutilizar ordinal | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `M5`, libro sintético, oráculo Union | Partición P-3 | **TKT-016b** |
| Barrido mutantes M-1…M-13, M-15 restantes | A8 ⚠ | Cerrar en 016b o antes de fusionar 016b |
| Hallazgos menores de código (TC-10, aserciones laxas) | No bloquean 016a | Opcional en 016b |
| `frontend/.../dinero.ts` cita `PA-T5` | Residuo P-7 | Anotado |
| Mapeo partida → `tipo_partida` | `PA-T8` | Ticket futuro del hub |

## Pull request

**Título:** `TKT-016a · Regla pura de explosión por tipo de partida`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub tras apertura.
