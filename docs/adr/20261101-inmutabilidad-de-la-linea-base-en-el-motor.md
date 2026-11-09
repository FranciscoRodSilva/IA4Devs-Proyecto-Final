# La inmutabilidad de la línea base la impone el motor, con disparadores que rechazan con un `SQLSTATE` propio

## Estado

Aceptado

## Contexto y problema

El invariante 14 del [modelo de datos](../03-modelo-datos.md#13-invariantes-en-base-de-datos) dice que una línea base congelada no se altera, y `RN-01` la declara inmutable: es el principio no negociable 1 del producto. El [ADR de copia física](20260918-snapshot-linea-base.md) fijó que un disparador rechaza `UPDATE` y `DELETE` sobre las tablas de copia. Ese texto se queda corto en tres puntos.

* **No nombra el `INSERT`.** Una copia que entra después del congelado cambia una línea base que ya no debería cambiar. El disparador tiene que leer el estado de la línea base antes de aceptar cualquier escritura sobre sus copias.
* **No dice nada de la fila `linea_base`.** El congelado necesita `UPDATE` sobre esa fila. Si el rol de aplicación pudiera devolverla a `BORRADOR`, reabriría sus copias. El privilegio no distingue el congelado de una reapertura, así que hace falta un disparador que fije las transiciones.
* **Los privilegios no son uniformes.** El rol de aplicación conserva `INSERT` sobre las tres tablas, y `UPDATE` sobre `linea_base` y `explosion_presupuesto`, porque `SELECT … FOR UPDATE` lo exige ([ADR-004](20260918-bloqueo-pesimista-presupuesto.md)). Sobre `linea_base_concepto` le quita `UPDATE` y `DELETE`. Sobre `explosion_presupuesto` conserva además `DELETE`, así que ahí el disparador es la única barrera.

El rechazo lo traduce [TKT-017](../05-tickets-trabajo.md) a una respuesta de la API. Por eso el código del error tiene que llegar al cliente como un `SQLSTATE` que se pueda identificar sin leer el texto del mensaje.

## Opciones consideradas

**Forma de la protección**

* Dos funciones de disparador, una para las copias (`linea_base_concepto` y `explosion_presupuesto`) y otra para `linea_base`, cada una con su `SQLSTATE` propio.
* Un único disparador que reúna las tres tablas.
* Solo privilegios, sin disparador. No basta: el rol de aplicación necesita `UPDATE` sobre `explosion_presupuesto` para el bloqueo pesimista, y con ese privilegio el motor no distingue una copia congelada de una activa.

**Código del rechazo**

* `P0001`, el que emite un `RAISE EXCEPTION` sin código. Lo comparte cualquier bloque `DO` y cualquier función, así que TKT-017 tendría que distinguir el rechazo por el texto del mensaje.
* Un código de la clase `23` (por ejemplo `23C01`). La clase pertenece a PostgreSQL y puede recibir códigos nuevos en una versión futura.
* `CM001`, de la clase `CM`. Su primera letra, la `C`, cae entre la A y la H, rango que el estándar SQL reserva para sí. El experimento de la fila A0 lo confirmó en la base, que lo acepta, pero una clase estándar futura podría chocar con él.
* `RN001`. Cae en el rango de la implementación, pero la persona dueña eligió `IN001`.
* `IN001`, de la clase `IN` (de «inmutable»). La `I` está en el rango que deja el estándar a la implementación, y PostgreSQL 18.6 no usa ninguna clase que empiece por `IN`.

**Lectura del estado antes de escribir una copia**

* `FOR SHARE` sobre la fila de la línea base. La inserción espera a la transacción que congela y relee la fila ya confirmada.
* Aceptar la carrera. Una copia insertada en paralelo con el congelado lee `BORRADOR` y entra después de que el congelado se confirme.

**`TRUNCATE`**

* `BEFORE TRUNCATE` que rechace la sentencia. Descartado: `TRUNCATE` no dispara los disparadores de fila, y un disparador de sentencia añadiría una pieza más sin cerrar nada. Solo lo ejecutaría el rol de migración, que es dueño de las tablas y superusuario, y puede desactivar o borrar cualquier disparador.

## Decisión

Se elige **la protección en el motor con dos funciones de disparador y un `SQLSTATE` propio, `IN001`**, porque:

* **Cubre `INSERT`, `UPDATE` y `DELETE` sobre las copias** (`presupuesto_proteger_copia_congelada()`, disparadores `trg_linea_base_concepto_inmutable` y `trg_explosion_presupuesto_inmutable`). Cada escritura lee la línea base con `FOR SHARE` y rechaza si no está en `BORRADOR`.
* **Fija las transiciones de la línea base** (`presupuesto_proteger_linea_base()`, `trg_linea_base_solo_avanza`). La fila solo avanza de `BORRADOR` a `CONGELADA` y de `CONGELADA` a `SUPERSEDIDA`. Desde `CONGELADA`, la comparación de la fila sin su estado con `to_jsonb` impide cualquier otro cambio, también en columnas que añada una migración futura.
* **Usa `FOR SHARE` para que la carrera no se cuele.** Sin él, una copia concurrente entra después del congelado.
* **Rechaza con `IN001`**, con el mensaje que empieza por `RN-01:`, y rellena `CONSTRAINT` y `TABLE`. El cliente recibe el nombre del disparador en `diag.constraint_name`, igual que con una restricción.
* **No añade `BEFORE TRUNCATE`.** El [diseño de TKT-011](../../sdd/tickets/tkt-011/design.md) acepta ese límite como `PA-T15`: el dueño del esquema puede retirar cualquier garantía, y eso lo cubre la disciplina de acceso al rol de migración.
* **Quita `UPDATE`, `DELETE` y `TRUNCATE` a `cimenta_aplicacion` sobre `linea_base_concepto`.** Es una segunda barrera: si alguien desactiva el disparador, el rol de aplicación sigue sin poder modificar la copia.

La prueba del disparador se ejecuta con el rol de migración, que sí tiene el privilegio, para que el permiso no tape al disparador. La prueba del permiso se ejecuta con el rol de aplicación.

## Consecuencias

**Positivas**

* Un `psql` o un script con el rol de aplicación no altera una copia congelada. Sobre `linea_base_concepto` lo impiden el disparador y el privilegio; sobre `explosion_presupuesto`, el disparador.
* La línea base solo puede avanzar en el motor. Nada de la aplicación puede devolverla a `BORRADOR` ni reabrir sus copias.
* El rechazo es uniforme: `IN001`, con el prefijo `RN-01:` y el nombre del disparador en `diag.constraint_name`.
* Las pruebas de TKT-011b comprueban estos comportamientos con el `SQLSTATE` y el nombre, no con el texto del mensaje.

**Negativas o costes aceptados**

* **TKT-017 tiene que traducir varios códigos**, no solo este. `IN001` se traduce a `409` `REGLA_NEGOCIO` con `regla` `RN-01` `(asumido)`. Además llegan `23505` (una segunda línea base `CONGELADA` por obra, o una `CONGELADA` que no pasa a `SUPERSEDIDA` antes de congelar la nueva), `23503` (una copia que apunta a una línea base o a un concepto inexistente) y `23001` (borrar un padre con hijos, porque la clave foránea es `ON DELETE RESTRICT`; la fila A2 comprobó que PostgreSQL responde `23001` y no `23503`).
* **El `FOR SHARE` exige `UPDATE` sobre `linea_base` para el rol de aplicación**, y respeta el `lock_timeout` de ese rol. Una transacción larga que modifique la línea base hace fallar la inserción de copias con `55P03`, en lugar de esperar sin fin (E-9).
* **Las copias solo se escriben en la transacción del congelado.** El rol de aplicación no tiene `DELETE` sobre `linea_base_concepto`, así que una copia escrita en un `BORRADOR` no se puede retirar después. Si el congelado falla, la transacción no deja nada.
* **La traducción vive en un solo punto: `cimenta/presupuesto/aplicacion/traduccion_motor.py`** (TKT-017a3). El caso de uso envuelve su transacción en `try/except DBAPIError` y el traductor lee `error.orig.sqlstate` y `error.orig.diag.constraint_name`. Vive en `aplicacion/` y no en `contrato_error/` porque el detalle de `RN-01` necesita leer la obra, y `contrato_error/` es puro y no conoce `sqlalchemy`. La tabla:

  | `SQLSTATE` | Respuesta |
  |---|---|
  | `IN001` | `409` `REGLA_NEGOCIO` con `regla` `RN-01` («La línea base congelada no se modifica.») |
  | `23505` de `uq_linea_base_obra_id_congelada` | `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION`, con el mismo mensaje que la confirmación con congelada vigente |
  | Otro `23505`, `23503` o `23001` | `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION` y la restricción en el detalle |
  | `55P03` | `409` `CONCURRENCIA` con el código `BLOQUEO_VENCIDO` y la acción `REINTENTAR` |
  | `57014` | `409` `CONCURRENCIA` con el código `TIEMPO_EJECUCION_VENCIDO` y la acción `REINTENTAR` |
  | `22003` (un valor no cabe en su columna, por ejemplo `numeric(14,4)` en `apu.*`) | `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION`: la importación debe analizarse de nuevo |
  | Cualquier otro, incluido `42501` | Sin traducción: se relanza y responde `500` |

  El `42501` queda sin traducir a propósito: es una decisión del diseño de TKT-017 (`M-A6` la vigila). Ninguna ruta emite `UPDATE` ni `DELETE` sobre `linea_base_concepto`, así que un `42501` sería un error de programa y debe llegar como `500` a Sentry, no disfrazarse de regla de negocio.
* **La `CONGELADA` anterior pasa a `SUPERSEDIDA` antes de congelar la nueva**, en la misma transacción. Si no, el índice único parcial responde `23505`. `BORRADOR` a `SUPERSEDIDA` está prohibido.
* **La bajada de la migración `0007` se niega mientras exista una línea base `CONGELADA` o `SUPERSEDIDA`.** Así lo fija la guarda de la bajada, y el plan de reversa queda escrito en la migración. La guarda de la bajada reutiliza `IN001`; no llega a la API.
* **`SELECT … FOR UPDATE` no dispara el disparador** (E-2). El bloqueo pesimista de [ADR-004](20260918-bloqueo-pesimista-presupuesto.md) funciona sobre una línea base congelada, y el rol de aplicación ya tiene el `UPDATE` que ese bloqueo exige.
* **El coste del `FOR SHARE` por fila está medido.** La prueba `test_tkt011_ca15_e13_congelar_una_obra_real_cabe_en_el_tiempo_del_rol` inserta 5,000 copias y 300 renglones de explosión y congela en una transacción con el rol de aplicación. Según la medición de esa prueba, tardó 0.070 s, frente a los 15 s del `statement_timeout` del rol. La cifra la registra el propio test en su mensaje y en la salida de `pytest -s`; el apartado «Entrega TKT-011b» de `sdd/tickets/tkt-011/impl.md` la recogerá con la fila B2.

**Evidencia**

La decisión se apoya en los resultados de los experimentos de la fila A0, que se ejecutaron contra `postgres:18.6` con psycopg 3.3.6. Están en [`impl.md`, sección «Experimentos previos»](../../sdd/tickets/tkt-011/impl.md#experimentos-previos-fila-a0):

* **E-2.** `SELECT … FOR UPDATE` no dispara un disparador `BEFORE UPDATE` de fila.
* **E-3.** `TRUNCATE` no dispara disparadores de fila. Es el motivo para descartar `BEFORE TRUNCATE`.
* **E-4.** Un `RAISE` con `ERRCODE`, `CONSTRAINT` y `TABLE` llega a psycopg con su `sqlstate`, `constraint_name` y `table_name`. El experimento usó `CM001`, `RN001` e `IN001` por igual, así que el driver no distingue entre ellos.
* **E-9.** Con `FOR SHARE`, la inserción concurrente espera (`55P03` con `lock_timeout` corto) y luego recibe el rechazo. Sin `FOR SHARE`, la copia se cuela: 0 copias con el bloqueo, 1 sin él.
* **E-11.** `(to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado')` es falso si solo cambia `estado`, y verdadero si cambia una columna `numeric`, `timestamptz`, `uuid` o `text`.

Los tests que cubren los criterios CA-15 y CA-16 están en [`backend/tests/test_tkt011_linea_base.py`](../../backend/tests/test_tkt011_linea_base.py). Entre ellos, `test_tkt011_ca15_una_copia_concurrente_no_entra_tras_el_congelado` comprueba la carrera de E-9 sobre la base real.

**Cuándo revisar esta decisión**

* Si el negocio pide corregir una copia congelada sin crear una versión nueva, la decisión se reabre. Hoy la corrección exige una versión nueva, con su motivo.
* Si la medición de E-13 con volumen real supera el `statement_timeout` del rol de aplicación, el `FOR SHARE` por fila se sustituye por otro mecanismo y se rehacen las migraciones afectadas.
* Si una versión de PostgreSQL permite que un disparador de fila se ejecute con `TRUNCATE`, se revisa el descarte de `BEFORE TRUNCATE`.
* Si TKT-017 no puede traducir `IN001` sin leer el mensaje, se reabre el código del rechazo.
</content>
