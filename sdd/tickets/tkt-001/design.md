# Design · TKT-001 · Estructura del repositorio y herramientas base

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

El ticket se resuelve con configuración nativa de cada herramienta y casi ningún código propio. `backend/` es un proyecto `uv` sin empaquetar con Ruff y mypy como dependencias de desarrollo, y su `pyproject.toml` declara las reglas de Ruff y el modo estricto de mypy solo sobre el patrón de módulo `cimenta.*.dominio.*`. `frontend/` es un proyecto `npm` con TypeScript, ESLint y un único archivo TypeScript mínimo, y la versión de Node se fija con `engines` más `engine-strict` en `.npmrc`, que convierte la advertencia de npm en bloqueo. La única pieza de código nueva es la comprobación de codificación, que se añade a `tools/verificar_docs.py` en lugar de nacer como script aparte: ese verificador ya recorre los mismos documentos, ya se ejecuta antes de cerrar cualquier cambio de documentación y ya está en el plan del pipeline de TKT-009. Cada compuerta se demuestra en rojo con un archivo desechable antes de darla por buena, y el arranque se verifica al final sobre dos copias limpias.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `backend/pyproject.toml` | 5 · objeto nuevo | No existe proyecto Python y `uv` lo exige. Sin `[build-system]`: el proyecto no se empaqueta todavía; empaquetarlo o no lo decide TKT-002 al crear los módulos |
| `backend/uv.lock` | 2 · nativo | Lo genera `uv add`; es la fuente de verdad de las versiones exactas (`CA-5`, `RNF-08`) |
| `backend/cimenta/__init__.py`, solo con docstring | 5 · objeto nuevo, mínimo | `mypy .` sin ningún archivo `.py` termina con código 2 («There are no .py[i] files»), y `CA-1` exige código 0. Es el paquete raíz, no un módulo ni una capa: no pisa el non-goal de TKT-002 |
| `backend/.python-version` | 1 · YAGNI, fuera | `requires-python = ">=3.13"` basta para que `uv` elija intérprete, y el archivo de bloqueo es universal. Fijar el intérprete en el repositorio es una decisión de la imagen (TKT-058) y del pipeline (TKT-009) |
| Reglas de Ruff en `[tool.ruff]` | 4 · cambio mínimo | Dentro del mismo `pyproject.toml`; un `ruff.toml` aparte sería un archivo más con el mismo contenido |
| Modo estricto de mypy sobre `dominio/` | 2 · nativo | Una sección `[[tool.mypy.overrides]]` con comodín no estructurado (`cimenta.*.dominio.*`), que mypy documenta y admite. No hace falta ningún script que filtre rutas |
| `frontend/package.json` | 5 · objeto nuevo | No existe proyecto Node y `npm` lo exige |
| `frontend/package-lock.json` | 2 · nativo | Lo genera `npm install`; fija versiones exactas |
| `frontend/.npmrc` con `engine-strict=true` y `save-exact=true` | 2 · nativo | `engines` solo advierte; `engine-strict` hace que `npm ci` falle con otra versión de Node (`CA-4` esc. 3), y `save-exact` hace que TKT-008 y los siguientes fijen versiones exactas sin acordarse |
| `.nvmrc` | 1 · YAGNI, fuera | Sería una segunda fuente de la versión de Node que puede divergir de `engines`. `engines` con `engine-strict` ya bloquea, y `actions/setup-node` puede leer la versión desde `package.json` `(asumido, a confirmar en TKT-009)` |
| `frontend/tsconfig.json` | 5 · objeto nuevo | No existe; `strict` es lo que exige `M2` |
| `frontend/eslint.config.js` | 5 · objeto nuevo | ESLint 9 y 10 solo leen configuración plana; sin archivo no hay reglas |
| `frontend/src/index.ts` | 5 · objeto nuevo, mínimo | `tsc` sin entradas falla con `TS18003`. Una sola constante exportada; TKT-008 lo sustituye |
| `.editorconfig` | 5 · objeto nuevo | No existe ningún mecanismo que fije la codificación en el editor |
| `.gitattributes` con `* text=auto eol=lf` | 2 · nativo | Git normaliza los finales de línea sin herramienta adicional |
| `.gitignore` | 4 · cambio mínimo | Ya existe y cubre Python, Node y `.env`. Se añaden `.env.*` y la excepción `!.env.example` |
| `.env.example`, solo cabecera | 5 · objeto nuevo, mínimo | `M3` lo exige y todavía no existe ninguna clave (resuelve `PA-T5`) |
| Comprobación de codificación | 4 · cambio mínimo | Se añade la función `verificar_codificacion` a `tools/verificar_docs.py`. Un script nuevo (peldaño 5) duplicaría el recorrido de directorios, la lista de exclusiones y la invocación que el proyecto ya obliga a correr; `editorconfig-checker` sería una dependencia nueva para dos comprobaciones de tres bytes (resuelve `PA-T8`) |
| Pruebas de la comprobación en `tools/tests/` con `unittest` | 2 · nativo | La biblioteca estándar basta y `tools/` es, por diseño, «sin dependencias». pytest recoge las clases `unittest.TestCase` sin cambios cuando TKT-009 las meta en el pipeline. Ponerlas en `backend/` obligaría a instalar pytest antes de su ticket y acoplaría los verificadores de documentación al entorno del backend |
| `docs/arranque-local.md` | 5 · objeto nuevo | El README es índice ([convenciones de documentación](../../../.claude/skills/conv-documentacion/SKILL.md)) y `CA-10` exige que enlace el arranque en lugar de contenerlo. Ningún documento existente trata el entorno local |
| `README.md`, `CLAUDE.md`, `llms.txt`, `docs/convenciones.md` §3, `docs/06-stack-tecnologico.md` §9, `tools/README.md` | 4 · cambio mínimo | Documentación afectada por el cambio. Se toca solo lo que el repositorio real contradice |

