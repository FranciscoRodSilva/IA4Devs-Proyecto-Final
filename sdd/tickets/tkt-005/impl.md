# Impl · TKT-005 · Contrato de error de regla de negocio

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md`, que crea `/sdd-completar`

## Qué se implementó

Se implementaron los dos paquetes del diseño, ambos fuera de `cimenta/` y de `root_packages` (decisión D-2).

`backend/contrato_error/` es Python puro, con la biblioteca estándar y `tipos_base` como únicas dependencias. Contiene los siete catálogos cerrados del borrador (`CodigoConflicto` con sus 26 valores, `Rol`, `Metodo`, `CodigoConcurrencia`, `CodigoValidacion`, `MotivoPermiso`, `MotivoSesion`), la `Accion` con los roles que pueden ejecutarla y una familia de ocho excepciones, una por `tipo`, con una sola para todas las reglas (`RechazoRegla`). Cada una valida lo que recibe al construirse y produce su cuerpo dados los roles de quien llama y el identificador de correlación.

`backend/servidor/` es la raíz de composición: la fábrica `crear_aplicacion()`, un *middleware* ASGI puro que genera siempre el identificador de correlación, el registro JSON con `structlog`, cuatro manejadores `def` —la familia del contrato, el `422` de Pydantic, el `404` de enrutado y el `500`— y `principal.py` con el `entrypoint` que usa `uv run fastapi dev`.

Las dependencias nuevas son `fastapi[standard-no-fastapi-cloud-cli]`, `pydantic` y `structlog` en ejecución, y `jsonschema`, `pyyaml`, `types-pyyaml` y `types-jsonschema` en desarrollo. Un `pip-audit` encontró un CVE en `certifi`, que se resolvió con `uv lock --upgrade-package certifi` a la versión 2026.10.19.

Además, dos auditorías independientes devolvieron `REQUIERE CAMBIOS` y un ciclo de corrección aplicó sus hallazgos. El más importante: el registro volcaba `str(exc)` y uvicorn volvía a imprimir la excepción en texto plano; ahora los dos destinos registran el tipo y los marcos de cada excepción de la cadena, nunca su mensaje.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-21 | Fila 1: se añadió `types-jsonschema` al grupo `dev`, en la fila 2 | `mypy` marcó `import-untyped` en `jsonschema`; es la regla de salida que el propio diseño prevé para la fila 1 |
| 2026-10-21 | Fila 4: `uv lock --upgrade-package certifi` a 2026.10.19 | `pip-audit` encontró `PYSEC-2026-4320` en la versión bloqueada; hay versión con arreglo y es una dependencia transitiva |
| 2026-10-21 | Fila 5: la comprobación de corrutinas baja por `original_router.routes` | FastAPI 0.159.1 deja un `_IncludedRouter` perezoso en `app.routes`: el recorrido del diseño no habría visto una `async def` de un `APIRouter` |
| 2026-10-21 | Fila 8: `TC-101` compara el SHA-256 de `uv.lock` antes y después, y `TC-103` y `TC-105` son comandos y no tests | `git diff --exit-code` falla siempre mientras el lock no esté confirmado; un test que lanza la suite completa se llamaría a sí mismo; `verificar_docs.py` falla hasta que existan `impl.md` y `delta.md` |
| 2026-10-21 | Fila 8: `fabrica.py` y `test_contrato_error_http.py` se convirtieron de CRLF a LF | Los escribió un agente con finales de línea de Windows; los detectó `test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf` |
| 2026-10-21 | Ciclo 1: `REINTENTAR` de una `ConcurrenciaVencida` no se filtra por rol | Sin la sesión de TKT-006 ningún vencimiento habría salido con su salida documentada (arquitectura `F001`); `REINTENTAR` repite la operación que quien llama ya invocó. Propuesta del orquestador, aprobada por el usuario el 2026-10-21 en `/sdd-revisar` (`F006`); el borrador y la especificación de la API se enmendaron en el mismo cambio |
| 2026-10-21 | Ciclo 1: un JSON malformado responde `campo: "cuerpo"` | El desplazamiento del error de análisis se tomaba por un índice de lista (`F003`) |
| 2026-10-21 | Ciclo 1: el registro y uvicorn conservan tipo y marcos, nunca `str(exc)` | Seguridad `F001` y `F002`. El `500` no cambia; se instala un `logging.Filter` en `uvicorn.error` desde `configurar_registro`, de forma idempotente |
| 2026-10-21 | Ciclo 1: tres pruebas existentes cambian su ancla (TC-42, TC-58 y TC-62) y TC-58 pasa de afirmar el mensaje en el registro a afirmar que no está | Las ajustó el tester: la comprobación anterior fijaba la fuga como comportamiento esperado |

Los ajustes de las filas 1 a 8 son de método de verificación o de versión. Del ciclo 1, tres cambian comportamiento observable, y cada uno tiene su motivo: `REINTENTAR` de una concurrencia no se filtra por rol (aprobado por el usuario, `F006`), el JSON malformado responde `campo: "cuerpo"` (`F003`) y el registro y uvicorn conservan tipo y marcos, nunca `str(exc)` (seguridad `F001` y `F002`). Los demás ajustes del ciclo 1 son de método: TC-42, TC-58 y TC-62 cambian su ancla.

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/contrato_error/{__init__,catalogos,acciones,excepciones}.py` | nuevo | aplicación |
| `backend/servidor/{__init__,registro,correlacion,fabrica,manejadores,principal}.py` | nuevo | api |
| `backend/pyproject.toml`, `backend/uv.lock` | modificado | configuración |
| `backend/tests/test_contrato_error_catalogos.py`, `test_contrato_error_construccion.py`, `test_contrato_error_http.py` | nuevo | pruebas |
| `backend/tests/test_servidor_correlacion.py`, `test_servidor_arranque.py`, `aplicacion_con_secreto.py` | nuevo | pruebas |
| `backend/tests/test_tkt005_fronteras.py`, `test_tkt005_regresion.py` | nuevo | pruebas |
| `docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md` | nuevo | documentación |
| `docs/api/openapi.yaml` (solo descripciones, `F006`), `docs/08-wireframes.md`, `docs/adr/20260918-contrato-error-negocio.md` | modificado | documentación |
| `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/adr/20260918-fastapi.md`, `docs/arranque-local.md`, `docs/convenciones.md`, `docs/02-arquitectura.md`, `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `docs/07-especificacion-api.md` | modificado | documentación |
| `.claude/skills/conv-dominio-python/SKILL.md`, `.claude/skills/conv-backend-fastapi/SKILL.md`, `.claude/agents/desarrollador-dominio.md` | modificado | convenciones del toolkit |
| `sdd/tickets/tkt-005/*`, `sdd/_evolucion.md` | nuevo · modificado | artefactos SDD |

Ningún archivo de `cimenta/`, de `tipos_base/`, de `herramientas/`, de `migraciones/` ni `tests/conftest.py` cambió.

## Pruebas

Los 245 tests propios del ticket (la regresión incluida) están en siete archivos planos, sin Docker. Nombres `test_tkt005_caNN_…` y `test_tkt005_carN_…`, con el identificador del diseño en el docstring (`TC-01` a `TC-79`, `TC-100` a `TC-106`). La correspondencia completa entre cada TC y su criterio está en [`design.md`](design.md#plan-de-pruebas); estos son los representantes de cada familia.

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_tkt005_ca04_catalogo_igual_al_borrador` | feliz | `CA-4` esc. 2 | FALLA | PASA |
| TC-02 | `test_tkt005_ca04_codigo_conflicto_rechaza_fuera_del_catalogo` | **rechazo** | `CA-4` esc. 3 | FALLA | PASA |
| TC-10 | `test_tkt005_ca01_rechazo_regla_produce_su_cuerpo` | feliz | `CA-1` | FALLA | PASA |
| TC-13 | `test_tkt005_ca02_regla_mal_formada` | **rechazo** | `CA-2` | FALLA | PASA |
| TC-15 | `test_tkt005_ca03_detalle_rechaza_float_y_decimal` | **rechazo** | `CA-3` esc. 2 | FALLA | PASA |
| TC-20, TC-21 | `ca05_concurrencia_*` | feliz y **rechazo** | `CA-5` | FALLA | PASA |
| TC-25 | `ca07_permiso_no_admite_detalle` | **rechazo** | `CA-7` | FALLA | PASA |
| TC-28, TC-53 | filtrado de acciones por roles | feliz y **rechazo** | `CA-9` | FALLA | PASA |
| TC-30 | `ca13_contrato_error_solo_carga_estandar_y_tipos_base` | **rechazo** | `CA-R3` | FALLA | PASA |
| TC-31 a TC-33 | `car3_*` (lista blanca del dominio) | **rechazo** | `CA-R3` | PASA (ya lo impedía ADR-021) | PASA |
| TC-40 a TC-44 | respuestas HTTP `409`, validadas contra el esquema del borrador | feliz y **rechazo** | `CA-1`, `CA-3` a `CA-5` | FALLA | PASA |
| TC-45 a TC-49 | `422` `VALIDACION`, traducción a los siete códigos | feliz y **rechazo** | `CA-6` | FALLA | PASA |
| TC-50 a TC-52 | `403`, `401`, `429`, `404` | feliz y **rechazo** | `CA-7`, `CA-8` | FALLA | PASA |
| TC-54, TC-55 | correlación en cuerpo y cabecera, línea de registro | feliz | `CA-10`, `CA-11` | FALLA | PASA |
| TC-57 | `ca13_excepcion_sin_contrato_no_es_regla` | **rechazo** | `CA-13` | FALLA | PASA |
| TC-58, TC-61, TC-62 | `500` mínimo sin `tipo`, sin traza ni texto | feliz y **rechazo** | `CA-14`, `CA-15` | FALLA | PASA |
| TC-59 | `ValueError` de un validador de `Dinero` → `422` `FORMATO`; `TypeError` → `500` | feliz y **rechazo** | `CA-15` | FALLA | PASA |
| TC-60 | `ca14_la_aplicacion_no_esta_en_depuracion` | **rechazo** | `CA-14` | FALLA | PASA |
| TC-70 a TC-74 | cabecera, dos peticiones, cabecera hostil descartada, registro sin secretos | feliz y **rechazo** | `CA-10`, `CA-11` | FALLA | PASA |
| TC-75 | `ca11_el_camino_del_error_no_toca_la_base` | **rechazo** | `CA-11` esc. 3 (sustituido, D-3) | FALLA | PASA |
| TC-77, TC-78 | ninguna ruta ni manejador es corrutina; una `async def` se detecta | feliz y **rechazo** | `CA-12` | FALLA | PASA |
| TC-79 | `ca12_comando_de_desarrollo_arranca` | feliz | `CA-12` esc. 2 | FALLA | PASA |
| TC-100 a TC-106 | regresión de `uv.lock`, calidad estática, BOM y CRLF, `serializar()` | **rechazo** | `CA-R1` a `CA-R7` | PASA (la garantía ya se cumplía; cada uno cae ante su mutante) | PASA |

Nacieron en verde y se investigaron: `TC-39` (oráculo del validador, comprobado a mano con cada defecto), `TC-31` a `TC-33` (la lista blanca de TKT-004 ya rechaza cualquier paquete externo), `TC-104` y `TC-100` a `TC-106` (regresión). Cada uno depende de algo, como demuestran los mutantes de la fila 8 y `R1` a `R7`.

### Ciclo TDD por fila

#### Fila 1 · Dependencias de prueba

Sin test propio: es infraestructura. **Verde:** `uv add --dev jsonschema pyyaml types-pyyaml`; `uv sync --locked` con código 0, `mypy` y `ruff` en verde, `lint-imports` en `15 kept, 0 broken`. **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

#### Fila 2 · Catálogos y acción

**Rojo** (tester, `sonnet`):

```text
30 failed, 3 passed in 0.67s
E   ModuleNotFoundError: No module named 'contrato_error'
```

Los tres que pasan son `TC-39`. **Verde:** `33 passed in 0.33s`; `mypy`, `ruff`, `lint-imports` y `verificar_float` en verde. **Refactor:** solo `ruff format` sobre una firma. **Tests devueltos al tester:** ninguno. El verificador del diseño `-k "ca04_catalogo or …"` no cubría TC-02 ni TC-05, así que el verde corrió el archivo entero.

#### Fila 3 · La familia de excepciones

**Rojo:**

```text
97 failed, 38 passed in 2.85s
E   ModuleNotFoundError: No module named 'contrato_error.excepciones'
E   ImportError: cannot import name 'RechazoRegla' from 'contrato_error'   (TC-30)
```

**Verde:** `135 passed in 3.14s` (sin Docker); `mypy`, `ruff`, `lint-imports` (`15 kept, 0 broken`) y `verificar_float` en verde. **Refactor:** `ruff format` y una supresión sobrante de `ruff` retirada. **Tests devueltos al tester:** ninguno. Los TC-31 a TC-33 se investigaron en una copia del árbol: con `contrato_error` permitido en la lista blanca, se ponen en rojo.

#### Fila 4 · Dependencias de la aplicación

**Verde:** `uv add "fastapi[standard-no-fastapi-cloud-cli]" pydantic structlog`; `uv sync --locked` con código 0; `import fastapi, pydantic, structlog, httpx` imprime `2.14.1`; `fastapi-cloud-cli` ausente de `uv.lock`. `pip-audit` encontró `certifi 2026.7.22` con `PYSEC-2026-4320`; tras `uv lock --upgrade-package certifi` (a 2026.10.19), `No known vulnerabilities found`.

#### Fila 5 · Fábrica, correlación y registro

**Rojo:**

```text
9 failed, 1 passed in 0.65s
E   ModuleNotFoundError: No module named 'servidor'
```

El que pasa es `TC-104`, que usa `ast` y no importa `servidor`. **Verde:** `10 passed in 1.76s`, y `135 passed` de las filas anteriores. **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno.

#### Fila 6 · Manejadores

**Rojo:**

```text
67 failed, 10 passed in 3.17s
assert 500 == 409     (24: el ErrorContrato sin manejador acaba en 500)
El cuerpo no es JSON ('text/plain; charset=utf-8'): 'Internal Server Error'     (14)
assert {'detail'} == {'correlacion_id', 'errores', 'mensaje', 'tipo'}     (6)
assert 'secreta-123' not in '{"detail":[…]}'     (2: el 422 por omisión refleja el cuerpo)
ModuleNotFoundError: No module named 'servidor.manejadores'     (19, TC-48a)
```

**Verde:** `77 passed in 2.49s` y `135 passed`; `mypy`, `ruff`, `lint-imports` y `verificar_float` en verde. **Refactor:** `ruff format` sobre `manejadores.py`. **Tests devueltos al tester:** ninguno. Ninguno de los 67 nació en verde: TC-42, TC-57 y TC-62 habrían nacido en verde con solo «el cuerpo no contiene tal texto», así que exigen además la forma mínima del `500`.

#### Fila 7 · `uv run fastapi dev`

**Rojo:**

```text
1 failed, 212 passed in 7.16s
Could not find a default file to run, please provide an explicit path
```

**Verde:** la comprobación previa `fastapi dev --no-reload --port 8765` desde `backend/` encontró `servidor` sin `[build-system]` (no hubo `ModuleNotFoundError`, así que no se escaló) y `GET /openapi.json` respondió `200` con `{"openapi":"3.1.0","info":{"title":"CIMENTA",…},"paths":{}}`. `7 passed` en `test_servidor_arranque.py` y `213 passed` en el conjunto del ticket. Ningún proceso quedó vivo. **Refactor:** sin refactor.

#### Fila 8 · Mutación y regresión

Se aplicaron 25 mutantes —MT-1 a MT-24 y MT-21b— de uno en uno, sobre el código real, con el SHA-256 del archivo antes y al restaurar. Los 25 pusieron algún test en rojo y todos los hashes coinciden al restaurar. Más siete mutantes de regresión (`R1` a `R7`) para los tests de `CA-R`. La tabla es anterior al ciclo 1: el código que añadió (exención de `REINTENTAR`, procesador de excepciones, filtro de `uvicorn.error`, `json_invalid`) no tiene mutación propia; la reauditoría de arquitectura lo probó a mano y lo cubren los 22 tests que nacieron en rojo.

| Mutante | Archivo | Test que cae |
|---|---|---|
| MT-1, MT-2 | `excepciones.py` (`\d` en vez de `[0-9]`, sin `fullmatch`) | TC-13 |
| MT-3, MT-4 | `excepciones.py` (acepta `float`, no exige cuantizar) | TC-15, TC-16, TC-42 |
| MT-5 | `excepciones.py` (`ConflictoEstado` admite `regla`) | TC-18, TC-17, TC-28, TC-43, TC-54 |
| MT-6, MT-8 | `acciones.py` (`permitida_para` permisivo con roles vacíos; `roles_permitidos` se serializa) | TC-05, TC-28, TC-53 · TC-03, TC-10, TC-20, TC-28 |
| MT-7 | `excepciones.py` (no filtra acciones) | TC-28, TC-53 |
| MT-9, MT-10 | `excepciones.py` (concurrencia sin `REINTENTAR` o con `Retry-After` negativo) | TC-21 · TC-20, TC-44 |
| MT-11, MT-20 | `manejadores.py` (el `500` con `str(exc)`, sin cabecera) | TC-58, TC-57, TC-42 · TC-58, TC-61, TC-62 |
| MT-12 | `fabrica.py` (`debug=True`) | TC-60, TC-58, TC-42, TC-57, TC-59, TC-61, TC-62 |
| MT-13, MT-14 | `correlacion.py` (reutiliza la cabecera del cliente; cabeceras en el registro) | TC-72 · TC-73, TC-72 |
| MT-15 a MT-19 | `manejadores.py` (el `422` refleja el `input`, códigos fuera de la tabla, `campo` fijo, manejador de `404` fijo) | TC-45, TC-48 · TC-48 · TC-46 · TC-45 a TC-48 · TC-52, TC-56, TC-77 |
| MT-21, MT-21b | `excepciones.py` importa `yaml` · lista blanca con `contrato_error` | TC-30 · TC-31, TC-32 |
| MT-22, MT-23 | `excepciones.py` (`PermisoDenegado` ignora argumentos extra) · `manejadores.py` (roles por omisión: todos) | TC-25 · TC-53 |
| MT-24 | `test_servidor_arranque.py` (recorrido sin los manejadores) | TC-78 |

Dos mutantes se aplicaron distinto del diseño: MT-14 decodifica las cabeceras a texto (con bytes habría roto el registro por un error de serialización y no por una fuga) y MT-12 conserva los bytes de un archivo con CRLF.

**Evidencia de ejecución al cerrar la fila** (`docker info` responde `29.8.2`):

```text
FAILED tests/test_tkt005_regresion.py::test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf
1 failed, 668 passed in 58.23s
```

La causa era `fabrica.py` con finales CRLF; convertido a LF por el orquestador, quedó en `669 passed in 53.49s`.

#### Fila 9 · Documentación y ADR-022

Ver «Documentación actualizada». `python tools/verificar_docs.py`, `extraer_mermaid.py` y `unittest` de `tools/` en verde, salvo los dos enlaces de `_index.md` hacia `impl.md` y `delta.md` mientras no existían.

#### Ciclo de corrección 1

**Rojo** (tester, `sonnet`): 22 pruebas nuevas o ajustadas.

```text
22 failed, 223 passed in 12.09s
assert [] == [{'clave': 'REINTENTAR', …}]     (arquitectura F001, 12 casos)
{'campo': '[11]', …} != {'campo': 'cuerpo', …}     (arquitectura F003, 3 casos)
assert 'S3cr3t!' not in '{"metodo": …=S3cr3t!"}'     (seguridad F001, 6 casos)
ERROR:    Exception in ASGI application … ValueError: contrasena=S3cr3t!     (seguridad F002, uvicorn real)
```

**Verde** (`corrector-revision`, `sonnet`): `245 passed in 10.71s` en el conjunto del ticket y `692 passed in 51.18s` en la suite completa con Docker; `mypy` (112 archivos), `ruff`, `lint-imports` (`15 kept, 0 broken`) y `verificar_float` en verde. **Refactor:** sin refactor. **Tests devueltos al tester:** ninguno; el corrector no editó ninguno.

#### Ciclo de corrección 2 y reauditorías de `/sdd-revisar`

La reauditoría de arquitectura de `/sdd-revisar` halló `F006` (Mayor): el borrador y la especificación de la API decían «nunca una acción que daría 403», y el código exime a `REINTENTAR`. El usuario aprobó la excepción y se enmendó el contrato. Una segunda pasada halló `F007` (Mayor, `docs/02-arquitectura.md`) y ocho Menores `F008` a `F015` de redacción y coherencia, todos de texto o de docstring. El corrector los aplicó sin tocar lógica; el docstring de una prueba lo cambió el tester. Reauditoría final: `APROBADO`, sin Mayores ni Críticos vivos. La suite no cambió: `692 passed`, `245` propias.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| Fila 1 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 2 · verde | agente general, por sustitución de `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 3 · verde | agente general, por sustitución de `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador «regla de dinero» |
| Fila 4 | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 5 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 5 · verde | agente general, por sustitución de `desarrollador-api` | `haiku` | `haiku` | — |
| Fila 6 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 6 · verde | agente general, por sustitución de `desarrollador-api` | `sonnet` | `sonnet` | Disparador «permisos de un rol» |
| Fila 7 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 7 · verde | `ingeniero-devsecops` | `haiku` | `haiku` | — |
| Fila 8 | `tester-backend` | `sonnet` | `sonnet` | — |
| Fila 9 | agente general, por sustitución del redactor | `haiku` | `haiku` | — |
| Auditoría de arquitectura | `auditor-arquitectura` | `sonnet` | `sonnet` | — |
| Auditoría de seguridad | `auditor-seguridad` | `sonnet` | `sonnet` | — |
| Ciclo 1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| Ciclo 1 · verde | `corrector-revision` | `haiku` | `sonnet` | Dos hallazgos Mayores sobre filtrado por rol y registro, que tocan el disparador «permisos de un rol» |
| Reauditorías de `/sdd-revisar` (tres) | `auditor-arquitectura` | `sonnet` (la acotada de `F005` y la de `F006`, `haiku`) | `haiku`, `haiku` y `sonnet` | Las dos acotadas a hallazgos documentales; la última, con un Mayor vivo, en `sonnet` |
| Ciclo 2 · corrección de texto | `corrector-revision` | `haiku` | `haiku` | — |
| Ciclo 2 · docstring de una prueba | `tester-backend` | `sonnet` | `haiku` | Tarea mecánica verificable por comando |

El diseño fijó la fila 1 en `ingeniero-devsecops` con `haiku`, aunque `/sdd-ejecutar` da `sonnet` por omisión a ese agente; se siguió el diseño. Ningún paso sube a `opus`.

Agentes ausentes que se sustituyeron: `desarrollador-aplicacion`, `desarrollador-api` y el redactor de documentación. Anotado en [`_evolucion.md`](../../_evolucion.md).

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` regla → `409` `REGLA_NEGOCIO` | `[M]` | Cumplido | TC-10, TC-11, TC-12, TC-40 |
| `CA-2` regla `RN-\d{2}` | `[M]` | Cumplido | TC-13, MT-1, MT-2 |
| `CA-3` importes como cadena | `[M]` | Cumplido | TC-14, TC-15, TC-16, TC-41, TC-42 |
| `CA-4` `CONFLICTO` y catálogo de 26 códigos | `[M]` | Cumplido | TC-01, TC-02, TC-17 a TC-19, TC-43 |
| `CA-5` `CONCURRENCIA` con `Retry-After` y `REINTENTAR` | `[M]` | Cumplido, tras el ciclo 1 | TC-20, TC-21, TC-44 y las pruebas de `F001` |
| `CA-6` `422` `VALIDACION` | `[M]` | Cumplido, tras el ciclo 1 | TC-22, TC-23, TC-45 a TC-49 y la de `json_invalid` |
| `CA-7` `403` `PERMISO` sin cifras | `[M]` | Cumplido | TC-24 a TC-26, TC-50 |
| `CA-8` `401`, `429`, `404` | `[M]` | Cumplido | TC-27, TC-51, TC-52 |
| `CA-9` acciones filtradas por roles | `[M]` | Cumplido | TC-03 a TC-05, TC-28, TC-53 |
| `CA-10` correlación | `[M]` | Cumplido | TC-54, TC-70 a TC-72 |
| `CA-11` registro JSON sin datos sensibles | `[M]` | Cumplido, con el escenario 3 sustituido (D-3) | TC-55, TC-73, TC-73b, TC-74, TC-75 |
| `CA-12` aplicación servible | `[M]` | Cumplido | TC-76 a TC-79 |
| `CA-13` un único camino | `[M]` | Cumplido | TC-29, TC-56, TC-57 |
| `CA-14` `500` mínimo | `[S]` | Cumplido, tras el ciclo 1 | TC-58, TC-60, TC-61 y las de seguridad `F001` y `F002` |
| `CA-15` `ValueError` de `tipos_base` → `422` | `[S]` | Cumplido | TC-59, TC-62 |
| `CA-R1` a `CA-R7` | `[M]` | Cumplido | TC-100 a TC-106, `lint-imports`, suite completa |

`CA-11` esc. 3 pide comprobar que no se escribe en la tabla `bitacora`, que no existe hasta TKT-007; lo sustituye TC-75 (el camino del error no carga SQLAlchemy ni `psycopg`) por decisión D-3 y TKT-007 añade la prueba contra la tabla.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `REQUIERE CAMBIOS` en la primera pasada; reauditoría con un Menor documental (`F005`); reauditoría de `/sdd-revisar` con un Mayor (`F006`, el contrato), enmendado tras la aprobación del usuario; reauditoría de `/sdd-revisar` del ciclo 2 con un Mayor (`F007`) y ocho Menores (`F008` a `F015`), corregidos en el ciclo 2 | 4 Mayores (F001, F002, F006, F007) y 11 Menores (F003, F004, F005, F008 a F015) | 3 |
| `auditor-sql` | No aplica: sin esquema, migración ni consulta | — | — |
| `auditor-seguridad` | `REQUIERE CAMBIOS` en la primera pasada; `APROBADO` en la reauditoría | 2 Medias y 4 Bajas | 1 |
| `auditor-codigo`, `auditor-docs` | Agentes ausentes; sus revisiones se hicieron por sustitución en los dos auditores presentes y en `verificar_docs.py` | — | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | arquitectura | Mayor | `contrato_error/excepciones.py:218-226` | `REINTENTAR` filtrado por rol: sin sesión, todo vencimiento salía sin acciones | Resuelto en la reauditoría |
| F002 | arquitectura | Mayor | `sdd/tickets/tkt-005/_index.md` | Sin `impl.md`, `verificar_docs.py` falla y el DoD no era verificable | Resuelto en la reauditoría |
| F003 | arquitectura | Menor | `servidor/manejadores.py:43-56` | JSON malformado con `campo: "[11]"` | Resuelto en la reauditoría |
| F004 | arquitectura | Menor | `docs/convenciones.md:61`, `docs/adr/20260918-fastapi.md:27`, `sdd/_evolucion.md` | Documentación sin actualizar y falta la fila de agentes sustituidos | Resuelto en la reauditoría |
| F001 | seguridad | Media (latente) | `servidor/correlacion.py:54`, `servidor/registro.py:20` | El registro volcaba `str(exc)` y la cadena de causas | Resuelto en la reauditoría |
| F002 | seguridad | Media (latente) | `servidor/manejadores.py:150` (el arreglo vive en `servidor/registro.py:84-107`) | uvicorn imprimía la excepción en texto plano al relanzar | Resuelto en la reauditoría |
| F003 | seguridad | Baja | `backend/pyproject.toml:8` | Dependencias de producción de más y versión de `fastapi` de pocas horas | Persiste; anotado, sin acción en este ticket |
| F004 | seguridad | Baja | `servidor/registro.py:47` | `or` evalúa la veracidad de una excepción: una con `__bool__` hostil hace lanzar al procesador | Nuevo; diferido a TKT-057 |
| F005 | seguridad | Baja | `servidor/registro.py:36-48` | `ExceptionGroup` no se recorre: se pierden los tipos internos | Nuevo; diferido a TKT-057 |
| F006 | seguridad | Baja | `servidor/registro.py:36,92` | Los marcos no tienen tope: un `RecursionError` produjo una línea de unos 159 KB | Nuevo; diferido a TKT-057 |
| F005 | arquitectura (reauditoría) | Menor | `spec.md`, ADR-022, `conv-backend-fastapi` | La excepción de `REINTENTAR` solo estaba en el código y las pruebas | Resuelto por el orquestador: matiz anotado en `CA-9`, en ADR-022 y en la convención |
| F006 | arquitectura (`/sdd-revisar`) | Mayor | `docs/api/openapi.yaml` (`Accion`, `ErrorConcurrencia`), `docs/07-especificacion-api.md` §3 | El borrador y la API decían «nunca una acción que daría 403», y el código exime a `REINTENTAR` sin aprobación humana | Resuelto: el usuario aprobó la excepción y se añadió a los dos esquemas, a la descripción general del borrador, a la especificación §3 y al supuesto 14 de §7. **El PR toca `docs/api/openapi.yaml` y debe señalarse a la persona que aprueba** |
| F007 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Mayor | `docs/02-arquitectura.md:331` | La regla «nunca se ofrece una acción que respondería 403» no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F008 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `docs/05-tickets-trabajo.md:183` | El DoD de acciones filtradas por roles no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F009 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `sdd/tickets/tkt-005/spec.md:49` | El requisito M5 no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F010 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `.claude/skills/conv-backend-fastapi/SKILL.md:90` | La convención de acciones filtradas no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F011 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `docs/adr/20260918-contrato-error-negocio.md` (Estado) | El ADR original no tenía nota de enmienda por ADR-022 | Resuelto en el ciclo 2 |
| F012 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `docs/08-wireframes.md:503` | La premisa de que el servidor filtra `acciones[]` no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F013 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `backend/contrato_error/acciones.py:5` | El docstring de `Accion` no mencionaba la excepción de `REINTENTAR` | Resuelto en el ciclo 2 |
| F014 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `sdd/tickets/tkt-005/impl.md:31` | «Ninguna fila quedó ⚠ Ajustado» contradecía la tabla de ajustes | Resuelto en el ciclo 2 |
| F015 (arq. /sdd-revisar) | `arquitectura (/sdd-revisar)` | Menor | `sdd/tickets/tkt-005/impl.md:270` | La cita `servidor/manejadores.py:151` apuntaba fuera del archivo, que tiene 150 líneas | Resuelto en el ciclo 2 |

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `backend/pyproject.toml`, `uv.lock` | El extra `standard-no-fastapi-cloud-cli` arrastra a producción `httpx`, `httpx2` 2.16.0 y `httpcore2` (subidos el 2026-10-21; exigidos por `fastapi` 0.159.1, con procedencia coherente: mantenedor Pydantic Services), `jinja2`, `python-multipart`, `email-validator` y un exportador de OpenTelemetry. Valorar `[tool.uv] exclude-newer` y mover el cliente HTTP al grupo `dev` al construir la imagen | Media |
| `servidor/fabrica.py` | `/docs`, `/redoc` y `/openapi.json` están activos y `/docs` carga `swagger-ui-dist@5` de un CDN sin versión fija ni SRI. Conviene poder apagarlos en producción (`pydantic-settings`, TKT-057) | Media |
| `servidor/manejadores.py:129` | Un `HTTPException` distinto de `404` (405, un `401` de las ayudas de FastAPI) sale como `{"detail": …}` sin `correlacion_id` en el cuerpo. Won't declarado; TKT-006 debe lanzar `SesionInvalida` o `PermisoDenegado` | Media |
| `docs/api/openapi.yaml` | Sigue publicando `HTTPValidationError` para el `422` y no declara un cuerpo para el `500` | Media |
| `servidor/registro.py` | Hallazgos Bajos de seguridad `F004` a `F006` (veracidad de una excepción hostil, `ExceptionGroup`, tope de marcos) y relativizar las rutas de los marcos si se envían a Sentry; un formateador a nivel raíz cubriría `asyncio`, `anyio` y `sqlalchemy.pool` | Baja |
| `contrato_error/acciones.py` | TKT-006 debe validar que la `ruta` de `REINTENTAR` sea la de la operación original, o dejar de pedirle `roles_permitidos`; y lanzar `ConcurrenciaVencida` solo tras comprobar rol y asignación a la obra | Media |
| `herramientas/verificar_float.py` | No revisa `contrato_error/`, que transporta importes; hoy lo cubren mypy y los tests | Baja |
| `contrato_error/excepciones.py:61` | El detalle admite `int`: un importe pasado como `int` saldría como número JSON. Documentarlo en `conv-backend-fastapi` junto a la advertencia sobre `float` | Baja |
| `docs/APLogo.jpeg` | Archivo sin seguimiento que no pertenece al ticket; debe quedar fuera del PR | Baja |
| uvicorn (`logging`) | Su registro de acceso no es JSON ni lleva `correlacion_id` | Baja |

Para TKT-006: la sesión debe fijar `request.state.roles_de_quien_llama` en cada petición; hasta entonces ningún rechazo ofrece acciones restringidas (fallo seguro). Cuando una obra exista pero no esté asignada al usuario, responder `NO_ENCONTRADO` y no `PERMISO`, para no crear un oráculo de existencia.

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| [ADR-022](../../../docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md) y `docs/adr/README.md` | Nuevo: quién lanza la excepción, dónde viven los dos paquetes, cómo se vigilan y cómo se correlaciona |
| `CLAUDE.md` | 22 decisiones; `uv run fastapi dev` ya no está marcado «desde TKT-005»; estructura con `contrato_error/` y `servidor/` |
| `README.md`, `llms.txt` | 21 → 22 decisiones |
| `docs/arranque-local.md` | `fastapi dev` sale de «Lo que todavía no arranca» y tiene su propio bloque; las pruebas del contrato no necesitan Docker |
| `docs/05-tickets-trabajo.md` | TKT-005: «excepción de aplicación», que lanza el caso de uso |
| `docs/02-arquitectura.md` | Cuatro motivos de `PERMISO`; párrafo «Quién lo lanza»; ADR-022 en §12 |
| `docs/06-stack-tecnologico.md` | La excepción la lanza el caso de uso; ADR-022 en §11 y §13 |
| `docs/07-especificacion-api.md` | §2.7 con el identificador siempre generado y el `500` sin `tipo` `(asumido)`; §3 con la excepción de `REINTENTAR`; §3.1 con `NO_ES_SOLICITANTE`; §7 supuesto 5 y supuesto 14 nuevo |
| `docs/api/openapi.yaml` | Salvedad de `REINTENTAR` en la descripción general, en `Accion` y en `ErrorConcurrencia` (`F006`) |
| `docs/06-stack-tecnologico.md` | Además: «Veintidós decisiones, veinte verificables automáticamente» |
| `docs/convenciones.md`, `docs/adr/20260918-fastapi.md` | `contrato_error/` y `servidor/` en la lista de `backend/`; nota «Ver ADR-022» |
| `.claude/skills/conv-dominio-python`, `conv-backend-fastapi`, `.claude/agents/desarrollador-dominio.md` | La excepción única la lanza el caso de uso; cómo se construye cada `tipo` |

El matiz de `REINTENTAR` se anotó además en `CA-9` de la spec, en ADR-022 y en `conv-backend-fastapi`.

`python tools/verificar_docs.py` → solo el enlace de `_index.md` a `delta.md`, que crea `/sdd-completar`.

## Verificación final

- [x] Todos los criterios `[M]` cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba (`692 passed`, con Docker)
- [x] ≥1 test de rechazo por tipo de error
- [x] Mutación en rutas críticas: 25 mutantes, ninguno sobrevivió
- [x] Todas las auditorías `APROBADO` o con solo Menores y Bajas resueltos o diferidos con ticket (arquitectura: un Menor documental, resuelto; tras la reauditoría de `/sdd-revisar`, `F006` y `F007` y las Menores `F008` a `F015` resueltos en el ciclo 2; seguridad: `APROBADO`)
- [x] Sin hallazgo crítico o mayor pendiente: `F006` y `F007` de arquitectura quedaron resueltos en el ciclo 2 tras la reauditoría de `/sdd-revisar`
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama `tkt-005-contrato-de-error` y sin secretos en el diff (revisado por el auditor de seguridad)
