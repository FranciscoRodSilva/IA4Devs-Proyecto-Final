# Delta · TKT-009d · Calidad de documentación

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Configuración de `markdownlint-cli2` | `.markdownlint-cli2.jsonc` | Fijar el alcance y las reglas de Markdown. Ninguna regla está apagada |
| Configuración de `Vale` con estilo propio mínimo | `.vale.ini`, `.vale/styles/Cimenta/Vocabulario.yml` y `.vale/styles/config/vocabularies/Cimenta/accept.txt` | Detectar errores de vocabulario del glosario (por ejemplo «tablaroka» por «tablaroca») y aceptar sus términos propios sin falsos errores |
| Configuración de `lychee` | `lychee.toml` | Comprobar enlaces internos y externos. Las anclas las sigue comprobando `verificar_docs.py`; se excluyen `cimenta.test` y `medium.com` |
| Configuración de `mermaid-cli` | `.github/puppeteer-config.json`, `.github/mermaid/package.json` y `.github/mermaid/package-lock.json` | Validar la sintaxis de los diagramas en el corredor, con la versión 12.0.0 fijada por lockfile |
| Pasos de calidad documental en el trabajo `documentacion` | `.github/workflows/ci.yml` | Ejecutar en cada pull request, en orden y cada uno con `if: ${{ !cancelled() }}`, `verificar_docs.py`, `markdownlint-cli2`, `Vale`, `lychee` y `mermaid-cli`. Un fallo pone en rojo el paso con archivo y línea |
| Detector semanal de enlaces | `.github/workflows/enlaces.yml` | Repetir la comprobación de enlaces cada lunes (`0 13 * * 1`) y a demanda con `workflow_dispatch`, para cazar enlaces externos que se rompen con el tiempo |
| Pruebas de la definición del flujo documental | `tools/tests/test_definicion_documentacion.py` | Fijar TC-64 y TC-65 sobre `ci.yml` y `enlaces.yml`, con clases `PruebasDeMutantes…` que comprueban que cada mutante es detectado. TC-62, TC-63, TC-66 y TC-68 se verifican en el ensayo del pipeline |
| ADR de `Vale` para prosa en español | `docs/adr/20261029-vale-para-prosa-en-espanol.md` | Registrar la decisión con sus opciones descartadas (ver «Decisiones») |
| Auditoría del lock de `mermaid-cli` y cuarta entrada de Dependabot | trabajo `dependencias` de `ci.yml` y `.github/dependabot.yml` | Que el único árbol de dependencias que no pasaba por ninguna auditoría quede vigilado (hallazgo `R-SEG-F001` de la revisión) |
| Sección «Calidad de la documentación en local» | `docs/arranque-local.md` | Los comandos para reproducir en local cada paso del pipeline documental |
| Sección «Herramientas documentales de terceros» | `tools/README.md` | La tabla de versiones fijadas y dónde corre cada herramienta |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Línea base documental | 119 archivos de `docs/` y `sdd/`, `README.md`, `CLAUDE.md` y `tools/README.md` | 586 hallazgos de `markdownlint-cli2`, 20 alertas de `Vale` y 1 enlace roto → cero en las tres herramientas. Se limpió en este ticket por decisión de la persona que aprueba, en tres commits: formato automático (`47a0500`), `markdownlint` a mano (`b6d8f34`) y `Vale` y `lychee` (`9a9f8b4`) |
| Bloques de código sin idioma y citas partidas | `docs/` y `sdd/` | 106 bloques sin idioma pasan a llevar `text` (uno `diff`), 29 citas separadas por una línea en blanco se unen y los 16 encabezados de primer nivel de `docs/05-tickets-trabajo.md` pasan a segundo nivel, sin cambiar su texto ni sus anclas |
| Pasos de escenario con nombres literales | `docs/04-historias-usuario.md` (líneas 503, 1330 y 1589) | El nombre de la partida en mayúsculas pasa a código en línea. Los títulos `**Escenario N:` no cambian: siguen siendo 162 |
| Recuento de decisiones | `CLAUDE.md`, `README.md` y `llms.txt` | 25 → 26 ADR |
| Convenciones de documentación | `docs/convenciones.md` §10 y `.claude/skills/conv-documentacion/SKILL.md` | La fila de prosa y la de diagramas describen el estilo del proyecto y `@mermaid-js/mermaid-cli` en CI, en lugar de herramientas «previstas» |
| Stack | `docs/06-stack-tecnologico.md` §6.4, §9 y §10 | §9: versiones fijadas de las cuatro herramientas y dónde corren. §10: trabajo `documentacion`, detector semanal, nivel de aviso en local y de error en CI. §6.4: lock de `mermaid-cli` y cuatro ecosistemas de Dependabot. §8: `interrogate` figura como previsto |
| Diseño común de TKT-009 | `sdd/tickets/tkt-009/design.md` | Filas D1 a D5 y D7 en `✓ Hecho`, la sección «Ajustes registrados al ejecutar la parte d» y las cuatro entradas de Dependabot |
| Índice de ADR | `docs/adr/README.md` y `docs/05-tickets-trabajo.md` | Entrada del ADR de `Vale` y una línea de enlace en la ficha de TKT-009 |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Símbolo de dólar y espacio previos a los comandos de los bloques de código | `docs/` y `sdd/` (regla MD014) | Es formato: el comando no cambia y la regla lo exige para poder copiarlo |
| Mención de `mermaid-cli` como sustitución futura | `tools/README.md` | Ya corre en el pipeline |

