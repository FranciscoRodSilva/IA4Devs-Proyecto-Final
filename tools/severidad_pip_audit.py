#!/usr/bin/env python3
"""Filtro de severidad para `pip-audit` (RNF-08, TKT-009b · fila B2).

`pip-audit` no informa la severidad de cada vulnerabilidad (supuesto A-3 de TKT-009). Este script lee su informe
JSON, toma la severidad del aviso de GitHub (`GHSA-…`) consultando OSV en `database_specific.severity`, y falla
ante `HIGH`, `CRITICAL` o severidad desconocida. `LOW` y `MODERATE` se informan y no fallan.

Sin severidad o sin `GHSA` no hay nada que consultar: el hallazgo es `DESCONOCIDA` y falla (fallo cerrado).

Uso, desde la raíz del repositorio:
    python tools/severidad_pip_audit.py <ruta del informe JSON de pip-audit>

Códigos: 0 si ningún hallazgo falla; 1 si alguno falla; 2 si el informe no se puede leer o la consulta a OSV
falla. No existe `--ignore-vuln`: las excepciones se declaran en el paso de `pip-audit`, con su comentario.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass(frozen=True)
class Hallazgo:
    """Una vulnerabilidad de `pip-audit` con su severidad (RNF-08).

    `aviso` es el primer `GHSA-…` entre el id y los alias, o `None` si no existe. `alias` son los alias del aviso de
    `pip-audit` tal como llegan; no entra en la igualdad, que solo mira lo que decide el filtro.
    """

    paquete: str
    version: str
    identificador: str  # el `id` de pip-audit
    aviso: str | None
    severidad: str  # LOW · MODERATE · HIGH · CRITICAL · DESCONOCIDA
    alias: tuple[str, ...] = field(default=(), compare=False)


def leer_informe(texto: str) -> list[dict]:
    """Devuelve la lista de dependencias del informe de `pip-audit` (RNF-08).

    Acepta el objeto `{"dependencies": [...]}` de la versión actual y la lista sin envoltorio de las antiguas.
    Cualquier otra forma es `ValueError`: un informe que no se entiende no pasa en verde.
    """
    datos = json.loads(texto)
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
            if not isinstance(vulnerabilidad.get("aliases", []), list):
                raise ValueError("«aliases» no es una lista")
    return datos


def consultar_osv(identificador: str) -> dict:
    """Pide a OSV el aviso `identificador` y devuelve su respuesta (RNF-08).

    No captura los errores de red ni de formato: `main` los convierte en código 2, para que un fallo de consulta
    nunca se confunda con un informe limpio.
    """
    url = URL_OSV.format(urllib.parse.quote(identificador, safe=""))
    with urllib.request.urlopen(url, timeout=TIEMPO_LIMITE_OSV) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _aviso_ghsa(identificador: str, alias: tuple[str, ...]) -> str | None:
    """El primer `GHSA-…` entre el id y los alias, o `None` (RNF-08, supuesto A-3)."""
    if identificador.startswith(PREFIJO_GHSA):
        return identificador
    return next((valor for valor in alias if valor.startswith(PREFIJO_GHSA)), None)


def _severidad_de(respuesta: object) -> str:
    """Lee `database_specific.severity` de OSV. Cualquier valor ausente o no reconocido es `DESCONOCIDA` (RNF-08)."""
    if not isinstance(respuesta, dict):
        return DESCONOCIDA
    especifica = respuesta.get("database_specific")
    severidad = especifica.get("severity") if isinstance(especifica, dict) else None
    if isinstance(severidad, str) and severidad.upper() in SEVERIDADES_CONOCIDAS:
        return severidad.upper()
    return DESCONOCIDA


def clasificar(dependencias: list[dict], consultar: Callable[[str], dict]) -> list[Hallazgo]:
    """Un `Hallazgo` por vulnerabilidad, con la severidad de OSV para su aviso GHSA (RNF-08).

    Sin GHSA no se consulta nada y la severidad es `DESCONOCIDA`. `consultar` se inyecta para que las pruebas no
    toquen la red.
    """
    hallazgos: list[Hallazgo] = []
    for dependencia in dependencias:
        for vulnerabilidad in dependencia.get("vulns", []):
            identificador = vulnerabilidad["id"]
            alias = tuple(vulnerabilidad.get("aliases", []))
            aviso = _aviso_ghsa(identificador, alias)
            severidad = DESCONOCIDA if aviso is None else _severidad_de(consultar(aviso))
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
    except (OSError, ValueError) as error:
        print(f"no se puede leer el informe de pip-audit: {error}", file=sys.stderr)
        return 2

    try:
        hallazgos = clasificar(dependencias, consultar_osv)
    except (OSError, ValueError) as error:
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
