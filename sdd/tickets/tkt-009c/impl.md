# Impl · TKT-009c · Verificador de escenarios sin test

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

`tools/verificar_escenarios.py` convierte en compuerta la regla de aceptación de [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md): un escenario que cuenta y no tiene un test que lo nombre falla el pipeline. Un escenario cuenta desde que su historia está en `tools/historias_activas.txt`; los de fase 2 cuentan cuando ese archivo contiene la línea `fase 2`; y uno retirado con el segmento `· retirado por TKT-0NN` en su título deja de contar. El verificador admite los nombres de fundación sin contarlos como huérfanos, informa de lo pendiente por historia y falla si una historia, o la línea `fase 2`, salen del archivo respecto a la base del PR.

Está hecho solo con la biblioteca estándar y se ejecuta en el trabajo `herramientas` de `ci.yml`, con la base del PR por `env`. Sus pruebas usan documentos de ejemplo y el árbol real. Se escribió el ADR de la política, se retiraron las marcas «desde TKT-009» del verificador y se actualizaron las prosas de retiro de la documentación.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-29 | La compuerta de C1 es `-k leer_` en lugar de «esos casos en verde» | El diseño asignaba TC-44 a TC-49 y TC-55 a C1, pero su resultado observable (código de salida y etiquetas) lo produce `main`, que es de C3. Los casos `test_tcNN_leer_…` cierran en C1 y los `test_tcNN_salida_…` en C3 |
| 2026-10-29 | `leer_historias` lee solo la primera tabla de la sección «El conjunto», la que tiene la columna `Fase` | El documento real trae dentro de esa sección una segunda tabla de complejidad con filas que empiezan por `\| HDU-00X \|`. El diseño no lo contemplaba y sin esto el lector lanzaba `EntradaInvalida` sobre el documento real |
| 2026-10-29 | Una historia duplicada, un `docs/04` inexistente y un `--activas-base` mal formado devuelven `EntradaInvalida` (código 2) | El diseño solo nombraba la lista de activas ausente. Fusionar en silencio un duplicado sería peor, y las tres son la misma clase de entrada mal formada |
| 2026-10-29 | `PASO_ESCENARIOS` del trabajo `herramientas` lleva `if: ${{ !cancelled() }}` | Hallazgo del propio ensayo C5: con `HDU-001` activa, el trabajo caía en «Pruebas de tools/» (TC-56 fija «162 pendientes, 0 exigidos») y el paso del verificador quedaba omitido, de modo que su compuerta no se ejecutaba. Es la razón de la regla común 6 del diseño. Rojo: cae solo TC-57 sobre el `ci.yml` real (1 de 171); verde: 171 de 171 |
| 2026-10-29 | La Definition of Done pide 27 `FALTA` en el pipeline; el plan de pruebas decía 26 (TC-58) | Inconsistencia del diseño, corregida a 27 (HDU-001 tiene 27 escenarios) |
| 2026-10-29 | La rama base de TKT-009c es `tkt-009a-pipeline-pruebas`, no `Produccion` | El PR #2 de TKT-009a todavía no está fusionado. El PR de 009c apunta a esa rama |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `tools/verificar_escenarios.py` | nuevo | herramientas |
| `tools/historias_activas.txt` | nuevo | herramientas |
| `tools/tests/test_verificar_escenarios.py` | nuevo | pruebas |
| `tools/tests/test_definicion_ci.py` | modificado (TC-57 y mutantes) | pruebas |
| `.github/workflows/ci.yml` | modificado (paso nuevo en `herramientas`) | entrega continua |
| `docs/adr/20261029-politica-del-verificador-de-escenarios.md`, `docs/adr/README.md` | nuevo, modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt` | modificado (marca de `CLAUDE.md:78` y recuento de ADR) | documentación |
| `docs/04-historias-usuario.md`, `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `docs/convenciones.md`, `docs/arranque-local.md`, `tools/README.md` | modificado | documentación |
| `sdd/tickets/tkt-009/design.md` | modificado (estados y TC-58) | documentación |

