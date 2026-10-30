# CIMENTA · Tickets de trabajo

> **Capa SDD:** *Tasks*. Descompone las [historias de usuario](04-historias-usuario.md) en unidades de trabajo técnico.
>
> **Alcance:** los tickets necesarios para llevar el proyecto de cero a un sistema que cierra el ciclo de valor, en **dos fases**. La **fase 1 · hilo vertical** es el MVP indiscutible: importar la línea base, levantar una requisición, que se bloquee o se autorice, emitir la orden, recibir el material y ver el semáforo. La **fase 2 · mano de obra y campo** añade personal, destajo, nómina, captura sin conexión y evidencia. El corte está razonado en el [PRD §7](01-descripcion-producto.md#7-alcance-mvp-y-evolución) y en [ADR-017](adr/20261015-fuentes-simuladas-analitica.md).

---

## Cómo se usan estos tickets

### Dónde vive la estimación

**Los story points viven en la historia, no en el ticket.** Es deliberado y viene del material del Módulo 4: *"las tasks son artefactos del agente más que del humano; si la story está bien definida, las tasks las puede generar el copiloto en su Explore-Plan-Execute"*.

Estimar cada ticket en puntos y sumarlos produce dos problemas: doble contabilidad frente a la estimación de la historia, y falsa precisión sobre trabajo que el agente va a descomponer de otra forma. Por eso cada ticket lleva una **talla indicativa** —S, M, L— y la unidad de planificación sigue siendo el story point de la historia.

### Formato

Cada ticket declara **qué hace**, **criterios técnicos verificables** y **non-goals**. Los non-goals no son relleno: sin ellos, a un agente al que se le pide un endpoint le sale además el refactor del módulo, la documentación y una optimización de consultas — un PR de 800 líneas en lugar de 150.

### Tipos y su DoD

| Tipo | Cuándo | DoD aplicable |
|---|---|---|
| **Fundación** | Infraestructura y andamiaje previos a cualquier funcionalidad | Funcionalidad nueva, sin criterios de aceptación de negocio |
| **Funcionalidad** | Implementa parte de una historia | Funcionalidad nueva |
| **Documentación** | Documentación técnica o de API | Documentación |
| **Spike** | Investigación acotada con decisión al final | Spike |

Plantillas completas en [`convenciones.md` §6](convenciones.md#6-definition-of-done-por-tipo-de-trabajo).

### Rutas del API

Los tickets citan los endpoints por método y ruta con las convenciones del [borrador OpenAPI](api/openapi.yaml): base `/api/v1`, recursos en español, plural y `kebab-case`, importes como cadena decimal, y **las transiciones de estado como sub-recursos `POST`** —`/requisiciones/{id}/envio`, `/cancelacion`, `/resolucion`—, nunca como un `PATCH` del campo estado. Una transición es un caso de uso con su regla, su bitácora y su contrato de error; un `PATCH` genérico la esconde detrás de una edición.

**Si una ruta de un ticket y la del borrador difieren, manda el borrador**, y TKT-061 lo hace cumplir: es el contrato contra el que se generan el backend y los tipos del cliente.

### Regla que atraviesa todos los tickets

> Ningún ticket de funcionalidad se da por terminado si los escenarios de rechazo de su historia no pasan en verde. La [regla de aceptación](04-historias-usuario.md#regla-de-aceptación) aplica al ticket igual que a la historia.
>
> Cada escenario tiene al menos un test que lo nombra con la convención `test_hdu00X_escNN_…` ([ADR-012](adr/20260918-trazabilidad-escenario-test.md)); los tickets de HDU-003 en adelante dicen qué escenarios les tocan para que ninguno quede en tierra de nadie.

---

## Índice

| Fase | Bloque | Tickets | Historia | SP |
|---|---|---|---|---|
| 1 | [Épica 0 · Fundación](#épica-0--fundación) | TKT-001 … TKT-010, TKT-059, TKT-062 | — | ~42 |
| 1 | [HDU-001 · Obra y línea base](#tickets-de-hdu-001--obra-y-línea-base) | TKT-011 … TKT-018 | HDU-001 | 14 |
| 1 | [HDU-002 · Requisición](#tickets-de-hdu-002--requisición-con-control-de-presupuesto) | TKT-019 … TKT-024 | HDU-002 | 8 |
| 1 | [HDU-003 · Resolución de requisiciones bloqueadas](#tickets-de-hdu-003--resolución-de-requisiciones-bloqueadas) | TKT-025 … TKT-028 | HDU-003 | 5 |
| 1 | [HDU-004 · Proveedores y órdenes de compra](#tickets-de-hdu-004--proveedores-y-órdenes-de-compra) | TKT-029 … TKT-032 | HDU-004 | 5 |
| 1 | [HDU-005 · Entrada de material, en línea](#tickets-de-hdu-005--entrada-de-material-con-recepción-parcial) | TKT-033 … TKT-038, TKT-054 | HDU-005 | 8 de 11 |
| 1 | [HDU-006 · Semáforo de obra](#tickets-de-hdu-006--semáforo-de-obra) | TKT-039 … TKT-041, TKT-060 | HDU-006 | 6 |
| 1 | [Endurecimiento y operación](#endurecimiento-y-operación) | TKT-057, TKT-058, TKT-061 | — | ~8 |
| 2 | [Fase 2 · HDU-007 a HDU-009 y captura en campo](#fase-2--mano-de-obra-y-campo) | TKT-042 … TKT-053, TKT-055, TKT-056, TKT-063 … TKT-069 | HDU-005 (3 de 11), HDU-007, HDU-008, HDU-009 | 33 + ~10 |

**69 tickets · 79 SP en historias**, más ~60 fuera de ellas —~42 de fundación, ~8 de endurecimiento, ~8 del armazón de campo (TKT-063, TKT-065) y ~2 del adaptador real (TKT-069)—: **~96 SP en la fase 1** (46 + 50) y **~43 en la fase 2** (33 + 10). La numeración no es contigua: TKT-053 a TKT-056 se añadieron en revisiones posteriores y TKT-059 a TKT-068 en la revisión de la Entrega 1; todos se listan junto a la historia o al bloque al que sirven. TKT-053 es transversal a HDU-008 y HDU-009. El reparto en sprints de las dos fases está en el [plan de sprints](#plan-de-sprints).

**TKT-057 y TKT-058 salieron de la revisión del stack del 2026-09-19**, que encontró que la especificación no declaraba ningún requisito de seguridad ni de recuperación. Los requisitos están ahora en el [PRD §9](01-descripcion-producto.md#9-requisitos-no-funcionales) y estos dos tickets los implementan.

**TKT-059 a TKT-068 salieron de la revisión de LIDR del 2026-10-14**, que pidió tres cosas: detallar todos los tickets al nivel de los de HDU-001 y HDU-002, cerrar el bloque que estaba *pendiente de descomponer* y recortar el MVP a un hilo vertical. El bloque pendiente ya no existe: su contenido son ahora TKT-059 —el camino mínimo de `archivos`, en la fase 1— y TKT-063 a TKT-068, en la fase 2. TKT-060 sostiene las fuentes simuladas del semáforo ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md)); TKT-061 convierte el borrador de [`docs/api/openapi.yaml`](api/openapi.yaml) en prueba de contrato; TKT-062 pone a la IA a revisar cada PR sin darle la aprobación.

---

## Épica 0 · Fundación

**Talla: XL · ~42 SP.** Es lo que hay que construir antes de que la primera regla de negocio pueda existir. No entrega valor al cliente, y eso es esperado: entrega la capacidad de entregar valor.

Son los diez tickets originales, que suman ~35, más dos que nacieron de la revisión de la Entrega 1: **TKT-059**, el camino mínimo del módulo `archivos` (~5), porque el Excel de HDU-001 no puede pasar por el API, y **TKT-062**, la revisión automatizada de pull requests (~2), que viaja con el pipeline. El armazón sin conexión que antes vivía en TKT-008 **no** está aquí: es fundación de la fase 2 y es TKT-063.

---

### TKT-001 · Estructura del repositorio y herramientas base

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** — |

**Qué hace.** Crea la estructura del repositorio con backend y frontend separados, configura el gestor de dependencias de Python, el formateador y el linter, y escribe el `CLAUDE.md` del proyecto.

**Criterios técnicos**

- [ ] Estructura `backend/` y `frontend/` con sus respectivos gestores de dependencias
- [ ] Formateador y linter configurados: las **herramientas** las fija el [stack §8](06-stack-tecnologico.md#8-calidad-y-herramientas) —Ruff, mypy estricto sobre `dominio/`, ESLint, TypeScript strict—; las **versiones** las elige este ticket, tomando la última estable de cada una y fijándola en el archivo de bloqueo. El stack decide con qué se trabaja, no con qué número de parche
- [ ] `.gitignore`, `.editorconfig` y archivo de variables de entorno de ejemplo
- [ ] `CLAUDE.md` en la raíz con convenciones de código, comandos del proyecto y las reglas que no se pueden romper, tomadas de `llms.txt`
- [ ] `README.md` con instrucciones de arranque local verificadas en una máquina limpia

**Non-goals** — No configura CI (TKT-009). No instala framework web ni ORM (TKT-002).

---

### TKT-002 · Esqueleto del backend por capas y verificación de fronteras

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-001 |

**Qué hace.** Monta el esqueleto del backend con los diez módulos y las cuatro capas de cada uno, y añade la verificación automática de que ningún módulo cruza la frontera de otro.

**Criterios técnicos**

- [ ] Un paquete por módulo, diez en total: `identidad`, `auditoria`, `archivos`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica`
- [ ] `archivos` no importa a ningún otro módulo de negocio y ninguno importa su `dominio/` ni su `infraestructura/`: el contrato lo declara expresamente ([arquitectura §7.7](02-arquitectura.md#77-archivos-y-evidencia))
- [ ] `avance` y `personal` existen como paquetes vacíos desde el primer día aunque su contenido sea de la fase 2: el grafo de dependencias se declara entero una sola vez, no se reabre al llegar la fase
- [ ] Cada módulo con sus carpetas `api/`, `aplicacion/`, `dominio/`, `infraestructura/`
- [ ] Cada módulo expone su interfaz de aplicación publicada en un único punto de entrada
- [ ] Verificación automática de dependencias que falla si un módulo importa de `dominio/` o `infraestructura/` de otro
- [ ] La verificación falla también si `dominio/` importa del framework web o del ORM
- [ ] El grafo declarado coincide con el de [arquitectura §4](02-arquitectura.md#nivel-3--componentes-del-api): `analitica` solo lee

> Sin esta verificación, el monolito modular degenera en monolito con carpetas en pocos sprints. Es el ticket que sostiene [ADR-001](adr/20260918-monolito-modular.md).

**Non-goals** — No implementa lógica de ningún módulo.

---

### TKT-003 · PostgreSQL, migraciones y esquema de identidad

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-002 |

**Qué hace.** Levanta PostgreSQL para desarrollo, configura el sistema de migraciones, crea el esquema inicial de identidad y establece los tres roles de base de datos con sus permisos.

**Criterios técnicos**

- [ ] PostgreSQL disponible en local mediante contenedor, con datos persistentes entre arranques
- [ ] Sistema de migraciones configurado, con migración inicial aplicable y reversible
- [ ] Tablas `usuario`, `rol`, `usuario_rol`, `sesion` e `intento_acceso` según [modelo de datos §10](03-modelo-datos.md#10-identidad-y-auditoría)
- [ ] Los seis roles del PRD cargados como datos de arranque
- [ ] Convenciones del esquema aplicadas: identificadores UUID, columnas de auditoría, `TIMESTAMPTZ`
- [ ] **Roles de PostgreSQL creados en la migración**, no a mano en el servidor: la migración crea los de aplicación y de solo lectura; el de migración (propietario) lo crea el entorno (`RNF-09`), con `ALTER DEFAULT PRIVILEGES` para que toda tabla nueva nazca con los permisos por omisión de cada rol. **Cada migración de módulo revoca** lo que sus tablas no admiten, con su prueba en el mismo cambio ([modelo de datos §13](03-modelo-datos.md#13-invariantes-en-base-de-datos))
- [ ] El rol de aplicación **no** tiene `UPDATE` ni `DELETE` sobre `intento_acceso` — invariante 20
- [ ] Las pruebas de permisos sobre `explosion_presupuesto` y `linea_base_concepto` —`SELECT … FOR UPDATE` con el rol de aplicación y el disparador del invariante 14— **no son de este ticket**: esas tablas las crea TKT-011, que es quien revoca y prueba. Aquí solo existen las tablas de identidad
- [ ] El rol de solo lectura no tiene más que `SELECT` — invariante 21
- [ ] `lock_timeout` y `statement_timeout` fijados **en el rol de aplicación** (`RNF-16`), de modo que apliquen aunque una ruta nueva no los pida
- [ ] Los tests corren contra PostgreSQL, **no** contra SQLite, construyen el esquema con `alembic upgrade head` y **se conectan con el rol de aplicación**

> Probar contra SQLite para "ir más rápido" verificaría garantías distintas de las de producción. El decimal exacto y las restricciones declarativas son parte del diseño, no un detalle del motor.
>
> **Conectarse con el propietario en los tests anularía tres invariantes.** Los números 10, 20 y 21 son permisos: con el rol propietario, el `UPDATE` sobre la bitácora funciona y la prueba que lo intenta queda verde por no tener nada que verificar.

**Non-goals** — No crea tablas de negocio: cada módulo trae las suyas. No implementa autenticación (TKT-006).

---

### TKT-004 · Tipos base del dominio con decimal exacto

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-002 |

**Qué hace.** Define los objetos de valor compartidos —`Dinero`, `Cantidad`, `Rendimiento`, `Porcentaje`— con decimal exacto, y prohíbe la coma flotante en todo el sistema.

**Criterios técnicos**

- [ ] Tipos implementados sobre decimal de precisión fija, nunca flotante
- [ ] Precisiones según [modelo de datos §2](03-modelo-datos.md#2-convenciones)
- [ ] Las operaciones conservan la precisión completa; el redondeo es una operación explícita y separada
- [ ] Serialización a JSON **como cadena**, nunca como número
- [ ] Un test verifica que `0.1 + 0.2` da exactamente `0.3`
- [ ] Un test verifica que sumar los 27 insumos de la explosión real reproduce el total del Excel sin desviación
- [ ] Regla del linter que falla si aparece un flotante en una firma de dominio

**Non-goals** — No implementa conversión de divisas: el sistema es en pesos mexicanos.

---

### TKT-005 · Contrato de error de regla de negocio

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-002 |

**Qué hace.** Implementa el tipo de excepción de regla de negocio y el manejador global que lo traduce al contrato de error estructurado.

**Criterios técnicos**

- [ ] Excepción de aplicación —la lanza el caso de uso a partir del resultado de la función de regla, que sigue pura— que transporta identificador de regla, mensaje, detalle y acciones
- [ ] Manejador global que la serializa según [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio)
- [ ] **Los siete `tipo` del borrador [`openapi.yaml`](api/openapi.yaml), más el `404`**: `REGLA_NEGOCIO` (`409`, con `regla`), `VALIDACION` (`422`), `PERMISO` (`403`), `CONFLICTO` (`409`, con `codigo`), `CONCURRENCIA` (`409`, con cabecera `Retry-After` y la acción `REINTENTAR`), `SESION` (`401`), `LIMITE_INTENTOS` (`429`) y `NO_ENCONTRADO` (`404`). El cliente distingue los `409` por `tipo`, nunca por el texto
- [ ] **Catálogo cerrado de `codigo`** para `CONFLICTO` —el enum `CodigoConflicto` del borrador—: un `codigo` fuera del catálogo no se puede construir, y ampliarlo se hace en el mismo cambio que añade el caso que lo produce
- [ ] **Un `409` que no viola una `RN` es `CONFLICTO` con `codigo`**, nunca un `RN-xx` inventado: un estado que no admite la operación, un duplicado o una precondición ausente no son reglas del PRD, y asentarlos como tales contaminaría la consulta de excepciones de `RN-04`
- [ ] **Las `acciones` se filtran por los roles de quien llama**: nunca se ofrece una acción que le daría `403`, salvo `REINTENTAR` de un `409` `CONCURRENCIA`. Un test construye el mismo rechazo para dos usuarios con roles distintos y verifica que las acciones difieren
- [ ] Todos los importes del detalle se serializan como cadena
- [ ] El identificador de regla admite únicamente valores con formato `RN-\d{2}`
- [ ] Un test por `tipo` que verifica la forma exacta de la respuesta contra su esquema del borrador
- [ ] **Registro estructurado en JSON con `structlog` e identificador de correlación por petición**, devuelto también en el cuerpo del error para que el usuario pueda citarlo (`RNF-13`)

> Es la base sobre la que se escriben todos los escenarios de rechazo de las nueve historias — cerca de la mitad de todos. Si llega tarde, cada historia inventa su propio formato de error.
>
> **El identificador de correlación vive aquí y no en TKT-058** porque tiene que viajar **dentro** del contrato de error, y porque el patrón de registro hay que establecerlo antes de que existan diez módulos que lo ignoren. Retrofitar el registro estructurado en el sprint de cierre sería tocar los diez. Lo que sí queda en TKT-058 es la **agregación** de errores, que es un servicio externo y no se puede contratar antes de tener qué agregar.

**Non-goals** — No implementa ninguna regla concreta. No agrega errores en ningún servicio externo: eso es TKT-058.

---

### TKT-006 · Autenticación y autorización por rol

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-003, TKT-005, TKT-007 |

**Qué hace.** Implementa inicio de sesión, sesión autenticada y comprobación de permisos por rol, incluida la prohibición de auto-autorización.

**Criterios técnicos**

- [ ] Inicio y cierre de sesión con contraseña derivada con `pwdlib[argon2]` — Argon2id, parámetros en configuración (`RNF-03`)
- [ ] **El inicio de sesión verifica un hash siempre**, exista el usuario o no, comparando contra un hash de descarte cuando el correo no está: de otro modo el tiempo de respuesta revela qué cuentas existen
- [ ] Sesión con estado en la tabla `sesion` ([ADR-014](adr/20260919-sesion-con-estado.md)); la cookie lleva un identificador opaco, `HttpOnly`, `Secure`, `SameSite=Lax` (`RNF-01`, `RNF-02`)
- [ ] Caducidad absoluta y por inactividad; cerrar sesión escribe `revocada_en` y **no** borra la fila
- [ ] **Desactivar un usuario o retirarle un rol surte efecto en la petición siguiente**, con test que lo comprueba
- [ ] Comprobación de permiso por rol en la capa `api`
- [ ] Un usuario puede acumular varios roles; el permiso efectivo es la unión
- [ ] Regla de no-auto-autorización implementada en `dominio/`, no en la interfaz, y probada sin HTTP
- [ ] Un intento sin permiso responde `403` y se asienta en la bitácora como `DENEGAR`, **en una transacción propia** —no hay cambio que acompañar— y siempre con usuario autenticado. Las denegaciones anónimas —token de doble envío ausente, credenciales erróneas al iniciar sesión— van a `intento_acceso` y al registro técnico, no a la bitácora: `bitacora.usuario_id` sigue `NOT NULL`
- [ ] **Solo dos rutas no exigen sesión: `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion`.** Un test **recorre el enrutador**, lo compara con esa lista cerrada y falla si cualquier otra ruta queda sin proteger
- [ ] Emite el token de doble envío en `GET /api/v1/sesion/csrf` (cookie `cimenta_csrf` sin `HttpOnly` y el mismo valor en el cuerpo); **verificarlo** en las rutas que mutan, rotarlo y el `403` `ORIGEN_NO_VERIFICADO` son de TKT-057

> **No se usa `passlib`.** Sin versión nueva desde 2020 en la pieza que guarda las contraseñas de seis roles que autorizan gasto. `pwdlib` hace lo mismo, se mantiene, y es lo que usan los ejemplos públicos de FastAPI — que por el criterio C3 del [stack §1](06-stack-tecnologico.md#1-cómo-se-eligió) cuenta.

**Non-goals** — No implementa recuperación de contraseña, segundo factor ni inicio de sesión federado. No implementa permisos por obra: el MVP autoriza por rol. **No implementa el límite de intentos, la verificación CSRF ni las cabeceras de seguridad: son TKT-057**, que viaja en el mismo sprint.

---

### TKT-007 · Bitácora transversal de solo-anexado

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-003 |

**Qué hace.** Crea la tabla `bitacora`, el servicio para escribir en ella dentro de la transacción en curso, y los permisos que la hacen inmutable.

**Criterios técnicos**

- [ ] Tabla `bitacora` según [modelo de datos §10](03-modelo-datos.md#10-identidad-y-auditoría). `bitacora.obra_id` es un identificador lógico **sin clave foránea**: `auditoria` es transversal y no depende de `presupuesto` ([modelo de datos §2](03-modelo-datos.md#2-convenciones))
- [ ] El enum `accion` completo, el mismo del modelo §10 y de `AccionBitacora` en el borrador: `CREAR`, `ACTUALIZAR`, `EVALUAR`, `BLOQUEAR`, `AUTORIZAR`, `RECHAZAR`, `CANCELAR`, `EMITIR`, `AJUSTAR`, `REPROGRAMAR`, `CONGELAR`, `RECAPTURAR`, `DESCARTAR`, `CONFIRMAR`, `ANULAR`, `SUSPENDER`, `REACTIVAR`, `CERRAR`, `DESACTIVAR`, `LIBERAR`, `VALIDAR`, `DENEGAR`
- [ ] El asiento se escribe en **la misma transacción** que el cambio: si la bitácora falla, el cambio se deshace
- [ ] El rol de aplicación tiene `INSERT` y `SELECT`, y **no** `UPDATE` ni `DELETE` ni `TRUNCATE`
- [ ] Un test verifica que un `UPDATE` sobre la bitácora falla a nivel de motor
- [ ] Consulta por obra, por rango de fechas y por regla de negocio —parámetro `regla_negocio`—, **paginada** y con el asiento más reciente primero, como caso de uso `consultar_bitacora` publicado en `cimenta.auditoria.interfaz`. **Sin ruta HTTP**: `GET /api/v1/bitacora` la monta TKT-027
- [ ] Servicio aparte, `asentar_denegacion`, para asentar un `403` como `DENEGAR` en **una transacción propia** —la abre quien llama, separada de la de la petición—, siempre con usuario autenticado y atribuido a él (`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`): es la única escritura de la bitácora que no acompaña a un cambio, y la usa TKT-006
- [ ] Índices `(obra_id, ocurrido_en DESC)` y parcial sobre `regla_negocio`

> Registrar después del cambio, o en un proceso aparte, produce huecos precisamente en los casos de error — que son los que importan.

**Non-goals** — No monta la ruta `GET /api/v1/bitacora` ni implementa interfaz de consulta: la ruta la monta TKT-027 con `exigir_rol`, y completa el nombre del usuario.

---

### TKT-008 · Esqueleto del frontend y cliente de API

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-005, TKT-006 |

**Qué hace.** Monta la aplicación React con navegación, inicio de sesión, el cliente de API que entiende el contrato de error y los componentes reutilizables que todas las historias van a necesitar.

**Criterios técnicos**

- [ ] Aplicación de página única con enrutado y estructura de carpetas por módulo de negocio
- [ ] Pantalla de inicio de sesión funcional contra TKT-006
- [ ] Navegación que muestra solo las secciones permitidas por los roles del usuario
- [ ] **Los tipos del cliente se generan del OpenAPI** que FastAPI publica (`openapi-typescript`), exportado sin servidor en marcha, con `npm run tipos:generar`; `npm run tipos:verificar` falla si el archivo versionado difiere de lo que se generaría. Engancharlo al pipeline es de TKT-009. Los tipos del contrato de error salen del borrador como provisionales hasta que FastAPI publique sus esquemas
- [ ] Cliente de API que reconoce el contrato de error y expone regla, detalle y acciones a los componentes
- [ ] Los esquemas Zod validan **formularios**, no respuestas: no se escribe ningún esquema que espeje un modelo de Pydantic
- [ ] Componente reutilizable de **pantalla de bloqueo** que renderiza cualquier violación de regla mostrando las cifras del detalle y botones para las acciones disponibles
- [ ] Componente reutilizable de **formulario de catálogo** con apertura, foco en el primer campo, validación y confirmación de baja — lo usan HDU-001, HDU-004 y HDU-007
- [ ] Componente reutilizable de **captura de motivo obligatorio** — lo usan HDU-003, HDU-005 y HDU-007
- [ ] Los importes recibidos como cadena se convierten con decimal exacto, nunca con el número nativo
- [ ] Diseño usable en escritorio **y en pantalla de teléfono**: la recepción de material ocurre de pie en el almacén de obra, y en la fase 2 también la medición
- [ ] Los tipos generados se comprueban además contra el borrador [`docs/api/openapi.yaml`](api/openapi.yaml) por la prueba de contrato de TKT-061: el cliente se genera de lo que el servidor publica, y lo que publica tiene que coincidir con lo que se especificó

> Los tres componentes reutilizables salen de escenarios que se repiten en varias historias. Extraerlos aquí evita tres implementaciones divergentes de la misma pantalla.
>
> **El armazón sin conexión salió de este ticket y es TKT-063, en la fase 2.** Antes vivía aquí por la misma razón que el contrato de error —si llega después, cada flujo de campo inventa su cola—, y esa razón sigue en pie: por eso TKT-063 es un ticket de fundación propio y llega **antes** que el primer flujo diferible, no junto a él. Lo que cambió es que en la fase 1 no hay ningún flujo diferible: la recepción de HDU-005 es en línea. Montar un service worker y una cola sin nada que encolar es código que nadie ejerce durante toda la fase 1.

**Non-goals** — No implementa ninguna pantalla de negocio. **No monta el armazón sin conexión** —service worker, caché persistida, cola en IndexedDB, sincronización, indicador de estado—: es TKT-063. No permite iniciar sesión sin conexión.

#### Partición en tres tickets hermanos

TKT-008 se ejecuta como tres tickets hermanos que comparten la spec y el diseño de [`sdd/tickets/tkt-008/`](../sdd/tickets/tkt-008/_index.md). El diseño aprobado el 2026-10-26 suma unas 4,600 líneas escritas a mano, más de diez veces el tope de unas 400 por cambio que fija la metodología. Partirlo en tres deja cada parte revisable por separado y permite que dos de ellas avancen en paralelo. TKT-008 queda como ticket paraguas: se cierra cuando se cierran los tres.

Que otro ticket dependa de TKT-008 significa que depende de los tres. Un consumidor que solo use una pieza puede arrancar en cuanto esa pieza esté cerrada. Las pantallas de negocio dependen de TKT-008a para el cliente y los tipos, de TKT-008b para el inicio de sesión y el armazón, y de TKT-008c si usan alguno de los componentes reutilizables.

| Ticket | Contenido | Talla | Depende de | Filas del diseño |
|---|---|---|---|---|
| TKT-008a | Andamiaje, generación de tipos, cliente de API y dinero | M | TKT-005, TKT-006 | 1 a 7 |
| TKT-008b | Enrutado, inicio de sesión, armazón por rol, humo de Playwright y documentación | M | TKT-008a | 8, 9, 10, 14, 16 y su parte de la 15 |
| TKT-008c | Pantalla de bloqueo, formulario de catálogo y captura de motivo | M | TKT-008a | 11, 12, 13 y su parte de la 15 |

##### TKT-008a · Andamiaje, tipos, cliente de API y dinero

**Qué hace.** Instala y configura la aplicación de cliente: React, Vite, Tailwind v4, las primitivas de shadcn/ui y las reglas de ESLint del proyecto. Genera los tipos del servidor y del contrato de error, y monta el cliente de API con la prueba de origen y la normalización del contrato de error. Deja también el módulo de dinero con `decimal.js`.

- [ ] `npm run dev` sirve el cliente y reenvía `/api/v1` al backend en el mismo origen
- [ ] Tipos generados con `openapi-typescript`: los del servidor salen del OpenAPI publicado y los del contrato de error, provisionales, del borrador. Un comando del proyecto falla si el archivo versionado difiere
- [ ] El cliente pone `X-CSRF-Token` en todo método que muta estado y normaliza toda respuesta de error a una unión discriminada por `tipo`
- [ ] El dinero y las cantidades pasan por `decimal.js`. Ninguna regla de ESLint permite `Number`, `parseFloat`, `parseInt` ni el `+` unario fuera del módulo de dinero, y Zod no se importa fuera de los formularios

##### TKT-008b · Inicio de sesión, armazón por rol y humo

**Qué hace.** Monta el enrutado, la estructura de carpetas por módulo de negocio, la pantalla de inicio de sesión con sus cinco estados de rechazo y el armazón con la navegación por rol. Suma el recorrido de humo de Playwright contra el backend real y la documentación del arranque.

- [ ] Pantalla de inicio de sesión funcional contra TKT-006, con sus rechazos del [wireframe §1](08-wireframes.md#1-inicio-de-sesión)
- [ ] Navegación que muestra la unión de las secciones de los roles del usuario, con una ruta marcador por sección ([wireframe §2](08-wireframes.md#2-armazón-de-navegación-por-rol))
- [ ] Un `401` fuera del inicio de sesión devuelve al inicio con el aviso de sesión terminada; un `403` vuelve a pedir la sesión
- [ ] Recorrido de humo de Playwright: iniciar sesión, ver el armazón y cerrar sesión
- [ ] `CLAUDE.md` y `docs/arranque-local.md` describen el arranque real del cliente

##### TKT-008c · Componentes reutilizables

**Qué hace.** Construye los tres componentes que usan las historias de la fase 1. La pantalla de bloqueo pinta cualquier `409`. El formulario de catálogo abre con el foco en el primer campo, valida, pinta el `422` y el duplicado en línea, y pide confirmación antes de una baja. La captura de motivo no envía sin motivo.

- [ ] Pantalla de bloqueo del [wireframe §6](08-wireframes.md#6-pantalla-de-bloqueo), con las cifras del detalle formateadas con `decimal.js` y un botón por cada acción del contrato
- [ ] Formulario de catálogo, que usan HDU-001, HDU-004 y HDU-007
- [ ] Captura de motivo obligatorio, que usan HDU-001, HDU-003, HDU-005 y HDU-007

> TKT-008c es la pieza que la costura del sprint 1 ya preveía mover: si el sprint no aguanta, cada componente viaja con su primer consumidor sin rehacer nada.

---

### TKT-009 · Pipeline de integración continua

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-002, TKT-008 |

**Qué hace.** Configura CI con tests, verificación de fronteras entre módulos, trazabilidad escenario ↔ test y calidad de documentación, y deja el sitio donde se enganchan la prueba de contrato de TKT-061 y la revisión de TKT-062.

**Criterios técnicos**

- [ ] Trabajo de tests de backend contra PostgreSQL real, con testcontainers y reporte de cobertura. **MinIO no entra en este ticket**: su servicio y sus pruebas llegan con TKT-059, que los añade a ese mismo trabajo. Antes de TKT-059 no existe el adaptador de almacén que usaría MinIO, así que levantarlo aquí no comprobaría nada
- [ ] Trabajo de frontend: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` y **`npm run tipos:verificar`**, este último con **`uv` y Node en el mismo trabajo** y `uv sync --locked --python 3.14` hecho en `backend/`, con el intérprete fijado como en [`arranque-local.md`](arranque-local.md) (TKT-008, `PA-T10`)
- [ ] Trabajo del humo de Playwright, `npm run e2e`, con Docker, la base migrada, las contraseñas de los roles fijadas y un `.env` construido desde `.env.example` (TKT-008)
- [ ] Trabajo de verificación de fronteras entre módulos (TKT-002), que falla el pipeline si se cruzan
- [ ] **Verificador de escenarios sin test** ([ADR-012](adr/20260918-trazabilidad-escenario-test.md), [stack §7.2](06-stack-tecnologico.md#72-trazabilidad-escenario--test)): recorre [`04-historias-usuario.md`](04-historias-usuario.md), extrae cada `HDU-00X esc. N` y falla si un escenario **que cuenta** no tiene un test que lo nombre con la convención `test_hdu00X_escNN_…`. **Un escenario cuenta desde que su historia tiene un ticket en curso**: el verificador lee `tools/historias_activas.txt` —una historia por línea, que se actualiza al arrancar cada sprint—, y los marcados **fase 2** cuentan además solo cuando la fase 2 empieza. Los que todavía no cuentan se informan como pendientes y no fallan el pipeline. Un escenario retirado con el segmento `· retirado por TKT-0NN` en su título —HDU-006 esc. 14 y 15, al retirar el adaptador simulado con TKT-069— deja de contar. Los tickets de **fundación** sin historia propia nombran sus tests por criterio, `tkt0NN_caNN_escNN_…` en pytest y `"tkt0NN_caNN_escNN · …"` en Vitest y Playwright (`PA-T4` de TKT-008): el verificador los admite y no los cuenta como huérfanos
- [ ] Trabajo **reservado** para la prueba de contrato de TKT-061: aquí se declara el paso y su posición —después de los tests de backend, antes de la generación de tipos—; el contenido lo pone TKT-061
- [ ] La revisión automatizada de TKT-062 es un flujo de trabajo **aparte** que comenta y nunca bloquea: este pipeline no depende de ella ni la espera
- [ ] **Auditoría de dependencias**: `pip-audit` y `npm audit`, que fallan el pipeline ante severidad alta (`RNF-08`)
- [ ] **Dependabot** para actualizaciones y **escaneo de secretos** activado sobre el repositorio (`RNF-07`)
- [ ] Calidad de documentación: linter de Markdown, linter de prosa y detector de enlaces rotos
- [ ] Vocabulario del proyecto declarado para el linter de prosa, tomado del [glosario](glosario.md): *tablaroca*, *destajo*, *perfacinta*, *antepecho*, *cajillo*, *plafón*, *redimix*, *CIMENTA*
- [ ] Detector de enlaces también en cron semanal
- [ ] Nivel de aviso en local, nivel de error en CI

**Non-goals** — No configura despliegue: se decide en el Paso 5.

#### Partición en cuatro tickets hermanos

TKT-009 se ejecuta como cuatro tickets hermanos que comparten la spec y el diseño de [`sdd/tickets/tkt-009/`](../sdd/tickets/tkt-009/_index.md). El diseño aprobado el 2026-10-28 suma unas 1,230 líneas escritas a mano, tres veces el tope de unas 400 por cambio que fija la metodología. TKT-009 queda como ticket paraguas: se cierra cuando se cierran los cuatro.

**El orden de fusión es fijo: a → c → b → d.** Las tres últimas editan los mismos documentos —`docs/06-stack-tecnologico.md`, `tools/README.md` y `docs/arranque-local.md`— y la limpieza documental de TKT-009d recorre todo `docs/` y `sdd/`, incluido `docs/04-historias-usuario.md`, que TKT-009c lee y modifica. Cada parte se rebasa sobre la anterior ya fusionada antes de abrir su PR.

Que otro ticket dependa de TKT-009 significa que depende de los cuatro. TKT-061 solo necesita TKT-009a, que declara el trabajo reservado, y TKT-062 solo necesita que el pipeline de TKT-009a esté en verde.

| Ticket | Contenido | Talla | Depende de | Filas del diseño |
|---|---|---|---|---|
| TKT-009a | Pipeline de pruebas y fronteras | S | TKT-002, TKT-008 | A0 a A8 |
| TKT-009c | Verificador de escenarios sin test | M | TKT-009a | C1 a C6 |
| TKT-009b | Auditoría de dependencias, Dependabot y escaneo de secretos | M | TKT-009a | B1 a B7 |
| TKT-009d | Calidad de documentación | M | TKT-009a, y fusiona después de TKT-009b | D1 a D7 |

##### TKT-009a · Pipeline de pruebas y fronteras

**Qué hace.** Crea el flujo de GitHub Actions `ci.yml`, disparado por `pull_request` y con permisos mínimos, con los trabajos de backend, fronteras entre módulos, frontend, humo de Playwright, suite de `tools/`, seguridad de los workflows y `verificar_docs.py`. Declara el trabajo reservado de TKT-061 y no depende de la revisión de TKT-062. **Los tests de backend corren contra PostgreSQL y no contra MinIO**: MinIO llega con TKT-059, que lo añade al trabajo `backend`.

- [ ] Trabajo de backend con formato, lint, tipos, `verificar_float` y `pytest` contra PostgreSQL real con testcontainers, y reporte de cobertura sin umbral
- [ ] Trabajo de fronteras, de frontend con `tipos:verificar` y del humo de Playwright, con los pasos que documenta [`arranque-local.md`](arranque-local.md)
- [ ] Trabajo reservado para TKT-061 entre los tests de backend y la generación de tipos, y ninguna dependencia de TKT-062
- [ ] Permisos mínimos: `contents: read` y sin `pull_request_target`

##### TKT-009c · Verificador de escenarios sin test

**Qué hace.** Escribe `tools/verificar_escenarios.py` y `tools/historias_activas.txt` y engancha el verificador al pipeline. Falla ante un escenario que cuenta y no tiene test, informa los pendientes, admite los nombres de los tickets de fundación y deja de exigir los escenarios retirados con el segmento `· retirado por TKT-0NN` en su título.

- [ ] Un escenario activo sin test falla el pipeline y se nombra; uno todavía no activo se informa como pendiente
- [ ] Los escenarios de fase 2 no cuentan hasta que `historias_activas.txt` contiene la línea `fase 2`, y una historia no sale nunca del archivo
- [ ] Un test que nombra una historia o un escenario inexistentes falla; los nombres de fundación se admiten y los demás se ignoran

##### TKT-009b · Cadena de suministro

**Qué hace.** Audita las dependencias de Python y de npm y falla ante severidad alta, activa Dependabot y deja verificado el escaneo de secretos del repositorio.

- [ ] `pip-audit` con un filtro de severidad que falla ante `HIGH`, `CRITICAL` o severidad desconocida, y `npm audit --audit-level=high`
- [ ] `.github/dependabot.yml` para `uv`, `npm` y `github-actions` y, desde TKT-009d, `npm` en `.github/mermaid`
- [ ] Escaneo de secretos y protección de empuje activos, comprobados con `gh api` y un empuje de ensayo con un token personal activo y sin permisos, que la protección rechaza (`GH013`)

La política de severidad de `pip-audit` y su motivo están en el [ADR del 2026-10-29](adr/20261029-severidad-en-la-auditoria-de-dependencias.md).

##### TKT-009d · Calidad de documentación

**Qué hace.** Configura `markdownlint-cli2`, `Vale` con el vocabulario del glosario, `lychee` y `mermaid-cli` en el pipeline, y el detector de enlaces en un cron semanal. Limpia la línea base de avisos, que nunca se había ejecutado: aviso en local y error en CI.

- [ ] Trabajo `documentacion` con los cuatro verificadores, y vocabulario del proyecto declarado para `Vale`
- [ ] Línea base limpia, medida antes de editar: si supera 120 hallazgos que `--fix` no corrige, la limpieza se separa en su propio ticket
- [ ] Detector de enlaces también en cron semanal

La decisión sobre la prosa en español y su motivo están en el [ADR del 2026-10-29](adr/20261029-vale-para-prosa-en-espanol.md).

---

### TKT-062 · Revisión automatizada de pull requests con Claude Code

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-001, TKT-009 · **Sprint 1**, o el 4 si se usa la costura del sprint 1 |

**Qué hace.** Añade un flujo de GitHub Actions con `anthropics/claude-code-action` que revisa cada pull request contra `CLAUDE.md`, las reglas no negociables y el ticket enlazado, y **comenta**. No aprueba ni fusiona: la aprobación sigue siendo de una persona. Añade además la etiqueta de origen obligatoria sobre la que se mide la velocidad.

**Criterios técnicos**

- [ ] Flujo propio, separado del pipeline de TKT-009, que se dispara al abrir un PR, al empujar a él y al sacarlo de borrador; los borradores no se revisan
- [ ] El token del flujo tiene permiso de **lectura** sobre el contenido y de **escritura solo sobre comentarios del PR**: sin escritura sobre el contenido no puede empujar commits, y el ajuste del repositorio que impide a GitHub Actions aprobar PR lo impide aunque lo intente
- [ ] La rama `Produccion` exige **al menos una aprobación humana** y el pipeline de TKT-009 en verde. Esto vale para todas las personas salvo la administradora del repositorio, que con `enforce_admins: false` puede fusionar con `--admin` sin esa aprobación; esa omisión solo es legítima con las diez comprobaciones requeridas en verde ([convenciones §6](convenciones.md#6-definition-of-done-por-tipo-de-trabajo)). La revisión automatizada **no** es una comprobación requerida: si falla o tarda, el PR no se bloquea
- [ ] Las instrucciones de revisión viven versionadas en el repositorio y remiten a `CLAUDE.md` en lugar de copiarlo: una copia divergiría al primer cambio de las reglas
- [ ] La revisión busca lo que un linter no ve, y **la lista de qué busca es una sola: la de [convenciones §12](convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)**. Las instrucciones de revisión remiten a ella en lugar de copiarla, igual que a `CLAUDE.md`, y este ticket no mantiene otra
- [ ] **Cada hallazgo cita lo que incumple** —la regla de `CLAUDE.md`, el `RN-xx`, el invariante o el *non-goal* del ticket—; un comentario sin cita no se publica. Es lo que separa una revisión de una opinión
- [ ] El PR enlaza su ticket (`TKT-0XX` en el título o en el cuerpo); si no lo hace, es el primer hallazgo, porque sin ticket no hay *non-goals* contra los que revisar
- [ ] **Etiqueta de origen** obligatoria —`human`, `human+copilot`, `agent`, `agent+human-review`—, comprobada por una verificación mecánica, no por la IA: el PR sin exactamente una etiqueta no pasa la comprobación requerida. La administradora puede fusionar con `--admin` porque `enforce_admins: false`; que no lo haga sin las diez comprobaciones en verde, la de la etiqueta incluida, es una convención del proyecto ([convenciones §6](convenciones.md#6-definition-of-done-por-tipo-de-trabajo)). Es la base del [seguimiento honesto de la velocidad](#seguimiento-honesto-de-la-velocidad)
- [ ] La clave de API vive en los secretos del repositorio, nunca en el flujo, y el flujo **no se ejecuta sobre PR que vienen de bifurcaciones**: un secreto expuesto a código ajeno es un secreto publicado (`RNF-07`)
- [ ] Turnos y tiempo de la revisión acotados en la configuración **(asumido: los valores se fijan con el primer mes de uso real)**
- [ ] Se prueba con un PR de ensayo que viola a propósito dos reglas —un `float` en una firma de dominio y una ruta `async def`— y se verifica que **las dos** se comentan con su cita y que el PR sigue sin poder fusionarse sin aprobación humana

> **Comenta y no aprueba, y es la decisión central del ticket.** Buena parte del código lo escriben agentes; un agente que aprueba lo que escribió otro agente cierra el circuito sin que ninguna persona haya leído el cambio, y la Definition of Done de cada historia exige *revisión de al menos un humano*. La IA en la revisión sirve para que esa persona llegue al PR con los hallazgos ya citados, no para sustituirla.
>
> **Viaja con TKT-009 y no después** porque la etiqueta de origen tiene que estar desde los primeros PR de funcionalidad: sin ella, la comparación de defectos entre PR de agente y PR humanos no tiene línea base.

**Non-goals** — No aprueba, no fusiona, no empuja commits ni propone correcciones aplicables con un clic. No sustituye a Ruff, mypy ni `import-linter`: lo que se comprueba mecánicamente lo comprueba el pipeline. No mide la calidad segmentada por etiqueta: eso se reporta al cerrar cada sprint.

#### Partición en dos tickets hermanos

TKT-062 se ejecuta como dos tickets hermanos que comparten la spec y el diseño de [`sdd/tickets/tkt-062/`](../sdd/tickets/tkt-062/_index.md). El diseño aprobado el 2026-10-29 suma unas 1,410 líneas escritas a mano, más de tres veces el tope de unas 400 por cambio que fija la metodología, y la persona responsable aprobó partirlo en dos en ese mismo gate. TKT-062 queda como ticket paraguas: conserva la spec y el diseño comunes y se cierra cuando se cierran los dos tickets.

**El orden de fusión es fijo: a → b.** 062b usa la protección de `Produccion` que aplica 062a, la comprobación «Etiqueta de origen» que corre en sus PR y las constantes de la guarda de revisión, que nacen en 062a. La rama de 062b se crea desde `Produccion` con 062a ya fusionado.

| Ticket | Musts | Contenido | Líneas estimadas | Depende de | Filas del diseño |
|---|---|---|---|---|---|
| TKT-062a | M5, M8 y M11 en su parte | Etiqueta de origen obligatoria | ~490 (≈ 170 de código y documentación y ≈ 320 de pruebas) | TKT-009 (archivado) | A0 a A8 |
| TKT-062b | M1 a M4, M6, M7, M9, M10, M8 y M11 en su parte, S1 | Revisión automatizada | ~920 (≈ 400 de código y documentación y ≈ 520 de pruebas) | TKT-062a | B1 a B3b, B6 a B8 (B4 y B5 retiradas, ver `_index.md`) |

Entre las dos fichas cubren los Musts M1 a M11 y el Should S1. M8 y M11 se reparten entre ambas, cada una con su parte.

##### TKT-062a · Etiqueta de origen obligatoria

**Qué hace.** Exige una etiqueta de origen en cada pull request —`human`, `human+copilot`, `agent` o `agent+human-review`— mediante el flujo propio `etiqueta-origen.yml`, que ejecuta un script de la biblioteca estándar sin IA y sin secretos. Esa comprobación es requerida en `Produccion`, junto con el pipeline de TKT-009. Crea las cuatro etiquetas en el repositorio, añade la etiqueta `agent` a los PR de Dependabot y establece la regla de que todo cambio a `Produccion` entra por un PR, también los cierres de ticket.

- [ ] Flujo `etiqueta-origen.yml`, con el disparador `synchronize`, que falla sin exactamente una etiqueta de origen. Su trabajo se llama «Etiqueta de origen», que es el contexto que exige la protección. `ci.yml` no cambia
- [ ] `tools/etiqueta_origen.py` en la biblioteca estándar: con ninguna etiqueta de origen o con dos falla, con una pasa, y el mensaje nombra las etiquetas halladas
- [ ] Las cuatro etiquetas existen en el repositorio y las cuatro entradas de `.github/dependabot.yml` añaden `labels:` con `agent`
- [ ] Protección de `Produccion` con el pipeline y «Etiqueta de origen» como comprobaciones requeridas, con `enforce_admins: false`, y con la lista de colaboradores como evidencia
- [ ] La regla «todo entra por PR» figura en §6 y §11 de las convenciones, con su porqué, y en los documentos del toolkit que listan los orígenes
- [ ] Las reglas comunes de TKT-009 se aplican a todo flujo de `.github/workflows/`, con la única excepción nombrada de la guarda de revisión que nace aquí y se usa en TKT-062b

**Cierra cuando.** A8 en verde, con la evidencia de A5 y A6 en su `impl.md`.

**Non-goals** — No revisa el contenido del PR, ni con IA ni con reglas: solo cuenta etiquetas. No toca `ci.yml`, porque un `labeled` allí relanzaría los nueve trabajos. No mide la velocidad por etiqueta: eso se reporta al cerrar cada sprint.

##### TKT-062b · Revisión automatizada

**Qué hace.** Añade el flujo `revision-ia.yml`, que ejecuta `anthropics/claude-code-action` sobre el PR con una clave de API dedicada y con un token que solo lee, de modo que el trabajo que ejecuta el modelo no tiene permiso de escritura. Un trabajo aparte, sin secreto y sobre la rama base, publica un único comentario tras filtrar los hallazgos que no traen una cita válida o que contienen algo con forma de clave (`tools/publicar_revision.py`). Incluye las instrucciones versionadas en `.claude/revision-pr.md`, la excepción nombrada que permite leer `secrets.` solo en ese flujo, el ADR-028 y los PR de ensayo.

- [ ] Flujo que se dispara al abrir o reabrir un PR, al empujar a él y al sacarlo de borrador, y que no revisa los borradores
- [ ] La guarda del trabajo excluye las bifurcaciones y los PR de Dependabot, que no reciben secretos
- [ ] El trabajo que lee el PR tiene `contents: read` y `pull-requests: read`, ninguna herramienta de escritura y lectura acotada al árbol de trabajo. El trabajo `publicar` tiene `pull-requests: write` y no tiene el secreto
- [ ] Los dos trabajos hacen checkout de la rama base, no del PR. `.claude/revision-pr.md` enlaza `CLAUDE.md` y convenciones §12 en lugar de copiarlos
- [ ] Un hallazgo sin cita válida, o con algo con forma de clave, no se publica. El título y el cuerpo del PR entran por variable de entorno, nunca interpolados en `run:`
- [ ] El PR sin ticket y el que toca `docs/api/openapi.yaml` reciben sus dos hallazgos mecánicos
- [ ] `ANTHROPIC_API_KEY` se lee una sola vez, en un único paso, con el tope de gasto mensual que fija la persona dueña y que queda en `impl.md`. Si se agota, el PR queda sin comentario y no se bloquea nada
- [ ] Se publica un único comentario por ejecución, con el SHA revisado, y no comentarios en línea
- [ ] El ajuste del repositorio que impide a GitHub Actions aprobar PR está activo y se comprueba por API
- [ ] Ensayo con un PR que viola a propósito un `float` en una firma de dominio y una ruta `async def`: las dos infracciones se comentan con su cita

Criterios que cierra: CA-1 a CA-5, CA-7, CA-8, CA-10, CA-11 (esc. 1 y 2), CA-S1 y CA-R1 a CA-R4, y su parte de CA-9 y CA-12, como los reparte la partición de la spec. Recorte del 2026-10-30: B4 y B5 retiradas y los criterios de `sdd/tickets/tkt-062b/_index.md` recortados; el registro vigente es ese índice.

**Cierra cuando.** B8 en verde. B4 y B5 quedaron retiradas por el recorte del 2026-10-30; el registro vigente es `sdd/tickets/tkt-062b/_index.md`.

**Non-goals** — No aprueba, no fusiona ni empuja commits, como el ticket paraguas. No comenta en línea. No revisa los PR de bifurcaciones ni los de Dependabot. No bloquea nada, ni como comprobación requerida ni con un umbral de hallazgos.

---

### TKT-010 · Datos semilla con catálogos reales

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-003, TKT-011 · **Sprint 2** |

**Qué hace.** Carga un conjunto de datos de arranque con usuarios de cada rol y los catálogos base reales, para que el desarrollo y los tests trabajen sobre datos del cliente y no inventados.

> **Va en el sprint 2 y no en el 1 porque las tablas que siembra no existen antes.** `empresa`, `tipo_partida` e `insumo` las crea TKT-011, que es del módulo `presupuesto`. Sembrar en el sprint 1 solo podría cargar usuarios y roles de acceso; los catálogos del cliente fallarían por tabla inexistente. El `rol_oficio` se siembra más tarde todavía, en TKT-042, junto a la tabla que lo contiene.

**Criterios técnicos**

- [ ] La fila única de `empresa` —Constructora Celsius—, **antes que nada**: `obra.empresa_id` es obligatoria y sin ella el alta de obra de TKT-012 falla por clave foránea
- [ ] Un usuario por cada uno de los seis roles
- [ ] Catálogo de `tipo_partida`: `MUROS`, `PLAFONES_Y_CAJILLOS`, `ENCHAPES`, `GENERALES`
- [ ] Los 27 insumos reales de la explosión de Union Square con sus unidades y precios, **con la misma clave que usará el importador**: TKT-014 da de alta los insumos que no encuentra, y si la clave no coincidiera duplicaría los 27
- [ ] La carga es idempotente: ejecutarla dos veces no duplica nada

> Ya **no** siembra obras: darlas de alta es funcionalidad de HDU-001 y debe probarse por su propio camino.

**Non-goals** — No importa el catálogo de conceptos (HDU-001). No siembra empleados ni proveedores: son funcionalidad de HDU-007 y HDU-004. No siembra `rol_oficio`: su tabla nace en TKT-042 y el catálogo se carga ahí. No siembra los datos simulados de mano de obra y avance: son un archivo de TKT-060, no filas de la base.

---

### TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-002, TKT-003, TKT-005, TKT-007, TKT-015 · **Sprint 2** |

**Qué hace.** Implementa el **camino mínimo** del módulo `archivos` que HDU-001 necesita para que el Excel de la línea base no pase por el API: alta de la fila en `PENDIENTE` con una URL prefirmada de subida, confirmación que verifica tamaño y hash contra el objeto almacenado, tipo leído de los bytes, URL prefirmada de lectura de vida corta y barrido de los `PENDIENTE` caducados ([ADR-016](adr/20261001-almacenamiento-de-objetos.md), `RNF-06`, `RNF-19`). Galería, anulación, evidencia de campo y expediente de obra son de la fase 2.

**Criterios técnicos**

- [ ] Tabla `archivo` según [modelo de datos §12](03-modelo-datos.md#12-archivos-adjuntos), con los invariantes 23, 24, 25 y 26 declarados en la migración y un test por cada uno que intenta violarlo **con el rol de aplicación**. `archivo.obra_id` es un identificador lógico **sin clave foránea**: `archivos` no depende de `presupuesto` ([modelo de datos §2](03-modelo-datos.md#2-convenciones))
- [ ] `referencia_tipo` nace con sus seis valores aunque la fase 1 solo use `IMPORTACION`: ampliar el `ENUM` en la fase 2 sería una migración evitable sobre una tabla que para entonces ya tiene datos
- [ ] Los tres índices del modelo: `(obra_id, estado, creado_en DESC)`, `(referencia_tipo, referencia_id)` y el parcial `(creado_en) WHERE estado = 'PENDIENTE'`
- [ ] Puerto `AlmacenObjetos` con un único adaptador sobre `boto3`, que cambia de destino solo por `endpoint_url` (regla 6 de ADR-016): **MinIO** en el Compose local con volumen persistente y en testcontainers, **R2** en producción. Las credenciales y el destino se leen con `pydantic-settings` y la aplicación no arranca si faltan (`RNF-07`)
- [ ] **Interfaz de aplicación publicada** para que el módulo dueño del documento registre el adjunto en su propia transacción: recibe obra, `referencia_tipo`, `referencia_id`, nombre original, tamaño y SHA-256 declarados, y devuelve el identificador del archivo, la URL de subida y su caducidad. `archivos` no comprueba que el documento exista —no conoce a ningún módulo de negocio—: lo garantiza quien llama ([arquitectura §7.7](02-arquitectura.md#77-archivos-y-evidencia))
- [ ] La URL de subida se firma **con el tamaño y el SHA-256 declarados** para que el propio almacén rechace un objeto distinto; la clave del objeto la genera el sistema y el nombre del usuario se guarda como dato, nunca como ruta (`RNF-06`)
- [ ] Límite de tamaño por tipo —15 MB imagen, 50 MB video, 25 MB documento **(asumido, `PA-15`)**— comprobado **al dar de alta** sobre el tamaño declarado: un declarado que excede el límite responde `422` y no se emite URL. Al confirmar, un tamaño almacenado distinto del declarado es `409` `CONFLICTO` `ARCHIVO_TAMANO_DISTINTO`
- [ ] `POST /api/v1/archivos/{archivo_id}/confirmacion` verifica tamaño y SHA-256 contra el objeto almacenado; si no coinciden, responde `409` `CONFLICTO` con `ARCHIVO_TAMANO_DISTINTO` o `ARCHIVO_HASH_DISTINTO`, mostrando lo declarado frente a lo almacenado, y el archivo **no** pasa a `DISPONIBLE` (HDU-001 esc. 25, `RNF-19`)
- [ ] La confirmación determina el tipo **leyendo los bytes** con `puremagic` contra la lista blanca cerrada del [stack §4.6](06-stack-tecnologico.md#46-los-archivos-no-viven-en-postgresql); para hoja de cálculo —solo `.xlsx`; un `.xls` no se admite— y XML la comprobación es **estructural** —abrir el ZIP y exigir la parte de libro en `[Content_Types].xml`; parsear el XML con `defusedxml`—. Un tipo fuera de la lista, **SVG incluido**, se rechaza con `409` `CONFLICTO` `ARCHIVO_TIPO_NO_PERMITIDO`, el tipo detectado y los admitidos, y el archivo no pasa a `DISPONIBLE` (HDU-001 esc. 26). Es `409` y no `422` porque la petición está bien formada: lo que no cuadra es el objeto almacenado con lo declarado, igual que en el hash del esc. 25
- [ ] Al pasar a `DISPONIBLE`, el sistema **reescribe el `Content-Type` del objeto** con el tipo que determinó, porque el que acompañó a la subida lo eligió el cliente (regla 4 de ADR-016), y asienta en la bitácora, **en la misma transacción**, el adjunto con su hash (`RNF-19`)
- [ ] `GET /api/v1/archivos/{archivo_id}` devuelve los metadatos —nunca los bytes ni la clave del objeto—, y `GET /api/v1/archivos/{archivo_id}/descarga` emite una URL de lectura de **minutos**, servida desde el origen del almacén y nunca desde el de la SPA; todo lo que no es imagen ni video lleva `Content-Disposition: attachment`. El rol se comprueba **al emitirla**, nunca después
- [ ] **Barrido al arrancar** de los `PENDIENTE` con la caducidad vencida, **reutilizando el mecanismo que construye TKT-015** para las importaciones con latido vencido (`RNF-17`), no uno nuevo: elimina el objeto que llegara a subirse y pasa la fila a **`CADUCADO`**, sin borrarla. `CADUCADO` y no `ANULADO` porque el barrido no tiene autor, y el invariante 24 exige autor y motivo para anular ([modelo de datos §12](03-modelo-datos.md#12-archivos-adjuntos))
- [ ] Ninguna ruta del API devuelve los bytes de un archivo: un test recorre el enrutador y falla si alguna respuesta de `archivos` es un flujo binario (regla 15 de `CLAUDE.md`)
- [ ] Tests de `RNF-06` y `RNF-19` del [stack §6.6](06-stack-tecnologico.md#66-qué-se-comprueba-solo) contra **MinIO real**: un `.svg` renombrado a `.jpg` se rechaza por su tipo real, un tamaño excedido se rechaza, la URL de lectura caduca, un PDF se sirve como descarga, un hash que no coincide no pasa a `DISPONIBLE`, y el hash confirmado aparece en la bitácora
- [ ] Añade el servicio y las pruebas de MinIO al trabajo `backend` del pipeline. TKT-009 deja ese trabajo sin MinIO hasta este ticket, porque antes no hay almacén que probar (ver su ficha)

> **Las sumas de verificación del almacén hay que comprobarlas al implementar.** Firmar la subida con el SHA-256 y leerlo después con los metadatos del objeto mantiene los bytes fuera del servidor, pero depende de que MinIO y R2 admitan esa suma en URL prefirmadas. Si alguno no la devuelve, la confirmación la calcula leyendo el objeto **desde el almacén y en un trabajo**, nunca dentro de una ruta `def`. *(asumido, a verificar con la documentación vigente de los dos destinos)*
>
> **Es fundación y no funcionalidad de HDU-001** porque la fase 2 lo reutiliza entero —evidencia de avance, remisión, expediente— y porque `archivos` es un módulo transversal. Lo que sí es de HDU-001 —crear la importación con su archivo y no analizar hasta que esté `DISPONIBLE`— vive en TKT-018.

**Non-goals** — No implementa galería, miniaturas ni visor (TKT-065). No implementa la anulación con motivo ni el expediente de obra (TKT-066, TKT-067). No adjunta evidencia a avances ni remisiones a entradas: son de la fase 2. No ofrece un alta genérica de archivo sin documento dueño: en la fase 1 el único documento adjuntable es la importación. No interpreta el contenido más allá de comprobar el tipo, ni el XML del CFDI. No escanea antivirus.

---

## Tickets de HDU-001 · Obra y línea base

Historia: [HDU-001](04-historias-usuario.md#hdu-001--alta-de-obra-e-importación-de-la-línea-base) · 14 SP

---

### TKT-011 · Esquema y migraciones del módulo presupuesto

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-003, TKT-059 |

**Criterios técnicos**

- [ ] Tablas `empresa`, `obra`, `nivel`, `area`, `tipo_partida`, `partida`, `concepto`, `insumo`, `precio_insumo`, `apu`, `apu_insumo`, `apu_cargo`
- [ ] `obra.empresa_id` es clave foránea **obligatoria** ([ADR-008](adr/20260918-despliegue-single-tenant.md)), aunque el despliegue sea de un solo inquilino y nadie filtre por ella
- [ ] Tablas `linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`
- [ ] Tablas `importacion`, `importacion_error`, `rendimiento_observado`, con `importacion.latido`, `importacion.progreso` y los tipos de error `PROCESO_INTERRUMPIDO` (`RNF-17`) y `SIN_CONCEPTOS` —hoja sin ninguna fila de concepto, HDU-001 esc. 27—
- [ ] `importacion` **no** tiene columnas de nombre ni de URL del archivo: el Excel vive en `archivo` con `referencia_tipo = 'IMPORTACION'` ([modelo de datos §11](03-modelo-datos.md#11-importación)). `importacion.archivo_id` es un identificador lógico **sin clave foránea** —una clave entre tablas de dos módulos cruzaría la frontera por el esquema— y está en la lista cerrada de [modelo de datos §2](03-modelo-datos.md#2-convenciones). El caso de uso que crea la importación es de TKT-018
- [ ] `obra` incluye `domicilio`, `retencion_destajo_pct`, `fondo_garantia_pct`, `iva_acreditable` (PA-02, PA-05) y `umbral_alerta_pct` —`Porcentaje`, nullable; F7.3—, el umbral que separa `AMARILLO` de `ROJO` en el semáforo y dispara su alerta (TKT-039; `PA-18`, resuelta el 2026-10-17)
- [ ] `insumo.creado_en_importacion BOOLEAN`, que TKT-014 marca al dar de alta un insumo que no encuentra
- [ ] `CHECK` de `concepto.unidad` e `insumo.unidad` contra el catálogo de unidades admitidas — invariante 27 —, el mismo enum que usa el borrador
- [ ] Restricción `UNIQUE (obra_id, codigo)` sobre `concepto` — invariante 13
- [ ] Índice único parcial que garantiza una sola línea base `CONGELADA` por obra — invariante 5
- [ ] `UNIQUE (linea_base_id, tipo_partida_id)` sobre `presupuesto_control` — invariante 6
- [ ] `presupuesto_control` incluye `actualizado_por_id`, `actualizado_en` y `motivo_ultimo_cambio`: el tope se recaptura, a diferencia de las copias congeladas
- [ ] Disparador que rechaza `UPDATE` y `DELETE` sobre `linea_base_concepto` y `explosion_presupuesto` cuando la línea base está congelada — invariante 14
- [ ] Índices `(linea_base_id, tipo_partida_id, insumo_id)` sobre `explosion_presupuesto`
- [ ] `rendimiento_observado` es tabla separada de `explosion_presupuesto`: ninguna escribe sobre la otra — invariante 19
- [ ] **Permisos del rol de aplicación, revocados en esta migración con su prueba** sobre los permisos por omisión de TKT-003: sobre `linea_base_concepto`, solo `SELECT` e `INSERT` —sin `UPDATE` ni `DELETE`—, **además** del disparador; sobre `explosion_presupuesto` y `presupuesto_control`, `UPDATE`, porque `SELECT … FOR UPDATE` exige ese privilegio y sin él el bloqueo pesimista de [ADR-004](adr/20260918-bloqueo-pesimista-presupuesto.md) falla por permisos en tiempo de ejecución ([arquitectura §7.6](02-arquitectura.md#76-seguridad-de-la-frontera))
- [ ] Un test toma `SELECT … FOR UPDATE` sobre `explosion_presupuesto` **con el rol de aplicación** y verifica que funciona; otro verifica que un `UPDATE` sobre `linea_base_concepto` con el rol de aplicación falla por permiso
- [ ] Un test verifica que el disparador de inmutabilidad dispara **ejecutándose con el rol de migración**: con el de aplicación fallaría antes por permiso y la prueba quedaría verde sin haber tocado el disparador

**Non-goals** — No crea tablas de otros módulos.

---

### TKT-012 · Alta y mantenimiento de obras

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-011, TKT-008 |

**Qué hace.** CRUD de obras con sus parámetros de negocio, incluida la baja protegida.

**Criterios técnicos**

- [ ] Alta con código, nombre, domicilio, tipo de contrato, porcentaje de retención de destajo (15 %), porcentaje de fondo de garantía (5 %), indicador de IVA acreditable y umbral de alerta del semáforo (`umbral_alerta_pct`, opcional; F7.3). `ObraNueva` y `ObraCambios` del borrador lo incluyen, y cambiarlo se asienta en la bitácora
- [ ] Los dos porcentajes son **conceptos distintos** y se guardan en la obra: ninguna constante en el código (**PA-02**)
- [ ] El indicador de IVA acreditable se guarda por obra porque varía entre ellas (**PA-05**, `RN-25`)
- [ ] Código de obra único: el duplicado responde `409` `CONFLICTO` `CODIGO_OBRA_DUPLICADO` identificando la obra en conflicto
- [ ] Máquina de estados `PLANEACION → ACTIVA → SUSPENDIDA/CERRADA`
- [ ] Una obra con línea base congelada o movimientos no se puede eliminar: responde `409` `CONFLICTO` `OBRA_CON_HISTORIAL` con las acciones de suspenderla o cerrarla
- [ ] Interfaz con el componente de formulario de catálogo de TKT-008

**Non-goals** — No importa presupuesto. No gestiona permisos por obra.

---

### TKT-013 · Lector del catálogo de conceptos

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-011 |

**Criterios técnicos**

- [ ] Reconstruye la jerarquía obra › nivel › área › partida › concepto a partir de la indentación y de las filas sin código
- [ ] Reconoce las unidades `M2`, `ML`, `PZA` y sus variantes de mayúsculas
- [ ] Deposita el resultado en la zona de preparación sin tocar el modelo real
- [ ] Se prueba contra los **dos** archivos reales, que tienen estructuras ligeramente distintas
- [ ] Reporta fila y columna de cada valor que no puede interpretar

**Non-goals** — No lee los análisis de precios unitarios; no confirma nada.

---

### TKT-014 · Lector de análisis de precios unitarios

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-013 |

**Criterios técnicos**

- [ ] Lee cada hoja de análisis: bloque de material, bloque de mano de obra, cargos porcentuales y cargos indirectos
- [ ] Asocia cada análisis con su concepto
- [ ] Extrae por insumo: unidad, costo unitario, rendimiento y cargo
- [ ] Extrae los cargos con su tipo, porcentaje, base e importe
- [ ] Da de alta los insumos que no existan, con `insumo.creado_en_importacion = true`
- [ ] Verifica que el precio unitario reconstruido coincide con el del archivo dentro de la tolerancia decimal; si no, lo reporta como error
- [ ] Se prueba con `MURO STD-635-STD`: material $201.67 + mano de obra $286.07 = costo directo $487.74, precio unitario $641.36

**Non-goals** — No recalcula precios; solo lee y verifica.

---

### TKT-015 · Validaciones y reporte de errores por fila

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-014 |

**Criterios técnicos**

- [ ] Detecta y clasifica: `REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO` y `SIN_CONCEPTOS`
- [ ] Una hoja sin ninguna fila de concepto deja la importación `CON_ERRORES` con un error `SIN_CONCEPTOS`, y no se puede confirmar. Test `test_hdu001_esc27_…` en verde
- [ ] Cada error registra hoja, fila, columna, tipo, mensaje y valor original
- [ ] Un error bloqueante deja la importación en estado `CON_ERRORES` y **no** permite confirmar
- [ ] Las filas válidas se conservan en preparación para no repetir el análisis completo
- [ ] Se prueba contra el catálogo de Union Square, que tiene `#REF!` en todas las columnas de precio: debe reportarlo fila a fila, no fallar en bloque
- [ ] El análisis corre en un `ProcessPoolExecutor` de un trabajador: openpyxl retiene el intérprete y degradaría la latencia del resto de la aplicación
- [ ] El trabajo refresca `importacion.latido` y `importacion.progreso` mientras analiza, y al arrancar la aplicación un barrido pasa a `CON_ERRORES` toda importación en `ANALIZANDO` con latido vencido, con un error `PROCESO_INTERRUMPIDO` (`RNF-17`)
- [ ] Un test simula la interrupción y verifica que la obra vuelve a admitir importaciones
- [ ] El barrido de arranque se construye como **mecanismo reutilizable** —trabajos en dos pasos cuyo segundo puede no ocurrir—: TKT-059 lo reutiliza para pasar a `CADUCADO` los `PENDIENTE` vencidos de `archivo`

> **Sin el barrido, un reinicio a mitad de análisis deja la fila en `ANALIZANDO` para siempre** y la obra sin poder importar, sin error que consultar y sin nadie a quien reclamar. La fase de análisis no escribe en el modelo real, así que ese es el único daño posible — y es suficiente para bloquear la historia entera.

**Non-goals** — No corrige los errores ni permite editar valores desde la interfaz.

---

### TKT-016 · Cálculo de la explosión por tipo de partida

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-014 |

**Criterios técnicos**

- [ ] Para cada **tipo de partida** e insumo, suma `cantidad_concepto × rendimiento` sobre todos los conceptos de ese tipo en **toda la obra** (**PA-01**)
- [ ] Conserva el `rendimiento_congelado` de cada insumo como referencia inmutable (`RN-24`)
- [ ] Calcula el importe de venta y un **importe sugerido** de control quitando utilidad e indirectos, marcado explícitamente como sugerencia
- [ ] El importe sugerido **no** se guarda como presupuesto de control: ese lo captura Dirección (**PA-03**)
- [ ] Sin redondeo intermedio: precisión completa en el cálculo, redondeo solo al presentar
- [ ] Un test verifica que la explosión agregada de toda la obra reproduce los 27 insumos y el total de $2,755,187.21 del archivo real

**Non-goals** — No congela nada ni captura el presupuesto de control: solo calcula.

---

### TKT-017 · Confirmación y congelado de la línea base

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-015, TKT-016, TKT-007 |

**Criterios técnicos**

- [ ] La confirmación materializa toda la jerarquía en **una sola transacción**: o entra todo, o no entra nada
- [ ] Un test provoca un fallo a mitad de escritura y verifica que no queda ningún dato persistido
- [ ] Reimportar sobre una línea base en borrador exige confirmación explícita y registra el descarte en la bitácora
- [ ] El congelado copia conceptos y explosión agregada por tipo de partida a las tablas de línea base
- [ ] El congelado registra fecha, usuario y motivo, escribe en la bitácora y pasa la obra a estado `ACTIVA`
- [ ] Intentar congelar una segunda línea base vigente falla con el contrato de error y regla `RN-01`
- [ ] Intentar modificar una línea base congelada falla a nivel de motor
- [ ] **Captura del presupuesto de control** por tipo de partida (**PA-03**), con el importe sugerido visible pero no impuesto
- [ ] Un importe tope superior al de venta exige confirmación con motivo: sin ella responde `409` `CONFLICTO` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR`; con ella, se guarda y el motivo queda en la bitácora
- [ ] El rechazo de una requisición contra una obra sin presupuesto de control capturado **no es de este ticket**: es `CONFLICTO` `SIN_PRESUPUESTO_CONTROL` y lo implementa TKT-021
- [ ] **Recaptura del tope** por Dirección General con motivo obligatorio: actualiza la fila y asienta en bitácora el valor anterior, el nuevo y el motivo, **con la regla `RN-03`**, de modo que la consulta de excepciones de TKT-027 devuelva las subidas de tope junto a las autorizaciones
- [ ] Recapturar sin el rol `DIRECCION_GENERAL` responde `403`; sin motivo, `422`. En ambos casos el tope conserva su valor
- [ ] `PUT …/presupuesto-control/{tipo_partida_id}` **no se declara idempotente**: cada recaptura exige motivo y se asienta, aunque repita el valor
- [ ] **Dueño de los casos de uso de congelación y de presupuesto de control, y de sus rutas**: `GET /api/v1/obras/{obra_id}/lineas-base`, `GET /api/v1/lineas-base/{linea_base_id}` con sus `conceptos` y su `explosion`, `POST /api/v1/lineas-base/{linea_base_id}/congelacion`, y `GET` y `PUT /api/v1/lineas-base/{linea_base_id}/presupuesto-control[/{tipo_partida_id}]`. La materialización que dispara la confirmación de una importación es suya; la ruta `POST /api/v1/importaciones/{importacion_id}/confirmacion` es de TKT-018, que la invoca

> **Subir un tope es una vía alternativa a autorizar una excepción.** Si se asentara con otra regla —o no se asentara— una partida podría sobregirarse sin que apareciera ni una sola excepción en la bitácora del mes.

**Non-goals** — No implementa versionado por trabajos extra (`RN-18`, v1.1). No permite tocar la línea base congelada: lo que se recaptura es el presupuesto de control, que no forma parte de ella.

---

### TKT-018 · Caso de uso, rutas e interfaz de importación

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-017, TKT-012, TKT-059 |

**Criterios técnicos**

- [ ] **Dueño del caso de uso de importación y de todas sus rutas**: `POST` y `GET /api/v1/obras/{obra_id}/importaciones`, `GET /api/v1/importaciones/{importacion_id}` y sus `/analisis`, `/errores`, `/confirmacion` y `/descarte`. El análisis lo hacen TKT-013 a TKT-015; la confirmación invoca la materialización de TKT-017
- [ ] El caso de uso que crea la importación en estado `RECIBIDO` registra en **la misma transacción**, por la interfaz publicada de TKT-059, el `archivo` `PENDIENTE` que la referencia: así el documento existe antes que el adjunto, que es lo único que ADR-016 exige (HDU-001 esc. 24)
- [ ] **Solo `.xlsx`.** Un formato declarado distinto —`.xls` incluido— responde `422` al crear la importación y no emite URL de subida (HDU-001 esc. 21); una hoja que llega sin conceptos no es un error de forma, sino una importación `CON_ERRORES` con `SIN_CONCEPTOS` (esc. 27, TKT-015)
- [ ] **El Excel entra por `archivo`** (HDU-001 esc. 24): el navegador calcula el SHA-256 y el tamaño, `POST /api/v1/obras/{obra_id}/importaciones` crea la importación con su archivo `PENDIENTE` y devuelve `archivo_id` y URL de subida, el navegador sube **directo al almacén** y llama a `POST /api/v1/archivos/{archivo_id}/confirmacion`. Ningún byte del Excel pasa por una ruta del API
- [ ] `POST /api/v1/importaciones/{importacion_id}/analisis` arranca el análisis **solo** si el archivo está `DISPONIBLE`; con el archivo en `PENDIENTE` responde `409` `CONFLICTO` `ARCHIVO_NO_DISPONIBLE` y la importación no cambia de estado (HDU-001 esc. 24)
- [ ] El analizador de TKT-015 lee el Excel **desde el almacén de objetos dentro de su trabajo**, no desde una ruta, y nunca recibe un archivo que no haya pasado la comprobación estructural de TKT-059 (HDU-001 esc. 26)
- [ ] Ante un hash o un tamaño que no coinciden, la pantalla muestra lo declarado frente a lo almacenado y pide volver a cargar; ante un tipo rechazado, el tipo detectado y los admitidos. En ningún caso queda una importación analizando (HDU-001 esc. 25 y 26)
- [ ] Tests `test_hdu001_esc21_…`, `test_hdu001_esc24_…`, `test_hdu001_esc25_…` y `test_hdu001_esc26_…` en verde: los dos de rechazo prueban que **no se escribe ninguna fila** en la zona de preparación ni en el modelo real
- [ ] Carga del archivo e indicador de progreso del análisis, alimentado por `importacion.progreso`, que no bloquea la pantalla
- [ ] Pantalla de previsualización con jerarquía leída, conteos, importe total e insumos creados durante la importación
- [ ] Tabla de errores navegable por hoja y fila, exportable
- [ ] Botón de confirmar deshabilitado mientras la importación esté en `CON_ERRORES`
- [ ] Acción de congelar con captura obligatoria del motivo
- [ ] La línea base congelada se muestra en modo lectura, sin controles de edición

**Non-goals** — No permite editar conceptos; una corrección se hace reimportando. No construye el componente de subida reutilizable con cámara y compresión: es de la fase 2 (TKT-065); aquí basta un selector de archivo.

---

## Tickets de HDU-002 · Requisición con control de presupuesto

Historia: [HDU-002](04-historias-usuario.md#hdu-002--requisición-con-control-de-presupuesto) · 8 SP

---

### TKT-019 · Esquema y migraciones del módulo compras

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-011 |

**Criterios técnicos**

- [ ] Tablas `requisicion`, `requisicion_renglon`, `solicitud_autorizacion`, `orden_compra`, `orden_compra_renglon` y `folio_consecutivo`, que guarda el último folio de cada serie —`REQUISICION` y `ORDEN_COMPRA`, global por serie— para numerar sin huecos dentro de la transacción que crea el documento (TKT-021, TKT-030)
- [ ] `requisicion.motivo_cancelacion` y `orden_compra.motivo_cancelacion`
- [ ] `orden_compra.proveedor_id` **sin clave foránea**: `proveedor` es de `proveedores`, que depende de `compras`, y la clave invertiría la arista. Lo valida el puerto `CatalogoProveedores` que declara `compras` (TKT-029, TKT-030), y está en la lista cerrada de [modelo de datos §2](03-modelo-datos.md#2-convenciones)
- [ ] `obra_id` y `tipo_partida_id` con restricción `NOT NULL` en `requisicion` — invariante 1 (**PA-01**)
- [ ] El estado de `requisicion` distingue `RECHAZADA` —decisión de Dirección sobre una excepción— de `CANCELADA` —el solicitante desistió—: mezclarlas contaminaría la consulta de excepciones de `RN-04`
- [ ] `CHECK (cantidad >= 0)` y `CHECK (costo_unitario >= 0)` en los renglones de requisición y de orden — invariante 8
- [ ] Tabla `reprogramacion_entrega` y columna `fecha_compromiso` en `orden_compra_renglon` (**PA-07**)
- [ ] `orden_compra` **no** tiene columna de motivo de cierre: no existe el cierre con saldo
- [ ] `orden_compra_renglon.cantidad_excedente_autorizada NUMERIC(14,4) NOT NULL DEFAULT 0` y `CHECK (cantidad_recibida <= cantidad_ordenada + cantidad_excedente_autorizada)` — invariante 2 —: lo recibido solo pasa de lo ordenado por el excedente que Dirección General autorizó (`RN-07`, `PA-16`, resuelta el 2026-10-17). La columna **la incrementa la entrada que consume la autorización** (TKT-035), nunca la resolución: una autorización que nadie usa no altera la orden
- [ ] `CHECK` que exige motivo al resolver una solicitud — invariante 9
- [ ] `solicitud_autorizacion` modelada de forma genérica, sin acoplarse a requisiciones. Para el motivo `EXCEDE_ORDENADO` guarda además `orden_compra_renglon_id` y `cantidad_excedente` —el renglón y la cantidad excedente solicitada—, nulos en los demás motivos y exigidos juntos en ese

**Non-goals** — No implementa lógica: solo esquema.

---

### TKT-020 · Regla RN-03 en el dominio

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-004, TKT-005 |

**Criterios técnicos**

- [ ] Función pura que recibe presupuestado, consumido y solicitado, y devuelve permitido o bloqueado con disponible y excedente
- [ ] Evalúa **los dos controles**: importe de la partida y volumen por insumo **dentro del tipo de partida** —`(tipo_partida_id, insumo_id)`, nunca solo por insumo—
- [ ] El `consumido` llega ya calculado y su definición es **una sola** para todo el sistema, la de [modelo de datos §15](03-modelo-datos.md#el-consumido-de-rn-03), y la calcula `compras` (TKT-021): `requisiciones vivas + comprometido + ejercido`, cada peso contado una vez
- [ ] Un insumo ausente de la explosión se trata como disponible cero, no como sin límite
- [ ] Sin dependencias de framework, ORM ni HTTP: se prueba sin levantar nada
- [ ] El identificador `RN-03` aparece en el docstring y en el nombre de los tests

> Materializa [ADR-003](adr/20260918-dominio-puro.md). Si esta regla acaba dentro de un controlador, los doce escenarios de HDU-002 se vuelven tests de integración lentos.

**Non-goals** — No consulta la base de datos; recibe los datos ya cargados.

---

### TKT-021 · Caso de uso con bloqueo pesimista

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-019, TKT-020, TKT-007 |

**Criterios técnicos**

- [ ] Una sola transacción: bloquea, lee consumido, evalúa, persiste y escribe bitácora
- [ ] **`compras` es dueño del cálculo del `consumido` y del `disponible`** ([modelo de datos §15](03-modelo-datos.md#el-consumido-de-rn-03)): `requisiciones_vivas` —las `EVALUADA` y `AUTORIZADA` sin convertir— y `comprometido` —el saldo no recibido de las órdenes `ABIERTA` y `PARCIAL`— salen de tablas suyas, y el **ejercido** le llega por el puerto **`FuenteEjercido`**, que declara `compras/aplicacion` e implementan otros módulos. Es la misma definición que lee el semáforo, que se la pide a `compras` y no la reescribe (TKT-039)
- [ ] `FuenteEjercido` se ejecuta **con la sesión de la transacción en curso**, dentro del bloqueo de ADR-004: un ejercido leído fuera del bloqueo podría quedar viejo entre la lectura y la escritura
- [ ] **Hasta que `almacen` implemente el puerto (TKT-035, sprint 5), `compras` trae un adaptador *cero real***: devuelve cero porque todavía no puede existir ninguna entrada, no porque falte el dato. El destajo lo aporta `avance` en la fase 2 (TKT-069). Las aristas son `almacen → compras` y `avance → compras`; `compras` no importa a ninguno de los dos
- [ ] El control por volumen agrupa por **`(tipo_partida_id, insumo_id)`**, nunca solo por insumo: el mismo insumo en `MUROS` y en `PLAFONES_Y_CAJILLOS` son dos bolsas distintas
- [ ] El folio de la requisición sale de `folio_consecutivo`, con la fila bloqueada en la misma transacción: si la transacción se deshace, el número vuelve con ella
- [ ] Un test verifica que dos requisiciones de $8,000 contra $12,000 disponibles **no pasan las dos**: es el escenario 9 y solo funciona si las requisiciones vivas consumen
- [ ] Un test verifica que el disponible que devuelve el endpoint de consulta y el que aplica la evaluación **coinciden al céntimo**: si divergen, Compras ve en pantalla un número que la regla no respeta
- [ ] `SELECT … FOR UPDATE` sobre `presupuesto_control` (control por importe) y `explosion_presupuesto` (control por volumen) del tipo de partida
- [ ] El tope de importe sale del valor **capturado**, no del sugerido (**PA-03**)
- [ ] Los bloqueos se toman **siempre ordenados por identificador de tipo de partida**, para evitar interbloqueo
- [ ] La requisición bloqueada se **persiste** en estado `BLOQUEADA` con las cifras del momento; no se descarta
- [ ] Se crea la solicitud de autorización dirigida al rol `DIRECCION_GENERAL`, y el `409` `RN-03` lleva la acción `VER_SOLICITUD_AUTORIZACION` —un `GET` a esa solicitud ya creada—, nunca `SOLICITAR_AUTORIZACION`: no hay nada que pedir otra vez (HDU-002 esc. 4)
- [ ] Contra una obra sin línea base congelada responde `409` `CONFLICTO` `SIN_LINEA_BASE_CONGELADA`; sin presupuesto de control capturado para su tipo de partida, `409` `CONFLICTO` `SIN_PRESUPUESTO_CONTROL`, con la acción de ir a capturarlo solo para quien puede hacerlo (TKT-005). Ninguno lleva regla ni se asienta como `RN-03`: no se evaluó nada
- [ ] Una requisición cancelada libera el presupuesto que tenía comprometido
- [ ] El vencimiento de `lock_timeout` **se traduce a `409` `CONCURRENCIA`** con cabecera `Retry-After` y la acción `REINTENTAR`, nunca a un fallo interno (`RNF-16`)
- [ ] Un test retiene el bloqueo desde otra sesión y verifica que la segunda vence y responde con el contrato, no con un `500`
- [ ] Si el caso de uso responde `403` (`NO_ES_SOLICITANTE`), un `403` que nace en un caso de uso se asienta como `DENEGAR` por la interfaz de auditoría, porque el asiento automático de `exigir_rol` cubre solo `ROL_INSUFICIENTE`; si hace falta un ayudante compartido, se publica en `cimenta.identidad.interfaz` en este ticket (TKT-006 no lo publica)

**Non-goals** — No resuelve la autorización; no emite orden de compra.

---

### TKT-022 · Test de concurrencia

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-021 |

**Criterios técnicos**

- [ ] Dos transacciones **reales y simultáneas** contra la misma partida, no simuladas con dobles de prueba
- [ ] Verifica que exactamente una queda `EVALUADA` y la otra `BLOQUEADA`
- [ ] Verifica que el disponible final refleja solo la aceptada
- [ ] Se ejecuta en CI de forma determinista, sin depender de temporizadores

> Es el escenario 9 de HDU-002 y el único que prueba [ADR-004](adr/20260918-bloqueo-pesimista-presupuesto.md). Un test con dobles aquí no prueba nada: la garantía la da el motor.

**Non-goals** — No mide rendimiento ni prueba carga.

---

### TKT-023 · Endpoints de requisición

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-021 |

**Criterios técnicos**

- [ ] `GET /api/v1/obras/{obra_id}/tipos-partida/{tipo_partida_id}/disponible`, con importe y cantidades por insumo, y el **consumido desglosado en tres**: requisiciones vivas, saldo de órdenes y ejercido
- [ ] `GET /api/v1/obras/{obra_id}/tipos-partida/{tipo_partida_id}/requisiciones-vivas`: **requisiciones evaluadas sin convertir**, ordenadas por antigüedad, con importe y solicitante: es el contrapeso de que la reserva no caduque sola
- [ ] `POST /api/v1/requisiciones` guarda en borrador sin evaluar, o crea y envía en un paso y responde **`201`**; `POST /api/v1/requisiciones/{requisicion_id}/envio` envía un borrador ya guardado y responde **`200`**, porque el recurso ya existía (HDU-002 esc. 3)
- [ ] `POST /api/v1/requisiciones/{requisicion_id}/cancelacion` con motivo —guardado en `requisicion.motivo_cancelacion`— desde `EVALUADA`, `BLOQUEADA` o `AUTORIZADA`, que pasa a `CANCELADA` —no a `RECHAZADA`— y **libera la reserva**: es la única transición que lo hace. **Solo el solicitante** puede cancelar; cualquier otro usuario recibe `403` (HDU-002 esc. 11)
- [ ] Modificar una requisición ya evaluada responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con la acción de cancelar y volver a levantar (HDU-002 esc. 12)
- [ ] `GET` por identificador y listado con filtros por obra, partida y estado
- [ ] Todas las respuestas de rechazo cumplen el contrato de error, con importes como cadena
- [ ] Documentación de API generada y verificada

**Non-goals** — No implementa endpoints de autorización (HDU-003) ni de orden de compra (HDU-004).

---

### TKT-024 · Interfaz de captura de requisición

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-023, TKT-008 |

**Criterios técnicos**

- [ ] Selección de obra y partida que muestra presupuestado, consumido —desglosado en requisiciones vivas, saldo de órdenes y ejercido— y disponible antes de capturar
- [ ] Lista de requisiciones evaluadas sin convertir con acción de cancelar, accesible desde la consulta de disponible
- [ ] Captura de renglones con insumo y cantidad, mostrando la cantidad disponible de cada insumo
- [ ] Guardado en borrador y recuperación posterior
- [ ] Al bloquearse, se usa el componente de pantalla de bloqueo de TKT-008 mostrando disponible, excedente e insumo culpable
- [ ] El botón de **ver la solicitud de autorización** —`VER_SOLICITUD_AUTORIZACION`: la solicitud ya se creó al bloquear— sale de las acciones del contrato de error, no está cableado en el componente (HDU-002 esc. 4)
- [ ] Una obra sin línea base congelada o sin presupuesto de control muestra el `CONFLICTO` con su código y la acción que el servidor devuelva, sin cifras que parezcan un disponible
- [ ] Los importes se calculan con decimal exacto en el cliente

**Non-goals** — No incluye la bandeja de autorizaciones.

---

## Tickets de HDU-003 · Resolución de requisiciones bloqueadas

Historia: [HDU-003](04-historias-usuario.md#hdu-003--resolución-de-una-requisición-bloqueada) · 5 SP · **fase 1**

Retoma el flujo donde HDU-002 lo deja: una `requisicion` en `BLOQUEADA` con su `solicitud_autorizacion` en `PENDIENTE`. Es la mitad del hilo vertical que dice *"o se autoriza"*, y sin ella HDU-004 no tiene el estado `AUTORIZADA` del que emite su escenario 5.

---

### TKT-025 · Casos de uso de autorizar y rechazar

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-021, TKT-026, TKT-007 |

**Qué hace.** Resuelve una solicitud de autorización —autorizar o rechazar— en una sola transacción que mueve la solicitud y la requisición, exige motivo en los dos sentidos y asienta la decisión en la bitácora. Es idempotente: una solicitud se resuelve una vez.

**Criterios técnicos**

- [ ] Una sola transacción: bloquea la solicitud con `SELECT … FOR UPDATE`, comprueba que sigue `PENDIENTE`, consulta la regla de autoridad de TKT-026, escribe la resolución, mueve la requisición y asienta la bitácora. Si la bitácora falla, no hay resolución (`RN-04`)
- [ ] **Autorizar**: solicitud a `AUTORIZADA` con `resuelta_por_id` y `resuelta_en`; requisición de `BLOQUEADA` a `AUTORIZADA`; asiento con el motivo y la regla `RN-03` (HDU-003 esc. 4)
- [ ] **Rechazar**: solicitud y requisición a `RECHAZADA`, y la requisición ya no puede convertirse en orden de compra (HDU-003 esc. 5). `RECHAZADA` no es `CANCELADA` ([modelo de datos §14](03-modelo-datos.md#14-máquinas-de-estado))
- [ ] **Motivo obligatorio también al autorizar**: sin motivo responde `422` con un mensaje que lo dice expresamente, y la solicitud sigue `PENDIENTE` (HDU-003 esc. 6). El invariante 9 lo garantiza además en el motor
- [ ] Resolver una solicitud ya resuelta responde `409` `CONFLICTO` `YA_RESUELTA` con quién la resolvió y cuándo, sin tocar estado ni motivo originales (HDU-003 esc. 9). Dos resoluciones **simultáneas** de la misma solicitud: exactamente una gana, por el bloqueo de fila
- [ ] Una solicitud cuya requisición está `CANCELADA` es **sin efecto**: no admite resolución y responde `409` `CONFLICTO` `SOLICITUD_SIN_EFECTO` mostrando el motivo de la cancelación (HDU-003 esc. 10). "Sin efecto" se **deriva** del estado de la requisición, no es un estado más de la solicitud **(asumido: el `ENUM` de §5 no lo tiene, y añadirlo obligaría a mantener dos estados sincronizados)**
- [ ] **Autorizar toma los mismos bloqueos que la evaluación de TKT-021**, en el mismo orden: al pasar a `AUTORIZADA` la requisición empieza a contar como requisición viva en el `consumido` ([modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo)), y una evaluación concurrente que no la viera dejaría pasar una requisición que ya no cabe **(asumido: consecuencia de la definición del consumido que ADR-004 no enuncia; se escala para confirmarla)**
- [ ] La resolución es **genérica sobre `solicitud_autorizacion`**: el efecto sobre la entidad se despacha por el `motivo`. Con `EXCEDE_PRESUPUESTO` mueve la requisición. Una solicitud `EXCEDE_ORDENADO` de HDU-005 esc. 5 se resuelve con motivo y se asienta con `RN-07`, **y autorizarla no registra la entrada ni toca la orden: la habilita**. La entrada la registra Almacén al reenviarla citando la solicitud, y es esa entrada la que suma el excedente a la recepción (TKT-035, HDU-005 esc. 21; `PA-16`, resuelta el 2026-10-17). Un test autoriza una `EXCEDE_ORDENADO` y verifica que `cantidad_recibida`, `cantidad_excedente_autorizada` y el estado de la orden no cambian
- [ ] Tests `test_hdu003_esc04_…`, `esc05`, `esc06`, `esc09` y `esc10` en verde contra PostgreSQL real, con el rol de aplicación

**Non-goals** — No emite orden de compra tras autorizar (HDU-004). No decide la regla de autoridad: la consulta a TKT-026. No registra la entrada excedente al autorizarla: es TKT-035. No implementa delegación ni suplencia.

---

### TKT-026 · Reglas de autoridad en el dominio

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-004, TKT-005, TKT-006 |

**Qué hace.** Usa en `dominio/` la prohibición de resolver lo propio que implementa TKT-006 (`evaluar_resolucion`); el rol lo comprueba `api/` con `exigir_rol` (TKT-006). Se prueba sin HTTP ni base de datos.

**Criterios técnicos**

- [ ] Función pura que recibe el actor y el solicitante (`evaluar_resolucion(*, solicitante_id, resolutor_id)`, sin roles) y devuelve un `ResultadoResolucion`, con `motivo = AUTO_RESOLUCION` cuando solicitante y resolutor coinciden, sin recibir roles. La falta de rol no la decide esta función: es `ROL_INSUFICIENTE` y la decide `api/` con `exigir_rol` (TKT-006), antes de llamar al caso de uso. `evaluar_resolucion` (TKT-006) cubre solo `AUTO_RESOLUCION` y no recibe roles
- [ ] El permiso efectivo es la **unión** de los roles del actor ([arquitectura §7.1](02-arquitectura.md#71-autorización)), que `exigir_rol` comprueba en `api/`; tener `DIRECCION_GENERAL` no exime de la prohibición de auto-autorización (HDU-003 esc. 8), que `evaluar_resolucion` aplica sin recibir roles
- [ ] La regla *"nadie resuelve lo suyo"* se escribe **una vez**, con un nombre que no dice *solicitud*: HDU-008 esc. 7 —no validar la propia medición— la reutiliza en la fase 2 por la interfaz publicada de `identidad`, que es donde vive. La implementa TKT-006 como `evaluar_resolucion`, publicada en `cimenta.identidad.interfaz`; este ticket la usa y no la reescribe.
- [ ] Sin dependencias de framework, ORM ni HTTP: `import-linter` lo verifica (TKT-002)
- [ ] Cuando el caso de uso que usa `evaluar_resolucion` responde `403` `AUTO_RESOLUCION`, ese `403` se asienta como `DENEGAR` por la interfaz de auditoría, porque el asiento automático de `exigir_rol` cubre solo `ROL_INSUFICIENTE`; si hace falta un ayudante compartido, se publica en `cimenta.identidad.interfaz` en este ticket (TKT-006 no lo publica)
- [ ] Tests de dominio `test_hdu003_esc07_…` y `test_hdu003_esc08_…` en milisegundos; la versión HTTP de los mismos escenarios es de TKT-027

> **El rol se comprueba en `api/` y la autoridad en `dominio/`; este ticket usa solo la segunda.** La comprobación del rol en la ruta es la que corta el paso; la de la autoridad es la que se puede probar sin levantar nada, y la prohibición de resolver lo propio sobrevive a una ruta nueva que olvide la dependencia ([arquitectura §7.6](02-arquitectura.md#76-seguridad-de-la-frontera)).

**Non-goals** — No implementa delegación, suplencia ni umbrales por monto (F2.7, fuera del MVP). No consulta la base de datos: recibe los datos ya cargados.

---

### TKT-027 · Endpoints de bandeja, detalle, resolución y bitácora de excepciones

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-025, TKT-006, TKT-007 |

**Qué hace.** Expone la bandeja de Dirección General, su contador, el detalle con las cifras del momento del bloqueo, la resolución y la consulta de excepciones de la bitácora.

**Criterios técnicos**

- [ ] `GET /api/v1/solicitudes-autorizacion?estado=PENDIENTE`: ordenadas de la más antigua a la más reciente, con obra, tipo de partida, solicitante, importe solicitado y excedente; las resueltas no aparecen (HDU-003 esc. 2). Las **sin efecto** sí aparecen, marcadas y con el motivo de la cancelación (esc. 10)
- [ ] `GET /api/v1/solicitudes-autorizacion/contador`: número de pendientes **resolubles**, que vale cero cuando no queda ninguna (esc. 1) **(asumido: las sin efecto no cuentan, porque no hay nada que decidir sobre ellas)**
- [ ] `GET /api/v1/solicitudes-autorizacion/{solicitud_id}`: cifras tomadas de `solicitud_autorizacion.contexto` y de la fila de la requisición **tal como quedaron al bloquear**, nunca recalculadas; renglones de la requisición y regla que provocó el bloqueo (esc. 3)
- [ ] `POST /api/v1/solicitudes-autorizacion/{solicitud_id}/resolucion` con decisión y motivo: es una transición, no un `PATCH` del estado
- [ ] Resolver sin `DIRECCION_GENERAL` responde `403`, la solicitud sigue `PENDIENTE` y el intento se asienta como `DENEGAR` (esc. 7); intentar resolver la propia responde `403` con la causa, y también se asienta (esc. 8)
- [ ] **`POST /api/v1/solicitudes-autorizacion` es de este ticket** y sirve solo a `RN-07`: crea la solicitud `EXCEDE_ORDENADO` a la que apunta la acción `SOLICITAR_AUTORIZACION` de HDU-005 esc. 5 (TKT-035). **El servidor recalcula las cifras** —ordenado, recibido acumulado, saldo y excedente— contra la orden y el renglón, nunca acepta las del cliente, las guarda en `contexto` y guarda además el **renglón** en `orden_compra_renglon_id` y la **cantidad excedente solicitada** en `cantidad_excedente` (TKT-019), que es el tope que la entrada podrá sumar al reenviarse (TKT-035). Va dirigida a `DIRECCION_GENERAL`. El bloqueo de `RN-03` ya crea su solicitud (TKT-021) y no pasa por aquí. La ruta se construye en el sprint 3; su test con una orden y una entrada reales viaja al sprint 5 con TKT-035
- [ ] `GET /api/v1/bitacora?regla_negocio=RN-03&obra_id=…&desde=…&hasta=…`, **paginada** —la consulta es la de TKT-007—, devuelve autorizaciones y rechazos con actor, momento, motivo y obra, distinguibles entre sí, **más los bloqueos que nunca se resolvieron** y las **recapturas de tope** que TKT-017 asienta con la misma regla (esc. 11). La ruta la monta este ticket desde la raíz de composición con `exigir_rol("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")` —`auditoria` no puede importar `identidad`—, y convierte el `usuario_id` que devuelve `consultar_bitacora` en el `UsuarioResumen` del borrador por la interfaz de `identidad`. Mientras `rutas_de` (la ayuda del test del enrutador, TC-47) no lea el contexto de inclusión, la dependencia `exigir_rol` se declara en el decorador de la propia ruta (`dependencies=[Depends(exigir_rol(...))]`) o se amplía `rutas_de` en este ticket: con `include_router(..., dependencies=[...])` la ruta queda protegida en ejecución, pero `violaciones()` la reporta como «sin proteger»
- [ ] Todos los importes como cadena; todos los rechazos con el contrato de error
- [ ] Los `403` `AUTO_RESOLUCION` y `NO_ES_SOLICITANTE` nacen en el caso de uso y no los asienta `exigir_rol`: el caso de uso los asienta como `DENEGAR` por la interfaz de auditoría (HDU-003 esc. 8)
- [ ] Tests HTTP `test_hdu003_esc01_…`, `esc02`, `esc03`, `esc07`, `esc08` y `esc11` en verde, con el escenario 11 sembrado con autorizaciones, rechazos y bloqueos sin resolver del mismo mes

**Non-goals** — No notifica por correo ni por ningún canal externo: el aviso es el contador. No implementa interfaz.

---

### TKT-028 · Interfaz de bandeja y resolución

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-027, TKT-008 |

**Qué hace.** La bandeja de Dirección General con su contador en la navegación, el detalle de cada solicitud y la resolución con motivo.

**Criterios técnicos**

- [ ] Contador de pendientes en la navegación, visible solo con `DIRECCION_GENERAL`, que desaparece al llegar a cero (HDU-003 esc. 1)
- [ ] Bandeja ordenada de la más antigua a la más reciente, con las columnas del escenario 2; las sin efecto, distinguibles y sin botones de resolver (esc. 10)
- [ ] Detalle con las cifras **del momento del bloqueo**, rotuladas así, y no las del disponible de hoy: si la partida siguió consumiéndose, el detalle tiene que seguir explicando por qué se bloqueó (esc. 3)
- [ ] Autorizar y rechazar usan el componente de **captura de motivo obligatorio** de TKT-008; el formulario no envía sin motivo, y si el servidor responde `422` el mensaje es el suyo (esc. 6)
- [ ] Un `409` `YA_RESUELTA` muestra quién y cuándo, y refresca la bandeja (esc. 9)
- [ ] Importes con `decimal.js`; ningún número nativo
- [ ] Recorrido de Playwright: requisición que se bloquea en HDU-002 y acaba autorizada aquí, que es uno de los dos que justifican la herramienta ([stack §7.3](06-stack-tecnologico.md#73-frontend))

**Non-goals** — No permite autorizar en lote. No muestra la bitácora de excepciones como pantalla: se consulta por API en la fase 1.

---

## Tickets de HDU-004 · Proveedores y órdenes de compra

Historia: [HDU-004](04-historias-usuario.md#hdu-004--proveedores-y-emisión-de-órdenes-de-compra) · 5 SP · **fase 1**

Sin orden de compra no hay contra qué recibir material (`RN-05`, `RN-06`): por eso esta historia está en el hilo vertical aunque no aplique ninguna regla dura.

> **Una arista del grafo que hay que fijar antes de empezar.** La [arquitectura §5](02-arquitectura.md#5-contextos-delimitados) dibuja `proveedores → compras`, pensada para la v1.1, y la historia dice que `compras` consulta el catálogo de `proveedores`. Las dos cosas juntas son un ciclo. Se resuelve **sin tocar el grafo**: `compras` declara en su capa de aplicación el puerto `CatalogoProveedores` y `proveedores` lo implementa, de modo que la arista sigue siendo `proveedores → compras`, y `orden_compra.proveedor_id` no lleva clave foránea ([modelo de datos §5](03-modelo-datos.md#5-compras)). Las consultas de `proveedores` que necesitan órdenes —la baja y el escenario 11— llaman a la interfaz publicada de `compras`, que es la dirección que el grafo ya permite.

---

### TKT-029 · Catálogo de proveedores

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-003, TKT-005, TKT-006, TKT-007, TKT-019 |

**Qué hace.** Esquema y CRUD del proveedor en el módulo `proveedores`, con los campos de la v1.1 ya capturables, y la baja protegida por las órdenes pendientes.

**Criterios técnicos**

- [ ] Tabla `proveedor` según [modelo de datos §9](03-modelo-datos.md#9-proveedores--v11), con `UNIQUE (rfc)` — invariante 28 —, `estado` `ACTIVO`, `DESACTIVADO` o `BAJA`, `tope_consignacion`, `dia_corte` y `dia_pago` aunque su lógica sea de la v1.1
- [ ] Alta con jueves y sábado como corte y pago por defecto (`RN-17`), visible en el selector al guardarse (HDU-004 esc. 2)
- [ ] RFC duplicado responde `409` `CONFLICTO` `RFC_DUPLICADO` mostrando el proveedor existente y no crea nada; la restricción única lo garantiza aunque la comprobación previa se salte (esc. 3)
- [ ] `GET /api/v1/proveedores`, `POST /api/v1/proveedores`, `GET /api/v1/proveedores/{proveedor_id}`, `PATCH /api/v1/proveedores/{proveedor_id}` para los datos de catálogo —no para el estado—
- [ ] **Dos operaciones de estado, y ninguna borra** (HDU-004 esc. 12). `POST /api/v1/proveedores/{proveedor_id}/desactivacion` con motivo **se admite siempre**: pasa a `DESACTIVADO`, deja de aparecer en el selector y en la emisión, conserva todo su historial y sus órdenes `ABIERTA` o `PARCIAL` siguen recibiendo material
- [ ] `POST /api/v1/proveedores/{proveedor_id}/baja` es la baja lógica definitiva —`BAJA`—: consulta por la interfaz publicada de `compras` las órdenes `ABIERTA` o `PARCIAL`, y si las hay responde `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` listándolas, con la acción de desactivar. **Nunca hay borrado físico**: no existe `DELETE` sobre proveedores, y un test recorre el enrutador para comprobarlo
- [ ] El proveedor implementa el puerto `CatalogoProveedores` que `compras` declara, respondiendo si existe y si está `ACTIVO`: uno `DESACTIVADO` o en `BAJA` no admite órdenes nuevas
- [ ] Altas, cambios, bajas y desactivaciones asentadas en la bitácora
- [ ] Tests `test_hdu004_esc02_…`, `esc03` y `esc12` en verde. El de la baja usa una orden `PARCIAL` **sembrada con `cantidad_recibida` mayor que cero** por la vía de pruebas —las órdenes reales llegan con TKT-030 y las entradas con TKT-035—, contra PostgreSQL real y no con dobles; el mismo escenario verifica que desactivar ese proveedor sí procede

**Non-goals** — No registra facturas, anticipos ni consignación (`RN-15`, `RN-16`, v1.1). No valida el RFC contra el SAT.

---

### TKT-030 · Emisión de la orden de compra desde una requisición

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-019, TKT-021, TKT-025, TKT-029 |

**Qué hace.** Convierte una requisición `EVALUADA` o `AUTORIZADA` en una orden de compra `ABIERTA` dirigida a un proveedor, copiando sus renglones, con folio único y consecutivo, y rechaza los estados desde los que no se puede emitir.

**Criterios técnicos**

- [ ] Una sola transacción: bloquea la requisición con `SELECT … FOR UPDATE`, comprueba su estado, valida el proveedor por el puerto `CatalogoProveedores` —`orden_compra.proveedor_id` no tiene clave foránea, y esta validación es lo único que la sostiene—, crea orden y renglones, pasa la requisición a `CONVERTIDA` y asienta la bitácora (HDU-004 esc. 4)
- [ ] La orden hereda `obra_id` de la requisición y alcanza su tipo de partida por `requisicion_id`: una requisición origina **como mucho una** orden, y esa cadena es de la que cuelga el semáforo
- [ ] Renglones **copiados** de la requisición, con `cantidad_ordenada`, `costo_unitario` y `cantidad_recibida = 0`; no se cambia el precio al emitir **(asumido: el escenario 4 dice "copiados", y un precio distinto movería el consumido sin pasar por `RN-03`)**
- [ ] `fecha_compromiso` opcional por renglón al emitir **(asumido: HDU-004 no la pide, pero sin ella el escenario 13 de HDU-005 no tiene desde cuándo contar la antigüedad del saldo)**
- [ ] Folio único y consecutivo, tomado de `folio_consecutivo` (TKT-019) con la fila bloqueada en la misma transacción: un fallo no deja huecos, como sí los dejaría una secuencia de PostgreSQL
- [ ] Desde una requisición `AUTORIZADA` la orden se crea igual y su representación expone la solicitud que la habilitó, alcanzada por la requisición, sin columna nueva (esc. 5)
- [ ] Desde `BLOQUEADA` o `RECHAZADA` responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado actual, **sin regla y sin asentarse como `RN-03`**: la regla ya se aplicó al bloquear, y repetirla contaría dos veces la misma excepción en HDU-003 esc. 11. Si está bloqueada, la acción es `VER_SOLICITUD_AUTORIZACION`, un `GET` a la solicitud que TKT-021 ya creó (esc. 6)
- [ ] Desde `CONVERTIDA` responde `409` `CONFLICTO` `ORDEN_YA_EMITIDA` con el folio de la orden existente; dos emisiones **simultáneas** de la misma requisición: exactamente una gana (esc. 7)
- [ ] Sin proveedor responde `422`; con un proveedor que no está `ACTIVO`, `409` `CONFLICTO` `PROVEEDOR_INACTIVO` **(asumido: el escenario 8 solo nombra la falta de proveedor)**; en ningún caso se crea orden (esc. 8)
- [ ] **El consumido no cambia al emitir**: el importe deja de contar como requisición viva y pasa a contar como saldo de orden. Un test compara el disponible antes y después, al céntimo ([modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo))
- [ ] `POST /api/v1/ordenes-compra` con `requisicion_id` y `proveedor_id`; `GET /api/v1/ordenes-compra/{orden_compra_id}`; `GET /api/v1/ordenes-compra?obra_id=…&proveedor_id=…&estado=…`
- [ ] Tests `test_hdu004_esc04_…` a `test_hdu004_esc08_…` en verde

**Non-goals** — No envía la orden al proveedor por ningún canal. No reparte una requisición entre varios proveedores. No reevalúa `RN-03`: el gasto ya se evaluó al levantar la requisición.

---

### TKT-031 · Cancelación de una orden sin recepciones

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-030 |

**Qué hace.** Cancela una orden `ABIERTA` sin ninguna entrada y devuelve la requisición al estado del que salió, sin liberar presupuesto. Rechaza la cancelación de una orden que ya recibió material y ofrece reprogramar el faltante.

**Criterios técnicos**

- [ ] `POST /api/v1/ordenes-compra/{orden_compra_id}/cancelacion` con motivo obligatorio, guardado en `orden_compra.motivo_cancelacion`; sin motivo, `422` **(asumido: el escenario 9 dice "indicando el motivo")**
- [ ] La orden pasa a `CANCELADA` y la requisición vuelve a `EVALUADA`, **o a `AUTORIZADA` si nació de una excepción resuelta**, para no perder la autorización de Dirección General; puede volver a convertirse (HDU-004 esc. 9, [modelo de datos §14](03-modelo-datos.md#14-máquinas-de-estado))
- [ ] **No libera presupuesto**: el importe vuelve al sumando de requisiciones vivas y el consumido no cambia. Un test compara el disponible antes y después, al céntimo. Para liberarlo hay que cancelar además la requisición, que es la única transición que suelta la reserva
- [ ] Con al menos una recepción responde `409` con regla `RN-06`, explica que ya hay material recibido y ofrece la acción `REPROGRAMAR` hacia la ruta de TKT-054 (esc. 10). Es la mitad de la decisión cuyo otro lado es HDU-005 esc. 10
- [ ] Bloquea con `SELECT … FOR UPDATE` **`orden_compra` primero y después sus renglones ordenados por id**, el mismo orden que la entrada de TKT-035 ([arquitectura §8.2](02-arquitectura.md#82-recepción-parcial--rn-06-y-rn-07)): una cancelación y una entrada simultáneas no pueden pasar las dos ni interbloquearse
- [ ] Bitácora con el motivo y los estados anterior y posterior de orden y requisición
- [ ] Tests `test_hdu004_esc09_…` y `test_hdu004_esc10_…` en verde. Hasta que exista TKT-035, el escenario 10 se prueba con `cantidad_recibida` sembrada por la vía de pruebas; en el sprint de HDU-005 se añade el recorrido con una entrada real

**Non-goals** — No implementa la reprogramación (TKT-054). No libera reserva: eso solo lo hace cancelar la requisición (TKT-023). No cancela órdenes con recepciones bajo ninguna autorización.

---

### TKT-032 · Consulta proveedor × obra e interfaz de catálogo y emisión

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-029, TKT-030, TKT-031 |

**Qué hace.** Responde a *"¿cuánto y de qué se le pidió a este proveedor en cada obra?"* y monta las pantallas de catálogo de proveedores, de emisión y de cancelación de órdenes.

**Criterios técnicos**

- [ ] `GET /api/v1/proveedores/{proveedor_id}/pedidos-por-obra?desde=…&hasta=…&estado=…`: por obra e insumo, cantidad e importe pedidos, más el total del proveedor; los datos los da la interfaz publicada de `compras` (HDU-004 esc. 11)
- [ ] Se prueba con el caso real del cliente: dos obras, mismo proveedor, mismo insumo —100 tableros para la obra 1 y 50 para la 2— y el desglose no los suma en una sola fila
- [ ] Interfaz de catálogo con el componente de formulario de TKT-008: el botón `+` abre el alta con el foco en el nombre (esc. 1); RFC duplicado muestra el existente (esc. 3); desactivar se ofrece siempre, y la baja con órdenes pendientes pinta el `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` con sus órdenes y la acción de desactivar tomada del contrato (esc. 12)
- [ ] Emisión desde la lista de requisiciones `EVALUADA` o `AUTORIZADA`, con selector que solo lista proveedores `ACTIVO`; los `409` de los escenarios 6 y 7 se pintan con la pantalla de bloqueo de TKT-008 y sus acciones
- [ ] Cancelación con el componente de captura de motivo; el `409` del escenario 10 ofrece la acción de reprogramar del contrato, no un botón cableado
- [ ] Importes con `decimal.js`
- [ ] Tests `test_hdu004_esc01_…` y `test_hdu004_esc11_…` en verde

**Non-goals** — No compara precios entre proveedores ni gestiona cotizaciones. No exporta la consulta.

---

## Tickets de HDU-005 · Entrada de material con recepción parcial

Historia: [HDU-005](04-historias-usuario.md#hdu-005--entrada-de-material-con-recepción-parcial) · 11 SP — **8 en la fase 1**, en línea, con los escenarios 1 a 14 y 21 a 23 —la entrada con excedente autorizado y la corrección sobre una orden `CERRADA`, que llegaron con las respuestas del cliente del 2026-10-17 a `PA-16` y `PA-17`—; **3 en la fase 2** con los escenarios 15 a 20, que son la captura diferible y la remisión adjunta (TKT-066, TKT-068)

---

### TKT-033 · Esquema y migraciones del módulo almacén

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-019 |

**Qué hace.** Crea las tablas del libro mayor de inventario y de las entradas, con los tipos de movimiento de la v1.1 ya contemplados.

**Criterios técnicos**

- [ ] Tablas `entrada_almacen`, `entrada_renglon` y `movimiento_inventario` según [modelo de datos §6](03-modelo-datos.md#6-almacén)
- [ ] `movimiento_inventario.tipo` con los seis valores —`ENTRADA`, `SALIDA`, `TRASPASO_SALIDA`, `TRASPASO_ENTRADA`, `MERMA`, `AJUSTE`— aunque la fase 1 use dos
- [ ] `movimiento_inventario.tipo_partida_id` `NOT NULL` y `obra_id` `NOT NULL` —invariante 1—: se copia del de la requisición de origen, y sin él un `AJUSTE` no llegaría a ninguna partida del semáforo
- [ ] `CHECK (cantidad >= 0)` y `CHECK (costo_unitario >= 0)` sobre `entrada_renglon` —invariante 8—; el movimiento lleva cantidad **con signo** y no tiene ese `CHECK`
- [ ] `UNIQUE (proveedor_id, folio_remision)` sobre `entrada_almacen` — invariante 29 —, para que el duplicado de HDU-005 esc. 7 lo detenga el motor y no solo la aplicación. `entrada_almacen.proveedor_id` se **copia de la orden** y no lleva clave foránea: sostiene la restricción sin cruzar a `proveedores` ([modelo de datos §2](03-modelo-datos.md#2-convenciones))
- [ ] `entrada_renglon.excedente NUMERIC(14,4) NOT NULL DEFAULT 0` —la cantidad del renglón que pasó del saldo, la marca de HDU-005 esc. 21— y `entrada_renglon.solicitud_autorizacion_id`, **sin clave foránea**: la solicitud es de `compras`, y la valida `almacen` por la interfaz publicada de `compras`, por la arista `almacen → compras` que ya existe
- [ ] `entrada_almacen` nace sin `capturado_en`: la columna es de la fase 2 y la añade TKT-064
- [ ] El rol de aplicación tiene `INSERT` y `SELECT` sobre `movimiento_inventario`, **no** `UPDATE` ni `DELETE` — invariante 30, [ADR-005](adr/20260918-ledger-inventario.md) —: la revocación va en esta migración, con un test que lo intenta con el rol de aplicación
- [ ] Índices `(obra_id, tipo_partida_id, ocurrido_en)` y `(obra_id, insumo_id, ocurrido_en)` sobre `movimiento_inventario` ([§15](03-modelo-datos.md#15-la-consulta-del-semáforo))
- [ ] Un test inspecciona el esquema y falla si aparece cualquier columna de existencia en cualquier tabla (DoD de HDU-005)

**Non-goals** — No crea `traspaso` ni `merma` (`RN-08`, `RN-09`, v1.1). No implementa lógica.

---

### TKT-034 · Reglas RN-05, RN-06 y RN-07 en el dominio

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-004, TKT-005 |

**Qué hace.** Escribe como funciones puras la validación contra remisión, el cálculo del saldo pendiente acumulado entre entregas, la derivación del estado de la orden y el límite de no recibir más de lo ordenado.

**Criterios técnicos**

- [ ] `RN-05`: una entrada sin folio de remisión es inválida y el resultado lo explica: la entrada se valida contra la remisión del proveedor, no contra la orden (HDU-005 esc. 4)
- [ ] `RN-06`: saldo pendiente por renglón = ordenado − recibido acumulado, sobre cualquier número de entregas (esc. 2 y 3)
- [ ] Derivación del estado de la orden desde sus renglones: `ABIERTA` sin nada recibido, `PARCIAL` con algún saldo, `CERRADA` **solo** con todo entregado —lo recibido cubre lo ordenado, con o sin excedente autorizado—. No existe ninguna función que cierre con saldo (esc. 1, 3, 12 y 21)
- [ ] `RN-07`: entrante mayor que el saldo devuelve el excedente con ordenado, recibido acumulado y saldo (esc. 5)
- [ ] `RN-07` **con autorización** (`PA-16`, resuelta el 2026-10-17): recibe el saldo, la cantidad entrante y la solicitud citada —estado, renglón, cantidad excedente autorizada y si ya se consumió— y devuelve la cantidad que se suma a la recepción y el `excedente` del renglón, o el rechazo. Con la solicitud `PENDIENTE` o `RECHAZADA`, o con un excedente mayor que el autorizado, el rechazo es `RN-07` con las cifras; con una solicitud de otro renglón o ya consumida, el código `SOLICITUD_NO_APLICABLE` (esc. 21 y 22)
- [ ] Un intento de cierre con saldo devuelve la violación de `RN-06` con la acción `REPROGRAMAR` (esc. 12)
- [ ] Sin framework, ORM ni HTTP; identificadores `RN-05`, `RN-06` y `RN-07` en docstrings y nombres de test
- [ ] Tests de dominio de los escenarios 1, 2, 3, 4, 5, 12, 21 y 22

**Non-goals** — No persiste nada. No decide el estado de la orden en ningún otro sitio: el caso de uso lo pide aquí.

---

### TKT-035 · Caso de uso de entrada de material

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** L · **Depende de** TKT-033, TKT-034, TKT-030, TKT-021, TKT-027, TKT-007 |

**Qué hace.** Registra una entrada contra una orden de compra: valida, escribe el movimiento en el libro mayor, actualiza lo recibido y **deriva** el estado de la orden, todo en una transacción. Es el flujo de la [arquitectura §8.2](02-arquitectura.md#82-recepción-parcial--rn-06-y-rn-07). Acepta además el reenvío de una entrada excedente con su autorización citada. **Pasó de M a L** con ese reenvío (`PA-16`, resuelta el 2026-10-17).

> **Si la talla L no cabe en el sprint, la costura es el reenvío.** La entrada en línea con sus rechazos —escenarios 1 a 7 y 14— va primero y cierra el hilo vertical; el reenvío con excedente autorizado —escenarios 21 y 22— puede ir detrás en el mismo sprint 5 sin tocarla, porque solo añade un camino a la misma transacción. Mientras falte, un excedente autorizado no se puede registrar todavía; lo que nunca ocurre es recibirlo sin autorización.

**Criterios técnicos**

- [ ] Una sola transacción: bloquea con `SELECT … FOR UPDATE`, **por la interfaz publicada de `compras`**, **`orden_compra` primero y después sus renglones ordenados por id** —el mismo orden que la cancelación de TKT-031, [arquitectura §8.2](02-arquitectura.md#82-recepción-parcial--rn-06-y-rn-07)—, copia `proveedor_id` de la orden a `entrada_almacen`, valida con TKT-034, inserta entrada, renglones y un movimiento `ENTRADA` por renglón, actualiza `cantidad_recibida`, deriva el estado y asienta la bitácora
- [ ] El movimiento copia `tipo_partida_id` de la requisición y `costo_unitario` del renglón de la orden; `importe = cantidad × costo_unitario` sin redondeo intermedio
- [ ] Entrada completa: orden `CERRADA`, saldo cero, movimiento por las 100 unidades (HDU-005 esc. 1); parcial: orden `PARCIAL` con saldo de 50 (esc. 2); segunda entrega con otro folio: `CERRADA` y dos movimientos separados (esc. 3)
- [ ] Sin folio: `422` con la regla `RN-05` y sin movimiento (esc. 4)
- [ ] Excedente: `409` con `RN-07`, detalle con ordenado, recibido acumulado, saldo y excedente, acción `SOLICITAR_AUTORIZACION`, **ningún movimiento** y saldo intacto: la transacción se deshace entera (esc. 5)
- [ ] La acción `SOLICITAR_AUTORIZACION` apunta a `POST /api/v1/solicitudes-autorizacion`, que es de TKT-027: crea en una petición aparte una `solicitud_autorizacion` `EXCEDE_ORDENADO` con las cifras **recalculadas por el servidor**, el renglón y la cantidad excedente. Va aparte porque la entrada se deshizo entera y no queda nada persistido de lo que colgarla. Autorizarla no registra nada (TKT-025): la entrada se **reenvía** (`PA-16`, resuelta el 2026-10-17)
- [ ] **Reenvío con el excedente autorizado** — HDU-005 esc. 21 —: la misma `POST /api/v1/entradas-almacen` acepta `solicitud_autorizacion_id` por renglón. Dentro de la transacción y después de los renglones, bloquea la solicitud y la lee **por la interfaz publicada de `compras`**, la evalúa con TKT-034 y, si procede, suma a la recepción hasta `saldo + excedente autorizado`, guarda `entrada_renglon.excedente` con la cantidad que pasó del saldo y la solicitud citada, incrementa `cantidad_excedente_autorizada` del renglón de la orden por la interfaz de `compras` —es la entrada, no la resolución, la que la mueve— y deriva la orden a `CERRADA`. La bitácora asienta la entrada con `RN-07` y la solicitud que la ampara
- [ ] **El excedente es costo ejercido**: el movimiento `ENTRADA` va por la cantidad recibida entera, saldo más excedente, con el mismo costo unitario, y entra en el `ejercido` y en el `consumido` por `FuenteEjercido` como cualquier material recibido. Un test lo lee en el disponible de TKT-023
- [ ] Rechazos del reenvío — HDU-005 esc. 22 —, todos con la transacción deshecha entera, ningún movimiento y la solicitud intacta: con la solicitud `PENDIENTE` o `RECHAZADA`, `409` `RN-07` con su estado; con más excedente que el autorizado, `409` `RN-07` con autorizado y solicitado; con una solicitud de otro renglón o ya consumida, `409` `CONFLICTO` `SOLICITUD_NO_APLICABLE`, código que se añade al catálogo del borrador en el mismo PR (TKT-005)
- [ ] **Una solicitud autorizada se consume una sola vez**: dos reenvíos simultáneos que citan la misma solicitud se serializan en su bloqueo de fila, y el segundo recibe `SOLICITUD_NO_APLICABLE`. Test con dos transacciones reales
- [ ] Contra una orden `CERRADA` o `CANCELADA`: `409` `CONFLICTO` `ORDEN_NO_ADMITE_ENTRADAS` con el estado actual (esc. 6)
- [ ] Folio de remisión repetido para el mismo proveedor: `409` `CONFLICTO` `FOLIO_REMISION_DUPLICADO` con la entrada previa (esc. 7)
- [ ] Dos entradas **simultáneas** contra el mismo saldo: la segunda espera, lee lo recibido por la primera y, si ya no cabe, recibe `RN-07`. El vencimiento de `lock_timeout` se traduce a `409` `CONCURRENCIA` (`RNF-16`)
- [ ] El `CHECK (cantidad_recibida <= cantidad_ordenada + cantidad_excedente_autorizada)` —invariante 2— se prueba **en el motor**, con una escritura directa que lo viola
- [ ] **`almacen` implementa el puerto `FuenteEjercido`** que declara `compras` (TKT-021) y sustituye el adaptador *cero real*: devuelve el ejercido de materiales —la suma de `movimiento_inventario.importe`— por tipo de partida y, para el control por volumen, por `(tipo_partida_id, insumo_id)`, leído con la sesión de la transacción en curso. La arista es `almacen → compras`, que ya existe; `compras` no importa nada de `almacen`
- [ ] **Dueño del test de HDU-005 esc. 14**: el ejercido del tipo de partida refleja la entrada **en la misma consulta siguiente**, sin proceso por lotes. Un test registra $18,000 a `MUROS` y lee el disponible de TKT-023, que ya pasa por `FuenteEjercido`
- [ ] Tests `test_hdu005_esc01_…` a `esc07`, `esc14`, `esc21` y `esc22` en verde contra PostgreSQL real; **dueño de los tests de HDU-005 esc. 21 y 22**

**Non-goals** — No asigna el estado de la orden a mano. No resuelve la solicitud de excedente: es TKT-025. No evalúa `RN-03` al recibir, tampoco el excedente: ninguna entrada lo hace. No acepta entradas encoladas sin conexión: es TKT-068, en la fase 2. No adjunta la remisión: es TKT-066.

---

### TKT-054 · Reprogramación del faltante

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-019, TKT-035 |

**Qué hace.** Da una nueva fecha comprometida al saldo de un renglón con motivo obligatorio (**PA-07**), deja la orden en `PARCIAL` y conserva comprometido el presupuesto. Es la vía que sustituye al cierre con saldo, que no existe.

**Criterios técnicos**

- [ ] `POST /api/v1/ordenes-compra/{orden_compra_id}/renglones/{renglon_id}/reprogramacion` con fecha nueva y motivo; vive en `compras`, dueño de `reprogramacion_entrega`
- [ ] Registra fecha anterior, fecha nueva, saldo pendiente y motivo; actualiza `fecha_compromiso`; la orden **permanece** `PARCIAL`; bitácora (HDU-005 esc. 10)
- [ ] El presupuesto sigue comprometido: un test compara el disponible antes y después, al céntimo
- [ ] Sin motivo o con fecha anterior a la vigente: `422` señalando el campo, y la fecha vigente no cambia (esc. 11).
- [ ] Un renglón sin fecha comprometida previa admite la primera, con `fecha_anterior` nula **(asumido; ver TKT-030)**
- [ ] `POST /api/v1/ordenes-compra/{orden_compra_id}/cierre` existe **solo para responder**: con saldo, `409` con `RN-06`, la explicación y la acción `REPROGRAMAR` (esc. 12); sin saldo, la orden ya está `CERRADA` por derivación. **No cierra nunca**, y en el borrador lleva `x-sin-exito: true`, de modo que TKT-061 la excluye de la comparación de respuestas `2xx`. Un test recorre las rutas y verifica que ninguna lleva una orden con saldo a `CERRADA` (DoD de HDU-005)
- [ ] Reprogramar con los roles `COMPRAS` o `ALMACEN` **(asumido: el escenario no dice quién)**
- [ ] Tests `test_hdu005_esc10_…`, `esc11` y `esc12` en verde

**Non-goals** — No libera presupuesto: el material se sigue debiendo. No cierra órdenes. No notifica al proveedor.

---

### TKT-036 · Corrección de entradas por movimiento de ajuste

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-035 |

**Qué hace.** Corrige una entrada mal capturada con un movimiento `AJUSTE` de signo contrario y motivo, sin tocar el movimiento original, y recalcula el saldo pendiente.

**Criterios técnicos**

- [ ] `POST /api/v1/entradas-almacen/{entrada_id}/correccion` con renglón, **`cantidad_correcta` absoluta** —lo que de verdad llegó— y motivo. El cliente nunca manda el ajuste: **el servidor calcula la diferencia** y escribe el `AJUSTE` de signo contrario
- [ ] Sobre una orden `PARCIAL` de 100 con una entrada capturada de 70 que en realidad fue de 50: genera un `AJUSTE` de −20 con su motivo, el mismo `tipo_partida_id` y el mismo costo unitario que la entrada; **no** modifica ni borra el original; la existencia calculada pasa a 50, el saldo de la orden pasa de 30 a 50, `cantidad_recibida` del renglón se recalcula por la interfaz de `compras` y la orden sigue `PARCIAL` (HDU-005 esc. 8)
- [ ] Sin motivo: `422` y ningún movimiento (esc. 9)
- [ ] Una cantidad correcta que dejaría lo recibido por encima de lo ordenado más el excedente autorizado responde `409` con `RN-07`; una negativa, `422`
- [ ] **No se corrige una entrada de una orden `CERRADA`** (`PA-17`, resuelta el 2026-10-17): `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado de la orden, ningún movimiento y `cantidad_recibida` intacta — HDU-005 esc. 23. En el [modelo de datos §14](03-modelo-datos.md#14-máquinas-de-estado) `CERRADA` es terminal, y corregir a la baja la reabriría. Sobre una orden `ABIERTA` o `PARCIAL` la corrección funciona normal
- [ ] El historial muestra los dos movimientos con su trazabilidad
- [ ] Un test verifica que ninguna corrección emite `UPDATE` ni `DELETE` sobre `movimiento_inventario`: con el permiso de TKT-033, el intento fallaría en el motor
- [ ] Tests `test_hdu005_esc08_…`, `esc09` y `esc23` en verde; **dueño del test de HDU-005 esc. 23**

**Non-goals** — No permite editar ni borrar un movimiento. No implementa mermas ni traspasos.

---

### TKT-037 · Endpoints de entradas, saldos y existencias

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-035, TKT-036, TKT-054 |

**Qué hace.** Expone el registro y la consulta de entradas, los saldos pendientes por obra con su antigüedad y su contador de reprogramaciones, la existencia calculada y el historial de movimientos.

**Criterios técnicos**

- [ ] `POST /api/v1/entradas-almacen`, `GET /api/v1/entradas-almacen` y `GET /api/v1/entradas-almacen/{entrada_id}`, con los roles `ALMACEN` y `RESIDENTE`, que según el [PRD §4](01-descripcion-producto.md#4-usuarios-y-roles) también recibe material contra remisión
- [ ] `GET /api/v1/obras/{obra_id}/saldos-pendientes`: por orden e insumo, ordenado, recibido y saldo; fecha comprometida vigente; **cuántas veces se reprogramó cada renglón**; antigüedad desde la **primera** fecha comprometida (HDU-005 esc. 13)
- [ ] `GET /api/v1/obras/{obra_id}/existencias`: suma de movimientos por insumo; **no** lee ninguna columna de stock porque no existe
- [ ] `GET /api/v1/obras/{obra_id}/movimientos-inventario` con filtros por insumo, tipo y fechas, y la referencia al documento de origen
- [ ] Importes y cantidades como cadena; rechazos con el contrato de error
- [ ] Documentación de API generada y coherente con el borrador (TKT-061)
- [ ] Test `test_hdu005_esc13_…` en verde, con una orden reprogramada dos veces

**Non-goals** — No expone ninguna columna de stock: no existe. No acepta `id` del cliente ni `capturado_en`: las rutas de captura los aceptan desde TKT-064, en la fase 2.

---

### TKT-038 · Interfaz de recepción, en línea

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-037, TKT-008 |

**Qué hace.** La pantalla de recepción de material, **en línea**: captura de remisión y cantidades contra la orden, saldo pendiente visible, reprogramación, corrección e historial.

**Criterios técnicos**

- [ ] Selección de la orden por obra y proveedor; captura de folio y fecha de remisión obligatorios, con el error de `RN-05` del servidor si faltan
- [ ] Por renglón: ordenado, recibido, saldo pendiente y fecha comprometida vigente **antes** de capturar
- [ ] El `409` de `RN-07` se pinta con la pantalla de bloqueo de TKT-008, con las cifras del detalle y la acción de solicitar autorización tomada del contrato (HDU-005 esc. 5)
- [ ] **La captura rechazada se conserva**, ligada a su solicitud: con la solicitud `AUTORIZADA`, reenviarla es una acción —**"Registrar con excedente autorizado"**—, no una recaptura, y manda la misma entrada con `solicitud_autorizacion_id` en el renglón. Mientras la solicitud siga `PENDIENTE`, la pantalla muestra su estado; si el servidor rechaza el reenvío, pinta el contrato que devuelve (esc. 21 y 22)
- [ ] En el detalle de la entrada y en el historial, el renglón con excedente se marca como tal, con la cantidad que pasó del saldo y la solicitud que lo ampara (esc. 21)
- [ ] El `409` de folio duplicado muestra la entrada previa (esc. 7)
- [ ] Reprogramación y corrección con el componente de captura de motivo (esc. 8 a 11); la corrección no se ofrece en una orden `CERRADA`, y si el servidor la rechaza se pinta su contrato (esc. 23)
- [ ] Historial de movimientos y de reprogramaciones por orden
- [ ] Vista de saldos pendientes de la obra, con antigüedad y contador de reprogramaciones (esc. 13)
- [ ] Usable en pantalla de teléfono: la recepción ocurre de pie en el almacén de obra
- [ ] **Sin señal, la pantalla lo dice y no captura**: en la fase 1 la recepción exige servidor, y un formulario que se queda girando hasta agotar el tiempo enseña a desconfiar del sistema
- [ ] Ningún cálculo de `RN-07` en el cliente: el saldo se muestra, no se aplica

**Non-goals** — **No es diferible sin conexión**: la captura encolada, el saldo leído de caché y el conflicto al sincronizar son TKT-068, en la fase 2, sobre el armazón de TKT-063 y la sincronización de TKT-064. No adjunta la remisión (TKT-066). No incluye traspasos ni mermas.

---

## Tickets de HDU-006 · Semáforo de obra

Historia: [HDU-006](04-historias-usuario.md#hdu-006--semáforo-de-obra) · 6 SP · **fase 1**, con la mano de obra y el avance servidos por un adaptador simulado hasta que TKT-069 lo retira en el sprint 8 ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md))

---

### TKT-060 · Puerto de fuentes de mano de obra y avance, con adaptador simulado

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-002, TKT-004 · **Sprint 4** |

**Qué hace.** Separa en `analitica` **qué fuentes existen** de **cómo se agregan**: el semáforo lee el destajo, la nómina imputada y el avance físico a través de un puerto con tres adaptadores —`SIMULADO` y `VACIO` en la fase 1, `REAL` desde el sprint 8 (TKT-069)—, sin tocar la consulta ni la interfaz ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md)).

**Criterios técnicos**

- [ ] Puerto `FuentesManoDeObraYAvance` en la capa de aplicación de `analitica`, con una lectura por fuente: destajo por tipo de partida (`DESTAJO`), nómina imputada a la obra (`NOMINA`) y avance físico por tipo de partida (`AVANCE_FISICO`), que cubre **alcance y m² validados**: no hay fuente `ALCANCE`. Cada lectura devuelve su valor **y su origen**: `REAL`, `SIMULADA` o `SIN_DATOS`
- [ ] El origen se declara **por fuente** en el metadato, no para todo el puerto: con el adaptador real la nómina sale `SIN_DATOS` hasta el sprint 9 mientras destajo y avance físico ya son `REAL`, y el metadato tiene que poder decirlo
- [ ] **Tres adaptadores, cada uno con su test**: `SIMULADO`, solo en `local`, `pruebas` y `demostracion`; **`VACIO`**, que devuelve todas las fuentes `SIN_DATOS` y es **el único admitido en `produccion` durante la fase 1**; y `REAL`, que es TKT-069. Este ticket entrega los dos primeros
- [ ] El adaptador `SIMULADO` lee un archivo semilla versionado de datos ficticios **(asumido: `backend/semillas/simulado/*.csv`)**, con importes leídos como `Decimal` desde cadena —nunca como flotante— y validado al cargar: tipos de partida existentes y áreas que existen en la línea base de demostración (consecuencia negativa declarada en ADR-017)
- [ ] El adaptador `SIMULADO` **solo entrega avance en estado `VALIDADO`**: la semilla puede traer mediciones capturadas y no validadas para que el escenario 10 se pueda demostrar, y no deben contar
- [ ] **La aplicación no arranca** con el adaptador `SIMULADO` si `entorno = produccion`: lo rechaza la validación de `pydantic-settings`, igual que un secreto ausente (`RNF-07`, regla 4 de ADR-017). Un test arranca con la combinación prohibida y verifica que falla; otro arranca `produccion` con `VACIO` y verifica que el semáforo declara las tres fuentes `SIN_DATOS` y pinta el aviso de cifra parcial
- [ ] **Lo simulado nunca entra en el `consumido` de `RN-03`** (regla 1). El consumido lo calcula `compras` (TKT-021) y `analitica` lo lee de él, nunca al revés; en la fase 1 el término de destajo vale cero, y es un cero real: no existe `pago_destajo`. El contrato `grafo-analitica` de TKT-002 ya impide que `compras` importe `analitica`, y este ticket no lo relaja
- [ ] Ningún adaptador escribe en ningún módulo ni crea tablas de `avance` o de `personal`; el `SIMULADO` lee su semilla de un archivo, no de la base (regla 5); `analitica` sigue conectada con el rol de solo lectura —invariante 21—
- [ ] **Test `test_hdu006_esc15_…`**: con un destajo simulado que haría exceder la partida, una requisición que cabe en el disponible **real** queda `EVALUADA`, y el disponible de TKT-023 no cambia al activar o vaciar la semilla
- [ ] **Test `test_hdu006_esc14_…` del puerto**: con `SIMULADO`, el puerto declara `SIMULADA` en destajo, nómina y avance físico. La parte HTTP del mismo escenario —`fuentes[]` y la desviación con `ilustrativa: true`— es de TKT-040

> **El riesgo de esta decisión no está en el tablero sino en la regla.** Un destajo simulado que llegara al consumido bloquearía requisiciones reales con dinero que no existe. Por eso el escenario 15 es de rechazo y vive en este ticket, no en la interfaz: lo que hay que probar es que el número que decide no se entera de que hay datos simulados.
>
> **Los escenarios 14 y 15 de HDU-006 tienen vigencia de fase 1.** Cuando TKT-069 retira el adaptador simulado, sus tests se retiran con él y los escenarios salen del verificador con el segmento `· retirado por TKT-069` en su título; no se reescriben. Lo que queda es su contrario: que ninguna fuente salga `SIMULADA`.
>
> **Cuando nazca `pago_destajo` en la fase 2, el término de destajo del consumido deja de ser cero** porque `avance` implementa el puerto `FuenteEjercido` de `compras` (TKT-069), no porque se amplíe aquí ninguna consulta. El adaptador simulado se **elimina en el sprint 8, con TKT-069**; no se conserva como opción, porque sería configuración muerta con capacidad de mentir.

**Non-goals** — No implementa el adaptador real (TKT-069). No genera datos simulados en tiempo de ejecución ni los proyecta. No toca el cálculo del consumido de TKT-021.

---

### TKT-039 · Consulta del semáforo

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-017, TKT-021, TKT-030, TKT-060 · TKT-035 para el escalón 2 |

**Qué hace.** La consulta del semáforo por obra y tipo de partida, con el consumido y el disponible que calcula `compras` y las fuentes del puerto de TKT-060, y el cálculo de avance, desviación y alerta en `dominio/`.

**Criterios técnicos**

- [ ] **`analitica` no reescribe las CTE del consumido.** Por tipo de partida obtiene `requisiciones_vivas`, `comprometido`, `ejercido`, `consumido` y `disponible` —con el presupuestado contra el que se calculan— llamando a la interfaz publicada de `compras`, con el rol de solo lectura —invariante 21—. La definición es una sola ([modelo de datos §15](03-modelo-datos.md#el-consumido-de-rn-03)), y el disponible del tablero es exactamente el que aplica `RN-03`
- [ ] Destajo, nómina y avance físico **vienen del puerto de TKT-060**, nunca de una consulta propia del semáforo
- [ ] **Cuatro filas por obra**, una por tipo de partida, más la fila de totales (HDU-006 esc. 1 y 13); cada fila expone `requisiciones_vivas` y `disponible`. El desglose por ubicación queda para TKT-040
- [ ] **El `ejercido` de cada fila es solo real** —el de `compras`, el que entra en el consumido—: materiales y, en la fase 2, destajo, con el desglose por fuente; el destajo llega por el tipo de partida de su etapa, no por reparto (esc. 4, **PA-08**). Lo que el puerto entregue como `SIMULADA` va en **`ejercido_simulado`**, aparte y nullable, nunca sumado al ejercido
- [ ] La nómina se agrega **a nivel de obra** en fila propia marcada como no imputada a partida; entra en el total y no en las desviaciones (esc. 5, **PA-10**)
- [ ] **El avance físico se divide entre el alcance**, no entre `SUM(avance.m2_contrato)`, y es `NULL` —no cero— mientras no haya nada validado (regla 12 de `CLAUDE.md`)
- [ ] Función pura en `analitica/dominio` que calcula la desviación como `(ejercido + ejercido_simulado) − presupuestado × avance`, con **`ilustrativa: true`** si alguna de sus entradas es `SIMULADA`, y la propaga `NULL` si el avance es `NULL`: −$2,000 en verde (esc. 2), $30,000 en rojo por encima del umbral que declara el escenario (esc. 3), *sin avance medido* (esc. 9)
- [ ] **Tres colores**, `VERDE`, `AMARILLO` y `ROJO` (`PA-18`, resuelta el 2026-10-17), y `SIN_AVANCE_MEDIDO` como **estado aparte, no un color**: sin avance validado no hay juicio. El corte es **(asumido, sin bloqueo)**: `VERDE` con desviación ≤ 0; `AMARILLO` con desviación > 0 y desviación relativa ≤ `obra.umbral_alerta_pct`; `ROJO` con relativa > umbral. Sin umbral configurado en la obra, toda desviación > 0 es `ROJO`. La desviación relativa se mide sobre `presupuestado × avance`
- [ ] **La alerta sale con `ROJO`** (esc. 11, F7.3, TKT-011), y `AMARILLO` no alerta — esc. 16. **Una desviación ilustrativa no emite alerta**: con datos simulados no se alerta a nadie
- [ ] **Dueño del test de HDU-006 esc. 16**: una partida con desviación positiva por debajo del umbral de la obra queda `AMARILLO` y sin alerta; en el mismo test, la misma partida sin umbral configurado queda `ROJO`
- [ ] Solo cuenta el avance `VALIDADO` (esc. 10): lo garantiza el puerto y un test con avance capturado sin validar
- [ ] Sin línea base congelada responde `409` `CONFLICTO` `SIN_LINEA_BASE_CONGELADA`, con la acción de ir a congelarla para quien puede hacerlo y **sin cifras** (esc. 8)
- [ ] Plan de ejecución verificado con el volumen real de ~4,900 conceptos; la prueba que falla el pipeline por encima de 2 s es de TKT-058 (`RNF-15`)
- [ ] Tests `test_hdu006_esc01_…` a `esc03`, `esc05`, `esc08` a `esc11`, `esc13` y `esc16` en el escalón 1; `esc04` —materiales en el ejercido— en el escalón 2, con entradas reales de TKT-035. Los de desviación, sin base de datos

> **TKT-039 se construye en escalones, y el corte en fases cambia cuáles.** En el sprint 4 no existe `movimiento_inventario`, y `avance`, `alcance_destajo`, `pago_destajo` e `imputacion_nomina_obra` no existen en toda la fase 1. Escribir la consulta entera de una vez no compila; por eso las fuentes que faltan llegan por puertos.
>
> | Cuándo | Qué añade | Qué ve la dirección |
> |---|---|---|
> | **Sprint 4** | Presupuestado, requisiciones vivas, comprometido, consumido y disponible leídos de `compras`, con el ejercido en *cero real* (adaptador de TKT-021); destajo, nómina y avance **simulados** por TKT-060 | Tope, reserva y pedido sin recibir, reales; la mano de obra simulada en su propia columna marcada; desviación *ilustrativa* y sin alertas |
> | **Sprint 5** | `almacen` implementa `FuenteEjercido` (TKT-035): el material recibido entra en el ejercido y en el consumido | Lo anterior más el material recibido, real |
> | **Sprint 8** | TKT-069 retira el adaptador simulado entero: destajo y avance físico `REAL`, nómina `SIN_DATOS` | Ninguna cifra simulada; la nómina declarada como faltante |
> | **Sprint 9** | TKT-056 conecta la nómina imputada: `NOMINA` pasa a `REAL` | El tablero completo, sin avisos |
>
> Cada escalón **actualiza el metadato de fuentes** que TKT-040 expone y TKT-041 pinta, de modo que el escenario 6 de HDU-006 siga siendo cierto en cada uno, y el 14 mientras quede algo simulado. La consulta y su interfaz no cambian entre escalones; cambia quién responde a los puertos.

**Non-goals** — No prorratea mano de obra entre partidas: produciría precisión falsa. No usa `SUM(avance.m2_contrato)` como denominador: es el índice de desviación de volumen, no el avance. No calcula el consumido: lo lee de `compras`. No mantiene tabla de resumen ni proceso nocturno.

---

### TKT-040 · Endpoints del semáforo, desglose y detalle

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-039 · TKT-035 para el escalón del sprint 5 |

**Qué hace.** Expone el semáforo, su metadato de fuentes, el desglose de una partida, el detalle hasta el movimiento de origen y el resumen de alertas.

**Criterios técnicos**

- [ ] `GET /api/v1/obras/{obra_id}/semaforo`: filas por tipo de partida —con `requisiciones_vivas`, `disponible`, `ejercido` solo real y `ejercido_simulado` aparte—, fila de nómina, totales y **`fuentes[]`** con `REAL`, `SIMULADA` o `SIN_DATOS` para `PRESUPUESTADO`, `COMPROMETIDO`, `MATERIALES`, `DESTAJO`, `NOMINA` y `AVANCE_FISICO` (HDU-006 esc. 6 y 14)
- [ ] La desviación viaja con **`ilustrativa: true`** si alguna de sus entradas es `SIMULADA` (regla 3 de ADR-017)
- [ ] `GET /api/v1/obras/{obra_id}/semaforo/partidas/{tipo_partida_id}`: desglose por fuente y desglose **por ubicación del presupuestado** —**nivel y área**, desde la línea base congelada— (esc. 13). El material no tiene ubicación en el libro mayor y no se inventa **(asumido: es la lectura del escenario 13 compatible con el [modelo de datos §6](03-modelo-datos.md#6-almacén))**
- [ ] `GET /api/v1/obras/{obra_id}/semaforo/partidas/{tipo_partida_id}/movimientos`: los movimientos del ejercido con fecha, tipo, `cantidad`, `unidad`, `motivo`, documento de origen y responsable, con referencia navegable a la entrada de almacén (esc. 7). **Es el escalón del sprint 5**: su test necesita entradas reales y viaja con TKT-035. El renglón de nómina es la parte de fase 2 del escenario
- [ ] Cada fila lleva su `estado` —`VERDE`, `AMARILLO`, `ROJO` o `SIN_AVANCE_MEDIDO`, que es un estado sin color— calculado por TKT-039, como lo declara el borrador; el cliente no lo deriva de las cifras (esc. 2, 3 y 16)
- [ ] `GET /api/v1/semaforo/alertas`: partidas en `ROJO` de todas las obras activas, para el resumen consolidado, **excluidas las de desviación ilustrativa**; las `AMARILLO` no aparecen (esc. 11 y 16)
- [ ] Sin el rol que permite consultar el semáforo responde `403` **sin ningún importe** en el cuerpo (esc. 12): en el MVP el permiso es por rol, no por obra (TKT-006), y el escenario es el de un usuario sin el rol
- [ ] Ningún importe como número JSON: todos como cadena, comprobado sobre el esquema publicado
- [ ] Tests HTTP `test_hdu006_esc06_…`, `esc12` y `esc14` —la parte HTTP; la del puerto es de TKT-060— en el escalón 1; `esc07` en el del sprint 5

**Non-goals** — No exporta a Excel ni a PDF. No calcula nada: lee lo que TKT-039 produce.

---

### TKT-041 · Interfaz del semáforo

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-040, TKT-008 · TKT-035 para el escalón del sprint 5 |

**Qué hace.** El tablero de obra: cuatro filas con su color, la fila de nómina aparte, los avisos de cifra parcial y de dato simulado, y el desglose navegable hasta el movimiento.

**Criterios técnicos**

- [ ] Cuatro filas por obra con sus columnas y la fila de totales (HDU-006 esc. 1 y 13); color `VERDE`, `AMARILLO` o `ROJO` según TKT-039 (`PA-18`, resuelta el 2026-10-17), y *sin avance medido* como estado, no como color (esc. 2, 3 y 16). El color lo trae el servidor; el cliente no lo calcula
- [ ] **Aviso de cifra parcial** cuando **alguna fuente no es `REAL`** —`SIN_DATOS` o `SIMULADA`—, diciendo cuáles; la cifra no se presenta como costo real completo (esc. 6)
- [ ] **El ejercido real se pinta en su celda y lo simulado en su propia columna**, marcada *dato simulado* celda a celda; rótulo **"ilustrativa"** en la desviación que llega con `ilustrativa: true`. La marca está en la celda, no en una nota al pie que una captura de pantalla recorta (esc. 14, ADR-017)
- [ ] El letrero de *datos simulados* **se genera desde `fuentes[]`**, no es fijo: desaparece solo cuando ninguna fuente sale `SIMULADA`
- [ ] Fila de mano de obra de nómina separada y marcada como no imputada a partida (esc. 5)
- [ ] Distinción explícita entre **"sin avance medido"** y desviación cero: con avance `NULL` las celdas de avance y de desviación se rotulan *sin avance medido*; el valor que viaja sigue siendo `null`, nunca `0` (esc. 9)
- [ ] Desglose navegable hasta la entrada de almacén de origen (esc. 7), en el escalón del sprint 5; partidas en alerta —las `ROJO`— marcadas (esc. 11); una `AMARILLO` lleva su color y ninguna marca de alerta (esc. 16); nunca alerta con desviación ilustrativa
- [ ] Obra sin línea base: pantalla de bloqueo con la acción de congelar si el contrato la trae, sin ceros que parezcan datos (esc. 8); sin permiso, pantalla de acceso denegado sin importes (esc. 12)
- [ ] Importes con `decimal.js`; la pantalla se refresca al invalidar la caché de TanStack Query tras una entrada (esc. 14 de HDU-005, escalón del sprint 5)

**Non-goals** — No incluye vista consolidada multi-obra más allá del resumen de alertas. No exporta. No oculta la marca de dato simulado en ningún entorno.

---

## Endurecimiento y operación

**No pertenecen a ninguna historia porque sirven a todas.** TKT-057 y TKT-058 son los dos tickets que cubren los requisitos no funcionales del [PRD §9](01-descripcion-producto.md#9-requisitos-no-funcionales): lo que tiene que ser cierto para que las 25 reglas de negocio signifiquen algo. TKT-061 se les une por la misma razón aplicada al contrato del API: lo que tiene que ser cierto para que el borrador signifique algo.

Están separados de la Épica 0 a propósito. La fundación entrega *la capacidad de entregar valor*; estos tres entregan *la capacidad de no perderlo*, y se descubren tarde en casi todos los proyectos porque nadie los pide.

---

### TKT-057 · Endurecimiento de la frontera HTTP

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-006 |

**Qué hace.** Cubre los requisitos de seguridad que TKT-006 declara fuera de su alcance: límite de intentos, protección contra peticiones cruzadas, cabeceras y gestión de secretos.

**Criterios técnicos**

- [ ] Límite de intentos de acceso por origen y bloqueo **temporal** por cuenta tras `N` fallos, con cada intento asentado en `intento_acceso` (`RNF-04`)
- [ ] El bloqueo caduca solo: una cuenta bloqueada para siempre es una denegación de servicio que cualquiera puede provocar
- [ ] Token de doble envío verificado en **todo** método que muta estado, con test de rechazo sin token (`RNF-05`). El rechazo anónimo va a `intento_acceso` y al registro técnico, no a la bitácora (TKT-006)
- [ ] Cabeceras `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options` y `Referrer-Policy` en todas las respuestas (`RNF-05`)
- [ ] La política de contenido admite en `img-src` y `media-src` el origen del almacén de objetos **y ningún otro** (regla 4 de [ADR-016](adr/20261001-almacenamiento-de-objetos.md), `RNF-06`). La validación de los archivos —tamaño, tipo leído de los bytes, nombre generado por el sistema, `Content-Disposition`— es de TKT-059
- [ ] Configuración con `pydantic-settings`: **la aplicación no arranca** si falta un secreto obligatorio, y existe `.env.example` con las claves sin los valores (`RNF-07`)
- [ ] Los nueve requisitos verificables de [stack §6.6](06-stack-tecnologico.md#66-qué-se-comprueba-solo) tienen su test y fallan el pipeline; el de `RNF-06` lo aporta TKT-059

> **Este ticket viaja con TKT-006 o no sirve.** Una autenticación sin límite de intentos no es una autenticación a medias: es una invitación, y además convierte el inicio de sesión —que usa Argon2 a propósito— en el punto más barato de saturar de todo el sistema.

**Non-goals** — No implementa segundo factor, recuperación de contraseña ni inicio de sesión federado: siguen fuera del MVP. No implementa permisos por obra. No valida archivos: es TKT-059.

---

### TKT-061 · El borrador OpenAPI como prueba de contrato

| | |
|---|---|
| **Tipo** | Documentación · **Talla** S · **Depende de** TKT-008, TKT-009 · **Sprint 4**, con cierre en el 6 |

**Qué hace.** Convierte el borrador [`docs/api/openapi.yaml`](api/openapi.yaml) —descrito en la [especificación del API](07-especificacion-api.md)— en una prueba que se ejecuta en cada PR: compara el OpenAPI que FastAPI publica con el borrador para los endpoints de la fase 1 y falla el pipeline si divergen. Es lo que hace del borrador el contrato contra el que el agente genera el backend y el cliente sus tipos, y no un documento que se desactualiza en el primer sprint.

**Criterios técnicos**

- [ ] El borrador pasa la validación de OpenAPI 3.1 en el pipeline, y los ejemplos que trae —el contrato de error de la [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio) entre ellos— se validan contra sus propios esquemas
- [ ] Un test obtiene el esquema que publica la aplicación y lo compara con el borrador, por operación de la fase 1: **ruta y método**, parámetros obligatorios, **códigos de respuesta** —incluidos `401`, `403`, `409` y `422`—, esquema del cuerpo y **forma del contrato de error**
- [ ] **Todo importe es `string`** en los dos esquemas; un importe declarado como número en cualquiera de los dos falla la prueba, aunque coincidan entre sí (regla 1 de `CLAUDE.md`)
- [ ] Una ruta publicada que no está en el borrador también falla: el borrador se actualiza **en el mismo PR** que cambia el comportamiento, que es la regla de documentación del proyecto
- [ ] **Trinquete de pendientes**: el test mantiene la lista explícita de operaciones del borrador aún sin implementar. La lista solo puede encoger —si una operación de la lista ya existe, el test falla hasta que se quite— y **en el sprint 6 tiene que estar vacía**. Así la prueba sirve desde el sprint 4 sin exigir lo que todavía no se ha construido **(asumido: el mecanismo; el objetivo es el del plan)**
- [ ] Las operaciones marcadas `x-sin-exito: true` en el borrador —hoy solo `POST /api/v1/ordenes-compra/{orden_compra_id}/cierre`, que existe para dar el rechazo de HDU-005 esc. 12— **se excluyen de la comparación de respuestas `2xx`**; sus rechazos se comparan como los de cualquier otra
- [ ] Ocupa el trabajo reservado en TKT-009, después de los tests de backend y antes de la generación de tipos del cliente de TKT-008
- [ ] La documentación navegable del API la sirve Scalar desde el esquema publicado, no desde el borrador ([stack §9](06-stack-tecnologico.md#9-documentación)): lo que se lee es lo que corre, y la prueba garantiza que coincide con lo que se especificó

> **Si el borrador y el código divergen, manda el borrador**, y cambiarlo se hace **en el mismo PR** que cambia el código, con su porqué ([stack §5.4](06-stack-tecnologico.md#54-el-contrato-de-api-no-se-replica-a-mano), [especificación del API](07-especificacion-api.md)). TKT-062 señala en la revisión todo PR que toca `openapi.yaml`, porque es el cambio que más consumidores rompe en silencio.

**Non-goals** — No escribe el borrador: ya existe. No cubre los endpoints de la fase 2, que la especificación solo lista. No genera el código del servidor a partir del borrador: FastAPI publica desde el código, y el borrador es la especificación contra la que ese código se comprueba.

---

### TKT-058 · Respaldo, recuperación y observabilidad

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-005, TKT-009, TKT-059 · **Sprint 6** |

**Qué hace.** Deja el sistema en condiciones de ser desplegado de verdad: que se pueda restaurar lo que se pierda y que se pueda saber qué falló.

**Bloqueado por PA-12.** Los objetivos de `RNF-10` —1 hora de pérdida, 8 horas de restauración— siguen **(asumido)**. Fijan el precio de la base gestionada, así que la pregunta tiene que estar respondida **antes de contratarla**, no después. Es lo único de este ticket que depende de alguien ajeno al equipo.

**Criterios técnicos**

- [ ] **PA-12 respondida por Dirección General** y los objetivos de `RNF-10` actualizados con lo que diga, o confirmados
- [ ] PostgreSQL gestionado con **recuperación a un punto en el tiempo**, más volcado lógico diario retenido aparte del proveedor (`RNF-10`)
- [ ] El respaldo cubre también los archivos subidos: bucket con **versionado de objetos** y política de ciclo de vida declarada (`RNF-19`). Una base restaurada cuya bitácora apunta a evidencia inexistente está restaurada a medias
- [ ] **Script de restauración versionado** en el repositorio, que restaura base y objetos sobre un entorno limpio y **verifica el SHA-256 de cada objeto contra el asentado en la bitácora**: un respaldo de archivos sin esa comprobación restaura bytes, no evidencia ([stack §10](06-stack-tecnologico.md#10-infraestructura))
- [ ] **Un ensayo de restauración documentado**, sobre entorno limpio, con el script anterior, el tiempo medido y comparado contra el objetivo acordado (`RNF-11`)
- [ ] La imagen única de Docker —el backend sirviendo los estáticos del frontend— se construye en el pipeline y es la que se restaura en el ensayo: un ensayo con una imagen distinta de la de producción no prueba la de producción
- [ ] Agregación de errores no controlados con Sentry o equivalente autoalojado, consumiendo el identificador de correlación que TKT-005 ya emite (`RNF-14`)
- [ ] El registro técnico **no** escribe en `bitacora` ni al revés: son dos sitios porque son dos preguntas
- [ ] Prueba de rendimiento del semáforo con volumen sembrado que falla el pipeline por encima de 2 s (`RNF-15`). En la fase 1 mide la consulta con las fuentes simuladas de TKT-060; desde el sprint 8 corre contra el adaptador real de TKT-069 ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md))

> **Va en el sprint 6, el último de la fase 1, por una razón y no por comodidad:** dos de sus criterios no se pueden ejecutar antes. No se contrata una base gestionada para un sistema que aún no existe, y la prueba de rendimiento necesita el semáforo con todas sus columnas, que no está completo hasta el sprint 5. Lo que sí podía adelantarse —el registro estructurado— se adelantó a TKT-005.
>
> **Dónde entra la IA, y dónde no.** El script de restauración, el `Dockerfile` y la configuración del pipeline los puede escribir un agente, y pasan por la revisión de TKT-062 y por una persona como cualquier PR. **El ensayo de restauración no**: es un procedimiento con testigo (`RNF-11`), y su valor es precisamente que alguien comprobó con sus ojos que el sistema volvió.

**Non-goals** — No implementa alta disponibilidad: `RNF-12` la descarta expresamente. No monta infraestructura de métricas ni trazado distribuido: hay un proceso. No emite el registro estructurado: eso es TKT-005. No elige el destino de despliegue: se decide aparte, y este ticket solo exige las dos restricciones que ese destino tiene que cumplir.

---

## Fase 2 · Mano de obra y campo

**Fase 2** · HDU-007, HDU-008, HDU-009, la parte diferible de HDU-005 y la captura en campo. Sus tickets son TKT-042 a TKT-053, TKT-055 y TKT-056 —las tres historias de mano de obra—, y TKT-063 a TKT-068, que absorben lo que el antiguo bloque *pendiente de descomponer* enumeraba: el armazón sin conexión (TKT-063), la sincronización idempotente en el servidor (TKT-064), el componente de subida y galería (TKT-065), la evidencia y el expediente (TKT-066, TKT-067) y la recepción diferible (TKT-068).

Los escenarios que cubren son los que llevan la marca **fase 2** en las historias: el 14 de HDU-002, del 15 al 20 de HDU-005, del 18 al 25 de HDU-008 y la parte de nómina del 7 de HDU-006, además de todos los de HDU-007 y HDU-009.

## Lo que no hay que hacer en la fase 2

Seis cosas que ADR-015 y ADR-016 ya decidieron y que conviene no reabrir al implementar:

- **No ampliar la lista de flujos diferibles.** Solo `avance` y `entrada_almacen`. La frontera es `RN-03` y no es negociable desde el backlog: el escenario 14 de HDU-002 existe para que el modo sin conexión no se lea como puerta trasera a esa regla.
- **No evaluar reglas en el cliente.** El saldo cacheado orienta al usuario; no autoriza nada.
- **No resolver conflictos automáticamente.** Los decide una persona.
- **No meter las fotos en la cola de sincronización.** El avance sube sin esperarlas. Treinta megabytes en IndexedDB compiten con una cuota que el navegador desaloja sin avisar.
- **No servir los archivos desde el API.** Las rutas son `def`: cada descarga retendría un hilo del grupo. La URL prefirmada no es una optimización, es la decisión.
- **No interpretar el XML del CFDI.** Se guarda. Conciliarlo contra la orden de compra son reglas de negocio que el PRD no tiene, y que no se inventan desde un ticket.

## Cuatro preguntas al cliente antes de empezar la fase 2

Ninguna bloquea la fase 1, pero las cuatro cambian el diseño de la fase 2. Conviene hacerlas durante el sprint 5 para tener la respuesta al planificar el 7:

| | Pregunta | Por qué importa |
|---|---|---|
| **1** | ¿Cada quien usa su propio dispositivo, o hay uno compartido en obra? | Con dispositivo compartido, la cola atada al último usuario autenticado deja de ser suficiente y hacen falta colas por usuario |
| **2** | ¿Cuánto llega a estar un residente sin señal: unas horas, un día, una semana? | Dimensiona la cola y decide a partir de qué antigüedad la caché deja de mostrarse y pasa a avisar |
| **3** | **`PA-14`** · ¿Un avance se puede validar sin evidencia fotográfica? | Decide si existe una regla de negocio nueva y si la octava regla de ADR-016 se sostiene. Es la única de las cuatro que puede invertir un escenario ya escrito: el 25 de HDU-008, que hoy está **(asumido)** |
| **4** | **`PA-15`** · ¿Cuánto video hace falta, y cuánto tiempo hay que conservarlo? | Fija los límites de `RNF-06`, la resolución a la que se guarda y la política de ciclo de vida del bucket. Mientras no se responda, los límites del [PRD §10](01-descripcion-producto.md#10-supuestos-y-preguntas-abiertas) son supuestos míos |

> **Las preguntas de negocio de la fase 2 ya están respondidas.** `PA-19` —semana del destajo—, `PA-20` —conflicto de modalidad—, `PA-21` —base de pago del destajo y fondo de garantía— y `PA-22` —reglas de nómina— las contestó el cliente el 2026-10-17, y los tickets que dependían de ellas las citan como resueltas. Lo que esas respuestas dejaron sin decir está en los [supuestos asumidos sin bloqueo del PRD §10](01-descripcion-producto.md#10-supuestos-y-preguntas-abiertas) y se marca **(asumido, sin bloqueo)** donde se usa.

## Tickets de HDU-007 · Catálogo de personal y cuadrillas

Historia: [HDU-007](04-historias-usuario.md#hdu-007--catálogo-de-personal-y-cuadrillas) · 5 SP

Es un bloque de catálogo sin reglas duras salvo `RN-13`, pero bloquea a las dos historias que siguen: el avance se captura por cuadrilla y la nómina se calcula por empleado. Las rutas siguen las convenciones de la [especificación de API](07-especificacion-api.md); los nombres finales los fija ese documento.

---

### TKT-042 · Esquema y migraciones del módulo personal

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-003, TKT-011 |

**Qué hace.** Crea las tablas del catálogo de personal con las restricciones que protegen los créditos y siembra el catálogo de roles de oficio del cliente, que nace aquí y no en TKT-010 porque su tabla no existe antes.

**Criterios técnicos**

- [ ] Tablas `rol_oficio`, `empleado`, `cuadrilla` —con `activo`—, `cuadrilla_empleado` y `credito_empleado` según [modelo de datos §8](03-modelo-datos.md#8-personal-y-nómina)
- [ ] `CHECK (saldo >= 0)` sobre `credito_empleado` — invariante 3 — y `CHECK (estado <> 'LIQUIDADO' OR saldo = 0)` — invariante 4 —, cada uno con un test que lo viola **con el rol de aplicación** y verifica que falla en el motor. El escenario 11 de HDU-009 descansa en el primero
- [ ] `CHECK (salario_semanal > 0)` y `CHECK (tarifa_hora_extra >= 0)` — invariante 8 —, respaldo de motor del escenario 5 de HDU-007
- [ ] `empleado.rol_oficio_id` y `cuadrilla.obra_id` con `NOT NULL`: el escenario 4 de HDU-007 se rechaza en la API, pero la columna no admite el hueco aunque alguien escriba por otra vía
- [ ] `CHECK (descuento_semanal > 0 AND descuento_semanal <= monto_total)` sobre `credito_empleado` — invariante 34 —, respaldo del escenario 10
- [ ] Restricción de exclusión sobre `cuadrilla_empleado` que impide dos asignaciones del mismo empleado con rangos `[desde, hasta]` solapados, con `btree_gist` habilitada en la migración, y `CHECK (hasta IS NULL OR hasta >= desde)` — invariante 33, escenario 7 de HDU-007 —
- [ ] Los seis roles de oficio del cliente sembrados en la migración —`PASTERO`, `TABLAROQUERO`, `AYUDANTE`, `OFICIAL`, `PINTOR`, `LIMPIEZA`—, de forma idempotente: aplicar la migración sobre una base que ya los tiene no los duplica
- [ ] Migración reversible; tests construidos con `alembic upgrade head` y conectados con el rol de aplicación

> **El solapamiento de cuadrillas se cierra en el motor y no solo en el caso de uso** porque de esa tabla depende a qué cuadrilla se imputa cada jornada (TKT-055) y, por tanto, qué modalidad de pago reclama (`RN-22`). Dos asignaciones simultáneas harían que la misma jornada perteneciera a dos cuadrillas, y la exclusividad de modalidad dejaría de tener un sujeto único.

**Non-goals** — No crea `jornada` ni ninguna tabla de nómina (TKT-049). No crea `modalidad_pago_semana` (TKT-053). No implementa ningún caso de uso.

---

### TKT-043 · Alta, cambios y baja de empleados

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-042, TKT-006, TKT-007, TKT-008 |

**Qué hace.** CRUD de empleados con su rol de oficio, baja lógica protegida por el historial y decisión explícita sobre los créditos pendientes al dar de baja, con su pantalla de catálogo.

**Criterios técnicos**

- [ ] `GET /api/v1/roles-oficio` devuelve solo los roles activos del catálogo — HDU-007 esc. 2
- [ ] `POST /api/v1/empleados` con nombre, rol de oficio, salario semanal, tarifa de hora extra e indicador de cuenta bancaria; el empleado queda activo y aparece en la consulta de asignables a cuadrilla — esc. 3
- [ ] Sin rol de oficio responde `422` señalando el campo — esc. 4 —; salario de cero o negativo responde `422` — esc. 5 —. En ambos casos un test cuenta filas antes y después y verifica que no se creó ninguna
- [ ] `PATCH /api/v1/empleados/{id}` para datos y salario. Cambiar el salario no reescribe nada calculado: la nómina copia el salario en su renglón (HDU-009 esc. 17, TKT-050)
- [ ] `DELETE /api/v1/empleados/{id}` sobre un empleado con historial —asignaciones, jornadas, renglones de nómina o avances— responde `409` `CONFLICTO` —con su `codigo`, que se añade al catálogo del borrador en el mismo PR (TKT-005)— y la acción de dar de baja; sin historial, se permite. Un test verifica que ningún empleado con historial admite borrado físico (DoD de HDU-007) — esc. 12
- [ ] `POST /api/v1/empleados/{id}/baja` con motivo: el empleado pasa a inactivo, su asignación vigente se cierra con la fecha de baja, deja de precargarse en las semanas posteriores y conserva todo su historial — esc. 12
- [ ] Dar de baja a un empleado con un crédito `ACTIVO` y saldo mayor que cero responde `409` con el saldo y su importe en el detalle, y las acciones `CONDONAR` y `MANTENER_SALDO`; la petición que repite la baja con la decisión y su motivo la ejecuta y la asienta en la bitácora — esc. 13. Condonar o no es la **decisión explícita** de quien da de baja, no un supuesto (`PA-22`, resuelta el 2026-10-17). *Condonar* deja el crédito en `LIQUIDADO` con saldo cero; *mantener como saldo por cobrar* lo deja en `SUSPENDIDO` con su saldo. El modelo no tiene un estado propio para la condonación: si el cliente necesita distinguirla en un reporte, hace falta un estado nuevo y hay que preguntarlo
- [ ] Mutaciones reservadas al rol `ADMINISTRACION` **(asumido)**; cualquier otro rol recibe `403` y el intento se asienta como `DENEGAR`
- [ ] Alta, baja, cambio de salario y decisión sobre crédito escriben en la bitácora en la misma transacción
- [ ] Interfaz con el componente de formulario de catálogo de TKT-008: el botón + abre el formulario con el foco en el primer campo — esc. 1 — y el rol se elige de un desplegable alimentado por la consulta de roles — esc. 2
- [ ] Rutas añadidas al borrador `docs/api/openapi.yaml`, de modo que la prueba de contrato de TKT-061 las cubra

**Non-goals** — No modela expediente laboral, prestaciones, vacaciones ni antigüedad. No gestiona altas ante el IMSS. No asigna cuadrillas (TKT-044) ni registra créditos (TKT-045).

---

### TKT-044 · Cuadrillas, encargado y asignación con historial

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-043, TKT-012 |

**Qué hace.** Alta de cuadrillas por obra con su encargado, asignación temporal de empleados y cambio de cuadrilla que conserva la asignación anterior. Publica la consulta que `avance` y la nómina necesitan: a qué cuadrilla pertenecía un empleado en una fecha.

**Criterios técnicos**

- [ ] `POST /api/v1/cuadrillas` con obra, nombre y encargado; el encargado tiene que ser un empleado activo. La existencia de la obra se comprueba por la interfaz publicada de `presupuesto`, nunca leyendo `obra` — esc. 6
- [ ] `GET /api/v1/cuadrillas?obra_id=…&activa=true` devuelve las cuadrillas activas de una obra con su encargado: es la que alimenta el selector de HDU-008 esc. 10 y la lista de receptores posibles de TKT-051
- [ ] `POST /api/v1/cuadrillas/{id}/asignaciones` con empleado y fecha de inicio — esc. 7. Si el empleado ya está en otra cuadrilla en esa fecha responde `409` `CONFLICTO` nombrando la cuadrilla vigente; la violación de la restricción de exclusión de TKT-042 —invariante 33— se traduce al mismo contrato, nunca a un `500`
- [ ] `POST /api/v1/empleados/{id}/cambio-cuadrilla` con cuadrilla destino, fecha y motivo: cierra la asignación anterior con `hasta` igual al día previo y abre la nueva, en una sola transacción — esc. 8
- [ ] Interfaz de aplicación publicada con `cuadrilla_vigente(empleado_id, fecha)`, `cuadrillas_activas(obra_id)` y `pertenece_a_obra(cuadrilla_id, obra_id)`. Un test verifica que, tras un cambio, la consulta para una fecha anterior devuelve la cuadrilla antigua: es lo que permite que la nómina ya calculada siga mostrando la cuadrilla que correspondía — esc. 8
- [ ] `POST /api/v1/cuadrillas/{id}/baja` pone `cuadrilla.activo = false`; con empleados activos asignados responde `409` `CONFLICTO` listándolos y pidiendo reasignarlos — esc. 14
- [ ] Bitácora en alta, asignación, cambio y baja
- [ ] Interfaz de catálogo de cuadrillas y de asignación, con el historial de asignaciones del empleado visible

**Non-goals** — No asigna una cuadrilla a varias obras a la vez. No decide la modalidad de pago de la cuadrilla: la reclama el primer pago de la semana (TKT-053).

---

### TKT-045 · Créditos activos de empleado

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-043 |

**Qué hace.** Registro de créditos de Infonavit y préstamos de la empresa, con su suspensión y reactivación. Deja el saldo listo para que la nómina lo amortice y garantiza que ninguna otra vía lo toque.

**Criterios técnicos**

- [ ] `POST /api/v1/empleados/{id}/creditos` con tipo, monto total y descuento semanal: el crédito nace `ACTIVO` con saldo igual al monto — esc. 9
- [ ] Un descuento semanal mayor que el monto total responde `422` con un mensaje que explica que el descuento no puede exceder la deuda; la restricción de motor de TKT-042 respalda el rechazo — esc. 10
- [ ] `POST /api/v1/creditos/{id}/suspension` con motivo pasa a `SUSPENDIDO` y conserva el saldo; `POST /api/v1/creditos/{id}/reactivacion` con motivo lo devuelve a `ACTIVO` — esc. 11. Sin motivo, `422`; desde `LIQUIDADO`, `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`
- [ ] Interfaz publicada `creditos_descontables(empleado_id)` que devuelve solo los `ACTIVO`; un test verifica que un crédito suspendido no aparece — es lo que hace que "deje de descontarse en las nóminas siguientes" (esc. 11) sin que la nómina tenga que saber de estados
- [ ] **Ninguna ruta acepta `saldo` en el cuerpo.** El saldo solo cambia por un descuento de nómina (TKT-050) o por la decisión de baja de TKT-043; un test recorre el esquema OpenAPI publicado y falla si algún cuerpo de petición de este módulo lo expone
- [ ] Bitácora en alta, suspensión y reactivación (`RN-13`)
- [ ] Interfaz de créditos dentro de la ficha del empleado, con saldo, estado y el componente de captura de motivo de TKT-008

> **El invariante `saldo >= 0` se reparte entre dos historias** (HDU-007 lo crea, HDU-009 lo amortiza). Que solo dos casos de uso puedan mover el saldo es lo que hace que ese reparto sea auditable: cualquier otro cambio de saldo es, por construcción, un defecto.

**Non-goals** — No calcula descuentos ni transiciones a `LIQUIDADO`: eso es TKT-050. No calcula intereses ni plazos.

---

## Tickets de HDU-008 · Avance de destajo

Historia: [HDU-008](04-historias-usuario.md#hdu-008--avance-de-destajo-medido-y-validado) · 12 SP

Los escenarios 1 a 17 se cubren en TKT-046, TKT-047, TKT-048 y TKT-053. Los escenarios 18 a 25 —captura sin conexión y evidencia— se reparten con los tickets de [captura en campo](#captura-en-campo--sin-conexión-y-evidencia), que dicen cuál de ellos es dueño del test de cada uno.

---

### TKT-046 · Esquema del módulo avance y etapas de destajo por tipo de partida

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-011, TKT-042 |

**Qué hace.** Crea las tablas del módulo `avance` con las dos garantías de motor que lo sostienen —un avance pagado está validado y el alcance no se duplica— y expone la configuración de etapas de destajo por obra y tipo de partida (**PA-08**).

**Criterios técnicos**

- [ ] Tablas `etapa_destajo`, `alcance_destajo`, `avance`, `pago_destajo` y `pago_destajo_avance` según [modelo de datos §7](03-modelo-datos.md#7-avance-y-destajo)
- [ ] `etapa_destajo.tipo_partida_id NOT NULL` y `UNIQUE (obra_id, tipo_partida_id, clave)` — invariante 32 —, de modo que `METAL · MUROS` y `METAL · PLAFONES Y CAJILLOS` son dos filas con precios propios — esc. 1
- [ ] `CHECK (precio_venta_m2 >= 0 AND precio_destajo_m2 >= 0)`, `CHECK (m2_real >= 0)` y `CHECK (m2_contrato >= 0)` — invariante 8
- [ ] `UNIQUE (area_id, etapa_destajo_id)` sobre `alcance_destajo` — invariante 22 —, con test que precarga dos veces y verifica que la segunda falla en el motor
- [ ] `avance.obra_id NOT NULL` — invariante 1 — y `UNIQUE (id, estado)` sobre `avance` para sostener la clave compuesta
- [ ] `pago_destajo_avance (avance_id, avance_estado)` con clave foránea compuesta contra `avance (id, estado)`, `CHECK (avance_estado = 'VALIDADO')` y `ON UPDATE RESTRICT` — invariante 11. Un test inserta un avance `CAPTURADO` en un pago y verifica que falla en el motor; otro verifica que un avance ya liquidado no puede salir de `VALIDADO`
- [ ] Índice único parcial `(avance_id) WHERE vigente` sobre `pago_destajo_avance` — invariante 35 —: una medición se liquida en un solo pago vigente, y cancelar el pago pone `vigente = false` y la libera **sin borrar la fila**. La fila puente lleva su `importe` —el bruto atribuible a esa medición—, que es lo que suma el ejercido de destajo (TKT-069)
- [ ] `pago_destajo.estado` con `CANCELADO`, más `motivo_cancelacion`, `cancelado_por_id` y `cancelado_en`, exigidos juntos — invariante 36 —
- [ ] `UNIQUE (area_id, etapa_destajo_id, cuadrilla_id, semana)` sobre `avance` — invariante 31 —, respaldo de motor de los escenarios 12 y 19: sin ella, dos dispositivos que sincronizan a la vez pasan los dos la comprobación del caso de uso
- [ ] `avance.fecha_medicion DATE NOT NULL` y `semana`, el **jueves de corte** de la semana de destajo de **jueves a miércoles** que la contiene (`PA-19`, resuelta el 2026-10-17): `CHECK` de jueves en `avance` y `pago_destajo` y, en `avance`, `CHECK (semana - fecha_medicion BETWEEN 1 AND 7)` — invariante 37 —. Una medición hecha en jueves pertenece a la semana que empieza ese día, y su corte es el jueves siguiente; un test lo verifica con el jueves y con el miércoles
- [ ] `pago_destajo.fondo_garantia_pct` y `pago_destajo.fondo_garantia_importe NUMERIC(18,4)`, el 5 % retenido, en paralelo con `retencion_importe` (`PA-21`, resuelta el 2026-10-17)
- [ ] `avance.capturado_en TIMESTAMPTZ`, distinta de la columna de auditoría `creado_en`: la primera es cuándo se midió en el dispositivo, la segunda cuándo llegó al servidor ([ADR-015](adr/20260919-captura-diferida-sin-conexion.md))
- [ ] Índices de [§15](03-modelo-datos.md#índices-que-la-sostienen) para `avance`, `alcance_destajo` y `pago_destajo_avance`
- [ ] `GET` y `POST /api/v1/obras/{obra_id}/etapas-destajo` con clave, tipo de partida, precio de venta y precio de destajo por m², capturados por separado — esc. 1. Sin tipo de partida responde `422` con el mensaje de que el costo de esa etapa no podría imputarse en el tablero — esc. 2
- [ ] `PATCH /api/v1/etapas-destajo/{id}` para precios; un test verifica que cambiarlo no altera los pagos ya generados, cuyo precio quedó congelado en `pago_destajo_avance.precio_destajo_m2`
- [ ] Configuración de etapas reservada al rol `DIRECTOR_PROYECTOS` **(asumido)**; bitácora en alta y cambio de precio

**Non-goals** — No precarga el alcance ni captura avance (TKT-047). **No crea `descuento_destajo` ni la tabla `fondo_garantia`**: los descuentos ad-hoc y la liberación del fondo (`RN-12`) son v1.1; la columna del importe retenido en `pago_destajo` sí es de este ticket. No fija ningún precio ni porcentaje en el código.

---

### TKT-047 · Alcance de destajo, medición en dos pasos y pago con retención

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** L · **Depende de** TKT-046, TKT-017, TKT-044, TKT-026, TKT-053 · **no se fusiona sin** el [adaptador real](#sustitución-del-adaptador-simulado) |

**Qué hace.** Precarga el alcance de destajo desde la línea base congelada, implementa la medición del residente y la validación del Director de Proyectos con su máquina de estados, y calcula el pago de destajo con la retención de la obra.

**Criterios técnicos**

*Alcance*

- [ ] `POST /api/v1/obras/{obra_id}/alcances-destajo/precarga` con un tipo de partida: crea una fila por área y etapa con los m² de contrato, sumando los conceptos en `M2` de las partidas de ese tipo en esa área. Lee la línea base por la interfaz publicada de `presupuesto`, nunca sus tablas — esc. 15
- [ ] Sin línea base congelada responde `409` `CONFLICTO` `SIN_LINEA_BASE_CONGELADA` con la acción de ir a congelarla
- [ ] La respuesta informa cuántos conceptos quedaron fuera por venir en `ML` o `PZA` — esc. 15
- [ ] Un test verifica que una partida con tres etapas aporta el triple de sus m² de catálogo (DoD de HDU-008)
- [ ] Repetir la precarga responde `409` `CONFLICTO`: el invariante 22 se traduce al contrato de error
- [ ] `POST /api/v1/alcances-destajo/{id}/correccion` con el valor nuevo y motivo, reservada a `DIRECTOR_PROYECTOS`: registra autor, fecha y motivo y asienta en la bitácora el valor anterior y el nuevo — esc. 16. Sin motivo, `422`; con otro rol, `403` — esc. 17
- [ ] Un test verifica que corregir el alcance **no** altera el `m2_contrato` de las mediciones ya capturadas (DoD de HDU-008)

*Medición y validación*

- [ ] `POST /api/v1/avances` reservado a `RESIDENTE`, con área, etapa, cuadrilla, fecha de medición y **únicamente** `m2_real`. El caso de uso copia `m2_contrato` del alcance en la misma transacción y deja el avance `CAPTURADO` con su autor; no genera pago — esc. 3
- [ ] Un cuerpo que incluya `m2_contrato` responde `403` con el mensaje de que el alcance lo corrige el Director de Proyectos; el alcance conserva su valor — esc. 17. No se ignora en silencio: quien lo intenta tiene que saber que no surtió efecto
- [ ] `semana` la deriva el servidor de la fecha de medición: `fecha_medicion` más los días hasta el jueves siguiente, el jueves de corte de la semana de destajo de jueves a miércoles (`PA-19`, resuelta el 2026-10-17), y el invariante 37 lo respalda
- [ ] Etapa sin configurar o área sin alcance para esa etapa responde `409` `CONFLICTO` con la acción de configurarla — esc. 9
- [ ] Cuadrilla que no pertenece a la obra responde `422`, comprobado por la interfaz de TKT-044 — esc. 10
- [ ] Duplicado de área, etapa, cuadrilla y semana responde `409` `CONFLICTO` que identifica el avance existente con su autor y sus m², y la acción de **pedir su rechazo al Director de Proyectos**: no hay transición `CAPTURADO → CAPTURADO`, así que *corregir el existente* no es una salida — esc. 12. La violación del invariante 31 se traduce al mismo contrato
- [ ] Con las cifras reales de `DESTAJO 27.08.26`: 81.87 m² de contrato y 83.82 reales se aceptan sin bloqueo y registran +1.95 m² de desviación de volumen — esc. 8
- [ ] `POST /api/v1/avances/{id}/validacion` reservada a `DIRECTOR_PROYECTOS`, que pasa a `VALIDADO` con validador y fecha — esc. 4. Validar una medición propia responde `403` y la deja en `CAPTURADO`, usando **la misma regla de dominio** que TKT-026 —"nadie resuelve lo suyo"—, no una copia — esc. 7
- [ ] `POST /api/v1/avances/{id}/rechazo` con motivo obligatorio pasa a `RECHAZADO`; `POST /api/v1/avances/{id}/correccion` del residente con el `m2_real` nuevo la devuelve a `CAPTURADO`. La bitácora conserva la medición rechazada, su motivo y el valor anterior — esc. 5
- [ ] Toda transición fuera de la máquina de estados de [§14](03-modelo-datos.md#avance) responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`, con un test por transición prohibida

*Pago*

- [ ] `POST /api/v1/pagos-destajo` con obra, cuadrilla, semana y las mediciones a liquidar. Una medición no `VALIDADO` responde `409` con regla `RN-10`, identificando cuáles no lo están, y no crea el pago — esc. 6. El invariante 11 respalda el rechazo en el motor
- [ ] Un pago liquida **solo mediciones de su misma semana**: una medición de otra semana responde `409` `CONFLICTO` `MEDICION_DE_OTRA_SEMANA`, código que se añade al catálogo del borrador en el mismo PR (TKT-005), identificándola, y no crea el pago **(asumido, sin bloqueo)**
- [ ] Cada fila puente guarda `importe = m2_liquidados × precio_destajo_m2`, con el precio congelado, y el importe bruto del pago es la suma de esas filas. **`m2_liquidados` es el `m2_real` de la medición validada** (`PA-21`, resuelta el 2026-10-17)
- [ ] Retención = bruto × `obra.retencion_destajo_pct` y **fondo de garantía = bruto × `obra.fondo_garantia_pct`**, los dos leídos de la obra por la interfaz de `presupuesto` (**PA-02**, `RN-11`) y guardados en `pago_destajo.retencion` y `pago_destajo.fondo_garantia`; neto = bruto − retención − fondo. El fondo se retiene **en cada pago desde la fase 2** (`PA-21`, resuelta el 2026-10-17), y que su base sea el bruto, igual que la retención, es **(asumido, sin bloqueo)**. Con 81.87 m² reales validados a $80, 15 % y 5 %: bruto `6549.6000`, retención `982.4400`, fondo de garantía `327.4800`, neto `5239.6800` — esc. 11. Un test cambia cada porcentaje de la obra y verifica que cambia el resultado (DoD)
- [ ] Antes de persistir, reclama la modalidad `DESTAJO` por la interfaz publicada de `personal` (TKT-053) **en la misma transacción**; si la cuadrilla ya tiene nómina esa semana, `409` con regla `RN-22` — esc. 14
- [ ] `POST /api/v1/pagos-destajo/{id}/cancelacion` con motivo, solo desde `CALCULADO`: pasa a `CANCELADO` con autor y fecha —invariante 36—, pone `vigente = false` en sus filas puente —libera las mediciones sin borrar filas—, libera la reclamación de modalidad y sale del ejercido de destajo. Es la ruta a la que apunta la acción de cancelar del contrato de `RN-22` (HDU-009 esc. 19)
- [ ] Toda operación escribe en la bitácora en la misma transacción

> **Este ticket no se fusiona antes que el término de destajo del consumido.** Desde el primer pago real, `RN-03` tiene que restarlo del disponible del tipo de partida: un `pago_destajo` que existe y no consume es exactamente la cifra parcial que el producto existe para impedir. Por eso depende del [adaptador real](#sustitución-del-adaptador-simulado) para fusionarse, aunque no para desarrollarse.
>
> **Si la talla L no cabe en el sprint, la costura está entre el alcance y lo demás.** Precarga y corrección del alcance van juntas y no necesitan medición; medición, validación y pago van juntas porque el pago no existe sin validación. Partir por otro sitio deja una máquina de estados a medias.

**Non-goals** — No libera el fondo de garantía retenido (`RN-12`, v1.1). No implementa `FuenteEjercido` para el destajo: es TKT-069, con el que viaja. No aplica descuentos ad-hoc. No genera estimaciones de cobro al cliente. No registra el pago efectivo: lo calcula. **No evalúa `RN-03` al generar el pago**: la regla bloquea requisiciones, y un pago de destajo consume la bolsa sin bloquearse; convertirlo en bloqueo sería una regla nueva. No deja que quien mide fije el número contra el que se le mide.

---

### TKT-048 · Interfaz de captura en campo, validación y desviación de volumen

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** L · **Depende de** TKT-047, TKT-063, TKT-064, TKT-065, TKT-066, TKT-008 |

**Qué hace.** La pantalla del residente para medir de pie en obra, con o sin señal, y adjuntar sus fotos; la del Director de Proyectos para validar —viendo la evidencia— y corregir el alcance desde oficina, y el reporte de desviación de volumen por obra, nivel y cuadrilla (F4.7). **Pasó de M a L** al recibir de TKT-067 los adjuntos de la medición.

**Criterios técnicos**

- [ ] Pantalla de captura diseñada para teléfono: usable a 360 px de ancho con una mano, sin desplazamiento horizontal, verificada en Playwright con ventana móvil
- [ ] Los m² de contrato se muestran en solo lectura junto al campo de m² reales; no existe control que permita editarlos — esc. 3 y esc. 17
- [ ] El selector de cuadrillas ofrece solo las activas de la obra — esc. 10
- [ ] La captura muestra a qué semana de destajo —de jueves a miércoles, por su jueves de corte— pertenece la fecha de medición; el valor que manda es el que deriva el servidor (TKT-047)
- [ ] La pantalla de validación muestra los m² **reales**, que son los que se pagan (`PA-21`, resuelta el 2026-10-17), junto a los de contrato y su desviación
- [ ] **Diferible sin conexión** sobre TKT-063: el alcance, las etapas y las cuadrillas de la obra quedan en la caché persistida al abrir la obra con señal, y la captura se completa sin red. Un test de Playwright corta la red, captura, verifica que el elemento quedó `PENDIENTE` en la cola y que no salió ninguna petición — esc. 18
- [ ] La captura escribe **siempre** por la cola, haya señal o no, de modo que hay un solo camino de escritura (TKT-063)
- [ ] Un elemento devuelto como duplicado queda `EN_CONFLICTO` con el contrato de error a la vista —el avance existente, su autor y sus m²— y las salidas de **pedir su rechazo al Director de Proyectos** o descartar el propio; la cola se detiene ahí. **Dueño del test de HDU-008 esc. 19**; TKT-064 aporta el lado servidor
- [ ] Una cola que no sube por rol retirado muestra el motivo y conserva los elementos. **Dueño del test de HDU-008 esc. 20**; TKT-064 aporta el lado servidor
- [ ] La pantalla muestra de cuándo son el alcance y las cuadrillas que está usando (regla 7 de ADR-015)
- [ ] **La validación no es diferible**: sin conexión, validar, rechazar y corregir el alcance aparecen deshabilitados con la explicación de que exigen servidor, y nada de eso se encola
- [ ] Pantalla de validación con mediciones `CAPTURADO` por obra y semana, rechazo con el componente de motivo de TKT-008 y corrección del alcance con motivo
- [ ] `GET /api/v1/obras/{obra_id}/desviacion-volumen?agrupar_por=nivel|cuadrilla` y su vista: suma de `m2_real − m2_contrato` sobre avances validados; un test reproduce los +1.95 m² del departamento 212 — esc. 8
- [ ] Importes y cantidades con `decimal.js`

*Adjuntos de la medición* —vinieron de TKT-067, que se queda con la remisión y el expediente—

- [ ] En la captura, el componente de TKT-065 adjunta fotos a una medición **ya sincronizada**; mientras está en la cola, el botón aparece deshabilitado con la explicación — HDU-008 esc. 21 y 22
- [ ] La lista de mediciones marca las que aún no tienen evidencia. Es una marca de pantalla, no una regla
- [ ] En la validación, el Director de Proyectos ve la galería de la medición; sin fotos, un aviso lo dice **y no impide validar** — HDU-008 esc. 25 **(asumido, `PA-14`)**
- [ ] Anular una foto de la medición con el componente de captura de motivo de TKT-008; la decisión es del servidor — HDU-008 esc. 24
- [ ] Los rechazos de tamaño y tipo se muestran con el contrato de error, no con un mensaje genérico — HDU-008 esc. 23

**Non-goals** — No valida sin conexión. No adjunta la remisión ni construye el expediente: son TKT-067. No implementa una cola propia: usa la de TKT-063. No genera estimaciones de cobro.

---

## Tickets de HDU-009 · Nómina semanal

Historia: [HDU-009](04-historias-usuario.md#hdu-009--nómina-semanal) · 13 SP

> **La costura sigue declarada:** *registro de jornada diaria* —TKT-049, TKT-055 y TKT-056, 5 SP— y *cálculo de nómina con créditos y pagos agrupados* —TKT-050, TKT-051 y TKT-052, 8 SP—. **Una precisión que la costura no decía:** `imputacion_nomina_obra` reparte el **neto** del renglón, y el neto lo produce el cálculo. La primera mitad deja los días por obra derivados y la función de reparto probada, pero el importe de nómina por obra solo llega al semáforo con la segunda. Entre una y otra, y una vez retirado el adaptador simulado, la fuente de nómina se muestra como `SIN_DATOS`, nunca como un cero real.

---

### TKT-049 · Esquema de jornada y nómina

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-042, TKT-011 |

**Qué hace.** Crea las tablas de jornada, nómina, descuentos y pagos con las cuatro restricciones que hacen que la nómina cuadre por construcción.

**Criterios técnicos**

- [ ] Tablas `jornada`, `nomina_semana`, `nomina_renglon`, `imputacion_nomina_obra`, `descuento_nomina`, `pago_nomina` y `pago_nomina_detalle` según [modelo de datos §8](03-modelo-datos.md#8-personal-y-nómina)
- [ ] `UNIQUE (empleado_id, fecha)` sobre `jornada` — invariante 16 —, con test
- [ ] `CHECK (fecha_corte = fecha_inicio + 6 AND EXTRACT(DOW FROM fecha_corte) = 4)` — invariante 18 —, con test que intenta un corte en martes; `UNIQUE (fecha_corte)` sobre `nomina_semana`
- [ ] Restricción diferida de que el detalle de un pago suma su importe — invariante 7 —, con test que confirma $11,000 contra un desglose de $10,500 y verifica que falla al confirmar la transacción
- [ ] **Restricción diferida de que `imputacion_nomina_obra` suma el neto del renglón** — invariante 17 —, con test que reparte de más y verifica el fallo: sin ella el reparto puede cuadrar por obra y no cuadrar con lo pagado
- [ ] `jornada.obra_id NOT NULL` — invariante 1 —, `CHECK (fraccion_dia > 0 AND fraccion_dia <= 1)` y `CHECK (horas_extra >= 0)`
- [ ] `jornada.cuadrilla_id` se guarda copiado del momento: es lo que mantiene la cuadrilla histórica de HDU-007 esc. 8
- [ ] `CHECK (saldo_posterior >= 0)` sobre `descuento_nomina`
- [ ] El parámetro `dias_semana_laboral`, con valor 6, en el sitio que declara el [modelo de datos §8](03-modelo-datos.md#8-personal-y-nómina) y **nunca como constante en el código** (`PA-22`, resuelta el 2026-10-17): es el divisor del salario semanal y el máximo de días de una semana
- [ ] Índices `(empleado_id, fecha)` único, `(obra_id, fecha)` sobre `jornada` e `(obra_id)` sobre `imputacion_nomina_obra` ([§15](03-modelo-datos.md#índices-que-la-sostienen))

**Non-goals** — No toca el esquema de personal (TKT-042) ni crea `modalidad_pago_semana` (TKT-053). No implementa ningún caso de uso.

---

### TKT-055 · Apertura de semana y registro de jornada diaria

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-049, TKT-044, TKT-012 |

**Qué hace.** Abre la semana de nómina de la empresa con corte en jueves y registra cada día trabajado por empleado y obra (**PA-04**, `RN-23`), que es de donde se derivan los días de la nómina y su reparto entre obras.

**Criterios técnicos**

- [ ] `POST /api/v1/semanas-nomina` con la fecha de corte: si es jueves, fija el inicio en el viernes anterior y deja la semana `ABIERTA`, sin obra — la semana es de la empresa — esc. 1. Si no es jueves, `422` con regla `RN-23` y el recordatorio de corte el jueves y pago el sábado — esc. 2. El invariante 18 respalda el rechazo
- [ ] Una segunda semana con la misma fecha de corte responde `409` `CONFLICTO`
- [ ] `POST /api/v1/jornadas` con empleado, fecha, obra, fracción de día y horas extra; acepta medias jornadas — esc. 3. La cuadrilla la pone el caso de uso con `cuadrilla_vigente(empleado_id, fecha)` de TKT-044, no la captura el usuario
- [ ] Jornada sin obra responde `422` con regla `RN-02` y el mensaje de que el costo de ese día no podría imputarse a nadie — esc. 5
- [ ] Segunda jornada del mismo empleado el mismo día responde `409` `CONFLICTO` con la acción de corregir la existente; la violación del invariante 16 por dos peticiones simultáneas se traduce al mismo contrato, con un test de dos transacciones reales — esc. 4
- [ ] Una jornada cuya fecha no cae en una semana `ABIERTA` responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`
- [ ] La suma de fracciones del empleado en la semana no puede exceder los días de la semana laboral: el exceso responde `422` señalando la jornada y el máximo admitido — esc. 12. El máximo es el parámetro `dias_semana_laboral` de TKT-049, **6 días** (`PA-22`, resuelta el 2026-10-17)
- [ ] **Los integrantes de una cuadrilla que cobra por destajo también registran jornada** **(asumido, sin bloqueo)**: `RN-23` exige saber cuándo y dónde trabajó cada empleado. La jornada se captura igual; lo que no genera es renglón de nómina en una semana en que su cuadrilla cobra destajo (TKT-050)
- [ ] Empleado inactivo u obra inexistente responden `422`; la obra se comprueba por la interfaz de `presupuesto`
- [ ] `PATCH /api/v1/jornadas/{id}` mientras la semana está `ABIERTA`; `GET /api/v1/jornadas` filtrable por semana, empleado y obra
- [ ] Reservado a `ADMINISTRACION` **(asumido)**. **No es diferible**: la jornada se captura en oficina y exige conexión (regla 1 de ADR-015)
- [ ] Bitácora en apertura, alta y corrección

**Non-goals** — No registra horarios de entrada y salida ni sustituye el control de asistencia. No calcula nómina (TKT-050). No reparte costo (TKT-056).

---

### TKT-056 · Imputación del costo de nómina entre obras

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-055, TKT-069 |

**Qué hace.** Reparte el neto de cada empleado entre las obras en proporción a los días que trabajó en cada una, como dato derivado de las jornadas y no como estimación capturada, y **lleva la nómina al semáforo**: conecta su lectura al adaptador real de TKT-069, que hasta aquí la declaraba `SIN_DATOS`.

**Criterios técnicos**

- [ ] Función pura en `dominio/` que recibe las fracciones de día por obra y el neto, y devuelve la imputación por obra. `RN-23` en su docstring
- [ ] El reparto suma **exactamente** el neto a cuatro decimales: el residuo de redondeo se asigna a la obra con más días, y a igualdad, a la de menor identificador **(asumido: política de redondeo no declarada; cualquier otra que sume exacto sirve)**
- [ ] Con $7,000 de neto, tres días en Union Square y dos en ENITI: `4200.0000` y `2800.0000`, en un único renglón con cinco días — esc. 7
- [ ] Persistencia de la imputación **en la misma transacción que el renglón**, invocada por el cálculo de TKT-050; el invariante 17 la verifica al confirmar. Hasta que TKT-050 exista, los tests la ejercitan sobre un renglón insertado como dato de prueba
- [ ] Interfaz publicada `nomina_imputada(obra_id)` que suma solo las semanas `CERRADA` o `PAGADA`, como la CTE `nomina_obra` de [§15](03-modelo-datos.md#la-nómina-va-aparte): es la que consume el [adaptador real](#sustitución-del-adaptador-simulado)
- [ ] Ninguna ruta permite capturar una imputación a mano
- [ ] **La lectura de `nomina_imputada(obra_id)` entra en el adaptador real** del puerto de ADR-017 (TKT-069), y la fuente `NOMINA` pasa de `SIN_DATOS` a `REAL` en cuanto la obra tiene una semana `CERRADA` o `PAGADA` con imputación; antes, sigue `SIN_DATOS`
- [ ] Dueño de los tests de HDU-009 esc. 18 —el costo de nómina llega al semáforo como fila de obra, distinguible de materiales y destajo— y de la parte de HDU-009 esc. 7 que dice que cada obra ve en su semáforo solo su parte
- [ ] **La nómina no entra en el consumido de `RN-03`** ([§15](03-modelo-datos.md#la-nómina-va-aparte), **PA-10**): un test cierra una semana con nómina en la obra y verifica que el disponible no cambia

**Non-goals** — No reparte por tipo de partida: la nómina llega solo a obra (**PA-10**). No calcula el neto.

---

### TKT-050 · Cálculo de la nómina semanal

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-055, TKT-056, TKT-045, TKT-053 |

**Qué hace.** Calcula la nómina de la semana en `dominio/`: días derivados de las jornadas, horas extra, amortización de créditos con liquidación automática y protección contra neto negativo. Reclama la modalidad de pago antes de escribir.

**Criterios técnicos**

- [ ] `POST /api/v1/semanas-nomina/{id}/calculo` sobre una semana `ABIERTA`: los días de cada empleado se **derivan** de sus jornadas, no se capturan — esc. 6
- [ ] Importe de nómina = salario semanal × días ÷ `dias_semana_laboral` —6 días, el parámetro de TKT-049 (`PA-22`, resuelta el 2026-10-17)—; importe extra = horas extra × tarifa; neto = bruto − descuentos; total de la semana = Σ netos — esc. 6
- [ ] El salario se **copia** al renglón: subir el salario después no cambia la nómina calculada — esc. 17
- [ ] Descuento por crédito `ACTIVO` = el menor entre el descuento semanal y el saldo, con `saldo_posterior` registrado. Con $6,200 y $620: descuento `620.0000`, saldo `5580.0000` — esc. 8. Con $400 y $620: descuento `400.0000`, saldo cero, crédito `LIQUIDADO` con fecha, y una segunda semana calculada no le descuenta nada — esc. 9
- [ ] Dos créditos se descuentan por separado, cada uno con su saldo posterior — esc. 10. Si la suma supera el bruto, el neto queda en cero y nunca negativo, con una advertencia en la respuesta que nombra al empleado. Cuando el bruto no alcanza, se descuenta **por antigüedad del adeudo** —primero lo que se debe desde más semanas atrás—, **sin prioridad por tipo de crédito**, hasta agotar el bruto; lo no descontado sigue en el saldo (`PA-22`, resuelta el 2026-10-17). Un test con un préstamo más antiguo que el Infonavit verifica que el préstamo se descuenta primero
- [ ] **Todo el cálculo en una sola transacción**: un descuento que el motor rechaza por el invariante 3 deshace la semana entera, y un test lo provoca saltándose el dominio y verifica que no queda ningún renglón — esc. 11
- [ ] Recalcular la semana **excluyendo una cuadrilla** libera su modalidad `NOMINA` por la interfaz de TKT-053: es la salida a la que apunta el contrato de `RN-22` cuando el que llega tarde es el pago de destajo (HDU-008 esc. 14; `PA-20`, resuelta el 2026-10-17)
- [ ] **Recalcular revierte antes de calcular.** Mientras la semana está `ABIERTA`, recalcular devuelve al saldo los descuentos del cálculo anterior —reactivando el crédito que hubiera liquidado— y sustituye renglones, imputaciones y descuentos, en la misma transacción. Un test calcula dos veces y verifica saldos idénticos a los de un solo cálculo
- [ ] Recalcular o modificar una semana `CERRADA` o `PAGADA` responde `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el mensaje de que las correcciones van en la semana siguiente — esc. 16 **(la extensión a `CERRADA` es asumida: el escenario solo nombra `PAGADA`)**
- [ ] Antes de persistir, reclama la modalidad `NOMINA` por cada **cuadrilla** que aparezca en las jornadas de la semana (TKT-053), comparando por el **jueves de corte**: la semana de nómina de viernes a jueves y la de destajo de jueves a miércoles que terminan con el mismo corte son la misma semana para `RN-22` (`PA-19`). Si alguna ya cobró destajo, el conflicto bloquea **solo a esa cuadrilla** (`PA-20`, resuelta el 2026-10-17): `RN-22` con el pago existente y su importe, las acciones de cancelar ese pago de destajo (TKT-047) o cambiar de modalidad, y **ningún renglón para sus integrantes**, que quedan fuera del cálculo hasta resolverlo; la nómina del resto de la semana se calcula. La forma HTTP: el cálculo responde `200` con una lista `cuadrillas_excluidas`, cada una con su contrato `RN-22`; responde `409` solo si no queda ninguna cuadrilla que calcular — esc. 19
- [ ] Un empleado con jornadas en dos cuadrillas de modalidad distinta en la semana responde `409` `CONFLICTO` señalando las dos asignaciones y sus fechas, con la acción de registrar la decisión; el recálculo acepta, por empleado, qué días van a nómina y el motivo, y lo asienta en la bitácora — esc. 20. **(asumido)** Una cuadrilla cuenta como de destajo esa semana si tiene reclamada la modalidad `DESTAJO`
- [ ] Invoca la imputación de TKT-056 por cada renglón
- [ ] Los escenarios 7, 8, 9 y 13 se prueban con las cifras reales de las hojas de nómina (DoD de HDU-009)

**Non-goals** — No calcula impuestos, cuotas ni prestaciones de ley. No registra pagos (TKT-051). No modifica una nómina pagada.

---

### TKT-051 · Pagos agrupados, consulta inversa y cierre de semana

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-050 |

**Qué hace.** Registra los depósitos separando *quién recibe* de *por cuenta de quién* (`RN-14`), permite preguntar por cualquier trabajador quién cobró su pago, y cierra la semana solo cuando todos tienen forma de cobro.

**Criterios técnicos**

- [ ] `POST /api/v1/semanas-nomina/{id}/pagos` con receptor, importe total, método, fecha y desglose por empleado. Tres netos de $3,000, $4,000 y $4,000 depositados en un solo pago de $11,000 al líder quedan con el líder como receptor y los tres en el desglose — esc. 13
- [ ] Un desglose que no suma el total responde `409` con regla `RN-14` y la diferencia en el detalle (`"500.0000"`), y no persiste ni el pago ni el desglose — esc. 14. El invariante 7 respalda el rechazo, con un test que se salta el dominio
- [ ] El importe del desglose de un empleado no puede exceder su neto pendiente de pagar en la semana **(asumido: el PRD no lo dice, pero sin ello un pago agrupado puede cubrir de más sin que nadie lo vea)**
- [ ] `GET /api/v1/empleados/{id}/pagos-nomina?semana_id=…` devuelve qué pago lo cubrió, quién lo recibió y por cuánto — esc. 13
- [ ] `POST /api/v1/semanas-nomina/{id}/cierre` pasa a `CERRADA`. Si un empleado sin cuenta bancaria no aparece en el desglose de ningún pago, `409` con regla `RN-14` listando a los empleados sin forma de cobro, y la semana sigue `ABIERTA` — esc. 15
- [ ] `POST /api/v1/semanas-nomina/{id}/pago` pasa de `CERRADA` a `PAGADA`, reservado al rol `ADMINISTRACION` al confirmar los depósitos del sábado (`PA-22`, resuelta el 2026-10-17); con otro rol, `403` y el intento se asienta como `DENEGAR`
- [ ] Desde `CERRADA`, la imputación de la semana cuenta para el semáforo (`ns.estado IN ('CERRADA','PAGADA')`, [§15](03-modelo-datos.md#la-nómina-va-aparte)); el test de HDU-009 esc. 18 es de TKT-056
- [ ] Ningún pago se registra ni se modifica en una semana `PAGADA` — esc. 16
- [ ] Bitácora en cada pago, cierre y paso a pagada
- [ ] Datos reales de referencia en los tests: `OMAR Y JUAN`, `LUPE Y JULIO`, `TABLAROQUEROS TOÑO Y NERI`

**Non-goals** — No timbra recibos ante el SAT. No se integra con ningún banco. No calcula nada: consume el neto de TKT-050.

---

### TKT-052 · Interfaz de jornadas y nómina semanal

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-051, TKT-008 |

**Qué hace.** Las pantallas de oficina de Administración: abrir la semana, capturar jornadas, calcular, resolver advertencias, registrar depósitos y cerrar.

**Criterios técnicos**

- [ ] Apertura de semana con selector de fecha que propone jueves; la validación que manda es la del servidor
- [ ] Captura de jornadas en rejilla empleado × día, con la obra de cada día, fracción y horas extra; ante un duplicado ofrece corregir la jornada existente — esc. 4
- [ ] Vista del cálculo con días, importes, descuentos —en el orden en que se aplicaron, por antigüedad del adeudo— y saldo posterior de cada crédito, y la advertencia de neto protegido
- [ ] Las cuadrillas excluidas por `RN-22` se listan aparte con su contrato y sus acciones, mientras el resto de la semana se muestra calculado — HDU-009 esc. 19
- [ ] Marcar la semana como `PAGADA` solo se ofrece con el rol `ADMINISTRACION`; la decisión es del servidor
- [ ] **Advertencia de cambio de cuadrilla a mitad de semana** con las dos asignaciones y la captura de la decisión con el componente de motivo de TKT-008 — esc. 20
- [ ] Captura de pago agrupado que muestra, mientras se escribe, la diferencia entre depósito y desglose calculada con `decimal.js`; la decisión es del servidor
- [ ] Cierre que lista a los empleados sin forma de cobro cuando el servidor lo rechaza — esc. 15
- [ ] Semana `PAGADA` en solo lectura, sin controles de edición — esc. 16
- [ ] Consulta inversa desde la ficha del empleado
- [ ] Sin conexión, todas las acciones aparecen deshabilitadas con la explicación de que la nómina exige servidor; nada se encola (regla 1 de ADR-015)

**Non-goals** — No permite modificar una nómina pagada. No imprime recibos.

---

## Transversal a HDU-008 y HDU-009 · RN-22

---

### TKT-053 · Exclusividad de modalidad de pago por cuadrilla y semana

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-044 |

**Qué hace.** Garantiza que una cuadrilla cobra por destajo **o** por nómina en una semana, nunca por ambas (`RN-22`, **PA-09**), con la tabla que el invariante 15 necesita, la regla en `dominio/` y la interfaz que reclaman los dos lados.

**Criterios técnicos**

- [ ] Tabla `modalidad_pago_semana` con `UNIQUE (cuadrilla_id, semana)` — invariante 15 —: `RN-22` habla de cuadrilla y semana, no de obra —, con test que reclama las dos modalidades y verifica que la segunda falla en el motor
- [ ] **`semana` es siempre el jueves de corte**, con `CHECK (EXTRACT(DOW FROM semana) = 4)` — invariante 37 —, y los dos lados la normalizan antes de reclamar (`PA-19`, resuelta el 2026-10-17). El destajo va de **jueves a miércoles** y la nómina de **viernes a jueves**; lo que comparten es el jueves de corte, y por él se compara. Un test genera un pago de destajo de la semana del jueves 20 al miércoles 26 de agosto de 2026 y una nómina del viernes 21 al jueves 27, y verifica que **chocan** —los dos tienen corte el jueves 27—; otro, con una medición del jueves 27, verifica que esa medición es de la semana siguiente y **no** choca
- [ ] Regla pura en `dominio/` con `RN-22` en el docstring y en el nombre de sus tests
- [ ] Interfaz publicada `reclamar_modalidad(cuadrilla_id, semana, modalidad)` que se ejecuta **dentro de la transacción de quien la llama**; reclamar la misma modalidad otra vez no falla
- [ ] El conflicto responde `409` con regla `RN-22`, el pago o la nómina existente y su importe en el detalle, y sus salidas: ante un pago de destajo existente, **cancelarlo** (TKT-047) — HDU-009 esc. 19 —; ante una nómina existente, **recalcular la semana excluyendo la cuadrilla**, que libera su modalidad `NOMINA` (TKT-050) — HDU-008 esc. 14 —; y en los dos, cambiar de modalidad. El conflicto bloquea **solo a la cuadrilla**, nunca la semana entera (`PA-20`, resuelta el 2026-10-17)
- [ ] **Cambiar de modalidad no es una ruta aparte**: es cancelar lo existente y reclamar la otra **(asumido)**. Ninguna operación cambia la modalidad mientras quede un pago vivo de la anterior, y `liberar_modalidad` solo procede cuando no queda ninguno
- [ ] Test de concurrencia con dos transacciones reales y simultáneas —un pago de destajo y un cálculo de nómina de la misma cuadrilla y semana—: exactamente una prospera, como en TKT-022
- [ ] HDU-008 esc. 14 y HDU-009 esc. 19 se prueban **en el mismo PR** contra la interfaz publicada (DoD de las dos historias); TKT-047 y TKT-050 añaden cada uno su test de integración
- [ ] `GET /api/v1/obras/{obra_id}/modalidades-pago?semana=…` para consulta

> **Este ticket es uno solo a propósito.** Las dos historias describen la misma comprobación desde lados opuestos: HDU-008 impide generar destajo si ya hay nómina, HDU-009 impide lo contrario. Implementarlas por separado produciría dos comprobaciones que pueden divergir, y el fallo que evitan —contabilizar dos veces el mismo trabajo en el semáforo— es silencioso. Viaja con la primera de las dos historias y la segunda consume la tabla y la regla que deja creadas.
>
> **La tabla y la regla viven en `personal`**, no en `avance`. La arista `avance → personal` ya existe; si `avance` fuera el dueño, `personal` necesitaría la inversa y el grafo dejaría de ser acíclico, que es lo que `import-linter` rechaza ([arquitectura §5](02-arquitectura.md#por-qué-rn-22-vive-en-personal)).
>
> **Normalizar la semana no es un detalle de formato.** El invariante 15 compara fechas: si el destajo guardara la fecha de la medición y la nómina la de corte, la restricción única nunca encontraría dos filas iguales y `RN-22` pasaría todos sus tests unitarios sin impedir nada.

**Non-goals** — No decide qué modalidad aplica a una cuadrilla: la reclama el primer pago de la semana. No implementa la cancelación ni el recálculo: las acciones apuntan a las rutas de TKT-047 y TKT-050.

---

## Captura en campo · sin conexión y evidencia

Cierra el bloque que la Entrega 1 dejó *pendiente de descomponer*. Absorbe sus cinco trabajos —partir TKT-008 (→ TKT-063), las rutas de captura aceptan `id` del cliente (→ TKT-064), diseño para teléfono (→ TKT-048 y TKT-068), componente de subida y galería (→ TKT-065), adjuntar en cada punto (→ TKT-066 y TKT-067)—; el sexto, el módulo `archivos` mínimo, es TKT-059 de la fase 1, del que dependen todos estos. Las decisiones están en [ADR-015](adr/20260919-captura-diferida-sin-conexion.md) y [ADR-016](adr/20261001-almacenamiento-de-objetos.md) y aquí no se reabren.

## Lo que ningún ticket de este bloque hace

| Prohibición | Dónde se verifica |
|---|---|
| Ampliar los flujos diferibles más allá de `avance` y `entrada_almacen` | TKT-063: la cola rechaza en código cualquier otro tipo · TKT-064: solo esos dos casos de uso aceptan identificador del cliente |
| Evaluar una regla en el cliente | TKT-068: se puede encolar una entrada que excede el saldo cacheado y vuelve rechazada · TKT-048: la validación no es diferible |
| Resolver un conflicto automáticamente | TKT-063: un elemento `EN_CONFLICTO` no sale de ese estado sin una decisión del usuario |
| Meter las fotos en la cola | TKT-063 y TKT-065: un test verifica que la cola no contiene `Blob` ni `File` |
| Servir archivos desde el API | TKT-065: un test verifica que los bytes van al origen del almacén y no al del API |
| Interpretar el XML del CFDI | Nada en este bloque lo lee: F8.3 es v1.1, y TKT-059 solo lo parsea hasta la raíz para validar el tipo |

## Qué ticket es dueño del test de cada escenario

La tabla cubre los escenarios cuyo test reparten varios tickets: los de este bloque y los de fase 1 que llegaron con las respuestas del cliente del 2026-10-17. El resto los nombra el ticket que los implementa.

| Escenario | Dueño del test | Contribuyen |
|---|---|---|
| HDU-005 esc. 21 · 22 · fase 1 | TKT-035 | TKT-019, TKT-025, TKT-027, TKT-033, TKT-034, TKT-038 |
| HDU-005 esc. 23 · fase 1 | TKT-036 | TKT-038 |
| HDU-006 esc. 16 · fase 1 | TKT-039 | TKT-011, TKT-040, TKT-041 |
| HDU-002 esc. 14 | TKT-063 | TKT-064 |
| HDU-005 esc. 15 · 16 · 17 · 18 | TKT-068 | TKT-063, TKT-064 |
| HDU-005 esc. 19 · 20 | TKT-066 | TKT-059, TKT-065, TKT-067 |
| HDU-008 esc. 18 · 19 · 20 | TKT-048 | TKT-063, TKT-064 |
| HDU-008 esc. 21 · 23 · 24 · 25 | TKT-066 | TKT-065, TKT-048 |
| HDU-008 esc. 22 | TKT-067 | TKT-064, TKT-048 |

---

### TKT-063 · Armazón sin conexión en el cliente

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-008, TKT-006, TKT-057 |

**Qué hace.** Monta lo que TKT-008 dejó de tener: service worker, caché persistida de lectura, cola en IndexedDB y sincronización FIFO idempotente (`RNF-18`). No hace diferible ningún flujo: deja la maquinaria para que TKT-048 y TKT-068 la usen.

**Criterios técnicos**

- [ ] Service worker con `vite-plugin-pwa` que sirve el paquete instalado: un test de Playwright carga la aplicación, corta la red, recarga y la aplicación abre
- [ ] Al detectar una versión nueva del API, la caché del paquete se invalida y se avisa al usuario: una versión vieja sirviendo código viejo es el modo de fallo nuevo que ADR-015 declara
- [ ] Caché persistida de TanStack Query (`@tanstack/query-persist-client` sobre `idb`) solo para las consultas que una pantalla de campo declara necesitar; el resto no se persiste
- [ ] Cola en IndexedDB con un registro por elemento: identificador UUID generado en el cliente, tipo, usuario de la sesión, `capturado_en`, carga y estado `PENDIENTE`, `SINCRONIZADO` o `EN_CONFLICTO` con el contrato de error si lo hubo
- [ ] **La cola solo admite `AVANCE` y `ENTRADA_ALMACEN`**: encolar otro tipo lanza un error en código, con test
- [ ] **Toda mutación no diferible falla explícitamente sin conexión** con un mensaje que dice que exige servidor. Un test corta la red, intenta enviar una requisición, verifica el mensaje y que la cola sigue vacía, y al reconectar verifica que **no** se creó ninguna requisición: lo que se prueba es la ausencia — HDU-002 esc. 14
- [ ] La consulta de disponible por partida no se persiste en caché: sin conexión no se muestra ningún disponible que pueda leerse como autorización — HDU-002 esc. 14
- [ ] Sincronización **FIFO que se detiene en el primer conflicto** (regla 6): con tres elementos y el segundo rechazado, el tercero sigue `PENDIENTE` y un test verifica que no salió su petición
- [ ] Reintento al recuperar conexión. Un corte después de que el servidor aplicó un elemento y antes de recibir la respuesta se resuelve reenviando: el servidor responde con la representación actual (TKT-064) y el elemento pasa a `SINCRONIZADO` sin duplicar
- [ ] **La cola solo sube con sesión válida** (regla 2, `RNF-01`): un `401` detiene la subida, conserva los elementos y pide iniciar sesión; un `403` por rol retirado la detiene, los conserva y muestra el motivo — HDU-008 esc. 20. Si quien inicia sesión no es el dueño de la cola, la cola no sube y se explica **(asumido: un dispositivo por persona; es la pregunta 1 que el bloque pendiente dejaba al cliente)**
- [ ] El token de doble envío se obtiene fresco antes de subir (`RNF-05`)
- [ ] Un elemento `EN_CONFLICTO` solo sale de ese estado por decisión del usuario —corregir y reencolar con el mismo identificador, o descartar con confirmación—; nada lo reintenta solo (regla 5)
- [ ] Indicador permanente: conectado o sin conexión, elementos en cola y desde cuándo espera el más antiguo, elementos en conflicto y **de cuándo son los datos que se muestran** (regla 7, `MS-1`). La antigüedad se muestra siempre y nunca se oculta el dato por viejo **(asumido: cuánto llega a estar un residente sin señal es la pregunta 2, abierta)**
- [ ] Los dos flujos de campo escriben **siempre** por la cola, haya señal o no: hay un solo camino de escritura y el modo sin conexión no es un modo aparte **(asumido: decisión de implementación)**
- [ ] **La cola no guarda archivos**: un test verifica que ningún elemento contiene `Blob` ni `File` y que su tamaño serializado no supera 64 KB (octava regla de ADR-016)
- [ ] Se pide almacenamiento persistente al navegador (`navigator.storage.persist()`) para reducir el desalojo, y si se niega se avisa: lo encolado vive solo en el dispositivo
- [ ] No se inicia sesión sin conexión

> **Separado de TKT-008 porque nadie lo consume en la fase 1.** El esqueleto, el inicio de sesión y el cliente de API se necesitan para importar la línea base; la cola no la necesita nadie hasta que hay algo que capturar en obra. Llevarla en el sprint 1 era pagar cinco puntos por una maquinaria sin pasajeros.

**Non-goals** — No hace diferible ningún flujo: eso lo deciden TKT-048 y TKT-068. No implementa nada en el servidor (TKT-064). No sube fotos. No permite iniciar sesión sin conexión.

---

### TKT-064 · Sincronización idempotente en el servidor

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-035, TKT-037, TKT-047 |

**Qué hace.** Hace que lo encolado entre por **los mismos casos de uso** que lo capturado en línea (regla 4 de ADR-015), con idempotencia sobre el identificador que genera el cliente y la misma respuesta de error por elemento.

**Criterios técnicos**

- [ ] `POST /api/v1/entradas-almacen` y `POST /api/v1/avances` aceptan `id` —UUID generado por el cliente— y `capturado_en`. **La sincronización no tiene ruta propia**: cada elemento de la cola es una petición a la ruta de su caso de uso, y su respuesta es la respuesta por elemento
- [ ] Mismo `id` y misma carga ya aplicados responden `200` con la **representación actual** del recurso —que pudo cambiar desde entonces, por ejemplo al validarse—: ninguna fila nueva, ningún movimiento de inventario nuevo, ningún asiento de bitácora nuevo. Un test reenvía tres veces y cuenta — HDU-005 esc. 16, lado servidor; el dueño es TKT-068
- [ ] **"Misma carga" se decide comparando los campos capturados, sin columna de hash.** Para una entrada: `orden_compra_id`, `folio_remision`, `fecha_remision`, `capturado_en` y, por renglón, `orden_compra_renglon_id`, `cantidad` y `solicitud_autorizacion_id`. Para un avance: `area_id`, `etapa_destajo_id`, `cuadrilla_id`, `fecha_medicion`, `m2_real` y `capturado_en`. Lo que el servidor deriva —`m2_contrato`, `semana`, `proveedor_id`— no entra en la comparación
- [ ] **El reenvío idempotente no dispara los rechazos por duplicado**: reenviar una entrada no responde *folio de remisión duplicado* (HDU-005 esc. 7), y reenviar un avance no responde *avance duplicado* (HDU-008 esc. 12). Un test por cada uno
- [ ] Mismo `id` con carga distinta responde `422` identificando la reutilización; nada se modifica
- [ ] Dos reenvíos simultáneos del mismo `id`: uno responde `201` y el otro `200`, con dos transacciones reales y la violación de clave primaria traducida, nunca un `500`
- [ ] Un elemento rechazado no deja documento, así que reenviarlo **se vuelve a evaluar** contra el estado actual del servidor. El rechazo de `RN-07` tampoco deja rastro: la solicitud de autorización del excedente se crea en una petición aparte (TKT-027), no la crea el rechazo
- [ ] Una entrada encolada que excede lo ordenado responde `409` con el contrato de `RN-07` y sus cifras — HDU-005 esc. 17, lado servidor. Dos avances de dispositivos distintos para la misma área, etapa, cuadrilla y semana: el segundo responde `409` `CONFLICTO` con la acción de pedir el rechazo del existente al Director de Proyectos, respaldado por el invariante 31 — HDU-008 esc. 19, lado servidor; el dueño es TKT-048. Un test compara el cuerpo del rechazo encolado con el del mismo rechazo en línea y verifica que coinciden salvo el identificador de correlación
- [ ] El permiso se comprueba por elemento: un rol retirado entre la captura y la sincronización responde `403` con el contrato y se asienta como `DENEGAR` — HDU-008 esc. 20, lado servidor —; sesión inválida, `401`. Ambas exigen el token de doble envío
- [ ] **Solo estos dos casos de uso aceptan `id` y `capturado_en`**: en cualquier otra ruta, notablemente `POST /api/v1/requisiciones`, esos campos responden `422` — HDU-002 esc. 14, lado servidor
- [ ] `capturado_en` se guarda junto a `creado_en` —la migración de este ticket añade `entrada_almacen.capturado_en`; la de `avance` la crea TKT-046— y se rechaza con `422` si es posterior al momento del servidor más cinco minutos **(asumido)**; la bitácora asienta los dos
- [ ] `m2_contrato` se copia del alcance **vigente al sincronizar**, no del que el dispositivo tenía en caché: un test corrige el alcance entre la captura y la subida y verifica que el avance recibe el valor nuevo
- [ ] Un avance se sincroniza sin ningún archivo y queda creado — HDU-008 esc. 22, lado servidor. Este test ya nombra el escenario, así que el verificador lo encuentra desde el sprint 8 aunque el dueño, TKT-067, llegue en el 10

> **Por qué no hay un endpoint `/sincronizaciones` que reciba la cola entera.** Un despachador que llamara a los casos de uso de `almacen` y de `avance` tendría que vivir en un módulo que dependiera de los dos y pudiera escribir en ellos. El único que depende a la vez de `almacen` y de `avance` es `analitica`, y es de solo lectura; crear un undécimo módulo para esto sería ampliar la arquitectura desde un ticket. Con una petición por elemento, los rechazos usan los mismos códigos `409`, `422` y `403` que en línea, y el orden FIFO lo garantiza el cliente, que es quien tiene la cola.

**Non-goals** — No fusiona ni resuelve conflictos. No acepta lotes. No relaja ninguna regla para lo encolado. No recibe archivos.

---

### TKT-065 · Componente de subida y galería

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-059, TKT-008 |

**Qué hace.** Un componente reutilizable, hermano de los tres de TKT-008, que abre la cámara, comprime, sube directo a la URL prefirmada con progreso y reintento, confirma, y muestra miniaturas y visor. No conoce a qué documento adjunta: lo recibe de quien lo usa.

**Criterios técnicos**

- [ ] `<input type="file" capture>` abre la cámara del teléfono; también admite elegir de la galería
- [ ] Las imágenes se comprimen y **normalizan a JPEG** con `canvas` antes de subir ([stack §5.1](06-stack-tecnologico.md#51-composición)), con lado mayor de 2048 px **(asumido)**. Un HEIC que el navegador no sabe convertir se sube tal cual y se ofrece como descarga, sin romper la galería
- [ ] El video no se recomprime. El componente avisa antes de subir si excede el límite (`RNF-06`, 50 MB **asumido**, `PA-15`), por cortesía: el límite lo hace cumplir el servidor
- [ ] Flujo: calcula el SHA-256 con Web Crypto, pide el alta con nombre, tamaño y hash por la función que le pasa quien lo usa, sube los bytes directo al almacén con indicador de progreso, y pide la confirmación
- [ ] **Los bytes nunca pasan por el API**: un test intercepta la red y verifica que la subida va al origen del almacén y no al del API
- [ ] Reintento ante fallo; si la URL prefirmada caducó, pide un alta nueva y el `PENDIENTE` anterior lo recoge el barrido de TKT-059
- [ ] Miniaturas y visor: imagen y video en línea desde el origen aislado, cualquier otro tipo como enlace de descarga. La URL de lectura es de vida corta y se pide de nuevo al caducar
- [ ] Un adjunto `ANULADO` se muestra tachado, con autor y motivo, nunca oculto
- [ ] **Sin conexión el componente no ofrece adjuntar**, ni guarda nada en IndexedDB: explica que la evidencia se adjunta cuando el documento esté sincronizado. Se deshabilita también mientras el documento esté `PENDIENTE` en la cola, porque el servidor exige que exista ([modelo de datos §12](03-modelo-datos.md#12-archivos-adjuntos))
- [ ] Usable en teléfono con una mano

> **Sin conexión, las fotos se quedan en la cámara del teléfono.** Es la consecuencia directa de la octava regla de ADR-016: si el componente las retuviera en el navegador hasta tener señal, la cola de fotos que esa regla prohíbe existiría con otro nombre. El residente fotografía con la cámara, y adjunta desde la galería cuando el avance ya está sincronizado.

**Non-goals** — No expone rutas. No decide permisos ni anula: lo hacen TKT-066 y TKT-067. No guarda archivos en el dispositivo.

---

### TKT-066 · Evidencia y expediente en el servidor

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-059, TKT-047, TKT-035, TKT-012 |

**Qué hace.** Adjuntar a un avance (F8.1), a una entrada de almacén (F8.2) y a la obra (F8.4), anular sin borrar y consultar el expediente de la obra (F8.5). La integridad referencial que el motor no puede dar ([§12](03-modelo-datos.md#12-archivos-adjuntos)) la da aquí el caso de uso dueño del documento.

**Criterios técnicos**

- [ ] Dueño de los tests de HDU-008 esc. 21, 23, 24 y 25 y de HDU-005 esc. 19 y 20; el 22 es de TKT-067
- [ ] `POST /api/v1/avances/{id}/adjuntos` en el módulo `avance`: comprueba que la medición existe y que quien adjunta tiene rol `RESIDENTE` o `DIRECTOR_PROYECTOS` **(asumido)**, y crea el `archivo` `PENDIENTE` por la interfaz de `archivos` con `referencia_tipo = 'AVANCE'` y el `obra_id` copiado del avance. Devuelve la URL prefirmada de subida — HDU-008 esc. 21
- [ ] Se puede adjuntar a un avance en cualquier estado, incluido `VALIDADO`: la evidencia llega después que la medición y ese es el coste declarado de ADR-016 — HDU-008 esc. 22
- [ ] Adjuntar a un avance que todavía no existe responde `404`: el documento tiene que existir antes que su adjunto
- [ ] `POST /api/v1/entradas-almacen/{id}/adjuntos` en `almacen`, con `referencia_tipo = 'ENTRADA_ALMACEN'`, para `ALMACEN` o `RESIDENTE` — HDU-005 esc. 19
- [ ] `POST /api/v1/obras/{obra_id}/documentos` en `presupuesto`, con `referencia_tipo = 'OBRA'` y `referencia_id` nulo — invariante 26 —, para `DIRECCION_GENERAL` o `DIRECTOR_PROYECTOS` **(asumido)** — F8.4
- [ ] La confirmación es la de TKT-059. Al pasar a `DISPONIBLE`, la bitácora asienta el hash junto al adjunto y al documento al que pertenece (`RNF-19`), con test que lo lee de vuelta
- [ ] Un ejecutable renombrado a `.pdf` no llega a `DISPONIBLE`, se rechaza con `409` `CONFLICTO` `ARCHIVO_TIPO_NO_PERMITIDO` indicando el tipo detectado y los admitidos, su objeto se barre y no aparece ni en la entrada ni en el expediente; un `.svg` presentado como imagen, igual — HDU-005 esc. 20
- [ ] Adjuntar no cambia nada del documento: ni el estado de la entrada ni el saldo de la orden ni la validación de `RN-05`, ni el estado de la medición — HDU-005 esc. 19, HDU-008 esc. 23
- [ ] Límites por tipo (`RNF-06`; 15 MB imagen, 50 MB video, 25 MB documento, **asumidos**, `PA-15`): un video declarado de 120 MB responde `422` con el límite y el tamaño, sin emitir URL ni crear objeto; un objeto cuyo tamaño real difiere de lo declarado no llega a `DISPONIBLE` al confirmar y responde `409` `CONFLICTO` `ARCHIVO_TAMANO_DISTINTO`. Un test por cada camino — HDU-008 esc. 23
- [ ] `POST /api/v1/archivos/{id}/anulacion` con motivo: pasa a `ANULADO` con autor y motivo — invariante 24 —, y un test verifica que **el objeto sigue en el almacén**. Sin motivo, `422`; sobre un adjunto ya anulado, `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`. Puede anular quien lo subió o el `DIRECTOR_PROYECTOS` **(asumido)** — HDU-008 esc. 24
- [ ] **No existe ninguna ruta `DELETE` sobre archivos**, verificado por un test que recorre el enrutador
- [ ] `GET /api/v1/avances/{id}/adjuntos` y `GET /api/v1/entradas-almacen/{id}/adjuntos`, sobre el índice `(referencia_tipo, referencia_id)`
- [ ] `GET /api/v1/obras/{obra_id}/expediente`, paginado y filtrable por tipo de referencia y estado, sobre el índice `(obra_id, estado, creado_en DESC)`: por defecto los `DISPONIBLE`, con quién lo adjuntó, cuándo y a qué documento; los `ANULADO`, a petición y con su motivo — F8.5
- [ ] La lectura usa la URL de descarga de TKT-059: el rol se comprueba al emitirla y su vida es corta
- [ ] **La evidencia no condiciona ninguna regla**: un contrato de `import-linter` verifica que ningún `dominio/` importa de `archivos`, y un test valida un avance sin ningún adjunto y verifica que queda `VALIDADO` — HDU-008 esc. 25 **(asumido, `PA-14`)**

> **Si `PA-14` se respondiera *"sin foto no se valida"*, el escenario 25 se invierte** y deja de ser un test de este ticket: nace una regla de negocio nueva, la validación pasaría a depender de `archivos`, y la octava regla de ADR-016 —el avance sincroniza sin sus fotos— dejaría de sostenerse. Habría que reabrir la frontera de ADR-015 antes de tocar código.

**Non-goals** — No interpreta el XML del CFDI ni adjunta facturas (F8.3, v1.1). No busca dentro de los documentos. No borra nada. No implementa la interfaz (TKT-048 para la medición, TKT-067 para la remisión y el expediente).

---

### TKT-067 · Interfaz del expediente y de los adjuntos de campo

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-065, TKT-066, TKT-068 |

**Qué hace.** Pone el componente de TKT-065 en la recepción y en la ficha de la obra, y construye la vista del expediente. **Los adjuntos de la medición salieron de este ticket y son de TKT-048**, en el sprint 8: la captura y la validación del avance llegan antes que este ticket, y dejar sus fotos para el sprint 10 habría dejado dos sprints de avance sin evidencia.

**Criterios técnicos**

- [ ] En la recepción (TKT-038 y TKT-068), adjuntar la foto o el PDF de la remisión — HDU-005 esc. 19
- [ ] En la ficha de la obra, subir documentos generales — F8.4
- [ ] Vista del expediente por obra: filtros por tipo de documento y estado, autor, fecha, enlace al documento de origen —incluidas las mediciones de TKT-048— y conmutador para ver los anulados — F8.5
- [ ] Anular un adjunto desde el expediente con el componente de captura de motivo de TKT-008; la decisión es del servidor
- [ ] Los rechazos de tipo y tamaño de la remisión se muestran con el contrato de error, no con un mensaje genérico — HDU-005 esc. 20
- [ ] **Dueño del test de HDU-008 esc. 22**, de extremo a extremo: una medición capturada sin señal con fotos sincroniza sin esperarlas, y las fotos se adjuntan después desde la pantalla de TKT-048. El lado servidor lo prueba TKT-064 desde el sprint 8, con un test que ya nombra el escenario
- [ ] Usable en teléfono

**Non-goals** — No adjunta fotos a las mediciones: es TKT-048. No edita ni borra adjuntos. No busca por contenido. No muestra facturas (v1.1).

---

### TKT-068 · Recepción de material diferible sin conexión

| | |
|---|---|
| **Tipo** | Funcionalidad · HDU-005 · **Talla** M · **Depende de** TKT-038, TKT-063, TKT-064 |

**Qué hace.** Hace diferible la recepción en línea de TKT-038 sobre la cola de TKT-063 (`RNF-18`). Lo que la fase 1 declaraba como diferible en TKT-038 sale de allí y vive aquí. Es **dueño de los tests de HDU-005 esc. 15 a 18**; TKT-063 y TKT-064 aportan la cola y el lado servidor.

**Criterios técnicos**

- [ ] Al abrir la obra con señal, las órdenes `ABIERTA` y `PARCIAL` con sus renglones y saldos quedan en la caché persistida
- [ ] Sin señal, la entrada se captura y queda `PENDIENTE` en la cola **sin generar movimiento de inventario**: un test verifica que el libro mayor del servidor no cambia mientras el elemento está en cola, y que la existencia calculada que muestra la pantalla tampoco — HDU-005 esc. 15
- [ ] Cada renglón muestra el saldo pendiente de la caché **con su antigüedad**, y aparte las cantidades que ya hay en cola para ese renglón. No se resta una de otra ni se muestra un *saldo resultante*: el saldo cacheado orienta y no autoriza — HDU-005 esc. 18
- [ ] **El cliente no evalúa `RN-07`**: capturar más que el saldo cacheado se permite y se encola sin aviso de bloqueo, con test
- [ ] Al recuperar señal la entrada se aplica, y un reenvío por corte no la duplica (prueba de extremo a extremo sobre TKT-064) — HDU-005 esc. 16
- [ ] Una entrada que al subir excede lo ordenado queda `EN_CONFLICTO` con las cifras de `RN-07` —ordenado, recibido acumulado, saldo y excedente— y la cola se detiene. Las opciones son corregir las cantidades y reencolar con el mismo identificador, descartar, o escalar con la acción `SOLICITAR_AUTORIZACION` del contrato, que exige conexión — HDU-005 esc. 17. Autorizada la solicitud, la entrada se reenvía citándola, como en HDU-005 esc. 21 (TKT-035): el elemento en conflicto se reencola con `solicitud_autorizacion_id` en el renglón y **un identificador nuevo**, porque el mismo identificador con otra carga es `422` en TKT-064 **(asumido: las respuestas del 2026-10-17 no tratan el reenvío desde la cola)**
- [ ] Una segunda recepción parcial encolada detrás de una en conflicto no se envía: su saldo dependía de la primera (regla 6), con test
- [ ] Pantalla diseñada para teléfono, con el mismo criterio de TKT-048

**Non-goals** — No incluye traspasos ni mermas (v1.1). No evalúa `RN-07` en el cliente. No mete la foto de la remisión en la cola: se adjunta después (TKT-067).

---

## Sustitución del adaptador simulado

En la fase 1, `analitica` lee la mano de obra y el avance por el puerto de [ADR-017](adr/20261015-fuentes-simuladas-analitica.md) con un adaptador simulado (TKT-060). Este ticket lo sustituye por el real y lo retira entero.

**Va en un bloque propio, TKT-069, y no como sección de TKT-046 o TKT-047**, por tres razones:

- **Es de otros módulos.** TKT-046 es esquema de `avance`; esto es trabajo de `analitica` y, para el consumido, de `avance` implementando el puerto `FuenteEjercido` que declara `compras`. Meterlo en un ticket de esquema obligaría a romper su non-goal *"no implementa ningún caso de uso"*.
- **Retira lo simulado de una vez.** Necesita `pago_destajo`, `avance` y `alcance_destajo` de HDU-008, y nada de HDU-009: la nómina la conecta después TKT-056, y entretanto sale `SIN_DATOS`.
- **Tiene una fecha de entrega que no es la de ningún esquema**: la del primer pago de destajo real, por el consumido de `RN-03`.

---

### TKT-069 · Adaptador real de fuentes de mano de obra y avance

| | |
|---|---|
| **Tipo** | Funcionalidad · HDU-006 · **Talla** M · **Depende de** TKT-060, TKT-039, TKT-021, TKT-046 · **Viaja con** TKT-047 |

**Qué hace.** Implementa el adaptador `REAL` del puerto de ADR-017 sobre `avance` y `alcance_destajo`, hace que `avance` implemente el puerto `FuenteEjercido` de `compras` para el destajo **solo a partir de datos reales**, y **retira el adaptador simulado entero**. La nómina sale `SIN_DATOS` hasta que TKT-056 la conecta en el sprint 9.

**Criterios técnicos**

*Semáforo*

- [ ] El adaptador `REAL` implementa el puerto **sin cambiar su firma ni la consulta del semáforo**: la misma batería de pruebas del puerto se ejecuta contra `VACIO` y `REAL` y pasa con ambos
- [ ] Avance físico (`AVANCE_FISICO`): alcance = Σ `alcance_destajo.m2_contrato` y ejecutado = Σ `m2_real` de los avances `VALIDADO`, por tipo de partida a través de la etapa (**PA-08**), leídos con el rol de solo lectura —invariante 21—, como en [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo)
- [ ] **El importe del destajo no lo suma el puerto**: llega al `ejercido` de la fila por `compras` (abajo), y el adaptador declara la fuente `DESTAJO` como `REAL` o `SIN_DATOS` para el metadato. Sumarlo por las dos vías lo contaría dos veces
- [ ] `NOMINA` sale `SIN_DATOS`: su lectura es de TKT-056
- [ ] **Ninguna fuente sale `SIMULADA`**: es `REAL` si tiene filas y `SIN_DATOS` si no, y el aviso de cifra parcial de HDU-006 esc. 6 lo pinta así. Un test `…_ninguna_fuente_sale_simulada` carga una obra y verifica que la marca *dato simulado*, la columna `ejercido_simulado` y el rótulo *ilustrativa* desaparecen
- [ ] El avance físico es `NULL` —*sin avance medido*— mientras no haya nada validado, y su denominador es `alcance_destajo`, nunca `SUM(avance.m2_contrato)` (regla 12 de `CLAUDE.md`), con un test por cada caso
- [ ] Dueño del test de HDU-008 esc. 13: el costo de destajo llega al semáforo y es distinguible por fuente. Los de HDU-009 esc. 7 —la parte de cada obra— y esc. 18 son de TKT-056

*Consumido de `RN-03`*

- [ ] **`avance` implementa `FuenteEjercido`**, el puerto que declara `compras` (TKT-021), para el destajo: suma `pago_destajo_avance.importe` de las filas **vigentes**, agrupado por `etapa_destajo.tipo_partida_id` y excluidos los pagos `CANCELADO` ([modelo de datos §15](03-modelo-datos.md#el-consumido-de-rn-03)). Sumar `pago_destajo.importe_bruto` a través de la unión contaría el bruto del pago una vez por cada medición que liquida. Se ejecuta con la sesión de la transacción en curso, dentro del bloqueo de ADR-004
- [ ] La arista es **`avance → compras`**, nueva y acíclica —`compras` no importa nada de `avance`—, y ya está declarada en el contrato `grafo-compras` desde TKT-002
- [ ] El destajo llega al consumido **solo** por `FuenteEjercido`, nunca por el puerto de `analitica`: el contrato de TKT-060 que impide a `compras` importar `analitica` sigue en pie
- [ ] **Con un pago de destajo real de $8,000 en `MUROS`**, el disponible baja exactamente `8000.0000`, y una requisición que antes cabía queda `BLOQUEADA` con su excedente. Cancelar ese pago lo devuelve
- [ ] El disponible del endpoint de TKT-023 y el que aplica la evaluación **coinciden al céntimo** con destajo real: el test de TKT-021 se repite con esa fuente activa, y la prueba de concurrencia de TKT-022 se vuelve a ejecutar con pagos de destajo en la partida
- [ ] **La nómina no entra en el consumido**: va aparte y a nivel de obra ([§15](03-modelo-datos.md#la-nómina-va-aparte), **PA-10**). Su test con nómina cerrada en la obra es de TKT-056

*Retirada del simulado*

- [ ] **El adaptador `VACIO` se retira junto con el `SIMULADO`**: desde el sprint 8 el `REAL` es el único adaptador en todos los entornos, y una fuente sin filas ya sale `SIN_DATOS` por sí sola. Un test verifica que la configuración solo admite `REAL`
- [ ] **El adaptador simulado se elimina, no se conserva como opción** (ADR-017, *cuándo revisar*): se borran el adaptador, la semilla `backend/semillas/simulado/` y la opción de configuración. Un test verifica que la configuración ya no admite `SIMULADO` en ningún entorno —ni `local` ni `demostracion`—, que es lo que deja sin objeto la guarda de arranque de la regla 4
- [ ] **Los tests de HDU-006 esc. 14 y 15 se retiran con el adaptador**, no se reescriben: tienen vigencia de fase 1 y salen del verificador con el segmento `· retirado por TKT-069` en su título. Lo que queda cubierto es su contrario, el test `…_ninguna_fuente_sale_simulada` de arriba
- [ ] Desde este ticket, la prueba de rendimiento de `RNF-15` de TKT-058 corre contra el adaptador real con su volumen sembrado, como ADR-017 exige al sustituirlo

> **Viaja con TKT-047 y no después.** Entre el primer pago de destajo real y este ticket habría una ventana en la que el destajo existe y no consume: una requisición pasaría contra un disponible que ya no es real. Por eso TKT-047 no se fusiona sin este, aunque se desarrollen en paralelo.
>
> **La nómina sale `SIN_DATOS` del sprint 8 al 9.** Este ticket no depende de TKT-049 ni de TKT-056: la lectura de `imputacion_nomina_obra` llega con TKT-056, y con ella los tests de HDU-009 esc. 7 y 18. `SIN_DATOS` es correcto entretanto: la nómina real todavía no existe, y el aviso de cifra parcial ya sabe pintarla.
>
> **Se retira entero, en el sprint 8.** Conservar la nómina simulada mientras llega el cálculo pondría una cifra ficticia junto a un destajo real en la misma fila de totales; `SIN_DATOS` dice la verdad. Si una demostración necesitara la nómina antes de TKT-050, se cargan nóminas reales de prueba por los casos de uso, no se resucita el adaptador.

**Non-goals** — No cambia la consulta del semáforo ni añade columnas. No conecta la nómina (TKT-056). No prorratea la nómina entre partidas. No convierte un pago de destajo en una operación que bloquea: `RN-03` sigue regulando requisiciones.

---

## Plan de sprints

## Advertencia sobre la velocidad

**Las cifras de abajo son una hipótesis, no una medición.** No hay historial de este equipo en este proyecto, así que la velocidad base es un supuesto que el primer sprint calibra. El material del Módulo 4 es explícito: *"una estimación sin discusión vale menos que la falta de estimación"*, y *"no multipliques velocity por 2 porque el equipo ahora tiene Claude Code"*.

Supuesto de partida: **una persona con copiloto, ~20 SP por sprint de dos semanas**. Con el buffer del 30-40 % recomendado para equipos con IA en el flujo, se comprometen **13-14 SP**.

El buffer no es pesimismo: los PR generados por agente exigen revisión más cuidadosa, el volumen de código sube y con él los defectos, y las herramientas cambian cada pocas semanas.

## Qué cambió con el corte en dos fases

> **El plan anterior tenía un sprint 6 de 21 SP y había que darlo por partido.** Juntaba HDU-008 y HDU-009 —destajo y nómina, que habían crecido a 8 y 13 puntos— contra un compromiso de 13-14, y la holgura del sprint 7 había dejado de ser un seguro para ser el plan. La revisión de LIDR del 2026-10-14 pidió recortar el MVP a un hilo vertical, y ese recorte resuelve el problema de raíz en lugar de repartirlo: **la mano de obra sale de la fase 1 entera** y en la fase 2 cada historia tiene su sprint. HDU-009 cabe sola en el suyo a 13 SP, y la costura entre jornada y cálculo queda declarada como reserva, no como plan.
>
> Lo que el corte **no** resuelve hay que decirlo igual: la sobrecarga se ha movido al principio. Los sprints 1 y 2 suman fundación y el camino mínimo de `archivos`, y eso no se puede repartir hacia atrás porque todo lo demás depende de ello.

## Sprints de la fase 1 · hilo vertical

| Sprint | Objetivo del sprint | Contenido | SP |
|---|---|---|---|
| **0** | *El esqueleto arranca, persiste y sabe rechazar.* | TKT-001 … TKT-005 | ~17 ⚠ |
| **1** | *Un usuario autenticado entra, la frontera HTTP ya está endurecida y cada PR llega revisado y etiquetado por origen.* | TKT-006 … TKT-009, TKT-057, TKT-062 | ~21 ⚠ |
| **2** | *Se da de alta una obra y se congela su línea base desde el Excel real, subido como archivo verificado, con los catálogos del cliente y los errores reportados fila a fila.* | HDU-001 · TKT-011 … TKT-018, TKT-010, TKT-059 | ~21 ⚠ |
| **3** | *Ninguna requisición sobregira una partida sin autorización explícita y registrada.* | HDU-002 + HDU-003 · TKT-019 … TKT-028 | 13 |
| **4** | *Lo pedido queda en firme frente a un proveedor, y el tablero ya compara presupuestado contra comprometido, con la mano de obra marcada como simulada.* | HDU-004 + HDU-006 parcial · TKT-029 … TKT-032, TKT-060, TKT-039 … TKT-041 (escalón 1), TKT-061 | ~11 |
| **5** | *El material recibido se refleja al momento como costo ejercido, y lo que falta por llegar tiene fecha comprometida y rastro.* | HDU-005 en línea + cierre de HDU-006 · TKT-033 … TKT-038, TKT-054, TKT-039 … TKT-041 (escalón 2: HDU-006 esc. 4 y 7) | ~10 |
| **6** | *El sistema se puede poner en manos del cliente: lo que se pierda se recupera, lo que falle se puede averiguar, y el API es el que se especificó.* | TKT-058 · cierre del trinquete de TKT-061 · aterrizaje de las costuras | ~3 |

**~96 SP en siete sprints.** La media es de 13.7, dentro del compromiso; el reparto no lo es, porque la fundación va delante por definición.

> **El sprint 1 se queda en ~21 SP y hay que decirlo.** TKT-057 entra ahí porque una autenticación sin límite de intentos no es una autenticación a medias, y TKT-062 porque la etiqueta de origen tiene que existir antes del primer PR de funcionalidad. El armazón sin conexión que salió de TKT-008 **no** compensa: nunca estuvo estimado.
>
> **La costura por donde parte, en este orden:** primero **TKT-062 se va al sprint 4** —nada depende de él, y mientras tanto la etiqueta de origen se pone a mano y se revisa al cerrar el sprint—, lo que deja el sprint 1 en ~19, como estaba. Si tampoco aguanta, los tres componentes reutilizables de TKT-008 —pantalla de bloqueo, formulario de catálogo y captura de motivo— viajan con su primer consumidor: el formulario con TKT-012, la pantalla de bloqueo con TKT-024 y la captura de motivo con TKT-028. El esqueleto, el inicio de sesión y el cliente de API se quedan, porque sin ellos el sprint 2 no arranca.
>
> **El sprint 2 se queda en ~21 SP, y es el más pesado de la fase.** HDU-001 son 14 puntos por sí sola —lee Excel del mundo real, que viene roto—, TKT-010 va aquí por dependencia y TKT-059 porque el Excel no puede pasar por el API y no hay otra puerta. Ninguno de los tres se puede mover.
>
> **La costura:** de TKT-059, el sprint 2 solo necesita la subida, la confirmación por hash y la validación de tipo. **La URL de descarga y el barrido de `PENDIENTE` caducados** pueden ir al sprint 4 sin que HDU-001 lo note, y dejan el 2 en ~19 y el 4 en ~13. El precio es declarado: hasta entonces, una subida abandonada deja una fila en `PENDIENTE` que nadie barre. No corrompe nada —la importación no arranca sin `DISPONIBLE`—, pero es una fila que miente sobre su estado, que es justo lo que el barrido existe para impedir.
>
> **TKT-010 no está en el sprint 1, y no por holgura sino por dependencia.** Los datos semilla cargan `empresa`, `tipo_partida` e `insumo`, tablas que crea TKT-011 en el sprint 2. Sembrarlas antes fallaría por tabla inexistente.
>
> **HDU-006 se reparte entre los sprints 4 y 5, y no es partir la historia por comodidad.** El escalón 2 de TKT-039, TKT-040 y TKT-041 necesita entradas reales, que llegan con TKT-035 en el sprint 5 y con ellas la implementación de `FuenteEjercido` por `almacen`; hasta entonces el ejercido es un *cero real*. La historia se da por terminada al cerrar el 5, con sus escenarios en verde salvo la parte de nómina del 7, que es de la fase 2; en el 4 se demuestra con el aviso de cifra parcial del escenario 6, que existe precisamente para eso.

### El sprint 6 tiene holgura a propósito

**Son ~3 SP contra un compromiso de 13-14, y no es un error de planificación.** Es donde aterriza lo que los sprints 1, 2 y 4 no aguanten —TKT-062 si se movió, la cola de TKT-059, TKT-061 si no cupo en el 4— sin tocar el objetivo de ningún otro sprint. Declararlo como sprint y no como buena intención evita la conversación de siempre, que es descubrir a la semana de arrancar que nadie se ocupó.

Lo que **no** es negociable es la condición de salida: no se pone el sistema en manos del cliente sin respaldo con recuperación a un punto en el tiempo, sin un ensayo de restauración hecho, y sin poder saber qué falló. **Y la fase 1 no se cierra con el trinquete de TKT-061 sin vaciar**: un API que no es el especificado no es un MVP entregado, es uno por documentar.

> **`PA-12` tiene que estar respondida antes de que empiece este sprint.** Es el único ticket de la fase que depende de una respuesta ajena al equipo, y llega tarde por naturaleza: nadie contrata infraestructura para un sistema que todavía no existe. Preguntar en el sprint 5 deja margen; preguntar el primer día del 6 convierte una decisión de presupuesto en una urgencia.

## Sprints de la fase 2 · mano de obra y campo

| Sprint | Objetivo del sprint | Contenido | SP |
|---|---|---|---|
| **7** | *El personal de la obra está dado de alta, y la aplicación ya sabe trabajar sin señal aunque todavía no haya nada que encolar.* | HDU-007 · TKT-042 … TKT-045, TKT-063, TKT-065 | ~13 |
| **8** | *El avance se mide en obra con o sin señal, con su evidencia, se valida en oficina y llega al semáforo como dato real.* | HDU-008 · TKT-046 … TKT-048, TKT-053, TKT-064, TKT-066, TKT-069 · el adaptador simulado se retira entero: destajo y avance físico pasan a `REAL` y la nómina sale `SIN_DATOS` | ~14 |
| **9** | *La nómina de la semana se calcula desde las jornadas y llega a la obra como dato real, y ningún trabajo se paga dos veces.* | HDU-009 · TKT-049 … TKT-052, TKT-055, TKT-056 · con TKT-056 la nómina pasa de `SIN_DATOS` a `REAL` | 13 |
| **10** | *La recepción de material también se captura sin señal y con su remisión adjunta, y el expediente de la obra se consulta entero.* | HDU-005 diferible · TKT-068, TKT-067 (remisión y expediente) | ~3 |

**~43 SP en cuatro sprints.** Ninguno pasa del compromiso.

> **El armazón sin conexión va en el sprint 7, antes del primer flujo diferible**, que es TKT-048 en el 8. Es la razón por la que salió de TKT-008 y la razón por la que no se funde con ninguna historia: si llegara junto a la medición, HDU-005 inventaría después su propia cola. El escenario 14 de HDU-002 —la requisición sin conexión se rechaza en el cliente y no se encola— viaja con él.
>
> **Los adjuntos de la medición van con TKT-048 en el sprint 8**, no con TKT-067 en el 10: la captura y la validación llegan en el 8, y dejar sus fotos para el 10 habría dejado dos sprints de avance sin evidencia. TKT-048 pasa de talla M a L y TKT-067 de M a S. **Los puntos no se mueven**: son de HDU-008 y ya contaban en el sprint 8.
>
> **El adaptador simulado se retira entero, en el sprint 8, con TKT-069.** Viaja con TKT-047, el primer pago de destajo real: entre ese pago y la sustitución habría una ventana en la que el destajo existe y no consume. **El sprint 8 es además el momento en que el término de destajo del `consumido` de `RN-03` deja de ser cero**: `avance` implementa el puerto `FuenteEjercido` de `compras` ([modelo de datos §15](03-modelo-datos.md#el-consumido-de-rn-03)), y la prueba de concurrencia de TKT-022 se vuelve a ejecutar con pagos de destajo en la partida. La nómina no se conserva simulada mientras llega su cálculo: sale `SIN_DATOS` hasta que TKT-056 la conecta en el sprint 9, que dice la verdad y que el aviso de cifra parcial ya sabe pintar ([ADR-017](adr/20261015-fuentes-simuladas-analitica.md)). Desde el 8, la prueba de `RNF-15` corre contra el adaptador real.
>
> **TKT-053 viaja con HDU-008, la primera de las dos historias que ejercen `RN-22`**, y HDU-009 consume en el sprint 9 la tabla y la regla que deja creadas.
>
> **La costura de HDU-009 sigue declarada, ahora como reserva.** Si la velocidad no aguanta, la historia se parte en *registro de jornada diaria* —TKT-049, TKT-055 y TKT-056, 5 SP, la mitad que alimenta el semáforo— y *cálculo de nómina con créditos y pagos agrupados* —TKT-050, TKT-051 y TKT-052, 8 SP—. La primera se queda en el 9 y la segunda va al 10, que tiene holgura para ella y queda en ~11. El precio es declarado: la nómina del semáforo sigue `SIN_DATOS` hasta el 10, porque el importe por obra llega con el cálculo (TKT-050), no con la jornada. A 13 SP la costura no hace falta de entrada; declararla por adelantado evita decidirla a mitad de sprint y con prisa.

**El objetivo del sprint es la pieza más importante de estas tablas.** Si alguien pregunta qué se hizo, la respuesta es el objetivo, no la lista de tickets.

Los sprints 0, 1 y 2 exceden el compromiso de 13-14 SP porque la fundación no se puede partir más sin dejar el sistema en un estado que no arranca. Es una excepción consciente, y el primer sprint dirá si el supuesto de velocidad aguanta.

## Por qué este orden

**La fundación primero, completa.** Repartir el contrato de error o la verificación de fronteras entre sprints posteriores significa que cada historia inventa su propio formato y su propia disciplina, y luego hay que unificarlos.

**La línea base antes que nada.** Sin referencia congelada, ninguna regla de presupuesto tiene contra qué evaluar. Es también la historia más arriesgada —lee Excel del mundo real, que viene roto— y conviene descubrir sus sorpresas en el sprint 2, no al final.

**El hilo vertical antes que la mano de obra.** Importar la línea base, levantar una requisición, que se bloquee o se autorice, emitir la orden, recibir el material y verlo en el semáforo es el recorrido que demuestra el producto, y cabe en siete sprints. Todo lo que no está en ese recorrido espera a la fase 2, aunque sea *must-have* para el uso diario, porque un MVP que no se puede demostrar entero no es un MVP.

**HDU-003 junto a HDU-002.** Una requisición bloqueada sin nadie que la resuelva es un callejón sin salida, y el producto existe para que el bloqueo sea una bifurcación. Por eso la autorización entra en el hilo y en el mismo sprint que el bloqueo.

**El semáforo en el sprint 4, con datos simulados marcados.** Aparece pronto y crece: en el 4 compara presupuestado con comprometido, en el 5 suma el ejercido de materiales, en la fase 2 la mano de obra real. Mientras tanto, las columnas de mano de obra y avance se rellenan con el adaptador simulado de TKT-060 y llevan su marca en cada celda. Un tablero que aparece al final es un tablero que se descubre mal enfocado al final; uno que se rellena sin marcar, miente.

**El personal al principio de la fase 2.** HDU-007 bloquea tanto a HDU-008 como a HDU-009. Es un bloque de CRUD sin reglas duras, así que comparte bien sprint con el armazón sin conexión, y llega justo antes de que destajo y nómina lo necesiten, con margen si el catálogo revela sorpresas —empleados que pertenecen a varias cuadrillas, créditos con condiciones que el cuestionario no describió—.

**Nómina y destajo en la fase 2, pero dentro del producto.** Son *should-have*, pero sin ellas la cifra del semáforo es parcial: la mano de obra es entre el 59 % y el 100 % del costo directo (`RN-21`). La fase 1 no lo esconde —lo marca—, y la fase 2 no es opcional: es la que convierte la cifra ilustrativa en la cifra real.

## Seguimiento honesto de la velocidad

Desde el primer PR, cada uno se etiqueta por origen: `human`, `human+copilot`, `agent`, `agent+human-review`. A mano en el sprint 0; desde el 1 —o desde el 4, si se usa la costura del sprint 1—, TKT-062 la hace obligatoria. La calidad se reporta segmentada por esa etiqueta.

Si los PR de agente acumulan tres veces más defectos que los humanos, la velocidad total está mintiendo y hay que reasignar esfuerzo a revisión. La velocidad sirve para planificar; **nunca** como indicador de rendimiento.
