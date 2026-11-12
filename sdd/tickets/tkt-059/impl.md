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

## Entrega TKT-059b · Adaptadores del almacén (filas 5 a 7)

Fecha de ejecución: 2026-11-11. Misma rama del ticket, `tkt-059-archivos-minimo`, partiendo del commit de cierre de 059a (`1fce498`).

### Qué se implementó

- El puerto `AlmacenObjetos` y el adaptador `AlmacenS3`, con dos clientes `boto3`: el firmante usa el origen público y el cliente de operaciones usa el endpoint interno (o el origen, si falta).
- El detector del tipo por los bytes, `detectar_tipo`, con lecturas por rango acotadas: reconoce JPEG, PNG, WebP, HEIC, MP4, PDF, XML y `.xlsx`, y rechaza SVG, `.xlsm`, ZIP genérico y XML con `DOCTYPE` o entidades.
- El ADR `20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md` y los avisos del ADR-016 y del stack §4.6.

### Ajustes respecto al design (059b)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-11 | `UrlFirmada` vive en `dominio/url_firmada.py` (dataclass congelado sin lógica) y `aplicacion/puertos.py` la re-exporta; el diseño la ponía en `puertos.py`. | `infraestructura` construye `UrlFirmada` y no puede importar `aplicacion` (contrato `esqueleto-capas`, mismo precedente que `identidad/infraestructura/contrasenas.py`). Los imports de los tests no cambian |
| 2026-11-11 | El detector quita el BOM UTF-8 y los blancos iniciales antes de decidir si la cabecera es XML. | El diseño decía «sin BOM ni blancos iniciales», pero `puremagic` no reconoce el XML con BOM ni con blancos (lista vacía) y `TC-25` exige `application/xml`. El código ya coincide con esta lectura |
| 2026-11-11 | La cabecera local del ZIP se lee en 30 bytes; las longitudes de nombre y extra salen de ahí y los datos comprimidos se leen por su posición calculada. | Menos bytes leídos y mismo resultado. El diseño decía «30 bytes más nombre y extra» |
| 2026-11-11 | `TC-08` busca los nombres de destino como palabra completa y lleva un control sobre texto sintético. | El test original buscaba subcadenas y «dominio» contiene «minio», palabra que el adaptador necesita en `from cimenta.archivos.dominio…`. Error del propio test, corregido por `tester-backend` |
| 2026-11-11 | `TC-33` sincroniza la firma con el inicio de un segundo y sondea el `403` sin `sleep`. | `X-Amz-Date` tiene precisión de segundo; con una vida de 1 s una URL firmada al final de un segundo podía caducar antes del primer `GET`. `esperar_hasta` no existe todavía en `conftest.py` (lo sube la fila 12a), así que el sondeo vive en el archivo de pruebas |
| 2026-11-11 | La mutación descubrió una laguna (`M-08c`, `forbid_dtd=False` en la parte del ZIP) y la auditoría tres huecos más: la suma firmada, el tope de descompresión y el nombre hostil de la descarga. Se añadieron cinco tests y todos los mutantes caen. | Ver «Mutación» y «Auditorías». El test del tope de descompresión añade una aserción de memoria (`tracemalloc`, tope 16 MiB), porque con `decompress(datos)` sin tope el resultado era idéntico y 64 MiB se descomprimen en milisegundos |

Decidido el 2026-11-11 por la persona dueña, que deja el diseño como está: el diseño aprobado clasifica como `video/mp4` cualquier `ftyp` que no sea marca HEIC, de modo que `avif`, `qt` (QuickTime) y `3gp*` entrarían como vídeo, y un AVIF con marca mayor `mif1` sale como `image/heic`. Es benigno porque el tipo se reescribe y todo sigue dentro de la lista blanca, y se acepta ese comportamiento; si más adelante esos formatos deben tener tipo propio o quedar fuera, será un cambio de diseño aparte.

### Archivos tocados (059b)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/archivos/aplicacion/puertos.py` | nuevo | aplicación |
| `backend/cimenta/archivos/dominio/url_firmada.py` | nuevo | dominio |
| `backend/cimenta/archivos/infraestructura/almacen_s3.py` | nuevo | infraestructura |
| `backend/cimenta/archivos/infraestructura/detector_tipo.py` | nuevo | infraestructura |
| `backend/tests/test_tkt059_almacen.py`, `test_tkt059_detector.py` | nuevos | pruebas |
| `backend/tests/conftest.py` | modificado (fixture `almacen`) | pruebas |
| `docs/adr/20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md` | nuevo | documentación |
| `docs/adr/20261001-almacenamiento-de-objetos.md`, `docs/adr/README.md`, `docs/06-stack-tecnologico.md`, `CLAUDE.md`, `README.md`, `llms.txt` | modificados (aviso de TKT-073, lista blanca, conteo a 43 ADR) | documentación |

### Pruebas y ciclo TDD por fila (059b)

| Fila | Rojo | Ejecutó | Verde | Mutantes |
|---|---|---|---|---|
| 5 | `2 failed, 7 errors in 2.21s` (`ModuleNotFoundError` de `almacen_s3` y `puertos`, dentro de la fixture o del test) | `tester-backend` → `desarrollador-aplicacion` | `10 passed` tras corregir `TC-08` | `M-21` |
| 6 | `31 failed in 0.50s` (`ModuleNotFoundError: …detector_tipo`) | `tester-backend` → `desarrollador-aplicacion` | `31 passed` | `M-06`, `M-07`, `M-08`, `M-16` y extras |
| 7 | No aplica (cierre) | `tester-backend`; el orquestador para la documentación | Suite completa, abajo | Sí |

Los rojos de las filas 5 y 6 son por la ausencia de un módulo nuevo, que es el rojo de una capa nueva según el diseño; el import está dentro del test o de la fixture, así que no es un error de colección.

| # | Test | Criterio |
|---|---|---|
| TC-08 | `test_tkt059_ca02_el_destino_cambia_solo_por_endpoint` (+ control del comprobador) | `CA-2` |
| TC-08b | `test_tkt059_ca02_las_url_llevan_el_origen_publico` y variante sin endpoint | `CA-2` |
| TC-21 | `test_tkt059_ca05_el_almacen_rechaza_la_subida_distinta`, la de otro tamaño y `…_una_suma_distinta_de_la_firmada` | `CA-5` |
| TC-33 | `test_tkt059_ca08_la_url_caduca` | `CA-8` |
| TC-25 | `test_tkt059_ca06_el_detector_reconoce_la_lista_blanca` (19 casos) | `CA-6` |
| TC-25b | `test_tkt059_ca06_el_detector_rechaza_lo_no_admitido` (19 casos, con los dos `DOCTYPE` en el ZIP) | `CA-6` |
| TC-52 | `test_tkt059_ca04_el_detector_lee_rangos_acotados` (4) y `…_parte_deflate_que_expande_mas_del_maximo` | `CA-4`, `PA-T59.14` |
| — | `test_tkt059_ca08_la_disposicion_neutraliza_nombres_hostiles` | `CA-8` |

#### Evidencia de ejecución al cerrar (corrida del 2026-11-11, anterior a los cinco tests añadidos después)

