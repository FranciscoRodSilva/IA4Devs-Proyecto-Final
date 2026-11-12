"""Alta de un archivo: la fila `PENDIENTE` y la URL de subida prefirmada (TKT-059, fila 9).

Implementa CA-3 y RNF-06. `registrar_archivo` es la interfaz que TKT-018 inyecta en su ruta: valida
la declaración, inserta la fila en la sesión **de quien llama** y firma la URL de subida. No abre ni
confirma transacción: si quien llama deshace, la fila no queda (RNF-19). Las reglas de la
declaración viven en `dominio/declaracion.py`; aquí solo se orquesta.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from cimenta.archivos.aplicacion.contexto import ContextoArchivos
from cimenta.archivos.dominio.confirmacion import EstadoArchivo
from cimenta.archivos.dominio.declaracion import evaluar_declaracion
from cimenta.archivos.infraestructura import repositorio
from contrato_error.excepciones import ErrorDeCampo, ValidacionRechazada

# Los seis valores de `ck_archivo_referencia_tipo` (migración v0012), exactos: sin normalizar.
TIPOS_DE_REFERENCIA: frozenset[str] = frozenset(
    {"AVANCE", "ENTRADA_ALMACEN", "MERMA", "FACTURA_PROVEEDOR", "IMPORTACION", "OBRA"}
)


@dataclass(frozen=True, slots=True)
class AltaArchivo:
    """Lo que quien llama necesita para que el navegador suba el archivo.

    `url` es una credencial de portador: no se muestra en `repr` (RNF-06, ADR-016).
    """

    archivo_id: uuid.UUID
    url: str = field(repr=False)
    metodo: Literal["PUT"]
    cabeceras: dict[str, str]
    expira_en: datetime


def registrar_archivo(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    *,
    obra_id: uuid.UUID,
    referencia_tipo: str,
    referencia_id: uuid.UUID | None,
    nombre_original: str,
    tamano_bytes: int,
    hash_sha256: str,
    tipo_declarado: str,
    usuario_id: uuid.UUID,
    campo_raiz: str = "archivo",
) -> AltaArchivo:
    """Implementa CA-3 y RNF-06. Valida, inserta `PENDIENTE` y firma; no confirma la transacción.

    Refleja `ck_archivo_referencia_tipo` y `ck_archivo_referencia_obligatoria`: un `referencia_tipo`
    fuera de los seis, o un `referencia_id` ausente salvo para `OBRA`, es un `ValueError` del
    llamador (TKT-018), no un error del cliente. Se evalúa antes que la declaración, sin firmar
    ni insertar.
    """
    if referencia_tipo not in TIPOS_DE_REFERENCIA:
        raise ValueError("referencia_tipo no es uno de los seis tipos de referencia admitidos")
    if referencia_tipo != "OBRA" and referencia_id is None:
        raise ValueError("referencia_id es obligatorio salvo cuando referencia_tipo es OBRA")
    limites = contexto.configuracion.limites
    defectos = evaluar_declaracion(
        nombre_original=nombre_original,
        tamano_bytes=tamano_bytes,
        hash_sha256=hash_sha256,
        tipo_declarado=tipo_declarado,
        limites=limites,
        campo_raiz=campo_raiz,
    )
    if defectos:
        raise ValidacionRechazada(
            errores=[
                ErrorDeCampo(campo=d.campo, codigo=d.codigo, mensaje=d.mensaje) for d in defectos
            ]
        )

    ahora = contexto.reloj()
    archivo_id = uuid.uuid4()
    clave = f"{obra_id}/{archivo_id}"
    repositorio.insertar(
        sesion_bd,
        repositorio.FilaArchivo(
            id=archivo_id,
            obra_id=obra_id,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            estado=EstadoArchivo.PENDIENTE,
            clave_objeto=clave,
            nombre_original=nombre_original,
            tipo_mime=None,
            tamano_bytes=tamano_bytes,
            hash_sha256=hash_sha256,
            subido_por_id=usuario_id,
            creado_en=ahora,
            confirmado_en=None,
            anulado_por_id=None,
            motivo_anulacion=None,
            anulado_en=None,
        ),
    )

    vida = contexto.configuracion.vida_url_subida
    firmada = contexto.almacen().url_subida(
        clave, tamano_bytes=tamano_bytes, sha256_hex=hash_sha256, vida=vida
    )
    return AltaArchivo(
        archivo_id=archivo_id,
        url=firmada.url,
        metodo="PUT",
        cabeceras=firmada.cabeceras,
        expira_en=ahora + vida,
    )
