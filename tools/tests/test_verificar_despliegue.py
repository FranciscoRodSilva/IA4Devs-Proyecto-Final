"""Pruebas de tools/verificar_despliegue.py · TKT-070 · TC-U1…TC-U12."""

from __future__ import annotations

import http.client
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest import mock

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

import verificar_despliegue as vd  # noqa: E402

SALIDA_PS_LOCAL = (
    "cimenta-sonda-db-1\t127.0.0.1:55433->5432/tcp\n"
    "cimenta-sonda-expuesta\t0.0.0.0:55435->5432/tcp\n"
)

SALIDA_PS_IPV6 = "cimenta-sonda-expuesta\t0.0.0.0:55435->5432/tcp, [::]:55435->5432/tcp\n"

SALIDA_PS_CADDY = "cimenta-caddy-caddy-1\t0.0.0.0:80->80/tcp, 443/tcp\n"

SALIDA_SS = """State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
LISTEN 0      4096   127.0.0.1:5433      0.0.0.0:*
LISTEN 0      4096   0.0.0.0:5435        0.0.0.0:*
LISTEN 0      4096   *:5435              0.0.0.0:*
LISTEN 0      4096   [::]:5435           [::]:*
LISTEN 0      4096   0.0.0.0:22          0.0.0.0:*
"""


class TestExposicionesDocker(unittest.TestCase):
    def test_tkt070_tc_u1_solo_bucle_local_vacio(self) -> None:
        salida = "cimenta-prod-db-1\t127.0.0.1:5433->5432/tcp\n"
        self.assertEqual(vd.exposiciones_docker(salida), [])

    def test_tkt070_tc_u2_publicacion_en_todas_las_interfaces(self) -> None:
        resultado = vd.exposiciones_docker(SALIDA_PS_IPV6)
        self.assertEqual(len(resultado), 2)
        for exposicion in resultado:
            self.assertEqual(exposicion.puerto_anfitrion, 55435)
            self.assertEqual(exposicion.contenedor, "cimenta-sonda-expuesta")

    def test_tkt070_tc_u3_ignora_caddy_y_puertos_sin_publicar(self) -> None:
        salida = SALIDA_PS_CADDY + "cimenta-test-db-1\t5432/tcp\n"
        self.assertEqual(vd.exposiciones_docker(salida), [])

    def test_tkt070_tc_u3b_rango_de_puertos_con_5432(self) -> None:
        salida = "cimenta-sonda-expuesta\t0.0.0.0:5432-5434->5432-5434/tcp\n"
        resultado = vd.exposiciones_docker(salida)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].puerto_anfitrion, 5432)
        self.assertIn("5432-5434", resultado[0].publicacion)


class TestEscuchasExpuestas(unittest.TestCase):
    def test_tkt070_tc_u4_marca_escuchas_fuera_de_bucle(self) -> None:
        puertos = {5435}
        expuestas = vd.escuchas_expuestas(SALIDA_SS, puertos)
        self.assertIn("0.0.0.0:5435", expuestas)
        self.assertIn("*:5435", expuestas)
        self.assertIn("[::]:5435", expuestas)
        self.assertNotIn("127.0.0.1:5433", expuestas)
        self.assertNotIn("0.0.0.0:22", expuestas)


class TestEvaluarRedireccion(unittest.TestCase):
    def test_tkt070_tc_u5_redireccion_valida(self) -> None:
        self.assertEqual(
            vd.evaluar_redireccion("ejemplo.test", 308, "https://ejemplo.test/", b""),
            [],
        )

    def test_tkt070_tc_u5b_redireccion_puerto_publicado(self) -> None:
        self.assertEqual(
            vd.evaluar_redireccion(
                "apbuildings.duckdns.org",
                308,
                "https://apbuildings.duckdns.org:10005/",
                b"",
                puerto_https=10005,
            ),
            [],
        )

    def test_tkt070_tc_u6_rechaza_contenido_en_cuerpo(self) -> None:
        fallos = vd.evaluar_redireccion(
            "apbuildings.duckdns.org",
            200,
            None,
            b"CIMENTA entorno prod",
        )
        self.assertTrue(any("200" in f for f in fallos))
        self.assertTrue(any("contenido" in f for f in fallos))

    def test_tkt070_tc_u7_rechaza_estado_y_location_incorrectos(self) -> None:
        fallos_estado = vd.evaluar_redireccion("n.test", 302, "https://n.test/", b"")
        self.assertEqual(len(fallos_estado), 1)
        self.assertIn("302", fallos_estado[0])
        fallos_http = vd.evaluar_redireccion("n.test", 308, "http://n.test/", b"")
        self.assertTrue(any("http://n.test/" in f for f in fallos_http))
        fallos_host = vd.evaluar_redireccion("n.test", 308, "https://otro.test/", b"")
        self.assertTrue(any("otro.test" in f for f in fallos_host))


