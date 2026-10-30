"""Pruebas estáticas del flujo de la etiqueta de origen, `.github/workflows/etiqueta-origen.yml`.

TKT-062a · fila A3. Comprueban lo que el flujo *declara*, no lo que hace al correr (lo que hace el guion lo cubre
`test_etiqueta_origen.py`, y el ensayo en un PR real, la fila A6). Mismo método que `test_definicion_ci.py`, de donde se
importan los ayudantes: `tools/` no tiene dependencias y la biblioteca estándar no trae un analizador de YAML, así que el
texto se lee con expresiones regulares, se ignoran las líneas comentadas y cada caso busca dentro del bloque de su trabajo.
Cada comprobación vive en una función `comprobar_*` que devuelve la lista de problemas, y las pruebas sobre texto
sintético demuestran que se pone en rojo ante cada mutante y por la razón esperada (cada mutante exige un fragmento del
mensaje, no solo que la lista no esté vacía).

Qué cubren:

* TC62-06 (`CA-6` esc. 4): `etiqueta-origen.yml` se dispara con `pull_request` y exactamente `opened`, `reopened`,
  `synchronize`, `labeled` y `unlabeled`; `permissions` es solo `contents: read`; el trabajo `etiqueta` se llama
  «Etiqueta de origen» (es el contexto que exige la protección de `Produccion`: cambiarlo la rompe en silencio), no tiene
  `if:`, corre en `ubuntu-24.04` con `timeout-minutes: 5`, hace el checkout por SHA con `persist-credentials: false`, y su
  paso ejecuta `python3 tools/etiqueta_origen.py` con `ETIQUETAS` por `env:` desde
  `toJSON(github.event.pull_request.labels.*.name)`. Ningún `secrets.`.
* TC62-07 (`CA-6` esc. 4, rechazo): el `pull_request` de `ci.yml` no declara `labeled`, `unlabeled` ni `edited`; etiquetar
  relanzaría los nueve trabajos. Como `ci.yml` ya cumple eso, el caso exige además que exista el flujo que sí recibe el
  `labeled`, y por eso nace en rojo.
* TC62-R1 (`CA-R1`): TC-13 de TKT-009 y las reglas comunes siguen en verde con `etiqueta-origen.yml` presente.
* TC62-38 (`CA-12` esc. 1, fila A7): la documentación de 062a describe la etiqueta de origen. Lee los archivos reales, no texto
  sintético, y comprueba la presencia de términos clave (sin tildes, sin mayúsculas, sin comillas invertidas ni negritas, con los
  espacios colapsados), no un texto literal: convenciones §6 y §11, `CLAUDE.md`, `tools/README.md`, stack «Integración continua»,
  `sdd/plantillas/delta.md`, la skill `sdd-completar`, el agente `git-entrega` y `sdd/00-propuesta-toolkit.md`. Un subtest por archivo,
  y cada fallo dice qué frase falta.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_definicion_etiqueta -v
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
import unittest

DIRECTORIO_DE_PRUEBAS = os.path.dirname(os.path.abspath(__file__))
if DIRECTORIO_DE_PRUEBAS not in sys.path:
    sys.path.insert(0, DIRECTORIO_DE_PRUEBAS)

from _ayudantes import exigir_rojo_en_todos, sustituir  # noqa: E402
from test_definicion_ci import (  # noqa: E402
    CI_A4,
    DIRECTORIO_DE_FLUJOS,
    ENLACES_SINTETICO,
    ETIQUETA_SINTETICA,
    RAIZ,
    SIN_CREDENCIALES,
    _disparadores,
    _indice_de_uses,
    _leer_flujos,
    _normalizada,
    _permisos_de_flujo,
    comando,
    comprobar_regla_comun_1,
    comprobar_reglas_comunes_de_todo_flujo,
    comprobar_tc12,
    comprobar_tc13,
    comprobar_tc21,
    comprobar_tc22,
    extraer_trabajos,
    mutar,
    pasos,
    sin_comentarios,
    valor_del_paso,
    valor_del_trabajo,
)

ETIQUETA_ORIGEN = os.path.join(DIRECTORIO_DE_FLUJOS, "etiqueta-origen.yml")

NOMBRE_DEL_TRABAJO = "Etiqueta de origen"
TIPOS_DEL_DISPARADOR = ("opened", "reopened", "synchronize", "labeled", "unlabeled")
TIPOS_QUE_RELANZARIAN_CI = ("labeled", "unlabeled", "edited")
ORDEN_DEL_PASO = "python3 tools/etiqueta_origen.py"
EXPRESION_DE_ETIQUETAS = "${{ toJSON(github.event.pull_request.labels.*.name) }}"
CHECKOUT_POR_SHA = re.compile(r"actions/checkout@[0-9a-f]{40}")
HAY_PULL_REQUEST = re.compile(r"(?<![\w-])pull_request(?![\w-])")
HAY_PULL_REQUEST_TARGET = re.compile(r"(?<![\w-])pull_request_target(?![\w-])")
LEE_SECRETOS = re.compile(r"\bsecrets\s*[.\[:]")


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones: cada una devuelve la lista de problemas, vacía si el caso se cumple
# ---------------------------------------------------------------------------------------------------------


def _tipos_de_pull_request(disparadores: str) -> list[str] | None:
    """Los `types:` del disparador `pull_request` (en lista de flujo `[a, b]` o en lista de bloque), o None si no declara `types:`.

    Solo mira el sub-bloque de `pull_request`: desde su línea hasta la siguiente clave del mismo nivel de sangría o menor. Un
    `types:` bajo otro disparador (`schedule`, `workflow_dispatch`...) no cuenta, ni cuando va antes ni cuando va después."""
    lineas = disparadores.splitlines()
    inicio = next((k for k, linea in enumerate(lineas) if re.match(r"^\s*pull_request\s*:", linea)), None)
    if inicio is None:
        return None
    sangria = len(lineas[inicio]) - len(lineas[inicio].lstrip())
    bloque: list[str] = []
    for linea in lineas[inicio + 1 :]:
        if linea.strip() and len(linea) - len(linea.lstrip()) <= sangria:
            break  # la siguiente clave del mismo nivel: termina el sub-bloque de `pull_request`
        bloque.append(linea)
    for k, linea in enumerate(bloque):
        encontrada = re.match(r"^(\s*)types:\s*(.*)$", linea)
        if not encontrada:
            continue
        resto = encontrada.group(2).strip()
        if resto.startswith("["):
            return [t.strip().strip("\"'") for t in resto.strip("[]").split(",") if t.strip()]
        elementos = []
        for siguiente in bloque[k + 1 :]:
            elemento = re.match(r"^\s*-\s+(.*)$", siguiente)
            if not elemento:
                break
            elementos.append(elemento.group(1).strip().strip("\"'"))
        return elementos
    return None


def comprobar_flujo_de_etiqueta(texto: str) -> list[str]:
    """TC62-06 · CA-6 esc. 4. El flujo de la etiqueta de origen, según el diseño de TKT-062a."""
    problemas: list[str] = []
    disparadores = _disparadores(texto)
    if not HAY_PULL_REQUEST.search(disparadores):
        problemas.append("el disparador debe ser `pull_request`")
    if HAY_PULL_REQUEST_TARGET.search(disparadores):
        problemas.append("usa pull_request_target, que corre con secretos sobre código de una bifurcación")
    tipos = _tipos_de_pull_request(disparadores)
    if tipos is None:
        problemas.append(
            "`pull_request` no declara `types:`; sin ellos no se relanza al etiquetar ni al quitar una etiqueta"
        )
    elif sorted(tipos) != sorted(TIPOS_DEL_DISPARADOR):
        problemas.append(
            f"`types:` debe ser exactamente {', '.join(TIPOS_DEL_DISPARADOR)} y es {', '.join(tipos) or '(vacío)'}"
        )
    permisos = _permisos_de_flujo(texto)
    if permisos != ["contents: read"]:
        problemas.append(f"`permissions:` a nivel de flujo debe ser solo `contents: read` y es {permisos!r}")
    if LEE_SECRETOS.search(sin_comentarios(texto)):
        problemas.append("lee secrets.*; el flujo de la etiqueta no lee ningún secreto")

    trabajos = extraer_trabajos(texto)
    if "etiqueta" not in trabajos:
        return problemas + ["no declara el trabajo `etiqueta`"]
    bloque = trabajos["etiqueta"]
    nombre = (valor_del_trabajo(bloque, "name") or "").strip("\"'")
    if nombre != NOMBRE_DEL_TRABAJO:
        problemas.append(
            f"el `name:` del trabajo debe ser «{NOMBRE_DEL_TRABAJO}» (es el contexto que exige la protección de rama) y es {nombre!r}"
        )
    if valor_del_trabajo(bloque, "if") is not None:
        problemas.append("el trabajo `etiqueta` no puede llevar `if:` a nivel de trabajo: se saltaría la comprobación requerida")
    problemas += comprobar_regla_comun_1({"etiqueta": bloque})

    lista = pasos(bloque)
    i_checkout = _indice_de_uses(lista, "actions/checkout@")
    if i_checkout is None:
        problemas.append("falta actions/checkout")
    else:
        paso = lista[i_checkout]
        if not CHECKOUT_POR_SHA.fullmatch(valor_del_paso(paso, "uses") or ""):
            problemas.append("actions/checkout debe fijarse por el SHA de 40 caracteres de su commit")
        if not SIN_CREDENCIALES.search(valor_del_paso(paso, "with") or ""):
            problemas.append("actions/checkout debe llevar `persist-credentials: false`")
    i_guion = next((i for i, paso in enumerate(lista) if comando(paso).strip() == ORDEN_DEL_PASO), None)
    if i_guion is None:
        problemas.append(f"falta el paso que ejecuta `{ORDEN_DEL_PASO}` (y solo eso)")
    else:
        if i_checkout is not None and i_checkout > i_guion:
            problemas.append("el checkout debe ir antes del paso que ejecuta el guion")
        asignaciones = [
            m.group(1)
            for linea in (valor_del_paso(lista[i_guion], "env") or "").splitlines()
            if (m := re.fullmatch(r"ETIQUETAS:\s*(.*)", linea.strip()))
        ]
        if len(asignaciones) != 1:
            problemas.append(f"el paso del guion debe declarar `ETIQUETAS` en `env:` exactamente una vez y la declara {len(asignaciones)}")
        elif _normalizada(asignaciones[0]) != _normalizada(EXPRESION_DE_ETIQUETAS):
            problemas.append(
                f"`ETIQUETAS` debe valer `{EXPRESION_DE_ETIQUETAS}` y vale `{asignaciones[0]}`"
            )
    return problemas


def comprobar_ci_no_se_relanza_al_etiquetar(texto_de_ci: str) -> list[str]:
    """TC62-07 · CA-6 esc. 4 (rechazo). El `pull_request` de `ci.yml` no declara `types:` o no incluye `labeled`, `unlabeled` ni `edited`."""
    tipos = _tipos_de_pull_request(_disparadores(texto_de_ci))
    if tipos is None:
        return []
    ajenos = [t for t in tipos if t in TIPOS_QUE_RELANZARIAN_CI]
    if ajenos:
        return [
            f"ci.yml: `pull_request` declara `types:` con {', '.join(ajenos)}; etiquetar o editar relanzaría los nueve trabajos del pipeline"
        ]
    return []


# ---------------------------------------------------------------------------------------------------------
# Mutantes sobre texto sintético
# ---------------------------------------------------------------------------------------------------------

CI_QUE_SE_RELANZA_AL_ETIQUETAR = "name: CI\n\non:\n  pull_request:\n    types: [opened, synchronize, reopened]\n\npermissions:\n  contents: read\n"


class PruebasDeMutantesDelFlujoDeEtiqueta(unittest.TestCase):
    """TC62-06 y TC62-07: cada propiedad que fija el diseño se pone en rojo cuando se estropea, y por la razón esperada."""

    def test_tkt062_ca06_esc04_mutantes_el_control_valido_pasa(self):
        """CA-6 esc. 4 · TC62-06 (control) — sin esto, un mutante «en rojo» podría estarlo por culpa del texto base."""
        self.assertEqual(comprobar_flujo_de_etiqueta(ETIQUETA_SINTETICA), [])

    def test_tkt062_ca06_esc04_mutantes_types_en_lista_de_bloque_tambien_vale(self):
        """CA-6 esc. 4 · TC62-06 — los cinco `types:` escritos como lista de bloque, en otro orden, son los mismos cinco."""
        en_bloque = sustituir(
            ETIQUETA_SINTETICA,
            "    types: [opened, reopened, synchronize, labeled, unlabeled]\n",
            "    types:\n      - unlabeled\n      - labeled\n      - synchronize\n      - reopened\n      - opened\n",
        )
        self.assertEqual(comprobar_flujo_de_etiqueta(en_bloque), [])

    def test_tkt062_ca06_esc04_mutantes_el_disparador_se_relanza_al_etiquetar(self):
        """CA-6 esc. 4 · TC62-06 — quitar `synchronize` (el PR esperaría para siempre), `labeled`, `unlabeled`, `opened` o `reopened`,
        añadir `edited`, no declarar `types:` o disparar con `pull_request_target` es rojo."""
        tipos = "    types: [opened, reopened, synchronize, labeled, unlabeled]\n"

        def con_tipos(nuevos: str) -> str:
            return sustituir(ETIQUETA_SINTETICA, tipos, f"    types: [{nuevos}]\n")

        casos = {
            "sin synchronize": (con_tipos("opened, reopened, labeled, unlabeled"), "`types:` debe ser exactamente"),
            "sin labeled": (con_tipos("opened, reopened, synchronize, unlabeled"), "`types:` debe ser exactamente"),
            "sin unlabeled": (con_tipos("opened, reopened, synchronize, labeled"), "`types:` debe ser exactamente"),
            "sin opened": (con_tipos("reopened, synchronize, labeled, unlabeled"), "`types:` debe ser exactamente"),
            "sin reopened": (con_tipos("opened, synchronize, labeled, unlabeled"), "`types:` debe ser exactamente"),
            "con edited de más": (
                con_tipos("opened, reopened, synchronize, labeled, unlabeled, edited"),
                "`types:` debe ser exactamente",
            ),
            "sin types": (sustituir(ETIQUETA_SINTETICA, tipos, ""), "no declara `types:`"),
            "pull_request_target": (
                sustituir(ETIQUETA_SINTETICA, "  pull_request:\n", "  pull_request_target:\n"),
                "pull_request_target",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_types_bajo_otro_disparador_no_cuenta(self):
        """CA-6 esc. 4 · TC62-06 — `types:` bajo `schedule` o `workflow_dispatch`, con `pull_request` sin `types:`, es rojo: los cinco tipos
        tienen que estar en el sub-bloque de `pull_request`, no en cualquier parte del `on:`."""
        con_pull_request = "  pull_request:\n    types: [opened, reopened, synchronize, labeled, unlabeled]\n"
        ajenos = "    types: [opened, reopened, synchronize, labeled, unlabeled]\n"
        casos = {
            "types bajo workflow_dispatch, después de pull_request": sustituir(
                ETIQUETA_SINTETICA, con_pull_request, "  pull_request:\n  workflow_dispatch:\n" + ajenos
            ),
            "types bajo schedule, antes de pull_request": sustituir(
                ETIQUETA_SINTETICA, con_pull_request, "  schedule:\n" + ajenos + "  pull_request:\n"
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos, "no declara `types:`")

    def test_tkt062_ca06_esc04_mutantes_types_de_otro_disparador_no_estorba(self):
        """CA-6 esc. 4 · TC62-06 (control) — un `types:` ajeno antes o después de `pull_request` no se confunde con el suyo: el flujo válido sigue pasando."""
        con_pull_request = "  pull_request:\n    types: [opened, reopened, synchronize, labeled, unlabeled]\n"
        casos = {
            "types ajenos antes": sustituir(
                ETIQUETA_SINTETICA, con_pull_request, "  workflow_dispatch:\n    types: [edited]\n" + con_pull_request
            ),
            "types ajenos después": sustituir(
                ETIQUETA_SINTETICA, con_pull_request, con_pull_request + "  schedule:\n    types: [edited]\n"
            ),
        }
        for descripcion, texto in casos.items():
            with self.subTest(control=descripcion):
                self.assertEqual(comprobar_flujo_de_etiqueta(texto), [])

    def test_tkt062_ca06_esc04_mutantes_los_permisos_son_solo_contents_read(self):
        """CA-6 esc. 4 · TC62-06 — sin `permissions:`, con `contents: write` o con `pull-requests: write` de más es rojo."""
        casos = {
            "sin permissions": (sustituir(ETIQUETA_SINTETICA, "permissions:\n  contents: read\n", ""), "`permissions:` a nivel de flujo"),
            "contents: write": (sustituir(ETIQUETA_SINTETICA, "contents: read", "contents: write"), "`permissions:` a nivel de flujo"),
            "pull-requests: write de más": (
                sustituir(ETIQUETA_SINTETICA, "  contents: read\n", "  contents: read\n  pull-requests: write\n"),
                "`permissions:` a nivel de flujo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_el_nombre_del_trabajo_es_el_contexto_de_la_proteccion(self):
        """CA-6 esc. 4 · TC62-06 — cambiar el `name:` del trabajo, o su id, rompe la protección en silencio, y la prueba lo ve."""
        casos = {
            "otro nombre": (
                mutar(ETIQUETA_SINTETICA, "etiqueta", "    name: Etiqueta de origen\n", "    name: Verificar etiqueta\n"),
                "el `name:` del trabajo debe ser «Etiqueta de origen»",
            ),
            "minúsculas": (
                mutar(ETIQUETA_SINTETICA, "etiqueta", "    name: Etiqueta de origen\n", "    name: etiqueta de origen\n"),
                "el `name:` del trabajo debe ser «Etiqueta de origen»",
            ),
            "sin name": (
                mutar(ETIQUETA_SINTETICA, "etiqueta", "    name: Etiqueta de origen\n", ""),
                "el `name:` del trabajo debe ser «Etiqueta de origen»",
            ),
            "otro id de trabajo": (
                sustituir(ETIQUETA_SINTETICA, "\n  etiqueta:\n", "\n  verificar:\n"),
                "no declara el trabajo `etiqueta`",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_el_trabajo_no_se_puede_saltar_ni_cambiar_de_corredor_o_de_tiempo(self):
        """CA-6 esc. 4 · TC62-06 — un `if:` a nivel de trabajo, otro corredor o un tiempo distinto de 5 minutos es rojo."""
        casos = {
            "if a nivel de trabajo": (
                mutar(
                    ETIQUETA_SINTETICA,
                    "etiqueta",
                    "    timeout-minutes: 5\n",
                    "    timeout-minutes: 5\n    if: github.event.action != 'unlabeled'\n",
                ),
                "no puede llevar `if:` a nivel de trabajo",
            ),
            "otro corredor": (
                sustituir(ETIQUETA_SINTETICA, "runs-on: ubuntu-24.04", "runs-on: ubuntu-latest"),
                "runs-on debe ser ubuntu-24.04",
            ),
            "diez minutos": (
                sustituir(ETIQUETA_SINTETICA, "timeout-minutes: 5", "timeout-minutes: 10"),
                "timeout-minutes debe ser 5",
            ),
            "sin timeout": (
                sustituir(ETIQUETA_SINTETICA, "    timeout-minutes: 5\n", ""),
                "timeout-minutes debe ser 5",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_el_checkout_va_por_sha_y_sin_credenciales(self):
        """CA-6 esc. 4 · TC62-06 — un checkout por etiqueta de versión, sin `persist-credentials: false`, o después del guion es rojo."""
        paso_checkout = (
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "        with:\n          persist-credentials: false\n"
        )
        paso_del_guion = (
            "      - name: Exactamente una etiqueta de origen\n"
            "        env:\n          ETIQUETAS: ${{ toJSON(github.event.pull_request.labels.*.name) }}\n"
            "        run: python3 tools/etiqueta_origen.py\n"
        )
        casos = {
            "checkout por etiqueta de versión": (
                sustituir(ETIQUETA_SINTETICA, "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "actions/checkout@v7"),
                "debe fijarse por el SHA",
            ),
            "persist-credentials: true": (
                sustituir(ETIQUETA_SINTETICA, "persist-credentials: false", "persist-credentials: true"),
                "persist-credentials: false",
            ),
            "sin persist-credentials": (
                sustituir(ETIQUETA_SINTETICA, "        with:\n          persist-credentials: false\n", ""),
                "persist-credentials: false",
            ),
            "sin checkout": (sustituir(ETIQUETA_SINTETICA, paso_checkout, ""), "falta actions/checkout"),
            "checkout después del guion": (
                sustituir(ETIQUETA_SINTETICA, paso_checkout + paso_del_guion, paso_del_guion + paso_checkout),
                "el checkout debe ir antes",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_el_guion_recibe_las_etiquetas_por_env(self):
        """CA-6 esc. 4 · TC62-06 — sin `env:`, con otra expresión, con la interpolación dentro de `run:` o con otro guion es rojo."""
        env = "        env:\n          ETIQUETAS: ${{ toJSON(github.event.pull_request.labels.*.name) }}\n"
        casos = {
            "sin env": (sustituir(ETIQUETA_SINTETICA, env, ""), "`ETIQUETAS` en `env:` exactamente una vez y la declara 0"),
            "ETIQUETAS declarada dos veces": (
                sustituir(ETIQUETA_SINTETICA, env, env + "          ETIQUETAS: ${{ toJSON(github.event.pull_request.labels.*.name) }}\n"),
                "exactamente una vez y la declara 2",
            ),
            "etiquetas sin .*.name": (
                sustituir(ETIQUETA_SINTETICA, "labels.*.name", "labels"),
                "`ETIQUETAS` debe valer",
            ),
            "sin toJSON": (
                sustituir(ETIQUETA_SINTETICA, "toJSON(github.event.pull_request.labels.*.name)", "join(github.event.pull_request.labels.*.name, ',')"),
                "`ETIQUETAS` debe valer",
            ),
            "variable con otro nombre": (
                sustituir(ETIQUETA_SINTETICA, "          ETIQUETAS:", "          LABELS:"),
                "`ETIQUETAS` en `env:` exactamente una vez y la declara 0",
            ),
            "otro guion": (
                sustituir(ETIQUETA_SINTETICA, "run: python3 tools/etiqueta_origen.py\n", "run: python3 tools/otra_cosa.py\n"),
                "falta el paso que ejecuta `python3 tools/etiqueta_origen.py`",
            ),
            "guion con argumentos": (
                sustituir(ETIQUETA_SINTETICA, "run: python3 tools/etiqueta_origen.py\n", "run: python3 tools/etiqueta_origen.py --sin-falla\n"),
                "falta el paso que ejecuta `python3 tools/etiqueta_origen.py`",
            ),
            "sin el paso del guion": (
                sustituir(ETIQUETA_SINTETICA, "        run: python3 tools/etiqueta_origen.py\n", "        run: echo hecho\n"),
                "falta el paso que ejecuta",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    def test_tkt062_ca06_esc04_mutantes_el_flujo_no_lee_secretos(self):
        """CA-6 esc. 4 · TC62-06 · TC-22 de TKT-009 — ni `secrets.GITHUB_TOKEN` en el `env:`: el flujo de la etiqueta no lee ningún secreto."""
        casos = {
            "secrets.GITHUB_TOKEN en el env": sustituir(
                ETIQUETA_SINTETICA,
                "        env:\n",
                "        env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n",
            ),
            "secrets: inherit": ETIQUETA_SINTETICA + "    secrets: inherit\n",
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos, "lee secrets")

    def test_tkt062_ca06_esc04_mutantes_un_comentario_no_cuenta_como_la_propiedad(self):
        """CA-6 esc. 4 · TC62-06 — `synchronize` solo en un comentario, o el paso del guion comentado, no cumplen el caso."""
        casos = {
            "synchronize en un comentario": (
                sustituir(
                    ETIQUETA_SINTETICA,
                    "    types: [opened, reopened, synchronize, labeled, unlabeled]\n",
                    "    # synchronize\n    types: [opened, reopened, labeled, unlabeled]\n",
                ),
                "`types:` debe ser exactamente",
            ),
            "paso del guion comentado": (
                sustituir(
                    ETIQUETA_SINTETICA,
                    "        run: python3 tools/etiqueta_origen.py\n",
                    "        run: echo hecho\n        # run: python3 tools/etiqueta_origen.py\n",
                ),
                "falta el paso que ejecuta",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_flujo_de_etiqueta, casos)

    # --- TC62-07 -------------------------------------------------------------------------------------------

    def test_tkt062_ca06_esc04_mutantes_ci_no_se_relanza_al_etiquetar_el_control_pasa(self):
        """CA-6 esc. 4 · TC62-07 (control) — `ci.yml` sin `types:` y con `opened, synchronize, reopened` no se relanza al etiquetar."""
        self.assertEqual(comprobar_ci_no_se_relanza_al_etiquetar("name: CI\n\non:\n  pull_request:\n\npermissions:\n  contents: read\n"), [])
        self.assertEqual(comprobar_ci_no_se_relanza_al_etiquetar(CI_QUE_SE_RELANZA_AL_ETIQUETAR), [])

    def test_tkt062_ca06_esc04_mutantes_etiquetar_relanzaria_ci(self):
        """CA-6 esc. 4 · TC62-07 (rechazo) — añadir `labeled`, `unlabeled` o `edited` al `pull_request` de `ci.yml`, en lista de flujo o de bloque, es rojo."""
        casos = {
            "labeled": (
                sustituir(CI_QUE_SE_RELANZA_AL_ETIQUETAR, "[opened, synchronize, reopened]", "[opened, synchronize, reopened, labeled]"),
                "labeled",
            ),
            "unlabeled": (
                sustituir(CI_QUE_SE_RELANZA_AL_ETIQUETAR, "[opened, synchronize, reopened]", "[opened, synchronize, reopened, unlabeled]"),
                "unlabeled",
            ),
            "edited": (
                sustituir(CI_QUE_SE_RELANZA_AL_ETIQUETAR, "[opened, synchronize, reopened]", "[edited, opened]"),
                "edited",
            ),
            "labeled y unlabeled en lista de bloque": (
                sustituir(
                    CI_QUE_SE_RELANZA_AL_ETIQUETAR,
                    "    types: [opened, synchronize, reopened]\n",
                    "    types:\n      - opened\n      - labeled\n      - unlabeled\n",
                ),
                "labeled, unlabeled",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_ci_no_se_relanza_al_etiquetar, casos, "etiquetar o editar relanzaría")

    def test_tkt062_ca06_esc04_mutantes_types_de_otro_disparador_no_relanzan_ci(self):
        """CA-6 esc. 4 · TC62-07 — `labeled` en un `types:` de otro disparador de `ci.yml` no es del `pull_request`: no es un falso rojo."""
        casos = {
            "pull_request sin types y types ajenos después": "name: CI\n\non:\n  pull_request:\n  workflow_dispatch:\n    types: [labeled]\n\npermissions:\n  contents: read\n",
            "types ajenos antes de pull_request sin types": "name: CI\n\non:\n  schedule:\n    types: [unlabeled, edited]\n  pull_request:\n\npermissions:\n  contents: read\n",
            "pull_request con types ok y types ajenos después": CI_QUE_SE_RELANZA_AL_ETIQUETAR.replace(
                "\npermissions:", "  schedule:\n    types: [labeled]\n\npermissions:"
            ),
        }
        for descripcion, texto in casos.items():
            with self.subTest(control=descripcion):
                self.assertEqual(comprobar_ci_no_se_relanza_al_etiquetar(texto), [])

    def test_tkt062_ca06_esc04_mutantes_un_comentario_no_cuenta_como_un_type_de_ci(self):
        """CA-6 esc. 4 · TC62-07 — `labeled` solo en un comentario no relanza `ci.yml`: no es un falso rojo."""
        con_comentario = sustituir(
            CI_QUE_SE_RELANZA_AL_ETIQUETAR, "    types: [opened, synchronize, reopened]\n", "    # sin labeled\n    types: [opened, synchronize, reopened]\n"
        )
        self.assertEqual(comprobar_ci_no_se_relanza_al_etiquetar(con_comentario), [])

    # --- TC62-R1 -------------------------------------------------------------------------------------------

    def test_tkt062_car1_esc01_mutantes_tc13_ve_los_flujos_nuevos(self):
        """CA-R1 · TC62-R1 (rechazo) — TC-13 de TKT-009 es rojo si `etiqueta-origen.yml` usa `workflow_run` o espera un trabajo ajeno,
        o si `ci.yml` pasa a esperar el trabajo `etiqueta`, que vive en otro archivo."""
        flujos = {"ci.yml": CI_A4, "enlaces.yml": ENLACES_SINTETICO, "etiqueta-origen.yml": ETIQUETA_SINTETICA}
        self.assertEqual(comprobar_tc13(flujos), [], "control: los flujos sintéticos válidos pasan TC-13")
        casos = {
            "workflow_run en etiqueta-origen.yml": (
                {**flujos, "etiqueta-origen.yml": sustituir(ETIQUETA_SINTETICA, "on:\n  pull_request:\n", "on:\n  workflow_run:\n    workflows: [CI]\n  pull_request:\n")},
                "etiqueta-origen.yml: usa el disparador workflow_run",
            ),
            "needs ajeno en etiqueta-origen.yml": (
                {**flujos, "etiqueta-origen.yml": sustituir(ETIQUETA_SINTETICA, "    runs-on: ubuntu-24.04\n", "    needs: backend\n    runs-on: ubuntu-24.04\n")},
                "etiqueta-origen.yml: 'etiqueta' necesita 'backend', que no es un trabajo de este archivo",
            ),
            "ci.yml espera al trabajo etiqueta": (
                {**flujos, "ci.yml": mutar(CI_A4, "documentacion", "    runs-on: ubuntu-24.04\n", "    needs: etiqueta\n    runs-on: ubuntu-24.04\n")},
                "ci.yml: 'documentacion' necesita 'etiqueta', que no es un trabajo de este archivo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc13, casos)


# ---------------------------------------------------------------------------------------------------------
# Los casos sobre el archivo real
# ---------------------------------------------------------------------------------------------------------


def _texto_de_etiqueta(caso: unittest.TestCase) -> str:
    """El texto de `etiqueta-origen.yml`. Sin el archivo el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(ETIQUETA_ORIGEN):
        caso.fail(f"No existe {os.path.relpath(ETIQUETA_ORIGEN, RAIZ)}: el flujo de la etiqueta de origen de TKT-062a todavía no está definido")
    with open(ETIQUETA_ORIGEN, encoding="utf-8") as archivo:
        return archivo.read()


