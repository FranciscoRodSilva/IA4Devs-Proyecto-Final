# Impl · TKT-001 · Estructura del repositorio y herramientas base

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

## Qué se implementó

Se creó el andamiaje del repositorio sobre la rama `tkt-001-estructura-repositorio`, sin lógica de negocio. El backend es un proyecto `uv` sin empaquetar en `backend/`, con Ruff y mypy; mypy es estricto solo sobre los módulos `cimenta.*.dominio.*`. El frontend es un proyecto `npm` en `frontend/`, con TypeScript en modo estricto, ESLint en configuración plana y la versión de Node fijada con `engines` más `engine-strict`. En la raíz se añadieron `.editorconfig`, `.gitattributes` y `.env.example` sin claves, y se completó el `.gitignore`. La comprobación de codificación vive en `tools/verificar_docs.py`, con sus pruebas `unittest` en `tools/tests/`. Se documentó el arranque en `docs/arranque-local.md` y se actualizaron `CLAUDE.md`, `README.md`, `llms.txt`, `docs/convenciones.md` §3, `docs/06-stack-tecnologico.md` §9 y `tools/README.md`.

Entorno de ejecución, el 2026-10-17: Windows 11 Pro 10.0.26200, `uv` 0.10.7, CPython 3.14.3, Node v24.22.0 y npm 11.19.1. Node 24 lo instaló el usuario durante la ejecución, porque el equipo tenía Node 22 y el diseño fija la línea LTS más reciente.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-17 | Fila 2: no hace falta el commit separado de normalización de finales de línea | `git ls-files --eol` dio 0 archivos en `i/crlf` (los 76 versionados están en `i/lf`); la copia de trabajo en Windows está en CRLF, pero el índice ya está en LF, así que `.gitattributes` no cambia ningún blob |
| 2026-10-17 | Fila 5: TC-17 nace en verde, no en rojo | Ruff 0.17.1 trae `I001` en su conjunto por omisión. El `select` explícito de `pyproject.toml` sustituye ese conjunto, y el mutante M6 (quitar `"I"`) pone TC-17 en verde, que es lo que demuestra que la compuerta depende de la configuración. Por eso `select` debe ser explícito y no `extend-select` |
| 2026-10-17 | Fila 6: `eslint` queda en `10.0.1`, no en la última (`10.13.0`) | La regla del diseño pide que `@eslint/js` lleve la misma versión exacta que `eslint`, y `npm view @eslint/js@10.13.0` responde E404: la última publicada es `10.0.1`. Se prefirió la coherencia del par a la última de ESLint. Alternativa disponible: `eslint` 10.13.0 con `@eslint/js` 10.0.1 (su dependencia par admite `^10.0.0`). Queda trazado contra `CA-5` |
| 2026-10-17 | Fila 6: el rojo previo de `npm ci` falla por falta de `package-lock.json`, no de `package.json` | `npm ci` exige el archivo de bloqueo; el texto del diseño se refería a la ausencia del proyecto |
| 2026-10-17 | TC-22: la excepción de `verificar_docs.py` alcanza también los enlaces del hub y del diseño a `impl.md` | `impl.md` tampoco existe hasta `/sdd-ejecutar`. Con este documento escrito desaparecen los enlaces a `impl.md`; el de `delta.md` queda hasta `/sdd-completar` |
| 2026-10-17 | Fila 8: `llms.txt` recibe además una línea «Estructura del repositorio» | TC-23 exige que `llms.txt` nombre `backend/`, `frontend/`, `tools/`, `sdd/` y `.claude/` |
| 2026-10-17 | Revisión: dos marcas de `CLAUDE.md` cambian y se añade una frase | La auditoría de arquitectura señaló que `uv run pytest · desde TKT-003` y `uv run fastapi dev · desde TKT-002` no estaban respaldadas por los criterios de esos tickets. Ahora dicen «desde TKT-003 o TKT-004, el primero en implementarse (asumido)» y «desde TKT-005 (asumido)», y una frase aclara que las reglas obligan desde ya |
| 2026-10-17 | Fila 4: `uv add --dev` genera los rangos `mypy>=2.4.0` y `ruff>=0.17.1` | Es el límite inferior que pone `uv`; las versiones exactas con hash viven en `uv.lock` |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `tools/verificar_docs.py` | modificado | herramientas |
| `tools/tests/test_verificar_codificacion.py` | nuevo | pruebas |
| `.editorconfig`, `.gitattributes`, `.env.example` | nuevo | configuración |
| `.gitignore` | modificado | configuración |
| `backend/pyproject.toml`, `backend/uv.lock`, `backend/cimenta/__init__.py` | nuevo | configuración |
| `frontend/.npmrc`, `package.json`, `package-lock.json`, `tsconfig.json`, `eslint.config.js`, `src/index.ts` | nuevo | configuración |
| `docs/arranque-local.md` | nuevo | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt`, `docs/convenciones.md`, `docs/06-stack-tecnologico.md`, `tools/README.md` | modificado | documentación |
| `sdd/tickets/tkt-001/` | nuevo | trazabilidad |

## Pruebas

Ticket de fundación sin base de datos: no hay PostgreSQL, MinIO ni `pytest`. Las pruebas de código son `unittest` (decisión aprobada del diseño) y el resto son comandos con su código de salida.

| # | Prueba | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_tkt001_ca7_arbol_correcto_sin_problemas` | feliz | `CA-7` | FALLA | PASA |
| TC-02 | `test_tkt001_ca7_esc01_markdown_con_bom_se_detecta` | **rechazo** | `CA-7` | FALLA | PASA |
| TC-03 | `test_tkt001_ca7_esc02_powershell_sin_bom_se_detecta` | **rechazo** | `CA-7` | FALLA | PASA |
| TC-04 | `test_tkt001_ca7_directorios_excluidos_no_se_revisan` | borde | `CA-7` | FALLA | PASA |
| TC-05 | `test_tkt001_ca7_extension_en_mayusculas_se_revisa` | borde | `CA-7` | FALLA | PASA |
| TC-05b | `test_tkt001_ca7_constante_bom_son_los_tres_bytes_de_utf8` (añadida por el tester) | feliz | `CA-7` | FALLA | PASA |
| TC-06 | `python tools/verificar_docs.py` sin problemas `Codificación ·` | regresión | `CA-R1`, `CA-R2` | — | PASA |
| TC-07 | Demostración sobre el repositorio real, con dos desechables | **rechazo** | `CA-7` | — | RECHAZA, como debe |
| TC-08, TC-09 | `editorconfig` sobre `.md`, `.py`, `.ts` y `.ps1` | feliz y regresión | `CA-6`, `CA-R1` | VACÍO (sin `.editorconfig`) | PASA |
| TC-10 | `git check-ignore` sobre ocho rutas y `.env.example` | regresión | `CA-R4` | FALLA en `.env.production` | PASA |
| TC-11 | `.env` con valor no se puede preparar | **rechazo** | `CA-8` | — | RECHAZA, como debe |
| TC-12 | `.env.example` solo con comentarios | feliz | `CA-8` | — | PASA |
| TC-13 | Backend: `uv sync --locked`, Ruff y mypy | feliz | `CA-1` | FALLA (sin `pyproject.toml`) | PASA |
| TC-14 | mypy rechaza función sin anotar en `dominio/` | **rechazo** | `CA-2` | FALLA (mypy no era estricto) | RECHAZA, como debe |
| TC-15 | mypy no rechaza esa función fuera de `dominio/` | rechazo del falso positivo | `CA-2` | vacuo | PASA |
| TC-16 | `ruff format --check` rechaza `x=1` | **rechazo** | `CA-2` | RECHAZA ya (valor por omisión) | RECHAZA |
| TC-17 | `ruff check` rechaza imports sin ordenar (`I001`) | **rechazo** | `S1` | NACE EN VERDE (ver ajustes) | RECHAZA, como debe |
| TC-18 | Frontend: `npm ci`, lint y typecheck | feliz | `CA-3` | FALLA (sin lockfile) | PASA |
| TC-19 | TypeScript rechaza parámetro sin tipo (`TS7006`) | **rechazo** | `CA-4` | Ver mutantes M7–M9: compuerta rota = no rechaza | RECHAZA, como debe |
| TC-20 | ESLint rechaza variable sin usar | **rechazo** | `CA-4` | Ver mutantes M7–M9: compuerta rota = no rechaza | RECHAZA, como debe |
| TC-21 | `npm ci` falla con `EBADENGINE` | **rechazo** | `CA-4` | Ver mutantes M7–M9: compuerta rota = no rechaza | RECHAZA, como debe |
| TC-22 | `verificar_docs.py` y `extraer_mermaid.py` | regresión | `CA-10`, `CA-R3` | — | Ver «Documentación actualizada» |
| TC-23 | Estructura nombrada en README, `llms.txt` y convenciones §3 | feliz | `CA-10` | — | PASA |
| TC-24, TC-26 | Cada comando de `CLAUDE.md`, en copia limpia | **rechazo** | `CA-9` | — | Tabla más abajo |
| TC-25 | Versiones idénticas en dos copias limpias | feliz | `CA-5` | — | PASA |

