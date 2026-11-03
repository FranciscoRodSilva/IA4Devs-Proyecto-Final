# Spec · TKT-015 · Validaciones y reporte de errores por fila

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

La importación de la línea base (HDU-001) ya tiene dos lectores en memoria: el del catálogo de conceptos (TKT-013) y el de los análisis de precio unitario (TKT-014). Ambos devuelven **hallazgos crudos** —22 causas internas como `ERROR_DE_FORMULA` o `PU_NO_CUADRA`— y ninguno decide qué hace el sistema con ellos. Hoy tampoco existe quien ejecute el análisis, deje constancia de su resultado en `importacion` e `importacion_error`, ni quien impida que un reinicio del servidor deje una importación en `ANALIZANDO` para siempre. TKT-015 construye esa pieza: **traduce los hallazgos a los siete tipos de error de la importación, decide si la importación queda `VALIDADO` o `CON_ERRORES`, conserva lo válido para no repetir el análisis, ejecuta el análisis fuera del proceso del API y recupera las importaciones interrumpidas** (`RNF-17`).

Lo que muestran los dos archivos reales, medido el 2026-11-03 con `leer_libro_presupuesto` sobre las copias de `D:\Documentos\Miich\Documentos\` (el diseño lo reconfirma en su fila de arranque, como hizo TKT-014):

| | ENITI Torre 5 | Union Square F2 |
|---|---|---|
| Conceptos y códigos distintos | 5,028 conceptos, 36 códigos | 4,281 conceptos, 31 códigos |
| Hallazgos del catálogo | ninguno | `ERROR_DE_FORMULA` 8,562 (la celda de P.U. y la de importe de cada concepto), `NOMBRE_ILEGIBLE` 21, `CONCEPTO_SIN_PARTIDA` 5 |
| Hallazgos de las hojas de APU | `CARGO_DESCONOCIDO` 20 (`SIROC`), `ERROR_DE_FORMULA` 5 | ninguno |
| Hallazgos del libro | `CODIGO_EN_VARIAS_HOJAS` 6, `ANALISIS_SIN_CODIGO` 1 | `ANALISIS_SIN_CODIGO` 20 |
| Códigos del catálogo sin hoja de APU (`SIN_APU`) | 16 de 36 | los 31 |
| Códigos con descripciones distintas (`DUPLICADO` del esc. 9) | 0 | 0 |
| Insumos por crear | 29 | 23 |

Tres hechos condicionan la especificación:

- **Ningún archivo real llega a `VALIDADO`.** Union Square tiene `#REF!` en todos los precios y ningún APU asociado; ENITI tiene 16 códigos sin APU y un cargo `SIROC` fuera de catálogo. El camino `VALIDADO` solo se prueba con un libro sintético (`PA-T3` de TKT-013: en CI los archivos reales se omiten con `skip` explícito y un fixture sintético con la misma estructura cubre el pipeline).
- **`DUPLICADO` literal no se dispara en ningún archivo real.** Los dos repiten cada código por área, pero con la misma descripción. El esc. 9 dice «el mismo código con descripciones **distintas**»; esta spec lo toma al pie de la letra (decisión de la persona dueña, 2026-11-03). Qué hacer con el código repetido de descripción igual frente a `UNIQUE (obra_id, codigo)` (invariante 13) es `PA-T1` de TKT-013 y **sigue abierto para TKT-017**.
- **El CHECK de `importacion_error.tipo` admite siete tipos y el lector produce 22 causas.** Dieciocho no tienen tipo propio. La persona dueña decidió el 2026-11-02 no ampliar el CHECK y el 2026-11-03 que cada causa sin tipo propio se persiste en el **tipo más cercano**, con la causa cruda dentro del `mensaje`.

## Historia de usuario

