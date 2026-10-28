"""Pruebas de la comprobación de codificación de `tools/verificar_docs.py`.

TKT-001 · CA-7. Los documentos (`*.md` y `llms.txt`) se guardan en UTF-8 sin BOM
y los scripts `.ps1` en UTF-8 con BOM: sin el BOM, Windows PowerShell 5.1
corrompe los acentos del script (aprendizaje del 2026-10-01).

Excepción acordada al convenio de pruebas: `tools/` es un directorio sin
dependencias, así que estas pruebas usan `unittest` y no pytest. El pipeline
`.github/workflows/ci.yml` ya las corre: el trabajo `herramientas` ejecuta la suite de
`tools/` y el trabajo `documentacion` ejecuta `verificar_docs.py`, que aplica esta comprobación.

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

# El BOM de UTF-8 se escribe literal para que la prueba no dependa de la
# constante `verificar_docs.BOM`, que es parte de lo que se prueba.
BOM_UTF8 = b"\xef\xbb\xbf"
CUERPO = "Contenido con acentos: ñ, á, é.\n".encode()


class PruebasCodificacion(unittest.TestCase):
    """Comprobación de BOM en documentos y en scripts de PowerShell."""

    def setUp(self) -> None:
        verificar_docs.problemas.clear()
        self.addCleanup(verificar_docs.problemas.clear)
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.raiz = directorio.name

    def escribir(self, *partes: str, con_bom: bool) -> str:
        """Crea un archivo bajo la raíz temporal y devuelve su ruta absoluta."""
        ruta = os.path.join(self.raiz, *partes)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "wb") as f:
            f.write((BOM_UTF8 if con_bom else b"") + CUERPO)
        return ruta

    def test_tkt001_ca7_arbol_correcto_sin_problemas(self) -> None:
        """TKT-001 CA-7 — un árbol correcto no genera problemas y cuenta sus 3 archivos."""
        self.escribir("docs", "nota.md", con_bom=False)
        self.escribir("llms.txt", con_bom=False)
        self.escribir(".claude", "hooks", "h.ps1", con_bom=True)

        revisados = verificar_docs.verificar_codificacion(self.raiz)

        self.assertEqual(revisados, 3)
        self.assertEqual(verificar_docs.problemas, [])

    def test_tkt001_ca7_esc01_markdown_con_bom_se_detecta(self) -> None:
        """TKT-001 CA-7 esc. 1 — un `.md` con BOM se rechaza con su ruta y el motivo."""
        self.escribir("docs", "nota.md", con_bom=True)

        verificar_docs.verificar_codificacion(self.raiz)

        ruta = os.path.join("docs", "nota.md")
        self.assertEqual(
            verificar_docs.problemas,
            [f"Codificación · {ruta} empieza con BOM; "
             "los documentos se guardan en UTF-8 sin BOM"],
        )

    def test_tkt001_ca7_esc02_powershell_sin_bom_se_detecta(self) -> None:
        """TKT-001 CA-7 esc. 2 — un `.ps1` sin BOM se rechaza con su ruta y el motivo."""
        self.escribir(".claude", "hooks", "h.ps1", con_bom=False)

        verificar_docs.verificar_codificacion(self.raiz)

        ruta = os.path.join(".claude", "hooks", "h.ps1")
        self.assertEqual(
            verificar_docs.problemas,
            [f"Codificación · {ruta} no empieza con BOM; "
             "los scripts .ps1 se guardan en UTF-8 con BOM"],
        )

    def test_tkt001_ca7_directorios_excluidos_no_se_revisan(self) -> None:
        """TKT-001 CA-7 — `node_modules` y `.venv` se podan: ni se revisan ni se cuentan."""
        self.escribir("node_modules", ".bin", "x.ps1", con_bom=False)
        self.escribir(".venv", "x.md", con_bom=True)

        revisados = verificar_docs.verificar_codificacion(self.raiz)

        self.assertEqual(verificar_docs.problemas, [])
        self.assertEqual(revisados, 0)

    def test_tkt001_ca7_extension_en_mayusculas_se_revisa(self) -> None:
        """TKT-001 CA-7 — la extensión se compara en minúsculas: `NOTA.MD` con BOM se rechaza."""
        self.escribir("docs", "NOTA.MD", con_bom=True)

        verificar_docs.verificar_codificacion(self.raiz)

        ruta = os.path.join("docs", "NOTA.MD")
        self.assertEqual(len(verificar_docs.problemas), 1)
        self.assertIn(ruta, verificar_docs.problemas[0])
        self.assertIn("empieza con BOM", verificar_docs.problemas[0])

    def test_tkt001_ca7_constante_bom_son_los_tres_bytes_de_utf8(self) -> None:
        """TKT-001 CA-7 — la constante `BOM` del verificador es `EF BB BF`."""
        self.assertEqual(verificar_docs.BOM, BOM_UTF8)


if __name__ == "__main__":
    unittest.main()
