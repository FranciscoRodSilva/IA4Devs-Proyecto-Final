# El código de obra es único por el índice `uq_obra_codigo` y el alta traduce su `23505`, sin comprobación previa

## Estado

Aceptado

## Contexto y problema

El alta de una obra (TKT-012a) tiene que rechazar un código que ya existe. Lo exige `HDU-001` esc. 3, y el diseño del ticket lo desdobla en dos criterios: `CA-2`, el código duplicado en dos altas sucesivas, y `CA-3`, la carrera de dos altas simultáneas con el mismo código. En el segundo caso, ninguna lectura previa sirve: las dos transacciones ven el código libre y las dos intentan insertar.

El índice único `uq_obra_codigo` existe desde la migración `0006`, de modo que el motor ya impide la duplicación. Queda decidir quién da la respuesta al cliente y con qué forma: un `409` `CONFLICTO` con el código `CODIGO_OBRA_DUPLICADO`, que lleva la obra existente y la acción `VER_OBRA`, y no un `500` por un `IntegrityError` sin traducir.

Se suman dos decisiones del mismo caso de uso. La primera es si el código se compara tal como llega o normalizado: `ap-058-25`, con un espacio al final, y `AP-058-25` son la misma obra para quien la nombra. La segunda es dónde se comprueba el rango de 0 a 1 de la retención de destajo y del fondo de garantía (`PA-02`) y el umbral de alerta no negativo (`PA-18`). Los `CHECK` de la migración `0006` ya lo imponen en la base, pero una violación llegaría como `23514`, un `SQLSTATE` que nadie traduce, y el cliente recibiría un `500`.

[ADR-031](20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) fijó que la traducción del `SQLSTATE` del motor vive en un solo punto, `cimenta/presupuesto/aplicacion/traduccion_motor.py`. Ese módulo cubre `IN001` y el `23505` de la línea base congelada, pero no el de `uq_obra_codigo`.

## Opciones consideradas

**Quién arbitra la unicidad**

* Una comprobación previa: un `SELECT` por código antes del `INSERT`. No cierra la carrera, porque entre la lectura y la escritura otra transacción puede insertar, y añade una consulta a cada alta. Habría que mantener además la traducción del `23505` para el caso de la carrera, con lo que se duplicaría el camino.
* Un bloqueo consultivo (`pg_advisory_xact_lock`) sobre el código. Cierra la carrera, pero introduce un mecanismo nuevo que el índice ya hace innecesario, y que solo protege mientras todo escritor lo tome.
* El índice único como único árbitro: se inserta sin mirar y se traduce el `23505` de `uq_obra_codigo` a `409` `CODIGO_OBRA_DUPLICADO`. Cubre la carrera y el caso sucesivo con el mismo código y sin consulta adicional en el camino feliz.

**Dónde se traduce el `23505`**

* En `traduccion_motor.py`, el módulo compartido de TKT-017. Mantendría la traducción en un solo punto, pero obliga a tocar el módulo y las pruebas de otro ticket para un rechazo que solo existe en el alta de obra.
* Localmente, en `aplicacion/obras.py`, antes de delegar en `traducir_error_del_motor` el resto de los `SQLSTATE`.

**Normalización del código**

* Igualdad exacta: se guarda lo que llega. `ap-058-25`, con un espacio al final, y `AP-058-25` serían dos obras distintas.
* Solo recortar los espacios.
* Recortar y pasar a mayúsculas, como la clave de insumo de TKT-014 (descripción recortada, en mayúsculas y con los espacios interiores colapsados, decisión de 2026-11-03). La `A2` de 2026-11-02 partía de un código que no existe y quedó sustituida. La persona dueña lo aprobó como `D-1` el 2026-11-10.

**Rango de los porcentajes**

* Dejarlo solo a los `CHECK` de la base. La violación llega como `23514`, sin traducir, y responde `500`.
* Una expresión regular en el DTO. Cambiaría el patrón que publica el borrador OpenAPI y esconde la regla `PA-02` en una cadena difícil de probar.
* Una función pura en `dominio/obra.py` que devuelve los parámetros fuera de rango, y un caso de uso que lanza `ValidacionRechazada` con `FUERA_DE_RANGO` antes de abrir la transacción. Se prueba sin base de datos y admite mutantes.

## Decisión

Se elige **el índice `uq_obra_codigo` como único árbitro, con la traducción local de su `23505`, la normalización de `D-1` y el rango en una función de `dominio/`**, porque:

