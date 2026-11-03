# Delta · TKT-014b · Asociación, libro completo y archivos reales

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-014b** del paraguas [TKT-014](_index.md). **TKT-014a** ya está en `Produccion` ([PR #38](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/38)). Con la fusión de este PR **cierra la planificación del paraguas TKT-014** (hub → `ARCHIVADO`).

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Asociación análisis↔catálogo e insumos por crear | `backend/cimenta/presupuesto/dominio/asociacion_analisis.py` | M5, M6 |
| Objetos de libro (`AnalisisDelLibro`, asociaciones, propuestas) | `backend/cimenta/presupuesto/dominio/analisis.py` | Contrato del lector completo |
| Causas de asociación e insumos | `backend/cimenta/presupuesto/dominio/catalogo.py` | Hallazgos crudos (TKT-015 traduce) |
| `leer_libro_presupuesto` / bytes (catálogo + APU + consolidación) | `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | Un solo paso openpyxl, CA-R3 |
| Pruebas TC-23…TC-39 | `test_tkt014_asociacion.py`, `test_tkt014_lector.py` | Sintético + openpyxl |
| Pruebas TC-40…TC-49 | `test_tkt014_archivos_reales.py` | ENITI + Union (`CIMENTA_CATALOGO_*`) |
| **ADR-035** clave por descripción, lectura por rótulos, cuadre por suma | `docs/adr/20261103-clave-de-insumo-y-lectura-de-apu.md` | Decisión de producto del importador |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Lectura post-viáticos (`cargosindirectos` / `cargosporcentuales`) | `lectura_analisis.py` | Encabezados de bloque no se leían como cargo (TC-47) |
| Lector de catálogo compartido con APU | `lector_catalogo.py` | Solo catálogo → libro presupuesto unificado |
| Soporte de pruebas (libro ENITI+APU, kwargs) | `soporte_tkt014.py` | Fixtures 014b |
| Conteo ADR (35) y deps TKT-015/016/017 → 014b | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/05`, `arranque-local` | Documentación alineada |
| Hub e impl SDD | `sdd/tickets/tkt-014/*` | Cierre 014b |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado |

## Comportamiento observable nuevo

**Ninguno en producción** (sin API ni pantalla). Internamente, el módulo `presupuesto` puede **leer un `.xlsx` de presupuesto completo**: catálogo TKT-013, cada hoja APU, asociar por código de concepto, proponer insumos por crear por clave normalizada y devolver hallazgos crudos — sin escribir en PostgreSQL. TKT-018 orquestará; TKT-015 clasificará errores; TKT-017 materializará.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / endpoints | Sin cambios | No |
| Esquema PostgreSQL | Sin cambios | No |
| Tipos generados frontend | Sin cambios | No |
| `CausaHallazgo` | +causas de asociación/conflicto de insumo | No (dominio interno) |
| Firma pública futura `leer_libro_presupuesto(contenido, insumos_existentes)` | Nueva en infraestructura | N/A hasta TKT-018 |

## Decisiones (ADR)

→ [ADR-035 · Clave de insumo y lectura de APU](../../../docs/adr/20261103-clave-de-insumo-y-lectura-de-apu.md) (MADR en índice).

**Evidencia:** 44 hojas medidas (E-1), 35 insumos distintos unión ENITI+Union (E-4), cuadre reconstruido vs pie (E-5 / TC-42).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Tras viáticos, rótulos `CARGOS INDIRECTOS` / `CARGOS PORCENTUALES` cierran bloque, no son filas de cargo | TC-47 hoja `01` ENITI | `lectura_analisis` |
| `git checkout` sobre paths no trackeados en Windows borra el working tree | Incidente 014b | Ramas: `git add` temprano |
| TC-38 «base intacta» se prueba mejor con AST del adaptador que con conteos DB | Revisión F002 | Pruebas de lectores in-memory |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | B4/B5 no deben marcarse en design sin mutación y suite en `impl.md` | Media |
| `documentación` | Design dice ADR-034 para APU; índice reservaba 034 → publicar como **ADR-035** | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Refactor menor `proponer_insumos` (F004) | No bloquea | Higiene futura |
| Normalización `M²` en insumos APU | Igual que catálogo TKT-013 | TKT-015 / producto |
| Imports privados `lectura_catalogo` ↔ `lectura_analisis` | Menor arquitectura | Ticket aparte |
| Códigos Union sin APU / mapa manual | `PA-T3` | Producto |
| `SIROC` como tipo de cargo | Fuera de alcance 014 | Ticket futuro (spec) |
| Sentido rendimiento mano de obra | `PA-T6` | TKT-016 |

## Pull request

**Título:** `TKT-014b · Asociación, lector de libro y archivos reales`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub.

**Fusión con omisión:** según procedimiento del orquestador tras aprobación explícita de la persona dueña.
