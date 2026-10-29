# Delta · TKT-005 · Contrato de error de regla de negocio

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Paquete `contrato_error`, Python puro (biblioteca estándar y `tipos_base`): siete catálogos cerrados copiados del borrador (`CodigoConflicto` con sus 26 valores, `Rol`, `Metodo`, `CodigoConcurrencia`, `CodigoValidacion`, `MotivoPermiso`, `MotivoSesion`), la `Accion` con los roles que pueden ejecutarla y ocho excepciones, una por `tipo`, con **una sola para todas las reglas** (`RechazoRegla`). Cada excepción valida al construirse y produce su cuerpo dados los roles de quien llama y el identificador de correlación: un cuerpo fuera de contrato no se puede construir. Los importes del detalle entran por `serializar()` de `tipos_base` y un `float` o un `Decimal` suelto es `TypeError` | `backend/contrato_error/` (`__init__.py`, `catalogos.py`, `acciones.py`, `excepciones.py`), fuera de `cimenta/` | Que ninguna historia invente su propio formato de error y que el caso de uso de cualquier módulo rechace con regla, cifras y acciones por un solo camino |
| Paquete `servidor`, raíz de composición: la fábrica `crear_aplicacion()`, un *middleware* ASGI puro que genera siempre el identificador de correlación, el registro JSON con `structlog`, cuatro manejadores `def` (la familia del contrato, el `422` de Pydantic, el `404` de enrutado y el `500`) y `principal.py` con `app` | `backend/servidor/` (`fabrica.py`, `correlacion.py`, `registro.py`, `manejadores.py`, `principal.py`), fuera de `cimenta/` | La aplicación servible mínima que ADR-018 había dejado a este ticket, y el punto donde TKT-006 montará sus enrutadores |
| Traducción de los errores de Pydantic a los siete códigos cerrados de `VALIDACION` (con `FORMATO` por omisión `(asumido)`), `campo` con la ruta anidada (`renglones[1].cantidad`) o `cuerpo` para un JSON malformado, sin reflejar `input` ni el `msg` de Pydantic | `backend/servidor/manejadores.py` | Que el `422` por omisión de FastAPI (`detail` con `loc`) deje de salir y no filtre el cuerpo de la petición |
| Registro técnico que conserva el tipo calificado y los marcos (`archivo:línea función`) de cada excepción de la cadena, sin `str(exc)` ni variables locales, y un `logging.Filter` en `uvicorn.error`, idempotente, que hace lo mismo con la traza que uvicorn imprime al relanzar | `backend/servidor/registro.py` | Que una contraseña, un identificador de sesión o un parámetro SQL dentro del mensaje de una excepción no lleguen al registro (`F001` y `F002` de seguridad) |
| Dependencias de ejecución `fastapi[standard-no-fastapi-cloud-cli]`, `pydantic` y `structlog`; de desarrollo `jsonschema`, `pyyaml`, `types-pyyaml` y `types-jsonschema` | `backend/pyproject.toml`, `backend/uv.lock` | Servir la aplicación, y validar cada respuesta contra el esquema del borrador en las pruebas |
| `[tool.fastapi] entrypoint = "servidor.principal:app"` | `backend/pyproject.toml` | Que `uv run fastapi dev` encuentre la aplicación |
| 245 pruebas propias en siete archivos planos más un módulo auxiliar, sin Docker: catálogos, construcción de cada excepción, respuestas HTTP de los ocho `tipo` validadas contra el borrador, correlación y registro, arranque con `fastapi dev` y con uvicorn real, fronteras y regresión | `backend/tests/test_contrato_error_*.py`, `test_servidor_*.py`, `test_tkt005_*.py`, `aplicacion_con_secreto.py` | Que cada garantía se haya visto fallar: 25 mutantes sobre el código de las filas 1 a 9, más siete de regresión, todos mueren |
| ADR-022, contrato de error y raíz de composición | `docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md` | Registrar quién lanza la excepción, dónde viven los dos paquetes, cómo se vigilan y cómo se correlaciona |
| Supuesto 14 de la especificación de la API | `docs/07-especificacion-api.md` §7 | Que la excepción de `REINTENTAR` conste como supuesto `(asumido)` |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Aplicación web | `backend/` | No existía → `uv run fastapi dev` arranca en `127.0.0.1:8000` con `/docs` y `/openapi.json`, sin rutas de negocio |
| Filtrado de acciones por rol | `docs/api/openapi.yaml` (descripción general, `Accion` y `ErrorConcurrencia`), `docs/07-especificacion-api.md` §3, `docs/02-arquitectura.md` §7.3, `docs/05-tickets-trabajo.md`, `docs/08-wireframes.md`, `conv-backend-fastapi` | «Nunca se ofrece una acción que daría 403» sin matices → con la salvedad de `REINTENTAR` de un `409` `CONCURRENCIA`, que repite la operación ya autorizada. **Solo se modificaron descripciones**: ningún esquema, ruta, código ni ejemplo cambió |
| Motivos de `PERMISO` | `docs/02-arquitectura.md` §7.3, `docs/07-especificacion-api.md` §3.1 y §7 supuesto 5 | Tres motivos en dos tablas y `ROL_INSUFICIENTE` para quien no es el solicitante → los cuatro del borrador, con `NO_ES_SOLICITANTE` |
| Quién lanza la excepción | `docs/05-tickets-trabajo.md`, `docs/06-stack-tecnologico.md`, `conv-dominio-python` §4, `conv-backend-fastapi` §6, `desarrollador-dominio` | «Excepción de dominio» → «excepción de aplicación»: la lanza el caso de uso a partir del resultado de la función de regla, que sigue pura. Cierra el `(asumido)` de `conv-dominio-python` |
| Identificador de correlación y `500` | `docs/07-especificacion-api.md` §2.7 | Solo la cabecera y el cuerpo del error → el servidor siempre genera el UUID y descarta el del cliente `(asumido)`; el `500` lleva `mensaje` y `correlacion_id` sin `tipo` `(asumido)` |
| Comando `uv run fastapi dev` | `CLAUDE.md`, `docs/arranque-local.md` | «desde TKT-005 (asumido)» y fila en «Lo que todavía no arranca» → comando funcional con su propio bloque, que no termina por sí solo |
| Estructura del backend | `CLAUDE.md`, `docs/convenciones.md` | Sin `contrato_error/` ni `servidor/` → aparecen, con la salvedad de que `import-linter` analiza `cimenta/` y `tipos_base/` y la pureza de `contrato_error` la comprueba una prueba |
| Conteo de decisiones | `CLAUDE.md`, `README.md`, `llms.txt`, `docs/adr/README.md`, `docs/02-arquitectura.md` §12, `docs/06-stack-tecnologico.md` §11 y §13 | 21 → 22 decisiones, 19 → 20 verificables automáticamente |
| ADR de FastAPI y de contrato de error | `docs/adr/20260918-fastapi.md`, `docs/adr/20260918-contrato-error-negocio.md` | Sin referencia a ADR-022 → nota «Ver ADR-022» y «Aceptado · enmendado por ADR-022 en un punto». La decisión histórica no se reescribió |
| `mypy` | `backend/pyproject.toml` | Override estricto de `cimenta.*.dominio.*` y `tipos_base.*` → también `contrato_error.*` y `servidor.*` |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Marca «desde TKT-005 (asumido)» del comando `uv run fastapi dev` | `CLAUDE.md`, `docs/arranque-local.md` | El comando arranca y responde `200` en `/openapi.json`; lo comprueba `test_tkt005_ca12_comando_de_desarrollo_arranca` |
| El bloque «`(asumido)` · quién lanza la excepción» | `.claude/skills/conv-dominio-python/SKILL.md` §4 | El usuario lo resolvió el 2026-10-20: la lanza el caso de uso |

