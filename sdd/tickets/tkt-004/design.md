# Design · TKT-004 · Tipos base del dominio con decimal exacto

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md`, que crea `/sdd-ejecutar`

## Estrategia

Los cuatro objetos de valor viven en un paquete nuevo, `backend/tipos_base/`, al lado de `cimenta/` y no dentro, para que `esqueleto-modulos` siga siendo exhaustivo sobre los diez módulos. Son *dataclasses* congeladas sobre `Decimal` que calculan con **contextos de `decimal` propios**, nunca con el del proceso: suma, resta y producto con precisión ilimitada y trampas de redondeo encendidas, división a 28 dígitos, y redondeo solo cuando se llama a `cuantizar()`, que además comprueba que el valor cabe en su columna. `serializar()` produce la cadena de escala completa y **no redondea**: rechaza lo que no se ha cuantizado. La prohibición de `float` se reparte entre lo que la plataforma ya trae y lo mínimo propio: la regla `RUF032` de Ruff marca `Decimal(0.1)`, y un verificador AST de unas ochenta líneas, `herramientas/verificar_float.py`, marca `float` en las anotaciones de `dominio/` y de `tipos_base/`, porque Ruff no tiene ninguna regla para eso. La lista blanca del dominio se expresa con el mecanismo de extensión documentado de `import-linter`, un **tipo de contrato propio** (`lista_blanca`), porque ningún contrato nativo distingue la biblioteca estándar de un paquete de tercero.

## Fuentes y verificación de las herramientas

**El arquitecto no tiene terminal en esta sesión.** La orden pedía experimentos con `uv run` en un directorio del *scratchpad*; no fue posible ejecutarlos. Lo que sigue se apoya en la lectura del código fuente instalado en `backend/.venv` —las mismas versiones que fija `uv.lock`— y en Context7. Cada afirmación que solo se demuestra ejecutando lleva su comando de comprobación en la fila indicada y, si falla, la regla que aplica el ejecutor sin decidir nada.

| Fuente | Hecho | Consecuencia para el diseño |
|---|---|---|
| `importlinter/contracts/forbidden.py` (2.15) | `forbidden_modules` solo admite paquetes externos de nivel raíz y no tiene exclusiones; un comodín se resuelve contra los módulos del grafo | Una lista blanca no se puede escribir con `forbidden` |
| `grimp-3.17.dist-info/METADATA`, sección «External packages» | Con `include_external_packages=True`, el ejemplo de la propia documentación lista `os` y `decimal` junto a `sqlalchemy` entre los importados: **la biblioteca estándar entra en el grafo como paquete externo**, indistinguible de un tercero | `forbidden_modules = ["*"]` prohibiría también `decimal`. Ningún comodín de grimp admite negación (`grimp/application/graph.py`, `find_matching_modules`) |
| `importlinter/contracts/protected.py`, `independence.py`, `layers.py` | Ninguno tiene noción de «biblioteca estándar» ni lista de permitidos externos | Se descartan |
| Context7, `/seddonym/import-linter`, «Custom contract types» | Un contrato propio se define heredando de `importlinter.Contract` con `check(graph, verbose) -> ContractCheck` y `render_broken_contract(check)`, y se registra con `contract_types` en la configuración | Peldaño 2: el propio `import-linter` ofrece la extensión |
| `importlinter/application/use_cases.py` | `contract_types` se lee de `session_options` y cada entrada `"nombre: ruta.Clase"` se importa con `importlib.import_module`; la lectura TOML (`adapters/user_options.py`) acepta listas | `contract_types = ["lista_blanca: herramientas.contrato_lista_blanca.ContratoListaBlanca"]` en `[tool.importlinter]` |
| `importlinter/domain/fields.py` | Existen `ListField`, `ModuleExpressionField`, `ModuleField` y `TextField`; un campo con `required=False` y sin valor queda en `None` | Campos del contrato propio |
| `grimp/application/graph.py` | `find_upstream_modules(module, as_package=True)` devuelve todo lo que el paquete importa directa o indirectamente, sin incluir sus propios descendientes; `find_shortest_chain(importer, imported, as_packages=True)` da la cadena para el mensaje | El contrato propio comprueba también los indirectos, como exige `CA-10` esc. 3 |
| `importlinter/application/use_cases.py`, `_validate_root_package_names` | Cada raíz de `root_packages` debe ser un paquete con `__init__.py`, no un módulo suelto | `tipos_base` es un paquete, no un `tipos_base.py` |
| Context7, `/websites/astral_sh_ruff`, `decimal-from-float-literal` | `RUF032` marca `Decimal(<literal float>)`; su arreglo es inseguro, así que `ruff check --fix` no lo aplica sin `--unsafe-fixes` | Peldaño 2 para `Decimal(0.1)` |
| Context7, `banned-api` (`TID251`) | Prohíbe importar o acceder a miembros de módulos; nada en su documentación dice que sepa limitarse a anotaciones | No sirve para `float` en firmas: marcaría también `float(x)` e `isinstance(x, float)` en todo el árbol |
| `backend/pyproject.toml` y delta de TKT-002 | No hay `[build-system]`: el proyecto no se instala. `cimenta` se importa porque pytest añade `.` (`pythonpath`), `lint-imports` añade el directorio actual y mypy se ejecuta desde `backend/` | `tipos_base/` se ve igual que `cimenta/` sin tocar el empaquetado. Ruff lo trata como *first-party* porque su `src` por omisión incluye el directorio del `pyproject.toml` |
| `backend/tests/conftest.py` | Ninguna *fixture* es `autouse`; el contenedor solo arranca si una prueba pide `contenedor_postgres` o algo que dependa de ella; `pytest_sessionstart` solo lee variables de entorno | `PA-T13` se confirma: los tests de este ticket no necesitan Docker |

**Sin verificar, y lo comprueba la fila indicada.** (a) Que `RUF032` sea estable, no *preview*, en Ruff 0.17.1 (fila 4: `uv run ruff rule RUF032`; si dice *preview*, se aplica la alternativa escrita en esa fila). (b) Que `"__future__"` y `"decimal"` estén en `sys.stdlib_module_names` del intérprete del entorno (fila 5). (c) Que `decimal.Context(prec=decimal.MAX_PREC, Emax=decimal.MAX_EMAX, Emin=decimal.MIN_EMIN)` se construya en el intérprete del entorno y multiplique sin `MemoryError` (fila 2: lo prueba TC-26). (d) Que `lint-imports` importe `herramientas.contrato_lista_blanca` desde el directorio actual (fila 5, TC-98). Si grimp resultara **no** incluir la biblioteca estándar en el grafo, el contrato propio sigue funcionando igual: solo vería menos nodos.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Paquete `backend/tipos_base/` (`__init__.py` y `numericos.py`) | 5 · objeto nuevo | `M1` y decisión del usuario (`PA-T1`): fuera de `cimenta/`, como Alembic. Nombre en español del vocabulario de la spec. Un paquete y no un módulo suelto, porque `root_packages` lo exige. `__init__.py` solo reexporta con `__all__`, porque `implicit_reexport = false` lo pide |
| Cuatro clases `Dinero`, `Cantidad`, `Rendimiento`, `Porcentaje` sobre una base privada `_Numero` | 5 · objeto nuevo, con la lógica común una sola vez | Construcción, suma, resta, `cuantizar` y `serializar` son idénticos salvo la precisión: van en la base, y cada subclase solo declara `_PRECISION`, `_ESCALA` y sus productos. Repetirlo cuatro veces sería cuatro sitios donde el redondeo puede divergir |
| `@dataclass(frozen=True, slots=True, init=False, order=True)` | 2 · nativo | La biblioteca estándar da inmutabilidad, `__eq__` que devuelve `NotImplemented` entre clases distintas, `__hash__` coherente, orden solo dentro de la misma clase y copia y *pickle* correctos con *slots*. `init=False` porque el constructor convierte `str` e `int` |
| `__float__`, `__round__`, `__int__`, `__radd__`, `__rmul__`, `__neg__`, `__abs__` | 1 · YAGNI, fuera | No definirlos **es** el rechazo: `float(x)` y `round(x, 2)` lanzan `TypeError` solos (`CA-2` esc. 3), `sum()` y `2 * x` también. Ningún Must pide negar ni valor absoluto |
| Tres contextos de módulo `_EXACTO`, `_REDONDEO`, `_DIVISION` | 2 · nativo | `decimal.Context` con precisión y trampas propias; los métodos `Context.add`, `multiply`, `subtract`, `divide` y `quantize(..., context=)` no leen el contexto del proceso (`CA-3` esc. 6) |
| `_EXACTO`: `prec=MAX_PREC`, `Emax=MAX_EMAX`, `Emin=MIN_EMIN`, trampas `InvalidOperation`, `DivisionByZero`, `Overflow`, `Inexact`, `Rounded` | 2 · nativo | La documentación de `decimal` describe esta configuración como aritmética exacta para sumas y productos. Con 28 dígitos, `Cantidad` máxima × `Rendimiento` máximo (32 dígitos) se redondearía en silencio (`CA-3` esc. 5); con una precisión fija mayor, un producto encadenado o la suma de miles de renglones con escalas distintas acabaría tocando el techo. Las trampas `Inexact` y `Rounded` son la red: si algún día una suma o un producto redondeara, falla en lugar de mentir |
| `_REDONDEO`: igual sin `Inexact` ni `Rounded` atrapados | 2 · nativo | `quantize` redondea por definición; con `Rounded` atrapado, `cuantizar` fallaría siempre |
| `_DIVISION`: `prec=28`, `ROUND_HALF_UP`, trampas `InvalidOperation`, `DivisionByZero`, `Overflow` | 2 · nativo | `PA-T6`. Una división inexacta con `MAX_PREC` agota la memoria. 28 dígitos son los del contexto por omisión, los que pide la spec, y sobran: el error relativo de 10⁻²⁸ sobre un importe de 14 enteros es 10⁻¹⁴, diez órdenes por debajo del diezmilésimo |
| Cero como divisor comprobado antes de dividir | 4 · cambio mínimo | `Decimal(0)/Decimal(0)` levanta `InvalidOperation`, no `ZeroDivisionError`; una línea explícita da el mismo error en los dos casos (`CA-4` esc. 4, regla 12) |
| Cadena con `re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?")` | 5 · objeto mínimo | `CA-1` esc. 5. `[0-9]` y no `\d`, porque `\d` admite dígitos de otros alfabetos que `Decimal` sí convierte. `fullmatch` y no `match` con `$`, que admite un salto de línea final |
| Rechazo de un `Decimal` construido desde `float` («huella de float») | 5 · objeto mínimo, **a confirmar en el gate (D-1)** | `CA-1` esc. 3 pide `TypeError` también para `Dinero(Decimal(0.1))`. En tiempo de ejecución ese valor es un `Decimal` como cualquiera; su huella es tener **más de 18 dígitos significativos** (más que cualquier columna del modelo) **y** ser exactamente un `double`. Un `Decimal(float)` con 18 dígitos o menos es exacto y no arrastra error. Cuatro líneas |
| `cuantizar()` con `ROUND_HALF_UP` y comprobación de dígitos enteros | 5 · objeto nuevo | `M3`. Modo `(asumido)`, `PA-T5`. El rango se comprueba **después** de redondear, porque `99999999999999.99995` sube a quince enteros |
| `serializar()` que rechaza un valor sin cuantizar y normaliza el cero negativo | 5 · objeto nuevo | `M4`, `PA-T7`. El criterio es de valor, no de exponente: `Dinero("1.50000")` cabe en cuatro decimales y serializa `"1.5000"`. Formato `"f"`, nunca notación científica |
| Lectura desde cadena | 3 · reuso | Es el constructor: `Dinero(d.serializar()) == d`. No hay un segundo analizador |
| `sumar(valores, tipo)` | 5 · objeto mínimo | `PA-T16`: la colección vacía da el cero **del tipo**, que `sum()` no puede dar sin un valor inicial. Rechaza un elemento de otro tipo |
| Productos conmutativos: `Cantidad × Rendimiento`, `Dinero × Cantidad`, `Dinero × Porcentaje`, en los dos órdenes | 4 · cambio mínimo, **a confirmar en el gate (D-6)** | `CA-8` multiplica `Cantidad × Rendimiento × Dinero`, que es `Cantidad × Dinero`; el contexto técnico de la spec cita `Porcentaje × Dinero` para TKT-012. Admitir los dos órdenes de los tres pares listados no añade ninguna combinación nueva |
| `Rendimiento ÷ Rendimiento`, `Porcentaje ÷ Porcentaje`, `Dinero ÷ Cantidad` | 1 · YAGNI, fuera | Non-goal de la spec (`PA-T11`, `PA-T15`) |
| Validación de rango en el constructor | 1 · fuera | `CA-5` y `CA-6` parten de un `Dinero` de quince enteros ya construido. El rango se comprueba en la frontera, `cuantizar` y `serializar`; el non-goal «solo aceptan lo que cabe» se lee así (objeción 4 de la pasada adversarial) |
| `RUF032` en `select` de Ruff | 2 · nativo | `Decimal(0.1)` lo marca Ruff, en todo `backend/`, sin código propio. Se añade a `select`, nunca con `extend-select` (`CA-R1`) |
| `herramientas/verificar_float.py` | 5 · objeto nuevo | Ruff no tiene ninguna regla de anotaciones `float`; `TID251` no se limita a anotaciones. Un verificador AST de la biblioteca estándar, sin dependencias. En `herramientas/` porque es una herramienta de operación fuera de `cimenta/`, como el script de contraseñas |
| Plugin de mypy, hook de Claude (`veto-float-dominio`) | 1 · fuera | Un plugin de mypy es más código y más acoplado a la versión; un hook de agente no corre en CI ni para una persona |
| Tipo de contrato `lista_blanca` en `herramientas/contrato_lista_blanca.py` | 2 · nativo (extensión documentada de `import-linter`) + 5 · objeto mínimo | `PA-T12`: ningún contrato nativo lo expresa (ver fuentes). Con el contrato propio, `lint-imports` sigue siendo el único comando de fronteras y el grafo es el mismo |
| `dominio-sin-framework` cambia de tipo y conserva su `id` | 4 · cambio mínimo | `M8` y `O1`: pasa de lista negra a lista blanca. Conservar el `id` mantiene el rastro de TKT-002 y de `CA-R3` |
| Contrato nuevo `tipos-base-puro` | 3 · reuso del mismo tipo | `M8`: `tipos_base` solo alcanza la biblioteca estándar |
| `root_package` pasa a `root_packages = ["cimenta", "tipos_base"]` | 4 · cambio mínimo | Sin eso, `tipos_base` sería un externo aplastado y su contenido no se analizaría |
| `tipos_base.*` en el *override* estricto de mypy | 4 · cambio mínimo | `CA-11`. Se añade al mismo `module = [...]` que ya existe |
| Dependencias nuevas | 1 · ninguna | Ni `uv.lock` ni `pyproject.toml` ganan dependencias: `import-linter`, `grimp` y Ruff ya están. `auditor-seguridad` no tiene dependencias que revisar |
| Glosario | 1 · sin cambio | `Dinero`, `Cantidad` y `Porcentaje` son tipos de código sin un significado de negocio distinto del habitual; su sitio es arquitectura §7.4. *Rendimiento* ya tiene entrada |

