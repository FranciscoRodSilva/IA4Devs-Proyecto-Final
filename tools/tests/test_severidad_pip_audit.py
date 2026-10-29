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
import http.client
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


class RespuestaHttpConLimite:
    """Una respuesta HTTP de bytes crudos que respeta el límite de `read(n)` y recuerda cuánto se le pidió y cuánto se leyó."""

    def __init__(self, cuerpo: bytes) -> None:
        self._cuerpo = cuerpo
        self.posicion = 0
        self.lecturas: list[object] = []

    def __enter__(self) -> RespuestaHttpConLimite:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, tamano: int | None = -1) -> bytes:
        self.lecturas.append(tamano)
        fin = len(self._cuerpo) if tamano is None or tamano < 0 else self.posicion + tamano
        trozo = self._cuerpo[self.posicion : fin]
        self.posicion += len(trozo)
        return trozo


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

    def ejecutar_main_sin_traza(
        self,
        argv: list[str],
        osv: OsvFalso | None = None,
        osv_lanza: BaseException | None = None,
    ) -> tuple[int, list[str], str, OsvFalso]:
        """Como `ejecutar_main`, pero una excepción que escapa de `main` es un fallo de la prueba: `main` debe terminar con un código."""
        try:
            return self.ejecutar_main(argv, osv, osv_lanza)
        except AssertionError:
            raise
        except Exception as error:
            self.fail(
                f"main dejó escapar {type(error).__name__} en lugar de terminar con un código: {error!r}"
            )

    def ejecutar_main_con_http(
        self,
        argv: list[str],
        respuesta: object | None = None,
        lanza: BaseException | None = None,
    ) -> tuple[int, list[str], str, mock.Mock]:
        """Corre `main(argv)` con la `consultar_osv` REAL y `urlopen` sustituido por `respuesta` o por la excepción `lanza`."""
        modulo = self.sev()
        salida, errores = io.StringIO(), io.StringIO()
        parche = (
            mock.patch("urllib.request.urlopen", side_effect=lanza)
            if lanza is not None
            else mock.patch("urllib.request.urlopen", return_value=respuesta)
        )
        try:
            with (
                parche as urlopen,
                contextlib.redirect_stdout(salida),
                contextlib.redirect_stderr(errores),
            ):
                codigo = modulo.main(argv)
        except AssertionError:
            raise
        except Exception as error:
            self.fail(
                f"main dejó escapar {type(error).__name__} en lugar de terminar con un código: {error!r}"
            )
        lineas = [linea.rstrip() for linea in salida.getvalue().splitlines()]
        return codigo, lineas, errores.getvalue(), urlopen

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


# ---------------------------------------------------------------------------------------------------------
# Ciclo 1 de corrección · defectos reales (nacen en rojo)
# ---------------------------------------------------------------------------------------------------------


