---
name: sdd-definir
description: Fase 1 del pipeline SDD de CIMENTA. Escribe la spec de un ticket — historia, alcance MoSCoW, criterios Gherkin con su escenario de rechazo, invariantes en riesgo, non-goals. Úsala cuando el usuario diga /sdd-definir o pida arrancar un ticket.
argument-hint: TKT-xxx
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Agent, Skill, WebSearch, WebFetch
---

# `/sdd-definir $ARGUMENTS`

Escribe la especificación del ticket **$ARGUMENTS**. Lee primero [`sdd/metodologia.md`](../../../sdd/metodologia.md).

## Paso 0 · Gate de entrada — si falla, STOP

| Comprobación | Si falla |
|---|---|
| El ticket existe en [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md) | Pedir el identificador correcto. No inventar el ticket |
| Su historia existe en [`docs/04-historias-usuario.md`](../../../docs/04-historias-usuario.md), con escenarios | Pedir la historia. No redactar escenarios desde cero |
| Las reglas que cita existen en el PRD | **Escalar.** No se inventan reglas de negocio |
| Si tiene endpoint, el [borrador OpenAPI](../../../docs/api/openapi.yaml) tiene operaciones con este ticket en `x-tickets` | **Escalar.** La ruta no se improvisa: el borrador se corrige antes, con revisión humana |
| Sus dependencias son de la misma fase o anterior | Un ticket de fase 1 que necesita algo de fase 2 → **escalar** (regla 17 de `CLAUDE.md`) |
| No existe ya `sdd/tickets/tkt-xxx/spec.md` | Si existe: decir el estado actual y preguntar si se reescribe |

## Paso 1 · Analizar

Despacha **`analista-dominio`** con el identificador del ticket. Devuelve: reglas `RN-xx` implicadas, invariantes en riesgo, escenarios de la historia que cubre el ticket, módulos y capas en alcance, y los términos del glosario que importan.

No sigas sin eso. Sin estado real de partida, la spec asume en vez de describir.

## Paso 2 · Intake en tres fases

No avances sin la evidencia de la anterior. Si el usuario dio todo en el primer mensaje, comprime en una sola validación.

| Fase | Qué confirmar | Señal para avanzar |
|---|---|---|
| **1 · Descubrimiento** | Qué se necesita, quién lo usa, de qué tipo es el ticket | Tipo y necesidad claros |
| **2 · Profundidad** | Módulos y capas, objetos existentes, invariantes en riesgo | Alcance identificado |
| **3 · Confirmación** | Proponer el MoSCoW y **que el usuario valide el Must** | El usuario confirma |

**Nunca generes la spec con el Must sin validar.**

## Paso 3 · Escribir la spec

Desde [`sdd/plantillas/spec.md`](../../../sdd/plantillas/spec.md), en `sdd/tickets/tkt-xxx/spec.md`.

Reglas que gobiernan la redacción:

- **Criterios por el patrón poke-holes**, nunca de una pasada. Primero el camino feliz del Must principal; después, con eso como contexto, generar candidatos de casos borde, supuestos implícitos, escenarios faltantes y riesgos de seguridad; después filtrar a los reales. Los descartados no se documentan.
- **Cada regla implicada lleva su escenario de rechazo.** Una spec de CIMENTA sin rechazos no está especificada.
- El escenario de rechazo verifica **el dato**, no solo el estado: disponible real, excedente, a quién va la autorización. Y nombra **el `tipo` del contrato de error** que responde: `REGLA_NEGOCIO` con su `RN-xx`, `CONFLICTO` con su `codigo` del catálogo cerrado, `CONCURRENCIA`, `VALIDACION` o `PERMISO` ([especificación de la API §3](../../../docs/07-especificacion-api.md#3-el-contrato-de-error)). Un conflicto que no es una `RN` no se etiqueta con una.
- Los criterios de aceptación **coinciden con los `x-escenarios` y los rechazos** de las operaciones del borrador OpenAPI. Si la historia y el borrador discrepan, es un hallazgo: escálalo, no elijas tú.
- Si toca una pantalla, los criterios citan su boceto de [`docs/08-wireframes.md`](../../../docs/08-wireframes.md).
- Un ticket de fase 1 no especifica nada de fase 2. Lo que necesite de mano de obra o avance llega por el adaptador simulado y **nunca** entra en el `consumido` de `RN-03` ([ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md)).
- **Sesgo a recortar.** Lo que puede vivir en su propio ticket no entra aquí ni como Could: va a «Tickets futuros sugeridos» de `_index.md`.
- Si el ticket **modifica algo que ya funciona**, la sección de invariantes es obligatoria y cada invariante genera un criterio de regresión `[M]`.
- Todo supuesto sin evidencia se marca `(asumido)` y se repite en preguntas abiertas.
- **Agencia real**: nombra la función, el disparador o el contrato que ejecuta cada acción.
- Contexto técnico **al final**, siempre.

## Paso 4 · Pasada adversarial

Invoca la skill **`abogado-del-diablo`** sobre la spec. Registra las objeciones y qué se hizo con cada una en la sección correspondiente. Si una objeción revela una regla que el PRD no tiene → **`/sdd-escalar`**.

## Paso 5 · Definition of Ready

Rellena la tabla INVEST. **Dos o más fallos → la spec no pasa**: dilo y vuelve a refinamiento con el usuario. Si falla *Estimable* por incertidumbre técnica, propone reclasificar el ticket como Spike.

## Paso 6 · Cerrar

1. Crea `_index.md` desde [la plantilla](../../../sdd/plantillas/_index.md) con estado `SPEC PENDIENTE` y su fila de Log.
2. Reporta: qué Must quedó, cuántos criterios y cuántos de rechazo, qué quedó `(asumido)`, qué salió del alcance.
3. Siguiente comando: `/sdd-disenar $ARGUMENTS`.

## Stop conditions

1. Falta cualquier documento de entrada → STOP, pedirlo.
2. El ticket pide algo que ninguna regla del PRD respalda → **escalar**, no inventar.
3. El usuario no ha validado el Must → no escribas la spec.
4. INVEST con dos o más fallos → no cierres la fase.
5. Un invariante registrado estorba a lo que el ticket pide → **escalar**.

## Qué NO hace este comando

No diseña, no propone archivos ni tablas, no escribe código. Si te descubres decidiendo *cómo*, eso es `/sdd-disenar`.