class TestEvaluarSondeo(unittest.TestCase):
    def test_tkt070_tc_u8_sondeo_conectado_o_no(self) -> None:
        self.assertIsNone(vd.evaluar_sondeo("192.0.2.1", 5433, False))
        texto = vd.evaluar_sondeo("192.0.2.1", 5433, True)
        self.assertIsNotNone(texto)
        assert texto is not None
        self.assertIn("192.0.2.1:5433", texto)


class TestEvaluarCertificado(unittest.TestCase):
    def test_tkt070_tc_u9_emisor_y_vigencia(self) -> None:
        ahora = 1_700_000_000.0
        vigente = {
            "issuer": (("organizationName", "Let's Encrypt"),),
            "notAfter": "Jan  1 12:00:00 2030 GMT",
        }
        self.assertEqual(vd.evaluar_certificado("n.test", vigente, ahora), [])
        vigente_anidado = {
            "issuer": (
                (("countryName", "US"),),
                (("organizationName", "Let's Encrypt"),),
                (("commonName", "YE2"),),
            ),
            "notAfter": "Jan  1 12:00:00 2030 GMT",
        }
        self.assertEqual(vd.evaluar_certificado("n.test", vigente_anidado, ahora), [])
        staging = {
            "issuer": (("organizationName", "(STAGING) Let's Encrypt"),),
            "notAfter": "Jan  1 12:00:00 2030 GMT",
        }
        self.assertTrue(vd.evaluar_certificado("n.test", staging, ahora))
        caducado = {
            "issuer": (("organizationName", "Let's Encrypt"),),
            "notAfter": "Jan  1 12:00:00 2020 GMT",
        }
        self.assertTrue(vd.evaluar_certificado("n.test", caducado, ahora))

    def test_tkt070_tc_u9c_rechaza_not_after_ausente(self) -> None:
        certificado = {
            "issuer": (("organizationName", "Let's Encrypt"),),
        }
        fallos = vd.evaluar_certificado("n.test", certificado, 1_700_000_000.0)
        self.assertEqual(len(fallos), 1)
        self.assertIn("no trae notAfter", fallos[0])

    def test_tkt070_tc_u9b_rechaza_not_after_ilegible(self) -> None:
        certificado = {
            "issuer": (("organizationName", "Let's Encrypt"),),
            "notAfter": "no-es-fecha",
        }
        fallos = vd.evaluar_certificado("n.test", certificado, 1_700_000_000.0)
        self.assertEqual(len(fallos), 1)
        self.assertIn("notAfter ilegible", fallos[0])


class TestPuertosDbPublicados(unittest.TestCase):
    def test_tkt070_tc_u3c_puertos_db_publicados_desde_ps(self) -> None:
        self.assertEqual(vd.puertos_db_publicados(SALIDA_PS_LOCAL), {55433, 55435})


