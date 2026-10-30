# Spec · TKT-062b · Revisión automatizada

> [← index](_index.md) | Spec común: [TKT-062](../tkt-062/spec.md) | Diseño común: [design](../tkt-062/design.md)

## Contexto y problema

TKT-062 se partió en dos tickets hermanos al aprobarse su diseño, el 2026-10-29. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-062/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-062b crea la revisión automática: el flujo `revision-ia.yml`, con un trabajo que ejecuta `anthropics/claude-code-action` con permisos de solo lectura y otro que publica un único comentario tras un filtro de citas; las instrucciones versionadas `.claude/revision-pr.md`; el script `tools/publicar_revision.py`; la excepción nombrada de `secrets.` en las pruebas de TKT-009; el ADR-028; y los PR de ensayo. La revisión comenta y nunca aprueba ni bloquea. Se ejecuta con TKT-062a ya fusionado, porque usa la protección de `Produccion` y la comprobación «Etiqueta de origen» que esa parte deja puestas.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-062/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1** flujo de revisión aparte, sin borradores ni bifurcaciones: queda construido y comprobado de forma estática; que comenta en ejecución es Won't en este ticket (recorte 2026-10-30) |
| | **M2** permisos mínimos y revisión que no puede aprobar: comprobado de forma estática; la prueba en ejecución es Won't en este ticket (recorte 2026-10-30) |
| | **M3** instrucciones versionadas que remiten y se leen de `Produccion`: comprobado de forma estática; la lectura de la base en ejecución es Won't en este ticket (recorte 2026-10-30) |
| | **M4** cada hallazgo cita lo que incumple, PR sin ticket y PR que toca `openapi.yaml`: cubierto por el filtro y sus pruebas; el comentario en un PR real es Won't en este ticket (recorte 2026-10-30) |
| | **M6** completo: la excepción nombrada de `secrets.` y el ADR-028 |
| | **M7** la clave en secretos del repositorio — **Won't en este ticket (recorte 2026-10-30)** |
| | **M8**, en su parte: el ajuste que impide a Actions aprobar PR sigue vigente; la clave dedicada con su tope y el secreto son Won't en este ticket (recorte 2026-10-30) |
| | **M9** turnos y tiempo acotados `(asumido)`: comprobado de forma estática; el ensayo de tiempo es Won't en este ticket (recorte 2026-10-30) |
| | **M10** el PR de ensayo con el `float` y el `async def` — **Won't en este ticket (recorte 2026-10-30)** |
| | **M11**, en su parte: convenciones §12, stack §10 (`revision-ia.yml`), `tools/README.md` (`publicar_revision.py`), `CLAUDE.md` (revisión y recuento de ADR) y el ADR-028 |
| **Should** | **S1** la tercera violación en el PR de ensayo, confirmada el 2026-10-29 — **Won't en este ticket (recorte 2026-10-30)** |
| **Won't** | La etiqueta de origen y la protección de `Produccion` (TKT-062a, ya fusionada) · lo de la spec común |

## Recorte de alcance del 2026-10-30