Ningún objeto que paró en el peldaño 4 toca un invariante del modelo de datos ni una de las 17 reglas de `CLAUDE.md`. El cambio de `dominio-sin-framework` **endurece** la regla 2; no la relaja.

## Capas afectadas

El ticket no escribe aplicación, API, infraestructura ni frontend, y no crea ni modifica ningún archivo bajo `backend/cimenta/`.

### Dominio · `backend/tipos_base/`

| Archivo | Qué | Regla |
|---|---|---|
| `tipos_base/__init__.py` | Docstring, `from tipos_base.numericos import Cantidad, Dinero, Porcentaje, Rendimiento, sumar` y `__all__ = ["Cantidad", "Dinero", "Porcentaje", "Rendimiento", "sumar"]` | Regla 1 y 2 de `CLAUDE.md` |
| `tipos_base/numericos.py` | Contextos, `_a_decimal`, `_viene_de_float`, `_Numero`, las cuatro clases, `_producto`, `_cociente`, `sumar` | Regla 1, arquitectura §7.4, regla 12 |

**Contenido de `tipos_base/numericos.py`.** El ejecutor copia esta forma; los docstrings pueden ampliarse, la lógica no.

```python
"""Tipos numéricos base de CIMENTA (TKT-004): Dinero, Cantidad, Rendimiento y Porcentaje.

Aritmética exacta sobre Decimal con contextos propios: el contexto de decimal del
proceso no altera ningún resultado. Redondear es llamar a cuantizar(), y serializar()
nunca redondea. Regla 1 de CLAUDE.md y arquitectura §7.4.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MAX_PREC,
    MIN_EMIN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
)
from typing import ClassVar, Self, overload

# Suma, resta y producto exactos. Inexact y Rounded atrapados: si algo redondeara, falla.
_EXACTO = Context(
    prec=MAX_PREC, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN,
    traps=[InvalidOperation, DivisionByZero, Overflow, Inexact, Rounded],
)
# quantize redondea por definición: aquí Inexact y Rounded no se atrapan.
_REDONDEO = Context(
    prec=MAX_PREC, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN,
    traps=[InvalidOperation, Overflow],
)
# Una división inexacta con MAX_PREC agota la memoria: 28 dígitos significativos (PA-T6).
_DIVISION = Context(
    prec=28, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
_DECIMAL_LLANO = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_DIGITOS_MAXIMOS_DE_COLUMNA = 18


def _viene_de_float(valor: Decimal) -> bool:
    """Huella de Decimal(float): más dígitos que cualquier columna y exactamente un double."""
    return (
        len(valor.as_tuple().digits) > _DIGITOS_MAXIMOS_DE_COLUMNA
        and Decimal.from_float(float(valor)) == valor
    )


def _a_decimal(valor: object, tipo: str) -> Decimal:
    if isinstance(valor, bool):
        raise TypeError(f"{tipo} no se construye desde bool: {valor!r}")
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            raise ValueError(f"{tipo} solo admite valores finitos, y recibió {valor!r}")
        if _viene_de_float(valor):
            raise TypeError(
                f"{tipo} no admite un Decimal construido desde float ({valor!r}): "
                "constrúyalo desde una cadena"
            )
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, str):
        if _DECIMAL_LLANO.fullmatch(valor) is None:
            raise ValueError(
                f"{tipo} no admite la cadena {valor!r}: se espera un decimal llano, como '1234.5600'"
            )
        return Decimal(valor)
    raise TypeError(f"{tipo} se construye desde str, int o Decimal, no desde {type(valor).__name__}")
```

La base y las cuatro clases. **Cada subclase lleva el mismo decorador**: sin él, la subclase tendría `__dict__` y generaría su igualdad con otras reglas.

```python
@dataclass(frozen=True, slots=True, init=False, order=True)
class _Numero:
    valor: Decimal
    _PRECISION: ClassVar[int]
    _ESCALA: ClassVar[int]

    def __init__(self, valor: str | int | Decimal) -> None:
        object.__setattr__(self, "valor", _a_decimal(valor, type(self).__name__))

    @classmethod
    def _nuevo(cls, valor: Decimal) -> Self:
        """Resultado de una operación: ya es un Decimal exacto y no pasa por las comprobaciones de entrada."""
        nuevo = object.__new__(cls)
        object.__setattr__(nuevo, "valor", valor)
        return nuevo

    def __add__(self, otro: Self) -> Self:
        if type(otro) is not type(self):
            return NotImplemented
        return self._nuevo(_EXACTO.add(self.valor, otro.valor))

    def __sub__(self, otro: Self) -> Self:
        if type(otro) is not type(self):
            return NotImplemented
        return self._nuevo(_EXACTO.subtract(self.valor, otro.valor))

    def cuantizar(self) -> Self:
        """Lleva el valor a la escala de su columna con ROUND_HALF_UP (asumido, PA-T5)."""
        return self._nuevo(self._en_columna(self._a_escala()))

    def serializar(self) -> str:
        """Cadena de escala completa para JSON. No redondea: rechaza un valor sin cuantizar."""
        en_escala = self._a_escala()
        if en_escala != self.valor:
            raise ValueError(
                f"{type(self).__name__} {self.valor} tiene más de {self._ESCALA} decimales: "
                "llame a cuantizar() antes de serializar"
            )
        en_columna = self._en_columna(en_escala)
        return format(en_columna.copy_abs() if en_columna.is_zero() else en_columna, "f")

    def _a_escala(self) -> Decimal:
        unidad = Decimal(f"1E-{self._ESCALA}")
        return self.valor.quantize(unidad, rounding=ROUND_HALF_UP, context=_REDONDEO)

    def _en_columna(self, valor: Decimal) -> Decimal:
        enteros = self._PRECISION - self._ESCALA
        if valor.copy_abs() >= Decimal(10**enteros):
            raise ValueError(
                f"{type(self).__name__} {valor} no cabe en NUMERIC({self._PRECISION},{self._ESCALA}): "
                f"admite hasta {enteros} dígitos enteros"
            )
        return valor
```

| Clase | `_PRECISION`, `_ESCALA` | Productos (`__mul__`) | División (`__truediv__`) |
|---|---|---|---|
| `Dinero` — importe y precio unitario | `18`, `4` | `def __mul__(self, otro: Cantidad \| Porcentaje) -> Dinero` | `def __truediv__(self, otro: Dinero) -> Porcentaje` |
| `Cantidad` | `14`, `4` | `@overload (otro: Rendimiento) -> Cantidad` y `@overload (otro: Dinero) -> Dinero` | `def __truediv__(self, otro: Cantidad) -> Porcentaje` |
| `Rendimiento` | `18`, `6` | `def __mul__(self, otro: Cantidad) -> Cantidad` | — |
| `Porcentaje` — `0.050000` es 5 % | `9`, `6` | `def __mul__(self, otro: Dinero) -> Dinero` | — |

Cada `__mul__` comprueba el tipo del otro operando con `isinstance(otro, <Tipo> | <Tipo>)`, devuelve `NotImplemented` si no es uno de los admitidos y, si lo es, `<TipoResultado>._nuevo(_producto(self, otro))`. Cada `__truediv__` comprueba `type(otro) is <MismoTipo>`, devuelve `NotImplemented` si no y, si sí, `_cociente(self, otro)`. Funciones de módulo:

```python
def _producto(a: _Numero, b: _Numero) -> Decimal:
    return _EXACTO.multiply(a.valor, b.valor)


def _cociente(a: _Numero, b: _Numero) -> Porcentaje:
    if b.valor.is_zero():
        raise ZeroDivisionError(
            f"{type(a).__name__} entre {type(b).__name__} cero: quien necesita «sin dato» "
            "decide antes de dividir (regla 12 de CLAUDE.md)"
        )
    return Porcentaje._nuevo(_DIVISION.divide(a.valor, b.valor))


def sumar[T: _Numero](valores: Iterable[T], tipo: type[T]) -> T:
    """Suma exacta de una colección de un solo tipo; la vacía da el cero del tipo (PA-T16)."""
    total = Decimal(0)
    for valor in valores:
        if type(valor) is not tipo:
            raise TypeError(f"sumar espera {tipo.__name__} y recibió {type(valor).__name__}")
        total = _EXACTO.add(total, valor.valor)
    return tipo._nuevo(total)
```

