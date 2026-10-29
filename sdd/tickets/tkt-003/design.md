# Design · TKT-003 · PostgreSQL, migraciones y esquema de identidad

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

El ticket se resuelve con lo que PostgreSQL, Compose y Alembic ya traen, sin ningún mecanismo propio salvo dos guardas pequeñas. Un único `compose.yaml` en la raíz levanta PostgreSQL 18 con volumen con nombre; el usuario que crea la imagen **es** el rol de migración, y Alembic, configurado en `[tool.alembic]` de `backend/pyproject.toml` y con su entorno en `backend/migraciones/`, fuera del paquete `cimenta`, se niega a correr con cualquier otro rol: así `ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion` cubre de verdad toda tabla futura. La migración inicial crea, de forma idempotente porque son del clúster, los roles de aplicación y de solo lectura **sin contraseña**; fija sus tiempos máximos con `ALTER ROLE … SET`; declara los privilegios por omisión **antes** de crear las cinco tablas, para que las de identidad nazcan por el mismo camino que las de cualquier módulo futuro; y revoca sobre `intento_acceso` lo que el invariante 20 prohíbe. Una segunda migración siembra los seis roles de negocio con identificadores fijos. Las contraseñas se fijan después, por entorno, con un script de `backend/herramientas/` que reutiliza la propia suite. Las pruebas levantan un contenedor por sesión, migran una vez una base plantilla con `alembic upgrade head` y dan a cada prueba una base copiada de ella, con conexiones del rol de aplicación protegidas por una guarda que hace fallar la suite si la conexión es la del propietario.

## Fuentes y verificación de las herramientas

Context7 respondió esta vez. Lo que el diseño toma de cada fuente, y lo que todavía no está verificado y comprueba una fila concreta:

| Librería · fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| Alembic · tutorial y changelog 1.16.0 | Desde 1.16.0 la configuración de código (`script_location`, `prepend_sys_path`, `file_template`) puede vivir en `[tool.alembic]` de `pyproject.toml`; la URL y el registro los consume solo `env.py`, y **Alembic corre sin `alembic.ini`** si solo hay `pyproject.toml`. `%(here)s` es el directorio del `pyproject.toml` | No hay `alembic.ini`. La URL la construye `env.py` desde el entorno. Versión mínima: 1.16 |
| Alembic · recetario «Sharing a Connection» y `Config` | `Config(toml_file=…)`; `cfg.attributes["connection"] = conexion` dentro de `engine.begin()` y `command.upgrade(cfg, "head")`; `env.py` usa esa conexión si existe | Las pruebas migran con el mismo `env.py` que la línea de comandos, pasándole la conexión del rol de migración |
| SQLAlchemy 2.0 · dialecto PostgreSQL y motores | Motor síncrono `postgresql+psycopg://`; `URL.create(...)` evita escapar la contraseña; `poolclass=NullPool` | `env.py` usa `URL.create("postgresql+psycopg", …)` y `NullPool`. Nada asíncrono (ADR-013) |
| psycopg 3 · `psycopg.errors` | Una clase por SQLSTATE (`LockNotAvailable` es `55P03`); `Error.sqlstate` y `Error.diag.constraint_name` | Las pruebas comprueban el SQLSTATE **y** el nombre de la restricción, no solo que haya excepción |
| testcontainers-python · `PostgresContainer` | `PostgresContainer(image, username, password, dbname, driver=None)`; espera a que acepte conexiones al arrancar; `get_container_host_ip()` y `get_exposed_port(5432)`. `sqlalchemy` y `psycopg` ya no son dependencias suyas | El proyecto declara su controlador. Imagen fijada, nunca `latest` |
| pytest · configuración | Desde 9.0 existe `[tool.pytest]` con tipos TOML nativos; `pythonpath` y `testpaths` | Configuración en `[tool.pytest]`. Versión mínima: 9.0 |

**Sin verificar, y lo comprueba la fila indicada.** (a) Que el módulo sea `testcontainers.postgres` y no `testcontainers.community.postgres` en la versión que resuelva `uv`: la documentación muestra los dos (fila 1). (b) Que `psycopg.pq.PGconn.encrypt_password` exista y produzca un verificador SCRAM (fila 3). (c) La etiqueta exacta de la última versión menor de PostgreSQL 18 y que su imagen monte los datos en `/var/lib/postgresql` (fila 2). (d) Que `uv run alembic` encuentre `[tool.alembic]` sin `alembic.ini` desde `backend/` (fila 3). El arquitecto no tiene terminal: cada una lleva su comando de comprobación y, si falla, la regla escrita en su fila, no una decisión del ejecutor.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `compose.yaml` en la raíz, un solo servicio `db` | 5 · objeto nuevo, mínimo | `M1`. En la raíz porque `CLAUDE.md` ya documenta `docker compose up -d db` desde la raíz y porque Compose lee el `.env` del directorio del proyecto, que es donde vive `.env.example`. Se llama `compose.yaml`, el nombre canónico de la especificación de Compose; `docker-compose.yml` también funcionaría y no aporta nada |
| `name: cimenta` en `compose.yaml` | 2 · nativo | Sin él, el proyecto toma el nombre del directorio, «Proyecto Final», y el volumen cambia de nombre según dónde se clone |
| Volumen con nombre `pg_datos` montado en `/var/lib/postgresql` | 2 · nativo | `M1`, datos persistentes. La imagen 18 coloca `PGDATA` en `/var/lib/postgresql/18/docker` y declara el volumen en `/var/lib/postgresql` `(asumido, lo comprueba TC-02)` |
| Contraseña del rol de migración con `${VAR:?mensaje}` | 2 · nativo | `CA-1` esc. 3 y `RNF-07`: Compose aborta y nombra la variable; no hay contraseña por omisión |
| Puerto publicado solo en `127.0.0.1` | 2 · nativo | Higiene de `conv-docker` §2: una base de desarrollo con contraseña evidente no se abre a la red local |
| PostgreSQL **18**, etiqueta menor exacta | 3 · reuso de la imagen oficial | Producción aún no tiene proveedor (TKT-058, `PA-12`). Se elige la versión mayor vigente con la ventana de soporte más larga que ofrecen ya los proveedores gestionados `(asumido)`. La 19, si ya salió, la ofrecen tarde los gestionados `(asumido)`. TKT-058 contrata la misma mayor o cambia una línea de `compose.yaml` |
| Una sola fuente de la imagen para Compose y pruebas | 3 · reuso | `conftest.py` lee la etiqueta de `compose.yaml` con una expresión regular. No hay segunda constante que pueda divergir, y la convención «misma versión mayor que producción» se cumple por construcción |
| Alembic en `backend/migraciones/`, configurado en `[tool.alembic]` | 4 · cambio mínimo | Fuera de `backend/cimenta/`, porque `esqueleto-modulos` es exhaustivo (deuda de TKT-002). Sin `alembic.ini`: la sección en `pyproject.toml` basta desde Alembic 1.16 y la conexión la construye `env.py` |
| `file_template = "v%%(rev)s_%%(slug)s"` | 2 · nativo | Un archivo `0001_….py` no es un nombre de módulo válido y mypy lo rechaza; con la `v` delante, ruff y mypy cubren las migraciones |
| `script.py.mako` propio | 4 · cambio mínimo | `M2`, «sistema de migraciones configurado»: sin plantilla, `alembic revision` falla en el primer ticket de módulo. Se escribe a mano con anotaciones que ruff y mypy aceptan |
| `alembic.ini`, modo sin conexión (`--sql`), `target_metadata` y autogeneración | 1 · YAGNI, fuera | Sin ORM no hay metadatos que comparar; `env.py` rechaza el modo sin conexión con un mensaje. Si TKT-058 necesita SQL para el operador, se añade allí |
| Guarda de `env.py`: solo migra `cimenta_migracion` | 5 · objeto nuevo, mínimo | Es la que hace verdad `M5`. `ALTER DEFAULT PRIVILEGES` solo afecta a los objetos que crea el rol sobre el que se declara: si otro rol migrara, sus tablas nacerían sin permisos para la aplicación y ninguna prueba de las tablas existentes lo notaría (objeción 1 de la spec). Seis líneas que comparan `current_user` |
| Controlador `psycopg` 3 (`psycopg[binary]`) | 3 · reuso | Es el controlador síncrono de primera clase de SQLAlchemy 2.0 (`postgresql+psycopg`). `psycopg2` está en mantenimiento. `[binary]` evita compilar en Windows; si TKT-058 prefiere `[c]` para la imagen, es una línea |
| `sqlalchemy` como dependencia directa | 3 · reuso | Ya llega como dependencia de Alembic, pero `env.py` y `herramientas/` la importan: una importación directa se declara |
| Modelos ORM de `identidad` (`PA-T11`) | 1 · YAGNI, fuera | Ningún criterio los necesita: las tablas se verifican contra el catálogo y con SQL directo. Los escribe TKT-006, que es el primero que lee y escribe estas tablas |
| Base `cimenta` y roles `cimenta_migracion`, `cimenta_aplicacion`, `cimenta_lectura` | 5 · nombres nuevos | Prefijo `cimenta_` para no chocar con otros roles del clúster gestionado; español del glosario; «lectura» y no «analitica», porque el rol es una propiedad de la conexión y no del módulo. Los nombres de rol son **constantes, no variables de entorno**: no son secretos, y que cambien por entorno rompería la guarda y las pruebas |
| Seis variables `CIMENTA_DB_*` | 5 · objeto nuevo, mínimo | `HOST`, `PUERTO`, `NOMBRE` y una `CONTRASENA_*` por rol. Partes y no URL, para que `URL.create` escape la contraseña. Prefijo propio para no chocar con `DATABASE_URL` u otras del sistema |
| Carga de `.env` con `uv run --env-file ../.env` | 2 · nativo | `uv` lo hace sin dependencia. `python-dotenv` añadiría una dependencia de ejecución para algo que en producción inyecta el entorno; `pydantic-settings` llega con TKT-057 y TKT-059 |
| Creación de los dos roles con `DO … IF NOT EXISTS` y `ALTER ROLE` posterior | 2 · nativo | `PA-T8`: los roles son del clúster y la suite crea varias bases en el mismo clúster. El `ALTER ROLE` posterior fuerza los atributos aunque el rol ya existiera con otros |
| Rol de migración creado por el arranque del entorno, no por la migración | 2 · nativo | Una migración no puede crear el rol con el que ya está conectada. En local y en pruebas lo crea la imagen (`POSTGRES_USER`), como fija `conv-docker` §2; en producción, el operador `(asumido, PA-T3)`. Ver la decisión D-5 |
| `GRANT USAGE ON SCHEMA public` explícito | 4 · cambio mínimo | PostgreSQL 15 y posteriores ya dan `USAGE` a `PUBLIC`, pero un gestionado endurecido puede quitarlo. Una línea, y no depende de `PUBLIC` |
| `ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public` | 2 · nativo | `M5`. Se declara **antes** de crear las tablas de identidad: así estas se prueban por el mismo camino que las de cualquier módulo. Sin secuencias ni funciones: las claves son UUID |
| `REVOKE UPDATE, DELETE ON intento_acceso FROM cimenta_aplicacion` | 2 · nativo | `M6`, invariante 20. `TRUNCATE` no se revoca porque los privilegios por omisión nunca lo conceden; `CA-6` esc. 4 lo prueba |
| `REVOKE CREATE ON SCHEMA public FROM PUBLIC` | 1 · YAGNI, fuera | PostgreSQL 15 y posteriores ya no conceden `CREATE` a `PUBLIC`, y la imagen es 18. TC-33 y TC-40 lo comprueban; si TKT-058 contrata un gestionado que lo concede, ahí se añade |
| `ALTER ROLE … SET lock_timeout / statement_timeout` en aplicación y lectura | 2 · nativo | `M8` y `RNF-16`: el rol, no cada conexión, y así aplica aunque una ruta nueva no lo pida. Valores en D-2 |
| Tiempos máximos del rol de migración | 1 · YAGNI, fuera | En desarrollo no hay carga concurrente que una migración pueda bloquear. Fijar `lock_timeout` al migrar contra producción es de TKT-058, que conoce la carga real. Ver D-2 |
| Cinco tablas con DDL escrito a mano y restricciones con nombre | 5 · objetos nuevos | `M3`. SQL literal y no `op.create_table`: los nombres de restricción y los tipos quedan a la vista de quien revisa, como pide `conv-sql-postgres` §4 |
| Columnas de auditoría solo en `usuario` y `usuario_rol`, con `*_por_id` nulos y clave foránea a `usuario` | 5 · columnas nuevas | Decisión del usuario (`PA-T1`). La clave foránea es intra-módulo y no invierte ninguna arista |
| `UNIQUE (usuario_id, rol_id)` en `usuario_rol` | 2 · nativo | Decisión del usuario (`PA-T2`) |
| Índices sobre `sesion.usuario_id`, `intento_acceso.usuario_id`, `intento_acceso.email` y `usuario_rol.rol_id` | 1 · YAGNI, fuera | Ningún criterio filtra por ellos todavía. Los fijan TKT-006 y TKT-057 con sus consultas reales y un `EXPLAIN`. La unicidad de `usuario_rol` ya indexa por `usuario_id` |
| `origen_ip` como `text` y no `inet` | 4 · cambio mínimo | El modelo dice `string`. Cambiar el tipo es una decisión de TKT-006, que es quien lo escribe |
| Semilla en su propia migración, `0002`, con UUID fijos | 5 · objeto nuevo, mínimo | `M4`. `conv-sql-postgres` §4 dice a la vez «una migración por ticket» y «los datos semilla van en su propia migración […], nunca mezclados con DDL»: en un ticket con semilla las dos no caben juntas, y se sigue la más específica. Se lee como «una migración de esquema por ticket, más la de semilla si la hay», y la aclaración se propone para la convención en D-8. UUID fijos para que todos los entornos tengan las mismas filas y `CA-2` esc. 2 compare datos idénticos tras bajar y subir. Las reglas futuras buscan el rol por `clave`, nunca por `id` |
| Purga y `DELETE` sobre `sesion` (`PA-T6`, `PA-T7`) | 1 · YAGNI, fuera | Ningún invariante la exige hoy; revocar `DELETE` sin un rol de purga sería inventar una regla. Se queda el permiso por omisión, `(asumido)` |
| Revocar el `SELECT` del rol de lectura sobre `sesion` y `usuario.password_hash` (`PA-T4`) | 2 · nativo, **pendiente del gate** | Recomendado. Fila 8 y D-1 |
| `backend/herramientas/` con `conexion.py` y `contrasenas_roles.py` | 5 · objeto nuevo, mínimo | Decisión del usuario: la contraseña se fija por entorno. El script la fija en local y **la misma función** la usa la suite, así que lo que se prueba es lo que se ejecuta. Fuera de `cimenta/`, como Alembic |
| Contraseña enviada ya cifrada en SCRAM | 2 · nativo | `PGconn.encrypt_password` de libpq: el texto plano no llega al servidor ni a su registro de sentencias `(asumido, lo comprueba la fila 3)` |
| Script en `docker-entrypoint-initdb.d` para crear roles o contraseñas | 1 · YAGNI, fuera | Prohibido por `conv-docker` §2: sacaría los permisos de la migración y dejaría producción sin ellos |
| `--import-mode=importlib` y nombres base únicos en `tests/` | 2 · nativo | Es el modo que pytest recomienda para proyectos nuevos; los nombres únicos los exige mypy sin `__init__.py`, y la regla queda escrita en «Pruebas» |
| pytest y testcontainers (`PA-T12`) | 3 · reuso | Son los del stack (§7.1). Se habilita aquí `uv run pytest`. Sin `pytest-timeout`, `pytest-env` ni `pytest-xdist`: ningún criterio los pide |
| Aislamiento por base copiada de una plantilla | 2 · nativo | `CREATE DATABASE … TEMPLATE` copia esquema, permisos y privilegios por omisión en fracciones de segundo. Deshacer una transacción envolvente no sirve: la prueba de `55P03` necesita una fila confirmada visible desde otra conexión, y `CA-2` cambia el esquema |
| Guarda de conexión de aplicación en `conftest.py` | 5 · objeto nuevo, mínimo | `CA-9` esc. 2. Comprueba `current_user`, que no sea superusuario y que no sea miembro del rol de migración |
| Guarda contra SQLite en `pytest_sessionstart` | 5 · objeto nuevo, mínimo | `CA-9` esc. 3. La suite no admite ninguna URL externa —siempre usa testcontainers—, así que la garantía real es que no hay perilla; la guarda convierte en error explícito el intento de dársela |

