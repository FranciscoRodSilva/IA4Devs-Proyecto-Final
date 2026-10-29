# Delta · TKT-009c · Verificador de escenarios sin test

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Verificador de escenarios sin test, de unas 450 líneas y solo con la biblioteca estándar | `tools/verificar_escenarios.py` | Hacer cumplir [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md): un escenario que cuenta y no tiene un test que lo nombre falla el pipeline. Lee `docs/04-historias-usuario.md`, `tools/historias_activas.txt` y los tests de `backend/tests`, `frontend/src`, `frontend/scripts` y `frontend/e2e` |
| Lista de historias activas, con solo tres líneas de comentario | `tools/historias_activas.txt` | Que la planificación de cada sprint declare qué historias cuentan. Ninguna historia sale nunca de la lista y la línea `fase 2` activa los escenarios de fase 2 |
| Pruebas del verificador, 91 casos | `tools/tests/test_verificar_escenarios.py` | Probar cada regla con documentos de ejemplo y su rechazo con el contrato completo (código de salida, etiqueta, identificador y título), más el árbol real (TC-56) y 31 casos nacidos de una mutación exploratoria de 110 mutantes |
| Paso «Verificar que cada escenario exigido tenga su test» en el trabajo `herramientas` | `.github/workflows/ci.yml` | Ejecutar el verificador en cada pull request, con la base del PR por `env` y con `if: ${{ !cancelled() }}` para que una prueba rota no lo tape |
| ADR de la política del verificador | `docs/adr/20261029-politica-del-verificador-de-escenarios.md` | Registrar las decisiones con sus opciones descartadas: la línea `fase 2`, el segmento de retiro en el título, la comparación con la base del PR, la forma en TypeScript y el anclaje del nombre |
| Sección del verificador | `tools/README.md` | Uso, argumentos, etiquetas, códigos de salida y cómo se actualiza la lista |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Regla de aceptación | `CLAUDE.md:78` | «Un verificador en CI falla … (desde TKT-009)» → sin la marca: el verificador ya corre en `herramientas` |
| Recuento de decisiones | `CLAUDE.md`, `README.md`, `llms.txt` | 23 → 24 ADR |
| Prosas de retiro | `docs/04-historias-usuario.md` (tres) | «una nota en la historia» → TKT-069 añade ` · retirado por TKT-069` al título del escenario. Los escenarios y sus títulos no cambian: siguen siendo 162 |
| Fichas de tickets | `docs/05-tickets-trabajo.md` (TKT-009, TKT-060 y TKT-069) | «nota en la historia» → el segmento del título |
| Stack | `docs/06-stack-tecnologico.md` §7.2 y §9 | Verificador pendiente → «En uso»; §7.2 describe la forma `"hduXXX_escNN · …"` en TypeScript, la línea `fase 2`, el retiro por segmento y que un test comentado no cuenta |
| Convenciones y arranque | `docs/convenciones.md` §10, `docs/arranque-local.md`, `tools/README.md` | La fila de escenarios sin test y la reproducción local nombran el verificador; desaparece la sección «Pendiente» |
| Supuestos de la spec común | `sdd/tickets/tkt-009/spec.md` (A-7, A-8) | A-7 abierta → resuelta por el ADR; A-8 recoge la regla de comentarios de TypeScript |
| Plan de pruebas | `sdd/tickets/tkt-009/design.md` | TC-58 decía 26 `FALTA`; HDU-001 tiene 27 |
| Pruebas de la definición del flujo | `tools/tests/test_definicion_ci.py` | Se amplían TC-57 y sus mutantes con el paso nuevo |
| Tickets futuros sugeridos | `sdd/tickets/tkt-009/_index.md` (línea 71) | «Un `it.skip` que nombra un escenario cuenta como cobertura» → «Un `it("hdu…")` dentro de un `describe.skip` cuenta como cobertura; `it.skip(...)` no» |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| La marca «(desde TKT-009)» del verificador de escenarios, «⏳ TKT-009» y «Se escribirá en TKT-009» | `CLAUDE.md:78`, `docs/06`, `tools/README.md` | El verificador existe y corre en el pipeline |

## Comportamiento observable nuevo

- Un pull request que active una historia sin que cada uno de sus escenarios tenga un test con la forma `test_hduNNN_escNN_…` (o `"hduNNN_escNN · …"` en TypeScript) falla el trabajo `herramientas` con una línea `FALTA` por escenario y su título.
- Mientras ninguna historia esté activa, el verificador informa lo pendiente por historia y termina en 0: hoy, 162 escenarios pendientes y 180 tests de fundación contados.
- Quitar una historia o la línea `fase 2` de `tools/historias_activas.txt` falla el pipeline, porque se compara con el archivo de la base del PR.
- Un test de TypeScript comentado no cuenta como cobertura, y un archivo de test que no esté en UTF-8 da el código 2 con su ruta en el mensaje.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoint, DTO, tipo generado o esquema | Ninguno | No |
| Forma del nombre de un test de historia | `test_hduNNN_escNN_…` en Python y `"hduNNN_escNN · …"` en TypeScript | No: hoy no existe ningún test de historia |
| Título de escenario | Se admite el segmento ` · retirado por TKT-0NN`, además del ya existente ` · fase 2` | No: `verificar_docs.py` solo lee `**Escenario N:` y sigue contando 162 |