class TestMain(unittest.TestCase):
    def test_tkt070_tc_u10_anfitrion_con_exposicion_sale_uno(self) -> None:
        def ejecutar(comando: list[str]) -> str:
            if comando[0] == "docker":
                return SALIDA_PS_LOCAL
            return SALIDA_SS

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = vd.main(["anfitrion"], ejecutar=ejecutar)
        self.assertEqual(codigo, 1)
        salida = buffer.getvalue()
        self.assertIn("FALLA", salida)
        self.assertIn("55435", salida)
        self.assertIn("cimenta-sonda-expuesta", salida)

    def test_tkt070_tc_u10_anfitrion_limpio_sale_cero(self) -> None:
        def ejecutar(comando: list[str]) -> str:
            if comando[0] == "docker":
                return "cimenta-prod-db-1\t127.0.0.1:5433->5432/tcp\n"
            return "State\nLISTEN 0 4096 127.0.0.1:5433 0.0.0.0:*\n"

        self.assertEqual(vd.main(["anfitrion"], ejecutar=ejecutar), 0)

    def test_tkt070_tc_u11_remoto_sondeo_falla(self) -> None:
        def sondear(ip: str, puerto: int, espera: float) -> bool:
            return puerto == 5433

        def pedir_http(
            nombre: str, puerto_http: int, espera: float
        ) -> tuple[int, str | None, bytes]:
            return 308, f"https://{nombre}/", b""

        def obtener_certificado(nombre: str, puerto_https: int, espera: float) -> dict[str, Any]:
            return {
                "issuer": (("organizationName", "Let's Encrypt"),),
                "notAfter": "Jan  1 12:00:00 2030 GMT",
            }

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = vd.main(
                ["remoto", "--ip", "192.0.2.1", "--puertos", "5433"],
                sondear=sondear,
                pedir_http=pedir_http,
                obtener_certificado=obtener_certificado,
                ahora=lambda: 1_700_000_000.0,
            )
        self.assertEqual(codigo, 1)
        salida = buffer.getvalue()
        self.assertIn("FALLA", salida)
        self.assertIn("192.0.2.1:5433", salida)

    def test_tkt070_tc_u11_remoto_en_verde(self) -> None:
        def sondear(ip: str, puerto: int, espera: float) -> bool:
            return False

        def pedir_http(
            nombre: str, puerto_http: int, espera: float
        ) -> tuple[int, str | None, bytes]:
            return 308, f"https://{nombre}/", b""

        def obtener_certificado(nombre: str, puerto_https: int, espera: float) -> dict[str, Any]:
            return {
                "issuer": (("organizationName", "Let's Encrypt"),),
                "notAfter": "Jan  1 12:00:00 2030 GMT",
            }

        with redirect_stdout(io.StringIO()):
            codigo = vd.main(
                ["remoto", "--ip", "192.0.2.1"],
                sondear=sondear,
                pedir_http=pedir_http,
                obtener_certificado=obtener_certificado,
                ahora=lambda: 1_700_000_000.0,
            )
        self.assertEqual(codigo, 0)

    def test_tkt070_tc_u12_anfitrion_sin_ss_sale_dos(self) -> None:
        def ejecutar(comando: list[str]) -> str:
            raise FileNotFoundError(comando[0])

        buffer_err = io.StringIO()
        with redirect_stderr(buffer_err):
            codigo = vd.main(["anfitrion"], ejecutar=ejecutar)
        self.assertEqual(codigo, 2)
        self.assertIn("ERROR", buffer_err.getvalue())

    def test_tkt070_tc_u12_anfitrion_docker_falla_sale_dos(self) -> None:
        def ejecutar(comando: list[str]) -> str:
            if comando[0] == "docker":
                raise subprocess.CalledProcessError(1, comando, stderr="docker ps fallo")
            return SALIDA_SS

        buffer_err = io.StringIO()
        with redirect_stderr(buffer_err):
            codigo = vd.main(["anfitrion"], ejecutar=ejecutar)
        self.assertEqual(codigo, 2)
        self.assertIn("docker ps fallo", buffer_err.getvalue())

    def test_tkt070_tc_u11_remoto_http_oserror(self) -> None:
        def pedir_http(
            nombre: str, puerto_http: int, espera: float
        ) -> tuple[int, str | None, bytes]:
            raise OSError("conexion rechazada")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = vd.main(
                ["remoto", "--ip", "192.0.2.1", "--puertos", "9999"],
                sondear=lambda *_a, **_k: False,
                pedir_http=pedir_http,
                obtener_certificado=lambda *_a, **_k: {
                    "issuer": (("organizationName", "Let's Encrypt"),),
                    "notAfter": "Jan  1 12:00:00 2030 GMT",
                },
                ahora=lambda: 1_700_000_000.0,
            )
        self.assertEqual(codigo, 1)
        self.assertIn("FALLA", buffer.getvalue())
        self.assertIn("HTTP de", buffer.getvalue())

    def test_tkt070_tc_u11_remoto_http_bad_status(self) -> None:
        def pedir_http(
            nombre: str, puerto_http: int, espera: float
        ) -> tuple[int, str | None, bytes]:
            raise http.client.BadStatusLine("no es HTTP")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = vd.main(
                ["remoto", "--ip", "192.0.2.1", "--puertos", "9999"],
                sondear=lambda *_a, **_k: False,
                pedir_http=pedir_http,
                obtener_certificado=lambda *_a, **_k: {
                    "issuer": (("organizationName", "Let's Encrypt"),),
                    "notAfter": "Jan  1 12:00:00 2030 GMT",
                },
                ahora=lambda: 1_700_000_000.0,
            )
        self.assertEqual(codigo, 1)
        self.assertIn("FALLA", buffer.getvalue())
        self.assertIn("no es HTTP", buffer.getvalue())

    def test_tkt070_tc_u11_remoto_certificado_oserror(self) -> None:
        def obtener_certificado(nombre: str, puerto_https: int, espera: float) -> dict[str, Any]:
            raise OSError("handshake fallo")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = vd.main(
                ["remoto", "--ip", "192.0.2.1", "--puertos", "9999"],
                sondear=lambda *_a, **_k: False,
                pedir_http=lambda *_a, **_k: (308, "https://x/", b""),
                obtener_certificado=obtener_certificado,
                ahora=lambda: 1_700_000_000.0,
            )
        self.assertEqual(codigo, 1)
        self.assertIn("FALLA", buffer.getvalue())
        self.assertIn("handshake fallo", buffer.getvalue())

    def test_tkt070_tc_u12_suborden_desconocida(self) -> None:
        with mock.patch(
            "verificar_despliegue.argparse.ArgumentParser.parse_args",
            return_value=mock.Mock(comando="otro"),
        ):
            self.assertEqual(vd.main([]), 2)

    def test_tkt070_tc_u12_remoto_dns_falla_sale_dos(self) -> None:
        with mock.patch(
            "verificar_despliegue.socket.gethostbyname",
            side_effect=OSError("name resolution failed"),
        ):
            with redirect_stderr(io.StringIO()):
                codigo = vd.main(
                    ["remoto"],
                    sondear=lambda *_a, **_k: False,
                    pedir_http=lambda *_a, **_k: (308, "https://x/", b""),
                    obtener_certificado=lambda *_a, **_k: {
                        "issuer": (("organizationName", "Let's Encrypt"),),
                        "notAfter": "Jan  1 12:00:00 2030 GMT",
                    },
                )
            self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
