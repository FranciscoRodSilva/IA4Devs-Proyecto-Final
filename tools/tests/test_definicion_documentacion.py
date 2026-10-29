"""Pruebas de la parte d del pipeline: el trabajo `documentacion` y `.github/workflows/enlaces.yml`.

TKT-009d · fila D5. Comprueban lo que el pipeline *declara*, no lo que hace al correr, con el mismo método que
`test_definicion_ci.py` (de donde se importan los ayudantes): `tools/` no tiene dependencias y la biblioteca estándar
no trae un analizador de YAML, así que el texto se lee con expresiones regulares, se ignoran las líneas comentadas
y cada caso busca dentro del bloque de su trabajo. Cada comprobación vive en una función `comprobar_*` que devuelve
la lista de problemas, y las pruebas sobre texto sintético demuestran que se pone en rojo ante cada mutante y por la
razón esperada (cada mutante exige un fragmento del mensaje, no solo que la lista no esté vacía).

Además de leer el texto, los pasos de Vale y de mermaid-cli se **ejecutan** (F001): el `run:` real de `ci.yml` corre con `bash`
sobre un árbol temporal, con un `uvx` y un `mmdc` de mentira, y se comprueba su código de salida y sus anotaciones. Hace falta
un `bash` (en Windows, el de Git for Windows; si `bash` es el de WSL, define `CIMENTA_BASH`); sin él las pruebas fallan, no se
saltan. Ver `localizar_bash` en `_ayudantes.py`.

Qué cubren:

* TC-65 (`CA-13` esc. 1, `CA-16` esc. 1, convenciones §10): el trabajo `documentacion` de `ci.yml` ejecuta, en este
  orden, `python3 tools/verificar_docs.py`, `markdownlint-cli2@0.24.0`, `vale --output=line` con la guarda de salida
  vacía, `lycheeverse/lychee-action` y `mmdc` sobre cada Markdown con un bloque `mermaid`. Cada paso lleva
  `if: ${{ !cancelled() }}` (regla común 6), también los de preparación (`setup-node`, `setup-uv`, la instalación de
  `mermaid-cli`): si fallase uno anterior y el de preparación se saltara, el paso siguiente correría sin su
  herramienta y taparía el hallazgo real con un «comando no encontrado». `mermaid-cli` no se instala suelto
  (`zizmor` marca `adhoc-packages`): `.github/mermaid/package.json` lo declara en la versión exacta `12.0.0`,
  `.github/mermaid/package-lock.json` la fija con su `integrity` y el trabajo ejecuta `npm ci` sobre ese directorio.
* TC-64 (`CA-14` esc. 1): `.github/workflows/enlaces.yml` se dispara un día por semana (`schedule`) y a mano
  (`workflow_dispatch`), con `permissions: contents: read`, y usa la misma configuración de `lychee` que el PR.
* Regresión `CA-R4`: los casos TC-12, TC-13, TC-21 y TC-22 de `test_definicion_ci.py` recorren todos los workflows y
  siguen en verde con `enlaces.yml` presente.
* Reglas comunes del diseño: 1 (corredor y tiempo máximo), 2 (acciones por SHA de 40 caracteres con la etiqueta en
  un comentario), 3 (herramientas por versión exacta), 4 (`persist-credentials: false`), 5 (sin `secrets.`), 6, 7
  (sin `continue-on-error`, sin `|| true`) y 9 (toda tubería declara `shell: bash`).

Formas que aceptan estos casos (la de la fila D5 tiene que ser una de ellas):

* `markdownlint`: `npx --yes markdownlint-cli2@0.24.0 "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md`.
* `Vale`: `uvx --from vale==3.25.1.0 vale --output=line docs sdd README.md CLAUDE.md tools/README.md >
  "$RUNNER_TEMP/vale.txt"` con el código de salida guardado (`|| estado=$?`), luego `cat` del archivo, y al final la
  guarda de salida vacía, en una de dos formas y nada más: `[ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]`
  como última línea del paso, o `if [ "$codigo" -ne 0 ] || [ -s "$RUNNER_TEMP/vale.txt" ]; then exit 1; fi`.
* `lychee`: `lycheeverse/lychee-action@<SHA de 40> # vX.Y.Z` con `args: --config lychee.toml --no-progress` más el
  alcance (ninguna otra opción: ni `--offline` ni `--exclude`), `lycheeVersion: v0.24.2` y `fail: true`. `setup-node`
  lleva `node-version-file: frontend/package.json`, y ni el trabajo ni el flujo declaran `defaults` con `working-directory`.
* `mermaid-cli`: un paso propio, antes del bucle, con `npm ci` y `working-directory: .github/mermaid` (o
  `npm ci --prefix .github/mermaid`), sin ningún `npm install` en el trabajo; y un bucle `for`/`while` sobre
  `grep -rl` (recursivo y que lista archivos) de «```mermaid» en el alcance que llama a
  `.github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json -i "$archivo"` (ruta relativa o bajo
  `$GITHUB_WORKSPACE`), con la llamada negada y sola (`if ! mmdc ...; then`, o `mmdc ... || { ...; }`); escribe
  `::error file=$archivo::diagrama Mermaid inválido`, pone `fallos=1` en la rama que falla (con `fallos=0` antes del
  bucle) y, tras el `done`, termina con `exit 1` condicionado por `fallos` (`-ne 0` o `-eq 1`), como último comando del paso.
  Los archivos reales: `.github/mermaid/package.json` (`"private": true` y `@mermaid-js/mermaid-cli` en `12.0.0`
  exacta, sin `^` ni `~`), `.github/mermaid/package-lock.json` (`lockfileVersion` 3 con esa versión e `integrity`),
  `.github/puppeteer-config.json` (`--no-sandbox` en `args`) y `.gitignore` con `node_modules`.
* `enlaces.yml`: `on:` es exactamente `schedule` y `workflow_dispatch`; declara `concurrency` con un `group` y
  `cancel-in-progress: false`; su `lychee-action` (SHA incluido) y sus `args` son los del trabajo `documentacion`.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_definicion_documentacion -v
"""

from __future__ import annotations

import copy
import json
import os
import re
import shlex
import sys
import unittest
from unittest import mock

DIRECTORIO_DE_PRUEBAS = os.path.dirname(os.path.abspath(__file__))
if DIRECTORIO_DE_PRUEBAS not in sys.path:
    sys.path.insert(0, DIRECTORIO_DE_PRUEBAS)

from _ayudantes import (  # noqa: E402
    ejecutar_en_bash,
    exigir_rojo,
    exigir_rojo_en_todos,
    localizar_bash,
    sustituir,
)
from test_definicion_ci import (  # noqa: E402
    CI_B3,
    DIRECTORIO_DE_FLUJOS,
    DOCUMENTACION_SINTETICA,
    ENMASCARA_EL_FALLO,
    GUARDA_DE_PASO,
    IF_DE_LAS_COMPUERTAS,
    LEE_SECRETOS,
    PASO_SETUP_UV,
    PASO_VERIFICAR_DOCS,
    PASO_VERIFICAR_DOCS_G,
    RAIZ,
    SIN_CREDENCIALES,
    VERIFICAR_DOCS,
    _disparadores,
    _indice_de_uses,
    _leer_flujos,
    _localizar,
    _nombre_del_paso,
    _orden_sin_cadenas,
    _permisos_de_flujo,
    _rebanada,
    _tiene_tuberia,
    _trabajos_de_ci,
    comando,
    comentar,
    comprobar_regla_comun_1,
    comprobar_regla_comun_6,
    comprobar_regla_comun_7,
    comprobar_regla_comun_8,
    comprobar_regla_comun_9,
    comprobar_tc12,
    comprobar_tc13,
    comprobar_tc21,
    comprobar_tc22,
    comprobar_trabajo_documentacion,
    directorio_por_omision,
    extraer_trabajos,
    mover,
    mutar,
    pasos,
    sin_comentarios,
    valor_del_paso,
)

ENLACES = os.path.join(DIRECTORIO_DE_FLUJOS, "enlaces.yml")

DOC = "documentacion"

# Alcance común de las tres herramientas (diseño, «Configuración de documentación»). Fuera: `.claude/` y `Doc de contexto/`.
ALCANCE_CON_GLOB = ("docs/**/*.md", "sdd/**/*.md", "README.md", "CLAUDE.md", "tools/README.md")
ALCANCE_DE_DIRECTORIOS = ("docs", "sdd", "README.md", "CLAUDE.md", "tools/README.md")

# Regla común 3: versiones exactas, escritas literales en el workflow.
VERSION_DE_MARKDOWNLINT = "0.24.0"
VERSION_DE_VALE = "3.25.1.0"
VERSION_DE_LYCHEE = "v0.24.2"
VERSION_DE_MMDC = "12.0.0"
CRON_SEMANAL = "0 13 * * 1"
ARCHIVO_DE_NODE = "frontend/package.json"
DISPARADORES_DE_ENLACES = {"schedule", "workflow_dispatch"}

MARKDOWNLINT = r"\bmarkdownlint-cli2(?![\w-])"
VALE_SUELTO = r"(?<![\w-])vale(?![\w-])"
VALE_FIJADO = rf"\buvx --from vale=={re.escape(VERSION_DE_VALE)} vale(?![\w.-])"
INSTALA_NPM = r"\bnpm\s+(?:ci|install|i|add)(?![\w-])"
NPM_QUE_RESUELVE = r"\bnpm\s+(?:install|i|add)(?![\w-])"
INVOCA_MMDC = r"(?i)mmdc\"?\s+-"
# El binario que instaló `npm ci` en `.github/mermaid`: relativo a la raíz o bajo `$GITHUB_WORKSPACE`.
BINARIO_DE_MMDC = r"(?:\$\{?GITHUB_WORKSPACE\}?/|\./|(?<![\w./-]))\.github/mermaid/node_modules/\.bin/mmdc(?![\w.-])\"?\s+-"

DIRECTORIO_DE_MERMAID = ".github/mermaid"
PAQUETE_DE_MMDC = "@mermaid-js/mermaid-cli"
ENTRADA_DEL_LOCK = f"node_modules/{PAQUETE_DE_MMDC}"
PACKAGE_JSON_DE_MERMAID = os.path.join(RAIZ, ".github", "mermaid", "package.json")
PACKAGE_LOCK_DE_MERMAID = os.path.join(RAIZ, ".github", "mermaid", "package-lock.json")
PUPPETEER_CONFIG = os.path.join(RAIZ, ".github", "puppeteer-config.json")
GITIGNORE = os.path.join(RAIZ, ".gitignore")

TEMPORAL = r"\"?\$\{?RUNNER_TEMP\}?"
ARCHIVO_DE_VALE = TEMPORAL + r"/vale\.txt\"?"
USES_FIJADO = re.compile(
    r"^(?:-\s+)?uses:\s*[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}\s+#\s*v\d+(?:\.\d+){1,2}\s*$"
)


# ---------------------------------------------------------------------------------------------------------
# Lectura de pasos y argumentos
# ---------------------------------------------------------------------------------------------------------


def _palabras(texto: str) -> list[str]:
    """Las palabras de una orden, sin las comillas que las envuelven."""
    try:
        return shlex.split(texto)
    except ValueError:
        return texto.split()


def _entrada_de_with(con: str, clave: str) -> str | None:
    """Valor de una entrada del `with:` de una acción: escalar en la misma línea o cuerpo de un bloque plegado (`>`, `|`).

    `con` es el cuerpo de `with:` tal como lo devuelve `valor_del_paso`: líneas sin sangría, unidas por saltos.
    """
    lineas = con.splitlines()
    for k, linea in enumerate(lineas):
        encontrada = re.match(rf"{re.escape(clave)}:\s*(.*)$", linea)
        if not encontrada:
            continue
        resto = encontrada.group(1).strip()
        if resto and resto[0] not in "|>":
            return resto
        cuerpo = []
        for siguiente in lineas[k + 1 :]:
            if re.match(r"[A-Za-z][\w-]*:(?:\s|$)", siguiente):
                break
            cuerpo.append(siguiente)
        return " ".join(cuerpo)
    return None


def _sin_el_par_config(palabras: list[str]) -> list[str]:
    """Las palabras sin `--config <archivo>` ni `--config=<archivo>`."""
    resultado: list[str] = []
    saltar = False
    for palabra in palabras:
        if saltar:
            saltar = False
            continue
        if palabra == "--config":
            saltar = True
            continue
        if palabra.startswith("--config="):
            continue
        resultado.append(palabra)
    return resultado


def _alcance_de(palabras: list[str]) -> list[str]:
    """Los argumentos que no son opciones, ordenados."""
    return sorted(p for p in palabras if not p.startswith("-"))


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones
# ---------------------------------------------------------------------------------------------------------


def _comprobar_paso_de_lychee(id_trabajo: str, paso: list[str]) -> list[str]:
    """La configuración de `lychee-action`: `--config lychee.toml`, `--no-progress`, el alcance, `lycheeVersion` y `fail: true`."""
    problemas: list[str] = []
    con = valor_del_paso(paso, "with") or ""
    argumentos = _entrada_de_with(con, "args")
    if argumentos is None:
        problemas.append(f"'{id_trabajo}': lychee-action no declara `args:`")
    else:
        if not re.search(
            r"""(?<![\w-])--config(?:=|\s+)["']?lychee\.toml["']?(?![\w.])""", argumentos
        ):
            problemas.append(f"'{id_trabajo}': lychee-action no usa `--config lychee.toml`")
        palabras = _palabras(argumentos)
        if "--no-progress" not in palabras:
            problemas.append(f"'{id_trabajo}': lychee-action no lleva `--no-progress`")
        sin_config = _sin_el_par_config(palabras)
        sobrantes = [p for p in sin_config if p.startswith("-") and p != "--no-progress"]
        if sobrantes:
            problemas.append(
                f"'{id_trabajo}': lychee-action lleva opciones fuera de `--config` y `--no-progress`: {sobrantes}; "
                "cambiarían qué enlaces se comprueban (`--offline`, `--exclude`...)"
            )
        alcance = _alcance_de(sin_config)
        if alcance != sorted(ALCANCE_CON_GLOB):
            problemas.append(
                f"'{id_trabajo}': el alcance de lychee-action debe ser {sorted(ALCANCE_CON_GLOB)} y es {alcance}"
            )
    if (_entrada_de_with(con, "fail") or "").strip("\"'").lower() != "true":
        problemas.append(
            f"'{id_trabajo}': lychee-action no declara `fail: true`; un enlace roto no pondría el trabajo en rojo"
        )
    if (_entrada_de_with(con, "lycheeVersion") or "").strip("\"'") != VERSION_DE_LYCHEE:
        problemas.append(
            f"'{id_trabajo}': lychee-action no fija `lycheeVersion: {VERSION_DE_LYCHEE}` (regla común 3)"
        )
    return problemas


def _guarda_de_salida_vacia(resto: str, codigo: str) -> re.Match[str] | None:
    """La guarda de Vale, en una de las dos únicas formas aceptadas y con cada prueba en su sentido.

    * A, la de `ci.yml`: `[ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]`, en cualquier orden, como línea completa.
      Es el estado del último comando del paso, así que decide el resultado.
    * B: `if [ "$codigo" -ne 0 ] || [ -s "$RUNNER_TEMP/vale.txt" ]; then exit 1; fi`, con `-s` sin negar.

    Un `-s` sin `!` en la forma A, un `-eq` donde va `-ne`, la prueba dentro de un `echo` o un `-s` negado en la forma B no
    comprueban lo que dicen, y la guarda ya no protege el paso.
    """
    variable = r"\[\s+\"?\$\{?" + codigo + r"\}?\"?\s+"
    codigo_cero = variable + r"-eq\s+0\s+\]"
    codigo_distinto = variable + r"-ne\s+0\s+\]"
    vacia = r"\[\s+!\s+-s\s+" + ARCHIVO_DE_VALE + r"\s+\]"
    con_contenido = r"\[\s+-s\s+" + ARCHIVO_DE_VALE + r"\s+\]"
    forma_a = rf"(?:{codigo_cero}\s*&&\s*{vacia}|{vacia}\s*&&\s*{codigo_cero})"
    forma_b = (
        rf"if\s+(?:{codigo_distinto}\s*\|\|\s*{con_contenido}|{con_contenido}\s*\|\|\s*{codigo_distinto})"
        r"\s*;\s*then\s+exit 1\s*;?\s*fi"
    )
    return re.search(rf"(?m)^[ \t]*(?:{forma_a}|{forma_b})[ \t]*$", resto)


def _comprobar_vale(lista: list[list[str]], hito: tuple[int, int]) -> list[str]:
    """Vale en CI: versión fija, `--output=line`, salida a `$RUNNER_TEMP/vale.txt`, impresión del archivo y falla si el código
    de salida no es 0 **o** el archivo no está vacío (los avisos no cambian el código de salida de Vale: solo `error`)."""
    problemas: list[str] = []
    run = comando(lista[hito[0]]).replace("\\\n", " ")
    fijado = re.search(VALE_FIJADO, run)
    donde_empieza = fijado or re.search(VALE_SUELTO, run)
    inicio = donde_empieza.start() if donde_empieza is not None else 0
    if fijado is None:
        problemas.append(
            f"'{DOC}': Vale no se invoca como `uvx --from vale=={VERSION_DE_VALE} vale`; sin la versión fija "
            "(regla común 3) o con `uvx vale` se ejecutaría otro paquete u otra versión"
        )
    resto = run[inicio:]
    linea = resto.split("\n")[0]
    orden = re.split(r"[;&|<>]", linea)[0]
    palabras = _palabras(orden)
    argumentos = palabras[palabras.index("vale") + 1 :] if "vale" in palabras else []
    if "--output=line" not in argumentos:
        problemas.append(
            f"'{DOC}': Vale no lleva `--output=line`; sin él no hay una línea por hallazgo con archivo y línea"
        )
    if _alcance_de(argumentos) != sorted(ALCANCE_DE_DIRECTORIOS):
        problemas.append(
            f"'{DOC}': el alcance de Vale debe ser {sorted(ALCANCE_DE_DIRECTORIOS)} y es {_alcance_de(argumentos)}"
        )
    if not re.search(rf"(?<![\d>&])>\s*{ARCHIVO_DE_VALE}(?![\w.])", linea):
        problemas.append(f"'{DOC}': Vale no redirige su salida a `$RUNNER_TEMP/vale.txt`")
    impresion = re.search(rf"\bcat\s+{ARCHIVO_DE_VALE}", resto)
    if impresion is None:
        problemas.append(
            f"'{DOC}': el paso de Vale no imprime `$RUNNER_TEMP/vale.txt`; el PR no vería los hallazgos"
        )
    captura = re.search(r"(\w+)=\$\?", resto)
    guarda = _guarda_de_salida_vacia(resto, captura.group(1) if captura else r"\w+")
    if guarda is None:
        problemas.append(
            f"'{DOC}': Vale sin la guarda de salida vacía: un aviso, que no cambia el código de salida, no pondría el paso en "
            'rojo. Solo se acepta `[ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]` como última línea del paso, o '
            '`if [ "$codigo" -ne 0 ] || [ -s "$RUNNER_TEMP/vale.txt" ]; then exit 1; fi`'
        )
    else:
        if impresion is not None and guarda.start() < impresion.start():
            problemas.append(
                f"'{DOC}': la guarda de salida vacía de Vale va antes de imprimir el archivo; el fallo ocultaría los hallazgos"
            )
        if resto[guarda.end() :].strip():
            problemas.append(
                f"'{DOC}': la guarda de salida vacía de Vale no es lo último del paso; lo que venga después "
                "(un `exit 0`, por ejemplo) ocultaría su fallo"
            )
    if captura is None or not re.search(
        rf"\$\{{?{captura.group(1)}(?![\w])", resto[captura.end() :]
    ):
        problemas.append(
            f"'{DOC}': el paso de Vale no conserva el código de salida (`|| estado=$?`) ni lo comprueba al final; "
            "un error de Vale con la salida vacía pasaría en verde"
        )
    return problemas


