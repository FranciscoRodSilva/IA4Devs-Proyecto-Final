"""Pruebas del filtro de la revisión automatizada, `tools/publicar_revision.py`.

TKT-062b · fila B1 · `CA-5` y `CA-7`. El modelo devuelve hallazgos estructurados y el filtro decide cuáles se publican:
solo los que traen una cita de la lista de convenciones y ninguna cadena con forma de clave de API. Al conjunto se
le añaden dos hallazgos mecánicos que no dependen del modelo (el PR sin ticket y el PR que toca el borrador OpenAPI).
`main(argv, entorno)` lee `HALLAZGOS`, `TITULO`, `CUERPO` y `CABEZA` del entorno, y `--archivos` y `--salida` de la línea
de órdenes. Devuelve 0 si escribió el comentario y 2 si la entrada es inválida; en el segundo caso `--salida` no se escribe.

Las pruebas de `main` no tocan la red ni el entorno real: reciben el entorno por parámetro y escriben en una carpeta
temporal. Solo las del bloque «como proceso» lanzan el guion con el intérprete, tal como lo hace el flujo.

Casos del plan de pruebas del diseño de TKT-062:

* TC62-20  un hallazgo con una cita de la lista se publica con su cita y su `archivo:linea`.
* TC62-21  las citas vacías, genéricas o fuera de rango (la regla 18 y la 170 de CLAUDE.md, la regla `RN` con número 26,
           el invariante con número 39 y el punto 12 de convenciones §12) no aparecen en el comentario. Desde el ajuste
           del 2026-10-30 (F003) la cita es de vocabulario cerrado: `CITA_VALIDA` se aplica con `fullmatch` sobre
           `cita.strip()`, así que una cita con texto libre alrededor (una mención, una imagen, otra cita) se descarta, y las
           formas exactas siguen valiendo, con espacios al borde incluidos.
* TC62-22  sin ticket en el título ni en el cuerpo, el primer hallazgo lo dice; con ticket en el cuerpo, no aparece.
* TC62-23  un PR que modifica `docs/api/openapi.yaml` lo señala; la comparación de la ruta es exacta.
* TC62-24  `HALLAZGOS` vacío, que no es JSON o sin la lista `hallazgos` termina en 2 y `--salida` no se escribe.
* TC62-25  encabezado con los siete primeros del SHA, «Sin hallazgos…», corte por `TOPE` con la nota de los que faltan y
           un registro en que ningún dato puede formar un comando de flujo de GitHub.
* TC62-42  un hallazgo con cita válida y una clave de API en su texto no se publica y el registro no la imprime. Desde el
           ajuste del 2026-10-30:
           (F001 c) una clave escrita con separadores (`s k - a n t - a p i 0 3 - …`), con guiones bajos, en mayúsculas o
           partida entre campos también se descarta, por la razón «por contener una clave»;
           (F002) si la clave está en `archivo`, el registro imprime `[archivo omitido]:<linea>` y ninguna línea del registro
           contiene `sk-ant-` ni su versión ofuscada.
           Desde la reauditoría del mismo día:
           (N001) `_normalizar` aplica `unicodedata.normalize("NFKC")` antes de pasar a minúsculas, así que una clave en ancho
           completo (`ｓｋ－ａｎｔ－api03…`) en el texto, la cita o el archivo también se descarta por la clave;
           (N002 a) si el descarte es por clave, el registro imprime siempre `[archivo omitido]:<linea>` (sin `:<linea>` si el
           hallazgo no trae línea), aunque la clave no sea detectable en `archivo` solo (el cuerpo de la clave en `archivo` y
           `sk-ant-` en el texto o la cita) y aunque el archivo conste en `--archivos`;
           (N002 b) si el descarte es por cita inválida, el registro imprime el `archivo` solo si figura, con ese nombre exacto,
           en la lista de `--archivos`; si no, `[archivo omitido]:<linea>` (sin `:<linea>` si no hay línea). Un archivo que es
           subcadena de uno de la lista no cuenta como listado.

Mutantes que estas pruebas deben matar (tabla de mutación del diseño). Cada uno se aplica a una copia privada del módulo y
la clase `PruebasDeMutantes` exige que la comprobación del caso devuelva problemas:

* `CITA_VALIDA` con el rango de las reglas ampliado a la 18: cae TC62-21 (la regla 18).
* `CITA_VALIDA` con las reglas `RN` de dos cifras sin sobrepasar el tope: cae TC62-21 (el número 26).
* `CITA_VALIDA` con una alternativa vacía, que casa con la cita vacía: cae TC62-21.
* `CITA_VALIDA` aplicada con `search` en lugar de `fullmatch` (F003): cae TC62-21 (la cita con texto libre alrededor).
* `CLAVE_EXPUESTA` comprobada solo en el texto y no en la cita ni en el archivo: cae TC62-42 (la clave en el archivo).
* `CLAVE_EXPUESTA` que nunca casa: cae TC62-42.
* `separar_por_cita` sin la comprobación de la clave ofuscada, sin pasar a minúsculas, sin quitar los guiones bajos o sin
  mirar la concatenación de los tres campos (F001 c): cae TC62-42 (la variante que se escapa en cada caso).
* `_normalizar` sin `unicodedata.normalize("NFKC")` (N001): cae TC62-42 (la clave en ancho completo).
* El registro que imprime el `archivo` siempre; que lo omite solo cuando la clave está en `archivo`; que lo omite siempre en
  una cita inválida; que lo imprime siempre en una cita inválida con clave omitida; que compara el archivo con la lista por
  subcadena (N002): cae el caso del registro que corresponde a cada uno. Estos mutantes sustituyen `main` por una copia
  que solo cambia cómo se elige la ubicación que se imprime.

El mutante que quitaba la guarda `(?!\\d)` de la regla de `CITA_VALIDA` se retira: con `fullmatch` esa guarda es redundante,
porque el final del patrón ya coincide con el final de la cita, así que el cambio no altera ningún resultado (mutante
equivalente). La cita «regla 170» sigue en `CITAS_INVALIDAS` y la mata el mutante de `search`.
* `_para_el_registro` sin sustituir los dos puntos dobles: cae TC62-25.
* `hallazgos_mecanicos` que busca el ticket solo en el título: cae TC62-22.
* `hallazgos_mecanicos` que compara la ruta del contrato por prefijo: cae TC62-23.

Queda sin mutante automático el orden «la clave se comprueba antes que la cita», porque solo se observa en la razón que
imprime el registro y no hay una costura en el módulo para invertirlo sin conocer su código; TC62-42 lo comprueba en
el registro y la mutación manual del ingeniero lo cubre al cerrar la fila.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_publicar_revision -v
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from collections.abc import Callable
from typing import Any, NamedTuple

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

GUION = os.path.join(HERRAMIENTAS, "publicar_revision.py")

# ---------------------------------------------------------------------------------------------------------
# Datos de ejemplo: los textos exactos del diseño
# ---------------------------------------------------------------------------------------------------------

ENCABEZADO = "### Revisión automatizada · comenta y no aprueba"
SIN_HALLAZGOS = "Sin hallazgos de la lista de convenciones §12."
CIERRE = (
    "La aprobación es de una persona. "
    "Si un hallazgo contradice una comprobación del pipeline, manda la comprobación."
)
TEXTO_SIN_TICKET = (
    "El PR no cita ningún TKT-0XX en el título ni en el cuerpo: "
    "sin ticket no hay non-goals contra los que revisar."
)
CITA_SIN_TICKET = "convenciones §12 punto 8"
TEXTO_OPENAPI = (
    "El PR modifica el borrador OpenAPI, que es el contrato que se implementa: "
    "la persona que aprueba tiene que ver este cambio explícitamente."
)
CITA_OPENAPI = "convenciones §12 punto 11"
CONTRATO = "docs/api/openapi.yaml"

SHA = "abcdef1234567890abcdef1234567890abcdef12"
TITULO_CON_TICKET = "TKT-062b · revisión automatizada"

# Citas que la lista de convenciones acepta. La regla 17 y el invariante 38 son los topes; la 1 y el 1, los mínimos.
CITAS_VALIDAS = (
    "CLAUDE.md regla 11",
    "CLAUDE.md regla 1",
    "CLAUDE.md regla 17",
    "CLAUDE.md «Qué no hacer»",
    "RN-01",
    "RN-03",
    "RN-25",
    "RNF-01",
    "RNF-19",
    "invariante 1",
    "invariante 38",
    "convenciones §12 punto 1",
    "convenciones §12 punto 11",
    "non-goal de TKT-062b",
    "non-goal de TKT-009",
    # Con espacios al borde se admite: el filtro aplica `fullmatch` sobre `cita.strip()`.
    "  RN-03  ",
    " CLAUDE.md regla 11 ",
)

# Citas que no. Cada una está justo fuera del rango o es una forma que se parece pero no es.
CITAS_INVALIDAS = (
    "",
    "buenas prácticas",
    "CLAUDE.md regla 18",
    "CLAUDE.md regla 170",
    "CLAUDE.md regla 0",
    "regla 11",
    "RN-26",
    "RN-250",
    "RN-00",
    "RNF-20",
    "invariante 39",
    "invariante 100",
    "convenciones §12 punto 12",
    "convenciones §12 punto 0",
    "non-goal de TKT-62",
    # F003 · la cita es de vocabulario cerrado: texto libre alrededor de una forma válida la descarta.
    "x @org/equipo ![i](https://e/?q=1) RN-03",
    "Viola CLAUDE.md regla 5 y además RN-04",
    "ver RN-03",
    "RN-03 @org/equipo",
    "RN-03 y RN-04",
    "CLAUDE.md regla 11 ![i](https://e/?q=1)",
    "RN-03\n![i](https://e/?q=1)",
)

CLAVE_DE_EJEMPLO = "sk-ant-abcdefghij0123456789"

# F001 (c) · la misma clave escrita con separadores, con guiones bajos, en mayúsculas o con otros signos. Ninguna casa con
# `CLAVE_EXPUESTA`; todas dejan `skant` al quitar lo que no es alfanumérico y pasar a minúsculas.
CLAVES_OFUSCADAS = {
    "con espacios": "s k - a n t - a p i 0 3 - A B C d e f 1 2 3 4",
    "con guiones bajos": "s_k_-_a_n_t_-_api03_ABCdef1234",
    "en mayúsculas": "SK-ANT-API03-ABCdef1234",
    "con otros signos": "s.k/a|n*t-api03-ABCdef1234",
}

# Cada una parte la clave entre dos campos contiguos: (archivo, texto, cita) concatenados en ese orden la completan.
CLAVES_PARTIDAS = {
    "archivo y texto": {"archivo": "src/sk-", "texto": "ant-api03-ABCdef1234 en el registro", "cita": "RN-03"},
    "archivo y texto con espacios": {"archivo": "s k", "texto": "- a n t - a p i 0 3 - ABCdef1234", "cita": "RN-03"},
    "texto y cita": {"archivo": "src/a.py", "texto": "La clave empieza en sk-", "cita": "ant-api03-ABCdef1234"},
}


def normalizado(texto: str) -> str:
    """Lo que el filtro compara (N001): en NFKC, en minúsculas y sin lo que no es alfanumérico (el guion bajo incluido)."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", texto).lower())