### Ciclo TDD por fila

#### Fila 1 · Comprobación de codificación

**Rojo** — `tester-backend`, `python -m unittest discover -s tools/tests -v`. Los seis tests fallan por la razón esperada, no por importación ni sintaxis:

```text
test_tkt001_ca7_arbol_correcto_sin_problemas ... ERROR
test_tkt001_ca7_constante_bom_son_los_tres_bytes_de_utf8 ... ERROR
test_tkt001_ca7_directorios_excluidos_no_se_revisan ... ERROR
test_tkt001_ca7_esc01_markdown_con_bom_se_detecta ... ERROR
test_tkt001_ca7_esc02_powershell_sin_bom_se_detecta ... ERROR
test_tkt001_ca7_extension_en_mayusculas_se_revisa ... ERROR
AttributeError: module 'verificar_docs' has no attribute 'verificar_codificacion'
AttributeError: module 'verificar_docs' has no attribute 'BOM'
Ran 6 tests in 0.010s
FAILED (errors=6)
```

**Verde** — `ingeniero-devsecops`: la constante `BOM` y `verificar_codificacion` (38 líneas añadidas, ninguna borrada):

```text
Ran 6 tests in 0.033s
OK
```

TC-06: `python tools/verificar_docs.py` imprime la línea `codificación 73` y ningún problema `Codificación ·`; ningún `.md` existente tenía BOM. TC-07: con `docs/_desechable_bom.md` (con BOM) y `.claude/hooks/_desechable.ps1` (sin BOM) el verificador termina con código 1 y nombra ambos archivos; se borraron y volvió a cero problemas.