class DefinicionDelFlujoDeEtiqueta(unittest.TestCase):
    """Casos estáticos de la fila A3 sobre `.github/workflows/etiqueta-origen.yml` y `ci.yml`. Sin el archivo, fallan; no se saltan."""

    def test_tkt062_ca06_esc04_el_flujo_de_etiqueta_se_relanza_al_etiquetar(self):
        """CA-6 esc. 4 · TC62-06 — `etiqueta-origen.yml`: `pull_request` con `opened, reopened, synchronize, labeled, unlabeled`; `permissions` solo
        `contents: read`; trabajo `etiqueta` con `name: Etiqueta de origen` y sin `if:`; checkout por SHA sin credenciales; el paso ejecuta
        `python3 tools/etiqueta_origen.py` con `ETIQUETAS` por `env:` desde `toJSON(github.event.pull_request.labels.*.name)`."""
        self.assertEqual(comprobar_flujo_de_etiqueta(_texto_de_etiqueta(self)), [])

    def test_tkt062_ca06_esc04_etiquetar_no_relanza_ci(self):
        """CA-6 esc. 4 · TC62-07 (rechazo estático) — el `pull_request` de `ci.yml` no declara `types:` o no incluye `labeled`, `unlabeled` ni `edited`;
        quien recibe el `labeled` es `etiqueta-origen.yml`, que debe existir."""
        flujos = _leer_flujos(self)
        if "etiqueta-origen.yml" not in flujos:
            self.fail(
                "No existe .github/workflows/etiqueta-origen.yml: sin él, nada recibe el `labeled` y la comprobación de la etiqueta no se relanza"
            )
        self.assertEqual(comprobar_ci_no_se_relanza_al_etiquetar(flujos["ci.yml"]), [])

    def test_tkt062_car1_esc01_tc13_y_las_reglas_siguen_en_verde_con_el_flujo_de_etiqueta_presente(self):
        """CA-R1 · TC62-R1 — con `etiqueta-origen.yml` presente, `_leer_flujos` lo lee y TC-12, TC-13, TC-21 y TC-22 de TKT-009 y las reglas comunes
        sobre todo flujo siguen en verde. Es el espejo de `test_tc13_ningun_workflow_usa_workflow_run_y_todo_needs_apunta_a_su_archivo`,
        que ya corre sobre todos los flujos pero no exige que el nuevo esté."""
        flujos = _leer_flujos(self)
        if "etiqueta-origen.yml" not in flujos:
            self.fail("No existe .github/workflows/etiqueta-origen.yml: el flujo de TKT-062a todavía no está definido")
        self.assertEqual(comprobar_tc12(extraer_trabajos(flujos["ci.yml"])), [])
        for comprobacion in (comprobar_tc13, comprobar_tc21, comprobar_tc22, comprobar_reglas_comunes_de_todo_flujo):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(flujos), [])