def ancho_completo(texto: str) -> str:
    """Los caracteres ASCII imprimibles pasan a su forma de ancho completo (`sk-` pasa a `ｓｋ－`); NFKC los devuelve a ASCII."""
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in texto)


# N001 · claves que solo se reconocen tras NFKC. La primera es la del hallazgo: prefijo en ancho completo y resto en ASCII.
CLAVES_ANCHO_COMPLETO = {
    "en ancho completo": ancho_completo("sk-ant-") + "api03-ABCdef1234",
    "toda en ancho completo": ancho_completo("SK-ANT-api03-ABCdef1234"),
    "con espacio ideográfico": ancho_completo("sk") + "　" + ancho_completo("-ant-") + "api03-ABCdef1234",
}


def hallazgo(
    archivo: str = "backend/cimenta/compras/aplicacion/crear_requisicion.py",
    linea: int | None = 42,
    texto: str = "La ruta se declara async def.",
    cita: str = "CLAUDE.md regla 11",
) -> dict[str, Any]:
    """Un hallazgo con la forma de la salida estructurada del modelo."""
    resultado: dict[str, Any] = {"archivo": archivo, "texto": texto, "cita": cita}
    if linea is not None:
        resultado["linea"] = linea
    return resultado


def como_hallazgos_json(hallazgos: list[dict[str, Any]]) -> str:
    return json.dumps({"hallazgos": hallazgos}, ensure_ascii=False)


class Resultado(NamedTuple):
    codigo: int
    registro: str
    comentario: str | None
    """`None` si `--salida` no se escribió."""

    @property
    def lineas_del_registro(self) -> list[str]:
        return self.registro.splitlines()