```text
uv run pytest -q -ra          →  2959 passed, 26 skipped in 582.70s (0:09:42)
uv run ruff format --check .  →  303 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 303 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
pip-audit (como el pipeline)  →  No known vulnerabilities found
python -m unittest discover -s tools/tests →  Ran 518 tests … OK
```

Después de esa corrida se añadieron cinco tests por la laguna `M-08c` y la auditoría (dos en el detector, tres en el almacén); los dos archivos afectados dieron `46 passed` y `ruff`, `mypy` y `lint-imports` salieron limpios. La suite completa se volvió a correr en `/sdd-revisar`; su resultado está en la «Verificación final» de esta entrega.

#### Mutación en rutas críticas (059b)

Huella SHA-256 de los `.py` de `backend/` idéntica antes y después de cada mutante; un mutante a la vez, con copias fuera del repositorio.

| Mutante | Test que cae |
|---|---|
| `M-06` · no mirar si la raíz es `svg` | `…rechaza_lo_no_admitido[svg-con-declaracion]` y `[svg-sin-declaracion]` |
| `M-07` · cualquier ZIP con `[Content_Types].xml` es `.xlsx` | `…[zip-sin-parte-de-libro]` y `[xlsm-con-macros]` |
| `M-08a` · `forbid_dtd=False` en el parser de XML | `…[xml-con-doctype]` |
| `M-08b` · los tres `forbid_*=False` | `[xml-con-doctype]` y `[xml-con-entidades]` |
| `M-08c` · `fromstring(parte, forbid_dtd=False)` | Sobrevivía; ahora cae `zip-con-doctype-en-content-types` |
| `M-16` · leer el objeto entero en un rango | `…lee_rangos_acotados[libro-26-mb]`, `[directorio-2-mib]` y `[parte-2-mib]` |
| `M-21` · `url_subida` firma con `self._cliente` | `test_tkt059_ca02_las_url_llevan_el_origen_publico` (contra MinIO real) |
| Quitar `msf1` de las marcas HEIC | `…reconoce_la_lista_blanca[heic-marca-msf1]` |
| `MAXIMO_PARTE = 10 MiB` | `…lee_rangos_acotados[parte-2-mib]` |
| `forbid_entities=False` solo | Sobrevive: equivalente, `forbid_dtd=True` corta antes de que se declare una entidad |
| Borrar `"ChecksumSHA256"` de `Params` (auditoría `F001`) | `…una_suma_distinta_de_la_firmada` (200 en lugar de 403) |
| `decompress(datos)` sin tope (auditoría `F002`) | `…parte_deflate_que_expande_mas_del_maximo` (pico de 148 327 331 bytes frente al tope de 16 MiB) |
| `_ascii_seguro(nombre_original)` por `nombre_original` (auditoría `F003`) | `…neutraliza_nombres_hostiles` (aparece un retorno de carro en la cabecera) |

### Modelo por paso (059b)

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | orquestador | — | — | La rama ya existía; se verificó el estado limpio |
| Fila 5 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| Fila 5 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| Fila 5 · `TC-08` | `tester-backend` | `haiku` | `haiku` | — |
| Fila 6 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| Fila 6 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | Cerró al primer intento |
| Fila 7 · mutantes y laguna | `tester-backend` | `sonnet` | `sonnet` y `haiku` | La laguna `M-08c` es un único test; se hizo en `haiku` |
| Fila 7 · suite y `pip-audit` | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 7 · documentación | agente general | — | `sonnet` | — |
| Auditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Correcciones de la auditoría | `tester-backend` | `sonnet` | `sonnet` | Mutación sobre guardas de seguridad |

### Resultado contra los criterios de aceptación (alcance de 059b)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-2` (el destino cambia solo por el endpoint; URL con el origen público) | `[M]` | Cumplido en el adaptador; las variables y el arranque son de 059c | `TC-08`, `TC-08b`, `M-21` |
| `CA-4` (lecturas por rango acotadas, hasta 262 144 bytes en un libro de 26 MB) | `[M]` | Cumplido en el detector; la ruta de confirmación es de 059d | `TC-52`, `M-16` |
| `CA-5` esc. 3 (el almacén rechaza la subida distinta) | `[M]` | Cumplido | `TC-21` y el test de la suma firmada |
| `CA-6` (tipo por los bytes, lista blanca, rechazos) | `[M]` | Cumplido en el detector | `TC-25`, `TC-25b`, `M-06` a `M-08` |
| `CA-8` esc. 3 (la URL de lectura caduca) | `[M]` | Cumplido en el adaptador | `TC-33` |

### Auditorías de cierre de fase (059b)

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` en la reauditoría (primer veredicto: `REQUIERE CAMBIOS`) | `F001` y `F002` (Mayores), `F003` (Menor): huecos de prueba, resueltos con tests | 1 |
| `auditor-sql` | No aplica: la entrega no tiene esquema ni consulta | — | — |

Observaciones de `auditor-arquitectura` que no bloquean: `O-1` y `O-2` (guardas defensivas equivalentes: `AUSENCIAS` de `head_object`, ZIP64 y método de compresión), `O-3` (la regla `ftyp` → `video/mp4`, ver arriba), `O-4` (`UrlFirmada` congelada con un `dict`: inmutable solo en apariencia), `O-5` (redacción del ADR, corregida) y `O-6` (la región `us-east-1` es un literal de región, no un destino).

### Documentación actualizada (059b)

| Documento | Qué cambió |
|---|---|
| ADR `20261111-confirmacion-de-archivos-sin-descargar-el-objeto.md` | Nuevo: la confirmación no descarga el objeto; la suma firmada y el tipo por rangos, con las opciones descartadas |
| ADR-016 | Aviso al inicio: el destino de producción será MinIO autoalojado en la VPS y el ADR que reemplaza su elección de destino es de TKT-073; lista blanca con `.xlsx` como única hoja de cálculo; el barrido no borra el objeto |
| `docs/06-stack-tecnologico.md` §4.6 | Lista blanca, firma propia de HEIC y lectura del ZIP por rangos |
| `docs/adr/README.md`, `CLAUDE.md`, `README.md`, `llms.txt` | Fila nueva y conteo de 42 a 43 ADR |

`python tools/verificar_docs.py` → falla solo por los cuatro problemas ajenos de TKT-018b (294 documentos, 43 ADR).

### Hallazgos fuera de alcance (059b)

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/tickets/tkt-018b/` | Los cuatro problemas de `verificar_docs.py`, ajenos a este ticket | Baja |
| `backend/cimenta/archivos/dominio/declaracion.py` | Sigue sin rechazar `NUL` en `nombre_original` (observación de seguridad de 059a): se resuelve en la capa de alta de 059c | Media, para 059c |

### Ciclo 1 de /sdd-revisar (059b)

Hallazgos de las auditorías de código, seguridad y documentación, y su resolución. Las cifras de la suite de este ciclo van en la «Verificación final» que añade `/sdd-revisar`.

