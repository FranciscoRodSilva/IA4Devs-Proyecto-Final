# Spec · TKT-003 · PostgreSQL, migraciones y esquema de identidad

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

CIMENTA no tiene hoy base de datos. El repositorio no contiene ningún `docker-compose`, ningún directorio de migraciones ni ninguna dependencia de persistencia: en `backend/pyproject.toml` la lista `dependencies` está vacía y el grupo de desarrollo solo trae `import-linter`, `mypy` y `ruff`. El módulo `identidad` existe desde [TKT-002](../tkt-002/_index.md) como esqueleto con su `__init__.py` y su `interfaz.py`, sin una sola tabla.

Este ticket de fundación entrega la capacidad de persistir y de **proteger lo que se persiste**. Levanta PostgreSQL para desarrollo, configura el sistema de migraciones, crea las cinco tablas de identidad y establece los **tres roles de PostgreSQL** del [RNF-09](../../../docs/01-descripcion-producto.md#9-requisitos-no-funcionales): migración (propietario), aplicación y solo lectura. Dos invariantes del modelo de datos son permisos y no restricciones declarativas, y por eso solo existen si los roles existen: el 20 (el registro de intentos de acceso no se altera desde la aplicación) y el 21 (las consultas de analítica no pueden escribir). La garantía de que `analitica` solo lee, que TKT-002 dejó expresamente a este ticket, se verifica aquí en tiempo de ejecución.

Estado de partida, criterio por criterio:

| Criterio del ticket | Estado de partida |
|---|---|
| PostgreSQL en local, con datos persistentes | No existe `docker-compose`; `docker compose up -d db` no funciona |
| Sistema de migraciones con migración inicial reversible | No existe; `uv run alembic upgrade head` no funciona |
| Cinco tablas de identidad según [modelo de datos §10](../../../docs/03-modelo-datos.md#10-identidad-y-auditoría) | No existe ninguna tabla |
| Seis roles del PRD como datos de arranque | No existen |
| Convenciones del esquema (UUID, auditoría, `TIMESTAMPTZ`) | Sin aplicar |
| Tres roles de PostgreSQL creados en la migración, con `ALTER DEFAULT PRIVILEGES` | No existen |
| Invariante 20 (`intento_acceso` sin `UPDATE` ni `DELETE` para la aplicación) | No existe la tabla |
| Invariante 21 (rol de solo lectura) | No existe el rol |
| `lock_timeout` y `statement_timeout` en el rol de aplicación (`RNF-16`) | No existen |
| Tests contra PostgreSQL con `alembic upgrade head` y rol de aplicación | No hay pytest, ni testcontainers, ni un solo test |

TKT-001 y TKT-002 dejaron deuda para este ticket, y esta spec la recoge: Alembic debe vivir **fuera** de `backend/cimenta/`, porque el contrato `esqueleto-modulos` de import-linter es exhaustivo sobre ese paquete y rechazaría un directorio ajeno a los diez módulos; el `.env.example` debe ganar valores de desarrollo evidentes, porque hoy solo tiene comentarios y la convención de Docker lo pide; y las marcas «desde TKT-003» de `CLAUDE.md` y de `docs/arranque-local.md` deben retirarse.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, persona o agente.

**Como** persona o agente que desarrolla CIMENTA
**quiero** una base de datos local reproducible, con su esquema de identidad migrado y con tres roles de privilegio mínimo
**para** que los tickets de negocio persistan sobre un esquema versionado y para que dos invariantes que son permisos —20 y 21— existan de verdad y no solo en el papel.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** PostgreSQL disponible en local mediante contenedor, con el servicio `db` y datos persistentes entre arranques |
| | **M2.** Sistema de migraciones configurado, con una migración inicial aplicable con `alembic upgrade head` y reversible |
| | **M3.** Tablas `usuario`, `rol`, `usuario_rol`, `sesion` e `intento_acceso` según el modelo de datos §10, con identificadores UUID, `TIMESTAMPTZ` y las restricciones de unicidad y de clave foránea. Por decisión del usuario: `usuario_rol` lleva además unicidad sobre (`usuario_id`, `rol_id`), y solo `usuario` y `usuario_rol` llevan columnas de auditoría |
| | **M4.** Los seis roles de negocio del PRD cargados como datos de arranque |
| | **M5.** Tres roles de PostgreSQL creados **en la migración**, no a mano: migración (propietario), aplicación y solo lectura, con `ALTER DEFAULT PRIVILEGES` para que toda tabla nueva nazca con los permisos por omisión de cada rol |
| | **M6.** El rol de aplicación no tiene `UPDATE` ni `DELETE` sobre `intento_acceso` (invariante 20) |
| | **M7.** El rol de solo lectura no tiene más que `SELECT` (invariante 21) |
| | **M8.** `lock_timeout` y `statement_timeout` fijados en el rol de aplicación, de modo que apliquen aunque una ruta nueva no los pida (`RNF-16`) |
| | **M9.** Los tests corren contra PostgreSQL real, construyen el esquema con `alembic upgrade head` y se conectan con el rol de aplicación |
| | **M10.** Consecuencia documental de M1 a M9, que no amplía el alcance: `.env.example` con valores de desarrollo evidentes para la base de datos, y retirada de las marcas «desde TKT-003» de `CLAUDE.md` y de `docs/arranque-local.md` |
| **Should** | **S1.** Corregir el modelo de datos §10 y §13 para que reflejen las dos decisiones del usuario (unicidad de `usuario_rol` y alcance de las columnas de auditoría), de modo que el esquema y el documento no diverjan |
| **Could** | — |
| **Won't** | Tablas de negocio · tabla `bitacora` y su disparador o revocación (TKT-007) · autenticación, hash de contraseña y uso de `sesion` (TKT-006) · límite de intentos y escritura en `intento_acceso` (TKT-057) · modelos ORM, repositorios y casos de uso de `identidad` · traducción de `lock_timeout` a `CONCURRENCIA` (TKT-005) · pruebas de permisos sobre `explosion_presupuesto` y `linea_base_concepto` (TKT-011, que crea esas tablas) · purga de `sesion` e `intento_acceso` · CI y ejecución de la suite en el pipeline (TKT-009) · MinIO (TKT-059) |

## Non-goals

- No crea ninguna tabla de negocio: cada módulo trae las suyas. Tampoco la tabla `bitacora`, aunque la nota del ticket cite el invariante 10: lo crea TKT-007, que es quien lo revoca y lo prueba.
- No implementa autenticación. `sesion` e `intento_acceso` existen como tablas; nadie las escribe todavía, ni hay endpoint, ni se calcula ningún hash.
- No escribe modelos ORM, repositorios ni casos de uso de `identidad` `(asumido)`. Las tablas se verifican contra el catálogo de PostgreSQL y con SQL directo. Si el diseño demuestra que necesita un modelo declarativo, lo justifica en su escalera de decisión.
- No traduce el vencimiento de un bloqueo al contrato de error: ese `CONCURRENCIA` es de TKT-005 y de su uso concreto en TKT-021. Aquí solo se demuestra que PostgreSQL corta la espera.
- No prueba permisos de tablas que otros tickets crean. Sí deja funcionando los `ALTER DEFAULT PRIVILEGES` de los que esas tablas dependerán.
- No purga `sesion` ni `intento_acceso`. El modelo de datos dice que las filas caducadas se purgan por antigüedad, pero no dice con qué rol, y el rol de aplicación no tiene `DELETE` sobre `intento_acceso`.
- No configura CI: eso es TKT-009. La suite corre en local con `uv run pytest`.
- No cambia el contrato de fronteras de TKT-002. Si el diseño necesita ajustarlo, lo declara.

## Reglas de negocio implicadas

Ninguna regla `RN-xx` se implementa en este ticket: no hay lógica de negocio. Sostiene requisitos no funcionales, decisiones de arquitectura y dos invariantes del modelo de datos.

| Referencia | Qué exige | Dónde está |
|---|---|---|
| `RNF-09` | La base de datos aplica privilegio mínimo con tres roles: migración, aplicación y solo lectura | [PRD §9](../../../docs/01-descripcion-producto.md#9-requisitos-no-funcionales) |
| `RNF-16` | Ninguna espera de bloqueo es indefinida: toda transacción tiene tiempo máximo de espera y de ejecución | PRD §9 |
| `RNF-04` | Los intentos de acceso se registran y están limitados. Respalda el invariante 20: la aplicación no puede borrar su propio rastro | PRD §9 |
| `RNF-07` | Ningún secreto vive en el repositorio ni en la imagen. Condiciona cómo se fijan las contraseñas de los roles | PRD §9 |
| `RNF-01` | La sesión tiene estado y es revocable. Este ticket solo crea la tabla `sesion` | PRD §9 |
| Invariante 20 | La aplicación tiene `INSERT` y `SELECT` sobre `intento_acceso`, no `UPDATE` ni `DELETE` | [modelo de datos §13](../../../docs/03-modelo-datos.md#13-invariantes-en-base-de-datos) |
| Invariante 21 | Rol de PostgreSQL con solo `SELECT`, con el que se conecta `analitica` | modelo de datos §13 |
| Invariantes 10, 14 y 30 | Los hacen cumplir permisos o disparadores en tablas de otros tickets. Dependen de los `ALTER DEFAULT PRIVILEGES` que fija este | modelo de datos §13 |
| [ADR-002](../../../docs/adr/) y `CLAUDE.md` | Los tests no usan SQLite, construyen el esquema con `alembic upgrade head` y se conectan con el rol de aplicación | [`CLAUDE.md`](../../../CLAUDE.md), «Qué no hacer» |
| [ADR-014](../../../docs/adr/20260919-sesion-con-estado.md) | La sesión vive en la tabla `sesion` y se cierra escribiendo `revocada_en`, nunca borrando la fila | `docs/adr/` |

## Invariantes que deben sobrevivir al cambio

El ticket crea tablas y roles nuevos, así que los invariantes 20 y 21 nacen con él y tienen su criterio propio (`CA-6` y `CA-7`). Sí modifica archivos que ya funcionan: `backend/pyproject.toml` y `backend/uv.lock`, `.env.example`, `CLAUDE.md`, `docs/arranque-local.md` y, por `S1`, `docs/03-modelo-datos.md`. Estas son las garantías de TKT-001 y TKT-002 que deben sobrevivir:

| Garantía existente | Qué protege | Criterio de regresión |
|---|---|---|
| Ruff y mypy terminan en verde sobre `backend/` con sus reglas actuales | Que la base de calidad no se rompa al añadir código de migraciones y de tests | `CA-R1` |
| `uv sync --locked` sigue funcionando con el archivo de bloqueo actualizado | Instalación reproducible y versiones exactas (`RNF-08`) | `CA-R2` |
| `uv run lint-imports` termina en verde con sus 14 contratos | Las fronteras de TKT-002, entre ellas `esqueleto-modulos`, que es exhaustivo sobre `cimenta`, y el dominio sin SQLAlchemy | `CA-R3` |
| Las marcas «desde TKT-xxx» de otros tickets siguen intactas | Que `uv run fastapi dev` siga diciendo que todavía no funciona | `CA-R4` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` siguen en verde | Enlaces, anclas e identificadores de la documentación | `CA-R5` |
| Los archivos nuevos no llevan BOM ni finales de línea fuera de LF | La comprobación de codificación de TKT-001 | `CA-R6` |

## Criterios de aceptación

Gherkin, en español. Como no hay reglas de negocio, el «rechazo» de cada criterio es la demostración de que la garantía **falla** ante su violación: un permiso que nunca se ha visto negado no está verificado. Donde el rechazo es de permisos, el contrato observable es el código de error de PostgreSQL (`42501`, `insufficient_privilege`); el contrato de error de la API no existe todavía y llega con TKT-005.

### CA-1 `[M]` · PostgreSQL local con datos persistentes · M1

```gherkin
Escenario: La base arranca y acepta conexiones
  Dado el repositorio con el ticket aplicado y un ".env" copiado de ".env.example"
  Cuando se ejecuta "docker compose up -d db" desde la raíz
  Entonces el servicio "db" queda sano y acepta una conexión con el rol de migración

Escenario: Los datos sobreviven a un reinicio
  Dado la base en marcha con una fila escrita en una tabla desechable
  Cuando se ejecutan "docker compose down" (sin "-v") y después "docker compose up -d db"
  Entonces la fila sigue ahí

Escenario: Rechazo — sin variables obligatorias no hay contraseña por omisión
  Dado un entorno sin ".env" y sin las variables de base de datos definidas
  Cuando se ejecuta "docker compose up -d db"
  Entonces el comando termina con código distinto de 0
  Y el error nombra la variable que falta
  Y no queda ningún contenedor "db" arrancado con una credencial por omisión
```

El tercer escenario materializa `RNF-07` y es `(asumido)`: que Compose no tenga valor por omisión para la contraseña. Ver `PA-T9`.

### CA-2 `[M]` · Migración inicial aplicable y reversible · M2

```gherkin
Escenario: La migración inicial se aplica sobre una base vacía
  Dado una base PostgreSQL sin ninguna tabla de CIMENTA
  Cuando se ejecuta "uv run --env-file ../.env alembic upgrade head" desde "backend/"
  Entonces termina con código 0
  Y existen las cinco tablas de identidad y los tres roles de PostgreSQL

Escenario: La migración es reversible y reaplicable sin residuos
  Dado la base con la migración aplicada
  Cuando se ejecutan "alembic downgrade base" y después "alembic upgrade head"
  Entonces ambos terminan con código 0
  Y el esquema resultante es idéntico al de la primera aplicación

Escenario: Aplicar de nuevo no cambia nada
  Dado la base ya en "head"
  Cuando se ejecuta "alembic upgrade head"
  Entonces termina con código 0 y no modifica ninguna tabla ni dato

Escenario: Rechazo — la aplicación no puede migrar
  Dado una conexión con el rol de aplicación
  Cuando intenta crear una tabla, alterar una existente o eliminar una de identidad
  Entonces PostgreSQL responde "42501" en cada intento
  Y el esquema queda sin cambios
```

Los roles de PostgreSQL pertenecen al clúster, no a la base de datos. Qué hace `downgrade` con ellos, y cómo se comporta `upgrade` si ya existen por otra base del mismo clúster, es decisión del diseño (`PA-T8`); el criterio exige el resultado observable, no el mecanismo.

### CA-3 `[M]` · Las cinco tablas de identidad con sus restricciones · M3

```gherkin
Escenario: Las tablas tienen las columnas y los tipos del modelo de datos
  Dado la base en "head"
  Cuando se consulta el catálogo para "usuario", "rol", "usuario_rol", "sesion" e "intento_acceso"
  Entonces cada tabla tiene exactamente las columnas del modelo de datos §10
  Y toda clave primaria es de tipo "uuid"
  Y toda columna de fecha y hora es de tipo "timestamp with time zone"

Escenario: Solo usuario y usuario_rol llevan columnas de auditoría
  Dado la base en "head"
  Cuando se consultan las columnas de las cinco tablas
  Entonces "usuario" y "usuario_rol" tienen "creado_en", "creado_por_id", "actualizado_en" y "actualizado_por_id"
  Y "rol", "sesion" e "intento_acceso" no las tienen
  Y "creado_por_id" y "actualizado_por_id" admiten nulo, porque ningún usuario existía al sembrar los datos

Escenario: Un intento fallido puede registrar un correo que no existe
  Dado la base en "head"
  Cuando se inserta en "intento_acceso" una fila con "usuario_id" nulo y un correo cualquiera tal como se escribió
  Entonces la inserción se acepta

Escenario: Rechazo — correo de usuario duplicado
  Dado un usuario con el correo "ana@cimenta.test"
  Cuando se inserta otro usuario con el mismo correo
  Entonces PostgreSQL responde "23505" y nombra la restricción única de "usuario"

Escenario: Rechazo — clave de rol duplicada
  Dado la base con los seis roles sembrados
  Cuando se inserta otro rol con la clave "RESIDENTE"
  Entonces PostgreSQL responde "23505" y nombra la restricción única de "rol"

Escenario: Rechazo — mismo rol asignado dos veces al mismo usuario
  Dado un usuario con el rol "COMPRAS" ya asignado
  Cuando se inserta de nuevo la misma pareja en "usuario_rol"
  Entonces PostgreSQL responde "23505" y nombra la restricción única de "usuario_rol"

Escenario: Rechazo — claves foráneas que apuntan a la nada
  Dado la base en "head"
  Cuando se inserta en "usuario_rol" un "rol_id" inexistente, o en "sesion" un "usuario_id" inexistente
  Entonces PostgreSQL responde "23503" y nombra la restricción de clave foránea
```

Las restricciones llevan nombre, según la convención de esquema. Cómo se llaman es del diseño.

### CA-4 `[M]` · Los seis roles de negocio como datos de arranque · M4

```gherkin
Escenario: Los seis roles del PRD están sembrados
  Dado la base en "head"
  Cuando se leen las filas de "rol"
  Entonces hay exactamente seis, con las claves DIRECCION_GENERAL, DIRECTOR_PROYECTOS, RESIDENTE, COMPRAS, ALMACEN y ADMINISTRACION
  Y cada una tiene su nombre legible del PRD §4

Escenario: Rechazo — la siembra no duplica ni inventa roles
  Dado la base con la migración aplicada, revertida y aplicada de nuevo
  Cuando se leen las filas de "rol"
  Entonces siguen siendo exactamente seis
  Y ninguna clave fuera de esas seis aparece
```

### CA-5 `[M]` · Tres roles de PostgreSQL creados por la migración · M5

```gherkin
Escenario: La migración crea los tres roles con privilegio mínimo
  Dado la base en "head"
  Cuando se consultan los roles en el catálogo
  Entonces existen el rol de migración, el de aplicación y el de solo lectura
  Y el rol de migración es propietario de las cinco tablas de identidad
  Y los roles de aplicación y de solo lectura no son superusuario ni pueden crear bases, roles ni objetos

Escenario: Una tabla creada después nace con los permisos por omisión
  Dado la base en "head"
  Cuando el rol de migración crea una tabla desechable "prueba_permisos"
  Entonces el rol de aplicación tiene sobre ella "SELECT", "INSERT", "UPDATE" y "DELETE"
  Y el rol de solo lectura tiene "SELECT"

Escenario: Rechazo — la aplicación no tiene más privilegios que los de la arquitectura
  Dado la tabla desechable "prueba_permisos" y las cinco tablas de identidad
  Cuando se consultan los privilegios del rol de aplicación
  Entonces no tiene "TRUNCATE", "REFERENCES" ni "TRIGGER" sobre ninguna
  Y no tiene "CREATE" sobre el esquema
```

El segundo escenario existe porque `ALTER DEFAULT PRIVILEGES` solo afecta a los objetos que crea el rol sobre el que se declara: si las migraciones futuras corren con otro rol, sus tablas nacerían sin permisos o con permisos ajenos, y las pruebas de las tablas de identidad no lo notarían. Los permisos exactos son los de [arquitectura §7.6](../../../docs/02-arquitectura.md).

### CA-6 `[M]` · Rechazo · La aplicación no altera `intento_acceso` · M6 · invariante 20

```gherkin
Escenario: La aplicación puede registrar y leer intentos de acceso
  Dado una conexión con el rol de aplicación
  Cuando inserta un intento de acceso y lo lee
  Entonces ambas operaciones se aceptan

Escenario: Rechazo — la aplicación no puede modificar un intento
  Dado un intento de acceso registrado
  Cuando el rol de aplicación ejecuta "UPDATE" sobre "intento_acceso"
  Entonces PostgreSQL responde "42501"
  Y la fila conserva sus valores originales

Escenario: Rechazo — la aplicación no puede borrar un intento
  Dado un intento de acceso registrado
  Cuando el rol de aplicación ejecuta "DELETE" sobre "intento_acceso"
  Entonces PostgreSQL responde "42501"
  Y la fila sigue existiendo

Escenario: Rechazo — la aplicación no puede vaciar la tabla
  Dado intentos de acceso registrados
  Cuando el rol de aplicación ejecuta "TRUNCATE" sobre "intento_acceso"
  Entonces PostgreSQL responde "42501"
  Y las filas siguen existiendo
```

`TRUNCATE` es un privilegio aparte del `DELETE`: sin el tercer escenario de rechazo, la aplicación podría borrar su propio rastro sin infringir la letra del invariante.

### CA-7 `[M]` · Rechazo · El rol de solo lectura solo lee · M7 · invariante 21

```gherkin
Escenario: El rol de solo lectura puede consultar
  Dado una conexión con el rol de solo lectura
  Cuando ejecuta "SELECT" sobre "rol" y sobre una tabla creada después de la migración
  Entonces ambas consultas se aceptan

Escenario: Rechazo — el rol de solo lectura no escribe
  Dado una conexión con el rol de solo lectura
  Cuando ejecuta "INSERT", "UPDATE", "DELETE" y "TRUNCATE" sobre "rol"
  Entonces PostgreSQL responde "42501" en cada uno
  Y el contenido de "rol" no cambia

Escenario: Rechazo — el rol de solo lectura no crea objetos
  Dado una conexión con el rol de solo lectura
  Cuando intenta crear una tabla
  Entonces PostgreSQL responde "42501"
```

### CA-8 `[M]` · Ninguna espera es indefinida · M8 · `RNF-16`

```gherkin
Escenario: Los tiempos máximos están fijados en el rol, no en la sesión
  Dado una conexión nueva con el rol de aplicación, sin ningún "SET" previo
  Cuando se consultan "lock_timeout" y "statement_timeout"
  Entonces ambos tienen un valor mayor que cero

Escenario: Rechazo — una espera de bloqueo se corta
  Dado una transacción que mantiene bloqueada una fila de una tabla desechable creada con el rol de migración
  Cuando otra conexión del rol de aplicación intenta bloquear esa fila con "SELECT … FOR UPDATE"
  Entonces PostgreSQL cancela la espera con "55P03" dentro de "lock_timeout"
  Y no queda esperando indefinidamente

Escenario: Rechazo — una consulta demasiado larga se cancela
  Dado una conexión nueva con el rol de aplicación
  Cuando ejecuta una consulta que dura más que "statement_timeout"
  Entonces PostgreSQL la cancela con "57014"
```

Los valores concretos no están documentados en ningún sitio: los propone el diseño y los aprueba el usuario (`PA-T5`).

### CA-9 `[M]` · Los tests no pueden verde por probar con el propietario · M9

```gherkin
Escenario: La suite construye el esquema con Alembic y usa el rol de aplicación
  Dado la suite del backend y PostgreSQL real levantado por testcontainers
  Cuando se ejecuta "uv run pytest" desde "backend/"
  Entonces termina con código 0
  Y el esquema de las pruebas lo construyó "alembic upgrade head", no "create_all()"
  Y la conexión que usan las pruebas de permisos corresponde al rol de aplicación

Escenario: Rechazo — probar con el propietario hace fallar la suite
  Dado la suite con su conexión de pruebas cambiada al rol propietario
  Cuando se ejecuta "uv run pytest"
  Entonces termina con código distinto de 0
  Y el fallo nombra que la conexión no es la del rol de aplicación

Escenario: Rechazo — la suite no corre contra SQLite
  Dado una variable de conexión que apunta a un archivo SQLite
  Cuando se ejecuta "uv run pytest"
  Entonces termina con código distinto de 0
  Y el fallo indica que solo se admite PostgreSQL
```

El segundo escenario es el que impide que los invariantes 20 y 21 queden en verde sin verificar nada: con el propietario, el `UPDATE` funciona y la prueba que lo intenta no tendría nada que negar.

### CA-10 `[M]` · Los roles no llevan secreto en el repositorio · M5 · `RNF-07`

```gherkin
Escenario: La migración crea los roles sin contraseña y se fija por entorno
  Dado la migración inicial y un ".env" con las contraseñas de desarrollo
  Cuando se aplica la migración y después se fijan las contraseñas desde el entorno
  Entonces los roles de aplicación y de solo lectura pueden iniciar sesión con su contraseña

Escenario: Rechazo — antes de fijar la contraseña no se puede entrar
  Dado la migración aplicada y las contraseñas todavía sin fijar
  Cuando se intenta conectar por la red con el rol de aplicación o con el de solo lectura, con contraseña vacía o cualquiera
  Entonces PostgreSQL rechaza la autenticación

Escenario: Rechazo — ningún secreto en el repositorio
  Dado los archivos del ticket (migración, Compose, ".env.example", pruebas)
  Cuando se buscan contraseñas literales de los roles de aplicación y de solo lectura
  Entonces ninguna aparece fuera de valores de desarrollo evidentes de ".env.example"
```

Que la migración cree los roles sin contraseña y que esta se fije por entorno es decisión del usuario del 2026-10-17. Quién ejecuta ese paso y cómo (script de arranque local, inicialización del contenedor) es del diseño; que en producción lo hace el operador es `(asumido)` (`PA-T3`).

### CA-11 `[M]` · La documentación y el entorno quedan al día · M10

```gherkin
Escenario: El ejemplo de entorno trae valores de desarrollo evidentes
  Dado ".env.example"
  Cuando se lee la sección de base de datos
  Entonces define cada variable que necesitan Compose, Alembic y las pruebas
  Y los valores son de desarrollo evidente, no secretos reales

Escenario: Las marcas de disponibilidad se retiran
  Dado "CLAUDE.md" y "docs/arranque-local.md"
  Cuando se leen las líneas de "docker compose up -d db", "uv run --env-file ../.env alembic upgrade head" y "uv run pytest"
  Entonces ya no llevan «desde TKT-003»
  Y los comandos funcionan tal como están escritos

Escenario: Rechazo — las marcas de otros tickets no se tocan
  Dado "CLAUDE.md"
  Cuando se leen las líneas de "uv run fastapi dev" y de "docker compose up -d minio"
  Entonces siguen marcadas «desde TKT-005» y «desde TKT-059»
```

### CA-R1 `[M]` · Regresión · La base de calidad sigue en verde

```gherkin
Escenario: Ruff y mypy terminan en verde
  Dado el ticket aplicado
  Cuando se ejecutan "uv run ruff format --check .", "uv run ruff check ." y "uv run mypy ." desde "backend/"
  Entonces los tres terminan con código 0
```

### CA-R2 `[M]` · Regresión · El archivo de bloqueo sigue reproducible

```gherkin
Escenario: uv sync --locked funciona con el bloqueo nuevo
  Dado "backend/uv.lock" actualizado con las dependencias de persistencia y de pruebas
  Cuando se ejecuta "uv sync --locked" desde "backend/"
  Entonces termina con código 0
  Y las dependencias nuevas respecto a TKT-002, además de sus transitivas, son solo las necesarias para migrar, conectar y probar contra PostgreSQL
```

### CA-R3 `[M]` · Regresión · Las fronteras de TKT-002 siguen en verde

```gherkin
Escenario: lint-imports termina en verde con el código nuevo
  Dado el ticket aplicado, con las migraciones y las pruebas fuera de "backend/cimenta/"
  Cuando se ejecuta "uv run lint-imports" desde "backend/"
  Entonces termina con código 0
  Y ningún "dominio/" importa "sqlalchemy"

Escenario: Rechazo — un directorio ajeno dentro de "cimenta" sigue rechazándose
  Dado un directorio "migraciones" colocado dentro de "backend/cimenta/"
  Cuando se ejecuta "uv run lint-imports"
  Entonces termina con código distinto de 0
  Y el informe nombra el paquete que no está entre los diez módulos
```

### CA-R4 `[M]` · Regresión · Las marcas de otros tickets no se tocan

```gherkin
Escenario: fastapi dev conserva su marca
  Dado "CLAUDE.md" y "docs/arranque-local.md"
  Cuando se lee la línea de "uv run fastapi dev"
  Entonces sigue marcada «desde TKT-005» y el comando sigue sin funcionar
```

### CA-R5 `[M]` · Regresión · La documentación sigue consistente

```gherkin
Escenario: Los verificadores de documentación terminan en verde
  Dado los cambios del ticket aplicados
  Cuando se ejecutan "python tools/verificar_docs.py" y "python tools/extraer_mermaid.py"
  Entonces ambos terminan con código 0
```

### CA-R6 `[M]` · Regresión · La codificación se conserva

```gherkin
Escenario: Los archivos nuevos cumplen la regla de codificación
  Dado los archivos creados o modificados por el ticket
  Cuando se ejecuta "python tools/verificar_docs.py"
  Entonces no aparece ningún problema "Codificación ·"
  Y el hook ".claude/hooks/recordar-caveman.ps1" sigue empezando por EF BB BF
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-002, archivado. Bloquea a TKT-006, TKT-007, TKT-011, TKT-059 y a todo el que persista |
| **N** | Describe el qué, no impone el cómo | Sí | Fija las tablas, los roles, los permisos y el contrato observable (`42501`, `23505`, `55P03`). No fija nombres de base, de roles ni de variables, ni la versión de PostgreSQL, ni dónde viven Compose y Alembic |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Pasa con reservas | El valor es para quien desarrolla y para el RNF-09; ningún rol del PRD §4 lo usa. Es esperable en una fundación |
| **E** | Estimable sin investigar antes | Pasa con reservas | Talla M. Dos incertidumbres técnicas: cómo se comporta un `downgrade` con roles que son del clúster y no de la base, y qué ejecuta el paso que fija las contraseñas. Ninguna cambia el alcance, y el diseño las resuelve |
| **S** | Cabe en una sesión sin romper contexto | Pasa con reservas | Es el ticket de fundación más ancho: Compose, Alembic, cinco tablas, tres roles, tiempos máximos y el armazón de pruebas. Un solo asunto —la persistencia protegida—, pero con muchas filas de diseño |
| **T** | Sus criterios se pueden ejecutar | Sí | Cada criterio es un comando o una consulta al catálogo con código de error o resultado observable |

Tres reservas (V, E y S), ningún fallo. La spec pasa.

## Definition of Done

La del tipo de ticket según [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo): ticket de fundación sin criterios de negocio, asimilado a *Funcionalidad* para el cierre.

- [ ] Todos los criterios `CA-1` a `CA-11` y `CA-R1` a `CA-R6` verificados, cada uno con su comando y su resultado en `impl.md`
- [ ] La demostración de rechazo de cada garantía de permisos (`CA-2`, `CA-5`, `CA-6`, `CA-7`, `CA-8`, `CA-9`, `CA-10`) ejecutada y registrada, no solo el camino verde
- [ ] Mutación de cada garantía: conceder un privilegio de más, quitar un `ALTER DEFAULT PRIVILEGES`, quitar un tiempo máximo o cambiar la conexión de pruebas al propietario, y confirmar que su prueba de rechazo se pone en rojo
- [ ] Los tests corren con el rol de aplicación contra PostgreSQL real y el esquema sale de `alembic upgrade head`
- [ ] Marcas de `CLAUDE.md` y `docs/arranque-local.md` actualizadas en el mismo cambio, y `.env.example` con valores de desarrollo evidentes
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde
- [ ] PR enlazado al ticket, con su origen (`agent` o `agent+human-review`) y revisado por al menos una persona

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | Solo `usuario` y `usuario_rol` llevan columnas de auditoría, con `creado_por_id` y `actualizado_por_id` nulos permitidos; `rol`, `sesion` e `intento_acceso` no | El ticket pide «columnas de auditoría», el modelo de datos §2 las limita a tablas transaccionales y §10 no las muestra: el esquema divergiría del documento | Resuelto por el usuario, 2026-10-17. `S1` corrige el modelo |
| PA-T2 | `usuario_rol` lleva unicidad sobre (`usuario_id`, `rol_id`), que el modelo §10 no declara | Sin ella, un usuario podría tener el mismo rol dos veces | Resuelto por el usuario, 2026-10-17. Hallazgo del modelo de datos; `S1` lo corrige |
| PA-T3 | La migración crea los roles de aplicación y de solo lectura sin contraseña y esta se fija por entorno. En producción la fija el operador `(asumido)`, porque el PostgreSQL es gestionado | La migración no puede dejar la base lista en producción sin intervención | Resuelto por el usuario para el desarrollo, 2026-10-17. El paso de producción es `(asumido)` y se confirma en el diseño |
| PA-T4 | El rol de solo lectura recibe `SELECT` sobre toda tabla por omisión, incluidas `sesion` —cuyo `id` es el identificador opaco de la cookie— y `usuario` —con `password_hash`—. `analitica` no necesita ninguna de las dos | Quien se conecte con el rol de lectura podría leer identificadores de sesión vivos y suplantar a un usuario. El invariante 21 dice «solo `SELECT`» y no dice sobre qué tablas | **Abierta. Decisión humana en el gate del diseño.** Recomendación: revocar `SELECT` al rol de lectura sobre `sesion` y sobre la columna `password_hash`. No es una regla de negocio nueva, sino privilegio mínimo; si se acepta, gana su criterio y se actualiza §13 |
| PA-T5 | Los valores de `lock_timeout` y `statement_timeout` no están documentados. Tampoco si el rol de solo lectura (consultas de analítica, más largas) o el de migración (DDL) deben tenerlos | Un valor corto corta consultas legítimas; uno largo no protege. Un tiempo en el rol de migración puede romper migraciones largas | Abierta. El diseño propone los valores y el usuario los aprueba |
| PA-T6 | La arquitectura §7.6 da al rol de aplicación `DELETE` por omisión sobre `sesion`, mientras que el modelo de datos §10 y [ADR-014](../../../docs/adr/20260919-sesion-con-estado.md) exigen cerrar una sesión escribiendo `revocada_en`, nunca borrando la fila. Se deja el permiso por omisión `(asumido)` | Si se revoca `DELETE` sobre `sesion`, la purga por antigüedad necesita otro rol | Abierta. Se resuelve en el diseño o en TKT-006; no hay invariante ni criterio hoy |
| PA-T7 | Las filas caducadas de `sesion` e `intento_acceso` «se purgan por antigüedad», pero el rol de aplicación no tiene `DELETE` sobre `intento_acceso` y no se dice con qué rol se purga | Los datos de acceso crecen sin límite | Abierta. Fuera de alcance; va a «Tickets futuros sugeridos» |
| PA-T8 | Los roles de PostgreSQL son del clúster. Qué hace `downgrade` con ellos, y cómo se comporta `upgrade` si ya existen por otra base del mismo clúster —en tests con varias bases— lo decide el diseño | Un `downgrade` que no los elimina deja residuos; uno que los elimina falla si otra base los usa | Abierta. Se resuelve en `/sdd-disenar`; `CA-2` fija el resultado observable |
| PA-T9 | Quedan sin documentar y los decide el diseño, con la documentación de la herramienta: nombre de la base, nombres de los roles, variables de entorno, controlador de PostgreSQL, versión mayor (que debe coincidir con producción), ubicación de Compose y de Alembic —fuera de `backend/cimenta/`—, ids de los seis roles sembrados y aislamiento de las pruebas. También `(asumido)`: que Compose no tenga contraseña por omisión | Ninguno de estos cambia el contrato observable de los criterios | Abierta. Se resuelve en `/sdd-disenar` |
| PA-T10 | `usuario.email` es único tal como el modelo declara; si la unicidad ignora mayúsculas lo decide TKT-006 `(asumido)` | Dos cuentas con «Ana@…» y «ana@…» | Abierta. Fuera de alcance; TKT-006 normaliza |
| PA-T11 | No se escriben modelos ORM en este ticket `(asumido)`: las tablas se crean con la migración y se verifican con el catálogo | Si el diseño necesita un modelo declarativo, `import-linter` y mypy lo ven | Abierta. El diseño lo justifica si lo necesita |
| PA-T12 | `uv run pytest` se habilita aquí, porque `CLAUDE.md` lo marca «desde TKT-003 o TKT-004, el primero en implementarse» y TKT-003 se implementa antes `(asumido)` | Si TKT-004 llega antes, las dependencias de pruebas ya están y este ticket solo añade las de PostgreSQL | Abierta. Se confirma al diseñar |
| PA-T13 | Ajustes de `/sdd-completar` (2026-10-18) para que la spec describa lo construido: `CA-2` esc. 1 y `CA-11` esc. 2 usan `uv run --env-file ../.env alembic upgrade head` (decisión D-7 del gate del diseño), y `CA-8` esc. 2 bloquea una fila de una tabla desechable creada con el rol de migración, porque `usuario` es de la fila 5 y las pruebas de tiempos de la entrega A no podían depender de ella (corrección A1 de la revisión de impacto) | La spec y las pruebas divergirían en el literal de dos comandos y de una tabla | Resuelto por el usuario en el gate del diseño; texto ajustado en el cierre |

## Pasada adversarial

Resultado de `abogado-del-diablo` (modo A, `/definir`) sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `ALTER DEFAULT PRIVILEGES` solo afecta a los objetos que crea el rol sobre el que se declara. Si la migración inicial lo declara para un rol y las migraciones futuras corren con otro, las tablas de los módulos nacen sin permisos o con permisos ajenos, y las pruebas de las tablas de identidad —que ya existían— pasan en verde sin detectarlo | `CA-5` crea una tabla desechable *después* de la migración con el rol de migración y comprueba los permisos de los otros dos roles |
| 2 | Alta | `TRUNCATE` es un privilegio distinto de `DELETE`, y `GRANT ALL` lo concede. Con él, la aplicación vacía `intento_acceso` y cumple la letra del invariante 20 mientras borra su propio rastro | `CA-6` incluye el rechazo de `TRUNCATE`; `CA-5` comprueba que la aplicación no tiene `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `CREATE` sobre el esquema |
| 3 | Alta | Una suite que se conecta con el propietario deja los invariantes 20 y 21 en verde sin verificar nada | `CA-9` exige que la suite falle si su conexión cambia al propietario, y que falle si apunta a SQLite |
| 4 | Alta | El rol de solo lectura heredaría `SELECT` sobre `sesion.id` —la credencial de la cookie— y sobre `password_hash`. El invariante 21 no limita las tablas | `PA-T4`, abierta y con recomendación; decisión humana en el gate del diseño. No se convierte en criterio sin esa decisión |
| 5 | Media | `ALTER ROLE … SET` solo afecta a las sesiones nuevas: un pool abierto antes sigue sin tiempos máximos, y una prueba que fija el valor en su propia sesión pasaría sin demostrar nada | `CA-8` usa una conexión nueva sin ningún `SET` previo y demuestra el corte con `55P03` y `57014`, no solo el valor |
| 6 | Media | Un rol creado sin contraseña pero con permiso de inicio de sesión podría entrar si la autenticación de la imagen fuera `trust` | `CA-10` prueba que la conexión por red sin contraseña válida es rechazada antes de fijarla |
| 7 | Media | Los roles son del clúster: `CREATE ROLE` falla si ya existe y `downgrade` puede dejar residuos o fallar, sobre todo con varias bases en el mismo clúster de pruebas | `CA-2` exige ciclo `upgrade` → `downgrade` → `upgrade` con esquema idéntico, y `PA-T8` deja el mecanismo al diseño |
| 8 | Baja | Hay tres sentidos de «rol» en el ticket: rol de negocio (tabla `rol`), rol de PostgreSQL y «rol de oficio» del glosario, que es la especialidad de un trabajador | La spec dice siempre «rol de negocio» o «rol de PostgreSQL». El diseño no debe mezclar los nombres |

Veredicto: 4 objeciones altas, todas absorbidas como criterio o como supuesto con dueño. Dos hallazgos de documentación no bloquean este ticket y van a `_index.md`: `conv-sql-postgres` §1 atribuye a un disparador la inmutabilidad de la bitácora, mientras el modelo de datos y la arquitectura la atribuyen a permisos; y `conv-sql-postgres` §5 pide `GRANT` explícito por tabla mientras el ticket y el modelo piden `ALTER DEFAULT PRIVILEGES`. Ninguna objeción revela una regla de negocio que el PRD no tenga, así que no hay escalación de entrada. `PA-T4` es la única decisión humana pendiente que puede cambiar criterios.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- Ticket: [`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md), TKT-003. Épica 0, talla M. Depende de TKT-002 (archivado).
- Modelo de datos: [`docs/03-modelo-datos.md`](../../../docs/03-modelo-datos.md) §2 (convenciones), §10 (identidad y auditoría), §13 (invariantes 10, 14, 20, 21, 30).
- Arquitectura: [`docs/02-arquitectura.md`](../../../docs/02-arquitectura.md) §7.6, con la tabla de permisos de los tres roles.
- Stack: [`docs/06-stack-tecnologico.md`](../../../docs/06-stack-tecnologico.md) §4.2 (tiempos máximos en el rol de aplicación), §4.4 (roles creados en la migración inicial; pruebas con `alembic upgrade head`) y la nota de Compose con PostgreSQL y volumen persistente.
- Convenciones: skills `conv-sql-postgres`, `conv-docker` y `conv-pruebas`. `conv-docker` §3 deja al diseño de este ticket el aislamiento de las pruebas.
- Decisiones: [ADR-002](../../../docs/adr/) (PostgreSQL, sin SQLite en tests), [ADR-013](../../../docs/adr/20260919-sqlalchemy-sincrono.md) (SQLAlchemy síncrono), [ADR-014](../../../docs/adr/20260919-sesion-con-estado.md) (sesión con estado).
- Deuda heredada: `sdd/tickets/tkt-002/delta.md` (Alembic fuera de `backend/cimenta/`); `sdd/tickets/tkt-001/delta.md` (`.env.example` sin valores; retirar marcas «desde TKT-003»).
- Archivos que se modifican: `backend/pyproject.toml`, `backend/uv.lock`, `.env.example`, `CLAUDE.md`, `docs/arranque-local.md` y, por `S1`, `docs/03-modelo-datos.md`. Archivos nuevos: el `docker-compose`, el directorio de migraciones fuera de `cimenta/` y las pruebas; su ubicación la fija el diseño.
- Módulos y tablas en alcance: `identidad` (tablas `usuario`, `rol`, `usuario_rol`, `sesion`, `intento_acceso`). Ningún otro módulo.
- Endpoints: ninguno. El borrador OpenAPI no tiene operaciones con este ticket en `x-tickets`.
