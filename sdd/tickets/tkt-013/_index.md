# TKT-013 · Lector del catálogo de conceptos

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO (al fusionarse el PR; ver comentario de registro en GitHub)

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — sin escenario propio: aporta la lectura de los escenarios 5, 6, 8 y 27; la clasificación en tipos de error es de TKT-015 |
| **Épica / sprint** | Sprint 2 · segundo ticket del análisis de la importación (TKT-013 a TKT-015) |
| **Puntos** | Talla M en el ticket; partido en TKT-013a y TKT-013b (ver «Partición propuesta» en [design.md](design.md)) |
| **Reglas implicadas** | Ninguna `RN-xx` gobierna la lectura. Aplica la regla 1 de `CLAUDE.md` (dinero) y respeta `RN-01` por omisión (no escribe) |
| **Invariantes en riesgo** | Ninguno modificado. Regresión: reglas 1, 2 y 3 de `CLAUDE.md`. Choca, sin tocarlo, con el invariante 13 (`PA-T1`) |
| **Módulos en alcance** | `presupuesto` |
| **Capas en alcance** | dominio e infraestructura. Sin API, aplicación ni frontend |
| **Depende de** | TKT-011b (ARCHIVADO) |
| **Rama** | `tkt-013b-lector-catalogo-openpyxl` (apila 013a+013b; en PR se puede partir como diseño) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-02 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-02 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-11-02 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-02 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-02 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por la persona dueña (M1 a M6, Should S1). 12 criterios `[M]`, uno `[S]` y tres de regresión `[M]`; seis de rechazo (CA-6 a CA-11). Se inspeccionaron los dos archivos reales. INVEST sin fallos y con tres reservas. Cinco objeciones adversariales incorporadas |
| 2026-11-02 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus). Condición de parada 3: ~1,455 líneas, se propone partir en TKT-013a (dominio puro, ~735) y TKT-013b (openpyxl, archivos reales y `S1`, ~720). `revisor-impacto`: sin frontera cruzada y seis hallazgos incorporados. Diez objeciones adversariales. Once preguntas (P1 a P11) esperan a la persona dueña; catorce experimentos quedan `(sin ejecutar)` hasta A0 y B0 |
| 2026-11-02 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones del arquitecto en P1 a P11. Spec ajustada en el mismo acto: sección «Partición en dos entregas», `PA-T2` y `PA-T9` resueltas |
| 2026-11-02 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | TKT-013a (A0–A4) y TKT-013b (B0–B5) implementados; 72 tests TKT-013 en verde con archivos reales; ADR-033; `CIMENTA_CATALOGO_UNION` debe ser el libro P.U. (CA-7) |
| 2026-11-02 | `EN REVISIÓN` | `REQUIERE CAMBIOS` | `/sdd-revisar` | `uv run pytest` → 1806 passed; mypy/ruff/lint-imports/verificar_float/verificar_docs OK; `unittest tools/tests` TC-56 falla (47 tests HDU-001); auditores arquitectura/código/docs REQUIERE CAMBIOS; seguridad APROBADO |
| 2026-11-02 | `REQUIERE CAMBIOS` | `REQUIERE CAMBIOS` | `corrector-revision` ciclo 1 | Cerrados COD-F001–F003, DOC-F001–F008, F004, ARQ-F002/F004, SEG-O004; `unittest` 484 OK; pendiente reauditoría y DOC-F009/F010, menores código, ARQ-F001 |
| 2026-11-02 | `REQUIERE CAMBIOS` | `LISTO PARA PR` | reauditoría ciclo 2 | Auditores arquitectura/código/docs APROBADO; `ruff format` dominio; 1809 pytest; menores ARQ-F001, DOC-F009/F010, COD F004–F012 anotados |
| 2026-11-02 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | `delta.md`; PR abierto; ticket archivado al fusionar |

## Decisiones registradas

- 2026-11-02 · persona dueña: aprobadas P1 a P11 del diseño: partir en TKT-013a y TKT-013b con fusión a → b; `Decimal(repr(f))` sin redondear; la fila de título se conserva como `RAIZ`; regla de profundidad con su límite conocido; filas vacías ignoradas sin hallazgo; `VALOR_AUSENTE` y `NO_ES_NUMERO`; total «no calculable» si falta algún importe; rótulo ausente o repetido deja el resultado sin conceptos; sin quitar espacios interiores de la unidad; `defusedxml` como dependencia en TKT-013b; ADR-033 y conteo de ADR a 33 en `CLAUDE.md`, `README.md` y `llms.txt`.
- 2026-11-02 · persona dueña: la zona de preparación es un valor en memoria devuelto por el lector, sin migración (`PA-T11`; cierra `PA-T12` de TKT-011).
- 2026-11-02 · persona dueña: el lector detecta y TKT-015 clasifica; no se amplía el CHECK de `importacion_error.tipo` (`PA-T10`).
- 2026-11-02 · persona dueña: unidades normalizadas solo por mayúsculas y espacios contra las ocho del catálogo (`PA-T12`).
- 2026-11-02 · persona dueña: un concepto sin partida se reporta como hallazgo; no se infiere ni se completa (`PA-T13`).
- 2026-11-02 · persona dueña: ruta local de los archivos reales, `D:\Documentos\Miich\Documentos`.
- 2026-11-02 · persona dueña: en CI, los archivos reales se omiten con `skip` explícito y visible, y un fixture sintético con la misma estructura cubre el pipeline (`PA-T3`).
- 2026-11-02 · persona dueña (revisión): un solo PR apilado TKT-013a+013b en rama `tkt-013b-lector-catalogo-openpyxl`, con la partición documentada en `docs/05` (alternativa a dos PR en cadena).

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- Resolver los códigos de concepto repetidos dentro de una obra (`PA-T1`): cambia el invariante 13, el escenario 9 de HDU-001 o el modelo de `concepto`. Es previo a TKT-015 y TKT-017.
- Asociar el nombre de una partida con un `tipo_partida` y decidir qué hacer con las que no coinciden (`PA-T8`, `ENCHAPES Y PINTURAS`).
- Decidir qué hace TKT-017 con la fila de título (`RAIZ`), que el modelo no tiene (P3 del diseño).
