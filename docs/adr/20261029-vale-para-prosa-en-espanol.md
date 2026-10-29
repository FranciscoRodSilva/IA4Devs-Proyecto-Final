# Vale para la prosa en español, con estilo propio mínimo en lugar del estilo Microsoft

## Estado

Aceptado

## Contexto y problema

La documentación de CIMENTA es el entregable y se valida en CI ([convenciones §10](../convenciones.md#10-validación-de-documentación-en-ci)). Para la prosa, el [stack §9](../06-stack-tecnologico.md#9-documentación) nombra `Vale`, y la convención la ataba al estilo Microsoft. Ese estilo está escrito para el inglés: sus reglas marcarían casi cada frase de un documento en español, y no distinguen un término del dominio de una errata. Lo que el proyecto necesita de la prosa es otra cosa: que los términos del [glosario](../glosario.md) (*tablaroca*, *destajo*, *perfacinta*, *plafón* y los demás) se escriban siempre igual, y que una palabra repetida por descuido no llegue a la revisión.

Hay dos restricciones más. La primera es que el aviso en local y el error en CI salgan de una sola configuración, para que lo que ve quien escribe sea lo que bloquea el PR. La segunda es que la línea base no estaba medida. El [diseño de TKT-009](../../sdd/tickets/tkt-009/design.md) fijó un umbral de 120 hallazgos que `--fix` no corrige para detener la parte d si se superaba (supuesto `A-5`).

## Opciones consideradas

* **Estilo Microsoft de `Vale`.** Es el que nombraba la convención. Está escrito para el inglés y marcaría casi cada frase en español. Se descarta.
* **Ortografía en español con Hunspell.** Su diccionario es español, así que marcaría cada término técnico que el proyecto toma del inglés (*pipeline*, *endpoint*, *commit*, *workflow*). Obligaría a desactivar la compuerta o a llenar el vocabulario de excepciones. Se descarta.
* **Sin `Vale`, solo `markdownlint-cli2`.** Cubre la sintaxis, pero no la terminología ni la repetición, que son lo que el proyecto necesita de la prosa. Se descarta.
* **Estilo propio mínimo.** `Vale.Terms` y `Vale.Repetition` del estilo `Vale`, y un estilo `Cimenta` con una regla `Cimenta.Vocabulario` de sustitución para las variantes erradas del glosario. Se elige.

## Decisión

Se elige el **estilo propio mínimo** porque:

* Cada regla activa atiende un fallo que quien escribe en español sí comete: una forma del vocabulario escrita mal o una palabra repetida. La ortografía y el estilo en inglés quedan fuera (`Vale.Spelling = NO`).
* El vocabulario sale del glosario y se declara en `.vale/styles/config/vocabularies/Cimenta/accept.txt`. Un término del dominio no se marca como falta, y su forma escrita, por ejemplo `CIMENTA` en mayúsculas, sí se exige.
* Las citas de una forma errónea, como el ejemplo «`tablaroka`», van en código en línea. Vale no revisa el contenido del código, así que la regla sigue activa y el ejemplo queda visible. Esto está comprobado: las citas de TKT-009 pasan con cero alertas.
* **No se apaga ninguna regla para bajar el número de hallazgos.** `Vale.Repetition` se queda. La medición no encontró celdas contiguas de tabla marcadas como repetición, así que la excepción que prevé el diseño no aplicaba. Las repeticiones reales se corrigieron en el texto.

**Aviso en local y error en CI con un solo `.vale.ini`.** El archivo declara todas las reglas en `warning`. Vale sale con código distinto de cero solo cuando hay una alerta de nivel `error`, así que en local `vale` imprime los avisos y termina en 0. Esto se comprobó con el mismo archivo: con `Cimenta = warning` la salida es 0 con las alertas impresas, y con `Cimenta = error`, 1. En CI el paso guarda la salida en un archivo, la imprime y falla si el código no es 0 o si el archivo no está vacío. Un aviso bloquea el PR sin que el pipeline necesite un segundo archivo de configuración.

**Envoltorio de PyPI.** Vale se ejecuta con `uvx --from vale==3.25.1.0 vale`. El paquete `vale` de PyPI es un envoltorio de terceros: en la primera ejecución descarga el binario oficial `v3.25.1` de `errata-ai/vale`, y el repositorio no fija el SHA de ese archivo. Se acepta como coste `(asumido)`: la versión queda fijada, pero el binario no tiene hash fijado. Fijar el asset por SHA queda como mejora.

**mermaid-cli.** En CI se instala con `npm ci` sobre `.github/mermaid/package-lock.json`, con `@mermaid-js/mermaid-cli` 12.0.0 fijado en `package.json`. No se usa `npm install` sin lockfile, porque zizmor, con su regla `adhoc-packages`, marca la instalación de paquetes fuera de un lockfile. Con `npm ci` no la marca, y los flujos no tienen comentarios de supresión de zizmor. Comprobado el 2026-10-29 sobre ese lock: `npm audit --audit-level=high` termina en 0 con dos avisos `low` de `katex`, dependencia de `mermaid-cli`. La compuerta de TKT-009 para npm es `--audit-level=high`.

**Navegador en el corredor.** `mmdc` necesita Chromium, y `.github/puppeteer-config.json` pasa `--no-sandbox` al lanzarlo en el corredor efímero de GitHub Actions. El corredor solo renderiza documentación del propio repositorio. Se acepta como coste `(asumido)`: la causa, que el sandbox de Chromium necesita espacios de nombres de usuario que el corredor no concede, no se ha comprobado en el corredor.

**lychee.** `include_fragments = "none"` en lugar de `false`. La versión 0.24.2 rechaza el booleano («wanted string or table»), y comprobado. El valor `"none"` conserva la decisión del diseño: las anclas las comprueba `tools/verificar_docs.py` con el algoritmo de GitHub. `lychee.toml` excluye `^https://medium\.com/`: Medium responde `403` al corredor de GitHub y `200` a una persona, así que su bloqueo a las IP de los corredores no es un enlace roto. El resto de enlaces externos sigue comprobándose.

**Medición de la línea base.** Antes de editar, sobre 119 archivos del alcance: 586 hallazgos de `markdownlint-cli2`, de los que 162 no corrige `--fix` (MD040, MD028, MD025 y MD001); 20 alertas de Vale (10 de `Vale.Terms`, 5 de `Vale.Repetition` y 5 de `Cimenta.Vocabulario`); y 1 enlace roto de lychee. Lo que `--fix` no corrige, más Vale y lychee, suma 183, por encima del umbral de 120 de `A-5`. La persona que aprueba decidió seguir en TKT-009d en lugar de separar la limpieza en otro ticket.

## Consecuencias

**Positivas**

* Un término del glosario escrito con una variante errónea, o una palabra repetida, falla el PR. Quien escribe ve la misma salida en local antes de subir.
* Una sola configuración sirve en local y en CI.
* La línea base queda medida y registrada, así que la limpieza se puede auditar.

**Negativas o costes aceptados**

* El paquete `vale` de PyPI descarga el binario oficial sin hash fijado en el repositorio (ver la decisión). Prioridad baja, `(asumido)`.
* `npx --yes markdownlint-cli2@0.24.0` resuelve sus dependencias transitivas en cada ejecución, porque no hay lockfile para esa herramienta. Prioridad baja, `(asumido)`.
* `--no-sandbox` en el corredor (ver la decisión).
* Vale no revisa la voz pasiva ni la ortografía. La voz activa que pide la convención se revisa a mano.

**Brecha cerrada.** Las actualizaciones de seguridad de Dependabot sí cubrían el lock de `.github/mermaid/` (la ejecución dinámica 40943924695 lo demuestra), pero las de versión faltaban. Desde la corrección del ciclo 1 de `/sdd-revisar` de TKT-009d, el trabajo `dependencias` audita `.github/mermaid` con `npm audit --audit-level=high` y Dependabot lo vigila cada semana. Con ello se cumple `RNF-08` también para ese lock.

**Cuándo revisar esta decisión**

* Si una regla de `Cimenta.Vocabulario` da un falso positivo más de una vez en un trimestre, se revisa la regla. No se apaga sin un ADR. Es un umbral propuesto, no medido.
* Si el paquete `vale` de PyPI deja de descargar el binario oficial, o cuando el asset se fije por SHA.
* Si el glosario añade términos que Vale debe exigir, se amplía `accept.txt` y se revisa esta decisión en el mismo cambio.
