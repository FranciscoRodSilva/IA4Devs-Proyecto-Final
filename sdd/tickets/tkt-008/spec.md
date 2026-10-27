# Spec · TKT-008 · Esqueleto del frontend y cliente de API

> [← index](_index.md) | Siguiente: design (pendiente de `/sdd-disenar`)

## Contexto y problema

Hoy no existe aplicación de cliente. El directorio `frontend/` es el esqueleto de TKT-001: un `package.json` con los scripts `lint` y `typecheck`, ESLint y TypeScript en modo estricto, y un único `src/index.ts` con una constante. No están instalados React, Vite, Tailwind, Vitest ni Playwright, y `npm run dev` figura en `CLAUDE.md` y en `docs/arranque-local.md` con la marca «desde TKT-008».

El backend, en cambio, ya publica lo que el cliente necesita para entrar: TKT-006 montó `GET /sesion/csrf`, `POST /sesion`, `GET /sesion` y `POST /sesion/cierre`, y TKT-005 fijó el contrato de error con su campo `tipo`. Sin un cliente que entienda ese contrato, cada historia de la fase 1 escribiría su propia forma de leer un `409`, su propio formulario de alta y su propio diálogo de motivo. Este ticket de fundación los entrega una sola vez.

Estado de partida, criterio por criterio del ticket:

| Criterio del ticket | Estado de partida |
|---|---|
| Aplicación de página única con enrutado y carpetas por módulo | No existe. `frontend/src/index.ts` es una constante; `tsconfig.json` no declara `jsx` y `eslint.config.js` solo revisa `**/*.ts` |
| Inicio de sesión contra TKT-006 | Las cuatro rutas existen en `backend/cimenta/identidad/api/rutas.py`. La cookie `cimenta_sesion` es `HttpOnly`, `Secure` y `SameSite=Lax`; el token CSRF viaja en la cookie `cimenta_csrf` y en el cuerpo `TokenCsrf`. El servidor todavía **no verifica ni rota** el token: eso es TKT-057 |
| Navegación por roles | `GET /sesion` devuelve `UsuarioActual` con `roles` y los dos vencimientos de la sesión. El borrador dice que «la navegación del cliente se construye con esta respuesta». No hay ninguna sección de negocio implementada |
| Tipos generados del OpenAPI publicado, comprobados | No hay generación ni CI (`.github/workflows/` no existe; TKT-009 depende de este ticket). **El OpenAPI publicado no declara los esquemas de error**: muestra `HTTPValidationError` para el `422` y no tiene `ErrorConflicto` ni `ErrorSesion` (`sdd/tickets/tkt-005/delta.md`) |
| Cliente que reconoce el contrato de error | No existe. El contrato tiene ocho `tipo`: `REGLA_NEGOCIO`, `VALIDACION`, `PERMISO`, `CONFLICTO`, `CONCURRENCIA`, `SESION`, `LIMITE_INTENTOS` y `NO_ENCONTRADO`; los `409` son un `oneOf` con discriminador en `tipo` |
| Zod solo en formularios | No hay Zod |
| Pantalla de bloqueo, formulario de catálogo y captura de motivo | No existen. La pantalla de bloqueo tiene boceto (wireframe §6); los otros dos **no tienen boceto**: se especifican desde los escenarios que los consumen |
| Importes con decimal exacto | No hay `decimal.js` |
| Usable en escritorio y en teléfono | Nada que usar todavía |
| Tipos comparados contra el borrador por TKT-061 | TKT-061 depende de este ticket y llega en el sprint 4 |

La spec parte de cuatro decisiones del usuario, tomadas el 2026-10-26 en el intake:

