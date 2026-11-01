# Spec · TKT-057 · Endurecimiento de la frontera HTTP

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

TKT-006 dejó la autenticación en pie, pero declaró fuera de su alcance cuatro defensas de la frontera HTTP. Hoy el sistema tiene estas carencias, comprobadas en el código y no supuestas:

- **El token CSRF se emite pero nadie lo verifica.** `GET /api/v1/sesion/csrf` fija la cookie `cimenta_csrf` y devuelve el mismo valor en el cuerpo, pero ninguna ruta que muta estado compara la cabecera `X-CSRF-Token` con la cookie, y tampoco se rota al iniciar ni al cerrar sesión. El cliente de TKT-008 ya envía la cabecera en todo método que muta, de modo que la verificación puede activarse sin romperlo. Un usuario de Dirección General con sesión abierta sigue pudiendo autorizar un sobregiro desde un sitio de terceros con un solo clic (`RNF-05`).
- **No existe límite de intentos de acceso.** La tabla `intento_acceso` y la columna `usuario.bloqueado_hasta` existen, y `abrir_sesion` ya asienta cada intento, pero nada lee el bloqueo ni cuenta fallos, y el contrato `429` `LIMITE_INTENTOS` está construido sin ningún caso de uso que lo lance. Como Argon2 encarece cada intento para el servidor también, el inicio de sesión es hoy el punto más barato de saturar de todo el sistema (`RNF-04`, `RNF-03`).
- **Las respuestas no llevan cabeceras de seguridad.** Solo existe el middleware de correlación (`RNF-05`, `RNF-06`).
- **La configuración se lee a mano de `os.environ`.** La aplicación arranca sin credenciales de base de datos, porque la prueba TC-75 de TKT-005, reescrita en TKT-006, exige exactamente eso. `RNF-07` pide lo contrario: un despliegue al que le falta un secreto tiene que no arrancar.

Este ticket no pertenece a ninguna historia de usuario: sirve a todas. Lo que entrega es la capacidad de no perder lo que las reglas de negocio protegen.

## Historia de usuario

Ticket de fundación, sin historia HDU asociada (como TKT-005 y TKT-006). Lo usa quien desarrolla el proyecto, persona o agente. Quien lo recibe al final es cualquier rol del PRD §4:

**Como** persona que opera CIMENTA con sesión abierta o intentando abrirla
**quiero** que la frontera HTTP rechace las peticiones que no vienen de la aplicación, limite quien adivina contraseñas y no arranque sin sus secretos
**para** que una autorización de gasto o un acceso a la obra no puedan provocarlos un sitio de terceros ni un ataque de fuerza bruta.

## Alcance

El Must lo validó la persona dueña el 2026-10-30.

