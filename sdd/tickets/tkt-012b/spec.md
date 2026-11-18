# Spec · TKT-012b · Mantenimiento y ciclo de vida de la obra

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

TKT-012a dejó la obra **creable, listable y consultable**, con su pantalla «Obras» y el botón `+` para Director de Proyectos y Dirección General. Quien entra hoy a esa pantalla no puede corregir un dato de la obra, ni eliminarla si se dio de alta por error, ni suspenderla, reactivarla o cerrarla: las cinco operaciones existen en el [borrador OpenAPI](../../../docs/api/openapi.yaml) (`actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra`, `cerrar_obra`, con `x-tickets: [TKT-012]`) pero ni el servidor ni el cliente las tienen. La entrega 3 se probó a mano el 2026-11-17 y el hueco quedó a la vista: la pantalla de obras solo permite crear.

TKT-012 original se partió el 2026-11-10 (TKT-012a / TKT-012b). Esta spec es la mitad pendiente, **con su pantalla**: la persona dueña validó el 2026-11-17 que TKT-012b lleve backend y frontend, para que las cinco operaciones se puedan ejercer desde la interfaz y no solo por API.

Hay **cinco huecos de regla** que TKT-012a dejó marcados y que esta spec debe cerrar antes del diseño (están en «Preguntas abiertas», con recomendación): qué cuenta como «historial» para `OBRA_CON_HISTORIAL`, la máquina de estados completa de la obra, qué estados bloquean la edición, el verbo de bitácora del borrado (`ELIMINAR` no existe entre los 23 verbos) y qué ve el selector con una obra suspendida. **HDU-001 solo tiene un escenario para este ticket, el 20**; el resto de criterios sale del borrador OpenAPI y de las reglas de la ficha, y se marca `(asumido)` donde la historia calla.

## Historia de usuario

**Como** Director de Proyectos (o Dirección General)
**quiero** corregir los datos de una obra, eliminarla si no tiene historial, y suspenderla, reactivarla o cerrarla
**para** mantener el catálogo de obras al día sin perder nunca un dato histórico.

