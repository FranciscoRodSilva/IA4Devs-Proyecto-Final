# El borrado de una obra sin historial es físico y se asienta con un verbo nuevo, `ELIMINAR`

## Estado

Aceptado

## Contexto y problema

TKT-012b permite eliminar una obra que todavía no tiene historial: ninguna línea base, ninguna importación, ninguna fila propia de otras tablas de la obra y ningún movimiento de los módulos posteriores ([RN-01](../01-descripcion-producto.md), HDU-001 esc. 20). Dos preguntas piden una decisión.

La primera es cómo desaparece la obra. El proveedor nunca se borra: se le da de baja ([TKT-029b](20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md)). La obra, en cambio, lleva una restricción `uq_obra_codigo` que impide reutilizar un código mientras la fila exista. Una obra creada por error, sin historial, retendría su código para siempre si solo se marcara como borrada.

La segunda es con qué verbo se asienta el borrado en la bitácora. La bitácora es de solo anexado y permanente ([RN-04](../01-descripcion-producto.md), invariante 10 del [modelo de datos](../03-modelo-datos.md)), y su `ENUM` `accion_bitacora` es cerrado. El asiento sobrevive a la obra porque `bitacora.obra_id` no lleva clave foránea.

Añadir un verbo trae las mismas dos limitaciones que ya resolvió `0016`: `ALTER TYPE … ADD VALUE` no deja usar el valor en la transacción que lo añade (`55P04`), y PostgreSQL no permite quitar un valor de un `ENUM` sin recrear el tipo.

## Opciones consideradas

* **A. Borrado lógico** (una columna de estado o de borrado en `obra`). No destruye nada, pero el código queda retenido por `uq_obra_codigo` para siempre, y relajar esa unicidad con un índice parcial abre una segunda fuente de verdad sobre qué obras existen. Además, toda consulta tendría que filtrar las obras borradas.
* **B. Borrado físico asentado con un verbo existente** (`CANCELAR`, `ANULAR` o `DESCARTAR`). No toca el tipo, pero cada uno significa otra cosa en el sistema: los tres nombran operaciones sobre un registro que se conserva, y ninguno dice que la fila dejó de existir. Quien lea la bitácora no distinguiría un borrado físico de esas operaciones.
* **C. Borrado físico asentado con un verbo propio, `ELIMINAR`.** El `DELETE` solo procede cuando `hay_historial` es falso, y el asiento, que conserva la fotografía de la obra en `datos_antes`, se escribe antes del `DELETE` en la misma transacción. La migración `0017` sigue el molde de `0016`.

## Decisión

Se elige **la opción C**. El borrado es físico porque libera el código y porque una obra sin historial no tiene nada que conservar; el asiento `ELIMINAR` conserva el código, el nombre y los parámetros de la obra, que es lo único que debe sobrevivir. El verbo es propio porque ningún verbo existente significa «borrado físico».

La subida de `0017` añade `ELIMINAR` al final del tipo, sin `IF NOT EXISTS` y sin `BEFORE` ni `AFTER`, y no usa el valor. La bajada, calcada de `0016`, bloquea `bitacora` con `ACCESS EXCLUSIVE`, se niega con `RAISE EXCEPTION` si existe algún asiento `ELIMINAR` y, si no existe ninguno, renombra el tipo, crea otro con los 23 verbos de `0016` en su orden, convierte la columna con `USING accion::text::accion_bitacora` y borra el tipo antiguo.

## Consecuencias

**Positivas**

* El código de una obra borrada queda libre para un alta nueva.
* El verbo dice lo que ocurrió: quien lee la bitácora distingue un borrado físico de una cancelación, una anulación o un descarte.
* La migración es reversible mientras no exista ningún asiento `ELIMINAR`.

**Negativas o costes aceptados**

* La bajada reescribe físicamente la columna `bitacora.accion` bajo `ACCESS EXCLUSIVE`, sin cambiar valores ni privilegios, como ya ocurre con `0016`.
* Con asientos `ELIMINAR` la bajada se niega: hay que respaldar con `pg_dump` y decidir con la persona dueña antes de cualquier intervención manual. La bajada de `0017` se ejecuta antes que la de `0016`, por el orden de Alembic.
* Ninguna migración posterior a `0017` que se aplique en el mismo `upgrade head` puede usar `ELIMINAR`: fallaría con `55P04`.
* El borrado físico es irreversible para la obra; solo queda el asiento. Por eso el caso de uso exige que `hay_historial` sea falso bajo `SELECT … FOR UPDATE` de la fila de la obra, y las claves foráneas `ON DELETE RESTRICT` son la última barrera.

**Cuándo revisar esta decisión**

* Si una migración futura necesita usar `ELIMINAR` en el mismo `upgrade head`.
* Si el negocio decide conservar las obras borradas por auditoría más allá de su asiento, caso en que el borrado lógico vuelve a ser la opción.
* Si PostgreSQL admite quitar valores de un `ENUM`, porque la bajada dejaría de necesitar la reescritura de la tabla.
