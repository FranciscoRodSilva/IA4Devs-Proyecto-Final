# Design · TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

El módulo `archivos` nace con sus cuatro capas y un puerto, `AlmacenObjetos`, con un único adaptador sobre `boto3` que habla con MinIO en local, en pruebas y, según la decisión de la persona dueña del 2026-11-06, también en producción (MinIO autoalojado en la VPS, que despliega TKT-073). El adaptador distingue dos direcciones: el **endpoint interno**, por el que el servidor opera sobre los objetos, y el **origen público**, con el que firma las URL que usa el navegador; firmar no abre red, así que son dos clientes `boto3` con la misma configuración. El almacén solo concede permiso de CORS al origen de la SPA, de modo que el navegador solo sube desde ahí (`CA-14`; no es una barrera del servidor contra otros clientes, ver el alcance real en la spec). El alta es una función de la interfaz publicada que escribe la fila `PENDIENTE` en la transacción de quien llama y devuelve una URL `PUT` firmada con el tamaño y el SHA-256 declarados; la confirmación es la única ruta que muta, bloquea la fila con `FOR UPDATE`, compara tamaño y suma contra los **metadatos** del objeto (`head_object` con `ChecksumMode=ENABLED`) y lee el tipo con **lecturas por rango** acotadas, nunca con la descarga completa. Las reglas —lista blanca, límites por categoría, orden de las comprobaciones, vencimiento— viven en `dominio/`; el reconocimiento de formatos (`puremagic`, ZIP, `defusedxml`) vive en `infraestructura/`. El barrido reutiliza `DefinicionBarrido` sin tocar el almacén, y la lectura del contenido para el ejecutor de TKT-015 se conecta en `servidor/fabrica.py`.

**Nada de esto se construye antes de los experimentos `E-1` y `E-2`.** La spec exige que el almacén verifique la suma firmada (`PA-T59.6`) y que la comprobación del `.xlsx` quepa en lecturas por rango (`PA-T59.14`). Ninguna de las dos afirmaciones tiene evidencia en el repositorio: la fila 0 las comprueba contra MinIO real y, si alguna falla, el ticket se detiene con `/sdd-escalar`.

Consultas a Context7 el 2026-11-05: `boto3` (configuración `request_checksum_calculation` con `when_supported` y `when_required`, URL prefirmadas con `generate_presigned_url` y `Params`; **la documentación no afirma** que una suma `ChecksumSHA256` quede firmada en una URL prefirmada ni que MinIO la verifique, y por eso es experimento), `puremagic` (`magic_string(bytes) -> list[PureMagicWithConfidence]` ordenada por confianza, con `extension` y `mime_type`, que puede venir vacío), FastAPI (`operation_id`, `response_model`, `dependencies` y `response_class` con `JSONResponse` por omisión en el decorador) y `pydantic-settings` (`env_ignore_empty`, `SecretStr`, validación de omisiones). SQLAlchemy 2.1 (`with_for_update()` en Core y `Session.begin()` que deshace ante una excepción) ya lo consultó TKT-017 el mismo día; este diseño no usa nada fuera de eso.

## Estado de partida comprobado

Leído el 2026-11-05 sobre `Produccion` (`b39b862`):

- `backend/cimenta/archivos/` tiene los cinco `__init__.py` y un `interfaz.py` vacíos. La última migración es `v0010_presupuesto_concepto_de_partida.py`; TKT-017 reservó `0011` en su diseño, sin ejecutar.
- `servidor/ajustes.py`: `AjustesServidor` con `db_contrasena_aplicacion`, `almacen_origen` (opcional, patrón de origen), `trabajos_intervalo_latido` y `trabajos_umbral_vencimiento`; `cargar_ajustes(mapa)` solo copia las claves de `model_fields`, así que las variables `CIMENTA_DB_HOST`, `_PUERTO` y `_NOMBRE` no llegan al modelo.
- `tests/test_tkt057_arranque.py`: TC-51 (líneas 91 a 97) carga un mapa **sin** variables de base; TC-52 (líneas 100 a 121) afirma el conjunto **exacto** de `model_fields`.
- `servidor/fabrica.py`: `crear_aplicacion(..., leer_contenido_archivo=None)` usa `leer_contenido_no_configurado` (líneas 61 a 65) y el `lifespan` barre solo `definicion_barrido_importacion` (líneas 88 a 96) y solo si hay motor o variables de base (líneas 79 a 85).
- `trabajos/barrido.py`: `barrer` marca vencida la fila con la marca **nula o anterior** a `now() - umbral` y llama a `al_vencer` si hubo cambios; `barrer_todas` corre cada definición en su transacción y relanza el primer fallo.
- El ejecutor de TKT-015 llama a `leer_contenido(archivo_id)` en su hilo coordinador (`ejecutor_analisis.py`, línea 227) y convierte cualquier excepción en `ARCHIVO_ILEGIBLE`.
- `exigir_rol` asienta `DENEGAR` con `registrar_denegacion` en una transacción propia (`identidad/api/dependencias.py`, líneas 157 a 187); `verificar_origen` hace lo mismo con `ORIGEN_NO_VERIFICADO`. Un `403` que nace en un caso de uso lo asienta el propio caso de uso con `asentar_denegacion`.
- `contrato_error`: los seis `ARCHIVO_*`, `ESTADO_NO_PERMITE_OPERACION` y `NO_ES_SOLICITANTE` existen. `normalizar_detalle` admite `str`, `int`, `bool`, `UUID`, listas y mapas, **no** `None`.
- `compose.yaml` solo tiene `db`; `conftest.py` lee la imagen de PostgreSQL de `compose.yaml` con un patrón que exige exactamente una línea `image: postgres:…`.
- `ci.yml`: el trabajo `backend` corre `pytest` sin servicios (testcontainers trae los contenedores); el trabajo `humo` genera las tres contraseñas con `openssl rand` a partir de `.env.example` y arranca el backend con `fastapi run` y la base migrada.
- `pyproject.toml`: sin `boto3` ni `puremagic`; `testcontainers[postgres]`; `grafo-archivos` (líneas 158 a 165) permite que importen `archivos` solo `presupuesto`, `almacen` y `avance`; el `mypy` estricto (líneas 49 a 58) no cubre `cimenta.archivos`.
- `tests/test_tkt072_migracion.py` usa `REVISION_NUEVA = "0010"` como cabeza en TC-20 (líneas 337 y 352): cualquier migración nueva la rompe, igual que ya previó TKT-017 en su fila A1.
- `nombres_de_usuarios` no existe todavía: TKT-017 la aprobó (`P-8`) para su entrega b1, sin ejecutar.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Tabla `archivo`, sus restricciones y sus tres índices | 5 · objeto nuevo | No existe; el modelo de datos §12 fija columnas, invariantes 23 a 26 e índices. Los invariantes son `CHECK` y `UNIQUE` del motor (peldaño 2 dentro del objeto) |
| `REVOKE DELETE ON archivo FROM cimenta_aplicacion` | 2 · nativo | El privilegio sostiene que un archivo no se borra (`PA-T59.10`); el patrón es el de `bitacora` en `0003`. `TRUNCATE` no se revoca porque los privilegios por omisión de `0001` no lo conceden: `TC-02` lo comprueba como regresión, y el mutante `M-18` (quitar el `REVOKE DELETE`) lo pone en rojo |
| Guarda de la bajada | 3 · reuso | El bloque `DO` con `RAISE EXCEPTION` de `0007` y `0010`: la bajada se niega si hay filas |
| `cimenta/archivos/dominio/tipos.py` | 5 · objeto nuevo | La lista blanca, su categoría y la disposición son regla (`RNF-06`) y no existen |
| `cimenta/archivos/dominio/declaracion.py` | 5 · objeto nuevo | Límites por categoría y forma de la declaración (`PA-15`); puro |
| `cimenta/archivos/dominio/confirmacion.py` | 5 · objeto nuevo | El orden de las comprobaciones, el vencimiento (`PA-T59.13`) y la comparación con lo almacenado son regla; puros y probables sin base |
| Puerto `AlmacenObjetos` (`aplicacion/puertos.py`) | 5 · objeto nuevo | Lo exige `M2`; un `Protocol` deja que las pruebas pongan un espía sin cambiar el caso de uso |
| `infraestructura/almacen_s3.py` · `AlmacenS3` | 5 · objeto nuevo | Único adaptador, sobre `boto3` (ADR-016 regla 6) |
| `infraestructura/detector_tipo.py` · `detectar_tipo` | 5 · objeto nuevo | `puremagic` reconoce firmas; el ZIP del `.xlsx` y el XML necesitan la comprobación estructural del stack §4.6 por rangos, que ninguna biblioteca hace sin descargar |
| `puremagic` | 3 · reuso | Lo decidió el stack §4.6; no se reabre |
| `defusedxml` | 3 · reuso | Ya es dependencia desde TKT-013b |
| `infraestructura/repositorio.py` | 5 · objeto nuevo | No hay repositorio de `archivo` |
| `aplicacion/contexto.py` · `ContextoArchivos` | 3 · reuso | El patrón de `ContextoIdentidad`: fábrica de sesiones perezosa y reloj inyectado, más el proveedor del almacén y la configuración |
| `aplicacion/alta.py` · `registrar_archivo` | 5 · objeto nuevo | Interfaz de alta de `M3` |
| `aplicacion/confirmacion.py` · `confirmar_archivo` | 5 · objeto nuevo | Caso de uso de `M4` |
| `aplicacion/consulta.py` · `obtener_archivo`, `emitir_url_descarga` | 5 · objeto nuevo | Casos de uso de `M5` |
| `aplicacion/lectura.py` · `crear_lector_contenido` | 5 · objeto nuevo | `M7`. Devuelve un `Callable[[UUID], bytes]`, la firma que el ejecutor ya espera |
| `aplicacion/barrido.py` · `definicion_barrido_archivo` | 3 · reuso | `DefinicionBarrido` con `columna_marca="creado_en"` y `al_vencer` sin efecto (ADR-037) |
| Bloqueo `FOR UPDATE` de la fila en la confirmación | 2 · nativo | Bloqueo de fila del motor, con el `lock_timeout` del rol de aplicación. Sin él, dos confirmaciones simultáneas asientan dos `CONFIRMAR` |
| Rutas, esquemas y montaje en `archivos/api/` | 5 · objeto nuevo | `archivos/api/` está vacío; el montaje sigue el patrón de `identidad` |
| Protección de rutas | 3 · reuso | `verificar_origen` y `exigir_rol` de `cimenta.identidad.interfaz`; `exigir_rol` ya asienta el `ROL_INSUFICIENTE` |
| Bitácora | 3 · reuso | `asentar` y `asentar_denegacion` de `cimenta.auditoria.interfaz` |
| `nombres_de_usuarios` en `cimenta.identidad.interfaz` | 3 · reuso si TKT-017b1 ya la publicó; si no, 5 · objeto nuevo con la firma de TKT-017 B1 (`P-5`) | `Archivo.subido_por` exige el nombre, y `archivos` no puede leer la tabla `usuario` |
| `UsuarioResumen` en `cimenta.identidad.interfaz` | 3 · reuso si ya está publicada; si no, 5 · objeto nuevo (`P-13`) | El diseño de TKT-017 solo prevé la función, no la clase. Si dos módulos declaran cada uno su `UsuarioResumen`, el OpenAPI publicado tendría dos componentes con ese nombre; la condición de la fila 11 es independiente para la función y para la clase |
| Variables del almacén y de archivos en `AjustesServidor` | 4 · cambio mínimo | Un solo sitio que valida y detiene el arranque nombrando la variable (`RNF-07`); `almacen_origen` ya existe y sigue siendo el origen público y el de la política de contenido; `almacen_endpoint` es nuevo y opcional (decisión de la persona dueña del 2026-11-06, que sustituye a `P-3`) |
| Segundo cliente `boto3` para firmar con el origen público | 4 · cambio mínimo | La URL prefirmada lleva el host con el que se firmó; en la VPS el servidor alcanza MinIO por la red interna de Docker y el navegador por el nombre público. Un cliente por dirección es lo mínimo: firmar no abre conexión |
| CORS del almacén | 2 · nativo (`E-5`) | MinIO lo resuelve con `put_bucket_cors` o con `MINIO_API_CORS_ALLOW_ORIGIN`; ningún objeto propio |
| Variable `CIMENTA_SPA_ORIGEN` | 5 · objeto nuevo (`P-15`) | No existe ninguna variable con el origen de la SPA (comprobado en `servidor/ajustes.py`, `frontend/vite.config.ts` y `.env.example`); la necesita el CORS. La leen `herramientas.almacen_local` o la interpolación de `compose.yaml`, no `AjustesServidor`: el servidor no la usa |
| Exigencia del almacén con base configurada | 4 · cambio mínimo | Una comprobación al final de `cargar_ajustes` con `variables_de_base_presentes`, que ya existe; no toca el arranque sin base |
| `crear_aplicacion(..., almacen=None)` y el montaje en la fábrica | 4 · cambio mínimo | Un parámetro y una llamada más, como `motor` y `montar_identidad` |
| Servicio `minio` en `compose.yaml` | 5 · objeto nuevo | Lo exige `M2` y lo prevé `conv-docker`. Detrás del perfil `almacen` (`P-14`), para que `docker compose up -d db` no lo arranque ni exija sus variables en la VPS ni en un `.env` local anterior |
| `herramientas/almacen_local.py` | 5 · objeto nuevo | Crea el bucket local; ningún documento decide cómo (`conv-docker` lo deja a este ticket, `P-6`) |
| Fixtures de MinIO en `conftest.py` | 3 · reuso | El patrón de `contenedor_postgres`, con la imagen leída de `compose.yaml` |
| Región `us-east-1` como constante del adaptador | 1 · YAGNI, sin variable | MinIO la acepta por omisión; una variable más no la pide ningún Must |
| Columna `tipo_declarado` | 1 · YAGNI, fuera | La spec decide que no se guarda (`PA-T59.5`) |
| Asiento de bitácora en el alta | 1 · YAGNI, fuera | Decisión de la persona dueña (`PA-T59.10`) |
| Cálculo del hash leyendo el objeto | 1 · fuera | Non-goal; si `E-1` falla, se escala |
| Servicio de MinIO en el trabajo `backend` de `ci.yml` | 1 · YAGNI, fuera | testcontainers levanta MinIO dentro de `pytest`, igual que PostgreSQL; un `services:` sería un segundo MinIO que ninguna prueba usa |
| MinIO en el trabajo `humo` | 1 · YAGNI, fuera (`P-7`) | La aplicación no contacta al almacén al arrancar y ningún recorrido de humo toca archivos |
| ADR nuevo | 5 · objeto nuevo (`P-8`) | Ver «¿Merece ADR?» |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la migración crea una tabla nueva, el cambio de ajustes no relaja el arranque sin base y el barrido de importaciones no cambia.

## Decisiones de diseño que la ejecución no reabre

### Tipos admitidos, categorías y disposición

Lista blanca en `dominio/tipos.py`, en este orden, que es también el de `tipos_admitidos` en el detalle de los rechazos:

| Tipo MIME | Categoría | Disposición |
|---|---|---|
| `image/jpeg` | `IMAGEN` | `inline` |
| `image/png` | `IMAGEN` | `inline` |
| `image/heic` | `IMAGEN` | `inline` |
| `image/webp` | `IMAGEN` | `inline` |
| `video/mp4` | `VIDEO` | `inline` |
| `application/pdf` | `DOCUMENTO` | `attachment` |
| `application/xml` | `DOCUMENTO` | `attachment` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `DOCUMENTO` | `attachment` |

El tipo declarado se compara **exacto**, tras `strip()` y `lower()`: sin alias (`text/xml`, `image/jpg`, `image/heif` se rechazan, `P-12`).

### Límites y forma de la declaración

`LimitesArchivo(imagen_bytes: int, video_bytes: int, documento_bytes: int)`. Por omisión, en mebibytes (`P-4`): 15 MiB = `15728640`, 50 MiB = `52428800`, 25 MiB = `26214400`. Un tamaño **igual** al límite se admite; uno mayor se rechaza.

`evaluar_declaracion(*, nombre_original: str, tamano_bytes: int, hash_sha256: str, tipo_declarado: str, limites: LimitesArchivo, campo_raiz: str) -> tuple[DefectoDeclaracion, ...]`, con `DefectoDeclaracion(campo: str, codigo: str, mensaje: str)`. Devuelve todos los defectos, en este orden de campos:

| Campo | Condición | `codigo` | `mensaje` |
|---|---|---|---|
| `{campo_raiz}.nombre_original` | vacío tras `strip()` | `OBLIGATORIO` | «El campo es obligatorio.» |
| `{campo_raiz}.nombre_original` | más de 255 caracteres | `DEMASIADO_LARGO` | «El nombre admite hasta 255 caracteres.» |
| `{campo_raiz}.nombre_original` | contiene `NUL` (U+0000) o un sustituto Unicode (U+D800 a U+DFFF) | `FORMATO` | «El nombre contiene caracteres no permitidos.» (decisión de la persona dueña, 2026-11-12; se acumula con `DEMASIADO_LARGO`, pero un nombre en blanco solo da `OBLIGATORIO`) |
| `{campo_raiz}.tamano_bytes` | `< 1` | `NO_POSITIVO` | «El tamaño debe ser mayor que cero.» |
| `{campo_raiz}.hash_sha256` | no cumple `^[0-9a-f]{64}$` | `FORMATO` | «El SHA-256 son 64 caracteres hexadecimales en minúsculas.» |
| `{campo_raiz}.tipo_declarado` | fuera de la lista blanca | `VALOR_NO_PERMITIDO` | «El tipo de archivo no está permitido. Se admiten JPEG, PNG, HEIC, WebP, MP4, PDF, XML y XLSX.» |
| `{campo_raiz}.tamano_bytes` | tipo admitido y tamaño > límite de su categoría | `FUERA_DE_RANGO` | «El archivo excede el límite de {límite} bytes ({MiB} MB) para {imágenes \| videos \| documentos}.», por ejemplo «El archivo excede el límite de 26214400 bytes (25 MB) para documentos.» |

`campo_raiz` vale `"archivo"` por omisión en la interfaz: es el nombre de la propiedad `DeclaracionArchivo` en `ImportacionNueva`. El dominio devuelve los códigos como cadena (no importa `contrato_error`); el caso de uso los envuelve en `ErrorDeCampo` y lanza `ValidacionRechazada`.

### Orden de comprobaciones de la confirmación

`confirmar_archivo(contexto: ContextoArchivos, *, archivo_id: UUID, usuario_id: UUID) -> ArchivoLeido`. Una transacción principal, `with contexto.fabrica_sesiones().begin() as sesion_bd:`, y el reloj leído **una vez** al empezar (`ahora = contexto.reloj()`).