**Como** Director de Proyectos
**quiero** que, al analizar mi Excel, el sistema me diga fila por fila qué está roto y no me deje confirmar mientras haya un error
**para** corregir el archivo antes de que algo llegue a la línea base, sin que un análisis largo o un reinicio del servidor me deje la obra bloqueada.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Clasificar todo hallazgo del análisis en los siete tipos de `importacion_error` (`REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO`, `SIN_CONCEPTOS`, `PROCESO_INTERRUMPIDO`), cada uno con hoja, fila, columna, tipo, mensaje y valor original. Todo error es bloqueante y ningún hallazgo se pierde en silencio |
| **Must** | **M2.** Dejar la importación en `VALIDADO` si no hay ningún error y en `CON_ERRORES` si hay uno solo, de modo que no se pueda confirmar. Una hoja sin ninguna fila de concepto es `SIN_CONCEPTOS` |
| **Must** | **M3.** Reportar el catálogo de Union Square, que trae `#REF!` en todas las columnas de precio, fila a fila: nunca fallar en bloque ni importar celdas rotas como ceros |
| **Must** | **M4.** Persistir el resultado válido del análisis como preparación, para no repetirlo al confirmar |
| **Must** | **M5.** Ejecutar el análisis en un `ProcessPoolExecutor` de un trabajador, con `latido` y `progreso` actualizados mientras corre, y con una salida para la excepción inesperada |
| **Must** | **M6.** Barrido de arranque: toda importación `ANALIZANDO` con latido vencido pasa a `CON_ERRORES` con un error `PROCESO_INTERRUMPIDO`, y la obra vuelve a admitir importaciones (`RNF-17`) |
| **Must** | **M7.** Construir el barrido como mecanismo reutilizable —trabajos en dos pasos cuyo segundo puede no ocurrir— que TKT-059 usará para `archivo` |
| **Should** | **S1.** Los contadores `filas_leidas`, `filas_validas` y `filas_rechazadas` de `importacion` |
| **Could** | — |
| **Won't** | Rutas, esquemas de respuesta y pantalla de importación (TKT-018, dueño de las tres rutas del OpenAPI que también citan a TKT-015) · confirmar, materializar o congelar (TKT-017) y el `409` al intentar confirmar una importación `CON_ERRORES` · el `resumen` de previsualización (`niveles`, `areas`, `importe_total`, `por_tipo_partida`, `insumos_creados`): TKT-018 lo calcula desde la preparación, porque `por_tipo_partida` depende de `PA-T8` · ampliar el CHECK de `importacion_error.tipo` o de `apu_cargo.tipo` · cambiar el invariante 13 o resolver el código repetido de descripción igual (`PA-T1`, TKT-017) · asociar nombres de partida con tipos de partida (`PA-T8`) · la regla `IMPORTACION_EN_CURSO` al crear una importación (TKT-018) · el adaptador del almacén de objetos (TKT-059) · corregir o editar valores · asentar el análisis en la bitácora |

## Partición en dos entregas

La persona dueña aprobó el 2026-11-03 partir el ticket en dos entregas con un PR cada una, como TKT-013 y TKT-014. El orden de fusión es fijo: **TKT-015a y después TKT-015b**. TKT-015 queda como paraguas, conserva esta spec y el diseño, y se cierra cuando se cierran las dos. TKT-017 y TKT-059 pasan a depender de TKT-015b (TKT-018 depende de TKT-017). TKT-016 no depende de este ticket: solo necesita la lectura de TKT-014b.

| Entrega | Contenido | Criterios |
|---|---|---|
| TKT-015a | Clasificación en `dominio/`, preparación persistida (migración `0009`) y caso de uso síncrono, con las pruebas contra los archivos reales | `M1` a `M4`, `S1`; `CA-1` a `CA-11`, `CA-18`, `CA-S1`, `CA-R1` a `CA-R3` |
| TKT-015b | Ejecutor en proceso aparte, latido y progreso, barrido reutilizable en `trabajos/` y arranque | `M5` a `M7`; `CA-12` a `CA-17` (TKT-015a cubre la parte síncrona de `CA-12`, `CA-14`, `CA-15` y `CA-16`); `CA-R1` y `CA-R2` del lector con avance y del paquete nuevo |

En TKT-015a, los criterios que dicen «se analiza la importación» se ejecutan en secuencia con `iniciar_analisis`, `analizar_contenido` y `registrar_resultado`, en el hilo de la prueba. `CA-11` (segundo escenario) y `CA-18` (reintento) se cubren con `registrar_interrupcion` e `iniciar_analisis`, y TKT-015b los repite con la excepción real y con la muerte del trabajador (`CA-14`) y con la solicitud encolada. El detalle está en el apartado «Partición propuesta» de [design.md](design.md).

## Non-goals

- No expone ninguna ruta HTTP. El caso de uso se prueba directamente y TKT-018 lo invoca desde sus rutas.
- No corrige errores ni permite editar valores: un archivo corregido es una importación nueva.
- No escribe en el modelo real (`concepto`, `insumo`, `linea_base`…). Solo escribe en `importacion`, `importacion_error` y la preparación (`RN-01` por omisión).
- No crea la fila `importacion` ni valida el archivo por sus bytes: ambas cosas son de TKT-018 y TKT-059. El análisis solo recibe el contenido de un archivo que ya pasó esa comprobación.
- No cambia lo que leen los lectores de TKT-013 y TKT-014: clasifica lo que ellos devuelven.
- No cambia el modelo de datos más allá de lo que exija persistir la preparación, ni el catálogo de tipos de error del borrador OpenAPI.

## Reglas de negocio implicadas