**Tabla de operaciones resultante.** Cualquier otra combinación —entre tipos distintos, con `int`, con `float`, `//`, `%`, `**`, negación, `abs`, `float()`, `int()`, `round()`, formato con precisión— termina en `TypeError` porque el método no existe o devuelve `NotImplemented`.

| | `Dinero` | `Cantidad` | `Rendimiento` | `Porcentaje` |
|---|---|---|---|---|
| **`Dinero`** | `+ − → Dinero`, `÷ → Porcentaje`, `< ≤ > ≥ ==` | `× → Dinero` | — | `× → Dinero` |
| **`Cantidad`** | `× → Dinero` | `+ − → Cantidad`, `÷ → Porcentaje`, orden | `× → Cantidad` | — |
| **`Rendimiento`** | — | `× → Cantidad` | `+ − → Rendimiento`, orden | — |
| **`Porcentaje`** | `× → Dinero` | — | — | `+ − → Porcentaje`, orden |

`==` entre tipos distintos da `False` (la *dataclass* devuelve `NotImplemented` y Python cae en la identidad). Con `otro: Self` en `__add__` y `__sub__`, mypy rechaza además `dinero + cantidad` antes de ejecutar.

### Herramientas · `backend/herramientas/`

| Archivo | Qué |
|---|---|
| `herramientas/verificar_float.py` | Verificador AST de anotaciones `float`. Comando: `uv run python -m herramientas.verificar_float [--raiz DIR]`, desde `backend/` |
| `herramientas/contrato_lista_blanca.py` | Tipo de contrato `lista_blanca` de `import-linter` |

**`herramientas/verificar_float.py`**, completo salvo el texto de los docstrings:

```python
"""Regla 1 de CLAUDE.md (TKT-004): ningún float en una anotación de cimenta/*/dominio/ ni de tipos_base/.

Uso, desde backend/:  uv run python -m herramientas.verificar_float [--raiz DIR]
Termina con 0 sin hallazgos, 1 con hallazgos y 2 si no encontró ningún archivo que revisar.
Decimal(0.1) lo marca Ruff con RUF032. Hueco conocido (PA-T14): un alias como
`Tasa = float` usado como anotación no se detecta.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

PATRONES = ("cimenta/*/dominio/**/*.py", "tipos_base/**/*.py")


@dataclass(frozen=True)
class Hallazgo:
    ruta: Path
    linea: int
    donde: str


def archivos_a_revisar(raiz: Path) -> list[Path]:
    return sorted({ruta for patron in PATRONES for ruta in raiz.glob(patron)})


def _menciona_float(anotacion: ast.expr) -> bool:
    for nodo in ast.walk(anotacion):
        if isinstance(nodo, ast.Name) and nodo.id == "float":
            return True
        if (
            isinstance(nodo, ast.Attribute)
            and nodo.attr == "float"
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "builtins"
        ):
            return True
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            try:
                interior = ast.parse(nodo.value, mode="eval").body
            except SyntaxError:
                continue
            if _menciona_float(interior):
                return True
    return False


def _anotaciones(arbol: ast.Module) -> Iterator[tuple[ast.expr, str]]:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            args = nodo.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation, f"el parámetro {arg.arg} de {nodo.name}"
            if nodo.returns is not None:
                yield nodo.returns, f"el retorno de {nodo.name}"
        elif isinstance(nodo, ast.AnnAssign):
            yield nodo.annotation, f"la anotación de {ast.unparse(nodo.target)}"


def buscar_float(codigo: str, ruta: Path) -> list[Hallazgo]:
    arbol = ast.parse(codigo, filename=str(ruta))
    return [
        Hallazgo(ruta, anotacion.lineno, donde)
        for anotacion, donde in _anotaciones(arbol)
        if _menciona_float(anotacion)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    lector = argparse.ArgumentParser(prog="verificar_float", description=__doc__)
    lector.add_argument("--raiz", type=Path, default=Path("."))
    opciones = lector.parse_args(argv)
    archivos = archivos_a_revisar(opciones.raiz)
    if not archivos:
        print(
            f"verificar_float: ningún archivo que revisar bajo {opciones.raiz.resolve()}; "
            "se ejecuta desde backend/",
            file=sys.stderr,
        )
        return 2
    hallazgos = [h for ruta in archivos for h in buscar_float(ruta.read_text(encoding="utf-8"), ruta)]
    for h in hallazgos:
        print(f"{h.ruta.as_posix()}:{h.linea}: float prohibido en {h.donde} (regla 1 de CLAUDE.md)")
    print(f"verificar_float: archivos revisados: {len(archivos)}; hallazgos: {len(hallazgos)}")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`from __future__ import annotations` no cambia el árbol sintáctico: las anotaciones siguen siendo expresiones, así que el mismo recorrido cubre los dos casos. Las cadenas se analizan como expresión, lo que cubre `'float'` y `Optional['float']`. El código 2 impide un verde silencioso si alguien lo ejecuta desde otro directorio.

**`herramientas/contrato_lista_blanca.py`**:

```python
"""Contrato propio de import-linter (TKT-004): lo que alcanzan los módulos de `origen`,
directa o indirectamente, es de la biblioteca estándar, de `permitidos` o del propio
origen. Sustituye la lista negra de dominio-sin-framework (deuda O1 de TKT-002).

grimp trata la biblioteca estándar como un paquete externo más: se reconoce con
sys.stdlib_module_names del intérprete que ejecuta lint-imports.
"""

from __future__ import annotations

import itertools
import sys
from typing import Any, cast

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output
from importlinter.application.contract_utils import render_broken_contract_guidance
from importlinter.domain.helpers import module_expressions_to_modules
from importlinter.domain.imports import Module, ModuleExpression


def _es_permitido(modulo: str, permitidos: tuple[str, ...]) -> bool:
    if modulo.partition(".")[0] in sys.stdlib_module_names:
        return True
    return any(modulo == p or modulo.startswith(f"{p}.") for p in permitidos)


class ContratoListaBlanca(Contract):
    origen = fields.ListField(subfield=fields.ModuleExpressionField())
    permitidos = fields.ListField(subfield=fields.ModuleField(), required=False)
    broken_contract_guidance = fields.TextField(required=False)

    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        expresiones = cast("list[ModuleExpression]", self.origen)
        origenes = sorted(m.name for m in module_expressions_to_modules(graph, expresiones))
        if not origenes:
            raise ValueError(f"Ningún módulo coincide con {[e.expression for e in expresiones]}.")
        permitidos = tuple(m.name for m in cast("list[Module] | None", self.permitidos) or [])
        for nombre in (*origenes, *permitidos):
            if nombre not in graph.modules:
                raise ValueError(f"El módulo '{nombre}' no existe.")
        violaciones: list[dict[str, Any]] = []
        for origen in origenes:
            for alcanzado in sorted(graph.find_upstream_modules(origen, as_package=True)):
                if _es_permitido(alcanzado, permitidos):
                    continue
                cadena = graph.find_shortest_chain(
                    importer=origen, imported=alcanzado, as_packages=True
                ) or (origen, alcanzado)
                eslabones = [
                    (a, b, tuple(d["line_number"] for d in graph.get_import_details(importer=a, imported=b)))
                    for a, b in itertools.pairwise(cadena)
                ]
                violaciones.append({"origen": origen, "alcanzado": alcanzado, "eslabones": eslabones})
        return ContractCheck(kept=not violaciones, metadata={"violaciones": violaciones})

    def render_broken_contract(self, check: ContractCheck) -> None:
        for violacion in check.metadata["violaciones"]:
            output.print_error(f"{violacion['origen']} no puede alcanzar {violacion['alcanzado']}:")
            for importador, importado, lineas in violacion["eslabones"]:
                output.indent_cursor()
                output.print_error(
                    f"{importador} -> {importado} (l.{', '.join(map(str, lineas))})", bold=False
                )
            output.new_line()
        render_broken_contract_guidance(cast("str | None", self.broken_contract_guidance))
```

Las tres excepciones `ValueError` son la defensa contra el verde vacío: un comodín que no coincide con nada o un nombre mal escrito rompen la ejecución, igual que hacen los contratos nativos con sus campos validados (ADR-018). Si `render_broken_contract_guidance` no admite `None`, se envuelve en `if self.broken_contract_guidance:`.

### Configuración · `backend/pyproject.toml`

Sin cambios en `[project]`, `[dependency-groups]` ni `uv.lock`.

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "RUF032"]      # fila 4

[[tool.mypy.overrides]]
module = ["cimenta.*.dominio.*", "tipos_base.*"]                 # fila 4; el resto del bloque, igual

[tool.importlinter]                                              # fila 5
root_packages = ["cimenta", "tipos_base"]
include_external_packages = true
exclude_type_checking_imports = false
contract_types = ["lista_blanca: herramientas.contrato_lista_blanca.ContratoListaBlanca"]

[[tool.importlinter.contracts]]                                  # fila 5, en el sitio del actual
id = "dominio-sin-framework"
name = "dominio/ solo importa la biblioteca estándar y tipos_base, ni directa ni indirectamente"
type = "lista_blanca"
origen = ["cimenta.*.dominio"]
permitidos = ["tipos_base"]
broken_contract_guidance = "El dominio es Python puro (docs/adr/20260918-dominio-puro.md): solo la biblioteca estándar y tipos_base. No se arregla con una excepción en el contrato."

[[tool.importlinter.contracts]]                                  # fila 5, justo después
id = "tipos-base-puro"
name = "tipos_base solo importa la biblioteca estándar, ni directa ni indirectamente"
type = "lista_blanca"
origen = ["tipos_base"]
broken_contract_guidance = "tipos_base lo importan todos los módulos: no puede depender de ninguno ni de un tercero."
```

`root_package = "cimenta"` desaparece; `lint-imports` pasa de 14 a 15 contratos.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** del siguiente. Todos los comandos, desde `backend/`, salvo los verificadores de documentación, desde la raíz.

**Reglas comunes.**

- Ninguna prueba de este ticket pide `contenedor_postgres` ni ninguna *fixture* que dependa de ella. Cada fila corre sus archivos sin Docker y termina con `uv run pytest` completo **con** Docker, para `CA-R7`.
- Los tests construyen todo importe desde cadena. Donde un caso necesita la construcción prohibida, la escribe y la silencia con un comentario que lo justifica: `Decimal(0.1)  # noqa: RUF032 — el caso necesita exactamente la construcción prohibida` y `Dinero(0.1)  # type: ignore[arg-type]`; `dinero + cantidad` con `# type: ignore[operator]`. mypy revisa `tests/` sin modo estricto, así que un `ignore` sobrante no falla.
- Archivos de prueba planos en `tests/`, sin `__init__.py`, con nombre base único: `test_tipos_base_construccion.py`, `test_tipos_base_aritmetica.py`, `test_tipos_base_explosion.py`, `test_tipos_base_redondeo.py`, `test_tipos_base_mypy.py`, `test_verificar_float.py`, `test_fronteras_dominio.py`, `test_tkt004_conftest.py`.
- Los subprocesos de prueba usan `sys.executable`, `env` con `PYTHONIOENCODING=utf-8` y `COLUMNS=250` (aprendizaje de TKT-002), `encoding="utf-8"` y `timeout=120`. Las copias del árbol usan `shutil.copytree(..., ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".import_linter_cache"))`.
- Las violaciones de `CA-9`, `CA-10` y `CA-11` se escriben en `tmp_path`, nunca en el árbol que se revisa.
- Las filas 1 a 3 verifican mypy estricto sobre el paquete con `uv run mypy --strict tipos_base` mientras el *override* no existe; desde la fila 4, `uv run mypy .`.

