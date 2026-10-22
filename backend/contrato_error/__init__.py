"""Contrato de error de regla de negocio (TKT-005).

Python puro: solo biblioteca estándar y `tipos_base`. Lo importa la capa `aplicacion/` de
cualquier módulo; `dominio/` no puede importarlo (ADR-021). Reexporta los catálogos cerrados del
borrador OpenAPI, la `Accion` y la familia de excepciones, una por `tipo` y una sola para
todas las reglas de negocio (`RechazoRegla`).
"""

from __future__ import annotations

from contrato_error.acciones import Accion
from contrato_error.catalogos import (
    TODOS_LOS_ROLES,
    CodigoConcurrencia,
    CodigoConflicto,
    CodigoValidacion,
    Metodo,
    MotivoPermiso,
    MotivoSesion,
    Rol,
)
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    ErrorDeCampo,
    LimiteIntentosExcedido,
    NoEncontrado,
    PermisoDenegado,
    RechazoRegla,
    SesionInvalida,
    ValidacionRechazada,
    mensaje_de_validacion,
    normalizar_detalle,
    validar_regla,
)

__all__ = [
    "TODOS_LOS_ROLES",
    "Accion",
    "CodigoConcurrencia",
    "CodigoConflicto",
    "CodigoValidacion",
    "ConcurrenciaVencida",
    "ConflictoEstado",
    "ErrorContrato",
    "ErrorDeCampo",
    "LimiteIntentosExcedido",
    "Metodo",
    "MotivoPermiso",
    "MotivoSesion",
    "NoEncontrado",
    "PermisoDenegado",
    "RechazoRegla",
    "Rol",
    "SesionInvalida",
    "ValidacionRechazada",
    "mensaje_de_validacion",
    "normalizar_detalle",
    "validar_regla",
]
