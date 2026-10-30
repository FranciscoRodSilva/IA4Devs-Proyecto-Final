# Delta · TKT-062a · Etiqueta de origen obligatoria

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Flujo «Etiqueta de origen» | `.github/workflows/etiqueta-origen.yml` | Comprueba en cada pull request que hay exactamente una etiqueta de origen. Se dispara al abrir, reabrir, empujar, etiquetar y quitar una etiqueta, y no relanza `ci.yml` |
| Script de la comprobación | `tools/etiqueta_origen.py` | Cuenta las etiquetas de origen del evento. Devuelve 0 con una, 1 con ninguna o con más de una, y 2 ante una entrada inválida (falla cerrado) |
| Pruebas del script | `tools/tests/test_etiqueta_origen.py` | Rojo y verde del script, también ejecutado como proceso con `subprocess`, con mutantes que prueban que el control no falla abierto |
| Pruebas de la definición del flujo | `tools/tests/test_definicion_etiqueta.py` | Fijan disparadores, nombre del trabajo, permisos, checkout, entorno y la documentación de la etiqueta |
| Las cuatro etiquetas | Configuración de GitHub: `human`, `human+copilot`, `agent`, `agent+human-review` | Etiquetas de origen que la comprobación acepta |
| Protección de `Produccion` | Configuración de GitHub | Una aprobación requerida, diez comprobaciones requeridas y `enforce_admins: false` |
| ADR-027 | `docs/adr/20261030-proteccion-de-produccion-y-fusion-con-omision.md` y su entrada en `docs/adr/README.md` | Registra la protección y la fusión con omisión de la aprobación |
| Bloque «Fusión con omisión» | `sdd/plantillas/delta.md` y `.claude/skills/sdd-completar/SKILL.md` | Dice dónde se registra una fusión con omisión de la protección |
| Subsección «Partición en dos tickets hermanos» | `docs/05-tickets-trabajo.md` | Registra TKT-062a y TKT-062b como partes de TKT-062 |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Etiquetas de Dependabot | `.github/dependabot.yml` | Sin `labels:` → `labels: ["agent"]` en las cuatro entradas. Sustituye `dependencies` y la etiqueta del ecosistema |
| Reglas comunes de los flujos | `tools/tests/test_definicion_ci.py` | Solo se aplicaban a los trabajos de `ci.yml` → se aplican a todo flujo, con la guarda de la futura revisión por IA como única excepción nombrada |
| Etiquetas de Dependabot | `tools/tests/test_definicion_dependabot.py` | Toleraban `labels:` → exigen `["agent"]` y rechazan un valor escalar |
| Significado de la etiqueta de origen | `docs/convenciones.md` §11 | Se medía a mano en el cuerpo del PR y podía cambiar al revisar → es el origen del código, la comprueba un flujo y no cambia al aprobar |
| Cambios a `Produccion` | `docs/convenciones.md` §6 | Los cierres de ticket se empujaban directo → todo cambio entra por un pull request, por convención |
| Párrafo de la etiqueta | `CLAUDE.md` | «`agent` o `agent+human-review`» → las cuatro etiquetas y la comprobación requerida «Etiqueta de origen» |
| Conteo de decisiones | `CLAUDE.md`, `README.md`, `llms.txt` | 26 → 27 decisiones |
| Flujos de CI | `docs/06-stack-tecnologico.md` §10 | Todo vivía en `ci.yml` → también `enlaces.yml` y `etiqueta-origen.yml` |
| Orígenes del PR | `sdd/plantillas/delta.md`, `sdd-completar/SKILL.md`, `git-entrega.md`, `sdd/00-propuesta-toolkit.md` | Tres orígenes → los cuatro, con su significado |
| Guía de las herramientas | `tools/README.md` | Sin `etiqueta_origen.py` ni las suites de la etiqueta → sección de `etiqueta_origen.py` y descripción de `test_etiqueta_origen.py` y `test_definicion_etiqueta.py` |
| Criterios del ticket paraguas | `docs/05-tickets-trabajo.md` (TKT-062) | «No se puede fusionar» sin aprobación ni matices → el matiz de la administradora con `enforce_admins: false` y de las diez comprobaciones, y el criterio del token corregido |
| Pruebas de documentación | `sdd/tickets/tkt-009d/delta.md` | `«tablaroka»` en prosa → en código. Excepción de alcance autorizada: Vale lo marcaba y bloqueaba el trabajo de documentación de cualquier PR |

## Eliminado

Nada que existiera antes del ticket.

## Comportamiento observable nuevo