**Refactor:** sin refactor, el código es lineal. Incidente: la primera escritura dejó el BOM como caracteres visibles en lugar de la secuencia de escape; se corrigió a `b"\xef\xbb\xbf"` y se verificó byte a byte.

**Tests devueltos al tester:** ninguno.

**Mutación:**

| Mutante | Resultado | Pruebas en rojo |
|---|---|---|
| M1 invertir la condición de documentos | rojo | TC-01, TC-02 y TC-05 |
| M2 quitar la comprobación de `.ps1` | rojo | TC-03 |
| M3 comparar la extensión sin minúsculas | rojo | TC-05 |
| M4 no podar `EXCLUIR` | rojo | TC-04 |

Tras los cuatro, el archivo quedó idéntico (`git diff --stat`: 38 inserciones, 0 borrados) y la suite en verde.

#### Fila 2 · `.editorconfig` y `.gitattributes`

**Rojo:** `npx --yes editorconfig` (paquete `editorconfig` 3.0.2) sobre `docs/glosario.md`, `tools/verificar_docs.py`, `frontend/src/index.ts` y el hook no devolvía ninguna propiedad, porque no existía `.editorconfig`.

**Verde:** TC-08, los tres primeros archivos resuelven `charset=utf-8`, `end_of_line=lf`, `insert_final_newline=true`, y `indent_size` 4 en Python y 2 en TypeScript. TC-09, el hook resuelve `charset=utf-8-bom` y sus tres primeros bytes siguen siendo `efbbbf` antes y después; ninguna fila lo editó. `verificar_docs.py`: cero problemas de codificación.

