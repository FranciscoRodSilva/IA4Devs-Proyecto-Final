# Design · TKT-071 · Mantenimiento de dependencias: mermaid-cli y parches de Dependabot

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (se enlaza en `/sdd-ejecutar`)

## Estrategia

Se cambian cuatro archivos de dependencias con comandos **acotados al paquete**, nunca con una regeneración libre: `npm install --package-lock-only --ignore-scripts --save-exact <paquete>@<versión>` en `.github/mermaid/` y en `frontend/`, y `uv lock --upgrade-package <paquete>==<versión>` en `backend/`. Así cada lock cambia solo en el paquete nombrado y en lo que él arrastra, que es lo que exige CA-5. Antes de tocar nada se captura la evidencia del «antes» (CA-2) y se demuestra que el comando que recorre el lock rechaza una copia anidada vulnerable (CA-3). La prueba TC-65 cambia primero, en rojo, y el lock de `mermaid-cli` la pone en verde. Ninguna fila toca `backend/cimenta/`, `ci.yml` ni configuración de lint: si una versión nueva reporta un hallazgo, se escala.

Todo el diseño se apoya en los cinco experimentos ejecutados el 2026-11-03 en Windows con npm 11.19.1, que se citan como hechos en cada fila.

## Hechos de partida

| # | Comando, ejecutado el 2026-11-03 | Resultado |
|---|---|---|
| H-1 | `uv lock --dry-run --upgrade-package sqlalchemy==2.1.6 --upgrade-package alembic==1.20.1 --upgrade-package ruff==0.17.3`, en `backend/` | Actualiza exactamente esos tres paquetes y nada más (114 resueltos) |
| H-2 | `npm install --package-lock-only --ignore-scripts --save-exact @mermaid-js/mermaid-cli@12.2.0`, en una copia de `.github/mermaid/` | Cambian 4 entradas del lock: `node_modules/@mermaid-js/mermaid-cli`, `node_modules/katex` (pasa a 0.18.10), `node_modules/katex/node_modules/commander` (nueva) y `node_modules/mermaid/node_modules/katex` (desaparece por deduplicación). `npm audit --package-lock-only` queda sin vulnerabilidades |
| H-3 | `npm install --package-lock-only --ignore-scripts --save-exact eslint@10.13.0`, en una copia de `frontend/` | Cambian 22 entradas: `eslint`; sus dependencias propias (`@eslint/config-helpers` 0.5.5 → 0.7.0, `@eslint/plugin-kit` 0.6.1 → 0.7.3, `file-entry-cache` 8 → 11, `flat-cache` 4 → 6, `keyv` 4 → 5, sale `json-buffer`, y entran `cacheable`, `@cacheable/*`, `@keyv/*`, `hashery`, `hookified` y `qified`); y seis entradas nuevas `node_modules/@tailwindcss/oxide-wasm32-wasi/node_modules/*` (`@emnapi/*`, `@napi-rs/wasm-runtime`, `@tybys/wasm-util`, `tslib`). El PR #16 de Dependabot añade exactamente las mismas 16 entradas nuevas |
| H-4 | `npm ci` en la copia con `mermaid-cli` 12.2.0, y `mmdc -p .github/puppeteer-config.json -i <archivo>` sobre los archivos que selecciona el `grep -rl` del pipeline | Valida los 6 archivos. Un diagrama con `A -->> B` termina con código 1. Solo en Windows: en el ejecutor Linux de CI queda `(sin ejecutar)` hasta el PR |
| H-5 | Estado de los PR de Dependabot #22 (`ruff`), #16 (`eslint`), #13 (`sqlalchemy`) y #12 (`alembic`) | Pasaron el pipeline con estas versiones. #12 y #13 solo fallan en «Etiqueta de origen» |

## Decisiones del diseño

**D-1 · CA-1 y CA-3 se comprueban con un comando que recorre `packages`, no con una aserción permanente.** El comando K (ver «Comandos de verificación») lee cada clave de `packages` del lock cuyo último segmento tras `node_modules/` sea `katex`, imprime ruta y versión, y sale con 1 si alguna es anterior a 0.18.2 o si no hay ninguna. Cada ruta instalada es una clave de `packages` en `lockfileVersion` 3, así que no se escapa ninguna copia anidada. Se descartó `npm ls katex --all`: imprime el árbol con copias marcadas `deduped`, no evalúa un umbral de versión y su salida habría que interpretarla. Se descartó una aserción nueva en TC-65 por el peldaño 1 de la escalera: la vigilancia permanente ya existe con tres piezas. TC-65 fija `mermaid-cli` en 12.2.0 exacta, y bajar de versión la pone en rojo. El paso «Auditar el lock de mermaid-cli» de `ci.yml` corre `npm audit` en cada PR. Dependabot vigila el lock cada semana. Un umbral de `katex` dentro de TC-65 duplicaría la base de avisos de GitHub en una prueba estructural y envejecería con el siguiente aviso.

