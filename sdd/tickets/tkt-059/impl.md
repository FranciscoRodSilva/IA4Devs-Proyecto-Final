# Impl · TKT-059 · Módulo `archivos` mínimo: subida prefirmada, confirmación por hash y barrido

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

Este archivo es uno solo para las cinco entregas del paraguas y lleva una sección por entrega. Las entregas posteriores añaden la suya sin reescribir las anteriores.

## Entrega TKT-059a · Esquema, dominio e infraestructura de MinIO (filas 0 a 4)

Fecha de ejecución: 2026-11-11. Rama única del ticket: `tkt-059-archivos-minimo`, creada desde `Produccion` (`555ad65`). Las entregas se acumulan en ella, según la regla vigente de `CLAUDE.md`; el nombre por entrega que citaban `_index.md` y `design.md` queda sin efecto.

### Qué se implementó

La entrega deja listo el terreno del módulo `archivos` sin montar ninguna ruta:

- MinIO como almacén local y de pruebas, declarado en `compose.almacen.yaml`, con su herramienta `herramientas.almacen_local` que crea el bucket.
- Las fixtures de MinIO de `conftest.py` y el CORS de pruebas.
- La migración `0012` con la tabla `archivo`, sus invariantes 23 a 26 y la imposibilidad de borrar un archivo (`REVOKE DELETE`).
- Las tres reglas puras de `dominio/`: lista blanca de tipos, validación de la declaración y orden de las comprobaciones de la confirmación.

Las dependencias nuevas (`boto3`, `puremagic`, `boto3-stubs`, `testcontainers[minio]`, `types-defusedxml`) entraron con `pip-audit` sin vulnerabilidades.

### Resultado de los experimentos de la fila 0

Los scripts y sus salidas completas están en [`experimentos/`](experimentos/). Imagen usada en todos: `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`.

| Experimento | Resultado | Valor que fija |
|---|---|---|
| `E-0` | Pasa, tras una escalada (ver «Ajustes») | Imagen `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`, digest `sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372`. Trae `mc`; el entrypoint no afecta a `command: ["server", …]` |
| `E-1` | Pasa | La URL firma `content-length;host;x-amz-checksum-sha256`; el cliente debe enviar la cabecera `x-amz-checksum-sha256` con el SHA-256 en base64. Otro contenido del mismo tamaño: `400` y el objeto no existe. Otro tamaño: `403`. Sin la cabecera: `400`. `head_object` devuelve la suma. Caso **(g1)**: `copy_object` con `REPLACE` conserva la suma, así que rige el orden A. La descarga prefirmada devuelve `Content-Disposition: attachment; filename="a.pdf"` |
| `E-2` | Pasa | Un `.xlsx` de 26 004 994 bytes se reconoce con cinco rangos `206` y 74 702 bytes leídos (cota 262 144) |
| `E-3` | Pasa | La tabla `EXTENSIONES` del diseño sirve sin cambios. Hallazgo para la fila 6: `puremagic` no reconoce HEIC con marca mayor `mif1` ni `msf1` (devuelve `.sndr`), así que el detector necesita su firma propia para esas dos marcas |
| `E-4` | **No cumple la forma prevista** | Un servicio con perfil inactivo y `${…:?}` hace fallar `up -d db`. La variante `:-` arrancaría MinIO con `minioadmin:minioadmin` si faltan las variables. La persona dueña eligió el segundo archivo de Compose |
| `E-5` | Pasa, caso **(c2)** | `put_bucket_cors` responde `501`. Sin configuración, MinIO refleja cualquier origen. Con `MINIO_API_CORS_ALLOW_ORIGIN` el preflight y el `PUT` firmado solo reciben `Access-Control-Allow-Origin` para el origen de la SPA |

### Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-11 | La imagen de MinIO es `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`, no `minio/minio`. | `E-0` falló: `minio/minio` ya no se puede descargar (Docker Hub lo rechaza, quay.io pide autenticación y el repositorio de GitHub está archivado). Se comprobaron las alternativas con `docker manifest inspect`: la persona dueña eligió el fork `pgsty/minio`, que mantiene las etiquetas `RELEASE.*`. Es un fork comunitario de una sola organización; la procedencia de la imagen queda para el ADR de 059b y para TKT-073 (fijar por digest en producción) |
| 2026-11-11 | El servicio `minio` vive en `compose.almacen.yaml`, sin perfil, y se arranca con `docker compose -f compose.yaml -f compose.almacen.yaml up -d minio`. `compose.yaml` conserva solo `db`. | `E-4`: un perfil inactivo no evita la interpolación de `${…:?}`. La alternativa del diseño (`:-`) deja credenciales por omisión publicadas en `127.0.0.1`. Decisión de la persona dueña. `_imagen_minio()` de `conftest.py` lee `compose.almacen.yaml` |
| 2026-11-11 | No hay `aplicar_cors` en `herramientas/almacen_local.py` ni código de CORS; el CORS lo aplica `MINIO_API_CORS_ALLOW_ORIGIN` en el servicio y en el contenedor de pruebas. | `E-5` cayó en el caso (c2) del diseño. `CIMENTA_SPA_ORIGEN` alimenta esa variable en Compose |
| 2026-11-11 | La migración es la `0012` (`down_revision = "0011"`), no la «siguiente a `0010`». | La cabeza real era `0011` (`v0011_presupuesto_campos_sin_fuente`). La regla de numeración `P-1` dice tomar el siguiente número libre |
| 2026-11-11 | `test_tkt017_migracion.py` ajustado: en los dos tests de la guarda de la bajada de `0011`, la precondición pasa de «subir a `0011`» (operación vacía con la base en la cabeza) a una bajada explícita de `0012` a `0011`. Los asertos no cambian. | La migración nueva desplaza la cabeza, igual que el diseño previó para TKT-072 (`CABEZA = "0012"`). Esos dos tests dependen ahora de que `archivo` esté vacía, que es el caso de `base_de_prueba` |
| 2026-11-11 | `tools/tests/test_definicion_dependabot.py` (`TC-18`) admite `CIMENTA_ALMACEN_CLAVE_ACCESO` con el valor exacto `cimenta-local` como identificador público de desarrollo. | Dos pruebas existentes no podían cumplirse a la vez: `TC-18` exige `solo-desarrollo-*` en toda clave sensible con valor, y `test_tkt057_entorno.py` prohíbe esa cadena en `.env.example`. Opciones presentadas a la persona dueña; eligió admitir la variable en `TC-18`. La excepción es nominal (nombre y valor exactos), con ocho mutantes de rechazo. El supuesto «valor exacto, no solo el nombre» lo tomó el tester y es más estricto; se confirma en la revisión |
| 2026-11-11 | `TC-54` nace en verde. | El CORS de pruebas lo da la configuración de la fixture (`E-5` c2), no código de producción. Lo valida el mutante `M-20` |

Supuestos de redacción del dominio que se anotan para confirmar en la revisión: `tipo_admitido` no normaliza el tipo (recibe tipos canónicos de la detección; solo `evaluar_declaracion` hace `strip().lower()`), la longitud de 255 del nombre se mide sobre el nombre sin recortar, y los MiB del mensaje de `FUERA_DE_RANGO` salen de una división entera.