Ningún objeto que paró en el peldaño 4 toca un invariante registrado ni una de las 17 reglas de `CLAUDE.md`. La revisión de `CLAUDE.md` añade marcas de disponibilidad, no cambia ninguna regla.

## Capas afectadas

El ticket no toca `dominio/`, `aplicacion/`, `api/`, `infraestructura/`, esquema ni frontend de aplicación. Sus capas son configuración, verificadores y documentación.

### Configuración del backend

`backend/pyproject.toml`, con este contenido y en este orden:

| Sección | Contenido exacto |
|---|---|
| `[project]` | `name = "cimenta"`, `version = "0.1.0"`, `description = "Backend de CIMENTA: control de costos de obra."`, `requires-python = ">=3.13"`, `dependencies = []` |
| `[dependency-groups]` | `dev`, escrito por `uv add --dev ruff mypy` con el límite inferior que `uv` pone por omisión (`ruff>=X.Y.Z`, `mypy>=X.Y`). No se edita a mano |
| `[tool.ruff]` | `line-length = 100`. Sin `target-version`: Ruff lo deduce de `requires-python` |
| `[tool.ruff.lint]` | `select = ["E", "W", "F", "I", "B", "UP", "SIM"]` e `ignore = ["E501"]`. `E501` se ignora porque la longitud la fija el formateador y la regla daría falsos positivos en cadenas y docstrings largos. La regla contra `float` no entra: es de TKT-004 |
| `[tool.mypy]` | `python_version = "3.13"` (se comprueba contra el mínimo declarado, no contra el intérprete local), `warn_unused_configs = true`, `warn_redundant_casts = true`, `exclude = ['^\.venv/']` |
| `[[tool.mypy.overrides]]` | `module = ["cimenta.*.dominio.*"]` con `disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_untyped_calls`, `disallow_untyped_decorators`, `disallow_any_generics`, `disallow_subclassing_any`, `check_untyped_defs`, `warn_return_any`, `warn_unused_ignores` y `strict_equality` a `true`, e `implicit_reexport = false` |

`strict = true` no se usa en la sección por módulo porque mypy lo admite solo como opción global; por eso se enumeran las banderas. Si mypy avisa de que alguna de ellas no es por módulo («Per-module sections should only specify per-module flags»), se retira esa bandera, se anota en `impl.md` y la fila sigue: el aviso es la señal, no una decisión pendiente.

El comodín de en medio de `cimenta.*.dominio.*` coincide con cero o más componentes, así que cubre `cimenta.presupuesto.dominio` y todos sus submódulos. Para que mypy calcule ese nombre de módulo, cada directorio intermedio necesita su `__init__.py`; los archivos desechables de la fila 5 lo llevan.

`backend/cimenta/__init__.py` contiene solo el docstring `"""Backend de CIMENTA. Los paquetes de módulo llegan con TKT-002."""`.

### Configuración del frontend

| Archivo | Contenido exacto |
|---|---|
| `frontend/.npmrc` | `engine-strict=true` y `save-exact=true`, una por línea |
| `frontend/package.json` | `"name": "cimenta-frontend"`, `"version": "0.0.0"`, `"private": true`, `"type": "module"`, `"engines": { "node": ">=N.0.0 <N+1.0.0" }` con `N` según la regla de versiones, `"scripts": { "lint": "eslint .", "typecheck": "tsc --noEmit" }` y `devDependencies` escritas por `npm install --save-dev`, exactas por `save-exact`. Sin `dependencies` |
| `frontend/tsconfig.json` | `compilerOptions`: `"target": "ES2022"`, `"module": "ESNext"`, `"moduleResolution": "Bundler"`, `"strict": true`, `"noEmit": true`, `"skipLibCheck": true`. `"include": ["src"]` |
| `frontend/eslint.config.js` | `defineConfig` importado de `eslint/config`, con un único objeto: `files: ["**/*.ts"]` y `extends: [js.configs.recommended, tseslint.configs.recommended]`, donde `js` viene de `@eslint/js` y `tseslint` de `typescript-eslint` |
| `frontend/src/index.ts` | Una línea: `export const NOMBRE_SISTEMA = "CIMENTA";` |

