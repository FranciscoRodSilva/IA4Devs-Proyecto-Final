# Impl · TKT-009d · Calidad de documentación

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: [delta](delta.md)

## Qué se implementó

Las filas D1 a D5 y D7 de la parte d del [diseño común](../tkt-009/design.md#parte-d--calidad-documental). La línea base documental, que superaba el umbral de 120 hallazgos de `A-5` (183), se limpió en este ticket por decisión de la persona que aprueba: `markdownlint-cli2`, `Vale` y `lychee` dan cero sobre el alcance. El trabajo `documentacion` de `ci.yml` ejecuta ahora el verificador propio, `markdownlint-cli2`, `Vale` con el vocabulario del glosario, `lychee` y `mermaid-cli`, y `enlaces.yml` repite la comprobación de enlaces cada lunes. El ADR de `Vale` para prosa en español y la documentación afectada cierran la fila D7.

**La fila D6**, el ensayo en el pipeline, la ejecutó la persona usuaria con dos PR en borrador: la ronda 1 puso en rojo cinco pasos (cuatro previstos y el de `markdownlint`, añadido en el ensayo) y la limpieza dejó todo en verde (ver «Fila D6»).

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-29 | `lychee.toml` lleva `include_fragments = "none"` en lugar de `false` | `lychee 0.24.2`, la última versión estable, rechaza el booleano («wanted string or table»); sus valores son `none`, `anchor-only`, `text-only` y `full`. `"none"` conserva la decisión del diseño: las anclas las comprueba `verificar_docs.py` |
| 2026-10-29 | `mermaid-cli` 12.0.0 se instala con `npm ci` sobre `.github/mermaid/package.json` y `package-lock.json`, no con `npm install --no-save` | `zizmor` marca `adhoc-packages` (instalar un paquete fuera de un lockfile) y el diseño exige `zizmor` sin hallazgos; la supresión en línea rebajaría una compuerta de seguridad. El lock se generó con `npm install --package-lock-only --ignore-scripts` para no descargar Chromium en local |
| 2026-10-29 | `enlaces.yml` declara `concurrency: { group: enlaces, cancel-in-progress: false }` | `zizmor` en perfil pedante marca `concurrency-limits`; con el bloque, las supresiones vuelven a una |
| 2026-10-29 | El enlace externo roto del ensayo es una página de GitHub que da 404, no `https://cimenta-ensayo.invalid/` | `lychee` excluye por defecto los dominios reservados `.invalid` (comprobado: «Excluded 1» y cero errores), así que esa violación nunca habría puesto el trabajo en rojo |
| 2026-10-29 | `lychee.toml` excluye `^https://medium\.com/` además de `cimenta\.test` | El primer PR (ejecución 40936972466, `ca1e9ab`) dejó en rojo solo `lychee`: un artículo de Medium citado en `sdd/00-propuesta-toolkit.md:456` responde `403` al corredor de GitHub y `200` desde una máquina de la persona usuaria, porque Medium bloquea las IP de los corredores. El diseño prevé ampliar `exclude` en el PR que lo necesita (objeción 2 de la pasada adversarial); se prefiere a aceptar el `403`, que taparía enlaces rotos reales |
| 2026-10-29 | Se añaden `lycheeVersion: v0.24.2` explícito en la acción y `if: ${{ !cancelled() }}` también en `setup-node`, `setup-uv` y la instalación de `mermaid-cli` | Regla común 3 (el valor por omisión de la acción puede cambiar) y regla común 6 (un `setup-uv` omitido taparía el hallazgo de `Vale` con «command not found») |
| 2026-10-29 | La salida de `mmdc` va a `$RUNNER_TEMP/mermaid/$n.md`, con `n` el número de orden del archivo, y no a `<archivo aplanado>.md` | Evita construir un nombre de archivo a partir de una ruta; no cambia lo que se valida (observación O1 de la auditoría de arquitectura) |
| 2026-10-29 | Las pruebas de D5 viven en un archivo nuevo, `tools/tests/test_definicion_documentacion.py`, y no en `tools/tests/test_definicion_ci.py` | El archivo de las partes a y b ya pasa de 3100 líneas y un archivo por tema es más legible (asumido) |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `.markdownlint-cli2.jsonc` | nuevo | configuración de documentación |
| `.vale.ini` | nuevo | configuración de documentación |
| `.vale/styles/config/vocabularies/Cimenta/accept.txt` | nuevo | configuración de documentación |
| `.vale/styles/Cimenta/Vocabulario.yml` | nuevo | configuración de documentación |
| `lychee.toml` | nuevo | configuración de documentación |
| `.github/puppeteer-config.json` | nuevo | configuración de documentación |
| `.github/mermaid/package.json`, `.github/mermaid/package-lock.json` | nuevo | configuración de documentación |
| `.github/workflows/ci.yml` | modificado (trabajo `documentacion`) | entrega continua |
| `.github/workflows/enlaces.yml` | nuevo | entrega continua |
| `tools/tests/test_definicion_documentacion.py` | nuevo | pruebas |
| 33 documentos de `docs/` y `sdd/` (D3), 24 más (D4 de `markdownlint`) y 11 más (D4 de `Vale`) | modificado | documentación (solo formato y términos marcados) |
| `docs/adr/20261029-vale-para-prosa-en-espanol.md` y `docs/adr/README.md` | nuevo, modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt`, `docs/convenciones.md` §10, `docs/06-stack-tecnologico.md` §9 y §10, `docs/arranque-local.md`, `docs/05-tickets-trabajo.md`, `tools/README.md`, `.claude/skills/conv-documentacion/SKILL.md`, `sdd/tickets/tkt-009/design.md` | modificado | documentación |

## Pruebas

D1 y D2 no tienen pruebas de `unittest`: sus casos (TC-60 y TC-61) son ejecuciones locales de `Vale`. Las pruebas estáticas del flujo (TC-64 y TC-65) llegan con D5.

### Ciclo por fila

#### Fila D1 · configuración de las herramientas

**Rojo.** Dos formas de probar que `Vale` no avisa sin la configuración del proyecto, sobre un `prueba.md` con «`tablaroka`»:

```text
sin .vale.ini:
[.vale.ini not found]:E100:no config file found
EXIT=2

con un .vale.ini mínimo (solo el estilo Vale, sin Cimenta):
(sin salida)
EXIT=0
```

**Verde.** Con la configuración del repositorio:

```text
prueba.md:3:4:Cimenta.Vocabulario:Usa 'tablaroca' en lugar de 'tablaroka' (glosario).
EXIT=0
```

Un `.md` con los términos del glosario (tablaroca, destajo, perfacinta, antepecho, cajillo, plafón, plafones, redimix, CIMENTA) da cero alertas y `EXIT=0`; «plafones» no da falso positivo con la sustitución de `plafon`. `vale ls-config` termina en 0. `markdownlint-cli2@0.24.0` lee `.markdownlint-cli2.jsonc` sin error. `python tools/verificar_docs.py` → `✓ Sin problemas.`

**Versiones fijadas para D5.** `markdownlint-cli2` 0.24.0 (`latest` de npm), `Vale` 3.25.1 (release oficial de `errata-ai/vale` del 2026-10-22; en local se ejecuta con el envoltorio de PyPI `vale==3.25.1.0`, que descarga el binario oficial `vale_3.25.1_Windows_64-bit.zip`, 13,359,702 bytes, en la primera ejecución), `lychee` 0.24.2 y `@mermaid-js/mermaid-cli` 12.0.0.

**`lychee` descargado con permiso.** La persona usuaria autorizó descargar el binario oficial `lychee-x86_64-pc-windows-msvc.zip` de `github.com/lycheeverse/lychee/releases` (v0.24.2, 6,868,524 bytes) a una carpeta del directorio temporal de la sesión. Su SHA256 coincide con el publicado (`32975d14…acfacad`). No se instaló en el sistema ni entra al repositorio.

**Refactor:** sin refactor.

#### Fila D2 · medición de la línea base (sin editar)

Alcance: 119 archivos (`docs/**/*.md`, `sdd/**/*.md`, `README.md`, `CLAUDE.md` y `tools/README.md`). Ninguna regla se apagó y ningún documento se editó. La corrección automática se probó solo en una copia desechable.

| Concepto | Valor |
|---|---|
| Hallazgos de `markdownlint-cli2`, línea base | **586** en 46 archivos (`docs/` 409, `sdd/` 173, raíz 2, `tools/README.md` 2) |
| Los que `--fix` corrige | 424 (MD032 265, MD022 57, MD004 38, MD038 30, MD014 15, MD029 13, MD012 4, MD034 2) |
| **Los que `--fix` no corrige** | **162** en 23 archivos (MD040 104, MD028 29, MD025 16, MD001 13) |
| Alertas de `Vale` | **20** (`Vale.Terms` 10, `Vale.Repetition` 5, `Cimenta.Vocabulario` 5) |
| Enlaces rotos de `lychee` | **1** de 1333 (337 únicos): el texto `«Ana@Cimenta.TEST»` de `sdd/tickets/tkt-006/impl.md` se interpreta como una ruta |
| **Suma que fija el umbral de `A-5`** | 162 + 20 + 1 = **183, mayor que 120** |

**Reglas de `markdownlint-cli2` por cantidad:** MD032 265, MD040 104, MD022 57, MD004 38, MD038 30, MD028 29, MD025 16, MD014 15, MD029 13, MD001 13, MD012 4, MD034 2. Los archivos con más hallazgos son `docs/04-historias-usuario.md` (168), `docs/05-tickets-trabajo.md` (127), `docs/glosario.md` (46) y `sdd/tickets/tkt-006/impl.md` (45).

**Lo que `--fix` no puede decidir.** MD040 (104) exige poner el idioma de cada bloque de código; MD028 (29), citas separadas por una línea en blanco; MD025 (16), varios encabezados de primer nivel; MD001 (13), saltos de nivel de encabezado. Necesitan una decisión por caso, no una regla.

**Efecto de `--fix` en una copia:** 33 archivos, +415 y −97 líneas; `docs/04-historias-usuario.md` queda en +165 y −3, todas líneas en blanco alrededor de listas y bloques. Las 162 líneas `**Escenario N: …` son idénticas antes y después, y `verificar_docs.py` sobre la copia da la misma salida completa (162 escenarios, sin problemas).

**`Vale.Repetition`:** 5 alertas y **ninguna es de celdas contiguas de tabla**, así que el diseño no permite apagar la regla. Cuatro son repeticiones reales en prosa («del del proceso») en `docs/02-arquitectura.md:357`, `sdd/tickets/tkt-004/delta.md:11`, `sdd/tickets/tkt-004/design.md:706` y `sdd/tickets/tkt-004/impl.md:9`. La quinta, `sdd/tickets/tkt-003/design.md:484`, es un falso positivo de contenido (la «A» repetida dentro de una celda).

**`Cimenta.Vocabulario`:** las 5 alertas están en `sdd/tickets/tkt-009/design.md` (líneas 292, 294, 319, 382 y 384) y citan «`tablaroka`» a propósito, como ejemplo del error que la regla detecta. Hay que decidir antes de D4 cómo escribirlas (entre comillas de código, p. ej.) sin apagar la regla.

**`Vale.Terms`:** 10 alertas por mayúsculas («`PLAFONES`», «`CAJILLOS`» en `docs/01-descripcion-producto.md` y `docs/04-historias-usuario.md`) y por «`cimenta`» en minúscula en `sdd/tickets/tkt-003/design.md` y «`Cimenta`» con inicial mayúscula en `sdd/tickets/tkt-006/impl.md`.

**Decisión tomada.** El umbral de `A-5` está superado (183 contra 120). La persona que aprueba decidió seguir en este ticket (ver `_index.md`, log del 2026-10-29); la limpieza se hizo en D3 y D4.

#### Fila D3 · limpieza automática

`npx markdownlint-cli2@0.24.0 --fix` sobre el alcance, en un commit que solo contiene formato (`47a0500`): 33 archivos, 415 inserciones y 97 eliminaciones. `verificar_docs.py` da los mismos conteos (162 escenarios, 601 anclas, 79 story points), `git diff -U0 -- docs/04-historias-usuario.md` no muestra ninguna línea `**Escenario` cambiada, y las 162 líneas de título son idénticas antes y después. La regla MD014 quita el símbolo de dólar y el espacio que preceden a los comandos de los bloques de código, lo que cambia contenido dentro de bloques pero no su significado.

#### Fila D4 · limpieza manual, un commit por herramienta

| Herramienta | Antes | Después | Qué se hizo |
|---|---|---|---|
| `markdownlint-cli2` (`b6d8f34`) | 164 (MD040 106, MD028 29, MD025 16, MD001 13) | 0 | Idioma en 106 bloques de código (`text`, y `diff` en uno); 29 citas separadas por una línea en blanco se unen con `>`; 16 encabezados de primer nivel de `docs/05-tickets-trabajo.md` pasan a segundo nivel sin cambiar su texto ni las anclas; un byte NUL real de `sdd/tickets/tkt-007/impl.md` pasa al texto visible `\x00`. Los 164 de esta fila son los 162 de la medición más 2 MD040 de los dos bloques del propio impl.md, escrito después de medir. |
| `Vale` (`9a9f8b4`) | 26 (`Vale.Terms` 13, `Cimenta.Vocabulario` 8, `Vale.Repetition` 5) | 0 | Los nombres literales (`PLAFONES Y CAJILLOS`, rutas, datos de entrada) y las citas intencionales de «`tablaroka`» van en código en línea; cuatro repeticiones reales («del del proceso») se corrigen y una «A» repetida en una celda se reformula. Ninguna regla se apagó ni se tocó el vocabulario. En `docs/04-historias-usuario.md` cambian tres pasos de escenario (líneas 503, 1330 y 1589; no son títulos): el nombre de la partida, que estaba en mayúsculas sin código, pasa a código en línea. Los títulos `**Escenario N:` y su significado no cambian. Las 26 incluyen 6 alertas de los documentos del propio ticket escritos durante D2 (5 en `impl.md` y 1 en `_index.md`), que la medición de 20 no contaba; el umbral no cambia: 183 sin el ticket y 191 con él, por encima de 120. |
| `lychee` | 1 error de 1333 enlaces | 0 errores de 1347 | El cambio de `sdd/tickets/tkt-006/impl.md:670` (el dato `<Ana@Cimenta.TEST>` en código en línea) resuelve el único enlace roto |

**Decisión de jerarquía.** La bajada de los H1 de `docs/05` a H2 deja algunos encabezados hijos como H2 hermanos de su sección: `tools/verificar_docs.py` exige que los encabezados de ticket sean H3. Cambiar esa regla del verificador es una decisión posterior.

#### Fila D5 · pasos de documentación y detector semanal

**Rojo.** `tools/tests/test_definicion_documentacion.py`: 23 pruebas, 4 en rojo sobre los archivos reales por la razón esperada (`enlaces.yml` y los pasos no existían) y el resto sintéticas, nacidas en verde por construcción, con unos 155 mutantes por `exigir_rojo`. Suite completa: 318 pruebas con 4 fallos.

**Verde.** El trabajo `documentacion` ejecuta, en orden y con `if: ${{ !cancelled() }}` en cada paso, `verificar_docs.py`, `markdownlint-cli2@0.24.0`, `Vale` (`uvx --from vale==3.25.1.0`, con la guarda de salida vacía), `lychee-action` v2.9.0 fijada por SHA con `lycheeVersion: v0.24.2` y `fail: true`, y el bucle de `mmdc`. `enlaces.yml` usa el cron `0 13 * * 1`, `workflow_dispatch` y la misma configuración de `lychee`. Con un `.md` de «`tablaroka`» puesto en `docs/`, el paso de `Vale` sale con 1 e imprime las alertas; sobre el repositorio limpio sale con 0 y un archivo vacío.

**Rojo de `zizmor` y ajuste.** El primer verde dejó a `zizmor` con un hallazgo `adhoc-packages` por `npm install` sin lockfile. Las pruebas se ajustaron en rojo (3 fallos: faltaban `.github/mermaid/` y el `npm ci`) y el verde posterior las dejó en 325 pruebas sin fallos, con `zizmor` en `No findings to report (1 suppressed)`; la supresión es la nota de concurrencia de `ci.yml` que ya existía.

**No ejecutado en local:** el bucle de `mmdc`, porque `npm ci` descarga Chromium (unos 170 MB). Se valida en el pipeline.

#### Fila D7 · documentación y ADR

ADR `docs/adr/20261029-vale-para-prosa-en-espanol.md` con sus opciones descartadas (estilo Microsoft, ortografía con Hunspell, sin `Vale`) y el estilo propio mínimo elegido; recuento de decisiones de 25 a 26 en `CLAUDE.md`, `README.md` y `llms.txt`; `convenciones.md` §10, la skill `conv-documentacion`, `docs/06` §9 y §10, `docs/arranque-local.md` y `tools/README.md`. Los tres verificadores y `verificar_docs.py` dan cero tras el cambio.

#### Fila D6 · ensayo en el pipeline (lo ejecutó la persona usuaria)

**Primer PR limpio.** El PR [#17](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/17), en borrador hacia `Produccion`, dejó en rojo solo el paso de `lychee` en su primera ejecución ([40936972466](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40936972466), sobre `ca1e9ab`): un artículo de Medium responde `403` al corredor. Con la exclusión de `^https://medium\.com/` (`a4c5949`), la ejecución [40938042934](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40938042934) pasó los nueve trabajos. Era la primera validación real de `Vale`, `lychee` y `mmdc` en el corredor.

**Ensayo.** El PR de ensayo [#18](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/18), en borrador con base en `tkt-009d-calidad-documental`, usa la rama `ensayo/tkt-009d-compuertas`: `8686f6a` (ronda 1) añade a `docs/convenciones.md` las cinco violaciones y `71d54d1` las revierte (ronda de limpieza). Las violaciones nunca se fusionan.

| Ronda | Commit | Ejecución | Resultado |
|---|---|---|---|
| 1 · cinco violaciones | `8686f6a` | [40939362032](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40939362032) | `failure`: solo el trabajo `Documentación`; los otros ocho trabajos en verde |
| Limpieza (revert) | `71d54d1` | [40939383211](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40939383211) | `success`: los nueve trabajos en verde |

**Pasos del trabajo `Documentación`.**

| Paso | Ronda 1 | Limpieza |
|---|---|---|
| Verificar la documentación | **`failure`** | `success` |
| Markdown con markdownlint-cli2 | **`failure`** | `success` |
| Prosa con Vale | **`failure`** | `success` |
| Enlaces con lychee | **`failure`** | `success` |
| Instalar mermaid-cli | `success` | `success` |
| Diagramas con mermaid-cli | **`failure`** | `success` |

**Extractos de la ronda 1, cada violación en su paso:**

```text
Verificar la documentación:
  ✗ Enlace roto · docs/convenciones.md → no-existe-ensayo.md
markdownlint-cli2:
  docs/convenciones.md:404 error MD040/fenced-code-language Fenced code blocks should have a language specified
Vale:
  docs/convenciones.md:400:54:Cimenta.Vocabulario:Usa 'tablaroca' en lugar de 'tablaroka' (glosario).
lychee (2 errores):
  [ERROR] docs/no-existe-ensayo.md (at 396:26) | File not found
  [404] https://github.com/FranciscoRodSilva/enlace-roto-cimenta-ensayo-009d (at 398:25) | Rejected status code: 404 Not Found
mermaid-cli:
  Error: Parse error on line 2 (flowchart TD, A -> B), con la anotación ::error del archivo
```

Los registros de ambas ejecuciones no contienen `ghp_` ni `github_pat_`. El detector semanal `enlaces.yml` no se podía lanzar hasta que llegara a la rama por omisión; su definición la fijan las pruebas TC-64 y su configuración es la del PR. Tras la fusión se lanzó a mano con `gh workflow run enlaces.yml`: la ejecución [40943983006](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40943983006) terminó en `success` sobre `6fb4cb6`. Su resultado se anota en `delta.md`.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| D1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D2 (`markdownlint` y `Vale`) | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D2 (`lychee`) | orquestador | `haiku` | sin agente | Descarga verificada y una ejecución de una línea; se corrigió `lychee.toml` en el acto |
| D3 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D4 `markdownlint` | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D4 `Vale` | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D5 · rojo y rojo del ajuste | `tester-backend` | `haiku` (el diseño asigna el rojo a `ingeniero-devsecops`) | `sonnet` | La convención de TDD de «Convenciones de código» de `CLAUDE.md`: quien escribe el código no toca los tests |
| D5 · verde y verde del ajuste | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| D6 | git-entrega (previsto, haiku) | — | sin agente | La ejecutó la persona usuaria con dos PR en borrador |
| D7 | `ingeniero-devsecops` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-13` `[M]` | `[M]` | **Cumplido** | `markdownlint-cli2`, `Vale` y `lychee` dan cero hallazgos sobre el alcance (la línea base de 183 se limpió en D3 y D4). El trabajo `documentacion` está en verde en el [PR #17](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/17) (ejecución [40938042934](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40938042934)) y en rojo, con cada violación en su archivo y línea, en el [PR de ensayo #18](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/18) (ejecución [40939362032](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40939362032)) |
| `CA-14` `[M]` | `[M]` | **Cumplido** | `enlaces.yml` tiene el cron semanal y `workflow_dispatch` (TC-64). En la ronda 1 del ensayo, `lychee` pone en rojo el enlace externo a una página de GitHub que da 404 |
| `CA-16` `[S]` | `[S]` | **Cumplido** | En la ronda 1 del ensayo, `mermaid-cli` pone en rojo el diagrama `A -> B` (prioridad `Should`). En la ejecución 40938042934 los diagramas reales pasan |
| `CA-R4` `[M]` | `[M]` | **Cumplido** | La suite de `tools/` pasa de 295 (antes de D5) a 325 pruebas en el cierre de la fila D5 (332 tras el ciclo 1 de `/sdd-revisar`, 338 tras el ciclo 2 y 341 tras el ciclo 3) (`python -m unittest discover -s tools/tests`), sin quitar ninguna ni añadir `skip`, `xfail` ni `.only`. Las 162 líneas `**Escenario N:` no cambian desde D3 |
| `CA-15` su parte | `[M]` | **Cumplido** | D7: `convenciones` §10, `conv-documentacion` y `docs/06` §9 y §10 |

## Auditorías

Primera pasada de cierre de fase y una reauditoría acotada, ambas con `REQUIERE CAMBIOS` por Menores documentales. Los de la primera pasada (F001, F003, F004 y F006) están resueltos y la reauditoría los confirmó. Ella encontró dos Menores y dos observaciones nuevos (N001 a N004): N001 a N003 se aplicaron con su texto literal sin una segunda reauditoría, y N004 se resolvió con la ejecución del pipeline. Ninguna auditoría ha aprobado este ticket todavía: `/sdd-revisar` vuelve a auditarlo.

| Auditor | Veredicto | Hallazgos | Nota |
|---|---|---|---|
| `auditor-arquitectura` | **REQUIERE CAMBIOS** | F001 a F003 Menores; F004 a F007 observaciones | Reauditoría en la fila siguiente |
| `auditor-arquitectura` (reauditoría) | **REQUIERE CAMBIOS** | N001 y N002 Menores; N003 y N004 observaciones | N001 a N003 aplicados; N004 resuelto |
| `auditor-sql` | No aplica | — | El ticket no toca el esquema |

Estado de los hallazgos:

| ID | Tipo | Hallazgo | Estado |
|---|---|---|---|
| F001 | Menor | Las secciones finales de este documento datan de cuando la ejecución se detuvo en D2 | **Resuelto** al aplicar esta corrección |
| F002 | Menor | El PR de ensayo #18 y su rama `ensayo/tkt-009d-compuertas` siguen abiertos | **Resuelto**: el PR #18 se cerró sin fusionar el 2026-10-29 y la rama `ensayo/tkt-009d-compuertas` ya no existe en `origin` |
| F003 | Menor | Los ajustes de la parte d (pruebas en `test_definicion_documentacion.py`, `lycheeVersion` y la exclusión de `medium.com`) no figuraban en el diseño | **Resuelto** al aplicar esta corrección |
| F004 | Observación | La fila D4 de `markdownlint-cli2` decía 164 sin explicar la diferencia con los 162 de la medición | **Resuelto** al aplicar esta corrección |
| F005 | Observación | `.github/mermaid` sin auditoría ni Dependabot | **Resuelto** en el ciclo 1 de `/sdd-revisar`: el trabajo `dependencias` audita `.github/mermaid` con `npm audit --audit-level=high` y Dependabot lo vigila cada semana |
| F006 | Observación | Tres pasos de escenario de `docs/04` cambiaron de texto a código sin que la fila D4 lo aclarara | **Resuelto** al aplicar esta corrección |
| F007 | Observación | El pipeline no se ha comprobado sobre el último commit | **Persiste (parcial)**: la ejecución [40943128945](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40943128945) sobre `b00f4da` dejó los nueve trabajos en verde; el HEAD de la rama (`d750d0d` y los commits posteriores) no tiene ejecución de CI y el paso «Auditar el lock de mermaid-cli» (`.github/workflows/ci.yml`) nunca ha corrido en CI. |
| N001 | Menor | La verificación final decía que D2 tenía ciclo con rojo antes de verde | **Resuelto**: D2 es una medición sin ciclo |
| N002 | Menor | Se hablaba de cinco violaciones previstas y de la cobertura de TC-62, TC-63, TC-66 y TC-68 para todas | **Resuelto**: cuatro previstas más la de `markdownlint`, que no tiene TC |
| N003 | Observación | Las 26 alertas de `Vale` frente a las 20 de la medición | **Resuelto**: 6 son de los documentos del propio ticket escritos durante D2 |
| N004 | Observación | `lychee` no se pudo ejecutar en la reauditoría | **Resuelto**: en la ejecución 40943128945 sobre `b00f4da`, los pasos `Enlaces con lychee` y `Diagramas con mermaid-cli` terminaron en `success` |

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `.github/puppeteer-config.json` | `--no-sandbox` desactiva el sandbox de Chromium en el corredor; es una decisión del diseño, para la auditoría de seguridad | Baja |
| `lychee.toml` | `exclude_path` toma expresiones regulares: el punto de `.venv` es un comodín | Baja |
| `Vale` en CI | El paquete de PyPI `vale` es un envoltorio de terceros que descarga el binario oficial en la primera ejecución sin hash; convendría fijar el binario oficial por SHA del asset (coste aceptado en el ADR, `(asumido)`) | Baja |
| `npx --yes markdownlint-cli2@0.24.0` | Resuelve sus dependencias transitivas en cada ejecución, sin lockfile (coste aceptado en el ADR, `(asumido)`) | Baja |

## Documentación actualizada

El commit `6b8ad11` (fila D7) tocó doce archivos, no once: el ADR y su entrada en el índice cuentan por separado.

| Archivo | Qué cambió |
|---|---|
| `docs/adr/20261029-vale-para-prosa-en-espanol.md` | ADR nuevo: estilo propio mínimo de `Vale` en lugar del estilo Microsoft, con sus opciones descartadas, la configuración de cada herramienta y la medición de la línea base |
| `docs/adr/README.md` | Entrada del ADR en el índice |
| `CLAUDE.md` | Recuento de decisiones de 25 a 26 |
| `README.md` | Recuento de ADR de 25 a 26 |
| `llms.txt` | Recuento de ADR de 25 a 26 |
| `docs/convenciones.md` §10 | Filas de prosa y de diagramas de la tabla de validación: estilo del proyecto y `@mermaid-js/mermaid-cli` en CI |
| `.claude/skills/conv-documentacion/SKILL.md` | Viñetas de validación alineadas con el estilo del proyecto y con `mermaid-cli` en el pipeline; forma errónea citada como ejemplo en código en línea; `interrogate` marcado como previsto |
| `docs/06-stack-tecnologico.md` §9 y §10 | §9: versiones fijadas de las cuatro herramientas y dónde corren. §10: trabajo `documentacion`, detector semanal `enlaces.yml` y nivel de aviso frente a nivel de error |
| `docs/arranque-local.md` | Fila del trabajo `documentacion` en la tabla de reproducción local y sección «Calidad de la documentación en local» con sus comandos |
| `tools/README.md` | Sección «Herramientas documentales de terceros» con la tabla de versiones; `mermaid-cli` ya no figura como sustitución futura |
| `docs/05-tickets-trabajo.md` | Una línea de enlace al ADR de `Vale`, junto al de la política de severidad de `pip-audit` |
| `sdd/tickets/tkt-009/design.md` | Filas D1 a D5 y D7 en `✓ Hecho`, y la sección «Ajustes registrados al ejecutar la parte d» |

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia: CA-13, CA-14, CA-16 (`[S]`), CA-R4 y CA-15 en su parte, en «Resultado contra los criterios de aceptación»
- [x] Ciclo por fila: D1 y D5 con rojo antes de verde (D5 con su ajuste); D2 es una medición sin ciclo, y sus casos TC-60 y TC-61 son ejecuciones locales de `Vale`; D3, D4 y D7 sin pruebas nuevas, verificadas con los verificadores; D6 lo ejecutó la persona usuaria, con la ronda 1 en rojo y la limpieza en verde
- [x] Suite en verde: `python -m unittest discover -s tools/tests` da 341 pruebas sin fallos
- [x] Rechazos: las cuatro violaciones previstas en el diseño ponen en rojo su paso con archivo y línea (TC-62, TC-63, TC-66 y TC-68). El fallo de `markdownlint` (MD040, `docs/convenciones.md:404`) no estaba previsto y no tiene TC; si se quiere uno propio, es un cambio de diseño que aprueba la persona que aprueba
- [x] Mutación de los comprobadores: las pruebas de D5 en `tools/tests/test_definicion_documentacion.py` incluyen clases `PruebasDeMutantes…` que comprueban que cada mutante es detectado
- [x] Documentación actualizada en la fila D7 (ver la tabla de arriba), y `verificar_docs.py` en 0
- [ ] Todas las auditorías APROBADO: **no**. `auditor-arquitectura` y su reauditoría están en REQUIERE CAMBIOS por Menores, ya aplicados (F001 a F006 y N001 a N004 resueltos; F007 persiste de forma parcial hasta que la rama se empuje y el pipeline pase sobre el último commit); falta que `/sdd-revisar` vuelva a auditar
- [x] Rama correcta y sin secretos en el diff

Pendiente para `delta.md`: anotar la ejecución manual de `enlaces.yml` [40943983006](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40943983006), `success` sobre `6fb4cb6`. Queda a cargo de la persona usuaria: empujar `tkt-009d-correcciones-revision` y comprobar el pipeline sobre el último commit (F007 y R-ARQ-C1-06).

## Revisión (`/sdd-revisar`, 2026-10-29)

**Contexto.** El PR [#17](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/17) se fusionó (`6fb4cb6`) antes de la revisión, así que esta se hace sobre la rama `tkt-009d-correcciones-revision`, creada después de la fusión.

**Suite ejecutada.**

| Comprobación | Resultado |
|---|---|
| Backend (`uv run pytest`) | `1138 passed in 242.68s` |
| `ruff` | En verde |
| `mypy` | 153 archivos fuente, sin problemas |
| `lint-imports` | 15 contratos, 0 rotos |
| `verificar_float` | 18 archivos, 0 hallazgos |
| `verificar_docs.py` | En verde |
| Pruebas de `tools/` | 325 pruebas (en `6fb4cb6`; 332 tras el ciclo 1, 338 tras el ciclo 2 y 341 tras el ciclo 3) |
| `markdownlint-cli2` | 0 hallazgos |
| `Vale` | 0 alertas |
| `zizmor` | Sin hallazgos |

**Auditorías del ciclo 0.** Las cuatro dieron `REQUIERE CAMBIOS`. Cada auditor numera sus hallazgos desde F001 o D001, así que aquí llevan prefijo para no repetir identificadores.

| Auditor | Prefijo | Hallazgos |
|---|---|---|
| `auditor-arquitectura` | `R-ARQ-` | F001 a F004, Menores |
| `auditor-codigo` | `R-COD-` | F001 y F002 Mayores; F003 a F006 |
| `auditor-seguridad` | `R-SEG-` | F001 `MEDIA`; F002 a F005 `BAJA` |
| `auditor-docs` | `R-DOC-` | D001 a D006 Menores; D007 a D009 observaciones |

**Ciclo 1 de corrección.** La rama `tkt-009d-correcciones-revision` recoge las pruebas endurecidas de los comprobadores, la auditoría del lock de `mermaid-cli` en el trabajo `dependencias`, la cuarta entrada de Dependabot para `.github/mermaid` y las correcciones documentales de esta pasada.

**Reauditoría del ciclo 1.** Sobre la rama con las correcciones del ciclo 1, los cuatro auditores volvieron a pasar. Sus identificadores llevan el mismo prefijo que en el ciclo 0.

| Auditor | Veredicto | Hallazgos |
|---|---|---|
| `auditor-seguridad` | **APROBADO** (registro del orquestador: el informe del auditor no se guardó en disco) | `R-SEG-F001` Resuelto; `R-SEG-F002` a `R-SEG-F005` persisten como costes aceptados de severidad `BAJA` |
| `auditor-codigo` | **REQUIERE CAMBIOS** | `R-COD-F001` Mayor reducido (10 mutantes de flujo vivos en el paso de `mmdc` y el de `Vale`); `R-COD-F005b`, `R-COD-F005c`, `R-COD-F007` y `R-COD-F008` Menores |
| `auditor-arquitectura` | **REQUIERE CAMBIOS** | `R-ARQ-C1-01` a `R-ARQ-C1-04` Menores; `R-ARQ-C1-05` y `R-ARQ-C1-06` observaciones |
| `auditor-docs` | **REQUIERE CAMBIOS** | `R-DOC-F001` Mayor; `R-DOC-F002` y `R-DOC-F003` Menores |

Estado de los hallazgos de la reauditoría:

| ID | Tipo | Hallazgo | Estado |
|---|---|---|---|
| R-SEG-F001 | `MEDIA` | El lock de `mermaid-cli` sin auditoría ni vigilancia | **Resuelto** |
| R-SEG-F002 a R-SEG-F005 | `BAJA` | Costes aceptados del ciclo 0 | Persisten como costes aceptados, sin acción |
| R-COD-F001 | Mayor | 10 mutantes de flujo vivos en el paso de `mmdc` y el de `Vale` | En corrección en el ciclo 2 (pruebas) |
| R-COD-F005b, R-COD-F005c, R-COD-F007, R-COD-F008 | Menor | Menores de código de la reauditoría | En corrección en el ciclo 2 (pruebas) |
| R-ARQ-C1-01 | Menor | Falta el lock de `mermaid-cli` en `docs/06` §6.4 y en el bloque local de `docs/arranque-local.md` | Corregido en el ciclo 2, pendiente de reauditar |
| R-ARQ-C1-02 | Menor | Cifra de pruebas de `tools/` desactualizada en este documento | Corregido en el ciclo 2 (338) y actualizado en el ciclo 3 (341), pendiente de reauditar |
| R-ARQ-C1-03 | Menor | El ADR de `Vale` omite el resultado del run 40943924695 y el aviso residual de `katex`, y deja «Brecha cerrada» entre los costes | Corregido en el ciclo 2, pendiente de reauditar |
| R-ARQ-C1-04 | Menor | El diseño de TKT-009 y `docs/05` siguen con tres ecosistemas de Dependabot y sin el paso de `mermaid-cli` | Corregido en el ciclo 2, pendiente de reauditar |
| R-ARQ-C1-05 | Observación | Flujo de actualización de `@mermaid-js/mermaid-cli` frente a TC-65 | Recogido en el ADR de `Vale` como coste aceptado, `(asumido)` |
| R-ARQ-C1-06 | Observación | Los commits del ciclo 1 no tienen ejecución de CI: la rama no está en `origin` | Persiste hasta empujar la rama y comprobar el pipeline sobre el último commit |
| R-DOC-F001 | Mayor | `docs/06` §6.4 y §10 no mencionaban el lock de `mermaid-cli` ni la cuarta entrada de Dependabot | Corregido en el ciclo 2, pendiente de reauditar |
| R-DOC-F002 | Menor | Cifras de pruebas de `tools/` de este documento | Corregido en el ciclo 2 (338) y actualizado en el ciclo 3 (341), pendiente de reauditar |
| R-DOC-F003 | Menor | `docs/06` §8 presentaba `interrogate` como si ya corriera en el pipeline | Corregido en el ciclo 2, pendiente de reauditar |

**Ciclo 2 de corrección, en curso.** Aplica los hallazgos anteriores: la documentación en esta pasada y las pruebas de `tools/` en otra. La revisión no tiene veredicto todavía; `/sdd-revisar` vuelve a auditar al terminar el ciclo.

## Veredicto de la revisión (2026-10-29)

**`LISTO PARA PR`, con una excepción aceptada.** Los criterios `[M]` están cumplidos con evidencia, no queda ningún hallazgo crítico ni Mayor sin atender, y el pipeline del PR [#19](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/19) pasó los nueve trabajos sobre `18dce53` ([ejecución 40958703474](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/actions/runs/40958703474)), incluido `herramientas` en Linux, donde corren por primera vez las pruebas que ejecutan con `bash` los pasos de `mermaid-cli` y de `Vale`, y el paso nuevo `Auditar el lock de mermaid-cli`. Los tres ciclos de corrección de `/sdd-revisar` están agotados:

- **Seguridad:** `APROBADO` en su reauditoría del ciclo 1 (registro del orquestador; el informe no se guardó en disco). Su MEDIA, el lock de `mermaid-cli`, se resolvió con el paso nuevo de `dependencias` y la cuarta entrada de Dependabot.
- **Código, arquitectura y documentación:** `REQUIERE CAMBIOS` en la reauditoría del ciclo 2. Todos sus hallazgos se aplicaron con su texto literal en el ciclo 3 (entre ellos el Mayor R-COD-F001, con su prueba en rojo primero), **sin una reauditoría formal**, porque los ciclos estaban agotados. Es la misma excepción que se aceptó en TKT-009a, TKT-009b y TKT-009c. La persona que aprueba la aceptó el 2026-10-29 con su respuesta «Sí, acepto», después de fusionar el PR #19.
- **Deuda aceptada, de prioridad baja:** `npx --yes markdownlint-cli2@0.24.0` resuelve sus dependencias transitivas sin lockfile, el paquete `vale` de PyPI descarga el binario sin hash, los dos avisos `low` de `katex` no tienen arreglo compatible, y `ruff format` falla en archivos de `tools/` que ya estaban sin formatear.