# --- TC62-38 · fila A7 · la documentación de 062a --------------------------------------------------------------------------

LAS_CUATRO_ETIQUETAS = ("human", "human+copilot", "agent", "agent+human-review")

REGLA_DE_PR = re.compile(r"todo cambio a produccion entra por (?:un )?(?:pr|pull request)")
CIERRES_TAMBIEN = re.compile(r"tambien (?:los )?cierres")
OMISION = re.compile(r"omision de la proteccion")
ENFORCE_ADMINS_FALSE = re.compile(r"enforce_admins:? ?(?:a )?false")
COMENTARIO_DEL_PR = re.compile(r"comentario (?:del|en el) pr")
FUSION_CON_OMISION = re.compile(r"fusion con omision")
CIERRE_DENTRO_DEL_PR = re.compile(r"cierre viaja dentro del pr")
NO_CAMBIA_AL_APROBAR = re.compile(r"no cambia (?:al|cuando|con la) aprob")


def _normalizar_doc(texto: str) -> str:
    """Minúsculas, sin tildes, sin comillas invertidas ni negritas, espacios colapsados: se buscan términos, no texto literal."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    sin_marcas = sin_tildes.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", sin_marcas).lower()


def _leer_doc(ruta_relativa: str) -> str:
    ruta = os.path.join(RAIZ, *ruta_relativa.split("/"))
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


def _seccion(texto: str, encabezado: str) -> str:
    """Cuerpo desde la línea que casa con `encabezado` hasta el siguiente encabezado del mismo nivel o superior. Vacío si no existe."""
    lineas = texto.splitlines()
    for inicio, linea in enumerate(lineas):
        if re.match(encabezado, linea):
            nivel = len(linea) - len(linea.lstrip("#"))
            fin = len(lineas)
            for j in range(inicio + 1, len(lineas)):
                if re.match(rf"#{{1,{nivel}}} ", lineas[j]):
                    fin = j
                    break
            return "\n".join(lineas[inicio + 1 : fin])
    return ""


def _primer_parrafo(cuerpo: str) -> str:
    for parrafo in re.split(r"\n\s*\n", cuerpo.strip()):
        if parrafo.strip():
            return parrafo
    return ""


def _etiqueta_aislada(texto: str, etiqueta: str) -> bool:
    """`human` no cuenta dentro de `human+copilot` ni de `agent+human-review`; `agent`, tampoco dentro de `agent+human-review`."""
    return re.search(rf"(?<![\w+\-]){re.escape(etiqueta)}(?![\w+\-])", texto) is not None


def _faltan_etiquetas(texto: str) -> list[str]:
    return [e for e in LAS_CUATRO_ETIQUETAS if not _etiqueta_aislada(texto, e)]


def _lineas_de_origen(texto_crudo: str) -> list[str]:
    """Las líneas que listan los orígenes: las que nombran `agent+human-review`, ya normalizadas."""
    return [_normalizar_doc(linea) for linea in texto_crudo.splitlines() if "agent+human-review" in linea]


def _origenes_que_faltan(texto_crudo: str) -> str:
    lineas = _lineas_de_origen(texto_crudo)
    if not lineas:
        return "ninguna línea lista los orígenes"
    return ", ".join(sorted({e for linea in lineas for e in _faltan_etiquetas(linea)})) or "ninguno"


def _lista_los_cuatro(texto_crudo: str) -> bool:
    lineas = _lineas_de_origen(texto_crudo)
    return bool(lineas) and all(not _faltan_etiquetas(linea) for linea in lineas)


def _requisitos_de_documentacion() -> dict[str, list[tuple[str, bool]]]:
    """Por archivo, la lista de (frase que debe existir, si existe), calculada sobre el archivo real."""
    convenciones = _leer_doc("docs/convenciones.md")
    s6 = _normalizar_doc(_seccion(convenciones, r"## 6\. "))
    s11 = _normalizar_doc(_seccion(convenciones, r"## 11\. "))
    claude = _leer_doc("CLAUDE.md")
    parrafo_pr = _normalizar_doc(next((p for p in re.split(r"\n\s*\n", claude) if "Etiqueta el PR con su origen" in p), ""))
    readme = _normalizar_doc(_leer_doc("tools/README.md"))
    stack = _leer_doc("docs/06-stack-tecnologico.md")
    entrada_ci = _normalizar_doc(_primer_parrafo(_seccion(stack, r"### Integraci\S+ continua")))
    delta = _leer_doc("sdd/plantillas/delta.md")
    delta_n = _normalizar_doc(delta)
    delta_pr = _normalizar_doc(_seccion(delta, r"## Pull request"))
    skill = _leer_doc(".claude/skills/sdd-completar/SKILL.md")
    skill_n = _normalizar_doc(skill)
    agente = _leer_doc(".claude/agents/git-entrega.md")
    agente_n = _normalizar_doc(agente)
    toolkit = _leer_doc("sdd/00-propuesta-toolkit.md")
    fila_git_entrega = "\n".join(linea for linea in toolkit.splitlines() if "| `git-entrega` |" in linea)

    return {
        "docs/convenciones.md": [
            ("existe la sección «6. Definition of Done por tipo de trabajo»", bool(s6)),
            ("existe la sección «11. Métricas honestas»", bool(s11)),
            ("§11 dice que la etiqueta es el «origen del código»", "origen del codigo" in s11),
            ("§11 dice que la etiqueta «no cambia al aprobar»", NO_CAMBIA_AL_APROBAR.search(s11) is not None),
            (
                "§11 lista las cuatro etiquetas (human, human+copilot, agent, agent+human-review): faltan "
                + ", ".join(_faltan_etiquetas(s11)),
                bool(s11) and not _faltan_etiquetas(s11),
            ),
            ("§11 dice que el flujo «Etiqueta de origen» (etiqueta-origen.yml) las comprueba", "etiqueta-origen.yml" in s11),
            ("§11 dice que esa comprobación es requerida", "requerid" in s11),
            ("§6 lleva la regla «todo cambio a Produccion entra por un PR»", REGLA_DE_PR.search(s6) is not None),
            ("§11 lleva la regla «todo cambio a Produccion entra por un PR»", REGLA_DE_PR.search(s11) is not None),
            ("§6 dice «también los cierres»", CIERRES_TAMBIEN.search(s6) is not None),
            ("§6 describe la fusión con omisión de la protección", OMISION.search(s6) is not None),
            ("§6 dice que el registro de la fusión va en un comentario del PR", COMENTARIO_DEL_PR.search(s6) is not None),
            ("§6 o §11 mencionan enforce_admins: false", ENFORCE_ADMINS_FALSE.search(s6 + " " + s11) is not None),
        ],
        "CLAUDE.md": [
            ("existe el párrafo «Etiqueta el PR con su origen»", bool(parrafo_pr)),
            (
                "«Etiqueta el PR con su origen» nombra las cuatro etiquetas: faltan " + ", ".join(_faltan_etiquetas(parrafo_pr)),
                bool(parrafo_pr) and not _faltan_etiquetas(parrafo_pr),
            ),
            ("«Etiqueta el PR con su origen» nombra la comprobación requerida etiqueta-origen.yml", "etiqueta-origen.yml" in parrafo_pr),
        ],
        "tools/README.md": [
            ("describe tools/etiqueta_origen.py", re.search(r"(?<!\w)etiqueta_origen\.py", readme) is not None),
            ("describe test_etiqueta_origen.py", "test_etiqueta_origen.py" in readme),
            ("describe test_definicion_etiqueta.py", "test_definicion_etiqueta.py" in readme),
        ],
        "docs/06-stack-tecnologico.md": [
            ("la sección «Integración continua» existe y tiene un párrafo de entrada", bool(entrada_ci)),
            ("la frase de entrada de «Integración continua» nombra etiqueta-origen.yml como flujo aparte", "etiqueta-origen.yml" in entrada_ci),
            ("la frase de entrada nombra enlaces.yml junto a ci.yml (ya no dice que todo vive en ci.yml)", "enlaces.yml" in entrada_ci),
            ("la frase de entrada dice que etiqueta-origen.yml es requerido", "requerid" in entrada_ci),
        ],
        "sdd/plantillas/delta.md": [
            ("la línea Origen lista los cuatro orígenes: faltan " + _origenes_que_faltan(delta), _lista_los_cuatro(delta)),
            ("dice que Origen es el «origen del código»", "origen del codigo" in delta_n),
            ("dice que Origen no es el «estado de la revisión»", "estado de la revision" in delta_n),
            ("«Pull request» tiene el bloque «Fusión con omisión»", FUSION_CON_OMISION.search(delta_pr) is not None),
            ("el bloque dice que el registro va en un comentario del PR", COMENTARIO_DEL_PR.search(delta_pr) is not None),
            ("el bloque dice que el cierre viaja dentro del PR", CIERRE_DENTRO_DEL_PR.search(delta_pr) is not None),
        ],
        ".claude/skills/sdd-completar/SKILL.md": [
            ("la línea del origen del PR lista los cuatro orígenes: faltan " + _origenes_que_faltan(skill), _lista_los_cuatro(skill)),
            ("incluye el bloque «Fusión con omisión»", FUSION_CON_OMISION.search(skill_n) is not None),
            ("dice que el registro va en un comentario del PR", COMENTARIO_DEL_PR.search(skill_n) is not None),
            ("dice que el cierre viaja dentro del PR del ticket", CIERRE_DENTRO_DEL_PR.search(skill_n) is not None),
            ("dice que el cierre nunca va por empuje directo", "empuje directo" in skill_n),
        ],
        ".claude/agents/git-entrega.md": [
            ("las líneas de origen del PR listan los cuatro orígenes: faltan " + _origenes_que_faltan(agente), _lista_los_cuatro(agente)),
            ("la entrega ya no fija la etiqueta de origen `agent`", re.search(r"etiqueta de origen `agent`", agente) is None),
            ("la entrega dice «una de las cuatro»", "una de las cuatro" in agente_n),
        ],
        "sdd/00-propuesta-toolkit.md": [
            ("existe la fila de git-entrega", bool(fila_git_entrega)),
            ("la fila de git-entrega lista los cuatro orígenes: faltan " + _origenes_que_faltan(fila_git_entrega), _lista_los_cuatro(fila_git_entrega)),
        ],
    }


class DocumentacionDeLaEtiqueta(unittest.TestCase):
    """Fila A7 · TC62-38: los documentos de 062a describen la etiqueta de origen. Lee los archivos reales; sin la frase, falla."""

    def test_tkt062_ca12_esc01_la_documentacion_de_062a_describe_la_etiqueta(self):
        """CA-12 esc. 1 · TC62-38 — convenciones §6 y §11 (origen del código, no cambia al aprobar, las cuatro etiquetas, `etiqueta-origen.yml`,
        todo cambio a Produccion entra por PR también los cierres, fusión con omisión de la protección con `enforce_admins: false` y registro
        en comentario del PR); `CLAUDE.md`; `tools/README.md`; stack «Integración continua»; y los cuatro orígenes (con `human`) más el bloque
        «Fusión con omisión» en `delta.md`, `sdd-completar`, `git-entrega` y la propuesta del toolkit."""
        for archivo, requisitos in _requisitos_de_documentacion().items():
            with self.subTest(archivo=archivo):
                faltan = [descripcion for descripcion, cumple in requisitos if not cumple]
                self.assertEqual(faltan, [], f"{archivo}: faltan {len(faltan)} frase(s): " + " | ".join(faltan))


if __name__ == "__main__":
    unittest.main()
