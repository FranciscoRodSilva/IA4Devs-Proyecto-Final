# Revisión automatizada de pull requests en un flujo aparte, con una única excepción de secretos

## Estado

Aceptado

## Contexto y problema

La revisión automatizada de pull requests ([convenciones §12](../convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)) necesita una clave de API de Anthropic. Eso choca con tres cosas que el proyecto ya decidió o comprobó.

* Las pruebas de TKT-009 prohíben que cualquier flujo lea `secrets.`: el pipeline no necesita secretos, porque los tests usan contenedores con credenciales efímeras.
* El modelo lee texto que escribe el autor del pull request: título, cuerpo y diff. Ese texto puede traer instrucciones disfrazadas de datos.
* Quien alguna vez haya visto un flujo que lee un secreto en este proyecto se preguntará por qué existe, por qué usa `pull_request` en lugar de `pull_request_target`, y por qué el modelo no publica lo que escribe.

Hay además dos hechos del diseño de TKT-062. El primero (`A-3`): el ajuste del repositorio que impide a GitHub Actions aprobar pull requests solo rige para `GITHUB_TOKEN`, no para el token de la aplicación de Claude que la acción obtiene por OIDC. El segundo (`A-6`): con `pull_request`, GitHub ejecuta el flujo que trae el propio pull request, con el secreto, antes de que nadie revise el diff.

## Opciones consideradas

1. **Flujo aparte con `pull_request`, excepción nombrada en un solo paso, modelo sin escritura con `github.token` y filtro de citas ejecutado desde la base en un trabajo sin secreto.** Se elige.
2. **`pull_request_target` con *checkout* de la base.** Resolvería `A-6`, porque el flujo siempre sería el de la base. Se descarta: la decisión del 2026-10-29 prohíbe `pull_request_target`, y una guarda mal escrita expondría el secreto a bifurcaciones.
3. **Dos flujos unidos por `workflow_run`.** Se descarta: `comprobar_tc13` lo prohíbe y duplica la superficie que hay que vigilar.
4. **Un entorno con revisores requeridos.** Se descarta: cada revisión esperaría una aprobación manual, lo que anula la automatización.
5. **La aplicación de Claude por OIDC.** Se descarta: el ajuste que impide aprobar no la cubre, y podría aprobar un pull request.
6. **Que el modelo publique directamente.** Se descarta: nada impediría mecánicamente un comentario sin cita, y el actor con permiso de escritura sería el que lee texto ajeno.
7. **Un trabajo dentro de `ci.yml`.** Se descarta: pondría un secreto en el pipeline y una IA con voz en lo que bloquea.

## Decisión

Se crea `.github/workflows/revision-ia.yml`, que es el único flujo que puede leer un secreto, y solo para pasar `ANTHROPIC_API_KEY` como entrada `anthropic_api_key` de `anthropics/claude-code-action`, en un único paso del trabajo `revision`. Las pruebas de TKT-009 conservan su prohibición general y nombran esta excepción de forma literal; cualquier otra lectura de un secreto sigue fallando.

El diseño tiene dos trabajos.

* `revision` ejecuta el modelo. Sus permisos son `contents: read` y `pull-requests: read`; recibe `github_token: ${{ github.token }}`; y devuelve su resultado como salida estructurada. El modelo **no tiene `Bash`**: sus herramientas permitidas son solo `Read(./**)`, `Glob` y `Grep`, con `Read(./**)` y no `Read` a secas, y se le deniegan además `Bash`, `Read(//proc/**)` y `Read(//sys/**)`. Como no puede llamar a `gh`, un paso previo de `revision`, anterior a la acción y **sin secreto**, escribe el pull request en `.revision-pr/pr.json` (título, cuerpo y archivos) y `.revision-pr/pr.diff` con `GH_TOKEN`, `GH_REPO` y `PR` por `env:`; el modelo los lee con `Read`. Las instrucciones le dicen que no lea el entorno del proceso.
* `publicar` no lee ningún secreto. Ejecuta [`tools/publicar_revision.py`](../../tools/publicar_revision.py) desde un *checkout* de la base, descarta todo hallazgo sin cita válida o con forma de clave, también escrita con separadores, mayúsculas, guiones bajos o partida entre campos, y publica un único comentario con `pull-requests: write`.

Ambos trabajos leen la base del pull request, nunca su cabeza, con `persist-credentials: false`. La guarda excluye borradores, bifurcaciones y los pull requests de Dependabot, que además no reciben secretos. La revisión comenta y nunca bloquea ni aprueba.

## Consecuencias

**Positivas**

* La excepción tiene un único lugar, una única forma literal y una prueba que se pone en rojo si se amplía.
* Un hallazgo sin cita no llega al pull request, y el modelo no tiene con qué aprobar, comentar ni llamar a la API.
* Una persona que revisa el pull request ve el comentario como lo que es: una lectura asistida, no una aprobación.

