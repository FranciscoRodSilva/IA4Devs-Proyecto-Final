# Clave de insumo por descripción normalizada, lectura de APU por rótulos y cuadre por suma

## Estado

Aceptado

## Contexto y problema

Las hojas de análisis de precios unitarios del cliente no traen un código por insumo: solo la descripción en la columna A. La asociación del análisis con el catálogo sí usa el código de la cabecera de la hoja. TKT-017 materializará insumos nuevos; hace falta una regla estable para saber si un renglón del Excel ya existe en `insumo`.

La disposición de cada hoja repite la misma forma en 44 hojas medidas (E-1): bloques `MATERIAL`, `MANO DE OBRA`, cargos con porcentaje en la columna D, base en la columna E, importe en la columna G, pie `PRECIO UNITARIO` en D con valor en G.

El pie del archivo trae un precio unitario; openpyxl entrega sumandos como `float`. Recalcular `costo × rendimiento` o `porcentaje × base` no reproduce siempre el Excel (mano de obra con rendimiento ambiguo, `PA-T6`).

## Opciones consideradas

**Clave del insumo al importar**

* Código de insumo en el Excel (decisión A2 del modelo) — las hojas no lo traen.
* **Descripción recortada, en mayúsculas y con espacios interiores colapsados** — `normalizar_clave_insumo`.
* Descripción más unidad como clave compuesta — duplica entradas si la misma descripción cambia de unidad entre hojas; se reporta con `UNIDAD_EN_CONFLICTO`.
* Mapa manual de la Dirección — fuera del alcance del lector.

**Lectura de la hoja**

* Posiciones fijas de fila — frágil ante filas insertadas.
* **Rótulos de fila en A con columnas fijas por bloque** — coincide con E-1 en 44/44 hojas.
* Rótulos de columna — no aplica al layout medido.

**Verificación del precio unitario**

* Recalcular cargos e insumos con fórmulas del glosario — contradice cifras reales (`CUADRILLA DE LIMPIEZA`, `PA-T6`).
* **Sumar lo leído** (material, mano de obra, cargos) y comparar el pie con tolerancia ±0.01 absoluta en `Decimal` — decisión 4 de la persona dueña.

## Decisión

Se identifica el insumo por **`normalizar_clave_insumo`**: `" ".join(descripcion.split()).upper()`.

Se lee cada hoja como **máquina de estados** sobre el rótulo normalizado de A, con columnas D/E/F/G para insumos y D/E/G para cargos, tal como TKT-014a/b implementan en `lectura_analisis.py`.

El **cuadre** usa `totalizar_analisis` + `verificar_precio_unitario` sobre los valores leídos, no sobre fórmulas rederivadas.

La lectura del libro entero (`leer_libro_presupuesto`) devuelve un **`AnalisisDelLibro` inmutable** con catálogo, análisis, asociaciones, insumos por crear y hallazgos crudos; no escribe en PostgreSQL (TKT-017 confirma).

## Consecuencias

**Positivas**

* El dominio se prueba con tuplas; openpyxl queda en `infraestructura/`.
* La misma clave alinea TKT-014 con la previsualización de TKT-018.

**Negativas o costes aceptados**

* **`PA-T1`:** errores tipográficos en la descripción crean insumos duplicados; la semilla TKT-010 (`TBR-001`…`TBR-027` por `codigo`) no coincide con esta clave y saldrán «por crear» hasta que TKT-017 decida el origen de `insumo.codigo` (P14).
* **`PA-T6`:** un cargo mal calculado en el Excel puede cuadrar el pie si las cifras internas son coherentes entre sí.
* La tolerancia ±0.01 vive en el dominio del lector, no en `tipos_base` (`PA-T11`).

**Cuándo revisar esta decisión**

* Si aparece un tercer layout de hoja APU que rompa E-1/E-2.
* Cuando TKT-017 fije cómo se genera `insumo.codigo` para propuestas sin código en el Excel.
