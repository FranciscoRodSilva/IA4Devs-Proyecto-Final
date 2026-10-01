# Spec · TKT-xxx · <título>

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

Qué se necesita y por qué. Si es corrección de error, aquí va la **causa raíz confirmada** con su evidencia, no el síntoma.

## Historia de usuario

**Como** <rol del PRD §4>
**quiero** <capacidad>
**para** <valor>

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | |
| **Should** | |
| **Could** | |
| **Won't** | |

## Non-goals

Lo que este ticket explícitamente **no** hace. Sin esto, el agente entrega además el refactor, la documentación y una optimización de consultas.

-

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-xx` | | PRD §8 — `docs/01-descripcion-producto.md` |

## Invariantes que deben sobrevivir al cambio

Obligatorio si el ticket **modifica algo que ya funciona**. Cada invariante genera un criterio de regresión `[M]` y su test.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| | | `CA-R1` |

> Una spec de modificación sin esta sección no pasa el Definition of Ready.

## Criterios de aceptación

Gherkin, en español. **Camino feliz y al menos un escenario de rechazo por cada regla implicada.**

### CA-1 `[M]` · <título> · `RN-xx` · `HDU-xxx esc. N`

```gherkin
Escenario: <nombre>
  Dado que …
  Cuando …
  Entonces …
  Y …
```

### CA-2 `[M]` · Rechazo · <título> · `RN-xx` · `HDU-xxx esc. N`

```gherkin
Escenario: <nombre del rechazo>
  Dado que …
  Cuando …
  Entonces la operación queda <estado>
  Y la respuesta indica <dato concreto: disponible real, excedente, motivo>
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | | |
| **N** | Describe el qué, no impone el cómo | | |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | | |
| **E** | Estimable sin investigar antes | | |
| **S** | Cabe en una sesión sin romper contexto | | |
| **T** | Sus criterios se pueden ejecutar | | |

Dos o más fallos → vuelve a refinamiento. Si falla **E** por incertidumbre técnica, es un Spike, no una funcionalidad.

## Definition of Done

La del tipo de ticket, de `sdd/metodologia.md` §8 «Definition of Done por tipo».

- [ ]

## Preguntas abiertas y supuestos

Todo lo marcado `(asumido)` en los criterios se repite aquí.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

Archivos, módulos, endpoints y tablas relevantes.
