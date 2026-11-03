"""Verificación del despliegue de prueba en VPS (TKT-070).

Implementa CA-1, CA-2, CA-3, CA-4 y CA-S3: exposición de PostgreSQL, escuchas del anfitrión,
redirección HTTP y certificados Let's Encrypt.
"""

from __future__ import annotations

import argparse
import http.client
import re
import socket
import ssl
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any


class ErrorEjecucionAnfitrion(Exception):
    """Fallo al ejecutar docker o ss en la VPS (salida 2)."""


@dataclass(frozen=True)
class Exposicion:
    contenedor: str
    publicacion: str
    puerto_anfitrion: int


def _publica_postgresql(especificacion_puerto: str) -> bool:
    if especificacion_puerto == "5432":
        return True
    if "-" in especificacion_puerto:
        inicio_texto, fin_texto = especificacion_puerto.split("-", 1)
        try:
            return int(inicio_texto) <= 5432 <= int(fin_texto)
        except ValueError:
            return False
    return False


def _analizar_publicacion(entrada: str) -> tuple[str, int] | None:
    entrada = entrada.strip()
    if "->" not in entrada or not entrada.endswith("/tcp"):
        return None
    izquierda, derecha = entrada.rsplit("->", 1)
    puerto_contenedor = derecha[: -len("/tcp")]
    if not _publica_postgresql(puerto_contenedor):
        return None
    if izquierda.startswith("["):
        coincidencia = re.fullmatch(r"\[(.+)\]:(\d+)", izquierda)
        if coincidencia is None:
            coincidencia = re.fullmatch(r"\[(.+)\]:(\d+)-\d+", izquierda)
        if coincidencia is None:
            return None
        return coincidencia.group(1), int(coincidencia.group(2))
    if ":" not in izquierda:
        return None
    direccion, puerto_texto = izquierda.rsplit(":", 1)
    puerto_base = puerto_texto.split("-", 1)[0]
    try:
        puerto_anfitrion = int(puerto_base)
    except ValueError:
        return None
    return direccion, puerto_anfitrion


def _iter_publicaciones_db(salida_docker_ps: str) -> Iterator[tuple[str, str]]:
    for linea in salida_docker_ps.strip().splitlines():
        if not linea.strip():
            continue
        partes = linea.split("\t", 1)
        if len(partes) != 2:
            continue
        nombre, publicaciones = partes[0], partes[1]
        if not publicaciones.strip():
            continue
        for entrada in publicaciones.split(", "):
            yield nombre, entrada.strip()


def exposiciones_docker(salida_docker_ps: str) -> list[Exposicion]:
    """Implementa CA-2: publicaciones de 5432/tcp fuera de 127.0.0.1."""
    resultado: list[Exposicion] = []
    for nombre, entrada in _iter_publicaciones_db(salida_docker_ps):
        analizada = _analizar_publicacion(entrada)
        if analizada is None:
            continue
        direccion, puerto_anfitrion = analizada
        if direccion == "127.0.0.1":
            continue
        resultado.append(Exposicion(nombre, entrada, puerto_anfitrion))
    return resultado


def puertos_db_publicados(salida_docker_ps: str) -> set[int]:
    """Puertos de anfitrion publicados hacia PostgreSQL (5432/tcp), para vigilar en ss."""
    puertos: set[int] = set()
    for _nombre, entrada in _iter_publicaciones_db(salida_docker_ps):
        analizada = _analizar_publicacion(entrada)
        if analizada is not None:
            puertos.add(analizada[1])
    return puertos


def escuchas_expuestas(salida_ss: str, puertos: set[int]) -> list[str]:
    """Escuchas en puertos de base que no son bucle local."""
    expuestas: list[str] = []
    for linea in salida_ss.strip().splitlines():
        campos = linea.split()
        if not campos or campos[0] == "State":
            continue
        if len(campos) < 4:
            continue
        local = campos[3]
        if ":" not in local:
            continue
        if local.startswith("["):
            coincidencia = re.fullmatch(r"\[(.+)\]:(\d+)", local)
            if coincidencia is None:
                continue
            direccion, puerto = coincidencia.group(1), int(coincidencia.group(2))
        else:
            direccion, puerto_texto = local.rsplit(":", 1)
            puerto = int(puerto_texto)
        if puerto not in puertos:
            continue
        if direccion.startswith("127.") or direccion == "::1":
            continue
        if local.startswith("["):
            expuestas.append(local)
        else:
            expuestas.append(f"{direccion}:{puerto}")
    return expuestas


def evaluar_sondeo(ip: str, puerto: int, conecto: bool) -> str | None:
    """Implementa CA-3: sonda TCP desde fuera hacia puertos de PostgreSQL."""
    if conecto:
        return f"la base responde desde fuera en {ip}:{puerto}"
    return None


