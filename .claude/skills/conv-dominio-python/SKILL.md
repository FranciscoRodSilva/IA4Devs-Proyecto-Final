---
name: conv-dominio-python
description: Convenciones de la capa dominio/ de CIMENTA — Decimal exacto con precisión declarada, pureza sin framework, objetos de valor, cómo se expresa un rechazo de negocio, trazabilidad RN-xx. Cárgala antes de escribir o auditar cualquier archivo bajo backend/cimenta/*/dominio/.
---

# Convenciones · capa `dominio/`

La capa donde está el valor del producto y la que más fácil se contamina. Estas reglas no son estilo: tres de ellas las verifica el pipeline y falla.

## 1 · El dinero nunca es flotante

```python
# ✗ Prohibido. El linter lo bloquea.
def calcular_disponible(presupuestado: float, consumido: float) -> float: ...

# ✓
def calcular_disponible(presupuestado: Dinero, consumido: Dinero) -> Dinero: ...
```

- `Decimal` en Python, `NUMERIC` en PostgreSQL, **cadena** en JSON, `decimal.js` en el cliente.
- Se construye desde `str`, **nunca** desde `float`: `Decimal("12.10")`, no `Decimal(12.10)`. Lo segundo arrastra el error binario desde el primer carácter.
- **Las operaciones conservan la precisión completa. El redondeo es una operación explícita y separada** (`TKT-004`). No se cuantiza al vuelo dentro de un cálculo intermedio: se calcula entero y se redondea una vez, donde la regla lo diga.
- Cuantización **explícita**, con escala y modo declarados: `.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. Un redondeo implícito es una regla de negocio sin documentar.
- Cada tipo tiene su precisión declarada en [modelo de datos §2](../../../docs/03-modelo-datos.md); `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje` no comparten escala. No la inventes: búscala.
- Dividir no es redondear: donde la regla exija reparto (prorrateo de explosión de insumos), la suma de las partes debe volver a dar el total. Si no cuadra, hay que decidir dónde cae el centavo y escribirlo.

## 2 · Cero imports de framework

Ni FastAPI, ni SQLAlchemy, ni Pydantic, ni `requests`, ni `datetime.now()`.

- Si una regla necesita la fecha, **se le pasa**. Una regla que consulta el reloj no se puede probar.
- Si necesita datos, los recibe ya materializados como objetos de valor. El dominio no consulta: decide.
- `import-linter` falla el contrato `dominio-sin-framework` si se cruza. No se «arregla» añadiendo una excepción al contrato.

## 3 · Objetos de valor

```python
@dataclass(frozen=True, slots=True)
class Dinero:
    monto: Decimal
    def __post_init__(self) -> None:
        if self.monto != self.monto.quantize(ESCALA):
            raise ValueError(f"escala inválida: {self.monto}")
```

`frozen=True` porque un importe que se muta a mitad de una regla es un error que no deja rastro. `slots=True` porque impide añadir atributos por accidente.

## 4 · Cómo se expresa un rechazo de negocio

Dos piezas, y el proyecto decidió las dos:

**La función de regla evalúa y devuelve.** Pura, sin efectos, testeable sin servidor ni base de datos — ese es el motivo declarado de que el dominio sea puro ([arquitectura §6](../../../docs/02-arquitectura.md)):

```python
def evaluar_disponibilidad(
    presupuestado: Dinero, consumido: Dinero, solicitado: Dinero
) -> ResultadoEvaluacion:
    """Implementa RN-03. Sin efectos secundarios."""
```

**Existe una sola excepción de dominio** que transporta `regla`, `mensaje`, `detalle` y `acciones`, y un manejador global que la serializa al contrato de error con código `409` (`TKT-005`). Una sola, no una por regla: el [ADR del contrato de error](../../../docs/adr/20260918-contrato-error-negocio.md) descarta esa opción porque produciría veintiuna formas distintas que la interfaz tendría que tratar por separado.

El `detalle` lleva las **cifras**, no una frase: disponible real, excedente, presupuestado, solicitado. Y `acciones` convierte el bloqueo en bifurcación: a qué ruta se pide la autorización. «Operación rechazada» no es una respuesta, y el escenario de rechazo verifica esos campos.

> **`(asumido)` · quién lanza la excepción.** La documentación define la función que devuelve y la excepción que se serializa, pero no dice quién convierte una en la otra. Lo que este toolkit asume —y hay que confirmar en `TKT-005`— es que **la lanza el caso de uso** a partir del resultado, para que la función de regla siga siendo probable sin capturar excepciones. **No lo des por cerrado por tu cuenta**: si el ticket que estás implementando depende de ello, escala.

Lo que sí es seguro: una excepción de Python corriente —`ValueError`, `KeyError`— **nunca** representa un rechazo de negocio. Esas son para errores de programa: un argumento imposible, un invariante del propio objeto roto.

## 5 · Cada regla lleva su identificador

En el docstring y en el nombre del test. Es lo que ata el código a la especificación y lo que permite verificar la trazabilidad en CI.

```python
"""Implementa RN-03. Sin efectos secundarios."""
```

Si la regla que estás escribiendo no tiene `RN-xx` en el PRD: **para y escala**. No se inventan reglas de negocio.

## 6 · Definiciones que viven una sola vez

`consumido = requisiciones vivas + comprometido + ejercido`. Está definido en [modelo de datos §15](../../../docs/03-modelo-datos.md) y lo comparten la regla y el tablero. Si lo reescribes en dos sitios, se desincronizan y el semáforo deja de coincidir con el bloqueo.

Lo mismo con el avance: el denominador es `alcance_destajo`, **nunca** `SUM(avance.m2_contrato)`. Sin avance validado el porcentaje es `NULL`, no cero.

## 7 · Forma del código

- `from __future__ import annotations` en todos los módulos.
- Tipado total. `mypy --strict` limpio. `Any` solo con un comentario que lo justifique.
- Funciones cortas, un nivel de abstracción por función. Si una regla necesita tres pasos, son tres funciones con nombre, no tres bloques con comentario.
- Nombres en **español**, los del [glosario](../../../docs/glosario.md). `concepto`, `partida`, `destajo`, `rendimiento` significan cosas concretas aquí; no los traduzcas ni los sustituyas por un sinónimo que suene mejor.
- Ruff con `E,F,W,B,UP,SIM,RUF,ANN,TRY,PL`.
- Sin comentarios que narren lo que el código ya dice. Los comentarios explican el *porqué* de lo que se ve raro.

## Trampas de esta capa

| Trampa | Cómo se ve | Qué hacer |
|---|---|---|
| El `float` que entra por una constante | `TASA = 0.16` | `Decimal("0.16")` |
| El import «inofensivo» | `from pydantic import BaseModel` para un objeto de valor | `@dataclass(frozen=True)` |
| La regla que consulta | el dominio recibe un repositorio por parámetro | recibe los datos, no la fuente |
| El redondeo implícito | `round(x, 2)` | `.quantize(..., ROUND_HALF_UP)` |
| La regla inventada | un `if` que el PRD no pide | escalar |
