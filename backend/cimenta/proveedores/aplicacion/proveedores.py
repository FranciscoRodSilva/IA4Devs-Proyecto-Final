"""Casos de uso del catálogo de proveedores (TKT-029a, fila A4): alta, consulta, lista, cambio y desactivación.

Orquesta; no decide. La normalización del RFC y la regla de qué estado admite la desactivación viven en
`dominio/proveedor.py`. Cada caso de uso abre una sola transacción y asienta la bitácora en ella. La
unicidad del RFC la arbitra `uq_proveedor_rfc`: su `23505` se traduce aquí a `RFC_DUPLICADO`, sin
comprobación previa, así que cubre también la carrera entre dos altas simultáneas.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from sqlalchemy.exc import DBAPIError

from cimenta.auditoria.interfaz import asentar
from cimenta.proveedores.aplicacion.contexto import ContextoProveedores
from cimenta.proveedores.dominio.proveedor import EstadoProveedor, admite_desactivacion
from cimenta.proveedores.infraestructura import repositorio_proveedor
from cimenta.proveedores.infraestructura.repositorio_proveedor import FilaProveedor
from contrato_error.excepciones import ConflictoEstado, NoEncontrado
from tipos_base import Dinero

ROLES_GESTION = ("COMPRAS",)
ROLES_LECTURA = (
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
)

CAMPOS_CAMBIABLES: Final = frozenset({"nombre", "tope_consignacion", "dia_corte", "dia_pago"})

MENSAJE_PROVEEDOR_NO_EXISTE = "El proveedor no existe."

_RESTRICCION_RFC = "uq_proveedor_rfc"
_SQLSTATE_UNICIDAD = "23505"


@dataclass(frozen=True, slots=True)
class DatosProveedorNuevo:
    nombre: str
    rfc: str
    tope_consignacion: Dinero | None
    dia_corte: int
    dia_pago: int


@dataclass(frozen=True, slots=True)
class CambiosProveedor:
    """Solo los campos de `presentes` se aplican; un tope presente y `None` deja la columna en `NULL`."""

    presentes: frozenset[str]
    nombre: str | None = None
    tope_consignacion: Dinero | None = None
    dia_corte: int | None = None
    dia_pago: int | None = None


@dataclass(frozen=True, slots=True)
class ProveedoresConsultados:
    elementos: tuple[FilaProveedor, ...]
    pagina: int
    tamano_pagina: int
    total: int


def _valor_de_bitacora(valor: object) -> object:
    return valor.cuantizar().serializar() if isinstance(valor, Dinero) else valor


def crear_proveedor(
    contexto: ContextoProveedores, *, datos: DatosProveedorNuevo, usuario_id: uuid.UUID
) -> uuid.UUID:
    """Da de alta un proveedor `ACTIVO` y asienta `CREAR` en la misma transacción."""
    proveedor_id = uuid.uuid4()
    ahora = contexto.reloj()
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            repositorio_proveedor.insertar_proveedor(
                sesion_bd,
                proveedor_id=proveedor_id,
                nombre=datos.nombre,
                rfc=datos.rfc,
                tope_consignacion=datos.tope_consignacion,
                dia_corte=datos.dia_corte,
                dia_pago=datos.dia_pago,
                creado_en=ahora,
                creado_por_id=usuario_id,
            )
            asentar(
                sesion_bd,
                accion="CREAR",
                entidad_tipo="proveedor",
                entidad_id=proveedor_id,
                usuario_id=usuario_id,
                ocurrido_en=ahora,
                datos_despues={
                    "nombre": datos.nombre,
                    "rfc": datos.rfc,
                    "estado": EstadoProveedor.ACTIVO.value,
                    "tope_consignacion": _valor_de_bitacora(datos.tope_consignacion),
                    "dia_corte": datos.dia_corte,
                    "dia_pago": datos.dia_pago,
                },
            )
    except DBAPIError as error:
        if _es_rfc_duplicado(error):
            _conflicto_rfc(contexto, datos.rfc, error)
        raise
    return proveedor_id


def obtener_proveedor(contexto: ContextoProveedores, proveedor_id: uuid.UUID) -> FilaProveedor:
    """El proveedor por id; `NoEncontrado` si no existe."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio_proveedor.leer_proveedor(sesion_bd, proveedor_id)
    if fila is None:
        raise NoEncontrado(recurso="proveedor", mensaje=MENSAJE_PROVEEDOR_NO_EXISTE)
    return fila


