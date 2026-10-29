# Impl · TKT-002 · Esqueleto del backend por capas y verificación de fronteras

> [← index](_index.md) | [← design](design.md) | Siguiente: delta, que escribe `/sdd-completar`

## Qué se implementó

Se creó el esqueleto del backend sobre la rama `tkt-002-esqueleto-backend`, sin lógica de negocio. Hay diez paquetes de módulo bajo `backend/cimenta/`, cada uno con `api/`, `aplicacion/`, `dominio/`, `infraestructura/` y un único punto de entrada de interfaz, `interfaz.py`. Son 60 archivos nuevos, 40 de ellos vacíos, más el docstring nuevo de `cimenta/__init__.py`. Las fronteras las vigilan 14 contratos de `import-linter` en `[tool.importlinter]` de `backend/pyproject.toml`, en cuatro familias: dos `layers` exhaustivos para el esqueleto, un `forbidden` que mantiene el dominio libre de FastAPI, SQLAlchemy y Pydantic, un `forbidden` con `allow_indirect_imports` que impide entrar al interior de otro módulo, y diez `protected`, uno por módulo, que declaran quién puede importarlo. El grafo declarado tiene 33 aristas permitidas y 57 prohibidas. Se documentó todo en un ADR nuevo, en `docs/02-arquitectura.md`, en `CLAUDE.md` y en los demás documentos que el grafo contradecía.

Entorno de ejecución, el 2026-10-17: Windows 11 Pro 10.0.26200, `uv` 0.10.7, CPython 3.14.3, `import-linter` 2.15, `grimp` 3.17, Node v24.22.0 y npm 11.19.1.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-17 | Las demostraciones se ejecutan con `COLUMNS=250 PYTHONUTF8=1 PYTHONIOENCODING=utf-8` | `rich` corta las líneas a 80 columnas y separa «does not» de «exist»; y en Windows la salida de `import-linter` mostraba caracteres rotos al imprimir «módulos» y «§». Las cadenas que se comprueban son ASCII y no dependen de la codificación |
| 2026-10-17 | `TC-03`, `TC-04`, `TC-05` y `TC-08` terminan por excepción, sin resumen «kept/broken» | `Missing layer in container …` es una excepción de `import-linter`: imprime el error y termina con código 1, sin contar contratos. La cadena esperada aparece, por la razón correcta |
| 2026-10-17 | `TC-04` rechaza con un mensaje distinto según se ejecute junto o aislado | En el run conjunto, la excepción de `esqueleto-capas` aborta antes y solo se ve ese mensaje (`cimenta.inventado.interfaz` o `.aplicacion`); aislado, `esqueleto-modulos` informa `not listed as layers: - cimenta.inventado`. La cadena `cimenta.inventado` aparece siempre |
| 2026-10-17 | Los mensajes de `TC-29` y `TC-30` salen antes de `Analyzed` | Quien automatice la comprobación no debe recortar la salida desde `^Analyzed` |
| 2026-10-17 | El rojo de `TC-17` a `TC-21` y de `TC-24` a `TC-28` es «el contrato aún no existe», no un rechazo anterior | Es el rojo previsto por el diseño: el desechable se importa como dependencia real y nada lo rechaza todavía |

Ninguna fila se marcó `⚠ Ajustado`: ningún ajuste cambia lo que el diseño decide.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/__init__.py` | modificado | estructura |
| `backend/cimenta/<m>/__init__.py`, `api/`, `aplicacion/`, `dominio/`, `infraestructura/` `__init__.py` y `interfaz.py` (diez módulos) | nuevo (60 archivos) | estructura |
| `backend/pyproject.toml`, `backend/uv.lock` | modificado | configuración |
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md`, `docs/adr/README.md` | nuevo, modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificado | documentación |
| `docs/02-arquitectura.md` §3, §4, §5, §6 y §7.7 | modificado | documentación |
| `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md` (TKT-059, 060, 064, 069), `docs/06-stack-tecnologico.md` §8, `docs/07-especificacion-api.md`, `docs/arranque-local.md` | modificado | documentación |
| `.claude/skills/conv-backend-fastapi/SKILL.md` §3 | modificado | convención |
| `sdd/tickets/tkt-002/` | nuevo | trazabilidad |