def correr(
    modulo: Any,
    hallazgos: list[dict[str, Any]] | None = None,
    *,
    texto_de_hallazgos: str | None = None,
    titulo: str = TITULO_CON_TICKET,
    cuerpo: str = "",
    archivos: list[str] | None = None,
    cabeza: str = SHA,
    sin_hallazgos_en_el_entorno: bool = False,
    sin_archivo_de_archivos: bool = False,
) -> Resultado:
    """Corre `modulo.main(argv, entorno)` en una carpeta temporal y devuelve código, registro y comentario escrito."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta_archivos = os.path.join(carpeta, "archivos.txt")
        ruta_salida = os.path.join(carpeta, "comentario.md")
        if not sin_archivo_de_archivos:
            with open(ruta_archivos, "w", encoding="utf-8", newline="") as archivo:
                archivo.write("".join(f"{nombre}\n" for nombre in (archivos or [])))
        entorno = {"TITULO": titulo, "CUERPO": cuerpo, "CABEZA": cabeza}
        if not sin_hallazgos_en_el_entorno:
            entorno["HALLAZGOS"] = (
                texto_de_hallazgos
                if texto_de_hallazgos is not None
                else como_hallazgos_json(hallazgos or [])
            )
        salida_estandar = io.StringIO()
        with contextlib.redirect_stdout(salida_estandar), contextlib.redirect_stderr(salida_estandar):
            codigo = modulo.main(["--archivos", ruta_archivos, "--salida", ruta_salida], entorno)
        comentario = None
        if os.path.exists(ruta_salida):
            with open(ruta_salida, encoding="utf-8", newline="") as archivo:
                comentario = archivo.read()
        return Resultado(codigo, salida_estandar.getvalue(), comentario)


def lineas_numeradas(comentario: str) -> list[str]:
    return [linea for linea in comentario.splitlines() if re.match(r"^\d+\. ", linea)]


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones por caso. Devuelven la lista de problemas; vacía si el módulo cumple. Las pruebas esperan [] sobre el
# módulo real y los mutantes esperan una lista no vacía sobre su copia.
# ---------------------------------------------------------------------------------------------------------


def problemas_tc62_21(modulo: Any) -> list[str]:
    """Citas válidas se publican; citas inválidas, no, ni en `separar_por_cita` ni en el comentario ni en el registro."""
    problemas: list[str] = []
    for cita in CITAS_VALIDAS:
        candidato = hallazgo(cita=cita)
        publicables, descartados = modulo.separar_por_cita([candidato])
        if publicables != [candidato] or descartados:
            problemas.append(f"cita válida descartada: {cita!r}")
    for cita in CITAS_INVALIDAS:
        candidato = hallazgo(cita=cita)
        publicables, descartados = modulo.separar_por_cita([candidato])
        if publicables or descartados != [candidato]:
            problemas.append(f"cita inválida publicada: {cita!r}")

    mezcla = [
        hallazgo(archivo=f"mal{numero}.py", linea=numero + 1, texto=f"TEXTO-INVALIDO-{numero}", cita=cita)
        for numero, cita in enumerate(CITAS_INVALIDAS)
    ]
    mezcla.append(hallazgo(archivo="bien.py", linea=3, texto="TEXTO-VALIDO", cita="RN-03"))
    # N002 b · el registro nombra el archivo solo si consta en `--archivos`: aquí constan todos.
    resultado = correr(modulo, mezcla, archivos=[candidato["archivo"] for candidato in mezcla])
    if resultado.codigo != 0 or resultado.comentario is None:
        problemas.append(f"main no escribió el comentario: código {resultado.codigo}")
        return problemas
    if "TEXTO-VALIDO" not in resultado.comentario:
        problemas.append("el hallazgo con cita válida falta en el comentario")
    for numero, cita in enumerate(CITAS_INVALIDAS):
        if f"TEXTO-INVALIDO-{numero}" in resultado.comentario:
            problemas.append(f"cita inválida publicada en el comentario: {cita!r}")
        linea_esperada = f"descartado sin cita: mal{numero}.py:{numero + 1}"
        if linea_esperada not in resultado.lineas_del_registro:
            problemas.append(f"falta en el registro la línea {linea_esperada!r}")
        if cita and cita in resultado.registro:
            problemas.append(f"el registro imprime la cita descartada: {cita!r}")
    if "TEXTO-INVALIDO" in resultado.registro:
        problemas.append("el registro imprime el texto de un hallazgo descartado")
    return problemas


def problemas_tc62_22(modulo: Any) -> list[str]:
    problemas: list[str] = []
    esperado = [{"archivo": "", "texto": TEXTO_SIN_TICKET, "cita": CITA_SIN_TICKET}]
    for titulo, cuerpo in (
        ("Arregla algo", "Sin referencia a ningún ticket."),
        ("", ""),
        ("TKT-62 con dos cifras", "tkt-062 en minúsculas"),
    ):
        if modulo.hallazgos_mecanicos(titulo, cuerpo, []) != esperado:
            problemas.append(f"sin ticket no devuelve el hallazgo del ticket: {titulo!r}")
    for titulo, cuerpo, donde in (
        ("Arregla algo", "Ver TKT-009a en el cuerpo", "ticket en el cuerpo"),
        ("TKT-062b · algo", "", "ticket en el título"),
        ("Cierra TKT-009a", "TKT-062b", "ticket en los dos"),
    ):
        if modulo.hallazgos_mecanicos(titulo, cuerpo, []) != []:
            problemas.append(f"con {donde} sigue diciendo que falta el ticket")

    resultado = correr(
        modulo,
        [hallazgo(texto="TEXTO-DEL-MODELO", cita="RN-03")],
        titulo="Arregla algo",
        cuerpo="Sin referencia a ningún ticket.",
    )
    if resultado.codigo != 0 or resultado.comentario is None:
        problemas.append(f"main sin ticket no escribió el comentario: código {resultado.codigo}")
        return problemas
    items = lineas_numeradas(resultado.comentario)
    if not items or "sin ticket no hay non-goals" not in items[0] or CITA_SIN_TICKET not in items[0]:
        problemas.append(f"el hallazgo 1 no es el de la falta de ticket: {items[:1]!r}")
    if len(items) != 2 or "TEXTO-DEL-MODELO" not in items[-1]:
        problemas.append(f"el hallazgo del modelo no va después del mecánico: {items!r}")

    con_ticket = correr(
        modulo,
        [hallazgo(texto="TEXTO-DEL-MODELO", cita="RN-03")],
        titulo="Arregla algo",
        cuerpo="Cuerpo que cita TKT-009a.",
    )
    if con_ticket.comentario is None or "sin ticket no hay non-goals" in con_ticket.comentario:
        problemas.append("con TKT-009a en el cuerpo el comentario sigue diciendo que falta el ticket")
    return problemas


def problemas_tc62_23(modulo: Any) -> list[str]:
    problemas: list[str] = []
    esperado = [{"archivo": CONTRATO, "texto": TEXTO_OPENAPI, "cita": CITA_OPENAPI}]
    if modulo.hallazgos_mecanicos(TITULO_CON_TICKET, "", ["README.md", CONTRATO]) != esperado:
        problemas.append("con el contrato entre los archivos no devuelve el hallazgo del contrato")
    for ruta in (f"{CONTRATO}.bak", f"{CONTRATO}/otro", f"x/{CONTRATO}", "docs/api/openapi.yml", "docs/api"):
        if modulo.hallazgos_mecanicos(TITULO_CON_TICKET, "", [ruta]) != []:
            problemas.append(f"una ruta que no es el contrato lo señala: {ruta!r}")

    senalado = correr(modulo, [], archivos=["README.md", CONTRATO])
    if senalado.comentario is None or CITA_OPENAPI not in senalado.comentario or "borrador OpenAPI" not in senalado.comentario:
        problemas.append("main no señala el cambio del contrato en el comentario")
    elif SIN_HALLAZGOS in senalado.comentario:
        problemas.append("el comentario dice «Sin hallazgos» aunque el PR toca el contrato")
    for ruta in (f"{CONTRATO}.bak", f"{CONTRATO}/otro"):
        otro = correr(modulo, [], archivos=[ruta])
        if otro.comentario is None or "borrador OpenAPI" in otro.comentario:
            problemas.append(f"main señala el contrato por la ruta {ruta!r}")
        elif SIN_HALLAZGOS not in otro.comentario:
            problemas.append(f"con la ruta {ruta!r} y ningún otro hallazgo falta «Sin hallazgos»")
    return problemas


def problemas_registro_neutralizado(modulo: Any) -> list[str]:
    problemas: list[str] = []
    neutralizado = modulo._para_el_registro("a\r\n::add-mask::x")
    if neutralizado != "a  : :add-mask: :x":
        problemas.append(f"_para_el_registro no neutraliza saltos y dos puntos dobles: {neutralizado!r}")
    # N002 b · un archivo que consta en `--archivos` se imprime, y entonces el registro lo neutraliza. Un nombre con salto de
    # línea no puede constar (la lista es de una línea por nombre): el registro lo omite y sigue siendo una sola línea.
    resultado = correr(
        modulo,
        [
            hallazgo(archivo="src/a::set-output name=x::y.py", linea=42, texto="TEXTO-X", cita="buenas prácticas"),
            hallazgo(archivo="src/b.py\n::set-output name=x::y", linea=43, texto="TEXTO-Y", cita="buenas prácticas"),
        ],
        archivos=["src/a::set-output name=x::y.py"],
    )
    if resultado.codigo != 0:
        problemas.append(f"main terminó en {resultado.codigo}")
    if "::" in resultado.registro:
        problemas.append("el registro contiene dos puntos dobles: puede formar un comando de flujo")
    descartados = [linea for linea in resultado.lineas_del_registro if linea.startswith("descartado")]
    esperado = [
        "descartado sin cita: src/a: :set-output name=x: :y.py:42",
        "descartado sin cita: [archivo omitido]:43",
    ]
    if descartados != esperado:
        problemas.append(f"el descartado no sale como una sola línea neutralizada: {descartados!r}")
    return problemas


def problemas_tc62_42(modulo: Any) -> list[str]:
    problemas: list[str] = []
    texto_con_clave = f"Se usa la clave {CLAVE_DE_EJEMPLO} en el código."
    en_texto = hallazgo(archivo="a.py", linea=7, texto=texto_con_clave, cita="CLAUDE.md regla 11")
    en_cita = hallazgo(archivo="b.py", linea=8, texto="TEXTO-B", cita=f"CLAUDE.md regla 11 {CLAVE_DE_EJEMPLO}")
    en_archivo = hallazgo(archivo=f"{CLAVE_DE_EJEMPLO}.py", linea=9, texto="TEXTO-C", cita="CLAUDE.md regla 11")
    sana = hallazgo(archivo="s.py", linea=1, texto="TEXTO-SANO", cita="CLAUDE.md regla 11")
    for descripcion, candidato in (("texto", en_texto), ("cita", en_cita), ("archivo", en_archivo)):
        publicables, descartados = modulo.separar_por_cita([candidato, sana])
        if publicables != [sana] or descartados != [candidato]:
            problemas.append(f"la clave en el {descripcion} no descarta el hallazgo")

    if modulo.CLAVE_EXPUESTA.search(CLAVE_DE_EJEMPLO) is None:
        problemas.append("CLAVE_EXPUESTA no casa con una clave de ejemplo")

    # F002 · Una clave en `archivo` se descarta del comentario y el registro no imprime el `archivo`: da su lugar en
    # `[archivo omitido]:<linea>`. Ningún dato del registro contiene la clave ni su versión ofuscada.
    solo_archivo = correr(modulo, [en_archivo, sana])
    if solo_archivo.comentario is None or "sk-ant-" in solo_archivo.comentario:
        problemas.append("el comentario publica una clave que venía en el archivo")
    if "descartado por contener una clave: [archivo omitido]:9" not in solo_archivo.lineas_del_registro:
        problemas.append(
            "con la clave en el archivo el registro no imprime «descartado por contener una clave: [archivo omitido]:9»: "
            f"{solo_archivo.lineas_del_registro!r}"
        )
    for fragmento in (CLAVE_DE_EJEMPLO, "sk-ant-", ".py"):
        if fragmento in solo_archivo.registro:
            problemas.append(f"con la clave en el archivo el registro imprime parte de él: {fragmento!r}")
    if "skant" in normalizado(solo_archivo.registro):
        problemas.append("con la clave en el archivo el registro imprime la clave ofuscada")
    resultado = correr(modulo, [en_texto, en_cita, sana])
    if resultado.codigo != 0 or resultado.comentario is None:
        problemas.append(f"main no escribió el comentario: código {resultado.codigo}")
        return problemas
    if "sk-ant-" in resultado.comentario:
        problemas.append("el comentario publica una clave")
    if "TEXTO-SANO" not in resultado.comentario:
        problemas.append("el hallazgo sin clave falta en el comentario")
    # N002 a · con una clave en cualquier campo el registro nunca imprime el archivo.
    if "descartado por contener una clave: [archivo omitido]:7" not in resultado.lineas_del_registro:
        problemas.append("el registro no dice «descartado por contener una clave» para el hallazgo del texto")
    if "descartado por contener una clave: [archivo omitido]:8" not in resultado.lineas_del_registro:
        problemas.append("el registro no dice «descartado por contener una clave» para el hallazgo de la cita")
    for fragmento in ("a.py", "b.py"):
        if fragmento in resultado.registro:
            problemas.append(f"con la clave en el texto o la cita el registro imprime el archivo: {fragmento!r}")
    # La clave en el texto y la cita inválida a la vez: la razón es la clave, que se comprueba primero.
    doble = correr(modulo, [hallazgo(archivo="c.py", linea=5, texto=texto_con_clave, cita="buenas prácticas")])
    if "descartado por contener una clave: [archivo omitido]:5" not in doble.lineas_del_registro:
        problemas.append("con cita inválida y clave a la vez, el registro no da la clave como razón")
    for fragmento in (CLAVE_DE_EJEMPLO, "sk-ant-", "Se usa la clave", "CLAUDE.md regla 11"):
        if fragmento in resultado.registro or fragmento in doble.registro:
            problemas.append(f"el registro imprime parte del texto o de la cita: {fragmento!r}")
    return problemas


def problemas_tc62_42_clave_ofuscada(modulo: Any) -> list[str]:
    """F001 (c) · Una clave con separadores, guiones bajos, mayúsculas o partida entre campos no se publica, el registro da la
    razón «por contener una clave» y nada de lo impreso contiene `sk-ant-` ni `skant` una vez normalizado."""
    problemas: list[str] = []
    sana = hallazgo(archivo="s.py", linea=1, texto="TEXTO-SANO", cita="CLAUDE.md regla 11")

    casos: list[tuple[str, dict[str, Any], str]] = []
    for nombre, clave in CLAVES_OFUSCADAS.items():
        casos += [
            (
                f"{nombre} en el texto",
                hallazgo(archivo="o.py", linea=3, texto=f"Se pasa {clave} al registro.", cita="RN-03"),
                "descartado por contener una clave: [archivo omitido]:3",
            ),
            (
                f"{nombre} en el archivo",
                hallazgo(archivo=f"{clave}.py", linea=4, texto="TEXTO-ARCHIVO", cita="RN-03"),
                "descartado por contener una clave: [archivo omitido]:4",
            ),
            (
                f"{nombre} en la cita",
                hallazgo(archivo="o.py", linea=5, texto="TEXTO-CITA", cita=f"RN-03 {clave}"),
                "descartado por contener una clave: [archivo omitido]:5",
            ),
        ]
    for nombre, campos in CLAVES_PARTIDAS.items():
        casos.append(
            (
                f"partida entre {nombre}",
                hallazgo(linea=6, **campos),
                "descartado por contener una clave: [archivo omitido]:6",
            )
        )

    for descripcion, candidato, linea_esperada in casos:
        publicables, descartados = modulo.separar_por_cita([candidato, sana])
        if publicables != [sana] or descartados != [candidato]:
            problemas.append(f"la clave ofuscada {descripcion} no descarta el hallazgo")
            continue
        resultado = correr(modulo, [candidato, sana])
        if resultado.codigo != 0 or resultado.comentario is None:
            problemas.append(f"la clave ofuscada {descripcion}: main no escribió el comentario, código {resultado.codigo}")
            continue
        if "TEXTO-SANO" not in resultado.comentario:
            problemas.append(f"la clave ofuscada {descripcion}: el hallazgo sin clave falta en el comentario")
        if "skant" in normalizado(resultado.comentario):
            problemas.append(f"la clave ofuscada {descripcion} llega al comentario")
        if "skant" in normalizado(resultado.registro) or "sk-ant-" in resultado.registro:
            problemas.append(f"la clave ofuscada {descripcion} llega al registro")
        if linea_esperada not in resultado.lineas_del_registro:
            problemas.append(
                f"la clave ofuscada {descripcion}: el registro no dice «{linea_esperada}»: {resultado.lineas_del_registro!r}"
            )
    return problemas


def problemas_tc62_42_ancho_completo(modulo: Any) -> list[str]:
    """N001 · Una clave en ancho completo (`ｓｋ－ａｎｔ－api03…`) en el texto, la cita, el archivo o partida entre campos no se
    publica, el registro da la razón «por contener una clave» y nada de lo impreso contiene `sk-ant-` ni `skant` en NFKC."""
    problemas: list[str] = []
    sana = hallazgo(archivo="s.py", linea=1, texto="TEXTO-SANO", cita="CLAUDE.md regla 11")

    casos: list[tuple[str, dict[str, Any]]] = []
    for nombre, clave in CLAVES_ANCHO_COMPLETO.items():
        casos += [
            (f"{nombre} en el texto", hallazgo(archivo="w.py", linea=3, texto=f"Se pasa {clave} al registro.", cita="RN-03")),
            (f"{nombre} en el archivo", hallazgo(archivo=f"{clave}.py", linea=3, texto="TEXTO-ARCHIVO", cita="RN-03")),
            (f"{nombre} en la cita", hallazgo(archivo="w.py", linea=3, texto="TEXTO-CITA", cita=f"RN-03 {clave}")),
        ]
    casos.append(
        (
            "partida entre archivo y texto",
            hallazgo(archivo="src/" + ancho_completo("sk-"), linea=3, texto=ancho_completo("ant-") + "api03-ABCdef1234", cita="RN-03"),
        )
    )

    for descripcion, candidato in casos:
        publicables, descartados = modulo.separar_por_cita([candidato, sana])
        if publicables != [sana] or descartados != [candidato]:
            problemas.append(f"la clave {descripcion} no descarta el hallazgo")
            continue
        resultado = correr(modulo, [candidato, sana])
        if resultado.codigo != 0 or resultado.comentario is None:
            problemas.append(f"la clave {descripcion}: main no escribió el comentario, código {resultado.codigo}")
            continue
        if "TEXTO-SANO" not in resultado.comentario:
            problemas.append(f"la clave {descripcion}: el hallazgo sin clave falta en el comentario")
        if "skant" in normalizado(resultado.comentario):
            problemas.append(f"la clave {descripcion} llega al comentario")
        if "skant" in normalizado(resultado.registro):
            problemas.append(f"la clave {descripcion} llega al registro")
        esperada = "descartado por contener una clave: [archivo omitido]:3"
        if resultado.lineas_del_registro != [esperada]:
            problemas.append(
                f"la clave {descripcion}: el registro no dice «{esperada}»: {resultado.lineas_del_registro!r}"
            )
    return problemas


def problemas_normalizar_aplica_nfkc(modulo: Any) -> list[str]:
    """N001 · `_normalizar` lleva el ancho completo a ASCII antes de pasar a minúsculas y de quitar lo que no es alfanumérico."""
    problemas: list[str] = []
    for texto, esperado in (
        (ancho_completo("sk-ant-"), "skant"),
        (ancho_completo("SK-ANT-"), "skant"),
        (ancho_completo("ABC_123"), "abc123"),
        (ancho_completo("s") + "　" + "k", "sk"),
        ("sk-ant-", "skant"),
    ):
        obtenido = modulo._normalizar(texto)
        if obtenido != esperado:
            problemas.append(f"_normalizar({texto!r}) devolvió {obtenido!r} en lugar de {esperado!r}")
    return problemas


# N002 · qué ubicación imprime el registro. Cada caso: (nombre, hallazgo, archivos de --archivos, línea esperada, texto que no
# puede aparecer en el registro). La línea del registro sustituye el archivo por `[archivo omitido]` sin quitar la línea.
CASOS_DEL_REGISTRO_CON_CLAVE: tuple[tuple[str, dict[str, Any], list[str], str, str], ...] = (
    (
        "clave con el cuerpo en el archivo y sk-ant- en el texto",
        hallazgo(archivo="api03-ABCdef1234.py", linea=11, texto="La clave empieza en sk-ant-", cita="RN-03"),
        ["api03-ABCdef1234.py"],
        "descartado por contener una clave: [archivo omitido]:11",
        "api03",
    ),
    (
        "clave con el cuerpo en el archivo y sk-ant- en la cita",
        hallazgo(archivo="api03-ABCdef1235.py", linea=12, texto="TEXTO-D", cita="RN-03 sk-ant-"),
        ["api03-ABCdef1235.py"],
        "descartado por contener una clave: [archivo omitido]:12",
        "api03",
    ),
    (
        "clave en el texto con el archivo listado",
        hallazgo(archivo="listado.py", linea=13, texto=f"clave {CLAVE_DE_EJEMPLO}", cita="RN-03"),
        ["README.md", "listado.py"],
        "descartado por contener una clave: [archivo omitido]:13",
        "listado.py",
    ),
    (
        "clave en el texto sin línea",
        hallazgo(archivo="listado.py", linea=None, texto=f"clave {CLAVE_DE_EJEMPLO}", cita="RN-03"),
        ["listado.py"],
        "descartado por contener una clave: [archivo omitido]",
        "listado.py",
    ),
)

CASOS_DEL_REGISTRO_SIN_CITA: tuple[tuple[str, dict[str, Any], list[str], str, str], ...] = (
    (
        "cita inválida con el archivo listado",
        hallazgo(archivo="src/listado.py", linea=21, texto="TEXTO-E", cita="buenas prácticas"),
        ["README.md", "src/listado.py"],
        "descartado sin cita: src/listado.py:21",
        "[archivo omitido]",
    ),
    (
        "cita inválida con el archivo listado y sin línea",
        hallazgo(archivo="src/listado.py", linea=None, texto="TEXTO-F", cita="buenas prácticas"),
        ["src/listado.py"],
        "descartado sin cita: src/listado.py",
        "[archivo omitido]",
    ),
    (
        "cita inválida con un archivo ajeno a la lista",
        hallazgo(archivo="src/ajeno.py", linea=22, texto="TEXTO-G", cita="buenas prácticas"),
        ["README.md", "src/listado.py"],
        "descartado sin cita: [archivo omitido]:22",
        "ajeno",
    ),
    (
        "cita inválida con un archivo ajeno a la lista y sin línea",
        hallazgo(archivo="src/ajeno.py", linea=None, texto="TEXTO-H", cita="buenas prácticas"),
        ["src/listado.py"],
        "descartado sin cita: [archivo omitido]",
        "ajeno",
    ),
    (
        "cita inválida con la lista vacía",
        hallazgo(archivo="src/ajeno.py", linea=23, texto="TEXTO-I", cita="RN-99"),
        [],
        "descartado sin cita: [archivo omitido]:23",
        "ajeno",
    ),
    (
        "cita inválida con un archivo contenido en uno de la lista",
        hallazgo(archivo="listado.py", linea=24, texto="TEXTO-J", cita="buenas prácticas"),
        ["src/listado.py"],
        "descartado sin cita: [archivo omitido]:24",
        "listado.py",
    ),
    (
        "cita inválida con un archivo que contiene a uno de la lista",
        hallazgo(archivo="src/listado.py.bak", linea=25, texto="TEXTO-K", cita="buenas prácticas"),
        ["src/listado.py"],
        "descartado sin cita: [archivo omitido]:25",
        "listado.py.bak",
    ),
)


def _problemas_del_registro(
    modulo: Any, casos: tuple[tuple[str, dict[str, Any], list[str], str, str], ...]
) -> list[str]:
    problemas: list[str] = []
    for nombre, candidato, archivos, esperada, prohibido in casos:
        resultado = correr(modulo, [candidato], archivos=archivos)
        if resultado.codigo != 0:
            problemas.append(f"{nombre}: main terminó en {resultado.codigo}")
            continue
        if resultado.lineas_del_registro != [esperada]:
            problemas.append(f"{nombre}: el registro no dice «{esperada}»: {resultado.lineas_del_registro!r}")
        if prohibido in resultado.registro:
            problemas.append(f"{nombre}: el registro imprime {prohibido!r}")
    return problemas


def problemas_n002_registro_con_clave(modulo: Any) -> list[str]:
    """N002 a · descartado por clave, el registro imprime siempre `[archivo omitido]:<linea>`."""
    return _problemas_del_registro(modulo, CASOS_DEL_REGISTRO_CON_CLAVE)


def problemas_n002_registro_sin_cita(modulo: Any) -> list[str]:
    """N002 b · descartado por cita inválida, el registro imprime el archivo solo si consta en `--archivos`."""
    return _problemas_del_registro(modulo, CASOS_DEL_REGISTRO_SIN_CITA)


# ---------------------------------------------------------------------------------------------------------
# Carga del módulo
# ---------------------------------------------------------------------------------------------------------


class PruebaBase(unittest.TestCase):
    """Importa el módulo bajo prueba en cada caso, para que un módulo ausente rompa cada caso por separado."""

    def publicar(self) -> Any:
        try:
            return importlib.import_module("publicar_revision")
        except ModuleNotFoundError as error:
            if error.name != "publicar_revision":
                raise
            self.fail("falta tools/publicar_revision.py: el módulo bajo prueba todavía no existe")

    def copia_privada(self) -> Any:
        """Una carga aparte del mismo archivo, para mutarla sin tocar el módulo que usan las demás pruebas."""
        if not os.path.exists(GUION):
            self.fail("falta tools/publicar_revision.py: el módulo bajo prueba todavía no existe")
        nombre = "publicar_revision_mutante"
        especificacion = importlib.util.spec_from_file_location(nombre, GUION)
        assert especificacion is not None and especificacion.loader is not None
        copia = importlib.util.module_from_spec(especificacion)
        sys.modules[nombre] = copia
        try:
            especificacion.loader.exec_module(copia)
        finally:
            del sys.modules[nombre]
        return copia


class PruebasDelFiltroDeLaRevision(PruebaBase):
    # --- TC62-20 · feliz ---------------------------------------------------------------------------------

    def test_tkt062_ca05_esc01_hallazgo_con_cita_se_publica(self) -> None:
        """TKT-062 CA-5 esc. 1 — un hallazgo con cita de la lista se publica con su `archivo:linea`, su texto y su cita."""
        modulo = self.publicar()
        candidato = hallazgo(
            archivo="backend/cimenta/compras/aplicacion/crear_requisicion.py",
            linea=42,
            texto="La ruta se declara async def.",
            cita="CLAUDE.md regla 11",
        )
        self.assertEqual(modulo.separar_por_cita([candidato]), ([candidato], []))
        resultado = correr(modulo, [candidato])
        self.assertEqual(resultado.codigo, 0, resultado.registro)
        self.assertIsNotNone(resultado.comentario)
        comentario = resultado.comentario or ""
        self.assertEqual(
            lineas_numeradas(comentario),
            [
                "1. `backend/cimenta/compras/aplicacion/crear_requisicion.py:42` — La ruta se declara async def. "
                "— *Cita:* CLAUDE.md regla 11"
            ],
        )
        self.assertNotIn(SIN_HALLAZGOS, comentario)
        self.assertEqual(resultado.lineas_del_registro, [])

    # --- TC62-21 · rechazo: cita inválida ----------------------------------------------------------------

    def test_tkt062_ca05_esc02_hallazgo_sin_cita_valida_no_se_publica(self) -> None:
        """TKT-062 CA-5 esc. 2 — citas vacías, genéricas o fuera de rango no se publican y el registro nombra `archivo:linea` sin su texto ni su cita."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_21(modulo), [])

    def test_tkt062_ca05_esc02_si_todo_se_descarta_el_comentario_dice_que_no_hay_hallazgos(self) -> None:
        """TKT-062 CA-5 esc. 2 — con todos los hallazgos descartados y ningún mecánico, el comentario dice «Sin hallazgos…» y conserva el cierre."""
        modulo = self.publicar()
        resultado = correr(modulo, [hallazgo(cita="buenas prácticas", texto="TEXTO-DESCARTADO")])
        self.assertEqual(resultado.codigo, 0, resultado.registro)
        comentario = resultado.comentario or ""
        self.assertIn(SIN_HALLAZGOS, comentario)
        self.assertNotIn("TEXTO-DESCARTADO", comentario)
        self.assertEqual(lineas_numeradas(comentario), [])
        self.assertIn(CIERRE, comentario)

    # --- TC62-22 · rechazo: PR sin ticket ----------------------------------------------------------------

    def test_tkt062_ca05_esc03_pr_sin_ticket_es_el_primer_hallazgo(self) -> None:
        """TKT-062 CA-5 esc. 3 — sin `TKT-` en título ni cuerpo, el hallazgo 1 dice que falta el ticket y que sin él no hay non-goals; con `TKT-009a` en el cuerpo no aparece."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_22(modulo), [])

    # --- TC62-23 · feliz y borde: el contrato ------------------------------------------------------------

    def test_tkt062_ca05_esc04_pr_que_toca_openapi_se_senala_siempre(self) -> None:
        """TKT-062 CA-5 esc. 4 — con `docs/api/openapi.yaml` entre los archivos y ningún otro hallazgo el comentario lo señala; `docs/api/openapi.yaml.bak` no."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_23(modulo), [])

    def test_tkt062_ca05_esc04_el_hallazgo_mecanico_del_contrato_lleva_su_cita_y_va_antes_que_los_del_modelo(self) -> None:
        """TKT-062 CA-5 esc. 4 — el hallazgo del contrato lleva su cita de convenciones §12 y va antes que los del modelo; el del ticket, antes que el del contrato."""
        modulo = self.publicar()
        self.assertEqual(
            modulo.hallazgos_mecanicos("Sin referencia", "ni en el cuerpo", [CONTRATO]),
            [
                {"archivo": "", "texto": TEXTO_SIN_TICKET, "cita": CITA_SIN_TICKET},
                {"archivo": CONTRATO, "texto": TEXTO_OPENAPI, "cita": CITA_OPENAPI},
            ],
        )
        resultado = correr(
            modulo,
            [hallazgo(texto="TEXTO-DEL-MODELO", cita="RN-03")],
            titulo="Sin referencia",
            archivos=[CONTRATO],
        )
        items = lineas_numeradas(resultado.comentario or "")
        self.assertEqual(len(items), 3, resultado.comentario)
        self.assertIn("sin ticket no hay non-goals", items[0])
        self.assertIn("borrador OpenAPI", items[1])
        self.assertIn("TEXTO-DEL-MODELO", items[2])

    # --- TC62-24 · rechazo: salida inválida del modelo ---------------------------------------------------

    def test_tkt062_ca05_esc02_salida_invalida_del_modelo_no_publica_nada(self) -> None:
        """TKT-062 CA-5 esc. 2 — `HALLAZGOS` vacío, que no es JSON o sin `hallazgos` termina en 2 con `::error::` y `--salida` no se escribe."""
        modulo = self.publicar()
        entradas = {
            "vacío": "",
            "solo espacios": "   ",
            "no es JSON": "no-json",
            "lista JSON en vez de objeto": "[]",
            "objeto sin hallazgos": '{"otro": []}',
            "hallazgos que no es lista": '{"hallazgos": "x"}',
            "hallazgo que no es objeto": '{"hallazgos": ["x"]}',
            "hallazgo sin cita": '{"hallazgos": [{"archivo": "a", "texto": "t"}]}',
            "hallazgo sin texto": '{"hallazgos": [{"archivo": "a", "cita": "RN-03"}]}',
            "hallazgo sin archivo": '{"hallazgos": [{"texto": "t", "cita": "RN-03"}]}',
            "cita que no es cadena": '{"hallazgos": [{"archivo": "a", "texto": "t", "cita": 3}]}',
            "línea que no es entero": '{"hallazgos": [{"archivo": "a", "texto": "t", "cita": "RN-03", "linea": "9"}]}',
            "JSON truncado": '{"hallazgos": [',
        }
        for descripcion, texto in entradas.items():
            with self.subTest(entrada=descripcion):
                resultado = correr(modulo, texto_de_hallazgos=texto)
                self.assertEqual(resultado.codigo, 2, resultado.registro)
                self.assertIsNone(resultado.comentario, "main escribió --salida con una entrada inválida")
                self.assertIn("::error::", resultado.registro)

    def test_tkt062_ca05_esc02_sin_la_variable_hallazgos_termina_en_2_y_no_escribe_la_salida(self) -> None:
        """TKT-062 CA-5 esc. 2 — sin `HALLAZGOS` en el entorno el filtro falla cerrado con 2 y no escribe `--salida`."""
        modulo = self.publicar()
        resultado = correr(modulo, sin_hallazgos_en_el_entorno=True)
        self.assertEqual(resultado.codigo, 2, resultado.registro)
        self.assertIsNone(resultado.comentario)
        self.assertIn("::error::", resultado.registro)

    def test_tkt062_ca05_esc02_sin_el_archivo_de_archivos_termina_en_2_y_no_escribe_la_salida(self) -> None:
        """TKT-062 CA-5 esc. 2 — si falta el archivo de `--archivos` el filtro falla cerrado con 2 y no escribe `--salida`."""
        modulo = self.publicar()
        resultado = correr(modulo, [hallazgo()], sin_archivo_de_archivos=True)
        self.assertEqual(resultado.codigo, 2, resultado.registro)
        self.assertIsNone(resultado.comentario)
        self.assertIn("::error::", resultado.registro)

    def test_tkt062_ca05_esc02_el_error_de_entrada_no_repite_el_contenido_de_hallazgos(self) -> None:
        """TKT-062 CA-5 esc. 2 — el `::error::` de una entrada inválida da el motivo sin repetir lo que venía en `HALLAZGOS`."""
        modulo = self.publicar()
        resultado = correr(modulo, texto_de_hallazgos=f"esto no es JSON {CLAVE_DE_EJEMPLO}")
        self.assertEqual(resultado.codigo, 2, resultado.registro)
        self.assertIsNone(resultado.comentario)
        self.assertIn("::error::", resultado.registro)
        self.assertNotIn("sk-ant-", resultado.registro)

    def test_tkt062_ca05_esc02_leer_hallazgos_lanza_value_error_con_entrada_invalida(self) -> None:
        """TKT-062 CA-5 esc. 2 — `leer_hallazgos` lanza `ValueError` con texto vacío, no JSON o sin la lista, y devuelve los hallazgos en otro caso."""
        modulo = self.publicar()
        for texto in ("", "no-json", "[]", '{"otro": []}', '{"hallazgos": [{"archivo": "a"}]}'):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                modulo.leer_hallazgos(texto)
        valido = hallazgo()
        self.assertEqual(modulo.leer_hallazgos(como_hallazgos_json([valido])), [valido])
        self.assertEqual(modulo.leer_hallazgos('{"hallazgos": []}'), [])

    def test_tkt062_ca05_esc02_una_lista_vacia_de_hallazgos_es_valida(self) -> None:
        """TKT-062 CA-5 esc. 2 — `{"hallazgos": []}` es una salida válida: termina en 0 y escribe el comentario de «Sin hallazgos…»."""
        modulo = self.publicar()
        resultado = correr(modulo, [])
        self.assertEqual(resultado.codigo, 0, resultado.registro)
        self.assertIn(SIN_HALLAZGOS, resultado.comentario or "")

    # --- TC62-25 · feliz y borde: cabecera, tope y registro ----------------------------------------------

    def test_tkt062_ca05_esc01_un_comentario_con_cabecera_tope_y_registro_neutralizado(self) -> None:
        """TKT-062 CA-5 esc. 1 — encabezado con los 7 primeros del SHA, «Sin hallazgos…» sin ninguno, corte por `TOPE` con la nota de los que faltan y un `archivo` con `\\n::set-output` impreso como una sola línea sin `::`."""
        modulo = self.publicar()
        # Encabezado y cierre.
        vacio = correr(modulo, [])
        comentario = vacio.comentario or ""
        self.assertEqual(comentario.splitlines()[0], ENCABEZADO)
        self.assertIn("Commit revisado: `abcdef1`", comentario)
        self.assertNotIn("abcdef12", comentario)
        self.assertIn(SIN_HALLAZGOS, comentario)
        self.assertTrue(comentario.rstrip().endswith(CIERRE), comentario)
        # Con hallazgos no aparece «Sin hallazgos».
        con_uno = correr(modulo, [hallazgo()])
        self.assertNotIn(SIN_HALLAZGOS, con_uno.comentario or "")
        self.assertIn(CIERRE, con_uno.comentario or "")
        # Un hallazgo sin archivo no lleva `archivo:linea`.
        sin_archivo = modulo.componer_comentario(
            [{"archivo": "", "texto": "TEXTO-MECANICO", "cita": CITA_SIN_TICKET}], [], SHA
        )
        items = lineas_numeradas(sin_archivo)
        self.assertEqual(len(items), 1)
        self.assertNotIn("``", items[0])
        self.assertIn("TEXTO-MECANICO", items[0])
        self.assertIn(f"*Cita:* {CITA_SIN_TICKET}", items[0])
        # Registro neutralizado.
        self.assertEqual(problemas_registro_neutralizado(modulo), [])

    def test_tkt062_ca05_esc01_el_comentario_largo_se_corta_en_el_tope_con_la_nota_de_los_que_faltan(self) -> None:
        """TKT-062 CA-5 esc. 1 — pasado el `TOPE`, el comentario se corta en el último hallazgo que cabe, añade cuántos faltan y conserva el cierre."""
        modulo = self.publicar()
        self.assertEqual(modulo.TOPE, 60000)
        total = 100
        publicables = [
            hallazgo(archivo="a.py", linea=numero + 1, texto=f"hallazgo-{numero:04d} " + "x" * 1000, cita="RN-03")
            for numero in range(total)
        ]
        comentario = modulo.componer_comentario([], publicables, SHA)
        self.assertLessEqual(len(comentario), 65536, "el comentario no cabe en el límite de GitHub")
        incluidos = len(lineas_numeradas(comentario))
        self.assertGreater(incluidos, 0)
        self.assertLess(incluidos, total)
        nota = re.search(r"\((\d+) hallazgos más no caben en el comentario: ver el registro del trabajo\)", comentario)
        self.assertIsNotNone(nota, comentario[-400:])
        assert nota is not None
        self.assertEqual(int(nota.group(1)), total - incluidos)
        # Se incluyen los primeros, en orden, y ninguno del resto.
        self.assertIn(f"hallazgo-{incluidos - 1:04d}", comentario)
        self.assertNotIn(f"hallazgo-{incluidos:04d}", comentario)
        self.assertIn(CIERRE, comentario)

    def test_tkt062_ca05_esc01_un_comentario_corto_no_lleva_la_nota_de_corte(self) -> None:
        """TKT-062 CA-5 esc. 1 — bajo el `TOPE` el comentario incluye todos los hallazgos y no lleva la nota de los que no caben."""
        modulo = self.publicar()
        publicables = [hallazgo(linea=numero + 1, texto=f"hallazgo-{numero}", cita="RN-03") for numero in range(5)]
        comentario = modulo.componer_comentario([], publicables, SHA)
        self.assertEqual(len(lineas_numeradas(comentario)), 5)
        self.assertNotIn("no caben en el comentario", comentario)

    def test_tkt062_ca05_esc01_para_el_registro_sustituye_saltos_y_dos_puntos_dobles(self) -> None:
        """TKT-062 CA-5 esc. 1 — `_para_el_registro` cambia `\\r` y `\\n` por un espacio y `::` por `: :`."""
        modulo = self.publicar()
        self.assertEqual(modulo._para_el_registro("a\nb"), "a b")
        self.assertEqual(modulo._para_el_registro("a\r\nb"), "a  b")
        self.assertEqual(modulo._para_el_registro("::set-output name=x::y"), ": :set-output name=x: :y")
        self.assertEqual(modulo._para_el_registro("src/a.py"), "src/a.py")

    # --- TC62-42 · rechazo: clave de API -----------------------------------------------------------------

    def test_tkt062_ca07_esc03_un_hallazgo_con_una_clave_no_se_publica(self) -> None:
        """TKT-062 CA-7 esc. 3 · RNF-07 — un hallazgo con cita válida y un `sk-ant-` seguido de veinte caracteres no se publica, y el registro dice «descartado por contener una clave» sin imprimir el texto."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_42(modulo), [])

    def test_tkt062_ca07_esc03_la_clave_exige_al_menos_diez_caracteres_tras_el_prefijo(self) -> None:
        """TKT-062 CA-7 esc. 3 · F001 c — `CLAVE_EXPUESTA` sigue exigiendo diez caracteres tras `sk-ant-`: con nueve no casa y con diez sí. El
        filtro, en cambio, descarta ambos hallazgos: el de nueve deja `skant` al quitar lo que no es alfanumérico, y esa comprobación no pide
        longitud."""
        modulo = self.publicar()
        casi = hallazgo(texto="Menciona sk-ant-abcdefghi sin más.", cita="RN-03")
        clave = hallazgo(texto="Menciona sk-ant-abcdefghij sin más.", cita="RN-03")
        self.assertEqual(modulo.separar_por_cita([casi]), ([], [casi]))
        self.assertEqual(modulo.separar_por_cita([clave]), ([], [clave]))
        self.assertIsNone(modulo.CLAVE_EXPUESTA.search("sk-ant-abcdefghi"))
        self.assertIsNotNone(modulo.CLAVE_EXPUESTA.search("sk-ant-abcdefghij"))
        self.assertIsNotNone(modulo.CLAVE_EXPUESTA.search("sk-ant-api03-ABCdef_123-xyz"))

    def test_tkt062_ca07_esc03_una_clave_ofuscada_no_se_publica_ni_se_imprime(self) -> None:
        """TKT-062 CA-7 esc. 3 · F001 c — `s k - a n t - a p i 0 3 - …`, con guiones bajos, en mayúsculas, con otros signos o partida entre
        `archivo` y `texto` o entre `texto` y `cita` no se publica; el registro dice «por contener una clave» y no imprime `sk-ant-` ni su
        versión ofuscada."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_42_clave_ofuscada(modulo), [])

    def test_tkt062_ca07_esc03_con_una_clave_el_registro_omite_el_archivo_en_todos_los_casos(self) -> None:
        """TKT-062 CA-7 esc. 3 · F002 y N002 a — con la clave en `archivo` o en el texto, el registro imprime `[archivo omitido]:<linea>` y no el
        archivo, conste o no en `--archivos`."""
        modulo = self.publicar()
        en_archivo = hallazgo(archivo=f"{CLAVE_DE_EJEMPLO}.py", linea=9, texto="TEXTO-C", cita="CLAUDE.md regla 11")
        en_texto = hallazgo(archivo="a.py", linea=7, texto=f"clave {CLAVE_DE_EJEMPLO}", cita="CLAUDE.md regla 11")
        resultado = correr(modulo, [en_archivo, en_texto], archivos=["a.py"])
        self.assertEqual(resultado.codigo, 0, resultado.registro)
        self.assertEqual(
            resultado.lineas_del_registro,
            [
                "descartado por contener una clave: [archivo omitido]:9",
                "descartado por contener una clave: [archivo omitido]:7",
            ],
        )
        self.assertNotIn("sk-ant-", resultado.registro)
        self.assertNotIn("a.py", resultado.registro)

    def test_tkt062_ca07_esc03_con_el_cuerpo_de_la_clave_en_el_archivo_y_el_prefijo_en_otro_campo_el_registro_omite_el_archivo(
        self,
    ) -> None:
        """TKT-062 CA-7 esc. 3 · N002 a — la clave no es detectable en `archivo` solo (su cuerpo en `archivo` y `sk-ant-` en el texto o la cita):
        el descarte es por clave y el registro imprime `[archivo omitido]:<linea>`; con el archivo en `--archivos` también, y sin línea no lleva `:<linea>`."""
        modulo = self.publicar()
        self.assertEqual(problemas_n002_registro_con_clave(modulo), [])

    def test_tkt062_ca05_esc02_con_una_cita_invalida_el_registro_imprime_el_archivo_solo_si_consta_en_la_lista(self) -> None:
        """TKT-062 CA-5 esc. 2 · N002 b — descartado por cita inválida, el registro imprime `archivo:linea` si el archivo figura con ese nombre exacto
        en `--archivos`; si no figura (ajeno, lista vacía, subcadena de uno de la lista o que contiene a uno), imprime `[archivo omitido]:<linea>`."""
        modulo = self.publicar()
        self.assertEqual(problemas_n002_registro_sin_cita(modulo), [])

    def test_tkt062_ca07_esc03_una_clave_en_ancho_completo_no_se_publica_ni_se_imprime(self) -> None:
        """TKT-062 CA-7 esc. 3 · N001 — `ｓｋ－ａｎｔ－api03…` en el texto, la cita o el archivo, o partida entre campos, no se publica; el registro
        dice «por contener una clave» y no imprime la clave ni su versión normalizada."""
        modulo = self.publicar()
        self.assertEqual(problemas_tc62_42_ancho_completo(modulo), [])

    def test_tkt062_ca07_esc03_normalizar_aplica_nfkc_antes_de_pasar_a_minusculas(self) -> None:
        """TKT-062 CA-7 esc. 3 · N001 — `_normalizar` devuelve `skant` para `sk-ant-` en ancho completo, en mayúsculas o con espacio ideográfico."""
        modulo = self.publicar()
        self.assertEqual(problemas_normalizar_aplica_nfkc(modulo), [])

    def test_tkt062_ca05_esc02_una_cita_con_texto_libre_alrededor_se_descarta(self) -> None:
        """TKT-062 CA-5 esc. 2 · F003 — `x @org/equipo ![i](https://e/?q=1) RN-03` no es una cita: se descarta como «sin cita», el hallazgo no se
        publica y ni la mención ni la imagen llegan al comentario. Las formas exactas siguen valiendo, con espacios al borde incluidos."""
        modulo = self.publicar()
        cita_con_ruido = "x @org/equipo ![i](https://e/?q=1) RN-03"
        con_ruido = hallazgo(archivo="r.py", linea=2, texto="TEXTO-RUIDOSO", cita=cita_con_ruido)
        self.assertEqual(modulo.separar_por_cita([con_ruido]), ([], [con_ruido]))
        resultado = correr(modulo, [con_ruido], archivos=["r.py"])
        self.assertEqual(resultado.codigo, 0, resultado.registro)
        self.assertEqual(resultado.lineas_del_registro, ["descartado sin cita: r.py:2"])
        comentario = resultado.comentario or ""
        self.assertIn(SIN_HALLAZGOS, comentario)
        for fragmento in ("@org/equipo", "https://e/", "TEXTO-RUIDOSO"):
            self.assertNotIn(fragmento, comentario)
        for cita in ("RN-03", "  RN-03  ", " CLAUDE.md regla 11 ", "non-goal de TKT-062b"):
            with self.subTest(cita=cita):
                exacto = hallazgo(cita=cita)
                self.assertEqual(modulo.separar_por_cita([exacto]), ([exacto], []))
        for cita in ("RN-03 y RN-04", "Viola CLAUDE.md regla 5 y además RN-04", "ver RN-03", "RN-03 @org/equipo"):
            with self.subTest(cita=cita):
                ajeno = hallazgo(cita=cita)
                self.assertEqual(modulo.separar_por_cita([ajeno]), ([], [ajeno]))


