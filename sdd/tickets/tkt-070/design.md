# Design · TKT-070 · Despliegue de prueba en una VPS con Caddy y PostgreSQL

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que escribe `/sdd-ejecutar`

## Estrategia

La VPS reutiliza el `compose.yaml` de la raíz tal como está —la misma imagen `postgres:18.6` que usan el desarrollo local y testcontainers— y le suma un único archivo de ajustes, `despliegue/compose.vps.yaml`, con la política de reinicio y el límite de memoria. Cada entorno es un **proyecto de Compose distinto** (`cimenta-prod` y `cimenta-test`) levantado con `-p` y con su propio `.env` fuera del repositorio, así que cada uno tiene su red, su volumen y su puerto de bucle local, y ninguno comparte red con el otro ni con Caddy. Un tercer proyecto, `cimenta-caddy`, publica los puertos 80 y 443 y responde en cada nombre con un texto de marcador, porque no hay aplicación todavía: Caddy no necesita alcanzar ninguna base. La migración se aplica desde el equipo de quien despliega, por túnel SSH, con `alembic` y `herramientas.contrasenas_roles` sin tocar una línea del backend, y un script de la biblioteca estándar en `tools/` comprueba desde dentro y desde fuera de la VPS que ninguna base queda expuesta y que el HTTP solo redirige.

El trabajo se reparte en dos mitades que no se mezclan: el agente escribe y ensaya en local los archivos y la documentación (filas `A`), y la persona dueña, que es la única con acceso SSH, ejecuta la guía en la VPS (filas `V`). La guía se escribe **antes** de las filas `V` para que seguirla sea la prueba de `CA-13`.

## Escalera de decisión

Una fila por objeto que el ticket propone crear o modificar. El peldaño donde paró es la justificación del objeto.

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `compose.yaml` de la raíz como base de cada entorno | 3 · reuso | Ya declara `postgres:18.6`, el volumen en `/var/lib/postgresql`, el puerto enlazado a `127.0.0.1`, el chequeo de salud y la variable obligatoria `${CIMENTA_DB_CONTRASENA_MIGRACION:?…}` que exige `CA-10`. Es además la única fuente de la imagen para testcontainers (`backend/tests/conftest.py:130-139`): un Compose nuevo con su propio `image:` abriría una segunda versión que puede divergir. Se usa sin modificarlo |
| Nombre de proyecto por entorno (`cimenta-prod`, `cimenta-test`) | 2 · nativo | La opción `-p` de Compose tiene precedencia sobre el `name: cimenta` del archivo (documentación de Compose consultada con Context7: «`-p` > `COMPOSE_PROJECT_NAME` > `name:` > directorio»). Con `-p`, Compose prefija red, volumen y contenedor: `cimenta-prod_pg_datos`, `cimenta-prod_default`, `cimenta-prod-db-1`. No hace falta un archivo por entorno |
| Red propia por entorno | 2 · nativo | La red `default` que Compose crea por proyecto ya separa `prod` de `test` y de Caddy. **No** se marca `internal: true`: una red interna no publica puertos y rompería el acceso de bucle local que usa el túnel (experimento E-L15) |
| `despliegue/compose.vps.yaml` (nuevo, cuatro claves) | 5 · objeto nuevo, mínimo | `restart` y `mem_limit` no están en el `compose.yaml` raíz y no deben estar: en desarrollo, un PostgreSQL que vuelve solo tras reiniciar el portátil y un tope de memoria serían ruido. Un archivo de ajustes que Compose fusiona con `-f` es la forma nativa de añadirlos sin tocar el de desarrollo. No declara `image:`, `ports:` ni `environment:`, para no divergir de la base |
| Puertos de bucle local `5433` (`prod`) y `5434` (`test`) | 2 · nativo | La variable `CIMENTA_DB_PUERTO` del `compose.yaml` raíz ya parametriza el puerto del anfitrión. Se eligen distintos del `5432` local para que el túnel en Windows no choque con el PostgreSQL de desarrollo, y el mismo número a los dos lados del túnel para que un único archivo sirva en la VPS y en el equipo |
| Bases `cimenta_prod` y `cimenta_test` | 2 · nativo | `CIMENTA_DB_NOMBRE` ya es variable. Un nombre distinto por entorno hace que un comando lanzado contra el túnel equivocado falle con «la base no existe» en lugar de escribir en el otro entorno. Ninguna migración depende del nombre de la base (comprobado: ninguna usa `current_database()`) |
| `.env` de cada entorno en la VPS (`/srv/cimenta/prod/.env`, `/srv/cimenta/test/.env`) y su copia `.env.prod` / `.env.test` en el equipo | 3 · reuso | Son las mismas seis claves `CIMENTA_DB_*` de `.env.example`. El archivo se genera **en la VPS** con `openssl rand -hex 24`, como ya hace el trabajo `humo` de `ci.yml:130-135`, y se copia byte a byte al equipo con `scp`. Así no pasa por PowerShell 5.1, que escribe UTF-16 con `>` y BOM con `Set-Content -Encoding utf8`. `.gitignore:27` ya ignora `.env.*` |
| Ausencia de `CIMENTA_SEMILLA_CONTRASENA` en `.env.prod` y `.env.test` | 3 · reuso | `semilla_local.main` (`backend/herramientas/semilla_local.py:292-296`) lee esa variable **antes** de conectar y aborta si falta. Es una segunda guarda contra la siembra por el túnel, que hoy solo mira el host (supuesto 4 de la spec), sin tocar código |
| `despliegue/caddy/compose.yaml` (nuevo) | 5 · objeto nuevo, mínimo | Un solo proceso puede escuchar en 80 y 443 de la VPS, y no puede pertenecer a ninguno de los dos entornos: si viviera en `cimenta-prod`, bajar `prod` dejaría a `test` sin HTTPS. Proyecto propio `cimenta-caddy`, con `name:` en el archivo porque hay una sola instancia |
| `despliegue/caddy/Caddyfile` (nuevo) | 5 · objeto nuevo, mínimo | Dos bloques de sitio con `respond` y una opción global. La redirección de HTTP a HTTPS **no** se escribe: es la redirección automática de Caddy, con `308` (peldaño 2, documentación de Caddy consultada con Context7: «Caddy uses `308` as the status code in its automatic HTTP to HTTPS redirects») |
| `acme_ca` fijado a Let's Encrypt, con autoridad de pruebas por variable | 2 · nativo | Sin `acme_ca`, Caddy usa Let's Encrypt **y ZeroSSL** como respaldo, y `CA-3` exige un certificado de Let's Encrypt. La variable `CIMENTA_ACME_CA` —valor por omisión en Compose: el directorio de producción— permite ajustar contra la autoridad de pruebas sin editar el Caddyfile, que la documentación de Caddy recomienda «para pruebas o desarrollo» |
| Volúmenes `caddy_datos` (`/data`) y `caddy_config` (`/config`) | 2 · nativo | Son las rutas `XDG_DATA_HOME` y `XDG_CONFIG_HOME` de la imagen oficial (Context7, `caddy-docker`). Un volumen con nombre sobrevive a `docker compose down` sin `-v`, que es lo que pide `CA-S5` |
| `cap_drop: [ALL]`, `cap_add: [NET_BIND_SERVICE]` y `security_opt: ["no-new-privileges:true"]` en Caddy, **sin** `user:` | 2 · nativo | [`conv-docker` §5](../../../.claude/skills/conv-docker/SKILL.md) prohíbe procesos como `root`. **E-L4 refutó la primera idea del diseño, `user: "1000:1000"`:** el volumen con nombre se crea con `/data` y `/config` propiedad de `root` y modo `755`, y un proceso con el usuario 1000 recibe `Permission denied` al escribir ahí, que es donde Caddy guarda sus certificados. Alternativa elegida, ya ensayada con éxito en local: Caddy corre como `root` dentro de su contenedor, pero con todas las capacidades retiradas salvo `NET_BIND_SERVICE` y sin poder ganar privilegios; escribe en `/data` y `/config` y responde `308`. Es una excepción a conv-docker §5 y el ADR la declara en sus costes aceptados |
| `despliegue/comprobar_permisos.sql` (nuevo) | 5 · objeto nuevo, mínimo | `CA-5` y `CA-R1` piden consultar `pg_roles`, `pg_authid`, `has_table_privilege` y `pg_trigger` **en la base remota**. Las pruebas de permisos existentes (`test_tkt011_permisos.py`…) corren solo contra testcontainers. Una única sentencia `SELECT` versionada evita escribir SQL dentro de una cadena de PowerShell 5.1, que no conserva las comillas dobles anidadas al pasarlas a un ejecutable |
| `tools/verificar_despliegue.py` (nuevo) | 5 · objeto nuevo | Lo pide `CA-S3`. Biblioteca estándar, compatible con Python 3.12 (el de Ubuntu 24.04) y con 3.14 (el del pipeline), para que corra igual en la VPS y en Windows. Vive en `tools/` porque ahí está la suite de `unittest` que ya ejecuta el trabajo `herramientas` de `ci.yml` |
| `tools/tests/test_verificar_despliegue.py` (nuevo) | 5 · objeto nuevo | El rojo del script: las funciones de análisis se prueban con salidas reales de `docker ps` y `ss` capturadas en E-L12 |
| Exclusión de `duckdns\.org` en `lychee.toml` | 4 · cambio mínimo | La VPS está pagada un mes. Cuando se apague, cualquier URL `duckdns.org` que alguien escriba como enlace rompería el detector semanal `enlaces.yml`. Una línea en la configuración compartida por los dos flujos lo cierra para siempre; los flujos no cambian, y `test_definicion_documentacion.py` solo vigila sus argumentos |
| Guía `docs/despliegue-prueba-vps.md` (nueva) | 5 · objeto nuevo | Must de la spec. Va en `docs/` y no en `despliegue/` porque el trabajo `documentacion` solo pasa `markdownlint`, `Vale` y `lychee` sobre `docs/`, `sdd/`, `README.md`, `CLAUDE.md` y `tools/README.md` (`ci.yml:226`, `:234`, `:241`): en `despliegue/` la guía solo la vería `verificar_docs.py` |
| ADR del destino de prueba | 5 · objeto nuevo | Must de la spec (`CA-11`) |
| Lo descartado | 1 · YAGNI | Ningún `Dockerfile`, imagen ni servicio de aplicación (regla 17, conv-docker §4). Ningún correo ACME: Let's Encrypt emite sin él. Ningún `!override` de `ports:` en el archivo de ajustes. Ningún actualizador de DuckDNS: la IP es fija. Ningún límite de memoria en Caddy: la spec solo lo pide para PostgreSQL. Ningún diagrama Mermaid: la tabla de topología basta. Ninguna prueba automática nueva en `backend/` |

