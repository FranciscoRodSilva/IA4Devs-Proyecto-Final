# Arranque local

Este documento dice qué hace falta instalar en la máquina de desarrollo, en qué orden se arrancan el backend, el frontend y los verificadores de la documentación, y qué comandos todavía no funcionan porque los habilita un ticket posterior.

Los comandos se ejecutan desde el directorio que indica cada bloque. La lista completa, con su marca de disponibilidad, está en [`CLAUDE.md`](../CLAUDE.md#comandos).

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Git | Cualquier versión reciente | Clonar el repositorio y trabajar con ramas |
| uv | La que instale el gestor oficial | Gestionar el backend: intérprete de Python, entorno y dependencias |
| Python | 3.13 o superior; el backend se instala con 3.14 (`--python 3.14`) | Ejecutar el backend y los verificadores de `tools/`. `uv` puede descargar el intérprete que falte. No uses uno más nuevo que el último que publica ruedas de las dependencias, como la 3.15: `pyyaml` intenta compilarse y falla sin compilador |
| Node.js | La línea 24 | Ejecutar el frontend. El proyecto la fija en `engines` y `frontend/.npmrc` la hace obligatoria |
| npm | El que trae esa línea de Node | Instalar y ejecutar las dependencias del frontend. No se instala aparte |
| Docker | Docker Desktop con el motor de Linux, o Docker Engine con Compose v2 | PostgreSQL local con `docker compose` y las pruebas con testcontainers |
| Navegador | Chromium o Firefox recientes | Desarrollo local. La cookie de sesión es `Secure` y en `http://localhost` la aceptan esos motores. Chromium está comprobado por el humo de TKT-008b; Firefox lo admite según la especificación de *Secure Contexts* `(asumido, PA-T7)`, sin que el humo lo haya comprobado; Safari no lo admite `(asumido, PA-T7)` |

El repositorio no fija ninguna versión de Python con un archivo propio: el mínimo lo declara `requires-python` en `backend/pyproject.toml`. Node sí se fija con `engines`. Si la versión instalada no es de la línea 24, `npm ci` se detiene con un error `EBADENGINE` en lugar de avisar y seguir.

Las versiones exactas de cada herramienta viven en los archivos de bloqueo, `backend/uv.lock` y `frontend/package-lock.json`. Este documento no las repite, porque envejecerían con cada actualización.

## Backend

Desde `backend/`:

```bash
uv sync --locked --python 3.14
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run lint-imports
uv run python -m herramientas.verificar_float
uv run pytest
```

`uv sync --locked --python 3.14` instala exactamente lo que dice `uv.lock` y falla si el archivo no coincide con `pyproject.toml`. `--python 3.14` fija el intérprete porque `uv` elige el más nuevo que cumpla `requires-python >= 3.13`: con uno más nuevo que el último que publica ruedas de las dependencias, por ejemplo la 3.15, `pyyaml` intenta compilarse y falla sin compilador. Por eso no se usa `uv sync` a secas en la verificación: un paso que actualiza el bloqueo en silencio no sirve como comprobación.

Los tres primeros comandos comprueban el formato, el estilo y los tipos. Si `ruff format --check` falla, `uv run ruff format .` reescribe los archivos con el formato correcto.

`uv run lint-imports` comprueba que existan los diez módulos con sus cuatro capas y su `interfaz.py`, que ningún `dominio/` alcance, ni directa ni indirectamente, nada que no sea la biblioteca estándar o `tipos_base`, que `tipos_base` solo alcance la biblioteca estándar, y que un módulo importe a otro solo por su interfaz y solo si el grafo de [arquitectura §5](02-arquitectura.md#5-contextos-delimitados) lo permite. Se ejecuta desde `backend/`, porque busca en el directorio actual los paquetes `cimenta` y `tipos_base` y el contrato propio de `herramientas/`. Su caché, `.import_linter_cache/`, se ignora sola.

`uv run python -m herramientas.verificar_float` busca `float` en las anotaciones de `cimenta/*/dominio/` y `tipos_base/`: parámetros, retornos y campos, también dentro de `float | None`, `list[float]` o una anotación en cadena. Lee cada archivo como UTF-8 con `utf-8-sig`, así que un BOM no lo rompe. Termina con 0 si no encuentra ninguno; con 1 si encuentra alguno, con su archivo y su línea, o si un archivo revisado no es Python válido, con el error de sintaxis y su línea; y con 2 si no encuentra ningún archivo que revisar, que es lo que pasa si `--raiz` apunta fuera de `backend/`. `Decimal(0.1)` lo marca `ruff check` con la regla `RUF032`.

**Lo que el verificador no ve.** No detecta un alias `Tasa = float` ni `type Tasa = float`; `TypeVar(bound=float)` ni el límite de un parámetro de tipo (`def g[U: float]`); `b.float` tras `import builtins as b`; un valor por omisión `x=0.5`; `float(x)` en el cuerpo de una función, ni lo que va en comentarios `# type:`. Da falso positivo con `Literal["float"]` y `Annotated[int, "float"]`. Por eso `RUF032` y el verificador son dos barreras, no una garantía total: [ADR-020](adr/20261019-tipos-numericos-base.md) lo detalla.

`uv run pytest` necesita Docker en marcha: levanta su propio PostgreSQL con testcontainers y no usa el de Compose. Los tests de los tipos base y de los verificadores no necesitan Docker. Las pruebas del contrato de error y del servidor no necesitan Docker.

Para arrancar la aplicación, aparte de la verificación y porque no termina por sí solo (se detiene con `Ctrl+C`):

```bash
uv run --env-file ../.env fastapi dev
```

`uv run --env-file ../.env fastapi dev` arranca la aplicación en `http://127.0.0.1:8000` con recarga automática; `/docs` muestra el contrato publicado. Sin el archivo de entorno la aplicación arranca, pero la primera ruta que necesita la base responde `500`. Cada petición deja una línea JSON en la salida estándar con su `correlacion_id`, el mismo que viaja en la cabecera `X-Correlacion-Id`.

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
npm test
npm run tipos:verificar
```

`npm ci` instala desde `package-lock.json` y no modifica el archivo de bloqueo. Para añadir una dependencia se usa `npm install`, que sí lo modifica.

`npm run tipos:generar` exporta el OpenAPI de FastAPI sin arrancar el servidor, ejecutando `uv run` en `backend/`, y genera `src/api/generado/`. Por eso necesita `uv` y `uv sync --locked --python 3.14` hecho en `backend/`. Los tipos del contrato de error salen del borrador y son provisionales: su archivo lo dice en la cabecera.

Con el backend en marcha en `127.0.0.1:8000`, `npm run dev` sirve el cliente en `http://localhost:5173` y reenvía `/api` al backend: la cookie de sesión viaja en el mismo origen. Ábrelo como `localhost`, no como `127.0.0.1`. El desarrollo local requiere Chromium o Firefox: la cookie de sesión es `Secure` y esos motores la aceptan en `http://localhost`. Chromium está comprobado por el humo de TKT-008b (3 de 3). Firefox lo admite según la especificación de *Secure Contexts* `(asumido, PA-T7)`, pero el humo no lo ha comprobado. Safari no lo admite `(asumido, PA-T7)`.

`npm run e2e` arranca el backend y el cliente si no están en marcha, siembra un usuario de Compras con una contraseña aleatoria y recorre tres escenarios: entrar y salir, credenciales incorrectas y el menú en un teléfono. Antes: `docker compose up -d db`, `alembic upgrade head`, `contrasenas_roles` y una vez `npx playwright install chromium`.

## Verificadores de la documentación

Desde la raíz del repositorio. Solo requieren Python, sin dependencias:

```bash
python tools/verificar_docs.py
python tools/extraer_mermaid.py
python -m unittest discover -s tools/tests -v
```

`verificar_docs.py` comprueba enlaces, anclas, identificadores, conteos y codificación. `extraer_mermaid.py` valida la sintaxis de los diagramas. Sus pruebas, en `tools/tests/`, cubren la comprobación de codificación, las listas de exclusiones de los verificadores y la guarda de la siembra del humo. El detalle de cada verificador está en [`tools/README.md`](../tools/README.md).

## Codificación

Los archivos de texto se guardan en UTF-8 y con finales de línea LF. La regla tiene una excepción deliberada:

- Los documentos Markdown y `llms.txt` se guardan **sin BOM**. Un BOM al principio rompe el bloque `---` inicial de los archivos con front matter, como los agentes y las skills de `.claude/`. `verificar_docs.py` falla si encuentra uno.
- Los scripts `.ps1` se guardan **con BOM**. Windows PowerShell 5.1 lee un script sin BOM como ANSI, y los acentos se corrompen sin ningún error visible. Seis agentes del toolkit quedaron ilegibles por esta causa, según el [registro de evolución](../sdd/_evolucion.md). `verificar_docs.py` falla si encuentra un `.ps1` sin BOM.

El archivo `.editorconfig` fija `charset = utf-8` para todo el repositorio y `utf-8-bom` solo para los `.ps1`. El editor lo respeta si tiene el plugin de EditorConfig activo.

## Lo que todavía no arranca

Los comandos siguientes aparecen en `CLAUDE.md` marcados con la fase en la que se habilitan. Hasta entonces fallan por diseño: el código que ejecutan todavía no existe.

| Comando | Lo habilita |
|---|---|
| `docker compose up -d minio` | TKT-059 |

Iniciar sesión en local: no hay alta de usuarios todavía (`PA-T13` de TKT-006); las pruebas siembran los suyos. El humo de Playwright siembra el suyo (`frontend/e2e/sembrar_usuario_humo.py`).

Cuando un ticket se completa, su `/sdd-completar` quita la marca del comando que habilita en `CLAUDE.md`.

Verificado en copia limpia el: 2026-10-27, en Windows 11, con Docker Engine 29.8.2 (Compose 5.6.0), PostgreSQL 18.6, uv 0.10.7, Python 3.14.3 (`--python 3.14`), Node v24.22.0 y npm 11.19.1. Backend: `uv sync --locked --python 3.14`, `ruff`, `mypy`, `lint-imports`, `verificar_float`, migraciones, contraseñas de roles y `pytest` (1138 pruebas). Frontend: `npm ci`, `lint`, `typecheck`, `test` (133), `tipos:verificar`, `build`, `npm run dev` con el backend en marcha y `npm run e2e` (3 de 3 en Chromium). El alcance es una copia limpia de `HEAD` de TKT-008a con los archivos de TKT-008b encima, que reutilizó la base de Compose existente.