class PruebasDelGuionComoProceso(unittest.TestCase):
    """Lanza `tools/publicar_revision.py` con el intérprete, como lo hace el paso del flujo. Cubre lo que `main(argv, entorno)`
    no ve: que la última línea llama a `sys.exit(main())` y que sin parámetros lee `sys.argv` y el entorno real."""

    def lanzar(self, hallazgos: str | None) -> tuple[subprocess.CompletedProcess[str], str]:
        """El guion con el entorno actual sin las cuatro variables, más las del caso. Devuelve el proceso y la ruta de `--salida`."""
        if not os.path.exists(GUION):
            self.fail("falta tools/publicar_revision.py: el módulo bajo prueba todavía no existe")
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ruta_archivos = os.path.join(carpeta, "archivos.txt")
        ruta_salida = os.path.join(carpeta, "comentario.md")
        with open(ruta_archivos, "w", encoding="utf-8") as archivo:
            archivo.write("README.md\n")
        entorno = {
            clave: valor
            for clave, valor in os.environ.items()
            if clave not in ("HALLAZGOS", "TITULO", "CUERPO", "CABEZA")
        }
        entorno.update({"TITULO": TITULO_CON_TICKET, "CUERPO": "", "CABEZA": SHA})
        if hallazgos is not None:
            entorno["HALLAZGOS"] = hallazgos
        proceso = subprocess.run(
            [sys.executable, "-X", "utf8", "-I", GUION, "--archivos", ruta_archivos, "--salida", ruta_salida],
            env=entorno,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            check=False,
        )
        return proceso, ruta_salida

    def test_tkt062_ca05_esc01_como_proceso_un_hallazgo_con_cita_termina_en_0_y_escribe_el_comentario(self) -> None:
        """TKT-062 CA-5 esc. 1 — como proceso, un hallazgo con cita válida termina en 0 y escribe el comentario con el encabezado."""
        proceso, ruta_salida = self.lanzar(como_hallazgos_json([hallazgo(texto="TEXTO-X", cita="RN-03")]))
        self.assertEqual(proceso.returncode, 0, proceso.stderr + proceso.stdout)
        self.assertTrue(os.path.exists(ruta_salida), "el guion no escribió --salida")
        with open(ruta_salida, encoding="utf-8") as archivo:
            comentario = archivo.read()
        self.assertTrue(comentario.startswith(ENCABEZADO), comentario)
        self.assertIn("TEXTO-X", comentario)

    def test_tkt062_ca05_esc02_como_proceso_sin_hallazgos_termina_en_2_y_no_escribe_la_salida(self) -> None:
        """TKT-062 CA-5 esc. 2 — como proceso, sin `HALLAZGOS` termina en 2 con `::error::` y no escribe `--salida`."""
        proceso, ruta_salida = self.lanzar(None)
        self.assertEqual(proceso.returncode, 2, proceso.stderr + proceso.stdout)
        self.assertIn("::error::", proceso.stdout + proceso.stderr)
        self.assertFalse(os.path.exists(ruta_salida), "el guion escribió --salida con una entrada inválida")

    def test_tkt062_ca07_esc03_como_proceso_una_clave_no_llega_ni_al_comentario_ni_al_registro(self) -> None:
        """TKT-062 CA-7 esc. 3 · N002 a — como proceso, un hallazgo con clave termina en 0, no aparece en el comentario y el registro no la imprime
        ni nombra su archivo."""
        hallazgos = como_hallazgos_json([hallazgo(archivo="a.py", linea=7, texto=f"clave {CLAVE_DE_EJEMPLO}", cita="RN-03")])
        proceso, ruta_salida = self.lanzar(hallazgos)
        self.assertEqual(proceso.returncode, 0, proceso.stderr + proceso.stdout)
        with open(ruta_salida, encoding="utf-8") as archivo:
            comentario = archivo.read()
        self.assertNotIn("sk-ant-", comentario)
        self.assertNotIn("sk-ant-", proceso.stdout + proceso.stderr)
        self.assertIn("descartado por contener una clave: [archivo omitido]:7", proceso.stdout + proceso.stderr)
        self.assertNotIn("a.py", proceso.stdout + proceso.stderr)