## Pruebas

Ticket de fundación sin base de datos ni pytest, por la excepción registrada en el diseño (`PA-T3`): cada caso es un comando con su código de salida y una cadena que debe aparecer o desaparecer. El rechazo se cuenta solo si el código es distinto de 0 **y** aparece la cadena del diseño.

| # | Prueba | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `lint-imports` sobre el esqueleto limpio | feliz | `CA-1`, `CA-3` | FALLA (sin esqueleto) | PASA: 14 kept, 0 broken |
| TC-02 | Los 61 `.py` solo tienen docstring o están vacíos | feliz | `CA-1` | — | PASA |
| TC-03 a TC-08 | Módulo o capa ausente, módulo ajeno, segunda interfaz, módulo fuera del contrato, nombre mal escrito | **rechazo** | `CA-2`, `CA-3`, `CA-7` | el contrato existía antes del esqueleto | RECHAZAN, como deben |
| TC-09 | `dominio/` importa otra capa de su módulo | **rechazo** | regla 2, borde de `CA-5` | — | RECHAZA |
| TC-10 | `mypy` sin `unused section` | regresión | `CA-8` | NOTA presente (deuda de TKT-001) | PASA |
| TC-11 | `mypy` rechaza función sin anotar en un `dominio/` real | **rechazo** | `CA-8` | — | RECHAZA |
| TC-12 | `dominio/` puro importa `decimal` y su propio módulo | feliz | `CA-5` | PASA | PASA con el contrato |
| TC-13 a TC-15 | `dominio/` importa `fastapi`, `sqlalchemy`, `pydantic` | **rechazo** | `CA-5` | NO RECHAZAN (código 0) | RECHAZAN |
| TC-16 | `dominio/` llega a SQLAlchemy por su propia infraestructura | **rechazo** | `CA-5`, indirecto | NO RECHAZA | RECHAZA |
| TC-17 a TC-21 | Un módulo importa `dominio/`, `infraestructura/`, `aplicacion/` o `api/` ajenos | **rechazo** | `CA-4`, `CA-3` | NO RECHAZAN (código 0) | RECHAZAN |
| TC-22 | Cadena real a través de la interfaz, sin falso positivo | feliz | `CA-3`, `PA-T7` | PASA | PASA con el contrato |
| TC-23 | Las 33 aristas permitidas | feliz | `CA-6` | PASA | PASA: 14 kept |
| TC-24 a TC-27 | `compras`→`analitica`, `presupuesto`→`compras`, `archivos`→`presupuesto`, `compras`→`almacen` | **rechazo** | `CA-6` | NO RECHAZAN (código 0) | RECHAZAN |
| TC-28 | Los 57 pares prohibidos a la vez: conjunto exacto | **rechazo** | `CA-6`, `M5` | 0 de 57 pares | 57 de 57 |
| TC-29, TC-30 | Nombre mal escrito en `protected_modules` y en `allowed_importers` | **rechazo** | `CA-7` | — | RECHAZAN |
| TC-31 a TC-33 | Copia limpia, base de calidad, marcas | regresión | `CA-8`, `CA-R1`, `CA-R2`, `CA-R3` | — | PASAN |
| TC-34, TC-35 | `verificar_docs.py` y codificación | regresión | `CA-R4`, `CA-R5` | — | PASAN con la excepción del hub |
| TC-36 | `§5`, la spec y los contratos dicen el mismo grafo | revisión | `S1` | — | COINCIDEN en las diez filas |
| TC-37 | Sin desechables, mutantes ni hashes alterados | regresión | `CA-R5`, DoD | — | PASA tras cada fila |

### Ciclo TDD por fila

#### Fila 1 · `import-linter` y contratos del esqueleto

**Rojo** — `uv run lint-imports` antes de instalar:

```
error: Failed to spawn: lint-imports / Caused by: program not found      (código 2)
```