class TestPeorSeveridadEntreTodosLosGhsa(PruebaBase):
    """F001 · fallo abierto: un aviso con varios GHSA toma la severidad del peor, no la del primero."""

    def test_ca10_esc02_id_pysec_con_alias_ghsa_bajo_y_ghsa_alto_termina_en_1(self) -> None:
        """RNF-08 · CA-10 esc. 2 — `PYSEC-1` con alias [GHSA bajo, GHSA alto]: gana la peor, el pipeline falla."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_ALTA])])
            )
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_ALTA: respuesta_osv("HIGH")})

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("ALTA  django 3.2  "), propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])

    def test_ca10_esc02_clasificar_devuelve_la_peor_severidad_de_los_dos_ghsa(self) -> None:
        """RNF-08 · CA-10 esc. 2 — el hallazgo guarda HIGH aunque el primer GHSA de los alias sea LOW."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_ALTA: respuesta_osv("HIGH")})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_ALTA])])], osv
        )

        self.assertEqual(1, len(hallazgos))
        self.assertEqual("HIGH", hallazgos[0].severidad)

    def test_ca10_esc02_el_id_ghsa_bajo_mas_un_alias_ghsa_distinto_alto_termina_en_1(self) -> None:
        """RNF-08 · CA-10 esc. 2 — el id es un GHSA LOW y un alias GHSA distinto es HIGH: el alias no se ignora."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia(
                    "django", "3.2", [vulnerabilidad(GHSA_BAJA, ["CVE-2024-0001", GHSA_ALTA])]
                )
            )
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_ALTA: respuesta_osv("HIGH")})

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "django")[0].startswith("ALTA"), lineas)

    def test_ca10_esc02_tres_ghsa_con_el_peor_en_medio_termina_en_1_como_critica(self) -> None:
        """RNF-08 · CA-10 esc. 2 — [LOW, CRITICAL, MODERATE]: el peor no es ni el primero ni el último."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia(
                    "django",
                    "3.2",
                    [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_CRITICA, GHSA_MEDIA])],
                )
            )
        )
        osv = OsvFalso(
            {
                GHSA_BAJA: respuesta_osv("LOW"),
                GHSA_CRITICA: respuesta_osv("CRITICAL"),
                GHSA_MEDIA: respuesta_osv("MODERATE"),
            }
        )

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "django")[0].startswith("CRÍTICA"), lineas)

    def test_ca10_esc02_un_ghsa_que_consulta_bien_y_otro_sin_severidad_termina_en_1_como_desconocida(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — GHSA LOW junto a un GHSA cuya consulta no trae severidad: DESCONOCIDA, falla cerrado."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_ALTA])])
            )
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_ALTA: respuesta_osv(None)})

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(1, codigo)
        self.assertTrue(self.lineas_de(lineas, "django")[0].startswith("DESCONOCIDA"), lineas)

    def test_ca10_a3_cada_ghsa_distinto_se_consulta_una_sola_vez(self) -> None:
        """RNF-08 · CA-10 — GHSA repetidos entre el id y los alias se consultan una vez; los distintos, todos."""
        modulo = self.sev()
        casos = {
            "alias repetido": vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_ALTA, GHSA_BAJA]),
            "el id GHSA vuelve a aparecer en los alias": vulnerabilidad(
                GHSA_BAJA, [GHSA_BAJA, GHSA_ALTA]
            ),
        }
        for descripcion, caso in casos.items():
            with self.subTest(caso=descripcion):
                osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_ALTA: respuesta_osv("LOW")})

                modulo.clasificar([dependencia("django", "3.2", [caso])], osv)

                self.assertEqual(sorted([GHSA_BAJA, GHSA_ALTA]), sorted(osv.consultas))

    def test_ca10_esc03_control_varios_ghsa_bajos_o_medios_no_fallan(self) -> None:
        """RNF-08 · CA-10 esc. 3 — control: la corrección no sobre-falla; LOW y MODERATE juntos terminan en 0 como MEDIA."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_MEDIA])])
            )
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_MEDIA: respuesta_osv("MODERATE")})

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(0, codigo)
        self.assertTrue(self.lineas_de(lineas, "django")[0].startswith("MEDIA"), lineas)


class TestErroresDeConsultaYDeLecturaNoSonTraza(PruebaBase):
    """F002 · `main` termina con 2 y mensaje ante los errores de `http.client` y la recursión del JSON, no con traza."""

    ERRORES_HTTP = (
        http.client.IncompleteRead(b"parcial"),
        http.client.BadStatusLine("''"),
        http.client.HTTPException("fallo genérico de http.client"),
    )

    def _informe_con_un_ghsa(self) -> str:
        return self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )

    def test_ca10_a3_error_de_http_client_en_la_consulta_inyectada_termina_en_2_con_mensaje(
        self,
    ) -> None:
        """RNF-08 · CA-10 — IncompleteRead, BadStatusLine y HTTPException no son OSError: igual terminan en 2."""
        ruta = self._informe_con_un_ghsa()
        for error in self.ERRORES_HTTP:
            with self.subTest(error=type(error).__name__):
                codigo, _, errores, _ = self.ejecutar_main_sin_traza([ruta], osv_lanza=error)

                self.assertEqual(2, codigo)
                self.assertIn("falla la consulta a OSV", errores)

    def test_ca10_a3_error_de_http_client_en_urlopen_real_termina_en_2_con_mensaje(self) -> None:
        """RNF-08 · CA-10 — mismo caso por el camino real: `urlopen` lanza el error dentro de `consultar_osv`."""
        ruta = self._informe_con_un_ghsa()
        for error in self.ERRORES_HTTP:
            with self.subTest(error=type(error).__name__):
                codigo, _, errores, _ = self.ejecutar_main_con_http([ruta], lanza=error)

                self.assertEqual(2, codigo)
                self.assertIn("falla la consulta a OSV", errores)

    def test_ca10_a3_json_del_informe_anidado_100000_niveles_termina_en_2_con_mensaje(
        self,
    ) -> None:
        """RNF-08 · CA-10 — un informe con `[` anidado 100000 veces desborda la recursión de `json`: exit 2, no traza."""
        ruta = self.escribir_informe("[" * 100_000)

        codigo, _, errores, _ = self.ejecutar_main_sin_traza([ruta])

        self.assertEqual(2, codigo)
        self.assertIn("no se puede leer el informe", errores)

    def test_ca10_a3_respuesta_de_osv_anidada_100000_niveles_termina_en_2_con_mensaje(
        self,
    ) -> None:
        """RNF-08 · CA-10 — la misma recursión en la respuesta de OSV: exit 2 con «falla la consulta a OSV»."""
        ruta = self._informe_con_un_ghsa()

        codigo, _, errores, _ = self.ejecutar_main_con_http(
            [ruta], RespuestaHttpConLimite(b"[" * 100_000)
        )

        self.assertEqual(2, codigo)
        self.assertIn("falla la consulta a OSV", errores)


class TestAliasesConElementosQueNoSonCadena(PruebaBase):
    """F003 · un alias que no es cadena es un informe mal formado: exit 2 con mensaje, no `AttributeError` ni `TypeError`."""

    def test_ca10_a3_aliases_con_elementos_que_no_son_cadena_termina_en_2_con_mensaje(
        self,
    ) -> None:
        """RNF-08 · CA-10 — `[1]`, `[null]` y `["GHSA-x", 5]` no se entienden; no pasan en verde ni dan traza."""
        casos = {
            "[1]": [1],
            "[null]": [None],
            '["GHSA-x", 5]': [GHSA_BAJA, 5],
        }
        for descripcion, alias in casos.items():
            with self.subTest(aliases=descripcion):
                ruta = self.escribir_informe(
                    informe_con(dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", alias)]))
                )

                codigo, _, errores, _ = self.ejecutar_main_sin_traza(
                    [ruta], OsvFalso(por_omision=respuesta_osv("LOW"))
                )

                self.assertEqual(2, codigo)
                self.assertTrue(errores.strip(), "un informe mal formado debe explicarse en stderr")

    def test_ca10_a3_leer_informe_rechaza_un_alias_que_no_es_cadena(self) -> None:
        """RNF-08 · CA-10 — la validación vive en `leer_informe`: lanza `ValueError`, que `main` convierte en 2."""
        modulo = self.sev()
        for alias in ([1], [None], [GHSA_BAJA, 5]):
            with self.subTest(aliases=alias), self.assertRaises(ValueError):
                modulo.leer_informe(
                    informe_con(dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", alias)]))
                )


class TestTopeDeLecturaDeLaRespuestaDeOsv(PruebaBase):
    """F004 de seguridad · `consultar_osv` lee a lo sumo 1.000.000 de bytes: una respuesta mayor no agota la memoria."""

    TOPE = 1_000_000

    @classmethod
    def cuerpo_de(cls, tamano: int) -> bytes:
        """Un JSON válido de OSV con `HIGH` y exactamente `tamano` bytes: solo el tope puede rechazarlo."""
        prefijo = b'{"database_specific": {"severity": "HIGH"}, "relleno": "'
        sufijo = b'"}'
        cuerpo = prefijo + b"x" * (tamano - len(prefijo) - len(sufijo)) + sufijo
        assert len(cuerpo) == tamano
        return cuerpo

    def test_ca10_a3_respuesta_de_un_millon_y_un_bytes_se_rechaza_con_value_error(self) -> None:
        """RNF-08 · CA-10 — 1.000.001 bytes superan el tope aunque sean JSON válido: `ValueError`."""
        modulo = self.sev()
        respuesta = RespuestaHttpConLimite(self.cuerpo_de(self.TOPE + 1))

        with (
            mock.patch("urllib.request.urlopen", return_value=respuesta),
            self.assertRaises(ValueError),
        ):
            modulo.consultar_osv(GHSA_ALTA)

    def test_ca10_a3_respuesta_de_un_millon_exacto_de_bytes_se_acepta(self) -> None:
        """RNF-08 · CA-10 — control del borde: 1.000.000 bytes exactos pasan, el tope no es `>=`."""
        modulo = self.sev()
        respuesta = RespuestaHttpConLimite(self.cuerpo_de(self.TOPE))

        with mock.patch("urllib.request.urlopen", return_value=respuesta):
            datos = modulo.consultar_osv(GHSA_ALTA)

        self.assertEqual("HIGH", datos["database_specific"]["severity"])

    def test_ca10_a3_read_se_llama_siempre_con_un_limite_y_no_se_lee_todo_un_cuerpo_enorme(
        self,
    ) -> None:
        """RNF-08 · CA-10 — con 5 MB en la respuesta, `read` recibe un límite entero y se consume a lo sumo tope + 1 byte."""
        modulo = self.sev()
        respuesta = RespuestaHttpConLimite(self.cuerpo_de(5_000_000))

        with (
            mock.patch("urllib.request.urlopen", return_value=respuesta),
            self.assertRaises(ValueError),
        ):
            modulo.consultar_osv(GHSA_ALTA)

        self.assertTrue(respuesta.lecturas, "consultar_osv no leyó la respuesta")
        for limite in respuesta.lecturas:
            self.assertIsInstance(limite, int, f"read se llamó sin límite: {respuesta.lecturas}")
            self.assertGreater(limite, 0, f"read se llamó sin límite: {respuesta.lecturas}")
        self.assertLessEqual(sum(respuesta.lecturas), self.TOPE + 1)
        self.assertLessEqual(respuesta.posicion, self.TOPE + 1)

    def test_ca10_a3_main_con_una_respuesta_de_osv_demasiado_grande_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — de punta a punta: la respuesta de 1.000.001 bytes es un fallo de consulta, no un HIGH ni un 0."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )

        codigo, _, errores, _ = self.ejecutar_main_con_http(
            [ruta], RespuestaHttpConLimite(self.cuerpo_de(self.TOPE + 1))
        )

        self.assertEqual(2, codigo)
        self.assertIn("falla la consulta a OSV", errores)


# ---------------------------------------------------------------------------------------------------------
# Ciclo 1 de corrección · mutantes vivos del auditor (el código ya es correcto: nacen en verde)
# ---------------------------------------------------------------------------------------------------------


class TestMutantesDeLaValidacionDelInforme(PruebaBase):
    """Mutantes 1 a 5 y 11: cada validación de `leer_informe` termina en 2 y no deja pasar un informe mal formado."""

    def _exigir_exit_2(self, texto: str, osv: OsvFalso | None = None) -> None:
        ruta = self.escribir_informe(texto)

        codigo, _, errores, consultas = self.ejecutar_main_sin_traza(
            [ruta], osv or OsvFalso(por_omision=respuesta_osv("LOW"))
        )

        self.assertEqual(2, codigo)
        self.assertTrue(errores.strip(), "un informe mal formado debe explicarse en stderr")
        self.assertEqual([], consultas.consultas)

    def test_ca10_a3_dependencia_con_vulnerabilidades_sin_nombre_o_version_termina_en_2(
        self,
    ) -> None:
        """RNF-08 · CA-10 — sin `name` o `version` no se puede nombrar el hallazgo: exit 2, no un `KeyError`."""
        vulns = [vulnerabilidad(GHSA_ALTA, [])]
        casos = {
            "sin name": {"version": "3.2", "vulns": vulns},
            "sin version": {"name": "django", "vulns": vulns},
            "name no es cadena": {"name": 5, "version": "3.2", "vulns": vulns},
            "version nula": {"name": "django", "version": None, "vulns": vulns},
        }
        for descripcion, entrada in casos.items():
            with self.subTest(caso=descripcion):
                self._exigir_exit_2(json.dumps({"dependencies": [entrada]}))

    def test_ca10_a3_json_que_no_es_una_lista_de_dependencias_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — `{}`, `{"dependencies": null}`, una cadena suelta y demás formas ajenas no son un informe limpio."""
        casos = {
            "objeto vacío": "{}",
            "dependencies nulo": '{"dependencies": null}',
            "dependencies es un objeto": '{"dependencies": {}}',
            "dependencies es una cadena": '{"dependencies": "django"}',
            "cadena suelta": '"suelta"',
            "número": "5",
            "null": "null",
            "lista de cadenas": '["django"]',
            "lista de enteros dentro del objeto": '{"dependencies": [1]}',
            "lista con un nulo": '{"dependencies": [null]}',
        }
        for descripcion, texto in casos.items():
            with self.subTest(forma=descripcion):
                self._exigir_exit_2(texto)

    def test_ca10_a3_vulns_que_no_es_una_lista_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — un `vulns` nulo, vacío-falsy o escalar no se toma por «sin vulnerabilidades»: exit 2."""
        for valor in (None, {}, "", 0, 5, "texto", {"id": GHSA_ALTA}, False):
            with self.subTest(vulns=valor):
                self._exigir_exit_2(
                    json.dumps(
                        {"dependencies": [{"name": "django", "version": "3.2", "vulns": valor}]}
                    )
                )

    def test_ca10_a3_vulnerabilidad_sin_id_cadena_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — un `id` ausente, nulo o numérico, o una vulnerabilidad que no es objeto: exit 2."""
        casos = {
            "id numérico": {"id": 5, "aliases": []},
            "id nulo": {"id": None, "aliases": []},
            "sin id": {"aliases": [GHSA_ALTA]},
            "id lista": {"id": [GHSA_ALTA], "aliases": []},
            "la vulnerabilidad es una cadena": GHSA_ALTA,
            "la vulnerabilidad es nula": None,
        }
        for descripcion, vuln in casos.items():
            with self.subTest(caso=descripcion):
                self._exigir_exit_2(
                    json.dumps(
                        {"dependencies": [{"name": "django", "version": "3.2", "vulns": [vuln]}]}
                    )
                )

    def test_ca10_a3_aliases_que_no_es_una_lista_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — `aliases` como cadena, nulo, número o mapa no se reinterpreta: exit 2."""
        for valor in (GHSA_ALTA, None, 5, {}, {GHSA_ALTA: 1}):
            with self.subTest(aliases=valor):
                entrada = {
                    "name": "django",
                    "version": "3.2",
                    "vulns": [{"id": "PYSEC-1", "aliases": valor}],
                }
                self._exigir_exit_2(json.dumps({"dependencies": [entrada]}))

    def test_ca10_esc01_dependencia_sin_la_clave_vulns_no_falla(self) -> None:
        """RNF-08 · CA-10 esc. 1 — `pip-audit` omite `vulns` en dependencias omitidas (`skip_reason`): exit 0 sin consultar."""
        omitida = {
            "name": "proyecto-local",
            "skip_reason": "Dependency not found on PyPI and could not be audited",
        }
        informes = {
            "sin vulns, con nombre y versión": {"name": "django", "version": "5.1"},
            "omitida, sin versión": omitida,
            "objeto vacío": {},
        }
        for descripcion, entrada in informes.items():
            with self.subTest(caso=descripcion):
                ruta = self.escribir_informe(json.dumps({"dependencies": [entrada]}))

                codigo, lineas, _, osv = self.ejecutar_main_sin_traza([ruta])

                self.assertEqual(0, codigo)
                self.assertEqual([], osv.consultas)
                self.assertEqual(["Sin vulnerabilidades en el informe de pip-audit."], lineas)

    def test_ca10_esc01_clasificar_y_leer_informe_aceptan_una_dependencia_sin_vulns(self) -> None:
        """RNF-08 · CA-10 esc. 1 — la ausencia de `vulns` se tolera en `leer_informe` y en `clasificar`, cada una por su cuenta."""
        modulo = self.sev()
        sin_vulns = [{"name": "django", "version": "5.1"}]

        leidas = modulo.leer_informe(json.dumps(sin_vulns))
        hallazgos = modulo.clasificar(sin_vulns, OsvFalso())

        self.assertEqual(sin_vulns, leidas)
        self.assertEqual([], hallazgos)


class TestMutantesDeLaRespuestaDeOsv(PruebaBase):
    """Mutantes 6 y 7: lo que OSV devuelve y no se entiende es DESCONOCIDA (falla, 1) o fallo de consulta (2)."""

    RESPUESTAS_SIN_FORMA = {
        "lista": [],
        "lista con un aviso dentro": [respuesta_osv("LOW")],
        "nulo": None,
        "cadena": "HIGH",
        "número": 5,
        "database_specific es una lista": {"database_specific": ["HIGH"]},
        "database_specific es una cadena": {"database_specific": "HIGH"},
        "database_specific es nulo": {"database_specific": None},
        "severity numérica": {"database_specific": {"severity": 5}},
        "severity nula": {"database_specific": {"severity": None}},
        "severity es una lista": {"database_specific": {"severity": ["HIGH"]}},
        "severity vacía": {"database_specific": {"severity": ""}},
        "severity no reconocida": {"database_specific": {"severity": "SEVERE"}},
    }

    def test_ca10_esc02_clasificar_marca_desconocida_una_respuesta_sin_la_forma_esperada(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — ninguna respuesta rara de OSV lanza ni se promueve a una severidad conocida."""
        modulo = self.sev()
        for descripcion, respuesta in self.RESPUESTAS_SIN_FORMA.items():
            with self.subTest(respuesta=descripcion):
                osv = OsvFalso({GHSA_ALTA: respuesta})  # type: ignore[dict-item]

                hallazgos = modulo.clasificar(
                    [dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])])], osv
                )

                self.assertEqual("DESCONOCIDA", hallazgos[0].severidad)

    def test_ca10_esc02_main_termina_en_1_ante_una_respuesta_de_osv_sin_la_forma_esperada(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — una lista o `null` en lugar del objeto de OSV: exit 1 con la línea DESCONOCIDA, no traza."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )
        for descripcion, respuesta in self.RESPUESTAS_SIN_FORMA.items():
            with self.subTest(respuesta=descripcion):
                codigo, lineas, _, _ = self.ejecutar_main_sin_traza(
                    [ruta],
                    OsvFalso({GHSA_ALTA: respuesta}),  # type: ignore[dict-item]
                )

                self.assertEqual(1, codigo)
                self.assertEqual(
                    f"DESCONOCIDA  django 3.2  {GHSA_ALTA} {SUFIJO_QUE_FALLA}",
                    self.lineas_de(lineas, "django")[0],
                )

    def test_ca10_esc02_por_el_camino_real_un_json_valido_que_no_es_objeto_termina_en_1(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — con `consultar_osv` real, `[]` o `null` válidos como JSON son DESCONOCIDA, exit 1."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )
        for cuerpo in (b"[]", b"null", b'"HIGH"', b"5"):
            with self.subTest(cuerpo=cuerpo):
                codigo, lineas, _, _ = self.ejecutar_main_con_http(
                    [ruta], RespuestaHttpConLimite(cuerpo)
                )

                self.assertEqual(1, codigo)
                self.assertTrue(
                    self.lineas_de(lineas, "django")[0].startswith("DESCONOCIDA"), lineas
                )

    def test_ca10_a3_respuesta_de_osv_que_no_es_json_termina_en_2(self) -> None:
        """RNF-08 · CA-10 — HTML de un proxy, cuerpo vacío o bytes que no son UTF-8: fallo de consulta, exit 2, nunca 0 ni 1."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_ALTA, [])]))
        )
        cuerpos = {
            "html": b"<html><body>502 Bad Gateway</body></html>",
            "vacío": b"",
            "texto suelto": b"HIGH",
            "JSON truncado": b'{"database_specific": {"severity": ',
            "bytes que no son UTF-8": b"\xff\xfe\x00\x80\x81",
        }
        for descripcion, cuerpo in cuerpos.items():
            with self.subTest(cuerpo=descripcion):
                codigo, lineas, errores, _ = self.ejecutar_main_con_http(
                    [ruta], RespuestaHttpConLimite(cuerpo)
                )

                self.assertEqual(2, codigo)
                self.assertIn("falla la consulta a OSV", errores)
                self.assertEqual([], self.lineas_de(lineas, "django"))


class TestMutantesDeLaSalida(PruebaBase):
    """Mutantes 8, 9 y 10: el resumen, la URL consultada y el paréntesis de alias, con el texto exacto."""

    def test_ca10_esc02_la_linea_de_resumen_afirma_los_dos_numeros_exactos(self) -> None:
        """RNF-08 · CA-10 esc. 2 — 3 hallazgos, 2 que fallan: `Hallazgos: 3 · que fallan el pipeline: 2`, en ese orden."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("flask", "2.0", [vulnerabilidad(GHSA_ALTA, [])]),
                dependencia("requests", "2.0", [vulnerabilidad(GHSA_MEDIA, [])]),
                dependencia("django", "3.2", [vulnerabilidad(GHSA_CRITICA, [])]),
            )
        )
        osv = OsvFalso(
            {
                GHSA_ALTA: respuesta_osv("HIGH"),
                GHSA_MEDIA: respuesta_osv("MODERATE"),
                GHSA_CRITICA: respuesta_osv("CRITICAL"),
            }
        )

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(1, codigo)
        self.assertEqual("Hallazgos: 3 · que fallan el pipeline: 2", lineas[-1])

    def test_ca10_esc03_la_linea_de_resumen_sin_fallos_dice_cero(self) -> None:
        """RNF-08 · CA-10 esc. 3 — 2 hallazgos y ninguno falla: `Hallazgos: 2 · que fallan el pipeline: 0` y exit 0."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia("flask", "2.0", [vulnerabilidad(GHSA_BAJA, [])]),
                dependencia("requests", "2.0", [vulnerabilidad(GHSA_MEDIA, [])]),
            )
        )
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_MEDIA: respuesta_osv("MODERATE")})

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        self.assertEqual(0, codigo)
        self.assertEqual("Hallazgos: 2 · que fallan el pipeline: 0", lineas[-1])

    def test_ca10_a3_el_identificador_se_codifica_entero_en_la_url_consultada(self) -> None:
        """RNF-08 · CA-10 — `/`, `?`, `#`, espacio y `%` del identificador no abren ruta, consulta ni fragmento de la URL."""
        modulo = self.sev()
        casos = {
            "GHSA-a/b": "GHSA-a%2Fb",
            "GHSA-a?b=c": "GHSA-a%3Fb%3Dc",
            "GHSA-a#b": "GHSA-a%23b",
            "GHSA-a b": "GHSA-a%20b",
            "GHSA-a%b": "GHSA-a%25b",
            "../../v1/query": "..%2F..%2Fv1%2Fquery",
        }
        for identificador, codificado in casos.items():
            with self.subTest(identificador=identificador):
                with mock.patch(
                    "urllib.request.urlopen", return_value=RespuestaHttpConLimite(b"{}")
                ) as urlopen:
                    modulo.consultar_osv(identificador)

                solicitud = urlopen.call_args.args[0]
                self.assertEqual(
                    "https://api.osv.dev/v1/vulns/" + codificado,
                    getattr(solicitud, "full_url", solicitud),
                )

    def _linea_de(self, identificador: str, alias: list[str], severidad: str) -> str:
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(identificador, alias)]))
        )
        osv = OsvFalso(por_omision=respuesta_osv(severidad))

        _, lineas, _, _ = self.ejecutar_main_sin_traza([ruta], osv)

        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        return propias[0]

    def test_ca10_a3_el_id_repetido_entre_los_alias_no_se_repite_en_el_parentesis(self) -> None:
        """RNF-08 · CA-10 — id `PYSEC-1` que también figura en los alias: `GHSA (PYSEC-1)`, sin `PYSEC-1, PYSEC-1`."""
        linea = self._linea_de("PYSEC-1", ["PYSEC-1", GHSA_ALTA], "HIGH")

        self.assertEqual(f"ALTA  django 3.2  {GHSA_ALTA} (PYSEC-1) {SUFIJO_QUE_FALLA}", linea)

    def test_ca10_a3_el_id_ghsa_va_de_cabeza_y_no_se_repite_en_el_parentesis(self) -> None:
        """RNF-08 · CA-10 — id GHSA con un alias CVE: `GHSA (CVE)`; el id no se añade a sí mismo."""
        linea = self._linea_de(GHSA_ALTA, ["CVE-2024-0001"], "HIGH")

        self.assertEqual(f"ALTA  django 3.2  {GHSA_ALTA} (CVE-2024-0001) {SUFIJO_QUE_FALLA}", linea)

    def test_ca10_a3_el_ghsa_repetido_en_los_alias_no_se_repite_en_el_parentesis(self) -> None:
        """RNF-08 · CA-10 — id GHSA que también está en sus alias: la cabeza no reaparece entre paréntesis."""
        linea = self._linea_de(GHSA_ALTA, [GHSA_ALTA, "CVE-2024-0001"], "HIGH")

        self.assertEqual(f"ALTA  django 3.2  {GHSA_ALTA} (CVE-2024-0001) {SUFIJO_QUE_FALLA}", linea)

    def test_ca10_a3_sin_ghsa_la_cabeza_es_el_id_y_los_alias_van_entre_parentesis(self) -> None:
        """RNF-08 · CA-10 · A-3 (robustez del filtro) — sin GHSA: `PYSEC-2 (CVE-2)`; sin alias, sin paréntesis."""
        con_alias = self._linea_de("PYSEC-2", ["CVE-2024-0002"], "LOW")
        sin_alias = self._linea_de("PYSEC-2", [], "LOW")

        self.assertEqual(
            f"DESCONOCIDA  django 3.2  PYSEC-2 (CVE-2024-0002) {SUFIJO_QUE_FALLA}", con_alias
        )
        self.assertEqual(f"DESCONOCIDA  django 3.2  PYSEC-2 {SUFIJO_QUE_FALLA}", sin_alias)


class TestMutantesDeLaCodificacion(PruebaBase):
    """Mutantes 12 y 13: el informe se lee como UTF-8 y la salida se escribe como UTF-8, sea cual sea la codificación local."""

    def test_ca10_a3_el_informe_se_lee_con_encoding_utf8_explicito(self) -> None:
        """RNF-08 · CA-10 — `read_text` recibe `encoding="utf-8"`: no se depende de la codificación de la plataforma."""
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_BAJA, [])]))
        )
        original = Path.read_text
        llamadas: list[tuple[tuple, dict]] = []

        def espia(ruta_leida: Path, *args: object, **kwargs: object) -> str:
            llamadas.append((args, kwargs))
            return original(ruta_leida, *args, **kwargs)

        with mock.patch.object(Path, "read_text", espia):
            codigo, _, _, _ = self.ejecutar_main_sin_traza(
                [ruta], OsvFalso({GHSA_BAJA: respuesta_osv("LOW")})
            )

        self.assertEqual(0, codigo)
        self.assertEqual(1, len(llamadas), llamadas)
        args, kwargs = llamadas[0]
        self.assertEqual("utf-8", kwargs.get("encoding", args[0] if args else None))

    def test_ca10_a3_un_informe_con_caracteres_no_ascii_se_lee_bien(self) -> None:
        """RNF-08 · CA-10 — «descripción» con acentos y un nombre con `Ł` (UTF-8 `C5 81`, ilegible en cp1252) llegan intactos."""
        nombre = "paquete-Łódź"
        entrada = dependencia(nombre, "1.0", [vulnerabilidad(GHSA_BAJA, [])])
        entrada["vulns"][0]["description"] = "Descripción con acentos: señal, año, ñandú, 日本語"
        ruta = self.escribir_informe(informe_con(entrada))

        codigo, lineas, _, _ = self.ejecutar_main_sin_traza(
            [ruta], OsvFalso({GHSA_BAJA: respuesta_osv("LOW")})
        )

        self.assertEqual(0, codigo)
        self.assertIn(f"BAJA  {nombre} 1.0  {GHSA_BAJA}", lineas)

    @staticmethod
    def _flujo_ascii() -> tuple[io.BytesIO, io.TextIOWrapper]:
        """Un flujo que se parece a la consola de Windows: su codificación no puede escribir `→`, `Í` ni `«`."""
        bruto = io.BytesIO()
        return bruto, io.TextIOWrapper(bruto, encoding="ascii", newline="\n", write_through=True)

    def test_ca10_a3_la_salida_estandar_se_escribe_en_utf8_aunque_la_consola_sea_ascii(
        self,
    ) -> None:
        """RNF-08 · CA-10 — `→` y `Í` salen como UTF-8 por stdout aunque la codificación inicial del flujo no los admita."""
        modulo = self.sev()
        ruta = self.escribir_informe(
            informe_con(dependencia("django", "3.2", [vulnerabilidad(GHSA_CRITICA, [])]))
        )
        bruto_salida, salida = self._flujo_ascii()
        bruto_errores, errores = self._flujo_ascii()

        with (
            mock.patch.object(
                modulo, "consultar_osv", OsvFalso({GHSA_CRITICA: respuesta_osv("CRITICAL")})
            ),
            contextlib.redirect_stdout(salida),
            contextlib.redirect_stderr(errores),
        ):
            codigo = modulo.main([ruta])

        self.assertEqual(1, codigo)
        texto = bruto_salida.getvalue().decode("utf-8")
        self.assertIn(f"CRÍTICA  django 3.2  {GHSA_CRITICA} {SUFIJO_QUE_FALLA}", texto.splitlines())

    def test_ca10_a3_la_salida_de_errores_se_escribe_en_utf8_aunque_la_consola_sea_ascii(
        self,
    ) -> None:
        """RNF-08 · CA-10 — `_salida_utf8` reconfigura también stderr: un mensaje con `«` o `→` sale como UTF-8."""
        modulo = self.sev()
        texto = "«vulns» → Í"
        bruto_salida, salida = self._flujo_ascii()
        bruto_errores, errores = self._flujo_ascii()

        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            modulo._salida_utf8()
            print(texto)
            print(texto, file=sys.stderr)

        self.assertEqual(texto + "\n", bruto_salida.getvalue().decode("utf-8"))
        self.assertEqual(texto + "\n", bruto_errores.getvalue().decode("utf-8"))

    def test_ca10_a3_un_flujo_que_no_es_textiowrapper_no_se_toca(self) -> None:
        """RNF-08 · CA-10 — un `StringIO` no tiene `reconfigure`: `_salida_utf8` lo deja como está, sin lanzar."""
        modulo = self.sev()
        salida, errores = io.StringIO(), io.StringIO()

        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            modulo._salida_utf8()
            print("«→Í»")

        self.assertEqual("«→Í»\n", salida.getvalue())


# ---------------------------------------------------------------------------------------------------------
# Ciclo 2 de corrección · huecos de prueba (el código ya es correcto: nacen en verde, cada uno mata un mutante)
# ---------------------------------------------------------------------------------------------------------


class TestDesconocidaPesaMasQueModerate(PruebaBase):
    """F007 · `DESCONOCIDA` es peor que `MODERATE` en `ORDEN_DE_GRAVEDAD`, sin importar el orden de los GHSA."""

    def _linea_de_django(
        self, ghsa_primero: str, ghsa_segundo: str, respuestas: dict, ghsa_esperado: str
    ) -> None:
        """`ghsa_esperado` es el GHSA sin severidad: el que decide y el que debe aparecer en la línea."""
        ruta = self.escribir_informe(
            informe_con(
                dependencia(
                    "django", "3.2", [vulnerabilidad("PYSEC-1", [ghsa_primero, ghsa_segundo])]
                )
            )
        )

        codigo, lineas, _, osv = self.ejecutar_main_sin_traza([ruta], OsvFalso(respuestas))

        self.assertEqual(1, codigo)
        propias = self.lineas_de(lineas, "django")
        self.assertEqual(1, len(propias), lineas)
        self.assertTrue(propias[0].startswith("DESCONOCIDA"), propias[0])
        self.assertTrue(propias[0].endswith(SUFIJO_QUE_FALLA), propias[0])
        # La línea nombra los dos GHSA (el segundo entre paréntesis, como alias): solo la cabeza dice cuál decidió.
        self.assertIn(f"django 3.2  {ghsa_esperado}", propias[0])
        self.assertEqual([ghsa_primero, ghsa_segundo], osv.consultas)

    def test_ca10_esc02_moderate_y_despues_un_ghsa_sin_severidad_termina_en_1_como_desconocida(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — [MODERATE, sin severidad]: la severidad ausente no se pierde tras el MODERATE."""
        self._linea_de_django(
            GHSA_MEDIA,
            GHSA_ALTA,
            {GHSA_MEDIA: respuesta_osv("MODERATE"), GHSA_ALTA: respuesta_osv(None)},
            ghsa_esperado=GHSA_ALTA,
        )

    def test_ca10_esc02_un_ghsa_sin_severidad_y_despues_moderate_termina_en_1_como_desconocida(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — [sin severidad, MODERATE]: el MODERATE posterior no rebaja la severidad ausente."""
        self._linea_de_django(
            GHSA_ALTA,
            GHSA_MEDIA,
            {GHSA_ALTA: respuesta_osv(None), GHSA_MEDIA: respuesta_osv("MODERATE")},
            ghsa_esperado=GHSA_ALTA,
        )


class TestSeleccionDelAvisoEnLaPeorSeveridad(PruebaBase):
    """F008 · `Hallazgo.aviso` es el GHSA que decidió la severidad: el primero en un empate, y solo se corta en HIGH o CRITICAL."""

    def test_ca10_a3_empate_de_dos_ghsa_low_conserva_el_primero_como_aviso_y_consulta_los_dos(
        self,
    ) -> None:
        """RNF-08 · CA-10 — [LOW, LOW]: gana el primero (`<`, no `<=`); LOW no corta, así que se consulta también el segundo."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_BAJA: respuesta_osv("LOW"), GHSA_OTRO: respuesta_osv("LOW")})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_OTRO])])], osv
        )

        self.assertEqual(1, len(hallazgos))
        self.assertEqual(GHSA_BAJA, hallazgos[0].aviso)
        self.assertEqual("LOW", hallazgos[0].severidad)
        self.assertEqual([GHSA_BAJA, GHSA_OTRO], osv.consultas)

    def test_ca10_a3_ghsa_sin_severidad_y_despues_high_no_corta_y_el_aviso_es_el_segundo(
        self,
    ) -> None:
        """RNF-08 · CA-10 — [sin severidad, HIGH]: DESCONOCIDA no corta la consulta; gana el HIGH y su GHSA es el aviso."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_BAJA: respuesta_osv(None), GHSA_ALTA: respuesta_osv("HIGH")})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_ALTA])])], osv
        )

        self.assertEqual(1, len(hallazgos))
        self.assertEqual("HIGH", hallazgos[0].severidad)
        self.assertEqual(GHSA_ALTA, hallazgos[0].aviso)
        self.assertEqual([GHSA_BAJA, GHSA_ALTA], osv.consultas)

    def test_ca10_esc02_empate_de_dos_ghsa_sin_severidad_conserva_el_primero_como_aviso(
        self,
    ) -> None:
        """RNF-08 · CA-10 esc. 2 — [sin severidad, sin severidad]: DESCONOCIDA empata consigo misma y gana el primer GHSA."""
        modulo = self.sev()
        osv = OsvFalso({GHSA_BAJA: respuesta_osv(None), GHSA_OTRO: respuesta_osv(None)})

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad("PYSEC-1", [GHSA_BAJA, GHSA_OTRO])])], osv
        )

        self.assertEqual(1, len(hallazgos))
        self.assertEqual(modulo.DESCONOCIDA, hallazgos[0].severidad)
        self.assertEqual(GHSA_BAJA, hallazgos[0].aviso)
        self.assertEqual([GHSA_BAJA, GHSA_OTRO], osv.consultas)


class TestBordesDelPrefijoGhsaYDelTopeDeLectura(PruebaBase):
    """Observaciones baratas del auditor: reconocimiento del prefijo GHSA y borde exacto del tope de lectura."""

    def test_ca10_a3_un_ghsa_en_minusculas_no_se_reconoce_no_se_consulta_y_es_desconocida(
        self,
    ) -> None:
        """RNF-08 · CA-10 — `ghsa-abcd-efgh-ijkl` no es un GHSA (el prefijo distingue mayúsculas): sin consulta, DESCONOCIDA, exit 1."""
        minuscula = "ghsa-abcd-efgh-ijkl"
        casos = {
            "como alias": vulnerabilidad("PYSEC-1", [minuscula]),
            "como id": vulnerabilidad(minuscula, []),
        }
        for descripcion, caso in casos.items():
            with self.subTest(caso=descripcion):
                ruta = self.escribir_informe(informe_con(dependencia("django", "3.2", [caso])))
                osv = OsvFalso(por_omision=respuesta_osv("LOW"))

                codigo, lineas, _, osv = self.ejecutar_main_sin_traza([ruta], osv)

                self.assertEqual(1, codigo)
                self.assertEqual([], osv.consultas)
                propias = self.lineas_de(lineas, "django")
                self.assertEqual(1, len(propias), lineas)
                self.assertTrue(propias[0].startswith("DESCONOCIDA"), propias[0])

    def test_ca10_a3_respuesta_de_un_millon_y_un_bytes_con_json_valido_al_inicio_se_rechaza(
        self,
    ) -> None:
        """RNF-08 · CA-10 — JSON válido seguido de espacios hasta 1.000.001 bytes: el primer millón se parsearía, pero el exceso se detecta."""
        modulo = self.sev()
        valido = b'{"database_specific": {"severity": "HIGH"}}'
        cuerpo = valido + b" " * (TestTopeDeLecturaDeLaRespuestaDeOsv.TOPE + 1 - len(valido))
        self.assertEqual(TestTopeDeLecturaDeLaRespuestaDeOsv.TOPE + 1, len(cuerpo))

        with (
            mock.patch("urllib.request.urlopen", return_value=RespuestaHttpConLimite(cuerpo)),
            self.assertRaisesRegex(ValueError, "supera"),
        ):
            modulo.consultar_osv(GHSA_ALTA)

    def test_ca10_a3_un_id_con_el_texto_ghsa_pegado_sin_guion_no_es_un_ghsa(self) -> None:
        """RNF-08 · CA-10 — `GHSAabcd` no lleva el guion del prefijo `GHSA-`: no se consulta y el hallazgo es DESCONOCIDA."""
        modulo = self.sev()
        osv = OsvFalso(por_omision=respuesta_osv("LOW"))

        hallazgos = modulo.clasificar(
            [dependencia("django", "3.2", [vulnerabilidad("GHSAabcd", [])])], osv
        )

        self.assertEqual(1, len(hallazgos))
        self.assertIsNone(hallazgos[0].aviso)
        self.assertEqual("DESCONOCIDA", hallazgos[0].severidad)
        self.assertEqual([], osv.consultas)


if __name__ == "__main__":
    unittest.main()
