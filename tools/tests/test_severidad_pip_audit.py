"""Pruebas del filtro de severidad de `pip-audit`, `tools/severidad_pip_audit.py`.

TKT-009b · fila B2. Cubren `CA-10` de la spec común (RNF-08): una dependencia de Python con una vulnerabilidad de
severidad alta falla el pipeline igual que un test roto. `pip-audit` no informa la severidad (supuesto A-3), así que
el filtro la toma del aviso de GitHub (`GHSA-…`) consultando OSV, y falla ante `HIGH`, `CRITICAL` o severidad
desconocida. Un hallazgo `LOW` o `MODERATE` se informa y no falla.

Ninguna prueba toca la red. `clasificar(dependencias, consultar)` recibe la consulta como parámetro; `main` la toma de
`consultar_osv`, que cada prueba sustituye en el módulo (`main` debe resolverla al llamarla, no fijarla como valor por
omisión). Además, `urllib.request.urlopen` queda sustituido en todas las pruebas por una función que falla: una
consulta real a OSV rompe el caso que la hizo.

Casos del diseño (TKT-009, tabla de pruebas), cada uno con prefijo `test_tcNN_`:

* TC-30  `HIGH` termina en 1; la línea nombra paquete, versión y `GHSA`, con la etiqueta `ALTA`.
* TC-31  `CRITICAL` termina en 1 (`CRÍTICA`).
* TC-32  `MODERATE` termina en 0 y se informa como `MEDIA`.
* TC-33  `LOW` termina en 0 (`BAJA`).
* TC-34  Un hallazgo sin `GHSA` entre el `id` y los alias, o sin severidad en OSV, termina en 1 (`DESCONOCIDA`).
* TC-35  Un informe sin vulnerabilidades termina en 0.
* TC-36  El JSON inexistente o ilegible termina en 2.
* TC-37  Un error de la consulta a OSV termina en 2.
* TC-38  Acepta `{"dependencies": [...]}` y la lista antigua.

Mutantes de la parte b que estas pruebas deben matar (tabla de mutación del diseño):

* `SEVERIDADES_QUE_FALLAN` sin `CRITICAL`: cae `test_tc31_critical_termina_en_1_con_etiqueta_critica`.
* `DESCONOCIDA` tratada como informativa: caen `test_tc34_hallazgo_sin_ghsa_termina_en_1_como_desconocida` y
  `test_tc34_severidad_ausente_en_osv_termina_en_1_como_desconocida`.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_severidad_pip_audit -v
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
import urllib.error
from pathlib import Path
from unittest import mock

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

# ---------------------------------------------------------------------------------------------------------
# Datos de ejemplo
# ---------------------------------------------------------------------------------------------------------

GHSA_ALTA = "GHSA-aaaa-bbbb-cccc"
GHSA_CRITICA = "GHSA-cccc-dddd-eeee"
GHSA_MEDIA = "GHSA-eeee-ffff-gggg"
GHSA_BAJA = "GHSA-gggg-hhhh-iiii"
GHSA_OTRO = "GHSA-iiii-jjjj-kkkk"

SUFIJO_QUE_FALLA = "→ falla el pipeline (RNF-08)"


def vulnerabilidad(identificador: str, alias: list[str]) -> dict:
    """Una entrada de `vulns` tal como la escribe `pip-audit -f json`."""
    return {
        "id": identificador,
        "fix_versions": ["9.9.9"],
        "aliases": alias,
        "description": "descripción de ejemplo",
    }


def dependencia(nombre: str, version: str, vulns: list[dict] | None = None) -> dict:
    """Una entrada de `dependencies` tal como la escribe `pip-audit -f json`."""
    return {"name": nombre, "version": version, "vulns": vulns or []}


def django_con_aviso_pysec(ghsa: str) -> dict:
    """`django 3.2` con un aviso PYSEC cuyo alias de GitHub es `ghsa`."""
    return dependencia("django", "3.2", [vulnerabilidad("PYSEC-2024-100", ["CVE-2024-0001", ghsa])])


def informe_con(*dependencias: dict) -> str:
    return json.dumps({"dependencies": list(dependencias)}, ensure_ascii=False)


def respuesta_osv(severidad: str | None) -> dict:
    """La parte de la respuesta de OSV que lee el filtro: `database_specific.severity`."""
    if severidad is None:
        return {"id": "GHSA-sin-severidad", "database_specific": {}}
    return {"id": "GHSA-con-severidad", "database_specific": {"severity": severidad}}


class OsvFalso:
    """La consulta inyectada: devuelve por identificador y recuerda a quién se consultó."""

    def __init__(
        self, respuestas: dict[str, dict] | None = None, por_omision: dict | None = None
    ) -> None:
        self.respuestas = respuestas or {}
        self.por_omision = por_omision if por_omision is not None else {}
        self.consultas: list[str] = []

    def __call__(self, identificador: str) -> dict:
        self.consultas.append(identificador)
        return self.respuestas.get(identificador, self.por_omision)


class RespuestaHttpFalsa:
    """Lo mínimo que `consultar_osv` necesita de lo que devuelve `urlopen`: usarse con `with` y `read()`."""

    def __init__(self, cuerpo: dict) -> None:
        self._bytes = json.dumps(cuerpo).encode("utf-8")

    def __enter__(self) -> RespuestaHttpFalsa:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, *args: object) -> bytes:
        return self._bytes


def _sin_red(*args: object, **kwargs: object) -> None:
    raise AssertionError("una prueba de severidad_pip_audit intentó abrir la red")


class PruebaBase(unittest.TestCase):
    """Importa el módulo bajo prueba en cada caso, para que un módulo ausente rompa cada caso por separado."""

    def setUp(self) -> None:
        parche = mock.patch("urllib.request.urlopen", side_effect=_sin_red)
        parche.start()
        self.addCleanup(parche.stop)
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.directorio = Path(directorio.name)

    def sev(self):  # noqa: ANN201
        try:
            return importlib.import_module("severidad_pip_audit")
        except ModuleNotFoundError as error:
            if error.name != "severidad_pip_audit":
                raise
            self.fail("falta tools/severidad_pip_audit.py: el módulo bajo prueba todavía no existe")

    def escribir_informe(self, texto: str, nombre: str = "pip-audit.json") -> str:
        ruta = self.directorio / nombre
        ruta.write_text(texto, encoding="utf-8")
        return str(ruta)

    def ejecutar_main(
        self,
        argv: list[str],
        osv: OsvFalso | None = None,
        osv_lanza: BaseException | None = None,
    ) -> tuple[int, list[str], str, OsvFalso]:
        """Corre `main(argv)` con `consultar_osv` sustituida. Devuelve código, líneas de salida, errores y la consulta."""
        modulo = self.sev()
        osv = osv or OsvFalso()
        sustituto = mock.Mock(side_effect=osv_lanza) if osv_lanza is not None else osv
        salida, errores = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(modulo, "consultar_osv", sustituto),
            contextlib.redirect_stdout(salida),
            contextlib.redirect_stderr(errores),
        ):
            codigo = modulo.main(argv)
        lineas = [linea.rstrip() for linea in salida.getvalue().splitlines()]
        return codigo, lineas, errores.getvalue(), osv

    @staticmethod
    def lineas_de(lineas: list[str], paquete: str) -> list[str]:
        return [linea for linea in lineas if paquete in linea]


# ---------------------------------------------------------------------------------------------------------
# TC-30 · HIGH
# ---------------------------------------------------------------------------------------------------------


class TestTc30Alta(PruebaBase):
    def test_tc30_high_termina_en_1_y_la_linea_nombra_paquete_version_y_ghsa(self) -> None:
        """RNF-08 · CA-10 esc. 2 — un HIGH falla el pipeline; la línea completa lleva ALTA, paquete, versión y GHSA."""
        ruta = self.escribir_informe(informe_con(django_con_aviso_pysec(GHSA_ALTA)))
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH")})

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        esperada = (
            f"ALTA  django 3.2  {GHSA_ALTA} (CVE-2024-0001, PYSEC-2024-100) {SUFIJO_QUE_FALLA}"
        )
        self.assertEqual(1, codigo)
        self.assertIn(esperada, lineas)
        self.assertEqual(1, len(self.lineas_de(lineas, "django")), lineas)

    def test_tc30_clasificar_consulta_el_ghsa_y_devuelve_el_hallazgo_high(self) -> None:
        """RNF-08 · CA-10 esc. 2 — la severidad se pide a OSV por el GHSA, no por el id PYSEC."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH")})

        hallazgos = modulo.clasificar([django_con_aviso_pysec(GHSA_ALTA)], osv)

        self.assertEqual([GHSA_ALTA], osv.consultas)
        self.assertEqual(
            [modulo.Hallazgo("django", "3.2", "PYSEC-2024-100", GHSA_ALTA, "HIGH")],
            hallazgos,
        )

    def test_tc30_aviso_es_el_id_cuando_el_id_ya_es_un_ghsa(self) -> None:
        """RNF-08 · CA-10 esc. 2 — si el id es un GHSA, gana sobre los GHSA de los alias."""
        modulo = self.sev()
        dependencias = [
            dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, ["CVE-2024-0001", GHSA_OTRO])])
        ]
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH")})

        hallazgos = modulo.clasificar(dependencias, osv)

        self.assertEqual([GHSA_ALTA], osv.consultas)
        self.assertEqual(GHSA_ALTA, hallazgos[0].aviso)
        self.assertEqual(GHSA_ALTA, hallazgos[0].identificador)

    def test_tc30_aviso_es_el_primer_ghsa_de_los_alias_cuando_el_id_no_lo_es(self) -> None:
        """RNF-08 · CA-10 esc. 2 — con un id PYSEC, el aviso es el primer GHSA de los alias."""
        modulo = self.sev()
        dependencias = [
            dependencia(
                "django",
                "3.2",
                [vulnerabilidad("PYSEC-2024-100", ["CVE-2024-0001", GHSA_ALTA, GHSA_OTRO])],
            )
        ]
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH"), GHSA_OTRO: respuesta_osv("LOW")})

        hallazgos = modulo.clasificar(dependencias, osv)

        self.assertEqual(GHSA_ALTA, hallazgos[0].aviso)
        self.assertEqual("HIGH", hallazgos[0].severidad)
        self.assertEqual("PYSEC-2024-100", hallazgos[0].identificador)

    def test_tc30_informe_mixto_falla_por_el_alto_y_lista_todos_los_hallazgos(self) -> None:
        """RNF-08 · CA-10 esc. 2 — un MEDIA junto a un ALTA no esconde al ALTA; el código no es el del último."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("limpio", "1.0"),
                dependencia("flask", "2.0", [vulnerabilidad(GHSA_ALTA, [])]),
                dependencia("requests", "2.0", [vulnerabilidad(GHSA_MEDIA, [])]),
            )
        )
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH"), GHSA_MEDIA: respuesta_osv("MODERATE")})

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        self.assertEqual(1, codigo)
        self.assertEqual(1, len(self.lineas_de(lineas, "flask")), lineas)
        self.assertEqual(1, len(self.lineas_de(lineas, "requests")), lineas)
        self.assertEqual([], self.lineas_de(lineas, "limpio"))
        self.assertTrue(self.lineas_de(lineas, "flask")[0].startswith("ALTA"))
        self.assertTrue(self.lineas_de(lineas, "requests")[0].startswith("MEDIA"))

    def test_tc30_ignore_vuln_no_existe_y_no_perdona_un_alto(self) -> None:
        """RNF-08 · CA-10 esc. 2 — el script no tiene `--ignore-vuln`: las excepciones se declaran en `pip-audit`."""
        ruta = self.escribir_informe(informe_con(django_con_aviso_pysec(GHSA_ALTA)))
        osv = OsvFalso({GHSA_ALTA: respuesta_osv("HIGH")})

        try:
            codigo, _, _, _ = self.ejecutar_main([ruta, "--ignore-vuln", "PYSEC-2024-100"], osv)
        except SystemExit as salida:  # argparse rechaza la opción desconocida
            codigo = salida.code

        self.assertNotEqual(0, codigo)


# ---------------------------------------------------------------------------------------------------------
# TC-31 · CRITICAL
# ---------------------------------------------------------------------------------------------------------


class TestTc31Critica(PruebaBase):
    def test_tc31_critical_termina_en_1_con_etiqueta_critica(self) -> None:
        """RNF-08 · CA-10 esc. 2 — un CRITICAL falla el pipeline con la etiqueta CRÍTICA."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_CRITICA, [])]))
        )
        osv = OsvFalso({GHSA_CRITICA: respuesta_osv("CRITICAL")})

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("CRÍTICA"), propias[0])
        self.assertIn("django 3.2", propias[0])
        self.assertIn(GHSA_CRITICA, propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_tc31_severidades_que_fallan_es_high_y_critical(self) -> None:
        """RNF-08 · CA-10 esc. 2 — la constante fija el umbral: HIGH y CRITICAL, nada más."""
        modulo = self.sev()

        self.assertEqual(frozenset({"HIGH", "CRITICAL"}), modulo.SEVERIDADES_QUE_FALLAN)


# ---------------------------------------------------------------------------------------------------------
# TC-32 y TC-33 · MODERATE y LOW informan y no fallan
# ---------------------------------------------------------------------------------------------------------


class TestTc32Media(PruebaBase):
    def test_tc32_moderate_termina_en_0_y_se_informa_como_media(self) -> None:
        """RNF-08 · CA-10 esc. 3 — un MODERATE no falla, pero se informa con la etiqueta MEDIA."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_MEDIA, [])]))
        )
        osv = OsvFalso({GHSA_MEDIA: respuesta_osv("MODERATE")})

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        self.assertEqual(0, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("MEDIA"), propias[0])
        self.assertIn("django 3.2", propias[0])
        self.assertIn(GHSA_MEDIA, propias[0])
        self.assertNotIn("falla el pipeline", propias[0])

    def test_tc32_clasificar_conserva_la_severidad_de_osv_sin_traducirla(self) -> None:
        """RNF-08 · CA-10 esc. 3 — el hallazgo guarda `MODERATE`; la etiqueta MEDIA es solo de presentación."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_MEDIA: respuesta_osv("MODERATE")})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad(GHSA_MEDIA, [])])], osv
        )

        self.assertEqual("MODERATE", hallazgos[0].severidad)

    def test_tc32_la_severidad_en_minusculas_se_normaliza_y_no_falla(self) -> None:
        """RNF-08 · CA-10 esc. 3 — `moderate` en minúsculas es MODERATE: se informa y no se confunde con DESCONOCIDA."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_MEDIA: respuesta_osv("moderate")})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad(GHSA_MEDIA, [])])], osv
        )

        self.assertEqual("MODERATE", hallazgos[0].severidad)


class TestTc33Baja(PruebaBase):
    def test_tc33_low_termina_en_0_y_se_informa_como_baja(self) -> None:
        """RNF-08 · CA-10 esc. 3 — un LOW no falla, pero se informa con la etiqueta BAJA."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_BAJA, [])]))
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW")})

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        self.assertEqual(0, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("BAJA"), propias[0])
        self.assertIn("django 3.2", propias[0])
        self.assertIn(GHSA_BAJA, propias[0])
        self.assertNotIn("falla el pipeline", propias[0])