## Comportamiento observable nuevo

- Todo rechazo de la aplicación sale con la forma fija de su `tipo` y se valida contra su esquema del borrador. `REGLA_NEGOCIO` y `CONFLICTO` responden `409`, `CONCURRENCIA` `409` con `Retry-After`, `VALIDACION` `422`, `PERMISO` `403`, `SESION` `401`, `LIMITE_INTENTOS` `429` y `NO_ENCONTRADO` `404`. Cada uno lleva `correlacion_id`, igual que la cabecera `X-Correlacion-Id`.
- Una ruta inexistente responde `404` `NO_ENCONTRADO` con `recurso` igual a la ruta pedida `(asumido)`, y no `{"detail": "Not Found"}`.
- Un cuerpo inválido responde `422` `VALIDACION` con `campo`, `codigo` y `mensaje` propios, y un JSON malformado responde `campo: "cuerpo"`. El valor enviado nunca se refleja en la respuesta ni en el registro.
- Un error no controlado responde `500` con un mensaje genérico y `correlacion_id`, sin traza, sin texto de la excepción y sin `tipo` `(asumido)`.
- Un `409` que no viola una `RN` es `CONFLICTO` con un `codigo` del catálogo de 26 valores, y no lleva `regla`. Una `regla` fuera de `RN-[0-9]{2}`, un `codigo` fuera del catálogo, un `float` en el detalle o un importe sin cuantizar no se pueden construir.
- Las `acciones` se filtran por los roles de quien llama (`request.state.roles_de_quien_llama`). Sin ellos no se ofrece ninguna acción restringida. La excepción es `REINTENTAR` de un vencimiento, que siempre se ofrece.
- Cada petición deja una línea JSON en la salida estándar con método, ruta, estado y `correlacion_id`, sin cuerpo, cookies, cabeceras ni cadena de consulta. Una excepción deja su tipo y sus marcos, nunca su mensaje, tanto en esa línea como en la de uvicorn.
- `uv run fastapi dev` arranca la aplicación. Una cabecera `X-Correlacion-Id` que mande el cliente se descarta.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints y DTO | Ninguno: el borrador no tiene operaciones con este ticket y la aplicación no define rutas de negocio | No |
| `docs/api/openapi.yaml` | **Tres descripciones** (general, `Accion` y `ErrorConcurrencia`) con la salvedad de `REINTENTAR`. Ningún esquema, ruta, código ni ejemplo cambia. **Debe señalarse a la persona que aprueba el PR** | No |
| Esquemas de error | Se implementan los ocho del borrador tal cual. El `500` no tiene esquema en el borrador y queda `(asumido)` | No |
| Respuesta por omisión de FastAPI para el `422` y el `404` | Sustituidas por `VALIDACION` y `NO_ENCONTRADO`. El OpenAPI que publica FastAPI sigue declarando `HTTPValidationError` hasta TKT-061 | No: no había consumidores |
| Interfaz de `contrato_error` | Las ocho excepciones, `Accion` y los siete catálogos. Los casos de uso de cualquier módulo la importan | No: no existía |
| Contratos de `import-linter` | Ninguno cambia: son 15 antes y después. Los dos paquetes nuevos quedan fuera de `root_packages` por la decisión D-2 y los vigilan pruebas | No |
| Esquema de base de datos, variables de entorno | Ninguno | No |

