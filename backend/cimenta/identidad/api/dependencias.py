"""Dependencias de la API de identidad (TKT-006): la sesión vigente y el rol de quien llama.

`sesion_vigente` reconoce la cookie contra la tabla `sesion` en cada petición (ADR-014);
`exigir_rol` se apoya en ella —el 401 va antes que el 403— y asienta cada denegación (M9).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado
from cimenta.identidad.aplicacion.denegacion import registrar_denegacion
from cimenta.identidad.aplicacion.sesiones import MENSAJE_SIN_SESION, validar_sesion
from cimenta.identidad.dominio.autorizacion import rol_suficiente
from contrato_error import PermisoDenegado, Rol, SesionInvalida

COOKIE_SESION = "cimenta_sesion"
COOKIE_CSRF = "cimenta_csrf"
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."

_esquema_sesion = APIKeyCookie(name=COOKIE_SESION, scheme_name="sesion", auto_error=False)


def contexto_de(request: Request) -> ContextoIdentidad:
    contexto: ContextoIdentidad = request.app.state.identidad
    return contexto


def _como_uuid(valor: str | None) -> uuid.UUID | None:
    """Un identificador ausente, vacío o mal formado se trata como si no existiera (CA-7 esc. 2)."""
    if not valor:
        return None
    try:
        return uuid.UUID(valor)
    except ValueError:
        return None


def sesion_vigente(
    request: Request, cookie: Annotated[str | None, Depends(_esquema_sesion)]
) -> UsuarioAutenticado:
    """M7 · ADR-014: reconoce la cookie contra la tabla en cada petición y fija los roles de
    quien llama. Nunca lanza HTTPException: lanza SesionInvalida, del contrato de error."""
    request.state.roles_de_quien_llama = frozenset()
    sesion_id = _como_uuid(cookie)
    if sesion_id is None:
        raise SesionInvalida(motivo="SIN_SESION", mensaje=MENSAJE_SIN_SESION)
    usuario = validar_sesion(contexto_de(request), sesion_id)
    request.state.roles_de_quien_llama = usuario.roles
    request.state.usuario_id = usuario.usuario_id
    request.state.sesion_id = usuario.sesion_id
    return usuario


def exigir_rol(*roles: str) -> Callable[..., UsuarioAutenticado]:
    """M7 · M9. Se declara en la ruta con los roles de su x-roles:
    dependencies=[Depends(exigir_rol("COMPRAS", "DIRECCION_GENERAL"))].

    Un rol mal escrito o la ausencia de roles falla al declarar, no en la petición."""
    requeridos = tuple(Rol(r).value for r in roles)  # ValueError si un rol no existe
    if not requeridos:
        raise ValueError("exigir_rol necesita al menos un rol")
    conjunto = frozenset(requeridos)

    def comprobar_rol(
        request: Request, usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)]
    ) -> UsuarioAutenticado:
        if rol_suficiente(usuario.roles, conjunto):
            return usuario
        registrar_denegacion(
            contexto_de(request),
            usuario=usuario,
            motivo="ROL_INSUFICIENTE",
            metodo=request.method,
            ruta=request.url.path,
            roles_requeridos=requeridos,
            correlacion_id=str(getattr(request.state, "correlacion_id", "")),
        )
        raise PermisoDenegado(
            motivo="ROL_INSUFICIENTE",
            mensaje=MENSAJE_ROL_INSUFICIENTE,
            roles_requeridos=requeridos,
        )

    return comprobar_rol