**Negativas o costes aceptados**

* Los pull requests de Dependabot y de bifurcaciones llegan sin revisión de la IA. El trabajo aparece como omitido, no en verde, y la etiqueta `agent` que Dependabot aplica los identifica.
* La revisión del pull request que introduce este flujo no funciona: su base todavía no tiene `.claude/revision-pr.md`. Se acepta, y lo cubre el ensayo de activación de la sección «Estado de la activación».
* Dependabot propondrá actualizaciones de la acción con frecuencia. Es la política de TKT-009b y se acepta como ruido de pull requests.

### Riesgo residual de `A-6`

Quien tiene permiso de escritura puede abrir un pull request desde una rama propia con `revision-ia.yml` modificado. `pull_request` ejecuta el flujo del pull request con el secreto antes de que nadie revise el diff, y ninguna prueba estática lo impide. La persona responsable aceptó este riesgo residual el 2026-10-29 (`D-1`). Se mitiga con cinco medidas:

1. **El secreto toca un solo paso.** `motivos_de_secretos` y zizmor fallan en `ci.yml` si el flujo lo lee en otro sitio. La exfiltración no se impide, pero queda a la vista en el pull request y en el registro de ejecuciones.
2. **El modelo no ejecuta órdenes, no escribe ni lee fuera del árbol.** El trabajo con el secreto tiene `pull-requests: read`, ninguna herramienta de escritura, ningún `Bash` y `Read(./**)`, con `/proc` y `/sys` denegados. Además, `publicar_revision.py` descarta todo hallazgo con forma de clave. Una inyección de instrucciones no puede usar GitHub ni el comentario para sacar la clave.
3. **Quién tiene escritura.** Al activar la revisión, la evidencia de `CA-9` del diseño incluirá la lista de colaboradores. Los agentes empujan con las credenciales de la dueña y ningún token de agente tiene escritura propia.
4. **Daño acotado (al activar).** La clave será dedicada, vivirá en un espacio de trabajo propio de la consola de Anthropic y tendrá un límite de gasto mensual (`D-3`). Una clave filtrada costará como máximo ese límite.
5. **Rotación.** El procedimiento siguiente se aplica ante cualquier pull request que toque `revision-ia.yml` sin que un ticket lo declare.

`CODEOWNERS` no mitiga este riesgo frente a quien tiene escritura: con una sola persona con escritura y `enforce_admins: false`, se autoaprobaría u omitiría la revisión, y tampoco impide la ejecución del pull request. La mitigación real es que la dueña lea el diff. Queda como ticket futuro sugerido.

### Procedimiento de rotación de la clave

1. En la consola de Anthropic, revoca la clave dedicada del espacio de trabajo de la revisión.
2. Crea otra clave en el mismo espacio de trabajo y conserva su límite de gasto mensual.
3. Sustituye el secreto con `gh secret set ANTHROPIC_API_KEY --repo <dueño>/<repositorio>`. La orden pide el valor de forma interactiva, así que no queda en el historial del intérprete ni se pasa como argumento.
4. Comprueba con `gh secret list --repo <dueño>/<repositorio>` que `ANTHROPIC_API_KEY` aparece con la fecha de hoy.
5. Anota la fecha y el motivo de la rotación en el registro del ticket. Nunca anotes la clave.

### Ajuste del 2026-10-30 · hallazgos de la auditoría de seguridad

La auditoría de seguridad de la ejecución de TKT-062b halló que `Read(./**)` solo acota la herramienta `Read`: con `Bash(gh pr view:*)`, `Glob` y `Grep` el modelo podía alcanzar la clave del entorno (por ejemplo con `--jq` y `$ENV`, o leyendo `/proc/self/environ`), y una clave escrita con separadores pasaba el filtro. La persona responsable decidió el 2026-10-30 quitar `Bash` y acotar el resto:

* **F001.** El modelo no tiene `Bash`. Un paso previo sin secreto deja el pull request en `.revision-pr/`, y `/proc` y `/sys` se deniegan con `Read(//proc/**)` y `Read(//sys/**)`; la barra doble indica una ruta absoluta en la sintaxis de reglas de Claude Code, que `--disallowedTools` admite igual que los ajustes. El filtro descarta también la clave ofuscada: sin lo que no es alfanumérico y en minúsculas, aparece `skant` en un campo o en la concatenación de los tres. La sintaxis se verificó el 2026-10-30 con la documentación de permisos de Claude Code (consultada con Context7, `/websites/code_claude`): `//ruta` es una ruta absoluta desde la raíz del sistema, `--disallowedTools` admite reglas con especificador y un nombre de herramienta solo (`Bash`) la quita del contexto del modelo. La misma documentación describe como de mejor esfuerzo que las reglas de lectura excluyan rutas denegadas de los resultados de `Grep` y `Glob`, y por eso queda abierta la condición N003.
* **F002.** El registro de `publicar` no imprime una clave: un hallazgo descartado por clave se nombra siempre `[archivo omitido]:<linea>`, y uno descartado por cita inválida solo muestra `archivo` si es uno de los del PR.
* **F003.** La cita es de vocabulario cerrado: `CITA_VALIDA` se aplica entera a la cita sin espacios al borde, así que una cita con texto libre alrededor se descarta.