Aviso de alcance para la persona dueña (`CA-14`): CORS es una barrera del navegador. MinIO acepta el `PUT` firmado desde cualquier origen; lo que se prueba es lo que ve el navegador. La frase «el almacén solo acepta el `PUT` firmado desde el origen de la SPA» de la spec describe más de lo que CORS garantiza. Decidido el 2026-11-11 por la persona dueña: ajustar el texto. `spec.md` (`CA-14`) y `design.md` (Estrategia) dicen ahora que CORS acota lo que el navegador puede subir, no lo que el almacén acepta de otros clientes.

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/archivos/dominio/tipos.py` | nuevo | dominio |
| `backend/cimenta/archivos/dominio/declaracion.py` | nuevo | dominio |
| `backend/cimenta/archivos/dominio/confirmacion.py` | nuevo | dominio |
| `backend/migraciones/versions/v0012_archivos_archivo.py` | nuevo | infraestructura |
| `backend/herramientas/almacen_local.py` | nuevo | infraestructura |
| `compose.almacen.yaml` | nuevo | infraestructura |
| `compose.yaml` | modificado (comentario de cabecera) | infraestructura |
| `.env.example` | modificado (sección del almacén) | infraestructura |
| `.github/workflows/ci.yml` | modificado (clave del almacén en `humo`) | infraestructura |
| `backend/pyproject.toml`, `backend/uv.lock` | modificados (dependencias, `mypy` estricto) | infraestructura |
| `backend/tests/conftest.py` | modificado (fixtures de MinIO) | pruebas |
| `backend/tests/test_tkt059_infraestructura.py`, `_herramienta.py`, `_cors.py`, `_migracion.py`, `_dominio.py` | nuevos | pruebas |
| `backend/tests/test_tkt017_migracion.py`, `test_tkt072_migracion.py` | modificados (cabeza `0012`) | pruebas |
| `tools/tests/test_definicion_dependabot.py` | modificado (`TC-18`) | pruebas |
| `docs/03-modelo-datos.md`, `docs/arranque-local.md`, `docs/despliegue-prueba-vps.md`, `docs/convenciones.md`, `docs/06-stack-tecnologico.md`, `.claude/skills/conv-docker/SKILL.md`, `CLAUDE.md` | modificados | documentación |
| `sdd/tickets/tkt-059/experimentos/`, `sdd/tickets/tkt-059/rojo/fila-3.txt` | nuevos (evidencia) | documentación |

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-45a | `test_tkt059_car1_compose_con_minio` y tres más, con controles | regresión y **rechazo** | `CA-R1`, `CA-13` | FALLA (3) | PASA |
| TC-51 | `test_tkt059_herramienta_almacen_local` (+ rechazo de origen no local y de variable ausente) | feliz y **rechazo** | `CA-13` | FALLA (8) | PASA |
| TC-54 | `test_tkt059_ca14_cors_solo_desde_la_spa` (+ `PUT` firmado) | feliz y **rechazo** | `CA-14` | nace en verde (ver «Ajustes»); el mutante `M-20` lo pone en rojo | PASA |
| TC-01 a TC-04 | `test_tkt059_ca01_*` | feliz y **rechazo** | `CA-1` | FALLA (17) | PASA |
| TC-47 a TC-50 | `test_tkt059_dominio_*` y dos de pureza | feliz y **rechazo** | `CA-3`, `CA-5` a `CA-8` | FALLA (75) | PASA |

### Ciclo TDD por fila

| Fila | Rojo | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| 0 | No aplica (sin código) | `tester-backend` | Línea base y experimentos, ver arriba | No aplica |
| 1a | `3 failed, 36 passed` | `tester-backend` → `ingeniero-devsecops` | `39 passed`; `tools/tests` 518 OK | No aplica (configuración); el control de la excepción de `TC-18` tiene su propia mutación, abajo |
| 1b | `8 failed, 2 passed` | `tester-backend` → `desarrollador-aplicacion` | `10 passed` | Con la fila 4 (`M-20`) |
| 2 | `17 failed, 8 passed` | `tester-backend` → `desarrollador-sql` | `32 passed` (tres suites de migración); filtro `migracion or esquema or semilla`: `209 passed` | Con la fila 4 (`M-18`) |
| 3 | `75 failed`, ver [`rojo/fila-3.txt`](rojo/fila-3.txt) | `tester-backend` → `desarrollador-dominio` | `75 passed` | Con la fila 4 |
| 4 | — | `tester-backend`; el orquestador para la documentación | ver abajo | Sí |

Notas de rojo: en las filas 1b y 3 los rojos son por ausencia del módulo (`herramientas.almacen_local`; `cimenta.archivos.dominio.*`), que es el rojo de una capa nueva según el diseño («el módulo no existe»). El import está dentro del test, así que no es un error de colección.

Salida literal del rojo de la fila 1a:

```text
FAILED tests/test_tkt059_infraestructura.py::test_tkt059_car1_compose_con_minio
FAILED tests/test_tkt059_infraestructura.py::test_tkt059_car1_env_example_seccion_del_almacen
FAILED tests/test_tkt059_infraestructura.py::test_tkt059_car1_humo_genera_la_clave_del_almacen
3 failed, 36 passed in 2.50s
```

Rojo de la fila 1b:

```text
FAILED tests/test_tkt059_herramienta.py::test_tkt059_herramienta_almacen_local
FAILED …::test_tkt059_herramienta_almacen_local_rechaza_origen_no_local[…] (3)
FAILED …::test_tkt059_herramienta_almacen_local_rechaza_variable_ausente[…] (4)
8 failed, 2 passed in 2.52s      (ModuleNotFoundError: herramientas.almacen_local)
```

Rojo de la fila 2:

```text
17 failed, 8 passed in 6.47s
AssertionError: Falta la migración 0012: la tabla archivo no existe (TKT-059, fila 2)   (15 + TC-04)
CommandError: Can't locate revision identified by '0012'                                  (TC-03)
```

#### Evidencia de ejecución al cerrar (con `docker info` respondiendo, servidor 29.9.3)

```text
uv run pytest -q -ra          →  2905 passed, 26 skipped in 601.07s (0:10:01)
uv run ruff format --check .  →  297 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 297 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 37; hallazgos: 0
uv run alembic heads          →  0012 (head)
pip-audit (como el pipeline)  →  No known vulnerabilities found
python -m unittest discover -s tools/tests →  Ran 518 tests … OK
python tools/extraer_mermaid.py            →  OK
```

Los 26 saltos son los conocidos de `PA-T3` (variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` sin definir). La línea base previa a los cambios era `2778 passed, 26 skipped`.

