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
```

`uv sync --locked` instala exactamente lo que dice `uv.lock` y falla si el archivo no coincide con `pyproject.toml`. Por eso no se usa `uv sync` a secas en la verificación: un paso que actualiza el bloqueo en silencio no sirve como comprobación.

Los tres comandos siguientes comprueban el formato, el estilo y los tipos. Si `ruff format --check` falla, `uv run ruff format .` reescribe los archivos con el formato correcto.

`uv run lint-imports` comprueba que existan los diez módulos con sus cuatro capas y su `interfaz.py`, que ningún `dominio/` importe FastAPI, SQLAlchemy ni Pydantic, y que un módulo importe a otro solo por su interfaz y solo si el grafo de [arquitectura §5](02-arquitectura.md#5-contextos-delimitados) lo permite. Se ejecuta desde `backend/`, porque busca el paquete `cimenta` en el directorio actual. Su caché, `.import_linter_cache/`, se ignora sola.

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
| `uv run pytest` | desde TKT-003 o TKT-004, el primero en implementarse (asumido) |
| `uv run alembic upgrade head` | TKT-003 |
| `docker compose up -d db` | TKT-003 |
| `docker compose up -d minio` | TKT-059 |
| `npm run dev` | TKT-008 |

Cuando un ticket se completa, su `/sdd-completar` quita la marca del comando que habilita en `CLAUDE.md`.

Verificado en copia limpia el: 2026-10-17, en Windows 11, con uv 0.10.7, Python 3.14.3, Node v24.22.0 y npm 11.19.1.
