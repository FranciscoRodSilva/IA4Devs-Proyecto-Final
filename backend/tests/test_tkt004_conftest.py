"""Revisión estática del arnés para los tipos base (TKT-004, fila 1): TC-13.

Sin Docker. Los tests de los tipos y del linter corren sin PostgreSQL mientras ninguna
fixture de `conftest.py` sea `autouse`: una que lo fuera arrancaría el contenedor en cada
prueba, también en las que no lo necesitan (CA-13 esc. 2).
"""

import ast
from pathlib import Path

CONFTEST = Path(__file__).resolve().parent / "conftest.py"


def _es_fixture(decorador: ast.expr) -> bool:
    objetivo = decorador.func if isinstance(decorador, ast.Call) else decorador
    if isinstance(objetivo, ast.Attribute):
        return objetivo.attr == "fixture"
    return isinstance(objetivo, ast.Name) and objetivo.id == "fixture"


def _lleva_autouse(decorador: ast.expr) -> bool:
    return isinstance(decorador, ast.Call) and any(
        palabra.arg == "autouse" for palabra in decorador.keywords
    )


def test_tkt004_ca13_conftest_sin_fixtures_autouse() -> None:
    """TC-13 · CA-13 esc. 2 — ninguna fixture de conftest.py declara autouse."""
    arbol = ast.parse(CONFTEST.read_text(encoding="utf-8"), filename=str(CONFTEST))
    fixtures = [
        (nodo.name, decorador)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef)
        for decorador in nodo.decorator_list
        if _es_fixture(decorador)
    ]

    assert fixtures, "no se encontró ninguna fixture en conftest.py: la revisión estaría vacía"
    con_autouse = sorted(nombre for nombre, decorador in fixtures if _lleva_autouse(decorador))
    assert con_autouse == [], f"fixtures con autouse en conftest.py: {con_autouse}"
