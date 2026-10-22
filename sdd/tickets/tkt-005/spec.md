# Spec · TKT-005 · Contrato de error de regla de negocio

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

CIMENTA vale en buena medida por lo que rechaza: compras que exceden el presupuesto, recepciones mayores a lo ordenado, pagos sin avance validado. Cerca de la mitad de los escenarios de las nueve historias son rechazos, y cada uno afirma que la respuesta lleva la regla, las cifras del momento y las acciones disponibles. Hoy no hay dónde producir esa respuesta: el backend no tiene aplicación web, ni excepción de rechazo, ni manejador de errores, ni registro estructurado. Si cada historia inventara su propio formato de error, la interfaz tendría que tratar cada rechazo por separado, que es lo que [ADR del contrato de error](../../../docs/adr/20260918-contrato-error-negocio.md) descartó.

Este ticket de fundación entrega la **aplicación servible mínima** y el **mecanismo único** con el que cualquier caso de uso futuro rechaza una operación: una excepción de regla, un manejador global y los ocho cuerpos de error del [borrador OpenAPI](../../../docs/api/openapi.yaml) —los siete `tipo` más `NO_ENCONTRADO`—, todos con identificador de correlación y registro estructurado. No implementa ninguna regla concreta.

Estado de partida, criterio por criterio del ticket:

| Criterio del ticket | Estado de partida |
|---|---|
| Excepción de dominio con regla, mensaje, detalle y acciones | No existe. Tampoco existe FastAPI, Pydantic ni structlog: `backend/pyproject.toml` solo declara `alembic`, `psycopg` y `sqlalchemy`, y `uv.lock` no los contiene |
| Manejador global según arquitectura §7.3 | No existe aplicación ni raíz de composición. [ADR de interfaz publicada](../../../docs/adr/20261017-interfaz-publicada-y-contrato-de-fronteras.md): «La raíz de composición queda para TKT-005» |
| Siete `tipo` más `404` | Solo existen como esquemas del borrador (`openapi.yaml`, `ErrorReglaNegocio` … `ErrorNoEncontrado`) |
| Catálogo cerrado `CodigoConflicto` | Existe como enum del borrador, con 26 valores; ningún código lo lee |
| Acciones filtradas por los roles de quien llama | No existe. Los roles de sesión llegan con TKT-006, que depende de este ticket |
| Importes del detalle como cadena | `tipos_base.serializar()` existe (TKT-004) y rechaza un valor sin cuantizar |
| Identificador de regla `RN-\d{2}` | No existe |
| Un test por `tipo` contra su esquema del borrador | No existe |
| Registro estructurado con identificador de correlación | No existe |
| `uv run fastapi dev` | Marcado «desde TKT-005 (asumido)» en `CLAUDE.md` y en `docs/arranque-local.md` |

La spec parte de cuatro decisiones del usuario, tomadas el 2026-10-20 en el intake:

1. **Must:** todo lo que pide el ticket, más la aplicación servible; el `500` genérico con identificador de correlación entra como Should; sustituir el `HTTPValidationError` del OpenAPI publicado es de TKT-061.
2. **Quién lanza la excepción:** el **caso de uso**, a partir del resultado que devuelve la función de regla. La función de `dominio/` sigue pura. Esto cierra el `(asumido)` de `conv-dominio-python` §4.
3. **Filtrado de acciones:** los roles de quien llama y los roles que exige cada acción entran como **datos**; el test usa dos conjuntos de roles inventados. TKT-006 conecta la sesión real.
4. **`404` y `500`:** una ruta inexistente responde `NO_ENCONTRADO`; un error no controlado responde un cuerpo mínimo con `correlacion_id` y sin traza. Ambos `(asumido)`, porque el borrador no define el `recurso` de un `404` de enrutado ni un cuerpo de `500`.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, persona o agente; quien lo recibe al final es cualquier rol del PRD §4 delante de una pantalla de rechazo.

**Como** persona o agente que desarrolla CIMENTA
**quiero** un único mecanismo para rechazar una operación con regla, cifras y acciones, y una forma fija para cada tipo de error
**para** que ninguna historia invente su propio formato, que la interfaz distinga cada rechazo por su `tipo` y que el usuario pueda citar un identificador cuando algo falla.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Aplicación FastAPI servible: una fábrica de la aplicación y `uv run fastapi dev` funcionando, con las dependencias nuevas (FastAPI, Pydantic v2, `structlog`) fijadas en `uv.lock` y las herramientas de prueba que hagan falta |
| | **M2.** Una sola excepción de rechazo de regla, con `regla` (`RN-\d{2}`), `mensaje`, `detalle` y `acciones`, que lanza el caso de uso, no la función de `dominio/`. Un solo manejador global la serializa a `409` `REGLA_NEGOCIO` |
| | **M3.** Los otros siete cuerpos —`CONFLICTO`, `CONCURRENCIA`, `VALIDACION`, `PERMISO`, `SESION`, `LIMITE_INTENTOS` y `NO_ENCONTRADO`— con su código HTTP, sus campos y sus cabeceras exactas del borrador, y la sustitución del `422` por omisión de FastAPI |
| | **M4.** Catálogo cerrado `CodigoConflicto`: un `codigo` fuera de los 26 del borrador no se puede construir. Un `409` que no viola una `RN` no lleva `regla` |
| | **M5.** Acciones filtradas por los roles de quien llama: nunca se ofrece una acción que le daría `403` (salvo `REINTENTAR` de una concurrencia; ver la nota de CA-9) |
| | **M6.** Importes del detalle serializados como cadena; el identificador de regla solo admite `RN-\d{2}` |
| | **M7.** Identificador de correlación por petición: cabecera `X-Correlacion-Id` en toda respuesta y `correlacion_id` en el cuerpo de todo error, y registro técnico estructurado en JSON con `structlog` que lo contiene (`RNF-13`) |
| | **M8.** Un test por `tipo` que valida la respuesta contra su esquema del borrador |
| | **M9.** Consecuencia documental de M1 a M8, que no amplía el alcance: retirar la marca «desde TKT-005 (asumido)» de `CLAUDE.md` y `docs/arranque-local.md`; cerrar el `(asumido)` de `conv-dominio-python` §4; corregir en el ticket «excepción de dominio» por «excepción de aplicación»; alinear los motivos de `PERMISO` de arquitectura §7.3 y API §3.1 con los cuatro del borrador, y el supuesto 5 de API §7 |
| **Should** | **S1.** Un error no controlado responde `500` con un cuerpo mínimo —mensaje genérico y `correlacion_id`, sin traza ni texto de la excepción— y queda en el registro técnico con su traza `(asumido)` |
| | **S2.** Un `ValueError` o `TypeError` de `tipos_base` lanzado al validar un campo de entrada llega al cliente como `422` `VALIDACION` con `codigo` `FORMATO`, no como `500` (compromiso del `delta.md` de TKT-004, `PA-T8`) |
| **Could** | — |
| **Won't** | Ninguna regla `RN-xx` concreta · cómo se obtienen los roles de la sesión (TKT-006) · asentar el `403` como `DENEGAR` en la bitácora (TKT-006 y TKT-007) · CSRF, límite de intentos y cabeceras de seguridad (TKT-057) · agregación de errores en Sentry (TKT-058) · sustituir el `HTTPValidationError` en el OpenAPI publicado y la prueba de contrato (TKT-061) · traducir `lock_timeout` a `CONCURRENCIA` en un caso de uso (TKT-021) · añadir códigos a `CodigoConflicto` para casos que no existen todavía · `405` y cualquier `tipo` fuera de los ocho · aceptar un identificador de correlación enviado por el cliente · pantalla de bloqueo y cliente de API (TKT-008) |

