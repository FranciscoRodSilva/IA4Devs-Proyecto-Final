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

`uv run lint-imports` comprueba que existan los diez módulos con sus cuatro capas y su `interfaz.py`, que ningún `dominio/` alcance, ni directa ni indirectamente, nada que no sea la biblioteca estándar o `tipos_base`, que `tipos_base` solo alcance la biblioteca estándar, que `trabajos` solo alcance la biblioteca estándar y `sqlalchemy` ([ADR-037](adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md)), y que un módulo importe a otro solo por su interfaz y solo si el grafo de [arquitectura §5](02-arquitectura.md#5-contextos-delimitados) lo permite. Se ejecuta desde `backend/`, porque busca en el directorio actual los paquetes `cimenta`, `tipos_base` y `trabajos` y el contrato propio de `herramientas/`. Su caché, `.import_linter_cache/`, se ignora sola.

`uv run python -m herramientas.verificar_float` busca `float` en las anotaciones de `cimenta/*/dominio/` y `tipos_base/`: parámetros, retornos y campos, también dentro de `float | None`, `list[float]` o una anotación en cadena. Lee cada archivo como UTF-8 con `utf-8-sig`, así que un BOM no lo rompe. Termina con 0 si no encuentra ninguno; con 1 si encuentra alguno, con su archivo y su línea, o si un archivo revisado no es Python válido, con el error de sintaxis y su línea; y con 2 si no encuentra ningún archivo que revisar, que es lo que pasa si `--raiz` apunta fuera de `backend/`. `Decimal(0.1)` lo marca `ruff check` con la regla `RUF032`.

**Lo que el verificador no ve.** No detecta un alias `Tasa = float` ni `type Tasa = float`; `TypeVar(bound=float)` ni el límite de un parámetro de tipo (`def g[U: float]`); `b.float` tras `import builtins as b`; un valor por omisión `x=0.5`; `float(x)` en el cuerpo de una función, ni lo que va en comentarios `# type:`. Da falso positivo con `Literal["float"]` y `Annotated[int, "float"]`. Por eso `RUF032` y el verificador son dos barreras, no una garantía total: [ADR-020](adr/20261019-tipos-numericos-base.md) lo detalla.

`uv run pytest` necesita Docker en marcha: levanta su propio PostgreSQL con testcontainers y no usa el de Compose. Los tests de los tipos base y de los verificadores no necesitan Docker. Las pruebas del contrato de error y del servidor no necesitan Docker.

Para arrancar la aplicación, aparte de la verificación y porque no termina por sí solo (se detiene con `Ctrl+C`):

```bash
uv run --env-file ../.env fastapi dev
```

`uv run --env-file ../.env fastapi dev` arranca la aplicación en `http://127.0.0.1:8000` con recarga automática. `/openapi.json` publica el contrato. `/docs` ya no se pinta en el navegador: su página carga Swagger desde un CDN con un script en línea, y la política de contenido que aplica `TKT-057` lo bloquea, así que el contrato se consulta en `/openapi.json` o en el borrador. Sin `CIMENTA_DB_CONTRASENA_APLICACION` la aplicación no arranca: lanza `ConfiguracionInvalida`, el error nombra la variable y no muestra ningún valor. **El barrido de importaciones interrumpidas** corre antes de servir y solo si hay base configurada, es decir, si `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO` y `CIMENTA_DB_NOMBRE` están definidas y no vacías: sin ellas la aplicación arranca sin barrer ni crear el ejecutor del análisis y registra el aviso `trabajos_omitidos`; con ellas, `fastapi dev` y `fastapi run` exigen la base arriba y migrada, y un barrido fallido impide arrancar ([ADR-037](adr/20261105-trabajos-en-dos-pasos-y-barrido-de-arranque.md)). Dos variables opcionales ajustan el trabajo, y sin ellas valen 5 y 60: `CIMENTA_TRABAJOS_INTERVALO_LATIDO` (de 1 a 60 segundos entre latidos) y `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO` (segundos sin latido para considerar interrumpida una importación, al menos tres veces el intervalo). Cada petición deja una línea JSON en la salida estándar con su `correlacion_id`, el mismo que viaja en la cabecera `X-Correlacion-Id`.

## Base de datos

Desde la raíz del repositorio, se crea el archivo de variables a partir de la plantilla y se levanta PostgreSQL:

```bash
cp .env.example .env
docker compose up -d db
```

Antes de levantar la base hay que rellenar en `.env` las tres contraseñas, `CIMENTA_DB_CONTRASENA_MIGRACION`, `CIMENTA_DB_CONTRASENA_APLICACION` y `CIMENTA_DB_CONTRASENA_LECTURA`, con valores propios y distintos entre sí. La plantilla las trae sin valor a propósito. Un valor válido se genera con `python -c "import secrets; print(secrets.token_urlsafe(24))"`, que imprime uno por ejecución. Compose se niega a arrancar la base mientras la de migración esté vacía, y el mensaje lo dice.

Quien ya tiene un volumen de PostgreSQL creado con las contraseñas anteriores conserva su `.env` tal como está. La imagen usa la contraseña de migración solo al crear el volumen, así que cambiarla en el archivo no cambia la base. Para empezar de cero con contraseñas nuevas, `docker compose down -v` borra el volumen y hay que volver a migrar.

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

`npm run tipos:generar` exporta el OpenAPI de FastAPI sin arrancar el servidor, ejecutando `uv run` en `backend/`, y genera `src/api/generado/`. Por eso necesita `uv` y `uv sync --locked --python 3.14` hecho en `backend/`. No necesita `.env`: el script pasa al servidor una contraseña aleatoria desechable que nunca conecta con ninguna base. Los tipos del contrato de error salen del borrador y son provisionales: su archivo lo dice en la cabecera.

Con el backend en marcha en `127.0.0.1:8000`, `npm run dev` sirve el cliente en `http://localhost:5173` y reenvía `/api` al backend: la cookie de sesión viaja en el mismo origen. Ábrelo como `localhost`, no como `127.0.0.1`. El desarrollo local requiere Chromium o Firefox: la cookie de sesión es `Secure` y esos motores la aceptan en `http://localhost`. Chromium está comprobado por el humo de TKT-008b (3 de 3). Firefox lo admite según la especificación de *Secure Contexts* `(asumido, PA-T7)`, pero el humo no lo ha comprobado. Safari no lo admite `(asumido, PA-T7)`.

`npm run e2e` arranca el backend y el cliente si no están en marcha, siembra sus usuarios de humo (Compras, Director de Proyectos y Dirección General) con una contraseña aleatoria en cada corrida, y también una obra nueva `E2E-LB-<8 hex>` con su línea base en `BORRADOR`, para el recorrido de la línea base. Después recorre sus escenarios: entrar y salir, credenciales incorrectas, el menú en un teléfono, el alta de una obra, el mismo código otra vez y el congelado de una línea base con la captura de un tope. Antes: `docker compose up -d db`, `alembic upgrade head`, `contrasenas_roles` y una vez `npx playwright install --with-deps chromium`. No hace falta `herramientas.semilla_local`.

## Verificadores de la documentación

Desde la raíz del repositorio. Solo requieren Python, sin dependencias:

```bash
python tools/verificar_docs.py
python tools/extraer_mermaid.py
python tools/verificar_escenarios.py
python -m unittest discover -s tools/tests -v
```

`verificar_docs.py` comprueba enlaces, anclas, identificadores, conteos y codificación. `extraer_mermaid.py` valida la sintaxis de los diagramas. `verificar_escenarios.py` comprueba que cada escenario que cuenta tenga un test que lo nombre (ADR-012). Sus pruebas, en `tools/tests/`, cubren la comprobación de codificación, las listas de exclusiones de los verificadores y la guarda de la siembra del humo. El detalle de cada verificador está en [`tools/README.md`](../tools/README.md).

## Integración continua

El pipeline, `.github/workflows/ci.yml`, corre en cada pull request las comprobaciones que la tabla de abajo lista, cada una en su trabajo. Si un comando pasa en local y falla en el pipeline, o al revés, la causa casi siempre es el entorno y no el comando: revisa la versión de Python y que el árbol de trabajo esté limpio.

Para reproducir un trabajo en local, desde el directorio que indica cada fila:

| Trabajo | Qué ejecuta | Cómo reproducirlo en local |
|---|---|---|
| `backend` | Formato, lint, tipos, `verificar_float` y pruebas con cobertura | Desde `backend/`, los comandos de la sección Backend, y después `uv run pytest --cov=cimenta --cov=tipos_base --cov=contrato_error --cov=servidor --cov=trabajos --cov-report=term --cov-report=xml:cobertura.xml --junitxml=pytest.xml`. Necesita Docker |
| `fronteras` | `lint-imports` | Desde `backend/`: `uv run lint-imports` |
| `contrato-api` | Reservado para TKT-061 | Nada que reproducir todavía |
| `frontend` | Lint, tipos, pruebas y `tipos:verificar` | Desde `backend/`, `uv sync --locked --python 3.14`; desde `frontend/`, los comandos de la sección Frontend |
| `humo` | Recorrido de Playwright con la base migrada | Desde la raíz, `cp .env.example .env`, se generan las tres contraseñas de la sección Base de datos y después `docker compose up -d --wait db`. El pipeline genera las suyas en el propio trabajo, con `openssl rand`, y nunca las versiona; desde `backend/`, `uv sync --locked --python 3.14`; después, las secciones Base de datos y Frontend (con su `npx playwright install --with-deps chromium`) y, desde `frontend/`, `npm run e2e`. Necesita Docker |
| `herramientas` | Pruebas de `tools/` con `unittest` y `verificar_escenarios.py` | Desde la raíz: `python -m unittest discover -s tools/tests`. La salida no debe contener `skipped=`, porque la guarda del pipeline falla si aparece. Después, `python tools/verificar_escenarios.py`; el pipeline le pasa además `--activas-base` con el `historias_activas.txt` de la base del PR, cuando la base lo tiene |
| `workflows` | `zizmor` sobre los flujos | Desde la raíz: `uvx zizmor@1.31.1 --offline .github/workflows` |
| `documentacion` | `verificar_docs.py`, `markdownlint-cli2`, Vale, `lychee` y `mermaid-cli` | Desde la raíz: `python tools/verificar_docs.py`. Los demás, en [Calidad de la documentación en local](#calidad-de-la-documentación-en-local) |

El trabajo `herramientas` corre las pruebas en el intérprete 3.14 con `uv run --no-project`; en local basta con cualquier Python de los que admite el proyecto.

### Auditar las dependencias en local

El trabajo `dependencias` audita el lock del backend, el del frontend y el de `mermaid-cli` (`.github/mermaid/`) con la política de [stack §6.4](06-stack-tecnologico.md#64-dependencias). Para reproducirlo, desde `backend/`, en una shell de Bash (Git Bash en Windows):

```bash
AUDITORIA="$(mktemp -d)"
uv export --locked --all-groups --no-emit-project --format requirements.txt -o "$AUDITORIA/req.txt"
uv run pip-audit -r "$AUDITORIA/req.txt" --require-hashes --disable-pip --strict -f json -o "$AUDITORIA/pip-audit.json" || true
uv run python ../tools/severidad_pip_audit.py "$AUDITORIA/pip-audit.json"
echo $?
rm -rf "$AUDITORIA"
```

`pip-audit` termina en 1 cuando encuentra vulnerabilidades, por eso su línea lleva `|| true`: quien decide es el script, que sale con 0 si ningún hallazgo falla, con 1 si alguno es `ALTA`, `CRÍTICA` o `DESCONOCIDA`, y con 2 si el informe no existe o OSV no responde. Sin el `|| true`, la auditoría se cortaría antes de llegar al script. La versión de `uv` en uso también escribe el contenido del `req.txt` por la salida estándar; si estorba, añade `> /dev/null` a la línea de `uv export`.

Desde la raíz del repositorio, el frontend y el lock de `mermaid-cli` se auditan con la opción nativa de `npm`:

```bash
(cd frontend && npm audit --audit-level=high)
(cd .github/mermaid && npm audit --audit-level=high)
```

Cada comando sale con 0 mientras no haya avisos `high` ni `critical`; los `moderate` y `low` se listan y no fallan. Necesita acceso al registro de npm.

### Calidad de la documentación en local

El trabajo `documentacion` corre `markdownlint-cli2`, Vale y `lychee` sobre el mismo alcance, y en el pipeline cualquier hallazgo falla. En local **solo informan**: el hallazgo se ve, pero nada bloquea. Desde la raíz del repositorio:

```bash
npx --yes markdownlint-cli2@0.24.0 "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md
uvx --from vale==3.25.1.0 vale --output=line docs sdd README.md CLAUDE.md tools/README.md
lychee --config lychee.toml --no-progress 'docs/**/*.md' 'sdd/**/*.md' README.md CLAUDE.md tools/README.md
```

- `markdownlint-cli2` necesita Node, que `npx` usa. Imprime cada hallazgo con su archivo y su línea. Sus reglas están en `.markdownlint-cli2.jsonc`.
- `vale` lo ejecuta `uvx` con el envoltorio de PyPI. La primera vez descarga el binario oficial de Vale 3.25.1, así que necesita red. Lee `.vale.ini` y, sin alertas, no imprime nada.
- `lychee` no se instala con ningún gestor de paquetes que este documento haya probado. Descarga el binario de la release oficial `v0.24.2` del repositorio `lycheeverse/lychee` y ponlo en el `PATH` antes de ejecutar el comando.

## Codificación

Los archivos de texto se guardan en UTF-8 y con finales de línea LF. La regla tiene una excepción deliberada:

- Los documentos Markdown y `llms.txt` se guardan **sin BOM**. Un BOM al principio rompe el bloque `---` inicial de los archivos con front matter, como los agentes y las skills de `.claude/`. `verificar_docs.py` falla si encuentra uno.
- Los scripts `.ps1` se guardan **con BOM**. Windows PowerShell 5.1 lee un script sin BOM como ANSI, y los acentos se corrompen sin ningún error visible. Seis agentes del toolkit quedaron ilegibles por esta causa, según el [registro de evolución](../sdd/_evolucion.md). `verificar_docs.py` falla si encuentra un `.ps1` sin BOM.

El archivo `.editorconfig` fija `charset = utf-8` para todo el repositorio y `utf-8-bom` solo para los `.ps1`. El editor lo respeta si tiene el plugin de EditorConfig activo.

## Pruebas contra los catálogos reales (TKT-013 y TKT-014)

Los archivos del cliente **no se versionan**. Para ejecutar las pruebas de `tests/test_tkt013_archivos_reales.py`, `tests/test_tkt014_archivos_reales.py` y las de totales que usan los reales, define en PowerShell:

```powershell
$env:CIMENTA_CATALOGO_ENITI = 'D:\ruta\Presupuesto Base Tablaroca Eniti T5 AP 2.xlsx'
$env:CIMENTA_CATALOGO_UNION = 'D:\ruta\AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx'
```

Union debe ser el libro de **precios unitarios** (`AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`) con la hoja `CATALOGO DE CONCEPTOS`, `#REF!` en P.U. e importe (CA-7) **y las hojas de APU** (TKT-014). ENITI debe incluir sus hojas de APU numeradas. Sin esas variables, esas pruebas hacen `pytest.skip` con el motivo en el resumen (`pytest -ra`).

### Oráculo de explosión Union (TKT-016)

Para `tests/test_tkt016_archivo_real.py` (CA-10), define además un CSV UTF-8 con encabezado `clave,cantidad,importe` (punto decimal, sin separador de miles), extraído a mano del libro `AP-058-25 EXPLOSION DE INSUMOS` y guardado **fuera del repositorio** junto a los `.xlsx` del cliente:

```powershell
$env:CIMENTA_EXPLOSION_UNION = 'D:\ruta\explosion-union.csv'
```

Requiere también `CIMENTA_CATALOGO_UNION` apuntando al libro P.U. de la misma obra. Si falta alguna variable, la reconciliación hace `pytest.skip` con el motivo explícito. Con el libro Union medido en TKT-014 (cero asociaciones catálogo↔APU, `PA-T3`), TC-26 sigue omitida aunque existan las rutas: el skip indica «PA-16.6 · PA-T3».

## Lo que todavía no arranca

Los comandos siguientes aparecen en `CLAUDE.md` marcados con la fase en la que se habilitan. Hasta entonces fallan por diseño: el código que ejecutan todavía no existe.

| Comando | Lo habilita |
|---|---|
| `docker compose up -d minio` | TKT-059 |

Iniciar sesión en local: `uv run --env-file ../.env python -m herramientas.semilla_local` siembra, solo en una base local, un usuario por rol (`<rol en minúsculas>@cimenta.test`) con la contraseña de `CIMENTA_SEMILLA_CONTRASENA`, y 27 insumos sintéticos con su precio. Se niega si el host no es local. No hay alta de usuarios fuera de esta herramienta (`PA-T13` de TKT-006); las pruebas siembran los suyos. El humo de Playwright siembra los suyos con `frontend/e2e/sembrar_usuario_humo.py`, que lee `CIMENTA_HUMO_CORREO` y `CIMENTA_HUMO_CONTRASENA` y, desde TKT-012a, también `CIMENTA_HUMO_ROL` (la clave del rol; por omisión `COMPRAS`) y `CIMENTA_HUMO_NOMBRE` (por omisión `Humo Compras`). La preparación global (`frontend/e2e/preparacion-global.ts`) lo ejecuta tres veces y genera una contraseña aleatoria por corrida, de modo que ninguna se guarda en el repositorio: siembra `humo.compras@cimenta.test` con el rol `COMPRAS`, `humo.director@cimenta.test` con el rol `DIRECTOR_PROYECTOS` y `humo.direccion@cimenta.test` con el rol `DIRECCION_GENERAL`. Del segundo deja el correo y la contraseña en `CIMENTA_HUMO_DP_CORREO` y `CIMENTA_HUMO_DP_CONTRASENA`, que usan el recorrido E2E de las obras y de la línea base; del tercero, en `CIMENTA_HUMO_DG_CORREO` y `CIMENTA_HUMO_DG_CONTRASENA`, que usa la captura del tope.

Una línea base de demostración para ver la pantalla en local la siembra `herramientas.semilla_linea_base_local`, después de `herramientas.semilla_local`, con el mismo host local obligatorio. Desde `backend/`, `uv run --env-file ../.env python -m herramientas.semilla_linea_base_local` crea la obra `DEMO-018A` en `PLANEACION` con su línea base en `BORRADOR` y sale con `OBRA_ID=<uuid>` en la última línea; la pantalla queda en `/obras/<OBRA_ID>/linea-base`. Acepta `CIMENTA_SEMILLA_LB_CODIGO` (por omisión `DEMO-018A`, y cada ejecución necesita un código nuevo) y `CIMENTA_SEMILLA_LB_CORREO` (por omisión `director_proyectos@cimenta.test`). El README lo explica con más detalle.

Cuando un ticket se completa, su `/sdd-completar` quita la marca del comando que habilita en `CLAUDE.md`.

Verificado en copia limpia el: 2026-10-27, en Windows 11, antes de TKT-057 (las contraseñas sin valor, `CIMENTA_DB_CONTRASENA_APLICACION` y la política de contenido son posteriores y no están en esa verificación; se comprueban con un arranque local completo desde un `.env` recién copiado, fila 14 de [`sdd/tickets/tkt-057/design.md`](../sdd/tickets/tkt-057/design.md)), con Docker Engine 29.8.2 (Compose 5.6.0), PostgreSQL 18.6, uv 0.10.7, Python 3.14.3 (`--python 3.14`), Node v24.22.0 y npm 11.19.1. Backend: `uv sync --locked --python 3.14`, `ruff`, `mypy`, `lint-imports`, `verificar_float`, migraciones, contraseñas de roles y `pytest` (1138 pruebas). Frontend: `npm ci`, `lint`, `typecheck`, `test` (133), `tipos:verificar`, `build`, `npm run dev` con el backend en marcha y `npm run e2e` (3 de 3 en Chromium). El alcance es una copia limpia de `HEAD` de TKT-008a con los archivos de TKT-008b encima, que reutilizó la base de Compose existente.