### Versiones: la regla, no el número

Este agente no tiene terminal, así que no pudo consultar `npm view` ni PyPI al diseñar. Lo que el diseño fija es **la regla determinista** con la que la fila de ejecución elige cada versión el día que corre; los números quedan en los archivos de bloqueo y en `impl.md`, con la fecha.

| Herramienta | Regla | Esperado al 2026-10-17 |
|---|---|---|
| Python | `requires-python = ">=3.13"`, sin límite superior (un techo en `requires-python` rompe la resolución de dependencias). El intérprete local puede ser 3.13 o 3.14 | Mínimo 3.13; el entorno de desarrollo tiene 3.14 ([stack §3.1](../../../docs/06-stack-tecnologico.md#31-python)) |
| Node | La línea mayor más reciente con campo `lts` distinto de `false` en `https://nodejs.org/dist/index.json` el día de la ejecución. `engines` admite toda esa línea mayor | Node 24, LTS activa; Node 26 no pasa a LTS hasta finales de octubre de 2026 `(asumido)` |
| npm | El que trae ese Node. No se fija aparte | — |
| Ruff, mypy | `uv add --dev ruff mypy`, que toma la última estable de PyPI | La última de cada una |
| ESLint | `npm install --save-dev eslint`, que toma la etiqueta `latest` de npm y la guarda exacta | Línea 10 (Context7 lista `v10.5.0`) |
| `@eslint/js` | **La misma versión exacta que `eslint`** | — |
| `typescript-eslint` | La última estable | Línea 8, que declara ESLint `^8.57.0 \|\| ^9.0.0 \|\| ^10.0.0` como dependencia par |
| TypeScript | La **más alta que satisfaga** el rango de `typescript` en `npm view typescript-eslint@<versión elegida> peerDependencies`. Si la última de TypeScript queda fuera de ese rango, se toma la mayor dentro y se anota en `impl.md` | — |

Ninguna dependencia lleva `latest`, `*` ni rango sin límite inferior (`CA-5`): en `package.json` son exactas, y en `pyproject.toml` llevan el límite inferior de `uv` con la versión exacta en `uv.lock`.

### Configuración de la raíz

| Archivo | Contenido exacto |
|---|---|
| `.editorconfig` | `root = true`. Sección `[*]`: `charset = utf-8`, `end_of_line = lf`, `insert_final_newline = true`, `indent_style = space`. `[*.py]`: `indent_size = 4`. `[*.{ts,js,json,yml,yaml}]`: `indent_size = 2`. `[*.ps1]`: `charset = utf-8-bom` |
| `.gitattributes` | Una línea: `* text=auto eol=lf` |
| `.gitignore` | Se añaden, en la sección «Entorno», `.env.*` y `!.env.example`. Lo que ya ignoraba se conserva sin tocar (`CA-R4`) |
| `.env.example` | Solo comentarios, ninguna clave (resuelve `PA-T5`). La cabecera dice: que se copia a `.env`, que `.env` nunca se versiona (`RNF-07`), que cada ticket añade aquí las claves que introduce —la base de datos en TKT-003, la configuración de arranque en TKT-057 y el almacén de objetos en TKT-059— y que ninguna clave lleva nunca un secreto real |

### Verificadores

En `tools/verificar_docs.py`:

| Elemento | Detalle |
|---|---|
| `BOM: bytes = b"\xef\xbb\xbf"` | Constante del módulo |
| `def verificar_codificacion(raiz: str) -> int` | Recorre `raiz` con `os.walk`, podando los directorios de `EXCLUIR` igual que `documentos()`. Lee **solo los tres primeros bytes** en modo binario. Un archivo cuyo nombre termina en `.md` o es `llms.txt` y empieza por `BOM` añade a `problemas` el texto `Codificación · {rel} empieza con BOM; los documentos se guardan en UTF-8 sin BOM`. Un archivo terminado en `.ps1` que no empieza por `BOM` añade `Codificación · {rel} no empieza con BOM; los scripts .ps1 se guardan en UTF-8 con BOM`. La extensión se compara en minúsculas. `rel` es `os.path.relpath(ruta, raiz)`, como en el resto del verificador. Devuelve el número de archivos revisados. Docstring: qué garantiza y por qué, con la referencia al aprendizaje del 2026-10-01 |
| `main()` | Llama a `verificar_codificacion(raiz)` después de `verificar_identificadores` e imprime la línea `codificación       {n:>5}` con el mismo formato que las demás |

`EXCLUIR` ya contiene `node_modules` y `.venv`. Es imprescindible: en Windows, `npm` crea en `node_modules/.bin/` *shims* `.ps1` sin BOM que harían fallar la comprobación.

Pruebas en `tools/tests/test_verificar_codificacion.py`: una clase `PruebasCodificacion(unittest.TestCase)` que añade `tools/` a `sys.path`, importa `verificar_docs`, vacía `verificar_docs.problemas` en `setUp` y construye cada árbol en un `tempfile.TemporaryDirectory`. Se ejecutan con `python -m unittest discover -s tools/tests -v` desde la raíz.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente.

En las filas de configuración, el rojo es el comando de verificación corrido **antes** del cambio, que falla por la razón esperada (el archivo o la regla no existe); en las filas 5 y 7, el rojo es el archivo desechable que la compuerta todavía no rechaza. Ninguna fila cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): no hay dinero, límites, bloqueo, autorización, inmutabilidad, permisos de rol ni semáforo. Las filas de `ingeniero-devsecops` bajan a `haiku` por la fila de §14.2 «tarea mecánica y verificable por comando… fijar una versión»; el tester conserva `sonnet` porque no baja por debajo de quien verifica.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | Comprobación de codificación en `tools/verificar_docs.py` y sus pruebas en `tools/tests/`. Antes del verde, la suite de la clase en rojo por `AttributeError` (la función no existe). Al terminar, mutación manual de la tabla de mutantes M1 a M4 | TC-01 a TC-05, TC-06, TC-07 | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | `python -m unittest discover -s tools/tests -v` en verde; `python tools/verificar_docs.py` muestra la línea `codificación` y ningún problema de codificación (TC-06); demostración TC-07 con su salida en `impl.md` | ✓ Hecho |
| 2 | `.editorconfig` y `.gitattributes`. Antes de crear `.gitattributes`, `git ls-files --eol` y anotar cuántos archivos están en `i/crlf`. Después, `git add --renormalize .` y `git status --short`: si cambia algún archivo, la normalización va en un commit propio «normaliza finales de línea a LF», separado del resto | TC-08, TC-09 | `ingeniero-devsecops` | `haiku` | `npx --yes editorconfig <ruta absoluta>` sobre `docs/glosario.md`, `tools/verificar_docs.py`, `frontend/src/index.ts` (EditorConfig resuelve por ruta, el archivo no necesita existir) y `.claude/hooks/recordar-caveman.ps1`; `python tools/verificar_docs.py` sin problemas de codificación tras la renormalización | ⚠ Ajustado |
| 3 | `.gitignore` y `.env.example` | TC-10, TC-11, TC-12 | `ingeniero-devsecops` | `haiku` | Los comandos de TC-10 a TC-12 con su salida | ✓ Hecho |
| 4 | `backend/`: `pyproject.toml` con `[project]` solamente, `uv add --dev ruff mypy`, `cimenta/__init__.py`. Rojo previo: `uv sync --locked` en `backend/` falla por falta de `pyproject.toml` | TC-13 | `ingeniero-devsecops` | `haiku` | Desde `backend/`: `uv sync --locked`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, los cuatro con código 0 | ✓ Hecho |
| 5 | Compuertas del backend. El tester crea los desechables de TC-14 a TC-17 bajo `backend/cimenta/desechable_tkt001/` y ejecuta: TC-14 y TC-17 deben estar en rojo (mypy y Ruff aún no rechazan), TC-15 y TC-16 ya rechazan o no por naturaleza. El desarrollador añade `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.mypy]` y el `override`. Se borran los desechables y se aplican los mutantes M5 y M6 | TC-14 a TC-17, y TC-13 de nuevo | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | Salidas de TC-14 a TC-17 en `impl.md`; mypy sin el aviso de banderas por módulo; tras borrar los desechables, `git status --short backend/` no lista nada bajo `desechable_tkt001` y TC-13 sigue en verde | ⚠ Ajustado |
| 6 | `frontend/`: primero `.npmrc`, después `package.json` sin dependencias, después `npm install --save-dev` de `eslint`, `@eslint/js`, `typescript-eslint` y `typescript` según la regla de versiones; luego `tsconfig.json`, `eslint.config.js` y `src/index.ts`. Rojo previo: `npm ci` en `frontend/` falla por falta de `package.json` | TC-18 | `ingeniero-devsecops` | `haiku` | Desde `frontend/`: `npm ci`, `npm run lint`, `npm run typecheck`, los tres con código 0; `package.json` sin `^`, `~`, `*` ni `latest` | ⚠ Ajustado |
| 7 | Compuertas del frontend. El tester crea `frontend/src/desechable_tipos.ts` y `frontend/src/desechable_lint.ts` y ejecuta TC-19 y TC-20; después TC-21 con `engines` alterado temporalmente. Mutantes M7, M8 y M9. Se restauran `package.json` y `.npmrc` y se borran los desechables | TC-19 a TC-21, y TC-18 de nuevo | rojo: `tester-backend` · verde: `ingeniero-devsecops` | tester `sonnet` · verde `haiku` | Salidas en `impl.md`; tras restaurar, TC-18 en verde y `git status --short frontend/src` sin desechables | ✓ Hecho |
| 8 | Documentación: `docs/arranque-local.md` nuevo; `CLAUDE.md`, `README.md`, `llms.txt`, `docs/convenciones.md` §3, `docs/06-stack-tecnologico.md` §9 y `tools/README.md` según «Documentación afectada» | TC-22, TC-23, TC-24 | Orquestador, con `conv-documentacion`, por sustitución: no hay agente redactor de documentación ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)) | `haiku` | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` con el criterio de TC-22; búsqueda de TC-23 | ✓ Hecho |
| 9 | Arranque en dos copias limpias. Cada copia se construye copiando con su ruta relativa los archivos que lista `git ls-files --cached --others --exclude-standard` a `<scratchpad>/tkt001-a` y `<scratchpad>/tkt001-b`: así no viajan `.venv`, `node_modules` ni cachés. En cada copia se corre la fila 4 y la fila 6 completas; después TC-25 y TC-26 | TC-13 y TC-18 en copia limpia, TC-25, TC-26 | `ingeniero-devsecops` | `haiku` | Salidas de las dos copias en `impl.md`, con fecha, sistema operativo, versión de `uv`, de Python y de Node | ✓ Hecho |

**Modelo:** `haiku` por omisión; ninguna fila cita disparador de `sonnet` para el desarrollador. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Cómo se ejecuta |
|---|---|---|---|---|
| TC-01 | `test_tkt001_ca7_arbol_correcto_sin_problemas`: un `.md` sin BOM, `llms.txt` sin BOM y un `.ps1` con BOM; `verificar_codificacion` devuelve 3 y `problemas` queda vacío | feliz | `CA-7` | `unittest` |
| TC-02 | `test_tkt001_ca7_esc01_markdown_con_bom_se_detecta`: `docs/nota.md` con BOM; `problemas` tiene **un** elemento que contiene `os.path.join("docs", "nota.md")` y `empieza con BOM` | **rechazo** | `CA-7` esc. 1 | `unittest` |
| TC-03 | `test_tkt001_ca7_esc02_powershell_sin_bom_se_detecta`: `.claude/hooks/h.ps1` sin BOM; un elemento con su ruta y `no empieza con BOM` | **rechazo** | `CA-7` esc. 2 | `unittest` |
| TC-04 | `test_tkt001_ca7_directorios_excluidos_no_se_revisan`: `node_modules/.bin/x.ps1` sin BOM y `.venv/x.md` con BOM; `problemas` vacío | borde | `CA-7` | `unittest` |
| TC-05 | `test_tkt001_ca7_extension_en_mayusculas_se_revisa`: `NOTA.MD` con BOM se detecta | borde | `CA-7` | `unittest` |
| TC-06 | El repositorio real: `python tools/verificar_docs.py` sin ningún problema `Codificación ·` | regresión | `CA-R1`, `CA-R2` | comando |
| TC-07 | Demostración en el repositorio real: se crea `docs/_desechable_bom.md` con BOM y `.claude/hooks/_desechable.ps1` sin BOM; `python tools/verificar_docs.py` termina con código 1 y nombra **los dos** archivos; se borran y vuelve a TC-06 | **rechazo** | `CA-7` esc. 1 y 2 | comando |
| TC-08 | `npx --yes editorconfig` sobre un `.md`, un `.py` y un `.ts` devuelve `charset=utf-8`, `end_of_line=lf`, `insert_final_newline=true` | feliz | `CA-6` esc. 1 | comando |
| TC-09 | `npx --yes editorconfig` sobre `.claude/hooks/recordar-caveman.ps1` devuelve `charset=utf-8-bom`; y `python -c "print(open('.claude/hooks/recordar-caveman.ps1','rb').read(3).hex())"` imprime `efbbbf` después de la renormalización | regresión | `CA-6` esc. 2, `CA-R1` | comando |
| TC-10 | `git check-ignore -v` sobre `"Doc de contexto/x"`, `.env`, `.env.local`, `.env.production`, `__pycache__/x.pyc`, `node_modules/x`, `backend/.venv/x` y `frontend/node_modules/x`: todos ignorados. `git check-ignore .env.example` termina con código 1 | regresión | `CA-R4` | comando |
| TC-11 | Con un `.env` que contiene `CLAVE=valor` en la raíz: `git add --dry-run .env` falla con «paths are ignored» y `git status --porcelain --ignored .env` lo muestra como `!!`. Se borra el `.env` | **rechazo** | `CA-8` esc. 2 | comando |
| TC-12 | Toda línea no vacía de `.env.example` empieza por `#`, y la cabecera nombra TKT-003, TKT-057 y TKT-059 | feliz | `CA-8` esc. 1 | comando |
| TC-13 | Desde `backend/`: `uv sync --locked`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .` con código 0 | feliz | `CA-1` | comando |
| TC-14 | `cimenta/desechable_tkt001/dominio/regla.py` con `def sumar(a, b): return a + b` (y `__init__.py` en `desechable_tkt001/` y en `dominio/`): `uv run mypy .` termina con código 1 y cita `Function is missing a type annotation  [no-untyped-def]` | **rechazo** | `CA-2` esc. 2 | comando |
| TC-15 | La misma función en `cimenta/desechable_tkt001/aplicacion/regla.py`, con su `__init__.py`: la salida de mypy no contiene `no-untyped-def` para ese archivo | rechazo del falso positivo | `CA-2` esc. 3 | comando |
| TC-16 | `cimenta/desechable_tkt001/formato.py` con `x=1`: `uv run ruff format --check .` termina con código 1 y nombra el archivo | **rechazo** | `CA-2` esc. 1 | comando |
| TC-17 | `cimenta/desechable_tkt001/importaciones.py` con `import sys` antes de `import os`, ambos usados: `uv run ruff check .` termina con código 1 y cita `I001` | **rechazo** | `S1` | comando |
| TC-18 | Desde `frontend/`: `npm ci`, `npm run lint`, `npm run typecheck` con código 0 | feliz | `CA-3` | comando |
| TC-19 | `src/desechable_tipos.ts` con `export function identidad(valor) { return valor; }`: `npm run typecheck` termina con código distinto de 0 y cita `TS7006` y `implicitly has an 'any' type` | **rechazo** | `CA-4` esc. 1 | comando |
| TC-20 | `src/desechable_lint.ts` con `const sinUso = 1;` y `export {};`: `npm run lint` termina con código distinto de 0 y cita `@typescript-eslint/no-unused-vars` | **rechazo** | `CA-4` esc. 2 | comando |
| TC-21 | Con `engines.node` cambiado temporalmente a `">=99.0.0"`: `npm ci` falla con `EBADENGINE` y muestra la versión requerida | **rechazo** | `CA-4` esc. 3 | comando |
| TC-22 | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` con código 0. Única excepción admitida: los enlaces del hub del ticket a artefactos de fases posteriores (`delta.md`) que aún no existen, ver riesgos | regresión | `CA-10` esc. 2, `CA-R3` | comando |
| TC-23 | `README.md`, `llms.txt` y `docs/convenciones.md` §3 nombran `backend/`, `frontend/`, `tools/`, `sdd/` y `.claude/`; el README enlaza `docs/arranque-local.md`; ninguno contiene «sin código todavía» ni «Sin código todavía» | feliz | `CA-10` esc. 1 | comando |
| TC-24 | Cada línea del bloque de comandos de `CLAUDE.md` sin marca está en la tabla de TC-26 como «funciona», y cada línea con marca cita un `TKT-xxx` existente | feliz | `CA-9` esc. 1 | revisión con su tabla en `impl.md` |
| TC-25 | En las dos copias limpias: `uv run ruff --version`, `uv run mypy --version`, `npx tsc --version`, `npx eslint --version` y `npm ls --depth=0` dan salidas idénticas | feliz | `CA-5` | comando |
| TC-26 | En una copia limpia se ejecuta **cada** comando del bloque de `CLAUDE.md`: los no marcados terminan con código 0 y los marcados fallan. Un comando sin marca que falla, o uno marcado que funciona, es hallazgo | **rechazo** | `CA-9` esc. 2 | comando, tabla en `impl.md` |

