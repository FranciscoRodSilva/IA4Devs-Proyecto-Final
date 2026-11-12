---
name: conv-docker
description: Convenciones de Docker en CIMENTA — Compose local con PostgreSQL y MinIO y la aplicación en el anfitrión, testcontainers para las pruebas, imagen única multietapa sin estado ni secretos para producción. Cárgala antes de escribir o auditar el `compose.yaml`, un Dockerfile, un workflow que construye la imagen, o cuando una suite de integración no arranca.
---

# Convenciones · Docker

Docker aparece en tres sitios del proyecto, y en cada uno con un papel distinto. Confundirlos es el error más caro: meter la aplicación en el Compose de desarrollo, o meter PostgreSQL en la imagen de producción.

| Dónde | Qué corre en contenedor | Qué **no** | Ticket |
|---|---|---|---|
| **Desarrollo local** | PostgreSQL y MinIO, cada uno con volumen persistente | El backend y el frontend: corren en el anfitrión con `uv` y Vite | `TKT-003` (PostgreSQL), `TKT-059` (MinIO) |
| **Pruebas** | PostgreSQL y MinIO **efímeros**, levantados por testcontainers en cada sesión | El Compose local: los tests no dependen de que esté arriba | `TKT-003`, `TKT-009`, `TKT-059` |
| **Producción** | **Una** imagen: el backend sirviendo los estáticos del frontend ya compilado | PostgreSQL (gestionado, con recuperación a un punto en el tiempo) y los archivos (bucket R2 versionado) | `TKT-058` |

**Excepción temporal (TKT-070):** el banco de pruebas en VPS sí corre PostgreSQL en contenedor, con `restart` y `mem_limit`, hasta que venza el mes contratado. Su Caddy corre como `root` dentro del contenedor, con todas las capacidades retiradas salvo `NET_BIND_SERVICE` y sin nuevos privilegios, porque con otro usuario no puede escribir en el volumen `/data` donde guarda certificados (E-L4).

