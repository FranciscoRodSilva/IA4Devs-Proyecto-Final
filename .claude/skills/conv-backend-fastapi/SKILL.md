---
name: conv-backend-fastapi
description: Convenciones de las capas aplicacion/, api/ e infraestructura/ de CIMENTA — rutas def nunca async, transacción en el caso de uso, Pydantic v2, SQLAlchemy 2.0 síncrono, el borrador OpenAPI como contrato, los siete tipo del contrato de error. Cárgala antes de escribir o auditar backend fuera de dominio/.
---

# Convenciones · `aplicacion/`, `api/`, `infraestructura/`

## 1 · Las rutas se declaran `def`. Nunca `async def`

```python
# ✗ Congela el bucle de eventos entero en la primera consulta bloqueante.
@router.post("/requisicion")
async def crear_requisicion(...): ...

# ✓ FastAPI la ejecuta en el pool de hilos.
@router.post("/requisicion")
def crear_requisicion(...): ...
```

SQLAlchemy aquí es **síncrono** ([ADR-013](../../../docs/adr/20260919-sqlalchemy-sincrono.md)). Una llamada bloqueante dentro de una corrutina no la detecta ningún linter: se manifiesta como latencia bajo carga, semanas después. Es la trampa número uno de este stack, y la mitad de lo que hay escrito en internet sobre FastAPI recomienda lo contrario.

Corolario de [ADR-016](../../../docs/adr/20261001-almacenamiento-de-objetos.md): como las rutas son `def`, servir un archivo por el API retendría un hilo del pool mientras dura la descarga. Por eso los archivos van por URL prefirmada y el servidor se aparta.

## 2 · El caso de uso orquesta. No decide reglas

La capa `aplicacion/`:

- **Abre la transacción** y la cierra. Una sola por caso de uso.
- Carga lo que haga falta por el repositorio, llama a la regla del dominio, persiste el resultado.
- **Escribe la bitácora en la misma transacción que el cambio.** No es un `after_commit`, no es un `BackgroundTask`, no es un hook del ORM. Si el cambio se revierte, la bitácora se revierte con él.
- Aplica el bloqueo pesimista donde el ADR lo exige: `select(...).with_for_update()` antes de evaluar el disponible. Sin él, dos requisiciones simultáneas pasan las dos.

Si aparece un `if` de negocio en `aplicacion/`, está en la capa equivocada. Un `if resultado.bloqueada:` para decidir qué persistir sí es orquestación; un `if solicitado > disponible:` no.

## 3 · Un módulo solo habla con otro por su interfaz de aplicación publicada

Nunca importando su repositorio, su modelo ni consultando su tabla. `compras` no hace `SELECT` sobre las tablas de `presupuesto`: llama al caso de uso que `presupuesto` publica.

`presupuesto` es el núcleo y no depende de nadie. `analitica` depende de todos pero **solo lee**.

## 4 · Pydantic v2

- `model_config = ConfigDict(from_attributes=True)`, `model_validate`, `model_dump`. `from_orm` y `.dict()` están deprecados.
- **`Decimal` ya se serializa como cadena en modo JSON, y el esquema lo declara `type: string`.** No hace falta añadir nada. Lo que hay que vigilar es que **nadie lo sobrescriba**: un `Annotated[Decimal, PlainSerializer(float, when_used='json')]` en un campo de dinero reintroduce el flotante por la puerta de atrás y pasa desapercibido porque el tipo Python sigue siendo `Decimal`.
- Los DTO de entrada y de salida son **distintos**. Un modelo que sirve para las dos cosas acaba exponiendo un campo que no debía.
- `pydantic-settings` para la configuración. Ningún `os.environ` suelto, ningún valor por defecto que funcione en producción.

## 5 · SQLAlchemy 2.0, estilo moderno

- `DeclarativeBase`, `Mapped[...]` con `mapped_column`, `select()` en estilo 2.0. Nada de `Query` heredado ni de `session.query(...)`.
- **`naming_convention` en el `MetaData`** — verificado contra la documentación de SQLAlchemy:

  ```python
  convencion = {
      "ix": "ix_%(column_0_label)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }

  class Base(DeclarativeBase):
      metadata = MetaData(naming_convention=convencion)
  ```

  Sin esto, Alembic genera restricciones con nombres automáticos que ninguna migración posterior puede referenciar para eliminarlas.
- El modelo del ORM es un mapa de la tabla. **Ninguna regla de negocio vive ahí**: ni en un `@validates`, ni en una `@property` que calcule un importe, ni en un `event.listen`.
- Nada de carga perezosa en el momento de serializar. Se carga explícitamente lo que el DTO necesita.

## 6 · El contrato de error es el contrato

