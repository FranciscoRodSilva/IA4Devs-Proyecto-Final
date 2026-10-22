"""Asiento de las denegaciones por rol (TKT-006, entrega B · M9 · PA-T6)."""

from __future__ import annotations

import structlog

from cimenta.auditoria import interfaz as auditoria  # el módulo, no el nombre: TC-64 lo sustituye
from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado

_registro = structlog.get_logger("cimenta.identidad")


def registrar_denegacion(
    contexto: ContextoIdentidad,
    *,
    usuario: UsuarioAutenticado,
    motivo: str,
    metodo: str,
    ruta: str,
    roles_requeridos: tuple[str, ...],
    correlacion_id: str,
) -> None:
    """M9 · RN-04 · modelo de datos §10: un 403 autenticado se asienta como DENEGAR en una
    transacción propia, separada de la de la petición. PA-T6: si la bitácora falla, el fallo se
    registra en el registro técnico —con el tipo de la excepción y sin su mensaje— y la
    denegación sigue: la respuesta es el 403 de siempre. La correlación no entra en la bitácora."""
    try:
        with contexto.fabrica_sesiones().begin() as sesion_bd:
            auditoria.asentar_denegacion(
                sesion_bd,
                usuario_id=usuario.usuario_id,
                ocurrido_en=contexto.reloj(),
                motivo=motivo,
                datos={
                    "metodo": metodo,
                    "ruta": ruta,
                    "roles_requeridos": list(roles_requeridos),
                },
            )
    except Exception:
        _registro.error(
            "denegacion_no_asentada",
            correlacion_id=correlacion_id,
            usuario_id=str(usuario.usuario_id),
            exc_info=True,
        )
