#!/usr/bin/env python3
"""Filtro de la revisión automatizada de pull requests (TKT-062b, CA-5 y CA-7).

El modelo devuelve hallazgos estructurados; este guion decide cuáles se publican. Solo se publican los que traen
una cita de la lista de convenciones §12 y ninguna cadena con forma de clave de API. A los hallazgos del modelo se
les anteponen dos hallazgos mecánicos que no dependen de él: el PR sin ticket y el PR que modifica el borrador
OpenAPI. Los datos del evento llegan por variable de entorno y nunca se interpolan en una orden del flujo.

Entrada, por variable de entorno: `HALLAZGOS` (JSON del modelo), `TITULO`, `CUERPO` y `CABEZA` (SHA del commit
revisado). Por línea de órdenes: `--archivos` (un nombre de archivo del PR por línea) y `--salida` (donde se
escribe el comentario).

Códigos de salida:
    0  se escribió el comentario.
    2  `HALLAZGOS` falta o es inválido, o falta el archivo de `--archivos` (fallo cerrado: `--salida` no se escribe).

Uso, desde la raíz del repositorio:
    python3 tools/publicar_revision.py --archivos archivos.txt --salida comentario.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections.abc import Mapping, Sequence

CITA_VALIDA = re.compile(
    r"CLAUDE\.md regla (?:1[0-7]|[1-9])(?!\d)"
    r"|CLAUDE\.md «Qué no hacer»"
    r"|\bRN-(?:0[1-9]|1\d|2[0-5])(?!\d)"
    r"|\bRNF-(?:0[1-9]|1\d)(?!\d)"
    r"|\binvariante (?:3[0-8]|[12]\d|[1-9])(?!\d)"
    r"|convenciones §12 punto (?:1[01]|[1-9])(?!\d)"
    r"|non-goal de TKT-\d{3}[a-z]?\b"
)
CLAVE_EXPUESTA = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")
TICKET = re.compile(r"\bTKT-\d{3}[a-z]?\b")
CONTRATO = "docs/api/openapi.yaml"
TOPE = 60000

_ENCABEZADO = "### Revisión automatizada · comenta y no aprueba"
_SIN_HALLAZGOS = "Sin hallazgos de la lista de convenciones §12."
_CIERRE = (
    "La aprobación es de una persona. "
    "Si un hallazgo contradice una comprobación del pipeline, manda la comprobación."
)
_CAMPOS_DE_TEXTO = ("archivo", "texto", "cita")
_CLAVE_OFUSCADA = "skant"

Hallazgo = dict[str, object]


def leer_hallazgos(texto: str) -> list[Hallazgo]:
    """Interpreta el JSON del modelo y devuelve la lista `hallazgos`.

    Lanza `ValueError` si el texto está vacío, no es JSON, no es un objeto con la lista `hallazgos`, o algún
    elemento no trae `archivo`, `texto` y `cita` como cadenas (y `linea`, si viene, como entero). El mensaje
    nunca repite el contenido recibido.
    """
    if not texto.strip():
        raise ValueError("HALLAZGOS está vacío")
    try:
        valor = json.loads(texto)
    except (ValueError, RecursionError):
        raise ValueError("HALLAZGOS no es JSON válido") from None
    if not isinstance(valor, dict) or not isinstance(valor.get("hallazgos"), list):
        raise ValueError("HALLAZGOS no es un objeto con la lista hallazgos")
    hallazgos: list[Hallazgo] = valor["hallazgos"]
    for elemento in hallazgos:
        if not isinstance(elemento, dict):
            raise ValueError("un hallazgo no es un objeto")
        for campo in _CAMPOS_DE_TEXTO:
            if not isinstance(elemento.get(campo), str):
                raise ValueError(f"un hallazgo no tiene {campo} como cadena")
        linea = elemento.get("linea")
        if "linea" in elemento and (isinstance(linea, bool) or not isinstance(linea, int)):
            raise ValueError("un hallazgo tiene linea y no es un entero")
    return hallazgos


def _normalizar(texto: str) -> str:
    """Quita todo lo que no es alfanumérico (el guion bajo incluido) y pasa a minúsculas."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", texto).lower())


def _tiene_clave(hallazgo: Hallazgo) -> bool:
    """Una clave con forma literal, u ofuscada (`skant` tras normalizar), en un campo o partida entre los tres."""
    campos = [str(hallazgo[campo]) for campo in _CAMPOS_DE_TEXTO]
    if any(CLAVE_EXPUESTA.search(campo) or _CLAVE_OFUSCADA in _normalizar(campo) for campo in campos):
        return True
    return _CLAVE_OFUSCADA in _normalizar("".join(campos))


def separar_por_cita(hallazgos: Sequence[Hallazgo]) -> tuple[list[Hallazgo], list[Hallazgo]]:
    """Devuelve `(publicables, descartados)`.

    Se descarta el hallazgo con una clave de API en cualquiera de sus campos (también ofuscada o partida entre
    campos), o cuya cita, sin espacios al borde, no case entera con `CITA_VALIDA`. La clave se comprueba primero:
    una cita válida no salva a un texto con una clave.
    """
    publicables: list[Hallazgo] = []
    descartados: list[Hallazgo] = []
    for hallazgo in hallazgos:
        if _tiene_clave(hallazgo) or not CITA_VALIDA.fullmatch(str(hallazgo["cita"]).strip()):
            descartados.append(hallazgo)
        else:
            publicables.append(hallazgo)
    return publicables, descartados


