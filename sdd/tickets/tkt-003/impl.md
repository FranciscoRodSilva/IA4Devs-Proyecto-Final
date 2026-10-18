# Impl · TKT-003 · PostgreSQL, migraciones y esquema de identidad

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

> **Entregas A y B ejecutadas.** El archivo cubre las once filas del orden de implementación, de la partición (b) aprobada en el gate del diseño: la entrega A (filas 1, 2, 3, 4, 7 y la parte A de la 9) y la entrega B (filas 5, 6, 8, 10, 11 y la parte B de la 9). Las dos se fusionan juntas a `Produccion`: la entrega A no se fusiona sin la B.

## Qué se implementó

PostgreSQL local con Compose, Alembic configurado fuera de `backend/cimenta/`, el arnés de pruebas con testcontainers, y dos migraciones: la `0001`, con los roles de aplicación y de solo lectura, los tiempos máximos, los privilegios por omisión y las cinco tablas de identidad, con la revocación de `UPDATE`, `DELETE` y `TRUNCATE` sobre `intento_acceso` (invariante 20) y de `sesion` y `usuario.password_hash` al rol de lectura (`PA-T4`); y la `0002`, que siembra los seis roles de negocio. Un script fija las contraseñas de los roles desde el entorno. La documentación afectada y el ADR-019 se actualizaron en el mismo cambio.

