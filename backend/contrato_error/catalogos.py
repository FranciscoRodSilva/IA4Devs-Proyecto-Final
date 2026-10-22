"""Catálogos cerrados del contrato de error (TKT-005, M4, CA-4, CA-7, CA-8).

Cada clase repite, con el mismo nombre y valor literal, un enumerado del borrador
`docs/api/openapi.yaml`. Como son `StrEnum`, un miembro se compara con la cadena que viaja
en la sesión o en el JSON, y construir uno con un valor ajeno lanza `ValueError` citando el valor
recibido. Una prueba compara cada catálogo con su `enum` del borrador en cada ejecución.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Rol(StrEnum):
    """Los seis roles del PRD §4 (esquema `Rol` del borrador). Un usuario puede acumular varios."""

    DIRECCION_GENERAL = "DIRECCION_GENERAL"
    DIRECTOR_PROYECTOS = "DIRECTOR_PROYECTOS"
    RESIDENTE = "RESIDENTE"
    COMPRAS = "COMPRAS"
    ALMACEN = "ALMACEN"
    ADMINISTRACION = "ADMINISTRACION"


class Metodo(StrEnum):
    """Métodos HTTP de una acción (propiedad `metodo` del esquema `Accion`)."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class CodigoConflicto(StrEnum):
    """Catálogo cerrado de un `409` `CONFLICTO` que no viola ninguna `RN-xx` (CA-4).

    Ampliarlo exige cambiar el borrador en el mismo cambio que añade el caso que lo produce.
    """

    CODIGO_OBRA_DUPLICADO = "CODIGO_OBRA_DUPLICADO"
    RFC_DUPLICADO = "RFC_DUPLICADO"
    FOLIO_REMISION_DUPLICADO = "FOLIO_REMISION_DUPLICADO"
    OBRA_CON_HISTORIAL = "OBRA_CON_HISTORIAL"
    ESTADO_NO_PERMITE_OPERACION = "ESTADO_NO_PERMITE_OPERACION"
    IMPORTACION_EN_CURSO = "IMPORTACION_EN_CURSO"
    IMPORTACION_CON_ERRORES = "IMPORTACION_CON_ERRORES"
    REEMPLAZO_NO_CONFIRMADO = "REEMPLAZO_NO_CONFIRMADO"
    SIN_LINEA_BASE_CONGELADA = "SIN_LINEA_BASE_CONGELADA"
    SIN_PRESUPUESTO_CONTROL = "SIN_PRESUPUESTO_CONTROL"
    TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR = "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR"
    YA_RESUELTA = "YA_RESUELTA"
    SOLICITUD_SIN_EFECTO = "SOLICITUD_SIN_EFECTO"
    SOLICITUD_NO_APLICABLE = "SOLICITUD_NO_APLICABLE"
    ORDEN_YA_EMITIDA = "ORDEN_YA_EMITIDA"
    ORDEN_YA_CERRADA = "ORDEN_YA_CERRADA"
    ORDEN_NO_ADMITE_ENTRADAS = "ORDEN_NO_ADMITE_ENTRADAS"
    SIN_SALDO_PENDIENTE = "SIN_SALDO_PENDIENTE"
    PROVEEDOR_INACTIVO = "PROVEEDOR_INACTIVO"
    PROVEEDOR_CON_ORDENES_ABIERTAS = "PROVEEDOR_CON_ORDENES_ABIERTAS"
    ARCHIVO_NO_SUBIDO = "ARCHIVO_NO_SUBIDO"
    ARCHIVO_NO_DISPONIBLE = "ARCHIVO_NO_DISPONIBLE"
    ARCHIVO_TAMANO_DISTINTO = "ARCHIVO_TAMANO_DISTINTO"
    ARCHIVO_HASH_DISTINTO = "ARCHIVO_HASH_DISTINTO"
    ARCHIVO_TIPO_NO_PERMITIDO = "ARCHIVO_TIPO_NO_PERMITIDO"
    ARCHIVO_CADUCADO = "ARCHIVO_CADUCADO"


class CodigoConcurrencia(StrEnum):
    """Código de un `409` `CONCURRENCIA` (esquema `ErrorConcurrencia`, RNF-16)."""

    BLOQUEO_VENCIDO = "BLOQUEO_VENCIDO"
    TIEMPO_EJECUCION_VENCIDO = "TIEMPO_EJECUCION_VENCIDO"


class CodigoValidacion(StrEnum):
    """Código de un error de campo de un `422` `VALIDACION` (esquema `ErrorValidacion`)."""

    OBLIGATORIO = "OBLIGATORIO"
    FORMATO = "FORMATO"
    NO_POSITIVO = "NO_POSITIVO"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"
    FECHA_ANTERIOR_A_VIGENTE = "FECHA_ANTERIOR_A_VIGENTE"
    VALOR_NO_PERMITIDO = "VALOR_NO_PERMITIDO"
    DEMASIADO_LARGO = "DEMASIADO_LARGO"


class MotivoPermiso(StrEnum):
    """Motivo de un `403` `PERMISO` (esquema `ErrorPermiso`)."""

    ROL_INSUFICIENTE = "ROL_INSUFICIENTE"
    AUTO_RESOLUCION = "AUTO_RESOLUCION"
    NO_ES_SOLICITANTE = "NO_ES_SOLICITANTE"
    ORIGEN_NO_VERIFICADO = "ORIGEN_NO_VERIFICADO"


class MotivoSesion(StrEnum):
    """Motivo de un `401` `SESION` (esquema `ErrorSesion`)."""

    SIN_SESION = "SIN_SESION"
    SESION_CADUCADA = "SESION_CADUCADA"
    SESION_REVOCADA = "SESION_REVOCADA"
    CREDENCIALES_INVALIDAS = "CREDENCIALES_INVALIDAS"


TODOS_LOS_ROLES: Final[frozenset[Rol]] = frozenset(Rol)
"""«Todos los roles» de CA-9, sin un valor centinela: una acción que cualquier rol puede ejecutar."""