## Decisiones (ADR)

Se creó `docs/adr/20261029-politica-del-verificador-de-escenarios.md` (formato MADR, con su entrada en el índice). Recoge cinco decisiones con sus opciones descartadas:

- **Fase 2:** la línea `fase 2` en `historias_activas.txt`, frente a un archivo propio.
- **Retiro:** el segmento del título, frente a un comentario HTML invisible o un párrafo de formato fijo.
- **Historias activas:** leer el archivo y compararlo con la base del PR, frente a inferirlas de los tests existentes, que no verían una historia activa sin tests.
- **Forma en TypeScript:** `"hduNNN_escNN · …"`, marcada `(asumido)`.
- **Anclaje del nombre:** `(?=$|[_\s·])`, frente a una expresión sin anclaje donde `esc04x` cubriría el escenario 4.

Evidencia: `test_tc42_salida_esc04x_no_cubre_por_el_anclaje`, `test_tc43_…`, `test_tc48_…`, `test_tc49_…`, `test_tc53_…` y `test_tc54_…`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un ensayo en el pipeline prueba lo que las pruebas locales no ven: una compuerta puede quedar tapada por otra que falla antes. Aquí el verificador se omitía porque TC-56 fija «0 exigidos» y caía primero | Primera ronda del PR de ensayo: «Pruebas de tools/» en rojo y el paso del verificador `skipped` | Todo paso de CI que dependa de que otros pasos pasen: `if: ${{ !cancelled() }}` |
| Una prueba que fija un valor del árbol real (aquí «162 pendientes») rompe el cambio que lo mueve; calcularlo del documento evita tocar la prueba en cada sprint | F005 de código y TC-56 | Pruebas sobre el árbol real |
| Una regla de lectura que descarta líneas (` * ` dentro de un bloque) puede esconder la regla del bloque: las pruebas con asterisco en cada línea no distinguen. Hacen falta casos sin asterisco y con código tras el cierre | Cuatro mutantes de `_lineas_con_codigo` que sobrevivían | Cualquier lector de texto con comentarios |
| `it.skip(` y `describe.skip(` no se leen con una expresión que exige `(` pegado a `it`, `test` o `describe`; sí se lee un `it("hdu…")` dentro de un `describe.skip`. El hueco no es el que se creía | Comprobación ejecutada por `auditor-arquitectura` | `docs/06` §7.2 y objeción 8 del diseño |
| La salida de un registro de GitHub Actions bajada con `gh run view --log` rotula los pasos como `UNKNOWN STEP` cuando falla el trabajo: no se separan las líneas de un paso concreto. El estado de cada paso sí consta en `--json jobs` | Evidencia del ensayo C5 | Citar evidencia de pasos |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `guardrail` | La mutación exploratoria que se hizo ya en `/sdd-ejecutar` (110 mutantes, 21 ramas sin prueba) no evitó que la revisión encontrara tres Mayores de código (comentarios de TypeScript, lectura que no era UTF-8, linter en rojo) y luego un cuarto de pruebas que no discriminaban. La mutación se aplicó a las ramas que se enumeraron, no a lo que no se pensó: la regla de comentarios y la lectura de archivos de test no estaban entre ellas | Media |
| `agente` | De nuevo cada ciclo de corrección de documentación produjo Menores nuevos sobre el texto del ciclo anterior (tres ciclos, siete hallazgos), y los auditores sin memoria no podían reclasificar los previos: hubo que repetirles el historial. Séptima vez que aparece | Alta |
| `comando` | Ningún comando prevé el trabajo apilado: TKT-009c depende de una rama cuyo PR no está fusionado, así que el PR de 009c apunta a la rama de 009a y no a `Produccion`. La rama base de `git-entrega` en modo apertura es siempre `Produccion` y hubo que sobrescribirla a mano | Media |
| `herramienta` | La descarga del registro de un trabajo fallido rotula los pasos como `UNKNOWN STEP`, así que `/sdd-ejecutar` no puede citar la salida de un paso concreto como evidencia. Convendría guardar la salida del verificador como artefacto o en el resumen del trabajo (`$GITHUB_STEP_SUMMARY`) | Baja |
| `convención` | `ruff` no corre sobre `tools/` en el pipeline: `auditor-codigo` encontró tres errores de linter en un archivo de pruebas que el CI nunca habría marcado. Segundo ticket que lo señala (TKT-009a) | Media |
| `contexto` | Un subagente murió por el límite de uso a mitad de un encargo, sin dejar nada en disco (el árbol no tenía ningún cambio de ese archivo). Se relanzó con el mismo encargo y funcionó | Baja |
| `plantilla` | El diseño estimaba unas 440 líneas para la parte c y llegó a 1,949 entre verificador (450) y pruebas (1,499). De nuevo, las estimaciones no cuentan las pruebas de un verificador, que son la mayor parte | Media |
| `modelo` | Ninguna fila de `haiku` necesitó subir a `sonnet`. El tester fue en `sonnet` en todas las filas de rojo y mutación; la reauditoría de código con Mayores en `sonnet` y las de Menores en `haiku`. Una línea de `ci.yml` se aplicó sin despachar agente, verificada por el rojo y `zizmor` | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Un `it("hdu…")` dentro de un `describe.skip`, un `@pytest.mark.skip` sobre un `def test_hdu…` o un `it("…", { skip: true })` cuentan como cobertura sin ejecutarse | La spec no lo pide; el verificador mira nombres, no si el test corre | Ticket futuro: excluir los tests saltados (objeción 8 del diseño) |
| Un comentario que sigue a código en la misma línea y un `/*` a mitad de una línea de código no se descartan | Límite declarado de A-8 | Ampliar la lectura si aparece un caso real |
| `clasificar` hace unas 90 líneas con tres responsabilidades | Observación de `auditor-codigo`, sin impacto en el comportamiento | Partir en `_hechos_de_tests`, `_clasificar_escenarios` y `_hechos_de_la_base` |
| `--activas-base` inexistente se ignora sin aviso; un archivo de test enlazado simbólicamente fuera de la raíz se lee; un `historias_activas.txt` con BOM da un mensaje confuso | Riesgo bajo; en CI la base la decide `git cat-file` con `fetch-depth: 0` | Endurecer el verificador con TKT-062 o con CODEOWNERS sobre `tools/` |
| Proteger `tools/` y `.github/` con revisión obligatoria | Con `pull_request` el PR ejecuta su propia copia del verificador; solo la base protege contra quitar historias | TKT-062 (protección de rama) |
| `ruff` no corre sobre `tools/` en el pipeline | Fuera del alcance | Ticket de calidad de `tools/`, con el de TKT-009a |
| El ADR aceptado `docs/adr/20261015-fuentes-simuladas-analitica.md:34` conserva «con una nota en la historia» | Un ADR aceptado lo decide la persona dueña | Nota fechada de actualización en ese ADR |
| El criterio CA-7 de la spec común de TKT-009 sigue hablando de «nota» de retiro (~l.195-201) | Lo supera A-7 y el ADR | Reescribir el Gherkin cuando se cierre el paraguas TKT-009 |
| El test de una historia con la marca ` · fase 1` en una historia de columna `2` no gana sobre la columna | `CLAUDE.md` dice que la marca «declara» la fase; el diseño dice lo contrario. Hoy no ocurre en el documento real | Decidir qué gana si aparece el caso |