# ---------------------------------------------------------------------------------------------------------
# Mutantes
# ---------------------------------------------------------------------------------------------------------


def cambiar_patron(nombre: str, viejo: str, nuevo: str) -> Callable[[Any], None]:
    """Mutante sobre el texto de una expresión regular del módulo. Falla si `viejo` no está: el mutante no sería aplicable."""

    def aplicar(modulo: Any) -> None:
        patron = getattr(modulo, nombre).pattern
        if viejo not in patron:
            raise AssertionError(f"el mutante no es aplicable: {viejo!r} no está en {nombre}")
        setattr(modulo, nombre, re.compile(patron.replace(viejo, nuevo, 1), getattr(modulo, nombre).flags))

    return aplicar


def cita_con_alternativa_vacia(modulo: Any) -> None:
    modulo.CITA_VALIDA = re.compile(modulo.CITA_VALIDA.pattern + "|", modulo.CITA_VALIDA.flags)


def cita_por_busqueda(modulo: Any) -> None:
    """F003 · `fullmatch` pasa a ser `search`: el patrón y sus alternativas son los de siempre, pero basta con que la cita los contenga."""
    original = modulo.CITA_VALIDA

    class ComoBusqueda:
        pattern = original.pattern
        flags = original.flags
        search = staticmethod(original.search)
        match = staticmethod(original.match)
        fullmatch = staticmethod(original.search)

    modulo.CITA_VALIDA = ComoBusqueda


