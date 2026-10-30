"""Pruebas estáticas del flujo de la revisión automatizada, `.github/workflows/revision-ia.yml`.

TKT-062b · fila B3a. Comprueban lo que el flujo *declara*, no lo que hace al correr (lo que hace el filtro lo cubre
`test_publicar_revision.py`, y el comportamiento en un PR real, el ensayo de la fila B5). Mismo método que
`test_definicion_ci.py` y `test_definicion_etiqueta.py`, de donde se importan los ayudantes: `tools/` no tiene dependencias
y la biblioteca estándar no trae un analizador de YAML, así que el texto se lee con expresiones regulares, se ignoran las
líneas comentadas y cada caso busca dentro del bloque de su trabajo. Cada comprobación vive en una función `comprobar_*` que
devuelve la lista de problemas, y las pruebas sobre texto sintético demuestran que se pone en rojo ante cada mutante y por la
razón esperada (cada mutante exige un fragmento del mensaje, no solo que la lista no esté vacía).

Qué cubren:

* TC62-10 (`CA-1` esc. 1): `revision-ia.yml` existe, se dispara con `pull_request` y exactamente `opened`, `synchronize`,
  `ready_for_review` y `reopened`; vive en su propio archivo (`ci.yml` no aloja ningún trabajo de revisión); el trabajo
  `revision` tiene un único paso `anthropics/claude-code-action@<40 hex>` con `id: claude`, y toda acción va por SHA con la
  etiqueta de versión en un comentario.
* TC62-11 (`CA-2` esc. 1 y 2, rechazo): el `if:` a nivel de trabajo de `revision` es `GUARDA_DE_REVISION`, comparado con
  `_normalizada` y no con `_expresion_de_if`, que se comería la comilla final de `'dependabot[bot]'`.
* TC62-13 (`CA-3` esc. 1): permisos mínimos. `revision` solo `contents: read` y `pull-requests: read`; `publicar` solo
  `contents: read` y `pull-requests: write` con un comentario en la línea anterior; ningún `id-token`, `contents: write`,
  `issues`, `actions` ni `checks`; todo token es `github.token`.
* TC62-14 (`CA-3` esc. 3, rechazo; ajuste del 2026-10-30, F001): el modelo no tiene `Bash` ni herramientas de escritura.
  `--allowedTools` exactamente `Read(./**),Glob,Grep` (`Read(./**)` y no `Read` a secas, ningún `Bash`); `--disallowedTools` con
  `Edit`, `Write`, `Bash`, `Read(//proc/**)` y `Read(//sys/**)`; solo las cinco banderas del diseño y solo las cuatro entradas del
  `with:`. Un paso de `revision`, antes de la acción y sin secretos, escribe `.revision-pr/pr.json` y `.revision-pr/pr.diff` con
  `gh` (`GH_TOKEN`, `GH_REPO` y `PR` por `env:`): es lo que el modelo lee en lugar de llamar a `gh`. Las instrucciones remiten a
  esos dos archivos, no a `gh`, y dicen que el entorno del proceso no se lee.
* TC62-17 (`CA-4` esc. 1): `.claude/revision-pr.md` existe, enlaza `../CLAUDE.md` y la lista de convenciones §12 (los dos
  enlaces resuelven, ancla incluida) y no copia los primeros 50 caracteres de ninguno de los once puntos de §12 ni de las 17
  reglas de `CLAUDE.md`, que se leen del árbol al correr. Remite, no copia: la lista vive en un solo sitio.
* TC62-18 (`CA-4` esc. 2, rechazo): los checkouts de `revision` y de `publicar` leen la base (`base.sha`), nunca la cabeza del
  PR, con `persist-credentials: false`; el `prompt` nombra `.claude/revision-pr.md`.
* TC62-26 (`CA-5` esc. 2): `publicar` espera a `revision`, sin `if:`; «Archivos del PR» con `gh api --paginate`, el filtro y
  `gh pr comment --body-file`, en ese orden; `HALLAZGOS` viene de `needs.revision.outputs.hallazgos`, que sale de
  `steps.claude.outputs.structured_output`; ningún `secrets.`.
* TC62-27 (`CA-7` esc. 1): en el repositorio real, solo `revision-ia.yml` lee un secreto, y es `USO_PERMITIDO_DEL_SECRETO` en su
  sitio.
* TC62-31 (`CA-8` esc. 2, rechazo): solo mutantes, porque la comprobación sobre los flujos reales ya es TC-13 de TKT-009:
  `needs: revision` en un trabajo de `ci.yml` y `workflow_run` en `revision-ia.yml`.
* TC62-33 (`CA-10` esc. 1): `--max-turns 20`, `--model sonnet` y `--json-schema` presentes; `timeout-minutes` 10 y 5.

Los casos sobre el archivo real fallan, no se saltan, si falta `.github/workflows/revision-ia.yml`.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_definicion_revision -v
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import unittest
from collections.abc import Callable

DIRECTORIO_DE_PRUEBAS = os.path.dirname(os.path.abspath(__file__))
if DIRECTORIO_DE_PRUEBAS not in sys.path:
    sys.path.insert(0, DIRECTORIO_DE_PRUEBAS)

from _ayudantes import _sangria, exigir_rojo, exigir_rojo_en_todos, sustituir  # noqa: E402
from test_definicion_ci import (  # noqa: E402
    ACCION_DE_REVISION,
    CI_A4,
    DIRECTORIO_DE_FLUJOS,
    ENLACES_SINTETICO,
    ETIQUETA_SINTETICA,
    FLUJO_DE_REVISION,
    GUARDA_DE_REVISION,
    LECTURA_DE_SECRETOS,
    RAIZ,
    SIN_CREDENCIALES,
    TIEMPO_POR_TRABAJO,
    USO_PERMITIDO_DEL_SECRETO,
    _expresion_de_if,
    _leer_flujos,
    _normalizada,
    _permisos_de_flujo,
    _texto_de_comentario,
    comprobar_reglas_comunes_de_todo_flujo,
    comprobar_tc13,
    comprobar_tc21,
    comprobar_tc22,
    extraer_trabajos,
    ids_de_needs,
    comando,
    motivos_de_secretos,
    mutar,
    pasos,
    sin_comentarios,
    valor_del_paso,
    valor_del_trabajo,
)
from test_definicion_etiqueta import (  # noqa: E402
    CHECKOUT_POR_SHA,
    HAY_PULL_REQUEST,
    HAY_PULL_REQUEST_TARGET,
    _leer_doc,
    _normalizar_doc,
    _seccion,
    _tipos_de_pull_request,
)
from test_definicion_ci import _disparadores  # noqa: E402

HERRAMIENTAS = os.path.dirname(DIRECTORIO_DE_PRUEBAS)
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

import verificar_docs  # noqa: E402

REVISION_IA =os.path.join(DIRECTORIO_DE_FLUJOS, FLUJO_DE_REVISION)

TIPOS_DEL_DISPARADOR = ("opened", "synchronize", "ready_for_review", "reopened")
REF_DE_LA_BASE = "${{ github.event.pull_request.base.sha }}"
TOKEN_DE_ACTIONS = "${{ github.token }}"
SALIDA_DEL_MODELO = "${{ steps.claude.outputs.structured_output }}"
HALLAZGOS_DE_REVISION = "${{ needs.revision.outputs.hallazgos }}"
INSTRUCCIONES_DEL_MODELO = ".claude/revision-pr.md"

PERMISOS_DE_REVISION = ["contents: read", "pull-requests: read"]
PERMISOS_DE_PUBLICAR = ["contents: read", "pull-requests: write"]

ENTRADAS_DEL_WITH = {"anthropic_api_key", "github_token", "prompt", "claude_args"}
BANDERAS_DEL_DISENO = {"--model", "--max-turns", "--allowedTools", "--disallowedTools", "--json-schema"}
HERRAMIENTAS_PERMITIDAS = ["Read(./**)", "Glob", "Grep"]
HERRAMIENTAS_PROHIBIDAS = [
    "Edit",
    "Write",
    "MultiEdit",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Bash",
    "Read(//proc/**)",
    "Read(//sys/**)",
]
CARPETA_DEL_PR = ".revision-pr"
JSON_DEL_PR = ".revision-pr/pr.json"
DIFF_DEL_PR = ".revision-pr/pr.diff"
VARIABLES_DE_GH = (
    ("GH_TOKEN", "${{ github.token }}"),
    ("GH_REPO", "${{ github.repository }}"),
    ("PR", "${{ github.event.pull_request.number }}"),
)
ORDENES_QUE_EL_MODELO_NO_PUEDE_TENER = ("gh pr review", "gh pr comment", "gh api")

USO_CON_VERSION = re.compile(r"^\s*(?:-\s+)?uses:\s*\S+@[0-9a-f]{40}\s+#\s*v\d+(?:\.\d+)*\s*$")
LINEA_DE_USES = re.compile(r"^\s*(?:-\s+)?uses:")
ACCION_POR_SHA = re.compile(re.escape(ACCION_DE_REVISION) + r"[0-9a-f]{40}")
LINEA_DE_TOKEN = re.compile(r"^\s*(?:GH_TOKEN|GITHUB_TOKEN|github_token)\s*:\s*(.*)$")


# ---------------------------------------------------------------------------------------------------------
# Lectura: el paso de la acción, su `with:` y las banderas de `claude_args`
# ---------------------------------------------------------------------------------------------------------


def _claves_del_bloque(paso: list[str], bloque: str) -> dict[str, list[str]]:
    """Hijos directos del bloque `with:` o `env:` de un paso, como clave -> lista de valores (una clave repetida suma valores).

    Un valor escalar es lo que sigue a los dos puntos; un valor con `|` o `>` es el cuerpo, sus líneas sin sangría unidas por
    saltos. Sin el bloque, el diccionario vacío."""
    columna = _sangria(paso[0]) + 2
    inicio = next((k for k, linea in enumerate(paso) if _sangria(linea) == columna and linea.strip() == f"{bloque}:"), None)
    if inicio is None:
        return {}
    cuerpo: list[str] = []
    for linea in paso[inicio + 1 :]:
        if _sangria(linea) <= columna:
            break
        cuerpo.append(linea)
    if not cuerpo:
        return {}
    hijo = min(_sangria(linea) for linea in cuerpo)
    claves: dict[str, list[str]] = {}
    k = 0
    while k < len(cuerpo):
        linea = cuerpo[k]
        k += 1
        encontrada = re.fullmatch(r"\s*([A-Za-z0-9_-]+):[ \t]*(.*)", linea) if _sangria(linea) == hijo else None
        if not encontrada:
            continue
        valor = encontrada.group(2).strip()
        if valor and valor[0] in "|>":
            lineas_del_valor: list[str] = []
            while k < len(cuerpo) and _sangria(cuerpo[k]) > hijo:
                lineas_del_valor.append(cuerpo[k].strip())
                k += 1
            valor = "\n".join(lineas_del_valor)
        claves.setdefault(encontrada.group(1), []).append(valor)
    return claves


def _paso_de_claude(texto: str) -> list[str] | None:
    """El paso del trabajo `revision` cuyo `uses:` empieza por `anthropics/claude-code-action@`; None si no hay."""
    bloque = extraer_trabajos(texto).get("revision")
    if bloque is None:
        return None
    return next((p for p in pasos(bloque) if (valor_del_paso(p, "uses") or "").startswith(ACCION_DE_REVISION)), None)


def _banderas(claude_args: str) -> dict[str, list[str | None]] | None:
    """Las banderas `--x [valor]` de `claude_args`, leídas como las leería un shell. None si las comillas no cierran."""
    try:
        fichas = shlex.split(claude_args)
    except ValueError:
        return None
    banderas: dict[str, list[str | None]] = {}
    k = 0
    while k < len(fichas):
        ficha = fichas[k]
        if ficha.startswith("--"):
            valor = None
            if k + 1 < len(fichas) and not fichas[k + 1].startswith("--"):
                valor = fichas[k + 1]
                k += 1
            banderas.setdefault(ficha, []).append(valor)
        k += 1
    return banderas


def _banderas_del_modelo(texto: str) -> tuple[dict[str, list[str | None]] | None, list[str]]:
    """(banderas de `claude_args`, problemas de lectura). Si no se puede leer, las banderas son None y el problema lo dice."""
    paso = _paso_de_claude(texto)
    if paso is None:
        return None, ["el trabajo `revision` no tiene el paso de anthropics/claude-code-action"]
    valores = _claves_del_bloque(paso, "with").get("claude_args", [])
    if len(valores) != 1:
        return None, [f"el `with:` de la acción debe declarar `claude_args` exactamente una vez y lo declara {len(valores)}"]
    banderas = _banderas(valores[0])
    if banderas is None:
        return None, ["`claude_args` no se puede leer: tiene unas comillas sin cerrar"]
    return banderas, []


# ---------------------------------------------------------------------------------------------------------
# Comprobaciones: cada una devuelve la lista de problemas, vacía si el caso se cumple
# ---------------------------------------------------------------------------------------------------------


def comprobar_disparo_y_accion(texto: str) -> list[str]:
    """TC62-10 · CA-1 esc. 1. Disparadores exactos y el trabajo `revision` con `claude-code-action` por SHA e `id: claude`."""
    problemas: list[str] = []
    disparadores = _disparadores(texto)
    if not HAY_PULL_REQUEST.search(disparadores):
        problemas.append("el disparador debe ser `pull_request`")
    if HAY_PULL_REQUEST_TARGET.search(disparadores):
        problemas.append("usa pull_request_target, que corre con secretos sobre código de una bifurcación")
    tipos = _tipos_de_pull_request(disparadores)
    if tipos is None:
        problemas.append("`pull_request` no declara `types:`; sin ellos no se revisa al marcar el PR como listo")
    elif sorted(tipos) != sorted(TIPOS_DEL_DISPARADOR):
        problemas.append(
            f"`types:` debe ser exactamente {', '.join(TIPOS_DEL_DISPARADOR)} y es {', '.join(tipos) or '(vacío)'}"
        )
    for linea in texto.splitlines():
        if LINEA_DE_USES.match(linea) and not USO_CON_VERSION.match(linea):
            problemas.append(
                f"`{linea.strip()}` debe fijarse por el SHA de 40 caracteres y llevar la etiqueta de versión en un comentario"
            )
    trabajos = extraer_trabajos(texto)
    if "revision" not in trabajos:
        return problemas + ["no declara el trabajo `revision`"]
    acciones = [
        paso for paso in pasos(trabajos["revision"]) if (valor_del_paso(paso, "uses") or "").startswith(ACCION_DE_REVISION)
    ]
    if len(acciones) != 1:
        problemas.append(
            f"el trabajo `revision` debe tener exactamente un paso con `uses: {ACCION_DE_REVISION}<40 hex>` y tiene {len(acciones)}"
        )
        return problemas
    if not ACCION_POR_SHA.fullmatch(valor_del_paso(acciones[0], "uses") or ""):
        problemas.append("claude-code-action debe fijarse por el SHA de 40 caracteres de su commit")
    if (valor_del_paso(acciones[0], "id") or "").strip("\"'") != "claude":
        problemas.append("el paso de claude-code-action debe llevar `id: claude`: de él sale `structured_output`")
    for id_trabajo, bloque in trabajos.items():
        if id_trabajo != "revision" and any(
            (valor_del_paso(paso, "uses") or "").startswith(ACCION_DE_REVISION) for paso in pasos(bloque)
        ):
            problemas.append(f"'{id_trabajo}': usa claude-code-action; solo `revision` puede usarla")
    return problemas


def comprobar_que_ci_no_aloja_la_revision(texto_de_ci: str) -> list[str]:
    """TC62-10 · CA-1 esc. 1. La revisión no es `ci.yml`: ahí no hay trabajo `revision` ni `publicar` ni la acción."""
    problemas: list[str] = []
    trabajos = extraer_trabajos(texto_de_ci)
    for id_trabajo in ("revision", "publicar"):
        if id_trabajo in trabajos:
            problemas.append(f"ci.yml: declara el trabajo '{id_trabajo}'; la revisión vive en {FLUJO_DE_REVISION}, no en el pipeline")
    if ACCION_DE_REVISION in sin_comentarios(texto_de_ci):
        problemas.append("ci.yml: usa claude-code-action; la revisión vive en su propio flujo")
    return problemas


def comprobar_guarda(texto: str) -> list[str]:
    """TC62-11 · CA-2 esc. 1 y 2. El `if:` a nivel de trabajo de `revision` es `GUARDA_DE_REVISION`, comparado con `_normalizada`."""
    trabajos = extraer_trabajos(texto)
    if "revision" not in trabajos:
        return ["no declara el trabajo `revision`, el que lleva la guarda"]
    valor = valor_del_trabajo(trabajos["revision"], "if")
    if _normalizada(valor) != _normalizada(GUARDA_DE_REVISION):
        return [
            "el `if:` a nivel de trabajo de `revision` debe ser exactamente GUARDA_DE_REVISION "
            f"(`{GUARDA_DE_REVISION}`) y es {valor!r}: borradores, bifurcaciones y Dependabot no se revisan"
        ]
    return []


def _permisos_del_trabajo(bloque: list[str]) -> list[str] | None:
    valor = valor_del_trabajo(bloque, "permissions")
    return None if valor is None else sorted(linea.strip() for linea in valor.splitlines() if linea.strip())


def comprobar_permisos_y_token(texto: str) -> list[str]:
    """TC62-13 · CA-3 esc. 1. Permisos mínimos por trabajo y todo token como `github.token`."""
    problemas: list[str] = []
    if _permisos_de_flujo(texto) != ["contents: read"]:
        problemas.append(f"`permissions:` a nivel de flujo debe ser solo `contents: read` y es {_permisos_de_flujo(texto)!r}")
    trabajos = extraer_trabajos(texto)
    for id_trabajo, esperados in (("revision", PERMISOS_DE_REVISION), ("publicar", PERMISOS_DE_PUBLICAR)):
        if id_trabajo not in trabajos:
            problemas.append(f"no declara el trabajo `{id_trabajo}`")
            continue
        reales = _permisos_del_trabajo(trabajos[id_trabajo])
        if reales != sorted(esperados):
            problemas.append(f"'{id_trabajo}': `permissions:` debe ser exactamente {', '.join(esperados)} y es {reales!r}")
    lineas = texto.splitlines()
    for numero, linea in enumerate(lineas):
        if re.fullmatch(r"\s*pull-requests\s*:\s*[\"']?write[\"']?\s*(?:#.*)?", linea):
            previa = lineas[numero - 1].strip() if numero else ""
            if not _texto_de_comentario(previa):
                problemas.append(
                    "`pull-requests: write` debe llevar en la línea anterior un comentario que diga qué publica y por qué no basta para aprobar"
                )
    for linea in sin_comentarios(texto).splitlines():
        if re.match(r"\s*id-token\s*:", linea):
            problemas.append("declara `id-token`: el flujo no usa OIDC, y con él no rige el ajuste que impide aprobar")
        elif (permiso := re.match(r"\s*(issues|actions|checks)\s*:\s*\S", linea)) is not None:
            problemas.append(f"declara el permiso `{permiso.group(1)}`, que ningún trabajo necesita")
        elif re.match(r"\s*contents\s*:\s*[\"']?write", linea):
            problemas.append("declara `contents: write`: ningún trabajo escribe en el repositorio")
        elif (token := LINEA_DE_TOKEN.match(linea)) is not None and _normalizada(token.group(1)) != _normalizada(TOKEN_DE_ACTIONS):
            problemas.append(f"`{linea.strip()}`: todo token debe ser `{TOKEN_DE_ACTIONS}`, el de la ejecución")
    paso = _paso_de_claude(texto)
    if paso is None:
        problemas.append("el trabajo `revision` no tiene el paso de anthropics/claude-code-action")
    else:
        tokens = _claves_del_bloque(paso, "with").get("github_token", [])
        if [_normalizada(t) for t in tokens] != [_normalizada(TOKEN_DE_ACTIONS)]:
            problemas.append(f"el `with:` de la acción debe declarar `github_token: {TOKEN_DE_ACTIONS}` exactamente una vez y declara {tokens!r}")
    return problemas


def comprobar_herramientas_del_modelo(texto: str) -> list[str]:
    """TC62-14 · CA-3 esc. 3. El modelo lee y no escribe: herramientas permitidas exactas, prohibidas presentes, nada más."""
    paso = _paso_de_claude(texto)
    if paso is None:
        return ["el trabajo `revision` no tiene el paso de anthropics/claude-code-action"]
    problemas: list[str] = []
    ajenas = sorted(set(_claves_del_bloque(paso, "with")) - ENTRADAS_DEL_WITH)
    if ajenas:
        problemas.append(
            f"el `with:` de la acción declara entradas fuera de {', '.join(sorted(ENTRADAS_DEL_WITH))}: {', '.join(ajenas)}"
            " (otra vía de dar herramientas o permisos al modelo)"
        )
    banderas, de_lectura = _banderas_del_modelo(texto)
    if banderas is None:
        return problemas + de_lectura
    otras = sorted(set(banderas) - BANDERAS_DEL_DISENO)
    if otras:
        problemas.append(f"`claude_args` lleva banderas fuera de las cinco del diseño: {', '.join(otras)}")
    for bandera, esperadas in (("--allowedTools", HERRAMIENTAS_PERMITIDAS), ("--disallowedTools", HERRAMIENTAS_PROHIBIDAS)):
        valores = banderas.get(bandera, [])
        if len(valores) != 1 or valores[0] is None:
            problemas.append(f"`{bandera}` debe declararse exactamente una vez, con valor, y se declara {len(valores)} veces")
            continue
        elementos = [e.strip() for e in valores[0].split(",") if e.strip()]
        if bandera == "--allowedTools":
            if "Read" in elementos:
                problemas.append("`--allowedTools` lleva `Read` a secas, que lee fuera del árbol de trabajo; debe ser `Read(./**)`")
            if sorted(elementos) != sorted(esperadas):
                problemas.append(f"`--allowedTools` debe ser exactamente {','.join(esperadas)} y es {valores[0]}")
            if any(e.split("(", 1)[0] == "Bash" for e in elementos):
                problemas.append(
                    "`--allowedTools` permite `Bash`: el modelo no debe tener intérprete de órdenes, con el que alcanzaría el entorno y la clave"
                )
            for orden in ORDENES_QUE_EL_MODELO_NO_PUEDE_TENER:
                if orden in valores[0]:
                    problemas.append(f"`--allowedTools` permite `{orden}`: el modelo no debe tener con qué aprobar, comentar ni llamar a la API")
        else:
            for herramienta in esperadas:
                if herramienta not in elementos:
                    problemas.append(f"`--disallowedTools` debe incluir `{herramienta}` y es {valores[0]}")
    return problemas


def _indice_del_paso(lista: list[list[str]], patron: str) -> int | None:
    return next((i for i, paso in enumerate(lista) if re.search(patron, comando(paso))), None)


def comprobar_metadatos_del_pr(texto: str) -> list[str]:
    """TC62-14 · CA-3 esc. 3 (ajuste del 2026-10-30, F001). Sin `Bash`, el modelo lee el PR de dos archivos que escribe un paso de
    `revision` antes de la acción, con `gh`, sin secretos y con `GH_TOKEN`, `GH_REPO` y `PR` por `env:`."""
    trabajos = extraer_trabajos(texto)
    if "revision" not in trabajos:
        return ["no declara el trabajo `revision`"]
    lista = pasos(trabajos["revision"])
    i_paso = _indice_del_paso(lista, r"\bgh pr (?:view|diff)\b|\.revision-pr/")
    if i_paso is None:
        return [
            f"falta el paso de `revision` que escribe `{JSON_DEL_PR}` y `{DIFF_DEL_PR}`: "
            "sin él el modelo no tiene cómo leer el PR sin `Bash`"
        ]
    paso = lista[i_paso]
    orden = comando(paso)
    problemas: list[str] = []
    if not re.search(r"\bmkdir\s+-p\s+\.revision-pr\b", orden):
        problemas.append(f"el paso de metadatos debe crear la carpeta con `mkdir -p {CARPETA_DEL_PR}`")
    if not re.search(r"\bgh pr view\s+\"?\$PR\"?\s+--json\s+title,body,files\s*>\s*\.revision-pr/pr\.json(?!\S)", orden):
        problemas.append(f"el paso de metadatos debe escribir `{JSON_DEL_PR}` con `gh pr view \"$PR\" --json title,body,files`")
    if not re.search(r"\bgh pr diff\s+\"?\$PR\"?\s*>\s*\.revision-pr/pr\.diff(?!\S)", orden):
        problemas.append(f"el paso de metadatos debe escribir `{DIFF_DEL_PR}` con `gh pr diff \"$PR\"`")
    variables = _claves_del_bloque(paso, "env")
    for variable, expresion in VARIABLES_DE_GH:
        valores = variables.get(variable, [])
        if [_normalizada(v) for v in valores] != [_normalizada(expresion)]:
            problemas.append(
                f"el paso de metadatos debe recibir `{variable}: {expresion}` por `env:` exactamente una vez y recibe {valores!r}"
            )
    if LECTURA_DE_SECRETOS.search("\n".join(paso)):
        problemas.append("el paso de metadatos lee secrets.: corre antes de la acción y no necesita ningún secreto")
    i_accion = next(
        (i for i, otro in enumerate(lista) if (valor_del_paso(otro, "uses") or "").startswith(ACCION_DE_REVISION)), None
    )
    if i_accion is not None and i_paso > i_accion:
        problemas.append("el paso de metadatos debe ir antes del paso de claude-code-action: el modelo lee archivos que ya deben existir")
    return problemas


def comprobar_checkout_de_la_base(texto: str) -> list[str]:
    """TC62-18 · CA-4 esc. 2. Los checkouts de `revision` y `publicar` leen la base, sin credenciales; el `prompt` nombra las instrucciones."""
    problemas: list[str] = []
    trabajos = extraer_trabajos(texto)
    for id_trabajo in ("revision", "publicar"):
        if id_trabajo not in trabajos:
            problemas.append(f"no declara el trabajo `{id_trabajo}`")
            continue
        lista = pasos(trabajos[id_trabajo])
        indices = [i for i, paso in enumerate(lista) if (valor_del_paso(paso, "uses") or "").startswith("actions/checkout@")]
        if not indices:
            problemas.append(f"'{id_trabajo}': falta actions/checkout de la base")
            continue
        if indices[0] != 0:
            problemas.append(f"'{id_trabajo}': el checkout debe ser el primer paso: lo que se ejecuta después sale de la base")
        for i in indices:
            paso = lista[i]
            refs = _claves_del_bloque(paso, "with").get("ref", [])
            if len(refs) != 1:
                problemas.append(
                    f"'{id_trabajo}': el checkout debe llevar `ref: {REF_DE_LA_BASE}` exactamente una vez y lo lleva {len(refs)} veces"
                )
            elif _normalizada(refs[0]) != _normalizada(REF_DE_LA_BASE):
                problemas.append(
                    f"'{id_trabajo}': el checkout debe leer la base (`ref: {REF_DE_LA_BASE}`) y no el PR; lleva `ref: {refs[0]}`"
                )
            if not CHECKOUT_POR_SHA.fullmatch(valor_del_paso(paso, "uses") or ""):
                problemas.append(f"'{id_trabajo}': actions/checkout debe fijarse por el SHA de 40 caracteres de su commit")
            if not SIN_CREDENCIALES.search(valor_del_paso(paso, "with") or ""):
                problemas.append(f"'{id_trabajo}': actions/checkout debe llevar `persist-credentials: false`")
    paso_de_claude = _paso_de_claude(texto)
    if paso_de_claude is None:
        problemas.append("el trabajo `revision` no tiene el paso de anthropics/claude-code-action")
    else:
        prompts = _claves_del_bloque(paso_de_claude, "with").get("prompt", [])
        if len(prompts) != 1 or INSTRUCCIONES_DEL_MODELO not in prompts[0]:
            problemas.append(f"el `prompt` debe nombrar `{INSTRUCCIONES_DEL_MODELO}`: de la base salen las instrucciones, no del PR")
    return problemas


def comprobar_publicar(texto: str) -> list[str]:
    """TC62-26 · CA-5 esc. 2. `publicar` no publica nada que no haya pasado por `tools/publicar_revision.py`."""
    problemas: list[str] = []
    trabajos = extraer_trabajos(texto)
    if "revision" not in trabajos:
        problemas.append("no declara el trabajo `revision`")
    else:
        salidas = [
            linea.split(":", 1)[1]
            for linea in (valor_del_trabajo(trabajos["revision"], "outputs") or "").splitlines()
            if re.match(r"hallazgos\s*:", linea)
        ]
        if [_normalizada(s) for s in salidas] != [_normalizada(SALIDA_DEL_MODELO)]:
            problemas.append(f"`outputs.hallazgos` de `revision` debe valer `{SALIDA_DEL_MODELO}` y vale {salidas!r}")
    if "publicar" not in trabajos:
        return problemas + ["no declara el trabajo `publicar`"]
    bloque = trabajos["publicar"]
    if ids_de_needs(bloque) != ["revision"]:
        problemas.append(f"'publicar': `needs:` debe ser solo `revision` y es {ids_de_needs(bloque)!r}")
    if valor_del_trabajo(bloque, "if") is not None:
        problemas.append("'publicar': no lleva `if:`; con `needs: revision`, si la revisión se omite o falla, `publicar` se omite sola")
    if LECTURA_DE_SECRETOS.search("\n".join(bloque)):
        problemas.append("'publicar': lee secrets.; el trabajo que publica no necesita ningún secreto")
    lista = pasos(bloque)
    i_archivos = _indice_del_paso(lista, r"\bgh api\b")
    i_filtro = _indice_del_paso(lista, r"\bpython3 tools/publicar_revision\.py\b")
    i_comentario = _indice_del_paso(lista, r"\bgh pr comment\b")
    if i_archivos is None:
        problemas.append("falta el paso «Archivos del PR» con `gh api`")
    else:
        orden = comando(lista[i_archivos])
        if "--paginate" not in orden:
            problemas.append("«Archivos del PR» debe usar `gh api --paginate`: un PR grande tiene más de una página de archivos")
        if not re.search(r"/pulls/\$PR/files\b", orden):
            problemas.append("«Archivos del PR» debe pedir `repos/$GH_REPO/pulls/$PR/files`")
        if not re.search(r">\s*\"?\$RUNNER_TEMP/archivos\.txt\"?", orden):
            problemas.append("«Archivos del PR» debe escribir `$RUNNER_TEMP/archivos.txt`")
    if i_filtro is None:
        problemas.append("falta el paso que ejecuta `python3 tools/publicar_revision.py`")
    else:
        paso = lista[i_filtro]
        orden = comando(paso)
        if not re.search(r"--archivos\s+\"?\$RUNNER_TEMP/archivos\.txt\"?", orden):
            problemas.append("el filtro debe recibir `--archivos \"$RUNNER_TEMP/archivos.txt\"`")
        if not re.search(r"--salida\s+\"?\$RUNNER_TEMP/comentario\.md\"?", orden):
            problemas.append("el filtro debe escribir `--salida \"$RUNNER_TEMP/comentario.md\"`")
        variables = _claves_del_bloque(paso, "env")
        hallazgos = variables.get("HALLAZGOS", [])
        if [_normalizada(h) for h in hallazgos] != [_normalizada(HALLAZGOS_DE_REVISION)]:
            problemas.append(f"el filtro debe recibir `HALLAZGOS: {HALLAZGOS_DE_REVISION}` exactamente una vez y recibe {hallazgos!r}")
        for variable, expresion in (
            ("TITULO", "${{ github.event.pull_request.title }}"),
            ("CUERPO", "${{ github.event.pull_request.body }}"),
            ("CABEZA", "${{ github.event.pull_request.head.sha }}"),
        ):
            valores = variables.get(variable, [])
            if [_normalizada(v) for v in valores] != [_normalizada(expresion)]:
                problemas.append(f"el filtro debe recibir `{variable}: {expresion}` por `env:` y recibe {valores!r}")
    if i_comentario is None:
        problemas.append("falta el paso que ejecuta `gh pr comment`")
    else:
        orden = comando(lista[i_comentario])
        if not re.search(r"--body-file\s+\"?\$RUNNER_TEMP/comentario\.md\"?", orden):
            problemas.append("`gh pr comment` debe publicar `--body-file \"$RUNNER_TEMP/comentario.md\"`, el archivo que escribió el filtro")
        if re.search(r"--body(?![-\w])", orden):
            problemas.append("`gh pr comment` publica con `--body`: el texto no pasó por el filtro")
    for paso in lista:
        if re.search(r"\bHALLAZGOS\b", comando(paso)):
            problemas.append("un `run:` de `publicar` usa HALLAZGOS directamente: el texto del modelo se publicaría sin pasar por el filtro")
    if None not in (i_archivos, i_filtro, i_comentario) and not (i_archivos < i_filtro < i_comentario):  # type: ignore[operator]
        problemas.append("los pasos de `publicar` deben ir en el orden «Archivos del PR», filtro, `gh pr comment`")
    return problemas


def comprobar_topes(texto: str) -> list[str]:
    """TC62-33 · CA-10 esc. 1. Tiempo, turnos, modelo y esquema acotados."""
    problemas: list[str] = []
    trabajos = extraer_trabajos(texto)
    for id_trabajo in ("revision", "publicar"):
        if id_trabajo not in trabajos:
            problemas.append(f"no declara el trabajo `{id_trabajo}`")
            continue
        tiempo = valor_del_trabajo(trabajos[id_trabajo], "timeout-minutes")
        if tiempo != str(TIEMPO_POR_TRABAJO[id_trabajo]):
            problemas.append(f"'{id_trabajo}': timeout-minutes debe ser {TIEMPO_POR_TRABAJO[id_trabajo]} y es {tiempo!r}")
    banderas, de_lectura = _banderas_del_modelo(texto)
    if banderas is None:
        return problemas + de_lectura
    for bandera, esperado in (("--max-turns", "20"), ("--model", "sonnet")):
        valores = banderas.get(bandera, [])
        if valores != [esperado]:
            problemas.append(f"`{bandera}` debe ser {esperado} (una sola vez) y es {valores or 'ausente'}")
    esquemas = banderas.get("--json-schema", [])
    if len(esquemas) != 1 or esquemas[0] is None:
        problemas.append(f"`--json-schema` debe declararse exactamente una vez, con valor, y se declara {len(esquemas)} veces")
    else:
        try:
            esquema = json.loads(esquemas[0])
        except ValueError:
            esquema = None
        if not isinstance(esquema, dict) or "hallazgos" not in esquema.get("required", []):
            problemas.append("`--json-schema` debe ser un esquema JSON que exija `hallazgos`")
    return problemas


def comprobar_solo_la_revision_lee_la_clave(flujos: dict[str, str]) -> list[str]:
    """TC62-27 · CA-7 esc. 1. `flujos` es nombre de archivo -> texto. Solo `revision-ia.yml` lee un secreto, y es `USO_PERMITIDO_DEL_SECRETO` en su sitio."""
    problemas: list[str] = []
    if FLUJO_DE_REVISION not in flujos:
        problemas.append(f"falta {FLUJO_DE_REVISION}: sin él nadie lee la clave y la revisión no tiene credencial")
    ajenos = sorted(
        nombre
        for nombre, texto in flujos.items()
        if nombre != FLUJO_DE_REVISION and any(LECTURA_DE_SECRETOS.search(linea) for linea in sin_comentarios(texto).splitlines())
    )
    if ajenos:
        problemas.append(f"lee secrets. fuera de la revisión: {', '.join(ajenos)}")
    if FLUJO_DE_REVISION in flujos:
        texto = flujos[FLUJO_DE_REVISION]
        lecturas = [linea for linea in sin_comentarios(texto).splitlines() if LECTURA_DE_SECRETOS.search(linea)]
        if len(lecturas) != 1 or _normalizada(lecturas[0]) != _normalizada(USO_PERMITIDO_DEL_SECRETO):
            problemas.append(
                f"{FLUJO_DE_REVISION}: la única lectura de secrets. debe ser `{USO_PERMITIDO_DEL_SECRETO}` y son {len(lecturas)}: {lecturas!r}"
            )
        paso = _paso_de_claude(texto)
        valor_permitido = _normalizada(USO_PERMITIDO_DEL_SECRETO.split(":", 1)[1])
        if paso is None or [_normalizada(v) for v in _claves_del_bloque(paso, "with").get("anthropic_api_key", [])] != [valor_permitido]:
            problemas.append(
                f"{FLUJO_DE_REVISION}: la clave solo se lee en `anthropic_api_key` del `with:` del paso de claude-code-action del trabajo `revision`"
            )
        problemas += [f"{FLUJO_DE_REVISION}: {motivo}" for motivo in motivos_de_secretos(FLUJO_DE_REVISION, texto)]
    return problemas


# ---------------------------------------------------------------------------------------------------------
# Texto sintético: `revision-ia.yml` tal como lo fija el diseño, y sus piezas para fabricar mutantes
# ---------------------------------------------------------------------------------------------------------

SHA_DEL_CHECKOUT = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SHA_DE_LA_ACCION = "0123456789abcdef0123456789abcdef01234567"
ESQUEMA_DE_SALIDA = (
    '{"type":"object","properties":{"hallazgos":{"type":"array","items":{"type":"object","properties":'
    '{"archivo":{"type":"string"},"linea":{"type":"integer"},"texto":{"type":"string"},"cita":{"type":"string"}},'
    '"required":["archivo","texto","cita"]}}},"required":["hallazgos"]}'
)

LINEA_DEL_IF = "    if: " + GUARDA_DE_REVISION + "\n"
LINEA_DE_TIPOS = "    types: [opened, synchronize, ready_for_review, reopened]\n"
COMENTARIO_DE_ESCRITURA = (
    "      # Publica un único comentario con los hallazgos citados. No basta para aprobar: el ajuste del repositorio lo impide (ADR-028).\n"
)
LINEA_DE_ESCRITURA = "      pull-requests: write\n"
CHECKOUT_DE_REVISION = (
    f"      - uses: actions/checkout@{SHA_DEL_CHECKOUT} # v7.0.1\n"
    "        with:\n"
    "          ref: ${{ github.event.pull_request.base.sha }}\n"
    "          persist-credentials: false\n"
    "          fetch-depth: 1\n"
)
CHECKOUT_DE_PUBLICAR = (
    f"      - uses: actions/checkout@{SHA_DEL_CHECKOUT} # v7.0.1\n"
    "        with:\n"
    "          ref: ${{ github.event.pull_request.base.sha }}\n"
    "          persist-credentials: false\n"
)
USO_DE_LA_ACCION = f"        uses: anthropics/claude-code-action@{SHA_DE_LA_ACCION} # v1.0.9\n"
PASO_DE_CLAUDE_CON_ID = "      - id: claude\n" + USO_DE_LA_ACCION
LINEA_DE_LA_CLAVE = "          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}\n"
LINEA_DEL_TOKEN = "          github_token: ${{ github.token }}\n"
LINEA_DEL_PROMPT = (
    "          prompt: Revisa el pull request número ${{ github.event.pull_request.number }} del repositorio "
    "${{ github.repository }} siguiendo .claude/revision-pr.md. Devuelve solo la salida estructurada.\n"
)
LINEA_DEL_MODELO = "            --model sonnet\n"
LINEA_DE_LOS_TURNOS = "            --max-turns 20\n"
LINEA_DE_LAS_PERMITIDAS = '            --allowedTools "Read(./**),Glob,Grep"\n'
LINEA_DE_LAS_PROHIBIDAS = (
    '            --disallowedTools "Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch,Bash,Read(//proc/**),Read(//sys/**)"\n'
)
LINEA_DEL_ESQUEMA = f"            --json-schema '{ESQUEMA_DE_SALIDA}'\n"
PASO_DE_CLAUDE = (
    PASO_DE_CLAUDE_CON_ID
    + "        with:\n"
    + LINEA_DE_LA_CLAVE
    + LINEA_DEL_TOKEN
    + LINEA_DEL_PROMPT
    + "          claude_args: |\n"
    + LINEA_DEL_MODELO
    + LINEA_DE_LOS_TURNOS
    + LINEA_DE_LAS_PERMITIDAS
    + LINEA_DE_LAS_PROHIBIDAS
    + LINEA_DEL_ESQUEMA
)
ENV_DE_GH = (
    "        env:\n"
    "          GH_TOKEN: ${{ github.token }}\n"
    "          GH_REPO: ${{ github.repository }}\n"
    "          PR: ${{ github.event.pull_request.number }}\n"
)
LINEA_DEL_MKDIR = "          mkdir -p .revision-pr\n"
LINEA_DEL_JSON = '          gh pr view "$PR" --json title,body,files > .revision-pr/pr.json\n'
LINEA_DEL_DIFF = '          gh pr diff "$PR" > .revision-pr/pr.diff\n'
PASO_DE_METADATOS = (
    "      - name: Metadatos y diff del PR\n" + ENV_DE_GH + "        run: |\n" + LINEA_DEL_MKDIR + LINEA_DEL_JSON + LINEA_DEL_DIFF
)
PASO_DE_ARCHIVOS = (
    "      - name: Archivos del PR\n"
    + ENV_DE_GH
    + "        run: gh api --paginate \"repos/$GH_REPO/pulls/$PR/files\" --jq '.[].filename' > \"$RUNNER_TEMP/archivos.txt\"\n"
)
PASO_DEL_FILTRO = (
    "      - name: Filtrar los hallazgos por su cita\n"
    "        env:\n"
    "          HALLAZGOS: ${{ needs.revision.outputs.hallazgos }}\n"
    "          TITULO: ${{ github.event.pull_request.title }}\n"
    "          CUERPO: ${{ github.event.pull_request.body }}\n"
    "          CABEZA: ${{ github.event.pull_request.head.sha }}\n"
    '        run: python3 tools/publicar_revision.py --archivos "$RUNNER_TEMP/archivos.txt" --salida "$RUNNER_TEMP/comentario.md"\n'
)
PASO_DEL_COMENTARIO = (
    "      - name: Publicar el comentario\n"
    + ENV_DE_GH
    + '        run: gh pr comment "$PR" --body-file "$RUNNER_TEMP/comentario.md"\n'
)

REVISION_COMPLETA = (
    """\
