# Spec · TKT-017 · Confirmación y congelado de la línea base

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

TKT-013 a TKT-016 dejaron la importación del Excel hasta el estado `VALIDADO`: el libro se lee, se clasifica, se guarda su preparación en `importacion.preparacion` y la explosión por tipo de partida se calcula en memoria. Nada de eso llega todavía al modelo real. No existe ninguna fila de `nivel`, `area`, `partida`, `concepto`, `partida_concepto` ni `apu` escrita por un caso de uso, ninguna línea base, ninguna copia congelada y ningún presupuesto de control. Sin este ticket el hilo vertical de la fase 1 no tiene contra qué evaluar una requisición: `RN-03` compara contra el tope capturado por Dirección, y ese tope cuelga de una línea base congelada.

El estado de partida, medido el 2026-11-05 por `analista-dominio`:

- El módulo `presupuesto` no tiene rutas, ni tablas Core ni repositorios para la jerarquía y la línea base. Su `interfaz.py` solo publica el ejecutor y el barrido del análisis.
- La preparación persistida tiene formato 1 y no tiene deserializador: `obtener_preparacion` devuelve el diccionario crudo.
- La preparación no trae datos que el esquema exige como `NOT NULL`: `area.tipo_unidad`, el orden de nivel y de partida, y, cuando la hoja del análisis viene vacía, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y `apu_cargo.base_calculo`.
- `calcular_explosion` (TKT-016) recibe cada concepto con su tipo de partida y su análisis y devuelve los renglones por tipo e insumo, con el importe de venta y el sugerido por tipo, calculados con el precio unitario **del pie del análisis**.
- La bitácora se asienta por `cimenta.auditoria.interfaz.asentar`, en la transacción de quien llama, con los verbos `CONFIRMAR`, `DESCARTAR`, `CONGELAR`, `CREAR`, `RECAPTURAR` y `DENEGAR` ya definidos.
- El estado de la obra solo existe como `CHECK` en el esquema. TKT-012, dueño de su máquina de estados, no está implementado ni es dependencia de este ticket.
- Los dos Excel reales todavía no llegan a `VALIDADO`: Union Square deja cero conceptos válidos y ENITI conserva un solo análisis de 24 ([ADR-036](../../../docs/adr/20261105-preparacion-de-importacion-en-jsonb.md)).

El ticket del backlog es demasiado grande para una sola entrega: diez escenarios de HDU-001, la escritura de unas nueve tablas sin repositorio, el reemplazo del borrador, el congelado con sus copias, la traducción de cinco `SQLSTATE`, siete rutas y la captura del tope con su bitácora. La persona dueña decidió el 2026-11-05 especificarlo como **paraguas con tres entregas** que se fusionan en orden **TKT-017a → TKT-017b → TKT-017c**:

| Entrega | Qué entrega | Escenarios de HDU-001 |
|---|---|---|
| **TKT-017a** · Materialización | El caso de uso que convierte una importación `VALIDADO` en la jerarquía real y una línea base `BORRADOR`, con el reemplazo del borrador. Sin ruta propia: lo invoca la confirmación de TKT-018 | 11, 12 y 13 |
| **TKT-017b** · Congelado y lecturas | El congelado con sus copias, la explosión congelada y las cuatro filas de control; las cuatro lecturas de la línea base; la traducción de los `SQLSTATE` del motor | 14, 18 y 19 |
| **TKT-017c** · Presupuesto de control | La lectura de las cuatro bolsas y la captura y recaptura del tope, con su bitácora | 15, 17, 22 y 23 |

Estas tres son las entregas funcionales de la spec. En el gate de diseño del 2026-11-05 la persona dueña las partió por tamaño en **seis entregas de código** —TKT-017a1, TKT-017a2 y TKT-017a3 dentro de la materialización, TKT-017b1 y TKT-017b2 dentro del congelado, y TKT-017c—, con sus filas y sus ramas en la nota «Partición aprobada» de [design.md](design.md). La ejecución sigue esas seis.

El ticket no depende de ningún servicio externo de pago, cuenta ni clave de API: todo corre contra PostgreSQL. No hay presupuesto que confirmar ni disparador de recorte.

## Historia de usuario

**Como** Director de Proyectos
**quiero** confirmar el catálogo importado, asignar a cada partida su tipo y congelar la línea base de la obra con un motivo
**para** que el presupuesto de venta quede fijo, la obra pase a operar y Dirección General capture contra él el tope de cada tipo de partida.

**Como** Dirección General
**quiero** capturar y, con motivo, recapturar el importe tope de cada tipo de partida, viendo el importe de venta y el sugerido
**para** que `RN-03` evalúe las requisiciones contra mi tope, y que cada subida del tope quede tan visible como una autorización de excepción.

## Alcance

### TKT-017a · Materialización

| Nivel | Ítem |
|---|---|
| **Must** | **A-M1.** Un caso de uso de materialización, publicado en `cimenta.presupuesto.interfaz` para que TKT-018 lo invoque desde `POST /api/v1/importaciones/{importacion_id}/confirmacion`. Recibe la importación, la asignación de tipos de partida, la confirmación de reemplazo con su motivo y el usuario |
| **Must** | **A-M2.** Lectura de la preparación persistida en formato 1. Una preparación con otro formato se rechaza con `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` sin escribir nada |
| **Must** | **A-M3.** Precondiciones, todas comprobadas antes de escribir: importación en `VALIDADO` (`CON_ERRORES` → `IMPORTACION_CON_ERRORES`; cualquier otro estado → `ESTADO_NO_PERMITE_OPERACION`); obra en `PLANEACION` y sin línea base `CONGELADA` (→ `ESTADO_NO_PERMITE_OPERACION`); la asignación cubre cada nombre de partida de la preparación con un tipo de partida existente (→ `422`); la explosión de TKT-016 se calcula sin rechazo (→ `ESTADO_NO_PERMITE_OPERACION` con el concepto y la causa) |
| **Must** | **A-M4.** Materialización en **una sola transacción**: alta de los insumos por crear; niveles, áreas y partidas con el orden del Excel y el tipo asignado; conceptos únicos por obra y sus conceptos de partida con el precio unitario del análisis; análisis con sus insumos y cargos; la línea base `BORRADOR` con su versión y su `importe_venta`; la importación a `CONFIRMADO`; el asiento `CONFIRMAR` |
| **Must** | **A-M5.** Reemplazo del borrador: sin confirmación responde `409` `REEMPLAZO_NO_CONFIRMADO` con la acción `CONFIRMAR_REEMPLAZO`; con confirmación y sin motivo, `422`; con ambos, descarta la línea base `BORRADOR` y toda la jerarquía de la obra en la misma transacción y asienta `DESCARTAR` |
| **Must** | **A-M6.** Atomicidad demostrada: un fallo provocado a mitad de la escritura no deja ningún dato persistido y la importación sigue en `VALIDADO` |
| **Must** | **A-M7.** Migración `0011`, reversible: `area.tipo_unidad`, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y `apu_cargo.base_calculo` pasan a admitir nulo |
| **Must** | **A-M8.** Documentación y borrador OpenAPI en el mismo cambio (detalle en los criterios) |
| **Should** | — |
| **Could** | — |
| **Won't** | La ruta de confirmación, la previsualización y la pantalla de asignación de tipos (TKT-018) · la captura de `area.tipo_unidad` (la llenará el alcance de destajo de la fase 2) |

