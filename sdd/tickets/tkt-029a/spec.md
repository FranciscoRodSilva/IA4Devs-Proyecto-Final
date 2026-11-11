# Spec · TKT-029a · Catálogo de proveedores, sin baja

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

Sin catálogo de proveedores no hay a quién emitir la orden de compra (`F2.5`, PRD §7), y hoy el módulo `proveedores` es un esqueleto: solo `__init__.py` e `interfaz.py` vacíos, sin tabla, sin rutas y sin montaje. TKT-029 original pide el esquema, el CRUD, la desactivación, la baja protegida por las órdenes pendientes y el puerto `CatalogoProveedores` que `compras` declara. Dos de esas piezas necesitan algo que todavía no existe: la **baja protegida** consulta órdenes `ABIERTA` o `PARCIAL` por la interfaz de `compras` (TKT-019 y TKT-030), y el **puerto** no lo consume nadie hasta que TKT-030 emita órdenes.

Por el plazo de la tercera entrega, la persona dueña validó el 2026-11-10 partir el ticket como se hizo con TKT-012: **TKT-029a** (esta spec: esquema, alta, listado, consulta, cambio de datos y desactivación, solo backend) y **TKT-029b** (la baja protegida, su prueba con una orden `PARCIAL` sembrada y el puerto, después de TKT-019 y TKT-030). La pantalla de catálogo no es de este ticket: la construye TKT-032.

## Historia de usuario

**Como** responsable de Compras
**quiero** dar de alta a mis proveedores, consultarlos, corregir sus datos y retirar del selector a los que ya no uso
**para** tener a quién emitir las órdenes de compra, sin perder el historial de los proveedores que se retiran.

