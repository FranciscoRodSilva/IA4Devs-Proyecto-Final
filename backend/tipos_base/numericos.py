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

# Cambiar el modo de redondeo es cambiar esta constante (PA-T5 de TKT-004).
_MODO_REDONDEO = ROUND_HALF_UP

# Suma, resta y producto exactos. Inexact y Rounded atrapados: si algo redondeara, falla.
_EXACTO = Context(
    prec=MAX_PREC,
    rounding=_MODO_REDONDEO,
    Emax=MAX_EMAX,
    Emin=MIN_EMIN,
    traps=[InvalidOperation, DivisionByZero, Overflow, Inexact, Rounded],
)
# quantize redondea por definición: aquí Inexact y Rounded no se atrapan.
_REDONDEO = Context(
    prec=MAX_PREC,
    rounding=_MODO_REDONDEO,
    Emax=MAX_EMAX,
    Emin=MIN_EMIN,
    traps=[InvalidOperation, Overflow],
)
# Una división inexacta con MAX_PREC agota la memoria: 28 dígitos significativos (PA-T6).
_DIVISION = Context(
    prec=28,
    rounding=_MODO_REDONDEO,
    Emax=MAX_EMAX,
    Emin=MIN_EMIN,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
_DECIMAL_LLANO = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_DIGITOS_MAXIMOS_DE_COLUMNA = 18
# Exponente admitido a la entrada: magnitud menor que 10^41 y como máximo 40 decimales (asumido, decisión del usuario, M-01 de la revisión de TKT-004).
_LIMITE_DE_EXPONENTE = 40
_LARGO_MAXIMO_DE_CADENA = 100
_BITS_MAXIMOS_DE_ENTERO = 140
_LARGO_DE_RESUMEN = 60


def _resumen(valor: object) -> str:
    """Resumen corto de la entrada para un mensaje de error.

    Un int se resume por sus bits: su repr puede tener miles de dígitos y el límite de conversión
    de CPython la rechaza con un mensaje ajeno al dominio. El resto, repr truncado a unos 60 caracteres.
    """
    if isinstance(valor, int) and not isinstance(valor, bool):
        return f"int de {valor.bit_length()} bits"
    texto = repr(valor)
    return texto if len(texto) <= _LARGO_DE_RESUMEN else f"{texto[:_LARGO_DE_RESUMEN]}…"


def _fuera_de_exponente(tipo: str, valor: object, por_magnitud: bool) -> ValueError:
    if por_magnitud:
        causa = f"la magnitud debe ser menor que 10^{_LIMITE_DE_EXPONENTE + 1}"
    else:
        causa = f"admite como máximo {_LIMITE_DE_EXPONENTE} decimales"
    return ValueError(f"{tipo} no admite {_resumen(valor)}: {causa}")


def _comprobar_exponente(valor: Decimal, tipo: str) -> None:
    exponente = valor.as_tuple().exponent
    if not isinstance(exponente, int):  # solo NaN e infinitos, ya descartados antes
        return
    adjustado = valor.adjusted()
    if adjustado > _LIMITE_DE_EXPONENTE or exponente < -_LIMITE_DE_EXPONENTE:
        # Si se cumplen las dos, se indica la magnitud: es la que el usuario ve primero.
        raise _fuera_de_exponente(tipo, valor, por_magnitud=adjustado > _LIMITE_DE_EXPONENTE)


def _viene_de_float(valor: Decimal) -> bool:
    """Huella de Decimal(float): más dígitos significativos que cualquier columna y exactamente un double.

    Los ceros finales son relleno de escala y no delatan un float: 0.5000000000000000000
    tiene 19 dígitos pero solo uno significativo.

    Es una heurística: puede rechazar un Decimal legítimo de 19 o más dígitos significativos
    que sea exactamente un double si se vuelve a envolver el `.valor` de un resultado
    (p. ej. 2⁻²⁷). Los valores leídos de PostgreSQL tienen 18 o menos.
    """
    return (
        _digitos_significativos(valor) > _DIGITOS_MAXIMOS_DE_COLUMNA
        and Decimal.from_float(float(valor)) == valor
    )


def _digitos_significativos(valor: Decimal) -> int:
    digitos = valor.as_tuple().digits
    fin = len(digitos)
    while fin > 0 and digitos[fin - 1] == 0:
        fin -= 1
    return fin


def _a_decimal(valor: object, tipo: str) -> Decimal:
    if isinstance(valor, bool):
        raise TypeError(f"{tipo} no se construye desde bool: {_resumen(valor)}")
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            raise ValueError(f"{tipo} solo admite valores finitos, y recibió {_resumen(valor)}")
        if _viene_de_float(valor):
            raise TypeError(
                f"{tipo} no admite un Decimal construido desde float ({_resumen(valor)}): "
                "constrúyalo desde una cadena"
            )
        _comprobar_exponente(valor, tipo)
        return valor
    if isinstance(valor, int):
        if valor.bit_length() > _BITS_MAXIMOS_DE_ENTERO:
            raise _fuera_de_exponente(tipo, valor, por_magnitud=True)
        convertido = Decimal(valor)
        _comprobar_exponente(convertido, tipo)
        return convertido
    if isinstance(valor, str):
        if len(valor) > _LARGO_MAXIMO_DE_CADENA:
            raise ValueError(
                f"{tipo} no admite la cadena {_resumen(valor)}: "
                f"excede {_LARGO_MAXIMO_DE_CADENA} caracteres"
            )
        if _DECIMAL_LLANO.fullmatch(valor) is None:
            raise ValueError(
                f"{tipo} no admite la cadena {_resumen(valor)}: "
                "se espera un decimal llano, como '1234.5600'"
            )
        convertido = Decimal(valor)
        _comprobar_exponente(convertido, tipo)
        return convertido
    raise TypeError(
        f"{tipo} se construye desde str, int o Decimal, no desde {type(valor).__name__}"
    )


# Cada subclase lleva el mismo decorador: sin él, la subclase tendría __dict__ y generaría
# su igualdad con otras reglas.
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
                f"{type(self).__name__} {_resumen(self.valor)} tiene más de {self._ESCALA} decimales: "
                "llame a cuantizar() antes de serializar"
            )
        en_columna = self._en_columna(en_escala)
        return format(en_columna.copy_abs() if en_columna.is_zero() else en_columna, "f")

    def _a_escala(self) -> Decimal:
        unidad = Decimal(f"1E-{self._ESCALA}")
        return self.valor.quantize(unidad, rounding=_MODO_REDONDEO, context=_REDONDEO)

    def _en_columna(self, valor: Decimal) -> Decimal:
        enteros = self._PRECISION - self._ESCALA
        if valor.copy_abs() >= Decimal(10**enteros):
            raise ValueError(
                f"{type(self).__name__} {_resumen(valor)} no cabe en NUMERIC({self._PRECISION},{self._ESCALA}): "
                f"admite hasta {enteros} dígitos enteros"
            )
        return valor


