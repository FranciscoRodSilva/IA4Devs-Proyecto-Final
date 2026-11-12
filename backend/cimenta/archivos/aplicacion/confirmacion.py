"""Confirmación de un archivo subido (TKT-059, fila 12a).

Implementa RNF-06, RNF-19, RNF-16, PA-T59.8 y PA-T59.13. `confirmar_archivo` bloquea la fila con
`SELECT ... FOR UPDATE`, decide el estado previo con `evaluar_previa`, coteja el objeto realmente
almacenado con `comparar_objeto`, lee su tipo de los bytes y, si todo coincide, reescribe el tipo del
objeto, pasa la fila a `DISPONIBLE` y asienta `CONFIRMAR` en la misma transacción. Aquí solo se
orquesta: las reglas viven en `dominio/`.

Los once pasos y sus resultados están en «Orden de comprobaciones de la confirmación» del diseño.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

import structlog
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.archivos.dominio.confirmacion import (
    Discrepancia,
    EstadoArchivo,
    ObjetoAlmacenado,
    PasoPrevio,
    comparar_objeto,
    evaluar_previa,
)
from cimenta.archivos.dominio.tipos import tipo_admitido, tipos_admitidos
from cimenta.archivos.infraestructura import repositorio
from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo
from cimenta.auditoria import interfaz as auditoria  # el módulo, no el nombre: TC-16 lo sustituye
from cimenta.identidad.interfaz import nombres_de_usuarios
from contrato_error.acciones import Accion
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    NoEncontrado,
    PermisoDenegado,
)

# `auditoria` se exporta a propósito: TC-16 sustituye `auditoria.asentar` y mypy exige que el módulo lo publique.
__all__ = ["ROL_DE_CONFIRMACION", "ArchivoLeido", "auditoria", "confirmar_archivo"]

_registro = structlog.get_logger("cimenta.archivos")

ROL_DE_CONFIRMACION = "DIRECTOR_PROYECTOS"
_ESPERA_BLOQUEO_MS = 5000
_ESPERA_EJECUCION_MS = 15000

_MENSAJE_NO_EXISTE = "El archivo no existe."
_MENSAJE_NO_SOLICITANTE = "Solo quien subió el archivo puede confirmarlo."
_MENSAJE_CADUCADO = "La subida del archivo caducó. Vuelve a cargar el archivo."
_MENSAJE_ANULADO = "El archivo está anulado y no se confirma."
_MENSAJE_NO_SUBIDO = "El archivo no llegó al almacén. Vuelve a cargarlo antes de confirmar."
_MENSAJE_TAMANO = (
    "El archivo almacenado no tiene el tamaño que se declaró al iniciar la subida. "
    "Vuelve a cargar el archivo."
)
_MENSAJE_HASH = (
    "El archivo almacenado no coincide con el que se declaró al iniciar la subida. "
    "Vuelve a cargar el archivo."
)
_MENSAJE_TIPO = "El tipo del archivo, leído de su contenido, no está permitido."
_MENSAJE_BLOQUEO = (
    "Otra operación está confirmando este archivo en este momento. Vuelve a intentarlo."
)
_MENSAJE_TIEMPO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."


@dataclass(frozen=True, slots=True)
class ArchivoLeido:
    """Un archivo tal como lo ve la API: los campos de la fila que expone, sin la clave del objeto."""

    id: uuid.UUID
    obra_id: uuid.UUID
    referencia_tipo: str
    referencia_id: uuid.UUID | None
    estado: EstadoArchivo
    nombre_original: str
    tipo_mime: str | None
    tamano_bytes: int
    hash_sha256: str
    subido_por_id: uuid.UUID
    subido_por_nombre: str
    creado_en: datetime
    confirmado_en: datetime | None


@dataclass(frozen=True, slots=True)
class _Resultado:
    """Lo que la transacción principal decide; lo que se lanza o se devuelve va fuera del `with`."""

    leido: ArchivoLeido | None = None
    rechazo_tras_confirmar: ErrorContrato | None = None
    denegado: bool = False


def _declaracion(fila: repositorio.FilaArchivo) -> tuple[int, str]:
    """Tamaño y suma declarados al dar de alta: el alta siempre los fija."""
    if fila.tamano_bytes is None or fila.hash_sha256 is None:
        raise RuntimeError("el archivo no tiene tamaño ni suma declarados")
    return fila.tamano_bytes, fila.hash_sha256


def _leido(sesion_bd: Session, fila: repositorio.FilaArchivo) -> ArchivoLeido:
    tamano, suma = _declaracion(fila)
    nombres = nombres_de_usuarios(sesion_bd, [fila.subido_por_id])
    return ArchivoLeido(
        id=fila.id,
        obra_id=fila.obra_id,
        referencia_tipo=fila.referencia_tipo,
        referencia_id=fila.referencia_id,
        estado=fila.estado,
        nombre_original=fila.nombre_original,
        tipo_mime=fila.tipo_mime,
        tamano_bytes=tamano,
        hash_sha256=suma,
        subido_por_id=fila.subido_por_id,
        subido_por_nombre=nombres[fila.subido_por_id],
        creado_en=fila.creado_en,
        confirmado_en=fila.confirmado_en,
    )


def _caducado(archivo_id: uuid.UUID) -> ConflictoEstado:
    return ConflictoEstado(
        codigo="ARCHIVO_CADUCADO",
        mensaje=_MENSAJE_CADUCADO,
        detalle={"archivo_id": str(archivo_id), "estado_archivo": "CADUCADO"},
    )


def _tipo_de_los_bytes(contexto: ContextoArchivos, fila: repositorio.FilaArchivo) -> str:
    """Pasos 7 a 10: cotejo del objeto almacenado y tipo leído de los bytes. Lanza el rechazo que toque."""
    tamano, suma = _declaracion(fila)
    almacen = contexto.almacen()
    objeto: ObjetoAlmacenado | None = almacen.metadatos(fila.clave_objeto)
    discrepancia = comparar_objeto(tamano_declarado=tamano, hash_declarado=suma, objeto=objeto)
    if discrepancia is Discrepancia.NO_SUBIDO:
        raise ConflictoEstado(
            codigo="ARCHIVO_NO_SUBIDO",
            mensaje=_MENSAJE_NO_SUBIDO,
            detalle={"archivo_id": str(fila.id)},
        )
    if objeto is not None and discrepancia is Discrepancia.TAMANO_DISTINTO:
        raise ConflictoEstado(
            codigo="ARCHIVO_TAMANO_DISTINTO",
            mensaje=_MENSAJE_TAMANO,
            detalle={"tamano_declarado": tamano, "tamano_almacenado": objeto.tamano_bytes},
        )
    if objeto is not None and discrepancia is Discrepancia.HASH_DISTINTO:
        detalle: dict[str, object] = {"hash_declarado": suma}
        if objeto.sha256_hex is not None:
            detalle["hash_almacenado"] = objeto.sha256_hex
        detalle["tamano_declarado"] = tamano
        detalle["tamano_almacenado"] = objeto.tamano_bytes
        raise ConflictoEstado(
            codigo="ARCHIVO_HASH_DISTINTO", mensaje=_MENSAJE_HASH, detalle=detalle
        )

    clave = fila.clave_objeto
    tipo = detectar_tipo(lambda inicio, fin: almacen.leer_rango(clave, inicio, fin), tamano)
    if not tipo_admitido(tipo):
        raise ConflictoEstado(
            codigo="ARCHIVO_TIPO_NO_PERMITIDO",
            mensaje=_MENSAJE_TIPO,
            detalle={"tipo_detectado": tipo, "tipos_admitidos": list(tipos_admitidos())},
        )
    return tipo


def _confirmar_en_transaccion(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    *,
    archivo_id: uuid.UUID,
    usuario_id: uuid.UUID,
    ahora: datetime,
) -> _Resultado:
    """Los pasos 1 a 11. Los rechazos sin escritura se lanzan; el del paso 6 se devuelve para que confirme."""
    fila = repositorio.bloquear(sesion_bd, archivo_id)
    if fila is None:
        raise NoEncontrado(recurso="archivo", mensaje=_MENSAJE_NO_EXISTE)

    paso = evaluar_previa(
        estado=fila.estado,
        subido_por_id=fila.subido_por_id,
        usuario_id=usuario_id,
        ahora=ahora,
        vence_en=fila.creado_en + contexto.configuracion.umbral_pendiente,
    )
    if paso is PasoPrevio.NO_ES_SOLICITANTE:
        return _Resultado(denegado=True)
    if paso is PasoPrevio.YA_DISPONIBLE:
        return _Resultado(leido=_leido(sesion_bd, fila))
    if paso is PasoPrevio.CADUCADO:
        raise _caducado(archivo_id)
    if paso is PasoPrevio.NO_CONFIRMABLE:
        raise ConflictoEstado(
            codigo="ESTADO_NO_PERMITE_OPERACION",
            mensaje=_MENSAJE_ANULADO,
            detalle={"archivo_id": str(archivo_id), "estado_archivo": fila.estado.value},
        )
    if paso is PasoPrevio.VENCIDO:
        repositorio.marcar_caducado(sesion_bd, archivo_id)
        return _Resultado(rechazo_tras_confirmar=_caducado(archivo_id))

    tipo = _tipo_de_los_bytes(contexto, fila)
    tamano, suma = _declaracion(fila)
    contexto.almacen().reescribir_tipo(fila.clave_objeto, tipo)
    repositorio.marcar_disponible(sesion_bd, archivo_id, tipo_mime=tipo, confirmado_en=ahora)
    datos_despues: dict[str, object] = {
        "hash_sha256": suma,
        "tamano_bytes": tamano,
        "tipo_mime": tipo,
        "referencia_tipo": fila.referencia_tipo,
    }
    if fila.referencia_id is not None:
        datos_despues["referencia_id"] = str(fila.referencia_id)
    auditoria.asentar(
        sesion_bd,
        accion="CONFIRMAR",
        entidad_tipo="archivo",
        entidad_id=archivo_id,
        usuario_id=usuario_id,
        ocurrido_en=ahora,
        obra_id=fila.obra_id,
        datos_despues=datos_despues,
    )
    confirmada = replace(fila, estado=EstadoArchivo.DISPONIBLE, tipo_mime=tipo, confirmado_en=ahora)
    return _Resultado(leido=_leido(sesion_bd, confirmada))


def _ruta_de_confirmacion(archivo_id: uuid.UUID) -> str:
    return f"/api/v1/archivos/{archivo_id}/confirmacion"


def _traducir_concurrencia(error: DBAPIError, archivo_id: uuid.UUID) -> ConcurrenciaVencida | None:
    """RNF-16: `55P03` (`lock_timeout`) y `57014` (`statement_timeout`) son `CONCURRENCIA`; el resto no."""
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
        return None
    return ConcurrenciaVencida(
        codigo=codigo,
        mensaje=mensaje,
        espera_maxima_ms=espera,
        reintentar_en_s=1,
        acciones=[
            Accion("REINTENTAR", "POST", _ruta_de_confirmacion(archivo_id), (ROL_DE_CONFIRMACION,))
        ],
    )


def _asentar_denegacion(
    contexto: ContextoArchivos, *, archivo_id: uuid.UUID, usuario_id: uuid.UUID, ahora: datetime
) -> None:
    """Un `403` autenticado se asienta `DENEGAR` en una transacción propia; si falla, el `403` sigue."""
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            auditoria.asentar_denegacion(
                sesion_bd,
                usuario_id=usuario_id,
                ocurrido_en=ahora,
                motivo="NO_ES_SOLICITANTE",
                datos={
                    "metodo": "POST",
                    "ruta": _ruta_de_confirmacion(archivo_id),
                    "roles_requeridos": [ROL_DE_CONFIRMACION],
                },
            )
    except Exception as error:  # noqa: BLE001 - la denegación no se pierde por un fallo de la bitácora
        _registro.error(
            "denegacion_no_asentada",
            usuario_id=str(usuario_id),
            tipo_error=type(error).__name__,
        )


def confirmar_archivo(
    contexto: ContextoArchivos, *, archivo_id: uuid.UUID, usuario_id: uuid.UUID
) -> ArchivoLeido:
    """Implementa RNF-06, RNF-19, RNF-16, PA-T59.8 y PA-T59.13.

    Solo quien subió el archivo lo confirma. Una transacción principal con `FOR UPDATE`; el reloj se
    lee una vez. Un `PENDIENTE` vencido pasa a `CADUCADO` y esa escritura se confirma antes de lanzar
    el `409`.
    """
    ahora = contexto.reloj()
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            resultado = _confirmar_en_transaccion(
                contexto, sesion_bd, archivo_id=archivo_id, usuario_id=usuario_id, ahora=ahora
            )
    except DBAPIError as error:
        traducido = _traducir_concurrencia(error, archivo_id)
        if traducido is None:
            raise
        raise traducido from error

    if resultado.denegado:
        _asentar_denegacion(contexto, archivo_id=archivo_id, usuario_id=usuario_id, ahora=ahora)
        raise PermisoDenegado(
            motivo="NO_ES_SOLICITANTE", mensaje=_MENSAJE_NO_SOLICITANTE, roles_requeridos=()
        )
    if resultado.rechazo_tras_confirmar is not None:
        raise resultado.rechazo_tras_confirmar
    if resultado.leido is None:
        raise RuntimeError("la confirmación no produjo resultado")
    return resultado.leido