| # | Comprobación | Resultado si falla | Qué escribe y dónde |
|---|---|---|---|
| 1 | `repositorio.bloquear(sesion_bd, archivo_id)` (`SELECT … FOR UPDATE`) | `NoEncontrado(recurso="archivo", mensaje="El archivo no existe.")`, lanzado dentro del bloque | Nada; se deshace |
| 2 | `evaluar_previa(...)` = `NO_ES_SOLICITANTE` (`fila.subido_por_id != usuario_id`) | `403` `PERMISO` `NO_ES_SOLICITANTE` | La transacción principal sale **sin escribir**; después, una transacción propia con `auditoria.asentar_denegacion` (ver «Denegación»); después se lanza `PermisoDenegado` |
| 3 | `= YA_DISPONIBLE` | `200` con la fila tal cual | Nada. Sin segundo asiento (`CA-4` esc. 2) |
| 4 | `= CADUCADO` | `409` `ARCHIVO_CADUCADO` | Nada |
| 5 | `= NO_CONFIRMABLE` (`ANULADO`, inalcanzable en este ticket) | `409` `ESTADO_NO_PERMITE_OPERACION` (`P-10`) | Nada |
| 6 | `= VENCIDO` (`PENDIENTE` y `vence_en < ahora`, con `vence_en = fila.creado_en + configuracion.umbral_pendiente` calculado en `aplicacion/`) | `409` `ARCHIVO_CADUCADO` | `repositorio.marcar_caducado` **dentro** del bloque; el bloque sale **sin excepción** y confirma; el `ConflictoEstado` se lanza **después** del `with` |
| 7 | `contexto.almacen().metadatos(clave)` → `comparar_objeto(...)` = `NO_SUBIDO` | `409` `ARCHIVO_NO_SUBIDO` | Nada |
| 8 | `= TAMANO_DISTINTO` | `409` `ARCHIVO_TAMANO_DISTINTO` | Nada |
| 9 | `= HASH_DISTINTO` (suma distinta **o ausente**, `P-11`) | `409` `ARCHIVO_HASH_DISTINTO` | Nada |
| 10 | `detectar_tipo(leer_rango, tamano)` → `tipo_admitido(tipo)` falso | `409` `ARCHIVO_TIPO_NO_PERMITIDO` | Nada |
| 11 | Todo coincide | `200` | Orden **A** (por omisión): `almacen.reescribir_tipo(clave, tipo)`; `repositorio.marcar_disponible(sesion_bd, archivo_id, tipo_mime=tipo, confirmado_en=ahora)`; `auditoria.asentar(sesion_bd, accion="CONFIRMAR", …)`; el bloque confirma. El orden definitivo lo fija `E-1` (g), según «Reescritura del tipo y suma del objeto» |

Los pasos 2 a 6 los decide **una** función pura, `evaluar_previa[T: Ordenable](*, estado: EstadoArchivo, subido_por_id: UUID, usuario_id: UUID, ahora: T, vence_en: T) -> PasoPrevio`, en ese orden: el solicitante va primero para que un `403` nunca revele el estado. `Ordenable` es un `Protocol` con `__lt__`, declarado en `dominio/confirmacion.py` con el mismo patrón de `identidad/dominio/vigencia.py`: la regla 2 de `CLAUDE.md` no deja usar `datetime` en `dominio/`, así que la suma `creado_en + umbral` la hace el caso de uso. El vencimiento es `vence_en < ahora`: en el instante exacto `ahora == vence_en` el archivo todavía se confirma. Los pasos 7 a 9 los decide `comparar_objeto(*, tamano_declarado: int, hash_declarado: str, objeto: ObjetoAlmacenado | None) -> Discrepancia | None`, en ese orden. El tipo admitido lo decide `tipo_admitido(tipo_mime: str) -> bool`.

**Cómo un `409` que además marca `CADUCADO` confirma la escritura.** El cuerpo del `with` no lanza en el paso 6: guarda el rechazo en una variable local `rechazo_tras_confirmar: ConflictoEstado | None` y termina normalmente, de modo que `Session.begin()` confirma el `UPDATE`. Fuera del `with`, `if rechazo_tras_confirmar is not None: raise rechazo_tras_confirmar`. Los rechazos que no escriben (pasos 1, 4, 5, 7 a 10) se lanzan dentro del bloque, que deshace una transacción vacía. El mutante `M-10` (lanzar dentro del bloque en el paso 6) pone en rojo `TC-28`.

**Bloqueo y E/S externa.** Los pasos 7 a 11 hablan con el almacén con la fila bloqueada: la cabecera, el final del ZIP, su directorio central y una parte de hasta 256 KiB, más un `copy_object` que copia dentro del almacén sin pasar por el servidor. La única espera que provoca es la de otra confirmación del **mismo** archivo. `TC-18` prueba que la segunda espera y después responde `200` sin segundo asiento.

**Vencimiento del bloqueo.** `CLAUDE.md` fija que el vencimiento de un bloqueo es `CONCURRENCIA`, igual que en TKT-017. `confirmar_archivo` envuelve la transacción principal en `try/except DBAPIError as error` y lee `getattr(error.orig, "sqlstate", None)`: con `55P03` lanza `ConcurrenciaVencida(codigo="BLOQUEO_VENCIDO", mensaje="Otra operación está confirmando este archivo en este momento. Vuelve a intentarlo.", espera_maxima_ms=5000, reintentar_en_s=1, acciones=[Accion("REINTENTAR", "POST", f"/api/v1/archivos/{archivo_id}/confirmacion", ("DIRECTOR_PROYECTOS",))])`; con `57014`, lo mismo con `codigo="TIEMPO_EJECUCION_VENCIDO"` y `espera_maxima_ms=15000`; con cualquier otro, relanza el error original. `5000` y `15000` son el `lock_timeout` y el `statement_timeout` del rol de aplicación en `v0001`. La traducción vive en `aplicacion/confirmacion.py` y no reutiliza la de `presupuesto`, que `archivos` no puede importar. `TC-18b` la prueba y `M-19` la quita.

**Reescritura del tipo y suma del objeto.** Un `copy_object` con `MetadataDirective="REPLACE"` puede crear el objeto copiado sin `ChecksumSHA256`. Con el orden A, si la reescritura ocurre y la transacción después no confirma, la fila sigue `PENDIENTE` sobre un objeto sin suma, y una segunda confirmación respondería `ARCHIVO_HASH_DISTINTO` por suma ausente (`P-11`) aunque el contenido sea el declarado. Quien ejecuta la fila 12a aplica, sin volver a decidir, el primer caso que `E-1` (g) haya registrado:

| Resultado de `E-1` (g) | Decisión |
|---|---|
| (g1) Tras `copy_object` con `REPLACE`, `head_object(ChecksumMode="ENABLED")` devuelve la misma suma | Orden A tal cual |
| (g2) La suma se pierde con (g1), pero se conserva añadiendo `ChecksumAlgorithm="SHA256"` a la copia | Orden A, y `reescribir_tipo` pasa `ChecksumAlgorithm="SHA256"` |
| (g3) Ninguna variante conserva la suma | Orden **B**: dentro del bloque, `marcar_disponible` y `asentar`; el bloque confirma; **después**, fuera de la transacción, `reescribir_tipo`. La reescritura es idempotente (copia el mismo objeto con el mismo tipo), y el paso 3 (`YA_DISPONIBLE`) también la ejecuta antes de devolver `200`, para que un fallo del almacén tras confirmar se repare al confirmar otra vez. En ese caso `TC-15` comprueba que `metadatos` no se llamó la segunda vez y que `reescribir_tipo` sí; con el hash ya guardado en la fila, la suma del objeto deja de ser necesaria |

No hay caso en que la ejecución tenga que escalar por esto: el orden B no depende del almacén. `impl.md` anota qué caso aplicó.

**Bitácora del paso 11.** `asentar(sesion_bd, accion="CONFIRMAR", entidad_tipo="archivo", entidad_id=archivo_id, usuario_id=usuario_id, ocurrido_en=ahora, obra_id=fila.obra_id, datos_despues={"hash_sha256": …, "tamano_bytes": …, "tipo_mime": …, "referencia_tipo": …, "referencia_id": str(…)})`; si `referencia_id` es nulo, la clave se omite. Sin `regla_negocio`, sin `motivo`. El caso de uso importa `from cimenta.auditoria import interfaz as auditoria` y llama `auditoria.asentar(...)`, para que `TC-16` lo sustituya con `monkeypatch`.

**Denegación (`NO_ES_SOLICITANTE`).** Igual que `registrar_denegacion` de `identidad`: `with contexto.fabrica_sesiones().begin() as s: auditoria.asentar_denegacion(s, usuario_id=usuario_id, ocurrido_en=ahora, motivo="NO_ES_SOLICITANTE", datos={"metodo": "POST", "ruta": f"/api/v1/archivos/{archivo_id}/confirmacion", "roles_requeridos": ["DIRECTOR_PROYECTOS"]})`, dentro de `try/except Exception` que registra `denegacion_no_asentada` con `structlog` (sin el mensaje de la excepción) y sigue. Después, `PermisoDenegado(motivo="NO_ES_SOLICITANTE", mensaje="Solo quien subió el archivo puede confirmarlo.", roles_requeridos=())`.

### Mensajes y detalles exactos

| Rechazo | `mensaje` | `detalle` | `acciones` |
|---|---|---|---|
| `ARCHIVO_NO_SUBIDO` | «El archivo no llegó al almacén. Vuelve a cargarlo antes de confirmar.» | `archivo_id` | — |
| `ARCHIVO_TAMANO_DISTINTO` | «El archivo almacenado no tiene el tamaño que se declaró al iniciar la subida. Vuelve a cargar el archivo.» | `tamano_declarado`, `tamano_almacenado` (enteros) | — |
| `ARCHIVO_HASH_DISTINTO` | «El archivo almacenado no coincide con el que se declaró al iniciar la subida. Vuelve a cargar el archivo.» | `hash_declarado`, `hash_almacenado` (hexadecimal; **se omite** si el almacén no informa la suma), `tamano_declarado`, `tamano_almacenado` | — |
| `ARCHIVO_TIPO_NO_PERMITIDO` | «El tipo del archivo, leído de su contenido, no está permitido.» | `tipo_detectado` (cadena), `tipos_admitidos` (lista de los ocho, en el orden de la tabla) | — |
| `ARCHIVO_CADUCADO` al confirmar | «La subida del archivo caducó. Vuelve a cargar el archivo.» | `archivo_id`, `estado_archivo` `"CADUCADO"` | — |
| `ESTADO_NO_PERMITE_OPERACION` al confirmar | «El archivo está anulado y no se confirma.» | `archivo_id`, `estado_archivo` | — |
| `ARCHIVO_NO_DISPONIBLE` al descargar | «El archivo todavía no está disponible.» | `archivo_id`, `estado_archivo` (`PENDIENTE` o `ANULADO`) | — |
| `ARCHIVO_CADUCADO` al descargar | «La subida del archivo caducó y no se puede descargar.» | `archivo_id`, `estado_archivo` `"CADUCADO"` | — |
| `NoEncontrado` | «El archivo no existe.» | `recurso` `"archivo"` | — |

### Detección del tipo por los bytes

`detectar_tipo(leer_rango: Callable[[int, int], bytes], tamano: int) -> str`, en `infraestructura/detector_tipo.py`. `leer_rango(inicio, fin)` devuelve los bytes `inicio..fin` **inclusivos**. Devuelve un tipo MIME; el caso de uso decide si se admite. Constantes: `CABECERA = 8192`, `COLA_ZIP = 65557` (22 de la cola del directorio más 65535 de comentario), `MAXIMO_DIRECTORIO = 1048576`, `MAXIMO_PARTE = 262144`.

1. `cabecera = leer_rango(0, min(tamano, CABECERA) - 1)`.
2. **ZIP** (`cabecera` empieza por `PK\x03\x04`): `cola = leer_rango(max(0, tamano - COLA_ZIP), tamano - 1)`; busca desde el final la firma `PK\x05\x06`; sin ella, o con `0xFFFF`/`0xFFFFFFFF` en número de entradas, tamaño o posición del directorio (ZIP64), o con el directorio mayor que `MAXIMO_DIRECTORIO` → `"application/zip"`. Lee el directorio con un rango, recorre sus entradas (`PK\x01\x02`) y busca la de nombre `[Content_Types].xml`; sin ella → `"application/zip"`. Lee la cabecera local (30 bytes más nombre y extra) y los datos comprimidos con rangos; tamaño comprimido mayor que `MAXIMO_PARTE`, método distinto de 0 o 8, o descompresión mayor que `MAXIMO_PARTE` (`zlib.decompressobj(-15).decompress(datos, MAXIMO_PARTE + 1)`) → `"application/zip"`. Analiza la parte con `defusedxml.ElementTree.fromstring(parte, forbid_dtd=True)`; si algún `Override` tiene `ContentType == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"` → el tipo `.xlsx`; si no, `"application/zip"`. Un `.xlsm` (parte `application/vnd.ms-excel.sheet.macroEnabled.main+xml`) cae en `"application/zip"`.
3. **XML** (`cabecera` sin BOM UTF-8 y sin blancos iniciales empieza por `<`): `DefusedXMLParser(target=_PrimeraEtiqueta(), forbid_dtd=True, forbid_entities=True, forbid_external=True)` y `parser.feed(cabecera)`, **sin** `close()`. `DTDForbidden`, `EntitiesForbidden` o `ExternalReferenceForbidden` → `"application/xml-dtd"` (`P-9`). Si la primera etiqueta tiene nombre local `svg` → `"image/svg+xml"`. Si hubo primera etiqueta → `"application/xml"`. `ParseError` antes de la primera etiqueta → `"text/plain"`. `_PrimeraEtiqueta` guarda el nombre de la primera llamada a `start` e ignora las demás.
4. **Firma** con `puremagic.magic_string(cabecera)` (un RIFF sin `WEBP` en los bytes 8 a 12 es `application/octet-stream`): se recorre la lista ordenada y se recorren solo las candidatas de **máxima confianza** y se toma la **primera** cuya `extension` esté en `EXTENSIONES` = `{".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heic", ".mp4": "video/mp4", ".pdf": "application/pdf"}` y se devuelve su tipo; si ninguna está, la primera candidata con `mime_type` no vacío da su `mime_type`; si no hay candidatas, o `PureError`/`PureValueError` → `"application/octet-stream"`. `E-3` fija la tabla definitiva: si `puremagic` no reconoce alguno de los seis tipos binarios de la lista, la fila 6 añade **antes** de `puremagic` una comprobación de firma propia para ese tipo (JPEG `FF D8 FF`; PNG `89 50 4E 47 0D 0A 1A 0A`; WebP `RIFF` + `WEBP` en 8; HEIC `ftyp` en 4 con marca `heic`, `heix`, `mif1` o `msf1`; MP4 `ftyp` en 4 con cualquier otra marca; PDF `%PDF-`).

La suma de bytes que lee la confirmación de un `.xlsx` queda acotada por `CABECERA + COLA_ZIP + MAXIMO_DIRECTORIO + 30 + 65535 + MAXIMO_PARTE`, y en un libro real son unos 74 KB (`E-2`), y en el peor caso unos 1,3 MiB. `TC-17` fija la cota de la prueba en **262144 bytes** para un `.xlsx` de 26,000,000 bytes.

### Puerto y adaptador del almacén

`aplicacion/puertos.py`:

```python
class AlmacenObjetos(Protocol):
    def url_subida(self, clave: str, *, tamano_bytes: int, sha256_hex: str, vida: timedelta) -> UrlFirmada: ...
    def metadatos(self, clave: str) -> ObjetoAlmacenado | None: ...
    def leer_rango(self, clave: str, inicio: int, fin: int) -> bytes: ...
    def leer_todo(self, clave: str) -> bytes: ...
    def reescribir_tipo(self, clave: str, tipo_mime: str) -> None: ...
    def url_lectura(self, clave: str, *, vida: timedelta, tipo_mime: str, nombre_original: str, disposicion: str) -> str: ...
```

`UrlFirmada(url: str, cabeceras: dict[str, str])` es un `dataclass` congelado de `aplicacion/puertos.py`; `ObjetoAlmacenado(tamano_bytes: int, sha256_hex: str | None)` es de `dominio/confirmacion.py`.

`infraestructura/almacen_s3.py` · `AlmacenS3(cliente: S3Client, firmante: S3Client, bucket: str)` y `crear_almacen_s3(*, endpoint: str | None, origen: str, bucket: str, clave_acceso: str, clave_secreta: str) -> AlmacenS3`, que construye dos clientes con `boto3.client("s3", endpoint_url=…, region_name="us-east-1", aws_access_key_id=…, aws_secret_access_key=…, config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, request_checksum_calculation="when_required", response_checksum_validation="when_required", connect_timeout=5, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}))`: `cliente` con `endpoint_url = endpoint if endpoint is not None else origen`, para `head_object`, `get_object` y `copy_object`; y `firmante` con `endpoint_url = origen`, que **solo** se usa en `generate_presigned_url`. `url_subida` y `url_lectura` llaman a `self._firmante`; `metadatos`, `leer_rango`, `leer_todo` y `reescribir_tipo`, a `self._cliente`. Cuando `endpoint` falta o es igual a `origen`, los dos clientes apuntan al mismo sitio y el comportamiento es el de un solo cliente. Ninguna cadena del archivo nombra un destino concreto (`TC-08` lo comprueba). `S3Client` viene de `boto3-stubs`, que es dependencia de desarrollo: se importa solo bajo `if TYPE_CHECKING: from mypy_boto3_s3 import S3Client`, con `from __future__ import annotations`, para que el código de producción no lo necesite en tiempo de ejecución.