* **Es la única opción que cierra la carrera de `CA-3`.** Solo el motor sabe, en el instante de escribir, si el código ya está. Una lectura previa no puede saberlo, y por eso el caso de uso no hace ninguna comprobación antes del `INSERT`. `crear_obra` inserta y, si el motor responde `23505` con `constraint_name` igual a `uq_obra_codigo`, lee la obra existente con `leer_obra_por_codigo` y lanza `ConflictoEstado` con el código `CODIGO_OBRA_DUPLICADO`, el detalle `obra_existente_id` y `obra_existente`, y la acción `VER_OBRA`. Si la obra ya no se encuentra, relanza el error original en lugar de inventar una respuesta.
* **La traducción es local porque solo existe aquí.** El `23505` de `uq_obra_codigo` no pertenece al ciclo de la línea base que [ADR-031](20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) y TKT-017 traducen, y tocar `traduccion_motor.py` obligaría a reabrir un módulo y unas pruebas ajenas a este ticket. Los demás `SQLSTATE` del alta (`55P03`, `57014` y los otros `23505`) siguen delegándose en `traducir_error_del_motor`.
* **El código se guarda recortado y en mayúsculas.** `normalizar_codigo_obra` devuelve `codigo.strip().upper()`, así que la unicidad no depende de cómo se escriba (`D-1`, aprobado). Con el índice sobre el valor normalizado, `ap-058-25` choca con `AP-058-25`.
* **El rango vive en `dominio/obra.py`.** `porcentajes_fuera_de_rango` implementa `PA-02` y `PA-18` con `Porcentaje`, devuelve los parámetros en un orden fijo y no lanza nada. El caso de uso lanza `ValidacionRechazada` antes de abrir la transacción, con el `campo` del parámetro y el código `FUERA_DE_RANGO`. Los `CHECK` de la migración `0006` quedan como segunda barrera, no como la primera.

## Consecuencias

**Positivas**

* La carrera de dos altas simultáneas con el mismo código termina siempre igual: una inserta y la otra recibe `409` `CODIGO_OBRA_DUPLICADO`, sin ventana de lectura previa. La prueba de concurrencia de `CA-3` fuerza el solapamiento con `pg_blocking_pids` en lugar de confiar en un `Barrier`.
* El camino feliz del alta no paga ninguna consulta de unicidad.
* Un porcentaje fuera de rango responde `422` con su campo, no `500`, y la regla se prueba sin base de datos.
* No se reabre `traduccion_motor.py` ni las pruebas de TKT-017.

**Negativas o costes aceptados**

* **La extracción del `SQLSTATE` y del `constraint_name` se duplica.** `_es_codigo_duplicado` en `aplicacion/obras.py` repite lo que hace `traduccion_motor.py` con `error.orig.sqlstate` y `error.orig.diag.constraint_name`. `auditor-codigo` lo señaló como el hallazgo F002. Se acepta como deuda hasta un ticket de limpieza que extraiga un auxiliar común.
* **Se desvía una consecuencia de ADR-031.** Ese ADR dice que «la traducción vive en un solo punto». Con este, hay una segunda traducción local del `23505`, la de `uq_obra_codigo`, que [ADR-031](20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) no cubre: este ADR lo completa y no lo sustituye. Quien busque dónde se traduce un `SQLSTATE` del presupuesto tendrá que mirar en `traduccion_motor.py` y en `aplicacion/obras.py`.
* **Cada duplicado deja un `IntegrityError` capturado en el registro técnico.** Es una excepción traducida, no un `500`, y el diseño lo aceptó en la objeción 3 de su pasada adversarial: una comprobación previa evitaría el ruido, pero añadiría una consulta y no cerraría la carrera.
* **Un cuerpo con defectos de forma y de rango informa solo los de forma.** Pydantic valida la forma antes de que el caso de uso compruebe el rango, igual que en TKT-017. Se registró en la objeción 4 del diseño.
* **El alta lee la obra existente en una transacción aparte**, porque la del `INSERT` ya falló. Si la obra duplicada desaparece entre las dos, el error original se relanza y responde `500`: un caso que hoy no puede darse, porque ninguna ruta borra obras.

**Cuándo revisar esta decisión**

* Si un tercer caso de uso necesita traducir el `23505` de otra restricción de unicidad, se extrae el auxiliar común y se mueve la traducción a `traduccion_motor.py`.
* Si el negocio pide que el código distinga mayúsculas de minúsculas o conserve su forma original, se reabre `D-1` y el índice cambia.
* Si el registro técnico se llena de `IntegrityError` por duplicados y estorba la vigilancia de Sentry, se reconsidera la comprobación previa como complemento, no como sustituto.