## Pull request

**Título:** `TKT-009c · Verificador de escenarios sin test`
**Origen:** `agent` (pasa a `agent+human-review` cuando una persona lo revise)
**Base:** `tkt-009a-pipeline-pruebas` mientras el PR #2 de TKT-009a no esté fusionado; después, `Produccion`. El PR real de 009c es el #6.
**Cuerpo:**

> **Qué.** Añade `tools/verificar_escenarios.py`, que hace cumplir ADR-012: un escenario que cuenta y no tiene un test que lo nombre falla el pipeline. Un escenario cuenta desde que su historia está en `tools/historias_activas.txt`; los de fase 2 cuando ese archivo contiene la línea `fase 2`; y uno retirado con el segmento ` · retirado por TKT-0NN` en su título deja de contar. El trabajo `herramientas` de `ci.yml` lo ejecuta con la base del PR, y falla si una historia o la línea `fase 2` salen de la lista. Incluye el ADR de la política, 91 pruebas con documentos de ejemplo y el árbol real, y retira las marcas «desde TKT-009» del verificador.
>
> **Por qué.** `CLAUDE.md` promete que un verificador en CI falla si un escenario se queda sin test, y hasta ahora no existía. Es la segunda de cuatro partes de TKT-009 (a → c → b → d).
>
> **Criterios cubiertos.** `CA-6`, `CA-7`, `CA-8`, `CA-R4` y la parte de `CA-15` de esta parte.
>
> **Cómo verificarlo.** El pipeline del PR está en verde sobre `229bbf7` (`actions/runs/40814645637`). En local: `python -m unittest discover -s tools/tests`, `python tools/verificar_escenarios.py` (hoy `exigidos 0 · pendientes 162`) y `python tools/verificar_docs.py`. El ensayo con `HDU-001` activa, en un PR en borrador ya cerrado sin fusionar, puso el paso del verificador en rojo con `exigidos 27 · faltan 27` (`actions/runs/40812135088`).
>
> **Aviso a quien revisa.** No toca `docs/api/openapi.yaml`. La última reauditoría de documentación quedó en `REQUIERE CAMBIOS` por dos Menores aplicados sin una cuarta reauditoría; consta en `sdd/tickets/tkt-009c/impl.md`.
>
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)
