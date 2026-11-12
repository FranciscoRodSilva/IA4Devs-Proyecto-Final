# El almacén local vive en `compose.almacen.yaml`, con una imagen fijada por digest y el CORS por variable de entorno

## Estado

Aceptado

## Contexto y problema

[ADR-016](20261001-almacenamiento-de-objetos.md) fijó que los archivos viven en un almacén compatible con S3: R2 en producción y MinIO en local y en las pruebas. TKT-059 tiene que levantar ese MinIO junto al PostgreSQL de desarrollo, y la verificación previa de su diseño (`E-0`, `E-4` y `E-5` en `sdd/tickets/tkt-059/impl.md`) desmintió tres supuestos del diseño original.

El primero afecta a la forma del servicio. El diseño preveía un servicio `minio` en `compose.yaml` con un perfil `almacen`, para que no arrancara con `docker compose up -d db`. Pero Compose interpola el archivo entero antes de elegir servicios, y un perfil inactivo no evita que `${CIMENTA_ALMACEN_CLAVE_SECRETA:?}` falle. El resultado era que `docker compose up -d db` dejaba de funcionar para quien aún no tuviera las variables del almacén en su `.env`, la VPS de prueba incluida.

El segundo afecta a la imagen. `minio/minio` ya no se puede descargar: el 2026-11-11 Docker Hub la rechaza, `quay.io` exige autenticación y el repositorio de GitHub figura archivado. Sin una imagen descargable, ni el entorno local ni los testcontainers de las pruebas arrancan.

El tercero afecta al CORS. El diseño preveía aplicarlo con `put_bucket_cors` desde una herramienta, pero MinIO responde `501` a esa llamada. Sin configuración alguna, MinIO refleja cualquier origen, y el navegador necesita que solo reciba `Access-Control-Allow-Origin` el origen de la SPA.

## Opciones consideradas

**Dónde vive el servicio de MinIO**

* Un servicio `minio` en `compose.yaml` con el perfil `almacen`. No funciona: un perfil inactivo no evita la interpolación de `${…:?}`, de modo que `up -d db` falla si faltan las variables (`E-4`).
* El mismo servicio con `${…:-}` en lugar de `${…:?}`. Evita el fallo, pero si faltan las variables MinIO arrancaría con `minioadmin:minioadmin`, publicado en `127.0.0.1`. Es una credencial por omisión conocida por todo el mundo.
* Un archivo aparte, `compose.almacen.yaml`, sin perfil y con `${…:?}`. Se carga solo cuando se pide: `docker compose -f compose.yaml -f compose.almacen.yaml up -d minio`.

**Qué imagen se usa**

* `minio/minio`, la imagen del diseño. Ya no se descarga.
* Una imagen de `quay.io`. Exige autenticación, lo que rompe el arranque reproducible de `TKT-001` y de la integración continua.
* `pgsty/minio`, un fork comunitario que conserva las etiquetas `RELEASE.*`, fijado por etiqueta y por digest.

**Cómo se aplica el CORS**

* `put_bucket_cors` desde `herramientas/almacen_local.py`. MinIO responde `501`.
* Sin configuración. MinIO refleja cualquier origen, y la restricción al origen de la SPA desaparece.
* `MINIO_API_CORS_ALLOW_ORIGIN` en el servicio y en el contenedor de las pruebas, con el valor de `CIMENTA_SPA_ORIGEN`.

## Decisión

Se elige **un archivo aparte sin perfil y con `:?`, la imagen `pgsty/minio` fijada por etiqueta y digest, y el CORS por `MINIO_API_CORS_ALLOW_ORIGIN`**, porque:

* **`compose.almacen.yaml` es la única forma que cumple las dos exigencias a la vez.** `docker compose up -d db` sigue funcionando con un `.env` anterior a TKT-059, y MinIO nunca arranca con credenciales por omisión: si faltan las variables, `up -d minio` falla en voz alta. La VPS no carga el archivo, así que su despliegue no cambia.
* **`pgsty/minio:RELEASE.2026-08-04T00-00-00Z`, con el digest `sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372`, es la alternativa descargable que se comprobó** con `docker manifest inspect` el 2026-11-11. Conserva las etiquetas `RELEASE.*` y trae `mc`, que usa el `healthcheck`. La persona dueña la eligió. Fijar el digest, además de la etiqueta, evita que un fork de una sola organización cambie la imagen bajo los pies sin que nadie lo note.
* **El CORS por variable de entorno es lo que MinIO sí implementa** (`E-5`, caso c2): con `MINIO_API_CORS_ALLOW_ORIGIN`, el preflight y el `PUT` firmado solo reciben `Access-Control-Allow-Origin` para el origen de la SPA. No hay código de CORS que mantener ni que probar aparte de la configuración de la fixture.

## Consecuencias

**Positivas**

* `docker compose up -d db` no cambia para nadie, y el arranque de MinIO exige las variables del almacén.
* La imagen es reproducible: etiqueta y digest, no `latest`.
* `herramientas/almacen_local.py` no contiene código de CORS, y `_imagen_minio()` de `conftest.py` lee la imagen de `compose.almacen.yaml`, de modo que local y pruebas usan la misma.

**Negativas o costes aceptados**

* **Se depende de un fork comunitario de una sola organización.** Si esa organización deja de publicar o retira la etiqueta, el almacén local y las pruebas dejan de arrancar. Se acepta en desarrollo; en producción el almacén es R2 y no usa esta imagen.
* **El comando de arranque es más largo**, porque hay que nombrar los dos archivos con `-f`.
* **El CORS es una barrera del navegador, no del servidor.** Un cliente que no sea un navegador (`curl`, un servicio) ignora la política. La protección de los objetos sigue siendo la URL prefirmada y su caducidad, no el CORS.
* **Cambiar el origen de la SPA obliga a recrear el contenedor**, porque la variable se lee al arrancar.

**Cuándo revisar esta decisión**

* En TKT-073, antes de producción: revisar la procedencia del fork y decidir si se mantiene, se sustituye o se construye una imagen propia.
* Si `minio/minio` vuelve a publicarse en un registro anónimo, o aparece un sustituto mantenido por el proyecto original.
* Si otro servicio de desarrollo necesita variables obligatorias y el patrón de un archivo por servicio deja de escalar, se reconsidera la estructura de los archivos de Compose.
