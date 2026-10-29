"""Pruebas estáticas de la definición del pipeline, `.github/workflows/ci.yml` y el resto de `.github/workflows/`.

TKT-009a · filas A2, A3 y A4. Comprueban lo que el pipeline *declara*, no lo que hace al correr: que cada compuerta
exista en el trabajo que le toca, en el orden que exigen los criterios, y que ninguna esté apagada sin quitarla.
Su rojo previo es que `ci.yml` no existe o que le falta la compuerta.

Qué cubren:

* Fila A2, trabajos `backend`, `fronteras`, `contrato-api` y `frontend`: TC-01, TC-05, TC-06, TC-12 y TC-13.
* Fila A3, trabajo `humo`: TC-08.
* Fila A4, trabajos `herramientas`, `workflows` y `documentacion`: TC-23, TC-21, TC-22 y TC-R4b, más el soporte de
  TC-20 y TC-24 (el trabajo `workflows` con zizmor de versión fija).
* Rechazos estáticos: TC-R1a (ni SQLite ni `create_all()`) y TC-13 (ni `workflow_run` ni `needs` ajeno).
* Reglas comunes del diseño: 1 (corredor y tiempo máximo), 6 (cada paso de comprobación de `backend` y `frontend`
  lleva `if: ${{ !cancelled() }}`), 7 (ninguna compuerta se desactiva: sin `continue-on-error`, sin un `if:` que
  apague el paso y sin `|| true`; además, un pytest sin selección), 8 (ningún `run:` interpola `${{ }}`) y 9
  (toda tubería declara `shell: bash`).

`tools/` no tiene dependencias y la biblioteca estándar no trae un analizador de YAML, así que el texto se lee
con expresiones regulares. Eso tiene un riesgo que la objeción 11 de la pasada adversarial del diseño nombra: un
paso comentado, o movido a otro trabajo, seguiría casando con una búsqueda sobre el archivo entero y la
compuerta estaría desactivada sin que nada lo note. Por eso:

* Se ignoran las líneas comentadas y los comentarios al final de línea.
* Cada caso busca **dentro del bloque de su trabajo** (se extrae por sangría bajo `jobs:`) y, dentro de él, en
  el `run:` de cada paso, no en su `name:`.
* Los casos viven en funciones `comprobar_*` que devuelven la lista de problemas. Las pruebas sobre texto
  sintético (las clases `PruebasDeMutantes*`) demuestran que cada función se pone en rojo ante el mutante «paso
  comentado», «paso en otro trabajo» o «compuerta apagada» sin tocar `ci.yml`, y por la razón esperada: cada
  mutante exige un fragmento del mensaje del problema, no solo que la lista no esté vacía.

Limitaciones de la lectura por expresiones regulares, aceptadas: un apóstrofo suelto en texto sin comillas
desactiva la poda de un comentario en esa línea, y las anclas y alias de YAML no se resuelven.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_definicion_ci -v
"""
from __future__ import annotations

import functools
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIRECTORIO_DE_FLUJOS = os.path.join(RAIZ, ".github", "workflows")
CI = os.path.join(DIRECTORIO_DE_FLUJOS, "ci.yml")

# Regla común 1 del diseño: corredor fijo y tiempo máximo por trabajo.
CORREDOR = "ubuntu-24.04"
TIEMPO_POR_TRABAJO = {"backend": 25, "humo": 20}
TIEMPO_POR_OMISION = 15


# ---------------------------------------------------------------------------------------------------------
# Lectura del texto: comentarios, bloques de trabajo, pasos y claves
# ---------------------------------------------------------------------------------------------------------


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


def _quitar_comentario(linea: str) -> str:
    """Recorta el comentario de una línea. En YAML, `#` abre comentario solo al inicio o tras un espacio, y no dentro de comillas."""
    comilla = None
    for i, caracter in enumerate(linea):
        if comilla:
            if caracter == comilla:
                comilla = None
        elif caracter in "\"'":
            comilla = caracter
        elif caracter == "#" and (i == 0 or linea[i - 1] in " \t"):
            return linea[:i].rstrip()
    return linea.rstrip()


def sin_comentarios(texto: str) -> str:
    """Devuelve el texto sin comentarios y sin líneas en blanco."""
    limpias = (_quitar_comentario(linea) for linea in texto.splitlines())
    return "\n".join(linea for linea in limpias if linea.strip())


def extraer_trabajos(texto: str) -> dict[str, list[str]]:
    """Bloque de líneas de cada trabajo bajo `jobs:`, por su `id`, sin comentarios. La primera línea del bloque es `id:`."""
    lineas = sin_comentarios(texto).splitlines()
    inicio = next((k for k, linea in enumerate(lineas) if re.fullmatch(r"jobs:\s*", linea)), None)
    if inicio is None:
        return {}
    trabajos: dict[str, list[str]] = {}
    sangria_de_trabajo = None
    actual = None
    for linea in lineas[inicio + 1 :]:
        sangria = _sangria(linea)
        if sangria == 0:
            break  # otra clave de primer nivel: termina `jobs:`
        if sangria_de_trabajo is None:
            sangria_de_trabajo = sangria
        encabezado = re.fullmatch(rf" {{{sangria_de_trabajo}}}([A-Za-z0-9_-]+):\s*", linea)
        if sangria == sangria_de_trabajo and encabezado:
            actual = encabezado.group(1)
            trabajos[actual] = [linea]
        elif actual is not None:
            trabajos[actual].append(linea)
    return trabajos


def _columna_del_trabajo(bloque: list[str]) -> int:
    """Columna de las claves del trabajo (`name`, `needs`, `steps`…)."""
    return _sangria(bloque[1]) if len(bloque) > 1 else 0


def _valor_de_clave(lineas: list[str], columna: int, clave: str) -> str | None:
    """Valor de `clave` en la `columna` dada: escalar en la misma línea, o el cuerpo de un bloque (`|`, `>` o lista)."""
    normales = list(lineas)
    if normales and re.match(r"^\s*- ", normales[0]):
        normales[0] = re.sub(r"^(\s*)- ", lambda m: m.group(1) + "  ", normales[0], count=1)
    patron = re.compile(rf"^ {{{columna}}}{re.escape(clave)}:[ \t]*(.*)$")
    for k, linea in enumerate(normales):
        encontrada = patron.match(linea)
        if not encontrada:
            continue
        resto = encontrada.group(1).strip()
        if resto and resto[0] not in "|>":
            return resto
        cuerpo = []
        for siguiente in normales[k + 1 :]:
            es_elemento_de_lista = resto == "" and _sangria(siguiente) == columna and siguiente.lstrip().startswith("- ")
            if _sangria(siguiente) > columna or es_elemento_de_lista:
                cuerpo.append(siguiente.strip())
            else:
                break
        return "\n".join(cuerpo)
    return None


def valor_del_trabajo(bloque: list[str], clave: str) -> str | None:
    """Valor de una clave del trabajo mismo (no de sus pasos)."""
    return _valor_de_clave(bloque, _columna_del_trabajo(bloque), clave)


def pasos(bloque: list[str]) -> list[list[str]]:
    """Los pasos de `steps:`, cada uno como lista de líneas."""
    columna = _columna_del_trabajo(bloque)
    inicio = next((k for k, linea in enumerate(bloque) if _sangria(linea) == columna and linea.strip() == "steps:"), None)
    if inicio is None:
        return []
    resultado: list[list[str]] = []
    sangria_de_elemento = None
    actual: list[str] | None = None
    for linea in bloque[inicio + 1 :]:
        sangria = _sangria(linea)
        es_elemento = linea.lstrip().startswith("- ")
        if sangria_de_elemento is None:
            if not es_elemento:
                break
            sangria_de_elemento = sangria
        if sangria < sangria_de_elemento or (sangria == sangria_de_elemento and not es_elemento):
            break
        if sangria == sangria_de_elemento:
            actual = [linea]
            resultado.append(actual)
        elif actual is not None:
            actual.append(linea)
    return resultado


def valor_del_paso(paso: list[str], clave: str) -> str | None:
    return _valor_de_clave(paso, _sangria(paso[0]) + 2, clave)


def comando(paso: list[str]) -> str:
    """El texto de `run:` del paso; vacío si no tiene. El `name:` de un paso nunca cuenta como comando."""
    return valor_del_paso(paso, "run") or ""


def directorio_por_omision(bloque: list[str]) -> str | None:
    """`defaults.run.working-directory` del trabajo."""
    columna = _columna_del_trabajo(bloque)
    for k, linea in enumerate(bloque):
        if _sangria(linea) == columna and linea.strip() == "defaults:":
            for siguiente in bloque[k + 1 :]:
                if _sangria(siguiente) <= columna:
                    break
                encontrado = re.match(r"\s*working-directory:\s*(\S+)", siguiente)
                if encontrado:
                    return encontrado.group(1).strip("\"'")
    return None


def directorio_del_paso(bloque: list[str], paso: list[str]) -> str | None:
    """El `working-directory` del paso; si no lo declara, el del trabajo."""
    propio = valor_del_paso(paso, "working-directory")
    if propio is not None:
        return propio.strip("\"'")
    return directorio_por_omision(bloque)


def ids_de_needs(bloque: list[str]) -> list[str]:
    valor = valor_del_trabajo(bloque, "needs") or ""
    return re.findall(r"[A-Za-z0-9_-]+", valor.replace("- ", " "))


def _normalizada(expresion: str | None) -> str:
    return re.sub(r"\s+", "", expresion or "")


def _localizar(lista_de_pasos: list[list[str]], patron: str, despues: tuple[int, int] = (-1, -1)) -> tuple[int, int] | None:
    """Primera coincidencia de `patron` en el `run:` de algún paso, estrictamente posterior a `despues`: (índice de paso, posición)."""
    for i, paso in enumerate(lista_de_pasos):
        for encontrado in re.finditer(patron, comando(paso)):
            if (i, encontrado.start()) > despues:
                return (i, encontrado.start())
    return None


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones: cada una devuelve la lista de problemas, vacía si el caso se cumple
# ---------------------------------------------------------------------------------------------------------

UV_SYNC = r"\buv sync --locked --python 3\.14(?![\w.])"


def comprobar_secuencia(
    id_trabajo: str,
    trabajos: dict[str, list[str]],
    esperados: list[tuple[str, str, str | None]],
) -> tuple[list[str], dict[str, tuple[int, int]]]:
    """Cada `(etiqueta, patrón, directorio)` debe aparecer en el `run:` de un paso del trabajo, tras el anterior y con ese directorio."""
    if id_trabajo not in trabajos:
        return [f"no existe el trabajo '{id_trabajo}'"], {}
    bloque = trabajos[id_trabajo]
    lista = pasos(bloque)
    problemas: list[str] = []
    posiciones: dict[str, tuple[int, int]] = {}
    previo = (-1, -1)
    anterior = "el inicio del trabajo"
    for etiqueta, patron, directorio in esperados:
        posicion = _localizar(lista, patron, previo)
        if posicion is None:
            problemas.append(
                f"'{id_trabajo}': falta «{etiqueta}» en un run: del trabajo, o aparece antes de «{anterior}» "
                "(un paso comentado o de otro trabajo no cuenta)"
            )
            continue
        posiciones[etiqueta] = posicion
        previo = posicion
        anterior = etiqueta
        if directorio is not None:
            real = directorio_del_paso(bloque, lista[posicion[0]])
            if real != directorio:
                problemas.append(f"'{id_trabajo}': «{etiqueta}» debe ejecutarse con working-directory: {directorio} y tiene {real!r}")
    return problemas, posiciones