**Verde** — `uv add --dev import-linter` resolvió `import-linter` 2.15 y `grimp` 3.17 (más `click` 8.5.0, `markdown-it-py` 4.2.0, `mdurl` 0.1.2, `pygments` 2.21.0 y `rich` 15.0.0), y se añadió el bloque `[tool.importlinter]` con `esqueleto-modulos` y `esqueleto-capas`. `uv sync --locked` con código 0; `uv tree --depth 1` lista solo `import-linter`, `mypy` y `ruff` como dependencias directas de desarrollo; `lint-imports` termina con código 1 y `Missing layer in container 'cimenta': module cimenta.identidad does not exist.`, que prueba que encuentra el paquete `cimenta` sin `[build-system]`.

**Refactor:** sin refactor.

#### Fila 2 · Esqueleto

**Rojo:** `Missing layer in container 'cimenta': module cimenta.analitica does not exist.`, código 1.

**Verde:** 60 archivos nuevos y el docstring de `cimenta/__init__.py`.

```
Analyzed 61 files, 0 dependencies.
cimenta tiene exactamente los diez módulos de arquitectura §5 KEPT
Cada módulo tiene sus cuatro capas y una sola interfaz, y su dominio no importa las otras KEPT
Contracts: 2 kept, 0 broken.
mypy: Success: no issues found in 61 source files   (sin «unused section», TC-10)
ruff format --check: 61 files already formatted · ruff check: All checks passed!
TC-02: archivos revisados 61, incumplen [], código 0
```

**Refactor:** sin refactor.

#### Fila 3 · Demostraciones del esqueleto

**Verde** (el contrato precede al código, así que los casos rechazan ya):

| Caso | Código | Cadena real |
|---|---|---|
| TC-03 `compras/dominio/` movido | 1 | `Missing layer in container 'cimenta.compras': module cimenta.compras.dominio does not exist.` |
| TC-04 `cimenta/inventado` | 1 | `Missing layer in container 'cimenta.inventado': module cimenta.inventado.interfaz does not exist.` |
| TC-05 `almacen/interfaz.py` movido | 1 | `module cimenta.almacen.interfaz does not exist.` |
| TC-06 `almacen/publico.py` | 1 | `esqueleto-capas BROKEN … not listed as layers: - cimenta.almacen.publico` |
| TC-07 sin `proveedores` en el contrato | 1 | `esqueleto-modulos BROKEN … not listed as layers: - cimenta.proveedores` |
| TC-08 `presupesto` | 1 | `module cimenta.presupesto does not exist.` |
| TC-09 `dominio`→`infraestructura` | 1 | `cimenta.compras.dominio is not allowed to import cimenta.compras.infraestructura:` |
| TC-11 `mypy` | 1 | `regla.py:1: error: Function is missing a type annotation  [no-untyped-def]` |

**Mutación:**

| Mutante | Resultado con el mutante | Revertido |
|---|---|---|
| M1 `esqueleto-modulos`: `exhaustive = false` | TC-07 pasa a código 0 | vuelve a rechazar |
| M2 `esqueleto-capas`: `exhaustive = false` | TC-06 a código 0 | vuelve a rechazar |
| M3 `interfaz` opcional | TC-05 a código 0 | vuelve a rechazar |
| M4 `dominio` opcional | TC-03 a código 0 | vuelve a rechazar |
| M5 `esqueleto-capas` en un nivel | TC-09 a código 0 | vuelve a rechazar |
| M6 override de mypy sobre `cimenta.dominio.*` | TC-11 a código 0, y reaparece la nota `unused section` (que cubre TC-10) | vuelve a rechazar |

Hashes de `pyproject.toml`, `presupuesto/interfaz.py` y `almacen/interfaz.py` idénticos tras cada edición. TC-37: sin desechables, `.import_linter_cache/` ignorada.

#### Fila 4 · `dominio-sin-framework`

**Rojo** — sin el contrato: TC-13 (`fastapi`), TC-14 (`sqlalchemy`) y TC-15 (`pydantic`) terminan con código 0 (`Contracts: 2 kept, 0 broken`); TC-16, sin `--contract`, solo falla por `esqueleto-capas` y ninguna línea cita `sqlalchemy` como violación del dominio; con `--contract dominio-sin-framework`: `Could not find contract 'dominio-sin-framework'`.

