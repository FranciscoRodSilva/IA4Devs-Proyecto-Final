# Spec · TKT-029b · Baja protegida de proveedores

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

TKT-029a entregó el catálogo de proveedores sin baja: un proveedor solo puede pasar de `ACTIVO` a `DESACTIVADO`, y ninguna operación escribe `BAJA`. Falta la mitad del escenario 12 de HDU-004: **dar de baja de forma definitiva** a un proveedor, y que el sistema **rechace la baja si tiene órdenes de compra pendientes de recibir**, listándolas y ofreciendo desactivarlo.

La razón del rechazo es de negocio, no de forma: una orden `ABIERTA` o `PARCIAL` todavía va a recibir material de ese proveedor. Si el proveedor se diera de baja, la entrada de almacén y el cierre de la orden quedarían apuntando a un proveedor retirado. Desactivarlo sí se admite siempre, porque solo lo saca del selector de órdenes nuevas y conserva todo lo demás.

Hasta TKT-019 no existían las tablas de órdenes. Ahora existen (migración `0014`), pero el módulo `compras` **no tiene todavía código Python**: su `interfaz.py` está vacío. Para que `proveedores` pregunte por las órdenes pendientes sin tocar las tablas de otro módulo (regla 3 de `CLAUDE.md`), este ticket añade en `compras` una única función de lectura publicada en su interfaz.

El 2026-11-15 la persona dueña resolvió las cuatro decisiones que la documentación dejaba abiertas: el puerto `CatalogoProveedores` **no** entra aquí (queda en TKT-030, su primer consumidor); la baja se asienta con un **verbo nuevo `DAR_BAJA`** (migración `0016`); la baja procede desde `ACTIVO` y desde `DESACTIVADO`, y `BAJA` es terminal; y `compras` publica una **función mínima** de lectura de órdenes pendientes.

## Historia de usuario

**Como** responsable de Compras
**quiero** dar de baja definitiva a un proveedor con el que ya no voy a trabajar, y que el sistema me lo impida mientras tenga material por recibir
**para** no perder la trazabilidad de las órdenes en curso, conservando la salida de desactivarlo para que no reciba órdenes nuevas.

