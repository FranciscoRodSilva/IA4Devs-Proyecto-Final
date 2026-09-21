# Libro mayor de solo-anexado para el inventario

## Estado

Aceptado

## Contexto y problema

El almacén tiene que responder dos preguntas: *¿cuánto hay de este insumo en esta obra?* y *¿por qué?*. La segunda no es secundaria. El principio no negociable 4 exige que todo movimiento de inventario quede registrado con actor, momento y motivo, y el cliente pidió expresamente resolver un problema que hoy no tiene solución: *"Actualmente no se documenta [la merma], proponer algo para cubrir esta parte."*

El modelo habitual —una columna de existencia que se incrementa y decrementa— responde bien a la primera pregunta y destruye la segunda. Cuando el saldo de un insumo no cuadra, no hay forma de reconstruir qué lo movió: cada actualización pisa el valor anterior.

Hay un requisito adicional que lo decide: el traspaso de sobrantes entre obras (RN-08) tiene que mover el **costo** de una obra a otra. Con saldos mutables, un traspaso son dos actualizaciones sin rastro de que estaban relacionadas.

## Opciones consideradas

* Libro mayor de solo-anexado: la existencia es la suma de los movimientos
* Saldo mutable en una tabla de existencias
* Saldo mutable más tabla de histórico en paralelo

## Decisión

Se elige el **libro mayor de solo-anexado**. No existe ninguna columna de existencia en el esquema. La existencia de un insumo en una obra es `SUM(cantidad)` sobre `movimiento_inventario`, filtrando por obra e insumo.

Cada movimiento lleva tipo (`ENTRADA`, `SALIDA`, `TRASPASO_SALIDA`, `TRASPASO_ENTRADA`, `MERMA`, `AJUSTE`), cantidad con signo, costo unitario, referencia al documento que lo originó, momento, usuario y motivo.

**Las correcciones son movimientos, no ediciones.** Un error se corrige con un movimiento `AJUSTE` de signo contrario y motivo obligatorio. No hay `UPDATE` ni `DELETE` sobre la tabla.

**Un traspaso genera dos movimientos** en la misma transacción, `TRASPASO_SALIDA` en la obra origen y `TRASPASO_ENTRADA` en la destino, ambos apuntando al mismo registro de traspaso. Así el costo se mueve, las dos obras quedan cuadradas y la relación entre ambos movimientos es explícita.

Se descarta el **saldo más histórico en paralelo** porque introduce dos fuentes de verdad que hay que mantener sincronizadas. El día que divergen —y divergen— no hay criterio para saber cuál es la buena.

## Consecuencias

**Positivas**

* Reconstruir el estado del inventario en cualquier fecha pasada es una consulta con filtro temporal.
* La merma deja de ser una resta sin explicación: es un movimiento tipado con motivo y responsable, que es lo que el cliente pidió.
* El costo de un traspaso viaja con sus dos movimientos, sin lógica adicional.
* No hay posibilidad de que el saldo y su histórico se contradigan, porque solo hay una fuente.

**Negativas o costes aceptados**

* Consultar la existencia implica agregar en lugar de leer una columna. Con decenas de movimientos diarios y un índice sobre `(obra_id, insumo_id, ocurrido_en)`, el coste es despreciable.
* La tabla crece de forma monótona. A este volumen —27 insumos por obra, movimientos semanales— tardaría años en ser un problema.
* Requiere disciplina: cualquier ruta que altere inventario tiene que escribir un movimiento, no tocar un saldo. Al no existir el saldo, la disciplina es estructural y no depende de recordarla.

**Cuándo revisar esta decisión**

* Si el libro mayor superara el millón de filas por obra, o si la consulta del semáforo excediera 2 s en el percentil 95, se introduce una vista materializada de existencias refrescada por disparador. El libro mayor sigue siendo la fuente de verdad; la vista sería solo caché.