**Mutación.** El ticket no toca rutas de dinero, límites ni congelado; aun así, cada compuerta se muta para demostrar que el test la vigila de verdad. Cada mutante se aplica, se ejecuta el test indicado, se confirma el rojo y se revierte.

| Mutante | Dónde | Test que debe ponerse rojo |
|---|---|---|
| M1 | En `verificar_codificacion`, invertir la condición de los documentos (`==` por `!=` frente a `BOM`) | TC-01 y TC-02 |
| M2 | Quitar la comprobación de `.ps1` | TC-03 |
| M3 | Comparar la extensión sin pasar a minúsculas | TC-05 |
| M4 | Dejar de podar los directorios de `EXCLUIR` en `verificar_codificacion` | TC-04 |
| M5 | Cambiar el patrón del `override` a `cimenta.dominio.*` | TC-14 (mypy deja de rechazar) |
| M6 | Quitar `"I"` de `select` | TC-17 |
| M7 | `"strict": false` en `tsconfig.json` | TC-19 |
| M8 | `files: ["**/*.js"]` en `eslint.config.js` | TC-20 |
| M9 | Borrar `engine-strict=true` de `.npmrc` con `engines` aún en `">=99.0.0"` | TC-21 (`npm ci` solo advierte y termina con código 0) |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `CLAUDE.md` | Todos los agentes, en cada sesión | Una marca mal puesta lleva a un agente a ejecutar un comando que falla, o a no ejecutar uno que ya funciona | TC-26 ejecuta cada comando en copia limpia |
| `.gitattributes` | Todos los archivos de texto versionados | La renormalización cambia finales de línea en archivos guardados con CRLF y ensucia el diff | Recuento previo con `git ls-files --eol` y commit separado (fila 2) |
| `.claude/hooks/recordar-caveman.ps1` | El hook de cada turno | Una herramienta que reescriba el archivo le quita el BOM y Windows PowerShell 5.1 corrompe los acentos | Ninguna fila edita el archivo; TC-09 y TC-06 comprueban sus bytes |
| `tools/verificar_docs.py` | La regla de cierre de todo cambio de documentación y el futuro pipeline de TKT-009 | La nueva comprobación hace fallar el verificador si algún `.md` ya tiene BOM hoy | TC-06 en la fila 1: si aparece un BOM existente, se le quita en la misma fila y se anota |
| `.gitignore` | `RNF-07` | Un patrón nuevo que ignore de más, por ejemplo `.env.example` | TC-10 comprueba que `.env.example` no se ignora |
| `README.md`, `llms.txt`, `docs/convenciones.md`, `docs/06-stack-tecnologico.md` | Los conteos y enlaces que vigila `verificar_docs.py` | Un enlace o un ancla rotos | TC-22 |

