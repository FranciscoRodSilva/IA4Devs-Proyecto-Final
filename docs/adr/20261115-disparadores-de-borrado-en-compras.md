# Una requisición solo se borra en borrador: dos disparadores con `IN002` y no la revocación de `DELETE`

## Estado

Aceptado

## Contexto y problema

El esquema de `compras` (TKT-019) tiene que decidir quién puede borrar una requisición. El borrador del API publica `eliminar_borrador_requisicion` (`204`) y [HDU-002](../04-historias-usuario.md) escenario 2 exige que un borrador se pueda eliminar. Pero una requisición `EVALUADA` ya consume presupuesto ([RN-03](../01-descripcion-producto.md)): si el rol de aplicación pudiera borrarla, su importe volvería al disponible y dos requisiciones simultáneas pasarían las dos. Un privilegio de PostgreSQL no distingue estados: o el rol puede borrar la fila o no puede.

La convención de [`conv-sql-postgres`](../../.claude/skills/conv-sql-postgres/SKILL.md) dice que los disparadores no implementan reglas de negocio. La única excepción hasta ahora son los de inmutabilidad y el del invariante 14, que protegen estructura. Elegir un disparador por estado obliga a decidir si este caso es otra excepción de estructura o una regla escondida en la base.

## Opciones consideradas

* **A. Revocar `DELETE` sobre `requisicion` y `requisicion_renglon`, y que el borrador se cancele.** El motor no tendría ningún borrado posible, sin disparadores. Exige quitar `eliminar_borrador_requisicion` del borrador del API, cambiar HDU-002 escenario 2 y añadir `BORRADOR → CANCELADA` a la máquina de estados de [modelo de datos §14](../03-modelo-datos.md), que hoy no la tiene. Un borrador cancelado conservaría su folio.
* **B. Conceder `DELETE` y rechazarlo con dos disparadores `BEFORE DELETE` que solo dejan pasar un `BORRADOR`.** El rol de aplicación conserva el privilegio, y `trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador` lo rechazan con `SQLSTATE` `IN002` si la requisición no está en `BORRADOR`. El del renglón lee la requisición con `FOR SHARE`, como el invariante 14, para que un borrado no se cuele mientras otra transacción cambia el estado.

## Decisión

Se elige **la opción B** porque:

* Respeta el contrato ya publicado, HDU-002 escenario 2 y la máquina de estados, sin reabrir tres artefactos que la opción A obliga a cambiar fuera del ticket.
* Un borrador no consume presupuesto, así que borrarlo no toca el `consumido` de [RN-03](../01-descripcion-producto.md); lo que protege el disparador es que una `EVALUADA` nunca devuelva su importe al disponible.
* No decide ninguna regla. Protege estructura, igual que el invariante 14: el caso de uso sigue comprobando el estado y respondiendo `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION`, y el disparador solo detiene lo que llegue por otra vía. El `SQLSTATE` `IN002` está libre en el repositorio (solo existe `IN001`, de `RN-01`).

## Consecuencias

**Positivas**

* El motor impide borrar una requisición que ya consume, aunque el código de aplicación tenga un defecto.
* El borrador del API y HDU-002 escenario 2 no cambian.
* La concurrencia entre borrar un renglón y evaluar la requisición queda cubierta por una prueba determinista sin `sleep` (TC-26 de TKT-019).

**Negativas o costes aceptados**

* Un borrador que ya tenía folio y se borra deja un hueco en la numeración. D-15 de TKT-019 hace nulable el folio solo en `BORRADOR` y deja a TKT-021 o TKT-023 decidir cuándo se numera; si es al crear, el contrato `Requisicion.folio` y la regla de folios sin huecos cambian y deben registrarse allí.
* El disparador decide por el estado actual y nada en el motor limita las transiciones: quien tenga `UPDATE` podría devolver una requisición numerada a `BORRADOR` y borrarla. La máquina de estados de §14 lo prohíbe y debe hacerlo cumplir el caso de uso de TKT-021 o TKT-023.
* Añade una excepción a la convención «los disparadores no implementan reglas», registrada en `conv-sql-postgres` y en `desarrollador-sql`.
* El traductor de `IN002` a `409` vive en `compras`: el de `presupuesto` solo conoce `IN001` y `compras` no puede importarlo.

**Cuándo revisar esta decisión**

* Si aparece un segundo disparador de `compras` que decida por estado, porque la excepción dejaría de ser un caso aislado.
* Si TKT-021 o TKT-023 deciden numerar la requisición al crearla y el hueco de los borradores borrados resulta inaceptable: entonces la opción A, con el borrador cancelado, vuelve a ser la candidata.
