#!/usr/bin/env python3
"""Filtro de severidad para `pip-audit` (RNF-08, TKT-009b · fila B2).

`pip-audit` no informa la severidad de cada vulnerabilidad (supuesto A-3 de TKT-009). Este script lee su informe
JSON, toma la severidad del aviso de GitHub (`GHSA-…`) consultando OSV en `database_specific.severity`, y falla
ante `HIGH`, `CRITICAL` o severidad desconocida. `LOW` y `MODERATE` se informan y no fallan.

Un hallazgo puede tener varios `GHSA` (el `id` y sus alias). Se consulta cada `GHSA` distinto una sola vez y gana
el peor (`CRITICAL` > `HIGH` > `DESCONOCIDA` > `MODERATE` > `LOW`): basta un `GHSA` que falle para que falle el
hallazgo (al primero `HIGH` o `CRITICAL` se deja de consultar). Una consulta sin severidad válida es `DESCONOCIDA`. Sin ningún `GHSA` no hay nada que consultar: el
hallazgo es `DESCONOCIDA` y falla (fallo cerrado).

Uso, desde la raíz del repositorio:
    python tools/severidad_pip_audit.py <ruta del informe JSON de pip-audit>

Códigos: 0 si ningún hallazgo falla; 1 si alguno falla; 2 si el informe no se puede leer o la consulta a OSV
falla. No existe `--ignore-vuln`: las excepciones se declaran en el paso de `pip-audit`, con su comentario.
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Severidades de OSV (la del aviso de GitHub) que fallan el pipeline (RNF-08). `DESCONOCIDA` falla aparte.
SEVERIDADES_QUE_FALLAN = frozenset({"HIGH", "CRITICAL"})
URL_OSV = "https://api.osv.dev/v1/vulns/{}"
TIEMPO_LIMITE_OSV = 15  # segundos

DESCONOCIDA = "DESCONOCIDA"
SEVERIDADES_CONOCIDAS = frozenset({"LOW", "MODERATE", "HIGH", "CRITICAL"})
ETIQUETAS = {
    "LOW": "BAJA",
    "MODERATE": "MEDIA",
    "HIGH": "ALTA",
    "CRITICAL": "CRÍTICA",
    DESCONOCIDA: DESCONOCIDA,
}
SUFIJO_QUE_FALLA = "→ falla el pipeline (RNF-08)"
PREFIJO_GHSA = "GHSA-"
# Del peor al mejor: la posición decide qué severidad gana entre varios GHSA de un mismo hallazgo.
ORDEN_DE_GRAVEDAD = ("CRITICAL", "HIGH", DESCONOCIDA, "MODERATE", "LOW")
TOPE_RESPUESTA_OSV = 1_000_000  # bytes


@dataclass(frozen=True)
class Hallazgo:
    """Una vulnerabilidad de `pip-audit` con su severidad (RNF-08).

    `aviso` es el `GHSA-…` que decidió la severidad (el de la peor), o `None` si el hallazgo no tiene ninguno. `alias` son los alias del aviso de
    `pip-audit` tal como llegan; no entra en la igualdad, que solo mira lo que decide el filtro.
    """

    paquete: str
    version: str
    identificador: str  # el `id` de pip-audit
    aviso: str | None
    severidad: str  # LOW · MODERATE · HIGH · CRITICAL · DESCONOCIDA
    alias: tuple[str, ...] = field(default=(), compare=False)


def leer_informe(texto: str) -> list[dict[str, Any]]:
    """Devuelve la lista de dependencias del informe de `pip-audit` (RNF-08).

    Acepta el objeto `{"dependencies": [...]}` de la versión actual y la lista sin envoltorio de las antiguas.
    Cualquier otra forma es `ValueError`: un informe que no se entiende no pasa en verde.
    """
    datos: object = json.loads(texto)
    if isinstance(datos, dict):
        datos = datos.get("dependencies")
    if not isinstance(datos, list) or not all(
        isinstance(dependencia, dict) for dependencia in datos
    ):
        raise ValueError("el informe no tiene la lista de dependencias de pip-audit")
    for dependencia in datos:
        vulnerabilidades = dependencia.get("vulns", [])
        if not isinstance(vulnerabilidades, list):
            raise ValueError("«vulns» no es una lista")
        if not vulnerabilidades:
            continue
        if not isinstance(dependencia.get("name"), str) or not isinstance(
            dependencia.get("version"), str
        ):
            raise ValueError("una dependencia con vulnerabilidades no declara nombre y versión")
        for vulnerabilidad in vulnerabilidades:
            if not isinstance(vulnerabilidad, dict) or not isinstance(
                vulnerabilidad.get("id"), str
            ):
                raise ValueError("una vulnerabilidad no declara su «id»")
            aliases = vulnerabilidad.get("aliases", [])
            if not isinstance(aliases, list):
                raise ValueError("«aliases» no es una lista")
            if not all(isinstance(valor, str) for valor in aliases):
                raise ValueError("«aliases» no es una lista de cadenas")
    return datos


def consultar_osv(identificador: str) -> object:
    """Pide a OSV el aviso `identificador` y devuelve su respuesta ya decodificada (RNF-08).

    Lee a lo sumo `TOPE_RESPUESTA_OSV` bytes: una respuesta mayor es `ValueError`. No captura los demás errores de
    red ni de formato: `main` los convierte en código 2, para que un fallo de consulta nunca se confunda con un
    informe limpio.
    """
    url = URL_OSV.format(urllib.parse.quote(identificador, safe=""))
    with urllib.request.urlopen(url, timeout=TIEMPO_LIMITE_OSV) as respuesta:
        cuerpo: bytes = respuesta.read(TOPE_RESPUESTA_OSV + 1)
    if len(cuerpo) > TOPE_RESPUESTA_OSV:
        raise ValueError(f"la respuesta de OSV supera {TOPE_RESPUESTA_OSV} bytes")
    datos: object = json.loads(cuerpo.decode("utf-8"))
    return datos


def _avisos_ghsa(identificador: str, alias: tuple[str, ...]) -> list[str]:
    """Todos los `GHSA-…` distintos entre el id y los alias, en ese orden y sin duplicados (RNF-08, supuesto A-3)."""
    avisos: list[str] = []
    for valor in (identificador, *alias):
        if valor.startswith(PREFIJO_GHSA) and valor not in avisos:
            avisos.append(valor)
    return avisos


def _severidad_de(respuesta: object) -> str:
    """Lee `database_specific.severity` de OSV. Cualquier valor ausente o no reconocido es `DESCONOCIDA` (RNF-08)."""
    if not isinstance(respuesta, dict):
        return DESCONOCIDA
    especifica = respuesta.get("database_specific")
    severidad = especifica.get("severity") if isinstance(especifica, dict) else None
    if isinstance(severidad, str) and severidad.upper() in SEVERIDADES_CONOCIDAS:
        return severidad.upper()
    return DESCONOCIDA


def _peor(avisos: list[str], consultar: Callable[[str], object]) -> tuple[str | None, str]:
    """Consulta cada GHSA una vez y devuelve el que tiene la peor severidad, con esa severidad (RNF-08).

    Ante un empate gana el primero. En cuanto un GHSA da `HIGH` o `CRITICAL` el hallazgo ya falla y no se consultan
    los siguientes. Sin GHSA devuelve `(None, DESCONOCIDA)` sin consultar.
    """
    peor_aviso: str | None = None
    peor_severidad = DESCONOCIDA
    peor_rango = len(ORDEN_DE_GRAVEDAD)
    for aviso in avisos:
        severidad = _severidad_de(consultar(aviso))
        rango = ORDEN_DE_GRAVEDAD.index(severidad)
        if rango < peor_rango:
            peor_aviso, peor_severidad, peor_rango = aviso, severidad, rango
        if peor_severidad in SEVERIDADES_QUE_FALLAN:
            break  # el hallazgo ya falla: consultar más GHSA no cambia el resultado
    return peor_aviso, peor_severidad


def clasificar(
    dependencias: list[dict[str, Any]], consultar: Callable[[str], object]
) -> list[Hallazgo]:
    """Un `Hallazgo` por vulnerabilidad, con la peor severidad de OSV entre todos sus avisos GHSA (RNF-08).

    Sin GHSA no se consulta nada y la severidad es `DESCONOCIDA`. `consultar` se inyecta para que las pruebas no
    toquen la red.
    """
    hallazgos: list[Hallazgo] = []
    for dependencia in dependencias:
        for vulnerabilidad in dependencia.get("vulns", []):
            identificador = vulnerabilidad["id"]
            alias = tuple(vulnerabilidad.get("aliases", []))
            aviso, severidad = _peor(_avisos_ghsa(identificador, alias), consultar)
            hallazgos.append(
                Hallazgo(
                    dependencia["name"],
                    dependencia["version"],
                    identificador,
                    aviso,
                    severidad,
                    alias,
                )
            )
    return hallazgos


def _falla(hallazgo: Hallazgo) -> bool:
    """Implementa RNF-08: `HIGH`, `CRITICAL` y `DESCONOCIDA` fallan; `LOW` y `MODERATE` solo se informan."""
    return hallazgo.severidad in SEVERIDADES_QUE_FALLAN or hallazgo.severidad == DESCONOCIDA


def _linea(hallazgo: Hallazgo) -> str:
    """Una línea por hallazgo: etiqueta, paquete, versión, GHSA, alias sin el GHSA y luego el id."""
    cabeza = hallazgo.aviso or hallazgo.identificador
    otros = [valor for valor in hallazgo.alias if valor != cabeza]
    if hallazgo.identificador != cabeza and hallazgo.identificador not in otros:
        otros.append(hallazgo.identificador)
    texto = f"{ETIQUETAS[hallazgo.severidad]}  {hallazgo.paquete} {hallazgo.version}  {cabeza}"
    if otros:
        texto += f" ({', '.join(otros)})"
    if _falla(hallazgo):
        texto += f" {SUFIJO_QUE_FALLA}"
    return texto


def _salida_utf8() -> None:
    """Fuerza UTF-8 en la salida de Windows, donde `→` y `Í` no caben en la codificación ANSI. Un `StringIO` no se toca."""
    for flujo in (sys.stdout, sys.stderr):
        if isinstance(flujo, io.TextIOWrapper):
            flujo.reconfigure(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Código 0 si ningún hallazgo falla; 1 si alguno falla; 2 si el informe o la consulta fallan (RNF-08)."""
    _salida_utf8()
    parser = argparse.ArgumentParser(
        description="Falla ante vulnerabilidades de severidad alta o desconocida (RNF-08)."
    )
    parser.add_argument("informe", type=Path, help="JSON de `pip-audit -f json`")
    argumentos = parser.parse_args(argv)

    try:
        dependencias = leer_informe(argumentos.informe.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as error:
        print(f"no se puede leer el informe de pip-audit: {error}", file=sys.stderr)
        return 2

    try:
        hallazgos = clasificar(dependencias, consultar_osv)
    except (OSError, ValueError, RecursionError, http.client.HTTPException) as error:
        print(f"falla la consulta a OSV: {error}", file=sys.stderr)
        return 2

    if not hallazgos:
        print("Sin vulnerabilidades en el informe de pip-audit.")
        return 0

    for hallazgo in hallazgos:
        print(_linea(hallazgo))
    fallan = [hallazgo for hallazgo in hallazgos if _falla(hallazgo)]
    print(f"Hallazgos: {len(hallazgos)} · que fallan el pipeline: {len(fallan)}")
    return 1 if fallan else 0


if __name__ == "__main__":
    sys.exit(main())