Ningún objeto que paró en el peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`.

## Capas afectadas

El ticket no escribe dominio, casos de uso, API ni frontend, y no toca nada bajo `backend/cimenta/`.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `cimenta_aplicacion` | rol | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`, sin contraseña, sin pertenencia a ningún rol. `lock_timeout = '5s'`, `statement_timeout = '15s'` (D-2) |
| `cimenta_lectura` | rol | Mismos atributos. `lock_timeout = '5s'`, `statement_timeout = '60s'` (D-2) |
| `cimenta_migracion` | rol | No lo crea la migración: es `POSTGRES_USER` en local y en pruebas, y el rol del operador en producción. Propietario de todo lo que crean las migraciones, incluida `alembic_version`, sobre la que los otros dos no tienen ningún privilegio |
| Privilegios por omisión | `pg_default_acl` | Para tablas que cree `cimenta_migracion` en `public`: aplicación `SELECT, INSERT, UPDATE, DELETE`; lectura `SELECT`. Nunca `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN` |
| `usuario`, `rol`, `usuario_rol`, `sesion`, `intento_acceso` | tablas | DDL literal más abajo |
| `pk_*`, `uq_usuario_email`, `uq_rol_clave`, `uq_usuario_rol_usuario_id_rol_id`, `fk_<tabla>_<columna>` | restricciones | Convención de nombres: `fk_<tabla>_<columna>` |
| `v0001_identidad_roles_y_esquema.py` | migración | Revisión `0001` |
| `v0002_semilla_roles_de_negocio.py` | migración | Revisión `0002`, semilla |

**Migración `0001`:** reversible: sí · destructiva: no en la subida; la bajada elimina las cinco tablas con sus datos · plan de reversa: `downgrade` elimina en esta base todo lo que la subida creó —tablas, privilegios por omisión y `USAGE` sobre el esquema— y **no elimina los dos roles ni sus tiempos máximos**, que son del clúster y pueden estar en uso por otra base (`PA-T8`). Una nueva subida los encuentra y los converge con `ALTER ROLE`. Quien quiera quitarlos del clúster local lo hace con `docker compose down -v`.

**Migración `0002`:** reversible: sí · destructiva: la bajada borra las seis filas por su `id`, y falla con `23503` si algún usuario ya tiene asignado uno de esos roles, que es lo correcto.

#### Contenido exacto de `backend/migraciones/versions/v0001_identidad_roles_y_esquema.py`

Cabecera y estructura:

```python
"""TKT-003 · Roles de PostgreSQL, privilegios por omisión y esquema de identidad.

Revisión: 0001
Anterior: ninguna

La ejecuta solo cimenta_migracion (lo exige env.py). Los roles son del clúster:
la subida los crea si no existen y la bajada no los elimina (PA-T8).
Cada sentencia va en su propia llamada a op.execute: con parámetros vacíos,
psycopg usa el protocolo extendido, que no admite varias sentencias juntas.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBIDA: tuple[str, ...] = (
    # §1 · roles (fila 3) … §7 · PA-T4 (fila 8), en este orden
)

_BAJADA: tuple[str, ...] = (
    # en el orden de más abajo
)


def upgrade() -> None:
    for sentencia in _SUBIDA:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _BAJADA:
        op.execute(sentencia)
```

Cada sentencia de `_SUBIDA` es una cadena; las secciones se añaden en la fila indicada y **en este orden dentro de la tupla**, aunque se escriban en filas distintas. Ninguna sentencia lleva `%` ni `:nombre`.

```sql
-- §1 · Roles, idempotente porque son del clúster (fila 3)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'cimenta_aplicacion') THEN
        CREATE ROLE cimenta_aplicacion;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'cimenta_lectura') THEN
        CREATE ROLE cimenta_lectura;
    END IF;
END
$$
ALTER ROLE cimenta_aplicacion WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
ALTER ROLE cimenta_lectura WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS

-- §2 · Tiempos máximos, RNF-16 (fila 7)
ALTER ROLE cimenta_aplicacion SET lock_timeout = '5s'
ALTER ROLE cimenta_aplicacion SET statement_timeout = '15s'
ALTER ROLE cimenta_lectura SET lock_timeout = '5s'
ALTER ROLE cimenta_lectura SET statement_timeout = '60s'

-- §3 · Esquema (fila 3)
GRANT USAGE ON SCHEMA public TO cimenta_aplicacion, cimenta_lectura

-- §4 · Privilegios por omisión, antes de cualquier tabla (fila 4)
ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cimenta_aplicacion
ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public GRANT SELECT ON TABLES TO cimenta_lectura

-- §5 · Tablas de identidad (fila 5)
CREATE TABLE usuario (
    id                 uuid        NOT NULL,
    nombre             text        NOT NULL,
    email              text        NOT NULL,
    password_hash      text        NOT NULL,
    activo             boolean     NOT NULL DEFAULT true,
    ultimo_acceso      timestamptz,
    bloqueado_hasta    timestamptz,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    creado_por_id      uuid,
    actualizado_en     timestamptz NOT NULL DEFAULT now(),
    actualizado_por_id uuid,
    CONSTRAINT pk_usuario PRIMARY KEY (id),
    CONSTRAINT uq_usuario_email UNIQUE (email),
    CONSTRAINT fk_usuario_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id)
)
CREATE TABLE rol (
    id     uuid NOT NULL,
    clave  text NOT NULL,
    nombre text NOT NULL,
    CONSTRAINT pk_rol PRIMARY KEY (id),
    CONSTRAINT uq_rol_clave UNIQUE (clave)
)
CREATE TABLE usuario_rol (
    id                 uuid        NOT NULL,
    usuario_id         uuid        NOT NULL,
    rol_id             uuid        NOT NULL,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    creado_por_id      uuid,
    actualizado_en     timestamptz NOT NULL DEFAULT now(),
    actualizado_por_id uuid,
    CONSTRAINT pk_usuario_rol PRIMARY KEY (id),
    CONSTRAINT uq_usuario_rol_usuario_id_rol_id UNIQUE (usuario_id, rol_id),
    CONSTRAINT fk_usuario_rol_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_rol_rol_id FOREIGN KEY (rol_id) REFERENCES rol (id),
    CONSTRAINT fk_usuario_rol_creado_por_id FOREIGN KEY (creado_por_id) REFERENCES usuario (id),
    CONSTRAINT fk_usuario_rol_actualizado_por_id FOREIGN KEY (actualizado_por_id) REFERENCES usuario (id)
)
CREATE TABLE sesion (
    id               uuid        NOT NULL,
    usuario_id       uuid        NOT NULL,
    creada_en        timestamptz NOT NULL DEFAULT now(),
    expira_en        timestamptz NOT NULL,
    ultima_actividad timestamptz NOT NULL DEFAULT now(),
    revocada_en      timestamptz,
    origen_ip        text,
    agente_usuario   text,
    CONSTRAINT pk_sesion PRIMARY KEY (id),
    CONSTRAINT fk_sesion_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id)
)
CREATE TABLE intento_acceso (
    id          uuid        NOT NULL,
    email       text        NOT NULL,
    usuario_id  uuid,
    exitoso     boolean     NOT NULL,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    origen_ip   text,
    CONSTRAINT pk_intento_acceso PRIMARY KEY (id),
    CONSTRAINT fk_intento_acceso_usuario_id FOREIGN KEY (usuario_id) REFERENCES usuario (id)
)

-- §6 · Lo que la tabla no admite, invariante 20 (fila 5)
REVOKE UPDATE, DELETE ON intento_acceso FROM cimenta_aplicacion

-- §7 · Solo si el gate aprueba PA-T4 (fila 8)
REVOKE SELECT ON sesion FROM cimenta_lectura
REVOKE SELECT ON usuario FROM cimenta_lectura
GRANT SELECT (id, nombre, email, activo, ultimo_acceso, bloqueado_hasta, creado_en, creado_por_id, actualizado_en, actualizado_por_id) ON usuario TO cimenta_lectura
```

`_BAJADA`, en este orden; cada fila añade las suyas en su sitio:

```sql
DROP TABLE intento_acceso                                         -- fila 5
DROP TABLE sesion                                                 -- fila 5
DROP TABLE usuario_rol                                            -- fila 5
DROP TABLE rol                                                    -- fila 5
DROP TABLE usuario                                                -- fila 5
ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public REVOKE SELECT ON TABLES FROM cimenta_lectura                         -- fila 4
ALTER DEFAULT PRIVILEGES FOR ROLE cimenta_migracion IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM cimenta_aplicacion -- fila 4
REVOKE USAGE ON SCHEMA public FROM cimenta_aplicacion, cimenta_lectura                                                                    -- fila 3
```

La bajada no lleva sentencias de §1, §2 ni §7: los roles y sus tiempos se quedan (`PA-T8`), y los privilegios de §6 y §7 desaparecen con sus tablas.

#### Contenido exacto de `backend/migraciones/versions/v0002_semilla_roles_de_negocio.py`

Misma estructura, con `revision = "0002"`, `down_revision = "0001"` y docstring `"""TKT-003 · Los seis roles de negocio del PRD §4, con identificadores fijos."""` más la línea `Revisión: 0002 · Anterior: 0001`. Una sentencia en cada sentido:

```sql
INSERT INTO rol (id, clave, nombre) VALUES
    ('c1e0a000-0000-4000-8000-000000000001', 'DIRECCION_GENERAL', 'Dirección General'),
    ('c1e0a000-0000-4000-8000-000000000002', 'DIRECTOR_PROYECTOS', 'Director de Proyectos'),
    ('c1e0a000-0000-4000-8000-000000000003', 'RESIDENTE', 'Residente de obra'),
    ('c1e0a000-0000-4000-8000-000000000004', 'COMPRAS', 'Compras'),
    ('c1e0a000-0000-4000-8000-000000000005', 'ALMACEN', 'Almacén'),
    ('c1e0a000-0000-4000-8000-000000000006', 'ADMINISTRACION', 'Administración')

DELETE FROM rol WHERE id IN ('c1e0a000-0000-4000-8000-000000000001', 'c1e0a000-0000-4000-8000-000000000002', 'c1e0a000-0000-4000-8000-000000000003', 'c1e0a000-0000-4000-8000-000000000004', 'c1e0a000-0000-4000-8000-000000000005', 'c1e0a000-0000-4000-8000-000000000006')
```

Los nombres legibles son los de la tabla del PRD §4. Los UUID son de versión 4 con la variante RFC 4122 y un prefijo reconocible; ninguna regla ni prueba futura debe buscar un rol por ellos, sino por `clave`.

### Entorno de migraciones

**`backend/migraciones/env.py`**, completo salvo docstrings:

```python
"""Entorno de Alembic de CIMENTA (TKT-003).

Solo migra cimenta_migracion: ALTER DEFAULT PRIVILEGES se declara para ese rol,
y una tabla creada por otro nacería sin los permisos de la aplicación.
"""

from alembic import context
from sqlalchemy import Connection, create_engine, pool, text

from herramientas.conexion import ROL_MIGRACION, url_migracion


def _exigir_rol_de_migracion(conexion: Connection) -> None:
    actual = conexion.execute(text("SELECT current_user")).scalar_one()
    if actual != ROL_MIGRACION:
        raise RuntimeError(
            f"Las migraciones de CIMENTA las ejecuta solo {ROL_MIGRACION}, y esta conexión es "
            f"{actual}. Los privilegios por omisión no cubrirían las tablas que cree otro rol."
        )


def _migrar(conexion: Connection) -> None:
    _exigir_rol_de_migracion(conexion)
    context.configure(connection=conexion, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("CIMENTA no genera SQL sin conexión: las migraciones se aplican contra la base.")

_externa = context.config.attributes.get("connection")
if _externa is not None:
    _migrar(_externa)
else:
    _motor = create_engine(url_migracion(), poolclass=pool.NullPool)
    with _motor.connect() as _conexion:
        _migrar(_conexion)
```

**`backend/migraciones/script.py.mako`**: la misma cabecera que las dos migraciones, con `${message}`, `Revisión: ${up_revision}`, `Anterior: ${down_revision | comma,n}`, las cuatro variables anotadas como en `v0001` usando `${repr(up_revision)}`, `${repr(down_revision)}`, `${repr(branch_labels)}` y `${repr(depends_on)}`, la importación `from alembic import op` seguida de `${imports if imports else ""}`, y `upgrade()` y `downgrade()` con `${upgrades if upgrades else "pass"}` y `${downgrades if downgrades else "pass"}`, ambas con `-> None`.

**`backend/herramientas/__init__.py`**: una línea, `"""Herramientas de operación de CIMENTA, fuera del paquete cimenta: no son código de la aplicación."""`.

**`backend/herramientas/conexion.py`**:

| Nombre | Firma o valor | Comportamiento |
|---|---|---|
| `ROL_MIGRACION`, `ROL_APLICACION`, `ROL_LECTURA` | `Final[str]`: `"cimenta_migracion"`, `"cimenta_aplicacion"`, `"cimenta_lectura"` | — |
| `leer_variable` | `(nombre: str) -> str` | Devuelve `os.environ[nombre]`. Si falta o está vacía, `RuntimeError` con el texto `Falta la variable de entorno {nombre}. Cópiala de .env.example a .env y ejecuta con: uv run --env-file ../.env …`. Nunca un valor por omisión |
| `url_migracion` | `() -> URL` | `URL.create("postgresql+psycopg", username=ROL_MIGRACION, password=leer_variable("CIMENTA_DB_CONTRASENA_MIGRACION"), host=leer_variable("CIMENTA_DB_HOST"), port=int(leer_variable("CIMENTA_DB_PUERTO")), database=leer_variable("CIMENTA_DB_NOMBRE"))` |

**`backend/herramientas/contrasenas_roles.py`**:

| Nombre | Firma | Comportamiento |
|---|---|---|
| `fijar_contrasenas` | `(conexion: psycopg.Connection[Any], *, aplicacion: str, lectura: str) -> None` | Docstring: «Fija por entorno las contraseñas que la migración no pone (RNF-07, decisión del 2026-10-17).» Para `(ROL_APLICACION, aplicacion)` y `(ROL_LECTURA, lectura)`: si la contraseña está vacía, `ValueError(f"La contraseña de {rol} está vacía")` **antes** de ejecutar nada; si no, `cifrada = conexion.pgconn.encrypt_password(contrasena.encode(), rol.encode(), b"scram-sha-256").decode()` y `conexion.execute(sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(sql.Identifier(rol), sql.Literal(cifrada)))`. La conexión llega en `autocommit` |
| `main` | `() -> int` | Lee con `leer_variable` `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO`, `CIMENTA_DB_NOMBRE`, `CIMENTA_DB_CONTRASENA_MIGRACION`, `CIMENTA_DB_CONTRASENA_APLICACION` y `CIMENTA_DB_CONTRASENA_LECTURA`; abre `psycopg.connect(host=…, port=…, dbname=…, user=ROL_MIGRACION, password=…, autocommit=True)`; llama a `fijar_contrasenas`; imprime exactamente `Contraseñas fijadas para cimenta_aplicacion y cimenta_lectura.` y devuelve `0`. **Nunca imprime ni registra una contraseña** |
| bloque final | `if __name__ == "__main__": raise SystemExit(main())` | Se ejecuta con `uv run --env-file ../.env python -m herramientas.contrasenas_roles` desde `backend/` |

Si la fila 3 comprueba que `encrypt_password` no existe en la versión resuelta, se envía `sql.Literal(contrasena)` sin cifrar, se anota en `impl.md` y el riesgo queda en `delta.md`; no se busca otra vía.

### Configuración y entorno

**`compose.yaml`**, en la raíz, literal salvo la etiqueta menor, que fija la fila 2:

```yaml
# PostgreSQL local de CIMENTA (TKT-003). El backend y el frontend corren en el anfitrión.
# El usuario de la imagen es el rol de migración; los otros dos los crea la migración.
name: cimenta

services:
  db:
    image: postgres:18.<menor>
    environment:
      POSTGRES_USER: cimenta_migracion
      POSTGRES_PASSWORD: ${CIMENTA_DB_CONTRASENA_MIGRACION:?Falta CIMENTA_DB_CONTRASENA_MIGRACION, copia .env.example a .env}
      POSTGRES_DB: ${CIMENTA_DB_NOMBRE:?Falta CIMENTA_DB_NOMBRE, copia .env.example a .env}
    ports:
      - "127.0.0.1:${CIMENTA_DB_PUERTO:-5432}:5432"
    volumes:
      - pg_datos:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cimenta_migracion -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 12

volumes:
  pg_datos:
```

No se fija `POSTGRES_HOST_AUTH_METHOD`. Según la documentación de la imagen oficial, con `POSTGRES_PASSWORD` definida y sin ese parámetro las conexiones por red se autentican con contraseña `(asumido, no verificado con Context7)`; la prueba empírica de que un rol sin contraseña no entra es TC-61, y MP-10 demuestra que el caso depende de ello (`CA-10` esc. 2). Dentro del contenedor, por el socket local, la imagen confía en el usuario: es el acceso de `docker compose exec` y no es una conexión por red.

**`.env.example`**: tras el bloque de comentarios actual, sin tocarlo, se añade:

```dotenv

# --- Base de datos · TKT-003 --------------------------------------------------
# PostgreSQL local del servicio db de compose.yaml. Valores de desarrollo,
# evidentes a propósito: en cualquier otro entorno se sustituyen.
CIMENTA_DB_HOST=127.0.0.1
CIMENTA_DB_PUERTO=5432
CIMENTA_DB_NOMBRE=cimenta
# Rol de migración (propietario). Lo crea la imagen en el primer arranque.
CIMENTA_DB_CONTRASENA_MIGRACION=solo-desarrollo-migracion
# Roles de aplicación y de solo lectura. La migración los crea sin contraseña;
# se fijan después, desde backend/:
#   uv run --env-file ../.env python -m herramientas.contrasenas_roles
CIMENTA_DB_CONTRASENA_APLICACION=solo-desarrollo-aplicacion
CIMENTA_DB_CONTRASENA_LECTURA=solo-desarrollo-lectura
```

**`backend/pyproject.toml`**: las dependencias se añaden con `uv add` (fila 1), nunca a mano. Después, al final del archivo y tras el último contrato de `import-linter`, este bloque literal. `[tool.ruff]`, `[tool.mypy]` y `[tool.importlinter]` no se tocan, salvo la regla de la fila 1 sobre `testcontainers`.

```toml
[tool.alembic]
script_location = "%(here)s/migraciones"
prepend_sys_path = ["."]
file_template = "v%%(rev)s_%%(slug)s"

[tool.pytest]
minversion = "9.0"
testpaths = ["tests"]
pythonpath = ["."]
addopts = ["-ra", "--strict-markers", "--import-mode=importlib"]
```

### Pruebas

**Regla de nombres en `backend/tests/` (en adelante, para todos los tickets).** Los archivos de prueba no llevan `__init__.py` y su nombre base es **único en todo el árbol de pruebas**, aunque vivan en subdirectorios. pytest corre con `--import-mode=importlib`, que la documentación de pytest recomienda para proyectos nuevos y que no altera `sys.path` al importar las pruebas; por sí solo admitiría nombres repetidos. Quien los prohíbe es mypy: sin paquetes, `uv run mypy .` toma cada archivo como un módulo de nivel superior y rechaza dos con el mismo nombre (`Duplicate module named`). Es la propia herramienta la que hace cumplir la regla, y se descarta cambiar la configuración de mypy de TKT-001 (`explicit_package_bases`) para relajarla. `herramientas` sí es paquete y se importa gracias a `pythonpath = ["."]`, que el modo `importlib` no sustituye.

Archivos nuevos en `backend/tests/`: `conftest.py`, `test_identidad_migracion.py`, `test_identidad_esquema.py`, `test_identidad_permisos.py`, `test_identidad_tiempos.py` y `test_identidad_credenciales.py`. Los nombres de prueba siguen `test_tkt003_<criterio>_<escenario>_<descripción>`: el ticket no tiene historia de usuario y el verificador de TKT-009 solo mira escenarios `HDU`.

**`conftest.py`** — lo escribe `tester-backend`, con estas piezas y estos nombres:

| Pieza | Alcance | Qué hace |
|---|---|---|
| `pytest_sessionstart(session)` | hook | Si `DATABASE_URL` o cualquier variable que empiece por `CIMENTA_DB_` contiene `sqlite` (sin distinguir mayúsculas), `pytest.exit(f"Solo se admite PostgreSQL (ADR-002): la variable {nombre} apunta a SQLite.", returncode=2)` |
| `_imagen_postgres()` | función privada | Lee `compose.yaml` de la raíz del repositorio y devuelve la única coincidencia de `^\s*image:\s*(postgres:\S+)\s*$` en modo multilínea. Si hay cero o más de una, falla con un mensaje que lo dice |
| `contenedor_postgres` | sesión | `PostgresContainer(_imagen_postgres(), username="cimenta_migracion", password=secrets.token_urlsafe(24), dbname="cimenta_plantilla", driver=None)`; arranca, cede y para. Sin Docker, falla: nunca se salta |
| `plantilla_migrada` | sesión | Migra `cimenta_plantilla` con `alembic upgrade head` a través de `migrar`. Al terminar no queda **ninguna** conexión abierta a la plantilla, o `CREATE DATABASE … TEMPLATE` fallaría |
| `observacion_sin_contrasena` | sesión | Depende de `plantilla_migrada` y corre **antes** de fijar contraseñas. Lee `rolname, rolpassword IS NULL` de `pg_authid` para los dos roles, e intenta conectar por TCP a la base `postgres` con cada rol y con las contraseñas `""` y `"cualquiera"`. Devuelve un `dataclass` congelado con los cuatro resultados: la clase de la excepción y su mensaje, o el aviso de que conectó |
| `credenciales` | sesión | Depende de `observacion_sin_contrasena`. Genera dos contraseñas con `secrets.token_urlsafe(24)` y las fija con `herramientas.contrasenas_roles.fijar_contrasenas` sobre una conexión del rol de migración a la base `postgres`. Importa `herramientas` **dentro** de la función. Devuelve `dict[str, str]` con las claves `migracion`, `aplicacion` y `lectura` |
| `migrar` | sesión, fábrica | `migrar(base: str, destino: str = "head", sentido: Literal["upgrade", "downgrade"] = "upgrade", rol: str = "cimenta_migracion") -> None`. Motor `URL.create("postgresql+psycopg", …)` con `NullPool`; `with motor.begin() as conexion:`; `Config(toml_file=<backend>/pyproject.toml)`, `cfg.attributes["connection"] = conexion` y `command.upgrade` o `command.downgrade`; `motor.dispose()`. El parámetro `rol` existe solo para TC-15 |
| `base_de_prueba` | función | `CREATE DATABASE prueba_<12 hex> TEMPLATE cimenta_plantilla` desde una conexión `autocommit` del rol de migración a `postgres`; cede el nombre; al final cierra las conexiones abiertas por `conectar` y ejecuta `DROP DATABASE … WITH (FORCE)` |
| `base_vacia` | función | Igual, sin `TEMPLATE`: una base sin ninguna tabla de CIMENTA en el mismo clúster, donde los roles ya existen |
| `conectar` | función, fábrica | `conectar(rol: Literal["migracion", "aplicacion", "lectura"], base: str, autocommit: bool = True) -> psycopg.Connection[tuple[Any, ...]]`. Usuario `cimenta_<rol>` y contraseña de `credenciales[rol]`. Si `rol == "aplicacion"`, aplica la guarda de abajo antes de devolver |
| `_exigir_rol_de_aplicacion(conexion)` | función privada | Consulta `SELECT current_user, r.rolsuper, pg_has_role(current_user, 'cimenta_migracion', 'MEMBER') FROM pg_roles r WHERE r.rolname = current_user`. Si el usuario no es `cimenta_aplicacion`, o es superusuario, o es miembro del rol de migración: `pytest.fail(f"La conexión de pruebas no es la del rol de aplicación (cimenta_aplicacion): es {actual}. Con el propietario, las pruebas de permisos quedan verdes sin verificar nada.")` |

Las comprobaciones de catálogo, incluidas las de `pg_authid`, que exige superusuario, usan la conexión del rol de migración. Toda **operación cuyo permiso se prueba** usa la del rol que el criterio nombra.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Los comandos se ejecutan desde `backend/`, salvo los de Compose y los verificadores de documentación, que van desde la raíz. Antes de la fila 2, `docker info` debe responder; si no, la fila se detiene y se informa como bloqueo, nunca como verde (`conv-docker` §1).

**Reglas comunes.**

- Los casos que son comandos (filas 2, 9 y 11) se registran con su código de salida y la cadena esperada, como en TKT-002. «Rechaza» es código distinto de 0 **y** la cadena indicada.
- Cada fila de pruebas termina con `uv run pytest` completo, no solo con sus casos: las filas 4 a 8 amplían una migración que ya probaron las anteriores.
- Las pruebas de una fila que nacen en verde se investigan. Solo dos están previstas: TC-33 y TC-40, que protege PostgreSQL 15 y posteriores de forma nativa. Su prueba de que dependen de algo es su mutante (MP-11).
- Los archivos desechables y los mutantes se aplican de uno en uno, con el SHA-256 anotado antes y comprobado al restaurar; los desechables llevan `tkt003` en el nombre.
- **Los identificadores de revisión son manuales.** Toda migración nueva, en este ticket y en los siguientes, se crea con `uv run alembic revision -m <slug> --rev-id <nnnn>`, con el número siguiente al de la cabeza: `0003` para la primera de TKT-007 o TKT-011, según cuál llegue antes. Sin `--rev-id`, Alembic genera un hexadecimal aleatorio y se pierde el orden legible. Las pruebas que dependen del contenido exacto de identidad migran hasta `0002`, no hasta la cabeza, para no romperse cuando otros tickets añadan tablas.
- **Agente de las filas 1, 2 y 11.** `ingeniero-devsecops` cubre «Compose, dependencias y gestión de secretos» según su descripción y [metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe); la fila 1 edita `pyproject.toml` y `uv.lock` como gestión de dependencias, igual que en TKT-002, y no toca `cimenta/`. Su lista de archivos nombra `docker-compose.yml`; el archivo de este ticket es `compose.yaml`, y la definición del agente se ajusta en el mismo cambio (ver «Documentación afectada»).