def _comprobar_markdownlint(lista: list[list[str]], hito: tuple[int, int]) -> list[str]:
    problemas: list[str] = []
    run = comando(lista[hito[0]]).replace("\\\n", " ")
    if not re.search(r"\bnpx\s+(?:--yes|-y)\s+markdownlint-cli2\b", run):
        problemas.append(
            f"'{DOC}': markdownlint-cli2 debe ejecutarse con `npx --yes markdownlint-cli2@{VERSION_DE_MARKDOWNLINT}`"
        )
    inicio = re.search(MARKDOWNLINT, run)
    linea = run[inicio.start() :].split("\n")[0] if inicio else ""
    paquete, _, resto = linea.partition(" ")
    version = paquete.partition("@")[2]
    if not version:
        problemas.append(
            f"'{DOC}': markdownlint-cli2 sin versión fija; debe ser markdownlint-cli2@{VERSION_DE_MARKDOWNLINT} (regla común 3)"
        )
    elif version != VERSION_DE_MARKDOWNLINT:
        problemas.append(
            f"'{DOC}': markdownlint-cli2@{version} y debe ser markdownlint-cli2@{VERSION_DE_MARKDOWNLINT} (regla común 3)"
        )
    palabras = _palabras(resto)
    if "--fix" in palabras:
        problemas.append(
            f"'{DOC}': markdownlint-cli2 lleva `--fix`, que corrige en lugar de fallar"
        )
    if _alcance_de(palabras) != sorted(ALCANCE_CON_GLOB):
        problemas.append(
            f"'{DOC}': el alcance de markdownlint-cli2 debe ser {sorted(ALCANCE_CON_GLOB)} y es {_alcance_de(palabras)}"
        )
    return problemas


def _directorio_normalizado(valor: str | None) -> str:
    """`./.github/mermaid/`, `".github/mermaid"` y `.github/mermaid` son el mismo directorio."""
    limpio = (valor or "").strip("\"'")
    return limpio.removeprefix("./").rstrip("/")


def _comprobar_instalacion_de_mermaid(
    paso: list[str], comparte_paso_con_el_bucle: bool
) -> list[str]:
    """La instalación de mermaid-cli es `npm ci` sobre `.github/mermaid` (su `package.json` y su lockfile), en un paso propio.
    `npm install <paquete>` instala fuera de un lockfile (`zizmor`: `adhoc-packages`)."""
    problemas: list[str] = []
    orden = comando(paso).replace("\\\n", " ")
    encontrada = re.search(INSTALA_NPM, orden)
    if encontrada is None:
        return problemas
    linea = orden[encontrada.start() :].split("\n")[0]
    palabras = _palabras(re.split(r"[;&|<>]", linea)[0])
    subcomando = palabras[1] if len(palabras) > 1 else ""
    if subcomando != "ci":
        problemas.append(
            f"'{DOC}': la instalación de mermaid-cli ejecuta `npm {subcomando}`; debe ser `npm ci`, que instala lo que fija "
            "el lockfile y no un paquete suelto (zizmor: adhoc-packages)"
        )
    prefijo: str | None = None
    sueltos: list[str] = []
    esperando_valor = False
    for palabra in palabras[2:]:
        if esperando_valor:
            prefijo, esperando_valor = palabra, False
        elif palabra == "--prefix":
            esperando_valor = True
        elif palabra.startswith("--prefix="):
            prefijo = palabra.partition("=")[2]
        elif not palabra.startswith("-"):
            sueltos.append(palabra)
    if subcomando == "ci" and sueltos:
        problemas.append(
            f"'{DOC}': `npm ci` no instala paquetes sueltos ({sueltos}); mermaid-cli se declara en {DIRECTORIO_DE_MERMAID}/package.json"
        )
    directorio_del_paso = valor_del_paso(paso, "working-directory")
    if prefijo is not None and directorio_del_paso is not None:
        problemas.append(
            f"'{DOC}': la instalación de mermaid-cli declara `working-directory` y `--prefix` a la vez; "
            "un prefijo relativo se resolvería dentro del directorio del paso"
        )
    efectivo = prefijo if prefijo is not None else directorio_del_paso
    if _directorio_normalizado(efectivo) != DIRECTORIO_DE_MERMAID:
        problemas.append(
            f"'{DOC}': `npm ci` de mermaid-cli no se ejecuta en `{DIRECTORIO_DE_MERMAID}` "
            f"(`working-directory: {DIRECTORIO_DE_MERMAID}` o `--prefix {DIRECTORIO_DE_MERMAID}`) y toma {efectivo!r}"
        )
    if comparte_paso_con_el_bucle:
        problemas.append(
            f"'{DOC}': la instalación de mermaid-cli comparte paso con el bucle de mmdc; debe ir en un paso propio, antes del bucle"
        )
    return problemas


def _comprobar_mermaid(
    lista: list[list[str]], instalacion: tuple[int, int] | None, bucle: tuple[int, int]
) -> list[str]:
    problemas: list[str] = []
    if instalacion is not None:
        problemas += _comprobar_instalacion_de_mermaid(
            lista[instalacion[0]], instalacion[0] == bucle[0]
        )
    run = comando(lista[bucle[0]])
    if not re.search(BINARIO_DE_MMDC, run):
        problemas.append(
            f"'{DOC}': mmdc no se invoca desde el binario que instaló `npm ci`: `{DIRECTORIO_DE_MERMAID}/node_modules/.bin/mmdc` "
            "(ruta relativa a la raíz o bajo `$GITHUB_WORKSPACE`)"
        )
    if not re.search(
        r"(?<![\w-])(?:-p|--puppeteerConfigFile)(?:=|\s+)\"?\.github/puppeteer-config\.json\"?", run
    ):
        problemas.append(
            f"'{DOC}': mmdc no recibe `-p .github/puppeteer-config.json`; Chromium no arranca en el corredor sin ese arreglo"
        )
    problemas += _comprobar_bucle_de_mmdc(run)
    for nombre, patron in (
        ("docs", r"(?<![\w./-])docs(?![\w-])"),
        ("sdd", r"(?<![\w./-])sdd(?![\w-])"),
        ("README.md", r"(?<![\w./-])README\.md"),
        ("CLAUDE.md", r"(?<![\w./-])CLAUDE\.md"),
        ("tools/README.md", r"(?<![\w./-])tools/README\.md"),
    ):
        if not re.search(patron, run):
            problemas.append(f"'{DOC}': el paso de mmdc no cubre {nombre} del alcance")
    if re.search(r"\b(?:grep|find)\b[^\n]*\s\.(?:\s|$)", run):
        problemas.append(
            f"'{DOC}': el paso de mmdc recorre el repositorio entero (`.`) en lugar del alcance"
        )
    return problemas


# Una orden que no encadena otras: ni `;`, ni `|`, ni `&&` (un `2>&1` sí cabe).
ORDEN_SIMPLE = r"(?:[^;|&]|&(?!&))*"


def _variable_del_bucle(cabecera: str) -> str | None:
    """La variable que recorre los archivos: `for archivo in ...` o `while ... read -r archivo`."""
    for_ = re.match(r"\s*for\s+(\w+)\s+in\b", cabecera)
    if for_:
        return for_.group(1)
    leer = re.search(r"\bread\s+(?:-\w+\s+)*(\w+)\s*(?:;|<|$)", cabecera)
    return leer.group(1) if leer else None


def _problema_de_la_llamada_a_mmdc(run: str) -> str | None:
    """La llamada a mmdc va negada y sola: `if ! mmdc ...; then`, o `mmdc ... || { ...; }`.

    Si va sin negar, el cuerpo del `if` corre cuando el diagrama es VÁLIDO; si la condición encadena otro comando
    (`; true;`, `| cat`, `&&`), el estado que decide ya no es el de mmdc. En ambos casos el bucle no marca ningún fallo.
    """
    binario = re.search(BINARIO_DE_MMDC, run)
    if binario is None:
        return None  # lo informa el llamador
    inicio = run.rfind("\n", 0, binario.start()) + 1
    fin = run.find("\n", binario.end())
    antes = run[inicio : binario.start()]
    despues = run[binario.start() : fin if fin != -1 else len(run)].rstrip()
    if re.fullmatch(r"""\s*if\s+!\s+["']?""", antes):
        if re.fullmatch(ORDEN_SIMPLE + r"\s*;\s*then", despues):
            return None
        return (
            f"'{DOC}': la condición `if ! mmdc ...` encadena otro comando (`;`, `|`, `&&`) y el estado que decide ya no es el de "
            "mmdc; un diagrama inválido no se detectaría"
        )
    if re.fullmatch(r"""\s*["']?""", antes) and re.match(ORDEN_SIMPLE + r"\|\|\s*\{", despues):
        return None
    return (
        f"'{DOC}': la llamada a mmdc no está negada (`if ! mmdc ...; then` o `mmdc ... || {{ ...; }}`); el cuerpo correría "
        "cuando el diagrama es válido"
    )


def _comprobar_bucle_de_mmdc(run: str) -> list[str]:
    """El bucle sobre los Markdown con diagramas: llamada negada, `-i` con la variable del bucle, `::error` por archivo, la
    variable de fallos (iniciada en 0 y puesta en 1 en la rama que falla) y un `exit 1` condicionado por ella tras el `done`."""
    problemas: list[str] = []
    problema_de_la_llamada = _problema_de_la_llamada_a_mmdc(run)
    if problema_de_la_llamada:
        problemas.append(problema_de_la_llamada)
    inicio_del_bucle = re.search(r"(?m)^\s*(?:for|while)\s", run)
    fines = list(re.finditer(r"(?m)^\s*done\b", run))
    if inicio_del_bucle is None or not fines:
        problemas.append(
            f"'{DOC}': mmdc no se ejecuta dentro de un bucle (`for`/`while` ... `done`) sobre los Markdown con diagramas"
        )
    else:
        problemas += _comprobar_el_cuerpo_del_bucle(run, inicio_del_bucle, fines[-1])
    seleccion = re.search(r"""\bgrep\s+((?:-\S+\s+)*)["']?```mermaid""", run)
    if seleccion is None:
        problemas.append(
            f"'{DOC}': el paso de mmdc no selecciona los Markdown que contienen un bloque ```mermaid"
        )
    else:
        opciones = seleccion.group(1).split()
        if not any(
            re.fullmatch(r"-[A-Za-z]*[rR][A-Za-z]*", o) or o.endswith("recursive") for o in opciones
        ):
            problemas.append(
                f"'{DOC}': el `grep` de los Markdown con diagramas no es recursivo (`-r`); sobre un directorio no entra en él"
            )
        if not any(
            re.fullmatch(r"-[A-Za-z]*l[A-Za-z]*", o) or o == "--files-with-matches"
            for o in opciones
        ):
            problemas.append(
                f"'{DOC}': el `grep` de los Markdown con diagramas no lista nombres de archivo (`-l`) y el bucle recibiría líneas"
            )
    return problemas


def _comprobar_el_cuerpo_del_bucle(
    run: str, inicio: re.Match[str], fin: re.Match[str]
) -> list[str]:
    problemas: list[str] = []
    variable = _variable_del_bucle(run[inicio.start() :].split("\n")[0])
    if variable is not None and not re.search(
        rf"""(?<![\w-])(?:-i|--input)(?:=|\s+)["']?\$\{{?{variable}\}}?["']?(?![\w])""", run
    ):
        problemas.append(
            f"'{DOC}': mmdc no recibe `-i \"${variable}\"`; con otro archivo el bucle no valida el diagrama que recorre"
        )
    error = re.search(r"::error file=(\S+?)::diagrama Mermaid inválido", run)
    binario = re.search(BINARIO_DE_MMDC, run)
    if (
        error is None
        or not inicio.start() < error.start() < fin.start()
        or (binario is not None and error.start() < binario.start())
    ):
        problemas.append(
            f"'{DOC}': el bucle de mmdc no escribe `::error file=<archivo>::diagrama Mermaid inválido` por cada fallo"
        )
        error = None
    elif variable is not None and not re.fullmatch(
        rf"""["']?\$\{{?{variable}\}}?""", error.group(1)
    ):
        problemas.append(
            f"'{DOC}': el `::error file=` no nombra el archivo del bucle (`${variable}`) sino {error.group(1)!r}"
        )
    marca = None
    if error is not None:
        cierre = re.search(r"(?m)^\s*fi\b|\}", run[error.end() :])
        segmento = (
            run[error.end() : error.end() + cierre.start()]
            if cierre
            else run[error.end() : fin.start()]
        )
        marca = re.search(r"(?<![\w$])(\w+)=1(?![\w.])", segmento)
        if marca is None:
            problemas.append(
                f"'{DOC}': el bucle de mmdc no marca el fallo: falta `fallos=1` entre el `::error` y el cierre de su rama"
            )
    fallos = marca.group(1) if marca else None
    if fallos is not None and not re.search(rf"(?m)^\s*{fallos}=0\s*$", run[: inicio.start()]):
        problemas.append(
            f"'{DOC}': el paso de mmdc no inicia `{fallos}=0` antes del bucle; sin iniciar, `[ \"${fallos}\" -ne 0 ]` da error (2), "
            "la condición es falsa y el paso termina en verde"
        )
    variable_de_fallos = re.escape(fallos) if fallos else r"\w+"
    prueba = rf'\[\s+"?\$\{{?{variable_de_fallos}\}}?"?\s+'
    hubo_fallos = prueba + r"(?:-ne\s+0|-eq\s+1)\s+\]"
    sin_fallos = prueba + r"-eq\s+0\s+\]"
    salida = (
        rf"if\s+{hubo_fallos}\s*;\s*then\s+exit 1\s*;?\s*fi"
        rf"|{hubo_fallos}\s*&&\s*exit 1"
        rf"|{sin_fallos}\s*\|\|\s*exit 1"
    )
    if not re.search(rf"(?m)^[ \t]*(?:{salida})\s*\Z", run[fin.end() :]):
        problemas.append(
            f"'{DOC}': el paso de mmdc no termina con `exit 1` después del bucle condicionado por la variable de fallos "
            '(`if [ "$fallos" -ne 0 ]; then exit 1; fi`, como último comando del paso)'
        )
    return problemas


def _leer_json(texto: str, archivo: str) -> tuple[dict | None, list[str]]:
    try:
        datos = json.loads(texto)
    except ValueError as error:
        return None, [f"{archivo}: no es JSON válido ({error})"]
    if not isinstance(datos, dict):
        return None, [f"{archivo}: la raíz debe ser un objeto JSON"]
    return datos, []


def comprobar_package_json_de_mermaid(texto: str) -> list[str]:
    """CA-16 esc. 1 · TC-65. `.github/mermaid/package.json`: `"private": true` y `@mermaid-js/mermaid-cli` en `dependencies` o
    `devDependencies` con la versión EXACTA `12.0.0` (sin `^`, `~`, rangos ni etiquetas)."""
    archivo = f"{DIRECTORIO_DE_MERMAID}/package.json"
    datos, problemas = _leer_json(texto, archivo)
    if datos is None:
        return problemas
    if datos.get("private") is not True:
        problemas.append(
            f'{archivo}: debe declarar `"private": true`; este manifiesto no se publica'
        )
    declaradas = [
        datos[seccion][PAQUETE_DE_MMDC]
        for seccion in ("dependencies", "devDependencies")
        if isinstance(datos.get(seccion), dict) and PAQUETE_DE_MMDC in datos[seccion]
    ]
    if not declaradas:
        problemas.append(
            f"{archivo}: no declara {PAQUETE_DE_MMDC} en `dependencies` ni en `devDependencies`"
        )
    for version in declaradas:
        if version != VERSION_DE_MMDC:
            problemas.append(
                f"{archivo}: declara {PAQUETE_DE_MMDC} en {version!r}; debe ser la versión exacta {VERSION_DE_MMDC!r}, "
                "sin `^` ni `~` (regla común 3)"
            )
    return problemas


def comprobar_package_lock_de_mermaid(texto: str) -> list[str]:
    """CA-16 esc. 1 · TC-65. `.github/mermaid/package-lock.json`: `lockfileVersion` 3, `node_modules/@mermaid-js/mermaid-cli` en
    `12.0.0` con `integrity`, y la raíz del lock (`packages[""]`) declarando la misma versión exacta que el `package.json`."""
    archivo = f"{DIRECTORIO_DE_MERMAID}/package-lock.json"
    datos, problemas = _leer_json(texto, archivo)
    if datos is None:
        return problemas
    if datos.get("lockfileVersion") != 3:
        problemas.append(
            f"{archivo}: `lockfileVersion` debe ser 3 y es {datos.get('lockfileVersion')!r}"
        )
    paquetes = datos.get("packages")
    if not isinstance(paquetes, dict):
        return problemas + [f"{archivo}: no tiene la sección `packages`"]
    entrada = paquetes.get(ENTRADA_DEL_LOCK)
    if not isinstance(entrada, dict):
        problemas.append(f"{archivo}: no fija `{ENTRADA_DEL_LOCK}`")
    else:
        if entrada.get("version") != VERSION_DE_MMDC:
            problemas.append(
                f"{archivo}: fija {PAQUETE_DE_MMDC} en {entrada.get('version')!r}; debe ser {VERSION_DE_MMDC!r}"
            )
        if not re.fullmatch(
            r"sha(?:256|384|512)-[A-Za-z0-9+/]+=*", str(entrada.get("integrity") or "")
        ):
            problemas.append(f"{archivo}: la entrada de {PAQUETE_DE_MMDC} no lleva `integrity`")
    raiz = paquetes.get("")
    declarada = None
    if isinstance(raiz, dict):
        for seccion in ("dependencies", "devDependencies"):
            if isinstance(raiz.get(seccion), dict) and PAQUETE_DE_MMDC in raiz[seccion]:
                declarada = raiz[seccion][PAQUETE_DE_MMDC]
    if declarada != VERSION_DE_MMDC:
        problemas.append(
            f"{archivo}: la raíz del lock declara {PAQUETE_DE_MMDC} en {declarada!r} y debe ser {VERSION_DE_MMDC!r}; "
            "el lock no corresponde al package.json"
        )
    return problemas


def comprobar_gitignore_de_node_modules(texto: str) -> list[str]:
    """`.gitignore` ignora `node_modules` en cualquier profundidad (el de `.github/mermaid` incluido): `node_modules`,
    `node_modules/`, `**/node_modules` o `**/node_modules/`, sin una negación posterior. Anclado a la raíz (`/node_modules/`) no basta."""
    lineas = [linea.strip() for linea in texto.splitlines()]
    activas = [linea for linea in lineas if linea and not linea.startswith("#")]
    problemas: list[str] = []
    if not any(
        linea in ("node_modules", "node_modules/", "**/node_modules", "**/node_modules/")
        for linea in activas
    ):
        problemas.append(
            ".gitignore: no ignora `node_modules/` en cualquier profundidad; `npm ci` dejaría .github/mermaid/node_modules como cambio pendiente"
        )
    if any(linea.startswith("!") and "node_modules" in linea for linea in activas):
        problemas.append(".gitignore: una negación (`!`) vuelve a incluir node_modules")
    return problemas


def comprobar_puppeteer_config(texto: str) -> list[str]:
    """CA-16 esc. 1 · TC-65. `.github/puppeteer-config.json`, el que recibe `mmdc -p`: un objeto con `args` (una lista) que incluye
    `--no-sandbox`. Sin él Chromium no arranca como root en el corredor, y todos los diagramas fallarían por eso."""
    archivo = ".github/puppeteer-config.json"
    datos, problemas = _leer_json(texto, archivo)
    if datos is None:
        return problemas
    argumentos = datos.get("args")
    if not isinstance(argumentos, list):
        return [f"{archivo}: no declara `args` como una lista de argumentos de Chromium"]
    if "--no-sandbox" not in argumentos:
        problemas.append(f"{archivo}: `args` no lleva `--no-sandbox` y es {argumentos!r}")
    return problemas