name: Revisión IA
# TKT-062b · ADR-028. Comenta y nunca aprueba ni bloquea: no es una comprobación requerida.
on:
  pull_request:
"""
    + LINEA_DE_TIPOS
    + """\
permissions:
  contents: read
jobs:
  revision:
    name: Revisión IA · lectura del PR
"""
    + LINEA_DEL_IF
    + """\
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: read
      pull-requests: read
    outputs:
      hallazgos: ${{ steps.claude.outputs.structured_output }}
    steps:
"""
    + CHECKOUT_DE_REVISION
    + PASO_DE_METADATOS
    + PASO_DE_CLAUDE
    + """\
  publicar:
    name: Revisión IA · publicar los hallazgos con cita
    needs: revision
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
"""
    + COMENTARIO_DE_ESCRITURA
    + LINEA_DE_ESCRITURA
    + "    steps:\n"
    + CHECKOUT_DE_PUBLICAR
    + PASO_DE_ARCHIVOS
    + PASO_DEL_FILTRO
    + PASO_DEL_COMENTARIO
)

FLUJOS_SINTETICOS = {
    "ci.yml": CI_A4,
    "enlaces.yml": ENLACES_SINTETICO,
    "etiqueta-origen.yml": ETIQUETA_SINTETICA,
    FLUJO_DE_REVISION: REVISION_COMPLETA,
}

TRABAJO_DE_REVISION_EN_CI = (
    "  revision:\n    name: Revisión\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    steps:\n      - run: echo revisar\n"
)

COMPROBACIONES_DE_LA_REVISION = (
    comprobar_disparo_y_accion,
    comprobar_guarda,
    comprobar_permisos_y_token,
    comprobar_herramientas_del_modelo,
    comprobar_metadatos_del_pr,
    comprobar_checkout_de_la_base,
    comprobar_publicar,
    comprobar_topes,
)


def _con_guarda(nueva: str) -> str:
    return sustituir(REVISION_COMPLETA, LINEA_DEL_IF, "    if: " + nueva + "\n")


def _con_args(viejo: str, nuevo: str) -> str:
    return sustituir(REVISION_COMPLETA, viejo, nuevo)


def _en_publicar(viejo: str, nuevo: str) -> str:
    return mutar(REVISION_COMPLETA, "publicar", viejo, nuevo)


def _en_revision(viejo: str, nuevo: str) -> str:
    return mutar(REVISION_COMPLETA, "revision", viejo, nuevo)


# ---------------------------------------------------------------------------------------------------------
# Mutantes sobre texto sintético
# ---------------------------------------------------------------------------------------------------------


class PruebasDeMutantesDelFlujoDeRevision(unittest.TestCase):
    """TC62-10 a TC62-33: cada propiedad que fija el diseño se pone en rojo cuando se estropea, y por la razón esperada."""

    # --- controles -----------------------------------------------------------------------------------------

    def test_tkt062_ca01_esc01_mutantes_el_control_valido_pasa(self):
        """CA-1 esc. 1 · TC62-10 (control) — el flujo sintético válido pasa cada comprobación de este módulo, las reglas comunes,
        TC-13, TC-21 y TC-22 de TKT-009; sin esto, un mutante «en rojo» podría estarlo por culpa del texto base."""
        for comprobacion in COMPROBACIONES_DE_LA_REVISION:
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(REVISION_COMPLETA), [])
        self.assertEqual(comprobar_que_ci_no_aloja_la_revision(CI_A4), [])
        self.assertEqual(comprobar_solo_la_revision_lee_la_clave(FLUJOS_SINTETICOS), [])
        self.assertEqual(comprobar_reglas_comunes_de_todo_flujo(FLUJOS_SINTETICOS), [])
        for comprobacion in (comprobar_tc13, comprobar_tc21, comprobar_tc22):
            with self.subTest(comprobacion=comprobacion.__name__):
                self.assertEqual(comprobacion(FLUJOS_SINTETICOS), [])

    # --- TC62-10 -------------------------------------------------------------------------------------------

    def test_tkt062_ca01_esc01_mutantes_los_disparadores_y_la_accion(self):
        """CA-1 esc. 1 · TC62-10 — quitar `ready_for_review` (un borrador marcado como listo nunca se revisaría), `synchronize`, `opened` o
        `reopened`, añadir `labeled`, no declarar `types:`, disparar con `pull_request_target`, fijar la acción por etiqueta de versión,
        quitarle `id: claude` o la etiqueta de versión, o usar otra acción es rojo."""

        def con_tipos(nuevos: str) -> str:
            return sustituir(REVISION_COMPLETA, LINEA_DE_TIPOS, f"    types: [{nuevos}]\n")

        sin_id = sustituir(REVISION_COMPLETA, PASO_DE_CLAUDE_CON_ID, "      - " + USO_DE_LA_ACCION.lstrip())
        casos = {
            "sin ready_for_review": (con_tipos("opened, synchronize, reopened"), "`types:` debe ser exactamente"),
            "sin synchronize": (con_tipos("opened, ready_for_review, reopened"), "`types:` debe ser exactamente"),
            "sin opened": (con_tipos("synchronize, ready_for_review, reopened"), "`types:` debe ser exactamente"),
            "sin reopened": (con_tipos("opened, synchronize, ready_for_review"), "`types:` debe ser exactamente"),
            "con labeled de más": (
                con_tipos("opened, synchronize, ready_for_review, reopened, labeled"),
                "`types:` debe ser exactamente",
            ),
            "sin types": (sustituir(REVISION_COMPLETA, LINEA_DE_TIPOS, ""), "no declara `types:`"),
            "pull_request_target": (
                sustituir(REVISION_COMPLETA, "on:\n  pull_request:\n", "on:\n  pull_request_target:\n"),
                "pull_request_target",
            ),
            "la acción por etiqueta de versión": (
                sustituir(REVISION_COMPLETA, f"claude-code-action@{SHA_DE_LA_ACCION} # v1.0.9", "claude-code-action@v1 # v1.0.9"),
                "debe fijarse por el SHA",
            ),
            "la acción sin la etiqueta de versión": (
                sustituir(REVISION_COMPLETA, f"claude-code-action@{SHA_DE_LA_ACCION} # v1.0.9", f"claude-code-action@{SHA_DE_LA_ACCION}"),
                "etiqueta de versión en un comentario",
            ),
            "el checkout sin la etiqueta de versión": (
                mutar(REVISION_COMPLETA, "publicar", f"actions/checkout@{SHA_DEL_CHECKOUT} # v7.0.1", f"actions/checkout@{SHA_DEL_CHECKOUT}"),
                "etiqueta de versión en un comentario",
            ),
            "sin id": (sin_id, "debe llevar `id: claude`"),
            "otro id": (sustituir(REVISION_COMPLETA, "      - id: claude\n", "      - id: revisar\n"), "debe llevar `id: claude`"),
            "otra acción": (
                sustituir(REVISION_COMPLETA, "uses: anthropics/claude-code-action@", "uses: otros/claude-code-action@"),
                "debe tener exactamente un paso con `uses: anthropics/claude-code-action@",
            ),
            "sin el trabajo revision": (
                sustituir(REVISION_COMPLETA, "\n  revision:\n", "\n  revisar:\n"),
                "no declara el trabajo `revision`",
            ),
            "la acción también en publicar": (
                _en_publicar(PASO_DE_ARCHIVOS, PASO_DE_ARCHIVOS + PASO_DE_CLAUDE),
                "usa claude-code-action; solo `revision` puede usarla",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_disparo_y_accion, casos)

    def test_tkt062_ca01_esc01_mutantes_ci_no_aloja_la_revision(self):
        """CA-1 esc. 1 · TC62-10 — un trabajo `revision` o `publicar` en `ci.yml`, o la acción usada ahí, es rojo: la revisión no es el pipeline."""
        casos = {
            "trabajo revision en ci.yml": (CI_A4 + TRABAJO_DE_REVISION_EN_CI, "ci.yml: declara el trabajo 'revision'"),
            "trabajo publicar en ci.yml": (
                CI_A4 + TRABAJO_DE_REVISION_EN_CI.replace("revision:", "publicar:"),
                "ci.yml: declara el trabajo 'publicar'",
            ),
            "la acción en ci.yml": (
                CI_A4 + f"      - uses: anthropics/claude-code-action@{SHA_DE_LA_ACCION} # v1.0.9\n",
                "ci.yml: usa claude-code-action",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_que_ci_no_aloja_la_revision, casos)

    # --- TC62-11 -------------------------------------------------------------------------------------------

    def test_tkt062_ca02_esc01_mutantes_la_guarda(self):
        """CA-2 esc. 1 y 2 · TC62-11 — sin `draft == false`, sin `full_name`, sin la exclusión de Dependabot, `github.actor` en lugar de
        `user.login`, `||` en lugar de `&&`, la comparación de Dependabot invertida, la guarda envuelta en `${{ }}` o entre comillas,
        sin `if:` y la guarda movida a un paso son rojo."""
        sin_if = sustituir(REVISION_COMPLETA, LINEA_DEL_IF, "")
        casos = {
            "sin draft == false": _con_guarda(GUARDA_DE_REVISION.replace("github.event.pull_request.draft == false && ", "")),
            "draft == true": _con_guarda(GUARDA_DE_REVISION.replace("draft == false", "draft == true")),
            "sin full_name": _con_guarda(
                GUARDA_DE_REVISION.replace("github.event.pull_request.head.repo.full_name == github.repository && ", "")
            ),
            "full_name sin comparar con el repositorio": _con_guarda(
                GUARDA_DE_REVISION.replace("full_name == github.repository", "full_name != github.repository")
            ),
            "sin la exclusión de Dependabot": _con_guarda(
                GUARDA_DE_REVISION.replace(" && github.event.pull_request.user.login != 'dependabot[bot]'", "")
            ),
            "github.actor en lugar de user.login": _con_guarda(
                GUARDA_DE_REVISION.replace("github.event.pull_request.user.login", "github.actor")
            ),
            "|| en lugar de &&": _con_guarda(GUARDA_DE_REVISION.replace("&&", "||")),
            "== dependabot en lugar de !=": _con_guarda(GUARDA_DE_REVISION.replace("!= 'dependabot[bot]'", "== 'dependabot[bot]'")),
            "dependabot[bot] sin comillas": _con_guarda(GUARDA_DE_REVISION.replace("'dependabot[bot]'", "dependabot[bot]")),
            "envuelta en ${{ }}": _con_guarda("${{ " + GUARDA_DE_REVISION + " }}"),
            "entre comillas dobles": _con_guarda('"' + GUARDA_DE_REVISION + '"'),
            "sin if": sin_if,
            "la guarda movida a un paso": sustituir(
                sin_if, PASO_DE_CLAUDE_CON_ID, "      - id: claude\n        if: " + GUARDA_DE_REVISION + "\n" + USO_DE_LA_ACCION
            ),
            "sin el trabajo revision": (
                sustituir(REVISION_COMPLETA, "\n  revision:\n", "\n  revisar:\n"),
                "no declara el trabajo `revision`",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_guarda, casos, "`if:` a nivel de trabajo de `revision`")

    def test_tkt062_ca02_esc01_mutantes_la_guarda_se_compara_con_normalizada_y_no_con_expresion_de_if(self):
        """CA-2 esc. 1 · TC62-11 — `_expresion_de_if` hace `.strip("\\"'")` y se comería la comilla final de `'dependabot[bot]'`: compararla así
        haría fallar siempre a la guarda válida. La comprobación usa `_normalizada`, que solo quita los espacios, y la guarda válida pasa."""
        self.assertNotEqual(_expresion_de_if(GUARDA_DE_REVISION), _normalizada(GUARDA_DE_REVISION))
        self.assertEqual(comprobar_guarda(REVISION_COMPLETA), [])
        con_espacios = _con_guarda(GUARDA_DE_REVISION.replace(" && ", "  &&  "))
        self.assertEqual(comprobar_guarda(con_espacios), [], "los espacios no cambian la guarda")

    # --- TC62-13 -------------------------------------------------------------------------------------------

    def test_tkt062_ca03_esc01_mutantes_permisos_y_token(self):
        """CA-3 esc. 1 · TC62-13 — `id-token: write`, `pull-requests: write` en `revision`, `contents: write` en `publicar`, `issues: write` sin
        comentario, `actions` o `checks`, el `: write` sin el comentario que lo justifica, permisos que faltan o de más, y un token que no es
        `github.token` son rojo."""
        sin_permisos_de_revision = _en_revision("    permissions:\n      contents: read\n      pull-requests: read\n", "")
        casos = {
            "id-token: write en revision": (
                _en_revision("      pull-requests: read\n", "      pull-requests: read\n      id-token: write\n"),
                "id-token",
            ),
            "id-token: write en publicar": (_en_publicar(LINEA_DE_ESCRITURA, LINEA_DE_ESCRITURA + "      id-token: write\n"), "id-token"),
            "id-token: write a nivel de flujo": (
                sustituir(REVISION_COMPLETA, "permissions:\n  contents: read\njobs:", "permissions:\n  contents: read\n  id-token: write\njobs:"),
                "id-token",
            ),
            "pull-requests: write en revision": (
                _en_revision("      pull-requests: read\n", COMENTARIO_DE_ESCRITURA + LINEA_DE_ESCRITURA),
                "'revision': `permissions:` debe ser exactamente",
            ),
            "contents: write en publicar": (
                _en_publicar("      contents: read\n", "      contents: write\n"),
                "contents: write",
            ),
            "contents: write en revision": (
                _en_revision("      contents: read\n", "      contents: write\n"),
                "contents: write",
            ),
            "contents: write a nivel de flujo": (
                sustituir(REVISION_COMPLETA, "permissions:\n  contents: read\njobs:", "permissions:\n  contents: write\njobs:"),
                "`permissions:` a nivel de flujo debe ser solo `contents: read`",
            ),
            "issues: write sin comentario": (
                _en_publicar(LINEA_DE_ESCRITURA, LINEA_DE_ESCRITURA + "      issues: write\n"),
                "issues",
            ),
            "actions: read": (
                _en_revision("      pull-requests: read\n", "      pull-requests: read\n      actions: read\n"),
                "`actions`",
            ),
            "checks: write": (
                _en_publicar(LINEA_DE_ESCRITURA, LINEA_DE_ESCRITURA + "      checks: write\n"),
                "`checks`",
            ),
            "pull-requests: write sin el comentario": (
                sustituir(REVISION_COMPLETA, COMENTARIO_DE_ESCRITURA, ""),
                "debe llevar en la línea anterior un comentario",
            ),
            "publicar sin pull-requests": (
                _en_publicar(COMENTARIO_DE_ESCRITURA + LINEA_DE_ESCRITURA, ""),
                "'publicar': `permissions:` debe ser exactamente",
            ),
            "revision sin permisos propios": (sin_permisos_de_revision, "'revision': `permissions:` debe ser exactamente"),
            "revision sin pull-requests": (
                _en_revision("      pull-requests: read\n", ""),
                "'revision': `permissions:` debe ser exactamente",
            ),
            "github_token con el secreto del repositorio": (
                _con_args(LINEA_DEL_TOKEN, "          github_token: ${{ secrets.GITHUB_TOKEN }}\n"),
                "github_token",
            ),
            "github_token con otro valor": (
                _con_args(LINEA_DEL_TOKEN, "          github_token: ${{ secrets.OTRO }}\n"),
                "github_token",
            ),
            "sin github_token": (_con_args(LINEA_DEL_TOKEN, ""), "debe declarar `github_token: ${{ github.token }}`"),
            "GH_TOKEN del paso de metadatos de revision con el secreto": (
                _en_revision(
                    PASO_DE_METADATOS, PASO_DE_METADATOS.replace("GH_TOKEN: ${{ github.token }}", "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}")
                ),
                "todo token debe ser `${{ github.token }}`",
            ),
            "GH_TOKEN de publicar con el secreto": (
                _en_publicar(
                    "          GH_TOKEN: ${{ github.token }}\n          GH_REPO: ${{ github.repository }}\n          PR: ${{ github.event.pull_request.number }}\n        run: gh api",
                    "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n          GH_REPO: ${{ github.repository }}\n          PR: ${{ github.event.pull_request.number }}\n        run: gh api",
                ),
                "todo token debe ser `${{ github.token }}`",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_permisos_y_token, casos)

    # --- TC62-14 -------------------------------------------------------------------------------------------

    def test_tkt062_ca03_esc03_mutantes_el_modelo_no_tiene_herramientas_de_escritura(self):
        """CA-3 esc. 3 · TC62-14 (F001) — permitir cualquier `Bash` (también el `Bash(gh pr view:*)` de antes del ajuste del 2026-10-30), quitar
        `Bash`, `Read(//proc/**)` o `Read(//sys/**)` de `--disallowedTools`, añadir `Bash(gh pr review:*)`, `Bash(gh pr comment:*)` o
        `Bash(gh api:*)`, `Read(./**)` cambiado por `Read`, `Edit` o `Write` quitados de `--disallowedTools`, herramientas de escritura
        permitidas, banderas o entradas del `with:` de más y las banderas declaradas dos veces son rojo."""
        permitidas = LINEA_DE_LAS_PERMITIDAS
        prohibidas = LINEA_DE_LAS_PROHIBIDAS

        def permite(nueva: str) -> str:
            return sustituir(REVISION_COMPLETA, permitidas, permitidas.replace('Grep"', f'Grep,{nueva}"'))

        casos = {
            "Bash(gh pr view:*) permitido (la configuración anterior a F001)": (
                permite("Bash(gh pr view:*)"),
                "permite `Bash`",
            ),
            "Bash(gh pr diff:*) permitido": (permite("Bash(gh pr diff:*)"), "permite `Bash`"),
            "Bash a secas permitido, reportado como Bash": (permite("Bash"), "permite `Bash`"),
            "Bash quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace(",Bash", "")),
                "`--disallowedTools` debe incluir `Bash`",
            ),
            "Read(//proc/**) quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace(",Read(//proc/**)", "")),
                "`--disallowedTools` debe incluir `Read(//proc/**)`",
            ),
            "Read(//sys/**) quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace(",Read(//sys/**)", "")),
                "`--disallowedTools` debe incluir `Read(//sys/**)`",
            ),
            "Bash(gh pr review:*) permitido": (permite("Bash(gh pr review:*)"), "permite `gh pr review`"),
            "Bash(gh pr comment:*) permitido": (permite("Bash(gh pr comment:*)"), "permite `gh pr comment`"),
            "Bash(gh api:*) permitido": (permite("Bash(gh api:*)"), "permite `gh api`"),
            "Bash a secas permitido": (permite("Bash"), "`--allowedTools` debe ser exactamente"),
            "Edit permitido": (permite("Edit"), "`--allowedTools` debe ser exactamente"),
            "Write permitido": (permite("Write"), "`--allowedTools` debe ser exactamente"),
            "Read a secas": (
                sustituir(REVISION_COMPLETA, permitidas, permitidas.replace("Read(./**)", "Read")),
                "`Read(./**)`",
            ),
            "Read(./**) quitado": (
                sustituir(REVISION_COMPLETA, permitidas, permitidas.replace("Read(./**),", "")),
                "`--allowedTools` debe ser exactamente",
            ),
            "Grep quitado": (
                sustituir(REVISION_COMPLETA, permitidas, permitidas.replace(",Grep", "")),
                "`--allowedTools` debe ser exactamente",
            ),
            "sin --allowedTools": (sustituir(REVISION_COMPLETA, permitidas, ""), "`--allowedTools` debe declararse exactamente una vez"),
            "--allowedTools dos veces": (
                sustituir(REVISION_COMPLETA, permitidas, permitidas + permitidas.replace("Read(./**),", "")),
                "`--allowedTools` debe declararse exactamente una vez",
            ),
            "Edit quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace("Edit,", "")),
                "`--disallowedTools` debe incluir `Edit`",
            ),
            "Write quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace("Write,", "")),
                "`--disallowedTools` debe incluir `Write`",
            ),
            "MultiEdit quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace("MultiEdit,", "")),
                "`--disallowedTools` debe incluir `MultiEdit`",
            ),
            "WebFetch quitado de --disallowedTools": (
                sustituir(REVISION_COMPLETA, prohibidas, prohibidas.replace(",WebFetch", "")),
                "`--disallowedTools` debe incluir `WebFetch`",
            ),
            "sin --disallowedTools": (sustituir(REVISION_COMPLETA, prohibidas, ""), "`--disallowedTools` debe declararse exactamente una vez"),
            "--dangerously-skip-permissions": (
                sustituir(REVISION_COMPLETA, LINEA_DEL_MODELO, LINEA_DEL_MODELO + "            --dangerously-skip-permissions\n"),
                "--dangerously-skip-permissions",
            ),
            "--permission-mode": (
                sustituir(REVISION_COMPLETA, LINEA_DEL_MODELO, LINEA_DEL_MODELO + "            --permission-mode acceptEdits\n"),
                "--permission-mode",
            ),
            "entrada allowed_tools en el with": (
                sustituir(REVISION_COMPLETA, LINEA_DEL_TOKEN, LINEA_DEL_TOKEN + "          allowed_tools: Bash\n"),
                "entradas fuera de",
            ),
            "entrada use_oidc en el with": (
                sustituir(REVISION_COMPLETA, LINEA_DEL_TOKEN, LINEA_DEL_TOKEN + "          use_oidc: true\n"),
                "entradas fuera de",
            ),
            "sin claude_args": (
                sustituir(
                    REVISION_COMPLETA,
                    PASO_DE_CLAUDE.split("          claude_args: |\n")[1],
                    "",
                ).replace("          claude_args: |\n", ""),
                "debe declarar `claude_args` exactamente una vez",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_herramientas_del_modelo, casos)

    def test_tkt062_ca03_esc03_mutantes_los_metadatos_del_pr_se_escriben_antes_de_la_accion_y_sin_secretos(self):
        """CA-3 esc. 3 · TC62-14 (F001) — sin `Bash` el modelo lee `.revision-pr/pr.json` y `.revision-pr/pr.diff`: el paso que los escribe falta,
        va después de la acción, lee un secreto, recibe `GH_TOKEN`, `GH_REPO` o `PR` de otro sitio o no los recibe, no crea la carpeta o
        escribe otra ruta, otros campos o ningún diff es rojo."""
        paso_con_secreto = PASO_DE_METADATOS.replace(
            "          PR: ${{ github.event.pull_request.number }}\n", "          PR: ${{ github.event.pull_request.number }}\n          X: ${{ secrets.ANTHROPIC_API_KEY }}\n"
        )
        casos = {
            "el paso ausente": (_en_revision(PASO_DE_METADATOS, ""), "falta el paso de `revision` que escribe `.revision-pr/pr.json`"),
            "el paso después de la acción": (
                _en_revision(PASO_DE_METADATOS + PASO_DE_CLAUDE, PASO_DE_CLAUDE + PASO_DE_METADATOS),
                "debe ir antes del paso de claude-code-action",
            ),
            "un secreto en el paso": (_en_revision(PASO_DE_METADATOS, paso_con_secreto), "el paso de metadatos lee secrets."),
            "GH_TOKEN con el secreto del repositorio": (
                _en_revision(
                    PASO_DE_METADATOS, PASO_DE_METADATOS.replace("GH_TOKEN: ${{ github.token }}", "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}")
                ),
                "`GH_TOKEN: ${{ github.token }}`",
            ),
            "sin GH_TOKEN": (
                _en_revision(PASO_DE_METADATOS, PASO_DE_METADATOS.replace("          GH_TOKEN: ${{ github.token }}\n", "")),
                "`GH_TOKEN: ${{ github.token }}`",
            ),
            "sin GH_REPO": (
                _en_revision(PASO_DE_METADATOS, PASO_DE_METADATOS.replace("          GH_REPO: ${{ github.repository }}\n", "")),
                "`GH_REPO: ${{ github.repository }}`",
            ),
            "sin PR": (
                _en_revision(
                    PASO_DE_METADATOS, PASO_DE_METADATOS.replace("          PR: ${{ github.event.pull_request.number }}\n", "")
                ),
                "`PR: ${{ github.event.pull_request.number }}`",
            ),
            "el número del PR interpolado en el run": (
                _en_revision(LINEA_DEL_DIFF, '          gh pr diff "${{ github.event.pull_request.number }}" > .revision-pr/pr.diff\n'),
                "debe escribir `.revision-pr/pr.diff`",
            ),
            "sin crear la carpeta": (_en_revision(LINEA_DEL_MKDIR, ""), "debe crear la carpeta con `mkdir -p .revision-pr`"),
            "sin el diff": (_en_revision(LINEA_DEL_DIFF, ""), "debe escribir `.revision-pr/pr.diff`"),
            "el diff en otra ruta": (
                _en_revision(LINEA_DEL_DIFF, '          gh pr diff "$PR" > pr.diff\n'),
                "debe escribir `.revision-pr/pr.diff`",
            ),
            "sin los metadatos": (_en_revision(LINEA_DEL_JSON, ""), "debe escribir `.revision-pr/pr.json`"),
            "los metadatos sin la lista de archivos": (
                _en_revision(LINEA_DEL_JSON, '          gh pr view "$PR" --json title,body > .revision-pr/pr.json\n'),
                "debe escribir `.revision-pr/pr.json`",
            ),
            "los metadatos en otra ruta": (
                _en_revision(LINEA_DEL_JSON, '          gh pr view "$PR" --json title,body,files > pr.json\n'),
                "debe escribir `.revision-pr/pr.json`",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_metadatos_del_pr, casos)

    # --- TC62-18 -------------------------------------------------------------------------------------------

    def test_tkt062_ca04_esc02_mutantes_la_revision_lee_la_base_y_no_el_pr(self):
        """CA-4 esc. 2 · TC62-18 — sin `ref:` en `revision` o en `publicar`, `ref:` con `head.sha`, con `github.sha` o con la rama del PR, sin
        `persist-credentials: false`, el checkout fuera del primer paso, sin checkout y un `prompt` que no nombra `.claude/revision-pr.md` son rojo."""
        ref_de_la_base = "          ref: ${{ github.event.pull_request.base.sha }}\n"
        casos = {
            "sin ref en revision": (_en_revision(ref_de_la_base, ""), "'revision': el checkout debe llevar `ref:"),
            "sin ref en publicar": (_en_publicar(ref_de_la_base, ""), "'publicar': el checkout debe llevar `ref:"),
            "head.sha en revision": (
                _en_revision(ref_de_la_base, "          ref: ${{ github.event.pull_request.head.sha }}\n"),
                "'revision': el checkout debe leer la base",
            ),
            "head.sha en publicar": (
                _en_publicar(ref_de_la_base, "          ref: ${{ github.event.pull_request.head.sha }}\n"),
                "'publicar': el checkout debe leer la base",
            ),
            "github.sha en publicar": (
                _en_publicar(ref_de_la_base, "          ref: ${{ github.sha }}\n"),
                "'publicar': el checkout debe leer la base",
            ),
            "la rama del PR en revision": (
                _en_revision(ref_de_la_base, "          ref: ${{ github.event.pull_request.head.ref }}\n"),
                "'revision': el checkout debe leer la base",
            ),
            "ref escrito dos veces en publicar": (
                _en_publicar(ref_de_la_base, ref_de_la_base + ref_de_la_base),
                "exactamente una vez",
            ),
            "persist-credentials: true en revision": (
                _en_revision("persist-credentials: false", "persist-credentials: true"),
                "'revision': actions/checkout debe llevar `persist-credentials: false`",
            ),
            "sin persist-credentials en publicar": (
                _en_publicar("          persist-credentials: false\n", ""),
                "'publicar': actions/checkout debe llevar `persist-credentials: false`",
            ),
            "checkout por etiqueta de versión en publicar": (
                _en_publicar(f"actions/checkout@{SHA_DEL_CHECKOUT}", "actions/checkout@v7"),
                "'publicar': actions/checkout debe fijarse por el SHA",
            ),
            "sin checkout en publicar": (_en_publicar(CHECKOUT_DE_PUBLICAR, ""), "'publicar': falta actions/checkout de la base"),
            "sin checkout en revision": (_en_revision(CHECKOUT_DE_REVISION, ""), "'revision': falta actions/checkout de la base"),
            "el paso de metadatos antes del checkout de revision": (
                _en_revision(CHECKOUT_DE_REVISION + PASO_DE_METADATOS, PASO_DE_METADATOS + CHECKOUT_DE_REVISION),
                "'revision': el checkout debe ser el primer paso",
            ),
            "el checkout de publicar después del primer paso": (
                _en_publicar(CHECKOUT_DE_PUBLICAR + PASO_DE_ARCHIVOS, PASO_DE_ARCHIVOS + CHECKOUT_DE_PUBLICAR),
                "'publicar': el checkout debe ser el primer paso",
            ),
            "el prompt sin las instrucciones": (
                sustituir(REVISION_COMPLETA, "siguiendo .claude/revision-pr.md.", "siguiendo las instrucciones."),
                "el `prompt` debe nombrar `.claude/revision-pr.md`",
            ),
            "el prompt con las instrucciones del PR": (
                sustituir(REVISION_COMPLETA, "siguiendo .claude/revision-pr.md.", "siguiendo .claude-pr/revision-pr.md."),
                "el `prompt` debe nombrar `.claude/revision-pr.md`",
            ),
            "sin prompt": (sustituir(REVISION_COMPLETA, LINEA_DEL_PROMPT, ""), "el `prompt` debe nombrar"),
        }
        exigir_rojo_en_todos(self, comprobar_checkout_de_la_base, casos)

    # --- TC62-26 -------------------------------------------------------------------------------------------

    def test_tkt062_ca05_esc02_mutantes_publicar_pasa_siempre_por_el_filtro(self):
        """CA-5 esc. 2 · TC62-26 — publicar `HALLAZGOS` sin pasar por el script (`gh pr comment --body "$HALLAZGOS"`), sin `needs: revision`, con
        `if:`, sin filtro, sin `--paginate`, los pasos en otro orden, `HALLAZGOS` desde otro sitio, la salida de `revision` desde otro paso,
        `gh pr comment` sin `--body-file` y un `secrets.` en `publicar` son rojo."""
        linea_de_salida = "      hallazgos: ${{ steps.claude.outputs.structured_output }}\n"
        casos = {
            "HALLAZGOS publicado sin pasar por el script": (
                _en_publicar(
                    '        run: gh pr comment "$PR" --body-file "$RUNNER_TEMP/comentario.md"\n',
                    '        run: gh pr comment "$PR" --body "$HALLAZGOS"\n',
                ),
                "publica con `--body`",
            ),
            "HALLAZGOS usado en un run": (
                _en_publicar(
                    '        run: gh pr comment "$PR" --body-file "$RUNNER_TEMP/comentario.md"\n',
                    '        run: echo "$HALLAZGOS" > "$RUNNER_TEMP/comentario.md" && gh pr comment "$PR" --body-file "$RUNNER_TEMP/comentario.md"\n',
                ),
                "usa HALLAZGOS directamente",
            ),
            "sin needs": (_en_publicar("    needs: revision\n", ""), "'publicar': `needs:` debe ser solo `revision`"),
            "needs de otro trabajo": (_en_publicar("    needs: revision\n", "    needs: [revision, otro]\n"), "`needs:` debe ser solo `revision`"),
            "con if": (
                _en_publicar("    needs: revision\n", "    needs: revision\n    if: ${{ always() }}\n"),
                "no lleva `if:`",
            ),
            "sin el filtro": (
                _en_publicar(PASO_DEL_FILTRO, "      - name: Filtrar\n        run: echo filtrar\n"),
                "falta el paso que ejecuta `python3 tools/publicar_revision.py`",
            ),
            "el filtro sin --salida": (
                _en_publicar(' --salida "$RUNNER_TEMP/comentario.md"', ""),
                "el filtro debe escribir `--salida",
            ),
            "el filtro sin --archivos": (
                _en_publicar(' --archivos "$RUNNER_TEMP/archivos.txt"', ""),
                "el filtro debe recibir `--archivos",
            ),
            "gh api sin --paginate": (_en_publicar("gh api --paginate ", "gh api "), "debe usar `gh api --paginate`"),
            "sin el paso de los archivos": (
                _en_publicar(PASO_DE_ARCHIVOS, "      - name: Archivos\n        run: echo archivos\n"),
                "falta el paso «Archivos del PR»",
            ),
            "el filtro antes que los archivos": (
                _en_publicar(PASO_DE_ARCHIVOS + PASO_DEL_FILTRO, PASO_DEL_FILTRO + PASO_DE_ARCHIVOS),
                "deben ir en el orden",
            ),
            "el comentario antes que el filtro": (
                _en_publicar(PASO_DEL_FILTRO + PASO_DEL_COMENTARIO, PASO_DEL_COMENTARIO + PASO_DEL_FILTRO),
                "deben ir en el orden",
            ),
            "sin gh pr comment": (
                _en_publicar(PASO_DEL_COMENTARIO, "      - name: Publicar\n        run: echo publicar\n"),
                "falta el paso que ejecuta `gh pr comment`",
            ),
            "gh pr comment sin --body-file": (
                _en_publicar('--body-file "$RUNNER_TEMP/comentario.md"', '--body-file "$RUNNER_TEMP/otro.md"'),
                "`gh pr comment` debe publicar `--body-file",
            ),
            "HALLAZGOS desde la salida del modelo": (
                _en_publicar("HALLAZGOS: ${{ needs.revision.outputs.hallazgos }}", "HALLAZGOS: ${{ steps.claude.outputs.structured_output }}"),
                "`HALLAZGOS: ${{ needs.revision.outputs.hallazgos }}`",
            ),
            "HALLAZGOS vacío": (
                _en_publicar("          HALLAZGOS: ${{ needs.revision.outputs.hallazgos }}\n", ""),
                "`HALLAZGOS: ${{ needs.revision.outputs.hallazgos }}`",
            ),
            "TITULO sin pasar por env": (
                _en_publicar("          TITULO: ${{ github.event.pull_request.title }}\n", ""),
                "`TITULO:",
            ),
            "CABEZA sin pasar por env": (
                _en_publicar("          CABEZA: ${{ github.event.pull_request.head.sha }}\n", ""),
                "`CABEZA:",
            ),
            "la salida de revision desde otro paso": (
                sustituir(REVISION_COMPLETA, linea_de_salida, "      hallazgos: ${{ steps.otro.outputs.structured_output }}\n"),
                "`outputs.hallazgos` de `revision` debe valer",
            ),
            "sin salida en revision": (sustituir(REVISION_COMPLETA, "    outputs:\n" + linea_de_salida, ""), "`outputs.hallazgos` de `revision` debe valer"),
            "un secreto en publicar": (
                _en_publicar(
                    "          PR: ${{ github.event.pull_request.number }}\n        run: gh pr comment",
                    "          PR: ${{ github.event.pull_request.number }}\n          X: ${{ secrets.X }}\n        run: gh pr comment",
                ),
                "lee secrets.",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_publicar, casos)

    # --- TC62-27 -------------------------------------------------------------------------------------------

    def test_tkt062_ca07_esc01_mutantes_solo_la_revision_lee_la_clave(self):
        """CA-7 esc. 1 · TC62-27 — la clave leída en `ci.yml`, `enlaces.yml` o `etiqueta-origen.yml`, sin `revision-ia.yml`, sin ninguna lectura en
        él, leída en `publicar`, bajo otra clave del `with:` o dos veces es rojo."""

        def con(nombre: str, texto: str) -> dict[str, str]:
            return {**FLUJOS_SINTETICOS, nombre: texto}

        etiqueta_linea = "          ETIQUETAS: ${{ toJSON(github.event.pull_request.labels.*.name) }}\n"
        sin_clave = sustituir(REVISION_COMPLETA, LINEA_DE_LA_CLAVE, "")
        casos = {
            "la clave en ci.yml": (
                con("ci.yml", CI_A4 + "      - run: echo ${{ secrets.ANTHROPIC_API_KEY }}\n"),
                "lee secrets. fuera de la revisión: ci.yml",
            ),
            "la clave en enlaces.yml": (
                con("enlaces.yml", ENLACES_SINTETICO + "      - run: echo ${{ secrets.X }}\n"),
                "lee secrets. fuera de la revisión: enlaces.yml",
            ),
            "la clave en etiqueta-origen.yml": (
                con("etiqueta-origen.yml", sustituir(ETIQUETA_SINTETICA, etiqueta_linea, etiqueta_linea + LINEA_DE_LA_CLAVE)),
                "lee secrets. fuera de la revisión: etiqueta-origen.yml",
            ),
            "sin revision-ia.yml": (
                {k: v for k, v in FLUJOS_SINTETICOS.items() if k != FLUJO_DE_REVISION},
                f"falta {FLUJO_DE_REVISION}",
            ),
            "revision-ia.yml sin ninguna lectura": (con(FLUJO_DE_REVISION, sin_clave), "la única lectura de secrets."),
            "la clave dos veces": (
                con(FLUJO_DE_REVISION, sustituir(REVISION_COMPLETA, LINEA_DE_LA_CLAVE, LINEA_DE_LA_CLAVE * 2)),
                "la única lectura de secrets.",
            ),
            "la clave bajo otra entrada del with": (
                con(FLUJO_DE_REVISION, sustituir(REVISION_COMPLETA, LINEA_DE_LA_CLAVE, "          github_token: ${{ secrets.ANTHROPIC_API_KEY }}\n")),
                "la clave solo se lee en `anthropic_api_key`",
            ),
            "la clave en el paso de metadatos de revision": (
                con(
                    FLUJO_DE_REVISION,
                    _en_revision(
                        '          gh pr diff "$PR" > .revision-pr/pr.diff\n',
                        '          gh pr diff "$PR" > .revision-pr/pr.diff\n          echo ${{ secrets.ANTHROPIC_API_KEY }}\n',
                    ),
                ),
                "la única lectura de secrets.",
            ),
            "la clave en publicar": (
                con(
                    FLUJO_DE_REVISION,
                    _en_publicar(
                        "          PR: ${{ github.event.pull_request.number }}\n        run: gh pr comment",
                        "          PR: ${{ github.event.pull_request.number }}\n          X: ${{ secrets.ANTHROPIC_API_KEY }}\n        run: gh pr comment",
                    ),
                ),
                "la única lectura de secrets.",
            ),
            "secrets.GITHUB_TOKEN además de la clave": (
                con(FLUJO_DE_REVISION, sustituir(REVISION_COMPLETA, LINEA_DEL_TOKEN, "          github_token: ${{ secrets.GITHUB_TOKEN }}\n")),
                "la única lectura de secrets.",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_solo_la_revision_lee_la_clave, casos)

    # --- TC62-31 -------------------------------------------------------------------------------------------

    def test_tkt062_ca08_esc02_ningun_trabajo_del_pipeline_espera_la_revision(self):
        """CA-8 esc. 2 · TC62-31 (rechazo estático) — solo mutantes, porque la comprobación sobre los flujos reales ya es TC-13 de TKT-009:
        `needs: revision` en un trabajo de `ci.yml`, `enlaces.yml` o `etiqueta-origen.yml`, y `workflow_run` en `revision-ia.yml`, son rojo."""
        self.assertEqual(comprobar_tc13(FLUJOS_SINTETICOS), [], "control: los flujos sintéticos válidos pasan TC-13")
        casos = {
            "ci.yml espera a revision": (
                {**FLUJOS_SINTETICOS, "ci.yml": mutar(CI_A4, "documentacion", "    runs-on: ubuntu-24.04\n", "    needs: revision\n    runs-on: ubuntu-24.04\n")},
                "ci.yml: 'documentacion' necesita 'revision', que no es un trabajo de este archivo",
            ),
            "ci.yml espera a publicar": (
                {**FLUJOS_SINTETICOS, "ci.yml": mutar(CI_A4, "documentacion", "    runs-on: ubuntu-24.04\n", "    needs: [publicar]\n    runs-on: ubuntu-24.04\n")},
                "ci.yml: 'documentacion' necesita 'publicar', que no es un trabajo de este archivo",
            ),
            "etiqueta-origen.yml espera a revision": (
                {**FLUJOS_SINTETICOS, "etiqueta-origen.yml": sustituir(ETIQUETA_SINTETICA, "    runs-on: ubuntu-24.04\n", "    needs: revision\n    runs-on: ubuntu-24.04\n")},
                "etiqueta-origen.yml: 'etiqueta' necesita 'revision', que no es un trabajo de este archivo",
            ),
            "workflow_run en revision-ia.yml": (
                {
                    **FLUJOS_SINTETICOS,
                    FLUJO_DE_REVISION: sustituir(
                        REVISION_COMPLETA, "on:\n  pull_request:\n", "on:\n  workflow_run:\n    workflows: [CI]\n  pull_request:\n"
                    ),
                },
                f"{FLUJO_DE_REVISION}: usa el disparador workflow_run",
            ),
            "revision-ia.yml espera a un trabajo de ci.yml": (
                {**FLUJOS_SINTETICOS, FLUJO_DE_REVISION: _en_revision("    runs-on: ubuntu-24.04\n", "    needs: backend\n    runs-on: ubuntu-24.04\n")},
                f"{FLUJO_DE_REVISION}: 'revision' necesita 'backend', que no es un trabajo de este archivo",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_tc13, casos)

    # --- TC62-33 -------------------------------------------------------------------------------------------

    def test_tkt062_ca10_esc01_mutantes_turnos_modelo_y_tiempo_acotados(self):
        """CA-10 esc. 1 · TC62-33 — sin `--max-turns`, con otro número de turnos, sin `--model`, con otro modelo, sin `--json-schema`, con un esquema
        que no es JSON o no exige `hallazgos`, `timeout-minutes` quitado o distinto (10 en `revision`, 5 en `publicar`) son rojo."""
        casos = {
            "sin --max-turns": (_con_args(LINEA_DE_LOS_TURNOS, ""), "`--max-turns` debe ser 20"),
            "--max-turns 50": (_con_args(LINEA_DE_LOS_TURNOS, "            --max-turns 50\n"), "`--max-turns` debe ser 20"),
            "--max-turns sin valor": (_con_args(LINEA_DE_LOS_TURNOS, "            --max-turns\n"), "`--max-turns` debe ser 20"),
            "--max-turns dos veces": (_con_args(LINEA_DE_LOS_TURNOS, LINEA_DE_LOS_TURNOS * 2), "`--max-turns` debe ser 20"),
            "sin --model": (_con_args(LINEA_DEL_MODELO, ""), "`--model` debe ser sonnet"),
            "--model opus": (_con_args(LINEA_DEL_MODELO, "            --model opus\n"), "`--model` debe ser sonnet"),
            "sin --json-schema": (_con_args(LINEA_DEL_ESQUEMA, ""), "`--json-schema` debe declararse exactamente una vez"),
            "--json-schema dos veces": (_con_args(LINEA_DEL_ESQUEMA, LINEA_DEL_ESQUEMA * 2), "`--json-schema` debe declararse exactamente una vez"),
            "--json-schema que no es JSON": (
                _con_args(LINEA_DEL_ESQUEMA, "            --json-schema '{no es json}'\n"),
                "`--json-schema` debe ser un esquema JSON que exija `hallazgos`",
            ),
            "--json-schema que no exige hallazgos": (
                _con_args(LINEA_DEL_ESQUEMA, "            --json-schema '{\"type\":\"object\"}'\n"),
                "`--json-schema` debe ser un esquema JSON que exija `hallazgos`",
            ),
            "revision sin timeout": (_en_revision("    timeout-minutes: 10\n", ""), "'revision': timeout-minutes debe ser 10"),
            "revision con 5 minutos": (_en_revision("timeout-minutes: 10", "timeout-minutes: 5"), "'revision': timeout-minutes debe ser 10"),
            "revision con 15 minutos": (_en_revision("timeout-minutes: 10", "timeout-minutes: 15"), "'revision': timeout-minutes debe ser 10"),
            "publicar sin timeout": (_en_publicar("    timeout-minutes: 5\n", ""), "'publicar': timeout-minutes debe ser 5"),
            "publicar con 10 minutos": (_en_publicar("timeout-minutes: 5", "timeout-minutes: 10"), "'publicar': timeout-minutes debe ser 5"),
            "comillas sin cerrar en claude_args": (
                _con_args(LINEA_DEL_MODELO, LINEA_DEL_MODELO + '            --append "sin cerrar\n'),
                "unas comillas sin cerrar",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_topes, casos)


# ---------------------------------------------------------------------------------------------------------
# TC62-17: las instrucciones remiten a la lista y a las reglas, no las copian
# ---------------------------------------------------------------------------------------------------------

INSTRUCCIONES_DEL_MODELO_RUTA = os.path.join(RAIZ, ".claude", "revision-pr.md")
CONVENCIONES_RUTA = os.path.join(RAIZ, "docs", "convenciones.md")
CLAUDE_MD_RUTA = os.path.join(RAIZ, "CLAUDE.md")

ENLACE_A_CLAUDE = "../CLAUDE.md"
ANCLA_DE_LA_LISTA = "qué-revisa-la-revisión-automatizada-de-pr"
ENLACE_A_LA_LISTA = f"../docs/convenciones.md#{ANCLA_DE_LA_LISTA}"
ENCABEZADO_DE_LA_LISTA = "Qué revisa la revisión automatizada de PR"
ENCABEZADO_DE_LAS_REGLAS = "Reglas que ninguna implementación puede romper"
PUNTOS_ESPERADOS = 11
REGLAS_ESPERADAS = 17
LARGO_DE_LA_HUELLA = 50

ENLACE_DE_MARKDOWN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ENLACE_CON_TEXTO = re.compile(r"\[([^\]]*)\]\([^)]*\)")
LINEA_DE_ENCABEZADO = re.compile(r"^#{1,6}\s+(.*?)\s*$")
LINEA_NUMERADA = re.compile(r"^\d+\.\s+(.*\S)\s*$")
ES_EXTERNO = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", re.IGNORECASE)


def _plano(texto: str) -> str:
    """Texto comparable: enlaces reducidos a su texto, sin negritas ni comillas de código, espacios colapsados, en minúsculas.
    Quien copia un punto suele cambiar el formato; la huella no debe depender de él."""
    texto = ENLACE_CON_TEXTO.sub(r"\1", texto)
    texto = texto.replace("*", "").replace("`", "")
    return " ".join(texto.split()).casefold()


def _elementos_numerados(texto: str, encabezado: str) -> list[str]:
    """Los elementos `N. …` de la sección cuyo encabezado es `encabezado`, hasta el siguiente encabezado. Vacía si no hay sección."""
    elementos: list[str] = []
    dentro = False
    for linea in texto.splitlines():
        titulo = LINEA_DE_ENCABEZADO.match(linea)
        if titulo is not None:
            if dentro:
                break
            dentro = titulo.group(1) == encabezado
            continue
        numerada = LINEA_NUMERADA.match(linea) if dentro else None
        if numerada is not None:
            elementos.append(numerada.group(1))
    return elementos


def _anclas_de(texto: str) -> set[str]:
    """Las anclas de los encabezados de un Markdown, con el algoritmo de `tools/verificar_docs.py` (el que usa CI)."""
    return {verificar_docs.ancla(m.group(2)) for m in verificar_docs.ENCABEZADO.finditer(verificar_docs.VALLA.sub("", texto))}


def comprobar_instrucciones(
    texto: str,
    puntos: list[str],
    reglas: list[str],
    anclas_de_convenciones: set[str],
    existe: Callable[[str], bool],
) -> list[str]:
    """TC62-17 · CA-4 esc. 1. `texto` es `.claude/revision-pr.md`; `puntos` son los de §12; `reglas`, las de `CLAUDE.md`;
    `existe(ruta)` dice si una ruta relativa a la raíz (con `/`) existe. Las instrucciones enlazan las dos fuentes, los enlaces
    resuelven y ningún punto ni regla aparece copiado (sus primeros `LARGO_DE_LA_HUELLA` caracteres, ya sin formato)."""
    problemas: list[str] = []
    if not puntos:
        problemas.append("no hay puntos de §12 contra los que comparar: la comprobación de copia sería vacía")
    if not reglas:
        problemas.append("no hay reglas de CLAUDE.md contra las que comparar: la comprobación de copia sería vacía")
    destinos = ENLACE_DE_MARKDOWN.findall(texto)
    for requerido in (ENLACE_A_CLAUDE, ENLACE_A_LA_LISTA):
        if requerido not in destinos:
            problemas.append(f"no enlaza `{requerido}`: las instrucciones deben remitir a la fuente, no repetirla")
    for destino in destinos:
        if ES_EXTERNO.match(destino):
            continue
        archivo, _, ancla = destino.partition("#")
        ruta = os.path.normpath(os.path.join(".claude", archivo)).replace("\\", "/")
        if not existe(ruta):
            problemas.append(f"enlace roto: `{destino}` no resuelve, {ruta} no existe")
        elif ancla and ruta == "docs/convenciones.md" and ancla not in anclas_de_convenciones:
            problemas.append(f"enlace roto: `{destino}` no resuelve, {ruta} no tiene un encabezado con la ancla #{ancla}")
    plano = _plano(texto)
    for etiqueta, elementos in (("el punto {n} de §12", puntos), ("la regla {n} de CLAUDE.md", reglas)):
        for n, elemento in enumerate(elementos, 1):
            huella = _plano(elemento)[:LARGO_DE_LA_HUELLA]
            if huella and huella in plano:
                problemas.append(f"copia {etiqueta.format(n=n)}: «{huella}». Debe remitir a la fuente, no copiarla")
    return problemas


def comprobar_lectura_del_pr_sin_gh(texto: str) -> list[str]:
    """TC62-14 · CA-3 esc. 3 (F001). `texto` es `.claude/revision-pr.md`. El modelo no tiene `Bash`: las instrucciones remiten a
    `.revision-pr/pr.json` y `.revision-pr/pr.diff`, no nombran ninguna orden `gh`, y dicen que el entorno del proceso no se lee."""
    problemas: list[str] = []
    for archivo in (JSON_DEL_PR, DIFF_DEL_PR):
        if archivo not in texto:
            problemas.append(f"no remite a `{archivo}`: es de donde el modelo lee el PR, ahora que no tiene `Bash`")
    if re.search(r"\bgh\s+(?:pr|api)\b", texto):
        problemas.append("nombra una orden `gh`: el modelo no puede ejecutarla, debe leer los dos archivos del PR")
    if not re.search(r"\b(?:no|nunca|ni)\b[^.\n]*\bentorno del proceso\b", _plano(texto)):
        problemas.append("no dice que el entorno del proceso no se lee: es donde vive la clave")
    return problemas


PUNTOS_SINTETICOS = [
    f"Punto {n} de la lista cerrada de la revisión, redactado con texto suficiente para pasar de cincuenta caracteres."
    for n in range(1, PUNTOS_ESPERADOS + 1)
]
REGLAS_SINTETICAS = [
    f"**Regla {n} del proyecto.** Esta regla sintética lleva también texto suficiente para pasar de cincuenta caracteres."
    for n in range(1, REGLAS_ESPERADAS + 1)
]
ANCLAS_SINTETICAS = {ANCLA_DE_LA_LISTA, "otra-seccion"}
RUTAS_SINTETICAS = {"CLAUDE.md", "docs/convenciones.md"}
INSTRUCCIONES_SINTETICAS = f"""\
# Revisión de pull requests