## Decisiones (ADR)

La decisión tuvo opciones descartadas con evidencia citable y se escribió como [ADR-022](../../../docs/adr/20261020-contrato-de-error-y-raiz-de-composicion.md):

- **Quién lanza.** El caso de uso, a partir del resultado de la regla, frente a lanzarla desde `dominio/`: la regla dejaría de probarse devolviendo un valor y la lista blanca de ADR-021 tendría que abrirse. Evidencia: TC-31 (`dominio/` no puede importar `contrato_error`) y TC-12.
- **Dónde vive.** `backend/contrato_error/`, puro, frente a `cimenta/comun` (rompe `esqueleto-modulos`), `tipos_base` (su contrato es solo biblioteca estándar y su asunto, los números), un paquete único con la parte HTTP (cada caso de uso arrastraría FastAPI) y una copia por módulo (diez formas que divergen). Evidencia: TC-30 y TC-75.
- **Dónde vive la composición.** `backend/servidor/`, frente a `cimenta/main.py` y a la composición dentro de un módulo.
- **Cómo se vigilan.** Fuera de `root_packages`, con una prueba de pureza en ejecución y la lista blanca del dominio, frente a dos contratos nuevos (cambia el total de 15 que fijan dos pruebas de TKT-004).
- **Correlación.** *Middleware* ASGI puro que siempre genera el UUID, frente a `BaseHTTPMiddleware`, a una dependencia de FastAPI (no cubre el `404` de enrutado ni el `422`) y a aceptar el identificador del cliente (inyección en el registro). Evidencia: TC-72 y MT-13.
- **Excepción a las acciones filtradas.** `REINTENTAR` de un vencimiento no se filtra: sin ella, mientras TKT-006 no fije los roles, todo vencimiento llegaría sin acción. Aprobada por el usuario en `/sdd-revisar` y registrada como supuesto 14.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `structlog.processors.format_exc_info` y `exc_info=True` vuelcan `str(exc)` y toda la cadena `__cause__` y `__context__`. Una excepción de SQLAlchemy o de psycopg trae parámetros y claves; con la sesión de TKT-006 serían identificadores válidos. Hay que registrar el tipo y los marcos | Sondas del auditor: `ValueError("…contrasena=S3cr3t!")` y `Key (token)=(…)` quedaban en el registro; `test_tkt005_ca14_el_registro_no_lleva_el_mensaje_de_la_excepcion` | Todo registro de errores, y el agregador de TKT-058 |
| Con `add_exception_handler(Exception, …)` Starlette responde y **vuelve a lanzar**: uvicorn imprime la traza en texto plano, fuera de `structlog` y sin `correlacion_id`. Arreglar el registro propio no basta | `test_tkt005_ca14_uvicorn_real_no_imprime_el_secreto_de_una_excepcion`, que lanza uvicorn real | Cualquier ticket que toque la salida de errores |
| FastAPI 0.159.1 deja un `_IncludedRouter` perezoso en `app.routes` y el `TestClient` devuelve `httpx2.Response`, no `httpx.Response`. Un recorrido de rutas escrito para versiones anteriores no vería una `async def` de un `APIRouter` | TC-78, que baja por `original_router.routes` | TKT-006 en adelante, y la prueba de contrato de TKT-061 |
| El `500` sale por `ServerErrorMiddleware`, fuera del *middleware* de usuario: su manejador tiene que poner él mismo la cabecera de correlación. Con `debug=False` Starlette no filtra traza aunque falte el manejador | TC-58, TC-60, MT-12 y MT-20 | Cualquier manejador de `Exception` |
| Pydantic 2.14 convierte un `ValueError` de un validador en `422`, pero un `TypeError` termina en `500`. Un DTO con un campo de `tipos_base` debe rechazar con `ValueError` | TC-59 | El primer DTO de dinero (TKT-020) |
| El validador JSON Schema no rechaza campos de más porque el borrador no declara `additionalProperties: false`: cada prueba compara además el conjunto exacto de claves | TC-17, TC-24, TC-40, TC-43, TC-50 y MT-8 | Pruebas de contrato de TKT-061 |
| Un test que lanza la suite completa se llamaría a sí mismo, y `git diff --exit-code` sobre un archivo sin confirmar falla siempre: la verificación de «sin cambios» se hace con el hash antes y después | TC-101 y TC-103 | Pruebas de regresión que comprueban comandos |
| Una salvedad a una afirmación absoluta del contrato aparece en más de quince sitios (código, convención, ADR, especificación, wireframes, borrador). Ni el diseño ni la ejecución la propagaron: la encontró la reauditoría | `F006`, `F007` y `F008` a `F015` | Cualquier ticket que matice un criterio `[M]` o una frase del contrato |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | Siguen faltando `revisor-impacto`, `auditor-codigo`, `auditor-docs`, `auditor-sql`, `meta-sdd`, `desarrollador-aplicacion` y ahora también `desarrollador-api` y un redactor de documentación. Sexta vez. Se sustituyeron por un agente general con la convención cargada; en este ticket funcionó, pero el tester tuvo que inventar la unión del repositorio con el diseño en cada fila | Alta |
| `herramienta` | `verificar_docs.py` falla durante todo el ticket por los enlaces del hub e `impl.md` a `delta.md`. Quinta vez (TKT-001 a TKT-005) | Alta |
| `comando` | El diseño volvió a descansar en afirmaciones no ejecutadas porque el arquitecto no tiene terminal: que `fastapi dev` encuentre `servidor` sin `[build-system]` (lo confirmó la fila 7), el código de `FastAPI` 0.159.1 (se adaptó el recorrido de rutas) y, sobre todo, `format_exc_info`, que el diseño prescribía y era una fuga. Cuarta vez (TKT-002, TKT-003, TKT-004 y este) | Alta |
| `guardrail` | El orquestador decidió por su cuenta, durante el ciclo de corrección, que `REINTENTAR` no se filtra por rol. La decisión era razonable, pero matizaba un criterio `[M]` y el contrato público; la reauditoría la sacó como Mayor y el usuario tuvo que aprobarla al final. Una corrección que cambia el comportamiento descrito en la spec o en el borrador se escala en el momento, no se resuelve con el código | Alta |
| `convención` | El diseño decía «con su traza» sin decir «sin el mensaje de la excepción»; un diseño que registra errores necesita una lista de lo que nunca entra en el registro (mensajes de excepción, cuerpos, cabeceras, parámetros) | Media |
| `herramienta` | Los agentes escriben archivos con finales CRLF en Windows y solo lo detecta una prueba de regresión; Ruff y mypy no lo ven. El verificador de codificación de `tools/` no cubre `backend/` | Baja |
| `comando` | El gate de `/sdd-ejecutar` exige Docker, pero el ticket no tenía pruebas de integración propias: Docker solo hizo falta para la regresión final. El demonio estaba apagado y lo arrancó el orquestador sin pedirlo | Baja |
| `contexto` | El agente de diseño en `opus` agotó el límite semanal a mitad de la escritura; el `design.md` ya estaba completo en disco, pero la notificación decía `failed`. Convendría comprobar el archivo antes de reintentar | Baja |
| `modelo` | `haiku` con código literal salió bien a la primera en las filas 1, 4, 5 y 7 y en las dos correcciones de texto. El corrector subió a `sonnet` por el disparador «permisos de un rol» en dos Mayores y cerró en un ciclo | Baja |
| `comando` | El orden sumó unas 2,100 líneas, más de cinco veces el tope, y las entregas A y B viven otra vez en una sola rama. Tercera vez (TKT-003, TKT-004 y este) | Media |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Hallazgos Bajos de seguridad `F004` a `F006`: `or` evalúa la veracidad de una excepción hostil, `ExceptionGroup` no se recorre y los marcos no tienen tope; relativizar las rutas de los marcos si se envían a Sentry; un formateador a nivel raíz para `asyncio`, `anyio` y `sqlalchemy.pool` | Bajos, no explotables sin definir una excepción hostil | TKT-057 y TKT-058 |
| Dependencias de producción que trae el extra de FastAPI: `httpx`, `httpx2` 2.16.0 y `httpcore2` (subidos el 2026-10-21), `jinja2`, `python-multipart`, `email-validator` y un exportador de OpenTelemetry. Valorar `[tool.uv] exclude-newer` y mover el cliente HTTP al grupo `dev` | Es del ticket que construya la imagen | Ticket de imagen de producción (TKT-057 o `conv-docker`) |
| `/docs`, `/redoc` y `/openapi.json` activos, con `/docs` cargando `swagger-ui-dist@5` de un CDN sin versión fija ni SRI | Debe poder apagarse por entorno, que es configuración | TKT-057 |
| Un `HTTPException` distinto de `404` (405, un `401` de las ayudas de seguridad de FastAPI) sale como `{"detail": …}` sin `correlacion_id` en el cuerpo | Won't declarado; TKT-006 debe lanzar `SesionInvalida` o `PermisoDenegado` | TKT-006 |
| `docs/api/openapi.yaml` sigue publicando `HTTPValidationError` para el `422` y no declara un cuerpo para el `500`; el `500` sin `tipo` es `(asumido)` | Es el borrador y TKT-061 | TKT-061 y un ticket para declarar el cuerpo oficial |
| Origen de los roles que exige cada acción: hoy cada caso de uso copia `x-roles` de la operación destino | Ningún documento lo fija | Un ticket que derive el catálogo de `x-roles` del borrador |
| `REINTENTAR`: validar que su `ruta` sea la de la operación invocada, o dejar de pedirle `roles_permitidos`; lanzar la concurrencia solo tras comprobar rol y asignación a la obra | TKT-006 aporta la sesión | TKT-006 |
| TKT-006 debe fijar `request.state.roles_de_quien_llama` en cada petición; y, cuando una obra exista y no esté asignada al usuario, responder `NO_ENCONTRADO` y no `PERMISO` | Es de la sesión | TKT-006 |
| La prueba contra la tabla `bitacora` de que un rechazo no escribe en ella (`CA-11` esc. 3, sustituido por TC-75) | La tabla llega con TKT-007 | TKT-007 |
| El detalle admite `int`: un importe pasado como entero saldría como número JSON; `verificar_float` no revisa `contrato_error/` | Bajo; lo cubren mypy y las pruebas | Ticket de endurecimiento de `verificar_float` |
| `ValueError` y `TypeError` de `tipos_base` dentro de un validador: convención documentada, sin ayuda compartida | No hay ningún DTO de dinero todavía | TKT-020 |
| `design.md` conserva el código literal de `format_exc_info` y de la tabla de manejadores, superado por `backend/` | Es el diseño aprobado en el gate | Ninguno: este delta lo supera |
| `markdownlint-cli2`, `Vale` y `lychee` no se ejecutaron | No están instalados | TKT-009 |
| `docs/APLogo.jpeg` sin seguimiento, ajeno al ticket | No es de este cambio | Excluir del PR |
| Las entregas A y B están en una sola rama y un solo commit | Los hunks de `pyproject.toml`, `CLAUDE.md` y la documentación mezclan A y B | Si se quieren dos PR, separarlos al abrirlos |

