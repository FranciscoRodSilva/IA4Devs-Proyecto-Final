# Preparación de importación en una columna `jsonb`

## Estado

Aceptado

## Contexto y problema

TKT-015 analiza el Excel de línea base sin escribir en el modelo real. Las filas válidas —catálogo, nodos, conceptos, análisis, asociaciones e insumos por crear— deben conservarse para que TKT-017 confirme sin repetir openpyxl, y deben quedar **completas o no existir**: un reintento borra errores y preparación en la misma transacción que vuelve a `ANALIZANDO`.

La preparación puede ser grande (miles de conceptos) pero es un solo documento por importación, se lee entero al confirmar y no se consulta por partes en SQL. Union Square deja la preparación con cero conceptos válidos; ENITI conserva un solo análisis de veinticuatro porque el resto falla — eso es correcto, no un fallo del almacén.

## Opciones consideradas

| | Columna `jsonb` en `importacion` | Tabla `importacion_preparacion` 1:1 | Tablas normalizadas | `bytea` con `pickle` |
|---|---|---|---|---|
| Completa o ninguna | Mismo `UPDATE` que fija el estado; `CHECK` impide valor en `RECIBIDO` y `ANALIZANDO` | Misma transacción; hace falta `DELETE` explícito al reintentar | Miles de filas en una transacción | Igual que la columna |
| Migración | Una columna y un `CHECK` (`v0009`) | Tabla, clave foránea, índice | Cinco o seis tablas nuevas | Una columna |
| Consultas del módulo | Cada `SELECT` de `importacion` nombra columnas; solo `leer_preparacion` lee el blob | Unión 1:1 | Varias consultas | Deserializar en Python |
| Tipado y evolución | JSON versionado (`formato: 1`) | Igual | Esquema relacional rígido | Acoplado a clases Python |

## Decisión

Se guarda el resultado del análisis en **`importacion.preparacion jsonb`**, anulable, con la restricción **`ck_importacion_preparacion_tras_analisis`**:

`preparacion IS NULL OR estado NOT IN ('RECIBIDO', 'ANALIZANDO')`.

La serialización vive en `preparacion_json.py` (**formato 1**):

- Clave `formato: 1` para que TKT-017 rechace otra versión. Un formato desconocido, una clave ausente o un tipo inesperado responden `409` `CONFLICTO` con el código `ESTADO_NO_PERMITE_OPERACION` y el mensaje «La preparación de la importación no se puede leer; la importación debe analizarse de nuevo.», con `importacion_id` y el `formato` leído (o nulo) en el detalle. La importación no cambia de estado.
- Cifras de `tipos_base` como **cadena** con `format(valor, "f")`, **sin cuantizar**; `None` → `null` en JSON.
- Enumerados como `.value`; rutas como filas de nodo, no nombres.
- Contenido: `hoja_catalogo`, `nodos`, `conceptos`, `analisis`, `asociaciones`, `insumos_por_crear`, más `filas_leidas`, `filas_validas` y `filas_rechazadas`.

El dominio no conoce JSON: `Preparacion` es inmutable; la infraestructura traduce.

### Mapa de causas a tipos (`PA-15.2`)

Las **22** `CausaHallazgo` del lector van a uno de los **siete** tipos persistidos en `importacion_error` mediante `TIPO_POR_CAUSA` en `clasificacion_importacion.py`. Reglas que fijan la semántica:

1. **`SIN_CONCEPTOS` solo para las cinco causas de hoja** (`HOJA_NO_LOCALIZADA`, `HOJA_AMBIGUA`, `ENCABEZADO_NO_LOCALIZADO`, `COLUMNA_NO_LOCALIZADA`, `NINGUN_CONCEPTO`), con `fila` y `columna` nulas en el error.
2. **`CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` son `REF_ROTA`**, no «hoja sin conceptos»: la referencia rota conserva la ubicación del hallazgo.
3. **`VALOR_AUSENTE` en la celda de rendimiento de un insumo** (columna F del bloque de insumos) se clasifica como **`RENDIMIENTO_AUSENTE`**, sin causa nueva en el lector: el lector sigue emitiendo `VALOR_AUSENTE`; la clasificación usa `es_celda_de_rendimiento`.
4. **`ANALISIS_SIN_CODIGO` es `REF_ROTA`**, no `SIN_APU`: si fuera `SIN_APU`, Union Square tendría decenas de errores de más y rompería `CA-3`.
5. Tres orígenes **sin causa cruda** completan los siete tipos: **`SIN_APU`** (códigos en `codigos_sin_analisis`), **`DUPLICADO`** (descripciones distintas para el mismo código en el catálogo) y **`PROCESO_INTERRUMPIDO`** (interrupción del análisis).

