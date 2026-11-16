"""Casos de uso del catálogo de proveedores (TKT-029a, fila A4): alta, consulta, lista, cambio, desactivación y baja (TKT-029b).

Orquesta; no decide. La normalización del RFC, la regla de qué estado admite la desactivación y la
que decide la baja (`rechazo_de_baja`) viven en `dominio/proveedor.py`. Cada caso de uso abre una
sola transacción y asienta la bitácora en ella. La unicidad del RFC la arbitra `uq_proveedor_rfc`:
su `23505` se traduce aquí a `RFC_DUPLICADO`, sin comprobación previa, así que cubre también la
carrera entre dos altas simultáneas.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final, assert_never

from sqlalchemy.exc import DBAPIError

from cimenta.auditoria.interfaz import asentar
from cimenta.compras.interfaz import OrdenPendiente, ordenes_pendientes_de_proveedor
from cimenta.proveedores.aplicacion.contexto import ContextoProveedores
from cimenta.proveedores.dominio.proveedor import (
    EstadoProveedor,
    RechazoBaja,
    admite_desactivacion,
    rechazo_de_baja,
)
from cimenta.proveedores.infraestructura import repositorio_proveedor
from cimenta.proveedores.infraestructura.repositorio_proveedor import FilaProveedor
from contrato_error.acciones import Accion
from contrato_error.excepciones import ConcurrenciaVencida, ConflictoEstado, NoEncontrado
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
MENSAJE_YA_DADO_DE_BAJA = "El proveedor ya está dado de baja: su estado es BAJA."

_RESTRICCION_RFC = "uq_proveedor_rfc"
_SQLSTATE_UNICIDAD = "23505"

_ESPERA_BLOQUEO_MS = 5000
_ESPERA_EJECUCION_MS = 15000
_MENSAJE_BLOQUEO = (
    "Otra operación está modificando este proveedor en este momento. Vuelve a intentarlo."
)
_MENSAJE_TIEMPO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."


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
    with _traducir_concurrencia("POST", "/api/v1/proveedores"):
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
                with contexto.fabrica_sesiones().begin() as sesion_bd:
                    existente = repositorio_proveedor.leer_proveedor_por_rfc(sesion_bd, datos.rfc)
                if existente is not None:
                    raise _rechazo_rfc_duplicado(existente) from error
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
    if not cambios.presentes or not cambios.presentes <= CAMPOS_CAMBIABLES:
        raise ValueError(
            "Los campos presentes deben ser un subconjunto no vacío de "
            f"{sorted(CAMPOS_CAMBIABLES)}; llegó {sorted(cambios.presentes)}."
        )
    ahora = contexto.reloj()
    with (
        _traducir_concurrencia("PATCH", f"/api/v1/proveedores/{proveedor_id}"),
        contexto.fabrica_sesiones().begin() as sesion_bd,
    ):
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
    with (
        _traducir_concurrencia("POST", f"/api/v1/proveedores/{proveedor_id}/desactivacion"),
        contexto.fabrica_sesiones().begin() as sesion_bd,
    ):
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


def dar_baja_proveedor(
    contexto: ContextoProveedores,
    *,
    proveedor_id: uuid.UUID,
    motivo: str,
    usuario_id: uuid.UUID,
) -> None:
    """Pasa un proveedor `ACTIVO` o `DESACTIVADO` a `BAJA` y asienta `DAR_BAJA` con motivo (CA-1 a CA-4, CA-7, CA-10, CA-11).

    Una sola transacción. El `FOR UPDATE` sobre el proveedor precede a la lectura de sus órdenes
    pendientes, así que dos bajas simultáneas se serializan y la segunda ve `BAJA` (CA-11). Los rechazos
    se lanzan dentro de la transacción: se revierte y no queda asiento. La bitácora guarda el estado
    leído como `datos_antes`, no un literal.
    """
    ahora = contexto.reloj()
    with (
        _traducir_concurrencia("POST", f"/api/v1/proveedores/{proveedor_id}/baja"),
        contexto.fabrica_sesiones().begin() as sesion_bd,
    ):
        fila = repositorio_proveedor.leer_proveedor(sesion_bd, proveedor_id, para_cambio=True)
        if fila is None:
            raise NoEncontrado(recurso="proveedor", mensaje=MENSAJE_PROVEEDOR_NO_EXISTE)
        estado = EstadoProveedor(fila.estado)
        pendientes = ordenes_pendientes_de_proveedor(sesion_bd, proveedor_id)
        rechazo = rechazo_de_baja(estado, len(pendientes))
        match rechazo:
            case None:
                pass
            case RechazoBaja.ESTADO_TERMINAL:
                raise ConflictoEstado(
                    codigo="ESTADO_NO_PERMITE_OPERACION",
                    mensaje=MENSAJE_YA_DADO_DE_BAJA,
                    detalle={"estado_actual": fila.estado},
                    acciones=(),
                )
            case RechazoBaja.ORDENES_PENDIENTES:
                raise _rechazo_ordenes_pendientes(fila, estado, pendientes)
            case _ as nunca:
                assert_never(nunca)
        repositorio_proveedor.actualizar_proveedor(
            sesion_bd, proveedor_id, {"estado": EstadoProveedor.BAJA.value}
        )
        asentar(
            sesion_bd,
            accion="DAR_BAJA",
            entidad_tipo="proveedor",
            entidad_id=proveedor_id,
            usuario_id=usuario_id,
            ocurrido_en=ahora,
            motivo=motivo,
            datos_antes={"estado": fila.estado},
            datos_despues={"estado": EstadoProveedor.BAJA.value},
        )


def _texto_ordenes(n: int) -> str:
    return "1 orden pendiente" if n == 1 else f"{n} órdenes pendientes"


def _rechazo_ordenes_pendientes(
    fila: FilaProveedor, estado: EstadoProveedor, pendientes: tuple[OrdenPendiente, ...]
) -> ConflictoEstado:
    """CA-3 y CA-4: lista las órdenes pendientes y ofrece desactivar solo si el proveedor sigue `ACTIVO`."""
    texto = _texto_ordenes(len(pendientes))
    detalle = {
        "ordenes": [{"id": o.id, "folio": o.folio, "estado": o.estado.value} for o in pendientes]
    }
    if admite_desactivacion(estado):
        return ConflictoEstado(
            codigo="PROVEEDOR_CON_ORDENES_ABIERTAS",
            mensaje=(
                f"{fila.nombre} tiene {texto} de recibir; se puede desactivar para órdenes "
                "nuevas conservando las existentes."
            ),
            detalle=detalle,
            acciones=(
                Accion(
                    "DESACTIVAR_PROVEEDOR",
                    "POST",
                    f"/api/v1/proveedores/{fila.id}/desactivacion",
                    ROLES_GESTION,
                ),
            ),
        )
    return ConflictoEstado(
        codigo="PROVEEDOR_CON_ORDENES_ABIERTAS",
        mensaje=(
            f"{fila.nombre} tiene {texto} de recibir y ya está desactivado; la baja procede "
            "cuando esas órdenes se reciban completas o se cancelen."
        ),
        detalle=detalle,
        acciones=(),
    )


@contextmanager
def _traducir_concurrencia(metodo: str, ruta: str) -> Iterator[None]:
    """RNF-16: `55P03` (`lock_timeout`) y `57014` (`statement_timeout`) son `CONCURRENCIA`; el resto se relanza."""
    try:
        yield
    except DBAPIError as error:
        sqlstate = getattr(error.orig, "sqlstate", None)
        if sqlstate == "55P03":
            codigo, mensaje, espera = "BLOQUEO_VENCIDO", _MENSAJE_BLOQUEO, _ESPERA_BLOQUEO_MS
        elif sqlstate == "57014":
            codigo, mensaje, espera = (
                "TIEMPO_EJECUCION_VENCIDO",
                _MENSAJE_TIEMPO,
                _ESPERA_EJECUCION_MS,
            )
        else:
            raise
        raise ConcurrenciaVencida(
            codigo=codigo,
            mensaje=mensaje,
            espera_maxima_ms=espera,
            reintentar_en_s=1,
            acciones=[Accion("REINTENTAR", metodo, ruta, ROLES_GESTION)],
        ) from error


def _es_rfc_duplicado(error: DBAPIError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return (
        getattr(error.orig, "sqlstate", None) == _SQLSTATE_UNICIDAD
        and getattr(diag, "constraint_name", None) == _RESTRICCION_RFC
    )


def _rechazo_rfc_duplicado(existente: FilaProveedor) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="RFC_DUPLICADO",
        mensaje=f"Ya existe un proveedor con el RFC {existente.rfc}.",
        detalle={
            "proveedor_existente_id": existente.id,
            "proveedor_existente": f"{existente.nombre} · {existente.rfc}",
        },
        acciones=(),
    )
