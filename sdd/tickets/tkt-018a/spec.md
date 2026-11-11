# Spec · TKT-018a · Pantalla de línea base y presupuesto de control

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

TKT-017 dejó listo, por backend, todo el ciclo de la línea base una vez importada: lecturas, congelado con motivo y captura y recaptura del tope de control. Pero lo declaró **sin frontend propio** y hoy las secciones `LINEA_BASE` y `PRESUPUESTO_CONTROL` del armazón son dos marcadores. Sin pantalla, el Director de Proyectos no puede congelar y la Dirección General no puede capturar el tope contra el que se evalúa toda requisición (`RN-03`): sin tope, el hilo vertical no avanza, porque la requisición responde `SIN_PRESUPUESTO_CONTROL`.

TKT-018 original construye esa pantalla **y** todo el flujo de importación (subida del Excel por archivo, análisis, previsualización, errores y confirmación), que depende de TKT-059 (módulo `archivos`, todavía sin código). Por el plazo de la tercera entrega, la persona dueña validó el 2026-11-10 partir el ticket: **TKT-018a** (esta spec: la pantalla de la línea base, el congelado y el tope de control, consumiendo solo rutas ya archivadas) y **TKT-018b** (la importación). Los criterios de la captura del tope —pantalla 4b del wireframe, escenarios 15, 17, 22 y 23 de HDU-001— no eran criterio de ningún ticket; la persona dueña los incorporó aquí.

## Historia de usuario

**Como** Director de Proyectos (congela) y Dirección General (captura y recaptura el tope)
**quiero** ver la línea base de una obra, congelarla con su motivo y fijar el presupuesto de control por tipo de partida
**para** que exista la referencia inmutable y el tope contra el que se medirá toda desviación y se evaluará toda requisición.

