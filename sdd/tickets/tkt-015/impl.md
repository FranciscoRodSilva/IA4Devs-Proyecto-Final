# Impl · TKT-015 · Validaciones y reporte de errores por fila

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

## Qué se implementó

**En curso — TKT-015a.** Entrega a del paraguas TKT-015: clasificación, preparación persistida y caso de uso síncrono.

Completado hasta la fila **A7** (pruebas con archivos reales) en rama `tkt-015a-clasificacion-preparacion`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-05 | A0 no ejecutó el guion E-1 | `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` no están definidas en el entorno local; se conserva el recuento E-1 del diseño (2026-11-03) hasta A7 con variables o escalada |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `docs/04-historias-usuario.md` | modificado | documentación |
| `docs/06-stack-tecnologico.md` | modificado | documentación |
| `docs/07-especificacion-api.md` | modificado | documentación |
| `docs/api/openapi.yaml` | modificado | documentación |
| `README.md` | modificado | documentación |
| `llms.txt` | modificado | documentación |
| `backend/cimenta/presupuesto/dominio/importacion.py` | nuevo | dominio |
| `backend/herramientas/soporte_tkt015.py` | nuevo | herramientas |
| `backend/tests/test_tkt015_importacion.py` | nuevo | pruebas |
| `backend/cimenta/presupuesto/dominio/clasificacion_importacion.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/preparacion_importacion.py` | nuevo | dominio |
| `backend/tests/test_tkt015_clasificacion.py` | nuevo | pruebas |
| `backend/tests/test_tkt015_clasificacion_libro.py` | nuevo | pruebas |
| `backend/tests/test_tkt015_preparacion.py` | nuevo | pruebas |
| `backend/migraciones/versions/v0009_presupuesto_preparacion_de_importacion.py` | nuevo | migración |
| `backend/tests/test_tkt015_esquema.py` | nuevo | pruebas |
| `backend/tests/test_tkt011_linea_base.py` | modificado | pruebas |
| `backend/tests/test_tkt011_migracion_linea_base.py` | modificado | pruebas |
| `backend/cimenta/presupuesto/infraestructura/tablas.py` | nuevo | infraestructura |
| `backend/cimenta/presupuesto/infraestructura/preparacion_json.py` | nuevo | infraestructura |
| `backend/cimenta/presupuesto/infraestructura/trabajo_analisis.py` | nuevo | infraestructura |
| `backend/herramientas/soporte_tkt015.py` | modificado | herramientas |
| `backend/tests/test_tkt015_contenido.py` | nuevo | pruebas |
| `backend/cimenta/presupuesto/infraestructura/repositorio_importacion.py` | nuevo | infraestructura |
| `backend/cimenta/presupuesto/aplicacion/analisis_importacion.py` | nuevo | aplicación |
| `backend/tests/test_tkt015_analisis.py` | nuevo | pruebas |
| `backend/tests/test_tkt015_archivos_reales.py` | nuevo | pruebas |
| `sdd/tickets/tkt-015/design.md` | modificado | diseño |

## Ciclo TDD por fila

### Fila A-pre · Escenarios 28 y 29 HDU-001

**Verde** — documentación y verificadores:

```text
python tools/verificar_docs.py → escenarios 164, sin problemas
python tools/verificar_escenarios.py → código 0; HDU-001 · 29 escenarios
python -m unittest discover -s tools/tests -v → Ran 509 tests OK
```

Escenarios 28 y 29 sin test hasta A2a (esc. 28) y A1 (esc. 29 parcial en dominio), como prevé el diseño.

### Fila A0 · Reconfirmar E-1

**Ajustado** — guion no corrido; ver tabla de ajustes.

### Fila A1 · `dominio/importacion.py`

**Verde:**

```text
uv run pytest tests/test_tkt015_importacion.py -v → 16 passed in 0.26s
uv run python -m herramientas.verificar_float → hallazgos: 0
```