| Auditor | Hallazgo | Gravedad | Decisión |
|---|---|---|---|
| `auditor-codigo` | `F001` · un `encoding` desconocido en el `XML` lanzaba `LookupError` o `ValueError` | Mayor | Corregido |
| `auditor-codigo` | `F002` · las ramas defensivas del detector no tenían test | Mayor | Tests añadidos; cobertura de ramas del detector al 100 % |
| `auditor-codigo` | `F003` · `leer_rango` no validaba el rango | Menor | Ahora lanza `ValueError` ante un rango inválido |
| `auditor-codigo` | `F004` · literales duplicados | Menor | Corregido |
| `auditor-seguridad` | `F001` · el mismo defecto que `F001` de código | Mayor | Corregido junto con aquel |
| `auditor-seguridad` | `F002` · `MAXIMO_PARTE` de 1 MiB permitía una bomba de profundidad en el XML (97 MiB de pico con 1 MiB de etiquetas anidadas) | Media | `MAXIMO_PARTE` baja a 262 144 bytes |
| `auditor-seguridad` | `F003` · los contenedores RIFF (AVI, WAV) salían como `image/webp` y se tomaba la primera candidata de `puremagic` | Media | RIFF sin `WEBP` pasa a `application/octet-stream` y solo se consideran las candidatas de máxima confianza. La regla `ftyp` → `video/mp4` se deja por decisión de la persona dueña |
| `auditor-seguridad` | `O1` · entradas `[Content_Types].xml` duplicadas | Observación | El detector responde `application/zip` |
| `auditor-docs` | `F001` a `F008` y `O-1` a `O-3` · fecha del ADR en el diseño, cifras de lectura del ADR, fechas de 059b, citas de ADR-016 y marcas de `ftyp` | Mayor y menor | Corregidos en el diseño, el ADR, el stack, el ticket 05, `_index.md` e `impl.md` |

**Ajuste respecto al diseño (ciclo 1).** `MAXIMO_PARTE` baja de 1 MiB a 256 KiB; el bucle de la lista blanca solo considera las candidatas de máxima confianza de `puremagic` (el respaldo por `mime_type` sigue recorriendo todas, porque las candidatas de máxima confianza de un ejecutable MZ no traen `mime_type` y devolverían `application/octet-stream` en lugar del tipo real; el respaldo por `mime_type` solo aporta el tipo de una candidata de menor confianza si ese tipo queda fuera de la lista blanca; la segunda ronda de la revisión cerró así el caso de una firma débil que colaba `image/jpeg`); RIFF sin `WEBP` es `application/octet-stream`; el detector rechaza un `[Content_Types].xml` duplicado; `leer_rango` rechaza rangos inválidos.

**Observaciones fuera de alcance (seguridad).**

| Observación | Dónde se atiende |
|---|---|
| `O2` · un `.xlsx` con hojas descomprimidas sin límite llega a `openpyxl` en `lector_catalogo.py` | TKT-013b y el consumidor del catálogo |
| `O3` · un XML o XHTML con `script` embebido pasa como `application/xml`, pero se sirve como `attachment` | En 059c, verificar que XML y `.xlsx` nunca se sirven en línea y que `url_lectura` valida la disposición |

**Notas para 059c.** Declarar `UrlFirmada.url` con `field(repr=False)`; rechazar `NUL` y sustitutos en el borde de Pydantic; y pedir `Body.read(fin - inicio + 1)` en `leer_rango`.

#### Verificación final de la entrega 059b (`/sdd-revisar`, 2026-11-11)

Cifras copiadas de la última corrida, con `docker info` respondiendo (servidor 29.9.3). La suite se ejecutó tres veces durante la revisión (`2962`, `3015` y `3019` pruebas pasadas) porque cada ciclo de corrección añadió tests; la que cuenta es la última.

```text
uv run pytest -q -ra          →  3019 passed, 26 skipped in 591.50s (0:09:51)
uv run ruff format --check .  →  303 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 303 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
python -m unittest discover -s tools/tests →  Ran 518 tests … OK
python tools/verificar_docs.py →  294 documentos, 43 ADR; falla solo por los cuatro problemas ajenos de TKT-018b
```

Cobertura de ramas de los dos módulos de la entrega, medida por `auditor-codigo`: `almacen_s3.py` 100 % (59 líneas, 4 ramas) y `detector_tipo.py` 100 % (167 líneas, 60 ramas).

