from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Protocol, Self

from cimenta.auditoria.dominio.asiento import (
    MENSAJE_ACCION,
    MENSAJE_REGLA,
    AccionBitacora,
    DefectoDeCampo,
    regla_bien_formada,
    texto_obligatorio,
)

PAGINA_POR_OMISION: Final = 1
TAMANO_PAGINA_POR_OMISION: Final = 50
TAMANO_PAGINA_MAXIMO: Final = 200

MENSAJE_ENTERO = "El valor es un número entero."
MENSAJE_PAGINA = "La página es un entero desde 1."
MENSAJE_TAMANO = "El tamaño de página es un entero entre 1 y 200."
MENSAJE_RANGO = "hasta no puede ser anterior a desde."


class Ordenable(Protocol):
    def __lt__(self, otro: Self, /) -> bool: ...


def _entero(
    campo: str,
    valor: object,
    minimo: int,
    maximo: int | None,
    mensaje: str,
    defectos: list[DefectoDeCampo],
) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        defectos.append(DefectoDeCampo(campo, "FORMATO", MENSAJE_ENTERO))
    elif valor < minimo or (maximo is not None and valor > maximo):
        defectos.append(DefectoDeCampo(campo, "FUERA_DE_RANGO", mensaje))


def revisar_filtros[T: Ordenable](
    *,
    pagina: object,
    tamano_pagina: object,
    regla_negocio: object,
    entidad_tipo: object,
    acciones: Sequence[object],
    desde: T | None,
    hasta: T | None,
) -> tuple[DefectoDeCampo, ...]:
    """M6 · borrador consultar_bitacora. desde inclusivo y hasta exclusivo; desde == hasta es un
    rango vacío y se admite; hasta < desde es defecto (asumido). Nunca lanza."""
    defectos: list[DefectoDeCampo] = []
    _entero("pagina", pagina, 1, None, MENSAJE_PAGINA, defectos)
    _entero("tamano_pagina", tamano_pagina, 1, TAMANO_PAGINA_MAXIMO, MENSAJE_TAMANO, defectos)
    if regla_negocio is not None and not regla_bien_formada(regla_negocio):
        defectos.append(DefectoDeCampo("regla_negocio", "FORMATO", MENSAJE_REGLA))
    if entidad_tipo is not None:
        texto_obligatorio("entidad_tipo", entidad_tipo, defectos)
    if any(not (isinstance(a, str) and a in AccionBitacora.__members__.values()) for a in acciones):
        defectos.append(DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", MENSAJE_ACCION))
    if desde is not None and hasta is not None and hasta < desde:
        defectos.append(DefectoDeCampo("hasta", "FUERA_DE_RANGO", MENSAJE_RANGO))
    return tuple(defectos)