### TKT-017b · Congelado y lecturas

| Nivel | Ítem |
|---|---|
| **Must** | **B-M1.** `POST /api/v1/lineas-base/{linea_base_id}/congelacion`, solo `DIRECTOR_PROYECTOS`, motivo obligatorio. En una transacción: copia cada concepto de partida a `linea_base_concepto`; calcula la explosión y la copia a `explosion_presupuesto` con el rendimiento congelado; crea las cuatro filas de `presupuesto_control`; pasa la línea base a `CONGELADA` con fecha, usuario y motivo; pasa la obra de `PLANEACION` a `ACTIVA`; asienta `CONGELAR` con `RN-01` |
| **Must** | **B-M2.** Rechazos del congelado: otra línea base `CONGELADA` en la obra → `409` `REGLA_NEGOCIO` `RN-01`; línea base que no está en `BORRADOR` u obra que no está en `PLANEACION` → `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` |
| **Must** | **B-M3.** Traducción de los `SQLSTATE` del motor al contrato de error, sin que ninguno llegue como `500` |
| **Must** | **B-M4.** Las lecturas `GET /api/v1/obras/{obra_id}/lineas-base`, `GET /api/v1/lineas-base/{linea_base_id}`, `GET /api/v1/lineas-base/{linea_base_id}/conceptos` y `GET /api/v1/lineas-base/{linea_base_id}/explosion`, tal como las declara el borrador |
| **Must** | **B-M5.** Las dos correcciones del borrador que `PA-16.7` de TKT-016 encargó a este ticket |
| **Should** | — |
| **Could** | — |
| **Won't** | Pasar una línea base `CONGELADA` a `SUPERSEDIDA` (versionado de `RN-18`, v1.1) · la máquina de estados completa de la obra (TKT-012) |

### TKT-017c · Presupuesto de control

| Nivel | Ítem |
|---|---|
| **Must** | **C-M1.** `GET /api/v1/lineas-base/{linea_base_id}/presupuesto-control`: las cuatro filas, con el importe de venta, el sugerido y el tope (nulo hasta capturarse) |
| **Must** | **C-M2.** `PUT /api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}`, solo `DIRECCION_GENERAL`, sobre una línea base `CONGELADA`. Primera captura sin motivo obligatorio, asentada `CREAR` sin regla; recaptura con motivo obligatorio, asentada `RECAPTURAR` con `RN-03`, valor anterior y nuevo |
| **Must** | **C-M3.** Un tope superior al importe de venta del tipo exige confirmación con motivo: sin ella, `409` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` |
| **Must** | **C-M4.** El `PUT` no se declara idempotente: repetir una recaptura con el mismo valor deja otro asiento |
| **Should** | — |
| **Could** | — |
| **Won't** | El rechazo `SIN_PRESUPUESTO_CONTROL` de una requisición (TKT-021) · el recálculo del disponible del escenario 22, que solo es observable cuando existan requisiciones (TKT-021) · la consulta de excepciones (TKT-027) · las pantallas 4a y 4b (TKT-018) |

## Non-goals

- No crea la ruta de confirmación de la importación ni ninguna pantalla: son de TKT-018, que invoca la materialización de TKT-017a.
- No implementa el versionado por trabajos extra (`RN-18`, v1.1) ni la transición `CONGELADA` → `SUPERSEDIDA`. El disparador que la protege ya existe y sus pruebas no cambian.
- No permite tocar la línea base congelada: lo que se recaptura es el presupuesto de control, que no forma parte de ella.
- No implementa la máquina de estados de la obra. Solo escribe la transición `PLANEACION` → `ACTIVA` que el congelado exige; TKT-012 la hereda.
- No cambia el lector, la clasificación ni el formato de la preparación de TKT-013 a TKT-015.
- No asienta en la bitácora el intento de modificar una copia congelada: no hay ruta que lo provoque ni actor (ver `PA-T17.4`).
- No concilia el precio unitario del catálogo con el del análisis: el del catálogo se descarta.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | El presupuesto de venta se congela al firmar; ninguna operación posterior lo modifica | [PRD](../../../docs/01-descripcion-producto.md) §8 |
| `RN-03` | Una requisición que excede el presupuesto de su tipo de partida en la obra se bloquea; el presupuestado es el tope capturado por Dirección. Este ticket captura ese tope y asienta sus subidas con esta regla | PRD §8 |
| `RN-04` | Toda autorización y todo rechazo se registran con actor, momento y motivo | PRD §8 |
| `RN-24` | La línea base conserva el rendimiento congelado para medir desviación | PRD §8 |
| `PA-01` | El control presupuestal es por tipo de partida en toda la obra, no por ubicación | PRD §10 |
| `PA-03` | Dirección captura el importe tope por obra y tipo de partida; no se calcula | PRD §10 |
| F1.4 y F1.5 | Congelar con fecha y responsable; recapturar el tope solo con autorización registrada | PRD §5 |

Tres criterios no salen del texto de una `RN` y no se etiquetan con una: la asignación de tipos de partida (`PA-T8`, decisión del 2026-11-05) responde `422`; el tope superior a la venta es `CONFLICTO` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` (HDU-001 esc. 17); las precondiciones de estado son `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`.

