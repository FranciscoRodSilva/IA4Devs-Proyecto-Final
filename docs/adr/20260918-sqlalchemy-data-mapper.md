# SQLAlchemy 2.0 con separación explícita entre dominio y persistencia

## Estado

Aceptado

## Contexto y problema

[ADR-003](20260918-dominio-puro.md) exige un dominio sin dependencias. [ADR-004](20260918-bloqueo-pesimista-presupuesto.md) exige bloqueo pesimista de fila. El modelo de datos exige aritmética decimal exacta y una consulta de agregación con varias CTE.

Hay una ambigüedad que hunde muchas arquitecturas por capas y conviene resolver aquí, no durante la implementación: **¿las entidades del dominio son las clases del ORM?**

Si lo son, el dominio depende del ORM y la pureza se pierde. Si no lo son, hay que mapear entre dos conjuntos de clases, y ese mapeo es trabajo que alguien tiene que escribir y mantener.

## Opciones consideradas

* SQLAlchemy 2.0 con Data Mapper y dominio de objetos de valor
* SQLAlchemy con las clases del ORM como entidades del dominio
* SQLModel
* Django ORM

## Decisión

Se elige **SQLAlchemy 2.0**, y se resuelve la ambigüedad así:

> **Las reglas del dominio reciben objetos de valor, no entidades.**

```
dominio/
  valores.py      Dinero, Cantidad, Rendimiento, Porcentaje   ← decimal puro
  reglas.py       evaluar_disponibilidad(...) -> Resultado    ← funciones puras
  resultados.py   ResultadoEvaluacion, MotivoBloqueo          ← dataclasses

infraestructura/
  modelos.py      clases SQLAlchemy mapeadas a las tablas
  repositorios.py cargan, extraen valores y persisten
```

`evaluar_disponibilidad(presupuestado: Dinero, consumido: Dinero, solicitado: Dinero)` no sabe que existe una tabla, una sesión ni un modelo. La capa de aplicación carga lo necesario, extrae los valores, llama a la regla y persiste el resultado.

**Esto evita el mapeo entidad a entidad sin renunciar a la pureza.** No hay dos jerarquías de clases que mantener sincronizadas: hay objetos de valor pequeños y funciones. El coste es que la capa de aplicación tiene que cargar explícitamente lo que la regla necesita, en lugar de dejar que el ORM haga cargas perezosas dentro de la regla — y eso es deliberado, porque una carga perezosa dentro de una regla la volvería dependiente de la persistencia.

Lo que SQLAlchemy 2.0 aporta a cada exigencia:

| Exigencia | Mecanismo |
|---|---|
| Bloqueo pesimista | `select(...).with_for_update()`, con `nowait`, `of` y `skip_locked` |
| Decimal exacto | `Numeric(18, 4)` → `NUMERIC` de PostgreSQL → `decimal.Decimal` en Python |
| Consulta del semáforo | Core expone `WITH`, `UNION ALL` y ventanas sin bajar a SQL en texto |
| Migraciones | Alembic, con el SQL de disparadores escrito a mano cuando no es declarativo |

**Se descarta SQLModel** aunque sea la opción idiomática con FastAPI. Fusiona Pydantic y SQLAlchemy en una sola clase, de modo que el mismo objeto es DTO de la API y fila de la tabla. Eso **borra la frontera entre la frontera y la persistencia**, que es exactamente la separación que este diseño protege: un cambio en el esquema se propagaría al contrato de la API sin que nadie lo decida.

**Se descarta el Django ORM** por Active Record, y con él toda la familia de ORM que ata la entidad a su tabla.

## Consecuencias

**Positivas**

* Las reglas se prueban sin base de datos, que es lo que hace viables los 137 escenarios.
* El bloqueo pesimista se expresa con una llamada del ORM, sin SQL en texto.
* Los importes nunca pasan por coma flotante entre la base de datos y Python.
* La consulta del semáforo se escribe con Core y sigue siendo legible.

**Negativas o costes aceptados**

* La capa de aplicación es más explícita: carga, extrae, llama, persiste. Hay más líneas que con un Active Record.
* SQLAlchemy 2.0 tiene más superficie de API que un ORM sencillo, y su curva es real.
* Hay que resistir la tentación de pasar modelos del ORM a las reglas cuando resulte cómodo. import-linter lo impide a nivel de módulo, pero dentro de la capa de aplicación es disciplina.

**Cuándo revisar esta decisión**

* Si apareciera una regla que necesita consultar datos **durante** su evaluación, y no solo antes, habría que revisar si el corte entre valores y entidades es el correcto para ese caso.