def location_https_esperada(nombre: str, puerto_https: int) -> str:
    if puerto_https == 443:
        return f"https://{nombre}/"
    return f"https://{nombre}:{puerto_https}/"


def evaluar_redireccion(
    nombre: str,
    estado: int,
    location: str | None,
    cuerpo: bytes,
    puerto_https: int = 443,
) -> list[str]:
    """Implementa CA-4: redireccion HTTP a HTTPS sin servir la aplicacion."""
    fallos: list[str] = []
    if estado not in {301, 308}:
        fallos.append(f"HTTP de {nombre} devolvio estado {estado}, se esperaba 301 o 308")
    esperada = location_https_esperada(nombre, puerto_https)
    if location != esperada:
        fallos.append(f"HTTP de {nombre} devolvio Location {location!r}, se esperaba {esperada!r}")
    if b"CIMENTA" in cuerpo:
        fallos.append(f"HTTP de {nombre} llevo contenido del entorno en el cuerpo")
    return fallos


def _issuer_tiene_organization(emisor: tuple[Any, ...], organizacion: str) -> bool:
    """getpeercert() devuelve pares planos o anidados ((k, v),) segun la version de OpenSSL."""
    for par in emisor:
        if par == ("organizationName", organizacion):
            return True
        if (
            isinstance(par, tuple)
            and len(par) == 1
            and isinstance(par[0], tuple)
            and len(par[0]) == 2
            and par[0] == ("organizationName", organizacion)
        ):
            return True
    return False


def evaluar_certificado(nombre: str, certificado: dict[str, Any], ahora: float) -> list[str]:
    """Implementa CA-S3: certificado Let's Encrypt vigente."""
    emisor = certificado.get("issuer", ())
    if not _issuer_tiene_organization(emisor, "Let's Encrypt"):
        return [f"certificado de {nombre} no lo emitio Let's Encrypt: emisor {emisor!r}"]
    not_after = certificado.get("notAfter")
    if not_after is None:
        return [f"certificado de {nombre} no trae notAfter"]
    try:
        caduca = ssl.cert_time_to_seconds(not_after)
    except ValueError:
        return [f"certificado de {nombre} trae notAfter ilegible ({not_after!r})"]
    if caduca <= ahora:
        return [f"certificado de {nombre} caducado ({not_after})"]
    return []


def _ejecutar(comando: list[str]) -> str:
    completado = subprocess.run(comando, capture_output=True, text=True, check=True)
    return completado.stdout


def _sondear(ip: str, puerto: int, espera: float) -> bool:
    try:
        with socket.create_connection((ip, puerto), timeout=espera):
            return True
    except OSError:
        return False


def _pedir_http(nombre: str, puerto_http: int, espera: float) -> tuple[int, str | None, bytes]:
    conexion = http.client.HTTPConnection(nombre, puerto_http, timeout=espera)
    try:
        conexion.request("GET", "/")
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read(4096)
        return respuesta.status, respuesta.getheader("Location"), cuerpo
    finally:
        conexion.close()


def _obtener_certificado(nombre: str, puerto_https: int, espera: float) -> dict[str, Any]:
    contexto = ssl.create_default_context()
    with (
        socket.create_connection((nombre, puerto_https), timeout=espera) as crudo,
        contexto.wrap_socket(crudo, server_hostname=nombre) as tls,
    ):
        certificado = tls.getpeercert()
        if certificado is None:
            return {}
        return certificado


def _imprimir_resultado(texto: str, ok: bool) -> None:
    etiqueta = "OK" if ok else "FALLA"
    print(f"{etiqueta}  {texto}")


