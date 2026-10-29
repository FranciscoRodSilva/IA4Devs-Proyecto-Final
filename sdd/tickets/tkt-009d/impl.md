# Impl · TKT-009d · Calidad de documentación

> [← index](_index.md) | [← design](../tkt-009/design.md) | Siguiente: delta (pendiente)

## Qué se implementó

Las filas D1 a D5 y D7 de la parte d del [diseño común](../tkt-009/design.md#parte-d--calidad-documental). La línea base documental, que superaba el umbral de 120 hallazgos de `A-5` (183), se limpió en este ticket por decisión de la persona que aprueba: `markdownlint-cli2`, `Vale` y `lychee` dan cero sobre el alcance. El trabajo `documentacion` de `ci.yml` ejecuta ahora el verificador propio, `markdownlint-cli2`, `Vale` con el vocabulario del glosario, `lychee` y `mermaid-cli`, y `enlaces.yml` repite la comprobación de enlaces cada lunes. El ADR de `Vale` para prosa en español y la documentación afectada cierran la fila D7.

**Queda pendiente la fila D6**, el ensayo en el pipeline, que exige empujar la rama y abrir dos PR en borrador a mano. La rama `ensayo/tkt-009d-compuertas` está preparada en local con la ronda 1 (cinco violaciones) y el revert que deja la limpieza.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-29 | `lychee.toml` lleva `include_fragments = "none"` en lugar de `false` | `lychee 0.24.2`, la última versión estable, rechaza el booleano («wanted string or table»); sus valores son `none`, `anchor-only`, `text-only` y `full`. `"none"` conserva la decisión del diseño: las anclas las comprueba `verificar_docs.py` |
| 2026-10-29 | `mermaid-cli` 12.0.0 se instala con `npm ci` sobre `.github/mermaid/package.json` y `package-lock.json`, no con `npm install --no-save` | `zizmor` marca `adhoc-packages` (instalar un paquete fuera de un lockfile) y el diseño exige `zizmor` sin hallazgos; la supresión en línea rebajaría una compuerta de seguridad. El lock se generó con `npm install --package-lock-only --ignore-scripts` para no descargar Chromium en local |
| 2026-10-29 | `enlaces.yml` declara `concurrency: { group: enlaces, cancel-in-progress: false }` | `zizmor` en perfil pedante marca `concurrency-limits`; con el bloque, las supresiones vuelven a una |
| 2026-10-29 | El enlace externo roto del ensayo es una página de GitHub que da 404, no `https://cimenta-ensayo.invalid/` | `lychee` excluye por defecto los dominios reservados `.invalid` (comprobado: «Excluded 1» y cero errores), así que esa violación nunca habría puesto el trabajo en rojo |
| 2026-10-29 | Se añaden `lycheeVersion: v0.24.2` explícito en la acción y `if: ${{ !cancelled() }}` también en `setup-node`, `setup-uv` y la instalación de `mermaid-cli` | Regla común 3 (el valor por omisión de la acción puede cambiar) y regla común 6 (un `setup-uv` omitido taparía el hallazgo de `Vale` con «command not found») |

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

**`Vale.Terms`:** 10 alertas por mayúsculas («`PLAFONES`», «`CAJILLOS`» en `docs/01-descripcion-producto.md` y `docs/04-historias-usuario.md`) y por «`cimenta`» en minúscula en `sdd/tickets/tkt-003/design.md` y `sdd/tickets/tkt-006/impl.md`.

**Decisión pendiente.** El umbral de `A-5` está superado (183 contra 120). El diseño dice que, en ese caso, la parte se detiene y se propone separar la limpieza en su propio ticket. Esta ejecución se detiene aquí: ver `_index.md`.

#### Fila D3 · limpieza automática

`npx markdownlint-cli2@0.24.0 --fix` sobre el alcance, en un commit que solo contiene formato (`47a0500`): 33 archivos, 415 inserciones y 97 eliminaciones. `verificar_docs.py` da los mismos conteos (162 escenarios, 601 anclas, 79 story points), `git diff -U0 -- docs/04-historias-usuario.md` no muestra ninguna línea `**Escenario` cambiada, y las 162 líneas de título son idénticas antes y después. La regla MD014 quita el símbolo de dólar y el espacio que preceden a los comandos de los bloques de código, lo que cambia contenido dentro de bloques pero no su significado.

#### Fila D4 · limpieza manual, un commit por herramienta

| Herramienta | Antes | Después | Qué se hizo |
|---|---|---|---|
| `markdownlint-cli2` (`b6d8f34`) | 164 (MD040 106, MD028 29, MD025 16, MD001 13) | 0 | Idioma en 106 bloques de código (`text`, y `diff` en uno); 29 citas separadas por una línea en blanco se unen con `>`; 16 encabezados de primer nivel de `docs/05-tickets-trabajo.md` pasan a segundo nivel sin cambiar su texto ni las anclas; un byte NUL real de `sdd/tickets/tkt-007/impl.md` pasa al texto visible `\x00` |
| `Vale` (`9a9f8b4`) | 26 (`Vale.Terms` 13, `Cimenta.Vocabulario` 8, `Vale.Repetition` 5) | 0 | Los nombres literales (`PLAFONES Y CAJILLOS`, rutas, datos de entrada) y las citas intencionales de «`tablaroka`» van en código en línea; cuatro repeticiones reales («del del proceso») se corrigen y una «A» repetida en una celda se reformula. Ninguna regla se apagó ni se tocó el vocabulario |
| `lychee` | 1 error de 1333 enlaces | 0 errores de 1347 | El cambio de `sdd/tickets/tkt-006/impl.md:670` (el dato `<Ana@Cimenta.TEST>` en código en línea) resuelve el único enlace roto |

**Decisión de jerarquía.** La bajada de los H1 de `docs/05` a H2 deja algunos encabezados hijos como H2 hermanos de su sección: `tools/verificar_docs.py` exige que los encabezados de ticket sean H3. Cambiar esa regla del verificador es una decisión posterior.

#### Fila D5 · pasos de documentación y detector semanal

**Rojo.** `tools/tests/test_definicion_documentacion.py`: 23 pruebas, 4 en rojo sobre los archivos reales por la razón esperada (`enlaces.yml` y los pasos no existían) y el resto sintéticas, nacidas en verde por construcción, con unos 155 mutantes por `exigir_rojo`. Suite completa: 318 pruebas con 4 fallos.

**Verde.** El trabajo `documentacion` ejecuta, en orden y con `if: ${{ !cancelled() }}` en cada paso, `verificar_docs.py`, `markdownlint-cli2@0.24.0`, `Vale` (`uvx --from vale==3.25.1.0`, con la guarda de salida vacía), `lychee-action` v2.9.0 fijada por SHA con `lycheeVersion: v0.24.2` y `fail: true`, y el bucle de `mmdc`. `enlaces.yml` usa el cron `0 13 * * 1`, `workflow_dispatch` y la misma configuración de `lychee`. Con un `.md` de «`tablaroka`» puesto en `docs/`, el paso de `Vale` sale con 1 e imprime las alertas; sobre el repositorio limpio sale con 0 y un archivo vacío.

**Rojo de `zizmor` y ajuste.** El primer verde dejó a `zizmor` con un hallazgo `adhoc-packages` por `npm install` sin lockfile. Las pruebas se ajustaron en rojo (3 fallos: faltaban `.github/mermaid/` y el `npm ci`) y el verde posterior las dejó en 325 pruebas sin fallos, con `zizmor` en `No findings to report (1 suppressed)`; la supresión es la nota de concurrencia de `ci.yml` que ya existía.

**No ejecutado en local:** el bucle de `mmdc`, porque `npm ci` descarga Chromium (unos 170 MB). Se valida en el pipeline.

#### Fila D7 · documentación y ADR

ADR `docs/adr/20261029-vale-para-prosa-en-espanol.md` con sus opciones descartadas (estilo Microsoft, ortografía con Hunspell, sin `Vale`) y el estilo propio mínimo elegido; recuento de decisiones de 25 a 26 en `CLAUDE.md`, `README.md` y `llms.txt`; `convenciones.md` §10, la skill `conv-documentacion`, `docs/06` §9 y §10, `docs/arranque-local.md` y `tools/README.md`. Los tres verificadores y `verificar_docs.py` dan cero tras el cambio.

#### Fila D6 · ensayo en el pipeline (pendiente de la persona usuaria)

La rama local `ensayo/tkt-009d-compuertas` está preparada: `8686f6a` (ronda 1) añade a `docs/convenciones.md` un enlace relativo roto, una página de GitHub que da 404, «`tablaroka`», un bloque sin idioma y un diagrama `flowchart TD` con `A -> B`; `71d54d1` lo revierte (ronda de limpieza). En local ya fallan `verificar_docs.py` (enlace roto), `markdownlint-cli2` (MD040) y `Vale` (`Cimenta.Vocabulario`); `lychee` falla con el 404; el diagrama solo se puede validar en el pipeline. Faltan las ejecuciones del pipeline: pasos esperados en rojo en la ronda 1 y todo en verde tras el revert.

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
| D7 | `ingeniero-devsecops` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-13` `[M]` | `[M]` | **Pendiente** | La línea base no está limpia: 183 hallazgos |
| `CA-14` `[M]` | `[M]` | **No empezado** | D5 y D6 |
| `CA-16` `[S]` | `[S]` | **No empezado** | D5 y D6 |
| `CA-R4` `[M]` | `[M]` | **No empezado** | D3 y D4 |
| `CA-15` su parte | `[M]` | **No empezado** | D7 |

## Auditorías

Ninguna todavía: la ejecución se detuvo antes del cierre de fase.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `.github/puppeteer-config.json` | `--no-sandbox` desactiva el sandbox de Chromium en el corredor; es una decisión del diseño, para la auditoría de seguridad | Baja |
| `lychee.toml` | `exclude_path` toma expresiones regulares: el punto de `.venv` es un comodín | Baja |
| `Vale` en CI | El paquete de PyPI `vale` es un envoltorio de terceros que descarga el binario oficial en la primera ejecución; convendría fijar el binario oficial por SHA del asset | Media |

## Documentación actualizada

Ninguna aún.

## Verificación final

- [ ] Todos los criterios `[M]` cumplidos con evidencia: **no, la ejecución se detuvo en D2**
- [x] Ciclo por fila ejecutado en D1 y D2: rojo antes de verde
- [ ] Suite en verde: no aplica todavía
- [ ] Auditorías: pendientes
- [x] Rama correcta y sin secretos en el diff
