# Impl · TKT-062a · Etiqueta de origen obligatoria

> [← index](_index.md) | [← design común](../tkt-062/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

TKT-062a deja exigida, para cada pull request, una etiqueta de origen: exactamente una de `human`, `human+copilot`, `agent` o `agent+human-review`. El script `tools/etiqueta_origen.py` evalúa las etiquetas del evento y falla cerrado ante una entrada inválida. El flujo `.github/workflows/etiqueta-origen.yml` lo ejecuta en el trabajo «Etiqueta de origen», que es ya una comprobación requerida de la protección de `Produccion`. Dependabot declara `labels: ["agent"]` en sus cuatro entradas.

Las pruebas de `tools/tests` extienden a todo flujo las reglas comunes de TKT-009 (corredor, tiempo, `if:`, interpolación en `run:` y tuberías), con la excepción nombrada de la guarda de la revisión, que nace aquí como constante y se ejerce solo con mutantes sintéticos porque `revision-ia.yml` pertenece a TKT-062b. La documentación recoge el significado de la etiqueta (el origen del código, que no cambia al aprobar) y la regla de que todo cambio a `Produccion` entra por un pull request.

La persona dueña aplicó los ajustes del repositorio (fila A5) y se ensayó la compuerta con un PR de ensayo (fila A6, rondas R0a y R1), cerrado sin fusionar.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-29 | El ejemplo del mensaje de dos etiquetas en `design.md` pasa de `(agent, human)` a `(human, agent)` | El diseño decía a la vez «en el orden de la tupla» y mostraba un ejemplo en otro orden. La tupla manda: `human` va antes que `agent`. El desarrollador de la fila A2 devolvió el test en lugar de forzar el código, y el tester corrigió la constante |
| 2026-10-29 | TC62-38 no exige la regla «todo cambio a `Produccion` entra por un PR» en `CLAUDE.md` | El tester la había exigido por su cuenta. El diseño pide en `CLAUDE.md` solo las cuatro etiquetas y la comprobación; la regla vive en convenciones §6 y §11. Se retiró del test para no ampliar el archivo de reglas del proyecto |
| 2026-10-29 | TC62-07 exige además que exista `etiqueta-origen.yml` | Sin esa precondición el caso nacía en verde, porque `ci.yml` ya no declaraba `types:`. El diseño dice que nace en rojo |
| 2026-10-29 | El párrafo «Cambios a `Produccion`» queda al final de convenciones §6 y no junto a «Revisión de al menos un humano» | Desviación menor de colocación, sin efecto en las pruebas. Observación F004 de la auditoría |
| 2026-10-29 | El comentario de fusión con bypass y `CLAUDE.md` nombran «diez comprobaciones» | El diseño fija diez: los nueve trabajos de `ci.yml` más «Etiqueta de origen» |
| 2026-10-30 | `design.md` corrige una tabla (`\|` dentro de un `jq`) y un término (`cimenta-revision-pr` en código) | El trabajo «Documentación» del PR de ensayo falló en `markdownlint` (MD056) y en Vale |
| 2026-10-30 | Excepción de alcance: `sdd/tickets/tkt-009d/delta.md` pone `tablaroka` en código en dos líneas | Vale lo marcaba y bloquearía el trabajo «Documentación» de cualquier PR. El archivo entró a `Produccion` con el commit de cierre de TKT-009d, sin CI. Autorizado por la persona responsable el 2026-10-30 |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.github/workflows/etiqueta-origen.yml` | nuevo | entrega continua |
| `.github/dependabot.yml` | modificado | entrega continua |
| `tools/etiqueta_origen.py` | nuevo | herramientas |
| `tools/tests/test_etiqueta_origen.py` | nuevo | pruebas |
| `tools/tests/test_definicion_etiqueta.py` | nuevo | pruebas |
| `tools/tests/test_definicion_ci.py` | modificado | pruebas |
| `tools/tests/test_definicion_dependabot.py` | modificado | pruebas |
| `docs/05-tickets-trabajo.md` | modificado | documentación |
| `docs/06-stack-tecnologico.md` | modificado | documentación |
| `docs/convenciones.md` | modificado | documentación |
| `CLAUDE.md` | modificado | documentación |
| `tools/README.md` | modificado | documentación |
| `sdd/plantillas/delta.md` | modificado | documentación |
| `.claude/skills/sdd-completar/SKILL.md` | modificado | documentación |
| `.claude/agents/git-entrega.md` | modificado | documentación |
| `sdd/00-propuesta-toolkit.md` | modificado | documentación |
| `sdd/tickets/tkt-062/` (`_index.md`, `spec.md`, `design.md`) | nuevo | documentación |
| `sdd/tickets/tkt-062a/` y `sdd/tickets/tkt-062b/` | nuevo | documentación |
| `sdd/tickets/tkt-009d/delta.md` | modificado | documentación (excepción de alcance) |

No se tocó nada de `backend/`, `frontend/` ni `docs/api/openapi.yaml`.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC62-01 | `test_tkt062_ca06_esc01_exactamente_una_etiqueta_pasa` | feliz | `CA-6` | FALLA | PASA |
| TC62-02 | `test_tkt062_ca06_esc02_sin_etiqueta_falla_y_nombra_las_cuatro` | **rechazo** | `CA-6` | FALLA | PASA |
| TC62-03 | `test_tkt062_ca06_esc03_dos_etiquetas_fallan_y_lo_dicen` | **rechazo** | `CA-6` | FALLA | PASA |
| TC62-04 | `test_tkt062_ca06_esc02_entrada_ausente_o_invalida_falla_cerrado` | **rechazo** | `CA-6` | FALLA | PASA |
| TC62-05 | `test_tkt062_ca06_esc02_variantes_de_la_etiqueta_no_cuentan` | **rechazo** | `CA-6` | FALLA | PASA |
| TC62-06 | `test_tkt062_ca06_esc04_el_flujo_de_etiqueta_se_relanza_al_etiquetar` | feliz | `CA-6` | FALLA | PASA |
| TC62-07 | `test_tkt062_ca06_esc04_etiquetar_no_relanza_ci` | **rechazo** | `CA-6` | FALLA | PASA |
| TC62-08 | `test_tkt062_ca06_esc05_dependabot_etiqueta_agent_en_sus_cuatro_entradas` | feliz | `CA-6` | FALLA | PASA |
| TC62-09 | `test_tkt062_car2_esc01_reglas_comunes_en_todo_flujo` | **rechazo** | `CA-R2` | PASA (rojo por mutantes) | PASA |
| TC62-R1 | `test_tkt062_car1_esc01_tc13_y_las_reglas_siguen_en_verde_con_el_flujo_de_etiqueta_presente` | regresión | `CA-R1` | FALLA | PASA |
| TC62-R4 | `test_tkt062_car4_esc01_tc15_sigue_en_verde_sobre_el_dependabot_real` | regresión | `CA-R4` | PASA | PASA |
| TC62-38 | `test_tkt062_ca12_esc01_la_documentacion_de_062a_describe_la_etiqueta` | feliz | `CA-12` | FALLA (8 archivos) | PASA |

TC62-09 y TC62-R4 nacen en verde sobre el repositorio real, como dice el diseño: el repositorio ya cumplía las reglas, y su rojo lo dan los mutantes sintéticos. Hay además los casos adicionales que el tester añadió: tres etiquetas, una variante junto a una válida, y las clases de mutantes de TC62-06, TC62-08, TC62-09 y de la regresión de TC-15.

### Ciclo TDD por fila

#### Fila A0 · Partición registrada en `docs/05` (`haiku`, sin ciclo de pruebas)

Fila documental sin test propio. `docs/05-tickets-trabajo.md` recibe la subsección «Partición en dos tickets hermanos» y la corrección de la frase del criterio sobre aprobar. Verificación: `python tools/verificar_docs.py` en verde y diff de la línea corregida limitado a la frase (50 inserciones, 1 eliminación).

#### Fila A2 · `tools/etiqueta_origen.py`

**Rojo** — 7 tests, 13 fallos, todos por la ausencia del módulo:

```text
Traceback (most recent call last):
  File "...\tools\tests\test_etiqueta_origen.py", line 65, in etiqueta
    return importlib.import_module("etiqueta_origen")
ModuleNotFoundError: No module named 'etiqueta_origen'
AssertionError: falta tools/etiqueta_origen.py: el módulo bajo prueba todavía no existe
Ran 7 tests in 0.133s
FAILED (failures=13)
```

**Verde** — primera pasada, 6 de 7. El séptimo falló por la contradicción del diseño descrita en «Ajustes». Tras corregir la constante del test:

```text
Ran 7 tests in 0.001s
OK
```

Códigos de salida del script: `["agent"]` da 0, `[]` da 1 y sin variable da 2.

**Refactor:** sin refactor; el módulo ya era mínimo.

**Tests devueltos al tester:** `MENSAJE_DOS_ETIQUETAS` esperaba `(agent, human)`. Se corrigió a `(human, agent)`.

**Mutación:** el orden de las etiquetas halladas, cambiado a alfabético y a orden de llegada, hace caer `esc03_dos_etiquetas_fallan_y_lo_dicen` y `esc03_tres_etiquetas_dan_el_numero_y_el_orden_de_la_tupla`. El archivo se restauró idéntico.

#### Fila A3 · Flujo `etiqueta-origen.yml` y reglas comunes sobre todo flujo

**Rojo** — 166 tests ejecutados, 3 fallos por la ausencia del flujo y ningún test previo roto:

```text
AssertionError: No existe .github/workflows/etiqueta-origen.yml: el flujo de la etiqueta de origen de TKT-062a todavía no está definido
Ran 166 tests in 13.016s
FAILED (failures=3)
```

Había 136 tests antes de la fila y quedaron 30 nuevos (17 en `test_definicion_etiqueta.py` y 13 en `test_definicion_ci.py`).

**Verde:**

```text
Ran 173 tests in 12.933s
OK
```

`uvx zizmor@1.31.1 --offline .github/workflows` termina sin hallazgos: «No findings to report. Good job! (2 suppressed)».

**Refactor:** sin refactor; el flujo ya era mínimo.

**Mutación:** comparar la guarda con `_expresion_de_if` en vez de `_normalizada` hace caer 4 subtests; que la regla 7 juzgue el `if:` de `revision`, 5; no comparar la guarda, 10.

#### Fila A4 · `labels:` en Dependabot

**Rojo** — un único fallo, el de TC62-08 sobre el archivo real; 34 tests en el archivo frente a 24 antes:

```text
AssertionError: Lists differ: ["uv /backend: labels debe ser ['agent'] y es None",
 "npm /frontend: labels debe ser ['agent'] y es None",
 "npm /.github/mermaid: labels debe ser ['agent'] y es None",
 "github-actions /: labels debe ser ['agent'] y es None"] != []
Ran 34 tests in 0.015s
FAILED (failures=1)
```

**Verde:**

```text
python -m unittest tools.tests.test_definicion_dependabot -v   Ran 34 tests in 0.015s   OK
python -m unittest discover -s tools/tests                      Ran 388 tests in 14.671s  OK
```

**Mutación:** cambiar `if etiquetas != ETIQUETAS_ESPERADAS:` por `if not etiquetas:` hace caer 9 casos (`dependencies`, `agent` con otra, orden inverso, `Agent`, `AGENT`, repetida, con espacio y `agents`). El archivo se restauró.

#### Fila A7 · Documentación de la etiqueta

**Rojo** — TC62-38 con 8 subtests en rojo, uno por archivo, todos por frases ausentes. `CLAUDE.md` falló solo por las cuatro etiquetas y por `etiqueta-origen.yml` después de retirar la exigencia sobrante. `verificar_docs.py` seguía en verde.

**Verde:**

```text
test_tkt062_ca12_esc01_la_documentacion_de_062a_describe_la_etiqueta ... ok
python -m unittest discover -s tools/tests   Ran 389 tests in 15.027s   OK
python tools/verificar_docs.py               ✓ Sin problemas.
```

**Tests devueltos al tester:** se retiró de TC62-38 la regla de PR en `CLAUDE.md`, por el motivo explicado en «Ajustes».

### Evidencia de ejecución al cerrar (fila A8)

Docker no interviene: este ticket no tiene pruebas de integración ni toca `backend/`.

```text
python -m unittest discover -s tools/tests
Ran 389 tests in 21.308s
OK

python tools/verificar_docs.py
Documentos analizados: 170 · enlaces relativos 1415 · anclas internas 640
✓ Sin problemas.

uvx zizmor@1.31.1 --offline .github/workflows
No findings to report. Good job! (2 suppressed)

uvx --from vale==3.25.1.0 vale --output=line docs sdd README.md CLAUDE.md tools/README.md
(sin texto, salida 0)

npx --yes markdownlint-cli2@0.24.0 "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md
Summary: 0 issues in 0 files
```

**Recuento frente a la línea base.** Con un `worktree` de `origin/Produccion` (2e192df) se ejecutaron 341 pruebas, con 3 fallos solo de entorno: `uv` intentaba compilar `pyyaml` en un directorio sin entorno de backend. En el repositorio real esos mismos tests pasan. Ahora hay 389: **48 pruebas nuevas**. Las líneas añadidas con `skip`, `skipTest`, `expectedFailure`, `xfail` o `.only` en `tools/tests` son cero.

**Las dos supresiones de `zizmor`.** Son avisos `concurrency-limits` de la persona *pedantic*, uno en `ci.yml` y otro en `etiqueta-origen.yml`. El pipeline usa la persona por omisión, que no los muestra, y `concurrency` es un *Won't* de TKT-062.

**Mutación sobre el flujo real.** Quitar `unlabeled` de `types`, o renombrar el trabajo a `Etiqueta`, hace caer `test_tkt062_ca06_esc04_el_flujo_de_etiqueta_se_relanza_al_etiquetar`. El archivo se restauró con el mismo SHA256 y la suite volvió a 389 en verde. Las dos mutaciones las atrapa el mismo test del archivo real; los mutantes sintéticos de TC62-06 cubren cada variante sobre la función comprobadora.

### Evidencia de la fila A5 (ajustes del repositorio, aplicados por la persona dueña)

**Paso 1 · etiquetas.** `gh label list --repo FranciscoRodSilva/IA4Devs-Proyecto-Final --json name --jq '.[].name'` muestra, junto a las predeterminadas y las de Dependabot, `human`, `human+copilot`, `agent` y `agent+human-review` (2026-10-29).

**Paso 2 · protección de `Produccion`.** Verificación (2026-10-29):

```text
{
  "admins": false,
  "aprobaciones": 1,
  "checks": [
    "Backend · formato, lint, tipos, float y pruebas",
    "Fronteras entre módulos",
    "Prueba de contrato de la API · reservado para TKT-061",
    "Frontend · lint, tipos, pruebas y tipos generados",
    "Humo · recorrido de Playwright con base migrada",
    "Herramientas · pruebas de tools/",
    "Seguridad de los workflows · zizmor",
    "Documentación · verificador propio, markdownlint, Vale, lychee y mermaid-cli",
    "Dependencias · auditoría de vulnerabilidades",
    "Etiqueta de origen"
  ]
}
```

Diez contextos, ninguno de «Revisión IA», `aprobaciones: 1` y `admins: false`. La respuesta completa también muestra `allow_force_pushes` y `allow_deletions` en `false`.

**Paso 3 · colaboradores con escritura.** `gh api "repos/$REPO/collaborators"` devuelve un único colaborador: `FranciscoRodSilva`, permisos `admin`.

### Evidencia de la fila A6 (ensayo de 062a)

PR de ensayo A′ = [#20](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/20), de `ensayo/tkt-062a` hacia `tkt-062a-etiqueta-origen`, con el único commit `cb3fe6d` (`ensayo-062a.txt`).

| Ronda | Qué se hizo | Resultado | Ejecución |
|---|---|---|---|
| R0a | Se abrió sin etiquetas | «Etiqueta de origen» en rojo con «El PR no tiene etiqueta de origen. Añade exactamente una de: human, human+copilot, agent, agent+human-review.» | `actions/runs/40986747759` |
| R1 | Se añadieron `agent` y `human` | Rojo con «El PR tiene 2 etiquetas de origen (human, agent); debe haber exactamente una de: human, human+copilot, agent, agent+human-review.» | `actions/runs/41069519364` y `41069520015` |
| R1 | Se quitó `human` | Verde | `actions/runs/41069651691` |
| R1 | Ejecuciones de `ci.yml` en la rama de ensayo | 1 ejecución en total, la misma antes y después de etiquetar: etiquetar no relanza el pipeline | `gh run list --workflow ci.yml` |
| Cierre | `gh pr close 20 --delete-branch` | `CLOSED`, `mergedAt: null`; la rama ya no existe en el remoto | — |

En R1, las dos ejecuciones de la etiqueta provocadas por añadir `agent` y `human` se lanzaron a la vez y las dos vieron ambas etiquetas. Es la carrera conocida que el diseño acepta mientras `concurrency` sea un *Won't*.

El trabajo «Documentación» del PR de ensayo falló por tres hallazgos de `markdownlint` y Vale, corregidos en este ticket (véase «Ajustes»). De los demás trabajos de `ci.yml`, los ocho restantes terminaron en verde (backend, fronteras, contrato, frontend, humo, herramientas, zizmor y dependencias), como confirma la ejecución `actions/runs/40986747758`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | `haiku` | `haiku` | — |
| A0 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| A2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A2 · verde | `ingeniero-devsecops` | `sonnet` | `sonnet` | — |
| A2 · corrección del test | `tester-backend` | `sonnet` | `sonnet` | Constante errónea en el test, no en el código |
| A3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A3 · verde | `ingeniero-devsecops` | `sonnet` | `sonnet` | — |
| A4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A4 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | Tarea mecánica, §14.2 |
| A7 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| A7 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | Tarea mecánica, §14.2 |
| Commit y push | `git-entrega` | `haiku` | `haiku` | — |
| A6 · rama de ensayo | `git-entrega` | `haiku` | `haiku` | — |
| A8 | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Corrección de F001 a F003 | `corrector-revision` | `haiku` | `haiku` | Hallazgos Menores |
| Reauditoría | `auditor-arquitectura` | `sonnet` | `sonnet` | — |

Ninguna fila subió ni bajó de modelo, y ninguna tocó `opus`. Todas las filas de `ingeniero-devsecops` que tocan contenido de un flujo usaron `sonnet`.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-6` esc. 1 a 4 | `[M]` | Cumplido | TC62-01 a TC62-07; rondas R0a y R1 |
| `CA-6` esc. 5 (Dependabot) | `[M]` | Cumplido en el archivo; **pendiente en vivo** | TC62-08. GitHub lee `dependabot.yml` solo de la rama por omisión, así que el PR de Dependabot etiquetado solo se observa tras fusionar |
| `CA-9` en lo suyo | `[M]` | Cumplido | Evidencia de A5 con fecha |
| `CA-12` en lo suyo | `[M]` | Cumplido | TC62-38 |
| `CA-R1`, `CA-R2` | `[M]` | Cumplido | TC62-R1, TC62-09 |
| `CA-R4` | `[M]` | **Parcial** | TC62-R4 en verde; los nueve trabajos de `ci.yml` en verde se verifican en el PR real del ticket |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` en la reauditoría final, tras dos veces `REQUIERE CAMBIOS` | 4 Menores, todos resueltos (F008 nació de la corrección de F003), y observaciones sin bloqueo | 3 de 3 |
| `auditor-sql` | No aplica | No hay esquema ni consulta | — |
| `auditor-codigo` | Pendiente de `/sdd-revisar` | — | — |
| `auditor-seguridad` | Pendiente de `/sdd-revisar` | — | — |
| `auditor-docs` | Pendiente de `/sdd-revisar` | — | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | `auditor-arquitectura` | Menor | `sdd/tickets/tkt-062/_index.md` | D-2 decía que el bypass se registra en el `delta.md`, y daba la partición por pendiente | Resuelto |
| F002 | `auditor-arquitectura` | Menor | `sdd-completar/SKILL.md`, `convenciones.md`, `delta.md` | El comentario de fusión listaba contenidos distintos | Resuelto |
| F003 | `auditor-arquitectura` | Menor | `docs/05-tickets-trabajo.md`, `CLAUDE.md` | «No se puede fusionar» sin el matiz de la administradora con `enforce_admins: false` | Resuelto |
| F008 | `auditor-arquitectura` | Menor | `CLAUDE.md:89`, `docs/05-tickets-trabajo.md:419` y `:424` | La corrección de F003 introdujo una excepción imposible: la administradora «salvo… solo con las diez comprobaciones en verde», cuando «Etiqueta de origen» es una de las diez. La omisión con `--admin` cubre solo la aprobación humana | Resuelto |
| F004 | `auditor-arquitectura` | Observación | `docs/convenciones.md` §6 | El párrafo «Cambios a `Produccion`» quedó al final de la sección | Aceptado, véase «Ajustes» |
| F005 | `auditor-arquitectura` | Observación | `tools/tests/` | Unas 1,540 líneas de pruebas frente a las 320 estimadas | Aceptado, véase abajo |
| F006 | `auditor-arquitectura` | Observación | `tkt-009d/delta.md` | Un cambio de otro ticket en el diff | Se commitea aparte |
| F007 | `auditor-arquitectura` | Observación | `etiqueta-origen.yml` | El flujo apareció modificado un instante | Causa: la mutación del tester corría en paralelo con la auditoría. El árbol volvió limpio |

**Desviación de tamaño (F005).** El diseño estimó unas 490 líneas para esta parte, con 320 de pruebas. El diff trae unas 1,540 líneas de pruebas: `test_definicion_etiqueta.py` 688, `test_etiqueta_origen.py` 177, `test_definicion_ci.py` +422 y `test_definicion_dependabot.py` +253. Es cobertura de mutantes de las compuertas, no alcance añadido, pero el criterio «cabe en una sesión» de la spec ya no se cumple por tamaño. Conviene ajustar la estimación de las pruebas de fundación en la siguiente partición.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `.github/workflows/etiqueta-origen.yml` | El checkout es el del PR: un PR puede alterar `etiqueta_origen.py` para pasar. Aceptado en el diseño; la mitigación estructural es `CODEOWNERS` | Baja, ticket futuro ya sugerido |
| `.github/workflows/etiqueta-origen.yml` | Sin `concurrency`, dos ejecuciones sobre el mismo SHA pueden terminar en desorden | Baja, ticket futuro ya sugerido |
| `sdd/tickets/tkt-009d/delta.md` | Los commits de cierre de ticket empujados directo a `Produccion` se saltaron la CI y dejaron un fallo de Vale. Desde la protección de la rama, el cierre viaja dentro del PR | Resuelto por la regla «todo entra por PR» |
| Repositorio | GitHub avisa de 2 vulnerabilidades de severidad baja en la rama por defecto | Baja, revisar en Dependabot |
| `docs/05-tickets-trabajo.md` | La frase «no se puede fusionar, tampoco si lo fusiona la administradora» suena a bloqueo técnico, y con `enforce_admins: false` es una convención del proyecto, como dicen convenciones §6 y el diseño. Observación O2 de la reauditoría final | Baja, afinar la redacción en una limpieza posterior |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/05-tickets-trabajo.md` | Subsección «Partición en dos tickets hermanos» y el criterio sobre aprobar |
| `docs/convenciones.md` | §6 y §11: el origen del código, la comprobación requerida, «todo entra por PR» y la fusión con omisión |
| `CLAUDE.md` | Solo el párrafo de la etiqueta de origen |
| `docs/06-stack-tecnologico.md` | §10: `etiqueta-origen.yml` y `enlaces.yml` como flujos aparte |
| `tools/README.md` | `etiqueta_origen.py`, sus pruebas y las reglas comunes sobre todo flujo |
| `sdd/plantillas/delta.md`, `sdd-completar/SKILL.md`, `git-entrega.md`, `00-propuesta-toolkit.md` | Las cuatro etiquetas y el bloque «Fusión con omisión» |

`python tools/verificar_docs.py` → `✓ Sin problemas.` (170 documentos).

## Verificación final

- [x] Todos los criterios `[M]` de esta parte cumplidos con evidencia, salvo `CA-6` esc. 5 en vivo y la segunda mitad de `CA-R4`, que dependen del PR real y de la fusión
- [x] Ciclo TDD completo en cada fila con código: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en las compuertas críticas
- [ ] Todas las auditorías `APROBADO` (arquitectura `APROBADO`; las demás, en `/sdd-revisar`)
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy` y `lint-imports` no aplican: no hay código de `backend/` en el diff
- [x] Rama correcta y sin secretos en el diff