@dataclass(frozen=True, slots=True, init=False, order=True)
class Dinero(_Numero):
    """Importe: NUMERIC(18,4). Un precio unitario se guarda en NUMERIC(14,4); ver arquitectura §7.4."""

    _PRECISION: ClassVar[int] = 18
    _ESCALA: ClassVar[int] = 4

    def __mul__(self, otro: Cantidad | Porcentaje) -> Dinero:
        if not isinstance(otro, Cantidad | Porcentaje):
            return NotImplemented
        return Dinero._nuevo(_producto(self, otro))

    def __truediv__(self, otro: Dinero) -> Porcentaje:
        if type(otro) is not Dinero:
            return NotImplemented
        return _cociente(self, otro)


@dataclass(frozen=True, slots=True, init=False, order=True)
class Cantidad(_Numero):
    """Cantidad de obra o de insumo: NUMERIC(14,4)."""

    _PRECISION: ClassVar[int] = 14
    _ESCALA: ClassVar[int] = 4

    @overload
    def __mul__(self, otro: Rendimiento) -> Cantidad: ...

    @overload
    def __mul__(self, otro: Dinero) -> Dinero: ...

    def __mul__(self, otro: Rendimiento | Dinero) -> Cantidad | Dinero:
        if isinstance(otro, Rendimiento):
            return Cantidad._nuevo(_producto(self, otro))
        if isinstance(otro, Dinero):
            return Dinero._nuevo(_producto(self, otro))
        return NotImplemented

    def __truediv__(self, otro: Cantidad) -> Porcentaje:
        if type(otro) is not Cantidad:
            return NotImplemented
        return _cociente(self, otro)


@dataclass(frozen=True, slots=True, init=False, order=True)
class Rendimiento(_Numero):
    """Rendimiento de un APU: NUMERIC(18,6)."""

    _PRECISION: ClassVar[int] = 18
    _ESCALA: ClassVar[int] = 6

    def __mul__(self, otro: Cantidad) -> Cantidad:
        if not isinstance(otro, Cantidad):
            return NotImplemented
        return Cantidad._nuevo(_producto(self, otro))


@dataclass(frozen=True, slots=True, init=False, order=True)
class Porcentaje(_Numero):
    """Porcentaje con 0.050000 como 5 %: NUMERIC(9,6)."""

    _PRECISION: ClassVar[int] = 9
    _ESCALA: ClassVar[int] = 6

    def __mul__(self, otro: Dinero) -> Dinero:
        if not isinstance(otro, Dinero):
            return NotImplemented
        return Dinero._nuevo(_producto(self, otro))


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
