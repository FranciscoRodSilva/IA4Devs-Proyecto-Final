"""Familia de excepciones del contrato de error (TKT-005, CA-1 a CA-9 y CA-13).

Una clase por `tipo` del borrador OpenAPI y una sola para todas las reglas de negocio. Cada
excepción valida lo que recibe al construirse, de modo que un cuerpo fuera de contrato no se puede
crear, y sabe producir su cuerpo dados los roles de quien llama y el identificador de correlación.
Python puro: solo biblioteca estándar y `tipos_base`. Los importes del detalle salen por
`serializar()`, que rechaza lo no cuantizado y nunca redondea (regla 1 de CLAUDE.md).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar, cast

from contrato_error.acciones import Accion
from contrato_error.catalogos import (
    CodigoConcurrencia,
    CodigoConflicto,
    CodigoValidacion,
    MotivoPermiso,
    MotivoSesion,
    Rol,
)
from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

_REGLA = re.compile(r"RN-[0-9]{2}")
_NUMERICOS = (Dinero, Cantidad, Rendimiento, Porcentaje)


def validar_regla(valor: object) -> str:
    """Valida un identificador de regla (CA-2): solo `RN-NN`, con dígitos ASCII y sin nada alrededor."""
    if not isinstance(valor, str):
        raise TypeError(f"El identificador de regla es una cadena, no {type(valor).__name__}")
    if _REGLA.fullmatch(valor) is None:
        raise ValueError(
            f"Identificador de regla no válido: {valor!r}; se espera RN-NN, como 'RN-03'"
        )
    return valor


def _texto(valor: object, nombre: str) -> str:
    if not isinstance(valor, str):
        raise TypeError(f"{nombre} es una cadena, no {type(valor).__name__}")
    if not valor.strip():
        raise ValueError(f"{nombre} no puede estar vacío")
    return valor


def _entero_no_negativo(valor: object, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"{nombre} es un entero, no {type(valor).__name__}")
    if valor < 0:
        raise ValueError(f"{nombre} no puede ser negativo: {valor}")
    return valor


def _a_json(valor: object, ruta: str) -> object:
    if isinstance(valor, bool | str | int):
        return valor
    if isinstance(valor, _NUMERICOS):
        return valor.serializar()  # rechaza lo no cuantizado: nunca redondea aquí
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, Mapping):
        resultado: dict[str, object] = {}
        for clave, interior in valor.items():
            if not isinstance(clave, str):
                raise TypeError(f"La clave {clave!r} de {ruta} no es una cadena")
            resultado[clave] = _a_json(interior, f"{ruta}.{clave}")
        return resultado
    if isinstance(valor, list | tuple):
        return [_a_json(interior, f"{ruta}[{i}]") for i, interior in enumerate(valor)]
    raise TypeError(
        f"{ruta} no admite {type(valor).__name__}: los importes viajan como Dinero, Cantidad, "
        "Rendimiento o Porcentaje cuantizados, nunca como float ni Decimal suelto (regla 1)"
    )


def normalizar_detalle(detalle: object) -> dict[str, object]:
    """Convierte el detalle a JSON llano (CA-3): importes como cadena, sin float ni Decimal suelto."""
    if not isinstance(detalle, Mapping):
        raise TypeError(f"El detalle es un diccionario, no {type(detalle).__name__}")
    return cast("dict[str, object]", _a_json(detalle, "detalle"))


def mensaje_de_validacion(errores: int) -> str:
    """Mensaje del `422` según el número de campos inválidos (CA-6)."""
    if errores == 1:
        return "La petición tiene 1 campo inválido."
    return f"La petición tiene {errores} campos inválidos."


class ErrorContrato(Exception):
    """Base de los ocho cuerpos de error del borrador. El manejador global la serializa (CA-13)."""

    tipo: ClassVar[str]
    estado_http: ClassVar[int]

    def __init__(self, mensaje: str) -> None:
        self.mensaje = _texto(mensaje, "mensaje")
        super().__init__(self.mensaje)

    def cuerpo(
        self, roles_de_quien_llama: frozenset[str], correlacion_id: str
    ) -> dict[str, object]:
        """Cuerpo JSON del error, con las acciones filtradas por los roles de quien llama."""
        return {
            "tipo": self.tipo,
            "mensaje": self.mensaje,
            **self._campos(roles_de_quien_llama),
            "correlacion_id": correlacion_id,
        }

    def cabeceras(self) -> dict[str, str]:
        """Cabeceras HTTP propias del error; por omisión, ninguna."""
        return {}

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        raise NotImplementedError


def _acciones(acciones: Sequence[Accion]) -> tuple[Accion, ...]:
    for accion in acciones:
        if not isinstance(accion, Accion):
            raise TypeError(f"Se espera Accion, no {type(accion).__name__}")
    return tuple(acciones)


def _filtrar(acciones: tuple[Accion, ...], roles: frozenset[str]) -> list[dict[str, str]]:
    return [a.como_dict() for a in acciones if a.permitida_para(roles)]


class RechazoRegla(ErrorContrato):
    """Rechazo por una regla `RN-xx` del PRD: `409` con `tipo` `REGLA_NEGOCIO` (CA-1, CA-2, CA-3).

    Una sola para todas las reglas: la regla viaja en el campo `regla`, nunca en el tipo de la
    excepción. La lanza el caso de uso a partir del resultado de la función de regla; `dominio/` no
    la importa (TKT-005, ADR del contrato de error).
    """

    tipo: ClassVar[str] = "REGLA_NEGOCIO"
    estado_http: ClassVar[int] = 409

    def __init__(
        self,
        *,
        regla: str,
        mensaje: str,
        detalle: Mapping[str, object],
        acciones: Sequence[Accion] = (),
    ) -> None:
        super().__init__(mensaje)
        self.regla = validar_regla(regla)
        self.detalle = normalizar_detalle(detalle)
        self.acciones = _acciones(acciones)

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {
            "regla": self.regla,
            "detalle": self.detalle,
            "acciones": _filtrar(self.acciones, roles_de_quien_llama),
        }


class ConflictoEstado(ErrorContrato):
    """Conflicto de estado o de unicidad que no es una `RN`: `409` `CONFLICTO` (CA-4).

    Lleva un `codigo` del catálogo cerrado y nunca una `regla`.
    """

    tipo: ClassVar[str] = "CONFLICTO"
    estado_http: ClassVar[int] = 409

    def __init__(
        self,
        *,
        codigo: str,
        mensaje: str,
        detalle: Mapping[str, object],
        acciones: Sequence[Accion] = (),
    ) -> None:
        super().__init__(mensaje)
        self.codigo = CodigoConflicto(codigo)
        self.detalle = normalizar_detalle(detalle)
        self.acciones = _acciones(acciones)

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {
            "codigo": self.codigo.value,
            "detalle": self.detalle,
            "acciones": _filtrar(self.acciones, roles_de_quien_llama),
        }


class ConcurrenciaVencida(ErrorContrato):
    """Venció `lock_timeout` o `statement_timeout` (RNF-16): `409` `CONCURRENCIA` con `Retry-After` (CA-5).

    `REINTENTAR` no se filtra por rol: repite la operación que quien llama acaba de invocar, así
    que por construcción tiene permiso para ella, y un vencimiento sin salida documentada dejaría
    al cliente sin camino. El resto de las acciones de la concurrencia sí se filtran por los roles
    de quien llama, como en cualquier otra clase. La exigencia de que exista `REINTENTAR` se valida
    sobre las acciones sin filtrar, y el cuerpo resultante siempre la trae.
    """

    tipo: ClassVar[str] = "CONCURRENCIA"
    estado_http: ClassVar[int] = 409

    def __init__(
        self,
        *,
        codigo: str,
        mensaje: str,
        espera_maxima_ms: int,
        reintentar_en_s: int,
        acciones: Sequence[Accion],
    ) -> None:
        super().__init__(mensaje)
        self.codigo = CodigoConcurrencia(codigo)
        self.espera_maxima_ms = _entero_no_negativo(espera_maxima_ms, "espera_maxima_ms")
        self.reintentar_en_s = _entero_no_negativo(reintentar_en_s, "reintentar_en_s")
        self.acciones = _acciones(acciones)
        if not any(a.clave == "REINTENTAR" for a in self.acciones):
            raise ValueError("La concurrencia necesita la acción REINTENTAR")

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {
            "codigo": self.codigo.value,
            "detalle": {"espera_maxima_ms": self.espera_maxima_ms},
            "acciones": [
                a.como_dict()
                for a in self.acciones
                if a.clave == "REINTENTAR" or a.permitida_para(roles_de_quien_llama)
            ],
        }

    def cabeceras(self) -> dict[str, str]:
        """`Retry-After` en segundos."""
        return {"Retry-After": str(self.reintentar_en_s)}


@dataclass(frozen=True, slots=True, init=False)
class ErrorDeCampo:
    """Un campo inválido de un `422` (CA-6). No es una excepción: la agrupa `ValidacionRechazada`."""

    campo: str
    codigo: CodigoValidacion
    mensaje: str
    regla: str | None

    def __init__(self, *, campo: str, codigo: str, mensaje: str, regla: str | None = None) -> None:
        object.__setattr__(self, "campo", _texto(campo, "campo"))
        object.__setattr__(self, "codigo", CodigoValidacion(codigo))
        object.__setattr__(self, "mensaje", _texto(mensaje, "mensaje"))
        object.__setattr__(self, "regla", None if regla is None else validar_regla(regla))

    def como_dict(self) -> dict[str, str]:
        """El elemento de `errores`; `regla` solo si la forma la impone una regla."""
        resultado = {"campo": self.campo, "codigo": self.codigo.value, "mensaje": self.mensaje}
        if self.regla is not None:
            resultado["regla"] = self.regla
        return resultado


class ValidacionRechazada(ErrorContrato):
    """Error de forma: `422` `VALIDACION` con un elemento por campo inválido (CA-6)."""

    tipo: ClassVar[str] = "VALIDACION"
    estado_http: ClassVar[int] = 422

    def __init__(self, *, errores: Sequence[ErrorDeCampo]) -> None:
        if not errores:
            raise ValueError("La validación necesita al menos un error de campo")
        for error in errores:
            if not isinstance(error, ErrorDeCampo):
                raise TypeError(f"Se espera ErrorDeCampo, no {type(error).__name__}")
        super().__init__(mensaje_de_validacion(len(errores)))
        self.errores = tuple(errores)

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {"errores": [e.como_dict() for e in self.errores]}


class PermisoDenegado(ErrorContrato):
    """Falta el rol, la autoridad o la prueba de origen: `403` `PERMISO` (CA-7).

    Nunca lleva cifras del recurso: no admite `detalle`.
    """

    tipo: ClassVar[str] = "PERMISO"
    estado_http: ClassVar[int] = 403

    def __init__(self, *, motivo: str, mensaje: str, roles_requeridos: Iterable[str]) -> None:
        super().__init__(mensaje)
        self.motivo = MotivoPermiso(motivo)
        self.roles_requeridos = tuple(Rol(r) for r in roles_requeridos)

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {
            "motivo": self.motivo.value,
            "roles_requeridos": [r.value for r in self.roles_requeridos],
        }


class SesionInvalida(ErrorContrato):
    """Sin sesión, caducada, revocada o con credenciales inválidas: `401` `SESION` (CA-8)."""

    tipo: ClassVar[str] = "SESION"
    estado_http: ClassVar[int] = 401

    def __init__(self, *, motivo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.motivo = MotivoSesion(motivo)

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {"motivo": self.motivo.value}


class LimiteIntentosExcedido(ErrorContrato):
    """Demasiados intentos: `429` `LIMITE_INTENTOS` con `Retry-After` (CA-8)."""

    tipo: ClassVar[str] = "LIMITE_INTENTOS"
    estado_http: ClassVar[int] = 429

    def __init__(self, *, mensaje: str, reintentar_en_s: int) -> None:
        super().__init__(mensaje)
        self.reintentar_en_s = _entero_no_negativo(reintentar_en_s, "reintentar_en_s")

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {"reintentar_en_s": self.reintentar_en_s}

    def cabeceras(self) -> dict[str, str]:
        """`Retry-After` en segundos."""
        return {"Retry-After": str(self.reintentar_en_s)}


class NoEncontrado(ErrorContrato):
    """El recurso no existe: `404` `NO_ENCONTRADO` (CA-8)."""

    tipo: ClassVar[str] = "NO_ENCONTRADO"
    estado_http: ClassVar[int] = 404

    def __init__(self, *, recurso: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.recurso = _texto(recurso, "recurso")

    def _campos(self, roles_de_quien_llama: frozenset[str]) -> dict[str, object]:
        return {"recurso": self.recurso}