**Verde** — contrato añadido (38 líneas); con los desechables a la vez, `--contract dominio-sin-framework` rechaza con código 1 las cuatro violaciones, incluida la cadena `indirecto -> infraestructura…orm -> sqlalchemy`.

```
TC-12 (puro.py + otro.py): código 0 · Contracts: 3 kept, 0 broken
TC-13: cimenta.presupuesto.dominio is not allowed to import fastapi:    (código 1; 2 kept, 1 broken)
TC-14: cimenta.compras.dominio is not allowed to import sqlalchemy:
TC-15: cimenta.almacen.dominio is not allowed to import pydantic:
TC-16 (--contract): cimenta.presupuesto.dominio is not allowed to import sqlalchemy:
       - …dominio.desechable_tkt002.indirecto -> …infraestructura.desechable_tkt002.orm (l.1)
         …infraestructura.desechable_tkt002.orm -> sqlalchemy (l.1)
```

**Refactor:** sin refactor.

**Mutación:** M7 (sin `"pydantic"`): TC-15 pasa a 0. M8 (`allow_indirect_imports = true`): TC-16 pasa a 0. M9 (`source_modules` sobre `aplicacion`): TC-13 pasa a 0. Todos revertidos con el hash comprobado. TC-37 limpio: `3 kept, 0 broken`.

#### Fila 5 · `solo-por-interfaz`

**Rojo:** TC-17 a TC-21 terminan con código 0 sin el contrato (`Analyzed 63 files, 1 dependencies`, 3 kept). TC-22, con la línea añadida a `presupuesto/interfaz.py`, da código 0 con 3 dependencias (la cadena `consumo → interfaz → caso → repositorio`); sin esa línea serían 2 y el caso no probaría nada.

**Verde** — contrato añadido (13 líneas):

```
TC-17 cimenta.compras is not allowed to import cimenta.presupuesto.dominio:           (código 1)
TC-18 cimenta.almacen is not allowed to import cimenta.compras.infraestructura:
TC-19 cimenta.presupuesto is not allowed to import cimenta.archivos.infraestructura:
TC-20 cimenta.compras is not allowed to import cimenta.presupuesto.aplicacion:
TC-21 cimenta.compras is not allowed to import cimenta.presupuesto.api:
TC-22 Analyzed 67 files, 3 dependencies. Contracts: 4 kept, 0 broken.                 (código 0)
```

**Refactor:** sin refactor.

**Mutación:** M10 (quitar `allow_indirect_imports`): TC-22 pasa a código 1 y cita las cadenas indirectas `…consumo -> cimenta.presupuesto.interfaz -> …aplicacion.desechable_tkt002.caso -> …infraestructura…repositorio`: es el falso positivo que `PA-T7` temía, y la prueba de que la opción lo evita. M11 a M14 (quitar `dominio`, `infraestructura`, `aplicacion` o `api` de `forbidden_modules`): TC-17, TC-18 y TC-19, TC-20 y TC-21 pasan a código 0. Revertidos y hash `0f3dd765…bee355` comprobado.

#### Fila 6 · Diez contratos `grafo-<m>`

**Rojo:** la tabla «Grafo declarado» de la spec, leída por un script (no el contrato), da 33 aristas permitidas y 57 prohibidas, 90 en total. TC-23 con las 33 da código 0; TC-24 a TC-27, cada uno solo, dan código 0 (`Contracts: 4 kept, 0 broken`); TC-28, con los 90 desechables, da código 0 y 0 de los 57 pares.

**Verde** — diez contratos añadidos tras `solo-por-interfaz` y `lint-imports` con `14 kept, 0 broken`:

```
TC-23: Analyzed 103 files, 33 dependencies. Contracts: 14 kept, 0 broken.             (código 0)
TC-24: Illegal imports of protected package cimenta.analitica:
       - cimenta.compras.aplicacion…prohibida_analitica -> cimenta.analitica.interfaz (l.1)
TC-25: protected package cimenta.compras: - cimenta.presupuesto.aplicacion…
TC-26: protected package cimenta.presupuesto: - cimenta.archivos.aplicacion…
TC-27: protected package cimenta.almacen: - cimenta.compras.aplicacion…
TC-29: "cimenta.presupesto" not present in the graph.                                  (código 1)
TC-30: "cimenta.almacen_" not present in the graph.                                   (código 1)
```

