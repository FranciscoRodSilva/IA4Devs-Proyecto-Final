# Arranque local

Este documento dice qué hace falta instalar en la máquina de desarrollo, en qué orden se arrancan el backend, el frontend y los verificadores de la documentación, y qué comandos todavía no funcionan porque los habilita un ticket posterior.

Los comandos se ejecutan desde el directorio que indica cada bloque. La lista completa, con su marca de disponibilidad, está en [`CLAUDE.md`](../CLAUDE.md#comandos).

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Git | Cualquier versión reciente | Clonar el repositorio y trabajar con ramas |
| uv | La que instale el gestor oficial | Gestionar el backend: intérprete de Python, entorno y dependencias |
| Python | 3.13 o superior | Ejecutar el backend y los verificadores de `tools/`. `uv` puede descargar el intérprete que falte |
| Node.js | La línea 24 | Ejecutar el frontend. El proyecto la fija en `engines` y `frontend/.npmrc` la hace obligatoria |
| npm | El que trae esa línea de Node | Instalar y ejecutar las dependencias del frontend. No se instala aparte |
| Docker | Docker Desktop con el motor de Linux, o Docker Engine con Compose v2 | PostgreSQL local con `docker compose` y las pruebas con testcontainers |

El repositorio no fija ninguna versión de Python con un archivo propio: el mínimo lo declara `requires-python` en `backend/pyproject.toml`. Node sí se fija con `engines`. Si la versión instalada no es de la línea 24, `npm ci` se detiene con un error `EBADENGINE` en lugar de avisar y seguir.

Las versiones exactas de cada herramienta viven en los archivos de bloqueo, `backend/uv.lock` y `frontend/package-lock.json`. Este documento no las repite, porque envejecerían con cada actualización.

## Backend

Desde `backend/`:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run lint-imports
uv run pytest
```

`uv sync --locked` instala exactamente lo que dice `uv.lock` y falla si el archivo no coincide con `pyproject.toml`. Por eso no se usa `uv sync` a secas en la verificación: un paso que actualiza el bloqueo en silencio no sirve como comprobación.

Los tres comandos siguientes comprueban el formato, el estilo y los tipos. Si `ruff format --check` falla, `uv run ruff format .` reescribe los archivos con el formato correcto.

`uv run lint-imports` comprueba que existan los diez módulos con sus cuatro capas y su `interfaz.py`, que ningún `dominio/` importe FastAPI, SQLAlchemy ni Pydantic, y que un módulo importe a otro solo por su interfaz y solo si el grafo de [arquitectura §5](02-arquitectura.md#5-contextos-delimitados) lo permite. Se ejecuta desde `backend/`, porque busca el paquete `cimenta` en el directorio actual. Su caché, `.import_linter_cache/`, se ignora sola.

`uv run pytest` necesita Docker en marcha: levanta su propio PostgreSQL con testcontainers y no usa el de Compose.

## Base de datos

Desde la raíz del repositorio, se crea el archivo de variables a partir de la plantilla y se levanta PostgreSQL:

```bash
cp .env.example .env
docker compose up -d db
```

`.env` no se versiona. Compose lee de él las contraseñas, y el backend lee de él la conexión. Después, desde `backend/`, se migra y se fijan las contraseñas de los roles de aplicación y de solo lectura:

```bash
uv run --env-file ../.env alembic upgrade head
uv run --env-file ../.env python -m herramientas.contrasenas_roles
```

Alembic se ejecuta desde `backend/` porque su configuración vive en `[tool.alembic]` de `backend/pyproject.toml`, y el `--env-file ../.env` apunta al `.env` de la raíz desde ese directorio.

La imagen crea el rol de migración, `cimenta_migracion`, que es el único con el que Alembic acepta migrar. La migración crea los roles `cimenta_aplicacion` y `cimenta_lectura` sin contraseña; el segundo comando se la fija desde `.env`. Bajar todas las migraciones no elimina esos dos roles, porque son del servidor y no de la base: `docker compose down -v` borra el volumen y lo deja todo como al principio.

En local, el rol de migración es superusuario, porque lo crea la imagen de PostgreSQL. Hoy la migración 0001 exige superusuario o un rol que posea los atributos que ajusta con `ALTER ROLE`: un rol `NOSUPERUSER` con `CREATEROLE` falla con `permission denied to alter role`, porque PostgreSQL solo deja cambiar un atributo a quien lo posee. `NOSUPERUSER` con `CREATEROLE` es el objetivo de producción (asumido; no se ha probado con un proveedor real), aún no alcanzable con la 0001. TKT-058 decide entre quitar los atributos `NO*` del `ALTER ROLE` o crear los roles con ellos desde el entorno.

## Frontend

Desde `frontend/`:

```bash
npm ci
npm run lint
npm run typecheck
```

`npm ci` instala desde `package-lock.json` y no modifica el archivo de bloqueo. Para añadir una dependencia se usa `npm install`, que sí lo modifica.

## Verificadores de la documentación

Desde la raíz del repositorio. Solo requieren Python, sin dependencias:

```bash
python tools/verificar_docs.py
python tools/extraer_mermaid.py
python -m unittest discover -s tools/tests -v
```

`verificar_docs.py` comprueba enlaces, anclas, identificadores, conteos y codificación. `extraer_mermaid.py` valida la sintaxis de los diagramas. Sus pruebas, en `tools/tests/`, cubren la comprobación de codificación. El detalle de cada verificador está en [`tools/README.md`](../tools/README.md).

## Codificación

Los archivos de texto se guardan en UTF-8 y con finales de línea LF. La regla tiene una excepción deliberada:

- Los documentos Markdown y `llms.txt` se guardan **sin BOM**. Un BOM al principio rompe el bloque `---` inicial de los archivos con front matter, como los agentes y las skills de `.claude/`. `verificar_docs.py` falla si encuentra uno.
- Los scripts `.ps1` se guardan **con BOM**. Windows PowerShell 5.1 lee un script sin BOM como ANSI, y los acentos se corrompen sin ningún error visible. Seis agentes del toolkit quedaron ilegibles por esta causa, según el [registro de evolución](../sdd/_evolucion.md). `verificar_docs.py` falla si encuentra un `.ps1` sin BOM.

El archivo `.editorconfig` fija `charset = utf-8` para todo el repositorio y `utf-8-bom` solo para los `.ps1`. El editor lo respeta si tiene el plugin de EditorConfig activo.

## Lo que todavía no arranca

Los comandos siguientes aparecen en `CLAUDE.md` marcados con la fase en la que se habilitan. Hasta entonces fallan por diseño: el código que ejecutan todavía no existe.

| Comando | Lo habilita |
|---|---|
| `uv run fastapi dev` | TKT-005 (asumido: el primer ticket que necesita una aplicación servible) |
| `docker compose up -d minio` | TKT-059 |
| `npm run dev` | TKT-008 |

Cuando un ticket se completa, su `/sdd-completar` quita la marca del comando que habilita en `CLAUDE.md`.

Verificado en copia limpia el: 2026-10-18, en Windows 11, con Docker Engine 29.8.2 (Compose 5.6.0), PostgreSQL 18.6, uv 0.10.7, Python 3.14.3, Node v24.22.0 y npm 11.19.1.
