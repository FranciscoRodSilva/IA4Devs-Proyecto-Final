"""Ayudantes compartidos por las pruebas de definición de `tools/tests` (TKT-009b).

`test_definicion_ci.py` y `test_definicion_dependabot.py` comprueban texto YAML con mutantes: toman un texto válido,
lo estropean de una forma concreta y exigen que la comprobación se ponga en rojo y por la razón esperada. Lo que
ambos módulos hacían igual vive aquí, una sola vez.

* `_sangria`  columnas de sangría de una línea.
* `sustituir`  aplica un mutante de texto exactamente una vez.
* `exigir_rojo` y `exigir_rojo_en_todos`  exigen que la comprobación detecte el mutante.

Una comprobación recibe la entrada ya preparada y devuelve la lista de problemas que encuentra. Si la entrada del
mutante es texto y la comprobación trabaja sobre otra forma (por ejemplo, el texto dividido en trabajos), el módulo
que llama pasa `preparar`, que convierte el texto en esa forma antes de comprobar.
"""

from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


def sustituir(texto: str, viejo: str, nuevo: str) -> str:
    """Mutante sobre el texto entero: cambia `viejo` por `nuevo` exactamente una vez, o falla.

    Un mutante que no se puede aplicar, o que no cambia nada, daría un verde engañoso.
    """
    if texto.count(viejo) != 1:
        raise AssertionError(
            f"el mutante no es aplicable: {viejo!r} aparece {texto.count(viejo)} veces en el texto"
        )
    mutante = texto.replace(viejo, nuevo)
    if mutante == texto:
        raise AssertionError(f"el mutante no cambia nada: {viejo!r} y {nuevo!r} son iguales")
    return mutante


def exigir_rojo(
    caso: unittest.TestCase,
    comprobacion: Callable[..., list[str]],
    entrada: Any,
    fragmento: str | None = None,
    *,
    preparar: Callable[[Any], Any] | None = None,
) -> list[str]:
    """El mutante `entrada` debe poner `comprobacion` en rojo y, si se da `fragmento`, por la razón esperada: algún problema lo menciona."""
    problemas = comprobacion(entrada if preparar is None else preparar(entrada))
    caso.assertNotEqual(
        problemas, [], "el mutante debía poner la comprobación en rojo y pasó en verde"
    )
    if fragmento is not None:
        caso.assertTrue(
            any(fragmento in problema for problema in problemas),
            f"el rojo no es por la razón esperada: ningún problema menciona {fragmento!r}: {problemas}",
        )
    return problemas


def exigir_rojo_en_todos(
    caso: unittest.TestCase,
    comprobacion: Callable[..., list[str]],
    casos: dict,
    fragmento: str | None = None,
    fragmentos: dict[str, str] | None = None,
    *,
    preparar: Callable[[Any], Any] | None = None,
) -> None:
    """Corre `exigir_rojo` por cada mutante de `casos`. El fragmento esperado sale, por orden, de `fragmentos[descripcion]`,
    del `(entrada, fragmento)` del propio caso o del `fragmento` común. `fragmentos` no puede nombrar un mutante que no existe."""
    fragmentos = fragmentos or {}
    caso.assertEqual(set(fragmentos) - set(casos), set(), "fragmentos para mutantes que no existen")
    for descripcion, valor in casos.items():
        entrada, propio = valor if isinstance(valor, tuple) else (valor, fragmento)
        with caso.subTest(mutante=descripcion):
            exigir_rojo(
                caso, comprobacion, entrada, fragmentos.get(descripcion, propio), preparar=preparar
            )