**Refactor:** sin refactor.

#### Fila 3 · `.gitignore` y `.env.example`

**Rojo:** TC-10 falla solo en `.env.production`, que no estaba ignorado.

**Verde:** con `.env.*` y `!.env.example`, todas las rutas quedan ignoradas y `git check-ignore .env.example` (sin `-v`) termina con código 1, es decir, no se ignora. TC-11: con un `.env` que contiene `CLAVE=valor`, `git add --dry-run .env` responde que la ruta está ignorada, `git status --porcelain --ignored .env` muestra `!! .env`, y se borró el archivo. TC-12: ninguna línea no vacía de `.env.example` deja de empezar por `#`, y la cabecera nombra TKT-003, TKT-057 y TKT-059.

**Refactor:** sin refactor. Nota: con `-v`, `git check-ignore` devuelve 0 para `.env.example` porque informa del patrón negado; el criterio es sin `-v`.

#### Fila 4 · Backend

**Rojo:** `uv sync --locked` en `backend/` vacío: `error: No pyproject.toml found in current directory or any parent directory`, código 2.

**Verde:** `backend/pyproject.toml`, `uv.lock` y `cimenta/__init__.py`. TC-13, los cuatro comandos con código 0:

```text
Resolved 8 packages / Audited 7 packages
1 file already formatted
All checks passed!
Success: no issues found in 1 source file
```

Versiones fijadas en `uv.lock`: Ruff 0.17.1 y mypy 2.4.0. Sin `.python-version`.

**Refactor:** sin refactor.

#### Fila 5 · Compuertas del backend

**Rojo** (tester, con desechables bajo `backend/cimenta/desechable_tkt001/`, sin configuración de Ruff ni mypy): TC-14, `mypy .` termina con código 0 y no cita `no-untyped-def`, lo esperado porque mypy aún no era estricto. TC-15, vacuo hasta que TC-14 esté en verde. TC-16, `ruff format --check` ya rechaza por omisión: `3 files would be reformatted`. TC-17, nace en verde: Ruff 0.17.1 incluye `I001` por omisión (ver ajustes).

**Verde** (`ingeniero-devsecops`): con `[tool.ruff]`, `[tool.ruff.lint]` (`select` explícito), `[tool.mypy]` y el `override`:

```text
cimenta\desechable_tkt001\dominio\regla.py:1: error: Function is missing a type annotation  [no-untyped-def]
Found 1 error in 1 file                                            (TC-14, código 1)
mypy no cita aplicacion/regla.py                                   (TC-15)
unformatted: ... formato.py:1:2 · 3 files would be reformatted     (TC-16, código 1)
I001 Import block is un-sorted or un-formatted · importaciones.py  (TC-17, código 1)
```

mypy no avisó de banderas que no sean por módulo; no se retiró ninguna.

**Refactor:** sin refactor. Se borró `backend/cimenta/desechable_tkt001/` y TC-13 volvió a pasar con los cuatro comandos en código 0. Con el desechable borrado, mypy imprime `note: unused section(s): module = ['cimenta.*.dominio.*']`: lo emite `warn_unused_configs` y desaparece cuando existan los `dominio/` reales.

