"""Verificación del despliegue de prueba en VPS (TKT-070).

Implementa CA-1, CA-2, CA-3, CA-4 y CA-S3.
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
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Exposicion:
    contenedor: str
    publicacion: str
    puerto_anfitrion: int


def _analizar_publicacion(entrada: str) -> tuple[str, int] | None:
    entrada = entrada.strip()
    if "->" not in entrada or not entrada.endswith("/tcp"):
        return None
    izquierda, derecha = entrada.rsplit("->", 1)
    puerto_contenedor = derecha[: -len("/tcp")]
    if puerto_contenedor != "5432":
        return None
    if izquierda.startswith("["):
        coincidencia = re.fullmatch(r"\[(.+)\]:(\d+)", izquierda)
        if coincidencia is None:
            return None
        return coincidencia.group(1), int(coincidencia.group(2))
    if ":" not in izquierda:
        return None
    direccion, puerto_texto = izquierda.rsplit(":", 1)
    return direccion, int(puerto_texto)


def exposiciones_docker(salida_docker_ps: str) -> list[Exposicion]:
    resultado: list[Exposicion] = []
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
            analizada = _analizar_publicacion(entrada)
            if analizada is None:
                continue
            direccion, puerto_anfitrion = analizada
            if direccion == "127.0.0.1":
                continue
            resultado.append(Exposicion(nombre, entrada.strip(), puerto_anfitrion))
    return resultado


def puertos_db_publicados(salida_docker_ps: str) -> set[int]:
    puertos: set[int] = set()
    for linea in salida_docker_ps.strip().splitlines():
        if not linea.strip():
            continue
        partes = linea.split("\t", 1)
        if len(partes) != 2:
            continue
        for entrada in partes[1].split(", "):
            analizada = _analizar_publicacion(entrada)
            if analizada is not None:
                puertos.add(analizada[1])
    return puertos


def escuchas_expuestas(salida_ss: str, puertos: set[int]) -> list[str]:
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
        if direccion.startswith("127.") or direccion in {"::1", "[::1]"}:
            continue
        if local.startswith("["):
            expuestas.append(local)
        else:
            expuestas.append(f"{direccion}:{puerto}")
    return expuestas


def evaluar_sondeo(ip: str, puerto: int, conecto: bool) -> str | None:
    if conecto:
        return f"la base responde desde fuera en {ip}:{puerto}"
    return None


def evaluar_redireccion(
    nombre: str, estado: int, location: str | None, cuerpo: bytes
) -> list[str]:
    fallos: list[str] = []
    if estado not in {301, 308}:
        fallos.append(f"HTTP de {nombre} devolvio estado {estado}, se esperaba 301 o 308")
    esperada = f"https://{nombre}/"
    if location != esperada:
        fallos.append(
            f"HTTP de {nombre} devolvio Location {location!r}, se esperaba {esperada!r}"
        )
    if b"CIMENTA" in cuerpo:
        fallos.append(f"HTTP de {nombre} llevo contenido del entorno en el cuerpo")
    return fallos


def evaluar_certificado(
    nombre: str, certificado: dict[str, Any], ahora: float
) -> list[str]:
    emisor = certificado.get("issuer", ())
    tiene_le = any(par == ("organizationName", "Let's Encrypt") for par in emisor)
    if not tiene_le:
        return [f"certificado de {nombre} no lo emitio Let's Encrypt: emisor {emisor!r}"]
    not_after = certificado.get("notAfter")
    if not_after is None:
        return [f"certificado de {nombre} no trae notAfter"]
    if ssl.cert_time_to_seconds(not_after) <= ahora:
        return [f"certificado de {nombre} caducado ({not_after})"]
    return []


def _ejecutar(comando: list[str]) -> str:
    completado = subprocess.run(
        comando, capture_output=True, text=True, check=True
    )
    return completado.stdout


def _sondear(ip: str, puerto: int, espera: float) -> bool:
    try:
        with socket.create_connection((ip, puerto), timeout=espera):
            return True
    except OSError:
        return False


def _pedir_http(nombre: str, espera: float) -> tuple[int, str | None, bytes]:
    conexion = http.client.HTTPConnection(nombre, 80, timeout=espera)
    try:
        conexion.request("GET", "/")
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read(4096)
        return respuesta.status, respuesta.getheader("Location"), cuerpo
    finally:
        conexion.close()


def _obtener_certificado(nombre: str, espera: float) -> dict[str, Any]:
    contexto = ssl.create_default_context()
    with socket.create_connection((nombre, 443), timeout=espera) as crudo, contexto.wrap_socket(
        crudo, server_hostname=nombre
    ) as tls:
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
) -> tuple[list[str], int | None]:
    fallas: list[str] = []
    try:
        salida_ps = ejecutar(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"])
        salida_ss = ejecutar(["ss", "-tln"])
    except FileNotFoundError as error:
        print(f"ERROR  {error}", file=sys.stderr)
        return fallas, 2
    except subprocess.CalledProcessError as error:
        print(f"ERROR  {error.stderr or error}", file=sys.stderr)
        return fallas, 2

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
    return fallas, None


def _cmd_remoto(
    args: argparse.Namespace,
    sondear: Callable[[str, int, float], bool],
    pedir_http: Callable[[str, float], tuple[int, str | None, bytes]],
    obtener_certificado: Callable[[str, float], dict[str, Any]],
    ahora: Callable[[], float],
) -> list[str]:
    fallas: list[str] = []
    ip = args.ip
    if ip is None:
        ip = socket.gethostbyname(args.nombres[0])

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
            estado, location, cuerpo = pedir_http(nombre, args.espera)
            fallos_http = evaluar_redireccion(nombre, estado, location, cuerpo)
            for fallo in fallos_http:
                _imprimir_resultado(fallo, False)
                fallas.append(fallo)
            if not fallos_http:
                _imprimir_resultado(f"HTTP de {nombre} redirige a HTTPS sin contenido", True)
        except (OSError, ssl.SSLError) as error:
            texto = f"HTTP de {nombre}: {error}"
            _imprimir_resultado(texto, False)
            fallas.append(texto)

        try:
            certificado = obtener_certificado(nombre, args.espera)
            fallos_cert = evaluar_certificado(nombre, certificado, instante)
            for fallo in fallos_cert:
                _imprimir_resultado(fallo, False)
                fallas.append(fallo)
            if not fallos_cert:
                _imprimir_resultado(f"certificado de {nombre} valido (Let's Encrypt)", True)
        except (OSError, ssl.SSLError) as error:
            texto = f"certificado de {nombre}: {error}"
            _imprimir_resultado(texto, False)
            fallas.append(texto)

    return fallas


def main(
    argv: list[str] | None = None,
    *,
    ejecutar: Callable[[list[str]], str] = _ejecutar,
    sondear: Callable[[str, int, float], bool] = _sondear,
    pedir_http: Callable[[str, float], tuple[int, str | None, bytes]] = _pedir_http,
    obtener_certificado: Callable[[str, float], dict[str, Any]] = _obtener_certificado,
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

    args = parser.parse_args(argv)
    if args.comando == "anfitrion":
        fallas, codigo_error = _cmd_anfitrion(args, ejecutar)
        if codigo_error is not None:
            return codigo_error
    elif args.comando == "remoto":
        fallas = _cmd_remoto(args, sondear, pedir_http, obtener_certificado, ahora)
    else:
        print(f"ERROR  suborden desconocida: {args.comando}", file=sys.stderr)
        return 2

    print(f"Resultado: {len(fallas)} fallas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
