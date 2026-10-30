# Impl · TKT-062b · Revisión automatizada

> [← index](_index.md) | [← design](../tkt-062/design.md) | Siguiente: `/sdd-revisar`, y después delta

## Qué se implementó

Las filas B1, B2, B3a, B3b, B6, B7 y B8 del diseño común, con el ciclo rojo, verde y refactor de cada una. Se crearon el flujo `revision-ia.yml` (dos trabajos: `revision` lee con permisos de solo lectura y `publicar` comenta tras el filtro), el filtro `tools/publicar_revision.py`, las instrucciones `.claude/revision-pr.md`, el ADR-028 y la documentación afectada, y se escribió la excepción nombrada de `secrets.` en las pruebas de TKT-009. La acción `anthropics/claude-code-action` queda fijada por SHA `6d5ae526d25ce88daa2200be073e1a373167f064`, que es la etiqueta `v1.0.265` (comprobada con `git ls-remote`).

Las filas B4 y B5 se retiran el 2026-10-30 por el recorte de alcance (ver `_index.md`, «Decisiones registradas»): no las ejecuta este ticket y este documento no contiene su evidencia.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-30 | **Ajuste mayor decidido por la persona responsable (F001 a F003).** El modelo pierde `Bash` (`--allowedTools "Read(./**),Glob,Grep"`; `--disallowedTools` añade `Bash`, `Read(//proc/**)` y `Read(//sys/**)`). Un paso nuevo y sin secreto de `revision` escribe `.revision-pr/pr.json` y `.revision-pr/pr.diff` antes de la acción. El filtro compara la cita con `fullmatch`, descarta claves ofuscadas (`skant` tras quitar lo no alfanumérico) y el registro no imprime `archivo` si hay clave. Consta en la sección «Ajuste del 2026-10-30» del diseño. La sintaxis de las reglas `Read(//proc/**)` y `--disallowedTools` se verificó el 2026-10-30 con Context7 (`/websites/code_claude`, páginas de permisos de Claude Code): `//ruta` es absoluta y las reglas de lectura excluyen rutas denegadas de `Grep` y `Glob` solo «de mejor esfuerzo» | La primera auditoría de seguridad halló que `Read(./**)` solo acota `Read`; con `Bash(gh pr view:*)`, `Glob` y `Grep` el modelo podía alcanzar la clave del entorno |
| 2026-10-30 | Segundo ciclo: `_normalizar` aplica NFKC (N001) y el registro imprime `archivo` de una cita inválida solo si figura en `--archivos` (N002) | Reauditoría de seguridad |
| 2026-10-30 | `_para_el_registro` usa `re.sub(r":(?=:)", ": ", …)` en lugar de `str.replace("::", ": :")` | Con `:::` el `replace` dejaba un `::` residual |
| 2026-10-30 | Línea añadida en `.claude/agents/ingeniero-devsecops.md` (regla «Secretos solo en GitHub Secrets») con la excepción de ADR-028 | Evita contradecir la línea que nombra la excepción |
| 2026-10-30 | Un hallazgo sin `linea` se nombra solo `archivo` | El diseño no cubría el caso |
| 2026-10-30 · Recorte de alcance | Se retiran B4 y B5; el flujo queda construido e inactivo sin clave de API, y la revisión es local con `/code-review`. Detalle en `_index.md`, «Decisiones registradas» | Falta de presupuesto para la clave de API, decisión de la persona responsable |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.github/workflows/revision-ia.yml` | nuevo | entrega continua |
| `.claude/revision-pr.md` | nuevo | entrega continua |
| `tools/publicar_revision.py` | nuevo | herramientas |
| `tools/tests/test_publicar_revision.py` | nuevo | pruebas |
| `tools/tests/test_definicion_revision.py` | nuevo | pruebas |
| `tools/tests/test_definicion_ci.py`, `test_definicion_dependabot.py` | modificado (excepción de secretos, TC62-28 a TC62-30) | pruebas |
| `docs/adr/20261029-revision-automatizada-de-pr-con-unica-excepcion-de-secretos.md` y `docs/adr/README.md` | nuevo y modificado | documentación |
| `docs/convenciones.md` §12, `docs/06-stack-tecnologico.md`, `tools/README.md`, `CLAUDE.md`, `README.md`, `llms.txt`, `.claude/agents/ingeniero-devsecops.md` | modificado | documentación |
| `sdd/tickets/tkt-062/design.md`, `sdd/tickets/tkt-062b/_index.md` | modificado | proceso |

Ningún archivo de `backend/` ni de `frontend/`.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC62-10, 11, 13, 14, 18, 26, 27, 31, 33 | `test_tkt062_ca01…` a `ca10…` en `test_definicion_revision.py` | feliz y **rechazo** estático | `CA-1` a `CA-4`, `CA-7`, `CA-8`, `CA-10` | FALLA (8 fallos: el flujo no existía) | PASA |
| TC62-17 | `test_tkt062_ca04_esc01_las_instrucciones_remiten_y_no_copian` | **rechazo** estático | `CA-4` | FALLA (el archivo no existía) | PASA |
| TC62-20 a 25, 42 | `test_tkt062_ca05…` y `ca07_esc03…` en `test_publicar_revision.py` | feliz y **rechazo** | `CA-5`, `CA-7` | FALLA (23 tests: el módulo no existía) | PASA |
| TC62-28 a 30 | mutantes de la excepción de `secrets.` | **rechazo** | `CA-7` | FALLA (37 fallos y 3 errores) | PASA |
| TC62-41 | `test_tkt062_ca12_esc01_la_documentacion_de_062b_describe_la_revision` | estático | `CA-12` | FALLA (20 frases ausentes) | PASA |
| TC62-R1 a R4 | `test_tc13…`, `test_tc21…`, `test_tc22…`, `test_tc18…`, `test_tc15…`, `test_car4…` | regresión | `CA-R1` a `CA-R4` | VERDE | PASA |

### Ciclo TDD por fila

Las salidas literales de cada rojo están en los informes de los despachos; resumen:

- **B1.** Rojo: `Ran 23 tests`, `FAILED (failures=35)` por «falta tools/publicar_revision.py». Verde: 23 tests OK; suite `Ran 421 tests … OK`.
- **B2.** Rojo: `Ran 195 tests`, `FAILED (failures=37, errors=3)`. Verde: `Ran 434 tests … OK`.
- **B3a.** Rojo: `Ran 20 tests`, `FAILED (failures=8)` por la ausencia de `revision-ia.yml`. Verde: `Ran 454 tests … OK`; `uvx zizmor@1.31.1 --offline .github/workflows` sin hallazgos.
- **B3b.** Rojo: un fallo por la ausencia de `.claude/revision-pr.md`. Verde con B6: `verificar_docs` en cero, 28 ADR.
- **B7.** Rojo: 20 frases ausentes. Verde: `Ran 463 tests … OK`, markdownlint y Vale limpios.
- **Ajuste F001 a F003.** Rojo: `Ran 470 tests`, `FAILED (failures=12)`. Verde: `Ran 470 tests … OK`.
- **Ajuste N001 y N002.** Rojo: `FAILED (failures=16)` en 30 tests. Verde: `Ran 474 tests … OK`.

**Evidencia de ejecución al cerrar** (`python -m unittest discover -s tools/tests`, sin saltos):

```text
Ran 474 tests in 14.983s