Ninguna `RN-xx` gobierna la clasificación. Los rechazos cuelgan de los escenarios de HDU-001, de `RNF-17` y de `RNF-06`.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RNF-17` | Un trabajo en segundo plano interrumpido no queda colgado: se detecta y se marca como fallido. Si el servidor se reinicia mientras analiza, la obra no puede quedar sin admitir otra importación | PRD §9 — `docs/01-descripcion-producto.md` |
| `RNF-06` | El analizador no recibe un archivo que no haya pasado la comprobación de tipo por bytes de TKT-059 | PRD §9 y `docs/05-tickets-trabajo.md` (TKT-018) |
| `RN-01` | Nada se escribe en el modelo real antes de confirmar. El análisis solo la respeta por omisión | PRD §8 |
| Regla 1 de `CLAUDE.md` | El dinero nunca es flotante: la preparación guarda `Decimal` y lo serializa como cadena | `CLAUDE.md` |
| Invariante 27 | `insumo.unidad` solo admite las ocho unidades del catálogo cerrado: fuente de `UNIDAD_DESCONOCIDA` | `docs/03-modelo-datos.md` |

## Invariantes que deben sobrevivir al cambio

El ticket añade una capa sobre los lectores y reutiliza `importacion` e `importacion_error`. Estas garantías ya vigentes no pueden romperse.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Resultado de los lectores | Las cifras de TKT-013 y TKT-014 (4,281 y 5,028 conceptos; 44 hojas de APU) no cambian por clasificarlas | `CA-R1` |
| Reglas 1 y 2 de `CLAUDE.md` y fronteras | `dominio/` puro, sin `float` y sin cruzar módulos | `CA-R2` |
| Invariante 13 (`UNIQUE (obra_id, codigo)`) y CHECK de siete tipos | Este ticket no los toca; `DUPLICADO` literal no resuelve `PA-T1` | `CA-R3` |

## Criterios de aceptación

Gherkin, en español. Los escenarios de HDU-001 son 4 a 9 y 27; `RENDIMIENTO_AUSENTE` y `PROCESO_INTERRUMPIDO` no tienen escenario en la historia (`PA-15.11`). Los rechazos devuelven un resultado persistido, no un error HTTP: este ticket no tiene rutas. Los datos citados salen de la tabla de arriba.

### CA-1 `[M]` · Un libro sin errores queda `VALIDADO` · `HDU-001 esc. 4 y 5`

```gherkin
Escenario: Libro válido de punta a punta
  Dado una importación en estado RECIBIDO cuyo archivo es un libro sintético con catálogo y un APU por cada código,
       unidades dentro de las ocho admitidas, rendimientos presentes y ningún código repetido con descripción distinta
  Cuando se analiza la importación
  Entonces la importación pasa por ANALIZANDO y termina en VALIDADO
  Y no existe ninguna fila de importacion_error para ella
  Y la preparación contiene la jerarquía, los conceptos, los análisis y los insumos por crear que leyeron los lectores
  Y las tablas del modelo real (concepto, insumo, linea_base y sus hijas) conservan exactamente las filas que tenían
```

### CA-2 `[M]` · Rechazo · `#REF!` en celdas de precio, un error por celda · `HDU-001 esc. 6`

```gherkin
Escenario: Celdas de fórmula rota
  Dado un libro sintético de 200 conceptos donde tres traen #REF! en la columna de P.U. y en la de importe
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES
  Y existen exactamente seis errores REF_ROTA, uno por celda rota
  Y cada uno lleva la hoja, la fila y la columna de su celda, un mensaje en español y el valor original "#REF!"
  Y la importación no es confirmable: su estado es CON_ERRORES
  Y las 197 filas sin error se conservan en la preparación
```

### CA-3 `[M]` · Rechazo · El catálogo real de Union Square se reporta fila a fila · `HDU-001 esc. 6`

```gherkin
Escenario: Union Square no falla en bloque
  Dado una importación RECIBIDO cuyo archivo es AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx
  Cuando se analiza la importación
  Entonces termina en CON_ERRORES, sin excepción y sin dejar la fila en ANALIZANDO
  Y los 8,562 hallazgos ERROR_DE_FORMULA del catálogo se persisten como errores REF_ROTA, cada uno con su hoja, fila y columna, dentro de un total de 8,608 REF_ROTA
  Y los 31 códigos sin hoja de APU se persisten como 31 errores SIN_APU
  Y ninguna celda rota se importó como cero: los 4,281 conceptos traen al menos una celda rota, así que quedan todos rechazados
  Y las cifras son filas_leidas 4,281, filas_validas 0 y filas_rechazadas 4,281, con la preparación sin ningún concepto
```

Se omite con `skip` explícito y visible donde el archivo no esté (`PA-T3` de TKT-013). Las cifras salen de la medición del 2026-11-03, que un revisor independiente repitió el mismo día con el mapa de causas aprobado: 8,562 `ERROR_DE_FORMULA` más 21 `NOMBRE_ILEGIBLE`, 5 `CONCEPTO_SIN_PARTIDA` y 20 `ANALISIS_SIN_CODIGO` dan 8,608 `REF_ROTA`, y con los 31 `SIN_APU` suman 8,639 errores. «Que no se importa como cero» se prueba además con un libro sintético en `CA-2`, donde sí quedan conceptos válidos.

