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
**Origen:** `agent` · `agent+human-review` · `human+copilot`
**Cuerpo:** qué, por qué, criterios cubiertos, cómo verificarlo.
