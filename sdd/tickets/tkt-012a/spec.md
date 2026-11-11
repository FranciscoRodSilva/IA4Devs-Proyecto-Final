# Spec · TKT-012a · Alta y consulta de obras

> [← index](_index.md) | Siguiente: design (se enlaza en `/sdd-disenar`)

## Contexto y problema

La línea base se importa, se confirma y se congela contra una **obra**, y todo gasto del sistema lleva `obra_id` (regla 6 de `CLAUDE.md`). Hoy el módulo `presupuesto` tiene la tabla `obra` desde la migración `0006` y la empresa única sembrada por la `0008`, y el congelado de TKT-017 ya escribe la transición `PLANEACION` → `ACTIVA`. Pero **no existe ninguna ruta para dar de alta una obra, listarla o consultarla**: la única ruta bajo `/obras` es `/obras/{obra_id}/lineas-base`. Las pruebas de TKT-017 siembran la obra por SQL. Sin esta entrega, un usuario no puede llegar a la pantalla de la línea base.

TKT-012 original agrupa diez operaciones del borrador OpenAPI y cinco huecos de reglas sin definir (qué cuenta como «movimientos» en `OBRA_CON_HISTORIAL`, la máquina de estados de la obra, la acción de bitácora del borrado, entre otros). Por el plazo de la entrega del 12 de noviembre, la persona dueña validó el 2026-11-10 partir el ticket como se hizo con TKT-011 y TKT-013: **TKT-012a** (esta spec: alta, listado y consulta, con su pantalla) y **TKT-012b** (actualizar, eliminar, suspender, reactivar y cerrar). Las dos mitades son tickets hermanos con un PR cada uno.

## Historia de usuario

**Como** Director de Proyectos (o Dirección General)
**quiero** dar de alta una obra con sus parámetros de negocio y ver las obras registradas
**para** tener la obra contra la que importaré y congelaré su línea base, con sus porcentajes de retención y de fondo de garantía y su tratamiento del IVA guardados **en la obra**.