1. **Los tipos del servidor salen del OpenAPI publicado; los del contrato de error, del borrador, como provisionales.** Es el uso que permite [API §6.2](../../../docs/07-especificacion-api.md#62-para-generar-los-tipos-del-cliente). Publicar los esquemas de error en FastAPI con `responses=` es un ticket futuro sugerido, previo a TKT-061, y en ese momento los tipos provisionales se retiran.
2. **La comprobación «en CI» se recorta a un comando del proyecto que falla si el archivo generado difiere.** Engancharlo al pipeline es de TKT-009; compararlo con el borrador es de TKT-061.
3. **La navegación lleva la tabla de secciones por rol del wireframe §2, y cada entrada lleva a una ruta marcador.** Sin selector de obra ni contador de autorizaciones: sus endpoints son de otros tickets.
4. **Playwright entra como Should**, con un único recorrido de humo: iniciar sesión, ver el armazón y cerrar sesión, contra el backend real.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario propia ([wireframe §1](../../../docs/08-wireframes.md#1-inicio-de-sesión): «Sin historia propia: es fundación»). Quien lo usa al final son los seis roles del sistema, que entran a CIMENTA por la pantalla de inicio de sesión; quienes lo invocan son las pantallas de HDU-001 a HDU-007, que usan sus tres componentes reutilizables.

**Como** persona o agente que desarrolla las pantallas de CIMENTA
**quiero** una aplicación con inicio de sesión, navegación por rol, un cliente de API que entienda el contrato de error y tres componentes reutilizables —pantalla de bloqueo, formulario de catálogo y captura de motivo—
**para** que cada historia pinte un rechazo, un alta o un motivo de la misma forma, sin recalcular cifras, sin leer la cookie de sesión y sin convertir un importe con `Number`.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Aplicación de página única con React 19, TypeScript y Vite, enrutado con React Router, carpetas por módulo de negocio y Tailwind v4 sin archivo de configuración. `npm run dev` levanta el cliente con un *proxy* al backend en el mismo origen, de modo que la cookie de sesión viaje sin configuración cruzada |
| | **M2.** Tipos del servidor generados con `openapi-typescript` del OpenAPI que publica FastAPI, obtenido **sin servidor en marcha**, y tipos del contrato de error generados del borrador [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml), marcados provisionales. Un comando del proyecto genera ambos y otro falla si el archivo versionado difiere de lo que se generaría |
| | **M3.** Cliente de API: envía la cookie, obtiene el token de `GET /sesion/csrf` y lo pone en `X-CSRF-Token` en todo método que muta estado, y **normaliza toda respuesta de error** a una unión discriminada por `tipo` que expone `mensaje`, `correlacion_id` y, según el tipo, `regla`, `codigo`, `detalle`, `acciones`, `errores`, `motivo` o `reintentar_en_s`. Un `401` fuera del inicio de sesión devuelve al inicio con el aviso de sesión terminada |
| | **M4.** Pantalla de inicio de sesión del [wireframe §1](../../../docs/08-wireframes.md#1-inicio-de-sesión), con sus cinco estados de rechazo: credenciales incorrectas, demasiados intentos, sin conexión, sesión terminada y origen no verificado |
| | **M5.** Armazón del [wireframe §2](../../../docs/08-wireframes.md#2-armazón-de-navegación-por-rol): menú con la **unión** de las secciones de los roles del usuario, nombre y rol en la cabecera, *Salir*, vencimiento visible como el menor de los dos que devuelve `GET /sesion`, menú plegable en teléfono, ruta marcador por sección, aviso *«No tienes permiso para esta sección»* sin importes al llegar por URL a una sección ajena, y aviso para el usuario sin roles |
| | **M6.** Componente de **pantalla de bloqueo** del [wireframe §6](../../../docs/08-wireframes.md#6-pantalla-de-bloqueo): pinta cualquier `409` del contrato por su `tipo`, con las cifras del `detalle` y un botón por cada elemento de `acciones[]`, sin recalcular nada |
| | **M7.** Componente de **formulario de catálogo**: apertura con el foco en el primer campo, validación de forma con Zod, `422` del servidor junto a su campo, `409` de duplicado pintado en línea con el registro existente, y confirmación explícita antes de una baja |
| | **M8.** Componente de **captura de motivo obligatorio**: no envía sin motivo y, si el servidor responde `422`, muestra el mensaje del servidor |
| | **M9.** El dinero y las cantidades del cliente pasan por `decimal.js`, nunca por `Number`, y se redondean solo al presentar. Zod valida formularios y no espeja ninguna respuesta del servidor |
| | **M10.** Pruebas de componente con Vitest que cubren los cuatro estados de cada vista —cargando, vacío, error y bloqueado— donde aplican, y la documentación al día: la marca «desde TKT-008» de `npm run dev` sale de `CLAUDE.md` y de `docs/arranque-local.md`, y la sección de frontend de este último describe el arranque real |
| **Should** | **S1.** Un recorrido de Playwright contra el backend real: iniciar sesión con un usuario sembrado, ver el armazón con sus secciones y cerrar sesión; y su rechazo, credenciales incorrectas |
| **Could** | — |
| **Won't** | Engancharse al pipeline de CI (TKT-009) · comparar los tipos generados con el borrador (TKT-061) · publicar los esquemas de error en FastAPI con `responses=` (ticket futuro) · selector de obra y `GET /obras` · contador de autorizaciones · cualquier pantalla de negocio · el armazón sin conexión —service worker, caché, cola, sincronización, indicador— (TKT-063) · iniciar sesión sin conexión · verificación y rotación real del token CSRF y el `429` real (TKT-057) · servir los estáticos desde el backend · cablear el efecto de una acción de negocio concreta de la pantalla de bloqueo, salvo `REINTENTAR` |

## Non-goals

- No implementa ninguna pantalla de negocio. Las secciones del menú llevan a rutas marcador; cada ticket de historia sustituye la suya.
- No toca el backend. Ni rutas, ni esquemas, ni `servidor/fabrica.py`. Si el cliente necesita algo que el servidor no publica, se anota y se escala.
- No decide qué hace el botón de una acción de negocio. La pantalla de bloqueo entrega la acción pulsada —clave, método y ruta— a quien la abrió; el efecto de `VER_SOLICITUD_AUTORIZACION`, `CANCELAR_REQUISICION` y las demás lo cablea la pantalla consumidora. La única acción que el componente resuelve por sí mismo es `REINTENTAR`, porque repite la petición original.
- No filtra acciones por rol: el servidor ya las filtra ([wireframe §6](../../../docs/08-wireframes.md#6-pantalla-de-bloqueo)).
- No monta nada de la fase 2: ni captura sin conexión, ni evidencia, ni cámara.
- No escribe tipos a mano que espejen un modelo de Pydantic ni un esquema Zod que espeje una respuesta.
- No configura CI ni Dependabot.

## Reglas de negocio implicadas

Ningún `RN-xx` de negocio se **implementa** en el cliente: el cliente nunca evalúa una regla (regla 10 de `CLAUDE.md`). Las reglas aparecen porque el cliente las **pinta** o porque fijan cómo debe comportarse.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-04` | Toda autorización y todo rechazo llevan actor, momento y motivo. La captura de motivo es el lado del cliente; quien exige el motivo es el servidor | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-03`, `RN-07` | Aparecen como contenido de la pantalla de bloqueo, con sus detalles `DetalleExcedePresupuesto` y `DetalleExcedeOrdenado`. El componente no las evalúa | PRD §8 |
| `RNF-01` | La sesión es revocable y surte efecto en la petición siguiente: un `401` devuelve al inicio, un `403` vuelve a pedir `GET /sesion` | PRD §9 |
| `RNF-02` | La credencial de sesión no es legible desde JavaScript: el cliente nunca lee `cimenta_sesion`, pregunta a `GET /sesion` | PRD §9 |
| `RNF-03` | La derivación de la contraseña es lenta a propósito: el botón de inicio se deshabilita mientras la petición está en vuelo | PRD §9 |
| `RNF-04` | Intentos de acceso limitados: el cliente muestra la cuenta atrás del `429` | PRD §9 |
| `RNF-05` | Toda operación que muta estado lleva la prueba de origen: `X-CSRF-Token` | PRD §9 |
| `RNF-13` | Correlación: la pantalla de bloqueo muestra `correlacion_id` como referencia | PRD §9 |
| `RNF-16` | Espera de bloqueo vencida: `REINTENTAR` respeta `Retry-After` | PRD §9 |
| Regla 1 de `CLAUDE.md` | El dinero nunca es flotante: en el cliente, `decimal.js` | `CLAUDE.md` |
| Regla 9 de `CLAUDE.md` | Sesión con estado en el servidor; cookie opaca | `CLAUDE.md`, ADR-014 |
| Regla 10 de `CLAUDE.md` | No se inicia sesión sin conexión; el cliente nunca evalúa una regla | `CLAUDE.md`, ADR-015 |
| Regla 17 de `CLAUDE.md` | El ticket es de fase 1 y no adelanta nada de la fase 2 | `CLAUDE.md` |

Términos del [glosario](../../../docs/glosario.md) que importan: *tipo de partida* (el detalle de `RN-03` se expresa por obra y tipo de partida, no por partida), *requisición* e *insumo*. El glosario no define *disponible*, *consumido* ni *excedente*: su definición está en la regla 5 de `CLAUDE.md` y en el [modelo de datos §15](../../../docs/03-modelo-datos.md#15-la-consulta-del-semáforo), y el cliente **no la aplica**: muestra las cifras que llegan.

## Invariantes que deben sobrevivir al cambio

El ticket no toca ninguna tabla ni ningún archivo del backend, pero modifica archivos que ya funcionan: `frontend/package.json` y su `package-lock.json`, `frontend/tsconfig.json`, `frontend/eslint.config.js`, `frontend/src/index.ts`, `CLAUDE.md` y `docs/arranque-local.md`.

| Invariante o garantía | Qué protege | Criterio de regresión |
|---|---|---|
| `npm ci`, `npm run lint` y `npm run typecheck` siguen funcionando, ahora sobre `.ts` y `.tsx`, con `engine-strict` y `save-exact` de `.npmrc` | El esqueleto de TKT-001 y la reproducibilidad del lock | `CA-R1` |
| El backend no cambia: la suite de TKT-001 a TKT-007, `ruff`, `mypy`, `lint-imports` y `verificar_float` siguen en verde | Que un ticket de frontend no rompa el servidor | `CA-R2` |
| `RNF-02`: ningún código del cliente lee `document.cookie` en busca de la sesión | La cookie de sesión opaca e ilegible (regla 9) | `CA-R3` |
| Regla 1 de `CLAUDE.md` en el cliente: ningún tipo generado declara un importe como `number` | El dinero como cadena hasta `decimal.js` | `CA-R3` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde; sin BOM y con LF | Enlaces, identificadores y conteos de la documentación | `CA-R4` |

## Criterios de aceptación

Gherkin, en español. Las pruebas de componente usan un doble del servidor que responde con cuerpos que cumplen los esquemas del borrador; el recorrido de humo de `CA-14` va contra el backend real. Cada test lleva en su nombre el criterio que cubre `(asumido)`, porque el ticket no tiene historia propia: el escenario `HDU-xxx esc. N` lo cubre la pantalla consumidora.

### CA-1 `[M]` · La aplicación arranca, enruta y respeta las convenciones del cliente · M1

```gherkin
Escenario: El cliente arranca en desarrollo contra el backend
  Dado el backend en 127.0.0.1:8000 y las dependencias instaladas con npm ci
  Cuando se ejecuta npm run dev
  Entonces el cliente sirve la aplicación y las peticiones a /api/v1 llegan al backend por el proxy, en el mismo origen
  Y la cookie de sesión viaja en las peticiones sin que el cliente la lea

Escenario: Estructura por módulo de negocio
  Dado el árbol de frontend/src
  Cuando se revisa
  Entonces hay una carpeta por módulo de negocio que tendrá pantallas y una zona compartida para el cliente de API y los componentes reutilizables

Escenario: Rechazo — una ruta que no existe
  Dado un usuario con sesión
  Cuando navega a una ruta que la aplicación no declara
  Entonces ve una página de «no encontrado» dentro del armazón, y no una pantalla en blanco
```

### CA-2 `[M]` · Los tipos se generan y su desfase se detecta · M2

```gherkin
Escenario: Generar los tipos sin servidor en marcha
  Dado el backend sin arrancar
  Cuando se ejecuta el comando de generación
  Entonces se escribe el archivo de tipos del OpenAPI que publica FastAPI y el archivo de tipos provisionales del contrato de error tomados del borrador
  Y todo importe y toda cantidad tienen tipo string, ninguno number
  Y el archivo provisional declara en su cabecera que es provisional y que se retira cuando el servidor publique los esquemas de error

Escenario: Los 409 se estrechan por su tipo
  Dado los tipos provisionales del contrato de error
  Cuando un switch sobre tipo distingue REGLA_NEGOCIO, CONFLICTO y CONCURRENCIA
  Entonces TypeScript da acceso a regla en la primera rama, a codigo en la segunda y a detalle.espera_maxima_ms en la tercera, sin conversión de tipos

Escenario: Rechazo — el archivo versionado está desfasado
  Dado un cambio en el OpenAPI publicado que no se regeneró
  Cuando se ejecuta el comando de verificación
  Entonces falla con salida distinta de cero y nombra el archivo que difiere

Escenario: La generación es determinista
  Dado el mismo OpenAPI publicado y el mismo borrador
  Cuando se ejecuta el comando de generación dos veces seguidas
  Entonces los archivos resultantes son idénticos byte a byte, y el comando de verificación pasa sin cambios

Escenario: Rechazo — nadie edita los tipos a mano
  Dado el archivo generado con una línea añadida a mano
  Cuando se ejecuta el comando de verificación
  Entonces falla igual que con un esquema desfasado
```

### CA-3 `[M]` · El cliente lleva la prueba de origen en toda mutación · M3 · `RNF-05`

```gherkin
Escenario: Token CSRF antes de iniciar sesión
  Dado un cliente sin token
  Cuando se envía POST /sesion
  Entonces antes se pidió GET /sesion/csrf, y la petición lleva la cabecera X-CSRF-Token con el token recibido

Escenario: Todo método que muta estado lleva la cabecera
  Dado un cliente con token
  Cuando envía un POST, un PUT, un PATCH o un DELETE
  Entonces cada petición lleva X-CSRF-Token, y un GET no la lleva

Escenario: Rechazo — origen no verificado
  Dado un doble del servidor que responde 403 con tipo PERMISO y motivo ORIGEN_NO_VERIFICADO
  Cuando el cliente recibe la respuesta
  Entonces no reintenta en silencio: entrega el error y la pantalla pide recargar
```

### CA-4 `[M]` · El cliente normaliza el contrato de error · M3

```gherkin
Escenario: Cada tipo llega con sus campos
  Dado un doble del servidor que responde con cada uno de los ocho tipo del contrato
  Cuando el cliente recibe cada respuesta
  Entonces entrega un error discriminado por tipo con mensaje y correlacion_id
  Y REGLA_NEGOCIO trae regla, detalle y acciones; CONFLICTO trae codigo, detalle y acciones; CONCURRENCIA trae codigo, detalle y el valor de Retry-After
  Y VALIDACION trae errores con campo, codigo y mensaje; PERMISO trae motivo y roles_requeridos; SESION trae motivo; LIMITE_INTENTOS trae reintentar_en_s; NO_ENCONTRADO trae recurso

Escenario: Rechazo — una respuesta fuera del contrato
  Dado un doble que responde 500 con mensaje y correlacion_id y sin tipo, y otro que responde un cuerpo que no es JSON
  Cuando el cliente recibe cada respuesta
  Entonces entrega un error genérico con el mensaje y la correlación cuando existen, sin lanzar una excepción sin tratar y sin inventar un tipo del contrato

Escenario: Rechazo — sin red
  Dado que la petición no llega al servidor
  Cuando el cliente la envía
  Entonces entrega un error de red distinto de cualquier tipo del contrato, y no lo confunde con un 401

Escenario: Las acciones se exponen tal como llegan
  Dado un 409 con acciones que traen clave, metodo y ruta absoluta con /api/v1
  Cuando el cliente lo normaliza
  Entonces las acciones conservan su orden y su ruta sin reescribirla
```

### CA-5 `[M]` · Un 401 devuelve al inicio; un 403 vuelve a preguntar quién es · M3, M5 · `RNF-01`

```gherkin
Escenario: Sesión caducada o revocada en cualquier pantalla
  Dado un usuario dentro del armazón
  Cuando una petición responde 401 con tipo SESION y motivo SESION_CADUCADA o SESION_REVOCADA
  Entonces la aplicación descarta lo que tenía en caché de la sesión y lleva al inicio de sesión con el aviso «Tu sesión terminó. Vuelve a iniciarla.»

Escenario: Rechazo — sin sesión previa no hay aviso de sesión terminada
  Dado un navegador que nunca inició sesión
  Cuando el usuario abre la aplicación y GET /sesion responde 401
  Entonces ve el inicio de sesión sin el aviso «Tu sesión terminó», porque no había sesión que terminara

Escenario: Rechazo — el 401 del propio inicio de sesión no se trata como sesión terminada
  Dado la pantalla de inicio de sesión
  Cuando POST /sesion responde 401 por credenciales incorrectas
  Entonces no aparece el aviso de sesión terminada ni hay redirección: se aplica CA-6

Escenario: Rol retirado durante la sesión
  Dado un usuario con los roles COMPRAS y ALMACEN y su menú dibujado
  Cuando una petición responde 403 y la siguiente consulta de GET /sesion devuelve solo ALMACEN
  Entonces el armazón redibuja el menú sin las secciones que solo daba COMPRAS
```

### CA-6 `[M]` · Inicio de sesión y sus rechazos · M4 · `RNF-02`, `RNF-03`, `RNF-04`

```gherkin
Escenario: Iniciar sesión
  Dado la pantalla de inicio de sesión
  Cuando el usuario escribe correo y contraseña y pulsa «Iniciar sesión»
  Entonces el botón queda deshabilitado mientras la petición está en vuelo
  Y al aceptar, la aplicación pide GET /sesion y entra al armazón en la primera sección que permiten sus roles, según el orden de la tabla del wireframe §2 (asumido)

Escenario: Ya hay sesión
  Dado un navegador con una sesión vigente
  Cuando el usuario abre la aplicación
  Entonces GET /sesion responde 200 y entra al armazón sin pasar por el formulario

Escenario: Rechazo — credenciales incorrectas
  Dado un doble que responde 401 con tipo SESION y motivo CREDENCIALES_INVALIDAS
  Cuando el usuario envía el formulario
  Entonces aparece un único mensaje «Correo o contraseña incorrectos.», igual exista o no el correo
  Y la contraseña se vacía y el correo se conserva

Escenario: Rechazo — forma inválida
  Dado un correo con forma inválida, o una contraseña vacía
  Cuando el usuario envía el formulario
  Entonces Zod lo marca junto al campo y no se envía ninguna petición
  Y si el servidor responde 422, sus errores se pintan junto al campo que nombra errores[].campo

Escenario: Rechazo — demasiados intentos
  Dado un doble que responde 429 con tipo LIMITE_INTENTOS y reintentar_en_s 900
  Cuando el usuario envía el formulario
  Entonces el mensaje dice cuánto falta, el botón queda deshabilitado con la cuenta atrás, y se rehabilita al llegar a cero

Escenario: Rechazo — sin conexión
  Dado el navegador sin conexión
  Cuando el usuario abre la pantalla de inicio de sesión
  Entonces el botón queda deshabilitado con la explicación «Sin conexión. Para iniciar sesión hace falta conexión con el servidor.» y no se encola nada

Escenario: Rechazo — origen no verificado
  Dado un doble que responde 403 con motivo ORIGEN_NO_VERIFICADO
  Cuando el usuario envía el formulario
  Entonces la pantalla pide recargar y no reintenta
```

### CA-7 `[M]` · El armazón muestra la unión de las secciones de los roles · M5

```gherkin
Escenario: Un rol, sus secciones
  Dado un usuario con el rol ALMACEN
  Cuando entra al armazón
  Entonces el menú muestra Órdenes de compra, Proveedores y Recepción · Pendientes de recibir, y ninguna otra sección
  Y la cabecera muestra su nombre, su rol y «Salir»

Escenario: Varios roles, la unión
  Dado un usuario con los roles COMPRAS y ALMACEN
  Cuando entra al armazón
  Entonces el menú muestra la unión de las secciones de ambos roles, sin repetir ninguna

Escenario: Cada sección lleva a su ruta marcador
  Dado un usuario con el rol DIRECCION_GENERAL
  Cuando elige cualquier sección del menú
  Entonces la URL cambia y el contenido muestra el nombre de la sección y que aún no está disponible

Escenario: Vencimiento de la sesión
  Dado GET /sesion con expira_en y expira_por_inactividad_en distintos
  Cuando el armazón los muestra
  Entonces muestra el menor de los dos

Escenario: Rechazo — sección ajena por URL
  Dado un usuario con el rol ALMACEN
  Cuando navega por URL a la ruta de Autorizaciones
  Entonces ve «No tienes permiso para esta sección» sin ningún importe, y el menú no muestra esa sección
  Y la guarda del cliente es solo cortesía de navegación: el control real es el 403 del servidor, que la pantalla de cada sección pinta igual con el mismo aviso

Escenario: Rechazo — usuario sin roles
  Dado un usuario con sesión y roles vacío
  Cuando entra al armazón
  Entonces el menú no tiene secciones y el contenido dice que no tiene secciones asignadas y que lo pida a un administrador (asumido)
  Y «Salir» sigue disponible

Escenario: Salir
  Dado un usuario dentro del armazón
  Cuando pulsa «Salir»
  Entonces el cliente envía POST /sesion/cierre con X-CSRF-Token, descarta la caché de la sesión y vuelve al inicio de sesión
  Y si la respuesta es 401 porque la sesión ya había terminado, vuelve al inicio igual

Escenario: Teléfono
  Dado un viewport de 375 px de ancho
  Cuando se abre el armazón
  Entonces el menú lateral se pliega bajo un botón «≡» que lo abre y lo cierra, y no hay desplazamiento horizontal
```

### CA-8 `[M]` · La pantalla de bloqueo pinta una regla de negocio · M6 · `RN-03`

```gherkin
Escenario: Bloqueo por importe con las cifras del detalle
  Dado un 409 con tipo REGLA_NEGOCIO, regla "RN-03" y un DetalleExcedePresupuesto con presupuestado "45000.0000", consumido "33000.0000" y su desglose, disponible "12000.0000", solicitado "15000.0000" y excedente "3000.0000"
  Cuando se abre la pantalla de bloqueo con esa respuesta
  Entonces la cabecera dice «Operación bloqueada» y «Regla RN-03»
  Y el cuerpo muestra el mensaje tal cual
  Y las cifras aparecen en el orden del esquema, formateadas con decimal.js como $45,000.00, $33,000.00, $12,000.00, $15,000.00 y $3,000.00
  Y el excedente se resalta y es el que llegó, no una resta del cliente
  Y la referencia muestra el correlacion_id

Escenario: Bloqueo por volumen
  Dado un DetalleExcedePresupuesto con insumos[], uno de ellos con presupuestado_en_partida false
  Cuando se abre la pantalla de bloqueo
  Entonces cada insumo muestra sus cinco cantidades y el que no está presupuestado se rotula «no presupuestado en esta partida»

Escenario: Excedente de recepción
  Dado un 409 con regla "RN-07" y un DetalleExcedeOrdenado con renglones[]
  Cuando se abre la pantalla de bloqueo
  Entonces cada renglón muestra cantidad ordenada, recibida, saldo pendiente, entrante y excedente

Escenario: Rechazo — una clave de detalle desconocida
  Dado un detalle con una clave que el componente no conoce
  Cuando se abre la pantalla de bloqueo
  Entonces la clave aparece con su nombre crudo y su valor, y no se omite

Escenario: Rechazo — una cifra que no es decimal
  Dado un detalle con un importe que no es una cadena decimal válida
  Cuando se abre la pantalla de bloqueo
  Entonces la cifra se muestra como no disponible y el componente no lanza una excepción ni muestra NaN
```

### CA-9 `[M]` · La pantalla de bloqueo pinta un conflicto y una concurrencia · M6 · `RNF-16`

```gherkin
Escenario: Conflicto de estado
  Dado un 409 con tipo CONFLICTO y codigo ESTADO_NO_PERMITE_OPERACION
  Cuando se abre la pantalla de bloqueo
  Entonces la cabecera dice «No se puede completar» y el codigo, y no muestra ninguna regla RN

Escenario: Concurrencia y reintento
  Dado un 409 con tipo CONCURRENCIA, la acción REINTENTAR y Retry-After de 2 segundos
  Cuando se abre la pantalla de bloqueo
  Entonces la cabecera dice «Inténtalo de nuevo»
  Y el botón «Reintentar» queda deshabilitado hasta que pasan los 2 segundos, y al pulsarlo invoca la función de reintento que le entregó la pantalla que lo abrió, que repite la petición original

Escenario: Rechazo — sin función de reintento
  Dado un 409 de CONCURRENCIA con la acción REINTENTAR, abierto por una pantalla que no entrega función de reintento
  Cuando el usuario pulsa «Reintentar»
  Entonces el componente entrega la acción a quien lo abrió, como cualquier otra, y no repite nada por su cuenta

Escenario: Rechazo — un 422 o un 403 no abren la pantalla de bloqueo
  Dado una respuesta 422 o una 403
  Cuando se intenta abrir la pantalla de bloqueo con ella
  Entonces el componente no la acepta: su entrada solo admite el tipo de los 409
```

### CA-10 `[M]` · Los botones de la pantalla de bloqueo salen del contrato · M6

```gherkin
Escenario: Un botón por acción, en su orden
  Dado un 409 con las acciones VER_SOLICITUD_AUTORIZACION y CANCELAR_REQUISICION
  Cuando se abre la pantalla de bloqueo
  Entonces aparecen dos botones rotulados por su clave, en ese orden, más «Cerrar»
  Y al pulsar uno, el componente entrega a quien lo abrió la clave, el método y la ruta tal como llegaron, sin invocarla

Escenario: Rechazo — sin acciones, solo Cerrar
  Dado un 409 con acciones vacías
  Cuando se abre la pantalla de bloqueo
  Entonces el único botón es «Cerrar», y ningún botón de negocio está cableado de antemano

Escenario: Rechazo — una clave desconocida
  Dado una acción con una clave que el componente no conoce
  Cuando se abre la pantalla de bloqueo
  Entonces su botón aparece con la clave cruda y se entrega igual a quien lo abrió
```

### CA-11 `[M]` · El formulario de catálogo · M7 · habilita `HDU-001` esc. 1 y 3, `HDU-004` esc. 1, 3 y 12, `HDU-007` esc. 1, 4, 5, 12 y 13

```gherkin
Escenario: Abrir con el foco en el primer campo
  Dado una pantalla que usa el formulario de catálogo con sus campos y su esquema Zod
  Cuando el usuario pulsa «+»
  Entonces se abre el formulario con el foco en el primer campo

Escenario: Guardar
  Dado el formulario con datos válidos
  Cuando el usuario guarda
  Entonces el botón queda deshabilitado mientras la petición está en vuelo y, al aceptar, el formulario entrega la respuesta a la pantalla y se cierra

Escenario: Rechazo — forma inválida en el cliente
  Dado un campo obligatorio vacío
  Cuando el usuario guarda
  Entonces Zod lo marca junto al campo, el foco va al primer campo con error y no se envía ninguna petición

Escenario: Rechazo — 422 del servidor
  Dado un doble que responde 422 con errores en dos campos
  Cuando el usuario guarda
  Entonces cada mensaje del servidor aparece junto a su campo, y un error cuyo campo no está en el formulario aparece en la cabecera del formulario

Escenario: Rechazo — duplicado
  Dado un doble que responde 409 con tipo CONFLICTO, un codigo de duplicado y el registro existente en detalle
  Cuando el usuario guarda
  Entonces el conflicto se pinta en línea con el registro existente y sus acciones, sin abrir la pantalla de bloqueo
  Y los datos capturados se conservan

Escenario: Confirmación de baja
  Dado un registro que la pantalla permite dar de baja
  Cuando el usuario pide la baja
  Entonces el formulario pide confirmación explícita, con motivo cuando la pantalla lo exige, antes de enviar nada
  Y si cancela, no se envía ninguna petición

Escenario: Rechazo — la baja la rechaza el servidor
  Dado un doble que responde 409 a la baja, con las acciones alternativas del contrato
  Cuando el usuario confirma la baja
  Entonces el rechazo se pinta con sus acciones, sin que el formulario decida otra alternativa por su cuenta
```

### CA-12 `[M]` · La captura de motivo obligatorio · M8 · `RN-04` · habilita `HDU-001` esc. 23, `HDU-003` esc. 4, 5 y 6, `HDU-005` esc. 9 y 11, `HDU-007` esc. 11 y 13

```gherkin
Escenario: Confirmar con motivo
  Dado una pantalla que abre la captura de motivo para una acción
  Cuando el usuario escribe un motivo y confirma
  Entonces el componente entrega el motivo a la pantalla, que lo envía, y el botón queda deshabilitado mientras la petición está en vuelo

Escenario: Rechazo — sin motivo no se envía
  Dado la captura de motivo abierta
  Cuando el motivo está vacío o solo tiene espacios
  Entonces el botón de confirmar no envía y el campo se marca como obligatorio

Escenario: Rechazo — el servidor rechaza el motivo
  Dado un doble que responde 422 con un error en el campo motivo
  Cuando el usuario confirma
  Entonces la captura muestra el mensaje del servidor junto al campo, no uno propio, y conserva el texto escrito

Escenario: Rechazo — el servidor rechaza la operación
  Dado un doble que responde 409
  Cuando el usuario confirma
  Entonces la captura entrega el error a la pantalla, que lo pinta con la pantalla de bloqueo
```

### CA-13 `[M]` · El dinero no pasa por Number y Zod no espeja respuestas · M9 · regla 1

```gherkin
Escenario: Conversión y formato exactos
  Dado los importes "0.1000" y "0.2000"
  Cuando el cliente los suma y formatea
  Entonces el resultado presentado es $0.30, y el valor intermedio es un Decimal, no un number

Escenario: Redondeo solo al presentar
  Dado el importe "1234.5650"
  Cuando se presenta con dos decimales
  Entonces se muestra $1,234.57 con redondeo ROUND_HALF_UP (asumido), y el valor guardado conserva sus cuatro decimales

Escenario: Rechazo — conversión numérica nativa en el cliente
  Dado un archivo de frontend/src, fuera del módulo de dinero, que llama a Number(), parseFloat() o parseInt() (asumido: la prohibición es general, no por tipo de valor, porque ninguna herramienta distingue un importe de otra cadena)
  Cuando se ejecuta npm run lint
  Entonces falla nombrando el archivo y la línea
  Y el módulo de dinero es el único punto de entrada de decimal.js para importes y cantidades

Escenario: Rechazo — un esquema Zod que espeja una respuesta
  Dado el código del cliente
  Cuando se revisa dónde se usa Zod
  Entonces solo aparece en formularios, y ninguna respuesta del servidor se valida con un esquema Zod escrito a mano
```

### CA-14 `[S]` · Recorrido de humo contra el backend real · S1

```gherkin
Escenario: Entrar y salir
  Dado el backend y la base de prueba con un usuario sembrado con el rol COMPRAS
  Cuando Playwright inicia sesión, espera el armazón y pulsa «Salir»
  Entonces el armazón muestra las secciones de COMPRAS, y tras salir GET /sesion responde 401

Escenario: Rechazo — credenciales incorrectas
  Dado el mismo usuario
  Cuando Playwright envía una contraseña equivocada
  Entonces aparece «Correo o contraseña incorrectos.» y la contraseña queda vacía
```

### Criterios de regresión

#### CA-R1 `[M]` · Esqueleto de TKT-001

`npm ci`, `npm run lint` y `npm run typecheck` en verde, ahora sobre `.ts` y `.tsx`; `.npmrc` conserva `engine-strict` y `save-exact`, y todas las versiones del `package.json` quedan fijadas sin rango.

#### CA-R2 `[M]` · El backend no cambia

La suite de TKT-001 a TKT-007 en verde con Docker; `ruff`, `mypy`, `lint-imports` y `verificar_float` en verde; ningún archivo bajo `backend/` en el diff.

#### CA-R3 `[M]` · Sesión ilegible y dinero como cadena

Ningún código del cliente lee `document.cookie` para la sesión; ningún importe ni cantidad de los tipos generados es `number`.

#### CA-R4 `[M]` · Documentación

`python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y los tests de `tools/` sin problemas; `npm run dev` sin la marca «desde TKT-008» en `CLAUDE.md` y en `docs/arranque-local.md`.

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-005 y TKT-006, archivados. Bloquea a TKT-009, TKT-061 y a toda pantalla de la fase 1 |
| **N** | Describe el qué, no impone el cómo | Sí | Nombra el stack fijado por el ADR de frontend; las carpetas, el método de exportación del OpenAPI y el *proxy* los decide el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí | Los seis roles pueden iniciar sesión y ver solo lo que su rol permite; las historias heredan tres componentes en vez de inventarlos |
| **E** | Estimable sin investigar antes | Sí | El contrato de error, el borrador, las rutas de sesión y los bocetos §1, §2 y §6 existen. Los dos componentes sin boceto se acotan con sus escenarios |
| **S** | Cabe en una sesión sin romper contexto | Con reservas | Talla M con tres componentes, una pantalla, el armazón y la generación de tipos. El diseño debería partirlo en dos entregas |
| **T** | Sus criterios se pueden ejecutar | Sí | Vitest con dobles del servidor; Playwright contra el backend real con Docker |

Una sola reserva: pasa.

## Definition of Done

La de **Fundación**, más el genérico de [`sdd/metodologia.md` §8](../../../sdd/metodologia.md#8--definition-of-done-por-tipo):

- [ ] Los 13 criterios `[M]` y los 4 de regresión pasan, cada uno con su test nombrado por el criterio.
- [ ] Cada rechazo comprueba el contrato de error completo —`tipo`, cifras, acciones o campo—, no solo el código de estado.
- [ ] `npm run lint`, `npm run typecheck`, las pruebas de Vitest y el comando de verificación de tipos en verde.
- [ ] Ningún archivo bajo `backend/` en el diff.
- [ ] `CLAUDE.md` y `docs/arranque-local.md` al día.
- [ ] Auditoría de arquitectura, de código y de seguridad sin hallazgos abiertos.

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | Los tipos del contrato de error se generan del borrador como provisionales hasta que FastAPI publique los esquemas de error | El cliente compilaría contra una forma de error que el servidor no respeta; lo detecta TKT-061 | Decidido por el usuario. Ticket futuro sugerido: publicar `responses=` |
| PA-T2 | La primera sección tras iniciar sesión es la primera de la tabla del wireframe §2 que permite alguno de los roles del usuario `(asumido)` | Un rol aterriza en una sección que no es la que más usa | Abierta; se revisa cuando existan las pantallas |
| PA-T3 | Un usuario con `roles: []` ve un aviso de que no tiene secciones asignadas, y puede salir `(asumido)`. El PRD no describe este caso | Un usuario sin roles vería una pantalla vacía sin explicación | Abierta |
| PA-T4 | El nombre de cada test cita el criterio `CA-n` de esta spec, no un escenario `HDU`, porque el ticket no tiene historia `(asumido)`. El verificador de escenarios de TKT-009 debe admitirlo | El verificador marcaría los tests como huérfanos o los escenarios como descubiertos | Abierta; se resuelve en TKT-009 |
| PA-T5 | El redondeo de presentación es `ROUND_HALF_UP`, como el de `cuantizar()` en el servidor `(asumido)` | Una cifra presentada distinta en un centavo de la que muestra el servidor | Abierta |
| PA-T6 | El servidor todavía no verifica el token CSRF ni produce `429` ni `ORIGEN_NO_VERIFICADO` (TKT-057). Esos rechazos se prueban contra un doble | El cliente podría no casar con la forma real cuando llegue TKT-057 | Abierta; TKT-057 añade la prueba contra el servidor real |
| PA-T7 | La cookie `Secure` funciona en `http://localhost` en desarrollo en Chromium (comprobado por el humo), Firefox `(asumido)` y Safari `(asumido)`, y el *proxy* de Vite mantiene el mismo origen `(asumido)` | El inicio de sesión no funcionaría en desarrollo local | Abierta; el diseño lo comprueba |
| PA-T8 | La tabla de secciones por rol vive en el cliente y duplica los `x-roles` del borrador | Si un `x-roles` cambia, el menú muestra una sección que responde `403` o esconde una permitida. El control real sigue siendo el `403` del servidor | Aceptada como cortesía de navegación; TKT-061 o el ticket de cada sección la revisa |
| PA-T9 | El cliente obtiene el token CSRF del cuerpo de `GET /sesion/csrf`, y lo vuelve a pedir tras iniciar y tras cerrar sesión `(asumido)` | Con la rotación de TKT-057, un token viejo daría `403` | Abierta; TKT-057 fija la rotación |
| PA-T10 | Exportar el OpenAPI publicado sin servidor exige el entorno Python del backend (`uv`) al generar los tipos del cliente `(asumido)` | El comando de generación no corre en una máquina solo con Node; TKT-009 debe tener ambos entornos en el mismo trabajo | Abierta; el diseño elige el método |
| PA-T11 | La prohibición de `Number()`, `parseFloat()` y `parseInt()` es general en `frontend/src`, con el módulo de dinero como única excepción `(asumido)` | Un uso legítimo —un índice de página, por ejemplo— necesitaría una excepción anotada | Abierta |
| PA-T12 | «Confirmación de baja» se interpreta como un diálogo de confirmación antes de enviar, con motivo cuando la pantalla lo exige. Ningún escenario lo describe como diálogo previo `(asumido)` | El componente pediría un paso que las historias no esperan | Abierta |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-13` pedía detectar `Number` «sobre un importe», y ninguna herramienta distingue un importe de otra cadena: el criterio no era verificable | Reescrito: la prohibición es general en `frontend/src` salvo el módulo de dinero, y la comprueba `npm run lint`. `PA-T11` |
| 2 | Alta | Una verificación de desfase sobre una generación no determinista falla sin cambios reales; y exportar el OpenAPI sin servidor arrastra el entorno Python al comando del cliente | `CA-2` añade el escenario de determinismo byte a byte; `PA-T10` declara la dependencia de `uv` |
| 3 | Media | En la primera visita, el `401` de `GET /sesion` habría mostrado «Tu sesión terminó» a quien nunca inició sesión | `CA-5` añade el escenario de rechazo sin sesión previa |
| 4 | Media | La pantalla de bloqueo no conoce la petición original, así que «Reintentar» no puede repetirla por sí misma | `CA-9` fija que el reintento lo entrega quien abre el componente, y añade el rechazo sin función de reintento |
| 5 | Media | Ocultar una sección en el menú o bloquearla por URL en el cliente podría leerse como control de acceso | `CA-7` declara la guarda como cortesía; el control es el `403` del servidor, y `PA-T8` registra la duplicación de `x-roles` |

Ninguna objeción reveló una regla que el PRD no tenga, así que no hace falta `/sdd-escalar`.

## Contexto técnico

Archivos, módulos y rutas relevantes. No son decisiones: el *cómo* es de `/sdd-disenar`.

- **Frontend actual:** `frontend/package.json` (scripts `lint` y `typecheck`; Node `>=24 <25`), `frontend/.npmrc` (`engine-strict`, `save-exact`), `frontend/tsconfig.json` (estricto, `moduleResolution: Bundler`, sin `jsx`), `frontend/eslint.config.js` (solo `**/*.ts`), `frontend/src/index.ts` (constante que se sustituye).
- **Stack del cliente:** [ADR de frontend React SPA](../../../docs/adr/20260918-frontend-react-spa.md) — React Router, TanStack Query, React Hook Form con Zod, `openapi-typescript` con `openapi-fetch`, shadcn/ui copiado al repositorio; [stack §5.3](../../../docs/06-stack-tecnologico.md#53-el-dinero-también-es-exacto-en-el-cliente) para `decimal.js`. Convenciones en `.claude/skills/conv-frontend-react`.
- **Rutas de sesión (TKT-006):** `obtener_token_csrf` `GET /api/v1/sesion/csrf`, `iniciar_sesion` `POST /api/v1/sesion`, `obtener_sesion_actual` `GET /api/v1/sesion`, `cerrar_sesion` `POST /api/v1/sesion/cierre`, en `backend/cimenta/identidad/api/rutas.py`, montadas en `backend/servidor/fabrica.py`. Esquema `UsuarioActual` en `backend/cimenta/identidad/api/esquemas.py`.
- **Contrato de error (TKT-005):** clases en `backend/contrato_error/excepciones.py`; manejadores en `backend/servidor/manejadores.py` (el `500` responde sin `tipo`; una `HTTPException` distinta de 404 responde `{"detail": …}`). En el borrador: `Accion`, `ErrorReglaNegocio`, `ErrorConflictoEstado`, `ErrorConcurrencia`, `ErrorConflicto` (`oneOf` con discriminador `tipo`), `ErrorValidacion`, `ErrorPermiso`, `ErrorSesion`, `ErrorLimiteIntentos`, `ErrorNoEncontrado`, y los detalles `DetalleExcedePresupuesto`, `DetalleExcedeOrdenado`, `DetalleOrdenConSaldo`, `DetalleGenerico`.
- **Bocetos:** [wireframe §1](../../../docs/08-wireframes.md#1-inicio-de-sesión), [§2](../../../docs/08-wireframes.md#2-armazón-de-navegación-por-rol) y [§6](../../../docs/08-wireframes.md#6-pantalla-de-bloqueo). Los consumidores del formulario de catálogo, de la captura de motivo y de la pantalla de bloqueo son los tickets que citan «TKT-008» en `docs/05-tickets-trabajo.md`.
- **Generación de tipos:** [API §6.2](../../../docs/07-especificacion-api.md#62-para-generar-los-tipos-del-cliente). El diseño decide cómo exportar el OpenAPI sin servidor vivo y dónde vive el archivo generado.
- **Pendientes que TKT-006 dejó para este ticket:** mostrar el menor de los dos vencimientos, la cookie `Secure` en desarrollo y el usuario con `roles: []` (`sdd/tickets/tkt-006/delta.md`); pedir `GET /sesion/csrf` antes de `POST /sesion` (`sdd/tickets/tkt-006/design.md`).
- **Documentación a alinear:** `CLAUDE.md` (sección de comandos) y `docs/arranque-local.md` (sección de frontend y tabla de marcas).
- **Consumidores:** TKT-009 (engancha la verificación de tipos), TKT-061 (compara contra el borrador), TKT-063 (armazón sin conexión) y las pantallas de las historias de la fase 1.
