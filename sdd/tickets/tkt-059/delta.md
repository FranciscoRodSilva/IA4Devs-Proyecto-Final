# Delta · TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> [← index](_index.md) | [← impl](impl.md)

El delta declara qué cambió en el sistema. TKT-059 se partió en cinco entregas que se ejecutaron y revisaron por separado, se acumularon en una sola rama y salen en un solo pull request:

| Entrega | Filas | Qué aportó |
|---|---|---|
| 059a | 0 a 4 | MinIO local y de pruebas (`compose.almacen.yaml`), la herramienta del bucket, la migración `0012` con la tabla `archivo` y sus invariantes 23 a 26, y las tres reglas puras del dominio (lista blanca, declaración y orden de la confirmación) |
| 059b | 5 a 7 | El puerto `AlmacenObjetos` con su adaptador `AlmacenS3` sobre `boto3` (dos clientes, uno por dirección) y el detector del tipo por los bytes con lecturas por rango acotadas |
| 059c | 8 a 10 | Los diez ajustes del almacén y de archivos, el almacén obligatorio con base, el contexto de archivos con su composición perezosa en la fábrica, el repositorio de `archivo` y `registrar_archivo`, la interfaz de alta que necesita TKT-018 |
| 059d | 11 a 13 | `confirmar_archivo` con sus once pasos y la ruta `POST /api/v1/archivos/{archivo_id}/confirmacion`. La fila 11 no necesitó código |
| 059e | 14 a 17 | Las dos rutas `GET` (metadatos y URL de descarga), el barrido de arranque de archivos, el lector del contenido conectado al ejecutor de TKT-015 y la prueba «ninguna ruta binaria» |

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Tabla `archivo`, sus nueve restricciones nombradas (invariantes 23 a 26), tres índices y `REVOKE DELETE` al rol de aplicación | `backend/migraciones/versions/v0012_archivos_archivo.py` | Guardar el archivo adjunto sin los bytes ni la clave en el contrato, con estados `PENDIENTE`, `DISPONIBLE`, `CADUCADO` y `ANULADO`. Un archivo no se borra |
| Lista blanca de ocho tipos, categorías y disposición; límites por categoría; orden de las comprobaciones de la confirmación; `UrlFirmada` | `backend/cimenta/archivos/dominio/` | Reglas de `RNF-06` y `RNF-19` puras, sin `datetime` ni biblioteca de terceros |
| Puerto `AlmacenObjetos` y adaptador `AlmacenS3` | `aplicacion/puertos.py`, `infraestructura/almacen_s3.py` | Hablar con MinIO por `boto3`: URL de subida firmada con tamaño y SHA-256, metadatos, lecturas por rango, reescritura del tipo dentro del almacén y URL de lectura con tipo y disposición firmados. Cambia de destino solo por `endpoint_url` |
| Detector del tipo por los bytes | `infraestructura/detector_tipo.py` | Reconocer JPEG, PNG, WebP, HEIC, MP4, PDF, XML y `.xlsx` leyendo como máximo 256 KiB por parte, y rechazar SVG, `.xlsm`, ZIP genérico y XML con `DOCTYPE` o entidades |
| `ContextoArchivos`, `ConfiguracionArchivos`, `AlmacenNoConfigurado` y `construir_contexto` | `aplicacion/contexto.py` | Composición perezosa: construir la aplicación no crea el cliente de `boto3` ni exige el almacén sin base |
| `registrar_archivo` y `AltaArchivo` | `aplicacion/alta.py` | Interfaz publicada con la que el módulo dueño del documento (TKT-018) registra el adjunto en su propia transacción. Valida la declaración antes de insertar o firmar |
| `confirmar_archivo` | `aplicacion/confirmacion.py` | Verificar tamaño, SHA-256 y tipo contra el objeto almacenado, con la fila bloqueada, y asentar `CONFIRMAR` en la misma transacción |
| `obtener_archivo`, `emitir_url_descarga` | `aplicacion/consulta.py` | Metadatos y URL de descarga de vida corta |
| `definicion_barrido_archivo` | `aplicacion/barrido.py` | Pasar a `CADUCADO` los `PENDIENTE` vencidos al arrancar, sin tocar el almacén ni la bitácora |
| `crear_lector_contenido`, `ArchivoNoLegible` | `aplicacion/lectura.py` | El origen de los bytes que lee el ejecutor del análisis de TKT-015 |
| Repositorio de `archivo` | `infraestructura/repositorio.py` | Acceso a la tabla, con `bloquear` (`FOR UPDATE`), `leer`, `marcar_disponible` y `marcar_caducado` |
| Rutas, esquemas, montaje y dependencia | `backend/cimenta/archivos/api/` | Las tres operaciones del borrador con `TKT-059` en `x-tickets` |
| Diez campos nuevos en `AjustesServidor` | `backend/servidor/ajustes.py`, `.env.example` | `CIMENTA_ALMACEN_ENDPOINT`, `CIMENTA_ALMACEN_BUCKET`, `CIMENTA_ALMACEN_CLAVE_ACCESO`, `CIMENTA_ALMACEN_CLAVE_SECRETA` y las seis `CIMENTA_ARCHIVOS_*`. `CIMENTA_ALMACEN_ORIGEN` ya existía desde TKT-057 y pasa a obligatoria con base. `CIMENTA_SPA_ORIGEN` la lee la herramienta del bucket y Compose, no `AjustesServidor` |
| MinIO local y herramienta del bucket | `compose.almacen.yaml`, `backend/herramientas/almacen_local.py` | Almacén de objetos en desarrollo y en las pruebas, aparte de `compose.yaml` para que `up -d db` siga funcionando con un `.env` anterior |
| Dos ADR | `docs/adr/20261111-almacen-local-en-compose-aparte.md`, `docs/adr/20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md` | Ver «Decisiones» |
| Ayudas de prueba y fixtures de MinIO | `backend/herramientas/soporte_tkt059.py`, `backend/tests/conftest.py` | Contenedor de MinIO, bucket y aplicación de pruebas con almacén |
| Más de 500 tests | `backend/tests/test_tkt059_*.py` | Un test por escenario, con el contrato de error completo en cada rechazo, concurrencia y tabla de mutantes |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `AjustesServidor` y `cargar_ajustes` | `backend/servidor/ajustes.py` | Cuatro campos → catorce. Con las variables de base configuradas, las cuatro del almacén son obligatorias y el arranque falla nombrándolas; sin base, nada cambia |
| `crear_aplicacion` y el `lifespan` | `backend/servidor/fabrica.py` | Sin archivos → `almacen=None`, `montar_archivos`, barrido de archivos después del de importaciones y lector del contenido real en lugar de `leer_contenido_no_configurado` |
| `EstadoArchivo` del borrador | `docs/api/openapi.yaml` | `[PENDIENTE, DISPONIBLE, ANULADO]` → incluye `CADUCADO` |
| `confirmar_archivo` del borrador | `docs/api/openapi.yaml` | El `409` genérico → `oneOf` de `CONFLICTO` y `CONCURRENCIA` con `Retry-After`, los códigos `ARCHIVO_NO_SUBIDO`, `ARCHIVO_CADUCADO` y `ESTADO_NO_PERMITE_OPERACION`, el `403` `NO_ES_SOLICITANTE` y ejemplos nuevos |
| `obtener_url_descarga_archivo` del borrador | `docs/api/openapi.yaml` | `409` genérico → `ARCHIVO_NO_DISPONIBLE` y `ARCHIVO_CADUCADO` con un ejemplo cada uno |
| Verificador de secretos de `.env.example` (`TC-18`) | `tools/tests/test_definicion_dependabot.py` | Toda clave sensible con valor debía ser `solo-desarrollo-*` o una credencial de prueba declarada → admite una excepción nominal: `CIMENTA_ALMACEN_CLAVE_ACCESO=cimenta-local`, identificador público de desarrollo, decidida por la persona dueña el 2026-11-11 (ver «Decisiones») |
| `compose.yaml` | `compose.yaml` | Sin mención del almacén → un comentario que remite a `compose.almacen.yaml`; el servicio `minio` no está en este archivo |
| Prueba de CSRF de las rutas que mutan | `backend/tests/test_tkt057_csrf.py` | `CUERPOS_VALIDOS` recibe la entrada de la confirmación (fila 12a del diseño) |
| Convenciones de Docker | `.claude/skills/conv-docker/SKILL.md` §2 | El bloque «(asumido)» sobre el almacén local → la decisión de TKT-059 (servicio `minio` en un Compose aparte y bucket creado por `herramientas.almacen_local`) |
| Trabajo `humo` de `ci.yml` | `.github/workflows/ci.yml` | Genera también `CIMENTA_ALMACEN_CLAVE_SECRETA` con `openssl rand` |
| Dependencias | `backend/pyproject.toml`, `backend/uv.lock` | Sin cliente de almacén → `boto3` y `puremagic`; de desarrollo, `boto3-stubs[s3]`, `testcontainers[postgres,minio]` y `types-defusedxml`. `mypy` estricto cubre `cimenta.archivos.*` |
| `TKT-057/TC-52`, `TKT-072/TC-20` y `TC-21`, `test_tkt017_migracion.py` | `backend/tests/` | El conjunto exacto de campos de los ajustes (cuatro → catorce, con la aserción de nombres acotada a los campos `db_`) y la cabeza de las migraciones (`0011` → `0012`) |
| Documentación | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/` | Conteo de ADR a 43, comandos de MinIO sin marca «desde TKT-059», lista blanca con solo `.xlsx`, estado de `CADUCADO`, la descarga en la especificación de la API, la ficha de TKT-059 y las filas `RNF-06` y `RNF-19` del stack §6.6 |
| Cuatro referencias rotas de TKT-018b | `sdd/tickets/tkt-018b/spec.md`, `_index.md` | Enlaces a `design.md` e `impl.md` que aún no existen y un ancla de `08-wireframes.md` → texto plano y el ancla real. Decisión de la persona dueña; sin cambio de reglas ni de criterios |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| El lector provisional `leer_contenido_no_configurado` como valor por omisión de la fábrica | `backend/servidor/fabrica.py` | La fábrica deja de importarlo porque conecta el lector real. La función sigue publicada en `presupuesto` y no se tocó ese módulo |
| La línea comentada `# CIMENTA_ALMACEN_ORIGEN=` de la sección de TKT-057 | `.env.example` | Sustituida por la sección del almacén, con la clave activa |