**El borrador [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml) manda.** Rutas, métodos, códigos de estado y esquemas de error salen de ahí, no se improvisan. Las extensiones `x-tickets`, `x-roles`, `x-reglas` y `x-escenarios` de cada operación dicen qué te toca, qué rol se comprueba en `api/`, qué regla lleva el `409` y qué tests escribir ([especificación de la API §6](../../../docs/07-especificacion-api.md#6-cómo-lo-usa-la-ia)). Si el OpenAPI que publica FastAPI diverge del borrador, se corrige el código; si cambió el diseño, el borrador cambia en el mismo PR. La prueba de contrato de `TKT-061` falla el pipeline si divergen en silencio.

El cliente distingue cada rechazo por `tipo`, nunca por el texto. Son **siete `tipo`, más `NO_ENCONTRADO`**, y ninguno más (`TKT-005`, [especificación de la API §3](../../../docs/07-especificacion-api.md#3-el-contrato-de-error)):

| `tipo` | Código | Cuándo |
|---|---|---|
| `REGLA_NEGOCIO` | `409` | Una regla `RN-xx` del PRD impide la operación. Lleva `regla`, `detalle` y `acciones` |
| `CONFLICTO` | `409` | Conflicto de estado o de unicidad que **no es una `RN`**: duplicado, solicitud ya resuelta, transición no admitida, obra sin línea base congelada o sin tope de control. Lleva un `codigo` del **catálogo cerrado** `CodigoConflicto`, nunca un `RN-xx` inventado |
| `CONCURRENCIA` | `409` | Venció `lock_timeout` o `statement_timeout` (`RNF-16`). Cabecera `Retry-After`, acción `REINTENTAR`, sin `regla`. Nada se persiste |
| `VALIDACION` | `422` | Error de forma. Si la forma la impone una regla, el error del campo la cita, pero sigue siendo `422` |
| `PERMISO` | `403` | Falta el rol, la autoridad sobre la excepción o la prueba de origen. **Nunca lleva cifras del recurso** |
| `SESION` | `401` | Sin sesión, caducada, revocada o credenciales inválidas |
| `LIMITE_INTENTOS` · `NO_ENCONTRADO` | `429` · `404` | Forma mínima, con `correlacion_id` |

La frontera entre `409` y `422` se decide con una pregunta: **¿la misma petición, contra otro estado del sistema, habría pasado?** Si sí, es `409`.

Nunca un `dict` suelto con un mensaje, y nunca una excepción por regla. Hay **una sola** excepción de dominio para las reglas —`regla`, `mensaje`, `detalle`, `acciones`— y **un manejador global** que serializa todos los `tipo` (`TKT-005`). El [ADR del contrato de error](../../../docs/adr/20260918-contrato-error-negocio.md) descarta la excepción por regla porque produciría una forma por regla que la interfaz tendría que tratar por separado.

El cuerpo de `REGLA_NEGOCIO` lleva el **dato accionable** —disponible real, excedente, presupuestado, solicitado y el `consumido_desglose`— y las `acciones` con su ruta absoluta (`/api/v1/...`). **Las `acciones` se filtran por los roles de quien llama**: nunca se ofrece una que le respondería `403`. Todos los importes del detalle, como cadena. El campo `regla` solo admite el formato `RN-\d{2}`.

Una requisición bloqueada responde `409` **y aun así se persiste** en `BLOQUEADA` con su solicitud de autorización; sus identificadores viajan en el `detalle`.

El identificador de correlación de la petición viaja **dentro** del cuerpo del error, para que el usuario pueda citarlo, y en el registro estructurado de `structlog` (`RNF-13`).

Los errores no filtran trazas ni estructura interna al cliente.

## 7 · Lo que esta capa tiene prohibido

- Guardar archivos en el disco del servidor o en una columna de PostgreSQL, o servirlos por una ruta del API.
- Interpretar el XML del CFDI. Se guarda, no se concilia.
- Cerrar una orden de compra con saldo pendiente.
- Una columna de existencia de inventario. El inventario es un libro mayor de solo-anexado; las correcciones son movimientos `AJUSTE`.
- Que el cliente evalúe una regla. Lo que viene de la cola sin conexión entra por los mismos casos de uso y puede volver rechazado.
- Sumar al `consumido` de `RN-03` un importe del adaptador simulado de `analitica`, o dejarlo viajar sin la marca `SIMULADA`. La configuración rechaza el adaptador simulado con `entorno = produccion`: la aplicación no arranca ([ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md)).
- Una ruta, un código o un esquema de error que no está en el borrador OpenAPI.

## 8 · Forma del código

- Tipado total, `mypy --strict`. Ruff con `E,F,W,B,UP,SIM,RUF,ANN,TRY,PL`.
- Español, el del [glosario](../../../docs/glosario.md).
- Inyección por `Depends`, no por import global. La sesión se inyecta; no se crea dentro del caso de uso.
- `structlog` para el registro; nada de `print`. Ningún dato sensible en el log.