### CA-4 `[M]` · Rechazo · Concepto sin análisis de precio unitario · `HDU-001 esc. 7`

```gherkin
Escenario: Un código del catálogo sin hoja de APU
  Dado un libro sintético con tres códigos en el catálogo y hojas de APU solo para dos
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES
  Y existe un único error SIN_APU cuyo valor original es el código del tercero
  Y su mensaje nombra ese código y explica que sin análisis de precio unitario no se puede calcular la explosión de insumos de ese concepto
```

### CA-5 `[M]` · Rechazo · Unidad que no está en el catálogo · `HDU-001 esc. 8`

```gherkin
Escenario: Unidad desconocida en una fila del catálogo
  Dado un libro sintético cuya fila 57 del catálogo trae la unidad "XYZ"
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES
  Y existe un error UNIDAD_DESCONOCIDA con la hoja, la fila 57, la columna de la unidad y el valor original "XYZ"
  Y las demás filas con unidad válida no generan error de unidad
```

### CA-6 `[M]` · Rechazo · Rendimiento ausente en un APU · ticket TKT-015

```gherkin
Escenario: Un insumo del APU sin rendimiento
  Dado un libro sintético cuya hoja de APU trae un insumo de material con la celda de rendimiento vacía
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES
  Y existe un error RENDIMIENTO_AUSENTE con la hoja del APU, la fila del insumo y la columna del rendimiento
  Y ninguna otra celda vacía del libro (la unidad, el analista, un rótulo de cabecera) se reporta como RENDIMIENTO_AUSENTE
```

### CA-7 `[M]` · Rechazo · Código repetido con descripciones distintas · `HDU-001 esc. 9`

```gherkin
Escenario: Mismo código, dos conceptos distintos
  Dado un libro sintético donde el código 620001 aparece en las filas 12 y 45 con la descripción "MURO STD" y en la fila 90 con "PLAFON"
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES
  Y existe un único error DUPLICADO para el código 620001
  Y su mensaje señala las filas en conflicto: 12, 45 y 90
```

### CA-8 `[M]` · Rechazo del rechazo · El código repetido con la misma descripción no es `DUPLICADO` · `HDU-001 esc. 9`

```gherkin
Escenario: Código repetido por área con descripción igual
  Dado ENITI Torre 5, con 5,028 conceptos y 36 códigos distintos, cada código repetido con su misma descripción
  Cuando se analiza la importación
  Entonces no existe ningún error DUPLICADO
  Y la comparación de descripciones ignora mayúsculas, espacios sobrantes y espacios interiores repetidos
```

Un libro sintético con descripciones que difieren solo en espacios o mayúsculas cubre lo mismo sin el archivo real. `(asumido: la normalización es la del ADR-035; PA-15.13)`.

### CA-9 `[M]` · Rechazo · Hoja sin ninguna fila de concepto · `HDU-001 esc. 27`

```gherkin
Escenario: Libro con solo encabezados
  Dado un .xlsx válido cuya hoja de catálogo solo trae encabezados, o está vacía
  Cuando se analiza la importación
  Entonces la importación queda en CON_ERRORES, sin excepción
  Y existe un error SIN_CONCEPTOS con la hoja analizada y fila y columna nulas
  Y su mensaje indica que la hoja no trae ninguna fila de concepto y la estructura mínima que se espera
  Y la importación no es confirmable: su estado es CON_ERRORES
```

### CA-10 `[M]` · Rechazo · Ningún hallazgo se pierde en silencio · ticket TKT-015

```gherkin
Escenario: Las 22 causas crudas
  Dado cada una de las 22 causas de CausaHallazgo, producida por un libro o por un hallazgo en memoria
  Cuando se clasifica
  Entonces cada causa termina en un error persistido de alguno de los siete tipos, con la causa cruda dentro del mensaje
  Y el número de errores persistidos es igual al de hallazgos crudos más los SIN_APU y los DUPLICADO
  Y ENITI, con sus 20 CARGO_DESCONOCIDO, sus 5 ERROR_DE_FORMULA, sus 6 CODIGO_EN_VARIAS_HOJAS, su ANALISIS_SIN_CODIGO y sus 16 SIN_APU, queda en CON_ERRORES con los 48 errores
```

La prueba recorre `CausaHallazgo` y falla si una causa nueva no tiene destino. El mapa causa por causa lo propone el diseño y lo aprueba la persona dueña (`PA-15.2`).

### CA-11 `[M]` · Preparación persistida, completa o ninguna · `HDU-001 esc. 6`