## Comportamiento observable nuevo

- Un pull request que introduzca un enlace interno o externo roto, un bloque de código sin idioma, una errata del vocabulario del glosario o un diagrama de Mermaid inválido falla el trabajo `Documentación`, y el paso en rojo imprime el archivo y la línea. En el ensayo, las cinco violaciones pusieron en rojo sus cinco pasos y el revert los dejó en verde.
- En local, `Vale` solo avisa; en CI, el mismo hallazgo es un error. La línea base queda en cero, así que cualquier alerta nueva viene del cambio.
- Cada lunes, `enlaces.yml` vuelve a comprobar los enlaces externos aunque nadie abra un PR. La primera ejecución manual (`gh workflow run enlaces.yml`, [40943983006](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40943983006)) terminó en `success` sobre `6fb4cb6`.
- Un artículo de Medium citado en la documentación no se comprueba, porque Medium responde `403` a los corredores de GitHub.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoint, DTO, tipo generado o esquema | Ninguno | No |
| Pipeline de pull request | El trabajo `documentacion` añade cuatro pasos y puede fallar por motivos nuevos | No para el código; sí para quien abra un PR con documentación sucia, que es lo que se busca |
| Títulos de escenario | Ninguno cambia; `verificar_docs.py` sigue contando 162 | No |
| Regla de `verificar_docs.py` sobre encabezados de ticket | Sin cambio, pero la bajada de los H1 de `docs/05` a H2 deja algunos encabezados hijos como hermanos de su sección (ver «Deuda») | No |

## Decisiones (ADR)

### 2026-10-29 — `Vale` con estilo propio mínimo para prosa en español

**Contexto:** `Vale` nunca se había ejecutado sobre unas 37,000 líneas de Markdown en español, y su estilo estándar es en inglés.
**Opciones consideradas:** el estilo Microsoft, la ortografía española con Hunspell y no usar `Vale`.
**Decisión:** un estilo propio mínimo con el vocabulario del glosario y la detección de repeticiones. El estilo Microsoft está escrito para el inglés y marcaría casi cada frase; Hunspell marcaría cada término técnico tomado del inglés (*pipeline*, *endpoint*); con solo `markdownlint-cli2` no habría compuerta sobre la terminología ni la repetición.
**Evidencia:** TC-60 y TC-61 (ejecuciones locales sobre «tablaroka» y los términos del glosario) y la ronda 1 del ensayo, donde `Vale` marca `Cimenta.Vocabulario` en `docs/convenciones.md:400`.
**Consecuencias:** el paquete `vale` de PyPI descarga el binario oficial sin hash en la primera ejecución, y `npx` resuelve las dependencias transitivas de `markdownlint-cli2` sin lockfile. Ambos son costes aceptados `(asumido)` de prioridad baja.

