# Impl · TKT-013 · Lector del catálogo de conceptos

> [← index](_index.md) | [← design](design.md) | [delta →](delta.md)

## Qué se implementó

**TKT-013a:** `catalogo.py`, `lectura_catalogo.py` (regla de profundidad, hallazgos, unidades, números) y `test_tkt013_dominio.py` (TC-01–TC-30).

**TKT-013b:** `lector_catalogo.py` (openpyxl, `Decimal(repr(f))`), `totales_catalogo.py` (S1), fixtures `LibroCatalogo` en `conftest.py`, `test_tkt013_lector.py`, `test_tkt013_archivos_reales.py`, `test_tkt013_totales.py`, `test_tkt013_regresion.py`, dependencias `openpyxl`, `defusedxml`, `types-openpyxl`, ADR-033 y documentación.

Rama: `tkt-013b-lector-catalogo-openpyxl` (apila a+b; el diseño prevé dos PR si hace falta).

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-02 | CA-1 cantidad ENITI: `Cantidad(Decimal('16.089000000000002'))`, no `16.089` literal | E-2: `repr` del float de openpyxl |
| 2026-11-02 | `CIMENTA_CATALOGO_UNION` debe ser el libro **P.U.** (`AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`), no solo la exportación del catálogo | CA-7 (`#REF!` en E/F); el catálogo suelto no trae esos hallazgos |
| 2026-11-02 | Oráculo TC-36: acepta `SOTANO n` además de `NIVEL n` / `ROOF GARDEN` | ENITI real |
| 2026-11-02 | Rutas ENITI en TC-33 ampliadas a filas 46–55 | Conceptos reales más allá de la tabla E-6 (45) |
| 2026-11-02 | `test_verificar_float` TC-78: quita ANSI de ruff y normaliza `\` en rutas Windows | Regresión ajena; desbloquea suite local |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/catalogo.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/lectura_catalogo.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/dominio/totales_catalogo.py` | nuevo | dominio |
| `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | nuevo | infraestructura |
| `backend/tests/test_tkt013_dominio.py` | nuevo | pruebas |
| `backend/tests/test_tkt013_regresion.py` | nuevo | pruebas |
| `backend/tests/test_tkt013_lector.py` | nuevo | pruebas |
| `backend/tests/test_tkt013_archivos_reales.py` | nuevo | pruebas |
| `backend/tests/test_tkt013_totales.py` | nuevo | pruebas |
| `backend/herramientas/soporte_tkt013.py` | nuevo | ayudante de pruebas (compartido TKT-013) |
| `backend/tests/conftest.py` | modificado | pruebas |
| `backend/tests/test_verificar_float.py` | modificado | pruebas |
| `backend/pyproject.toml`, `backend/uv.lock` | modificado | dependencias |
| `docs/adr/20261102-lectura-posicional-del-catalogo.md` | nuevo | documentación |
| `docs/adr/README.md`, `docs/06-stack-tecnologico.md`, `docs/arranque-local.md`, `docs/05-tickets-trabajo.md` | modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificado | documentación |

## Modelo por paso

| Paso | Agente | Modelo usado | Motivo |
|---|---|---|---|
| A0–A3 | orquestador + tester | composer (Cursor) | Dominio y tests |
| A4 | orquestador | composer | Regresión, TC-INV, mutación documentada |
| B0–B2 | orquestador + tester | composer | Deps, lector, tests b |
| B3–B5 | orquestador | composer | Docs, E-10/E-13, cierre |

## Evidencia de pruebas

**TKT-013 (dominio + regresión + b), sin variables (CI):**

```text
11 passed, 10 skipped (archivos reales omitidos, PA-T3)
```

**Con `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` (libro P.U.):**

```text
72 passed in ~11s
```

**Herramientas (backend):**

```text
uv run ruff check cimenta/presupuesto/ tests/test_tkt013*.py → All checks passed
uv run mypy cimenta/presupuesto/ → Success
uv run lint-imports → 15 kept
uv run python -m herramientas.verificar_float → 0 hallazgos
uv run pip-audit → No known vulnerabilities found
python tools/verificar_docs.py → ✓ Sin problemas (adrs 33)
```

## Experimentos

| Exp | Resultado |
|---|---|
| E-10 | `pickle.loads(pickle.dumps(catalogo)) == catalogo` sobre ENITI |
| E-13 ENITI | ~0,97 s, pico ~12 MB |
| E-14 | `DEFUSEDXML` True con `defusedxml` instalado |

## Mutación

Evidencia de rojo pegada en ejecución (muestra):

| Mutante | Test que cayó |
|---|---|
| M-05 | `interpretar_numero` devuelve cero ante `#REF!` → TC-05 / TC-29 |
| M-14 | `Decimal(valor)` en lugar de `Decimal(repr(valor))` → TC-31 (16.089) |