**Por qué cada fila lleva su modelo.** Las filas 2 y 3 caen en el disparador «la fila toca una regla de dinero» de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): son la aritmética y el redondeo sobre los que se apoyan `RN-03`, `RN-06` y `RN-07`, y un error ahí no lo nota ningún test de regla posterior. El desarrollador va en `sonnet`. Las filas 1, 4, 5 y 7 tienen su código o su texto literal en este diseño: `haiku`. El tester va siempre en `sonnet`.

**Agentes.** `desarrollador-dominio` hoy escribe «solo bajo `backend/cimenta/<modulo>/dominio/`»; `tipos_base/` es dominio compartido fuera de esa ruta. Se le despacha con la ampliación de D-4, que el gate aprueba. Las filas 4 y 5 son compuertas —un verificador y un contrato que hacen fallar el *pipeline*— más `pyproject.toml`: son de `ingeniero-devsecops`, cuya definición nombra «el pipeline que bloquea un `float`». No añaden dependencias.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| 1 | **Construcción, inmutabilidad e igualdad.** Rojo: los tests fallan con `ModuleNotFoundError: No module named 'tipos_base'` al importar —rojo válido, el módulo no existe— y TC-13 nace en verde y se anota (comprueba un archivo que ya existe; su prueba de que depende de algo es MT-20). Verde: `tipos_base/__init__.py` y de `numericos.py` los contextos, `_viene_de_float`, `_a_decimal`, `_Numero` sin `cuantizar`, `serializar` ni sus auxiliares, y las cuatro clases con sus `ClassVar` y **sin** `__mul__` ni `__truediv__` | TC-01 a TC-13 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_tipos_base_construccion.py tests/test_tkt004_conftest.py` en verde; `uv run mypy --strict tipos_base`, `uv run ruff check .` y `uv run ruff format --check .` en verde; `uv run lint-imports` sigue en `14 kept, 0 broken` | ⚠ Ajustado (ver impl.md) |
| 2 | **Aritmética, división y la explosión de 27 insumos.** Rojo: TC-20 a TC-35 fallan con `TypeError: unsupported operand type(s) for *` o `/` y con `ImportError` de `sumar`; TC-40 a TC-43, igual. TC-35 nace en verde por diseño (es el oráculo de `float`, no depende del código) y se anota. Verde: `__mul__` y `__truediv__` de las cuatro clases según la tabla, `_producto`, `_cociente` y `sumar` | TC-20 a TC-35, TC-40 a TC-43 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `sonnet`, disparador «regla de dinero» | `uv run pytest tests/test_tipos_base_aritmetica.py tests/test_tipos_base_explosion.py` en verde. TC-26 es la comprobación (c): si falla con `MemoryError` o al construir el contexto, la fila se detiene y se escala; **no** se baja `prec` | ✓ Hecho |
| 3 | **Cuantizar y serializar.** Rojo: TC-50 a TC-61 fallan con `AttributeError: 'Dinero' object has no attribute 'cuantizar'` o `'serializar'`. Verde: `cuantizar`, `serializar`, `_a_escala` y `_en_columna` | TC-50 a TC-61 | rojo `tester-backend` · verde `desarrollador-dominio` | tester `sonnet` · verde `sonnet`, disparador «regla de dinero» | `uv run pytest tests/test_tipos_base_*.py` en verde; `uv run mypy --strict tipos_base` en verde | ✓ Hecho |
| 4 | **La regla contra `float`.** Comprobación previa (a): `uv run ruff rule RUF032`. Rojo: TC-70 a TC-77 fallan con `ModuleNotFoundError: No module named 'herramientas.verificar_float'`; TC-78 falla porque la salida de Ruff no contiene `RUF032`; TC-80 falla porque mypy termina con 0 sin el *override*; TC-79 nace en verde (las filas 1 a 3 ya exigieron `--strict`) y se anota. Verde: `herramientas/verificar_float.py` literal; `"RUF032"` en `select`; `"tipos_base.*"` en el *override*. **Si `RUF032` resulta *preview***, no se activa el modo *preview*: se añade a `_anotaciones` una rama para `ast.Call` cuya función es `Decimal` o `<x>.Decimal` y cuyo primer argumento es una constante `float` o su negación, con el mensaje `Decimal construido desde un literal float`, y TC-78 se reescribe contra el verificador | TC-70 a TC-80 | rojo `tester-backend` · verde `ingeniero-devsecops` | tester `sonnet` · verde `haiku`, código literal | `uv run pytest tests/test_verificar_float.py tests/test_tipos_base_mypy.py` en verde; `uv run python -m herramientas.verificar_float` con código 0; `uv run ruff check .` y `uv run mypy .` en verde | ✓ Hecho |
| 5 | **Fronteras: lista blanca y pureza de `tipos_base`.** Comprobación previa (b): `uv run python -c "import sys; print('__future__' in sys.stdlib_module_names, 'decimal' in sys.stdlib_module_names)"` imprime `True True`; si no, se escala. Rojo: TC-90, TC-91, TC-93, TC-94, TC-95 y TC-97 fallan porque la copia del árbol aún tiene la lista negra (pasa `requests`, pasa `tipos_base` que importa `pydantic`; no existe `tipos-base-puro`); TC-92 y TC-96 nacen en verde (la lista negra ya los rechaza) y se anota. Verde: `herramientas/contrato_lista_blanca.py` literal y el bloque `[tool.importlinter]` | TC-90 a TC-98 | rojo `tester-backend` · verde `ingeniero-devsecops` | tester `sonnet` · verde `haiku`, código literal | `uv run lint-imports` con `Contracts: 15 kept, 0 broken` (comprobación (d)); `uv run pytest tests/test_fronteras_dominio.py` en verde; `uv run mypy .` y `uv run ruff check .` en verde | ✓ Hecho (entrega B) |
| 6 | **Mutación y regresión.** Sin código de producción. El tester aplica los mutantes MT-1 a MT-20 de uno en uno, con el SHA-256 del archivo anotado antes y comprobado al restaurar, y ejecuta TC-100 a TC-103 | TC-100 a TC-103 | `tester-backend` | `sonnet` | Tabla de mutantes en `impl.md`: mutante, test que cae, salida. Ningún mutante deja la suite en verde | ✓ Hecho (entregas A y B) |
| 7 | **Documentación y ADR**, según «Documentación afectada»; primero los ADR y su fila del índice | TC-110 a TC-113 | Orquestador con `conv-documentacion`, por sustitución: no hay agente redactor ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)) | `haiku` · textos literales | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` desde la raíz con código 0 | ✓ Hecho (entregas A y B) |

**Modelo:** `haiku` por omisión; `sonnet` en las filas 2 y 3, que citan su disparador, y en el tester. Nunca `opus` en una fila de ejecución.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

**Tamaño: supera el tope de unas 400 líneas.** Estimación de líneas escritas a mano: producción y configuración, unas 400 —`numericos.py` 180, `__init__.py` 12, `verificar_float.py` 90, `contrato_lista_blanca.py` 80, `pyproject.toml` 25—; pruebas, unas 800 —construcción 120, aritmética 170, explosión 70, redondeo y serialización 130, mypy 50, verificador 160, fronteras 160, conftest 15—; documentación, unas 100, y 140 con los dos ADR. **Unas 1,340 en total.** El peso está en las pruebas, y casi todas son rechazos que la spec exige. Siete filas, en el límite de la spec. La spec (INVEST «S») prevé partir en dos entregas, y aquí, a diferencia de TKT-003, **cada entrega se fusiona sola**: ver D-2.

| Entrega | Filas | Criterios que cierra | Líneas | Fusionable sola |
|---|---|---|---|---|
| **A · tipos y linter** | 1, 2, 3, 4; de la 6, MT-1 a MT-15 y MT-19, MT-20; de la 7, todo salvo lo marcado «B» | `CA-1` a `CA-9`, `CA-11`, `CA-12` (parte A), `CA-13`, `CA-R1` a `CA-R7` | unas 1,000 | **Sí.** Sin `root_packages`, `tipos_base` es un externo aplastado que la lista negra actual no prohíbe; los 14 contratos siguen en verde |
| **B · fronteras** | 5; de la 6, MT-16 a MT-18; de la 7, lo marcado «B» y ADR-021 | `CA-10`, `CA-12` (parte B), `CA-R3` con 15 contratos | unas 340 | Sí, sobre A |

## Plan de pruebas

Todos se ejecutan con `uv run pytest` desde `backend/`. El nombre de cada test empieza por `test_tkt004_caNN_`, porque el ticket no tiene escenario HDU. Un caso de rechazo comprueba **el tipo de excepción y el contenido del mensaje** (`pytest.raises(..., match=...)`), no solo que haya excepción.

### Construcción e inmutabilidad (fila 1, `test_tipos_base_construccion.py` y `test_tkt004_conftest.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-01 | `test_tkt004_ca01_construye_desde_cadena_entero_y_decimal`: `Dinero("12.10").valor == Decimal("12.10")` y `str(...) == "12.10"`; `Dinero(12).valor == Decimal(12)`; `Dinero(Decimal("12.10")).valor` igual a la primera | feliz | `CA-1` esc. 1 |
| TC-02 | `test_tkt004_ca01_admite_signo_sin_validar_rangos`: `Dinero`, `Cantidad` y `Porcentaje` de `"-250.0000"` se construyen y su `valor` es `Decimal("-250.0000")` | feliz | `CA-1` esc. 2 |
| TC-03 | `test_tkt004_ca01_rechaza_float`, parametrizado sobre los cuatro tipos: `T(0.1)` lanza `TypeError` con `match="float"` | **rechazo** | `CA-1` esc. 3 |
| TC-04 | `test_tkt004_ca01_rechaza_decimal_construido_desde_float`: `Dinero(Decimal(0.1))` lanza `TypeError` con `match="float"` | **rechazo** | `CA-1` esc. 3, D-1 |
| TC-05 | `test_tkt004_ca01_admite_decimal_exacto_de_dieciocho_digitos`: `Dinero(Decimal("12345678901234.5625"))` se construye. Es un `double` exacto con 18 dígitos: el borde del criterio de la huella | feliz de borde | D-1 |
| TC-06 | `test_tkt004_ca01_rechaza_booleano`: `Dinero(True)` y `Dinero(False)` lanzan `TypeError` con `match="bool"` | **rechazo** | `CA-1` esc. 4 |
| TC-07 | `test_tkt004_ca01_rechaza_cadena_que_no_es_decimal_llano`, parametrizado con `"NaN"`, `"Infinity"`, `"1e3"`, `"1,234.50"`, `" 12.10"`, `"+12.10"` y `""`: `ValueError` cuyo mensaje contiene `repr(cadena)` | **rechazo** | `CA-1` esc. 5 |
| TC-08 | `test_tkt004_ca01_rechaza_decimal_no_finito`: `Decimal("NaN")`, `Decimal("Infinity")` y `Decimal("-Infinity")` dan `ValueError` con `match="finitos"` | **rechazo** | `CA-1` esc. 6 |
| TC-09 | `test_tkt004_ca01_rechaza_otros_tipos`: `Dinero(None)` y `Dinero(Fraction(1, 3))` lanzan `TypeError` cuyo mensaje nombra `NoneType` y `Fraction` | **rechazo** | `M1` |
| TC-10 | `test_tkt004_ca02_valor_inmutable`: asignar `d.valor` y añadir `d.otro` lanzan `AttributeError`; después `d.valor == Decimal("10.0000")` | **rechazo** | `CA-2` esc. 1 |
| TC-11 | `test_tkt004_ca02_igualdad_y_hash_por_valor`: `Dinero("1.0") == Dinero("1.0000")`; un diccionario con la primera como clave se lee con la segunda; un conjunto con las dos tiene un elemento | feliz | `CA-2` esc. 2 |
| TC-12 | `test_tkt004_ca02_sin_conversion_a_float_ni_redondeo` y `test_tkt004_ca02_dinero_y_cantidad_no_se_mezclan`: `float(d)` y `round(d, 2)` lanzan `TypeError`; `Dinero("5.0000")` con `Cantidad("5.0000")`: `+`, `-`, `<` y `>` lanzan `TypeError`, y `==` es `False` | **rechazo** | `CA-2` esc. 3 y 4 |
| TC-13 | `test_tkt004_ca13_conftest_sin_fixtures_autouse`: se analiza `tests/conftest.py` con `ast`; ningún decorador `pytest.fixture` lleva `autouse` | **rechazo** estático | `CA-13` esc. 2 |