→ Creado: [`docs/adr/20261029-vale-para-prosa-en-espanol.md`](../../../docs/adr/20261029-vale-para-prosa-en-espanol.md), con su entrada en el índice. Es la decisión 26.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `lychee` excluye por omisión los dominios reservados `.invalid`, así que un enlace roto de ensayo en ese dominio nunca pondría el paso en rojo. Hay que usar una página real que dé 404 | Comprobado: «Excluded 1» y cero errores | Cualquier ensayo de una compuerta de enlaces |
| Medium responde `403` a las IP de los corredores de GitHub y `200` desde una máquina de la persona: un enlace sano puede romper el pipeline. Se excluye de forma explícita en lugar de aceptar el `403`, que taparía enlaces rotos reales | Ejecución 40936972466 (rojo) y 40938042934 (verde con la exclusión) | `lychee.toml` y cualquier comprobador de enlaces externos |
| `lychee 0.24.2` rechaza `include_fragments = false`; el valor es una cadena (`none`, `anchor-only`, `text-only`, `full`) | Error «wanted string or table» | `lychee.toml` |
| `zizmor` marca `npm install` de un paquete fuera de un lockfile (`adhoc-packages`); instalar la herramienta con `npm ci` sobre un lock dedicado mantiene la compuerta de seguridad sin supresiones | Ajuste de la fila D5 | Toda herramienta de Node que se instale en el pipeline |
| El primer ensayo de una compuerta nueva descubre violaciones que el diseño no previó: aquí, una de `markdownlint` (MD040) entró en el ensayo y no tenía caso de prueba | Ronda 1 del PR #18 | Ensayo de compuertas de TKT futuros |
| `--fix` de `markdownlint-cli2` cambió 33 archivos sin tocar ninguna línea `**Escenario`, y `verificar_docs.py` dio los mismos conteos antes y después. Separar el commit de formato del manual lo hizo demostrable | `47a0500` y el diff vacío sobre las líneas de título | Toda limpieza masiva de documentación |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | De nuevo cada ciclo de corrección produjo Menores nuevos sobre el texto del ciclo anterior (tres ciclos, cuatro auditores) y los auditores sin memoria no reclasifican sin que se les repita el historial. Octava vez que aparece | Alta |
| `guardrail` | La mutación enumerada en el diseño y la hecha en `/sdd-ejecutar` dejaron 10 mutantes de flujo vivos en el paso de `mmdc` y el de `Vale`, (`R-COD-F001`, Mayor de la reauditoría del ciclo 2 de `/sdd-revisar`). La revisión volvió a encontrar lo que la mutación enumerada no vio | Media |
| `plantilla` | El diseño común estimaba unas 225 líneas para la parte d. El ticket toca 67 archivos con miles de líneas insertadas (sobre todo la limpieza de la línea base y las pruebas de la definición del flujo): la limpieza de la línea base y las pruebas de la definición del flujo no entran en la estimación. Cuarto ticket de `tools/` o de CI que lo repite | Media |
| `comando` | La medición de la línea base (D2) dio 183 hallazgos contra el umbral de 120 y el ticket se detuvo en `REQUIERE DECISIÓN`. El mecanismo funcionó, pero el umbral de 120 era una cifra supuesta (`A-5`) y no un cálculo; una medición previa en `/sdd-disenar` habría evitado la parada | Media |
| `herramienta` | Cuatro reglas de `markdownlint` (MD040, MD028, MD025 y MD001) y los falsos positivos de `Vale` sobre nombres literales exigieron decisiones por caso que `--fix` no toma. Costó 164 cambios manuales de `markdownlint` en 24 archivos, más 26 alertas de `Vale` resueltas a mano | Baja |
| `convención` | `ruff format` sigue fallando en archivos de `tools/` que ya estaban sin formatear y el pipeline no ejecuta `ruff` sobre `tools/`. Tercer ticket que lo señala (TKT-009a, TKT-009c y este) | Media |
| `comando` | El trabajo apilado y la rama de cierre: el PR de revisión (#19) se fusionó antes de que `/sdd-revisar` diera su veredicto, y el cierre se hace en una rama nueva. Ningún comando describe ese orden | Media |
| `modelo` | Ninguna fila de `haiku` subió a `sonnet` por no cerrar. El rojo de D5 fue a `tester-backend` en `sonnet`, por la convención de TDD, y la limpieza (D3 y D4) fue entera en `haiku` | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `tools/verificar_docs.py` exige que los encabezados de ticket sean H3; la bajada de los H1 de `docs/05` a H2 dejó algunos encabezados hijos como hermanos de su sección | Cambiar la regla del verificador es una decisión aparte, no una limpieza | Ticket futuro: decidir si el verificador acepta H2, o rehacer la jerarquía de `docs/05` |
| El aviso de requisitos huérfanos de `verificar_docs.py` sigue siendo aviso | Won't de la spec | Convertirlo en error cuando la línea base de requisitos esté limpia |
| `npx --yes markdownlint-cli2@0.24.0` resuelve dependencias transitivas sin lockfile; el paquete `vale` de PyPI descarga el binario sin hash | Coste aceptado en el ADR, prioridad baja | Fijar `markdownlint-cli2` con un lock dedicado como el de `mermaid-cli`, y `Vale` por SHA del asset |
| Dos avisos `low` de `katex` sin arreglo compatible en el lock de `mermaid-cli` | `npm audit --audit-level=high` los admite | Revisar cuando `mermaid-cli` suba de versión |
| `lychee.toml`: `exclude_path` toma expresiones regulares y el punto de `.venv` es un comodín | Riesgo bajo | Escapar el punto en la próxima edición de `lychee.toml` |
| `--no-sandbox` de Chromium en `.github/puppeteer-config.json` | Decisión del diseño para el corredor; el contenido es el repositorio propio | Reevaluar si `mermaid-cli` empieza a procesar contenido ajeno |
| `ruff format` falla en archivos de `tools/` y `ruff` no corre sobre `tools/` en el pipeline | Fuera del alcance | Ticket de calidad de `tools/` (ya sugerido por TKT-009a y TKT-009c) |
| Pipeline sobre el último commit | CI verificado sobre `18dce53` (PR #19); los commits posteriores solo tocan documentación del ticket | — |
| Los hallazgos de código, arquitectura y documentación del ciclo 2 de `/sdd-revisar` se aplicaron sin una reauditoría formal | Los tres ciclos estaban agotados; la persona que aprueba aceptó la excepción el 2026-10-29, como en TKT-009a, TKT-009b y TKT-009c | La revisión de la persona que abra el PR |

## Pull request

**Título:** `TKT-009d · Calidad de documentación`
**Origen:** `agent` (pasa a `agent+human-review` cuando una persona lo revise)
**Base:** `Produccion`. Las partes que contienen el trabajo, el PR [#17](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/17) y el de correcciones [#19](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/19), ya están fusionadas; este PR de cierre contiene el delta, el archivo del ticket y el registro de evolución.
**Cuerpo:**

> **Qué.** Cierra TKT-009d, la cuarta y última parte de TKT-009. El pipeline de pull request ejecuta ahora `markdownlint-cli2`, `Vale` con el vocabulario del glosario, `lychee` y `mermaid-cli` además de `verificar_docs.py`, y un detector semanal de enlaces (`enlaces.yml`) repite la comprobación cada lunes. La línea base documental (586 hallazgos de formato, 20 alertas de prosa y un enlace roto) quedó en cero sin apagar ninguna regla y sin cambiar un solo título de escenario. Este PR añade el delta, archiva el ticket y anota las observaciones de proceso.
>
> **Por qué.** Hasta ahora la documentación del repositorio, unas 37,000 líneas, solo pasaba `verificar_docs.py`. Un enlace roto, un bloque sin idioma, una errata del vocabulario de obra o un diagrama inválido llegaban a `Produccion` sin que nada los marcara. Es la parte final de TKT-009 (a → c → b → d).
>
> **Criterios cubiertos.** `CA-13`, `CA-14`, `CA-16`, `CA-R4` y la parte de `CA-15` de esta parte.
>
> **Cómo verificarlo.** El PR #19 pasó los nueve trabajos en verde sobre `18dce53` ([ejecución 40958703474](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40958703474)). El ensayo de compuertas ([PR #18](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/18), cerrado sin fusionar) puso en rojo los cinco pasos con una violación cada uno y el revert los dejó en verde. En local: `python tools/verificar_docs.py`, `python -m unittest discover -s tools/tests` (341 pruebas) y, según `docs/arranque-local.md`, `npx markdownlint-cli2@0.24.0` y `uvx --from vale==3.25.1.0 vale`.
>
> **Aviso a quien revisa.** No toca `docs/api/openapi.yaml` ni el esquema. Los hallazgos de código, arquitectura y documentación del ciclo 2 de la revisión se aplicaron sin reauditoría formal tras agotar los tres ciclos; la persona que aprueba aceptó la excepción el 2026-10-29. Seguridad dio `APROBADO` en el ciclo 1. El detalle consta en `sdd/tickets/tkt-009d/impl.md`.
>
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)