## Invariantes que deben sobrevivir al cambio

El ticket escribe por primera vez en tablas cuyo esquema y disparadores ya existen, y modifica cinco columnas con la migración `0011`. Cada invariante genera un criterio de regresión.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 5 | Una sola línea base `CONGELADA` por obra, con el índice único parcial | `CA-B2`, `CA-B6` |
| 6 | `UNIQUE (linea_base_id, tipo_partida_id)` en `presupuesto_control` | `CA-B1`, `CA-C2` |
| 8 | Cantidades, precios e importes no negativos | `CA-A3`, `CA-R1` |
| 10 | La bitácora no admite `UPDATE` ni `DELETE` | `CA-R1` |
| 13 | Concepto único por obra | `CA-A1` |
| 14 | Las copias de la línea base no se modifican fuera de `BORRADOR`; las transiciones solo avanzan | `CA-B5`, `CA-R1` |
| 19 | El rendimiento congelado vive separado del observado | `CA-B1` |
| 27 | La unidad está dentro del catálogo cerrado | `CA-R1` |
| 39 | Un concepto aparece a lo sumo una vez por partida | `CA-A1`, `CA-R1` |
| Preparación de TKT-015 | Su formato 1 no cambia | `CA-R1` |

## Criterios de aceptación

Los libros de prueba son **sintéticos con la forma de los reales** (decisión del 2026-11-05): un código de concepto repetido en varias áreas, con precios distintos en el catálogo, y análisis completos. La prueba con un Excel real queda abierta en `PA-T17.9`.

### TKT-017a · Materialización

#### CA-A1 `[M]` · Confirmación de la importación · `RN-01` · `HDU-001 esc. 11`

```gherkin
Escenario: La materialización crea la jerarquía y la línea base en borrador
  Dado que la importación de la obra "AP-058-25" está en "VALIDADO" y la obra en "PLANEACION" sin línea base
  Y su preparación trae el concepto "620040-A" en dos áreas, con precios de catálogo 414.93 y 428.19 y un análisis cuyo precio unitario de pie es 420.0000
  Y trae un insumo por crear con clave "PANEL YESO 1/2"
  Cuando el Director de Proyectos confirma con la asignación "MUROS EXTERIORES" → MUROS y "PLAFON" → PLAFONES_Y_CAJILLOS
  Entonces en una sola transacción se crean los niveles, áreas y partidas con el orden en que aparecen en el catálogo
  Y cada partida lleva el tipo de partida que le asignó el Director por su nombre
  Y existe un solo concepto "620040-A" en la obra, con dos conceptos de partida
  Y los dos conceptos de partida tienen precio unitario 420.0000, y su importe es cantidad × 420.0000 cuantizado a cuatro decimales con ROUND_HALF_UP
  Y se crea el insumo con código "PANEL YESO 1/2", marcado como creado en la importación
  Y se crean los análisis con sus insumos y cargos
  Y se crea la línea base en "BORRADOR" con versión 1 e importe de venta igual a la suma de los importes de sus conceptos de partida
  Y la importación queda en "CONFIRMADO"
  Y la bitácora tiene un asiento "CONFIRMAR" sin regla, escrito en la misma transacción
```

#### CA-A2 `[M]` · Rechazo · Importación que no está validada · `HDU-001 esc. 6 a 9 y 11`

```gherkin
Escenario: Confirmar una importación con errores o en otro estado
  Dado que la importación está en "CON_ERRORES"
  Cuando el Director de Proyectos la confirma
  Entonces responde 409 CONFLICTO con código "IMPORTACION_CON_ERRORES"
  Y no se escribe ninguna fila ni ningún asiento, y la importación sigue en "CON_ERRORES"

Escenario: Confirmar una importación que no está en VALIDADO ni en CON_ERRORES
  Dado que la importación está en "RECIBIDO", "ANALIZANDO", "CONFIRMADO" o "DESCARTADO"
  Cuando el Director de Proyectos la confirma
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION" y el estado actual en el detalle
  Y no se escribe nada
```

#### CA-A3 `[M]` · Rechazo · Asignación de tipos incompleta o inválida · `PA-T8`

```gherkin
Escenario: Falta el tipo de una partida
  Dado que la preparación trae las partidas "MUROS EXTERIORES" y "PLAFON"
  Cuando el Director confirma con tipo asignado solo a "MUROS EXTERIORES"
  Entonces responde 422 VALIDACION con un error OBLIGATORIO en el campo de la asignación de "PLAFON"
  Y no se escribe nada y la importación sigue en "VALIDADO"

Escenario: El tipo asignado no existe
  Cuando el Director asigna a una partida un tipo de partida inexistente
  Entonces responde 422 VALIDACION con un error VALOR_NO_PERMITIDO en ese campo
  Y no se escribe nada
```

#### CA-A4 `[M]` · Rechazo · Obra que no admite una línea base nueva · `RN-01`

```gherkin
Escenario: La obra ya tiene una línea base congelada
  Dado que la obra tiene una línea base "CONGELADA"
  Cuando el Director confirma una importación "VALIDADO" de esa obra
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION"
  Y el mensaje explica que la obra ya tiene una línea base congelada
  Y no se escribe nada y la línea base congelada no cambia

Escenario: La obra no está en planeación
  Dado que la obra está en "SUSPENDIDA" o "CERRADA"
  Cuando el Director confirma
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION" y el estado de la obra en el detalle
  Y no se escribe nada
```

#### CA-A5 `[M]` · Rechazo · Preparación ilegible o explosión imposible

```gherkin
Escenario: La preparación tiene un formato desconocido
  Dado que la preparación persistida declara un formato distinto de 1
  Cuando el Director confirma
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION"
  Y el mensaje indica que la importación debe analizarse de nuevo
  Y no se escribe nada

Escenario: La explosión de la importación se rechaza
  Dado que un análisis tiene cargos de utilidad e indirectos que superan su precio unitario
  Cuando el Director confirma
  Entonces la materialización calcula la explosión antes de escribir y responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION"
  Y el detalle nombra la causa que devolvió la explosión y el tipo de partida, por ejemplo "SUGERIDO_NEGATIVO" en MUROS, y el concepto cuando la causa es por concepto
  Y no se escribe nada
```