No se tocó `backend/` ni `frontend/`.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-40 a TC-43 | `test_tc40_…` a `test_tc43_…` | feliz y **rechazo** | `CA-6` | FALLA (`NotImplementedError`) | PASA |
| TC-44 a TC-49 | `test_tc44_…` a `test_tc49_…` | feliz y **rechazo** | `CA-7` | FALLA | PASA |
| TC-50 a TC-55 | `test_tc50_…` a `test_tc55_…` | feliz y **rechazo** | `CA-8`, entrada mal formada | FALLA | PASA |
| TC-56 | `PruebasSobreElArbolReal` | regresión | `CA-7` esc. 1 | FALLA (código 2: falta el archivo) | PASA |
| TC-57 | `DefinicionDeCIFilaC4` | estático, con rechazo | `CA-6` esc. 1 | FALLA (2 de 139; luego 1 de 171) | PASA |
| TC-58 | ensayo en el pipeline | **rechazo** | `CA-6` esc. 1 | — | rojo con el paso del verificador fallando |

### Ciclo TDD por fila

#### Fila C1 · lectores

**Rojo.** El tester escribió las 49 pruebas de la parte c y un esqueleto con las firmas del diseño cuyas funciones lanzan `NotImplementedError`, para que el rojo fuera de comportamiento y no de importación. Resultado: `Ran 49 tests … FAILED (errors=53)`, 49 pruebas más 4 subcasos, todos `NotImplementedError`. Con una implementación de referencia desechable, fuera del repositorio, las 49 pasaban y los cuatro mutantes del diseño caían en las pruebas esperadas.

**Verde.** Gate `-k leer_`: `Ran 12 tests … OK`. El resto seguía en rojo (37 errores).

#### Fila C2 · `recolectar_tests` y `clasificar`

**Verde.** `-k recolectar`: `Ran 4 tests … OK`. Ninguna prueba llama a `clasificar` directamente: todas llegan por `main`. El desarrollador la comprobó con un script de sondeo fuera del repositorio. Resto: `FAILED (errors=33)`, todos de `main` (C3).

#### Fila C3 · `main`

**Verde.** `Ran 49 tests … OK`; suite de `tools/` con 126 pruebas en `OK`. Sobre el árbol real, sin la lista de historias, código 2 con «no existe tools/historias_activas.txt».

#### Fila C4 · lista real y paso de CI

**Rojo.** `Ran 139 tests … FAILED (failures=6)`: las cuatro de TC-56, por el código 2 al faltar el archivo, y las dos de TC-57, por «falta `python3 tools/verificar_escenarios.py`».

**Verde.** `Ran 139 tests … OK`, sin `skipped=`. Verificador sobre el árbol real: código 0, `exigidos 0 · pendientes 162 · tests de fundación 180`. `zizmor`: «No findings to report».

#### Fila C5 · ensayo en el pipeline

**Primera ronda.** El PR de ensayo #5 (`HDU-001` activa) puso el trabajo `herramientas` en rojo, pero en el paso «Pruebas de tools/» por TC-56, y el paso del verificador quedó `skipped`. Es el ajuste del 2026-10-29 de la tabla anterior.

**Rojo del ajuste.** `Ran 171 tests … FAILED (failures=1)`: TC-57 sobre el `ci.yml` real, «el paso del verificador de escenarios no declara `if: ${{ !cancelled() }}`».

**Verde del ajuste.** `Ran 171 tests … OK`; `zizmor` sin hallazgos.

**Segunda ronda.** Con el arreglo en la rama de ensayo, el trabajo `herramientas` terminó en rojo con los pasos «Pruebas de tools/» y «Verificar que cada escenario exigido tenga su test» fallados (`actions/runs/40812135088`), y el registro contiene el resumen `Escenarios: 162 · exigidos 27 · cubiertos 0 · faltan 27 · pendientes 135 · retirados 0 · tests HDU 0 · tests de fundación 180`. El PR real de 009c quedó con los ocho trabajos en verde (`actions/runs/40812133855`). El PR de ensayo se cerró sin fusionar y su rama se borró. No pude separar por paso las líneas `FALTA` del registro, porque la descarga del registro no rotula el paso (`UNKNOWN STEP`); el estado de cada paso consta en el listado de pasos del trabajo.

