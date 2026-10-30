"""Pruebas estáticas de `.github/dependabot.yml` y de la ausencia de excepciones en el escaneo de secretos.

TKT-009b · fila B4. Comprueban lo que el repositorio *declara*, no lo que GitHub hace al correr:

* TC-15 (`CA-11` esc. 1): `dependabot.yml` existe, es de la versión 2 y declara exactamente cuatro entradas
  semanales: `uv` (o `pip`, la sustitución que el diseño permite si GitHub rechaza `uv`) en `/backend`,
  `npm` en `/frontend`, `npm` en `/.github/mermaid` (el lock de mermaid-cli, que audita el trabajo `dependencias`,
  RNF-08) y `github-actions` en `/`.
* TC62-08 (TKT-062a, `CA-6` esc. 5): las cuatro entradas llevan `labels:` con exactamente `["agent"]`, para que los PR
  de Dependabot pasen la comprobación «Etiqueta de origen». TC62-R4 (`CA-R4`): TC-15 sigue en verde con `labels:` presente.
* TC-18 (`CA-11` esc. 3 y `CA-R3`), rechazo estático: el diseño **no crea ninguna excepción** para las contraseñas
  de desarrollo de `.env.example` (segunda interpretación señalada en el gate). Por eso no existe
  `.github/secret_scanning.yml`, ningún `paths-ignore` ni otra lista de exclusión de `.github/` cita `.env.example`
  (ni `.env*`) y ningún workflow lee `secrets.`. Además, `.env.example` solo lleva valores `solo-desarrollo-*` o
  las credenciales de prueba declaradas, de modo que no hay nada que excusar.
* TC-16 y TC-17 (el escaneo de secretos y la protección de empuje activos, y el empuje con un token revocado) son
  manuales: son ajustes del repositorio y ninguna prueba estática los ve. No están aquí.

Mismo método que `test_definicion_ci.py`: `tools/` no tiene dependencias y la biblioteca estándar no trae un
analizador de YAML, así que el texto se lee con expresiones regulares, ignorando las líneas comentadas. Cada
comprobación vive en una función `comprobar_*` que devuelve la lista de problemas, y las pruebas sobre texto
sintético demuestran que se ponen en rojo ante cada mutante y por la razón esperada (cada mutante exige un
fragmento del mensaje, no solo que la lista no esté vacía).

Los casos que leen el repositorio real fallan, no se saltan, si falta el archivo que comprueban. Los de TC-18 sobre
el repositorio real nacen en verde por diseño: el invariante ya se cumple (no hay `secret_scanning.yml`, ni
exclusiones, ni `secrets.`), y lo que impide que sean vacuos es que sus mutantes sintéticos sí los ponen en rojo.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_definicion_dependabot -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest

DIRECTORIO_DE_PRUEBAS = os.path.dirname(os.path.abspath(__file__))
if DIRECTORIO_DE_PRUEBAS not in sys.path:
    sys.path.insert(0, DIRECTORIO_DE_PRUEBAS)

from _ayudantes import _sangria, exigir_rojo, exigir_rojo_en_todos, sustituir  # noqa: E402  (la ruta se ajusta arriba)
from test_definicion_ci import (  # noqa: E402
    CLAVE_ANTHROPIC_SINTETICA,
    LINEA_DE_LA_CLAVE,
    LINEA_DEL_PROMPT,
    MOTIVO_DE_OTRO_FLUJO,
    MOTIVO_FUERA_DE_LA_EXCEPCION,
    REVISION_CON_CLAVE,
    motivos_de_secretos,
    sin_comentarios,
)

RAIZ = os.path.dirname(os.path.dirname(DIRECTORIO_DE_PRUEBAS))
DIRECTORIO_GITHUB = os.path.join(RAIZ, ".github")
DEPENDABOT = os.path.join(DIRECTORIO_GITHUB, "dependabot.yml")
ENV_EXAMPLE = os.path.join(RAIZ, ".env.example")

RUTA_DEPENDABOT = ".github/dependabot.yml"
RUTA_CI = ".github/workflows/ci.yml"

# Lo que exige TC-15: (etiqueta, ecosistemas admitidos, directorio). `pip` sustituye a `uv` si GitHub rechaza `uv`.
ENTRADAS_ESPERADAS = (
    ("uv", ("uv", "pip"), "/backend"),
    ("npm", ("npm",), "/frontend"),
    ("npm de mermaid", ("npm",), "/.github/mermaid"),
    ("github-actions", ("github-actions",), "/"),
)
INTERVALO = "weekly"


# ---------------------------------------------------------------------------------------------------------
# Lectura de dependabot.yml
# ---------------------------------------------------------------------------------------------------------


def _desquillar(valor: str) -> str:
    return valor.strip().strip("\"'")


def entradas_de_updates(texto: str) -> list[list[str]]:
    """Cada elemento de la lista `updates:` como líneas, sin comentarios y con el guion inicial convertido en sangría."""
    lineas = sin_comentarios(texto).splitlines()
    inicio = next(
        (k for k, linea in enumerate(lineas) if re.fullmatch(r"updates:\s*", linea)), None
    )
    if inicio is None:
        return []
    entradas: list[list[str]] = []
    sangria_de_elemento = None
    for linea in lineas[inicio + 1 :]:
        if _sangria(linea) == 0:
            break  # otra clave de primer nivel: termina `updates:`
        es_elemento = linea.lstrip().startswith("- ")
        if sangria_de_elemento is None:
            if not es_elemento:
                break
            sangria_de_elemento = _sangria(linea)
        if es_elemento and _sangria(linea) == sangria_de_elemento:
            entradas.append([re.sub(r"^(\s*)- ", lambda m: m.group(1) + "  ", linea, count=1)])
        elif entradas:
            entradas[-1].append(linea)
    return entradas


def _columna_de_claves(entrada: list[str]) -> int:
    return _sangria(entrada[0])


def escalar_de_entrada(entrada: list[str], clave: str) -> str | None:
    """Valor de `clave` en la columna de claves de la entrada, sin comillas; `None` si no está."""
    columna = _columna_de_claves(entrada)
    patron = re.compile(rf"^ {{{columna}}}{re.escape(clave)}:[ \t]*(.*)$")
    for linea in entrada:
        encontrada = patron.match(linea)
        if encontrada:
            return _desquillar(encontrada.group(1))
    return None


def intervalo_de_entrada(entrada: list[str]) -> str | None:
    """`schedule.interval` de la entrada. Un `interval:` fuera de `schedule:` no cuenta."""
    columna = _columna_de_claves(entrada)
    for k, linea in enumerate(entrada):
        if not re.fullmatch(rf" {{{columna}}}schedule:\s*", linea):
            continue
        hijos = []
        for siguiente in entrada[k + 1 :]:
            if _sangria(siguiente) <= columna:
                break
            hijos.append(siguiente)
        if not hijos:
            return None
        columna_hijos = _sangria(hijos[0])
        for hijo in hijos:
            encontrado = re.match(rf"^ {{{columna_hijos}}}interval:[ \t]*(.*)$", hijo)
            if encontrado:
                return _desquillar(encontrado.group(1))
        return None
    return None


def comprobar_tc15(texto: str) -> list[str]:
    """`CA-11` esc. 1 · TC-15. Versión 2 y exactamente cuatro entradas semanales: uv|pip en /backend, npm en /frontend,
    npm en /.github/mermaid (el lock de mermaid-cli) y github-actions en /.

    Hay dos entradas `npm`, así que cada una se asigna por su directorio: primero la entrada con el directorio exacto
    de cada esperada y, con lo que sobre, la primera del mismo ecosistema (para decir que su directorio es otro). Lo que
    aún sobra es una entrada repetida."""
    problemas: list[str] = []
    if not re.search(r"^version:[ \t]*2[ \t]*$", sin_comentarios(texto), re.MULTILINE):
        problemas.append("dependabot.yml debe declarar `version: 2` en la raíz")
    entradas = entradas_de_updates(texto)
    if len(entradas) != len(ENTRADAS_ESPERADAS):
        problemas.append(
            f"debe declarar exactamente cuatro entradas en `updates:` y declara {len(entradas)}"
        )
    admitidos = {
        ecosistema for _, ecosistemas, _ in ENTRADAS_ESPERADAS for ecosistema in ecosistemas
    }
    for entrada in entradas:
        ecosistema = escalar_de_entrada(entrada, "package-ecosystem")
        if ecosistema not in admitidos:
            problemas.append(f"ecosistema no previsto en `updates:`: {ecosistema!r}")

    pendientes = [e for e in entradas if escalar_de_entrada(e, "package-ecosystem") in admitidos]
    asignadas: dict[str, list[str]] = {}
    for exigir_directorio in (True, False):
        for etiqueta, ecosistemas, directorio in ENTRADAS_ESPERADAS:
            if etiqueta in asignadas:
                continue
            for entrada in pendientes:
                if escalar_de_entrada(entrada, "package-ecosystem") not in ecosistemas:
                    continue
                if exigir_directorio and escalar_de_entrada(entrada, "directory") != directorio:
                    continue
                asignadas[etiqueta] = entrada
                pendientes.remove(entrada)
                break
    for etiqueta, ecosistemas, directorio in ENTRADAS_ESPERADAS:
        if etiqueta not in asignadas:
            problemas.append(
                f"falta la entrada de {etiqueta} ({' o '.join(ecosistemas)}) en `updates:`; una entrada comentada no cuenta"
            )
            continue
        entrada = asignadas[etiqueta]
        real = escalar_de_entrada(entrada, "directory")
        if real != directorio:
            problemas.append(f"{etiqueta}: directory debe ser {directorio!r} y es {real!r}")
        intervalo = intervalo_de_entrada(entrada)
        if intervalo != INTERVALO:
            problemas.append(
                f"{etiqueta}: schedule.interval debe ser {INTERVALO!r} y es {intervalo!r}"
            )
    for sobrante in pendientes:
        ecosistema = escalar_de_entrada(sobrante, "package-ecosystem")
        directorio = escalar_de_entrada(sobrante, "directory")
        candidatas = [(et, d) for et, ecos, d in ENTRADAS_ESPERADAS if ecosistema in ecos]
        etiqueta = next((et for et, d in candidatas if d == directorio), candidatas[0][0])
        problemas.append(f"hay más de una entrada de {etiqueta}; debe haber exactamente una")
    return problemas


# ---------------------------------------------------------------------------------------------------------
# TC62-08: la etiqueta `agent` en las cuatro entradas (TKT-062a)
# ---------------------------------------------------------------------------------------------------------

ETIQUETAS_ESPERADAS = ["agent"]
ESCALAR_EN_LABELS = ("<escalar>",)  # lo que devuelve `etiquetas_de_entrada` si `labels:` lleva un valor que no es una lista


def etiquetas_de_entrada(entrada: list[str]) -> list[str] | None:
    """Los elementos de `labels:` en la columna de claves de la entrada, sin comillas ni vacíos; `None` si la clave no está.

    Admite la forma en línea (`labels: ["agent"]`) y la de bloque (`- "agent"`, con la lista más sangrada o al mismo nivel
    que la clave). `labels:` sin elementos, o con una cadena vacía, da la lista vacía: no es lo mismo que no declararla.

    Un valor en la misma línea que no es una lista en línea (que empiece por `[` y termine en `]`), como `labels: agent` o
    `labels: "agent"`, es un escalar: Dependabot lo rechaza, así que devuelve `ESCALAR_EN_LABELS`, que nunca es `["agent"]`."""
    columna = _columna_de_claves(entrada)
    for k, linea in enumerate(entrada):
        encontrada = re.match(rf"^ {{{columna}}}labels:[ \t]*(.*)$", linea)
        if not encontrada:
            continue
        resto = encontrada.group(1).strip()
        if resto:
            if not (resto.startswith("[") and resto.endswith("]")):
                return list(ESCALAR_EN_LABELS)
            elementos = [_desquillar(t) for t in resto[1:-1].split(",")]
            return [t for t in elementos if t]
        elementos = []
        for siguiente in entrada[k + 1 :]:
            es_elemento = siguiente.lstrip().startswith("- ")
            if _sangria(siguiente) > columna or (_sangria(siguiente) == columna and es_elemento):
                if es_elemento:
                    elementos.append(_desquillar(siguiente.lstrip()[2:]))
            else:
                break
        return [t for t in elementos if t]
    return None


def comprobar_tc62_08(texto: str) -> list[str]:
    """`CA-6` esc. 5 · TC62-08. Cada una de las cuatro entradas de `updates:` declara `labels:` con exactamente `["agent"]`:
    ni otra etiqueta, ni etiquetas de más, ni la clave ausente o vacía, ni `Agent` con otra capitalización."""
    entradas = entradas_de_updates(texto)
    problemas: list[str] = []
    if len(entradas) != len(ENTRADAS_ESPERADAS):
        problemas.append(
            f"debe declarar exactamente cuatro entradas en `updates:` y declara {len(entradas)}"
        )
    for entrada in entradas:
        ecosistema = escalar_de_entrada(entrada, "package-ecosystem")
        directorio = escalar_de_entrada(entrada, "directory")
        etiquetas = etiquetas_de_entrada(entrada)
        if etiquetas != ETIQUETAS_ESPERADAS:
            problemas.append(
                f"{ecosistema} {directorio}: labels debe ser {ETIQUETAS_ESPERADAS!r} y es {etiquetas!r}"
            )
    return problemas


# ---------------------------------------------------------------------------------------------------------
# TC-18: ninguna excepción para .env.example
# ---------------------------------------------------------------------------------------------------------

# Claves de YAML cuyo valor es una lista de exclusión. `paths` solo cuenta en sus elementos con negación (`!ruta`).
CLAVES_DE_EXCLUSION = ("paths-ignore", "exclude-paths", "exclude", "ignore")
CITA_ENV = re.compile(r"(?<![A-Za-z0-9_])\.env\b")
EXTENSIONES_DE_TEXTO = (".yml", ".yaml", ".json", ".md", ".txt", ".toml")


def _cuerpo_de_clave(lineas: list[str], k: int, sangria: int, es_elemento: bool, resto: str) -> str:
    """Texto de la clave: lo que sigue en su línea, más las líneas hijas o los elementos de lista al mismo nivel."""
    cuerpo = [resto]
    for siguiente in lineas[k + 1 :]:
        mismo_nivel = (
            _sangria(siguiente) == sangria
            and siguiente.lstrip().startswith("- ")
            and not es_elemento
        )
        if _sangria(siguiente) > sangria or mismo_nivel:
            cuerpo.append(siguiente)
        else:
            break
    return "\n".join(cuerpo)


def _elementos(cuerpo: str) -> list[str]:
    """Elementos de un valor de YAML en bloque o en línea: sin guiones, corchetes, comas ni comillas."""
    return [t for t in re.split(r"[\s,\[\]\"']+", cuerpo) if t and t != "-"]


def listas_de_exclusion(texto: str) -> list[tuple[str, str]]:
    """`(clave, elemento)` de cada elemento de una lista de exclusión del YAML, sin comentarios."""
    lineas = sin_comentarios(texto).splitlines()
    resultado: list[tuple[str, str]] = []
    for k, linea in enumerate(lineas):
        encontrada = re.match(r"^(\s*)(- +)?([A-Za-z0-9_-]+)[ \t]*:[ \t]*(.*)$", linea)
        if not encontrada:
            continue
        clave = encontrada.group(3)
        if clave not in CLAVES_DE_EXCLUSION and clave != "paths":
            continue
        cuerpo = _cuerpo_de_clave(
            lineas, k, len(encontrada.group(1)), bool(encontrada.group(2)), encontrada.group(4)
        )
        for elemento in _elementos(cuerpo):
            if clave == "paths" and not elemento.startswith("!"):
                continue
            resultado.append((clave, elemento))
    return resultado


def comprobar_sin_secret_scanning(archivos: dict[str, str]) -> list[str]:
    """`CA-11` esc. 3 · TC-18. No existe `.github/secret_scanning.yml`: sería una exclusión de rutas del escaneo."""
    return [
        f"{ruta}: existe; el diseño no crea ninguna excepción en el escaneo de secretos (CA-11 esc. 3)"
        for ruta in sorted(archivos)
        if os.path.basename(ruta) in ("secret_scanning.yml", "secret_scanning.yaml")
    ]


def comprobar_sin_exclusion_de_env(archivos: dict[str, str]) -> list[str]:
    """`CA-11` esc. 3 · TC-18. `.env.example` no figura (ni `.env*`) en ninguna lista de exclusión de `.github/`."""
    problemas = []
    for ruta in sorted(archivos):
        if not ruta.endswith((".yml", ".yaml")):
            continue
        for clave, elemento in listas_de_exclusion(archivos[ruta]):
            if CITA_ENV.search(elemento):
                problemas.append(
                    f"{ruta}: la lista `{clave}` excluye {elemento!r}; `.env.example` no se excluye del escaneo (CA-11 esc. 3)"
                )
    return problemas


def comprobar_sin_secrets_en_flujos(archivos: dict[str, str]) -> list[str]:
    """`CA-R3` y `CA-7` · TC-18. Ningún workflow declara `secrets.`, `secrets[` ni `secrets:`, salvo la excepción nombrada de
    `revision-ia.yml` (`motivos_de_secretos`, compartida con TC-22). El envoltorio pasa el nombre base y antepone la ruta completa."""
    problemas = []
    for ruta in sorted(archivos):
        if not ruta.startswith(".github/workflows/") or not ruta.endswith((".yml", ".yaml")):
            continue
        problemas += [f"{ruta}: {motivo}" for motivo in motivos_de_secretos(os.path.basename(ruta), archivos[ruta])]
    return problemas


def comprobar_tc18(archivos: dict[str, str]) -> list[str]:
    """`CA-11` esc. 3 y `CA-R3` · TC-18: las tres comprobaciones sobre los archivos de `.github/` (ruta relativa a la raíz -> texto)."""
    return (
        comprobar_sin_secret_scanning(archivos)
        + comprobar_sin_exclusion_de_env(archivos)
        + comprobar_sin_secrets_en_flujos(archivos)
    )


# Credenciales sintéticas de las pruebas: se arman por concatenación para que ningún escáner de secretos
# las vea enteras en este archivo.
CLAVE_AWS_SINTETICA = "AKIA" + "ABCDEFGHIJKLMNOP"
TOKEN_GITHUB_SINTETICO = "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789"

# Valores con forma de credencial real, vengan en la clave que vengan.
FORMAS_DE_CREDENCIAL = (
    r"AKIA[0-9A-Z]{16}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9]{20,}",
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
)
CLAVE_SENSIBLE = re.compile(r"CONTRASENA|PASSWORD|SECRET|TOKEN|CLAVE|KEY|LLAVE|CREDENCIAL")
PREFIJO_DE_PRUEBA = "CIMENTA_PRUEBA_"
PREFIJO_DE_DESARROLLO = "solo-desarrollo-"


def comprobar_env_example(texto: str) -> list[str]:
    """RNF-07 · `CA-11` esc. 3. Toda clave sensible lleva un valor `solo-desarrollo-*` o es una credencial de prueba declarada
    (`CIMENTA_PRUEBA_*`, con un comentario que diga PRUEBA); ningún valor tiene forma de credencial real."""
    problemas = []
    hay_prueba = False
    for linea in texto.splitlines():
        if linea.lstrip().startswith("#"):
            continue
        encontrada = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", linea.strip())
        if not encontrada:
            continue
        clave = encontrada.group(1)
        valor = _desquillar(re.split(r"\s+#", encontrada.group(2), maxsplit=1)[0])
        for forma in FORMAS_DE_CREDENCIAL:
            if re.search(forma, valor):
                problemas.append(f"{clave}: el valor tiene forma de credencial real ({forma})")
        if clave.startswith(PREFIJO_DE_PRUEBA):
            hay_prueba = True
        elif CLAVE_SENSIBLE.search(clave) and valor and not valor.startswith(PREFIJO_DE_DESARROLLO):
            problemas.append(
                f"{clave}: una clave sensible solo puede llevar un valor {PREFIJO_DE_DESARROLLO}* o ser una credencial de prueba declarada"
            )
    if hay_prueba and not any(
        re.search(r"\bPRUEBA\b", linea)
        for linea in texto.splitlines()
        if linea.lstrip().startswith("#")
    ):
        problemas.append(
            "hay credenciales CIMENTA_PRUEBA_* y ningún comentario que las declare como de PRUEBA"
        )
    return problemas


# ---------------------------------------------------------------------------------------------------------
# Lectura del repositorio real
# ---------------------------------------------------------------------------------------------------------


def _leer_dependabot(caso: unittest.TestCase) -> str:
    """El texto de `dependabot.yml`. Sin el archivo el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(DEPENDABOT):
        caso.fail(
            f"No existe {os.path.relpath(DEPENDABOT, RAIZ)}: la fila B4 de TKT-009b todavía no lo crea"
        )
    with open(DEPENDABOT, encoding="utf-8") as archivo:
        return archivo.read()