## Pull request

**Título:** `TKT-005 · contrato de error de regla de negocio`
**Origen:** `agent`
**Cuerpo:**

Qué: añade el contrato de error de la API y la aplicación servible mínima. `backend/contrato_error/` (Python puro) tiene los siete catálogos cerrados del borrador, la `Accion` con los roles que pueden ejecutarla y ocho excepciones, una por `tipo`, con una sola para todas las reglas; cada una valida al construirse y produce su cuerpo. `backend/servidor/` es la raíz de composición: la fábrica `crear_aplicacion()`, un *middleware* ASGI de correlación que siempre genera el UUID, el registro JSON con `structlog` y los manejadores de la familia del contrato, del `422`, del `404` y del `500`. `uv run fastapi dev` arranca. Añade 245 pruebas propias sin Docker, ADR-022 y el supuesto 14 de la especificación de la API.

Por qué: cerca de la mitad de los escenarios de las nueve historias son rechazos y cada uno afirma regla, cifras y acciones. Sin un mecanismo único, cada historia habría inventado su formato de error y la interfaz habría tenido que tratarlas por separado.

Criterios cubiertos: `CA-1` a `CA-15` y `CA-R1` a `CA-R7` de `sdd/tickets/tkt-005/spec.md`. Suite completa con Docker: 692 pruebas en verde, 15 contratos de `import-linter`, `ruff`, `mypy` y `verificar_float` limpios. 25 mutantes de uno en uno con SHA-256 verificado, más siete de regresión: todos mueren. Decisiones del usuario aplicadas: el caso de uso lanza la excepción, los paquetes viven fuera de `cimenta/` y de `root_packages`, el borrador manda en los motivos de `PERMISO`, el servidor siempre genera el identificador de correlación y el `500` no lleva `tipo`.

