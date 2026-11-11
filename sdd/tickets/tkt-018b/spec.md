# Spec · TKT-018b · Flujo de importación del presupuesto

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

TKT-018 se partió el 2026-11-10 por el plazo de la tercera entrega. TKT-018a, ya fusionado, entregó la pantalla de la línea base, el congelado y el presupuesto de control. Esta mitad, TKT-018b, entrega lo que falta para que exista una línea base real: **todo el flujo de importación del catálogo de conceptos**, desde que el Director de Proyectos elige el Excel hasta que la línea base queda en `BORRADOR`.

Hoy el servidor tiene los componentes por separado y ninguna ruta que los una:

- El análisis (TKT-013 a TKT-015) lee el libro, lo clasifica y deja la **preparación** en `importacion.preparacion`, pero ninguna ruta lo arranca, ninguna crea la importación y ninguna lista sus errores.
- La materialización (TKT-017) vive en la interfaz publicada de `presupuesto` como `materializar_importacion`, pero ninguna ruta la invoca.
- El módulo `archivos` (TKT-059) tiene solo el esqueleto: sin tabla `archivo`, sin `registrar_archivo` y sin lector del contenido. **TKT-059 está sin ejecutar**; esta spec se puede escribir, pero la ejecución de TKT-018b no puede empezar hasta que TKT-059 entregue, como mínimo, el alta del archivo, su confirmación y el lector del contenido.
- El frontend no tiene tipos generados de importación ni de archivos, y la pantalla de la línea base dice que la importación «llegará en una próxima entrega (TKT-018b)».

Además, TKT-018b hereda deuda declarada de TKT-017: `motivo_reemplazo` sin tope de longitud y expuesto al carácter `NUL`, y la medición con el archivo real del catálogo (`PA-T3`, `PA-T17.9`).

La spec también registra **hallazgos entre la historia, la ficha y el borrador OpenAPI** que el diseño debe resolver con revisión humana (sección «Preguntas abiertas y supuestos»), sobre todo que el contrato no publica los nombres de partida a los que se asigna un tipo.

## Historia de usuario

**Como** Director de Proyectos
**quiero** subir el Excel del catálogo de conceptos de una obra, ver qué leyó el sistema y qué errores trae, asignar un tipo de partida a cada nombre de partida y confirmar la importación
**para** obtener la línea base en `BORRADOR` que luego congelo, sin que un archivo malo o un fallo a medias deje datos en el modelo real.

## Alcance

Must validado por la persona dueña el 2026-11-11.