TC-28, con los 33 permitidos y los 57 prohibidos presentes, termina con código 1 (`5 kept, 9 broken`); el extractor halla los 57 pares exactos, `auditoria`→`identidad` está entre ellos y ninguna línea cita una `arista_`. Los pares por destino: `analitica` 9, `proveedores` 9, `avance` 8, `almacen` 8, `personal` 7, `archivos` 6, `compras` 5, `presupuesto` 4, `identidad` 1.

**Refactor:** sin refactor.

**Mutación:**

| Mutante | Resultado con el mutante | Revertido |
|---|---|---|
| M15 `grafo-analitica` + `cimenta.compras` | TC-24 a código 0 | rechaza |
| M16 `grafo-compras` + `cimenta.presupuesto` | TC-25 a código 0 | rechaza |
| M17 `grafo-presupuesto` + `cimenta.archivos` | TC-26 a código 0 | rechaza |
| M18 `grafo-almacen` + `cimenta.compras` | TC-27 a código 0 | rechaza |
| M19 `grafo-analitica`: `as_packages = false` | TC-24 a código 0: sin descendientes solo protege el `__init__.py` | rechaza |
| M20 borrar `grafo-proveedores` | TC-28 informa 48 pares en lugar de 57: faltan los nueve `X → proveedores` | vuelve a 57 |

#### Fila 7 · Documentación y ADR

Ver «Documentación actualizada». No tiene ciclo rojo→verde de código; la evidencia son los verificadores, las búsquedas de `TC-33` y la tabla de `TC-36`. Todas las frases de origen que el diseño manda reemplazar existían literalmente, así que ningún documento quedó sin tocar.

**TC-36:** las tres fuentes (arquitectura §5, la tabla de la spec y los `allowed_importers` invertidos de los diez contratos) coinciden en las diez filas:

| Módulo | Importa, solo por su interfaz |
|---|---|
| `identidad` | `auditoria` |
| `auditoria` | — |
| `archivos` | `identidad`, `auditoria` |
| `presupuesto` | `identidad`, `auditoria`, `archivos` |
| `compras` | `presupuesto`, `identidad`, `auditoria` |
| `almacen` | `compras`, `presupuesto`, `identidad`, `auditoria`, `archivos` |
| `proveedores` | `compras`, `identidad`, `auditoria` |
| `personal` | `presupuesto`, `identidad`, `auditoria` |
| `avance` | `compras`, `presupuesto`, `personal`, `identidad`, `auditoria`, `archivos` |
| `analitica` | `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `identidad`, `auditoria` |

#### Fila 8 · Copia limpia

Se construyó `tkt002-limpia` en el scratchpad con los 159 archivos de `git ls-files --cached --others --exclude-standard`, sin `.venv`, `node_modules` ni `.git`. En ella, `uv sync --locked`, `lint-imports` (`14 kept, 0 broken`), `ruff` y `mypy` (sin `unused section`) con código 0; `uv tree --depth 1` lista solo `import-linter` 2.15, `mypy` 2.4.0 y `ruff` 0.17.1; el diff de `pyproject.toml` frente a `Produccion` son 142 inserciones y ningún borrado, repartidas en la línea de `import-linter` y el bloque `[tool.importlinter]`. `uv run pytest` y `uv run fastapi dev` siguen fallando con `program not found` (código 2). Además, `npm ci`, lint y typecheck del frontend en verde, 6 pruebas `unittest` en verde y `extraer_mermaid.py` con 30 diagramas. La línea «Verificado en copia limpia» de `docs/arranque-local.md` ya coincidía con las versiones reales y no se cambió.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 2 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 3 | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · rojo, verde y cierre | `tester-backend`, `ingeniero-devsecops`, `tester-backend` | `sonnet`, `haiku`, `sonnet` | igual | — |
| Fila 5 · rojo, verde y cierre | `tester-backend`, `ingeniero-devsecops`, `tester-backend` | `sonnet`, `haiku`, `sonnet` | igual | — |
| Fila 6 · rojo, verde y cierre | `tester-backend`, `ingeniero-devsecops`, `tester-backend` | `sonnet`, `haiku`, `sonnet` | igual | — |
| Fila 7 | `general-purpose` | `haiku` | `haiku` | Sustituye al agente redactor, que no existe (metodología §13) |
| Fila 8 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Auditorías de arquitectura y seguridad | `auditor-arquitectura`, `auditor-seguridad` | `sonnet` | `sonnet` | — |

Ningún paso subió de modelo.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-01, TC-02 |
| `CA-2` | `[M]` | Cumplido | TC-03, TC-04, M3, M4 |
| `CA-3` | `[M]` | Cumplido | TC-05, TC-06, TC-20 a TC-22, M2, M3, M10, M13 |
| `CA-4` | `[M]` | Cumplido | TC-17 a TC-19, M11, M12 |
| `CA-5` | `[M]` | Cumplido | TC-12 a TC-16, M7 a M9 |
| `CA-6` | `[M]` | Cumplido | TC-23 a TC-28, M15 a M20 |
| `CA-7` | `[M]` | Cumplido | TC-07, TC-08, TC-29, TC-30, M1 |
| `CA-8` | `[M]` | Cumplido | TC-10, TC-11, TC-31, TC-33, M6 |
| `CA-R1` a `CA-R5` | `[M]` | Cumplido | TC-32, TC-31, TC-33, TC-34, TC-35 |
| `S1` | Should | Cumplido | TC-36, ADR-018 y arquitectura §3 a §7.7 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 4 observaciones, ninguna bloquea | 1 |
| `auditor-seguridad` | `APROBADO` | Ninguno | 1 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O1 | arquitectura | Observación | `backend/pyproject.toml`, `dominio-sin-framework` | El contrato es una lista negra de tres paquetes; otro paquete de tercero o `dominio` → `interfaz` de otro módulo pasan, aunque la regla 2 dice «no importa nada» | Anotada como deuda para TKT-004 |
| O2 | arquitectura | Observación | `docs/02-arquitectura.md` §5, fila `analítica` | Las aristas `(asumido)` hacia `identidad` y `auditoria` perdieron la marca al documentar | Resuelto: la fila dice `identidad, auditoría (asumido)` y `PA-T5` consta como resuelta |
| O3 | arquitectura | Observación | `docs/02-arquitectura.md` §3 | `uv run lint-imports` y `[tool.importlinter]` sin comillas invertidas | Resuelto: entre comillas invertidas |
| O4 | arquitectura | Observación | `sdd/tickets/tkt-002/` | Faltaba `impl.md` y el hub seguía en `LISTO PARA EJECUTAR` | Resuelto con este documento |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/00-propuesta-toolkit.md` línea 17 | Menciona «17 ADRs» en un documento de propuesta histórico; con el ADR-018 son 18. No está en el diseño | Baja |
| `docs/03-modelo-datos.md` | La frase de `presupuesto` y `archivos` está en la sección de adjuntos (línea ~1018); no se comprobó si el diseño la llama §11 o §12 | Baja |
| `docs/arranque-local.md` | El párrafo nuevo de `lint-imports` queda tras «Los tres comandos siguientes…», que habla de Ruff y mypy | Baja |
| `backend/cimenta/<m>/__init__.py` | Es la única segunda puerta que el contrato no cierra: un `__init__.py` con código lo importaría quien tenga la arista. Una comprobación en TKT-009 podría exigir que los diez solo tengan docstring | Baja |
| `dominio-sin-framework` | Ampliar la lista negra o pasar a lista blanca, y decidir qué hacer con `dominio` → `interfaz` de otro módulo (auditoría de arquitectura, O1) | Baja (TKT-004) |
| `pip-audit` | No está declarado en el grupo `dev`; la auditoría de seguridad lo ejecuta con `uvx` | Baja (TKT-009) |
| `TKT-003`, `TKT-004`, `TKT-005` | Avisos de impacto del diseño: Alembic debe quedar fuera de `cimenta/`; los tipos compartidos ajustan el contrato; la raíz de composición de FastAPI chocará con tres familias de contratos | Informativa |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md` | ADR-018 nuevo, formato MADR, con las tres decisiones y sus opciones descartadas |
| `docs/adr/README.md`, `README.md`, `llms.txt` | Fila nueva del ADR y conteo de 17 a 18 |
| `CLAUDE.md` | 18 decisiones; regla 2 sin la marca «desde TKT-002»; regla 3 con la interfaz y su verificación; árbol del backend con `interfaz.py`; frase de `presupuesto` y `analitica`; comando `lint-imports` sin marca |
| `docs/02-arquitectura.md` | §3 verificación y párrafo de la interfaz publicada; §4 frase de `presupuesto` y `analitica`; §5 columna «Importa, solo por su interfaz» y «el contrato es la fuente»; §6 árbol; §7.7 `archivos` |
| `docs/06-stack-tecnologico.md` §8 | Las cuatro familias de contratos en lugar del ejemplo `ini` |
| `docs/arranque-local.md` | `lint-imports` en el arranque del backend y fuera de la tabla de lo que aún no arranca |
| `docs/03-modelo-datos.md`, `docs/07-especificacion-api.md` | `archivos` no conoce a ningún módulo de negocio |
| `docs/05-tickets-trabajo.md` | TKT-059, 060, 064 y 069 alineados con el grafo declarado |
| `.claude/skills/conv-backend-fastapi/SKILL.md` §3 | Interfaz en `interfaz.py` y frase de `presupuesto` y `analitica` |

`python tools/verificar_docs.py` → 18 ADR contados y, tras escribir este documento, el único problema esperado es el enlace del hub a `delta.md`, que se resuelve en `/sdd-completar`. Se confirma en el cierre.

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (`lint-imports` 14 kept, `mypy`, `ruff`, 6 pruebas `unittest`)
- [x] ≥1 prueba de rechazo por cada compuerta y por cada arista del grafo (57 pares)
- [x] Mutación de cada contrato: M1 a M20
- [x] Todas las auditorías `APROBADO`: arquitectura y seguridad, en el primer ciclo
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy` y `lint-imports` limpios
- [x] Rama correcta y sin secretos en el diff: la rama es `tkt-002-esqueleto-backend` y la auditoría de seguridad no halló secretos ni fuentes no oficiales en el bloqueo