**Por qué cada fila lleva su modelo.** Las filas 3, 4, 5, 7 y 8 caen en el disparador de [metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho) «los permisos de un rol», y la 7 además en «bloqueo pesimista o concurrencia»: el desarrollador va en `sonnet`. Las filas 1, 2, 6, 10 y 11 son mecánicas y su contenido exacto está en este diseño: `haiku`. El tester va siempre en `sonnet`: no baja por debajo de quien verifica.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Dependencias y configuración.** Desde `backend/`: `uv add alembic sqlalchemy "psycopg[binary]"` y `uv add --dev pytest "testcontainers[postgres]"`; después el bloque `[tool.alembic]` y `[tool.pytest]` literal. Comprobaciones previas a la fila 3: `uv run python -c "import testcontainers.postgres"` —si falla y `testcontainers.community.postgres` existe, el `conftest.py` usará este último, y se anota—; `uv run mypy .` sin archivos nuevos sigue en verde. Si al añadir las pruebas mypy dice `missing library stubs or py.typed` para `testcontainers`, se añade exactamente `[[tool.mypy.overrides]]` con `module = ["testcontainers.*"]` e `ignore_missing_imports = true`, y nada más | Ninguno: habilita los siguientes | `ingeniero-devsecops` | `haiku` · mecánico | `uv sync --locked` con código 0. `uv tree --depth 1` lista como directas `alembic`, `psycopg`, `sqlalchemy` y, en `dev`, `import-linter`, `mypy`, `pytest`, `ruff` y `testcontainers`. Alembic ≥ 1.16 y pytest ≥ 9.0, o la fila se detiene y se escala. `uv run pytest` termina con código 5, «no tests ran». `uv run lint-imports` con `14 kept, 0 broken` | ✓ Hecho |
| 2 | **Compose y entorno.** Rojo: `docker compose up -d db` desde la raíz falla con `no configuration file provided`. Verde: `docker pull postgres:18` y `docker image inspect postgres:18 --format "{{range .Config.Env}}{{println .}}{{end}}"` para leer `PG_VERSION`; se escribe `compose.yaml` con `postgres:18.<menor>` exacto y se amplía `.env.example`; se copia a `.env` | TC-01, TC-02, TC-03 | `ingeniero-devsecops` | `haiku` · contenido literal | Salidas en `impl.md`. `docker compose config` no muestra ninguna contraseña distinta de la de `.env`. Si el contenedor no arranca por la ruta del volumen, se lee el mensaje de la imagen, se monta donde indique **su** documentación y se anota; si no lo indica, se escala | ✓ Hecho |
| 3 | **Arnés, entorno de Alembic y roles.** Rojo (`tester-backend`): `conftest.py` completo y los casos de la columna siguiente; fallan porque `migraciones/` no existe (`CommandError: Path doesn't exist`) y porque `herramientas` no existe (`ModuleNotFoundError`), las dos razones esperadas. Verde (`desarrollador-sql`): `herramientas/` completo, `migraciones/env.py`, `script.py.mako` y `v0001` con §1 y §3 de `_SUBIDA` y el `REVOKE USAGE` de `_BAJADA` | TC-11, TC-15, TC-16, TC-18, TC-30, TC-60, TC-61, TC-62, TC-63, TC-64, TC-65 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `sonnet`, disparador «permisos de un rol» | `uv run pytest` en verde con la línea de resumen en `impl.md`. La bajada de §3 se comprueba aquí por comando: `uv run --env-file ../.env alembic downgrade base` contra Compose con código 0 y, desde `docker compose exec db psql`, `SELECT nspacl FROM pg_namespace WHERE nspname = 'public'` ya no nombra a los dos roles; TC-12 la cubre como prueba en la fila 6. `uv run --env-file ../.env alembic upgrade head` contra el `db` de Compose con código 0, que confirma que Alembic encuentra `[tool.alembic]` sin `alembic.ini`. `uv run python -c "import psycopg.pq; print(hasattr(psycopg.pq.PGconn, 'encrypt_password'))"` imprime `True`; si no, se aplica la regla de `herramientas/contrasenas_roles.py`. Ruff y mypy en verde | ⚠ Ajustado (commit en env.py; ver impl.md) |
| 4 | **Privilegios por omisión.** Rojo: TC-31, TC-32 y TC-41 fallan porque la tabla posterior nace sin privilegios para los dos roles. TC-33 y TC-40 nacen en verde y se anota por qué (protección nativa). Verde: §4 de `_SUBIDA` y sus dos sentencias de `_BAJADA` | TC-31, TC-32, TC-33, TC-40, TC-41 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `sonnet`, «permisos de un rol» | `uv run pytest` en verde. `alembic downgrade base` contra Compose deja `pg_default_acl` sin filas, comprobado con `psql` | ✓ Hecho |
| 5 | **Tablas de identidad e invariante 20.** Rojo: los casos de la columna siguiente fallan porque las tablas no existen (`UndefinedTable`, `42P01`). Verde: §5 y §6 de `_SUBIDA` y los cinco `DROP TABLE` de `_BAJADA` | TC-14, TC-20, TC-21, TC-22, TC-23, TC-26, TC-34, TC-35, TC-36, TC-37, TC-38, TC-39, TC-42, TC-43 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `sonnet`, «permisos de un rol» | `uv run pytest` en verde. `uv run --env-file ../.env alembic downgrade base` y `upgrade head` contra Compose con código 0 | ✓ Hecho |
| 6 | **Semilla de los seis roles.** Rojo: TC-24, TC-25, TC-27 y TC-28 fallan porque `rol` está vacía; TC-10, TC-12 y TC-13 fallan porque la revisión `0002` no existe (`CommandError: Can't locate revision`); TC-17 falla porque la lista revisada no incluye `v0002`. Verde: `v0002` literal | TC-10, TC-12, TC-13, TC-17, TC-24, TC-25, TC-27, TC-28 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `haiku`, contenido literal sin permisos | `uv run pytest` en verde; TC-16 ya ve `0002` como cabeza | ⚠ Ajustado (TC-17 renombrado; ver impl.md) |
| 7 | **Tiempos máximos.** Rojo: TC-50 falla con `0`; en TC-51, sin ningún tiempo máximo, B espera hasta que la salvaguarda de 30 s cierra A y obtiene la fila sin error, así que el caso falla; TC-52 termina sin error tras 20 s. Verde: §2 de `_SUBIDA` | TC-50, TC-51, TC-52 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `sonnet`, «bloqueo o concurrencia» y «permisos de un rol» | `uv run pytest` en verde. TC-51 bloquea una fila de una tabla desechable que crea el propio caso, así que esta fila solo depende de las filas 3 y 4 y cabe en la entrega A de D-4. Antes del rojo, el usuario ha aprobado los valores de D-2; si cambian, cambian aquí y en TC-50, TC-51 y TC-52 a la vez | ✓ Hecho |
| 8 | **`PA-T4`, solo si el gate lo aprueba (D-1).** Rojo: TC-44, TC-45 y TC-46 fallan porque el rol de lectura lee `sesion` y `password_hash`. Verde: §7 de `_SUBIDA`. Si el gate no lo aprueba, la fila se marca «No aplica» y TC-44 a TC-46 no se escriben | TC-44, TC-45, TC-46 | rojo: `tester-backend` · verde: `desarrollador-sql` | tester `sonnet` · verde `sonnet`, «permisos de un rol» | `uv run pytest` en verde; TC-42 lo ajusta **el tester**, en el rojo de esta fila, a los conjuntos nuevos de `usuario` y `sesion`, y se anota | ✓ Hecho |
| 9 | **Demostraciones de la suite y mutantes.** Sin código de producción. El tester ejecuta TC-70, TC-71 y TC-72 y los mutantes MP-1 a MP-17 de uno en uno, con su caso y su resultado | TC-70, TC-71, TC-72, TC-82 | `tester-backend` | `sonnet` | Tabla de mutantes en `impl.md`: mutante, caso que se pone rojo, salida. Ningún mutante deja la suite en verde. TC-82 al final | ⚠ Ajustado (solo parte A; ver impl.md) |
| 10 | **Documentación**, según «Documentación afectada»; si el gate aprueba el ADR (D-3), primero el ADR y su fila del índice | TC-76, TC-77, TC-78 | Orquestador, con `conv-documentacion`, por sustitución: no hay agente redactor de documentación ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)) | `haiku` · textos literales en este diseño | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` desde la raíz | ✓ Hecho |
| 11 | **Cierre en copia limpia.** Copia de los archivos que lista `git ls-files --cached --others --exclude-standard` a `<scratchpad>/tkt003-limpia`, con un `.env` copiado de `.env.example`, y allí el arranque completo de `docs/arranque-local.md` | TC-73, TC-74, TC-75, TC-79, TC-80, TC-81, TC-82, TC-83 | `ingeniero-devsecops` | `haiku` · verificable por comando | Salidas en `impl.md`, con fecha, sistema operativo y versiones de `uv`, Python, Docker, PostgreSQL, Alembic, psycopg, pytest y testcontainers. `docker compose down -v` al terminar, para no dejar el volumen de la copia | ⚠ Ajustado (TC-80 y TC-83; ver impl.md) |

**Modelo:** `haiku` por omisión; `sonnet` en las filas que citan su disparador. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera el tope de ~400 líneas.** Estimación de líneas escritas a mano: unas 500 de producción y configuración —`compose.yaml` 25, `.env.example` 15, `pyproject.toml` 12, `env.py` 40, `script.py.mako` 25, `herramientas/` 90, `v0001` 190, `v0002` 35, más `uv.lock`, que no cuenta—, unas 850 de pruebas —`conftest.py` 200 y cinco archivos de unas 130 cada uno— y unas 80 de documentación, 150 con el ADR. **Unas 1,450 en total, el triple del tope.** El peso está en las pruebas, y casi todas son rechazos que la spec exige. Propuesta de partición en D-4.

## Plan de pruebas

Todos los casos de pytest se ejecutan con `uv run pytest` desde `backend/`. Un caso de rechazo comprueba **el SQLSTATE y el nombre de la restricción o el dato**, no solo que haya excepción, y después comprueba que el estado no cambió. Los SQLSTATE se comprueban con `excinfo.value.sqlstate`.

### Compose (comandos, fila 2)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-01 | `docker compose up -d db`, código 0; `docker compose ps db` informa `healthy` en menos de 60 s; desde `backend/`, `uv run --env-file ../.env python -c` con `psycopg.connect(...)` como `cimenta_migracion` imprime `cimenta_migracion` para `SELECT current_user` | feliz | `CA-1` esc. 1 | comando |
| TC-02 | `docker compose exec db psql -U cimenta_migracion -d cimenta -c "CREATE TABLE desechable_tkt003 (n int); INSERT INTO desechable_tkt003 VALUES (1);"`; `docker compose down` **sin** `-v`; `docker compose up -d db`; esperar `healthy`; `SELECT n FROM desechable_tkt003` devuelve `1`; `DROP TABLE desechable_tkt003` | feliz | `CA-1` esc. 2 | comando |
| TC-03 | `docker compose down`; en el scratchpad, un archivo vacío `vacio.env`; con ninguna `CIMENTA_DB_*` en el entorno de la consola, `docker compose --env-file <ruta>/vacio.env up -d db` rechaza con `Falta CIMENTA_DB_`; después `docker compose ps -a -q db` no imprime nada | **rechazo** | `CA-1` esc. 3 | comando |

### Migración y arnés (fila 3; TC-10 y TC-14 en la 5)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-10 | `test_tkt003_ca02_esc01_migracion_inicial_sobre_base_vacia`: `migrar(base_vacia, "0002")`; en `pg_tables` del esquema `public` están exactamente `alembic_version`, `intento_acceso`, `rol`, `sesion`, `usuario` y `usuario_rol`; existen los tres roles en `pg_roles`; `alembic_version` tiene la fila `0002`. Se migra hasta `0002` y no hasta la cabeza para que el conjunto exacto siga siendo cierto cuando TKT-007 o TKT-011 añadan tablas | feliz | `CA-2` esc. 1 | pytest |
| TC-11 | `test_tkt003_pat8_subida_con_roles_ya_existentes_en_el_cluster`: antes de migrar `base_vacia`, los dos roles ya existen (los creó la plantilla) y alguien les cambió un atributo: el arnés ejecuta `ALTER ROLE cimenta_lectura CREATEDB` como migración. `migrar(base_vacia)` termina sin error y después `rolcreatedb` vuelve a ser `false`: la propia subida corrigió el atributo, y la prueba no necesita restaurar nada | **rechazo** de un estado ajeno | `CA-2`, `PA-T8` | pytest |
| TC-12 | `test_tkt003_ca02_esc02_bajada_y_subida_sin_residuos`: `migrar(base_vacia, "0002")`, fotografía A; `migrar(base_vacia, "base", "downgrade")`; sin residuos en la base: solo queda `alembic_version`, sin filas; `pg_default_acl` no tiene filas; `aclexplode(nspacl)` de `public` no nombra a ninguno de los dos roles; ningún `relacl` los nombra. `migrar(base_vacia, "0002")`, fotografía B; `A == B`. La fotografía es una tupla ordenada de: columnas (`table_name, column_name, data_type, is_nullable, column_default`), restricciones (`conname, contype, pg_get_constraintdef`), `pg_indexes.indexdef`, `relacl::text` de cada tabla, filas de `pg_default_acl`, `nspacl::text` de `public`, atributos de los dos roles en `pg_roles`, sus `setconfig` en `pg_db_role_setting` y las filas de `rol` ordenadas por `clave` | **rechazo** de residuos | `CA-2` esc. 2, `PA-T8` | pytest |
| TC-13 | `test_tkt003_ca02_esc03_aplicar_de_nuevo_no_cambia_nada`: `migrar(base_vacia, "0002")`, fotografía A; `migrar(base_vacia, "0002")` otra vez sin error; fotografía B igual a la A y la versión sigue siendo `0002` | feliz | `CA-2` esc. 3 | pytest |
| TC-14 | `test_tkt003_ca02_esc04_la_aplicacion_no_puede_migrar`: con `conectar("aplicacion", base_de_prueba)`, `CREATE TABLE desechable_tkt003 (n int)`, `ALTER TABLE usuario ADD COLUMN desechable_tkt003 int` y `DROP TABLE rol` responden cada uno `42501`; la fotografía de TC-12 no cambió | **rechazo** | `CA-2` esc. 4 | pytest |
| TC-15 | `test_tkt003_guarda_solo_migra_el_rol_de_migracion`: `migrar(base_vacia, rol="cimenta_aplicacion")` lanza `RuntimeError` cuyo texto contiene `solo cimenta_migracion` y `cimenta_aplicacion`; después, `base_vacia` no tiene `alembic_version` | **rechazo** | `M5`, objeción 1 de la spec | pytest |
| TC-16 | `test_tkt003_ca09_esc01_esquema_por_alembic_y_conexion_de_aplicacion`: en `base_de_prueba`, `alembic_version` tiene la cabeza; `conectar("aplicacion", …)` devuelve una conexión cuyo `current_user` es `cimenta_aplicacion` | feliz | `CA-9` esc. 1 | pytest |
| TC-17 | `test_tkt003_ca09_esc01_sin_create_all`: ningún `.py` bajo `backend/tests`, `backend/migraciones` ni `backend/herramientas` contiene la cadena buscada; la búsqueda revisó al menos `conftest.py`, los cuatro archivos de prueba que existen en la fila 6, `env.py` y las dos migraciones. La cadena se construye por concatenación en el propio caso, `"create_" + "all("`, para que el caso no se encuentre a sí mismo | **rechazo** estático | `CA-9` esc. 1 | pytest, sin Docker |
| TC-18 | `test_tkt003_rnf07_sin_variable_no_hay_conexion`: con `monkeypatch.delenv("CIMENTA_DB_CONTRASENA_MIGRACION", raising=False)`, `url_migracion()` lanza `RuntimeError` que nombra `CIMENTA_DB_CONTRASENA_MIGRACION`; con la variable en `""`, lo mismo | **rechazo** | `RNF-07` | pytest, sin Docker |

### Esquema y semilla (filas 5 y 6)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-20 | `test_tkt003_ca03_esc01_columnas_y_tipos_del_modelo`: para cada tabla, el conjunto `(column_name, data_type, is_nullable)` de `information_schema.columns` es **exactamente** el de la tabla de abajo; toda clave primaria es `uuid` | feliz | `CA-3` esc. 1 | pytest |
| TC-21 | `test_tkt003_ca03_esc02_auditoria_solo_en_usuario_y_usuario_rol`: `usuario` y `usuario_rol` tienen las cuatro columnas, con `creado_por_id` y `actualizado_por_id` `YES`; `rol`, `sesion` e `intento_acceso` no tienen ninguna | feliz y **rechazo** | `CA-3` esc. 2 | pytest |
| TC-22 | `test_tkt003_ca03_esc03_intento_con_correo_inexistente`: el rol de aplicación inserta en `intento_acceso` `(id, email, usuario_id, exitoso) = (uuid4, 'nadie@cimenta.test', NULL, false)`; se acepta y se lee | feliz | `CA-3` esc. 3 | pytest |
| TC-23 | `test_tkt003_ca03_esc04_correo_duplicado`: dos usuarios con `ana@cimenta.test`; el segundo responde `23505` con `diag.constraint_name == "uq_usuario_email"`; hay una sola fila | **rechazo** | `CA-3` esc. 4 | pytest |
| TC-24 | `test_tkt003_ca03_esc05_clave_de_rol_duplicada`: insertar en `rol` un `id` nuevo con clave `RESIDENTE` responde `23505` con `uq_rol_clave`; siguen seis filas | **rechazo** | `CA-3` esc. 5 | pytest |
| TC-25 | `test_tkt003_ca03_esc06_mismo_rol_dos_veces`: un usuario con `COMPRAS` asignado; repetir la pareja con otro `id` responde `23505` con `uq_usuario_rol_usuario_id_rol_id` | **rechazo** | `CA-3` esc. 6 | pytest |
| TC-26 | `test_tkt003_ca03_esc07_claves_foraneas_a_la_nada`: `usuario_rol` con `rol_id` inexistente responde `23503` con `fk_usuario_rol_rol_id`; `sesion` con `usuario_id` inexistente responde `23503` con `fk_sesion_usuario_id` | **rechazo** | `CA-3` esc. 7 | pytest |
| TC-27 | `test_tkt003_ca04_esc01_seis_roles_sembrados`: las filas `(id, clave, nombre)` de `rol` son exactamente las seis de la semilla, con sus `id` y sus nombres con acento | feliz | `CA-4` esc. 1 | pytest |
| TC-28 | `test_tkt003_ca04_esc02_la_siembra_no_duplica_ni_inventa`: `migrar(base_vacia, "0002")`, bajar a `base`, subir a `0002`; siguen exactamente las seis, con los mismos `id`; ninguna otra clave | **rechazo** | `CA-4` esc. 2 | pytest |

Columnas que TC-20 exige, `uuid`, `text`, `boolean` y `timestamp with time zone` como los informa `information_schema`; `NO` es `NOT NULL`:

| Tabla | Columnas `(nombre, tipo, nulo)` |
|---|---|
| `usuario` | `id uuid NO` · `nombre text NO` · `email text NO` · `password_hash text NO` · `activo boolean NO` · `ultimo_acceso timestamptz YES` · `bloqueado_hasta timestamptz YES` · `creado_en timestamptz NO` · `creado_por_id uuid YES` · `actualizado_en timestamptz NO` · `actualizado_por_id uuid YES` |
| `rol` | `id uuid NO` · `clave text NO` · `nombre text NO` |
| `usuario_rol` | `id uuid NO` · `usuario_id uuid NO` · `rol_id uuid NO` · `creado_en timestamptz NO` · `creado_por_id uuid YES` · `actualizado_en timestamptz NO` · `actualizado_por_id uuid YES` |
| `sesion` | `id uuid NO` · `usuario_id uuid NO` · `creada_en timestamptz NO` · `expira_en timestamptz NO` · `ultima_actividad timestamptz NO` · `revocada_en timestamptz YES` · `origen_ip text YES` · `agente_usuario text YES` |
| `intento_acceso` | `id uuid NO` · `email text NO` · `usuario_id uuid YES` · `exitoso boolean NO` · `ocurrido_en timestamptz NO` · `origen_ip text YES` |

### Roles y permisos (filas 3, 4, 5 y 8)

`privilegios(tabla, rol)` es el conjunto de `privilege_type` de `aclexplode(relacl)` para ese `grantee`; se compara por **igualdad de conjuntos**, que es lo que detecta un `TRUNCATE`, `REFERENCES`, `TRIGGER` o `MAINTAIN` de más.

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-30 | `test_tkt003_ca05_esc01_roles_sin_atributos_de_privilegio`: para los dos roles, `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication` y `rolbypassrls` son `false` y `rolcanlogin` es `true`; ninguno aparece como `member` en `pg_auth_members` | **rechazo** | `CA-5` esc. 1 | pytest |
| TC-31 | `test_tkt003_ca05_esc02_tabla_posterior_nace_con_permisos`: la migración crea `prueba_permisos (id uuid PRIMARY KEY)` en `base_de_prueba`; `privilegios(prueba_permisos, aplicacion) == {SELECT, INSERT, UPDATE, DELETE}` y `privilegios(prueba_permisos, lectura) == {SELECT}` | feliz | `CA-5` esc. 2 | pytest |
| TC-32 | `test_tkt003_ca05_esc03_aplicacion_sin_privilegios_de_mas_en_tabla_posterior`: sobre `prueba_permisos`, `has_table_privilege` de la aplicación es `false` para `TRUNCATE`, `REFERENCES`, `TRIGGER` y `MAINTAIN` | **rechazo** | `CA-5` esc. 3 | pytest |
| TC-33 | `test_tkt003_ca05_esc03_aplicacion_sin_create_en_el_esquema`: `has_schema_privilege('cimenta_aplicacion', 'public', 'CREATE')` y el de lectura son `false`; `has_database_privilege(…, current_database(), 'CREATE')` también | **rechazo** | `CA-5` esc. 3 | pytest |
| TC-39 | `test_tkt003_ca05_esc01_migracion_es_propietaria`: `tableowner` de las cinco tablas en `pg_tables` es `cimenta_migracion` | feliz | `CA-5` esc. 1 | pytest |
| TC-40 | `test_tkt003_ca07_esc03_lectura_no_crea_objetos`: con `conectar("lectura", …)`, `CREATE TABLE desechable_tkt003 (n int)` responde `42501` | **rechazo** | `CA-7` esc. 3 | pytest |
| TC-41 | `test_tkt003_ca07_esc01_lectura_consulta_tabla_posterior`: la migración crea `prueba_permisos` e inserta una fila; el rol de lectura la lee | feliz | `CA-7` esc. 1 | pytest |
| TC-42 | `test_tkt003_ca05_esc03_privilegios_exactos_en_identidad`: aplicación `{SELECT, INSERT, UPDATE, DELETE}` sobre `usuario`, `rol`, `usuario_rol` y `sesion`, y `{SELECT, INSERT}` sobre `intento_acceso`; lectura `{SELECT}` sobre las cinco (con `PA-T4` aprobada, la fila 8 lo ajusta: vacío sobre `sesion` y `usuario`) | **rechazo** | `CA-5` esc. 3, invariantes 20 y 21 | pytest |
| TC-43 | `test_tkt003_ca07_esc01_lectura_consulta_rol`: el rol de lectura ejecuta `SELECT count(*) FROM rol` | feliz | `CA-7` esc. 1 | pytest |
| TC-34 | `test_tkt003_ca06_esc01_aplicacion_registra_y_lee_intentos`: insertar y leer un intento con el rol de aplicación | feliz | `CA-6` esc. 1 | pytest |
| TC-35 | `test_tkt003_ca06_esc02_aplicacion_no_modifica_intento`: `UPDATE intento_acceso SET exitoso = true WHERE id = …` responde `42501`; la fila conserva `exitoso = false` y su `email` | **rechazo** | `CA-6` esc. 2, invariante 20 | pytest |
| TC-36 | `test_tkt003_ca06_esc03_aplicacion_no_borra_intento`: `DELETE` responde `42501`; la fila sigue | **rechazo** | `CA-6` esc. 3, invariante 20 | pytest |
| TC-37 | `test_tkt003_ca06_esc04_aplicacion_no_vacia_intentos`: con dos intentos, `TRUNCATE intento_acceso` responde `42501`; siguen dos | **rechazo** | `CA-6` esc. 4 | pytest |
| TC-38 | `test_tkt003_ca07_esc02_lectura_no_escribe`: sobre `rol`, `INSERT`, `UPDATE`, `DELETE` y `TRUNCATE` del rol de lectura responden `42501` cada uno; el contenido de `rol` es el mismo antes y después | **rechazo** | `CA-7` esc. 2, invariante 21 | pytest |
| TC-44 | `test_tkt003_pat4_lectura_no_lee_sesiones` *(fila 8)*: `SELECT id FROM sesion` del rol de lectura responde `42501` | **rechazo** | `PA-T4` | pytest |
| TC-45 | `test_tkt003_pat4_lectura_no_lee_password_hash` *(fila 8)*: `SELECT password_hash FROM usuario` y `SELECT * FROM usuario` responden `42501` | **rechazo** | `PA-T4` | pytest |
| TC-46 | `test_tkt003_pat4_lectura_lee_el_resto_de_usuario` *(fila 8)*: `SELECT id, nombre, email, activo FROM usuario` se acepta | feliz | `PA-T4` | pytest |

### Tiempos máximos (fila 7)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-50 | `test_tkt003_ca08_esc01_tiempos_fijados_en_el_rol`: conexión **nueva**, sin ningún `SET`; `SHOW lock_timeout` y `SHOW statement_timeout` dan `5s` y `15s` para la aplicación, y `5s` y `1min` para la lectura | feliz | `CA-8` esc. 1 | pytest |
| TC-51 | `test_tkt003_ca08_esc02_espera_de_bloqueo_se_corta`: el rol de migración crea en `base_de_prueba` la tabla desechable `bloqueo_tkt003 (id uuid PRIMARY KEY)`, que nace con los privilegios por omisión de la fila 4 —entre ellos `UPDATE`, que `FOR UPDATE` exige—; el rol de aplicación inserta y confirma una fila. Conexión A, del rol de aplicación y **sin** `autocommit`: `SELECT id FROM bloqueo_tkt003 WHERE id = %s FOR UPDATE`, y la deja abierta. Conexión B, nueva, del rol de aplicación: la misma consulta lanza `psycopg.errors.LockNotAvailable` con `sqlstate == "55P03"`, y el tiempo medido con `time.monotonic()` está entre 4.5 y 7.0 s. A hace `rollback`; B vuelve a intentarlo y obtiene la fila. Salvaguarda, no sincronización: antes de la consulta de B se arma `threading.Timer(30.0, conexion_a.close)` y se cancela al terminar; sin ningún tiempo máximo, el cierre de A libera la fila, B la obtiene sin error y el caso falla en lugar de colgarse | **concurrencia**, **rechazo** | `CA-8` esc. 2, `RNF-16` | pytest |
| TC-52 | `test_tkt003_ca08_esc03_consulta_larga_se_cancela`: conexión nueva del rol de aplicación; `SELECT pg_sleep(20)` lanza `psycopg.errors.QueryCanceled` con `sqlstate == "57014"`, entre 14 y 18 s | **rechazo** | `CA-8` esc. 3 | pytest |

TC-51 no necesita hilos: A queda en espera inactiva con el bloqueo tomado y B se ejecuta en el mismo hilo. Sin `lock_timeout`, B esperaría hasta `statement_timeout` y fallaría con `57014`: el caso exige `55P03`, así que se pone rojo igual.

### Credenciales (fila 3)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-60 | `test_tkt003_ca10_esc01_roles_entran_con_su_contrasena`: con `credenciales`, la aplicación y la lectura conectan por TCP y su `current_user` es el suyo; en `pg_authid`, `starts_with(rolpassword, 'SCRAM-SHA-256$')` es `true` para los dos | feliz | `CA-10` esc. 1 | pytest |
| TC-61 | `test_tkt003_ca10_esc02_sin_contrasena_no_se_entra`: con `observacion_sin_contrasena`, `rolpassword IS NULL` era `true` para los dos roles, y los cuatro intentos fallaron con `psycopg.OperationalError`; el de `"cualquiera"` contiene `password authentication failed` | **rechazo** | `CA-10` esc. 2 | pytest |
| TC-62 | `test_tkt003_ca10_esc01_script_fija_desde_el_entorno`: con `monkeypatch.setenv` de las seis variables apuntando al contenedor, a la base `postgres` y a las contraseñas de `credenciales`, `main()` devuelve `0`; `capsys` contiene `Contraseñas fijadas` y **ninguna** de las tres contraseñas; la aplicación sigue entrando | feliz y **rechazo** de fuga | `CA-10` esc. 1, `RNF-07` | pytest |
| TC-63 | `test_tkt003_ca10_contrasena_vacia_se_rechaza`: `fijar_contrasenas(conexion, aplicacion="", lectura="x")` lanza `ValueError` que nombra `cimenta_aplicacion`, y la contraseña de `cimenta_lectura` no cambió: sigue entrando con la de `credenciales` | **rechazo** | `RNF-07` | pytest |
| TC-64 | `test_tkt003_ca10_esc03_ningun_secreto_en_el_repositorio`: revisa `compose.yaml`, `backend/migraciones/**/*.py`, `backend/herramientas/**/*.py` y `backend/tests/**/*.py`, y exige que la lista revisada incluya `compose.yaml`, `env.py` y `v0001_identidad_roles_y_esquema.py`. Ninguno contiene la cadena `PASSWORD '` —construida por concatenación, `"PASS" + "WORD '"`, para que el caso no se encuentre a sí mismo— ni ninguno de los tres valores de `CIMENTA_DB_CONTRASENA_*` que lee de `.env.example`; los tres empiezan por `solo-desarrollo-` | **rechazo** | `CA-10` esc. 3 | pytest, sin Docker |
| TC-65 | `test_tkt003_ca11_esc01_env_example_define_lo_que_se_usa`: las claves `CIMENTA_DB_*` de `.env.example` son exactamente `HOST`, `PUERTO`, `NOMBRE`, `CONTRASENA_MIGRACION`, `CONTRASENA_APLICACION` y `CONTRASENA_LECTURA`, con `127.0.0.1`, `5432`, `cimenta` y tres valores que empiezan por `solo-desarrollo-`. Toda variable `CIMENTA_DB_[A-Z_]+` que aparece en `compose.yaml`, `backend/herramientas/` y `backend/migraciones/` está en ese conjunto, y la lista revisada incluye `compose.yaml` y `herramientas/conexion.py` | feliz y **rechazo** | `CA-11` esc. 1 | pytest, sin Docker |