| Nivel | Ítem |
|---|---|
| **Must** | **Backend.** Las siete rutas de importación del borrador (`crear_importacion`, `listar_importaciones`, `obtener_importacion`, `iniciar_analisis_importacion`, `listar_errores_importacion`, `confirmar_importacion`, `descartar_importacion`) y la ruta `listar_tipos_partida` que el selector de tipos necesita. El caso de uso de crear registra el `archivo` `PENDIENTE` en la misma transacción. El arranque del análisis comprueba que el archivo esté `DISPONIBLE`. La previsualización (`resumen` con conteos, importe total, insumos creados y los nombres de partida leídos) la construye este ticket. Confirmar invoca `materializar_importacion`. El tope y el carácter `NUL` en `motivo_reemplazo` (deuda de TKT-017) |
| **Must** | **Frontend.** Pantalla 3a (carga y progreso), 3b (previsualización con asignación de tipos de partida y confirmación) y 3c (errores por hoja y fila) de [`docs/08-wireframes.md`](../../../docs/08-wireframes.md#3-importación-del-presupuesto), con el diálogo de reemplazo y los rechazos que el boceto pinta. El enlace desde la pantalla de la línea base reemplaza el texto «llegará en una próxima entrega» |
| **Must** | Escenarios 4 a 13, 21 y 24 a 29 de HDU-001, **con los rechazos de 25 y 26 vistos desde esta pantalla**. Sus tests propios de confirmación de archivo son de TKT-059 |
| **Should** | `S1` · «Exportar errores»: CSV generado en el cliente con lo ya filtrado y cargado, sin ruta nueva. `(asumido)` |
| **Should** | `S2` · Medir con el archivo real del catálogo las suposiciones de TKT-017 (`PA-T3`, `PA-T17.9`) con las 26 pruebas omitidas, si los archivos privados están disponibles |
| **Should** | `S3` · Prueba E2E de Playwright del flujo feliz con almacén de objetos real |
| **Could** | — |
| **Won't** | Editar conceptos (una corrección se hace reimportando). El componente de subida reutilizable con cámara y compresión (TKT-065). Una ruta de exportación de errores. Las tablas «Ver conceptos» y «Ver explosión por tipo de partida» del boceto 4a. El selector de obra del armazón. Adelantar nada de la fase 2. Publicar `crear_obra` en la interfaz de `presupuesto` y migrar la semilla de TKT-018a a ella |

**Disparadores de recorte `(asumido)`.** `S3` se recorta sin preguntar si el trabajo `humo` no puede levantar el almacén de objetos. `S2` se recorta sin preguntar si los archivos del catálogo no están disponibles al cierre de la ejecución; en ese caso la deuda de `PA-T3` sigue abierta y se dice en el delta. `S1` se recorta si el plazo aprieta.

## Non-goals

- **No edita conceptos ni el contenido de la preparación.** Una corrección se hace reimportando.
- **No es dueño de la validación del archivo.** El tamaño, el hash, el tipo leído de los bytes y la caducidad del `PENDIENTE` son de TKT-059. Aquí solo se consume su resultado.
- **No implementa el análisis ni la materialización.** Los dos existen (TKT-013 a TKT-017) y cambian solo para lo que este ticket nombra: la guarda del archivo `DISPONIBLE` y el tope del motivo.
- **No toca la congelación ni el presupuesto de control**, que son de TKT-017 y TKT-018a.
- **No crea una ruta de exportación** ni un formato de exportación en el servidor.
- **No amplía el contrato más allá de los huecos que esta spec nombra**, y los corrige el diseño con revisión humana.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | La línea base se congela al firmar; ninguna operación posterior la modifica. Aquí: una obra con línea base `CONGELADA` no admite una importación nueva, y reemplazar un `BORRADOR` es explícito y queda asentado | PRD §8 — `docs/01-descripcion-producto.md` |
| `RN-02` | Todo lo que se consume está imputado a un tipo de partida. Aquí: sin tipo asignado a cada nombre de partida no hay explosión por tipo, así que no se confirma | PRD §8 |
| `RN-24` | La línea base conserva el rendimiento congelado | PRD §8 (la materialización lo copia; este ticket no lo recalcula) |
| `RNF-06` | Tipo leído de los bytes, lista blanca y SVG prohibido | PRD §9. Esc. 21, 24 y 26: consume el resultado de TKT-059 |
| `RNF-17` | Un trabajo en segundo plano interrumpido no queda colgado | PRD §9. Esc. 29 |
| `RNF-19` | La bitácora conserva el hash de lo adjuntado | PRD §9. Esc. 24 y 25: consume el resultado de TKT-059 |

Los escenarios 24 a 26 no aplican ninguna `RN`: implementan `RNF-06` y `RNF-19` (nota de HDU-001).

## Invariantes que deben sobrevivir al cambio

El ticket **modifica algo que ya funciona** (la guarda del análisis, la pantalla de la línea base, el contrato y los tipos generados), así que cada fila genera un criterio de regresión.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| `INV-05` | Una sola línea base `CONGELADA` por obra | `CA-R1` |
| `INV-14` y `RN-01` | Inmutabilidad de la línea base congelada (disparador `IN001`) | `CA-R1` |
| `INV-26` | Todo adjunto señala un documento: `referencia_id` no nulo salvo en `OBRA` | `CA-1` |
| Pantalla de la línea base (TKT-018a `CA-12`, `CA-1`, `CA-2`) | Estado vacío, borrador y congelada siguen mostrándose igual; solo cambia el texto de la importación | `CA-R2` |
| Análisis ya probado (TKT-015b: esc. 6 a 9, 27 a 29) | Una ruta nueva no cambia lo que el analizador clasifica ni cómo cierra la importación | `CA-R3` |
| Contrato publicado y tipos del cliente | El OpenAPI y `generado/servidor.ts` siguen coherentes | `CA-R4` |

## Criterios de aceptación

Gherkin, en español. Los nombres de test llevan `hdu001_escNN` donde hay escenario y `tkt018b_caNN` donde no.

### Backend

#### CA-1 `[M]` · Crear la importación con su archivo `PENDIENTE` · `RN-01`, `RNF-06` · `HDU-001 esc. 4 y 24`

```gherkin
Escenario: El Director de Proyectos crea la importación de una obra sin línea base congelada
  Dado que existe una obra sin línea base CONGELADA ni importación en ANALIZANDO
  Y el navegador declaró nombre, tamaño y hash SHA-256 de un archivo .xlsx
  Cuando el Director de Proyectos crea la importación
  Entonces la importación queda en estado RECIBIDO
  Y existe un archivo en estado PENDIENTE con referencia_tipo "IMPORTACION" y referencia_id igual al identificador de la importación
  Y el archivo se dio de alta por la interfaz publicada de archivos en la misma transacción que la importación
  Y la respuesta trae archivo_id y una URL prefirmada de subida de vida corta
  Y ningún byte del Excel pasa por el API
```

#### CA-2 `[M]` · Rechazo · Formato declarado distinto de `.xlsx` · `RNF-06` · `HDU-001 esc. 21`

```gherkin
Escenario: Un .xls, un .csv o un PDF se rechazan antes de crear nada
  Dado que el navegador declara un nombre o un tipo que no es .xlsx, por ejemplo catalogo.xls
  Cuando el Director de Proyectos intenta crear la importación
  Entonces responde 422 con el contrato de error VALIDACION y el campo del formato declarado
  Y el mensaje indica que solo se admite .xlsx
  Y no se escribe ninguna fila en importacion ni en archivo
  Y no se emite URL de subida
```

#### CA-3 `[M]` · Rechazo · Obra que no admite una importación nueva · `RN-01`

```gherkin
Escenario: Una obra con línea base congelada o con una importación analizándose rechaza la creación
  Dado que la obra tiene una línea base CONGELADA
  O que tiene otra importación en estado ANALIZANDO
  Cuando el Director de Proyectos intenta crear una importación
  Entonces responde 409 y no se crea ni la importación ni el archivo
  Y con la línea base congelada el contrato de error es REGLA_NEGOCIO con regla "RN-01" (según el borrador) (asumido)
  Y con otra importación en curso es CONFLICTO con código IMPORTACION_EN_CURSO
```

#### CA-4 `[M]` · Arrancar el análisis con el archivo `DISPONIBLE` · `RNF-17` · `HDU-001 esc. 4 y 24`

```gherkin
Escenario: El análisis arranca solo cuando el archivo está disponible
  Dado que la importación está en RECIBIDO y su archivo está DISPONIBLE
  Cuando el Director de Proyectos pide el análisis
  Entonces responde 202 y la importación pasa a ANALIZANDO
  Y el trabajo del analizador lee el Excel desde el almacén de objetos, no desde una ruta
  Y la consulta de la importación devuelve el progreso como porcentaje
```

#### CA-5 `[M]` · Rechazo · Análisis con el archivo `PENDIENTE` · `RNF-06` · `HDU-001 esc. 24`

```gherkin
Escenario: Pedir el análisis con el archivo todavía en PENDIENTE
  Dado que la importación está en RECIBIDO y su archivo sigue en PENDIENTE
  Cuando el Director de Proyectos pide el análisis
  Entonces responde 409 CONFLICTO con código ARCHIVO_NO_DISPONIBLE y la acción CONFIRMAR_ARCHIVO
  Y la importación sigue en RECIBIDO
  Y no se escribe nada en la preparación
```

#### CA-6 `[M]` · Rechazo · Archivo rechazado por TKT-059: la importación no arranca · `RNF-06`, `RNF-19` · `HDU-001 esc. 25 y 26`

```gherkin
Escenario: Un archivo con hash, tamaño o tipo que no son los declarados no llega al analizador
  Dado que la confirmación del archivo respondió ARCHIVO_HASH_DISTINTO, ARCHIVO_TAMANO_DISTINTO o ARCHIVO_TIPO_NO_PERMITIDO
  Cuando el Director de Proyectos pide el análisis de esa importación
  Entonces responde 409 y la importación no pasa a ANALIZANDO
  Y el lector de hojas de cálculo no recibe el archivo
  Y no se escribe ninguna fila en la preparación ni en el modelo real
```

Los tests de la confirmación del archivo (esc. 25 y 26) son de TKT-059. Aquí se prueba la consecuencia en la importación.

#### CA-7 `[M]` · Previsualización de lo leído · `HDU-001 esc. 5 y 10`

```gherkin
Escenario: Consultar una importación VALIDADO
  Dado que el análisis terminó sin errores y la importación está en VALIDADO
  Cuando el Director de Proyectos o Dirección General la consultan
  Entonces la respuesta trae el número de niveles, áreas, partidas y conceptos, el importe total calculado, los insumos creados durante la importación marcados como tales y los nombres de partida leídos
  Y el resumen sale de la preparación, no del modelo real
  Y el modelo real no tiene ninguna fila de esa importación
```

#### CA-8 `[M]` · Rechazo · Errores del análisis por hoja y fila · `HDU-001 esc. 6 a 9, 27 y 28`

```gherkin
Esquema del escenario: La lista de errores devuelve cada fila afectada con su tipo
  Dado que el análisis dejó la importación en CON_ERRORES con errores de tipo <tipo>
  Cuando se consulta la lista de errores, con o sin filtro de hoja y de tipo
  Entonces cada renglón trae hoja, fila, columna, tipo y detalle
  Y el renglón <tipo> conserva el valor original o el código que lo causó

  Ejemplos:
    | tipo                |
    | REF_ROTA            |
    | SIN_APU             |
    | UNIDAD_DESCONOCIDA  |
    | DUPLICADO           |
    | SIN_CONCEPTOS       |
    | RENDIMIENTO_AUSENTE |
```

#### CA-9 `[M]` · Rechazo · Confirmar una importación con errores · `RN-01` · `HDU-001 esc. 6 a 9, 27 y 28`

```gherkin
Escenario: Una importación CON_ERRORES no se confirma
  Dado que la importación está en CON_ERRORES
  Cuando el Director de Proyectos intenta confirmarla
  Entonces responde 409 CONFLICTO con código IMPORTACION_CON_ERRORES
  Y no se escribe nada en el modelo real ni en la línea base
  Y las filas válidas de la preparación se conservan
```

#### CA-10 `[M]` · Análisis interrumpido y reintento · `RNF-17` · `HDU-001 esc. 29`

```gherkin
Escenario: Una interrupción deja un único error y admite reintentar
  Dado que un análisis en curso se interrumpe por reinicio, excepción o muerte del trabajador
  Cuando se registra la interrupción
  Entonces la importación queda en CON_ERRORES con un único renglón PROCESO_INTERRUMPIDO cuyo mensaje distingue la causa
  Y no queda preparación persistida de ese análisis
  Y la obra vuelve a admitir otra importación
  Y pedir de nuevo el análisis de esa importación está admitido
  Y el barrido de arranque no modifica una importación cuyo latido sigue vigente ni una que ya salió de ANALIZANDO
```

#### CA-11 `[M]` · Confirmar con la asignación de tipos · `RN-01`, `RN-02` · `HDU-001 esc. 11`

```gherkin
Escenario: La confirmación materializa la línea base en BORRADOR
  Dado que la importación está en VALIDADO y el cuerpo trae asignacion_tipos_partida con un tipo por cada nombre de partida leído
  Cuando el Director de Proyectos confirma
  Entonces la ruta invoca materializar_importacion de la interfaz de presupuesto
  Y crea niveles, áreas, partidas, conceptos y análisis de precio unitario con sus insumos en una sola transacción
  Y la importación queda en CONFIRMADO y la línea base en BORRADOR
```

#### CA-12 `[M]` · Rechazo · Tipos de partida sin asignar o inexistentes · `RN-02`

```gherkin
Escenario: Un nombre de partida sin tipo, o con un tipo que no existe, no se confirma
  Dado que la importación está en VALIDADO
  Cuando la confirmación omite un nombre de partida leído o le asigna un tipo_partida_id que no existe
  Entonces responde 422 VALIDACION con el campo "asignacion_tipos_partida.{nombre}" y su código
  Y la importación sigue en VALIDADO y no se escribe nada en el modelo real
```

#### CA-13 `[M]` · Rechazo · Fallo a mitad de la confirmación · `HDU-001 esc. 12`

```gherkin
Escenario: Un error al escribir un registro revierte toda la confirmación
  Dado que la confirmación escribe y falla al registro 3,000 de 4,900
  Cuando la transacción se interrumpe
  Entonces ningún dato de esa importación queda en el modelo real
  Y la importación sigue en VALIDADO
  Y la respuesta es el error interno del contrato de error con el identificador de correlación, sin dejar la obra en estado intermedio
```

#### CA-14 `[M]` · Rechazo · Reimportar sobre un `BORRADOR` · `RN-01` · `HDU-001 esc. 13`

```gherkin
Escenario: Reemplazar el BORRADOR exige una confirmación explícita y deja rastro
  Dado que la obra tiene una línea base en BORRADOR
  Cuando el Director de Proyectos confirma una importación nueva sin reemplazar_borrador
  Entonces responde 409 REGLA_NEGOCIO o CONFLICTO según el catálogo, con código REEMPLAZO_NO_CONFIRMADO y la acción CONFIRMAR_REEMPLAZO
  Y el BORRADOR anterior sigue intacto

Escenario: Reemplazo confirmado con motivo
  Dado que la obra tiene un BORRADOR
  Cuando confirma con reemplazar_borrador y un motivo_reemplazo válido
  Entonces el BORRADOR anterior se descarta y se crea la nueva línea base
  Y la bitácora asienta el reemplazo con el motivo, en la misma transacción
```

#### CA-15 `[M]` · Rechazo · `motivo_reemplazo` con `NUL` o demasiado largo · Deuda de TKT-017

```gherkin
Escenario: El motivo de reemplazo no puede romper la persistencia
  Dado que se confirma con reemplazar_borrador
  Cuando motivo_reemplazo contiene el carácter NUL o supera el tope de longitud
  Entonces responde 422 VALIDACION sobre el campo motivo_reemplazo
  Y no se escribe nada en el modelo real ni en la bitácora
  Y no se produce un error 500 de la base de datos
```

El tope lo fija el diseño reutilizando el tipo de motivo que TKT-018a ya usa (`MotivoTexto` o equivalente).

#### CA-16 `[M]` · Descartar una importación · `RN-01` · `HDU-001 esc. 13`

```gherkin
Escenario: Descartar una importación CON_ERRORES o VALIDADO
  Dado que la importación está en CON_ERRORES o en VALIDADO
  Cuando el Director de Proyectos la descarta con un motivo
  Entonces la importación queda descartada, la bitácora lo asienta con el motivo y la obra admite otra importación

Escenario: Descartar sin motivo o en un estado que no lo admite
  Dado que no se envía motivo, o que la importación está en CONFIRMADO
  Cuando se intenta descartar
  Entonces responde 422 VALIDACION por el motivo, o 409 CONFLICTO con código ESTADO_NO_PERMITE_OPERACION
  Y la importación conserva su estado
```

#### CA-17 `[M]` · Rechazo · Permisos y existencia · `RN-01`

```gherkin
Escenario: Roles y recursos ajenos
  Dado que la petición viene sin sesión, o de un rol que no es Director de Proyectos
  Cuando intenta crear, analizar, confirmar o descartar
  Entonces responde 401, o 403 con el contrato de error PERMISO y motivo ROL_INSUFICIENTE, y el estado no cambia
  Y Dirección General puede listar, consultar y ver los errores, pero no escribir
  Y una importación o una obra inexistentes responden 404
```

#### CA-18 `[M]` · Catálogo de tipos de partida para la asignación

```gherkin
Escenario: Listar los cuatro tipos de partida
  Dado que el catálogo de tipos de partida está sembrado
  Cuando un usuario autenticado de los roles del borrador consulta la lista
  Entonces recibe los cuatro tipos con su identificador y nombre, sin paginar
```

### Frontend

#### CA-19 `[M]` · Carga del archivo y progreso sin bloquear · `HDU-001 esc. 4 y 24` · Boceto 3a

```gherkin
Escenario: El Director de Proyectos carga el Excel y sigue trabajando
  Dado que está en la pantalla de importación de una obra sin línea base congelada
  Cuando elige un archivo .xlsx
  Entonces el navegador calcula el SHA-256 y el tamaño, crea la importación, sube directo al almacén con la URL prefirmada, confirma el archivo y pide el análisis
  Y la pantalla muestra tres barras: subida, verificación y análisis, esta última con el porcentaje de progreso
  Y consulta el progreso cada 3 segundos (asumido) y no bloquea la navegación
  Y al llegar a VALIDADO pasa a la previsualización y al llegar a CON_ERRORES, a la tabla de errores
```

#### CA-20 `[M]` · Rechazo · Rechazos de carga mostrados al usuario · `HDU-001 esc. 21, 24, 25 y 26` · Boceto 3a

```gherkin
Escenario: Cada rechazo de la carga se explica y no deja una importación colgada
  Dado que el servidor responde 422 por el formato, o ARCHIVO_HASH_DISTINTO, ARCHIVO_TAMANO_DISTINTO o ARCHIVO_TIPO_NO_PERMITIDO, o ARCHIVO_NO_DISPONIBLE
  Cuando la pantalla recibe la respuesta
  Entonces el 422 aparece junto al selector con el mensaje de que solo se admite .xlsx
  Y el hash o el tamaño muestran lo declarado frente a lo almacenado y ofrecen «Volver a subir»
  Y el tipo rechazado muestra el tipo detectado y los formatos admitidos
  Y en ningún caso se pinta la importación como analizándose
```

#### CA-21 `[M]` · Previsualización y asignación de tipos · `RN-02` · `HDU-001 esc. 5 y 10` · Boceto 3b

```gherkin
Escenario: La previsualización muestra lo leído y exige asignar tipos
  Dado que la importación está en VALIDADO
  Cuando el Director de Proyectos abre la previsualización
  Entonces ve los conteos, el importe total y los insumos creados durante la importación marcados para revisión
  Y ve una fila por cada nombre de partida leído con un selector de uno de los cuatro tipos
  Y el botón «Confirmar» está deshabilitado mientras quede una partida sin tipo
```

#### CA-22 `[M]` · Rechazo · Confirmar con reemplazo, concurrencia y fallo · `RN-01` · `HDU-001 esc. 12 y 13` · Boceto 3b

```gherkin
Escenario: Los rechazos de la confirmación se resuelven en la pantalla
  Dado que el Director de Proyectos confirma
  Cuando el servidor responde REEMPLAZO_NO_CONFIRMADO
  Entonces se abre el diálogo del reemplazo, exige el motivo y reenvía con reemplazar_borrador
  Y si responde 422 en "asignacion_tipos_partida.{nombre}", marca esa partida
  Y si responde CONCURRENCIA o un error interno, muestra el mensaje y el identificador de correlación y la importación sigue en VALIDADO
  Y al confirmar con éxito navega a la línea base en BORRADOR
```

#### CA-23 `[M]` · Rechazo · Tabla de errores y bloqueo de confirmar · `HDU-001 esc. 6 a 9 y 27 a 29` · Boceto 3c

```gherkin
Escenario: La tabla de errores es navegable y el botón Confirmar no existe como acción
  Dado que la importación está en CON_ERRORES
  Cuando se abre la pantalla de errores
  Entonces se ve la tabla Hoja · Fila · Columna · Tipo · Detalle con filtros por tipo y hoja y paginación
  Y «Confirmar» aparece deshabilitado
  Y con PROCESO_INTERRUMPIDO se ofrece «Reintentar análisis»
  Y «Subir archivo corregido» inicia una importación nueva
```

#### CA-24 `[M]` · Entrada desde la pantalla de la línea base · Regresión de TKT-018a

```gherkin
Escenario: El estado vacío ofrece importar
  Dado que la obra no tiene línea base
  Cuando el Director de Proyectos abre la pantalla de la línea base
  Entonces ve una acción «Importar presupuesto» que lleva a la pantalla de importación
  Y no ve el texto «llegará en una próxima entrega (TKT-018b)»

Escenario: Dirección General no ve la acción de importar
  Dado que el usuario es Dirección General
  Cuando abre la misma pantalla
  Entonces no ve la acción de importar, pero sí el estado y las cifras
```

#### Criterio descartado · Borrador más nuevo que la `CONGELADA`

La persona dueña decidió el 2026-11-11 que una obra con línea base `CONGELADA` **no** reimporta (`RN-01`, `CA-3`). Por eso nunca coexisten una `CONGELADA` y un `BORRADOR` más nuevo, y la deuda de TKT-018a sobre ver ese borrador deja de aplicar. No hay criterio para ello.

#### Regresión

- **`CA-R1` `[M]`** · Con la importación en `VALIDADO` o `CON_ERRORES`, la línea base `CONGELADA` y el disparador de inmutabilidad no cambian, y ninguna ruta nueva escribe en las copias congeladas (`INV-05`, `INV-14`).
- **`CA-R2` `[M]`** · Las pruebas de la pantalla de la línea base de TKT-018a (estado, borrador, congelada, motivo del congelado) siguen en verde, salvo el texto del estado vacío que este ticket cambia a propósito.
- **`CA-R3` `[M]`** · Las pruebas de TKT-013 a TKT-015 y de `materializar_importacion` (TKT-017) siguen en verde sin cambiar su comportamiento. La única diferencia es la guarda del archivo `DISPONIBLE` al iniciar el análisis.
- **`CA-R4` `[M]`** · El OpenAPI publicado coincide con las rutas implementadas y `npm run tipos:verificar` pasa con los tipos regenerados.

#### Should

- **`S1`** · «Exportar errores» genera un CSV con las filas filtradas y cargadas, sin ruta nueva `(asumido)`.
- **`S2`** · Con `CIMENTA_CATALOGO_UNION` y `CIMENTA_CATALOGO_ENITI`, las 26 pruebas omitidas por `PA-T3` corren y las suposiciones de `PA-T17.9` quedan medidas.
- **`S3`** · Un E2E de Playwright sube un `.xlsx` al almacén real, previsualiza, asigna tipos y confirma.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Con reserva | Depende de TKT-059, sin ejecutar: sus cinco entregas no están hechas. La spec es independiente, la ejecución no |
| **N** | Describe el qué, no impone el cómo | Sí | Las rutas y los códigos salen del borrador; el diseño decide cómo se arma el resumen y cómo se consulta el archivo |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Hoy ninguna ruta crea una línea base: sin esto el hilo vertical no arranca |
| **E** | Estimable sin investigar antes | Con reserva | Quedan huecos de contrato (`Q-1` a `Q-3`) y la interfaz de TKT-059 aún no existe. Ambos se cierran en el diseño |
| **S** | Cabe en una sesión sin romper contexto | No | Backend y frontend, siete rutas y tres pantallas. El diseño debe partirlo en entregas (backend, pantallas 3a y 3b, pantalla 3c) con un solo PR |
| **T** | Sus criterios se pueden ejecutar | Sí | Todos tienen su rechazo; los de archivo se prueban con la interfaz de TKT-059 o una prueba doble hasta que exista |

Un fallo claro (**S**) y dos reservas. Por el sesgo del proyecto se acepta con las entregas que el diseño fije; si el diseño no puede partirlo, se vuelve a refinamiento.

## Definition of Done

La de una funcionalidad, de `sdd/metodologia.md`.

- [ ] Cada criterio `[M]` tiene su test con el nombre del escenario y el rechazo prueba el contrato de error completo
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float`, `pytest`, `eslint`, `tsc`, `npm test`, `tipos:verificar` y `verificar_docs` en verde
- [ ] `docs/api/openapi.yaml` y `docs/07-especificacion-api.md` corregidos y coherentes con lo implementado, con las operaciones atribuidas a `TKT-018b`
- [ ] Wireframe §3 actualizado con lo decidido (asignación de tipos y motivo de reemplazo)
- [ ] `tools/historias_activas.txt` revisado: HDU-001 **no** se activa en este ticket
- [ ] Delta con la deuda que quede (`S2`, `F001` de TKT-018a)

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| `Q-1` | **Hallazgo D2.** El contrato no publica los nombres de partida a los que el Director de Proyectos asigna tipo. La persona dueña decidió corregirlo en el diseño | Sin los nombres la asignación no se puede pintar ni validar | Decidido: corrección del OpenAPI en `/sdd-disenar`, con revisión humana |
| `Q-2` | **Hallazgo D1.** `ResumenImportacion.por_tipo_partida` exige el tipo, pero el tipo se asigna después en la previsualización (`PA-T8`). Se propone que en `VALIDADO` el resumen no traiga el desglose por tipo | El boceto 3b pinta «Por tipo de partida» antes de asignar | Decidido con `Q-1` |
| `Q-3` | **Hallazgo D3.** Nadie construye `importacion.resumen`; `PA-15.10` de TKT-015 lo pasó a TKT-018 | Sin resumen no hay previsualización | Este ticket lo construye. Dónde y cuándo (al terminar el análisis o al consultar) lo fija el diseño |
| `Q-4` | Esc. 25 y 26: dueño de los tests | Doble dueño rompe el verificador de escenarios | Decidido: TKT-059 es dueño; aquí solo la consecuencia (`CA-6`, `CA-20`) |
| `Q-5` | La interfaz de TKT-059 no prevé consultar el estado de un archivo; `presupuesto` lo necesita para `CA-4` y `CA-5` | Sin esa consulta no hay guarda `DISPONIBLE` | Pendiente: añadirlo al diseño de TKT-059 o publicarlo en su entrega c. Se eleva a la persona dueña en el gate de diseño |
| `Q-6` | Tipo exacto del `409` al crear sobre una obra con congelada (`REGLA_NEGOCIO` `RN-01` o `CONFLICTO`; con `Q-7` decidido, la obra congelada rechaza siempre), y el de `REEMPLAZO_NO_CONFIRMADO` (el catálogo ya lo define) | Una `RN` inventada o un código mal etiquetado | `(asumido)`: `RN-01` por el borrador; el diseño lo confirma contra `catalogos.py` |
| `Q-7` | ¿Una obra con `CONGELADA` puede reimportar? | `CA-3` y la deuda de TKT-018a sobre ver un borrador más nuevo | Decidido el 2026-11-11 por la persona dueña: no (`RN-01`). `CA-3` se mantiene y el criterio del borrador más nuevo se descartó |
| `Q-8` | Estados en que se admite descartar (`CON_ERRORES` y `VALIDADO`) y el código para el resto | `RECIBIDO` colgado sin salida | `(asumido)` en `CA-16`; el diseño lo confirma. El descarte cita el esc. 13 pero ese escenario es el reemplazo (hallazgo D4) |
| `Q-9` | Intervalo de consulta del progreso: 3 segundos | Carga o lentitud en la pantalla | `(asumido)`; lo decidió la persona dueña como parte del `S1` |
| `Q-10` | Formato de la exportación de errores: CSV en el cliente | Una ruta nueva en el servidor | `(asumido)`; `S1` |
| `Q-11` | Esc. 4 de HDU-001 dice que la importación se registra en `ANALIZANDO`, mientras el 24 y el borrador la crean en `RECIBIDO` (hallazgo D6) | Dos estados iniciales | La spec sigue el 24 y el borrador. Se registra para corregir la historia |
| `Q-12` | `PROCESO_INTERRUMPIDO` por archivo ilegible lleva la causa `ARCHIVO_ILEGIBLE` en el código (hallazgo D5), pero la historia no la nombra | Mensaje distinto del esperado | `(asumido)`: el mensaje distingue la causa; el diseño la documenta |
| `Q-13` | Sin costo externo: el almacén de objetos es MinIO propio (TKT-059, TKT-073); ninguna clave de pago | Recorte si hubiera presupuesto | Confirmado por la persona dueña el 2026-11-11 |
| `Q-14` | Límites de tamaño del archivo `(asumido)` (`PA-15`) | El 422 por tamaño declarado cambia | Heredado de TKT-059 |

**Dependencias cruzadas** (búsquedas del 2026-11-11 sobre `docs/05-tickets-trabajo.md`, `sdd/tickets/*/_index.md` y `tools/historias_activas.txt`):

- `tools/historias_activas.txt` está vacía: ninguna historia activa.
- `sdd/tickets/tkt-015/_index.md` l.58: «el `resumen` de previsualización sale del Should y pasa a TKT-018 (`PA-15.10`)». Es dependencia, no pregunta.
- `docs/05-tickets-trabajo.md` l.804: TKT-018 depende de TKT-017, TKT-012 y TKT-059; TKT-018b hereda TKT-018a y TKT-059.
- `sdd/tickets/tkt-059/_index.md` l.60: TKT-059 es dueño de los tests de HDU-001 esc. 25 y 26 y TKT-018, del 24.
- `sdd/tickets/tkt-012a/delta.md` l.111: `listar_tipos_partida` y `listar_insumos` se construyen con su primer consumidor; este ticket construye `listar_tipos_partida`.
- Los escenarios 1 a 3 son de TKT-012a, el 20 de TKT-012b y el 16 de TKT-021. HDU-001 **no se activa** en este ticket: le faltan esos escenarios y la persona dueña mantuvo la historia sin activar en TKT-017 (`P-13`). Se activa en el último ticket que cierre la historia.

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **La ejecución no puede empezar.** TKT-059 no tiene código y su interfaz prometida no incluye consultar el estado de un archivo; sin ello `CA-4` y `CA-5` no se pueden probar con el almacén real | Registrado en la ficha y en `Q-5`. Se eleva a la persona dueña en el gate de diseño; mientras tanto los criterios de archivo se prueban con una prueba doble de la interfaz |
| 2 | Alta | **Tamaño.** Siete rutas más ocho para pantallas, en un ticket con una sola ventana de PR | INVEST marca **S** como fallo; el diseño debe partirlo en entregas con un solo PR y un disparador de recorte para `S1` a `S3` |
| 3 | Alta | **El contrato no basta para la asignación.** Sin nombres de partida publicados el criterio `CA-21` no se puede probar | `Q-1` y `Q-2`: se corrige el OpenAPI en el diseño. Si la persona dueña lo rechaza, `CA-11`, `CA-12` y `CA-21` cambian |
| 4 | Media | Los esc. 25 y 26 podrían quedar sin test si TKT-059 los recorta | `CA-6` y `CA-20` prueban la consecuencia; el verificador de escenarios seguirá apuntando a TKT-059 |
| 5 | Media | `CA-3` inventa una regla si el `409` de la congelada no es una `RN` | Se deja `(asumido)` y se obliga al diseño a confirmar el tipo contra el catálogo cerrado (`Q-6`) |
| 6 | Media | `CA-13` pide «error interno» sin nombre de tipo | El diseño lo ata al contrato de error ya implementado; no se inventa un tipo |
| 7 | Baja | La demostración de `S3` depende de MinIO en el trabajo `humo` | Disparador de recorte declarado; no bloquea ningún `[M]` |

## Contexto técnico

Archivos y objetos relevantes que existen hoy:

- `backend/cimenta/presupuesto/aplicacion/analisis_importacion.py`: `iniciar_analisis`, `solicitar_analisis`, `registrar_resultado`, `registrar_interrupcion`, `obtener_preparacion`, `SeguimientoImportacion`. Hoy `iniciar_analisis` no comprueba el estado del archivo.
- `backend/cimenta/presupuesto/interfaz.py`: `materializar_importacion(contexto, *, importacion_id, asignacion_tipos_partida, reemplazar_borrador, motivo_reemplazo, usuario_id) -> LineaBaseMaterializada`.
- `backend/cimenta/presupuesto/infraestructura/repositorio_importacion.py`: sin alta ni listado ni consulta de errores.
- `backend/cimenta/presupuesto/api/montaje.py`: monta solo obras, línea base y presupuesto de control. No hay ruta de importación.
- `backend/cimenta/archivos/`: solo `__init__.py` y un `interfaz.py` vacío; ninguna migración crea `archivo`.
- `backend/contrato_error/catalogos.py`: ya trae `IMPORTACION_CON_ERRORES`, `REEMPLAZO_NO_CONFIRMADO`, `ARCHIVO_NO_DISPONIBLE`, `IMPORTACION_EN_CURSO` y `ESTADO_NO_PERMITE_OPERACION`.
- `backend/servidor/fabrica.py`: arma el ejecutor del análisis con un lector del contenido no configurado, que lleva el análisis a `ARCHIVO_ILEGIBLE`; TKT-059e lo conecta.
- `docs/api/openapi.yaml` y `docs/07-especificacion-api.md` l.275-281: las siete operaciones, atribuidas a `TKT-018`.
- `frontend/src/modulos/presupuesto/`: `obras/` y `linea-base/`; `rutas.tsx` declara `obras` y `obras/:obraId/linea-base`. Los tipos generados no traen importaciones ni archivos.
- `frontend/src/modulos/presupuesto/linea-base/PantallaLineaBase.tsx` l.68: el texto del estado vacío que este ticket reemplaza.
- `docs/08-wireframes.md` §3 (pantallas 3a, 3b, 3c); la asignación de tipos y el motivo de reemplazo no están dibujados.
- ADR relevantes: `adr/20261001-almacenamiento-de-objetos.md` (ADR-016), `adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md` (ADR-037), `adr/20261105-preparacion-de-importacion-en-jsonb.md` (ADR-036), `adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` (ADR-031).