def _leer_github(caso: unittest.TestCase) -> dict[str, str]:
    """Ruta relativa a la raíz (con `/`) -> texto de cada archivo bajo `.github/`. Exige `ci.yml`, para que ningún caso sea vacuo."""
    archivos: dict[str, str] = {}
    for carpeta, _, nombres in os.walk(DIRECTORIO_GITHUB):
        for nombre in nombres:
            ruta = os.path.join(carpeta, nombre)
            relativa = os.path.relpath(ruta, RAIZ).replace(os.sep, "/")
            texto = ""
            if nombre.endswith(EXTENSIONES_DE_TEXTO):
                with open(ruta, encoding="utf-8", errors="replace") as archivo:
                    texto = archivo.read()
            archivos[relativa] = texto
    if RUTA_CI not in archivos:
        caso.fail(f"No existe {RUTA_CI}: sin él, las comprobaciones de TC-18 no examinan nada")
    return archivos


# ---------------------------------------------------------------------------------------------------------
# Texto sintético
# ---------------------------------------------------------------------------------------------------------

ENTRADA_UV = """\
  # Python: el lock de uv
  - package-ecosystem: "uv"
    directory: "/backend"
    schedule:
      interval: "weekly"
"""
ENTRADA_NPM = """\
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
"""
ENTRADA_MERMAID = """\
  # npm: el lock de mermaid-cli, que audita el trabajo `dependencias`
  - package-ecosystem: "npm"
    directory: "/.github/mermaid"
    schedule:
      interval: "weekly"
"""
ENTRADA_ACTIONS = """\
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
"""
CABECERA = "# Actualizaciones semanales de dependencias.\nversion: 2\nupdates:\n"
DEPENDABOT_VALIDO = CABECERA + ENTRADA_UV + ENTRADA_NPM + ENTRADA_MERMAID + ENTRADA_ACTIONS