**Refactor:** sin refactor.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| A-pre | orquestador (documentación) | `haiku` | Composer 2.5 | Ejecución directa en Cursor |
| A1 rojo+verde | orquestador | `haiku` | Composer 2.5 | Misma sesión |

## Bloqueos

| Bloqueo | Impacto | Acción |
|---|---|---|
### Fila A2b · clasificación de libro

**Verde:** `uv run pytest tests/test_tkt015_clasificacion_libro.py tests/test_tkt015_clasificacion.py -q` → 11 passed

### Fila A3 · preparación

**Verde:** `uv run pytest tests/test_tkt015_preparacion.py -q` → 1 passed; dominio TKT-015a: **28 passed**

### Fila A4 · migración `v0009`

**Verde:**

```text
uv run pytest tests/test_tkt015_esquema.py tests/test_tkt011_linea_base.py tests/test_tkt011_migracion_linea_base.py -k importacion → 23 passed (A4 subset)
uv run pytest tests/test_tkt015_*.py -q → 31 passed
```

**Refactor:** sin refactor.

### Fila A5 · contenido y JSON

**Verde:** `uv run pytest tests/test_tkt015_contenido.py -q` → 5 passed

**E-3 (muestra sintética, 2026-11-05):** `len(json.dumps(preparacion))` con `libro_sintetico(conceptos=200)` válido ≈ **44 933** bytes (~**225** bytes/concepto), coherente con la estimación del diseño (~250). ENITI/Union en base (`pg_column_size`) queda para A6/A7.

**Refactor:** sin refactor.

### Fila A6 · repositorio y casos de uso

**Verde:** `uv run pytest tests/test_tkt015_analisis.py tests/test_tkt015_esquema.py -q` → 48 passed (45 + 3 esquema)

**E-4:** TC-38 inserta 8 600 errores en una transacción en ~4 s local; no se midió ENITI en `pg_column_size` (pendiente A7/archivos reales o escalada).

**Nota:** `servidor/manejadores.py` aún no traduce `55P03` a `409 CONCURRENCIA` (TKT-018).

**Detalle JSONB:** `pasar_a_analizando` usa `sqlalchemy.null()` para `preparacion`, no Python `None` (evita JSON `null` con estado `ANALIZANDO`).

**Refactor:** sin refactor.

### Fila A7 · archivos reales

**Verde (condicional):** `uv run pytest tests/test_tkt015_archivos_reales.py tests/test_tkt013_archivos_reales.py tests/test_tkt014_archivos_reales.py -ra` → 5 skipped cada suite sin `CIMENTA_CATALOGO_ENITI` / `CIMENTA_CATALOGO_UNION` (PA-T3).

**E-4:** `test_tkt015_e4_union_cierre_en_tiempo` mide `registrar_resultado` y `pg_column_size` con Union cuando hay variables; en este entorno no se ejecutó.

**Refactor:** sin refactor.

### Fila A8 · ADR-036 y documentación (parte a)

**Entregables:** `docs/adr/20261105-preparacion-de-importacion-en-jsonb.md`; índice ADR; §11 de `docs/03-modelo-datos.md` (`preparacion`, formato 1, `CHECK`); ficha TKT-015 (partición a/b, criterio de `preparacion`); fila ADR-036 en `docs/02-arquitectura.md` §12; conteo **36 ADR** en `CLAUDE.md`, `README.md` y `llms.txt`.

**Conteo ADR (post-A8):** 36 archivos indexados en `docs/adr/README.md` (excluye `template.md`).

**Verificación:**

```text
python tools/verificar_docs.py
python tools/extraer_mermaid.py
python -m unittest discover -s tools/tests -v
```

**Refactor:** sin refactor.

### Fila A9 · Cierre TKT-015a

**Mutación M-01…M-12:** `uv run python -m herramientas.ejecutar_mutantes_tkt015a` → **12/12 en rojo**, código revertido tras cada uno. Ajustes de prueba para atar mutantes: TC-08 con `VALOR_AUSENTE` en D y F (M-03); TC-35 con retardo en `pasar_a_analizando` bajo `patch` (M-08 determinista).