| Nivel | Ítem |
|---|---|
| **Must** | **M1** Bloqueo temporal por cuenta (correo): tras 5 fallos en 15 minutos, la cuenta se bloquea 15 minutos, el bloqueo caduca solo y la respuesta es idéntica exista o no la cuenta (`RNF-04`) |
| | **M2** Límite por origen: 20 intentos fallidos en 15 minutos desde un mismo origen bloquean ese origen (`RNF-04`) |
| | **M3** Cada intento de acceso —exitoso, fallido, a una cuenta inexistente o rechazado por bloqueo— queda asentado en `intento_acceso` |
| | **M4** Token de doble envío verificado en **todo** método que muta estado (`POST`, `PUT`, `PATCH`, `DELETE`): `403` `PERMISO` con motivo `ORIGEN_NO_VERIFICADO`, comparación en tiempo constante, y rotación del token al iniciar y al cerrar sesión (`RNF-05`) |
| | **M5** `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` y `Cache-Control` en todas las respuestas; la política admite el origen del almacén de objetos y ningún otro origen externo (`RNF-05`, `RNF-06`, regla 4 de ADR-016) |
| | **M6** Configuración con `pydantic-settings`: la contraseña del rol de aplicación (`CIMENTA_DB_CONTRASENA_APLICACION`) es obligatoria y sin valor por omisión; la aplicación no arranca si falta; las de migración y lectura las exige quien las usa (el comando de migración y las herramientas), no el servidor; `.env.example` lleva las claves de las tres sin valor (`RNF-07`, `RNF-09`) |
| | **M7** Pruebas de `RNF-04`, `RNF-05` y `RNF-07` de [stack §6.6](../../../docs/06-stack-tecnologico.md#66-qué-se-comprueba-solo) que fallan el pipeline en el trabajo `backend` |
| | **M8** Consecuencia documental: el borrador OpenAPI, la especificación del API, el stack y la guía de arranque local reflejan lo que cambia este ticket, en el mismo PR |
| **Should** | **S1** Una prueba que recorre el enrutador y falla si una ruta que muta no declara la verificación del token |
| | **S2** Los valores de bloqueo (5 fallos, 20 por origen, 15 minutos) se leen de la configuración, con esos valores por omisión |
| **Could** | Ninguno |
| **Won't** | Resto de la deuda que TKT-006 dejó señalada para este ticket (ver «Non-goals») · comprobación de `Origin` o `Referer` · segundo factor |

## Non-goals

- **No implementa segundo factor, recuperación de contraseña ni inicio de sesión federado**: siguen fuera del MVP.
- **No implementa permisos por obra**: el MVP autoriza por rol.
- **No valida archivos.** Tamaño, tipo leído de los bytes, nombre generado y `Content-Disposition` son de TKT-059, igual que la prueba de `RNF-06`. TKT-057 solo deja la política de contenido preparada para el origen del almacén.
- **No cubre la deuda de TKT-006 que el ticket no lista**, por decisión de la persona dueña: topes de tamaño de cuerpo y de longitud de contraseña, suelo mínimo y re-derivación de los costes de Argon2, qué hacer con `/docs` y `/openapi.json` en producción (y el Swagger servido desde un CDN sin SRI), el `DENEGAR` sin límite de un usuario autenticado y la conexión retenida durante Argon2. Va a «Tickets futuros sugeridos» de [`_index.md`](_index.md). `Cache-Control` sí entra: es una cabecera más.
- **No comprueba `Origin` ni `Referer`.** El comentario de `frontend/vite.config.ts` lo insinúa, pero `RNF-05` se cumple con el doble envío y la persona dueña no lo pidió.
- **No monta `slowapi`.** El límite por origen se cuenta con lo que ya asienta `intento_acceso`: es persistente, sirve con varios procesos y no añade dependencia.
- **No toca ninguna pantalla del frontend.** Solo el guion `frontend/scripts/tipos.ts`, que hoy construye la aplicación sin secretos para exportar el OpenAPI y pasa a darle una contraseña efímera (decisión de la persona dueña, 2026-10-30). La pantalla de inicio de sesión ya contempla `429` y `403` `ORIGEN_NO_VERIFICADO` ([wireframe 1](../../../docs/08-wireframes.md), estados de rechazo); TKT-008 la construyó.
- **No agrega agregación de errores, imagen de producción ni respaldo**: son de TKT-058.
- **No añade un secreto «semilla del token CSRF».** El token es de doble envío, sin firma y sin estado; no hay semilla que guardar. El [stack §6.3](../../../docs/06-stack-tecnologico.md#63-archivos-y-secretos) la menciona y se corrige (M8).

## Reglas de negocio implicadas

Ninguna `RN-xx` se implementa: el ticket aplica requisitos no funcionales, que fijan el comportamiento de la frontera, no una regla del negocio.

| Requisito | Qué exige | Dónde está |
|---|---|---|
| `RNF-04` | Intentos de acceso limitados por cuenta y por origen, con bloqueo temporal y registro del intento | PRD §9 — `docs/01-descripcion-producto.md` |
| `RNF-05` | Toda operación que muta estado exige prueba de que la intención viene de la aplicación | PRD §9 |
| `RNF-06` | Los archivos se sirven desde un origen distinto al de la aplicación; aquí solo la parte de la política de contenido | PRD §9 |
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen | PRD §9 |
| `RNF-03` | Argon2 encarece cada intento; es la razón del límite. No se modifica | PRD §9 |
| `RNF-13` | Los rechazos anónimos van al registro técnico; no se modifica | PRD §9 |

## Invariantes que deben sobrevivir al cambio

El ticket modifica algo que ya funciona (inicio de sesión, cierre de sesión, arranque), así que cada invariante genera un criterio de regresión `[M]`.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 20 del modelo de datos | El rol de aplicación tiene `INSERT` y `SELECT` sobre `intento_acceso`, no `UPDATE` ni `DELETE`: el recuento y el bloqueo nunca se hacen editando ni borrando filas | `CA-R1` |
| 10 del modelo de datos | `bitacora.usuario_id` es `NOT NULL`: el rechazo anónimo no llega a la bitácora; el rechazo con usuario sí | `CA-R2` |
| 21 del modelo de datos | El rol de solo lectura no ve `sesion` ni `password_hash` | `CA-R3` |
| Regla 9 de `CLAUDE.md` | La cookie `cimenta_sesion` lleva un identificador opaco, con las banderas de TKT-006 | `CA-R4` |
| Regla 11 de `CLAUDE.md` | Las rutas se declaran `def`, nunca `async def` | `CA-R5` |
| Lista cerrada de TKT-006 | Solo `GET /sesion/csrf` y `POST /sesion` no exigen sesión | `CA-R6` |
| Contrato de error | Los siete tipos de error conservan su forma; `401` de credenciales inválidas no cambia | `CA-R7` |
| Arranque de TKT-005 | `GET /api/v1/sesion/csrf` y las respuestas de error siguen funcionando cuando la configuración es válida | `CA-R8` |

## Criterios de aceptación

Gherkin, en español. «El origen» es la dirección de red del cliente que registra `intento_acceso.origen_ip`. Los valores 5, 20 y 15 minutos son los confirmados por la persona dueña el 2026-10-30 y siguen marcados `(asumido)` hasta que Dirección General los ajuste ([PA-T2](#preguntas-abiertas-y-supuestos)).

### Límite por cuenta

### CA-1 `[M]` · Cinco fallos, el sexto intento bloqueado · `RNF-04`

```gherkin
Escenario: tras cinco fallos de contraseña, el sexto intento responde bloqueado
  Dado un usuario activo "ana@cimenta.test" con su contraseña
  Y un token CSRF válido en cada petición
  Cuando se hacen cinco intentos de inicio de sesión con contraseña incorrecta en menos de 15 minutos
  Entonces cada uno de los cinco responde 401 con tipo "SESION" y código "CREDENCIALES_INVALIDAS"
  Y el sexto intento responde 429 con tipo "LIMITE_INTENTOS"
  Y la respuesta lleva "reintentar_en_s" mayor que 0 y no mayor que 900
  Y la cabecera "Retry-After" es igual a "reintentar_en_s"
  Y la respuesta lleva "correlacion_id"
  Y "usuario.bloqueado_hasta" de Ana es la hora del quinto fallo más 15 minutos
```

### CA-2 `[M]` · Rechazo · El bloqueo gana a la contraseña correcta · `RNF-04`

```gherkin
Escenario: durante el bloqueo, la contraseña correcta tampoco abre sesión
  Dado que la cuenta "ana@cimenta.test" está bloqueada por cinco fallos
  Cuando se hace un intento de inicio de sesión con la contraseña correcta
  Entonces la respuesta es 429 con tipo "LIMITE_INTENTOS" y "reintentar_en_s" mayor que 0
  Y no se crea ninguna fila nueva en "sesion"
  Y la respuesta no lleva la cookie "cimenta_sesion"
```

### CA-3 `[M]` · El bloqueo caduca solo y no se prolonga · `RNF-04`

```gherkin
Escenario: el bloqueo vence a los 15 minutos aunque se siga intentando
  Dado que la cuenta "ana@cimenta.test" se bloqueó a las 10:00 por cinco fallos
  Y que a las 10:05 y a las 10:10 hubo otros dos intentos, ambos respondidos 429
  Cuando a las 10:15:01 se inicia sesión con la contraseña correcta
  Entonces la respuesta es 200 y se abre la sesión
  Y no hizo falta ninguna acción de una persona administradora
```

```gherkin
Escenario: los intentos rechazados por bloqueo no alargan el bloqueo
  Dado que la cuenta "ana@cimenta.test" se bloqueó a las 10:00
  Cuando se hacen veinte intentos más durante el bloqueo
  Entonces "usuario.bloqueado_hasta" sigue siendo las 10:15
  Y "reintentar_en_s" de cada respuesta 429 es el tiempo que falta hasta las 10:15
```

### CA-4 `[M]` · Rechazo · El bloqueo no revela qué cuentas existen · `RNF-04`

```gherkin
Escenario: un correo inexistente se bloquea igual que uno existente
  Dado que el correo "nadie@cimenta.test" no corresponde a ningún usuario
  Cuando se hacen cinco intentos de inicio de sesión con ese correo
  Entonces cada uno responde 401 "CREDENCIALES_INVALIDAS"
  Y el sexto responde 429 "LIMITE_INTENTOS"
  Y el cuerpo del 429 tiene exactamente los mismos campos que el de una cuenta existente
```

### CA-5 `[M]` · Qué cuenta como fallo · `RNF-04`

```gherkin
Escenario: un inicio correcto reinicia el recuento
  Dado cuatro fallos recientes de "ana@cimenta.test"
  Cuando Ana inicia sesión con su contraseña correcta
  Y después falla una vez más
  Entonces ese fallo es el primero del recuento y la cuenta no está bloqueada
```

```gherkin
Escenario: una petición mal formada no cuenta como intento
  Dado una petición de inicio de sesión sin el campo "contrasena"
  Cuando el servidor la rechaza con 422
  Entonces no se asienta fila en "intento_acceso"
  Y el recuento de fallos de ninguna cuenta ni origen cambia
```

### Límite por origen

### CA-6 `[M]` · Veinte fallos bloquean al origen · `RNF-04`

```gherkin
Escenario: un origen que adivina contraseñas de cuentas distintas queda bloqueado
  Dado el origen 203.0.113.7
  Cuando en 15 minutos hace 20 intentos fallidos repartidos entre cuentas distintas, sin llegar a 5 en ninguna
  Entonces el intento número 21 de ese origen responde 429 "LIMITE_INTENTOS" aunque use credenciales correctas
  Y el cuerpo es igual en forma al del bloqueo por cuenta
```

### CA-7 `[M]` · Rechazo · El bloqueo de un origen no alcanza a otros · `RNF-04`

```gherkin
Escenario: otro origen sigue pudiendo iniciar sesión
  Dado que el origen 203.0.113.7 está bloqueado
  Cuando Ana inicia sesión con su contraseña correcta desde el origen 198.51.100.4
  Entonces la respuesta es 200

Escenario: el bloqueo del origen caduca solo
  Dado que el origen 203.0.113.7 quedó bloqueado a las 10:00
  Cuando a las 10:15:01 hace un intento con credenciales correctas
  Entonces la respuesta es 200
```

### CA-8 `[M]` · Cada intento queda asentado · `RNF-04`

```gherkin
Escenario: el registro del intento no depende del resultado
  Cuando se hacen cuatro intentos: uno exitoso, uno con contraseña errónea, uno con un correo inexistente y uno rechazado por bloqueo
  Entonces "intento_acceso" tiene cuatro filas nuevas
  Y cada una lleva el correo en minúsculas, el origen y "exitoso" verdadero solo en el primero
  Y las filas del correo inexistente y del rechazo por bloqueo existen aunque la respuesta sea 401 o 429
```

```gherkin
Escenario: el recuento nunca se hace editando filas
  Dado el rol de aplicación de la base
  Cuando intenta UPDATE o DELETE sobre "intento_acceso"
  Entonces el motor lo rechaza por falta de privilegio
```

### Verificación del token CSRF

### CA-9 `[M]` · Rechazo · Mutar sin prueba de origen · `RNF-05`

```gherkin
Esquema del escenario: toda mutación sin par de token válido se rechaza
  Dado un usuario con sesión válida
  Cuando envía <método> <ruta> con cookie "cimenta_csrf" <cookie> y cabecera "X-CSRF-Token" <cabecera>
  Entonces la respuesta es 403 con tipo "PERMISO" y motivo "ORIGEN_NO_VERIFICADO"
  Y "roles_requeridos" es una lista vacía
  Y la respuesta no lleva cifras ni datos del recurso
  Y no se ejecutó la operación: ninguna fila cambió en ninguna tabla de negocio

  Ejemplos:
    | método | ruta                            | cookie  | cabecera |
    | POST   | /api/v1/sesion/cierre           | ausente | ausente  |
    | POST   | /api/v1/sesion/cierre           | presente| ausente  |
    | POST   | /api/v1/sesion/cierre           | ausente | presente |
    | POST   | /api/v1/sesion/cierre           | "aaa"   | "bbb"    |
```

El escenario cubre cada uno de los cuatro métodos que mutan: la prueba recorre el enrutador y, para cada operación `POST`, `PUT`, `PATCH` o `DELETE` que existe, comprueba las mismas cuatro combinaciones (ver `CA-18`).

### CA-10 `[M]` · Con un par válido la operación se ejecuta · `RNF-05`

```gherkin
Escenario: cookie y cabecera coinciden
  Dado un usuario con sesión válida y el token obtenido con GET /api/v1/sesion/csrf
  Cuando envía POST /api/v1/sesion/cierre con la cookie "cimenta_csrf" y la cabecera "X-CSRF-Token" con el mismo valor
  Entonces la respuesta es 204 y "sesion.revocada_en" queda escrito
```

### CA-11 `[M]` · Rechazo con sesión y rechazo anónimo · `RNF-05`, `RNF-13`

```gherkin
Escenario: sin sesión, la sesión se evalúa primero
  Dado una petición sin cookie "cimenta_sesion" y sin token CSRF
  Cuando llama a POST /api/v1/sesion/cierre
  Entonces la respuesta es 401 con tipo "SESION"
  Y no se asienta nada en "bitacora"
```

```gherkin
Escenario: con sesión válida, el rechazo se atribuye al usuario
  Dado un usuario autenticado "ana@cimenta.test" con sesión válida
  Cuando llama a una ruta que muta sin token CSRF
  Entonces la respuesta es 403 "ORIGEN_NO_VERIFICADO"
  Y la bitácora tiene un asiento "DENEGAR" con el usuario de Ana, escrito en una transacción propia
  Y el asiento no contiene el token
```

```gherkin
Escenario: el rechazo anónimo del inicio de sesión no llega a la bitácora
  Dado una petición POST /api/v1/sesion sin token CSRF y con el correo "ana@cimenta.test" en el cuerpo
  Cuando el servidor la rechaza
  Entonces la respuesta es 403 "ORIGEN_NO_VERIFICADO"
  Y "intento_acceso" tiene una fila nueva con "exitoso" falso
  Y el registro técnico tiene una línea con el "correlacion_id"
  Y "bitacora" no tiene filas nuevas
  Y no se verificó ninguna contraseña
```

El rechazo CSRF en cualquier otra ruta sin sesión no existe: la sesión se evalúa primero y responde `401`. Si el cuerpo de `POST /sesion` no permite leer un correo, el rechazo queda solo en el registro técnico `(asumido)`.

### CA-12 `[M]` · Rotación del token · `RNF-05`

```gherkin
Escenario: iniciar sesión entrega un token nuevo
  Dado un cliente con el token T1 obtenido con GET /api/v1/sesion/csrf
  Cuando inicia sesión con éxito enviando T1
  Entonces la respuesta fija la cookie "cimenta_csrf" con un valor T2 distinto de T1
  Y la cookie conserva las banderas de la emitida en GET /sesion/csrf (sin HttpOnly)
  Y una petición posterior con la cookie T2 y la cabecera T1 es rechazada 403 "ORIGEN_NO_VERIFICADO"

Escenario: cerrar sesión entrega un token nuevo
  Dado un usuario con sesión y el token T2
  Cuando cierra sesión enviando T2
  Entonces la respuesta 204 fija la cookie "cimenta_csrf" con un valor T3 distinto de T2
```

El borrador OpenAPI no documenta hoy esa cabecera `Set-Cookie` en las respuestas `200` de `iniciar_sesion` ni `204` de `cerrar_sesion`: se añade en el mismo PR (`M8`).

### Cabeceras

### CA-13 `[M]` · Cabeceras en toda respuesta · `RNF-05`, `RNF-06`

```gherkin
Esquema del escenario: toda respuesta lleva las cabeceras, también los rechazos
  Cuando se hace <petición>
  Entonces la respuesta lleva "Strict-Transport-Security: max-age=31536000"
  Y lleva "X-Content-Type-Options: nosniff"
  Y lleva "Referrer-Policy"
  Y lleva "Content-Security-Policy"
  Y la ruta "/api/" lleva "Cache-Control: no-store"

  Ejemplos:
    | petición                                          |
    | GET /api/v1/sesion/csrf (200)                     |
    | POST /api/v1/sesion con credenciales falsas (401) |
    | POST /api/v1/sesion sin token (403)               |
    | POST /api/v1/sesion mal formado (422)             |
    | GET /api/v1/ruta-inexistente (404)                |
    | una excepción no controlada (500)                 |
    | un bloqueo (429)                                  |
```

La directiva `Strict-Transport-Security` es `max-age=31536000`, sin `includeSubDomains` ni `preload`, por decisión de la persona dueña. Los valores de `Referrer-Policy`, `Cache-Control` y de las demás directivas de la política de contenido son `(asumido)` y los fija el diseño (`PA-T4`).

### CA-14 `[M]` · Rechazo · La política de contenido no admite orígenes ajenos · `RNF-06`

```gherkin
Escenario: el origen del almacén es el único origen externo admitido
  Dado la variable del origen del almacén configurada como "https://almacen.cimenta.test"
  Cuando se lee "Content-Security-Policy" de cualquier respuesta
  Entonces "img-src", "media-src" y "connect-src" admiten "'self'" y "https://almacen.cimenta.test" y ningún otro origen
  Y ninguna directiva de la política contiene "*" ni "unsafe-inline" ni "unsafe-eval"
  Y "object-src" es "'none'"

Escenario: sin almacén configurado no hay origen externo
  Dado la variable del origen del almacén sin configurar
  Cuando se lee "Content-Security-Policy"
  Entonces ninguna directiva admite un origen distinto de "'self'"
```

`connect-src` lleva el origen del almacén porque el navegador sube directo con una URL prefirmada (regla 1 de ADR-016); es una ampliación respecto al texto del ticket, que nombra `img-src` y `media-src`, confirmada por la persona dueña. La variable es opcional hasta que TKT-059 monte el almacén.

### Configuración y secretos

### CA-15 `[M]` · La aplicación no arranca sin su secreto · `RNF-07`

```gherkin
Escenario: falta la contraseña del rol de aplicación
  Dado el entorno sin "CIMENTA_DB_CONTRASENA_APLICACION"
  Cuando se crea la aplicación
  Entonces falla al arrancar con un error que nombra "CIMENTA_DB_CONTRASENA_APLICACION"
  Y el mensaje de error no contiene el valor de ninguna contraseña
  Y no se abre ninguna conexión a la base de datos
```

```gherkin
Escenario: el servidor no necesita la credencial de migración
  Dado el entorno con "CIMENTA_DB_CONTRASENA_APLICACION" y sin "CIMENTA_DB_CONTRASENA_MIGRACION" ni "CIMENTA_DB_CONTRASENA_LECTURA"
  Cuando se crea la aplicación
  Entonces arranca
  Y ningún objeto de configuración de la aplicación contiene la contraseña de migración
```

```gherkin
Escenario: el comando de migración exige la suya
  Dado el entorno sin "CIMENTA_DB_CONTRASENA_MIGRACION"
  Cuando se ejecuta "alembic upgrade head"
  Entonces falla con un error que nombra "CIMENTA_DB_CONTRASENA_MIGRACION"
```

### CA-16 `[M]` · Una variable vacía no es un valor · `RNF-07`

```gherkin
Escenario: una contraseña definida pero vacía se trata como ausente
  Dado el entorno con "CIMENTA_DB_CONTRASENA_APLICACION" definida como cadena vacía
  Cuando se crea la aplicación
  Entonces falla al arrancar con el mismo error que si faltara
```

### CA-17 `[M]` · `.env.example` documenta sin revelar · `RNF-07`

```gherkin
Escenario: el archivo de ejemplo lista las claves de las tres contraseñas sin valores
  Dado el archivo ".env.example"
  Cuando se leen sus claves
  Entonces contiene "CIMENTA_DB_CONTRASENA_MIGRACION", "CIMENTA_DB_CONTRASENA_APLICACION" y "CIMENTA_DB_CONTRASENA_LECTURA"
  Y ninguna de las tres lleva valor
  Y no contiene ninguna cadena "solo-desarrollo-"
```

```gherkin
Escenario: el pipeline arranca con valores de prueba inyectados, no con los del archivo
  Dado el trabajo "humo" de "ci.yml"
  Cuando prepara el entorno
  Entonces las contraseñas se generan dentro del trabajo, no están en ningún archivo versionado y valen solo para esa ejecución
  Y la aplicación arranca
```

### Comprobación automática

### CA-18 `[S]` · El enrutador no deja mutaciones sin verificar · `RNF-05`

```gherkin
Escenario: una ruta nueva que muta sin verificación rompe el pipeline
  Dado el enrutador de la aplicación
  Cuando una prueba recorre todas sus operaciones POST, PUT, PATCH y DELETE
  Entonces para cada una comprueba las cuatro combinaciones de CA-9
  Y falla si alguna se ejecuta sin par válido
```

### CA-19 `[M]` · El pipeline falla ante la violación · `RNF-04`, `RNF-05`, `RNF-07`

```gherkin
Escenario: cada defensa tiene una prueba que se ve fallar
  Dado las pruebas de CA-1, CA-9 y CA-15
  Cuando se desactiva cada defensa por separado (sin límite de intentos, sin verificación, con valor por omisión)
  Entonces el trabajo "backend" termina en rojo
```

### Regresión

### CA-R1 `[M]` · Invariante 20 · `intento_acceso` solo se anexa

```gherkin
Escenario: el rol de aplicación conserva INSERT y SELECT y no gana UPDATE ni DELETE
  Dado el esquema creado con "alembic upgrade head"
  Cuando se consulta el privilegio del rol de aplicación sobre "intento_acceso"
  Entonces tiene "INSERT" y "SELECT"
  Y no tiene "UPDATE" ni "DELETE"
```

### CA-R2 `[M]` · Invariante 10 · La bitácora solo recibe rechazos con usuario

```gherkin
Escenario: ningún rechazo anónimo escribe en la bitácora
  Cuando se rechazan un CSRF ausente, unas credenciales erróneas y un bloqueo, todos sin sesión
  Entonces "bitacora" no tiene filas nuevas
```

### CA-R3 `[M]` · Invariante 21 · Lo que ve el rol de lectura no cambia

```gherkin
Escenario: el rol de solo lectura no gana columnas
  Cuando se consultan los privilegios del rol de solo lectura
  Entonces no ve "sesion" ni "usuario.password_hash"
  Y puede leer "usuario.bloqueado_hasta" tal como antes
```

### CA-R4 `[M]` · La cookie de sesión no cambia

```gherkin
Escenario: banderas de la cookie de sesión
  Cuando Ana inicia sesión con éxito
  Entonces "cimenta_sesion" es un identificador opaco, HttpOnly, Secure, SameSite=Lax
  Y "cimenta_csrf" no es HttpOnly
```

### CA-R5 `[M]` · Rutas `def`

```gherkin
Escenario: ninguna ruta ni dependencia nueva es corrutina
  Cuando una prueba recorre el enrutador
  Entonces ningún endpoint ni dependencia es "async def"
```

### CA-R6 `[M]` · Solo dos rutas sin sesión

```gherkin
Escenario: la lista cerrada de TKT-006 se mantiene
  Cuando una prueba recorre el enrutador
  Entonces las únicas rutas que no exigen sesión son "GET /api/v1/sesion/csrf" y "POST /api/v1/sesion"
```

### CA-R7 `[M]` · El contrato de error no cambia de forma

```gherkin
Escenario: credenciales inválidas siguen siendo 401 con su forma
  Cuando se inicia sesión con contraseña errónea sin llegar al límite
  Entonces la respuesta es 401 con tipo "SESION", código "CREDENCIALES_INVALIDAS" y "correlacion_id"
```

### CA-R8 `[M]` · Arranque y emisión del token intactos

```gherkin
Escenario: GET /sesion/csrf sin sesión y con configuración válida
  Dado la aplicación creada con la contraseña del rol de aplicación
  Cuando se llama a GET /api/v1/sesion/csrf sin sesión
  Entonces la respuesta es 200 con el token en el cuerpo y el mismo valor en la cookie "cimenta_csrf"
  Y el cliente de TKT-008 inicia y cierra sesión contra el servidor sin cambios (prueba de humo "npm run e2e")
```

La prueba TC-75 («la aplicación arranca sin `CIMENTA_DB_*`») exige lo contrario de `RNF-07` y **se reescribe** en este ticket, con la decisión de la persona dueña, igual que TKT-006 reescribió una de TKT-005. Las pruebas de TKT-006 que hoy envían el inicio y el cierre de sesión sin token pasan a enviarlo; las actualiza el rol tester, no quien escribe el código.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-006, archivado. TKT-063 depende de este ticket, no al revés |
| **N** | Describe el qué, no impone el cómo | Sí | Los criterios hablan de respuestas, filas y arranque. Dónde se cuenta el bloqueo y qué biblioteca lee la configuración se decide en el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con matiz | El valor llega como protección de todos los roles, sobre todo de Dirección General, cuya autorización de gasto era falsificable |
| **E** | Estimable sin investigar antes | Sí | El estado del código se verificó; no queda incertidumbre técnica relevante |
| **S** | Cabe en una sesión sin romper contexto | **Reserva** | Ocho Must (M1 a M8), una migración posible (`PA-T11`) y tests reescritos de TKT-005 y TKT-006. Talla M del ticket; el diseño puede proponer partir en dos entregas (límite de intentos y CSRF frente a cabeceras y configuración), como hizo TKT-006 |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada uno se traduce a un test con Docker; el reloj se controla en las pruebas de caducidad |

Una reserva, ningún fallo: pasa.

## Definition of Done

La de un ticket de fundación (`sdd/metodologia.md` §8).

- [ ] Los 18 criterios `[M]` y los 8 de regresión pasan; `CA-18` (`[S]`) pasa o se recorta vía `/sdd-escalar`
- [ ] Cada escenario tiene su test con el identificador en el nombre
- [ ] `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`, `lint-imports` y `verificar_float` en verde
- [ ] El trabajo `backend` de `ci.yml` falla si se desactiva el límite de intentos, la verificación CSRF o la validación de la configuración (`CA-19`)
- [ ] `docs/api/openapi.yaml`, `docs/07-especificacion-api.md`, `docs/06-stack-tecnologico.md` y `docs/arranque-local.md` actualizados en el mismo PR (`M8`)
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` sin problemas
- [ ] El PR señala a quien aprueba: cambia el contrato (`openapi.yaml`), reescribe TC-75, actualiza pruebas de TKT-006, cambia `.env.example` y el trabajo `humo`

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | El recuento y el bloqueo salen de `intento_acceso` por correo normalizado, exista o no el usuario; `usuario.bloqueado_hasta` se escribe además para las cuentas reales. Decisión de la persona dueña el 2026-10-30 | Si solo se usara `bloqueado_hasta`, un correo inexistente daría `401` y uno real `429`, y se revelarían las cuentas (lo prohíbe el borrador OpenAPI) | Confirmado |
| PA-T2 | 5 fallos por cuenta, 20 por origen, ventana y bloqueo de 15 minutos, bloqueo fijo (no escala), un inicio correcto reinicia el recuento, los `422` no cuentan. Propuesta de la persona que define aceptada por la persona dueña el 2026-10-30 como valor de partida | Son una propuesta técnica, no una exigencia del cliente; Dirección General puede pedir otros valores. Por eso `S2` los hace configurables | `(asumido)` — confirmado como punto de partida |
| PA-T3 | El quinto fallo responde `401` y el sexto `429`, incluso con la contraseña correcta (lectura literal de stack §6.6) | Si el quinto debiera responder `429`, cambian `CA-1` y la prueba de `RNF-04` | Confirmado |
| PA-T4 | Los valores de `Referrer-Policy`, `Cache-Control` y las directivas de la política de contenido distintas de `img-src`, `media-src`, `connect-src` y `object-src`. Una política con `'self'` rompe además `/docs` (Swagger, servido hoy desde un CDN): se deja así o se exime, y es parte de la deuda de `/docs` que queda fuera | El diseño los propone y la persona dueña los aprueba en el gate del diseño. Una política demasiado estricta rompe el Swagger o el cliente; demasiado laxa no protege | `(asumido)` — aprobado en el gate del diseño (`D-2`) |
| PA-T5 | El origen del cliente es `request.client.host` (como hoy). **Detrás de un proxy inverso todos los clientes compartirían origen** y el límite por origen bloquearía a todos a la vez, o a ninguno | Si en producción hay un proxy, hay que decidir qué cabecera de reenvío se acepta y de qué proxies de confianza; sin eso, el límite por origen es inútil o dañino | **Abierta.** Recomiendo resolverla en el diseño de TKT-058 (despliegue) y dejar aquí `request.client.host` `(asumido)` |
| PA-T6 | El rechazo CSRF de `POST /sesion` se asienta en `intento_acceso` solo si el cuerpo trae un correo legible; si no, solo va al registro técnico. `intento_acceso.email` es `NOT NULL` y no hay migración | Si se exigiera asentar todo rechazo, haría falta una migración aditiva (correo nulo y columna de motivo) | `(asumido)` — derivado de la decisión del 2026-10-30 |
| PA-T7 | «Rotar» el token significa fijar en la respuesta de iniciar y de cerrar sesión una cookie `cimenta_csrf` con valor nuevo. El token no guarda estado en el servidor, así que el valor anterior solo deja de valer porque ya no coincide con la cookie vigente | Si se quisiera que el servidor recordara y revocara tokens, sería un diseño distinto (con estado) | `(asumido)` — a confirmar en el diseño |
| PA-T8 | `.env.example` sin valores contradice la nota «Credenciales de desarrollo» del stack §6.4, que describe valores `solo-desarrollo-*`, y el trabajo `humo` que copia el archivo. Se resuelve inyectando los valores de prueba como variables del trabajo; la guía de arranque local debe decir cómo definirlos. `compose.yaml` ya falla con mensaje si falta `CIMENTA_DB_CONTRASENA_MIGRACION` | Quien clone el repositorio ya no arranca sin definir las contraseñas; hay que documentarlo bien o se pierde el primer arranque | Confirmado por la persona dueña el 2026-10-30; impacto en docs (`M8`) |
| PA-T11 | **Distinguir un fallo de un rechazo por bloqueo.** `CA-8` asienta los intentos rechazados por bloqueo con `exitoso` falso, y `CA-3` y `PA-T9` exigen que no cuenten ni alarguen el bloqueo. `intento_acceso` no tiene columna que los distinga, y para un correo inexistente tampoco existe `bloqueado_hasta`. El diseño debe mostrar cómo se calcula sin ambigüedad (por ejemplo, contando solo fallos posteriores al final del bloqueo anterior) o proponer una migración aditiva (columna de resultado) | Si no se resuelve, un atacante que siga intentando contra un correo inexistente mantendría el bloqueo vivo y se distinguiría de una cuenta real por su duración, que es la enumeración que `CA-4` prohíbe | **Resuelta** en el diseño (`D-1`): migración aditiva `v0005` con `credenciales_verificadas`, aprobada el 2026-10-30 |
| PA-T12 | **Riesgo residual aceptado por el ticket:** quien conozca un correo puede bloquearlo con cinco intentos cada 15 minutos, y una oficina entera comparte origen. Es el costo de un bloqueo que caduca solo (el ticket lo prefiere a un bloqueo permanente). Dirección General no podría autorizar mientras su cuenta esté bloqueada | Si el negocio no lo tolera, hace falta otro mecanismo (bloqueo por cuenta y origen combinados, desbloqueo por una persona administradora) | Abierta; ticket futuro sugerido |
| PA-T9 | El recuento por origen cuenta solo **fallos** del origen, no intentos exitosos ni rechazados por bloqueo | Si contaran los rechazados, un atacante mantendría bloqueado indefinidamente a un origen compartido (una oficina entera) | `(asumido)` — a confirmar en el diseño |
| PA-T10 | Dependencias externas de pago o cuenta: **ninguna**. El límite, el token, las cabeceras y la configuración son código local. El escaneo de secretos de GitHub que cita el stack §6.6 es una configuración del repositorio, ya cubierta por TKT-009 | No hay presupuesto que confirmar | Resuelto |

## Pasada adversarial

Resultado de `abogado-del-diablo`, modo A (retar el qué), sobre esta spec. Sin evidencia del historial de evolución para este dominio más allá de lo que citan `sdd/tickets/tkt-006/delta.md` y su `spec.md` (`PA-T5`, `PA-T9`).

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Crítica | Exigir al arrancar las tres contraseñas de base de datos pone la credencial de migración en el entorno del servidor, contra `RNF-09`; el código solo usa la de aplicación en ejecución (`backend/servidor/fabrica.py:27-47`) | Consultado a la persona dueña, que decidió el 2026-10-30 exigir solo `CIMENTA_DB_CONTRASENA_APLICACION` al servidor. `M6`, `CA-15` y `CA-17` reescritos; nombres reales de variable |
| 2 | Alta | `CA-12` pedía rechazar el token anterior T1 con cookie y cabecera ambas en T1; con doble envío sin estado ese par coincide y se aceptaría: el criterio era inalcanzable | Reescrito: cookie T2 con cabecera T1 se rechaza. `PA-T7` aclara qué significa rotar |
| 3 | Alta | `CA-8`, `CA-3` y `PA-T9` se contradicen sin forma de distinguir un fallo de un rechazo por bloqueo en `intento_acceso`, y para correos inexistentes no hay `bloqueado_hasta`; un bloqueo que se prolonga revela la cuenta inexistente | Nueva `PA-T11`, abierta: el diseño demuestra el cálculo o propone migración aditiva con visto bueno de la persona dueña |
| 4 | Media | Bloqueo que caduca solo permite bloquear a otra persona o a una oficina entera por origen compartido | Riesgo residual aceptado por el ticket, registrado en `PA-T12` y en tickets futuros |
| 5 | Media | La política de contenido con `'self'` rompe `/docs`, que el ticket no cubre | Anotado en `PA-T4`; queda dentro de la deuda de `/docs` fuera de alcance |

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

**Estado de partida (verificado en el código, 2026-10-30).**

- `backend/cimenta/identidad/api/rutas.py:27-32` emite el token (`secrets.token_urlsafe(32)`, cookie `cimenta_csrf` con `secure`, sin `httponly`, `samesite=lax`). `iniciar_sesion` (línea 35) y `cerrar_sesion` (línea 61) no verifican ni rotan. La constante `COOKIE_CSRF` está en `api/dependencias.py:23`.
- `backend/cimenta/identidad/aplicacion/sesiones.py:50-83` asienta el intento y lo confirma antes del `401`. `usuario.bloqueado_hasta` (migración `v0001`, línea 56; modelo `infraestructura/modelos.py:38`) no se lee ni se escribe en ninguna parte.
- `intento_acceso` (`v0001`, líneas 108-118): `email text NOT NULL`, `usuario_id` nulo, `exitoso`, `ocurrido_en`, `origen_ip text`; `REVOKE UPDATE, DELETE` en la línea 120. Modelo ORM en `modelos.py:79`.
- `backend/contrato_error/excepciones.py:321-336` define `LimiteIntentosExcedido` con `Retry-After`, serializada en `backend/servidor/manejadores.py:100-104`. `MotivoPermiso.ORIGEN_NO_VERIFICADO` existe en `catalogos.py:95` y nadie lo lanza. `PermisoDenegado` exige `roles_requeridos` (`excepciones.py:295`).
- `backend/servidor/fabrica.py:27-47` lee `os.environ`; `backend/cimenta/identidad/aplicacion/configuracion.py` es una `dataclass` hecha a mano con cinco variables opcionales. `pydantic-settings` solo está como transitiva (`backend/uv.lock:665`).
- `backend/tests/test_servidor_arranque.py:140-164` (TC-75) exige arrancar sin `CIMENTA_DB_*`. `backend/tests/test_tkt006_enrutador.py:56` ya recorre el enrutador con `LISTA_CERRADA` de dos rutas y es la base de `CA-18` y `CA-R6`.
- Los tests `test_tkt006_inicio_sesion.py` y `test_tkt006_cierre.py` envían inicio y cierre sin token porque «exigirlo es de TKT-057».
- `frontend/src/api/cliente.ts:29-33, 58-82` ya envía `X-CSRF-Token` en todo método que muta y vuelve a pedir el token tras iniciar y cerrar sesión. `PaginaInicioSesion.tsx` ya contempla `429` y `403`.
- `.env.example` línea 10 reserva «TKT-057: configuración de arranque». El trabajo `humo` hace `cp .env.example .env` (`.github/workflows/ci.yml:130-131`).

**Contrato.**

- Operaciones del borrador con `TKT-057` en `x-tickets`: `obtener_token_csrf` (`GET /sesion/csrf`) e `iniciar_sesion` (`POST /sesion`, con `401`, `403`, `422`, `429`). `cerrar_sesion` (`POST /sesion/cierre`) declara `csrf` y `403` pero cita solo `TKT-006`: se le añade `TKT-057`.
- Componentes: esquema de seguridad `csrf` (`openapi.yaml:3276-3283`), `DemasiadosIntentos` (3496), `ErrorLimiteIntentos` (4161-4175, «misma respuesta por cuenta que por origen»), `ErrorPermiso` (4117-4144).
- [Especificación del API §2.5](../../../docs/07-especificacion-api.md): «La rotación y la verificación llegan con TKT-057».

**Discrepancias que este ticket corrige en la documentación (`M8`).**

- Stack §6.3 pide una «semilla del token CSRF» como secreto obligatorio; el token no tiene semilla.
- Stack §6.4 describe valores `solo-desarrollo-*` en `.env.example`.
- Ticket (`docs/05-tickets-trabajo.md`): `img-src` y `media-src` «y ningún otro»; se amplía a `connect-src`.
- Ticket dice «N fallos»; stack §6.6 dice «N+1»; se fija en `CA-1`.

**Del glosario.** «Origen» tiene tres sentidos que no deben mezclarse: la dirección de red del cliente (`intento_acceso.origen_ip`), el origen de la política de contenido (esquema, host y puerto del almacén) y la «prueba de origen» del token CSRF. Esta spec usa el primero en `CA-6` a `CA-8`, el segundo en `CA-14` y el tercero en `CA-9` a `CA-12`.

**Aguas abajo.** TKT-063 (armazón sin conexión) pide «token de doble envío fresco antes de subir». TKT-059 reutiliza la política de contenido y la configuración. El ticket de analítica reutiliza la validación de `pydantic-settings` (ADR-017, regla 4).