Historia de referencia: [HDU-001](../../../docs/04-historias-usuario.md#hdu-001--alta-de-obra-e-importación-de-la-línea-base), escenario 20.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | `PATCH /api/v1/obras/{obra_id}` (`actualizar_obra`): cambia nombre, domicilio, los dos porcentajes, el IVA acreditable y el umbral de alerta; **no** el código ni el tipo de contrato ni el estado. Cada cambio se asienta en la bitácora con el valor anterior |
| **Must** | `DELETE /api/v1/obras/{obra_id}` (`eliminar_obra`): solo una obra **sin historial**; con historial, `409` `CONFLICTO` `OBRA_CON_HISTORIAL` con el detalle y las acciones que permite su estado (`SUSPENDER_OBRA` y `CERRAR_OBRA` desde `ACTIVA`; solo `CERRAR_OBRA` desde `PLANEACION` y `SUSPENDIDA`; ninguna desde `CERRADA`) (HDU-001 esc. 20). Eliminar se asienta en la bitácora |
| **Must** | `POST …/suspension`, `…/reactivacion` y `…/cierre` (`suspender_obra`, `reactivar_obra`, `cerrar_obra`), cada una con motivo obligatorio y asiento `SUSPENDER`, `REACTIVAR` o `CERRAR` |
| **Must** | La máquina de estados de la obra, en una función pura de dominio: qué transición admite cada estado y cuál rechaza. Respeta la transición `PLANEACION` → `ACTIVA` que ya escribe el congelado de TKT-017 (`PA-T17.8`) sin reescribirla |
| **Must** | Rechazos: `403` (rol), `401`, `404` (obra inexistente), `422` por campo y por motivo ausente, `409` por transición no admitida y por edición en estado terminal, y `409` `OBRA_CON_HISTORIAL` |
| **Must** | Pantalla «Obras»: en cada fila, las acciones **Editar**, **Eliminar**, **Suspender**, **Reactivar** y **Cerrar** según el estado y el rol; el formulario de edición reutiliza `FormularioCatalogo`; la captura de motivo reutiliza el componente de TKT-008; el `409` `OBRA_CON_HISTORIAL` se pinta como bloqueo con sus dos acciones tomadas del contrato |
| **Must** | Una prueba de extremo a extremo: editar el nombre de una obra y verlo en la lista; suspender y reactivar; intentar eliminar una obra con historial y ver el bloqueo |
| **Should** | Confirmación explícita antes de eliminar (diálogo con el código de la obra) |
| **Could** | — |
| **Won't** | Permisos por obra. Reabrir una obra `CERRADA`. Tocar la línea base, la importación o el congelado. El selector de obra del armazón (wireframe §2). Exportar la lista |

## Non-goals

- **No cambia el alta ni la lista** de TKT-012a: son regresión (`CA-R1`).
- **No define permisos por obra**: el borrador da escritura a Director de Proyectos y Dirección General sobre todas las obras.
- **No reabre obras cerradas**: `CERRADA` es terminal `(asumido)`. Reabrir sería un ticket con regla propia.
- **No decide qué hacen los demás módulos con una obra suspendida** (que Compras no pueda levantar requisiciones, por ejemplo): esa regla vive en los tickets de cada módulo y entra cuando exista su primer consumidor. Aquí solo se guarda el estado y se asienta el cambio.
- No toca la línea base, la importación ni el presupuesto de control.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | La línea base congelada es inmutable y **nada de lo que la sostiene se borra**: una obra con línea base congelada no se elimina | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-25`, `PA-02`, `PA-05`, `PA-18` | Los parámetros de la obra (porcentajes, IVA, umbral) son **por obra** y editables; ninguna constante en el código | PRD |
| Regla 8 de `CLAUDE.md` | La bitácora se escribe en la misma transacción que el cambio; un rechazo no deja asiento | [`CLAUDE.md`](../../../CLAUDE.md) |
| Regla 6 de `CLAUDE.md` | Toda obra es la unidad de imputación; ningún gasto sin obra | `CLAUDE.md` |

## Invariantes que deben sobrevivir al cambio

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Transición `PLANEACION` → `ACTIVA` del congelado (`PA-T17.8`) | El congelado de TKT-017 sigue activando la obra; la máquina de estados nueva no lo modela distinto ni lo bloquea | `CA-R1` |
| Alta, lista y consulta de TKT-012a | Sus criterios `CA-1` a `CA-13` siguen en verde | `CA-R2` |
| Restricciones de `obra` de la migración `0006` (`uq_obra_codigo`, los dos `CHECK` de rango de porcentaje, `ck_obra_umbral_alerta_pct_no_negativo`) | El motor sigue siendo la última barrera aunque el API valide antes | `CA-R3` |
| Congelado inmutable de la línea base (invariante 14) | Ninguna operación nueva toca las copias congeladas ni borra sus filas por cascada | `CA-R4` |
| Formulario de catálogo y componentes de TKT-008c | La reutilización no cambia el comportamiento ya probado | `CA-R5` |

## Criterios de aceptación

Gherkin, en español.

### CA-1 `[M]` · Corregir los datos de una obra · `RN-25`, `PA-02` · `HDU-001`

```gherkin
Escenario: Un Director de Proyectos corrige nombre y porcentajes
  Dado que existe la obra "AP-058-25" en estado "ACTIVA"
  Cuando un Director de Proyectos envía PATCH /api/v1/obras/{id} con
    nombre "Union Square F2 (ampliación)" y retencion_destajo_pct "0.100000"
  Entonces responde 200 con la obra actualizada
  Y el código, el tipo de contrato y el estado no cambian
  Y la bitácora tiene un asiento ACTUALIZAR de esa obra con el valor anterior y el nuevo de cada campo cambiado
  Y el asiento se escribió en la misma transacción que el cambio
```

Variantes, cada una con su test: Dirección General edita igual; `umbral_alerta_pct` a `null` borra el umbral; un cuerpo que no cambia ningún valor responde 200 sin asiento nuevo `(asumido)`.

### CA-2 `[M]` · Rechazo · Campos que no se editan · `HDU-001`

```gherkin
Esquema del escenario: El cuerpo intenta cambiar un dato fijo
  Dado una obra existente
  Cuando un Director de Proyectos envía PATCH con <campo>
  Entonces responde 422 con tipo "VALIDACION" señalando <campo>
  Y la obra y la bitácora no cambian

  Ejemplos:
    | campo         |
    | codigo        |
    | tipo_contrato |
    | estado        |
    | cuerpo vacío  |
```

### CA-3 `[M]` · Rechazo · Forma y rango de los cambios · `PA-02`

```gherkin
Esquema del escenario: El cambio no cumple la forma del contrato
  Dado una obra existente
  Cuando un Director de Proyectos envía PATCH con <defecto>
  Entonces responde 422 con tipo "VALIDACION" señalando el campo
  Y no se escribe ningún cambio ni asiento

  Ejemplos:
    | defecto                                        |
    | nombre vacío                                   |
    | domicilio vacío                                |
    | porcentaje fuera de rango o con más de 6 decimales |
    | iva_acreditable no booleano                    |
    | texto con carácter NUL                         |
```

### CA-4 `[M]` · Rechazo · Editar una obra cerrada · `(asumido)`

```gherkin
Escenario: La obra está CERRADA
  Dado que la obra está en estado "CERRADA"
  Cuando un Director de Proyectos envía PATCH /api/v1/obras/{id}
  Entonces responde 409 con tipo "CONFLICTO" y codigo "ESTADO_NO_PERMITE_OPERACION"
  Y el detalle trae el estado actual
  Y la obra y la bitácora no cambian
```

### CA-5 `[M]` · Eliminar una obra sin historial · `HDU-001 esc. 20`

```gherkin
Escenario: Se elimina una obra recién dada de alta
  Dado que la obra "AP-099-26" está en "PLANEACION", sin línea base, sin importaciones y sin movimientos
  Cuando un Director de Proyectos envía DELETE /api/v1/obras/{id}
  Entonces responde 204
  Y la obra deja de existir y ya no aparece en GET /api/v1/obras
  Y la bitácora conserva un asiento del borrado con el código y el nombre de la obra
  Y el código "AP-099-26" queda libre para un alta nueva
```

### CA-6 `[M]` · Rechazo · Eliminar una obra con historial · `RN-01` · `HDU-001 esc. 20`

```gherkin
Escenario: La obra tiene línea base congelada y movimientos
  Dado que la obra "AP-058-25" tiene una línea base "CONGELADA"
  Cuando un Director de Proyectos envía DELETE /api/v1/obras/{id}
  Entonces responde 409 con tipo "CONFLICTO" y codigo "OBRA_CON_HISTORIAL"
  Y el detalle trae linea_base_congelada y el conteo de movimientos
  Y las acciones incluyen SUSPENDER_OBRA y CERRAR_OBRA, con método POST y la ruta de esa obra
  Y la obra, su línea base y todos sus datos siguen intactos
  Y no se asienta nada en la bitácora
```

Un segundo ejemplo, con la obra sin línea base congelada pero **con una importación**, responde igual con `linea_base_congelada` falso (ver D-1).

### CA-7 `[M]` · Rechazo · Eliminar en carrera con el congelado · `RN-01`

```gherkin
Escenario: El congelado llega a la vez que el borrado
  Dado una obra en "PLANEACION" con una línea base en "BORRADOR" lista para congelar
  Cuando llegan a la vez DELETE de la obra y el congelado de su línea base
  Entonces el congelado gana y el borrado responde 409 con codigo "OBRA_CON_HISTORIAL"
  Y nunca queda una línea base "CONGELADA" sin obra
  Y ninguna responde 500
```

Lectura fijada en el diseño (D-DIS-3): con historial amplio, una línea base `BORRADOR` materializada ya es historial, así que el borrado nunca gana. La carrera real de borrado contra la escritura de una fila que cuelga de la obra se prueba aparte (TC-56).

### CA-8 `[M]` · Suspender, reactivar y cerrar · `HDU-001 esc. 20`

```gherkin
Esquema del escenario: Una transición admitida
  Dado que la obra está en <origen>
  Cuando un Director de Proyectos envía <operación> con un motivo
  Entonces responde 200 con la obra en <destino>
  Y la bitácora tiene un asiento <verbo> con el estado anterior y el motivo
  Y ningún dato histórico de la obra se pierde

  Ejemplos:
    | origen     | operación  | destino    | verbo     |
    | ACTIVA     | suspension | SUSPENDIDA | SUSPENDER |
    | SUSPENDIDA | reactivacion | ACTIVA   | REACTIVAR |
    | ACTIVA     | cierre     | CERRADA    | CERRAR    |
    | SUSPENDIDA | cierre     | CERRADA    | CERRAR    |
    | PLANEACION | cierre     | CERRADA    | CERRAR    |
```

Dirección General puede igual. La transición `PLANEACION` → `CERRADA` está admitida (D-2, resuelta el 2026-11-17; ejemplo añadido en el diseño, D-DIS-6).

### CA-9 `[M]` · Rechazo · Transición no admitida · `(asumido)`

```gherkin
Esquema del escenario: La máquina de estados no admite la transición
  Dado que la obra está en <origen>
  Cuando un Director de Proyectos envía <operación> con un motivo
  Entonces responde 409 con tipo "CONFLICTO" y codigo "ESTADO_NO_PERMITE_OPERACION"
  Y el detalle trae el estado actual y las transiciones que sí admite
  Y la obra y la bitácora no cambian

  Ejemplos:
    | origen      | operación    |
    | PLANEACION  | suspension   |
    | PLANEACION  | reactivacion |
    | ACTIVA      | reactivacion |
    | SUSPENDIDA  | suspension   |
    | CERRADA     | suspension   |
    | CERRADA     | reactivacion |
    | CERRADA     | cierre       |
```

### CA-10 `[M]` · Rechazo · Motivo ausente · `(asumido)`

```gherkin
Escenario: Suspender, reactivar o cerrar sin motivo
  Dado una obra en un estado que admite la transición
  Cuando se envía la transición sin motivo, vacío, de solo espacios o de más de la longitud máxima del contrato
  Entonces responde 422 con tipo "VALIDACION" señalando motivo
  Y la obra y la bitácora no cambian
```

### CA-11 `[M]` · Rechazo · Rol y sesión · `RN-25`

```gherkin
Esquema del escenario: Quien no puede operar
  Dado una obra existente
  Cuando <quien> envía cualquiera de las cinco operaciones
  Entonces responde <código> con el tipo del contrato de error
  Y la obra y la bitácora no cambian

  Ejemplos:
    | quien                              | código |
    | un usuario sin sesión              | 401    |
    | Compras, Almacén, Residente o Administración | 403 |
    | una solicitud sin cabecera CSRF    | 403    |
```

`403` es `PERMISO`: *«No tienes permiso»*, sin cifras. La consulta (`GET`) sigue abierta a los seis roles (`CA-R2`).

### CA-12 `[M]` · Rechazo · Obra inexistente

```gherkin
Escenario: El identificador no existe
  Cuando un Director de Proyectos envía cualquiera de las cinco operaciones sobre un obra_id que no existe
  Entonces responde 404 con tipo "NO_ENCONTRADO"
  Y no se asienta nada
```

### CA-13 `[M]` · Dos transiciones simultáneas · `(asumido)`

```gherkin
Escenario: Suspender y cerrar a la vez
  Dado que la obra está "ACTIVA"
  Cuando llegan a la vez su suspensión y su cierre
  Entonces ambas se serializan con la fila bloqueada
  Y el resultado final es coherente con la máquina de estados: o "CERRADA", o "SUSPENDIDA" y después "CERRADA" admitida
  Y cada operación que gana deja su asiento y ninguna responde 500
```

### CA-14 `[M]` · Pantalla · Acciones de la fila según estado y rol · `wireframe «Obras»`

```gherkin
Esquema del escenario: La fila ofrece solo lo que procede
  Dado que el usuario entró como <rol> y la obra está en <estado>
  Cuando abre «Obras»
  Entonces la fila ofrece <acciones>

  Ejemplos:
    | rol                 | estado     | acciones                              |
    | Director de Proyectos | PLANEACION | Editar, Eliminar, Cerrar           |
    | Director de Proyectos | ACTIVA     | Editar, Suspender, Cerrar           |
    | Director de Proyectos | SUSPENDIDA | Editar, Reactivar, Cerrar           |
    | Director de Proyectos | CERRADA    | ninguna                             |
    | Compras             | cualquiera | ninguna (solo consulta)               |
```

Es cortesía de navegación: el control real es el `403` del servidor (como en TKT-012a).

### CA-15 `[M]` · Pantalla · Editar · `HDU-001`

```gherkin
Escenario: Se edita el nombre desde la lista
  Dado que el Director de Proyectos está en «Obras» con la obra "AP-058-25"
  Cuando pulsa «Editar», cambia el nombre y guarda
  Entonces el formulario se cierra y la lista muestra el nombre nuevo sin recargar la página
  Y el código y el tipo de contrato aparecen en el formulario solo de lectura
```

Un `422` se pinta junto al campo, no en una pantalla aparte.

### CA-16 `[M]` · Pantalla · Eliminar con historial muestra el bloqueo · `HDU-001 esc. 20`

```gherkin
Escenario: Se intenta eliminar la obra con línea base congelada
  Dado que el Director de Proyectos pulsa «Eliminar» sobre una obra con historial
  Cuando el servidor responde 409 OBRA_CON_HISTORIAL
  Entonces la pantalla muestra el bloqueo con el mensaje del servidor y el detalle
  Y ofrece las acciones que el contrato da para el estado de la obra, no cableadas: «Suspender» y «Cerrar» desde `ACTIVA`; solo «Cerrar» desde `PLANEACION` y `SUSPENDIDA`; ninguna desde `CERRADA`
  Y la obra sigue en la lista
```

### CA-17 `[M]` · Pantalla · Suspender y reactivar con motivo

```gherkin
Escenario: Se suspende y se reactiva con motivo
  Dado que el Director de Proyectos pulsa «Suspender» sobre una obra "ACTIVA"
  Cuando captura el motivo y confirma
  Entonces la fila pasa a "Suspendida" y ofrece «Reactivar»
  Y sin motivo el botón de confirmar no envía y el campo señala el error
```

### CA-18 `[M]` · Prueba de extremo a extremo

```gherkin
Escenario: Recorrido de mantenimiento de una obra
  Dado un Director de Proyectos autenticado y dos obras sembradas con un código único por corrida:
    M1 en "ACTIVA" con línea base congelada, y M2 en "PLANEACION" con línea base "BORRADOR" (con historial)
  Cuando edita el nombre de M1, la suspende, la reactiva y la lista
  Y después intenta eliminar M2
  Entonces ve el nombre nuevo, los estados Suspendida y Activa de M1 y el bloqueo OBRA_CON_HISTORIAL de M2
```

Dos obras porque «Eliminar» solo se ofrece en `PLANEACION` (`CA-14`) y suspender exige `ACTIVA` (D-DIS-2).

### Criterios de regresión

- **CA-R1 `[M]`** El congelado de TKT-017 sigue pasando `PLANEACION` → `ACTIVA` con la máquina de estados nueva en el código.
- **CA-R2 `[M]`** Los criterios de TKT-012a (alta, lista, consulta, conflicto de código) siguen en verde; `GET` sigue abierto a los seis roles.
- **CA-R3 `[M]`** Los `CHECK` y `uq_obra_codigo` de `0006` siguen rechazando lo mismo si se llega al motor saltándose el API.
- **CA-R4 `[M]`** Eliminar una obra sin historial no deja huérfanas ni altera filas de líneas base congeladas de otras obras.
- **CA-R5 `[M]`** Las pruebas de `FormularioCatalogo` y de los componentes de motivo y bloqueo de TKT-008c no cambian.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Solo depende de TKT-012a (archivado) |
| **N** | Describe el qué, no impone el cómo | Sí | El «historial», los estados y el verbo de bitácora quedan como decisiones del diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Director de Proyectos y Dirección General corrigen, eliminan y cambian el ciclo de vida desde la pantalla |
| **E** | Estimable sin investigar antes | Sí | Los cinco huecos de regla (D-1 a D-5) se resolvieron el 2026-11-17 |
| **S** | Cabe en una sesión sin romper contexto | **No** | Cinco operaciones de backend más pantalla y E2E superan el tope de unas 400 líneas por cambio; el diseño las parte en entregas **a** (backend) y **b** (pantalla y E2E) en **un solo PR** |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio nombra un resultado observable |

Un fallo (S), con la propuesta de partición en entregas. No se rebaja a Spike.

## Definition of Done

La de funcionalidad de `sdd/metodologia.md` §8.

- [ ] Los criterios `[M]` `CA-1` a `CA-18` y `CA-R1` a `CA-R5` con su prueba en verde
- [ ] Una prueba de extremo a extremo (`CA-18`) en el pipeline
- [ ] Borrador OpenAPI y tipos del cliente reconciliados con lo construido (incluido el verbo nuevo de bitácora, si D-4 lo confirma)
- [ ] Wireframe «Obras» actualizado con las acciones de fila
- [ ] Cierre de los huecos de TKT-012a en `docs/05-tickets-trabajo.md` y `docs/03-modelo-datos.md` (máquina de estados de la obra)

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| D-1 | **¿Qué cuenta como «historial» de una obra?** HDU-001 esc. 20 dice «línea base congelada y movimientos». Recomendación: historial = **cualquier** línea base distinta de `BORRADOR` sin filas, o cualquier importación, o cualquier fila de presupuesto de control **o** cualquier fila de módulos posteriores que cuelgue de `obra_id` (se consulta por la interfaz publicada de cada módulo, hoy vacío). Cuatro tablas de `presupuesto` ya llevan `obra_id` | Si es más estrecho, se pierde una importación o un tope capturado; si es más ancho, no se pueden corregir altas hechas por error | **Resuelta 2026-11-17**: amplio, como se recomienda |
| D-2 | **Máquina de estados.** Recomendación: `PLANEACION → ACTIVA` (congelado), `ACTIVA ↔ SUSPENDIDA`, `ACTIVA → CERRADA`, `SUSPENDIDA → CERRADA`, y `PLANEACION → CERRADA` **admitida** (una obra que nunca arrancó se cierra sin eliminarse); `CERRADA` terminal. El borrador ya marca `reactivacion` como `(asumido)` | Sin `PLANEACION → CERRADA`, una obra sin historial que no se quiere eliminar no tiene salida | **Resuelta 2026-11-17**: con `PLANEACION → CERRADA`; `CERRADA` terminal |
| D-3 | **Qué estados bloquean la edición.** Recomendación: solo `CERRADA` (`CA-4`); `SUSPENDIDA` se edita | Si también `SUSPENDIDA` está bloqueada, hay que reactivar para corregir un nombre | **Resuelta 2026-11-17** con D-2: solo `CERRADA` bloquea la edición |
| D-4 | **Verbo de bitácora del borrado.** `ELIMINAR` no existe entre los 23 verbos. Recomendación: migración que lo añade (como `DAR_BAJA` en `0016`, ADR incluido) en vez de reutilizar `CANCELAR` o `ANULAR`, cuyo significado es otro | Con migración, la bajada tiene que ser segura como la de `0016` | **Resuelta 2026-11-17**: verbo nuevo `ELIMINAR` con migración, ADR y bajada segura |
| D-5 | **El borrado es físico.** `eliminar_obra` borra la fila (a diferencia del proveedor, que nunca se borra). Recomendación: físico, porque solo procede sin historial y el código queda libre para reutilizarse | Con borrado lógico, `uq_obra_codigo` retiene el código para siempre y cualquier alta con ese código da `CODIGO_OBRA_DUPLICADO` | **Resuelta 2026-11-17** con D-4: borrado físico |
| S-1 | El motivo es obligatorio en las **tres** transiciones, no solo en suspender `(asumido)`: el borrador usa `MotivoObligatorio` en las tres | Si la reactivación no lo exige, `CA-10` pierde un ejemplo | `(asumido)` |
| S-2 | Una edición sin cambios reales responde 200 sin asiento `(asumido)` | Un asiento vacío ensucia la bitácora | `(asumido)` |
| S-3 | Qué hace cada módulo con una obra suspendida no se decide aquí; se pregunta en el ticket de cada módulo | Si Compras levanta requisiciones contra una obra suspendida, el estado no significa nada | Diferida a los tickets de requisición y entrada |

## Pasada adversarial

Aplicada por quien redacta esta spec, no por un subagente `abogado-del-diablo`; conviene repetirla con la skill en `/sdd-disenar`.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | «Movimientos» en esc. 20 no tiene tabla hoy: `requisicion`, `orden_compra` y `movimiento_inventario` cuelgan de obra a través de otros módulos o aún no existen. Un borrado que ignore lo que el diseño de esos módulos añadirá sería inseguro más adelante | `CA-6` exige el conteo de movimientos por la interfaz publicada y D-1 lo deja como decisión; el diseño debe definir el puerto y dejarlo en cero hoy |
| 2 | Alta | El borrado y el congelado compiten por la misma fila: una línea base `CONGELADA` sin obra rompería el invariante 14 | `CA-7` y `CA-R4`; el diseño decide el bloqueo (`FOR UPDATE` de la obra) |
| 3 | Media | `PATCH` permite cambiar `retencion_destajo_pct` y `fondo_garantia_pct` con la obra `ACTIVA`: cambia retroactivamente destajos ya calculados | Fuera de esta entrega: no existe destajo en la fase 1. Se anota como pregunta para el módulo de destajo |
| 4 | Media | Un usuario edita el nombre en dos pestañas: gana el último sin aviso | `(asumido)` último gana en la fase 1; sin control de concurrencia optimista. Se registra como supuesto |
| 5 | Baja | La acción `SUSPENDER_OBRA` del `409` apunta a una transición que, para una obra en `PLANEACION`, no existe (`CA-9`) | El diseño debe ofrecer solo las acciones que la máquina de estados admite desde el estado actual |

## Contexto técnico

- **Backend:** módulo `presupuesto`. Ya existe `cimenta/presupuesto/aplicacion/obras.py` (alta, lista, consulta) y la tabla `obra` (migración `0006`). Hay que añadir cinco casos de uso, la función pura de la máquina de estados en `dominio/`, el verbo de bitácora si D-4 lo confirma y las cinco rutas en el enrutador existente.
- **Contrato:** `docs/api/openapi.yaml` ya trae las cinco operaciones con `x-tickets: [TKT-012]` y los esquemas `ObraCambios`, `MotivoObligatorio` y `ErrorConflictoEstado`. Hay que actualizar sus `x-tickets` a `TKT-012b` y, si D-4 procede, el enum `AccionBitacora`.
- **Frontend:** `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` (hoy solo con el botón de alta, línea 159), `obras.consultas.ts` y `obras.formulario.ts`; tipos en `frontend/src/api/generado/servidor.ts`. Hay una prueba E2E de alta en `frontend/e2e/obras.spec.ts`.
- **Documentos que cambian:** `docs/05-tickets-trabajo.md` (cierre de la partición), `docs/03-modelo-datos.md` (máquina de estados de `obra`), `docs/08-wireframes.md` (acciones de la fila), `docs/04-historias-usuario.md` (escenarios nuevos si la persona dueña los quiere en la historia).