**Para quien aprueba, con atención:**

- **Este PR toca `docs/api/openapi.yaml`.** Solo tres descripciones (general, `Accion` y `ErrorConcurrencia`) con la salvedad de que `REINTENTAR` de un `409` `CONCURRENCIA` no se filtra por rol. Ningún esquema, ruta, código ni ejemplo cambia. Es una decisión del usuario, registrada en `_index.md`, y consta como supuesto 14 de la especificación de la API.
- El `500` sin `tipo`, el `recurso` del `404` de enrutado, la traducción de Pydantic a los siete códigos y que el servidor descarte el identificador del cliente son supuestos `(asumido)`.
- Dos auditorías de seguridad y tres de arquitectura. La seguridad encontró que el registro volcaba el mensaje de las excepciones y que uvicorn volvía a imprimirlas; ya no.
- No incluir `docs/APLogo.jpeg`.

Cómo verificarlo, con `uv` y Docker instalados:

```bash
cd backend && uv sync --locked
uv run pytest tests/test_contrato_error_*.py tests/test_servidor_*.py tests/test_tkt005_*.py   # sin Docker
uv run pytest && uv run ruff check . && uv run mypy . && uv run lint-imports
uv run python -m herramientas.verificar_float
uv run fastapi dev
cd .. && python tools/verificar_docs.py
```

Qué queda abierto: ver «Deuda que queda abierta» en `sdd/tickets/tkt-005/delta.md`. Auditorías: arquitectura y seguridad aprobadas tras dos ciclos de corrección; un auditor de código y uno de documentación, por sustitución, porque esos agentes no existen en este entorno. La ejecución se hizo en dos entregas sobre una sola rama.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