ETIQUETA_AGENT = '    labels:\n      - "agent"\n'


def con_etiquetas(*bloques: str) -> str:
    """`DEPENDABOT_VALIDO` con un bloque de `labels:` (texto ya sangrado, o cadena vacía) tras cada una de las cuatro entradas."""
    assert len(bloques) == 4, "un bloque por entrada: uv, npm, npm de mermaid y github-actions"
    entradas = (ENTRADA_UV, ENTRADA_NPM, ENTRADA_MERMAID, ENTRADA_ACTIONS)
    return CABECERA + "".join(e + b for e, b in zip(entradas, bloques, strict=True))


DEPENDABOT_CON_ETIQUETA = con_etiquetas(*[ETIQUETA_AGENT] * 4)


def comentada(entrada: str) -> str:
    return "".join("  # " + linea.strip() + "\n" for linea in entrada.splitlines() if linea.strip())


class PruebasDeMutantesDeTC15(unittest.TestCase):
    """Cada rechazo de TC-15 se prueba sobre texto sintético: su verde es el de la comprobación, no el de `dependabot.yml`."""

    def test_tc15_mutantes_el_texto_valido_pasa(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — control: la base cumple; sin esto un rojo podría ser del texto base."""
        self.assertEqual(comprobar_tc15(DEPENDABOT_VALIDO), [])

    def test_tc15_mutantes_formas_equivalentes_validas_siguen_en_verde(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — `pip` en lugar de `uv`, comillas simples o ninguna, otro orden de claves, opciones de más y comentarios al final no rompen el caso."""
        validos = {
            "pip en lugar de uv": sustituir(
                DEPENDABOT_VALIDO, 'package-ecosystem: "uv"', 'package-ecosystem: "pip"'
            ),
            "comillas simples": DEPENDABOT_VALIDO.replace('"', "'"),
            "sin comillas": DEPENDABOT_VALIDO.replace('"', ""),
            "otro orden de entradas": CABECERA
            + ENTRADA_ACTIONS
            + ENTRADA_MERMAID
            + ENTRADA_NPM
            + ENTRADA_UV,
            "la de mermaid antes que la de frontend": CABECERA
            + ENTRADA_UV
            + ENTRADA_MERMAID
            + ENTRADA_NPM
            + ENTRADA_ACTIONS,
            "schedule antes de directory": sustituir(
                DEPENDABOT_VALIDO,
                '    directory: "/frontend"\n    schedule:\n      interval: "weekly"\n',
                '    schedule:\n      interval: "weekly"\n    directory: "/frontend"\n',
            ),
            "opciones de más": sustituir(
                DEPENDABOT_VALIDO,
                '    directory: "/frontend"\n',
                '    directory: "/frontend"\n    open-pull-requests-limit: 5\n    labels:\n      - "dependencias"\n',
            ),
            "opciones de más en la entrada de mermaid": sustituir(
                DEPENDABOT_VALIDO,
                '    directory: "/.github/mermaid"\n',
                '    directory: "/.github/mermaid"\n    open-pull-requests-limit: 3\n',
            ),
            "comentarios al final de línea": sustituir(
                DEPENDABOT_VALIDO,
                'directory: "/backend"',
                'directory: "/backend"  # el lock vive aquí',
            ),
            "entrada que abre con otra clave": sustituir(
                DEPENDABOT_VALIDO,
                '  - package-ecosystem: "npm"\n    directory: "/frontend"\n',
                '  - directory: "/frontend"\n    package-ecosystem: "npm"\n',
            ),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc15(texto), [])

    def test_tc15_mutantes_falta_un_ecosistema(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: sin cualquiera de las cuatro entradas, en especial la de mermaid, el caso falla y nombra cuál falta."""
        casos = {
            "sin uv ni pip": (DEPENDABOT_VALIDO.replace(ENTRADA_UV, ""), "falta la entrada de uv"),
            "sin npm de frontend": (
                DEPENDABOT_VALIDO.replace(ENTRADA_NPM, ""),
                "falta la entrada de npm (npm)",
            ),
            "sin npm de mermaid": (
                DEPENDABOT_VALIDO.replace(ENTRADA_MERMAID, ""),
                "falta la entrada de npm de mermaid",
            ),
            "solo uv y github-actions": (
                DEPENDABOT_VALIDO.replace(ENTRADA_NPM, "").replace(ENTRADA_MERMAID, ""),
                "falta la entrada de npm de mermaid",
            ),
            "sin github-actions": (
                DEPENDABOT_VALIDO.replace(ENTRADA_ACTIONS, ""),
                "falta la entrada de github-actions",
            ),
            "sin updates": (CABECERA, "falta la entrada de uv"),
            "ecosistema de otro lenguaje en lugar de npm de frontend": (
                sustituir(
                    DEPENDABOT_VALIDO,
                    '"npm"\n    directory: "/frontend"',
                    '"bundler"\n    directory: "/frontend"',
                ),
                "falta la entrada de npm (npm)",
            ),
            "ecosistema de otro lenguaje en lugar de npm de mermaid": (
                sustituir(
                    DEPENDABOT_VALIDO,
                    '"npm"\n    directory: "/.github/mermaid"',
                    '"bundler"\n    directory: "/.github/mermaid"',
                ),
                "falta la entrada de npm de mermaid",
            ),
            "docker en lugar de github-actions": (
                sustituir(
                    DEPENDABOT_VALIDO,
                    'package-ecosystem: "github-actions"',
                    'package-ecosystem: "docker"',
                ),
                "falta la entrada de github-actions",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)

    def test_tc15_mutantes_una_entrada_comentada_no_cuenta(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: la entrada comentada de cada ecosistema equivale a no tenerla."""
        casos = {
            "uv comentada": (
                DEPENDABOT_VALIDO.replace(ENTRADA_UV, comentada(ENTRADA_UV)),
                "falta la entrada de uv",
            ),
            "npm comentada": (
                DEPENDABOT_VALIDO.replace(ENTRADA_NPM, comentada(ENTRADA_NPM)),
                "falta la entrada de npm (npm)",
            ),
            "npm de mermaid comentada": (
                DEPENDABOT_VALIDO.replace(ENTRADA_MERMAID, comentada(ENTRADA_MERMAID)),
                "falta la entrada de npm de mermaid",
            ),
            "github-actions comentada": (
                DEPENDABOT_VALIDO.replace(ENTRADA_ACTIONS, comentada(ENTRADA_ACTIONS)),
                "falta la entrada de github-actions",
            ),
            "version comentada": (
                sustituir(DEPENDABOT_VALIDO, "version: 2\n", "# version: 2\n"),
                "version: 2",
            ),
            "interval comentado": (
                sustituir(
                    DEPENDABOT_VALIDO.replace(ENTRADA_ACTIONS, ""),
                    '      interval: "weekly"\n  - package-ecosystem: "npm"',
                    '      # interval: "weekly"\n  - package-ecosystem: "npm"',
                ),
                "uv: schedule.interval debe ser 'weekly'",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)

    def test_tc15_mutantes_directorio_equivocado(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: el directorio de cada entrada es el del manifiesto de su ecosistema; ni otro, ni sin barra, ni ausente."""
        casos = {
            "uv en la raíz": (
                sustituir(DEPENDABOT_VALIDO, 'directory: "/backend"', 'directory: "/"'),
                "uv: directory debe ser '/backend' y es '/'",
            ),
            "uv sin barra": (
                sustituir(DEPENDABOT_VALIDO, 'directory: "/backend"', 'directory: "backend"'),
                "uv: directory debe ser '/backend' y es 'backend'",
            ),
            "npm en backend": (
                sustituir(DEPENDABOT_VALIDO, 'directory: "/frontend"', 'directory: "/backend"'),
                "npm: directory debe ser '/frontend' y es '/backend'",
            ),
            "github-actions en .github": (
                sustituir(DEPENDABOT_VALIDO, 'directory: "/"', 'directory: "/.github/workflows"'),
                "github-actions: directory debe ser '/'",
            ),
            "mermaid repetida con /frontend": (
                sustituir(
                    DEPENDABOT_VALIDO, 'directory: "/.github/mermaid"', 'directory: "/frontend"'
                ),
                "npm de mermaid: directory debe ser '/.github/mermaid' y es '/frontend'",
            ),
            "mermaid en /.github": (
                sustituir(
                    DEPENDABOT_VALIDO, 'directory: "/.github/mermaid"', 'directory: "/.github"'
                ),
                "npm de mermaid: directory debe ser '/.github/mermaid' y es '/.github'",
            ),
            "mermaid sin barra inicial": (
                sustituir(
                    DEPENDABOT_VALIDO,
                    'directory: "/.github/mermaid"',
                    'directory: ".github/mermaid"',
                ),
                "npm de mermaid: directory debe ser '/.github/mermaid' y es '.github/mermaid'",
            ),
            "mermaid en el directorio del workflow": (
                sustituir(
                    DEPENDABOT_VALIDO,
                    'directory: "/.github/mermaid"',
                    'directory: "/.github/workflows"',
                ),
                "npm de mermaid: directory debe ser '/.github/mermaid' y es '/.github/workflows'",
            ),
            "mermaid sin directory": (
                sustituir(DEPENDABOT_VALIDO, '    directory: "/.github/mermaid"\n', ""),
                "npm de mermaid: directory debe ser '/.github/mermaid' y es None",
            ),
            "directory con subdirectorio": (
                sustituir(
                    DEPENDABOT_VALIDO, 'directory: "/frontend"', 'directory: "/frontend/src"'
                ),
                "npm: directory debe ser '/frontend'",
            ),
            "directories en lugar de directory": (
                sustituir(
                    DEPENDABOT_VALIDO, 'directory: "/frontend"', 'directories:\n      - "/frontend"'
                ),
                "npm: directory debe ser '/frontend' y es None",
            ),
            "sin directory": (
                sustituir(DEPENDABOT_VALIDO, '    directory: "/frontend"\n', ""),
                "npm: directory debe ser '/frontend' y es None",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)

    def test_tc15_mutantes_intervalo_distinto_de_semanal(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: cada entrada es semanal; ni diaria, ni mensual, ni sin `schedule`, ni con `interval` fuera de `schedule`."""
        casos = {
            "uv diaria": (
                sustituir(
                    DEPENDABOT_VALIDO.replace(ENTRADA_NPM, "")
                    .replace(ENTRADA_MERMAID, "")
                    .replace(ENTRADA_ACTIONS, ""),
                    'interval: "weekly"',
                    'interval: "daily"',
                ),
                "uv: schedule.interval debe ser 'weekly' y es 'daily'",
            ),
            "npm mensual": (
                DEPENDABOT_VALIDO.replace(ENTRADA_NPM, ENTRADA_NPM.replace("weekly", "monthly")),
                "npm: schedule.interval debe ser 'weekly' y es 'monthly'",
            ),
            "npm de mermaid mensual": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_MERMAID, ENTRADA_MERMAID.replace("weekly", "monthly")
                ),
                "npm de mermaid: schedule.interval debe ser 'weekly' y es 'monthly'",
            ),
            "npm de mermaid diaria": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_MERMAID, ENTRADA_MERMAID.replace("weekly", "daily")
                ),
                "npm de mermaid: schedule.interval debe ser 'weekly' y es 'daily'",
            ),
            "npm de mermaid sin schedule": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_MERMAID,
                    '  - package-ecosystem: "npm"\n    directory: "/.github/mermaid"\n',
                ),
                "npm de mermaid: schedule.interval debe ser 'weekly' y es None",
            ),
            "github-actions diaria": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_ACTIONS, ENTRADA_ACTIONS.replace("weekly", "daily")
                ),
                "github-actions: schedule.interval debe ser 'weekly' y es 'daily'",
            ),
            "schedule sin interval": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_NPM,
                    '  - package-ecosystem: "npm"\n    directory: "/frontend"\n    schedule:\n      day: "monday"\n',
                ),
                "npm: schedule.interval debe ser 'weekly' y es None",
            ),
            "sin schedule": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_NPM, '  - package-ecosystem: "npm"\n    directory: "/frontend"\n'
                ),
                "npm: schedule.interval debe ser 'weekly' y es None",
            ),
            "interval fuera de schedule": (
                DEPENDABOT_VALIDO.replace(
                    ENTRADA_NPM,
                    '  - package-ecosystem: "npm"\n    directory: "/frontend"\n    interval: "weekly"\n',
                ),
                "npm: schedule.interval debe ser 'weekly' y es None",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)

    def test_tc15_mutantes_version_y_numero_de_entradas(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: versión distinta de 2 o ausente, una quinta entrada y una entrada repetida con el mismo directorio."""
        casos = {
            "version 1": (sustituir(DEPENDABOT_VALIDO, "version: 2", "version: 1"), "`version: 2`"),
            "version entre comillas": (
                sustituir(DEPENDABOT_VALIDO, "version: 2", 'version: "2"'),
                "`version: 2`",
            ),
            "sin version": (sustituir(DEPENDABOT_VALIDO, "version: 2\n", ""), "`version: 2`"),
            "una quinta entrada": (
                DEPENDABOT_VALIDO
                + '  - package-ecosystem: "docker"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n',
                "exactamente cuatro entradas",
            ),
            "una quinta entrada npm en otro directorio": (
                DEPENDABOT_VALIDO
                + '  - package-ecosystem: "npm"\n    directory: "/frontend/src"\n    schedule:\n      interval: "weekly"\n',
                "exactamente cuatro entradas",
            ),
            "solo tres entradas (la antigua tríada)": (
                DEPENDABOT_VALIDO.replace(ENTRADA_MERMAID, ""),
                "exactamente cuatro entradas",
            ),
            "npm de frontend repetida con el mismo directorio": (
                DEPENDABOT_VALIDO + ENTRADA_NPM,
                "más de una entrada de npm;",
            ),
            "npm de mermaid repetida con el mismo directorio": (
                DEPENDABOT_VALIDO + ENTRADA_MERMAID,
                "más de una entrada de npm de mermaid",
            ),
            "uv y pip a la vez": (
                DEPENDABOT_VALIDO + ENTRADA_UV.replace('"uv"', '"pip"'),
                "más de una entrada de uv",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)

    def test_tc15_mutantes_el_archivo_vacio_o_sin_updates_falla_en_todo(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: un archivo vacío no pasa por vacuidad."""
        for texto in ("", "version: 2\n", "version: 2\nupdates:\n"):
            with self.subTest(texto=texto):
                problemas = comprobar_tc15(texto)
                self.assertTrue(
                    any("exactamente cuatro entradas" in p for p in problemas), problemas
                )


class DefinicionDeDependabot(unittest.TestCase):
    """Fila B4 sobre `.github/dependabot.yml`. Sin el archivo, falla; no se salta."""

    def test_tc15_dependabot_declara_uv_npm_dos_veces_y_github_actions_semanales(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 y TKT-062a · CA-R4 esc. 1 · TC62-R4 — versión 2 y cuatro entradas semanales: uv (o pip) en /backend,
        npm en /frontend, npm en /.github/mermaid y github-actions en /. El archivo real ya lleva `labels:` en las cuatro, así que este
        mismo caso es la regresión de TC-15 con `labels:` presente."""
        self.assertEqual(comprobar_tc15(_leer_dependabot(self)), [])

    def test_tkt062_ca06_esc05_dependabot_etiqueta_agent_en_sus_cuatro_entradas(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — las cuatro entradas de `dependabot.yml` declaran `labels: ["agent"]`, y solo esa."""
        self.assertEqual(comprobar_tc62_08(_leer_dependabot(self)), [])


class PruebasDeMutantesDeTC62_08(unittest.TestCase):
    """TC62-08 sobre texto sintético: su verde es el de la comprobación, no el de `dependabot.yml`."""

    def test_tkt062_ca06_esc05_mutantes_el_texto_con_las_cuatro_etiquetas_pasa(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — control positivo: la base con `labels: ["agent"]` en las cuatro entradas cumple."""
        self.assertEqual(comprobar_tc62_08(DEPENDABOT_CON_ETIQUETA), [])

    def test_tkt062_ca06_esc05_mutantes_formas_equivalentes_validas_siguen_en_verde(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — control: la forma en línea, las comillas simples o ninguna, la lista al mismo nivel que la clave y los comentarios no rompen el caso."""
        validos = {
            "en línea": con_etiquetas(*['    labels: ["agent"]\n'] * 4),
            "en línea sin comillas": con_etiquetas(*["    labels: [agent]\n"] * 4),
            "comillas simples": con_etiquetas(*["    labels:\n      - 'agent'\n"] * 4),
            "sin comillas": con_etiquetas(*["    labels:\n      - agent\n"] * 4),
            "lista al mismo nivel que la clave": con_etiquetas(*["    labels:\n    - agent\n"] * 4),
            "con comentario al final": con_etiquetas(
                *['    labels:\n      - "agent"  # el origen del PR\n'] * 4
            ),
            "con una etiqueta comentada": con_etiquetas(
                *['    labels:\n      - "agent"\n      # - "dependencies"\n'] * 4
            ),
            "labels antes que schedule": sustituir(
                DEPENDABOT_CON_ETIQUETA,
                '  - package-ecosystem: "github-actions"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n    labels:\n      - "agent"\n',
                '  - package-ecosystem: "github-actions"\n    directory: "/"\n    labels:\n      - "agent"\n    schedule:\n      interval: "weekly"\n',
            ),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc62_08(texto), [])

    def test_tkt062_ca06_esc05_mutantes_una_entrada_sin_labels(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — rechazo: cualquiera de las cuatro sin `labels:` falla y nombra cuál."""
        agent = ETIQUETA_AGENT
        casos = {
            "uv sin labels": (
                con_etiquetas("", agent, agent, agent),
                "uv /backend: labels debe ser ['agent'] y es None",
            ),
            "npm sin labels": (
                con_etiquetas(agent, "", agent, agent),
                "npm /frontend: labels debe ser ['agent'] y es None",
            ),
            "npm de mermaid sin labels": (
                con_etiquetas(agent, agent, "", agent),
                "npm /.github/mermaid: labels debe ser ['agent'] y es None",
            ),
            "github-actions sin labels": (
                con_etiquetas(agent, agent, agent, ""),
                "github-actions /: labels debe ser ['agent'] y es None",
            ),
            "ninguna con labels (el dependabot.yml de antes)": (
                DEPENDABOT_VALIDO,
                "uv /backend: labels debe ser ['agent'] y es None",
            ),
            "labels comentada": (
                con_etiquetas(
                    '    # labels:\n    #   - "agent"\n', agent, agent, agent
                ),
                "uv /backend: labels debe ser ['agent'] y es None",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc62_08, casos)

    def test_tkt062_ca06_esc05_mutantes_una_etiqueta_que_no_es_solo_agent(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — rechazo: otra etiqueta, una de más, la capitalización distinta, una repetida, `labels` vacía o un escalar en lugar de una lista fallan con el dato real."""
        agent = ETIQUETA_AGENT
        casos = {
            "labels: dependencies": (
                con_etiquetas('    labels:\n      - "dependencies"\n', agent, agent, agent),
                "uv /backend: labels debe ser ['agent'] y es ['dependencies']",
            ),
            "labels: agent y dependencies": (
                con_etiquetas(
                    agent, agent, agent, '    labels:\n      - "agent"\n      - "dependencies"\n'
                ),
                "github-actions /: labels debe ser ['agent'] y es ['agent', 'dependencies']",
            ),
            "labels: dependencies y agent (otro orden)": (
                con_etiquetas(
                    agent, '    labels:\n      - "dependencies"\n      - "agent"\n', agent, agent
                ),
                "npm /frontend: labels debe ser ['agent'] y es ['dependencies', 'agent']",
            ),
            "labels vacío en bloque": (
                con_etiquetas(agent, agent, "    labels:\n", agent),
                "npm /.github/mermaid: labels debe ser ['agent'] y es []",
            ),
            "labels vacío en línea": (
                con_etiquetas("    labels: []\n", agent, agent, agent),
                "uv /backend: labels debe ser ['agent'] y es []",
            ),
            "labels con cadena vacía": (
                con_etiquetas(agent, agent, agent, '    labels:\n      - ""\n'),
                "github-actions /: labels debe ser ['agent'] y es []",
            ),
            'labels: ["Agent"]': (
                con_etiquetas(agent, '    labels:\n      - "Agent"\n', agent, agent),
                "npm /frontend: labels debe ser ['agent'] y es ['Agent']",
            ),
            'labels: ["AGENT"] en línea': (
                con_etiquetas(agent, agent, '    labels: ["AGENT"]\n', agent),
                "npm /.github/mermaid: labels debe ser ['agent'] y es ['AGENT']",
            ),
            "agent repetida": (
                con_etiquetas('    labels:\n      - "agent"\n      - "agent"\n', agent, agent, agent),
                "uv /backend: labels debe ser ['agent'] y es ['agent', 'agent']",
            ),
            "agent con espacio": (
                con_etiquetas(agent, agent, agent, '    labels: ["agent "]\n'),
                "github-actions /: labels debe ser ['agent'] y es ['agent ']",
            ),
            "una etiqueta parecida": (
                con_etiquetas(agent, agent, agent, '    labels:\n      - "agents"\n'),
                "github-actions /: labels debe ser ['agent'] y es ['agents']",
            ),
            'labels: "agent" (escalar entre comillas)': (
                con_etiquetas('    labels: "agent"\n', agent, agent, agent),
                "uv /backend: labels debe ser ['agent'] y es ['<escalar>']",
            ),
            "labels: agent (escalar sin comillas)": (
                con_etiquetas(agent, agent, "    labels: agent\n", agent),
                "npm /.github/mermaid: labels debe ser ['agent'] y es ['<escalar>']",
            ),
            "labels: [agent (lista en línea sin cerrar)": (
                con_etiquetas(agent, "    labels: [agent\n", agent, agent),
                "npm /frontend: labels debe ser ['agent'] y es ['<escalar>']",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc62_08, casos)

    def test_tkt062_ca06_esc05_mutantes_el_numero_de_entradas_sigue_siendo_cuatro(self):
        """TKT-062a · CA-6 esc. 5 · TC62-08 — rechazo: una quinta entrada, aunque lleve la etiqueta, o solo tres, no pasan por vacuidad."""
        casos = {
            "una quinta entrada": (
                DEPENDABOT_CON_ETIQUETA
                + '  - package-ecosystem: "docker"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n'
                + ETIQUETA_AGENT,
                "exactamente cuatro entradas",
            ),
            "solo tres entradas": (
                DEPENDABOT_CON_ETIQUETA.replace(ENTRADA_MERMAID + ETIQUETA_AGENT, ""),
                "exactamente cuatro entradas",
            ),
            "sin updates": (CABECERA, "exactamente cuatro entradas"),
        }
        exigir_rojo_en_todos(self, comprobar_tc62_08, casos)


class PruebasDeRegresionDeTC15ConEtiqueta(unittest.TestCase):
    """TC62-R4 sobre texto sintético: `labels:` no rompe TC-15 y no deja pasar sus mutantes."""

    def test_tkt062_car4_esc01_tc15_sigue_en_verde_con_labels_agent_en_las_cuatro_entradas(self):
        """TKT-062a · CA-R4 esc. 1 · TC62-R4 — la base con `labels: ["agent"]` en las cuatro entradas sigue cumpliendo TC-15: cuatro apartados, semanales."""
        self.assertEqual(comprobar_tc15(DEPENDABOT_CON_ETIQUETA), [])

    def test_tkt062_car4_esc01_tc15_sigue_en_verde_con_labels_en_linea_o_de_bloque(self):
        """TKT-062a · CA-R4 esc. 1 · TC62-R4 — `labels:` en línea, en bloque, vacía o con otras etiquetas no cambia el veredicto de TC-15 (eso es asunto de TC62-08)."""
        for descripcion, texto in {
            "en línea": con_etiquetas(*['    labels: ["agent"]\n'] * 4),
            "con otra etiqueta": con_etiquetas(*['    labels:\n      - "dependencies"\n'] * 4),
            "vacía": con_etiquetas(*["    labels: []\n"] * 4),
        }.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc15(texto), [])

    def test_tkt062_car4_esc01_tc15_sigue_rechazando_con_labels_presente(self):
        """TKT-062a · CA-R4 esc. 1 · TC62-R4 — con `labels:` en las cuatro entradas, TC-15 sigue en rojo ante una entrada que falta, un intervalo distinto y una quinta entrada."""
        casos = {
            "sin la entrada de mermaid": (
                DEPENDABOT_CON_ETIQUETA.replace(ENTRADA_MERMAID + ETIQUETA_AGENT, ""),
                "exactamente cuatro entradas",
            ),
            "github-actions diaria": (
                DEPENDABOT_CON_ETIQUETA.replace(
                    ENTRADA_ACTIONS, ENTRADA_ACTIONS.replace("weekly", "daily")
                ),
                "github-actions: schedule.interval debe ser 'weekly' y es 'daily'",
            ),
            "una quinta entrada": (
                DEPENDABOT_CON_ETIQUETA
                + '  - package-ecosystem: "docker"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n'
                + ETIQUETA_AGENT,
                "exactamente cuatro entradas",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc15, casos)


class PruebasDeMutantesDeTC18(unittest.TestCase):
    """Cada rechazo de TC-18 se prueba sobre archivos sintéticos de `.github/`."""

    CI_VALIDO = (
        "name: CI\n"
        "on:\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  humo:\n"
        "    runs-on: ubuntu-24.04\n"
        "    steps:\n"
        "      - run: cp .env.example .env\n"
    )

    def base(self) -> dict[str, str]:
        return {RUTA_CI: self.CI_VALIDO, RUTA_DEPENDABOT: DEPENDABOT_VALIDO}

    def con_ci(self, ci: str) -> dict[str, str]:
        return {**self.base(), RUTA_CI: ci}

    def test_tc18_mutantes_la_base_pasa_aunque_el_flujo_nombre_env_example(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — control: `cp .env.example .env` en un `run:` no es una exclusión y la base pasa."""
        self.assertEqual(comprobar_tc18(self.base()), [])

    def test_tc18_mutantes_un_secret_scanning_yml_es_una_excepcion(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: `secret_scanning.yml` (o `.yaml`) en `.github/` excluye rutas del escaneo y no debe existir."""
        casos = {
            "secret_scanning.yml": (
                {
                    **self.base(),
                    ".github/secret_scanning.yml": "paths-ignore:\n  - '.env.example'\n",
                },
                ".github/secret_scanning.yml",
            ),
            "secret_scanning.yaml": (
                {**self.base(), ".github/secret_scanning.yaml": "paths-ignore: []\n"},
                ".github/secret_scanning.yaml",
            ),
            "secret_scanning.yml vacío": (
                {**self.base(), ".github/secret_scanning.yml": ""},
                "secret_scanning.yml",
            ),
            "secret_scanning.yml en una subcarpeta": (
                {**self.base(), ".github/config/secret_scanning.yml": ""},
                "secret_scanning.yml",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc18, casos)

    def test_tc18_mutantes_paths_ignore_que_cita_env_example_en_un_workflow(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: un `paths-ignore` con `.env.example` o `.env*`, en bloque o en línea, se detecta y nombra el archivo."""

        def con_paths_ignore(cuerpo: str) -> dict[str, str]:
            return self.con_ci(
                sustituir(self.CI_VALIDO, "    branches: [main]\n", f"    paths-ignore:\n{cuerpo}")
            )

        casos = {
            "en bloque": (
                con_paths_ignore("      - .env.example\n"),
                f"{RUTA_CI}: la lista `paths-ignore` excluye '.env.example'",
            ),
            "entre comillas": (
                con_paths_ignore("      - '.env.example'\n"),
                "excluye '.env.example'",
            ),
            "con otras rutas antes": (
                con_paths_ignore("      - 'docs/**'\n      - .env.example\n"),
                "excluye '.env.example'",
            ),
            "con otras rutas después": (
                con_paths_ignore("      - .env.example\n      - 'docs/**'\n"),
                "excluye '.env.example'",
            ),
            "comodín .env*": (con_paths_ignore("      - '.env*'\n"), "excluye '.env*'"),
            "comodín **/.env*": (con_paths_ignore("      - '**/.env*'\n"), "excluye '**/.env*'"),
            ".env a secas": (con_paths_ignore("      - .env\n"), "excluye '.env'"),
            "en línea": (
                self.con_ci(
                    sustituir(
                        self.CI_VALIDO,
                        "    branches: [main]\n",
                        '    paths-ignore: [".env.example", "docs/**"]\n',
                    )
                ),
                "excluye '.env.example'",
            ),
            "elementos de lista al mismo nivel que la clave": (
                self.con_ci(
                    sustituir(
                        self.CI_VALIDO,
                        "    branches: [main]\n",
                        "    paths-ignore:\n    - .env.example\n",
                    )
                ),
                "excluye '.env.example'",
            ),
            "paths con negación": (
                self.con_ci(
                    sustituir(
                        self.CI_VALIDO,
                        "    branches: [main]\n",
                        "    paths:\n      - '**'\n      - '!.env.example'\n",
                    )
                ),
                "excluye '!.env.example'",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc18, casos)

    def test_tc18_mutantes_la_exclusion_tambien_se_detecta_fuera_de_ci_yml_y_de_los_workflows(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: otro workflow, `dependabot.yml` o cualquier YAML de `.github/` con `.env.example` en una exclusión."""
        excluyendo_en_push = "name: Otro\non:\n  push:\n    paths-ignore:\n      - .env.example\n"
        casos = {
            "otro workflow": (
                {**self.base(), ".github/workflows/otro.yml": excluyendo_en_push},
                ".github/workflows/otro.yml: la lista `paths-ignore` excluye",
            ),
            "dependabot.yml con exclude-paths": (
                {
                    **self.base(),
                    RUTA_DEPENDABOT: sustituir(
                        DEPENDABOT_VALIDO,
                        '    directory: "/"\n',
                        '    directory: "/"\n    exclude-paths:\n      - ".env.example"\n',
                    ),
                },
                f"{RUTA_DEPENDABOT}: la lista `exclude-paths` excluye '.env.example'",
            ),
            "un YAML cualquiera de .github": (
                {**self.base(), ".github/labeler.yml": "paths-ignore:\n  - .env.example\n"},
                ".github/labeler.yml",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc18, casos)

    def test_tc18_mutantes_lo_que_no_es_una_exclusion_de_env_pasa(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — control: un `paths-ignore` sin `.env*`, una exclusión comentada, `.environment` o un `run:` que cita el archivo no son hallazgos."""
        validos = {
            "paths-ignore de documentación": self.con_ci(
                sustituir(
                    self.CI_VALIDO,
                    "    branches: [main]\n",
                    "    paths-ignore:\n      - 'docs/**'\n      - '**.md'\n",
                )
            ),
            "exclusión comentada": self.con_ci(
                sustituir(
                    self.CI_VALIDO,
                    "    branches: [main]\n",
                    "    paths-ignore:\n      # - .env.example\n      - 'docs/**'\n",
                )
            ),
            "comentario al final de línea": self.con_ci(
                sustituir(
                    self.CI_VALIDO,
                    "    branches: [main]\n",
                    "    paths-ignore:\n      - 'docs/**'  # no .env.example\n",
                )
            ),
            ".environment no es .env": self.con_ci(
                sustituir(
                    self.CI_VALIDO,
                    "    branches: [main]\n",
                    "    paths-ignore:\n      - '.environment/**'\n",
                )
            ),
            "paths sin negación": self.con_ci(
                sustituir(
                    self.CI_VALIDO, "    branches: [main]\n", "    paths:\n      - '.env.example'\n"
                )
            ),
        }
        for descripcion, archivos in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc18(archivos), [])

    def test_tc18_mutantes_un_workflow_que_lee_secrets_se_detecta(self):
        """RNF-07 · CA-R3 · TC-18 — rechazo: `secrets.X`, `secrets[...]` y `secrets: inherit` en un workflow se detectan y nombran el archivo."""
        casos = {
            "secrets.X en env": (
                self.con_ci(
                    self.CI_VALIDO
                    + "      - run: echo hola\n        env:\n          TOKEN: ${{ secrets.TOKEN }}\n"
                ),
                f"{RUTA_CI}: lee secrets",
            ),
            "secrets.GITHUB_TOKEN": (
                self.con_ci(
                    self.CI_VALIDO
                    + "      - uses: actions/x@abc\n        with:\n          token: ${{ secrets.GITHUB_TOKEN }}\n"
                ),
                f"{RUTA_CI}: lee secrets",
            ),
            "secrets con corchetes": (
                self.con_ci(
                    self.CI_VALIDO
                    + "      - run: echo\n        env:\n          X: ${{ secrets['X'] }}\n"
                ),
                "lee secrets",
            ),
            "secrets: inherit": (
                {
                    **self.base(),
                    ".github/workflows/otro.yml": "jobs:\n  reutiliza:\n    uses: ./.github/workflows/ci.yml\n    secrets: inherit\n",
                },
                ".github/workflows/otro.yml: lee secrets",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc18, casos)

    def test_tc18_mutantes_secrets_comentado_o_fuera_de_los_workflows_no_cuenta(self):
        """RNF-07 · CA-R3 · TC-18 — control: `secrets.` en un comentario, o en un archivo que no es un workflow, no es un hallazgo de este caso."""
        validos = {
            "comentado": self.con_ci(self.CI_VALIDO + "      # TOKEN: ${{ secrets.TOKEN }}\n"),
            "en un comentario al final de línea": self.con_ci(
                self.CI_VALIDO.replace(
                    "cp .env.example .env", "cp .env.example .env  # sin secrets.X"
                )
            ),
            "fuera de workflows": {
                **self.base(),
                ".github/ISSUE_TEMPLATE/error.md": "No pegues secrets.TOKEN aquí\n",
            },
        }
        for descripcion, archivos in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_tc18(archivos), [])


RUTA_REVISION = ".github/workflows/revision-ia.yml"


class PruebasDeMutantesDeTC18ConLaExcepcionDeRevision(unittest.TestCase):
    """TKT-062b · TC62-28 y TC62-29 · CA-7. TC-18 y TC-22 de TKT-009 comparten una sola definición de la excepción de `secrets.`
    (`motivos_de_secretos`); el envoltorio de TC-18 le pasa el nombre base y antepone él mismo la ruta completa."""

    def base(self) -> dict[str, str]:
        return {RUTA_CI: PruebasDeMutantesDeTC18.CI_VALIDO, RUTA_DEPENDABOT: DEPENDABOT_VALIDO}

    def con_revision(self, texto: str) -> dict[str, str]:
        return {**self.base(), RUTA_REVISION: texto}

    def test_tkt062_ca07_esc01_tc18_el_uso_permitido_en_revision_ia_pasa(self):
        """CA-7 esc. 1 · TC62-28 (control) · TC-18 — `revision-ia.yml` con la única lectura permitida no es un hallazgo de TC-18."""
        self.assertEqual(comprobar_sin_secrets_en_flujos(self.con_revision(REVISION_CON_CLAVE)), [])
        self.assertEqual(comprobar_tc18(self.con_revision(REVISION_CON_CLAVE)), [])

    def test_tkt062_ca07_esc02_tc18_el_motivo_lleva_la_ruta_completa_y_empieza_por_lee_secrets(self):
        """CA-7 esc. 2 · TC62-28 · TC-18 — rechazo: el envoltorio antepone `ruta: ` al motivo sin prefijo, así que los mutantes de
        TKT-009 siguen recibiendo `f"{ruta}: lee secrets…"`; un secreto en `ci.yml` da exactamente un problema."""
        con_secreto = PruebasDeMutantesDeTC18.CI_VALIDO + "      - run: echo\n        env:\n          X: ${{ secrets.X }}\n"
        self.assertEqual(
            comprobar_sin_secrets_en_flujos({**self.base(), RUTA_CI: con_secreto}),
            [f"{RUTA_CI}: {MOTIVO_DE_OTRO_FLUJO}"],
        )
        problemas = comprobar_sin_secrets_en_flujos(self.con_revision(sustituir(REVISION_CON_CLAVE, LINEA_DE_LA_CLAVE, "")))
        self.assertEqual(problemas, [f"{RUTA_REVISION}: {MOTIVO_FUERA_DE_LA_EXCEPCION}"])

    def test_tkt062_ca07_esc02_tc18_la_excepcion_se_acota_igual_que_en_tc22(self):
        """CA-7 esc. 2 · TC62-28 · TC-18 — rechazo: la línea permitida movida al `env:`, un segundo secreto, `secrets: inherit` en la revisión,
        o el mismo texto válido bajo otro nombre, dejan TC-18 en rojo con la ruta completa del archivo."""
        en_el_env = sustituir(
            sustituir(REVISION_CON_CLAVE, LINEA_DE_LA_CLAVE, ""),
            LINEA_DEL_PROMPT,
            LINEA_DEL_PROMPT + "        env:\n          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}\n",
        )
        segundo = sustituir(
            REVISION_CON_CLAVE, LINEA_DEL_PROMPT, LINEA_DEL_PROMPT + "        env:\n          OTRA: ${{ secrets.OTRA }}\n"
        )
        con_inherit = sustituir(REVISION_CON_CLAVE, "    timeout-minutes: 10\n", "    timeout-minutes: 10\n    secrets: inherit\n")
        casos = {
            "la línea permitida en el env del paso": (self.con_revision(en_el_env), f"{RUTA_REVISION}: {MOTIVO_FUERA_DE_LA_EXCEPCION}"),
            "un segundo secreto": (self.con_revision(segundo), f"{RUTA_REVISION}: {MOTIVO_FUERA_DE_LA_EXCEPCION}"),
            "secrets: inherit además del uso permitido": (self.con_revision(con_inherit), f"{RUTA_REVISION}: {MOTIVO_FUERA_DE_LA_EXCEPCION}"),
            "el texto válido bajo otro nombre": (
                {**self.base(), ".github/workflows/otro.yml": REVISION_CON_CLAVE},
                f".github/workflows/otro.yml: {MOTIVO_DE_OTRO_FLUJO}",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc18, casos)

    def test_tkt062_ca07_esc03_tc18_la_clave_literal_falla(self):
        """CA-7 esc. 3 · TC62-29 · RNF-07 · TC-18 — rechazo: la clave escrita en `anthropic_api_key:` en lugar del secreto deja TC-18 en rojo."""
        literal = sustituir(REVISION_CON_CLAVE, LINEA_DE_LA_CLAVE, f"          anthropic_api_key: {CLAVE_ANTHROPIC_SINTETICA}\n")
        problemas = comprobar_tc18(self.con_revision(literal))
        self.assertEqual(problemas, [f"{RUTA_REVISION}: {MOTIVO_FUERA_DE_LA_EXCEPCION}"])


class DefinicionSinExcepcionesEnElEscaneo(unittest.TestCase):
    """TC-18 sobre el repositorio real. Nacen en verde por diseño: el invariante ya se cumple; sus mutantes sintéticos, arriba, demuestran que podrían fallar."""

    def test_tc18_no_existe_secret_scanning_yml(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — `.github/` no tiene `secret_scanning.yml`: el diseño no crea ninguna excepción por ruta."""
        self.assertEqual(comprobar_sin_secret_scanning(_leer_github(self)), [])

    def test_tc18_env_example_no_figura_en_ninguna_lista_de_exclusion(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — ningún `paths-ignore` ni otra exclusión de ningún YAML de `.github/` cita `.env.example` ni `.env*`."""
        self.assertEqual(comprobar_sin_exclusion_de_env(_leer_github(self)), [])

    def test_tc18_ningun_workflow_declara_secrets(self):
        """RNF-07 · CA-R3 · TC-18 — ningún workflow de `.github/workflows/` lee `secrets.`."""
        self.assertEqual(comprobar_sin_secrets_en_flujos(_leer_github(self)), [])


ENV_VALIDO = """\
# Plantilla.
CIMENTA_DB_HOST=127.0.0.1
CIMENTA_DB_CONTRASENA_MIGRACION=solo-desarrollo-migracion
# Credenciales de PRUEBA para iniciar sesión a mano. No son un secreto.
CIMENTA_PRUEBA_CORREO=prueba.compras@cimenta.test
CIMENTA_PRUEBA_CONTRASENA=Cimenta-Prueba-2026
# CIMENTA_SESION_TOKEN=comentada-y-real
"""


class PruebasDeMutantesDeEnvExample(unittest.TestCase):
    """`.env.example` no lleva nada que haya que excusar: cada rechazo se prueba sobre texto sintético."""

    def test_tc18_env_mutantes_el_texto_valido_pasa(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — control: valores `solo-desarrollo-*`, credenciales de prueba declaradas y claves sensibles comentadas pasan."""
        self.assertEqual(comprobar_env_example(ENV_VALIDO), [])

    def test_tc18_env_mutantes_una_clave_sensible_con_valor_real_se_detecta(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: una contraseña, un secreto o un token que no sea `solo-desarrollo-*` ni de prueba declarada falla y nombra la clave."""
        casos = {
            "contraseña de base con valor real": (
                sustituir(ENV_VALIDO, "solo-desarrollo-migracion", "Xk3-real-9f"),
                "CIMENTA_DB_CONTRASENA_MIGRACION: una clave sensible solo puede llevar",
            ),
            "clave del almacén de objetos": (
                ENV_VALIDO + "CIMENTA_S3_SECRET_KEY=abcdef123456\n",
                "CIMENTA_S3_SECRET_KEY",
            ),
            "token": (ENV_VALIDO + "CIMENTA_SENTRY_TOKEN=abc123\n", "CIMENTA_SENTRY_TOKEN"),
            "valor entre comillas que no es de desarrollo": (
                ENV_VALIDO + 'CIMENTA_API_KEY="de-verdad"\n',
                "CIMENTA_API_KEY",
            ),
            "prefijo parecido pero distinto": (
                sustituir(ENV_VALIDO, "solo-desarrollo-migracion", "desarrollo-migracion"),
                "CIMENTA_DB_CONTRASENA_MIGRACION",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_env_example, casos)

    def test_tc18_env_mutantes_un_valor_con_forma_de_credencial_real_se_detecta(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: la forma de una credencial de proveedor falla aunque la clave no parezca sensible."""
        casos = {
            "clave de acceso de AWS": (
                ENV_VALIDO + "CIMENTA_S3_ACCESO=" + CLAVE_AWS_SINTETICA + "\n",
                "forma de credencial real",
            ),
            "token de GitHub": (
                ENV_VALIDO + "CIMENTA_OTRO=" + TOKEN_GITHUB_SINTETICO + "\n",
                "forma de credencial real",
            ),
            "clave privada": (
                ENV_VALIDO + "CIMENTA_OTRO=-----BEGIN RSA PRIVATE KEY-----\n",
                "forma de credencial real",
            ),
            "credencial de prueba con forma de token": (
                sustituir(ENV_VALIDO, "Cimenta-Prueba-2026", TOKEN_GITHUB_SINTETICO),
                "CIMENTA_PRUEBA_CONTRASENA: el valor tiene forma de credencial real",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_env_example, casos)

    def test_tc18_env_mutantes_una_credencial_de_prueba_sin_declarar_se_detecta(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — rechazo: las credenciales `CIMENTA_PRUEBA_*` sin ningún comentario que las declare de PRUEBA no pasan."""
        sin_declarar = (
            "\n".join(linea for linea in ENV_VALIDO.splitlines() if "PRUEBA para" not in linea)
            + "\n"
        )
        exigir_rojo(
            self,
            comprobar_env_example,
            sin_declarar,
            "ningún comentario que las declare como de PRUEBA",
        )


class DefinicionDeEnvExample(unittest.TestCase):
    """`.env.example` real. Solo lectura. Nace en verde por diseño: es el estado actual del archivo, que TC-18 protege de aquí en adelante."""

    def test_tc18_env_example_solo_lleva_valores_de_desarrollo_o_de_prueba_declarados(self):
        """RNF-07 · CA-11 esc. 3 · TC-18 — toda clave sensible de `.env.example` vale `solo-desarrollo-*` o es una credencial de prueba declarada, y ningún valor tiene forma de credencial real."""
        if not os.path.isfile(ENV_EXAMPLE):
            self.fail(f"No existe {os.path.relpath(ENV_EXAMPLE, RAIZ)}")
        with open(ENV_EXAMPLE, encoding="utf-8") as archivo:
            self.assertEqual(comprobar_env_example(archivo.read()), [])


if __name__ == "__main__":
    unittest.main()