Historia de referencia: [HDU-004](../../../docs/04-historias-usuario.md#hdu-004--proveedores-y-emisión-de-órdenes-de-compra), escenarios 2, 3 y 12 (este último solo en su mitad de desactivación).

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | Migración `0012`: tabla `proveedor` con `UNIQUE (rfc)` (invariante 28), `estado` `ACTIVO`/`DESACTIVADO`/`BAJA`, `tope_consignacion`, `dia_corte` y `dia_pago`, y los permisos del rol de aplicación |
| **Must** | `POST /api/v1/proveedores` (`crear_proveedor`): alta `ACTIVO` con jueves y sábado por omisión (`RN-17`); RFC duplicado responde `409` `RFC_DUPLICADO` con el proveedor existente |
| **Must** | `GET /api/v1/proveedores` (`listar_proveedores`: por omisión solo `ACTIVO`, que es el selector; filtro `estado`, búsqueda `q`, paginación) y `GET /api/v1/proveedores/{proveedor_id}` (`obtener_proveedor`) |
| **Must** | `PATCH /api/v1/proveedores/{proveedor_id}` (`actualizar_proveedor`): nombre, tope de consignación y días de corte y pago |
| **Must** | `POST /api/v1/proveedores/{proveedor_id}/desactivacion` (`desactivar_proveedor`) con motivo: pasa a `DESACTIVADO`, deja el selector y conserva todo su historial |
| **Must** | Altas, cambios y desactivaciones asentadas en la bitácora en la misma transacción; el `403` se asienta como `DENEGAR`. Una prueba comprueba que no existe ninguna ruta `DELETE` sobre proveedores |
| **Should** | — |
| **Could** | — |
| **Won't** | `dar_baja_proveedor` (`POST /baja`) y el rechazo `PROVEEDOR_CON_ORDENES_ABIERTAS`: pasan a TKT-029b. El puerto `CatalogoProveedores`: se declara con su primer consumidor (TKT-030). La pantalla de catálogo y el escenario 1 de HDU-004: TKT-032. La reactivación de un proveedor `DESACTIVADO` |

## Non-goals

- **No hay baja definitiva.** Ningún proveedor llega a `BAJA` en esta entrega: el estado existe en la restricción de la tabla porque el modelo de datos y el borrador lo definen, pero ninguna operación lo escribe.
- No declara ni implementa `CatalogoProveedores` y no toca el módulo `compras`.
- No registra facturas, anticipos ni consignación (`RN-15`, `RN-16`, v1.1): solo captura `tope_consignacion`.
- No valida el RFC contra el SAT; solo comprueba su forma.
- No tiene pantalla. El escenario 1 de HDU-004 (el `+` abre el alta con el foco en el nombre) es de TKT-032.
- No hay reactivación: ninguna ruta devuelve un proveedor `DESACTIVADO` a `ACTIVO`.
- No permite corregir el RFC ni el estado por `PATCH`: el borrador no los incluye en `ProveedorCambios`.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-17` | El corte de facturación de proveedores es el jueves y el pago el sábado. Por omisión `dia_corte` es 4 y `dia_pago` es 6 (ISO 8601, 1 = lunes), por proveedor | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md). El «por omisión» lo fijan la historia (esc. 2) y el borrador |
| `RN-15`, `RN-16` | Tope de consignación y anticipos. **Fuera de esta entrega** (v1.1): se cita porque `tope_consignacion` se captura ya | PRD §8 |

Invariantes del modelo de datos que toca: **28** (`UNIQUE (rfc)`: un proveedor no se da de alta dos veces), **8** (importes no negativos: `tope_consignacion`) y **10** (la bitácora no se modifica). Regla 8 de `CLAUDE.md`: la bitácora se escribe en la misma transacción que el cambio.

## Invariantes que deben sobrevivir al cambio

El ticket **añade una migración encima de la cabeza `0011`** y un enrutador nuevo; no modifica comportamiento existente, pero toca dos garantías generales que otras suites vigilan.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Cadena de migraciones, reversibilidad y privilegios por omisión de los tres roles | La migración `0012` cuelga de `0011`, sube y baja limpia y no abre permisos de más | `CA-R1` |
| Rutas protegidas y CSRF (TKT-006, TKT-057) | Las rutas nuevas de mutación exigen sesión, CSRF y rol | `CA-R2` |

## Criterios de aceptación

Gherkin, en español.

### CA-1 `[M]` · Alta con los días por omisión · `RN-17` · `HDU-004 esc. 2`

```gherkin
Escenario: Compras da de alta un proveedor sin indicar días
  Dado un usuario autenticado con rol COMPRAS
  Y que no existe ningún proveedor con el RFC "XAXX010101000"
  Cuando envía POST /api/v1/proveedores con nombre "CoPanel" y rfc "XAXX010101000"
  Entonces responde 201 con la cabecera Location del proveedor
  Y el proveedor queda en estado "ACTIVO"
  Y dia_corte vale 4 (jueves) y dia_pago vale 6 (sábado)
  Y tope_consignacion es nulo
  Y el proveedor guarda cuándo se creó
  Y aparece en GET /api/v1/proveedores sin indicar estado
  Y la bitácora tiene un asiento CREAR de ese proveedor escrito en la misma transacción
```

Variantes, cada una con su test: con `tope_consignacion` `"300000.0000"` se guarda y se devuelve como cadena con cuatro decimales; con `dia_corte` 2 y `dia_pago` 5 se guardan esos valores en lugar de los de omisión; con `tope_consignacion` `null` explícito se guarda nulo.

### CA-2 `[M]` · Rechazo · RFC duplicado · `HDU-004 esc. 3`

```gherkin
Escenario: El RFC ya está registrado
  Dado que ya existe el proveedor "CoPanel" con el RFC "XAXX010101000"
  Cuando Compras envía POST /api/v1/proveedores con otro nombre y el mismo RFC
  Entonces responde 409 con tipo "CONFLICTO" y codigo "RFC_DUPLICADO"
  Y el detalle identifica al proveedor existente (su identificador y "CoPanel · XAXX010101000")
  Y no se crea ninguna fila en proveedor
  Y no se asienta ningún CREAR nuevo en la bitácora
```

### CA-3 `[M]` · Rechazo · Dos altas simultáneas con el mismo RFC · `HDU-004 esc. 3`

```gherkin
Escenario: La restricción única decide aunque la comprobación previa se salte
  Dado que no existe ningún proveedor con el RFC "XAXX010101000"
  Cuando dos solicitudes POST /api/v1/proveedores con ese RFC llegan a la vez
  Entonces exactamente una responde 201
  Y la otra responde 409 "CONFLICTO" "RFC_DUPLICADO" con el proveedor de la primera
  Y queda un solo proveedor con ese RFC y un solo asiento CREAR
  Y ninguna solicitud responde 500
```

### CA-4 `[M]` · Rechazo · Error de forma, por campo · `HDU-004 esc. 2`

```gherkin
Esquema del escenario: El cuerpo del alta no cumple la forma del contrato
  Dado un cuerpo de alta válido salvo <defecto>
  Cuando Compras envía POST /api/v1/proveedores
  Entonces responde 422 con tipo "VALIDACION"
  Y el detalle señala el campo <campo>
  Y no se crea ninguna fila en proveedor ni en la bitácora

  Ejemplos:
    | defecto                                                        | campo             |
    | nombre ausente, vacío o solo espacios                          | nombre            |
    | nombre con carácter NUL                                        | nombre            |
    | nombre por encima del máximo permitido                         | nombre            |
    | rfc ausente                                                    | rfc               |
    | rfc que no cumple la forma del RFC (longitud, letras, dígitos) | rfc               |
    | rfc con carácter NUL, salto de línea final o dígitos no ASCII  | rfc               |
    | dia_corte o dia_pago menor que 1, mayor que 7 o no entero      | el día afectado   |
    | tope_consignacion negativo                                     | tope_consignacion |
    | tope_consignacion con más de cuatro decimales o no cadena      | tope_consignacion |
```

### CA-5 `[M]` · Rechazo · Sin permiso o sin sesión

```gherkin
Escenario: Un rol que no gestiona proveedores lo intenta
  Dado un usuario autenticado con rol DIRECCION_GENERAL, DIRECTOR_PROYECTOS, RESIDENTE, ALMACEN o ADMINISTRACION
  Cuando envía POST /api/v1/proveedores con un cuerpo válido
  Entonces responde 403 con tipo "PERMISO"
  Y el intento queda asentado como DENEGAR en la bitácora
  Y no se crea ninguna fila en proveedor

Escenario: Sin sesión o sin CSRF
  Cuando alguien sin sesión envía POST /api/v1/proveedores
  Entonces responde 401
  Cuando un usuario COMPRAS con sesión lo envía sin la cabecera CSRF válida
  Entonces responde 403 sin crear nada
```

El mismo criterio vale para `PATCH` y para la desactivación: solo `COMPRAS` muta, y cada rechazo no cambia el proveedor.

### CA-6 `[M]` · Listado de proveedores · `HDU-004 esc. 2`

```gherkin
Escenario: El listado por omisión es el selector
  Dado proveedores ACTIVO y DESACTIVADO
  Cuando un usuario autenticado de cualquiera de los seis roles envía GET /api/v1/proveedores
  Entonces responde 200 solo con los ACTIVO, con su paginación
  Y el orden es determinista: dos llamadas seguidas devuelven el mismo orden

Escenario: Filtro por estado y búsqueda
  Cuando envía GET /api/v1/proveedores?estado=DESACTIVADO
  Entonces devuelve solo los DESACTIVADO
  Cuando envía q con parte del nombre o del RFC
  Entonces devuelve los proveedores que coinciden, sin distinguir mayúsculas
  Y una q con los caracteres "%" o "_" se busca como texto literal, no como comodín

Escenario: Rechazo · parámetros inválidos
  Cuando envía un estado fuera del enumerado, una pagina menor que 1 o un tamano_pagina fuera de rango
  Entonces responde 422 con tipo "VALIDACION" y el parámetro señalado, sin 500

Escenario: Página inalcanzable
  Cuando envía una pagina cuyo desplazamiento supera el total, aunque sea enorme
  Entonces responde 200 con la página vacía y el total, sin 500
```

### CA-7 `[M]` · Consulta de un proveedor

```gherkin
Escenario: Se consulta un proveedor
  Dado que existe el proveedor "CoPanel"
  Cuando un usuario autenticado envía GET /api/v1/proveedores/{proveedor_id}
  Entonces responde 200 con el proveedor completo, también si está DESACTIVADO

Escenario: Rechazo · no existe o mal formado
  Cuando envía el identificador de un proveedor inexistente
  Entonces responde 404
  Cuando envía un identificador que no es UUID
  Entonces responde 422 con tipo "VALIDACION"
```

### CA-8 `[M]` · Cambio de datos del proveedor · `RN-17`

```gherkin
Escenario: Compras corrige los datos
  Dado el proveedor "CoPanel" ACTIVO con dia_corte 4
  Cuando Compras envía PATCH /api/v1/proveedores/{id} con dia_corte 2 y un tope "250000.0000"
  Entonces responde 200 con el proveedor actualizado
  Y el rfc y el estado no cambian
  Y la bitácora tiene un asiento ACTUALIZAR con los valores anteriores y los nuevos
  Y un proveedor DESACTIVADO también admite el cambio de sus datos

Escenario: Rechazo · cuerpo vacío o inválido
  Cuando envía un cuerpo sin ninguna propiedad
  Entonces responde 422 con tipo "VALIDACION"
  Y cuando algún valor incumple la forma (día fuera de 1 a 7, tope negativo, nombre vacío)
  Entonces responde 422 señalando el campo y el proveedor no cambia

Escenario: Rechazo · inexistente
  Cuando el proveedor no existe
  Entonces responde 404 y no se asienta nada
```

### CA-9 `[M]` · Desactivación · `HDU-004 esc. 12` (mitad de desactivación)

```gherkin
Escenario: Compras desactiva a un proveedor
  Dado el proveedor "CoPanel" ACTIVO
  Cuando Compras envía POST /api/v1/proveedores/{id}/desactivacion con el motivo "Ya no surte tablaroca"
  Entonces responde 200 con el proveedor en estado "DESACTIVADO"
  Y deja de aparecer en GET /api/v1/proveedores sin indicar estado
  Y sigue apareciendo con estado=DESACTIVADO y en GET /api/v1/proveedores/{id}
  Y su fila, su RFC y todos sus datos se conservan sin cambio
  Y la bitácora tiene un asiento DESACTIVAR con el motivo, escrito en la misma transacción

Escenario: Rechazo · sin motivo
  Cuando el motivo falta, está en blanco, tiene más de 2000 caracteres o contiene NUL
  Entonces responde 422 con tipo "VALIDACION" señalando el motivo
  Y el proveedor sigue ACTIVO y no se asienta nada

Escenario: Rechazo · ya no está activo
  Dado un proveedor ya DESACTIVADO
  Cuando Compras lo desactiva otra vez
  Entonces responde 409 con tipo "CONFLICTO" y codigo "ESTADO_NO_PERMITE_OPERACION"
  Y el detalle indica el estado actual del proveedor
  Y no se asienta nada

Escenario: Rechazo · inexistente
  Cuando el proveedor no existe
  Entonces responde 404
```

### CA-10 `[M]` · Nunca se borra un proveedor

```gherkin
Escenario: No existe ninguna ruta de borrado
  Cuando una prueba recorre el enrutador de la aplicación
  Entonces no existe ninguna operación DELETE sobre /proveedores ni sobre /proveedores/{proveedor_id}

Escenario: Rechazo · el rol de aplicación no puede borrar filas
  Dado una conexión con el rol de aplicación
  Cuando intenta un DELETE sobre la tabla proveedor
  Entonces el motor lo rechaza por falta de privilegio
```

### CA-11 `[M]` · Restricciones del motor · invariantes 8 y 28

```gherkin
Escenario: El motor rechaza lo que el API dejara pasar
  Dado una escritura directa a la tabla proveedor con el rol de aplicación
  Cuando el RFC está duplicado, o el estado está fuera de los tres valores, o el tope es negativo, o un día está fuera de 1 a 7
  Entonces el motor la rechaza con la restricción nombrada correspondiente (uq_proveedor_rfc y los tres CHECK)
```

### CA-R1 `[M]` · Regresión · La migración encaja en la cadena

```gherkin
Escenario: La migración 0012 sube, baja y respeta los permisos
  Dado la base en la cabeza 0011
  Cuando se aplica alembic upgrade head y luego un downgrade de una versión
  Entonces la tabla proveedor se crea y se elimina sin dejar objetos huérfanos
  Y la cabeza sigue siendo única y lineal
  Y las suites de esquema, privilegios por omisión y permisos de TKT-003, TKT-007 y TKT-011 pasan sin modificarse
```

### CA-R2 `[M]` · Regresión · Rutas protegidas

```gherkin
Escenario: Las rutas nuevas quedan bajo las guardas del servidor
  Cuando corren las pruebas de enrutador y de CSRF de TKT-006 y TKT-057
  Entonces las tres mutaciones de proveedor exigen sesión, CSRF y rol
  Y ninguna ruta nueva queda sin protección
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Solo necesita TKT-003, 005, 006 y 007, archivados. TKT-030 y TKT-032 dependen de esta entrega, no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | El contexto técnico va al final |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Compras puede tener su catálogo de proveedores y retirar a los que ya no usa |
| **E** | Estimable sin investigar antes | Sí | Patrón ya probado en TKT-012a y TKT-017 |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Unas 650 a 750 líneas de producción de backend. Si el diseño supera ~400, se parte en entregas de ejecución (migración y repositorio; casos de uso y API) con un solo PR |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es observable por la API o por el motor |

Sin fallos: pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` tiene su test con el escenario en el nombre (`test_hdu004_esc02_…`, `esc03`, `esc12`) y los rechazos verifican el contrato de error completo.
- [ ] Pruebas contra PostgreSQL real con el rol de aplicación, nunca SQLite; el esquema se construye con `alembic upgrade head`.
- [ ] Prueba de concurrencia del alta con el mismo RFC (`CA-3`).
- [ ] La migración es reversible y lo demuestra una prueba.
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float` y `verificar_docs` en verde.
- [ ] Los tipos del cliente se regeneran con `npm run tipos:generar` y `tipos:verificar` pasa.
- [ ] Documentación afectada actualizada en el mismo cambio: la partición en `docs/05-tickets-trabajo.md`, el modelo de datos si cambia algo, el delta del ticket.
- [ ] Las auditorías aplicables aprueban.

## Preguntas abiertas y supuestos

Decididas por la persona dueña el 2026-11-10: partir el ticket sin baja, sin pantalla y sin el puerto de `compras`. Costos: el ticket no depende de ningún servicio externo de pago, cuenta ni clave de API.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | **Normalización del RFC.** Recomendación: recortar espacios al inicio y al final y pasar a mayúsculas **antes** de validar la forma, como se decidió para el código de obra (TKT-012a, `D-1`). Así `xaxx010101000 ` choca con `XAXX010101000`. Sin normalizar, el patrón del borrador rechaza las minúsculas con `422` | Duplicados que no se ven como tales, o rechazos molestos por una minúscula | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 2 | **Forma del `409` `RFC_DUPLICADO`.** El borrador solo dice «con el proveedor existente». Recomendación: `detalle` con `proveedor_existente_id` y `proveedor_existente` («nombre · RFC»), **sin acción** (no existe una acción `VER_PROVEEDOR` en el catálogo y esta entrega no tiene pantalla) | Una acción inventada que ningún cliente sabe pintar | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 3 | **`PATCH` sobre un proveedor `DESACTIVADO`.** Recomendación: se admite (son datos de catálogo y no abre órdenes nuevas). El `409` que el borrador declara para `PATCH` no tiene causa descrita y esta entrega no lo emite | Un proveedor retirado quedaría con datos que no se pueden corregir | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 4 | **Quitar el privilegio `DELETE` al rol de aplicación sobre `proveedor`.** Recomendación: sí, con su prueba (`CA-10`): «nunca hay borrado físico» se apoya así en el motor y no solo en la ausencia de una ruta. La migración de `0006` concede `DELETE` por omisión | Un defecto futuro podría borrar un proveedor con historial | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 5 | **Longitud máxima de `nombre`.** El borrador no la fija. Recomendación: 200 caracteres, con `maxLength` en el borrador, como `D-5` de TKT-012a | Texto libre sin tope | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 6 | **Campos extra en el cuerpo** (`estado`, `rfc` en el `PATCH`, `id`…). Recomendación: se ignoran, como se confirmó en TKT-017 (`E2`) y en TKT-012a (`D-2`) | Con rechazo `422`, un cliente con campos de más dejaría de funcionar | Resuelta el 2026-11-10 con la recomendación (`design.md`) |
| 7 | **El wireframe contradice al resto.** `docs/08-wireframes.md` dice que no hay baja aparte y que la única operación es la desactivación como baja lógica con `activo = false`; el ticket, el borrador, la especificación de la API y el modelo de datos definen dos operaciones y un `estado` de tres valores. Esta spec sigue las cuatro fuentes que coinciden. El wireframe se reconcilia en TKT-032, que dibuja la pantalla | El texto del wireframe seguiría desactualizado | Hallazgo registrado · se corrige en TKT-032 |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **`CA-10` depende de una decisión abierta.** El segundo escenario (el rol de aplicación no puede borrar) solo existe si la pregunta 4 se aprueba; sin ella, «nunca se borra» descansa únicamente en que no haya una ruta `DELETE`, que un defecto futuro puede añadir | Aceptada. La pregunta 4 se resuelve en el diseño; si se rechaza, se borra el segundo escenario y la spec lo dice expresamente |
| 2 | Alta | **El esc. 12 de HDU-004 queda a medias**, y el DoD de la historia dice que ninguno de sus escenarios es opcional: dar por cerrado TKT-029a no cierra el 12 | Aceptada. Está declarado como «mitad de desactivación» en la historia de referencia, en el alcance y en `HDU-004` sin activar; el cierre lo asume TKT-029b |
| 3 | Media | El borrador seguirá listando `dar_baja_proveedor` con `x-tickets: [TKT-029]` mientras la API publicada no la tenga: una divergencia entre contrato e implementación | Aceptada y sin cambio de contrato. Ninguna prueba compara hoy la cobertura de operaciones de `proveedores` y TKT-029b la cierra; el borrador no se toca |
| 4 | Media | Un `q` con `%` o `_` actuaría como comodín en una búsqueda `ILIKE` y devolvería más proveedores de los esperados | Aceptada. Incorporada a `CA-6` con su rechazo: se busca como texto literal |

## Contexto técnico

Siempre al final.

**Qué existe.**

- `backend/cimenta/proveedores/` es un esqueleto: `__init__.py` e `interfaz.py` vacíos. No hay tablas, rutas ni montaje. `backend/cimenta/compras/` también está vacío.
- `import-linter`: `grafo-compras` admite a `cimenta.proveedores` como importador y `grafo-proveedores` solo admite a sí mismo, así que nadie importa `proveedores`.
- La cabeza de migraciones es `0011` (`v0011_presupuesto_campos_sin_fuente.py`). TKT-012a no migra, así que `0012` es de esta entrega; TKT-019 tomaría la siguiente.
- Patrones reutilizables de TKT-017 y TKT-012a: montaje por enrutador propio, `exigir_rol` y `verificar_origen`, transacción única en el caso de uso con `asentar`, traducción de `23505`, paginación con página vacía (`D20`), contrato de error con `Accion`. Como los módulos no se importan entre sí, la paginación se replica dentro de `proveedores`.
- El catálogo del contrato de error ya trae `RFC_DUPLICADO` y `PROVEEDOR_CON_ORDENES_ABIERTAS` (este último, de TKT-029b). La bitácora ya tiene `CREAR`, `ACTUALIZAR` y `DESACTIVAR`.
- Frontend: la sección `PROVEEDORES` (`/compras/proveedores`) y su marcador ya existen en `secciones.ts` y `modulos/proveedores/rutas.tsx`. Esta entrega no los toca.

**Contrato.** Operaciones del borrador [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml) con `x-tickets: [TKT-029]`: `crear_proveedor`, `listar_proveedores`, `obtener_proveedor`, `actualizar_proveedor` y `desactivar_proveedor`. `dar_baja_proveedor` queda para TKT-029b. Esquemas: `ProveedorNuevo`, `ProveedorCambios`, `Proveedor`, `ListaProveedores`, `EstadoProveedor`, `DiaSemana`. Roles: solo `COMPRAS` muta; los seis leen.

**Tabla.** `proveedor` según [modelo de datos §9](../../../docs/03-modelo-datos.md#9-proveedores--v11): `id`, `nombre`, `rfc`, `estado`, `tope_consignacion NUMERIC(18,4)` anulable, `dia_corte` y `dia_pago` enteros con valores por omisión 4 y 6 y `CHECK` de 1 a 7, y las columnas de creación. Restricciones: `uq_proveedor_rfc`, `ck_proveedor_estado` y `ck_proveedor_tope_consignacion_no_negativo`.

**Módulos y capas.** `proveedores` (dominio, aplicación, api, infraestructura) y, por su interfaz, `auditoria` e `identidad`. Frontend: ninguna capa. Con migración.

**Dependencias cruzadas** (búsqueda de TKT-029 y de HDU-004 sobre `docs/05-tickets-trabajo.md`, los `_index.md` de `sdd/tickets/` y `tools/historias_activas.txt`):

- `docs/05-tickets-trabajo.md`: TKT-030 (emisión de la orden) y TKT-032 (consulta proveedor por obra e interfaz del catálogo) dependen de TKT-029; los dos son posteriores.
- `sdd/tickets/`: ningún hub de ticket citaba a TKT-029 antes de esta spec.
- `tools/historias_activas.txt`: vacía. HDU-004 **no** se activa en esta entrega: sus escenarios 1 y 4 a 11 son de TKT-030 a TKT-032 y el 12 queda a medias hasta TKT-029b.