- Un pull request sin una etiqueta de origen, o con dos, deja la comprobación «Etiqueta de origen» en rojo y no pasa la protección de `Produccion`. El mensaje nombra las cuatro etiquetas válidas.
- Etiquetar o quitar una etiqueta vuelve a comprobar y no relanza el pipeline `ci.yml`.
- Los pull requests de Dependabot llegan con la etiqueta `agent`. Se observó en vivo con el PR #22, abierto un minuto después de la fusión.
- `Produccion` exige una aprobación y las diez comprobaciones. Con `enforce_admins: false`, la persona administradora puede fusionar con `--admin` y omitir solo la aprobación, y registra la fusión en un comentario del PR. Es una convención del proyecto, no un bloqueo técnico.
- Los cierres de ticket entran por un pull request y ya no por empuje directo a `Produccion`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Aplicación (endpoints, DTO, tipos generados, esquema) | Ninguno | No |
| Nombre de la comprobación requerida «Etiqueta de origen» | Es el contexto que exige la protección de `Produccion`; cambiar el `name:` del trabajo rompe la protección | Sí, si se renombra: lo impide TC62-06 |
| Etiquetas de los PR de Dependabot | `agent` sustituye a `dependencies` y a la del ecosistema | Sí, para quien filtrara por las etiquetas antiguas; ningún flujo ni documento lo hacía |
| PR anteriores de Dependabot | Los abiertos antes de la fusión (#9 y #11 a #16) conservan sus etiquetas antiguas | Sí: su comprobación quedará en rojo hasta que se les añada una etiqueta de origen |

## Decisiones (ADR)

### 2026-10-29 (registrada el 2026-10-30) — Protección de `Produccion` sin segunda persona y fusión con omisión

**Contexto:** el repositorio tiene una sola persona con escritura y GitHub no deja a quien abre un PR aprobarlo. Hacía falta una protección que exigiera una aprobación humana y las diez comprobaciones sin bloquear toda fusión.
**Opciones consideradas:** añadir una segunda persona con escritura que apruebe, `enforce_admins: false` con una aprobación requerida y fusión con omisión, y `enforce_admins: true` con una sola persona.
**Decisión:** `enforce_admins: false`, porque hoy no hay segunda persona. La aprobación humana es la revisión de comentario de la dueña y la omisión cubre solo esa aprobación, nunca una comprobación en rojo.
**Evidencia:** `design.md` D-2 y «Fusión con omisión de la protección», la salida de `gh api .../protection` en `impl.md` y la ronda R6 prevista en TKT-062b.
**Consecuencias:** no hay una segunda mirada independiente `(asumido)`, y la regla de que todo entra por PR es una convención. Se revisa cuando haya una segunda persona con escritura `(asumido)`.

→ [ADR-027](../../../docs/adr/20261030-proteccion-de-produccion-y-fusion-con-omision.md).

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| GitHub lee `dependabot.yml` solo de la rama por omisión, así que el efecto de `labels:` solo se observa tras fusionar | El PR #22 de Dependabot llegó con `agent` un minuto después de la fusión | Cualquier cambio de configuración de Dependabot |
| `labels:` en Dependabot sustituye las etiquetas por omisión, no las suma | PR #9 y #11 a #16 conservan `dependencies` y el ecosistema; #22 solo lleva `agent` | Informes por etiqueta de Dependabot |
| Un guion de CI debe probarse **como proceso**: sin eso sobreviven `sys.exit(main())` por `main()`, que falla abierto, y `os.environ` por `{}` | Mutantes M1 y M2 de la auditoría de código | Todo script de `tools/` que haga cumplir una compuerta |
| `python -I` ignora `PYTHONUTF8` y `PYTHONIOENCODING`: una prueba con tilde se rompe si el hijo y el padre decodifican distinto | Dos fallos reproducidos en Python 3.14 con `PYTHONUTF8=1` | Pruebas con `subprocess` en Windows; se fija con `-X utf8` y `encoding="utf-8"` |
| Con dos eventos de etiqueta casi simultáneos, dos ejecuciones sobre el mismo SHA pueden ver ambas etiquetas | Rondas R1: dos ejecuciones lanzadas a la vez, las dos rojas | Mientras `concurrency` sea un *Won't* |
| Los comandos con variables y *heredoc* del procedimiento son de Git Bash; en PowerShell `REPO=…` no define la variable | La primera ejecución de la persona dueña falló con «too many arguments» y 404 | Todo procedimiento de ajustes del repositorio |
| Las 2 supresiones de `zizmor` son avisos `concurrency-limits` de la persona *pedantic*, que el pipeline no usa | `zizmor --persona=pedantic` | Lectura de «2 suppressed» en futuros flujos |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | Los linters de documentación (Vale y markdownlint) solo se veían en el pipeline: el trabajo «Documentación» del PR de ensayo falló por tres hallazgos que nadie había visto en local. Los dos corren con `uvx` y `npx` con los mismos comandos del pipeline; basta que `/sdd-ejecutar` los ejecute en el paso de documentación | Media |
| `comando` | La partición decidida en el gate dejó la ronda de ensayo A6 dependiendo de un flujo de la parte b; el auditor de preparación lo detectó y hubo que repartir el ensayo por partes. Un diseño que se parte debe repartir también sus ensayos y sus ramas de ensayo | Media |
| `agente` | Los agentes sin terminal (`arquitecto-tecnico`) dejaron la verificación sin ejecutar y rellenaron tablas de hallazgos con texto genérico («Observaciones sin bloqueo»), que luego hubo que reescribir con los datos reales. Es otra vez el mismo patrón de agente sin terminal que afirma sin ejecutar, ya anotado en tickets anteriores | Alta |
| `convención` | Un ADR redactado por un agente atribuyó a la persona que decidió alternativas que nadie documentó (la cuenta bot y «recomendaba el diseño»), y `auditor-docs` lo marcó Mayor (F401) en dos pasadas seguidas. Regla propuesta: cada opción, factor y consecuencia de un ADR consta en una fuente o lleva `(asumido)` | Alta |
| `guardrail` | Una mutación sobre el árbol por el tester, en paralelo con una auditoría, dejó el flujo «modificado» un instante (F007). Las mutaciones se hacen sobre una copia, nunca sobre el árbol cuando hay otro agente leyéndolo | Media |
| `agente` | `git-entrega` ignoró la atribución pedida en la instrucción explícita y puso la de su propio modelo en tres commits; el orquestador tuvo que hacer los siguientes a mano | Media |
| `plantilla` | La estimación del diseño dijo unas 490 líneas, con 320 de pruebas, y el resultado fueron unas 2,200 con unas 1,700 de pruebas. Es otra vez el patrón ya anotado: el tamaño de las pruebas de un verificador desborda la estimación | Media |
| `agente` | Una corrección del orquestador para F003 («salvo la administradora, solo con las diez comprobaciones en verde») introdujo una excepción imposible (F008). Las instrucciones aproximadas al corrector producen hallazgos nuevos en la reauditoría | Media |
| `convención` | Los cierres de ticket se empujaban directo a `Produccion` y se saltaron la CI: el de TKT-009d dejó un fallo de Vale que bloqueó la siguiente ronda de documentación. Resuelto por la regla «todo entra por PR» | Media |
| `comando` | Los procedimientos para la persona dueña no dicen en qué intérprete se ejecutan cada uno; en PowerShell fallaron todos. Conviene que cada bloque indique «Git Bash» y defina `REPO` en la primera línea | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| PR de Dependabot #9 y #11 a #16 abiertos antes de la fusión, con `dependencies` y el ecosistema pero sin etiqueta de origen: su comprobación fallará cuando se sincronicen | La etiqueta `agent` no puede añadirse sola a PR anteriores; es un gesto manual de la persona dueña | Ninguno: añadir `agent` a cada uno, o cerrarlos y dejar que Dependabot los rehaga |
| Comentario de registro de la fusión del PR #21 con el marcador «enlace al comentario de revisión» sin la URL | Se redactó con el texto del procedimiento | Editar el comentario con la URL real, o dejarlo como evidencia de la primera fusión con omisión |
| `concurrency` en `etiqueta-origen.yml` y `ci.yml` | *Won't* de la spec | Ticket de endurecimiento del pipeline |
| Un PR puede alterar `tools/etiqueta_origen.py` para pasar la comprobación | La mitigación real es la lectura del diff por la dueña; `CODEOWNERS` no aporta nada con una sola persona con escritura | Ninguno mientras haya una sola persona con escritura |
| `sha_pinning_required` en `false` y `allowed_actions: all` | Ajustes de repositorio fuera del alcance | Ticket de endurecimiento de los ajustes del repositorio |
| 2 vulnerabilidades de severidad baja que GitHub avisa en `Produccion` | Ajenas al ticket | Revisar en Dependabot |

## Pull request

**Título:** `TKT-062a · Cierre: delta, archivo del ticket y registro de evolución`
**Origen:** `agent`. Es el origen del código, es decir, quién lo escribió, no el estado de la revisión: lo fija quien abre el PR y no cambia al aprobar.
**Cuerpo:** qué (el `delta.md`, el archivo del ticket y las observaciones de proceso), por qué (el cierre de un ticket viaja dentro de un pull request y no se empuja a `Produccion`), criterios cubiertos (los de TKT-062a, ya fusionados en el PR #21) y cómo verificarlo (`python tools/verificar_docs.py`).

**Fusión con omisión:** este PR solo cambia documentación. Si se fusiona con omisión de la protección de `Produccion`, el registro no va en este archivo, porque `delta.md` se escribe antes de fusionar. Va en un comentario del PR que la persona dueña deja justo después de `gh pr merge --admin`, con la frase «fusionado con omisión de la protección», la fecha, el número del PR, la etiqueta de origen, el enlace a su revisión en el PR y el enlace a la ejecución con las diez comprobaciones requeridas en verde.
