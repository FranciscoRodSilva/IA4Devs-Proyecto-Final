# CIMENTA · Especificación de la API

> **Capa SDD:** *Plan · contrato*. Traduce las [historias de usuario](04-historias-usuario.md) a operaciones HTTP con sus esquemas y sus rechazos, sobre la [arquitectura](02-arquitectura.md) y el [modelo de datos](03-modelo-datos.md). Cada operación dice qué roles la invocan, qué reglas `RN-xx` evalúa, qué escenarios cubre y qué ticket la implementa.
>
> **El contrato ejecutable es [`api/openapi.yaml`](api/openapi.yaml)**, OpenAPI 3.1, con los 70 endpoints de la fase 1. Este documento explica sus convenciones y lista los de la fase 2, que todavía no tienen esquema.

---

## Índice

1. [Por qué hay un borrador si FastAPI genera el OpenAPI](#1-por-qué-hay-un-borrador-si-fastapi-genera-el-openapi)
2. [Convenciones](#2-convenciones)
3. [El contrato de error](#3-el-contrato-de-error)
4. [Endpoints de la fase 1](#4-endpoints-de-la-fase-1)
5. [Endpoints de la fase 2](#5-endpoints-de-la-fase-2)
6. [Cómo lo usa la IA](#6-cómo-lo-usa-la-ia)
7. [Lo que este documento asume](#7-lo-que-este-documento-asume)

---

## 1. Por qué hay un borrador si FastAPI genera el OpenAPI

FastAPI publica un OpenAPI a partir del código. Es exacto, pero **llega tarde**: describe lo que ya se escribió, y si un agente inventa una ruta, un nombre de campo o un código de estado, el generado lo documenta con la misma fidelidad que lo correcto. Un esquema derivado del código no puede servir de especificación del código.

Por eso existen los dos, y cada uno manda en un sitio:

| | Borrador · [`api/openapi.yaml`](api/openapi.yaml) | Generado por FastAPI |
|---|---|---|
| **Lo escribe** | Una persona, antes del código | El framework, a partir de las rutas y los modelos de Pydantic |
| **Manda en** | **Todo**: qué rutas existen, qué aceptan, qué rechazan y con qué contrato. Si diverge del generado, manda el borrador | Nada: describe lo que el servidor responde de verdad, y se corrige cuando diverge |
| **Lo consume** | El agente que implementa el ticket, como contexto | El cliente: los tipos de TypeScript se generan de él |
| **Lo verifica** | TKT-061, comparándolo con el generado | Los tests de integración, contra el servidor |

**La comparación es la pieza que hace útiles a los dos.** TKT-061 añade una prueba de contrato que recorre las rutas del hilo vertical y falla el pipeline si el OpenAPI publicado diverge del borrador en rutas, métodos, códigos de estado o esquemas de error. **Si divergen, manda el borrador**: se corrige el código, y si lo que cambió es el diseño, el borrador se modifica en el mismo PR. Lo que no puede ocurrir es que diverjan en silencio.

> El borrador no es documentación de referencia para integradores: no hay consumidores externos ([ADR-007](adr/20260918-contrato-error-negocio.md)). Es el contrato que el agente implementa.

---

## 2. Convenciones

### 2.1. Rutas y nombres

| Aspecto | Convención | Ejemplo |
|---|---|---|
| **Base** | `/api/v1`, mismo origen que el SPA | `/api/v1/requisiciones` |
| **Recursos** | Español, plural, `kebab-case`, vocabulario del [glosario](glosario.md) | `/ordenes-compra`, `/entradas-almacen` |
| **Anidamiento** | Solo cuando el recurso no existe fuera del padre o el padre acota la consulta | `/obras/{obra_id}/saldos-pendientes` |
| **Identificadores** | UUID en la ruta y en el cuerpo. El folio es un dato, no un identificador | `/requisiciones/4d2a9f1c-…` |
| **`operationId`** | Español, `snake_case`, verbo primero. Es el nombre del caso de uso | `crear_requisicion`, `resolver_solicitud_autorizacion` |
| **Campos** | `snake_case`, los mismos nombres que el [modelo de datos](03-modelo-datos.md) | `importe_tope`, `tipo_partida_id` |
| **`tags`** | Uno por módulo: el que es dueño del caso de uso | `compras`, `almacen` |

**Las transiciones de estado son sub-recursos `POST`**, con el sustantivo de la acción: `/requisiciones/{id}/envio`, `/cancelacion`, `/solicitudes-autorizacion/{id}/resolucion`, `/lineas-base/{id}/congelacion`. Nunca un `PATCH` del campo `estado`. La razón es que una transición no es una edición: tiene precondiciones, motivo obligatorio casi siempre, asiento en la bitácora y a veces una regla que evaluar. Un `PATCH {"estado": "AUTORIZADA"}` invita a saltarse las cuatro cosas, y le dice al agente que el estado es un campo más.

Por la misma razón, **lo que no se borra no tiene `DELETE`**. Cerrar sesión es `POST /sesion/cierre` porque escribe `revocada_en` y la fila se conserva. Solo dos rutas usan `DELETE`: una obra sin historial y una requisición en `BORRADOR`, que son los dos únicos casos en que el PRD admite eliminar.

### 2.2. Consultas

**Paginación por página.** `pagina` (desde 1) y `tamano_pagina` (50 por omisión, 200 como máximo). Toda lista paginada responde `{elementos: [...], paginacion: {pagina, tamano_pagina, total}}`. Se elige página y no cursor porque el volumen es pequeño —decenas de operaciones por hora ([arquitectura §1](02-arquitectura.md#1-escala-real-del-sistema))— y porque TanStack Table pagina por número. Los catálogos cerrados —los cuatro tipos de partida, las cuatro filas de presupuesto de control, el semáforo— no se paginan.

**Filtros en la consulta**, con el nombre del campo: `?obra_id=…&estado=EVALUADA&estado=AUTORIZADA`. Los enumerados admiten varios valores repitiendo el parámetro. Los rangos de tiempo son `desde` (inclusivo) y `hasta` (exclusivo).

### 2.3. Dinero, cantidades y fechas

| Tipo | Esquema | Patrón | Ejemplo |
|---|---|---|---|
| Importe | `Importe` · `NUMERIC(18,4)` | `^-?\d{1,14}(\.\d{1,4})?$` | `"45000.0000"` |
| Precio unitario | `PrecioUnitario` · `NUMERIC(14,4)` | `^\d{1,10}(\.\d{1,4})?$` | `"641.3600"` |
| Cantidad | `Cantidad` · `NUMERIC(14,4)` | con signo solo en el libro mayor | `"-20.0000"` |
| Rendimiento | `Rendimiento` · `NUMERIC(18,6)` | `^\d{1,12}(\.\d{1,6})?$` | `"0.673400"` |
| Porcentaje | `Porcentaje` · `NUMERIC(9,6)` | **fracción**, no centésimas | `"0.150000"` es 15 % |
| Marca de tiempo | `date-time` | RFC 3339 **con zona** | `"2026-10-15T10:42:00-06:00"` |
| Fecha de negocio | `date` | sin hora | `"2026-10-22"` |

**Todo lo decimal es `type: string` con `format: decimal`. Ningún esquema del borrador usa `number`**, y es comprobable: el YAML no contiene ni uno. Un número JSON pasa por el flotante de doble precisión de JavaScript, y el principio de exactitud del [modelo de datos §1](03-modelo-datos.md#1-principios-de-modelado) no admite que el importe se degrade en el transporte. El cliente convierte con `decimal.js`. El servidor responde siempre con la escala completa —cuatro decimales en importes—; en la entrada acepta menos.

Los enteros solo aparecen donde no hay unidad monetaria ni física: conteos (`pendientes`, `reprogramaciones`, `filas_leidas`), tamaños en bytes, días de la semana y paginación.

Las fechas de negocio sin hora —la fecha de la remisión, la comprometida de entrega— viajan como `date` porque en el esquema son `DATE`: convertirlas a medianoche con zona inventa una hora que nadie capturó y las desplaza un día al cruzar husos.

### 2.4. Códigos de estado

| Código | Cuándo | Cuerpo |
|---|---|---|
| `200` | Consulta, o transición que devuelve el recurso transformado | El recurso |
| `201` | Se creó un recurso. Lleva `Location`. Crear una requisición y enviarla en un paso es `201`; enviar un borrador que ya existía es `200` | El recurso creado |
| `202` | Se aceptó un trabajo en segundo plano: el análisis de una importación | El recurso en su estado intermedio |
| `204` | Éxito sin cuerpo: cierre de sesión, eliminación de un borrador | — |
| `401` | Sin sesión, caducada o revocada; credenciales inválidas | `ErrorSesion` |
| `403` | Falta el rol, o la autoridad sobre la excepción, o la prueba de origen | `ErrorPermiso` |
| `404` | El recurso no existe | `ErrorNoEncontrado` |
| `409` | **El estado actual impide la operación**: una regla de negocio, un conflicto de estado o unicidad, o un bloqueo que venció | `ErrorReglaNegocio`, `ErrorConflictoEstado` o `ErrorConcurrencia` |
| `422` | **La petición está mal formada**: falta un campo, sobra un signo, el motivo está vacío | `ErrorValidacion` |
| `429` | Límite de intentos de acceso (`RNF-04`) | `ErrorLimiteIntentos` |

La frontera que más importa es la de `409` y `422`, y se decide con una pregunta: **¿la misma petición, contra otro estado del sistema, habría pasado?** Si sí, es `409`. Una requisición de $15,000 pasa con $20,000 disponibles y se bloquea con $12,000: es `409`. Una requisición sin tipo de partida no pasa nunca: es `422`, aunque la obligación venga de `RN-02`. Cuando la forma la impone una regla, el error del campo la cita (`regla: "RN-02"`), pero el código sigue siendo `422` porque es lo que HDU-002 esc. 6 y HDU-005 esc. 4 piden.

**Una requisición bloqueada responde `409` y, aun así, se persiste.** No es una contradicción: el `409` dice que la operación pedida —dejar la requisición lista para convertirse en orden— no ocurrió; la fila en `BLOQUEADA` y su solicitud de autorización existen y sus identificadores viajan en el `detalle`. Así lo fija el flujo de [arquitectura §8.1](02-arquitectura.md#81-requisición-evaluada-contra-presupuesto--rn-03).

### 2.5. Sesión y CSRF

**La sesión es una cookie opaca**, `cimenta_sesion`, `HttpOnly`, `Secure`, `SameSite=Lax`, con un identificador contra la tabla `sesion` y ningún dato del usuario ([ADR-014](adr/20260919-sesion-con-estado.md)). En el YAML es el esquema de seguridad `sesion`, de tipo `apiKey` en cookie, y es el global: toda operación lo exige salvo **las dos únicas rutas sin sesión** —`GET /sesion/csrf` y `POST /sesion`—, que TKT-006 lista expresamente.

**Todo método que muta estado exige además el token de doble envío** (`RNF-05`): la cookie `cimenta_csrf`, legible desde JavaScript, y la cabecera `X-CSRF-Token` con el mismo valor. En el YAML es el esquema `csrf`, declarado en cada `POST`, `PUT`, `PATCH` y `DELETE` —se comprueba por programa que no falta en ninguno—. Sin token, o con uno distinto, `403` con `motivo: ORIGEN_NO_VERIFICADO`.

El inicio de sesión también muta estado, y por eso hay una ruta previa, `GET /sesion/csrf`, que fija la cookie y devuelve el token antes de que exista sesión. El token se rota al iniciar y al cerrar sesión.

### 2.6. Idempotencia

**En la fase 1 la protección contra el doble envío es la máquina de estados**, no una cabecera. Enviar dos veces la misma requisición, resolver dos veces la misma solicitud o cancelar dos veces la misma orden responde `409` a la segunda, con el estado actual. Las creaciones que tienen una clave natural la hacen cumplir el motor: código de obra, RFC, folio de remisión por proveedor.

Queda un hueco declarado: dos `POST /requisiciones` idénticos por un doble clic crean dos requisiciones, y las dos consumen. El cliente deshabilita el botón al enviar, y la consulta de requisiciones vivas de HDU-002 esc. 13 hace visible la duplicada para cancelarla. **No se añade `Idempotency-Key` en la fase 1** porque la única operación que de verdad lo necesita es la sincronización diferida, y allí el identificador lo genera el cliente al capturar, no al enviar, y viaja como `id` del recurso: es TKT-064, y ese diseño sirve también para cerrar este hueco si llegara a importar.

La única operación de la fase 1 idempotente por diseño lo declara: confirmar un archivo ya `DISPONIBLE` devuelve la misma fila. `capturar_presupuesto_control` es un `PUT` porque reemplaza el tope de una fila que la ruta identifica, pero **no se declara idempotente**: cada recaptura exige motivo y deja su propio asiento en la bitácora, así que repetirla no es inocuo.

### 2.7. Correlación

Toda respuesta lleva la cabecera `X-Correlacion-Id`, y todo error la repite en el cuerpo como `correlacion_id` (`RNF-13`, TKT-005). Es lo que el usuario cita cuando llama para decir que algo falló, y lo que TKT-058 usa para encontrar la petición en Sentry. **No se asienta en la bitácora**: son dos registros para dos preguntas distintas.

El servidor genera siempre el identificador, un UUID, y descarta el que traiga la petición `(asumido)`: aceptarlo permitiría inyectar texto en el registro técnico. Un error no controlado responde `500` con un cuerpo mínimo, `mensaje` y `correlacion_id`, sin `tipo` `(asumido)`.

### 2.8. Archivos

**El API nunca recibe ni sirve los bytes** ([ADR-016](adr/20261001-almacenamiento-de-objetos.md), [arquitectura §7.7](02-arquitectura.md#77-archivos-y-evidencia)). En la fase 1 el único archivo es el Excel de la línea base, y su recorrido son cuatro llamadas:

| Paso | Llamada | Qué pasa |
|---|---|---|
| 1 | `POST /obras/{obra_id}/importaciones` con nombre, tamaño, SHA-256 y tipo declarado | En una transacción nacen la importación en `RECIBIDO` y el `archivo` en `PENDIENTE`. Responde con la URL prefirmada de escritura. Lo inválido por la declaración —formato distinto de `.xlsx` (no se admite `.xls`) o tamaño mayor que el límite— es `422` y no crea nada |
| 2 | `PUT` directo al almacén de objetos | El navegador sube el Excel. El API no participa |
| 3 | `POST /archivos/{archivo_id}/confirmacion` | El servidor compara tamaño y hash con el objeto almacenado y determina el tipo **leyendo los bytes**. Si coincide, `DISPONIBLE`; si no, `409` `ARCHIVO_TAMANO_DISTINTO`, `ARCHIVO_HASH_DISTINTO` o `ARCHIVO_TIPO_NO_PERMITIDO`, y la fila sigue `PENDIENTE` hasta el barrido |
| 4 | `POST /importaciones/{importacion_id}/analisis` | Exige el archivo `DISPONIBLE` —si no, `409`— y arranca el análisis con `202` |

La fila del archivo la crea el caso de uso que crea el documento, en el módulo dueño del documento, porque `archivos` no conoce a ningún módulo de negocio y no puede comprobar que la importación exista ([arquitectura §7.7](02-arquitectura.md#77-archivos-y-evidencia)). Lo que sí es genérico y vive en `archivos` es la confirmación y la emisión de la URL de lectura. En la fase 2, TKT-066 añade las rutas de adjuntar sobre un documento ya guardado siguiendo el mismo patrón: `POST /avances/{id}/adjuntos` en `avance`, no un `POST /archivos` genérico.

---

## 3. El contrato de error

Cada rechazo tiene forma fija y el cliente lo distingue por `tipo`. Todos comparten tres campos —`tipo`, `mensaje`, `correlacion_id`— y añaden los suyos. TKT-005 implementa **los siete `tipo`** del borrador —`REGLA_NEGOCIO`, `VALIDACION`, `PERMISO`, `CONFLICTO`, `CONCURRENCIA`, `SESION` y `LIMITE_INTENTOS`— más `NO_ENCONTRADO` para el `404`, y ninguno más.

**Las `acciones` se filtran por los roles de quien llama.** Un rechazo nunca ofrece una acción que le respondería `403`: si Compras topa con una obra sin tope de control, recibe el `409` sin la acción `CAPTURAR_PRESUPUESTO_CONTROL`, que solo Dirección General puede ejecutar. Por eso `acciones` puede llegar vacía aunque el rechazo tenga salida para otro rol, y el mensaje dice a quién pedírsela. **Una excepción:** `REINTENTAR` de un `409` `CONCURRENCIA` no se filtra, porque repite la operación que quien llama acaba de invocar y que `api/` ya autorizó por su rol; sin ella, mientras la sesión no fije los roles, todo vencimiento llegaría sin su salida documentada (supuesto 14).

### 3.1. Los tres esquemas principales

| `tipo` | Código | Esquema | Campos propios | Para qué |
|---|---|---|---|---|
| `REGLA_NEGOCIO` | `409` | `ErrorReglaNegocio` | `regla` (`^RN-\d{2}$`), `detalle`, `acciones[]` | Una regla del PRD impide la operación. Es **exactamente** el contrato de [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) más `correlacion_id` |
| `VALIDACION` | `422` | `ErrorValidacion` | `errores[]` con `campo`, `codigo`, `mensaje` y `regla` opcional | La petición está mal formada. Sustituye al `{"detail": [{"loc": …}]}` por omisión de FastAPI |
| `PERMISO` | `403` | `ErrorPermiso` | `motivo` (`ROL_INSUFICIENTE`, `AUTO_RESOLUCION`, `NO_ES_SOLICITANTE`, `ORIGEN_NO_VERIFICADO`), `roles_requeridos[]` | Falta el rol, la autoridad sobre la excepción o la prueba de origen. **Nunca lleva cifras del recurso** (HDU-006 esc. 12) |

Los cuatro motivos de `403` vienen de capas distintas, y conviene que el cliente lo sepa: `ROL_INSUFICIENTE` lo decide `api/`; `AUTO_RESOLUCION` —nadie resuelve lo suyo— y `NO_ES_SOLICITANTE` —solo quien levantó la requisición la cancela— los decide `dominio/`, porque es una regla del negocio ([arquitectura §7.6](02-arquitectura.md#76-seguridad-de-la-frontera)); `ORIGEN_NO_VERIFICADO` es el CSRF. Con usuario autenticado, todo `403` se asienta en la bitácora como `DENEGAR`, en una transacción propia porque no hay cambio que acompañar. Las denegaciones anónimas —el CSRF o las credenciales del inicio de sesión— van a `intento_acceso` y al registro técnico, no a la bitácora, cuyo `usuario_id` es obligatorio.

**`REGLA_NEGOCIO` · requisición que excede el importe (HDU-002 esc. 4):**

```json
{
  "tipo": "REGLA_NEGOCIO",
  "regla": "RN-03",
  "mensaje": "La requisición excede el presupuesto de control disponible del tipo de partida MUROS.",
  "detalle": {
    "obra": "AP-058-25 · Union Square F2",
    "tipo_partida": "MUROS",
    "presupuestado": "45000.0000",
    "consumido": "33000.0000",
    "consumido_desglose": {
      "requisiciones_vivas": "9000.0000",
      "comprometido": "14000.0000",
      "ejercido": "10000.0000",
      "total": "33000.0000"
    },
    "disponible": "12000.0000",
    "solicitado": "15000.0000",
    "excedente": "3000.0000",
    "requisicion_id": "4d2a9f1c-3b7e-4e5a-8c6d-2f1e0a9b8c7d",
    "folio": "REQ-AP05825-0042",
    "solicitud_autorizacion_id": "9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b"
  },
  "acciones": [
    { "clave": "VER_SOLICITUD_AUTORIZACION", "metodo": "GET",  "ruta": "/api/v1/solicitudes-autorizacion/9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b" },
    { "clave": "CANCELAR_REQUISICION",       "metodo": "POST", "ruta": "/api/v1/requisiciones/4d2a9f1c-3b7e-4e5a-8c6d-2f1e0a9b8c7d/cancelacion" }
  ],
  "correlacion_id": "c3d4e5f6-a7b8-4901-8cde-f01234567890"
}
```

`consumido_desglose` es aditivo: el contrato de §7.3 no cambia, y la pantalla de bloqueo puede mostrar los tres sumandos de la [regla 5 de `CLAUDE.md`](../CLAUDE.md) sin pedirlos aparte.

**`VALIDACION` · requisición sin tipo de partida (HDU-002 esc. 6):**

```json
{
  "tipo": "VALIDACION",
  "mensaje": "La petición tiene 1 campo inválido.",
  "errores": [
    {
      "campo": "tipo_partida_id",
      "codigo": "OBLIGATORIO",
      "mensaje": "No existe gasto sin centro de costos; la requisición necesita tipo de partida.",
      "regla": "RN-02"
    }
  ],
  "correlacion_id": "c3d4e5f6-a7b8-4901-8cde-f01234567890"
}
```

**`PERMISO` · Dirección General intenta autorizar su propia solicitud (HDU-003 esc. 8):**

```json
{
  "tipo": "PERMISO",
  "motivo": "AUTO_RESOLUCION",
  "mensaje": "Nadie resuelve sus propias solicitudes, aunque tenga el rol de Dirección General.",
  "roles_requeridos": ["DIRECCION_GENERAL"],
  "correlacion_id": "c3d4e5f6-a7b8-4901-8cde-f01234567890"
}
```

### 3.2. Los esquemas auxiliares

Hacen falta cuatro más, y los cuatro respetan la misma envoltura:

| `tipo` | Código | Por qué no cabe en los tres |
|---|---|---|
| `CONFLICTO` | `409` | Conflictos de estado o de unicidad que **no son una regla `RN-xx`**: código de obra duplicado, solicitud ya resuelta, transición desde un estado que no la admite, archivo cuyo hash no coincide, obra sin línea base congelada o sin tope de control. Misma forma que `REGLA_NEGOCIO` con un `codigo` del **catálogo cerrado** `CodigoConflicto` en lugar de `regla`. Etiquetarlos con una regla que no es la suya ensuciaría la consulta de excepciones por regla de la bitácora |
| `CONCURRENCIA` | `409` | Venció `lock_timeout` o `statement_timeout` (`RNF-16`). Ver §3.3 |
| `SESION` | `401` | Sin sesión, caducada, revocada o credenciales inválidas. No distingue correo inexistente de contraseña errónea |
| `LIMITE_INTENTOS` · `NO_ENCONTRADO` | `429` · `404` | Forma mínima, con `correlacion_id` |

**El catálogo de `codigo` es cerrado.** Un `409` que no viola una regla lleva uno de los códigos de `CodigoConflicto` en [`api/openapi.yaml`](api/openapi.yaml), nunca una `RN-xx` inventada para la ocasión. Los que más se confunden con una regla son dos: **`SIN_LINEA_BASE_CONGELADA`** y **`SIN_PRESUPUESTO_CONTROL`**, que responden igual en la requisición, en el disponible y en el semáforo —no hay contra qué evaluar, así que no es `RN-03`—, y **`ESTADO_NO_PERMITE_OPERACION`** al emitir una orden desde una requisición `BLOQUEADA`, con la acción `VER_SOLICITUD_AUTORIZACION`, sin regla y sin asentarse como `RN-03`. Ampliar el catálogo exige cambiar el borrador en el mismo PR que añade el caso.

**`acciones[].ruta` es absoluta, con `/api/v1`.** El cliente la usa tal cual, sin componerla. El ejemplo de [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) está alineado con esta forma; si alguna vez divergen, manda el borrador.

### 3.3. El vencimiento del bloqueo: `409`, no `423` ni `503`

`RNF-16` exige que una espera de bloqueo vencida se traduzca al contrato de error **con una acción**, no a un fallo genérico. Había tres candidatos y se elige `409` con `tipo: CONCURRENCIA`, cabecera `Retry-After` y la acción `REINTENTAR`:

- **`423 Locked`** describe un recurso bloqueado hasta que alguien lo desbloquee explícitamente, y viene de WebDAV. Aquí el bloqueo dura milisegundos y se libera solo; el `423` sugeriría que hay que esperar a alguien. Además, ningún cliente HTTP genérico lo trata de forma especial, así que no aporta nada que `tipo` no diga ya.
- **`503 Service Unavailable`** declara al servidor incapaz de atender. Es exactamente el *fallo genérico* que `RNF-16` prohíbe, y haría que TKT-058 lo agregara en Sentry como una caída cuando es contención esperada.
- **`409 Conflict`** dice que el estado actual del recurso impide la operación ahora. Es cierto —otra transacción tiene la bolsa— y es el código que el cliente ya sabe tratar: lee `tipo`, pinta el mensaje y ofrece el botón de la acción.

Lo que el `409` no lleva es `regla`. No se violó ninguna, y asentar un bloqueo vencido como `RN-03` haría que la consulta de excepciones del mes contara intentos que nadie hizo. **Nada se persiste** en un vencimiento: la transacción se deshace entera, también la requisición, así que reintentar es seguro.

---

## 4. Endpoints de la fase 1

Base `/api/v1`. **Roles**: DG Dirección General · DP Director de Proyectos · RE Residente · CO Compras · AL Almacén · AD Administración · *Todos* los seis. Los escenarios se citan por historia y número. El esquema completo de cada operación —cuerpo, respuestas, ejemplos— está en [`api/openapi.yaml`](api/openapi.yaml).

### 4.1. `identidad`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/sesion/csrf` | sin sesión | — | — | TKT-057 |
| `POST` | `/sesion` | sin sesión | — | — | TKT-006, TKT-057 |
| `GET` | `/sesion` | Todos | — | — | TKT-006 |
| `POST` | `/sesion/cierre` | Todos | — | — | TKT-006 |

### 4.2. `presupuesto`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/tipos-partida` | Todos | — | HDU-002 · 1 | TKT-012 |
| `GET` | `/insumos` | Todos | — | HDU-001 · 10 | TKT-012 |
| `POST` | `/obras` | DP, DG | RN-25 | HDU-001 · 2, 3 | TKT-012 |
| `GET` | `/obras` | Todos | — | HDU-001 · 2 | TKT-012 |
| `GET` | `/obras/{obra_id}` | Todos | — | — | TKT-012 |
| `PATCH` | `/obras/{obra_id}` | DP, DG | RN-25 | — | TKT-012 |
| `DELETE` | `/obras/{obra_id}` | DP, DG | RN-01 | HDU-001 · 20 | TKT-012 |
| `POST` | `/obras/{obra_id}/suspension` | DP, DG | — | HDU-001 · 20 | TKT-012 |
| `POST` | `/obras/{obra_id}/reactivacion` | DP, DG | — | — | TKT-012 |
| `POST` | `/obras/{obra_id}/cierre` | DP, DG | — | HDU-001 · 20 | TKT-012 |
| `POST` | `/obras/{obra_id}/importaciones` | DP | RN-01 | HDU-001 · 4, 21, 24 | TKT-018, TKT-059 |
| `GET` | `/obras/{obra_id}/importaciones` | DP, DG | — | — | TKT-018 |
| `GET` | `/importaciones/{importacion_id}` | DP, DG | — | HDU-001 · 4, 5, 10 | TKT-018, TKT-015 |
| `POST` | `/importaciones/{importacion_id}/analisis` | DP | — | HDU-001 · 4, 6–9, 24, 25, 27 | TKT-018, TKT-015 |
| `GET` | `/importaciones/{importacion_id}/errores` | DP, DG | — | HDU-001 · 6–9, 27 | TKT-018, TKT-015 |
| `POST` | `/importaciones/{importacion_id}/confirmacion` | DP | RN-01 | HDU-001 · 6–9, 11–13 | TKT-018, TKT-017 |
| `POST` | `/importaciones/{importacion_id}/descarte` | DP | — | HDU-001 · 13 | TKT-018 |
| `GET` | `/obras/{obra_id}/lineas-base` | DG, DP, CO | RN-01 | — | TKT-017 |
| `GET` | `/lineas-base/{linea_base_id}` | DG, DP, CO | RN-01 | HDU-001 · 14, 18 | TKT-017 |
| `POST` | `/lineas-base/{linea_base_id}/congelacion` | DP | RN-01, RN-24 | HDU-001 · 14, 19 | TKT-017 |
| `GET` | `/lineas-base/{linea_base_id}/conceptos` | DG, DP, CO | RN-01 | HDU-001 · 14 | TKT-017 |
| `GET` | `/lineas-base/{linea_base_id}/explosion` | DG, DP, CO | RN-24 | HDU-001 · 14 | TKT-016, TKT-017 |
| `GET` | `/lineas-base/{linea_base_id}/presupuesto-control` | DG, DP, CO | RN-03 | HDU-001 · 15 | TKT-017 |
| `PUT` | `/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}` | DG | RN-03, RN-04 | HDU-001 · 15, 17, 22, 23 | TKT-017 |

HDU-001 esc. 18 —modificar una línea base congelada— **no tiene ruta que lo provoque**, y es deliberado: ninguna operación escribe sobre `linea_base_concepto` ni `explosion_presupuesto`. El escenario se prueba contra el motor, con el disparador del invariante 14.

### 4.3. `archivos`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/archivos/{archivo_id}` | DG, DP | — | HDU-001 · 24 | TKT-059 |
| `POST` | `/archivos/{archivo_id}/confirmacion` | DP | — | HDU-001 · 24, 25, 26 | TKT-059 |
| `GET` | `/archivos/{archivo_id}/descarga` | DG, DP | — | — | TKT-059 |

El alta de la fila `PENDIENTE` no tiene ruta propia en `archivos`: la crea `crear_importacion` (§2.8). Los roles de lectura son los de la importación, el único documento con archivo en la fase 1; TKT-066 los generaliza por tipo de documento.

### 4.4. `compras`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/obras/{obra_id}/tipos-partida/{tipo_partida_id}/disponible` | CO, DG, DP | RN-03 | HDU-002 · 1, 13 · HDU-006 · 15 | TKT-023 |
| `GET` | `/obras/{obra_id}/tipos-partida/{tipo_partida_id}/requisiciones-vivas` | CO, DG, DP | RN-03 | HDU-002 · 13 | TKT-023 |
| `POST` | `/requisiciones` | CO | RN-02, RN-03, RN-04 | HDU-002 · 2–10 · HDU-001 · 16 · HDU-006 · 15 | TKT-023, TKT-021 |
| `GET` | `/requisiciones` | CO, DG, DP | — | HDU-002 · 13 | TKT-023 |
| `GET` | `/requisiciones/{requisicion_id}` | CO, DG, DP | — | HDU-002 · 4 | TKT-023 |
| `PUT` | `/requisiciones/{requisicion_id}` | CO | RN-02 | HDU-002 · 2, 12 | TKT-023 |
| `DELETE` | `/requisiciones/{requisicion_id}` | CO | — | HDU-002 · 2 | TKT-023 |
| `POST` | `/requisiciones/{requisicion_id}/envio` | CO | RN-02, RN-03, RN-04 | HDU-002 · 3–10 | TKT-023, TKT-021 |
| `POST` | `/requisiciones/{requisicion_id}/cancelacion` | CO | RN-03, RN-04 | HDU-002 · 11, 13 · HDU-003 · 10 | TKT-023 |
| `POST` | `/solicitudes-autorizacion` | AL, RE | RN-07, RN-04 | HDU-005 · 5 | TKT-027 |
| `GET` | `/solicitudes-autorizacion` | DG | RN-03, RN-07 | HDU-003 · 2, 10 | TKT-027 |
| `GET` | `/solicitudes-autorizacion/contador` | DG | — | HDU-003 · 1 | TKT-027 |
| `GET` | `/solicitudes-autorizacion/{solicitud_id}` | DG, CO, AL, RE | RN-03, RN-07 | HDU-003 · 3, 10 | TKT-027 |
| `POST` | `/solicitudes-autorizacion/{solicitud_id}/resolucion` | DG | RN-03, RN-04, RN-07 | HDU-003 · 4–10 | TKT-027, TKT-025, TKT-026 |
| `GET` | `/proveedores/{proveedor_id}/pedidos-por-obra` | CO, DG | RN-02 | HDU-004 · 11 | TKT-032 |
| `POST` | `/ordenes-compra` | CO | RN-02, RN-06 | HDU-004 · 4–8 | TKT-030 |
| `GET` | `/ordenes-compra` | CO, AL, RE, DG, DP | — | — | TKT-030 |
| `GET` | `/ordenes-compra/{orden_compra_id}` | CO, AL, RE, DG, DP | RN-06 | HDU-004 · 5 · HDU-005 · 2 | TKT-030 |
| `POST` | `/ordenes-compra/{orden_compra_id}/cancelacion` | CO | RN-03, RN-06 | HDU-004 · 9, 10 | TKT-031 |
| `POST` | `/ordenes-compra/{orden_compra_id}/cierre` | CO, AL | RN-06 | HDU-005 · 12 | TKT-054 · `x-sin-exito` |
| `POST` | `/ordenes-compra/{orden_compra_id}/renglones/{renglon_id}/reprogramacion` | CO, AL | RN-06 | HDU-005 · 10, 11 | TKT-054, TKT-037 |

Cuatro decisiones de esta tabla que no son evidentes:

**El disponible y las requisiciones vivas cuelgan de la bolsa, no de la requisición.** `/obras/{obra_id}/tipos-partida/{tipo_partida_id}/…` nombra las cuatro bolsas por obra de PA-01 en la propia ruta, y su respuesta trae `consumido` con los tres sumandos de la [regla 5 de `CLAUDE.md`](../CLAUDE.md). `compras` es dueño de ese cálculo: el ejercido le llega por el puerto `FuenteEjercido`, que declara `compras/aplicacion` e implementan `almacen` (materiales) y, en la fase 2, `avance` (destajo). Es la misma consulta que aplica `RN-03`, y el semáforo no la reescribe: la obtiene por la interfaz publicada de `compras`. El test de TKT-021 que verifica que coinciden al céntimo puede llamar a esta ruta.

**Dos acciones distintas para pedir autorización.** En `RN-03` la solicitud **ya existe**: nace en la misma transacción que el bloqueo ([arquitectura §8.1](02-arquitectura.md#81-requisición-evaluada-contra-presupuesto--rn-03)), así que la acción es **`VER_SOLICITUD_AUTORIZACION`**, un `GET` a ella; la misma acción acompaña al `409` `ESTADO_NO_PERMITE_OPERACION` de emitir una orden desde una requisición `BLOQUEADA`. En `RN-07` la entrada se deshizo entera y no hay nada persistido a lo que colgarla, así que la acción es **`SOLICITAR_AUTORIZACION`**, `POST /solicitudes-autorizacion`, que la crea con motivo `EXCEDE_ORDENADO`; el servidor recalcula las cifras contra la orden y el renglón, nunca acepta las del cliente, y guarda en la solicitud el renglón y la cantidad excedente. Una clave, un método. **Autorizar un excedente lo habilita, no lo registra** (`PA-16`, resuelta el 2026-10-17): con la solicitud `AUTORIZADA`, Almacén reenvía la entrada a `POST /entradas-almacen` citando `solicitud_autorizacion_id` en el renglón, y es esa entrada la que suma el excedente a la recepción (§4.6). Una autorización que nunca se usa no altera la orden.

**Cancelar una requisición es cosa de su solicitante** (HDU-002 esc. 11). Otro usuario de Compras recibe `403`, y la lista de vivas ofrece la acción solo en las propias.

**`POST /ordenes-compra/{id}/cierre` existe y nunca cierra.** No hay cierre con saldo (PA-07), y una orden completa ya está `CERRADA` porque el estado se deriva. Pero HDU-005 esc. 12 exige que el intento reciba `409` con `RN-06` y la acción `REPROGRAMAR`, y sin ruta recibiría un `405` sin salida. La ruta responde siempre `409`, y un test verifica que no cambia el estado de ninguna orden. Es la única operación marcada `x-sin-exito: true`: TKT-061 la excluye de la comparación de códigos `2xx`.

### 4.5. `proveedores`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `POST` | `/proveedores` | CO | RN-17 | HDU-004 · 2, 3 | TKT-029 |
| `GET` | `/proveedores` | Todos | — | HDU-004 · 2, 12 | TKT-029 |
| `GET` | `/proveedores/{proveedor_id}` | Todos | — | — | TKT-029 |
| `PATCH` | `/proveedores/{proveedor_id}` | CO | RN-17 | — | TKT-029 |
| `POST` | `/proveedores/{proveedor_id}/baja` | CO | — | HDU-004 · 12 | TKT-029 |
| `POST` | `/proveedores/{proveedor_id}/desactivacion` | CO | — | HDU-004 · 12 | TKT-029 |

**Baja y desactivación son dos operaciones** (HDU-004 esc. 12), y ninguna borra. `proveedor.estado` es `ACTIVO`, `DESACTIVADO` o `BAJA`. Desactivar se admite siempre: el proveedor sale del selector de órdenes nuevas y sus órdenes pendientes se siguen recibiendo. Dar de baja es definitivo y se rechaza con `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` si tiene órdenes `ABIERTA` o `PARCIAL`, con la acción de desactivarlo.

### 4.6. `almacen`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `POST` | `/entradas-almacen` | AL, RE | RN-02, RN-05, RN-06, RN-07 | HDU-005 · 1–7, 14, 21, 22 | TKT-035, TKT-037 |
| `GET` | `/entradas-almacen` | AL, RE, CO, DG, DP | — | HDU-005 · 3 | TKT-037 |
| `GET` | `/entradas-almacen/{entrada_id}` | AL, RE, CO, DG, DP | — | HDU-005 · 7, 8 | TKT-037 |
| `POST` | `/entradas-almacen/{entrada_id}/correccion` | AL | RN-06, RN-07 | HDU-005 · 8, 9, 23 | TKT-036, TKT-037 |
| `GET` | `/obras/{obra_id}/saldos-pendientes` | AL, RE, CO, DG, DP | RN-06 | HDU-005 · 13 | TKT-037 |
| `GET` | `/obras/{obra_id}/existencias` | AL, RE, CO, DG, DP | — | HDU-005 · 8 | TKT-037 |
| `GET` | `/obras/{obra_id}/movimientos-inventario` | AL, RE, CO, DG, DP | — | HDU-005 · 3, 8 | TKT-037 |

**La existencia se llama `cantidad_calculada` y no `existencia`.** Es una suma del libro mayor en el momento de la consulta ([ADR-005](adr/20260918-ledger-inventario.md)), y un campo de API con nombre de columna es la invitación más directa a que un agente la cree. **La corrección declara la cantidad correcta absoluta** (`cantidad_correcta`), no la diferencia: el servidor calcula el `AJUSTE` de signo contrario, que es el único movimiento que escribe. HDU-005 esc. 8 la ejemplifica sobre una orden `PARCIAL`. **Una entrada de una orden `CERRADA` no se corrige** (`PA-17`, resuelta el 2026-10-17): responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` y nada se registra (HDU-005 esc. 23).

**El excedente autorizado se suma a la recepción y queda marcado** (`RN-07`, `PA-16`, resuelta el 2026-10-17). Un renglón de `POST /entradas-almacen` puede citar `solicitud_autorizacion_id`: una solicitud `EXCEDE_ORDENADO` `AUTORIZADA` de ese mismo renglón, que `almacen` valida por la interfaz de aplicación de `compras`. El servidor admite hasta `saldo + cantidad excedente autorizada`, marca el renglón de la entrada con `excedente` —lo que pasó del saldo—, incrementa `cantidad_excedente_autorizada` del renglón de la orden y la orden queda `CERRADA`. El excedente es costo ejercido: entra al libro mayor y al `consumido` (HDU-005 esc. 21). Con la solicitud `PENDIENTE` o `RECHAZADA`, o con más excedente que el autorizado, `409` `RN-07` y nada se registra (esc. 22); con una solicitud de otro renglón o ya consumida, `409` `CONFLICTO` `SOLICITUD_NO_APLICABLE`, código nuevo del catálogo cerrado. La solicitud se consume una sola vez.

**Cancelar una orden y registrar una entrada bloquean en el mismo orden**: `orden_compra` primero y después sus renglones ordenados por id.

### 4.7. `auditoria`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/bitacora` | DG, DP | RN-04 | HDU-003 · 11 · HDU-001 · 22 | TKT-007, TKT-027 |

Filtrar por `regla_negocio=RN-03` devuelve en una consulta los bloqueos —también los nunca resueltos—, las autorizaciones, los rechazos y las recapturas de tope, que se asientan con la misma regla ([modelo de datos §4.2](03-modelo-datos.md#42-línea-base)). La consulta es paginada, el asiento más reciente primero. Los `403` de usuarios autenticados aparecen con `accion=DENEGAR`; `AccionBitacora` es exactamente el enumerado de `bitacora.accion` del [modelo de datos §10](03-modelo-datos.md).

### 4.8. `analitica`

| Método | Ruta | Roles | Reglas | Escenarios | Ticket |
|---|---|---|---|---|---|
| `GET` | `/obras/{obra_id}/semaforo` | DG, DP | RN-21, RN-03 | HDU-006 · 1–6, 8–16 | TKT-040, TKT-039, TKT-060 |
| `GET` | `/obras/{obra_id}/semaforo/partidas/{tipo_partida_id}` | DG, DP | RN-21 | HDU-006 · 4, 13, 14 | TKT-040 |
| `GET` | `/obras/{obra_id}/semaforo/partidas/{tipo_partida_id}/movimientos` | DG, DP | RN-21 | HDU-006 · 7 | TKT-040 |
| `GET` | `/semaforo/alertas` | DG, DP | RN-21 | HDU-006 · 11, 16 | TKT-040 |

El semáforo es la respuesta donde más fácil es mentir sin querer, así que su esquema hace seis cosas explícitas:

| Qué | Cómo aparece en la respuesta | De dónde sale |
|---|---|---|
| **El consumido es el de `compras`** | `requisiciones_vivas`, `comprometido`, `ejercido`, `consumido` y `disponible` de cada fila salen de la interfaz publicada de `compras`, leída con el rol de solo lectura. `analitica` no reescribe esas consultas | [Regla 5 de `CLAUDE.md`](../CLAUDE.md) · [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo) |
| **Cada fuente declara su procedencia** | `fuentes[]` con `REAL`, `SIMULADA` o `SIN_DATOS`. `cifra_parcial` es `true` en cuanto **alguna** fuente no es `REAL`. El letrero de datos simulados de la interfaz se genera desde `fuentes[]`, no es fijo. `AVANCE_FISICO` cubre alcance y ejecutado: no hay fuente aparte para el alcance | [ADR-017](adr/20261015-fuentes-simuladas-analitica.md), reglas 2 y 3 · HDU-006 esc. 6 y 14 |
| **Ejercido real y simulado viajan separados** | `ejercido` es **solo real** y es el que entra en `consumido`; `ejercido_simulado` va aparte, `null` si ninguna fuente de ejercido de la fila es `SIMULADA`. La interfaz pinta el real en su celda y lo simulado en su propia columna marcada | ADR-017, regla 1 · HDU-006 esc. 15 |
| **Sin avance, `null`, no cero** | `avance_fisico.porcentaje` y `desviacion.importe` son nulables, con `estado: SIN_AVANCE_MEDIDO` | [Regla 12 de `CLAUDE.md`](../CLAUDE.md) · [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo) · HDU-006 esc. 9 |
| **La desviación con algo simulado es ilustrativa, y no alerta** | `desviacion` se calcula con `ejercido + ejercido_simulado` y lleva `ilustrativa: true` si alguna entrada es `SIMULADA`. Con desviación ilustrativa `alerta` es `false`, y `GET /semaforo/alertas` la excluye | ADR-017, regla 3 · HDU-006 esc. 11 |
| **Tres colores y un estado sin color** | `estado` es `VERDE`, `AMARILLO` o `ROJO` (`PA-18`, resuelta el 2026-10-17), o `SIN_AVANCE_MEDIDO`, que no es un color: sin avance no hay juicio. Corte **(asumido, sin bloqueo)**: `VERDE` con desviación ≤ 0, `AMARILLO` con desviación positiva y relativa ≤ `umbral_alerta_pct`, `ROJO` por encima; sin umbral en la obra, toda desviación positiva es `ROJO`. `alerta` es `true` con `ROJO` y desviación no ilustrativa | PRD F7.3 · `PA-18` · HDU-006 esc. 2, 3 y 16 |

En la fase 1 el puerto de [ADR-017](adr/20261015-fuentes-simuladas-analitica.md) tiene dos adaptadores: `SIMULADO`, admitido solo en `local`, `pruebas` y `demostracion`, y `VACIO`, que declara `SIN_DATOS` todas sus fuentes y es el único admitido en `produccion`. La aplicación no arranca en `produccion` con el simulado.

El desglose por ubicación se abre **por nivel y por área**, y se consulta sin ser el nivel de control. Los movimientos de una partida traen cantidad, unidad, importe y, en un `AJUSTE`, su motivo. La parte de nómina de HDU-006 esc. 7 es de la fase 2. Un usuario sin el rol recibe `403` sin importes (HDU-006 esc. 12): en el MVP no hay permiso por obra.

---

## 5. Endpoints de la fase 2

**Solo listados, sin esquema.** Las rutas son **las que fijan los tickets de la fase 2** (TKT-042…TKT-069), que son la referencia canónica mientras no tengan esquema: el ticket que implementa cada una la añade al borrador en el mismo PR, con la misma prueba de contrato de TKT-061. Siguen las convenciones de §2 sin excepción.

| Módulo | Recurso | Operaciones | Ticket |
|---|---|---|---|
| `personal` | Roles de oficio | `GET /roles-oficio` | TKT-043 |
| `personal` | Empleados | `POST /empleados` · `PATCH /empleados/{id}` · `DELETE /empleados/{id}` (solo sin historial; con historial, `409` `CONFLICTO` y la acción de dar de baja) · `POST /empleados/{id}/baja` | TKT-043 |
| `personal` | Cuadrillas | `POST /cuadrillas` · `GET /cuadrillas?obra_id=…&activa=true` · `POST /cuadrillas/{id}/asignaciones` · `POST /empleados/{id}/cambio-cuadrilla` · `POST /cuadrillas/{id}/baja` | TKT-044 |
| `personal` | Créditos | `POST /empleados/{id}/creditos` · `POST /creditos/{id}/suspension`, `/reactivacion`. Ninguna ruta acepta `saldo` | TKT-045 |
| `avance` | Etapas de destajo | `GET`, `POST /obras/{obra_id}/etapas-destajo` · `PATCH /etapas-destajo/{id}` | TKT-046 |
| `avance` | Alcance de destajo | `POST /obras/{obra_id}/alcances-destajo/precarga` · `POST /alcances-destajo/{id}/correccion` | TKT-047 |
| `avance` | Avances: captura y validación | `POST /avances` · `POST /avances/{id}/validacion`, `/rechazo`, `/correccion`. La `semana` del avance la deriva el servidor: es el **jueves de corte** de la semana de destajo, de jueves a miércoles (`PA-19`, resuelta el 2026-10-17) | TKT-047 |
| `avance` | Pagos de destajo | `POST /pagos-destajo` · `POST /pagos-destajo/{id}/cancelacion`. Se paga sobre los m² **reales** validados, y cada pago retiene sobre el bruto la retención y el **fondo de garantía**, dos importes que la respuesta devuelve aparte (`retencion`, `fondo_garantia`) con los porcentajes de la obra (`PA-21`, resuelta el 2026-10-17). La **liberación** del fondo es v1.1 (`RN-12`) y no tiene ruta | TKT-047 |
| `avance` | Desviación de volumen | `GET /obras/{obra_id}/desviacion-volumen?agrupar_por=nivel\|cuadrilla` | TKT-048 |
| `personal` | Semana y jornadas | `POST /semanas-nomina` (apertura) · `POST /jornadas` · `PATCH /jornadas/{id}` · `GET /jornadas` | TKT-055 |
| `personal` | Nómina semanal | `POST /semanas-nomina/{id}/calculo`. Semana laboral de **6 días**, parámetro y no constante; si el bruto no alcanza, los descuentos se aplican por antigüedad del adeudo (`PA-22`, resuelta el 2026-10-17). Un conflicto de modalidad de `RN-22` bloquea **solo a la cuadrilla** afectada: la nómina del resto se calcula (`PA-20`, resuelta el 2026-10-17) | TKT-050 |
| `personal` | Pagos, cierre y pago de la semana | `POST /semanas-nomina/{id}/pagos` · `GET /empleados/{id}/pagos-nomina?semana_id=…` (consulta inversa) · `POST /semanas-nomina/{id}/cierre` · `POST /semanas-nomina/{id}/pago`, que pasa la semana a `PAGADA` y es del rol `ADMINISTRACION` (`PA-22`, resuelta el 2026-10-17) | TKT-051 |
| `personal` | Modalidad de pago | `GET /obras/{obra_id}/modalidades-pago?semana=…`. Cambiar de modalidad no es una ruta: es cancelar lo existente y reclamar la otra | TKT-053 |
| `personal` | Imputación entre obras | **Sin ruta.** La calcula TKT-050 y la lee el adaptador real por la interfaz publicada `nomina_imputada(obra_id)` | TKT-056 |
| `avance`, `almacen` | Sincronización diferida idempotente | **Sin ruta propia.** `POST /avances` y `POST /entradas-almacen` aceptan `id` —UUID generado por el cliente al capturar— y `capturado_en`; cualquier otra ruta responde `422` si los recibe. Reenviar el mismo `id` responde `200` con la representación actual del recurso, sin duplicar; un rechazo vuelve con el contrato de error | TKT-064 |
| `almacen` | Entrada diferible | La cola del cliente la envía a `POST /entradas-almacen`, el mismo caso de uso que la captura en línea | TKT-068 |
| `avance`, `almacen`, `presupuesto` | Adjuntos | `POST /avances/{id}/adjuntos` · `POST /entradas-almacen/{id}/adjuntos` (remisión) · `POST /obras/{obra_id}/documentos` · `GET /avances/{id}/adjuntos` · `GET /entradas-almacen/{id}/adjuntos` | TKT-066 |
| `archivos` | Anulación | `POST /archivos/{id}/anulacion` con motivo obligatorio. **Nunca `DELETE`** (invariante 24) | TKT-066 |
| `presupuesto` | Expediente de obra | `GET /obras/{obra_id}/expediente` | TKT-066 |

El armazón del cliente sin conexión (TKT-063), el componente de subida y galería (TKT-065), las pantallas de campo con los adjuntos de la medición (TKT-048), la interfaz del expediente y de la remisión (TKT-067) y el adaptador real de ADR-017 (TKT-069) no añaden rutas: consumen las de esta tabla.

**La sincronización diferida no tiene ruta propia.** Cada elemento de la cola es una petición a la ruta de su caso de uso, con el identificador que el cliente generó al capturar. Una ruta central de sincronización necesitaría un módulo con derecho a escribir a la vez en `avance` y en `almacen`, y ese módulo no existe ni hace falta. La idempotencia es la clave primaria. El orden FIFO y la detención en el primer conflicto son del cliente (TKT-063), que es quien tiene la cola. Así lo encolado entra por los mismos casos de uso que la captura en línea ([ADR-015](adr/20260919-captura-diferida-sin-conexion.md)) y responde con el mismo contrato de error. **El cliente no evalúa ninguna regla**: lo encolado puede volver rechazado.

---

## 6. Cómo lo usa la IA

El borrador es un artefacto pensado para agentes antes que para personas: un agente que implementa un ticket necesita saber qué aceptar y qué rechazar con más precisión que la que da una historia en Gherkin, y menos contexto del que daría leer los cinco documentos de especificación enteros. Lo usa en tres momentos, dentro del ciclo de [convenciones §12](convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo).

### 6.1. Como contexto al implementar

El agente que toma un ticket de endpoint recibe, además de `CLAUDE.md` y la historia, **las operaciones del borrador cuyo `x-tickets` incluye ese ticket**. Las extensiones están ahí para eso:

| Extensión | Qué le dice al agente |
|---|---|
| `x-tickets` | Qué operaciones le tocan y, por exclusión, cuáles no: los *non-goals* del ticket en forma verificable |
| `x-roles` | La comprobación de permiso que va en `api/`. El test de TKT-006 que recorre el enrutador la contrasta |
| `x-reglas` | Qué funciones de `dominio/` invoca el caso de uso y qué `regla` lleva el `409` |
| `x-escenarios` | Qué tests tiene que escribir, con el nombre que exige el verificador de escenarios: `test_hdu002_esc04_…` |

Las descripciones de cada operación enumeran sus rechazos con el código y el `codigo` o la `regla` de cada uno. Es deliberado: el agente que lee *"sin motivo → `422` (esc. 6)"* escribe ese test; el que solo lee *"autoriza o rechaza una solicitud"* escribe el camino feliz ([regla 14 de `CLAUDE.md`](../CLAUDE.md)).

### 6.2. Para generar los tipos del cliente

Los tipos de TypeScript se generan con `openapi-typescript` **del OpenAPI que publica FastAPI**, no del borrador (TKT-008). La razón es que el cliente habla con el servidor que existe, no con el que se diseñó; generar del borrador produciría tipos correctos contra una API que quizá todavía no los respeta. Lo que garantiza que ambos digan lo mismo es la prueba de contrato del punto siguiente.

Antes de que exista el backend, el borrador **sí** sirve para generar tipos provisionales y montar las pantallas contra un servidor de pruebas. Es el uso que permite a TKT-024 o TKT-041 empezar en paralelo al endpoint, y se tira en cuanto el publicado existe.

Dos propiedades del borrador hacen que los tipos generados sirvan sin retoques: todo decimal es `string`, así que ninguno sale como `number` y el cliente queda obligado a pasar por `decimal.js`; y los `409` son un `oneOf` con discriminador en `tipo`, así que TypeScript estrecha `ErrorReglaNegocio | ErrorConflictoEstado | ErrorConcurrencia` con un `switch` y el componente de pantalla de bloqueo de TKT-008 no tiene que adivinar.

### 6.3. Como prueba de contrato

TKT-061 añade un test que carga el borrador y el OpenAPI publicado y, para cada ruta del borrador, comprueba:

- que la ruta y el método existen en el publicado, con el mismo `operationId`;
- que los códigos de estado declarados coinciden, salvo los `2xx` de las operaciones marcadas `x-sin-exito: true` —solo `cerrar_orden_compra`, que nunca responde con éxito—;
- que los cuerpos de error de `401`, `403`, `409` y `422` referencian los esquemas comunes y no la forma por omisión de FastAPI;
- que ningún campo decimal del publicado es `number`.

Falla el pipeline si algo diverge, y **la divergencia se resuelve a favor del borrador**: se corrige el código, o el borrador cambia en el mismo PR. **No compara los esquemas de éxito campo a campo**: el publicado los genera Pydantic con detalles —títulos, `anyOf` con `null`— que el borrador no reproduce, y exigir igualdad literal convertiría la prueba en ruido. Lo que compara es lo que, si diverge, rompe a un cliente o a un escenario.

El borrador se valida además en cada cambio con `openapi-spec-validator`, como cualquier otro documento del repositorio que tiene sintaxis propia.

---

## 7. Lo que este documento asume

Todo lo marcado **(asumido)** en el borrador, reunido para escalar. Ninguno es una regla de negocio nueva: son decisiones de diseño de la API que el PRD no fija.

| # | Supuesto | Dónde | Qué cambia si es falso |
|---|---|---|---|
| 1 | El `codigo` y el `tipo_contrato` de una obra no se modifican con `PATCH` | `actualizar_obra` | Se añaden al esquema `ObraCambios` |
| 2 | Una obra `SUSPENDIDA` puede volver a `ACTIVA` | `reactivar_obra` | Se elimina la ruta |
| 3 | Un Excel corregido es una importación nueva, no un reintento | `iniciar_analisis_importacion` | Haría falta adjuntar un archivo nuevo a una importación existente |
| 4 | El disponible sin línea base o sin tope responde `409`, igual que la requisición | `obtener_disponible` | Respondería `200` con `presupuestado` nulo |
| 5 | Quien no es el solicitante y cancela una requisición recibe `403` con motivo `NO_ES_SOLICITANTE` | `cancelar_requisicion` | Se responde `ROL_INSUFICIENTE` y `NO_ES_SOLICITANTE` sale del catálogo de `ErrorPermiso` |
| 6 | Quien solicitó una autorización puede ver su detalle | `obtener_solicitud_autorizacion` | `x-roles` se reduce a DG |
| 7 | La fecha comprometida puede fijarse por renglón al emitir la orden | `emitir_orden_compra` | Una sola fecha por orden |
| 8 | El faltante se reprograma también sobre órdenes `ABIERTA` | `reprogramar_faltante` | Se restringe a `PARCIAL` con un `409` |
| 9 | La desviación relativa que se compara con `obra.umbral_alerta_pct` es `desviación ÷ (presupuestado × avance)` | `Desviacion` | Cambia la fórmula, no el esquema |
| 10 | Las marcas de tiempo se responden en la zona `America/Mexico_City` | `FechaHora` | Se responden en UTC; el cliente convierte |
| 11 | El corte de color del semáforo: `VERDE` con desviación ≤ 0, `AMARILLO` hasta `obra.umbral_alerta_pct`, `ROJO` por encima, y sin umbral toda desviación positiva es `ROJO` | `FilaSemaforo.estado` | Cambian el corte y la alerta, no el esquema |
| 12 | Una solicitud `EXCEDE_ORDENADO` cubre un solo renglón; una remisión que excede en varios pide una por renglón | `crear_solicitud_autorizacion` | `SolicitudExcedenteNueva` vuelve a aceptar varios renglones y la solicitud guarda una lista |
| 13 | Que una solicitud ya se consumió se lee del `entrada_renglon` que la cita, sin columna nueva en `solicitud_autorizacion` | `SolicitudAutorizacion.consumida_por_entrada_id` | Se guarda la marca en la solicitud |
| 14 | `REINTENTAR` de una `CONCURRENCIA` no se filtra por los roles de quien llama: repite la operación ya autorizada por `api/` | `ErrorConcurrencia` | Se filtra como el resto de las acciones; mientras no exista la sesión de TKT-006, todo vencimiento llegaría sin acciones |

Las tres preguntas que dejaban provisional parte del borrador —`PA-16` (excedente de recepción), `PA-17` (corrección sobre orden `CERRADA`) y `PA-18` (colores del semáforo)— se resolvieron el 2026-10-17 ([PRD §10](01-descripcion-producto.md#10-supuestos-y-preguntas-abiertas)), y lo que decían ya es contrato en las operaciones de §4.4, §4.6 y §4.8.