Historia de referencia: [HDU-001](../../../docs/04-historias-usuario.md#hdu-001--alta-de-obra-e-importación-de-la-línea-base), escenarios 1, 2 y 3.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | `POST /api/v1/obras` (`crear_obra`): alta en `PLANEACION` con código, nombre, domicilio, tipo de contrato, retención de destajo, fondo de garantía, IVA acreditable y umbral de alerta opcional. La empresa es la única activa. El alta se asienta en la bitácora en la misma transacción |
| **Must** | Rechazos de `crear_obra`: `409` `CONFLICTO` `CODIGO_OBRA_DUPLICADO` con la obra existente, `422` por campo (incluido el rango de los dos porcentajes y del umbral), `403` y `401` |
| **Must** | `GET /api/v1/obras` (`listar_obras`, con filtro de estado y paginación) y `GET /api/v1/obras/{obra_id}` (`obtener_obra`), esta última porque la acción `VER_OBRA` del `409` apunta a ella |
| **Must** | Pantalla de obras con el botón `+`, el formulario de alta construido sobre el formulario de catálogo de TKT-008c (extendido con casilla y desplegable) y la lista de obras con sus cuatro estados |
| **Must** | Una prueba de extremo a extremo del flujo: inicio de sesión → alta de obra → la obra aparece en la lista → segundo alta con el mismo código muestra el conflicto |
| **Should** | — |
| **Could** | — |
| **Won't** | `actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra`, `cerrar_obra` y el escenario 20 de HDU-001: pasan a TKT-012b. `listar_tipos_partida` y `listar_insumos`: los consume la captura de requisición (HDU-002) y la previsualización de la importación (HDU-001 esc. 10), y se hacen con su primer consumidor |

## Non-goals

- **No construye la máquina de estados de la obra.** Esta entrega solo escribe `PLANEACION` al crear. La transición `PLANEACION` → `ACTIVA` sigue escrita por el congelado de TKT-017 (`PA-T17.8`) y no se toca.
- **No modifica ni elimina obras.** Una corrección de un dato de la obra espera a TKT-012b.
- No decide qué es «historial» de una obra ni qué bloquea una obra suspendida o cerrada: son los huecos de TKT-012b.
- No gestiona permisos por obra: el borrador da lectura a los seis roles y escritura a Director de Proyectos y Dirección General, sin restringir por obra.
- No importa presupuesto ni crea línea base (TKT-018). La cláusula final del esc. 2 de HDU-001 —«la obra aparece disponible para importar su presupuesto»— se cumple aquí solo en el sentido de que la obra en `PLANEACION` existe, se lista y se consulta; la pantalla de importación es de TKT-018.
- No construye el selector de obra del armazón (wireframe §2): es otra pantalla, que consume `listar_obras` pero no es objeto de esta spec.
- No introduce constantes de retención ni de fondo de garantía en el servidor (`PA-02`).

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-25` | El tratamiento del IVA se configura **por obra**, no es una constante del sistema. El indicador `iva_acreditable` se guarda en la obra; `false` significa que el IVA es costo | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `PA-02` | La retención de destajo (15 % de referencia) y el fondo de garantía (5 % de referencia) son **dos conceptos distintos**, configurables por obra y sin constante en el código | PRD, preguntas al cliente |
| `PA-05` | El IVA es configuración por obra | PRD, preguntas al cliente |
| `PA-18` | El umbral de alerta es por obra y opcional; sin él, toda desviación positiva es `ROJO` | PRD, preguntas al cliente |
| `RN-01` | La línea base se congela al firmar y nada posterior la modifica. **No es objeto de esta entrega**; se cita porque la obra recién creada **no** debe traer línea base vigente | PRD §8 |

Regla 6 de `CLAUDE.md`: toda obra es la unidad de imputación; sin obra no hay gasto. Regla 8: la bitácora se escribe en la misma transacción que el cambio.

## Invariantes que deben sobrevivir al cambio

El ticket **no modifica comportamiento existente**, pero amplía el mapeo de la tabla `obra` (hoy el modelo Core solo declara `id`, `codigo`, `nombre`, `estado`, `actualizado_en` y `actualizado_por_id`) y extiende un componente compartido. Los dos puntos de contacto con lo que ya funciona generan criterio de regresión.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Transición `PLANEACION` → `ACTIVA` del congelado (`PA-T17.8`) | El congelado de TKT-017 sigue activando la obra, ahora que la tabla está mapeada con todas sus columnas | `CA-R1` |
| Restricciones de la tabla `obra` de la migración `0006` (`uq_obra_codigo`, los dos `CHECK` de rango de porcentaje, `ck_obra_umbral_alerta_pct_no_negativo`) | El motor sigue siendo la última barrera aunque el API valide antes | `CA-R2` |
| Formulario de catálogo de TKT-008c | La extensión con casilla y desplegable no cambia el comportamiento ya probado de los campos de texto, correo y fecha | `CA-R3` |

## Criterios de aceptación

Gherkin, en español.

### CA-1 `[M]` · Alta de obra con sus parámetros · `RN-25`, `PA-02` · `HDU-001 esc. 2`

```gherkin
Escenario: Un Director de Proyectos da de alta una obra
  Dado que existe la única empresa activa
  Y que no existe ninguna obra con el código "AP-058-25"
  Cuando un Director de Proyectos autenticado envía POST /api/v1/obras con
    código "AP-058-25", nombre "Union Square F2", un domicilio,
    tipo_contrato "PRECIO_ALZADO_MAXIMO_GARANTIZADO",
    retencion_destajo_pct "0.150000", fondo_garantia_pct "0.050000",
    iva_acreditable false y umbral_alerta_pct "0.150000"
  Entonces responde 201 con la cabecera Location de la obra
  Y la obra queda en estado "PLANEACION" con linea_base_vigente_id nulo
  Y los dos porcentajes quedan guardados en la obra como dos valores distintos y la respuesta los devuelve con seis decimales ("0.150000" y "0.050000")
  Y iva_acreditable queda guardado en la obra como false
  Y la obra pertenece a la única empresa activa
  Y la obra guarda quién la creó y cuándo
  Y la bitácora tiene un asiento CREAR de esa obra escrito en la misma transacción
```

Variantes del mismo criterio, cada una con su test: `umbral_alerta_pct` ausente o `null` guarda `null`; `iva_acreditable` `true` se guarda como `true`; Dirección General puede dar de alta igual que Director de Proyectos.

### CA-2 `[M]` · Rechazo · Código de obra duplicado · `HDU-001 esc. 3`

```gherkin
Escenario: El código ya lo usa otra obra
  Dado que ya existe la obra "AP-058-25 · Union Square F2"
  Cuando un Director de Proyectos envía POST /api/v1/obras con el código "AP-058-25"
  Entonces responde 409 con tipo "CONFLICTO" y codigo "CODIGO_OBRA_DUPLICADO"
  Y el detalle trae obra_existente_id y obra_existente "AP-058-25 · Union Square F2"
  Y las acciones incluyen VER_OBRA con método GET y la ruta de esa obra
  Y no se crea ninguna fila en obra
  Y no se asienta ninguna fila de CREAR en la bitácora
```

### CA-3 `[M]` · Rechazo · Dos altas simultáneas con el mismo código · `HDU-001 esc. 3`

```gherkin
Escenario: Dos altas concurrentes con el mismo código
  Dado que no existe ninguna obra con el código "AP-070-26"
  Cuando dos solicitudes POST /api/v1/obras con ese código llegan a la vez
  Entonces exactamente una responde 201
  Y la otra responde 409 "CONFLICTO" "CODIGO_OBRA_DUPLICADO" con la obra de la primera
  Y queda una sola obra con ese código y un solo asiento CREAR
  Y ninguna solicitud responde 500
```

La unicidad la garantiza `uq_obra_codigo`: la comprobación previa del caso de uso puede saltarse y el motor sigue rechazando.

### CA-4 `[M]` · Rechazo · Error de forma, por campo · `HDU-001 esc. 2`

```gherkin
Esquema del escenario: El cuerpo no cumple la forma del contrato
  Dado un cuerpo de alta válido salvo <defecto>
  Cuando un Director de Proyectos envía POST /api/v1/obras
  Entonces responde 422 con tipo "VALIDACION"
  Y el detalle señala el campo <campo>
  Y no se crea ninguna fila en obra ni en la bitácora

  Ejemplos:
    | defecto                                      | campo                 |
    | código ausente o vacío                       | codigo                |
    | código de más de 40 caracteres               | codigo                |
    | nombre ausente o vacío                       | nombre                |
    | domicilio ausente o vacío                    | domicilio             |
    | tipo_contrato fuera del enumerado            | tipo_contrato         |
    | retención de destajo ausente                 | retencion_destajo_pct |
    | fondo de garantía ausente                    | fondo_garantia_pct    |
    | iva_acreditable ausente o no booleano        | iva_acreditable       |
    | texto con carácter NUL en código, nombre o domicilio | el campo afectado |
    | porcentaje con más de 6 decimales o no numérico | el campo afectado  |
```

La fila del carácter NUL existe porque en TKT-017 un `NUL` en un texto llegó al motor y respondió `500`: aquí debe rechazarse antes con `422`.

### CA-5 `[M]` · Rechazo · Porcentajes fuera de rango · `PA-02`

```gherkin
Esquema del escenario: Un porcentaje queda fuera del rango que admite la obra
  Dado un cuerpo de alta válido salvo que <campo> vale <valor>
  Cuando un Director de Proyectos envía POST /api/v1/obras
  Entonces responde 422 con tipo "VALIDACION" y el detalle señala <campo>
  Y no se crea ninguna fila en obra ni en la bitácora
  Y ninguna solicitud llega al motor para que lo rechace con un CHECK

  Ejemplos:
    | campo                 | valor      |
    | retencion_destajo_pct | "-0.010000"|
    | retencion_destajo_pct | "1.000001" |
    | fondo_garantia_pct    | "-0.010000"|
    | fondo_garantia_pct    | "1.000001" |
    | umbral_alerta_pct     | "-0.000001"|
```

Bordes que **sí** se admiten, porque el `CHECK` de la base los admite: `"0.000000"` y `"1.000000"` en retención y fondo, y `"0.000000"` en el umbral. El borrador define `Porcentaje` con negativos y hasta tres cifras enteras; el servidor valida el rango más estrecho antes del motor (decisión de la persona dueña, 2026-11-10).

### CA-6 `[M]` · Rechazo · Sin permiso o sin sesión

```gherkin
Escenario: Un rol que no da de alta obras lo intenta
  Dado un usuario autenticado con rol RESIDENTE, COMPRAS, ALMACEN o ADMINISTRACION
  Cuando envía POST /api/v1/obras con un cuerpo válido
  Entonces responde 403 con tipo "PERMISO"
  Y el intento queda asentado como DENEGAR en la bitácora
  Y no se crea ninguna fila en obra

Escenario: Sin sesión
  Cuando alguien sin sesión envía POST /api/v1/obras
  Entonces responde 401
  Y no se crea ninguna fila en obra
```

Una solicitud autenticada sin la cabecera CSRF válida se rechaza como el resto de las mutaciones del sistema (TKT-006), sin crear nada.

### CA-7 `[M]` · Listado de obras · `HDU-001 esc. 2`

```gherkin
Escenario: Cualquier rol autenticado lista las obras
  Dado que existen obras en distintos estados
  Cuando un usuario autenticado de cualquiera de los seis roles envía GET /api/v1/obras
  Entonces responde 200 con la página de obras y su paginación
  Y cada obra trae sus campos del contrato (incluido linea_base_vigente_id)
  Y el orden es determinista: dos llamadas seguidas devuelven el mismo orden

Escenario: Filtro por estado
  Dado que existen obras en PLANEACION y en ACTIVA
  Cuando envía GET /api/v1/obras?estado=ACTIVA
  Entonces solo devuelve las obras ACTIVA
  Y estado repetido (estado=ACTIVA&estado=PLANEACION) devuelve la unión

Escenario: Rechazo · parámetros inválidos
  Cuando envía un estado fuera del enumerado, una pagina menor que 1 o un tamano_pagina fuera de rango
  Entonces responde 422 con tipo "VALIDACION" y el parámetro señalado
  Y no responde 500

Escenario: Página inalcanzable
  Cuando envía una pagina cuyo desplazamiento supera el total de filas, aunque sea enorme
  Entonces responde 200 con la página vacía y el total
  Y no responde 500
```

El último escenario aplica la decisión `D20` de TKT-017: una página que no alcanza filas es página vacía, y un desplazamiento que desborda el entero de la base no produce `500`.

### CA-8 `[M]` · Consulta de una obra

```gherkin
Escenario: Se consulta una obra existente
  Dado que existe la obra "AP-058-25"
  Cuando un usuario autenticado envía GET /api/v1/obras/{obra_id}
  Entonces responde 200 con la obra completa
  Y linea_base_vigente_id es nulo si no tiene línea base congelada
  Y es el identificador de la línea base CONGELADA si la tiene

Escenario: Rechazo · la obra no existe
  Cuando envía GET /api/v1/obras/{obra_id} con un identificador que no existe
  Entonces responde 404

Escenario: Rechazo · identificador mal formado
  Cuando envía GET /api/v1/obras/abc
  Entonces responde 422 con tipo "VALIDACION"
```

### CA-9 `[M]` · Interfaz · Apertura del formulario · `HDU-001 esc. 1`

```gherkin
Escenario: El botón + abre el formulario con el foco en el código
  Dado un Director de Proyectos en la pantalla de obras
  Cuando hace clic en el botón +
  Entonces se abre el formulario de alta de obra
  Y el cursor queda en el campo de código de obra

Escenario: Rechazo · quien no da de alta no ve el botón
  Dado un usuario con rol RESIDENTE, COMPRAS, ALMACEN o ADMINISTRACION en la pantalla de obras
  Entonces ve la lista de obras
  Y no ve el botón +
```

El ocultar el botón es comodidad: la barrera es el `403` del servidor (`CA-6`).

### CA-10 `[M]` · Interfaz · Alta con parámetros · `HDU-001 esc. 2` · `RN-25`

```gherkin
Escenario: Se captura y se guarda una obra desde la pantalla
  Dado el formulario de alta abierto
  Y que el formulario ofrece 15 y 5 como valores sugeridos y editables de retención y fondo de garantía
  Y que el tipo de contrato aparece preseleccionado con su único valor
  Cuando el usuario captura código, nombre y domicilio, indica si el IVA es acreditable y guarda
  Entonces el cliente envía los porcentajes como cadenas decimales exactas ("0.150000", "0.050000")
  Y la obra aparece en la lista en estado PLANEACION
  Y el formulario se cierra
```

Los valores 15 y 5 son una sugerencia del cliente que el usuario puede cambiar; el servidor no los conoce. El cliente calcula con `decimal.js`, nunca con `float`.

### CA-11 `[M]` · Interfaz · Rechazos del servidor · `HDU-001 esc. 3`

```gherkin
Escenario: El código ya existe
  Dado el formulario de alta con el código "AP-058-25" que ya usa otra obra
  Cuando el usuario guarda
  Entonces el formulario permanece abierto con lo capturado conservado
  Y muestra en línea el conflicto con la obra existente (código y nombre) y la acción «Ver la obra», que cierra el formulario y deja la lista a la vista
  Y no aparece ninguna obra nueva en la lista

Escenario: Error de forma
  Cuando el servidor responde 422 con el campo señalado
  Entonces el mensaje se pinta junto a ese campo

Escenario: Sin permiso
  Cuando el servidor responde 403
  Entonces el formulario muestra el mensaje del servidor («Tu rol no permite esta operación.») sin cifras
```

### CA-12 `[M]` · Interfaz · Estados de la lista de obras

```gherkin
Esquema del escenario: La lista de obras cubre sus estados
  Dado el estado <estado> de la consulta de obras
  Entonces la pantalla muestra <vista>

  Ejemplos:
    | estado           | vista                                                                                   |
    | cargando         | un indicador de carga                                                                   |
    | sin obras        | «No hay obras» y, solo para quien puede crearlas, la acción de dar de alta una obra     |
    | con obras        | la lista con código, nombre y estado de cada una                                        |
    | error del servidor | un aviso de error con el identificador de correlación y la opción de reintentar       |
```

El estado `BLOQUEADO` de los demás flujos no aplica: una obra no tiene límite que bloquear.

### CA-13 `[M]` · Flujo de extremo a extremo

```gherkin
Escenario: Alta de obra de punta a punta
  Dado un usuario de humo con rol DIRECTOR_PROYECTOS y la aplicación en marcha
  Y un código de obra único para esta corrida (con sufijo aleatorio)
  Cuando inicia sesión, abre la pantalla de obras, da de alta una obra con ese código y guarda
  Entonces la obra aparece en la lista en PLANEACION

Escenario: Rechazo · el mismo código otra vez
  Cuando da de alta otra obra con el mismo código
  Entonces el formulario muestra el conflicto con la obra existente
  Y la lista sigue teniendo una sola obra con ese código
```

El usuario que siembra hoy `frontend/e2e/sembrar_usuario_humo.py` tiene rol `COMPRAS`, que recibiría `403` al dar de alta: el sembrador se parametriza para sembrar un Director de Proyectos, sin romper el humo de TKT-008, que sigue con su usuario. El código único por corrida evita que una segunda ejecución sobre la misma base choque con la obra de la primera.

### CA-R1 `[M]` · Regresión · El congelado sigue activando la obra · `PA-T17.8` · `HDU-001 esc. 14`

```gherkin
Escenario: Una obra creada por la API se congela y pasa a ACTIVA
  Dado una obra dada de alta por POST /api/v1/obras y una línea base lista para congelar
  Cuando se congela
  Entonces la obra pasa a ACTIVA
  Y GET /api/v1/obras/{obra_id} devuelve linea_base_vigente_id con la línea base congelada
```

Además, las suites de TKT-017 (congelado, materialización, lecturas y control) siguen en verde sin cambios.

### CA-R2 `[M]` · Regresión · El motor sigue siendo la última barrera

```gherkin
Escenario: Las restricciones de obra rechazan lo que el API dejara pasar
  Dado una escritura directa a la tabla obra con el rol de aplicación
  Cuando el código está duplicado, o un porcentaje fuera de 0 a 1, o el umbral es negativo
  Entonces el motor la rechaza con la restricción nombrada correspondiente
```

### CA-R3 `[M]` · Regresión · El formulario de catálogo no cambia con lo ya probado

```gherkin
Escenario: Los campos de texto, correo y fecha se comportan como antes
  Dado el formulario de catálogo extendido con casilla y desplegable
  Cuando se ejecutan sus pruebas de TKT-008c
  Entonces pasan todas, salvo las dos aserciones de TC-86 que esperan la etiqueta cruda `VER_OBRA`
```

> **Ajuste del 2026-11-10 (persona dueña, durante `/sdd-ejecutar`).** Rotular la acción `VER_OBRA` como «Ver la obra» (`CA-11`) obliga a actualizar las dos aserciones de `tkt008_ca11_esc05 · duplicado en línea (TC-86)`, que buscaban la etiqueta cruda. `CA-R3` se lee desde entonces como «ningún comportamiento de los campos de texto, correo y fecha cambia»; el resto de las pruebas de TKT-008c de `FormularioCatalogo.test.tsx` (21 antes de añadir las de este ticket) pasa sin modificar. Ver `impl.md`, entrega b, «Ajustes respecto al design».

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Sin dependencias pendientes: TKT-011b, TKT-010, TKT-017 y TKT-008c están archivados. TKT-012b y TKT-018 dependen de esta entrega, no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | El contexto técnico va al final y la persona dueña fija solo comportamiento visible |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | El Director de Proyectos puede dar de alta una obra sin tocar la base |
| **E** | Estimable sin investigar antes | Sí | Patrones ya existentes en TKT-017 (rutas, bitácora, paginación, error de conflicto) y componente ya construido |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Backend de tres rutas más una pantalla con formulario y una prueba de extremo a extremo. Si el diseño supera ~400 líneas de producción por cambio, se parte en backend y frontend como en TKT-017 |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio tiene un escenario observable |

Sin fallos: pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` tiene su test con el escenario en el nombre (`test_hdu001_esc02_…`, `test_hdu001_esc03_…`) y los rechazos verifican el contrato de error completo.
- [ ] Pruebas contra PostgreSQL real con el rol de aplicación, nunca SQLite; el esquema se construye con `alembic upgrade head`.
- [ ] Una prueba de concurrencia del alta con el mismo código (`CA-3`).
- [ ] Vitest de los cuatro estados de la lista y del formulario; Playwright del flujo (`CA-13`).
- [ ] `ruff`, `mypy`, `lint-imports`, `verificar_float` y `verificar_docs` en verde; `npm run lint`, `typecheck` y `tipos:verificar` en verde.
- [ ] El borrador `docs/api/openapi.yaml` no se rompe y los tipos del cliente se regeneran si cambia.
- [ ] Documentación afectada actualizada en el mismo cambio: la partición en `docs/05-tickets-trabajo.md`, el boceto de la pantalla de obras en `docs/08-wireframes.md` si la persona dueña lo confirma, y el delta del ticket.
- [ ] Las seis auditorías aplicables aprueban.

## Preguntas abiertas y supuestos

Decisiones ya tomadas por la persona dueña el 2026-11-10: partir el ticket y fijar el Must en las tres rutas con su pantalla; precargar 15 y 5 como sugerencia del cliente; que el cliente envíe `tipo_contrato` preseleccionado; validar el rango de los porcentajes con `422`. La empresa se resuelve con la única empresa activa, decisión `A9` de TKT-010 (2026-11-02).

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| 1 | **Normalización del código de obra.** Recomendación: recortar espacios al inicio y al final y guardar en mayúsculas, como se decidió para el código de insumo en TKT-014 (`A2`). Así `ap-058-25` y `AP-058-25 ` chocan con `AP-058-25`. Sin normalizar, la unicidad es por igualdad exacta y dos códigos que se leen igual conviven | Duplicados que el usuario no ve como tales | Resuelta el 2026-11-10 con la recomendación (`design.md`, decisiones D-1 a D-4) |
| 2 | **Campos extra en el cuerpo** (`estado`, `empresa_id`, `id`, `linea_base_vigente_id`…). Recomendación: se ignoran, como se confirmó en TKT-017 (`E2`); el estado inicial y la empresa nunca salen del cliente | Si se rechazaran con `422`, un cliente con campos de más dejaría de funcionar | Resuelta el 2026-11-10 con la recomendación (`design.md`, decisiones D-1 a D-4) |
| 3 | **Dónde vive el botón `+` y la sección «Obras».** Recomendación: una sección «Obras» del armazón visible a los seis roles, con el botón solo para Director de Proyectos y Dirección General, y su boceto en `docs/08-wireframes.md`. Los bocetos actuales no dibujan esta pantalla (la pantalla 3 dice que el alta «no se dibuja aquí») | El esc. 1 no tiene dónde ocurrir | Resuelta el 2026-11-10 con la recomendación (`design.md`, decisiones D-1 a D-4) |
| 4 | **Orden de la lista.** Recomendación: por código ascendente, con el identificador como desempate. El borrador no fija orden | Sin orden fijo, la paginación repite o salta filas | Resuelta el 2026-11-10 con la recomendación (`design.md`, decisiones D-1 a D-4) |
| 5 | El ticket original habla de «(15 %)» y «(5 %)». Se interpretó como valores sugeridos por el cliente, no como constantes del servidor | Una constante en el servidor contradiría `PA-02` | Resuelta el 2026-11-10 |
| 6 | **Costos.** El ticket no depende de ningún servicio externo de pago, cuenta ni clave de API | — | Confirmado: no aplica |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **El usuario de humo es `COMPRAS`** (`frontend/e2e/sembrar_usuario_humo.py`, línea 47): con él, `CA-13` recibiría `403` en el alta y el E2E jamás pasaría | Aceptada. `CA-13` exige un usuario `DIRECTOR_PROYECTOS`; el sembrador se parametriza sin romper el humo existente |
| 2 | Alta | **`CA-13` no era repetible.** Con el código fijo `AP-E2E-01`, la segunda corrida sobre la misma base fallaría en el primer alta por `CODIGO_OBRA_DUPLICADO` | Aceptada. Código único por corrida con sufijo aleatorio |
| 3 | Media | La cláusula final del esc. 2 («disponible para importar su presupuesto») no tenía criterio ni non-goal: un auditor la daría por incumplida | Aceptada. Non-goal explícito: se cumple solo como «existe y se lista»; la importación es TKT-018 |
| 4 | Media | `CA-1` decía «tal como se enviaron» y el esquema devuelve seis decimales: enviar `"0.15"` y recibir `"0.150000"` sería ambiguo | Aceptada. `CA-1` fija la respuesta con seis decimales |
| 5 | Baja | Evidencia a favor que sí resistió: `uq_obra_codigo` y los `CHECK` de rango ya están en `0006`, así que `CA-3` y `CA-R2` se apoyan en el motor y no solo en el caso de uso. Obs. de TKT-017 sobre `NUL` en texto (`500`) y página inalcanzable (`D20`) ya están incorporadas a `CA-4` y `CA-7` | Sin cambio |

Veredicto: cuatro objeciones sustantivas, todas acogidas. Ninguna revela una regla que el PRD no tenga.

## Contexto técnico

Siempre al final.

**Qué existe.**

- Tabla `obra` y `empresa` en la migración `0006`; la `0008` siembra la empresa única y los cuatro tipos de partida. Restricciones de `obra`: `uq_obra_codigo`, `ck_obra_estado`, `ck_obra_tipo_contrato`, los rangos de 0 a 1 de los dos porcentajes y `ck_obra_umbral_alerta_pct_no_negativo`; `creado_por_id` es `NOT NULL`.
- El modelo Core de `obra` en `backend/cimenta/presupuesto/infraestructura/tablas.py` solo declara seis columnas; no hay tabla Core de `empresa`. `repositorio_linea_base.py` ya trae `bloquear_obra`, `leer_obra` y `activar_obra`.
- No hay repositorio de obra, ni caso de uso, ni ruta `/obras`. `api/montaje.py` monta hoy dos enrutadores; se añade uno.
- Patrones reutilizables: `rutas_presupuesto_control.py` (`exigir_rol`, `verificar_origen`, sesión vigente, rutas `def`), el reloj inyectado de `contexto.py`, `cimenta.auditoria.interfaz.asentar` y la denegación asentada de `identidad` (`denegacion.py`). El catálogo de acciones de la bitácora ya incluye `CREAR`.
- El catálogo del contrato de error ya tiene `CODIGO_OBRA_DUPLICADO`; la acción `VER_OBRA` se filtra por rol.
- Frontend: `frontend/src/compartido/formularios/FormularioCatalogo.tsx` admite campos `text`, `email` y `date`; **no admite casilla ni desplegable**, que esta entrega necesita para `iva_acreditable` y `tipo_contrato`. `frontend/src/modulos/presupuesto/rutas.tsx` solo tiene marcadores; `frontend/src/app/navegacion/secciones.ts` no tiene «Obras». `frontend/src/api/generado/servidor.ts` se regenera desde el OpenAPI.

**Contrato.** Operaciones del borrador [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml): `crear_obra`, `listar_obras` y `obtener_obra`, todas con `x-tickets: [TKT-012]`. `docs/07-especificacion-api.md` §4 las lista.

**Módulos y capas.** `presupuesto` (dominio, aplicación, api, infraestructura) y, por su interfaz, `auditoria` e `identidad`. Frontend: `modulos/presupuesto`, la navegación y `compartido/formularios`. **Sin migración.**

**Dependencias cruzadas** (búsqueda del identificador y de su historia sobre `docs/05-tickets-trabajo.md`, los `_index.md` de `sdd/tickets/` y `tools/historias_activas.txt`):

- `docs/05-tickets-trabajo.md`: TKT-012 lo citan TKT-018 (depende de él), TKT-043/TKT-044 (el personal depende de la obra), TKT-049 y TKT-065. Todos futuros salvo TKT-018, que necesita esta entrega y TKT-059.
- `sdd/tickets/tkt-010`: deja abierta la resolución de `empresa_id` en el alta (resuelta: `A9`). `tkt-011`: «cada ticket añade modelos ORM con su primer caso de uso; TKT-012 abre con `obra` y `empresa`». `tkt-017`: «TKT-012 hereda la transición `PLANEACION` → `ACTIVA` escrita por el congelado».
- `tools/historias_activas.txt`: vacía. HDU-001 **no** se activa en esta entrega: `verificar_escenarios` da faltantes de otros tickets (importación y archivos), y la persona dueña dejó HDU-001 sin activar en TKT-017 (`P-13`). Los escenarios 1, 2 y 3 los cubre esta entrega; el 20 queda para TKT-012b.