| Auditor | Veredicto final | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` (reauditoría tras tres huecos de prueba) | 1 |
| `auditor-sql` | No aplica: la entrega no tiene esquema | — |
| `auditor-codigo` | `APROBADO` | 2 (el ciclo 1 halló `F005` y `F006`, resueltos en el ciclo 2) |
| `auditor-seguridad` | `APROBADO` | 1 |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: `N001` a `N006`, `O-N1` y `O-N2`, todos de redacción, resueltos por el orquestador con el texto literal del auditor tras el segundo ciclo | 2 |

Observaciones de `auditor-seguridad` que quedan abiertas, ambas de prioridad baja: `O4` (algunas firmas defectuosas de `puremagic`, como `\x89PNG` escrito como texto o `%PDF` sin guion, producen un tipo de la lista blanca; el segundo ciclo cerró el caso de una candidata débil en el respaldo, pero las candidatas de máxima confianza con firma defectuosa siguen igual, y el objeto se sirve con ese tipo sin que el navegador lo interprete como HTML) y `O5` (un ZIP con `nlen` mayor que lo que queda del directorio coincide con `[Content_Types].xml` aunque `zipfile` lo rechace; el consumidor del `.xlsx` debe seguir validando con su propio analizador). Ambas pasan a 059d o 059e (ver «Entrega TKT-059c»). Observaciones de `auditor-codigo`: `O-9` a `O-11` (estéticas).

Resultado por criterio de 059b: todos los `[M]` de su alcance cumplidos con evidencia (ver la tabla de criterios de esta sección). Los criterios `CA-2`, `CA-4`, `CA-5` y `CA-6` se completan en 059c a 059e con los casos de uso y las rutas. Desviaciones: las de «Ajustes respecto al design (059b)» y el ciclo 1 de `/sdd-revisar`.


## Entrega TKT-059c · Ajustes y alta (filas 8 a 10)

Fecha de ejecución: 2026-11-12. Misma rama del ticket, `tkt-059-archivos-minimo`, partiendo del commit de cierre de 059b (`6bf304c`). La petición de ejecución nombraba también 059a y 059b; las dos ya estaban ejecutadas, revisadas y acumuladas en la rama, así que este comando ejecutó solo 059c, que es lo que admite el gate de `_index.md`.

### Qué se implementó

- Diez campos nuevos en `AjustesServidor` (el endpoint interno, el bucket, las dos claves, las vidas de las URL, el umbral del barrido y los tres límites) con sus validadores, y la exigencia de las cuatro variables del almacén cuando hay variables de base, en los dos retornos de `cargar_ajustes`. El mensaje nombra las variables que faltan y nunca sus valores.
- `ContextoArchivos`, `ConfiguracionArchivos`, `AlmacenNoConfigurado` y `construir_contexto`, y su composición en `servidor/fabrica.py`: `crear_aplicacion(..., almacen=None)` con un proveedor perezoso del almacén. Construir la aplicación no crea el cliente de `boto3`. Todavía no hay enrutador, barrido ni lector (filas 11 en adelante).
- El repositorio de `archivo` (`insertar`, `bloquear`, `leer`, `marcar_disponible`, `marcar_caducado`) y el caso de uso `registrar_archivo` con `AltaArchivo`, que escribe la fila `PENDIENTE` en la transacción de quien llama y devuelve la URL `PUT` firmada. `contexto_de_archivos` queda publicada para TKT-018.
- `UrlFirmada.url` y `AltaArchivo.url` salen del `repr`, porque la URL prefirmada es una credencial de portador (RNF-06, ADR-016).
- Regla de forma nueva en `evaluar_declaracion`: un `nombre_original` con `NUL` o con un sustituto Unicode se rechaza con `FORMATO`.

### Ajustes respecto al design (059c)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-12 | `evaluar_declaracion` rechaza `NUL` y sustitutos Unicode en `nombre_original` (`FORMATO`, «El nombre contiene caracteres no permitidos.»). La tabla de «Límites y forma de la declaración» y los casos `TC-13` y `TC-49` de `design.md` lo recogen. `_defectos_nombre` acumula `DEMASIADO_LARGO` y `FORMATO`; un nombre en blanco solo da `OBLIGATORIO`. | `auditor-arquitectura` halló (F001) que un nombre con `NUL` o con un sustituto pasaba la declaración y fallaba en el `INSERT` con un `500` (`DataError` de PostgreSQL o `UnicodeEncodeError` de `psycopg`). 059b lo había dejado «para 059c». **Decisión de la persona dueña, 2026-11-12:** resolverlo como regla de forma en el dominio, sin `RN-xx` |
| 2026-11-12 | `almacen_bucket` se valida con `^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$` y el mensaje «debe ser un nombre de bucket válido». | El diseño fija el patrón pero no el texto. El mensaje no sale al operador, porque `ConfiguracionInvalida` solo nombra la variable; dos tests lo cubren |
| 2026-11-12 | `AltaArchivo.url` también va con `field(repr=False)`. | El diseño lo pedía solo para `UrlFirmada`; `AltaArchivo` arrastra la misma credencial hacia el registro. `auditor-arquitectura` lo aprobó y se añadió su test (F002) |
| 2026-11-12 | `repositorio.insertar` recibe una `FilaArchivo` y no una lista de argumentos por palabra clave. | Desviación menor de la firma del diseño (observación `O-5`); el comportamiento y las columnas son los mismos |
| 2026-11-12 | Los desarrolladores de las filas 8 y 9 escribieron todos sus pasos de una vez y corrieron la suite después, en lugar de ponerlos en verde de uno en uno. | Todos los tests de cada fila ya estaban en rojo por la misma ausencia de la funcionalidad. El verde final de cada fila es completo |

Pendientes de 059b que 059c no cierra, con su destino: `O4` y `O5` de `auditor-seguridad` (firmas defectuosas de `puremagic` y `nlen` mayor que el directorio central) y pedir `Body.read(fin - inicio + 1)` en `leer_rango` siguen abiertas porque ninguna de las filas 8 a 10 las asigna. Son de prioridad baja y se atienden en 059d o 059e, o se descartan con motivo en la revisión de esa entrega. La comprobación de que XML y `.xlsx` nunca se sirven en línea (`O3`) es de la fila 14 (059e).

### Archivos tocados (059c)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/servidor/ajustes.py`, `backend/servidor/fabrica.py` | modificados | servidor |
| `backend/cimenta/archivos/aplicacion/contexto.py`, `aplicacion/alta.py` | nuevos | aplicación |
| `backend/cimenta/archivos/infraestructura/repositorio.py` | nuevo | infraestructura |
| `backend/cimenta/archivos/api/dependencias.py` | nuevo | api |
| `backend/cimenta/archivos/interfaz.py`, `dominio/url_firmada.py`, `dominio/declaracion.py` | modificados | interfaz y dominio |
| `backend/tests/test_tkt059_ajustes.py`, `test_tkt059_alta.py` | nuevos | pruebas |
| `backend/tests/test_tkt059_infraestructura.py` (`TC-45b`), `test_tkt057_arranque.py` (`TKT-057/TC-52`), `test_tkt059_dominio.py` (NUL y sustitutos) | modificados | pruebas |
| `docs/arranque-local.md`, `sdd/tickets/tkt-059/design.md`, `impl.md`, `_index.md`, `rojo/fila-8.txt`, `rojo/fila-9.txt`, `rojo/f001-nul.txt` | modificados o nuevos | documentación |

### Pruebas y ciclo TDD por fila (059c)

| Fila | Rojo (`sdd/tickets/tkt-059/rojo/`) | Ejecutó | Verde | Mutantes |
|---|---|---|---|---|
| 8 | `fila-8.txt`: `68 failed, 68 passed`, cero errores. Las razones son la ausencia de los campos de ajustes y de los símbolos de `cimenta.archivos.interfaz`, y rechazos que no ocurrían | `tester-backend` (`sonnet`) → `desarrollador-aplicacion` (`haiku`) | `171 passed` en las siete suites de la fila | `X2` |
| 9 | `fila-9.txt`: `25 failed`, cero errores. Importaciones ausentes dentro del test y el `repr` que mostraba la URL | `tester-backend` (`sonnet`) → `desarrollador-aplicacion` (`haiku`) | `102 passed` en `test_tkt059_alta.py` y `test_tkt059_ajustes.py` | `M-05b`, `X1` |
| 10 | — | `tester-backend` (`sonnet`) | Suite completa, abajo | — |
| F001 | `f001-nul.txt`: `16 failed, 5 passed`; los 5 son guardas de nombres válidos que nacen en verde a propósito | `tester-backend` (`sonnet`) → `desarrollador-dominio` (`haiku`) | `122 passed` en `test_tkt059_dominio.py` y `test_tkt059_alta.py` | Dieciséis mutantes de `auditor-arquitectura` |

Corrección de error del propio test, hecha por `tester-backend`: el caso `par_sustituto_sin_combinar` usaba el emoji real U+1F600 (un carácter válido) en lugar de dos sustitutos escapados, y contradecía el caso válido de emoji. `desarrollador-dominio` lo señaló y no lo editó.

Las filas 8 y 9 son de ejecución con subagentes: el tester escribió el rojo y un agente distinto lo puso en verde.

### Mutación (059c)