| Método | Llamada | Notas |
|---|---|---|
| `url_subida` | `generate_presigned_url("put_object", Params={"Bucket", "Key", "ContentLength": tamano_bytes, "ChecksumSHA256": base64(bytes.fromhex(sha256_hex))}, ExpiresIn=int(vida.total_seconds()), HttpMethod="PUT")` | `cabeceras`: `{"x-amz-checksum-sha256": <base64>}` si `E-1` muestra esa cabecera en `X-Amz-SignedHeaders`; si `E-1` muestra que `boto3` la llevó a la cadena de consulta, `{}`. `Content-Length` no se devuelve: el navegador la fija y no la deja fijar a JavaScript |
| `metadatos` | `head_object(Bucket, Key, ChecksumMode="ENABLED")` | `ClientError` con código `404`, `NoSuchKey` o `NotFound` → `None`; `ChecksumSHA256` ausente → `sha256_hex=None`; presente → `base64.b64decode(...).hex()` |
| `leer_rango` | `get_object(Bucket, Key, Range=f"bytes={inicio}-{fin}")["Body"].read()` | |
| `leer_todo` | `get_object(Bucket, Key)["Body"].read()` | Solo lo usa el lector del ejecutor, nunca una ruta |
| `reescribir_tipo` | `copy_object(Bucket, Key, CopySource={"Bucket", "Key"}, MetadataDirective="REPLACE", ContentType=tipo_mime)` | Copia dentro del almacén |
| `url_lectura` | `generate_presigned_url("get_object", Params={"Bucket", "Key", "ResponseContentType": tipo_mime, "ResponseContentDisposition": _disposicion(...)}, ExpiresIn=…)` | `_disposicion` = `f'{disposicion}; filename="{ascii}"; filename*=UTF-8\'\'{quote(nombre_original, safe="")}'`, con `ascii` = el nombre con todo carácter fuera de `0x20`–`0x7E`, `"` y `\` cambiado por `_` |

La clave del objeto la genera el alta: `f"{obra_id}/{archivo_id}"`. No contiene el nombre original.

### Ajustes y variables

`AjustesServidor` gana diez campos. Todos se leen con el prefijo `CIMENTA_`.

| Variable | Campo | Tipo y omisión | Validación | Obligatoria |
|---|---|---|---|---|
| `CIMENTA_ALMACEN_ORIGEN` | `almacen_origen` | `str \| None = None` (ya existe) | `PATRON_ORIGEN` (ya existe). Origen **público**: con él se firman las URL de subida y de lectura, y es el origen de la política de contenido | Con base |
| `CIMENTA_ALMACEN_ENDPOINT` | `almacen_endpoint` | `str \| None = None`; si falta, el adaptador usa `almacen_origen` | `PATRON_ENDPOINT = r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?"`: http o https, sin ruta, y el host puede ser un nombre interno (`http://minio:9000`), a diferencia del origen. Mensaje: «debe ser una URL http o https sin ruta» | No |
| `CIMENTA_ALMACEN_BUCKET` | `almacen_bucket` | `str \| None = None` | `^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$` | Con base |
| `CIMENTA_ALMACEN_CLAVE_ACCESO` | `almacen_clave_acceso` | `str \| None = None` | — | Con base |
| `CIMENTA_ALMACEN_CLAVE_SECRETA` | `almacen_clave_secreta` | `SecretStr \| None = None` | — | Con base |
| `CIMENTA_ARCHIVOS_VIDA_URL_SUBIDA` | `archivos_vida_url_subida` | `int = 900` (segundos) | 60 a 3600 | No |
| `CIMENTA_ARCHIVOS_VIDA_URL_LECTURA` | `archivos_vida_url_lectura` | `int = 300` | 60 a 3600 | No |
| `CIMENTA_ARCHIVOS_UMBRAL_PENDIENTE` | `archivos_umbral_pendiente` | `int = 86400` | Mayor que `archivos_vida_url_subida`, con el validador tolerante de `trabajos_umbral_vencimiento` (si la vida ya falló, no compara) | No |
| `CIMENTA_ARCHIVOS_LIMITE_IMAGEN_BYTES` | `archivos_limite_imagen_bytes` | `int = 15728640` | ≥ 1 | No |
| `CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES` | `archivos_limite_video_bytes` | `int = 52428800` | ≥ 1 | No |
| `CIMENTA_ARCHIVOS_LIMITE_DOCUMENTO_BYTES` | `archivos_limite_documento_bytes` | `int = 26214400` | ≥ 1 | No |

Los mensajes de los validadores siguen el patrón actual: «debe estar entre 60 y 3600 segundos», «debe ser mayor que la vida de la URL de subida», «debe ser al menos 1». `_mensaje` ya nombra la variable y nunca el valor.

**«Con base».** `cargar_ajustes` tiene dos retornos (líneas 103 a 118 de `ajustes.py`: el de `entorno is None`, que construye `AjustesServidor()`, y el del mapa, que construye `_AjustesDesdeMapa`). Los dos pasan por `_exigir_almacen_con_base(ajustes, entorno_efectivo)` antes de devolver, donde `entorno_efectivo` es el mapa recibido o `os.environ` si es `None`: si `variables_de_base_presentes(entorno_efectivo)` y alguno de los cuatro campos obligatorios del almacén (`almacen_origen`, `almacen_bucket`, `almacen_clave_acceso`, `almacen_clave_secreta`; `almacen_endpoint` no) es `None`, lanza `ConfiguracionInvalida` (sin `from`, porque no hay excepción que encadenar) con la lista ordenada de las variables que faltan. El texto lo arma una ayuda nueva, `_mensaje_de_variables(variables: Iterable[str]) -> str`, que devuelve «Configuración incompleta o inválida: {variables separadas por coma}. Defínelas en el entorno; las claves están en .env.example.»; `_mensaje(error: ValidationError)` pasa a llamarla con los nombres que saca de `error.errors()`, de modo que los dos errores tienen el mismo texto. Sin variables de base, nada cambia: `CA-R4` de TKT-006, ADR-037 §5 y TC-51 siguen igual. `servidor/ajustes.py` importa `variables_de_base_presentes` de `herramientas.conexion`.

**TC-51 no cambia**: su mapa no tiene variables de base. **TC-52 sí**, en dos puntos: el conjunto exacto de `model_fields` pasa de cuatro a catorce campos, y la aserción `not any("migracion" in campo or "lectura" in campo …)` se pondría en rojo, porque `archivos_vida_url_lectura` contiene «lectura». El ajuste restringe esa aserción a los campos que empiezan por `db_`, que es lo que TC-52 protege (RNF-09: el servidor no recibe las contraseñas de migración ni de lectura).

Pruebas existentes que el ticket ajusta, todas por el tester de la fila indicada. Los identificadores de otros tickets llevan su prefijo para no confundirlos con los de este plan: `TKT-057/TC-52` de `test_tkt057_arranque.py` (fila 8); `TKT-072/TC-20` y `TKT-072/TC-21` de `test_tkt072_migracion.py` (fila 2); `CUERPOS_VALIDOS` de `test_tkt057_csrf.py` (líneas 1265 a 1270), que hace fallar `TKT-057/TC-48` ante una ruta que muta sin entrada, gana `"POST /api/v1/archivos/{archivo_id}/confirmacion": PeticionValida(ruta=f"/api/v1/archivos/{uuid.uuid4()}/confirmacion")`, sin cuerpo (fila 12a); y, si la fila 11 publica algo en `identidad`, la aserción de `test_tkt006_enrutador.py` (líneas 741 a 771) que fija `set(cimenta.identidad.interfaz.__all__)` a siete nombres, que pasa a incluir los que la fila 11 añada (fila 11).

**`.env.example`**, sección «Almacén de objetos · TKT-059», con estas claves **activas**. Entra en la fila 1a, porque la documentación de 059a ya enseña a arrancar MinIO con ellas; es inocua hasta la fila 8, porque `AjustesServidor` ignora las claves que no conoce (`extra="ignore"`) y la obligatoriedad no existe hasta entonces:

```text
CIMENTA_ALMACEN_ORIGEN=http://localhost:9000
CIMENTA_ALMACEN_BUCKET=cimenta
CIMENTA_ALMACEN_CLAVE_ACCESO=cimenta-local
CIMENTA_ALMACEN_CLAVE_SECRETA=
CIMENTA_SPA_ORIGEN=http://localhost:5173
# CIMENTA_ALMACEN_ENDPOINT=   # sin valor: vale CIMENTA_ALMACEN_ORIGEN; en la VPS, la red interna (http://minio:9000)
```

`CIMENTA_SPA_ORIGEN` (`P-15`) es el origen desde el que el navegador sube y lee; en local, el de Vite (`frontend/vite.config.ts`, puerto 5173). La consume la configuración de CORS que fije `E-5`, nunca `AjustesServidor`. La línea comentada `# CIMENTA_ALMACEN_ORIGEN=` de la sección de TKT-057 se sustituye por un comentario que remite a la nueva sección (`problemas_de_la_seccion_de_tkt057` acepta la clave activa). La clave secreta va sin valor, como las contraseñas de los roles; un comentario indica generarla con `python -c "import secrets; print(secrets.token_urlsafe(24))"` y que MinIO exige al menos 8 caracteres. Las seis variables `CIMENTA_ARCHIVOS_*` van comentadas con su omisión, como las de TKT-015b.

**`compose.yaml`**, servicio `minio`, con la forma que recomienda `P-14` (perfil `almacen` y `:?` en las credenciales) y sujeta a `E-4`:

```yaml
  minio:
    image: minio/minio:<etiqueta RELEASE fijada en E-0>
    profiles: ["almacen"]
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${CIMENTA_ALMACEN_CLAVE_ACCESO:?define CIMENTA_ALMACEN_CLAVE_ACCESO en .env}
      MINIO_ROOT_PASSWORD: ${CIMENTA_ALMACEN_CLAVE_SECRETA:?define CIMENTA_ALMACEN_CLAVE_SECRETA en .env}
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
    volumes:
      - minio_datos:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 12
```

y `minio_datos:` en `volumes:`. El comentario de cabecera pasa a nombrar los dos servicios y el perfil.

**CORS del almacén (`CA-14`).** Lo que se aplica depende de `E-5`, con esta tabla cerrada:

| Resultado de `E-5` | Dónde se aplica | Qué se aplica |
|---|---|---|
| (c1) MinIO acepta `put_bucket_cors` y lo respeta en el preflight | `herramientas/almacen_local.py`, después de crear el bucket (idempotente: `put_bucket_cors` en cada ejecución) | Una regla: `AllowedOrigins=[CIMENTA_SPA_ORIGEN]`, `AllowedMethods=["PUT", "GET", "HEAD"]`, `AllowedHeaders=["content-type", "x-amz-checksum-sha256"]`, `ExposeHeaders=["ETag"]`, `MaxAgeSeconds=600`. La herramienta termina con código 2 nombrando `CIMENTA_SPA_ORIGEN` si falta. Las pruebas aplican la misma regla al bucket de pruebas con una función pública de la herramienta, `aplicar_cors(cliente, bucket, origen_spa)` |
| (c2) MinIO responde `NotImplemented` a `put_bucket_cors`, o lo acepta pero no lo aplica, y respeta `MINIO_API_CORS_ALLOW_ORIGIN` | El servicio `minio` de `compose.yaml` y el contenedor de pruebas | `MINIO_API_CORS_ALLOW_ORIGIN: ${CIMENTA_SPA_ORIGEN:-http://localhost:5173}` en `environment:`; en `conftest.py`, `contenedor_minio` recibe la misma variable con un origen de prueba fijo, `http://spa.prueba.test` |
| (c3) Ninguno de los dos restringe el origen | — | `/sdd-escalar` antes de la fila 1a: `CA-14` no se puede cumplir con MinIO |

En la VPS, el CORS lo configura TKT-073.

**Por qué el perfil (`P-14`).** Compose interpola el archivo entero antes de elegir servicios. Con `${…:?}` en `minio` y sin perfil, `docker compose … up -d --wait db` fallaría en tres sitios que no traen las variables del almacén: los entornos `test` y `prod` de la VPS ([guía](../../../docs/despliegue-prueba-vps.md), pasos 7 y 5, con un `.env` que solo tiene la base), y el `.env` local de quien lo creó antes de este ticket. Además, los proyectos `cimenta-prod` y `cimenta-test` levantarían dos MinIO que chocarían en `127.0.0.1:9000` y `9001`. Con `profiles: ["almacen"]`, `up -d db` no arranca `minio`, y `docker compose up -d minio` lo sigue arrancando porque Compose activa el perfil de un servicio nombrado en la orden. Falta comprobar que un servicio de un perfil inactivo no hace fallar la interpolación de sus `:?`: es `E-4`. Si `E-4` muestra que sí falla, la fila 1a sustituye `:?` por `:-` en las dos variables del servicio y `herramientas/almacen_local.py` comprueba antes de crear el bucket que las dos estén definidas y que la secreta tenga al menos 8 caracteres, terminando con código 2 si no. `despliegue/compose.vps.yaml` no cambia en ningún caso: MinIO en la VPS es de TKT-073. El bucket local lo crea `uv run --env-file ../.env python -m herramientas.almacen_local` (`P-6`): con `boto3`, `head_bucket` y, si responde `404`, `create_bucket`; se niega, con código de salida 2 y un mensaje que nombra la variable, si el host de `CIMENTA_ALMACEN_ORIGEN` no es `localhost` ni `127.0.0.1`.

**Trabajo `humo`** de `ci.yml`, paso «Preparar el entorno con contraseñas de prueba generadas», también en la fila 1a, en el mismo cambio que añade la clave vacía a `.env.example`:

```bash
grep -v -e '^CIMENTA_DB_CONTRASENA_' -e '^CIMENTA_ALMACEN_CLAVE_SECRETA=' .env.example > .env
for rol in MIGRACION APLICACION LECTURA; do
  echo "CIMENTA_DB_CONTRASENA_${rol}=$(openssl rand -hex 24)" >> .env
done
echo "CIMENTA_ALMACEN_CLAVE_SECRETA=$(openssl rand -hex 24)" >> .env
```

Sin servicio de MinIO en `humo` (`P-7`): con estas variables la aplicación arranca, el barrido de archivos no toca el almacén y ningún recorrido de humo sube un archivo. `docker compose up -d --wait db` sigue igual; la interpolación de `compose.yaml` encuentra las dos variables del servicio `minio` en el `.env` generado.

### Composición en `servidor/fabrica.py`

`crear_aplicacion(..., almacen: AlmacenObjetos | None = None)`. Después de `cargar_ajustes`:

`servidor/fabrica.py` solo importa `cimenta.archivos.interfaz` y, desde la fila 12a, `cimenta.archivos.api.montaje`. Por eso la fila 8 crea `interfaz.py` con lo que la fábrica necesita en ese momento: `AlmacenNoConfigurado`, `AlmacenObjetos`, `ConfiguracionArchivos`, `LimitesArchivo`, `ContextoArchivos`, `construir_contexto` y `crear_almacen_s3`. Las filas siguientes añaden lo suyo.

1. `proveedor_almacen`: `lambda: almacen` si se inyectó; si no, `functools.cache` de una función que llama a `crear_almacen_s3(endpoint=ajustes.almacen_endpoint, origen=…, bucket=…, clave_acceso=…, clave_secreta=…)` y lanza `AlmacenNoConfigurado("el almacén de objetos no está configurado")` si alguno de los cuatro obligatorios es `None`. `AlmacenNoConfigurado` es un `RuntimeError` declarado en `aplicacion/contexto.py` y publicado en la interfaz. Construir la aplicación no crea el cliente.
2. `configuracion_archivos = ConfiguracionArchivos(vida_url_subida=timedelta(seconds=…), vida_url_lectura=…, umbral_pendiente=…, limites=LimitesArchivo(…))`.
3. Fila 8: `aplicacion.state.archivos = construir_contexto(proveedor_motor=proveedor_motor, proveedor_almacen=proveedor_almacen, configuracion=configuracion_archivos, reloj=reloj)`, después de `montar_identidad`, sin enrutador. Fila 12a: esa línea se sustituye por `montar_archivos(aplicacion, proveedor_motor=…, proveedor_almacen=…, configuracion=…, reloj=…)`, que hace lo mismo e incluye el enrutador.
4. En el `lifespan`, con base: la lista de `barrer_todas` es `[definicion_barrido_importacion(…), definicion_barrido_archivo(timedelta(seconds=ajustes.archivos_umbral_pendiente))]`, en ese orden; y `leer_contenido` es `leer_contenido_archivo` si se pasó, si no `crear_lector_contenido(aplicacion.state.archivos)`. `leer_contenido_no_configurado` deja de importarse en la fábrica; sigue publicada en `presupuesto` (no se toca ese módulo).
5. El docstring del módulo nombra `cimenta.archivos.api.montaje` y el barrido de archivos.

### Lector del contenido

`crear_lector_contenido(contexto: ContextoArchivos) -> Callable[[UUID], bytes]`. La función devuelta abre `with contexto.fabrica_sesiones().begin()`, lee la fila sin bloqueo y, si no existe o no está `DISPONIBLE`, lanza `ArchivoNoLegible(f"el archivo {archivo_id} no está DISPONIBLE")` (un `RuntimeError` publicado) **sin** llamar al almacén; si está `DISPONIBLE`, devuelve `contexto.almacen().leer_todo(fila.clave_objeto)`. Corre en el hilo coordinador del ejecutor, fuera de cualquier ruta.

### Barrido

`definicion_barrido_archivo(umbral: timedelta) -> DefinicionBarrido(nombre="archivo", tabla="archivo", estado_intermedio="PENDIENTE", estado_vencido="CADUCADO", columna_marca="creado_en", umbral=umbral, al_vencer=_sin_efecto)`, con `_sin_efecto(sesion_bd, identificadores) -> None` que no hace nada. El barrido compara con `now()` del motor; la confirmación, con el reloj del contexto. En producción son el mismo reloj; en las pruebas de arranque las filas se siembran con `creado_en` relativo a `now()`.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `cimenta/archivos/dominio/tipos.py` | `CategoriaArchivo(StrEnum)`: `IMAGEN`, `VIDEO`, `DOCUMENTO`. `TIPO_XLSX: Final[str]`. `TIPOS_ADMITIDOS: Final[tuple[tuple[str, CategoriaArchivo], ...]]` con la tabla de arriba. `tipos_admitidos() -> tuple[str, ...]`, `categoria_de(tipo_mime: str) -> CategoriaArchivo \| None`, `tipo_admitido(tipo_mime: str) -> bool`, `disposicion_de(tipo_mime: str) -> Literal["inline", "attachment"]` (`inline` solo para `IMAGEN` y `VIDEO`) | `RNF-06`, ADR-016 reglas 3 y 4 |
| `cimenta/archivos/dominio/declaracion.py` | `LimitesArchivo`, `DefectoDeclaracion`, `evaluar_declaracion`, según «Límites y forma de la declaración» | `RNF-06`, `PA-15` |
| `cimenta/archivos/dominio/confirmacion.py` | `Ordenable(Protocol)` con `__lt__`, como en `identidad/dominio/vigencia.py`. `EstadoArchivo(StrEnum)`: `PENDIENTE`, `DISPONIBLE`, `CADUCADO`, `ANULADO`. `PasoPrevio(StrEnum)`: `NO_ES_SOLICITANTE`, `YA_DISPONIBLE`, `CADUCADO`, `NO_CONFIRMABLE`, `VENCIDO`, `CONFIRMABLE`. `evaluar_previa[T: Ordenable]`. `ObjetoAlmacenado`. `Discrepancia(StrEnum)`: `NO_SUBIDO`, `TAMANO_DISTINTO`, `HASH_DISTINTO`. `comparar_objeto` | `RNF-06`, `RNF-19`, `PA-T59.8`, `PA-T59.13` |

