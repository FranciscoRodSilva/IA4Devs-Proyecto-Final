from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

_REGLA = re.compile(r"RN-[0-9]{2}")

MENSAJE_OBLIGATORIO = "El campo es obligatorio."
MENSAJE_TEXTO = "El valor es un texto."
MENSAJE_UUID = "El valor no es un identificador UUID."
MENSAJE_ACCION = "La acción no es uno de los 22 verbos de la bitácora."
MENSAJE_REGLA = "La regla de negocio tiene la forma RN-NN, como RN-03."
MENSAJE_DATOS_NO_OBJETO = "Los datos son un objeto JSON."
MENSAJE_CLAVE_NO_CADENA = "Las claves de los datos son cadenas."
MENSAJE_VALOR_NO_JSON = (
    "El valor no es JSON admitido: los importes viajan como cadena, nunca como float ni Decimal "
    "(regla 1)."
)
MENSAJE_NUL = "El texto contiene el carácter U+0000, que PostgreSQL no admite en text ni en jsonb."


class AccionBitacora(StrEnum):
    """Los 22 verbos de bitacora.accion: modelo de datos §10 y AccionBitacora del borrador, en ese orden."""

    CREAR = "CREAR"
    ACTUALIZAR = "ACTUALIZAR"
    EVALUAR = "EVALUAR"
    BLOQUEAR = "BLOQUEAR"
    AUTORIZAR = "AUTORIZAR"
    RECHAZAR = "RECHAZAR"
    CANCELAR = "CANCELAR"
    EMITIR = "EMITIR"
    AJUSTAR = "AJUSTAR"
    REPROGRAMAR = "REPROGRAMAR"
    CONGELAR = "CONGELAR"
    RECAPTURAR = "RECAPTURAR"
    DESCARTAR = "DESCARTAR"
    CONFIRMAR = "CONFIRMAR"
    ANULAR = "ANULAR"
    SUSPENDER = "SUSPENDER"
    REACTIVAR = "REACTIVAR"
    CERRAR = "CERRAR"
    DESACTIVAR = "DESACTIVAR"
    LIBERAR = "LIBERAR"
    VALIDAR = "VALIDAR"
    DENEGAR = "DENEGAR"


@dataclass(frozen=True, slots=True)
class DefectoDeCampo:
    """Un campo mal formado. codigo es un valor de CodigoValidacion del borrador; el caso de uso
    lo convierte en ErrorDeCampo de contrato_error, que el dominio no puede importar."""

    campo: str
    codigo: str
    mensaje: str


@dataclass(frozen=True, slots=True)
class Asiento:
    """Objeto de valor de un asiento bien formado. Sin id ni ocurrido_en: los pone el caso de uso."""

    accion: AccionBitacora
    entidad_tipo: str
    entidad_id: uuid.UUID
    usuario_id: uuid.UUID
    regla_negocio: str | None
    obra_id: uuid.UUID | None
    motivo: str | None
    datos_antes: dict[str, object] | None
    datos_despues: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class ResultadoAsiento:
    asiento: Asiento | None
    defectos: tuple[DefectoDeCampo, ...]


def regla_bien_formada(valor: object) -> bool:
    """RN-04 · RN-NN con dígitos ASCII y nada alrededor (fullmatch, no match; [0-9], no \\d)."""
    return isinstance(valor, str) and _REGLA.fullmatch(valor) is not None


def texto_obligatorio(campo: str, valor: object, defectos: list[DefectoDeCampo]) -> str | None:
    if valor is None:
        defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    if not isinstance(valor, str):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_TEXTO))
        return None
    if not valor.strip():
        defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    if "\x00" in valor:
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_NUL))
        return None
    return valor


def _uuid(
    campo: str, valor: object, *, obligatorio: bool, defectos: list[DefectoDeCampo]
) -> uuid.UUID | None:
    if valor is None:
        if obligatorio:
            defectos.append(DefectoDeCampo(campo, "OBLIGATORIO", MENSAJE_OBLIGATORIO))
        return None
    if not isinstance(valor, uuid.UUID):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_UUID))
        return None
    return valor


def _verbo(valor: object, defectos: list[DefectoDeCampo]) -> AccionBitacora | None:
    if isinstance(valor, str) and valor in AccionBitacora.__members__.values():
        return AccionBitacora(valor)
    defectos.append(DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", MENSAJE_ACCION))
    return None


def _a_json(valor: object, ruta: str, defectos: list[DefectoDeCampo]) -> object:
    if isinstance(valor, str) and "\x00" in valor:
        defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_NUL))
        return None
    if valor is None or isinstance(valor, bool | str | int):
        return valor
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, Mapping):
        resultado: dict[str, object] = {}
        for clave, interior in valor.items():
            if not isinstance(clave, str):
                defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_CLAVE_NO_CADENA))
                continue
            if "\x00" in clave:
                defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_NUL))
                continue
            resultado[clave] = _a_json(interior, f"{ruta}.{clave}", defectos)
        return resultado
    if isinstance(valor, list | tuple):
        return [_a_json(interior, f"{ruta}[{i}]", defectos) for i, interior in enumerate(valor)]
    defectos.append(DefectoDeCampo(ruta, "FORMATO", MENSAJE_VALOR_NO_JSON))
    return None


def _datos(campo: str, valor: object, defectos: list[DefectoDeCampo]) -> dict[str, object] | None:
    if valor is None:
        return None
    if not isinstance(valor, Mapping):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_DATOS_NO_OBJETO))
        return None
    return cast("dict[str, object]", _a_json(valor, campo, defectos))


def revisar_asiento(
    *,
    accion: object,
    entidad_tipo: object,
    entidad_id: object,
    usuario_id: object,
    regla_negocio: object,
    obra_id: object,
    motivo: object,
    datos_antes: object,
    datos_despues: object,
) -> ResultadoAsiento:
    """RN-04 · M4 · regla 1. Devuelve el asiento normalizado o todos sus defectos, en el orden de
    los campos; nunca lanza. Los UUID dentro de datos_* salen como cadena; float, Decimal y
    cualquier otro tipo, defecto con la ruta del valor (datos_despues.renglones[0].precio)."""
    defectos: list[DefectoDeCampo] = []
    verbo = _verbo(accion, defectos)
    tipo = texto_obligatorio("entidad_tipo", entidad_tipo, defectos)
    entidad = _uuid("entidad_id", entidad_id, obligatorio=True, defectos=defectos)
    usuario = _uuid("usuario_id", usuario_id, obligatorio=True, defectos=defectos)
    if regla_negocio is not None and not regla_bien_formada(regla_negocio):
        defectos.append(DefectoDeCampo("regla_negocio", "FORMATO", MENSAJE_REGLA))
    obra = _uuid("obra_id", obra_id, obligatorio=False, defectos=defectos)
    texto_motivo = None if motivo is None else texto_obligatorio("motivo", motivo, defectos)
    antes = _datos("datos_antes", datos_antes, defectos)
    despues = _datos("datos_despues", datos_despues, defectos)
    if defectos or verbo is None or tipo is None or entidad is None or usuario is None:
        return ResultadoAsiento(asiento=None, defectos=tuple(defectos))
    return ResultadoAsiento(
        asiento=Asiento(
            accion=verbo,
            entidad_tipo=tipo,
            entidad_id=entidad,
            usuario_id=usuario,
            regla_negocio=cast("str | None", regla_negocio),
            obra_id=obra,
            motivo=texto_motivo,
            datos_antes=antes,
            datos_despues=despues,
        ),
        defectos=(),
    )
