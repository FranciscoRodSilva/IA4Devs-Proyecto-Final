"""La acción de un rechazo (TKT-005, M5, CA-9).

Una `Accion` es una salida documentada de un error: dice a qué ruta ir para salir del bloqueo.
Lleva además los roles que pueden ejecutarla, que sirven para filtrarla y nunca se serializan:
no se ofrece una acción que le respondería `403` a quien llama, salvo `REINTENTAR` de una
concurrencia: repite una operación que `api/` ya autorizó (ADR-022).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from contrato_error.catalogos import Metodo, Rol

_CLAVE = re.compile(r"[A-Z][A-Z0-9_]*")
_RUTA = re.compile(r"/api/v1/[^\s]*")


@dataclass(frozen=True, slots=True, init=False)
class Accion:
    """Salida documentada de un rechazo (esquema `Accion` del borrador).

    `roles_permitidos` decide quién la ve y no se serializa. La ruta exige el prefijo
    `/api/v1/` `(asumido)`: el borrador solo pide que empiece por `/`, pero su descripción y la
    especificación de la API §3.2 la quieren absoluta y con el prefijo.
    """

    clave: str
    metodo: Metodo
    ruta: str
    roles_permitidos: frozenset[Rol]

    def __init__(self, clave: str, metodo: str, ruta: str, roles_permitidos: Iterable[str]) -> None:
        if not isinstance(clave, str) or _CLAVE.fullmatch(clave) is None:
            raise ValueError(
                f"Clave de acción no válida: {clave!r}; se espera MAYUSCULAS_CON_GUION_BAJO"
            )
        if not isinstance(ruta, str) or _RUTA.fullmatch(ruta) is None:
            raise ValueError(
                f"Ruta de acción no válida: {ruta!r}; se espera absoluta, con /api/v1/ y sin espacios"
            )
        roles = frozenset(Rol(rol) for rol in roles_permitidos)
        if not roles:
            raise ValueError(f"La acción {clave} necesita al menos un rol que pueda ejecutarla")
        object.__setattr__(self, "clave", clave)
        object.__setattr__(self, "metodo", Metodo(metodo))
        object.__setattr__(self, "ruta", ruta)
        object.__setattr__(self, "roles_permitidos", roles)

    def permitida_para(self, roles_de_quien_llama: frozenset[str]) -> bool:
        """M5: se ofrece si quien llama tiene al menos uno de los roles; sin roles conocidos, nunca."""
        return not self.roles_permitidos.isdisjoint(roles_de_quien_llama)

    def como_dict(self) -> dict[str, str]:
        """Cuerpo de la acción en el JSON del error: `clave`, `metodo` y `ruta`, sin los roles."""
        return {"clave": self.clave, "metodo": self.metodo.value, "ruta": self.ruta}