Ningún objeto paró en el peldaño 4 tocando un invariante. Ninguno de los treinta y ocho invariantes ni de las diecisiete reglas de `CLAUDE.md` estorba.

## Capas afectadas

Ni dominio, ni aplicación, ni API, ni frontend, ni ningún módulo de `backend/cimenta/`. Ninguna migración nueva.

### Infraestructura de despliegue

#### Disposición en el repositorio y en la VPS

```text
repositorio                                  VPS (/srv/cimenta, copia por scp)
compose.yaml                     sin cambios  /srv/cimenta/compose.yaml
despliegue/compose.vps.yaml      nuevo        /srv/cimenta/despliegue/compose.vps.yaml
despliegue/comprobar_permisos.sql nuevo       (solo en el equipo: se ejecuta por el túnel)
despliegue/caddy/compose.yaml    nuevo        /srv/cimenta/despliegue/caddy/compose.yaml
despliegue/caddy/Caddyfile       nuevo        /srv/cimenta/despliegue/caddy/Caddyfile
tools/verificar_despliegue.py    nuevo        /srv/cimenta/tools/verificar_despliegue.py
.env.prod, .env.test             ignorados    /srv/cimenta/prod/.env, /srv/cimenta/test/.env  (700 el directorio, 600 el archivo)
```

La VPS recibe los archivos con `scp` desde el árbol de trabajo, no con `git clone`: durante `/sdd-ejecutar` la rama no está publicada, y el flujo de entrega prohíbe empujarla a mano. Los archivos conservan la ruta relativa de la raíz del repositorio, así que todo comando de la guía se escribe igual en la VPS y en el equipo. No existe `/srv/cimenta/.env`: con `--env-file` explícito Compose no lee el `.env` del directorio del proyecto, y su ausencia impide que un comando sin `--env-file` tome secretos por sorpresa.

#### Topología

| | `prod` | `test` | Caddy |
|---|---|---|---|
| Proyecto de Compose | `cimenta-prod` (`-p`) | `cimenta-test` (`-p`) | `cimenta-caddy` (`name:`) |
| Archivos | `compose.yaml` + `despliegue/compose.vps.yaml` | igual | `despliegue/caddy/compose.yaml` |
| Contenedor | `cimenta-prod-db-1` | `cimenta-test-db-1` | `cimenta-caddy-caddy-1` |
| Nombre | `apbuildings.duckdns.org` | `apbuildings-test.duckdns.org` | ambos |
| Base | `cimenta_prod` | `cimenta_test` | — |
| Publicación | `127.0.0.1:5433->5432/tcp` | `127.0.0.1:5434->5432/tcp` | `0.0.0.0:80`, `0.0.0.0:443` (y `[::]`) |
| Volumen | `cimenta-prod_pg_datos` | `cimenta-test_pg_datos` | `cimenta-caddy_caddy_datos`, `cimenta-caddy_caddy_config` |
| Red | `cimenta-prod_default` | `cimenta-test_default` | `cimenta-caddy_default` |
| `.env` en la VPS | `/srv/cimenta/prod/.env` | `/srv/cimenta/test/.env` | ninguno |
| Copia en el equipo | `.env.prod` (raíz del repositorio) | `.env.test` | — |
| Límite de memoria | `768m` | `768m` | ninguno |
| Reinicio | `unless-stopped` | `unless-stopped` | `unless-stopped` |

Los dos límites suman 1.5 GiB de los 4 GB de la VPS. `CA-S2` mide el uso en reposo, no el límite.

#### Objetos

| Objeto | Tipo | Detalle exacto |
|---|---|---|
| `despliegue/compose.vps.yaml` | Archivo de ajustes de Compose | Comentario de cabecera de dos líneas: «Ajustes de la VPS de prueba (TKT-070) sobre el compose.yaml de la raíz. No declara imagen, puertos ni entorno: los hereda.» y «Guía: docs/despliegue-prueba-vps.md». Contenido: `services:` → `db:` → `restart: unless-stopped` y `mem_limit: 768m`. Nada más |
| `despliegue/caddy/compose.yaml` | Compose | Cabecera con el mismo patrón. `name: cimenta-caddy`. Servicio `caddy`: `image: caddy:2.11.7`; `cap_drop: [ALL]`; `cap_add: [NET_BIND_SERVICE]`; `security_opt: ["no-new-privileges:true"]`; `restart: unless-stopped`; `ports:` `"80:80"` y `"443:443"`; `environment:` `CIMENTA_ACME_CA: ${CIMENTA_ACME_CA:-https://acme-v02.api.letsencrypt.org/directory}`; `volumes:` `./Caddyfile:/etc/caddy/Caddyfile:ro`, `caddy_datos:/data`, `caddy_config:/config`. Volúmenes de primer nivel `caddy_datos` y `caddy_config`. Sin `443/udp`: HTTP/3 queda fuera |
| `despliegue/caddy/Caddyfile` | Configuración de Caddy | Comentario de cabecera con TKT-070 y la guía. Bloque global `{ acme_ca {$CIMENTA_ACME_CA} }`. Sitio `apbuildings.duckdns.org { respond "CIMENTA entorno prod: sin aplicacion todavia (TKT-070)" 200 }`. Sitio `apbuildings-test.duckdns.org { respond "CIMENTA entorno test: sin aplicacion todavia (TKT-070)" 200 }`. El texto va sin acentos a propósito: se lee en la consola de PowerShell 5.1, que no decodifica UTF-8 por omisión. Formateado como lo deja `caddy fmt` (tabulador de sangría) |
| `despliegue/comprobar_permisos.sql` | Consulta de verificación, una sola sentencia `SELECT … UNION ALL …` | Dos columnas: `comprobacion text`, `ok boolean`, en el orden de la tabla siguiente. Cabecera de comentario con TKT-070, `CA-5`, `CA-7`, `CA-R1` y la orden que la ejecuta. Solo lectura de catálogo: ningún `SET`, ningún DDL ni DML |
| `tools/verificar_despliegue.py` | Script, biblioteca estándar | Ver «El script de verificación» |
| `tools/tests/test_verificar_despliegue.py` | Pruebas `unittest` | Ver plan de pruebas, `TC-U1`…`TC-U12` |
| `lychee.toml` | Configuración | La lista `exclude` pasa a `['cimenta\.test', '^https://medium\.com/', 'duckdns\.org']`, con una línea de comentario encima: «La VPS de prueba de TKT-070 se contrató un mes: sus nombres de DuckDNS dejan de responder al apagarla.» |

**Filas de `comprobar_permisos.sql`.** Veintidós, cada una con su `ok` verdadero cuando el estado es el esperado.

| `comprobacion` | Expresión de `ok` | Criterio |
|---|---|---|
| `rol_existe_cimenta_migracion` | `EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cimenta_migracion')` | `CA-5` |
| `rol_existe_cimenta_aplicacion` | ídem con `cimenta_aplicacion` | `CA-5` |
| `rol_existe_cimenta_lectura` | ídem con `cimenta_lectura` | `CA-5` |
| `login_cimenta_aplicacion` | `(SELECT rolcanlogin FROM pg_roles WHERE rolname = 'cimenta_aplicacion')` | `CA-5` |
| `login_cimenta_lectura` | ídem con `cimenta_lectura` | `CA-5` |
| `contrasena_cimenta_aplicacion` | `(SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname = 'cimenta_aplicacion')` | `CA-5`. Lee `pg_authid`, que exige superusuario: el rol de migración lo es (supuesto 2) |
| `contrasena_cimenta_lectura` | ídem con `cimenta_lectura` | `CA-5` |
| `aplicacion_sin_update_bitacora` | `NOT has_table_privilege('cimenta_aplicacion', 'bitacora', 'UPDATE')` | `CA-R1` · invariante 10 |
| `aplicacion_sin_delete_bitacora` | ídem `DELETE` | `CA-R1` · invariante 10 |
| `aplicacion_sin_truncate_bitacora` | ídem `TRUNCATE` | `CA-R1` · invariante 10 |
| `aplicacion_sin_update_intento_acceso` | ídem sobre `intento_acceso`, `UPDATE` | `CA-R1` · invariante 20 |
| `aplicacion_sin_delete_intento_acceso` | ídem `DELETE` | `CA-R1` · invariante 20 |
| `aplicacion_sin_truncate_intento_acceso` | ídem `TRUNCATE` | `CA-R1` · invariante 20 |
| `aplicacion_sin_update_linea_base_concepto` | ídem sobre `linea_base_concepto`, `UPDATE` | `CA-R1` · invariante 14 |
| `aplicacion_sin_delete_linea_base_concepto` | ídem `DELETE` | `CA-R1` · invariante 14 |
| `aplicacion_sin_truncate_linea_base_concepto` | ídem `TRUNCATE` | `CA-R1` · invariante 14 |
| `lectura_sin_select_sesion` | `NOT has_table_privilege('cimenta_lectura', 'sesion', 'SELECT')` | `CA-R1` · invariante 21 |
| `lectura_sin_select_usuario` | ídem sobre `usuario`. `has_table_privilege` mira el privilegio de tabla, no los de columna que concede la migración 0001 (`:124`) | `CA-R1` · invariante 21 |
| `disparador_trg_linea_base_concepto_inmutable` | `EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '…' AND NOT tgisinternal AND tgenabled = 'O')` | `CA-R1` · invariante 14 |
| `disparador_trg_explosion_presupuesto_inmutable` | ídem | `CA-R1` · invariante 14 |
| `disparador_trg_linea_base_solo_avanza` | ídem | `CA-R1` · invariante 14 |
| `usuario_sin_filas` | `NOT EXISTS (SELECT 1 FROM usuario)` | `CA-7`: no se ejecutó la siembra |

Los nombres de los disparadores salen de `backend/migraciones/versions/v0007_presupuesto_linea_base_e_importacion.py:151`, `:234` y `:239`.

#### El script de verificación

`tools/verificar_despliegue.py`, con docstring que cite TKT-070, `CA-1`, `CA-2`, `CA-3`, `CA-4` y `CA-S3`. `from __future__ import annotations`; nada posterior a Python 3.12. Dos subórdenes:

```text
python3 tools/verificar_despliegue.py anfitrion [--puertos 5432 5433 5434]
python  tools/verificar_despliegue.py remoto [--nombres apbuildings.duckdns.org apbuildings-test.duckdns.org] [--ip IP] [--puertos 5432 5433 5434] [--espera 5]
```

Firmas exactas:

| Firma | Qué devuelve |
|---|---|
| `@dataclass(frozen=True) class Exposicion: contenedor: str; publicacion: str; puerto_anfitrion: int` | Una publicación del puerto 5432/tcp de un contenedor a una dirección que no es `127.0.0.1` |
| `exposiciones_docker(salida_docker_ps: str) -> list[Exposicion]` | Analiza la salida de `docker ps --format "{{.Names}}\t{{.Ports}}"`. Cada entrada de `Ports` separada por `", "` con forma `<dirección>:<puerto>-><puerto contenedor>/tcp`. Devuelve las que tienen puerto de contenedor `5432` y dirección distinta de `127.0.0.1`. Ignora entradas sin `->` (puerto expuesto sin publicar) |
| `puertos_db_publicados(salida_docker_ps: str) -> set[int]` | Los puertos de anfitrión de toda publicación de `5432/tcp`, en cualquier dirección |
| `escuchas_expuestas(salida_ss: str, puertos: set[int]) -> list[str]` | Analiza `ss -tln`. Salta la línea cuyo primer campo es `State`. La dirección local es el cuarto campo; el puerto, lo que sigue al último `:`. Devuelve `"<dirección>:<puerto>"` de cada escucha con puerto en `puertos` cuya dirección no empieza por `127.` ni es `[::1]` (`0.0.0.0`, `*`, `[::]` y cualquier otra) |
| `evaluar_sondeo(ip: str, puerto: int, conecto: bool) -> str \| None` | `"la base responde desde fuera en <ip>:<puerto>"` si `conecto`; `None` si no |
| `evaluar_redireccion(nombre: str, estado: int, location: str \| None, cuerpo: bytes) -> list[str]` | Vacía si `estado` está en `{301, 308}`, `location == f"https://{nombre}/"` y `b"CIMENTA"` no está en `cuerpo`. Si no, un texto por cada fallo, que nombra el estado, la `Location` recibida o el contenido |
| `evaluar_certificado(nombre: str, certificado: dict[str, Any], ahora: float) -> list[str]` | `certificado` con la forma de `ssl.SSLSocket.getpeercert()`. Vacía si algún par `("organizationName", "Let's Encrypt")` está en `issuer` y `ssl.cert_time_to_seconds(certificado["notAfter"]) > ahora`. Si no, un texto que nombra el emisor o la fecha |
| `main(argv: list[str] \| None = None, *, ejecutar: Callable[[list[str]], str] = _ejecutar, sondear: Callable[[str, int, float], bool] = _sondear, pedir_http: Callable[[str, float], tuple[int, str \| None, bytes]] = _pedir_http, obtener_certificado: Callable[[str, float], dict[str, Any]] = _obtener_certificado, ahora: Callable[[], float] = time.time) -> int` | Código de salida |

Las cuatro dependencias por omisión: `_ejecutar` corre la orden con `subprocess.run(…, capture_output=True, text=True, check=True)` y devuelve `stdout`; `_sondear` intenta `socket.create_connection((ip, puerto), timeout=espera)` y devuelve `True` si conecta, `False` ante `OSError`; `_pedir_http` hace `GET /` con `http.client.HTTPConnection(nombre, 80, timeout=espera)`, que no sigue redirecciones, y lee como máximo 4096 bytes del cuerpo; `_obtener_certificado` abre `ssl.create_default_context().wrap_socket(…, server_hostname=nombre)` al 443 y devuelve `getpeercert()`.

Comportamiento de `main`:

- `anfitrion`: ejecuta `docker ps --format "{{.Names}}\t{{.Ports}}"` y `ss -tln`. Comprueba `exposiciones_docker` y `escuchas_expuestas` con la unión de `--puertos` y `puertos_db_publicados`. Imprime `OK  <texto>` o `FALLA  <texto>` por comprobación; una `FALLA` de exposición nombra la publicación entera y el contenedor, por ejemplo `FALLA  0.0.0.0:5435->5432/tcp en cimenta-sonda-expuesta`.
- `remoto`: resuelve `--ip` con `socket.gethostbyname` del primer nombre si no se da. Sondea cada puerto de `--puertos` (`CA-1`, `CA-2`), pide HTTP a cada nombre (`CA-4`) y su certificado (`CA-3`). Un `ssl.SSLError` o un `OSError` al pedir HTTP o certificado es una `FALLA` de ese nombre, no un error del script: el certificado de la autoridad de pruebas falla aquí, como debe.
- Última línea: `Resultado: <n> fallas`. Sale con `0` sin fallas, con `1` con alguna, y con `2` si la suborden no existe o si `docker` o `ss` no se pueden ejecutar (`FileNotFoundError`, `subprocess.CalledProcessError`), con el motivo por la salida de error. El fallo es cerrado: en Windows, `anfitrion` sale con `2` porque no hay `ss`.

`anfitrion` se ejecuta en la VPS con `sudo` si el usuario no está en el grupo `docker`.

#### Variables que leen las herramientas del backend, y cómo apuntan al túnel

`backend/migraciones/env.py` construye su motor con `url_migracion()`, y `backend/herramientas/contrasenas_roles.py` conecta con las mismas variables. Las dos leen de `backend/herramientas/conexion.py`: `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO`, `CIMENTA_DB_NOMBRE`, `CIMENTA_DB_CONTRASENA_MIGRACION`, y la segunda además `CIMENTA_DB_CONTRASENA_APLICACION` y `CIMENTA_DB_CONTRASENA_LECTURA`. El usuario es la constante `ROL_MIGRACION`, no una variable. Por eso `.env.prod` lleva `CIMENTA_DB_HOST=127.0.0.1`, `CIMENTA_DB_PUERTO=5433` y `CIMENTA_DB_NOMBRE=cimenta_prod`, y el extremo local del túnel escucha en `127.0.0.1:5433`. El mismo archivo, copiado a la VPS, le da a Compose el puerto, el nombre de la base y la contraseña de migración; Compose ignora las otras claves.

#### La secuencia de migración, por entorno

Desde `backend/`, en una ventana de PowerShell nueva, con el túnel de ese entorno abierto en otra:

1. **Comprobación previa.** `Get-ChildItem Env: | Where-Object Name -Match '^(CIMENTA_|PG)'` no devuelve nada. Si una variable del mismo nombre ya está en el entorno, el resultado de E-L8 dice si `uv run --env-file` la respeta o la pisa; la guía exige el entorno vacío en los dos casos.
2. **Túnel.** En otra ventana: `ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:5434:127.0.0.1:5434 <usuario>@apbuildings.duckdns.org` para `test` (5433 para `prod`). `ExitOnForwardFailure` hace que `ssh` termine si el puerto local está ocupado, en lugar de quedarse conectado sin reenviar. Comprobación: `Test-NetConnection 127.0.0.1 -Port 5434` devuelve `TcpTestSucceeded : True`.
3. **Migración.** `uv run --env-file ../.env.test alembic upgrade head`, y `alembic current` informa `0008 (head)`.
4. **Contraseñas.** `uv run --env-file ../.env.test python -m herramientas.contrasenas_roles` imprime `Contraseñas fijadas para cimenta_aplicacion y cimenta_lectura.`
5. **Rojo de `CA-8`, con la base ya migrada.** Tiene que ir **después** de los pasos 3 y 4: los roles `cimenta_aplicacion` y `cimenta_lectura` los crea la migración 0001, y en una base sin migrar `PGOPTIONS='-c role=cimenta_aplicacion'` falla con `FATAL: role "cimenta_aplicacion" does not exist` al abrir la conexión, sin llegar nunca a la guarda de `env.py`. Con la base migrada: `$env:PGOPTIONS = '-c role=cimenta_aplicacion'`, luego `uv run --env-file ../.env.test alembic upgrade head`: `env.py` aborta con `RuntimeError: Las migraciones de CIMENTA las ejecuta solo cimenta_migracion, y esta conexión es cimenta_aplicacion…`. Después `Remove-Item Env:PGOPTIONS` y `uv run --env-file ../.env.test alembic current`, que sigue informando `0008 (head)`.
6. **Comprobación de permisos** (`CA-5`, `CA-7`, `CA-R1`), por el túnel:

   ```powershell
   uv run --env-file ../.env.test python -c "import os,sys,pathlib,psycopg; e=os.environ; c=psycopg.connect(host=e['CIMENTA_DB_HOST'], port=int(e['CIMENTA_DB_PUERTO']), dbname=e['CIMENTA_DB_NOMBRE'], user='cimenta_migracion', password=e['CIMENTA_DB_CONTRASENA_MIGRACION'], connect_timeout=5); f=c.execute(pathlib.Path('../despliegue/comprobar_permisos.sql').read_text(encoding='utf-8')).fetchall(); [print(*x, sep=' | ') for x in f]; sys.exit(0 if f and all(x[-1] for x in f) else 1)"
   ```

   El código de Python lleva solo comillas simples, porque PowerShell 5.1 descarta las dobles anidadas al pasar argumentos a un ejecutable. Termina con código `0` y veintidós líneas acabadas en `True`.
7. **Rechazo de la siembra** (solo en `test`): `uv run --env-file ../.env.test python -m herramientas.semilla_local` termina con `Falta la variable de entorno CIMENTA_SEMILLA_CONTRASENA…` sin conectar, y la fila `usuario_sin_filas` del paso 6 sigue en `True`. Contra `prod` no se ejecuta nunca, ni siquiera para ver el rechazo.

`herramientas.semilla_local` no se ejecuta en ningún otro paso. El `.env` local no se apunta nunca al túnel.

## Orden de implementación

Se ejecuta fila por fila. Las filas `A` las ejecuta un agente en el repositorio; las filas `V` las ejecuta **a mano la persona dueña**, en la VPS o en su equipo contra la VPS, siguiendo la guía, y el orquestador pega en `impl.md` la salida que ella le entregue. Es un ticket con Definition of Done de Documentación: no hay suite de `pytest` nueva. El rojo de cada fila es su rechazo: la exposición, la variable que falta, el rol equivocado, la contraseña del otro entorno.