La fuente de estas decisiones es el [stack §10](../../../docs/06-stack-tecnologico.md#10-infraestructura), [ADR-008](../../../docs/adr/20260918-despliegue-single-tenant.md) y [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md). Esta convención no añade ninguna decisión de arquitectura: las reúne. Lo que sí añade son **prácticas de higiene de contenedores** —versiones fijadas, puertos a `127.0.0.1`, usuario sin privilegios, `.dockerignore`— que ningún documento del proyecto escribe; van marcadas con ‡ y, si alguna choca con un ticket, manda el ticket.

## 1 · Requisito previo: el demonio responde

```bash
docker info
```

testcontainers necesita Docker en marcha. **Si `docker info` falla, la suite de integración no se puede ejecutar, y eso se reporta como bloqueo, no como verde.** Prohibido sustituir el contenedor por SQLite, por un doble del almacén o por el Compose local para «avanzar»: probaría otro sistema ([regla de `CLAUDE.md`](../../../CLAUDE.md#qué-no-hacer)).

En Windows, Docker Desktop tiene que estar iniciado y con el motor de Linux; el primer arranque de testcontainers descarga las imágenes y tarda.

## 2 · Compose local

Dos servicios, `db` y `minio`, y nada más, cada uno con **volumen con nombre** para que los datos sobrevivan a `docker compose down`:

- **PostgreSQL.** El usuario que crea la imagen es el **propietario**, el de migración. Los roles de aplicación y de solo lectura **no** se crean en un script de arranque del contenedor: los crea la migración inicial de Alembic, con `ALTER DEFAULT PRIVILEGES` (`TKT-003`, `RNF-09`). Un script de `docker-entrypoint-initdb.d` que los creara sacaría los permisos de la migración y dejaría producción sin ellos.
- **MinIO**, desde TKT-059, en `compose.almacen.yaml` y no en `compose.yaml`. El mismo API de S3 que R2, con otro `endpoint_url`. No es un doble ni una concesión. La imagen es `pgsty/minio`, un fork comunitario, porque `minio/minio` dejó de ser descargable.

```bash
docker compose up -d db           # PostgreSQL local
docker compose -f compose.yaml -f compose.almacen.yaml up -d minio   # MinIO local
uv run --env-file ../.env python -m herramientas.almacen_local       # desde backend/: crea el bucket
uv run --env-file ../.env alembic upgrade head   # desde backend/, el esquema siempre por migración
```

- ‡ La versión de cada imagen se **fija** con su etiqueta exacta. `latest` cambia bajo los pies y rompe la reproducibilidad del arranque que exige `TKT-001`.
- Credenciales por variables del `.env`, que **no** se versiona; el `.env.example` sí, pero sin contraseñas: las de los roles van vacías y cada persona las genera (`RNF-07`).
- ‡ Puertos publicados solo a `127.0.0.1`. Un PostgreSQL de desarrollo con contraseña trivial abierto a la red local es una base expuesta.

**Decidido en TKT-059.** El servicio se llama `minio`. Va en un segundo archivo, `compose.almacen.yaml`, sin perfil, y no en `compose.yaml`: Compose interpola el archivo entero antes de elegir servicios, y un servicio con perfil inactivo y `${…:?}` hace fallar `up -d db` en quien aún no define las variables del almacén (la VPS incluida). El bucket no lo crea un servicio de una sola ejecución ni la aplicación: lo crea `herramientas.almacen_local`, que se niega si falta una variable o si el host de `CIMENTA_ALMACEN_ORIGEN` no es `localhost` ni `127.0.0.1`. El CORS del navegador no se aplica por código: MinIO no implementa `put_bucket_cors`, así que se fija con `MINIO_API_CORS_ALLOW_ORIGIN`, que `compose.almacen.yaml` toma de `CIMENTA_SPA_ORIGEN`.

## 3 · testcontainers en las pruebas

- PostgreSQL de la **misma versión mayor** que la de producción. El esquema se construye con `alembic upgrade head` contra el contenedor y la suite se conecta con el **rol de aplicación** ([`conv-pruebas`](../conv-pruebas/SKILL.md)).
- MinIO en testcontainers cuando el ticket toca archivos: firma, caducidad, `Content-Type` reescrito y hash solo se verifican contra un almacén real.
- Un contenedor por sesión de pruebas, no por test. Cómo se aíslan los tests entre sí lo decide el diseño de `TKT-003`: las pruebas de concurrencia y de bitácora necesitan transacciones confirmadas de verdad, así que deshacer una transacción envolvente no sirve para todas.
- En el pipeline, el corredor de GitHub Actions trae Docker y la suite corre igual que en local: los mismos tests, con los mismos comandos.

## 4 · La imagen de producción

La escribe un agente y pasa por revisión como cualquier PR ([convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)). Es de `TKT-058`: **no se adelanta desde otro ticket.**

- **Multietapa.** Una etapa construye el frontend con Node; otra instala el backend con `uv` desde el archivo de bloqueo; la final copia solo lo necesario sobre una base mínima de Python. Ni Node ni herramientas de compilación en la imagen final.
- **Sin estado.** Ningún archivo subido, ningún volumen de datos junto al contenedor: si los archivos acabaran ahí, el artefacto deja de ser recreable y ADR-008 se rompe por la puerta de atrás.
- **Sin secretos.** Ni en capas, ni en `ARG`, ni en `ENV`, ni copiados con el contexto. ‡ `.dockerignore` excluye `.env`, `.git`, `node_modules` y la caché de `uv` (`RNF-07`).
- ‡ **Usuario sin privilegios** en la etapa final; nunca `root`.
- El servidor arranca con las rutas `def` sobre el grupo de hilos (ADR-013): ningún ajuste de la imagen convierte el servidor en asíncrono.
- **La aplicación no arranca** con el adaptador simulado de `analitica` y `entorno = produccion` ([ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md)); la imagen no lo esquiva con una variable por omisión.
- El pipeline construye la imagen en cada PR, y **la que se restaura en el ensayo de `RNF-11` es la misma que se despliega**. El ensayo lo ejecuta y cronometra una persona.

## 5 · Lo que esta convención prohíbe

- El backend o el frontend dentro del Compose de desarrollo.
- Crear roles o permisos de PostgreSQL fuera de una migración.
- PostgreSQL o MinIO dentro de la imagen de producción.
- Imágenes con `latest`, secretos horneados, o un proceso que corre como `root`.
- Dar por buena una suite de integración que no levantó sus contenedores.