### Aritmética (fila 2, `test_tipos_base_aritmetica.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-20 | `test_tkt004_ca03_cantidad_por_rendimiento_conserva_decimales`: `Cantidad("3.1234") * Rendimiento("0.673400")` es `Cantidad`, su `valor == Decimal("2.10329756")` y su exponente es `-10`, no `-4` | feliz | `CA-3` esc. 1 |
| TC-21 | `test_tkt004_ca03_productos_conmutativos`: `Rendimiento * Cantidad`, `Cantidad * Dinero` y `Porcentaje * Dinero` dan el mismo tipo y valor que el orden inverso | feliz | D-6 |
| TC-22 | `test_tkt004_ca03_dinero_por_cantidad_y_por_porcentaje`: `Dinero("1000.0000") * Cantidad("2.5000") == Dinero("2500")` y es `Dinero`; `Dinero("1000.0000") * Porcentaje("0.150000") == Dinero("150")` | feliz | `CA-3` esc. 2 |
| TC-23 | `test_tkt004_ca03_suma_resta_y_coleccion_vacia`: `Dinero("100.1001") + Dinero("0.0009") + Dinero("-50.5") == Dinero("49.601")`; `Dinero("100.1001") - Dinero("0.0009") == Dinero("100.0992")`; `sumar` de los tres da lo mismo; `sumar([], Dinero)` es de tipo `Dinero`, no `int`, y su `valor == 0` | feliz | `CA-3` esc. 3 |
| TC-24 | `test_tkt004_ca03_sumar_rechaza_tipos_mezclados`: `sumar([Dinero("1"), Cantidad("1")], Dinero)` lanza `TypeError` que nombra `Cantidad`; `sum([Dinero("1")])` lanza `TypeError` | **rechazo** | `PA-T16` |
| TC-25 | `test_tkt004_ca03_sin_redondeo_intermedio`: `Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857"))` vale exactamente `Decimal("1000.4989995")` | feliz | `CA-3` esc. 4 (primera mitad) |
| TC-26 | `test_tkt004_ca03_operandos_maximos_exactos`: `Cantidad("9999999999.9999") * Rendimiento("999999999999.999999")` vale `Decimal("9999999999999899990000.0000000001")`, con 32 dígitos significativos | feliz de borde | `CA-3` esc. 5 |
| TC-27 | `test_tkt004_ca03_contexto_del_proceso_no_altera_nada`: dentro de `decimal.localcontext()` con `prec = 5`, `traps[Inexact] = False` y `traps[Rounded] = False`, se repiten los cálculos de TC-20, TC-22, TC-23, TC-25, TC-26 y TC-31 y se comparan con los **mismos literales** | **rechazo** de dependencia | `CA-3` esc. 6 |
| TC-28 | `test_tkt004_ca03_combinaciones_sin_sentido`, parametrizado: `Cantidad * Cantidad`, `Dinero * Dinero`, `Rendimiento + Dinero`, `Dinero * 0.5`, `Dinero * 2`, `2 * Dinero`, `Dinero + 1`, `-Dinero` y `Rendimiento * Dinero` lanzan `TypeError` | **rechazo** | `CA-3` esc. 7, `PA-T15` |
| TC-29 | `test_tkt004_ca04_cantidad_entre_cantidad`: `Cantidad("30.0000") / Cantidad("120.0000")` es `Porcentaje` con `valor == Decimal("0.25")` | feliz | `CA-4` esc. 1 |
| TC-30 | `test_tkt004_ca04_dinero_entre_dinero`: `Dinero("-50.0000") / Dinero("200.0000")` es `Porcentaje` igual a `-0.25` | feliz | `CA-4` esc. 2 |
| TC-31 | `test_tkt004_ca04_division_no_exacta_con_28_digitos`: `Cantidad("1") / Cantidad("3")` vale `Decimal("0." + "3" * 28)`; su exponente es `-28`, no `-6` | feliz | `CA-4` esc. 3 |
| TC-32 | `test_tkt004_ca04_division_entre_cero`: `Cantidad("12.0000") / Cantidad("0.0000")`, `Dinero("1") / Dinero("0")` y `Cantidad("0") / Cantidad("0")` lanzan `ZeroDivisionError` con `match="regla 12"` | **rechazo** | `CA-4` esc. 4 |
| TC-33 | `test_tkt004_ca04_division_entre_tipos_no_admitida`: `Cantidad / Dinero`, `Rendimiento / Rendimiento` y `Porcentaje / Porcentaje` lanzan `TypeError` | **rechazo** | `PA-T11` |
| TC-34 | `test_tkt004_ca07_cero_uno_mas_cero_dos`: para los cuatro tipos, `T("0.1") + T("0.2") == T("0.3")` | feliz | `CA-7` esc. 1 |
| TC-35 | `test_tkt004_ca07_oraculo_float`: `0.1 + 0.2 != 0.3` | **rechazo** (oráculo) | `CA-7` esc. 2 |

### Explosión de 27 insumos (fila 2, `test_tipos_base_explosion.py`)

El fixture es el producto cartesiano de tres cantidades, tres rendimientos y tres precios, sin datos de ninguna obra. Por la propiedad distributiva, la suma de los 27 importes es **el producto de las tres sumas**, que se calcula a mano con enteros y es independiente del código que se prueba; TC-43 lo vuelve a comprobar con `fractions.Fraction`.

```python
CANTIDADES = ("1459.5600", "16.0890", "237.4125")      # suma 1713.0615
RENDIMIENTOS = ("0.673400", "0.017000", "2.437153")    # suma 3.127553
PRECIOS = ("539.6300", "0.2500", "87.1237")            # suma 627.0037
TOTAL_ESPERADO = "3359291.85066580048515"
```

Cálculo del literal: 17130615 × 3127553 = 53,576,906,335,095; × 6270037 = 335,929,185,066,580,048,515; con 4 + 6 + 4 = 14 decimales, `3359291.85066580048515`. Tiene **21 dígitos significativos** y termina en 5: la representación más corta de un `double` tiene como mucho 17, así que `Decimal(repr(suma_en_float))` **no puede** ser igual al literal. El fixture garantiza el rechazo de `CA-8` esc. 3 por construcción, no por suerte.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-40 | `test_tkt004_ca08_explosion_sintetica_sin_desviacion`: *fixture* `explosion_sintetica`, lista de 27 tuplas `(Cantidad, Rendimiento, Dinero)` de `itertools.product`; `sumar([c * r * p for c, r, p in explosion_sintetica], Dinero) == Dinero(TOTAL_ESPERADO)` y el exponente del resultado es `-14`: los renglones no se cuantizaron | feliz | `CA-8` esc. 1 |
| TC-41 | `test_tkt004_ca08_el_orden_no_importa`: los renglones invertidos y barajados con `random.Random(20261019).shuffle` dan el mismo total | feliz | `CA-8` esc. 2 |
| TC-42 | `test_tkt004_ca08_el_mismo_calculo_en_float_se_desvia`: `len(Decimal(TOTAL_ESPERADO).as_tuple().digits) > 17` como guarda, y `Decimal(repr(sum(float(c) * float(r) * float(p) ...))) != Decimal(TOTAL_ESPERADO)` | **rechazo** | `CA-8` esc. 3 |
| TC-43 | `test_tkt004_ca08_total_esperado_independiente`: la suma de los 27 productos con `Fraction(c) * Fraction(r) * Fraction(p)` es igual a `Fraction(TOTAL_ESPERADO)` | oráculo | `CA-8` esc. 1 |

### Redondeo y serialización (fila 3, `test_tipos_base_redondeo.py`)

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-50 | `test_tkt004_ca05_cuantizar_a_la_escala_de_cada_tipo`: `Dinero("2.12345")` → `2.1235`, `Cantidad("2.12345")` → `2.1235`, `Rendimiento("2.1234565")` → `2.123457`, `Porcentaje("0.1234565")` → `0.123457`; el original conserva su valor | feliz | `CA-5` esc. 1 |
| TC-51 | `test_tkt004_ca05_empate_se_aleja_del_cero`: `Dinero("0.00005")` → `0.0001`; `Dinero("-0.00005")` → `-0.0001` | feliz | `CA-5` esc. 2 |
| TC-52 | `test_tkt004_ca05_ya_en_escala_no_cambia`: `Dinero("12.3400").cuantizar() == Dinero("12.34")` | feliz | `CA-5` esc. 3 |
| TC-53 | `test_tkt004_ca05_no_cabe_en_la_columna`: `Dinero("100000000000000.0000")` con `match=r"NUMERIC\(18,4\)"`; `Porcentaje("1000.000000")` con `match=r"NUMERIC\(9,6\)"`; `Cantidad("10000000000")` con `(14,4)`; `Rendimiento("1000000000000")` con `(18,6)`; `Dinero("99999999999999.99995")` falla porque el redondeo lo lleva a quince enteros; `Dinero("99999999999999.9999").cuantizar()` no falla | **rechazo** y borde | `CA-5` esc. 4 |
| TC-54 | `test_tkt004_ca05_nada_cuantiza_por_su_cuenta`: el resultado de TC-20 tiene exponente `-10` y el de TC-25, `-7`, ambos con más decimales que su escala | **rechazo** de redondeo oculto | `CA-5` esc. 5 |
| TC-55 | `test_tkt004_ca03_cuantizar_una_sola_vez_al_final`: la expresión de TC-25 cuantizada es `Dinero("1000.4990")`, y es distinta de `(Dinero("1000.5") * (Cantidad("7") * Rendimiento("0.142857")).cuantizar()).cuantizar()`, que da `Dinero("1000.5000")` | **rechazo** de redondeo intermedio | `CA-3` esc. 4 |
| TC-56 | `test_tkt004_ca06_serializa_con_la_escala_de_la_columna`: `"1234.5000"`, `"8.0000"`, `"0.673400"`, `"0.050000"`; cada uno es `str`, y `json.dumps({"importe": ...})` contiene `"\"1234.5000\""` | feliz | `CA-6` esc. 1 |
| TC-57 | `test_tkt004_ca06_sin_redondeo_ni_notacion_cientifica`: `Dinero("0.00000001").cuantizar().serializar() == "0.0000"`; `Dinero("123456789012.3456789").cuantizar().serializar() == "123456789012.3457"`; `Porcentaje("0.000001").serializar() == "0.000001"`; ninguna contiene `"E"` | feliz | `CA-6` esc. 2 |
| TC-58 | `test_tkt004_ca06_cero_negativo_sin_signo`: `Dinero("-0.0000").serializar()` y `Dinero("-0.00001").cuantizar().serializar()` dan `"0.0000"` | **rechazo** de `-0.0000` | `CA-6` esc. 3 |
| TC-59 | `test_tkt004_ca06_mas_decimales_que_la_escala`: `Dinero("1234.56789").serializar()` lanza `ValueError` con `match="4 decimales"`; `Dinero("1.50000").serializar() == "1.5000"`, porque el criterio es de valor | **rechazo** | `CA-6` esc. 4 |
| TC-60 | `test_tkt004_ca06_ida_y_vuelta`: para `Dinero("1234.5")`, `Dinero("-99999999999999.9999")`, `Cantidad("8")`, `Rendimiento("0.6734")` y `Porcentaje("-0.05")`, `q = v.cuantizar()` y `type(q)(q.serializar()) == q` | feliz | `CA-6` esc. 5 |
| TC-61 | `test_tkt004_ca06_no_serializa_lo_que_no_cabe`: `Dinero("100000000000000.0000").serializar()` lanza `ValueError` con `match=r"NUMERIC\(18,4\)"` | **rechazo** | `CA-6` esc. 6 |