def _separar_reimplementado(
    modulo: Any,
    normalizar: Callable[[str], str] | None,
    *,
    con_la_concatenacion: bool = True,
    con_clave_literal: bool = True,
    solo_el_texto: bool = False,
) -> None:
    """Sustituye `separar_por_cita` por una versión con lo que el diseño pide, menos lo que el mutante quita: cita con `fullmatch` sobre
    `cita.strip()`, `CLAVE_EXPUESTA` en los campos, y `skant` tras `normalizar` en cada campo y en la concatenación de los tres."""

    def separar(hallazgos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        publicables: list[dict[str, Any]] = []
        descartados: list[dict[str, Any]] = []
        for candidato in hallazgos:
            campos = [str(candidato[nombre]) for nombre in ("archivo", "texto", "cita")]
            vistos = [campos[1]] if solo_el_texto else campos
            con_clave = con_clave_literal and any(modulo.CLAVE_EXPUESTA.search(campo) for campo in vistos)
            if normalizar is not None:
                con_clave = con_clave or any("skant" in normalizar(campo) for campo in campos)
                if con_la_concatenacion:
                    con_clave = con_clave or "skant" in normalizar("".join(campos))
            if con_clave or not modulo.CITA_VALIDA.fullmatch(str(candidato["cita"]).strip()):
                descartados.append(candidato)
            else:
                publicables.append(candidato)
        return publicables, descartados

    modulo.separar_por_cita = separar


def clave_solo_en_el_texto(modulo: Any) -> None:
    _separar_reimplementado(modulo, None, solo_el_texto=True)


def sin_clave_ofuscada(modulo: Any) -> None:
    _separar_reimplementado(modulo, None)


def ofuscada_sin_minusculas(modulo: Any) -> None:
    _separar_reimplementado(modulo, lambda texto: re.sub(r"[\W_]+", "", texto))


def ofuscada_sin_quitar_guiones_bajos(modulo: Any) -> None:
    _separar_reimplementado(modulo, lambda texto: re.sub(r"\W+", "", texto.lower()))


def ofuscada_solo_por_campo(modulo: Any) -> None:
    _separar_reimplementado(modulo, normalizado, con_la_concatenacion=False)


def sin_nfkc(modulo: Any) -> None:
    """N001 · `_normalizar` como antes del ajuste: minúsculas y fuera lo que no es alfanumérico, sin pasar por NFKC."""
    modulo._normalizar = lambda texto: re.sub(r"[\W_]+", "", texto.lower())


def _omitido(hallazgo_descartado: dict[str, Any]) -> str:
    linea = hallazgo_descartado.get("linea")
    return f"[archivo omitido]:{linea}" if linea is not None else "[archivo omitido]"


def _main_con_ubicacion(
    modulo: Any, elegir: Callable[[Any, dict[str, Any], bool, list[str]], str]
) -> None:
    """Sustituye `main` por una copia que solo cambia cómo se elige la ubicación del registro: `elegir(modulo, descartado, con_clave,
    archivos)`. El resto (lectura, filtro, mecánicos, comentario) usa los ayudantes del módulo."""

    def main(argv: list[str] | None = None, entorno: dict[str, str] | None = None) -> int:
        analizador = argparse.ArgumentParser()
        analizador.add_argument("--archivos", required=True)
        analizador.add_argument("--salida", required=True)
        argumentos = analizador.parse_args(argv)
        entorno = entorno or {}
        hallazgos = modulo.leer_hallazgos(entorno.get("HALLAZGOS", ""))
        archivos = modulo._leer_archivos(argumentos.archivos)
        publicables, descartados = modulo.separar_por_cita(hallazgos)
        for descartado in descartados:
            con_clave = modulo._tiene_clave(descartado)
            razon = "por contener una clave" if con_clave else "sin cita"
            print(f"descartado {razon}: {modulo._para_el_registro(elegir(modulo, descartado, con_clave, archivos))}")
        mecanicos = modulo.hallazgos_mecanicos(entorno.get("TITULO", ""), entorno.get("CUERPO", ""), archivos)
        comentario = modulo.componer_comentario(mecanicos, publicables, entorno.get("CABEZA", ""))
        with open(argumentos.salida, "w", encoding="utf-8", newline="\n") as salida:
            salida.write(comentario)
        return 0

    modulo.main = main


def registro_imprime_el_archivo_siempre(modulo: Any) -> None:
    _main_con_ubicacion(modulo, lambda m, d, con_clave, archivos: m._ubicacion(d))


def registro_omite_solo_si_la_clave_esta_en_el_archivo(modulo: Any) -> None:
    """La conducta anterior: omite solo cuando `archivo` por sí solo contiene la clave; con cita inválida imprime el archivo."""

    def elegir(m: Any, d: dict[str, Any], con_clave: bool, archivos: list[str]) -> str:
        if con_clave and m._tiene_clave({**d, "texto": "", "cita": ""}):
            return _omitido(d)
        return m._ubicacion(d)

    _main_con_ubicacion(modulo, elegir)


def registro_con_cita_invalida_imprime_el_archivo_siempre(modulo: Any) -> None:
    """Omite el archivo con una clave, en todos los casos, pero lo imprime siempre con una cita inválida."""
    _main_con_ubicacion(modulo, lambda m, d, con_clave, archivos: _omitido(d) if con_clave else m._ubicacion(d))


def registro_con_cita_invalida_omite_el_archivo_siempre(modulo: Any) -> None:
    """Omite el archivo en todos los casos: ignora la lista de `--archivos`."""
    _main_con_ubicacion(modulo, lambda m, d, con_clave, archivos: _omitido(d))


def registro_compara_el_archivo_con_la_lista_por_subcadena(modulo: Any) -> None:
    def elegir(m: Any, d: dict[str, Any], con_clave: bool, archivos: list[str]) -> str:
        figura = any(str(d["archivo"]) in nombre or nombre in str(d["archivo"]) for nombre in archivos)
        return m._ubicacion(d) if figura and not con_clave else _omitido(d)

    _main_con_ubicacion(modulo, elegir)


def clave_que_nunca_casa(modulo: Any) -> None:
    modulo.CLAVE_EXPUESTA = re.compile(r"(?!)")


def registro_sin_sustituir_dos_puntos(modulo: Any) -> None:
    modulo._para_el_registro = lambda texto: texto.replace("\r", " ").replace("\n", " ")


def ticket_solo_en_el_titulo(modulo: Any) -> None:
    original = modulo.hallazgos_mecanicos
    modulo.hallazgos_mecanicos = lambda titulo, cuerpo, archivos: original(titulo, "", archivos)


def contrato_por_prefijo(modulo: Any) -> None:
    original = modulo.hallazgos_mecanicos
    contrato = modulo.CONTRATO

    def mecanicos(titulo: str, cuerpo: str, archivos: list[str]) -> list[dict[str, object]]:
        if any(archivo.startswith(contrato) for archivo in archivos):
            archivos = [*archivos, contrato]
        return original(titulo, cuerpo, archivos)

    modulo.hallazgos_mecanicos = mecanicos


# (compuerta, descripción del mutante, aplicación, comprobación, fragmento del problema que debe aparecer)
MUTANTES: tuple[tuple[str, str, Callable[[Any], None], Callable[[Any], list[str]], str], ...] = (
    (
        "CITA_VALIDA",
        "rango de las reglas ampliado a la 18",
        cambiar_patron("CITA_VALIDA", "regla (?:1[0-7]|[1-9])", "regla (?:1[0-8]|[1-9])"),
        problemas_tc62_21,
        "'CLAUDE.md regla 18'",
    ),
    (
        "CITA_VALIDA",
        "las reglas RN de dos cifras sin tope",
        cambiar_patron("CITA_VALIDA", r"\bRN-(?:0[1-9]|1\d|2[0-5])", r"\bRN-\d\d"),
        problemas_tc62_21,
        "'RN-26'",
    ),
    (
        "CITA_VALIDA",
        "alternativa vacía",
        cita_con_alternativa_vacia,
        problemas_tc62_21,
        "cita inválida publicada",
    ),
    (
        "CITA_VALIDA",
        "aplicada con search en lugar de fullmatch",
        cita_por_busqueda,
        problemas_tc62_21,
        "cita inválida publicada: 'x @org/equipo ![i](https://e/?q=1) RN-03'",
    ),
    (
        "CLAVE_EXPUESTA",
        "comprobada solo en el texto",
        clave_solo_en_el_texto,
        problemas_tc62_42,
        "la clave en el archivo no descarta el hallazgo",
    ),
    (
        "CLAVE_EXPUESTA",
        "nunca casa",
        clave_que_nunca_casa,
        problemas_tc62_42,
        "CLAVE_EXPUESTA no casa con una clave de ejemplo",
    ),
    (
        "separar_por_cita",
        "sin la comprobación de la clave ofuscada",
        sin_clave_ofuscada,
        problemas_tc62_42_clave_ofuscada,
        "la clave ofuscada con espacios en el texto no descarta el hallazgo",
    ),
    (
        "separar_por_cita",
        "la clave ofuscada sin pasar a minúsculas",
        ofuscada_sin_minusculas,
        problemas_tc62_42_clave_ofuscada,
        "la clave ofuscada en mayúsculas en el texto no descarta el hallazgo",
    ),
    (
        "separar_por_cita",
        "la clave ofuscada sin quitar los guiones bajos",
        ofuscada_sin_quitar_guiones_bajos,
        problemas_tc62_42_clave_ofuscada,
        "la clave ofuscada con guiones bajos en el texto no descarta el hallazgo",
    ),
    (
        "separar_por_cita",
        "la clave ofuscada sin mirar la concatenación de los tres campos",
        ofuscada_solo_por_campo,
        problemas_tc62_42_clave_ofuscada,
        "la clave ofuscada partida entre archivo y texto no descarta el hallazgo",
    ),
    (
        "_normalizar",
        "sin unicodedata.normalize NFKC (N001)",
        sin_nfkc,
        problemas_tc62_42_ancho_completo,
        "la clave en ancho completo en el texto no descarta el hallazgo",
    ),
    (
        "_normalizar",
        "sin NFKC, comprobado sobre la propia función",
        sin_nfkc,
        problemas_normalizar_aplica_nfkc,
        "_normalizar(",
    ),
    (
        "main",
        "el registro imprime el archivo siempre (N002)",
        registro_imprime_el_archivo_siempre,
        problemas_n002_registro_con_clave,
        "clave con el cuerpo en el archivo y sk-ant- en el texto: el registro no dice",
    ),
    (
        "main",
        "el registro omite el archivo solo si la clave está en archivo (N002)",
        registro_omite_solo_si_la_clave_esta_en_el_archivo,
        problemas_n002_registro_con_clave,
        "clave con el cuerpo en el archivo y sk-ant- en el texto: el registro no dice",
    ),
    (
        "main",
        "con cita inválida el registro imprime el archivo siempre (N002 b)",
        registro_con_cita_invalida_imprime_el_archivo_siempre,
        problemas_n002_registro_sin_cita,
        "cita inválida con un archivo ajeno a la lista: el registro no dice",
    ),
    (
        "main",
        "con cita inválida el registro omite el archivo siempre (N002 b)",
        registro_con_cita_invalida_omite_el_archivo_siempre,
        problemas_n002_registro_sin_cita,
        "cita inválida con el archivo listado: el registro no dice",
    ),
    (
        "main",
        "el archivo se compara con la lista por subcadena (N002 b)",
        registro_compara_el_archivo_con_la_lista_por_subcadena,
        problemas_n002_registro_sin_cita,
        "cita inválida con un archivo contenido en uno de la lista: el registro no dice",
    ),
    (
        "_para_el_registro",
        "sin sustituir los dos puntos dobles",
        registro_sin_sustituir_dos_puntos,
        problemas_registro_neutralizado,
        "dos puntos dobles",
    ),
    (
        "hallazgos_mecanicos",
        "el ticket se busca solo en el título",
        ticket_solo_en_el_titulo,
        problemas_tc62_22,
        "ticket en el cuerpo",
    ),
    (
        "hallazgos_mecanicos",
        "la ruta del contrato se compara por prefijo",
        contrato_por_prefijo,
        problemas_tc62_23,
        "una ruta que no es el contrato lo señala",
    ),
)


class PruebasDeMutantes(PruebaBase):
    """Cada mutante se aplica a una copia privada del módulo; la comprobación del caso debe devolver el problema esperado."""

    def test_mutantes_la_copia_sin_mutar_pasa_todas_las_comprobaciones(self) -> None:
        """Control — sin esto, un mutante «en rojo» podría estarlo por culpa de la comprobación y no del cambio."""
        for comprobacion in (
            problemas_tc62_21,
            problemas_tc62_22,
            problemas_tc62_23,
            problemas_registro_neutralizado,
            problemas_tc62_42,
            problemas_tc62_42_clave_ofuscada,
            problemas_tc62_42_ancho_completo,
            problemas_normalizar_aplica_nfkc,
            problemas_n002_registro_con_clave,
            problemas_n002_registro_sin_cita,
        ):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(self.copia_privada()), [])

    def test_mutantes_cada_mutante_pone_en_rojo_la_comprobacion_de_su_caso(self) -> None:
        """TKT-062 CA-5 y CA-7 — cada mutante de `CITA_VALIDA`, `CLAVE_EXPUESTA`, `_normalizar`, el registro de `main`, `_para_el_registro` y `hallazgos_mecanicos` hace fallar su caso, con el problema esperado."""
        for compuerta, descripcion, aplicar, comprobacion, fragmento in MUTANTES:
            with self.subTest(compuerta=compuerta, mutante=descripcion):
                copia = self.copia_privada()
                aplicar(copia)
                problemas = comprobacion(copia)
                self.assertNotEqual(problemas, [], f"el mutante «{descripcion}» de {compuerta} no puso nada en rojo")
                self.assertTrue(
                    any(fragmento in problema for problema in problemas),
                    f"el mutante «{descripcion}» de {compuerta} cayó, pero no por {fragmento!r}: {problemas}",
                )


if __name__ == "__main__":
    unittest.main()