#### Fila C6 · documentación y ADR

`python tools/verificar_docs.py` → «✓ Sin problemas», con 162 escenarios y 24 ADR. `grep "desde TKT-009"` y `grep "⏳ TKT-009\|Se escribirá en TKT-009"` sin coincidencias en `CLAUDE.md`, `.claude`, `docs` y `tools`; `desde TKT-059` sigue presente.

**Tests devueltos al tester:** ninguno. Ningún desarrollador editó un test.

**Mutación en rutas críticas.** El tester aplicó 110 mutantes sobre una copia del verificador, con reversión comprobada por `cmp` y `sha256`. Los cuatro de la tabla de mutación del diseño murieron, y de los 106 restantes (uno por rama del código) mueren 97 y sobreviven 9. Con la suite original sobrevivían 21 mutantes exploratorios: se escribieron 31 pruebas nuevas, todas probadas contra su mutante. Los 9 supervivientes son equivalentes (`rglob` sobre una carpeta ausente, `def test_x` sin paréntesis, el valor por omisión de `--activas-base`, `fases[historia] != 1`, la codificación explícita en Python 3.15) o la spec no dice nada (un comentario con sangría en `historias_activas.txt`, dos segmentos de retiro en un título, si «tests HDU» cuenta los tests erróneos). No se inventó ninguna regla.

**Evidencia de ejecución al cerrar:**

