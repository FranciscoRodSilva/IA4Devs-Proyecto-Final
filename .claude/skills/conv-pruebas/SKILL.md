---
name: conv-pruebas
description: Convenciones de pruebas de CIMENTA — tests antes que el código, PostgreSQL y MinIO reales con testcontainers nunca SQLite, esquema por alembic upgrade head, rol de aplicación, nombre del test con el escenario HDU, rechazo con el contrato de error completo, concurrencia, mutación. Cárgala antes de escribir o auditar cualquier test.
---

# Convenciones · pruebas

## 0 · Primero el test, en rojo

**Los tests se escriben antes que el código** ([convenciones §12](../../../docs/convenciones.md#12-la-ia-en-el-ciclo-de-desarrollo)). Por cada escenario del ticket, primero el test que lo nombra; se ejecuta y **falla por la razón esperada**; después, la implementación que lo pone en verde. La salida en rojo se pega en `impl.md`. Un test que nace en verde no demuestra que prueba algo.

Los escenarios salen de la historia y de los `x-escenarios` de las operaciones del [borrador OpenAPI](../../../docs/api/openapi.yaml) cuyo `x-tickets` incluye el ticket. Las descripciones de esas operaciones enumeran los rechazos con su `tipo` y su `regla` o `codigo`: cada uno es un test.

## 1 · Nunca SQLite

Los tests levantan **PostgreSQL real** con testcontainers, y **MinIO real** cuando el ticket toca archivos: un doble del almacén no verifica que la URL prefirmada se firme, que caduque ni que el hash coincida. testcontainers necesita **Docker en marcha**; sin el demonio la suite falla, no se salta ([`conv-docker`](../conv-docker/SKILL.md)). SQLite probaría contra garantías distintas de las de producción, y treinta y ocho invariantes del proyecto viven exactamente en esas garantías: disparadores, restricciones de exclusión, `NUMERIC`, tipos con zona horaria, bloqueo `FOR UPDATE`.

- El esquema se construye con **`alembic upgrade head`**, nunca con `create_all()`. Probar contra un esquema que no es el que se despliega es probar otro sistema.
- La conexión usa el **rol de aplicación**. Con el propietario, las pruebas de permisos quedan verdes sin verificar nada.

## 2 · El nombre del test lleva el escenario

```python
def test_hdu002_esc04_requisicion_excede_importe_presupuestado(...):
    """HDU-002 esc. 4 · RN-03 — la requisición queda BLOQUEADA con su excedente."""
```

Un verificador en CI falla si un escenario de [`docs/04-historias-usuario.md`](../../../docs/04-historias-usuario.md) se queda sin test. El identificador en el nombre es lo que hace posible esa comprobación: no es decoración.

## 3 · Ningún criterio cubre solo el camino feliz

**Cada regla de negocio implicada necesita su test de rechazo.** En CIMENTA el valor del sistema está en lo que rechaza: compras que exceden el presupuesto, recepciones mayores a lo ordenado, pagos sin validación de avance, pedidos que superan el tope de consignación. Una suite que solo prueba el éxito no prueba el producto.

El test de rechazo verifica **el dato**, no solo el estado: que el excedente sea `$3,000`, que el disponible reportado sea el real, que la autorización vaya a quien corresponde. Comprobar únicamente que `estado == "BLOQUEADA"` deja pasar una regla que calcula mal.

En `api/`, el test de rechazo comprueba **el contrato de error completo**, no solo el código de estado: el `tipo` (`REGLA_NEGOCIO`, `CONFLICTO`, `CONCURRENCIA`, `VALIDACION`, `PERMISO`…), la `regla` o el `codigo` del catálogo cerrado, las cifras como cadena y las `acciones` filtradas por el rol de quien llama ([especificación de la API §3](../../../docs/07-especificacion-api.md#3-el-contrato-de-error)). Un `409` correcto con el `tipo` equivocado es un fallo.

**Lo simulado nunca consume.** Donde el ticket lee mano de obra o avance por el adaptador simulado de [ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md), un test comprueba que el importe simulado no cambia el disponible de `RN-03` y viaja marcado `SIMULADA`.

## 4 · Concurrencia donde hay bloqueo

Donde el diseño usa bloqueo pesimista, hay un test con **dos transacciones simultáneas** contra el mismo presupuesto, y pasa una sola. Es la prueba que distingue un control presupuestal real de uno decorativo: sin ella, dos requisiciones concurrentes pasan las dos y el test de una sola requisición sigue verde.

Recordatorio de la regla: una requisición `EVALUADA` **sí** consume.

## 5 · Anti-test-teatro

Un test que no puede fallar no es un test.

- En rutas críticas —reglas de dinero, límites, congelado de línea base, cálculo de avance— se hace **mutación manual mínima**: cambiar un operador (`>` por `>=`), un umbral o un signo, y confirmar que algún test se pone rojo. Si ninguno se inmuta, falta un test; se añade antes de avanzar.
- Lo que se documenta en `impl.md` es qué se mutó y qué test cayó.
- **Evidencia real.** La salida de `pytest` se pega en `impl.md`. Un «todo en verde» sin la línea de resumen no cuenta.
- Prohibido alterar o borrar un test para que la suite pase. Si un test estorba, o la regla cambió —y entonces cambia la spec— o el código está mal.

## 6 · Qué se prueba en cada capa

| Capa | Herramienta | Qué se prueba | Qué **no** |
|---|---|---|---|
| `dominio/` | pytest puro, sin base | La regla: feliz, rechazo, bordes, escalas de `Decimal` | Nada de I/O — si necesita base, la regla no es pura |
| `aplicacion/` | pytest + testcontainers | Transacción, bitácora en la misma transacción, bloqueo, concurrencia | Reimplementar los casos de la regla |
| `infraestructura/` | pytest + testcontainers (PostgreSQL, MinIO) | Disparadores que rechazan de verdad, permisos del rol de aplicación, URL prefirmada que caduca, tipo leído de los bytes | Lógica de negocio |
| `api/` | pytest + cliente de pruebas | Contrato del borrador OpenAPI: forma, `tipo` del error, `409`/`422`/`403`/`401`, CSRF, permiso por obra | La lógica, ya cubierta abajo |
| frontend | Vitest | Componente: los cuatro estados, formato de importes | Flujos completos |
| extremo a extremo | Playwright | El flujo de la historia, **incluido el de rechazo** | Casos borde de unidad |

## 7 · Corrección de error

El test que **reproduce el fallo** se commitea **antes** del arreglo, y falla. Es la Definition of Done declarada del proyecto para este tipo de ticket; sin el commit previo no hay forma de demostrar que el test probaba algo.

## 8 · Forma

- Un test, una afirmación de comportamiento. Si necesita tres `assert` para decir una cosa, bien; si dice tres cosas, son tres tests.
- Datos de prueba construidos por *fixtures* con nombre del dominio, no diccionarios anónimos repetidos.
- Nada de `sleep` para sincronizar. Nada de orden entre tests.
- Los importes se construyen desde cadena: `Decimal("12000.00")`.
