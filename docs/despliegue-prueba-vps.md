# Despliegue de prueba en VPS (TKT-070)

Guía de operación para la VPS Linux de Database Mart con dos entornos PostgreSQL (`prod` y `test`) y un Caddy único con HTTPS. **No hay aplicación todavía** (TKT-058). Los nombres son `apbuildings.duckdns.org` (`prod`) y `apbuildings-test.duckdns.org` (`test`). Detalle de la decisión: [ADR-034](adr/20261102-destino-de-prueba-en-vps.md).

## 1 · Qué es y qué no es

* **Es** un banco de pruebas: certificados, aislamiento de bases, esquema con tres roles por túnel SSH.
* **No es** producción para el cliente: sin recuperación a un punto en el tiempo (`RNF-10`, `RNF-11`); respaldo del proveedor cada cuatro semanas.
* **No despliega** backend ni frontend; no monta MinIO (TKT-059).
* **`prod`** es el nombre del entorno en la VPS, no la rama `Produccion` de Git.

## 2 · Topología

| | `prod` | `test` | Caddy |
|---|---|---|---|
| Proyecto Compose | `cimenta-prod` (`-p`) | `cimenta-test` (`-p`) | `cimenta-caddy` (`name:`) |
| Archivos | `compose.yaml` + `despliegue/compose.vps.yaml` | igual | `despliegue/caddy/compose.yaml` |
| Contenedor | `cimenta-prod-db-1` | `cimenta-test-db-1` | `cimenta-caddy-caddy-1` |
| Base | `cimenta_prod` | `cimenta_test` | — |
| Publicación | `127.0.0.1:5433→5432` | `127.0.0.1:5434→5432` | `0.0.0.0:80`, `0.0.0.0:443` (dentro de la VM) |
| Puertos públicos (IPv4 compartida) | — | — | **10004→80**, **10005→443** (Database Mart) |
| `.env` en VPS | `/srv/cimenta/prod/.env` | `/srv/cimenta/test/.env` | `/srv/cimenta/despliegue/caddy/.env` (`DUCKDNS_API_TOKEN`) |
| Copia en equipo | `.env.prod` | `.env.test` | — |

En la VPS, el árbol bajo `/srv/cimenta/` replica las rutas del repositorio (`compose.yaml`, `despliegue/`, `tools/`). No existe `/srv/cimenta/.env` en la raíz.

## 3 · Acceso y puertos

* **SSH** por llave. En Database Mart el reenvío público es **10003→22** (no uses el puerto 22 de la IP en el cliente).
* **HTTP/HTTPS hacia Caddy:** el proveedor publica **10004→80** y **10005→443** hacia la VM. Los puertos **80 y 443 estándar** de la IP pública **no** llegan a Caddy; las comprobaciones externas usan **`:10004`** y **`:10005`**.
* **Certificados:** Let's Encrypt con **DNS-01** (plugin DuckDNS en Caddy). No depende de que el puerto 80 público estándar responda.
* **5433 y 5434** solo en `127.0.0.1` de la VPS para el túnel de migración.
* **Por qué Internet no alcanza PostgreSQL:** ningún `ports:` de una base enlaza a `0.0.0.0`, porque Docker publica en la cadena `DOCKER` de `iptables`/`nftables` **saltándose `ufw`**. Compruébalo con la sonda de la §8 (`docker run … -p 0.0.0.0:5435:5432` → `ss -tln` muestra `0.0.0.0:5435` aunque `ufw` no lo liste) y con `sudo python3 tools/verificar_despliegue.py anfitrion`.

## 4 · Preparar el servidor (V1)

Desde el equipo, con la rama del ticket copiada por `scp` (no hace falta `git clone` en la VPS):

1. Comprobar Docker: `docker version --format '{{.Server.Version}}'` (29.x), `docker compose version`, `systemctl is-enabled docker` → `enabled`.
2. Comprobar firewall: `sudo ufw status verbose` → solo 22, 80, 443 en `ALLOW IN`.
3. Comprobar Python: `python3 --version` → 3.12.x.
4. En la VPS:

   ```bash
   sudo mkdir -p /srv/cimenta/{despliegue/caddy,tools,prod,test}
   sudo chown "$USER:$USER" /srv/cimenta
   chmod 700 /srv/cimenta/prod /srv/cimenta/test
   ```

5. Copiar desde la raíz del repositorio (ajusta usuario e IP):

   ```bash
   scp -P 10003 compose.yaml <usuario>@<IP_VPS>:/srv/cimenta/
   scp -P 10003 despliegue/compose.vps.yaml despliegue/comprobar_permisos.sql \
       <usuario>@<IP_VPS>:/srv/cimenta/despliegue/
   scp -P 10003 despliegue/caddy/Dockerfile despliegue/caddy/compose.yaml despliegue/caddy/Caddyfile \
       despliegue/caddy/.env.example despliegue/caddy/.dockerignore \
       <usuario>@<IP_VPS>:/srv/cimenta/despliegue/caddy/
   scp -P 10003 tools/verificar_despliegue.py \
       <usuario>@<IP_VPS>:/srv/cimenta/tools/
   ```

