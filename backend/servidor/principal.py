"""Punto de entrada de `fastapi dev` y de `uvicorn` (TKT-005, fila 7, CA-12).

Este módulo es el único que crea la aplicación a nivel de módulo. Las pruebas y cualquier otro
importador usan `servidor.fabrica.crear_aplicacion` directamente: importar la fábrica no configura
el registro global, y importar este módulo sí.
"""

from servidor.fabrica import crear_aplicacion

app = crear_aplicacion()
