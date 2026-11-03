# El destino de prueba es una VPS con un Compose por entorno, un Caddy único y la migración por túnel SSH

## Estado

Aceptado · **temporal**: la VPS se contrató por un mes para comprobar el destino antes de TKT-058. Si no se renueva, este ADR queda como histórico.

## Contexto y problema

Hasta TKT-058 no hay imagen del backend ni destino de producción. La pieza más delicada del despliegue —PostgreSQL con tres roles, revocaciones y disparadores de inmutabilidad, detrás de un proxy con HTTPS— solo se había probado en el equipo de desarrollo. TKT-070 levanta un banco de pruebas en una VPS Linux de bajo costo (Ubuntu 24.04, Docker, 4 GB de RAM) con dos entornos aislados (`prod` y `test`) **sin la aplicación**, para validar certificados, aislamiento de bases y reproducción del esquema por túnel SSH.

## Opciones consideradas

* VPS de bajo costo: reutilizar el `compose.yaml` raíz por entorno con `-p`, un Caddy único y migración desde el equipo por túnel SSH.
* Esperar a TKT-058 y probar directamente en el destino final con base gestionada: descartada porque `PA-12` fija el precio de esa base y sigue sin respuesta.
* Migrar dentro de la VPS instalando `uv` y el backend en el servidor: descartada porque la imagen es de TKT-058 y un segundo camino de despliegue diverge del stack.
* Publicar PostgreSQL con lista de IP permitidas para migrar sin túnel: descartada porque Docker publica saltándose `ufw` y la base quedaría a una regla de distancia de Internet.

## Decisión

Se elige la **VPS con Compose por proyecto** (`cimenta-prod`, `cimenta-test`, `cimenta-caddy`), reutilizando el `compose.yaml` raíz y el ajuste `despliegue/compose.vps.yaml`, porque:

* Hay una sola fuente de la imagen `postgres:18.6` (local, testcontainers y VPS).
* Cada entorno tiene red y volumen propios; Caddy es un tercer proyecto que no comparte red con las bases.
* Ningún `ports:` de una base enlaza fuera de `127.0.0.1`; la migración entra por túnel SSH desde quien despliega.

## Consecuencias

**Positivas**

* Se comprueba Let's Encrypt (DNS-01 con DuckDNS en la IPv4 compartida de Database Mart), redirección HTTP→HTTPS en los puertos publicados **10004/10005**, y permisos del esquema real antes de invertir en la imagen de TKT-058.
* Los archivos viven en el repositorio (`despliegue/`, `tools/verificar_despliegue.py`, [`docs/despliegue-prueba-vps.md`](../despliegue-prueba-vps.md)).

**Negativas o costes aceptados**

* **No hay recuperación a un punto en el tiempo** y el respaldo del proveedor es **cada cuatro semanas**. Esto **incumple `RNF-10` y `RNF-11`**, y el [stack §10](../06-stack-tecnologico.md#despliegue) descarta un contenedor de PostgreSQL sobre un volumen de VPS sin más.
* **La decisión del destino final sigue siendo de TKT-058** (con `PA-12` respondida).
* El rol de migración es **superusuario** en la VPS `(asumido)`; la fila genérica «Constructora Celsius» de la migración 0008 no cuenta como dato real `(asumido)`.
* El túnel esquiva la guarda de host de `semilla_local`; lo impide no ejecutarla y la ausencia de `CIMENTA_SEMILLA_CONTRASENA` en `.env.prod` y `.env.test`.
* `prod` no recibe datos reales del cliente mientras no exista TKT-058.
* `PA-T5` de TKT-057 (origen del cliente detrás del proxy) queda en TKT-058; aquí no hay aplicación ni cabeceras de seguridad de Caddy más allá de TLS.
* Caddy corre como `root` dentro de su contenedor, con `cap_drop: ALL`, `NET_BIND_SERVICE` y `no-new-privileges`, porque con el usuario 1000 no puede escribir en el volumen `/data` (experimento E-L4). Es una excepción temporal a conv-docker §5.
* La imagen `cimenta-caddy:2.11.7-duckdns` se construye en la VPS con `xcaddy` y el módulo `caddy-dns/duckdns@v0.4.0`; Dependabot no cubre imágenes Docker ni el token DuckDNS en `despliegue/caddy/.env`.
* Los puertos **80/443 estándar** de la IP pública no llegan a la VM; el acceso externo usa **10004** y **10005** hasta que el proveedor cambie el reenvío (decisión 2026-11-03).

**Cuándo revisar esta decisión**

* Si la VPS no se renueva (este ADR pasa a histórico).
* Cuando TKT-058 decida el destino final.
* Antes de poner cualquier aplicación detrás de Caddy (`PA-T5` y cabeceras).
* Si el `compose.yaml` raíz gana un servicio o cambia de versión mayor de PostgreSQL.