# ---------------------------------------------------------------------------------------------------------
# TC-34 · DESCONOCIDA falla cerrado
# ---------------------------------------------------------------------------------------------------------


class TestTc34Desconocida(PruebaBase):
    def test_tc34_hallazgo_sin_ghsa_termina_en_1_como_desconocida(self) -> None:
        """RNF-08 · CA-10 esc. 2 — sin GHSA entre el id y los alias no hay severidad que consultar: falla cerrado."""
        dependencias = [
            dependencia("django", "3.2", [vulnerabilidad("PYSEC-2024-200", ["CVE-2024-0002"])])
        ]
        ruta = self.escribir_informe(informe_con(*dependencias))
        # Si el filtro consultara de todos modos, esta respuesta lo haría pasar como LOW.
        osv = OsvFalso(por_omision=respuesta_osv("LOW"))

        codigo, lineas, _, _ = self.ejecutar_main([ruta], osv)

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("DESCONOCIDA  django 3.2  "), propias[0])
        self.assertIn("PYSEC-2024-200", propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_tc34_clasificar_sin_ghsa_deja_el_aviso_vacio_y_no_consulta(self) -> None:
        """RNF-08 · CA-10 esc. 2 — `aviso` queda en `None`, la severidad en DESCONOCIDA y OSV no se consulta."""
        modulo = self.sev()
        dependencias = [
            dependencia("django", "3.2", [vulnerabilidad("PYSEC-2024-200", ["CVE-2024-0002"])])
        ]
        osv = OsvFalso(por_omision=respuesta_osv("LOW"))

        hallazgos = modulo.clasificar(dependencias, osv)

        self.assertEqual([], osv.consultas)
        self.assertEqual(
            [modulo.Hallazgo("django", "3.2", "PYSEC-2024-200", None, "DESCONOCIDA")],
            hallazgos,
        )

    def test_tc34_severidad_ausente_en_osv_termina_en_1_como_desconocida(self) -> None:
        """RNF-08 · CA-10 esc. 2 — con GHSA pero sin `database_specific.severity` en la respuesta: falla cerrado."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )
        for respuesta in ({}, {"id": GHSA_ALTA}, respuesta_osv(None)):
            with self.subTest(respuesta=respuesta):
                codigo, lineas, _, _ = self.ejecutar_main([ruta], OsvFalso({GHSA_ALTA: respuesta}))

                self.assertEqual(1, codigo)
                propias = self.lineas_de(lineas, "django")
                self.assertEqual(1, len(propias), lineas)
                self.assertTrue(propias[0].startswith("DESCONOCIDA  django 3.2  "), propias[0])
                self.assertIn(GHSA_ALTA, propias[0])
                self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_tc34_clasificar_con_severidad_ausente_marca_desconocida_y_conserva_el_aviso(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — el hallazgo guarda el GHSA aunque OSV no traiga severidad."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_ALTA: respuesta_osv(None)})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])])], osv
        )

        self.assertEqual(
            [modulo.Hallazgo("django", "3.2", GHSA_ALTA, GHSA_ALTA, "DESCONOCIDA")],
            hallazgos,
        )


# ---------------------------------------------------------------------------------------------------------
# TC-35 · informe limpio
# ---------------------------------------------------------------------------------------------------------


class TestTc35Limpio(PruebaBase):
    def test_tc35_informe_sin_vulnerabilidades_termina_en_0(self) -> None:
        """RNF-08 · CA-10 esc. 1 — dependencias sin avisos: exit 0, sin hallazgos y sin consultar a OSV."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "5.1"), dependencia("flask", "3.0"))
        )

        codigo, lineas, _, osv = self.ejecutar_main([ruta])

        self.assertEqual(0, codigo)
        self.assertEqual([], osv.consultas)
        self.assertEqual([], self.lineas_de(lineas, "django"))
        self.assertEqual([], self.lineas_de(lineas, "flask"))
        for etiqueta in ("BAJA", "MEDIA", "ALTA", "CRÍTICA", "DESCONOCIDA"):
            self.assertFalse([linea for linea in lineas if linea.startswith(etiqueta)], lineas)

    def test_tc35_informe_sin_dependencias_termina_en_0(self) -> None:
        """RNF-08 · CA-10 esc. 1 — `{"dependencies": []}` también es un informe limpio."""
        ruta = self.escribir_informe(informe_con())

        codigo, _, _, osv = self.ejecutar_main([ruta])

        self.assertEqual(0, codigo)
        self.assertEqual([], osv.consultas)

    def test_tc35_clasificar_sin_vulnerabilidades_devuelve_lista_vacia(self) -> None:
        """RNF-08 · CA-10 esc. 1 — `clasificar` no inventa hallazgos para una dependencia sin `vulns`."""
        modulo = self.sev()
        osv = OsvFalso()

        hallazgos = modulo.clasificar([dependencia("django", "5.1")], osv)

        self.assertEqual([], hallazgos)
        self.assertEqual([], osv.consultas)