```gherkin
Escenario: Lo válido se conserva sin releer el Excel
  Dado una importación analizada, con errores o sin ellos
  Cuando se consulta su preparación
  Entonces devuelve los conceptos sin error, la jerarquía, los análisis asociados y los insumos por crear, con el dinero como cadena decimal
  Y obtenerla no vuelve a abrir el archivo
  Y los conceptos que tienen algún error no están en ella

Escenario: Un análisis interrumpido no deja una preparación a medias
  Dado un análisis que falla antes de terminar
  Cuando la importación queda en CON_ERRORES con PROCESO_INTERRUMPIDO
  Entonces no existe preparación para ella: o queda completa, o no queda
```

### CA-12 `[M]` · El análisis corre fuera del proceso del API · ticket TKT-015

```gherkin
Escenario: Ejecución en un proceso distinto
  Dado la aplicación en marcha y una importación RECIBIDO
  Cuando se solicita el análisis
  Entonces el caso de uso devuelve el control sin esperar a que termine
  Y el análisis se ejecuta en un proceso distinto al del API, de un solo trabajador
  Y dos importaciones solicitadas a la vez se analizan una tras otra, no en paralelo
  Y el resultado de un trabajador que muere o lanza una excepción no queda sin registrar (ver CA-14)
```

### CA-13 `[M]` · `progreso` y `latido` mientras analiza · `HDU-001 esc. 4`

```gherkin
Escenario: Seguimiento de un análisis largo
  Dado un libro sintético con varias hojas de APU y un análisis que dura más de un intervalo de refresco
  Cuando se consulta la importación durante el análisis
  Entonces su estado es ANALIZANDO, el progreso está entre 0 y 1 y nunca baja entre dos consultas, y el latido avanza
  Y al terminar el progreso queda en 1 y la importación sale de ANALIZANDO
```

Un análisis pendiente de turno, con otro trabajo en curso, no debe quedar con el latido vencido (`PA-15.4`); `CA-16` lo comprueba.

### CA-14 `[M]` · Rechazo · Excepción o muerte del trabajador · `RNF-17`

```gherkin
Escenario: El trabajo falla por una causa inesperada
  Dado un análisis cuyo trabajador lanza una excepción, o muere, a mitad de la lectura
  Cuando el caso de uso lo detecta
  Entonces la importación pasa a CON_ERRORES con un error PROCESO_INTERRUMPIDO cuyo mensaje distingue la causa
  Y la excepción queda en el registro estructurado con el identificador de la importación
  Y la obra vuelve a admitir otra importación
  Y el siguiente análisis arranca con un trabajador sano
```

`(asumido: no hay otro tipo en el CHECK para una excepción inesperada; PA-15.6)`.

### CA-15 `[M]` · Barrido de arranque de una importación interrumpida · `RNF-17`

```gherkin
Escenario: Reinicio a mitad de análisis
  Dado una importación en ANALIZANDO cuyo último latido es más viejo que el umbral de vencimiento
  Cuando arranca la aplicación
  Entonces la importación pasa a CON_ERRORES
  Y existe un error PROCESO_INTERRUMPIDO con hoja, fila y columna nulas y un mensaje que explica qué pasó
  Y la obra de esa importación admite una importación nueva: no le queda ninguna en ANALIZANDO
  Y la importación interrumpida admite el reintento del análisis
```

### CA-16 `[M]` · Rechazo · El barrido no toca lo que está vivo · `RNF-17`

```gherkin
Escenario: Un barrido con tres importaciones
  Dado una importación ANALIZANDO con latido vigente, una VALIDADO y una CON_ERRORES, todas con latido viejo
  Cuando corre el barrido
  Entonces la ANALIZANDO con latido vigente sigue como estaba
  Y la VALIDADO y la CON_ERRORES no cambian de estado ni ganan errores

Escenario: Dos barridos a la vez
  Dado una importación ANALIZANDO con latido vencido y dos instancias que arrancan al mismo tiempo
  Cuando corren los dos barridos
  Entonces la importación termina con un único error PROCESO_INTERRUMPIDO
  Y correr un tercer barrido no cambia nada
```

`(asumido: una importación ANALIZANDO con latido nulo se trata como vencida; PA-15.5)`.

### CA-17 `[M]` · El barrido es reutilizable por otro módulo · ticket TKT-015 y TKT-059

```gherkin
Escenario: Un segundo trabajo en dos pasos
  Dado el mecanismo de barrido definido por TKT-015
  Cuando se registra una segunda definición de prueba que no es una importación (un estado intermedio, un estado de caducidad y su propia tabla de prueba)
  Entonces el barrido la resuelve sin una línea específica de la importación
  Y el mecanismo no importa nada de presupuesto: lint-imports pasa con un módulo que solo conoce la definición
```

### CA-18 `[M]` · Rechazo · Estado que no admite el análisis · ticket TKT-015

