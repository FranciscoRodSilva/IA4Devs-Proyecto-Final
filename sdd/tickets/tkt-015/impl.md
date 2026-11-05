# Impl · TKT-015 · Validaciones y reporte de errores por fila

> [← index](_index.md) | [← design](design.md) | [delta](delta.md)

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

Ninguno en TKT-015a.

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

[Delta del sistema](delta.md) · TKT-015a fusionada (PR #44, #45).

---

## TKT-015b · en ejecución

**Rama:** `tkt-015b-ejecutor-barrido` (desde `Produccion`).

### Fila B0 · experimentos E-5 (Linux) y E-7

**E-5 (Linux, `python:3.14-slim`, 2026-11-05):** guion temporal fuera del repo. Salida:

```text
initargs: [1, 2, 3]
submit-cola: PicklingError
```

Coincide con el diseño (tres mensajes por `initargs`; pasar la cola por `submit` falla). **No escala.**

**E-7:** `uv run lint-imports` → `Contracts: 15 kept, 0 broken` (antes). La verificación «16 kept» y las importaciones deliberadas van con el contrato `trabajos-solo-sqlalchemy` en **B1** (misma fila que el paquete).

**Estado B0:** E-5 ✓ · E-7 (baseline) ✓ · E-7 (post-contrato) ✓ (16 kept con `trabajos-solo-sqlalchemy`).

### Fila B1 · barrido genérico (`trabajos/barrido.py`)

**Tests nuevos:** `tests/test_tkt015_barrido.py` (TC-43, TC-44, TC-45).

**Fronteras actualizadas:** `test_fronteras_dominio.py`, `test_tkt005_fronteras.py`, `test_tkt007_fronteras.py` (copia incluye `trabajos/` si existe; conteo **16**); `test_tkt013_regresion.py` literal «16 kept».

**Salida en rojo (2026-11-05):**

```text
uv run pytest tests/test_tkt015_barrido.py tests/test_fronteras_dominio.py::test_tkt004_ca10_arbol_real -q
4 failed
TC-43/44: ModuleNotFoundError: No module named 'trabajos'
TC-45: AssertionError: falta el paquete backend/trabajos (B1 verde)
TC-98: Contracts: 15 kept, 0 broken — assert (15, 0) == (16, 0)
```

**Verde (2026-11-05):**

```text
uv run pytest tests/test_tkt015_barrido.py + fronteras (4 casos) → 7 passed
uv run lint-imports → Contracts: 16 kept, 0 broken
uv run mypy . → Success
```

Producción: `backend/trabajos/barrido.py`, contrato `trabajos-solo-sqlalchemy`, `root_packages` y override mypy en `pyproject.toml`.

### Fila B1b · cobertura de `trabajos` en CI

**Cambios:** `.github/workflows/ci.yml` añade `--cov=trabajos`; `tools/tests/test_definicion_ci.py` — `comprobar_cov_trabajos` y `test_tkt015_b1b_backend_pytest_mide_cobertura_de_trabajos` (sin tocar `comprobar_tc01`).

**Verificación (2026-11-05):** `test_tkt015_b1b_backend_pytest_mide_cobertura_de_trabajos` OK. Cobertura local con `tests/test_tkt015_barrido.py`: `trabajos/barrido.py` **69%** (39 stmts; sin cubrir el gancho `al_vencer`, previsto en B2).

### Fila B2 · barrido de importación

**Tests:** `tests/test_tkt015_barrido_importacion.py` (TC-43b, TC-46–TC-49).

**Producción:** `cimenta/presupuesto/aplicacion/barrido_importacion.py`; `interfaz.py` exporta `definicion_barrido_importacion` en `__all__`.

**Verde (2026-11-05):**

```text
uv run pytest tests/test_tkt015_barrido_importacion.py tests/test_tkt015_barrido.py → 8 passed
uv run lint-imports → 16 kept; uv run mypy . → Success
```

### Fila B3 · avance de lectura

**Cambios:** `progreso_de_lectura` en `dominio/importacion.py`; `al_avanzar` en `leer_libro_presupuesto` y `analizar_contenido`; firma TKT-014 actualizada; `tests/test_tkt015_avance.py`; corrección en `libro_sintetico` (no duplicar hoja APU).

**Verde (2026-11-05):** pytest B3 + TKT-013/014 lector + `test_tkt015_contenido` OK; `lint-imports` y `mypy` OK.

**Siguiente:** B4 — ejecutor, repositorio (parte b), TC-52–TC-62.

### Fila B4 · ejecutor, seguimiento y solicitud de análisis

**Producción:** `repositorio_importacion.py` (`refrescar_latido`, `registrar_progreso` con `GREATEST(COALESCE(progreso, 0), :progreso)` y `Porcentaje.valor`); `infraestructura/ejecutor_analisis.py` (`Seguimiento`, `EjecutorCerrado`, `resumir_avances`, `notificar_avance`, `ejecutar_en_trabajador`, `EjecutorAnalisis` con `ProcessPoolExecutor(max_workers=1)` en contexto `spawn`, cola de avance por `initargs` e hilo despachador `cimenta-despachador-analisis`); `aplicacion/analisis_importacion.py` (`SeguimientoImportacion`, `solicitar_analisis`). Apoyo: `herramientas/soporte_tkt015.py` (`trabajo_de_prueba`, `liberar`). Sin cambios en B5 (`lifespan`, `crear_ejecutor_analisis`, `interfaz.py`).

**Tests:** `tests/test_tkt015_ejecutor.py` (TC-52 a TC-62), sin `sleep`: esperan con `esperar_latidos` y `esperar_inactivo`, con tope de 30 s.

**Ajustes de prueba respecto al diseño:**

- TC-54, TC-55 y TC-57 usan `esperar_latidos(2, 30)` (y TC-57 `(3, 30)` al final) donde el diseño decía 1: un latido ya confirmado en la base puede incrementar el contador después de fijar la base de la espera, y una comparación de `latido` quedaría intermitente. Antes, cada prueba deja pasar latidos hasta que el avance del hijo llega a la base, porque el arranque `spawn` tarda más que un intervalo de 200 ms.
- TC-59 ejecuta antes un trabajo `anotar` para conocer el `pid` del hijo original; la muerta y la siguiente se encolan juntas antes de `liberar`, como pide el diseño, y el `pid` de la siguiente debe diferir del original.
- TC-60 comprueba que no se envió nada al hijo viendo que el grupo no creó ningún proceso (`_processes` vacío), porque el trabajo corre en otro proceso y no puede registrar llamadas.

**Verde (2026-11-05), tres ejecuciones seguidas:**

```text
uv run pytest tests/test_tkt015_ejecutor.py -q ? 11 passed in 9.86s
uv run pytest tests/test_tkt015_ejecutor.py -q ? 11 passed in 9.79s
uv run pytest tests/test_tkt015_ejecutor.py -q ? 11 passed in 9.86s
uv run mypy .           ? Success: no issues found in 223 source files
uv run lint-imports     ? Contracts: 16 kept, 0 broken
uv run ruff check .     ? All checks passed!
uv run ruff format --check . ? 223 files already formatted
uv run python -m herramientas.verificar_float ? hallazgos: 0
```

Regresión TKT-015 (ejecutor, análisis, barridos, avance y contenido): 79 passed.

**Siguiente:** B5 — ajustes, `lifespan`, `crear_ejecutor_analisis`, `leer_contenido_no_configurado` y `__all__`.

### Fila B5 · arranque: ajustes, `lifespan` e interfaz

**Producción:** `herramientas/conexion.py` (`variables_de_base_presentes`); `servidor/ajustes.py` (`trabajos_intervalo_latido`, entre 1 y 60, y `trabajos_umbral_vencimiento`, al menos tres intervalos, con validador tolerante vía `ValidationInfo.data`); `cimenta/presupuesto/interfaz.py` (`crear_ejecutor_analisis`, `leer_contenido_no_configurado`, reexportación de `EjecutorAnalisis` y `__all__` completo); `servidor/fabrica.py` (parámetro `leer_contenido_archivo`, `proveedor_motor` extraído y compartido con identidad, `lifespan` con `asynccontextmanager` y `run_in_threadpool` para `barrer_todas` y `ejecutor.cerrar`, aviso `trabajos_omitidos` sin variables de base, docstring actualizado).

**Tests:** `tests/test_tkt015_arranque.py` (TC-63 a TC-67); `tests/test_tkt057_arranque.py` afirma ahora los cuatro campos de `AjustesServidor` y conserva la comprobación de que no hay campo de migración ni de lectura.

**Notas:**

- El `lifespan` cierra el ejecutor en un `finally`, de modo que también se cierra si el servidor sale con error tras arrancar.
- Pydantic no valida los valores por omisión: con `CIMENTA_TRABAJOS_INTERVALO_LATIDO=30` y sin umbral, el umbral por omisión (60) queda por debajo de `3 × 30` sin error. El diseño no pide `validate_default`; queda como pregunta para la persona dueña.

**Verde (2026-11-05):**

```text
uv run pytest (las 14 suites de la fila) → 409 passed
uv run mypy .           → Success: no issues found in 224 source files
uv run lint-imports     → Contracts: 16 kept, 0 broken
uv run ruff check .     → All checks passed!
uv run ruff format --check . → 224 files already formatted
uv run python -m herramientas.verificar_float → hallazgos: 0
```

**Siguiente:** B6 — ADR-037 y documentación de b.

### Fila B6 · ADR-037 y documentación de b

**Sin código.** `docs/adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md` (ADR-037, MADR): latido en el proceso del API frente al hijo, un trabajo a la vez en un `ProcessPoolExecutor` `spawn`, `trabajos/` con contrato de lista blanca y la alternativa de `root_packages` de ADR-022, barrido en el `lifespan` con base configurada, omisión sin base (P16), trabajo colgado que mantiene su latido (P12), excepción del `lifespan` `async def` a la regla 11 y a ADR-013 (P13), `progreso_de_lectura` con `ROUND_DOWN` `(asumido)` (P17) y el hijo fuera de `pytest-cov`.

**Documentación:** `docs/adr/README.md` (fila de ADR-037); `CLAUDE.md` (37 decisiones, `trabajos/` en la estructura, `import-linter` analiza `trabajos/`, frase de la excepción en la regla 11); `README.md` y `llms.txt` (37 ADR); `docs/convenciones.md` (`trabajos/` en la lista de paquetes); `docs/02-arquitectura.md` (§1 contenedores, §7.7, §9 con el latido del API y el barrido del `lifespan`, rótulo de `CON_ERRORES → ANALIZANDO`, §12 con ADR-037); `docs/03-modelo-datos.md` §11 (rótulos de `progreso` y `latido`, `progreso` en 1 al terminar y conservado tras una interrupción, latido del API, barrido solo con base); `docs/05-tickets-trabajo.md` (línea del latido y el progreso de TKT-015, TKT-017 y TKT-059 dependen de TKT-015b, TKT-059 reutiliza `DefinicionBarrido` con `columna_marca="creado_en"`); `docs/06-stack-tecnologico.md` (§3.3 y la fila de `RNF-17` con TC-46 y TC-63); `.env.example` (las dos variables de trabajos, comentadas); `docs/arranque-local.md` (`trabajos` en `lint-imports`, `--cov=trabajos`, el barrido exige las variables de base y las dos variables opcionales).

**Notas:**

- El borrador OpenAPI no se tocó: el ajuste de la descripción de `progreso` era opcional.
- `docs/05-tickets-trabajo.md:566` conserva «el barrido que construye TKT-015» porque cuenta la historia del corte de un ciclo de dependencias.
- `docs/arranque-local.md` y `.env.example` dicen «al menos tres veces el intervalo» para el umbral; el validador no lo comprueba cuando el umbral queda en su valor por omisión (nota de B5).

**Verde (2026-11-05):**

```text
python tools/verificar_docs.py → Sin problemas (37 ADR)
python tools/extraer_mermaid.py → 30 diagramas encontrados
python -m unittest discover -s tools/tests → 510 tests, OK
uv run pytest tests/test_tkt057_entorno.py → 8 passed
Grep «37 decisiones» en CLAUDE.md → :14
```

**Siguiente:** B7 — cierre de b con los mutantes M-13 a M-23.

### Fila B7 · cierre de b: mutantes y TC-INV-2

**Herramienta:** `herramientas/ejecutar_mutantes_tkt015b.py` — aplica M-13…M-23, ejecuta los tests anclados del diseño y revierte al terminar cada mutante.

**Tests añadidos:** `test_tkt015_registrar_progreso_no_sobrescribe_con_menor` (TC-55 · `GREATEST` en repositorio). El escenario `avance-desordenado` del ejecutor sigue comprobando el camino integrado, pero sin este test M-18 no caía porque `resumir_avances` filtra avances menores antes de persistir.

**Mutantes:** 11/11 en rojo (2026-11-05). M-17 exige `max_workers=2` además de despachar la cola en la misma vuelta; solo la cola extra con un worker no bastaba en Windows/`spawn`.

**Verde (2026-11-05):**

```text
uv run python -m herramientas.ejecutar_mutantes_tkt015b → 11/11 mutantes cayeron en rojo
uv run pytest tests/ -k tkt015 -q → 128 passed
uv run python -m herramientas.verificar_float → hallazgos: 0
uv run lint-imports → Contracts: 16 kept, 0 broken
uv run ruff check . → All checks passed!
uv run mypy . → Success: no issues found in 225 source files
```

**Siguiente:** `/sdd-revisar TKT-015b` y, con veredicto favorable, `/sdd-completar TKT-015b`.

### Revisión TKT-015b (2026-11-05)

**Correcciones tras auditorías (ciclo 1):**

- `ejecutor_analisis.cerrar()` interrumpe cola y trabajo en curso con `MotivoInterrupcion.REINICIO` (decisión persona dueña sobre F001 arquitectura).
- `submit` protegido ante `BrokenProcessPool` / `RuntimeError`; vaciado de avance tolera cola corrupta (F001–F002 código).
- `fabrica.py` normalizado a LF (TC-105 regresión).
- ADR-037 §4 y consecuencias actualizados (cierre ordenado vs muerte brusca).
- Test nuevo: `test_tkt015_cerrar_interrumpe_cola_y_en_curso`.

**Pendiente en `/sdd-completar`:** versionar archivos sin trackear (ADR-037, `trabajos/`, ejecutor, tests b, mutantes b); CI en GitHub.

## Verificación final · TKT-015b

| Criterio | Resultado | Evidencia |
|---|---|---|
| **M5** | Cumplido | `EjecutorAnalisis`, TC-52–TC-62, `test_tkt015_ejecutor.py` |
| **M6** | Cumplido | `lifespan` + `barrido_importacion`, TC-63–TC-66 |
| **M7** | Cumplido | `trabajos/barrido.py`, TC-43–TC-45, TC-43b, TC-46–TC-49 |
| **CA-12** | Cumplido | TC-52, TC-62, cierre con REINICIO |
| **CA-13** | Cumplido | TC-50–TC-57, `registrar_progreso` + GREATEST |
| **CA-14** | Cumplido | TC-58–TC-60 |
| **CA-15** | Cumplido | TC-46, TC-63 |
| **CA-16** | Cumplido | TC-48, TC-57 |
| **CA-17** | Cumplido | TC-44, `DefinicionBarrido` |
| **CA-R1** (lector) | Cumplido | TC-50, regresiones TKT-013/014 |
| **CA-R2** | Cumplido | TC-INV-2, mutantes M-13–M-23 |

**Auditorías:**

| Auditor | Veredicto | Notas |
|---|---|---|
| arquitectura | Aprobado tras corrección | F001 cerrado con `cerrar()` + ADR; F002–F004 menores documentados |
| código | Aprobado con observaciones | F001–F002 corregidos; F003–F012 menores abiertos (logging, tipado cola, refactors test) |
| seguridad | Aprobado | O1–O3 baja, sin bloqueos |
| documentación | Aprobado al commitear | F001 = incluir ADR y archivos nuevos en el PR |

**Suite (salida real, 2026-11-05):**

```text
docker info → Client 29.9.2 (desktop-linux)
uv run pytest -q → 2013 passed in 394.91s
uv run ruff check . → All checks passed!
uv run mypy cimenta/ → Success: no issues found in 101 source files
uv run lint-imports → Contracts: 16 kept, 0 broken
uv run python -m herramientas.verificar_float → hallazgos: 0
python tools/verificar_docs.py → ✓ Sin problemas (37 ADR)
uv run python -m herramientas.ejecutar_mutantes_tkt015b → 11/11 mutantes cayeron en rojo
uv run pytest tests/ -k tkt015 -q → 129 passed
```

**Estado:** [delta.md](delta.md) · entrega en PR (TKT-015b).