**D-2 · Excepción E-1 de CA-5.** Las seis entradas nuevas bajo `node_modules/@tailwindcss/oxide-wasm32-wasi/node_modules/` que añade H-3 se admiten en el diff de `frontend/package-lock.json` aunque no las arrastre `eslint`. Motivo: son las dependencias empaquetadas de un paquete opcional que solo se instala en `wasm32`; no sube ninguna versión, solo aparecen como entradas que npm normaliza al reescribir el lock; el PR #16 de Dependabot produce exactamente las mismas; y evitarlas exigiría editar el lock a mano, que es peor. La excepción es estrecha: solo entradas **ausentes** en el lock de `Produccion` y **bajo ese prefijo**. Una entrada que ya existía y cambia, o una nueva fuera del prefijo, no la cubre E-1 y detiene la fila. La excepción se registra en `impl.md` con la salida del comando D.

**D-3 · TC-65 se actualiza con un reemplazo literal en todo el archivo.** En `tools/tests/test_definicion_documentacion.py` se reemplaza cada `12.0.0` por `12.2.0` y cada `12_0_0` por `12_2_0`, sin excepción. Hoy `12.0.0` aparece en 20 líneas (23, 50, 143, 638, 667, 1992, 2013, 2513, 2515, 2518, 2521, 2522, 2550, 2572, 2616, 2617, 2618, 3302, 3333 y 3344) y 2 de `12_0_0` (los nombres de las pruebas de las líneas 3332 y 3342). El reemplazo cambia la constante `VERSION_DE_MMDC`, el fragmento esperado `"debe ser la versión exacta '12.2.0'"` y los mutantes `^12.2.0`, `~12.2.0` y `>=12.2.0`, que son los que demuestran CA-7. Los mutantes `12.0.1`, `12.x`, `latest` y `11.12.0` no contienen `12.0.0` y quedan como están: siguen siendo versiones distintas de la exigida. Derivar los literales de la constante abarataría el próximo cambio, pero no lo exige ningún Must: queda fuera.

**D-4 · No se regenera `.cursor/`.** `tools/agentes_cursor.py` solo traduce `.claude/agents/*.md` (líneas 3 a 33); las skills no se copian, se citan por ruta (`.claude/skills/<nombre>/SKILL.md`, líneas 92 a 94). Cambiar `conv-documentacion/SKILL.md` no cambia ningún archivo generado. La fila 9 lo comprueba con `--verificar`.

**D-5 · Un hallazgo nuevo de Ruff, mypy o ESLint se escala, nunca se silencia.** Si `ruff format --check`, `ruff check`, `mypy` o `npm run lint` reportan algo con la versión nueva que no reportaban con la anterior, la fila se detiene y se ejecuta `/sdd-escalar` con el hallazgo, el archivo y la regla. Está prohibido, sin decisión de la persona dueña: `noqa`, `ignore`, `per-file-ignores`, `type: ignore`, `eslint-disable`, desactivar una regla en `eslint.config.js`, reformatear código con `ruff format` y cualquier edición de `backend/cimenta/` o de `frontend/src/`. Que el pipeline de los PR #22 y #16 pasara (H-5) hace esto improbable, no imposible: aquellos PR corrieron cada versión por separado.

**D-6 · Los comandos de esta fila corren en `bash`.** En Windows, el `bash` de Git for Windows. Una redirección `>` de PowerShell escribe UTF-16 y estropea las copias de los lock que se comparan.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `.github/mermaid/package.json` · `@mermaid-js/mermaid-cli` a `12.2.0` | 4 · cambio mínimo | Una línea; la versión exacta la exige TC-65 |
| `.github/mermaid/package-lock.json` | 4 · cambio mínimo | Lo reescribe `npm install --package-lock-only` acotado al paquete; cambian las 4 entradas de H-2 |
| `backend/uv.lock` | 4 · cambio mínimo | `uv lock --upgrade-package` acotado a tres paquetes (H-1). `backend/pyproject.toml` no se toca, por decisión de la persona dueña |
| `frontend/package.json` · `eslint` a `10.13.0` | 4 · cambio mínimo | Una línea de `devDependencies`. `@eslint/js` sigue en 10.0.1, su última versión publicada (non-goal de la spec) |
| `frontend/package-lock.json` | 4 · cambio mínimo | Acotado a `eslint`; las 22 entradas de H-3, con la excepción E-1 (D-2) |
| TC-65 en `tools/tests/test_definicion_documentacion.py` | 4 · cambio mínimo | Reemplazo literal de la versión (D-3). Ninguna aserción nueva |
| Comprobación de CA-1 y CA-3 sobre todas las rutas | 3 · reuso | Lee el `packages` del lock, que ya enumera cada ruta instalada; es un comando de verificación, no un objeto del repositorio (D-1) |
| Comprobación de CA-5 | 3 · reuso | `git show Produccion:<lock>` y una comparación de entradas; no deja nada en el repositorio |
| Aserción permanente de `katex` en TC-65 | 1 · YAGNI, descartada | TC-65, `npm audit` en el pipeline y Dependabot ya vigilan (D-1) |
| Regenerar `.cursor/agents/` | 1 · YAGNI, descartada | El generador no lee skills (D-4) |
| Cinco documentos y la nota del ADR | 4 · cambio mínimo | Sustituir la versión citada; el ADR conserva su texto y suma una nota fechada, por decisión de la persona dueña |