Ningún archivo de `dominio/` importa `datetime` (regla 2 de `CLAUDE.md`, ADR-021): el instante y el vencimiento llegan como argumentos genéricos. `tipos.py` y `declaracion.py` solo manejan cadenas y enteros, y `confirmacion.py` usa `uuid.UUID`, que no es E/S ni reloj.

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `aplicacion/puertos.py` | `AlmacenObjetos`, `UrlFirmada` | — |
| `aplicacion/contexto.py` | `AlmacenNoConfigurado(RuntimeError)`; `ConfiguracionArchivos(vida_url_subida: timedelta, vida_url_lectura: timedelta, umbral_pendiente: timedelta, limites: LimitesArchivo)`; `ContextoArchivos(fabrica_sesiones: Callable[[], sessionmaker[Session]], almacen: Callable[[], AlmacenObjetos], configuracion: ConfiguracionArchivos, reloj: Callable[[], datetime])`; `construir_contexto(*, proveedor_motor, proveedor_almacen, configuracion, reloj) -> ContextoArchivos`, con la fábrica en `functools.cache` y `datetime.now(UTC)` por omisión | — |
| `aplicacion/alta.py` | `registrar_archivo(contexto: ContextoArchivos, sesion_bd: Session, *, obra_id: UUID, referencia_tipo: str, referencia_id: UUID \| None, nombre_original: str, tamano_bytes: int, hash_sha256: str, tipo_declarado: str, usuario_id: UUID, campo_raiz: str = "archivo") -> AltaArchivo`. `AltaArchivo(archivo_id: UUID, url: str, metodo: Literal["PUT"], cabeceras: dict[str, str], expira_en: datetime)`. Orden: `evaluar_declaracion` (defectos → `ValidacionRechazada`, sin escribir ni firmar); `archivo_id = uuid4()`; clave; `repositorio.insertar(...)` con `creado_en = contexto.reloj()`; `contexto.almacen().url_subida(...)`; `expira_en = ahora + vida_url_subida` | En la sesión **de quien llama**; no abre ni confirma transacción. Si quien llama deshace, la fila no queda |
| `aplicacion/confirmacion.py` | `confirmar_archivo` y `ArchivoLeido` (los campos de la fila más `subido_por_nombre: str`) | Una transacción principal con `FOR UPDATE`; una propia para el `DENEGAR`. Llama al repositorio y a la auditoría por atributo del módulo |
| `aplicacion/consulta.py` | `obtener_archivo(contexto, *, archivo_id) -> ArchivoLeido` y `emitir_url_descarga(contexto, *, archivo_id) -> UrlDescargaEmitida(url, expira_en, tipo_mime, nombre_original, disposicion)`. La descarga: `PENDIENTE` o `ANULADO` → `ARCHIVO_NO_DISPONIBLE`; `CADUCADO` → `ARCHIVO_CADUCADO`; `DISPONIBLE` → `url_lectura` con `vida_url_lectura`, `disposicion_de(tipo_mime)` y `expira_en = reloj() + vida` | Una transacción de lectura, sin bloqueo. El nombre de quien subió sale de `nombres_de_usuarios` en esa misma sesión |
| `aplicacion/lectura.py` | `crear_lector_contenido`, `ArchivoNoLegible` | Una transacción de lectura por llamada |
| `aplicacion/barrido.py` | `definicion_barrido_archivo` | La abre `barrer_todas` |
| `interfaz.py` | Nace en la fila 8. Al final exporta `AlmacenNoConfigurado`, `AlmacenObjetos`, `AltaArchivo`, `ArchivoNoLegible`, `ConfiguracionArchivos`, `ContextoArchivos`, `LimitesArchivo`, `construir_contexto`, `contexto_de_archivos`, `crear_almacen_s3`, `crear_lector_contenido`, `definicion_barrido_archivo`, `registrar_archivo`. `contexto_de_archivos(request: Request) -> ContextoArchivos` vive en `api/dependencias.py` y lee `request.app.state.archivos`: es lo que TKT-018 inyecta en su ruta para llamar a `registrar_archivo` | — |

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `archivo` | tabla | `id uuid`, `obra_id uuid NOT NULL`, `referencia_tipo text NOT NULL`, `referencia_id uuid NULL`, `estado text NOT NULL DEFAULT 'PENDIENTE'`, `clave_objeto text NOT NULL`, `nombre_original text NOT NULL`, `tipo_mime text NULL`, `tamano_bytes bigint NULL`, `hash_sha256 char(64) NULL`, `subido_por_id uuid NOT NULL`, `creado_en timestamptz NOT NULL DEFAULT now()`, `confirmado_en timestamptz NULL`, `anulado_por_id uuid NULL`, `motivo_anulacion text NULL`, `anulado_en timestamptz NULL` |
| `pk_archivo` | restricción | `PRIMARY KEY (id)` |
| `fk_archivo_subido_por_id`, `fk_archivo_anulado_por_id` | restricción | Hacia `usuario(id)`. **Ninguna** clave foránea en `obra_id` ni en `referencia_id` |
| `uq_archivo_clave_objeto` | restricción | Invariante 25 |
| `ck_archivo_referencia_tipo` | restricción | `referencia_tipo IN ('AVANCE','ENTRADA_ALMACEN','MERMA','FACTURA_PROVEEDOR','IMPORTACION','OBRA')` |
| `ck_archivo_estado` | restricción | `estado IN ('PENDIENTE','DISPONIBLE','CADUCADO','ANULADO')` |
| `ck_archivo_disponible_verificado` | restricción | Invariante 23, la expresión del modelo de datos §13 |
| `ck_archivo_anulado_con_motivo` | restricción | Invariante 24 |
| `ck_archivo_referencia_obligatoria` | restricción | Invariante 26 |
| `ix_archivo_obra_id_estado_creado_en` | índice | `(obra_id, estado, creado_en DESC)` |
| `ix_archivo_referencia_tipo_referencia_id` | índice | `(referencia_tipo, referencia_id)` |
| `ix_archivo_creado_en_pendiente` | índice parcial | `(creado_en) WHERE estado = 'PENDIENTE'` |
| Privilegios | rol | `REVOKE DELETE ON archivo FROM cimenta_aplicacion`, que es el sostén de `PA-T59.10`. El resto, por los privilegios por omisión de `0001`, que no conceden `TRUNCATE`: el rol de aplicación conserva `SELECT`, `INSERT` y `UPDATE` (el `UPDATE` lo exige el `FOR UPDATE`); el de lectura, `SELECT` |
| `infraestructura/repositorio.py` | repositorio | Tabla Core `archivo` con las columnas que se usan. `FilaArchivo` (`dataclass` congelado con todas las columnas). `insertar(sesion_bd, *, id, obra_id, referencia_tipo, referencia_id, clave_objeto, nombre_original, tamano_bytes, hash_sha256, subido_por_id, creado_en) -> None`; `bloquear(sesion_bd, archivo_id) -> FilaArchivo \| None` (`with_for_update()`); `leer(sesion_bd, archivo_id) -> FilaArchivo \| None`; `marcar_disponible(sesion_bd, archivo_id, *, tipo_mime, confirmado_en) -> None`; `marcar_caducado(sesion_bd, archivo_id) -> None` |
| `infraestructura/almacen_s3.py` | adaptador | Según «Puerto y adaptador del almacén» |
| `infraestructura/detector_tipo.py` | adaptador | Según «Detección del tipo por los bytes» |

**Migración:** la siguiente libre al ejecutar la fila 2 (`P-1`), `revision = "00NN"`, `down_revision` = la cabeza que muestre `uv run alembic heads`, archivo `v00NN_archivos_archivo.py`, tuplas `_SUBIDA` y `_BAJADA` con una sentencia por `op.execute`. La bajada empieza con la guarda:

```sql
DO $guarda$
BEGIN
    LOCK TABLE archivo IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM archivo) THEN
        RAISE EXCEPTION USING MESSAGE =
            'La bajada de 00NN se niega: hay filas en archivo, y los objetos del almacén '
            'perderían su rastro. Respáldalas con pg_dump y retíralas fuera de esta migración.';
    END IF;
END
$guarda$
```

seguida de `DROP TABLE archivo` (que se lleva índices, restricciones y privilegios).

Reversible: sí, sin filas · destructiva: no · plan de reversa: `alembic downgrade <anterior>` con el rol de migración deja el catálogo idéntico al de la revisión anterior (`TC-03`); con filas se niega (`TC-04`).

### API

Operaciones del [borrador OpenAPI](../../../docs/api/openapi.yaml) con `TKT-059` en `x-tickets`, salvo `crear_importacion`, que es de TKT-018. Todas `def`, en `cimenta/archivos/api/rutas.py` con `APIRouter(prefix="/api/v1/archivos", tags=["archivos"])`; las fechas, con zona.

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `obtener_archivo` · `GET /api/v1/archivos/{archivo_id}` | `archivo_id: UUID` | `Archivo` | `200` · `401` · `403 PERMISO ROL_INSUFICIENTE` · `404 NO_ENCONTRADO` | `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS`; `dependencies=[Depends(exigir_rol(...))]` |
| `confirmar_archivo` · `POST /api/v1/archivos/{archivo_id}/confirmacion` | `archivo_id: UUID`; sin cuerpo | `Archivo` | `200` · `401` · `403 PERMISO ROL_INSUFICIENTE \| ORIGEN_NO_VERIFICADO \| NO_ES_SOLICITANTE` · `404` · `409 CONFLICTO ARCHIVO_NO_SUBIDO \| ARCHIVO_TAMANO_DISTINTO \| ARCHIVO_HASH_DISTINTO \| ARCHIVO_TIPO_NO_PERMITIDO \| ARCHIVO_CADUCADO \| ESTADO_NO_PERMITE_OPERACION` · `409 CONCURRENCIA BLOQUEO_VENCIDO \| TIEMPO_EJECUCION_VENCIDO` | `DIRECTOR_PROYECTOS`; `dependencies=[Depends(verificar_origen), Depends(exigir_rol("DIRECTOR_PROYECTOS"))]`; el `usuario_id` sale de `Annotated[UsuarioAutenticado, Depends(sesion_vigente)]` |
| `obtener_url_descarga_archivo` · `GET /api/v1/archivos/{archivo_id}/descarga` | `archivo_id: UUID` | `UrlDescarga` | `200` · `401` · `403 PERMISO ROL_INSUFICIENTE` · `404` · `409 CONFLICTO ARCHIVO_NO_DISPONIBLE \| ARCHIVO_CADUCADO` | Los dos roles de `obtener_archivo` |

**Esquemas** en `api/esquemas.py`, con los nombres de los componentes del borrador: `EstadoArchivo(StrEnum)` (los cuatro estados); `Archivo(BaseModel)` con `id: UUID`, `obra_id: UUID`, `referencia_tipo: Literal[…seis…]`, `referencia_id: UUID | None`, `estado: EstadoArchivo`, `nombre_original: str`, `tipo_mime: str | None`, `tamano_bytes: int`, `hash_sha256: str`, `subido_por: UsuarioResumen`, `creado_en: datetime`, `confirmado_en: datetime | None`; `UrlDescarga(BaseModel)` con `url: str`, `expira_en: datetime`, `tipo_mime: str`, `nombre_original: str`, `disposicion: Literal["inline", "attachment"]`. `UsuarioResumen` se importa de `cimenta.identidad.interfaz` (`P-5`). Ningún esquema tiene `clave_objeto`.

**Cambios del borrador OpenAPI**, por entrega:

- **Cambio del borrador en 059d** (fila 12a). `EstadoArchivo.enum` pasa a `[PENDIENTE, DISPONIBLE, CADUCADO, ANULADO]`, porque `api/esquemas.py` publica `EstadoArchivo` con los cuatro estados desde esa fila. `confirmar_archivo`: la descripción enumera `ARCHIVO_NO_SUBIDO` (objeto ausente), `ARCHIVO_CADUCADO` (fila `CADUCADO`, o `PENDIENTE` vencida que pasa a `CADUCADO` en la misma operación), `ESTADO_NO_PERMITE_OPERACION` (fila `ANULADO`), el `409` `CONCURRENCIA` y el `403` `NO_ES_SOLICITANTE` asentado `DENEGAR`. El ejemplo `tipo_no_permitido` cambia `tipo_declarado` por `tipos_admitidos` con la lista de ocho, y su `mensaje` por el de la tabla. Se añaden ejemplos `no_subido` y `caducado`. El ejemplo `hash_distinto` añade al mensaje «Vuelve a cargar el archivo.».
- **Cambio del borrador en 059e** (fila 14). El `409` de `obtener_url_descarga_archivo` deja de ser `$ref: Conflicto` genérico y nombra `ARCHIVO_NO_DISPONIBLE` y `ARCHIVO_CADUCADO` con un ejemplo cada uno. `obtener_url_descarga_archivo.x-escenarios` sigue vacío.

**Aviso para el tester.** `obtener_archivo` y `confirmar_archivo` citan `HDU-001 esc. 24` en `x-escenarios` (líneas 605 y 658 del borrador), pero ese escenario es de TKT-018. Ningún test de este ticket se llama `test_hdu001_esc24_…`: los del camino feliz se llaman `test_tkt059_…`.

Tras montar cada ruta, desde `frontend/`: `npm run tipos:generar` y se versiona `frontend/src/api/generado/servidor.ts`; `npm run tipos:verificar` en verde.

## Experimentos previos

Ninguno se ha ejecutado: todos están **(sin ejecutar)**. Los corre `tester-backend` en la fila 0, desde `backend/`, con Docker en marcha, **antes** de añadir ninguna dependencia: cada script se escribe en un directorio temporal fuera del repositorio y se ejecuta con dependencias efímeras, por ejemplo `uv run --with boto3 --with "testcontainers[minio]" --with puremagic --with openpyxl python -I <ruta>/e1_suma_firmada.py`. El script y su salida completa se pegan en `impl.md`.

| # | Afirmación | Cómo se comprueba | Qué se espera | Si falla |
|---|---|---|---|---|
| `E-0` | Existe una imagen de MinIO fijable | `docker pull minio/minio:<etiqueta>` con la etiqueta `RELEASE.*` más reciente publicada en Docker Hub; si `minio/minio` ya no publica, `quay.io/minio/minio` con la misma etiqueta | La imagen baja y `docker run --rm <imagen> --version` responde | Ninguna de las dos → `/sdd-escalar` antes de la fila 1a (sin almacén de pruebas no hay ticket) |
| `E-1` (`PA-T59.6`) | MinIO verifica la suma firmada y la devuelve | Con `MinioContainer(<imagen de E-0>)`, un bucket y el cliente configurado como en «Puerto y adaptador»: (a) `generate_presigned_url("put_object", Params={…, "ContentLength": n, "ChecksumSHA256": b64})`; imprimir la URL y su `X-Amz-SignedHeaders`. (b) `PUT` del contenido correcto con `x-amz-checksum-sha256: b64` (si la cabecera está firmada). (c) `PUT`, a otra clave firmada igual, de **otro contenido del mismo tamaño**. (d) `PUT` de contenido de **otro tamaño**. (e) `PUT` del contenido correcto **sin** la cabecera. (f) `head_object(ChecksumMode="ENABLED")` tras (b). (g) `copy_object` con `MetadataDirective="REPLACE"` y otro `ContentType`, y de nuevo (f); si la suma desaparece, la misma copia con `ChecksumAlgorithm="SHA256"` sobre otro objeto subido como en (b), y de nuevo (f). (h) `generate_presigned_url("get_object", Params={…, "ResponseContentDisposition": 'attachment; filename="a.pdf"', "ResponseContentType": "application/pdf"})` y un `GET` | (b) `200`. (c) `4xx` y `head_object` de esa clave → `404`. (d) `403`. (f) `ChecksumSHA256 == b64`. (h) `200` con `Content-Disposition: attachment; filename="a.pdf"`. Se anota el resultado de (e), que no condiciona nada, y el de (g) como (g1), (g2) o (g3) de «Reescritura del tipo y suma del objeto», que fija el orden del paso 11 | (c) aceptado o (f) sin suma → `/sdd-escalar` **antes de la fila 1a**: el non-goal prohíbe calcular el hash en la ruta, y calcularlo en un trabajo es otro alcance. (e) aceptado no escala: la confirmación lo detecta como `ARCHIVO_HASH_DISTINTO` sin `hash_almacenado` (`P-11`) y `TC-20` lo cubre. (h) sin la cabecera → `/sdd-escalar` (`CA-8`) |
| `E-2` (`PA-T59.14`) | La comprobación estructural de un `.xlsx` grande cabe en lecturas por rango acotadas | Un libro mínimo de `openpyxl` al que `zipfile` en modo `"a"` añade `xl/media/relleno.bin` de 26,000,000 bytes aleatorios, `ZIP_STORED`. Se sube a MinIO y se ejecuta el algoritmo de «Detección del tipo» con `get_object(Range=…)`, contando los bytes recibidos | Cada rango responde `206` con la longitud pedida; el algoritmo encuentra la parte de libro; bytes leídos ≤ 262144 | Rango no respetado, ZIP64 en el libro de prueba o más de 262144 bytes → `/sdd-escalar` antes de la fila 1a |
| `E-3` | `puremagic` y `defusedxml` se comportan como asume el detector | `puremagic.magic_string` sobre cabeceras sintéticas de JPEG, PNG, WebP, HEIC (`ftypheic`), MP4 (`ftypisom`), PDF, un ejecutable (`MZ`) y un ZIP; anotar la primera `extension` y `mime_type`. `DefusedXMLParser(target=…, forbid_dtd=True, forbid_entities=True, forbid_external=True).feed(...)` con un XML con `<!DOCTYPE` y entidades, y con `<svg xmlns="http://www.w3.org/2000/svg">` | Los seis tipos binarios dan una extensión de `EXTENSIONES`; el `MZ` da `.exe` u otra fuera de la tabla; el `feed` del DOCTYPE lanza `DTDForbidden` **durante** `feed`; el del SVG entrega `{http://www.w3.org/2000/svg}svg` a `start` | Un tipo binario no reconocido → la fila 6 añade su firma propia, según «Detección del tipo» (no escala). El `feed` no lanza durante `feed` → `/sdd-escalar` antes de la fila 6 |
| `E-4` (`P-14`) | Un servicio con un perfil inactivo no hace fallar `docker compose up -d db` aunque sus `${…:?}` no estén definidas | Un `compose.yaml` temporal con `db` y el servicio `minio` de «Ajustes y variables» (perfil `almacen`), y un `--env-file` con solo las variables de base: `docker compose -p e4 -f <temporal> --env-file <env> config` y `up -d --wait db`; después, `docker compose -p e4 … up -d minio` con el mismo `.env`. Se anota `docker compose version` | `up -d db` arranca solo `db`; `up -d minio` falla nombrando la variable que falta | Si `up -d db` falla por la interpolación → la fila 1a aplica la variante `:-` descrita en «Por qué el perfil» (no escala) |
| `E-5` (`CA-14`) | MinIO restringe el origen del CORS por bucket, o al menos por la variable global | Con `MinioContainer(<imagen de E-0>)` y un bucket: (a) `put_bucket_cors` con la regla de «CORS del almacén» y origen `http://localhost:5173`; anotar si responde `NotImplemented`. (b) `OPTIONS` a la URL de un objeto con `Origin: http://localhost:5173`, `Access-Control-Request-Method: PUT` y `Access-Control-Request-Headers: x-amz-checksum-sha256`; y el mismo con `Origin: http://otro.prueba.test`. Anotar las cabeceras `Access-Control-Allow-*`. (c) Si (a) o (b) no restringen, un contenedor nuevo con `MINIO_API_CORS_ALLOW_ORIGIN=http://localhost:5173` y las dos peticiones de (b). (d) Un `PUT` firmado con `Origin: http://localhost:5173` → anotar `Access-Control-Allow-Origin` en la respuesta | Uno de los dos mecanismos da `Access-Control-Allow-Origin: http://localhost:5173` al origen de la SPA y ninguna `Access-Control-Allow-Origin` al otro | Aplicar la fila de la tabla «CORS del almacén» que corresponda: (c1) o (c2) no escalan; (c3) → `/sdd-escalar` antes de la fila 1a |