## Comportamiento observable nuevo

- Un Director de Proyectos puede confirmar el archivo que subió: el servidor comprueba contra el objeto realmente almacenado que exista, que su tamaño y SHA-256 coincidan con lo declarado y que su tipo, **leído de los bytes**, esté en la lista blanca. Si todo coincide el archivo pasa a `DISPONIBLE` y el SHA-256 queda en la bitácora; si no, `409` y el archivo sigue `PENDIENTE` (HDU-001 esc. 25 y 26).
- Confirmar dos veces el mismo archivo devuelve `200` con la misma fila y un solo asiento. Una subida que venció sin que el barrido la alcanzara responde `409` `ARCHIVO_CADUCADO` y la fila pasa a `CADUCADO` en la misma operación.
- Otro Director de Proyectos que intente confirmar un archivo ajeno recibe `403` `NO_ES_SOLICITANTE`, asentado como `DENEGAR`, sin ningún dato del archivo.
- Dirección General y Director de Proyectos pueden consultar los metadatos de un archivo y pedir una URL de descarga que caduca en minutos, servida desde el origen del almacén. Todo lo que no es imagen ni video se descarga como `attachment`.
- Al arrancar, la aplicación pasa a `CADUCADO` los archivos `PENDIENTE` con más de 24 horas, sin tocar el almacén.
- Con la base configurada, la aplicación no arranca si falta alguna variable del almacén, y el error nombra cuáles sin mostrar sus valores. Sin base, arranca como antes.
- El análisis del Excel de TKT-015 ya puede leer el contenido de un archivo `DISPONIBLE`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/archivos/{archivo_id}/confirmacion` (`confirmar_archivo`) | Ruta nueva, solo `DIRECTOR_PROYECTOS`, CSRF por doble envío | No |
| `GET /api/v1/archivos/{archivo_id}` (`obtener_archivo`) | Ruta nueva, `DIRECCION_GENERAL` y `DIRECTOR_PROYECTOS` | No |
| `GET /api/v1/archivos/{archivo_id}/descarga` (`obtener_url_descarga_archivo`) | Ruta nueva con los mismos roles | No |
| `EstadoArchivo` | Se añade `CADUCADO` a un enumerado que ningún cliente consumía todavía | No |
| `Archivo`, `UrlDescarga` | Esquemas nuevos; `Archivo` nunca lleva la clave del objeto | No |
| `frontend/src/api/generado/servidor.ts` | Regenerado | No |
| `cimenta.archivos.interfaz` | Publica `AlmacenObjetos`, `AltaArchivo`, `AlmacenNoConfigurado`, `ArchivoNoLegible`, `ConfiguracionArchivos`, `ContextoArchivos`, `LimitesArchivo`, `construir_contexto`, `contexto_de_archivos`, `crear_almacen_s3`, `crear_lector_contenido`, `definicion_barrido_archivo` y `registrar_archivo` | No: es nueva |
| Esquema de la base | Tabla `archivo`, migración `0012`; la bajada se niega si hay filas | No |
| Configuración | Diez variables nuevas; cuatro obligatorias con base | **Sí, para quien despliega con base:** `TKT-058`, `/sdd-desplegar` y los `.env` de la VPS necesitan las cuatro variables antes de arrancar la aplicación |

## Decisiones (ADR)

### 2026-11-11 — Almacén local en un Compose aparte

**Contexto:** el diseño ponía el servicio `minio` en `compose.yaml` detrás de un perfil. Los experimentos `E-0` y `E-4` mostraron que la imagen `minio/minio` ya no se descarga y que Compose interpola las credenciales del servicio aunque su perfil esté inactivo.
**Opciones consideradas:** perfil `almacen` en `compose.yaml` con `:?`; el mismo perfil con `:-`; un segundo archivo de Compose.
**Decisión:** `compose.almacen.yaml` aparte, sin perfil, con la imagen `pgsty/minio` fijada por etiqueta y digest, para que `docker compose up -d db` no exija las variables del almacén en la VPS ni en un `.env` anterior.
**Evidencia:** `E-0`, `E-4` y `TC-45a` en `impl.md` de 059a.
**Consecuencias:** hay dos archivos de Compose y el comando de MinIO los nombra. El CORS local lo fija `MINIO_API_CORS_ALLOW_ORIGIN`, porque MinIO responde `501` a `put_bucket_cors`.

→ `docs/adr/20261111-almacen-local-en-compose-aparte.md`.

### 2026-11-11 — Confirmación de archivos sin descargar el objeto

**Contexto:** la confirmación debe comprobar tamaño, hash y tipo sin retener un hilo del grupo ni pasar los bytes por el API (ADR-013, ADR-016).
**Opciones consideradas:** calcular el SHA-256 leyendo el objeto en la ruta; calcularlo en un trabajo; firmar el SHA-256 en la subida y compararlo con los metadatos; leer el tipo con una descarga completa o con lecturas por rango.
**Decisión:** el almacén verifica la suma firmada al recibir el `PUT`, la confirmación la compara con los metadatos del objeto (`head_object` con `ChecksumMode=ENABLED`) y el tipo se lee con lecturas por rango acotadas. `copy_object` con `REPLACE` conserva la suma, así que la reescritura del tipo ocurre antes de confirmar la fila (orden A).
**Evidencia:** `E-1` y `E-2` en `impl.md` de 059a; `TC-17` (un libro de 26 MB se reconoce con menos de 262 144 bytes leídos) y `TC-21`.
**Consecuencias:** el límite de lectura de una parte baja de 1 MiB a 256 KiB por una bomba de profundidad en el XML. Una suma ausente cuenta como distinta.

→ `docs/adr/20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md`.

### 2026-11-11 — Excepción nominal de `TC-18` para la clave de acceso del almacén local

**Contexto:** dos pruebas existentes no podían cumplirse a la vez: `TC-18` exige `solo-desarrollo-*` en toda clave sensible con valor en `.env.example`, y `test_tkt057_entorno.py` prohíbe esa cadena en el archivo.
**Opciones consideradas:** relajar `TC-18` para toda clave de acceso; admitir solo esta variable con su valor exacto; cambiar la otra prueba. Se presentaron a la persona dueña, que eligió admitir la variable en `TC-18`.
**Decisión:** una excepción nominal, con el nombre de la variable y su valor exactos (`cimenta-local`, identificador público de desarrollo, no un secreto), y ocho mutantes de rechazo. Que la excepción exija **el valor exacto y no solo el nombre** es un supuesto del tester y más estricto que la decisión **(asumido)**.
**Evidencia:** `impl.md`, «Ajustes respecto al design» de 059a.
**Consecuencias:** cualquier otra clave sensible con valor sigue sin pasar. No merece un ADR del repositorio: es una excepción acotada a una prueba, sin efecto sobre la arquitectura, y consta aquí y en `impl.md`.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un `409` que además marca la fila como vencida debe guardar el rechazo y lanzarlo **después** del `with`; si se lanza dentro, la transacción se deshace y el `UPDATE` se pierde | `M-10` cae en `TC-28` | Cualquier caso de uso que rechaza y escribe a la vez |
| Quitar `repr=False` de una URL prefirmada la lleva al `repr` de la excepción y de los registros; un test de `repr`, `str` y f-string la protege | `test_tkt059_ca03_url_firmada_oculta_la_url_en_su_repr` y su gemelo de `AltaArchivo` | Toda credencial de portador en un `dataclass` |
| Un valor con `NUL` o con sustitutos Unicode llega a PostgreSQL y revienta con `500` (`DataError` o `UnicodeEncodeError`); la defensa es una regla de forma en el dominio | `test_tkt059_ca03_nombre_con_caracteres_no_permitidos` | Cualquier texto libre que se inserte |
| `copy_object` con `MetadataDirective="REPLACE"` conserva la suma SHA-256 en MinIO, lo que permite reescribir el tipo sin perder la integridad | Resultado `E-1 (g1)` | La reescritura del tipo en la fase 2 (evidencia de campo) |
| La interpolación de Compose evalúa las credenciales de **todos** los servicios aunque su perfil esté inactivo | `E-4` | Cualquier servicio opcional con variables obligatorias |
| Una prueba que recorre las rutas de la aplicación necesita un caso de control que la obligue a fallar; un comprobador que solo mira la clase declarada deja pasar un `StreamingResponse` sin anotar | `M-17` y los seis casos de control de `TC-43` | Cualquier prueba de arquitectura sobre el enrutador |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Un subagente de cierre murió por el límite de uso de la cuenta a mitad de una tanda de mutantes, y pudo dejar un mutante aplicado en el árbol. Se detectó porque el orquestador revisó `git status` y buscó restos antes de reanudarlo; el protocolo de mutación no dice qué hacer si el agente se corta | Media |
| `comando` | `/sdd-revisar` detectó huecos de cobertura Mayores (la rama `57014` y `referencia_id` nulo) **después** de que `/sdd-ejecutar` cerrara con la tabla de mutantes completa en verde. La tabla de mutantes del diseño cubre las reglas del plan de pruebas, pero no las ramas de código añadidas por el desarrollador | Media |
| `plantilla` | El diseño citó nombres de tests (`TC-07`, `TC-30`, `TC-53`) que la ejecución repartió en varios o no escribió, y `auditor-docs` los marcó en cada entrega. El plan de pruebas no tiene una columna que se actualice al ejecutar | Baja |
| `agente` | Los desarrolladores de las filas 8 y 9 escribieron todos sus pasos de una vez y corrieron la suite después, en lugar de ponerlos en verde de uno en uno. Se declaró en `impl.md` como ajuste | Baja |
| `comando` | El verificador de documentos estuvo en rojo en toda la rama por cuatro enlaces de otro ticket (TKT-018b) y recién en la última revisión se decidió corregirlos. Cada auditor de docs lo marcó como ajeno pero Mayor | Media |
| `comando` | El diseño pedía varias decisiones sobre el almacén (`P-3`, `P-14`) que la ejecución superó con evidencia (`E-0`, `E-4`) y tuvo que reescribir en `impl.md`; el bloque «Documentación afectada» de `design.md` mantuvo texto superado hasta tener una nota de ajuste | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Endurecimiento del detector de tipos frente a dos entradas malformadas de contenedores que hoy no se rechazan (`auditor-seguridad`, prioridad baja), y pedir `Body.read(fin - inicio + 1)` en `leer_rango` | Prioridad baja, no empeoradas por las entregas posteriores; decisión de la persona dueña del 2026-11-12 | Endurecimiento del detector de tipos de `archivos` (sin número todavía) |
| El lector del contenido y la confirmación mantienen una conexión del pool durante la E/S con el almacén; el motor no fija `pool_timeout` ni `idle_in_transaction_session_timeout` | El diseño lo fija así (`leer_todo` dentro del `with begin()`); sacar la lectura del bloque son tres líneas | Un ticket de operación del motor de base y, si se decide, un ajuste del lector |
| Las lecturas de archivos filtran solo por rol (**asumido**: decisión por rol de `PA-T59.8`; no existe eje de asignación por obra) | No existe modelo de asignación usuario-obra | TKT-018: todo listado que exponga un `archivo_id` debe filtrar por obra, el DTO debe tipar `referencia_tipo` como `Literal`, y al crear la importación se exige un archivo `DISPONIBLE`, de la misma obra y `.xlsx` |
| Imagen `pgsty/minio` (fork comunitario, fijada por etiqueta y digest en `compose.almacen.yaml`): procedencia y sustitución antes de producción | `minio/minio` ya no se descarga (comprobado el 2026-11-11); la elección de la imagen la decidió la persona dueña | TKT-073 |
| `nosniff` en el origen del almacén | Una URL prefirmada no puede fijar esa cabecera; la defensa es `attachment` y el `Content-Type` firmado | TKT-073 (MinIO en la VPS, detrás de Caddy) |
| `obtener_archivo` conserva `HDU-001 esc. 24` en `x-escenarios` del borrador | Ese escenario es de TKT-018 | TKT-018 o su cierre |
| El conteo de `HDU-001` sigue `PENDIENTE` en `tools/historias_activas.txt` | Hasta TKT-017c el verde de `verificar_escenarios.py` no prueba los esc. 25 y 26; los prueban los tests por nombre | TKT-017c |
| Retirar `leer_contenido_no_configurado` de `presupuesto` | Ya no tiene llamadores en producción, pero el diseño la deja publicada | Un ticket de `presupuesto` |

## Pull request

**Título:** `TKT-059 · Módulo archivos mínimo: subida prefirmada, confirmación por hash y barrido`
**Origen:** `agent`
**Cuerpo:** qué (el módulo `archivos` mínimo, en cinco entregas: almacén y esquema, adaptadores, ajustes y alta, confirmación, consulta y barrido), por qué (el Excel de la línea base no puede pasar por el API, ADR-016, y la fase 2 reutiliza el módulo entero), criterios cubiertos (los catorce de la spec y `CA-R1`, con los escenarios 25 y 26 de HDU-001) y cómo verificarlo (`uv run pytest` con Docker, `lint-imports`, `verificar_docs.py`). Señala que modifica `docs/api/openapi.yaml`, `.github/workflows/ci.yml`, `.claude/skills/conv-docker/SKILL.md`, `docs/adr/`, `compose.yaml`, `pyproject.toml`, `uv.lock` y `tools/tests/test_definicion_dependabot.py`: **modifica las compuertas**.