La persona responsable decidió el 2026-10-30, mediante `/sdd-escalar`, recortar este ticket por falta de presupuesto para una clave de API de Anthropic. El registro vigente está en [`_index.md`](_index.md#decisiones-registradas). La revisión automatizada queda **construida pero inactiva**, y mientras tanto la revisión es local, con `/code-review`.

Pasan a **Won't en este ticket**, con la misma fecha, estas partes de los ítems de la tabla de Alcance, que solo se cumplen con la revisión en ejecución: la parte en ejecución de `M1`, `M2`, `M3`, `M4` y `M9`; `M7` y `M10` enteros; `M8` en su parte de clave y secreto, y `S1`. La tabla de Alcance marca cada ítem afectado. Con ellos, los escenarios `CA-1` (que la revisión comenta), `CA-3` esc. 2, `CA-4` esc. 2, `CA-8` esc. 1, `CA-10` esc. 2, `CA-11`, `CA-S1` y `CA-9` en lo suyo. Siguen vigentes, y verificados de forma estática con su rechazo, `CA-2`, `CA-3` esc. 1 y 3, `CA-4` esc. 1, `CA-5`, `CA-7`, `CA-8` esc. 2, `CA-10` esc. 1, `CA-12` y `CA-R1` a `CA-R4`. Las rondas de ensayo R0b a R6 y la fila B4 se retiran.

## Non-goals

- No cambia `etiqueta-origen.yml` ni la protección de `Produccion` salvo para comprobarlas de forma estática.
- No añade la revisión a las comprobaciones requeridas.
- No añade `concurrency`, `CODEOWNERS` ni plantilla de PR.
- No activa el flujo: no crea el secreto `ANTHROPIC_API_KEY` ni ejecuta rondas de ensayo (recorte del 2026-10-30).
- No toca `backend/` ni `frontend/`.
- Los non-goals de la [spec común](../tkt-062/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

Ninguna `RN-xx`. `RNF-07` y `RNF-08`, convenciones §12 y las exigencias de proceso de `CLAUDE.md`. Detalle en la [spec común](../tkt-062/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Todos los de la [spec común](../tkt-062/spec.md#invariantes-que-deben-sobrevivir-al-cambio), con los cuatro flujos ya presentes: el pipeline no espera la revisión, los permisos siguen mínimos y justificados, ningún flujo salvo el de revisión lee `secrets.`, y Dependabot y los nueve trabajos de `ci.yml` siguen igual.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-1` `[M]` | La revisión se dispara (estático); que comenta es Won't en este ticket (recorte 2026-10-30) | B3a |
| `CA-2` `[M]` | Borrador y bifurcación no se revisan | B2, B3a |
| `CA-3` `[M]` | Permisos mínimos y herramientas sin escritura (estático); la aprobación imposible y la inyección en ejecución son Won't en este ticket (recorte 2026-10-30) | B3a |
| `CA-4` `[M]` | Instrucciones que remiten y leídas de `Produccion` (estático) | B3a, B3b |
| `CA-5` `[M]` | Cita, comentario sin cita, PR sin ticket y `openapi.yaml` | B1, B3a |
| `CA-7` `[M]` | La excepción de `secrets.` acotada | B1, B2, B3a |
| `CA-8` `[M]` | La revisión no bloquea (estático: ningún trabajo del pipeline la espera) | B3a |
| `CA-10` `[M]` | Turnos y tiempo acotados (estático) | B3a |
| `CA-11` `[M]` | **Won't en este ticket (recorte 2026-10-30)**: las dos violaciones comentadas y el PR de ensayo sin aprobación | — |
| `CA-S1` `[S]` | **Won't en este ticket (recorte 2026-10-30)**: la regla de negocio en un controlador | — |
| `CA-9` `[M]` | Su parte: el ajuste de aprobación sigue vigente, con la evidencia de `impl.md`; la clave dedicada con su tope y el secreto son Won't en este ticket (recorte 2026-10-30) | — |
| `CA-12` `[M]` | Su parte: §12, stack §10, `tools/README.md`, `CLAUDE.md` y el ADR-028 | B7 |
| `CA-R1` a `CA-R4` `[M]` | Con los cuatro flujos | B2, B8 |

Los casos de prueba son los `TC62-NN` que el [diseño común](../tkt-062/design.md) asigna a las filas B1 a B8, y las rondas de ensayo R0b a R6 se retiraron con el recorte del 2026-10-30.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-062a fusionado; nada depende de él |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común, ya aprobado |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Quien aprueba un PR llega con los hallazgos citados |
| **E** | Estimable sin investigar antes | Sí | Unas 920 líneas según el diseño; los supuestos de la acción se resolvieron con Context7 |
| **S** | Cabe en una sesión sin romper contexto | No | Unas 920 líneas, muy por encima del tope de unas 400. No se parte más porque el flujo y el filtro de publicación solo tienen sentido juntos; el diseño divide el trabajo en filas B1 a B8 con B3a y B3b |
| **T** | Sus criterios se pueden ejecutar | Sí, con una salvedad | `CA-3` (rechazo de aprobación), `CA-10` y `CA-11` solo se demostrarían en el repositorio real; con el recorte del 2026-10-30 quedan fuera de este ticket |

Un fallo (*Pequeño*), aceptado y registrado por la persona responsable al aprobar la partición: pasa.

## Definition of Done

La genérica de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo), más lo que ese tipo exige aquí:

- [ ] Los escenarios de la tabla pasan y cada compuerta nueva se demuestra en rojo antes de pasar a verde.
- [ ] El pipeline completo corre en verde sobre el árbol del ticket, sin `skip`, `xfail` ni `.only` nuevos.
- [ ] La evidencia estática, la lectura fechada del ajuste de aprobación y el recorte constan en `impl.md`.
- [ ] `python tools/verificar_docs.py` en verde y el ADR-028 publicado en su índice.
- [ ] Auditoría de arquitectura, de seguridad, de código y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-062/spec.md#preguntas-abiertas-y-supuestos), los que toca esta parte: `A-1` a `A-6`. Todos tienen resolución en el [diseño común](../tkt-062/design.md#supuestos-abiertos-resueltos-en-el-diseño), y `A-1` y `A-2` siguen marcados `(asumido)` hasta el primer mes de uso real.

## Pasada adversarial

La de la [spec común](../tkt-062/spec.md#pasada-adversarial) y la del [diseño común](../tkt-062/design.md). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-062/spec.md#contexto-técnico). Filas B1 a B8 del [diseño común](../tkt-062/design.md); las de construcción en `sonnet`, y `haiku` en `git-entrega`, B7 y la fase verde que el diseño indica.