OK
```

También en verde: `python tools/verificar_docs.py` («✓ Sin problemas», 28 ADR), `markdownlint-cli2@0.24.0` (0 problemas en 133 archivos), Vale 3.25.1.0 (sin alertas) y zizmor 1.31.1 (sin hallazgos, 6 suprimidos por la persona por omisión).

**Mutación manual.** En `publicar_revision.py`: comprobar la cita antes que la clave en el registro (cae TC62-42 y el control del registro); `or` por `and` en `separar_por_cita` (9 tests); eliminar la comprobación de clave (4 tests). El intercambio del orden dentro de `separar_por_cita` es un mutante equivalente (la condición es conmutativa). En el oráculo de secretos se aplicaron 16 mutaciones, todas con caída tras añadir tres casos. Los mutantes por compuerta del diseño viven en las clases `PruebasDeMutantes…`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| B1 rojo y verde | `tester-backend`, `ingeniero-devsecops` | `sonnet` | `sonnet` | — |
| B2 | `tester-backend` | `sonnet` | `sonnet` | — |
| B3a, B3b y B6 | `tester-backend`, `ingeniero-devsecops` | `sonnet` | `sonnet` | — |
| B7 rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| B7 verde | `ingeniero-devsecops` | `haiku` | `haiku` | Tarea mecánica verificable por comando (§14.2) |
| B8 | `tester-backend` | `sonnet` | `sonnet` | — |
| Ajuste F001 a F003, rojo y verde | `tester-backend`, `ingeniero-devsecops` | `sonnet` | `sonnet` | — |
| N001 y N002 | `tester-backend`, `corrector-revision` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-seguridad`, `auditor-docs` | `sonnet` | `sonnet` | — |