#### Mutación en rutas críticas (fila 4)

Huella SHA-256 de todos los `.py` de `backend/` antes y después de cada mutante: `d5d1e7628f10dc6460e06d993b21c7b0e5222e9e4e4be245122dbc4c678b83e7` (idéntica). Un mutante a la vez, con copias previas fuera del repositorio.

| Mutante | Test que cae | Razón |
|---|---|---|
| `M-01` · vencido también en el instante exacto | `test_tkt059_dominio_evaluar_previa[PENDIENTE-PROPIO-100-CONFIRMABLE]` | Devuelve `VENCIDO` en vez de `CONFIRMABLE` |
| `M-02` · solicitante después del estado | `…evaluar_previa[DISPONIBLE-AJENO-50-NO_ES_SOLICITANTE]` | Devuelve `YA_DISPONIBLE` |
| `M-03` · no comparar el hash | `…comparar_objeto[objeto5-HASH_DISTINTO]` | Devuelve `None` |
| `M-04` · suma `None` cuenta como coincidente | `…comparar_objeto[objeto6-HASH_DISTINTO]` | Devuelve `None` |
| `M-05` · `>` por `>=` en el límite | `…evaluar_declaracion_limite_por_categoria[image/jpeg-15728640-…]` | Un tamaño igual al límite se rechaza |
| `M-05` · límite de imagen para documentos | `…evaluar_declaracion[…25 MB…documentos]` | El mensaje trae 15 MB |
| `M-11` · `inline` para PDF | `…tipos_y_disposicion_por_tipo[application/pdf-DOCUMENTO-attachment]` | Devuelve `inline` |
| `M-18` · migración sin `REVOKE DELETE` | `…el_rol_de_aplicacion_no_borra_archivos[delete]` y `…la_migracion_sube_y_baja` | El `DELETE` borra la fila; el verificador de privilegios ve `DELETE` |
| `M-20` · `MINIO_API_CORS_ALLOW_ORIGIN=*` | `test_tkt059_ca14_cors_solo_desde_la_spa` | El otro origen recibe `Access-Control-Allow-Origin`. El caso del `PUT` firmado no se ejercitó con este mutante (`pytest -x`) |

