"""Pruebas de la comprobación de la etiqueta de origen, `tools/etiqueta_origen.py`.

TKT-062a · fila A2 · `CA-6`. Todo PR lleva exactamente una etiqueta de origen entre `human`, `human+copilot`, `agent`
y `agent+human-review`. `evaluar` cuenta las etiquetas que coinciden exactamente con una de las cuatro y devuelve
`(aceptado, mensaje)`; `main` lee `ETIQUETAS` (la lista JSON de los nombres de etiqueta del PR) y traduce el veredicto a un
código de salida: 0 acepta, 1 rechaza, 2 es entrada ausente o inválida (fallo cerrado).

Las pruebas de `evaluar` y de `main` no tocan la red, el entorno real ni el sistema de archivos: `main` recibe el entorno
por parámetro. Solo las del bloque «como proceso» lanzan el guion con el intérprete, tal como lo hace el flujo, y le pasan
un entorno armado a propósito (el actual sin `ETIQUETAS`, más `ETIQUETAS` según el caso): son las únicas que ven el
`sys.exit(main())` de la última línea y la lectura del entorno real, que la llamada directa a `main(entorno)` se salta.

Una etiqueta repetida cuenta una vez: la lista `["agent", "agent"]` tiene una etiqueta de origen, no dos, y pasa;
`["agent", "agent", "human"]` tiene dos distintas y falla diciendo 2.

Casos del plan de pruebas del diseño de TKT-062:

* TC62-01  una etiqueta de origen pasa, con otras ajenas también; `main` termina en 0 y dice cuál.
* TC62-02  ninguna falla y el mensaje nombra las cuatro, en orden.
* TC62-03  dos o más fallan, con el número y las halladas en el orden de la tupla.
* TC62-04  `ETIQUETAS` ausente, que no es JSON o que no es una lista de cadenas termina en 2.
* TC62-05  la coincidencia es exacta: mayúsculas, espacios y variantes no cuentan.

Mutantes que estas pruebas deben matar (tabla de mutación del diseño):

* `evaluar` con `!= 1` cambiado por `>= 1`: cae `test_tkt062_ca06_esc03_dos_etiquetas_fallan_y_lo_dicen`.
* `evaluar` comparando con `.lower()` o `.strip()`: cae `test_tkt062_ca06_esc02_variantes_de_la_etiqueta_no_cuentan`.
* `main` que con JSON inválido devuelve 0: cae `test_tkt062_ca06_esc02_entrada_ausente_o_invalida_falla_cerrado`.
* `sys.exit(main())` cambiado por `main()`: caen las pruebas «como proceso» de rechazo, porque el guion termina siempre en 0.
* `entorno = os.environ` cambiado por `entorno = {}`: cae la prueba «como proceso» de una etiqueta válida, porque el guion
  nunca ve `ETIQUETAS`.
* Contar las etiquetas de origen con repeticiones (`sum` en lugar de un conjunto): cae
  `test_tkt062_ca06_esc01_una_etiqueta_repetida_cuenta_una_vez`.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_etiqueta_origen -v
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import unittest

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

GUION = os.path.join(HERRAMIENTAS, "etiqueta_origen.py")

# ---------------------------------------------------------------------------------------------------------
# Datos de ejemplo: los mensajes exactos del diseño
# ---------------------------------------------------------------------------------------------------------

LAS_CUATRO = ("human", "human+copilot", "agent", "agent+human-review")

MENSAJE_SIN_ETIQUETA = (
    "El PR no tiene etiqueta de origen. "
    "Añade exactamente una de: human, human+copilot, agent, agent+human-review."
)
MENSAJE_DOS_ETIQUETAS = (
    "El PR tiene 2 etiquetas de origen (human, agent); "
    "debe haber exactamente una de: human, human+copilot, agent, agent+human-review."
)
MENSAJE_ENTRADA_INVALIDA = "::error::ETIQUETAS ausente o inválida"


class PruebaBase(unittest.TestCase):
    """Importa el módulo bajo prueba en cada caso, para que un módulo ausente rompa cada caso por separado."""

    def etiqueta(self):  # noqa: ANN201
        try:
            return importlib.import_module("etiqueta_origen")
        except ModuleNotFoundError as error:
            if error.name != "etiqueta_origen":
                raise
            self.fail("falta tools/etiqueta_origen.py: el módulo bajo prueba todavía no existe")

    def ejecutar_main(self, entorno: dict[str, str]) -> tuple[int, str]:
        """Corre `main(entorno)` y devuelve `(código, salida estándar)`."""
        modulo = self.etiqueta()
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = modulo.main(entorno)
        return codigo, salida.getvalue().strip()

    def ejecutar_con(self, etiquetas: list[str]) -> tuple[int, str]:
        return self.ejecutar_main({"ETIQUETAS": json.dumps(etiquetas)})


class PruebasDeLaEtiquetaDeOrigen(PruebaBase):
    # --- TC62-01 · feliz ---------------------------------------------------------------------------------

    def test_tkt062_ca06_esc01_exactamente_una_etiqueta_pasa(self) -> None:
        """TKT-062 CA-6 esc. 1 — una etiqueta de origen pasa, sola o junto a etiquetas ajenas, y el mensaje dice cuál."""
        modulo = self.etiqueta()
        self.assertEqual(modulo.ETIQUETAS_DE_ORIGEN, LAS_CUATRO)
        self.assertEqual(modulo.evaluar(["agent"]), (True, "Etiqueta de origen: agent."))
        self.assertEqual(
            modulo.evaluar(["agent", "dependencies"]), (True, "Etiqueta de origen: agent.")
        )
        for etiqueta in LAS_CUATRO:
            with self.subTest(etiqueta=etiqueta):
                self.assertEqual(
                    modulo.evaluar([etiqueta]), (True, f"Etiqueta de origen: {etiqueta}.")
                )
        codigo, salida = self.ejecutar_con(["agent", "dependencies"])
        self.assertEqual(codigo, 0)
        self.assertEqual(salida, "Etiqueta de origen: agent.")

    # --- TC62-02 · rechazo: ninguna ----------------------------------------------------------------------

    def test_tkt062_ca06_esc02_sin_etiqueta_falla_y_nombra_las_cuatro(self) -> None:
        """TKT-062 CA-6 esc. 2 — sin etiqueta de origen falla con código 1 y el mensaje nombra las cuatro, en orden."""
        modulo = self.etiqueta()
        for etiquetas in ([], ["dependencies"]):
            with self.subTest(etiquetas=etiquetas):
                self.assertEqual(modulo.evaluar(etiquetas), (False, MENSAJE_SIN_ETIQUETA))
                codigo, salida = self.ejecutar_con(etiquetas)
                self.assertEqual(codigo, 1)
                self.assertEqual(salida, "::error::" + MENSAJE_SIN_ETIQUETA)

    # --- TC62-03 · rechazo: dos o más --------------------------------------------------------------------

    def test_tkt062_ca06_esc03_dos_etiquetas_fallan_y_lo_dicen(self) -> None:
        """TKT-062 CA-6 esc. 3 — dos etiquetas de origen fallan con código 1, el número y las halladas en el orden de la tupla."""
        modulo = self.etiqueta()
        self.assertEqual(modulo.evaluar(["agent", "human"]), (False, MENSAJE_DOS_ETIQUETAS))
        # El orden del mensaje es el de la tupla, no el de llegada.
        self.assertEqual(modulo.evaluar(["human", "agent"]), (False, MENSAJE_DOS_ETIQUETAS))
        codigo, salida = self.ejecutar_con(["agent", "human"])
        self.assertEqual(codigo, 1)
        self.assertEqual(salida, "::error::" + MENSAJE_DOS_ETIQUETAS)
        self.assertIn("exactamente una", salida)

    def test_tkt062_ca06_esc03_tres_etiquetas_dan_el_numero_y_el_orden_de_la_tupla(self) -> None:
        """TKT-062 CA-6 esc. 3 — con tres etiquetas de origen el mensaje dice 3 y las lista en el orden de la tupla, ignorando las ajenas."""
        modulo = self.etiqueta()
        aceptado, mensaje = modulo.evaluar(["agent+human-review", "bug", "human", "agent"])
        self.assertFalse(aceptado)
        self.assertEqual(
            mensaje,
            "El PR tiene 3 etiquetas de origen (human, agent, agent+human-review); "
            "debe haber exactamente una de: human, human+copilot, agent, agent+human-review.",
        )

    # --- TC62-04 · rechazo: entrada ausente o inválida ---------------------------------------------------

    def test_tkt062_ca06_esc02_entrada_ausente_o_invalida_falla_cerrado(self) -> None:
        """TKT-062 CA-6 esc. 2 — ETIQUETAS ausente, que no es JSON o que no es una lista de cadenas termina en 2 (fallo cerrado)."""
        entradas = {
            "ausente": {},
            "no es JSON": {"ETIQUETAS": "no-json"},
            "objeto JSON": {"ETIQUETAS": '{"a":1}'},
            "lista de números": {"ETIQUETAS": "[1]"},
            "lista mixta": {"ETIQUETAS": '["agent", 1]'},
            "cadena JSON": {"ETIQUETAS": '"agent"'},
            "vacía": {"ETIQUETAS": ""},
        }
        for descripcion, entorno in entradas.items():
            with self.subTest(entrada=descripcion):
                codigo, salida = self.ejecutar_main(entorno)
                self.assertEqual(codigo, 2)
                self.assertEqual(salida, MENSAJE_ENTRADA_INVALIDA)

    def test_tkt062_ca06_esc02_entrada_con_anidamiento_desmesurado_falla_cerrado(self) -> None:
        """TKT-062 CA-6 esc. 2 — un `ETIQUETAS` de 100000 corchetes abiertos desborda la recursión del analizador de JSON: termina en 2
        con el mensaje del fallo cerrado, no con un traceback ni con la `RecursionError` sin capturar."""
        try:
            codigo, salida = self.ejecutar_main({"ETIQUETAS": "[" * 100000})
        except RecursionError:
            self.fail("`main` dejó escapar RecursionError: un JSON demasiado anidado debe terminar en 2, no en un traceback")
        self.assertEqual(codigo, 2)
        self.assertEqual(salida, MENSAJE_ENTRADA_INVALIDA)

    # --- TC62-05 · rechazo: coincidencia exacta ----------------------------------------------------------

    def test_tkt062_ca06_esc02_variantes_de_la_etiqueta_no_cuentan(self) -> None:
        """TKT-062 CA-6 esc. 2 — mayúsculas, espacios y variantes no cuentan como etiqueta de origen: sigue sin haber ninguna."""
        modulo = self.etiqueta()
        for variante in ("Agent", "agent ", " agent", "AGENT", "agente", "Human+Copilot"):
            with self.subTest(variante=variante):
                self.assertEqual(modulo.evaluar([variante]), (False, MENSAJE_SIN_ETIQUETA))
                codigo, salida = self.ejecutar_con([variante])
                self.assertEqual(codigo, 1)
                self.assertEqual(salida, "::error::" + MENSAJE_SIN_ETIQUETA)

    def test_tkt062_ca06_esc02_una_variante_junto_a_una_valida_no_hace_dos(self) -> None:
        """TKT-062 CA-6 esc. 2 — una variante inexacta no se suma a una etiqueta válida: sigue habiendo exactamente una."""
        modulo = self.etiqueta()
        self.assertEqual(modulo.evaluar(["agent", "Human"]), (True, "Etiqueta de origen: agent."))

    # --- TC62-03 · las repetidas cuentan una vez ---------------------------------------------------------

    def test_tkt062_ca06_esc01_una_etiqueta_repetida_cuenta_una_vez(self) -> None:
        """TKT-062 CA-6 esc. 1 — la misma etiqueta de origen dos veces es una etiqueta, no dos: pasa con el mismo mensaje."""
        modulo = self.etiqueta()
        self.assertEqual(modulo.evaluar(["agent", "agent"]), (True, "Etiqueta de origen: agent."))
        codigo, salida = self.ejecutar_con(["agent", "agent"])
        self.assertEqual(codigo, 0)
        self.assertEqual(salida, "Etiqueta de origen: agent.")

    def test_tkt062_ca06_esc03_las_repetidas_no_inflan_el_numero_de_distintas(self) -> None:
        """TKT-062 CA-6 esc. 3 — `agent` repetida más `human` son dos etiquetas distintas: falla diciendo 2, no 3."""
        modulo = self.etiqueta()
        self.assertEqual(
            modulo.evaluar(["agent", "agent", "human"]), (False, MENSAJE_DOS_ETIQUETAS)
        )
        codigo, salida = self.ejecutar_con(["agent", "agent", "human"])
        self.assertEqual(codigo, 1)
        self.assertEqual(salida, "::error::" + MENSAJE_DOS_ETIQUETAS)


class PruebasDelGuionComoProceso(unittest.TestCase):
    """Lanza `tools/etiqueta_origen.py` con el intérprete, como lo hace el paso del flujo. Cubre lo que `main(entorno)` no ve:
    que la última línea llama a `sys.exit(main())` y que sin parámetro lee el entorno real."""

    def lanzar(self, etiquetas: str | None) -> subprocess.CompletedProcess[str]:
        """El guion con el entorno actual sin `ETIQUETAS` más `ETIQUETAS=etiquetas`, o sin la variable si es `None`.

        La codificación se fija en los dos extremos para no depender del intérprete padre: el hijo escribe en UTF-8 con
        `-X utf8` (`-I` ignora `PYTHONUTF8` y `PYTHONIOENCODING`, así que una opción de línea de comandos es lo único que
        vale) y el padre lo decodifica con `encoding="utf-8"`; sin esto, las tildes de los mensajes se corrompen o fallan
        cuando `PYTHONUTF8` del padre difiere de la página de códigos con que el hijo abre su salida."""
        entorno = {clave: valor for clave, valor in os.environ.items() if clave != "ETIQUETAS"}
        if etiquetas is not None:
            entorno["ETIQUETAS"] = etiquetas
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-I", GUION],
            env=entorno,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            check=False,
        )

    def test_tkt062_ca06_esc01_como_proceso_una_etiqueta_termina_en_0_y_dice_cual(self) -> None:
        """TKT-062 CA-6 esc. 1 — como proceso, `ETIQUETAS='["agent"]'` termina en 0 y escribe exactamente «Etiqueta de origen: agent.»."""
        resultado = self.lanzar('["agent"]')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout, "Etiqueta de origen: agent.\n")
        self.assertEqual(resultado.stderr, "")

    def test_tkt062_ca06_esc02_como_proceso_sin_etiquetas_termina_en_1_con_el_mensaje_de_ninguna(self) -> None:
        """TKT-062 CA-6 esc. 2 — como proceso, `ETIQUETAS='[]'` termina en 1 y escribe `::error::` con el mensaje de «ninguna»."""
        resultado = self.lanzar("[]")
        self.assertEqual(resultado.returncode, 1, resultado.stderr)
        self.assertEqual(resultado.stdout, "::error::" + MENSAJE_SIN_ETIQUETA + "\n")
        self.assertEqual(resultado.stderr, "")

    def test_tkt062_ca06_esc02_como_proceso_sin_la_variable_termina_en_2_cerrado(self) -> None:
        """TKT-062 CA-6 esc. 2 — como proceso, sin `ETIQUETAS` en el entorno termina en 2 con «ETIQUETAS ausente o inválida»."""
        resultado = self.lanzar(None)
        self.assertEqual(resultado.returncode, 2, resultado.stderr)
        self.assertEqual(resultado.stdout, MENSAJE_ENTRADA_INVALIDA + "\n")
        self.assertEqual(resultado.stderr, "")

    def test_tkt062_ca06_esc03_como_proceso_dos_etiquetas_terminan_en_1(self) -> None:
        """TKT-062 CA-6 esc. 3 — como proceso, dos etiquetas de origen terminan en 1 y el mensaje dice 2 y las nombra en el orden de la tupla."""
        resultado = self.lanzar('["agent", "human"]')
        self.assertEqual(resultado.returncode, 1, resultado.stderr)
        self.assertEqual(resultado.stdout, "::error::" + MENSAJE_DOS_ETIQUETAS + "\n")
        self.assertEqual(resultado.stderr, "")


if __name__ == "__main__":
    unittest.main()
