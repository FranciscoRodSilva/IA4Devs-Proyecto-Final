"""Pruebas de la guarda de destino de `frontend/e2e/sembrar_usuario_humo.py`.

TKT-008b · ciclo de corrección 1 · F302 y S103. El script escribe un usuario con contraseña
conocida con el rol de migración. Solo puede hacerlo en la base local, y tiene que negarse
antes de conectar: ni el host remoto ni una dirección que `libpq` tome de `PGHOSTADDR` (que
gana sobre el host del nombre) pueden llevar esa escritura fuera del equipo.

Estas pruebas no usan la base. Lanzan el script como lo hace `frontend/e2e/preparacion-global.ts`
(`uv run` desde `backend/`, con `PYTHONPATH=.`) y con un entorno construido aquí: las variables
`CIMENTA_*` y `PG*` del entorno de quien ejecuta se descartan para que nada real llegue al script.
Las contraseñas son valores de prueba que no corresponden a ningún servidor.

Requieren `uv`, porque el script importa `pwdlib` y `sqlalchemy` del entorno de `backend/`. Sin
`uv` se saltan con ese motivo: un trabajo del pipeline de `tools/` que no instale `uv` no las corre.
TKT-009 decide si ese trabajo lo instala.

Ejecución, desde la raíz del repositorio:

    python -m unittest discover -s tools/tests -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(RAIZ, "backend")
SCRIPT = os.path.join(RAIZ, "frontend", "e2e", "sembrar_usuario_humo.py")
UV = shutil.which("uv")
# Direcciones de documentación (RFC 5737): no enrutan, así que un intento de conexión no llega a ningún servidor real.
DIRECCION_DE_DOCUMENTACION = "203.0.113.10"


def lanzar_siembra(host: str, **extra: str) -> subprocess.CompletedProcess[str]:
    """Ejecuta el script con `host` como `CIMENTA_DB_HOST` y `extra` añadido al entorno. Nunca usa el `.env` real."""
    assert UV is not None
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("CIMENTA_", "PG"))}
    entorno.update(
        {
            "PYTHONPATH": ".",
            "CIMENTA_DB_HOST": host,
            "CIMENTA_DB_PUERTO": "5432",
            "CIMENTA_DB_NOMBRE": "cimenta_prueba",
            "CIMENTA_DB_CONTRASENA_MIGRACION": "valor-de-prueba-sin-servidor",
            "CIMENTA_HUMO_CORREO": "humo.prueba@cimenta.test",
            "CIMENTA_HUMO_CONTRASENA": "valor-de-prueba-sin-servidor",
            # Si una prueba llegara a conectar, que no espere: el intento se corta en dos segundos.
            "PGCONNECT_TIMEOUT": "2",
        }
    )
    entorno.update(extra)
    return subprocess.run(
        [UV, "run", "--locked", "python", SCRIPT],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )


def resumen(resultado: subprocess.CompletedProcess[str]) -> str:
    """Última línea de la salida de error: lo bastante para entender un fallo sin volcar un `Traceback` entero."""
    lineas = resultado.stderr.strip().splitlines()
    return f"código {resultado.returncode}; última línea de stderr: {lineas[-1] if lineas else '(vacía)'}"


@unittest.skipUnless(UV, "requiere `uv` en el PATH: el script usa el entorno de backend/")
class PruebasGuardaDeDestino(unittest.TestCase):
    """La siembra del humo se niega a escribir fuera de la base local."""

    def test_rechaza_un_host_remoto_y_no_se_conecta(self) -> None:
        """TKT-008b TC-R316 · F302, S103 — host remoto: sale con 1, nombra el host y no llega a conectar."""
        resultado = lanzar_siembra("db.ejemplo.com")

        self.assertEqual(resultado.returncode, 1, resumen(resultado))
        self.assertTrue("db.ejemplo.com" in resultado.stderr, f"no nombra el host. {resumen(resultado)}")
        self.assertTrue("no es local" in resultado.stderr, f"no dice que no es local. {resumen(resultado)}")
        # Un intento de conexión fallido dejaría un `Traceback` de psycopg; la negativa es un mensaje, no una excepción.
        self.assertTrue("Traceback" not in resultado.stderr, f"intentó conectar. {resumen(resultado)}")

    def test_rechaza_variables_que_redirigen_aunque_el_host_sea_local(self) -> None:
        """TKT-008b TC-R317 · F302, S103 — con `PGHOSTADDR` o `PGSERVICE` definidos, `libpq` ignora el host: se rechaza antes de conectar."""
        # `PGSERVICE=x` no nombra ningún servidor: si la guarda dejara pasar la variable, el script fallaría al conectar.
        casos = (("PGHOSTADDR", DIRECCION_DE_DOCUMENTACION), ("PGSERVICE", "x"))
        for variable, valor in casos:
            with self.subTest(variable=variable):
                resultado = lanzar_siembra("127.0.0.1", **{variable: valor})

                self.assertEqual(resultado.returncode, 1, resumen(resultado))
                self.assertTrue(variable in resultado.stderr, f"no nombra {variable}. {resumen(resultado)}")
                self.assertTrue("Traceback" not in resultado.stderr, f"intentó conectar. {resumen(resultado)}")


if __name__ == "__main__":
    unittest.main()
