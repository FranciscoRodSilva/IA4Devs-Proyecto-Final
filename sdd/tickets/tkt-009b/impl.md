# Impl · TKT-009b · Cadena de suministro

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

Las filas B1 a B4 y B7 de la parte b del [diseño común](../tkt-009/design.md#parte-b--cadena-de-suministro). `pip-audit` entra en el grupo `dev`. El filtro `tools/severidad_pip_audit.py` toma la severidad del aviso de GitHub en OSV y falla ante `HIGH`, `CRITICAL` o severidad desconocida. El trabajo `dependencias` de `ci.yml` encadena `uv export`, `pip-audit`, el filtro y `npm audit --audit-level=high`. Dependabot cubre `uv`, `npm` y `github-actions` cada semana. El ADR de severidad, la política de `docs/06` §6.4 y la guía de auditoría local cierran la documentación.

**La fila B5 la ejecutó la persona dueña el 2026-10-29** (ver «Fila B5» abajo). **La fila B6**, el ensayo en el pipeline, la ejecutó la persona usuaria el mismo día con una rama de ensayo y un PR en borrador (ver «Fila B6»). La guía [ajustes-repositorio.md](ajustes-repositorio.md) dejó redactados los comandos y las rondas. Con ellas, todas las filas están hechas y el ticket queda listo para `/sdd-revisar`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-28 | `Hallazgo` lleva un sexto campo, `alias`, con `compare=False` | Imprimir «(CVE-…, PYSEC-…)» sin romper la igualdad de cinco argumentos que fijan las pruebas |
| 2026-10-28 | Una severidad de OSV desconocida o ausente es `DESCONOCIDA` y falla | Extiende el fallo cerrado de `A-3` a valores no reconocidos `(asumido)` |
| 2026-10-28 | `consultar_osv` codifica el identificador con `quote(..., safe="")` | Un identificador con caracteres especiales no altera la URL |
| 2026-10-28 | `comprobar_regla_comun_7` admite el `\|\| true` de `uv run pip-audit` en el trabajo `dependencias` | El diseño pide ese `\|\| true` y a la vez prohíbe todo el resto; la excepción está acotada y tiene sus pruebas |
| 2026-10-28 | Las pruebas de Dependabot viven en `tools/tests/test_definicion_dependabot.py` | `test_definicion_ci.py` ya pasa de 3100 líneas |
| 2026-10-28 | Los tests en rojo de B2, B3 y B4 los escribe `tester-backend` (`sonnet`), no `ingeniero-devsecops` (`haiku`) | La convención de TDD de «Convenciones de código» de `CLAUDE.md` dice que quien escribe el código no toca los tests, y el diseño asignaba ambas cosas a un mismo agente; el orquestador separó el rojo (tester) del verde (desarrollador) |
| 2026-10-28 | El trabajo `dependencias` no ejecuta `npm ci` | `npm audit` lee `package-lock.json`; se comprobó que sale igual sin `node_modules` |
| 2026-10-28 | Fecha del ADR: 20261029 | La mayor entre hoy y la del ADR más reciente |
| 2026-10-29 | Orden del token en B5: se crea activo y sin permisos y se revoca después del empuje | El primer intento no fue concluyente; solo el token activo se probó (GH013) |
| 2026-10-29 | B6 usa stream-json@3.6.0 en lugar de nanoid@3.1.30 | Ese candidato tiene tres avisos altos en la base de avisos de GitHub |
| 2026-10-29 | `Hallazgo.aviso` pasa de «el primer GHSA» a «el GHSA que fija la severidad: el peor de los consultados, con corte en el primer HIGH o CRITICAL» | El primer GHSA dejaba pasar en verde un aviso con un segundo GHSA alto (fallo abierto, hallazgo R-COD-F001 de código); lo decide la corrección, y la persona que aprueba debe confirmarlo (pregunta abierta `A-12` de la [spec](../tkt-009/spec.md)) |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | modificado | herramientas (18 paquetes nuevos en el lock) |
| `tools/severidad_pip_audit.py` | nuevo | herramientas |
| `tools/tests/test_severidad_pip_audit.py` | nuevo | pruebas |
| `tools/tests/test_definicion_ci.py` | modificado | pruebas |
| `tools/tests/test_definicion_dependabot.py` | nuevo | pruebas |
| `tools/tests/_ayudantes.py` | nuevo (ciclo 1 de revisión) | pruebas |
| `.github/workflows/ci.yml` | modificado | entrega continua |
| `.github/dependabot.yml` | nuevo | entrega continua |
| `docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md`, `docs/adr/README.md` | nuevo, modificado | documentación |
| `docs/06-stack-tecnologico.md`, `docs/arranque-local.md`, `docs/05-tickets-trabajo.md`, `tools/README.md`, `CLAUDE.md`, `README.md`, `llms.txt` | modificado | documentación |
| `sdd/tickets/tkt-009/design.md` | modificado | estados de las filas |
| `sdd/tickets/tkt-009b/ajustes-repositorio.md` | nuevo | guía para B5 y B6 |

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-30 | `test_tc30_*` (6) | **rechazo** | `CA-10` esc. 2 | FALLA | PASA |
| TC-31 | `test_tc31_*` (2) | **rechazo** | `CA-10` esc. 2 | FALLA | PASA |
| TC-32 | `test_tc32_*` (3) | **rechazo** (bloqueo de más) | `CA-10` esc. 3 | FALLA | PASA |
| TC-33 | `test_tc33_*` | feliz | `CA-10` esc. 3 | FALLA | PASA |
| TC-34 | `test_tc34_*` (4) | **rechazo** | `CA-10` esc. 2 | FALLA | PASA |
| TC-35 | `test_tc35_*` (3) | feliz | `CA-10` esc. 1 | FALLA | PASA |
| TC-36, TC-37 | `test_tc36_*` (4), `test_tc37_*` (4) | **rechazo** | `CA-10` | FALLA | PASA |
| TC-38 | `test_tc38_*` (3) | feliz | `CA-10` | FALLA | PASA |
| TC-14 | `test_tc14_*` (3, más 12 de mutantes sintéticos) | estático | `CA-10` esc. 1 | FALLA | PASA |
| TC-15 | `test_tc15_*` (1, más 8 de mutantes) | estático | `CA-11` esc. 1 | FALLA | PASA |
| TC-18 | `test_tc18_*` (4, más mutantes) | **rechazo** (estático) | `CA-11` esc. 3, `CA-R3` | Nace en verde, ver abajo | PASA |
| TC-R2a | `git diff` de `pyproject.toml` | regresión | `CA-R2` | `pip-audit --version` falla | `15 kept, 0 broken` |
| TC-16, TC-17 | Manuales | **rechazo** | `CA-11` esc. 2, `CA-R3` esc. 2 | Intento 1 no concluyente: el archivo empujado contenía un comando, no un token | PASAN con un token activo sin permisos: `GH013` (B5) |
| TC-11a, TC-11b | Ensayo en el pipeline | **rechazo** | `CA-10` esc. 2 y 3 | — | PASAN: ronda 1 en rojo, ronda 2 en verde (B6) |

**Los casos de TC-18 sobre el repositorio real nacen en verde, y se investigó.** El invariante ya se cumple: `.github/` solo tiene `workflows/ci.yml`, sin exclusiones ni `secrets.`. Para que no sean vacuos, el lector exige que `ci.yml` exista y sus mutantes sintéticos (`paths-ignore` con `.env.example`, un `secret_scanning.yml`, `secrets.X`) sí los ponen en rojo.

**Cifras tras los ciclos 1 a 3 de revisión.** `tools/tests/test_severidad_pip_audit.py` tiene 78 pruebas (30 `test_tc` originales y 48 `test_ca10_*` añadidas en la revisión: 40, 7 y 1 de los ciclos 1, 2 y 3; por prefijo, 2 `test_ca10_esc01_`, 12 `test_ca10_esc02_`, 2 `test_ca10_esc03_` y 32 `test_ca10_a3_`) y `tools/tests` suma 295, de las cuales 24 son de Dependabot. El ciclo 1 añadió el módulo auxiliar `tools/tests/_ayudantes.py` y tocó `tools/tests/test_definicion_ci.py`, `tools/tests/test_definicion_dependabot.py` y `tools/tests/test_severidad_pip_audit.py`. El filtro evalúa ahora todos los `GHSA` de un hallazgo, captura también `http.client.HTTPException` y `RecursionError`, valida que los alias sean cadenas, lee a lo sumo 1.000.000 de bytes de la respuesta de OSV y pasa `mypy --strict`.

### Ciclo TDD por fila

#### Fila B1 · `pip-audit` en el grupo `dev`

**Rojo:**

```
uv run pip-audit --version
error: Failed to spawn: `pip-audit`
  Caused by: program not found
```

**Verde:** `uv add --dev pip-audit --python 3.14` instala `pip-audit 2.10.1` y 17 paquetes más. `uv sync --locked --python 3.14` sale con 0 y `uv run lint-imports` da `Contracts: 15 kept, 0 broken`. El diff de `pyproject.toml` es una línea del grupo `dev`:

```
+    "pip-audit>=2.10.1",
```

**Refactor:** sin refactor.

#### Fila B2 · `tools/severidad_pip_audit.py`

**Rojo** (`python -m unittest tools.tests.test_severidad_pip_audit -v`): 29 pruebas, todas con `AssertionError: falta tools/severidad_pip_audit.py: el módulo bajo prueba todavía no existe`, y `FAILED (failures=33)` contando los subtests. El resto de la suite (178) seguía en verde.

**Verde:** 29 en verde a la primera. El desarrollador escribió el módulo entero de una vez y no caso a caso; consta aquí para que se valore como ejecución de bloque. Después, `Ran 207 tests ... OK`.

**Refactor:** formato y `ruff` limpios.

**Tests devueltos al tester:** ninguno. El desarrollador informó de dos errores de `ruff` en el propio archivo de pruebas; los corrigió el tester, sin cambiar lo que comprueba ninguna prueba.

**Mutación** (script en el directorio temporal; el módulo se restauró tras cada mutante y se comprobó con `cmp`):

| Mutante | Resultado |
|---|---|
| `SEVERIDADES_QUE_FALLAN` sin `CRITICAL` | Rojo: `test_tc31_critical_termina_en_1_con_etiqueta_critica` y `test_tc31_severidades_que_fallan_es_high_y_critical` |
| `DESCONOCIDA` informativa | Rojo: los dos `test_tc34` de `main` |
| Informe ilegible sale con 0 | Rojo: cuatro `test_tc36` |
| La excepción de red pasa o la consulta fallida sale con 0 | Rojo: `test_tc37_error_de_red_en_la_consulta_termina_en_2` y `test_tc37_error_de_consulta_no_se_oculta_tras_un_alto_ya_visto` |
| Consultar OSV con el identificador `PYSEC` | Rojo: cinco pruebas de `test_tc30` y `test_tc38` |
| Sin `HIGH`; `main` siempre en 0; hallazgo sin `GHSA` como `LOW` | Rojo en cada caso |
| **Quitar `.upper()` a la severidad de OSV** | **Sobrevivió.** El tester añadió `test_tc32_la_severidad_en_minusculas_se_normaliza_y_no_falla`, que lo mata; la clase pasa a 30 pruebas |

**Sobre el árbol real** (desde `backend/`): `uv export` → 111 paquetes; `pip-audit` → `No known vulnerabilities found`; el script → `Sin vulnerabilidades en el informe de pip-audit.`, código 0. Con un informe de `django 3.2` contra OSV real, el script da `CRÍTICA ... → falla el pipeline (RNF-08)` y código 1. El supuesto `A-3` se comprobó: `database_specific.severity` existe en los tres `GHSA` consultados.

#### Fila B3 · trabajo `dependencias`

**Rojo** (`python -m unittest tools.tests.test_definicion_ci.DefinicionDeCIFilaB3`):

```
FAIL: test_tc14_dependencias_corre_en_paralelo_sin_needs
AssertionError: False is not true : el ci.yml no declara el trabajo `dependencias` (TKT-009b fila B3)
Ran 3 tests ... FAILED (failures=3)
```

Además, 12 pruebas sobre texto sintético (control, formas válidas y mutantes: paso comentado o movido, `--omit=dev`, `\|\| true` fuera de lugar, `if` ausente, `continue-on-error`, tubería sin `shell: bash`) que nacen en verde por construcción.

**Verde:** `Ran 90 tests ... OK` en `test_definicion_ci`, `Ran 223 tests ... OK` en toda la suite, sin `skipped=`. `uvx zizmor@1.31.1 --offline .github/workflows` → `No findings to report` (1 suprimido: una nota de concurrencia que solo aparece con `--persona pedantic`; ya estaba antes de este ticket). `npm audit --audit-level=high` desde `frontend/` sale con 0 e informa 3 avisos `low` (`deepmerge` vía `shadcn`, una devDependency).

**Mutación sobre la propia comprobación `comprobar_tc14`:** 14 puntos neutralizados y cada uno puso en rojo al menos una prueba. Sobrevivientes: ninguno.

#### Fila B4 · `.github/dependabot.yml`

**Rojo:** `test_tc15_dependabot_declara_uv_npm_y_github_actions_semanales` falla con `No existe .github\dependabot.yml: la fila B4 de TKT-009b todavía no lo crea`; `Ran 24 tests ... FAILED (failures=1)`.

**Verde:** 24 en verde, y `Ran 247 tests ... OK` en toda la suite. `uvx check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml` → `ok -- validation done`; con `interval: "weekl"` la validación lo rechaza (control negativo).

#### Fila B7 · documentación y ADR

`python tools/verificar_docs.py` → `✓ Sin problemas.` con 25 ADR y 159 archivos revisados de codificación. Los comandos de `docs/arranque-local.md` se ejecutaron tal cual: `Sin vulnerabilidades en el informe de pip-audit.`, código 0.

#### Fila B5 · ajustes del repositorio (los ejecutó la persona dueña)

**Estado antes** (`gh api repos/FranciscoRodSilva/IA4Devs-Proyecto-Final --jq '{visibility, security_and_analysis}'`): repositorio `public`, `secret_scanning` y `secret_scanning_push_protection` ya en `enabled`, `dependabot_security_updates` en `disabled`.

**Ajustes aplicados:** `PUT .../vulnerability-alerts` y `PUT .../automated-security-fixes`, ambos sin salida (204). El `PATCH` de la guía no se ejecutó porque los dos ajustes de secretos ya estaban activos.

**Estado después:**

```
dependabot_security_updates          enabled
secret_scanning                      enabled
secret_scanning_push_protection      enabled
secret_scanning_non_provider_patterns disabled
secret_scanning_validity_checks      disabled
visibility                           public
```

**Empuje de ensayo, intento 1: no concluyente.** El empuje de `ensayo/tkt-009b-secreto` fue aceptado, y `GET .../secret-scanning/alerts` devolvió una lista vacía tanto justo después como unos minutos más tarde. La causa quedó establecida cuando el auditor de seguridad leyó el archivo empujado en la rama remota: la línea `TOKEN=` contenía un comando de PowerShell pegado por error, no un token. Lo empujado no tenía forma de token, así que el intento no prueba nada sobre la protección, y no está demostrado cómo trata a un token revocado. **Consecuencia para la guía:** el único procedimiento verificado es el del intento 2, con un token activo y sin permisos, revocado justo después del empuje.

**Empuje de ensayo, intento 2 (token personal clásico activo y sin permisos): rechazado.** Extracto del registro, sin el token ni la URL de desbloqueo:

```
remote: error: GH013: Repository rule violations found for refs/heads/ensayo/tkt-009b-secreto2.
remote: - GITHUB PUSH PROTECTION
remote:     - Push cannot contain secrets
remote:       —— GitHub Personal Access Token ——
remote:          - commit: a2a01501c0982c2cd87a14451c58705b73ebfb72
remote:            path: ensayo-secreto.txt:2
 ! [remote rejected] ensayo/tkt-009b-secreto2 -> ensayo/tkt-009b-secreto2 (push declined due to repository rule violations)
```

Se pidió y se aprobó el cambio de orden: el token se creó activo y sin permisos, y se revoca justo después del empuje. Como el empuje se rechazó, el secreto no llegó a quedar en GitHub en el intento 2. En el intento 1 sí llegó la rama `ensayo/tkt-009b-secreto`, pero con un comando de PowerShell y no con un token. Esa rama sigue en `origin`, en el commit `0c3a99e`, pendiente de que la persona dueña la borre; no contiene ningún token.

#### Fila B6 · ensayo en el pipeline (lo ejecutó la persona usuaria)

La rama `ensayo/tkt-009b-compuertas` y el PR en borrador [#7](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/7), hacia `tkt-009b-cadena-suministro`, se prepararon el 2026-10-29. Los tres commits se comprobaron antes en local, y los empujó la persona usuaria en dos tiempos para que cada ronda tuviera su propia ejecución. Las violaciones nunca se fusionan.

**Comprobación local previa.** Ronda 1: el filtro sale con 1 y `npm audit --audit-level=high` sale con 1. Ronda 2: el filtro sale con 0 y `npm audit` sale con 0, informando un aviso moderado. `nanoid@3.1.30`, el candidato original, se descartó porque la base de avisos de GitHub le asigna tres avisos altos; lo sustituye `stream-json@3.6.0`, con un único aviso medio (`GHSA-jj87-hc4r-jwfw`).

| Ronda | Commit | Ejecución | Resultado | Trabajo en rojo |
|---|---|---|---|---|
| 1 · `django==3.2` y `lodash@4.17.20` | `77e6fb2` | [40892962684](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40892962684) | `failure` | Solo `dependencias`; los otros ocho trabajos en verde |
| 2 · revertida la ronda 1 y `stream-json@3.6.0` | `1d6e937` | [40893078834](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40893078834) | `success` | Ninguno; los nueve trabajos en verde |

**Pasos del trabajo `dependencias`.**

| Paso | Ronda 1 | Ronda 2 |
|---|---|---|
| Auditar Python con pip-audit | `success` (lleva `\|\| true`) | `success` |
| Filtrar los hallazgos por severidad | **`failure`** | `success` |
| Auditar npm | **`failure`** | `success` |

**Extracto del paso «Filtrar los hallazgos por severidad», ronda 1:**

```
CRÍTICA  django 3.2  GHSA-xpfp-f569-q3p2 (CVE-2021-35042, BIT-django-2021-35042, PYSEC-2021-109) → falla el pipeline (RNF-08)
ALTA  django 3.2  GHSA-53qw-q765-4fww (CVE-2021-45115, BIT-django-2021-45115, PYSEC-2022-1) → falla el pipeline (RNF-08)
Hallazgos: 65 · que fallan el pipeline: 40
##[error]Process completed with exit code 1.
```

**Extracto del paso «Auditar npm», ronda 1:**

```
lodash  <=4.17.23
Severity: high
4 vulnerabilities (3 low, 1 high)
##[error]Process completed with exit code 1.
```

**Ronda 2, pasos «Filtrar los hallazgos por severidad» y «Auditar npm»:**

```
Sin vulnerabilidades en el informe de pip-audit.
stream-json  2.0.0 - 3.6.0
Severity: moderate
4 vulnerabilities (3 low, 1 moderate)
```

El aviso moderado queda informado en el registro y el trabajo termina en verde (`CA-10` esc. 3). Ningún registro contiene `ghp_` ni `github_pat_`. El PR #7 se cerró sin fusionar el 2026-10-29 y su rama `ensayo/tkt-009b-compuertas` ya no existe en `origin`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| B1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B2 · rojo | `ingeniero-devsecops` | `haiku` | `tester-backend` · `sonnet` | La convención de TDD de «Convenciones de código» de `CLAUDE.md` dice que quien escribe el código no toca los tests, y el diseño asignaba ambas cosas a un mismo agente; el orquestador separó el rojo (tester) del verde (desarrollador) |
| B2 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B2 · mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| B3 · rojo | `ingeniero-devsecops` | `haiku` | `tester-backend` · `sonnet` | La convención de TDD de «Convenciones de código» de `CLAUDE.md` dice que quien escribe el código no toca los tests, y el diseño asignaba ambas cosas a un mismo agente; el orquestador separó el rojo (tester) del verde (desarrollador) |
| B3 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B4 · rojo | `ingeniero-devsecops` | `haiku` | `tester-backend` · `sonnet` | La convención de TDD de «Convenciones de código» de `CLAUDE.md` dice que quien escribe el código no toca los tests, y el diseño asignaba ambas cosas a un mismo agente; el orquestador separó el rojo (tester) del verde (desarrollador) |
| B4 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B7 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Auditoría de arquitectura y corrección | `auditor-arquitectura`, `corrector-revision` | `sonnet`, `haiku` | `sonnet`, `haiku` | — |

Tres pasos subieron de modelo: el rojo de B2, B3 y B4 pasó de `haiku` a `sonnet` al encargarse a `tester-backend`, por la convención de TDD de «Convenciones de código» de `CLAUDE.md` que consta en «Ajustes respecto al design». Ningún paso subió de modelo por no cerrar tras dos intentos. B5 y B6 las ejecutaron personas, no agentes; la fila B6 del diseño asignaba `git-entrega` y no se usó.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-10` esc. 1 | `[M]` | Cumplido | TC-35 y TC-14; la cadena real da código 0 |
| `CA-10` esc. 2 y 3 | `[M]` | Cumplido | TC-30 a TC-34 en verde; ensayo en el pipeline: ronda 1 en rojo y ronda 2 en verde con el aviso informado (B6, TC-11a y TC-11b) |
| `CA-11` esc. 1 y 3 | `[M]` | Cumplido | TC-15 y TC-18 |
| `CA-11` esc. 2 | `[M]` | Cumplido | Consulta de `gh api` con los dos ajustes en `enabled`; empuje de ensayo rechazado con `GH013` (B5, TC-16 y TC-17) |
| `CA-R2` | `[M]` | Cumplido | El diff de `pyproject.toml` es una línea del grupo `dev`; `15 kept, 0 broken` |
| `CA-R3` | `[M]` | Cumplido | Esc. 1 por TC-18 y TC-22; esc. 2 por el empuje rechazado de B5 |
| `CA-R4` | `[M]` | Cumplido | La suite de `tools/` pasa de 178 a 295 pruebas sin quitar ninguna ni añadir `skip` |
| `CA-15` su parte | `[M]` | Cumplido | `docs/06` §6.4 y los textos de la auditoría; TC-70b sin marcas que retirar |

Un Must incumplido **no se aprueba**. Con B5 y B6 hechas, no queda ningún Must pendiente.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `REQUIERE CAMBIOS` en ambas pasadas; sus cuatro Menores (F001 a F004) están corregidos y verificados con `verificar_docs.py`, sin una tercera reauditoría | 4 Menores (F001 a F004) y la observación O3 | 2 en la ejecución; la revisión lleva sus propios ciclos (ver «Revisión») |
| `auditor-sql` | No aplica | No hay esquema ni migración | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `sdd/tickets/tkt-009b/ajustes-repositorio.md:134` | Atribuía al paso de `pip-audit` la lista de vulnerabilidades, que sale en el paso del filtro | Resuelto (confirmado por la reauditoría) |
| F002 | arquitectura | Menor | `sdd/tickets/tkt-009b/impl.md:3` | El enlace a `delta.md`, que aún no existe, rompía `verificar_docs.py`, y la cifra de archivos estaba desactualizada | Resuelto: el enlace pasa a «delta (pendiente)» y la cifra es 159; `verificar_docs.py` da `✓ Sin problemas.` |
| F003 | arquitectura | Menor | `sdd/tickets/tkt-009b/impl.md`, «Modelo por paso» | Decía que la fila B6 quedaba para `git-entrega`, cuando la ejecutó la persona usuaria | Resuelto |
| F004 | arquitectura | Menor | `docs/05-tickets-trabajo.md:382` y fila B5 del diseño | Pedían «token revocado», pero el único procedimiento verificado usa un token activo y sin permisos | Resuelto |
| O3 | arquitectura | Observación | `tools/tests/test_definicion_ci.py` | El archivo está sin formatear desde antes de este ticket | Persiste, fuera de alcance |

Observaciones del auditor que no bloquean: el filtro solo consultaba el primer `GHSA` de un hallazgo (corregido en el ciclo 1 de revisión: ahora evalúa todos); `zizmor` no estaba instalado en su entorno (la salida en 0 la confirmó la ejecución con `uvx` de esta sesión); `nanoid@3.1.30` resultó no servir para la ronda 2 (tres avisos altos); el candidato pasa a ser `stream-json@3.6.0`, con un único aviso medio confirmado el 2026-10-29.

### Revisión (`/sdd-revisar`, 2026-10-29)

**Suite ejecutada en la revisión.**

| Comprobación | Resultado |
|---|---|
| Backend, `uv run pytest` | `1138 passed in 240.71s (0:04:00)` |
| `uv run ruff check .` | `All checks passed` |
| `uv run ruff format --check .` | `153 files already formatted` |
| `uv run mypy .` | `Success` en 153 archivos |
| `uv run lint-imports` | `15 kept, 0 broken` |
| `uv run python -m herramientas.verificar_float` | 18 archivos, 0 hallazgos |
| `python tools/verificar_docs.py` | `Sin problemas` |
| `python -m unittest discover -s tools/tests` | 295 pruebas, `OK`, sin `skipped` |
| `zizmor@1.31.1 --offline` | `No findings` |
| `verificar_escenarios` | exigidos 0, cubiertos 0, faltan 0, pendientes 162 (ninguna historia activa) |

**Auditorías de la revisión, por ciclo.** Los identificadores de la revisión llevan el prefijo `R-` y el del auditor (`R-ARQ-`, `R-COD-`, `R-SEG-`, `R-DOC-`), de modo que ninguno se repite entre auditores ni se confunde con F001 a F004 de la ejecución. Los auditores numeran por su cuenta en cada pasada y la reauditoría 3 reutilizó F002 y F003 de arquitectura, así que esos identificadores llevan el sufijo `-r3`. Nada de lo que sigue es un veredicto definitivo: son hechos fechados el 2026-10-29, y el ciclo 3 espera su verificación.

* **Auditoría inicial de la revisión.** Arquitectura `REQUIERE CAMBIOS` (R-ARQ-F003 y R-ARQ-F004, Menores). Código `REQUIERE CAMBIOS`: R-COD-F001 y R-COD-F002 Mayores (fallo abierto con varios `GHSA` y `HTTPException` sin capturar), R-COD-F004 Mayor (13 mutantes vivos), R-COD-F003, R-COD-F005 y R-COD-F006 Menores. Seguridad `REQUIERE CAMBIOS`: R-SEG-F001 y R-SEG-F002 `MEDIA`, R-SEG-F003 a R-SEG-F007 `BAJA`. Documentación `REQUIERE CAMBIOS`: R-DOC-F001 y R-DOC-F002 Mayores, R-DOC-F003 a R-DOC-F010 Menores.
* **Ciclo 1 de corrección.** Pruebas en rojo en `25ac431` (25 fallos del ejecutor, subpruebas incluidas, de 16 métodos), código en `c94ceb4` y documentación en `5d6c7c4`.
* **Ciclo 1 de reauditoría.** Seguridad `APROBADO`, sin hallazgos que bloqueen; queda la tarea de la persona dueña de borrar la rama remota `ensayo/tkt-009b-secreto`, que no contiene token. Código `REQUIERE CAMBIOS`: R-COD-F007 Mayor (huecos de prueba del orden de severidades), R-COD-F008 y R-COD-F009 Menores. Arquitectura `REQUIERE CAMBIOS`: R-ARQ-N1 (renombrar las pruebas por escenario) y R-ARQ-N2 (las tablas de esta sección). Documentación `REQUIERE CAMBIOS`: R-DOC-F011 Mayor y R-DOC-F012 a R-DOC-F016.
* **Ciclo 2 de corrección.** `039b5d4` (7 pruebas nuevas del orden de severidades, los empates y los bordes del tope) y `ad7e261` (pruebas nombradas por escenario y documentación al día).
* **Ciclo 2 de reauditoría.** Código `REQUIERE CAMBIOS`: R-COD-N1 Menor (no se fijaba qué `GHSA` decide en un hallazgo `DESCONOCIDA`) y las observaciones R-COD-O1 a R-COD-O3. Arquitectura `REQUIERE CAMBIOS`: R-ARQ-N3 a R-ARQ-N6, Menores. Documentación `REQUIERE CAMBIOS`: R-DOC-F011 persiste y R-DOC-F017, R-DOC-F018 y R-DOC-F019 son Mayores; R-DOC-F020 es Menor.
* **Ciclo 3 de corrección** (`e77d91b` y esta pasada de documentación). La reauditoría 3 aportó R-DOC-F021 (Mayor), R-DOC-F022 y R-DOC-F024 (Menores), R-ARQ-F002-r3 y R-ARQ-F003-r3, la observación R-ARQ-O-a-r3, la observación R-DOC-O-A-r3 y las observaciones de código R-COD-O4 y R-COD-O5. Esta pasada de documentación los atiende (tabla siguiente) y sigue pendiente de verificación.
* **Estado de seguridad.** Su reauditoría fue la del ciclo 1 y dio `APROBADO`, sin hallazgos que bloqueen. No se reauditó tras los ciclos 2 y 3 porque solo cambiaron documentación, nombres de pruebas y una prueba nueva (`test_ca10_esc02_empate_de_dos_ghsa_sin_severidad_conserva_el_primero_como_aviso`), y el código de producción del filtro no cambió desde `c94ceb4` salvo docstrings.
* **Docstrings.** Los docstrings de `Hallazgo.aviso`, de `_peor` y del módulo de `tools/severidad_pip_audit.py` se ajustaron en el ciclo 3 y se commitean con esta pasada; no cambia ninguna línea de lógica.

| Auditor · ciclo | ID | Severidad | Hallazgo | Estado |
|---|---|---|---|---|
| código · reauditoría 1 | R-COD-F007 | Mayor | Huecos de prueba del orden de severidades | Resuelto, deducido de su ausencia en la reauditoría siguiente; no verificado uno a uno |
| código · reauditoría 1 | R-COD-F008, R-COD-F009 | Menor | Menores de código | Resuelto, deducido de su ausencia en la reauditoría siguiente; no verificado uno a uno |
| código · reauditoría 2 | R-COD-N1 | Menor | No se fijaba qué `GHSA` decide en un hallazgo `DESCONOCIDA` | Resuelto en el ciclo 3 (`e77d91b`); pendiente de verificación |
| código · reauditoría 2 | R-COD-O1 | Observación | El docstring del módulo no decía quién gana entre `HIGH` y `CRITICAL` | Resuelto en el ciclo 3; pendiente de verificación |
| código · reauditoría 2 | R-COD-O2 | Observación | El mutante `PREFIJO_GHSA in valor` en lugar de `startswith` es equivalente en la práctica | No bloquea; sin acción |
| código · reauditoría 2 | R-COD-O3 | Observación | El número de escenario en el nombre de las pruebas de robustez era aproximado | Resuelto con el renombrado a `test_ca10_a3_*`; pendiente de verificación |
| código · reauditoría 3 | R-COD-O4 | Observación | Docstrings sin «esc. N» en cuatro pruebas | Resuelto con el renombrado o queda como observación que no bloquea |
| código · reauditoría 3 | R-COD-O5 | Observación | Prueba opcional para la pareja `HIGH`, `CRITICAL` | Resuelto con el renombrado o queda como observación que no bloquea |
| arquitectura · reauditoría 1 | R-ARQ-N1 | Menor | Renombrar las pruebas por escenario | Resuelto en el ciclo 2 (`ad7e261`) y completado en el ciclo 3; pendiente de verificación |
| arquitectura · reauditoría 1 | R-ARQ-N2 | Menor | Las tablas de esta sección | Resuelto en el ciclo 2; pendiente de verificación |
| arquitectura · reauditoría 2 | R-ARQ-N3 | Menor | Un veredicto de reauditoría presentado como definitivo o anticipado | Resuelto en el ciclo 3 con esta reescritura; pendiente de verificación |
| arquitectura · reauditoría 2 | R-ARQ-N4 | Menor | Renombrado de las pruebas de robustez | Lo hace otro agente en el ciclo 3; pendiente de verificación |
| arquitectura · reauditoría 2 | R-ARQ-N5 | Menor | Cambio de `Hallazgo.aviso` sin constar en «Ajustes respecto al design» | Resuelto en el ciclo 3; pendiente de verificación |
| arquitectura · reauditoría 2 | R-ARQ-N6 | Menor | Cifras (`verificar_escenarios`, cuatro Menores, «25 en rojo») e identificadores repetidos | Resuelto en el ciclo 3; pendiente de verificación |
| arquitectura · reauditoría 3 | R-ARQ-F002-r3 | Menor | Identificadores repetidos entre auditores en la sección de revisión | Resuelto con los prefijos de esta sección; pendiente de verificación |
| arquitectura · reauditoría 3 | R-ARQ-F003-r3 | Menor | Constancia de los docstrings de `Hallazgo.aviso` y `_peor` ajustados en el ciclo 3 | Resuelto: ajustados y commiteados, sin cambio de lógica; pendiente de verificación |
| arquitectura · reauditoría 3 | R-ARQ-O-a-r3 | Observación | Faltaba `(asumido)` en la consecuencia de `DESCONOCIDA` y código 2 | Resuelto en el ADR y en «Ajustes respecto al design»; pendiente de verificación |
| docs · reauditoría 1 | R-DOC-F011 | Mayor | La línea de `aviso` del diseño no describía el GHSA que fija la severidad | Persistía tras el ciclo 2; resuelto en el ciclo 3, pendiente de verificación |
| docs · reauditoría 1 | R-DOC-F012 a R-DOC-F016 | Menor | Menores de documentación | Resuelto, deducido de su ausencia en la reauditoría siguiente; no verificado uno a uno |
| docs · reauditoría 2 | R-DOC-F017 | Mayor | «Modelo por paso» omitía que tres pasos subieron de modelo | Resuelto en el ciclo 3; pendiente de verificación |
| docs · reauditoría 2 | R-DOC-F018 | Mayor | Veredictos de reauditoría presentados como definitivos | Resuelto en el ciclo 3; pendiente de verificación |
| docs · reauditoría 2 | R-DOC-F019 | Mayor | Cifras de la suite desactualizadas | Resuelto en el ciclo 3; pendiente de verificación |
| docs · reauditoría 2 | R-DOC-F020 | Menor | El ADR no decía que el filtro consulta hasta el primer `HIGH` o `CRITICAL` | Resuelto en el ciclo 3; pendiente de verificación |
| docs · reauditoría 3 | R-DOC-F021 | Mayor | El corte en el primer `HIGH` o `CRITICAL` cambia el diseño aprobado y no estaba marcado | Resuelto: `(asumido)` en el diseño y pregunta abierta `A-12` en la spec, citada en el ADR; pendiente de verificación |
| docs · reauditoría 3 | R-DOC-F022 | Menor | «La regla 6 de `CLAUDE.md`» citaba una regla que es otra cosa | Resuelto: ahora cita la convención de TDD de «Convenciones de código»; pendiente de verificación |
| docs · reauditoría 3 | R-DOC-F024 | Menor | «Solo cambiaron documentación y nombres de pruebas» no era exacto | Resuelto con el texto del ciclo 3 y el estado de seguridad; pendiente de verificación |
| docs · reauditoría 3 | R-DOC-O-A-r3 | Observación | El docstring del módulo decía «gana el peor» sin acotarlo a los consultados | Resuelto: «gana el peor de los consultados»; pendiente de verificación |

**Nombres de las pruebas del filtro.** Las pruebas de robustez del filtro (errores de lectura o de consulta con código 2, formas inválidas, tope de lectura, codificación y formato) se nombran `test_ca10_a3_*`, y solo las que afirman un escenario de `CA-10` llevan `test_ca10_escNN_*`.

**Decisión para la persona que aprueba.** La forma `test_ca10_*` y `test_tcNN_*` no coincide con `PATRON_FUNDACION` del verificador de escenarios, así que no se cuenta como «test de fundación». `CA-10` no es una HDU y ninguna compuerta exige esa coincidencia.

**Decisión del corrector, a revisar:** `_peor` corta en el primer `HIGH` o `CRITICAL`, como describe el ADR en sus costes aceptados.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/06-stack-tecnologico.md` §13 | La tabla «Decisiones registradas» no lista los ADR 018, 023 ni 024; es anterior a este ticket | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md` y `docs/adr/README.md` | ADR de la política de severidad, con sus opciones descartadas |
| `CLAUDE.md`, `README.md`, `llms.txt` | Recuento de decisiones de 24 a 25 |
| `docs/06-stack-tecnologico.md` | §6.4 con la política y la nota de `.env.example`; §10 con el trabajo `dependencias` |
| `docs/arranque-local.md`, `tools/README.md` | Auditoría de dependencias en local y sección de `severidad_pip_audit.py` |
| `docs/05-tickets-trabajo.md` | Enlace al ADR en la ficha de TKT-009b |
| `sdd/tickets/tkt-009/design.md` | B1 a B7 en `✓ Hecho` |

`python tools/verificar_docs.py` → `✓ Sin problemas.`

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila ejecutable por un agente: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (backend `1138 passed`; 295 pruebas de `tools/` tras los tres ciclos de la revisión)
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en las rutas críticas del filtro y de la comprobación `comprobar_tc14`
- [ ] Todas las auditorías `APROBADO`: **no**. Seguridad quedó en `APROBADO` en su reauditoría del ciclo 1. Código, arquitectura y documentación quedaron en `REQUIERE CAMBIOS` en la reauditoría del ciclo 3 (código y arquitectura con Menores; documentación con un Mayor, la marca `(asumido)` y la pregunta abierta sobre el corte). Los textos literales que pidieron se aplicaron después, con la suite y `verificar_docs.py` en verde, **sin una reauditoría formal**, porque los tres ciclos de corrección ya estaban agotados
- [x] Sin hallazgo crítico pendiente. El Mayor documental de la reauditoría 3 se corrigió con su texto literal, pero queda como decisión de la persona que aprueba (`A-12`)
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `lint-imports` en `15 kept, 0 broken`; `ruff` y `mypy --strict` limpios sobre los archivos nuevos de `tools/`; el backend corrió `ruff`, `mypy`, `lint-imports` y `verificar_float` en verde
- [x] Rama correcta y sin secretos en el diff

## Veredicto de la revisión (2026-10-29)

**`REQUIERE DECISIÓN`.** El trabajo está completo: los criterios `[M]` están cumplidos con evidencia, la suite pasa y no hay hallazgos críticos. No se emite `LISTO PARA PR` por dos motivos que no le corresponden a un agente:

1. **Decisión de diseño `A-12`.** El filtro corta en el primer `GHSA` `HIGH` o `CRITICAL` de un hallazgo. El código de salida es siempre el correcto; solo cambia la etiqueta (`ALTA` en lugar de `CRÍTICA`). Lo introdujo el corrector para conciliar dos pruebas y cambia el diseño aprobado, así que debe confirmarlo quien aprueba. Lo mismo vale para la extensión de `A-3` a `DESCONOCIDA` y a los fallos de red.
2. **Excepción de cierre.** Tres auditores terminaron en `REQUIERE CAMBIOS` con los ciclos agotados y sus textos literales se aplicaron sin una reauditoría. Es la misma excepción que se aceptó en TKT-009a y TKT-009c, y la persona dueña debe aceptarla.

**Tareas de la persona dueña, fuera del código:** borrar la rama remota `ensayo/tkt-009b-secreto` (commit `0c3a99e`, sin token) y confirmar que el token del segundo intento de B5 está revocado. Antes del PR, empujar los commits locales de la rama del ticket y rebasarla sobre `Produccion` cuando 009a y 009c se fusionen.