**Mutación:** M5 (patrón `cimenta.dominio.*`): mypy termina con código 0, TC-14 deja de rechazar; al revertir, vuelve a código 1. M6 (quitar `"I"` de `select`): `All checks passed!`, TC-17 deja de rechazar; al revertir, vuelve a código 1.

#### Fila 6 · Frontend

**Rojo:** `npm ci` en `frontend/` vacío: `EUSAGE`, el comando exige un `package-lock.json` existente.

**Verde:** tras `rm -rf node_modules`, `npm ci` instala 88 paquetes con 0 vulnerabilidades; `npm run lint` y `npm run typecheck` terminan con código 0. `package.json` no contiene `^`, `~`, `*` ni `latest`, y no tiene `dependencies`. `npx eslint --print-config src/index.ts` contiene `no-unused-vars`, así que la configuración no está vacía.

Versiones elegidas el 2026-10-17: `eslint` 10.0.1 y `@eslint/js` 10.0.1 (ver ajustes); `typescript-eslint` 8.71.2, cuya dependencia par exige `typescript >=4.8.4 <6.1.0`; `typescript` 6.0.3, la mayor dentro de ese rango, porque 7.0.2 queda fuera. Node: la línea 24 («Krypton»), la LTS más reciente según `nodejs.org/dist/index.json`. Context7 no respondió, y la sintaxis de `eslint.config.js` se verificó contra los paquetes instalados.

**Refactor:** sin refactor.

#### Fila 7 · Compuertas del frontend

**Rojo:** no hay rojo previo. La configuración del frontend nació en la fila 6, con `tsconfig.json` y `eslint.config.js` ya escritos, así que la fila 7 solo demuestra que las compuertas rechazan. El equivalente al rojo son los mutantes M7 a M9, que ponen en verde lo que debía rechazar.

**Verde:** TC-19: `src/desechable_tipos.ts(1,27): error TS7006: Parameter 'valor' implicitly has an 'any' type.`, código 2. TC-20: `1:7 error 'sinUso' is assigned a value but never used @typescript-eslint/no-unused-vars`, código 1. TC-21, con `engines.node` en `>=99.0.0`: `npm error code EBADENGINE`, `Required: {"node":">=99.0.0"}`, `Actual: {"node":"v24.22.0","npm":"11.19.1"}`, código 1.

**Mutación:**

| Mutante | Resultado con el mutante | Tras revertir |
|---|---|---|
| M7 `"strict": false` | `typecheck` código 0, sin `TS7006` | vuelve `TS7006` |
| M8 `files: ["**/*.js"]` | `lint` código 0, sin reporte | vuelve el error |
| M9 sin `engine-strict=true` | `npm ci` solo advierte `EBADENGINE`, instala y sale con 0 | vuelve a fallar |

Se borraron los desechables y los hashes SHA-256 de `package.json`, `package-lock.json`, `.npmrc`, `tsconfig.json`, `eslint.config.js` y `src/index.ts` son idénticos antes y después. TC-18 en verde de nuevo.

#### Fila 8 · Documentación

Fila de documentación: no tiene ciclo rojo→verde de código; la evidencia son los verificadores y la tabla TC-26. Ver «Documentación actualizada». TC-23 pasa: README, `llms.txt` y convenciones §3 nombran `backend/`, `frontend/`, `tools/`, `sdd/` y `.claude/`, y el README enlaza `docs/arranque-local.md`. Queda una mención de «sin código» en la sección histórica de la Entrega 1 del README, que no se tocó.

#### Fila 9 · Arranque en dos copias limpias

Fila de verificación de arranque: no tiene ciclo rojo→verde de código; la evidencia son los verificadores y la tabla TC-26.

Se construyeron `tkt001-a` y `tkt001-b` en el scratchpad con los 93 archivos de `git ls-files --cached --others --exclude-standard`, sin `.venv`, `node_modules` ni `.git`; el hook `.ps1` es idéntico byte a byte (SHA-256 `ffb8144b…aa97`). En ambas copias, backend y frontend pasan con código 0 en todos los comandos. TC-25, salidas idénticas en A y B:

| Comando | Salida |
|---|---|
| `uv run ruff --version` | `ruff 0.17.1` |
| `uv run mypy --version` | `mypy 2.4.0 (compiled: yes)` |
| `npx tsc --version` | `Version 6.0.3` |
| `npx eslint --version` | `v10.0.1` |
| `npm ls --depth=0` | `@eslint/js@10.0.1`, `eslint@10.0.1`, `typescript-eslint@8.71.2`, `typescript@6.0.3` |

La cabecera de `npm ls` incluye la ruta absoluta de cada copia, así que la comparación se hace sin esa primera línea.

TC-26, copia A, cada comando del bloque de `CLAUDE.md`. Las marcas de `uv run pytest` y `uv run fastapi dev` cambiaron después de la primera ejecución, solo de texto, y en la tabla ya figuran con su texto nuevo; esos dos comandos se reejecutaron el 2026-10-17 y su resultado real va debajo de la tabla:

| Comando | Marca | Resultado | Código | ¿Cumple? |
|---|---|---|---|---|
| `uv sync --locked` | — | sin cambios | 0 | sí |
| `uv run ruff format .` | — | 1 archivo sin cambios | 0 | sí |
| `uv run ruff check --fix .` | — | `All checks passed!`, sin cambiar archivos | 0 | sí |
| `uv run mypy .` | — | `Success` y la nota de sección sin usar | 0 | sí |
| `uv run lint-imports` | desde TKT-002 | `program not found` | 2 | sí |
| `uv run fastapi dev` | desde TKT-005 (asumido) | `program not found` | 2 | sí |
| `uv run pytest` | desde TKT-003 o TKT-004, el primero en implementarse (asumido) | `program not found` | 2 | sí |
| `uv run alembic upgrade head` | desde TKT-003 | `program not found` | 2 | sí |
| `npm ci` | — | 88 paquetes | 0 | sí |
| `npm run lint` | — | limpio | 0 | sí |
| `npm run typecheck` | — | limpio | 0 | sí |
| `npm run dev` | desde TKT-008 | `Missing script: "dev"` | 1 | sí |
| `docker compose up -d db` | desde TKT-003 | `no configuration file provided` | 1 | sí |
| `docker compose up -d minio` | desde TKT-059 | `no configuration file provided` | 1 | sí |
| `python tools/verificar_docs.py` | — | 3 enlaces rotos a `impl.md` y `delta.md` | 1 | excepción de TC-22 |
| `python tools/extraer_mermaid.py` | — | 30 diagramas | 0 | sí |
| `python -m unittest discover -s tools/tests -v` | — | 6 pruebas OK | 0 | sí |

Reejecución de los dos comandos cuyas marcas cambiaron, el 2026-10-17, desde `backend/` (`fastapi dev` con `timeout 20`):

```text
$ uv run pytest
error: Failed to spawn: `pytest`
  Caused by: program not found                       (código 2)

$ timeout 20 uv run fastapi dev
error: Failed to spawn: `fastapi`
  Caused by: program not found                       (código 2)
```

Tras la ejecución no quedó ningún proceso `fastapi` activo.

Ningún comando marcado funciona y ninguno sin marca falla, salvo `verificar_docs.py` por los artefactos de fases posteriores. Los SHA-256 de los 93 archivos no cambiaron tras ejecutar los comandos. Constancia: `docs/arranque-local.md` dice «Verificado en copia limpia el: 2026-10-17, en Windows 11, con uv 0.10.7, Python 3.14.3, Node v24.22.0 y npm 11.19.1».

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Fila 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 1 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Filas 2 y 3 | `ingeniero-devsecops` | `haiku` | `haiku` | Despachadas juntas: ambas son configuración mecánica y verificable por comando |
| Fila 4 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 6 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 7 | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 8 | `general-purpose` | `haiku` | `haiku` | Sustituye al agente redactor, que no existe (metodología §13) |
| Fila 9 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Auditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Auditoría de seguridad | `auditor-seguridad` | `sonnet` | `sonnet` | — |
| Correcciones de la revisión | orquestador | `haiku` | — | Tres ediciones mínimas de texto en `CLAUDE.md` y `docs/arranque-local.md`, hechas por el orquestador sin despachar `corrector-revision` |