## Non-goals

- No implementa ninguna regla concreta. Los ejemplos `RN-03`, `RN-02` o `RN-07` aparecen como datos de prueba, no como lógica.
- No agrega errores en ningún servicio externo: eso es TKT-058.
- No decide de dónde salen los roles de quien llama ni los roles que exige cada acción en una petición real. Recibe ambos conjuntos como datos; TKT-006 y los casos de uso de cada módulo los aportan.
- No crea tablas, migraciones ni permisos de base de datos. No escribe en la bitácora: el `correlacion_id` y la bitácora son dos registros para dos preguntas distintas ([API §2.7](../../../docs/07-especificacion-api.md#27-correlación)).
- No crea endpoints de negocio. La aplicación nace sin rutas propias más allá de las que FastAPI publica (`/openapi.json`, `/docs`).
- No amplía el catálogo `CodigoConflicto`: «ampliarlo se hace en el mismo cambio que añade el caso que lo produce».

## Reglas de negocio implicadas

Ninguna regla `RN-xx` se implementa. El ticket sostiene el mecanismo por el que todas las reglas rechazan. Los identificadores aparecen en los escenarios solo como valores de ejemplo.

| Referencia | Qué exige | Dónde está |
|---|---|---|
| `RN-03` | Ejemplo canónico del contrato: la requisición que excede el disponible se bloquea y responde `409` `REGLA_NEGOCIO` con presupuestado, consumido, disponible, solicitado y excedente | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `RN-04` | Toda autorización y rechazo se registran. Un `409` sin regla que se asentara con un `RN-xx` inventado contaminaría la consulta de excepciones por `regla_negocio` | PRD §8 |
| `RN-02` | Ejemplo de `VALIDACION` con `regla` opcional: la requisición sin tipo de partida | PRD §8 |
| `RNF-13` | Registro técnico estructurado con identificador de correlación por petición, **separado de la bitácora** | PRD §9 |
| `RNF-16` | El vencimiento de `lock_timeout` o `statement_timeout` se traduce al contrato de error con una acción, no a un fallo genérico. La traducción es de TKT-021; aquí solo existe la forma `CONCURRENCIA` | PRD §9 |
| Regla 5 de `CLAUDE.md` | Los límites bloquean con detalle: el desglose `consumido = requisiciones vivas + comprometido + ejercido` viaja como `consumido_desglose`, aditivo | `CLAUDE.md` |
| Regla 1 de `CLAUDE.md` | Los importes viajan como cadena | `CLAUDE.md` |
| Regla 11 de `CLAUDE.md` | Rutas `def`, nunca `async def` | `CLAUDE.md` |
| Convención de errores de `CLAUDE.md` | `409` `REGLA_NEGOCIO`; `422` forma; `403` permiso; un `409` sin `RN` es `CONFLICTO`; el vencimiento es `CONCURRENCIA` | `CLAUDE.md` |

Términos del [glosario](../../../docs/glosario.md) que importan: *tipo de partida* (la bolsa de control por obra, que aparece en `detalle.tipo_partida`), *presupuesto de control* (`SIN_PRESUPUESTO_CONTROL`) y *requisición* (ejemplo del rechazo). El glosario no define *contrato de error*, *acción* ni *correlación*: viven en [arquitectura §7.3](../../../docs/02-arquitectura.md#73-contrato-de-error-de-regla-de-negocio), [API §3](../../../docs/07-especificacion-api.md#3-el-contrato-de-error) y `RNF-13`.

## Invariantes que deben sobrevivir al cambio

El ticket no crea tablas, así que no toca ninguno de los 38 invariantes del modelo de datos. Sí modifica archivos que ya funcionan: `backend/pyproject.toml` y `uv.lock` (dependencias y contratos de `import-linter`), `CLAUDE.md`, `docs/arranque-local.md`, la documentación del contrato y las convenciones. Estas son las garantías de TKT-001 a TKT-004 que deben sobrevivir:

| Garantía existente | Qué protege | Criterio de regresión |
|---|---|---|
| `uv sync --locked` sigue funcionando y las dependencias nuevas quedan en `uv.lock` | Instalación reproducible (`RNF-08`) | `CA-R1` |
| Ruff, mypy y `verificar_float` terminan en verde sobre `backend/` y `tipos_base/` | La base de calidad de TKT-001 y TKT-004; el código nuevo no introduce `float` | `CA-R2` |
| Los 15 contratos de `import-linter` siguen en verde y cada uno sigue fallando ante su violación, sin `ignore_imports` | Fronteras de TKT-002 y lista blanca del dominio de TKT-004; el ADR de interfaz publicada: «Ningún contrato lleva `ignore_imports`» | `CA-R3` |
| `dominio/` y `tipos_base/` no importan FastAPI, Pydantic ni `structlog` | Regla 2 de `CLAUDE.md` | `CA-R3` |
| La suite existente —identidad, permisos, tipos base, fronteras— sigue en verde, y los tests siguen conectándose con el rol de aplicación | TKT-003 y TKT-004; que añadir una aplicación no altere `conftest.py` ni la conexión | `CA-R4` |
| Las marcas «desde TKT-xxx» de otros tickets siguen intactas | Que `npm run dev` siga marcado «desde TKT-008», MinIO «desde TKT-059» y el pipeline «desde TKT-009» | `CA-R5` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` siguen en verde | Enlaces, anclas, identificadores y conteos | `CA-R6` |
| Los archivos nuevos no llevan BOM ni finales de línea fuera de LF | La comprobación de codificación de TKT-001 | `CA-R6` |
| `serializar()` de `tipos_base` sigue rechazando un valor sin cuantizar | Que el detalle del error nunca redondee por su cuenta (TKT-004) | `CA-R7` |

> Una spec de modificación sin esta sección no pasa el Definition of Ready.

## Criterios de aceptación

Gherkin, en español. Camino feliz y rechazo por cada `tipo`. Como el ticket no implementa reglas, el rechazo de cada criterio es la demostración de que un cuerpo fuera de contrato **no se puede construir** o **no llega al cliente**: un contrato que nunca se ha visto rechazar su violación no está verificado. Cada respuesta se valida contra su esquema de [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml). Las rutas de prueba son rutas de la suite, no del producto.

### CA-1 `[M]` · Una regla rechazada responde `409` `REGLA_NEGOCIO` con regla, cifras y acciones · M2, M3 · `RN-03`

```gherkin
Escenario: El caso de uso lanza la excepción y el manejador global la serializa
  Dado un caso de uso de prueba cuya función de regla devuelve BLOQUEADA para RN-03
  Y el detalle con presupuestado "45000.0000", consumido "33000.0000", disponible "12000.0000", solicitado "15000.0000" y excedente "3000.0000"
  Y la acción VER_SOLICITUD_AUTORIZACION con GET y ruta "/api/v1/solicitudes-autorizacion/9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b"
  Cuando el caso de uso lanza la excepción de rechazo de regla
  Entonces la respuesta es 409 con tipo "REGLA_NEGOCIO" y regla "RN-03"
  Y el cuerpo trae mensaje, detalle con las cinco cifras como cadena, acciones con la acción dada y correlacion_id
  Y el cuerpo valida contra el esquema ErrorReglaNegocio del borrador

Escenario: Una función de regla de dominio no lanza nada
  Dado una función de regla de prueba en dominio/ que recibe objetos de valor
  Cuando devuelve el resultado BLOQUEADA
  Entonces no lanza ninguna excepción y se prueba sin servidor ni base de datos
  Y solo el caso de uso que la invoca convierte el resultado en excepción

Escenario: Rechazo — el manejador no existe para una excepción por regla
  Dado el conjunto de excepciones de rechazo del proyecto
  Cuando se enumeran
  Entonces hay una sola excepción de regla y no una por cada RN-xx
  Y toda regla viaja en el campo regla, no en el tipo de la excepción
```

### CA-2 `[M]` · Rechazo · El identificador de regla solo admite `RN-\d{2}` · M6 · `RN-04`

```gherkin
Esquema del escenario: Rechazo — un identificador de regla mal formado no se puede construir
  Dado el identificador de regla "<valor>"
  Cuando se intenta construir la excepción de rechazo de regla con él
  Entonces la construcción falla con ValueError que cita el valor recibido
  Y ninguna respuesta llega a salir con ese valor

  Ejemplos:
    | valor     |
    | RN03      |
    | RN-A      |
    | rn-03     |
    | RN-03␠    |
    | RNF-13    |
    | (vacío)   |
```

El cuarto ejemplo es el identificador válido seguido de un espacio (␠), y el sexto es la cadena vacía. El quinto es el identificador de un requisito no funcional, que no es una regla.

### CA-3 `[M]` · Los importes del detalle viajan como cadena · M6 · regla 1

```gherkin
Escenario: Un Dinero cuantizado sale como cadena de cuatro decimales
  Dado un detalle con el Dinero "45000" cuantizado a su escala
  Cuando el manejador serializa el rechazo
  Entonces el campo presupuestado vale la cadena "45000.0000" y no el número 45000

Escenario: Rechazo — un float en el detalle no se puede construir
  Dado un detalle que contiene el float 33000.0
  Cuando se intenta construir la excepción de rechazo de regla
  Entonces la construcción falla con TypeError que nombra el tipo recibido
  Y ninguna cifra viaja como número JSON

Escenario: Rechazo — un importe sin cuantizar no se redondea por su cuenta
  Dado un Dinero "12000.00005" sin cuantizar
  Cuando el manejador intenta serializar el detalle
  Entonces el error es el de serializar() de tipos_base y no se emite ninguna cifra redondeada
  Y la petición responde como error no controlado, porque es un error del programa y no del usuario
```

El tercer escenario documenta que un importe sin cuantizar es un defecto del caso de uso. No se traduce a `409`.

### CA-4 `[M]` · Un `409` sin `RN` es `CONFLICTO` con `codigo` del catálogo cerrado · M3, M4 · `RN-04`

```gherkin
Escenario: Obra sin línea base congelada responde CONFLICTO y no una regla
  Dado un caso de uso de prueba que lanza un conflicto con codigo "SIN_LINEA_BASE_CONGELADA"
  Cuando el manejador lo serializa
  Entonces la respuesta es 409 con tipo "CONFLICTO" y codigo "SIN_LINEA_BASE_CONGELADA"
  Y el cuerpo no contiene el campo regla
  Y valida contra el esquema ErrorConflictoEstado del borrador

Escenario: El catálogo del código coincide con el del borrador
  Dado el enum CodigoConflicto de docs/api/openapi.yaml con sus 26 valores
  Cuando un test compara ese enum con el catálogo del código
  Entonces los dos conjuntos son idénticos, sin valores de más ni de menos

Escenario: Rechazo — un codigo fuera del catálogo no se puede construir
  Dado el codigo "SOLICITUD_YA_USADA", que no está en el catálogo
  Cuando se intenta construir un conflicto con él
  Entonces la construcción falla con ValueError que cita el valor recibido
  Y no se emite ninguna respuesta con ese codigo

Escenario: Rechazo — un conflicto no admite regla
  Dado un conflicto con codigo "ESTADO_NO_PERMITE_OPERACION"
  Cuando se intenta construir pasándole también la regla "RN-03"
  Entonces la construcción falla
  Y el cuerpo de un CONFLICTO nunca lleva el campo regla
```

### CA-5 `[M]` · El vencimiento del bloqueo responde `CONCURRENCIA` con `Retry-After` y `REINTENTAR` · M3 · `RNF-16`

```gherkin
Escenario: Un vencimiento responde 409 CONCURRENCIA con su cabecera y su acción
  Dado un caso de uso de prueba que lanza una concurrencia con codigo "BLOQUEO_VENCIDO"
  Y espera_maxima_ms 5000, Retry-After de 1 segundo y la acción REINTENTAR hacia la ruta de la operación original
  Cuando el manejador la serializa
  Entonces la respuesta es 409 con tipo "CONCURRENCIA" y codigo "BLOQUEO_VENCIDO"
  Y lleva la cabecera Retry-After con el valor 1
  Y detalle.espera_maxima_ms vale 5000 y acciones contiene REINTENTAR
  Y el cuerpo no contiene el campo regla
  Y valida contra el esquema ErrorConcurrencia del borrador

Escenario: Rechazo — una concurrencia sin acción o con valores fuera de rango no se construye
  Dado una concurrencia sin la acción REINTENTAR, o con Retry-After negativo, o con codigo "OTRO"
  Cuando se intenta construir
  Entonces cada intento falla con ValueError
  Y ningún vencimiento llega al cliente sin una salida documentada
```

### CA-6 `[M]` · Una petición mal formada responde `422` `VALIDACION`, nunca el `detail` de FastAPI · M3

```gherkin
Escenario: Un campo obligatorio ausente responde VALIDACION con su campo y código
  Dado una ruta de prueba con un cuerpo de dos campos, uno de ellos obligatorio
  Cuando se envía el cuerpo sin ese campo
  Entonces la respuesta es 422 con tipo "VALIDACION"
  Y errores contiene un elemento con campo igual al nombre del campo, codigo "OBLIGATORIO" y mensaje
  Y valida contra el esquema ErrorValidacion del borrador
  Y el cuerpo no contiene la clave detail ni loc

Escenario: El campo anidado se nombra con su ruta
  Dado un cuerpo con una lista de renglones en la que el segundo renglón trae una cantidad mal formada
  Cuando se envía
  Entonces el campo del error es "renglones[1].cantidad"

Escenario: Una petición con varios errores los devuelve todos
  Dado un cuerpo con dos campos inválidos
  Cuando se envía
  Entonces errores contiene dos elementos y el mensaje dice "La petición tiene 2 campos inválidos."

Escenario: Rechazo — todo error de Pydantic cae en el enum cerrado de códigos
  Dado cada tipo de error de validación que Pydantic puede emitir para el cuerpo de prueba
  Cuando el manejador lo traduce
  Entonces el codigo es uno de OBLIGATORIO, FORMATO, NO_POSITIVO, FUERA_DE_RANGO, FECHA_ANTERIOR_A_VIGENTE, VALOR_NO_PERMITIDO o DEMASIADO_LARGO
  Y un error sin correspondencia conocida se traduce a FORMATO `(asumido)` y nunca expone el tipo interno de Pydantic

Escenario: Rechazo — una regla que impone la forma lleva su regla
  Dado un caso de uso que rechaza un cuerpo sin tipo_partida_id con la regla "RN-02" y codigo "OBLIGATORIO"
  Cuando el manejador lo serializa
  Entonces el elemento de errores lleva regla "RN-02"
```

### CA-7 `[M]` · Un permiso negado responde `403` `PERMISO` sin cifras del recurso · M3

```gherkin
Escenario: Un rol insuficiente responde PERMISO con los roles requeridos
  Dado una ruta de prueba que exige el rol DIRECCION_GENERAL
  Cuando la llama alguien con el rol COMPRAS
  Entonces la respuesta es 403 con tipo "PERMISO" y motivo "ROL_INSUFICIENTE"
  Y roles_requeridos vale ["DIRECCION_GENERAL"]
  Y valida contra el esquema ErrorPermiso del borrador

Escenario: Rechazo — un permiso nunca lleva cifras del recurso
  Dado el esquema ErrorPermiso, que no tiene el campo detalle
  Cuando se intenta construir un PERMISO con un detalle de cifras
  Entonces la construcción falla
  Y ningún 403 trae importes, cantidades ni identificadores del recurso

Escenario: Rechazo — motivo o rol fuera de los enumerados no se construye
  Dado el motivo "PROHIBIDO" y el rol "GERENTE"
  Cuando se intenta construir un PERMISO con cada uno
  Entonces cada intento falla con ValueError
  Y los motivos admitidos son los cuatro del borrador: ROL_INSUFICIENTE, AUTO_RESOLUCION, NO_ES_SOLICITANTE y ORIGEN_NO_VERIFICADO
```

### CA-8 `[M]` · Sesión ausente, límite de intentos y recurso inexistente · M3

```gherkin
Escenario: Sin sesión responde 401 SESION
  Dado un caso de uso de prueba que lanza una sesión con motivo "SIN_SESION"
  Cuando el manejador la serializa
  Entonces la respuesta es 401 con tipo "SESION" y motivo "SIN_SESION"
  Y valida contra el esquema ErrorSesion del borrador

Escenario: Demasiados intentos responde 429 con Retry-After
  Dado un límite de intentos con reintentar_en_s 30
  Cuando el manejador lo serializa
  Entonces la respuesta es 429 con tipo "LIMITE_INTENTOS", reintentar_en_s 30 y la cabecera Retry-After con el valor 30
  Y valida contra el esquema ErrorLimiteIntentos del borrador

Escenario: Un recurso inexistente responde 404 NO_ENCONTRADO con su recurso
  Dado un caso de uso de prueba que lanza un no encontrado con recurso "requisicion"
  Cuando el manejador lo serializa
  Entonces la respuesta es 404 con tipo "NO_ENCONTRADO" y recurso "requisicion"
  Y valida contra el esquema ErrorNoEncontrado del borrador

Escenario: Una ruta que no existe también responde NO_ENCONTRADO
  Dado la aplicación sin ninguna ruta llamada "/api/v1/no-existe"
  Cuando se hace GET sobre esa ruta
  Entonces la respuesta es 404 con tipo "NO_ENCONTRADO" y no el {"detail": "Not Found"} de FastAPI
  Y el recurso es la ruta pedida `(asumido)`

Escenario: Rechazo — motivo de sesión o espera negativa fuera de contrato no se construyen
  Dado el motivo de sesión "EXPIRADA" y reintentar_en_s -1
  Cuando se intenta construir cada uno
  Entonces cada intento falla con ValueError
```

### CA-9 `[M]` · Las acciones se filtran por los roles de quien llama · M5

> **Matiz acordado al cerrar el ticket (reauditoría de arquitectura, `F005`).** `REINTENTAR` de una `CONCURRENCIA` no se filtra por rol: repite la operación que quien llama acaba de invocar, y el vencimiento solo ocurre después de que `api/` comprobó su rol. Sin esta excepción, mientras TKT-006 no fije los roles, todo vencimiento saldría sin su salida documentada y violaría `CA-5`. Las demás acciones de una concurrencia, y todas las de las otras clases, siguen filtradas.

```gherkin
Escenario: El mismo rechazo ofrece acciones distintas a dos usuarios con roles distintos
  Dado un rechazo con dos acciones candidatas
  Y CAPTURAR_PRESUPUESTO_CONTROL, que solo puede ejecutar DIRECCION_GENERAL
  Y VER_REQUISICION, que pueden ejecutar todos los roles
  Cuando el manejador serializa el rechazo para alguien con el rol DIRECCION_GENERAL
  Entonces acciones contiene las dos
  Cuando lo serializa para alguien con el rol COMPRAS
  Entonces acciones contiene solo VER_REQUISICION

Escenario: El permiso efectivo es la unión de los roles
  Dado alguien con los roles COMPRAS y ADMINISTRACION
  Y una acción que solo puede ejecutar ADMINISTRACION
  Cuando el manejador serializa el rechazo
  Entonces la acción se ofrece

Escenario: Rechazo — nunca se ofrece una acción que daría 403
  Dado alguien con el rol RESIDENTE y una acción que no puede ejecutar ningún rol que tenga
  Cuando el manejador serializa el rechazo
  Entonces acciones llega vacía y no contiene ninguna acción prohibida
  Y el rechazo conserva su regla, su detalle y su mensaje

Escenario: Rechazo — sin rol conocido no se ofrece ninguna acción restringida
  Dado una petición cuyos roles de quien llama no se conocen
  Cuando el manejador serializa un rechazo con una acción restringida a un rol
  Entonces la acción no se ofrece
```

El cuarto escenario fija el comportamiento seguro ante la ausencia de datos: omitir la acción es el fallo permitido, ofrecer una que dé `403` no.

### CA-10 `[M]` · Toda respuesta lleva identificador de correlación, y el error lo repite en el cuerpo · M7 · `RNF-13`

```gherkin
Escenario: Una respuesta exitosa lleva la cabecera
  Dado una ruta de prueba que responde 200
  Cuando se hace la petición
  Entonces la respuesta lleva la cabecera X-Correlacion-Id con un UUID válido

Escenario: El error repite el mismo identificador en el cuerpo
  Dado cada uno de los ocho tipos de error de prueba
  Cuando el manejador los serializa
  Entonces el correlacion_id del cuerpo es igual al de la cabecera X-Correlacion-Id
  Y es un UUID válido según el esquema Uuid del borrador

Escenario: Dos peticiones reciben identificadores distintos
  Dado dos peticiones consecutivas
  Cuando se comparan sus cabeceras X-Correlacion-Id
  Entonces son distintas

Escenario: Rechazo — una cabecera enviada por el cliente no se acepta ni se refleja
  Dado una petición con la cabecera X-Correlacion-Id igual a "valor-arbitrario\nlinea-inyectada"
  Cuando se atiende
  Entonces el identificador de la respuesta lo generó el servidor y es un UUID
  Y el valor del cliente no aparece en el cuerpo, en las cabeceras de respuesta ni en el registro técnico `(asumido)`
```

### CA-11 `[M]` · El registro técnico es JSON, lleva la correlación y no lleva datos sensibles · M7 · `RNF-13`

```gherkin
Escenario: Cada petición deja una línea JSON con su correlación
  Dado la aplicación con el registro capturado por la prueba
  Cuando se atiende una petición que termina en un rechazo REGLA_NEGOCIO
  Entonces el registro contiene una línea JSON válida con correlacion_id, método, ruta y estado 409
  Y su correlacion_id es el de la cabecera de la respuesta

Escenario: Rechazo — el registro no contiene cuerpos, cookies ni credenciales
  Dado una petición con el cuerpo {"contrasena": "secreta-123"}, la cabecera Cookie y la cabecera Authorization
  Cuando se atiende
  Entonces ninguna línea del registro contiene "secreta-123", el valor de la cookie ni el de Authorization

Escenario: El registro técnico no es la bitácora
  Dado un rechazo de regla
  Cuando se atiende
  Entonces no se escribe ninguna fila en la tabla bitacora
  Y el correlacion_id no se asienta en ella
```

### CA-12 `[M]` · La aplicación es servible y el marcador del comando se retira · M1, M9 · regla 11

```gherkin
Escenario: La fábrica construye la aplicación y publica el contrato
  Dado la fábrica de la aplicación
  Cuando se construye y se pide GET /openapi.json
  Entonces la respuesta es 200 y el cuerpo es un OpenAPI válido

Escenario: El comando de desarrollo arranca
  Dado las dependencias instaladas con uv sync --locked
  Cuando se ejecuta uv run fastapi dev en backend/
  Entonces el proceso queda escuchando y responde a GET /openapi.json con 200

Escenario: Ninguna ruta ni manejador es una corrutina
  Dado la aplicación construida y sus rutas y manejadores de excepción registrados
  Cuando un test los recorre
  Entonces ninguno se declara con async def

Escenario: Rechazo — una ruta async def se detecta
  Dado una ruta de prueba declarada con async def añadida a la aplicación
  Cuando corre el mismo recorrido
  Entonces el test falla y nombra la ruta

Escenario: La documentación deja de decir «desde TKT-005»
  Dado CLAUDE.md y docs/arranque-local.md
  Cuando se leen tras el cambio
  Entonces uv run fastapi dev ya no está marcado «desde TKT-005 (asumido)»
  Y las marcas «desde TKT-008», «desde TKT-009» y «desde TKT-059» siguen intactas
```

El recorrido de rutas y manejadores no cubre el *middleware* de correlación, que por construcción es una aplicación ASGI. Es el supuesto `PA-T9`.

### CA-13 `[M]` · Los ocho cuerpos salen por un único camino · M2, M3

```gherkin
Escenario: Todo rechazo pasa por el mismo manejador y el mismo serializador
  Dado el conjunto de manejadores de excepción registrados en la aplicación
  Cuando un test los enumera
  Entonces hay un manejador por familia de excepción del contrato y ninguno por regla
  Y ninguno devuelve un dict suelto con un mensaje

Escenario: Rechazo — una excepción sin contrato no se disfraza de regla
  Dado un caso de uso que lanza un RuntimeError con el texto "RN-03 excedida"
  Cuando el manejador lo atiende
  Entonces no responde 409 ni tipo "REGLA_NEGOCIO"
  Y el texto del error no se interpreta como regla
```

### CA-14 `[S]` · Un error no controlado responde `500` mínimo con su correlación · S1

```gherkin
Escenario: Un error no controlado no filtra traza ni texto
  Dado una ruta de prueba que lanza RuntimeError("fallo con detalle interno")
  Cuando se hace la petición
  Entonces la respuesta es 500 con un mensaje genérico y correlacion_id
  Y el cuerpo no contiene "fallo con detalle interno", ni una traza, ni el nombre de la excepción
  Y la cabecera X-Correlacion-Id es la del cuerpo
  Y el registro técnico contiene la traza y ese mismo correlacion_id

Escenario: Rechazo — el 500 no se confunde con un rechazo
  Dado el cuerpo del 500
  Cuando se compara con los ocho tipos del contrato
  Entonces no tiene ningún tipo de regla, de conflicto ni de permiso
```

### CA-15 `[S]` · Un valor de `tipos_base` mal formado en la entrada llega como `422` · S2

```gherkin
Escenario: Una cadena que no es un decimal llano responde FORMATO
  Dado una ruta de prueba cuyo cuerpo tiene un campo importe validado con Dinero
  Cuando se envía importe "1e3"
  Entonces la respuesta es 422 con tipo "VALIDACION"
  Y errores contiene campo "importe" y codigo "FORMATO"

Escenario: Rechazo — un error del programa en tipos_base no se disfraza de error del usuario
  Dado un caso de uso que suma un Dinero y una Cantidad y recibe TypeError
  Cuando el manejador lo atiende
  Entonces el resultado es el de un error no controlado y no un 422
```

### Criterios de regresión

#### CA-R1 `[M]` · Instalación reproducible

```gherkin
Escenario: uv.lock incluye las dependencias nuevas y la instalación es reproducible
  Dado el pyproject.toml con FastAPI, Pydantic y structlog y su uv.lock regenerado
  Cuando se ejecuta uv sync --locked
  Entonces termina sin cambiar uv.lock

Escenario: Rechazo — un uv.lock desactualizado falla
  Dado una dependencia añadida a pyproject.toml sin regenerar uv.lock
  Cuando se ejecuta uv sync --locked
  Entonces el comando falla
```

#### CA-R2 `[M]` · Calidad estática sin flotantes

```gherkin
Escenario: Ruff, mypy y verificar_float terminan en verde
  Cuando se ejecutan uv run ruff check, uv run mypy y uv run python -m herramientas.verificar_float
  Entonces los tres terminan sin hallazgos sobre el código nuevo y el existente

Escenario: Rechazo — un float en una firma de tipos o de dominio sigue fallando
  Dado una firma de dominio con un parámetro float añadida de prueba
  Cuando corre verificar_float
  Entonces falla y nombra el archivo
```

#### CA-R3 `[M]` · Fronteras intactas

```gherkin
Escenario: Los 15 contratos de import-linter siguen en verde sin ignore_imports
  Cuando se ejecuta uv run lint-imports
  Entonces los 15 contratos pasan y ninguno declara ignore_imports

Escenario: Rechazo — importar FastAPI, Pydantic o structlog desde dominio/ falla
  Dado un archivo de prueba en dominio/ que importa fastapi, pydantic o structlog
  Cuando se ejecuta uv run lint-imports
  Entonces el contrato dominio-sin-framework falla

Escenario: Rechazo — la composición de la aplicación no abre una puerta entre módulos
  Dado la aplicación y su raíz de composición, ubicadas donde el diseño decida
  Cuando se ejecuta uv run lint-imports
  Entonces ningún contrato exhaustivo —esqueleto-modulos, solo-por-interfaz, grafo-<módulo>— se rompe
```

#### CA-R4 `[M]` · La suite existente sigue en verde

```gherkin
Escenario: La suite de TKT-003 y TKT-004 pasa con el rol de aplicación
  Dado Docker en marcha
  Cuando se ejecuta uv run pytest
  Entonces las pruebas de identidad, permisos, tipos base y fronteras pasan sin cambios
  Y las pruebas siguen conectándose con el rol de aplicación y no con el propietario

Escenario: Rechazo — las pruebas de la aplicación no abren la base con otro rol
  Dado una prueba nueva que necesita base de datos
  Cuando se conecta
  Entonces lo hace con el rol de aplicación
```

#### CA-R5 `[M]` · Las marcas de otros tickets siguen intactas

```gherkin
Escenario: Solo se retira la marca de este ticket
  Dado CLAUDE.md y docs/arranque-local.md tras el cambio
  Cuando se buscan las marcas "desde TKT-"
  Entonces siguen presentes TKT-008, TKT-009 y TKT-059
  Y TKT-005 ya no aparece en el comando uv run fastapi dev
```

#### CA-R6 `[M]` · Documentación y codificación

```gherkin
Escenario: Los verificadores de documentación pasan
  Cuando se ejecutan python tools/verificar_docs.py y python tools/extraer_mermaid.py
  Entonces terminan sin problemas

Escenario: Rechazo — un archivo con BOM o con CRLF se detecta
  Dado un archivo nuevo con BOM o con finales de línea CRLF
  Cuando corre verificar_docs.py
  Entonces falla y nombra el archivo
```

#### CA-R7 `[M]` · `serializar()` sigue rechazando lo sin cuantizar

```gherkin
Escenario: tipos_base no cambia de comportamiento
  Dado la suite de tipos base
  Cuando corre tras el cambio
  Entonces los tests de serializar() que rechazan un valor con más decimales que su escala siguen en verde
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-002, archivado. TKT-004, también archivado, aporta `serializar()`. Bloquea a TKT-006, TKT-008, TKT-020, TKT-021, TKT-057, TKT-058 y TKT-061 |
| **N** | Describe el qué, no impone el cómo | Sí | Los nombres de la excepción, del paquete y de la fábrica quedan para el diseño. Se fija solo quién lanza, qué forma sale y qué no se puede construir |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con matiz | El valor para el usuario final llega con las historias que lo usan. Lo que el ticket entrega hoy es capacidad de entregar valor, como el resto de la Épica 0 |
| **E** | Estimable sin investigar antes | Sí | Talla S en el ticket; el reparto en capas y el sitio de la composición es trabajo de diseño, pero acotado. Hay un riesgo de talla en `PA-T3` |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Quince criterios de aceptación y siete de regresión. Si el diseño supera unas 400 líneas, se parte en entregas como en TKT-004 |
| **T** | Sus criterios se pueden ejecutar | Sí | Todo se verifica con `TestClient`, comparación contra `openapi.yaml` y un recorrido del enrutador. `CA-12` arranca el comando real |

Ningún fallo. Pasa.

## Definition of Done

La del tipo Fundación, asimilada a Funcionalidad sin criterios de negocio ([`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo)).

- [ ] Los trece criterios `[M]` y los siete de regresión, cumplidos
- [ ] Cada escenario tiene su test, con el identificador del criterio en el nombre y el rechazo comprobando el contrato de error completo
- [ ] Cada test se vio fallar por la razón esperada antes de que existiera el código
- [ ] Ningún Should implementado sin su criterio en esta spec
- [ ] Auditorías de arquitectura y de seguridad en `APROBADO`
- [ ] Documentación afectada actualizada en el mismo cambio (M9)
- [ ] `uv run ruff`, `mypy`, `lint-imports`, `verificar_float` y `pytest` en verde; `verificar_docs.py` y `extraer_mermaid.py` en verde

## Preguntas abiertas y supuestos

Todo lo marcado `(asumido)` en los criterios se repite aquí.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | La excepción de rechazo la lanza el **caso de uso** a partir del resultado de la función de regla, no el dominio | Si la lanzara `dominio/`, habría que decidir cómo pasa `import-linter` sin `ignore_imports`, que el ADR de interfaz publicada prohíbe | Resuelto por el usuario, 2026-10-20 |
| PA-T2 | Los roles de quien llama y los roles que exige cada acción entran como datos. De dónde salen en una petición real —sesión de TKT-006, y `x-roles` del borrador para la acción— queda para TKT-006 y para cada caso de uso | Si no se documenta, TKT-021 y TKT-025 construirán cada uno su propia tabla de roles por acción | Resuelto el mecanismo, 2026-10-20. **Abierto el origen de los roles por acción:** se anota como ticket sugerido y se decide en el diseño |
| PA-T3 | Dónde viven la excepción, el manejador y la raíz de composición. `esqueleto-modulos` es exhaustivo sobre los hijos de `cimenta/`, `tipos-base-puro` solo admite la biblioteca estándar y el ADR prohíbe `ignore_imports`. La excepción la importan los casos de uso de todos los módulos | Un paquete común bajo `cimenta/` rompe `esqueleto-modulos`; uno fuera de `cimenta/` queda sin análisis de `import-linter`. Puede exigir un contrato nuevo y subir la talla | **Abierta, de diseño.** `CA-R3` fija lo que no puede romperse |
| PA-T4 | Un `404` de enrutado responde `NO_ENCONTRADO` con `recurso` igual a la ruta pedida | El borrador no dice qué `recurso` lleva un `404` que no viene de un caso de uso. Si debía ser otra cosa, cambia un campo | Resuelto el comportamiento por el usuario; el valor de `recurso` es `(asumido)` |
| PA-T5 | El `500` con mensaje genérico y `correlacion_id`, sin `tipo` que lo clasifique entre los ocho. API §3 dice «ninguno más» | Si el cliente exige un `tipo`, habría que añadir un noveno al borrador. Escalado: el borrador se corrige antes de diseñar `S1`, con revisión humana | **Abierta.** Bloquea solo a `S1`; los Must no dependen de ella |
| PA-T6 | Cada error de Pydantic se traduce a uno de los siete códigos del enum cerrado. Uno sin correspondencia conocida se traduce a `FORMATO`. Tipos con equivalente claro: campo ausente `OBLIGATORIO`; cadena mal formada `FORMATO`; `gt` y `ge` `NO_POSITIVO` o `FUERA_DE_RANGO`; `max_length` `DEMASIADO_LARGO`; enumerado `VALOR_NO_PERMITIDO` | Si el mapa elegido no coincidiera con lo que la interfaz espera, un formulario marcaría el campo con el código equivocado | `(asumido)`; la tabla exacta se fija en el diseño |
| PA-T7 | El servidor **siempre genera** el identificador de correlación y descarta el que traiga la petición | Si el cliente debiera propagar su propio identificador, no se podría correlacionar una operación desde el origen. Es el supuesto seguro frente a inyección en el registro | `(asumido)`; escalado al usuario en el gate del diseño |
| PA-T8 | El motivo de `PERMISO` tiene cuatro valores, los del borrador. Arquitectura §7.3 y API §3.1 (tabla) listan tres, y el supuesto 5 de API §7 dice que quien no es el solicitante recibe `ROL_INSUFICIENTE`, contra `NO_ES_SOLICITANTE` del borrador | El ticket implementa el enum. Si el supuesto 5 prevaleciera, `NO_ES_SOLICITANTE` sobraría | **Hallazgo documental.** Manda el borrador ([`docs/05-tickets-trabajo.md`](../../../docs/05-tickets-trabajo.md): «Si una ruta … difieren, manda el borrador»); M9 alinea los documentos. Se escala por si el usuario decidiera lo contrario |
| PA-T9 | La regla 11 —nunca `async def`— rige para rutas y manejadores de excepción. El *middleware* de correlación es ASGI y no bloquea | Si la regla incluyera el *middleware*, habría que resolver la correlación de otro modo | `(asumido)` |
| PA-T10 | `Retry-After` de `CONCURRENCIA` lo fija quien la lanza como entero ≥0; este ticket no elige un valor por omisión | Si hubiera un valor canónico, cada caso de uso repetiría un literal | `(asumido)`; TKT-021 lo fija al traducir `lock_timeout` |
| PA-T11 | La redacción del ticket dice «excepción **de dominio**». Con PA-T1 resuelta, es una excepción de aplicación | La documentación seguiría contradiciendo al código | Resuelto: M9 la corrige |

## Pasada adversarial

Resultado de `abogado-del-diablo`, modo A (retar el qué), sobre esta spec. Sin evidencia del historial de evolución para este dominio salvo la fila `convención` de `sdd/_evolucion.md` del 2026-10-01 sobre la regla inventada «los rechazos son valores, nunca excepciones», que es lo que `PA-T1` y `PA-T11` cierran.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El ticket dice «excepción de dominio» y el usuario resolvió que la lanza el caso de uso. Una spec que lo acepte sin decirlo contradice el documento fuente | Resuelto en `PA-T1` y `PA-T11`: `M9` corrige el ticket y `conv-dominio-python` §4 |
| 2 | Alta | El criterio de filtrado por roles no se puede probar con roles reales porque TKT-006 aún no existe; un test con dos roles inventados podría pasar y no demostrar nada sobre quién decide qué acción corresponde a qué rol | `CA-9` incluye el caso de ausencia de datos (omitir la acción) y la unión de roles. El origen de la tabla de roles por acción queda como pregunta abierta `PA-T2`, con ticket sugerido |
| 3 | Alta | `CA-3` dice que un importe sin cuantizar «responde como error no controlado». Eso depende de `S1`, que es Should: si no se implementa, el `500` es el de FastAPI por omisión y puede filtrar la traza | `S1` queda ligado a `PA-T5`; el diseño debe garantizar que, aunque `S1` se recorte, ningún `500` devuelve texto de excepción. Anotado como riesgo para el diseño |
| 4 | Media | El `422` por omisión de FastAPI sale en el esquema publicado de OpenAPI (`HTTPValidationError`) aunque el comportamiento ya sea otro. Dos fuentes de verdad hasta TKT-061 | Fuera de alcance, declarado en Won't. `CA-6` verifica el comportamiento, no el esquema publicado |
| 5 | Media | `CA-10` descarta el identificador entrante. Si el cliente de TKT-008 envía uno y espera verlo de vuelta, el contrato diverge | `PA-T7`, con escalado en el gate del diseño. Es el supuesto seguro: evita inyección en el registro |
| 6 | Media | El `404` de enrutado tendría un `recurso` inventado y no uno de un caso de uso | `PA-T4`, marcado `(asumido)` |
| 7 | Baja | `CA-12` arranca `uv run fastapi dev` en una prueba, que puede ser frágil por puertos y por tiempo | Se deja como criterio con la salvedad de que el diseño elija una prueba de humo sin depender de un puerto fijo |

Veredicto: siete objeciones. Ninguna descubre una regla de negocio que el PRD no tenga; todas son decisiones de diseño sin documentar o supuestos marcados. No hay escalada obligatoria.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

**Qué existe hoy.** `backend/cimenta/` tiene los diez módulos con `api/`, `aplicacion/`, `dominio/` e `infraestructura/`, cada uno con un `interfaz.py` vacío. `backend/tipos_base/` tiene `Dinero`, `Cantidad`, `Rendimiento`, `Porcentaje` y `sumar`; `serializar()` rechaza un valor sin cuantizar y sus errores son `TypeError`, `ValueError` y `ZeroDivisionError`. `backend/herramientas/` tiene `verificar_float`, conexión y contraseñas de roles. `backend/tests/` es plano, con `conftest.py` basado en testcontainers y rol de aplicación. La configuración de `import-linter` vive en `[tool.importlinter]` de `pyproject.toml`, con 15 contratos. No hay `main.py`, ni aplicación, ni enrutadores.

**Dependencias nuevas.** FastAPI, Pydantic v2 y `structlog`, más lo que las pruebas necesiten (`httpx` para `TestClient`, un validador de esquemas JSON). `pydantic-settings` y el arranque que falla sin secretos son de TKT-057. Conviene consultar Context7 al escribir contra FastAPI y Pydantic.

**Contrato que se implementa.** Esquemas `ErrorReglaNegocio`, `ErrorConflictoEstado`, `ErrorConcurrencia`, `ErrorValidacion`, `ErrorPermiso`, `ErrorSesion`, `ErrorLimiteIntentos` y `ErrorNoEncontrado`, más `Accion`, `Rol`, `ReglaId`, `Uuid` y `CodigoConflicto` de [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml), líneas 3929 a 4187. Ninguna operación del borrador lleva `x-tickets: TKT-005`: el ticket no tiene endpoint propio.

**Documentos que cambian.** `CLAUDE.md` (marca del comando), `docs/arranque-local.md` (línea 109), `docs/05-tickets-trabajo.md` (la redacción «excepción de dominio»), `docs/02-arquitectura.md` §7.3 y `docs/07-especificacion-api.md` §3.1 y §7 (motivos de `PERMISO`), `.claude/skills/conv-dominio-python/SKILL.md` §4, `.claude/skills/conv-backend-fastapi/SKILL.md` y `.claude/agents/desarrollador-dominio.md` (la excepción la lanza el caso de uso).

**Quién consume esto.** TKT-006 (`SESION` y `PERMISO`, roles de la sesión), TKT-008 (esquemas para `openapi-typescript`, `correlacion_id` en la pantalla de bloqueo, [wireframes §6](../../../docs/08-wireframes.md#6-pantalla-de-bloqueo)), TKT-020 (convierte el resultado de `RN-03` en el rechazo), TKT-021 (`SIN_LINEA_BASE_CONGELADA`, `SIN_PRESUPUESTO_CONTROL`, `CONCURRENCIA`), TKT-057 (`LIMITE_INTENTOS`, `ORIGEN_NO_VERIFICADO`), TKT-058 (agrega por `correlacion_id`) y TKT-061 (prueba de contrato).