La suite tiene 61 pruebas, todas contra PostgreSQL 18.6 real levantado por testcontainers, con el esquema construido por `alembic upgrade head` y conexiones del rol de aplicación. Una guarda hace fallar la suite si la conexión no es la de ese rol, y otra rechaza una variable que apunte a SQLite. Los mutantes del diseño, los añadidos por el tester y los 27 de la entrega B ponen la suite en rojo, salvo uno equivalente que se descartó.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-17 | `uv add sqlalchemy` resolvió a la versión 2.1.5 y no a una 2.0.x. El diseño no fijaba el mayor y el stack dice «SQLAlchemy 2.0 síncrono». Se acepta 2.1.5 y se anota para `delta.md` | La API síncrona que usa el ticket es la misma; fijar `<2.1` sería una restricción que nadie pidió. Las 24 pruebas pasan con 2.1.5 |
| 2026-10-17 | El arnés usa `testcontainers.community.postgres`, no `testcontainers.postgres` | `testcontainers.postgres` importa pero emite `DeprecationWarning`; el módulo nuevo importa sin avisos |
| 2026-10-17 | Compose fija `postgres:18.6` | El diseño pedía `postgres:18.<menor>` exacto: `PG_VERSION=18.6-1.pgdg13+2`, y `postgres:18` y `postgres:18.6` tienen el mismo digest |
| 2026-10-17 | **Fila 3 reabierta (⚠ Ajustado).** La guarda de `env.py` abría una transacción implícita con `SELECT current_user` que nadie confirmaba: la CLI `alembic upgrade head` terminaba con código 0 y no persistía nada. Se añadió `test_identidad_migracion_cli.py` (3 casos, ruta real de la CLI) y `_conexion.commit()` en la rama del motor propio de `env.py` | La suite no lo veía porque sus fixtures pasan la conexión por `attributes["connection"]` y confirman ellas. Lo descubrió el desarrollador al comprobar `pg_default_acl` tras la CLI en la fila 4. La verificación de la fila 3 («código 0») era insuficiente: debía comprobar que persistía |
| 2026-10-17 | `conftest.py`: el ciclo de dependencias `migrar` → `credenciales` → `observacion_sin_contrasena` → `plantilla_migrada` se resolvió con un fixture privado `_contrasenas_de_roles`; las pruebas importan `herramientas` con `importlib.import_module` | Con `import` estático mypy falla con `import-not-found` antes del verde, y el desarrollador no puede tocar los tests. Coste: las llamadas a `herramientas` quedan como `Any` en las pruebas |
| 2026-10-17 | TC-32 lleva una precondición que el diseño no declara: la aplicación tiene `SELECT` sobre la tabla posterior | Sin ella nacería en verde por vacuidad: una tabla sin ningún privilegio también da `false` para `TRUNCATE`, `REFERENCES` y `TRIGGER` |
| 2026-10-17 | Caso extra `test_tkt003_ca08_esc01_migracion_sin_tiempos_en_este_ticket` (TC-50b), con la guarda de D-2: el rol de migración no tiene tiempos máximos. `SHOW statement_timeout` devuelve `1min` para el rol de lectura, no `60s` | Un test, una afirmación. El valor de `SHOW` es el formato de PostgreSQL para 60 s |
| 2026-10-17 | Caso nuevo `test_tkt003_ca05_esc03_usage_del_esquema_no_depende_de_public` (TC-33b), en `test_identidad_uso_del_esquema.py` | El mutante X-08 (quitar `GRANT USAGE ON SCHEMA public`) dejaba la suite en verde: PostgreSQL 15 y posteriores conceden `USAGE` a `PUBLIC`. El test revoca `USAGE` a `PUBLIC` en la copia desechable y exige que ambos roles lo conserven |
| 2026-10-18 | TC-17 se renombra a `test_tkt003_ca09_esc01_esquema_sin_creacion_automatica` (el diseño lo llamaba `test_tkt003_ca09_esc01_sin_create_all`). El escaneo no cambia | Defecto del tester: `def test_..._sin_create_all()` contiene la subcadena `create_all(` que el escaneo busca, así que el caso se encontraba a sí mismo y fallaba en verde-esperado (53 de 54). El diseño (B4) ya preveía el autoencuentro y lo resolvía con la concatenación, pero olvidó que el nombre de la función también se lee. Mutantes desechables con `tkt003` en el nombre (la llamada a la creación automática en `tests/`, `herramientas/`, `migraciones/` y `migraciones/versions/`, y una URL de SQLite en `tests/`) ponen el caso en rojo con el infractor nombrado; sin ellos, verde. Los desechables se borraron. La fila 3 de `design.md` (TC-17) conserva el nombre antiguo y debe actualizarse al aprobar |
| 2026-10-18 | `backend/migraciones/script.py.mako` (fila 11, TC-80): una revisión recién generada no pasaba `ruff check` ni `ruff format --check`. Corrección en la plantilla, sin tocar `v0001` ni `v0002` ni los tests: (1) `from alembic import op` solo se emite si hay `upgrades` o `downgrades`; (2) `revision`, `down_revision`, `branch_labels` y `depends_on` se escriben con comillas dobles mediante una función `_literal` en `<%! %>`, en lugar de `repr()`; (3) la línea vacía sobrante tras los imports desaparece, con `imports` condicional. Sin cambio de contrato: el archivo generado sigue teniendo `upgrade()` y `downgrade()` con `pass`. Causa: `repr()` produce comillas simples que `ruff format` reescribe; `op` sin uso daba F401 y dejaba dos líneas en blanco tras los imports (I001). Alembic 1.x documenta la plantilla estándar con `repr()` y `op` incondicional, así que la corrección es propia del proyecto | Con la plantilla original, TC-80 nacía en rojo y TC-73 fallaría con la siguiente migración. Verificado: `alembic revision -m desechable --rev-id 0003` genera `v0003_desechable.py`; `ruff format --check`, `ruff check` y `mypy` sobre ese archivo salen con 0; el archivo se borró y `alembic heads` sigue en `0002 (head)`. Además, con la plantilla renderizada a mano se comprobó una fusión con `down_revision` en tupla (`("0001", "0002")`), que pasa mypy. Suite: `uv run pytest -q` 61 passed; `ruff format --check .`, `ruff check .`, `mypy .` y `lint-imports` (14 kept, 0 broken) en verde. Pendiente, fuera de este ajuste: las revisiones con cuerpo generadas por `--autogenerate` no pasan por ruff format sin un `post_write_hooks` en `[tool.alembic]`; se decide al escribir la primera migración de módulo |
| 2026-10-18 | `backend/tests/test_identidad_permisos_tablas.py` (fila 11, TC-83): finales de línea convertidos de CRLF a LF; 332 líneas, sin cambio de contenido | El archivo se escribió con CRLF y el cierre de la fila 11 exige LF: TC-83 falla si un archivo de las rutas que revisa contiene `\r`. Corrección mecánica: bytes `\r\n` reemplazados por `\n`, sin otro cambio |
| 2026-10-18 | Entrega B, fila 5: caso extra TC-26b (seis claves foráneas que TC-26 no nombra, parametrizado). El archivo de permisos de tablas se llama `test_identidad_permisos_tablas.py`, no `test_identidad_permisos.py` | Ese nombre base ya existía y mypy exige nombres base únicos en `tests/`. TC-26b cubre las claves de auditoría de `usuario` y `usuario_rol`, que son decisión del usuario |
| 2026-10-18 | Entrega B, fila 6: casos extra TC-28b (bajar solo a `0001` deja `rol` vacía y con versión `0001`) y TC-28c (bajar con un rol asignado falla con `23503` y hace rollback). TC-17 exige los 13 archivos de prueba del ticket más `conftest.py`, `env.py` y las dos migraciones | Sin TC-28b, una `_BAJADA` vacía de `0002` pasaba desapercibida: TC-12 baja hasta `base` y esa bajada elimina `rol` igualmente |
| 2026-10-18 | Entrega B, fila 6: el docstring de `v0002` lleva un párrafo más que el literal del diseño (los id son fijos para que todos los entornos tengan las mismas filas, y el código busca un rol por clave, nunca por id) | Es prosa tomada del propio diseño; no cambia el código |
| 2026-10-18 | Entrega B, fila 8: los tests de `PA-T4` se desdoblaron en siete (comportamiento y catálogo; lectura y aplicación sin regresión), con consultas laterales (`count(*)`, `WHERE password_hash`, fila completa). TC-42 se ajustó en el rojo de esta fila a los conjuntos nuevos: lectura sin privilegios por tabla sobre `usuario` y `sesion`, y `SELECT` por columna sobre las diez de `usuario` que no son `password_hash` | Impiden que un verde parcial deje pasar una fuga. El ajuste de TC-42 lo prevé el diseño y lo hace el tester |
| 2026-10-18 | TC-51 bloquea una fila de la tabla desechable `bloqueo_tkt003`, creada por el propio caso con el rol de migración, y no una fila de `usuario` como dice el literal de `CA-8` esc. 2. Es la corrección A1 de la revisión de impacto, aprobada en el diseño | Es la corrección A1 de la revisión de impacto, aprobada en el diseño. La tabla desechable demuestra igualmente `55P03` en unos 5 s |
| 2026-10-18 | El archivo de pruebas de tiempos se llama `test_identidad_tiempos_maximos.py`, no `test_identidad_tiempos.py` | Por la regla de nombres base únicos de mypy y para que el nombre diga qué prueba |
| 2026-10-18 | La afirmación de la verificación final («ningún archivo del ticket con retorno de carro ni BOM») es cierta para los archivos nuevos y los modificados del ticket, salvo tres del directorio `.claude/` (`ingeniero-devsecops.md`, `conv-docker/SKILL.md` y `conv-sql-postgres/SKILL.md`), que conservan CRLF en el árbol de trabajo local (el blob de HEAD tiene LF). `.gitattributes` fija `eol=lf` y el commit los normaliza. TC-83 no revisa `.claude/` | Conservan CRLF en el árbol de trabajo local; el blob de HEAD tiene LF. `.gitattributes` fija `eol=lf` y el commit los normaliza. TC-83 no revisa `.claude/` |
| 2026-10-18 | Entrega B, fila 10: la documentación incorpora la decisión del usuario sobre SQLAlchemy («2.x síncrono», bloqueo en 2.1.5), la frase «la migración crea los roles de aplicación y de solo lectura; el de migración lo crea el entorno» en cada documento que decía «los tres roles», y la advertencia de que Alembic se ejecuta desde `backend/` y de que el rol de migración es superusuario solo en local. El ADR nuevo es el ADR-019 | Decisiones D-3, D-5, D-7, D-8 y D-9 del gate, y F002 de la auditoría de arquitectura de la entrega A. El índice del stack seguía sin la fila del ADR-018 (preexistente de TKT-002) y no se añadió aquí |
| 2026-10-18 | `backend/tests/test_identidad_migracion_ciclo.py`, docstring de TC-10: «deja las cinco tablas y los tres roles» → «deja las cinco tablas y los roles de PostgreSQL». Solo el texto del docstring; sin cambio de código ni de aserciones | «tres roles» podía leerse como las filas de la tabla `rol`, que son los seis roles de negocio de `0002`; el docstring precisa que se trata de los roles de PostgreSQL |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/pyproject.toml` | modificado (dependencias, `[tool.alembic]`, `[tool.pytest]`) | infraestructura |
| `backend/uv.lock` | modificado | infraestructura |
| `compose.yaml` | nuevo | infraestructura |
| `.env.example` | modificado (bloque de base de datos) | infraestructura |
| `backend/herramientas/__init__.py`, `conexion.py`, `contrasenas_roles.py` | nuevos | infraestructura |
| `backend/migraciones/env.py`, `script.py.mako` | nuevos | infraestructura |
| `backend/migraciones/versions/v0001_identidad_roles_y_esquema.py` | nuevo (§1 roles, §2 tiempos, §3 `USAGE`, §4 privilegios por omisión, §5 cinco tablas, §6 revocación sobre `intento_acceso`, §7 rol de lectura sin `sesion` ni `password_hash`) | infraestructura |
| `backend/migraciones/versions/v0002_semilla_roles_de_negocio.py` | nuevo (los seis roles de negocio con UUID fijos) | infraestructura |
| `backend/tests/conftest.py` | nuevo | pruebas |
| `backend/tests/test_identidad_migracion.py`, `test_identidad_migracion_cli.py`, `test_identidad_permisos.py`, `test_identidad_credenciales.py`, `test_identidad_privilegios_por_omision.py`, `test_identidad_tiempos_maximos.py`, `test_identidad_uso_del_esquema.py`, `test_identidad_esquema.py`, `test_identidad_permisos_tablas.py`, `test_identidad_migracion_ciclo.py`, `test_identidad_semilla.py`, `test_identidad_sin_create_all.py`, `test_identidad_lectura_sin_secretos.py` | nuevos | pruebas |
| `docs/adr/20261017-roles-postgresql-y-migraciones.md` | nuevo (ADR-019) | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt`, `docs/02-arquitectura.md`, `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `docs/adr/README.md`, `docs/arranque-local.md`, `docs/convenciones.md` | modificados | documentación |
| `.claude/skills/conv-sql-postgres/SKILL.md`, `.claude/skills/conv-docker/SKILL.md`, `.claude/agents/ingeniero-devsecops.md` | modificados (con aprobación humana, D-8 y D-9) | documentación |

Nada bajo `backend/cimenta/` cambió.

## Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-11 | `test_tkt003_pat8_subida_con_roles_ya_existentes_en_el_cluster` | **rechazo** | `CA-2`, `PA-T8` | ERROR | PASA |
| TC-15 | `test_tkt003_guarda_solo_migra_el_rol_de_migracion` | **rechazo** | `M5` | ERROR | PASA |
| TC-16 | `test_tkt003_ca09_esc01_esquema_por_alembic_y_conexion_de_aplicacion` | feliz | `CA-9` esc. 1 | ERROR | PASA |
| TC-18 | `test_tkt003_rnf07_sin_variable_no_hay_conexion` | **rechazo** | `RNF-07` | FALLA | PASA |
| TC-30 | `test_tkt003_ca05_esc01_roles_sin_atributos_de_privilegio` | **rechazo** | `CA-5` esc. 1 | ERROR | PASA |
| TC-31 | `test_tkt003_ca05_esc02_tabla_posterior_nace_con_permisos` | feliz | `CA-5` esc. 2 | FALLA | PASA |
| TC-32 | `test_tkt003_ca05_esc03_aplicacion_sin_privilegios_de_mas_en_tabla_posterior` | **rechazo** | `CA-5` esc. 3 | FALLA | PASA |
| TC-33 | `test_tkt003_ca05_esc03_aplicacion_sin_create_en_el_esquema` | **rechazo** | `CA-5` esc. 3 | verde (nativo) | PASA |
| TC-33b | `test_tkt003_ca05_esc03_usage_del_esquema_no_depende_de_public` | **rechazo** | `CA-5` | verde (producción ya existía) | PASA |
| TC-40 | `test_tkt003_ca07_esc03_lectura_no_crea_objetos` | **rechazo** | `CA-7` esc. 3 | verde (nativo) | PASA |
| TC-41 | `test_tkt003_ca07_esc01_lectura_consulta_tabla_posterior` | feliz | `CA-7` esc. 1 | FALLA | PASA |
| TC-50 | `test_tkt003_ca08_esc01_tiempos_fijados_en_el_rol` | feliz | `CA-8` esc. 1 | FALLA | PASA |
| TC-50b | `test_tkt003_ca08_esc01_migracion_sin_tiempos_en_este_ticket` | **rechazo** | `CA-8`, D-2 | verde (valor `0`) | PASA |
| TC-51 | `test_tkt003_ca08_esc02_espera_de_bloqueo_se_corta` | **rechazo** | `CA-8` esc. 2 | FALLA | PASA |
| TC-52 | `test_tkt003_ca08_esc03_consulta_larga_se_cancela` | **rechazo** | `CA-8` esc. 3 | FALLA | PASA |
| TC-60 a TC-63 | `test_tkt003_ca10_…` (cuatro casos: entran con su contraseña, sin contraseña no se entra, el script fija desde el entorno, contraseña vacía) | feliz y **rechazo** | `CA-10` | ERROR | PASA |
| TC-64 | `test_tkt003_ca10_esc03_ningun_secreto_en_el_repositorio` | **rechazo** | `CA-10` esc. 3 | FALLA | PASA |
| TC-65 | `test_tkt003_ca11_esc01_env_example_define_lo_que_se_usa` | feliz | `CA-11` esc. 1 | FALLA | PASA |
| — | `test_identidad_migracion_cli.py` (3): `upgrade head` persiste, `downgrade base` revierte, rol distinto se rechaza | feliz y **rechazo** | `CA-2` (ruta real de la CLI) | 2 FALLAN, 1 verde | PASAN |
| TC-10 | `test_tkt003_ca02_esc01_migracion_inicial_sobre_base_vacia` | feliz | `CA-2` esc. 1 | FALLA | PASA |
| TC-12 | `test_tkt003_ca02_esc02_bajada_y_subida_sin_residuos` | **rechazo** | `CA-2` esc. 2 | FALLA | PASA |
| TC-13 | `test_tkt003_ca02_esc03_aplicar_de_nuevo_no_cambia_nada` | **rechazo** | `CA-2` esc. 3 | FALLA | PASA |
| TC-14 | `test_tkt003_ca02_esc04_la_aplicacion_no_puede_migrar` | **rechazo** | `CA-2` esc. 4 | FALLA | PASA |
| TC-17 | `test_tkt003_ca09_esc01_esquema_sin_creacion_automatica` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-20 a TC-22 | `test_tkt003_ca03_esc01` a `esc03` (columnas y tipos, auditoría solo en dos tablas, intento con correo inexistente) | feliz | `CA-3` | FALLA | PASA |
| TC-23 a TC-26, TC-26b | `test_tkt003_ca03_esc04` a `esc07` (correo duplicado, clave de rol duplicada, mismo rol dos veces, claves foráneas a la nada y de auditoría) | **rechazo** | `CA-3` | FALLA | PASA |
| TC-27, TC-28, TC-28b, TC-28c | `test_tkt003_ca04_…` (seis roles sembrados; la siembra no duplica ni inventa; bajar a `0001`; bajar con un rol asignado) | feliz y **rechazo** | `CA-4` | FALLA | PASA |
| TC-34 a TC-37 | `test_tkt003_ca06_esc01` a `esc04` (la aplicación registra y lee; no modifica, no borra y no vacía `intento_acceso`) | feliz y **rechazo** | `CA-6`, invariante 20 | FALLA | PASA |
| TC-38, TC-43 | `test_tkt003_ca07_esc02` y `esc01` (la lectura no escribe en `rol`; sí consulta) | **rechazo** y feliz | `CA-7`, invariante 21 | FALLA | PASA |
| TC-39, TC-42 | `test_tkt003_ca05_esc01_migracion_es_propietaria` y `…esc03_privilegios_exactos_en_identidad` | **rechazo** | `CA-5` | FALLA | PASA |
| TC-44 a TC-46 | `test_tkt003_pat4_…` (siete: la lectura no lee `sesion` ni `password_hash`, por comportamiento y por catálogo; sí lee el resto de `usuario`; la aplicación conserva su acceso) | **rechazo** y feliz | `PA-T4`, D-1 | 4 FALLAN y 3 verdes | PASAN |

TC-01 a TC-03 son comandos de Compose y se registran en la fila 2. TC-70 a TC-72 son demostraciones de la fila 9.

### Ciclo TDD por fila

#### Fila 1 · Dependencias y configuración

Sin tests propios: habilita las siguientes filas. Versiones resueltas: `alembic` 1.20.0, `psycopg[binary]` 3.3.6, `sqlalchemy` 2.1.5; en `dev`, `import-linter` 2.15, `mypy` 2.4.0, `pytest` 9.1.1, `ruff` 0.17.1 y `testcontainers` 4.15.0. Python 3.14.3.

```
uv sync --locked             -> Resolved 37 packages / Audited 36 packages            EXIT=0
uv run pytest                -> collected 0 items (No files were found in testpaths)    EXIT=5
uv run lint-imports          -> Contracts: 14 kept, 0 broken.                           EXIT=0
uv run ruff check . / format -> All checks passed! / 61 files already formatted         EXIT=0
uv run mypy .                -> Success: no issues found in 61 source files             EXIT=0
```

**Refactor:** sin refactor.

#### Fila 2 · Compose y entorno

Sus casos son comandos. **Rojo:** `docker compose up -d db` sin `compose.yaml` → `no configuration file provided: not found`, código 1. **Verde:** `PG_VERSION=18.6-1.pgdg13+2`, `PGDATA=/var/lib/postgresql/18/docker`, volumen declarado en `/var/lib/postgresql`.

```
TC-01  up -d db -> healthy en ~6 s; conexión como cimenta_migracion: SELECT current_user = cimenta_migracion
TC-02  tabla desechable + fila; down (sin -v); up -d db; SELECT n = 1; tabla borrada después
TC-03  docker compose --env-file <vacío> up -d db ->
       required variable CIMENTA_DB_NOMBRE is missing a value: Falta CIMENTA_DB_NOMBRE, copia .env.example a .env
       required variable CIMENTA_DB_CONTRASENA_MIGRACION is missing a value: ...      exit=1; sin contenedor
