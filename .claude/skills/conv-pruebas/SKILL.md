---
name: conv-pruebas
description: Convenciones de pruebas de CIMENTA — PostgreSQL real con testcontainers nunca SQLite, esquema por alembic upgrade head, rol de aplicación, nombre del test con el escenario HDU, rechazo obligatorio, concurrencia, mutación. Cárgala antes de escribir o auditar cualquier test.
---

# Convenciones · pruebas

## 1 · Nunca SQLite

Los tests levantan **PostgreSQL real** con testcontainers. SQLite probaría contra garantías distintas de las de producción, y veintiséis invariantes del proyecto viven exactamente en esas garantías: disparadores, restricciones de exclusión, `NUMERIC`, tipos con zona horaria, bloqueo `FOR UPDATE`.

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
| `api/` | pytest + cliente de pruebas | Contrato: forma, `409`/`422`/`403`, auth, CSRF, permiso por obra | La lógica, ya cubierta abajo |
| frontend | Vitest | Componente: los cuatro estados, formato de importes | Flujos completos |
| extremo a extremo | Playwright | El flujo de la historia, **incluido el de rechazo** | Casos borde de unidad |

## 7 · Corrección de error

El test que **reproduce el fallo** se commitea **antes** del arreglo, y falla. Es la Definition of Done declarada del proyecto para este tipo de ticket; sin el commit previo no hay forma de demostrar que el test probaba algo.

## 8 · Forma

- Un test, una afirmación de comportamiento. Si necesita tres `assert` para decir una cosa, bien; si dice tres cosas, son tres tests.
- Datos de prueba construidos por *fixtures* con nombre del dominio, no diccionarios anónimos repetidos.
- Nada de `sleep` para sincronizar. Nada de orden entre tests.
- Los importes se construyen desde cadena: `Decimal("12000.00")`.
