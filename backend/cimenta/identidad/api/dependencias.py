"""Dependencias de la API de identidad (TKT-006): la sesión vigente y el rol de quien llama.

`sesion_vigente` reconoce la cookie contra la tabla `sesion` en cada petición (ADR-014);
`exigir_rol` se apoya en ella —el 401 va antes que el 403— y asienta cada denegación (M9).
"""

from __future__ import annotations

import ipaddress
import secrets
import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie, APIKeyHeader

from cimenta.identidad.api.esquemas import CredencialesInicio
from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado
from cimenta.identidad.aplicacion.denegacion import registrar_denegacion
from cimenta.identidad.aplicacion.sesiones import (
    MENSAJE_SIN_SESION,
    registrar_rechazo_de_origen,
    validar_sesion,
)
from cimenta.identidad.dominio.autorizacion import rol_suficiente
from contrato_error import PermisoDenegado, Rol, SesionInvalida

COOKIE_SESION = "cimenta_sesion"
COOKIE_CSRF = "cimenta_csrf"
CABECERA_CSRF = "X-CSRF-Token"
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)

_esquema_sesion = APIKeyCookie(name=COOKIE_SESION, scheme_name="sesion", auto_error=False)
_esquema_csrf = APIKeyHeader(name=CABECERA_CSRF, scheme_name="csrf", auto_error=False)


def contexto_de(request: Request) -> ContextoIdentidad:
    contexto: ContextoIdentidad = request.app.state.identidad
    return contexto


def origen_de(request: Request) -> str:
    """RNF-04: el origen contra el que se cuenta el límite de intentos; devuelve siempre una cadena.

    Una IPv6 se agrupa por su prefijo /64, porque quien tiene un /64 entero controla 2^64 direcciones
    y, contando la dirección completa, evadiría el límite por origen rotando de dirección. Una
    `::ffff:a.b.c.d` se desenvuelve a su IPv4. Una IPv4 se devuelve tal cual. Sin cliente
    (`request.client is None`) cae en la cubeta fija `desconocido`, que también se bloquea: devolver
    `None` dejaría esa petición sin límite. Un host que no es una dirección (el `testclient` de las
    pruebas) se devuelve sin tocar. Detrás de un proxy todos los clientes comparten origen: su
    tratamiento es PA-T5, de TKT-058.
    """
    if request.client is None:
        return "desconocido"
    host = request.client.host
    try:
        direccion = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(direccion, ipaddress.IPv6Address):
        if direccion.ipv4_mapped is not None:
            return str(direccion.ipv4_mapped)
        return str(ipaddress.ip_network(f"{host}/64", strict=False))
    return host


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


def par_csrf_valido(cookie: str | None, cabecera: str | None) -> bool:
    """M4 · CA-9 y CA-10: el token de la cookie y el de la cabecera deben ser el mismo valor.

    Se compara en bytes UTF-8: `compare_digest` con `str` no ASCII lanza `TypeError`, que sería un 500."""
    if not cookie or not cabecera:
        return False
    return secrets.compare_digest(cookie.encode("utf-8"), cabecera.encode("utf-8"))


def verificar_origen(
    request: Request,
    usuario: Annotated[UsuarioAutenticado, Depends(sesion_vigente)],
    cabecera: Annotated[str | None, Depends(_esquema_csrf)],
) -> UsuarioAutenticado:
    """M4 · CA-9 · CA-11: doble envío CSRF. `usuario` va antes que `cabecera`: sin sesión responde 401
    antes de mirar el token. Un par ausente o distinto es 403 ORIGEN_NO_VERIFICADO, asentado como DENEGAR."""
    if par_csrf_valido(request.cookies.get(COOKIE_CSRF), cabecera):
        return usuario
    registrar_denegacion(
        contexto_de(request),
        usuario=usuario,
        motivo="ORIGEN_NO_VERIFICADO",
        metodo=request.method,
        ruta=request.url.path,
        roles_requeridos=(),
        correlacion_id=str(getattr(request.state, "correlacion_id", "")),
    )
    raise PermisoDenegado(
        motivo="ORIGEN_NO_VERIFICADO",
        mensaje=MENSAJE_ORIGEN_NO_VERIFICADO,
        roles_requeridos=(),
    )


def credenciales_con_origen_verificado(
    request: Request,
    credenciales: CredencialesInicio,
    cabecera: Annotated[str | None, Depends(_esquema_csrf)],
) -> CredencialesInicio:
    """M4 · CA-9 · CA-11 esc. 3 · D-5. Verifica el par CSRF de `POST /sesion`, que no tiene sesión.

    FastAPI valida el cuerpo antes de llamar a esta dependencia: un cuerpo inválido responde `422`
    sin fila de intento ni rechazo de origen. Con el cuerpo válido y un par inválido, asienta el
    rechazo anónimo y lanza `403 ORIGEN_NO_VERIFICADO`, sin verificar ninguna contraseña."""
    if par_csrf_valido(request.cookies.get(COOKIE_CSRF), cabecera):
        return credenciales
    registrar_rechazo_de_origen(
        contexto_de(request),
        correo_escrito=credenciales.email,
        origen_ip=origen_de(request),
        metodo=request.method,
        ruta=request.url.path,
    )
    raise PermisoDenegado(
        motivo="ORIGEN_NO_VERIFICADO",
        mensaje=MENSAJE_ORIGEN_NO_VERIFICADO,
        roles_requeridos=(),
    )


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
