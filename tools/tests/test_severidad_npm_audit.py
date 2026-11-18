"""Pruebas del filtro de severidad de `npm audit`, `tools/severidad_npm_audit.py`.

RNF-08, excepción documentada de `picomatch` (2026-11-18). `npm audit --audit-level=high` falla por `picomatch`
(`GHSA-fc5q-39xc-vjpf`), que no tiene versión corregida. El filtro lee el informe de `npm audit --json` (formato
`auditReportVersion: 2`) y falla ante cualquier aviso `high`, `critical` o de severidad desconocida, salvo los avisos
aceptados en la tabla `EXCEPCIONES` del propio script, cada uno por su `GHSA` exacto y con una fecha de revisión.
Pasada esa fecha la excepción deja de valer y el filtro vuelve a fallar. Un paquete que solo depende de otro (su `via`
es una cadena) sigue a su aviso raíz.

Ninguna prueba toca la red ni el reloj: `fecha_de_hoy` se sustituye en el módulo y, salvo las que comprueban la tabla
real, la tabla `EXCEPCIONES` también.

Casos, cada uno con prefijo `test_npm_NN_`:

* 01  Informe sin vulnerabilidades: 0.
* 02  Un aviso alto sin excepción: 1.
* 03  El aviso aceptado y vigente: 0, con el paquete dependiente excusado.
* 04  La misma excepción caducada: 1.
* 05  Un aviso alto aceptado junto a otro alto distinto: 1.
* 06  Severidad desconocida, crítica y moderada.
* 07  Informe ausente o ilegible: 2.
* 08  Una excepción que ya no aparece se informa y no falla.
* 09  Informe real reducido de `npm audit --json`: sin la excepción falla, con ella pasa y vencida vuelve a fallar.
* 10  La excepción es por `GHSA` exacto y por la severidad aceptada, nunca por paquete.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_severidad_npm_audit -v
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

GHSA_ACEPTADO = "GHSA-aaaa-bbbb-cccc"
GHSA_OTRO_ALTO = "GHSA-cccc-dddd-eeee"
GHSA_MEDIO = "GHSA-eeee-ffff-gggg"
GHSA_REAL = "GHSA-fc5q-39xc-vjpf"

HOY = date(2026, 11, 18)
REVISION = date(2026, 12, 18)
SUFIJO_QUE_FALLA = "→ falla el pipeline (RNF-08)"

# Un informe REAL de `npm audit --json` (frontend/, 2026-11-18), reducido a los seis paquetes que importan: la raíz
# `picomatch` (alta, GHSA-fc5q-39xc-vjpf, sin versión corregida), los cuatro paquetes que dependen de ella por cadenas
# y `minimatch`, una raíz moderada. Es un fragmento literal: los campos son los que escribe npm.
INFORME_REAL_REDUCIDO = """
{
  "auditReportVersion": 2,
  "vulnerabilities": {
    "picomatch": {
      "name": "picomatch",
      "severity": "high",
      "isDirect": false,
      "via": [
        {
          "source": 1247710,
          "name": "picomatch",
          "dependency": "picomatch",
          "title": "picomatch vulnerable to ReDoS through single-branch repeated extglobs",
          "url": "https://github.com/advisories/GHSA-fc5q-39xc-vjpf",
          "severity": "high",
          "cwe": ["CWE-1333"],
          "cvss": {"score": 7.5, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"},
          "range": "<=4.0.7"
        }
      ],
      "effects": ["@dotenvx/dotenvx", "fdir", "micromatch", "tinyglobby", "vite", "vitest"],
      "range": "*",
      "nodes": ["node_modules/micromatch/node_modules/picomatch", "node_modules/picomatch"],
      "fixAvailable": {"name": "vite", "version": "6.2.7", "isSemVerMajor": true}
    },
    "fdir": {
      "name": "fdir",
      "severity": "high",
      "isDirect": false,
      "via": ["picomatch"],
      "effects": ["@dotenvx/dotenvx", "tinyglobby"],
      "range": ">=5.2.1",
      "nodes": ["node_modules/fdir"],
      "fixAvailable": {"name": "vite", "version": "6.2.7", "isSemVerMajor": true}
    },
    "tinyglobby": {
      "name": "tinyglobby",
      "severity": "high",
      "isDirect": false,
      "via": ["fdir", "picomatch"],
      "effects": ["@typescript-eslint/typescript-estree", "vite", "vitest"],
      "range": "*",
      "nodes": ["node_modules/tinyglobby"],
      "fixAvailable": {"name": "vite", "version": "6.2.7", "isSemVerMajor": true}
    },
    "vite": {
      "name": "vite",
      "severity": "high",
      "isDirect": true,
      "via": ["picomatch", "tinyglobby"],
      "effects": ["@vitejs/plugin-react", "vitest"],
      "range": ">=6.3.0-beta.0",
      "nodes": ["node_modules/vite"],
      "fixAvailable": {"name": "vite", "version": "6.2.7", "isSemVerMajor": true}
    },
    "vitest": {
      "name": "vitest",
      "severity": "high",
      "isDirect": true,
      "via": ["picomatch", "tinyglobby", "vite"],
      "effects": [],
      "range": ">=3.1.2",
      "nodes": ["node_modules/vitest"],
      "fixAvailable": {"name": "vitest", "version": "3.1.4", "isSemVerMajor": true}
    },
    "minimatch": {
      "name": "minimatch",
      "severity": "moderate",
      "isDirect": false,
      "via": [
        {
          "source": 1244623,
          "name": "minimatch",
          "dependency": "minimatch",
          "title": "minimatch has potential denial of service via globparts amplification",
          "url": "https://github.com/advisories/GHSA-g3hv-75wg-m249",
          "severity": "moderate",
          "cwe": ["CWE-405"],
          "cvss": {"score": 0, "vectorString": null},
          "range": ">=7.0.0 <11.0.1"
        }
      ],
      "effects": ["@ts-morph/common", "@typescript-eslint/typescript-estree", "eslint"],
      "range": "7.0.0 - 11.0.0",
      "nodes": ["node_modules/minimatch"],
      "fixAvailable": {"name": "shadcn", "version": "2.10.0", "isSemVerMajor": true}
    }
  }
}
"""


def aviso(paquete: str, ghsa: str, severidad: str = "high") -> dict:
    """Un aviso raíz: el objeto de `via` que npm escribe cuando el paquete mismo es el vulnerable."""
    return {
        "source": 1,
        "name": paquete,
        "dependency": paquete,
        "title": "aviso de ejemplo",
        "url": f"https://github.com/advisories/{ghsa}",
        "severity": severidad,
        "cwe": ["CWE-1333"],
        "cvss": {"score": 7.5, "vectorString": None},
        "range": "<=1.0.0",
    }


def vulnerabilidad(nombre: str, severidad: str, via: list) -> dict:
    """Una entrada de `vulnerabilidades` tal como la escribe `npm audit --json`."""
    return {
        "name": nombre,
        "severity": severidad,
        "isDirect": False,
        "via": via,
        "effects": [],
        "range": "*",
        "nodes": [f"node_modules/{nombre}"],
        "fixAvailable": False,
    }


def raiz(nombre: str, ghsa: str, severidad: str = "high") -> dict:
    return vulnerabilidad(nombre, severidad, [aviso(nombre, ghsa, severidad)])


def informe(**vulnerabilidades: dict) -> str:
    return json.dumps({"auditReportVersion": 2, "vulnerabilities": vulnerabilidades}, ensure_ascii=False)


class PruebaBase(unittest.TestCase):
    """Importa el módulo bajo prueba en cada caso, para que un módulo ausente rompa cada caso por separado."""

    def setUp(self) -> None:
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.directorio = Path(directorio.name)

    def sev(self):  # noqa: ANN201
        try:
            return importlib.import_module("severidad_npm_audit")
        except ModuleNotFoundError as error:
            if error.name != "severidad_npm_audit":
                raise
            self.fail("falta tools/severidad_npm_audit.py: el módulo bajo prueba todavía no existe")

    def excepcion(self, ghsa: str = GHSA_ACEPTADO, severidad: str = "high", revision: date = REVISION):  # noqa: ANN201
        modulo = self.sev()
        return modulo.Excepcion(
            ghsa=ghsa,
            paquete="paquete-de-ejemplo",
            severidad=severidad,
            decidida_por="la persona dueña del proyecto, en una prueba",
            motivo="motivo de ejemplo",
            revision=revision,
        )

    def escribir(self, texto: str, nombre: str = "npm-audit.json") -> str:
        ruta = self.directorio / nombre
        ruta.write_text(texto, encoding="utf-8")
        return str(ruta)

    def ejecutar(
        self,
        texto: str,
        excepciones: tuple | None = (),
        hoy: date = HOY,
    ) -> tuple[int, list[str], str]:
        """Corre `main` con el reloj y la tabla sustituidos. `excepciones=None` deja la tabla real del módulo."""
        ruta = self.escribir(texto)
        return self.ejecutar_ruta(ruta, excepciones, hoy)

    def ejecutar_ruta(self, ruta: str, excepciones: tuple | None = (), hoy: date = HOY) -> tuple[int, list[str], str]:
        modulo = self.sev()
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as pila:
            pila.enter_context(mock.patch.object(modulo, "fecha_de_hoy", lambda: hoy))
            if excepciones is not None:
                pila.enter_context(mock.patch.object(modulo, "EXCEPCIONES", excepciones))
            pila.enter_context(contextlib.redirect_stdout(salida))
            pila.enter_context(contextlib.redirect_stderr(errores))
            try:
                codigo = modulo.main([ruta])
            except AssertionError:
                raise
            except Exception as error:
                self.fail(f"main dejó escapar {type(error).__name__} en lugar de terminar con un código: {error!r}")
        lineas = [linea.rstrip() for linea in salida.getvalue().splitlines()]
        return codigo, lineas, errores.getvalue()

    @staticmethod
    def lineas_de(lineas: list[str], paquete: str) -> list[str]:
        """Las líneas que EMPIEZAN por una etiqueta y nombran el paquete como palabra completa."""
        return [linea for linea in lineas if f"  {paquete}  " in linea or linea.endswith(f"  {paquete}")]


# ---------------------------------------------------------------------------------------------------------
# 01 · informe vacío
# ---------------------------------------------------------------------------------------------------------


class TestNpm01Vacio(PruebaBase):
    def test_npm_01_informe_sin_vulnerabilidades_termina_en_0(self) -> None:
        """RNF-08 — un informe sin vulnerabilidades no falla ni inventa líneas."""
        codigo, lineas, _ = self.ejecutar(informe())

        self.assertEqual(0, codigo)
        for etiqueta in ("BAJA", "MEDIA", "ALTA", "CRÍTICA", "DESCONOCIDA"):
            self.assertFalse([linea for linea in lineas if linea.startswith(etiqueta)], lineas)

    def test_npm_01_informe_vacio_con_todos_los_campos_de_npm_termina_en_0(self) -> None:
        """RNF-08 — la forma completa del informe limpio de npm (con `metadata`) también se acepta."""
        texto = json.dumps(
            {
                "auditReportVersion": 2,
                "vulnerabilities": {},
                "metadata": {"vulnerabilities": {"info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0}},
            }
        )

        codigo, _, _ = self.ejecutar(texto)

        self.assertEqual(0, codigo)


# ---------------------------------------------------------------------------------------------------------
# 02 · un aviso alto sin excepción
# ---------------------------------------------------------------------------------------------------------


class TestNpm02AltoSinExcepcion(PruebaBase):
    def test_npm_02_un_aviso_alto_sin_excepcion_termina_en_1_y_nombra_paquete_y_ghsa(self) -> None:
        """RNF-08 — un `high` que nadie aceptó falla; la línea lleva ALTA, el paquete, el GHSA y el sufijo."""
        codigo, lineas, _ = self.ejecutar(informe(picomatch=raiz("picomatch", GHSA_ACEPTADO)))

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "picomatch")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("ALTA  picomatch  "), propias[0])
        self.assertIn(GHSA_ACEPTADO, propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_npm_02_el_paquete_que_solo_depende_de_otro_tambien_falla_si_su_raiz_no_esta_aceptada(self) -> None:
        """RNF-08 — `vite` depende de `picomatch` por cadena: sin excepción falla igual que su raíz."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            vite=vulnerabilidad("vite", "high", ["picomatch"]),
        )

        codigo, lineas, _ = self.ejecutar(texto)

        self.assertEqual(1, codigo)
        self.assertEqual(1, len(self.lineas_de(lineas, "vite")), lineas)
        self.assertTrue(self.lineas_de(lineas, "vite")[0].endswith(SUFIJO_QUE_FALLA), lineas)

    def test_npm_02_no_existe_la_opcion_ignore_ni_ninguna_otra_excepcion_por_linea_de_comandos(self) -> None:
        """RNF-08 — las excepciones viven en el código revisado: el script no acepta `--ignore`."""
        modulo = self.sev()
        ruta = self.escribir(informe(picomatch=raiz("picomatch", GHSA_ACEPTADO)))

        with (
            mock.patch.object(modulo, "EXCEPCIONES", ()),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                codigo = modulo.main([ruta, "--ignore", GHSA_ACEPTADO])
            except SystemExit as salida:  # argparse rechaza la opción desconocida
                codigo = salida.code

        self.assertNotEqual(0, codigo)


# ---------------------------------------------------------------------------------------------------------
# 03 · el aviso aceptado y vigente
# ---------------------------------------------------------------------------------------------------------


class TestNpm03AceptadoYVigente(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            vite=vulnerabilidad("vite", "high", ["picomatch"]),
        )

    def test_npm_03_el_aviso_aceptado_y_vigente_termina_en_0_y_excusa_al_dependiente(self) -> None:
        """RNF-08 — raíz y dependiente quedan EXCUSADOS con su fecha de revisión; no fallan."""
        codigo, lineas, _ = self.ejecutar(self.texto, (self.excepcion(),))

        self.assertEqual(0, codigo)
        for paquete in ("picomatch", "vite"):
            propias = self.lineas_de(lineas, paquete)
            self.assertEqual(1, len(propias), lineas)
            self.assertTrue(propias[0].startswith("EXCUSADA  "), propias[0])
            self.assertIn(GHSA_ACEPTADO, propias[0])
            self.assertIn("2026-12-18", propias[0])
            self.assertNotIn("falla el pipeline", propias[0])

    def test_npm_03_el_motivo_y_quien_decidio_se_imprimen_junto_a_la_excepcion(self) -> None:
        """RNF-08 — lo excusado no es silencioso: el registro del pipeline muestra quién, por qué y hasta cuándo."""
        _, lineas, _ = self.ejecutar(self.texto, (self.excepcion(),))

        todo = "\n".join(lineas)
        self.assertIn("motivo de ejemplo", todo)
        self.assertIn("la persona dueña del proyecto, en una prueba", todo)
        self.assertIn("2026-12-18", todo)

    def test_npm_03_el_ultimo_dia_de_la_fecha_de_revision_todavia_vale(self) -> None:
        """RNF-08 — la excepción vale hasta la fecha de revisión inclusive; falla el día siguiente."""
        codigo_el_dia, _, _ = self.ejecutar(self.texto, (self.excepcion(),), hoy=REVISION)
        codigo_despues, _, _ = self.ejecutar(self.texto, (self.excepcion(),), hoy=date(2026, 12, 19))

        self.assertEqual(0, codigo_el_dia)
        self.assertEqual(1, codigo_despues)

    def test_npm_03_un_dependiente_con_una_raiz_moderada_y_la_aceptada_tambien_queda_excusado(self) -> None:
        """RNF-08 — una raíz `moderate` no falla, así que no hace falta aceptarla para excusar al dependiente."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            minimatch=raiz("minimatch", GHSA_MEDIO, "moderate"),
            tinyglobby=vulnerabilidad("tinyglobby", "high", ["picomatch", "minimatch"]),
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(0, codigo)
        self.assertTrue(self.lineas_de(lineas, "tinyglobby")[0].startswith("EXCUSADA"), lineas)

    def test_npm_03_la_cadena_de_varios_saltos_sigue_a_su_raiz(self) -> None:
        """RNF-08 — `vitest` depende de `vite`, que depende de `picomatch`: se resuelve hasta la raíz."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            vite=vulnerabilidad("vite", "high", ["picomatch"]),
            vitest=vulnerabilidad("vitest", "high", ["vite"]),
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(0, codigo)
        self.assertTrue(self.lineas_de(lineas, "vitest")[0].startswith("EXCUSADA"), lineas)


# ---------------------------------------------------------------------------------------------------------
# 04 · la excepción caducada
# ---------------------------------------------------------------------------------------------------------


class TestNpm04Caducada(PruebaBase):
    def test_npm_04_la_misma_excepcion_caducada_termina_en_1_y_lo_dice(self) -> None:
        """RNF-08 — pasada la fecha de revisión el aviso vuelve a fallar, y la línea nombra la caducidad."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            vite=vulnerabilidad("vite", "high", ["picomatch"]),
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),), hoy=date(2026, 12, 19))

        self.assertEqual(1, codigo)
        for paquete in ("picomatch", "vite"):
            propias = self.lineas_de(lineas, paquete)
            self.assertEqual(1, len(propias), lineas)
            self.assertTrue(propias[0].startswith("ALTA  "), propias[0])
            self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])
        self.assertIn("caducó", "\n".join(lineas))
        self.assertIn("2026-12-18", "\n".join(lineas))


# ---------------------------------------------------------------------------------------------------------
# 05 · un alto aceptado junto a otro alto distinto
# ---------------------------------------------------------------------------------------------------------


class TestNpm05AceptadoJuntoAOtroAlto(PruebaBase):
    def test_npm_05_un_alto_aceptado_junto_a_otro_alto_distinto_termina_en_1(self) -> None:
        """RNF-08 — la excepción no ampara al otro aviso: la raíz aceptada se excusa y la otra falla."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            otro=raiz("otro", GHSA_OTRO_ALTO),
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "picomatch")[0].startswith("EXCUSADA"), lineas)
        self.assertTrue(self.lineas_de(lineas, "otro")[0].endswith(SUFIJO_QUE_FALLA), lineas)

    def test_npm_05_un_dependiente_de_la_raiz_aceptada_y_de_otro_alto_falla(self) -> None:
        """RNF-08 — basta una raíz alta sin aceptar entre las del dependiente para que falle."""
        texto = informe(
            picomatch=raiz("picomatch", GHSA_ACEPTADO),
            otro=raiz("otro", GHSA_OTRO_ALTO),
            vite=vulnerabilidad("vite", "high", ["picomatch", "otro"]),
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "vite")
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias)
        self.assertIn(GHSA_OTRO_ALTO, propias[0])

    def test_npm_05_un_paquete_con_dos_avisos_propios_y_solo_uno_aceptado_falla(self) -> None:
        """RNF-08 — un mismo paquete con dos avisos raíz: aceptar uno no ampara el otro."""
        texto = informe(
            picomatch=vulnerabilidad(
                "picomatch", "high", [aviso("picomatch", GHSA_ACEPTADO), aviso("picomatch", GHSA_OTRO_ALTO)]
            )
        )

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "picomatch")[0].endswith(SUFIJO_QUE_FALLA), lineas)