### La regla contra `float` y mypy (fila 4, `test_verificar_float.py` y `test_tipos_base_mypy.py`)

Una función auxiliar del test, `escribir(tmp_path, ruta_relativa, codigo)`, crea el archivo y sus directorios. Los casos en proceso llaman a `verificar_float.main(["--raiz", str(tmp_path)])` y leen la salida con `capsys`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-70 | `test_tkt004_ca09_dominio_sin_float_pasa`: `cimenta/demo/dominio/reglas.py` con firmas de `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje` y un campo de *dataclass* `Dinero` → código 0; salida `archivos revisados: 1; hallazgos: 0` | feliz | `CA-9` esc. 1 |
| TC-71 | `test_tkt004_ca09_float_en_parametro_y_retorno`: `def disponible(presupuestado: float) -> float: ...` en la línea 3 → código 1; dos líneas que empiezan por `cimenta/demo/dominio/reglas.py:3:`, una con `el parámetro presupuestado de disponible` y otra con `el retorno de disponible` | **rechazo** | `CA-9` esc. 2 |
| TC-72 | `test_tkt004_ca09_float_compuesto_o_en_cadena`, parametrizado sobre `float \| None`, `Optional[float]` (con `from typing import Optional`), `list[float]`, `dict[str, float]` y `'float'`, cada uno con y sin `from __future__ import annotations` → código 1 y un hallazgo en la línea esperada | **rechazo** | `CA-9` esc. 3 |
| TC-73 | `test_tkt004_ca09_float_en_campo_de_dataclass`: `tasa: float` dentro de una clase `@dataclass` → hallazgo `la anotación de tasa` | **rechazo** | `CA-9` esc. 4 |
| TC-74 | `test_tkt004_ca09_cubre_tipos_base`: `tipos_base/x.py` con `def f(x: float) -> None` → código 1 | **rechazo** | `CA-9` esc. 6 |
| TC-75 | `test_tkt004_ca09_no_revisa_api_ni_infraestructura`: `float` en `cimenta/demo/api/rutas.py` y en `cimenta/demo/infraestructura/repo.py`, más un dominio limpio → código 0 y `archivos revisados: 1` | **rechazo** de alcance | `CA-9` esc. 7 |
| TC-76 | `test_tkt004_ca09_sin_archivos_no_da_verde`: `tmp_path` vacío → código 2 y mensaje en `stderr` | **rechazo** | anti-verde vacío |
| TC-77 | `test_tkt004_ca09_comando_documentado_sobre_el_arbol_real`: subproceso `[sys.executable, "-m", "herramientas.verificar_float"]` con `cwd` en `backend/` → código 0 y `archivos revisados: N` con `N ≥ 12` (diez `dominio/__init__.py` y dos de `tipos_base`) | feliz | `CA-9` esc. 1 |
| TC-78 | `test_tkt004_ca09_decimal_desde_literal_float`: en `tmp_path`, copia de `backend/pyproject.toml` y `cimenta/demo/dominio/reglas.py` con `from decimal import Decimal` (línea 1), `X = Decimal(0.1)` (línea 3) y `Y = Decimal("0.1")` (línea 4); subproceso `[sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "concise", "."]` con `cwd=tmp_path` → la salida contiene `reglas.py:3:` seguido de `RUF032`, y ninguna línea `reglas.py:4:` con `RUF032` | **rechazo** | `CA-9` esc. 5 |
| TC-79 | `test_tkt004_ca11_tipos_base_pasa_mypy_estricto`: copia a `tmp_path` de `pyproject.toml` y `tipos_base/`; subproceso `[sys.executable, "-m", "mypy", "tipos_base", "--cache-dir", <directorio de sesión>]` → código 0 | feliz | `CA-11` esc. 1 |
| TC-80 | `test_tkt004_ca11_funcion_sin_tipos_rompe_mypy`: la misma copia con `def sin_tipos(x): return x` añadida a `tipos_base/numericos.py` → código distinto de 0 y `missing a type annotation` en la salida | **rechazo** | `CA-11` esc. 2 |

### Fronteras (fila 5, `test_fronteras_dominio.py`)

Cada caso copia a `tmp_path` `pyproject.toml`, `cimenta/`, `tipos_base/` y `herramientas/`, añade su archivo y ejecuta `lint-imports --no-cache` con `cwd=tmp_path` (`shutil.which("lint-imports")`; si es `None`, `pytest.fail`). «Roto» es código distinto de 0 **y** una línea con el `name` del contrato y `BROKEN`.

| # | Caso | Tipo | Criterio |
|---|---|---|---|
| TC-90 | `test_tkt004_ca10_dominio_importa_estandar_y_tipos_base`: `cimenta/compras/dominio/regla_tkt004.py` con `from __future__ import annotations`, `from decimal import Decimal` y `from tipos_base import Dinero` → código 0 y `Contracts: 15 kept, 0 broken` | feliz | `CA-10` esc. 1 |
| TC-91 | `test_tkt004_ca10_tercero_cualquiera_rompe_el_dominio`, parametrizado con `requests` y `numpy` → `dominio-sin-framework` roto y `no puede alcanzar requests` (o `numpy`) | **rechazo** | `CA-10` esc. 2 |
| TC-92 | `test_tkt004_ca10_framework_directo_rompe_el_dominio`: `import pydantic` en el dominio → roto | **rechazo** | `CA-10` esc. 3 |
| TC-93 | `test_tkt004_ca10_framework_indirecto_rompe_el_dominio`: `tipos_base/numericos.py` de la copia con `import sqlalchemy` y un dominio que importa `tipos_base` → `dominio-sin-framework` **y** `tipos-base-puro` rotos; la cadena impresa contiene `tipos_base` y `sqlalchemy` | **rechazo** | `CA-10` esc. 3 |
| TC-94 | `test_tkt004_ca10_dominio_no_importa_la_interfaz_de_otro_modulo`: `cimenta/compras/dominio/regla_tkt004.py` con `from cimenta.presupuesto import interfaz` → `dominio-sin-framework` roto, aunque el grafo permita `compras → presupuesto` | **rechazo** | `O1`, D-5 |
| TC-95 | `test_tkt004_ca10_tipos_base_puro`, parametrizado: `tipos_base` que importa `pydantic` o `cimenta.presupuesto` → `tipos-base-puro` roto | **rechazo** | `CA-10` esc. 4 |
| TC-96 | `test_tkt004_car3_contratos_de_tkt002_siguen_vigentes`, tres casos: `cimenta/extra/__init__.py` → código distinto de 0 y `cimenta.extra` en la salida; dominio con `import fastapi` → `dominio-sin-framework` roto; `cimenta/compras/aplicacion/x.py` con `import cimenta.presupuesto.dominio` → `solo-por-interfaz` roto | **rechazo** | `CA-R3` |
| TC-97 | `test_tkt004_ca10_comodin_sin_coincidencia_no_da_verde`: en el `pyproject.toml` de la copia, `origen = ["cimenta.*.nada"]` → código distinto de 0 y `Ningún módulo coincide` | **rechazo** | anti-verde vacío |
| TC-98 | `test_tkt004_ca10_arbol_real`: `lint-imports --no-cache` con `cwd` en `backend/` → `Contracts: 15 kept, 0 broken` | feliz | `CA-10`, `CA-R3` |

### Regresión y cierre (filas 6 y 7, comandos)

| # | Caso | Criterio |
|---|---|---|
| TC-100 | Con `DOCKER_HOST=tcp://127.0.0.1:9` en el entorno, `uv run pytest` con los ocho archivos de este ticket nombrados uno a uno → todos en verde, ningún error de contenedor | `CA-13` esc. 1 |
| TC-101 | `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy .` con código 0; `[tool.ruff.lint]` tiene `select` con `"I"` y no tiene la clave `extend-select` | `CA-R1` |
| TC-102 | `uv sync --locked` con código 0 y `git diff --exit-code backend/uv.lock` con código 0 | `CA-R2` |
| TC-103 | Con Docker en marcha, `uv run pytest` completo: los 13 tests de identidad y todos los de este ticket en verde, con la línea de resumen en `impl.md` | `CA-R7` |
| TC-110 | `CLAUDE.md` y `docs/arranque-local.md` no contienen `desde TKT-004` | `CA-12` esc. 1 |
| TC-111 | `CLAUDE.md`, `docs/02-arquitectura.md` y `conv-dominio-python` contienen `tipos_base` y `ROUND_HALF_UP`; `conv-dominio-python` §3 ya no contiene `Decimal("0.01")` en el constructor | `CA-12` esc. 2 |
| TC-112 | `python tools/verificar_docs.py` y `python tools/extraer_mermaid.py` con código 0; ningún archivo nuevo con BOM ni CRLF | `CA-12` esc. 3, `CA-R5`, `CA-R6` |
| TC-113 | `CLAUDE.md` y `docs/arranque-local.md` siguen diciendo `desde TKT-005 (asumido)` para `uv run fastapi dev` y `desde TKT-008` para `npm run dev` | `CA-R4` |

### Mutación

Cada mutante se aplica solo, se ejecuta `uv run pytest` sobre los archivos de este ticket y se confirma que **al menos** los casos indicados se ponen rojos; después se revierte y se comprueba el hash.

| Mutante | Dónde y qué | Debe ponerse rojo |
|---|---|---|
| MT-1 | `_a_escala` con `ROUND_HALF_EVEN` | TC-51 (`0.00005` da `0.0000`) |
| MT-2 | `__add__`, `__sub__` y `_producto` con los operadores `+`, `-` y `*` de `Decimal` en lugar de `_EXACTO` | TC-27 y TC-26 (el contexto por omisión redondea a 28 dígitos) |
| MT-3 | `_EXACTO` con `prec=28` | TC-26 (`Rounded` atrapado: falla en lugar de redondear) |
| MT-4 | `cuantizar` devuelve `self` | TC-50, TC-51, TC-55 |
| MT-5 | `serializar` cuantiza en silencio en vez de rechazar | TC-59 |
| MT-6 | `_a_decimal` acepta `float` con `Decimal(str(valor))` | TC-03 |
| MT-7 | Sin la comprobación de `bool` | TC-06 |
| MT-8 | Expresión regular con `[+-]?` | TC-07 (`"+12.10"`) |
| MT-9 | `_en_columna` con `>` en lugar de `>=` | TC-53 y TC-61 (quince enteros exactos pasan) |
| MT-10 | `_cociente` devuelve `Porcentaje("0")` ante divisor cero | TC-32 |
| MT-11 | `_DIVISION` con `prec=10` | TC-31 |
| MT-12 | `serializar` sin la normalización del cero | TC-58 |
| MT-13 | `verificar_float`: sin la rama de `ast.Constant` | TC-72 (`'float'`) |
| MT-14 | `verificar_float`: sin la rama de `ast.AnnAssign` | TC-73 |
| MT-15 | `verificar_float.main` devuelve siempre 0 («regla vaciada») | TC-71 a TC-74; `RUF032` fuera de `select` → TC-78; `tipos_base.*` fuera del *override* → TC-80 |
| MT-16 | Contrato: `_es_permitido` devuelve `True` para todo lo que no empieza por `cimenta` | TC-91, TC-92, TC-95 |
| MT-17 | Contrato: solo imports directos (`find_modules_directly_imported_by` sobre el paquete y sus descendientes) | TC-93 (el dominio pasa; solo cae `tipos-base-puro`) |
| MT-18 | Contrato: sin la rama de `sys.stdlib_module_names` | TC-90 |
| MT-19 | Sin `_viene_de_float` | TC-04 |
| MT-20 | `@pytest.fixture(autouse=True)` en una *fixture* de `conftest.py` | TC-13 |

