# Delta · TKT-xxx · <título>

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|

## Comportamiento observable nuevo

Lo que un usuario o un integrador nota. Si el ticket era un refactor, esta sección dice «Ninguno» — y eso es el criterio de que fue un refactor.

-

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| endpoint · DTO · tipo generado · esquema | | |

## Decisiones (ADR)

Solo lo que un recién llegado se preguntaría «por qué lo hicieron así» **y** tuvo opciones descartadas. Sin evidencia citable no es un ADR, es una opinión.

### <fecha> — <título de la decisión>

**Contexto:** qué forzó decidir
**Opciones consideradas:**
**Decisión:** la elegida y por qué
**Evidencia:** el test, la medición o el hallazgo que la respalda
**Consecuencias:** qué queda limitado o pendiente

→ Si merece ADR del repositorio: `docs/adr/YYYYMMDD-<slug>.md`, y su entrada en el índice.

## Aprendizajes

Dato o patrón reutilizable, sin alternativa descartada. Si tiene alternativa descartada, es ADR, no fila.

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto: qué costó más de lo que debía, qué faltó en una plantilla, qué guardrail no existía.

| Tema | Observación | Severidad |
|---|---|---|

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|

## Pull request

**Título:** `TKT-xxx · <título>`
**Origen:** `human` · `human+copilot` · `agent` · `agent+human-review`. Es el origen del código, es decir, quién lo escribió, no el estado de la revisión: lo fija quien abre el PR y no cambia al aprobar.
**Cuerpo:** qué, por qué, criterios cubiertos, cómo verificarlo.

**Fusión con omisión:** solo si esta fusión será con omisión de la protección de `Produccion`. El registro no va en este archivo, porque `delta.md` se escribe antes de fusionar. Va en un comentario del PR que la persona dueña deja justo después de `gh pr merge --admin`, con la frase «fusionado con omisión de la protección», la fecha, el número del PR, la etiqueta de origen, el enlace a su revisión en el PR y el enlace a la ejecución con las diez comprobaciones requeridas en verde. El cierre viaja dentro del PR del ticket: nunca se empuja directamente a `Produccion`.