## Orden de implementación

> **Nota para quien ejecuta desde Cursor.** Los agentes de Cursor corren todos en `composer-2.5[fast=false]`: la columna Modelo no se aplica tal cual, y en `impl.md` se anota el modelo con que corrió cada fila. Context7 puede no estar disponible; si falta, se anota y se sigue con la documentación del diseño. `/sdd-escalar` sí está disponible y es obligatorio donde el diseño lo pide. Los comandos están escritos para PowerShell: sin comodines en rutas (PowerShell no los expande para `pytest`), con `-k` o con listas explícitas, y con `$env:TEMP` como directorio temporal.

Ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd) por fila: el tester escribe en rojo los tests de la fila, el desarrollador los pone en verde de uno en uno y la verificación corre antes de la fila siguiente. Comandos desde `backend/` con Docker en marcha. Rojo válido: la función, el módulo, la tabla o la ruta no existen, o el rechazo no ocurre; nunca un error de importación del propio test. `tester-backend` y `tester-api` van en `sonnet`, su valor por omisión. Las líneas son de producción (sin pruebas) y estimadas.

**Quién hace qué**, según las definiciones de los agentes: las dependencias, `compose.yaml`, `ci.yml` y `.env.example` son de `ingeniero-devsecops` (`.claude/agents/ingeniero-devsecops.md`, línea 16, y la tabla del paso 2b de `sdd-ejecutar`); las fixtures de `conftest.py` y todo archivo de `tests/` son del tester (`desarrollador-aplicacion.md`, línea 20: «No tocas los tests»); la documentación, el borrador OpenAPI y el ADR de cada cierre los aplica el orquestador, en el paso de documentación de `/sdd-ejecutar`; el tester del cierre solo corre los mutantes y la suite.

**Apertura de cada entrega** distinta de 059a: si `Produccion` no cambió desde el cierre de la entrega anterior, basta `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run alembic heads`. Si cambió, se corre además `uv run pytest -q -ra`. La suite completa corre siempre en la fila de cierre.

**`pip-audit` como en el pipeline**, en PowerShell desde `backend/`: `uv export --locked --all-groups --no-emit-project --format requirements.txt -o "$env:TEMP\req.txt"`; `uv run pip-audit -r "$env:TEMP\req.txt" --require-hashes --disable-pip --strict -f json -o "$env:TEMP\pip-audit.json"` (en PowerShell un código de salida distinto de cero no corta la secuencia, que es lo que el `|| true` del pipeline consigue); `python ..\tools\severidad_pip_audit.py "$env:TEMP\pip-audit.json"`, que es quien decide si falla.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 0 | Línea base de herramientas y experimentos `E-0` a `E-5`. Sin código | — | `tester-backend` | `haiku` · tarea mecánica: comandos y resultado esperado escritos aquí | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run alembic heads`, `uv run pytest -q -ra`; desde la raíz, `python tools/verificar_docs.py`. Salida en `impl.md`. **Si `E-0`, `E-1`, `E-2` o `E-5` (caso c3) fallan como dice su columna, `/sdd-escalar` y no se ejecuta ninguna fila más** | ⚠ Ajustado |
| 1a | Dependencias: `uv add boto3 puremagic`; `uv add --dev "boto3-stubs[s3]" "testcontainers[postgres,minio]" types-defusedxml` (si `uv` no resuelve `types-defusedxml`, un `[[tool.mypy.overrides]]` con `module = ["defusedxml", "defusedxml.*"]` e `ignore_missing_imports = true`, anotado en `impl.md`). El `[[tool.mypy.overrides]]` estricto añade `cimenta.archivos.*`; si `mypy` informa que `puremagic` no tiene tipos, otro con `module = ["puremagic"]` e `ignore_missing_imports = true`. El extra `minio` de testcontainers arrastra el paquete `minio` como dependencia de desarrollo, y entra en el `pip-audit`. Servicio `minio` en `compose.yaml` con la etiqueta de `E-0`, el perfil `almacen`, las credenciales con `:?` o `:-` según `E-4` y, solo en el caso (c2) de `E-5`, `MINIO_API_CORS_ALLOW_ORIGIN`. Sección del almacén en `.env.example` (con `CIMENTA_SPA_ORIGEN` activa y `CIMENTA_ALMACEN_ENDPOINT` comentada) y paso de `humo` en `ci.yml`, según «Ajustes y variables». Antes, el tester escribe `TC-45a` en rojo. ~10 de configuración | `TC-45a`, `TKT-057/TC-64` y `TKT-057/TC-65` de `test_tkt057_entorno.py`, `test_identidad_credenciales.py` | `tester-backend` → `ingeniero-devsecops` | `haiku` · tarea mecánica verificable por comando | `uv sync --locked --python 3.14`; `uv run pytest tests/test_tkt059_infraestructura.py tests/test_tkt057_entorno.py tests/test_identidad_credenciales.py -q`; `uv run mypy .`; desde la raíz, con un `.env` **temporal** de valores ficticios en `$env:TEMP` (nunca el `.env` real, cuya salida imprimiría contraseñas, RNF-07), `docker compose -p tkt059-verif --env-file "$env:TEMP\tkt059.env" config --quiet`; con otro `.env` temporal **sin** las variables del almacén, `docker compose -p tkt059-verif --env-file "$env:TEMP\tkt059-sin-almacen.env" up -d --wait db` arranca `db` y no `minio`; al final, `docker compose -p tkt059-verif down -v`, para no tocar el volumen de quien desarrolla | ⚠ Ajustado |
| 1b | En `conftest.py`: `_imagen_minio()` (mismo patrón que `_imagen_postgres`, con `minio/minio:\S+` o `quay.io/minio/minio:\S+`), `contenedor_minio` (sesión), `bucket_de_pruebas` (sesión, `create_bucket` una vez) y `cliente_s3` (cliente `boto3` directo para sembrar objetos). La fixture `almacen` **no** entra aquí: depende de `crear_almacen_s3`, que nace en la fila 5. El CORS de las pruebas se fija según `E-5`: en (c1), `bucket_de_pruebas` llama a `aplicar_cors` con `http://spa.prueba.test`; en (c2), `contenedor_minio` recibe `MINIO_API_CORS_ALLOW_ORIGIN=http://spa.prueba.test`. Después, `herramientas/almacen_local.py`, con `aplicar_cors` en el caso (c1). ~60 | `TC-51`, `TC-54` | `tester-backend` (fixtures, `TC-51` y `TC-54`) → `desarrollador-aplicacion` (herramienta) | `haiku` | `uv run pytest tests/test_tkt059_herramienta.py tests/test_tkt059_cors.py -q`; `uv run pytest tests -q -k "tkt003 or identidad_credenciales"` | ⚠ Ajustado |
| 2 | Migración de `archivo` con subida, guarda y bajada. El tester ajusta `test_tkt072_migracion.py`: si TKT-017a1 no se fusionó, separa `REVISION_NUEVA` en `REVISION_0010 = "0010"` (subida y bajada de `TKT-072/TC-18`, destino de `TKT-072/TC-21`) y `CABEZA = "00NN"` (versión esperada en `TKT-072/TC-20`, líneas 337 y 352, y en la bajada de `TKT-072/TC-21`); si ya se fusionó, solo cambia el valor de `CABEZA`. ~90 | `TC-01` a `TC-04`, `TKT-072/TC-18` a `TKT-072/TC-21` ajustados | `tester-backend` → `desarrollador-sql` | `sonnet` · disparador: los permisos de un rol (el `REVOKE DELETE` del rol de aplicación sostiene que un archivo no se borra) | `uv run pytest tests/test_tkt059_migracion.py tests/test_tkt072_migracion.py -q`; `uv run pytest -q -k "migracion or esquema or semilla"`; `uv run alembic heads` muestra una sola cabeza | ⚠ Ajustado |
| 3 | `dominio/tipos.py`, `dominio/declaracion.py`, `dominio/confirmacion.py`. ~120 | `TC-47` a `TC-50` | `tester-backend` → `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt059_dominio.py -q`; `uv run python -m herramientas.verificar_float`; `uv run lint-imports` | ✓ Hecho |
| 4 | Cierre de 059a: mutantes `M-01` a `M-05`, `M-11`, `M-18` y `M-20`, uno a uno y revertidos (`tester-backend`); documentación de la fila «059a» de «Documentación afectada» (el orquestador) | Todos los de 0 a 3 y `TC-44` | `tester-backend`; el orquestador para la documentación | `sonnet` · valor por omisión | Cada mutante pone en rojo su test; tras revertir, la línea base de la fila 0 completa, el `pip-audit` como en el pipeline (las dependencias nuevas entran en esta entrega), y desde la raíz `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py` y `python -m unittest discover -s tools/tests -v` | ✓ Hecho |
| 5 | `aplicacion/puertos.py` e `infraestructura/almacen_s3.py`. El tester añade a `conftest.py` la fixture `almacen` (función: `crear_almacen_s3` sobre `contenedor_minio` y `bucket_de_pruebas`, con `endpoint=None`). ~160 | `TC-08`, `TC-08b`, `TC-21`, `TC-33` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_almacen.py -q`; `uv run mypy .` | ⚠ Ajustado |
| 6 | `infraestructura/detector_tipo.py`, con la tabla `EXTENSIONES` que fijó `E-3`. ~150 | `TC-25`, `TC-25b`, `TC-52` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_detector.py -q` | ✓ Hecho |
| 7 | Cierre de 059b: mutantes `M-06` a `M-08`, `M-16` y `M-21` (`tester-backend`); documentación de la fila «059b», incluido el ADR (el orquestador) | Todos los de 5 y 6 y `TC-44` | `tester-backend`; el orquestador para la documentación | `sonnet` · valor por omisión | Igual que la fila 4 | ✓ Hecho |
| 8 | Ajustes (diez campos, `PATRON_ENDPOINT`, validadores, `_mensaje_de_variables`, `_exigir_almacen_con_base` en los dos retornos de `cargar_ajustes`), `aplicacion/contexto.py` (`AlmacenNoConfigurado`, `ConfiguracionArchivos`, `ContextoArchivos`, `construir_contexto`), `interfaz.py` con lo que la fábrica importa (ver «Composición en `servidor/fabrica.py`»), y en la fábrica `crear_aplicacion(..., almacen=None)`, el proveedor perezoso del almacén, la configuración y `aplicacion.state.archivos = construir_contexto(...)`, todavía sin enrutador ni barrido. El tester ajusta `TKT-057/TC-52` de `test_tkt057_arranque.py` como dice «Ajustes y variables». ~110 | `TC-05` a `TC-07`, `TC-07b`, `TC-45b`, `TKT-057/TC-51` y `TKT-057/TC-52` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_ajustes.py tests/test_tkt059_infraestructura.py tests/test_tkt057_arranque.py tests/test_tkt057_entorno.py tests/test_tkt015_arranque.py tests/test_servidor_arranque.py tests/test_identidad_credenciales.py -q`; `uv run lint-imports` | ⚠ Ajustado |
| 9 | `infraestructura/repositorio.py`, `aplicacion/alta.py`, `api/dependencias.py` (`contexto_de_archivos`) y su exportación, con `registrar_archivo` y `AltaArchivo`, en `interfaz.py`. ~150 | `TC-09` a `TC-13`, `TC-13b` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_alta.py -q`; `uv run lint-imports` | ⚠ Ajustado |
| 10 | Cierre de 059c: mutante `M-05b` (`tester-backend`); documentación de la fila «059c» (el orquestador) | Todos los de 8 y 9 y `TC-44` | `tester-backend`; el orquestador para la documentación | `sonnet` · valor por omisión | Igual que la fila 4 | ✓ Hecho |
| 11 | Dos condiciones independientes, comprobadas en `cimenta.identidad.interfaz` al empezar la fila: (a) si no está `nombres_de_usuarios`, se crea `nombres_de_usuarios(sesion_bd: Session, ids: Iterable[UUID]) -> dict[UUID, str]` (repositorio de `identidad`, aplicación e interfaz, `P-5`); (b) si no está `UsuarioResumen`, se crea `UsuarioResumen(BaseModel)` con `id: UUID` y `nombre: str` en `identidad/api/esquemas.py`, publicado en la interfaz (`P-13`). Si las dos existen, la fila no tiene código y se marca `✓ Hecho` con esa constancia. El tester ajusta la aserción de `test_tkt006_enrutador.py` (líneas 741 a 771) que fija `set(cimenta.identidad.interfaz.__all__)` a siete nombres, añadiendo los que se creen. ~30 | `TC-53`, la aserción ajustada de `test_tkt006_enrutador.py` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_identidad_nombres.py tests/test_tkt006_enrutador.py -q`; `uv run lint-imports` | Pendiente |
| 12a | `aplicacion/confirmacion.py` completo (los once pasos, la denegación y la traducción de `55P03` y `57014`), `api/esquemas.py` (`EstadoArchivo`, `Archivo`), `api/rutas.py` (la ruta de confirmación), `api/montaje.py`, `montar_archivos` en `servidor/fabrica.py` en lugar de la línea de la fila 8, el orden del paso 11 que fijó `E-1` (g), y el «Cambio del borrador en 059d». El tester añade a `conftest.py` la fixture `aplicacion_archivos` (`crear_aplicacion(motor=motor_aplicacion, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA, almacen=almacen)`), `esperar_hasta` (movida desde su copia local en `test_tkt072_migracion.py`, que pasa a importarla) y `fabrica_espera_corta` (motor del rol de aplicación con `connect_args={"options": "-c lock_timeout=200ms"}`), si TKT-017 no las creó ya; y la entrada de la confirmación en `CUERPOS_VALIDOS` de `test_tkt057_csrf.py`. Después, `npm run tipos:generar` y se versiona `servidor.ts`. ~240 | `TC-14` a `TC-18`, `TC-18b`, `TKT-057/TC-48` | `tester-api` → `desarrollador-api` | `sonnet` · disparadores: bloqueo pesimista y concurrencia (`FOR UPDATE`, `TC-18` y `TC-18b`) | `uv run pytest tests/test_tkt059_confirmacion.py tests/test_tkt059_confirmacion_concurrencia.py -q`, el de concurrencia **tres veces seguidas** sin intermitencia; `uv run pytest tests -q -k "tkt006 or tkt057 or tkt072"` y `uv run pytest tests/test_tkt015_arranque.py -q`, porque esas suites construyen la aplicación real con la fixture `cliente`, que entra en el `lifespan`, y desde esta fila la aplicación monta `archivos`; desde `frontend/`, `npm run tipos:verificar` | Pendiente |
| 12b | Sin código nuevo previsto: los rechazos ya están escritos en 12a según «Orden de comprobaciones de la confirmación». El tester los escribe en rojo con un mutante temporal (por ejemplo, saltar el paso que rechaza) para comprobar que cada test falla por su razón, y el desarrollador solo corrige lo que no cumpla el contrato. ~40 | `TC-19`, `TC-20`, `TC-22` a `TC-24`, `TC-26` a `TC-30` | `tester-api` → `desarrollador-api` | `sonnet` · disparador: los permisos de un rol (exclusiva de `DIRECTOR_PROYECTOS`, `NO_ES_SOLICITANTE` asentado `DENEGAR`) | `uv run pytest tests/test_tkt059_confirmacion_rechazos.py -q`; `uv run pytest tests -q -k "tkt006 or tkt057"` | Pendiente |
| 13 | Cierre de 059d: mutantes `M-02b`, `M-09`, `M-10`, `M-15` y `M-19` (`tester-backend`); documentación de la fila «059d» (el orquestador) | Todos los de 11 a 12b y `TC-44` | `tester-backend`; el orquestador para la documentación | `sonnet` · valor por omisión | Igual que la fila 4 | Pendiente |
| 14 | `aplicacion/consulta.py`, `UrlDescarga` y las dos rutas `GET`, el «Cambio del borrador en 059e». Después, `npm run tipos:generar` y se versiona `servidor.ts`. ~130 | `TC-31`, `TC-32`, `TC-34` a `TC-36` | `tester-api` → `desarrollador-api` | `sonnet` · disparador: los permisos de un rol (dos rutas restringidas a dos roles, con el `403` sin datos ni URL para los otros cuatro y el rol comprobado al emitir) | `uv run pytest tests/test_tkt059_consulta.py tests/test_tkt006_enrutador.py -q`; desde `frontend/`, `npm run tipos:verificar` | Pendiente |
| 15 | `aplicacion/barrido.py`, `aplicacion/lectura.py`, el `lifespan` de `servidor/fabrica.py` (barrido de archivos y lector) y su docstring; `interfaz.py` completa. ~75 | `TC-37` a `TC-42` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt059_arranque.py tests/test_tkt015_arranque.py tests/test_tkt015_ejecutor.py tests/test_tkt059_confirmacion.py tests/test_tkt059_confirmacion_concurrencia.py tests/test_tkt059_confirmacion_rechazos.py tests/test_tkt059_consulta.py -q` (las suites de 059d y 059e, porque desde esta fila el barrido de arranque caduca todo `PENDIENTE` sembrado antes de entrar al `TestClient`); `uv run pytest tests -q -k "tkt006 or tkt057"` | Pendiente |
| 16 | Prueba «ninguna ruta binaria» sobre la aplicación real. Sin código de producción | `TC-43` | `tester-api` | `sonnet` · valor por omisión | `uv run pytest tests/test_tkt059_rutas.py -q` | Pendiente |
| 17 | Cierre de 059e: mutantes `M-12` a `M-14` y `M-17` (`tester-backend`); documentación de la fila «059e» (el orquestador); cierre del paraguas | Todos y `TC-44` | `tester-backend`; el orquestador para la documentación | `sonnet` · valor por omisión | Igual que la fila 4, más `python tools/verificar_escenarios.py`. **Advertencia en `impl.md`:** HDU-001 sigue `PENDIENTE` en `tools/historias_activas.txt` hasta TKT-017c (`P-13` de TKT-017); el verde de `verificar_escenarios.py` no prueba aquí los esc. 25 y 26: lo prueba la tabla del plan de pruebas | Pendiente |

