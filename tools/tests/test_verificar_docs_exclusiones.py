"""Pruebas de los directorios que `tools/verificar_docs.py` no recorre.

TKT-008b · fila 16 · TC-R5. Playwright escribe archivos `.md` en
`frontend/test-results/` y `frontend/playwright-report/` cuando una prueba
falla. Si el verificador los recorriera, trataría un volcado de error como
documentación y comprobaría sus enlaces, sus identificadores y su codificación.

`EXCLUIR` se lee con `ast` y no importando el módulo: la prueba comprueba el
texto de la constante, sin ejecutar nada del verificador.

Ejecución, desde la raíz del repositorio:

    python -m unittest discover -s tools/tests -v
"""
from __future__ import annotations

import ast
import os
import unittest

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFICADOR = os.path.join(HERRAMIENTAS, "verificar_docs.py")


def leer_excluir() -> set[str]:
    """Devuelve el valor literal de la asignación `EXCLUIR` del verificador."""
    with open(VERIFICADOR, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), filename=VERIFICADOR)
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign):
            nombres = [t.id for t in nodo.targets if isinstance(t, ast.Name)]
            if "EXCLUIR" in nombres:
                return set(ast.literal_eval(nodo.value))
        elif (
            isinstance(nodo, ast.AnnAssign)
            and isinstance(nodo.target, ast.Name)
            and nodo.target.id == "EXCLUIR"
            and nodo.value is not None
        ):
            return set(ast.literal_eval(nodo.value))
    raise AssertionError("verificar_docs.py no asigna EXCLUIR en el nivel del módulo")


class PruebasExclusiones(unittest.TestCase):
    """Directorios que el verificador no debe recorrer."""

    def test_excluye_los_artefactos_de_playwright(self) -> None:
        """TKT-008b TC-R5 · CA-R4 — `test-results` y `playwright-report` no se recorren."""
        excluidos = leer_excluir()
        faltan = {"test-results", "playwright-report"} - excluidos
        self.assertEqual(faltan, set(), f"EXCLUIR no contiene {sorted(faltan)}; contiene {sorted(excluidos)}")

    def test_conserva_las_exclusiones_anteriores(self) -> None:
        """TKT-008b TC-R5 · CA-R4 — añadir los de Playwright no quita los que ya estaban."""
        excluidos = leer_excluir()
        previos = {"node_modules", ".git", ".venv", "dist", "Doc de contexto"}
        faltan = previos - excluidos
        self.assertEqual(faltan, set(), f"EXCLUIR perdió {sorted(faltan)}; contiene {sorted(excluidos)}")


EXTRACTOR = os.path.join(HERRAMIENTAS, "extraer_mermaid.py")


def leer_excluir_de(ruta: str) -> set[str]:
    """Devuelve el valor literal de `EXCLUIR` en el archivo `ruta`, leído con `ast` sin importarlo."""
    with open(ruta, encoding="utf-8") as f:
        arbol = ast.parse(f.read(), filename=ruta)
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EXCLUIR" for t in nodo.targets):
            return set(ast.literal_eval(nodo.value))
    raise AssertionError(f"{os.path.basename(ruta)} no asigna EXCLUIR en el nivel del módulo")


class PruebasExclusionesDelExtractor(unittest.TestCase):
    """TKT-008b · ciclo de corrección 1 · F304. `extraer_mermaid.py` recorre el árbol como `verificar_docs.py`."""

    def test_el_extractor_excluye_los_artefactos_de_playwright_y_conserva_los_anteriores(self) -> None:
        """TKT-008b TC-R318 · CA-R4 — `test-results` y `playwright-report` no se recorren y lo anterior sigue."""
        excluidos = leer_excluir_de(EXTRACTOR)
        esperados = {"test-results", "playwright-report", "node_modules", ".git", ".venv", "dist", "Doc de contexto"}
        faltan = esperados - excluidos
        self.assertEqual(faltan, set(), f"EXCLUIR de extraer_mermaid.py no contiene {sorted(faltan)}; contiene {sorted(excluidos)}")

    def test_el_extractor_y_el_verificador_excluyen_lo_mismo(self) -> None:
        """TKT-008b TC-R318 · CA-R4 — las dos herramientas no divergen: lo que una salta, la otra también."""
        self.assertEqual(leer_excluir_de(EXTRACTOR), leer_excluir_de(VERIFICADOR))


if __name__ == "__main__":
    unittest.main()
