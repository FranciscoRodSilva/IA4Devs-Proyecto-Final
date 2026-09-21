# SQLAlchemy síncrono con rutas `def`, en lugar de asíncrono

## Estado

Aceptado

## Contexto y problema

[ADR-010](20260918-sqlalchemy-data-mapper.md) eligió SQLAlchemy 2.0 y [ADR-009](20260918-fastapi.md) eligió FastAPI, pero ninguno dijo en qué **modo de ejecución** se usan. SQLAlchemy 2.0 ofrece los dos: `Session` síncrona y `AsyncSession`. FastAPI también: una ruta declarada `def` corre en su grupo de hilos, una declarada `async def` corre en el bucle de eventos.

Parece un detalle de estilo y no lo es. Determina cómo se escribe cada transacción, cómo se escribe el test de concurrencia de TKT-022, y qué categoría de fallos es posible. Sobre todo, es una decisión que **si no se toma, se toma sola y mal**: el proyecto acaba con las dos formas mezcladas porque cada ticket resuelve a su manera, y una `Session` síncrona invocada desde una ruta `async def` bloquea el bucle sin que nada lo señale.

La operación que define el sistema es la de [ADR-004](20260918-bloqueo-pesimista-presupuesto.md): `BEGIN`, `SELECT … FOR UPDATE` sobre las cuatro filas de presupuesto de la obra, calcular consumido, evaluar `RN-03`, persistir y confirmar. Es una transacción corta que **serializa a propósito**.

## Opciones consideradas

* SQLAlchemy síncrono con rutas `def`
* SQLAlchemy asíncrono con rutas `async def`
* Mezcla: asíncrono donde convenga, síncrono en las rutas transaccionales

## Decisión

Se elige **SQLAlchemy síncrono, con todas las rutas declaradas `def`**. FastAPI las ejecuta en su grupo de hilos, cada petición toma una conexión del pool y la transacción vive dentro de la petición.

* **La transacción central se lee mejor sin `await` intercalado.** La pregunta que importa en ese bloque es *"¿se toma el bloqueo antes de leer el consumido y se suelta solo al confirmar?"*. Cada `await` en medio es un punto donde hay que preguntarse si algo más pudo ejecutarse, y la respuesta tiene que ser siempre la misma. Quitar la pregunta es más barato que responderla catorce veces.
* **El test de concurrencia de TKT-022 es determinista.** Dos hilos con dos `Session` reales contra la misma partida son unas pocas líneas que fallan de verdad si el bloqueo no está. La versión asíncrona exige orquestar tareas y es fácil acabar con un test que pasa por cómo quedaron los tiempos y no por el bloqueo — que es peor que no tener test, porque da confianza falsa sobre la única garantía que el producto no puede perder.
* **No hay concurrencia que ganar.** La escala son decenas de operaciones por hora ([arquitectura §1](../02-arquitectura.md#1-escala-real-del-sistema)). Async compra solapar espera de E/S; aquí la E/S que importa son cuatro filas que se serializan deliberadamente.
* **La otra operación pesada tampoco se beneficia.** openpyxl es síncrono y además retiene el intérprete: la importación se aísla en un proceso aparte, que es una solución ortogonal a este debate.
* **Criterio C3.** Los ejemplos públicos de SQLAlchemy con transacciones y bloqueo son mayoritariamente síncronos. Un agente que escriba la variante asíncrona tiene más ocasiones de inventar.

**Se descarta la mezcla** aunque sea técnicamente defendible. Dos modos conviviendo obligan a saber, en cada archivo nuevo, en cuál se está; y el fallo de equivocarse —una llamada bloqueante dentro de una ruta `async def`— no lo detecta ningún linter ni ninguna prueba. Se manifiesta como una aplicación lenta bajo carga, sin un solo error en el registro. Un modo único elimina la pregunta.

## Consecuencias

**Positivas**

* Las transacciones con bloqueo pesimista se leen de arriba abajo, sin puntos de suspensión.
* El test de concurrencia prueba el bloqueo, no la temporización.
* Se cierra por decisión una trampa que no tiene verificación automática posible.

**Negativas o costes aceptados**

* **El techo de concurrencia es el tamaño del grupo de hilos**, no el del bucle de eventos. A decenas de operaciones por hora sobra, pero es un techo real y más bajo.
* Si en el futuro hiciera falta hablar con un servicio externo lento —notificaciones, timbrado fiscal—, cada llamada ocupa un hilo mientras espera. La salida es ejecutarla fuera de la petición, no cambiar el modo de todo el sistema.
* Se renuncia a las bibliotecas que solo existen en versión asíncrona. Ninguna del stack actual lo es.

**Cómo se verifica**

* Una prueba recorre el enrutador de la aplicación y **falla si alguna ruta está declarada `async def`**. Es la forma de que la decisión no dependa de que nadie se despiste en el ticket número cuarenta.

**Cuándo revisar esta decisión**

* Si el sistema incorporara integraciones externas con latencia alta en el camino de la petición.
* Si la concurrencia real superara el grupo de hilos configurado, lo que a esta escala significaría que el producto cambió de tamaño.