| Causa | Tipo |
|---|---|
| Causas 1–5 de hoja (ver arriba) | `SIN_CONCEPTOS` |
| `ERROR_DE_FORMULA`, `NO_ES_NUMERO`, `VALOR_AUSENTE` (salvo rendimiento), `NOMBRE_ILEGIBLE`, `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA`, `VALOR_NEGATIVO`, `FECHA_NO_RECONOCIDA`, `PU_NO_CUADRA`, `PU_NO_VERIFICABLE`, `ANALISIS_SIN_CODIGO`, `CODIGO_SIN_CONCEPTO` | `REF_ROTA` |
| `VALOR_AUSENTE` en celda de rendimiento | `RENDIMIENTO_AUSENTE` |
| `UNIDAD_NO_RECONOCIDA`, `CARGO_DESCONOCIDO`, `UNIDAD_EN_CONFLICTO` | `UNIDAD_DESCONOCIDA` |
| `CODIGO_EN_VARIAS_HOJAS`, `TIPO_EN_CONFLICTO` | `DUPLICADO` |

El detalle fila a fila, plantillas de mensaje y recuentos sobre ENITI y Union Square están en el diseño de TKT-015 (`PA-15.2`).

### Qué rechaza cada `DUPLICADO`

| Origen | Alcance del rechazo |
|---|---|
| `detectar_duplicados` en el **catálogo** (mismo código, descripciones normalizadas distintas) | **Todas las filas** de ese código en el catálogo |
| `CODIGO_EN_VARIAS_HOJAS` o `TIPO_EN_CONFLICTO` en una **hoja de APU** | **Solo ese análisis**; no rechaza filas del catálogo (si rechazara filas, ENITI perdería conceptos válidos cuyo código tiene un APU defectuoso) |
| `SIN_APU` | **Todas las filas** del código en el catálogo |

Un `SIN_APU` o un `DUPLICADO` de catálogo en la **primera fila** del código implica rechazar **todas** las filas del código: el defecto es del código entero, no de una fila suelta.

### Por qué no se amplía el `CHECK`

El `CHECK` solo ata **presencia de preparación** a **estado terminal o intermedio permitido**. No valida la forma del JSON: eso lo hace TKT-017 al deserializar (`formato`, tipos, claves). Validar el documento en PostgreSQL exigiría funciones propias, duplicar reglas del dominio y rechazar preparaciones casi vacías pero válidas (Union con cero conceptos). La coherencia «completa o ninguna» en el reintento ya la garantiza **`preparacion IS NULL` mientras `ANALIZANDO`** más el borrado en `iniciar_analisis` (`PA-15.7`).

## Consecuencias

**Positivas**

- Una migración pequeña; permisos heredados de `importacion`.
- Reintento sin preparación huérfana: imposible dejar JSON con estado `RECIBIDO` o `ANALIZANDO`.
- TKT-017 lee un solo campo; explosión y confirmación no repiten el parseo del Excel.

**Negativas o costes aceptados**

- No hay consultas SQL parciales sobre conceptos dentro de la preparación.
- Documentos muy grandes van a TOAST; si `pg_column_size` superara ~20 MB en un libro real, habría que escalar a tabla 1:1 (condición de parada del diseño).
- El dinero en JSON no está cuantizado: TKT-017 debe respetar la escala al materializar (`RN-01`, ADR-020).

**Cuándo revisar esta decisión**

- Si la confirmación necesita indexar insumos o conceptos dentro de la preparación antes de materializar.
- Si el tamaño medido en producción obliga a normalizar.