def hallazgos_mecanicos(titulo: str, cuerpo: str, archivos: Sequence[str]) -> list[Hallazgo]:
    """Los hallazgos que no dependen del modelo: el PR sin ticket y el PR que toca el contrato.

    La ruta del contrato se compara entera, no por prefijo.
    """
    mecanicos: list[Hallazgo] = []
    if not (TICKET.search(titulo) or TICKET.search(cuerpo)):
        mecanicos.append(
            {
                "archivo": "",
                "texto": (
                    "El PR no cita ningún TKT-0XX en el título ni en el cuerpo: "
                    "sin ticket no hay non-goals contra los que revisar."
                ),
                "cita": "convenciones §12 punto 8",
            }
        )
    if CONTRATO in archivos:
        mecanicos.append(
            {
                "archivo": CONTRATO,
                "texto": (
                    "El PR modifica el borrador OpenAPI, que es el contrato que se implementa: "
                    "la persona que aprueba tiene que ver este cambio explícitamente."
                ),
                "cita": "convenciones §12 punto 11",
            }
        )
    return mecanicos


def _ubicacion(hallazgo: Hallazgo) -> str:
    """`archivo:linea`, o solo `archivo` si no hay línea; cadena vacía si no hay archivo."""
    archivo = str(hallazgo["archivo"])
    linea = hallazgo.get("linea")
    return f"{archivo}:{linea}" if archivo and linea is not None else archivo


def _como_elemento(numero: int, hallazgo: Hallazgo) -> str:
    ubicacion = _ubicacion(hallazgo)
    prefijo = f"`{ubicacion}` — " if ubicacion else ""
    return f"{numero}. {prefijo}{hallazgo['texto']} — *Cita:* {hallazgo['cita']}"


def componer_comentario(
    mecanicos: Sequence[Hallazgo], publicables: Sequence[Hallazgo], cabeza: str
) -> str:
    """Compone el comentario: primero los mecánicos y luego los publicables, en el orden recibido.

    Si el total pasa de `TOPE`, corta en el último hallazgo que cabe y añade cuántos no caben.
    """
    elementos = [
        _como_elemento(numero, hallazgo)
        for numero, hallazgo in enumerate([*mecanicos, *publicables], start=1)
    ]
    encabezado = f"{_ENCABEZADO}\n\nCommit revisado: `{cabeza[:7]}`"

    def componer(incluidos: Sequence[str]) -> str:
        partes = [encabezado]
        if elementos:
            partes.append("\n".join(incluidos))
            omitidos = len(elementos) - len(incluidos)
            if omitidos:
                partes.append(
                    f"({omitidos} hallazgos más no caben en el comentario: ver el registro del trabajo)"
                )
        else:
            partes.append(_SIN_HALLAZGOS)
        partes.append(_CIERRE)
        return "\n\n".join(partes) + "\n"

    cabe = len(elementos)
    while cabe > 0 and len(componer(elementos[:cabe])) > TOPE:
        cabe -= 1
    return componer(elementos[:cabe])


def _para_el_registro(texto: str) -> str:
    """Cambia `\\r` y `\\n` por un espacio y cada `::` por `: :`, para que nada impreso forme un comando de flujo."""
    sin_saltos = texto.replace("\r", " ").replace("\n", " ")
    return re.sub(r":(?=:)", ": ", sin_saltos)


def _leer_archivos(ruta: str) -> list[str]:
    with open(ruta, encoding="utf-8") as archivo:
        return [linea.strip() for linea in archivo if linea.strip()]


def main(argv: Sequence[str] | None = None, entorno: Mapping[str, str] | None = None) -> int:
    """Filtra los hallazgos del entorno y escribe el comentario en `--salida`.

    Devuelve 0 si lo escribió y 2 si la entrada es inválida; en ese caso no escribe `--salida`. El registro nombra
    cada descartado por `archivo:linea`, sin su texto ni su cita.
    """
    analizador = argparse.ArgumentParser(description="Filtra los hallazgos de la revisión automatizada.")
    analizador.add_argument("--archivos", required=True, help="archivo con un nombre de archivo del PR por línea")
    analizador.add_argument("--salida", required=True, help="donde se escribe el comentario")
    argumentos = analizador.parse_args(argv)
    if entorno is None:
        entorno = os.environ
    try:
        hallazgos = leer_hallazgos(entorno.get("HALLAZGOS", ""))
        archivos = _leer_archivos(argumentos.archivos)
    except ValueError as error:
        print(f"::error::{_para_el_registro(str(error))}")
        return 2
    except OSError:
        print("::error::no se pudo leer el archivo de --archivos")
        return 2

    publicables, descartados = separar_por_cita(hallazgos)
    for descartado in descartados:
        con_clave = _tiene_clave(descartado)
        razon = "por contener una clave" if con_clave else "sin cita"
        linea = descartado.get("linea")
        omitido = f"[archivo omitido]:{linea}" if linea is not None else "[archivo omitido]"
        if not con_clave and str(descartado["archivo"]) in archivos:
            ubicacion = _ubicacion(descartado)
        else:
            ubicacion = omitido
        print(f"descartado {razon}: {_para_el_registro(ubicacion)}")
    mecanicos = hallazgos_mecanicos(entorno.get("TITULO", ""), entorno.get("CUERPO", ""), archivos)
    comentario = componer_comentario(mecanicos, publicables, entorno.get("CABEZA", ""))
    with open(argumentos.salida, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(comentario)
    return 0


if __name__ == "__main__":
    sys.exit(main())
