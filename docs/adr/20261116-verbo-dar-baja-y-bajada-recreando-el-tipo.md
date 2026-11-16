# El verbo `DAR_BAJA` de la bitácora entra con `ADD VALUE` y su bajada recrea el tipo tras una guarda

## Estado

Aceptado

## Contexto y problema

La baja de un proveedor (TKT-029b) se asienta en la bitácora con un verbo propio, `DAR_BAJA`, que hoy no existe en el `ENUM` `accion_bitacora`. La bitácora es de solo anexado y permanente ([RN-04](../01-descripcion-producto.md), invariante 10 del [modelo de datos](../03-modelo-datos.md)): ningún asiento se edita ni se borra. Eso condiciona la migración que añade el verbo, porque toda migración de este repositorio debe poder bajarse, y PostgreSQL no permite quitar un valor de un `ENUM` sin recrear el tipo.

Hay además una limitación de la subida. `ALTER TYPE … ADD VALUE` no deja usar el valor nuevo en la transacción que lo añade: PostgreSQL responde `55P04` (`unsafe use of new value`). Como `env.py` corre todas las migraciones de un `upgrade head` en una sola transacción, la restricción alcanza a cualquier migración posterior que se aplique en esa misma ejecución.

La pregunta es qué debe hacer la bajada de la migración `0016`: negarse siempre, dejar el verbo en el tipo o recrear el tipo sin él.

## Opciones consideradas

* **A. Bajada que se niega siempre.** No toca la bitácora y nunca puede perder un asiento. Pero deja la migración sin reversa, y el proyecto exige que toda migración se baje y se vuelva a subir.
* **B. Bajada que deja el valor en el tipo.** No reescribe la tabla. Pero tras bajar, `DAR_BAJA` sigue existiendo en la base, el criterio `CA-R1` de TKT-029b («el verbo deja de existir tras bajar») se incumple y el tipo de la base deja de coincidir con `AccionBitacora` y con el borrador de la API.
* **C. Bajada que recrea el tipo tras una guarda.** La guarda bloquea la tabla y se niega con `RAISE EXCEPTION` si existe algún asiento `DAR_BAJA`; si no existe ninguno, la bajada renombra el tipo, crea otro con los 22 verbos de `0003` en su orden, convierte la columna con `USING accion::text::accion_bitacora` y borra el tipo antiguo.

## Decisión

Se elige **la opción C**, porque es la única que cumple `CA-R1` y a la vez respeta que la bitácora es permanente. La guarda impide que la conversión pierda un asiento `DAR_BAJA`, y sin asientos el tipo vuelve exactamente al de `0003`.

La subida añade `DAR_BAJA` al final del tipo, sin `IF NOT EXISTS` (un valor ya presente es un defecto que debe fallar) y sin `BEFORE` ni `AFTER`, para que el orden del tipo coincida con el de `AccionBitacora` y con el borrador.

## Consecuencias

**Positivas**

* La migración es reversible y la bajada deja el esquema como estaba antes de `0016`.
* La guarda se niega antes de tocar el tipo, así que una bajada con asientos `DAR_BAJA` no pierde nada.

**Negativas o costes aceptados**

* La bajada reescribe físicamente la columna `bitacora.accion`, la tabla de solo anexado, con el rol de migración y bajo `ACCESS EXCLUSIVE`. No cambia ningún valor ni ningún privilegio: el tipo nuevo conserva el `USAGE` por omisión y `ALTER COLUMN … TYPE` no toca la ACL de `bitacora`. La prueba TC-04 compara las filas y los privilegios antes y después.
* Con asientos `DAR_BAJA` la bajada se niega y exige respaldar la base con `pg_dump` y decidir con la persona dueña antes de cualquier intervención manual. En un entorno donde ya se dio de baja a un proveedor, la reversa de `0016` deja de ser automática.
* Ninguna migración posterior a `0016` que se aplique en el mismo `upgrade head` puede usar `DAR_BAJA`: fallaría con `55P04`. La docstring de la migración lo advierte para el siguiente ticket.

**Evidencia**

La sonda del supuesto 5 del diseño de TKT-029b, ejecutada el 2026-11-15 contra un PostgreSQL 17 desechable, comprobó tres hechos:

1. `ADD VALUE` seguido de un `INSERT` del valor nuevo en la misma transacción falla con `unsafe use of new value`.
2. Tras `COMMIT`, el `INSERT` del valor nuevo funciona.
3. Recrear el tipo sin el valor y convertir la columna con `USING accion::text::accion` falla con `invalid input value for enum` cuando existe una fila con el valor nuevo, lo que justifica la guarda.

Las pruebas TC-03 (la sonda repetida con el PostgreSQL de las pruebas y el rol de migración real), TC-04 (la bajada conserva filas y privilegios) y TC-05 (la bajada se niega con asientos `DAR_BAJA`) lo comprueban en cada ejecución.

**Cuándo revisar esta decisión**

* Si una migración futura necesita usar `DAR_BAJA` en el mismo `upgrade head`, porque habría que partir la ejecución en transacciones distintas.
* Si PostgreSQL admite quitar valores de un `ENUM`, porque la bajada dejaría de necesitar la reescritura de la tabla.