def comprobar_acciones_fijadas(texto: str, id_trabajo: str) -> list[str]:
    """Regla común 2. Sobre el texto sin podar, porque la etiqueta `# vX.Y.Z` es un comentario: cada `uses:` del trabajo apunta
    a un SHA de 40 caracteres hexadecimales y lleva su etiqueta."""
    if f"\n  {id_trabajo}:\n" not in texto:
        return [f"no existe el trabajo '{id_trabajo}'"]
    inicio, fin = _rebanada(texto, id_trabajo)
    problemas = []
    for linea in texto[inicio:fin].splitlines():
        limpia = linea.strip()
        if limpia.startswith("#") or not re.match(r"(?:-\s+)?uses:", limpia):
            continue
        if not USES_FIJADO.match(limpia):
            problemas.append(
                f"'{id_trabajo}': `{limpia}` no está fijada por SHA de 40 caracteres con su etiqueta `# vX.Y.Z` (regla común 2)"
            )
    return problemas


def _comprobar_checkout(
    id_trabajo: str, lista: list[list[str]], i_checkout: int | None
) -> list[str]:
    """El trabajo tiene `actions/checkout` y este no persiste las credenciales (regla común 4)."""
    if i_checkout is None:
        return [f"'{id_trabajo}': falta actions/checkout"]
    if not SIN_CREDENCIALES.search(valor_del_paso(lista[i_checkout], "with") or ""):
        return [f"'{id_trabajo}': el checkout debe declarar `persist-credentials: false`"]
    return []


def comprobar_tc65(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-13 esc. 1 y CA-16 esc. 1 · TC-65. El trabajo `documentacion` ejecuta, en orden, `verificar_docs.py`,
    `markdownlint-cli2@0.24.0`, Vale (con la guarda de salida vacía), `lychee-action` y `mmdc`; cada paso posterior al checkout
    lleva `if: ${{ !cancelled() }}`; `setup-node` precede a `npx` y `npm`, y `setup-uv` a `uvx`."""
    if DOC not in trabajos:
        return [f"no existe el trabajo '{DOC}'"]
    bloque = trabajos[DOC]
    lista = pasos(bloque)
    problemas = comprobar_regla_comun_1({DOC: bloque})

    i_checkout = _indice_de_uses(lista, "actions/checkout@")
    problemas += _comprobar_checkout(DOC, lista, i_checkout)
    i_node = _indice_de_uses(lista, "actions/setup-node@")
    i_uv = _indice_de_uses(lista, "astral-sh/setup-uv@")
    i_lychee = _indice_de_uses(lista, "lycheeverse/lychee-action@")

    hitos = {
        "python3 tools/verificar_docs.py": _localizar(lista, VERIFICAR_DOCS),
        "markdownlint-cli2": _localizar(lista, MARKDOWNLINT),
        "vale": _localizar(lista, VALE_SUELTO),
        "lychee-action": (i_lychee, 0) if i_lychee is not None else None,
        "npm ci de mermaid-cli": _localizar(lista, INSTALA_NPM),
        "bucle de mmdc": _localizar(lista, INVOCA_MMDC),
    }
    previo = (-1, -1)
    anterior = "el inicio del trabajo"
    for etiqueta, hito in hitos.items():
        if hito is None:
            problemas.append(
                f"'{DOC}': falta «{etiqueta}» en un paso del trabajo (un paso comentado o de otro trabajo no cuenta)"
            )
        elif hito <= previo:
            problemas.append(f"'{DOC}': «{etiqueta}» debe ir después de «{anterior}»")
        else:
            previo = hito
            anterior = etiqueta
    for paso in lista:
        if re.search(NPM_QUE_RESUELVE, comando(paso).replace("\\\n", " ")):
            problemas.append(
                f"'{DOC}': el paso `{_nombre_del_paso(paso)}` ejecuta `npm install`; en el trabajo solo se instala con "
                "`npm ci` sobre un lockfile (zizmor: adhoc-packages)"
            )

    if i_node is not None:
        con_node = valor_del_paso(lista[i_node], "with") or ""
        if (_entrada_de_with(con_node, "node-version-file") or "").strip("\"'") != ARCHIVO_DE_NODE:
            problemas.append(
                f"'{DOC}': setup-node no declara `node-version-file: {ARCHIVO_DE_NODE}`; sin él la versión de Node "
                "dejaría de ser la del cliente"
            )
    if hitos["markdownlint-cli2"] is not None:
        problemas += _comprobar_markdownlint(lista, hitos["markdownlint-cli2"])
        if i_node is None or i_node > hitos["markdownlint-cli2"][0]:
            problemas.append(
                f"'{DOC}': falta actions/setup-node antes de markdownlint-cli2; npx necesita Node"
            )
    if hitos["vale"] is not None:
        problemas += _comprobar_vale(lista, hitos["vale"])
        if i_uv is None or i_uv > hitos["vale"][0]:
            problemas.append(f"'{DOC}': falta astral-sh/setup-uv antes de Vale; uvx necesita uv")
    if i_lychee is not None:
        problemas += _comprobar_paso_de_lychee(DOC, lista[i_lychee])
    if hitos["bucle de mmdc"] is not None:
        problemas += _comprobar_mermaid(
            lista, hitos["npm ci de mermaid-cli"], hitos["bucle de mmdc"]
        )
        instalacion = hitos["npm ci de mermaid-cli"]
        if instalacion is not None and instalacion > hitos["bucle de mmdc"]:
            problemas.append(f"'{DOC}': mmdc se ejecuta antes de instalar mermaid-cli")
        if instalacion is not None and (i_node is None or i_node > instalacion[0]):
            problemas.append(
                f"'{DOC}': falta actions/setup-node antes de instalar mermaid-cli; npm necesita Node"
            )

    return problemas + _comprobar_cada_paso_y_el_trabajo(bloque, lista, i_checkout)


def _comprobar_cada_paso_y_el_trabajo(
    bloque: list[str], lista: list[list[str]], i_checkout: int | None
) -> list[str]:
    """Reglas comunes 6, 7 y 9 en cada paso posterior al checkout, y lo que no debe declarar el trabajo: `continue-on-error`,
    `secrets.` y un `working-directory` por omisión (que movería sin avisar el `npm ci`, el bucle de mmdc y los verificadores)."""
    problemas: list[str] = []
    for k, paso in enumerate(lista):
        if i_checkout is not None and k <= i_checkout:
            continue
        condicion = valor_del_paso(paso, "if")
        if re.sub(r"\s+", "", (condicion or "").strip("\"'")) not in IF_DE_LAS_COMPUERTAS:
            problemas.append(
                f"'{DOC}': el paso `{_nombre_del_paso(paso)}` no declara `if: ${{{{ !cancelled() }}}}` (regla común 6); "
                "tras un fallo anterior no correría y se vería solo el primer fallo"
            )
        if ENMASCARA_EL_FALLO.search(_orden_sin_cadenas(comando(paso))):
            problemas.append(
                f"'{DOC}': el paso `{_nombre_del_paso(paso)}` enmascara su fallo con `|| true` (regla común 7)"
            )
        if (
            _tiene_tuberia(comando(paso))
            and (valor_del_paso(paso, "shell") or "").strip("\"'") != "bash"
        ):
            problemas.append(
                f"'{DOC}': el paso `{_nombre_del_paso(paso)}` usa una tubería sin `shell: bash` (regla común 9)"
            )
    if any(re.match(r"\s*(?:-\s+)?[\"']?continue-on-error[\"']?\s*:", linea) for linea in bloque):
        problemas.append(
            f"'{DOC}': declara `continue-on-error`; una compuerta que no falla está desactivada"
        )
    if LEE_SECRETOS.search("\n".join(bloque)):
        problemas.append(f"'{DOC}': lee `secrets.`; ningún workflow del proyecto usa secretos")
    por_omision = directorio_por_omision(bloque)
    if por_omision not in (None, "."):
        problemas.append(
            f"'{DOC}': declara `defaults.run.working-directory: {por_omision}`; los pasos correrían fuera de la raíz y el "
            "`working-directory` de cada uno ya no diría dónde corre"
        )
    return problemas


def comprobar_tc65_texto(texto: str) -> list[str]:
    """TC-65 sobre el texto de `ci.yml`: la estructura del trabajo y el fijado por SHA de sus acciones."""
    problemas = comprobar_tc65(extraer_trabajos(texto)) + comprobar_acciones_fijadas(texto, DOC)
    if re.search(r"(?m)^defaults\s*:", sin_comentarios(texto)):
        problemas.append(
            f"ci.yml: declara `defaults:` a nivel de flujo; se aplicaría también al trabajo '{DOC}' sin que sus pasos lo digan"
        )
    return problemas


# ---------------------------------------------------------------------------------------------------------
# Comportamiento: se ejecuta el `run:` real de un paso con bash (F001)
#
# Las comprobaciones de arriba leen el texto del paso y no pueden ver su flujo: `fallos=1` seguido de `fallos=0`,
# un `exit 0` antes de la marca, un `continue` antes de mmdc, `while false` o un `codigo=0` tras el `cat` de Vale
# dejan el texto "correcto" y el paso inútil. Aquí el `run:` se extrae de `ci.yml`, se ejecuta con `bash -eo pipefail`
# (como `shell: bash` en GitHub) sobre un árbol temporal y con un `mmdc` y un `uvx` de mentira, y se comprueba qué
# código de salida y qué anotaciones produce. Siguen vivas las comprobaciones estáticas de lo que el programa de
# mentira no ve: `-p`, el alcance, la ruta del binario y las versiones.
#
# Límite conocido (F006), no exigido: si ningún Markdown del alcance tiene un bloque `mermaid`, el bucle no corre y
# el paso termina en verde. Hoy es el comportamiento del diseño (no hay nada que validar) y las pruebas no lo fijan.
# ---------------------------------------------------------------------------------------------------------

PASO_DE_MERMAID = "Diagramas con mermaid-cli"
PASO_DE_VALE = "Prosa con Vale"
RUTA_DE_MMDC = ".github/mermaid/node_modules/.bin/mmdc"

# mmdc de mentira: valida el archivo que recibe con `-i`; sale 1 si contiene `INVALID`, 2 si no recibe un archivo legible.
MMDC_DE_MENTIRA = """#!/usr/bin/env bash
entrada=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -i) entrada="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [ -z "$entrada" ] || [ ! -f "$entrada" ]; then
  echo "mmdc de mentira: falta -i con un archivo legible" >&2
  exit 2
fi
if grep -q INVALID "$entrada"; then
  exit 1
fi
exit 0
"""

# uvx de mentira: imprime lo que dicte `CIMENTA_VALE_SALIDA` y sale con `CIMENTA_VALE_CODIGO`.
UVX_DE_MENTIRA = """#!/usr/bin/env bash
printf '%s' "$CIMENTA_VALE_SALIDA"
exit "${CIMENTA_VALE_CODIGO:-0}"
"""

DIAGRAMA_VALIDO = "# Diagrama\n\n```mermaid\ngraph TD\n  A --> B\n```\n"
DIAGRAMA_INVALIDO = "# Diagrama\n\n```mermaid\nINVALID\n```\n"
ARBOL_BASE = {
    "docs/leeme.md": "# Docs\n",
    "sdd/leeme.md": "# SDD\n",
    "README.md": "# Léeme\n",
    "CLAUDE.md": "# Claude\n",
    "tools/README.md": "# Tools\n",
}
ALERTA_DE_VALE = "docs/a.md:3:1:Vale.Terms:Usa 'cadena' en lugar de 'string'."


def _run_del_paso(texto_ci: str, nombre: str) -> str | None:
    """El `run:` del paso `nombre` del trabajo `documentacion` de `ci.yml`, o `None` si no existe."""
    bloque = extraer_trabajos(texto_ci).get(DOC)
    for paso in pasos(bloque) if bloque else []:
        if valor_del_paso(paso, "name") == nombre and comando(paso):
            return comando(paso)
    return None


def _desviaciones(
    nombre: str,
    resultado: tuple[int, str],
    codigo: int,
    presentes: tuple[str, ...],
    ausentes: tuple[str, ...],
) -> list[str]:
    salida_del_paso, salida = resultado
    problemas: list[str] = []
    if salida_del_paso != codigo:
        problemas.append(
            f"escenario «{nombre}»: el paso salió con {salida_del_paso} y debía salir con {codigo}; salida: {salida[-400:]!r}"
        )
    problemas += [
        f"escenario «{nombre}»: la salida no contiene {texto!r}: {salida[-400:]!r}"
        for texto in presentes
        if texto not in salida
    ]
    problemas += [
        f"escenario «{nombre}»: la salida contiene {texto!r}"
        for texto in ausentes
        if texto in salida
    ]
    return problemas


def _anotacion(archivo: str) -> str:
    return f"::error file={archivo}::diagrama Mermaid inválido"


# (nombre, archivos del escenario, código de salida esperado, anotaciones que deben salir, anotaciones que no)
ESCENARIOS_DE_MERMAID: tuple[
    tuple[str, dict[str, str], int, tuple[str, ...], tuple[str, ...]], ...
] = (
    (
        "un diagrama inválido en docs",
        {"docs/malo.md": DIAGRAMA_INVALIDO},
        1,
        (_anotacion("docs/malo.md"),),
        (),
    ),
    (
        "solo diagramas válidos",
        {"docs/bueno.md": DIAGRAMA_VALIDO, "README.md": DIAGRAMA_VALIDO},
        0,
        (),
        ("::error",),
    ),
    (
        "inválido en docs y válido después, en sdd",
        {"docs/malo.md": DIAGRAMA_INVALIDO, "sdd/bueno.md": DIAGRAMA_VALIDO},
        1,
        (_anotacion("docs/malo.md"),),
        (_anotacion("sdd/bueno.md"),),
    ),
    (
        "válido en README y inválido en sdd",
        {"README.md": DIAGRAMA_VALIDO, "sdd/malo.md": DIAGRAMA_INVALIDO},
        1,
        (_anotacion("sdd/malo.md"),),
        (_anotacion("README.md"),),
    ),
    (
        "dos archivos inválidos, cada uno con su anotación",
        {"docs/malo.md": DIAGRAMA_INVALIDO, "tools/README.md": DIAGRAMA_INVALIDO},
        1,
        (_anotacion("docs/malo.md"), _anotacion("tools/README.md")),
        (),
    ),
    (
        "un Markdown sin bloque mermaid no se valida",
        {"docs/texto.md": "# Texto\n\nINVALID, pero sin diagrama.\n"},
        0,
        (),
        ("::error",),
    ),
)


def comprobar_comportamiento_de_mermaid(texto_ci: str) -> list[str]:
    """Ejecuta el `run:` real del paso de mermaid-cli con un `mmdc` de mentira y devuelve cada escenario que no se cumple."""
    run = _run_del_paso(texto_ci, PASO_DE_MERMAID)
    if run is None:
        return [f"'{DOC}': no hay un paso «{PASO_DE_MERMAID}» con `run:` que ejecutar"]
    problemas: list[str] = []
    for nombre, archivos, codigo, presentes, ausentes in ESCENARIOS_DE_MERMAID:
        resultado = ejecutar_en_bash(
            run, archivos={**ARBOL_BASE, **archivos}, ejecutables={RUTA_DE_MMDC: MMDC_DE_MENTIRA}
        )
        problemas += _desviaciones(nombre, resultado, codigo, presentes, ausentes)
    return problemas


# (nombre, salida de Vale, código de Vale, código esperado del paso, la alerta debe verse en la salida)
ESCENARIOS_DE_VALE: tuple[tuple[str, str, int, int, bool], ...] = (
    (
        "una alerta con código 0 (los avisos no cambian el código)",
        ALERTA_DE_VALE + "\n",
        0,
        1,
        True,
    ),
    ("sin salida y con código 0", "", 0, 0, False),
    ("sin salida y con código 1 (error de Vale)", "", 1, 1, False),
    ("una alerta con código 1", ALERTA_DE_VALE + "\n", 1, 1, True),
)


def comprobar_comportamiento_de_vale(texto_ci: str) -> list[str]:
    """Ejecuta el `run:` real del paso de Vale con un `uvx` de mentira y devuelve cada escenario que no se cumple."""
    run = _run_del_paso(texto_ci, PASO_DE_VALE)
    if run is None:
        return [f"'{DOC}': no hay un paso «{PASO_DE_VALE}» con `run:` que ejecutar"]
    problemas: list[str] = []
    for nombre, salida_de_vale, codigo_de_vale, codigo, se_ve in ESCENARIOS_DE_VALE:
        resultado = ejecutar_en_bash(
            run,
            archivos=ARBOL_BASE,
            en_path={"uvx": UVX_DE_MENTIRA},
            entorno={
                "CIMENTA_VALE_SALIDA": salida_de_vale,
                "CIMENTA_VALE_CODIGO": str(codigo_de_vale),
            },
        )
        problemas += _desviaciones(
            nombre,
            resultado,
            codigo,
            (ALERTA_DE_VALE,) if se_ve else (),
            () if se_ve else (ALERTA_DE_VALE,),
        )
    return problemas


def _columna(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


def _claves_de_on(disparadores: str) -> set[str]:
    """Los disparadores de primer nivel de `on:`: las claves del mapa, o los nombres de la forma en línea (`on: [a, b]`) o en lista."""
    lineas = disparadores.splitlines()
    claves = set(re.findall(r"[\w-]+", lineas[0])) if lineas else set()
    cuerpo = [linea for linea in lineas[1:] if linea.strip()]
    if not cuerpo:
        return claves
    primera_columna = min(_columna(linea) for linea in cuerpo)
    for linea in cuerpo:
        if _columna(linea) != primera_columna:
            continue
        encontrada = re.match(r"\s*(?:-\s+)?([\w-]+)\s*(?::|$)", linea)
        if encontrada:
            claves.add(encontrada.group(1))
    return claves


def _concurrencia_sin_cancelar(texto: str) -> bool:
    """`concurrency:` a nivel de flujo con un `group` y `cancel-in-progress: false`."""
    lineas = sin_comentarios(texto).splitlines()
    for k, linea in enumerate(lineas):
        if not re.fullmatch(r"concurrency\s*:", linea):
            continue
        cuerpo = []
        for siguiente in lineas[k + 1 :]:
            if _columna(siguiente) == 0:
                break
            cuerpo.append(siguiente.strip())
        return any(re.fullmatch(r"group:\s*\S.*", c) for c in cuerpo) and any(
            re.fullmatch(r"""cancel-in-progress:\s*["']?false["']?""", c) for c in cuerpo
        )
    return False


def _comprobar_disparadores_de_enlaces(texto: str) -> list[str]:
    """Cómo se dispara `enlaces.yml`: `schedule` con un único `cron` semanal, `workflow_dispatch`, `on:` exacto y `concurrency`."""
    problemas: list[str] = []
    disparadores = _disparadores(texto)
    if not re.search(r"(?<![\w-])schedule\s*:", disparadores):
        problemas.append(
            "enlaces.yml: no declara el disparador `schedule`; el detector de enlaces no correría solo"
        )
    else:
        crons = [c.strip() for c in re.findall(r"""\bcron:\s*["']?([^"'\n]*)""", disparadores)]
        if not crons:
            problemas.append("enlaces.yml: `schedule` no declara ningún `cron`")
        elif len(crons) > 1:
            problemas.append(
                f"enlaces.yml: declara {len(crons)} crons; debe ser uno solo, de un día por semana"
            )
        for cron in crons:
            campos = cron.split()
            if len(campos) != 5:
                problemas.append(f"enlaces.yml: el cron `{cron}` no tiene cinco campos")
            elif re.search(r"[,\-*/]", campos[4]):
                problemas.append(
                    f"enlaces.yml: el cron `{cron}` corre más de un día por semana (día de la semana `{campos[4]}`)"
                )
            if cron != CRON_SEMANAL:
                problemas.append(
                    f"enlaces.yml: el cron debe ser `{CRON_SEMANAL}` (lunes, un día por semana) y es `{cron}`"
                )
    if not re.search(r"(?<![\w-])workflow_dispatch(?![\w-])", disparadores):
        problemas.append(
            "enlaces.yml: no declara `workflow_dispatch`; no se puede lanzar a mano tras fusionar"
        )
    disparadores_declarados = _claves_de_on(disparadores)
    if disparadores_declarados != DISPARADORES_DE_ENLACES:
        problemas.append(
            f"enlaces.yml: `on:` declara {sorted(disparadores_declarados)} y debe declarar exactamente "
            f"{sorted(DISPARADORES_DE_ENLACES)}; otro disparador lo correría en cada PR o con permisos de otro contexto"
        )
    if not _concurrencia_sin_cancelar(texto):
        problemas.append(
            "enlaces.yml: no declara `concurrency` con un `group` y `cancel-in-progress: false`; una corrida a mano que "
            "coincida con el cron cancelaría la otra, o se solaparían"
        )
    return problemas