**Fronteras entre módulos:** No. El ticket no crea módulos.

## Documentación afectada

| Documento | Qué cambia |
|---|---|
| `docs/arranque-local.md` (nuevo) | Requisitos (Git, `uv`, Python 3.13 o superior, Node de la línea fijada en `engines` y el npm que trae); arranque del backend y del frontend con los comandos de TC-13 y TC-18; verificadores de `tools/` y cómo correr sus pruebas; la regla de codificación y por qué el `.ps1` lleva BOM; una tabla «Lo que todavía no arranca» con cada comando y el ticket que lo habilita; dónde están las versiones exactas (los archivos de bloqueo, no este documento); y la constancia «verificado en copia limpia el AAAA-MM-DD», que rellena la fila 9 |
| `CLAUDE.md` | Sección «Comandos» reescrita en tres grupos con su directorio —«desde `backend/`», «desde `frontend/`», «desde la raíz»— y precedida de una frase que define la marca. Se añade `uv run ruff format .`, `mypy cimenta/` pasa a `mypy .`, `uv sync` pasa a `uv sync --locked`, y se añaden `npm ci`, `npm run lint`, `npm run typecheck` y los tres comandos de `tools/`. Enlace a `docs/arranque-local.md`. Las marcas, en el formato de la sección siguiente |
| `README.md` | La línea de estado de la cabecera deja de decir «sin código» y pasa a «Entrega 2 en curso». En «Documentación transversal», una fila para el arranque local y otra que enumera la estructura del repositorio (`backend/`, `frontend/`, `tools/`, `sdd/`, `.claude/`) con enlace a convenciones §3. Las secciones históricas de la Entrega 1 no se tocan |
| `llms.txt` | La línea de estado pasa de «Sin código todavía» a «Andamiaje de `backend/` y `frontend/` con sus herramientas de calidad desde TKT-001; sin lógica de negocio todavía», y se añade el enlace al arranque local |
| `docs/convenciones.md` §3 | El árbol incluye `.editorconfig`, `.gitattributes`, `.env.example`, `backend/`, `frontend/`, `tools/`, `sdd/`, `.claude/` y `docs/arranque-local.md`, una línea de comentario por entrada |
| `docs/06-stack-tecnologico.md` §9 | La fila de `tools/verificar_docs.py` añade «documentos con BOM y scripts `.ps1` sin él» a lo que detecta |
| `tools/README.md` | Una fila «Codificación» en la tabla de `verificar_docs.py` y la orden para ejecutar `tools/tests/` |

