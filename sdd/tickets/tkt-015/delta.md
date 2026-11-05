# Delta · TKT-015a · Clasificación, preparación jsonb y análisis síncrono

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-015a** del paraguas [TKT-015](_index.md). **TKT-015b** (ejecutor en proceso aparte, latido, barrido reutilizable) queda pendiente; el hub **no** se archiva hasta fusionar la b.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Siete tipos de error, estados y `ErrorImportacion` | `backend/cimenta/presupuesto/dominio/importacion.py` | M1, M2, contrato interno TKT-015 |
| Mapa 22 causas → 7 tipos, duplicados, SIN_APU, `clasificar_libro` | `backend/cimenta/presupuesto/dominio/clasificacion_importacion.py` | M1, esc. 6–9 HDU-001 |
| Preparación serializable (conceptos, insumos, dinero en cadena) | `backend/cimenta/presupuesto/dominio/preparacion_importacion.py` | M4 |
| Casos de uso `iniciar_analisis`, `analizar_contenido`, `registrar_resultado`, `interrumpir` | `backend/cimenta/presupuesto/aplicacion/analisis_importacion.py` | M2, M5–M7 (síncrono en fase a) |
| Tablas ORM `importacion` / `importacion_error`, JSON preparación | `backend/cimenta/presupuesto/infraestructura/tablas.py`, `preparacion_json.py` | Persistencia |
| Repositorio con `FOR UPDATE`, errores, contadores | `backend/cimenta/presupuesto/infraestructura/repositorio_importacion.py` | M3, concurrencia |
| Adaptador síncrono sobre lector TKT-014 | `backend/cimenta/presupuesto/infraestructura/trabajo_analisis.py` | Orquestación in-process |
| Migración `v0009` columna `preparacion jsonb` + `CHECK` | `backend/migraciones/versions/v0009_presupuesto_preparacion_de_importacion.py` | M4, ADR-036 |
| Pruebas TC-01…TC-42 + mutantes M-01…M-12 | `backend/tests/test_tkt015_*.py` (8 módulos) | Criterios Must y archivos reales |
| Soporte y mutación | `backend/herramientas/soporte_tkt015.py`, `ejecutar_mutantes_tkt015a.py` | TDD y CAR2 |
| **ADR-036** preparación en jsonb | `docs/adr/20261105-preparacion-de-importacion-en-jsonb.md` | Decisión de persistencia |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Modelo §11 `preparacion`, formato 1 | `docs/03-modelo-datos.md` | Sin columna → jsonb documentado |
| Partición TKT-015a/b, deps TKT-017 → 015b | `docs/05-tickets-trabajo.md`, historias HDU-001 esc. 4–9 | Documentación alineada |
| Conteo **36 ADR** | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/02-arquitectura.md` | +ADR-036 |
| Esquema nulabilidad `importacion.preparacion` | `backend/tests/test_tkt011_*.py` | Refleja v0009 |
| Hub, impl, design SDD | `sdd/tickets/tkt-015/*` | Cierre entrega a |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado |

## Comportamiento observable nuevo

**Ninguno en producción** (sin rutas HTTP ni pantalla en esta entrega). Internamente, el módulo `presupuesto` puede **analizar un `.xlsx` ya subido**: clasificar hallazgos en los siete tipos, persistir errores fila a fila, guardar preparación jsonb cuando hay filas válidas, y dejar la importación en `VALIDADO` o `CON_ERRORES`. Union Square se reporta celda a celda (`#REF!`), no en bloque. TKT-015b añadirá ejecución fuera del API; TKT-018 expondrá las rutas.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / endpoints | Sin cambios en este PR | No |
| Esquema PostgreSQL | `importacion.preparacion jsonb`, `CHECK` formato 1 | No (columna nueva, migración) |
| Tipos generados frontend | Sin cambios | No |
| `importacion_error.tipo` | Sigue en los siete valores del CHECK | No |

## Decisiones (ADR)

→ [ADR-036 · Preparación de importación en jsonb](../../../docs/adr/20261105-preparacion-de-importacion-en-jsonb.md).

**Evidencia:** E-3 ~225 bytes/concepto sintético; TC-40 Union 8 639 errores persistidos; TC-41 ENITI seis `CODIGO_EN_VARIAS_HOJAS`; mutación 12/12 en rojo.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `sqlalchemy.null()` en `UPDATE` evita JSON `null` con estado `ANALIZANDO` | impl A6 | Repositorios jsonb |
| `hallazgo_ejemplo` compartido evita drift entre suites de clasificación | Revisión F001 | `herramientas/soporte_tkt*.py` |
| Precedencia en `_filas_y_hojas_rechazadas` afecta qué filas entran en preparación | Mutante / auditoría | Dominio clasificación |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `guardrail` | `historias_activas.txt` se corrompió (Latin-1) durante una prueba de revisión; conviene no tocar el archivo salvo para añadir historias | Media |
| `comando` | Partición a/b: la entrega a cierra con hub vivo; estados `LISTO PARA PR · TKT-015a` funcionaron | Baja |
| `herramienta` | Archivos reales PA-T3 omitidos en CI; verificación local con rutas del cliente cierra el hueco | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Ejecutor en proceso aparte, latido, barrido arranque, progreso | Entrega b del diseño | **TKT-015b** |
| Rutas HTTP de importación, CSRF, permisos | Fuera de alcance 015a | **TKT-018** |
| `55P03` → `409 CONCURRENCIA` en manejadores | Anotado en impl A6 | **TKT-018** |
| Materializar línea base desde preparación | Depende de 015b + 017 | **TKT-017** |
| `PA-T1` código repetido misma descripción vs UNIQUE | Abierto desde TKT-013 | Producto / TKT-017 |
| CHECK `RECIBIDO` parametrizado (opcional sql) | Menor auditoría sql | Higiene futura |

## Pull request

**Título:** `TKT-015a · Clasificación, preparación jsonb y análisis síncrono`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub.

**Fusión con omisión:** según procedimiento del orquestador tras aprobación explícita.
