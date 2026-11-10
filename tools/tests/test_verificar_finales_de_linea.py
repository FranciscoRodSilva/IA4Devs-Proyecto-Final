"""Pruebas de la comprobación de finales de línea de `tools/verificar_docs.py`.

Propuesta de `meta-sdd` tras TKT-017 (raíz `herramienta` de `sdd/_evolucion.md`, once tickets): la
copia de trabajo de Windows queda en CRLF, los agentes escriben con uno u otro y nadie lo
comprobaba. Lo que importa es lo que el índice de Git guarda, y `.gitattributes` pide LF. La
comprobación lee `git ls-files --eol`; estas pruebas le pasan esa salida ya escrita, para no
depender de un repositorio ni de la configuración de la máquina.

Ejecución, desde la raíz del repositorio:

    python -m unittest discover -s tools/tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

import verificar_docs  # noqa: E402


def linea(indice: str, trabajo: str, ruta: str) -> str:
    """Una línea con el formato de `git ls-files --eol`."""
    return f"{indice}    {trabajo}  attr/text=auto eol=lf \t{ruta}"


class PruebasFinalesDeLinea(unittest.TestCase):
    """El índice debe guardar LF; la copia de trabajo en CRLF solo se avisa."""

    def setUp(self) -> None:
        verificar_docs.problemas.clear()
        verificar_docs.avisos.clear()
        self.addCleanup(verificar_docs.problemas.clear)
        self.addCleanup(verificar_docs.avisos.clear)

    def verificar(self, *lineas: str) -> int:
        return verificar_docs.verificar_finales_de_linea(".", "\n".join(lineas) + "\n")

    def test_tkt017_indice_en_lf_no_da_problemas_y_se_cuenta(self) -> None:
        """Un archivo versionado en LF, en una carpeta y con extensión revisadas, pasa y se cuenta."""
        revisados = self.verificar(
            linea("i/lf", "w/lf", "backend/cimenta/a.py"),
            linea("i/lf", "w/lf", "sdd/tickets/tkt-017/impl.md"),
        )

        self.assertEqual(revisados, 2)
        self.assertEqual(verificar_docs.problemas, [])
        self.assertEqual(verificar_docs.avisos, [])

    def test_tkt017_indice_en_crlf_se_rechaza_con_su_ruta(self) -> None:
        """Un archivo que el índice guarda en CRLF es problema, y el mensaje nombra la ruta y el motivo."""
        self.verificar(linea("i/crlf", "w/crlf", "docs/adr/nuevo.md"))

        self.assertEqual(
            verificar_docs.problemas,
            ["Finales de línea · docs/adr/nuevo.md se guarda en el índice de Git con crlf; "
             "el repositorio guarda LF (.gitattributes)"],
        )

    def test_tkt017_indice_mezclado_se_rechaza(self) -> None:
        """Un archivo con mezcla de finales de línea en el índice también es problema."""
        self.verificar(linea("i/mixed", "w/mixed", ".claude/agents/x.md"))

        self.assertEqual(len(verificar_docs.problemas), 1)
        self.assertIn("mixed", verificar_docs.problemas[0])
        self.assertIn(".claude/agents/x.md", verificar_docs.problemas[0])

    def test_tkt017_copia_de_trabajo_en_crlf_solo_se_avisa(self) -> None:
        """Con LF en el índice, la copia en CRLF no es problema: Git la normaliza al commitear."""
        self.verificar(
            linea("i/lf", "w/crlf", "tools/a.py"),
            linea("i/lf", "w/mixed", "backend/b.py"),
            linea("i/lf", "w/lf", "backend/c.py"),
        )

        self.assertEqual(verificar_docs.problemas, [])
        self.assertEqual(
            verificar_docs.avisos,
            ["Finales de línea · 2 archivos tienen CRLF en la copia de trabajo y LF en el índice; "
             "Git los normaliza al commitear"],
        )

    def test_tkt017_carpetas_extensiones_y_excluidos_no_se_revisan(self) -> None:
        """Fuera de las cinco carpetas, con otra extensión o bajo un directorio excluido, no se mira."""
        revisados = self.verificar(
            linea("i/crlf", "w/crlf", "frontend/src/a.json"),
            linea("i/crlf", "w/crlf", "backend/datos.csv"),
            linea("i/crlf", "w/crlf", "backend/.venv/x.py"),
            linea("i/none", "w/none", "backend/cimenta/__init__.py"),
            linea("i/-text", "w/-text", "backend/.coverage"),
        )

        self.assertEqual(revisados, 1)  # solo `__init__.py`: carpeta y extensión revisadas
        self.assertEqual(verificar_docs.problemas, [])

    def test_tkt017_sin_git_se_avisa_y_no_se_comprueba(self) -> None:
        """Si no hay repositorio de Git en la raíz, avisa y devuelve cero sin fallar."""
        with tempfile.TemporaryDirectory() as raiz:
            revisados = verificar_docs.verificar_finales_de_linea(raiz)

        self.assertEqual(revisados, 0)
        self.assertEqual(verificar_docs.problemas, [])
        self.assertEqual(
            verificar_docs.avisos,
            ["Finales de línea · no se pudo ejecutar git: se omite la comprobación"],
        )


if __name__ == "__main__":
    unittest.main()