```
python -m unittest discover -s tools/tests  -> Ran 171 tests ... OK (sin "skipped=")
python tools/verificar_escenarios.py        -> exigidos 0 · pendientes 162 · tests de fundación 180, exit 0
python tools/verificar_docs.py              -> ✓ Sin problemas. (162 escenarios, 24 ADR)
uvx zizmor@1.31.1 --offline .github/workflows -> No findings to report.
Pipeline del PR real de 009c (actions/runs/40812133855) -> 8 de 8 trabajos en verde
```

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| C1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| C1, C2, C3 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| C4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| C4 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| C6 · documentación | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Mutación y mutación exploratoria | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditoría de cierre de fase | `auditor-arquitectura` | `sonnet` | `sonnet` | La reauditoría acotada a Menores fue en `haiku` |
| Corrección de F001 y F002 | `corrector-revision` | `haiku` | `haiku` | El primer despacho murió por el límite de uso y se relanzó sin cambio de modelo |
| C5 · ajuste (rojo) | `tester-backend` | `sonnet` | `sonnet` | — |
| C5 · ajuste (verde) | orquestador | `haiku` | sin despacho | Una línea verificada por el rojo, `zizmor` y el pipeline |
| Push y ramas de ensayo | `git-entrega` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-6` | `[M]` | Cumplido | TC-40 a TC-43 y TC-55 (rechazo con código, etiqueta, identificador y título); ensayo con 27 `FALTA` |
| `CA-7` | `[M]` | Cumplido | TC-44 a TC-49 y TC-56 |
| `CA-8` | `[M]` | Cumplido | TC-50 a TC-54 |
| `CA-R4` | `[M]` | Cumplido | La suite de `tools/` pasa de 77 a 171 pruebas sin quitar ninguna ni añadir `skip` |
| `CA-15` su parte | `[M]` | Cumplido | `CLAUDE.md:78`, ficha de TKT-069 y las tres prosas de retiro de `docs/04`; TC-70c sin coincidencias |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | REQUIERE CAMBIOS, luego APROBADO | 2 Menores y 3 observaciones | 1 |
| `auditor-sql` | No aplica | No hay esquema ni migración | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 de arquitectura | arquitectura | Menor | `docs/arranque-local.md` | El trabajo `herramientas` ejecuta el verificador y la guía de reproducción no lo nombraba | Resuelto |
| F002 de arquitectura | arquitectura | Menor | `docs/05-tickets-trabajo.md` | Las fichas de TKT-009 y TKT-060 decían que «una nota en la historia» retira un escenario; la política dice el segmento del título | Resuelto |
| O001 de arquitectura | arquitectura | Observación | `docs/adr/20261015-fuentes-simuladas-analitica.md:34` | ADR aceptado que conserva la frase «con una nota en la historia» | Persiste: lo decide la persona dueña |
| O002 de arquitectura | arquitectura | Observación | `tools/tests/test_verificar_escenarios.py` | El docstring del módulo habla de las filas C1 a C3 | Persiste |
| O003 de arquitectura | arquitectura | Observación | TC-56 | Fija «162 pendientes, 0 exigidos» y fallará, a propósito, cuando se active la primera historia | Persiste: previsto |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/tickets/tkt-009/spec.md` (CA-7, ~l.195-201) | El criterio sigue hablando de «nota» de retiro; la política dice el segmento del título. Lo recoge `delta.md` | Baja |
| `docs/adr/20261015-fuentes-simuladas-analitica.md:34` | Ver O001 | Baja |
| `tools/verificar_escenarios.py` | La expresión de nombres de Python no ve `async def test_`. `CLAUDE.md` los excluye (SQLAlchemy síncrono) | Baja |
| `tools/verificar_escenarios.py` | Un comentario con sangría en `historias_activas.txt` es hoy `EntradaInvalida`; la spec no lo decide | Baja |
| `tools/verificar_escenarios.py` | Una marca `· fase 1` en una historia de columna `2` no gana sobre la columna, por el diseño; `CLAUDE.md` dice que la marca «declara» la fase | Baja |
| Pipeline | Un `it("hdu…")` dentro de un `describe.skip` sigue contando como cobertura, porque el lector no mira el bloque que lo contiene (objeción 8 del diseño). `it.skip(...)` no cuenta | Media |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/adr/20261029-politica-del-verificador-de-escenarios.md` y `docs/adr/README.md` | ADR de la política del verificador, con sus opciones descartadas y su entrada en el índice |
| `CLAUDE.md`, `README.md`, `llms.txt` | Marca de `CLAUDE.md:78` retirada; recuento de decisiones de 23 a 24 |
| `docs/04-historias-usuario.md` | Las tres prosas de retiro hablan del segmento del título; los escenarios no cambian |
| `docs/05-tickets-trabajo.md` | Ficha de TKT-069 y notas de TKT-009 y TKT-060 con el segmento del título |
| `docs/06-stack-tecnologico.md` | §7.2 (forma en TypeScript, línea `fase 2`, nota de retiro) y §9 (verificador «En uso») |
| `docs/convenciones.md` §10, `docs/arranque-local.md`, `tools/README.md` | Fila del verificador, reproducción local y sección del verificador sin «Pendiente» |
| `sdd/tickets/tkt-009/design.md` | Estados de las filas y TC-58 a 27 |

`python tools/verificar_docs.py` → «✓ Sin problemas».

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas, con mutación exploratoria
- [x] La auditoría de arquitectura terminó en `APROBADO`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] Rama correcta y sin secretos en el diff
- [ ] `ruff`, `mypy` y `lint-imports` no se ejecutaron: el ticket no toca `backend/`; el trabajo `backend` del pipeline está en verde

Quedan, como en TKT-009a, dos acciones locales tuyas: restaurar `frontend/node_modules` y revisar las contraseñas de roles de tu base de desarrollo.

## Revisión (`/sdd-revisar`, 2026-10-29)

**Completitud, corrección y coherencia.** Los cinco criterios `[M]` de la spec (`CA-6`, `CA-7`, `CA-8`, `CA-R4` y la parte de `CA-15`) tienen resultado y evidencia en este documento. Se implementó lo de la spec sin alcance de más y los archivos coinciden con los del diseño.

**Suite ejecutada en esta revisión:**

```
uv run pytest -q                    -> 1138 passed in 229.84s (0:03:49), exit=0
uv run ruff check . / format --check -> All checks passed! / 153 files already formatted
uv run mypy .                       -> Success: no issues found in 153 source files
uv run lint-imports                 -> Contracts: 15 kept, 0 broken.
herramientas.verificar_float        -> hallazgos: 0
python tools/verificar_docs.py      -> ✓ Sin problemas.
python tools/verificar_escenarios.py -> exigidos 0 · pendientes 162, exit 0
uvx zizmor@1.31.1 --offline .github/workflows -> No findings to report.
python -m unittest discover -s tools/tests   -> Ran 178 tests ... OK (sin "skipped=")
uvx ruff check --config backend/pyproject.toml (verificador y sus dos archivos de pruebas) -> All checks passed!
```

El frontend no se tocó en este ticket. Su evidencia es el trabajo `frontend` del pipeline.

**Auditorías de la revisión.** `auditor-arquitectura` y `auditor-seguridad` dieron `APROBADO`. `auditor-codigo` y `auditor-docs` dieron `REQUIERE CAMBIOS`, y el ciclo 1 de corrección resolvió todos sus hallazgos:

| ID | Auditor | Severidad | Hallazgo | Estado |
|---|---|---|---|---|
| F001 de código | código | Mayor | `recolectar_tests` no atrapaba `UnicodeDecodeError`: un test que no era UTF-8 daba traza y código 1 en lugar del 2 de «entrada mal formada». Ahora usa la lectura común y el mensaje nombra la ruta relativa | Resuelto |
| F002 de código | código | Mayor | Un test de TypeScript comentado (`// it(…)` o `/* test(…) */`) cubría el escenario: falso verde. `_lineas_con_codigo` ignora líneas y bloques comentados | Resuelto |
| F003 de código | código | Mayor | Tres errores de `ruff` en el archivo de pruebas | Resuelto |
| F004 de código | código | Menor | `CARPETAS_DE_TESTS`, constante sin uso | Resuelto |
| F005 de código | código | Menor | TC-56 fijaba el total real de 162 escenarios | Resuelto: el total se calcula del documento |
| F006 de código | código | Menor | `type: ignore` de conveniencia y duplicación en las pruebas | Resuelto |
| F001 a F003 de docs | docs | Menor | `tools/README.md`: causas del código 2 incompletas y rótulo del resumen; la fila de `it.skip` de este documento era inexacta | Resuelto |
| F001 a F005 de seguridad | seguridad | Baja | Lectura sin tope; `--activas-base` inexistente se ignora; enlaces simbólicos; la política de repositorio (CODEOWNERS) | Persiste: observaciones |
| O004 de arquitectura | arquitectura | Observación | Este documento describía mal el hueco de `it.skip` | Resuelto con la fila de «Hallazgos fuera de alcance» |