#### CA-A6 `[M]` · Insumo por crear que ya existe al confirmar · `PA-T13`

```gherkin
Escenario: Otra obra dio de alta el mismo insumo entre el análisis y la confirmación
  Dado que la preparación trae el insumo por crear "PANEL YESO 1/2", de unidad PZA y tipo MATERIAL
  Y ya existe un insumo con código "PANEL YESO 1/2", unidad PZA y tipo MATERIAL
  Cuando el Director confirma
  Entonces la materialización usa el insumo existente, no crea otro y no cambia su marca de creado en importación

Escenario: Rechazo · el insumo existente no coincide
  Dado que el insumo existente con ese código tiene otra unidad o otro tipo
  Cuando el Director confirma
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION", con el código, la unidad y el tipo de los dos lados en el detalle
  Y el mensaje indica que la importación debe analizarse de nuevo
  Y no se escribe nada
```

#### CA-A7 `[M]` · Rechazo · Fallo a mitad de la confirmación · `HDU-001 esc. 12`

```gherkin
Escenario: Un error al escribir interrumpe la materialización
  Dado que una prueba provoca un error de escritura después de que la materialización ya escribió parte de la jerarquía
  Cuando la transacción se interrumpe
  Entonces no queda ninguna fila nueva de nivel, área, partida, concepto, concepto de partida, análisis, insumo ni línea base
  Y no queda ningún asiento de bitácora de esa confirmación
  Y la importación sigue en "VALIDADO"
  Y el caso de uso deja propagar el error, que el manejador genérico responde como 500 con mensaje y correlacion_id, sin tipo
```

#### CA-A8 `[M]` · Rechazo · Reemplazo sin confirmar · `HDU-001 esc. 13`

```gherkin
Escenario: La obra ya tiene una línea base en borrador
  Dado que la obra tiene una línea base "BORRADOR" versión 1 de una importación anterior
  Cuando el Director confirma una importación nueva sin confirmar el reemplazo
  Entonces responde 409 CONFLICTO con código "REEMPLAZO_NO_CONFIRMADO"
  Y el detalle trae el identificador y la versión de la línea base en borrador
  Y las acciones incluyen "CONFIRMAR_REEMPLAZO", que el Director de Proyectos sí puede ejecutar
  Y no se escribe nada: la línea base anterior y su jerarquía siguen intactas y la importación nueva sigue en "VALIDADO"

Escenario: Reemplazo confirmado sin motivo
  Cuando el Director confirma el reemplazo sin escribir el motivo
  Entonces responde 422 VALIDACION con un error OBLIGATORIO en el motivo del reemplazo
  Y no se escribe nada
```

#### CA-A9 `[M]` · Reemplazo confirmado · `HDU-001 esc. 13`

```gherkin
Escenario: El Director confirma el reemplazo con motivo
  Dado que la obra tiene una línea base "BORRADOR" versión 1 con su jerarquía y sus análisis
  Cuando el Director confirma una importación nueva con el reemplazo confirmado y el motivo "Corrección de cantidades del nivel 3"
  Entonces en una sola transacción se borran la línea base en borrador y toda la jerarquía de la obra: niveles, áreas, partidas, conceptos, conceptos de partida y análisis con sus insumos y cargos
  Y los insumos que dio de alta la importación anterior se conservan
  Y se materializa la importación nueva y su línea base "BORRADOR" toma la versión 1 + la mayor versión que siga existiendo en la obra
  Y la bitácora tiene un asiento "DESCARTAR" sobre la línea base anterior, con el motivo, sin regla, y con su versión y la importación de la que provenía
  Y un asiento "CONFIRMAR" de la importación nueva
  Y la importación anterior conserva su estado "CONFIRMADO"
```

#### CA-A10 `[M]` · Rechazo · Dos confirmaciones simultáneas de la misma obra

```gherkin
Escenario: Dos confirmaciones compiten por la misma obra
  Dado que la obra no tiene línea base y hay dos importaciones "VALIDADO"
  Cuando el Director confirma las dos a la vez, sin confirmar reemplazo
  Entonces una sola termina y crea la línea base "BORRADOR"
  Y la otra responde 409 CONFLICTO "REEMPLAZO_NO_CONFIRMADO", o 409 CONCURRENCIA con la acción "REINTENTAR" si venció la espera del bloqueo
  Y nunca quedan dos líneas base en borrador ni jerarquías de dos importaciones mezcladas en la obra
```

#### CA-A11 `[M]` · Migración `0011`

```gherkin
Escenario: La migración relaja los campos que la preparación no trae
  Dado que la base está en la migración 0010
  Cuando se aplica la migración 0011 con el rol de migración
  Entonces area.tipo_unidad, apu.fecha_analisis, apu.analista, apu_cargo.porcentaje y apu_cargo.base_calculo admiten nulo
  Y cuando se baja sin filas con esos campos nulos, el esquema vuelve a ser el de 0010

Escenario: Rechazo · la bajada encuentra nulos
  Dado que existe alguna fila con uno de esos campos en nulo
  Cuando se baja la migración 0011
  Entonces la bajada se niega con un mensaje explícito y no toca nada
```

#### CA-A12 `[M]` · Documentación y borrador de TKT-017a

- `ConfirmacionImportacion` del borrador OpenAPI añade la asignación de tipos: un mapa del nombre de partida leído al `tipo_partida_id`, una entrada por nombre, válida en todas las áreas donde aparece. El `409` de `confirmar_importacion` deja de describir el «fallo a mitad de la escritura», que responde `500`, y nombra `IMPORTACION_CON_ERRORES`, `REEMPLAZO_NO_CONFIRMADO` y `ESTADO_NO_PERMITE_OPERACION`.
- El [modelo de datos](../../../docs/03-modelo-datos.md) (§4) y el [glosario](../../../docs/glosario.md) (*Concepto de partida*) dicen que el precio unitario del concepto de partida es el del pie del análisis y que el del catálogo se descarta; el ejemplo de `620040-A` con dos precios se reescribe. La migración `0011` aparece en §4 y en §11.
- `PA-T13` de TKT-014 y `PA-T17` de TKT-011 quedan marcadas como resueltas, con la decisión y su fecha.
- [ADR-036](../../../docs/adr/20261105-preparacion-de-importacion-en-jsonb.md) registra que un formato desconocido responde `ESTADO_NO_PERMITE_OPERACION`.
- HDU-001 esc. 12 se corrige: la importación no «vuelve» a `VALIDADO`, nunca sale de él.

