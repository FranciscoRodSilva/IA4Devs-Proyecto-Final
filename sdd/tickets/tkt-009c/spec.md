# Spec · TKT-009c · Verificador de escenarios sin test

> [← index](_index.md) | Spec común: [TKT-009](../tkt-009/spec.md) | Diseño común: [design](../tkt-009/design.md)

## Contexto y problema

TKT-009 se partió en cuatro tickets hermanos al aprobarse su diseño, el 2026-10-28. Esta spec no redacta criterios nuevos: reparte los de la [spec común](../tkt-009/spec.md) y fija cuáles cierra este ticket. El texto Gherkin de cada criterio está en la spec común y es el que se prueba.

TKT-009c convierte en compuerta la regla de aceptación de [ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md): un escenario que cuenta y no tiene un test que lo nombre falla el pipeline. Un escenario cuenta desde que su historia está en `tools/historias_activas.txt`; los de fase 2 cuentan cuando ese archivo contiene la línea `fase 2`; y uno retirado con el segmento ` · retirado por TKT-0NN` en su título deja de contar. Hoy no hay ningún test con la forma `test_hdu00X_escNN_…` ni un solo escenario retirado, así que el verificador se prueba con documentos de ejemplo y no contra el repositorio real.

## Historia de usuario

Ticket de fundación, sin historia de usuario propia. La historia es la de la [spec común](../tkt-009/spec.md#historia-de-usuario).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M5** completo: el verificador, `historias_activas.txt`, el informe de pendientes, la política de fase 2, el retiro de escenarios y la admisión de los nombres de fundación |
| | **M12**, en su parte: `CLAUDE.md:78`, `docs/05-tickets-trabajo.md` (ficha de TKT-069), las tres prosas de retiro de `docs/04-historias-usuario.md`, `docs/convenciones.md` §10 (fila de escenarios sin test) y el recuento de ADR |
| **Should** | — |
| **Won't** | Excluir de la cobertura un test saltado (`it.skip`), que es un ticket futuro · renombrar tests archivados · los Won't de la spec común |

## Non-goals

- No retira ningún escenario todavía: lo hace TKT-069 con el segmento en el título. Aquí solo se documenta la forma.
- No comprueba que el test verifique lo que dice el escenario: solo que exista y lo nombre.
- No importa nada de `backend/cimenta/`: usa la biblioteca estándar.
- Los non-goals de la [spec común](../tkt-009/spec.md#non-goals) siguen en pie.

## Reglas de negocio implicadas

[ADR-012](../../../docs/adr/20260918-trazabilidad-escenario-test.md) y la regla 14 de `CLAUDE.md`. Ninguna `RN-xx`. Detalle en la [spec común](../tkt-009/spec.md#reglas-de-negocio-implicadas).

## Invariantes que deben sobrevivir al cambio

Los de la [spec común](../tkt-009/spec.md#invariantes-que-deben-sobrevivir-al-cambio). En especial: `verificar_docs.py` sigue contando 162 escenarios, y el segmento de retiro no cambia ese conteo.

## Criterios de aceptación

| Criterio de la spec común | Escenarios que cierra este ticket | Filas del diseño |
|---|---|---|
| `CA-6` `[M]` | Todos: escenario activo sin test, cubierto y test mal nombrado | C1, C2, C3 |
| `CA-7` `[M]` | Todos: pendiente por historia, fase 2, historia «1+2», retiro y retiro sin nota | C1, C2, C3 |
| `CA-8` `[M]` | Todos: nombres de fundación, tests sin prefijo, inexistentes y una historia que no sale | C2, C3, C4, C5 |
| `CA-R4` `[M]` | Repetido sobre el árbol con esta parte | C4, C5 |
| `CA-15` `[M]` | Su parte: `CLAUDE.md:78`, la ficha de TKT-069 y las prosas de retiro | C6 |

Los mutantes son los de la parte c del [diseño común](../tkt-009/design.md#plan-de-pruebas).

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-009a por el trabajo `herramientas` |
| **N** | Describe el qué, no impone el cómo | Sí | El cómo está en el diseño común |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Un escenario de rechazo omitido deja de pasar inadvertido |
| **E** | Estimable sin investigar antes | Sí | Unas 440 líneas, la mitad de pruebas |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Algo por encima del tope de unas 400 líneas; el verificador y sus pruebas son una unidad y no se parten más |
| **T** | Sus criterios se pueden ejecutar | Sí | Documentos de ejemplo en un directorio temporal y una ronda de ensayo |

Una reserva y ningún fallo: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los escenarios de la tabla anterior pasan, con el verificador probado con documentos de ejemplo.
- [ ] Sobre el árbol real termina en 0 con «exigidos 0» y «pendientes 162», y con `HDU-001` añadida en la rama de ensayo falla listando sus 27 escenarios.
- [ ] `python tools/verificar_docs.py` en verde, con 162 escenarios.
- [ ] ADR de la política del verificador escrito, con su entrada en el índice.
- [ ] Auditoría de arquitectura, de código y de documentación sin hallazgos abiertos.

## Preguntas abiertas y supuestos

De la [spec común](../tkt-009/spec.md#preguntas-abiertas-y-supuestos), los que toca este ticket: `A-6`, `A-7` y `A-8`, resueltos en el diseño.

## Pasada adversarial

La de la [spec común](../tkt-009/spec.md#pasada-adversarial) y la del [diseño común](../tkt-009/design.md#pasada-adversarial). La partición no añade objeciones.

## Contexto técnico

El de la [spec común](../tkt-009/spec.md#contexto-técnico). Filas C1 a C6 del [diseño común](../tkt-009/design.md#parte-c--verificador-de-escenarios); todas en `haiku`.
