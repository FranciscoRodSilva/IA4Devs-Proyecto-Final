# El historial de la obra se cuenta por un puerto que los módulos posteriores implementan

## Estado

Aceptado

## Contexto y problema

RN-01 dice que una obra con historial no se borra. El historial de HDU-001 esc. 20 abarca líneas base, importaciones y filas propias de `presupuesto`, y también movimientos de módulos que cuelgan de la obra: requisiciones, órdenes de compra, solicitudes de autorización, archivos y, más adelante, entradas de almacén o de avance. El borrado de TKT-012b debe responder `409 OBRA_CON_HISTORIAL` con un conteo real, no solo con un error de base de datos.

Hay una restricción de dependencias. `presupuesto` es el núcleo y no depende de ningún módulo de negocio: el contrato `grafo-compras` de `import-linter` lo verifica en cada PR. Pero `compras` y los módulos posteriores sí necesitan `presupuesto`, así que la dirección de la importación no puede invertirse. El caso de uso de borrado de `presupuesto` necesita contar movimientos que no puede leer por sí mismo.

## Opciones consideradas

* **Importar las interfaces publicadas de los módulos posteriores desde `presupuesto`.** Es la forma directa de obtener el conteo. Rompe `grafo-presupuesto`: `presupuesto` pasaría a depender de `compras` y de los demás, y el núcleo quedaría atado a sus consumidores.
* **Consultar directamente las tablas de los módulos posteriores desde `presupuesto`.** Evita el puerto y no añade código. Viola la regla 3 del proyecto: un módulo solo habla con otro por su interfaz publicada, nunca por sus repositorios, modelos o tablas.
* **Confiar solo en las claves foráneas `ON DELETE RESTRICT`.** El motor ya impide borrar una obra con hijas, así que la integridad queda protegida. Pero la restricción no da el conteo ni el mensaje para la persona usuaria, y depende de que cada tabla futura declare su clave foránea y la mantenga. Una tabla con `obra_id` sin clave foránea, como `archivo` hoy, quedaría fuera sin que nadie lo notara.
* **Un puerto `FuenteHistorialObra` definido en `presupuesto`, implementado por cada módulo posterior y cableado en la raíz de composición.** Es la opción elegida.

## Decisión

Se elige **un puerto inyectado** porque:

* `presupuesto` define el `Protocol` `FuenteHistorialObra` (con `nombre` y `contar(sesion_bd, obra_id) -> int`) y no importa a ningún módulo que lo implemente. Así se respetan `grafo-presupuesto` y la regla 3.
* El caso de uso `contar_historial` suma el conteo propio del repositorio de `presupuesto` y el de cada fuente del `ContextoPresupuesto`. Usa la sesión del llamador, dentro de la transacción que ya tiene la obra bloqueada, de modo que el conteo y el borrado ven el mismo estado.
* Una fuente que falla no se trata como cero: el error se propaga y el borrado no ocurre. Un conteo parcial que la persona leyera como completo sería peor que un error.
* La clave foránea `ON DELETE RESTRICT` queda como última barrera. Si una tabla hija existe y su fuente no está inyectada, el motor responde `23001` y el caso de uso lo traduce a `OBRA_CON_HISTORIAL`, sin inventar un conteo.
* Hoy ningún módulo publica una fuente, así que `movimientos` vale cero. El parámetro `fuentes_historial` ya existe en `construir_contexto` y en `montar_presupuesto`, para que el cableado se ejercite de extremo a extremo desde el primer día.

**Obligación para los tickets posteriores.** El primer ticket que escriba una tabla con `obra_id` debe publicar su fuente de historial en el mismo cambio. Esto incluye `archivos`, cuya columna `obra_id` no tiene clave foránea y, por eso, no tiene barrera del motor. Las tablas que ya existen en el esquema y que cuelgan de la obra (`requisicion`, `orden_compra` y `solicitud_autorizacion`) cuentan para esta obligación en cuanto su módulo escriba en ellas. El `delta.md` del ticket que las escriba debe citar este ADR.

## Consecuencias

**Positivas**

* `presupuesto` mantiene su grafo de importaciones, y `lint-imports` lo verifica en el PR.
* El conteo de RN-01 es explícito en código y tiene pruebas propias: cada fuente se consulta una vez, con la sesión correcta, y su fallo se propaga.
* La decisión de si una obra tiene historial vive en `dominio/historial_obra.py` (`hay_historial`), no en una consulta SQL.

**Negativas o costes aceptados**

* Mientras ningún módulo publique su fuente, `movimientos` es cero y la barrera real es la clave foránea. Un ticket posterior que olvide publicar la fuente hace que el conteo del `409` sea incompleto, aunque el borrado siga protegido por el motor. El riesgo R-1 de `sdd/tickets/tkt-012b/design.md` lo recoge.
* La tabla `archivo` no tiene clave foránea sobre `obra_id`. Hasta que su ticket publique la fuente, un archivo podría quedar huérfano tras un borrado. La obligación de este ADR lo cubre cuando se escriba esa tabla.
* La raíz de composición (`servidor/`) debe pasar las fuentes al montar el módulo. Olvidarlo deja el puerto sin ejercitar en producción; las pruebas de la fila A4 no lo detectan por sí solas.

**Cuándo revisar esta decisión**

* Si un módulo posterior necesita una consulta del historial que el conteo por obra no expresa (por ejemplo, historial por tipo de partida), el puerto debe ampliarse y este ADR revisarse.
* Si aparecen más de tres módulos con fuentes, conviene evaluar un registro explícito de fuentes en lugar de la tupla que arma `servidor/`.