docker compose config | grep -i password -> solo la contraseña de .env; puerto 127.0.0.1:5432
```

**Refactor:** sin refactor.

#### Fila 3 · Arnés, entorno de Alembic y roles

**Rojo** (`tester-backend`): 3 FAILED y 8 ERROR, todos por las razones esperadas. Los ocho ERROR pasan por la fixture `plantilla_migrada`:

```
E   alembic.util.exc.CommandError: Path doesn't exist: ...\backend\migraciones.
E   ModuleNotFoundError: No module named 'herramientas'                (TC-18)
3 failed, 8 errors in 1.84s
```

**Verde** (`desarrollador-sql`): `herramientas/`, `migraciones/env.py`, `script.py.mako` y `v0001` con §1 y §3.

```
uv run pytest                                -> 11 passed in 2.53s
hasattr(psycopg.pq.PGconn, 'encrypt_password') -> True
```

**Ajuste posterior (⚠):** véase la tabla de ajustes. La CLI no persistía. Rojo: `2 failed, 1 passed` (`assert (None,) == ('alembic_version',)`, con salida 0 y stderr vacío). Verde: `_conexion.commit()` en `env.py`, rama del motor propio. `uv run pytest` → 19 passed. Por la CLI real contra Compose: `alembic upgrade head` deja `alembic_version = 0001`; `downgrade base` la deja con 0 filas.

**Refactor:** sin refactor.

#### Fila 4 · Privilegios por omisión

**Rojo:** `3 failed, 13 passed`. TC-31 (`assert set() == {'DELETE','INSERT','SELECT','UPDATE'}`), TC-32 (precondición `(False,) == (True,)`) y TC-41 (`permission denied for table prueba_permisos`). TC-33 y TC-40 nacen en verde: es la protección nativa de PostgreSQL 15 y posteriores (`PUBLIC` ya no recibe `CREATE` sobre `public`); su prueba de que dependen de algo es el mutante MP-11.

**Verde:** §4 de `_SUBIDA` y sus dos `REVOKE` de `_BAJADA`. `uv run pytest` → 16 passed. Contra Compose, tras `upgrade head`: `pg_default_acl` = `{cimenta_aplicacion=arwd/cimenta_migracion,cimenta_lectura=r/cimenta_migracion}`; tras `downgrade base`: 0 filas, y `nspacl` de `public` ya no nombra a los roles.

**Refactor:** sin refactor.

#### Fila 7 · Tiempos máximos

**Rojo:** `3 failed, 20 passed in 57.28s`. TC-50 (`'lock_timeout': '0' != '5s'`), TC-51 (`DID NOT RAISE LockNotAvailable`: la conexión B espera hasta que la salvaguarda de 30 s cierra A) y TC-52 (`DID NOT RAISE QueryCanceled`).

**Verde:** §2 de `_SUBIDA`, con los valores de D-2: aplicación `5s` y `15s`; lectura `5s` y `60s`; migración sin ninguno. `uv run pytest` → 23 passed. Contra Compose:

```
cimenta_aplicacion | {lock_timeout=5s,statement_timeout=15s}
cimenta_lectura    | {lock_timeout=5s,statement_timeout=60s}
cimenta_migracion  |
```

**Refactor:** sin refactor.

#### Fila 9 (parte A) · Demostraciones de la suite y mutantes

Sin código de producción. TC-70, TC-71 y TC-72:

```
TC-70 (MP-8: la conexión de «aplicación» pasa a cimenta_migracion) -> 7 failed, 16 passed; «no es la del rol de aplicación» 14 veces
TC-71 DATABASE_URL=sqlite:///prueba_tkt003.db; uv run pytest -> código 2: «Solo se admite PostgreSQL (ADR-002)»
TC-72 backend/cimenta/migraciones/__init__.py -> lint-imports código 1: Missing layer in container 'cimenta.migraciones'; borrado, 14 kept
```

Cada mutante se aplicó solo, con el SHA-256 anotado antes y comprobado al restaurar.

| Mutante | Cambio | Rojo |
|---|---|---|
| MP-1 | la aplicación recibe `TRUNCATE` por omisión | TC-31, TC-32 y los dos de CLI. 4 failed |
| MP-3 | se elimina §4 | TC-31, TC-32, TC-41, TC-51 y los dos de CLI. 6 failed |
| MP-4 | la lectura recibe `INSERT` por omisión | TC-31 y los dos de CLI. 3 failed |
| MP-5 | se quita `lock_timeout` de la aplicación | TC-50 y TC-51. 2 failed |
| MP-6 | se quita `statement_timeout` de la aplicación | TC-50 y TC-52. 2 failed |
| MP-7 | la aplicación es miembro del rol de migración | TC-30, la guarda y otros ocho. 10 failed |
| MP-8 | la conexión de aplicación del arnés usa el propietario | la guarda: siete pruebas. 7 failed |
| MP-9 | se quita la guarda de `env.py` | TC-15 y el rechazo de la CLI. 2 failed |
| MP-10 | autenticación `trust` en el contenedor | TC-61. 1 failed |
| MP-11 | `GRANT CREATE ON SCHEMA public` a los dos roles | TC-33 y TC-40. 2 failed |
| MP-12 | `CREATE ROLE` sin condición | TC-11 y `upgrade` por CLI. 2 failed |
| MP-13 | la bajada elimina los roles | `downgrade` por CLI. 1 failed |
| MP-14 | `PASSWORD '…'` en la migración | TC-61 y TC-64. 2 failed |
| MP-16 | el bucle de `pytest_sessionstart` no mira el entorno | suite en verde por diseño; lo detecta TC-71 como comando |
| X-01 a X-07, X-09 a X-12 | mutantes añadidos por el tester (valores de tiempos, atributos de los roles, `commit()`, validación y salida del script) | cada uno pone rojo al menos un caso |
| **X-08** | se quita `GRANT USAGE ON SCHEMA public` | **verde con los 23 tests originales** → falta un test; lo cierra TC-33b. Con el test nuevo: 1 failed |
| X-13 | `default_transaction_read_only = off` en lectura | verde; equivalente (es el valor por omisión), descartado |

**Quedan para la entrega B**, porque necesitan las tablas o la semilla: MP-2 (sin `REVOKE` sobre `intento_acceso`), MP-15 (`usuario_rol` sin unicidad), MP-17 (revocar en lectura `sesion` y `password_hash`), y la variante con `GRANT` por tabla de MP-3. MP-1, MP-4, MP-11, MP-12 y MP-13 se completan en B con TC-37, TC-38, TC-14, TC-10, TC-12 y TC-28. X-08 deberá revisarse contra TC-12 al llegar la semilla.

**Evidencia de ejecución al cerrar** (`docker info` responde, Docker 29.8.2; reejecutada por el orquestador):

```
uv run pytest -q   -> 24 passed in 27.41s
uv run lint-imports -> Contracts: 14 kept, 0 broken.
```

#### Fila 5 · Tablas de identidad e invariante 20

**Rojo:** `20 failed, 24 passed in 28.85s`. Todos por tabla inexistente: `psycopg.errors.UndefinedTable` (`42P01`) o una aserción sobre el catálogo con valores vacíos. Ninguno nació en verde. Con el DDL de la §5 y la §6 copiado a un directorio desechable, los 20 pasan (`20 passed`), lo que prueba que los tests no piden más de lo que el diseño ofrece.

**Verde:** §5 (cinco `CREATE TABLE`) y §6 (`REVOKE UPDATE, DELETE ON intento_acceso FROM cimenta_aplicacion`) de `_SUBIDA`, y los cinco `DROP TABLE` de `_BAJADA`. `uv run pytest` → 44 passed. Contra Compose: las cinco tablas son de `cimenta_migracion`; `has_table_privilege` de la aplicación sobre `intento_acceso` da `UPDATE` falso, `DELETE` falso y `TRUNCATE` falso, y `UPDATE` sobre `usuario` verdadero. `TRUNCATE` no hizo falta revocarlo: los privilegios por omisión no lo conceden.

**Refactor:** sin refactor.

#### Fila 6 · Semilla de los seis roles

**Rojo:** `10 failed, 44 passed in 31.60s`. TC-10, TC-12, TC-13, TC-28, TC-28b y TC-28c: `CommandError: Can't locate revision identified by '0002'`. TC-24: `DID NOT RAISE UniqueViolation`. TC-25: «La tabla rol no tiene COMPRAS». TC-27: la lista de seis filas llega vacía. TC-17: `v0002_semilla_roles_de_negocio.py` faltaba en la lista revisada.