# ---------------------------------------------------------------------------------------------------------
# 06 · severidades
# ---------------------------------------------------------------------------------------------------------


class TestNpm06Severidades(PruebaBase):
    def test_npm_06_severidad_desconocida_termina_en_1_como_desconocida(self) -> None:
        """RNF-08 — una severidad que el script no reconoce falla cerrado."""
        for severidad in ("urgente", "", "HIGHEST"):
            with self.subTest(severidad=severidad):
                codigo, lineas, _ = self.ejecutar(informe(paquete=raiz("paquete", GHSA_OTRO_ALTO, severidad)))

                self.assertEqual(1, codigo)
                propias = self.lineas_de(lineas, "paquete")
                self.assertTrue(propias[0].startswith("DESCONOCIDA  paquete  "), propias[0])
                self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_npm_06_critica_termina_en_1_con_etiqueta_critica(self) -> None:
        """RNF-08 — un `critical` falla con la etiqueta CRÍTICA."""
        codigo, lineas, _ = self.ejecutar(informe(paquete=raiz("paquete", GHSA_OTRO_ALTO, "critical")))

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "paquete")
        self.assertTrue(propias[0].startswith("CRÍTICA  paquete  "), propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_npm_06_moderada_termina_en_0_y_se_informa_como_media(self) -> None:
        """RNF-08 — un `moderate` no falla pero se informa con la etiqueta MEDIA."""
        codigo, lineas, _ = self.ejecutar(informe(minimatch=raiz("minimatch", GHSA_MEDIO, "moderate")))

        self.assertEqual(0, codigo)
        propias = self.lineas_de(lineas, "minimatch")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("MEDIA  minimatch  "), propias[0])
        self.assertIn(GHSA_MEDIO, propias[0])
        self.assertNotIn("falla el pipeline", propias[0])

    def test_npm_06_baja_e_info_terminan_en_0_y_se_informan(self) -> None:
        """RNF-08 — `low` e `info` no fallan; se informan con BAJA e INFO."""
        texto = informe(uno=raiz("uno", GHSA_MEDIO, "low"), dos=raiz("dos", GHSA_OTRO_ALTO, "info"))

        codigo, lineas, _ = self.ejecutar(texto)

        self.assertEqual(0, codigo)
        self.assertTrue(self.lineas_de(lineas, "uno")[0].startswith("BAJA  "), lineas)
        self.assertTrue(self.lineas_de(lineas, "dos")[0].startswith("INFO  "), lineas)

    def test_npm_06_la_severidad_en_mayusculas_se_normaliza(self) -> None:
        """RNF-08 — `HIGH` y `Moderate` son `high` y `moderate`: no se confunden con DESCONOCIDA."""
        texto = informe(uno=raiz("uno", GHSA_OTRO_ALTO, "HIGH"), dos=raiz("dos", GHSA_MEDIO, "Moderate"))

        codigo, lineas, _ = self.ejecutar(texto)

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "uno")[0].startswith("ALTA  "), lineas)
        self.assertTrue(self.lineas_de(lineas, "dos")[0].startswith("MEDIA  "), lineas)

    def test_npm_06_un_alto_sin_ningun_aviso_raiz_falla_cerrado(self) -> None:
        """RNF-08 — un paquete `high` cuyo `via` está vacío no se puede explicar: falla, no se excusa."""
        codigo, lineas, _ = self.ejecutar(informe(raro=vulnerabilidad("raro", "high", [])), (self.excepcion(),))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "raro")[0].endswith(SUFIJO_QUE_FALLA), lineas)

    def test_npm_06_un_alto_que_depende_de_un_paquete_ausente_del_informe_falla_cerrado(self) -> None:
        """RNF-08 — el `via` apunta a un paquete que el informe no describe: no hay raíz que aceptar."""
        codigo, lineas, _ = self.ejecutar(informe(raro=vulnerabilidad("raro", "high", ["fantasma"])), (self.excepcion(),))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "raro")[0].endswith(SUFIJO_QUE_FALLA), lineas)

    def test_npm_06_un_ciclo_entre_paquetes_no_cuelga_el_script_y_falla(self) -> None:
        """RNF-08 — `a` depende de `b` y `b` de `a`, sin ninguna raíz: termina y falla cerrado."""
        texto = informe(
            a=vulnerabilidad("a", "high", ["b"]),
            b=vulnerabilidad("b", "high", ["a"]),
        )

        codigo, _, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(1, codigo)

    def test_npm_06_un_aviso_raiz_sin_url_de_ghsa_no_se_puede_aceptar_y_falla(self) -> None:
        """RNF-08 — una excepción es por GHSA exacto; sin GHSA en la `url` no hay nada con qué cotejarla."""
        sin_url = aviso("picomatch", GHSA_ACEPTADO)
        sin_url["url"] = "https://example.com/otro-aviso"

        codigo, _, _ = self.ejecutar(informe(picomatch=vulnerabilidad("picomatch", "high", [sin_url])), (self.excepcion(),))

        self.assertEqual(1, codigo)


