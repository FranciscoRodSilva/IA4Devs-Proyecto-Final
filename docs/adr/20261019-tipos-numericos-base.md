# Tipos numéricos base con aritmética exacta y redondeo explícito

## Estado

Aceptado

## Contexto y problema

Los importes de una obra son dinero: un precio unitario, un destajo o una retención que se desvía un centavo en una explosión de insumos de miles de renglones acaba visible en el presupuesto. La regla 1 de [CLAUDE.md](../../CLAUDE.md) fija el tipo en cada capa (`Decimal` en Python, `NUMERIC` en PostgreSQL, cadena en JSON, `decimal.js` en el cliente) y prohíbe `float` en cualquier firma de `dominio/`. Esa regla no responde a tres preguntas que cada módulo tendría que contestar por su cuenta: dónde viven los tipos que todos importan, con qué contexto de `decimal` se calcula y cuándo se redondea. Por defecto, `decimal` calcula con el contexto del proceso, que cualquier módulo puede cambiar sin que el resto lo note, y `Decimal(float)` acepta sin queja el error binario que la regla prohíbe.

La arquitectura fija el criterio: se calcula con la precisión completa y se redondea una sola vez, donde la regla lo indica ([arquitectura §7.4](../02-arquitectura.md#74-dinero-y-cantidades)). El problema es que la precisión completa no cabe en un número fijo de dígitos. El producto de una cantidad (escala 4) por un rendimiento (escala 6) tiene diez decimales, y el producto de los máximos de columna tiene 32 dígitos significativos. Ninguna precisión de 28 dígitos lo conserva entero.

Este registro se escribe porque TKT-004 fija estas decisiones antes de que el primer módulo de negocio las use, y porque quien llegue después verá un paquete fuera de `cimenta/`, un contexto de `decimal` con precisión máxima y un verificador propio, y se preguntará por qué. El razonamiento completo y las fuentes que lo sostienen están en el [diseño de TKT-004](../../sdd/tickets/tkt-004/design.md).

## Opciones consideradas

**Ubicación de los tipos**

* `backend/tipos_base/`, un paquete fuera de `cimenta/`. **Elegida.**
* Un undécimo módulo `cimenta/comun`. Descartada: rompe el esqueleto de diez módulos, añade un nodo al grafo de [arquitectura §5](../02-arquitectura.md#5-contextos-delimitados) y una arista desde cada módulo.
* `cimenta/tipos.py` en la raíz del paquete. Descartada: el contrato de capas exhaustivo de `import-linter` también la rechaza.
* Un tipo de importe por cada módulo. Descartada: son cuatro sitios donde el redondeo puede divergir.

**Aritmética**

* Un contexto propio de `decimal`, con precisión máxima y las señales `Inexact` y `Rounded` atrapadas, de modo que suma, resta y producto no redondean nunca y fallan si lo hicieran. Para dividir, un contexto aparte de 28 dígitos significativos. **Elegida.**
* El contexto del proceso. Descartada: cualquier módulo que cambie la precisión global altera todos los importes.
* Una precisión fija de 28 dígitos para todo. Descartada: redondea en silencio el producto de los máximos de columna.

**Redondeo**

* `cuantizar()` explícito, con `ROUND_HALF_UP`. **Elegida**, como supuesto `(asumido)`: negocio no ha confirmado el modo, y la pregunta sigue abierta en la especificación de TKT-004 (`PA-T5`).
* `ROUND_HALF_EVEN`. Descartada por ahora: es la alternativa que negocio debe confirmar o descartar.
* Redondear en el constructor, como decía el ejemplo antiguo de la convención de dominio. Descartada: un operando ya redondeado arrastra un error que el cálculo posterior no puede deshacer.

**Serialización**

* Cadena de escala completa que rechaza un valor sin cuantizar. **Elegida.**
* Serializar redondeando. Descartada: es el redondeo oculto que la regla 1 prohíbe.

**Prohibición de `float`**

* La regla `RUF032` de Ruff para `Decimal(0.1)` más un verificador AST propio, `herramientas/verificar_float.py`, para las anotaciones. **Elegida.**
* `banned-api` (`TID251`) de Ruff. Descartada: prohíbe el acceso a `float` en todo el árbol, también en `float(x)` e `isinstance(x, float)`, y no se limita a las anotaciones.
* Un plugin de mypy. Descartada: es más código, y queda acoplado a la versión de mypy.
* Un hook de agente. Descartada: no corre en CI ni para una persona que trabaja en local.

## Decisión

Se elige un paquete `backend/tipos_base/` con cuatro objetos de valor (`Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`) y una función de suma, porque:

* Ningún resultado depende del contexto global de `decimal`. Cada operación usa un contexto propio, así que un importe no cambia porque otro módulo tocó la precisión del proceso.
* Redondear es una operación explícita. `cuantizar()` lleva el valor a la escala de su columna y falla si no cabe en ella. El redondeo ocurre una vez, donde la regla lo pide, y no al construir un valor.
* `serializar()` no redondea: rechaza lo que no se ha cuantizado. El valor que sale a JSON es el que se calculó.
* Un `float` tiene dos barreras que cubren cosas distintas. `RUF032` ataca la construcción de un `Decimal` desde un literal `float`, y el verificador ataca las anotaciones. Cada herramienta cubre lo que la otra no ve, pero ninguna es una garantía total: las dos tienen límites, que están en las consecuencias.
* Las combinaciones de tipos están cerradas. `Dinero × 2`, `Dinero + Cantidad` o `float(dinero)` terminan en `TypeError`, no en un resultado silencioso.

## Consecuencias

**Positivas**

* Un único punto de redondeo, `cuantizar()`, que cualquier módulo puede buscar y auditar.
* Las guardas de tamaño actúan antes de convertir: se rechazan las cadenas de más de 100 caracteres y los enteros de más de 140 bits. Todo entero de más de 140 bits excede de todos modos la magnitud permitida, así que la guarda solo corta el coste de convertirlo. Las cadenas admiten solo decimal llano.
* Los errores de tipo se detectan en la operación que los causa, no en el informe que los muestra.

**Negativas o costes aceptados**

* El proyecto mantiene código propio: el paquete `tipos_base/`, el verificador de `float` y sus pruebas.
* La división es la única operación que redondea sin pedirlo: da un `Porcentaje` de 28 dígitos significativos.
* Una división puede producir un `Porcentaje` cuyo propio constructor rechazaría si se vuelve a envolver su `.valor`: un cociente menor que 1e-13 tiene con 28 dígitos significativos más de 40 decimales. `cuantizar()` y `serializar()` funcionan sobre ese resultado; se asume.
* El verificador de `float` tiene límites conocidos, y `RUF032` solo cubre la construcción desde un literal. El verificador no detecta un alias `Tasa = float` ni `type Tasa = float` usados como anotación; `TypeVar(bound=float)` ni el límite de un parámetro de tipo (`def g[U: float]`); `b.float` tras `import builtins as b`; un valor por omisión `x=0.5`; `float(x)` en el cuerpo de una función, ni comentarios `# type:`. Da falso positivo con `Literal["float"]` y `Annotated[int, "float"]`. Son huecos que la revisión debe vigilar.
* La huella de `float` de la entrada pública (`_viene_de_float`, D-1 de TKT-004) es una heurística: más de 18 dígitos significativos y exactamente un `double`. Un `Decimal` legítimo de 19 o más dígitos que sea exactamente un `double`, como 2⁻²⁷ (`7.450580596923828125E-9`), se rechaza si se vuelve a envolver el `.valor` de un resultado. Los valores leídos de PostgreSQL tienen 18 dígitos o menos y no lo alcanzan.
* Los tipos rechazan al construir un valor con más de 40 decimales o con una magnitud de 10^41 o más (asumido, decisión del usuario en la revisión de TKT-004, hallazgo M-01), para impedir el consumo desmedido de memoria y tiempo con `Decimal('1E+999999999')`.
* Si negocio elige otro modo de redondeo, el cambio toca una sola constante, pero cambia cifras de todos los importes ya calculados.

**Cuándo revisar esta decisión**

* Si negocio elige un modo de redondeo distinto de `ROUND_HALF_UP`.
* Si un ticket necesita una división con más de 28 dígitos significativos.
* Si el verificador de `float` deja pasar un caso real en el código del proyecto.