**Verde:** `v0002` con el literal del diseño. Primera pasada: `53 passed, 1 failed` (TC-17).

**Test devuelto al tester:** TC-17 se encontraba a sí mismo porque el nombre de su función contenía la cadena buscada. El desarrollador no tocó el test: lo devolvió. El tester lo renombró y demostró con cinco mutantes desechables que sigue detectando la creación automática del esquema y SQLite. Véase la tabla de ajustes. Tras la corrección: `54 passed`. Contra Compose, `alembic upgrade head` deja `0002 (head)` y `SELECT clave FROM rol` devuelve las seis claves; `downgrade base` deja solo `alembic_version`.

**Refactor:** sin refactor.

#### Fila 8 · `PA-T4`: el rol de lectura no lee sesiones ni `password_hash`

**Rojo:** `5 failed, 56 passed`. TC-44 (`SELECT id`, `SELECT *`, `count(*)` y `SELECT usuario_id` sobre `sesion` devuelven `None` en lugar de `42501`), su comprobación por catálogo (`has_table_privilege` da `True`), TC-45 (igual sobre `password_hash`, con el canal lateral `WHERE password_hash LIKE …`), su catálogo, y TC-42 ajustado. TC-46 nace en verde porque hoy la lectura lo lee todo; su papel es impedir que el verde revoque de más, y se demostró con cinco variantes del verde (A: exacto, 15 de 15 verdes; B a E: cada una pone rojo TC-46 o TC-42).