Revisas y comentas; nunca apruebas ni propones parches aplicables. Tu única salida es la salida estructurada.

Las reglas del proyecto están en [CLAUDE.md]({ENLACE_A_CLAUDE}) y la lista de lo que se revisa es la única de
[convenciones §12]({ENLACE_A_LA_LISTA}). Léelas del árbol de trabajo, que es la rama base.
"""


INSTRUCCIONES_SIN_GH = (
    INSTRUCCIONES_SINTETICAS
    + """\

El pull request está en `.revision-pr/pr.json` (título, cuerpo y archivos) y `.revision-pr/pr.diff` (su diff). Ábrelos con tu herramienta de
lectura. Nunca leas el entorno del proceso ni sus variables: no son material de la revisión.
"""
)


def _entrada(
    texto: str = INSTRUCCIONES_SINTETICAS,
    puntos: list[str] = PUNTOS_SINTETICOS,
    reglas: list[str] = REGLAS_SINTETICAS,
    anclas: set[str] = ANCLAS_SINTETICAS,
    rutas: set[str] = RUTAS_SINTETICAS,
) -> dict:
    return {
        "texto": texto,
        "puntos": puntos,
        "reglas": reglas,
        "anclas_de_convenciones": anclas,
        "existe": lambda ruta: ruta in rutas,
    }


def _comprobar_entrada(entrada: dict) -> list[str]:
    return comprobar_instrucciones(**entrada)


class PruebasDeMutantesDeLasInstrucciones(unittest.TestCase):
    """TC62-17: cada propiedad de `.claude/revision-pr.md` se pone en rojo cuando se estropea, y por la razón esperada."""

    def test_tkt062_ca04_esc01_mutantes_las_instrucciones_control_valido_pasa(self):
        """CA-4 esc. 1 · TC62-17 (control) — las instrucciones sintéticas válidas pasan; sin esto, un mutante «en rojo» podría estarlo por
        culpa del texto base. Y una frase corta compartida con un punto no es una copia: la huella son 50 caracteres, no menos."""
        self.assertEqual(_comprobar_entrada(_entrada()), [])
        frase_corta = _plano(PUNTOS_SINTETICOS[2])[: LARGO_DE_LA_HUELLA - 1]
        self.assertEqual(_comprobar_entrada(_entrada(texto=INSTRUCCIONES_SINTETICAS + frase_corta + "\n")), [])

    def test_tkt062_ca04_esc01_mutantes_los_enlaces(self):
        """CA-4 esc. 1 · TC62-17 — sin el enlace a `CLAUDE.md`, sin el de §12, con el ancla sin acentos, sin ancla, apuntando a otro archivo, o con
        un destino que no resuelve (archivo ausente, ancla ausente del encabezado de §12, enlace roto adicional) es rojo."""
        sin_claude = sustituir(INSTRUCCIONES_SINTETICAS, f"({ENLACE_A_CLAUDE})", "(#fuentes)")
        sin_lista = sustituir(INSTRUCCIONES_SINTETICAS, f"({ENLACE_A_LA_LISTA})", "(#fuentes)")
        casos = {
            "sin el enlace a CLAUDE.md": (_entrada(texto=sin_claude), f"no enlaza `{ENLACE_A_CLAUDE}`"),
            "CLAUDE.mdx": (
                _entrada(texto=sustituir(INSTRUCCIONES_SINTETICAS, f"({ENLACE_A_CLAUDE})", "(../CLAUDE.mdx)")),
                f"no enlaza `{ENLACE_A_CLAUDE}`",
            ),
            "CLAUDE.md sin ../": (
                _entrada(texto=sustituir(INSTRUCCIONES_SINTETICAS, f"({ENLACE_A_CLAUDE})", "(CLAUDE.md)")),
                "enlace roto: `CLAUDE.md` no resuelve",
            ),
            "sin el enlace a §12": (_entrada(texto=sin_lista), f"no enlaza `{ENLACE_A_LA_LISTA}`"),
            "ancla sin acentos": (
                _entrada(
                    texto=sustituir(
                        INSTRUCCIONES_SINTETICAS, ANCLA_DE_LA_LISTA, "que-revisa-la-revision-automatizada-de-pr"
                    )
                ),
                f"no enlaza `{ENLACE_A_LA_LISTA}`",
            ),
            "convenciones sin ancla": (
                _entrada(texto=sustituir(INSTRUCCIONES_SINTETICAS, f"({ENLACE_A_LA_LISTA})", "(../docs/convenciones.md)")),
                f"no enlaza `{ENLACE_A_LA_LISTA}`",
            ),
            "el archivo CLAUDE.md no existe": (
                _entrada(rutas={"docs/convenciones.md"}),
                "enlace roto: `../CLAUDE.md` no resuelve, CLAUDE.md no existe",
            ),
            "el archivo convenciones.md no existe": (
                _entrada(rutas={"CLAUDE.md"}),
                "no resuelve, docs/convenciones.md no existe",
            ),
            "convenciones.md sin el encabezado de §12": (
                _entrada(anclas={"otra-seccion"}),
                f"no tiene un encabezado con la ancla #{ANCLA_DE_LA_LISTA}",
            ),
            "un enlace roto además de los buenos": (
                _entrada(texto=INSTRUCCIONES_SINTETICAS + "\nVéase [el ADR](../docs/adr/no-existe.md).\n"),
                "enlace roto: `../docs/adr/no-existe.md` no resuelve",
            ),
        }
        exigir_rojo_en_todos(self, _comprobar_entrada, casos)

    def test_tkt062_ca04_esc01_mutantes_copiar_un_punto_de_la_lista(self):
        """CA-4 esc. 1 · TC62-17 — pegar cualquiera de los once puntos de §12 es rojo, también con otro formato (negritas, comillas de código,
        espacios dobles, mayúsculas) y también si solo se pegan sus primeros 50 caracteres. Los once, uno por uno."""
        casos = {}
        for n, punto in enumerate(PUNTOS_SINTETICOS, 1):
            casos[f"el punto {n} pegado"] = (
                _entrada(texto=INSTRUCCIONES_SINTETICAS + f"\n{n}. {punto}\n"),
                f"copia el punto {n} de §12",
            )
        punto = PUNTOS_SINTETICOS[4]
        con_formato = "**" + "  ".join(punto.upper().split(" ")) + "**"
        casos["el punto 5 con otro formato"] = (
            _entrada(texto=INSTRUCCIONES_SINTETICAS + f"\n- {con_formato}\n"),
            "copia el punto 5 de §12",
        )
        casos["solo los primeros 50 caracteres del punto 7"] = (
            _entrada(texto=INSTRUCCIONES_SINTETICAS + "\n" + PUNTOS_SINTETICOS[6][:LARGO_DE_LA_HUELLA] + "\n"),
            "copia el punto 7 de §12",
        )
        casos["el punto 1 partido en dos líneas"] = (
            _entrada(texto=INSTRUCCIONES_SINTETICAS + "\n" + PUNTOS_SINTETICOS[0].replace(", ", ",\n") + "\n"),
            "copia el punto 1 de §12",
        )
        exigir_rojo_en_todos(self, _comprobar_entrada, casos)

    def test_tkt062_ca04_esc01_mutantes_copiar_una_regla_de_claude_md(self):
        """CA-4 esc. 1 · TC62-17 — pegar cualquiera de las 17 reglas de `CLAUDE.md`, con o sin sus negritas, es rojo. Las diecisiete, una por una."""
        casos = {}
        for n, regla in enumerate(REGLAS_SINTETICAS, 1):
            casos[f"la regla {n} pegada"] = (
                _entrada(texto=INSTRUCCIONES_SINTETICAS + f"\n{n}. {regla}\n"),
                f"copia la regla {n} de CLAUDE.md",
            )
        casos["la regla 11 sin negritas"] = (
            _entrada(texto=INSTRUCCIONES_SINTETICAS + "\n" + REGLAS_SINTETICAS[10].replace("**", "") + "\n"),
            "copia la regla 11 de CLAUDE.md",
        )
        exigir_rojo_en_todos(self, _comprobar_entrada, casos)

    def test_tkt062_ca03_esc03_mutantes_las_instrucciones_remiten_a_los_archivos_del_pr_y_no_a_gh(self):
        """CA-3 esc. 3 · TC62-14 (F001) — sin `Bash`, las instrucciones remiten a `.revision-pr/pr.json` y `.revision-pr/pr.diff`: nombrar `gh pr view`,
        `gh pr diff` o `gh api`, no remitir a alguno de los dos archivos o no decir que el entorno del proceso no se lee es rojo."""
        self.assertEqual(comprobar_lectura_del_pr_sin_gh(INSTRUCCIONES_SIN_GH), [], "control: las instrucciones sintéticas válidas pasan")
        casos = {
            "gh pr view": (INSTRUCCIONES_SIN_GH + "\nObtén el PR con `gh pr view <número> --json title,body,files`.\n", "nombra una orden `gh`"),
            "gh pr diff": (INSTRUCCIONES_SIN_GH + "\nObtén el diff con `gh pr diff <número>`.\n", "nombra una orden `gh`"),
            "gh api": (INSTRUCCIONES_SIN_GH + "\nConsulta `gh api repos/x/y/pulls/1`.\n", "nombra una orden `gh`"),
            "sin pr.json": (sustituir(INSTRUCCIONES_SIN_GH, ".revision-pr/pr.json", "el archivo de metadatos"), "no remite a `.revision-pr/pr.json`"),
            "sin pr.diff": (sustituir(INSTRUCCIONES_SIN_GH, ".revision-pr/pr.diff", "el archivo del diff"), "no remite a `.revision-pr/pr.diff`"),
            "sin decir que el entorno no se lee": (
                sustituir(INSTRUCCIONES_SIN_GH, "Nunca leas el entorno del proceso ni sus variables: no son material de la revisión.", "Lee con calma."),
                "no dice que el entorno del proceso no se lee",
            ),
            "el entorno del proceso como lectura permitida": (
                sustituir(
                    INSTRUCCIONES_SIN_GH,
                    "Nunca leas el entorno del proceso ni sus variables: no son material de la revisión.",
                    "Lee el entorno del proceso si te hace falta.",
                ),
                "no dice que el entorno del proceso no se lee",
            ),
        }
        exigir_rojo_en_todos(self, comprobar_lectura_del_pr_sin_gh, casos)

    def test_tkt062_ca04_esc01_mutantes_sin_fuentes_la_comparacion_no_es_vacua(self):
        """CA-4 esc. 1 · TC62-17 — si no se leyó ningún punto o ninguna regla, la comprobación de copia pasaría por vacuidad: es rojo."""
        casos = {
            "sin puntos de §12": (_entrada(puntos=[]), "no hay puntos de §12"),
            "sin reglas de CLAUDE.md": (_entrada(reglas=[]), "no hay reglas de CLAUDE.md"),
        }
        exigir_rojo_en_todos(self, _comprobar_entrada, casos)


# ---------------------------------------------------------------------------------------------------------
# Los casos sobre el archivo real
# ---------------------------------------------------------------------------------------------------------


def _texto_de_revision(caso: unittest.TestCase) -> str:
    """El texto de `revision-ia.yml`. Sin el archivo el caso falla; nunca se salta ni da un verde por vacuidad."""
    if not os.path.isfile(REVISION_IA):
        caso.fail(
            f"No existe {os.path.relpath(REVISION_IA, RAIZ)}: el flujo de la revisión automatizada de TKT-062b todavía no está definido"
        )
    with open(REVISION_IA, encoding="utf-8") as archivo:
        return archivo.read()


class DefinicionDelFlujoDeRevision(unittest.TestCase):
    """Casos estáticos de la fila B3a sobre `.github/workflows/revision-ia.yml` y `ci.yml`. Sin el archivo, fallan; no se saltan."""

    def test_tkt062_ca01_esc01_la_revision_se_dispara_y_usa_claude_code_action(self):
        """CA-1 esc. 1 · TC62-10 — `revision-ia.yml` existe, se dispara con exactamente `opened, synchronize, ready_for_review, reopened`, no es
        `ci.yml`, y el trabajo `revision` usa `anthropics/claude-code-action@<40 hex>` con `id: claude`."""
        texto = _texto_de_revision(self)
        self.assertEqual(comprobar_disparo_y_accion(texto), [])
        self.assertEqual(comprobar_que_ci_no_aloja_la_revision(_leer_flujos(self)["ci.yml"]), [])

    def test_tkt062_ca02_esc01_borradores_bifurcaciones_y_dependabot_no_se_revisan(self):
        """CA-2 esc. 1 y 2 · TC62-11 (rechazo estático) — el `if:` de `revision` es `GUARDA_DE_REVISION`: sin borradores, sin bifurcaciones, sin Dependabot."""
        self.assertEqual(comprobar_guarda(_texto_de_revision(self)), [])

    def test_tkt062_ca03_esc01_permisos_minimos_y_token_de_actions(self):
        """CA-3 esc. 1 · TC62-13 — `revision`: `contents: read` y `pull-requests: read`, nada más; `publicar`: `contents: read` y `pull-requests: write`
        con comentario, nada más; ningún `id-token`, `contents: write`, `issues`, `actions` ni `checks`; `github_token: ${{ github.token }}`."""
        self.assertEqual(comprobar_permisos_y_token(_texto_de_revision(self)), [])

    def test_tkt062_ca03_esc03_el_modelo_no_tiene_herramientas_de_escritura(self):
        """CA-3 esc. 3 · TC62-14 (rechazo estático) — `--allowedTools` exacto, con `Read(./**)` y no `Read` a secas; `--disallowedTools` incluye `Edit` y
        `Write`; ningún `gh pr review`, `gh pr comment` ni `gh api` permitido."""
        self.assertEqual(comprobar_herramientas_del_modelo(_texto_de_revision(self)), [])

    def test_tkt062_ca03_esc03_los_metadatos_del_pr_se_escriben_antes_de_la_accion_y_sin_secretos(self):
        """CA-3 esc. 3 · TC62-14 (F001) — un paso de `revision`, antes de la acción y sin secretos, escribe `.revision-pr/pr.json` (`gh pr view --json
        title,body,files`) y `.revision-pr/pr.diff` (`gh pr diff`), con `GH_TOKEN`, `GH_REPO` y `PR` por `env:`."""
        self.assertEqual(comprobar_metadatos_del_pr(_texto_de_revision(self)), [])

    def test_tkt062_ca04_esc02_la_revision_lee_la_base_y_no_el_pr(self):
        """CA-4 esc. 2 · TC62-18 (rechazo estático) — los checkouts de `revision` y de `publicar` llevan `ref: ${{ github.event.pull_request.base.sha }}` y
        `persist-credentials: false`, y el `prompt` nombra `.claude/revision-pr.md`."""
        self.assertEqual(comprobar_checkout_de_la_base(_texto_de_revision(self)), [])

    def test_tkt062_ca05_esc02_publicar_pasa_siempre_por_el_filtro(self):
        """CA-5 esc. 2 · TC62-26 — `publicar`: `needs: revision`, sin `if:`; pasos «Archivos del PR» (con `gh api --paginate`), filtro y
        `gh pr comment --body-file`, en ese orden; `HALLAZGOS` desde `needs.revision.outputs.hallazgos`; la salida de `revision` desde
        `steps.claude.outputs.structured_output`; ningún `secrets.`."""
        self.assertEqual(comprobar_publicar(_texto_de_revision(self)), [])

    def test_tkt062_ca07_esc01_solo_la_revision_lee_la_clave(self):
        """CA-7 esc. 1 · TC62-27 — en el repositorio real, solo `revision-ia.yml` lee un secreto, y es `USO_PERMITIDO_DEL_SECRETO` en su sitio."""
        _texto_de_revision(self)  # falla con el motivo exacto si el archivo no existe
        flujos = _leer_flujos(self)
        self.assertEqual(comprobar_solo_la_revision_lee_la_clave(flujos), [])
        self.assertEqual(motivos_de_secretos(FLUJO_DE_REVISION, flujos[FLUJO_DE_REVISION]), [])
        self.assertEqual(comprobar_tc22(flujos), [])

    def test_tkt062_ca10_esc01_turnos_modelo_y_tiempo_acotados(self):
        """CA-10 esc. 1 · TC62-33 — `--max-turns 20`, `--model sonnet` y `--json-schema` presentes; `timeout-minutes` 10 en `revision` y 5 en `publicar`."""
        self.assertEqual(comprobar_topes(_texto_de_revision(self)), [])


def _leer(ruta: str) -> str:
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


class DefinicionDeLasInstruccionesDeRevision(unittest.TestCase):
    """Caso estático de la fila B3b sobre `.claude/revision-pr.md`. Sin el archivo, falla; no se salta."""

    def test_tkt062_ca04_esc01_las_instrucciones_remiten_y_no_copian(self):
        """CA-4 esc. 1 · TC62-17 — `.claude/revision-pr.md` existe, enlaza `../CLAUDE.md` y `../docs/convenciones.md#qué-revisa-la-revisión-automatizada-de-pr`,
        los dos resuelven (el archivo existe y el encabezado de §12 produce esa ancla) y no contiene los primeros 50 caracteres de ninguno de los once
        puntos de §12 ni de ninguna de las 17 reglas de `CLAUDE.md`, leídos del árbol al correr la prueba."""
        if not os.path.isfile(INSTRUCCIONES_DEL_MODELO_RUTA):
            self.fail(
                f"No existe {os.path.relpath(INSTRUCCIONES_DEL_MODELO_RUTA, RAIZ)}: las instrucciones de la revisión automatizada de TKT-062b "
                "todavía no están escritas"
            )
        convenciones = _leer(CONVENCIONES_RUTA)
        claude = _leer(CLAUDE_MD_RUTA)
        anclas = _anclas_de(convenciones)
        self.assertIn(
            ANCLA_DE_LA_LISTA,
            anclas,
            f"docs/convenciones.md no tiene un encabezado «{ENCABEZADO_DE_LA_LISTA}» cuya ancla sea #{ANCLA_DE_LA_LISTA}",
        )
        puntos = _elementos_numerados(convenciones, ENCABEZADO_DE_LA_LISTA)
        reglas = _elementos_numerados(claude, ENCABEZADO_DE_LAS_REGLAS)
        self.assertEqual(len(puntos), PUNTOS_ESPERADOS, "los puntos de §12 leídos del árbol")
        self.assertEqual(len(reglas), REGLAS_ESPERADAS, "las reglas de CLAUDE.md leídas del árbol")
        problemas = comprobar_instrucciones(
            _leer(INSTRUCCIONES_DEL_MODELO_RUTA),
            puntos,
            reglas,
            anclas,
            lambda ruta: os.path.exists(os.path.join(RAIZ, *ruta.split("/"))),
        )
        self.assertEqual(problemas, [])

    def test_tkt062_ca03_esc03_las_instrucciones_remiten_a_los_archivos_del_pr_y_no_a_gh(self):
        """CA-3 esc. 3 · TC62-14 (F001) — `.claude/revision-pr.md` remite a `.revision-pr/pr.json` y `.revision-pr/pr.diff`, no nombra `gh pr view`,
        `gh pr diff` ni `gh api`, y dice que el entorno del proceso no se lee."""
        if not os.path.isfile(INSTRUCCIONES_DEL_MODELO_RUTA):
            self.fail(f"No existe {os.path.relpath(INSTRUCCIONES_DEL_MODELO_RUTA, RAIZ)}")
        self.assertEqual(comprobar_lectura_del_pr_sin_gh(_leer(INSTRUCCIONES_DEL_MODELO_RUTA)), [])


# ---------------------------------------------------------------------------------------------------------
# TC62-41 · fila B7 · la documentación de 062b
# ---------------------------------------------------------------------------------------------------------

DOC_STACK = "docs/06-stack-tecnologico.md"
DOC_TOOLS = "tools/README.md"
DOC_CLAUDE = "CLAUDE.md"
DOC_CONVENCIONES = "docs/convenciones.md"
DOC_DEVSECOPS = ".claude/agents/ingeniero-devsecops.md"
DOC_README = "README.md"
DOC_LLMS = "llms.txt"
DOCUMENTOS_DE_062B = (DOC_STACK, DOC_TOOLS, DOC_CLAUDE, DOC_CONVENCIONES, DOC_DEVSECOPS, DOC_README, DOC_LLMS)

# Lo que 062b retira. La frase vieja del stack presentaba la revisión como uno de los «trabajos» que meten la IA en el pipeline.
LA_REVISION_COMO_TRABAJO_DEL_PIPELINE = re.compile(r"dos trabajos mas|meten la ia en el pipeline")
COMENTARIOS_EN_LINEA = re.compile(r"comentarios en linea")
DECISIONES_VIEJAS = re.compile(r"\b27 (?:decisiones|adrs)\b")
DECISIONES_NUEVAS = re.compile(r"\b28 (?:decisiones|adrs)\b")
SCRIPT_DE_PUBLICAR = re.compile(r"(?<![\w.])publicar_revision\.py")
FLUJO_DE_LA_REVISION = "revision-ia.yml"
CLAVE_DEL_MODELO = "anthropic_api_key"


def _parrafos(texto: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", texto) if p.strip()]


def _linea_que_contiene(texto: str, fragmento: str) -> str:
    """Primera línea cruda que contiene `fragmento` (el fragmento se busca ya normalizado), normalizada. Vacía si no hay."""
    for linea in texto.splitlines():
        if fragmento in _normalizar_doc(linea):
            return _normalizar_doc(linea)
    return ""


def comprobar_documentacion_de_revision(documentos: dict[str, str]) -> list[str]:
    """Devuelve las frases de la documentación de 062b que faltan. `documentos` es el texto crudo de cada archivo, por ruta.

    Función pura sobre texto: la prueba del repositorio le pasa los archivos reales y los mutantes le pasan texto sintético.
    Cada problema empieza por la ruta del archivo y dice la frase que falta, para que el mutante exija su razón.
    """
    problemas: list[str] = []

    def exigir(archivo: str, descripcion: str, cumple: bool) -> None:
        if not cumple:
            problemas.append(f"{archivo}: {descripcion}")

    stack = documentos[DOC_STACK]
    seccion_ci = _seccion(stack, r"### Integraci\S+ continua")
    entrada_ci = _normalizar_doc(next(iter(_parrafos(seccion_ci)), ""))
    seccion_ci_n = _normalizar_doc(seccion_ci)
    exigir(DOC_STACK, "falta la sección «Integración continua»", bool(entrada_ci))
    exigir(DOC_STACK, "la frase de entrada de «Integración continua» no nombra revision-ia.yml", FLUJO_DE_LA_REVISION in entrada_ci)
    exigir(
        DOC_STACK,
        "«Integración continua» sigue diciendo que la revisión es un trabajo del pipeline («Dos trabajos más… meten la IA en el pipeline»)",
        bool(seccion_ci_n) and LA_REVISION_COMO_TRABAJO_DEL_PIPELINE.search(seccion_ci_n) is None,
    )

    exigir(DOC_TOOLS, "no describe publicar_revision.py", SCRIPT_DE_PUBLICAR.search(_normalizar_doc(documentos[DOC_TOOLS])) is not None)
    herramientas = _normalizar_doc(documentos[DOC_TOOLS])
    exigir(DOC_TOOLS, "no describe test_publicar_revision.py", "test_publicar_revision.py" in herramientas)
    exigir(DOC_TOOLS, "no describe test_definicion_revision.py", "test_definicion_revision.py" in herramientas)

    claude = documentos[DOC_CLAUDE]
    parrafo_de_comandos = _normalizar_doc(next((p for p in _parrafos(claude) if "corren en cada pull request" in p), ""))
    exigir(DOC_CLAUDE, "falta la frase de Comandos sobre lo que corre en cada pull request", bool(parrafo_de_comandos))
    exigir(DOC_CLAUDE, "la frase de Comandos sobre lo que corre en cada pull request no nombra revision-ia.yml", FLUJO_DE_LA_REVISION in parrafo_de_comandos)
    lectura = _linea_que_contiene(claude, "docs/adr/")
    exigir(DOC_CLAUDE, "la lista de lectura no dice «28 decisiones»", DECISIONES_NUEVAS.search(lectura) is not None)
    exigir(DOC_CLAUDE, "sigue diciendo «27 decisiones»", DECISIONES_VIEJAS.search(_normalizar_doc(claude)) is None)

    convenciones = documentos[DOC_CONVENCIONES]
    s12 = _normalizar_doc(_seccion(convenciones, r"## 12\. "))
    fila_mantenimiento = _linea_que_contiene(convenciones, "| mantenimiento |")
    parrafo_de_la_revision = _normalizar_doc(_seccion(convenciones, r"### Qu\S+ revisa la revisi\S+ automatizada de PR"))
    exigir(DOC_CONVENCIONES, "falta la sección «12. La IA en el ciclo de desarrollo»", bool(s12))
    exigir(DOC_CONVENCIONES, "§12 no tiene la fila «Mantenimiento»", bool(fila_mantenimiento))
    exigir(
        DOC_CONVENCIONES,
        "la fila «Mantenimiento» de §12 sigue diciendo «comentarios en línea»",
        bool(fila_mantenimiento) and COMENTARIOS_EN_LINEA.search(fila_mantenimiento) is None,
    )
    exigir(DOC_CONVENCIONES, "§12 no nombra revision-ia.yml bajo la lista de lo que revisa", FLUJO_DE_LA_REVISION in parrafo_de_la_revision)
    for excluido in ("borradores", "bifurcaciones", "dependabot"):
        exigir(DOC_CONVENCIONES, f"§12 no dice que la revisión no cubre {excluido}", excluido in parrafo_de_la_revision)

    devsecops = documentos[DOC_DEVSECOPS]
    fila_de_la_revision = _linea_que_contiene(devsecops, "| la revision automatizada de pr |")
    secreto = _linea_que_contiene(devsecops, "ningun secreto en workflows")
    exigir(DOC_DEVSECOPS, "falta la fila «La revisión automatizada de PR»", bool(fila_de_la_revision))
    exigir(DOC_DEVSECOPS, "la fila de la revisión no nombra revision-ia.yml", FLUJO_DE_LA_REVISION in fila_de_la_revision)
    exigir(DOC_DEVSECOPS, "falta la lista «Ningún secreto en workflows…»", bool(secreto))
    exigir(DOC_DEVSECOPS, "«Ningún secreto en workflows…» no nombra la excepción ANTHROPIC_API_KEY", CLAVE_DEL_MODELO in secreto)
    exigir(DOC_DEVSECOPS, "«Ningún secreto en workflows…» no dice que la excepción es solo de revision-ia.yml", FLUJO_DE_LA_REVISION in secreto)

    for archivo in (DOC_README, DOC_LLMS):
        linea = _linea_que_contiene(documentos[archivo], "docs/adr/readme.md")
        exigir(archivo, "falta la línea de las decisiones de arquitectura", bool(linea))
        exigir(archivo, "la línea de las decisiones de arquitectura no dice «28 ADRs»", DECISIONES_NUEVAS.search(linea) is not None)
        exigir(archivo, "sigue diciendo «27 ADRs»", DECISIONES_VIEJAS.search(linea) is None)

    return problemas


DOCUMENTOS_SINTETICOS = {
    DOC_STACK: """\