**Modelo:** `haiku` por omisión; `sonnet` solo donde la fila cita su disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo), y en las filas del tester y de cierre por su valor por omisión. Ninguna fila va en `opus`.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

### Tamaño y partición propuesta

| Fila | Líneas de producción estimadas |
|---|---|
| 1a | ~10 (más `compose.yaml`, `pyproject.toml`, `.env.example` y `ci.yml`) |
| 1b | ~60 (con `aplicar_cors`; más las fixtures, que son de prueba) |
| 2 | ~90 |
| 3 | ~120 |
| 5 | ~160 (con el segundo cliente) |
| 6 | ~150 |
| 8 | ~120 (con `almacen_endpoint`) |
| 9 | ~150 |
| 11 | ~30 (condicional) |
| 12a | ~240 |
| 12b | ~40 |
| 14 | ~130 |
| 15 | ~75 |
| **Total** | **~1,375** |

Más de tres veces el umbral de ~400. **Propuesta de partición (`P-2`), sin aplicarla:** cinco entregas que se fusionan en orden, cada una con su rama, su PR y su fusión.

| Entrega | Filas | Producción | Rama | Qué deja funcionando |
|---|---|---|---|---|
| TKT-059a · Esquema, dominio e infraestructura de MinIO | 0 a 4 | ~280 | `tkt-059a-esquema-y-dominio` | Tabla con sus invariantes, reglas puras, MinIO en Compose y en testcontainers, CORS del almacén local |
| TKT-059b · Adaptadores del almacén | 5 a 7 | ~310 | `tkt-059b-adaptadores` | Firma con el origen público, operaciones por el endpoint interno, metadatos, rangos y detección del tipo contra MinIO real |
| TKT-059c · Ajustes y alta | 8 a 10 | ~270 | `tkt-059c-ajustes-y-alta` | El arranque exige el almacén con base; la interfaz de alta que TKT-018 necesita |
| TKT-059d · Confirmación | 11 a 13 | ~310 | `tkt-059d-confirmacion` | `confirmar_archivo` de extremo a extremo |
| TKT-059e · Lecturas, barrido y lector | 14 a 17 | ~205 | `tkt-059e-lecturas-y-barrido` | Metadatos, descarga, barrido de arranque y lector conectado al ejecutor |

Reglas de la partición, que la ejecución no reabre si se aprueba:

- Cada entrega distinta de 059a abre con la apertura reducida descrita al principio del orden de implementación (sin repetir los experimentos, que corren una sola vez en 059a) y cierra con su fila de cierre: suite completa, linters, `pip-audit` y los tres comandos de documentación.
- **Cada mutante corre en la entrega que contiene el código que muta**: los del dominio (`M-01` a `M-05`, `M-11`), el de la migración (`M-18`) y el del CORS (`M-20`) en 059a; los del detector (`M-06` a `M-08`, `M-16`) y el del origen de firma (`M-21`) en 059b; el del alta (`M-05b`) en 059c; los de la confirmación (`M-02b`, `M-09`, `M-10`, `M-15`, `M-19`) en 059d; los de la descarga, el barrido, el lector y la prueba de rutas (`M-12` a `M-14`, `M-17`) en 059e. Ninguna entrega se fusiona con código suyo sin mutar.
- La documentación de cada entrega viaja con ella, según «Documentación afectada»; el borrador y `servidor.ts` de cada ruta, en la entrega que la monta.
- `.env.example` y `humo` traen las variables del almacén desde 059a, donde son inocuas; la obligatoriedad con base llega en 059c, que no monta rutas.
- `/sdd-ejecutar TKT-059a` ejecuta las filas 0 a 4 y se detiene tras la fila 4; cada entrega siguiente se ejecuta con su propio `/sdd-ejecutar TKT-059x`. `impl.md` es uno solo, con una sección por entrega.

## Plan de pruebas

PostgreSQL y MinIO reales con testcontainers; esquema por `alembic upgrade head`; escrituras con el rol de aplicación. Las imágenes salen de `compose.yaml`. Cada rechazo por la API comprueba el contrato completo —`tipo`, `codigo` o `motivo`, `mensaje`, `detalle` con sus valores y `acciones`— y, después, que la fila y la bitácora no cambiaron. En los casos de uso, el rechazo se comprueba con `excepcion.cuerpo(roles, "c")`. Las sesiones de API usan `TestClient(app, base_url="https://testserver", raise_server_exceptions=False)` con `sembrar_usuario` y el inicio de sesión de las suites de TKT-006. La aplicación de las pruebas de API es `crear_aplicacion(motor=motor_aplicacion, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA, almacen=almacen)`. Las subidas usan `httpx.put(url, content=…, headers=cabeceras)`. Ningún `sleep` para sincronizar: las esperas usan `esperar_hasta(condicion, limite)` con sondeo, que la fila 12a sube a `conftest.py` desde su copia local en `test_tkt072_migracion.py`.

**Altas dentro del `TestClient`.** El reloj de prueba empieza el 2026-10-21 (`conftest.py`, línea 57), así que una fila `PENDIENTE` dada de alta con ese reloj ya tiene más de 24 horas para el `now()` del motor. Desde la fila 15, el barrido de arranque la caducaría al entrar en el `TestClient`. Por eso, en toda prueba de API, las altas y las siembras de `PENDIENTE` se hacen **dentro** del bloque `with TestClient(...)`, nunca antes; las pruebas de arranque (`TC-37`, `TC-38`) son la excepción, porque siembran a propósito antes de entrar, con `creado_en` relativo a `now()`.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_tkt059_ca01_invariantes_del_archivo`, parametrizado: `DISPONIBLE` sin hash, sin tamaño o sin `confirmado_en` → `23514` en `ck_archivo_disponible_verificado`; `ANULADO` sin autor o sin motivo → `ck_archivo_anulado_con_motivo`; clave repetida → `23505` en `uq_archivo_clave_objeto`; `referencia_id` nulo con `IMPORTACION` → `ck_archivo_referencia_obligatoria`; estado `BORRADO` y tipo `COMPRA` → su `CHECK`. Nulo con `OBRA` se admite. Con el rol de aplicación; se lee `diag.constraint_name` | **rechazo** | `CA-1` esc. 1 | — |
| TC-02 | `test_tkt059_ca01_el_rol_de_aplicacion_no_borra_archivos`: `DELETE FROM archivo WHERE id = …` y `TRUNCATE archivo` → `42501`; la fila sigue. El `DELETE` lo sostiene el `REVOKE` de la migración (`M-18`); el `TRUNCATE`, los privilegios por omisión de `0001` | **rechazo** | `CA-1` esc. 2 | — |
| TC-03 | `test_tkt059_ca01_la_migracion_sube_y_baja`: `base_vacia` a la revisión anterior, fotografía A; subida: columnas, tipos, nulabilidad, las nueve restricciones con nombre, los tres índices (el parcial con su predicado), privilegios del rol de aplicación sin `DELETE` ni `TRUNCATE`, y ninguna clave foránea sobre `obra_id` ni `referencia_id`; bajada: fotografía `== A`; subida otra vez | feliz | `CA-1` esc. 3 | — |
| TC-04 | `test_tkt059_ca01_la_bajada_se_niega_con_archivos`: con una fila, la bajada → `P0001` y el texto «La bajada de 00NN se niega»; versión y fila intactas | **rechazo** | `CA-1` esc. 3 | — |
| TC-05 | `test_tkt059_ca02_con_base_el_almacen_es_obligatorio`, parametrizado por las cuatro variables, ausente y vacía, con las tres variables de base y la contraseña de aplicación en el mapa: `ConfiguracionInvalida` cuyo mensaje nombra **solo** la variable que falta y no contiene ningún valor del mapa; `__cause__ is None`. Variante con las cuatro ausentes: el mensaje las nombra ordenadas. Variante por proceso: `crear_aplicacion()` en un proceso hijo con base y sin `CIMENTA_ALMACEN_BUCKET` termina con ese error | **rechazo** | `CA-2` esc. 1 | — |
| TC-06 | `test_tkt059_ca02_sin_base_arranca_sin_almacen`: `cargar_ajustes` con solo la contraseña de aplicación deja los cuatro campos en `None`; `crear_aplicacion(entorno=…)` sin base sirve `/openapi.json` con `200` y el `lifespan` registra `trabajos_omitidos`. Que las tres rutas de archivos estén publicadas sin base lo comprueba `TC-43`, en la fila 16 | feliz y regresión | `CA-2` esc. 2, `CA-R1` | — |
| TC-07 | `test_tkt059_ca02_las_omisiones_de_los_ajustes_de_archivos`, `test_tkt059_ca02_ajustes_de_archivos_fuera_de_rango`, `test_tkt059_ca02_ajustes_de_archivos_en_el_borde_valido` y `test_tkt059_ca02_el_umbral_se_compara_con_la_vida_de_subida_configurada`: omisiones `900`, `300`, `86400`, `15728640`, `52428800`, `26214400`; `59` y `3601` en las vidas, `0` en un límite y un umbral igual a la vida de subida → `ConfiguracionInvalida` que nombra solo esa variable y no su valor; un umbral inválido junto a una vida inválida nombra solo la vida. `CIMENTA_ALMACEN_ENDPOINT`: `http://minio:9000` y `https://almacen.interno:9443` se aceptan; `ftp://minio`, `http://minio:9000/ruta` y `minio:9000` se rechazan nombrando la variable; con base y sin `CIMENTA_ALMACEN_ENDPOINT`, `cargar_ajustes` no lanza | **rechazo** y feliz | `CA-2` | — |
| TC-07b | `test_tkt059_ca02_el_proveedor_del_almacen_es_perezoso`: `crear_aplicacion` sin almacén inyectado y sin las cuatro variables, con `crear_almacen_s3` sustituido por un espía, no lo llama al construirse; `aplicacion.state.archivos.almacen()` lanza `AlmacenNoConfigurado`; con las cuatro variables, la primera llamada crea el adaptador una vez y la segunda devuelve el mismo objeto | feliz y **rechazo** | `CA-2` esc. 2 | — |
| TC-08b | `test_tkt059_ca02_las_url_llevan_el_origen_publico`: con el contenedor alcanzable por dos nombres (`endpoint = http://127.0.0.1:<puerto>`, `origen = http://localhost:<puerto>`), `url_subida` y `url_lectura` devuelven URL cuyo esquema, host y puerto son los del **origen**, el `PUT` y el `GET` por esas URL responden `200`, y un espía sobre los dos clientes muestra que `metadatos`, `leer_rango`, `leer_todo` y `reescribir_tipo` solo usaron el cliente del **endpoint**. Con `endpoint=None`, las dos direcciones son el origen | feliz | `CA-2` esc. 4 | — |
| TC-08 | `test_tkt059_ca02_el_destino_cambia_solo_por_endpoint`: `crear_almacen_s3` con el `endpoint` del contenedor firma una subida, `PUT` responde `200`, `metadatos`, `leer_rango`, `leer_todo` (los mismos bytes), `reescribir_tipo` (`head_object` da el tipo nuevo) y `url_lectura` funcionan; el texto de `almacen_s3.py` no contiene `minio`, `r2` ni `cloudflare` (sin distinguir mayúsculas; palabra completa, ajuste en `impl.md`, «Ajustes respecto al design (059b)») | feliz | `CA-2` esc. 3 | — |
| TC-09 | `test_tkt059_ca03_alta_registra_el_pendiente`: en una transacción abierta por la prueba, `registrar_archivo` con `IMPORTACION`, «Presupuesto torre 5.xlsx», `8388608` bytes, su SHA-256 y el tipo `.xlsx`: fila `PENDIENTE` con nombre, tamaño, hash y `subido_por_id`; `clave_objeto == f"{obra_id}/{archivo_id}"`, sin el nombre; `metodo == "PUT"`; la URL empieza por el origen del almacén; `cabeceras` según `E-1`; `expira_en == reloj + 15 min`; la URL lleva `X-Amz-Expires=900` | feliz | `CA-3` esc. 1 | `HDU-001 esc. 24` (dueño TKT-018) |
| TC-10 | `test_tkt059_ca03_alta_se_deshace_con_quien_llama`: la transacción de la prueba lanza después del alta; ninguna fila | **rechazo** | `CA-3` esc. 1 | — |
| TC-11 | `test_tkt059_ca03_tamano_declarado_excede_limite`, parametrizado por las tres categorías con límite + 1: `422` `VALIDACION`, un error en `archivo.tamano_bytes`, `FUERA_DE_RANGO`, el mensaje con el límite exacto («26214400 bytes (25 MB) para documentos»); ninguna fila; `url_subida` no se llamó (espía). Borde: el límite exacto se admite | **rechazo** | `CA-3` esc. 2 | — |
| TC-12 | `test_tkt059_ca03_tipo_declarado_fuera_de_lista`, parametrizado `application/vnd.ms-excel`, `image/svg+xml`, `application/x-msdownload`: `VALOR_NO_PERMITIDO` en `archivo.tipo_declarado` y ningún error de tamaño; ninguna fila ni URL | **rechazo** | `CA-3` esc. 3 | — |
| TC-13 | `test_tkt059_ca03_forma_de_la_declaracion`, parametrizado: hash con mayúsculas o de 63 caracteres → `FORMATO`; tamaño `0` → `NO_POSITIVO`; nombre `"  "` → `OBLIGATORIO`; nombre de 256 caracteres → `DEMASIADO_LARGO`; nombre con `NUL` o con un sustituto Unicode → `FORMATO` (`test_tkt059_ca03_nombre_con_caracteres_no_permitidos`, decisión del 2026-11-12) | **rechazo** | `CA-3` | — |
| TC-13b | `test_tkt059_ca03_contexto_de_archivos`: una ruta de prueba `def` que declara `Depends(contexto_de_archivos)` sobre `crear_aplicacion(...)` recibe el mismo objeto que `aplicacion.state.archivos` | feliz | `CA-3` | — |
| TC-14 | `test_tkt059_ca04_confirmar_un_xlsx`: alta, `PUT` del libro de `libro_catalogo` con `Content-Type: application/octet-stream`, `POST …/confirmacion` → `200`; el cuerpo valida contra `Archivo` del borrador y no tiene `clave_objeto`; fila `DISPONIBLE`, `tipo_mime` `.xlsx`, `confirmado_en == reloj`; `head_object` da `ContentType` `.xlsx`; un asiento `CONFIRMAR` de `archivo` con `obra_id` y `datos_despues` con hash, tamaño, tipo, `referencia_tipo` y `referencia_id` | feliz | `CA-4` esc. 1 | `HDU-001 esc. 24` (dueño TKT-018) |
| TC-15 | `test_tkt059_ca04_confirmar_dos_veces`: segunda confirmación → `200` con el mismo cuerpo; un solo `CONFIRMAR`; `metadatos` no se llamó la segunda vez (espía) | feliz | `CA-4` esc. 2 | — |
| TC-16 | `test_tkt059_ca04_la_bitacora_va_en_la_misma_transaccion`: `monkeypatch` de `confirmacion.auditoria.asentar` con una función que lanza `RuntimeError("fallo provocado")` → `500`; la fila sigue `PENDIENTE` con `confirmado_en` nulo | **rechazo** | `CA-4` esc. 1 · `RNF-19` | — |
| TC-17 | `test_tkt059_ca04_confirmar_lee_una_fraccion_acotada`: el libro de 26,000,000 bytes de `E-2`, subido y confirmado con un `AlmacenContador` que envuelve al almacén real: `200`; la suma de bytes de `leer_rango` ≤ `262144`; `leer_todo` nunca se llamó | feliz | `CA-4` · `PA-T59.14` | — |
| TC-18 | `test_tkt059_ca04_dos_confirmaciones_simultaneas`: el hilo A se pausa dentro de `metadatos` con un `threading.Event`; el hilo B confirma el mismo archivo y queda en espera de A (`pg_blocking_pids` con `esperar_hasta`); al liberar, los dos devuelven `DISPONIBLE` y hay un solo `CONFIRMAR` | concurrencia | `CA-4` esc. 2 | — |
| TC-18b | `test_tkt059_ca04_confirmacion_con_bloqueo_vencido`: con la aplicación sobre `fabrica_espera_corta` y otra sesión que tiene la fila de `archivo` con `FOR UPDATE` → `409` `CONCURRENCIA` `BLOQUEO_VENCIDO`, `detalle.espera_maxima_ms == 5000`, `Retry-After: 1`, acción `REINTENTAR` `POST` a la ruta de confirmación; la fila sigue `PENDIENTE` y no hay asiento | concurrencia y **rechazo** | `CA-4` | — |
| TC-19 | `test_hdu001_esc25_tamano_distinto`: objeto sembrado con `cliente_s3` de 8126464 bytes para una declaración de 8388608 → `409` `CONFLICTO` `ARCHIVO_TAMANO_DISTINTO`, `detalle == {"tamano_declarado": 8388608, "tamano_almacenado": 8126464}`, `acciones == []`; fila `PENDIENTE`; ningún asiento | **rechazo** | `CA-5` esc. 1 | `HDU-001 esc. 25` |
| TC-20 | `test_hdu001_esc25_hash_distinto`: mismo tamaño, otro contenido, sembrado con `ChecksumSHA256` de lo sembrado → `409` `ARCHIVO_HASH_DISTINTO` con los dos hashes en hexadecimal y los dos tamaños; el mensaje contiene «Vuelve a cargar el archivo»; fila `PENDIENTE`, ningún asiento. Variante sembrada **sin** suma: mismo código, `detalle` sin `hash_almacenado` | **rechazo** | `CA-5` esc. 2 | `HDU-001 esc. 25` |
| TC-21 | `test_tkt059_ca05_el_almacen_rechaza_la_subida_distinta`: `PUT` por la URL prefirmada de otro contenido del mismo tamaño → el código `4xx` que registró `E-1`; `metadatos` → `None` | **rechazo** | `CA-5` esc. 3 | — |
| TC-22 | `test_hdu001_esc26_tipo_no_permitido`, parametrizado (declarado `.xlsx`): ejecutable (`MZ…`), SVG, ZIP con `[Content_Types].xml` sin la parte de libro, ZIP sin `[Content_Types].xml`, `.xlsm` → `409` `ARCHIVO_TIPO_NO_PERMITIDO`, `tipo_detectado` (`image/svg+xml` para el SVG, `application/zip` para los tres ZIP) y `tipos_admitidos` igual a la lista de ocho en orden; fila `PENDIENTE`, ningún asiento | **rechazo** | `CA-6` esc. 1 | `HDU-001 esc. 26` |
| TC-23 | `test_tkt059_ca06_svg_renombrado_a_jpg`: declarado `image/jpeg`, nombre `foto.jpg`, contenido SVG → `tipo_detectado == "image/svg+xml"` | **rechazo** | `CA-6` esc. 2 | — |
| TC-24 | `test_tkt059_ca06_xml_con_entidades`: XML de expansión de entidades («mil millones de risas») declarado `application/xml` → `409` `ARCHIVO_TIPO_NO_PERMITIDO` con `tipo_detectado == "application/xml-dtd"`, en menos de 5 s | **rechazo** | `CA-6` esc. 3 | — |
| TC-25 | `test_tkt059_ca06_el_detector_reconoce_la_lista_blanca`: sobre `leer_rango` en memoria, JPEG, PNG, WebP, HEIC, MP4, PDF, XML con y sin declaración y con BOM, y `.xlsx` de `openpyxl` → su tipo canónico | feliz | `CA-6` | — |
| TC-25b | `test_tkt059_ca06_el_detector_rechaza_lo_no_admitido`, sobre `leer_rango` en memoria y parametrizado: SVG **sin** `DOCTYPE` (con él saldría `application/xml-dtd`) → `image/svg+xml`; ZIP con `[Content_Types].xml` sin la parte de libro → `application/zip`; `.xlsm` → `application/zip`; XML con `DOCTYPE` y XML con entidades → `application/xml-dtd`. Es el test de los mutantes `M-06` a `M-08`, que corren en 059b, antes de que exista la ruta | **rechazo** | `CA-6` | — |
| TC-26 | `test_tkt059_ca07_objeto_nunca_subido` → `409` `ARCHIVO_NO_SUBIDO` con `archivo_id`; fila `PENDIENTE` | **rechazo** | `CA-7` esc. 1 | — |
| TC-27 | `test_tkt059_ca07_confirmar_un_caducado`: fila `CADUCADO` → `409` `ARCHIVO_CADUCADO`; estado igual; ningún asiento | **rechazo** | `CA-7` esc. 2 | — |
| TC-28 | `test_tkt059_ca07_pendiente_vencido_sin_barrer`: `creado_en = reloj − 24 h − 1 s` y el objeto coincide → `409` `ARCHIVO_CADUCADO`; leída **desde otra conexión**, la fila está `CADUCADO`; ningún `CONFIRMAR`; `metadatos` no se llamó. Borde: `creado_en = reloj − 24 h` exacto → `200` | **rechazo** | `CA-7` esc. 3 | — |
| TC-29 | `test_tkt059_ca07_otro_director_no_confirma`: `403` `PERMISO`, `motivo` `NO_ES_SOLICITANTE`, `roles_requeridos == []`, sin `detalle` ni datos del archivo; un `DENEGAR` de `usuario` con ese motivo, `metodo`, `ruta` y `roles_requeridos`; fila `PENDIENTE`. Variante sobre un `CADUCADO`: también `403` | **rechazo** | `CA-7` esc. 4 | — |
| TC-30 | `test_tkt059_ca07_sin_rol_sin_origen_o_inexistente`, parametrizado por `DIRECCION_GENERAL`, `COMPRAS`, `RESIDENTE`, `ALMACEN`, `ADMINISTRACION` → `403` `ROL_INSUFICIENTE` asentado `DENEGAR`; sin token CSRF → `403` `ORIGEN_NO_VERIFICADO`; identificador inexistente → `404` `NO_ENCONTRADO` con `recurso` `archivo`; sin sesión → `401` | **rechazo** | `CA-7` esc. 5 | — |
| TC-31 | `test_tkt059_ca08_descargar_un_pdf`, para `DIRECCION_GENERAL` y `DIRECTOR_PROYECTOS`: `200` con `UrlDescarga` válida contra el borrador; `url` empieza por el origen del almacén; `expira_en == reloj + 5 min`; `tipo_mime` `application/pdf`; `disposicion` `attachment`; `GET` a la URL → `200`, `Content-Type: application/pdf` y `Content-Disposition` que empieza por `attachment;` con el nombre | feliz | `CA-8` esc. 1 | — |
| TC-32 | `test_tkt059_ca08_una_imagen_en_linea`: JPEG → `disposicion` `inline` y cabecera `inline;` | feliz | `CA-8` esc. 2 | — |
| TC-33 | `test_tkt059_ca08_la_url_caduca`: `url_lectura` con `vida=timedelta(seconds=1)`; el primer `GET` → `200`; `esperar_hasta` un `GET` con `403`, límite 15 s | **rechazo** | `CA-8` esc. 3 | — |
| TC-34 | `test_tkt059_ca08_metadatos`, para los dos roles: `200`, cuerpo válido contra `Archivo` del borrador, claves iguales a las propiedades del esquema, sin `clave_objeto`; un `CADUCADO` sale con ese estado y valida | feliz | `CA-8` esc. 4 | — |
| TC-35 | `test_tkt059_ca09_descarga_no_disponible`: `PENDIENTE` → `409` `ARCHIVO_NO_DISPONIBLE`; `CADUCADO` → `ARCHIVO_CADUCADO`; `detalle == {"archivo_id", "estado_archivo"}`; sin `url` | **rechazo** | `CA-9` esc. 1 y 2 | — |
| TC-36 | `test_tkt059_ca09_sin_rol`, parametrizado por las dos rutas `GET` y los cuatro roles restantes → `403` `ROL_INSUFICIENTE` sin `detalle` ni `url`, asentado `DENEGAR`; inexistente → `404` | **rechazo** | `CA-9` esc. 3 | — |
| TC-37 | `test_tkt059_ca10_el_arranque_caduca_los_pendientes_vencidos`: filas `PENDIENTE` con `creado_en = now() − 25 h` y `now() − 1 h`, una `DISPONIBLE` con `now() − 25 h`, y una importación `ANALIZANDO` vencida; `with TestClient(app)` con un almacén espía que falla ante cualquier llamada → la primera `CADUCADO`, las otras igual, el mismo número de filas, la bitácora sin asientos nuevos, el espía sin llamadas, la importación `CON_ERRORES` | feliz y regresión | `CA-10` esc. 1, `CA-R1` | — |
| TC-38 | `test_tkt059_ca10_el_almacen_caido_no_impide_arrancar`: almacén inyectado cuyos métodos lanzan `ConnectionError`; la aplicación arranca y el registro `barrido` trae `{"importacion": 0, "archivo": 1}` | **rechazo** | `CA-10` esc. 2 | — |
| TC-39 | `test_tkt059_ca10_definicion_del_barrido`: tabla, estados, `columna_marca == "creado_en"` y `al_vencer` sin efecto sobre un doble de sesión | feliz | `CA-10` | — |
| TC-40 | `test_tkt059_ca11_el_lector_devuelve_los_bytes`: `DISPONIBLE` con objeto → los mismos bytes | feliz | `CA-11` esc. 1 | — |
| TC-41 | `test_tkt059_ca11_el_lector_rechaza_lo_no_disponible`, parametrizado `PENDIENTE`, `CADUCADO`, inexistente → `ArchivoNoLegible`; `leer_todo` no se llamó | **rechazo** | `CA-11` esc. 2 | — |
| TC-42 | `test_tkt059_ca11_la_fabrica_conecta_el_lector`: `monkeypatch` de `fabrica.crear_ejecutor_analisis` con un espía que guarda `leer_contenido`; tras el `lifespan`, con un `DISPONIBLE` devuelve sus bytes y con un `PENDIENTE` lanza `ArchivoNoLegible` | feliz y **rechazo** | `CA-11` esc. 1 y 2 | — |
| TC-43 | `test_tkt059_ca12_ninguna_ruta_de_archivos_es_binaria`, sobre la aplicación real sin base: las `APIRoute` con ruta bajo `/api/v1/archivos` son exactamente las tres `(método, ruta, operationId)` del borrador con `TKT-059` en `x-tickets`, sin `crear_importacion`; ninguna `async def`; `response_class` efectiva `JSONResponse`; en `/openapi.json` cada respuesta de esas rutas tiene solo `application/json`; la `POST` declara `verificar_origen` antes que `exigir_rol` y las `GET`, `exigir_rol`. **Control**: el mismo comprobador sobre una aplicación con una ruta extra de prueba bajo `/api/v1/archivos` con `StreamingResponse` la señala | **rechazo** y regresión | `CA-12` | — |
| TC-44 | Regresión sin test nuevo: suites de TKT-006 (enrutador, sesión), TKT-007, TKT-015b (arranque, barrido, ejecutor), TKT-057 (arranque con `TKT-057/TC-52` ajustado, entorno, CSRF) y TKT-072 (con `CABEZA`) en verde; `lint-imports` en verde; `git diff --stat` en `backend/tests` solo toca los archivos que nombra cada fila | regresión de invariante | `CA-R1` | — |
| TC-45a | `test_tkt059_car1_compose_con_minio`, en `tests/test_tkt059_infraestructura.py` (fila 1a): `compose.yaml` tiene `minio` con imagen fijada (sin `latest`), perfil `almacen`, puertos en `127.0.0.1`, volumen con nombre y las dos credenciales con `:?` o con `:-`, según lo que fijó `E-4`; `_imagen_postgres` sigue encontrando una sola imagen; `.env.example` trae las cuatro claves del almacén activas con `CIMENTA_ALMACEN_CLAVE_SECRETA` vacía, `CIMENTA_SPA_ORIGEN=http://localhost:5173` activa y `CIMENTA_ALMACEN_ENDPOINT` solo comentada; el paso de `humo` genera esa clave con `openssl rand -hex` antes de `docker compose up`. Control sobre texto sintético con cada desvío | regresión y **rechazo** | `CA-R1`, `CA-13` | — |
| TC-45b | `test_tkt059_car1_humo_arranca_con_el_env_derivado`, en el mismo archivo (fila 8): con un mapa construido como lo hace `humo` (las claves activas de `.env.example` más las cuatro contraseñas generadas), `cargar_ajustes` no lanza; sin la clave secreta generada, lanza nombrándola | regresión y **rechazo** | `CA-R1` | — |
| TC-46 | Documentación coherente: los tres comandos de documentación en verde y cada fila de «Documentación afectada» de la entrega aplicada | regresión | `CA-13` | — |
| TC-47 | `test_tkt059_dominio_evaluar_previa`: tabla de casos con enteros como instantes (el tipo genérico lo permite), incluidos el solicitante antes que el estado, el borde `ahora == vence_en` → `CONFIRMABLE` y `ahora == vence_en + 1` → `VENCIDO`; y un caso con `datetime` construido en la prueba, para fijar que el tipo real también sirve | feliz y **rechazo** | `CA-7` | — |
| TC-48 | `test_tkt059_dominio_comparar_objeto`: `None` → `NO_SUBIDO`; tamaño distinto con hash igual → `TAMANO_DISTINTO`; hash distinto o `None` → `HASH_DISTINTO`; todo igual → `None` | feliz y **rechazo** | `CA-5`, `CA-7` | — |
| TC-49 | `test_tkt059_dominio_evaluar_declaracion`: bordes de cada límite, tipo inválido sin error de tamaño, varios defectos a la vez en el orden de la tabla, y el nombre con `NUL` o sustituto (casos `test_tkt059_ca03_dominio_nombre_*`) | feliz y **rechazo** | `CA-3` | — |
| TC-50 | `test_tkt059_dominio_tipos_y_disposicion`: ocho tipos y su categoría; `inline` solo imagen y video; `image/svg+xml` no admitido | feliz y **rechazo** | `CA-6`, `CA-8` | — |
| TC-51 | `test_tkt059_herramienta_almacen_local`: contra el contenedor, crea el bucket y una segunda llamada no falla; con un origen que no es local, termina con código 2 nombrando `CIMENTA_ALMACEN_ORIGEN` | feliz y **rechazo** | `CA-13` | — |
| TC-52 | `test_tkt059_ca04_el_detector_lee_rangos_acotados`: con un `leer_rango` en memoria que cuenta bytes, el libro de 26,000,000 bytes se reconoce leyendo ≤ 262144 bytes; un directorio central declarado de 2 MiB, una parte de 2 MiB y un ZIP64 → `application/zip` sin leerlos | **rechazo** y feliz | `CA-4` · `PA-T59.14` | — |
| TC-54 | `test_tkt059_ca14_cors_solo_desde_la_spa`, contra MinIO real con el CORS de pruebas de la fila 1b: `OPTIONS` a la URL de un objeto con `Origin: http://spa.prueba.test`, `Access-Control-Request-Method: PUT` y `Access-Control-Request-Headers: x-amz-checksum-sha256` → `Access-Control-Allow-Origin: http://spa.prueba.test` y `PUT` entre los métodos admitidos; el mismo preflight con `Origin: http://otro.prueba.test` → sin `Access-Control-Allow-Origin`; un `PUT` firmado con `Origin: http://spa.prueba.test` → `200` con `Access-Control-Allow-Origin` del mismo origen. En el caso (c1) de `E-5`, además, `herramientas.almacen_local` termina con código 2 si falta `CIMENTA_SPA_ORIGEN` | feliz y **rechazo** | `CA-14` | — |
| TC-53 | `test_tkt059_nombres_de_usuarios` (solo si la fila 11 corre): dos identificadores existentes y uno ajeno → solo los dos, con su nombre | feliz | `CA-8` | — |