### Demostraciones de la suite (fila 9)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-70 | Mutante MP-8 aplicado: `uv run pytest` rechaza y la salida contiene `no es la del rol de aplicación` | **rechazo** | `CA-9` esc. 2 | comando |
| TC-71 | En PowerShell, `$env:DATABASE_URL = "sqlite:///prueba_tkt003.db"; uv run pytest; $LASTEXITCODE; Remove-Item Env:DATABASE_URL`: código 2 y `Solo se admite PostgreSQL` | **rechazo** | `CA-9` esc. 3 | comando |
| TC-72 | `backend/cimenta/migraciones/__init__.py` vacío: `uv run lint-imports --no-cache` rechaza y nombra `cimenta.migraciones`; se borra | **rechazo** | `CA-R3` esc. 2 | comando |

### Regresión y cierre (filas 10 y 11)

| # | Caso | Tipo | Criterio | Cómo |
|---|---|---|---|---|
| TC-73 | `uv run ruff format --check .`, `uv run ruff check .` y `uv run mypy .` con código 0. Cobertura: un desechable `x: int = "a"` en `herramientas/desechable_tkt003.py`, otro en `tests/test_desechable_tkt003.py` y otro en `migraciones/versions/vdesechable_tkt003.py` hacen fallar mypy, cada uno solo; se borran | regresión y **rechazo** | `CA-R1` | comando |
| TC-74 | `uv sync --locked` con código 0; `uv tree --depth 1` como en la fila 1 | regresión | `CA-R2` | comando |
| TC-75 | `uv run lint-imports` con `14 kept, 0 broken` | regresión | `CA-R3` esc. 1 | comando |
| TC-76 | En `CLAUDE.md` y `docs/arranque-local.md`, las líneas de `docker compose up -d db`, `alembic upgrade head` y `uv run pytest` no contienen `desde TKT-003`; las de `uv run fastapi dev` y `docker compose up -d minio` conservan `desde TKT-005` y `desde TKT-059`; `uv run fastapi dev` sigue fallando | regresión y **rechazo** | `CA-11` esc. 2 y 3, `CA-R4` | búsqueda y comando |
| TC-77 | Desde la raíz, `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` con código 0. Excepción admitida, la de TKT-001 y TKT-002: los enlaces del hub a `impl.md` y `delta.md` que aún no existan, listados uno a uno | regresión | `CA-R5` | comando |
| TC-78 | Ningún problema `Codificación ·`; el primer triplete de `.claude/hooks/recordar-caveman.ps1` es `efbbbf` | regresión | `CA-R6` | comando |
| TC-79 | En la copia limpia, desde `backend/`: `uv run alembic upgrade head` **sin** `--env-file` rechaza con `Falta la variable de entorno CIMENTA_DB_`; `uv run --env-file ../.env alembic upgrade head`, `alembic current` informa `0002 (head)`, `downgrade base`, `upgrade head`, todos con código 0; `uv run --env-file ../.env python -m herramientas.contrasenas_roles` imprime la línea exacta; con la contraseña de `.env`, `cimenta_aplicacion` conecta. El primer paso es el rechazo que D-7 hace explícito: la forma `uv run alembic upgrade head` de `CA-2` esc. 1 y `CA-11` esc. 2 solo funciona con las variables ya en el entorno | feliz y **rechazo** | `CA-2`, `CA-10` esc. 1, `CA-11` esc. 2, D-7 | comando |
| TC-80 | `uv run alembic revision -m desechable --rev-id 9999` crea `migraciones/versions/v9999_desechable.py`, que pasa `ruff check` y `mypy`; se borra | regresión | `M2` | comando |
| TC-81 | `uv run pytest` completo con código 0; se pega la línea de resumen y la duración | regresión | `CA-9` esc. 1 | comando |
| TC-82 | Limpieza: no queda ningún archivo con `tkt003` en el nombre fuera de `sdd/`, ni `backend/cimenta/migraciones`, ni ninguna base `prueba_*` (el contenedor ya no existe); los archivos mutados tienen su SHA-256 | regresión | DoD | comando |
| TC-83 | `verificar_docs.py` solo comprueba la codificación de Markdown y de `.ps1` (`CA-R6`). Para el resto, un `python -c` desde la raíz recorre `compose.yaml`, `.env.example`, `backend/pyproject.toml`, `backend/migraciones/script.py.mako` y todo `.py` bajo `backend/migraciones`, `backend/herramientas` y `backend/tests`, y falla si alguno empieza por `EF BB BF` o contiene `\r` | regresión | `CA-R6` | comando |

