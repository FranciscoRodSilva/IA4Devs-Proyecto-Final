"""Las cuatro rutas de sesión del borrador OpenAPI (TKT-006, entrega A). Todas `def`, nunca `async def`.

Solo `GET /api/v1/sesion/csrf` y `POST /api/v1/sesion` se atienden sin sesión (lista cerrada de CA-14).
El token CSRF solo se emite aquí. Se emite de nuevo, con uno distinto, al iniciar sesión y al cerrarla
(rotación de CA-12): el servidor no guarda el token, así que el anterior deja de valer porque la cookie
vigente ya no coincide con él (PA-T7).
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from cimenta.identidad.api.dependencias import (
    COOKIE_CSRF,
    COOKIE_SESION,
    contexto_de,
    credenciales_con_origen_verificado,
    origen_de,
    sesion_vigente,
    verificar_origen,
)
from cimenta.identidad.api.esquemas import CredencialesInicio, TokenCsrf, UsuarioActual
from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado
from cimenta.identidad.aplicacion.sesiones import abrir_sesion, cerrar_sesion_vigente

enrutador = APIRouter(prefix="/api/v1/sesion", tags=["identidad"])


def _fijar_cookie_csrf(response: Response) -> str:
    """M1 · CA-12: fija un token CSRF nuevo en `cimenta_csrf` y devuelve su valor. Sin estado en el servidor."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE_CSRF, token, path="/", secure=True, httponly=False, samesite="lax")
    return token


@enrutador.get("/csrf", operation_id="obtener_token_csrf")
def obtener_token_csrf(response: Response) -> TokenCsrf:
    """M1: emite un token nuevo en cada petición, en cookie legible por JavaScript y en el cuerpo."""
    return TokenCsrf(token=_fijar_cookie_csrf(response))


@enrutador.post("", operation_id="iniciar_sesion")
def iniciar_sesion(
    request: Request,
    response: Response,
    credenciales: Annotated[CredencialesInicio, Depends(credenciales_con_origen_verificado)],
) -> UsuarioActual:
    """M2 · RNF-03 · CA-12: abre una sesión, fija la cookie opaca y rota el token CSRF. Sin `max_age`: la caducidad la decide el servidor."""
    usuario = abrir_sesion(
        contexto_de(request),
        correo_escrito=credenciales.email,
        contrasena=credenciales.contrasena,
        origen_ip=origen_de(request),
        agente_usuario=request.headers.get("user-agent"),
    )
    response.set_cookie(
        COOKIE_SESION, str(usuario.sesion_id), path="/", secure=True, httponly=True, samesite="lax"
    )
    _fijar_cookie_csrf(response)
    return UsuarioActual.desde(usuario)


@enrutador.get("", operation_id="obtener_sesion_actual")
def obtener_sesion_actual(
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
) -> UsuarioActual:
    """M5: la sesión de quien llama, ya validada contra la tabla."""
    return UsuarioActual.desde(usuario)


@enrutador.post("/cierre", operation_id="cerrar_sesion", status_code=204, response_class=Response)
def cerrar_sesion(
    request: Request, usuario: Annotated[UsuarioAutenticado, Depends(verificar_origen)]
) -> Response:
    """M4 · CA-12: revoca la sesión (nunca la borra), expira la cookie y rota el token CSRF. Exige el par CSRF (CA-9)."""
    cerrar_sesion_vigente(contexto_de(request), usuario.sesion_id)
    respuesta = Response(status_code=204)
    respuesta.delete_cookie(COOKIE_SESION, path="/", secure=True, httponly=True, samesite="lax")
    _fijar_cookie_csrf(respuesta)
    return respuesta