### Formato de la marca de disponibilidad

- En el bloque de comandos, al final del comentario de la línea, separado por punto medio: `uv run alembic upgrade head      # migraciones · desde TKT-003`.
- En prosa, entre paréntesis y con el enlace al ticket omitido: `(desde TKT-004)`.
- Antes del bloque, una sola frase: «Un comando o una comprobación marcados *desde TKT-xxx* todavía no funcionan: los habilita ese ticket, y su `/sdd-completar` quita la marca».

| Línea | Marca |
|---|---|
| `uv run lint-imports` | `· desde TKT-002` |
| `uv run fastapi dev` | `· desde TKT-002` |
| `uv run pytest` | `· desde TKT-003` `(asumido)`: es el primer ticket cuyos criterios declaran la suite del backend. Si TKT-002 instala pytest antes, su `delta.md` corrige la marca |
| `uv run alembic upgrade head` | `· desde TKT-003` |
| `docker compose up -d db` | `· desde TKT-003`. La línea actual `docker compose up -d db minio` se parte en dos porque cada servicio llega con un ticket distinto |
| `docker compose up -d minio` | `· desde TKT-059` |
| `npm run dev` (sustituye a `npm --prefix frontend run dev`) | `· desde TKT-008` |
| Regla 1, «el linter lo bloquea» | `(desde TKT-004)` |
| Regla 2, «`import-linter` falla el pipeline» | `(desde TKT-002; en el pipeline desde TKT-009)` |
| «Un verificador en CI falla si algún escenario…» | `(desde TKT-009)` |

