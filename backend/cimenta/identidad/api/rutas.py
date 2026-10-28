"""Las cuatro rutas de sesión del borrador OpenAPI (TKT-006, entrega A). Todas `def`, nunca `async def`.

Solo `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion` se atienden sin sesión (lista cerrada de CA-14).
El token CSRF solo se emite aquí; verificarlo es de TKT-057.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from cimenta.identidad.api.dependencias import (
    COOKIE_CSRF,
    COOKIE_SESION,
    contexto_de,
    sesion_vigente,
)
from cimenta.identidad.api.esquemas import CredencialesInicio, TokenCsrf, UsuarioActual
from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado
from cimenta.identidad.aplicacion.sesiones import abrir_sesion, cerrar_sesion_vigente

enrutador = APIRouter(prefix="/api/v1/sesion", tags=["identidad"])


@enrutador.get("/csrf", operation_id="obtener_token_csrf")
def obtener_token_csrf(response: Response) -> TokenCsrf:
    """M1: emite un token nuevo en cada petición, en cookie legible por JavaScript y en el cuerpo."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE_CSRF, token, path="/", secure=True, httponly=False, samesite="lax")
    return TokenCsrf(token=token)


@enrutador.post("", operation_id="iniciar_sesion")
def iniciar_sesion(
    credenciales: CredencialesInicio, request: Request, response: Response
) -> UsuarioActual:
    """M2 · RNF-03: abre una sesión y fija la cookie opaca. Sin `max_age`: la caducidad la decide el servidor."""
    usuario = abrir_sesion(
        contexto_de(request),
        correo_escrito=credenciales.email,
        contrasena=credenciales.contrasena,
        origen_ip=request.client.host if request.client else None,
        agente_usuario=request.headers.get("user-agent"),
    )
    response.set_cookie(
        COOKIE_SESION, str(usuario.sesion_id), path="/", secure=True, httponly=True, samesite="lax"
    )
    return UsuarioActual.desde(usuario)


@enrutador.get("", operation_id="obtener_sesion_actual", summary="ENSAYO summary desactualizado")
def obtener_sesion_actual(
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
) -> UsuarioActual:
    """M5: la sesión de quien llama, ya validada contra la tabla."""
    return UsuarioActual.desde(usuario)


@enrutador.post("/cierre", operation_id="cerrar_sesion", status_code=204, response_class=Response)
def cerrar_sesion(
    request: Request, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)]
) -> Response:
    """M4: revoca la sesión (nunca la borra) y expira la cookie."""
    cerrar_sesion_vigente(contexto_de(request), usuario.sesion_id)
    respuesta = Response(status_code=204)
    respuesta.delete_cookie(COOKIE_SESION, path="/", secure=True, httponly=True, samesite="lax")
    return respuesta