### TKT-017b · Congelado y lecturas

#### CA-B1 `[M]` · Congelado de la línea base · `RN-01` · `RN-24` · `HDU-001 esc. 14`

```gherkin
Escenario: El Director congela la línea base en borrador
  Dado que la obra "AP-058-25" está en "PLANEACION" con una línea base "BORRADOR" de 12 conceptos de partida
  Y los conceptos solo usan los tipos MUROS y PLAFONES_Y_CAJILLOS
  Cuando el Director de Proyectos la congela con el motivo "Firma de contrato 2026-11-04"
  Entonces en una sola transacción se copian los 12 conceptos de partida a la línea base, con código, cantidad, precio unitario e importe
  Y se copia la explosión agregada por tipo de partida e insumo, con la cantidad presupuestada, el rendimiento congelado y el costo unitario que devuelve calcular_explosion
  Y se crean cuatro filas de presupuesto de control, una por tipo de partida, con el importe sugerido de la explosión, 0.0000 en ENCHAPES y GENERALES, y el tope en nulo
  Y la línea base queda en "CONGELADA" con la fecha, el usuario y el motivo
  Y la obra pasa a "ACTIVA"
  Y la bitácora tiene un asiento "CONGELAR" con la regla RN-01 y el motivo
  Y la respuesta es 200 con la línea base tal como la declara el esquema LineaBase del borrador
  Y la explosión copiada, calculada desde las filas materializadas, es igual renglón por renglón a la que calculó la materialización sobre la preparación de la misma importación
```

#### CA-B2 `[M]` · Rechazo · Segunda línea base vigente · `RN-01` · `HDU-001 esc. 19`

```gherkin
Escenario: La obra ya tiene una línea base congelada
  Dado que la obra tiene la línea base versión 1 "CONGELADA" y otra en "BORRADOR"
  Cuando el Director intenta congelar la que está en borrador
  Entonces responde 409 REGLA_NEGOCIO con regla RN-01
  Y el detalle trae la obra, el identificador de la línea base vigente y su versión 1
  Y el mensaje explica que para sustituirla hay que crear una versión nueva que marque la anterior como "SUPERSEDIDA"
  Y las acciones van vacías
  Y ninguna de las dos líneas base, la obra ni el presupuesto de control cambian
```

#### CA-B3 `[M]` · Rechazo · Línea base u obra en otro estado

```gherkin
Escenario: La línea base no está en borrador
  Dado que la línea base está en "CONGELADA" o en "SUPERSEDIDA"
  Cuando el Director intenta congelarla
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION" y el estado actual en el detalle
  Y nada cambia

Escenario: La obra no está en planeación
  Dado que la obra de la línea base en borrador está en "SUSPENDIDA" o "CERRADA"
  Cuando el Director intenta congelarla
  Entonces responde 409 CONFLICTO con código "ESTADO_NO_PERMITE_OPERACION" y el estado de la obra en el detalle
  Y nada cambia
```

#### CA-B4 `[M]` · Rechazo · Congelar sin motivo o sin rol · `RN-04`

```gherkin
Escenario: Congelar sin motivo
  Cuando el Director intenta congelar sin motivo
  Entonces responde 422 VALIDACION con un error OBLIGATORIO en el motivo
  Y la línea base sigue en "BORRADOR"

Escenario: Congelar sin el rol de Director de Proyectos
  Dado que el usuario tiene el rol DIRECCION_GENERAL o COMPRAS
  Cuando intenta congelar
  Entonces responde 403 PERMISO
  Y la bitácora asienta "DENEGAR"
  Y la línea base sigue en "BORRADOR"
```

#### CA-B5 `[M]` · Rechazo · Modificar una línea base congelada · `RN-01` · `HDU-001 esc. 18`

```gherkin
Escenario: El motor rechaza tocar las copias congeladas
  Dado que existe una línea base "CONGELADA" con sus copias
  Cuando una prueba, conectada con el rol de aplicación, intenta insertar, modificar o borrar una fila de sus conceptos o de su explosión
  Entonces la base de datos rechaza cada operación y ninguna fila cambia
  Y cuando el rechazo es el SQLSTATE IN001, el traductor del caso de uso lo responde como 409 REGLA_NEGOCIO con regla RN-01
```

#### CA-B6 `[M]` · Traducción de los `SQLSTATE` del motor · ADR-031

```gherkin
Escenario: Ningún rechazo del motor llega como 500
  Dado un caso de uso de la línea base que recibe del motor cada uno de estos errores
  Entonces IN001 se responde como 409 REGLA_NEGOCIO con regla RN-01
  Y 23505 sobre el índice de línea base vigente se responde como 409 REGLA_NEGOCIO RN-01 con el mismo detalle que CA-B2
  Y 55P03 se responde como 409 CONCURRENCIA con la cabecera Retry-After y la acción "REINTENTAR"
  Y 23503 y 23001 se responden como 409 CONFLICTO "ESTADO_NO_PERMITE_OPERACION"

Escenario: Dos congelados simultáneos de la misma obra
  Dado que dos líneas base en borrador de la misma obra se congelan a la vez
  Cuando las dos transacciones intentan quedar "CONGELADA"
  Entonces una termina y la otra responde 409 REGLA_NEGOCIO RN-01 o 409 CONCURRENCIA, nunca 500
  Y la obra tiene una sola línea base "CONGELADA"

Escenario: Un reemplazo y un congelado compiten por el mismo borrador
  Dado que la obra tiene una línea base "BORRADOR"
  Cuando el Director la congela mientras otra sesión confirma una importación nueva con el reemplazo confirmado
  Entonces gana una de las dos y la otra responde 409 sin escribir nada
  Y si ganó el congelado, la confirmación responde CONFLICTO "ESTADO_NO_PERMITE_OPERACION" porque la obra ya tiene una línea base congelada
  Y si ganó el reemplazo, el congelado responde 404 NO_ENCONTRADO por la línea base borrada, o 409 CONCURRENCIA si venció la espera
  Y nunca queda una línea base congelada con su jerarquía borrada
```