**Verde:** §7 de `_SUBIDA`: `REVOKE SELECT ON sesion`, `REVOKE SELECT ON usuario` y `GRANT SELECT` por las diez columnas de `usuario` sin `password_hash`. `uv run pytest` → 61 passed. Contra Compose: `has_table_privilege('cimenta_lectura','sesion','SELECT')` falso, `has_column_privilege(… 'password_hash' …)` falso, `email` verdadero.

**Mutación (MP-17), con SHA-256 verificado al restaurar:** (a) sin el `REVOKE` sobre `sesion` → 3 failed (TC-44, su catálogo y TC-42); (b) `password_hash` en el `GRANT` por columnas → 3 failed (TC-45, su catálogo y TC-42); (c) `REVOKE` sin `GRANT` por columnas → 2 failed (TC-46 y TC-42).

**Refactor:** sin refactor.

#### Fila 9 (parte B) · Mutantes de las tablas y de la semilla

Línea base: `61 passed in 31.00 s`, con el SHA-256 de 187 archivos versionables. Los 27 mutantes se aplicaron de uno en uno y todos pusieron la suite en rojo; el SHA coincidió al restaurar en los 27, y la comparación final de SHA de los 187 archivos fue idéntica.

| Mutante | Cambio | Rojo |
|---|---|---|
| MP-2 | se quita el `REVOKE` sobre `intento_acceso` | TC-35, TC-36 y TC-42. 3 failed |
| MP-2b / MP-2c | el `REVOKE` solo de `UPDATE` / solo de `DELETE` | TC-36 y TC-42 / TC-35 y TC-42 |
| MP-15 | sin `uq_usuario_rol_usuario_id_rol_id` | TC-25. 1 failed |
| MP-3 (variante) | sin privilegios por omisión y con `GRANT` por tabla | TC-31, TC-32, TC-41, TC-51 y dos de CLI; **TC-42 sigue verde**, como prevé la spec: las tablas de identidad no notan que falten los privilegios por omisión |
| MP-1, MP-4, MP-11, MP-12, MP-13 | los de la entrega A, completados con las tablas | TC-37 y TC-42; TC-38 y TC-42; TC-14 y TC-12; TC-10, TC-12 y TC-13; TC-12 y TC-28 |
| bajada de `0002` vacía | se borra el `DELETE` de `_BAJADA` | TC-28b |
| UUID, clave o nombre sin acento de un rol; séptimo rol `AUDITOR` | cambios en `v0002` | TC-27 y los de bajada |
| `password_hash` nullable; sin `uq_usuario_email`; sin `uq_rol_clave`; sin `fk_*` (cuatro); `exitoso` sin `NOT NULL`; `activo` con `DEFAULT false`; la aplicación sin `DELETE` por omisión | cambios en `v0001` | cada uno pone rojo al menos un caso (TC-20, TC-23, TC-24, TC-26, TC-31, TC-34 a TC-37, TC-46) |
| X-08 revisado con la semilla | se quita `GRANT USAGE ON SCHEMA public` | solo TC-33b; TC-12 no lo detecta, y es correcto. **Se conserva TC-33b** |
| X-14, X-18 | `_BAJADA` sin `REVOKE USAGE` / sin `DROP TABLE sesion` | TC-12 |