### Mutación

La DoD exige demostrar que cada garantía de permisos hace falta. Cada mutante se aplica solo, se ejecuta `uv run pytest` y se confirma que **al menos** los casos indicados se ponen rojos; después se revierte y se comprueba el hash.

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MP-1 | §4: la aplicación recibe por omisión `SELECT, INSERT, UPDATE, DELETE, TRUNCATE` | TC-32, TC-37, TC-42 |
| MP-2 | §6 eliminado: sin `REVOKE` sobre `intento_acceso` | TC-35, TC-36, TC-42 |
| MP-3 | **Quitar los privilegios por omisión y sustituirlos por `GRANT` por tabla**: §4 se mueve **después** de §5, y en su lugar se escribe `GRANT SELECT, INSERT, UPDATE, DELETE ON usuario, rol, usuario_rol, sesion, intento_acceso TO cimenta_aplicacion` y `GRANT SELECT ON … TO cimenta_lectura` | TC-31 y TC-41, mientras TC-42 sigue verde. Es la demostración de la objeción 1 de la spec: las tablas de identidad no lo notan |
| MP-4 | §4: la lectura recibe por omisión `SELECT, INSERT` | TC-38, TC-31, TC-42 |
| MP-5 | §2 sin `lock_timeout` de la aplicación | TC-50, TC-51 (falla con `57014` a los 15 s) |
| MP-6 | §2 sin `statement_timeout` de la aplicación | TC-50, TC-52 |
| MP-7 | §1: `GRANT cimenta_migracion TO cimenta_aplicacion` al final | TC-30, y la guarda hace fallar todo lo que usa la conexión de aplicación |
| MP-8 | `conectar`: el usuario de `"aplicacion"` pasa a `cimenta_migracion` con su contraseña | Toda prueba que use la aplicación, con el mensaje de la guarda (TC-70) |
| MP-9 | `env.py` sin la llamada a `_exigir_rol_de_migracion` | TC-15 |
| MP-10 | `conftest.py`: `.with_env("POSTGRES_HOST_AUTH_METHOD", "trust")` en el contenedor | TC-61 |
| MP-11 | Desechable de la fila 9: `GRANT CREATE ON SCHEMA public TO cimenta_aplicacion, cimenta_lectura` en §3 | TC-33, TC-40, TC-14. Demuestra que TC-33 y TC-40, nacidos en verde, sí dependen del privilegio |
| MP-12 | §1: el bloque `DO` sustituido por `CREATE ROLE cimenta_aplicacion` y `CREATE ROLE cimenta_lectura` sin condición | TC-10, TC-11, TC-12 (`42710` en la segunda base del clúster) |
| MP-13 | `_BAJADA` termina con `DROP ROLE cimenta_lectura` y `DROP ROLE cimenta_aplicacion` | TC-12, TC-28 (`2BP01`: la plantilla y las bases de prueba los usan) |
| MP-14 | §1: `CREATE ROLE cimenta_aplicacion PASSWORD 'x'` | TC-61, TC-64 |
| MP-15 | §5: `usuario_rol` sin `uq_usuario_rol_usuario_id_rol_id` | TC-25, TC-20 no cambia: la prueba que lo detecta es la del rechazo |
| MP-16 | `pytest_sessionstart` sin la guarda de SQLite | TC-71 termina con código 0 o con otro mensaje |
| MP-17 | *(solo con `PA-T4`)* §7 sin `REVOKE SELECT ON sesion` | TC-44 |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `backend/pyproject.toml` y `uv.lock` | Ruff, mypy, `import-linter`, `uv` | Que la configuración nueva cambie las compuertas de TKT-001 y TKT-002, o entren dependencias no pedidas | Bloques añadidos al final; TC-73, TC-74 y TC-75 |
| Código Python fuera de `cimenta/` (`migraciones/`, `herramientas/`, `tests/`) | `import-linter` no lo analiza | Que alguien importe `cimenta` desde allí y se salte las fronteras | Nada de lo nuevo importa `cimenta`. Los tickets que escriban pruebas de módulo importarán interfaces; un contrato para `tests` queda como sugerencia para TKT-009 |
| `migraciones/env.py` importa `herramientas` | Toda migración futura | Que `herramientas` crezca con dependencias pesadas que Alembic arrastre | `herramientas/conexion.py` solo depende de `os` y `sqlalchemy` |
| Privilegios por omisión | Todas las tablas de todos los módulos | Una tabla creada por un rol distinto de `cimenta_migracion` nacería sin permisos | Guarda de `env.py` (TC-15, MP-9); TC-31 y MP-3 |
| Tiempos máximos en el rol | TKT-005 (traducción a `CONCURRENCIA`), TKT-021 y TKT-022 (bloqueo pesimista), TKT-011 y la importación de Excel | Una importación con una sentencia de más de 15 s se cortaría | La importación inserta por lotes; si alguna sentencia legítima supera el valor, se sube con decisión del usuario o se fija `SET LOCAL` en ese caso de uso, documentado |
| `cimenta_lectura` | `analitica` (TKT-039 y siguientes) | Con `PA-T4`, `SELECT *` sobre `usuario` falla y cada columna nueva de `usuario` necesita su `GRANT` | Falla hacia el lado seguro; queda escrito en el modelo de datos |
| `conv-sql-postgres` §5 dice «cada migración concede los permisos de forma explícita» | Cualquier revisor o auditor que aplique la convención | Que un auditor pida `GRANT` por tabla, que es exactamente el mutante MP-3 | Ya está en «Tickets futuros sugeridos» del hub. Recomendación: alinear la convención en el mismo PR, con dos frases (D-8) |
| `CLAUDE.md` y `docs/arranque-local.md` | Todos los agentes | Una marca mal retirada, o un comando que no funciona tal como se escribe | TC-76 y TC-79 con texto literal |
| Volumen `cimenta_pg_datos` | Quien desarrolla | `docker compose down -v` borra la base local | Documentado en el arranque; es el comportamiento estándar |
| TKT-006, TKT-007, TKT-011, TKT-057, TKT-059 | Usan este esquema, los roles y el arnés | Que necesiten el arnés con otra forma | `conectar`, `base_de_prueba` y `migrar` quedan como la forma de las pruebas de integración; MinIO se añadirá como otro contenedor de sesión en TKT-059 |

**Fronteras entre módulos:** no. El ticket no hace hablar a ningún módulo con otro y no crea código bajo `backend/cimenta/`.

### Revisión de impacto independiente

Hallazgos de la revisión de impacto encargada por el orquestador sobre la primera versión de este diseño, y lo que se hizo con cada uno.

| # | Severidad | Hallazgo | Acción en este diseño |
|---|---|---|---|
| A1 | Alta | Con la partición de D-4, la entrega A no podía cerrar `CA-8`: TC-51 bloqueaba una fila de `usuario`, que crea la fila 5, de la entrega B. Y D-4 presentaba como reducción de riesgo una partición que no se fusiona por separado | TC-51 bloquea una fila de la tabla desechable `bloqueo_tkt003`, que crea el propio caso y que nace con los privilegios por omisión; la fila 7 solo depende de las filas 3 y 4. MP-5 y MP-6 no cambian. D-4 reescrita: la partición en entregas es de revisión y de contexto, no de despliegue, y se expone la partición real en dos tickets como alternativa, sin decidirla |
| A2 | Alta | TC-12, TC-13 y TC-17 estaban en la fila 3 y no podían pasar a verde con lo que esa fila escribe: dependen de `rol`, de `0002` y de archivos de prueba posteriores | TC-10, TC-12, TC-13 y TC-17 pasan a la fila 6. La bajada de §3 y §4 se comprueba por comando en las filas 3 y 4 |
| A3 | Alta | D-5 contradice los textos que dicen «la migración crea los tres roles» en arquitectura, modelo de datos, stack, el texto del ticket y `conv-sql-postgres` | Frases literales de reemplazo en la ampliación de «Documentación afectada»; las del ticket y de las convenciones, como corrección con aprobación humana (D-9) |
| M1 | Media | El diseño amplía la lista de archivos de la spec sin declararlo, y `conv-sql-postgres` §4 dice «una migración por ticket» | Documentación en dos tablas, «necesaria por la spec» y «ampliación a aprobar», con D-9. La pareja `0001` y `0002` se justifica en la escalera |
| M2 | Media | TC-79 contradice la forma literal de `CA-2` esc. 1 y `CA-11` esc. 2 | D-7 dice que exige reinterpretar los dos escenarios y qué texto se ajustaría; la spec no se edita |
| M3 | Media | TC-10 y TC-12 exigían «exactamente seis tablas» contra la cabeza y se romperían con TKT-007 o TKT-011 | Migran hasta `0002`. Regla de `--rev-id` manual y correlativo en «Reglas comunes» |
| M4 | Media | `tests/` sin `__init__.py` exige nombres base únicos en todo el árbol | `--import-mode=importlib` en `[tool.pytest]`, verificado con la documentación de pytest; la unicidad la sigue exigiendo mypy, y la regla queda escrita en «Pruebas» |
| M5 | Media | Faltaban en la documentación `docs/convenciones.md`, la estructura de `CLAUDE.md`, `conv-sql-postgres` §2, `conv-docker`, el conteo de ADR del stack y la nota para TKT-057 | Añadidos a la ampliación; la nota de TKT-057, abajo |
| B1 | Baja | La afirmación sobre SCRAM y `trust` de la imagen no estaba verificada | Matizada como `(asumido)`; la prueba empírica es TC-61 con MP-10 |
| B3 | Baja | `pydantic-settings` se atribuía a TKT-005 | Corregido: TKT-057 y TKT-059 |
| B4 | Baja | TC-17 y TC-64 se encontrarían a sí mismos al buscar su cadena | La cadena se construye por concatenación dentro del caso |
| B5 | Baja | `ingeniero-devsecops` nombra `docker-compose.yml` y su lista no incluye `pyproject.toml` | Justificado en «Reglas comunes» como gestión de dependencias; la definición del agente se corrige en la ampliación |
| B6 | Baja | Faltaba un caso para `CA-11` esc. 1, y `CA-R6` solo cubre Markdown y `.ps1` | TC-65 y TC-83 |
| B7 | Baja | «Dos servicios» en el stack, cuando hasta TKT-059 solo existe `db` | Texto del stack corregido en la ampliación |

### Impacto en tickets posteriores

