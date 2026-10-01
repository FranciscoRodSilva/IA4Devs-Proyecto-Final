# CIMENTA · Tickets de trabajo

> **Capa SDD:** *Tasks*. Descompone las [historias de usuario](04-historias-usuario.md) en unidades de trabajo técnico.
>
> **Alcance:** los tickets necesarios para llevar el proyecto de cero a un sistema que cierra el ciclo de valor. Abarca la fundación del repositorio y las nueve historias.

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

### Regla que atraviesa todos los tickets

> Ningún ticket de funcionalidad se da por terminado si los escenarios de rechazo de su historia no pasan en verde. La [regla de aceptación](04-historias-usuario.md#regla-de-aceptación) aplica al ticket igual que a la historia.

---

## Índice

| Bloque | Tickets | Historia | SP |
|---|---|---|---|
| [Épica 0 · Fundación](#épica-0--fundación) | TKT-001 … TKT-010 | — | ~35 |
| [HDU-001 · Obra y línea base](#tickets-de-hdu-001--obra-y-línea-base) | TKT-011 … TKT-018 | HDU-001 | 13 |
| [HDU-002 · Requisición](#tickets-de-hdu-002--requisición-con-control-de-presupuesto) | TKT-019 … TKT-024 | HDU-002 | 8 |
| [HDU-003 a HDU-009](#tickets-de-hdu-003-a-hdu-009) | TKT-025 … TKT-056 | HDU-003 … HDU-009 | 49 |
| [Endurecimiento y operación](#endurecimiento-y-operación) | TKT-057 … TKT-058 | — | ~6 |
| [**Pendiente de descomponer · captura sin conexión y evidencia documental**](#pendiente-de-descomponer--captura-sin-conexión-y-evidencia-documental) | *sin numerar* | HDU-001, 002, 005, 008 | *~20 sin estimar* |

**58 tickets · ~111 SP**, más el bloque pendiente, que está declarado y **no** descompuesto. La numeración no es contigua: TKT-053 a TKT-056 se añadieron en revisiones posteriores y se listan junto a la historia a la que sirven. TKT-053 es transversal a HDU-008 y HDU-009.

**TKT-057 y TKT-058 salieron de la revisión del stack del 2026-09-19**, que encontró que la especificación no declaraba ningún requisito de seguridad ni de recuperación. Los requisitos están ahora en el [PRD §9](01-descripcion-producto.md#9-requisitos-no-funcionales) y estos dos tickets los implementan.

---

# Épica 0 · Fundación

**Talla: XL · ~35 SP.** Es lo que hay que construir antes de que la primera regla de negocio pueda existir. No entrega valor al cliente, y eso es esperado: entrega la capacidad de entregar valor.

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
- [ ] Un paquete por módulo: `identidad`, `auditoria`, `presupuesto`, `compras`, `almacen`, `avance`, `personal`, `proveedores`, `analitica`
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
- [ ] **Tres roles de PostgreSQL creados en la migración**, no a mano en el servidor: migración (propietario), aplicación y solo lectura (`RNF-09`)
- [ ] El rol de aplicación **no** tiene `UPDATE` ni `DELETE` sobre `intento_acceso` — invariante 20
- [ ] El rol de aplicación **sí** tiene `UPDATE` sobre `explosion_presupuesto` y `presupuesto_control`: en PostgreSQL `SELECT … FOR UPDATE` exige ese privilegio, y sin él el bloqueo pesimista de [ADR-004](adr/20260918-bloqueo-pesimista-presupuesto.md) falla por permisos en tiempo de ejecución. La inmutabilidad de la línea base la garantiza el disparador del invariante 14, no la ausencia de permiso — ver [arquitectura §7.6](02-arquitectura.md#76-seguridad-de-la-frontera)
- [ ] Un test toma `SELECT … FOR UPDATE` sobre `explosion_presupuesto` **con el rol de aplicación** y verifica que funciona; otro verifica que un `UPDATE` directo sobre `linea_base_concepto` falla
- [ ] El rol de solo lectura no tiene más que `SELECT` — invariante 21
- [ ] `lock_timeout` y `statement_timeout` fijados **en el rol de aplicación** (`RNF-16`), de modo que apliquen aunque una ruta nueva no los pida
- [ ] Los tests corren contra PostgreSQL, **no** contra SQLite, construyen el esquema con `alembic upgrade head` y **se conectan con el rol de aplicación**

> Probar contra SQLite para "ir más rápido" verificaría garantías distintas de las de producción. El decimal exacto y las restricciones declarativas son parte del diseño, no un detalle del motor.

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
- [ ] Excepción de dominio que transporta identificador de regla, mensaje, detalle y acciones
- [ ] Manejador global que la serializa según [arquitectura §7.3](02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio)
- [ ] Código `409` para violación de regla, `422` para error de forma, `403` para falta de permiso: tres situaciones, tres códigos
- [ ] Todos los importes del detalle se serializan como cadena
- [ ] El identificador de regla admite únicamente valores con formato `RN-\d{2}`
- [ ] Test que verifica la forma exacta de la respuesta
- [ ] **Registro estructurado en JSON con `structlog` e identificador de correlación por petición**, devuelto también en el cuerpo del error para que el usuario pueda citarlo (`RNF-13`)

> Es la base sobre la que se escriben todos los escenarios de rechazo de las nueve historias — cerca de la mitad de los 131. Si llega tarde, cada historia inventa su propio formato de error.

> **El identificador de correlación vive aquí y no en TKT-058** porque tiene que viajar **dentro** del contrato de error, y porque el patrón de registro hay que establecerlo antes de que existan diez módulos que lo ignoren. Retrofitar el registro estructurado en el sprint 7 sería tocar los diez. Lo que sí queda en TKT-058 es la **agregación** de errores, que es un servicio externo y no se puede contratar antes de tener qué agregar.

**Non-goals** — No implementa ninguna regla concreta. No agrega errores en ningún servicio externo: eso es TKT-058.

---

### TKT-006 · Autenticación y autorización por rol

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-003, TKT-005 |

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
- [ ] Un intento sin permiso responde `403` y queda registrado en la bitácora
- [ ] Ningún endpoint queda accesible sin autenticación salvo el de inicio de sesión, verificado por un test que **recorre el enrutador** y falla si alguna ruta queda sin proteger

> **No se usa `passlib`.** Sin versión nueva desde 2020 en la pieza que guarda las contraseñas de seis roles que autorizan gasto. `pwdlib` hace lo mismo, se mantiene, y es lo que usan los ejemplos públicos de FastAPI — que por el criterio C3 del [stack §1](06-stack-tecnologico.md#1-cómo-se-eligió) cuenta.

**Non-goals** — No implementa recuperación de contraseña, segundo factor ni inicio de sesión federado. No implementa permisos por obra: el MVP autoriza por rol. **No implementa el límite de intentos, CSRF ni las cabeceras de seguridad: son TKT-057**, que viaja en el mismo sprint.

---

### TKT-007 · Bitácora transversal de solo-anexado

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-003 |

**Qué hace.** Crea la tabla `bitacora`, el servicio para escribir en ella dentro de la transacción en curso, y los permisos que la hacen inmutable.

**Criterios técnicos**
- [ ] Tabla `bitacora` según [modelo de datos §10](03-modelo-datos.md#10-identidad-y-auditoría)
- [ ] El asiento se escribe en **la misma transacción** que el cambio: si la bitácora falla, el cambio se deshace
- [ ] El rol de aplicación tiene `INSERT` y `SELECT`, y **no** `UPDATE` ni `DELETE`
- [ ] Un test verifica que un `UPDATE` sobre la bitácora falla a nivel de motor
- [ ] Consulta por obra, por rango de fechas y por regla de negocio
- [ ] Índices `(obra_id, ocurrido_en DESC)` y parcial sobre `regla_negocio`

> Registrar después del cambio, o en un proceso aparte, produce huecos precisamente en los casos de error — que son los que importan.

**Non-goals** — No implementa interfaz de consulta: se consulta por API en esta fase.

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
- [ ] **Los tipos del cliente se generan del OpenAPI** que FastAPI publica (`openapi-typescript`), con la generación en un comando del proyecto y comprobada en CI: si el archivo generado no coincide con el esquema actual, el pipeline falla
- [ ] Cliente de API que reconoce el contrato de error y expone regla, detalle y acciones a los componentes
- [ ] Los esquemas Zod validan **formularios**, no respuestas: no se escribe ningún esquema que espeje un modelo de Pydantic
- [ ] Componente reutilizable de **pantalla de bloqueo** que renderiza cualquier violación de regla mostrando las cifras del detalle y botones para las acciones disponibles
- [ ] Componente reutilizable de **formulario de catálogo** con apertura, foco en el primer campo, validación y confirmación de baja — lo usan HDU-001, HDU-004 y HDU-007
- [ ] Componente reutilizable de **captura de motivo obligatorio** — lo usan HDU-003, HDU-005 y HDU-007
- [ ] Los importes recibidos como cadena se convierten con decimal exacto, nunca con el número nativo
- [ ] Diseño usable en escritorio **y en pantalla de teléfono**: la captura de campo ocurre de pie en obra
- [ ] **Armazón sin conexión** (`RNF-18`, [ADR-015](adr/20260919-captura-diferida-sin-conexion.md)): service worker que sirve el paquete instalado, caché de lectura persistida de TanStack Query, y la cola en IndexedDB con su estado por elemento —pendiente, sincronizado, en conflicto—
- [ ] Sincronización **FIFO que se detiene en el primer conflicto**, con reintento al recuperar conexión y **idempotencia por el identificador que genera el cliente**
- [ ] Indicador permanente de estado: conectado o sin conexión, cuántos elementos hay en cola y **de cuándo son los datos que se están mostrando**
- [ ] La cola solo sube con sesión válida: si el rol se retiró, no entra y se explica por qué (`RNF-01`)

> Los tres componentes reutilizables salen de escenarios que se repiten en varias historias. Extraerlos aquí evita tres implementaciones divergentes de la misma pantalla.

> **El armazón sin conexión va aquí y no en las historias de campo** por la misma razón que el contrato de error: si llega después, HDU-005 y HDU-008 inventan cada una su cola.

**Non-goals** — No implementa ninguna pantalla de negocio. **No hace diferible ningún flujo**: solo deja la cola y el service worker montados; qué se puede capturar sin conexión lo deciden TKT-038 y TKT-048. No permite iniciar sesión sin conexión.

---

### TKT-009 · Pipeline de integración continua

| | |
|---|---|
| **Tipo** | Fundación · **Talla** S · **Depende de** TKT-002, TKT-008 |

**Qué hace.** Configura CI con tests, verificación de fronteras entre módulos y calidad de documentación.

**Criterios técnicos**
- [ ] Trabajo de tests de backend contra PostgreSQL real, con reporte de cobertura
- [ ] Trabajo de tests de frontend
- [ ] Trabajo de verificación de fronteras entre módulos (TKT-002), que falla el pipeline si se cruzan
- [ ] **Auditoría de dependencias**: `pip-audit` y `npm audit`, que fallan el pipeline ante severidad alta (`RNF-08`)
- [ ] **Dependabot** para actualizaciones y **escaneo de secretos** activado sobre el repositorio (`RNF-07`)
- [ ] Calidad de documentación: linter de Markdown, linter de prosa y detector de enlaces rotos
- [ ] Vocabulario del proyecto declarado para el linter de prosa, tomado del [glosario](glosario.md): *tablaroca*, *destajo*, *perfacinta*, *antepecho*, *cajillo*, *plafón*, *redimix*, *CIMENTA*
- [ ] Detector de enlaces también en cron semanal
- [ ] Nivel de aviso en local, nivel de error en CI

**Non-goals** — No configura despliegue: se decide en el Paso 5.

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

**Non-goals** — No importa el catálogo de conceptos (HDU-001). No siembra empleados ni proveedores: son funcionalidad de HDU-007 y HDU-004. No siembra `rol_oficio`: su tabla nace en TKT-042 y el catálogo se carga ahí.

---

# Tickets de HDU-001 · Obra y línea base

Historia: [HDU-001](04-historias-usuario.md#hdu-001--alta-de-obra-e-importación-de-la-línea-base) · 13 SP

---

### TKT-011 · Esquema y migraciones del módulo presupuesto

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-003 |

**Criterios técnicos**
- [ ] Tablas `empresa`, `obra`, `nivel`, `area`, `tipo_partida`, `partida`, `concepto`, `insumo`, `precio_insumo`, `apu`, `apu_insumo`, `apu_cargo`
- [ ] `obra.empresa_id` es clave foránea **obligatoria** ([ADR-008](adr/20260918-despliegue-single-tenant.md)), aunque el despliegue sea de un solo inquilino y nadie filtre por ella
- [ ] Tablas `linea_base`, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`
- [ ] Tablas `importacion`, `importacion_error`, `rendimiento_observado`, con `importacion.latido` y el tipo de error `PROCESO_INTERRUMPIDO` (`RNF-17`)
- [ ] `obra` incluye `retencion_destajo_pct`, `fondo_garantia_pct` e `iva_acreditable` (PA-02, PA-05)
- [ ] Restricción `UNIQUE (obra_id, codigo)` sobre `concepto` — invariante 13
- [ ] Índice único parcial que garantiza una sola línea base `CONGELADA` por obra — invariante 5
- [ ] `UNIQUE (linea_base_id, tipo_partida_id)` sobre `presupuesto_control` — invariante 6
- [ ] `presupuesto_control` incluye `actualizado_por_id`, `actualizado_en` y `motivo_ultimo_cambio`: el tope se recaptura, a diferencia de las copias congeladas
- [ ] Disparador que rechaza `UPDATE` y `DELETE` sobre `linea_base_concepto` y `explosion_presupuesto` cuando la línea base está congelada — invariante 14
- [ ] Índices `(linea_base_id, tipo_partida_id, insumo_id)` sobre `explosion_presupuesto`
- [ ] `rendimiento_observado` es tabla separada de `explosion_presupuesto`: ninguna escribe sobre la otra — invariante 19
- [ ] Un test verifica que el disparador de inmutabilidad dispara

**Non-goals** — No crea tablas de otros módulos.

---

### TKT-012 · Alta y mantenimiento de obras

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-011, TKT-008 |

**Qué hace.** CRUD de obras con sus parámetros de negocio, incluida la baja protegida.

**Criterios técnicos**
- [ ] Alta con código, nombre, domicilio, tipo de contrato, porcentaje de retención de destajo (15 %), porcentaje de fondo de garantía (5 %) e indicador de IVA acreditable
- [ ] Los dos porcentajes son **conceptos distintos** y se guardan en la obra: ninguna constante en el código (**PA-02**)
- [ ] El indicador de IVA acreditable se guarda por obra porque varía entre ellas (**PA-05**, `RN-25`)
- [ ] Código de obra único, con mensaje que identifica la obra en conflicto
- [ ] Máquina de estados `PLANEACION → ACTIVA → SUSPENDIDA/CERRADA`
- [ ] Una obra con línea base congelada o movimientos no se puede eliminar: se suspende o se cierra
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
- [ ] Da de alta los insumos que no existan, marcándolos como creados durante la importación
- [ ] Verifica que el precio unitario reconstruido coincide con el del archivo dentro de la tolerancia decimal; si no, lo reporta como error
- [ ] Se prueba con `MURO STD-635-STD`: material $201.67 + mano de obra $286.07 = costo directo $487.74, precio unitario $641.36

**Non-goals** — No recalcula precios; solo lee y verifica.

---

### TKT-015 · Validaciones y reporte de errores por fila

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-014 |

**Criterios técnicos**
- [ ] Detecta y clasifica: `REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO`
- [ ] Cada error registra hoja, fila, columna, tipo, mensaje y valor original
- [ ] Un error bloqueante deja la importación en estado `CON_ERRORES` y **no** permite confirmar
- [ ] Las filas válidas se conservan en preparación para no repetir el análisis completo
- [ ] Se prueba contra el catálogo de Union Square, que tiene `#REF!` en todas las columnas de precio: debe reportarlo fila a fila, no fallar en bloque
- [ ] El análisis corre en un `ProcessPoolExecutor` de un trabajador: openpyxl retiene el intérprete y degradaría la latencia del resto de la aplicación
- [ ] El trabajo refresca `importacion.latido` mientras analiza, y al arrancar la aplicación un barrido pasa a `CON_ERRORES` toda importación en `ANALIZANDO` con latido vencido, con un error `PROCESO_INTERRUMPIDO` (`RNF-17`)
- [ ] Un test simula la interrupción y verifica que la obra vuelve a admitir importaciones

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
- [ ] Un importe tope superior al de venta exige confirmación con motivo, que queda en bitácora
- [ ] Una requisición contra una obra sin presupuesto de control capturado se rechaza con `409` y acción para ir a capturarlo
- [ ] **Recaptura del tope** por Dirección General con motivo obligatorio: actualiza la fila y asienta en bitácora el valor anterior, el nuevo y el motivo, **con la regla `RN-03`**, de modo que la consulta de excepciones de TKT-027 devuelva las subidas de tope junto a las autorizaciones
- [ ] Recapturar sin el rol `DIRECCION_GENERAL` responde `403`; sin motivo, `422`. En ambos casos el tope conserva su valor

> **Subir un tope es una vía alternativa a autorizar una excepción.** Si se asentara con otra regla —o no se asentara— una partida podría sobregirarse sin que apareciera ni una sola excepción en la bitácora del mes.

**Non-goals** — No implementa versionado por trabajos extra (`RN-18`, v1.1). No permite tocar la línea base congelada: lo que se recaptura es el presupuesto de control, que no forma parte de ella.

---

### TKT-018 · Interfaz de importación

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** M · **Depende de** TKT-017, TKT-012 |

**Criterios técnicos**
- [ ] Carga de archivo con indicador de progreso que no bloquea la pantalla
- [ ] Pantalla de previsualización con jerarquía leída, conteos, importe total e insumos creados durante la importación
- [ ] Tabla de errores navegable por hoja y fila, exportable
- [ ] Botón de confirmar deshabilitado mientras la importación esté en `CON_ERRORES`
- [ ] Acción de congelar con captura obligatoria del motivo
- [ ] La línea base congelada se muestra en modo lectura, sin controles de edición

**Non-goals** — No permite editar conceptos; una corrección se hace reimportando.

---

# Tickets de HDU-002 · Requisición con control de presupuesto

Historia: [HDU-002](04-historias-usuario.md#hdu-002--requisición-con-control-de-presupuesto) · 8 SP

---

### TKT-019 · Esquema y migraciones del módulo compras

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-011 |

**Criterios técnicos**
- [ ] Tablas `requisicion`, `requisicion_renglon`, `solicitud_autorizacion`, `orden_compra`, `orden_compra_renglon`
- [ ] `obra_id` y `tipo_partida_id` con restricción `NOT NULL` en `requisicion` — invariante 1 (**PA-01**)
- [ ] El estado de `requisicion` distingue `RECHAZADA` —decisión de Dirección sobre una excepción— de `CANCELADA` —el solicitante desistió—: mezclarlas contaminaría la consulta de excepciones de `RN-04`
- [ ] `CHECK (cantidad >= 0)` y `CHECK (costo_unitario >= 0)` en los renglones de requisición y de orden — invariante 8
- [ ] Tabla `reprogramacion_entrega` y columna `fecha_compromiso` en `orden_compra_renglon` (**PA-07**)
- [ ] `orden_compra` **no** tiene columna de motivo de cierre: no existe el cierre con saldo
- [ ] `CHECK (cantidad_recibida <= cantidad_ordenada)` en `orden_compra_renglon` — invariante 2
- [ ] `CHECK` que exige motivo al resolver una solicitud — invariante 9
- [ ] `solicitud_autorizacion` modelada de forma genérica, sin acoplarse a requisiciones

**Non-goals** — No implementa lógica: solo esquema.

---

### TKT-020 · Regla RN-03 en el dominio

| | |
|---|---|
| **Tipo** | Funcionalidad · **Talla** S · **Depende de** TKT-004, TKT-005 |

**Criterios técnicos**
- [ ] Función pura que recibe presupuestado, consumido y solicitado, y devuelve permitido o bloqueado con disponible y excedente
- [ ] Evalúa **los dos controles**: importe de la partida y volumen por insumo
- [ ] El `consumido` llega ya calculado y su definición es **una sola** para todo el sistema, la de [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo): `requisiciones vivas + comprometido + ejercido`, cada peso contado una vez
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
- [ ] **El `consumido` se calcula con la consulta de [modelo de datos §15](03-modelo-datos.md#15-la-consulta-del-semáforo), la misma que alimenta el semáforo.** Incluye las requisiciones `EVALUADA` y `AUTORIZADA` sin convertir, el saldo no recibido de las órdenes abiertas y parciales, las entradas de almacén y los pagos de destajo de esa partida
- [ ] Un test verifica que dos requisiciones de $8,000 contra $12,000 disponibles **no pasan las dos**: es el escenario 9 y solo funciona si las requisiciones vivas consumen
- [ ] Un test verifica que el disponible que devuelve el endpoint de consulta y el que aplica la evaluación **coinciden al céntimo**: si divergen, Compras ve en pantalla un número que la regla no respeta
- [ ] `SELECT … FOR UPDATE` sobre `presupuesto_control` (control por importe) y `explosion_presupuesto` (control por volumen) del tipo de partida
- [ ] El tope de importe sale del valor **capturado**, no del sugerido (**PA-03**)
- [ ] Los bloqueos se toman **siempre ordenados por identificador de tipo de partida**, para evitar interbloqueo
- [ ] La requisición bloqueada se **persiste** en estado `BLOQUEADA` con las cifras del momento; no se descarta
- [ ] Se crea la solicitud de autorización dirigida al rol `DIRECCION_GENERAL`
- [ ] Rechaza requisiciones contra obras sin línea base congelada
- [ ] Una requisición cancelada libera el presupuesto que tenía comprometido
- [ ] El vencimiento de `lock_timeout` **se traduce al contrato de error** con la acción de reintentar, nunca a un fallo interno (`RNF-16`)
- [ ] Un test retiene el bloqueo desde otra sesión y verifica que la segunda vence y responde con el contrato, no con un `500`

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
- [ ] `GET` de disponible por partida, con importe y cantidades por insumo, y el **consumido desglosado en tres**: requisiciones vivas, saldo de órdenes y ejercido
- [ ] `GET` de **requisiciones evaluadas sin convertir**, ordenadas por antigüedad, con importe y solicitante: es el contrapeso de que la reserva no caduque sola
- [ ] `POST` de requisición y guardado en borrador sin evaluar
- [ ] Cancelación con motivo desde `EVALUADA`, `BLOQUEADA` o `AUTORIZADA`, que pasa a `CANCELADA` —no a `RECHAZADA`— y **libera la reserva**: es la única transición que lo hace
- [ ] Modificar una requisición ya evaluada responde `409` con la acción sugerida de cancelar y volver a levantar
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
- [ ] El botón de solicitar autorización sale de las acciones del contrato de error, no está cableado en el componente
- [ ] Los importes se calculan con decimal exacto en el cliente

**Non-goals** — No incluye la bandeja de autorizaciones.

---

# Tickets de HDU-003 a HDU-009

Mismo formato y mismos criterios de calidad; se presentan en tabla por concisión. Cada uno hereda la [regla de aceptación](04-historias-usuario.md#regla-de-aceptación) y la DoD de funcionalidad nueva.

### HDU-003 · Resolución de requisiciones bloqueadas · 5 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-025** | S | Casos de uso de autorizar y rechazar, con motivo obligatorio en ambos y resolución idempotente: resolver dos veces falla con `409`. Una solicitud cuya requisición fue cancelada queda "sin efecto" y no admite resolución | No emite orden de compra tras autorizar |
| **TKT-026** | S | Reglas de autoridad en `dominio/`: rol requerido y prohibición de auto-autorización, probadas sin HTTP | No implementa delegación ni suplencia |
| **TKT-027** | S | Endpoints de bandeja, detalle y resolución; contador de pendientes; consulta de bitácora filtrada por regla, incluidos los bloqueos nunca resueltos | No notifica por ningún canal externo |
| **TKT-028** | M | Interfaz de bandeja con contador en la navegación y detalle que muestra las cifras del momento del bloqueo, no recalculadas | No permite autorizar en lote |

### HDU-004 · Proveedores y órdenes de compra · 5 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-029** | S | Esquema y CRUD de `proveedor` con tope de consignación, día de corte (jueves) y día de pago (sábado) por defecto; RFC único; baja lógica bloqueada si hay órdenes abiertas | No registra facturas ni anticipos |
| **TKT-030** | M | Caso de uso de emisión de orden de compra desde requisición `EVALUADA` o `AUTORIZADA`; folio único consecutivo; herencia de obra y partida; rechazo desde estados inválidos y doble emisión | No envía la orden al proveedor |
| **TKT-031** | S | Cancelación de orden sin recepciones, que devuelve la requisición a `EVALUADA` —o a `AUTORIZADA` si nació de una excepción resuelta, para no perder la autorización—. **No libera presupuesto**: lo devuelve al sumando de requisiciones vivas, así que el consumido no cambia. Rechazo de cancelación con recepciones, ofreciendo **reprogramar el faltante** como vía alternativa | No implementa la reprogramación (es TKT-054). No libera reserva: eso solo lo hace cancelar la requisición |
| **TKT-032** | M | Consulta cruzada proveedor × obra: qué insumos, cuánta cantidad y qué importe se pidió a cada proveedor por obra, con filtros de fecha y estado. Interfaz de catálogo y de emisión | No compara precios entre proveedores |

### HDU-005 · Entrada de material con recepción parcial · 8 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-033** | S | Esquema del módulo almacén: `entrada_almacen`, `entrada_renglon`, `movimiento_inventario`, con los tipos de movimiento de v1.1 ya contemplados y `CHECK (cantidad >= 0)` sobre los renglones —invariante 8—. `movimiento_inventario` lleva `tipo_partida_id` propio, copiado del de la requisición de origen: sin él, un `AJUSTE` o una `MERMA` no tienen cómo llegar a una partida del semáforo | No crea `traspaso` ni `merma` |
| **TKT-034** | S | Reglas `RN-05`, `RN-06` y `RN-07` en `dominio/`, incluido el cálculo de saldo pendiente acumulado entre entregas. Una orden solo llega a `CERRADA` al entregarse completa | No persiste nada |
| **TKT-035** | M | Caso de uso de entrada: valida, escribe el movimiento en el libro mayor y **deriva** el estado de la orden de compra. Detección de folio de remisión duplicado por proveedor | No asigna el estado de la orden a mano |
| **TKT-054** | S | **Reprogramación del faltante** (**PA-07**): nueva fecha comprometida con motivo obligatorio, registro en `reprogramacion_entrega`, la orden permanece `PARCIAL` y el presupuesto sigue comprometido. Rechazo de fecha anterior a la vigente y de cierre con saldo | No libera presupuesto: el material se sigue debiendo |
| **TKT-036** | S | Corrección de entradas mediante movimiento `AJUSTE` con motivo obligatorio, sin modificar ni borrar el movimiento original; recálculo del saldo pendiente | No permite editar ni borrar un movimiento |
| **TKT-037** | S | Endpoints de entrada, corrección, reprogramación, saldos pendientes por obra con antigüedad y contador de reprogramaciones, y existencia calculada desde el libro mayor | No expone ninguna columna de stock: no existe |
| **TKT-038** | M | Interfaz de recepción con captura de remisión, cantidades, saldo pendiente visible por renglón, fecha comprometida vigente e historial de movimientos y reprogramaciones. **Diferible sin conexión** sobre la cola de TKT-008 (`RNF-18`): el saldo se lee de caché con su antigüedad a la vista, y una entrada que al sincronizar exceda lo ordenado vuelve con el contrato de error de `RN-07` para que una persona decida | No incluye traspasos ni mermas. No evalúa `RN-07` en el cliente: el saldo cacheado orienta, no autoriza |

### HDU-006 · Semáforo de obra · 5 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-039** | M | Consulta del semáforo con sus cinco fuentes y los índices de [§15](03-modelo-datos.md#15-la-consulta-del-semáforo); plan de ejecución verificado con el volumen real de ~4,900 conceptos. La mano de obra se agrega **a nivel de obra**, no por partida (**PA-08**). El **avance físico se divide entre `alcance_destajo`**, no entre los m² de contrato de lo ya medido, y es `NULL` —no cero— mientras no haya nada validado, para que la desviación salga *no calculable* en vez de igual al ejercido | No prorratea mano de obra entre partidas: produciría precisión falsa. No usa `SUM(avance.m2_contrato)` como denominador: eso es el índice de desviación de volumen, no el avance |
| **TKT-040** | S | Endpoints de semáforo, desglose por partida y detalle hasta el movimiento de origen; metadato de qué fuentes de costo tienen datos y cuáles no; importes como cadena | No exporta a Excel ni a PDF |
| **TKT-041** | M | Interfaz del semáforo con código de color, aviso de cifra parcial cuando faltan fuentes, fila separada de mano de obra marcada como no imputada a partida, desglose navegable y distinción explícita entre "sin avance medido" y desviación cero | No incluye vista consolidada multi-obra |

> **TKT-039 se construye en tres entregas y hay que decirlo, porque en el sprint 4 no existen sus cinco fuentes.** `movimiento_inventario` nace en TKT-033 (sprint 5), y `avance`, `alcance_destajo`, `pago_destajo` e `imputacion_nomina_obra` en TKT-046 y TKT-049 (sprint 6). Escribir la consulta entera en el sprint 4 no compila.
>
> | Sprint | Qué añade a la consulta | Qué ve la dirección |
> |---|---|---|
> | **4** | `presupuestado` y `comprometido`, con sus índices | Cuánto se topó y cuánto está pedido sin recibir |
> | **5** | `ejercido_materiales`, tras TKT-033 | Lo anterior más el material ya recibido |
> | **6** | `ejercido_destajo`, `alcance`, `ejecutado` y la columna de desviación, tras TKT-046 y TKT-049 | El tablero completo |
>
> Cada entrega añade sus CTE y sus índices y **actualiza el metadato de fuentes disponibles** que TKT-040 expone y TKT-041 pinta, de modo que el escenario 6 de HDU-006 siga siendo cierto en cada escalón. La prueba de rendimiento de `RNF-15` es del sprint 7 (TKT-058) porque necesita la consulta entera. **La columna de desviación no existe hasta el sprint 6**: hasta entonces el escenario 9 la muestra como "sin avance medido".

### HDU-007 · Catálogo de personal y cuadrillas · 5 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-042** | S | Esquema del módulo personal: `rol_oficio`, `empleado`, `cuadrilla`, `cuadrilla_empleado`, `credito_empleado`, con las restricciones de saldo no negativo y coherencia de crédito liquidado —invariantes 3 y 4— y `CHECK (salario_semanal > 0)` —invariante 8—. **Siembra el catálogo de `rol_oficio`** del cliente: `PASTERO`, `TABLAROQUERO`, `AYUDANTE`, `OFICIAL`, `PINTOR`, `LIMPIEZA`, porque la tabla nace aquí y no en TKT-010 | No crea tablas de nómina ni de jornada |
| **TKT-043** | M | CRUD de empleados con rol de oficio obligatorio y salario positivo; baja lógica bloqueada si hay nóminas históricas; decisión explícita sobre créditos pendientes al dar de baja | No modela expediente laboral completo |
| **TKT-044** | S | Cuadrillas con encargado designado y asignación temporal de empleados (`desde`/`hasta`); un empleado no puede estar en dos cuadrillas a la vez; el cambio de cuadrilla conserva historial | No asigna cuadrillas a varias obras a la vez |
| **TKT-045** | S | Créditos activos con validación de que el descuento no excede el monto; suspensión y reactivación con motivo. Interfaz de catálogo con desplegable de roles | No calcula descuentos: eso es HDU-009 |

### HDU-008 · Avance de destajo · 8 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-046** | M | Esquema del módulo avance y configuración de etapas de destajo **por obra y tipo de partida** (**PA-08**), con precio de venta y de destajo separados. Incluye `alcance_destajo` con su `UNIQUE (area_id, etapa_destajo_id)` —invariante 22— y `pago_destajo_avance` con la clave foránea compuesta contra `avance (id, estado)` —invariante 11—. Una etapa sin tipo de partida se rechaza: sin ella su costo no podría imputarse en el tablero | No fija ningún precio en el código |
| **TKT-047** | L | **Precarga del alcance de destajo** desde la línea base al configurar las etapas, sumando los conceptos en `M2` por área y reportando cuántos quedan fuera por venir en `ML` o `PZA`; corrección del alcance reservada al Director de Proyectos con motivo y bitácora. Captura y validación en dos pasos con máquina de estados; `m2_contrato` se **copia** del alcance y es de solo lectura para el residente; prohibición de auto-validación; rechazo de cuadrillas ajenas a la obra y de duplicados por área/etapa/semana. El cálculo de pago lee el porcentaje de retención **de la obra** (**PA-02**) | No libera fondo de garantía ni aplica descuentos ad-hoc. No deja que quien mide fije el número contra el que se le mide |
| **TKT-048** | M | Interfaz de captura para el residente —con los m² de contrato visibles y bloqueados— y de validación para el Director de Proyectos, incluida la corrección del alcance; más el reporte de desviación de volumen por obra, nivel y cuadrilla. **Diferible sin conexión** sobre la cola de TKT-008 (`RNF-18`), con el alcance, las etapas y las cuadrillas de la obra precargados en caché para poder capturar sin red. La validación del Director de Proyectos **no** es diferible: ocurre en oficina | No genera estimaciones de cobro al cliente. No valida sin conexión |

### HDU-009 · Nómina semanal · 13 SP

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-049** | S | Esquema de nómina: `jornada`, `nomina_semana`, `nomina_renglon`, `imputacion_nomina_obra`, `descuento_nomina`, `pago_nomina`, `pago_nomina_detalle`. Incluye `UNIQUE (empleado_id, fecha)` —invariante 16—, el `CHECK` de semana viernes-jueves —invariante 18—, la restricción diferida de suma del desglose de pago —invariante 7— y **la restricción diferida de que `imputacion_nomina_obra` sume el neto del renglón** —invariante 17—, sin la cual el reparto entre obras puede cuadrar por obra y no cuadrar con lo pagado | No toca el esquema de personal (TKT-042) |
| **TKT-055** | M | **Registro de jornada diaria** (**PA-04**, `RN-23`): captura por empleado, fecha y **obra**, con fracciones de día y horas extra. Rechazo de jornada sin obra y de dos jornadas del mismo empleado el mismo día | No registra asistencia por horario ni control de entradas y salidas |
| **TKT-056** | M | **Imputación del costo entre obras**: reparte el neto de cada empleado en proporción a los días trabajados en cada obra, derivado de las jornadas. Un test cubre el caso de tres días en una obra y dos en otra | No reparte por partida: la nómina llega solo a obra (**PA-10**) |
| **TKT-050** | M | Cálculo en `dominio/`: días derivados de las jornadas, horas extra, amortización de uno o varios créditos con transición automática a liquidado, y protección contra neto negativo | No calcula impuestos ni prestaciones de ley |
| **TKT-051** | M | Pagos agrupados con desglose por trabajador, consulta inversa (dado un empleado, quién recibió su pago) y cierre de semana bloqueado si hay empleados sin forma de cobro | No timbra recibos ante el SAT |
| **TKT-052** | M | Interfaz de captura de jornadas y de nómina semanal, apertura de semana con corte en jueves, registro de depósitos. Advertencia cuando un empleado cambió de cuadrilla a mitad de semana | No permite modificar una nómina pagada |

### Transversal a HDU-008 y HDU-009 · RN-22

| Ticket | Talla | Qué hace | Non-goal principal |
|---|---|---|---|
| **TKT-053** | S | Exclusividad de modalidad de pago: tabla `modalidad_pago_semana` con `UNIQUE (obra_id, cuadrilla_id, semana)` —invariante 15—, regla en `dominio/` y contrato de error con la acción de cambiar de modalidad. **La tabla y la regla viven en `personal`**; `avance` reclama la modalidad por su interfaz de aplicación publicada, porque la arista `avance → personal` ya existe y la inversa rompería el grafo acíclico que `import-linter` verifica. Cubre el escenario 14 de HDU-008 y el 19 de HDU-009 | No decide automáticamente qué modalidad aplica: la reclama el primer pago de la semana |

> **Este ticket es uno solo a propósito.** Las dos historias describen la misma comprobación desde lados opuestos: HDU-008 impide generar destajo si ya hay nómina, HDU-009 impide lo contrario. Implementarlas por separado produciría dos comprobaciones que pueden divergir, y el fallo que evitan —contabilizar dos veces el mismo trabajo en el semáforo— es silencioso. Si las dos historias acabaran en sprints distintos, este ticket viaja con la primera y la segunda consume la tabla y la regla que deja creadas.

---

# Endurecimiento y operación

**No pertenecen a ninguna historia porque sirven a todas.** Son los dos tickets que cubren los requisitos no funcionales del [PRD §9](01-descripcion-producto.md#9-requisitos-no-funcionales): lo que tiene que ser cierto para que las 25 reglas de negocio signifiquen algo.

Están separados de la Épica 0 a propósito. La fundación entrega *la capacidad de entregar valor*; estos dos entregan *la capacidad de no perderlo*, y se descubren tarde en casi todos los proyectos porque nadie los pide.

---

### TKT-057 · Endurecimiento de la frontera HTTP

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-006 |

**Qué hace.** Cubre los requisitos de seguridad que TKT-006 declara fuera de su alcance: límite de intentos, protección contra peticiones cruzadas, cabeceras, archivos subidos y gestión de secretos.

**Criterios técnicos**
- [ ] Límite de intentos de acceso por origen y bloqueo **temporal** por cuenta tras `N` fallos, con cada intento asentado en `intento_acceso` (`RNF-04`)
- [ ] El bloqueo caduca solo: una cuenta bloqueada para siempre es una denegación de servicio que cualquiera puede provocar
- [ ] Token de doble envío verificado en **todo** método que muta estado, con test de rechazo sin token (`RNF-05`)
- [ ] Cabeceras `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options` y `Referrer-Policy` en todas las respuestas (`RNF-05`)
- [ ] Archivos subidos: límite de tamaño, validación de tipo, nombre generado por el sistema —el del usuario se guarda como dato, nunca como ruta— y `Content-Disposition: attachment` al servirlos (`RNF-06`)
- [ ] Configuración con `pydantic-settings`: **la aplicación no arranca** si falta un secreto obligatorio, y existe `.env.example` con las claves sin los valores (`RNF-07`)
- [ ] Los nueve requisitos verificables de [stack §6.6](06-stack-tecnologico.md#66-qué-se-comprueba-solo) tienen su test y fallan el pipeline

> **Este ticket viaja con TKT-006 o no sirve.** Una autenticación sin límite de intentos no es una autenticación a medias: es una invitación, y además convierte el inicio de sesión —que usa Argon2 a propósito— en el punto más barato de saturar de todo el sistema.

**Non-goals** — No implementa segundo factor, recuperación de contraseña ni inicio de sesión federado: siguen fuera del MVP. No implementa permisos por obra.

---

### TKT-058 · Respaldo, recuperación y observabilidad

| | |
|---|---|
| **Tipo** | Fundación · **Talla** M · **Depende de** TKT-005, TKT-009 · **Sprint 7** |

**Qué hace.** Deja el sistema en condiciones de ser desplegado de verdad: que se pueda restaurar lo que se pierda y que se pueda saber qué falló.

**Bloqueado por PA-12.** Los objetivos de `RNF-10` —1 hora de pérdida, 8 horas de restauración— siguen **(asumido)**. Fijan el precio de la base gestionada, así que la pregunta tiene que estar respondida **antes de contratarla**, no después. Es lo único de este ticket que depende de alguien ajeno al equipo.

**Criterios técnicos**
- [ ] **PA-12 respondida por Dirección General** y los objetivos de `RNF-10` actualizados con lo que diga, o confirmados
- [ ] PostgreSQL gestionado con **recuperación a un punto en el tiempo**, más volcado lógico diario retenido aparte del proveedor (`RNF-10`)
- [ ] El respaldo cubre también los archivos subidos: una base restaurada cuya bitácora apunta a evidencia inexistente está restaurada a medias
- [ ] **Un ensayo de restauración documentado**, sobre entorno limpio, con el tiempo medido y comparado contra el objetivo acordado (`RNF-11`)
- [ ] Agregación de errores no controlados con Sentry o equivalente autoalojado, consumiendo el identificador de correlación que TKT-005 ya emite (`RNF-14`)
- [ ] El registro técnico **no** escribe en `bitacora` ni al revés: son dos sitios porque son dos preguntas
- [ ] Prueba de rendimiento del semáforo con volumen sembrado que falla el pipeline por encima de 2 s (`RNF-15`)

> **Va en el sprint 7 y no antes por una razón y no por comodidad:** dos de sus criterios no se pueden ejecutar todavía. No se contrata una base gestionada para un sistema que aún no existe, y la prueba de rendimiento del semáforo necesita un semáforo con sus cinco fuentes, que no está completo hasta el sprint 6. Lo que sí podía adelantarse —el registro estructurado— se adelantó a TKT-005.

**Non-goals** — No implementa alta disponibilidad: `RNF-12` la descarta expresamente. No monta infraestructura de métricas ni trazado distribuido: hay un proceso. No emite el registro estructurado: eso es TKT-005.

---

## Plan de sprints

### Advertencia sobre la velocidad

**Las cifras de abajo son una hipótesis, no una medición.** No hay historial de este equipo en este proyecto, así que la velocidad base es un supuesto que el primer sprint calibra. El material del Módulo 4 es explícito: *"una estimación sin discusión vale menos que la falta de estimación"*, y *"no multipliques velocity por 2 porque el equipo ahora tiene Claude Code"*.

Supuesto de partida: **una persona con copiloto, ~20 SP por sprint de dos semanas**. Con el buffer del 30-40 % recomendado para equipos con IA en el flujo, se comprometen **13-14 SP**.

El buffer no es pesimismo: los PR generados por agente exigen revisión más cuidadosa, el volumen de código sube y con él los defectos, y las herramientas cambian cada pocas semanas.

### Sprints

| Sprint | Objetivo del sprint | Contenido | SP |
|---|---|---|---|
| **0** | *El esqueleto arranca, persiste y sabe rechazar.* | TKT-001 … TKT-005 | ~17 |
| **1** | *Un usuario autenticado entra, y la frontera HTTP ya está endurecida.* | TKT-006 … TKT-009, TKT-057 | ~19 ⚠ |
| **2** | *Se da de alta una obra y se congela su línea base desde el Excel real, con los catálogos del cliente y los errores reportados fila a fila.* | HDU-001 · TKT-011 … TKT-018, TKT-010 | ~15 |
| **3** | *Ninguna requisición sobregira una partida sin autorización explícita y registrada.* | HDU-002 + HDU-003 · TKT-019 … TKT-028 | 13 |
| **4** | *Lo pedido queda en firme frente a un proveedor y el tablero ya muestra presupuestado contra comprometido.* | HDU-004 + HDU-006 · TKT-029 … TKT-032, TKT-039 … TKT-041 | 10 |
| **5** | *El material recibido se refleja como costo ejercido y existe la base de personal para medir mano de obra.* | HDU-005 + HDU-007 · TKT-033 … TKT-038, TKT-054, TKT-042 … TKT-045 | 13 |
| **6** | *El semáforo incluye mano de obra y avance físico: la cifra deja de ser parcial, y ningún trabajo se contabiliza dos veces.* | HDU-008 + HDU-009 · TKT-046 … TKT-053, TKT-055, TKT-056 | **21** ⚠ |
| **7** | *El sistema se puede poner en manos del cliente: lo que se pierda se recupera, y lo que falle se puede averiguar.* | TKT-058 | ~3 |

> **El sprint 6 va sobrecargado y hay que decirlo.** Son 21 SP contra un compromiso de 13-14, y ya no es un exceso que se pueda absorber apretando. Dos causas: HDU-009 creció de 8 a 13 puntos al aparecer la jornada diaria (`RN-23`), y HDU-008 de 5 a 8 al aparecer la precarga del alcance de destajo — el denominador del avance físico, sin el cual la columna de desviación del semáforo no significa nada. Ninguna de las dos se puede separar de la otra sin más: `RN-22` es una sola comprobación que ambas ejercen desde lados opuestos.
>
> **La costura por donde parte, y a 21 SP hay que darla por tomada:** HDU-009 se divide en *registro de jornada diaria* (5 SP) y *cálculo de nómina con créditos y pagos agrupados* (8 SP). La primera mitad va al sprint 6 —es la que alimenta el semáforo— y la segunda al 7, que deja el 6 en 13 SP y el 7 en 11. Declarar la costura por adelantado evita que la decisión se tome a mitad de sprint y con prisa; declararla y no usarla, a 21 SP, sería no haberla declarado.

> **El sprint 1 se queda en ~19 SP y también hay que decirlo.** TKT-057 entra ahí porque no tiene sentido en ningún otro sitio: una autenticación sin límite de intentos no es una autenticación a medias, y dejarla para más tarde significa que el sistema pasa meses con el agujero abierto mientras nadie lo recuerda.
>
> **TKT-010 ya no está aquí, y no por holgura sino por dependencia.** Los datos semilla cargan `empresa`, `tipo_partida` e `insumo`, tablas que crea TKT-011 en el sprint 2. Sembrarlas antes fallaría por tabla inexistente.
>
> **La costura por donde parte si la velocidad no aguanta:** los tres componentes reutilizables de TKT-008 —pantalla de bloqueo, formulario de catálogo y captura de motivo— se separan del esqueleto y viajan con su primer consumidor: el formulario de catálogo con TKT-012, la pantalla de bloqueo con TKT-024 y la captura de motivo con TKT-028. El esqueleto, el inicio de sesión y el cliente de API se quedan, porque sin ellos el sprint 2 no arranca.

### El sprint 7 tiene holgura a propósito

**Son ~3 SP contra un compromiso de 13-14, y eso no es un error de planificación.** El sprint 7 es donde aterriza lo que el 6 no aguante: la costura declarada arriba —partir HDU-009 y mandar aquí el cálculo de nómina con créditos y pagos agrupados, 8 SP— cabe sin tocar nada y deja el sprint en 11 SP. Con el 6 en 21 SP, esa holgura ha dejado de ser un seguro y es el plan.

Lo que **no** es negociable es la condición de salida: no se pone el sistema en manos del cliente sin respaldo con recuperación a un punto en el tiempo, sin un ensayo de restauración hecho, y sin poder saber qué falló. Declararlo como sprint y no como buena intención evita la conversación de siempre, que es descubrir a la semana de arrancar que nadie se ocupó.

> **`PA-12` tiene que estar respondida antes de que empiece este sprint.** Es el único ticket del backlog que depende de una respuesta ajena al equipo, y llega tarde por naturaleza: nadie contrata infraestructura para un sistema que todavía no existe. Preguntar en el sprint 6 deja margen; preguntar el primer día del 7 convierte una decisión de presupuesto en una urgencia.

**El objetivo del sprint es la pieza más importante de esta tabla.** Si alguien pregunta qué se hizo, la respuesta es el objetivo, no la lista de tickets.

Los sprints 0 y 1 exceden el compromiso de 13-14 SP porque la fundación no se puede partir más sin dejar el sistema en un estado que no arranca. Es una excepción consciente, y el primer sprint dirá si el supuesto de velocidad aguanta.

### Por qué este orden

**La fundación primero, completa.** Repartir el contrato de error o la verificación de fronteras entre sprints posteriores significa que cada historia inventa su propio formato y su propia disciplina, y luego hay que unificarlos.

**La línea base antes que nada.** Sin referencia congelada, ninguna regla de presupuesto tiene contra qué evaluar. Es también la historia más arriesgada —lee Excel del mundo real, que viene roto— y conviene descubrir sus sorpresas en el sprint 2, no en el 6.

**El semáforo en el sprint 4, cuando solo tiene dos columnas con datos.** Aparece pronto y crece: en el 4 muestra presupuestado contra comprometido, en el 5 suma el ejercido de materiales, en el 6 la mano de obra. El escenario 5 de HDU-006 existe precisamente para que en cada etapa la pantalla avise de lo que aún no cubre. Un tablero que aparece al final es un tablero que se descubre mal enfocado al final.

**El personal en el sprint 5, junto a la entrada de material.** Es un bloque de CRUD sin reglas duras, así que equilibra bien un sprint donde la otra historia es la más pesada del módulo de almacén. Y llega justo antes de que destajo y nómina lo necesiten.

**Nómina y destajo al final, pero dentro.** Son *should-have*, pero sin ellas la cifra del semáforo es parcial: la mano de obra es entre el 59 % y el 100 % del costo directo (`RN-21`). Dejarlas fuera convertiría el entregable en una media verdad.

**El personal en el sprint 5 y no más tarde.** HDU-007 bloquea tanto a HDU-008 como a HDU-009, y ambas caen en el sprint 6. Adelantarlo deja margen si el catálogo revela sorpresas —por ejemplo, empleados que pertenecen a varias cuadrillas o créditos con condiciones que el cuestionario no describió.

---

# Pendiente de descomponer · captura sin conexión y evidencia documental

> **Estado: abierto desde el 2026-09-19, ampliado el 2026-10-01.** Dos revisiones dejaron la capa de decisión escrita y el **backlog no**:
>
> - `PA-13` confirmó que **en la obra no hay internet**. El requisito (`RNF-18`) y la decisión ([ADR-015](adr/20260919-captura-diferida-sin-conexion.md)) están escritos.
> - La revisión del **2026-10-01** encontró que el sistema exigía evidencia en varios sitios y no decía dónde guardarla. Nacen la capacidad `C8`, el requisito `RNF-19`, el `RNF-06` reescrito y [ADR-016](adr/20261001-almacenamiento-de-objetos.md).
>
> Las dos van juntas en un solo bloque y no en dos, porque **tocan las mismas historias y los mismos tickets**: HDU-005 y HDU-008 son a la vez los flujos diferibles y los que llevan evidencia, y la octava regla de ADR-016 —la evidencia no viaja en la cola— solo se puede implementar con las dos cosas delante.
>
> Se deja aquí a propósito y no en un documento aparte: es trabajo de la capa *Tasks*, y un pendiente que vive fuera del backlog es un pendiente que nadie mira. **No empezar la Épica 0 dando por hecho que esto está resuelto.**

## Qué falta

### 1 · Escenarios, unos quince

Ninguna historia describe hoy qué pasa sin conexión, y ninguna describe qué pasa al adjuntar un archivo. Faltan, con su historia destino:

| Historia | Escenarios de captura sin conexión | Escenarios de evidencia y archivos |
|---|---|---|
| **HDU-001** | — | El Excel se adjunta como `archivo` y la importación **no arranca** hasta que está `DISPONIBLE` · **rechazo**: se confirma un objeto cuyo hash no coincide con el declarado |
| **HDU-002** | Intento de levantar una requisición sin conexión → **rechazo explícito**. Es el escenario que impide que el modo sin conexión se lea como puerta trasera a `RN-03` | — |
| **HDU-005** | Captura de entrada sin señal, que queda en cola sin generar movimiento de inventario · sincronización correcta al recuperar señal · **conflicto**: entrada encolada que al subir excede lo ordenado, vuelve con el contrato de error de `RN-07` y detiene la cola · saldo leído de caché mostrando su antigüedad | Se adjunta la remisión del proveedor a la entrada (`F8.2`) · **rechazo**: se sube un ejecutable renombrado a `.pdf` y el sistema lo detecta por los bytes, no por la extensión |
| **HDU-008** | Captura de avance sin señal con alcance, etapas y cuadrillas precargados · **conflicto por duplicado**: dos dispositivos capturan la misma área, etapa, cuadrilla y semana · cola que **no sube** porque el rol del usuario se retiró mientras estaba en obra | Se adjuntan fotos a una medición desde el teléfono (`F8.1`) · **el avance sincroniza sin esperar a sus fotos** y estas suben después (octava regla de ADR-016) · **rechazo**: video que excede el límite de tamaño · anulación de un adjunto equivocado con motivo, **sin borrarlo** |

Cada uno necesita además su escenario de rechazo, según la regla de aceptación. Con ellos, el conteo pasa de 137 a **~152 escenarios**, y hay que actualizar la Definition of Done de las cuatro historias, el total del documento y las citas de 137 en el stack y en los ADR.

> **Un escenario que parece de interfaz y no lo es:** *"el avance se valida y todavía no tiene fotos"*. Es el coste declarado de la octava regla de [ADR-016](adr/20261001-almacenamiento-de-objetos.md), y **solo se puede escribir si `PA-14` está respondida**. Si la respuesta fuera *"sin foto no se valida"*, el escenario se invierte, nace una regla de negocio nueva y hay que reabrir la frontera de ADR-015.

### 2 · Tickets

| Trabajo | Dónde |
|---|---|
| **Partir TKT-008.** El esqueleto y el inicio de sesión se quedan en el sprint 1; el armazón sin conexión —service worker, caché persistida, cola en IndexedDB, sincronización FIFO, indicador de estado— sale a un ticket propio | Ticket nuevo, por numerar |
| **Endpoint de sincronización idempotente**, que hoy no existe en ningún ticket. El servidor tiene que aceptar la cola por los mismos casos de uso y devolver el contrato de error por elemento rechazado | Amplía TKT-037 (`almacen`) y los endpoints de `avance` de TKT-047 |
| **Diseño para pantalla de teléfono** de las dos pantallas de campo | Amplía TKT-038 y TKT-048, que ya lo declaran pero no lo estiman |
| **Módulo `archivos` con su esquema y su adaptador de objetos.** Tabla `archivo`, invariantes 23 a 26, puerto `AlmacenObjetos` con `boto3`, MinIO en el Compose y en testcontainers, emisión y caducidad de URL prefirmadas, validación de tipo por los bytes, confirmación por hash y barrido de `PENDIENTE` caducados (`RNF-06`, `RNF-19`) | **Ticket nuevo de fundación**, por numerar. Es prerrequisito de todo lo demás de este bloque |
| **Componente de subida y galería** reutilizable: cámara, compresión en el cliente, progreso, reintento, miniatura y visor | Ticket nuevo, hermano de los tres componentes compartidos de TKT-008 |
| **Adjuntar y consultar en cada punto**: evidencia de avance, remisión de entrada, documentos de obra y expediente (`F8.1`, `F8.2`, `F8.4`, `F8.5`) | Amplía TKT-038 (`almacen`), TKT-048 (`avance`) y TKT-012 (alta de obra) |
| **El Excel de importación entra por `archivo`** y deja de ser dos columnas sueltas | Amplía TKT-018, y toca la migración de TKT-011 |

### 3 · Puntos y sprints

| | Hoy | Después |
|---|---|---|
| Épica 0 | ~35 SP | **~45 SP** — el armazón sin conexión y el módulo `archivos` son fundación |
| HDU-001 | 13 SP | ~14 SP |
| HDU-005 | 8 SP | ~11 SP |
| HDU-008 | 8 SP | ~12 SP |
| Sprint 1 | ~19 SP ⚠ | **~24 SP** — insostenible contra un compromiso de 13-14 |

**Las dos costuras propuestas**, y conviene que no se decidan a mitad de sprint:

- **El armazón sin conexión** no se necesita hasta el sprint 5, cuando HDU-005 lo consume. Cabe en el sprint 3 o el 4, que son los que menos apretados van. Lo que **no** puede es llegar después de HDU-005: entonces la recepción se implementa dos veces.
- **El módulo `archivos`** tiene un consumidor más temprano de lo que parece: HDU-001 importa un Excel en el sprint 2. Dos salidas, y la segunda es la buena: adelantarlo al sprint 2 completo, o implementar primero solo el camino de subida y confirmación —que es lo que la importación necesita— y dejar galería, anulación y expediente para el sprint 5, con la evidencia de campo. **La segunda es preferible** porque reparte diez puntos entre dos sprints en lugar de amontonarlos en el que ya va a ~19.

## Lo que no hay que hacer

Seis cosas que ADR-015 y ADR-016 ya decidieron y que conviene no reabrir al descomponer:

- **No ampliar la lista de flujos diferibles.** Solo `avance` y `entrada_almacen`. La frontera es `RN-03` y no es negociable desde el backlog.
- **No evaluar reglas en el cliente.** El saldo cacheado orienta al usuario; no autoriza nada.
- **No resolver conflictos automáticamente.** Los decide una persona.
- **No meter las fotos en la cola de sincronización.** El avance sube sin esperarlas. Treinta megabytes en IndexedDB compiten con una cuota que el navegador desaloja sin avisar.
- **No servir los archivos desde el API.** Las rutas son `def`: cada descarga retendría un hilo del grupo. La URL prefirmada no es una optimización, es la decisión.
- **No interpretar el XML del CFDI.** Se guarda. Conciliarlo contra la orden de compra son reglas de negocio que el PRD no tiene, y que no se inventan desde un ticket.

## Cuatro preguntas al cliente antes de esa sesión

Ninguna bloquea el resto del proyecto, pero las cuatro cambian el diseño:

| | Pregunta | Por qué importa |
|---|---|---|
| **1** | ¿Cada quien usa su propio dispositivo, o hay uno compartido en obra? | Con dispositivo compartido, la cola atada al último usuario autenticado deja de ser suficiente y hacen falta colas por usuario |
| **2** | ¿Cuánto llega a estar un residente sin señal: unas horas, un día, una semana? | Dimensiona la cola y decide a partir de qué antigüedad la caché deja de mostrarse y pasa a avisar |
| **3** | **`PA-14`** · ¿Un avance se puede validar sin evidencia fotográfica? | Decide si existe una regla de negocio nueva y si la octava regla de ADR-016 se sostiene. Es la única de las cuatro que puede invertir un escenario ya escrito |
| **4** | **`PA-15`** · ¿Cuánto video hace falta, y cuánto tiempo hay que conservarlo? | Fija los límites de `RNF-06`, la resolución a la que se guarda y la política de ciclo de vida del bucket. Mientras no se responda, los límites del [PRD §10](01-descripcion-producto.md#10-supuestos-y-preguntas-abiertas) son supuestos míos |

### Seguimiento honesto de la velocidad

Desde el primer PR, cada uno se etiqueta por origen: `human`, `human+copilot`, `agent`, `agent+human-review`. La calidad se reporta segmentada por esa etiqueta.

Si los PR de agente acumulan tres veces más defectos que los humanos, la velocidad total está mintiendo y hay que reasignar esfuerzo a revisión. La velocidad sirve para planificar; **nunca** como indicador de rendimiento.