def _comprobar_trabajos_de_enlaces(texto: str) -> list[str]:
    """Qué hace `enlaces.yml` una vez disparado: permisos de solo lectura, sin secretos ni `pull_request_target`, y un trabajo con
    checkout sin credenciales persistidas y `lychee-action` con la configuración del PR; todas las acciones fijadas por SHA."""
    problemas: list[str] = []
    activo = sin_comentarios(texto)
    permisos = _permisos_de_flujo(texto)
    if permisos is None:
        problemas.append("enlaces.yml: no declara `permissions:` a nivel de flujo")
    elif not any(re.fullmatch(r"contents:\s*read", linea) for linea in permisos):
        problemas.append("enlaces.yml: `permissions:` a nivel de flujo no declara `contents: read`")
    if re.search(r":\s*[\"']?write\b", activo):
        problemas.append(
            "enlaces.yml: pide un permiso de escritura; un detector de enlaces solo lee"
        )
    if re.search(r"\bpull_request_target\b", activo):
        problemas.append(
            "enlaces.yml: usa pull_request_target, que corre con secretos sobre código de una bifurcación"
        )
    if LEE_SECRETOS.search(activo):
        problemas.append("enlaces.yml: lee secrets.*; el pipeline no lee secretos (regla común 5)")
    if re.search(r"""^\s*(?:-\s+)?["']?continue-on-error["']?\s*:""", activo, flags=re.MULTILINE):
        problemas.append(
            "enlaces.yml: declara `continue-on-error`; una compuerta que no falla está desactivada"
        )

    trabajos = extraer_trabajos(texto)
    problemas += comprobar_regla_comun_1(trabajos)
    encontrado = False
    for id_trabajo, bloque in trabajos.items():
        lista = pasos(bloque)
        i_lychee = _indice_de_uses(lista, "lycheeverse/lychee-action@")
        if i_lychee is None:
            continue
        encontrado = True
        i_checkout = _indice_de_uses(lista, "actions/checkout@")
        if i_checkout is not None and i_checkout > i_lychee:
            problemas.append(f"'{id_trabajo}': actions/checkout va después de lychee-action")
        problemas += _comprobar_checkout(id_trabajo, lista, i_checkout)
        problemas += _comprobar_paso_de_lychee(id_trabajo, lista[i_lychee])
    if not encontrado:
        problemas.append("enlaces.yml: ningún trabajo usa lycheeverse/lychee-action")
    for id_trabajo in trabajos:
        problemas += comprobar_acciones_fijadas(texto, id_trabajo)
    return problemas


def comprobar_tc64(texto: str) -> list[str]:
    """CA-14 esc. 1 · TC-64. `enlaces.yml` se dispara con `schedule` y un único `cron` de un día por semana (`0 13 * * 1`) y con
    `workflow_dispatch`; declara `permissions: contents: read` a nivel de flujo sin escritura alguna; no usa `pull_request_target`
    ni `secrets.`; tiene un trabajo con checkout (`persist-credentials: false`) y `lychee-action` con la configuración del PR;
    todas sus acciones van fijadas por SHA; corredor `ubuntu-24.04` y `timeout-minutes`."""
    return _comprobar_disparadores_de_enlaces(texto) + _comprobar_trabajos_de_enlaces(texto)


def _configuracion_de_lychee(texto: str) -> tuple[str, tuple[str, ...], str, str] | None:
    """La acción (`uses:` con su SHA), los `args` ordenados, `fail` y `lycheeVersion` del trabajo que usa lychee-action."""
    for bloque in extraer_trabajos(texto).values():
        lista = pasos(bloque)
        i_lychee = _indice_de_uses(lista, "lycheeverse/lychee-action@")
        if i_lychee is not None:
            con = valor_del_paso(lista[i_lychee], "with") or ""
            return (
                valor_del_paso(lista[i_lychee], "uses") or "",
                tuple(sorted(_palabras(_entrada_de_with(con, "args") or ""))),
                (_entrada_de_with(con, "fail") or "").strip("\"'").lower(),
                (_entrada_de_with(con, "lycheeVersion") or "").strip("\"'"),
            )
    return None


def comprobar_misma_configuracion_de_lychee(ci: str, enlaces: str) -> list[str]:
    """CA-14 esc. 1 · TC-64. El detector semanal lleva exactamente la configuración del PR: la misma acción (el mismo SHA), mismos
    `args` (sin importar el orden ni las comillas), mismo `fail` y misma versión de lychee; así lo que el cron encuentra es lo que el PR habría visto."""
    del_pr = _configuracion_de_lychee(ci)
    semanal = _configuracion_de_lychee(enlaces)
    if del_pr is None:
        return [
            "ci.yml: ningún trabajo usa lycheeverse/lychee-action; no hay configuración con la que comparar"
        ]
    if semanal is None:
        return [
            "enlaces.yml: ningún trabajo usa lycheeverse/lychee-action; no hay configuración que comparar"
        ]
    if del_pr != semanal:
        return [
            f"enlaces.yml: la configuración de lychee difiere de la del PR: PR {del_pr}, enlaces.yml {semanal}"
        ]
    return []


# ---------------------------------------------------------------------------------------------------------
# Texto sintético válido
# ---------------------------------------------------------------------------------------------------------

SHA_CHECKOUT = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SHA_SETUP_NODE = "949feb2413d6458794dcd2491c4babbbce0c15c1"
SHA_SETUP_UV = "68559e99cc807c1eb7e9238fd43a15bba460eec2"
SHA_LYCHEE = "e7477775783ea5526144ba13e8db5eec57747ce8"

PASO_CHECKOUT_D5 = f"      - uses: actions/checkout@{SHA_CHECKOUT} # v7.0.1\n        with:\n          persist-credentials: false\n"
PASO_SETUP_NODE_D5 = (
    f"      - uses: actions/setup-node@{SHA_SETUP_NODE} # v7.1.0\n"
    + GUARDA_DE_PASO
    + "        with:\n          node-version-file: frontend/package.json\n"
)
PASO_MARKDOWNLINT = (
    "      - name: Markdown con markdownlint-cli2\n"
    + GUARDA_DE_PASO
    + '        run: npx --yes markdownlint-cli2@0.24.0 "docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md\n'
)
PASO_SETUP_UV_D5 = f"      - uses: astral-sh/setup-uv@{SHA_SETUP_UV} # v10.3.3\n" + GUARDA_DE_PASO

LINEA_CODIGO_DE_VALE = "          codigo=0\n"
LINEA_VALE = (
    "          uvx --from vale==3.25.1.0 vale --output=line docs sdd README.md CLAUDE.md tools/README.md"
    ' > "$RUNNER_TEMP/vale.txt" || codigo=$?\n'
)
LINEA_CAT = '          cat "$RUNNER_TEMP/vale.txt"\n'
LINEA_GUARDA = '          [ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]\n'
PASO_VALE = (
    "      - name: Prosa con Vale\n"
    + GUARDA_DE_PASO
    + "        run: |\n"
    + LINEA_CODIGO_DE_VALE
    + LINEA_VALE
    + LINEA_CAT
    + LINEA_GUARDA
)

ARGS_DE_LYCHEE = "          args: --config lychee.toml --no-progress 'docs/**/*.md' 'sdd/**/*.md' README.md CLAUDE.md tools/README.md\n"
CON_DE_LYCHEE = (
    "        with:\n" + ARGS_DE_LYCHEE + "          lycheeVersion: v0.24.2\n          fail: true\n"
)
PASO_LYCHEE = (
    "      - name: Enlaces con lychee\n"
    + GUARDA_DE_PASO
    + f"        uses: lycheeverse/lychee-action@{SHA_LYCHEE} # v2.9.0\n"
    + CON_DE_LYCHEE
)

LINEAS_INSTALAR_MMDC = "        working-directory: .github/mermaid\n        run: npm ci\n"
PASO_INSTALAR_MMDC = "      - name: Instalar mermaid-cli\n" + GUARDA_DE_PASO + LINEAS_INSTALAR_MMDC
LLAMADA_A_MMDC = (
    "            if ! .github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json"
    ' -i "$archivo" -o "$RUNNER_TEMP/mermaid/$n.md"; then\n'
)
FIN_DEL_BUCLE = '          if [ "$fallos" -ne 0 ]; then\n            exit 1\n          fi\n'
LINEAS_DEL_BUCLE = (
    "          fallos=0\n"
    "          n=0\n"
    '          mkdir -p "$RUNNER_TEMP/mermaid"\n'
    "          while IFS= read -r archivo; do\n"
    "            n=$((n + 1))\n"
    + LLAMADA_A_MMDC
    + '              echo "::error file=$archivo::diagrama Mermaid inválido"\n'
    "              fallos=1\n"
    "            fi\n"
    "          done < <(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md)\n"
    + FIN_DEL_BUCLE
)
PASO_MERMAID = (
    "      - name: Diagramas con mermaid-cli\n"
    + GUARDA_DE_PASO
    + "        run: |\n"
    + LINEAS_DEL_BUCLE
)

DOCUMENTACION_D5 = (
    "  documentacion:\n"
    "    name: Documentación · verificador propio, markdownlint, Vale, lychee y mermaid-cli\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 15\n"
    "    steps:\n"
    + PASO_CHECKOUT_D5
    + PASO_VERIFICAR_DOCS_G
    + PASO_SETUP_NODE_D5
    + PASO_MARKDOWNLINT
    + PASO_SETUP_UV_D5
    + PASO_VALE
    + PASO_LYCHEE
    + PASO_INSTALAR_MMDC
    + PASO_MERMAID
)

CI_D5 = sustituir(
    CI_B3,
    DOCUMENTACION_SINTETICA.replace(PASO_VERIFICAR_DOCS, PASO_VERIFICAR_DOCS_G),
    DOCUMENTACION_D5,
)

PASO_LYCHEE_DE_ENLACES = (
    "      - name: Enlaces con lychee\n"
    + f"        uses: lycheeverse/lychee-action@{SHA_LYCHEE} # v2.9.0\n"
    + CON_DE_LYCHEE
)
CONCURRENCIA_DE_ENLACES = "concurrency:\n  group: enlaces\n  cancel-in-progress: false\n"
ENLACES_D5 = (
    "name: Enlaces\n"
    "on:\n"
    "  schedule:\n"
    '    - cron: "0 13 * * 1"\n'
    "  workflow_dispatch:\n"
    "permissions:\n"
    "  contents: read\n" + CONCURRENCIA_DE_ENLACES + "jobs:\n"
    "  enlaces:\n"
    "    name: Enlaces · detector semanal con lychee\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 15\n"
    "    steps:\n" + PASO_CHECKOUT_D5 + PASO_LYCHEE_DE_ENLACES
)

INTEGRIDAD_SINTETICA = "sha512-" + "A" * 86 + "=="
PACKAGE_JSON_BASE = {
    "name": "cimenta-mermaid",
    "private": True,
    "dependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC},
}
PACKAGE_LOCK_BASE = {
    "name": "cimenta-mermaid",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {
            "name": "cimenta-mermaid",
            "dependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC},
        },
        ENTRADA_DEL_LOCK: {
            "version": VERSION_DE_MMDC,
            "resolved": f"https://registry.npmjs.org/{PAQUETE_DE_MMDC}/-/mermaid-cli-{VERSION_DE_MMDC}.tgz",
            "integrity": INTEGRIDAD_SINTETICA,
            "license": "MIT",
        },
    },
}
_BORRAR = object()


def json_mutado(base: dict, ruta: tuple[str, ...], valor: object = _BORRAR) -> str:
    """El JSON de `base` con el valor de `ruta` cambiado por `valor` (o la clave borrada), como texto. Falla si no cambia nada."""
    copia = copy.deepcopy(base)
    destino = copia
    for clave in ruta[:-1]:
        destino = destino[clave]
    if valor is _BORRAR:
        del destino[ruta[-1]]
    else:
        destino[ruta[-1]] = valor
    if copia == base:
        raise AssertionError(f"el mutante no cambia nada: {ruta!r} ya vale {valor!r}")
    return json.dumps(copia, indent=2)


PACKAGE_JSON_D5 = json.dumps(PACKAGE_JSON_BASE, indent=2)
PACKAGE_LOCK_D5 = json.dumps(PACKAGE_LOCK_BASE, indent=2)
GITIGNORE_D5 = "__pycache__/\n.env\nnode_modules/\ndist/\n"
PUPPETEER_CONFIG_D5 = '{"args": ["--no-sandbox"]}'


def sin_guarda(paso: str) -> str:
    """El paso sin su línea `if: ${{ !cancelled() }}`."""
    return sustituir(paso, GUARDA_DE_PASO, "")


def en_documentacion(viejo: str, nuevo: str) -> str:
    """`CI_D5` con `viejo` cambiado por `nuevo`, solo dentro del trabajo `documentacion`."""
    return mutar(CI_D5, DOC, viejo, nuevo)


# ---------------------------------------------------------------------------------------------------------
# Pruebas de los mutantes: cada comprobación se pone en rojo por la razón esperada
# ---------------------------------------------------------------------------------------------------------