def comprobar_tc01(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-1 esc. 1."""
    problemas, posiciones = comprobar_secuencia(
        "backend",
        trabajos,
        [
            ("uv sync --locked --python 3.14", UV_SYNC, None),
            ("ruff format --check", r"\buv run ruff format --check\b", None),
            ("ruff check", r"\buv run ruff check\b", None),
            ("mypy", r"\buv run mypy\b", None),
            ("herramientas.verificar_float", r"\buv run python -m herramientas\.verificar_float\b", None),
            ("pytest", r"\buv run pytest\b", None),
        ],
    )
    if "backend" not in trabajos:
        return problemas
    lista = pasos(trabajos["backend"])
    posicion_de_pytest = posiciones.get("pytest")
    if posicion_de_pytest is not None:
        # Las banderas tienen que estar en la misma orden de pytest, no en cualquier otra parte del paso.
        orden = comando(lista[posicion_de_pytest[0]])[posicion_de_pytest[1] :].replace("\\\n", " ").split("\n")[0]
        for bandera in (r"--cov(?:=|\s|$)", r"--junitxml(?:=|\s|$)"):
            if not re.search(bandera, orden):
                problemas.append(f"'backend': la orden de pytest no lleva {bandera.split('(')[0]}")
    despues = posicion_de_pytest[0] if posicion_de_pytest else -1
    subida = next(
        (p for i, p in enumerate(lista) if i > despues and re.match(r"actions/upload-artifact@", valor_del_paso(p, "uses") or "")),
        None,
    )
    if subida is None:
        problemas.append("'backend': falta un paso actions/upload-artifact después de pytest")
    elif _normalizada(valor_del_paso(subida, "if")) not in ("always()", "${{always()}}"):
        problemas.append("'backend': el paso upload-artifact no declara `if: always()` y un fallo de pytest no publicaría el informe")
    return problemas


def comprobar_tc05(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-3 esc. 1."""
    problemas, _ = comprobar_secuencia(
        "fronteras",
        trabajos,
        [
            ("uv sync --locked --python 3.14", UV_SYNC, "backend"),
            ("uv run lint-imports", r"\buv run lint-imports\b", "backend"),
        ],
    )
    return problemas


def comprobar_tc06(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-4 esc. 1."""
    problemas, _ = comprobar_secuencia(
        "frontend",
        trabajos,
        [
            ("uv sync --locked --python 3.14", UV_SYNC, "backend"),
            ("npm ci", r"\bnpm ci(?![\w:-])", "frontend"),
            ("npm run lint", r"\bnpm run lint(?![\w:-])", "frontend"),
            ("npm run typecheck", r"\bnpm run typecheck(?![\w:-])", "frontend"),
            ("npm test", r"\bnpm test(?![\w:-])", "frontend"),
            ("npm run tipos:verificar", r"\bnpm run tipos:verificar(?![\w:-])", "frontend"),
        ],
    )
    return problemas


def comprobar_tc08(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-5 esc. 1 · fila A3. El trabajo `humo` construye el entorno desde cero, corre el recorrido y sube el informe si falla."""
    problemas, posiciones = comprobar_secuencia(
        "humo",
        trabajos,
        [
            ("cp .env.example .env", r"\bcp \.env\.example \.env(?![\w.])", None),
            ("docker compose up -d --wait db", r"\bdocker compose up -d --wait db(?![\w-])", None),
            ("uv sync --locked --python 3.14", UV_SYNC, "backend"),
            ("alembic upgrade head", r"\buv run --env-file \.\./\.env alembic upgrade head(?![\w-])", "backend"),
            (
                "herramientas.contrasenas_roles",
                r"\buv run --env-file \.\./\.env python -m herramientas\.contrasenas_roles(?![\w.])",
                "backend",
            ),
            ("npm ci", r"\bnpm ci(?![\w:-])", "frontend"),
            ("npx playwright install --with-deps chromium", r"\bnpx playwright install --with-deps chromium(?![\w-])", "frontend"),
            ("npm run e2e -- --reporter=list,html", r"\bnpm run e2e -- --reporter=list,html(?![\w,.-])", "frontend"),
        ],
    )
    if "humo" not in trabajos:
        return problemas
    bloque = trabajos["humo"]
    lista = pasos(bloque)
    # `.env.example` y `compose.yaml` viven en la raíz: ejecutados desde otro directorio, no encuentran nada.
    for etiqueta in ("cp .env.example .env", "docker compose up -d --wait db"):
        posicion = posiciones.get(etiqueta)
        if posicion is not None:
            real = directorio_del_paso(bloque, lista[posicion[0]])
            if real not in (None, "."):
                problemas.append(f"'humo': «{etiqueta}» debe ejecutarse desde la raíz del repositorio y tiene working-directory: {real}")
    despues = posiciones["npm run e2e -- --reporter=list,html"][0] if "npm run e2e -- --reporter=list,html" in posiciones else -1
    subidas = [
        p
        for i, p in enumerate(lista)
        if i > despues and re.match(r"actions/upload-artifact@", valor_del_paso(p, "uses") or "")
    ]
    informe = next((p for p in subidas if re.search(r"^name:\s*humo-playwright\s*$", valor_del_paso(p, "with") or "", flags=re.MULTILINE)), None)
    if informe is None:
        problemas.append("'humo': falta, después de npm run e2e, un actions/upload-artifact con `name: humo-playwright`")
        return problemas
    if _normalizada(valor_del_paso(informe, "if")) not in ("failure()", "${{failure()}}"):
        problemas.append("'humo': el paso upload-artifact no declara `if: failure()`; un recorrido roto no publicaría el informe")
    ruta = valor_del_paso(informe, "with") or ""
    for carpeta in ("frontend/playwright-report/", "frontend/test-results/"):
        if carpeta not in ruta:
            problemas.append(f"'humo': el artefacto humo-playwright no incluye {carpeta}")
    return problemas


def _no_se_cancela(bloque: list[str]) -> bool:
    return _normalizada(valor_del_trabajo(bloque, "if")) in ("${{!cancelled()}}", "!cancelled()")


def comprobar_tc12(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-9 esc. 1 y pasada adversarial 12."""
    problemas = []
    if "contrato-api" not in trabajos:
        problemas.append("no existe el trabajo 'contrato-api'")
    else:
        reservado = trabajos["contrato-api"]
        if "TKT-061" not in (valor_del_trabajo(reservado, "name") or ""):
            problemas.append("'contrato-api': su name: no cita TKT-061")
        if "backend" not in ids_de_needs(reservado):
            problemas.append("'contrato-api': no declara needs: backend")
        if not _no_se_cancela(reservado):
            problemas.append("'contrato-api': le falta `if: ${{ !cancelled() }}` a nivel de trabajo")
    if "frontend" not in trabajos:
        problemas.append("no existe el trabajo 'frontend'")
    else:
        cliente = trabajos["frontend"]
        if "contrato-api" not in ids_de_needs(cliente):
            problemas.append("'frontend': no declara needs: contrato-api")
        if not _no_se_cancela(cliente):
            problemas.append("'frontend': le falta `if: ${{ !cancelled() }}` a nivel de trabajo")
    return problemas


def comprobar_tc13(flujos: dict[str, str]) -> list[str]:
    """CA-9 esc. 2. `flujos` es nombre de archivo -> texto."""
    problemas = []
    for nombre, texto in flujos.items():
        if re.search(r"\bworkflow_run\b", sin_comentarios(texto)):
            problemas.append(f"{nombre}: usa el disparador workflow_run, que ata el pipeline a otro flujo")
        trabajos = extraer_trabajos(texto)
        for id_trabajo, bloque in trabajos.items():
            for necesidad in ids_de_needs(bloque):
                if necesidad not in trabajos:
                    problemas.append(f"{nombre}: '{id_trabajo}' necesita '{necesidad}', que no es un trabajo de este archivo")
    return problemas


def comprobar_regla_comun_1(trabajos: dict[str, list[str]]) -> list[str]:
    """Regla común 1 del diseño: `runs-on: ubuntu-24.04` y `timeout-minutes` en todos los trabajos."""
    problemas = []
    if not trabajos:
        return ["el archivo no declara ningún trabajo bajo jobs:"]
    for id_trabajo, bloque in trabajos.items():
        corredor = valor_del_trabajo(bloque, "runs-on")
        if corredor != CORREDOR:
            problemas.append(f"'{id_trabajo}': runs-on debe ser {CORREDOR} y es {corredor!r}")
        tiempo = valor_del_trabajo(bloque, "timeout-minutes")
        esperado = TIEMPO_POR_TRABAJO.get(id_trabajo, TIEMPO_POR_OMISION)
        if tiempo != str(esperado):
            problemas.append(f"'{id_trabajo}': timeout-minutes debe ser {esperado} y es {tiempo!r}")
    return problemas


def comprobar_r1a(texto: str) -> list[str]:
    """CA-R1 esc. 1. Un comentario que explique por qué no hay SQLite no cuenta como uso."""
    activo = sin_comentarios(texto).lower()
    return [f"ci.yml contiene «{palabra}»" for palabra in ("sqlite", "create_all") if palabra in activo]


# ---------------------------------------------------------------------------------------------------------
# Pruebas de los ayudantes, sobre texto sintético
# ---------------------------------------------------------------------------------------------------------


class PruebasDeLosAyudantes(unittest.TestCase):
    """Demuestran que el extractor ignora comentarios y respeta los límites de cada trabajo (objeción 11)."""

    def test_ayudante_sin_comentarios_quita_lineas_y_finales_pero_no_el_numeral_entrecomillado(self):
        """Pasada adversarial 11 — un `#` es comentario salvo dentro de comillas o pegado a una palabra."""
        texto = (
            "# cabecera\n"
            "  - run: uv run mypy .   # comprobar tipos\n"
            "    # - run: uv run pytest\n"
            '  - run: echo "a # b"\n'
            "  - uses: x/y@abc # v1\n"
            "  - run: curl http://h/#ancla\n"
        )
        self.assertEqual(
            sin_comentarios(texto).splitlines(),
            [
                "  - run: uv run mypy .",
                '  - run: echo "a # b"',
                "  - uses: x/y@abc",
                "  - run: curl http://h/#ancla",
            ],
        )

    def test_ayudante_extraer_trabajos_separa_bloques_y_no_mezcla_pasos(self):
        """Pasada adversarial 11 — un paso de un trabajo no aparece en el bloque del vecino."""
        texto = (
            "name: X\njobs:\n  uno:\n    steps:\n      - run: a\n  dos:\n    steps:\n      - run: b\npermissions:\n  contents: read\n"
        )
        trabajos = extraer_trabajos(texto)
        self.assertEqual(list(trabajos), ["uno", "dos"])
        self.assertEqual([comando(p) for p in pasos(trabajos["uno"])], ["a"])
        self.assertEqual([comando(p) for p in pasos(trabajos["dos"])], ["b"])

    def test_ayudante_extraer_trabajos_ignora_un_trabajo_comentado(self):
        """Pasada adversarial 11 — un trabajo entero comentado no existe."""
        texto = "jobs:\n  uno:\n    steps: []\n#  dos:\n#    steps: []\n"
        self.assertEqual(list(extraer_trabajos(texto)), ["uno"])

    def test_ayudante_comando_lee_solo_run_y_cuerpos_de_bloque(self):
        """Pasada adversarial 11 — el `name:` de un paso que cita un comando no es el comando."""
        texto = (
            "jobs:\n  uno:\n    steps:\n"
            "      - name: uv run mypy .\n"
            "        run: echo nada\n"
            "      - name: multilinea\n"
            "        run: |\n"
            "          uv sync --locked --python 3.14\n"
            "          uv run pytest -q\n"
            "      - uses: actions/checkout@abc\n"
        )
        lista = pasos(extraer_trabajos(texto)["uno"])
        self.assertEqual(comando(lista[0]), "echo nada")
        self.assertEqual(comando(lista[1]), "uv sync --locked --python 3.14\nuv run pytest -q")
        self.assertEqual(comando(lista[2]), "")

    def test_ayudante_needs_acepta_escalar_corchetes_y_lista(self):
        """CA-9 — las tres formas de declarar `needs`."""
        for forma in ("needs: backend", "needs: [backend, otro]", "needs:\n      - backend\n      - otro"):
            with self.subTest(forma=forma):
                texto = f"jobs:\n  uno:\n    {forma}\n    steps: []\n"
                esperado = ["backend"] if forma == "needs: backend" else ["backend", "otro"]
                self.assertEqual(ids_de_needs(extraer_trabajos(texto)["uno"]), esperado)

    def test_ayudante_clave_del_trabajo_no_confunde_la_de_un_paso(self):
        """CA-9 / pasada adversarial 12 — un `if:` de un paso no es el `if:` del trabajo."""
        texto = "jobs:\n  uno:\n    runs-on: x\n    steps:\n      - run: a\n        if: ${{ !cancelled() }}\n"
        bloque = extraer_trabajos(texto)["uno"]
        self.assertIsNone(valor_del_trabajo(bloque, "if"))
        self.assertEqual(valor_del_paso(pasos(bloque)[0], "if"), "${{ !cancelled() }}")


# ---------------------------------------------------------------------------------------------------------
# Texto sintético válido y sus mutantes: demuestran que cada comprobación se pone en rojo
# ---------------------------------------------------------------------------------------------------------

CI_SINTETICO_VALIDO = """\
name: CI
on:
  pull_request:
permissions:
  contents: read
jobs:
  backend:
    name: Backend · formato, lint, tipos, float y pruebas
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@abc # v6
      - uses: astral-sh/setup-uv@abc # v10
      - run: uv sync --locked --python 3.14
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run mypy .
      - run: uv run python -m herramientas.verificar_float
      - run: uv run pytest --cov=cimenta --cov-report=xml:cobertura.xml --junitxml=pytest.xml
      - uses: actions/upload-artifact@abc # v5
        if: always()
        with:
          name: backend-pruebas
          path: backend/pytest.xml
  fronteras:
    name: Fronteras entre módulos
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@abc # v6
      - uses: astral-sh/setup-uv@abc # v10
      - run: uv sync --locked --python 3.14
      - run: uv run lint-imports
  contrato-api:
    name: Prueba de contrato de la API · reservado para TKT-061
    needs: backend
    if: ${{ !cancelled() }}
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - run: echo "Reservado para TKT-061: sin contenido todavía."
  frontend:
    name: Frontend · lint, tipos, pruebas y tipos generados
    needs: contrato-api
    if: ${{ !cancelled() }}
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@abc # v6
      - uses: astral-sh/setup-uv@abc # v10
      - run: uv sync --locked --python 3.14
        working-directory: backend
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm run typecheck
        working-directory: frontend
      - run: npm test
        working-directory: frontend
      - run: npm run tipos:verificar
        working-directory: frontend
"""

COMPROBACIONES_DE_TRABAJO = (
    comprobar_tc01,
    comprobar_tc05,
    comprobar_tc06,
    comprobar_tc12,
    comprobar_regla_comun_1,
)


def _rebanada(texto: str, id_trabajo: str) -> tuple[int, int]:
    """Posición inicial y final del bloque de un trabajo dentro del texto."""
    inicio = texto.index(f"\n  {id_trabajo}:\n") + 1
    siguiente = re.search(r"^  [A-Za-z0-9_-]+:\s*$", texto[inicio + 1 :], flags=re.MULTILINE)
    fin = inicio + 1 + siguiente.start() if siguiente else len(texto)
    return inicio, fin


def mutar(texto: str, id_trabajo: str, viejo: str, nuevo: str) -> str:
    """Cambia `viejo` por `nuevo` una sola vez y solo dentro del trabajo dado. Falla si el mutante no cambia nada."""
    inicio, fin = _rebanada(texto, id_trabajo)
    bloque = texto[inicio:fin]
    if bloque.count(viejo) != 1:
        raise AssertionError(f"el mutante no es aplicable: {viejo!r} aparece {bloque.count(viejo)} veces en '{id_trabajo}'")
    return texto[:inicio] + bloque.replace(viejo, nuevo) + texto[fin:]


def comentar(texto: str, id_trabajo: str, viejo: str) -> str:
    """Mutante «paso comentado»: antepone `# ` a cada línea de `viejo`."""
    comentado = "".join("      # " + linea.strip() + "\n" if linea.strip() else linea for linea in viejo.splitlines(keepends=True))
    return mutar(texto, id_trabajo, viejo, comentado)


def mover(texto: str, origen: str, destino: str, paso: str, despues_de: str) -> str:
    """Mutante «paso en otro trabajo»: saca `paso` de `origen` y lo pone tras `despues_de` en `destino`."""
    sin_paso = mutar(texto, origen, paso, "")
    return mutar(sin_paso, destino, despues_de, despues_de + paso)


def sustituir(texto: str, viejo: str, nuevo: str) -> str:
    """Mutante sobre el texto entero (fuera de un bloque de trabajo): cambia `viejo` por `nuevo` exactamente una vez, o falla."""
    if texto.count(viejo) != 1:
        raise AssertionError(f"el mutante no es aplicable: {viejo!r} aparece {texto.count(viejo)} veces en el texto")
    mutante = texto.replace(viejo, nuevo)
    if mutante == texto:
        raise AssertionError(f"el mutante no cambia nada: {viejo!r} y {nuevo!r} son iguales")
    return mutante


def exigir_rojo(caso: unittest.TestCase, comprobacion, texto: str, fragmento: str | None = None) -> list[str]:
    """El mutante `texto` debe poner `comprobacion` en rojo y, si se da `fragmento`, por la razón esperada: algún problema lo menciona."""
    problemas = comprobacion(extraer_trabajos(texto))
    caso.assertNotEqual(problemas, [], "el mutante debía poner la comprobación en rojo y pasó en verde")
    if fragmento is not None:
        caso.assertTrue(
            any(fragmento in problema for problema in problemas),
            f"el rojo no es por la razón esperada: ningún problema menciona {fragmento!r}: {problemas}",
        )
    return problemas


def exigir_rojo_en_todos(
    caso: unittest.TestCase, comprobacion, casos: dict, fragmento: str | None = None, fragmentos: dict[str, str] | None = None
) -> None:
    """Corre `exigir_rojo` por cada mutante de `casos`. El fragmento esperado sale, por orden, de `fragmentos[descripcion]`,
    del `(texto, fragmento)` del propio caso o del `fragmento` común. `fragmentos` no puede nombrar un mutante que no existe."""
    fragmentos = fragmentos or {}
    caso.assertEqual(set(fragmentos) - set(casos), set(), "fragmentos para mutantes que no existen")
    for descripcion, valor in casos.items():
        texto, propio = valor if isinstance(valor, tuple) else (valor, fragmento)
        with caso.subTest(mutante=descripcion):
            exigir_rojo(caso, comprobacion, texto, fragmentos.get(descripcion, propio))


PASO_MYPY = "      - run: uv run mypy .\n"
PASO_PYTEST ="      - run: uv run pytest --cov=cimenta --cov-report=xml:cobertura.xml --junitxml=pytest.xml\n"
PASO_SINCRONIZAR_BACKEND = "      - run: uv sync --locked --python 3.14\n        working-directory: backend\n"
PASO_NPM_CI = "      - run: npm ci\n        working-directory: frontend\n"
PASO_LINT = "      - run: npm run lint\n        working-directory: frontend\n"
PASO_TYPECHECK = "      - run: npm run typecheck\n        working-directory: frontend\n"
PASO_NPM_TEST = "      - run: npm test\n        working-directory: frontend\n"
PASO_TIPOS = "      - run: npm run tipos:verificar\n        working-directory: frontend\n"
PASO_LINT_IMPORTS = "      - run: uv run lint-imports\n"


class PruebasDeMutantes(unittest.TestCase):
    """Objeción 11: cada comprobación estática se pone en rojo si el paso se comenta o se mueve de trabajo."""

    def test_mutantes_el_texto_valido_pasa_todas_las_comprobaciones(self):
        """Control — sin esto, un mutante «en rojo» podría estar en rojo por culpa del texto base."""
        trabajos = extraer_trabajos(CI_SINTETICO_VALIDO)
        for comprobacion in COMPROBACIONES_DE_TRABAJO:
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])
        self.assertEqual(comprobar_tc13({"ci.yml": CI_SINTETICO_VALIDO}), [])
        self.assertEqual(comprobar_r1a(CI_SINTETICO_VALIDO), [])

    def test_mutantes_tc01_backend_pierde_cada_compuerta(self):
        """CA-1 esc. 1 · TC-01 — un paso comentado o llevado a otro trabajo deja el caso en rojo."""
        casos = {
            "mypy comentado": comentar(CI_SINTETICO_VALIDO, "backend", PASO_MYPY),
            "pytest comentado": comentar(CI_SINTETICO_VALIDO, "backend", PASO_PYTEST),
            "mypy movido a fronteras": mover(CI_SINTETICO_VALIDO, "backend", "fronteras", PASO_MYPY, PASO_LINT_IMPORTS),
            "pytest movido a fronteras": mover(CI_SINTETICO_VALIDO, "backend", "fronteras", PASO_PYTEST, PASO_LINT_IMPORTS),
            "mypy antes que ruff check": mutar(
                CI_SINTETICO_VALIDO, "backend", "      - run: uv run ruff check .\n" + PASO_MYPY, PASO_MYPY + "      - run: uv run ruff check .\n"
            ),
            "sin --junitxml": mutar(CI_SINTETICO_VALIDO, "backend", " --junitxml=pytest.xml", ""),
            "sin --cov": mutar(CI_SINTETICO_VALIDO, "backend", "--cov=cimenta --cov-report=xml:cobertura.xml ", ""),
            "if: always() comentado": comentar(CI_SINTETICO_VALIDO, "backend", "        if: always()\n"),
            "uv sync comentado": comentar(CI_SINTETICO_VALIDO, "backend", "      - run: uv sync --locked --python 3.14\n"),
            "uv sync sin --locked": mutar(CI_SINTETICO_VALIDO, "backend", "uv sync --locked --python 3.14", "uv sync --python 3.14"),
            "el comando solo en un name": mutar(CI_SINTETICO_VALIDO, "backend", PASO_MYPY, "      - name: uv run mypy .\n        run: echo omitido\n"),
        }
        fragmentos = {
            "mypy comentado": "mypy",
            "pytest comentado": "pytest",
            "mypy movido a fronteras": "mypy",
            "pytest movido a fronteras": "pytest",
            "mypy antes que ruff check": "mypy",
            "sin --junitxml": "la orden de pytest no lleva --junitxml",
            "sin --cov": "la orden de pytest no lleva --cov",
            "if: always() comentado": "el paso upload-artifact no declara `if: always()` y un fallo de pytest no publicaría el informe",
            "uv sync comentado": "uv sync --locked --python 3.14",
            "uv sync sin --locked": "uv sync --locked --python 3.14",
            "el comando solo en un name": "mypy",
        }
        exigir_rojo_en_todos(self, comprobar_tc01, casos, "'backend'", fragmentos=fragmentos)

    def test_mutantes_tc05_fronteras_pierde_lint_imports_o_su_directorio(self):
        """CA-3 esc. 1 · TC-05 — comentar, mover o sacar de `backend/` el paso deja el caso en rojo."""
        casos = {
            "lint-imports comentado": comentar(CI_SINTETICO_VALIDO, "fronteras", PASO_LINT_IMPORTS),
            "lint-imports movido a backend": mover(
                CI_SINTETICO_VALIDO, "fronteras", "backend", PASO_LINT_IMPORTS, "      - run: uv run ruff check .\n"
            ),
            "sin working-directory": mutar(
                CI_SINTETICO_VALIDO,
                "fronteras",
                "    defaults:\n      run:\n        working-directory: backend\n",
                "",
            ),
            "working-directory distinto": mutar(CI_SINTETICO_VALIDO, "fronteras", "working-directory: backend", "working-directory: frontend"),
            "trabajo ausente": sustituir(CI_SINTETICO_VALIDO, "\n  fronteras:\n", "\n  limites:\n"),
        }
        fragmentos = {
            "lint-imports comentado": "uv run lint-imports",
            "lint-imports movido a backend": "uv run lint-imports",
            "sin working-directory": "uv sync --locked --python 3.14",
            "working-directory distinto": "uv sync --locked --python 3.14",
            "trabajo ausente": "no existe el trabajo",
        }
        exigir_rojo_en_todos(self, comprobar_tc05, casos, "'fronteras'", fragmentos=fragmentos)

    def test_mutantes_tc06_frontend_pierde_un_paso_o_su_orden(self):
        """CA-4 esc. 1 · TC-06 — comentar, mover o reordenar un paso del cliente deja el caso en rojo."""
        casos = {
            "tipos:verificar comentado": comentar(CI_SINTETICO_VALIDO, "frontend", PASO_TIPOS),
            "npm test comentado": comentar(CI_SINTETICO_VALIDO, "frontend", PASO_NPM_TEST),
            "npm test movido a backend": mover(CI_SINTETICO_VALIDO, "frontend", "backend", PASO_NPM_TEST, PASO_MYPY),
            "tipos:verificar movido a fronteras": mover(CI_SINTETICO_VALIDO, "frontend", "fronteras", PASO_TIPOS, PASO_LINT_IMPORTS),
            "uv sync comentado": comentar(CI_SINTETICO_VALIDO, "frontend", PASO_SINCRONIZAR_BACKEND),
            "uv sync después de npm ci": mutar(
                CI_SINTETICO_VALIDO, "frontend", PASO_SINCRONIZAR_BACKEND + PASO_NPM_CI, PASO_NPM_CI + PASO_SINCRONIZAR_BACKEND
            ),
            "typecheck antes que lint": mutar(CI_SINTETICO_VALIDO, "frontend", PASO_LINT + PASO_TYPECHECK, PASO_TYPECHECK + PASO_LINT),
            "uv sync fuera de backend": mutar(
                CI_SINTETICO_VALIDO,
                "frontend",
                PASO_SINCRONIZAR_BACKEND,
                "      - run: uv sync --locked --python 3.14\n",
            ),
            "npm ci sin directorio": mutar(CI_SINTETICO_VALIDO, "frontend", PASO_NPM_CI, "      - run: npm ci\n"),
        }
        fragmentos = {
            "tipos:verificar comentado": "npm run tipos:verificar",
            "npm test comentado": "npm test",
            "npm test movido a backend": "npm test",
            "tipos:verificar movido a fronteras": "npm run tipos:verificar",
            "uv sync comentado": "uv sync --locked --python 3.14",
            "uv sync después de npm ci": "npm ci",
            "typecheck antes que lint": "npm run typecheck",
            "uv sync fuera de backend": "uv sync --locked --python 3.14",
            "npm ci sin directorio": "npm ci",
        }
        exigir_rojo_en_todos(self, comprobar_tc06, casos, "'frontend'", fragmentos=fragmentos)

    def test_mutantes_tc12_contrato_api_y_frontend_pierden_su_cadena(self):
        """CA-9 esc. 1 · TC-12 y pasada adversarial 12 — sin `needs` o sin `!cancelled()` el caso queda en rojo."""
        casos = {
            "contrato-api sin needs": mutar(CI_SINTETICO_VALIDO, "contrato-api", "    needs: backend\n", ""),
            "contrato-api con needs comentado": comentar_linea_de_trabajo(CI_SINTETICO_VALIDO, "contrato-api", "    needs: backend\n"),
            "contrato-api depende de fronteras": mutar(CI_SINTETICO_VALIDO, "contrato-api", "needs: backend", "needs: fronteras"),
            "contrato-api sin if": mutar(CI_SINTETICO_VALIDO, "contrato-api", "    if: ${{ !cancelled() }}\n", ""),
            "contrato-api sin TKT-061": mutar(CI_SINTETICO_VALIDO, "contrato-api", "reservado para TKT-061", "reservado"),
            "contrato-api ausente": sustituir(CI_SINTETICO_VALIDO, "\n  contrato-api:\n", "\n  reservado:\n"),
            "frontend sin needs": mutar(CI_SINTETICO_VALIDO, "frontend", "    needs: contrato-api\n", ""),
            "frontend depende de backend": mutar(CI_SINTETICO_VALIDO, "frontend", "needs: contrato-api", "needs: backend"),
            "frontend sin if": mutar(CI_SINTETICO_VALIDO, "frontend", "    if: ${{ !cancelled() }}\n", ""),
            "if movido a un paso": mutar(
                mutar(CI_SINTETICO_VALIDO, "frontend", "    if: ${{ !cancelled() }}\n", ""),
                "frontend",
                PASO_NPM_CI,
                PASO_NPM_CI + "        if: ${{ !cancelled() }}\n",
            ),
        }
        fragmentos = {
            "contrato-api sin needs": "no declara needs: backend",
            "contrato-api con needs comentado": "no declara needs: backend",
            "contrato-api depende de fronteras": "no declara needs: backend",
            "contrato-api sin if": "le falta `if: ${{ !cancelled() }}` a nivel de trabajo",
            "contrato-api sin TKT-061": "su name: no cita TKT-061",
            "contrato-api ausente": "no existe el trabajo",
            "frontend sin needs": "no declara needs: contrato-api",
            "frontend depende de backend": "no declara needs: contrato-api",
            "frontend sin if": "le falta `if: ${{ !cancelled() }}` a nivel de trabajo",
            "if movido a un paso": "le falta `if: ${{ !cancelled() }}` a nivel de trabajo",
        }
        exigir_rojo_en_todos(self, comprobar_tc12, casos, fragmentos=fragmentos)

    def test_mutantes_tc13_workflow_run_y_needs_a_otro_archivo(self):
        """CA-9 esc. 2 · TC-13 — un disparador `workflow_run` o un `needs` sin trabajo en el archivo dejan el caso en rojo."""
        con_workflow_run = sustituir(CI_SINTETICO_VALIDO, "  pull_request:\n", "  pull_request:\n  workflow_run:\n    workflows: [Revision]\n")
        con_necesidad_ajena = mutar(CI_SINTETICO_VALIDO, "frontend", "needs: contrato-api", "needs: [contrato-api, revision-automatica]")
        for descripcion, texto, fragmento in (
            ("workflow_run", con_workflow_run, "workflow_run"),
            ("needs a un trabajo ausente", con_necesidad_ajena, "revision-automatica"),
        ):
            with self.subTest(mutante=descripcion):
                problemas = comprobar_tc13({"ci.yml": texto})
                self.assertTrue(any(fragmento in problema for problema in problemas), problemas)

    def test_mutantes_tc13_un_workflow_run_comentado_no_cuenta(self):
        """CA-9 esc. 2 · TC-13 — la ausencia del disparador se lee del texto activo, no de los comentarios."""
        con_comentario = sustituir(CI_SINTETICO_VALIDO, "  pull_request:\n", "  pull_request:\n  # workflow_run: no se usa, ver CA-9\n")
        self.assertEqual(comprobar_tc13({"ci.yml": con_comentario}), [])

    def test_mutantes_tc13_revisa_todos_los_archivos_dados(self):
        """CA-9 esc. 2 · TC-13 — el `workflow_run` de otro workflow también cuenta y se nombra el archivo."""
        otro = "name: Otro\non:\n  workflow_run:\n    workflows: [CI]\njobs:\n  x:\n    runs-on: ubuntu-24.04\n    steps: []\n"
        problemas = comprobar_tc13({"ci.yml": CI_SINTETICO_VALIDO, "otro.yml": otro})
        self.assertEqual(len(problemas), 1)
        self.assertIn("otro.yml", problemas[0])

    def test_mutantes_r1a_sqlite_y_create_all_en_rojo_y_el_comentario_no(self):
        """CA-R1 esc. 1 · TC-R1a — `sqlite` o `create_all` activos fallan, aunque cambie la capitalización; en un comentario, no."""
        for descripcion, texto, esperado in (
            ("sqlite", mutar(CI_SINTETICO_VALIDO, "backend", "      - run: uv run mypy .\n", "      - run: SQLITE_URL=x uv run mypy .\n"), "sqlite"),
            ("create_all", mutar(CI_SINTETICO_VALIDO, "backend", PASO_MYPY, "      - run: python -c 'Base.metadata.create_all(e)'\n"), "create_all"),
        ):
            with self.subTest(mutante=descripcion):
                problemas = comprobar_r1a(texto)
                self.assertEqual(len(problemas), 1, problemas)
                self.assertIn(esperado, problemas[0])
        con_comentario = sustituir(CI_SINTETICO_VALIDO, "name: CI\n", "name: CI\n# Sin SQLite ni create_all: ver CA-R1\n")
        self.assertEqual(comprobar_r1a(con_comentario), [])

    def test_mutantes_regla_comun_1_corredor_y_tiempo(self):
        """Regla común 1 — otro corredor, sin tiempo máximo o con uno distinto del fijado dejan el caso en rojo."""
        casos = {
            "backend en ubuntu-latest": mutar(CI_SINTETICO_VALIDO, "backend", "ubuntu-24.04", "ubuntu-latest"),
            "frontend sin timeout": mutar(CI_SINTETICO_VALIDO, "frontend", "    timeout-minutes: 15\n", ""),
            "backend con 15 minutos": mutar(CI_SINTETICO_VALIDO, "backend", "timeout-minutes: 25", "timeout-minutes: 15"),
            "fronteras con 60 minutos": mutar(CI_SINTETICO_VALIDO, "fronteras", "timeout-minutes: 15", "timeout-minutes: 60"),
        }
        fragmentos = {
            "backend en ubuntu-latest": "runs-on",
            "frontend sin timeout": "timeout-minutes",
            "backend con 15 minutos": "timeout-minutes",
            "fronteras con 60 minutos": "timeout-minutes",
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_1, casos, fragmentos=fragmentos)


def comentar_linea_de_trabajo(texto: str, id_trabajo: str, linea: str) -> str:
    """Comenta una línea de nivel de trabajo (no de paso), conservando su sangría."""
    return mutar(texto, id_trabajo, linea, "    # " + linea.strip() + "\n")


# Fila A3 · trabajo `humo`. Texto aparte para no alterar la base de los mutantes de la fila A2.
HUMO_SINTETICO = """\
  humo:
    name: Humo · Playwright con base migrada
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@abc # v6
      - uses: astral-sh/setup-uv@abc # v10
      - uses: actions/setup-node@abc # v7
      - run: cp .env.example .env
      - run: docker compose up -d --wait db
      - run: uv sync --locked --python 3.14
        working-directory: backend
      - run: uv run --env-file ../.env alembic upgrade head
        working-directory: backend
      - run: uv run --env-file ../.env python -m herramientas.contrasenas_roles
        working-directory: backend
      - run: npm ci
        working-directory: frontend
      - run: npx playwright install --with-deps chromium
        working-directory: frontend
      - run: npm run e2e -- --reporter=list,html
        working-directory: frontend
      - uses: actions/upload-artifact@abc # v7
        if: failure()
        with:
          name: humo-playwright
          path: |
            frontend/playwright-report/
            frontend/test-results/
"""

CI_CON_HUMO = CI_SINTETICO_VALIDO + HUMO_SINTETICO

PASO_CP_ENV = "      - run: cp .env.example .env\n"
PASO_COMPOSE = "      - run: docker compose up -d --wait db\n"
PASO_ALEMBIC = "      - run: uv run --env-file ../.env alembic upgrade head\n        working-directory: backend\n"
PASO_CONTRASENAS = "      - run: uv run --env-file ../.env python -m herramientas.contrasenas_roles\n        working-directory: backend\n"
PASO_PLAYWRIGHT = "      - run: npx playwright install --with-deps chromium\n        working-directory: frontend\n"
PASO_E2E = "      - run: npm run e2e -- --reporter=list,html\n        working-directory: frontend\n"
PASO_SUBIDA_HUMO = (
    "      - uses: actions/upload-artifact@abc # v7\n"
    "        if: failure()\n"
    "        with:\n"
    "          name: humo-playwright\n"
    "          path: |\n"
    "            frontend/playwright-report/\n"
    "            frontend/test-results/\n"
)


class PruebasDeMutantesDelHumo(unittest.TestCase):
    """Fila A3 · TC-08: cada compuerta del trabajo `humo` se pone en rojo si se comenta, se mueve, se reordena o se desvía."""

    def test_humo_mutantes_el_texto_valido_pasa_todas_las_comprobaciones(self):
        """Control — con el trabajo `humo` añadido, ninguna comprobación existente ni TC-08 falla."""
        trabajos = extraer_trabajos(CI_CON_HUMO)
        self.assertIn("humo", trabajos)
        for comprobacion in COMPROBACIONES_DE_TRABAJO + (comprobar_tc08,):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])
        self.assertEqual(comprobar_tc13({"ci.yml": CI_CON_HUMO}), [])
        self.assertEqual(comprobar_r1a(CI_CON_HUMO), [])

    def test_humo_mutantes_tc08_pierde_un_paso_su_orden_o_su_directorio(self):
        """CA-5 esc. 1 · TC-08 — comentar, mover, reordenar o desviar de directorio un paso deja el caso en rojo."""
        base = CI_CON_HUMO
        casos = {
            "trabajo humo ausente": sustituir(base, "\n  humo:\n", "\n  recorrido:\n"),
            "cp .env.example comentado": comentar(base, "humo", PASO_CP_ENV),
            "cp .env.example movido a backend": mover(base, "humo", "backend", PASO_CP_ENV, "      - run: uv run mypy .\n"),
            "cp .env.example después de compose": mutar(base, "humo", PASO_CP_ENV + PASO_COMPOSE, PASO_COMPOSE + PASO_CP_ENV),
            "cp con directorio por omisión backend": mutar(
                base, "humo", "    steps:\n      - uses: actions/checkout@abc # v6\n      - uses: astral-sh/setup-uv@abc # v10\n      - uses: actions/setup-node",
                "    defaults:\n      run:\n        working-directory: backend\n    steps:\n      - uses: actions/checkout@abc # v6\n      - uses: astral-sh/setup-uv@abc # v10\n      - uses: actions/setup-node",
            ),
            "compose comentado": comentar(base, "humo", PASO_COMPOSE),
            "compose sin --wait": mutar(base, "humo", "docker compose up -d --wait db", "docker compose up -d db"),
            "compose levanta otro servicio": mutar(base, "humo", "docker compose up -d --wait db", "docker compose up -d --wait minio"),
            "uv sync comentado": comentar(base, "humo", PASO_SINCRONIZAR_BACKEND),
            "uv sync sin --locked": mutar(base, "humo", "uv sync --locked --python 3.14", "uv sync --python 3.14"),
            "uv sync fuera de backend": mutar(base, "humo", PASO_SINCRONIZAR_BACKEND, "      - run: uv sync --locked --python 3.14\n"),
            "alembic comentado": comentar(base, "humo", PASO_ALEMBIC),
            "alembic sin --env-file": mutar(base, "humo", "uv run --env-file ../.env alembic upgrade head", "uv run alembic upgrade head"),
            "alembic movido a backend": mover(base, "humo", "backend", PASO_ALEMBIC, "      - run: uv run mypy .\n"),
            "alembic fuera de backend": mutar(
                base, "humo", PASO_ALEMBIC, "      - run: uv run --env-file ../.env alembic upgrade head\n"
            ),
            "contrasenas comentado": comentar(base, "humo", PASO_CONTRASENAS),
            "contrasenas antes de alembic": mutar(base, "humo", PASO_ALEMBIC + PASO_CONTRASENAS, PASO_CONTRASENAS + PASO_ALEMBIC),
            "contrasenas sin --env-file": mutar(
                base, "humo", "uv run --env-file ../.env python -m herramientas.contrasenas_roles", "uv run python -m herramientas.contrasenas_roles"
            ),
            "npm ci comentado": comentar(base, "humo", "      - run: npm ci\n        working-directory: frontend\n"),
            "npm ci sin directorio": mutar(
                base, "humo", "      - run: npm ci\n        working-directory: frontend\n", "      - run: npm ci\n"
            ),
            "playwright install comentado": comentar(base, "humo", PASO_PLAYWRIGHT),
            "playwright install sin --with-deps": mutar(
                base, "humo", "npx playwright install --with-deps chromium", "npx playwright install chromium"
            ),
            "playwright install después del e2e": mutar(base, "humo", PASO_PLAYWRIGHT + PASO_E2E, PASO_E2E + PASO_PLAYWRIGHT),
            "e2e comentado": comentar(base, "humo", PASO_E2E),
            "e2e sin reporter html": mutar(base, "humo", "npm run e2e -- --reporter=list,html", "npm run e2e"),
            "e2e solo con reporter list": mutar(base, "humo", "npm run e2e -- --reporter=list,html", "npm run e2e -- --reporter=list"),
            "e2e sin directorio": mutar(base, "humo", PASO_E2E, "      - run: npm run e2e -- --reporter=list,html\n"),
            "e2e movido a frontend": mover(base, "humo", "frontend", PASO_E2E, "      - run: npm run tipos:verificar\n        working-directory: frontend\n"),
            "el comando solo en un name": mutar(base, "humo", PASO_E2E, "      - name: npm run e2e -- --reporter=list,html\n        run: echo omitido\n"),
        }
        fragmentos = {
            "trabajo humo ausente": "no existe el trabajo",
            "cp .env.example comentado": "cp .env.example .env",
            "cp .env.example movido a backend": "cp .env.example .env",
            "cp .env.example después de compose": "docker compose up -d --wait db",
            "cp con directorio por omisión backend": "cp .env.example .env",
            "compose comentado": "docker compose up -d --wait db",
            "compose sin --wait": "docker compose up -d --wait db",
            "compose levanta otro servicio": "docker compose up -d --wait db",
            "uv sync comentado": "uv sync --locked --python 3.14",
            "uv sync sin --locked": "uv sync --locked --python 3.14",
            "uv sync fuera de backend": "uv sync --locked --python 3.14",
            "alembic comentado": "alembic upgrade head",
            "alembic sin --env-file": "alembic upgrade head",
            "alembic movido a backend": "alembic upgrade head",
            "alembic fuera de backend": "alembic upgrade head",
            "contrasenas comentado": "herramientas.contrasenas_roles",
            "contrasenas antes de alembic": "herramientas.contrasenas_roles",
            "contrasenas sin --env-file": "herramientas.contrasenas_roles",
            "npm ci comentado": "npm ci",
            "npm ci sin directorio": "npm ci",
            "playwright install comentado": "npx playwright install --with-deps chromium",
            "playwright install sin --with-deps": "npx playwright install --with-deps chromium",
            "playwright install después del e2e": "npm run e2e -- --reporter=list,html",
            "e2e comentado": "npm run e2e -- --reporter=list,html",
            "e2e sin reporter html": "npm run e2e -- --reporter=list,html",
            "e2e solo con reporter list": "npm run e2e -- --reporter=list,html",
            "e2e sin directorio": "npm run e2e -- --reporter=list,html",
            "e2e movido a frontend": "npm run e2e -- --reporter=list,html",
            "el comando solo en un name": "npm run e2e -- --reporter=list,html",
        }
        exigir_rojo_en_todos(self, comprobar_tc08, casos, "'humo'", fragmentos=fragmentos)

    def test_humo_mutantes_tc08_el_informe_sube_si_falla_con_su_nombre_y_sus_carpetas(self):
        """CA-5 esc. 2 · TC-08 — sin `if: failure()`, con otro nombre, otra carpeta o antes del e2e, el informe no llega."""
        base = CI_CON_HUMO
        casos = {
            "upload-artifact comentado": comentar(base, "humo", PASO_SUBIDA_HUMO),
            "upload-artifact sin if": mutar(base, "humo", "        if: failure()\n", ""),
            "if: always() en lugar de failure()": mutar(base, "humo", "if: failure()", "if: always()"),
            "if: success()": mutar(base, "humo", "if: failure()", "if: success()"),
            "if comentado": mutar(base, "humo", "        if: failure()\n", "        # if: failure()\n"),
            "if movido al trabajo": mutar(
                mutar(base, "humo", "        if: failure()\n", ""),
                "humo",
                "    timeout-minutes: 20\n",
                "    timeout-minutes: 20\n    if: failure()\n",
            ),
            "otro nombre de artefacto": mutar(base, "humo", "name: humo-playwright", "name: informe"),
            "sin playwright-report": mutar(base, "humo", "            frontend/playwright-report/\n", ""),
            "sin test-results": mutar(base, "humo", "            frontend/test-results/\n", ""),
            "playwright-report fuera de frontend": mutar(
                base, "humo", "            frontend/playwright-report/\n", "            playwright-report/\n"
            ),
            "upload-artifact antes del e2e": mutar(base, "humo", PASO_E2E + PASO_SUBIDA_HUMO, PASO_SUBIDA_HUMO + PASO_E2E),
            "upload-artifact movido a backend": mover(base, "humo", "backend", PASO_SUBIDA_HUMO, "      - run: uv run mypy .\n"),
        }
        fragmentos = {
            "upload-artifact comentado": "falta, después de npm run e2e, un actions/upload-artifact con `name: humo-playwright`",
            "upload-artifact sin if": "el paso upload-artifact no declara `if: failure()`",
            "if: always() en lugar de failure()": "el paso upload-artifact no declara `if: failure()`",
            "if: success()": "el paso upload-artifact no declara `if: failure()`",
            "if comentado": "el paso upload-artifact no declara `if: failure()`",
            "if movido al trabajo": "el paso upload-artifact no declara `if: failure()`",
            "otro nombre de artefacto": "falta, después de npm run e2e, un actions/upload-artifact con `name: humo-playwright`",
            "sin playwright-report": "el artefacto humo-playwright no incluye frontend/playwright-report/",
            "sin test-results": "el artefacto humo-playwright no incluye frontend/test-results/",
            "playwright-report fuera de frontend": "el artefacto humo-playwright no incluye frontend/playwright-report/",
            "upload-artifact antes del e2e": "falta, después de npm run e2e, un actions/upload-artifact con `name: humo-playwright`",
            "upload-artifact movido a backend": "falta, después de npm run e2e, un actions/upload-artifact con `name: humo-playwright`",
        }
        exigir_rojo_en_todos(self, comprobar_tc08, casos, "'humo'", fragmentos=fragmentos)

    def test_humo_mutantes_regla_comun_1_el_humo_tiene_20_minutos_y_corredor_fijo(self):
        """Regla común 1 — el trabajo `humo` con otro corredor, sin tiempo máximo o con uno distinto de 20 minutos queda en rojo."""
        casos = {
            "humo en ubuntu-latest": mutar(CI_CON_HUMO, "humo", "ubuntu-24.04", "ubuntu-latest"),
            "humo sin timeout": mutar(CI_CON_HUMO, "humo", "    timeout-minutes: 20\n", ""),
            "humo con 15 minutos": mutar(CI_CON_HUMO, "humo", "timeout-minutes: 20", "timeout-minutes: 15"),
            "humo con 25 minutos": mutar(CI_CON_HUMO, "humo", "timeout-minutes: 20", "timeout-minutes: 25"),
        }
        fragmentos = {
            "humo en ubuntu-latest": "runs-on",
            "humo sin timeout": "timeout-minutes",
            "humo con 15 minutos": "timeout-minutes",
            "humo con 25 minutos": "timeout-minutes",
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_1, casos, "'humo'", fragmentos=fragmentos)


# ---------------------------------------------------------------------------------------------------------
# Los casos sobre el archivo real
# ---------------------------------------------------------------------------------------------------------


def _leer_flujos(caso: unittest.TestCase) -> dict[str, str]:
    """Nombre de archivo -> texto de cada workflow. Sin `ci.yml` el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(CI):
        caso.fail(f"No existe {os.path.relpath(CI, RAIZ)}: el pipeline de TKT-009a todavía no está definido")
    flujos = {}
    for ruta in sorted(glob.glob(os.path.join(DIRECTORIO_DE_FLUJOS, "*.y*ml"))):
        with open(ruta, encoding="utf-8") as archivo:
            flujos[os.path.basename(ruta)] = archivo.read()
    return flujos


def _trabajos_de_ci(caso: unittest.TestCase) -> dict[str, list[str]]:
    """Los trabajos de `ci.yml` (los de su `jobs:`), sin comentarios."""
    return extraer_trabajos(_leer_flujos(caso)["ci.yml"])


class DefinicionDeCI(unittest.TestCase):
    """Casos estáticos de las filas A2 y A3 sobre `.github/workflows/ci.yml`. Sin el archivo, fallan; no se saltan."""

    def test_tc01_backend_ejecuta_formato_lint_tipos_float_pruebas_y_sube_el_informe(self):
        """CA-1 esc. 1 · TC-01 — `backend`, en orden: sync, ruff format --check, ruff check, mypy, verificar_float, pytest con --cov y --junitxml, y upload-artifact con if: always()."""
        self.assertEqual(comprobar_tc01(_trabajos_de_ci(self)), [])

    def test_tc05_fronteras_ejecuta_lint_imports_desde_backend(self):
        """CA-3 esc. 1 · TC-05 — `fronteras` ejecuta `uv run lint-imports` con working-directory: backend."""
        self.assertEqual(comprobar_tc05(_trabajos_de_ci(self)), [])

    def test_tc06_frontend_sincroniza_backend_antes_de_npm_ci_y_corre_los_cuatro_scripts_en_orden(self):
        """CA-4 esc. 1 · TC-06 — `frontend`: uv sync en backend/, luego npm ci, lint, typecheck, test y tipos:verificar en frontend/."""
        self.assertEqual(comprobar_tc06(_trabajos_de_ci(self)), [])

    def test_tc08_humo_construye_el_entorno_corre_el_recorrido_y_sube_el_informe_si_falla(self):
        """CA-5 esc. 1 · TC-08 — `humo`: cp .env.example, compose --wait db, sync, alembic, contraseñas, npm ci, playwright install, e2e con reporter html y upload-artifact `humo-playwright` con if: failure()."""
        self.assertEqual(comprobar_tc08(_trabajos_de_ci(self)), [])

    def test_tc12_contrato_api_reservado_entre_backend_y_frontend_sin_cancelarse(self):
        """CA-9 esc. 1 · TC-12 — `contrato-api` cita TKT-061 y espera a backend; `frontend` espera a `contrato-api`; ambos con `if: ${{ !cancelled() }}`."""
        self.assertEqual(comprobar_tc12(_trabajos_de_ci(self)), [])

    def test_tc13_ningun_workflow_usa_workflow_run_y_todo_needs_apunta_a_su_archivo(self):
        """CA-9 esc. 2 · TC-13 (rechazo estático) — el pipeline no espera ni invoca la revisión automatizada de TKT-062."""
        self.assertEqual(comprobar_tc13(_leer_flujos(self)), [])

    def test_tcr1a_ci_no_usa_sqlite_ni_create_all(self):
        """CA-R1 esc. 1 · TC-R1a — el trabajo de backend no toma atajos: ni SQLite ni `create_all()`."""
        self.assertEqual(comprobar_r1a(_leer_flujos(self)["ci.yml"]), [])

    def test_regla_comun_1_todos_los_trabajos_en_ubuntu_24_04_con_tiempo_maximo(self):
        """Regla común 1 del diseño — `runs-on: ubuntu-24.04` y `timeout-minutes` (backend 25, humo 20, el resto 15)."""
        self.assertEqual(comprobar_regla_comun_1(_trabajos_de_ci(self)), [])


# =========================================================================================================
# Fila A4 · trabajos `herramientas`, `workflows` y `documentacion` (solo verificar_docs.py)
# TC-23, TC-21, TC-22, TC-R4b y las reglas comunes 8 y 9. Siguen las reglas comunes 6 y 7 y el pytest completo,
# añadidas en el ciclo de corrección 1; las secciones de arriba son las filas A2 y A3.
# =========================================================================================================

UNITTEST_DE_TOOLS = r"\bpython3? -m unittest discover -s tools/tests(?![\w/.-])"
GUARDA_DE_SALTOS = r"""!\s+grep\s+-q\s+["']skipped=["']"""
ZIZMOR = r"\buvx zizmor@\d+\.\d+\.\d+ --offline \.github/workflows(?![\w/.-])"
VERIFICAR_DOCS = r"\bpython3 tools/verificar_docs\.py(?![\w.])"


def _indice_de_uses(lista_de_pasos: list[list[str]], prefijo: str) -> int | None:
    """Índice del primer paso cuyo `uses:` empieza por `prefijo`."""
    for i, paso in enumerate(lista_de_pasos):
        if (valor_del_paso(paso, "uses") or "").startswith(prefijo):
            return i
    return None


def _sin_comillas(texto: str) -> str:
    return texto.replace('"', "").replace("'", "")


def _en_la_raiz(bloque: list[str], paso: list[str]) -> bool:
    return directorio_del_paso(bloque, paso) in (None, ".")


def comprobar_tc23(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-R4 esc. 2 · TC-23. La suite de `tools/` corre con `uv` instalado, la tubería a `tee` no esconde un fallo (`shell: bash`)
    y la guarda de `skipped=` falla el trabajo si algún test se salta."""
    if "herramientas" not in trabajos:
        return ["no existe el trabajo 'herramientas'"]
    bloque = trabajos["herramientas"]
    lista = pasos(bloque)
    problemas = comprobar_regla_comun_1({"herramientas": bloque})
    previos, i_checkout, i_uv = _comprobar_checkout_y_uv(
        "herramientas", lista, True, "; sin `uv` un test de tools/ se salta en lugar de correr (CA-R4 esc. 2)"
    )
    problemas += previos
    if i_checkout is not None and not re.search(
        r"^fetch-depth:\s*[\"']?0[\"']?\s*$", valor_del_paso(lista[i_checkout], "with") or "", flags=re.MULTILINE
    ):
        problemas.append("'herramientas': el checkout debe declarar `fetch-depth: 0` (la parte c compara con la base del PR)")
    secuencia, posiciones = comprobar_secuencia(
        "herramientas",
        trabajos,
        [
            ("uv sync --locked --python 3.14", UV_SYNC, "backend"),
            ("unittest discover -s tools/tests", UNITTEST_DE_TOOLS, None),
            ("guarda ! grep -q \"skipped=\"", GUARDA_DE_SALTOS, None),
        ],
    )
    problemas += secuencia
    sincronizacion = posiciones.get("uv sync --locked --python 3.14")
    if i_uv is not None and sincronizacion is not None and sincronizacion[0] < i_uv:
        problemas.append("'herramientas': uv sync va antes de setup-uv")
    pruebas = posiciones.get("unittest discover -s tools/tests")
    if pruebas is not None:
        paso = lista[pruebas[0]]
        if not _en_la_raiz(bloque, paso):
            problemas.append("'herramientas': unittest discover -s tools/tests se ejecuta desde la raíz del repositorio, no desde otro directorio")
        if (valor_del_paso(paso, "shell") or "").strip("\"'") != "bash":
            problemas.append(
                "'herramientas': el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`; sin él no hay pipefail "
                "y el estado del paso es el de `tee`, siempre 0"
            )
        destino = re.search(r"2>&1\s*\|\s*tee\s+(?:-a\s+)?(\S+)", comando(paso))
        if destino is None:
            problemas.append("'herramientas': el paso de la suite de tools/ debe terminar en `2>&1 | tee <archivo>` (unittest escribe en stderr)")
        else:
            guarda = posiciones.get('guarda ! grep -q "skipped="')
            if guarda is not None and _sin_comillas(destino.group(1)) not in _sin_comillas(comando(lista[guarda[0]])):
                problemas.append(f"'herramientas': la guarda de skipped= no lee el archivo que escribe tee ({destino.group(1)})")
    return problemas


def patron_de_la_guarda(trabajos: dict[str, list[str]]) -> str | None:
    """La cadena que busca la guarda de `herramientas` (`skipped=`), o None si el trabajo no la tiene."""
    if "herramientas" not in trabajos:
        return None
    for paso in pasos(trabajos["herramientas"]):
        encontrada = re.search(r"""!\s+grep\s+-q\s+["']([^"']+)["']""", comando(paso))
        if encontrada:
            return encontrada.group(1)
    return None


def _comprobar_checkout_y_uv(
    id_trabajo: str, lista: list[list[str]], con_setup_uv: bool, motivo_de_uv: str = ""
) -> tuple[list[str], int | None, int | None]:
    """Hay `actions/checkout` y, si el trabajo usa `uv`, `astral-sh/setup-uv` después de él. Devuelve los problemas y los índices de ambos pasos."""
    problemas = []
    i_checkout = _indice_de_uses(lista, "actions/checkout@")
    if i_checkout is None:
        problemas.append(f"'{id_trabajo}': falta actions/checkout")
    i_uv = _indice_de_uses(lista, "astral-sh/setup-uv@")
    if con_setup_uv:
        if i_uv is None:
            problemas.append(f"'{id_trabajo}': falta astral-sh/setup-uv{motivo_de_uv}")
        elif i_checkout is not None and i_checkout > i_uv:
            problemas.append(f"'{id_trabajo}': el checkout debe ir antes de setup-uv")
    return problemas, i_checkout, i_uv


def _comprobar_trabajo_con_checkout(
    id_trabajo: str,
    trabajos: dict[str, list[str]],
    con_setup_uv: bool,
    etiqueta: str,
    patron: str,
) -> list[str]:
    if id_trabajo not in trabajos:
        return [f"no existe el trabajo '{id_trabajo}'"]
    bloque = trabajos[id_trabajo]
    lista = pasos(bloque)
    problemas = comprobar_regla_comun_1({id_trabajo: bloque})
    previos, i_checkout, i_uv = _comprobar_checkout_y_uv(id_trabajo, lista, con_setup_uv)
    problemas += previos
    secuencia, posiciones = comprobar_secuencia(id_trabajo, trabajos, [(etiqueta, patron, None)])
    problemas += secuencia
    posicion = posiciones.get(etiqueta)
    if posicion is not None:
        if not _en_la_raiz(bloque, lista[posicion[0]]):
            problemas.append(f"'{id_trabajo}': «{etiqueta}» se ejecuta desde la raíz del repositorio")
        if i_checkout is not None and posicion[0] < i_checkout:
            problemas.append(f"'{id_trabajo}': «{etiqueta}» va antes del checkout")
        if con_setup_uv and i_uv is not None and posicion[0] < i_uv:
            problemas.append(f"'{id_trabajo}': «{etiqueta}» va antes de setup-uv")
    return problemas


def comprobar_trabajo_workflows(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-12 esc. 3 (soporte de TC-20 y TC-24) · checkout, setup-uv y `uvx zizmor@<versión exacta> --offline .github/workflows`."""
    return _comprobar_trabajo_con_checkout(
        "workflows", trabajos, True, "uvx zizmor@<versión> --offline .github/workflows", ZIZMOR
    )


def comprobar_trabajo_documentacion(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-13 (parte a) · checkout y `python3 tools/verificar_docs.py`. La parte d añade las demás herramientas."""
    return _comprobar_trabajo_con_checkout(
        "documentacion", trabajos, False, "python3 tools/verificar_docs.py", VERIFICAR_DOCS
    )


def _orden_sin_cadenas(orden: str) -> str:
    """La orden sin las comillas de YAML que la envuelven y con el contenido de sus cadenas vaciado: lo que hay entre comillas no es sintaxis de shell."""
    texto = orden.strip()
    if len(texto) >= 2 and texto[0] in "\"'" and texto[-1] == texto[0] and "\n" not in texto:
        texto = texto[1:-1]
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', texto)


def _tiene_tuberia(orden: str) -> bool:
    """Hay un `|` que no es `||` fuera de comillas. Una orden entre comillas de YAML se desenvuelve antes."""
    return re.search(r"(?<!\|)\|(?!\|)", _orden_sin_cadenas(orden)) is not None


def comprobar_regla_comun_9(trabajos: dict[str, list[str]]) -> list[str]:
    """Regla común 9: todo paso con una tubería declara `shell: bash` (pipefail)."""
    problemas = []
    for id_trabajo, bloque in trabajos.items():
        for paso in pasos(bloque):
            if _tiene_tuberia(comando(paso)) and (valor_del_paso(paso, "shell") or "").strip("\"'") != "bash":
                resumen = comando(paso).strip().splitlines()[0]
                problemas.append(f"'{id_trabajo}': el paso `{resumen}` usa una tubería sin `shell: bash`")
    return problemas


def comprobar_regla_comun_8(trabajos: dict[str, list[str]]) -> list[str]:
    """Regla común 8: ningún `run:` interpola `${{ }}`; los valores de GitHub entran por `env:`."""
    problemas = []
    for id_trabajo, bloque in trabajos.items():
        for paso in pasos(bloque):
            if "${{" in comando(paso):
                resumen = comando(paso).strip().splitlines()[0]
                problemas.append(f"'{id_trabajo}': el paso `{resumen}` interpola ${{{{ }}}} dentro de run: (inyección de plantillas)")
    return problemas


# `if:` que no apaga un paso: correr siempre, correr salvo cancelación o correr solo tras un fallo.
IF_QUE_NO_APAGA = ("${{!cancelled()}}", "!cancelled()", "${{always()}}", "always()", "${{failure()}}", "failure()")
IF_DE_LAS_COMPUERTAS = ("${{!cancelled()}}", "!cancelled()")
ENMASCARA_EL_FALLO = re.compile(r"\|\|\s*(?:true\b|:(?!\w)|exit\s+0\b)")
ES_COMPROBACION = re.compile(r"\b(?:uv run|npm run|npm test|python3 tools/verificar_docs\.py)(?![\w.])")
ENCUENTRA_PYTEST = re.compile(r"(?:^|[\s;&|])pytest(?![\w.:/-])")
FIN_DE_LA_ORDEN = re.compile(r"\n|&&|\|\||;|\|")
OPCION_DE_INFORME = re.compile(r"--cov(?:=\S*)?|--cov-report=\S+|--junitxml=\S+|-q+|-v+|-ra|--tb=\w+")


def _expresion_de_if(valor: str | None) -> str:
    """El `if:` sin espacios ni comillas, para compararlo."""
    return _normalizada((valor or "").strip().strip("\"'"))


def _primera_linea(orden: str, alternativa: str) -> str:
    lineas = orden.strip().splitlines()
    return lineas[0].strip() if lineas else alternativa


def _nombre_del_paso(paso: list[str]) -> str:
    return valor_del_paso(paso, "name") or _primera_linea(comando(paso), valor_del_paso(paso, "uses") or "(sin nombre)")


def comprobar_regla_comun_7(trabajos: dict[str, list[str]]) -> list[str]:
    """Regla común 7: ninguna compuerta se desactiva sin quitarla. Se rechaza `continue-on-error` (de trabajo o de paso, con
    cualquier valor), un `if:` distinto de `!cancelled()`, `always()` o `failure()`, y un `|| true` / `|| :` / `|| exit 0` en un `run:`."""
    problemas = []
    for id_trabajo, bloque in trabajos.items():
        columna = _columna_del_trabajo(bloque)
        for linea in bloque:
            if re.match(r"\s*(?:-\s+)?[\"']?continue-on-error[\"']?\s*:", linea):
                es_del_trabajo = _sangria(linea) == columna and not linea.lstrip().startswith("- ")
                nivel = "a nivel de trabajo" if es_del_trabajo else "en un paso"
                problemas.append(
                    f"'{id_trabajo}': declara `continue-on-error` {nivel}; un fallo de la compuerta no pondría el trabajo en rojo"
                )
        del_trabajo = valor_del_trabajo(bloque, "if")
        if del_trabajo is not None and _expresion_de_if(del_trabajo) not in IF_QUE_NO_APAGA:
            problemas.append(f"'{id_trabajo}': el `if:` a nivel de trabajo es `{del_trabajo}` y puede apagar el trabajo entero")
        for paso in pasos(bloque):
            condicion = valor_del_paso(paso, "if")
            if condicion is not None and _expresion_de_if(condicion) not in IF_QUE_NO_APAGA:
                problemas.append(
                    f"'{id_trabajo}': el paso `{_nombre_del_paso(paso)}` tiene `if: {condicion}`, que puede apagarlo; "
                    "solo se admite `!cancelled()`, `always()` o `failure()`"
                )
            if ENMASCARA_EL_FALLO.search(_orden_sin_cadenas(comando(paso))):
                problemas.append(
                    f"'{id_trabajo}': el paso `{_nombre_del_paso(paso)}` enmascara su fallo con `|| true` (o `|| :`, `|| exit 0`)"
                )
    return problemas


def comprobar_regla_comun_6(trabajos: dict[str, list[str]]) -> list[str]:
    """Regla común 6: en `backend`, `frontend` y `documentacion`, todo paso de comprobación (`uv run ...`, `npm run ...`,
    `npm test`, `python3 tools/verificar_docs.py`; no la sincronización ni la instalación) declara `if: ${{ !cancelled() }}`,
    para que un fallo no oculte los que vienen detrás. Los tres trabajos son obligatorios y `documentacion` debe tener al
    menos un paso de comprobación."""
    problemas = []
    for id_trabajo in ("backend", "frontend", "documentacion"):
        if id_trabajo not in trabajos:
            problemas.append(f"no existe el trabajo '{id_trabajo}'")
            continue
        comprobaciones = 0
        for paso in pasos(trabajos[id_trabajo]):
            orden = comando(paso)
            if not ES_COMPROBACION.search(orden):
                continue
            comprobaciones += 1
            if _expresion_de_if(valor_del_paso(paso, "if")) not in IF_DE_LAS_COMPUERTAS:
                problemas.append(
                    f"'{id_trabajo}': el paso de comprobación `{_primera_linea(orden, '')}` no declara `if: ${{{{ !cancelled() }}}}`; "
                    "tras un fallo anterior no correría y se vería solo el primer fallo"
                )
        if id_trabajo == "documentacion" and comprobaciones == 0:
            problemas.append(f"'{id_trabajo}': no tiene ningún paso de comprobación (`python3 tools/verificar_docs.py`)")
    return problemas


def _argumentos_de_pytest(orden: str) -> list[list[str]]:
    """Los argumentos de cada invocación de `pytest` en la orden, con las continuaciones de línea unidas."""
    unida = orden.replace("\\\n", " ")
    invocaciones = []
    for encontrada in ENCUENTRA_PYTEST.finditer(unida):
        resto = FIN_DE_LA_ORDEN.split(unida[encontrada.end() :], maxsplit=1)[0]
        try:
            invocaciones.append(shlex.split(resto))
        except ValueError:
            invocaciones.append(resto.split())
    return invocaciones


def comprobar_pytest_sin_filtros(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-1 esc. 1: el pytest de `backend` es el comando completo del diseño. Ningún `pytest` del pipeline lleva `-k`, `-m`,
    `--deselect`, `--ignore`, una ruta ni nada que no sea informe (`--cov`, `--cov-report`, `--junitxml`, `-q`, `-v`, `-ra`, `--tb`)."""
    if "backend" not in trabajos:
        return ["no existe el trabajo 'backend'"]
    problemas = []
    for id_trabajo, bloque in trabajos.items():
        hay_pytest = False
        for paso in pasos(bloque):
            for argumentos in _argumentos_de_pytest(comando(paso)):
                hay_pytest = True
                for argumento in argumentos:
                    if not OPCION_DE_INFORME.fullmatch(argumento):
                        problemas.append(
                            f"'{id_trabajo}': pytest lleva `{argumento}`, que selecciona, excluye o cambia las pruebas; "
                            "la orden del diseño es el comando completo, solo con opciones de informe"
                        )
        if id_trabajo == "backend" and not hay_pytest:
            problemas.append("'backend': no hay ninguna orden de pytest en un run: del trabajo")
    return problemas


def _permisos_de_flujo(texto: str) -> list[str] | None:
    """Líneas del bloque `permissions:` de primer nivel, o None si no hay bloque."""
    lineas = sin_comentarios(texto).splitlines()
    for k, linea in enumerate(lineas):
        if re.fullmatch(r"permissions:\s*", linea):
            cuerpo = []
            for siguiente in lineas[k + 1 :]:
                if _sangria(siguiente) == 0:
                    break
                cuerpo.append(siguiente.strip())
            return cuerpo
    return None


def _texto_de_comentario(fragmento: str) -> bool:
    return fragmento.startswith("#") and fragmento.lstrip("#").strip() != ""


def comprobar_tc21(flujos: dict[str, str]) -> list[str]:
    """CA-12 esc. 1 y 3 · TC-21. `flujos` es nombre de archivo -> texto."""
    if not flujos:
        return ["no hay ningún workflow en .github/workflows/"]
    problemas = []
    for nombre, texto in flujos.items():
        cuerpo = _permisos_de_flujo(texto)
        if cuerpo is None:
            problemas.append(f"{nombre}: no declara `permissions:` a nivel de flujo; el token heredaría los permisos por omisión")
        elif not any(re.fullmatch(r"contents:\s*read", linea) for linea in cuerpo):
            problemas.append(f"{nombre}: `permissions:` a nivel de flujo no declara `contents: read`")
        lineas = texto.splitlines()
        for numero, linea in enumerate(lineas, 1):
            activa = _quitar_comentario(linea)
            if not re.search(r":\s*[\"']?write\b", activa):
                continue
            previa = lineas[numero - 2].strip() if numero >= 2 else ""
            if not (_texto_de_comentario(linea[len(activa) :].strip()) or _texto_de_comentario(previa)):
                problemas.append(f"{nombre}:{numero}: `{activa.strip()}` amplía el permiso sin un comentario que lo justifique")
    return problemas


def _disparadores(texto: str) -> str:
    """Texto del bloque `on:` de primer nivel, sin comentarios."""
    lineas = sin_comentarios(texto).splitlines()
    for k, linea in enumerate(lineas):
        encontrada = re.fullmatch(r"[\"']?on[\"']?:(.*)", linea)
        if encontrada and _sangria(linea) == 0:
            cuerpo = [encontrada.group(1)]
            for siguiente in lineas[k + 1 :]:
                if _sangria(siguiente) == 0:
                    break
                cuerpo.append(siguiente)
            return "\n".join(cuerpo)
    return ""


def comprobar_tc22(flujos: dict[str, str]) -> list[str]:
    """CA-12 esc. 2 y CA-R3 esc. 1 · TC-22. Ni `pull_request_target` ni `secrets.` en ningún flujo; `ci.yml` usa `pull_request`."""
    problemas = []
    for nombre, texto in flujos.items():
        activo = sin_comentarios(texto)
        if re.search(r"\bpull_request_target\b", activo):
            problemas.append(f"{nombre}: usa pull_request_target, que corre con secretos sobre código de una bifurcación")
        if re.search(r"\bsecrets\s*(?:\.|\[)", activo):
            problemas.append(f"{nombre}: lee secrets.*; el pipeline no lee secretos (regla común 5)")
    if "ci.yml" not in flujos:
        problemas.append("falta ci.yml entre los workflows")
    elif not re.search(r"(?<![\w-])pull_request(?![\w-])", _disparadores(flujos["ci.yml"])):
        problemas.append("ci.yml: el disparador debe ser `pull_request`")
    return problemas


def guarda_de_saltos(salida: str, patron: str = "skipped=") -> int:
    """Código de salida de `! grep -q "<patron>"` sobre la salida de unittest: 1 si hay saltos, 0 si no."""
    return 1 if patron in salida else 0


def _path_sin_uv() -> str:
    partes = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join(d for d in partes if d and shutil.which("uv", path=d) is None)


@functools.lru_cache(maxsize=1)
def salida_de_tools_sin_uv() -> tuple[int, str]:
    """Corre solo `test_sembrar_usuario_humo` (el que se salta sin `uv`) con `uv` fuera del PATH. No la suite entera: se llamaría a sí misma."""
    entorno = dict(os.environ)
    entorno["PATH"] = _path_sin_uv()
    proceso = subprocess.run(
        [sys.executable, "-m", "unittest", "tools.tests.test_sembrar_usuario_humo", "-v"],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return proceso.returncode, proceso.stdout + proceso.stderr


# --- Texto sintético de los trabajos nuevos y de un segundo workflow -------------------------------------

PASO_CHECKOUT_HERRAMIENTAS = (
    "      - uses: actions/checkout@abc # v7\n"
    "        with:\n"
    "          fetch-depth: 0\n"
    "          persist-credentials: false\n"
)
PASO_SETUP_UV = "      - uses: astral-sh/setup-uv@abc # v10\n"
PASO_SINCRONIZAR_HERRAMIENTAS = (
    "      - name: Sincronizar dependencias del backend\n"
    "        working-directory: backend\n"
    "        run: uv sync --locked --python 3.14\n"
)
PASO_TOOLS = (
    "      - name: Pruebas de tools/\n"
    "        shell: bash\n"
    '        run: uv run --no-project --python 3.14 python -m unittest discover -s tools/tests -v 2>&1 | tee "$RUNNER_TEMP/tools.txt"\n'
)
PASO_GUARDA = (
    "      - name: Guarda contra pruebas saltadas\n"
    "        run: |\n"
    '          ! grep -q "skipped=" "$RUNNER_TEMP/tools.txt"\n'
)

# Fila C4 (parte c): el verificador de escenarios, tras la guarda de saltos. Sin tubería, así que sin `shell: bash`; la base
# del PR entra por `env:` y nunca por `${{ }}` dentro de `run:`.
PASO_ESCENARIOS = (
    "      - name: Verificar que cada escenario exigido tenga su test\n"
    "        env:\n"
    "          BASE: ${{ github.event.pull_request.base.sha }}\n"
    "        run: |\n"
    "          argumentos=()\n"
    '          if git cat-file -e "$BASE:tools/historias_activas.txt"; then\n'
    '            git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/activas_base.txt"\n'
    '            argumentos=(--activas-base "$RUNNER_TEMP/activas_base.txt")\n'
    "          fi\n"
    '          python3 tools/verificar_escenarios.py "${argumentos[@]}"\n'
)

HERRAMIENTAS_SINTETICO = (
    "  herramientas:\n"
    "    name: Herramientas · pruebas de tools/\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 15\n"
    "    steps:\n"
    + PASO_CHECKOUT_HERRAMIENTAS
    + PASO_SETUP_UV
    + PASO_SINCRONIZAR_HERRAMIENTAS
    + PASO_TOOLS
    + PASO_GUARDA
    + PASO_ESCENARIOS
)

PASO_ZIZMOR = "      - name: Auditar los workflows\n        run: uvx zizmor@1.14.2 --offline .github/workflows\n"
PASO_CHECKOUT_SIMPLE = "      - uses: actions/checkout@abc # v7\n        with:\n          persist-credentials: false\n"

WORKFLOWS_SINTETICO = (
    "  workflows:\n"
    "    name: Seguridad de los workflows\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 15\n"
    "    steps:\n"
    + PASO_CHECKOUT_SIMPLE
    + PASO_SETUP_UV
    + PASO_ZIZMOR
)

PASO_VERIFICAR_DOCS = "      - name: Verificar la documentación\n        run: python3 tools/verificar_docs.py\n"

DOCUMENTACION_SINTETICA = (
    "  documentacion:\n"
    "    name: Documentación\n"
    "    runs-on: ubuntu-24.04\n"
    "    timeout-minutes: 15\n"
    "    steps:\n"
    + PASO_CHECKOUT_SIMPLE
    + PASO_VERIFICAR_DOCS
)

CI_A4 = CI_CON_HUMO + HERRAMIENTAS_SINTETICO + WORKFLOWS_SINTETICO + DOCUMENTACION_SINTETICA

ENLACES_SINTETICO = """\
name: Enlaces
on:
  schedule:
    - cron: "0 13 * * 1"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  enlaces:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@abc # v7
"""

COMPROBACIONES_A4 = (
    comprobar_tc23,
    comprobar_trabajo_workflows,
    comprobar_trabajo_documentacion,
    comprobar_regla_comun_8,
    comprobar_regla_comun_9,
)


class PruebasDeMutantesDeLaFilaA4(unittest.TestCase):
    """Fila A4: cada compuerta nueva se pone en rojo si se comenta, se mueve de trabajo, se reordena o se desvía."""

    def test_a4_mutantes_el_texto_valido_pasa_todas_las_comprobaciones_nuevas_y_las_viejas(self):
        """Control — sin esto, un mutante «en rojo» podría estarlo por culpa del texto base."""
        trabajos = extraer_trabajos(CI_A4)
        for id_trabajo in ("herramientas", "workflows", "documentacion"):
            self.assertIn(id_trabajo, trabajos)
        for comprobacion in COMPROBACIONES_DE_TRABAJO + (comprobar_tc08,) + COMPROBACIONES_A4:
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])
        flujos = {"ci.yml": CI_A4, "enlaces.yml": ENLACES_SINTETICO}
        self.assertEqual(comprobar_tc13(flujos), [])
        self.assertEqual(comprobar_tc21(flujos), [])
        self.assertEqual(comprobar_tc22(flujos), [])
        self.assertEqual(comprobar_r1a(CI_A4), [])
        self.assertEqual(patron_de_la_guarda(trabajos), "skipped=")

    def test_a4_mutantes_tc23_herramientas_pierde_shell_bash(self):
        """CA-R4 esc. 2 · TC-23 — sin `shell: bash` en el paso de la tubería, una prueba rota no pondría el trabajo en rojo."""
        casos = {
            "shell: bash borrado": mutar(CI_A4, "herramientas", "        shell: bash\n", ""),
            "shell: bash comentado": comentar_linea_de_trabajo(CI_A4, "herramientas", "        shell: bash\n"),
            "shell: sh": mutar(CI_A4, "herramientas", "shell: bash", "shell: sh"),
            "shell: bash en otro paso": mutar(
                mutar(CI_A4, "herramientas", "        shell: bash\n", ""),
                "herramientas",
                PASO_SINCRONIZAR_HERRAMIENTAS,
                sustituir(PASO_SINCRONIZAR_HERRAMIENTAS, "        run:", "        shell: bash\n        run:"),
            ),
            "shell: bash en el trabajo y no en el paso": mutar(
                mutar(CI_A4, "herramientas", "        shell: bash\n", ""),
                "herramientas",
                "    timeout-minutes: 15\n",
                "    timeout-minutes: 15\n    shell: bash\n",
            ),
        }
        fragmentos = {
            "shell: bash borrado": "el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`",
            "shell: bash comentado": "el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`",
            "shell: sh": "el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`",
            "shell: bash en otro paso": "el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`",
            "shell: bash en el trabajo y no en el paso": "el paso que ejecuta la suite de tools/ con una tubería no declara `shell: bash`",
        }
        exigir_rojo_en_todos(self, comprobar_tc23, casos, "'herramientas'", fragmentos=fragmentos)

    def test_a4_mutantes_tc23_herramientas_pierde_la_guarda_de_skipped(self):
        """CA-R4 esc. 2 · TC-23 — la guarda borrada, comentada, movida, desviada o invertida deja el caso en rojo."""
        casos = {
            "guarda borrada": mutar(CI_A4, "herramientas", PASO_GUARDA, ""),
            "guarda comentada": comentar(CI_A4, "herramientas", PASO_GUARDA),
            "guarda movida a workflows": mover(CI_A4, "herramientas", "workflows", PASO_GUARDA, PASO_SETUP_UV),
            "guarda movida a backend": mover(CI_A4, "herramientas", "backend", PASO_GUARDA, "      - run: uv run mypy .\n"),
            "guarda antes de las pruebas": mutar(CI_A4, "herramientas", PASO_TOOLS + PASO_GUARDA, PASO_GUARDA + PASO_TOOLS),
            "guarda sin la negación": mutar(CI_A4, "herramientas", '! grep -q "skipped="', 'grep -q "skipped="'),
            "guarda busca otra cadena": mutar(CI_A4, "herramientas", '"skipped="', '"skipped"'),
            "guarda lee otro archivo": mutar(
                CI_A4, "herramientas", PASO_GUARDA, sustituir(PASO_GUARDA, "tools.txt", "otro.txt")
            ),
            "el comando solo en un name": mutar(
                CI_A4, "herramientas", PASO_GUARDA, '      - name: ! grep -q "skipped="\n        run: echo omitido\n'
            ),
        }
        fragmentos = {
            "guarda borrada": "guarda ! grep -q \"skipped=\"",
            "guarda comentada": "guarda ! grep -q \"skipped=\"",
            "guarda movida a workflows": "guarda ! grep -q \"skipped=\"",
            "guarda movida a backend": "guarda ! grep -q \"skipped=\"",
            "guarda antes de las pruebas": "guarda ! grep -q \"skipped=\"",
            "guarda sin la negación": "guarda ! grep -q \"skipped=\"",
            "guarda busca otra cadena": "guarda ! grep -q \"skipped=\"",
            "guarda lee otro archivo": "la guarda de skipped= no lee el archivo que escribe tee",
            "el comando solo en un name": "guarda ! grep -q \"skipped=\"",
        }
        exigir_rojo_en_todos(self, comprobar_tc23, casos, "'herramientas'", fragmentos=fragmentos)

    def test_a4_mutantes_tc23_herramientas_pierde_la_suite_uv_o_el_historial(self):
        """CA-R4 esc. 2 · TC-23 — sin `uv`, sin sincronizar, sin el historial completo o con la tubería mal armada, el caso queda en rojo."""
        casos = {
            "trabajo ausente": sustituir(CI_A4, "\n  herramientas:\n", "\n  utilidades:\n"),
            "setup-uv borrado": mutar(CI_A4, "herramientas", PASO_SETUP_UV, ""),
            "setup-uv comentado": comentar(CI_A4, "herramientas", PASO_SETUP_UV),
            "setup-uv después de uv sync": mutar(
                CI_A4, "herramientas", PASO_SETUP_UV + PASO_SINCRONIZAR_HERRAMIENTAS, PASO_SINCRONIZAR_HERRAMIENTAS + PASO_SETUP_UV
            ),
            "uv sync comentado": comentar(CI_A4, "herramientas", PASO_SINCRONIZAR_HERRAMIENTAS),
            "uv sync sin --locked": mutar(CI_A4, "herramientas", "uv sync --locked --python 3.14", "uv sync --python 3.14"),
            "uv sync fuera de backend": mutar(CI_A4, "herramientas", "        working-directory: backend\n", ""),
            "sin fetch-depth": mutar(CI_A4, "herramientas", "          fetch-depth: 0\n", ""),
            "fetch-depth comentado": mutar(CI_A4, "herramientas", "          fetch-depth: 0\n", "          # fetch-depth: 0\n"),
            "fetch-depth: 1": mutar(CI_A4, "herramientas", "fetch-depth: 0", "fetch-depth: 1"),
            "checkout borrado": mutar(CI_A4, "herramientas", PASO_CHECKOUT_HERRAMIENTAS, ""),
            "unittest comentado": comentar(CI_A4, "herramientas", PASO_TOOLS),
            "unittest movido a backend": mover(CI_A4, "herramientas", "backend", PASO_TOOLS, "      - run: uv run mypy .\n"),
            "unittest sobre otra carpeta": mutar(CI_A4, "herramientas", "-s tools/tests", "-s backend/tests"),
            "unittest sin discover": mutar(CI_A4, "herramientas", "unittest discover -s tools/tests", "unittest tools.tests"),
            "unittest sin 2>&1": mutar(CI_A4, "herramientas", " 2>&1 |", " |"),
            "unittest sin tee": mutar(CI_A4, "herramientas", ' 2>&1 | tee "$RUNNER_TEMP/tools.txt"', ""),
            "unittest desde backend": mutar(
                CI_A4, "herramientas", PASO_TOOLS, sustituir(PASO_TOOLS, "        shell: bash\n", "        shell: bash\n        working-directory: backend\n")
            ),
            "el comando solo en un name": mutar(
                CI_A4, "herramientas", PASO_TOOLS, "      - name: python -m unittest discover -s tools/tests\n        shell: bash\n        run: echo omitido\n"
            ),
            "ubuntu-latest": mutar(CI_A4, "herramientas", "ubuntu-24.04", "ubuntu-latest"),
            "timeout de 25": mutar(CI_A4, "herramientas", "timeout-minutes: 15", "timeout-minutes: 25"),
            "sin timeout": mutar(CI_A4, "herramientas", "    timeout-minutes: 15\n", ""),
        }
        fragmentos = {
            "trabajo ausente": "no existe el trabajo",
            "setup-uv borrado": "falta astral-sh/setup-uv",
            "setup-uv comentado": "falta astral-sh/setup-uv",
            "setup-uv después de uv sync": "uv sync va antes de setup-uv",
            "uv sync comentado": "uv sync --locked --python 3.14",
            "uv sync sin --locked": "uv sync --locked --python 3.14",
            "uv sync fuera de backend": "uv sync --locked --python 3.14",
            "sin fetch-depth": "el checkout debe declarar `fetch-depth: 0`",
            "fetch-depth comentado": "el checkout debe declarar `fetch-depth: 0`",
            "fetch-depth: 1": "el checkout debe declarar `fetch-depth: 0`",
            "checkout borrado": "falta actions/checkout",
            "unittest comentado": "unittest discover -s tools/tests",
            "unittest movido a backend": "unittest discover -s tools/tests",
            "unittest sobre otra carpeta": "unittest discover -s tools/tests",
            "unittest sin discover": "unittest discover -s tools/tests",
            "unittest sin 2>&1": "el paso de la suite de tools/ debe terminar en `2>&1 | tee <archivo>`",
            "unittest sin tee": "el paso de la suite de tools/ debe terminar en `2>&1 | tee <archivo>`",
            "unittest desde backend": "unittest discover -s tools/tests se ejecuta desde la raíz del repositorio, no desde otro directorio",
            "el comando solo en un name": "unittest discover -s tools/tests",
            "ubuntu-latest": "runs-on",
            "timeout de 25": "timeout-minutes",
            "sin timeout": "timeout-minutes",
        }
        exigir_rojo_en_todos(self, comprobar_tc23, casos, "'herramientas'", fragmentos=fragmentos)

    def test_a4_mutantes_workflows_exige_zizmor_con_version_exacta_y_sin_red(self):
        """CA-12 esc. 3 · soporte de TC-20 y TC-24 — el trabajo `workflows` existe, instala `uv` y audita con una versión fija."""
        casos = {
            "trabajo ausente": sustituir(CI_A4, "\n  workflows:\n", "\n  seguridad:\n"),
            "zizmor comentado": comentar(CI_A4, "workflows", PASO_ZIZMOR),
            "zizmor movido a documentacion": mover(CI_A4, "workflows", "documentacion", PASO_ZIZMOR, PASO_CHECKOUT_SIMPLE),
            "zizmor sin versión": mutar(CI_A4, "workflows", "zizmor@1.14.2", "zizmor"),
            "zizmor@latest": mutar(CI_A4, "workflows", "zizmor@1.14.2", "zizmor@latest"),
            "zizmor con versión parcial": mutar(CI_A4, "workflows", "zizmor@1.14.2", "zizmor@1.14"),
            "zizmor con rango": mutar(CI_A4, "workflows", "zizmor@1.14.2", "zizmor@^1.14.2"),
            "zizmor sin --offline": mutar(CI_A4, "workflows", " --offline", ""),
            "zizmor sobre otra ruta": mutar(CI_A4, "workflows", ".github/workflows", "."),
            "zizmor sin uvx": mutar(CI_A4, "workflows", "uvx zizmor@1.14.2", "zizmor@1.14.2"),
            "zizmor desde backend": mutar(CI_A4, "workflows", PASO_ZIZMOR, sustituir(PASO_ZIZMOR, "        run:", "        working-directory: backend\n        run:")),
            "setup-uv borrado": mutar(CI_A4, "workflows", PASO_SETUP_UV, ""),
            "setup-uv después de zizmor": mutar(CI_A4, "workflows", PASO_SETUP_UV + PASO_ZIZMOR, PASO_ZIZMOR + PASO_SETUP_UV),
            "checkout borrado": mutar(CI_A4, "workflows", PASO_CHECKOUT_SIMPLE, ""),
            "el comando solo en un name": mutar(CI_A4, "workflows", PASO_ZIZMOR, "      - name: uvx zizmor@1.14.2 --offline .github/workflows\n        run: echo omitido\n"),
            "timeout de 25": mutar(CI_A4, "workflows", "timeout-minutes: 15", "timeout-minutes: 25"),
            "ubuntu-latest": mutar(CI_A4, "workflows", "ubuntu-24.04", "ubuntu-latest"),
        }
        fragmentos = {
            "trabajo ausente": "no existe el trabajo",
            "zizmor comentado": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor movido a documentacion": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor sin versión": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor@latest": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor con versión parcial": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor con rango": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor sin --offline": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor sobre otra ruta": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor sin uvx": "uvx zizmor@<versión> --offline .github/workflows",
            "zizmor desde backend": "uvx zizmor@<versión> --offline .github/workflows",
            "setup-uv borrado": "falta astral-sh/setup-uv",
            "setup-uv después de zizmor": "uvx zizmor@<versión> --offline .github/workflows",
            "checkout borrado": "falta actions/checkout",
            "el comando solo en un name": "uvx zizmor@<versión> --offline .github/workflows",
            "timeout de 25": "timeout-minutes",
            "ubuntu-latest": "runs-on",
        }
        exigir_rojo_en_todos(self, comprobar_trabajo_workflows, casos, "'workflows'", fragmentos=fragmentos)

    def test_a4_mutantes_documentacion_exige_verificar_docs_desde_la_raiz(self):
        """CA-13 (parte a) — el trabajo `documentacion` existe, hace checkout y ejecuta `python3 tools/verificar_docs.py`."""
        casos = {
            "trabajo ausente": sustituir(CI_A4, "\n  documentacion:\n", "\n  docs:\n"),
            "verificar_docs comentado": comentar(CI_A4, "documentacion", PASO_VERIFICAR_DOCS),
            "verificar_docs movido a workflows": mover(CI_A4, "documentacion", "workflows", PASO_VERIFICAR_DOCS, PASO_CHECKOUT_SIMPLE),
            "verificar_docs con python en lugar de python3": mutar(CI_A4, "documentacion", "python3 tools", "python tools"),
            "verificar_docs sobre otro script": mutar(CI_A4, "documentacion", "verificar_docs.py", "extraer_mermaid.py"),
            "verificar_docs desde backend": mutar(
                CI_A4, "documentacion", PASO_VERIFICAR_DOCS, sustituir(PASO_VERIFICAR_DOCS, "        run:", "        working-directory: backend\n        run:")
            ),
            "verificar_docs antes del checkout": mutar(
                CI_A4, "documentacion", PASO_CHECKOUT_SIMPLE + PASO_VERIFICAR_DOCS, PASO_VERIFICAR_DOCS + PASO_CHECKOUT_SIMPLE
            ),
            "checkout borrado": mutar(CI_A4, "documentacion", PASO_CHECKOUT_SIMPLE, ""),
            "el comando solo en un name": mutar(
                CI_A4, "documentacion", PASO_VERIFICAR_DOCS, "      - name: python3 tools/verificar_docs.py\n        run: echo omitido\n"
            ),
            "timeout de 25": mutar(CI_A4, "documentacion", "timeout-minutes: 15", "timeout-minutes: 25"),
            "sin timeout": mutar(CI_A4, "documentacion", "    timeout-minutes: 15\n", ""),
            "ubuntu-latest": mutar(CI_A4, "documentacion", "ubuntu-24.04", "ubuntu-latest"),
        }
        fragmentos = {
            "trabajo ausente": "no existe el trabajo",
            "verificar_docs comentado": "python3 tools/verificar_docs.py",
            "verificar_docs movido a workflows": "python3 tools/verificar_docs.py",
            "verificar_docs con python en lugar de python3": "python3 tools/verificar_docs.py",
            "verificar_docs sobre otro script": "python3 tools/verificar_docs.py",
            "verificar_docs desde backend": "python3 tools/verificar_docs.py",
            "verificar_docs antes del checkout": "python3 tools/verificar_docs.py",
            "checkout borrado": "falta actions/checkout",
            "el comando solo en un name": "python3 tools/verificar_docs.py",
            "timeout de 25": "timeout-minutes",
            "sin timeout": "timeout-minutes",
            "ubuntu-latest": "runs-on",
        }
        exigir_rojo_en_todos(self, comprobar_trabajo_documentacion, casos, "'documentacion'", fragmentos=fragmentos)

    def test_a4_mutantes_regla_comun_9_toda_tuberia_declara_shell_bash(self):
        """Regla común 9 — una tubería sin `shell: bash` en cualquier trabajo deja el caso en rojo; `||` y las comillas no cuentan."""
        sin_shell = mutar(CI_A4, "backend", PASO_MYPY, "      - run: uv run mypy . | tee mypy.txt\n")
        problemas = exigir_rojo(self, comprobar_regla_comun_9, sin_shell)
        self.assertIn("'backend'", problemas[0])
        casos = {
            "tubería en el run de un bloque": mutar(CI_A4, "backend", PASO_MYPY, "      - run: |\n          uv run mypy .\n          cat a | sort\n"),
            "tubería con shell: sh": mutar(CI_A4, "backend", PASO_MYPY, "      - run: uv run mypy . | tee x\n        shell: sh\n"),
            "tubería con la orden entre comillas de YAML": mutar(CI_A4, "backend", PASO_MYPY, "      - run: 'uv run mypy . | tee x'\n"),
            "se quita shell: bash a herramientas": mutar(CI_A4, "herramientas", "        shell: bash\n", ""),
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_9, casos, "tubería")
        validos = {
            "tubería con shell: bash": mutar(CI_A4, "backend", PASO_MYPY, "      - run: uv run mypy . | tee x\n        shell: bash\n"),
            "|| no es una tubería": mutar(CI_A4, "backend", PASO_MYPY, "      - run: uv run mypy . || true\n"),
            "| dentro de comillas": mutar(CI_A4, "backend", PASO_MYPY, '      - run: grep -E "a|b" x\n'),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_regla_comun_9(extraer_trabajos(texto)), [])

    def test_a4_mutantes_regla_comun_8_ningun_run_interpola_expresiones(self):
        """Regla común 8 — un `${{ }}` dentro de `run:` deja el caso en rojo; en `env:` o en `if:` no."""
        casos = {
            "interpolación en una línea": mutar(CI_A4, "backend", PASO_MYPY, '      - run: echo "${{ github.head_ref }}"\n'),
            "interpolación en un bloque": mutar(CI_A4, "backend", PASO_MYPY, "      - run: |\n          uv run mypy .\n          echo ${{ github.event.pull_request.title }}\n"),
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_8, casos, "interpola")
        por_env = mutar(
            CI_A4, "backend", PASO_MYPY, '      - run: echo "$RAMA"\n        env:\n          RAMA: ${{ github.head_ref }}\n        if: ${{ !cancelled() }}\n'
        )
        self.assertEqual(comprobar_regla_comun_8(extraer_trabajos(por_env)), [])

    def test_a4_mutantes_tc21_cada_workflow_declara_contents_read_y_justifica_todo_write(self):
        """CA-12 esc. 1 y 3 · TC-21 — sin permisos a nivel de flujo, con otro permiso o con un `: write` sin comentario, el caso queda en rojo."""
        sin_permisos = sustituir(CI_A4, "permissions:\n  contents: read\n", "")
        solo_en_trabajo = mutar(
            sin_permisos, "backend", "    timeout-minutes: 25\n", "    timeout-minutes: 25\n    permissions:\n      contents: read\n"
        )
        escritura = "    timeout-minutes: 25\n    permissions:\n      contents: write\n"
        casos = {
            "ci.yml sin permissions": {"ci.yml": sin_permisos, "enlaces.yml": ENLACES_SINTETICO},
            "permissions solo a nivel de trabajo": {"ci.yml": solo_en_trabajo, "enlaces.yml": ENLACES_SINTETICO},
            "permissions comentado": {"ci.yml": sustituir(CI_A4, "permissions:\n  contents: read\n", "# permissions:\n#   contents: read\n"), "enlaces.yml": ENLACES_SINTETICO},
            "permissions: read-all": {"ci.yml": sustituir(CI_A4, "permissions:\n  contents: read\n", "permissions: read-all\n"), "enlaces.yml": ENLACES_SINTETICO},
            "contents: write a nivel de flujo": {"ci.yml": sustituir(CI_A4, "contents: read\n", "contents: write\n"), "enlaces.yml": ENLACES_SINTETICO},
            "flujo con contents: read y pull-requests: write sin comentario": {
                "ci.yml": sustituir(CI_A4, "  contents: read\n", "  contents: read\n  pull-requests: write\n"),
                "enlaces.yml": ENLACES_SINTETICO,
            },
            "un trabajo amplía sin comentario": {"ci.yml": mutar(CI_A4, "backend", "    timeout-minutes: 25\n", escritura), "enlaces.yml": ENLACES_SINTETICO},
            "un trabajo amplía con un comentario vacío": {
                "ci.yml": mutar(CI_A4, "backend", "    timeout-minutes: 25\n", sustituir(escritura, "write\n", "write #\n")),
                "enlaces.yml": ENLACES_SINTETICO,
            },
            "un trabajo amplía con el comentario separado por una línea": {
                "ci.yml": mutar(CI_A4, "backend", "    timeout-minutes: 25\n", sustituir(escritura, "      contents", "      # justificado\n\n      contents")),
                "enlaces.yml": ENLACES_SINTETICO,
            },
            "el otro workflow no declara permissions": {"ci.yml": CI_A4, "enlaces.yml": sustituir(ENLACES_SINTETICO, "permissions:\n  contents: read\n", "")},
            "no hay ningún workflow": {},
        }
        for descripcion, flujos in casos.items():
            with self.subTest(mutante=descripcion):
                self.assertNotEqual(comprobar_tc21(flujos), [], "el mutante debía poner TC-21 en rojo y pasó en verde")

    def test_a4_mutantes_tc21_nombra_el_archivo_sin_permisos(self):
        """CA-12 esc. 3 — «falla y nombra el archivo»."""
        problemas = comprobar_tc21({"ci.yml": CI_A4, "ensayo.yml": sustituir(ENLACES_SINTETICO, "permissions:\n  contents: read\n", "")})
        self.assertEqual(len(problemas), 1, problemas)
        self.assertIn("ensayo.yml", problemas[0])

    def test_a4_mutantes_tc21_un_write_justificado_por_escrito_pasa(self):
        """CA-12 esc. 1 — «salvo uno que lo justifique por escrito»: comentario al final o en la línea de arriba."""
        escritura = "    timeout-minutes: 25\n    permissions:\n      contents: write\n"
        for descripcion, bloque in (
            ("al final de la línea", sustituir(escritura, "write\n", "write # publica el informe en la rama gh-pages\n")),
            ("en la línea de arriba", sustituir(escritura, "      contents", "      # publica el informe en la rama gh-pages\n      contents")),
        ):
            with self.subTest(justificacion=descripcion):
                texto = mutar(CI_A4, "backend", "    timeout-minutes: 25\n", bloque)
                self.assertEqual(comprobar_tc21({"ci.yml": texto, "enlaces.yml": ENLACES_SINTETICO}), [])

    def test_a4_mutantes_tc22_ni_pull_request_target_ni_secretos_y_ci_usa_pull_request(self):
        """CA-12 esc. 2 y CA-R3 esc. 1 · TC-22 — cualquiera de los tres incumplimientos deja el caso en rojo."""
        con_secreto = mutar(CI_A4, "backend", PASO_MYPY, "      - run: uv run mypy .\n        env:\n          TOKEN: ${{ secrets.TOKEN }}\n")
        casos = {
            "pull_request_target en lugar de pull_request": {"ci.yml": sustituir(CI_A4, "  pull_request:\n", "  pull_request_target:\n")},
            "pull_request_target además de pull_request": {"ci.yml": sustituir(CI_A4, "  pull_request:\n", "  pull_request:\n  pull_request_target:\n")},
            "pull_request_target en otro workflow": {
                "ci.yml": CI_A4,
                "ensayo.yml": sustituir(ENLACES_SINTETICO, "  workflow_dispatch:\n", "  pull_request_target:\n"),
            },
            "secrets.TOKEN": {"ci.yml": con_secreto},
            "secrets.GITHUB_TOKEN": {"ci.yml": sustituir(con_secreto, "secrets.TOKEN", "secrets.GITHUB_TOKEN")},
            "secrets['TOKEN']": {"ci.yml": sustituir(con_secreto, "secrets.TOKEN", "secrets['TOKEN']")},
            "secreto en otro workflow": {"ci.yml": CI_A4, "enlaces.yml": ENLACES_SINTETICO + "      - run: echo ${{ secrets.X }}\n"},
            "ci.yml dispara por push": {"ci.yml": sustituir(CI_A4, "  pull_request:\n", "  push:\n")},
            "pull_request solo en un comentario": {"ci.yml": sustituir(CI_A4, "  pull_request:\n", "  push:\n  # pull_request:\n")},
            "ci.yml ausente": {"enlaces.yml": ENLACES_SINTETICO},
        }
        for descripcion, flujos in casos.items():
            with self.subTest(mutante=descripcion):
                self.assertNotEqual(comprobar_tc22(flujos), [], "el mutante debía poner TC-22 en rojo y pasó en verde")

    def test_a4_mutantes_tc22_lo_comentado_y_otras_formas_de_pull_request_no_cuentan(self):
        """CA-12 esc. 2 · TC-22 — un comentario que cita lo prohibido no falla; `on: [pull_request]` en línea sí cumple."""
        comentado = sustituir(CI_A4, "name: CI\n", "name: CI\n# Sin pull_request_target ni secrets.X: ver CA-12\n")
        self.assertEqual(comprobar_tc22({"ci.yml": comentado}), [])
        en_linea = sustituir(CI_A4, "on:\n  pull_request:\n", "on: [pull_request]\n")
        self.assertEqual(comprobar_tc22({"ci.yml": en_linea}), [])

    def test_a4_mutantes_tc22_nombra_el_archivo_infractor(self):
        """CA-R3 esc. 1 — el mensaje dice en qué archivo está el incumplimiento."""
        problemas = comprobar_tc22({"ci.yml": CI_A4, "ensayo.yml": sustituir(ENLACES_SINTETICO, "  workflow_dispatch:\n", "  pull_request_target:\n")})
        self.assertEqual(len(problemas), 1, problemas)
        self.assertIn("ensayo.yml", problemas[0])

    def test_a4_mutantes_tcr4b_la_guarda_ve_los_saltos_y_no_los_inventa(self):
        """CA-R4 esc. 2 · TC-R4b — la guarda de `ci.yml` busca `skipped=`, y una guarda borrada, comentada o movida de trabajo no tiene patrón."""
        trabajos = extraer_trabajos(CI_A4)
        self.assertEqual(patron_de_la_guarda(trabajos), "skipped=")
        for descripcion, texto in {
            "guarda borrada": mutar(CI_A4, "herramientas", PASO_GUARDA, ""),
            "guarda comentada": comentar(CI_A4, "herramientas", PASO_GUARDA),
            "guarda movida a workflows": mover(CI_A4, "herramientas", "workflows", PASO_GUARDA, PASO_SETUP_UV),
        }.items():
            with self.subTest(mutante=descripcion):
                self.assertIsNone(patron_de_la_guarda(extraer_trabajos(texto)))


# =========================================================================================================
# Reglas comunes 6 y 7 y pytest completo: ninguna compuerta se desactiva (ciclo de corrección 1)
# =========================================================================================================

GUARDA_DE_PASO = "        if: ${{ !cancelled() }}\n"


def con_guardas(texto: str) -> str:
    """Añade `if: ${{ !cancelled() }}` a cada paso de comprobación (`uv run`, `npm run`, `npm test`) de `backend` y `frontend`,
    y al `python3 tools/verificar_docs.py` de `documentacion`."""
    for id_trabajo in ("backend", "frontend"):
        inicio, fin = _rebanada(texto, id_trabajo)
        bloque = re.sub(
            r"(?m)^(      - run: (?:uv run|npm run|npm test)\b.*\n)", lambda m: m.group(1) + GUARDA_DE_PASO, texto[inicio:fin]
        )
        texto = texto[:inicio] + bloque + texto[fin:]
    return mutar(texto, "documentacion", PASO_VERIFICAR_DOCS, con_guarda(PASO_VERIFICAR_DOCS))


def con_guarda(paso: str, expresion: str = "${{ !cancelled() }}") -> str:
    """El `paso` con `if: <expresion>` justo después de su primera línea."""
    primera, resto = paso.split("\n", 1)
    return primera + f"\n        if: {expresion}\n" + resto


CI_CON_GUARDAS = con_guardas(CI_A4)

PASO_RUFF = "      - run: uv run ruff check .\n"
PASO_FORMAT_G = con_guarda("      - run: uv run ruff format --check .\n")
PASO_RUFF_G = con_guarda(PASO_RUFF)
PASO_MYPY_G = con_guarda(PASO_MYPY)
PASO_FLOAT_G = con_guarda("      - run: uv run python -m herramientas.verificar_float\n")
PASO_PYTEST_G = con_guarda(PASO_PYTEST)
PASO_LINT_G = con_guarda(PASO_LINT)
PASO_NPM_TEST_G = con_guarda(PASO_NPM_TEST)
PASO_TIPOS_G = con_guarda(PASO_TIPOS)
PASO_VERIFICAR_DOCS_G = con_guarda(PASO_VERIFICAR_DOCS)

COMPROBACIONES_DE_COMPUERTAS = (comprobar_regla_comun_6, comprobar_regla_comun_7, comprobar_pytest_sin_filtros)


def problemas_de_compuertas(trabajos: dict[str, list[str]]) -> list[str]:
    return [problema for comprobacion in COMPROBACIONES_DE_COMPUERTAS for problema in comprobacion(trabajos)]


class PruebasDeMutantesDeLasCompuertas(unittest.TestCase):
    """Reglas comunes 6 y 7: una compuerta desactivada sin quitarla del archivo (`continue-on-error`, un `if:` que nunca
    corre, `|| true`, un pytest filtrado) deja el pipeline en verde aunque nada se compruebe. Cada una se pone en rojo."""

    def test_compuertas_mutantes_el_texto_valido_pasa_todas_las_comprobaciones(self):
        """Control — la base guardada pasa las compuertas nuevas y todas las anteriores."""
        trabajos = extraer_trabajos(CI_CON_GUARDAS)
        for comprobacion in COMPROBACIONES_DE_TRABAJO + (comprobar_tc08,) + COMPROBACIONES_A4 + COMPROBACIONES_DE_COMPUERTAS:
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])

    def test_compuertas_mutantes_regla_comun_7_continue_on_error_en_un_paso_o_en_un_trabajo(self):
        """Regla común 7 — `continue-on-error`, de paso o de trabajo y con cualquier valor, deja el caso en rojo."""
        casos = {
            "continue-on-error tras mypy": (
                mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY_G + "        continue-on-error: true\n"),
                "continue-on-error",
            ),
            "continue-on-error tras npm test": (
                mutar(CI_CON_GUARDAS, "frontend", PASO_NPM_TEST_G, PASO_NPM_TEST_G + "        continue-on-error: true\n"),
                "continue-on-error",
            ),
            "continue-on-error antes del run del paso": (
                mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, "      - continue-on-error: true\n        run: uv run mypy .\n" + GUARDA_DE_PASO),
                "continue-on-error",
            ),
            "continue-on-error: false también sobra": (
                mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY_G + "        continue-on-error: false\n"),
                "continue-on-error",
            ),
            "continue-on-error en el trabajo backend": (
                mutar(CI_CON_GUARDAS, "backend", "    timeout-minutes: 25\n", "    timeout-minutes: 25\n    continue-on-error: true\n"),
                "a nivel de trabajo",
            ),
            "continue-on-error en el trabajo fronteras": (
                mutar(CI_CON_GUARDAS, "fronteras", "    timeout-minutes: 15\n", "    timeout-minutes: 15\n    continue-on-error: true\n"),
                "a nivel de trabajo",
            ),
            "continue-on-error en el trabajo humo": (
                mutar(CI_CON_GUARDAS, "humo", "    timeout-minutes: 20\n", "    timeout-minutes: 20\n    continue-on-error: ${{ true }}\n"),
                "a nivel de trabajo",
            ),
            "continue-on-error en un paso de humo": (
                mutar(CI_CON_GUARDAS, "humo", PASO_E2E, PASO_E2E + "        continue-on-error: true\n"),
                "en un paso",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_7, casos)

    def test_compuertas_mutantes_regla_comun_7_un_if_que_apaga_el_paso(self):
        """Regla común 7 — un `if:` de paso o de trabajo distinto de `!cancelled()`, `always()` o `failure()` deja el caso en rojo."""
        guardas_malas = {
            "if: ${{ false }}": "${{ false }}",
            "if: false": "false",
            "if: ${{ 1 == 2 }}": "${{ 1 == 2 }}",
            "if: success()": "success()",
            "if: ${{ success() }}": "${{ success() }}",
            "if: ${{ always() && false }}": "${{ always() && false }}",
            "if: ${{ github.event_name == 'push' }}": "${{ github.event_name == 'push' }}",
            "if: cancelled()": "cancelled()",
        }
        casos = {}
        for descripcion, expresion in guardas_malas.items():
            casos[f"ruff check con {descripcion}"] = (
                mutar(CI_CON_GUARDAS, "backend", PASO_RUFF_G, con_guarda(PASO_RUFF, expresion)),
                "if:",
            )
        casos["npm test con if: ${{ false }}"] = (
            mutar(CI_CON_GUARDAS, "frontend", PASO_NPM_TEST_G, con_guarda(PASO_NPM_TEST, "${{ false }}")),
            "if:",
        )
        casos["upload-artifact con if: false"] = (
            mutar(CI_CON_GUARDAS, "backend", "        if: always()\n", "        if: false\n"),
            "if:",
        )
        casos["el trabajo fronteras con if: ${{ false }}"] = (
            mutar(CI_CON_GUARDAS, "fronteras", "    timeout-minutes: 15\n", "    timeout-minutes: 15\n    if: ${{ false }}\n"),
            "a nivel de trabajo",
        )
        casos["el trabajo frontend con if: false"] = (
            mutar(CI_CON_GUARDAS, "frontend", "    needs: contrato-api\n    if: ${{ !cancelled() }}\n", "    needs: contrato-api\n    if: false\n"),
            "a nivel de trabajo",
        )
        exigir_rojo_en_todos(self, comprobar_regla_comun_7, casos)

    def test_compuertas_mutantes_regla_comun_7_un_or_true_enmascara_el_fallo(self):
        """Regla común 7 — `|| true`, `|| :` o `|| exit 0` al final de una orden deja el caso en rojo."""
        casos = {
            "mypy || true": mutar(CI_CON_GUARDAS, "backend", "uv run mypy .\n", "uv run mypy . || true\n"),
            "pytest || true": mutar(CI_CON_GUARDAS, "backend", "--junitxml=pytest.xml\n", "--junitxml=pytest.xml || true\n"),
            "verificar_float || :": mutar(CI_CON_GUARDAS, "backend", "herramientas.verificar_float\n", "herramientas.verificar_float || :\n"),
            "lint-imports || true": mutar(CI_CON_GUARDAS, "fronteras", "uv run lint-imports\n", "uv run lint-imports || true\n"),
            "npm test || true": mutar(CI_CON_GUARDAS, "frontend", "npm test\n", "npm test || true\n"),
            "e2e || true": mutar(CI_CON_GUARDAS, "humo", "--reporter=list,html\n", "--reporter=list,html || true\n"),
            "alembic || true": mutar(CI_CON_GUARDAS, "humo", "alembic upgrade head\n", "alembic upgrade head || true\n"),
            "alembic || exit 0": mutar(CI_CON_GUARDAS, "humo", "alembic upgrade head\n", "alembic upgrade head || exit 0\n"),
            "|| true sin espacios": mutar(CI_CON_GUARDAS, "backend", "uv run mypy .\n", "uv run mypy .||true\n"),
            "|| true en la segunda línea de un bloque": mutar(
                CI_CON_GUARDAS, "backend", PASO_MYPY_G, "      - run: |\n          uv sync --locked\n          uv run mypy . || true\n" + GUARDA_DE_PASO
            ),
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_7, casos, "||")

    def test_compuertas_mutantes_regla_comun_7_lo_legitimo_no_se_marca(self):
        """Regla común 7 — `always()`, `failure()`, `!cancelled()` (con o sin comillas), un `||` que no enmascara y un comentario no fallan."""
        validos = {
            "if: always()": mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, con_guarda(PASO_MYPY, "always()")),
            "if: failure()": mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, con_guarda(PASO_MYPY, "failure()")),
            "if: '!cancelled()' sin llaves": mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, con_guarda(PASO_MYPY, "'!cancelled()'")),
            "if entre comillas": mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, con_guarda(PASO_MYPY, '"${{ !cancelled() }}"')),
            "|| con una orden que sí falla": mutar(CI_CON_GUARDAS, "backend", "uv run mypy .\n", "uv run mypy . || exit 1\n"),
            "continue-on-error en un comentario": mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY_G + "        # continue-on-error: true\n"),
            "|| true en un comentario": mutar(CI_CON_GUARDAS, "backend", "uv run mypy .\n", "uv run mypy . # || true\n"),
        }
        for descripcion, texto in validos.items():
            with self.subTest(valido=descripcion):
                self.assertEqual(comprobar_regla_comun_7(extraer_trabajos(texto)), [])

    def test_compuertas_mutantes_regla_comun_6_todo_paso_de_comprobacion_lleva_if_no_cancelado(self):
        """Regla común 6 — en `backend`, `frontend` y `documentacion`, un paso de comprobación sin `if: ${{ !cancelled() }}` deja el caso en rojo."""
        casos = {
            "ruff format sin if": (mutar(CI_CON_GUARDAS, "backend", PASO_FORMAT_G, "      - run: uv run ruff format --check .\n"), "uv run ruff format"),
            "ruff check sin if": (mutar(CI_CON_GUARDAS, "backend", PASO_RUFF_G, "      - run: uv run ruff check .\n"), "uv run ruff check"),
            "mypy sin if": (mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY), "uv run mypy"),
            "verificar_float sin if": (
                mutar(CI_CON_GUARDAS, "backend", PASO_FLOAT_G, "      - run: uv run python -m herramientas.verificar_float\n"),
                "verificar_float",
            ),
            "pytest sin if": (mutar(CI_CON_GUARDAS, "backend", PASO_PYTEST_G, PASO_PYTEST), "uv run pytest"),
            "mypy con if: always()": (mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, con_guarda(PASO_MYPY, "always()")), "uv run mypy"),
            "mypy con el if comentado": (
                mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY + "        # if: ${{ !cancelled() }}\n"),
                "uv run mypy",
            ),
            "un paso nuevo de comprobación sin if": (
                mutar(CI_CON_GUARDAS, "backend", PASO_MYPY_G, PASO_MYPY_G + "      - run: uv run python -m herramientas.otra\n"),
                "herramientas.otra",
            ),
            "npm run lint sin if": (mutar(CI_CON_GUARDAS, "frontend", PASO_LINT_G, PASO_LINT), "npm run lint"),
            "npm test sin if": (mutar(CI_CON_GUARDAS, "frontend", PASO_NPM_TEST_G, PASO_NPM_TEST), "npm test"),
            "tipos:verificar sin if": (mutar(CI_CON_GUARDAS, "frontend", PASO_TIPOS_G, PASO_TIPOS), "tipos:verificar"),
            "trabajo backend ausente": (mutar(CI_CON_GUARDAS, "backend", "  backend:\n", "  construccion:\n"), "'backend'"),
            "trabajo frontend ausente": (mutar(CI_CON_GUARDAS, "frontend", "  frontend:\n", "  cliente:\n"), "'frontend'"),
            "verificar_docs sin if": (mutar(CI_CON_GUARDAS, "documentacion", PASO_VERIFICAR_DOCS_G, PASO_VERIFICAR_DOCS), "verificar_docs"),
            "verificar_docs con if: always()": (
                mutar(CI_CON_GUARDAS, "documentacion", PASO_VERIFICAR_DOCS_G, con_guarda(PASO_VERIFICAR_DOCS, "always()")),
                "verificar_docs",
            ),
            "verificar_docs con el if comentado": (
                mutar(CI_CON_GUARDAS, "documentacion", PASO_VERIFICAR_DOCS_G, PASO_VERIFICAR_DOCS + "        # if: ${{ !cancelled() }}\n"),
                "verificar_docs",
            ),
            "paso de verificar_docs ausente": (mutar(CI_CON_GUARDAS, "documentacion", PASO_VERIFICAR_DOCS_G, ""), "'documentacion'"),
            "paso de verificar_docs comentado": (comentar(CI_CON_GUARDAS, "documentacion", PASO_VERIFICAR_DOCS_G), "'documentacion'"),
            "trabajo documentacion ausente": (mutar(CI_CON_GUARDAS, "documentacion", "  documentacion:\n", "  docs:\n"), "'documentacion'"),
        }
        exigir_rojo_en_todos(self, comprobar_regla_comun_6, casos)

    def test_compuertas_mutantes_regla_comun_6_la_sincronizacion_y_la_instalacion_no_son_comprobaciones(self):
        """Regla común 6 — `uv sync`, `npm ci`, el checkout y la subida del informe no necesitan `if: ${{ !cancelled() }}`; `fronteras` y `humo` tampoco."""
        self.assertEqual(comprobar_regla_comun_6(extraer_trabajos(CI_CON_GUARDAS)), [])

    def test_compuertas_mutantes_pytest_el_comando_es_el_completo_sin_seleccion(self):
        """Pytest completo — `-k`, `-m`, `--deselect`, `--ignore`, `--collect-only` o una ruta posicional reducen las pruebas y dejan el caso en rojo."""
        casos = {
            "-k nada": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest -k nada "), "`-k`"),
            "-knada pegado": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest -knada "), "`-knada`"),
            "-k=nada": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest -k=nada "), "`-k=nada`"),
            "-m not lento": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", 'uv run pytest -m "not lento" '), "`-m`"),
            "--deselect": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest --deselect tests/x.py::t "), "`--deselect`"),
            "--ignore": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest --ignore=tests/api "), "`--ignore=tests/api`"),
            "--collect-only": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest --collect-only "), "`--collect-only`"),
            "una ruta posicional": (mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest tests/dominio "), "`tests/dominio`"),
            "filtro al final de la orden": (mutar(CI_CON_GUARDAS, "backend", "--junitxml=pytest.xml\n", "--junitxml=pytest.xml -k nada\n"), "`-k`"),
            "filtro tras una continuación de línea": (
                mutar(
                    CI_CON_GUARDAS,
                    "backend",
                    PASO_PYTEST_G,
                    "      - run: |\n          uv run pytest --cov=cimenta \\\n            -k nada \\\n            --junitxml=pytest.xml\n" + GUARDA_DE_PASO,
                ),
                "`-k`",
            ),
            "pytest en otro trabajo con filtro": (mutar(CI_CON_GUARDAS, "humo", PASO_CP_ENV, PASO_CP_ENV + "      - run: uv run pytest -k nada\n"), "'humo'"),
            "pytest comentado": (comentar(CI_CON_GUARDAS, "backend", PASO_PYTEST_G), "pytest"),
            "pytest movido a fronteras": (mover(CI_CON_GUARDAS, "backend", "fronteras", PASO_PYTEST_G, "      - run: uv run lint-imports\n"), "'backend'"),
        }
        exigir_rojo_en_todos(self, comprobar_pytest_sin_filtros, casos)

    def test_compuertas_mutantes_pytest_las_opciones_de_informe_no_son_seleccion(self):
        """Pytest completo — `--cov`, `--cov-report`, `--junitxml`, `-q`, `-ra` y `--tb` no filtran pruebas y pasan."""
        for opciones in ("-q ", "-ra ", "--tb=short ", "--cov=tipos_base --cov-report=term "):
            with self.subTest(opciones=opciones):
                texto = mutar(CI_CON_GUARDAS, "backend", "uv run pytest ", "uv run pytest " + opciones)
                self.assertEqual(comprobar_pytest_sin_filtros(extraer_trabajos(texto)), [])


# --- Los casos sobre el archivo real ----------------------------------------------------------------------


class DefinicionDeCIFilaA4(unittest.TestCase):
    """Casos estáticos de la fila A4 sobre `.github/workflows/`. Sin los trabajos, fallan; no se saltan."""

    def test_tc23_herramientas_instala_uv_corre_la_suite_con_pipefail_y_guarda_los_saltos(self):
        """CA-R4 esc. 2 · TC-23 — `herramientas`: checkout con fetch-depth 0, setup-uv, uv sync en backend/, la suite con `shell: bash` y tubería a tee, y `! grep -q "skipped="`."""
        self.assertEqual(comprobar_tc23(_trabajos_de_ci(self)), [])

    def test_a4_workflows_audita_con_zizmor_de_version_exacta(self):
        """CA-12 esc. 3 · soporte de TC-20 y TC-24 — `workflows`: checkout, setup-uv y `uvx zizmor@<versión> --offline .github/workflows`, con timeout 15."""
        self.assertEqual(comprobar_trabajo_workflows(_trabajos_de_ci(self)), [])

    def test_a4_documentacion_ejecuta_verificar_docs(self):
        """CA-13 (parte a) — `documentacion`: checkout y `python3 tools/verificar_docs.py`, con timeout 15."""
        self.assertEqual(comprobar_trabajo_documentacion(_trabajos_de_ci(self)), [])

    def test_tc21_cada_workflow_declara_contents_read_y_justifica_todo_write(self):
        """CA-12 esc. 1 y 3 · TC-21 — `permissions: contents: read` a nivel de flujo en cada archivo; todo `: write` lleva su comentario."""
        self.assertEqual(comprobar_tc21(_leer_flujos(self)), [])

    def test_tc22_ningun_workflow_usa_pull_request_target_ni_secretos(self):
        """CA-12 esc. 2 y CA-R3 esc. 1 · TC-22 (rechazo estático) — un PR de una bifurcación no recibe secretos; `ci.yml` usa `pull_request`."""
        self.assertEqual(comprobar_tc22(_leer_flujos(self)), [])

    def test_regla_comun_8_ningun_run_interpola_expresiones(self):
        """Regla común 8 — los valores de GitHub entran por `env:`, nunca con `${{ }}` dentro de `run:`."""
        self.assertEqual(comprobar_regla_comun_8(_trabajos_de_ci(self)), [])

    def test_regla_comun_9_toda_tuberia_declara_shell_bash(self):
        """Regla común 9 — todo paso con una tubería declara `shell: bash`, para que GitHub lo ejecute con pipefail."""
        self.assertEqual(comprobar_regla_comun_9(_trabajos_de_ci(self)), [])

    def test_tcr4b_la_guarda_de_ci_detecta_la_salida_real_de_tools_sin_uv(self):
        """CA-R4 esc. 2 · TC-R4b (rechazo) — la cadena que busca la guarda de `herramientas` aparece en la salida real de la suite sin `uv`."""
        patron = patron_de_la_guarda(_trabajos_de_ci(self))
        self.assertIsNotNone(patron, "el trabajo 'herramientas' no tiene la guarda `! grep -q \"skipped=\"`")
        _, salida = salida_de_tools_sin_uv()
        self.assertEqual(guarda_de_saltos(salida, patron), 1, salida)


class DefinicionDeCIDeLasCompuertas(unittest.TestCase):
    """Reglas comunes 6 y 7 y pytest completo sobre el `ci.yml` real, y los nueve mutantes del auditor sobre una copia en memoria."""

    def test_regla_comun_7_ninguna_compuerta_se_desactiva(self):
        """Regla común 7 — sin `continue-on-error`, sin `if:` que apague un paso y sin `|| true` en ningún trabajo."""
        self.assertEqual(comprobar_regla_comun_7(_trabajos_de_ci(self)), [])

    def test_regla_comun_6_todo_paso_de_comprobacion_de_backend_y_frontend_sigue_corriendo(self):
        """Regla común 6 — cada `uv run` de `backend`, cada `npm run`/`npm test` de `frontend` y el `verificar_docs.py` de `documentacion` lleva `if: ${{ !cancelled() }}`."""
        self.assertEqual(comprobar_regla_comun_6(_trabajos_de_ci(self)), [])

    def test_pytest_de_backend_es_el_comando_completo_del_diseno(self):
        """CA-1 esc. 1 — el pytest de `backend` no selecciona ni excluye pruebas."""
        self.assertEqual(comprobar_pytest_sin_filtros(_trabajos_de_ci(self)), [])

    def test_compuertas_las_formas_de_desactivar_una_compuerta_se_detectan_sobre_el_ci_real(self):
        """Regla común 7, regla común 6 y CA-1 — los nueve mutantes del auditor y uno más (mypy sin su `if`), aplicados al `ci.yml` real, deja alguna compuerta en rojo."""
        real = _leer_flujos(self)["ci.yml"]
        casos = {
            "continue-on-error tras mypy": (
                mutar(real, "backend", "        run: uv run mypy .\n", "        run: uv run mypy .\n        continue-on-error: true\n"),
                "continue-on-error",
            ),
            "continue-on-error tras npm test": (
                mutar(real, "frontend", "        run: npm test\n", "        run: npm test\n        continue-on-error: true\n"),
                "continue-on-error",
            ),
            "if: ${{ false }} en Lint con Ruff": (
                mutar(
                    real,
                    "backend",
                    "        if: ${{ !cancelled() }}\n        run: uv run ruff check .",
                    "        if: ${{ false }}\n        run: uv run ruff check .",
                ),
                "if:",
            ),
            "mypy || true": (mutar(real, "backend", "uv run mypy .\n", "uv run mypy . || true\n"), "||"),
            "pytest --junitxml || true": (mutar(real, "backend", "--junitxml=pytest.xml\n", "--junitxml=pytest.xml || true\n"), "||"),
            "pytest -k nada": (mutar(real, "backend", "uv run pytest ", "uv run pytest -k nada "), "`-k`"),
            "lint-imports || true": (mutar(real, "fronteras", "uv run lint-imports\n", "uv run lint-imports || true\n"), "||"),
            "e2e || true": (mutar(real, "humo", "--reporter=list,html\n", "--reporter=list,html || true\n"), "||"),
            "alembic || true": (mutar(real, "humo", "alembic upgrade head\n", "alembic upgrade head || true\n"), "||"),
            "mypy sin su if": (
                mutar(real, "backend", "        if: ${{ !cancelled() }}\n        run: uv run mypy .", "        run: uv run mypy ."),
                "uv run mypy",
            ),
        }
        exigir_rojo_en_todos(self, problemas_de_compuertas, casos)
        # El control: la copia sin mutar no tiene ningún problema, así que el rojo viene del mutante.
        self.assertEqual(problemas_de_compuertas(extraer_trabajos(real)), [])


class SaltosSinUv(unittest.TestCase):
    """CA-R4 esc. 2 · TC-R4b — caracteriza el comportamiento que la guarda vigila. No depende de `ci.yml`."""

    def test_tcr4b_sin_uv_en_el_path_la_suite_de_tools_se_salta_y_lo_dice_con_skipped(self):
        """CA-R4 esc. 2 · TC-R4b — sin `uv`, `test_sembrar_usuario_humo` se salta en lugar de correr y unittest imprime `skipped=`."""
        codigo, salida = salida_de_tools_sin_uv()
        self.assertEqual(codigo, 0, salida)
        self.assertIn("skipped=", salida)
        self.assertEqual(guarda_de_saltos(salida), 1)


# =========================================================================================================
# Fila C4 · el verificador de escenarios en el trabajo `herramientas` (TC-57)
# =========================================================================================================

VERIFICADOR_DE_ESCENARIOS = r"\bpython3 tools/verificar_escenarios\.py(?![\w.])"
ENV_DE_LA_BASE = re.compile(r"^BASE:\s*\$\{\{\s*github\.event\.pull_request\.base\.sha\s*\}\}\s*$", flags=re.MULTILINE)
EXISTE_EN_LA_BASE = re.compile(r"""\bgit cat-file -e "\$BASE:tools/historias_activas\.txt"(?![\w./-])""")
VUELCA_LA_BASE = re.compile(r"""\bgit show "\$BASE:tools/historias_activas\.txt"\s*>\s*"?\$RUNNER_TEMP/activas_base\.txt"?(?![\w./-])""")
PASA_LA_BASE = re.compile(r"""--activas-base[ =]+"?\$RUNNER_TEMP/activas_base\.txt"?(?![\w./-])""")


def comprobar_tc57(trabajos: dict[str, list[str]]) -> list[str]:
    """CA-6 esc. 1 · TC-57 (fila C4). El trabajo `herramientas` ejecuta `python3 tools/verificar_escenarios.py` después de la
    guarda de saltos, desde la raíz. La base del PR entra por `env: BASE: ${{ github.event.pull_request.base.sha }}` (un `${{ }}`
    en `run:` sería inyección de plantillas, regla común 8); si la base tenía `tools/historias_activas.txt`
    (`git cat-file -e "$BASE:..."`), `git show` la vuelca a `$RUNNER_TEMP/activas_base.txt` y se pasa con `--activas-base`. Con
    una tubería, el paso declara `shell: bash` (regla común 9)."""
    secuencia, posiciones = comprobar_secuencia(
        "herramientas",
        trabajos,
        [
            ("guarda ! grep -q \"skipped=\"", GUARDA_DE_SALTOS, None),
            ("python3 tools/verificar_escenarios.py", VERIFICADOR_DE_ESCENARIOS, None),
        ],
    )
    problemas = list(secuencia)
    posicion = posiciones.get("python3 tools/verificar_escenarios.py")
    if "herramientas" not in trabajos or posicion is None:
        return problemas
    bloque = trabajos["herramientas"]
    paso = pasos(bloque)[posicion[0]]
    orden = comando(paso)
    if not _en_la_raiz(bloque, paso):
        problemas.append("'herramientas': python3 tools/verificar_escenarios.py se ejecuta desde la raíz del repositorio")
    if not ENV_DE_LA_BASE.search(valor_del_paso(paso, "env") or ""):
        problemas.append(
            "'herramientas': el paso del verificador de escenarios no declara en env: BASE: ${{ github.event.pull_request.base.sha }}"
        )
    if "${{" in orden:
        problemas.append(
            "'herramientas': el paso del verificador de escenarios interpola ${{ }} dentro de run:; el valor entra por env: (inyección de plantillas)"
        )
    cat_file = EXISTE_EN_LA_BASE.search(orden)
    volcado = VUELCA_LA_BASE.search(orden)
    llamada = re.search(VERIFICADOR_DE_ESCENARIOS, orden)
    if cat_file is None:
        problemas.append('\'herramientas\': el paso del verificador de escenarios no comprueba con git cat-file -e "$BASE:tools/historias_activas.txt"')
    if volcado is None:
        problemas.append(
            '\'herramientas\': el paso del verificador de escenarios no vuelca con git show "$BASE:tools/historias_activas.txt" '
            'a "$RUNNER_TEMP/activas_base.txt"'
        )
    if cat_file is not None and volcado is not None and cat_file.start() > volcado.start():
        problemas.append("'herramientas': git cat-file -e debe ir antes que git show (la base puede no tener el archivo)")
    if volcado is not None and llamada is not None and volcado.start() > llamada.start():
        problemas.append("'herramientas': git show debe volcar la base antes de ejecutar el verificador")
    if not PASA_LA_BASE.search(orden):
        problemas.append(
            '\'herramientas\': el paso del verificador de escenarios no pasa --activas-base "$RUNNER_TEMP/activas_base.txt"'
        )
    if _tiene_tuberia(orden) and (valor_del_paso(paso, "shell") or "").strip("\"'") != "bash":
        problemas.append("'herramientas': el paso del verificador de escenarios usa una tubería sin `shell: bash`")
    return problemas


COMPROBACIONES_DE_LA_FILA_C4 = (comprobar_tc57, comprobar_regla_comun_6, comprobar_regla_comun_7, comprobar_regla_comun_8, comprobar_regla_comun_9)


class PruebasDeMutantesDeLaFilaC4(unittest.TestCase):
    """Fila C4: el paso del verificador de escenarios se pone en rojo si se comenta, se mueve, pierde `--activas-base` o
    interpola la base dentro de `run:`; y las reglas comunes 6, 7, 8 y 9 siguen en verde con el paso en su sitio."""

    def test_c4_mutantes_el_texto_valido_pasa_tc57_y_las_reglas_comunes(self):
        """Control — la base con el paso nuevo pasa TC-57 y las reglas comunes 6, 7, 8 y 9; sin esto un rojo podría ser del texto base."""
        trabajos = extraer_trabajos(CI_CON_GUARDAS)
        self.assertIn(PASO_ESCENARIOS, CI_CON_GUARDAS, "la base sintética debe llevar el paso nuevo")
        for comprobacion in COMPROBACIONES_DE_LA_FILA_C4:
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])
        self.assertEqual(comprobar_tc23(trabajos), [], "añadir el paso no debe romper TC-23")

    def test_c4_mutantes_tc57_el_paso_comentado_o_en_otro_trabajo_no_cuenta(self):
        """CA-6 esc. 1 · TC-57 — comentar el paso, llevarlo a otro trabajo o anteponerlo a la guarda deja el caso en rojo."""
        casos = {
            "paso comentado": comentar(CI_A4, "herramientas", PASO_ESCENARIOS),
            "paso movido a documentacion": mover(CI_A4, "herramientas", "documentacion", PASO_ESCENARIOS, PASO_CHECKOUT_SIMPLE),
            "paso movido a workflows": mover(CI_A4, "herramientas", "workflows", PASO_ESCENARIOS, PASO_SETUP_UV),
            "paso movido a backend": mover(CI_A4, "herramientas", "backend", PASO_ESCENARIOS, "      - run: uv run mypy .\n"),
            "paso antes de la guarda": mutar(CI_A4, "herramientas", PASO_GUARDA + PASO_ESCENARIOS, PASO_ESCENARIOS + PASO_GUARDA),
            "paso antes de las pruebas": mutar(CI_A4, "herramientas", PASO_TOOLS + PASO_GUARDA + PASO_ESCENARIOS, PASO_ESCENARIOS + PASO_TOOLS + PASO_GUARDA),
            "el comando solo en un name": mutar(
                CI_A4,
                "herramientas",
                PASO_ESCENARIOS,
                "      - name: python3 tools/verificar_escenarios.py\n        run: echo omitido\n",
            ),
            "python en lugar de python3": mutar(CI_A4, "herramientas", "          python3 tools/verificar_escenarios.py", "          python tools/verificar_escenarios.py"),
            "otro script": mutar(CI_A4, "herramientas", "tools/verificar_escenarios.py", "tools/verificar_docs.py"),
            "trabajo ausente": sustituir(CI_A4, "\n  herramientas:\n", "\n  utilidades:\n"),
        }
        exigir_rojo_en_todos(self, comprobar_tc57, casos, "verificar_escenarios", fragmentos={"trabajo ausente": "no existe el trabajo"})

    def test_c4_mutantes_tc57_sin_activas_base_el_historial_no_se_compara(self):
        """CA-6 esc. 1 · TC-57 — sin `--activas-base` una historia podría salir de la lista sin que nadie lo vea."""
        casos = {
            "sin --activas-base": mutar(CI_A4, "herramientas", '--activas-base "$RUNNER_TEMP/activas_base.txt"', ""),
            "--activas-base lee otro archivo": mutar(CI_A4, "herramientas", '--activas-base "$RUNNER_TEMP/activas_base.txt"', '--activas-base "$RUNNER_TEMP/otro.txt"'),
            "--activas-base comentado": mutar(
                CI_A4,
                "herramientas",
                '          argumentos=(--activas-base "$RUNNER_TEMP/activas_base.txt")\n',
                '          # argumentos=(--activas-base "$RUNNER_TEMP/activas_base.txt")\n',
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc57, casos, "--activas-base")

    def test_c4_mutantes_tc57_la_base_del_pr_se_comprueba_y_se_vuelca(self):
        """CA-6 esc. 1 · TC-57 — sin `git cat-file -e` o sin `git show`, o en otro orden, el archivo de la base no llega al verificador."""
        casos = {
            "sin git cat-file": (
                mutar(CI_A4, "herramientas", 'if git cat-file -e "$BASE:tools/historias_activas.txt"; then', "if true; then"),
                "git cat-file -e",
            ),
            "git cat-file sobre otra ruta": (
                mutar(CI_A4, "herramientas", 'git cat-file -e "$BASE:tools/historias_activas.txt"', 'git cat-file -e "$BASE:docs/04-historias-usuario.md"'),
                "git cat-file -e",
            ),
            "sin git show": (
                mutar(
                    CI_A4,
                    "herramientas",
                    '            git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/activas_base.txt"\n',
                    "            :\n",
                ),
                "git show",
            ),
            "git show vuelca a otro archivo": (
                mutar(CI_A4, "herramientas", 'git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/activas_base.txt"', 'git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/otro.txt"'),
                "git show",
            ),
            "git show antes que git cat-file": (
                mutar(
                    CI_A4,
                    "herramientas",
                    '          if git cat-file -e "$BASE:tools/historias_activas.txt"; then\n'
                    '            git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/activas_base.txt"\n',
                    '          git show "$BASE:tools/historias_activas.txt" > "$RUNNER_TEMP/activas_base.txt"\n'
                    '          if git cat-file -e "$BASE:tools/historias_activas.txt"; then\n',
                ),
                "git cat-file -e debe ir antes que git show",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc57, casos)

    def test_c4_mutantes_tc57_la_base_entra_por_env_y_no_por_run(self):
        """CA-6 esc. 1 · TC-57 y regla común 8 — `BASE` interpolado dentro de `run:`, o sin `env:`, deja el caso en rojo."""
        interpolado = mutar(
            CI_A4,
            "herramientas",
            'git cat-file -e "$BASE:tools/historias_activas.txt"',
            'git cat-file -e "${{ github.event.pull_request.base.sha }}:tools/historias_activas.txt"',
        )
        casos = {
            "BASE interpolado dentro de run": (interpolado, "interpola ${{ }} dentro de run:"),
            "sin env BASE": (
                mutar(CI_A4, "herramientas", "        env:\n          BASE: ${{ github.event.pull_request.base.sha }}\n", ""),
                "no declara en env: BASE",
            ),
            "env BASE de otra expresión": (
                mutar(CI_A4, "herramientas", "BASE: ${{ github.event.pull_request.base.sha }}", "BASE: ${{ github.sha }}"),
                "no declara en env: BASE",
            ),
            "env BASE de la cabeza del PR": (
                mutar(CI_A4, "herramientas", "pull_request.base.sha", "pull_request.head.sha"),
                "no declara en env: BASE",
            ),
            "env con otro nombre": (mutar(CI_A4, "herramientas", "          BASE:", "          RAMA_BASE:"), "no declara en env: BASE"),
        }
        exigir_rojo_en_todos(self, comprobar_tc57, casos)
        # La regla común 8 también lo ve: no depende de TC-57 para impedir la inyección.
        self.assertTrue(any("interpola" in p for p in comprobar_regla_comun_8(extraer_trabajos(interpolado))))

    def test_c4_mutantes_tc57_con_tuberia_el_paso_declara_shell_bash(self):
        """Regla común 9 — si el paso del verificador usa una tubería, sin `shell: bash` no hay pipefail."""
        con_tuberia = mutar(
            CI_A4,
            "herramientas",
            '"${argumentos[@]}"\n',
            '"${argumentos[@]}" | tee "$RUNNER_TEMP/escenarios.txt"\n',
        )
        con_shell = mutar(con_tuberia, "herramientas", "      - name: Verificar que cada escenario exigido tenga su test\n", "      - name: Verificar que cada escenario exigido tenga su test\n        shell: bash\n")
        sin_shell = extraer_trabajos(con_tuberia)
        self.assertTrue(any("tubería sin `shell: bash`" in p for p in comprobar_tc57(sin_shell)), comprobar_tc57(sin_shell))
        self.assertTrue(any("tubería sin `shell: bash`" in p for p in comprobar_regla_comun_9(sin_shell)))
        self.assertEqual(comprobar_tc57(extraer_trabajos(con_shell)), [])
        self.assertEqual(comprobar_regla_comun_9(extraer_trabajos(con_shell)), [])

    def test_c4_mutantes_las_reglas_comunes_siguen_viendo_las_compuertas_con_el_paso_nuevo(self):
        """Reglas comunes 6 y 7 — añadir el paso no apaga ninguna compuerta ni deja de detectar un `continue-on-error` en él."""
        con_continue = mutar(CI_CON_GUARDAS, "herramientas", "        env:\n", "        continue-on-error: true\n        env:\n")
        con_or_true = mutar(CI_CON_GUARDAS, "herramientas", '"${argumentos[@]}"\n', '"${argumentos[@]}" || true\n')
        for descripcion, texto in (("continue-on-error en el paso", con_continue), ("|| true en el paso", con_or_true)):
            with self.subTest(mutante=descripcion):
                self.assertNotEqual(comprobar_regla_comun_7(extraer_trabajos(texto)), [])


class DefinicionDeCIFilaC4(unittest.TestCase):
    """Fila C4 sobre el `ci.yml` real. Sin el paso en `herramientas`, falla; no se salta."""

    def test_tc57_herramientas_ejecuta_el_verificador_de_escenarios_con_la_base_del_pr_por_env(self):
        """CA-6 esc. 1 · TC-57 — tras la guarda de saltos: `env: BASE`, `git cat-file -e`, `git show` a `$RUNNER_TEMP/activas_base.txt`, `--activas-base` y `python3 tools/verificar_escenarios.py`."""
        self.assertEqual(comprobar_tc57(_trabajos_de_ci(self)), [])

    def test_tc57_las_reglas_comunes_6_7_8_y_9_siguen_en_verde_con_el_paso_nuevo(self):
        """Reglas comunes 6 a 9 — el paso nuevo no interpola en `run:`, no enmascara el fallo y declara `shell: bash` si usa tubería."""
        trabajos = _trabajos_de_ci(self)
        self.assertIn("python3 tools/verificar_escenarios.py", "\n".join(comando(p) for p in pasos(trabajos.get("herramientas", []))))
        for comprobacion in (comprobar_regla_comun_6, comprobar_regla_comun_7, comprobar_regla_comun_8, comprobar_regla_comun_9):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(trabajos), [])


if __name__ == "__main__":
    unittest.main()