# ---------------------------------------------------------------------------------------------------------
# 07 · informe ausente o ilegible
# ---------------------------------------------------------------------------------------------------------


class TestNpm07InformeIlegible(PruebaBase):
    def exigir_2(self, texto: str) -> None:
        codigo, _, errores = self.ejecutar(texto)

        self.assertEqual(2, codigo)
        self.assertTrue(errores.strip(), "un informe que no se lee debe explicarse en stderr")

    def test_npm_07_informe_inexistente_termina_en_2(self) -> None:
        """RNF-08 — si `npm audit` no dejó informe, el trabajo no pasa en verde: exit 2."""
        codigo, _, errores = self.ejecutar_ruta(str(self.directorio / "no-existe.json"))

        self.assertEqual(2, codigo)
        self.assertTrue(errores.strip())

    def test_npm_07_json_con_sintaxis_rota_o_archivo_vacio_termina_en_2(self) -> None:
        """RNF-08 — un informe truncado o vacío no es un informe limpio."""
        for texto in ('{"auditReportVersion": 2, "vulnerabilities": {', ""):
            with self.subTest(texto=texto):
                self.exigir_2(texto)

    def test_npm_07_bytes_que_no_son_utf8_terminan_en_2(self) -> None:
        """RNF-08 — un archivo ilegible como texto termina en 2, no con una traza."""
        ruta = self.directorio / "binario.json"
        ruta.write_bytes(b"\xff\xfe\x00\x80\x81")

        codigo, _, _ = self.ejecutar_ruta(str(ruta))

        self.assertEqual(2, codigo)

    def test_npm_07_el_informe_de_error_de_npm_termina_en_2(self) -> None:
        """RNF-08 — sin red, `npm audit --json` escribe `{"error": …}` y ninguna lista de vulnerabilidades: no es verde."""
        self.exigir_2(json.dumps({"message": "request to registry failed", "error": {"code": "ENOTFOUND"}}))

    def test_npm_07_otra_version_del_formato_termina_en_2(self) -> None:
        """RNF-08 — solo se entiende `auditReportVersion: 2`; otra forma no se interpreta a ciegas."""
        self.exigir_2(json.dumps({"auditReportVersion": 1, "vulnerabilities": {}}))
        self.exigir_2(json.dumps({"vulnerabilities": {}}))

    def test_npm_07_formas_inesperadas_terminan_en_2(self) -> None:
        """RNF-08 — raíz que no es objeto, `vulnerabilities` que no es objeto, severidad ausente, `via` mal formado."""
        casos = {
            "lista en la raíz": "[]",
            "vulnerabilities es lista": json.dumps({"auditReportVersion": 2, "vulnerabilities": []}),
            "entrada que no es objeto": json.dumps({"auditReportVersion": 2, "vulnerabilities": {"a": 1}}),
            "sin severity": json.dumps(
                {"auditReportVersion": 2, "vulnerabilities": {"a": {"name": "a", "via": []}}}
            ),
            "severity que no es cadena": json.dumps(
                {"auditReportVersion": 2, "vulnerabilities": {"a": {"name": "a", "severity": 5, "via": []}}}
            ),
            "via que no es lista": json.dumps(
                {"auditReportVersion": 2, "vulnerabilities": {"a": {"name": "a", "severity": "high", "via": "b"}}}
            ),
            "elemento de via que es número": json.dumps(
                {"auditReportVersion": 2, "vulnerabilities": {"a": {"name": "a", "severity": "high", "via": [3]}}}
            ),
            "aviso de via sin severity": json.dumps(
                {
                    "auditReportVersion": 2,
                    "vulnerabilities": {
                        "a": {"name": "a", "severity": "high", "via": [{"name": "a", "url": "https://x"}]}
                    },
                }
            ),
        }
        for descripcion, texto in casos.items():
            with self.subTest(caso=descripcion):
                self.exigir_2(texto)

    def test_npm_07_json_anidado_100000_niveles_termina_en_2_sin_traza(self) -> None:
        """RNF-08 — un `[` anidado 100000 veces desborda la recursión de `json`: exit 2, no traza."""
        self.exigir_2("[" * 100_000)