Ningún paso subió de modelo.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-13, y en dos copias limpias (fila 9) |
| `CA-2` | `[M]` | Cumplido | TC-14 a TC-16, M5 |
| `CA-3` | `[M]` | Cumplido | TC-18 |
| `CA-4` | `[M]` | Cumplido | TC-19 a TC-21, M7 a M9 |
| `CA-5` | `[M]` | Cumplido con una desviación | TC-25; `eslint` queda en 10.0.1, no en la última (ver ajustes) |
| `CA-6` | `[M]` | Cumplido | TC-08, TC-09 |
| `CA-7` | `[M]` | Cumplido | TC-01 a TC-07, M1 a M4 |
| `CA-8` | `[M]` | Cumplido | TC-11, TC-12 |
| `CA-9` | `[M]` | Cumplido | TC-24, TC-26; dos marcas corregidas tras la revisión |
| `CA-10` | `[M]` | Cumplido con la excepción de TC-22 | TC-23; `verificar_docs.py` falla solo por el enlace del hub a `delta.md` |
| `CA-R1` a `CA-R4` | `[M]` | Cumplido | TC-06, TC-09, TC-10 |
| `S1` | Should | Cumplido | `select` explícito, M6 |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` en el ciclo 3 (`REQUIERE CAMBIOS` en los ciclos 1 y 2) | 3 menores y 2 observaciones, todos resueltos; 2 observaciones bajas sobre el diseño | 3 |
| `auditor-seguridad` | `APROBADO` | 2 observaciones bajas | 1 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `CLAUDE.md:103`, `docs/arranque-local.md` | Marca de `uv run pytest` sin respaldo: TKT-002 no tiene criterio de tests y TKT-003 exige tests y depende solo de TKT-002 | Resuelto: «desde TKT-003 o TKT-004, el primero en implementarse (asumido)» |
| F002 | arquitectura | Menor | `CLAUDE.md:102`, `docs/arranque-local.md` | Marca de `fastapi dev` sin respaldo: TKT-002 no crea una aplicación servible | Resuelto: «desde TKT-005 (asumido)» |
| F003 | arquitectura | Menor | `sdd/tickets/tkt-001/` | Faltaba `impl.md` con las demostraciones de rechazo y los mutantes | Resuelto con este documento |
| F004 | arquitectura | Observación | `CLAUDE.md` | La marca de la regla 1 podía leerse como regla diferida | Resuelto: frase aclaratoria tras la definición de la marca |
| F005 | arquitectura | Observación | `frontend/package.json` | `eslint` en 10.0.1 frente a `CA-5` | Resuelto: motivo trazado en ajustes |
| O1 | seguridad | Baja | `backend/pyproject.toml` | Rangos `>=` en el grupo dev | Aceptado: `uv.lock` fija las versiones; confirmar `--locked` en el pipeline (TKT-009) |
| O2 | seguridad | Baja | `backend/pyproject.toml` | `pip-audit` no está declarado | Fuera de alcance: lo trae TKT-009. La auditoría lo ejecutó con `uvx` sin vulnerabilidades |

Las correcciones de la revisión son texto de documentación y no se reauditaron: el auditor de arquitectura queda con las dos marcas y la frase por confirmar en `/sdd-revisar`.

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `.claude/agents/git-entrega.md`, `.claude/skills/sdd-completar/SKILL.md` | Cambios previos y ajenos al ticket, sin commitear. No deben entrar en el commit de TKT-001 | Alta (higiene del commit) |
| `tools/extraer_mermaid.py` | Escribe `tools/mermaid-check.html`, ignorado por `.gitignore` y no mencionado en `docs/arranque-local.md` | Baja |
| `backend/` | Sin `.python-version`, el intérprete depende de la máquina: aquí `uv` resolvió CPython 3.14.3 con `requires-python >=3.13`. Lo decide TKT-009 con el pipeline o TKT-058 con la imagen | Baja |
| `tools/tests/` | Con la consola cp1252 de Git Bash, `unittest -v` muestra caracteres corruptos en los nombres con acentos; con `PYTHONIOENCODING=utf-8` sale limpio. Cosmético | Baja |
| `uv run mypy .` | Emite una nota de sección sin usar hasta que existan `cimenta/<módulo>/dominio/` (TKT-002) | Baja |
| `backend/pyproject.toml` | `pip-audit` no está declarado como dependencia | Baja (TKT-009) |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/arranque-local.md` | Nuevo: requisitos, arranque del backend y del frontend, verificadores, regla de codificación, tabla «Lo que todavía no arranca» y la constancia de la verificación en copia limpia |
| `CLAUDE.md` | Sección «Comandos» en tres grupos con su directorio y con las marcas «desde TKT-xxx»; marcas en prosa de las reglas 1 y 2 y del verificador de escenarios; frase aclaratoria. Ninguna regla cambió |
| `README.md` | Estado «Entrega 2 en curso» y filas para el arranque local y la estructura del repositorio |
| `llms.txt` | Estado actualizado, enlace al arranque local y línea de estructura |
| `docs/convenciones.md` §3 | Árbol con `backend/`, `frontend/`, `tools/`, `sdd/`, `.claude/` y los archivos de la raíz |
| `docs/06-stack-tecnologico.md` §9 | `verificar_docs.py` también detecta documentos con BOM y `.ps1` sin él |
| `tools/README.md` | Fila «Codificación» y cómo ejecutar `tools/tests/` |