**Pruebas del ciclo 1.** Primero el rojo del tester: 89 pruebas, 84 en verde y 5 en rojo por la razón esperada (la traza de `UnicodeDecodeError` en dos casos, y el test comentado que cubre un escenario en tres). Después el verde del desarrollador: 89 en verde y 176 en toda la suite de `tools/`.

**Decisión del desarrollador, para revisar** (asumido, límite de A-8 de `sdd/tickets/tkt-009/spec.md`): el código que sigue a un `*/` en la misma línea (`/* x */ it("hdu…")`) cuenta como test, porque no es comentario. Un `/*` que abre un bloque a mitad de una línea de código no abre bloque: es un límite de A-8.

**Observaciones que quedan abiertas, ninguna bloqueante:** las del ADR `20261015-fuentes-simuladas-analitica.md:34`, el criterio CA-7 de la spec común de TKT-009 (resuelto en su fila A-7, pero el Gherkin sigue hablando de «nota»), la propuesta de `auditor-codigo` de partir `clasificar`, y la de proteger `tools/` y `.github/` con CODEOWNERS (política de repositorio).

**Ciclo 2 de corrección (código y documentación).** La reauditoría de código encontró un Mayor nuevo (F007): cuatro mutantes de `_lineas_con_codigo` (no seguir los bloques de varias líneas, no leer lo que sigue a `*/` en la misma línea o en otra, y quitar la regla `*`) sobrevivían con la suite en verde, porque en los casos de bloque cada línea interior empezaba por ` * ` y esa regla las descartaba sola. El código era correcto; faltaban las pruebas. Se añadieron dos (`test_tc43_recolectar_typescript_bloque_sin_asterisco_y_codigo_tras_el_cierre` y `test_tc43_recolectar_typescript_una_linea_con_asterisco_suelta_fuera_de_bloque_no_es_test`) y cada una cae con su mutante; el cuarto mutante no resultó equivalente y lo mata `test_tc43_recolectar_typescript_una_linea_con_asterisco_suelta_fuera_de_bloque_no_es_test`. También se quitó el último `type: ignore` (F006). La suite del verificador queda en 91 pruebas y la de `tools/` en 178, sin `skipped=`. La reauditoría de documentación pidió dos Menores (F004 y F005): decir en `tools/README.md` y en `docs/06` §7.2 que en TypeScript los comentarios no cuentan.

