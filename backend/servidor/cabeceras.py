"""Cabeceras de seguridad de toda respuesta (TKT-057, fila 13; RNF-05 y RNF-06).

Starlette no trae estas cabeceras. `cabeceras_de_seguridad` fija los valores aprobados en el diseño,
`cabeceras_para_ruta` añade `Cache-Control: no-store` solo bajo `/api/` y `MiddlewareCabecerasSeguridad`
las aplica con ASGI puro, igual que `MiddlewareCorrelacion`. El origen del almacén de objetos entra en la
política de contenido solo si `CIMENTA_ALMACEN_ORIGEN` está configurado (CA-14).
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

PREFIJO_API = "/api/"


def cabeceras_de_seguridad(almacen_origen: str | None) -> tuple[tuple[str, str], ...]:
    """RNF-05 · RNF-06 — las cuatro cabeceras que llevan todas las respuestas, de cualquier ruta.

    `almacen_origen` ya llega validado como origen https sin ruta, o http en localhost (`servidor.ajustes`), así que no
    puede inyectar directivas. Sin él, la política no admite ningún origen externo.
    """
    sufijo_origen = f" {almacen_origen}" if almacen_origen else ""
    politica = (
        "default-src 'self'; base-uri 'none'; "
        f"connect-src 'self'{sufijo_origen}; font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
        f"img-src 'self'{sufijo_origen}; media-src 'self'{sufijo_origen}; object-src 'none'; script-src 'self'; "
        "style-src 'self'"
    )
    return (
        ("Strict-Transport-Security", "max-age=31536000"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
        ("Content-Security-Policy", politica),
    )


def cabeceras_para_ruta(
    ruta: str, fijas: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """RNF-06 — `Cache-Control: no-store` solo si la ruta empieza por `/api/`.

    Bajo `/api/` reemplaza cualquier `Cache-Control` que traiga `fijas` por `no-store`, así que aparece
    una sola vez aunque la lista ya la incluya. Fuera de `/api/` (documentación, OpenAPI) devuelve la
    lista tal cual.
    """
    if not ruta.startswith(PREFIJO_API):
        return fijas
    sin_cache = tuple((n, v) for n, v in fijas if n.lower() != "cache-control")
    return (*sin_cache, ("Cache-Control", "no-store"))


class MiddlewareCabecerasSeguridad:
    """ASGI puro, con el patrón de `MiddlewareCorrelacion` (RNF-05 · RNF-06).

    En `http.response.start` quita de la respuesta las cabeceras con los mismos nombres, sin distinguir
    mayúsculas, y añade las suyas: así ninguna ruta puede duplicarlas ni rebajarlas. `Cache-Control`
    solo se quita bajo `/api/`, igual que solo se añade ahí. Lifespan y websocket pasan sin cambios.
    """

    def __init__(self, app: ASGIApp, *, cabeceras: tuple[tuple[str, str], ...]) -> None:
        self.app = app
        self.cabeceras = cabeceras

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        fijas = cabeceras_para_ruta(scope["path"], self.cabeceras)
        nombres = frozenset(nombre.lower().encode("ascii") for nombre, _ in fijas)

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                conservadas = [
                    (k, v) for k, v in mensaje.get("headers", []) if k.lower() not in nombres
                ]
                conservadas.extend(
                    (nombre.lower().encode("ascii"), valor.encode("ascii"))
                    for nombre, valor in fijas
                )
                mensaje = {**mensaje, "headers": conservadas}
            await send(mensaje)

        await self.app(scope, receive, enviar)
