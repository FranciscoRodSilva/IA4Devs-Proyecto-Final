"""Casos de uso de mantenimiento de la obra (TKT-012b, fila A5): actualizar y eliminar.

Orquesta; no decide. La edición (PA-02, PA-18) y el borrado (RN-01, HDU-001 esc. 20) comparten el
molde: una transacción por caso de uso, `SELECT ... FOR UPDATE` de la obra **antes** de leer su estado o
contar su historial, y el asiento de bitácora en la misma sesión. Las decisiones viven en
`dominio/ciclo_vida_obra.py` y `dominio/historial_obra.py`. La regla de edición vive en las decisiones D-2
y D-3 de la spec de TKT-012b y no tiene `RN` en el PRD: por eso el asiento de `ACTUALIZAR` no cita regla
(F002a). La única traducción propia es la de la clave
foránea hija (`23001`) a `OBRA_CON_HISTORIAL` (D-DIS-4), que llega antes que el genérico de
`traducir_error_del_motor`.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import asentar
from cimenta.presupuesto.aplicacion.ciclo_vida_obra import (
    MENSAJE_ESTADO_NO_PERMITE,
    acciones_de_operaciones,
)
from cimenta.presupuesto.aplicacion.consulta_linea_base import MENSAJE_OBRA_NO_EXISTE
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.historial_obra import contar_historial
from cimenta.presupuesto.aplicacion.obras import (
    MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
    MENSAJE_UMBRAL_NEGATIVO,
    ROLES_ALTA,
)
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_fallo_de_obra
from cimenta.presupuesto.dominio.ciclo_vida_obra import (
    DatosObraEditables,
    EstadoObraDominio,
    OperacionObra,
    ValorEditable,
    admite_edicion,
    cambios_efectivos,
    operaciones_admitidas,
)
from cimenta.presupuesto.dominio.historial_obra import ConteosHistorial, hay_historial
from cimenta.presupuesto.dominio.obra import ParametroObra, porcentajes_fuera_de_rango
from cimenta.presupuesto.infraestructura import repositorio_obra
from cimenta.presupuesto.infraestructura.repositorio_obra import FilaObraCompleta
from contrato_error.excepciones import (
    ConflictoEstado,
    ErrorContrato,
    ErrorDeCampo,
    NoEncontrado,
    ValidacionRechazada,
)
from tipos_base import Porcentaje

_SQLSTATE_CLAVE_FORANEA_HIJA = "23001"
_MENSAJE_CON_HISTORIAL = "La obra {codigo} tiene historial y no se puede eliminar."
_CERO = Porcentaje("0")
# Las acciones del `409` `OBRA_CON_HISTORIAL` que el borrador declara: solo suspender y cerrar.
_OPERACIONES_CON_HISTORIAL: frozenset[OperacionObra] = frozenset(
    {OperacionObra.SUSPENDER, OperacionObra.CERRAR}
)


def actualizar_obra(
    contexto: ContextoPresupuesto,
    obra_id: uuid.UUID,
    cambios: Mapping[str, ValorEditable],
    usuario_id: uuid.UUID,
) -> None:
    """Edita los campos que cambian y asienta `ACTUALIZAR` en la misma transacción, sin cita de regla (D-3)."""
    _rechazar_fuera_de_rango(cambios)
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            obra = repositorio_obra.bloquear_obra_completa(sesion_bd, obra_id)
            if obra is None:
                raise NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)
            ahora = contexto.reloj()
            estado = EstadoObraDominio(obra.estado)
            if not admite_edicion(estado):
                raise ConflictoEstado(
                    codigo="ESTADO_NO_PERMITE_OPERACION",
                    mensaje=MENSAJE_ESTADO_NO_PERMITE.format(
                        codigo=obra.codigo, estado=estado.value
                    ),
                    detalle={"estado": estado.value},
                )
            efectivos = cambios_efectivos(_datos_editables(obra), cambios)
            if not efectivos.despues:
                return
            repositorio_obra.actualizar_obra(
                sesion_bd, obra_id, efectivos.despues, ahora, usuario_id
            )
            asentar(
                sesion_bd,
                accion="ACTUALIZAR",
                entidad_tipo="obra",
                entidad_id=obra_id,
                usuario_id=usuario_id,
                ocurrido_en=ahora,
                obra_id=obra_id,
                regla_negocio=None,
                datos_antes={campo: _serializar(valor) for campo, valor in efectivos.antes.items()},
                datos_despues={
                    campo: _serializar(valor) for campo, valor in efectivos.despues.items()
                },
            )
    except DBAPIError as error:
        traducido = traducir_fallo_de_obra(
            error,
            ruta_reintento=f"/api/v1/obras/{obra_id}",
            metodo_reintento="PATCH",
            roles_reintento=ROLES_ALTA,
        )
        if traducido is None:
            raise
        raise traducido from error


def eliminar_obra(
    contexto: ContextoPresupuesto,
    obra_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> None:
    """Borra la obra sin historial y asienta `ELIMINAR` en la misma transacción (RN-01)."""
    obra_bloqueada: FilaObraCompleta | None = None
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            obra = repositorio_obra.bloquear_obra_completa(sesion_bd, obra_id)
            if obra is None:
                raise NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)
            obra_bloqueada = obra
            ahora = contexto.reloj()
            conteos = contar_historial(sesion_bd, contexto, obra_id)
            if hay_historial(conteos):
                raise _rechazo_con_historial(obra, _detalle_de_conteos(conteos))
            _asentar_eliminacion(sesion_bd, obra, usuario_id=usuario_id, ahora=ahora)
            repositorio_obra.eliminar_obra(sesion_bd, obra_id)
    except DBAPIError as error:
        traducido = _traducir_fallo_de_borrado(obra_id, obra_bloqueada, error)
        if traducido is None:
            raise
        raise traducido from error


def _rechazar_fuera_de_rango(cambios: Mapping[str, ValorEditable]) -> None:
    """Valida solo los porcentajes presentes, con los mismos mensajes del alta, antes de la transacción."""
    retencion = cambios.get("retencion_destajo_pct")
    fondo = cambios.get("fondo_garantia_pct")
    umbral = cambios.get("umbral_alerta_pct")
    fuera = porcentajes_fuera_de_rango(
        retencion_destajo=retencion if isinstance(retencion, Porcentaje) else _CERO,
        fondo_garantia=fondo if isinstance(fondo, Porcentaje) else _CERO,
        umbral_alerta=umbral if isinstance(umbral, Porcentaje) else None,
    )
    if not fuera:
        return
    raise ValidacionRechazada(
        errores=[
            ErrorDeCampo(
                campo=parametro.value,
                codigo="FUERA_DE_RANGO",
                mensaje=(
                    MENSAJE_UMBRAL_NEGATIVO
                    if parametro is ParametroObra.UMBRAL_ALERTA
                    else MENSAJE_PORCENTAJE_FUERA_DE_RANGO
                ),
            )
            for parametro in fuera
        ]
    )


def _datos_editables(obra: FilaObraCompleta) -> DatosObraEditables:
    return DatosObraEditables(
        nombre=obra.nombre,
        domicilio=obra.domicilio,
        retencion_destajo_pct=obra.retencion_destajo_pct,
        fondo_garantia_pct=obra.fondo_garantia_pct,
        iva_acreditable=obra.iva_acreditable,
        umbral_alerta_pct=obra.umbral_alerta_pct,
    )


def _serializar(valor: ValorEditable) -> str | bool | None:
    """Los porcentajes viajan como cadena de escala 6; el resto, tal cual."""
    return valor.cuantizar().serializar() if isinstance(valor, Porcentaje) else valor


def _asentar_eliminacion(
    sesion_bd: Session, obra: FilaObraCompleta, *, usuario_id: uuid.UUID, ahora: datetime
) -> None:
    umbral = obra.umbral_alerta_pct
    asentar(
        sesion_bd,
        accion="ELIMINAR",
        entidad_tipo="obra",
        entidad_id=obra.id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        obra_id=obra.id,
        regla_negocio="RN-01",
        datos_antes={
            "codigo": obra.codigo,
            "nombre": obra.nombre,
            "domicilio": obra.domicilio,
            "tipo_contrato": obra.tipo_contrato,
            "retencion_destajo_pct": obra.retencion_destajo_pct.cuantizar().serializar(),
            "fondo_garantia_pct": obra.fondo_garantia_pct.cuantizar().serializar(),
            "iva_acreditable": obra.iva_acreditable,
            "umbral_alerta_pct": None if umbral is None else umbral.cuantizar().serializar(),
            "estado": obra.estado,
        },
    )


def _detalle_de_conteos(conteos: ConteosHistorial) -> dict[str, object]:
    return {
        "linea_base_congelada": conteos.linea_base_congelada,
        "lineas_base": conteos.lineas_base,
        "importaciones": conteos.importaciones,
        "movimientos": conteos.movimientos,
    }


def _rechazo_con_historial(obra: FilaObraCompleta, detalle: dict[str, object]) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="OBRA_CON_HISTORIAL",
        mensaje=_MENSAJE_CON_HISTORIAL.format(codigo=obra.codigo),
        detalle=detalle,
        acciones=acciones_de_operaciones(
            obra.id,
            operaciones_admitidas(EstadoObraDominio(obra.estado)),
            solo=_OPERACIONES_CON_HISTORIAL,
        ),
    )


def _traducir_fallo_de_borrado(
    obra_id: uuid.UUID, obra_bloqueada: FilaObraCompleta | None, error: DBAPIError
) -> ErrorContrato | None:
    """D-DIS-4: la clave foránea hija es `OBRA_CON_HISTORIAL`, sin el nombre de la restricción; lo demás, al traductor."""
    if (
        getattr(error.orig, "sqlstate", None) == _SQLSTATE_CLAVE_FORANEA_HIJA
        and obra_bloqueada is not None
    ):
        return _rechazo_con_historial(
            obra_bloqueada,
            {
                "linea_base_congelada": False,
                "lineas_base": 0,
                "importaciones": 0,
                "movimientos": 1,
            },
        )
    return traducir_fallo_de_obra(
        error,
        ruta_reintento=f"/api/v1/obras/{obra_id}",
        metodo_reintento="DELETE",
        roles_reintento=ROLES_ALTA,
    )