# ---------------------------------------------------------------------------------------------------------
# 08 · una excepción que ya no aparece
# ---------------------------------------------------------------------------------------------------------


class TestNpm08ExcepcionSinUso(PruebaBase):
    def test_npm_08_una_excepcion_que_ya_no_aparece_termina_en_0_con_una_nota_para_retirarla(self) -> None:
        """RNF-08 — el aviso ya no está en el informe: no falla, y el registro dice que la excepción se puede retirar."""
        codigo, lineas, _ = self.ejecutar(informe(), (self.excepcion(),))

        self.assertEqual(0, codigo)
        notas = [linea for linea in lineas if linea.startswith("INFORMATIVA")]
        self.assertEqual(1, len(notas), lineas)
        self.assertIn(GHSA_ACEPTADO, notas[0])
        self.assertIn("retirar", notas[0])

    def test_npm_08_una_excepcion_usada_no_genera_la_nota(self) -> None:
        """RNF-08 — la nota solo aparece cuando la excepción sobra."""
        _, lineas, _ = self.ejecutar(informe(picomatch=raiz("picomatch", GHSA_ACEPTADO)), (self.excepcion(),))

        self.assertEqual([], [linea for linea in lineas if linea.startswith("INFORMATIVA")], lineas)

    def test_npm_08_una_excepcion_caducada_que_ya_no_aparece_tambien_se_informa_y_no_falla(self) -> None:
        """RNF-08 — caducada y sin uso: nada que fallar, y la nota sigue pidiendo retirarla."""
        codigo, lineas, _ = self.ejecutar(informe(), (self.excepcion(),), hoy=date(2027, 1, 1))

        self.assertEqual(0, codigo)
        self.assertEqual(1, len([linea for linea in lineas if linea.startswith("INFORMATIVA")]), lineas)