#### Fila 10 · Documentación

Ejecutada por un agente general con `conv-documentacion`, por sustitución: no hay agente redactor. Aplicó las frases literales del diseño en los documentos listados arriba más el ADR-019. Véase «Documentación actualizada».

#### Fila 11 · Cierre en copia limpia

188 archivos de `git ls-files --cached --others --exclude-standard` copiados a un directorio del scratchpad, con `COMPOSE_PROJECT_NAME=cimentalimpia` y el puerto 5433 para no tocar el contenedor del repositorio. El arranque de `docs/arranque-local.md` se ejecutó tal como está escrito. Entorno: 2026-10-18, Windows 11 Pro 10.0.26200; `uv` 0.10.7; Python 3.14.3; Docker Engine 29.8.2 con Compose 5.6.0; PostgreSQL 18.6; Alembic 1.20.0; psycopg 3.3.6; SQLAlchemy 2.1.5; pytest 9.1.1; testcontainers 4.15.0; ruff 0.17.1; mypy 2.4.0; import-linter 2.15; Node v24.22.0 y npm 11.19.1.

```
uv sync --locked / ruff format --check / ruff check / mypy / lint-imports   -> todos EXIT=0 (81 files; 14 kept, 0 broken)
TC-73 (x: int = "a" en tests, herramientas y versions)                        -> mypy EXIT=1 en cada uno; desechables borrados
docker compose up -d db (copia)                                               -> healthy a la primera
TC-79 alembic upgrade head sin variables                                      -> EXIT=1: Falta la variable de entorno CIMENTA_DB_CONTRASENA_MIGRACION
alembic upgrade head / contrasenas_roles / current / downgrade base / upgrade -> EXIT=0; 0002 (head)
conexión con el rol de aplicación                                             -> current_user = cimenta_aplicacion, server 18.6
uv run pytest (TC-81)                                                         -> 61 passed in 31.21s
npm ci, lint, typecheck (frontend)                                            -> EXIT=0
python -m unittest discover -s tools/tests                                    -> Ran 6 tests, OK
docker compose down -v (solo la copia) y copia borrada                        -> EXIT=0
```