| Ticket | Qué hereda de este | Qué tiene que saber |
|---|---|---|
| TKT-004 y TKT-005 | `backend/pyproject.toml` y `uv.lock` | Si se trabajan en paralelo con este, chocarán en esos dos archivos: el bloqueo se regenera con `uv lock` tras fusionar, nunca se mezcla a mano |
| TKT-006 | Las cinco tablas y el rol de aplicación | Necesita la URL y el motor del rol de aplicación —`herramientas/conexion.py` solo construye la de migración— y los modelos ORM de `identidad`, que este ticket no escribe (`PA-T11`). Decide índices, normalización del correo (`PA-T10`), `inet` y el destino del `DELETE` sobre `sesion` (`PA-T6`) |
| TKT-007 y TKT-011 | Alembic y los privilegios por omisión | Revisiones con `--rev-id` manual y correlativo, `0003` en adelante; cada una revoca lo que su tabla no admite y lo prueba con `conectar("aplicacion", …)`. La prueba del disparador del invariante 14 usa `conectar("migracion", …)` |
| TKT-009 | La suite y el arnés | El corredor necesita Docker; la suite añade unos 20 s por TC-51 y TC-52. `lint-imports` no mira `tests/`, `migraciones/` ni `herramientas/`: un contrato propio queda como sugerencia |
| TKT-057 | `.env.example` | Añade sus claves en su propio bloque, bajo el de base de datos, sin tocar las seis `CIMENTA_DB_*`; TC-65 fallará si alguna desaparece o cambia de valor de desarrollo |
| TKT-058 | Roles, migraciones y tiempos | El rol de migración debe llamarse exactamente `cimenta_migracion` o `env.py` se niega; necesita `CREATEROLE` en el gestionado `(asumido)`; la imagen de producción debe incluir `backend/migraciones/` y `backend/herramientas/`; decide el `lock_timeout` del rol de migración y la versión mayor contratada (D-6) |
| TKT-059 | `compose.yaml` y el arnés | Al añadir el servicio `minio`, la expresión regular del `conftest.py` que lee la imagen de PostgreSQL debe seguir encontrando una sola línea `image: postgres:…`; MinIO entra como otro contenedor de sesión |

## Documentación afectada

Todos los textos son literales para que la fila 10 los copie sin reformular; ninguno usa sintaxis de enlace hacia archivos que aún no existen. **El diseño amplía la lista de archivos de la spec**, que solo nombraba `backend/pyproject.toml`, `backend/uv.lock`, `.env.example`, `CLAUDE.md` (marcas), `docs/arranque-local.md`, `docs/03-modelo-datos.md` (por `S1`) y los archivos nuevos de Compose, migraciones y pruebas. Por eso la documentación va en dos tablas: lo que la spec ya pide, y la ampliación, que se aprueba en el gate (D-9).

### Necesaria por la spec

| Documento | Qué cambia |
|---|---|
| `CLAUDE.md`, bloque «Desde `backend/`» | Línea de `uv run pytest`: comentario `# tests · requiere Docker en marcha (testcontainers)`. La línea de Alembic pasa a `uv run --env-file ../.env alembic upgrade head   # migraciones, siempre con el rol de migración`, y debajo `uv run --env-file ../.env python -m herramientas.contrasenas_roles   # contraseñas de los roles, tras migrar`. El cambio de la línea de Alembic depende de D-7 |
| `CLAUDE.md`, bloque «Desde la raíz» | `docker compose up -d db          # PostgreSQL local` |
| `docs/arranque-local.md` | (1) Requisitos: fila nueva «Docker \| Docker Desktop con el motor de Linux, o Docker Engine con Compose v2 \| PostgreSQL local con `docker compose` y las pruebas con testcontainers». (2) Sección nueva «Base de datos», tras «Backend», con los pasos: `cp .env.example .env` desde la raíz; `docker compose up -d db`; desde `backend/`, `uv run --env-file ../.env alembic upgrade head` y `uv run --env-file ../.env python -m herramientas.contrasenas_roles`; y este párrafo: «La imagen crea el rol de migración, `cimenta_migracion`, que es el único con el que Alembic acepta migrar. La migración crea los roles `cimenta_aplicacion` y `cimenta_lectura` sin contraseña; el segundo comando se la fija desde `.env`. Bajar todas las migraciones no elimina esos dos roles, porque son del servidor y no de la base: `docker compose down -v` borra el volumen y lo deja todo como al principio.» (3) Bloque «Backend»: `uv run pytest` tras `uv run lint-imports`, con la frase «`uv run pytest` necesita Docker en marcha: levanta su propio PostgreSQL con testcontainers y no usa el de Compose.» (4) En «Lo que todavía no arranca» se borran las filas de `uv run pytest`, `uv run alembic upgrade head` y `docker compose up -d db`. (5) La línea «Verificado en copia limpia» se actualiza en la fila 11, con la versión de Docker |
| `docs/03-modelo-datos.md` §10 (`S1`) | En el diagrama, `USUARIO` y `USUARIO_ROL` ganan `timestamptz creado_en`, `uuid creado_por_id FK "nulo permitido"`, `timestamptz actualizado_en` y `uuid actualizado_por_id FK "nulo permitido"`. Tras la frase de `usuario_rol` de muchos a muchos: «Una persona no tiene dos veces el mismo rol: `usuario_rol` lleva `UNIQUE (usuario_id, rol_id)`.» |
| `docs/03-modelo-datos.md` §2 (`S1`) | En «Columnas de auditoría», tras «en toda tabla transaccional»: «. En identidad las llevan `usuario` y `usuario_rol`, con `creado_por_id` y `actualizado_por_id` nulos permitidos porque la siembra y el primer usuario no tienen autor; `rol`, `sesion` e `intento_acceso` no las llevan» |
| `.env.example` | El bloque de «Configuración y entorno» |

### Ampliación a aprobar en el gate (D-9)

Casi toda la ampliación es consecuencia de D-5: varios documentos dicen que «la migración crea los tres roles», y con D-5 eso deja de ser literal. La frase de reemplazo es siempre la misma idea: **la migración crea los roles de aplicación y de solo lectura; el de migración lo crea el entorno**. Las filas marcadas con «corrección con aprobación humana» tocan el texto de un ticket o una convención del toolkit, y no se aplican sin el visto bueno explícito del usuario en el gate.

| Documento | Qué cambia | Por qué |
|---|---|---|
| `docs/02-arquitectura.md` §7.6, línea 385 | «La migración inicial (TKT-003) crea los tres roles y fija con `ALTER DEFAULT PRIVILEGES`» pasa a «La migración inicial (TKT-003) crea los roles de aplicación y de solo lectura —el de migración lo crea el entorno— y fija con `ALTER DEFAULT PRIVILEGES`». Tras «Los permisos nacen con la tabla, no después.», se añade: «Alembic solo migra con el rol de migración y se niega con cualquier otro: los privilegios por omisión se declaran para ese rol, y una tabla creada por otro nacería sin ellos.» | D-5 |
| `docs/03-modelo-datos.md` §2, línea 53 | «Tres roles de PostgreSQL —migración, aplicación y solo lectura— creados en la migración inicial con `ALTER DEFAULT PRIVILEGES`» pasa a «Tres roles de PostgreSQL —migración, aplicación y solo lectura—: la migración inicial crea los de aplicación y de solo lectura, el de migración lo crea el entorno, y los permisos por omisión se fijan con `ALTER DEFAULT PRIVILEGES`» | D-5 |
| `docs/03-modelo-datos.md` §13, línea 1171 | «La migración inicial crea los tres roles con `ALTER DEFAULT PRIVILEGES`» pasa a «La migración inicial crea los roles de aplicación y de solo lectura —el de migración lo crea el entorno— y fija los permisos por omisión con `ALTER DEFAULT PRIVILEGES`» | D-5 |
| `docs/03-modelo-datos.md` §13 y `docs/02-arquitectura.md` §7.6 | **Solo con `PA-T4` aprobada (D-1).** Invariante 21, columna «Mecanismo»: se añade «; sin acceso a `sesion` ni a `usuario.password_hash`». En §7.6, fila «Lectura»: «`SELECT` y nada más; ni `sesion`, cuyo identificador es la credencial de la cookie, ni `usuario.password_hash`» | D-1 |
| `docs/06-stack-tecnologico.md` §4.4, línea 193 | «**Los tres roles de PostgreSQL y sus permisos también se crean en la migración inicial**, no a mano en el servidor.» pasa a «**Los roles de PostgreSQL y sus permisos también nacen en la migración inicial**, no a mano en el servidor: la migración crea los de aplicación y de solo lectura; el de migración lo crea el entorno.» Y al final de §4.4: «El entorno de Alembic vive en `backend/migraciones/`, fuera del paquete `cimenta`, y su configuración en `[tool.alembic]` de `backend/pyproject.toml`.» | D-5 y ubicación |
| `docs/06-stack-tecnologico.md` §6.5, línea 323 | «se crean en la migración inicial» pasa a «nacen en la migración inicial —la migración crea los de aplicación y de solo lectura; el de migración lo crea el entorno—» | D-5 |
| `docs/06-stack-tecnologico.md` §10 «Local» | «**Docker Compose** con dos servicios: PostgreSQL y **MinIO**» pasa a «**Docker Compose** (`compose.yaml`, en la raíz) con dos servicios: PostgreSQL, desde TKT-003, y **MinIO**, desde TKT-059». Tras la primera frase: «PostgreSQL es la versión mayor 18, la misma que se contratará en producción; las pruebas leen la etiqueta exacta de `compose.yaml`.» | Hasta TKT-059 solo existe `db` |
| `docs/06-stack-tecnologico.md` §11 y §13 | **Solo si D-3 se aprueba**: el ADR nuevo en la lista de decisiones registradas, con el mismo formato que las demás | Conteo de ADR |
| `docs/convenciones.md`, árbol del repositorio (líneas 55 a 60) | `.env.example` pasa a «Plantilla de variables de entorno con valores de desarrollo evidentes; `.env` no se versiona». Fila nueva tras ella: «`compose.yaml` · PostgreSQL local (TKT-003); MinIO llega con TKT-059». `backend/` pasa a «Proyecto uv del backend: pyproject.toml, uv.lock, el paquete `cimenta/` y, fuera de él, migraciones/, herramientas/ y tests/» | `M10` y ubicación |
| `CLAUDE.md`, «Estructura del backend» (líneas 54 a 61) | Tras el bloque: «Fuera de `cimenta/`, en `backend/`, viven `migraciones/` (Alembic), `herramientas/` (operación, como fijar las contraseñas de los roles) y `tests/`. `import-linter` no los analiza.» | Ubicación |
| `docs/05-tickets-trabajo.md`, TKT-003, línea 133 — **corrección con aprobación humana** | «**Tres roles de PostgreSQL creados en la migración**, no a mano en el servidor: migración (propietario), aplicación y solo lectura (`RNF-09`)» pasa a «**Roles de PostgreSQL creados en la migración**, no a mano en el servidor: la migración crea los de aplicación y de solo lectura; el de migración (propietario) lo crea el entorno (`RNF-09`)» | D-5 |
| `.claude/skills/conv-sql-postgres/SKILL.md` — **corrección con aprobación humana** | §2: «**Claves primarias `UUID`** y **columnas de auditoría** en toda tabla» pasa a «**Claves primarias `UUID`** en toda tabla y **columnas de auditoría** en toda tabla transaccional, según el modelo de datos §2: en identidad, solo `usuario` y `usuario_rol`». §4: «Una migración por ticket, con el identificador en el mensaje» pasa a «Una migración de esquema por ticket, más la de semilla si la hay, con el identificador en el mensaje y `--rev-id` correlativo». §5, línea 52: «**Los tres roles se crean en la migración**, no a mano en el servidor (`RNF-09`). Cada migración que crea un objeto le concede los permisos al rol de aplicación de forma explícita: un objeto nuevo sin `GRANT` solo falla en el primer despliegue.» pasa a «**La migración crea los roles de aplicación y de solo lectura; el de migración lo crea el entorno**, y nada se crea a mano en el servidor (`RNF-09`). Cada tabla nace con los permisos por omisión que fija la migración inicial con `ALTER DEFAULT PRIVILEGES`, y cada migración de módulo **revoca** lo que su tabla no admite, con su prueba.» §8: «`GRANT` al rol de aplicación para cada objeto nuevo» pasa a «Revocación y prueba de lo que la tabla no admite» | D-5, D-8 y `PA-T1` |
| `.claude/skills/conv-docker/SKILL.md` — **corrección con aprobación humana** | En la descripción, «un docker-compose» pasa a «el `compose.yaml`». En §2, el bloque de comandos pasa a `docker compose up -d db` (y `minio` desde TKT-059) y `uv run --env-file ../.env alembic upgrade head`, desde `backend/` | Nombre del archivo y D-7 |
| `.claude/agents/ingeniero-devsecops.md`, línea 16 — **corrección con aprobación humana** | «el `docker-compose.yml`» pasa a «el `compose.yaml`» | Nombre del archivo |
| Si D-3 se aprueba: ADR nuevo, `docs/adr/README.md`, `README.md`, `llms.txt` y `CLAUDE.md` línea 14 | El ADR de «¿Merece ADR?», su fila en el índice (fecha `2026-10-17`, estado `Aceptado`, afecta a «Base de datos, migraciones y pruebas de integración») y el conteo de 18 a 19 | D-3 |

## ¿Merece ADR?

**Sí, y se propone; lo aprueba el usuario (D-3).** Archivo propuesto: `docs/adr/20261017-roles-postgresql-y-migraciones.md`, formato MADR, estado `Aceptado`. Cumple las dos condiciones: quien llegue verá que Alembic se niega a correr con el superusuario, que bajar todas las migraciones deja dos roles en el servidor y que las contraseñas no están en la migración, y se preguntará por qué; y hubo opciones descartadas con motivo en tres decisiones que condicionan a cada ticket con tablas.

- **Contexto:** `RNF-09` exige tres roles creados en la migración, y los invariantes 10, 20, 21 y 30 son permisos que dependen de `ALTER DEFAULT PRIVILEGES`.
- **Decisión 1, quién migra:** el rol que crea el entorno, con guarda en `env.py`. Descartadas: que la migración cree el rol de migración y haga `SET ROLE` (en PostgreSQL 16 y posteriores, quien crea un rol con `CREATEROLE` no obtiene por omisión la opción `SET` sobre él, y `alembic_version` la crearía el usuario de conexión antes de la primera migración); y migrar con cualquier superusuario (las tablas nacerían de otro propietario y sin los privilegios por omisión).
- **Decisión 2, roles del clúster:** creación idempotente y bajada que no los elimina. Descartadas: `CREATE ROLE` simple (falla en la segunda base del clúster) y una bajada que los elimina (falla con `2BP01` si otra base los usa, y en pruebas siempre la hay).
- **Decisión 3, contraseñas:** fuera de la migración, por entorno, con un script que la suite reutiliza y que envía la contraseña ya cifrada. Descartadas: contraseña en la migración (`RNF-07`) y script de inicio del contenedor (`conv-docker` §2: dejaría producción sin roles).
- **Decisión 4, aislamiento de pruebas:** base copiada de una plantilla migrada una vez por sesión. Descartadas: transacción envolvente deshecha (no admite filas confirmadas, que la prueba de `55P03` y las de bitácora necesitan), y vaciar tablas (exige el propietario y borra la semilla).
- **Consecuencias:** el rol de migración es superusuario en local y en pruebas, y en producción un rol con `CREATEROLE` `(asumido)`; quitar los roles del clúster es una acción de operación; toda tabla nueva tiene permisos sin escribir un `GRANT`, y cada migración de módulo solo revoca.
- **Cuándo revisar:** si TKT-058 contrata un PostgreSQL gestionado que no permita `CREATEROLE` al rol de migración, o si una prueba necesita más de un contenedor.

