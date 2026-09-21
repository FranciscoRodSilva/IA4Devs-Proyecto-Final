# Línea base como copia inmutable

## Estado

Aceptado

## Contexto y problema

El principio no negociable 1 es el más importante del producto: *la línea base es inmutable*. El presupuesto de venta se congela al firmar porque el contrato es a precio alzado máximo garantizado, y toda desviación se mide contra ella. Si la línea base se puede mover, la desviación deja de significar nada y el sistema entero pierde su propósito.

El problema es cómo se materializa el congelado. La forma habitual —una columna `estado = 'CONGELADA'` sobre las mismas filas de conceptos que se siguen usando— depende enteramente de que ninguna ruta de código escriba sobre ellas. Con siete módulos, una importación, trabajos extra que crean versiones y agentes implementando buena parte del backlog, esa garantía es una cuestión de confianza.

A esto se suma que el presupuesto **sí** cambia legítimamente: un trabajo extra amplía el alcance y crea una versión nueva (RN-18), pero la original tiene que conservarse íntegra para seguir midiendo contra ella.

## Opciones consideradas

* Copia física: al congelar, se copian conceptos y explosión a tablas de línea base
* Bandera de estado sobre las filas de trabajo
* Versionado por filas con vigencia temporal
* Registro de eventos y reconstrucción del estado

## Decisión

Se elige la **copia física**. Al congelar una línea base:

1. Se crea una fila en `linea_base` con versión, momento, usuario y motivo.
2. Se copian todos los conceptos a `linea_base_concepto` con su código, cantidad, precio unitario e importe **del momento**.
3. Se calcula y se copia la explosión agregada por tipo de partida a `explosion_presupuesto`, con cantidad presupuestada, rendimiento congelado, costo unitario e importe de venta.
4. Dirección captura el `presupuesto_control` —el importe tope por tipo de partida— sobre esa línea base (PA-03).

A partir de ahí, **todo el control de costos consulta las copias, nunca las tablas de trabajo**. `presupuesto_control` es la fuente del control por importe y `explosion_presupuesto` la del control por volumen.

El `rendimiento_congelado` que se copia aquí nunca se toca. El rendimiento que aprende de la ejecución real (`RN-24`) vive en `rendimiento_observado`, una tabla aparte: si compartieran columna, la línea base dejaría de ser inmutable en el sentido que importa.

La razón de fondo: una copia no depende de nada. No hay ruta de código, script de migración ni corrección manual que pueda alterar la línea base sin que sea evidente, porque las filas que el resto del sistema edita son otras. Una bandera de estado, en cambio, solo protege mientras cada nueva línea de código la respete.

Se refuerza con dos mecanismos en el motor: un índice único parcial que garantiza **una sola línea base congelada vigente por obra**, y un disparador que rechaza `UPDATE` y `DELETE` sobre las tablas de copia. El disparador es el único invariante del modelo que no se puede expresar de forma declarativa, y se acepta precisamente porque protege el principio más importante.

Se descarta el **registro de eventos** por desproporción: da inmutabilidad, pero obliga a reconstruir el presupuesto en cada consulta para un caso donde el estado cambia dos o tres veces en la vida de una obra.

## Consecuencias

**Positivas**

* La inmutabilidad no depende de la disciplina del código.
* El versionado por trabajos extra es natural: una versión nueva es otra copia, y la anterior queda intacta y consultable.
* Comparar versiones es un `JOIN` entre dos copias, no una reconstrucción.
* La explosión por partida se calcula una vez al congelar, no en cada consulta del tablero.

**Negativas o costes aceptados**

* Duplicación de datos: ~4,900 filas de concepto por versión de línea base. A dos o tres versiones por obra, es irrelevante.
* El congelado es una operación pesada que tiene que ser transaccional: o se copia todo, o no se copia nada.
* Si se corrige un error del presupuesto después de congelar, hay que crear una versión nueva. Es deliberado: obliga a dejar constancia del motivo en lugar de editar en silencio.

**Cuándo revisar esta decisión**

* Si una obra llegara a decenas de versiones de línea base, habría que evaluar almacenar diferencias en lugar de copias completas. No se prevé: los trabajos extra son excepcionales.
