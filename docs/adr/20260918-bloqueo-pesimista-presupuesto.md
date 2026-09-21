# Bloqueo pesimista para la evaluación presupuestal

## Estado

Aceptado

## Contexto y problema

El principio no negociable 3 dice que los límites bloquean, no advierten. RN-03 lo concreta: una requisición que excede el presupuesto disponible de su partida se bloquea y requiere autorización de Dirección General.

La evaluación tiene tres pasos: leer lo presupuestado, calcular lo consumido, decidir. Si dos personas de Compras capturan requisiciones contra la misma partida al mismo tiempo, sin control ambas leen el mismo disponible, ambas concluyen que caben y ambas pasan. La partida queda sobregirada **sin que ninguna autorización se haya solicitado** — el fallo exacto que el producto existe para impedir.

La probabilidad es baja: dos obras, un puñado de personas en Compras, decenas de operaciones por hora. Pero la consecuencia es la negación del propósito del sistema, y un fallo así es silencioso: nadie se entera hasta que alguien compara cifras semanas después.

## Opciones consideradas

* Bloqueo pesimista: `SELECT … FOR UPDATE` sobre las filas de presupuesto del tipo de partida
* Bloqueo optimista: columna de versión y reintento ante conflicto
* Nivel de aislamiento `SERIALIZABLE` para toda la transacción
* Restricción declarativa en base de datos que impida el sobregiro

## Decisión

Se elige el **bloqueo pesimista**. La evaluación completa ocurre en una sola transacción que empieza tomando un bloqueo sobre las filas de presupuesto del tipo de partida afectado:

```sql
BEGIN;
-- control por importe: el tope capturado por Dirección (PA-03)
SELECT … FROM presupuesto_control
 WHERE linea_base_id = :lb AND tipo_partida_id = :tipo_partida
   FOR UPDATE;
-- control por volumen: la explosión derivada del APU
SELECT … FROM explosion_presupuesto
 WHERE linea_base_id = :lb AND tipo_partida_id = :tipo_partida
   FOR UPDATE;
-- calcular consumido, evaluar la regla, persistir resultado y bitácora
COMMIT;
```

El nivel de control es **obra + tipo de partida** (PA-01): cuatro bolsas por obra en lugar de una por partida y ubicación. Eso reduce drásticamente la contención potencial, porque los bloqueos se concentran en pocas filas, y hace todavía más importante el orden determinista de adquisición.

La segunda requisición espera a que la primera confirme y lee el estado ya actualizado.

**Por qué no optimista.** El reintento optimista es superior cuando los conflictos son raros y el reintento es transparente. Aquí el conflicto también es raro, pero el reintento no es transparente: la persona ya llenó un formulario con varios renglones y recibiría un error de concurrencia que no significa nada para ella. A esta escala el bloqueo dura milisegundos y nadie lo percibe.

**Por qué no `SERIALIZABLE`.** Daría la garantía, pero al precio de errores de serialización en transacciones que no tienen nada que ver con el presupuesto, obligando a lógica de reintento en todo el sistema para resolver un problema localizado en una operación.

**Por qué no una restricción declarativa.** Una restricción puede impedir el sobregiro, pero RN-03 no pide impedirlo: pide **bloquear la requisición, persistirla en estado `BLOQUEADA` y abrir una solicitud de autorización**. Eso es un flujo, no un rechazo. Una restricción abortaría la transacción y perdería el registro del intento, que es justamente el dato que hoy le falta a la dirección.

El mismo patrón se aplica a las otras dos evaluaciones con la misma forma: RN-07 (no recibir más de lo ordenado) bloquea los renglones de la orden de compra, y RN-15 (tope de consignación) bloquea la fila del proveedor.

## Consecuencias

**Positivas**

* Imposible sobregirar una partida por concurrencia.
* El intento bloqueado queda registrado con las cifras del momento, lo que permite contar cuántas veces se intentó sobregirar cada partida.
* El patrón es uniforme para las tres reglas de tope, así que se entiende una vez.

**Negativas o costes aceptados**

* Las requisiciones contra la misma partida se serializan. Irrelevante a esta escala.
* Exige disciplina: **toda** ruta que consuma presupuesto tiene que tomar el bloqueo. Una que lo olvide reabre el agujero. Se mitiga concentrando la evaluación en un único caso de uso por el que pasan todas las rutas.
* Riesgo de interbloqueo si una transacción tomara bloqueos de varias partidas en orden distinto. Se mitiga ordenando siempre los bloqueos por identificador de partida.

**Cuándo revisar esta decisión**

* Si se observara espera de bloqueo perceptible —más de 500 ms en el percentil 95— habría que reconsiderar la granularidad del bloqueo.
