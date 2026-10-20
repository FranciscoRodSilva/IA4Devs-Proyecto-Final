# Spec · TKT-004 · Tipos base del dominio con decimal exacto

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

CIMENTA no tiene hoy ningún tipo numérico propio. En `backend/cimenta/` los diez módulos existen como esqueleto vacío (TKT-002) y `identidad` tiene sus tablas (TKT-003), pero ninguna regla de negocio puede escribirse todavía: `RN-03` compara importes, `RN-06` y `RN-07` comparan cantidades, la explosión de insumos multiplica cantidades por rendimientos y el semáforo divide metros cuadrados entre metros cuadrados. Si cada ticket resolviera eso con `Decimal` suelto, cada uno elegiría su escala, su modo de redondeo y su forma de serializar, y el sistema volvería al ruido de coma flotante que motivó [ADR-002](../../../docs/adr/20260918-postgresql.md): una suma que debía dar `2755187.2112` y daba otra cifra.

Este ticket de fundación entrega los cuatro objetos de valor compartidos —`Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`—, su aritmética exacta, el redondeo como operación explícita y separada, su serialización como cadena y la regla de linter que impide que un `float` entre en una firma de dominio. También resuelve la deuda que dejó TKT-002: dónde viven los tipos que todos los módulos importan sin romper `esqueleto-modulos`, y cómo se cierra la lista negra de `dominio-sin-framework` (deuda `O1`).

Estado de partida, criterio por criterio:

| Criterio del ticket | Estado de partida |
|---|---|
| Tipos sobre decimal de precisión fija, nunca flotante | No existe ningún tipo; el dominio de los módulos está vacío |
| Precisiones del [modelo de datos §2](../../../docs/03-modelo-datos.md#2-convenciones) | Solo existen como convención escrita: importes `NUMERIC(18,4)`, cantidades `NUMERIC(14,4)`, rendimientos `NUMERIC(18,6)`, porcentajes `NUMERIC(9,6)` |
| Operaciones con precisión completa y redondeo explícito | No existe; la única mención es [arquitectura §7.4](../../../docs/02-arquitectura.md) y `conv-dominio-python` §1 |
| Serialización a JSON como cadena | No existe; Pydantic llega con TKT-005 y `dominio/` no puede importarlo |
| Test de `0.1 + 0.2` y test de los 27 insumos | No existen. Los datos reales de la explosión no están en el repositorio (`README`: los presupuestos del cliente no se versionan) |
| Regla de linter contra `float` | No existe. `CLAUDE.md`, regla 1, dice «el linter lo bloquea (desde TKT-004)» y hoy no es verdad |
| Ubicación de los tipos compartidos | Sin decidir. Un hijo nuevo de `cimenta/` rompe `esqueleto-modulos`, que es exhaustivo sobre los diez módulos |
| `dominio-sin-framework` | Lista negra de tres paquetes (`fastapi`, `sqlalchemy`, `pydantic`). Cualquier otro paquete de tercero pasa (deuda `O1` de TKT-002) |

La spec parte de cuatro decisiones del usuario, tomadas el 2026-10-19 en el intake:

1. **Datos de los 27 insumos:** fixture sintético, con el total esperado calculado de forma independiente. La reconciliación con el total real (`2755187.2112`) queda en TKT-016.
2. **Ubicación:** un paquete fuera de `cimenta/`, como Alembic, para no tocar `esqueleto-modulos`.
3. **Tipos:** cuatro, con precisión completa en el valor y la escala de columna aplicada en la frontera, por cuantización explícita.
4. **Alcance de la prohibición de `float`:** las firmas de `dominio/` y las del paquete de tipos base.

## Historia de usuario

Ticket de fundación (Épica 0), sin historia de usuario asociada. El rol que lo usa es quien desarrolla el proyecto, persona o agente.

**Como** persona o agente que desarrolla CIMENTA
**quiero** tipos de valor para dinero, cantidades, rendimientos y porcentajes que hagan aritmética exacta y solo redondeen cuando se les pide
**para** que ninguna regla de negocio posterior pueda introducir un error de coma flotante ni un redondeo oculto, y para que quien intente hacerlo lo vea fallar en el linter antes de llegar a revisión.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Cuatro objetos de valor inmutables sobre `Decimal`, en un paquete fuera de `cimenta/`: `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`. Solo se construyen desde `str`, `int` o `Decimal`; nunca desde `float`. Distintos entre sí: no se mezclan |
| | **M2.** Aritmética que conserva la precisión completa, sin redondeo ni dependencia del contexto de `decimal` del proceso: suma y resta de un mismo tipo, `Cantidad × Rendimiento`, `Dinero × Cantidad`, `Dinero × Porcentaje`, y división `Cantidad ÷ Cantidad` y `Dinero ÷ Dinero` que da un `Porcentaje` |
| | **M3.** Redondeo como operación explícita y separada: `cuantizar` lleva el valor a la escala de su tipo (`18,4`, `14,4`, `18,6`, `9,6`) con `ROUND_HALF_UP` `(asumido)` y falla si el valor no cabe en la precisión de la columna |
| | **M4.** Serialización a JSON como **cadena** de escala completa, nunca como número, sin redondear por su cuenta, y lectura desde cadena con formato estricto |
| | **M5.** Test de que `0.1 + 0.2` da exactamente `0.3` |
| | **M6.** Test de que sumar 27 insumos sintéticos reproduce un total esperado calculado de forma independiente, sin desviación |
| | **M7.** Regla de linter que falla ante un `float` en una firma de `dominio/` o del paquete de tipos base, y ante `Decimal` construido desde un literal `float`, con la prueba de que falla |
| | **M8.** Ajuste de `import-linter` y de `mypy`, sin romper los 14 contratos de TKT-002: `dominio-sin-framework` pasa a lista blanca (cierra `O1`) y el paquete de tipos base queda bajo `mypy` estricto y bajo su propio contrato de pureza |
| | **M9.** Consecuencia documental de M1 a M8, que no amplía el alcance: retirar la marca «desde TKT-004» de `CLAUDE.md` y de `docs/arranque-local.md`, documentar la ubicación del paquete y el modo de redondeo, y alinear `conv-dominio-python` §1 y §3 con los tipos |
| **Should** | **S1.** Los tests de los tipos y del linter no requieren Docker: se pueden ejecutar con `uv run pytest` sin PostgreSQL en marcha |
| **Could** | — |
| **Won't** | Conversión de divisas (non-goal del ticket) · serialización con Pydantic y validación de entrada del API (TKT-005) · tipo `PrecioUnitario` y variantes de signo (`ImporteNoNegativo`, `CantidadPositiva`…): el signo lo valida cada caso de uso · reparto o prorrateo y la decisión de dónde cae el centavo (fase 2, `RN-23`) · `Dinero ÷ Cantidad` y cualquier otra operación que ningún ticket necesite todavía · tolerancia decimal de TKT-014 · datos reales del Excel y su reconciliación con `2755187.2112` (TKT-016) · prohibir los literales `float` sueltos y las constantes `float` de `dominio/` |

## Non-goals

- No implementa conversión de divisas: el sistema es en pesos mexicanos.
- No sabe nada de la base de datos ni del API. No hay tipo de columna de SQLAlchemy, ni esquema de Pydantic, ni DTO: los adaptan TKT-005 y los tickets de cada módulo.
- No valida rangos de negocio. Que una cantidad no sea negativa (invariante 8) o que un porcentaje no pase de uno lo decide cada caso de uso. Los tipos solo aceptan lo que cabe en la precisión de su columna.
- No define cómo un caso de uso traduce un error de programa a una respuesta del API. Los errores de estos tipos son excepciones corrientes de Python, **nunca** un rechazo de negocio ([`conv-dominio-python` §4](../../../.claude/skills/conv-dominio-python/SKILL.md)).
- No reparte importes ni prorratea. Dividir no es repartir: la suma de las partes de un reparto es una regla de fase 2.
- No amplía el conjunto de reglas de Ruff a las de `conv-dominio-python` §7: la discrepancia se anota como ticket futuro.
- No reescribe el contrato de fronteras de TKT-002 más allá de `dominio-sin-framework` y del contrato de pureza del paquete nuevo.

## Reglas de negocio implicadas

Ninguna regla `RN-xx` se implementa en este ticket: no hay lógica de negocio. Sostiene reglas de `CLAUDE.md`, un principio de arquitectura y la base numérica de las reglas que vendrán.

| Referencia | Qué exige | Dónde está |
|---|---|---|
| Regla 1 de `CLAUDE.md` | El dinero nunca es flotante: `Decimal`, `NUMERIC`, cadena en JSON; `float` prohibido en firmas de dominio y el linter lo bloquea | [`CLAUDE.md`](../../../CLAUDE.md) |
| Regla 2 de `CLAUDE.md` | `dominio/` no importa nada: el paquete de tipos base tampoco puede importar framework | `CLAUDE.md` |
| Principio 7 de arquitectura §2 | Importes y rendimientos en decimal de precisión fija; flotante prohibido en cualquier campo monetario o de cantidad | [`docs/02-arquitectura.md`](../../../docs/02-arquitectura.md) |
| Arquitectura §7.4 | Se calcula con precisión completa y se redondea solo al presentar, nunca en cálculos intermedios | `docs/02-arquitectura.md` |
| API §2.3 | El servidor responde siempre con la escala completa, cuatro decimales en importes | [`docs/07-especificacion-api.md`](../../../docs/07-especificacion-api.md) |
| Regla 12 de `CLAUDE.md` | Sin avance validado el porcentaje es `NULL`, no cero: una división entre cero no puede devolver cero | `CLAUDE.md` |
| Invariante 8 | Cantidades y precios no negativos. No es de este ticket: lo valida cada caso de uso, pero la decisión de que los tipos admitan signo lo condiciona | [modelo de datos §13](../../../docs/03-modelo-datos.md#13-invariantes-en-base-de-datos) |
| [ADR-002](../../../docs/adr/20260918-postgresql.md), [ADR-017](../../../docs/adr/20261015-fuentes-simuladas-analitica.md) | Aritmética exacta y precisiones; nada de fase 2 | `docs/adr/` |

Términos del [glosario](../../../docs/glosario.md) que importan: *rendimiento* («cantidad de insumo consumida por cada unidad de concepto ejecutada»), *explosión de insumos* (suma de `cantidad_concepto × rendimiento_insumo`) y *cargo*. `Dinero`, `Cantidad` y `Porcentaje` no tienen entrada en el glosario: se la añade la consecuencia documental M9 si el diseño lo juzga necesario.

## Invariantes que deben sobrevivir al cambio

El ticket crea código nuevo, pero modifica archivos que ya funcionan: `backend/pyproject.toml` y `backend/uv.lock` (contratos de `import-linter`, `mypy`), `CLAUDE.md`, `docs/arranque-local.md` y `conv-dominio-python`. Estas son las garantías de TKT-001 a TKT-003 que deben sobrevivir:

| Garantía existente | Qué protege | Criterio de regresión |
|---|---|---|
| Ruff y mypy terminan en verde sobre `backend/` con sus reglas actuales, y `select` de Ruff sigue siendo explícito | La base de calidad de TKT-001: una regla nueva se añade a `select`, nunca con `extend-select` | `CA-R1` |
| `uv sync --locked` sigue funcionando | Instalación reproducible (`RNF-08`) | `CA-R2` |
| Los 14 contratos de `import-linter` siguen en verde y cada uno sigue fallando ante su violación | Fronteras de TKT-002, entre ellas `esqueleto-modulos` exhaustivo sobre diez módulos y el dominio sin framework | `CA-R3` |
| Las marcas «desde TKT-xxx» de otros tickets siguen intactas | Que `uv run fastapi dev` siga diciendo que todavía no funciona | `CA-R4` |
| `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` siguen en verde | Enlaces, anclas e identificadores | `CA-R5` |
| Los archivos nuevos no llevan BOM ni finales de línea fuera de LF | La comprobación de codificación de TKT-001 | `CA-R6` |
| Los 13 tests de `identidad` y las pruebas de permisos de TKT-003 siguen en verde | Que los tipos nuevos no alteren `conftest.py` ni la conexión con el rol de aplicación | `CA-R7` |

## Criterios de aceptación

Gherkin, en español. Como no hay reglas de negocio, el «rechazo» de cada criterio es la demostración de que la garantía **falla** ante su violación: un tipo que nunca se ha visto rechazar un `float` no está verificado. Los errores son excepciones corrientes de Python y no el contrato de error de la API, que llega con TKT-005.

### CA-1 `[M]` · Construcción exacta y sin flotantes · M1

```gherkin
Escenario: Se construye desde cadena, entero o Decimal sin perder dígitos
  Dado la cadena "12.10", el entero 12 y el Decimal("12.10")
  Cuando se construye un Dinero con cada uno
  Entonces los tres valores son exactos y el de "12.10" conserva exactamente 12.10

Escenario: Los tipos admiten signo y no validan rangos de negocio
  Dado la cadena "-250.0000"
  Cuando se construye un Dinero, una Cantidad y un Porcentaje con ella
  Entonces se construyen sin error, porque el signo lo valida cada caso de uso

Escenario: Rechazo — un float no se acepta, venga como argumento o dentro de Decimal
  Dado el literal float 0.1
  Cuando se intenta construir un Dinero con él, y también con Decimal(0.1)
  Entonces la construcción desde float falla con TypeError que nombra el tipo recibido
  Y no se construye ningún valor con el error binario arrastrado

Escenario: Rechazo — un booleano no es un número
  Dado el valor True
  Cuando se intenta construir un Dinero con él
  Entonces falla con TypeError, aunque bool sea subclase de int en Python

Escenario: Rechazo — cadenas que no son un decimal llano
  Dado las cadenas "NaN", "Infinity", "1e3", "1,234.50", " 12.10", "+12.10" y ""
  Cuando se intenta construir un Dinero con cada una
  Entonces cada intento falla con ValueError y el mensaje cita la cadena recibida
  Y ningún valor se construye con notación científica, coma de millares ni espacios

Escenario: Rechazo — un Decimal no finito
  Dado Decimal("NaN") y Decimal("Infinity")
  Cuando se intenta construir un Dinero con cada uno
  Entonces falla con ValueError
```

### CA-2 `[M]` · Valores inmutables y tipos que no se mezclan · M1

```gherkin
Escenario: Un valor construido no cambia
  Dado un Dinero("10.0000")
  Cuando se intenta asignar un atributo o añadir uno nuevo
  Entonces la asignación falla y el valor sigue siendo 10.0000

Escenario: Dos valores con el mismo número son iguales y tienen el mismo hash
  Dado Dinero("1.0") y Dinero("1.0000")
  Cuando se comparan y se usan como claves de un diccionario
  Entonces son iguales y comparten clave

Escenario: Rechazo — un valor no se convierte en float por la puerta de atrás
  Dado un Dinero("10.0000")
  Cuando se intenta float(dinero) o round(dinero, 2)
  Entonces ambos fallan con TypeError, porque los tipos no ofrecen conversión a float ni redondeo implícito

Escenario: Rechazo — Dinero y Cantidad no se mezclan
  Dado un Dinero("5.0000") y una Cantidad("5.0000")
  Cuando se suman, se restan o se comparan con < o >
  Entonces suma, resta y orden fallan con TypeError
  Y la igualdad entre ambos da falso, no verdadero
```

### CA-3 `[M]` · Aritmética con precisión completa · M2

```gherkin
Escenario: Cantidad por rendimiento conserva todos los decimales
  Dado Cantidad("3.1234") y Rendimiento("0.673400")
  Cuando se multiplica la cantidad por el rendimiento
  Entonces el resultado es una Cantidad exactamente igual a 2.10329756
  Y no se redondeó a las cuatro cifras de la escala de Cantidad

Escenario: Dinero por cantidad y dinero por porcentaje
  Dado Dinero("1000.0000"), Cantidad("2.5000") y Porcentaje("0.150000")
  Cuando se calcula Dinero × Cantidad y Dinero × Porcentaje
  Entonces el primero es Dinero 2500.0000 y el segundo es Dinero 150.0000

Escenario: Suma y resta de un mismo tipo, incluida una colección vacía
  Dado tres Dinero y una colección vacía de Dinero
  Cuando se suman los tres, se resta uno de otro y se suma la colección vacía
  Entonces las operaciones son exactas
  Y la suma de la colección vacía es el Dinero cero, no el entero 0 ni un error

Escenario: El redondeo no ocurre en pasos intermedios
  Dado Cantidad("7"), Rendimiento("0.142857") y Dinero("1000.5")
  Cuando se calcula Dinero × (Cantidad × Rendimiento) y después se cuantiza una vez
  Entonces el resultado es Dinero 1000.4990
  Y es distinto de 1000.5000, que saldría de cuantizar la Cantidad antes de multiplicar

Escenario: Los operandos más grandes no se redondean en silencio
  Dado la Cantidad más grande que cabe en NUMERIC(14,4) y el Rendimiento más grande que cabe en NUMERIC(18,6)
  Cuando se multiplican
  Entonces el producto tiene todos sus dígitos y es exacto
  Aunque supere los 28 dígitos significativos del contexto por omisión de decimal

Escenario: El contexto de decimal del proceso no altera el resultado
  Dado un proceso cuyo contexto de decimal tiene precisión 5 y la trampa de redondeo desactivada
  Cuando se repiten las multiplicaciones y sumas de los escenarios anteriores
  Entonces los resultados son idénticos a los de un proceso con el contexto por omisión

Escenario: Rechazo — combinaciones que no tienen sentido de dominio
  Dado una Cantidad, un Dinero y un Rendimiento
  Cuando se intenta Cantidad × Cantidad, Dinero × Dinero, Rendimiento + Dinero, Dinero × float y Dinero × 2 (entero)
  Entonces cada intento falla con TypeError y no devuelve un valor sin sentido
  Y multiplicar por un entero no está permitido: solo existen las operaciones listadas (ver PA-T15)
```

### CA-4 `[M]` · División que da un porcentaje, sin devolver cero ante un divisor nulo · M2 · regla 12

```gherkin
Escenario: Cantidad entre cantidad da un Porcentaje
  Dado Cantidad("30.0000") y Cantidad("120.0000")
  Cuando se divide la primera entre la segunda
  Entonces el resultado es un Porcentaje exactamente igual a 0.25

Escenario: Dinero entre dinero da un Porcentaje
  Dado Dinero("-50.0000") y Dinero("200.0000")
  Cuando se divide
  Entonces el resultado es un Porcentaje igual a -0.25

Escenario: Una división que no termina conserva al menos 28 dígitos significativos
  Dado Cantidad("1") y Cantidad("3")
  Cuando se divide la primera entre la segunda
  Entonces el Porcentaje conserva al menos 28 dígitos significativos
  Y no se redondea a la escala 9,6 del tipo, porque eso es cuantizar y es una operación aparte

Escenario: Rechazo — dividir entre cero no devuelve cero ni infinito
  Dado Cantidad("12.0000") y Cantidad("0.0000")
  Cuando se divide la primera entre la segunda
  Entonces falla con ZeroDivisionError
  Y no devuelve Porcentaje cero ni infinito: quien necesita «sin avance, NULL» decide antes de dividir
```

### CA-5 `[M]` · Redondeo explícito, separado y acotado a la columna · M3

```gherkin
Escenario: Cuantizar lleva cada tipo a la escala de su columna
  Dado Dinero("2.12345"), Cantidad("2.12345"), Rendimiento("2.1234565") y Porcentaje("0.1234565")
  Cuando se cuantiza cada uno
  Entonces resultan Dinero 2.1235, Cantidad 2.1235, Rendimiento 2.123457 y Porcentaje 0.123457
  Y el valor original no cambia: cuantizar devuelve un valor nuevo

Escenario: El empate se redondea alejándose del cero
  Dado Dinero("0.00005") y Dinero("-0.00005")
  Cuando se cuantiza cada uno
  Entonces resultan 0.0001 y -0.0001

Escenario: Cuantizar un valor que ya está en escala no lo cambia
  Dado Dinero("12.3400")
  Cuando se cuantiza
  Entonces es igual a Dinero("12.34")

Escenario: Rechazo — un valor que no cabe en la columna no se trunca
  Dado Dinero("100000000000000.0000", con 15 dígitos enteros) y Porcentaje("1000.000000", con 4 dígitos enteros)
  Cuando se cuantiza cada uno
  Entonces falla con ValueError que indica el tipo y la precisión (18,4) o (9,6)
  Y el valor máximo que sí cabe, 99999999999999.9999 para Dinero, se cuantiza sin error

Escenario: Rechazo — nada cuantiza por su cuenta
  Dado una cadena de operaciones de CA-3 sin llamar a cuantizar
  Cuando se inspecciona el resultado
  Entonces el valor conserva más decimales que la escala de su tipo
```

### CA-6 `[M]` · Serialización como cadena y lectura estricta · M4

```gherkin
Escenario: Cada tipo se serializa con la escala completa de su columna
  Dado Dinero("1234.5"), Cantidad("8"), Rendimiento("0.6734") y Porcentaje("0.05")
  Cuando se serializan para JSON
  Entonces resultan las cadenas "1234.5000", "8.0000", "0.673400" y "0.050000"
  Y el resultado es de tipo str y, codificado en JSON, va entre comillas

Escenario: Serializar no redondea y nunca usa notación científica
  Dado Dinero("0.0000") obtenido de cuantizar Dinero("0.00000001"), y Dinero("123456789012.3457") obtenido de cuantizar Dinero("123456789012.3456789")
  Cuando se serializan
  Entonces resultan "0.0000" y "123456789012.3457", sin exponente

Escenario: El cero negativo se serializa sin signo
  Dado Dinero("-0.0000") y el resultado de cuantizar Dinero("-0.00001")
  Cuando se serializan
  Entonces ambos resultan "0.0000" y no "-0.0000"

Escenario: Rechazo — un valor con más decimales que su escala no se serializa
  Dado Dinero("1234.56789"), que no ha pasado por cuantizar
  Cuando se intenta serializar
  Entonces falla con ValueError que indica la escala del tipo
  Y no emite una cadena redondeada en silencio: el redondeo de presentación es una llamada explícita a cuantizar

Escenario: La cadena serializada se lee de vuelta
  Dado cualquier valor cuantizado de los cuatro tipos
  Cuando se serializa y la cadena se vuelve a construir
  Entonces el valor recuperado es igual al original

Escenario: Rechazo — un valor que no cabe en la columna no se serializa
  Dado Dinero("100000000000000.0000")
  Cuando se intenta serializar
  Entonces falla con ValueError, igual que cuantizar, y no emite una cadena que PostgreSQL rechazaría
```

La decisión de que serializar no redondea sale de la pasada adversarial (objeción 1): un redondeo dentro de la serialización sería el redondeo implícito que `CA-5` prohíbe. Ver `PA-T7`.

### CA-7 `[M]` · `0.1 + 0.2` da exactamente `0.3` · M5

```gherkin
Escenario: La suma exacta
  Dado Dinero("0.1") y Dinero("0.2")
  Cuando se suman
  Entonces el resultado es igual a Dinero("0.3")
  Y lo mismo ocurre con Cantidad y con Porcentaje

Escenario: Rechazo — el oráculo detecta una implementación con flotantes
  Dado los literales float 0.1 y 0.2
  Cuando se suman
  Entonces el resultado no es igual a 0.3
  Y el test falla si los tipos se reimplementan sobre float
```

### CA-8 `[M]` · Los 27 insumos sintéticos reproducen el total esperado · M6

```gherkin
Escenario: La explosión sintética suma sin desviación
  Dado un fixture con 27 renglones de insumo, cada uno con cantidad de concepto, rendimiento y precio
  Y un total esperado fijado como literal, calculado de forma independiente del código que se prueba
  Cuando se calcula, renglón por renglón, Cantidad × Rendimiento × Dinero y se suman los 27 importes
  Entonces el total es exactamente igual al literal, sin cuantizar los renglones

Escenario: El orden no importa
  Dado los mismos 27 renglones en otro orden
  Cuando se suman
  Entonces el total es el mismo

Escenario: Rechazo — el mismo cálculo en flotante se desvía
  Dado los mismos 27 renglones convertidos a float
  Cuando se suman
  Entonces el total en flotante no coincide con el literal
  Y el fixture se eligió para que así sea, de modo que el test demuestra lo que previene
```

El fixture es sintético: no contiene precios ni cantidades de obras reales. La reconciliación con el total real del Excel, `2755187.2112`, es de TKT-016.

### CA-9 `[M]` · El linter bloquea el `float` en el dominio · M7

```gherkin
Escenario: Un dominio sin flotantes pasa
  Dado un archivo de dominio con firmas anotadas con Dinero, Cantidad, Rendimiento y Porcentaje
  Cuando se ejecuta la comprobación documentada
  Entonces termina con código 0

Escenario: Rechazo — float en un parámetro o en el retorno
  Dado un archivo bajo un dominio/ con "def disponible(presupuestado: float) -> float"
  Cuando se ejecuta la comprobación documentada
  Entonces termina con código distinto de 0
  Y el mensaje cita el archivo y la línea de cada anotación prohibida

Escenario: Rechazo — float escondido en una anotación compuesta o en una cadena
  Dado anotaciones "float | None", "Optional[float]", "list[float]", "dict[str, float]" y "'float'"
  Cuando se ejecuta la comprobación documentada
  Entonces cada una se marca, también con "from __future__ import annotations"

Escenario: Rechazo — float en un campo de dataclass
  Dado una clase con el campo anotado "tasa: float"
  Cuando se ejecuta la comprobación documentada
  Entonces se marca

Escenario: Rechazo — Decimal construido desde un literal float
  Dado "Decimal(0.1)" en un archivo de dominio
  Cuando se ejecuta la comprobación documentada
  Entonces se marca, y "Decimal('0.1')" no se marca

Escenario: La regla cubre el paquete de tipos base
  Dado un float en una firma del propio paquete de tipos base
  Cuando se ejecuta la comprobación documentada
  Entonces se marca

Escenario: El alcance es el dominio, no el sistema entero
  Dado un float en una firma de api/ o de infraestructura/
  Cuando se ejecuta la comprobación documentada
  Entonces no se marca, porque la decisión del usuario limita la regla a dominio/ y a los tipos base

Escenario: Rechazo — la regla no puede quitarse sin que un test falle
  Dado la regla desactivada o vaciada
  Cuando se ejecuta la suite
  Entonces el test que presenta una violación conocida falla
```

Los archivos con violaciones de estos escenarios los genera el test en un directorio temporal, fuera de las rutas que la comprobación revisa; si vivieran en el árbol, la propia comprobación fallaría siempre. Un alias como `Tasa = float` usado como anotación no se detecta: es un hueco conocido (`PA-T14`).

### CA-10 `[M]` · Fronteras: lista blanca para el dominio y pureza del paquete de tipos · M8

```gherkin
Escenario: El dominio puede importar la biblioteca estándar y los tipos base
  Dado un dominio/ que importa decimal y el paquete de tipos base
  Cuando se ejecuta uv run lint-imports
  Entonces el contrato de dominio se cumple
  Y esqueleto-modulos sigue siendo exhaustivo sobre los diez módulos, porque el paquete vive fuera de cimenta/

Escenario: Rechazo — un paquete de tercero cualquiera en el dominio
  Dado un dominio/ que importa requests, o numpy
  Cuando se ejecuta uv run lint-imports
  Entonces el contrato de dominio se rompe, aunque el paquete no sea fastapi, sqlalchemy ni pydantic

Escenario: Rechazo — los tres frameworks de antes siguen prohibidos, directa e indirectamente
  Dado un dominio/ que importa pydantic, y otro que importa un módulo que arrastra sqlalchemy
  Cuando se ejecuta uv run lint-imports
  Entonces ambos rompen el contrato de dominio

Escenario: Rechazo — el paquete de tipos base no importa framework ni módulos de negocio
  Dado el paquete de tipos base que importa pydantic o cimenta.presupuesto
  Cuando se ejecuta uv run lint-imports
  Entonces el contrato de pureza del paquete se rompe
```

### CA-11 `[M]` · El paquete de tipos base queda bajo mypy estricto · M8

```gherkin
Escenario: El paquete tipado pasa mypy con las opciones estrictas del dominio
  Dado el paquete de tipos base
  Cuando se ejecuta uv run mypy .
  Entonces termina con código 0

Escenario: Rechazo — una función sin tipos o un Any en el paquete rompe mypy
  Dado una función sin anotar en el paquete de tipos base
  Cuando se ejecuta uv run mypy .
  Entonces termina con código distinto de 0
```

### CA-12 `[M]` · La documentación dice lo que el código hace · M9

```gherkin
Escenario: Las marcas de este ticket se retiran y las de otros quedan
  Dado CLAUDE.md y docs/arranque-local.md
  Cuando se buscan las marcas "desde TKT-004"
  Entonces no aparece ninguna
  Y las de otros tickets siguen donde estaban

Escenario: La ubicación del paquete y el modo de redondeo están documentados
  Dado CLAUDE.md, arquitectura y conv-dominio-python
  Cuando se lee dónde viven los tipos compartidos y cómo se redondea
  Entonces los tres dicen lo mismo: paquete fuera de cimenta/, cuantizar con ROUND_HALF_UP, escala por tipo
  Y el ejemplo de conv-dominio-python §3 ya no exige una escala fija de dos decimales en el constructor

Escenario: Rechazo — la documentación no queda rota
  Dado los cambios documentales
  Cuando se ejecutan python tools/verificar_docs.py y python tools/extraer_mermaid.py
  Entonces ambos terminan con código 0
```

### CA-13 `[S]` · Los tests de los tipos no requieren Docker · S1

```gherkin
Escenario: La suite de los tipos corre sin PostgreSQL
  Dado una máquina sin Docker en marcha
  Cuando se ejecutan los tests de los tipos base y del linter
  Entonces pasan sin intentar levantar ningún contenedor

Escenario: Rechazo — los tests de los tipos no usan el rol de base de datos
  Dado el conftest.py actual
  Cuando se leen sus fixtures
  Entonces ninguna es autouse y ninguna fuerza la conexión
```

### Regresión

```gherkin
Escenario CA-R1 [M]: Ruff y mypy en verde con select explícito
  Cuando se ejecutan uv run ruff check ., uv run ruff format --check . y uv run mypy .
  Entonces los tres terminan con código 0
  Y el select de Ruff sigue siendo explícito, de modo que quitar la regla "I" lo rompe

Escenario CA-R2 [M]: Instalación reproducible
  Cuando se ejecuta uv sync --locked
  Entonces termina con código 0 y uv.lock no cambia

Escenario CA-R3 [M]: Los contratos de TKT-002 siguen vigentes
  Cuando se ejecuta uv run lint-imports
  Entonces los 14 contratos anteriores terminan en verde
  Y un módulo extra bajo cimenta/ rompe esqueleto-modulos, un dominio que importa fastapi rompe el de framework y un módulo que importa dominio de otro rompe solo-por-interfaz

Escenario CA-R4 [M]: Las marcas de otros tickets siguen intactas
  Cuando se leen CLAUDE.md y docs/arranque-local.md
  Entonces "uv run fastapi dev" sigue marcado "desde TKT-005 (asumido)" y "npm run dev" "desde TKT-008"

Escenario CA-R5 [M]: Los verificadores de documentación en verde
  Cuando se ejecutan python tools/verificar_docs.py y python tools/extraer_mermaid.py
  Entonces ambos terminan con código 0

Escenario CA-R6 [M]: Codificación de los archivos nuevos
  Cuando se ejecuta python tools/verificar_docs.py
  Entonces ningún archivo nuevo tiene BOM ni finales de línea distintos de LF

Escenario CA-R7 [M]: Identidad intacta
  Dado Docker en marcha
  Cuando se ejecuta uv run pytest
  Entonces los tests de identidad y de permisos de TKT-003 siguen en verde
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende solo de TKT-002, archivado. Lo bloquean TKT-016, TKT-020 y la mayoría de los tickets de módulo, pero no necesita a TKT-005: no importa Pydantic |
| **N** | Describe el qué, no impone el cómo | Sí | El nombre del paquete, el mecanismo del linter y la forma de expresar la lista blanca quedan para el diseño. Los nombres de las operaciones se fijan en el diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con matiz | Es un ticket de fundación sin rol del PRD, como TKT-003: el valor lo recibe quien desarrolla, que obtiene los tipos y un linter que le impide fallar |
| **E** | Estimable sin investigar antes | Sí | Talla S del plan. Dos incertidumbres técnicas, la lista blanca de `import-linter` y el mecanismo del linter, tienen salida de escape en `PA-T9` y `PA-T12` y no requieren un Spike |
| **S** | Cabe en una sesión sin romper contexto | Sí, con vigilancia | 13 criterios más 7 de regresión. Si el diseño supera unas 400 líneas o más de siete filas, se parte en dos entregas, tipos y linter por un lado y fronteras por otro |
| **T** | Sus criterios se pueden ejecutar | Sí | Todos terminan en un comando `uv run` o en un test sin Docker |

Un solo matiz, ningún fallo: la spec pasa.

## Definition of Done

La de un ticket de funcionalidad nueva sin criterios de aceptación de negocio, de `sdd/metodologia.md` §8.

- [ ] Los 12 criterios `[M]` de aceptación y los siete de regresión cumplidos, con un test cada escenario de rechazo
- [ ] Cada test lleva en su nombre el criterio que cubre, `test_tkt004_ca05_…`, porque el ticket no tiene escenario HDU
- [ ] Mutación sobre la aritmética, el redondeo y el linter: los mutantes que desactivan la cuantización, usan `float`, cambian `ROUND_HALF_UP` o vacían la regla quedan en rojo
- [ ] `uv run ruff format .`, `uv run ruff check .`, `uv run mypy .` y `uv run lint-imports` en verde
- [ ] Auditorías de arquitectura y de seguridad sin Críticos ni Altos; la de seguridad aplica si el diseño añade dependencias nuevas
- [ ] `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` en verde
- [ ] Marcas «desde TKT-004» retiradas de `CLAUDE.md` y de `docs/arranque-local.md`
- [ ] PR con etiqueta `agent`; el PR lo abre una persona

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T1 | El paquete de tipos base vive fuera de `cimenta/`, como Alembic. Su nombre lo fija el diseño | Un hijo nuevo de `cimenta/` cambia `esqueleto-modulos` y arquitectura §5 | Resuelto por el usuario, 2026-10-19 |
| PA-T2 | Los 27 insumos son un fixture sintético con total literal; el total real se reconcilia en TKT-016 | Si se necesitaran datos reales, hay que decidir cómo versionarlos sin exponer precios de obras (`README`) | Resuelto por el usuario, 2026-10-19 |
| PA-T3 | Cuatro tipos; `Dinero` cubre importe y precio unitario. La escala de columna se aplica en la frontera por cuantización explícita | Si TKT-014 o TKT-016 necesitan `PrecioUnitario` con escala `14,4` propia, se añade ahí | Resuelto por el usuario, 2026-10-19 |
| PA-T4 | La regla de `float` cubre `dominio/` y el paquete de tipos base, no todo `cimenta/` | Un `float` en `api/` o `infraestructura/` pasa hasta que otro ticket amplíe la regla | Resuelto por el usuario, 2026-10-19 |
| PA-T5 | El modo de redondeo es `ROUND_HALF_UP` `(asumido)`. Lo recoge el PRD como `PA-23` ([§10](../../../docs/01-descripcion-producto.md#preguntas-abiertas)) y [ADR-020](../../../docs/adr/20261019-tipos-numericos-base.md); ningún documento lo fija todavía | Si negocio prefiere `ROUND_HALF_EVEN`, cambian los escenarios de empate de `CA-5` y los importes de la explosión pueden diferir en el último decimal | Abierta. Supuesto de trabajo validado en el intake; ratificar con negocio antes de TKT-016 |
| PA-T6 | La división conserva al menos 28 dígitos significativos `(asumido)`, el contexto por omisión de `decimal` | Con menos, una razón como 1/3 pierde dígitos antes de cuantizarse | Abierta. Se confirma al diseñar |
| PA-T7 | Serializar emite la escala completa del tipo (API §2.3) y **rechaza** un valor con más decimales, en vez de redondearlo `(asumido)`; el redondeo de presentación es una llamada explícita a `cuantizar` | Si se prefiere que serializar cuantice por su cuenta, `CA-6` y `CA-5` se contradicen y hay que elegir dónde vive el redondeo | Abierta. Decidida en la pasada adversarial; confirmar al diseñar |
| PA-T8 | Los errores son `TypeError`, `ValueError` y `ZeroDivisionError` de Python y no un contrato de error `(asumido)`. Cómo los traduce un caso de uso se decide en TKT-005 y TKT-020 | Si el API debiera responder `422` ante una cadena mal formada, el límite lo pone la validación de Pydantic en TKT-005, no estos tipos | Abierta |
| PA-T9 | El mecanismo de la regla de linter lo elige el diseño `(asumido)`: Ruff no trae ninguna regla que prohíba `float` en anotaciones, y el toolkit prevé una regla propia o un hook (`veto-float-dominio`, hoy pendiente) | Si ninguna opción puede formar parte de `uv run ruff check`, el comando se documenta aparte y se añade al pipeline en TKT-009 | Abierta. Se resuelve al diseñar |
| PA-T10 | Dónde cae el centavo en un reparto no se decide aquí: no hay reparto en este ticket | `RN-23` y la nómina de fase 2 necesitan esa decisión antes de implementarse | Abierta. Ticket futuro |
| PA-T11 | «Tolerancia decimal» de TKT-014 y «cero desviación» de TKT-004 conviven: este ticket solo ofrece comparación exacta | TKT-014 puede necesitar una comparación con tolerancia explícita, que se añadiría ahí | Abierta |
| PA-T12 | `import-linter` puede expresar una lista blanca de importaciones externas para `dominio/` `(asumido)`. El contrato actual es una lista negra de tres paquetes, y no consta que sepa distinguir la biblioteca estándar | Si no puede, el diseño propone otra mecánica o escala; cerrar `O1` con otra lista negra más larga no la cierra | Abierta. Se resuelve al diseñar |
| PA-T13 | `uv run pytest` ya funciona desde TKT-003 y los tests de los tipos no necesitan Docker | Si algún fixture global exigiera Docker, `CA-13` falla | Abierta. Se confirma al diseñar |
| PA-T14 | La regla de linter no detecta un alias de `float` (`Tasa = float`) ni `numbers.Real` `(asumido)` | Un `float` entra por el alias sin que nadie lo marque | Abierta. Ticket futuro sugerido |
| PA-T15 | Multiplicar un tipo por un entero, o sumar un entero, no está permitido `(asumido)`: solo existen las operaciones listadas | Si un ticket necesita «el doble» o `Dinero × 2`, añade esa operación con su escenario | Abierta |
| PA-T16 | `sumar` una colección vacía devuelve el cero del tipo `(asumido)`; el nombre y la forma de la función los fija el diseño | Si devolviera error, la suma de una requisición sin renglones tendría que tratarse aparte | Abierta. Se confirma al diseñar |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-6` redondeaba al serializar, y `CA-5` prohíbe que nada redondee por su cuenta: una serialización que cuantiza es exactamente el redondeo oculto que el ticket combate. Además `-0.00001` podía dar `-0.0000` | Aceptada. Serializar ya no redondea: rechaza un valor con más decimales que su escala y exige `cuantizar` antes. El cero negativo se normaliza. `CA-6` reescrito, `PA-T7` actualizado |
| 2 | Media | Un valor podía salir a `float` por `float(x)` o `round(x, 2)`, y la prohibición del linter no lo ve | Aceptada. Escenario de rechazo nuevo en `CA-2`: ambas llamadas fallan con `TypeError` |
| 3 | Media | El linter no detecta alias de `float`, y sus propios tests no pueden dejar archivos con violaciones en el árbol que revisan | Parcial. Nota en `CA-9` sobre dónde viven las violaciones de prueba y hueco declarado en `PA-T14` con ticket futuro; ampliar la detección crece el alcance |
| 4 | Media | Las operaciones no listadas, como `Dinero × 2`, quedaban sin definir: un diseñador podría admitirlas o no | Aceptada. `CA-3` las rechaza expresamente y `PA-T15` lo deja como supuesto |
| 5 | Media | La suma de una colección vacía no estaba cubierta por ningún supuesto, aunque `CA-3` exige un cero del tipo | Aceptada. `PA-T16`. Sin objeción sobre la existencia de una regla de negocio nueva: ninguna objeción exigió escalar |

Falsabilidad: la recomendación de dejar la lista blanca de `import-linter` para el diseño sería incorrecta si la herramienta no distinguiera la biblioteca estándar. Está recogido en `PA-T12`, con la salida de escalar.

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

**Precisiones** ([modelo de datos §2](../../../docs/03-modelo-datos.md#2-convenciones)): importes `NUMERIC(18,4)` (14 dígitos enteros), precios y cantidades `NUMERIC(14,4)` (10 enteros), rendimientos `NUMERIC(18,6)` (12 enteros) y porcentajes `NUMERIC(9,6)` (3 enteros), donde `0.050000` es 5 %. El [borrador OpenAPI](../../../docs/api/openapi.yaml) distingue además `Importe` y `PrecioUnitario`; por decisión del usuario este ticket usa `Dinero` para ambos.

**Estado del backend:** los diez módulos con sus cuatro capas vacías; fuera de `cimenta/`, `migraciones/`, `herramientas/` y `tests/`. `backend/pyproject.toml` tiene Ruff con `select = ["E","W","F","I","B","UP","SIM"]`, `mypy` estricto solo sobre `cimenta.*.dominio.*`, 14 contratos de `import-linter` con `include_external_packages = true` y `pytest` con `--import-mode=importlib`. Pydantic y FastAPI no están instalados.

**Contratos que este ticket toca:** `dominio-sin-framework` (lista negra de tres paquetes, `allow_indirect_imports = false`) y el override de `mypy`, que no cubre el paquete nuevo. `esqueleto-modulos`, `esqueleto-capas`, `solo-por-interfaz` y los diez `grafo-*` no se tocan.

**Quién consume estos tipos después:** TKT-016 (explosión, `Cantidad × Rendimiento`, `Cantidad × Dinero`, sin redondeo intermedio), TKT-020 (`RN-03`: resta y comparación de `Dinero`), TKT-034 (`RN-06` y `RN-07`: resta y comparación de `Cantidad`), TKT-039 (`÷` que da `Porcentaje` y puede ser `NULL`) y TKT-012 (`Porcentaje × Dinero`: retenciones). TKT-005 es paralelo y comparte `pyproject.toml` y `uv.lock`: el segundo que llegue rebasa y regenera el bloqueo con `uv lock`.

**Archivos que se esperan tocar:** `backend/pyproject.toml`, `backend/uv.lock`, el paquete nuevo de tipos base con sus tests, el verificador del linter, `CLAUDE.md`, `docs/arranque-local.md`, `docs/02-arquitectura.md`, `.claude/skills/conv-dominio-python/SKILL.md`.

**Deuda de TKT-002 que este ticket cierra:** `O1` (`impl.md` de TKT-002, `delta.md` de TKT-002), ubicación de los tipos compartidos.
