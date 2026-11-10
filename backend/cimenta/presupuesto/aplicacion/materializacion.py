"""Caso de uso de la confirmación de una importación: materializa la línea base (TKT-017a3, fila A6a).

Orquesta; no decide. La regla de cómo una preparación se convierte en filas vive en
`dominio/materializacion.py` (`RN-01`, `PA-T8`, `PA-T13`, `PA-T17`). Aquí se abre una sola
transacción, se bloquea la importación y después la obra, se comprueban las precondiciones en el
orden de «Orden de comprobaciones de la materialización» del diseño, se persiste el plan y se asienta
`CONFIRMAR` en la misma transacción. Los rechazos salen por el contrato de error.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import asentar, consultar_bitacora
from cimenta.presupuesto.aplicacion.causas_explosion import detalle_de_causas
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.traduccion_motor import (
    MENSAJE_PREPARACION_ILEGIBLE,
    traducir_error_del_motor,
)
from cimenta.presupuesto.dominio.importacion import EstadoImportacion
from cimenta.presupuesto.dominio.materializacion import (
    AsignacionInvalida,
    CausaRechazoConfirmacion,
    ConfirmacionAdmitida,
    ExplosionRechazada,
    InsumoEnConflicto,
    LineaBaseDeObra,
    PlanMaterializacion,
    PreparacionInconsistente,
    ResultadoConfirmacion,
    evaluar_confirmacion_en_obra,
    evaluar_importacion_confirmable,
    planificar_materializacion,
)
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from cimenta.presupuesto.infraestructura import repositorio_importacion, repositorio_linea_base
from cimenta.presupuesto.infraestructura.preparacion_json import (
    FormatoPreparacionDesconocido,
    preparacion_desde_json,
)
from cimenta.presupuesto.infraestructura.repositorio_linea_base import FilaLineaBase, FilaObra
from contrato_error import (
    Accion,
    ConflictoEstado,
    ErrorContrato,
    ErrorDeCampo,
    NoEncontrado,
    ValidacionRechazada,
)
from tipos_base import Dinero

_ROLES_CONFIRMACION = ("DIRECTOR_PROYECTOS",)
_CAMPO_ASIGNACION = "asignacion_tipos_partida"

_MENSAJE_IMPORTACION_NO_EXISTE = "La importación no existe."
_MENSAJE_CON_ERRORES = "La importación tiene errores bloqueantes y no se confirma."
_MENSAJE_ESTADO = (
    "La importación está en {estado} y no se confirma. Solo se confirma una importación VALIDADO."
)
_MENSAJE_CONGELADA = (
    "La obra {codigo} ya tiene una línea base congelada; no admite otra importación."
)
_MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
_MENSAJE_REEMPLAZO = (
    "La obra ya tiene una línea base en borrador; confirmar esta importación la reemplaza."
)
_MENSAJE_INSUMO_EN_CONFLICTO = (
    "El insumo {codigo} ya existe con otra unidad o tipo; la importación debe analizarse de nuevo."
)
_MENSAJE_EXPLOSION = "La explosión de insumos de la importación no se puede calcular."
_MENSAJE_FALTA_TIPO = "Falta el tipo de partida de esta partida."
_MENSAJE_TIPO_INEXISTENTE = "El tipo de partida no existe."
_MENSAJE_CLAVES_AMBIGUAS = "Hay dos claves con distinto tipo para esta partida; deja una sola."
_MENSAJE_OBLIGATORIO = "El campo es obligatorio."


@dataclass(frozen=True, slots=True)
class LineaBaseMaterializada:
    importacion_id: uuid.UUID
    linea_base_id: uuid.UUID
    version: int
    importe_venta: Dinero


def materializar_importacion(
    contexto: ContextoPresupuesto,
    *,
    importacion_id: uuid.UUID,
    asignacion_tipos_partida: Mapping[str, uuid.UUID],
    reemplazar_borrador: bool,
    motivo_reemplazo: str | None,
    usuario_id: uuid.UUID,
) -> LineaBaseMaterializada:
    """Confirma una importación `VALIDADO`: crea la jerarquía y una línea base `BORRADOR` (RN-01)."""
    fabrica = contexto.fabrica_sesiones()
    try:
        with fabrica.begin() as sesion_bd:
            return _materializar(
                sesion_bd,
                contexto,
                importacion_id=importacion_id,
                asignacion=asignacion_tipos_partida,
                reemplazar_borrador=reemplazar_borrador,
                motivo_reemplazo=motivo_reemplazo,
                usuario_id=usuario_id,
            )
    except DBAPIError as error:
        traducido = traducir_error_del_motor(
            error,
            ruta_reintento=_ruta_confirmacion(importacion_id),
            metodo_reintento="POST",
            roles_reintento=_ROLES_CONFIRMACION,
            rechazo_vigente=lambda: _rechazo_vigente(contexto, importacion_id),
        )
        if traducido is None:
            raise
        raise traducido from error


def _ruta_confirmacion(importacion_id: uuid.UUID) -> str:
    return f"/api/v1/importaciones/{importacion_id}/confirmacion"


def _materializar(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    importacion_id: uuid.UUID,
    asignacion: Mapping[str, uuid.UUID],
    reemplazar_borrador: bool,
    motivo_reemplazo: str | None,
    usuario_id: uuid.UUID,
) -> LineaBaseMaterializada:
    repositorio = repositorio_linea_base
    importacion = repositorio_importacion.bloquear_importacion(sesion_bd, importacion_id)
    if importacion is None:
        raise NoEncontrado(recurso="importacion", mensaje=_MENSAJE_IMPORTACION_NO_EXISTE)
    _rechazar_si_no_confirmable(importacion_id, importacion.estado)

    obra = repositorio.bloquear_obra(sesion_bd, importacion.obra_id)
    if obra is None:
        raise NoEncontrado(recurso="obra", mensaje="La obra no existe.")
    lineas = repositorio.lineas_base_de_obra(sesion_bd, obra.id)
    congelada = _linea_en_estado(lineas, "CONGELADA")
    borrador = _linea_en_estado(lineas, "BORRADOR")
    _rechazar_si_obra_no_admite(
        importacion_id,
        obra,
        evaluar_confirmacion_en_obra(
            estado_obra=obra.estado,
            congelada=congelada,
            borrador=borrador,
            reemplazar_borrador=reemplazar_borrador,
            motivo_reemplazo=motivo_reemplazo,
        ),
        congelada,
    )

    plan = _plan(sesion_bd, importacion_id, asignacion)
    if borrador is not None:
        _descartar_borrador(
            sesion_bd,
            contexto,
            obra_id=obra.id,
            borrador=borrador,
            motivo=motivo_reemplazo,
            usuario_id=usuario_id,
        )
    return _persistir(
        sesion_bd,
        contexto,
        importacion_id=importacion_id,
        obra_id=obra.id,
        version=repositorio.version_siguiente(sesion_bd, obra.id),
        plan=plan,
        usuario_id=usuario_id,
    )


def _descartar_borrador(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    obra_id: uuid.UUID,
    borrador: LineaBaseDeObra,
    motivo: str | None,
    usuario_id: uuid.UUID,
) -> None:
    """Borra el borrador y su jerarquía y asienta `DESCARTAR`; ya con el plan aceptado."""
    importacion_anterior = _importacion_del_borrador(sesion_bd, borrador.id)
    repositorio_linea_base.borrar_jerarquia(sesion_bd, obra_id, borrador.id)
    asentar(
        sesion_bd,
        accion="DESCARTAR",
        entidad_tipo="linea_base",
        entidad_id=borrador.id,
        usuario_id=usuario_id,
        ocurrido_en=contexto.reloj(),
        motivo=motivo,
        obra_id=obra_id,
        datos_antes={
            "estado": "BORRADOR",
            "version": borrador.version,
            "importacion_id": importacion_anterior,
        },
    )


def _importacion_del_borrador(sesion_bd: Session, borrador_id: uuid.UUID) -> str | None:
    """La importación que lo creó, del asiento `CONFIRMAR`; nula si el borrador se sembró sin él (P-5)."""
    pagina = consultar_bitacora(
        sesion_bd,
        entidad_tipo="linea_base",
        entidad_id=borrador_id,
        accion=("CONFIRMAR",),
        tamano_pagina=1,
    )
    if not pagina.elementos:
        return None
    origen = (pagina.elementos[0].datos_despues or {}).get("importacion_id")
    return origen if isinstance(origen, str) else None


def _linea_en_estado(lineas: list[FilaLineaBase], estado: str) -> LineaBaseDeObra | None:
    linea = next((linea for linea in lineas if linea.estado == estado), None)
    return None if linea is None else LineaBaseDeObra(id=linea.id, version=linea.version)


def _rechazar_si_no_confirmable(importacion_id: uuid.UUID, estado: EstadoImportacion) -> None:
    resultado = evaluar_importacion_confirmable(estado)
    if isinstance(resultado, ConfirmacionAdmitida):
        return
    detalle = {"importacion_id": importacion_id, "estado": estado.value}
    if resultado.causa == CausaRechazoConfirmacion.IMPORTACION_CON_ERRORES:
        raise ConflictoEstado(
            codigo="IMPORTACION_CON_ERRORES", mensaje=_MENSAJE_CON_ERRORES, detalle=detalle
        )
    raise ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje=_MENSAJE_ESTADO.format(estado=estado.value),
        detalle=detalle,
    )


def _rechazar_si_obra_no_admite(
    importacion_id: uuid.UUID,
    obra: FilaObra,
    resultado: ResultadoConfirmacion,
    congelada: LineaBaseDeObra | None,
) -> None:
    """Traduce la causa del dominio a su contrato de error; no decide ninguna regla."""
    if isinstance(resultado, ConfirmacionAdmitida):
        return
    causa, datos = resultado.causa, resultado.datos
    nombre_completo = f"{obra.codigo} · {obra.nombre}"
    if causa == CausaRechazoConfirmacion.OBRA_CON_CONGELADA and congelada is not None:
        raise _conflicto_obra_con_congelada(obra, congelada)
    if causa == CausaRechazoConfirmacion.OBRA_FUERA_DE_PLANEACION:
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_FUERA_DE_PLANEACION.format(
                codigo=obra.codigo, estado=datos["estado_obra"]
            ),
            detalle={"obra": nombre_completo, **datos},
        )
    if causa == CausaRechazoConfirmacion.REEMPLAZO_NO_CONFIRMADO:
        raise ConflictoEstado(
            codigo="REEMPLAZO_NO_CONFIRMADO",
            mensaje=_MENSAJE_REEMPLAZO,
            detalle=datos,
            acciones=(
                Accion(
                    "CONFIRMAR_REEMPLAZO",
                    "POST",
                    _ruta_confirmacion(importacion_id),
                    _ROLES_CONFIRMACION,
                ),
            ),
        )
    if causa == CausaRechazoConfirmacion.MOTIVO_REEMPLAZO_OBLIGATORIO:
        raise ValidacionRechazada(
            errores=[
                ErrorDeCampo(
                    campo="motivo_reemplazo", codigo="OBLIGATORIO", mensaje=_MENSAJE_OBLIGATORIO
                )
            ]
        )
    raise AssertionError(causa)


def _conflicto_obra_con_congelada(obra: FilaObra, vigente: LineaBaseDeObra) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje=_MENSAJE_CONGELADA.format(codigo=obra.codigo),
        detalle={
            "obra": f"{obra.codigo} · {obra.nombre}",
            "linea_base_vigente_id": vigente.id,
            "version_vigente": vigente.version,
        },
    )


def _plan(
    sesion_bd: Session, importacion_id: uuid.UUID, asignacion: Mapping[str, uuid.UUID]
) -> PlanMaterializacion:
    preparacion = _leer_preparacion(sesion_bd, importacion_id)
    resultado = planificar_materializacion(
        preparacion,
        asignacion=asignacion,
        tipos_partida=repositorio_linea_base.tipos_partida(sesion_bd),
        insumos_registrados=repositorio_linea_base.insumos_registrados(sesion_bd),
        nuevo_id=uuid.uuid4,
    )
    if isinstance(resultado, PlanMaterializacion):
        return resultado
    if isinstance(resultado, AsignacionInvalida):
        raise _rechazo_asignacion(resultado)
    if isinstance(resultado, PreparacionInconsistente):
        raise _rechazo_ilegible(
            {
                "importacion_id": importacion_id,
                "motivo": resultado.motivo,
                "codigo_concepto": resultado.codigo_concepto,
            }
        )
    if isinstance(resultado, InsumoEnConflicto):
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_INSUMO_EN_CONFLICTO.format(codigo=resultado.codigo),
            detalle={
                "codigo": resultado.codigo,
                "unidad_importacion": resultado.unidad_importacion,
                "tipo_importacion": resultado.tipo_importacion.value,
                "unidad_registrada": resultado.unidad_registrada,
                "tipo_registrado": resultado.tipo_registrado.value,
            },
        )
    raise _rechazo_explosion(importacion_id, resultado)


def _leer_preparacion(sesion_bd: Session, importacion_id: uuid.UUID) -> Preparacion:
    documento = repositorio_importacion.leer_preparacion(sesion_bd, importacion_id)
    if documento is None:
        raise _rechazo_formato(importacion_id, None)
    try:
        return preparacion_desde_json(documento)
    except FormatoPreparacionDesconocido as error:
        raise _rechazo_formato(importacion_id, error.formato) from error


def _rechazo_formato(importacion_id: uuid.UUID, formato: object) -> ConflictoEstado:
    admitido = formato if formato is None or isinstance(formato, bool | int | str) else str(formato)
    return _rechazo_ilegible({"importacion_id": importacion_id, "formato": admitido})


def _rechazo_ilegible(detalle: Mapping[str, object]) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION", mensaje=MENSAJE_PREPARACION_ILEGIBLE, detalle=detalle
    )


def _rechazo_asignacion(invalida: AsignacionInvalida) -> ValidacionRechazada:
    grupos = (
        (invalida.faltantes, "OBLIGATORIO", _MENSAJE_FALTA_TIPO),
        (invalida.inexistentes, "VALOR_NO_PERMITIDO", _MENSAJE_TIPO_INEXISTENTE),
        (invalida.ambiguas, "VALOR_NO_PERMITIDO", _MENSAJE_CLAVES_AMBIGUAS),
    )
    return ValidacionRechazada(
        errores=[
            ErrorDeCampo(campo=f"{_CAMPO_ASIGNACION}.{nombre}", codigo=codigo, mensaje=mensaje)
            for nombres, codigo, mensaje in grupos
            for nombre in nombres
        ]
    )


def _rechazo_explosion(importacion_id: uuid.UUID, rechazada: ExplosionRechazada) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje=_MENSAJE_EXPLOSION,
        detalle={
            "importacion_id": importacion_id,
            "causas": detalle_de_causas(rechazada.causas),
        },
    )


def _persistir(
    sesion_bd: Session,
    contexto: ContextoPresupuesto,
    *,
    importacion_id: uuid.UUID,
    obra_id: uuid.UUID,
    version: int,
    plan: PlanMaterializacion,
    usuario_id: uuid.UUID,
) -> LineaBaseMaterializada:
    repositorio = repositorio_linea_base
    ahora = contexto.reloj()
    linea_base_id = uuid.uuid4()
    repositorio.insertar_insumos(sesion_bd, plan.insumos_insertar)
    repositorio.insertar_niveles(sesion_bd, obra_id, plan.niveles)
    repositorio.insertar_areas(sesion_bd, plan.areas)
    repositorio.insertar_partidas(sesion_bd, plan.partidas)
    repositorio.insertar_conceptos(sesion_bd, obra_id, plan.conceptos)
    repositorio.insertar_partidas_concepto(sesion_bd, plan.partidas_concepto)
    repositorio.insertar_apus(sesion_bd, plan.apus)
    repositorio.insertar_linea_base(
        sesion_bd,
        linea_base_id=linea_base_id,
        obra_id=obra_id,
        version=version,
        importe_venta=plan.importe_venta,
        creado_en=ahora,
        creado_por_id=usuario_id,
    )
    repositorio.confirmar_importacion(sesion_bd, importacion_id)
    asentar(
        sesion_bd,
        accion="CONFIRMAR",
        entidad_tipo="linea_base",
        entidad_id=linea_base_id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        obra_id=obra_id,
        datos_despues={
            "importacion_id": str(importacion_id),
            "version": version,
            "importe_venta": plan.importe_venta.serializar(),
        },
    )
    return LineaBaseMaterializada(
        importacion_id=importacion_id,
        linea_base_id=linea_base_id,
        version=version,
        importe_venta=plan.importe_venta,
    )


def _rechazo_vigente(contexto: ContextoPresupuesto, importacion_id: uuid.UUID) -> ErrorContrato:
    """Transacción corta de solo lectura: el rechazo de la congelada vigente tras perder la carrera."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        obra_id = repositorio_linea_base.obra_de_importacion(sesion_bd, importacion_id)
        obra = None if obra_id is None else repositorio_linea_base.leer_obra(sesion_bd, obra_id)
        if obra is not None:
            lineas = repositorio_linea_base.lineas_base_de_obra(sesion_bd, obra.id)
            vigente = _linea_en_estado(lineas, "CONGELADA")
            if vigente is not None:
                return _conflicto_obra_con_congelada(obra, vigente)
    return NoEncontrado(recurso="importacion", mensaje=_MENSAJE_IMPORTACION_NO_EXISTE)