```gherkin
Escenario: Analizar lo que no se puede analizar
  Dado una importación en ANALIZANDO, VALIDADO, CONFIRMADO o DESCARTADO, o en CON_ERRORES con errores distintos de PROCESO_INTERRUMPIDO
  Cuando se solicita el análisis
  Entonces se rechaza con CONFLICTO y el código ESTADO_NO_PERMITE_OPERACION
  Y la importación, sus errores y su preparación no cambian

Escenario: Reintento tras una interrupción
  Dado una importación en CON_ERRORES cuyo único error es PROCESO_INTERRUMPIDO
  Cuando se solicita el análisis
  Entonces vuelve a ANALIZANDO, el error del intento anterior se reemplaza y el análisis arranca de nuevo

Escenario: Dos solicitudes a la vez
  Dado una importación RECIBIDO y dos solicitudes simultáneas de análisis
  Cuando las dos se ejecutan
  Entonces una arranca y la otra recibe CONFLICTO ESTADO_NO_PERMITE_OPERACION
```

`(asumido: el código del conflicto, el reintento solo desde PROCESO_INTERRUMPIDO y el reemplazo de los errores; PA-15.7)`.

### CA-S1 `[S]` · Contadores de filas

```gherkin
Escenario: Conteo de filas tras el análisis
  Dado un libro sintético de 200 conceptos donde 3 tienen algún error
  Cuando termina el análisis
  Entonces filas_leidas es 200, filas_rechazadas es 3 y filas_validas es 197
```

`(asumido: la definición de «fila»; PA-15.9)`.

### Regresión

### CA-R1 `[M]` · Los lectores no cambian · invariante de resultado

```gherkin
Escenario: Mismas cifras que antes
  Dado las suites de TKT-013 y TKT-014 y los dos archivos reales
  Cuando se corre la suite completa
  Entonces siguen en verde y Union Square y ENITI leen 4,281 y 5,028 conceptos
  Y cualquier hallazgo crudo nuevo que traiga TKT-015 se marca en el lector, no se infiere en la clasificación
```

### CA-R2 `[M]` · Dominio puro, sin `float`, fronteras · reglas 1 a 3 de `CLAUDE.md`

```gherkin
Escenario: Los verificadores siguen pasando
  Dado la clasificación en dominio/ y el mecanismo de barrido
  Cuando corren verificar_float, lint-imports, ruff y mypy
  Entonces pasan sin excepción nueva
  Y la clasificación importa solo la biblioteca estándar y tipos_base
```

### CA-R3 `[M]` · Esquema de tipos y código repetido intactos · invariante 13