Apertura de la rama con `git-entrega` en `haiku`.

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-2`, `CA-3` (esc. 1 y 3), `CA-4` (esc. 1), `CA-5`, `CA-7`, `CA-8` (esc. 2), `CA-10` (esc. 1) | `[M]` | Cumplido en lo estático | TC62-10 a 33 |
| `CA-1` | `[M]` | Cumplido solo en lo estático (el flujo se dispara y usa la acción). Que «comenta» queda **recortado**: no se ha ejecutado, no hay clave | TC62-10; recorte en `_index.md` |
| `CA-3` esc. 2, `CA-4` esc. 2 (R3), `CA-8` esc. 1, `CA-10` esc. 2, `CA-11`, `CA-S1` | `[M]`/`[S]` | Recortado (decisión del 2026-10-30, ver `_index.md`) | Rondas R0b a R6 (fila B5) |
| `CA-9` | `[M]` | Parcial: el ajuste que impide a Actions aprobar PR sigue vigente y consta abajo; la clave dedicada, su tope y el secreto están recortados (decisión del 2026-10-30, ver `_index.md`) | Fila B4, retirada, y lectura de abajo |
| `CA-12` | `[M]` | Cumplido | TC62-41 |
| `CA-R1` a `CA-R4` | `[M]` | Cumplido en local | TC62-R1 a R4; falta la ejecución verde del PR |

Un Must incumplido no se aprueba: los pendientes de la tabla bloquean `/sdd-completar`.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | Primera pasada APROBADO; tras el recorte, REQUIERE CAMBIOS por coherencia documental, cerrada por verificación mecánica por decisión de la persona responsable del 2026-10-30 | Un Mayor de gobierno (F-01, resuelto en `spec.md`) y menores de redacción, corregidos | 4 |
| `auditor-seguridad` | APROBADO con condición de cierre | F001 a F003 y N001 y N002 resueltos. **N003** abierto como condición manual: confirmar en la ronda R2c que `Grep` y `Glob` sobre `/proc/self/environ` son rechazados. Si no, denegarlos explícitamente y reauditar | 3 |
| `auditor-docs` | Tres ciclos tras el recorte; los hallazgos menores quedaron corregidos y verificados por las herramientas | Menores de redacción y de coherencia con el recorte | 3 |

## Pendientes de la persona dueña

Ningún trámite externo bloquea este ticket. Quedan por hacer, y no se han hecho: la ejecución verde de las diez comprobaciones requeridas en el PR del ticket (`CA-R1` a `CA-R4`), que verifica `/sdd-completar` antes de fusionar. **Condición de activación N003** (que `Grep` y `Glob` no lean `/proc/self/environ`), que la auditoría de seguridad dejó abierta y que consta también en el ADR-028 y en `_index.md`. B4 y B5 se retiran el 2026-10-30 por el recorte de alcance (ver `_index.md`, «Decisiones registradas»). La activación de la revisión está en ADR-028, «Estado de la activación».

## Fuera de alcance anotado

- `concurrency` (F004) y la sanitización de `@menciones` e imágenes del comentario: ticket futuro sugerido.
- Homoglifos y codificaciones (base64) no los cubre ningún filtro de texto: los cubre la ausencia de `Bash` y de acceso al entorno (N003).

## Verificación final

Esta verificación es anterior al recorte del 2026-10-30; el registro de estados de `_index.md` manda sobre sus huecos.

Revisión de 2026-10-30 con `/sdd-revisar`. **Veredicto: `REQUIERE CAMBIOS`.** La verificación de completitud (paso 1) falla, así que no se emite `LISTO PARA PR` ni se despachan auditorías nuevas: las tres de `/sdd-ejecutar` ya están cerradas y el diff no cambió desde entonces.

**Suite ejecutada de nuevo** (Docker responde, versión 29.9.2; no hay `backend/` ni `frontend/` en el diff, por lo que `pytest`, `ruff`, `mypy` y `lint-imports` no aplican):

```text
python -m unittest discover -s tools/tests  ->  Ran 474 tests in 14.463s  OK
python tools/verificar_docs.py              ->  ✓ Sin problemas.
uvx zizmor@1.31.1 --offline .github/workflows -> No findings to report. Good job! (6 suppressed)
```

El diff no toca `docs/api/openapi.yaml`, así que no hay nada que señalar por convenciones §12 punto 11. El rastro del ciclo TDD (rojo antes de verde, tests escritos solo por el tester) consta fila por fila arriba.

**Huecos que impiden aprobar** (todos son criterios `[M]` o `[S]` que solo se demuestran en el repositorio real, no en el pipeline de un PR, y por eso no caben en la excepción de «se verifica en `/sdd-completar`»):

| Criterio | Qué falta | Quién |
|---|---|---|
| `CA-9` | Fila B4: ajuste que impide a Actions aprobar, clave dedicada con tope, secreto y prueba del escaneo, con salidas fechadas | Persona dueña |
| `CA-3` esc. 2, `CA-4` esc. 2, `CA-8` esc. 1, `CA-10` esc. 2, `CA-11`, `CA-S1` | Fila B5: rondas R0b a R6 con su evidencia | Persona dueña |
| Condición N003 de la auditoría de seguridad | Ronda R2c: `Grep` y `Glob` sobre `/proc/self/environ` rechazados. Si no, denegarlos explícitamente y reauditar | Persona dueña |

Los criterios estáticos (`CA-1` a `CA-5`, `CA-7`, `CA-12` y `CA-R1` a `CA-R4` en local) tienen cobertura verificada, con su test de rechazo.

**Siguiente:** `/sdd-revisar TKT-062b` con el recorte registrado en `_index.md`.

**Segunda verificación (2026-10-30, tras el recorte).** Suite: 474 pruebas OK; `verificar_docs`, markdownlint y Vale limpios; zizmor sin hallazgos. Auditoría de documentación: tres ciclos, hallazgos menores corregidos. Auditoría de arquitectura: tres ciclos; el tercero deja un Mayor de gobierno (F-01), resuelto reflejando el recorte en `spec.md` («Recorte de alcance del 2026-10-30»), más F-02 a F-04 corregidos. Falta la reauditoría final, que exige la autorización de la persona responsable porque el límite de tres ciclos está agotado.

**Lecturas de GitHub, solo lectura, del 2026-10-30** (`gh api repos/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/permissions/workflow`, `.../branches/Produccion/protection` y `gh secret list`): el ajuste «can_approve_pull_request_reviews» está en `false`; las diez comprobaciones requeridas de `Produccion` no incluyen ninguna de la revisión (`Revisión IA`); la protección exige una aprobación. `gh secret list` no muestra `ANTHROPIC_API_KEY`, como corresponde al recorte.

**Cierre de la revisión (2026-10-30).** La reauditoría final autorizada devolvió `REQUIERE CAMBIOS` con menores de redacción entre `spec.md`, `impl.md`, `_index.md` y el ADR-028 (N-03 a N-13). Se corrigieron N-03 a N-08 y N-11 a N-13 en esos documentos; N-09 se contrastó con el Gherkin de la spec común (CA-3: esc. 1 token, esc. 2 rechazo de aprobación, esc. 3 inyección) y la fila de la spec es coherente; N-10 queda como historial. Verificación mecánica posterior: 474 pruebas OK, `verificar_docs` limpio, markdownlint y Vale sin alertas, zizmor sin hallazgos. **No hay una auditoría de IA posterior a estas correcciones.**
