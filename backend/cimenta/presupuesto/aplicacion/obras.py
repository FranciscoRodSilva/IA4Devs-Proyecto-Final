"""Casos de uso de la obra (TKT-012a, fila A3): alta, consulta y lista.

Orquesta; no decide. El rango de los porcentajes (`PA-02`, `PA-18`) y la normalización del código viven
en `dominio/obra.py`. El alta valida el rango **antes** de abrir la transacción, abre una sola
transacción, toma la única empresa activa (A9), inserta la obra y asienta `CREAR` en la misma sesión. La
unicidad del código la arbitra `uq_obra_codigo`: su `23505` se traduce aquí a `CODIGO_OBRA_DUPLICADO`,
sin comprobación previa, así que cubre también la carrera entre dos altas simultáneas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import asentar
from cimenta.presupuesto.aplicacion.consulta_linea_base import MENSAJE_OBRA_NO_EXISTE
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_error_del_motor
from cimenta.presupuesto.dominio.obra import (
    ParametroObra,
    normalizar_codigo_obra,
    porcentajes_fuera_de_rango,
)
from cimenta.presupuesto.infraestructura import repositorio_obra
from cimenta.presupuesto.infraestructura.repositorio_obra import FilaObraCompleta
from contrato_error.acciones import Accion
from contrato_error.excepciones import (
    ConflictoEstado,
    ErrorContrato,
    ErrorDeCampo,
    NoEncontrado,
    ValidacionRechazada,
)
from tipos_base import Porcentaje

ROLES_ALTA = ("DIRECTOR_PROYECTOS", "DIRECCION_GENERAL")
ROLES_LECTURA_OBRA = (
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
)

MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."
MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."

_RESTRICCION_CODIGO = "uq_obra_codigo"
_SQLSTATE_UNICIDAD = "23505"
_MENSAJE_EMPRESA = (
    "Se esperaba exactamente una empresa activa y hay {n}; revise el despliegue (A9)."
)


@dataclass(frozen=True, slots=True)
class DatosObraNueva:
    codigo: str
    nombre: str
    domicilio: str
    tipo_contrato: str
    retencion_destajo_pct: Porcentaje
    fondo_garantia_pct: Porcentaje
    iva_acreditable: bool
    umbral_alerta_pct: Porcentaje | None


@dataclass(frozen=True, slots=True)
class ObrasConsultadas:
    elementos: tuple[FilaObraCompleta, ...]
    pagina: int
    tamano_pagina: int
    total: int


def crear_obra(
    contexto: ContextoPresupuesto, *, datos: DatosObraNueva, usuario_id: uuid.UUID
) -> uuid.UUID:
    """Da de alta una obra en `PLANEACION` y asienta `CREAR` en la misma transacción."""
    _rechazar_fuera_de_rango(datos)
    codigo = normalizar_codigo_obra(datos.codigo)
    obra_id = uuid.uuid4()
    ahora = contexto.reloj()
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            _insertar(
                sesion_bd, datos, codigo=codigo, obra_id=obra_id, ahora=ahora, usuario_id=usuario_id
            )
    except DBAPIError as error:
        traducido = _traducir_fallo_de_alta(contexto, codigo, error)
        if traducido is None:
            raise
        raise traducido from error
    return obra_id


def obtener_obra(contexto: ContextoPresupuesto, obra_id: uuid.UUID) -> FilaObraCompleta:
    """La obra completa con su línea base vigente; `NoEncontrado` si no existe."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio_obra.leer_obra_completa(sesion_bd, obra_id)
    if fila is None:
        raise NoEncontrado(recurso="obra", mensaje=MENSAJE_OBRA_NO_EXISTE)
    return fila