Ningún objeto toca un invariante registrado ni una regla de `CLAUDE.md`. Los invariantes del esquema solo están en riesgo de regresión, y los vigilan CA-R1 y CA-R2.

## Objetos por zona

### Cadena de suministro

| Archivo | Qué cambia | Cómo |
|---|---|---|
| `.github/mermaid/package.json` | `"@mermaid-js/mermaid-cli": "12.2.0"` | Lo escribe `npm install --save-exact` |
| `.github/mermaid/package-lock.json` | Entradas de H-2 y la raíz `""` | `npm install --package-lock-only --ignore-scripts --save-exact @mermaid-js/mermaid-cli@12.2.0` |
| `backend/uv.lock` | `sqlalchemy` 2.1.6, `alembic` 1.20.1, `ruff` 0.17.3 | `uv lock --upgrade-package sqlalchemy==2.1.6 --upgrade-package alembic==1.20.1 --upgrade-package ruff==0.17.3` |
| `frontend/package.json` | `"eslint": "10.13.0"` en `devDependencies` | Lo escribe `npm install --save-exact` |
| `frontend/package-lock.json` | Entradas de H-3 y la raíz `""` | `npm install --package-lock-only --ignore-scripts --save-exact eslint@10.13.0` |

### Pruebas de `tools/`

| Archivo | Qué cambia |
|---|---|
| `tools/tests/test_definicion_documentacion.py` | D-3: `12.0.0` → `12.2.0` y `12_0_0` → `12_2_0` en todo el archivo. Las dos pruebas sobre los archivos reales pasan a llamarse `test_tc65_mermaid_cli_package_json_declara_la_version_exacta_12_2_0` y `test_tc65_mermaid_cli_package_lock_fija_la_version_12_2_0_con_su_integridad` |

## Comandos de verificación

Cada uno se guarda como archivo en un directorio temporal **fuera del repositorio**, que aquí se llama `$ESC`, y se ejecuta con `python -I $ESC/<nombre>.py <argumentos>` desde la raíz del repositorio. Así no hay comillas que escapar en ninguna consola. Las copias del «antes» se sacan en la fila 1 con `git show Produccion:<ruta> > $ESC/<nombre>`, siempre en `bash` (D-6).

**K · `katex` en todas las rutas del lock** (`$ESC/k.py <lock>`). Recorre `packages`; para cada clave cuyo `clave.rsplit("node_modules/", 1)[-1] == "katex"` imprime `ok <ruta> <versión>` o `VULNERABLE <ruta> <versión>`, comparando la tupla de enteros de la versión (sin sufijo `-…`) con `(0, 18, 2)`. Sale con 1 si hay alguna `VULNERABLE` **o si no encontró ninguna entrada `katex`**, para que un lock sin `katex` no pase en verde por vacío; si no, con 0.

**D · Entradas que cambian en un lock npm** (`$ESC/d.py <lock-antes> <lock-después>`). Para cada clave de la unión de los dos `packages`, si la entrada completa difiere (versión, `resolved`, `integrity` o dependencias), imprime `<ruta> <versión-antes> -> <versión-después>`, con `None` donde la entrada no existe. Solo informa: la clasificación la hace la fila.

**U · Paquetes que cambian en `uv.lock`** (`$ESC/u.py <lock-antes> <lock-después>`). Con `tomllib`, construye `{nombre: versión}` de la lista `package` de cada lock e imprime `<nombre> <antes> -> <después>` para cada nombre cuya versión difiere.

**V · Versiones fijadas de CA-4** (`$ESC/v.py`). Lee `backend/uv.lock` con `tomllib`, y `frontend/package-lock.json` y `frontend/package.json` con `json`. Compara `sqlalchemy` = `2.1.6`, `alembic` = `1.20.1`, `ruff` = `0.17.3`, `packages["node_modules/eslint"].version` = `10.13.0` y `devDependencies.eslint` = `10.13.0`. Imprime cada valor real y sale con 1 si alguno no coincide.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd). En las filas de dependencias, el rojo es la comprobación que falla con el lock de `Produccion` y por la razón esperada, como manda la regla «infraestructura sin lógica también tiene rojo».

**Modelo.** Ninguna fila cae en un disparador de [metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho). Las filas 5 y 6 ejecutan las pruebas del disparador de la línea base y de los permisos por rol, pero no los modifican: cambian la versión de la biblioteca que hay debajo, y «fijar una versión» es tarea `haiku` en esa misma tabla. Las filas del tester también van en `haiku`, por la bajada de §14.2 para una tarea mecánica y verificable por comando; ningún desarrollador del ticket va por encima. Se aplica el reintento en `sonnet` de §14.2 si una fila no cierra en dos intentos.

