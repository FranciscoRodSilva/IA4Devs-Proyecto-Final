#!/usr/bin/env python3
"""Filtro de severidad para `npm audit` con excepciones documentadas y con fecha de revisión (RNF-08).

`npm audit --audit-level=high` falla ante cualquier aviso alto, también cuando no existe versión corregida y la única
salida es esperar al paquete. Este script lee el informe de `npm audit --json` (formato `auditReportVersion: 2`) y
falla ante `high`, `critical` o una severidad que no reconoce, salvo los avisos aceptados en la tabla `EXCEPCIONES`
de este archivo. Cada excepción es por `GHSA` exacto y por la severidad que se aceptó, nunca por paquete, y lleva
quién la decidió, su motivo y una fecha de revisión: pasada esa fecha deja de valer y el script vuelve a fallar.

El informe describe cada paquete afectado con su `via`. Un elemento de `via` que es un objeto es un aviso raíz, con su
`url` (de donde sale el `GHSA`) y su severidad; un elemento que es una cadena nombra otro paquete del que este
depende. Un paquete se excusa solo si todos sus avisos raíz alcanzables que fallan están aceptados y vigentes: los
paquetes que solo dependen de otro siguen a su raíz. Los avisos raíz `moderate`, `low` e `info` no fallan y no
hace falta aceptarlos. Un paquete alto cuya raíz no se puede determinar (`via` vacío, un paquete que el informe no
describe, un aviso sin `GHSA` en su `url`) falla: el fallo es cerrado.

Una excepción que ya no aparece en el informe se informa, para que se pueda retirar de la tabla.

Uso, desde la raíz del repositorio:
    python tools/severidad_npm_audit.py <ruta del informe JSON de npm audit>

Códigos: 0 si nada falla; 1 si algo falla; 2 si el informe no existe o no se puede leer. No existe `--ignore`: las
excepciones viven en este archivo, que pasa por revisión como cualquier otro cambio, igual que la de `pip-audit`
en el paso del flujo de trabajo.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

FORMATO_ADMITIDO = 2
SEVERIDADES_CONOCIDAS = ("info", "low", "moderate", "high", "critical")
SEVERIDADES_QUE_FALLAN = frozenset({"high", "critical"})
DESCONOCIDA = "desconocida"
ETIQUETAS = {
    "info": "INFO",
    "low": "BAJA",
    "moderate": "MEDIA",
    "high": "ALTA",
    "critical": "CRÍTICA",
    DESCONOCIDA: "DESCONOCIDA",
}
SUFIJO_QUE_FALLA = "→ falla el pipeline (RNF-08)"
GHSA_EN_URL = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}")


@dataclass(frozen=True)
class Excepcion:
    """Un aviso aceptado: por `ghsa` exacto y por la `severidad` que se aceptó, hasta la fecha de `revision` inclusive.

    `paquete` es solo informativo: el cotejo es por `ghsa`, nunca por nombre de paquete.
    """

    ghsa: str
    paquete: str
    severidad: str
    decidida_por: str
    motivo: str
    revision: date


# Las excepciones aceptadas. Añadir o ampliar una es una decisión de la persona dueña del proyecto: va por revisión
# de código, con su motivo y su fecha de revisión. Para retirarla basta con quitarla de la tabla.
EXCEPCIONES: tuple[Excepcion, ...] = (
    Excepcion(
        ghsa="GHSA-fc5q-39xc-vjpf",
        paquete="picomatch",
        severidad="high",
        decidida_por="la persona dueña del proyecto, 2026-11-18, en la sesión de Claude Code",
        motivo=(
            "picomatch (ReDoS por extglobs repetidos, severidad alta, rango afectado <= 4.0.7) no tiene versión "
            "corregida: la 4.0.7 es la última publicada (`npm view picomatch dist-tags`, 2026-11-18), y no hay "
            "actualización que la corrija. `npm ls picomatch --omit=dev` en frontend/ no lista ninguna copia el "
            "2026-11-18: llega solo por dependencias de desarrollo (shadcn, vite y vitest). Se revisa a más tardar en la "
            "fecha de revisión, o en cuanto se publique una versión corregida; entonces se retira esta excepción"
        ),
        revision=date(2026, 12, 18),
    ),
)


def fecha_de_hoy() -> date:
    """La fecha del reloj. Función propia para que las pruebas la sustituyan sin tocar el reloj (RNF-08)."""
    return date.today()


@dataclass(frozen=True)
class Raiz:
    """Un aviso raíz alcanzable desde un paquete: su `GHSA` (o `None` si no se puede leer) y su severidad."""

    ghsa: str | None
    severidad: str


@dataclass(frozen=True)
class Paquete:
    """Un paquete del informe con su veredicto: `falla`, `excusado` o `informa` (RNF-08)."""

    nombre: str
    severidad: str
    veredicto: str
    avisos: tuple[str, ...]
    revision: date | None = None
    caducadas: tuple[str, ...] = ()


def _severidad(valor: str) -> str:
    """La severidad en minúsculas si es una de las conocidas; cualquier otra es `DESCONOCIDA` y falla (RNF-08)."""
    normal = valor.strip().lower()
    return normal if normal in SEVERIDADES_CONOCIDAS else DESCONOCIDA


def _falla(severidad: str) -> bool:
    """Implementa RNF-08: `high`, `critical` y la severidad desconocida fallan; el resto solo se informa."""
    return severidad in SEVERIDADES_QUE_FALLAN or severidad == DESCONOCIDA


def leer_informe(texto: str) -> dict[str, dict[str, Any]]:
    """Devuelve el objeto `vulnerabilities` del informe de `npm audit --json` (RNF-08).

    Solo entiende `auditReportVersion: 2`. Cualquier otra forma es `ValueError`, incluido el informe de error que npm
    escribe sin red: un informe que no se entiende no pasa en verde.
    """
    datos: object = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("el informe no es un objeto JSON")
    if datos.get("auditReportVersion") != FORMATO_ADMITIDO:
        raise ValueError(f"el informe no declara «auditReportVersion»: {FORMATO_ADMITIDO}")
    vulnerabilidades = datos.get("vulnerabilities")
    if not isinstance(vulnerabilidades, dict):
        raise ValueError("el informe no tiene el objeto «vulnerabilities»")
    for nombre, entrada in vulnerabilidades.items():
        if not isinstance(entrada, dict) or not isinstance(entrada.get("severity"), str):
            raise ValueError(f"«{nombre}» no declara su «severity»")
        via = entrada.get("via")
        if not isinstance(via, list):
            raise ValueError(f"«{nombre}»: «via» no es una lista")
        for elemento in via:
            if isinstance(elemento, str):
                continue
            if not isinstance(elemento, dict) or not isinstance(elemento.get("severity"), str):
                raise ValueError(f"«{nombre}»: un elemento de «via» no es un paquete ni un aviso con «severity»")
    return vulnerabilidades


def _ghsa_de(aviso: dict[str, Any]) -> str | None:
    """El `GHSA-…` de la `url` del aviso, o `None` si no tiene ninguno."""
    url = aviso.get("url")
    encontrado = GHSA_EN_URL.search(url) if isinstance(url, str) else None
    return encontrado.group(0) if encontrado else None


def _raices(
    nombre: str, vulnerabilidades: dict[str, dict[str, Any]], visitados: set[str]
) -> list[Raiz]:
    """Los avisos raíz alcanzables desde `nombre`, siguiendo las cadenas de `via` (RNF-08).

    Un paquete que el informe no describe, o un ciclo sin ninguna raíz, no aportan raíz alguna: quien dependa solo de
    ellos queda sin raíz que aceptar y falla.
    """
    if nombre in visitados or nombre not in vulnerabilidades:
        return []
    visitados.add(nombre)
    raices: list[Raiz] = []
    for elemento in vulnerabilidades[nombre]["via"]:
        if isinstance(elemento, str):
            raices += _raices(elemento, vulnerabilidades, visitados)
        else:
            raices.append(Raiz(_ghsa_de(elemento), _severidad(elemento["severity"])))
    return raices


def _acepta(excepcion: Excepcion, raiz: Raiz) -> bool:
    """La excepción cubre el aviso: mismo `GHSA` exacto y misma severidad que se aceptó (RNF-08)."""
    return raiz.ghsa == excepcion.ghsa and raiz.severidad == _severidad(excepcion.severidad)


def clasificar(
    vulnerabilidades: dict[str, dict[str, Any]],
    excepciones: Sequence[Excepcion],
    hoy: date,
) -> tuple[list[Paquete], list[Excepcion]]:
    """Un `Paquete` por entrada del informe, y las excepciones que ya no aparecen en él (RNF-08).

    Qué paquetes entran a decidir lo fija la severidad que `npm audit` da al paquete, como con `--audit-level=high`:
    un paquete `moderate` no falla aunque dependa de otro alto. Veredicto `informa` si su severidad no falla;
    `excusado` si falla y todas las raíces que fallan están aceptadas por una excepción vigente (`hoy` no pasa de su
    `revision`); `falla` en cualquier otro caso.
    """
    paquetes: list[Paquete] = []
    vistos: set[str] = set()  # GHSA que el informe trae, para saber qué excepciones sobran
    for nombre, entrada in vulnerabilidades.items():
        severidad = _severidad(entrada["severity"])
        raices = _raices(nombre, vulnerabilidades, set())
        vistos.update(raiz.ghsa for raiz in raices if raiz.ghsa is not None)
        que_fallan = [raiz for raiz in raices if _falla(raiz.severidad)]
        avisos = tuple(dict.fromkeys(raiz.ghsa or "sin GHSA" for raiz in (que_fallan or raices)))
        if not _falla(severidad):
            paquetes.append(Paquete(nombre, severidad, "informa", avisos))
            continue
        cubiertas = [[e for e in excepciones if _acepta(e, raiz)] for raiz in que_fallan]
        vigentes = [[e for e in lista if hoy <= e.revision] for lista in cubiertas]
        if que_fallan and all(vigentes):
            revision = min(max(e.revision for e in lista) for lista in vigentes)
            paquetes.append(Paquete(nombre, severidad, "excusado", avisos, revision))
        else:
            caducadas = tuple(
                dict.fromkeys(
                    f"la excepción caducó el {e.revision.isoformat()}"
                    for lista, vigente in zip(cubiertas, vigentes, strict=True)
                    if not vigente
                    for e in lista
                )
            )
            paquetes.append(Paquete(nombre, severidad, "falla", avisos, None, caducadas))
    sobrantes = [excepcion for excepcion in excepciones if excepcion.ghsa not in vistos]
    return paquetes, sobrantes


def _linea(paquete: Paquete) -> str:
    """Una línea por paquete: etiqueta, nombre, avisos y, según el veredicto, el sufijo o la fecha de revisión."""
    texto = f"{ETIQUETAS[paquete.severidad]}  {paquete.nombre}  {', '.join(paquete.avisos) or 'sin aviso raíz'}"
    if paquete.veredicto == "excusado" and paquete.revision is not None:
        return f"EXCUSADA  {paquete.nombre}  {', '.join(paquete.avisos)} · fecha de revisión {paquete.revision.isoformat()}"
    if paquete.veredicto == "falla":
        if paquete.caducadas:
            texto += f" · {'; '.join(paquete.caducadas)}"
        texto += f" {SUFIJO_QUE_FALLA}"
    return texto


def _salida_utf8() -> None:
    """Fuerza UTF-8 en la salida de Windows, donde `→` y `Í` no caben en la codificación ANSI. Un `StringIO` no se toca."""
    for flujo in (sys.stdout, sys.stderr):
        if isinstance(flujo, io.TextIOWrapper):
            flujo.reconfigure(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Código 0 si nada falla; 1 si algo falla; 2 si el informe no existe o no se puede leer (RNF-08)."""
    _salida_utf8()
    parser = argparse.ArgumentParser(
        description="Falla ante avisos de npm audit de severidad alta, crítica o desconocida, salvo las excepciones vigentes (RNF-08)."
    )
    parser.add_argument("informe", type=Path, help="JSON de `npm audit --json`")
    argumentos = parser.parse_args(argv)

    try:
        vulnerabilidades = leer_informe(argumentos.informe.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as error:
        print(f"no se puede leer el informe de npm audit: {error}", file=sys.stderr)
        return 2

    excepciones = EXCEPCIONES
    paquetes, sobrantes = clasificar(vulnerabilidades, excepciones, fecha_de_hoy())

    if not paquetes:
        print("Sin vulnerabilidades en el informe de npm audit.")
    for paquete in paquetes:
        print(_linea(paquete))
    excusadas = {e.ghsa: e for e in excepciones if any(e.ghsa in p.avisos for p in paquetes if p.veredicto == "excusado")}
    for excepcion in excusadas.values():
        print(
            f"EXCEPCIÓN  {excepcion.ghsa} ({excepcion.paquete}, {excepcion.severidad}) · decidida por "
            f"{excepcion.decidida_por} · fecha de revisión {excepcion.revision.isoformat()} · motivo: {excepcion.motivo}"
        )
    for excepcion in sobrantes:
        print(
            f"INFORMATIVA  la excepción {excepcion.ghsa} ({excepcion.paquete}) ya no aparece en el informe: "
            "se puede retirar de EXCEPCIONES"
        )
    fallan = [p for p in paquetes if p.veredicto == "falla"]
    excusados = [p for p in paquetes if p.veredicto == "excusado"]
    print(f"Paquetes: {len(paquetes)} · que fallan el pipeline: {len(fallan)} · excusados: {len(excusados)}")
    return 1 if fallan else 0


if __name__ == "__main__":
    sys.exit(main())