Historia de referencia: [HDU-004](../../../docs/04-historias-usuario.md#hdu-004--proveedores-y-emisión-de-órdenes-de-compra), escenario 12 completo. TKT-029a cubrió su mitad de desactivación; este ticket cubre la baja y su rechazo.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | `POST /api/v1/proveedores/{proveedor_id}/baja` (`dar_baja_proveedor`) con motivo obligatorio: pasa el proveedor de `ACTIVO` o `DESACTIVADO` a `BAJA` y responde `200` con el `Proveedor` |
| **Must** | Rechazo `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` si tiene órdenes `ABIERTA` o `PARCIAL`: `detalle.ordenes` con `{id, folio, estado}` de cada una, ordenadas por folio, y la acción `DESACTIVAR_PROVEEDOR` solo si el proveedor está `ACTIVO` |
| **Must** | Desde `BAJA`, `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado actual. `BAJA` es terminal: no hay reactivación |
| **Must** | Función de lectura en `cimenta.compras.interfaz` que devuelve las órdenes pendientes de un proveedor (con su estado derivado de las cantidades), y que `proveedores` consume sin importar nada más de `compras` |
| **Must** | Verbo `DAR_BAJA` en la bitácora: migración `0016` sobre la cabeza `0015`, cambio del borrador (`AccionBitacora`) y del conteo de verbos en el mismo PR. El asiento lleva el motivo y se escribe en la misma transacción |
| **Must** | Concurrencia: la baja toma el proveedor con `FOR UPDATE`; dos bajas simultáneas dejan exactamente una ganadora, y el vencimiento de `lock_timeout` o `statement_timeout` responde `409` `CONCURRENCIA` |
| **Must** | Prueba con una orden `PARCIAL` **sembrada con `cantidad_recibida` mayor que cero** contra PostgreSQL real con el rol de aplicación; el mismo escenario comprueba que desactivar a ese proveedor sí procede y que sus órdenes siguen intactas |
| **Must** | Documentación y contrato reconciliados en el mismo PR: `x-tickets` de `dar_baja_proveedor`, la frase «desactivar se admite siempre» de `docs/07` y `docs/03`, la sección «Proveedor» de modelo de datos §14, la partición de `docs/05`, y las pruebas de TKT-029a (`TC-38` y `TC-40`) que afirman que `/baja` no existe |
| **Should** | Una nota en TKT-030 de `docs/05`: la emisión de una orden lee el proveedor con `FOR SHARE`, para que no se cuele una orden entre la comprobación de la baja y su escritura |
| **Could** | — |
| **Won't** | El puerto `CatalogoProveedores` (TKT-030). La reactivación de un proveedor `DESACTIVADO` o `BAJA`. La pantalla del catálogo y el escenario 1 de HDU-004, y la reconciliación del boceto de `docs/08-wireframes.md` (TKT-032). La consulta proveedor × obra, escenario 11 (TKT-032). Activar HDU-004 en `tools/historias_activas.txt` |

## Non-goals

- **No hay borrado físico.** Ninguna operación borra un proveedor; no existe `DELETE` sobre `/proveedores`, y el rol de aplicación ya no tiene ese privilegio (TKT-029a).
- **No hay reactivación.** Un proveedor en `BAJA` no vuelve a otro estado, y uno `DESACTIVADO` solo puede dejar de serlo pasando a `BAJA`.
- **No libera el RFC.** Un proveedor en `BAJA` conserva su RFC y `UNIQUE (rfc)` (invariante 28) sigue impidiendo un alta nueva con el mismo valor. Quien quiera volver a trabajar con él no puede darlo de alta otra vez: eso es una decisión de negocio que esta spec no toma.
- **No declara ni implementa `CatalogoProveedores`.** Tampoco emite, cancela ni lee órdenes más allá de la función de órdenes pendientes.
- **No añade pantalla ni toca el frontend.** Los tipos del cliente se regeneran porque cambia el borrador.
- **No cancela ni reprograma órdenes** para destrabar una baja. Una orden `PARCIAL` abandonada bloquea la baja hasta que se reciba entera o se cancele por las rutas de TKT-031 y TKT-054; la salida mientras tanto es desactivar.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| Ninguna `RN-xx` propia | El rechazo de la baja es `CONFLICTO` con su `codigo` del catálogo cerrado, no `REGLA_NEGOCIO`. La operación declara `x-reglas: []` | [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml) `dar_baja_proveedor`; [`docs/07-especificacion-api.md`](../../../docs/07-especificacion-api.md) |
| `RN-06` (contexto) | Una orden no se cierra con saldo pendiente: el faltante se reprograma. Por eso una orden `PARCIAL` puede seguir pendiente indefinidamente, y la baja la respeta | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |

Invariantes del modelo de datos que toca: **28** (`UNIQUE (rfc)`: la baja no libera el RFC), **10** (la bitácora no se modifica: el asiento `DAR_BAJA` solo se anexa) y, en la siembra de la prueba, **8** y **2** (cantidades no negativas y `cantidad_recibida` dentro de lo ordenado más el excedente autorizado). Reglas de `CLAUDE.md`: **3** (módulos solo por su interfaz), **8** (bitácora en la misma transacción), **11** (rutas `def`) y **14** (cada regla con su rechazo).

## Invariantes que deben sobrevivir al cambio

El ticket **modifica algo que ya funciona**: añade una migración sobre `0015`, un verbo a la bitácora, una operación a un enrutador existente y la primera función publicada de `compras`.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Cadena de migraciones y privilegios por omisión de los tres roles | `0016` cuelga de `0015`, sube y baja sin dejar objetos huérfanos y no abre permisos | `CA-R1` |
| Frontera entre módulos (regla 3) | `proveedores` solo importa `cimenta.compras.interfaz`; `compras` no importa `proveedores`; `analitica` y los demás no cambian | `CA-R2` |
| Comportamiento de TKT-029a | Alta, listado, consulta, cambio de datos y desactivación siguen como estaban; solo cambian las dos afirmaciones de que `/baja` no existe | `CA-R3` |
| Rutas protegidas y CSRF (TKT-006, TKT-057) | La mutación nueva exige sesión, CSRF y rol `COMPRAS` | `CA-R4` |
| Bitácora de solo anexado (invariante 10) | Los asientos existentes no cambian y el verbo nuevo no rompe la lectura de los anteriores | `CA-R1` |

## Criterios de aceptación

Gherkin, en español. El camino feliz de la baja **no tiene escenario propio en la historia**: lo respaldan `docs/05-tickets-trabajo.md` (TKT-029) y el borrador. Sus tests llevan `esc12` en el nombre.

### CA-1 `[M]` · Baja de un proveedor sin órdenes pendientes · `HDU-004 esc. 12`

```gherkin
Escenario: Compras da de baja a un proveedor que no tiene órdenes pendientes
  Dado el proveedor "CoPanel" en estado ACTIVO sin ninguna orden de compra
  Y un usuario autenticado con rol COMPRAS
  Cuando envía POST /api/v1/proveedores/{id}/baja con el motivo "Cerró su negocio"
  Entonces responde 200 con el proveedor en estado "BAJA"
  Y deja de aparecer en GET /api/v1/proveedores sin indicar estado
  Y sigue apareciendo con estado=BAJA y en GET /api/v1/proveedores/{id}
  Y su fila, su RFC y todos sus datos se conservan sin cambio
  Y la bitácora tiene un asiento DAR_BAJA con el motivo, los datos anteriores (estado ACTIVO) y los posteriores (estado BAJA), escrito en la misma transacción
```

### CA-2 `[M]` · Baja de un proveedor desactivado · `HDU-004 esc. 12`

```gherkin
Escenario: Un proveedor DESACTIVADO sin órdenes pendientes pasa a BAJA
  Dado el proveedor "CoPanel" en estado DESACTIVADO sin órdenes pendientes
  Cuando Compras envía POST /api/v1/proveedores/{id}/baja con un motivo
  Entonces responde 200 con el proveedor en estado "BAJA"
  Y el asiento DAR_BAJA guarda el estado anterior DESACTIVADO
```

### CA-3 `[M]` · Rechazo · Órdenes pendientes · `HDU-004 esc. 12`

```gherkin
Escenario: El proveedor activo tiene órdenes ABIERTA y PARCIAL
  Dado el proveedor "CoPanel" ACTIVO con una orden ABIERTA (nada recibido) y otra PARCIAL (con cantidad_recibida mayor que cero)
  Cuando Compras envía POST /api/v1/proveedores/{id}/baja con un motivo
  Entonces responde 409 con tipo "CONFLICTO" y codigo "PROVEEDOR_CON_ORDENES_ABIERTAS"
  Y detalle.ordenes lista las dos órdenes con su id, su folio y su estado (ABIERTA, PARCIAL), ordenadas por folio
  Y el mensaje nombra al proveedor y cuántas órdenes tiene pendientes
  Y acciones trae DESACTIVAR_PROVEEDOR con método POST y la ruta /api/v1/proveedores/{id}/desactivacion
  Y el proveedor sigue ACTIVO
  Y no se asienta nada en la bitácora
```

### CA-4 `[M]` · Rechazo · Órdenes pendientes con el proveedor ya desactivado · `HDU-004 esc. 12`

```gherkin
Escenario: Un proveedor DESACTIVADO con una orden pendiente tampoco se da de baja
  Dado el proveedor "CoPanel" DESACTIVADO con una orden PARCIAL
  Cuando Compras envía POST /api/v1/proveedores/{id}/baja con un motivo
  Entonces responde 409 con tipo "CONFLICTO" y codigo "PROVEEDOR_CON_ORDENES_ABIERTAS" con la orden listada
  Y acciones queda vacía, porque desactivar de nuevo respondería 409
  Y el proveedor sigue DESACTIVADO y no se asienta nada
```

### CA-5 `[M]` · Qué cuenta como orden pendiente · `HDU-004 esc. 12`

```gherkin
Esquema del escenario: Solo bloquean las órdenes vivas con material por recibir de ese proveedor
  Dado el proveedor "CoPanel" ACTIVO con una orden <orden>
  Cuando Compras envía POST /api/v1/proveedores/{id}/baja con un motivo
  Entonces responde <resultado>

  Ejemplos:
    | orden                                                                            | resultado                                  |
    | CERRADA: todos los renglones con cantidad_recibida igual a cantidad_ordenada     | 200, queda en BAJA                         |
    | CERRADA con excedente autorizado: recibida mayor que ordenada                    | 200, queda en BAJA                         |
    | CANCELADA (cancelada_en con valor), aunque no haya recibido nada                 | 200, queda en BAJA                         |
    | de otro proveedor, ABIERTA                                                       | 200, queda en BAJA                         |
    | ABIERTA con un solo renglón sin nada recibido                                    | 409 PROVEEDOR_CON_ORDENES_ABIERTAS         |
    | PARCIAL con un renglón completo y otro con saldo                                 | 409 PROVEEDOR_CON_ORDENES_ABIERTAS         |
```

### CA-6 `[M]` · Desactivar sí procede con órdenes pendientes · `HDU-004 esc. 12`

```gherkin
Escenario: Tras el rechazo, Compras desactiva al proveedor y sus órdenes siguen recibiendo
  Dado el rechazo de CA-3, con una orden PARCIAL sembrada con cantidad_recibida mayor que cero
  Cuando Compras envía POST /api/v1/proveedores/{id}/desactivacion con un motivo
  Entonces responde 200 con el proveedor en estado "DESACTIVADO"
  Y deja de aparecer en el selector
  Y la orden PARCIAL conserva su proveedor, su estado y sus cantidades sin cambio
  Y un intento posterior de baja sigue respondiendo 409 PROVEEDOR_CON_ORDENES_ABIERTAS
```

### CA-7 `[M]` · Rechazo · Un proveedor ya dado de baja · `HDU-004 esc. 12`

```gherkin
Escenario: BAJA es terminal
  Dado un proveedor en estado BAJA
  Cuando Compras envía POST /api/v1/proveedores/{id}/baja con un motivo
  Entonces responde 409 con tipo "CONFLICTO" y codigo "ESTADO_NO_PERMITE_OPERACION"
  Y el detalle indica el estado actual "BAJA"
  Y no se asienta nada

Escenario: Un proveedor en BAJA tampoco se desactiva
  Dado un proveedor en estado BAJA
  Cuando Compras envía POST /api/v1/proveedores/{id}/desactivacion con un motivo
  Entonces responde 409 "ESTADO_NO_PERMITE_OPERACION" con el estado actual "BAJA"
```

### CA-8 `[M]` · Rechazo · Motivo obligatorio · `HDU-004 esc. 12`

```gherkin
Escenario: La baja exige un motivo válido
  Cuando el motivo falta, está en blanco, tiene más de 2000 caracteres o contiene NUL
  Entonces responde 422 con tipo "VALIDACION" señalando el motivo
  Y el proveedor conserva su estado y no se asienta nada
```

### CA-9 `[M]` · Rechazo · Permiso, sesión y CSRF

```gherkin
Escenario: Un rol que no gestiona proveedores intenta la baja
  Dado un usuario autenticado con rol DIRECCION_GENERAL, DIRECTOR_PROYECTOS, RESIDENTE, ALMACEN o ADMINISTRACION
  Cuando envía POST /api/v1/proveedores/{id}/baja con un cuerpo válido
  Entonces responde 403 con tipo "PERMISO"
  Y el intento queda asentado como DENEGAR en la bitácora
  Y el proveedor no cambia

Escenario: Sin sesión o sin CSRF
  Cuando alguien sin sesión envía POST /api/v1/proveedores/{id}/baja
  Entonces responde 401
  Cuando un usuario COMPRAS con sesión lo envía sin la cabecera CSRF válida
  Entonces responde 403 sin cambiar nada
```

### CA-10 `[M]` · Rechazo · Proveedor inexistente o identificador mal formado

```gherkin
Escenario: El proveedor no existe
  Cuando Compras envía la baja para un identificador de proveedor inexistente
  Entonces responde 404 y no se asienta nada
  Cuando envía un identificador que no es UUID
  Entonces responde 422 con tipo "VALIDACION"
```

### CA-11 `[M]` · Concurrencia · Dos bajas simultáneas y bloqueo vencido

```gherkin
Escenario: Dos bajas del mismo proveedor llegan a la vez
  Dado el proveedor "CoPanel" ACTIVO sin órdenes pendientes
  Cuando dos solicitudes de baja llegan a la vez
  Entonces exactamente una responde 200
  Y la otra responde 409 "CONFLICTO" "ESTADO_NO_PERMITE_OPERACION" con el estado actual "BAJA"
  Y queda un solo asiento DAR_BAJA y ninguna solicitud responde 500

Escenario: Otra transacción retiene el proveedor y vence el bloqueo
  Dado otra transacción que mantiene bloqueada la fila del proveedor
  Cuando Compras envía la baja y vence lock_timeout
  Entonces responde 409 con tipo "CONCURRENCIA" y codigo "BLOQUEO_VENCIDO"
  Y la respuesta lleva la cabecera Retry-After y la acción REINTENTAR
  Y el proveedor no cambia y no se asienta nada
```

### CA-12 `[M]` · La función de órdenes pendientes de `compras`

```gherkin
Escenario: compras publica las órdenes pendientes de un proveedor
  Dado órdenes de varios proveedores: ABIERTA, PARCIAL, CERRADA y CANCELADA
  Cuando proveedores pide por cimenta.compras.interfaz las órdenes pendientes de uno de ellos, con la sesión de la transacción en curso
  Entonces recibe solo las suyas que están ABIERTA o PARCIAL, cada una con su id, su folio y su estado derivado de las cantidades
  Y las recibe ordenadas por folio
  Y ninguna orden cancelada, cerrada ni de otro proveedor aparece
  Y la función no escribe nada

Escenario: Estado derivado de los renglones
  Dado una orden viva con dos renglones, uno con cantidad_recibida igual a la ordenada y otro con cantidad_recibida cero
  Cuando se consulta
  Entonces su estado es PARCIAL, porque hay algo recibido y algo por recibir

Escenario: Rechazo · la consulta no se salta la frontera
  Cuando corre lint-imports
  Entonces proveedores no importa nada de compras fuera de cimenta.compras.interfaz
```

### CA-13 `[M]` · Nunca se borra un proveedor · `HDU-004 esc. 12`

```gherkin
Escenario: La baja es lógica y el motor y el enrutador lo siguen garantizando
  Cuando una prueba recorre el enrutador de la aplicación
  Entonces no existe ninguna operación DELETE sobre /proveedores ni sobre /proveedores/{proveedor_id}
  Y el rol de aplicación sigue sin privilegio DELETE sobre proveedor

Escenario: El RFC de un proveedor en BAJA sigue ocupado
  Dado un proveedor en BAJA con el RFC "XAXX010101000"
  Cuando Compras envía POST /api/v1/proveedores con ese RFC
  Entonces responde 409 "CONFLICTO" "RFC_DUPLICADO" con el proveedor existente
```

### CA-14 `[M]` · El contrato publicado coincide con la implementación

```gherkin
Escenario: El borrador describe lo que la API responde
  Cuando una prueba de contrato compara las respuestas reales de la baja con docs/api/openapi.yaml
  Entonces dar_baja_proveedor declara x-tickets TKT-029b, sus respuestas 200, 401, 403, 404, 409 y 422, y el 409 de CONCURRENCIA con Retry-After
  Y el verbo DAR_BAJA está en AccionBitacora del borrador
  Y los tipos del cliente se regeneran y tipos:verificar pasa
```

### CA-R1 `[M]` · Regresión · La migración `0016` encaja en la cadena

```gherkin
Escenario: 0016 sube, baja y respeta los permisos
  Dado la base en la cabeza 0015
  Cuando se aplica alembic upgrade head y luego un downgrade de una versión
  Entonces el verbo DAR_BAJA existe tras subir y, sin asientos que lo usen, deja de existir tras bajar
  Y la cabeza sigue siendo única y lineal
  Y los asientos de bitácora que ya existían no cambian
  Y las suites de esquema, privilegios por omisión y bitácora de TKT-003, TKT-007, TKT-011 y TKT-019 pasan sin modificarse

Escenario: Rechazo · bajar con asientos DAR_BAJA no destruye la bitácora
  Dado al menos un asiento DAR_BAJA
  Cuando se intenta el downgrade
  Entonces se rechaza con un mensaje claro y la bitácora queda intacta
```

### CA-R2 `[M]` · Regresión · Fronteras entre módulos

```gherkin
Escenario: Los contratos de import-linter siguen en verde
  Cuando corre lint-imports
  Entonces los contratos pasan, sin que compras importe proveedores ni proveedores importe tablas, modelos o repositorios de compras
```

### CA-R3 `[M]` · Regresión · TKT-029a sigue entero

```gherkin
Escenario: El catálogo sigue funcionando
  Cuando corre la suite de TKT-029a
  Entonces pasa, salvo las dos afirmaciones (TC-38 y TC-40) de que /baja no existe, que cambian por decisión de este ticket
```

### CA-R4 `[M]` · Regresión · Rutas protegidas

```gherkin
Escenario: La mutación nueva queda bajo las guardas del servidor
  Cuando corren las pruebas de enrutador y de CSRF de TKT-006 y TKT-057
  Entonces la baja exige sesión, CSRF y rol, y ninguna ruta queda sin protección
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Necesita TKT-029a y TKT-019, ambos archivados. TKT-030 y TKT-032 dependen de esta entrega, no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | La técnica de `ALTER TYPE`, la tabla de lectura de `compras` y el orden de bloqueos quedan para el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Compras puede retirar definitivamente a un proveedor sin perder trazabilidad de lo que falta por recibir |
| **E** | Estimable sin investigar antes | Sí, con reserva | La única incertidumbre es `ALTER TYPE … ADD VALUE` (`(sin ejecutar)`): el diseño la comprueba en su primera fila |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Unas 250 a 350 líneas de producción (migración, función de `compras`, caso de uso, ruta y borrador) y unas 800 de pruebas. Toca dos módulos, así que el diseño decide si se parte en dos entregas de ejecución con un solo PR |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio se observa por la API o por el motor; la orden `PARCIAL` se siembra por la vía de pruebas |

Sin fallos: pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` tiene su test con el escenario en el nombre (`test_hdu004_esc12_…`) y los rechazos verifican el contrato de error completo: `tipo`, `codigo`, cifras, `detalle.ordenes` y `acciones`.
- [ ] Pruebas contra PostgreSQL real con el rol de aplicación, nunca SQLite; el esquema se construye con `alembic upgrade head`.
- [ ] Prueba de concurrencia de dos bajas simultáneas y del bloqueo vencido (`CA-11`).
- [ ] La migración `0016` es reversible y lo demuestra una prueba, incluido el rechazo con asientos `DAR_BAJA`.
- [ ] Mutación en la ruta crítica: la comprobación de órdenes pendientes y la de estado se mutan, y algún test se pone rojo.
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float` y `verificar_docs` en verde.
- [ ] Los tipos del cliente se regeneran con `npm run tipos:generar` y `tipos:verificar` pasa.
- [ ] Documentación afectada actualizada en el mismo cambio: borrador OpenAPI, `docs/03` (§14 y conteo de verbos), `docs/05`, `docs/07`, `docs/glosario.md` (baja y desactivación), el delta del ticket.
- [ ] Las auditorías aplicables aprueban.

## Preguntas abiertas y supuestos

Decididas por la persona dueña el 2026-11-15: el puerto queda en TKT-030, el verbo es `DAR_BAJA` con migración `0016`, la baja procede desde `ACTIVO` y `DESACTIVADO` y `BAJA` es terminal, y `compras` publica una función mínima. La persona dueña validó el Must con ese contenido. Costos: el ticket no depende de ningún servicio externo de pago, cuenta ni clave de API.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | **Definición de «pendiente».** `docs/03` §5 dice que `ABIERTA`, `PARCIAL` y `CERRADA` salen de comparar cantidades, pero no da la fórmula. Esta spec usa: orden con `cancelada_en` nulo y al menos un renglón con `cantidad_recibida < cantidad_ordenada`; `PARCIAL` si además algún renglón tiene `cantidad_recibida > 0`, y `ABIERTA` si ninguno. **(asumido)** | Una orden que el negocio considera cerrada seguiría bloqueando la baja, o una pendiente la dejaría pasar | Abierta · la persona dueña confirma al aprobar el diseño |
| 2 | **Orden viva sin renglones.** Si el esquema la permitiera, no tendría saldo y no sería pendiente. **(asumido)** | Una orden sin renglones bloquearía o no la baja contra la intuición | Abierta · el diseño comprueba si el esquema la admite |
| 3 | **Detalle del `409`.** Se listan todas las órdenes pendientes, sin tope, ordenadas por folio, con `{id, folio, estado}` como el ejemplo del borrador | Una respuesta enorme si un proveedor tiene cientos de órdenes pendientes | Resuelta el 2026-11-15 al validar el Must |
| 4 | **La baja no libera el RFC.** Un alta nueva con el mismo RFC sigue respondiendo `RFC_DUPLICADO` | Un proveedor retirado que vuelve a trabajar con la empresa no se puede dar de alta de nuevo | Resuelta el 2026-11-15 al validar el Must · la reactivación es un ticket futuro |
| 5 | **`ALTER TYPE … ADD VALUE` y su uso en la misma transacción.** Un valor nuevo de un `ENUM` de PostgreSQL no se puede usar hasta que la transacción que lo añade confirma; y quitarlo no es una operación directa del motor. **(sin ejecutar)** | La migración no se podría probar en la misma transacción, o la bajada requeriría recrear el tipo | Abierta · la primera fila de la ejecución lo comprueba contra el PostgreSQL de las pruebas, antes de construir nada encima |
| 6 | **Textos del `409`.** El mensaje de `PROVEEDOR_CON_ORDENES_ABIERTAS` y el de `ESTADO_NO_PERMITE_OPERACION` en la baja se redactan en el diseño, sobre el ejemplo del borrador. **(asumido)** | Un texto que a la persona usuaria no le sirva | Abierta · la persona dueña revisa los textos al aprobar el diseño |
| 7 | **La baja y la emisión de una orden de TKT-030.** Sin el puerto `CatalogoProveedores` nadie emite todavía órdenes, así que hoy no hay carrera. Cuando TKT-030 emita, debe leer el proveedor con `FOR SHARE` para que no entre una orden entre la comprobación de la baja y su escritura | Un proveedor en `BAJA` con una orden `ABIERTA` colada | Anotado como `Should` en `docs/05` (TKT-030) · lo cumple TKT-030 |
| 8 | **Una orden `PARCIAL` abandonada bloquea la baja para siempre.** El glosario dice que una orden no se cierra con saldo, se reprograma, y la cancelación con recepciones está prohibida | Compras no podría dar de baja a un proveedor con una orden incompleta que nunca llegará | Aceptado · la salida es desactivar; reprogramar es TKT-054 |
| 9 | **El camino feliz de la baja no tiene escenario en la historia.** HDU-004 esc. 12 solo describe el rechazo y la desactivación. ¿Se añade a la historia una frase que cubra la baja sin órdenes? | El DoD de la historia («ningún escenario es opcional») no nombraría el camino feliz | Abierta · recomendación: añadirlo a la historia en el mismo PR; la persona dueña decide si toca la historia |
| 10 | **Reconciliar `docs/08-wireframes.md`** (dice que no hay baja aparte). Es de TKT-032, que dibuja la pantalla | El boceto sigue desactualizado hasta entonces | Hallazgo registrado desde TKT-029a · se corrige en TKT-032 |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **Carrera baja contra emisión.** Entre la lectura de las órdenes pendientes y el `UPDATE` a `BAJA`, otra transacción podría emitir una orden para ese proveedor, y quedaría una orden `ABIERTA` de un proveedor en `BAJA` | Aceptada. Hoy no hay emisor, así que no se puede probar; la baja toma el proveedor con `FOR UPDATE` (`CA-11`) y TKT-030 debe leerlo con `FOR SHARE`. Se anota como `Should` en `docs/05` (TKT-030) y como supuesto 7 |
| 2 | Alta | **La definición de «pendiente» es un supuesto que decide el rechazo.** Si se equivoca, bloquea de más o deja pasar una baja con material por recibir | Aceptada. `CA-5` fija los siete casos que la definen (cerrada, con excedente, cancelada, de otro proveedor, abierta, parcial) y el supuesto 1 queda `(asumido)` para que la persona dueña lo confirme al aprobar el diseño |
| 3 | Media | **El `409` ofrece una acción que también respondería `409`** si el proveedor ya está `DESACTIVADO` | Aceptada. `CA-4`: sin acción en ese caso |
| 4 | Media | **`ALTER TYPE ADD VALUE` puede no ser probable ni reversible** en la misma transacción | Aceptada. Supuesto 5, `(sin ejecutar)`: la primera fila de la ejecución lo comprueba, y `CA-R1` exige la bajada con su rechazo si hay asientos |
| 5 | Media | **El camino feliz de la baja no tiene escenario en la historia**; los tests llevarían `esc12` por un escenario que solo describe el rechazo | Aceptada como pregunta 9: se recomienda añadir la frase a la historia; no se inventa ninguna regla, porque la baja sin órdenes sale de `docs/05` y del borrador |

## Contexto técnico

Siempre al final.

**Qué existe.**

- `backend/cimenta/proveedores/` ya tiene las capas de TKT-029a. `aplicacion/proveedores.py` trae `desactivar_proveedor` (que es el patrón de la baja: `FOR UPDATE`, `ConflictoEstado`, `asentar` con motivo, `_traducir_concurrencia`), `dominio/proveedor.py` trae `EstadoProveedor` y `admite_desactivacion`, y `infraestructura/repositorio_proveedor.py` trae `leer_proveedor(..., para_cambio=True)`.
- `backend/cimenta/compras/` **no tiene código**: `interfaz.py` solo trae su docstring, y las demás capas solo `__init__.py`. TKT-019 creó únicamente migraciones. No existe ninguna función publicada para consultar órdenes y no hay tablas Core de `compras`.
- `import-linter`: `grafo-compras` admite a `cimenta.proveedores` como importador (`backend/pyproject.toml`), y `grafo-proveedores` solo se admite a sí mismo. La arista es `proveedores → compras`, y `docs/05` lo dice: «las consultas de `proveedores` que necesitan órdenes llaman a la interfaz publicada de `compras`».
- Bitácora: `AccionBitacora` tiene veintidós verbos (`backend/cimenta/auditoria/dominio/asiento.py`), con `DESACTIVAR` y `REACTIVAR` pero sin `BAJA`. El tipo es un `ENUM` de PostgreSQL `accion_bitacora` (excepción histórica de [ADR de catálogos cerrados](../../../docs/adr/20261101-catalogos-cerrados-por-check.md)). `docs/03-modelo-datos.md` §10 dice que un verbo nuevo es una migración del enum y un cambio del borrador en el mismo PR.
- La cabeza de migraciones es `0015` (`v0015_semilla_folios_de_compras.py`, TKT-019). Esta entrega añade `0016`.
- Esquema de órdenes (`0014`): `orden_compra` (con `cancelada_en` y `motivo_cancelacion`; **no guarda su estado**) y `orden_compra_renglon` (`cantidad_ordenada`, `cantidad_recibida` con `DEFAULT 0`, `cantidad_excedente_autorizada`). `proveedor_id` no tiene clave foránea. El rol de aplicación tiene `INSERT`, `UPDATE` y `SELECT` sin `DELETE`.
- El catálogo del contrato de error ya trae `PROVEEDOR_CON_ORDENES_ABIERTAS` y `ESTADO_NO_PERMITE_OPERACION`. `Accion.clave` es un patrón libre, así que `DESACTIVAR_PROVEEDOR` no exige tocar ningún enum.
- Siembra de pruebas: `backend/tests/test_tkt019_restricciones.py` tiene las fábricas locales `fila_requisicion`, `fila_orden`, `fila_orden_renglon`, `orden_valida` y `renglon_de_orden_valido`, que omiten `cantidad_recibida`: hay que pasarla de forma explícita. No son compartidas en un `conftest`.
- Pruebas de TKT-029a que afirman que `/baja` no existe y cambian aquí: `backend/tests/test_tkt029a_api_proveedores.py`, `TC-38` (el conjunto exacto de cinco rutas) y `TC-40` (`".../baja" not in contrato["paths"]`).

**Contrato.** Operación del borrador [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml): `dar_baja_proveedor` (`POST /proveedores/{proveedor_id}/baja`, rol `COMPRAS`, cuerpo `MotivoObligatorio`, respuesta `200` `Proveedor`, `409` `ErrorConflicto`). Hoy declara `x-tickets: [TKT-029]` mientras `docs/07` dice `TKT-029b`: se corrige a `TKT-029b`. El `409` en línea no trae `Retry-After`, que sí trae `components/responses/Conflicto`: se reconcilia para el `409` de `CONCURRENCIA`.

**Discrepancias entre fuentes que este ticket cierra.**

- El puerto `CatalogoProveedores`: `docs/05` lo pone en TKT-029b, y el hub y el delta de TKT-029a lo difieren a TKT-030. Rige TKT-030; se corrige `docs/05` en este PR.
- «Desactivar se admite siempre» (`docs/07`, `docs/03`): el borrador y el código responden `409` si el proveedor no está `ACTIVO`. Se corrige la frase.
- Máquina de estados del proveedor: `docs/03` §14 no la tiene. Se añade: `ACTIVO → DESACTIVADO`, `ACTIVO → BAJA`, `DESACTIVADO → BAJA`, con `BAJA` terminal.
- Wireframe: `docs/08-wireframes.md` dice que no hay baja aparte. Se corrige en TKT-032.

**Módulos y capas.** `proveedores` (dominio: `admite_baja`; aplicación: `dar_baja_proveedor`; api: la ruta) y `compras` (aplicación o infraestructura, e `interfaz.py`: la función de lectura), más `auditoria` por su interfaz. Con migración (`0016`). Sin frontend.

**Dependencias cruzadas** (búsqueda de TKT-029b y de HDU-004 sobre `docs/05-tickets-trabajo.md`, los `_index.md` de `sdd/tickets/` y `tools/historias_activas.txt`):

- `docs/05-tickets-trabajo.md`: TKT-029b aparece solo en la tabla de partición de TKT-029. TKT-030 (emisión) usa el puerto y depende de «TKT-029»; TKT-031 (cancelación) siembra `cantidad_recibida` por la misma vía de pruebas; TKT-032 (catálogo y emisión) pinta el `409` de la baja en pantalla y reconcilia el boceto.
- `sdd/tickets/`: `tkt-029a` (`_index.md` y `delta.md`) registra la deuda que este ticket cierra; `tkt-019` (`_index.md`) habilita HDU-004 sin probar escenarios.
- `tools/historias_activas.txt`: vacía. **HDU-004 no se activa en esta entrega**: sus escenarios 1 y 4 a 11 son de TKT-030 a TKT-032.
