"""Dependencias de las rutas de archivos (TKT-059, fila 9).

`contexto_de_archivos` entrega a una ruta `def` el `ContextoArchivos` que la fábrica dejó en
`aplicacion.state.archivos`. La ruta de TKT-018 lo inyecta con `Depends` para llamar a
`registrar_archivo` sin importar nada de la composición.
"""

from __future__ import annotations

from fastapi import Request

from cimenta.archivos.aplicacion.contexto import ContextoArchivos


def contexto_de_archivos(request: Request) -> ContextoArchivos:
    contexto: ContextoArchivos = request.app.state.archivos
    return contexto