Los mutantes del control de `TC-18` (excepción nominal): ocho subcasos de rechazo, incluidos exención solo por nombre, por prefijo, solo por valor y por todo el prefijo del almacén. Cayeron todos; un quinto mutante (saltarse la rama de forma) es equivalente con la regla de valor exacto.

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | — | `haiku` | — |
| Fila 0 | `tester-backend` | `haiku` | `haiku` | — |
| Fila 1a · rojo | `tester-backend` | `haiku` | `haiku` | — |
| Fila 1a · verde | `ingeniero-devsecops` | `haiku` | `sonnet` | La definición del agente y la tabla del paso 2b fijan `sonnet` para pipeline, imagen y dependencias |
| Fila 1a · `TC-18` | `tester-backend` | `haiku` | `haiku` | — |
| Fila 1b · rojo | `tester-backend` | `haiku` | `haiku` | — |
| Fila 1b · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | Disparador del diseño (permisos de un rol) |
| Fila 2 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador del diseño |
| Fila 2 · ajuste de TKT-017 | `tester-backend` | `haiku` | `haiku` | — |
| Fila 3 · rojo y verde | `tester-backend`, `desarrollador-dominio` | `haiku` | `haiku` | — |
| Fila 4 · mutantes y suite | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 4 · documentación | agente general | — | `sonnet` | Documentación de la entrega |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |

Las ejecuciones se interrumpieron una vez por el límite de uso de la cuenta (fila 4); los dos agentes se reanudaron y se comprobó antes que el árbol no tenía ningún mutante aplicado.

### Resultado contra los criterios de aceptación (alcance de 059a)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (tabla e invariantes 23 a 26, sin `DELETE`, bajada) | `[M]` | Cumplido | TC-01 a TC-04, `M-18` |
| `CA-2` (almacén en Compose y pruebas, destino cambia solo por endpoint) | `[M]` | Parcial: la mitad de 059a (MinIO en Compose, fixtures); las variables y el adaptador son de 059b y 059c | TC-45a, TC-51 |
| `CA-3`, `CA-5` a `CA-8` (reglas puras del dominio) | `[M]` | Reglas cubiertas; los casos de uso, de 059c a 059e | TC-47 a TC-50 |
| `CA-13` (documentación y herramienta) | `[M]` | Cumplido para 059a | TC-45a, TC-51, `verificar_docs.py` |
| `CA-14` (CORS) | `[M]` | Cumplido en lo que CORS garantiza; ver el aviso de alcance | TC-54, `M-20` |
| `CA-R1` | regresión | Cumplido | Suite completa `2905 passed` |

HDU-001 esc. 25 y 26: 059a cubre sus reglas puras con `test_tkt059_dominio_*`; los tests con el escenario en el nombre llegan en 059c a 059e según sus filas del diseño.

### Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` en la reauditoría (primer veredicto: `REQUIERE CAMBIOS` por F001) | F001 (Menor), resuelto | 2 |
| `auditor-sql` | `APROBADO` | O-01 a O-03 (observaciones) | 1 |
| `auditor-codigo` | No despachado en esta entrega | — | — |
| `auditor-seguridad` | No despachado en esta entrega (no hay endpoint, ruta ni sesión; los secretos los revisó `auditor-arquitectura`) | — | — |
| `auditor-docs` | Pendiente: lo despacha `/sdd-revisar` | — | — |

#### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | `auditor-arquitectura` | Menor | `sdd/tickets/tkt-059/` | Faltaba `impl.md` con la evidencia de los experimentos de la fila 0 | Resuelto con este archivo y con [`experimentos/`](experimentos/); la reauditoría lo confirmó |
| O1 | `auditor-arquitectura` | Observación | `compose.almacen.yaml` | La imagen es un fork comunitario fijado por etiqueta; el digest va solo en un comentario. Conviene un ADR o nota que lo registre, y fijar por `@sha256:` en producción | Resuelto: la imagen ya lleva etiqueta y digest en `compose.almacen.yaml`, y el ADR `20261111-almacen-local-en-compose-aparte.md` (059a) registra la decisión; la procedencia del fork se revisa en TKT-073 |
| O2 | `auditor-arquitectura` | Observación | `compose.almacen.yaml` | `healthcheck: mc ready local` no se comprobó con `docker compose up`; `E-0` sí confirmó `mc ready local` dentro del contenedor | Anotado: la verificación de `E-0` lo cubre |
| O3 | `auditor-arquitectura` | Observación | `test_definicion_dependabot.py` | La excepción de `TC-18` es decisión de la persona dueña | Resuelto: consta en «Ajustes» |
| O-01 | `auditor-sql` | Observación | `v0012:88` | El rol de aplicación conserva `UPDATE` sobre toda la tabla (lo exige `FOR UPDATE`); el hash lo protege la bitácora, no el esquema. Se podría restringir con `GRANT UPDATE (columnas)` | Decisión de la persona dueña, no bloquea |
| O-02 | `auditor-sql` | Observación | `v0012:60-61` | Las dos claves foráneas a `usuario` no tienen índice | Sin acción |
| O-03 | `auditor-sql` | Observación | `v0012:52` | `hash_sha256 char(64)` sin `CHECK` de formato | Sin acción: lo valida el dominio |

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/tickets/tkt-018b/spec.md` y `_index.md` | `verificar_docs.py` reporta tres enlaces rotos (a `design.md` e `impl.md`, que aún no existen) y un ancla inexistente `08-wireframes.md#3-importación-del-presupuesto`. Son de TKT-018b | Baja |
| 18 archivos modificados | Tienen CRLF en la copia de trabajo y LF en el índice; Git los normaliza al hacer commit | Informativa |
| `heic` con marca `mif1`/`msf1` | `puremagic` no lo reconoce; lo resuelve la fila 6 (059b) con firma propia | Hecho en 059b |

### Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/03-modelo-datos.md` §12 y §14 | `CADUCADO` no elimina el objeto (ciclo de vida del bucket, `PA-T59.3`); el rol de aplicación no tiene `DELETE` sobre `archivo`; `PENDIENTE → CADUCADO` por el barrido o por la confirmación de un vencido (`PA-T59.13`) |
| `docs/arranque-local.md` | Sección «Almacén de objetos»: `compose.almacen.yaml`, la imagen `pgsty/minio`, el comando con dos archivos, `herramientas.almacen_local`, variables, `CIMENTA_SPA_ORIGEN` y CORS, generación de la clave secreta; `up -d db` sigue funcionando con un `.env` anterior |
| `docs/despliegue-prueba-vps.md` | `compose.yaml` solo declara `db`; la VPS no carga `compose.almacen.yaml`; MinIO en la VPS es de TKT-073 |
| `.claude/skills/conv-docker/SKILL.md` §2 | El bloque `(asumido)` pasa a lo decidido |
| `CLAUDE.md` | Comando real de MinIO con dos archivos y `herramientas.almacen_local` en los comandos de `backend/` |
| `docs/convenciones.md`, `docs/06-stack-tecnologico.md` §10 | Árbol con `compose.almacen.yaml`; MinIO entra al trabajo `backend` por testcontainers |

Pendientes de otras entregas, sin tocar aquí: aviso en ADR-016 y ADR de la confirmación (059b); OpenAPI y especificación de la API (059d y 059e); fichas de `docs/05-tickets-trabajo.md` y `§6.6` del stack (059e).

`python tools/verificar_docs.py` → falla solo por los cuatro problemas ajenos de TKT-018b descritos arriba (corrida del 2026-11-11: 293 documentos, 164 escenarios, 73 tickets, 39 invariantes, 42 ADR).

### Verificación final de la entrega

- [x] Criterios de 059a cumplidos con evidencia (los restantes del paraguas son de 059b a 059e)
- [x] Ciclo TDD completo en cada fila con código: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas críticas
- [x] Todas las auditorías despachadas en esta entrega `APROBADO` (`auditor-arquitectura` tras reauditar, `auditor-sql`); `auditor-docs` lo despacha `/sdd-revisar`
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada por 059a actualizada en este cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama correcta; sin secretos en el diff (solo valores de prueba declarados)

### Revisión de la entrega 059a (`/sdd-revisar`, 2026-11-11)

Suite ejecutada de nuevo por el revisor, sin fiarse del cierre de `/sdd-ejecutar`: `2905 passed, 26 skipped` antes de las correcciones; tras ellas, `2913` (ciclo 1) y `2916` (ciclo 2).

#### Ciclos de corrección