| ID | Auditor | Severidad | Hallazgo | Estado |
|---|---|---|---|---|
| F007 de código | código | Mayor | Pruebas de `_lineas_con_codigo` que no discriminaban: cuatro mutantes sobrevivían | Resuelto |
| F004 de docs | docs | Menor | `tools/README.md` no decía que en TypeScript se ignoran los comentarios | Resuelto |
| F005 de docs | docs | Menor | `docs/06` §7.2 no excluía los tests comentados | Resuelto: §7.2 recoge el límite de A-8 |
| F006 de docs | docs | Mayor | la regla de comentarios de TypeScript se citaba como límite de A-8 sin estar en la spec | Resuelto |
| F007 de docs | docs | Menor | La fila «F005 de docs» de este registro figuraba como resuelta antes de corregir `docs/06` §7.2 | Resuelto |
| F008 de docs | docs | Menor | La fila A-8 de la spec no decía que el código que sigue al `*/` de un bloque en la misma línea sí se lee | Resuelto: ahora lo enuncia |

**Ciclo 3 de documentación y veredicto.** La tercera reauditoría de documentación resolvió F005 y F006 y encontró dos Menores más (un registro de este documento y la frase de A-8 sobre el código que sigue a `*/`). Con los tres ciclos agotados y solo Menores vivos, se aplicaron con el texto literal del auditor y se verificaron contra el código (`_lineas_con_codigo` lee `' it("hdu001_esc01 x")'` tras un `*/`) y con `verificar_docs.py`, **sin una cuarta reauditoría**. Quedan por tanto `auditor-docs` en `REQUIERE CAMBIOS` en su último veredicto formal, `auditor-arquitectura`, `auditor-seguridad` y `auditor-codigo` en `APROBADO`. Es la misma excepción que se aplicó en TKT-009a: la persona dueña debe aceptarla al archivar.

**Reauditoría de documentación posterior (2026-10-28).** Se pidió antes de ejecutar TKT-009b. `auditor-docs` verificó que los dos Menores del ciclo 3 quedaron bien aplicados (F004 a F008 en `Resuelto`) y encontró un Menor nuevo, F009: la objeción 8 de `sdd/tickets/tkt-009/design.md` decía que `it.skip(...)` cubría un escenario, y el verificador no lo lee (`_TEST_TYPESCRIPT` exige el paréntesis pegado a `it`, `test` o `describe`); lo que sí cubre es un `it(...)` dentro de un `describe.skip`. Se corrigió con el texto literal del auditor, y una segunda reauditoría dio `APROBADO` sin hallazgos nuevos, con `verificar_docs.py` en verde y 178 pruebas de `tools/` en verde. Quedan sus observaciones O1 y O2, que no bloquean. Con ello, el último veredicto formal de `auditor-docs` es `APROBADO` y la excepción del párrafo anterior deja de aplicarse.

**Veredicto:** cinco criterios `[M]` cumplidos, sin hallazgo Mayor ni Crítico vivo, y la pila de comprobaciones locales en verde. `LISTO PARA PR`.