Hallazgos de la fila, resueltos antes de cerrarla: TC-83 falló porque `test_identidad_permisos_tablas.py` tenía CRLF (corregido a LF por el tester; hoy ningún archivo del ticket contiene retorno de carro ni BOM, comprobado por bytes por el orquestador); TC-80 falló porque la plantilla de Alembic generaba una revisión que no pasaba `ruff` (corregida en `script.py.mako`; véase la tabla de ajustes). Quedan dos observaciones: `verificar_docs.py` solo admite la excepción de enlaces a `delta.md` de TKT-001 y TKT-002, así que el código 1 por los dos enlaces a `delta.md` de TKT-003 se resuelve con `/sdd-completar`; y `docs/arranque-local.md` no trae un comando literal para conectarse como `cimenta_aplicacion`, así que el cierre lo hizo con `psycopg` en línea.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | `haiku` | `haiku` | — |
| Fila 1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 2 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Ajuste fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Ajuste fila 3 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 7 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 7 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «bloqueo o concurrencia» y «permisos de un rol» |
| Fila 9 (A) | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 6 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 6 · verde | `desarrollador-sql` | `haiku` | `haiku` | Contenido literal; el único fallo era del test |
| Fila 6 · corrección de TC-17 | `tester-backend` | `sonnet` | `sonnet` | Test devuelto por defecto propio |
| Fila 8 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 8 · verde y MP-17 | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 9 (B) | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 10 | agente general, por sustitución | `haiku` | `haiku` | Textos literales del diseño; no hay agente redactor |
| Fila 11 | `ingeniero-devsecops` | `haiku` | `haiku` | Verificable por comando |
| Fila 11 · TC-83 (CRLF) | `tester-backend` | `sonnet` | `haiku` | Corrección mecánica de finales de línea |
| Fila 11 · TC-80 (plantilla) | `desarrollador-sql` | `haiku` | `haiku` | Cambio mínimo en una plantilla, verificado por comando |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-01 a TC-03 |
| `CA-2` | `[M]` | Cumplido. Esc. 1 y 3 se ejecutan con `--env-file ../.env` (decisión D-7, que reinterpreta el comando literal de la spec; se ajusta en `/sdd-completar`) | TC-10 a TC-15; tres casos de CLI |
| `CA-3` | `[M]` | Cumplido | TC-20 a TC-26b |
| `CA-4` | `[M]` | Cumplido | TC-27, TC-28, TC-28b, TC-28c |
| `CA-5` | `[M]` | Cumplido | TC-30 a TC-33b, TC-39, TC-42 |
| `CA-6` | `[M]` | Cumplido | TC-34 a TC-37 |
| `CA-7` | `[M]` | Cumplido | TC-38, TC-40, TC-41, TC-43 |
| `CA-8` | `[M]` | Cumplido | TC-50, TC-50b, TC-51, TC-52 |
| `CA-9` | `[M]` | Cumplido | TC-16, TC-17, TC-70, TC-71 |
| `CA-10` | `[M]` | Cumplido | TC-60 a TC-64 |
| `CA-11` | `[M]` | Cumplido. Esc. 2: las marcas «desde TKT-003» de `docker compose up -d db`, `alembic upgrade head` y `uv run pytest` se retiraron; el comando de Alembic lleva `--env-file ../.env` (D-7) | TC-65, TC-76, TC-79 |
| `CA-R1` | `[M]` | Cumplido | `ruff format --check`, `ruff check` y `mypy` en 0 sobre 81 archivos |
| `CA-R2` | `[M]` | Cumplido | `uv sync --locked` en 0; directas: `alembic`, `psycopg`, `sqlalchemy`; en `dev`, `pytest` y `testcontainers` |
| `CA-R3` | `[M]` | Cumplido | `lint-imports`: 14 kept, 0 broken; TC-72 con un directorio ajeno dentro de `cimenta` |
| `CA-R4` | `[M]` | Cumplido | `uv run fastapi dev` sigue marcado «desde TKT-005»; MinIO, «desde TKT-059» |
| `CA-R5` | `[M]` | Cumplido, con una observación | `verificar_docs.py` y `extraer_mermaid.py`: solo los dos enlaces a `delta.md` de TKT-003, esperados hasta `/sdd-completar` |
| `CA-R6` | `[M]` | Cumplido | TC-83: 24 archivos sin retorno de carro ni BOM, comprobado por bytes; el hook `recordar-caveman.ps1` conserva su BOM. Los tres archivos de `.claude/` modificados conservan CRLF en el árbol de trabajo y el commit los normaliza a LF (véase el último ajuste de 2026-10-18) |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | **APROBADO** (tras 3 ciclos: entrega A, cierre de A y B, y reauditoría focal) | Sin Críticos, Mayores ni Menores abiertos | 3 |
| `auditor-seguridad` | **APROBADO** (tras 3 ciclos: entrega A, cierre de A y B, y reauditoría focal) | N-01 resuelto; F003 a F007 y N-02 a N-04 informativos, fuera de alcance | 3 |

No existe `auditor-sql` en este proyecto: el esquema lo cubren los dos auditores anteriores. Ninguna auditoría devolvió `RIESGOSO`.

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Menor | `impl.md` | `impl.md` solo cubría las filas 1 y 2 cuando se auditó | Resuelto: este archivo se completó con las filas 3, 4, 7 y 9-A, la tabla de mutantes y los ajustes |
| F002 | arquitectura | Menor | `backend/pyproject.toml:8`, `uv.lock` | SQLAlchemy 2.1.5 frente a «2.0» en el stack y en `CLAUDE.md` | Decidido por el usuario el 2026-10-18: se acepta 2.1 y la entrega B actualiza el stack y `CLAUDE.md` a «2.x síncrono»; `delta.md` lo anota |
| F001 | seguridad | Media | `v0001…py:45-46` | Los privilegios por omisión son «hacia abierto»; `cimenta_lectura` leería `sesion` y `password_hash` | Condición de cierre de la entrega B: la fila 8 (`PA-T4`, D-1 aprobada) con TC-44 a TC-46 y el mutante MP-17; cada tabla de módulo trae su `REVOKE` con su prueba |
| F002 | seguridad | Baja | `compose.yaml`, `env.py` | `cimenta_migracion` es superusuario en local; ningún documento fija sus atributos en producción | Entrega B: documentarlo en `arranque-local.md` y en arquitectura §7.6 (local superusuario; producción `NOSUPERUSER` con `CREATEROLE`) |
| F003 | seguridad | Baja | `contrasenas_roles.py:19-21` | El script no rechaza las contraseñas `solo-desarrollo-*` en un entorno real | Fuera de alcance; candidato para TKT-058 |
| F004 | seguridad | Baja | `compose.yaml:7` | Imagen fijada por etiqueta, no por digest | Fuera de alcance; TKT-009 o TKT-058 |
| F005 | seguridad | Baja | `v0001…py:43-46` | `PUBLIC` conserva `CONNECT` y `TEMP` sobre la base | Fuera de alcance; TKT-058 |
| F006 | seguridad | Baja | `pyproject.toml` | `pip-audit` no está en el grupo `dev`; se ejecutó con `uvx` y no halló vulnerabilidades en las 81 líneas del bloqueo | Fuera de alcance; TKT-009 |
| F007 | seguridad | Baja | `v0001…py:49-53` | La bajada no elimina los roles, que conservan `LOGIN` y contraseña (`PA-T8`) | Aceptado; la frase de `arranque-local.md` sobre `docker compose down -v` lo documenta |