Historia de referencia: [HDU-001](../../../docs/04-historias-usuario.md#hdu-001--alta-de-obra-e-importación-de-la-línea-base), escenarios 14, 15, 17, 18, 19, 22 y 23.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | Pantalla de la línea base de una obra: estado, versión, importe de venta y su desglose por tipo de partida; estados cargando, sin línea base, con error y obra inexistente |
| **Must** | Congelar con motivo obligatorio (solo Director de Proyectos), pintando el `422`, el `409` `RN-01`, el `409` de estado y el `409` de concurrencia con su reintento; tras congelar, modo lectura con fecha, autor y motivo, sin controles de edición |
| **Must** | Presupuesto de control (wireframe 4b): tabla de venta, sugerido y tope por tipo de partida; primera captura sin motivo con campos vacíos; un `PUT` por fila; tope superior a la venta con confirmación y motivo; recaptura con motivo; vista de solo lectura para quien no es Dirección General; en `BORRADOR`, «Congela primero la línea base…» |
| **Must** | Acceso a la pantalla desde la lista de obras de TKT-012a: la obra de contexto va en la ruta (`/obras/:obraId/…`) y la lista gana un enlace por obra |
| **Must** | Importes siempre como cadena decimal exacta, sin pasar por `Number` |
| **Should** | Un script de semilla local que deja una línea base `BORRADOR` real (pasando por el caso de uso `materializar_importacion`) para poder demostrar la pantalla, y un E2E de congelar como Director de Proyectos y capturar el tope como Dirección General |
| **Could** | — |
| **Won't** | Todo el flujo de importación: subida, análisis, previsualización, errores y confirmación, y la deuda de TKT-017 que va con él (TKT-018b). Las tablas de «Ver conceptos» y «Ver explosión por tipo de partida». El selector de obra del armazón. Cualquier cambio de backend |

## Non-goals

- **No hay backend nuevo.** La pantalla consume solo rutas archivadas en TKT-017 y `listar_obras` de TKT-012a. No se toca `docs/api/openapi.yaml` ni se regenera `servidor.ts`.
- **No crea líneas base.** Ninguna ruta del sistema crea una hasta TKT-018b: en un entorno real, hasta entonces la pantalla muestra «sin línea base». La demostración depende de la semilla (Should).
- No muestra quién importó ni cuándo, ni el conteo de conceptos o insumos que dibuja el wireframe 4a: el contrato publicado no trae esos datos (ver pregunta 4).
- No recalcula ni muestra el «disponible» tras recapturar (escenario 22, última cláusula): lo recalcula la requisición (TKT-021 y TKT-023).
- No emite `SIN_PRESUPUESTO_CONTROL` (escenario 16): lo emite TKT-021.
- No permite editar, borrar ni reemplazar una línea base congelada por ninguna vía.
- No construye el componente de subida de archivos (TKT-065, fase 2).

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | La línea base se congela al firmar y ninguna operación posterior la modifica; no puede haber dos vigentes por obra | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-03` | La requisición se evalúa contra el tope de control por tipo de partida: **la recaptura del tope se asienta con esta regla** y aparece en la bitácora de excepciones | PRD §8 |
| `RN-04` | Toda autorización y todo rechazo se registran con actor, momento y motivo, de forma permanente: el motivo de la confirmación del tope superior y de la recaptura va a la bitácora | PRD §8 |
| `PA-03` | El presupuesto de control **se captura**: Dirección captura el importe tope por obra y tipo de partida, y `RN-03` evalúa contra ese importe capturado. El sugerido es solo una referencia | PRD, preguntas al cliente |
| `PA-01` | El control es por obra y tipo de partida (cuatro bolsas), no por ubicación | PRD, preguntas al cliente |

Regla 13 de `CLAUDE.md`: quien mide no fija el número contra el que se le mide; regla 5: los límites bloquean, no advierten (la pantalla no deja guardar un tope superior a la venta sin confirmación registrada).

## Invariantes que deben sobrevivir al cambio

El ticket **no modifica backend**, pero añade un consumidor de rutas ya probadas y toca archivos compartidos de frontend (`etiquetas.ts`, `rutas.tsx`, la lista de obras de TKT-012a).

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Pruebas de TKT-008 y de TKT-012a sobre componentes compartidos, la lista de obras y el armazón | Los cambios en `etiquetas.ts`, `rutas.tsx` y la lista de obras no rompen lo ya probado | `CA-R1` |
| Contrato publicado y tipos generados | La pantalla no cambia el contrato: `tipos:verificar` sigue en verde sin regenerar | `CA-R2` |

## Criterios de aceptación

Gherkin, en español.

### CA-1 `[M]` · Llegar a la pantalla desde la lista de obras

```gherkin
Escenario: Se abre la línea base de una obra desde la lista
  Dado un usuario con rol DIRECTOR_PROYECTOS, DIRECCION_GENERAL o COMPRAS en la lista de obras
  Cuando elige el enlace «Línea base» de la obra "AP-058-25"
  Entonces la ruta contiene el identificador de esa obra
  Y la pantalla pide la línea base de esa obra y no de otra

Escenario: Rechazo · rol sin acceso
  Dado un usuario con rol RESIDENTE, ALMACEN o ADMINISTRACION
  Entonces la lista no le ofrece el enlace «Línea base»
  Y si abre la ruta a mano, ve el aviso de que no tiene permiso, sin cifras
```

### CA-2 `[M]` · Ver la línea base en borrador

```gherkin
Escenario: La obra tiene una línea base en BORRADOR
  Dado la obra "AP-058-25" con una línea base BORRADOR de importe de venta "$62,500.00"
  Cuando un Director de Proyectos abre su pantalla de línea base
  Entonces ve el estado "BORRADOR", la versión y el importe de venta con su desglose por tipo de partida
  Y ve el campo de motivo y el botón «Congelar línea base»
  Y no ve la sección de presupuesto de control
  Y ve el mensaje «Congela primero la línea base para capturar el presupuesto de control»
```

### CA-3 `[M]` · Congelar la línea base · `RN-01` · `HDU-001 esc. 14`

```gherkin
Escenario: El Director de Proyectos congela con motivo
  Dado una línea base BORRADOR y el motivo "Contrato firmado el 13-oct-2026"
  Cuando el Director de Proyectos pulsa «Congelar línea base»
  Entonces el cliente envía el motivo y la línea base pasa a "CONGELADA"
  Y la pantalla pasa a modo lectura con la fecha, quien congeló y el motivo
  Y ya no hay campo de motivo ni botón de congelar
  Y la obra se muestra en estado "ACTIVA"
  Y aparece la sección de presupuesto de control con sus cuatro tipos de partida
```

### CA-4 `[M]` · Rechazos del congelado · `RN-01` · `HDU-001 esc. 19`

```gherkin
Esquema del escenario: El servidor rechaza el congelado
  Dado una línea base BORRADOR
  Cuando el Director de Proyectos intenta congelar y el servidor responde <respuesta>
  Entonces la pantalla muestra <vista>
  Y la línea base sigue en BORRADOR en pantalla

  Ejemplos:
    | respuesta                                       | vista                                                                                                   |
    | 422 por motivo ausente o en blanco              | el mensaje junto al campo de motivo, sin pantalla de bloqueo                                            |
    | 409 REGLA_NEGOCIO RN-01 (segunda vigente)      | la pantalla de bloqueo con el detalle (obra y versión vigente) y la explicación, sin acciones            |
    | 409 CONFLICTO ESTADO_NO_PERMITE_OPERACION       | el mensaje del contrato con el estado o las causas del detalle                                          |
    | 409 CONCURRENCIA BLOQUEO_VENCIDO                | el mensaje y la acción «Reintentar» con la espera que indique el servidor                               |
    | 403 sin permiso                                 | el mensaje del servidor con su referencia de correlación, sin cifras                                     |
    | 404 la línea base no existe                     | «La línea base no existe»                                                                                |
```

El cliente tampoco envía el congelado con el motivo vacío o en blanco: el rechazo se pinta junto al campo antes de llamar al servidor. El escenario `409` `RN-01` no puede provocarse desde la interfaz con el backend actual (una obra con línea base vigente ya no está en `PLANEACION`): se prueba con respuestas simuladas.

### CA-5 `[M]` · Línea base congelada: solo lectura · `HDU-001 esc. 18`

```gherkin
Escenario: Una línea base congelada no ofrece ninguna edición
  Dado una línea base CONGELADA
  Cuando cualquiera de los roles con acceso abre su pantalla
  Entonces ve el estado, la versión, el importe de venta, la fecha, el autor y el motivo del congelado
  Y no existe ningún campo editable, botón de congelar, de modificar ni de eliminar sobre la línea base
```

### CA-6 `[M]` · Primera captura del tope · `PA-03` · `HDU-001 esc. 15`

```gherkin
Escenario: Dirección General captura los topes
  Dado una línea base CONGELADA sin topes capturados
  Y un usuario con rol DIRECCION_GENERAL en la sección de presupuesto de control
  Entonces la tabla muestra por tipo de partida la venta, el sugerido y un campo de tope vacío (no precargado con el sugerido)
  Cuando captura "45000.00" en MUROS y "38000.00" en PLAFONES_Y_CAJILLOS y pulsa «Guardar topes»
  Entonces el cliente envía un PUT por cada fila capturada, con el importe como cadena decimal, sin motivo
  Y cada fila guardada muestra quién la capturó y cuándo
  Y las filas sin capturar siguen vacías con «sin capturar»
```

### CA-7 `[M]` · Tope superior a la venta · `RN-03`, `RN-04` · `HDU-001 esc. 17`

```gherkin
Escenario: Un tope mayor que la venta exige confirmación con motivo
  Dado la venta de GENERALES en "$7,400.00"
  Cuando Dirección General captura "8000.00" y guarda
  Entonces el servidor responde 409 con la acción de confirmar el tope superior
  Y la pantalla abre el diálogo con el tipo de partida, la venta "$7,400.00" y el tope "$8,000.00"
  Y el campo de motivo es obligatorio y «Confirmar con motivo» no envía sin él
  Cuando escribe el motivo y confirma
  Entonces el cliente reenvía el mismo PUT con la confirmación y el motivo
  Y la fila queda guardada

Escenario: Rechazo · corregir en vez de confirmar
  Cuando pulsa «Corregir»
  Entonces el diálogo se cierra, el tope no se guarda y el campo conserva lo capturado para editarlo
```

### CA-8 `[M]` · Recaptura del tope · `RN-03` · `HDU-001 esc. 22`

```gherkin
Escenario: Dirección General recaptura un tope ya capturado
  Dado MUROS con tope vigente "$45,000.00" capturado por M. Torres el 15-oct-2026
  Cuando Dirección General abre «Recapturar» en MUROS
  Entonces el diálogo muestra el tope vigente con su autor y fecha, un campo de tope nuevo y un motivo obligatorio
  Cuando captura "50000.00" con el motivo "Ampliación de muros en nivel 9" y pulsa «Recapturar»
  Entonces el cliente envía el PUT con el tope nuevo y el motivo
  Y la fila muestra el tope nuevo, y el autor y la fecha de la recaptura
  Y el diálogo informa que queda en la bitácora con RN-03
```

### CA-9 `[M]` · Rechazos de la recaptura · `RN-03`, `RN-04` · `HDU-001 esc. 23`

```gherkin
Escenario: La recaptura sin motivo se rechaza
  Cuando Dirección General recaptura sin motivo
  Entonces el mensaje aparece junto al campo de motivo, no se envía nada o el servidor responde 422
  Y el tope conserva su valor

Escenario: Quien no es Dirección General no puede capturar
  Dado un usuario con rol DIRECTOR_PROYECTOS o COMPRAS en la sección de presupuesto de control
  Entonces la columna de tope es de solo lectura, sin campos ni botones de captura ni de recaptura
  Y si un 403 llega del servidor, el tope conserva su valor y la pantalla muestra el mensaje del servidor con su referencia de correlación
```

### CA-10 `[M]` · Importes mal formados · `RN-03`

```gherkin
Esquema del escenario: Un tope con forma inválida no se envía
  Dado un campo de tope con <entrada>
  Cuando Dirección General guarda
  Entonces el mensaje aparece junto al campo
  Y no se envía ninguna petición para esa fila

  Ejemplos:
    | entrada                              |
    | texto no numérico                    |
    | un importe negativo                  |
    | más de cuatro decimales              |
    | más de catorce dígitos enteros       |
    | notación científica ("1e5")          |
```

Además, un `422` del servidor sobre el importe se pinta en ese campo. Los importes se calculan y se comparan con `decimal.js`; nunca se convierten a `Number`.

### CA-11 `[M]` · Guardar topes con éxito parcial

```gherkin
Escenario: Una fila falla y las demás se conservan
  Dado tres topes capturados y guardados con un PUT cada uno
  Cuando el servidor rechaza la segunda fila y acepta las otras
  Entonces las filas aceptadas muestran su captura y la rechazada muestra su mensaje
  Y la pantalla indica cuáles se guardaron y cuál no
```

### CA-12 `[M]` · Estados de la pantalla

```gherkin
Esquema del escenario: La pantalla cubre sus estados
  Dado <situación> al abrir la pantalla de una obra
  Entonces muestra <vista>

  Ejemplos:
    | situación                                     | vista                                                                                              |
    | consulta en curso                             | un indicador de carga                                                                              |
    | la obra no tiene ninguna línea base           | «Esta obra todavía no tiene línea base» y la explicación de que la importación llega con TKT-018b, sin botón que simule importar |
    | la obra no existe (404)                       | «La obra no existe»                                                                                |
    | error del servidor                            | un aviso con el identificador de correlación y la opción de reintentar                             |
    | línea base BORRADOR                           | la vista de `CA-2`                                                                                 |
    | línea base CONGELADA                          | la vista de `CA-5` y la sección de `CA-6`                                                          |
```

### CA-13 `[M]` · Quién ve qué

```gherkin
Escenario: La visibilidad sigue a los roles del borrador del contrato
  Dado un usuario con rol DIRECCION_GENERAL, DIRECTOR_PROYECTOS o COMPRAS
  Entonces puede abrir la pantalla de línea base
  Y solo DIRECTOR_PROYECTOS ve el formulario de congelado
  Y solo DIRECCION_GENERAL ve los controles de captura y recaptura del tope

Escenario: Rechazo · COMPRAS y el borrador
  Dado una línea base en BORRADOR
  Cuando la abre un usuario COMPRAS
  Entonces no ve el borrador ni los importes de la importación (supuesto 1)
```

### CA-S1 `[S]` · Demostración de punta a punta (Should)

```gherkin
Escenario: Congelar y capturar el tope en el navegador
  Dado una obra con una línea base BORRADOR sembrada por el script local
  Cuando un Director de Proyectos inicia sesión, congela con motivo y cierra sesión
  Y una Dirección General inicia sesión y captura el tope de MUROS
  Entonces la pantalla muestra la línea base CONGELADA y el tope de MUROS capturado con su autor

Escenario: Rechazo · el script no corre contra una base remota
  Cuando se ejecuta el script de semilla con una base que no es local
  Entonces se niega y no escribe nada
```

### CA-R1 `[M]` · Regresión · Lo compartido sigue verde

```gherkin
Escenario: Los cambios compartidos no rompen lo ya probado
  Cuando corren las pruebas del armazón, de las secciones, de la lista de obras de TKT-012a y de los componentes de bloqueo y de formulario de TKT-008c
  Entonces pasan sin modificar ninguna aserción existente, salvo las que enumeran claves o filas que esta entrega añade y declara
```

### CA-R2 `[M]` · Regresión · El contrato no cambia

```gherkin
Escenario: Sin backend nuevo, sin tipos nuevos
  Cuando se ejecuta npm run tipos:verificar
  Entonces pasa sin regenerar servidor.ts
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí, con orden | Necesita TKT-012a ya integrado (la lista de obras, `listar_obras` y los tipos de las rutas de obra). TKT-018b depende de esta entrega, no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | El contexto técnico va al final |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | El Director de Proyectos congela y Dirección General fija el tope por pantalla |
| **E** | Estimable sin investigar antes | Sí | Rutas y errores ya probados; componentes de bloqueo y motivo ya existen |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Unas 450 a 480 líneas de producción de frontend, sin backend. Si el diseño las supera, se parte en dos entregas de ejecución (4a y 4b) con un solo PR |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es observable en la pantalla con respuestas simuladas, y el `CA-S1` en el navegador |

Sin fallos: pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` tiene su test con el escenario en el nombre (`hdu001_esc14_…`, `esc15`, `esc17`, `esc18`, `esc19`, `esc22`, `esc23`) y los rechazos verifican el contrato de error que la pantalla pinta.
- [ ] Vitest con respuestas simuladas de cada rechazo de `CA-4`, `CA-7`, `CA-9`, `CA-10` y `CA-11`, y de los estados de `CA-12`.
- [ ] Los importes se tratan como cadena decimal y ninguna prueba ni código los convierte a `Number`.
- [ ] `npm run lint`, `typecheck`, `test` y `tipos:verificar` en verde; `python tools/verificar_docs.py` en verde.
- [ ] Documentación afectada actualizada en el mismo cambio: la partición en `docs/05-tickets-trabajo.md`, el wireframe 4 (los textos del esc. 18 y de `RN-18` desactualizados), el delta del ticket.
- [ ] Si se hace el Should, el script de semilla se niega contra una base no local y lo demuestra una prueba.
- [ ] Las auditorías aplicables aprueban.

## Preguntas abiertas y supuestos

Decididas por la persona dueña el 2026-11-10: partir TKT-018; incluir la captura del tope; la obra de contexto va en la ruta con un enlace desde la lista de obras. Costos: el ticket no depende de ningún servicio externo de pago, cuenta ni clave de API.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | **COMPRAS y el borrador.** El wireframe dice que Compras ve la línea base congelada y no la importación, pero el borrador da lectura a Compras también sobre el borrador. Recomendación: la interfaz le oculta el borrador. Es una decisión de presentación; el servidor no la impone | Compras vería importes de una importación que aún no es firme | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 2 | **Qué línea base se muestra si hay varias.** Recomendación: la `CONGELADA` si existe y, si no, el `BORRADOR` de mayor versión | Mostrar una versión que no es la vigente | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 3 | **El motivo del congelado, en línea o en diálogo.** El wireframe lo dibuja en línea; el componente `CapturaMotivo` existente es un diálogo. Recomendación: en línea, como el wireframe, reutilizando la validación del motivo | Un componente propio más, o desviarse del wireframe | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 4 | **Lo que el wireframe 4a muestra y el contrato no trae.** «Importada el … por …, N conceptos, N insumos» no está en `LineaBase`. Recomendación: mostrar solo versión, estado, importe de venta, desglose por tipo de partida y, congelada, fecha, autor y motivo; sin inventar campos ni cambiar el contrato | Pedir un campo al backend sería alcance nuevo | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 5 | **«Guardar topes» con éxito parcial.** El wireframe lo marca como supuesto de la interfaz, no del API: un `PUT` por fila y, si uno falla, los demás conservan su resultado. Recomendación: confirmarlo (`CA-11`) | Una captura a medias sin aviso | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 6 | **El wireframe está desactualizado** en el esc. 18 (dice que se asienta en la bitácora; HDU-001, ya corregida, dice que no) y cita `RN-18`, que TKT-017 cambió por `F1.6`. Se corrige en este cambio | Documentación en desacuerdo con la historia | Hallazgo registrado · se corrige aquí |
| 7 | **Tablas «Ver conceptos» y «Ver explosión».** Ningún criterio de TKT-018 las exige. Se dejan fuera (Won't) y quedan como ticket futuro | Una pantalla de línea base sin acceso a sus conceptos hasta otro ticket | Resuelta con la recomendación al validar el Must |
| 8 | **Orden de ejecución.** TKT-018a se ramifica de `Produccion` después de integrar TKT-012a: toca los mismos archivos (`secciones.ts`, `rutas.tsx`, `etiquetas.ts`, la lista de obras) y un conflicto haría fallar `tipos:verificar` | Conflictos de fusión | Resuelta el 2026-11-10 con la recomendación (`design.md`) |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **Cita de regla equivocada.** La primera redacción atribuía la captura del tope a `RN-24`, que en el PRD es la recalibración del rendimiento: el tope capturado es `PA-03` y la trazabilidad del motivo es `RN-04` | Aceptada y corregida en la tabla de reglas y en los títulos de `CA-6`, `CA-7` y `CA-9` |
| 2 | Alta | **Sin línea base real no hay demostración.** Ninguna ruta crea una hasta TKT-018b: en un entorno real la pantalla solo mostraría «sin línea base», y la semilla y el E2E son *Should*. Si se recortan, la entrega no puede mostrar la pantalla funcionando | Aceptada como riesgo, y se eleva a la persona dueña en el gate de diseño: la semilla se mantiene *Should* con su disparador de recorte claro. `CA-12` sí cubre el estado vacío |
| 3 | Media | **Un `409` de `RN-01` que la interfaz no puede provocar** (una obra con línea base vigente ya no está en `PLANEACION`) podría dar un criterio sin prueba real | Aceptada. `CA-4` lo declara y lo prueba con respuestas simuladas; es lo mismo que decidió TKT-017 |
| 4 | Media | **Dependencia de orden con TKT-012a.** La lista de obras, `listar_obras` y los tipos aún no existen en `Produccion`: ejecutar 018a antes produciría conflictos en `secciones.ts`, `rutas.tsx`, `etiquetas.ts` y `servidor.ts` | Aceptada. Declarada en INVEST (I) y en la pregunta 8: 018a se ramifica después de integrar 012a |
| 5 | Baja | La pregunta 1 (Compras no ve el borrador) es presentación y no seguridad: el servidor sí devuelve el borrador a Compras | Aceptada. Dicho expresamente en la pregunta 1 |

## Contexto técnico

Siempre al final.

**Qué existe.**

- Rutas ya archivadas en TKT-017 y presentes en `frontend/src/api/generado/servidor.ts`: `listar_lineas_base`, `obtener_linea_base`, `congelar_linea_base` (solo Director de Proyectos), `listar_presupuesto_control` y `capturar_presupuesto_control` (solo Dirección General; `PUT` con `importe_tope`, `motivo` y `confirmar_superior_a_venta`). Lectura para Dirección General, Director de Proyectos y Compras.
- Comportamiento del backend que la pantalla debe respetar: una línea base en `BORRADOR` devuelve el control como `[]`; el control nace al congelar con cuatro filas de tope `null`; la primera captura asienta `CREAR` sin motivo; la recaptura asienta `RECAPTURAR` con `RN-03`, también si repite el valor; `actualizado_*` es nulo en la primera captura.
- Errores que la pantalla pinta: `422` (motivo, importe, motivo con NUL o de más de 2000 caracteres), `409` `REGLA_NEGOCIO` `RN-01`, `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`, `SIN_LINEA_BASE_CONGELADA` y `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` (con la acción `CONFIRMAR_TOPE_SUPERIOR`), `409` `CONCURRENCIA` con `Retry-After` y `REINTENTAR`, `403` y `404`.
- Frontend: `secciones.ts` define `LINEA_BASE` y `PRESUPUESTO_CONTROL` como marcadores en `modulos/presupuesto/rutas.tsx`. Existen `CapturaMotivo`, `ConflictoEnLinea`, `PantallaBloqueo`, `DetalleCifras`, `BotonesAcciones` (con cuenta atrás de `CONCURRENCIA`), `compartido/dinero/dinero.ts` y los componentes `dialog`, `input` y `textarea`. `etiquetas.ts` ya trae `CONFIRMAR_TOPE_SUPERIOR`, `REINTENTAR`, `CONGELAR_LINEA_BASE` y `CAPTURAR_PRESUPUESTO_CONTROL`; faltan las claves de detalle `importe_venta`, `importe_tope` y `version_vigente` y ocultar `linea_base_id` y `linea_base_vigente_id`, o el detalle pinta claves crudas.
- No existe selector de obra en el armazón: por eso la obra de contexto va en la ruta (decisión de la persona dueña).
- Sin línea base real hasta TKT-018b. El script de semilla (Should) se apoya en `herramientas/soporte_tkt017.py` (`preparacion_sintetica()`), que no depende de pytest, y llama a `materializar_importacion` de la interfaz de `presupuesto`. Debe negarse contra un host que no sea local, como `sembrar_usuario_humo.py`. El E2E necesita dos roles (Director de Proyectos para congelar y Dirección General para capturar): hay que decidir en el diseño si son dos usuarios.

**Contrato.** Operaciones del borrador `docs/api/openapi.yaml` con `x-tickets: [TKT-017]`, sin cambios. Wireframe: [pantalla 4](../../../docs/08-wireframes.md#4-congelado-y-presupuesto-de-control).

**Módulos y capas.** Frontend: `modulos/presupuesto`, `compartido/componentes/bloqueo/etiquetas.ts` y la lista de obras de TKT-012a. Backend: ninguna capa. Sin migración.

**Dependencias cruzadas** (búsqueda de TKT-018 y de HDU-001 sobre `docs/05-tickets-trabajo.md`, los `_index.md` de `sdd/tickets/` y `tools/historias_activas.txt`):

- `docs/05-tickets-trabajo.md`: TKT-018 declara depender de TKT-017, TKT-012 y TKT-059. TKT-018a hereda TKT-017 y TKT-012a y **no** hereda TKT-059, que es de la importación (TKT-018b). TKT-059 sigue en `LISTO PARA EJECUTAR · entrega TKT-059a`, sin código.
- `sdd/tickets/tkt-017`: cita a TKT-018 en tres deudas que pasan a TKT-018b: confirmar la importación por ruta, el `NUL` de `motivo_reemplazo` y el archivo real del catálogo.
- `sdd/tickets/tkt-012a`: la spec excluye expresamente el selector de obra y su diseño descartó la ficha de obra; esta entrega añade el enlace «Línea base» a la lista de obras que TKT-012a construye.
- `tools/historias_activas.txt`: vacía. HDU-001 **no** se activa en esta entrega: sus escenarios 4 a 13, 21 y 24 a 29 son de TKT-018b, y la persona dueña dejó HDU-001 sin activar en TKT-017 (`P-13`). Los escenarios 14, 15, 17, 18, 19, 22 y 23 los cubre esta entrega, con el 19 solo en pruebas con respuestas simuladas.
