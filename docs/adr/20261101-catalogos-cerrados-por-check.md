# Los conjuntos cerrados se declaran con `CHECK` con nombre, no con `ENUM`

## Estado

Aceptado

## Contexto y problema

El esquema del módulo `presupuesto` tiene nueve columnas con conjuntos cerrados de valores: el estado y el tipo de contrato de la obra, la unidad de concepto y de insumo, el tipo de insumo, el tipo de cargo del APU, el estado de la línea base, el estado de la importación y el tipo de error de importación. Todas las declara el borrador de la API como enumeración cerrada, y la unidad además es un invariante del modelo de datos (invariante 27).

El modelo de datos (§2) dice que los conjuntos cerrados y estables se declaran como tipo `ENUM` de PostgreSQL, y la migración `0003` ya usa uno para `accion_bitacora`. Sin embargo, la especificación de TKT-011 exige que cada rechazo por un valor fuera del conjunto responda un único `SQLSTATE` y nombre la restricción infractora (criterio CA-8, que cubre seis de esas columnas, y la Definition of Done del ticket: el nombre de la restricción en cada rechazo). Las nueve columnas necesitan, por tanto, un mecanismo que el motor responda de forma uniforme y con nombre.

El esquema tiene además que poder cambiarse. Un conjunto que hoy tiene siete valores puede ganar uno o perder otro, y la migración que lo cambie tiene que ser reversible.

## Opciones consideradas

* **`CHECK (columna IN (…))` con nombre `ck_<tabla>_<columna>`, sobre una columna `text NOT NULL`.** El motor responde `23514` (`check_violation`) y `diag.constraint_name` lleva el nombre de la restricción.
* **Tipo `ENUM` de PostgreSQL.** El motor responde `22P02` (`invalid_text_representation`), y el mensaje no trae el nombre de ninguna restricción. El experimento E-7 comprobó que el código no depende de cómo envía el cliente el valor, pero tampoco nombra la restricción. Ampliar el tipo con `ALTER TYPE … ADD VALUE` no tiene inverso: PostgreSQL no ofrece `DROP VALUE`, así que una migración que se revierte no puede deshacer la ampliación.
* **Tabla de catálogo con clave foránea.** Permite que el conjunto crezca sin migración, pero los conjuntos de este ticket no los amplía el cliente: los fija la especificación y el borrador de la API. Una tabla añadiría joins, una clave foránea por columna y un catálogo que sembrar, sin que ningún usuario lo edite.

## Decisión

Se elige el **`CHECK (columna IN (…))` con nombre `ck_<tabla>_<columna>`, sobre `text NOT NULL`** porque:

* Cada rechazo responde `23514` y nombra la restricción, lo que permite que la prueba afirme el `SQLSTATE` y el nombre, como exige la Definition of Done de TKT-011.
* Las nueve columnas usan el mismo mecanismo que la unidad, que ya es un `CHECK` por el invariante 27. Así el módulo tiene un solo modo de cerrar un conjunto, y no dos.
* Sustituir un `CHECK` es reversible dentro de una migración: se quita la restricción antigua y se añade la nueva en la bajada y en la subida.
* El ORM mapea una columna `text` sin declarar un tipo propio en la base.

El `ENUM` de `accion_bitacora` se mantiene como excepción histórica: la migración `0003` ya lo creó y cambiarlo requeriría reescribir una tabla que ya tiene datos de auditoría. La convención de `docs/03-modelo-datos.md` (§2) se actualiza para decir cuándo se usa cada mecanismo.

Una tabla de catálogo se sigue usando cuando el cliente puede ampliar el conjunto.

## Consecuencias

**Positivas**

* Los rechazos por valor fuera de un conjunto cerrado son uniformes: `23514` y el nombre de la restricción, en todas las columnas del módulo que lo usan.
* Ampliar o reducir un conjunto es una migración que se revierte, sin el límite de `ALTER TYPE`.
* Las pruebas de rechazo afirman el mismo `SQLSTATE` para todos los conjuntos, lo que facilita leerlas y mantenerlas.

**Negativas o costes aceptados**

* Conviven dos mecanismos en el esquema: `ENUM` en `accion_bitacora` y `CHECK` en el resto. Quien lea el esquema tiene que conocer la excepción, y por eso queda escrita en el modelo de datos.
* Los diagramas del modelo de datos siguen usando la palabra `enum` para nombrar un conjunto cerrado. El modelo lo aclara en su §2, pero el tipo físico de esas columnas es `text`.
* Cambiar un conjunto exige reemplazar la restricción. Al añadirla de nuevo, PostgreSQL valida toda la tabla, así que en una tabla con mucho volumen la migración tarda más. Las tablas de este módulo nacen vacías, así que el coste es nulo mientras no se cambie un conjunto con datos cargados.
* Una columna `text` acepta cualquier cadena si la restricción se quita a mano. El `CHECK` protege lo que el motor evalúa, no a quien tiene el rol de migración.

**Evidencia del mecanismo**

El experimento E-7 del diseño de TKT-011 compara los dos mecanismos. Su estado es el siguiente:

* **Lado `CHECK`.** La prueba `test_tkt057_ca08_un_exito_sin_credenciales_verificadas_lo_rechaza_la_base` (TC-10 de TKT-057) afirma que un `CHECK` con nombre responde `23514` y que `diag.constraint_name` es el de la restricción. Esa prueba es la evidencia del comportamiento en el pipeline.
* **Lado `ENUM`.** El experimento E-7 se ejecutó el 2026-11-01 contra un contenedor `postgres:18.6` con psycopg 3.3.6 (fila A0 de TKT-011a). Un valor ajeno en una columna `ENUM` respondió `22P02` con `constraint_name` nulo, tanto con parámetro de servidor como con literal y con parámetro con conversión explícita; el mismo valor en una columna `text` con `CHECK` nombrado respondió `23514` con el nombre de la restricción. El código del `ENUM`, por tanto, no depende de cómo envía el cliente el valor, aunque no nombra la restricción.
* **Reversibilidad de `ALTER TYPE … ADD VALUE`.** La falta de `DROP VALUE` proviene de la documentación de PostgreSQL, no de un experimento propio.

Los resultados de E-1 a E-11 están en [impl de TKT-011a](../../sdd/tickets/tkt-011/impl.md#experimentos-previos-fila-a0).

**Cuándo revisar esta decisión**

* Si un conjunto cerrado pasa a ser editable por el cliente, se migra a una tabla de catálogo.
* Si el experimento E-7 muestra que un `ENUM` nombra la restricción en el mensaje de error, la ventaja que motivó la elección desaparece y se reabre la decisión.
* Si una versión de PostgreSQL permite quitar valores de un `ENUM` sin reescribir la tabla, se revisa la alternativa.