**Mutación.** Cada mutante se aplica a mano, se corre su test, se anota en `impl.md` qué cayó y se revierte.

| # | Mutante | Test que debe ponerse rojo | Entrega |
|---|---|---|---|
| M-01 | `evaluar_previa`: `vence_en < ahora` por `not ahora < vence_en` (vencido también en el instante exacto) | `TC-47` (borde exacto); `TC-28` repite el borde por la API en 059d | 059a |
| M-02 | `evaluar_previa`: el solicitante después del estado | `TC-47` | 059a |
| M-02b | `confirmar_archivo`: comprobar el solicitante después de los pasos 3 a 6 | `TC-29` (variante `CADUCADO`) | 059d |
| M-03 | `comparar_objeto`: no comparar el hash | `TC-48`, `TC-20` | 059a |
| M-04 | `comparar_objeto`: una suma `None` cuenta como coincidente | `TC-48` y la variante sin suma de `TC-20` | 059a |
| M-05 | `evaluar_declaracion`: `>` por `>=` en el límite, y en otro intento el límite de imagen para los documentos | `TC-49` | 059a |
| M-05b | `registrar_archivo`: firmar la URL antes de evaluar la declaración | `TC-11` (el espía de `url_subida` registra la llamada) | 059c |
| M-06 | `detectar_tipo`: no mirar si la raíz es `svg` | `TC-25b` (el SVG); `TC-22` y `TC-23` lo repiten por la API en 059d | 059b |
| M-07 | `detectar_tipo`: aceptar como `.xlsx` cualquier ZIP con `[Content_Types].xml` | `TC-25b` (ZIP sin parte de libro y `.xlsm`) | 059b |
| M-08 | `detectar_tipo`: `forbid_dtd=False` | `TC-25b` (XML con `DOCTYPE` y con entidades) | 059b |
| M-09 | `confirmar_archivo`: asentar en una transacción aparte, después de confirmar | `TC-16` | 059d |
| M-10 | `confirmar_archivo`: lanzar el `ARCHIVO_CADUCADO` del vencido dentro del bloque | `TC-28` | 059d |
| M-11 | `disposicion_de`: `inline` para `application/pdf` | `TC-50`; `TC-31` lo repite por la API en 059e | 059a |
| M-12 | Ruta de descarga: `exigir_rol` admite también `COMPRAS` | `TC-36` | 059e |
| M-13 | Lector: no comprobar el estado | `TC-41` | 059e |
| M-14 | Barrido: `columna_marca="confirmado_en"` (nula en todo `PENDIENTE`, así que los barre todos) | `TC-37` (la fila de hace una hora) | 059e |
| M-15 | `repositorio.bloquear` sin `with_for_update()` | `TC-18` (B no queda en espera y `esperar_hasta` vence) | 059d |
| M-16 | `detectar_tipo`: leer el objeto entero con un solo rango | `TC-52` y `TC-17` | 059b |
| M-17 | Comprobador de `TC-43`: solo mira `response_class` declarada | El caso de control de `TC-43` | 059e |
| M-18 | Migración sin `REVOKE DELETE ON archivo FROM cimenta_aplicacion` | `TC-02` (el `DELETE` borra la fila) | 059a |
| M-19 | `confirmar_archivo` sin la traducción de `55P03` | `TC-18b` (responde `500`) | 059d |
| M-20 | CORS abierto: en (c1), `AllowedOrigins=["*"]` en `aplicar_cors`; en (c2), `MINIO_API_CORS_ALLOW_ORIGIN=*` en el contenedor de pruebas | `TC-54` (el otro origen recibe `Access-Control-Allow-Origin`) | 059a |
| M-21 | `url_subida` firma con `self._cliente` en lugar de `self._firmante` | `TC-08b` (la URL lleva el host del endpoint) | 059b |

No hay rutas de dinero, límites presupuestales ni congelado: los mutantes cubren el vencimiento, la integridad, el tipo, los permisos y el bloqueo, que son las rutas críticas de este ticket.

## Impacto

Análisis del arquitecto; `revisor-impacto` lo revisa en el gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `AjustesServidor` y `cargar_ajustes` | Todo arranque; TC-50 a TC-54 de TKT-057, TC-64 de TKT-015b | Con base y sin almacén, el servidor deja de arrancar | Es lo pedido (`CA-2`); `.env.example` y `humo` traen las variables desde 059a, antes de que sean obligatorias (059c); `TKT-057/TC-52` se ajusta en su conjunto de campos y en su aserción de nombres |
| `servidor/fabrica.py` | Todas las pruebas que construyen la aplicación | Un parámetro nuevo o un barrido más rompen llamadas existentes | `almacen` es opcional; el barrido de archivos va **después** del de importaciones y no cambia su error (TC-66 de TKT-015b) |
| `lifespan`: lector real en lugar de `leer_contenido_no_configurado` | Ejecutor de TKT-015b | Un archivo inexistente cambia de `RuntimeError` a `ArchivoNoLegible` | Las dos son excepciones; el ejecutor las convierte igual en `ARCHIVO_ILEGIBLE` |
| Nueva cabeza de Alembic | TC-20 y TC-21 de TKT-072; diseño de TKT-017a1 | Pruebas que fijan la cabeza en `0010`; choque de número con `0011` | `CABEZA` en TKT-072 (fila 2); regla de numeración `P-1` |
| `compose.yaml` | `conftest._imagen_postgres`, `humo`, el arranque local, la VPS de prueba (`docs/despliegue-prueba-vps.md`, `despliegue/compose.vps.yaml`) | Sin perfil, la interpolación de `${…:?}` haría fallar `up -d db` en `test`, en `prod` y en un `.env` local anterior, y los dos proyectos de la VPS chocarían en los puertos 9000 y 9001 | Perfil `almacen` (`P-14`) comprobado por `E-4`, con la variante `:-` si falla; la VPS no arranca MinIO |
| `identidad.interfaz` (si la fila 11 corre) | TKT-017b1; `test_tkt006_enrutador.py`, líneas 741 a 771 | Dos tickets crean la misma función o declaran dos `UsuarioResumen`; la lista exacta de `__all__` se pone en rojo | `P-5` y `P-13`: quien llega segundo reutiliza; el tester de la fila 11 ajusta la lista |
| `CUERPOS_VALIDOS` de `test_tkt057_csrf.py` | `TKT-057/TC-48` | Una ruta que muta sin entrada lo pone en rojo | Entrada nueva en la fila 12a |
| `frontend/src/api/generado/servidor.ts` | Cliente | Tipos nuevos | Se regenera y verifica en 059d y 059e |

