"""Identificador de correlación por petición y registro de acceso (CA-10, CA-11, RNF-13)."""

import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CABECERA_CORRELACION = "X-Correlacion-Id"
_CABECERA_EN_BYTES = CABECERA_CORRELACION.lower().encode("ascii")


class MiddlewareCorrelacion:
    """ASGI puro (PA-T9). Genera siempre el identificador y descarta el que envíe el cliente (PA-T7).

    Registra método, ruta sin consulta, estado y duración. Nunca cuerpos, cabeceras, cookies ni
    la cadena de consulta. El 500 no pasa por aquí al responder: su manejador pone la cabecera.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlacion_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlacion_id"] = correlacion_id
        estado = 500

        async def enviar(mensaje: Message) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                cabeceras = [
                    (k, v) for k, v in mensaje.get("headers", []) if k.lower() != _CABECERA_EN_BYTES
                ]
                cabeceras.append((_CABECERA_EN_BYTES, correlacion_id.encode("ascii")))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        registro = structlog.get_logger("cimenta.peticion")
        campos = {"metodo": scope["method"], "ruta": scope["path"]}
        inicio = time.perf_counter()
        with structlog.contextvars.bound_contextvars(correlacion_id=correlacion_id):
            try:
                await self.app(scope, receive, enviar)
            except Exception:
                registro.error(
                    "peticion_fallida",
                    **campos,
                    estado=500,
                    duracion_ms=round((time.perf_counter() - inicio) * 1000),
                    exc_info=True,
                )
                raise
            registro.info(
                "peticion_atendida",
                **campos,
                estado=estado,
                duracion_ms=round((time.perf_counter() - inicio) * 1000),
            )