| Ciclo | Auditor | Hallazgos | Quién | Resultado |
|---|---|---|---|---|
| 1 | `auditor-codigo` | F001 y F002 (Mayores: la rama de `ValueError` de `_origen_local` y el código de salida 1 de `almacen_local` sin test); F003 a F007 (Menores) | `tester-backend` (tests, conftest), `corrector-revision` (`declaracion.py`) | Resueltos; la reauditoría halló F008 |
| 1 | `auditor-seguridad` | F001 (diferencial de parseo entre `urlsplit` y `urllib3`), F002 (imagen sin digest), F003 (secreto literal en los experimentos) | `corrector-revision` | Resueltos; F004 (`UPDATE` sobre toda la tabla) queda como deuda aceptada, es la `O-01` de `auditor-sql` |
| 1 | `auditor-docs` | F001 (Mayor: falta ADR), F002 a F006, F008 (Menores y Observaciones) | agente de documentación | Resueltos, incluido el ADR `20261111-almacen-local-en-compose-aparte.md`; la reauditoría halló N-1, N-2 y N-4 (Menores de redacción) y F007 y F009 (Observaciones) |
| 2 | `auditor-codigo` | F008 (Mayor, nuevo): los controles de esquema y de barra invertida de `_origen_local` sin test | `tester-backend` | Resuelto: tres orígenes nuevos, cada mutante cae |
| 2 | `auditor-docs` | N-1, N-2, N-3, N-4, F007, F009 | El orquestador, con el texto literal del auditor, y `tester-backend` para el docstring de `tools/tests` | Resueltos sin reauditar, por el criterio de parada de redacción (paso 4 de `/sdd-revisar`); se comunican a la persona dueña en este registro |

Mutantes añadidos en la revisión (huellas SHA-256 de los `.py` de `backend/` idénticas antes y después):

| Mutante | Test que cae |
|---|---|
| `except ValueError: return True` en `_origen_local` | `rechaza_origen_no_local[http://[::1]` |
| Quitar `"@" in partes.netloc` | `rechaza_origen_no_local[http://user@localhost:9000]` |
| Quitar el control del esquema | `[ftp://localhost:9000]` y `[file://127.0.0.1/x]` |
| Quitar `"\\" in origen` | `[http://localhost:9000\]` |
| `return 1` por `return 0` en `main` | `…error_del_almacen_devuelve_1` y `…servidor_inalcanzable_devuelve_1` |
| `M-20` sin `-x` | `test_tkt059_ca14_cors_solo_desde_la_spa` y `…_en_el_put_firmado` |

#### Verificación final (copiada de la última corrida)

```text
docker info                   →  servidor 29.9.3
uv run pytest -q -ra          →  2916 passed, 26 skipped in 603.00s (0:10:02)
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 297 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
python -m unittest discover -s tools/tests →  Ran 518 tests … OK
python tools/verificar_docs.py →  293 documentos, 42 ADR; falla solo por los cuatro problemas ajenos de TKT-018b
```

| Auditor | Veredicto final |
|---|---|
| `auditor-arquitectura` | `APROBADO` (reauditoría tras F001) |
| `auditor-sql` | `APROBADO` |
| `auditor-codigo` | `APROBADO` (ciclo 2) |
| `auditor-seguridad` | `APROBADO` (ciclo 1) |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: N-1, N-2, N-3, N-4, F007 y F009, solo de redacción, resueltos con el texto literal del auditor |

Se queda fuera de esta entrega, por ser de otro ticket: los cuatro problemas de `verificar_docs.py` en `sdd/tickets/tkt-018b/` (`F000` del auditor, ajeno). Deuda aceptada: `O-01` de `auditor-sql`, el rol de aplicación conserva `UPDATE` sobre toda la tabla `archivo`. Observaciones del auditor de código para las entregas siguientes: la división entera de los MiB en el mensaje de `FUERA_DE_RANGO` con límites que no sean múltiplo de 1 MiB (`O1`), el llamador de `tipo_admitido` (`O2`) y la unificación de los clientes `boto3` cuando exista `crear_almacen_s3` (fila 5). De seguridad para 059b: el rechazo de `NUL` en `nombre_original`, que la clave del objeto no se derive del nombre, forzar `response-content-disposition` y `nosniff`, y guardar el tipo normalizado.

Criterios de la entrega 059a: todos los `[M]` de su alcance cumplidos con evidencia (ver la tabla de arriba); `CA-2` y `CA-3` a `CA-8` quedan completos en 059b a 059e. Desviaciones: las de «Ajustes respecto al design».
