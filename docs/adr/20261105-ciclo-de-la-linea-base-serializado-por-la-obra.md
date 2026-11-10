# El ciclo de la línea base de una obra se serializa con el bloqueo de la fila de la obra

## Estado

Aceptado

## Contexto y problema

Confirmar una importación crea la jerarquía de una obra y una línea base en `BORRADOR`; reemplazar un borrador la borra y crea otra; congelar la copia a las tablas de la línea base congelada. Las tres operaciones leen y escriben el mismo conjunto de filas de una obra, y [`RN-01`](../01-descripcion-producto.md) exige que de ese conjunto salga una sola línea base vigente. [TKT-017](../05-tickets-trabajo.md) las implementa en tres entregas y necesita un mecanismo de exclusión mutua que cubra a la vez dos carreras distintas:

* **Dos confirmaciones simultáneas de la misma obra (`CA-A10`).** Cada una lee que no hay borrador, crea su jerarquía y su línea base, y las dos terminan. Nada en el esquema impide dos filas `BORRADOR` de una misma obra, y la jerarquía duplicada solo chocaría después, contra `uq_concepto_obra_id_codigo`, con un error que nadie puede atribuir a un borrador.
* **Un reemplazo frente a un congelado (`CA-B6`, escenario 3).** El congelado copia la jerarquía mientras otra sesión la borra para sustituir el borrador. El congelado puede copiar filas que ya no existen o dejar una línea base congelada sin sus copias.

El índice único parcial `uq_linea_base_obra_id_congelada` (invariante 5) solo garantiza que no haya dos líneas base `CONGELADA` por obra. No cubre ninguna de las dos carreras. El rol de aplicación, además, lleva un `lock_timeout` de 5 s y un `statement_timeout` de 15 s (migración `v0001`), de modo que cualquier espera tiene un tope y se puede contar al cliente como un `409` de concurrencia.

## Opciones consideradas

* **Bloqueo de la fila de `obra`**: `SELECT … FOR UPDATE` sobre la obra al inicio de confirmar, reemplazar y congelar.
* **`pg_advisory_xact_lock` por obra**: un bloqueo consultivo de transacción cuya clave se deriva del identificador de la obra.
* **Confiar solo en `uq_linea_base_obra_id_congelada`** y traducir el `23505` que produce una segunda línea base congelada.
* **Índice único parcial sobre las líneas base en `BORRADOR`**, una por obra.
* **Aislamiento `SERIALIZABLE`** para estas transacciones.

## Decisión

Se elige **el bloqueo de la fila de `obra`** porque:

* **Serializa a la vez las dos carreras.** Confirmar, reemplazar y congelar toman el mismo bloqueo antes de leer las filas que protegen, así que dos confirmaciones se ejecutan una detrás de otra (`CA-A10`) y un congelado espera a que termine el reemplazo que está borrando la jerarquía, o lo precede (`CA-B6`, escenario 3). Las demás opciones cubren una de las dos o ninguna.
* **Usa un mecanismo nativo del motor y el patrón de [ADR-004](20260918-bloqueo-pesimista-presupuesto.md)**: un bloqueo de fila que respeta el `lock_timeout` del rol. Una espera que excede 5 s no cuelga la solicitud; PostgreSQL responde `55P03` y el caso de uso lo traduce a `CONCURRENCIA` con el código `BLOQUEO_VENCIDO` y la acción `REINTENTAR`.
* **La obra ya es la raíz de lo que se protege.** Toda la jerarquía y toda línea base cuelgan de `obra_id`. Bloquear su fila es bloquear exactamente el conjunto que el ciclo toca, sin una clave derivada.

El orden de adquisición es fijo y lo respeta todo caso de uso que toque estos objetos: **importación → obra → línea base → presupuesto de control**. La confirmación bloquea la importación y después la obra; el congelado lee la línea base sin bloqueo para conocer su obra, bloquea la obra y después la línea base; si esta ya no existe porque un reemplazo la borró mientras esperaba, responde que no existe. La recaptura del tope bloquea su fila de `presupuesto_control` después de los anteriores.

Las demás opciones quedan descartadas por estas razones:

* **`pg_advisory_xact_lock` por obra** resuelve lo mismo que el bloqueo de fila, pero con una clave numérica derivada del identificador que puede colisionar con la de otra obra o con otro uso del bloqueo consultivo. No aparece en `pg_locks` como una fila de `obra`, de modo que las pruebas no pueden comprobar la espera con el mismo `pg_blocking_pids` que usan las demás, y no compite con ninguna otra transacción que ya bloquee la fila de la obra.
* **Confiar solo en `uq_linea_base_obra_id_congelada`** no impide dos `BORRADOR`, y no impide que un congelado copie una jerarquía que otra sesión está borrando. Traducir el `23505` a un rechazo `RN-01` solo es correcto para esa restricción concreta; cualquier otra restricción única atribuida a `RN-01` mentiría. La traducción se queda como red de seguridad (ver «Consecuencias»), no como mecanismo.
* **El índice único parcial sobre `BORRADOR`** cubriría `CA-A10`, pero no `CA-B6` esc. 3, que de todos modos exige el bloqueo de la obra. Además, la segunda confirmación chocaría antes con `uq_concepto_obra_id_codigo`, y el traductor no puede atribuir ese choque a un borrador.
* **`SERIALIZABLE`** daría la garantía, pero al precio de errores de serialización (`40001`) en transacciones sin relación con la línea base y de una lógica de reintento en todo el sistema para resolver un problema que ocurre en tres operaciones. [ADR-004](20260918-bloqueo-pesimista-presupuesto.md) lo descartó por la misma razón.

## Consecuencias

**Positivas**

* Una obra no puede tener dos borradores ni un congelado que copie una jerarquía que se está borrando. La espera se ve en `pg_locks` como un bloqueo de fila de `obra`.
* La espera tiene tope: el `lock_timeout` del rol de aplicación (5 s) la convierte en `CONCURRENCIA` `BLOQUEO_VENCIDO` con `Retry-After`, y el `statement_timeout` (15 s) en `TIEMPO_EJECUCION_VENCIDO`.
* **La explosión congelada es la validada.** Como la confirmación y el congelado corren bajo el mismo bloqueo y calculan con la misma función de dominio, `explotar_filas`, la confirmación **cuantiza cada valor a la escala de su columna antes de calcular** importes y explosión. El congelado lee de la base esos mismos números ya cuantizados. Sin esa cuantización, una celda del Excel con más decimales que su columna haría que la explosión validada y la congelada difirieran en centavos (`CA-B1`).
* El orden de adquisición queda escrito en un solo lugar para los tickets que vengan: TKT-012 (máquina de estados de la obra) y TKT-021 (requisición).

**Negativas o costes aceptados**

* **Las operaciones sobre la misma obra se serializan.** Confirmar, reemplazar y congelar son poco frecuentes y de segundos de duración; la contención es irrelevante a esta escala.
* **Exige disciplina de orden.** Un caso de uso futuro que bloquee la obra después de `presupuesto_control` invertiría el orden y abriría un interbloqueo. Se mitiga con este documento y con la revisión del diseño de cada ticket que toque el ciclo.
* **El bloqueo no sustituye a las garantías del motor.** El índice parcial de la congelada y los disparadores de [inmutabilidad](20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) siguen vigentes como barrera de último recurso; el caso de uso traduce sus errores (`23505` de `uq_linea_base_obra_id_congelada`, `IN001`) en lugar de ignorarlos.

**Evidencia**

* `test_tkt017_caa10_dos_confirmaciones_simultaneas` (`TC-A22`): dos hilos confirman importaciones distintas de la misma obra; uno termina, el otro recibe `REEMPLAZO_NO_CONFIRMADO` o `ConcurrenciaVencida`, y queda una sola línea base con los conceptos de una sola importación.
* `test_tkt017_caa10_la_confirmacion_espera_el_bloqueo_de_la_obra` (`TC-A23`): comprueba la **espera** con `pg_blocking_pids`, no solo el resultado, y su variante con `lock_timeout` corto comprueba la respuesta `BLOQUEO_VENCIDO`.
* El mutante `M-A1`, que quita el `with_for_update()` de `bloquear_obra`, puso en rojo `test_tkt017_caa10_dos_confirmaciones_simultaneas`, `..._la_confirmacion_espera_el_bloqueo_de_la_obra` y `..._y_vence` (`impl.md`, TKT-017a3).

**Cuándo revisar esta decisión**

* Si se observa una espera de bloqueo perceptible en la confirmación o el congelado de una obra (más de 500 ms en el percentil 95, el umbral de [ADR-004](20260918-bloqueo-pesimista-presupuesto.md)).
* Si el negocio permite varios borradores por obra o varias importaciones simultáneas, la unidad de bloqueo deja de ser la obra.
* Si la máquina de estados de la obra de TKT-012 necesita su propio bloqueo y el orden de adquisición deja de ser lineal.