# ---------------------------------------------------------------------------------------------------------
# 09 · el informe real
# ---------------------------------------------------------------------------------------------------------


class TestNpm09InformeReal(PruebaBase):
    def test_npm_09_sin_la_excepcion_el_informe_real_falla(self) -> None:
        """RNF-08 · rojo — sin excepción, el informe real de `npm audit --json` termina en 1 y nombra a `picomatch`."""
        codigo, lineas, _ = self.ejecutar(INFORME_REAL_REDUCIDO, ())

        self.assertEqual(1, codigo)
        for paquete in ("picomatch", "fdir", "tinyglobby", "vite", "vitest"):
            propias = self.lineas_de(lineas, paquete)
            self.assertEqual(1, len(propias), (paquete, lineas))
            self.assertTrue(propias[0].startswith("ALTA  "), propias[0])
            self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])
        self.assertIn(GHSA_REAL, "\n".join(lineas))

    def test_npm_09_con_la_tabla_real_el_informe_real_pasa_y_los_moderados_se_informan(self) -> None:
        """RNF-08 · verde — con la tabla `EXCEPCIONES` del script y la fecha del 2026-11-18 el informe termina en 0."""
        codigo, lineas, errores = self.ejecutar(INFORME_REAL_REDUCIDO, None, hoy=HOY)

        self.assertEqual(0, codigo, (lineas, errores))
        for paquete in ("picomatch", "fdir", "tinyglobby", "vite", "vitest"):
            propias = self.lineas_de(lineas, paquete)
            self.assertEqual(1, len(propias), (paquete, lineas))
            self.assertTrue(propias[0].startswith("EXCUSADA  "), propias[0])
            self.assertIn("2026-12-18", propias[0])
        self.assertTrue(self.lineas_de(lineas, "minimatch")[0].startswith("MEDIA  "), lineas)
        self.assertEqual([], [linea for linea in lineas if linea.startswith("INFORMATIVA")], lineas)

    def test_npm_09_con_la_tabla_real_y_la_fecha_vencida_el_informe_real_vuelve_a_fallar(self) -> None:
        """RNF-08 · rojo por caducidad — el 2026-12-19 la excepción real ya no vale."""
        codigo, lineas, _ = self.ejecutar(INFORME_REAL_REDUCIDO, None, hoy=date(2026, 12, 19))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "picomatch")[0].endswith(SUFIJO_QUE_FALLA), lineas)

    def test_npm_09_la_tabla_real_declara_solo_la_excepcion_de_picomatch(self) -> None:
        """RNF-08 — la tabla tiene una sola entrada: GHSA exacto, severidad `high`, quién decidió, motivo y revisión."""
        modulo = self.sev()

        self.assertEqual(1, len(modulo.EXCEPCIONES))
        excepcion = modulo.EXCEPCIONES[0]
        self.assertEqual(GHSA_REAL, excepcion.ghsa)
        self.assertEqual("picomatch", excepcion.paquete)
        self.assertEqual("high", excepcion.severidad)
        self.assertEqual(date(2026, 12, 18), excepcion.revision)
        self.assertIn("la persona dueña del proyecto", excepcion.decidida_por)
        self.assertIn("2026-11-18", excepcion.decidida_por)
        self.assertGreater(len(excepcion.motivo), 40)

    def test_npm_09_el_motivo_solo_afirma_lo_que_se_comprobo(self) -> None:
        """RNF-08 — el motivo cita la comprobación de `npm ls --omit=dev` y la ausencia de versión corregida."""
        modulo = self.sev()

        motivo = modulo.EXCEPCIONES[0].motivo
        self.assertIn("npm ls picomatch --omit=dev", motivo)
        self.assertIn("4.0.7", motivo)