#### CA-B7 `[M]` · Rechazo · Fallo a mitad del congelado · `RN-01`

```gherkin
Escenario: Un error interrumpe el congelado después de copiar
  Dado que una prueba provoca un error después de copiar los conceptos y antes de terminar el congelado
  Cuando la transacción se interrumpe
  Entonces la línea base sigue en "BORRADOR" y no tiene ninguna fila copiada de conceptos ni de explosión
  Y no hay filas de presupuesto de control, la obra sigue en "PLANEACION" y no hay asiento "CONGELAR"
```

#### CA-B8 `[M]` · Lecturas de la línea base · `HDU-001 esc. 14`

```gherkin
Escenario: Consultar la línea base congelada
  Dado que la obra tiene una línea base "CONGELADA"
  Cuando un usuario con rol DIRECCION_GENERAL, DIRECTOR_PROYECTOS o COMPRAS consulta las líneas base de la obra, la línea base, sus conceptos o su explosión
  Entonces cada respuesta tiene la forma que declara el borrador OpenAPI para su operación
  Y los conceptos admiten los filtros por tipo de partida, por nivel y por texto, y la paginación del borrador
  Y los importes viajan como cadena con su escala

Escenario: Rechazo · consultar sin rol o lo inexistente
  Cuando un usuario sin ninguno de esos roles consulta cualquiera de las cuatro
  Entonces responde 403 PERMISO sin importes
  Y cuando la obra o la línea base no existen, responde 404 NO_ENCONTRADO
```

#### CA-B9 `[M]` · Correcciones del borrador de `PA-16.7`

- `obtener_explosion_insumos` lleva `x-tickets: [TKT-017]`.
- `RenglonExplosion.importe_venta` se renombra para decir lo que es, cantidad × costo unitario, y la columna `explosion_presupuesto.importe_venta` se documenta igual en el modelo de datos. El nombre lo fija el diseño.

### TKT-017c · Presupuesto de control

#### CA-C1 `[M]` · Lectura del presupuesto de control · `PA-03` · `HDU-001 esc. 15`

```gherkin
Escenario: Dirección consulta las cuatro bolsas
  Dado que la línea base está "CONGELADA" y nadie ha capturado topes
  Cuando un usuario con rol DIRECCION_GENERAL, DIRECTOR_PROYECTOS o COMPRAS consulta su presupuesto de control
  Entonces recibe cuatro filas, una por tipo de partida
  Y cada fila trae el importe de venta del tipo —la suma de los importes ya cuantizados de sus conceptos congelados—, el importe sugerido y el tope en nulo
  Y la suma de los cuatro importes de venta es exactamente el importe de venta de la línea base
  Y ese mismo importe de venta del tipo es contra el que se compara el tope del escenario 17

Escenario: Rechazo · consultar sin rol
  Cuando un usuario sin ninguno de esos roles consulta
  Entonces responde 403 PERMISO sin importes
```

#### CA-C2 `[M]` · Primera captura del tope · `PA-03` · `RN-03` · `HDU-001 esc. 15`

```gherkin
Escenario: Dirección captura un tope distinto del sugerido
  Dado que la fila de MUROS tiene importe de venta 480000.0000, sugerido 410000.0000 y tope nulo
  Cuando Dirección General captura 450000.0000 sin motivo
  Entonces la fila guarda el tope 450000.0000 con quien lo capturó y cuándo
  Y el sugerido no cambia
  Y la bitácora tiene un asiento "CREAR" sin regla, con el valor capturado
  Y ese asiento no aparece en una consulta de la bitácora por la regla RN-03
```

#### CA-C3 `[M]` · Rechazo · Tope superior a la venta · `HDU-001 esc. 17`

```gherkin
Escenario: Tope superior a la venta sin confirmar
  Dado que la fila de MUROS tiene importe de venta 480000.0000
  Cuando Dirección General captura 500000.0000 sin confirmar que supera la venta
  Entonces responde 409 CONFLICTO con código "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR"
  Y el detalle trae el tipo de partida, el importe de venta 480000.0000 y el tope 500000.0000
  Y las acciones incluyen "CONFIRMAR_TOPE_SUPERIOR"
  Y el tope conserva su valor y no hay asiento

Escenario: Rechazo · confirmación sin motivo
  Cuando Dirección confirma que supera la venta sin escribir el motivo
  Entonces responde 422 VALIDACION con un error OBLIGATORIO en el motivo
  Y el tope conserva su valor

Escenario: Tope superior a la venta confirmado con motivo
  Cuando Dirección confirma que supera la venta con el motivo "Subcontrato de bastidor más caro"
  Entonces el tope queda en 500000.0000 y el motivo en la fila
  Y el asiento de esa captura o recaptura lleva el motivo
```

#### CA-C4 `[M]` · Recaptura del tope · `RN-03` · `RN-04` · `HDU-001 esc. 22`

```gherkin
Escenario: Dirección sube un tope ya capturado
  Dado que el tope de MUROS se capturó en 450000.0000
  Cuando Dirección General lo recaptura en 470000.0000 con el motivo "Se subestimó el bastidor de los cubos de escalera"
  Entonces el tope queda en 470000.0000 con quien lo cambió, cuándo y el motivo en la propia fila
  Y la bitácora tiene un asiento "RECAPTURAR" con la regla RN-03, el valor anterior 450000.0000, el nuevo 470000.0000 y el motivo
  Y ese asiento aparece en una consulta de la bitácora por la regla RN-03

Escenario: Bajar el tope también es una recaptura
  Cuando Dirección General lo recaptura en 440000.0000 con motivo
  Entonces el asiento es "RECAPTURAR" con la regla RN-03 y los dos valores, igual que una subida

Escenario: Recapturar el mismo valor deja otro asiento
  Cuando Dirección recaptura 470000.0000 de nuevo con motivo
  Entonces hay un segundo asiento "RECAPTURAR" con la regla RN-03
```

#### CA-C5 `[M]` · Rechazo · Recaptura sin autoridad o sin motivo · `RN-04` · `HDU-001 esc. 23`