Protocolo de `tester-backend`: copia previa fuera del repositorio, huella SHA-256 de todos los `.py` de `backend/` antes y después, un mutante a la vez y `git status` idéntico al terminar. Huella antes y después de cada reversión: `d8d13c36a20f8593e4be7f1d56a9ff9765ba8439645c59158b181095089086bb`.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-05b` | `registrar_archivo` firma la URL antes de evaluar la declaración | `TC-11` (`tamano_declarado_excede_limite` por las tres categorías) y los rechazos de `TC-12` y `TC-13`: 13 failed, 12 passed |
| `X1` | `registrar_archivo` inserta la fila antes de evaluar la declaración | Los mismos 13, por `assert 1 == 0` |
| `X2` | `cargar_ajustes(None)` no llama a `_exigir_almacen_con_base` | `sin_mapa_tambien_se_exige_el_almacen_con_base` y `proceso_con_base_y_sin_bucket_no_arranca` |
| F002 | Quitar `repr=False` de `AltaArchivo.url` | `alta_archivo_oculta_la_url_en_su_repr` |

Ningún mutante sobrevivió.

### Modelo por paso (059c)

| Paso | Agente | Modelo | Motivo |
|---|---|---|---|
| Fila 8, rojo | `tester-backend` | `sonnet` | Valor por omisión del tester |
| Fila 8, verde | `desarrollador-aplicacion` | `haiku` | Valor del diseño; cerró a la primera |
| Fila 9, rojo | `tester-backend` | `sonnet` | Valor por omisión |
| Fila 9, verde | `desarrollador-aplicacion` | `haiku` | Valor del diseño; cerró a la primera |
| Fila 10, mutación y suite | `tester-backend` | `sonnet` | Valor por omisión |
| F001, rojo | `tester-backend` | `sonnet` | Valor por omisión |
| F001, verde | `desarrollador-dominio` | `haiku` | Tarea mecánica; devolvió un test equivocado y el tester lo corrigió |
| Auditorías de cierre | `auditor-arquitectura` | `sonnet` | Valor del comando |

### Resultado contra los criterios de aceptación (alcance de 059c)

| Criterio | Estado | Evidencia |
|---|---|---|
| `CA-2` esc. 1 (con base, el almacén es obligatorio) | Cumplido | `TC-05`, con el mensaje exacto y sin valores |
| `CA-2` esc. 2 (sin base arranca sin almacén) | Cumplido | `TC-06`, `TC-07b` |
| `CA-2` (ajustes de archivos y endpoint) | Cumplido | `TC-07` |
| `CA-3` esc. 1 a 3 (alta, tamaño excedido, tipo fuera de lista) | Cumplido | `TC-09` a `TC-13b` |
| `CA-R1` (regresión del arranque sin base) | Cumplido | `TKT-057/TC-51`, `TKT-057/TC-52` ajustado, `TC-45b` |

El escenario 24 de HDU-001 es de TKT-018; esta entrega le deja la interfaz de alta.

### Auditorías de cierre de fase (059c)

| Auditor | Veredicto | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 2: el primero halló `F001` (NUL y sustitutos sin cubrir) y `F002` (sin test del `repr` de `AltaArchivo`), ambos Menores y resueltos |
| `auditor-sql` | No aplica: la entrega no tiene esquema | — |

Observaciones de `auditor-arquitectura` sin bloqueo: `O-1` (el repositorio completo se ejerce en 059d, con `M-15`, `TC-18` y `TC-28`), `O-2` (`functools.cache` no es seguro frente a hilos y, en el peor caso, se crean dos clientes `boto3` inocuos), `O-3` (`almacen_clave_acceso` es `str` y aparece en el `repr` de los ajustes; el diseño lo fija así), `O-4` (la clave foránea a `usuario` en el `MetaData` propio del repositorio es inofensiva porque nadie llama a `create_all`) y `O-6` (el aviso a TKT-058 y a `/sdd-desplegar` sobre las variables obligatorias va en el `delta.md`).

Lo que `auditor-arquitectura` verificó en la reauditoría, ítem por ítem: F001 y F002 resueltos y probados con dieciséis mutantes en una copia fuera del repositorio; la pureza de `declaracion.py` (solo `re`, `dataclasses` y `tipos`); el orden y la acumulación de los defectos; que el alcance no creció; las reglas 1, 2, 11, 15 y 17; y el árbol sin cambios tras las mutaciones.

### Documentación actualizada (059c)

| Documento | Cambio |
|---|---|
| `docs/arranque-local.md` | Desde 059c, con las variables de base la aplicación no arranca sin las cuatro variables del almacén; qué es opcional |
| `sdd/tickets/tkt-059/design.md` | Filas 8 a 10 marcadas; la fila nueva de `NUL` y sustitutos en la tabla de la declaración; `TC-13` y `TC-49` |

### Hallazgos fuera de alcance (059c)

| Archivo | Observación | Prioridad |
|---|---|---|
| `sdd/tickets/tkt-018b/` | Los cuatro problemas de `verificar_docs.py`, ajenos a este ticket | Baja |
| `backend/tests/test_tkt059_dominio.py` | El separador de sección de `TC-50` perdió un espacio | Baja |

### Verificación final de la entrega 059c

Cifras copiadas de la última corrida, con Docker respondiendo (servidor 29.9.3):

```text
uv run pytest -q -ra          →  3162 passed, 26 skipped in 728.43s (0:12:08)
uv run ruff format --check .  →  309 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 309 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
pip-audit (como el pipeline)  →  No known vulnerabilities found (corrida de la fila 10; F001 no cambia dependencias)
python tools/verificar_docs.py →  falla solo por los cuatro problemas ajenos de TKT-018b
python tools/extraer_mermaid.py  →  30 diagramas encontrados
python -m unittest discover -s tools/tests -v  →  Ran 518 tests · OK
```

Los 26 saltos son las pruebas contra los archivos reales del catálogo (`CIMENTA_CATALOGO_*`, `PA-T3` de TKT-013), ajenas a este ticket.


### Revisión de la entrega 059c (`/sdd-revisar`, 2026-11-12)

Docker respondió (servidor 29.9.3). La suite completa se ejecutó dos veces durante la ejecución y la revisión (`3145` y `3162` pruebas pasadas) porque el ciclo de corrección añadió tests; la que cuenta es la última.

#### Ciclo de corrección

| Auditor | Hallazgo | Gravedad | Decisión |
|---|---|---|---|
| `auditor-codigo` | `F001` · `registrar_archivo` aceptaba un `referencia_tipo` fuera de los seis valores, o distinto de `OBRA` sin `referencia_id`, y fallaba en el `INSERT` con un `500` | Menor | **Decisión de la persona dueña, 2026-11-12:** guarda con `ValueError` antes de evaluar, insertar o firmar. Once tests nuevos, en rojo antes del código (`sdd/tickets/tkt-059/rojo/revisar-f001.txt`) y en verde después. Corregido por `corrector-revision` |
| `auditor-codigo` | `F002` · `# type: ignore` sin justificación en el espía de los tests | Menor | Sustituido por `cast(AlmacenObjetos, espia)` |
| `auditor-codigo` | `F003` · la lista de las cuatro variables obligatorias del almacén estaba duplicada | Menor | `AjustesServidor.almacen_obligatorio()` es ahora el único origen |
| `auditor-codigo` | `F004` · aserción tautológica en `TKT-057/TC-52` | Menor | Eliminada |
| `auditor-codigo` | `F005` · separador `TC-50·` sin espacio | Menor | Restaurado |
| `auditor-docs` | `F001`, `F001b` · cifra de la suite desactualizada | Menor | Sustituida por `3162 passed, 26 skipped in 728.43s (0:12:08)` en `impl.md` y `_index.md` |
| `auditor-docs` | `F002` · faltaban `extraer_mermaid.py` y `unittest` en la verificación final | Menor | Añadidos con su salida |
| `auditor-docs` | `F003`, `F003b` · `CA-10` citado como ajustes; es el barrido de la fila 15 | Menor | `CA-10` quitado de la fila de `impl.md` y de `TC-07` en `design.md` |
| `auditor-docs` | `F004` · `O4` y `O5` «se atienden en 059c» en la sección de 059b | Menor | Reemplazado por «pasan a 059d o 059e» |
| `auditor-docs` | `F005` · el nombre del test de `TC-07` no existía | Menor | `design.md` lista los cuatro nombres reales |
| `auditor-docs` | `F006` · `PA-T3` sin prefijo | Menor | `PA-T3 de TKT-013` |