`python tools/verificar_docs.py` → tras escribir este documento, el único problema esperado es el enlace del hub a `delta.md`, que se resuelve en `/sdd-completar`. Se confirma en el cierre.

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia, con la desviación de `CA-5` anotada
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (6 pruebas `unittest`)
- [x] ≥1 prueba de rechazo por criterio con regla o compuerta
- [x] Mutación de cada compuerta: M1 a M9
- [x] Todas las auditorías `APROBADO`: seguridad en el ciclo 1 y arquitectura en el ciclo 3 de `/sdd-revisar`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy` limpios (`lint-imports` llega con TKT-002)
- [x] Rama correcta y sin secretos en el diff: la rama es correcta y la auditoría de seguridad no halló secretos. Condición para el commit: no incluir los cambios ajenos de `.claude/agents/git-entrega.md` y `.claude/skills/sdd-completar/SKILL.md`

### Revisión (`/sdd-revisar`, 2026-10-17)

Suite ejecutada de nuevo por el revisor, no copiada de este documento: `docker info` responde (aunque este ticket no usa contenedores); desde `backend/`, `uv sync --locked`, `ruff format --check`, `ruff check` y `mypy .` con código 0; desde `frontend/`, `npm ci`, `npm run lint` y `npm run typecheck` con código 0; `unittest` con 6 pruebas OK; `extraer_mermaid.py` con código 0; el hook conserva `efbbbf`. `python tools/verificar_docs.py` termina con código 1 solo por el enlace a `delta.md` desde el hub y desde este documento, que se resuelve en `/sdd-completar`. Criterios Must: 14 de 14 cumplidos, `CA-5` con la desviación de `eslint` anotada. Auditorías: seguridad `APROBADO`, arquitectura `APROBADO` tras tres ciclos de corrección sin hallazgos críticos ni mayores. No se despachó `auditor-codigo` ni `auditor-docs` porque esos agentes no existen en este entorno; el código nuevo es una función de 38 líneas con sus pruebas y mutantes.