class PruebasDeMutantesDeLaFilaD5ParaTC65(unittest.TestCase):
    """TC-65: los pasos de `documentacion` se comentan, se mueven, se reordenan o se desvían, y el caso queda en rojo.
    Las pruebas de este grupo trabajan sobre texto sintético: su verde es el de la comprobación, no el de `ci.yml`."""

    def test_tc65_mutantes_el_texto_valido_pasa_el_caso_y_las_reglas_comunes(self):
        """CA-13 esc. 1 · TC-65 — control: la base pasa el caso y las reglas comunes; sin esto un rojo podría ser del texto base."""
        self.assertEqual(comprobar_tc65_texto(CI_D5), [])
        trabajos = extraer_trabajos(CI_D5)
        self.assertEqual(comprobar_trabajo_documentacion(trabajos), [])
        for regla in (
            comprobar_regla_comun_1,
            comprobar_regla_comun_6,
            comprobar_regla_comun_7,
            comprobar_regla_comun_8,
            comprobar_regla_comun_9,
        ):
            with self.subTest(regla=regla.__name__):
                self.assertEqual(regla(trabajos), [])

    def test_tc65_mutantes_formas_equivalentes_validas_siguen_en_verde(self):
        """CA-13 esc. 1 · TC-65 — otra forma legítima de escribir el mismo paso no rompe el caso (un rojo falso bloquearía la fila)."""
        vale_con_if = LINEA_GUARDA.replace(
            '[ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]',
            'if [ "${codigo}" -ne 0 ] || [ -s "${RUNNER_TEMP}/vale.txt" ]; then exit 1; fi',
        )
        vale_continuado = (
            "          uvx --from vale==3.25.1.0 vale \\\n"
            "            --output=line \\\n"
            "            docs sdd README.md CLAUDE.md tools/README.md \\\n"
            '            > "$RUNNER_TEMP/vale.txt" || codigo=$?\n'
        )
        bucle_for = (
            "          fallos=0\n"
            "          for archivo in $(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md); do\n"
            "            .github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json"
            ' -i "$archivo" -o "$RUNNER_TEMP/mermaid.md" || { echo "::error file=$archivo::diagrama Mermaid inválido"; fallos=1; }\n'
            "          done\n"
            '          [ "$fallos" -eq 0 ] || exit 1\n'
        )
        validos = {
            "guarda de salida vacía con if y exit 1": en_documentacion(LINEA_GUARDA, vale_con_if),
            "Vale con continuaciones de línea": en_documentacion(LINEA_VALE, vale_continuado),
            "markdownlint con npx -y": en_documentacion("npx --yes", "npx -y"),
            "markdownlint con comillas simples": en_documentacion(
                '"docs/**/*.md" "sdd/**/*.md"', "'docs/**/*.md' 'sdd/**/*.md'"
            ),
            "args de lychee en bloque plegado": en_documentacion(
                ARGS_DE_LYCHEE,
                "          args: >-\n"
                "            --config lychee.toml --no-progress\n"
                "            'docs/**/*.md' 'sdd/**/*.md'\n"
                "            README.md CLAUDE.md tools/README.md\n",
            ),
            "lycheeVersion entre comillas": en_documentacion(
                "lycheeVersion: v0.24.2", "lycheeVersion: 'v0.24.2'"
            ),
            "npm ci con --prefix en lugar de working-directory": en_documentacion(
                LINEAS_INSTALAR_MMDC, "        run: npm ci --prefix .github/mermaid\n"
            ),
            "npm ci con --prefix= y comillas": en_documentacion(
                LINEAS_INSTALAR_MMDC, '        run: npm ci --prefix=".github/mermaid"\n'
            ),
            "working-directory con ./ y barra final": en_documentacion(
                "working-directory: .github/mermaid", 'working-directory: "./.github/mermaid/"'
            ),
            "npm ci con --no-audit --no-fund": en_documentacion(
                "run: npm ci\n", "run: npm ci --no-audit --no-fund\n"
            ),
            "mmdc bajo $GITHUB_WORKSPACE": en_documentacion(
                "if ! .github/mermaid/node_modules/.bin/mmdc",
                'if ! "$GITHUB_WORKSPACE/.github/mermaid/node_modules/.bin/mmdc"',
            ),
            "mmdc bajo ${GITHUB_WORKSPACE}": en_documentacion(
                "if ! .github/mermaid/node_modules/.bin/mmdc",
                "if ! ${GITHUB_WORKSPACE}/.github/mermaid/node_modules/.bin/mmdc",
            ),
            "mmdc con ruta ./ entre comillas": en_documentacion(
                "if ! .github/mermaid/node_modules/.bin/mmdc",
                'if ! "./.github/mermaid/node_modules/.bin/mmdc"',
            ),
            "bucle for con || { ...; } y exit 1 en una línea": en_documentacion(
                LINEAS_DEL_BUCLE, bucle_for
            ),
            "guarda de Vale con las pruebas en orden inverso": en_documentacion(
                LINEA_GUARDA, '          [ ! -s "$RUNNER_TEMP/vale.txt" ] && [ "$codigo" -eq 0 ]\n'
            ),
            "guarda de Vale con if en varias líneas y las pruebas en orden inverso": en_documentacion(
                LINEA_GUARDA,
                '          if [ -s "$RUNNER_TEMP/vale.txt" ] || [ "$codigo" -ne 0 ]; then\n'
                "            exit 1\n"
                "          fi\n",
            ),
            "salida del bucle con -eq 1": en_documentacion(
                '[ "$fallos" -ne 0 ]', '[ "$fallos" -eq 1 ]'
            ),
            "salida del bucle con && exit 1": en_documentacion(
                FIN_DEL_BUCLE, '          [ "${fallos}" -ne 0 ] && exit 1\n'
            ),
            "la variable de fallos con otro nombre": en_documentacion(
                LINEAS_DEL_BUCLE, LINEAS_DEL_BUCLE.replace("fallos", "errores")
            ),
            "grep -R": en_documentacion("grep -rl", "grep -Rl"),
            "grep -r -l": en_documentacion("grep -rl", "grep -r -l"),
            "la salida de mmdc descartada con 2>&1 dentro del if": en_documentacion(
                '-o "$RUNNER_TEMP/mermaid/$n.md"; then',
                '-o "$RUNNER_TEMP/mermaid/$n.md" > /dev/null 2>&1; then',
            ),
            "node-version-file entre comillas": en_documentacion(
                "node-version-file: frontend/package.json",
                'node-version-file: "frontend/package.json"',
            ),
            "un paso de más entre Vale y lychee": en_documentacion(
                PASO_LYCHEE,
                "      - run: echo intermedio\n        if: ${{ !cancelled() }}\n" + PASO_LYCHEE,
            ),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc65_texto(texto), [])
                self.assertEqual(comprobar_regla_comun_7(extraer_trabajos(texto)), [])

    def test_tc65_mutantes_cada_paso_comentado_o_en_otro_trabajo_no_cuenta(self):
        """CA-13 esc. 1 y CA-16 esc. 1 · TC-65 — comentar un paso o llevarlo a otro trabajo lo quita de `documentacion`."""
        casos = {
            "trabajo ausente": (
                sustituir(CI_D5, "\n  documentacion:\n", "\n  docs:\n"),
                "no existe el trabajo",
            ),
            "verificar_docs comentado": (
                comentar(CI_D5, DOC, PASO_VERIFICAR_DOCS_G),
                "python3 tools/verificar_docs.py",
            ),
            "markdownlint comentado": (
                comentar(CI_D5, DOC, PASO_MARKDOWNLINT),
                "«markdownlint-cli2»",
            ),
            "Vale comentado": (comentar(CI_D5, DOC, PASO_VALE), "«vale»"),
            "lychee comentado": (comentar(CI_D5, DOC, PASO_LYCHEE), "«lychee-action»"),
            "instalación de mermaid-cli comentada": (
                comentar(CI_D5, DOC, PASO_INSTALAR_MMDC),
                "npm ci de mermaid-cli",
            ),
            "bucle de mmdc comentado": (comentar(CI_D5, DOC, PASO_MERMAID), "«bucle de mmdc»"),
            "markdownlint movido a workflows": (
                mover(CI_D5, DOC, "workflows", PASO_MARKDOWNLINT, PASO_SETUP_UV),
                "«markdownlint-cli2»",
            ),
            "Vale movido a herramientas": (
                mover(CI_D5, DOC, "herramientas", PASO_VALE, PASO_SETUP_UV),
                "«vale»",
            ),
            "lychee movido a workflows": (
                mover(CI_D5, DOC, "workflows", PASO_LYCHEE, PASO_SETUP_UV),
                "«lychee-action»",
            ),
            "bucle de mmdc movido a dependencias": (
                mover(CI_D5, DOC, "dependencias", PASO_MERMAID, PASO_SETUP_UV),
                "«bucle de mmdc»",
            ),
            "el comando solo en un name": (
                en_documentacion(
                    PASO_MARKDOWNLINT,
                    "      - name: npx --yes markdownlint-cli2@0.24.0\n"
                    + GUARDA_DE_PASO
                    + "        run: echo omitido\n",
                ),
                "«markdownlint-cli2»",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_el_orden_de_los_pasos_se_conserva(self):
        """CA-13 esc. 1 · TC-65 — verificar_docs, markdownlint, Vale, lychee y mmdc, en ese orden; las herramientas, tras su preparación."""
        casos = {
            "Vale antes que markdownlint": (
                en_documentacion(
                    PASO_MARKDOWNLINT + PASO_SETUP_UV_D5 + PASO_VALE,
                    PASO_SETUP_UV_D5 + PASO_VALE + PASO_MARKDOWNLINT,
                ),
                "«vale» debe ir después de «markdownlint-cli2»",
            ),
            "lychee antes que Vale": (
                en_documentacion(PASO_VALE + PASO_LYCHEE, PASO_LYCHEE + PASO_VALE),
                "«lychee-action» debe ir después de «vale»",
            ),
            "mermaid-cli antes que lychee": (
                en_documentacion(
                    PASO_LYCHEE + PASO_INSTALAR_MMDC + PASO_MERMAID,
                    PASO_INSTALAR_MMDC + PASO_MERMAID + PASO_LYCHEE,
                ),
                "«npm ci de mermaid-cli» debe ir después de «lychee-action»",
            ),
            "el bucle antes de instalar mermaid-cli": (
                en_documentacion(
                    PASO_INSTALAR_MMDC + PASO_MERMAID, PASO_MERMAID + PASO_INSTALAR_MMDC
                ),
                "mmdc se ejecuta antes de instalar mermaid-cli",
            ),
            "verificar_docs al final": (
                en_documentacion(PASO_VERIFICAR_DOCS_G, "").replace(
                    PASO_MERMAID, PASO_MERMAID + PASO_VERIFICAR_DOCS_G
                ),
                "«markdownlint-cli2» debe ir después de «python3 tools/verificar_docs.py»",
            ),
            "setup-node borrado": (
                en_documentacion(PASO_SETUP_NODE_D5, ""),
                "falta actions/setup-node antes de markdownlint-cli2",
            ),
            "setup-node comentado": (
                comentar(CI_D5, DOC, PASO_SETUP_NODE_D5),
                "falta actions/setup-node antes de markdownlint-cli2",
            ),
            "setup-node después de markdownlint": (
                en_documentacion(
                    PASO_SETUP_NODE_D5 + PASO_MARKDOWNLINT, PASO_MARKDOWNLINT + PASO_SETUP_NODE_D5
                ),
                "falta actions/setup-node antes de markdownlint-cli2",
            ),
            "setup-node borrado: tampoco antes de instalar mermaid-cli": (
                en_documentacion(PASO_SETUP_NODE_D5, ""),
                "falta actions/setup-node antes de instalar mermaid-cli",
            ),
            "setup-uv borrado": (
                en_documentacion(PASO_SETUP_UV_D5, ""),
                "falta astral-sh/setup-uv antes de Vale",
            ),
            "setup-uv después de Vale": (
                en_documentacion(PASO_SETUP_UV_D5 + PASO_VALE, PASO_VALE + PASO_SETUP_UV_D5),
                "falta astral-sh/setup-uv antes de Vale",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_todo_paso_tras_el_checkout_conserva_su_guarda(self):
        """CA-13 esc. 1 · TC-65 y regla común 6 — sin `if: ${{ !cancelled() }}` el paso no corre tras un fallo anterior."""
        fragmento = "no declara `if: ${{ !cancelled() }}` (regla común 6)"
        casos = {
            "verificar_docs sin if": (
                en_documentacion(PASO_VERIFICAR_DOCS_G, PASO_VERIFICAR_DOCS),
                fragmento,
            ),
            "setup-node sin if": (
                en_documentacion(PASO_SETUP_NODE_D5, sin_guarda(PASO_SETUP_NODE_D5)),
                fragmento,
            ),
            "markdownlint sin if": (
                en_documentacion(PASO_MARKDOWNLINT, sin_guarda(PASO_MARKDOWNLINT)),
                fragmento,
            ),
            "setup-uv sin if": (
                en_documentacion(PASO_SETUP_UV_D5, sin_guarda(PASO_SETUP_UV_D5)),
                fragmento,
            ),
            "Vale sin if": (en_documentacion(PASO_VALE, sin_guarda(PASO_VALE)), fragmento),
            "lychee sin if": (en_documentacion(PASO_LYCHEE, sin_guarda(PASO_LYCHEE)), fragmento),
            "instalación de mermaid-cli sin if": (
                en_documentacion(PASO_INSTALAR_MMDC, sin_guarda(PASO_INSTALAR_MMDC)),
                fragmento,
            ),
            "bucle de mmdc sin if": (
                en_documentacion(PASO_MERMAID, sin_guarda(PASO_MERMAID)),
                fragmento,
            ),
            "Vale con if: always()": (
                en_documentacion(PASO_VALE, PASO_VALE.replace("${{ !cancelled() }}", "always()")),
                fragmento,
            ),
            "Vale con if: ${{ false }}": (
                en_documentacion(
                    PASO_VALE, PASO_VALE.replace("${{ !cancelled() }}", "${{ false }}")
                ),
                fragmento,
            ),
            "if comentado": (
                en_documentacion(
                    PASO_LYCHEE,
                    PASO_LYCHEE.replace(GUARDA_DE_PASO, "        # if: ${{ !cancelled() }}\n"),
                ),
                fragmento,
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_markdownlint_fijado_y_con_su_alcance(self):
        """CA-13 esc. 1 · TC-65 — versión exacta de markdownlint-cli2 y el alcance común; sin `--fix`."""
        casos = {
            "sin versión": (
                en_documentacion("markdownlint-cli2@0.24.0", "markdownlint-cli2"),
                "markdownlint-cli2 sin versión fija",
            ),
            "versión latest": (
                en_documentacion("markdownlint-cli2@0.24.0", "markdownlint-cli2@latest"),
                "markdownlint-cli2@latest",
            ),
            "otra versión": (
                en_documentacion("markdownlint-cli2@0.24.0", "markdownlint-cli2@0.23.0"),
                "markdownlint-cli2@0.23.0",
            ),
            "versión con acento circunflejo": (
                en_documentacion("markdownlint-cli2@0.24.0", "markdownlint-cli2@^0.24.0"),
                "markdownlint-cli2@^0.24.0",
            ),
            "sin --yes": (en_documentacion("npx --yes", "npx"), "npx --yes markdownlint-cli2"),
            "con --fix": (
                en_documentacion("markdownlint-cli2@0.24.0 ", "markdownlint-cli2@0.24.0 --fix "),
                "`--fix`",
            ),
            "sin CLAUDE.md": (
                en_documentacion(
                    '"sdd/**/*.md" README.md CLAUDE.md tools/README.md\n',
                    '"sdd/**/*.md" README.md tools/README.md\n',
                ),
                "el alcance de markdownlint-cli2",
            ),
            "sin sdd": (
                en_documentacion(' "sdd/**/*.md" README.md', " README.md"),
                "el alcance de markdownlint-cli2",
            ),
            "con .claude de más": (
                en_documentacion(
                    '"docs/**/*.md" "sdd/**/*.md"', '"docs/**/*.md" "sdd/**/*.md" ".claude/**/*.md"'
                ),
                "el alcance de markdownlint-cli2",
            ),
            "solo docs": (
                en_documentacion(
                    '"docs/**/*.md" "sdd/**/*.md" README.md CLAUDE.md tools/README.md',
                    '"docs/**/*.md"',
                ),
                "el alcance de markdownlint-cli2",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_vale_fijado_con_su_salida_y_la_guarda_de_salida_vacia(self):
        """CA-13 esc. 1 · TC-65 — Vale con versión exacta, una línea por hallazgo, la salida impresa y la guarda de salida vacía."""
        guarda = "Vale sin la guarda de salida vacía"
        casos = {
            "sin la guarda de salida vacía": (
                en_documentacion(LINEA_GUARDA, '          [ "$codigo" -eq 0 ]\n'),
                guarda,
            ),
            "sin guarda ni comprobación": (en_documentacion(LINEA_GUARDA, ""), guarda),
            "la guarda mira otro archivo": (
                en_documentacion(LINEA_GUARDA, LINEA_GUARDA.replace("vale.txt", "otro.txt")),
                guarda,
            ),
            "la guarda sin la prueba -s": (
                en_documentacion(
                    LINEA_GUARDA,
                    '          [ "$codigo" -eq 0 ] && [ -n "$RUNNER_TEMP/vale.txt" ]\n',
                ),
                guarda,
            ),
            "solo la salida vacía, sin el código": (
                en_documentacion(
                    LINEA_GUARDA, '          [ ! -s "$RUNNER_TEMP/vale.txt" ]\n'
                ).replace(" || codigo=$?", ""),
                "no conserva el código de salida",
            ),
            "el código capturado y nunca consultado": (
                en_documentacion(LINEA_GUARDA, '          [ ! -s "$RUNNER_TEMP/vale.txt" ]\n'),
                "no conserva el código de salida",
            ),
            "la guarda antes de imprimir": (
                en_documentacion(LINEA_CAT + LINEA_GUARDA, LINEA_GUARDA + LINEA_CAT),
                "antes de imprimir el archivo",
            ),
            "sin imprimir el archivo": (en_documentacion(LINEA_CAT, ""), "no imprime"),
            "sin redirigir la salida": (
                en_documentacion(' > "$RUNNER_TEMP/vale.txt" ||', " ||"),
                "no redirige su salida",
            ),
            "redirigida a otro archivo": (
                en_documentacion(' > "$RUNNER_TEMP/vale.txt" ||', ' > "$RUNNER_TEMP/otro.txt" ||'),
                "no redirige su salida",
            ),
            "sin --output=line": (en_documentacion(" --output=line", ""), "`--output=line`"),
            "con --output=JSON": (
                en_documentacion("--output=line", "--output=JSON"),
                "`--output=line`",
            ),
            "sin --from": (
                en_documentacion("uvx --from vale==3.25.1.0 vale", "uvx vale"),
                "no se invoca como `uvx --from vale==3.25.1.0 vale`",
            ),
            "sin versión": (
                en_documentacion("vale==3.25.1.0", "vale"),
                "no se invoca como `uvx --from vale==3.25.1.0 vale`",
            ),
            "otra versión": (
                en_documentacion("vale==3.25.1.0", "vale==3.24.0.0"),
                "no se invoca como `uvx --from vale==3.25.1.0 vale`",
            ),
            "versión mayor o igual": (
                en_documentacion("vale==3.25.1.0", "vale>=3.25.1.0"),
                "no se invoca como `uvx --from vale==3.25.1.0 vale`",
            ),
            "sin sdd": (
                en_documentacion("--output=line docs sdd", "--output=line docs"),
                "el alcance de Vale",
            ),
            "sin tools/README.md": (
                en_documentacion(" CLAUDE.md tools/README.md >", " CLAUDE.md >"),
                "el alcance de Vale",
            ),
            "recorre .claude": (
                en_documentacion(
                    "--output=line docs sdd README.md", "--output=line docs sdd .claude README.md"
                ),
                "el alcance de Vale",
            ),
            "con || true": (
                en_documentacion("|| codigo=$?", "|| true").replace(
                    LINEA_GUARDA, '          [ ! -s "$RUNNER_TEMP/vale.txt" ]\n'
                ),
                "enmascara su fallo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_lychee_fijado_con_su_configuracion_y_fail_true(self):
        """CA-13 esc. 1 · TC-65 — `lychee-action` por SHA con etiqueta, `--config lychee.toml`, el alcance y `fail: true`."""
        casos = {
            "sin fail: true": (en_documentacion("          fail: true\n", ""), "`fail: true`"),
            "fail: false": (en_documentacion("fail: true", "fail: false"), "`fail: true`"),
            "fail comentado": (
                en_documentacion("          fail: true\n", "          # fail: true\n"),
                "`fail: true`",
            ),
            "sin --config": (
                en_documentacion("--config lychee.toml ", ""),
                "`--config lychee.toml`",
            ),
            "otro archivo de configuración": (
                en_documentacion("--config lychee.toml", "--config otra.toml"),
                "`--config lychee.toml`",
            ),
            "sin --no-progress": (en_documentacion(" --no-progress", ""), "`--no-progress`"),
            "alcance sin sdd": (
                en_documentacion(" 'sdd/**/*.md'", ""),
                "el alcance de lychee-action",
            ),
            "alcance con .claude": (
                en_documentacion("'sdd/**/*.md' README.md", "'sdd/**/*.md' .claude README.md"),
                "el alcance de lychee-action",
            ),
            "lychee con --offline": (
                en_documentacion(" --no-progress", " --no-progress --offline"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "lychee con --exclude y su valor": (
                en_documentacion(" --no-progress", " --no-progress --exclude example.com"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "lychee con --exclude=valor": (
                en_documentacion(" --no-progress", " --no-progress --exclude=example.com"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "lychee con --exclude-path": (
                en_documentacion(" --no-progress", " --no-progress --exclude-path docs"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "sin args": (en_documentacion(ARGS_DE_LYCHEE, ""), "no declara `args:`"),
            "sin lycheeVersion": (
                en_documentacion("          lycheeVersion: v0.24.2\n", ""),
                "lycheeVersion: v0.24.2",
            ),
            "lycheeVersion latest": (
                en_documentacion("v0.24.2", "latest"),
                "lycheeVersion: v0.24.2",
            ),
            "otra lycheeVersion": (
                en_documentacion("lycheeVersion: v0.24.2", "lycheeVersion: v0.23.0"),
                "lycheeVersion: v0.24.2",
            ),
            "sin with": (en_documentacion(CON_DE_LYCHEE, ""), "no declara `args:`"),
            "uses con etiqueta en lugar de SHA": (
                en_documentacion(f"lychee-action@{SHA_LYCHEE} # v2.9.0", "lychee-action@v2"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "uses con SHA corto": (
                en_documentacion(f"lychee-action@{SHA_LYCHEE}", "lychee-action@e747777"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "uses con SHA sin etiqueta": (
                en_documentacion(
                    f"lychee-action@{SHA_LYCHEE} # v2.9.0", f"lychee-action@{SHA_LYCHEE}"
                ),
                "no está fijada por SHA de 40 caracteres",
            ),
            "uses con SHA y una etiqueta que no es versión": (
                en_documentacion(
                    f"lychee-action@{SHA_LYCHEE} # v2.9.0", f"lychee-action@{SHA_LYCHEE} # main"
                ),
                "no está fijada por SHA de 40 caracteres",
            ),
            "continue-on-error en lychee": (
                en_documentacion(
                    CON_DE_LYCHEE, CON_DE_LYCHEE + "        continue-on-error: true\n"
                ),
                "continue-on-error",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_mermaid_cli_se_instala_con_npm_ci_y_el_bucle_falla_por_cada_diagrama(
        self,
    ):
        """CA-16 esc. 1 · TC-65 — mermaid-cli con `npm ci` en `.github/mermaid` (paso propio, sin `npm install`), el binario de ahí, `-p`, el `::error` por archivo y `exit 1` tras el bucle."""
        paso_npm_install_suelto = (
            "      - name: Instalar otra cosa\n"
            + GUARDA_DE_PASO
            + "        run: npm install --no-save left-pad\n"
        )
        casos = {
            "vuelve npm install con el paquete suelto": (
                en_documentacion(
                    LINEAS_INSTALAR_MMDC,
                    '        run: npm install --no-save --prefix "$RUNNER_TEMP/mmdc" @mermaid-js/mermaid-cli@12.0.0\n',
                ),
                "debe ser `npm ci`",
            ),
            "npm install sin paquete": (
                en_documentacion("run: npm ci\n", "run: npm install\n"),
                "debe ser `npm ci`",
            ),
            "npm i": (en_documentacion("run: npm ci\n", "run: npm i\n"), "debe ser `npm ci`"),
            "npm install sigue en el trabajo, en otro paso": (
                en_documentacion(PASO_INSTALAR_MMDC, PASO_INSTALAR_MMDC + paso_npm_install_suelto),
                "ejecuta `npm install`",
            ),
            "npm install en el paso del bucle": (
                en_documentacion(
                    "          fallos=0\n",
                    "          npm install --no-save left-pad\n          fallos=0\n",
                ),
                "ejecuta `npm install`",
            ),
            "npm ci con el paquete como argumento": (
                en_documentacion("run: npm ci\n", "run: npm ci @mermaid-js/mermaid-cli@12.0.0\n"),
                "no instala paquetes sueltos",
            ),
            "npm ci sin working-directory": (
                en_documentacion("        working-directory: .github/mermaid\n", ""),
                "no se ejecuta en `.github/mermaid`",
            ),
            "npm ci con working-directory de frontend": (
                en_documentacion(
                    "working-directory: .github/mermaid", "working-directory: frontend"
                ),
                "no se ejecuta en `.github/mermaid`",
            ),
            "npm ci con working-directory de .github": (
                en_documentacion(
                    "working-directory: .github/mermaid", "working-directory: .github"
                ),
                "no se ejecuta en `.github/mermaid`",
            ),
            "npm ci con --prefix de otro directorio": (
                en_documentacion(LINEAS_INSTALAR_MMDC, "        run: npm ci --prefix frontend\n"),
                "no se ejecuta en `.github/mermaid`",
            ),
            "npm ci con el prefijo temporal de antes": (
                en_documentacion(
                    LINEAS_INSTALAR_MMDC, '        run: npm ci --prefix "$RUNNER_TEMP/mmdc"\n'
                ),
                "no se ejecuta en `.github/mermaid`",
            ),
            "working-directory y --prefix a la vez": (
                en_documentacion("run: npm ci\n", "run: npm ci --prefix .github/mermaid\n"),
                "`working-directory` y `--prefix` a la vez",
            ),
            "la instalación comparte paso con el bucle": (
                mutar(
                    mutar(CI_D5, DOC, PASO_INSTALAR_MMDC, ""),
                    DOC,
                    PASO_MERMAID,
                    PASO_MERMAID.replace(
                        "        run: |\n",
                        "        run: |\n          npm ci --prefix .github/mermaid\n",
                    ),
                ),
                "debe ir en un paso propio",
            ),
            "el bucle llama al mmdc del prefijo temporal": (
                en_documentacion(
                    "if ! .github/mermaid/node_modules/.bin/mmdc",
                    'if ! "$RUNNER_TEMP/mmdc/node_modules/.bin/mmdc"',
                ),
                "mmdc no se invoca desde el binario que instaló `npm ci`",
            ),
            "el bucle llama al mmdc de frontend": (
                en_documentacion(
                    "if ! .github/mermaid/node_modules/.bin/mmdc",
                    "if ! frontend/node_modules/.bin/mmdc",
                ),
                "mmdc no se invoca desde el binario que instaló `npm ci`",
            ),
            "el bucle llama a un mmdc global": (
                en_documentacion("if ! .github/mermaid/node_modules/.bin/mmdc", "if ! mmdc"),
                "mmdc no se invoca desde el binario que instaló `npm ci`",
            ),
            "el bucle llama a npx mmdc": (
                en_documentacion("if ! .github/mermaid/node_modules/.bin/mmdc", "if ! npx mmdc"),
                "mmdc no se invoca desde el binario que instaló `npm ci`",
            ),
            "el bucle llama al binario de un directorio con otro prefijo": (
                en_documentacion(
                    "if ! .github/mermaid/node_modules/.bin/mmdc",
                    "if ! docs/.github/mermaid/node_modules/.bin/mmdc",
                ),
                "mmdc no se invoca desde el binario que instaló `npm ci`",
            ),
            "mmdc sin -p": (
                en_documentacion(" -p .github/puppeteer-config.json", ""),
                "no recibe `-p .github/puppeteer-config.json`",
            ),
            "mmdc con otro archivo de Puppeteer": (
                en_documentacion("-p .github/puppeteer-config.json", "-p puppeteer.json"),
                "no recibe `-p .github/puppeteer-config.json`",
            ),
            "mmdc sin ::error": (
                en_documentacion(
                    '              echo "::error file=$archivo::diagrama Mermaid inválido"\n', ""
                ),
                "no escribe `::error file=<archivo>::diagrama Mermaid inválido`",
            ),
            "::error con otro mensaje": (
                en_documentacion("diagrama Mermaid inválido", "falló mmdc"),
                "no escribe `::error file=<archivo>::diagrama Mermaid inválido`",
            ),
            "::error sin el archivo": (
                en_documentacion("::error file=$archivo::", "::error::"),
                "no escribe `::error file=<archivo>::diagrama Mermaid inválido`",
            ),
            "sin exit 1": (
                en_documentacion(FIN_DEL_BUCLE, ""),
                "no termina con `exit 1`",
            ),
            "exit 1 dentro del bucle, que corta en el primer diagrama": (
                en_documentacion(FIN_DEL_BUCLE, "").replace(
                    "              fallos=1\n", "              exit 1\n"
                ),
                "no termina con `exit 1`",
            ),
            "sin bucle": (
                en_documentacion(
                    LINEAS_DEL_BUCLE,
                    "          .github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json -i docs/README.md"
                    ' -o "$RUNNER_TEMP/mermaid.md"\n          exit 1\n',
                ),
                "no se ejecuta dentro de un bucle",
            ),
            "sin seleccionar los Markdown con mermaid": (
                en_documentacion("grep -rl '```mermaid'", "grep -rl 'mermaid'"),
                "no selecciona los Markdown que contienen un bloque ```mermaid",
            ),
            "alcance sin sdd": (
                en_documentacion(
                    "docs sdd README.md CLAUDE.md tools/README.md)",
                    "docs README.md CLAUDE.md tools/README.md)",
                ),
                "no cubre sdd",
            ),
            "alcance sin tools/README.md": (
                en_documentacion("CLAUDE.md tools/README.md)", "CLAUDE.md)"),
                "no cubre tools/README.md",
            ),
            "alcance sin CLAUDE.md": (
                en_documentacion(
                    "README.md CLAUDE.md tools/README.md)", "README.md tools/README.md)"
                ),
                "no cubre CLAUDE.md",
            ),
            "recorre el repositorio entero": (
                en_documentacion(
                    "grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md)",
                    "grep -rl '```mermaid' . --include=*.md docs sdd README.md CLAUDE.md tools/README.md)",
                ),
                "recorre el repositorio entero",
            ),
            "mmdc con || true": (
                en_documentacion(
                    '-o "$RUNNER_TEMP/mermaid/$n.md"; then',
                    '-o "$RUNNER_TEMP/mermaid/$n.md" || true; then',
                ),
                "enmascara su fallo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_el_bucle_de_mmdc_detecta_el_fallo_y_sale_con_exit_1_solo_si_lo_hubo(
        self,
    ):
        """CA-16 esc. 1 · TC-65 — el bucle de mmdc no se comprueba por presencia de fragmentos: la llamada va negada y sola,
        `fallos=1` está en la rama que falla, `exit 1` es un comando completo condicionado por `fallos` y `grep` es recursivo."""
        llamada = "if ! .github/mermaid/node_modules/.bin/mmdc"
        cierre_de_la_condicion = '-o "$RUNNER_TEMP/mermaid/$n.md"; then'
        casos = {
            "fallos=1 cambiado por fallos=0": (
                en_documentacion("              fallos=1\n", "              fallos=0\n"),
                "no marca el fallo",
            ),
            "fallos=1 fuera de la rama que falla": (
                en_documentacion(
                    "              fallos=1\n            fi\n",
                    "            fi\n            fallos=1\n",
                ),
                "no marca el fallo",
            ),
            "se marca otra variable que la del exit": (
                en_documentacion("              fallos=1\n", "              otro=1\n"),
                "no termina con `exit 1`",
            ),
            "la variable de fallos sin iniciar": (
                en_documentacion("          fallos=0\n", ""),
                "no inicia `fallos=0` antes del bucle",
            ),
            "exit 1 cuando no hubo fallos (-eq 0)": (
                en_documentacion('[ "$fallos" -ne 0 ]', '[ "$fallos" -eq 0 ]'),
                "no termina con `exit 1`",
            ),
            "exit 1 con -ne 1": (
                en_documentacion('[ "$fallos" -ne 0 ]', '[ "$fallos" -ne 1 ]'),
                "no termina con `exit 1`",
            ),
            "exit 1 como texto de un echo": (
                en_documentacion("            exit 1\n", '            echo "exit 1"\n'),
                "no termina con `exit 1`",
            ),
            "exit 1 incondicional": (
                en_documentacion(FIN_DEL_BUCLE, "          exit 1\n"),
                "no termina con `exit 1`",
            ),
            "un exit 0 después del exit 1 condicionado": (
                en_documentacion(FIN_DEL_BUCLE, FIN_DEL_BUCLE + "          exit 0\n"),
                "no termina con `exit 1`",
            ),
            "la llamada a mmdc sin negar": (
                en_documentacion(llamada, "if .github/mermaid/node_modules/.bin/mmdc"),
                "no está negada",
            ),
            "mmdc encadenada con && a un bloque de error": (
                en_documentacion(
                    LLAMADA_A_MMDC,
                    "            .github/mermaid/node_modules/.bin/mmdc -p .github/puppeteer-config.json"
                    ' -i "$archivo" -o "$RUNNER_TEMP/mermaid/$n.md" && { echo "::error file=$archivo::diagrama Mermaid inválido"; fallos=1; }\n'
                    "            if false; then\n",
                ),
                "no está negada",
            ),
            "un true encadenado dentro del if": (
                en_documentacion(
                    cierre_de_la_condicion, '-o "$RUNNER_TEMP/mermaid/$n.md"; true; then'
                ),
                "encadena otro comando",
            ),
            "una tubería en la condición del if": (
                en_documentacion(
                    cierre_de_la_condicion, '-o "$RUNNER_TEMP/mermaid/$n.md" | cat; then'
                ),
                "encadena otro comando",
            ),
            "grep sin -r": (
                en_documentacion("grep -rl '```mermaid'", "grep -l '```mermaid'"),
                "no es recursivo",
            ),
            "grep sin -l": (
                en_documentacion("grep -rl '```mermaid'", "grep -r '```mermaid'"),
                "no lista nombres de archivo",
            ),
            "mmdc sobre un archivo fijo en lugar de la variable del bucle": (
                en_documentacion('-i "$archivo"', "-i README.md"),
                "mmdc no recibe `-i",
            ),
            "el ::error nombra un archivo fijo": (
                en_documentacion("::error file=$archivo::", "::error file=README.md::"),
                "no nombra el archivo del bucle",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_la_guarda_de_salida_vacia_de_vale_solo_acepta_sus_dos_formas(self):
        """CA-13 esc. 1 · TC-65 — la guarda de Vale es `[ "$codigo" -eq 0 ] && [ ! -s ... ]` como última línea, o `if [ ... -ne 0 ] ||
        [ -s ... ]; then exit 1; fi`; la presencia de `-s vale.txt` no basta, y cada prueba tiene que ir en su sentido."""
        guarda = "Vale sin la guarda de salida vacía"
        archivo = '"$RUNNER_TEMP/vale.txt"'

        def con_guarda(linea: str) -> str:
            return en_documentacion(LINEA_GUARDA, f"          {linea}\n")

        casos = {
            "la prueba -s sin negar en la forma A": (
                con_guarda(f'[ "$codigo" -eq 0 ] && [ -s {archivo} ]'),
                guarda,
            ),
            "-eq cambiado por -ne en la forma A": (
                con_guarda(f'[ "$codigo" -ne 0 ] && [ ! -s {archivo} ]'),
                guarda,
            ),
            "&& cambiado por || en la forma A": (
                con_guarda(f'[ "$codigo" -eq 0 ] || [ ! -s {archivo} ]'),
                guarda,
            ),
            "la guarda dentro de un echo": (
                con_guarda(f"echo '[ \"$codigo\" -eq 0 ] && [ ! -s {archivo} ]'"),
                guarda,
            ),
            "la guarda como argumento de un comando": (
                con_guarda(f'echo hecho [ "$codigo" -eq 0 ] && [ ! -s {archivo} ]'),
                guarda,
            ),
            "un exit 0 después de la guarda": (
                en_documentacion(LINEA_GUARDA, LINEA_GUARDA + "          exit 0\n"),
                "no es lo último del paso",
            ),
            "la forma B con la prueba -s negada": (
                con_guarda(f'if [ "$codigo" -ne 0 ] || [ ! -s {archivo} ]; then exit 1; fi'),
                guarda,
            ),
            "la forma B con -eq 0 en lugar de -ne 0": (
                con_guarda(f'if [ "$codigo" -eq 0 ] || [ -s {archivo} ]; then exit 1; fi'),
                guarda,
            ),
            "la forma B con && en lugar de ||": (
                con_guarda(f'if [ "$codigo" -ne 0 ] && [ -s {archivo} ]; then exit 1; fi'),
                guarda,
            ),
            "la forma B que sale con exit 0": (
                con_guarda(f'if [ "$codigo" -ne 0 ] || [ -s {archivo} ]; then exit 0; fi'),
                guarda,
            ),
            "la forma B sin cuerpo que salga": (
                con_guarda(f'if [ "$codigo" -ne 0 ] || [ -s {archivo} ]; then echo hallazgos; fi'),
                guarda,
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)

    def test_tc65_mutantes_el_contenido_de_puppeteer_config_pasa_el_sandbox_a_chromium(self):
        """CA-16 esc. 1 · TC-65 — `.github/puppeteer-config.json` lleva `--no-sandbox`: sin él, Chromium no arranca como root
        en el corredor y mmdc falla en todos los diagramas por una razón que no es de los diagramas."""
        self.assertEqual(comprobar_puppeteer_config(PUPPETEER_CONFIG_D5), [])
        casos = {
            "vaciado a {}": ("{}", "no declara `args`"),
            "args vacío": ('{"args": []}', "no lleva `--no-sandbox`"),
            "otro argumento": ('{"args": ["--disable-gpu"]}', "no lleva `--no-sandbox`"),
            "un argumento que solo se le parece": (
                '{"args": ["--no-sandbox-fake"]}',
                "no lleva `--no-sandbox`",
            ),
            "args como cadena": ('{"args": "--no-sandbox"}', "no declara `args`"),
            "JSON roto": ("{ no es json", "no es JSON válido"),
            "raíz que no es un objeto": ('["--no-sandbox"]', "la raíz debe ser un objeto JSON"),
        }
        exigir_rojo_en_todos(self, comprobar_puppeteer_config, casos)

    def test_tc65_mutantes_reglas_comunes_del_trabajo(self):
        """CA-13 esc. 1 · TC-65 y reglas comunes 1, 2, 4, 5, 7 y 9 — corredor, tiempo, credenciales, SHA, secretos y tuberías."""
        con_secreto = en_documentacion(
            CON_DE_LYCHEE, CON_DE_LYCHEE + "          token: ${{ secrets.GITHUB_TOKEN }}\n"
        )
        con_tuberia = en_documentacion(
            "          done < <(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md)\n",
            "          done < <(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md | sort)\n",
        )
        casos = {
            "runs-on distinto": (
                en_documentacion("    runs-on: ubuntu-24.04\n", "    runs-on: ubuntu-latest\n"),
                "runs-on debe ser ubuntu-24.04",
            ),
            "sin timeout-minutes": (
                en_documentacion("    timeout-minutes: 15\n", ""),
                "timeout-minutes",
            ),
            "timeout de 30 minutos": (
                en_documentacion("timeout-minutes: 15", "timeout-minutes: 30"),
                "timeout-minutes debe ser 15",
            ),
            "checkout sin persist-credentials": (
                en_documentacion("        with:\n          persist-credentials: false\n", ""),
                "persist-credentials: false",
            ),
            "checkout con persist-credentials: true": (
                en_documentacion("persist-credentials: false", "persist-credentials: true"),
                "persist-credentials: false",
            ),
            "checkout ausente": (en_documentacion(PASO_CHECKOUT_D5, ""), "falta actions/checkout"),
            "lee secrets.": (con_secreto, "lee `secrets.`"),
            "continue-on-error en Vale": (
                en_documentacion(
                    PASO_VALE,
                    PASO_VALE.replace(
                        "        run: |\n", "        continue-on-error: true\n        run: |\n"
                    ),
                ),
                "continue-on-error",
            ),
            "continue-on-error en el trabajo": (
                en_documentacion(
                    "    timeout-minutes: 15\n",
                    "    timeout-minutes: 15\n    continue-on-error: true\n",
                ),
                "continue-on-error",
            ),
            "setup-node por etiqueta": (
                en_documentacion(f"setup-node@{SHA_SETUP_NODE} # v7.1.0", "setup-node@v7"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "setup-uv por etiqueta": (
                en_documentacion(f"setup-uv@{SHA_SETUP_UV} # v10.3.3", "setup-uv@v10"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "checkout por etiqueta": (
                en_documentacion(f"checkout@{SHA_CHECKOUT} # v7.0.1", "checkout@v7"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "tubería sin shell: bash": (con_tuberia, "usa una tubería sin `shell: bash`"),
            "setup-node sin node-version-file": (
                en_documentacion(
                    "        with:\n          node-version-file: frontend/package.json\n", ""
                ),
                "setup-node no declara `node-version-file: frontend/package.json`",
            ),
            "setup-node con node-version en lugar del archivo": (
                en_documentacion("node-version-file: frontend/package.json", "node-version: 22"),
                "setup-node no declara `node-version-file: frontend/package.json`",
            ),
            "setup-node con el package.json de otro directorio": (
                en_documentacion(
                    "node-version-file: frontend/package.json", "node-version-file: package.json"
                ),
                "setup-node no declara `node-version-file: frontend/package.json`",
            ),
            "defaults.run.working-directory en el trabajo": (
                en_documentacion(
                    "    timeout-minutes: 15\n",
                    "    timeout-minutes: 15\n    defaults:\n      run:\n        working-directory: backend\n",
                ),
                "declara `defaults.run.working-directory: backend`",
            ),
            "defaults a nivel de flujo": (
                sustituir(
                    CI_D5,
                    "\njobs:\n",
                    "\ndefaults:\n  run:\n    working-directory: backend\njobs:\n",
                ),
                "declara `defaults:` a nivel de flujo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc65_texto, casos)
        # Con `shell: bash` la tubería es legítima (regla común 9).
        paso_con_shell = PASO_MERMAID.replace(
            "        run: |\n", "        shell: bash\n        run: |\n"
        ).replace("tools/README.md)\n", "tools/README.md | sort)\n")
        con_shell = en_documentacion(PASO_MERMAID, paso_con_shell)
        self.assertEqual(comprobar_tc65_texto(con_shell), [])
        self.assertEqual(comprobar_regla_comun_9(extraer_trabajos(con_shell)), [])

    def test_tc65_mutantes_las_reglas_comunes_8_y_9_vigilan_el_trabajo_nuevo(self):
        """Reglas comunes 8 y 9 — un `${{ }}` dentro de `run:` o una tubería sin `shell: bash` en `documentacion` ponen en rojo las reglas existentes."""
        con_interpolacion = en_documentacion(
            "          fallos=0\n",
            "          fallos=0\n          echo ${{ github.event.pull_request.title }}\n",
        )
        con_tuberia = en_documentacion(
            "          done < <(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md)\n",
            "          done < <(grep -rl '```mermaid' docs sdd README.md CLAUDE.md tools/README.md | sort)\n",
        )
        exigir_rojo(
            self,
            comprobar_regla_comun_8,
            con_interpolacion,
            "interpola ${{ }} dentro de run:",
            preparar=extraer_trabajos,
        )
        exigir_rojo(
            self,
            comprobar_regla_comun_9,
            con_tuberia,
            "usa una tubería sin `shell: bash`",
            preparar=extraer_trabajos,
        )

    def test_tc65_mutantes_el_manifiesto_de_mermaid_cli_pasa_en_su_forma_valida(self):
        """CA-16 esc. 1 · TC-65 — control y formas equivalentes: `package.json`, `package-lock.json` y `.gitignore` válidos pasan; un rojo falso bloquearía la fila."""
        self.assertEqual(comprobar_package_json_de_mermaid(PACKAGE_JSON_D5), [])
        self.assertEqual(comprobar_package_lock_de_mermaid(PACKAGE_LOCK_D5), [])
        self.assertEqual(comprobar_gitignore_de_node_modules(GITIGNORE_D5), [])
        validos_json = {
            "en devDependencies": json_mutado(
                {**PACKAGE_JSON_BASE, "devDependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC}},
                ("dependencies",),
            ),
            "con scripts, version y otras dependencias exactas": json_mutado(
                {
                    **PACKAGE_JSON_BASE,
                    "version": "1.0.0",
                    "scripts": {"mmdc": "mmdc"},
                    "dependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC, "otra": "1.2.3"},
                },
                ("version",),
                "0.0.0",
            ),
        }
        for descripcion, texto in validos_json.items():
            with self.subTest(package_json=descripcion):
                self.assertEqual(comprobar_package_json_de_mermaid(texto), [])
        validos_lock = {
            "con la raíz en devDependencies": json_mutado(
                PACKAGE_LOCK_BASE,
                ("packages", ""),
                {"devDependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC}},
            ),
            "con integridad sha384": json_mutado(
                PACKAGE_LOCK_BASE,
                ("packages", ENTRADA_DEL_LOCK, "integrity"),
                "sha384-" + "B" * 64,
            ),
            "con otras dependencias transitivas": json_mutado(
                PACKAGE_LOCK_BASE,
                ("packages", "node_modules/puppeteer"),
                {"version": "23.1.0", "integrity": INTEGRIDAD_SINTETICA},
            ),
        }
        for descripcion, texto in validos_lock.items():
            with self.subTest(package_lock=descripcion):
                self.assertEqual(comprobar_package_lock_de_mermaid(texto), [])
        validos_gitignore = {
            "node_modules sin barra": "node_modules\n",
            "**/node_modules/": "# dependencias\n**/node_modules/\n",
            "con finales de línea de Windows": "dist/\r\nnode_modules/\r\n",
            "con una negación de otra cosa": "node_modules/\n!.env.example\n",
        }
        for descripcion, texto in validos_gitignore.items():
            with self.subTest(gitignore=descripcion):
                self.assertEqual(comprobar_gitignore_de_node_modules(texto), [])

    def test_tc65_mutantes_package_json_de_mermaid_cli_fija_la_version_exacta(self):
        """CA-16 esc. 1 · TC-65 — `package.json`: `private: true` y `@mermaid-js/mermaid-cli` en `12.0.0` exacta, no `^`, `~`, rango ni etiqueta."""
        ruta = ("dependencies", PAQUETE_DE_MMDC)
        fragmento_de_version = "debe ser la versión exacta '12.0.0'"
        casos = {
            "con acento circunflejo": (
                json_mutado(PACKAGE_JSON_BASE, ruta, "^12.0.0"),
                fragmento_de_version,
            ),
            "con tilde": (json_mutado(PACKAGE_JSON_BASE, ruta, "~12.0.0"), fragmento_de_version),
            "con rango": (json_mutado(PACKAGE_JSON_BASE, ruta, ">=12.0.0"), fragmento_de_version),
            "con comodín": (json_mutado(PACKAGE_JSON_BASE, ruta, "12.x"), fragmento_de_version),
            "latest": (json_mutado(PACKAGE_JSON_BASE, ruta, "latest"), fragmento_de_version),
            "otra versión": (json_mutado(PACKAGE_JSON_BASE, ruta, "12.0.1"), fragmento_de_version),
            "versión anterior": (
                json_mutado(PACKAGE_JSON_BASE, ruta, "11.12.0"),
                fragmento_de_version,
            ),
            "sin la dependencia": (
                json_mutado(PACKAGE_JSON_BASE, ("dependencies",), {}),
                "no declara @mermaid-js/mermaid-cli",
            ),
            "sin la sección de dependencias": (
                json_mutado(PACKAGE_JSON_BASE, ("dependencies",)),
                "no declara @mermaid-js/mermaid-cli",
            ),
            "solo en optionalDependencies": (
                json_mutado(
                    {
                        **PACKAGE_JSON_BASE,
                        "optionalDependencies": {PAQUETE_DE_MMDC: VERSION_DE_MMDC},
                    },
                    ("dependencies",),
                ),
                "no declara @mermaid-js/mermaid-cli",
            ),
            "exacta en dependencies y con ^ en devDependencies": (
                json_mutado(
                    {**PACKAGE_JSON_BASE, "devDependencies": {PAQUETE_DE_MMDC: "^12.0.0"}},
                    ("name",),
                    "otro",
                ),
                fragmento_de_version,
            ),
            "sin private": (json_mutado(PACKAGE_JSON_BASE, ("private",)), '"private": true'),
            "private falso": (
                json_mutado(PACKAGE_JSON_BASE, ("private",), False),
                '"private": true',
            ),
            "private como cadena": (
                json_mutado(PACKAGE_JSON_BASE, ("private",), "true"),
                '"private": true',
            ),
            "JSON roto": ("{ no es json", "no es JSON válido"),
            "raíz que no es un objeto": ("[]", "la raíz debe ser un objeto JSON"),
            "archivo vacío": ("", "no es JSON válido"),
        }
        exigir_rojo_en_todos(self, comprobar_package_json_de_mermaid, casos)

    def test_tc65_mutantes_package_lock_de_mermaid_cli_fija_la_version_y_su_integridad(self):
        """CA-16 esc. 1 · TC-65 — `package-lock.json`: `lockfileVersion` 3, la entrada de mermaid-cli en `12.0.0` con `integrity`, y la raíz del lock con la misma versión exacta."""
        entrada = ("packages", ENTRADA_DEL_LOCK)
        raiz = ("packages", "", "dependencies", PAQUETE_DE_MMDC)
        casos = {
            "lockfileVersion 2": (
                json_mutado(PACKAGE_LOCK_BASE, ("lockfileVersion",), 2),
                "`lockfileVersion` debe ser 3",
            ),
            "lockfileVersion 1": (
                json_mutado(PACKAGE_LOCK_BASE, ("lockfileVersion",), 1),
                "`lockfileVersion` debe ser 3",
            ),
            "sin lockfileVersion": (
                json_mutado(PACKAGE_LOCK_BASE, ("lockfileVersion",)),
                "`lockfileVersion` debe ser 3",
            ),
            "lockfileVersion como cadena": (
                json_mutado(PACKAGE_LOCK_BASE, ("lockfileVersion",), "3"),
                "`lockfileVersion` debe ser 3",
            ),
            "otra versión fijada": (
                json_mutado(PACKAGE_LOCK_BASE, (*entrada, "version"), "12.0.1"),
                "fija @mermaid-js/mermaid-cli en '12.0.1'",
            ),
            "versión fijada anterior": (
                json_mutado(PACKAGE_LOCK_BASE, (*entrada, "version"), "11.12.0"),
                "fija @mermaid-js/mermaid-cli en '11.12.0'",
            ),
            "sin la entrada del paquete": (
                json_mutado(PACKAGE_LOCK_BASE, ("packages", ENTRADA_DEL_LOCK)),
                "no fija `node_modules/@mermaid-js/mermaid-cli`",
            ),
            "sin integrity": (
                json_mutado(PACKAGE_LOCK_BASE, (*entrada, "integrity")),
                "no lleva `integrity`",
            ),
            "integrity vacía": (
                json_mutado(PACKAGE_LOCK_BASE, (*entrada, "integrity"), ""),
                "no lleva `integrity`",
            ),
            "integrity con un algoritmo inventado": (
                json_mutado(PACKAGE_LOCK_BASE, (*entrada, "integrity"), "md5-abcd"),
                "no lleva `integrity`",
            ),
            "la raíz del lock declara ^12.0.0": (
                json_mutado(PACKAGE_LOCK_BASE, raiz, "^12.0.0"),
                "la raíz del lock declara @mermaid-js/mermaid-cli en '^12.0.0'",
            ),
            "la raíz del lock declara otra versión": (
                json_mutado(PACKAGE_LOCK_BASE, raiz, "11.12.0"),
                "la raíz del lock declara @mermaid-js/mermaid-cli en '11.12.0'",
            ),
            "la raíz del lock no declara el paquete": (
                json_mutado(PACKAGE_LOCK_BASE, ("packages", "", "dependencies"), {}),
                "la raíz del lock declara @mermaid-js/mermaid-cli en None",
            ),
            "sin la sección packages": (
                json_mutado(PACKAGE_LOCK_BASE, ("packages",)),
                "no tiene la sección `packages`",
            ),
            "JSON roto": ("{ no es json", "no es JSON válido"),
            "archivo vacío": ("", "no es JSON válido"),
        }
        exigir_rojo_en_todos(self, comprobar_package_lock_de_mermaid, casos)

    def test_tc65_mutantes_gitignore_ignora_node_modules_en_cualquier_profundidad(self):
        """CA-16 esc. 1 · TC-65 — `.gitignore` ignora `node_modules`, también el de `.github/mermaid`; anclado a la raíz, comentado o negado no cuenta."""
        casos = {
            "sin la línea": ("__pycache__/\n.env\n", "no ignora `node_modules/`"),
            "archivo vacío": ("", "no ignora `node_modules/`"),
            "anclado a la raíz": ("/node_modules/\n", "no ignora `node_modules/`"),
            "solo el de frontend": ("frontend/node_modules/\n", "no ignora `node_modules/`"),
            "solo el de .github/mermaid de otro directorio": (
                "docs/node_modules/\n",
                "no ignora `node_modules/`",
            ),
            "comentada": ("# node_modules/\n", "no ignora `node_modules/`"),
            "con un nombre parecido": ("node_modules_viejos/\n", "no ignora `node_modules/`"),
            "negada después": (
                "node_modules/\n!.github/mermaid/node_modules/\n",
                "una negación (`!`) vuelve a incluir node_modules",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_gitignore_de_node_modules, casos)


class PruebasDeMutantesDeLaFilaD5ParaTC64(unittest.TestCase):
    """TC-64: `enlaces.yml` pierde su disparador, sus permisos o su configuración de lychee, y el caso queda en rojo.
    Las pruebas de este grupo trabajan sobre texto sintético: su verde es el de la comprobación, no el de `enlaces.yml`."""

    def test_tc64_mutantes_el_texto_valido_pasa_el_caso_y_las_comprobaciones_de_flujo(self):
        """CA-14 esc. 1 · TC-64 — control: la base pasa TC-64 y la comparación; con `ci.yml` pasan también TC-13, TC-21 y TC-22."""
        self.assertEqual(comprobar_tc64(ENLACES_D5), [])
        self.assertEqual(comprobar_misma_configuracion_de_lychee(CI_D5, ENLACES_D5), [])
        flujos = {"ci.yml": CI_D5, "enlaces.yml": ENLACES_D5}
        for comprobacion in (comprobar_tc13, comprobar_tc21, comprobar_tc22):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(flujos), [])
        self.assertEqual(comprobar_tc12(extraer_trabajos(CI_D5)), [])

    def test_tc64_mutantes_formas_equivalentes_validas_siguen_en_verde(self):
        """CA-14 esc. 1 · TC-64 — comillas simples en el cron, argumentos plegados y un comentario sobre un permiso no rompen el caso."""
        validos = {
            "cron con comillas simples": sustituir(ENLACES_D5, '"0 13 * * 1"', "'0 13 * * 1'"),
            "cron con un comentario al final": sustituir(
                ENLACES_D5,
                '"0 13 * * 1"\n',
                '"0 13 * * 1"  # lunes, 07:00 de la Ciudad de México\n',
            ),
            "workflow_dispatch con llaves vacías": sustituir(
                ENLACES_D5, "  workflow_dispatch:\n", "  workflow_dispatch: {}\n"
            ),
            "args en bloque plegado": sustituir(
                ENLACES_D5,
                ARGS_DE_LYCHEE,
                "          args: >-\n"
                "            --config lychee.toml --no-progress\n"
                "            'docs/**/*.md' 'sdd/**/*.md'\n"
                "            README.md CLAUDE.md tools/README.md\n",
            ),
            "workflow_dispatch con entradas": sustituir(
                ENLACES_D5,
                "  workflow_dispatch:\n",
                "  workflow_dispatch:\n    inputs:\n      motivo:\n        required: false\n",
            ),
            "concurrency con cancel-in-progress entre comillas": sustituir(
                ENLACES_D5, "cancel-in-progress: false", 'cancel-in-progress: "false"'
            ),
            "args con las mismas palabras en otro orden": sustituir(
                ENLACES_D5,
                ARGS_DE_LYCHEE,
                "          args: --no-progress --config lychee.toml README.md CLAUDE.md tools/README.md"
                " 'docs/**/*.md' 'sdd/**/*.md'\n",
            ),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc64(texto), [])
                self.assertEqual(comprobar_misma_configuracion_de_lychee(CI_D5, texto), [])

    def test_tc64_mutantes_el_disparador_es_un_dia_por_semana_y_a_mano(self):
        """CA-14 esc. 1 · TC-64 — sin `schedule`, con un cron de más de un día o sin `workflow_dispatch`, el caso queda en rojo."""
        cron = '    - cron: "0 13 * * 1"\n'
        casos = {
            "sin schedule": (
                sustituir(ENLACES_D5, "  schedule:\n" + cron, ""),
                "no declara el disparador `schedule`",
            ),
            "schedule comentado": (
                sustituir(
                    ENLACES_D5,
                    "  schedule:\n" + cron,
                    '  # schedule:\n  #   - cron: "0 13 * * 1"\n',
                ),
                "no declara el disparador `schedule`",
            ),
            "schedule sin cron": (sustituir(ENLACES_D5, cron, ""), "no declara ningún `cron`"),
            "cron lunes y miércoles": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 13 * * 1,3"),
                "más de un día por semana",
            ),
            "cron de lunes a viernes": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 13 * * 1-5"),
                "más de un día por semana",
            ),
            "cron diario": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 13 * * *"),
                "más de un día por semana",
            ),
            "cron cada cinco minutos": (
                sustituir(ENLACES_D5, "0 13 * * 1", "*/5 * * * *"),
                "más de un día por semana",
            ),
            "cron de otro día": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 13 * * 2"),
                "el cron debe ser `0 13 * * 1`",
            ),
            "cron a otra hora": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 7 * * 1"),
                "el cron debe ser `0 13 * * 1`",
            ),
            "cron con cuatro campos": (
                sustituir(ENLACES_D5, "0 13 * * 1", "0 13 * 1"),
                "no tiene cinco campos",
            ),
            "dos crons": (
                sustituir(ENLACES_D5, cron, cron + '    - cron: "0 13 * * 4"\n'),
                "declara 2 crons",
            ),
            "sin workflow_dispatch": (
                sustituir(ENLACES_D5, "  workflow_dispatch:\n", ""),
                "workflow_dispatch",
            ),
            "workflow_dispatch comentado": (
                sustituir(ENLACES_D5, "  workflow_dispatch:\n", "  # workflow_dispatch:\n"),
                "workflow_dispatch",
            ),
            "workflow_dispatch solo en un comentario al final": (
                sustituir(ENLACES_D5, "  workflow_dispatch:\n", "  push:  # workflow_dispatch\n"),
                "workflow_dispatch",
            ),
            "además pull_request": (
                sustituir(
                    ENLACES_D5, "  workflow_dispatch:\n", "  workflow_dispatch:\n  pull_request:\n"
                ),
                "debe declarar exactamente ['schedule', 'workflow_dispatch']",
            ),
            "además push": (
                sustituir(ENLACES_D5, "  workflow_dispatch:\n", "  workflow_dispatch:\n  push:\n"),
                "debe declarar exactamente ['schedule', 'workflow_dispatch']",
            ),
            "además workflow_run": (
                sustituir(
                    ENLACES_D5, "  workflow_dispatch:\n", "  workflow_dispatch:\n  workflow_run:\n"
                ),
                "debe declarar exactamente ['schedule', 'workflow_dispatch']",
            ),
            "además pull_request antes de schedule": (
                sustituir(ENLACES_D5, "on:\n", "on:\n  pull_request:\n"),
                "debe declarar exactamente ['schedule', 'workflow_dispatch']",
            ),
            "sin concurrency": (
                sustituir(ENLACES_D5, CONCURRENCIA_DE_ENLACES, ""),
                "cancel-in-progress: false",
            ),
            "concurrency comentada": (
                sustituir(
                    ENLACES_D5,
                    CONCURRENCIA_DE_ENLACES,
                    "# concurrency:\n#   group: enlaces\n#   cancel-in-progress: false\n",
                ),
                "cancel-in-progress: false",
            ),
            "concurrency que cancela la corrida en curso": (
                sustituir(ENLACES_D5, "cancel-in-progress: false", "cancel-in-progress: true"),
                "cancel-in-progress: false",
            ),
            "concurrency sin cancel-in-progress": (
                sustituir(ENLACES_D5, "  cancel-in-progress: false\n", ""),
                "cancel-in-progress: false",
            ),
            "concurrency sin group": (
                sustituir(ENLACES_D5, "  group: enlaces\n", ""),
                "cancel-in-progress: false",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc64, casos)

    def test_tc64_mutantes_los_permisos_son_de_solo_lectura(self):
        """CA-14 esc. 1 · TC-64 y CA-12 — sin `contents: read` a nivel de flujo, o con cualquier escritura, el caso queda en rojo."""
        permisos = "permissions:\n  contents: read\n"
        casos = {
            "sin permissions": (
                sustituir(ENLACES_D5, permisos, ""),
                "no declara `permissions:` a nivel de flujo",
            ),
            "permissions comentado": (
                sustituir(ENLACES_D5, permisos, "# permissions:\n#   contents: read\n"),
                "no declara `permissions:` a nivel de flujo",
            ),
            "contents: write": (
                sustituir(ENLACES_D5, "contents: read", "contents: write"),
                "contents: read",
            ),
            "contents: read más issues: write": (
                sustituir(ENLACES_D5, permisos, permisos + "  issues: write\n"),
                "permiso de escritura",
            ),
            "permissions: write-all": (
                sustituir(ENLACES_D5, permisos, "permissions: write-all\n"),
                "no declara `permissions:`",
            ),
            "permissions solo en el trabajo": (
                mutar(
                    sustituir(ENLACES_D5, permisos, ""),
                    "enlaces",
                    "    timeout-minutes: 15\n",
                    "    timeout-minutes: 15\n    permissions:\n      contents: read\n",
                ),
                "no declara `permissions:` a nivel de flujo",
            ),
            "pull_request_target": (
                sustituir(
                    ENLACES_D5,
                    "  workflow_dispatch:\n",
                    "  workflow_dispatch:\n  pull_request_target:\n",
                ),
                "pull_request_target",
            ),
            "lee secrets.": (
                sustituir(
                    ENLACES_D5,
                    "          fail: true\n",
                    "          fail: true\n          token: ${{ secrets.GITHUB_TOKEN }}\n",
                ),
                "secrets.",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc64, casos)

    def test_tc64_mutantes_el_trabajo_usa_checkout_y_lychee_fijados_en_el_corredor_de_siempre(self):
        """CA-14 esc. 1 · TC-64 — checkout sin credenciales persistidas, lychee-action con `fail: true`, acciones por SHA, corredor y tiempo."""
        casos = {
            "sin checkout": (
                mutar(ENLACES_D5, "enlaces", PASO_CHECKOUT_D5, ""),
                "falta actions/checkout",
            ),
            "checkout comentado": (
                comentar(ENLACES_D5, "enlaces", PASO_CHECKOUT_D5),
                "falta actions/checkout",
            ),
            "checkout después de lychee": (
                mutar(
                    ENLACES_D5,
                    "enlaces",
                    PASO_CHECKOUT_D5 + PASO_LYCHEE_DE_ENLACES,
                    PASO_LYCHEE_DE_ENLACES + PASO_CHECKOUT_D5,
                ),
                "actions/checkout va después de lychee-action",
            ),
            "checkout sin persist-credentials": (
                sustituir(ENLACES_D5, "        with:\n          persist-credentials: false\n", ""),
                "persist-credentials: false",
            ),
            "lychee comentado": (
                comentar(ENLACES_D5, "enlaces", PASO_LYCHEE_DE_ENLACES),
                "ningún trabajo usa lycheeverse/lychee-action",
            ),
            "sin fail: true": (sustituir(ENLACES_D5, "          fail: true\n", ""), "`fail: true`"),
            "fail: false": (sustituir(ENLACES_D5, "fail: true", "fail: false"), "`fail: true`"),
            "sin --config lychee.toml": (
                sustituir(ENLACES_D5, "--config lychee.toml ", ""),
                "`--config lychee.toml`",
            ),
            "sin --no-progress": (sustituir(ENLACES_D5, " --no-progress", ""), "`--no-progress`"),
            "alcance sin sdd": (
                sustituir(ENLACES_D5, " 'sdd/**/*.md'", ""),
                "el alcance de lychee-action",
            ),
            "lychee con --offline": (
                sustituir(ENLACES_D5, " --no-progress", " --no-progress --offline"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "lychee con --exclude": (
                sustituir(ENLACES_D5, " --no-progress", " --no-progress --exclude=example.com"),
                "opciones fuera de `--config` y `--no-progress`",
            ),
            "sin lycheeVersion": (
                sustituir(ENLACES_D5, "          lycheeVersion: v0.24.2\n", ""),
                "lycheeVersion: v0.24.2",
            ),
            "lychee por etiqueta": (
                sustituir(ENLACES_D5, f"lychee-action@{SHA_LYCHEE} # v2.9.0", "lychee-action@v2"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "lychee con SHA sin etiqueta": (
                sustituir(
                    ENLACES_D5,
                    f"lychee-action@{SHA_LYCHEE} # v2.9.0",
                    f"lychee-action@{SHA_LYCHEE}",
                ),
                "no está fijada por SHA de 40 caracteres",
            ),
            "checkout por etiqueta": (
                sustituir(ENLACES_D5, f"checkout@{SHA_CHECKOUT} # v7.0.1", "checkout@v7"),
                "no está fijada por SHA de 40 caracteres",
            ),
            "runs-on distinto": (
                sustituir(ENLACES_D5, "ubuntu-24.04", "ubuntu-latest"),
                "runs-on debe ser ubuntu-24.04",
            ),
            "sin timeout-minutes": (
                sustituir(ENLACES_D5, "    timeout-minutes: 15\n", ""),
                "timeout-minutes",
            ),
            "continue-on-error en lychee": (
                sustituir(
                    ENLACES_D5,
                    "          fail: true\n",
                    "          fail: true\n        continue-on-error: true\n",
                ),
                "continue-on-error",
            ),
            "sin trabajos": (
                sustituir(ENLACES_D5, ENLACES_D5[ENLACES_D5.index("jobs:") :], "jobs: {}\n"),
                "ningún trabajo usa lycheeverse/lychee-action",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc64, casos)

    def test_tc64_mutantes_la_configuracion_de_lychee_es_la_del_pr(self):
        """CA-14 esc. 1 · TC-64 — si `enlaces.yml` o el PR cambian de configuración y el otro no, el caso queda en rojo."""
        casos = {
            "enlaces sin --config": (
                sustituir(ENLACES_D5, "--config lychee.toml ", ""),
                "difiere de la del PR",
            ),
            "enlaces con otro alcance": (
                sustituir(ENLACES_D5, " 'sdd/**/*.md'", ""),
                "difiere de la del PR",
            ),
            "enlaces sin --no-progress": (
                sustituir(ENLACES_D5, " --no-progress", ""),
                "difiere de la del PR",
            ),
            "enlaces con otra versión de lychee": (
                sustituir(ENLACES_D5, "lycheeVersion: v0.24.2", "lycheeVersion: v0.23.0"),
                "difiere de la del PR",
            ),
            "enlaces con otro fail": (
                sustituir(ENLACES_D5, "fail: true", "fail: false"),
                "difiere de la del PR",
            ),
            "enlaces con un argumento de más": (
                sustituir(ENLACES_D5, " --no-progress", " --no-progress --verbose"),
                "difiere de la del PR",
            ),
            "enlaces sin lychee": (
                sustituir(ENLACES_D5, "lycheeverse/lychee-action", "otro/accion"),
                "ningún trabajo usa lycheeverse/lychee-action",
            ),
        }
        casos["enlaces con otro SHA de lychee-action"] = (
            sustituir(ENLACES_D5, SHA_LYCHEE, "0" * 40),
            "difiere de la del PR",
        )
        exigir_rojo_en_todos(
            self, lambda texto: comprobar_misma_configuracion_de_lychee(CI_D5, texto), casos
        )
        # El otro sentido: el PR cambia su configuración y el detector semanal se queda con la vieja.
        en_el_pr = {
            "el PR añade un argumento": en_documentacion(
                "--no-progress", "--no-progress --verbose"
            ),
            "el PR cambia de versión de lychee": en_documentacion(
                "lycheeVersion: v0.24.2", "lycheeVersion: v0.23.0"
            ),
            "el PR cambia de SHA de lychee-action": en_documentacion(SHA_LYCHEE, "0" * 40),
        }
        exigir_rojo_en_todos(
            self,
            lambda ci: comprobar_misma_configuracion_de_lychee(ci, ENLACES_D5),
            {descripcion: (ci, "difiere de la del PR") for descripcion, ci in en_el_pr.items()},
        )

    def test_tc64_mutantes_regresion_ca_r4_enlaces_no_rompe_tc13_tc21_ni_tc22(self):
        """CA-R4 · TC-13, TC-21 y TC-22 — los casos existentes recorren `enlaces.yml` y lo ponen en rojo si pide escritura sin motivo,
        usa `pull_request_target`, lee secretos, usa `workflow_run` o necesita un trabajo ajeno."""
        base = {"ci.yml": CI_D5}
        casos = (
            (
                "TC-21: contents: write sin comentario",
                comprobar_tc21,
                sustituir(ENLACES_D5, "contents: read", "contents: write"),
                "enlaces.yml",
            ),
            (
                "TC-21: sin permissions",
                comprobar_tc21,
                sustituir(ENLACES_D5, "permissions:\n  contents: read\n", ""),
                "enlaces.yml: no declara `permissions:`",
            ),
            (
                "TC-22: pull_request_target",
                comprobar_tc22,
                sustituir(
                    ENLACES_D5,
                    "  workflow_dispatch:\n",
                    "  workflow_dispatch:\n  pull_request_target:\n",
                ),
                "enlaces.yml: usa pull_request_target",
            ),
            (
                "TC-22: secrets.",
                comprobar_tc22,
                sustituir(
                    ENLACES_D5,
                    "          fail: true\n",
                    "          fail: true\n          token: ${{ secrets.GITHUB_TOKEN }}\n",
                ),
                "enlaces.yml: lee secrets.",
            ),
            (
                "TC-13: workflow_run",
                comprobar_tc13,
                sustituir(
                    ENLACES_D5, "  workflow_dispatch:\n", "  workflow_dispatch:\n  workflow_run:\n"
                ),
                "enlaces.yml: usa el disparador workflow_run",
            ),
            (
                "TC-13: needs de otro archivo",
                comprobar_tc13,
                sustituir(
                    ENLACES_D5,
                    "    timeout-minutes: 15\n",
                    "    needs: backend\n    timeout-minutes: 15\n",
                ),
                "'enlaces' necesita 'backend'",
            ),
        )
        for descripcion, comprobacion, texto, fragmento in casos:
            with self.subTest(mutante=descripcion):
                exigir_rojo(
                    self,
                    comprobacion,
                    texto,
                    fragmento,
                    preparar=lambda enlaces: {**base, "enlaces.yml": enlaces},
                )


# ---------------------------------------------------------------------------------------------------------
# Los casos sobre los archivos reales
# ---------------------------------------------------------------------------------------------------------


def _texto_de_enlaces(caso: unittest.TestCase) -> str:
    """El texto de `enlaces.yml`. Si el archivo no existe el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(ENLACES):
        caso.fail(
            f"No existe {os.path.relpath(ENLACES, RAIZ)}: el detector semanal de enlaces de TKT-009d todavía no está definido"
        )
    with open(ENLACES, encoding="utf-8") as archivo:
        return archivo.read()


def _texto_de_archivo(caso: unittest.TestCase, ruta: str, motivo: str) -> str:
    """El texto de un archivo real. Si no existe el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(ruta):
        caso.fail(f"No existe {os.path.relpath(ruta, RAIZ)}: {motivo}")
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


def _ci_real(caso: unittest.TestCase) -> str:
    return _leer_flujos(caso)["ci.yml"]


class PruebasDeMutantesDeFlujoDelTrabajoDocumentacion(unittest.TestCase):
    """F001 — mutantes que dejan el texto del paso «correcto» pero cambian lo que hace. Solo los mata ejecutar el `run:`."""

    def test_tc65_mutantes_de_flujo_del_paso_de_mermaid_se_detectan_al_ejecutarlo(self):
        """CA-16 esc. 1 · TC-65 — diez mutantes de flujo (la marca de fallo se borra, el bucle no corre o la selección no encuentra
        nada) dejan el paso en verde con un diagrama inválido; el escenario que los detecta es el del diagrama inválido."""
        ci = _ci_real(self)
        marca = "fallos=1"
        sangria = "              "
        casos = {
            "fallos=1 seguido de fallos=0": sustituir(
                ci, marca, marca + "\n" + sangria + "fallos=0"
            ),
            "exit 0 antes de fallos=1": sustituir(ci, marca, "exit 0\n" + sangria + marca),
            "fallos=0 tras el done": sustituir(
                ci, "tools/README.md)\n", "tools/README.md)\n          fallos=0\n"
            ),
            "fallos=0 justo antes de comprobar fallos": sustituir(
                ci,
                'if [ "$fallos" -ne 0 ]; then',
                'fallos=0\n          if [ "$fallos" -ne 0 ]; then',
            ),
            "continue antes de mmdc": sustituir(
                ci,
                "if ! .github/mermaid/node_modules/.bin/mmdc",
                "continue\n            if ! .github/mermaid/node_modules/.bin/mmdc",
            ),
            "while false": sustituir(ci, "while IFS= read -r archivo; do", "while false; do"),
            "grep con otro patrón": sustituir(ci, "'```mermaid'", "'```nomermaid'"),
            "grep sin -l, el bucle recibe líneas": sustituir(ci, "grep -rl '", "grep -rh '"),
        }
        # `else fallos=0` solo cae si un diagrama válido viene después de uno inválido.
        casos["else fallos=0"] = (
            sustituir(
                ci,
                marca + "\n            fi",
                marca + "\n            else\n              fallos=0\n            fi",
            ),
            "inválido en docs y válido después, en sdd",
        )
        exigir_rojo_en_todos(
            self,
            comprobar_comportamiento_de_mermaid,
            casos,
            fragmento="escenario «un diagrama inválido en docs»",
        )

    def test_tc65_mutantes_de_flujo_del_paso_de_vale_se_detectan_al_ejecutarlo(self):
        """CA-13 esc. 1 · TC-65 — un `codigo=0` o un `: > vale.txt` después del `cat` no cambian el texto de la guarda pero la anulan:
        el paso sale en verde con una alerta (que no cambia el código de salida de Vale) o con un error de Vale sin salida."""
        ci = _ci_real(self)
        impresion = 'cat "$RUNNER_TEMP/vale.txt"'
        exigir_rojo_en_todos(
            self,
            comprobar_comportamiento_de_vale,
            {
                "codigo=0 después del cat": (
                    sustituir(ci, impresion, impresion + "\n          codigo=0"),
                    "escenario «sin salida y con código 1",
                ),
                "vaciar vale.txt después del cat": (
                    sustituir(ci, impresion, impresion + '\n          : > "$RUNNER_TEMP/vale.txt"'),
                    "escenario «una alerta con código 0",
                ),
                "exit 0 al final": (
                    sustituir(
                        ci,
                        '[ ! -s "$RUNNER_TEMP/vale.txt" ]',
                        '[ ! -s "$RUNNER_TEMP/vale.txt" ]\n          exit 0',
                    ),
                    # Bajo `-e`, una alerta ya corta en la guarda; solo el error de Vale sin salida llega al `exit 0`.
                    "escenario «sin salida y con código 1",
                ),
                "la guarda antes del cat": (
                    sustituir(
                        ci,
                        impresion
                        + '\n          [ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ]',
                        '[ "$codigo" -eq 0 ] && [ ! -s "$RUNNER_TEMP/vale.txt" ] || exit 1\n          '
                        + impresion,
                    ),
                    "la salida no contiene",
                ),
            },
        )

    def test_tc65_mutantes_sin_paso_ejecutable_se_detectan(self):
        """CA-16 esc. 1 · TC-65 — si el paso se renombra o se comenta no hay nada que ejecutar y la comprobación lo dice, en lugar de dar verde."""
        ci = _ci_real(self)
        exigir_rojo(
            self,
            comprobar_comportamiento_de_mermaid,
            sustituir(ci, "name: Diagramas con mermaid-cli", "name: Diagramas"),
            "no hay un paso «Diagramas con mermaid-cli»",
        )
        exigir_rojo(
            self,
            comprobar_comportamiento_de_vale,
            sustituir(ci, "name: Prosa con Vale", "name: Prosa"),
            "no hay un paso «Prosa con Vale»",
        )

    def test_tc65_sin_un_bash_utilizable_la_prueba_falla_con_un_mensaje_claro(self):
        """CA-16 esc. 1 · TC-65 — si `CIMENTA_BASH` apunta a algo que no es un bash utilizable, `localizar_bash` lanza `AssertionError`
        con el candidato y el motivo; no se salta ni se da por verde (el pipeline prohíbe `skipped=`)."""
        inexistente = {"CIMENTA_BASH": os.path.join(RAIZ, "no-existe", "bash")}
        with (
            mock.patch.dict(os.environ, inexistente),
            self.assertRaises(AssertionError) as capturado,
        ):
            localizar_bash.__wrapped__()
        self.assertIn("No hay un bash utilizable", str(capturado.exception))
        self.assertIn("no-existe", str(capturado.exception))


class DefinicionDeCIFilaD5(unittest.TestCase):
    """Casos estáticos de la fila D5 sobre `.github/workflows/`. Sin los pasos o sin `enlaces.yml`, fallan; no se saltan."""

    def test_tc65_documentacion_ejecuta_verificador_markdownlint_vale_lychee_y_mmdc_en_orden(self):
        """CA-13 esc. 1 y CA-16 esc. 1 · convenciones §10 · TC-65 — `documentacion`: verificar_docs, markdownlint-cli2@0.24.0, Vale 3.25.1.0
        con la guarda de salida vacía, lychee-action por SHA con `fail: true` y mmdc 12.0.0 por cada Markdown con un diagrama."""
        self.assertEqual(comprobar_tc65_texto(_leer_flujos(self)["ci.yml"]), [])

    def test_tc65_el_paso_de_mermaid_ejecutado_rechaza_el_diagrama_invalido_y_acepta_el_valido(
        self,
    ):
        """CA-16 esc. 1 · TC-65 — se ejecuta el `run:` real con un `mmdc` de mentira: un diagrama inválido (en cualquier posición, aunque
        vengan válidos después) da salida 1 y `::error file=<archivo>::diagrama Mermaid inválido` solo para él; solo válidos, salida 0.
        Límite F006, no exigido: sin ningún Markdown con bloque `mermaid` el paso termina en verde."""
        self.assertEqual(comprobar_comportamiento_de_mermaid(_ci_real(self)), [])

    def test_tc65_el_paso_de_vale_ejecutado_falla_con_una_alerta_o_un_error_y_pasa_sin_ellos(self):
        """CA-13 esc. 1 · TC-65 — se ejecuta el `run:` real con un `uvx` de mentira: una alerta con código 0 da salida 1 y se imprime;
        un error de Vale (código 1) sin salida da salida 1; sin alerta y con código 0 da salida 0."""
        self.assertEqual(comprobar_comportamiento_de_vale(_ci_real(self)), [])

    def test_tc65_documentacion_cumple_las_reglas_comunes_6_7_8_y_9(self):
        """CA-13 esc. 1 · convenciones §10 · TC-65 — los pasos nuevos no se desactivan, no interpolan `${{ }}` en `run:` ni usan tuberías sin `shell: bash`.
        Es una regresión: nace en verde porque hoy el trabajo solo tiene `verificar_docs.py`; deja de serlo si un paso nuevo rompe una regla."""
        trabajos = _trabajos_de_ci(self)
        self.assertIn(DOC, trabajos)
        for regla in (
            comprobar_regla_comun_6,
            comprobar_regla_comun_7,
            comprobar_regla_comun_8,
            comprobar_regla_comun_9,
        ):
            with self.subTest(regla=regla.__name__):
                self.assertEqual(regla(trabajos), [])

    def test_tc65_mermaid_cli_package_json_declara_la_version_exacta_12_0_0(self):
        """CA-16 esc. 1 · TC-65 · regla común 3 — `.github/mermaid/package.json` es privado y declara `@mermaid-js/mermaid-cli` en `12.0.0`, sin `^` ni `~`;
        así `npm ci` no instala un paquete suelto (zizmor: adhoc-packages)."""
        texto = _texto_de_archivo(
            self,
            PACKAGE_JSON_DE_MERMAID,
            "el manifiesto de mermaid-cli de TKT-009d todavía no está definido",
        )
        self.assertEqual(comprobar_package_json_de_mermaid(texto), [])

    def test_tc65_mermaid_cli_package_lock_fija_la_version_12_0_0_con_su_integridad(self):
        """CA-16 esc. 1 · TC-65 · regla común 3 — `.github/mermaid/package-lock.json` (`lockfileVersion` 3) fija `node_modules/@mermaid-js/mermaid-cli`
        en `12.0.0` con `integrity` y su raíz declara la misma versión exacta que el `package.json`."""
        texto = _texto_de_archivo(
            self,
            PACKAGE_LOCK_DE_MERMAID,
            "el lockfile de mermaid-cli de TKT-009d todavía no está definido",
        )
        self.assertEqual(comprobar_package_lock_de_mermaid(texto), [])

    def test_tc65_mermaid_cli_puppeteer_config_lleva_no_sandbox(self):
        """CA-16 esc. 1 · TC-65 — `.github/puppeteer-config.json`, que recibe `mmdc -p`, lleva `--no-sandbox`; sin él Chromium no arranca
        como root en el corredor."""
        texto = _texto_de_archivo(
            self,
            PUPPETEER_CONFIG,
            "la configuración de Puppeteer de TKT-009d todavía no está definida",
        )
        self.assertEqual(comprobar_puppeteer_config(texto), [])

    def test_tc65_gitignore_ignora_node_modules_para_que_npm_ci_no_ensucie_el_arbol(self):
        """CA-16 esc. 1 · TC-65 — `.gitignore` ignora `node_modules` en cualquier profundidad: `npm ci` en `.github/mermaid` no deja cambios pendientes.
        Es una regresión: nace en verde porque la línea ya existe; deja de serlo si alguien la quita o la ancla a la raíz."""
        texto = _texto_de_archivo(self, GITIGNORE, "el .gitignore del repositorio")
        self.assertEqual(comprobar_gitignore_de_node_modules(texto), [])

    def test_tc64_enlaces_se_programa_un_dia_por_semana_y_se_lanza_a_mano(self):
        """CA-14 esc. 1 · convenciones §10 · TC-64 — `enlaces.yml`: `schedule` con `0 13 * * 1`, `workflow_dispatch`, `permissions: contents: read`,
        checkout sin credenciales persistidas y lychee-action por SHA con `--config lychee.toml`, el alcance y `fail: true`."""
        self.assertEqual(comprobar_tc64(_texto_de_enlaces(self)), [])

    def test_tc64_enlaces_usa_la_misma_configuracion_de_lychee_que_el_pr(self):
        """CA-14 esc. 1 · convenciones §10 · TC-64 — los `args`, el `fail` y la versión de lychee de `enlaces.yml` son los del trabajo `documentacion`."""
        self.assertEqual(
            comprobar_misma_configuracion_de_lychee(
                _leer_flujos(self)["ci.yml"], _texto_de_enlaces(self)
            ),
            [],
        )

    def test_car4_los_casos_existentes_recorren_enlaces_yml_y_siguen_en_verde(self):
        """CA-R4 · TC-12, TC-13, TC-21 y TC-22 — con `enlaces.yml` presente, `_leer_flujos` lo lee y los cuatro casos siguen en verde."""
        _texto_de_enlaces(self)
        flujos = _leer_flujos(self)
        self.assertIn("enlaces.yml", flujos)
        self.assertEqual(comprobar_tc12(extraer_trabajos(flujos["ci.yml"])), [])
        for comprobacion in (comprobar_tc13, comprobar_tc21, comprobar_tc22):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(flujos), [])


if __name__ == "__main__":
    unittest.main()