Los hallazgos de `auditor-docs` son de redacción y de cifras; el orquestador los resolvió con el texto literal del auditor, sin reauditar (paso 4 de `/sdd-revisar`), y se los comunica a la persona dueña.

Observaciones que quedan abiertas, sin bloqueo:

- `auditor-seguridad` · `F001` (`almacen_clave_acceso` es `str` y aparece en el `repr` de los ajustes; el diseño lo fija así), `F002` (el nombre acepta `\n` y marcas bidireccionales; el cliente debe escapar siempre `nombre_original`) y `F003` (los límites por categoría no tienen tope). Las tres son de prioridad baja.
- `auditor-seguridad` · para TKT-018: `registrar_archivo` confía en `obra_id`, `referencia_tipo` y `referencia_id`, así que la ruta debe verificar rol y asignación a la obra, y que `referencia_id` pertenezca a ella.
- `auditor-seguridad` · para 059d: al confirmar, la categoría del tipo leído de los bytes debería aplicar su propio límite.
- `auditor-codigo` · `N08` para TKT-018: el DTO debe tipar `referencia_tipo` como `Literal` de los seis valores, con un test del `422`, o el cliente recibiría un `500`.
- `auditor-codigo` · `N03`: `herramientas/almacen_local.py` tiene una tercera copia de la lista de variables, anterior a esta entrega.
- `auditor-docs` · `O1` (el aplazamiento de `O4`, `O5` y `Body.read(fin - inicio + 1)` a 059d o 059e no tiene decisión registrada), `O2` (la regla de `NUL` y sustitutos no tiene ADR; es una regla de forma sin alternativas relevantes) y `O4` (la regla vive en `design.md` y no en `spec.md`).

#### Verificación final de la entrega 059c

Cifras copiadas de la última corrida, desde `backend/`:

```text
uv run pytest -q -ra          →  3162 passed, 26 skipped in 728.43s (0:12:08)
uv run ruff format --check .  →  309 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 309 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
python tools/verificar_docs.py →  falla solo por los cuatro problemas ajenos de TKT-018b
```

| Auditor | Veredicto final | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 2 (el ciclo 1 halló `F001` y `F002`, resueltos) |
| `auditor-sql` | No aplica: la entrega no tiene esquema | — |
| `auditor-codigo` | `APROBADO` | 2 (el ciclo 1 halló `F001` a `F005`, resueltos) |
| `auditor-seguridad` | `APROBADO` | 1 |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: `F001` a `F006` de redacción y cifras, resueltos por el orquestador con el texto literal del auditor | 1 |

Resultado por criterio de 059c: todos los `[M]` de su alcance cumplidos con evidencia (`CA-2`, `CA-3` y `CA-R1`, ver la tabla de criterios de esta sección). Los criterios `CA-4` a `CA-14` se completan en 059d y 059e. Desviaciones: las de «Ajustes respecto al design (059c)» y las de este ciclo.


## Entrega TKT-059d · Confirmación del archivo y su ruta (filas 11 a 13)

Fecha de ejecución: 2026-11-12. Misma rama del ticket, `tkt-059-archivos-minimo`, partiendo del commit de cierre de 059c (`b72eb0d`).

### Qué se implementó

- **Fila 11, sin código.** `nombres_de_usuarios` y `UsuarioResumen` ya estaban publicadas en `cimenta.identidad.interfaz` desde TKT-017b1, y la aserción de `test_tkt006_enrutador.py` que fija el `__all__` de `identidad` ya las incluye. Por eso no hubo nada que crear ni que ajustar, y `TC-53` (que el diseño condicionaba a que la fila corriera) no se escribió: `tests/test_tkt017_identidad_nombres.py` ya prueba la función.
- `confirmar_archivo`, con los once pasos del diseño: bloqueo `FOR UPDATE` de la fila, el solicitante antes que el estado, la idempotencia, el vencimiento de un `PENDIENTE` que el barrido no alcanzó (se marca `CADUCADO` y el `409` se lanza después de confirmar la escritura), la comparación con los metadatos del objeto, la lectura del tipo por los bytes con lecturas acotadas, la reescritura del tipo dentro del almacén, el cambio a `DISPONIBLE` y el asiento `CONFIRMAR` en la misma transacción. La denegación `NO_ES_SOLICITANTE` se asienta como `DENEGAR` en una transacción propia. El vencimiento del bloqueo (`55P03`) y del tiempo de ejecución (`57014`) responden `409` `CONCURRENCIA`.
- `POST /api/v1/archivos/{archivo_id}/confirmacion` con `verificar_origen` antes que `exigir_rol("DIRECTOR_PROYECTOS")`, los esquemas `EstadoArchivo` y `Archivo` (sin `clave_objeto`) y `montar_archivos`, que sustituye en la fábrica a la línea de la fila 8.
- El cambio del borrador OpenAPI de 059d, `docs/07-especificacion-api.md` §2.8 y los tipos del cliente regenerados (`frontend/src/api/generado/servidor.ts`).

### Ajustes respecto al design (059d)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-12 | **Caso de `E-1 (g)` aplicado: (g1), orden A.** `reescribir_tipo`, luego `marcar_disponible`, luego el asiento, y el bloque confirma. | `copy_object` con `REPLACE` conserva la suma (resultado de `E-1` en 059a); `almacen_s3.reescribir_tipo` no pasa `ChecksumAlgorithm` |
| 2026-11-12 | `esperar_hasta` ya estaba en `herramientas/tiempo_de_prueba.py` y `fabrica_espera_corta` equivale a la fixture `motor_espera_corta` de TKT-017; no se movió ni se creó nada. | Las dos las había creado TKT-017; el diseño dice «si TKT-017 no las creó ya» |
| 2026-11-12 | Las ayudas de las pruebas de la confirmación (`AlmacenContador`, el alta y el `PUT` por HTTP, el libro de 26 MB y las lecturas SQL) viven en `backend/herramientas/soporte_tkt059.py`. | Mismo patrón que los `soporte_tkt017_*`; el diseño no lo preveía |
| 2026-11-12 | `ArchivoLeido` lleva `subido_por_id` además de `subido_por_nombre`. | El esquema de la API arma `UsuarioResumen` con el identificador y el nombre |
| 2026-11-12 | `TKT-057/TC-48` no queda en rojo solo con la entrada nueva de `CUERPOS_VALIDOS`. | Recorre las rutas que existen y no comprueba que cada entrada tenga ruta; la entrada cobra sentido ahora que la ruta existe. No se amplió su aserción para no ir más allá de lo pedido |
| 2026-11-12 | `__all__` de `aplicacion/confirmacion.py` publica `auditoria`. | La caché incremental de `mypy` daba un falso error sobre `confirmacion.auditoria` en `TC-16`; con `__all__` el módulo lo declara de forma explícita |
| 2026-11-12 | No hay test del `TIEMPO_EJECUCION_VENCIDO` (`57014`). | El plan de pruebas no le asigna un caso propio; el código lo traduce igual que el de `55P03` |