def listar_obras(
    contexto: ContextoPresupuesto,
    *,
    estados: frozenset[str] | None,
    pagina: int,
    tamano_pagina: int,
) -> ObrasConsultadas:
    """Una página de obras por código, con el total que cumple el filtro."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        resultado = repositorio_obra.listar_obras(
            sesion_bd,
            estados=estados,
            desplazamiento=(pagina - 1) * tamano_pagina,
            limite=tamano_pagina,
        )
    return ObrasConsultadas(
        elementos=tuple(resultado.filas),
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        total=resultado.total,
    )


def _rechazar_fuera_de_rango(datos: DatosObraNueva) -> None:
    fuera = porcentajes_fuera_de_rango(
        retencion_destajo=datos.retencion_destajo_pct,
        fondo_garantia=datos.fondo_garantia_pct,
        umbral_alerta=datos.umbral_alerta_pct,
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


def _insertar(
    sesion_bd: Session,
    datos: DatosObraNueva,
    *,
    codigo: str,
    obra_id: uuid.UUID,
    ahora: datetime,
    usuario_id: uuid.UUID,
) -> None:
    empresas = repositorio_obra.empresas_activas(sesion_bd)
    if len(empresas) != 1:
        raise RuntimeError(_MENSAJE_EMPRESA.format(n=len(empresas)))
    repositorio_obra.insertar_obra(
        sesion_bd,
        obra_id=obra_id,
        empresa_id=empresas[0],
        codigo=codigo,
        nombre=datos.nombre,
        domicilio=datos.domicilio,
        tipo_contrato=datos.tipo_contrato,
        retencion_destajo_pct=datos.retencion_destajo_pct,
        fondo_garantia_pct=datos.fondo_garantia_pct,
        iva_acreditable=datos.iva_acreditable,
        umbral_alerta_pct=datos.umbral_alerta_pct,
        creado_en=ahora,
        creado_por_id=usuario_id,
    )
    umbral = datos.umbral_alerta_pct
    asentar(
        sesion_bd,
        accion="CREAR",
        entidad_tipo="obra",
        entidad_id=obra_id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        obra_id=obra_id,
        datos_despues={
            "codigo": codigo,
            "nombre": datos.nombre,
            "domicilio": datos.domicilio,
            "tipo_contrato": datos.tipo_contrato,
            "retencion_destajo_pct": datos.retencion_destajo_pct.cuantizar().serializar(),
            "fondo_garantia_pct": datos.fondo_garantia_pct.cuantizar().serializar(),
            "iva_acreditable": datos.iva_acreditable,
            "umbral_alerta_pct": None if umbral is None else umbral.cuantizar().serializar(),
            "estado": "PLANEACION",
        },
    )


def _traducir_fallo_de_alta(
    contexto: ContextoPresupuesto, codigo: str, error: DBAPIError
) -> ErrorContrato | None:
    """El error de contrato del fallo del alta, o `None` si el caso de uso debe relanzar el original."""
    if _es_codigo_duplicado(error):
        existente = _leer_por_codigo(contexto, codigo)
        return None if existente is None else _rechazo_duplicado(existente)
    return traducir_error_del_motor(
        error,
        ruta_reintento="/api/v1/obras",
        metodo_reintento="POST",
        roles_reintento=ROLES_ALTA,
        rechazo_vigente=lambda: ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje="La operación entra en conflicto con el estado actual de los datos.",
            detalle={},
        ),
    )


def _es_codigo_duplicado(error: DBAPIError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return (
        getattr(error.orig, "sqlstate", None) == _SQLSTATE_UNICIDAD
        and getattr(diag, "constraint_name", None) == _RESTRICCION_CODIGO
    )


def _leer_por_codigo(contexto: ContextoPresupuesto, codigo: str) -> FilaObraCompleta | None:
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        return repositorio_obra.leer_obra_por_codigo(sesion_bd, codigo)


def _rechazo_duplicado(existente: FilaObraCompleta) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="CODIGO_OBRA_DUPLICADO",
        mensaje=f"Ya existe una obra con el código {existente.codigo}.",
        detalle={
            "obra_existente_id": existente.id,
            "obra_existente": f"{existente.codigo} · {existente.nombre}",
        },
        acciones=(Accion("VER_OBRA", "GET", f"/api/v1/obras/{existente.id}", ROLES_LECTURA_OBRA),),
    )