```gherkin
Escenario: Ni el CHECK ni el invariante 13 se tocaron
  Dado el esquema tras las migraciones de este ticket
  Cuando se compara con el de TKT-011b
  Entonces ck_importacion_error_tipo admite exactamente los mismos siete tipos
  Y concepto sigue con UNIQUE (obra_id, codigo)
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-014b (archivado). Entrega valor sin rutas: queda probado por el caso de uso y lo exponen TKT-018 y TKT-059 |
| **N** | Describe el qué, no impone el cómo | Sí | `ProcessPoolExecutor` y el barrido de arranque vienen del ticket y de `RNF-17`. El mecanismo de persistencia de la preparación y el del barrido genérico quedan al diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | El Director de Proyectos ve qué está roto y una obra no queda bloqueada tras un reinicio |
| **E** | Estimable sin investigar antes | Reserva | El mecanismo de preparación (columna o tabla, migración y ADR) y el reparto de la clasificación entre dominio e infraestructura se deciden en el diseño; no exigen un Spike |
| **S** | Cabe en una sesión sin romper contexto | Reserva | Siete Must que cruzan dominio, aplicación, infraestructura, migración y arranque. Se recomienda que el diseño evalúe partirlo en TKT-015a (clasificación y estado) y TKT-015b (trabajo, latido y barrido), como TKT-013 y TKT-014 |
| **T** | Sus criterios se pueden ejecutar | Sí | Los 18 criterios `[M]`, el criterio `[S]` y los tres de regresión corren contra PostgreSQL real con el rol de aplicación; el reinicio se simula con el barrido |

Sin fallos. Dos reservas, que el diseño resuelve.

## Definition of Done

La de funcionalidad, de `sdd/metodologia.md` §8, más la de HDU-001.

- [ ] Los criterios `[M]` en verde, cada uno con un test cuyo nombre lleva su escenario (`test_hdu001_esc06_…`, `test_hdu001_esc27_…`) o, donde no hay escenario, el ticket (`test_tkt015_…`)
- [ ] Todos los tests contra PostgreSQL con `alembic upgrade head` y el rol de aplicación; nada de SQLite
- [ ] Union Square y ENITI probados con los archivos reales, omitidos con `skip` explícito donde no estén
- [ ] Un test simula la interrupción y verifica que la obra vuelve a admitir importaciones (`CA-15`)
- [ ] Documentación afectada actualizada en el mismo cambio, y ADR del mecanismo de trabajos y del barrido
- [ ] La cobertura del módulo `presupuesto` no baja
- [ ] PR enlazado al ticket, con etiqueta de origen y revisión humana

## Preguntas abiertas y supuestos

Resueltas el 2026-11-03 por la persona dueña: sin rutas en este ticket; `DUPLICADO` literal; causas sin tipo propio al tipo más cercano; preparación persistida en este ticket; el Must M1 a M7 como está escrito. El ticket no depende de ningún servicio externo de pago ni de claves de API (`openpyxl` y `ProcessPoolExecutor` son de la biblioteca estándar y de una dependencia ya adoptada).

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| **PA-15.1** | Un error por **celda** y no por fila: es lo que ya devuelve el lector. Union Square produce unos 8,600 errores, lo que exige insertar en lote en una sola transacción y que la lista de errores de TKT-018 esté paginada (`MetaPagina`) | Con «una por fila afectada» (esc. 6) habría la mitad de renglones y se perdería la columna | Resuelta el 2026-11-03 (P14 del diseño) |
| **PA-15.2** | El mapa causa por causa de las 18 sin tipo propio. La persona dueña fijó el principio; el diseño propone el mapa y ella lo aprueba | Un mapa mal elegido confunde al Director de Proyectos al leer el error | Resuelta el 2026-11-03 (P2 del diseño): `SIN_CONCEPTOS` solo para las cinco causas de hoja; `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` van a `REF_ROTA`. Con ese mapa Union Square da 8,608 `REF_ROTA` y 31 `SIN_APU`, y ENITI 48 errores |
| **PA-15.3** | El análisis recibe el **contenido del archivo** por un puerto, sin ruta ni subida. TKT-059 no existe: sus pruebas usan un adaptador en memoria, y el adaptador del almacén de objetos lo aporta TKT-059 | Si TKT-059 cambia el contrato, hay que reabrir el puerto | `(asumido)` |
| **PA-15.4** | El umbral de latido vencido y el intervalo de refresco son configurables y los fija el diseño. Una importación que espera su turno detrás de otro análisis no debe vencer: quien refresca su latido lo decide el diseño | Barrer una importación viva, o dejar para siempre una muerta | `(asumido)`; el diseño propone valores |
| **PA-15.5** | Una importación `ANALIZANDO` con latido nulo se trata como vencida | Una importación recién arrancada se barre antes de su primer latido | `(asumido)` |
| **PA-15.6** | Una excepción inesperada o un trabajador muerto se registra como `PROCESO_INTERRUMPIDO`, porque el CHECK no tiene otro tipo | El mensaje puede sonar a reinicio cuando fue un defecto del archivo | `(asumido)` |
| **PA-15.7** | `ESTADO_NO_PERMITE_OPERACION` como código del conflicto (el OpenAPI no nombra el código); el reintento solo desde `PROCESO_INTERRUMPIDO`, como dice el OpenAPI; un archivo corregido es una importación nueva; el reintento reemplaza los errores del intento anterior | TKT-018 puede necesitar otro código o conservar el historial | `(asumido)`; TKT-018 lo confirma |
| **PA-15.8** | El análisis y el barrido no se asientan en la bitácora: no son un cambio de negocio y el PRD no lo pide | Si la persona dueña quiere traza del barrido, es un criterio nuevo | `(asumido)` |
| **PA-15.9** | `filas_leidas` es el número de conceptos del catálogo leídos, `filas_rechazadas` los que tienen algún error y `filas_validas` la diferencia | Cifras distintas en la pantalla de TKT-018 | `(asumido)` |
| **PA-15.10** | El `resumen` de previsualización lo calcula TKT-018 desde la preparación, porque `por_tipo_partida` depende de `PA-T8` | TKT-018 necesitaría una preparación con más datos | `(asumido)`; recorte de una parte del Should validado, registrado aquí |
| **PA-15.11** | `RENDIMIENTO_AUSENTE` y `PROCESO_INTERRUMPIDO` no tienen escenario en HDU-001: el verificador de escenarios no los exige y quedan sin trazabilidad. Se propone un escenario 28 y otro 29 en la historia | Dos tipos de error sin historia que los ampare | Resuelta el 2026-11-03 (P15 del diseño): se añaden antes de la fila A1, en un cambio de documentación aparte |
| **PA-15.12** | El mecanismo de persistencia de la preparación (columna `jsonb` en `importacion` o tabla propia) | Una migración y un ADR en el diseño; el criterio `CA-11` no cambia | Resuelta el 2026-11-03 (P4 del diseño): columna `importacion.preparacion jsonb` con su `CHECK` y ADR-036 |
| **PA-15.13** | La normalización de la descripción de `DUPLICADO` es la del ADR-035 (recortada, mayúsculas, espacios interiores colapsados) | Falsos duplicados o duplicados sin detectar | `(asumido)` |
| **PA-15.14** | Un `SIN_APU` lleva la hoja y la fila de la **primera** aparición del código en el catálogo, y el código como valor original | La navegación de TKT-018 apunta a otra fila | `(asumido)` |
| **PA-15.15** | `PA-T1` de TKT-013 sigue abierta para TKT-017: los dos archivos reales no se pueden confirmar mientras el modelo no admita el código repetido por área | TKT-017 no puede materializar ninguno de los dos archivos reales | Escalada; previa a TKT-017 |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Un solo trabajador deja la segunda importación esperando su turno: si el latido lo refresca el propio trabajo, la que espera lo tiene viejo y un barrido la declara muerta. Además el proceso hijo no tiene la conexión del API | `CA-12` fija el trabajador único y `CA-16` prueba que un latido vigente no se barre; `PA-15.4` deja al diseño quién refresca el de la que espera |
| 2 | Alta | «Las filas válidas se conservan» no define qué es una fila válida, y una preparación que sobrevive a un intento interrumpido es peor que ninguna | `CA-11`: fila válida es un concepto sin ningún error asociado; la preparación queda completa o no queda. `PA-15.12` deja el mecanismo al diseño |
| 3 | Alta | Union Square produce unos 8,600 errores por celda; el esc. 6 dice «por cada fila afectada». Sin lote, el análisis tarda más que el propio Excel | `CA-3` fija la cifra; `PA-15.1` registra la lectura por celda y el lote |
| 4 | Media | Registrar una excepción inesperada como `PROCESO_INTERRUMPIDO` miente cuando el defecto es del archivo, pero el CHECK está congelado | `CA-14` exige que el mensaje distinga la causa y que la excepción llegue al registro; `PA-15.6` |
| 5 | Media | El verificador de escenarios no ve `RENDIMIENTO_AUSENTE` ni `PROCESO_INTERRUMPIDO` porque no tienen escenario; la mitad del Must quedaría sin historia. Y `DUPLICADO` literal no se dispara en ningún archivo real: la prueba sobre archivo real no prueba nada | `PA-15.11` propone los escenarios 28 y 29; `CA-7` y `CA-8` usan libros sintéticos para `DUPLICADO` y `CA-8` fija con el archivo real que no hay falsos positivos |

## Contexto técnico

Siempre al final.

- **Existe:** `leer_libro_presupuesto` y `leer_catalogo` en `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py`; `AnalisisDelLibro` en `dominio/analisis.py`; `Hallazgo` y `CausaHallazgo` en `dominio/catalogo.py`; las tablas `importacion` (`estado`, `progreso`, `latido`, `filas_*`, `resumen`) e `importacion_error` en la migración `v0007`, sin índice por `(estado, latido)`; `cimenta/auditoria/aplicacion/asentar.py`. El rol de aplicación tiene `UPDATE` y `DELETE` sobre ambas tablas.
- **No existe:** modelos ORM ni repositorios de `presupuesto`; casos de uso; un `ProcessPoolExecutor` o cualquier mecanismo de trabajos; un `lifespan` o barrido de arranque en `backend/servidor/`; el módulo `archivos` (TKT-059); TKT-012 (obras) y TKT-018. La fila `importacion` la crea hoy solo una prueba, y las filas de `obra` y `usuario` de que depende también.
- **Hallazgo de partida:** los hallazgos crudos están repartidos en tres sitios (`catalogo.hallazgos`, `analisis[i].hallazgos` y `AnalisisDelLibro.hallazgos`); `SIN_APU` sale de `codigos_sin_analisis` (`analisis.py:104`) y `DUPLICADO` no lo produce ningún lector. `Hallazgo` no trae `mensaje`.
- **Operaciones del borrador OpenAPI que citan este ticket** (rutas de TKT-018): `obtener_importacion`, `iniciar_analisis_importacion` y `listar_errores_importacion`; el catálogo de `CodigoConflicto` ya trae `IMPORTACION_EN_CURSO`, `IMPORTACION_CON_ERRORES` y `ESTADO_NO_PERMITE_OPERACION`.
- **Boceto:** `docs/08-wireframes.md` (errores de importación) muestra `PROCESO_INTERRUMPIDO` con la acción «Reintentar análisis».
- **Medición de TKT-013 (E-13):** ENITI se lee en unos 0,97 s con un pico de unos 12 MB; el 2026-11-03 la lectura completa de los dos libros tardó 0,3 s cada uno en esta máquina.
- **Referencias:** `docs/06-stack-tecnologico.md` (`ProcessPoolExecutor` y openpyxl), `docs/02-arquitectura.md` §9 (máquina de estados y latido), ADR-033 (lectura posicional) y ADR-035 (clave de insumo y APU).