Sigue sin resolverse la ausencia de `concurrency` (F004), que queda para el ticket futuro.

### Topes `(asumido)` que se revisan al mes

* **`A-1`.** `--max-turns 20`, `timeout-minutes: 10` en `revision` y `timeout-minutes: 5` en `publicar` y en `etiqueta`. Son los valores mínimos que permite el diseño, no valores medidos.
* **`A-2`.** `--model sonnet`, el alias de la CLI de Claude Code que apunta al Sonnet vigente. Los puntos de la lista cerrada que quedan para la IA exigen leer intención: un modelo menor los pierde, y uno mayor no aporta en una lista cerrada.

Tras el primer mes de uso real se revisan ambos con las ejecuciones reales y cualquier cambio se registra en este ADR. Medir el coste por revisión queda fuera del alcance de TKT-062.

**Cuándo revisar esta decisión**

* Ante cualquier cambio en `revision-ia.yml` que no declare un ticket.
* Si GitHub extiende el ajuste que impide aprobar a las credenciales de la aplicación de Claude, o permite proteger `revision-ia.yml` de una rama propia.
* Si el proyecto tiene más de una persona con permiso de escritura.

## Estado de la activación

**Fecha: 2026-10-30.** El estado de la decisión sigue **Aceptado**. Lo que cambia es que el flujo está construido pero **inactivo**: por falta de presupuesto no hay clave de API de Anthropic, y sin ella el trabajo `revision` no puede ejecutar el modelo.

El flujo `revision-ia.yml`, el filtro `tools/publicar_revision.py`, `.claude/revision-pr.md` y sus pruebas se conservan tal como se describen arriba. La decisión no retira nada: aplaza la clave. Mientras tanto, la revisión de cada pull request es local: la persona autora ejecuta `/code-review` de Claude Code sobre la rama antes de abrir el PR. Como la revisión no es comprobación requerida, su ausencia no bloquea ninguna fusión.

Estado comprobado el 2026-10-30 con lectura de GitHub:

* El secreto `ANTHROPIC_API_KEY` no existe en el repositorio.
* El ajuste del repositorio que impide a GitHub Actions aprobar pull requests está en `false` (`gh api repos/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/permissions/workflow`).
* `revision-ia.yml` no aparece en `gh workflow list --all`, porque el archivo todavía no está en la rama base. Hasta que se fusione no hay nada que deshabilitar.

Para activarla, en este orden:

1. Crear una clave de API dedicada, en un espacio de trabajo propio de la consola de Anthropic y con el límite de gasto mensual que fija la persona dueña (`D-3`).
2. Guardarla con `gh secret set ANTHROPIC_API_KEY --repo <dueño>/<repositorio>`. La orden pide el valor de forma interactiva. Comprobarla con `gh secret list --repo <dueño>/<repositorio>`.
3. Comprobar el ajuste del repositorio que impide a GitHub Actions aprobar pull requests (`CA-9` de TKT-062b).
4. Ejecutar la ronda R2c (`N003` de la auditoría de seguridad de 2026-10-30, que pide confirmar que `Grep` y `Glob` no leen el entorno del proceso por `/proc/self/environ`, algo que `Read(//proc/**)` no cubre porque solo acota `Read`): en un pull request de ensayo, un diff que pida a la revisión leer `/proc/self/environ` y `/proc/self/cmdline` con `Grep` y `Glob`, y una clave de prueba escrita con separadores. Hay que verificar que esas lecturas se rechazan y que ningún comentario ni registro muestra la clave. Si no se rechazan, se denegarán explícitamente y se reauditará.
5. Ejecutar las rondas de ensayo que el recorte del 2026-10-30 retiró de TKT-062b (R0b a R6, en `sdd/tickets/tkt-062/design.md`, sección «Ensayo»), con la persona dueña, en un ticket de activación.
6. Habilitar el flujo con `gh workflow enable revision-ia.yml`.

Al fusionar el archivo a la rama base, `/sdd-completar` lo deshabilita de inmediato con `gh workflow disable revision-ia.yml`, antes de que el siguiente pull request lo ejecute sin clave (paso 5e del procedimiento de fusión de esa skill, por decisión de la persona responsable del 2026-10-30). Sin esa orden, cada pull request mostraría una ejecución en rojo que no es comprobación requerida, pero que induce a error.