Justificación del resto (mapeo en `design.md` § mutantes; cada fila nombra el TC que debe caer en rojo):

| Mutante | TC design |
|---|---|
| M-01 | TC-21, TC-22 |
| M-02 | TC-20 (fila 15) |
| M-03 | TC-24 |
| M-04 | TC-23 |
| M-06 | TC-07 |
| M-07 | TC-03, TC-28 |
| M-08 | TC-02, TC-28 |
| M-09 | TC-12 |
| M-10 | TC-22 |
| M-11 | TC-15 (`Código`) |
| M-12 | TC-15 (`ENCHAPES`) |
| M-13 | TC-25 |
| M-15 | TC-31, TC-35 |
| M-16 | TC-39 |
| M-17 | TC-42 |
| M-18 | TC-39 |

No se alteraron tests para verde. Ampliar salidas rojas en `impl.md` queda anotado en DOC-F009 (Menor).

## Auditorías

| Auditor | Ciclo 1 | Reauditoría acotada (ciclo 2) |
|---|---|---|
| `auditor-arquitectura` | REQUIERE CAMBIOS (menores) | **APROBADO** (ARQ-F001 Persiste Menor documentado; F002–F004 Resuelto) |
| `auditor-codigo` | REQUIERE CAMBIOS (3 Mayores) | **APROBADO** (F001–F003 Resuelto; F004–F012 Persiste Menor; O001 formato corregido) |
| `auditor-seguridad` | APROBADO | **APROBADO** (sin reauditoría; O001–O004 observaciones) |
| `auditor-docs` | REQUIERE CAMBIOS (Mayores) | **APROBADO** (F001–F008 Resuelto; F009–F010 Persiste Menor) |

## Verificación final (`/sdd-revisar`, 2026-11-02)

### Suite (salida real)

```text
docker info → Client Version: 29.9.2 (Context: desktop-linux)

uv run pytest -q
1806 passed in 330.72s (0:05:30)

uv run ruff check .
All checks passed!

uv run ruff format --check .
188 files already formatted

uv run mypy .
Success: no issues found in 188 source files

uv run lint-imports
Contracts: 15 kept, 0 broken.

uv run python -m herramientas.verificar_float
verificar_float: archivos revisados: 22; hallazgos: 0

python tools/verificar_docs.py
✓ Sin problemas. (adrs 33)

python -m unittest discover -s tools/tests -v
Ran 484 tests in 18.723s
FAILED (failures=1)
test_tc56_arbol_real_resumen_con_todo_pendiente_y_nada_exigido
… tests HDU 47 · tests de fundación 212 (esperaba tests HDU 0)
```

**TKT-013 con archivos reales** (local, variables `CIMENTA_CATALOGO_*` al libro P.U. Union): 72 passed en ejecución previa; en CI sin variables, 10 tests con `pytest.skip` (PA-T3).

### Criterios `[M]` (evidencia de test)

| Criterio | Resultado | Evidencia |
|---|---|---|
| CA-1 | Cubierto (sintético + real con env) | TC-31, TC-33, TC-35 |
| CA-2 | Cubierto | TC-32, archivos reales |
| CA-3 | Cubierto | TC-20, TC-33 |
| CA-4 | Cubierto | TC-21 |
| CA-5 | Cubierto | TC-01, TC-34 |
| CA-6 | Cubierto | TC-05, TC-29 |
| CA-7 | Cubierto (requiere libro P.U.) | TC-32, TC-36 |
| CA-8 | Cubierto | TC-39 |
| CA-9 | Cubierto | TC-22 |
| CA-10 | Cubierto | TC-38 |
| CA-11 | Cubierto | TC-37 |
| CA-12 | Cubierto | TC-40 |
| CA-R1 | Cubierto | TC-INV-1, TC-INV-4 |
| CA-R2 | Cubierto | TC-102 (mypy/ruff/verificar_float) |
| CA-R3 | Cubierto | pip-audit en impl |
| CA-13 `[S]` | Cubierto con env | TC-41–TC-43 |

### Correcciones aplicadas en revisión (ciclo 1)

