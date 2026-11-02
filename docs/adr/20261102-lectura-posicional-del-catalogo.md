# Lectura posicional del catálogo de conceptos y conversión de `float` con `repr`

## Estado

Aceptado

## Contexto y problema

La importación de la línea base empieza leyendo un Excel de catálogo. Las filas de nivel, área y partida no traen código: solo el nombre en la columna de descripción. La jerarquía depende de **dónde** aparecen esas filas respecto de los conceptos, no de indentación ni de un nombre fijo como «NIVEL n».

openpyxl, en modo `read_only=True` y `data_only=True`, entrega números como `int` o `float`, nunca `Decimal`. El dominio de CIMENTA prohíbe `float` en firmas y exige `Cantidad` y `Dinero` exactos.

## Opciones consideradas

**Profundidad**

* Alinear **todas** las corridas de filas sin código a la partida.
* Alinear **todas** a la raíz.
* Reconocer nivel/área/partida por el texto del nombre.
* Contar la profundidad máxima del archivo.
* **Primera corrida de la hoja a la raíz; las siguientes a la partida** (cuatro niveles: raíz, nivel, área, partida).

**Conversión numérica en la frontera openpyxl → dominio**

* `Decimal(f)` — arrastra el binario de IEEE y `tipos_base` lo rechaza.
* `round(f, 4)` — redondea antes de tiempo.
* Leer el XML de la celda sin openpyxl.
* **`Decimal(repr(f))`** — cadena decimal más corta que reproduce el mismo `float`.

## Decisión

Se elige la regla de **primera corrida a raíz y corridas posteriores a partida**, porque es la única que cuadra con los dos archivos reales del cliente sin depender de nombres de fila.

Se elige **`Decimal(repr(f))` en infraestructura**, una sola vez al cruzar la frontera, sin redondear; `cuantizar()` queda para la materialización (TKT-017).

El resultado es un **`CatalogoLeido` en memoria** (`PA-T11`): no hay tabla de preparación ni migración en TKT-013.

## Consecuencias

**Positivas**

* El dominio se prueba entero con tuplas, sin openpyxl ni base.
* Los hallazgos crudos (`Hallazgo`) se traducen a `importacion_error` en TKT-015, sin mezclar vocabularios.

**Negativas o costes aceptados**

* Un catálogo sin fila de título, o un área sin partida fuera de la primera corrida, puede leerse corrido sin hallazgo; un oráculo sobre los archivos completos vigila el límite (TC-36).
* La fila de título (`RAIZ`) no tiene tabla en el modelo; TKT-017 decide qué hacer con ella.

**Cuándo revisar esta decisión**

* Si aparece un tercer archivo real cuyo catálogo no traiga fila de título o tenga un área sin partida fuera de la primera corrida (fallo en TC-36).
* Si TKT-017 requiere persistir o descartar explícitamente el nodo `RAIZ` al materializar en [`docs/06-stack-tecnologico.md`](../06-stack-tecnologico.md) §4.5.
