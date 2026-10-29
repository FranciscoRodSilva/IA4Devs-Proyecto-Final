# Spec · TKT-009d · Calidad de documentación

> [← index](_index.md) | Spec común: [TKT-009](../tkt-009/spec.md) | Diseño común: [design](../tkt-009/design.md)

## Contexto y problema

TKT-009 se partió en cuatro tickets hermanos al aprobarse su diseño, el 2026-10-28. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-009/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-009d pone en el pipeline la calidad de la documentación: `markdownlint-cli2`, `Vale` con el vocabulario del glosario, `lychee` y `mermaid-cli`, más el detector de enlaces en un cron semanal. Ninguna de esas herramientas tiene configuración ni se ha ejecutado nunca sobre unas 37,000 líneas de Markdown, por lo que el ticket mide la línea base antes de tocar nada y la limpia: aviso en local, error en CI.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-009/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M10** completo: los verificadores documentales, el vocabulario del proyecto, el nivel de aviso en local y de error en CI, y la línea base limpia |
| | **M11** completo: el detector de enlaces en cron semanal |
| | **M12**, en su parte: `docs/convenciones.md` §10 (prosa y diagramas), `.claude/skills/conv-documentacion/SKILL.md`, `docs/06-stack-tecnologico.md` §9 y §10, `docs/arranque-local.md`, `tools/README.md` y el recuento de ADR |
| **Should** | **S1** completo: `mermaid-cli` en CI |
| **Won't** | `interrogate` · reglas de ortografía española con Hunspell · el estilo Microsoft de `Vale` · convertir en error el aviso de requisitos huérfanos de `verificar_docs.py` · los Won't de la spec común |

## Non-goals

- No cambia el texto de ningún escenario ni el de sus títulos: la limpieza no toca las líneas `**Escenario N:`.
- No reescribe documentación para mejorar su contenido: solo corrige lo que una herramienta marca.
- No apaga una regla para bajar el número de hallazgos, salvo `Vale.Repetition` si marca celdas contiguas de tabla.
- Los non-goals de la [spec común](../tkt-009/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

Ninguna `RN-xx`. Aplica [convenciones §10](../../../docs/convenciones.md#10-validación-de-documentación-en-ci). Detalle en la [spec común](../tkt-009/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-009/spec.md#invariantes-que-deben-sobrevivir-al-cambio). En especial: `verificar_docs.py` sigue contando los mismos 162 escenarios, y ningún título de escenario cambia con la limpieza automática.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-13` `[M]` | Todos: documentación limpia, aviso en local, enlace roto o falta, vocabulario sin falsos errores y línea base que no se ensucia | D1, D2, D3, D4, D5, D6 |
| `CA-14` `[M]` | Todos: cron semanal y enlace externo roto | D5, D6 |
| `CA-16` `[S]` | Todos: validación con `mermaid-cli` y diagrama inválido | D5, D6 |
| `CA-R4` `[M]` | Repetido sobre el árbol con esta parte | D3, D4 |
| `CA-15` `[M]` | Su parte: `convenciones` §10, `conv-documentacion` y `docs/06` §9 y §10 | D7 |

Los mutantes y las rondas de ensayo son los de la parte d del [diseño común](../tkt-009/design.md#ensayo-de-compuertas).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-009a por `ci.yml`; fusiona al final por orden |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Un enlace roto o una errata del vocabulario bloquean el PR |
| **E** | Estimable sin investigar antes | Con reservas | La línea base es desconocida; la fila D2 la mide y fija el umbral de 120 |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Unas 225 líneas, más la limpieza; si supera el umbral se separa |
| **T** | Sus criterios se pueden ejecutar | Sí | Archivos de ejemplo y rondas de ensayo |

Dos reservas y ningún fallo: pasa. Si la medición supera el umbral, se propone partir la limpieza antes de seguir.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, con cada compuerta demostrada en rojo.
- [ ] La tabla de medición de la línea base está en `impl.md` y la limpieza termina con cero hallazgos.
- [ ] `git diff -U0 -- docs/04-historias-usuario.md` sin ninguna línea `**Escenario N:` cambiada, y `verificar_docs.py` con 162 escenarios.
- [ ] ADR de `Vale` para prosa en español escrito, con su entrada en el índice.
- [ ] Auditoría de arquitectura, de código y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-009/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `A-5` (la línea base) y `A-11` (`Vale` sobre prosa en español).

## Pasada adversarial

La de la [spec común](../tkt-009/spec.md#pasada-adversarial) y la del [diseño común](../tkt-009/design.md#pasada-adversarial). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-009/spec.md#contexto-técnico). Filas D1 a D7 del [diseño común](../tkt-009/design.md#parte-d--calidad-documental); todas en `haiku`.
