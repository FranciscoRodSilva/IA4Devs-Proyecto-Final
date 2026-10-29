# Impl · TKT-009b · Cadena de suministro

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

Las filas B1 a B4 y B7 de la parte b del [diseño común](../tkt-009/design.md#parte-b--cadena-de-suministro). `pip-audit` entra en el grupo `dev`. El filtro `tools/severidad_pip_audit.py` toma la severidad del aviso de GitHub en OSV y falla ante `HIGH`, `CRITICAL` o severidad desconocida. El trabajo `dependencias` de `ci.yml` encadena `uv export`, `pip-audit`, el filtro y `npm audit --audit-level=high`. Dependabot cubre `uv`, `npm` y `github-actions` cada semana. El ADR de severidad, la política de `docs/06` §6.4 y la guía de auditoría local cierran la documentación.

**La fila B5 la ejecutó la persona dueña el 2026-10-29** (ver «Fila B5» abajo). **Queda pendiente la fila B6**, el ensayo en el pipeline, que exige una rama de ensayo y un PR en borrador que abre la persona usuaria a mano. La guía [ajustes-repositorio.md](ajustes-repositorio.md) deja redactados los comandos y las rondas. Por eso los escenarios `CA-10` esc. 2 y 3 en el pipeline no tienen todavía evidencia, y este ticket **no puede pasar a `LISTO PARA PR`** hasta que la tengan.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-28 | `Hallazgo` lleva un sexto campo, `alias`, con `compare=False` | Imprimir «(CVE-…, PYSEC-…)» sin romper la igualdad de cinco argumentos que fijan las pruebas |
| 2026-10-28 | Una severidad de OSV desconocida o ausente es `DESCONOCIDA` y falla | Extiende el fallo cerrado de `A-3` a valores no reconocidos |
| 2026-10-28 | `consultar_osv` codifica el identificador con `quote(..., safe="")` | Un identificador con caracteres especiales no altera la URL |
| 2026-10-28 | `comprobar_regla_comun_7` admite el `\|\| true` de `uv run pip-audit` en el trabajo `dependencias` | El diseño pide ese `\|\| true` y a la vez prohíbe todo el resto; la excepción está acotada y tiene sus pruebas |
| 2026-10-28 | Las pruebas de Dependabot viven en `tools/tests/test_definicion_dependabot.py` | `test_definicion_ci.py` ya pasa de 3,100 líneas |
| 2026-10-28 | El trabajo `dependencias` no ejecuta `npm ci` | `npm audit` lee `package-lock.json`; se comprobó que sale igual sin `node_modules` |
| 2026-10-28 | Fecha del ADR: 20261029 | La mayor entre hoy y la del ADR más reciente |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | modificado | herramientas (18 paquetes nuevos en el lock) |
| `tools/severidad_pip_audit.py` | nuevo | herramientas |
| `tools/tests/test_severidad_pip_audit.py` | nuevo | pruebas |
| `tools/tests/test_definicion_ci.py` | modificado | pruebas |
| `tools/tests/test_definicion_dependabot.py` | nuevo | pruebas |
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
| TC-16, TC-17 | Manuales | **rechazo** | `CA-11` esc. 2, `CA-R3` esc. 2 | Empuje con un token revocado: aceptado, sin alerta | PASAN con un token activo sin permisos: `GH013` (B5) |
| TC-11a, TC-11b | Ensayo en el pipeline | **rechazo** | `CA-10` esc. 2 y 3 | — | **Pendientes (B6)** |

**Los casos de TC-18 sobre el repositorio real nacen en verde, y se investigó.** El invariante ya se cumple: `.github/` solo tiene `workflows/ci.yml`, sin exclusiones ni `secrets.`. Para que no sean vacuos, el lector exige que `ci.yml` exista y sus mutantes sintéticos (`paths-ignore` con `.env.example`, un `secret_scanning.yml`, `secrets.X`) sí los ponen en rojo.

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

**Empuje de ensayo, intento 1 (token revocado antes de pegarlo): sin bloqueo y sin alerta.** El empuje de `ensayo/tkt-009b-secreto` fue aceptado, y `GET .../secret-scanning/alerts` devolvió una lista vacía tanto justo después como unos minutos más tarde. No se conoce el prefijo del token usado, así que la causa no está establecida: puede que la protección ignore un token ya revocado, o que lo pegado no tuviera forma de token de GitHub. **Consecuencia para la guía:** pedir "revocado antes" no sirve como ensayo.

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

Se pidió y se aprobó el cambio de orden: el token se creó activo y sin permisos, y se revoca justo después del empuje. Como el empuje se rechazó, el secreto no llegó a quedar en GitHub en el intento 2. En el intento 1 sí llegó la rama `ensayo/tkt-009b-secreto` con un token revocado; se borra al terminar el ensayo.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| B1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| B2 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B2 · mutación y B3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| B3 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| B4 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| B7 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Auditoría de arquitectura y corrección | `auditor-arquitectura`, `corrector-revision` | `sonnet`, `haiku` | `sonnet`, `haiku` | — |

Ningún paso subió de modelo. B5 la ejecuta la persona dueña y B6 queda para `git-entrega`.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-10` esc. 1 | `[M]` | Cumplido | TC-35 y TC-14; la cadena real da código 0 |
| `CA-10` esc. 2 y 3 | `[M]` | **Parcial** | TC-30 a TC-34 en verde; falta el ensayo en el pipeline (B6, TC-11a y TC-11b) |
| `CA-11` esc. 1 y 3 | `[M]` | Cumplido | TC-15 y TC-18 |
| `CA-11` esc. 2 | `[M]` | Cumplido | Consulta de `gh api` con los dos ajustes en `enabled`; empuje de ensayo rechazado con `GH013` (B5, TC-16 y TC-17) |
| `CA-R2` | `[M]` | Cumplido | El diff de `pyproject.toml` es una línea del grupo `dev`; `15 kept, 0 broken` |
| `CA-R3` | `[M]` | Cumplido | Esc. 1 por TC-18 y TC-22; esc. 2 por el empuje rechazado de B5 |
| `CA-R4` | `[M]` | Cumplido | La suite de `tools/` pasa de 178 a 247 pruebas sin quitar ninguna ni añadir `skip` |
| `CA-15` su parte | `[M]` | Cumplido | `docs/06` §6.4 y los textos de la auditoría; TC-70b sin marcas que retirar |

Un Must incumplido **no se aprueba**: `CA-10` esc. 2 y 3 sigue parcial hasta el ensayo de B6, y bloquea el paso a `LISTO PARA PR`.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `REQUIERE CAMBIOS` en ambas pasadas; sus dos Menores (documentales) están corregidos y verificados con `verificar_docs.py`, sin una tercera reauditoría | 2 Menores (F001, F002) | 2 |
| `auditor-sql` | No aplica | No hay esquema ni migración | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `sdd/tickets/tkt-009b/ajustes-repositorio.md:134` | Atribuía al paso de `pip-audit` la lista de vulnerabilidades, que sale en el paso del filtro | Resuelto (confirmado por la reauditoría) |
| F002 | arquitectura | Menor | `sdd/tickets/tkt-009b/impl.md:3` | El enlace a `delta.md`, que aún no existe, rompía `verificar_docs.py`, y la cifra de archivos estaba desactualizada | Resuelto: el enlace pasa a «delta (pendiente)» y la cifra es 159; `verificar_docs.py` da `✓ Sin problemas.` |

Observaciones del auditor que no bloquean: `_aviso_ghsa` solo consulta el primer `GHSA` de un hallazgo; `zizmor` no estaba instalado en su entorno (la salida en 0 la confirmó la ejecución con `uvx` de esta sesión); `nanoid@3.1.30` resultó no servir para la ronda 2 (tres avisos altos); el candidato pasa a ser `stream-json@3.6.0`, con un único aviso medio confirmado el 2026-10-29.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/06-stack-tecnologico.md` §13 | La tabla «Decisiones registradas» no lista los ADR 018, 023 ni 024; es anterior a este ticket | Baja |
| `tools/severidad_pip_audit.py` | Un aviso con varios `GHSA` de severidades distintas solo evalúa el primero | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261029-severidad-en-la-auditoria-de-dependencias.md` y `docs/adr/README.md` | ADR de la política de severidad, con sus opciones descartadas |
| `CLAUDE.md`, `README.md`, `llms.txt` | Recuento de decisiones de 24 a 25 |
| `docs/06-stack-tecnologico.md` | §6.4 con la política y la nota de `.env.example`; §10 con el trabajo `dependencias` |
| `docs/arranque-local.md`, `tools/README.md` | Auditoría de dependencias en local y sección de `severidad_pip_audit.py` |
| `docs/05-tickets-trabajo.md` | Enlace al ADR en la ficha de TKT-009b |
| `sdd/tickets/tkt-009/design.md` | B1 a B4 y B7 en `✓ Hecho`; B5 y B6 en `Pendiente` |

`python tools/verificar_docs.py` → `✓ Sin problemas.`

## Verificación final

- [ ] Todos los criterios `[M]` cumplidos con evidencia: **faltan `CA-10` esc. 2 y 3 en el pipeline (B6)**
- [x] Ciclo TDD completo en cada fila ejecutable por un agente: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (247 pruebas de `tools/`)
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en las rutas críticas del filtro y de la comprobación `comprobar_tc14`
- [ ] Todas las auditorías `APROBADO`: la de arquitectura quedó en `REQUIERE CAMBIOS` en su último veredicto formal, con los dos Menores ya corregidos; falta además `/sdd-revisar`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `lint-imports` en `15 kept, 0 broken`; `ruff` limpio sobre los archivos nuevos de `tools/`. `mypy` no aplica: no se tocó `backend/`
- [x] Rama correcta y sin secretos en el diff