### Integración continua

**GitHub Actions**. El pipeline está en `.github/workflows/ci.yml`. Junto a él hay flujos aparte: `enlaces.yml`, `etiqueta-origen.yml`
(requerido) y `revision-ia.yml`, la revisión automatizada, que no es comprobación requerida.

- **`backend`**: ruff y pytest.

Una pieza más del pipeline y una que vive aparte:

- **Prueba de contrato de la API** (TKT-061). Compara el OpenAPI publicado contra el borrador.
- **Revisión automatizada de PR** (TKT-062). Claude Code revisa cada PR en `revision-ia.yml`. **No aprueba ni fusiona**.

### Despliegue
""",
    DOC_TOOLS: """\
## Pruebas

`publicar_revision.py` filtra las citas de la revisión. `test_publicar_revision.py` lo prueba y `test_definicion_revision.py` comprueba
lo que declara `revision-ia.yml`.
""",
    DOC_CLAUDE: """\
6. [`docs/adr/`](docs/adr/) — 28 decisiones con su porqué

Las comprobaciones de estas secciones corren en cada pull request, en [`ci.yml`](.github/workflows/ci.yml), y `revision-ia.yml` es un flujo
aparte que no es comprobación requerida.
""",
    DOC_CONVENCIONES: """\
## 12. La IA en el ciclo de desarrollo

