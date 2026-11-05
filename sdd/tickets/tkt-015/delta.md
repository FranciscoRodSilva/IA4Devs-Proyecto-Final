# Delta · TKT-015b · Ejecutor, latido, barrido y arranque

> [← index](_index.md) | [← impl](impl.md)

Entrega hermana **TKT-015b** del paraguas [TKT-015](_index.md). Con su fusión cierra el paraguas entero (TKT-015a ya está en `Produccion`).

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Barrido genérico reutilizable | `backend/trabajos/barrido.py` | M7, TKT-059 |
| Contrato `trabajos-solo-sqlalchemy` | `backend/pyproject.toml`, suites de fronteras | Regla 3, ADR-037 |
| Barrido de importaciones interrumpidas | `backend/cimenta/presupuesto/aplicacion/barrido_importacion.py` | M6, RNF-17 |
| Ejecutor `spawn`, latido y progreso | `backend/cimenta/presupuesto/infraestructura/ejecutor_analisis.py` | M5, CA-12–CA-14 |
| `SeguimientoImportacion`, `solicitar_analisis` | `backend/cimenta/presupuesto/aplicacion/analisis_importacion.py` | CA-12, CA-13 |
| `progreso_de_lectura`, callback `al_avanzar` | `dominio/importacion.py`, `lector_catalogo.py` | CA-13, esc. 4 HDU-001 |
| `variables_de_base_presentes`, ajustes de trabajos | `herramientas/conexion.py`, `servidor/ajustes.py` | P16, TC-64–67 |
| `lifespan` con barrido y ejecutor | `servidor/fabrica.py` | M6, CA-15 |
| `crear_ejecutor_analisis`, `__all__` | `cimenta/presupuesto/interfaz.py` | Composición |
| Pruebas TC-43…TC-67, mutantes M-13…M-23 | `backend/tests/test_tkt015_*.py` (filas b) | Criterios b |
| Mutación B7 | `backend/herramientas/ejecutar_mutantes_tkt015b.py` | CAR2 entrega b |
| **ADR-037** trabajos en dos pasos | `docs/adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md` | Decisión de arquitectura |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| CI cobertura `trabajos` | `.github/workflows/ci.yml`, `tools/tests/test_definicion_ci.py` | Sin `--cov=trabajos` → compuerta B1b |
| Conteo **37 ADR**, regla 11 excepción `lifespan` | `CLAUDE.md`, `README.md`, `llms.txt`, arquitectura, modelo §11, stack, arranque | Documentación alineada a b |
| Regresiones lectores TKT-013/014 | `test_tkt013_regresion.py`, `test_tkt014_lector.py` | Sin cambio de resultado (CA-R1) |
| Hub SDD | `sdd/tickets/tkt-015/*` | Cierre entrega b |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| — | — | Nada eliminado |

## Comportamiento observable nuevo

**Sin rutas HTTP nuevas** (sigue TKT-018). Con base configurada, al arrancar el API **barre** importaciones `ANALIZANDO` con latido vencido y las deja `CON_ERRORES` con `PROCESO_INTERRUMPIDO` (`REINICIO`), de modo que la obra puede reintentar (`RNF-17`). El análisis pesado corre en **un proceso hijo**; mientras tanto el API actualiza `latido` y `progreso`. Un apagado **ordenado** interrumpe cola y trabajo en curso con `REINICIO`; un reinicio brusco sigue dependiendo del barrido del arranque siguiente (hasta el umbral). Sin variables de base, el servidor arranca sin barrido ni ejecutor (`trabajos_omitidos`, P16).

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| OpenAPI / endpoints | Sin cambios | No |
| Esquema PostgreSQL | Sin migración nueva en b | No |
| Variables de entorno opcionales | `CIMENTA_TRABAJOS_INTERVALO_LATIDO`, `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO` | No (opcionales, documentadas) |
| `app.state.ejecutor_analisis` | Nuevo estado del servidor | No (interno hasta TKT-018) |

## Decisiones (ADR)

→ [ADR-037 · Trabajos en dos pasos y barrido de arranque](../../../docs/adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md).

**Evidencia:** TC-63–66 arranque; TC-52–62 ejecutor; mutación 11/11 en rojo; `lint-imports` contrato `trabajos` kept.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `GREATEST` en repo exige test directo; `resumir_avances` enmascara M-18 | B7 mutación | Persistencia de progreso |
| M-17 necesita `max_workers=2` + cola extra para caer en Windows/`spawn` | `ejecutar_mutantes_tkt015b` | Mutación de concurrencia |
| Cierre ordenado del ejecutor evita hueco RNF-17 en reinicio rápido | Decisión revisión 2026-11-05 | `lifespan` / operación |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `mutación` | Dos scripts `ejecutar_mutantes_tkt015a/b` duplican estructura; candidato a helper común tras tercer ticket | Baja |
| `revisión` | Auditoría arquitectura vs ADR sobre «hasta el umbral» obligó decisión explícita en revisión, no en diseño | Media |
| `herramienta` | `tools/historias_activas.tmp` apareció en working tree; no versionar | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Rutas HTTP importación, CSRF, permisos | Fuera de alcance 015 | **TKT-018** |
| Adaptador almacén + `leer_contenido` real | TKT-059 | **TKT-059** |
| Tiempo máximo por análisis (`terminate_workers`) | P12, ADR-037 | Ticket Python 3.14+ |
| Stripping `CIMENTA_*` en hijo `spawn` | O1 seguridad, baja | Endurecimiento futuro |
| Validador Pydantic umbral default vs 3×intervalo | Nota B5 | Decisión producto |
| Menores auditoría código (logging, tipado cola) | No bloquean | Higiene |

## Pull request

**Título:** `TKT-015b · Ejecutor, latido, barrido y arranque`
**Origen:** `agent+human-review`
**Cuerpo:** ver PR en GitHub.

**Fusión con omisión:** según procedimiento del orquestador tras aprobación explícita.
