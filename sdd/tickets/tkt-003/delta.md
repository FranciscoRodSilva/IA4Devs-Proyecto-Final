# Delta · TKT-003 · PostgreSQL, migraciones y esquema de identidad

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| PostgreSQL local de desarrollo: servicio `db` con la imagen `postgres:18.6`, volumen con nombre y puerto solo en `127.0.0.1`; la contraseña es obligatoria y no tiene valor por omisión | `compose.yaml` y bloque de base de datos de `.env.example` | Que quien desarrolla tenga una base reproducible con `docker compose up -d db`, sin secretos en el repositorio |
| Entorno de migraciones de Alembic, fuera del paquete `cimenta`, configurado en `[tool.alembic]` sin `alembic.ini`. `env.py` se niega a migrar con cualquier rol que no sea `cimenta_migracion` y confirma la transacción en la rama de la línea de comandos | `backend/migraciones/` (`env.py`, `script.py.mako`) y `backend/pyproject.toml` | Que toda tabla de todo módulo nazca del mismo propietario, con los privilegios por omisión que le corresponden |
| Migración `0001`: los roles de PostgreSQL `cimenta_aplicacion` y `cimenta_lectura` (sin contraseña, con todos los atributos en `NO*`), sus tiempos máximos, `USAGE` sobre `public`, los privilegios por omisión, las cinco tablas de identidad y las revocaciones de `intento_acceso` (invariante 20), de `sesion` y de `usuario.password_hash` al rol de lectura (invariante 21 y `PA-T4`) | `backend/migraciones/versions/v0001_identidad_roles_y_esquema.py` | Persistir identidad con privilegio mínimo (`RNF-09`, `RNF-16`) |
| Migración `0002`: los seis roles de negocio con UUID fijos | `backend/migraciones/versions/v0002_semilla_roles_de_negocio.py` | Datos de arranque del PRD §4 |
| Script que fija las contraseñas de los roles desde el entorno, enviándolas ya cifradas con SCRAM | `backend/herramientas/` (`conexion.py`, `contrasenas_roles.py`) | Que las contraseñas no vivan en la migración ni en el repositorio (`RNF-07`) |
| Suite de integración de 61 pruebas en 13 archivos más `conftest.py`: PostgreSQL real con testcontainers, esquema por `alembic upgrade head`, conexiones del rol de aplicación, guarda que falla si la conexión no es la de ese rol y otra que rechaza SQLite | `backend/tests/` | Que los invariantes 20 y 21, que son permisos, estén verificados y no solo escritos |
| ADR-019, roles de PostgreSQL y migraciones | `docs/adr/20261017-roles-postgresql-y-migraciones.md` | Registrar las opciones descartadas de cuatro decisiones que condicionan a cada ticket con tablas |
| Dependencias: `alembic`, `psycopg[binary]` y `sqlalchemy` en ejecución; `pytest` y `testcontainers[postgres]` en desarrollo | `backend/pyproject.toml` y `backend/uv.lock` | Migrar, conectar y probar contra PostgreSQL |
| Cinco tablas de identidad y tres roles de PostgreSQL | base de datos | `usuario`, `rol`, `usuario_rol`, `sesion` e `intento_acceso`; migración, aplicación y solo lectura |
| Sección «Base de datos» y requisito de Docker en el arranque local, y enlace al ADR-019 en `llms.txt` | `docs/arranque-local.md`, `llms.txt` | Que el arranque documentado incluya la base de datos y el ADR sea localizable |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Comandos del proyecto | `CLAUDE.md`, `docs/arranque-local.md` | `uv run pytest`, `alembic upgrade head` y `docker compose up -d db` figuraban «desde TKT-003» → funcionan; Alembic se ejecuta con `--env-file ../.env` y desde `backend/` |
| Versión de SQLAlchemy | `CLAUDE.md`, `docs/06-stack-tecnologico.md`, `llms.txt` | «SQLAlchemy 2.0 síncrono» → «2.x síncrono»; el bloqueo resolvió 2.1.5. Decisión del usuario del 2026-10-18 |
| Quién crea los roles | `docs/02-arquitectura.md` §7.6, `docs/03-modelo-datos.md` §2 y §13, `docs/06-stack-tecnologico.md` §4.4 y §6.5, `docs/05-tickets-trabajo.md` (criterio de TKT-003), `conv-sql-postgres` | «La migración crea los tres roles» → la migración crea los de aplicación y de solo lectura; el de migración lo crea el entorno |
| Esquema de identidad | `docs/03-modelo-datos.md` §2 y §10 | Sin columnas de auditoría ni unicidad de `usuario_rol` → `usuario` y `usuario_rol` llevan las cuatro columnas de auditoría con autor nulo permitido, y `usuario_rol` lleva `UNIQUE (usuario_id, rol_id)` |
| Invariante 21 | `docs/03-modelo-datos.md` §13, `docs/02-arquitectura.md` §7.6 | «Solo `SELECT`» → solo `SELECT`, sin acceso a `sesion` ni a `usuario.password_hash`, con `GRANT` por columna sobre `usuario` y la regla de que toda tabla futura con credenciales revoca `SELECT` en su propia migración |
| Estructura del repositorio y convenciones | `docs/convenciones.md`, `CLAUDE.md` | `.env.example` «sin valores» → con valores de desarrollo evidentes; aparecen `compose.yaml`, `backend/migraciones/`, `backend/herramientas/` y `backend/tests/` |
| Convenciones de SQL y de Docker, y agente de DevSecOps | `.claude/skills/conv-sql-postgres`, `.claude/skills/conv-docker`, `.claude/agents/ingeniero-devsecops.md` | `GRANT` explícito por tabla → privilegios por omisión más `REVOKE` con su prueba; `docker-compose.yml` → `compose.yaml`; un servicio hasta TKT-059 |
| Conteo de ADR | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/06-stack-tecnologico.md` §13 | 18 → 19 |
| Literales de la spec | `sdd/tickets/tkt-003/spec.md` (`CA-2` esc. 1, `CA-8` esc. 2, `CA-11` esc. 2 y `PA-T13`) | Comando sin `--env-file` y bloqueo de una fila de `usuario` → los literales que se construyeron (D-7 y corrección A1 del diseño) |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Marca «desde TKT-003» de `uv run pytest`, `alembic upgrade head` y `docker compose up -d db`, y sus filas de «Lo que todavía no arranca» | `CLAUDE.md`, `docs/arranque-local.md` | Los tres comandos ya funcionan, verificados en copia limpia |

## Comportamiento observable nuevo

- `docker compose up -d db` levanta PostgreSQL 18.6 con datos persistentes entre arranques; sin la variable de contraseña, Compose falla nombrándola y no arranca nada.
- `uv run --env-file ../.env alembic upgrade head` deja la base en `0002`: cinco tablas de identidad, tres roles de PostgreSQL y seis roles de negocio. Con cualquier rol que no sea `cimenta_migracion` se niega y no persiste nada; sin variables, falla nombrando la que falta.
- `alembic downgrade base` revierte las tablas y los privilegios por omisión, pero **no elimina los roles de PostgreSQL**, que son del servidor y no de la base.
- Tras la migración, los roles de aplicación y de lectura no pueden iniciar sesión hasta que `uv run --env-file ../.env python -m herramientas.contrasenas_roles` les fije la contraseña desde `.env`.
- La aplicación no puede modificar, borrar ni vaciar `intento_acceso`, ni crear ni alterar objetos. El rol de lectura no puede escribir, ni leer `sesion` ni `usuario.password_hash`. Todas las denegaciones son `42501`.
- Una espera de bloqueo de más de 5 s se corta con `55P03`, y una sentencia de la aplicación de más de 15 s (60 s para lectura) con `57014`.
- `uv run pytest` necesita Docker en marcha: levanta su propio PostgreSQL y no usa el de Compose. Si la conexión de pruebas no es la del rol de aplicación, o apunta a SQLite, la suite falla.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO y tipos generados | Ninguno; el borrador OpenAPI no tiene operaciones con este ticket | No |
| Esquema de base de datos | Tablas `usuario`, `rol`, `usuario_rol`, `sesion` e `intento_acceso`; roles de PostgreSQL `cimenta_migracion`, `cimenta_aplicacion` y `cimenta_lectura`; revisión de Alembic `0002` | No: no había base de datos. Toda tabla futura hereda los privilegios por omisión |
| Convención interna de migraciones | Solo migra `cimenta_migracion`; las revisiones nuevas llevan `--rev-id` manual y correlativo (`0003` en adelante) | No |
| Variables de entorno | `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO`, `CIMENTA_DB_NOMBRE` y tres contraseñas | No |

## Decisiones (ADR)

La decisión tuvo opciones descartadas con evidencia citable y se escribió como ADR-019: [`docs/adr/20261017-roles-postgresql-y-migraciones.md`](../../../docs/adr/20261017-roles-postgresql-y-migraciones.md). Resumen:

- **Quién migra:** el rol que crea el entorno, con una guarda en `env.py`, frente a que la migración cree el rol de migración y haga `SET ROLE` (en PostgreSQL 16 y posteriores quien crea un rol con `CREATEROLE` no obtiene por omisión la opción `SET` sobre él) y frente a migrar con cualquier superusuario (las tablas nacerían de otro propietario y sin los privilegios por omisión).
- **Roles del clúster:** creación idempotente y bajada que no los elimina, frente a `CREATE ROLE` simple (falla en la segunda base del clúster) y a una bajada que los elimina (falla con `2BP01` si otra base los usa).
- **Contraseñas:** fuera de la migración, por entorno, con un script que la suite reutiliza, frente a una contraseña en la migración (`RNF-07`) y a un script de inicio del contenedor (dejaría producción sin roles).
- **Aislamiento de pruebas:** base copiada de una plantilla migrada una vez por sesión, frente a una transacción envolvente deshecha (no admite las filas confirmadas que necesita la prueba de `55P03`) y a vaciar tablas (exige el propietario y borra la semilla).
- **Evidencia:** 61 pruebas con rechazo por garantía, más de 40 mutantes aplicados de uno en uno con SHA-256 verificado, y la prueba ejecutada por el auditor de seguridad en PostgreSQL 18.6 (`impl.md`). Esa prueba **corrigió una premisa del ADR**: ver el aprendizaje sobre `CREATEROLE`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un rol `NOSUPERUSER` con `CREATEROLE`, dueño de la base, **no** puede aplicar la `0001`: `ALTER ROLE … NOSUPERUSER NOCREATEDB NOREPLICATION NOBYPASSRLS` falla con `permission denied to alter role`, porque PostgreSQL solo deja cambiar un atributo a quien lo posee. Pasan `LOGIN`, `NOCREATEROLE`, `CREATE ROLE`, `ALTER ROLE … SET`, `GRANT USAGE` y `ALTER DEFAULT PRIVILEGES`. Un `CREATE ROLE` sin opciones ya nace con todos los atributos en `NO*`: el endurecimiento solo hace falta para roles preexistentes | Hallazgo N-01 y dos pruebas del auditor de seguridad en PostgreSQL 18.6 | TKT-058: quitar los `NO*` del `ALTER ROLE` o crear los roles con ellos desde el entorno. Las frases de `design.md` que dicen que `CREATEROLE` basta quedan superadas |
| Una conexión de SQLAlchemy 2 abre la transacción en la primera sentencia: la guarda de `env.py` (`SELECT current_user`) la dejaba abierta y la CLI de Alembic terminaba con código 0 sin persistir nada, rollback al cerrar | Fila 4: `pg_default_acl` vacía tras la CLI; `test_identidad_migracion_cli.py` | Todo `env.py` que ejecute algo antes de migrar: confirmar en la rama que posee la conexión |
| Una verificación de «código de salida 0» no prueba que algo se haya hecho: hay que comprobar el efecto | Mismo hallazgo; la verificación de la fila 3 era insuficiente | Toda fila cuya verificación sea un comando que escribe en la base |
| `ALTER DEFAULT PRIVILEGES` solo afecta a lo que crea el rol sobre el que se declara; por eso `env.py` exige migrar con ese rol | TC-15, TC-31, MP-3 | Toda migración de módulo |
| `PUBLIC` conserva `USAGE` sobre `public` desde PostgreSQL 15: quitar `GRANT USAGE` a los roles no se nota salvo que la prueba revoque `USAGE` a `PUBLIC` | Mutante X-08 (sobrevivía) y TC-33b | Pruebas de permisos sobre esquemas |
| `ALTER ROLE … SET` solo afecta a sesiones nuevas, y el propio rol puede anularlo con `SET` (`SET statement_timeout=0`): los tiempos son red de seguridad de recursos, no frontera de seguridad | TC-50 a TC-52 y la prueba del auditor | TKT-005 y TKT-021: no apoyar ninguna garantía de seguridad en ellos |
| `SHOW statement_timeout` devuelve `1min`, no `60s` | TC-50 | Pruebas que comparen el valor mostrado |
| `testcontainers.postgres` está deprecado; el módulo vigente es `testcontainers.community.postgres` | `DeprecationWarning` en la fila 1 | TKT-059 (MinIO) y cualquier prueba nueva |
| La imagen `postgres:18` declara su volumen en `/var/lib/postgresql` y `PGDATA=/var/lib/postgresql/18/docker` | `docker image inspect` y TC-02 | `compose.yaml`; la imagen de producción de TKT-058 |
| Con `--import-mode=importlib`, pytest no necesita `__init__.py` en `tests/`, pero mypy exige nombres base de archivo únicos en todo el árbol | `[tool.pytest]` y los nombres de las pruebas (`permisos_tablas`, `tiempos_maximos`) | Todos los tickets que añadan pruebas |
| La plantilla estándar de Alembic escribe `repr()` (comillas simples) y `op` sin uso: una revisión recién generada no pasa `ruff`. La plantilla del proyecto emite `op` solo si hay cuerpo y escribe comillas dobles | TC-80 | La primera migración de módulo; con `--autogenerate` hará falta además un `post_write_hooks` |
| Una prueba que escanea el árbol en busca de una cadena se encuentra a sí misma por el nombre de su función, no solo por su cuerpo | TC-17: 53 de 54 en verde | Pruebas de escaneo estático |
| En Git Bash, `grep -c $'\r'` da falsos positivos y falsos ceros; la comprobación fiable de retornos de carro es por bytes con Python | Fila 11 y las dos reauditorías | Cualquier comprobación de LF |
| Con la semilla presente, quitar `GRANT USAGE` solo lo detecta TC-33b; TC-12 (ciclo `upgrade` → `downgrade` → `upgrade`) no lo ve porque compara dos fotografías iguales | Mutante X-08 revisado | Conservar TC-33b |
| `has_table_privilege` y `has_column_privilege` leen el catálogo del rol de migración; las pruebas de comportamiento van con el rol del criterio | `conftest.py` | Cualquier prueba de permisos nueva |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `auditor-sql`, `meta-sdd` y `desarrollador-aplicacion`. Es la cuarta vez que aparece; se sustituyeron según metodología §13: la revisión de impacto la hizo un agente `Explore`, la documentación un agente general con `conv-documentacion`, y `meta-sdd` el orquestador | Alta |
| `herramienta` | `verificar_docs.py` falla durante todo el ticket por los enlaces del hub y de `impl.md` a `delta.md`. Tercera vez (TKT-001, TKT-002 y este): ya es un patrón | Alta |
| `guardrail` | La verificación de una fila que escribe en una base debe comprobar el efecto, no el código de salida: la CLI de Alembic devolvía 0 sin persistir y la suite verde no lo veía porque sus fixtures confirmaban por su cuenta. Lo destapó el desarrollador al consultar `pg_default_acl` tras la CLI | Alta |
| `comando` | El diseño afirmó «`CREATEROLE` basta» sin probarlo; el arquitecto no tiene terminal. Lo refutó el auditor de seguridad al final del ticket, cuando ya estaba en el ADR y en cuatro documentos. `/sdd-disenar` debería exigir un experimento previo —quién lo ejecuta, dónde— cuando el diseño afirma qué permite un privilegio. Segunda vez que el diseño descansa en un supuesto sin ejecutar (TKT-002) | Alta |
| `comando` | El orden de implementación sumó unas 1,450 líneas, el triple del tope de 400 de `/sdd-disenar`. La partición en dos entregas del mismo ticket no es una partición real: la entrega A no se fusiona sin la B y `v0001` se completó en B. La talla M del ticket subestimaba un ticket con roles, permisos y arnés de pruebas | Media |
| `comando` | Entre la spec y el diseño aprobado hubo reinterpretaciones de literales (el comando de Alembic con `--env-file`, la tabla de `CA-8` esc. 2) que solo se reconcilian en `/sdd-completar`. Tras el gate del diseño debería ajustarse la spec en el mismo paso, para que `/sdd-revisar` compare contra el texto vigente | Media |
| `guardrail` | Las promesas escritas en la sección «Impacto» del diseño («queda escrito en el modelo de datos»; «documentado en arquitectura §7.6») no se cumplieron en la fila 10 y las encontró el auditor tres ciclos después. La fila de documentación debería llevar una lista de verificación de lo que el diseño prometió | Media |
| `convención` | Un test que escanea el árbol se encontró a sí mismo por el nombre de su función; el diseño (B4) había previsto el autoencuentro del cuerpo y no del nombre. La convención de `conv-pruebas` debería decirlo | Baja |
| `herramienta` | Los finales de línea en Windows siguen siendo fricción: el tester escribió un archivo con CRLF y `grep $'\r'` dio resultados inconsistentes, con lo que dos agentes llegaron a diagnósticos contrarios. Segunda vez tras TKT-001. Conviene un verificador por bytes en `tools/` | Media |
| `agente` | Cada ciclo de reauditoría encontró textos aproximados escritos por el corrector o por el orquestador (una celda, una fecha, una versión de Node): tres ciclos para tres Menores de trazabilidad en `impl.md`. Mismo patrón que TKT-001 | Baja |
| `modelo` | Las filas de `haiku` con contenido literal salieron bien a la primera (`v0002`, Compose, documentación). El tester en `sonnet` añadió por su cuenta mutantes extra y encontró uno que sobrevivía (X-08): la fase de mutación por garantía vale su coste en tickets de permisos | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| La `0001` exige superusuario o un rol que posea los atributos que ajusta; `NOSUPERUSER` con `CREATEROLE` no basta (N-01) | El contrato de producción lo decide quien contrate el PostgreSQL gestionado | TKT-058: quitar los `NO*` del `ALTER ROLE` o crear los roles con ellos desde el entorno |
| `design.md` conserva frases que dicen que `CREATEROLE` basta (líneas ~657, 706, 746 y 767), el nombre antiguo de TC-17 y del archivo de tiempos | Es el diseño aprobado en el gate | Ninguno: este delta las supera |
| `cimenta_aplicacion` conserva `DELETE` sobre `sesion` por omisión, contra el espíritu de ADR-014; y nadie puede purgar `sesion` ni `intento_acceso` por antigüedad (`PA-T6` y `PA-T7`) | Revocarlo sin decidir con qué rol se purga sería inventar una regla | TKT-057, que escribe `intento_acceso`, o un ticket de operación |
| `cimenta_lectura` lee `email` y `origen_ip` de `intento_acceso` (N-04); y los privilegios por omisión son «hacia abierto» para tablas futuras con credenciales (N-03) | Fuera del alcance de identidad; la regla de §13 obliga a revocar en cada migración | Primer ticket de `analitica` (TKT-039) y toda migración con credenciales |
| `herramientas/contrasenas_roles.py` acepta contraseñas `solo-desarrollo-*` fuera de local | Sin configuración de entorno todavía | TKT-057 y TKT-058 |
| `cimenta_aplicacion` conserva `INSERT`, `UPDATE` y `DELETE` sobre `rol` | Ningún caso de uso lo edita todavía | Migración posterior, con su prueba, si se confirma |
| Imagen de Compose fijada por etiqueta y no por digest; `PUBLIC` conserva `CONNECT` y `TEMP` sobre la base | Aceptable en local | TKT-009 y TKT-058 |
| `pip-audit` no está en el grupo `dev` (se ejecutó con `uvx`) | Es del pipeline | TKT-009 |
| TKT-005 también modifica `pyproject.toml` y `uv.lock`; TKT-004 comparte `uv run pytest` | El segundo que llegue rebasa | TKT-004 y TKT-005 |
| TKT-006 necesita una URL y un motor de aplicación (`herramientas` solo define `url_migracion()`) y los modelos ORM; y normalizar el correo (`PA-T10`) | Non-goals de este ticket | TKT-006 |
| Las revisiones con `--autogenerate` no pasan por `ruff format` sin `post_write_hooks` | No hay primera migración de módulo | TKT-011 |
| El verificador de escenarios de TKT-009 solo mira `HDU`, así que ignora `test_tkt003_*`; falta un contrato de `import-linter` para `tests/`; la suite tarda unos 31 s y necesita Docker en CI | Es del pipeline | TKT-009 |
| Seis archivos de prueba redefinen el alias `Conectar` en lugar de importar el `Protocol` del `conftest.py`; `_contrasenas_de_roles` da un `KeyError` poco claro si la prueba no pide `credenciales`; el mensaje de la guarda con el mutante MP-7 dice «es cimenta_aplicacion» | Refactor menor sin efecto en las garantías | Cuando se toquen esos archivos |
| `docs/arranque-local.md` no trae un comando literal para conectarse como `cimenta_aplicacion`, y `docs/06-stack-tecnologico.md` §13 sigue sin la fila del ADR-018 (de TKT-002) | Sin efecto funcional | Siguiente cambio de documentación |
| «SQLAlchemy 2.0» sigue en ADR-010, ADR-013 y en `conv-backend-fastapi`, `desarrollador-sql`, `arquitecto-tecnico` y `sdd-disenar` | Históricos o estilo 2.0, válido en 2.1 | Siguiente cambio del toolkit |
| Los tres archivos de `.claude/` modificados conservan CRLF en el árbol de trabajo local | El blob de HEAD tiene LF y `.gitattributes` fija `eol=lf`: el commit los normaliza | Ninguno |

## Pull request

**Título:** `TKT-003 · PostgreSQL, migraciones y esquema de identidad`
**Origen:** `agent`
**Cuerpo:**

Qué: levanta PostgreSQL 18.6 para desarrollo con Compose, configura Alembic fuera de `backend/cimenta/` y crea las cinco tablas de identidad (`usuario`, `rol`, `usuario_rol`, `sesion`, `intento_acceso`) con los seis roles de negocio como datos de arranque. Establece los tres roles de PostgreSQL de `RNF-09`: el de migración, que crea el entorno y es el único con el que Alembic acepta migrar, y los de aplicación y solo lectura, que crea la migración sin contraseña —se fija por entorno con `herramientas.contrasenas_roles`—. Fija `lock_timeout` y `statement_timeout` en el rol (`RNF-16`) y hace verdad los invariantes 20 y 21: la aplicación no puede modificar, borrar ni vaciar `intento_acceso`, y el rol de lectura no escribe ni lee `sesion` ni `usuario.password_hash`. Añade 61 pruebas contra PostgreSQL real con testcontainers, el ADR-019 y la documentación afectada.

Por qué: dos invariantes del modelo de datos son permisos, no restricciones declarativas, y solo existen si los roles existen. Los tickets de negocio persisten sobre este esquema y heredan sus privilegios por omisión.

Criterios cubiertos: `CA-1` a `CA-11` y `CA-R1` a `CA-R6` de `sdd/tickets/tkt-003/spec.md`. Cada garantía de permisos se vio fallar con un mutante (más de 40, SHA-256 verificado al restaurar); el mutante X-08 sobrevivía y lo cierra un test nuevo. Decisiones del usuario aplicadas: auditoría solo en `usuario` y `usuario_rol`, `UNIQUE (usuario_id, rol_id)`, roles sin contraseña en la migración, `PA-T4` (el rol de lectura no lee `sesion` ni `password_hash`), tiempos de 5 s y 15 s para la aplicación y de 5 s y 60 s para lectura, PostgreSQL 18, SQLAlchemy 2.x, y el ADR-019. Hallazgo a revisar con atención: **la migración `0001` exige un rol superusuario o equivalente; `NOSUPERUSER` con `CREATEROLE` no basta** (verificado en PostgreSQL 18.6), y TKT-058 decide cómo contratarlo en producción.

Cómo verificarlo, con `uv` y Docker instalados:

```bash
cp .env.example .env
docker compose up -d db
cd backend && uv sync --locked && uv run --env-file ../.env alembic upgrade head
uv run --env-file ../.env python -m herramientas.contrasenas_roles
uv run pytest && uv run ruff check . && uv run mypy . && uv run lint-imports
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-003/delta.md`. Auditorías: arquitectura y seguridad aprobadas tras dos ciclos de cierre y dos de `/sdd-revisar`. No se despacharon `auditor-sql`, `auditor-codigo` ni `auditor-docs`, porque esos agentes no existen en este entorno. La ejecución se hizo en dos entregas sobre una sola rama; como `v0001` se completó en la segunda y la primera no se fusiona sin ella, el PR es único.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