**Parada.** Si una verificación no da lo que la fila espera y la causa no es de entorno, la fila se detiene y se ejecuta `/sdd-escalar`. No se ajusta el comando ni la expectativa para que pase.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Evidencia del antes, sin editar el repositorio.** `npm --version` (se espera 11.19.1; si difiere, se anota y la fila 3 compara su diff con H-2 antes de seguir). Copias en `$ESC` de los tres lock y de los dos `package.json` de `Produccion`. En `.github/mermaid/`: `npm audit --json > $ESC/audit-antes.json; echo $?` y `npm audit --audit-level=high; echo $?`. K sobre el lock actual. Copia sintética en `$ESC/lock-anidado.json` del lock actual, con `node_modules/katex` puesto en `0.18.10` y `node_modules/mermaid/node_modules/katex` puesto en `0.16.47`, y K sobre ella. En `backend/`: `uv lock --dry-run --upgrade` (sin acotar), que solo informa. Recuentos de partida: `uv run pytest -q`, `npm test` en `frontend/` y `python -m unittest discover -s tools/tests`, con su línea de resumen | TC-01, TC-02, TC-03, TC-11a | `ingeniero-devsecops` | `haiku` | `audit-antes.json` nombra `katex` con `GHSA-238p-pmpm-9mq7`, rango `>=0.11.0 <0.18.2`, severidad `low` y nodo `node_modules/katex`; el primer `echo` da distinto de 0 y el segundo, 0. K sobre el lock actual sale con 1 e imprime `VULNERABLE node_modules/katex 0.16.47`. K sobre la copia sintética sale con 1 e imprime `VULNERABLE node_modules/mermaid/node_modules/katex 0.16.47` y `ok node_modules/katex 0.18.10`. `uv lock --dry-run --upgrade` lista más de tres paquetes: es la evidencia de que una regeneración sin acotar violaría CA-5; si lista solo tres, se anota que ese rojo no se pudo mostrar. Todo en `impl.md`, y `git status --porcelain` igual que al empezar | Pendiente |
| 2 | **Rojo de TC-65.** Reemplazo de D-3 en `tools/tests/test_definicion_documentacion.py` | TC-05 (rojo) | `tester-backend` | `haiku` | `grep -c "12\.0\.0"` y `grep -c "12_0_0"` sobre el archivo dan 0. `python -m unittest tools.tests.test_definicion_documentacion -v`: exactamente las dos pruebas renombradas en rojo, con un mensaje que contiene `debe ser '12.2.0'` o `la versión exacta '12.2.0'` y cita `'12.0.0'` como lo encontrado; el resto en verde, incluidos los mutantes de TC-65 | Pendiente |
| 3 | **Verde: lock de `mermaid-cli`.** En `.github/mermaid/`: `npm install --package-lock-only --ignore-scripts --save-exact @mermaid-js/mermaid-cli@12.2.0` | TC-04, TC-05, TC-08a | `ingeniero-devsecops` | `haiku` | La suite de la fila 2 entera en verde. K sobre el lock nuevo sale con 0 e imprime solo `ok node_modules/katex 0.18.10` (o una 0.18.x posterior, que se anota). `npm audit --json` sin vulnerabilidades y sin `katex`, guardado en `$ESC/audit-despues.json`; `npm audit --audit-level=high` en 0. D contra la copia del antes lista exactamente las 4 entradas de H-2 más, si aparece, la raíz `""`. `git diff -U0 Produccion -- .github/mermaid/package.json` cambia una sola línea | Pendiente |
| 4 | **Regresión de diagramas y mutación de CA-7.** En `.github/mermaid/`, `npm ci`. Desde la raíz, en `bash`, el bucle del paso «Diagramas con mermaid-cli» de `ci.yml` (líneas 252 a 264) con `$ESC` en lugar de `$RUNNER_TEMP`. Un archivo `$ESC/invalido.md` con un bloque `mermaid` que contiene `graph TD` y `A -->> B`, procesado con `.github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json -i $ESC/invalido.md -o $ESC/inv.md`. Mutación manual: `.github/mermaid/package.json` con `^12.2.0`, la suite de la fila 2, y reversión | TC-R3a, TC-R3b, TC-06 | `ingeniero-devsecops` | `haiku` | `node_modules/.bin/mmdc --version` da 12.2.0. El bucle valida los 6 archivos y termina en 0. `invalido.md` termina con código 1. Con `^12.2.0`, `test_tc65_mermaid_cli_package_json_declara_la_version_exacta_12_2_0` en rojo con «declara @mermaid-js/mermaid-cli en '^12.2.0'; debe ser la versión exacta '12.2.0'»; tras revertir, `git diff Produccion -- .github/mermaid/package.json` vuelve a la línea de la fila 3 y la suite, a verde. En el ejecutor Linux, `(sin ejecutar)` hasta el PR | Pendiente |
| 5 | **Lock del backend y compuertas.** En `backend/`: `uv lock --upgrade-package sqlalchemy==2.1.6 --upgrade-package alembic==1.20.1 --upgrade-package ruff==0.17.3`; `uv sync --locked --python 3.14`. Después, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports` y `uv run python -m herramientas.verificar_float`. Un hallazgo: D-5 | TC-07 (parte del backend), TC-08b, TC-R2 | `ingeniero-devsecops` | `haiku` | Rojo previo: V sale con 1 con los valores de `Produccion`. Después, U contra la copia del antes imprime exactamente `alembic 1.20.0 -> 1.20.1`, `ruff 0.17.1 -> 0.17.3` y `sqlalchemy 2.1.5 -> 2.1.6`. `git diff Produccion -- backend/uv.lock` no cambia las líneas `version =`, `revision =` ni `requires-python =` de la cabecera. `uv run ruff --version` da `ruff 0.17.3`. Las cinco compuertas en 0, y `lint-imports` informa 15 contratos cumplidos y 0 rotos. `git diff --exit-code Produccion -- backend/pyproject.toml` en 0 | Pendiente |
| 6 | **Suite del backend con las versiones nuevas.** `uv run pytest` en `backend/`, con Docker en marcha. Después, las cuatro pruebas de ciclo de migración por separado: `uv run pytest tests/test_identidad_migracion_ciclo.py tests/test_tkt010_migracion.py tests/test_tkt011_migracion_linea_base.py tests/test_tkt057_migracion.py -v` | TC-R1 | `ingeniero-devsecops` | `haiku` | La línea de resumen de `pytest`, con tantas pruebas pasadas como el recuento de la fila 1 o más, cero fallos y ningún `skipped` nuevo; las cuatro pruebas de ciclo en verde. Un fallo que no estaba en la fila 1 detiene la fila y se escala, sin tocar código ni pruebas | Pendiente |
| 7 | **ESLint del frontend.** En `frontend/`: `npm install --package-lock-only --ignore-scripts --save-exact eslint@10.13.0`; `npm ci`; `npm run lint`, `npm run typecheck`, `npm test`, `npm run tipos:verificar` y `npm run e2e`. Un hallazgo de lint: D-5 | TC-07 (parte del frontend), TC-08c, TC-R5 | `ingeniero-devsecops` | `haiku` | V sale con 0. `git diff -U0 Produccion -- frontend/package.json` cambia solo la línea de `eslint`, y `typescript`, `react-router`, `@types/node` y `@testing-library/jest-dom` conservan su versión. D contra la copia del antes: cada entrada se clasifica en `eslint`, dependencia de `eslint` (la lista de H-3), excepción E-1 o raíz `""`. Rojo de la clasificación: sin E-1, las seis entradas `@tailwindcss/oxide-wasm32-wasi/node_modules/*` quedan sin clasificar; con E-1, todas, y las seis son `None -> <versión>`. Si el total o la lista difieren de H-3, la fila se detiene. Los cinco comandos en 0, y `git diff --exit-code Produccion -- frontend/eslint.config.js` en 0. Si `npm run e2e` no arranca por entorno local (base sin migrar, sin `.env`), se anota la causa y queda `(sin ejecutar)` en local: lo verifica el trabajo `humo` del PR | Pendiente |
| 8 | **Auditoría de dependencias en los tres directorios.** Los pasos del trabajo `dependencias` de `ci.yml` (líneas 280 a 307), en local: `uv export --locked --all-groups --no-emit-project --format requirements.txt -o $ESC/req.txt`, `uv run pip-audit -r $ESC/req.txt --require-hashes --disable-pip --strict -f json -o $ESC/pip-audit.json`, `python tools/severidad_pip_audit.py $ESC/pip-audit.json`, y `npm audit --audit-level=high` en `frontend/` y en `.github/mermaid/` | TC-R4 | `ingeniero-devsecops` | `haiku` | `severidad_pip_audit.py` y los dos `npm audit` terminan en 0. `git diff --exit-code Produccion -- .github/workflows/ci.yml` en 0. Una vulnerabilidad alta nueva, ajena a estos paquetes, detiene la fila y se escala | Pendiente |
| 9 | **Documentación.** Los cambios de «Documentación afectada», con el texto exacto que se fija allí | TC-09, TC-10 | `ingeniero-devsecops` | `haiku` | `grep -n "12\.0\.0\|2\.1\.5"` sobre `docs/06-stack-tecnologico.md`, `tools/README.md` y `.claude/skills/conv-documentacion/SKILL.md` sin coincidencias. `git diff --numstat Produccion -- docs/adr/20261029-vale-para-prosa-en-espanol.md` con 0 líneas borradas. `git diff --name-only Produccion -- sdd/tickets/` solo lista archivos de `sdd/tickets/tkt-071/`. `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en 0. `vale --output=line` sobre los cinco documentos sin alertas. `python tools/agentes_cursor.py --verificar` en 0 | Pendiente |
| 10 | **Cierre.** Suite completa de `tools/`, recuentos frente a la fila 1, y búsqueda de silenciadores en el diff | TC-11b, TC-12 | `tester-backend` | `haiku` | `python -m unittest discover -s tools/tests -v` en verde, con tantas pruebas como en la fila 1 o más. `git diff Produccion` sin líneas añadidas que contengan `noqa`, `type: ignore`, `eslint-disable`, `skip`, `xfail`, `.only`, `ignore =` ni `per-file-ignores`. `git diff --name-only Produccion` solo lista los once archivos de «Impacto» y los de `sdd/tickets/tkt-071/`; ninguno bajo `backend/cimenta/` ni `frontend/src/`. Todo en `impl.md` | Pendiente |

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño.** Unas 40 líneas escritas a mano (una prueba, cinco documentos y dos manifiestos) más los lock generados. Muy por debajo de las 400: no se parte.

**Lo que verifica el PR, no la ejecución.** Las diez comprobaciones requeridas corren en el único PR del ticket, que abre `/sdd-completar`. Allí se cierran los `(sin ejecutar)` de las filas 4 y 7: `mmdc` 12.2.0 en el ejecutor Linux y el humo de Playwright. Tras la fusión, `/sdd-completar` comprueba que la alerta de `katex` y los PR #22, #16, #13 y #12 se cerraron solos (supuesto A-1 de la spec).

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `npm audit --json` sobre el lock de `Produccion` en `.github/mermaid/` nombra `katex`, `GHSA-238p-pmpm-9mq7` y severidad `low`; K da la versión instalada 0.16.47; `--audit-level=high` sale en 0 | **rechazo** | `CA-2` | Fundación, sin historia |
| TC-02 | K sobre la copia sintética con la raíz en 0.18.10 y `node_modules/mermaid/node_modules/katex` en 0.16.47 sale con 1 y nombra la ruta anidada y su versión | **rechazo** | `CA-3` | Fundación |
| TC-03 | K sobre el lock de `Produccion` sale con 1 y nombra `node_modules/katex 0.16.47` | **rechazo** | `CA-3`, `CA-2` | Fundación |
| TC-04 | K sobre el lock nuevo sale con 0; `npm audit --json` sin vulnerabilidades ni `katex` | feliz | `CA-1`, `CA-2` | Fundación |
| TC-05 | Las dos pruebas de TC-65 sobre los archivos reales: en rojo tras la fila 2 y en verde tras la fila 3 | feliz | `CA-7`, `M1` | Fundación |
| TC-06 | Mutante `^12.2.0`: el permanente de `test_tc65_mutantes_package_json_de_mermaid_cli_fija_la_version_exacta` («con acento circunflejo») y la mutación manual del archivo real; los dos nombran `'12.2.0'` | **rechazo** | `CA-7` | Fundación |
| TC-07 | V: las cinco versiones de CA-4; `backend/pyproject.toml` sin cambios | feliz | `CA-4` | Fundación |
| TC-08a | D sobre el lock de `.github/mermaid/`: solo las entradas de H-2 | **rechazo** | `CA-5` | Fundación |
| TC-08b | U sobre `backend/uv.lock`: solo los tres paquetes | **rechazo** | `CA-5` | Fundación |
| TC-08c | D sobre `frontend/package-lock.json`: todo clasificado con la lista de H-3 y E-1; sin E-1 quedan seis entradas sin clasificar; los cuatro paquetes de versión mayor sin cambio | **rechazo** | `CA-5` | Fundación |
| TC-09 | Los cinco documentos sin `12.0.0` ni `2.1.5`; el ADR sin líneas borradas y con la nota; tickets cerrados intactos; `verificar_docs.py`, `extraer_mermaid.py` y Vale en 0 | feliz | `CA-6` | Fundación |
| TC-10 | `agentes_cursor.py --verificar` en 0 tras cambiar la skill | regresión | `CA-6` | Fundación |
| TC-11a, TC-11b | Recuentos de pruebas de backend, frontend y `tools/` antes y después: iguales o mayores | regresión | `CA-R1`, `CA-R5` | Fundación |
| TC-12 | Diff sin silenciadores ni archivos fuera de la lista; nada en `backend/cimenta/` | **rechazo** | `CA-R2`, DoD | Fundación |
| TC-R1 | Suite del backend y las cuatro pruebas de ciclo de migración con SQLAlchemy 2.1.6 y Alembic 1.20.1, contra PostgreSQL real con el rol de aplicación | regresión de invariante | `CA-R1` | Fundación |
| TC-R2 | Las cinco compuertas del backend en 0; 15 contratos; `pyproject.toml` intacto | regresión de invariante | `CA-R2` | Fundación |
| TC-R3a | `mmdc` 12.2.0 valida los 6 archivos del alcance del pipeline | regresión | `CA-R3` | Fundación |
| TC-R3b | Un diagrama con `A -->> B` termina con código 1 | **rechazo** | `CA-R3` | Fundación |
| TC-R4 | `pip-audit` filtrado y `npm audit --audit-level=high` en `frontend/` y `.github/mermaid/` en 0; `ci.yml` intacto | regresión | `CA-R4` | Fundación |
| TC-R5 | `lint`, `typecheck`, `test`, `tipos:verificar` y `e2e` en 0; `eslint.config.js` intacto | regresión | `CA-R5` | Fundación |

El ticket no tiene historia de usuario, así que ninguna prueba nombra un `HDU-xxx`, y `tools/verificar_escenarios.py` no exige ninguna. No hay concurrencia ni bloqueo pesimista.

**Mutación.** No hay ruta de dinero, límite ni congelado. Se mutan los dos oráculos del ticket: el lock que lee K, con la copia sintética de TC-02, y la versión exacta de TC-65, con `^12.2.0` en TC-06. Cada uno debe ponerse en rojo nombrando la ruta o la versión.

## Impacto

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `.github/mermaid/package.json` y su lock | Paso «Diagramas con mermaid-cli» del trabajo `documentacion`; paso «Auditar el lock de mermaid-cli» de `dependencias`; TC-65 | Que `mmdc` 12.2.0 cambie sus argumentos o el formato de `puppeteer-config.json` (A-2 de la spec) | Fila 4 en Windows (H-4); el PR lo prueba en Linux |
| `backend/uv.lock` | Todo el backend, las migraciones y las compuertas de `backend` y `fronteras` | Que SQLAlchemy o Alembic cambien el esquema generado o el ciclo de bajada; que Ruff marque algo nuevo | Filas 5 y 6; D-5 |
| `frontend/package.json` y su lock | Trabajos `frontend`, `contrato-api` y `humo` | Que ESLint 10.13.0 marque algo nuevo | Fila 7; D-5 |
| `tools/tests/test_definicion_documentacion.py` | Trabajo `herramientas` | Que el reemplazo deje un literal suelto y un mutante deje de exigir la versión | Fila 2: recuento de `grep` en 0 y mutantes en verde; fila 4: mutación manual |
| `docs/06-stack-tecnologico.md`, `tools/README.md`, `.claude/skills/conv-documentacion/SKILL.md`, el ADR de Vale | Lectores y agentes que cargan `conv-documentacion` | Ninguno funcional | Fila 9 |

La lista cerrada de archivos que puede cambiar el ticket, fuera de `sdd/tickets/tkt-071/`: los once de esta tabla (los cinco de la cadena de suministro, la prueba, los cuatro documentos y `docs/05-tickets-trabajo.md`, cuya ficha de TKT-071 añadió `/sdd-definir`).

**Fronteras entre módulos:** No. Ningún archivo de `backend/cimenta/` cambia.

## Documentación afectada

| Documento | Línea | Qué cambia |
|---|---|---|
| `docs/06-stack-tecnologico.md` | 144 | La frase pasa a ser: «El bloqueo de dependencias del backend (`backend/uv.lock`) fija SQLAlchemy 2.1.6, dentro de la línea 2.x que se contrata. Lo resolvió TKT-003 y lo actualizó TKT-071.» |
| `docs/06-stack-tecnologico.md` | 470 | `@mermaid-js/mermaid-cli` 12.0.0 → 12.2.0 |
| `docs/06-stack-tecnologico.md` | 495 | `@mermaid-js/mermaid-cli` 12.0.0 → 12.2.0 |
| `tools/README.md` | 16 | Celda de versión `12.0.0` → `12.2.0` |
| `tools/README.md` | 97 | `@mermaid-js/mermaid-cli` 12.0.0 → 12.2.0 |
| `.claude/skills/conv-documentacion/SKILL.md` | 73 | `@mermaid-js/mermaid-cli` 12.0.0 → 12.2.0 |
| `docs/adr/20261029-vale-para-prosa-en-espanol.md` | tras la 65 | Las líneas 33, 49, 57 y 65 no cambian. Se añade al final, separado por una línea en blanco, este párrafo: «**Nota del 2026-11-03 (TKT-071).** `@mermaid-js/mermaid-cli` 12.2.0, publicada el 2026-11-02, declara `katex ^0.18.10`, fuera del rango afectado por GHSA-238p-pmpm-9mq7. TKT-071 fija esa versión en `.github/mermaid/package.json`: el lock ya no contiene ninguna copia de `katex` anterior a 0.18.2 y `npm audit` en `.github/mermaid/` no reporta vulnerabilidades. Las pruebas TC-65 exigen ahora la versión exacta 12.2.0. Lo que este ADR dice de `katex` y de la versión 12.0.0 se conserva tal como era cierto el 2026-10-29.» |

No cambian: `CLAUDE.md`, `docs/02-arquitectura.md`, el índice de ADR (la nota no cambia el estado del ADR), `.github/workflows/ci.yml`, `.github/dependabot.yml` ni ningún artefacto de un ticket cerrado. La casilla de la ficha de TKT-071 en `docs/05-tickets-trabajo.md` la marca `/sdd-completar`.

## ¿Merece ADR?

No. El ticket no toma ninguna decisión de arquitectura nueva: aplica versiones dentro de las líneas ya contratadas y corrige un dato del ADR de Vale con una nota fechada, como decidió la persona dueña. La única elección con alternativas descartadas, la excepción E-1 y la forma de comprobar CA-3, es del ticket y queda en D-1 y D-2 de este diseño y en `impl.md`.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | K es un comando de una sola vez: si mañana alguien baja `mermaid-cli`, nada en el repositorio comprueba `katex` | TC-65 exige 12.2.0 exacta y una bajada la pone en rojo; `npm audit` corre en cada PR y Dependabot vigila el lock. Lo explica D-1 |
| 2 | Alta | La excepción E-1 podría tapar un cambio real bajo `@tailwindcss/oxide-wasm32-wasi` | E-1 solo admite entradas **ausentes** antes y bajo ese prefijo; una entrada existente que cambia detiene la fila. La lista coincide con la del PR #16 (H-3) |
| 3 | Media | Reemplazar `12.0.0` en todo el archivo de pruebas podría tocar otra herramienta con esa versión | `grep` de este diseño: las 20 líneas son todas de `mermaid-cli`. La fila 2 exige recuento 0 y los mutantes en verde |
| 4 | Media | `uv lock` con otra versión de `uv` puede reescribir la cabecera del lock y colar un cambio que U no ve | La fila 5 comprueba que `version`, `revision` y `requires-python` de la cabecera no cambian |
| 5 | Media | Un `>` de PowerShell escribe UTF-16 y las comparaciones fallarían por codificación, no por contenido | D-6: los comandos corren en `bash`; los scripts leen con `encoding="utf-8"` |
| 6 | Media | K pasaría en verde sobre un lock sin ninguna entrada `katex` | K sale con 1 si no encuentra ninguna |
| 7 | Baja | TKT-001 eligió `eslint` 10.0.1 para que coincidiera con `@eslint/js`; 10.13.0 rompe esa coherencia | Ninguna prueba ni convención la exige: la `delta.md` de TKT-001 dejó esa alternativa abierta, y la spec la adopta como non-goal |
| 8 | Baja | `npm install --save-exact` en `frontend/` podría reordenar o reescribir otras líneas de `package.json` | La fila 7 exige que el diff de `package.json` sea una sola línea |

La pasada de `abogado-del-diablo` del orquestador, sobre el diseño ya escrito, no añadió objeciones sustantivas. La revisión de impacto del 2026-11-03 tampoco encontró omisiones: buscó cada versión anterior en todo el repositorio, sin contar los lock ni los tickets cerrados, y todas las coincidencias ya estaban en este diseño. `lint-imports` informó 15 contratos cumplidos y ninguno roto.

## Riesgos

**Pre-mortem.** Supón que el ticket fracasó. Las causas más probables son las que siguen.

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| El registro de npm publicó algo después del 2026-11-03 y el lock regenerado difiere de H-2 o H-3 (por ejemplo, `katex` 0.18.11) | Media | Bajo | D lo muestra. Una versión más nueva de un paquete que arrastra el nombrado se admite y se anota; una entrada sin clasificar detiene la fila |
| `mmdc` 12.2.0 no arranca Chromium en el ejecutor Linux, aunque en Windows funcionó (H-4) | Baja | Alto: el trabajo `documentacion` queda en rojo | Se ve en el PR. Se escala con el registro; no se toca `ci.yml` ni `puppeteer-config.json` sin decisión |
| Ruff 0.17.3, mypy con SQLAlchemy 2.1.6 o ESLint 10.13.0 reportan algo al combinarse | Baja (H-5) | Medio | D-5: se escala, nunca se silencia |
| Un fallo de la suite del backend que ya existía en `Produccion` se atribuye a la actualización | Baja | Medio | La fila 1 deja el recuento de partida; la fila 6 compara contra él |
| `npm run e2e` no se puede ejecutar en local | Media | Bajo | `(sin ejecutar)` en local con su causa; lo verifica `humo` en el PR |
| Otro `npm` que el de H-2 y H-3 normaliza el lock de otra forma | Baja | Bajo | La fila 1 registra `npm --version`; las filas 3 y 7 comparan el diff con el hecho correspondiente |
| Dependabot no cierra sus PR al fusionar | Baja | Bajo | `/sdd-completar` lo comprueba e informa; decide la persona dueña (A-1) |
| `pip-audit` encuentra una vulnerabilidad alta nueva, ajena al ticket, el día de la ejecución | Baja | Medio | La fila 8 se detiene y se escala; no se añade `--ignore-vuln` |
