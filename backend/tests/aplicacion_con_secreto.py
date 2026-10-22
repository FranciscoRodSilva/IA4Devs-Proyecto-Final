"""Aplicación auxiliar de la suite para la prueba con uvicorn real (TKT-005, ciclo de corrección 1).

No es una prueba: `test_servidor_arranque.py` la lanza en un subproceso con
`python -m uvicorn --app-dir tests aplicacion_con_secreto:app`. Es la aplicación de la fábrica más
una ruta `def` que lanza una excepción con un valor sensible en su mensaje. El valor llega por la
variable de entorno `SECRETO_DE_PRUEBA`, de modo que ninguna línea de código fuente de un marco de
la traza lo contiene. Vive en `tests/` porque solo la suite la usa; el producto no la conoce.
"""

import os

from fastapi import APIRouter

from servidor.fabrica import crear_aplicacion

SECRETO = os.environ["SECRETO_DE_PRUEBA"]


def ruta_que_falla() -> None:
    raise ValueError(f"contrasena={SECRETO}")


app = crear_aplicacion()
_router = APIRouter()
_router.add_api_route("/prueba/falla", ruta_que_falla, methods=["POST"])
app.include_router(_router)