6. Tras copiar, en la VPS: `grep -c $'\r' /srv/cimenta/despliegue/caddy/Caddyfile` debe dar **0** (sin CRLF).
7. Generar `.env` **en la VPS** (nunca con `>` de PowerShell en el equipo):

   ```bash
   umask 077
   cd /srv/cimenta/prod
   cat > .env <<'EOF'
   CIMENTA_DB_HOST=127.0.0.1
   CIMENTA_DB_NOMBRE=cimenta_prod
   CIMENTA_DB_PUERTO=5433
   CIMENTA_DB_CONTRASENA_MIGRACION=REEMPLAZAR
   CIMENTA_DB_CONTRASENA_APLICACION=REEMPLAZAR
   CIMENTA_DB_CONTRASENA_LECTURA=REEMPLAZAR
   EOF
   sed -i "s/^CIMENTA_DB_CONTRASENA_MIGRACION=.*/CIMENTA_DB_CONTRASENA_MIGRACION=$(openssl rand -hex 24)/" .env
   sed -i "s/^CIMENTA_DB_CONTRASENA_APLICACION=.*/CIMENTA_DB_CONTRASENA_APLICACION=$(openssl rand -hex 24)/" .env
   sed -i "s/^CIMENTA_DB_CONTRASENA_LECTURA=.*/CIMENTA_DB_CONTRASENA_LECTURA=$(openssl rand -hex 24)/" .env
   test "$(grep CONTRASENA .env | cut -d= -f2 | sort -u | wc -l)" -eq 3
   chmod 600 .env
   ```

   Repetir en `/srv/cimenta/test/` con `CIMENTA_DB_NOMBRE=cimenta_test`, `CIMENTA_DB_PUERTO=5434` y **otras** tres contraseñas.

8. Token DuckDNS para Caddy (misma cuenta que los subdominios), en la VPS:

   ```bash
   umask 077
   cd /srv/cimenta/despliegue/caddy
   cp .env.example .env
   # Editar .env: pegar el token de https://www.duckdns.org (una sola línea DUCKDNS_API_TOKEN=...)
   chmod 600 .env
   ```

9. Copiar al equipo: `scp -P 10003 <usuario>@<IP_VPS>:/srv/cimenta/prod/.env .env.prod` (y `.env.test`). Comprobar: `git check-ignore -v .env.prod .env.test`.

**Prohibido** apuntar el `.env` local de desarrollo al túnel: `semilla_local` solo mira el host y aceptaría `127.0.0.1`.

## 5 · Levantar las bases (V2)

Desde `/srv/cimenta`:

```bash
docker compose -p cimenta-prod -f compose.yaml -f despliegue/compose.vps.yaml \
  --env-file /srv/cimenta/prod/.env up -d --wait db
docker compose -p cimenta-test -f compose.yaml -f despliegue/compose.vps.yaml \
  --env-file /srv/cimenta/test/.env up -d --wait db
```

Comprobaciones: `docker compose ls` lista `cimenta-prod` y `cimenta-test`, no `cimenta`. Bajar `test` sin `-v` no debe detener `cimenta-prod-db-1`.

## 6 · Caddy (V4)

La imagen incluye `github.com/caddy-dns/duckdns` (DNS-01). Construir una vez en la VPS:

```bash
cd /srv/cimenta/despliegue/caddy
docker compose -f compose.yaml build
```

Primero la **autoridad de pruebas** (límites de emisión):

```bash
cd /srv/cimenta
CIMENTA_ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory \
  docker compose -f despliegue/caddy/compose.yaml up -d --build
```

Comprobar logs (debe aparecer emisión por DNS, no HTTP-01 en puerto 80 público):

```bash
docker compose -f despliegue/caddy/compose.yaml logs --tail 40 caddy
```

Luego producción Let's Encrypt (sin `CIMENTA_ACME_CA`):

```bash
docker compose -f despliegue/caddy/compose.yaml up -d --force-recreate --build
```

Desde el PC (puertos publicados):

```powershell
curl.exe -sI http://apbuildings.duckdns.org:10004/ | findstr /I "HTTP Location"
curl.exe -sI https://apbuildings.duckdns.org:10005/ | findstr /I HTTP
```

Si `remoto` sigue viendo certificados de prueba: `docker compose -f despliegue/caddy/compose.yaml down`, `docker volume rm cimenta-caddy_caddy_datos cimenta-caddy_caddy_config`, y `up -d --build` de nuevo.

## 7 · Migrar por túnel desde Windows (V5)

En **PowerShell 5.1**, ventana nueva sin variables `CIMENTA_*` ni `PG*` (`Get-ChildItem Env: | Where-Object Name -Match '^(CIMENTA_|PG)'` vacío).