def listar_proveedores(
    contexto: ContextoProveedores,
    *,
    estados: frozenset[str],
    q: str | None,
    pagina: int,
    tamano_pagina: int,
) -> ProveedoresConsultados:
    """Una página del catálogo por nombre, con el total que cumple el filtro."""
    busqueda = None if q is None or not q.strip() else q.strip()
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        resultado = repositorio_proveedor.listar_proveedores(
            sesion_bd,
            estados=estados,
            q=busqueda,
            desplazamiento=(pagina - 1) * tamano_pagina,
            limite=tamano_pagina,
        )
    return ProveedoresConsultados(
        elementos=tuple(resultado.filas),
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        total=resultado.total,
    )


def actualizar_proveedor(
    contexto: ContextoProveedores,
    *,
    proveedor_id: uuid.UUID,
    cambios: CambiosProveedor,
    usuario_id: uuid.UUID,
) -> None:
    """Aplica los campos presentes bajo `FOR UPDATE` y asienta `ACTUALIZAR`. No consulta el estado (D-3)."""
    ahora = contexto.reloj()
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio_proveedor.leer_proveedor(sesion_bd, proveedor_id, para_cambio=True)
        if fila is None:
            raise NoEncontrado(recurso="proveedor", mensaje=MENSAJE_PROVEEDOR_NO_EXISTE)
        campos = sorted(cambios.presentes)
        valores: Mapping[str, object] = {campo: getattr(cambios, campo) for campo in campos}
        repositorio_proveedor.actualizar_proveedor(sesion_bd, proveedor_id, valores)
        asentar(
            sesion_bd,
            accion="ACTUALIZAR",
            entidad_tipo="proveedor",
            entidad_id=proveedor_id,
            usuario_id=usuario_id,
            ocurrido_en=ahora,
            datos_antes={campo: _valor_de_bitacora(getattr(fila, campo)) for campo in campos},
            datos_despues={campo: _valor_de_bitacora(valores[campo]) for campo in campos},
        )


def desactivar_proveedor(
    contexto: ContextoProveedores,
    *,
    proveedor_id: uuid.UUID,
    motivo: str,
    usuario_id: uuid.UUID,
) -> None:
    """Pasa un proveedor `ACTIVO` a `DESACTIVADO` bajo `FOR UPDATE` y asienta `DESACTIVAR` con motivo."""
    ahora = contexto.reloj()
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio_proveedor.leer_proveedor(sesion_bd, proveedor_id, para_cambio=True)
        if fila is None:
            raise NoEncontrado(recurso="proveedor", mensaje=MENSAJE_PROVEEDOR_NO_EXISTE)
        if not admite_desactivacion(EstadoProveedor(fila.estado)):
            raise ConflictoEstado(
                codigo="ESTADO_NO_PERMITE_OPERACION",
                mensaje=f"El proveedor no está activo: su estado es {fila.estado}.",
                detalle={"estado_actual": fila.estado},
                acciones=(),
            )
        repositorio_proveedor.actualizar_proveedor(
            sesion_bd, proveedor_id, {"estado": EstadoProveedor.DESACTIVADO.value}
        )
        asentar(
            sesion_bd,
            accion="DESACTIVAR",
            entidad_tipo="proveedor",
            entidad_id=proveedor_id,
            usuario_id=usuario_id,
            ocurrido_en=ahora,
            motivo=motivo,
            datos_antes={"estado": EstadoProveedor.ACTIVO.value},
            datos_despues={"estado": EstadoProveedor.DESACTIVADO.value},
        )


def _es_rfc_duplicado(error: DBAPIError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return (
        getattr(error.orig, "sqlstate", None) == _SQLSTATE_UNICIDAD
        and getattr(diag, "constraint_name", None) == _RESTRICCION_RFC
    )


def _conflicto_rfc(contexto: ContextoProveedores, rfc: str, error: DBAPIError) -> None:
    """Lee el existente en otra transacción y lanza el `409`; si no aparece, deja que el llamador relance."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        existente = repositorio_proveedor.leer_proveedor_por_rfc(sesion_bd, rfc)
    if existente is None:
        return
    raise ConflictoEstado(
        codigo="RFC_DUPLICADO",
        mensaje=f"Ya existe un proveedor con el RFC {existente.rfc}.",
        detalle={
            "proveedor_existente_id": existente.id,
            "proveedor_existente": f"{existente.nombre} · {existente.rfc}",
        },
        acciones=(),
    ) from error