### Revisión (`/sdd-revisar`, 2026-10-17)

Suite ejecutada de nuevo por el revisor, no copiada de este documento. `docker info` responde (el ticket no usa contenedores). Desde `backend/`: `uv sync --locked`, `uv run lint-imports --no-cache` con `Analyzed 61 files, 0 dependencies` y `Contracts: 14 kept, 0 broken`, `mypy` con `Success: no issues found in 61 source files` y `ruff format --check` y `ruff check` en verde, todos con código 0. Desde `frontend/`: `npm ci`, `npm run lint` y `npm run typecheck` con código 0. `unittest` con 6 pruebas OK, `extraer_mermaid.py` con código 0 y el hook conserva `efbbbf`. `python tools/verificar_docs.py` cuenta 18 ADR y termina solo con el enlace del hub a `delta.md`, que se resuelve en `/sdd-completar`.

Dos comprobaciones propias, independientes de las demostraciones del ejecutor: un desechable que hace `import fastapi` en `cimenta/presupuesto/dominio/` rompe `dominio-sin-framework` (`13 kept, 1 broken`, código 1), y otro que hace `compras` → `cimenta.analitica.interfaz` rompe `grafo-analitica` (`Illegal imports of protected package cimenta.analitica`). Ambos se borraron y el contrato volvió a `14 kept, 0 broken`.

Criterios Must: 13 de 13 cumplidos (`CA-1` a `CA-8` y `CA-R1` a `CA-R5`), más el Should `S1`. Auditorías: arquitectura y seguridad `APROBADO` en el primer ciclo, sin hallazgos críticos, mayores ni menores. Las tres observaciones de arquitectura que pedían un cambio (O2, O3 y O4) se aplicaron antes del cierre, por el orquestador y no por `corrector-revision`, porque eran tres ediciones de texto: se verificaron con una búsqueda en el repositorio y no se reauditaron. No se despacharon `auditor-codigo` ni `auditor-docs`, porque esos agentes no existen en este entorno; el código nuevo son sesenta archivos con docstring.
