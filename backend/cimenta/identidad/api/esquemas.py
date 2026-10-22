"""DTO de la API de identidad (TKT-006): entrada y salida de las cuatro rutas de sesión.

Los esquemas salen de `components.schemas` del borrador OpenAPI: `TokenCsrf`, `CredencialesInicio`
y `UsuarioActual`. Un `ValueError` de un validador llega al manejador de TKT-005 y sale como
`422 VALIDACION` con código `FORMATO`; la contraseña vacía sale `OBLIGATORIO`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, Field, WithJsonSchema

from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado
from contrato_error import Rol


def forma_de_correo(valor: str) -> str:
    """CA-5: valida la forma y devuelve el valor tal como se escribió (CA-2: `intento_acceso` lo guarda así).

    Decisión del usuario: se valida con `email_validator` sin comprobar la entrega y en modo de
    entorno de pruebas, porque `pydantic.networks.validate_email` rechaza dominios reservados como
    `cimenta.test`. Se devuelve el valor original, no el normalizado.
    """
    if valor != valor.strip() or "<" in valor or ">" in valor:
        raise ValueError("no es una dirección de correo")
    try:
        validate_email(valor, check_deliverability=False, test_environment=True)
    except EmailNotValidError as error:
        raise ValueError("no es una dirección de correo") from error
    return valor


class TokenCsrf(BaseModel):
    token: str = Field(min_length=32)


class CredencialesInicio(BaseModel):
    email: Annotated[
        str,
        AfterValidator(forma_de_correo),
        WithJsonSchema({"type": "string", "format": "email"}),
    ]
    contrasena: Annotated[str, Field(min_length=1)]


class VigenciaSesion(BaseModel):
    expira_en: datetime
    expira_por_inactividad_en: datetime


class UsuarioActual(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str
    roles: list[Rol]
    sesion: VigenciaSesion

    @classmethod
    def desde(cls, usuario: UsuarioAutenticado) -> UsuarioActual:
        """Los roles salen ordenados por valor, para que la respuesta no dependa del orden del conjunto."""
        return cls(
            id=usuario.usuario_id,
            nombre=usuario.nombre,
            email=usuario.email,
            roles=[Rol(r) for r in sorted(usuario.roles)],
            sesion=VigenciaSesion(
                expira_en=usuario.expira_en,
                expira_por_inactividad_en=usuario.expira_por_inactividad_en,
            ),
        )