### Archivos tocados (059d)

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/archivos/aplicacion/confirmacion.py` | nuevo | aplicación |
| `backend/cimenta/archivos/api/esquemas.py`, `rutas.py`, `montaje.py` | nuevos | api |
| `backend/servidor/fabrica.py` | modificado (`montar_archivos`) | servidor |
| `backend/herramientas/soporte_tkt059.py` | nuevo (ayudas de prueba) | pruebas |
| `backend/tests/test_tkt059_confirmacion.py`, `test_tkt059_confirmacion_concurrencia.py`, `test_tkt059_confirmacion_rechazos.py` | nuevos | pruebas |
| `backend/tests/conftest.py` (fixture `aplicacion_archivos`), `test_tkt057_csrf.py` (`CUERPOS_VALIDOS`) | modificados | pruebas |
| `docs/api/openapi.yaml` | modificado (cambio del borrador en 059d) | contrato |
| `docs/07-especificacion-api.md` | modificado (§2.8 fila 3) | documentación |
| `frontend/src/api/generado/servidor.ts` | regenerado | cliente |
| `sdd/tickets/tkt-059/design.md`, `impl.md`, `_index.md`, `rojo/fila-12a.txt`, `rojo/fila-12b.txt` | modificados o nuevos | documentación |

### Pruebas y ciclo TDD por fila (059d)

| Fila | Rojo (`sdd/tickets/tkt-059/rojo/`) | Ejecutó | Verde | Mutantes |
|---|---|---|---|---|
| 11 | No aplica: sin código | — | — | — |
| 12a | `fila-12a.txt`: `6 failed, 73 passed`, cero errores. Cinco por la ruta ausente (`404`) y uno por el módulo `confirmacion` ausente | `tester-api` (`sonnet`) → `desarrollador-api` (`sonnet`) | `6 passed` en las dos suites de la fila; concurrencia tres veces seguidas; `567 passed` en `-k "tkt006 or tkt057 or tkt072"`; `12 passed` en `test_tkt015_arranque.py` | `M-15`, `M-19` |
| 12b | `fila-12b.txt`: los rechazos ya existían desde 12a, así que el rojo se demostró con treinta mutantes temporales, cada uno con su salida | `tester-api` (`sonnet`) | `33 passed` en `test_tkt059_confirmacion_rechazos.py` | `A01` a `G02` (tabla abajo) |
| 13 | — | `tester-backend` (`sonnet`) | Suite completa, abajo | `M-02b`, `M-09`, `M-10`, `M-15`, `M-19` |

El rojo de la fila 12a es de ejecución con subagentes: el tester lo escribió y un agente distinto lo puso en verde. En la fila 12b el tester demostró cada rechazo mutando la producción y revirtiendo desde una copia previa, con la huella SHA-256 de los `.py` de `backend/` idéntica antes y después: `c6294d73cf3182f17898947a4935aba6b931714f8857b9057fcef712afabc5b0`.

### Mutación (059d)

Mutantes de la fila 13, uno a uno sobre `confirmacion.py` y `repositorio.py`, con copia previa fuera del repositorio. Huella inicial y final de los 317 `.py` de `backend/`: `aca3259431953f6aa0504f12c256601315b5c96e64889653762ddd4765491b9c`.

| Mutante | Cambio | Test que cae | Resumen de pytest |
|---|---|---|---|
| `M-02b` | El solicitante se comprueba después de los pasos 3 a 6 | `otro_director_no_confirma[CADUCADO]`, `[ANULADO]` y `[DISPONIBLE]` (`[PENDIENTE]` sigue pasando, como se esperaba) | `3 failed, 1 passed` |
| `M-09` | El asiento `CONFIRMAR` se escribe en una transacción aparte, después de confirmar | `test_tkt059_ca04_la_bitacora_va_en_la_misma_transaccion` (`TC-16`) | `1 failed` |
| `M-10` | El `ARCHIVO_CADUCADO` del vencido se lanza dentro del bloque | `test_tkt059_ca07_pendiente_vencido_sin_barrer` (`TC-28`) | `1 failed` |
| `M-15` | `repositorio.bloquear` sin `with_for_update()` | `test_tkt059_ca04_dos_confirmaciones_simultaneas` (`TC-18`) | `1 failed, 1 passed` |
| `M-19` | Sin la traducción de `55P03` | `test_tkt059_ca04_confirmacion_con_bloqueo_vencido` (`TC-18b`) | `1 failed, 1 passed` |

Mutantes de la fila 12b (`fila-12b.txt` trae la salida de cada uno): `A01` a `A03` (tamaño), `B01` a `B04` (hash, con `M-03` y `M-04`), `C01` a `C05` (tipo, con `M-06`), `D01` a `D06` (existencia y vencimiento, con `M-01`, `M-10`), `E01` a `E05` (solicitante y denegación, con `M-02`), `F01` a `F05`, `G01` y `G02` (`ANULADO`). Los treinta cayeron por su razón y ninguno sobrevivió.

### Modelo por paso (059d)

| Paso | Agente | Modelo | Motivo |
|---|---|---|---|
| Fila 12a, rojo | `tester-api` | `sonnet` | Valor por omisión |
| Fila 12a, verde | `desarrollador-api` | `sonnet` | Disparador del diseño: bloqueo pesimista y concurrencia |
| Fila 12b | `tester-api` | `sonnet` | Disparador del diseño: los permisos de un rol |
| Fila 13, mutación y suite | `tester-backend` | `sonnet` | Valor por omisión |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | Valor del comando |

### Resultado contra los criterios de aceptación (alcance de 059d)

| Criterio | Estado | Evidencia |
|---|---|---|
| `CA-4` esc. 1 y 2 (confirmar, idempotencia, bitácora, bloqueo) | Cumplido | `TC-14`, `TC-15`, `TC-16`, `TC-17`, `TC-18`, `TC-18b` |
| `CA-5` (tamaño y hash distintos) | Cumplido | `TC-19`, `TC-20` (`HDU-001` esc. 25); `TC-21` es de 059b |
| `CA-6` (tipo leído de los bytes) | Cumplido | `TC-22`, `TC-23`, `TC-24` (`HDU-001` esc. 26) |
| `CA-7` (no subido, caducado, vencido, otro director, rol, origen, inexistente) | Cumplido | `TC-26` a `TC-30` y el caso de `ANULADO` |

El escenario 24 de HDU-001 es de TKT-018; ningún test de esta entrega lleva ese nombre. Los criterios `CA-8`, `CA-9`, `CA-10`, `CA-11` y `CA-12` son de 059e.

### Auditorías de cierre de fase (059d)

| Auditor | Veredicto | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 1 |
| `auditor-sql` | No aplica: la entrega no tiene esquema | — |

Observaciones de `auditor-arquitectura`, sin bloqueo: `O001` (la sección de `impl.md` faltaba; es esta), `O002` (el borrador no declara `422` para un `archivo_id` que no es UUID; patrón que ya tienen otras operaciones) y `O003` (un Director que no subió el archivo distingue «no existe» de «existe pero es de otro»; es la secuencia que fija el diseño, `PA-T59.8`).

**Señal para quien apruebe el PR:** esta entrega modifica `docs/api/openapi.yaml` (cambio del borrador en 059d: `CADUCADO` en `EstadoArchivo`, los códigos y ejemplos de la confirmación, el `409` como `oneOf` de `CONFLICTO` y `CONCURRENCIA`).

### Verificación de la entrega 059d

Cifras copiadas de la última corrida, desde `backend/` con Docker respondiendo (servidor 29.9.3):

```text
uv run pytest -q -ra          →  3201 passed, 26 skipped in 572.53s (0:09:32)
uv run ruff format --check .  →  317 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 317 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
pip-audit (como el pipeline)  →  No known vulnerabilities found
npm run tipos:verificar       →  Tipos al día.
npm run lint, npm run typecheck →  sin hallazgos
python tools/verificar_docs.py →  falla solo por los cuatro problemas ajenos de TKT-018b
```

Los 26 saltos son las pruebas contra los archivos reales del catálogo (`CIMENTA_CATALOGO_*`, `PA-T3` de TKT-013), ajenas a este ticket.


### Revisión de la entrega 059d (`/sdd-revisar`, 2026-11-12)

Docker respondió (servidor 29.9.3). La suite completa se ejecutó tres veces durante la ejecución y la revisión (`3201`, `3205` y `3206` pruebas pasadas) porque los ciclos de corrección añadieron tests; la que cuenta es la última.

#### Ciclo de corrección

| Auditor | Hallazgo | Gravedad | Decisión |
|---|---|---|---|
| `auditor-codigo` | `F001` · la rama `57014` (`TIEMPO_EJECUCION_VENCIDO`) y la que relanza un `DBAPIError` ajeno de `_traducir_concurrencia` no las ejercitaba ningún test | Mayor | Dos tests nuevos: `TC-18c` obtiene un `57014` real del motor y comprueba el contrato completo; `TC-18d` provoca un `22012` real y exige un `500` sin traducir. Cada uno cae con su mutante (`15000` por `14000`, la rama `57015`, traducir todo error de base) |
| `auditor-codigo` | `F002` · la rama `referencia_id` nulo no tenía test y con `None` se habría guardado `"None"` en la bitácora | Mayor | `test_tkt059_ca04_confirmar_sin_referencia`: el cuerpo trae `referencia_id: null` y `datos_despues` tiene exactamente cuatro claves |
| `auditor-codigo` | `F003` · la ruta de fallo de `_asentar_denegacion` no tenía test | Menor | `test_tkt059_ca07_si_la_bitacora_falla_el_403_sigue`: el `403` sigue, el evento `denegacion_no_asentada` lleva el tipo del error y no su texto |
| `auditor-codigo` | `F004` · docstrings de test con un «Rojo de la fila 12a» ya falso | Menor | Párrafos quitados |
| `auditor-codigo` | `F005` · `EstadoArchivo` duplicado en `dominio` y `api/esquemas.py`; los seis `referencia_tipo` repetidos | Menor | `esquemas.py` importa `EstadoArchivo` del dominio. El `Literal` se mantiene porque el OpenAPI publica sus valores, y un test (`test_tkt059_ca04_el_literal_de_referencia_tipo_coincide_con_el_conjunto_de_alta`) compara ambos; cae al quitar `"OBRA"` del `Literal` |
| `auditor-codigo` | `F006` · dos constructores de la misma aplicación y un libro de prueba copiado | Menor | `libro_de_presupuesto` única en `soporte_tkt059.py`; la fixture `aplicacion_archivos` delega en `crear_aplicacion_de_archivos` |
| `auditor-codigo` | `F007` (reauditoría) · el docstring de `esquemas.py` afirmaba que `api/` no importa `aplicacion/` | Menor | Sustituido por el texto literal del auditor, resuelto por el orquestador sin reauditar |
| `auditor-docs` | `F001`, `F002`, `F003` · comando y nombre de test de la fila 11 y `TC-53` que no existen, y descripción incompleta del cambio del borrador | Menor | `design.md` corregido con el texto literal del auditor |

Los hallazgos `F005` (guarda), `F007` y los de `auditor-docs` son de redacción o de código de pruebas; el orquestador los resolvió tras el segundo ciclo con el texto literal del auditor, sin tercera reauditoría (paso 4 de `/sdd-revisar`), y se los comunica a la persona dueña. La producción solo cambió en `api/esquemas.py` durante la revisión.

Observaciones que quedan abiertas, sin bloqueo:

- `auditor-seguridad` · `O-1` (la confirmación mantiene una conexión del pool y el `FOR UPDATE` mientras habla con el almacén; sin `idle_in_transaction_session_timeout` y con el pool por omisión, muchas confirmaciones con un almacén lento podrían saturarlo), `O-2` (un Director ajeno distingue «no existe» de «es de otro»; es la decisión `PA-T59.8`), `O-3` (cada intento ajeno añade un asiento `DENEGAR`) y `O-4` (la URL de `PUT` sigue vigente tras confirmar y el `Content-Type` no va firmado: en 059e, `url_lectura` debe fijar siempre `ResponseContentType` y la disposición).
- `auditor-arquitectura` · `O002` (el borrador no declara `422` para un `archivo_id` que no es UUID) y `O003`.
- `auditor-codigo` · `O1` a `O5` y `O6` (línea larga en el docstring de `servidor/fabrica.py`).
- `auditor-docs` · `O001` (la spec cita `HDU-001` esc. 24 en `CA-3`, `CA-4` y `CA-8`, pero `PA-T59.11` lo asigna a TKT-018), `O002` y `O003` (`docs/02-arquitectura.md` §7.7 no recoge la regla «solo confirma quien subió»).

#### Verificación final de la entrega 059d

Cifras copiadas de la última corrida, desde `backend/`:

```text
uv run pytest -q -ra          →  3206 passed, 26 skipped in 561.87s (0:09:21)
uv run ruff format --check .  →  317 files already formatted
uv run ruff check .           →  All checks passed!
uv run mypy .                 →  Success: no issues found in 317 source files
uv run lint-imports           →  Contracts: 16 kept, 0 broken.
uv run python -m herramientas.verificar_float → archivos revisados: 38; hallazgos: 0
uv run alembic heads          →  0012 (head)
npm run tipos:verificar       →  Tipos al día.
python tools/verificar_docs.py →  falla solo por los cuatro problemas ajenos de TKT-018b
```

| Auditor | Veredicto final | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 1 |
| `auditor-sql` | No aplica: la entrega no tiene esquema | — |
| `auditor-codigo` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: `F005` (guarda) y `F007`, de test y de docstring, resueltos por el orquestador con el texto literal del auditor | 2 |
| `auditor-seguridad` | `APROBADO` | 1 |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`: `F001` a `F003`, de redacción, resueltos por el orquestador con el texto literal del auditor | 1 |

Resultado por criterio de 059d: todos los `[M]` de su alcance cumplidos con evidencia (`CA-4` a `CA-7`, ver la tabla de criterios de la sección «Entrega TKT-059d»). Los criterios `CA-8` a `CA-12` se completan en 059e. Desviaciones: las de «Ajustes respecto al design (059d)» y las de este ciclo.