## Impacto

`revisor-impacto` no existe; el análisis lo hace el arquitecto por sustitución ([metodología §13](../../metodologia.md#13--el-catálogo-de-agentes-y-qué-hacer-cuando-uno-no-existe)).

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `[tool.importlinter]`: `root_packages`, `contract_types`, `dominio-sin-framework` con otro tipo y un contrato nuevo | Todo ticket con `dominio/`; TKT-005, que comparte `pyproject.toml` | Que un dominio futuro que hoy importaría otro módulo o un tercero deje de pasar; conflicto de fusión con TKT-005 | Es la regla 2 escrita; el mensaje del contrato dice qué hacer. TKT-005 rebasa y no toca este bloque |
| Contrato propio en `herramientas/` | `lint-imports` en local y en CI (TKT-009) | Que `lint-imports` no lo encuentre si se ejecuta fuera de `backend/`; que una versión futura de `import-linter` cambie `module_expressions_to_modules`, que no es API documentada | TKT-002 ya exige ejecutarlo desde `backend/`. La versión está fijada en `uv.lock`; si cambia, TC-90 a TC-98 lo detectan |
| `sys.stdlib_module_names` | El contrato | Un módulo que salga de la biblioteca estándar en una versión futura pasaría a contar como tercero | Falla hacia el lado seguro: rompe el contrato, no lo relaja |
| `RUF032` en todo `backend/` | `migraciones/`, `herramientas/`, `tests/` | Un test que necesite `Decimal(0.1)` | `noqa` con motivo, como en este ticket |
| `herramientas.verificar_float` | TKT-009 (pipeline), TKT-062 (PR de ensayo con un `float`) | Que el pipeline no lo ejecute y la regla 1 vuelva a ser solo texto | Documentado en `CLAUDE.md`; TKT-009 lo añade como paso |
| `tipos_base` | TKT-012, 014, 016, 020, 034, 039 y los modelos de TKT-005 | Que necesiten una operación que no existe (`Dinero ÷ Cantidad`, negación) o que `copy`/`pickle` falle | Cada operación nueva se añade con su escenario (`PA-T15`); la *dataclass* con *slots* ya da `copy` y `pickle` |
| `Dinero` como precio unitario | TKT-014, TKT-016 | Su columna es `NUMERIC(14,4)` y `cuantizar` admite catorce enteros: un precio de once enteros pasaría `cuantizar` y lo rechazaría PostgreSQL | `PA-T3`, decisión del usuario. Si duele, `PrecioUnitario` en TKT-014 |
| `desarrollador-dominio` | Filas 1 a 3 y futuros cambios de `tipos_base` | Su definición no cubre `tipos_base/` | D-4 |

**Fronteras entre módulos:** no. Ningún módulo habla con otro; el ticket **cierra** además la puerta `dominio → interfaz` de otro módulo, que `O1` dejaba abierta.

### Impacto en tickets posteriores

| Ticket | Qué hereda | Qué tiene que saber |
|---|---|---|
| TKT-005 | `pyproject.toml`; tipos para los DTO | Los DTO convierten con `Dinero(cadena)` a la entrada y `.cuantizar().serializar()` a la salida; los errores de estos tipos son `TypeError`, `ValueError` y `ZeroDivisionError`, y traducirlos a `422` es suyo (`PA-T8`) |
| TKT-009 | Dos comandos | El pipeline ejecuta, desde `backend/`, `uv run lint-imports` (15 contratos) y `uv run python -m herramientas.verificar_float` |
| TKT-016 | La explosión | Sumar con `sumar(..., Dinero)` y cuantizar una vez al final; ratificar `ROUND_HALF_UP` (`PA-T5`) |
| TKT-039 | División | `ZeroDivisionError` con alcance cero: el semáforo decide `NULL` **antes** de dividir (regla 12) |

## Documentación afectada

Los textos son literales para que la fila 7 los copie. Ninguno usa sintaxis de enlace hacia un archivo que aún no existe. «B» marca lo que va con la entrega B si el gate elige partir (D-2).

| Documento | Qué cambia |
|---|---|
| `CLAUDE.md`, regla 1 | «Está prohibido `float` en cualquier firma de dominio y el linter lo bloquea (desde TKT-004).» pasa a «Está prohibido `float` en cualquier firma de `dominio/` y de `tipos_base/`: lo marcan `uv run python -m herramientas.verificar_float` y, para `Decimal(0.1)`, la regla `RUF032` de Ruff (en el pipeline desde TKT-009). Los tipos son `Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`, de `tipos_base`: calculan con precisión completa y solo redondean con `cuantizar()`.» |
| `CLAUDE.md`, regla 2 · **B** | «Ni FastAPI, ni SQLAlchemy, ni Pydantic.» pasa a «Ni FastAPI, ni SQLAlchemy, ni Pydantic, ni ningún otro paquete: solo la biblioteca estándar y `tipos_base`.» |
| `CLAUDE.md`, «Estructura del backend» | El párrafo «Fuera de `cimenta/`…» pasa a «Fuera de `cimenta/`, en `backend/`, viven `tipos_base/` (`Dinero`, `Cantidad`, `Rendimiento` y `Porcentaje`, que importa cualquier capa de cualquier módulo), `migraciones/` (Alembic), `herramientas/` (operación y verificadores propios, como fijar las contraseñas de los roles o buscar `float` en el dominio) y `tests/`. `import-linter` analiza `cimenta/` y `tipos_base/`; los demás, no.» (la última frase, en la entrega B; en A: «`import-linter` no analiza los tres últimos.») |
| `CLAUDE.md`, comandos «Desde `backend/`» | Tras `uv run lint-imports`: `uv run python -m herramientas.verificar_float   # float prohibido en firmas de dominio/ y tipos_base/` |
| `CLAUDE.md`, línea 14; `README.md`; `llms.txt` | 19 → 20 decisiones con ADR-020, y → 21 con ADR-021 (**B**) |
| `docs/arranque-local.md`, bloque «Backend» | Tras `uv run lint-imports`, la línea `uv run python -m herramientas.verificar_float`, y este párrafo tras el de `lint-imports`: «`uv run python -m herramientas.verificar_float` busca `float` en las anotaciones de `cimenta/*/dominio/` y `tipos_base/`: parámetros, retornos y campos, también dentro de `float \| None`, `list[float]` o una anotación en cadena. Termina con 0 si no encuentra ninguno; con 1 si encuentra alguno, con su archivo y su línea; y con 2 si no encuentra nada que revisar, que es lo que pasa fuera de `backend/`. `Decimal(0.1)` lo marca `ruff check` con la regla `RUF032`.» Y tras el de `uv run pytest`: «Los tests de los tipos base y de los verificadores no necesitan Docker.» |
| `docs/arranque-local.md`, párrafo de `lint-imports` · **B** | «que ningún `dominio/` importe FastAPI, SQLAlchemy ni Pydantic» pasa a «que ningún `dominio/` alcance, ni directa ni indirectamente, nada que no sea la biblioteca estándar o `tipos_base`, que `tipos_base` solo alcance la biblioteca estándar». «porque busca el paquete `cimenta` en el directorio actual» pasa a «porque busca en el directorio actual los paquetes `cimenta` y `tipos_base` y el contrato propio de `herramientas/`» |
| `docs/02-arquitectura.md` §7.4 | Tras la tabla, antes de «Regla de redondeo»: «**Tipos.** `Dinero` —importes y precios unitarios—, `Cantidad`, `Rendimiento` y `Porcentaje` viven en `backend/tipos_base/`, fuera de `cimenta/` para que cualquier capa de cualquier módulo los importe sin ser un módulo más del grafo de §5. Calculan con un contexto de `decimal` propio, independiente del del proceso: sumas, restas y productos son exactos, y una división da un `Porcentaje` con 28 dígitos significativos o falla con `ZeroDivisionError`, nunca devuelve cero. Solo existen `Cantidad × Rendimiento → Cantidad`, `Dinero × Cantidad → Dinero` y `Dinero × Porcentaje → Dinero`, en los dos órdenes, y `Cantidad ÷ Cantidad` y `Dinero ÷ Dinero → Porcentaje`; lo demás es `TypeError`. Los usan la explosión de insumos (TKT-016), `RN-03` (TKT-020), `RN-06` y `RN-07` (TKT-034), el semáforo (TKT-039) y las retenciones (TKT-012).» Tras el párrafo de redondeo: «Redondear es llamar a `cuantizar()`, que lleva el valor a la escala de su columna con `ROUND_HALF_UP` `(asumido)` y falla si no cabe. `serializar()` produce la cadena de escala completa que viaja en JSON y **no redondea**: rechaza un valor sin cuantizar. Un precio unitario es un `Dinero`; su columna `NUMERIC(14,4)` admite cuatro enteros menos que la escala de `Dinero`, y el excedente lo rechaza PostgreSQL.» |
| `docs/02-arquitectura.md` §12 | Filas de ADR-020 y ADR-021 (**B**) |
| `docs/06-stack-tecnologico.md` §8 | Fila de mypy: «Tipos, en modo estricto sobre `dominio/` y `tipos_base/`». **B:** la fila `dominio-sin-framework` pasa a «`dominio-sin-framework` y `tipos-base-puro` · `lista_blanca`, tipo propio en `herramientas/`, con indirectos · un `dominio/` que alcanza algo que no es la biblioteca estándar, `tipos_base` o su propio paquete; `tipos_base` que alcanza algo fuera de la biblioteca estándar». Tras «Por qué estos tipos», la mención de ADR-021. §11 y §13: los dos ADR en la lista |
| `docs/adr/README.md` | Filas de ADR-020 y ADR-021 (**B**); la de ADR-018 añade «· **sustituido por ADR-021**» en «Afecta a» (**B**) |
| `.claude/skills/conv-dominio-python/SKILL.md` §1 | El punto de cuantización pasa a «Cuantización **explícita** con `cuantizar()` de los tipos de `tipos_base`: lleva el valor a la escala de su columna con `ROUND_HALF_UP` `(asumido, PA-T5 de TKT-004)` y falla si no cabe. Fuera de los tipos, `.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)` con escala y modo declarados.» Punto nuevo al final de §1: «`float` en una anotación de `dominio/` o de `tipos_base/` lo marca `uv run python -m herramientas.verificar_float`; `Decimal(0.1)`, la regla `RUF032` de Ruff.» |
| `.claude/skills/conv-dominio-python/SKILL.md` §3 | El ejemplo pasa a `from tipos_base import Cantidad, Dinero, Rendimiento` y `def importe_de_insumo(cantidad: Cantidad, rendimiento: Rendimiento, precio: Dinero) -> Dinero: return precio * (cantidad * rendimiento)`. El texto pasa a «Los cuatro tipos de `tipos_base` son `@dataclass(frozen=True, slots=True)`: inmutables, sin atributos nuevos, iguales por valor y solo con su mismo tipo. El constructor admite `str`, `int` o `Decimal`, nunca `float`, y **no fija la escala**: el valor conserva la precisión completa hasta `cuantizar()`, y `serializar()` rechaza lo que no se ha cuantizado. Un objeto de valor propio de un módulo sigue el mismo patrón.» |
| `.claude/agents/desarrollador-dominio.md` — **corrección con aprobación humana (D-4)** | «Escribes **solo** bajo `backend/cimenta/<modulo>/dominio/`.» pasa a «Escribes **solo** bajo `backend/cimenta/<modulo>/dominio/` y `backend/tipos_base/`.» |
| Dos ADR nuevos | Ver «¿Merece ADR?» |
| Glosario, `docs/03-modelo-datos.md` | Sin cambio. El modelo de datos ya declara las precisiones; el puente entre columnas y tipos queda en arquitectura §7.4 |

## ¿Merece ADR?

**Sí, dos**, en formato MADR, estado `Aceptado`, escritos en la fila 7. Quien llegue verá un paquete fuera de `cimenta/`, un contexto de `decimal` con precisión ilimitada, un verificador propio y un contrato propio de `import-linter`, y se preguntará por qué; en las cuatro decisiones hubo opciones descartadas con motivo.

**ADR-020 · `docs/adr/20261019-tipos-numericos-base.md` — Tipos numéricos base con aritmética exacta y redondeo explícito.** Afecta a «Todos los módulos».

- **Ubicación.** Elegida: `backend/tipos_base/`. Descartadas: un undécimo módulo `cimenta/comun` (rompe `esqueleto-modulos`, añade un nodo al grafo de §5 y una arista desde cada módulo); `cimenta/tipos.py` en la raíz del paquete (el `layers` exhaustivo también lo rechaza); un tipo por módulo (cuatro sitios donde el redondeo diverge).
- **Aritmética.** Elegida: contexto propio con `MAX_PREC` y `Inexact` y `Rounded` atrapados, y 28 dígitos solo para dividir. Descartadas: el contexto del proceso (cualquier `getcontext().prec = …` en otro sitio cambiaría los importes); precisión fija de 28 (redondea en silencio el producto de los máximos de columna).
- **Redondeo.** Elegido: `cuantizar()` explícito con `ROUND_HALF_UP` `(asumido)`. Descartados: `ROUND_HALF_EVEN`, pendiente de negocio (`PA-T5`); redondear en el constructor, como decía el ejemplo antiguo de la convención (pierde precisión intermedia).
- **Serialización.** Elegida: cadena de escala completa que rechaza lo no cuantizado. Descartada: serializar redondeando (es el redondeo oculto que la regla prohíbe).
- **`float`.** Elegido: `RUF032` más un verificador AST propio. Descartados: `banned-api` (no distingue anotaciones), un plugin de mypy (más código y acoplado a su versión), el hook de agente (no corre en CI).
- **Consecuencias:** ningún resultado depende del contexto global; `Dinero × 2` no existe; un alias de `float` pasa (`PA-T14`).
- **Cuándo revisar:** si negocio elige otro modo de redondeo, o si un ticket necesita una precisión de división mayor.

**ADR-021 · `docs/adr/20261019-lista-blanca-del-dominio.md` — El dominio importa solo la biblioteca estándar y `tipos_base`, verificado con un contrato propio de `import-linter`.** Afecta a «Todo el backend»; sustituye el contrato `dominio-sin-framework` de ADR-018.

- **Elegido:** tipo de contrato `lista_blanca` en `herramientas/`, que recorre todo lo alcanzable y reconoce la biblioteca estándar con `sys.stdlib_module_names`.
- **Descartados:** `forbidden` con una lista negra más larga (no cierra `O1`: el paquete siguiente pasa); `forbidden` con todos los paquetes instalados (se desincroniza de `uv.lock` y no ve un paquete aún no instalado); `forbidden_modules = ["*"]` (grimp trata la biblioteca estándar como externa y los comodines no admiten negación); un verificador AST fuera de `import-linter` (rehace el grafo que `import-linter` ya construye y no ve los indirectos).
- **Consecuencias:** el dominio tampoco importa la interfaz de otro módulo; son unas ochenta líneas propias que mantener, con nueve pruebas y tres mutantes; la biblioteca estándar es la del intérprete que ejecuta `lint-imports`.
- **Cuándo revisar:** si `import-linter` incorpora una lista de permitidos nativa, o si un dominio necesita de verdad un tercero.

## Decisiones sobre las preguntas abiertas de la spec

| # | Decisión del diseño |
|---|---|
| `PA-T1` | Nombre: `tipos_base`, en `backend/tipos_base/` |
| `PA-T5` | Se mantiene `ROUND_HALF_UP` `(asumido)`; TC-51 y MT-1 lo fijan, y cambiarlo es una línea y un test |
| `PA-T6` | **Confirmada:** 28 dígitos significativos exactos en la división, con `ROUND_HALF_UP` en el último. Suma y producto, sin límite |
| `PA-T7` | **Confirmada:** `serializar` rechaza un valor con más decimales que su escala, con criterio de valor |
| `PA-T8` | **Confirmada:** `TypeError`, `ValueError` y `ZeroDivisionError` |
| `PA-T9` | **Resuelta:** `RUF032` para `Decimal(0.1)`; verificador AST propio para las anotaciones, porque Ruff no tiene regla. Comando documentado aparte; TKT-009 lo pone en el pipeline |
| `PA-T12` | **Resuelta:** ningún contrato nativo puede, porque grimp incluye la biblioteca estándar como externa y los comodines no niegan; sí puede el mecanismo de contratos propios de `import-linter`. No hace falta escalar |
| `PA-T13` | **Confirmada** por lectura de `conftest.py`; TC-13 y TC-100 la vuelven verificable |
| `PA-T14` | Hueco conocido, declarado en el docstring del verificador |
| `PA-T15` | **Confirmada**, con la conmutatividad de D-6 |
| `PA-T16` | **Confirmada:** `sumar(valores, tipo)`, vacía da el cero del tipo |

## Decisiones que requieren al usuario en el gate

| # | Pregunta | Recomendación | Si se decide otra cosa |
|---|---|---|---|
| D-1 | `CA-1` esc. 3 pide `TypeError` para `Dinero(Decimal(0.1))`, que en ejecución es un `Decimal` cualquiera. ¿Se acepta la huella «más de 18 dígitos y exactamente un `double`»? | **Sí.** Es la única forma de cumplir el escenario tal como está escrito; un `Decimal(float)` de 18 dígitos o menos es exacto y no arrastra error, y TC-05 prueba que no rechaza un valor legítimo de columna | Se quitan `_viene_de_float`, TC-04, TC-05 y MT-19, y la segunda mitad del escenario se cubre solo con `RUF032` (TC-78); hay que reescribir `CA-1` esc. 3 |
| D-2 | El orden suma unas 1,340 líneas. ¿Cómo se entrega? | **Dos PR dentro del ticket**, A (tipos y linter) y B (fronteras). A diferencia de TKT-003, A se fusiona sola sin dejar nada a medias | Un solo PR, en el orden de las siete filas |
| D-3 | ¿Se escriben los dos ADR? | **Sí** | Las decisiones quedan solo en este diseño y en `delta.md` |
| D-4 | ¿Se amplía `desarrollador-dominio` a `backend/tipos_base/`? | **Sí**: es dominio compartido, con la misma convención | Las filas 1 a 3 las ejecuta el orquestador por sustitución, y se anota en `_evolucion.md` |
| D-5 | La lista blanca prohíbe también que un dominio importe la **interfaz** de otro módulo (la otra mitad de `O1`). ¿Se acepta? | **Sí**: es la regla 2 literal; los datos de otro módulo llegan al dominio por la aplicación, ya materializados | Se añade `cimenta.*.interfaz` a `permitidos` y TC-94 se invierte |
| D-6 | Los productos se admiten en los dos órdenes, aunque `M2` los nombra en uno | **Sí**: `CA-8` necesita `Cantidad × Dinero` y TKT-012 `Porcentaje × Dinero` | Solo el orden literal; `CA-8` se escribe `p * (c * r)` y TC-21 desaparece |
| D-7 | `RUF032` activa en todo `backend/`, no solo en el dominio | **Sí**: la regla 1 no admite `Decimal(0.1)` en ningún sitio | `per-file-ignores` que la limite, con su prueba |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El contrato propio es código nuestro: un error suyo da verde sin que nadie lo note, exactamente lo que ADR-018 evitó eligiendo campos validados | Tres `ValueError` contra el verde vacío (TC-97), cinco casos de rechazo reales (TC-91 a TC-95) y tres mutantes que vacían su lógica (MT-16 a MT-18) |
| 2 | Alta | El arquitecto no ejecutó nada: el diseño descansa en lectura de código | Declarado arriba; cuatro comprobaciones con comando y regla de salida en las filas 2, 4 y 5; el contrato funciona aunque grimp excluyera la biblioteca estándar. **Tres de las comprobaciones ya las ejecutó el orquestador el 2026-10-19:** `RUF032` es estable en Ruff 0.17.1 y marca `Decimal(0.1)` sin modo *preview* (el riesgo de la fila 4 queda descartado); el producto de `Cantidad` y `Rendimiento` máximos de columna es exacto con `MAX_PREC` y `Inexact` atrapado; `__future__` y `decimal` están en `sys.stdlib_module_names`. Siguen pendientes de ejecutar, en su fila, el contrato `lista_blanca` y `lint-imports` con 15 contratos |
| 3 | Media | La huella de `float` es heurística | D-1; TC-05 cubre el borde de 18 dígitos; solo se aplica a la entrada pública, nunca a los resultados internos (`_nuevo`) |
| 4 | Media | El non-goal «los tipos solo aceptan lo que cabe en la precisión de su columna» contradice que `CA-5` y `CA-6` construyan un `Dinero` de quince enteros | Se lee como frontera: el constructor no comprueba el rango y `cuantizar` y `serializar` sí. Un producto intermedio puede superar la columna legítimamente |
| 5 | Media | Los contextos de módulo son compartidos entre hilos y sus banderas se escriben en cada operación | Las banderas no se leen nunca; cada trampa se evalúa con el estado de su propia operación y, con el GIL, cada operación de `_decimal` es atómica. Un intérprete sin GIL queda fuera del stack |
| 6 | Media | `if disponible:` es siempre verdadero, también con `Dinero("0")` | Ningún Must lo pide; se propone `__bool__` que lance `TypeError` como ticket futuro |
| 7 | Media | `RUF032` no ve `Decimal(float(x))` ni `Decimal(variable_float)` | Fuera del alcance de la spec («desde un literal»); en ejecución, la huella de D-1 lo detecta si tiene más de 18 dígitos |
| 8 | Baja | `module_expressions_to_modules` no es API documentada de `import-linter` | Versión fijada en `uv.lock`; las pruebas de la fila 5 detectan un cambio |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| `RUF032` es *preview* en Ruff 0.17.1 | Baja | Media | Alternativa escrita en la fila 4: rama en el verificador |
| `MAX_PREC` falla en el intérprete del entorno | Baja | Alta | TC-26 lo detecta en la fila 2; la fila se detiene y se escala, sin bajar la precisión |
| Las pruebas de subproceso (mypy, Ruff, `lint-imports`) alargan la suite | Media | Baja | Unos 30 s; caché de mypy de sesión |
| Un ticket necesita una operación no prevista | Media | Baja | Se añade con su escenario (`PA-T15`) |
| TKT-005 llega antes y choca en `pyproject.toml` | Media | Baja | El segundo rebasa; ninguno regenera `uv.lock`, porque ninguno añade dependencias de este bloque |