# ---------------------------------------------------------------------------------------------------------
# 10 · la excepción es por GHSA exacto
# ---------------------------------------------------------------------------------------------------------


class TestNpm10PorGhsaExacto(PruebaBase):
    def test_npm_10_otro_ghsa_del_mismo_paquete_no_queda_excusado(self) -> None:
        """RNF-08 — aceptar un aviso de `picomatch` no acepta otro aviso de `picomatch`."""
        texto = informe(picomatch=raiz("picomatch", GHSA_OTRO_ALTO))
        tabla = (self.excepcion(GHSA_ACEPTADO),)

        codigo, _, _ = self.ejecutar(texto, tabla)

        self.assertEqual(1, codigo)

    def test_npm_10_el_nombre_del_paquete_de_la_excepcion_no_se_usa_para_cotejar(self) -> None:
        """RNF-08 — el aviso aceptado en OTRO paquete (mismo GHSA) también cuenta: manda el GHSA, no el nombre."""
        texto = informe(otro_nombre=raiz("otro_nombre", GHSA_ACEPTADO))

        codigo, _, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(0, codigo)

    def test_npm_10_si_el_aviso_sube_de_severidad_la_excepcion_ya_no_lo_ampara(self) -> None:
        """RNF-08 — se aceptó un `high`; si el mismo GHSA pasa a `critical`, falla."""
        texto = informe(picomatch=raiz("picomatch", GHSA_ACEPTADO, "critical"))

        codigo, lineas, _ = self.ejecutar(texto, (self.excepcion(),))

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "picomatch")[0].startswith("CRÍTICA  "), lineas)

    def test_npm_10_un_ghsa_con_otra_capitalizacion_no_se_acepta(self) -> None:
        """RNF-08 — la coincidencia es exacta: no se normaliza el identificador."""
        texto = informe(picomatch=raiz("picomatch", GHSA_ACEPTADO.upper().replace("GHSA", "GHSA")))
        tabla = (self.excepcion(GHSA_ACEPTADO),)

        codigo, _, _ = self.ejecutar(texto, tabla)

        self.assertEqual(1, codigo)


# ---------------------------------------------------------------------------------------------------------
# El reloj
# ---------------------------------------------------------------------------------------------------------


class TestNpm11Reloj(PruebaBase):
    def test_npm_11_fecha_de_hoy_devuelve_una_fecha_sin_hora(self) -> None:
        """RNF-08 — la función sustituible entrega un `date`, no un `datetime`."""
        hoy = self.sev().fecha_de_hoy()

        self.assertIs(type(hoy), date)


if __name__ == "__main__":
    unittest.main()