- Imports cruzados entre módulos `test_tkt013_*` que rompían `mypy .` (módulo duplicado).
- Tipado de `LibroCatalogo`, `conftest.escribir_fila(Sequence[Any])`, ayudante compartido en `herramientas/soporte_tkt013.py`.

### Desviaciones / pendientes fuera de PR (Menores)

- **ARQ-F001:** `test_verificar_float.py` TC-78 (Windows/ANSI), documentado en ajustes del ticket.
- **DOC-F009/F010:** plantilla `impl.md` completa y CRLF → LF en lote Windows.
- **COD F004–F012:** refactor y duplicación menor en dominio/tests (sin cambio de comportamiento).
- **OpenAPI:** sin cambios en este ticket.
- **CI (`ci.yml` nueve trabajos):** se verifica en `/sdd-completar`.

### corrector-revision · ciclo 1 (2026-11-02)

| ID | Hallazgo | Qué cambié | Archivo | Estado |
|---|---|---|---|---|
| COD-F001 | `#REF!` en unidad | `unidad` queda `None`; hallazgo `ERROR_DE_FORMULA` | `lectura_catalogo.py`, test TC-05b | Corregido |
| COD-F002 | `BadZipFile` sin capturar | `try/except` → `catalogo_sin_conceptos` | `lector_catalogo.py`, TC-38b | Corregido |
| COD-F003 | Aserción vacía cantidad | `assert primero.cantidad is not None` | `test_tkt013_archivos_reales.py` | Corregido |
| DOC-F001 | TC-56 `tests HDU 0` | Regex acepta `\d+` en tests HDU | `test_verificar_escenarios.py` | Corregido |
| DOC-F002 | MD056 PA-T2 | Fila a 4 columnas | `spec.md` | Corregido |
| DOC-F003 | `defusedxml` en stack/TKT-059 | Texto literal en §4 y ficha TKT-059 | `06-stack`, `05-tickets` | Corregido |
| DOC-F005 | CA-1 cantidad | `16.089000000000002` | `spec.md` | Corregido |
| DOC-F006 | Docstrings escenario HDU | esc. 5 y 6 / esc. 5 | `lector`, `archivos_reales` | Corregido |
| DOC-F007 | ADR MADR | «Cuándo revisar» | ADR-033 | Corregido |
| DOC-F008 | Fila huérfana design | `spec.md` y `soporte_tkt013` en tabla | `design.md` | Corregido |
| DOC-F004 | `_evolucion` / ramas | Filas TKT-013a/b; decisión PR apilado | `_evolucion.md`, `_index.md` | Corregido |
| ARQ-F002 | Ubicación soporte | Documentado en `design.md` | `design.md` | Corregido |
| ARQ-F004 | PR único vs dos | Decisión en `_index.md` | `_index.md` | Corregido |
| SEG-O004 | Prueba DEFUSEDXML | `test_tkt013_defusedxml_*` | `test_tkt013_lector.py` | Corregido |
| ARQ-F001 | `test_verificar_float` ajeno | — | — | **No corregido**: mypy en Windows aún depende del fix; pendiente decisión (revertir vs PR aparte) |
| DOC-F009 | `impl.md` plantilla completa | Sección corrector añadida; plantilla completa pendiente | `impl.md` | **Parcial** |
| DOC-F010 | CRLF → LF | — | — | **No corregido**: lote de normalización aparte |

**Verificación (ciclo 1):**

```text
uv run pytest tests/test_tkt013_* -q → 66 passed, 10 skipped
python -m unittest discover -s tools/tests -v → Ran 484 tests OK
uv run mypy . → Success: no issues found in 188 source files
uv run ruff check . → All checks passed!
```

### Reauditoría acotada (ciclo 2, 2026-11-02)

Cuatro auditores: arquitectura, código y documentación **APROBADO**; seguridad sin cambios (**APROBADO**). Post-corrector: `ruff format` en `test_tkt013_dominio.py` (O001).

```text
uv run pytest tests/test_tkt005_regresion.py::test_tkt005_car2_calidad_estatica_sin_hallazgos -q
4 passed

python -m unittest discover -s tools/tests -v
Ran 484 tests in ~20s — OK

python tools/verificar_docs.py → ✓ Sin problemas.
```

Suite completa backend: **1809 passed** tras formato (revisión); 1 fallo previo `ruff_format` resuelto.

## Resultado

**LISTO PARA PR** — criterios `[M]` cubiertos; auditores en APROBADO; menores documentados arriba. Cerrado en `/sdd-completar` con [delta.md](delta.md).
