"""Pruebas estáticas de `.github/dependabot.yml` y de la ausencia de excepciones en el escaneo de secretos.

TKT-009b · fila B4. Comprueban lo que el repositorio *declara*, no lo que GitHub hace al correr:

* TC-15 (`CA-11` esc. 1): `dependabot.yml` existe, es de la versión 2 y declara exactamente tres entradas
  semanales: `uv` (o `pip`, la sustitución que el diseño permite si GitHub rechaza `uv`) en `/backend`,
  `npm` en `/frontend` y `github-actions` en `/`.
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

from test_definicion_ci import sin_comentarios  # noqa: E402  (la ruta se ajusta arriba)

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
    ("github-actions", ("github-actions",), "/"),
)
INTERVALO = "weekly"


# ---------------------------------------------------------------------------------------------------------
# Lectura de dependabot.yml
# ---------------------------------------------------------------------------------------------------------


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


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
    """`CA-11` esc. 1 · TC-15. Versión 2 y exactamente tres entradas semanales: uv|pip en /backend, npm en /frontend, github-actions en /."""
    problemas: list[str] = []
    if not re.search(r"^version:[ \t]*2[ \t]*$", sin_comentarios(texto), re.MULTILINE):
        problemas.append("dependabot.yml debe declarar `version: 2` en la raíz")
    entradas = entradas_de_updates(texto)
    if len(entradas) != len(ENTRADAS_ESPERADAS):
        problemas.append(
            f"debe declarar exactamente tres entradas en `updates:` y declara {len(entradas)}"
        )
    admitidos = {
        ecosistema for _, ecosistemas, _ in ENTRADAS_ESPERADAS for ecosistema in ecosistemas
    }
    for entrada in entradas:
        ecosistema = escalar_de_entrada(entrada, "package-ecosystem")
        if ecosistema not in admitidos:
            problemas.append(f"ecosistema no previsto en `updates:`: {ecosistema!r}")
    for etiqueta, ecosistemas, directorio in ENTRADAS_ESPERADAS:
        propias = [e for e in entradas if escalar_de_entrada(e, "package-ecosystem") in ecosistemas]
        if not propias:
            problemas.append(
                f"falta la entrada de {etiqueta} ({' o '.join(ecosistemas)}) en `updates:`; una entrada comentada no cuenta"
            )
            continue
        if len(propias) > 1:
            problemas.append(f"hay más de una entrada de {etiqueta}; debe haber exactamente una")
        for entrada in propias:
            real = escalar_de_entrada(entrada, "directory")
            if real != directorio:
                problemas.append(f"{etiqueta}: directory debe ser {directorio!r} y es {real!r}")
            intervalo = intervalo_de_entrada(entrada)
            if intervalo != INTERVALO:
                problemas.append(
                    f"{etiqueta}: schedule.interval debe ser {INTERVALO!r} y es {intervalo!r}"
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
    """`CA-R3` · TC-18. Ningún workflow declara `secrets.`, `secrets[` ni `secrets:`."""
    problemas = []
    for ruta in sorted(archivos):
        if not ruta.startswith(".github/workflows/") or not ruta.endswith((".yml", ".yaml")):
            continue
        if re.search(r"\bsecrets\s*(?:\.|\[|:)", sin_comentarios(archivos[ruta])):
            problemas.append(f"{ruta}: lee secrets; el pipeline no lee secretos (CA-R3)")
    return problemas


def comprobar_tc18(archivos: dict[str, str]) -> list[str]:
    """`CA-11` esc. 3 y `CA-R3` · TC-18: las tres comprobaciones sobre los archivos de `.github/` (ruta relativa a la raíz -> texto)."""
    return (
        comprobar_sin_secret_scanning(archivos)
        + comprobar_sin_exclusion_de_env(archivos)
        + comprobar_sin_secrets_en_flujos(archivos)
    )


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
ENTRADA_ACTIONS = """\
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
"""
CABECERA = "# Actualizaciones semanales de dependencias.\nversion: 2\nupdates:\n"
DEPENDABOT_VALIDO = CABECERA + ENTRADA_UV + ENTRADA_NPM + ENTRADA_ACTIONS


def sustituir(texto: str, viejo: str, nuevo: str) -> str:
    """Cambia `viejo` por `nuevo` exactamente una vez, o falla: un mutante que no cambia nada daría un verde engañoso."""
    if texto.count(viejo) != 1:
        raise AssertionError(
            f"el mutante no es aplicable: {viejo!r} aparece {texto.count(viejo)} veces"
        )
    return texto.replace(viejo, nuevo)


def comentada(entrada: str) -> str:
    return "".join("  # " + linea.strip() + "\n" for linea in entrada.splitlines() if linea.strip())


def exigir_rojo(caso: unittest.TestCase, comprobacion, entrada, fragmento: str) -> list[str]:
    """El mutante debe poner `comprobacion` en rojo y por la razón esperada: algún problema contiene `fragmento`."""
    problemas = comprobacion(entrada)
    caso.assertNotEqual(
        problemas, [], "el mutante debía poner la comprobación en rojo y pasó en verde"
    )
    caso.assertTrue(
        any(fragmento in problema for problema in problemas),
        f"el rojo no es por la razón esperada: ningún problema menciona {fragmento!r}: {problemas}",
    )
    return problemas


def exigir_rojo_en_todos(caso: unittest.TestCase, comprobacion, casos: dict[str, tuple]) -> None:
    for descripcion, (entrada, fragmento) in casos.items():
        with caso.subTest(mutante=descripcion):
            exigir_rojo(caso, comprobacion, entrada, fragmento)


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
            "otro orden de entradas": CABECERA + ENTRADA_ACTIONS + ENTRADA_NPM + ENTRADA_UV,
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
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: sin la entrada de cualquiera de los tres ecosistemas, el caso falla y nombra cuál falta."""
        casos = {
            "sin uv ni pip": (DEPENDABOT_VALIDO.replace(ENTRADA_UV, ""), "falta la entrada de uv"),
            "sin npm": (DEPENDABOT_VALIDO.replace(ENTRADA_NPM, ""), "falta la entrada de npm"),
            "sin github-actions": (
                DEPENDABOT_VALIDO.replace(ENTRADA_ACTIONS, ""),
                "falta la entrada de github-actions",
            ),
            "sin updates": (CABECERA, "falta la entrada de uv"),
            "ecosistema de otro lenguaje en lugar de npm": (
                sustituir(
                    DEPENDABOT_VALIDO, 'package-ecosystem: "npm"', 'package-ecosystem: "bundler"'
                ),
                "falta la entrada de npm",
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
                "falta la entrada de npm",
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
                    DEPENDABOT_VALIDO.replace(ENTRADA_NPM, "").replace(ENTRADA_ACTIONS, ""),
                    'interval: "weekly"',
                    'interval: "daily"',
                ),
                "uv: schedule.interval debe ser 'weekly' y es 'daily'",
            ),
            "npm mensual": (
                DEPENDABOT_VALIDO.replace(ENTRADA_NPM, ENTRADA_NPM.replace("weekly", "monthly")),
                "npm: schedule.interval debe ser 'weekly' y es 'monthly'",
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
        """RNF-08 · CA-11 esc. 1 · TC-15 — rechazo: versión distinta de 2 o ausente, una cuarta entrada y una entrada repetida."""
        casos = {
            "version 1": (sustituir(DEPENDABOT_VALIDO, "version: 2", "version: 1"), "`version: 2`"),
            "version entre comillas": (
                sustituir(DEPENDABOT_VALIDO, "version: 2", 'version: "2"'),
                "`version: 2`",
            ),
            "sin version": (sustituir(DEPENDABOT_VALIDO, "version: 2\n", ""), "`version: 2`"),
            "una cuarta entrada": (
                DEPENDABOT_VALIDO
                + '  - package-ecosystem: "docker"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n',
                "exactamente tres entradas",
            ),
            "npm repetida": (DEPENDABOT_VALIDO + ENTRADA_NPM, "más de una entrada de npm"),
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
                self.assertTrue(any("exactamente tres entradas" in p for p in problemas), problemas)


class DefinicionDeDependabot(unittest.TestCase):
    """Fila B4 sobre `.github/dependabot.yml`. Sin el archivo, falla; no se salta."""

    def test_tc15_dependabot_declara_uv_npm_y_github_actions_semanales(self):
        """RNF-08 · CA-11 esc. 1 · TC-15 — versión 2 y tres entradas semanales: uv (o pip) en /backend, npm en /frontend y github-actions en /."""
        self.assertEqual(comprobar_tc15(_leer_dependabot(self)), [])


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
                ENV_VALIDO + "CIMENTA_S3_ACCESO=AKIAABCDEFGHIJKLMNOP\n",
                "forma de credencial real",
            ),
            "token de GitHub": (
                ENV_VALIDO + "CIMENTA_OTRO=ghp_abcdefghijklmnopqrstuvwxyz0123456789\n",
                "forma de credencial real",
            ),
            "clave privada": (
                ENV_VALIDO + "CIMENTA_OTRO=-----BEGIN RSA PRIVATE KEY-----\n",
                "forma de credencial real",
            ),
            "credencial de prueba con forma de token": (
                sustituir(
                    ENV_VALIDO, "Cimenta-Prueba-2026", "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
                ),
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