Las marcas en prosa no cambian ninguna regla: dicen desde cuándo la herramienta la hace cumplir. La regla obliga desde ya.

## ¿Merece ADR?

No. Las elecciones de este ticket —extender `verificar_docs.py` en lugar de crear un script, `unittest` en lugar de pytest para `tools/`, `engines` con `engine-strict` en lugar de `.nvmrc`, el proyecto `uv` sin empaquetar— son configuración reversible en minutos, no arquitectura: ninguna condiciona el diseño de un módulo ni cuesta caro deshacer. Las herramientas las decidió ya el [stack §8](../../../docs/06-stack-tecnologico.md#8-calidad-y-herramientas) y la ubicación del proyecto `uv`, el usuario (`PA-T1`). El porqué de cada una queda en la escalera de arriba, en `docs/arranque-local.md` y en el `delta.md`.

## Decisiones sobre las preguntas abiertas

| # | Decisión |
|---|---|
| `PA-T5` | `.env.example` solo lleva la cabecera, sin ninguna clave. Las claves llegan con TKT-003, TKT-057 y TKT-059 |
| `PA-T6` | `requires-python = ">=3.13"` sin techo; `python_version = "3.13"` en mypy; sin `.python-version`. Las versiones de cada herramienta siguen la regla determinista de «Versiones» y quedan en los archivos de bloqueo |
| `PA-T7` | Gestor `npm`. Node fijado solo con `engines` (la línea LTS más reciente, se espera la 24) más `engine-strict=true` en `frontend/.npmrc`; sin `.nvmrc` |
| `PA-T8` | Sin script nuevo: la función `verificar_codificacion` se añade a `tools/verificar_docs.py` y se invoca con `python tools/verificar_docs.py`. Comprueba que los `.md` y `llms.txt` no empiezan por `EF BB BF` y que los `.ps1` sí. Se prueba con `unittest` en `tools/tests/`, más la demostración TC-07 sobre el repositorio real |

## Pasada adversarial

Pasada del propio arquitecto con el método de `abogado-del-diablo` (modo A); el orquestador puede despacharla de nuevo en el gate.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `tools/verificar_docs.py` ya falla hoy, antes de tocar nada: el hub del ticket enlaza `impl.md` y `delta.md`, que aún no existen. `CA-R3` y `CA-10` esc. 2 piden código 0 y no lo tendrán hasta `/sdd-completar` | TC-22 admite como única excepción los enlaces del hub a artefactos de fases posteriores, listados uno a uno en `impl.md`. Se escala la cuestión de fondo: es un problema del toolkit que afectará a todos los tickets |
| 2 | Alta | `.gitattributes` con `eol=lf` puede reescribir cientos de archivos guardados con CRLF y esconder el cambio real en un diff ilegible | Recuento previo y commit de normalización separado (fila 2) |
| 3 | Media | El modo estricto de mypy se prueba con un desechable, no con los `dominio/` reales | Ya recogido en la spec como criterio de regresión heredado por TKT-002. TC-14 exige además los `__init__.py` intermedios, que son los que hacen que el nombre de módulo coincida |
| 4 | Media | La última TypeScript puede quedar fuera del rango que admite `typescript-eslint` y romper `npm ci` por dependencia par | La regla de versiones fija TypeScript dentro de ese rango |
| 5 | Media | El encargo pedía pytest para el verificador; el diseño usa `unittest` | La escalera para en el peldaño 2: la biblioteca estándar resuelve. pytest las recogerá sin cambios en TKT-009. Se señala en el gate |
| 6 | Media | `cimenta/__init__.py` puede leerse como adelantar TKT-002 | Es el paquete raíz y solo lleva un docstring; sin él `mypy .` no termina en 0 |
| 7 | Media | `CA-8` dice «sin valores», y [`conv-docker`](../../../.claude/skills/conv-docker/SKILL.md) dice que el `.env.example` lleva «valores de desarrollo evidentes» cuando lleguen las claves | No choca en este ticket, que no tiene claves. TKT-003 hereda la tensión y la resuelve en su spec |
| 8 | Baja | `npx --yes editorconfig` descarga un paquete para verificar | Es una verificación puntual, no una dependencia del proyecto; su versión se anota en `impl.md` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| El Node instalado en la máquina del usuario no es de la línea fijada y `engine-strict` impide `npm ci` | Media | Medio | Es el comportamiento buscado; `docs/arranque-local.md` dice qué versión instalar y la fila 9 anota la usada |
| Algún `.md` existente ya tiene BOM y la nueva comprobación lo saca a la luz | Baja | Bajo | Se corrige en la fila 1, con el archivo anotado en `impl.md` |
| Una bandera del `override` de mypy no es por módulo en la versión instalada | Baja | Bajo | Regla escrita en «Configuración del backend»: se retira y se anota |
| Las versiones esperadas del diseño difieren de las reales el día de la ejecución | Media | Bajo | El diseño fija la regla, no el número; el número queda en el archivo de bloqueo |
| La marca de `uv run pytest` (`desde TKT-003`) resulta equivocada | Media | Bajo | Marcada `(asumido)`; la corrige el `delta.md` del ticket que instale pytest |
| La documentación crece más de lo estimado y el ticket supera la talla S | Baja | Medio | Estimación: unas 350 líneas escritas a mano —unas 210 de configuración, verificador y pruebas, y unas 140 de documentación—, sin contar los archivos de bloqueo generados. Por debajo del tope de 400; no se propone partir el ticket |
