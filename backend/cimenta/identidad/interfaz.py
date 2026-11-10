"""Interfaz publicada del módulo `identidad`: lo único que otro módulo importa de él.

Un módulo protege sus rutas con `exigir_rol` y los roles de `x-roles`; el caso de uso que resuelve
una solicitud llama a `evaluar_resolucion` y convierte `AUTO_RESOLUCION` en `PermisoDenegado`
(TKT-026). `sesion_vigente` reconoce la sesión de quien llama y `UsuarioAutenticado` es lo que
entrega.

Convención para las rutas que cambian estado (TKT-057, CA-9): toda ruta `POST`, `PUT`, `PATCH`
o `DELETE` declara `dependencies=[Depends(verificar_origen), Depends(exigir_rol(...))]`, con
`verificar_origen` primero. `verificar_origen` ya incluye la sesión vigente (401 antes que el token).

`nombres_de_usuarios` resuelve los nombres visibles de un conjunto de ids y `UsuarioResumen` es el
DTO que los lleva (TKT-017b1, P-8): así `presupuesto` muestra quién congeló o capturó sin importar las
tablas de `identidad`. Los ids ajenos se ignoran, y la función no abre transacción.
"""

from __future__ import annotations

from cimenta.identidad.api.dependencias import exigir_rol, sesion_vigente, verificar_origen
from cimenta.identidad.api.esquemas import UsuarioResumen
from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado
from cimenta.identidad.aplicacion.usuarios import nombres_de_usuarios
from cimenta.identidad.dominio.autorizacion import (
    MotivoNegacion,
    ResultadoResolucion,
    evaluar_resolucion,
)

__all__ = [
    "MotivoNegacion",
    "ResultadoResolucion",
    "UsuarioAutenticado",
    "evaluar_resolucion",
    "exigir_rol",
    "sesion_vigente",
    "verificar_origen",
    "nombres_de_usuarios",
    "UsuarioResumen",
]