```gherkin
Escenario: Recapturar sin el rol de Dirección General
  Dado que el tope de MUROS es 450000.0000
  Cuando un Director de Proyectos intenta recapturarlo
  Entonces responde 403 PERMISO
  Y la bitácora asienta "DENEGAR"
  Y el tope sigue en 450000.0000

Escenario: Recapturar sin motivo
  Cuando Dirección General recaptura sin motivo
  Entonces responde 422 VALIDACION con un error OBLIGATORIO en el motivo
  Y el tope sigue en 450000.0000 y no hay asiento "RECAPTURAR"
```

#### CA-C6 `[M]` · Rechazo · Línea base no congelada o datos inválidos

```gherkin
Escenario: La línea base está en borrador
  Dado que la línea base está en "BORRADOR"
  Cuando Dirección General intenta capturar un tope
  Entonces responde 409 CONFLICTO con código "SIN_LINEA_BASE_CONGELADA"
  Y no se escribe nada

Escenario: Tope negativo o mal formado
  Cuando Dirección captura un tope negativo, con más de cuatro decimales o que no es una cadena de importe
  Entonces responde 422 VALIDACION y el tope conserva su valor

Escenario: Tipo de partida o línea base inexistente
  Cuando el tipo de partida o la línea base de la ruta no existen
  Entonces responde 404 NO_ENCONTRADO
```

#### CA-C7 `[M]` · Rechazo · Recapturas simultáneas · `RN-03`

```gherkin
Escenario: Dos recapturas del mismo tope a la vez
  Dado que el tope de MUROS es 450000.0000
  Cuando dos sesiones de Dirección General lo recapturan a la vez, a 460000.0000 y a 470000.0000
  Entonces las dos se aplican una tras otra y el segundo asiento lleva como valor anterior el que dejó el primero
  Y si venció la espera del bloqueo, la que no entra responde 409 CONCURRENCIA con la acción "REINTENTAR" y no deja asiento
```

### Regresión

#### CA-R1 `[M]` · Lo que ya funciona sigue en verde

- Las suites de TKT-010, TKT-011, TKT-013 a TKT-016 y TKT-072 siguen en verde, ajustadas solo donde la migración `0011` lo exige.
- Las pruebas de los disparadores de inmutabilidad, de los permisos por rol y de la bitácora sin `UPDATE` ni `DELETE` siguen en verde sin cambios.
- El formato 1 de la preparación no cambia.
- `lint-imports` sigue en verde: `presupuesto` no importa ningún módulo de negocio, y la bitácora y la identidad entran por su interfaz.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí, con reserva | Las tres entregas se fusionan en orden. TKT-017a no tiene ruta y solo se ve desde TKT-018; su valor es el caso de uso publicado y probado |
| **N** | Describe el qué, no impone el cómo | Sí | Los nombres de campo del borrador y el nombre del importe renombrado los fija el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | El Director congela la línea base y Dirección captura los topes contra los que evalúa `RN-03` |
| **E** | Estimable sin investigar antes | Sí | Las once decisiones abiertas se resolvieron el 2026-11-05; el esquema y la explosión ya existen |
| **S** | Cabe en una sesión sin romper contexto | Sí, partido | Cada entrega por separado. Como un solo ticket no pasaba |
| **T** | Sus criterios se pueden ejecutar | Sí | Todos contra PostgreSQL real con libros sintéticos; el archivo real queda en `PA-T17.9` |

Sin fallos; dos reservas (I y S), resueltas con la partición.

## Definition of Done

La de una funcionalidad de `sdd/metodologia.md` §8, más la de HDU-001 en lo que toca a este ticket:

- [ ] Un test por criterio, con el escenario de HDU-001 en su nombre cuando lo hay, y cada rechazo verificado con el contrato de error completo: tipo, regla o código, detalle y acciones
- [ ] Pruebas contra PostgreSQL real, con el esquema de `alembic upgrade head` y el rol de aplicación
- [ ] El tope capturado prevalece sobre el sugerido en la fila que lee `RN-03`
- [ ] La recaptura aparece en una consulta de la bitácora por `RN-03`
- [ ] Borrador OpenAPI, modelo de datos, glosario, HDU-001 y ADR-036 al día en el mismo cambio de cada entrega
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float`, `verificar_docs` y `extraer_mermaid` en verde

## Preguntas abiertas y supuestos

Las decisiones de la persona dueña del 2026-11-05 cierran todo lo que la spec necesitaba; lo que sigue queda registrado para quien diseñe o para otros tickets.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| `PA-T17.1` | Partición en TKT-017a, TKT-017b y TKT-017c con fusión a → b → c | — | Resuelta por la persona dueña el 2026-11-05 |
| `PA-T17.2` | `PA-T17`: el precio unitario del concepto de partida es el del pie del análisis; el importe es cantidad × ese precio, cuantizado; `importe_venta` es la suma. Se pierde el precio por área del catálogo | — | Resuelta el 2026-11-05 |
| `PA-T17.3` | `PA-T8`: la asignación viaja en el cuerpo de la confirmación, por nombre de partida, válida en todas las áreas. Falta o tipo inexistente → `422` | — | Resuelta el 2026-11-05 |
| `PA-T17.4` | HDU-001 esc. 18 dice que el intento de modificar una copia congelada «queda registrado en la bitácora». Sin ruta ni actor que lo provoque, y con el rechazo del motor abortando la transacción, este ticket no lo asienta. **La historia debe corregirse** | Si la persona dueña quiere el asiento, hace falta una transacción aparte, contra la letra de la regla 8 | Resuelta el 2026-11-05 (sin asiento); corrección de HDU-001 pendiente |
| `PA-T17.5` | `PA-T13`: `insumo.codigo` es la clave normalizada del lector (ADR-035). Si el insumo ya existe con la misma unidad y tipo se reutiliza; si difiere, `409` | — | Resuelta el 2026-11-05 |
| `PA-T17.6` | Reemplazo: se borra toda la jerarquía de la obra; los insumos anteriores se conservan; la versión es 1 + la mayor que siga existiendo, así que un borrador reemplazado cede su número | — | Resuelta el 2026-11-05 |
| `PA-T17.7` | Confirmar sobre una obra con línea base `CONGELADA` o fuera de `PLANEACION` se rechaza con `ESTADO_NO_PERMITE_OPERACION`; la sustitución de una congelada es `RN-18` (v1.1). Con esto, el escenario 19 solo se alcanza por una carrera o por un dato sembrado | — | Resuelta el 2026-11-05 |
| `PA-T17.8` | El congelado escribe `obra.estado` `PLANEACION` → `ACTIVA` dentro de `presupuesto`. TKT-012 debe respetar esa transición al construir la máquina de estados | Si TKT-012 la modela distinto, habrá que mover la escritura a su caso de uso | Resuelta el 2026-11-05; aviso para TKT-012 |
| `PA-T17.9` | La DoD de HDU-001 pide probar con los archivos reales, que hoy no llegan a `VALIDADO`. TKT-017 se verifica con libros sintéticos de forma real | Un detalle del archivo real que el sintético no reproduce aparecerá en TKT-018 | Resuelta el 2026-11-05; prueba real abierta para TKT-018 |
| `PA-T17.10` | El rechazo de un `UPDATE` o `DELETE` sobre `linea_base_concepto` por la revocación del permiso (`42501`) no tiene traducción declarada; CA-B5 solo exige que el motor lo rechace | Si alguna ruta futura lo provocara, llegaría como `500` | Resuelta por el diseño el 2026-11-05: `42501` no se traduce y responde `500`, porque ninguna ruta emite `UPDATE` ni `DELETE` sobre `linea_base_concepto` y un `42501` sería un error de programa (ver «Escalera de decisión» y «Traducción del motor» de [design.md](design.md); el mutante `M-A6` lo vigila) |
| `PA-T17.11` | `area.tipo_unidad` queda nulo en toda obra importada hasta que el alcance de destajo de la fase 2 lo llene | Una lectura de fase 1 que lo exija fallaría | Resuelta el 2026-11-05 (migración `0011`) |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El reemplazo de TKT-017a y el congelado de TKT-017b actúan sobre el mismo borrador. Si corren a la vez, un congelado podría copiar una jerarquía que el reemplazo está borrando, y ningún criterio lo cubría | Escenario añadido a `CA-B6`: gana una de las dos, la otra responde sin escribir, y nunca queda una congelada sin jerarquía. Cómo se serializan lo decide el diseño |
| 2 | Media | La explosión se calcula dos veces: al confirmar, sobre la preparación, para validar; al congelar, sobre las filas materializadas. Si la materialización pierde o redondea algo, las dos difieren y el congelado guardaría otra cosa que la validada | `CA-B1` exige que las dos explosiones sean iguales renglón por renglón |
| 3 | Media | Hay tres «importes de venta» posibles por tipo: el de `calcular_explosion` sin cuantizar por concepto, la suma de los importes cuantizados y el `importe_venta` de la línea base. Por el redondeo pueden diferir en centavos, y el escenario 17 no decía contra cuál compara | `CA-C1` fija la suma de los importes cuantizados de los conceptos congelados, exige que las cuatro sumen el de la línea base y que sea la cifra del escenario 17 |
| 4 | Media | Los ejemplos de recaptura solo subían el tope. Una implementación que asentara `RN-03` solo en las subidas pasaría todos los criterios | Escenario añadido a `CA-C4`: bajar el tope también se asienta `RECAPTURAR` con `RN-03`, como dice el borrador |
| 5 | — | Se buscó un consumidor de la jerarquía que impida borrarla al reemplazar el borrador. No hay ninguno: las copias de la línea base solo existen después del congelado, y el congelado impide confirmar otra importación | Sin cambio |

Veredicto: cuatro objeciones sustantivas, las cuatro incorporadas a los criterios. Ninguna revela una regla que el PRD no tenga.

## Contexto técnico

- **Módulo:** `presupuesto`, capas `dominio`, `aplicacion`, `infraestructura` y `api`; sin frontend. Consume por interfaz `auditoria` (`asentar`) e `identidad` (`exigir_rol`, que ya asienta el `403` como `DENEGAR`).
- **Esquema:** `v0006` (jerarquía, `insumo`, `apu`, `apu_insumo`, `apu_cargo`, `obra`), `v0007` (`linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, disparadores `presupuesto_proteger_linea_base` y `presupuesto_proteger_copia_congelada`, índice `uq_linea_base_obra_id_congelada`, revocación sobre `linea_base_concepto`), `v0010` (`partida_concepto`, `linea_base_concepto.partida_concepto_id`). La migración nueva es `0011`.
- **Dominio reutilizable:** `cimenta/presupuesto/dominio/explosion.py` (`calcular_explosion`, `ConceptoAExplotar`, `ImportesTipoPartida`) y `dominio/preparacion_importacion.py` (`Preparacion`).
- **Preparación:** `infraestructura/preparacion_json.py` serializa el formato 1; `aplicacion/analisis_importacion.py` la lee hoy como diccionario.
- **Contrato de error:** `backend/contrato_error/excepciones.py` (`RechazoRegla`, `ConflictoEstado`, `ConcurrenciaVencida`) y `catalogos.py`. Ningún código nuevo en el catálogo cerrado.
- **Borrador OpenAPI:** `confirmar_importacion`, `listar_lineas_base`, `obtener_linea_base`, `congelar_linea_base`, `listar_conceptos_linea_base`, `obtener_explosion_insumos`, `listar_presupuesto_control`, `capturar_presupuesto_control`; esquemas `ConfirmacionImportacion`, `LineaBase`, `RenglonExplosion`, `CapturaPresupuestoControl`, `PresupuestoControl`.
- **ADR:** [ADR-031](../../../docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) (inmutabilidad en el motor y traducción de `SQLSTATE`), [explosión por tipo de partida](../../../docs/adr/20261103-explosion-por-tipo-de-partida.md), [ADR-036](../../../docs/adr/20261105-preparacion-de-importacion-en-jsonb.md), [concepto único](../../../docs/adr/20261105-concepto-unico-y-concepto-de-partida.md), [clave de insumo](../../../docs/adr/20261103-clave-de-insumo-y-lectura-de-apu.md), [bloqueo pesimista](../../../docs/adr/20260918-bloqueo-pesimista-presupuesto.md).
- **Bocetos:** [wireframes](../../../docs/08-wireframes.md) §3b, §4a y §4b. Las pantallas son de TKT-018; los criterios de este ticket respetan lo que pintan: el tope llega vacío, no precargado con el sugerido, y la sección de control no existe en `BORRADOR`.