| Fase | Qué hace la IA |
|---|---|
| **Mantenimiento** | Revisa cada pull request y deja un comentario con los hallazgos citados. |

### Qué revisa la revisión automatizada de PR

1. Un `float` en dinero.

Corre en `revision-ia.yml` en dos trabajos. No revisa borradores, bifurcaciones ni los PR de Dependabot. Las instrucciones viven en
`.claude/revision-pr.md`.

## 13. Otra sección
""",
    DOC_DEVSECOPS: """\
| La revisión automatizada de PR | `TKT-062`: `revision-ia.yml`, flujo **aparte**, que comenta y nunca bloquea |

- [ ] Ningún secreto en *workflows*, imagen, Compose ni salida de pasos, salvo `ANTHROPIC_API_KEY` en `revision-ia.yml` (ADR-028)
""",
    DOC_README: "| [Decisiones de arquitectura](docs/adr/README.md) | 28 ADRs en formato MADR |\n",
    DOC_LLMS: "- [Decisiones de arquitectura](docs/adr/README.md): 28 ADRs en formato MADR\n",
}


def _documentos_con(archivo: str, viejo: str, nuevo: str) -> dict[str, str]:
    """Los documentos sintéticos con un solo cambio en `archivo`: el mutante."""
    return {**DOCUMENTOS_SINTETICOS, archivo: sustituir(DOCUMENTOS_SINTETICOS[archivo], viejo, nuevo)}


class MutantesDeLaDocumentacionDeRevision(unittest.TestCase):
    """Fila B7 · TC62-41 sobre texto sintético: la comprobación acepta el control válido y cae, por su razón, ante cada mutante."""

    def test_tkt062_ca12_esc01_mutantes_el_control_valido_pasa(self):
        """CA-12 esc. 1 · TC62-41 — los documentos sintéticos válidos no producen ningún problema: sin esto, los mutantes serían vacuos."""
        self.assertEqual(set(DOCUMENTOS_SINTETICOS), set(DOCUMENTOS_DE_062B))
        self.assertEqual(comprobar_documentacion_de_revision(DOCUMENTOS_SINTETICOS), [])

    def test_tkt062_ca12_esc01_mutantes_la_documentacion_de_062b(self):
        """CA-12 esc. 1 · TC62-41 (rechazo) — quitar de cada documento lo que 062b añade, o dejar lo que retira, pone la comprobación en rojo."""
        casos = {
            "stack: revision-ia.yml quitado de la frase de entrada": (
                _documentos_con(DOC_STACK, " y `revision-ia.yml`, la revisión automatizada, que no es comprobación requerida", ""),
                "no nombra revision-ia.yml",
            ),
            "stack: la frase vieja «Dos trabajos más… meten la IA en el pipeline»": (
                _documentos_con(
                    DOC_STACK,
                    "Una pieza más del pipeline y una que vive aparte:",
                    "Dos trabajos más, que son los que meten la IA en el pipeline sin darle la última palabra:",
                ),
                "sigue diciendo que la revisión es un trabajo del pipeline",
            ),
            "tools/README: publicar_revision.py quitado": (
                _documentos_con(DOC_TOOLS, "`publicar_revision.py` filtra", "el filtro filtra"),
                "no describe publicar_revision.py",
            ),
            "tools/README: test_publicar_revision.py quitado": (
                _documentos_con(DOC_TOOLS, "`test_publicar_revision.py` lo prueba", "alguien lo prueba"),
                "no describe test_publicar_revision.py",
            ),
            "tools/README: test_definicion_revision.py quitado": (
                _documentos_con(DOC_TOOLS, "`test_definicion_revision.py` comprueba", "otra prueba comprueba"),
                "no describe test_definicion_revision.py",
            ),
            "CLAUDE.md: revision-ia.yml quitado de Comandos": (
                _documentos_con(DOC_CLAUDE, ", y `revision-ia.yml` es un flujo\naparte que no es comprobación requerida", ""),
                "no nombra revision-ia.yml",
            ),
            "CLAUDE.md: «27 decisiones»": (
                _documentos_con(DOC_CLAUDE, "28 decisiones", "27 decisiones"),
                "la lista de lectura no dice «28 decisiones»",
            ),
            "convenciones: «comentarios en línea» vuelve a la fila Mantenimiento": (
                _documentos_con(DOC_CONVENCIONES, "deja un comentario con los hallazgos citados", "deja comentarios en línea"),
                "sigue diciendo «comentarios en línea»",
            ),
            "convenciones: revision-ia.yml quitado del párrafo de §12": (
                _documentos_con(DOC_CONVENCIONES, "Corre en `revision-ia.yml` en dos trabajos.", "Corre en dos trabajos."),
                "no nombra revision-ia.yml bajo la lista",
            ),
            "convenciones: las bifurcaciones ya no se mencionan": (
                _documentos_con(DOC_CONVENCIONES, "borradores, bifurcaciones ni", "borradores ni"),
                "no cubre bifurcaciones",
            ),
            "devsecops: revision-ia.yml quitado de la fila de la revisión": (
                _documentos_con(DOC_DEVSECOPS, "`TKT-062`: `revision-ia.yml`, flujo", "`TKT-062`: flujo"),
                "la fila de la revisión no nombra revision-ia.yml",
            ),
            "devsecops: la excepción de ANTHROPIC_API_KEY quitada": (
                _documentos_con(DOC_DEVSECOPS, ", salvo `ANTHROPIC_API_KEY` en `revision-ia.yml` (ADR-028)", ""),
                "no nombra la excepción ANTHROPIC_API_KEY",
            ),
            "README.md: «27 ADRs»": (_documentos_con(DOC_README, "28 ADRs", "27 ADRs"), "no dice «28 ADRs»"),
            "llms.txt: «27 ADRs»": (_documentos_con(DOC_LLMS, "28 ADRs", "27 ADRs"), "no dice «28 ADRs»"),
        }
        exigir_rojo_en_todos(self, comprobar_documentacion_de_revision, casos)


class DocumentacionDeLaRevision(unittest.TestCase):
    """Fila B7 · TC62-41: los documentos de 062b describen la revisión automatizada. Lee los archivos reales; sin la frase, falla."""

    def test_tkt062_ca12_esc01_la_documentacion_de_062b_describe_la_revision(self):
        """CA-12 esc. 1 · TC62-41 — stack §10 nombra `revision-ia.yml` y deja de presentar la revisión como trabajo del pipeline; `tools/README.md`
        describe `publicar_revision.py`; `CLAUDE.md` nombra `revision-ia.yml` y dice 28 decisiones; convenciones §12 ya no dice «comentarios en
        línea» y describe cómo corre; `ingeniero-devsecops.md` nombra `revision-ia.yml` y la excepción de `ANTHROPIC_API_KEY`; `README.md` y
        `llms.txt` dicen 28 ADRs."""
        documentos = {archivo: _leer_doc(archivo) for archivo in DOCUMENTOS_DE_062B}
        problemas = comprobar_documentacion_de_revision(documentos)
        self.assertEqual(problemas, [], f"faltan {len(problemas)} frase(s): " + " | ".join(problemas))


if __name__ == "__main__":
    unittest.main()