**Reauditoría de cierre (entregas A y B).** Seguridad F001 (`PA-T4`): resuelto, con evidencia ejecutada contra PostgreSQL 18.6 (`cimenta_lectura` sin `SELECT` sobre `sesion` y `password_hash`, también por el canal lateral `count(*) WHERE password_hash IS NOT NULL`; la aplicación sin `UPDATE`, `DELETE` ni `TRUNCATE` sobre `intento_acceso`). Seguridad F002: resuelto con reserva, y la reserva fue el hallazgo N-01.

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura (cierre) | Menor | `docs/03-modelo-datos.md:55` | La fila «Columnas de auditoría» quedó sin punto final ni barra de cierre | Resuelto |
| F002 | arquitectura (cierre) | Menor | `docs/02-arquitectura.md` §7.6 | Faltaba la frase del superusuario solo en local, prometida por F002 de seguridad | Resuelto |
| F003 | arquitectura (cierre) | Menor | `docs/03-modelo-datos.md` §13 | Faltaba la consecuencia de `PA-T4` (cada columna nueva de `usuario` necesita su `GRANT`; `SELECT *` falla) | Resuelto; añadida además la regla para tablas futuras con credenciales (N-03) |
| N-01 | seguridad (cierre) | Media | `docs/arranque-local.md:63`, ADR-019 `:61` y `:67` | La documentación decía que en producción basta `NOSUPERUSER` con `CREATEROLE`. **Comprobado en PostgreSQL 18.6: falso.** La migración `0001` falla en `ALTER ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS` con `permission denied to alter role`, porque PostgreSQL solo deja cambiar un atributo a quien lo posee; `LOGIN`, `NOCREATEROLE`, `CREATE ROLE`, `ALTER ROLE … SET`, `GRANT USAGE` y `ALTER DEFAULT PRIVILEGES` sí pasan | Resuelto con texto: hoy la `0001` exige superusuario o un rol que posea esos atributos; `NOSUPERUSER` con `CREATEROLE` queda como objetivo `(asumido)`; TKT-058 decide entre quitar los atributos `NO*` del `ALTER ROLE` o crear los roles con ellos desde el entorno. **Aprendizaje para `delta.md`:** la premisa «`CREATEROLE` basta» del diseño y de D-5 era falsa para el `ALTER ROLE` de endurecimiento; un `CREATE ROLE` sin opciones ya nace con todos los atributos en `NO*`, así que el endurecimiento solo hace falta para roles preexistentes |
| N-02 a N-04 | seguridad (cierre) | Baja | varios | Falta de mención en §7.6 (resuelto con F002); privilegios por omisión «hacia abierto» para tablas futuras (cubierto con la regla de §13); `cimenta_lectura` lee `email` y `origen_ip` de `intento_acceso` | Informativos; N-04 se confirma en el ticket de analítica |

Quedan en `design.md` frases anteriores a N-01 que afirman que `CREATEROLE` basta (líneas ~657, 706, 746 y 767). Es el diseño aprobado, y el aprendizaje va a `delta.md`; no se reescribe.

Observaciones del auditor de arquitectura, sin bloqueo: `prepend_sys_path = ["."]` exige ejecutar Alembic desde `backend/` (se documenta en la entrega B); `_contrasenas_de_roles` solo se llena si la prueba pide `credenciales` (`KeyError` poco claro si no); seis archivos de prueba redefinen el alias `Conectar` en lugar de importar el `Protocol` del `conftest.py`. Quedan para un refactor cuando se toquen esos archivos.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/tests/conftest.py` | Con MP-7, el mensaje de la guarda dice «es cimenta_aplicacion» aunque la causa es la pertenencia al rol de migración. El texto confunde, pero la guarda cae correctamente | Baja |
| `compose.yaml` | `CIMENTA_DB_PUERTO` tiene valor por omisión (`5432`); es el literal del diseño y no es un secreto | Informativa |
| `backend/herramientas/contrasenas_roles.py` | Acepta contraseñas `solo-desarrollo-*` fuera de local. Lo tratan TKT-057 y TKT-058 | Baja (informativa) |
| `backend/migraciones/versions/v0001_identidad_roles_y_esquema.py` | `statement_timeout` y `lock_timeout` son parámetros que el propio rol puede cambiar con `SET`. Son red de seguridad de recursos y no una frontera de seguridad (comprobado: `SET statement_timeout=0` y `pg_sleep(20)` completo) | Baja (informativa) |
| `backend/migraciones/versions/v0001_identidad_roles_y_esquema.py` | `cimenta_aplicacion` conserva `INSERT`, `UPDATE` y `DELETE` sobre `rol` por los privilegios por omisión. Revocar en una migración posterior si ningún caso de uso edita `rol` | Baja (informativa) |
| `sdd/tickets/tkt-003/spec.md` | CA-9 esc. 2, CA-1 y CA-R3 esc. 2 se demuestran por comando o por la guarda del arnés, no por un test automático propio | Baja (informativa) |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `CLAUDE.md` | Comandos con `--env-file ../.env`; marcas «desde TKT-003» retiradas de `uv run pytest`, `alembic upgrade head` y `docker compose up -d db`; «SQLAlchemy 2.x síncrono»; «19 decisiones»; párrafo sobre `migraciones/`, `herramientas/` y `tests/` fuera de `cimenta` |
| `docs/arranque-local.md` | Requisito de Docker; sección «Base de datos»; Alembic desde `backend/`; rol de migración superusuario solo en local `(asumido)` para producción; filas retiradas de «Lo que todavía no arranca» |
| `docs/03-modelo-datos.md` | §2 (permisos y auditoría), §10 (columnas de auditoría y `UNIQUE (usuario_id, rol_id)`), §13 (invariante 21 sin acceso a `sesion` ni `password_hash`) |
| `docs/02-arquitectura.md` | §7.6: fila de lectura y la regla de que solo migra el rol de migración |
| `docs/06-stack-tecnologico.md` | «SQLAlchemy 2.x síncrono» con la nota de 2.1.5; §4.4, §6.5 y §10; fila del ADR-019 |
| `docs/05-tickets-trabajo.md` | Criterio de TKT-003 sobre quién crea los roles (con aprobación humana) |
| `docs/convenciones.md`, `README.md`, `llms.txt`, `docs/adr/README.md` | Estructura del repositorio, conteo de ADR y enlace |
| `docs/adr/20261017-roles-postgresql-y-migraciones.md` | ADR-019, MADR, estado Aceptado |
| `.claude/skills/conv-sql-postgres`, `conv-docker` y `.claude/agents/ingeniero-devsecops.md` | Alineados con los privilegios por omisión, `compose.yaml` y `--env-file` (D-8 y D-9) |

`python tools/verificar_docs.py` → 87 documentos, 19 ADR, solo dos problemas: los enlaces a `delta.md` de `impl.md` y de `_index.md`, que se resuelven con `/sdd-completar`. `python tools/extraer_mermaid.py` → 30 diagramas, código 0; la sintaxis real se valida al abrir la página generada en un navegador, y no se ha hecho.

## Verificación final

Reejecutada por el orquestador el 2026-10-18 sobre el estado final: `uv run pytest -q` → `61 passed in 31.05s`; `ruff check`, `ruff format --check` (81 archivos), `mypy` (81 archivos) y `lint-imports` (14 kept, 0 broken) en verde; ningún archivo nuevo del ticket ni de `docs/` con retorno de carro ni BOM (los tres modificados de `.claude/` conservan CRLF y el commit los normaliza).

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador (los dos tests corregidos fueron obra del tester)
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por garantía de permisos
- [x] Mutación de todas las garantías de permisos, con un test añadido por el mutante que sobrevivía (X-08)
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Todas las auditorías `APROBADO` (arquitectura y seguridad, tras el segundo ciclo de cierre)
- [x] Documentación afectada actualizada en este mismo cambio
- [ ] Rama correcta y sin secretos en el diff (se comprueba con `git-entrega` al completar) (la cierra `git-entrega` al completar)