| Mutante | Cambio | Test que cae |
|---|---|---|
| M-01 | `ERROR_DE_FORMULA` → `SIN_CONCEPTOS` | TC-06, TC-25 |
| M-02 | Falta `TIPO_EN_CONFLICTO` en mapa | TC-05 |
| M-03 | `es_celda_de_rendimiento` sin columna F | TC-08 |
| M-04 | `detectar_duplicados` sin normalizar | TC-12 |
| M-05 | Duplicado por repetición de código | TC-12, TC-41 |
| M-06 | `estado_tras_analisis` solo con `len>1` | TC-01, TC-26 |
| M-07 | `puede_analizarse` siempre en `CON_ERRORES` | TC-02, TC-33 |
| M-08 | Sin `FOR UPDATE` | TC-35 |
| M-09 | `cerrar_analisis` sin filtro `ANALIZANDO` | TC-37 |
| M-10 | `CONCEPTO_SIN_PARTIDA` → `SIN_CONCEPTOS` | TC-05, TC-40 |
| M-11 | `DUPLICADO` de APU rechaza catálogo | TC-14, TC-42 |
| M-12 | `interrumpir` escribe `preparacion` | TC-32 |

**Verificación TC-INV-2:**

```text
uv run ruff format --check .  → 215 files already formatted
uv run ruff check .           → All checks passed!
uv run mypy .                 → Success (215 source files)
uv run lint-imports           → 15 kept, 0 broken
uv run python -m herramientas.verificar_float → hallazgos: 0
uv run pytest tests/test_tkt015_*.py (8 módulos) → 81 passed, 5 skipped (PA-T3)
test_tkt005_car2_calidad_estatica_sin_hallazgos → 4 passed (ruff, mypy, format, lint-imports)
```

**Escenarios HDU-001 (28–29):** con `HDU-001` en `historias_activas.txt`, esc. 4–10 y 27–29 no figuran en `FALTA` (cubiertos por `test_hdu001_esc28_*` y `test_hdu001_esc29_*`); los 19 restantes de fase 1 pertenecen a otros tickets.

**Refactor:** mypy en dominio (`_enumerar`, `claves_desc`, `CursorResult` en `borrar_errores`); tipos en tests de contenido y `hallazgo()` con ubicación anulable.

## Revisión TKT-015a (2026-11-05)

**Suite:** `uv run pytest` (repositorio completo) → 1945 passed, 25 skipped; módulos `test_tkt015_*` → 81 passed, 5 skipped en CI (PA-T3). **Local (2026-11-05):** con catálogos en `D:\Documentos\Miich\Documentos\`, `test_tkt015_archivos_reales.py` → 5 passed.

**Auditorías iniciales:** arquitectura y código → REQUIERE CAMBIOS; sql y docs → APROBADO.

**Ciclo de corrección (hallazgos Mayores):**

| ID | Acción |
|---|---|
| F001 arq | `tools/historias_activas.txt` ya en UTF-8 válido; sin cambio de contenido |
| F001 código | `hallazgo_ejemplo` centralizado en `herramientas/soporte_tkt015.py` |
| F002 código | TC-05 exige `TIPO_POR_CAUSA`; esc. 27 y TC-30 con aserciones explícitas |
| F003 arq | A7: TC-40/41/42 omitidos aquí por PA-T3; CI con catálogos reales los ejecuta |
| F008 código | Precedencia en `_filas_y_hojas_rechazadas`; `cast(CursorResult)` en `borrar_errores` |
| O002 docs | Eliminado `tools/historias_activas.tmp.txt` |

**Verificación final (post-corrección):** ruff, mypy, lint-imports, verificar_float y `test_tkt015_*` en verde; `python tools/verificar_docs.py` OK.

**Veredicto:** TKT-015a **LISTO PARA PR** (TKT-015b fuera de alcance).

## Siguiente

[Delta del sistema](delta.md) · fusión del PR de TKT-015a. TKT-015b (B0…) queda aparte.