def _cmd_anfitrion(
    args: argparse.Namespace,
    ejecutar: Callable[[list[str]], str],
) -> list[str]:
    fallas: list[str] = []
    try:
        salida_ps = ejecutar(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"])
        salida_ss = ejecutar(["ss", "-tln"])
    except FileNotFoundError as error:
        raise ErrorEjecucionAnfitrion(str(error)) from error
    except subprocess.CalledProcessError as error:
        raise ErrorEjecucionAnfitrion(error.stderr or str(error)) from error

    puertos = set(args.puertos) | puertos_db_publicados(salida_ps)
    for exposicion in exposiciones_docker(salida_ps):
        texto = f"{exposicion.publicacion} en {exposicion.contenedor}"
        _imprimir_resultado(texto, False)
        fallas.append(texto)

    for escucha in escuchas_expuestas(salida_ss, puertos):
        _imprimir_resultado(f"escucha expuesta {escucha}", False)
        fallas.append(escucha)

    if not fallas:
        _imprimir_resultado("ninguna publicacion ni escucha expuesta de PostgreSQL", True)
    return fallas


def _cmd_remoto(
    args: argparse.Namespace,
    sondear: Callable[[str, int, float], bool],
    pedir_http: Callable[[str, int, float], tuple[int, str | None, bytes]],
    obtener_certificado: Callable[[str, int, float], dict[str, Any]],
    ahora: Callable[[], float],
) -> list[str]:
    fallas: list[str] = []
    ip = args.ip
    if ip is None:
        try:
            ip = socket.gethostbyname(args.nombres[0])
        except OSError as error:
            raise OSError(f"resolucion DNS de {args.nombres[0]}: {error}") from error

    for puerto in args.puertos:
        conecto = sondear(ip, puerto, args.espera)
        mensaje = evaluar_sondeo(ip, puerto, conecto)
        if mensaje:
            _imprimir_resultado(mensaje, False)
            fallas.append(mensaje)
        else:
            _imprimir_resultado(f"puerto {puerto} de {ip} no responde desde fuera", True)

    instante = ahora()
    for nombre in args.nombres:
        try:
            estado, location, cuerpo = pedir_http(nombre, args.http_port, args.espera)
            fallos_http = evaluar_redireccion(nombre, estado, location, cuerpo, args.https_port)
            for fallo in fallos_http:
                _imprimir_resultado(fallo, False)
                fallas.append(fallo)
            if not fallos_http:
                _imprimir_resultado(f"HTTP de {nombre} redirige a HTTPS sin contenido", True)
        except (OSError, http.client.HTTPException) as error:
            texto = f"HTTP de {nombre}: {error}"
            _imprimir_resultado(texto, False)
            fallas.append(texto)

        try:
            certificado = obtener_certificado(nombre, args.https_port, args.espera)
            fallos_cert = evaluar_certificado(nombre, certificado, instante)
            for fallo in fallos_cert:
                _imprimir_resultado(fallo, False)
                fallas.append(fallo)
            if not fallos_cert:
                _imprimir_resultado(f"certificado de {nombre} valido (Let's Encrypt)", True)
        except OSError as error:
            texto = f"certificado de {nombre}: {error}"
            _imprimir_resultado(texto, False)
            fallas.append(texto)

    return fallas


def main(
    argv: list[str] | None = None,
    *,
    ejecutar: Callable[[list[str]], str] = _ejecutar,
    sondear: Callable[[str, int, float], bool] = _sondear,
    pedir_http: Callable[[str, int, float], tuple[int, str | None, bytes]] = _pedir_http,
    obtener_certificado: Callable[[str, int, float], dict[str, Any]] = _obtener_certificado,
    ahora: Callable[[], float] = time.time,
) -> int:
    parser = argparse.ArgumentParser(description="Verificacion de despliegue TKT-070")
    sub = parser.add_subparsers(dest="comando", required=True)

    anfitrion = sub.add_parser("anfitrion", help="Comprueba en la VPS (docker ps y ss)")
    anfitrion.add_argument(
        "--puertos",
        type=int,
        nargs="+",
        default=[5432, 5433, 5434],
        help="Puertos de PostgreSQL a vigilar en ss",
    )

    remoto = sub.add_parser("remoto", help="Comprueba desde fuera de la VPS")
    remoto.add_argument(
        "--nombres",
        nargs="+",
        default=["apbuildings.duckdns.org", "apbuildings-test.duckdns.org"],
    )
    remoto.add_argument("--ip", default=None)
    remoto.add_argument(
        "--puertos",
        type=int,
        nargs="+",
        default=[5432, 5433, 5434],
    )
    remoto.add_argument("--espera", type=float, default=5.0)
    remoto.add_argument(
        "--http-port",
        type=int,
        default=80,
        help="Puerto HTTP publico hacia Caddy (Database Mart: 10004)",
    )
    remoto.add_argument(
        "--https-port",
        type=int,
        default=443,
        help="Puerto HTTPS publico hacia Caddy (Database Mart: 10005)",
    )

    args = parser.parse_args(argv)
    if args.comando == "anfitrion":
        try:
            fallas = _cmd_anfitrion(args, ejecutar)
        except ErrorEjecucionAnfitrion as error:
            print(f"ERROR  {error}", file=sys.stderr)
            return 2
    elif args.comando == "remoto":
        try:
            fallas = _cmd_remoto(args, sondear, pedir_http, obtener_certificado, ahora)
        except OSError as error:
            print(f"ERROR  {error}", file=sys.stderr)
            return 2
    else:
        print(f"ERROR  suborden desconocida: {args.comando}", file=sys.stderr)
        return 2

    print(f"Resultado: {len(fallas)} fallas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
