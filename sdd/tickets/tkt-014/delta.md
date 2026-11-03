# Delta · TKT-014a · Dominio de la hoja de APU

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-014a** del paraguas [TKT-014](_index.md). **TKT-014b** (asociación, adaptador, reales, ADR-034) queda pendiente; el ticket paraguas no se archiva hasta cerrar las dos.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Objetos de la hoja (`AnalisisLeido`, insumos, cargos, totales) | `backend/cimenta/presupuesto/dominio/analisis.py` | Contrato in-memory de un APU leído |
| Lector por rótulos (`analizar_hoja_apu`, cuadre ±0.01) | `backend/cimenta/presupuesto/dominio/lectura_analisis.py` | M1–M4, M7, M8, S1 sobre filas en memoria |
| Causas `VALOR_NEGATIVO`, `FECHA_NO_RECONOCIDA`, `CARGO_DESCONOCIDO`, `PU_NO_CUADRA`, `PU_NO_VERIFICABLE` | `backend/cimenta/presupuesto/dominio/catalogo.py` | Hallazgos crudos del APU (TKT-015 traduce después) |
| `interpretar_numero` para `Rendimiento` y `Porcentaje` | `lectura_catalogo.py` | Cargos e insumos con precisión exacta |
| Fixture de hoja sintética (disposición E-1) | `backend/herramientas/soporte_tkt014.py` | 44 tests de dominio sin openpyxl |
| Pruebas TC-01–TC-22 (dominio) | `backend/tests/test_tkt014_hoja.py` | Criterios 014a y regresión TKT-013 dominio |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Ficha TKT-014 y dependencias TKT-015/016 | `docs/05-tickets-trabajo.md` | Partición 014a/014b; criterios ±0.01, insumos por crear en 017; deps → TKT-014b |
| Diseño E-1/E-2 y tabla sintética | `sdd/tickets/tkt-014/design.md` | Columnas cargos D/E/G; viáticos reales; pie fila 21 |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado |

## Comportamiento observable nuevo

**Ninguno en producción.** No hay API ni pantalla. El backend gana capacidad interna de **interpretar una hoja de APU en memoria** (tuplas fila/columna): bloques material/mano de obra/cargos/viáticos, hallazgos crudos y verificación del precio unitario del pie contra totales reconstruidos (±0.01). Lo consumirá TKT-014b al abrir libros Excel.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / endpoints | Sin cambios | No |
| Esquema PostgreSQL | Sin cambios | No |
| Tipos generados frontend | Sin cambios | No |
| `CausaHallazgo` (dominio presupuesto) | +5 variantes | No (solo ampliación del enum interno) |

## Decisiones (ADR)

Ninguna ADR nueva en 014a. ADR-034 queda para **TKT-014b** (clave de insumo por descripción).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| El rótulo real de viáticos es `CARGOS VIATICOS Y HOSPEDAJE`, no `startswith("viaticos")` | E-2 en 44 hojas; 8 tests caen si se revierte | Lectura APU y fixtures |
| Pie `PRECIO UNITARIO` en columna D, valor en G | E-1 44/44 | `lectura_analisis._buscar_material_y_pie` |
| Cargos: porcentaje D, base E, importe G (F vacía) | E-1 | Bloque CARGOS |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | TKT-014a requirió 3 ciclos de `/sdd-revisar`: mutación/E-2, viáticos vs fixture, tests de cabecera F012 | Media |
| `comando` | TC-11 de subtotales debe insertarlos **antes** del pie, no después | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Asociación análisis↔concepto, insumos por crear, `leer_libro_presupuesto` | Alcance 014b | **TKT-014b** |
| Imports privados entre `lectura_analisis` y `lectura_catalogo` | Menor | Higiene en 014b o ticket aparte |
| Normalización `M²`→`M2` en insumos APU | Misma regla que catálogo TKT-013 | Decisión producto / TKT-015 |
| ADR-034 y docs CLAUDE/README (34 ADR) | 014b | **TKT-014b** |
| TC-47 cuadre 44 hojas reales | Requiere adaptador | **TKT-014b** |

## Pull request

**Título:** `TKT-014a · Dominio de la hoja de APU`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub.

**Fusión con omisión:** según procedimiento del orquestador tras aprobación explícita de la persona dueña.