**Fronteras entre módulos:** No. `archivos` importa solo `cimenta.identidad.interfaz` y `cimenta.auditoria.interfaz`; `servidor/` importa `cimenta.archivos.api.montaje` y `cimenta.archivos.interfaz`, como ya hace con `identidad` y `presupuesto`. `grafo-archivos` no cambia.

## Documentación afectada

Ajuste del 2026-11-11: lo que este diseño dice sobre el perfil `almacen`, `minio/minio` y el servicio en `compose.yaml` queda superado por `impl.md` («Ajustes respecto al design»): MinIO va en `compose.almacen.yaml`, sin perfil, con `pgsty/minio`.

| Entrega | Documento | Qué cambia |
|---|---|---|
| 059a | [Modelo de datos](../../../docs/03-modelo-datos.md) §12 | La fila `CADUCADO` de la tabla de estados (línea 1116): el objeto no se elimina en el barrido; lo recoge la regla de ciclo de vida del bucket (`PA-T59.3`). El rol de aplicación no tiene `DELETE` sobre `archivo` |
| 059a | Modelo de datos §14 | El diagrama de estados de `archivo` (línea 1298) y su texto (línea 1304): `PENDIENTE --> CADUCADO` por el barrido **o** por la confirmación de un vencido (`PA-T59.13`) |
| 059a | [Arranque local](../../../docs/arranque-local.md) | `docker compose -f compose.yaml -f compose.almacen.yaml up -d minio`, la herramienta del bucket y las variables del almacén; que `docker compose up -d db` sigue funcionando con un `.env` anterior que no las trae, y que hay que añadirlas antes de arrancar MinIO; se quita la marca «desde TKT-059» de la tabla de comandos |
| 059a | [Despliegue de prueba](../../../docs/despliegue-prueba-vps.md) | La línea 9 («no monta MinIO») pasa a decir que MinIO está en `compose.almacen.yaml`, que la VPS no carga: `up -d --wait db` de los pasos 5 y 7 no cambia y el `.env` de la VPS no necesita variables del almacén mientras no corra la aplicación con base; MinIO en la VPS lo despliega TKT-073. `despliegue/compose.vps.yaml`, `.claude/agents/ingeniero-despliegue.md` y la skill `sdd-desplegar` no cambian con la recomendación de `P-14`; si el gate elige otra opción que los afecte, se actualizan en esta entrega |
| 059a | [`conv-docker`](../../../.claude/skills/conv-docker/SKILL.md) §2 | El bloque `(asumido)` de las líneas 32 a 46 se sustituye por lo decidido: el servicio se llama `minio`, va en el perfil `almacen` y el bucket lo crea `herramientas.almacen_local`. La skill la comparten Claude Code y Cursor, así que no hay copia que regenerar |
| 059a | [`CLAUDE.md`](../../../CLAUDE.md) | Se quita la marca «desde TKT-059» de `docker compose up -d minio` y se añade `uv run --env-file ../.env python -m herramientas.almacen_local` a «Desde `backend/`» |
| 059a | [Convenciones](../../../docs/convenciones.md) | La línea de `compose.yaml` del árbol: PostgreSQL y MinIO |
| 059a | [Stack](../../../docs/06-stack-tecnologico.md) §10 | El párrafo «Desviación respecto a TKT-009»: MinIO entra en el trabajo `backend` por testcontainers, sin servicio en el flujo |
| 059b | [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md) y stack §4.6 | La lista blanca admite solo `.xlsx` entre las hojas de cálculo; el barrido no borra el objeto. ADR-016 recibe además, al inicio, un aviso que remite a TKT-073: el destino de producción será MinIO autoalojado en la VPS (decisión de la persona dueña del 2026-11-06), y el ADR que reemplaza su elección de destino es de TKT-073. TKT-059 no reescribe la decisión |
| 059b | ADR nuevo y su fila en [`docs/adr/README.md`](../../../docs/adr/README.md); conteo de ADR en `CLAUDE.md`, `README.md` y `llms.txt` | Ver «¿Merece ADR?» (`P-8`) |
| 059a | Arranque local | `CIMENTA_SPA_ORIGEN` y el CORS que aplica la herramienta o el servicio `minio`, según `E-5` (`CA-14`) |
| 059a | `.env.example` y `ci.yml` (`humo`) | Sección del almacén y clave secreta generada, según «Ajustes y variables»; los escribe `ingeniero-devsecops` en la fila 1a |
| 059a | [Arranque local](../../../docs/arranque-local.md) | Generar `CIMENTA_ALMACEN_CLAVE_SECRETA` |
| 059c | Arranque local | Que, desde esta entrega, la aplicación con base no arranca sin las cuatro variables del almacén |
| 059d | [Borrador OpenAPI](../../../docs/api/openapi.yaml) | «Cambio del borrador en 059d», incluido `CADUCADO` en `EstadoArchivo` |
| 059d | [Especificación de la API](../../../docs/07-especificacion-api.md) §2.8 | Los códigos de la confirmación y el `403` `NO_ES_SOLICITANTE` |
| 059e | Borrador OpenAPI | «Cambio del borrador en 059e» |
| 059e | [Tickets](../../../docs/05-tickets-trabajo.md) | Ficha de TKT-059: el barrido marca `CADUCADO` sin borrar el objeto; el rol de aplicación no tiene `DELETE`; el trabajo `backend` recibe MinIO por testcontainers. Tabla de dueños de los tests de escenario: TKT-059 es dueño de HDU-001 esc. 25 y 26, TKT-018 del 24 |
| 059e | Stack §6.6 | Las filas `RNF-06` y `RNF-19` enlazan los tests que las cumplen (`TC-11`, `TC-20`, `TC-23`, `TC-31`, `TC-33`, `TC-14`) |

## ¿Merece ADR?

**Sí, con `P-8`**, si `E-1` y `E-2` pasan: `docs/adr/20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md`, formato MADR. Un recién llegado preguntaría por qué la confirmación no calcula el hash y por qué lee el ZIP a trozos, y hubo opciones descartadas:

| Opción | Por qué se descarta |
|---|---|
| **Elegida:** suma SHA-256 firmada en la URL de subida, verificada por el almacén y leída de los metadatos; tipo por lecturas por rango acotadas | — |
| Descargar el objeto en la ruta y calcular el hash y el tipo | Una ruta `def` retendría un hilo del grupo durante la transferencia de hasta 50 MiB (ADR-013, ADR-016) |
| Confirmar en un trabajo de segundo plano | Añade un estado intermedio, un latido y un barrido más; la spec lo deja como alcance distinto si `E-1` falla |
| Confiar en el `ETag` | Es MD5 y en subidas por partes no es el hash del contenido: no sirve como prueba de `RNF-19` |
| Descargar solo la cabecera y aceptar cualquier ZIP como `.xlsx` | El stack §4.6 exige la comprobación estructural, y HDU-001 esc. 26 la prueba |

Consecuencia que el ADR declara: el destino de producción tiene que admitir la misma suma firmada. Con la decisión del 2026-11-06, ese destino es MinIO autoalojado en la VPS, el mismo software que `E-1` comprueba; la verificación contra R2 (`PA-T59.7`) deja de aplicar, y la de la versión de MinIO que despliegue TKT-073 es de ese ticket.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Si `boto3` lleva la suma a la cadena de consulta y MinIO no la verifica allí, el cliente podría subir otro contenido y la garantía de `CA-5` esc. 3 sería decorativa | `E-1` (c) lo comprueba antes de construir y escala si falla; aun así, la confirmación compara la suma de los metadatos y rechaza la ausente (`P-11`, `TC-20`), así que un objeto sin suma nunca llega a `DISPONIBLE` |
| 2 | Alta | La confirmación hace E/S externa con la fila bloqueada | La E/S está acotada (cabecera, cola y una parte del ZIP, más una copia dentro del almacén); el bloqueo solo lo disputa otra confirmación del mismo archivo; `TC-18` prueba la espera y `M-15` que el bloqueo existe |
| 3 | Media | `archivos_vida_url_lectura` contiene «lectura» y rompería TC-52 de TKT-057 sin que nadie lo advirtiera | El ajuste de TC-52 está escrito en «Ajustes y variables»; la intención de esa aserción (las contraseñas de los roles) se conserva sobre los campos `db_` |
| 4 | Media | Un `PENDIENTE` creado con el reloj de prueba podría barrerse al arrancar una aplicación de prueba cuyo `lifespan` corre después del alta | El barrido corre al entrar en el `TestClient`, antes de que la prueba dé de alta; las pruebas de arranque siembran `creado_en` relativo a `now()` |
| 5 | Media | El XML de un CFDI con `DOCTYPE` legítimo se rechazaría | Un CFDI no lleva `DOCTYPE`; rechazar todo `DOCTYPE` es lo que impide la expansión de entidades sin depender de detectar el ataque (`P-9`) |
| 6 | Media | `compose.yaml` con `:?` en las variables del almacén impediría `docker compose up -d db` en la VPS de prueba y a quien tenga un `.env` local anterior a este ticket (objeción B del orquestador y omisión de `revisor-impacto`) | Perfil `almacen` para `minio` (`P-14`), comprobado por `E-4`, con la variante `:-` y la comprobación en `herramientas.almacen_local` si la interpolación no respeta el perfil. `docs/arranque-local.md` y la guía de la VPS lo dicen (fila 4) |
| 7 | Alta | `copy_object` con `MetadataDirective="REPLACE"` puede perder `ChecksumSHA256`; si la transacción no confirma después, una segunda confirmación respondería `ARCHIVO_HASH_DISTINTO` por suma ausente aunque el contenido sea el declarado (objeción A del orquestador) | `E-1` (g) lo comprueba, también con `ChecksumAlgorithm="SHA256"`; la tabla «Reescritura del tipo y suma del objeto» fija el orden del paso 11 para cada resultado, incluido el orden B (confirmar la fila antes de reescribir, con reescritura idempotente), sin dejar la decisión a quien ejecuta |
| 8 | Media | Cuatro pruebas existentes fijan listas cerradas que el ticket amplía (`model_fields` en TC-52, la cabeza en TKT-072, `CUERPOS_VALIDOS` en `test_tkt057_csrf.py`, `__all__` de `identidad` en `test_tkt006_enrutador.py`) | Cada ajuste está asignado a su fila y a su tester en «Ajustes y variables» |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| MinIO no verifica la suma firmada (`PA-T59.6`) | Media | Bloquea el ticket | `E-1` antes de construir; `/sdd-escalar` |
| La imagen comunitaria de MinIO ya no se publica en Docker Hub | Media | Sin almacén de pruebas | `E-0` prueba Docker Hub y `quay.io`; si ninguno, `/sdd-escalar` |
| El MinIO de la VPS, en otra versión, se comporta distinto del de las pruebas en la suma o en el CORS | Baja | Producción aceptaría o rechazaría lo que las pruebas no previeron | TKT-073 fija la misma etiqueta de imagen de `compose.yaml` o repite `E-1` y `E-5` contra la suya. (La verificación en R2, `PA-T59.7`, ya no aplica) |
| La VPS expone MinIO con un nombre público distinto de la red interna | Media | Si alguien configura solo `CIMENTA_ALMACEN_ORIGEN` con la dirección interna, el navegador recibiría URL que no alcanza | Dos variables (`ENDPOINT` interno, `ORIGEN` público) y `TC-08b`; la configuración de la VPS es de TKT-073 |
| `puremagic` no reconoce HEIC o MP4 | Baja | Un tipo admitido se rechazaría | `E-3` y la firma propia de respaldo, decidida aquí |
| Quien corre `pytest` con `--env-file ../.env` incompleto ve fallar TC-54 de TKT-057 | Baja | Ruido local | El pipeline no fija variables de base en el trabajo `backend`; `arranque-local.md` indica completar el `.env` |
| Choque de número de migración con TKT-017 | Alta | Dos cabezas | `P-1` |
| TKT-058 despliega una aplicación con base posterior a 059c sin las variables del almacén | Media | El servidor no arranca en `test` ni en `prod` | Aviso para TKT-058 y para `/sdd-desplegar`: desde 059c, el `.env` de cada entorno necesita `CIMENTA_ALMACEN_ORIGEN`, `CIMENTA_ALMACEN_BUCKET`, `CIMENTA_ALMACEN_CLAVE_ACCESO` y `CIMENTA_ALMACEN_CLAVE_SECRETA` (y `CIMENTA_ALMACEN_ENDPOINT` si el servidor alcanza MinIO por la red interna), que fijará TKT-073 al desplegar MinIO en la VPS; se anota en el `delta.md` de 059c |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P-1 | Número de la migración, con `0011` reservado en el diseño de TKT-017 | La siguiente libre al ejecutar la fila 2 (`uv run alembic heads` + 1). Quien se fusione segundo renumera en su rama antes de fusionar: `revision`, `down_revision`, nombre de archivo, el texto «La bajada de 00NN se niega» y la constante `CABEZA` de las pruebas. La misma regla vale para TKT-017 |
| P-2 | Partición | Las cinco entregas de «Tamaño y partición propuesta», con sus reglas |
| P-3 | Destino y origen del almacén | **Sustituida** por la decisión de la persona dueña del 2026-11-06: dos variables, `CIMENTA_ALMACEN_ENDPOINT` (interna, opcional, por omisión el origen) y `CIMENTA_ALMACEN_ORIGEN` (pública, con la que se firma y que entra en la política de contenido), y dos clientes `boto3` en el adaptador |
| P-4 | «MB» de `PA-15` | Mebibytes: 15 MiB = 15,728,640 bytes, 50 MiB = 52,428,800 y 25 MiB = 26,214,400. El ejemplo de la spec (8 MB = 8,388,608 bytes) ya usa esa unidad |
| P-5 | El nombre de quien subió (`Archivo.subido_por`) | Reutilizar `nombres_de_usuarios` (`P-8` de TKT-017) y publicar `UsuarioResumen` en `cimenta.identidad.interfaz`; los crea quien llegue primero (fila 11 aquí o B1 en TKT-017b1) y el otro los reutiliza. Publicar el esquema en `identidad` evita dos componentes `UsuarioResumen` distintos en el OpenAPI |
| P-6 | Creación del bucket local (`conv-docker` lo deja abierto) | `herramientas/almacen_local.py`, como `contrasenas_roles`: sin una segunda imagen (`minio/mc`) que fijar y auditar. Alternativa: un servicio de una sola ejecución con `mc` en Compose |
| P-7 | MinIO en el trabajo `humo` | No: la aplicación no contacta al almacén al arrancar y ningún recorrido de humo toca archivos; el `.env` generado trae las variables y la clave secreta se genera con `openssl` |
| P-8 | ADR nuevo | Sí, el de «¿Merece ADR?», en 059b, con el conteo de ADR de `CLAUDE.md`, `README.md` y `llms.txt` subido en uno; si TKT-017a3 ya subió el suyo, el conteo queda en 41 |
| P-9 | XML con `DOCTYPE` | Rechazar todo `DOCTYPE`, no solo las entidades, con `tipo_detectado` `application/xml-dtd`. El stack §4.6 pide parsear hasta la raíz con `defusedxml`, y un CFDI no lleva `DOCTYPE` |
| P-10 | Confirmar o descargar un `ANULADO` (inalcanzable hasta TKT-066) | Confirmar → `ESTADO_NO_PERMITE_OPERACION`; descargar → `ARCHIVO_NO_DISPONIBLE` |
| P-11 | Objeto sin suma en los metadatos | `ARCHIVO_HASH_DISTINTO` con `hash_almacenado` omitido del detalle: sin suma no hay prueba de `RNF-19`, y el contrato no admite nulos en el detalle |
| P-12 | Alias del tipo declarado (`text/xml`, `image/jpg`, `image/heif`) | Comparación exacta, sin alias: en la fase 1 la única subida es el `.xlsx`, y los alias se deciden cuando la fase 2 suba evidencia |
| P-13 | Quién declara `UsuarioResumen`, que el diseño de TKT-017 no prevé (solo `nombres_de_usuarios`) | Una sola clase, en `identidad/api/esquemas.py`, publicada en `cimenta.identidad.interfaz`, la declara quien llegue primero entre la fila 11 de este ticket y TKT-017b1; el otro la importa. TKT-017b1 usa esa misma clase en `congelada_por`, `capturado_por` y `actualizado_por`. Así el OpenAPI publica un solo componente `UsuarioResumen`, el del borrador |
| P-15 · aprobada el 2026-11-06 | Nombre y lugar del origen de la SPA para el CORS (no existe ninguna variable: lo comprobé en `servidor/ajustes.py`, `frontend/vite.config.ts` y `.env.example`) | `CIMENTA_SPA_ORIGEN`, activa en `.env.example` con `http://localhost:5173` (el puerto de `vite.config.ts`), leída solo por `herramientas.almacen_local` o por la interpolación de `compose.yaml`, según `E-5`. No entra en `AjustesServidor` porque el servidor no la usa, y así TC-52 de TKT-057 no gana un campo más. En la VPS la fija TKT-073 con el origen público de la SPA. Alternativa: derivarla del origen de la petición en cada alta, que no sirve porque el CORS se configura en el almacén antes de cualquier petición |
| P-14 | `compose.yaml` con MinIO sin romper `docker compose up -d db` en la VPS de prueba ni en un `.env` local anterior | Perfil `almacen` para el servicio `minio`, con `:?` en sus credenciales si `E-4` confirma que un perfil inactivo no se interpola con error; si no, `:-` y la comprobación de las credenciales en `herramientas.almacen_local`. Alternativas: un `compose.minio.yaml` aparte que se añade con `-f` (más órdenes para todos), o `:-` sin perfil (la VPS levantaría MinIO con credenciales vacías y dos proyectos chocarían en 9000 y 9001) |