# ---------------------------------------------------------------------------------------------------------
# TC-36 · el JSON no se puede leer
# ---------------------------------------------------------------------------------------------------------


class TestTc36InformeIlegible(PruebaBase):
    def test_tc36_json_inexistente_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — si `pip-audit` no dejó informe, el trabajo no pasa en verde: exit 2."""
        ruta = str(self.directorio / "no-existe.json")

        codigo, _, errores, osv = self.ejecutar_main([ruta])

        self.assertEqual(2, codigo)
        self.assertEqual([], osv.consultas)
        self.assertTrue(errores.strip(), "un fallo de lectura debe explicarse en stderr")

    def test_tc36_json_con_sintaxis_rota_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — un informe truncado no es un informe limpio: exit 2."""
        ruta = self.escribir_informe('{"dependencies": [{"name": "django", ')

        codigo, _, errores, _ = self.ejecutar_main([ruta])

        self.assertEqual(2, codigo)
        self.assertTrue(errores.strip(), "un fallo de lectura debe explicarse en stderr")

    def test_tc36_archivo_vacio_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — un informe vacío (por ejemplo, `pip-audit` murió antes de escribir): exit 2."""
        ruta = self.escribir_informe("")

        codigo, _, _, _ = self.ejecutar_main([ruta])

        self.assertEqual(2, codigo)

    def test_tc36_bytes_que_no_son_utf8_terminan_en_2(self) -> None:
        """RNF-08 · CA-10 — un archivo ilegible como texto termina en 2, no con una traza."""
        ruta = self.directorio / "binario.json"
        ruta.write_bytes(b"\xff\xfe\x00\x80\x81")

        codigo, _, _, _ = self.ejecutar_main([str(ruta)])

        self.assertEqual(2, codigo)


# ---------------------------------------------------------------------------------------------------------
# TC-37 · falla la consulta a OSV
# ---------------------------------------------------------------------------------------------------------


class TestTc37ErrorDeConsulta(PruebaBase):
    def test_tc37_error_de_red_en_la_consulta_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — si OSV no responde no se adivina la severidad: exit 2, nunca 0."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_MEDIA, [])]))
        )
        for error in (
            urllib.error.URLError("sin ruta al servidor"),
            TimeoutError("se agotó el tiempo"),
        ):
            with self.subTest(error=type(error).__name__):
                codigo, _, errores, _ = self.ejecutar_main([ruta], osv_lanza=error)

                self.assertEqual(2, codigo)
                self.assertTrue(errores.strip(), "un fallo de consulta debe explicarse en stderr")

    def test_tc37_error_de_consulta_no_se_oculta_tras_un_alto_ya_visto(self) -> None:
        """RNF-08 · CA-10 — un fallo de consulta en cualquier hallazgo cuenta aunque otro ya fuera ALTA."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("flask", "2.0", [vulnerabilidad(GHSA_ALTA, [])]),
                dependencia("requests", "2.0", [vulnerabilidad(GHSA_MEDIA, [])]),
            )
        )

        def consulta(identificador: str) -> dict:
            if identificador == GHSA_MEDIA:
                raise urllib.error.URLError("sin ruta al servidor")
            return respuesta_osv("HIGH")

        modulo = self.sev()
        with (
            mock.patch.object(modulo, "consultar_osv", consulta),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            codigo = modulo.main([ruta])

        self.assertEqual(2, codigo)

    def test_tc37_consultar_osv_pide_el_aviso_con_tiempo_limite_de_15_segundos(self) -> None:
        """RNF-08 · CA-10 — `consultar_osv` usa `URL_OSV` con el identificador, `urllib` y un timeout de 15 s."""
        modulo = self.sev()
        cuerpo = respuesta_osv("HIGH")

        with mock.patch(
            "urllib.request.urlopen", return_value=RespuestaHttpFalsa(cuerpo)
        ) as urlopen:
            respuesta = modulo.consultar_osv(GHSA_ALTA)

        self.assertEqual(cuerpo, respuesta)
        urlopen.assert_called_once()
        solicitud = urlopen.call_args.args[0]
        url = getattr(solicitud, "full_url", solicitud)
        self.assertEqual("https://api.osv.dev/v1/vulns/" + GHSA_ALTA, url)
        self.assertEqual(modulo.URL_OSV.format(GHSA_ALTA), url)
        timeout = urlopen.call_args.kwargs.get("timeout")
        if timeout is None and len(urlopen.call_args.args) >= 3:
            timeout = urlopen.call_args.args[2]
        self.assertEqual(15, timeout)

    def test_tc37_consultar_osv_deja_pasar_el_error_de_red(self) -> None:
        """RNF-08 · CA-10 — `consultar_osv` no se traga el error: lo decide `main`, que termina en 2."""
        modulo = self.sev()

        with (
            mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin ruta")),
            self.assertRaises(OSError),
        ):
            modulo.consultar_osv(GHSA_ALTA)


# ---------------------------------------------------------------------------------------------------------
# TC-38 · los dos formatos del informe
# ---------------------------------------------------------------------------------------------------------


class TestTc38Formatos(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.dependencias = [
            dependencia("limpio", "1.0"),
            dependencia(
                "django", "3.2", [vulnerabilidad("PYSEC-2024-100", ["CVE-2024-0001", GHSA_ALTA])]
            ),
        ]

    def test_tc38_leer_informe_acepta_el_objeto_con_dependencies(self) -> None:
        """RNF-08 · CA-10 — `{"dependencies": [...]}` es el formato actual de `pip-audit`."""
        modulo = self.sev()

        leidas = modulo.leer_informe(json.dumps({"dependencies": self.dependencias, "fixes": []}))

        self.assertEqual(self.dependencias, leidas)

    def test_tc38_leer_informe_acepta_la_lista_antigua(self) -> None:
        """RNF-08 · CA-10 — las versiones antiguas de `pip-audit` escribían la lista de dependencias sin envoltorio."""
        modulo = self.sev()

        leidas = modulo.leer_informe(json.dumps(self.dependencias))

        self.assertEqual(self.dependencias, leidas)

    def test_tc38_main_trata_igual_los_dos_formatos(self) -> None:
        """RNF-08 · CA-10 esc. 2 — un HIGH falla con el objeto y con la lista antigua, con la misma línea."""
        formatos = {
            "objeto": json.dumps({"dependencies": self.dependencias}),
            "lista": json.dumps(self.dependencias),
        }
        esperada = (
            f"ALTA  django 3.2  {GHSA_ALTA} (CVE-2024-0001, PYSEC-2024-100) {SUFIJO_QUE_FALLA}"
        )
        for nombre, texto in formatos.items():
            with self.subTest(formato=nombre):
                ruta = self.escribir_informe(texto, f"{nombre}.json")

                codigo, lineas, _, _ = self.ejecutar_main(
                    [ruta], OsvFalso({GHSA_ALTA: respuesta_osv("HIGH")})
                )

                self.assertEqual(1, codigo)
                self.assertIn(esperada, lineas)


if __name__ == "__main__":
    unittest.main()