**Regla de evidencia para todas las filas.** Nada que contenga un secreto entra en `impl.md`: ni el contenido de un `.env`, ni `docker compose config` sin `--no-interpolate`, ni `docker inspect` sin `--format`, porque los tres imprimen `POSTGRES_PASSWORD`. Los ensayos locales usan un archivo de entorno de usar y tirar en el directorio temporal de la sesión, con contraseñas que dicen `sonda-no-secreta`.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A1 | **Registrar la evidencia ya ejecutada, sin repetirla.** Copia a `impl.md`, tal cual, la tabla «Resultados de los experimentos ejecutados» de este diseño y la muestra de `docker ps` que usa A5 como dato. **No vuelve a ejecutar E-L6, E-L7, E-L8, E-L12 ni E-L14**: ya se ejecutaron al revisar el diseño. Solo repite `docker pull caddy:2.11.7`, por si la etiqueta cambió | Ninguno: prepara los datos de prueba de A5 | `ingeniero-devsecops` | `haiku` · bajada por tarea mecánica verificable por comando ([metodología §14.2](../../metodologia.md#142--el-orquestador-elige-el-modelo-en-cada-despacho)) | `impl.md` contiene la tabla de resultados y la salida de `docker pull caddy:2.11.7` | Pendiente |
| A2 | **`despliegue/compose.vps.yaml`.** Contenido exacto de la tabla de objetos. Ensayo local con un proyecto `cimenta-sonda` en el puerto `55433` | TC-09, TC-S2a | `ingeniero-devsecops` | `haiku` · ídem | E-L1 (rechazo sin contraseña, sin contenedor creado), E-L2 (`restart` y `mem_limit` fusionados, `805306368 unless-stopped` en `docker inspect --format`) y E-L15. Al final, `docker compose -p cimenta-sonda … down -v`. TC-09 nace en verde porque el rechazo lo da el `compose.yaml` raíz que se reutiliza: se anota así en `impl.md` | Pendiente |
| A3 | **Caddy.** `despliegue/caddy/compose.yaml` y `despliegue/caddy/Caddyfile`, contenido exacto de la tabla de objetos, **sin `user:`**: E-L4 ya demostró que con el usuario 1000 no se puede escribir en `/data`. La fila A6 declara en el ADR, en costes aceptados, que Caddy corre como `root` dentro de su contenedor, con las capacidades retiradas | TC-05a | `ingeniero-devsecops` | `haiku` · ídem | E-L3 (`Valid configuration`, sin aviso de formato), E-L4 repetido con los ajustes del Compose (redirección `308` local, escritura en `/data` y `/config` y volumen con nombre) y E-L5 | Pendiente |
| A4 | **`despliegue/comprobar_permisos.sql` y ensayo local completo de la secuencia de migración** contra el proyecto `cimenta-sonda`: rojo de la consulta sobre una base sin migrar, pasos 3 a 7 de la secuencia, mutación del permiso y bucle de `CA-6` | TC-06a, TC-07a, TC-08a, TC-11a, TC-INV-1a | `desarrollador-sql` | `sonnet` · los permisos de un rol (metodología §14.2) | E-L9, E-L10, E-L11 y E-L13 con su resultado esperado. Al final, `down -v` del proyecto sonda | Pendiente |
| A5 | **Script de verificación, por TDD.** Rojo: `tester-backend` escribe `tools/tests/test_verificar_despliegue.py` con TC-U1…TC-U12, usando como datos las salidas reales de E-L12, y lo ejecuta: falla por `ModuleNotFoundError: No module named 'verificar_despliegue'` o equivalente de carga del módulo. Verde: `ingeniero-devsecops` escribe `tools/verificar_despliegue.py` con las firmas exactas de «El script de verificación», un test cada vez. Refactor con la suite en verde | TC-U1…TC-U12 | `tester-backend` (rojo) · `ingeniero-devsecops` (verde) | `sonnet` el tester (nunca por debajo de quien escribe) · `haiku` el desarrollador | El archivo de pruebas añade `tools/` a `sys.path` con el mismo patrón que `tools/tests/test_verificar_escenarios.py:60-63`, porque `tools/` no es un paquete. `python -m unittest discover -s tools/tests -p "test_verificar_despliegue.py" -v` en verde; `python -m unittest discover -s tools/tests -v` sin `skipped=`; `uv run --no-project --python 3.12 python -m unittest discover -s tools/tests -p "test_verificar_despliegue.py"` en verde (compatibilidad con la VPS); `python tools/verificar_despliegue.py anfitrion` en Windows sale con `2` y nombra `ss`. Mutantes M1, M2 y M3 del plan de pruebas, cada uno con su test en rojo | Pendiente |
| A6 | **Documentación antes de la VPS.** ADR, su fila en el índice, los recuentos, la guía y el resto de «Documentación afectada», y la línea de `lychee.toml` | TC-12, y prepara TC-13 | `ingeniero-devsecops` | `haiku` · el contenido de cada documento está dictado en este diseño | El ADR, su fila del índice y los tres recuentos de `CLAUDE.md`, `README.md` y `llms.txt` van **juntos en esta fila**: `python -m unittest discover -s tools/tests -v` falla (`test_definicion_revision.py`) mientras haya un ADR de más y un recuento de menos. `python tools/verificar_docs.py` sin problemas, con `adrs 34` (solo cuenta archivos y comprueba el índice, no los recuentos); `python tools/extraer_mermaid.py`; `npx --yes markdownlint-cli2@0.24.0 "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md` sin errores; `uvx --from vale==3.25.1.0 vale --output=line docs sdd README.md CLAUDE.md tools/README.md` sin salida; `python -m unittest discover -s tools/tests -v` en verde. `lychee` lo comprueba el pipeline | Pendiente |
| V1 | **Preparar la VPS** (guía §4). E-V1, E-V2, E-V5. Crear `/srv/cimenta/{despliegue/caddy,tools,prod,test}`, `chmod 700` a `prod` y `test`. Copiar con `scp` los cinco archivos desde la raíz del repositorio. Generar los dos `.env` en la VPS con `umask 077` y `openssl rand -hex 24`, y copiarlos al equipo con `scp` como `.env.prod` y `.env.test` | TC-10a | **Persona dueña** (manual, VPS y equipo) | — | `stat -c '%a %U' /srv/cimenta/prod/.env /srv/cimenta/test/.env` → `600 <usuario>` dos veces; en el equipo, `git check-ignore -v .env.prod .env.test` cita `.gitignore:27` para los dos | Pendiente `(sin ejecutar)` |
| V2 | **Levantar las bases** (guía §5): `docker compose -p cimenta-prod -f compose.yaml -f despliegue/compose.vps.yaml --env-file /srv/cimenta/prod/.env up -d --wait db`, y lo mismo con `test`. Bajar `test` sin `-v` y comprobar que `prod` sigue; volver a subir `test` | TC-S1, TC-S2b | **Persona dueña** | — | `docker compose ls` lista `cimenta-prod` y `cimenta-test` y no `cimenta`; `docker network inspect cimenta-prod_default --format '{{range .Containers}}{{.Name}} {{end}}'` → solo `cimenta-prod-db-1` (ídem `test`); `docker stats --no-stream` suma menos de 2 GiB; `docker inspect cimenta-prod-db-1 --format '{{.HostConfig.Memory}} {{.HostConfig.RestartPolicy.Name}}'` → `805306368 unless-stopped` | Pendiente `(sin ejecutar)` |
| V3 | **Rojo y verde de la exposición** (guía §8): `sudo python3 tools/verificar_despliegue.py anfitrion` en verde; arrancar la sonda de E-V3; el script en rojo; parar la sonda; el script otra vez en verde | TC-01, TC-02 | **Persona dueña** | — | Salida `0` → `1` nombrando `0.0.0.0:5435->5432/tcp en cimenta-sonda-expuesta` → `0`; las órdenes de E-V3 muestran la regla de Docker para el 5435 sin que `ufw` lo liste | Pendiente `(sin ejecutar)` |
| V4 | **Caddy contra la autoridad de pruebas, luego la real** (guía §6) | TC-04, TC-05 | **Persona dueña** | — | E-V6: con la de pruebas, los registros muestran la emisión de los dos nombres; `remoto` falla solo en `certificado` (no es de confianza). Con la real, `remoto` pasa `CA-3` y `CA-4`, y los registros nombran `acme-v02.api.letsencrypt.org` | Pendiente `(sin ejecutar)` |
| V5 | **Migración por túnel**, primero `test` y después `prod`: los siete pasos de «La secuencia de migración» (el paso 7 solo en `test`) | TC-06, TC-08, TC-11, TC-INV-1 | **Persona dueña** | — | `alembic current` → `0008 (head)` en los dos; `comprobar_permisos.sql` sale con `0` y 22 `True` en los dos; el rojo de `CA-8` en cada base ya migrada y con contraseñas, con `alembic current` aún en `0008 (head)` | Pendiente `(sin ejecutar)` |
| V6 | **Contraseñas cruzadas** (guía §8, `CA-6`): primero el control positivo, luego los seis cruces | TC-07 | **Persona dueña** | — | El control positivo termina sin error; cada cruce termina en `password authentication failed for user "cimenta_<rol>"`, no en `connection refused` ni en `timeout` | Pendiente `(sin ejecutar)` |
| V7 | **Comprobaciones externas** desde el equipo, que está en otra red: `python tools/verificar_despliegue.py remoto` y las órdenes literales de `CA-1` | TC-03, TC-04, TC-05 | **Persona dueña** | — | `remoto` sale con `0`; `Test-NetConnection <ip> -Port 5432`, `-Port 5433` y `-Port 5434` → `TcpTestSucceeded : False` | Pendiente `(sin ejecutar)` |
| V8 | **Recrear Caddy y reiniciar la VPS** (guía §9): `CA-S5`, luego `CA-S4`. Búsqueda de secretos en el repositorio (`CA-9`) | TC-S5, TC-S4, TC-10 | **Persona dueña** | — | Tras `down` y `up -d` de Caddy, `docker compose -f despliegue/caddy/compose.yaml logs caddy \| grep -c "certificate obtained successfully"` → `0`; tras `sudo reboot`, `docker ps` muestra los tres contenedores y `remoto` sale con `0`; la búsqueda de `CA-9` no imprime `ENCONTRADO` y `git ls-files` no lista otro `.env` que `.env.example` | Pendiente `(sin ejecutar)` |
| A7 | **Cierre documental.** Cada desviación entre la guía y lo que la persona dueña tuvo que hacer en V1…V8 se corrige en la guía, y queda en `impl.md` con la fila `V` que la reveló. Si no hubo ninguna, se anota «sin desviaciones» | TC-13, TC-12 otra vez | `ingeniero-devsecops` | `haiku` · ídem | Los mismos verificadores de A6; la persona dueña confirma en la sesión que siguió la guía sin otra fuente | Pendiente |

**Talla.** Unas 790 líneas: `compose.vps.yaml` 6, Caddy 40, `comprobar_permisos.sql` 45, script 170, sus pruebas 150, `lychee.toml` 2, ADR 75, guía 280 y retoques en otros documentos 25. Unas 415 son configuración y código, y unas 375 son documentación. **Pasa de las ~400**; la partición está en «Preguntas para el gate».

## Experimentos

Toda afirmación del diseño sobre lo que una herramienta permite o rechaza se apoya en uno de estos experimentos. **El arquitecto no pudo ejecutarlos** (su sesión no tenía consola), y por eso la revisión posterior ejecutó en local, con Docker 29 y `uv` en el equipo de la persona dueña, los experimentos E-L1 a E-L4, E-L6 a E-L15 salvo E-L5, sobre una base y un Caddy de usar y tirar con contraseñas `sonda-no-secreta`, y los desmontó después. Sus resultados están en «Resultados de los experimentos ejecutados». Los que dependen de archivos que aún no existen —E-L5, y la repetición de E-L2, E-L3 y E-L4 sobre los archivos finales— los corre el agente de la fila que los cita. Los de la VPS los ejecuta la persona dueña y siguen `(sin ejecutar)`.

| # | Afirmación | Orden | Quién y dónde | Resultado esperado | Si no se cumple |
|---|---|---|---|---|---|
| E-L1 | `${VAR:?}` aborta Compose y no crea el contenedor | Archivo de usar y tirar sin `CIMENTA_DB_CONTRASENA_MIGRACION`; `docker compose -p cimenta-sonda -f compose.yaml -f despliegue/compose.vps.yaml --env-file <temporal>/sin_contrasena.env up -d db`; luego `docker ps -a --filter name=cimenta-sonda` | Agente, A2, Windows | Salida distinta de cero con `required variable CIMENTA_DB_CONTRASENA_MIGRACION is missing a value: define CIMENTA_DB_CONTRASENA_MIGRACION en .env`; ningún contenedor | Se detiene la fila: la premisa de `CA-10` es falsa y se escala |
| E-L2 | El archivo de ajustes se fusiona y Compose aplica `mem_limit` sin Swarm | Con el archivo completo: `docker compose … config --no-interpolate`; `up -d --wait db`; `docker inspect cimenta-sonda-db-1 --format '{{.HostConfig.Memory}} {{.HostConfig.RestartPolicy.Name}}'` | Agente, A2 | `restart: unless-stopped` y `mem_limit` en la configuración; `805306368 unless-stopped` | Se sustituye `mem_limit: 768m` por `deploy.resources.limits.memory: 768M`, que Compose también traduce a `HostConfig.Memory` (código de `create.go`, Context7), y se repite |
| E-L3 | El Caddyfile es válido | `docker run --rm -v <repo>/despliegue/caddy/Caddyfile:/etc/caddy/Caddyfile:ro -e CIMENTA_ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory caddy:2.11.7 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` | Agente, A3 | `Valid configuration`, sin `not formatted` | Se corrige la sintaxis o se aplica `caddy fmt` y se repite |
| E-L4 | Caddy, con las capacidades retiradas, escribe en sus volúmenes y redirige con `308` sin cuerpo. **Ejecutado al revisar el diseño: con `--user 1000:1000` falla con `Permission denied` al escribir en `/data`; con `--cap-drop ALL --cap-add NET_BIND_SERVICE --security-opt no-new-privileges:true` pasa.** | `docker run -d --name cimenta-sonda-caddy --cap-drop ALL --cap-add NET_BIND_SERVICE --security-opt no-new-privileges:true -p 127.0.0.1:18080:80 -v cimenta-sonda-caddy:/data -v <Caddyfile>:/etc/caddy/Caddyfile:ro -e CIMENTA_ACME_CA=https://127.0.0.1:9/directory caddy:2.11.7`; `curl.exe -sS -i -H "Host: apbuildings.duckdns.org" http://127.0.0.1:18080/`; `docker logs cimenta-sonda-caddy`; luego `docker rm -f` y `docker volume rm` | Agente, A3. La autoridad apunta a un puerto cerrado de bucle local para que ninguna petición ACME salga del equipo | `HTTP/1.1 308 Permanent Redirect`, `Location: https://apbuildings.duckdns.org/`, cuerpo vacío; `docker exec cimenta-sonda-caddy sh -c 'touch /data/prueba && touch /config/prueba'` termina sin error; los registros no dicen `permission denied` | Se escala: sin escribir en `/data` Caddy no puede guardar sus certificados |
| E-L5 | El Compose de Caddy es válido y el valor por omisión de la autoridad se aplica | `docker compose -f despliegue/caddy/compose.yaml config` sin la variable definida | Agente, A3 | `CIMENTA_ACME_CA: https://acme-v02.api.letsencrypt.org/directory`, `cap_drop: ALL`, `cap_add: NET_BIND_SERVICE`, `no-new-privileges:true`, los dos volúmenes | Se corrige y se repite |
| E-L6 | En Windows PowerShell 5.1, `curl` es un alias de `Invoke-WebRequest` | `powershell.exe -NoProfile -Command "Get-Alias curl"` | Agente, A1 | `curl -> Invoke-WebRequest` | Si no hay alias, la guía mantiene `curl.exe`, que funciona igual |
| E-L7 | El cliente `ssh` del equipo acepta la opción `ExitOnForwardFailure`. **Ejecutado:** en este equipo `ssh` es el de Git (`C:\Program Files\Git\usr\bin\ssh.exe`), no el de Windows, y `ssh -G` imprime `exitonforwardfailure yes` pero **no** imprime la línea `localforward`. El reenvío con `-L` no se puede comprobar sin un servidor: lo comprueba V5 con un túnel real y `Test-NetConnection` | `ssh -G -o ExitOnForwardFailure=yes -L 127.0.0.1:5433:127.0.0.1:5433 ejemplo.invalid` | Hecho al revisar el diseño | `exitonforwardfailure yes`; la sintaxis `-L 127.0.0.1:5433:127.0.0.1:5433` es estándar y V5 la prueba de verdad | Si V5 no abre el túnel, la guía §7 lo nombra como trampa y se anota la salida |
| E-L8 | Qué gana si la variable ya está en el entorno: el archivo o el entorno | `$env:CIMENTA_DB_PUERTO = '1'`; `uv run --no-project --env-file <temporal>/puerto.env python -c "import os; print(os.environ['CIMENTA_DB_PUERTO'])"` con `CIMENTA_DB_PUERTO=55433` en el archivo; `Remove-Item Env:CIMENTA_DB_PUERTO` | Agente, A1 | Se anota el valor impreso, sea cual sea | Nada cambia: la comprobación previa de la secuencia exige el entorno vacío en los dos casos |
| E-L9 | `PGOPTIONS='-c role=…'` llega a la guarda de `env.py`, **solo con la base ya migrada**: antes de la migración 0001 el rol no existe y la conexión falla antes de la guarda | Base sonda migrada y con contraseñas fijadas (pasos 3 y 4); `$env:PGOPTIONS='-c role=cimenta_aplicacion'`; `uv run --env-file <temporal>/sonda.env alembic upgrade head`. Control negativo previo, con la base sin migrar: el mismo comando falla con `role "cimenta_aplicacion" does not exist`, y eso queda anotado como resultado inválido para `CA-8` | Agente, A4 | `RuntimeError` con `esta conexión es cimenta_aplicacion`; `alembic current` sigue en `0008 (head)` | **Escalar** (`/sdd-escalar`): `url_migracion()` fija el usuario a `cimenta_migracion` y no hay otra forma de llegar a la guarda sin cambiar código. `CA-8` tendría que reescribirse |
| E-L10 | `comprobar_permisos.sql` distingue el estado correcto del incorrecto | Rojo: la consulta del paso 6 contra la sonda sin migrar → error `role "cimenta_aplicacion" does not exist` o `relation "bitacora" does not exist`. Verde: tras los pasos 3 y 4, código `0` y 22 `True`. Mutación: `docker exec cimenta-sonda-db-1 psql -U cimenta_migracion -d cimenta_sonda -c "GRANT UPDATE ON bitacora TO cimenta_aplicacion"` → `aplicacion_sin_update_bitacora \| False` y código `1`; después `REVOKE` y otra vez `0` | Agente, A4 | Lo descrito | Se corrige la consulta |
| E-L11 | El bucle de `CA-6` funciona con las comillas de PowerShell 5.1 y distingue la contraseña ajena de un túnel caído | Un segundo archivo de usar y tirar con las mismas claves y contraseñas distintas; el bucle de la guía §8 contra la sonda; luego el mismo bucle con el puerto `55499`, cerrado | Agente, A4, en `powershell.exe` 5.1 | Seis `password authentication failed`. **Ejecutado:** con el puerto cerrado el resultado fue `connection timeout expired` en este equipo, no `connection refused`; la guía nombra **ambos** como resultado inválido, igual que cualquier salida que no diga `password authentication failed`. El control positivo abrió sesión | Se corrige el fragmento de la guía |
| E-L12 | Formato real de `docker ps` y de `ss` para los datos de prueba del script | Con la base local arriba: `docker ps --format "{{.Names}}\t{{.Ports}}"`. Con `docker run -d --rm --name cimenta-sonda-expuesta -p 0.0.0.0:55435:5432 alpine:3.22 sleep 120`, otra vez. Para `ss`: `docker run --rm --network host alpine:3.22 ss -tln` no sirve en Docker Desktop, así que la muestra de `ss` la toma la fila A5 de la página de manual de `ss` de iproute2 y la confirma V3 | Agente, A1 | **Ejecutado:** `cimenta-sonda-db-1\t127.0.0.1:55433->5432/tcp` y `cimenta-sonda-expuesta\t0.0.0.0:55435->5432/tcp`. Docker Desktop no imprimió la entrada `[::]` que Docker Engine en Linux sí añade; las pruebas de A5 usan **las dos formas**, la real de arriba y la variante `0.0.0.0:55435->5432/tcp, [::]:55435->5432/tcp`, y V3 confirma la de Linux | Las pruebas usan la forma que se imprimió, no la esperada |
| E-L13 | La siembra se niega sin su variable antes de conectar | `uv run --env-file <temporal>/sonda.env python -m herramientas.semilla_local` (el archivo no trae `CIMENTA_SEMILLA_CONTRASENA`) | Agente, A4 | `Falta la variable de entorno CIMENTA_SEMILLA_CONTRASENA`; `usuario_sin_filas` sigue `True` | Se escala: el supuesto 4 quedaría sin la segunda guarda |
| E-L14 | La etiqueta `caddy:2.11.7` existe | `docker pull caddy:2.11.7` | Agente, A1 | Descarga correcta | Regla de A1 |
| E-L15 | Una red `internal: true` no publica puertos | Archivo temporal que añade `networks: default: internal: true` al proyecto sonda; `up -d`; `Test-NetConnection 127.0.0.1 -Port 55433` | Agente, A2 | `TcpTestSucceeded : False` | Si publica, no cambia nada del diseño: la red por omisión ya aísla. Se corrige la justificación en la escalera |
| E-V1 | Docker vuelve solo tras reiniciar | `docker version --format '{{.Server.Version}}'`; `docker compose version`; `systemctl is-enabled docker` | Persona dueña, V1, VPS | `29.x`, `v5.7.x`, `enabled` | `sudo systemctl enable docker` y se anota |
| E-V2 | `ufw` deja solo 22, 80 y 443 | `sudo ufw status verbose` | Persona dueña, V1 | `22/tcp`, `80/tcp`, `443/tcp` `ALLOW IN` y política `deny (incoming)` | Se anota; la protección de la base no depende de `ufw` |
| E-V3 | Docker publica saltándose `ufw` cuando se enlaza a todas las interfaces | `docker run -d --rm --name cimenta-sonda-expuesta -p 0.0.0.0:5435:5432 alpine:3.22 sleep 600`; `ss -tln \| grep 5435`; `sudo ufw status \| grep 5435`; `sudo iptables -S DOCKER \| grep 5432` (o `sudo nft list ruleset \| grep 5432` si `iptables` no lista la cadena); `docker rm -f cimenta-sonda-expuesta` | Persona dueña, V3. La sonda es un `alpine` sin nada escuchando: no expone ninguna base de verdad | `ss` muestra `0.0.0.0:5435`; `ufw` no lo lista; la regla `ACCEPT` de Docker hacia el 5432 del contenedor existe | Se anota la salida tal cual en la guía: la causa de la protección sigue siendo que ningún `ports:` de una base enlaza a `0.0.0.0` |
| E-V5 | Python 3.12 en la VPS | `python3 --version` | Persona dueña, V1 | `Python 3.12.x` | Si es menor, se escala antes de V3 |
| E-V6 | HTTP-01 por el puerto 80 y cambio de autoridad sin reutilizar el certificado de pruebas | `CIMENTA_ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory docker compose -f despliegue/caddy/compose.yaml up -d`; `docker compose -f despliegue/caddy/compose.yaml logs caddy \| grep -E "certificate obtained successfully\|acme-staging"`; después `docker compose -f despliegue/caddy/compose.yaml up -d --force-recreate` sin la variable y el mismo `logs` con `acme-v02` | Persona dueña, V4 | Dos emisiones con la de pruebas; dos emisiones nuevas con la real; `remoto` pasa `CA-3` | Si `remoto` sigue viendo el emisor de pruebas: `down`, `docker volume rm cimenta-caddy_caddy_datos`, `up -d`. Cuesta una emisión real por nombre |

## Resultados de los experimentos ejecutados

Ejecutados el 2026-11-02 al revisar el diseño, en el equipo de la persona dueña, con Docker 29.9.2, `uv`, `postgres:18.6` y `caddy:2.11.7`. Se usó un proyecto `cimenta-sonda` en el puerto `55433`, con contraseñas `sonda-no-secreta-*` en archivos de entorno fuera del repositorio. Todo se desmontó después: sin contenedores, volúmenes ni redes de la sonda. Ningún secreto entra en esta tabla.

| # | Resultado | ¿Cambió el diseño? |
|---|---|---|
| E-L1 | Sin `CIMENTA_DB_CONTRASENA_MIGRACION`, `docker compose up -d db` aborta con `required variable CIMENTA_DB_CONTRASENA_MIGRACION is missing a value: define CIMENTA_DB_CONTRASENA_MIGRACION en .env` y no crea ningún contenedor | No |
| E-L2 | El archivo de ajustes se fusiona: `docker inspect` da `805306368 unless-stopped` y `docker ps` publica `127.0.0.1:55433->5432/tcp`. Un archivo de entorno con claves de más (`HOST`, `APLICACION`, `LECTURA`) no molesta a Compose | No |
| E-L3 | `caddy validate` da `Valid configuration` con el Caddyfile del diseño, y `caddy fmt --diff` no marca diferencias | No |
| E-L4 | **Con `--user 1000:1000`: `touch /data/prueba` da `Permission denied`; `/data` y `/config` son de `root`, modo `755`. Con `--cap-drop ALL --cap-add NET_BIND_SERVICE --security-opt no-new-privileges:true`: escribe en los dos volúmenes y responde `308` con `Location: https://apbuildings.duckdns.org/` y cuerpo vacío** | **Sí:** se retira `user: "1000:1000"` y se adopta la alternativa con capacidades retiradas |
| E-L6 | En Windows PowerShell 5.1, `curl` es un alias de `Invoke-WebRequest` | No |
| E-L7 | `ssh` es el de Git en este equipo; `-G` imprime `exitonforwardfailure yes` pero no `localforward` | Sí: V5 prueba el túnel de verdad |
| E-L8 | Con `CIMENTA_DB_PUERTO=1` ya en el entorno y `55433` en el archivo, `uv run --env-file` imprime `1`: **el entorno gana sobre el archivo** | No: confirma que la comprobación previa del entorno vacío es obligatoria |
| E-L9 | Sobre una base sin migrar, `PGOPTIONS='-c role=cimenta_aplicacion'` falla con `FATAL: role "cimenta_aplicacion" does not exist`. Sobre la base migrada y con contraseñas, `alembic upgrade head` aborta con `RuntimeError: Las migraciones de CIMENTA las ejecuta solo cimenta_migracion, y esta conexión es cimenta_aplicacion…` y `alembic current` sigue en `0008 (head)` | No: confirma el reordenamiento ya hecho |
| E-L10 | La consulta de permisos, escrita como un `SELECT … UNION ALL …` con las mismas expresiones del diseño, da todo `True` y código `0` tras migrar y fijar contraseñas, con los tres nombres de disparador existentes. Con `GRANT UPDATE ON bitacora TO cimenta_aplicacion` una fila pasa a `False` y el código es `1`; tras el `REVOKE` vuelve a `0` | No |
| E-L11 | La contraseña de `cimenta_lectura` con el rol `cimenta_aplicacion` da `password authentication failed`; el control positivo abre sesión; el puerto cerrado da `connection timeout expired` | Sí: la guía nombra timeout y refused como resultados inválidos |
| E-L12 | `docker ps --format "{{.Names}}\t{{.Ports}}"` imprime `127.0.0.1:55433->5432/tcp` y `0.0.0.0:55435->5432/tcp`, sin entrada `[::]` en Docker Desktop | Sí: A5 usa las dos formas |
| E-L13 | `herramientas.semilla_local` por el bucle local termina con `Falta la variable de entorno CIMENTA_SEMILLA_CONTRASENA…`, sin conectar | No |
| E-L14 | `docker pull caddy:2.11.7` descarga la etiqueta | No |
| E-L15 | Con `internal: true`, `docker ps` muestra `5432/tcp` sin publicar: la red interna no publica puertos | No |

`E-L5` no se ejecutó porque el Compose de Caddy aún no existe, y E-V1 a E-V6 son de la VPS.

## Plan de pruebas

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `anfitrion` en la VPS con los dos entornos arriba sale con `0`: ninguna publicación de 5432/tcp fuera de `127.0.0.1`, ninguna escucha en 5432, 5433 o 5434 fuera del bucle local | feliz | `CA-1`, `CA-2` | Ninguno: ticket de Fundación |
| TC-02 | Con la sonda en `0.0.0.0:5435`, `anfitrion` sale con `1` y nombra `0.0.0.0:5435->5432/tcp en cimenta-sonda-expuesta` y la escucha `0.0.0.0:5435`; sin la sonda vuelve a `0` | **rechazo** | `CA-S3`, `CA-2` | — |
| TC-03 | `remoto` desde el equipo: los puertos 5432, 5433 y 5434 de la IP pública no conectan; `Test-NetConnection` da `False` en los tres | **rechazo** | `CA-1`, `CA-2` | — |
| TC-04 | `remoto` comprueba que el certificado de cada nombre valida con el contexto por omisión de Python, lo emitió `Let's Encrypt` y no está caducado; `curl.exe -I https://<nombre>` responde `200` | feliz | `CA-3` | — |
| TC-05 | `remoto` comprueba en cada nombre: `GET http://<nombre>/` → `308`, `Location: https://<nombre>/`, cuerpo sin `CIMENTA`. TC-05a es lo mismo en local contra Caddy con las capacidades retiradas (E-L4) | **rechazo** | `CA-4` | — |
| TC-06 | `comprobar_permisos.sql` por el túnel en cada base: 22 `True` y código `0`; `alembic current` → `0008 (head)` en las dos. TC-06a, el ensayo en la sonda (E-L10) | feliz | `CA-5`, `CA-7` | — |
| TC-07 | Control positivo con el archivo propio; luego seis conexiones cruzadas (los tres roles, en los dos sentidos) terminan en `password authentication failed` y ninguna abre sesión. TC-07a, el ensayo en la sonda (E-L11) | **rechazo** | `CA-6` | — |
| TC-08 | Con la base ya migrada y `PGOPTIONS='-c role=cimenta_aplicacion'`, `alembic upgrade head` aborta con el mensaje de `env.py` que nombra `cimenta_aplicacion`, y `alembic current` sigue en `0008 (head)`. Sobre una base sin migrar no vale: falla antes con `role "cimenta_aplicacion" does not exist`. TC-08a, en la sonda (E-L9) | **rechazo** | `CA-8` | — |
| TC-09 | Sin `CIMENTA_DB_CONTRASENA_MIGRACION`, `docker compose up -d db` aborta con el mensaje que nombra la variable y no crea el contenedor (E-L1) | **rechazo** | `CA-10` | — |
| TC-10 | `.env` de la VPS con `600`; `git check-ignore` marca `.env.prod` y `.env.test`; `git ls-files` solo lista `.env.example`; ningún valor de los dos archivos aparece con `git grep -q -F` | **rechazo** | `CA-9` | — |
| TC-11 | `semilla_local` con `.env.test` termina sin conectar porque falta `CIMENTA_SEMILLA_CONTRASENA`; `usuario_sin_filas` sigue `True`. TC-11a, en la sonda (E-L13) | **rechazo** | `CA-9`, `CA-7`, supuesto 4 | — |
| TC-12 | `verificar_docs.py` sin problemas con `adrs 34`; la suite de `tools/tests`, que es la que compara los recuentos de ADR con `docs/adr/`, en verde; `extraer_mermaid.py`, `markdownlint-cli2` y `Vale` sin hallazgos; `lychee` en verde en el pipeline. El ADR dice las tres cosas de `CA-11` | **rechazo** (los verificadores fallan ante cualquier rotura) | `CA-11`, `CA-12` | — |
| TC-13 | La persona dueña ejecuta V1…V8 siguiendo solo la guía; cada desviación se corrige en A7 | feliz | `CA-13` | — |
| TC-S1 | `docker compose ls` lista dos proyectos de base y Caddy; bajar `test` sin `-v` deja `cimenta-prod-db-1` en marcha y `cimenta-prod_pg_datos` y `cimenta-prod_default` intactos | **rechazo** (un entorno no arrastra al otro) | `CA-S1` | — |
| TC-S2 | TC-S2a: `805306368` en `HostConfig.Memory` (E-L2). TC-S2b: `docker stats --no-stream` de los dos PostgreSQL suma menos de 2 GiB | feliz | `CA-S2` | — |
| TC-S4 | Tras `sudo reboot`, los tres contenedores están en marcha sin intervención y `remoto` sale con `0` | feliz | `CA-S4` | — |
| TC-S5 | Tras `down` y `up -d` de Caddy, ninguna línea `certificate obtained successfully` en el contenedor nuevo, y `remoto` sale con `0` | feliz | `CA-S5` | — |
| TC-INV-1 | Las filas de invariantes 10, 14, 20 y 21 de `comprobar_permisos.sql` en `True` en `prod` y en `test`. TC-INV-1a: en la sonda, el `GRANT UPDATE ON bitacora` de E-L10 pone en `False` su fila y el código en `1` | regresión de invariante | `CA-R1` | — |

**Pruebas del script** (`tools/tests/test_verificar_despliegue.py`, `unittest`, sin red ni procesos: `main` recibe sus dependencias por parámetro). Nombres con el prefijo `test_tkt070_`.

| # | Caso | Tipo |
|---|---|---|
| TC-U1 | `exposiciones_docker` con dos contenedores publicados en `127.0.0.1` devuelve una lista vacía | feliz |
| TC-U2 | `exposiciones_docker` con `0.0.0.0:55435->5432/tcp, [::]:55435->5432/tcp` devuelve dos `Exposicion` con `puerto_anfitrion == 55435` y el nombre del contenedor | **rechazo** |
| TC-U3 | `exposiciones_docker` ignora `0.0.0.0:80->80/tcp` de Caddy y las entradas sin `->` | **rechazo** de falso positivo |
| TC-U4 | `escuchas_expuestas` marca `0.0.0.0:5435`, `*:5435` y `[::]:5435`, y no marca `127.0.0.1:5433` ni `0.0.0.0:22`; salta la cabecera `State` | **rechazo** |
| TC-U5 | `evaluar_redireccion` con `308`, `https://<nombre>/` y cuerpo vacío devuelve vacío | feliz |
| TC-U6 | `evaluar_redireccion` con `200` y cuerpo `CIMENTA entorno prod…` devuelve fallos que nombran el estado y el contenido | **rechazo** |
| TC-U7 | `evaluar_redireccion` falla con `302`, con `Location` `http://…` y con `Location` de otro nombre | **rechazo** |
| TC-U8 | `evaluar_sondeo` con `conecto=True` devuelve un texto con `<ip>:<puerto>`; con `False`, `None` | **rechazo** |
| TC-U9 | `evaluar_certificado` acepta emisor `Let's Encrypt` vigente, y falla con `(STAGING) Let's Encrypt` y con un `notAfter` anterior a `ahora` | **rechazo** |
| TC-U10 | `main(["anfitrion"])` con un `ejecutar` que devuelve una exposición sale con `1` y la imprime; con salidas limpias, `0` | **rechazo** |
| TC-U11 | `main(["remoto", "--ip", "192.0.2.1"])` con dependencias en verde sale con `0`; si `sondear` conecta en 5433, `1` y nombra `192.0.2.1:5433` | **rechazo** |
| TC-U12 | `main(["anfitrion"])` con un `ejecutar` que lanza `FileNotFoundError` sale con `2`; una suborden desconocida, también `2` | **rechazo** (fallo cerrado) |

**Mutación** (fila A5, ruta crítica de la exposición). Cada mutante se aplica, se ejecuta la suite y se deshace; `impl.md` anota qué cayó.

| Mutante | Test que debe ponerse rojo |
|---|---|
| M1 · `exposiciones_docker` compara la dirección con `"0.0.0.0"` en lugar de excluir `"127.0.0.1"` (deja pasar `[::]`) | TC-U2 |
| M2 · `evaluar_redireccion` acepta `{301, 302, 307, 308}` | TC-U7 |
| M3 · `escuchas_expuestas` trata `*` como bucle local | TC-U4 |

No hay concurrencia ni bloqueo pesimista en este ticket: no aplica el caso de dos transacciones.

## Impacto

Resultado de la revisión de impacto del arquitecto; `revisor-impacto` la confirma en el gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `compose.yaml` raíz, sin cambios, pasa a tener un segundo consumidor | La VPS de prueba; el desarrollo local; testcontainers (`conftest.py:130`) | Un cambio futuro del archivo cambia la VPS sin que nadie lo note. TKT-059 añadirá el servicio `minio` | Toda orden de la guía nombra el servicio (`up -d db`). El ADR lo pone en «Cuándo revisar» |
| `lychee.toml` | Los trabajos `documentacion` de `ci.yml` y `enlaces` de `enlaces.yml` | Una exclusión demasiado amplia ocultaría un enlace roto legítimo | El patrón solo cubre `duckdns.org`, que el proyecto no usa para nada más |
| `tools/` gana un script y una prueba | El trabajo `herramientas` (Python 3.14, guarda de `skipped=`) | Un test que dependa de Docker, de la red o de `ss` se saltaría o fallaría en el corredor | Todas las dependencias se inyectan; ningún test toca la red ni lanza procesos |
| `CLAUDE.md`, `README.md` y `llms.txt` | Todo agente y toda persona que llega | Recuento de ADR desfasado | Los tres pasan de 33 a 34 en el mismo cambio |
| `docs/02-arquitectura.md` §7.6 | Quien lea los roles de base de datos | Dice que el rol de migración es superusuario «solo en local y en pruebas» | Se añade la VPS de prueba con su `(asumido)` |
| La VPS | Nadie más: no hay aplicación ni datos reales | Un `ports:` mal escrito expondría una base | TC-02 prueba que el script lo detecta; la guía nombra la causa |

**Fronteras entre módulos:** No. Ningún archivo de `backend/` cambia.

## Documentación afectada

Qué se actualiza en **este mismo** cambio (filas A6 y A7).

| Documento | Qué cambia |
|---|---|
| `docs/despliegue-prueba-vps.md` (nuevo) | La guía de operación. Secciones: §1 Qué es y qué no es (prueba, sin aplicación, sin respaldo, sin datos reales; enlace al ADR) · §2 Topología (la tabla de este diseño) · §3 Acceso y puertos (SSH por llave; 22, 80 y 443 y por qué cada uno; `ufw`; **por qué ninguna base se alcanza: ningún `ports:` de una base enlaza a `0.0.0.0`, porque Docker publica saltándose `ufw`**, con la salida de E-V3) · §4 Preparar el servidor (V1) · §5 Levantar las bases (V2; siempre `-p`, `-f` y `--env-file`; siempre `db` al final) · §6 Caddy (autoridad de pruebas primero, luego la real; límites de emisión de Let's Encrypt; el volumen guarda los certificados) · §7 Migrar por túnel desde Windows (los siete pasos; **prohibido apuntar el `.env` local al túnel**, porque `semilla_local` solo mira el host y aceptaría `127.0.0.1`; `semilla_local` nunca contra `prod`) · §8 Verificar (`anfitrion`, `remoto`, el bucle de `CA-6` con su control positivo, `Test-NetConnection`) · §9 Operación (actualizar el servidor con `apt` y `/var/run/reboot-required`; cambiar una versión de imagen solo desde el repositorio; reiniciar; **rotar contraseñas**: las de aplicación y lectura, regenerando la línea en la VPS, copiándola y ejecutando `contrasenas_roles`; la de migración, con `\password cimenta_migracion` dentro de `docker exec -it … psql` y actualizando las dos copias, porque `POSTGRES_PASSWORD` solo se lee al iniciar el volumen; **recrear un entorno desde cero** con `down -v`, con el aviso de que borra la base; apagar al terminar el mes) · §10 Trampas conocidas (`curl` es alias en PowerShell 5.1: usar `curl.exe`; `>` escribe UTF-16 y `Set-Content -Encoding utf8` añade BOM: por eso el `.env` se genera en la VPS; comillas dobles en `python -c`; variables ya definidas en el entorno; `docker compose config` y `docker inspect` imprimen secretos). Las URL van en bloques de código, nunca como enlace |
| `docs/adr/20261102-destino-de-prueba-en-vps.md` (nuevo, ADR-034) | Ver «¿Merece ADR?» |
| `docs/adr/README.md` | Fila: `2026-11-02` · el título del ADR («El destino de prueba es una VPS con un Compose por entorno, un Caddy único y la migración por túnel SSH») enlazado al archivo `20261102-destino-de-prueba-en-vps.md` con la misma forma que las demás filas · `Aceptado · temporal` · `Despliegue, base de datos, operación · TKT-070` |
| `CLAUDE.md:14`, `README.md:30`, `llms.txt:27` | `33` pasa a `34`. **No es cosmético:** `tools/tests/test_definicion_revision.py` compara esos tres recuentos con el número de archivos de `docs/adr/` y falla si no coinciden |
| `README.md:263` | La tabla de cifras dice `Decisiones de arquitectura (ADR) \| 33`. Pasa a `34`. Ninguna prueba la comprueba: se edita a mano |
| `.editorconfig` | Una sección `[Caddyfile]` con `indent_style = tab`, porque el archivo se deja como lo formatea `caddy fmt` y un editor con EditorConfig lo reindentaría con espacios |
| `.claude/skills/conv-docker/SKILL.md` | Una nota en la tabla de «Producción»: el banco de pruebas de TKT-070 sí corre PostgreSQL en contenedor, con `restart` y `mem_limit`, y es temporal; y su Caddy corre como `root` dentro del contenedor, con las capacidades retiradas, porque no puede escribir en su volumen con otro usuario. Aprobada por la persona dueña en el gate |
| `README.md` (tabla de documentos, junto a la fila de `:35`) y `llms.txt` (junto a `:25`) | Una fila y una línea: «Despliegue de prueba en VPS — la guía de operación de TKT-070» |
| `docs/convenciones.md` §3 | En el árbol: `├── despliegue/  Compose de ajustes de la VPS de prueba, Caddy y su consulta de permisos (TKT-070)` y, bajo `docs/`, `├── despliegue-prueba-vps.md  Guía de operación de la VPS de prueba` |
| `docs/02-arquitectura.md:393` | «El rol de migración es superusuario solo en local y en pruebas» pasa a «…solo en local, en pruebas y en la VPS de prueba de TKT-070 `(asumido)`», con un enlace al ADR del destino de prueba, hacia `adr/20261102-destino-de-prueba-en-vps.md` |
| `docs/06-stack-tecnologico.md` §10, «Despliegue» (`:515`) | Una frase al final del párrafo: TKT-070 levanta un banco de pruebas en una VPS que no es candidata por omisión, enlazando el ADR |
| `docs/05-tickets-trabajo.md`, ficha de TKT-070 (`:1533`) | «La ubicación exacta la fija `/sdd-disenar`» pasa a nombrar `despliegue/`, `tools/verificar_despliegue.py` y `docs/despliegue-prueba-vps.md` |
| `tools/README.md` | Sección `## verificar_despliegue.py`: uso de las dos subórdenes, códigos `0`, `1` y `2`, que corre con Python 3.12 o posterior, y cómo se prueba sin red. Se nombra que no es un verificador de documentación, igual que `severidad_pip_audit.py` |
| `lychee.toml` | La exclusión de `duckdns\.org` |

## ¿Merece ADR?

**Sí.** Alguien que llegue verá una base de datos en un contenedor sobre el volumen de una VPS, que el [stack §10](../../../docs/06-stack-tecnologico.md#despliegue) descarta expresamente, y una migración lanzada desde un portátil. Las dos preguntas tienen respuesta, y hubo opciones descartadas.

- **Archivo:** `docs/adr/20261102-destino-de-prueba-en-vps.md` · ADR-034 · formato MADR de [`docs/adr/template.md`](../../../docs/adr/template.md).
- **Título:** «El destino de prueba es una VPS con un Compose por entorno, un Caddy único y la migración por túnel SSH».
- **Estado:** `Aceptado · temporal`, como ADR-017.
- **Contexto y problema:** no hay destino hasta TKT-058; la pieza delicada —PostgreSQL con tres roles, disparadores y revocaciones, detrás de un proxy con HTTPS— no se ha probado fuera del equipo de desarrollo; la VPS de un mes a 4.07 USD con sus características; no hay imagen del backend (regla 17).
- **Opciones consideradas** (a confirmar por la persona dueña en el gate: el ADR transcribe, no inventa):
  1. VPS de bajo costo, el `compose.yaml` raíz reutilizado por entorno con `-p`, un Caddy único y la migración desde el equipo por túnel SSH.
  2. Esperar a TKT-058 y probar directamente en el destino final con base gestionada: descartada porque `PA-12` fija el precio de esa base y sigue sin respuesta.
  3. Migrar dentro de la VPS, instalando `uv` y el backend en el servidor o con una imagen: descartada porque la imagen es de TKT-058 y un backend instalado en el anfitrión sería un segundo camino de despliegue.
  4. Publicar PostgreSQL con una lista de IP permitidas para migrar sin túnel: descartada porque Docker publica saltándose `ufw` y la base quedaría a una regla de distancia de Internet.
- **Decisión:** la opción 1, con las razones de la escalera de este diseño (una sola fuente de la imagen, aislamiento por proyecto, un solo dueño de 80 y 443, ningún puerto de base fuera del bucle local).
- **Consecuencias negativas o costes aceptados**, las tres de `CA-11` dichas literalmente: **no hay recuperación a un punto en el tiempo y el respaldo del proveedor es cada cuatro semanas**; **esto incumple `RNF-10` y `RNF-11`, y el [stack §10](../../../docs/06-stack-tecnologico.md#despliegue) descarta un contenedor de PostgreSQL sobre un volumen de VPS sin más**; **la decisión del destino final sigue siendo de TKT-058**. Además: el rol de migración es superusuario en la VPS `(asumido)`; el túnel esquiva la guarda de host de `semilla_local`, y lo único que lo impide es no ejecutarla, más la ausencia de su variable en `.env.prod` y `.env.test`; `prod` no recibe datos reales, y la fila de «Constructora Celsius» de la migración 0008 no cuenta como tal `(asumido)`; `PA-T5` de TKT-057 queda en TKT-058; sin cabeceras de seguridad en Caddy. Caddy corre como `root` dentro de su contenedor, con todas las capacidades retiradas salvo `NET_BIND_SERVICE` y sin nuevos privilegios, porque con el usuario 1000 no puede escribir en el volumen `/data` (E-L4, ejecutado); es una excepción a conv-docker §5. `caddy:2.11.7` queda fijado a mano, sin actualización automática de Dependabot.
- **Cuándo revisar:** si la VPS no se renueva (el ADR queda como histórico); cuando TKT-058 decida el destino final; antes de poner cualquier aplicación detrás de Caddy (`PA-T5` de TKT-057 y las cabeceras); si el `compose.yaml` raíz gana un servicio o cambia de versión mayor de PostgreSQL.

## Pasada adversarial

Hecha por el arquitecto sobre este diseño, con la postura de `abogado-del-diablo`.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-6` pasa en verde con el túnel caído: un `connection refused` también es «PostgreSQL no abrió sesión» | TC-07 exige el texto `password authentication failed` y un control positivo previo con el archivo propio; E-L11 ensaya en local el caso del puerto cerrado para que la guía lo nombre como resultado inválido |
| 2 | Alta | `docker compose config` y `docker inspect` sin formato imprimen `POSTGRES_PASSWORD`, y pegar su salida en `impl.md` versionaría un secreto | Regla de evidencia en el orden de implementación; `--no-interpolate` y `--format` en todos los experimentos; la guía §10 lo advierte |
| 3 | Alta | `CA-8` dice «con las credenciales de `cimenta_aplicacion`», pero `url_migracion()` fija el usuario a la constante `cimenta_migracion`: ninguna variable permite conectar como otro usuario, y una contraseña ajena falla en la autenticación, antes de la guarda | El diseño llega a la guarda con `PGOPTIONS='-c role=cimenta_aplicacion'`, que cambia `current_user`. E-L9 lo prueba en local antes de la VPS y, si no funciona, se escala. Se pide al gate ajustar la redacción de `CA-8` |
| 4 | Alta | `CA-7` escribe literalmente `uv run --env-file ../.env alembic upgrade head`, que contradice `CA-9` y la decisión registrada de no apuntar el `.env` local al túnel | El diseño usa `../.env.prod` y `../.env.test`. Se pide al gate corregir el texto de `CA-7` |
| 5 | Media | Si una variable `CIMENTA_*` ya está en la sesión de PowerShell, `uv run --env-file` puede respetarla y migrar la base equivocada (la documentación de Compose dice que en Compose el entorno del sistema siempre gana) | Comprobación previa obligatoria del entorno vacío; E-L8 registra el comportamiento real de `uv`; bases con nombre distinto por entorno para que el error sea ruidoso |
| 6 | Media | Olvidar `-p` mete los contenedores en el proyecto `cimenta` del archivo raíz | Toda orden de la guía lleva `-p`; V2 comprueba que `docker compose ls` no lista `cimenta`. Un entorno con el archivo del otro choca en el puerto y en el nombre de la base en lugar de escribir en silencio |
| 7 | Media | Ajustar el Caddyfile contra la autoridad real puede agotar los límites de emisión | Autoridad de pruebas primero (E-V6); volumen de certificados (TC-S5); la autoridad se cambia por variable, sin editar el archivo |
| 8 | Media | La siembra por el túnel solo la impide la disciplina | Segunda guarda sin código: la variable de siembra no está en `.env.prod` ni en `.env.test` (E-L13, TC-11). El paso 7 nunca contra `prod` |
| 9 | Media | Archivos con CRLF o BOM rompen el `.env` o el Caddyfile en Linux. `.gitattributes` (`* text=auto eol=lf`) solo actúa sobre lo que Git guarda y extrae, y `scp` copia el árbol de trabajo de Windows, no blobs de Git | Antes de cada `scp`, la fila V1 comprueba que ninguno de los cinco archivos lleva `\r` (`grep -c $'\r'` en la VPS tras copiar, y `Select-String "\r"` en el equipo antes); el `.env` nace en la VPS y viaja con `scp`, que copia bytes |
| 11 | Media | `caddy:2.11.7` queda fijado a mano: `dependabot.yml` no cubre el ecosistema `docker` y sus pruebas lo rechazan | El ADR lo declara en «Cuándo revisar». La VPS dura un mes |
| 12 | Alta | El rojo de `CA-8` «antes de migrar» no da lo que dice: en una base sin migrar el rol `cimenta_aplicacion` no existe y la conexión falla antes de la guarda | Se reordenó la secuencia: el rojo va después de migrar y fijar contraseñas, y E-L9 y TC-08 lo reflejan |
| 10 | Baja | Un script de verificación que solo corre en Linux no sirve en Windows | Las dos subórdenes se separan por dónde corren; `anfitrion` en Windows sale con `2`, que no es verde |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| E-L9 muestra que `PGOPTIONS` no llega a la guarda | Baja | `CA-8` no se puede ejecutar como está escrito | Se escala con `/sdd-escalar` antes de tocar la VPS; ninguna fila `V` depende de que pase |
| La VPS no se renueva antes de cerrar el ticket | Media | Las filas `V` quedan a medias | Las filas `A` van primero y completas; V1…V8 caben en una sesión. Si se apaga, el ADR queda como histórico (supuesto 1) |
| La IPv4 compartida no reenvía el puerto 80 como dijo el proveedor | Baja | No hay HTTP-01 ni redirección | Con la autoridad de pruebas se ve en minutos y sin gastar emisiones reales; Caddy intenta además TLS-ALPN por el 443 |
| Un `alembic upgrade head` lanzado contra el túnel equivocado | Baja | Migraría la otra base | Nombres de base distintos: la conexión falla con «la base no existe» |
| Un cambio futuro del `compose.yaml` raíz llega a la VPS sin revisión | Media | La VPS se desvía de lo probado | Servicio nombrado en cada orden; «Cuándo revisar» del ADR |
| Caddy corre como `root` en su contenedor | Cierta | Se incumple la letra de conv-docker §5 | Capacidades retiradas, sin nuevos privilegios, y declarado en el ADR y en la nota de conv-docker. Se ensayó en local |
| La guía tiene un paso que solo entiende quien la escribió | Media | `CA-13` falla | La sigue la persona dueña en V1…V8 y A7 corrige cada desviación |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| G1 | ¿Se corrige el texto de `CA-7` para que diga `--env-file ../.env.prod` y `--env-file ../.env.test` en lugar de `../.env`? | Sí: hoy contradice `CA-9` y la decisión registrada |
| G2 | ¿Se corrige el texto de `CA-8` a «con una conexión cuyo `current_user` es `cimenta_aplicacion`», que es lo único que llega a la guarda sin cambiar código? | Sí, condicionado a E-L9 |
| G3 | ¿Las opciones 2, 3 y 4 del ADR son las que se consideraron? | Confirmar o corregir la lista: el ADR transcribe |
| G4 | ¿Se aprueba editar el recuento de `CLAUDE.md`, `README.md` y `llms.txt` de 33 a 34? | Sí, como se hizo con ADR-033 en TKT-013 |
| G5 | El ticket suma unas 790 líneas, la mitad documentación. ¿Se mantiene entero o se recorta `CA-S3` (el script, un Should) a un ticket propio con `/sdd-escalar`, ahorrando unas 320? | Mantenerlo: el script es la única prueba repetible de que una base expuesta se detecta, y la parte de la VPS no suma líneas |