## Decisiones sobre las preguntas abiertas de la spec

| # | Decisión del diseño |
|---|---|
| `PA-T3` | El operador fija las contraseñas de producción con el mismo script, `python -m herramientas.contrasenas_roles`, o desde la consola del proveedor `(asumido)`. Se confirma en TKT-058 |
| `PA-T4` | Recomendación: **revocar** el `SELECT` del rol de lectura sobre `sesion` entera y sobre `usuario.password_hash`. Costo: tres sentencias, tres pruebas y un mutante; cada columna nueva de `usuario` necesitará su `GRANT` al rol de lectura, y `SELECT *` sobre `usuario` deja de funcionar con ese rol. No se recomienda ir más allá, por ejemplo con `intento_acceso`: la spec no lo plantea. Decisión humana: D-1 |
| `PA-T5` | Propuesta en D-2 |
| `PA-T6` | Se mantiene el `DELETE` por omisión del rol de aplicación sobre `sesion` `(asumido)`. Revocarlo sin decidir con qué rol se purga sería inventar una regla. TKT-006 o el ticket de purga lo revisan |
| `PA-T8` | Creación idempotente; la bajada no elimina los roles ni sus tiempos máximos, y deja la base sin ningún otro residuo salvo la tabla vacía de `alembic_version`, que es de Alembic. TC-11, TC-12, MP-12 y MP-13 |
| `PA-T9` | Resuelta en la escalera: `compose.yaml` en la raíz; Alembic en `backend/migraciones/`; base `cimenta`; roles `cimenta_migracion`, `cimenta_aplicacion` y `cimenta_lectura`; variables `CIMENTA_DB_*`; `psycopg` 3; PostgreSQL 18 `(asumido, D-6)`; UUID fijos de la semilla; aislamiento por plantilla. Sin contraseña por omisión en Compose: TC-03 |
| `PA-T10` | Sin cambio: `uq_usuario_email` distingue mayúsculas; TKT-006 normaliza |
| `PA-T11` | Sin ORM en este ticket |
| `PA-T12` | Se confirma: `uv run pytest` se habilita aquí, con `pytest` y `testcontainers[postgres]` en `dev` |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación del diseño | Si se decide otra cosa |
|---|---|---|---|
| D-1 | ¿Se revoca al rol de lectura el `SELECT` sobre `sesion` y sobre `usuario.password_hash` (`PA-T4`)? | **Sí.** `sesion.id` es la credencial de la cookie: quien lea con ese rol puede suplantar a cualquier usuario con sesión viva | La fila 8, TC-44 a TC-46 y MP-17 se marcan «No aplica»; TC-42 conserva `{SELECT}` en las cinco |
| D-2 | Valores de los tiempos máximos (`PA-T5`) | Aplicación: `lock_timeout = 5s`, `statement_timeout = 15s`. Lectura: `5s` y `60s`, porque las consultas de analítica son más largas y un `SELECT` solo espera ante el DDL de una migración. Migración: **ninguno** en este ticket, y TKT-058 fija `lock_timeout` al migrar contra producción | Se cambian los literales de §2 y de TC-50 a TC-52 antes de la fila 7. Con `statement_timeout` mayor de 15 s, TC-52 tarda lo mismo que el valor |
| D-3 | ¿Se escribe el ADR de roles y migraciones? | **Sí** | Las decisiones viven solo en este diseño y en `delta.md` |
| D-4 | El orden suma unas 1,450 líneas, el triple del tope. ¿Cómo se parte? | El diseño **no decide**: expone tres opciones con su costo. **(a) Un solo PR**, en el orden de las 11 filas. **(b) Dos entregas dentro del mismo ticket.** Entrega A, filas 1 a 4, 7 y 9 con los mutantes que no tocan tablas: Compose, Alembic, arnés, roles, privilegios por omisión y tiempos, unas 850 líneas; cierra `CA-1`, `CA-5` esc. 1 (atributos) y esc. 2, `CA-7` esc. 3, `CA-8` entero —TC-51 usa una tabla desechable—, `CA-9` y `CA-10`. Entrega B, filas 5, 6, 8, 10 y 11: tablas, semilla, `PA-T4` y documentación, unas 600; cierra el resto. Dicho con honestidad: `0001` se completa en B y una migración fusionada ya no se edita, así que **A no se fusiona hasta que B esté lista**. Es una partición de revisión y de contexto, **no de despliegue**: reduce el tamaño de cada lectura, no el riesgo de lo que llega a `Produccion`. **(c) Partición real en dos tickets.** TKT-003 se queda con Compose, Alembic, arnés, roles, privilegios por omisión y tiempos, en la migración `0001`, fusionable sola; un ticket nuevo crea las tablas de identidad y la semilla en `0002` y `0003`, con el invariante 20. Lo que la permite: `M5`, `M8`, `M9` y los invariantes 21 y los privilegios por omisión se demuestran sobre tablas desechables, y el modelo de datos llama «migración inicial» a la que crea roles y privilegios. Lo que la desaconseja: el texto de TKT-003 en `docs/05-tickets-trabajo.md` pone las tablas y el invariante 20 en este ticket, y la spec aprobada exige en `CA-2` esc. 1 que tras `upgrade head` existan «las cinco tablas de identidad y los tres roles», además de `CA-3`, `CA-4` y `CA-6`; partir obliga a reabrir la spec, mover esos criterios al ticket nuevo, darle número y hacer que TKT-006, TKT-007 y TKT-011 dependan de los dos | Con (a), un PR de unas 1,450 líneas y una sesión larga. Con (b), dos revisiones y una fusión conjunta. Con (c), el gate devuelve la spec a `/sdd-definir` y este diseño se recorta a las filas de A |
| D-5 | `M5` dice «tres roles creados en la migración», y una migración no puede crear el rol con el que se conecta | El rol de migración lo crea el entorno —`POSTGRES_USER` en local y en pruebas, el operador en producción—, como ya dice `conv-docker` §2; la migración crea los otros dos y `env.py` exige que migre ese rol. Arrastra la corrección de los textos que dicen «la migración crea los tres roles», listados en la ampliación (D-9) | Si se exige crearlo en la migración, hace falta la alternativa de `SET ROLE` descartada en el ADR, con `REQUIERE DECISIÓN` sobre los privilegios del rol del operador |
| D-6 | PostgreSQL 18 como versión de producción `(asumido)` | **18**, y TKT-058 contrata la misma mayor | Una línea de `compose.yaml`; las pruebas la siguen solas |
| D-7 | El comando documentado de Alembic pasa a `uv run --env-file ../.env alembic upgrade head`. **Exige reinterpretar dos criterios de la spec**: `CA-2` esc. 1 («se ejecuta "uv run alembic upgrade head" desde "backend/"») y `CA-11` esc. 2 («los comandos funcionan tal como están escritos», con la línea de `uv run alembic upgrade head`). Con D-7, la forma literal sin `--env-file` solo funciona si las variables ya están en el entorno, y TC-79 demuestra que sin ellas falla nombrando la variable | **Sí**: sin dependencia nueva. El diseño no edita la spec; si se aprueba, en el cierre se ajusta el texto de esos dos escenarios a «`uv run --env-file ../.env alembic upgrade head`, o `uv run alembic upgrade head` con las variables `CIMENTA_DB_*` en el entorno» | Añadir `python-dotenv` a las dependencias de ejecución y leer `../.env` en `herramientas/conexion.py`; entonces el comando literal de la spec funciona sin reinterpretación |
| D-9 | El diseño amplía la lista de archivos de la spec: `docs/02-arquitectura.md`, `docs/06-stack-tecnologico.md`, `docs/convenciones.md`, la estructura de `CLAUDE.md`, el ADR y sus índices, `README.md`, `llms.txt`, `docs/05-tickets-trabajo.md`, `conv-sql-postgres`, `conv-docker` e `ingeniero-devsecops`, además de `compose.yaml` como nombre de archivo | **Sí** a toda la tabla «Ampliación a aprobar en el gate», incluidas las correcciones con aprobación humana: sin ellas, los textos dicen lo contrario de D-5 y del nombre del archivo, y el siguiente agente que los lea reabre la decisión | Se aplica solo «Necesaria por la spec»; el resto pasa a «Tickets futuros sugeridos» del hub, y el auditor de arquitectura encontrará las contradicciones |
| D-8 | ¿Se alinea `conv-sql-postgres` §5 y §8 con los privilegios por omisión en este mismo PR? | **Sí**, con las frases de la ampliación: si no, el primer auditor que aplique la convención pedirá el mutante MP-3 | Queda en «Tickets futuros sugeridos», como hoy |

## Pasada adversarial

Pasada del propio arquitecto con el método de `abogado-del-diablo` (modo A); el orquestador puede despacharla de nuevo en el gate.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Si un día migra el superusuario o el rol del operador en lugar de `cimenta_migracion`, las tablas nuevas nacen sin permisos y las pruebas de las tablas viejas no lo notan | Guarda en `env.py`, TC-15 y MP-9; TC-31 y MP-3 prueban la tabla posterior |
| 2 | Alta | Los roles son del clúster y la suite crea muchas bases en el mismo: una bajada que los elimina o un `CREATE ROLE` simple romperían la suite, y una subida sobre un rol preexistente con atributos peligrosos los heredaría | Creación con `IF NOT EXISTS` seguida de `ALTER ROLE` que fuerza los atributos (TC-11); la bajada no los toca (TC-12, MP-12, MP-13) |
| 3 | Alta | La guarda de la conexión de aplicación vive en el mismo archivo que el mutante que la burla: un mutante más listo podría cambiar a la vez el usuario y la guarda | La guarda compara literales independientes de la fábrica —nombre, superusuario y pertenencia— y además TC-42 compara conjuntos exactos de privilegios desde el catálogo, que no dependen de la conexión. Cambiar las dos cosas es alterar el oráculo, que la regla del ciclo prohíbe al desarrollador |
| 4 | Alta | El rol de migración es superusuario en local y en pruebas: lo que funciona aquí puede fallar en un gestionado sin superusuario | `(asumido)` declarado en D-5 y en el ADR; las sentencias usadas —`CREATE ROLE`, `ALTER ROLE … SET`, `ALTER DEFAULT PRIVILEGES` sobre sí mismo— las permite `CREATEROLE` en PostgreSQL 16 y posteriores. TKT-058 lo ensaya contra el proveedor real |
| 5 | Media | Con autenticación `trust`, un rol sin contraseña entraría y `CA-10` esc. 2 quedaría verde sin probar nada | El caso conecta por TCP, donde la imagen debería exigir contraseña `(asumido)`; la prueba empírica es TC-61, y MP-10 demuestra que el caso depende de ello |
| 6 | Media | `ALTER ROLE … SET` solo afecta a sesiones nuevas, y una prueba que fijara el valor en su propia sesión pasaría sin demostrar nada | TC-50 a TC-52 usan conexiones nuevas sin `SET`; MP-5 y MP-6 |
| 7 | Media | TC-51 y TC-52 tardan unos 20 s por los valores reales | Se acepta: probar con valores rebajados demostraría el mecanismo pero no el valor aprobado. Si el tiempo de la suite molesta, TKT-009 puede marcar las dos como lentas |
| 8 | Media | `CREATE DATABASE … TEMPLATE` falla si queda una conexión abierta a la plantilla | El arnés lo exige en `plantilla_migrada`; `observacion_sin_contrasena` y `credenciales` se conectan a la base `postgres` |
| 9 | Media | `ALTER ROLE … PASSWORD` con texto plano deja la contraseña en el registro del servidor si este registra sentencias | Se envía cifrada con `encrypt_password`; si la API no existe, se anota el riesgo |
| 10 | Media | `op.execute` con varias sentencias en una sola cadena falla con psycopg 3, y un `%` o un `:nombre` se interpretaría como parámetro | Una sentencia por llamada, escrito en la cabecera de la migración; ninguna sentencia lleva esos caracteres |
| 11 | Media | El diseño deja `DELETE` sobre `sesion` a la aplicación, contra el espíritu de ADR-014 | Decidido como `(asumido)` en `PA-T6`: sin rol de purga, revocarlo sería una regla nueva |
| 12 | Baja | Los UUID fijos de la semilla podrían acabar usados como constantes mágicas en el código | La docstring de `v0002` lo prohíbe: se busca por `clave` |
| 13 | Alta | La partición en dos entregas de D-4 no reduce el riesgo, porque la entrega A no se fusiona sin la B: lo que llega a `Produccion` es lo mismo que con un solo PR | D-4 lo dice así y expone como alternativa la partición real en dos tickets, con lo que la permite y lo que la desaconseja; decide el usuario |

Ninguna objeción revela una regla de negocio que el PRD no tenga ni un choque con un invariante o con las 17 reglas de `CLAUDE.md`. No hay `REQUIERE DECISIÓN` de entrada: las nueve decisiones del gate son de alcance, de valores o de interpretación.

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| La imagen 18 no monta los datos en `/var/lib/postgresql` como se asume | Baja | Medio | TC-02 lo detecta; la fila 2 sigue la documentación de la imagen y lo anota |
| `testcontainers` cambió el módulo de `PostgresContainer` o no trae tipos | Media | Bajo | Regla escrita en la fila 1: módulo alternativo y `ignore_missing_imports` solo para `testcontainers.*` |
| `encrypt_password` no existe en la versión de psycopg | Baja | Bajo | Regla de la fila 3; riesgo anotado en `delta.md` |
| Alembic no encuentra `[tool.alembic]` sin `alembic.ini` | Muy baja | Medio | La fila 3 lo comprueba con la línea de comandos; si falla, se escala en lugar de crear `alembic.ini` |
| El proveedor de producción no permite `CREATEROLE` al rol de migración | Media | Alto | Fuera de este ticket; declarado en el ADR y para TKT-058 |
| `psycopg[binary]` sin rueda para la versión de Python del entorno | Baja | Medio | La fila 1 lo detecta con `uv sync --locked`; se escala, no se compila |
| La suite tarda por crear una base por prueba | Baja | Bajo | Unas cuarenta bases copiadas y unos 20 s de tiempos máximos; se registra la duración en TC-81 |
| Docker Desktop no arrancado en Windows | Media | Medio | `docker info` antes de la fila 2; la suite falla, nunca se salta |
| El tamaño del ticket agota el contexto de una sesión | Alta | Medio | D-4 propone dos entregas; las filas son independientes por sección de la migración |