1. Túnel (otra ventana), ejemplo `test`:

   ```powershell
   ssh -4 -N -p 10003 -o ExitOnForwardFailure=yes -i $HOME\.ssh\cimenta_vps `
     -L 127.0.0.1:5434:127.0.0.1:5434 <usuario>@<IP_VPS>
   ```

   Para `prod`, puerto **5433**. Comprobar: `Test-NetConnection 127.0.0.1 -Port 5434`.

2. Desde `backend/`:

   ```powershell
   uv run --env-file ../.env.test alembic upgrade head
   uv run --env-file ../.env.test alembic current
   uv run --env-file ../.env.test python -m herramientas.contrasenas_roles
   ```

3. **Rechazo CA-8** (base ya migrada):

   ```powershell
   $env:PGOPTIONS = '-c role=cimenta_aplicacion'
   uv run --env-file ../.env.test alembic upgrade head
   Remove-Item Env:PGOPTIONS
   uv run --env-file ../.env.test alembic current
   ```

4. Permisos (`CA-5`, `CA-7`, `CA-R1`) — desde `backend/`, túnel abierto, entorno sin variables `CIMENTA_*` ni `PG*`:

   ```powershell
   uv run --env-file ../.env.test python -c "import os,sys,pathlib,psycopg; e=os.environ; c=psycopg.connect(host=e['CIMENTA_DB_HOST'], port=int(e['CIMENTA_DB_PUERTO']), dbname=e['CIMENTA_DB_NOMBRE'], user='cimenta_migracion', password=e['CIMENTA_DB_CONTRASENA_MIGRACION'], connect_timeout=5); f=c.execute(pathlib.Path('../despliegue/comprobar_permisos.sql').read_text(encoding='utf-8')).fetchall(); [print(*x, sep=' | ') for x in f]; sys.exit(0 if f and all(x[-1] for x in f) else 1)"
   ```

   Sustituye `.env.test` por `.env.prod` y el puerto del túnel al repetir en `prod`. Solo comillas simples en el `-c`.

5. **Solo en `test`:** `uv run --env-file ../.env.test python -m herramientas.semilla_local` debe fallar por falta de `CIMENTA_SEMILLA_CONTRASENA`. **Nunca** ejecutar siembra contra `prod`.

Repetir la secuencia para `prod` con `.env.prod` y puerto 5433 (sin paso de siembra).

## 8 · Verificar (V3, V6, V7)

**En la VPS:**

```bash
cd /srv/cimenta
sudo python3 tools/verificar_despliegue.py anfitrion
```

Sonda de exposición (debe poner el script en rojo):

```bash
docker run -d --rm --name cimenta-sonda-expuesta -p 0.0.0.0:5435:5432 alpine:3.22 sleep 600
sudo python3 tools/verificar_despliegue.py anfitrion
docker rm -f cimenta-sonda-expuesta
```

**Contraseñas cruzadas (CA-6)** — control positivo con el `.env` propio; luego seis intentos con contraseña del otro entorno. Resultado válido: `password authentication failed`. Inválidos: `connection refused`, `timeout`, cualquier cosa que no sea autenticación fallida.

**Desde el equipo (otra red):**

```powershell
python tools/verificar_despliegue.py remoto --http-port 10004 --https-port 10005
Test-NetConnection <IP_VPS> -Port 5432
Test-NetConnection <IP_VPS> -Port 5433
Test-NetConnection <IP_VPS> -Port 5434
```

Los tres `TcpTestSucceeded` deben ser **False**.

## 9 · Operación

* **Actualizar SO:** `sudo apt update && sudo apt upgrade`; si existe `/var/run/reboot-required`, reiniciar en ventana acordada.
* **Cambiar versión de imagen:** solo desde el repositorio y volver a copiar con `scp`.
* **Reinicio:** `sudo reboot`; tras volver, `docker ps` debe mostrar los tres contenedores y `remoto` debe salir con 0.
* **Rotar contraseñas de aplicación y lectura:** regenerar líneas en la VPS, copiar `.env` al equipo, `contrasenas_roles` por túnel.
* **Rotar contraseña de migración:** `\password cimenta_migracion` dentro de `docker exec -it cimenta-prod-db-1 psql …` y actualizar las dos copias del `.env` ( `POSTGRES_PASSWORD` solo se lee al crear el volumen).
* **Recrear un entorno:** `docker compose -p cimenta-test … down -v` **borra la base**. Volver a §5 y §7.
* **Fin del mes:** apagar contenedores; la VPS puede no renovarse (ADR temporal).

## 10 · Trampas conocidas

* En PowerShell 5.1, `curl` es alias de `Invoke-WebRequest`; usar **`curl.exe`** para HTTPS externo.
* `>` y `Set-Content -Encoding utf8` en PowerShell corrompen `.env`; generarlos en la VPS con `openssl`.
* Comillas dobles anidadas en `python -c` se pierden; usar el one-liner con comillas simples del diseño.
* Variables `CIMENTA_*` ya definidas en la sesión **pisan** `--env-file` (comprobar entorno vacío).
* `docker compose config` sin `--no-interpolate` e `docker inspect` sin `--format` **imprimen secretos** (incluido `DUCKDNS_API_TOKEN` en el contenedor de Caddy); no pegar su salida en tickets ni commits.
