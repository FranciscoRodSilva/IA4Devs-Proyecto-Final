"""Pruebas del verificador de escenarios, `tools/verificar_escenarios.py`.

TKT-009c · filas C1, C2 y C3. Cubren `CA-6`, `CA-7` y `CA-8` de la spec común (ADR-012): un escenario que cuenta y
no tiene un test que lo nombre falla el pipeline. Cada caso construye en un directorio temporal un árbol con un
`docs/04-historias-usuario.md` de ejemplo, un `tools/historias_activas.txt` y archivos de test (Python bajo
`backend/tests/`, TypeScript bajo `frontend/`); ninguno lee el repositorio real, porque hoy no hay un solo test
`test_hdu00X_escNN_…` ni un escenario retirado (objeción 1 de la pasada adversarial).

Documento de ejemplo (`documento_historias`): tres historias y 12 escenarios.

* `HDU-001`, columna `Fase` = `1`: escenarios 1 a 5. Los 4 y 5 llevan ` · fase 1` y son los que se retiran.
* `HDU-002`, columna `Fase` = `1+2`: escenarios 1 a 4 sin marca y el 5 con ` · fase 2`.
* `HDU-003`, columna `Fase` = `2`: escenarios 1 y 2, sin marca.

El parámetro `retiro` reproduce los tres estados del documento real: `None` (nada se retira), `"nota"` (solo prosa,
como está hoy HDU-006) y `"segmento"` (el título lleva ` · retirado por TKT-069`, como queda tras TKT-069). La prosa
de retiro menciona a propósito `retirado por TKT-069`: una nota fuera del título no retira nada.

Dos niveles de prueba por caso, con el mismo identificador `TC-NN`:

* `test_tcNN_leer_…`: la lectura (`leer_historias`, `leer_activas`, `recolectar_tests`), sin pasar por `main`.
* `test_tcNN_salida_…`: el contrato completo de `main`: código de salida, etiqueta exacta (`FALTA`, `PENDIENTE`,
  `RETIRADO`, `ERROR`), identificador y línea de resumen.

El diseño asigna TC-44 a TC-49 y TC-55 a la fila C1, pero su resultado observable (el código y las etiquetas) lo
produce `main`. Por eso la compuerta de C1 es `-k leer_`; los `salida_` de esos casos se ponen en verde en C3.

Mutantes de la parte c que estas pruebas deben matar (tabla de mutación del diseño):

* `PATRON_HDU` sin el anclaje `(?=$|[_\\s·])`: cae `test_tc42_salida_esc04x_no_cubre_por_el_anclaje`.
* Fase calculada solo por la marca, sin la columna `Fase`: caen `test_tc47_leer_historia_fase_2_sin_marca` y
  `test_tc47_salida_historia_fase_2_sin_marca_es_pendiente`.
* Retiro aceptado por cualquier mención de «retir» en el bloque: caen `test_tc49_leer_nota_en_prosa_no_retira` y
  `test_tc49_salida_nota_de_retiro_en_prosa_no_esquiva_el_verificador`.
* Comparación con la base desactivada: caen `test_tc53_salida_historia_que_sale_de_la_lista_es_error` y
  `test_tc54_salida_fase_2_que_sale_de_la_lista_es_error`.

TC-56 (fila C4) está al final: es la única clase que lee el repositorio real y no un árbol de ejemplo. TC-57 (definición
del trabajo `herramientas`) vive en `test_definicion_ci.py`, y TC-58 (ensayo en el pipeline) es de la fila C5.

Ejecución, desde la raíz del repositorio:

    python -m unittest tools.tests.test_verificar_escenarios -v
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

import verificar_escenarios as ve  # noqa: E402

# ---------------------------------------------------------------------------------------------------------
# El documento de ejemplo
# ---------------------------------------------------------------------------------------------------------

TITULOS = {
    "HDU-001": {
        1: "Alta de obra con sus parámetros",
        2: "Código de obra duplicado",
        3: "Congelado de la línea base",
        4: "Mano de obra y avance simulados, y rotulados como tales · fase 1",
        5: "Un importe simulado nunca entra en el disponible · fase 1",
    },
    "HDU-002": {
        1: "Requisición dentro del importe presupuestado",
        2: "Requisición de una partida sin presupuesto de control",
        3: "Requisición que consume exactamente el disponible",
        4: "La requisición excede el importe presupuestado",
        5: "Intento de levantar una requisición sin conexión · fase 2",
    },
    "HDU-003": {
        1: "Alta de una cuadrilla en la obra",
        2: "Cuadrilla duplicada en la misma obra",
    },
}

FILA_HDU001 = "| HDU-001 | [Alta de obra](#hdu-001--alta-de-obra) | **Must** | C1 | Alta | 14 | 1 |"
FILA_HDU002 = (
    "| HDU-002 | [Requisición con control de presupuesto](#hdu-002--requisición-con-control-de-presupuesto) "
    "| **Must** | C2 | Alta | 8 | 1+2 |"
)
FILA_HDU003 = "| HDU-003 | [Catálogo de cuadrillas](#hdu-003--catálogo-de-cuadrillas) | *Should* | C5 | Baja | 5 | 2 |"

NOTA_DE_RETIRO = (
    "> **Los escenarios 4 y 5 tienen vigencia de fase 1.** Existen mientras existe el adaptador simulado y figuran\n"
    "> como retirado por TKT-069 en el backlog. Cuando TKT-069 lo retira, salen del verificador de escenarios sin\n"
    "> reescribir su texto.\n"
)


def _escenario(numero: int, titulo: str) -> str:
    return (
        f"**Escenario {numero}: {titulo}**\n"
        "- **Dado que** el usuario está en la pantalla\n"
        "- **Cuando** ejecuta la acción\n"
        "- **Entonces** el sistema responde como se espera.\n\n"
    )


def _seccion(historia: str, nombre: str, retiro: str | None = None) -> str:
    texto = f"## {historia} · {nombre}\n\n**Título de la Historia de Usuario: {historia} - {nombre}**\n\n"
    texto += "*Como* usuario *quiero* una acción *para* un resultado.\n\n### Criterios de aceptación\n\n"
    for numero, titulo in TITULOS[historia].items():
        if retiro == "segmento" and historia == "HDU-001" and numero in (4, 5):
            titulo += " · retirado por TKT-069"
        texto += _escenario(numero, titulo)
    if historia == "HDU-001" and retiro is not None:
        texto += NOTA_DE_RETIRO + "\n### Definition of Done\n\n"
        texto += "- [ ] Los escenarios 4 y 5 tienen **vigencia de fase 1** y los retira TKT-069\n\n"
    else:
        texto += f"### Definition of Done\n\n- [ ] Los {len(TITULOS[historia])} escenarios pasan\n\n"
    return texto


def documento_historias(retiro: str | None = None) -> str:
    """Construye el `docs/04-historias-usuario.md` de ejemplo. `retiro` es `None`, `"nota"` o `"segmento"`."""
    encabezado = (
        "# Historias de usuario\n\nPreámbulo del documento.\n\n---\n\n## El conjunto\n\n"
        "| # | Historia | Prioridad | Cap. | Complejidad | SP | Fase |\n|---|---|---|---|---|---|---|\n"
        f"{FILA_HDU001}\n{FILA_HDU002}\n{FILA_HDU003}\n\n"
        "**Total: 27 SP · 12 escenarios.**\n\n"
        "## Dependencias entre historias\n\n"
        "| De | A | Tipo | Nota |\n|---|---|---|---|\n"
        "| HDU-001 | HDU-002 | Bloquea | HDU-002 esc. 4 rechaza requisiciones sin línea base |\n"
        "| HDU-002 | HDU-003 | Continúa | La cuadrilla se da de alta después |\n\n---\n\n"
    )
    cuerpo = _seccion("HDU-001", "Alta de obra", retiro)
    cuerpo += _seccion("HDU-002", "Requisición con control de presupuesto")
    cuerpo += _seccion("HDU-003", "Catálogo de cuadrillas")
    return encabezado + cuerpo


# ---------------------------------------------------------------------------------------------------------
# El árbol temporal: historias, lista de activas y archivos de test
# ---------------------------------------------------------------------------------------------------------

ACTIVAS_VACIAS = (
    "# Historias con ticket en curso, una por línea.\n"
    "# La actualiza la planificación de cada sprint.\n"
    "# Ninguna historia sale nunca de esta lista (ADR-012).\n"
)


def nombres_hdu(historia: str, *numeros: int) -> list[str]:
    """Nombres de test de Python que cubren los escenarios dados de una historia, p. ej. `test_hdu002_esc04_…`."""
    return [
        f"test_hdu{historia[-3:]}_esc{n:02d}_" + re.sub(r"\W+", "_", TITULOS[historia][n].split(" · ")[0].lower())
        for n in numeros
    ]


def it_(nombre: str) -> str:
    return f'it("{nombre}", () => {{}});'


def test_(nombre: str) -> str:
    return f"test('{nombre}', () => {{}});"


def describe_(nombre: str) -> str:
    return f"describe(`{nombre}`, () => {{}});"


def _fuente_python(nombres: list[str]) -> str:
    texto = "import unittest\n\n\nclass Pruebas(unittest.TestCase):\n"
    for nombre in nombres:
        texto += f"    def {nombre}(self) -> None:\n        pass\n\n"
    return texto


def linea_py(indice: int) -> int:
    """Línea de la definición número `indice` (desde 0) en un archivo escrito por `_fuente_python`."""
    return 5 + 3 * indice


def linea_ts(indice: int) -> int:
    """Línea de la llamada número `indice` (desde 0) en un archivo escrito por `_fuente_typescript`."""
    return 3 + indice


def _fuente_typescript(lineas: list[str]) -> str:
    return 'import { describe, it, test } from "vitest";\n\n' + "\n".join(lineas) + "\n"


def construir_raiz(
    directorio: Path,
    *,
    activas: str | None = ACTIVAS_VACIAS,
    retiro: str | None = None,
    tests: dict[str, list[str]] | None = None,
    historias_md: str | None = None,
) -> Path:
    """Crea `repo/` bajo `directorio` y devuelve su ruta.

    `activas=None` no crea `tools/historias_activas.txt`. En `tests`, la clave es la ruta relativa: para un `.py`
    el valor son nombres de función y para un `.ts` o `.tsx` son líneas de código completas (`it_`, `test_`,
    `describe_`).
    """
    raiz = directorio / "repo"
    (raiz / "docs").mkdir(parents=True)
    (raiz / "tools").mkdir()
    texto = historias_md if historias_md is not None else documento_historias(retiro)
    (raiz / "docs" / "04-historias-usuario.md").write_text(texto, encoding="utf-8")
    if activas is not None:
        (raiz / "tools" / "historias_activas.txt").write_text(activas, encoding="utf-8")
    for ruta, contenido in (tests or {}).items():
        destino = raiz / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        fuente = _fuente_python(contenido) if ruta.endswith(".py") else _fuente_typescript(contenido)
        destino.write_text(fuente, encoding="utf-8")
    return raiz


# ---------------------------------------------------------------------------------------------------------
# Lectura de la salida de `main`
# ---------------------------------------------------------------------------------------------------------


def hechos(salida: str, etiqueta: str) -> list[str]:
    """Texto de cada línea que empieza por la etiqueta exacta, sin la etiqueta ni el relleno."""
    resultado = []
    for linea in salida.splitlines():
        coincide = re.match(rf"^{etiqueta}\s+(\S.*?)\s*$", linea)
        if coincide:
            resultado.append(coincide.group(1))
    return resultado


def identificadores(lineas: list[str]) -> list[str]:
    """`HDU-002 esc. 4 · título` se reduce a `HDU-002 esc. 4`."""
    return [linea.split(" · ")[0] for linea in lineas]


def resumen(salida: str) -> str:
    lineas = [linea for linea in salida.splitlines() if linea.startswith("Escenarios:")]
    return lineas[-1] if lineas else ""


def resumen_esperado(
    total: int, exigidos: int, cubiertos: int, faltan: int, pendientes: int, retirados: int, hdu: int, fundacion: int
) -> str:
    return (
        f"Escenarios: {total} · exigidos {exigidos} · cubiertos {cubiertos} · faltan {faltan} · "
        f"pendientes {pendientes} · retirados {retirados} · tests HDU {hdu} · tests de fundación {fundacion}"
    )


class BaseConRaiz(unittest.TestCase):
    """Directorio temporal por prueba y ejecución de `main` con la salida capturada."""

    def setUp(self) -> None:
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.directorio = Path(temporal.name)

    def raiz(
        self,
        *,
        activas: str | None = ACTIVAS_VACIAS,
        retiro: str | None = None,
        tests: dict[str, list[str]] | None = None,
        historias_md: str | None = None,
    ) -> Path:
        return construir_raiz(self.directorio, activas=activas, retiro=retiro, tests=tests, historias_md=historias_md)

    def correr_separado(self, raiz: Path, base: str | None = None) -> tuple[int, str, str]:
        """Ejecuta `main` y devuelve (código, stdout, stderr) por separado."""
        argumentos = ["--raiz", str(raiz)]
        if base is not None:
            archivo = self.directorio / "activas_base.txt"
            archivo.write_text(base, encoding="utf-8")
            argumentos += ["--activas-base", str(archivo)]
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = ve.main(argumentos)
        return codigo, salida.getvalue(), error.getvalue()

    def correr(self, raiz: Path, base: str | None = None) -> tuple[int, str]:
        """Ejecuta `main` y devuelve (código, salida estándar y de error juntas)."""
        codigo, salida, error = self.correr_separado(raiz, base)
        return codigo, salida + error


# ---------------------------------------------------------------------------------------------------------
# leer_historias
# ---------------------------------------------------------------------------------------------------------


class PruebasLeerHistorias(unittest.TestCase):
    """Fila C1: lectura del documento de historias."""

    def test_tc40_leer_historias_extrae_historias_numeros_y_titulos(self) -> None:
        """CA-6 esc. 1 · el informe nombra «HDU-00X esc. N»: se leen la historia, el número y el título."""
        historias = ve.leer_historias(documento_historias())

        self.assertEqual(set(historias), {"HDU-001", "HDU-002", "HDU-003"})
        self.assertEqual([e.numero for e in historias["HDU-001"]], [1, 2, 3, 4, 5])
        self.assertEqual([e.numero for e in historias["HDU-002"]], [1, 2, 3, 4, 5])
        self.assertEqual([e.numero for e in historias["HDU-003"]], [1, 2])
        self.assertEqual(sum(len(e) for e in historias.values()), 12)
        self.assertEqual(
            historias["HDU-002"][3],
            ve.Escenario(
                historia="HDU-002",
                numero=4,
                titulo="La requisición excede el importe presupuestado",
                fase=1,
                retirado_por=None,
            ),
        )

    def test_tc40_leer_historias_ignora_las_filas_de_otras_tablas(self) -> None:
        """CA-6 · la tabla de dependencias también empieza por «| HDU-001 |» y no es la tabla «El conjunto»."""
        historias = ve.leer_historias(documento_historias())

        self.assertEqual({e.fase for e in historias["HDU-001"]}, {1})

    def test_tc45_leer_historias_la_marca_fase_2_del_titulo_fija_la_fase(self) -> None:
        """CA-7 esc. 2 · el escenario marcado « · fase 2» es de fase 2 y los demás de su historia, de fase 1."""
        escenarios = ve.leer_historias(documento_historias())["HDU-002"]

        self.assertEqual([e.fase for e in escenarios], [1, 1, 1, 1, 2])

    def test_tc47_leer_historia_1mas2_sin_marca_es_fase_1(self) -> None:
        """CA-7 esc. 3 · en una historia «1+2» el escenario sin marca cuenta como de fase 1."""
        escenarios = ve.leer_historias(documento_historias())["HDU-002"]

        self.assertEqual([e.fase for e in escenarios if e.numero <= 4], [1, 1, 1, 1])

    def test_tc47_leer_historia_fase_2_sin_marca(self) -> None:
        """CA-7 esc. 3 · en una historia de columna «2» el escenario sin marca es de fase 2.

        Mata el mutante «fase solo por la marca, sin la columna Fase».
        """
        escenarios = ve.leer_historias(documento_historias())["HDU-003"]

        self.assertEqual([e.fase for e in escenarios], [2, 2])

    def test_tc48_leer_el_segmento_retirado_por_fija_el_retiro(self) -> None:
        """CA-7 esc. 4 · « · retirado por TKT-069» en el título retira el escenario y deja intacta su fase."""
        historias = ve.leer_historias(documento_historias("segmento"))

        retirados = {(e.historia, e.numero): e for e in historias["HDU-001"] if e.retirado_por}
        self.assertEqual(set(retirados), {("HDU-001", 4), ("HDU-001", 5)})
        self.assertEqual({e.retirado_por for e in retirados.values()}, {"TKT-069"})
        self.assertEqual({e.fase for e in retirados.values()}, {1})
        self.assertEqual(sum(len(e) for e in historias.values()), 12)
        self.assertTrue(all(e.retirado_por is None for e in historias["HDU-002"] + historias["HDU-003"]))

    def test_tc49_leer_nota_en_prosa_no_retira(self) -> None:
        """CA-7 esc. 5 · una nota de retiro fuera del título, aunque diga «retirado por TKT-069», no retira nada.

        Mata el mutante «retiro por cualquier mención de retir en el bloque».
        """
        historias = ve.leer_historias(documento_historias("nota"))

        self.assertTrue(all(e.retirado_por is None for e in historias["HDU-001"]))

    def test_tc55_leer_historia_sin_fila_en_la_tabla_es_entrada_invalida(self) -> None:
        """Códigos · una sección «## HDU-003 · …» sin fila en la tabla «El conjunto» está mal formada."""
        sin_fila = documento_historias().replace(FILA_HDU003 + "\n", "")

        with self.assertRaises(ve.EntradaInvalida) as contexto:
            ve.leer_historias(sin_fila)

        self.assertIn("HDU-003", str(contexto.exception))


class PruebasLeerActivas(unittest.TestCase):
    """Fila C1: lectura de `tools/historias_activas.txt`."""

    def test_tc44_leer_activas_solo_lista_las_historias_escritas(self) -> None:
        """CA-7 esc. 1 · una historia que no está en la lista no es activa; los comentarios y vacías se ignoran."""
        activas, fase_2 = ve.leer_activas(ACTIVAS_VACIAS + "\nHDU-001\n")

        self.assertEqual(activas, frozenset({"HDU-001"}))
        self.assertFalse(fase_2)

    def test_tc44_leer_activas_solo_comentarios_no_tiene_historias(self) -> None:
        """CA-7 esc. 1 · el archivo inicial del ticket, con tres comentarios, no activa ninguna historia."""
        self.assertEqual(ve.leer_activas(ACTIVAS_VACIAS), (frozenset(), False))

    def test_tc46_leer_activas_la_linea_fase_2_inicia_la_fase_2(self) -> None:
        """CA-7 esc. 2 · con la línea exacta «fase 2» la fase 2 está iniciada y no cuenta como historia."""
        activas, fase_2 = ve.leer_activas(ACTIVAS_VACIAS + "HDU-002\nfase 2\n")

        self.assertEqual(activas, frozenset({"HDU-002"}))
        self.assertTrue(fase_2)

    def test_tc55_leer_activas_linea_invalida_es_entrada_invalida(self) -> None:
        """Códigos · una línea que no es «HDU-NNN», «fase 2», comentario ni vacía está mal formada y se nombra."""
        for linea in ("HDU-1", "hdu-001", "fase 3", "Fase 2", "texto suelto"):
            with self.subTest(linea=linea):
                with self.assertRaises(ve.EntradaInvalida) as contexto:
                    ve.leer_activas(ACTIVAS_VACIAS + linea + "\n")

                self.assertIn(linea, str(contexto.exception))


# ---------------------------------------------------------------------------------------------------------
# recolectar_tests
# ---------------------------------------------------------------------------------------------------------


class PruebasRecolectarTests(BaseConRaiz):
    """Fila C2: qué archivos y qué nombres de test se leen (A-8)."""

    def test_tc41_recolectar_python_devuelve_archivo_linea_y_nombre(self) -> None:
        """CA-6 esc. 2 · un `def test_…` bajo `backend/tests/` se lee con su ruta relativa con «/» y su línea."""
        nombres = nombres_hdu("HDU-002", 1, 4)
        raiz = self.raiz(
            tests={
                "backend/tests/presupuesto/test_requisicion.py": nombres,
                "backend/tests/ayuda.py": ["test_hdu002_esc02_oculto_en_un_archivo_sin_prefijo"],
            }
        )

        encontrados = sorted(ve.recolectar_tests(raiz), key=lambda t: (t.archivo, t.linea))

        archivo = "backend/tests/presupuesto/test_requisicion.py"
        self.assertEqual(
            encontrados,
            [ve.NombreDeTest(archivo, linea_py(0), nombres[0]), ve.NombreDeTest(archivo, linea_py(1), nombres[1])],
        )

    def test_tc43_recolectar_typescript_lee_el_primer_argumento_de_it_test_y_describe(self) -> None:
        """CA-6 esc. 2 · `it(`, `test(` y `describe(` con comillas dobles, simples o de plantilla dan el nombre."""
        raiz = self.raiz(
            tests={
                "frontend/src/a.test.ts": [
                    it_("hdu002_esc01 · uno"),
                    test_("hdu002_esc02 · dos"),
                    describe_("hdu002_esc03 · tres"),
                ],
                "frontend/src/componentes/b.test.tsx": [it_("hdu002_esc04 · cuatro")],
                "frontend/scripts/c.test.ts": [it_("tkt008_ca3_esc02 · cinco")],
                "frontend/e2e/d.spec.ts": [test_("hdu003_esc01 · seis")],
            }
        )

        nombres = {t.nombre for t in ve.recolectar_tests(raiz)}

        self.assertEqual(
            nombres,
            {
                "hdu002_esc01 · uno",
                "hdu002_esc02 · dos",
                "hdu002_esc03 · tres",
                "hdu002_esc04 · cuatro",
                "tkt008_ca3_esc02 · cinco",
                "hdu003_esc01 · seis",
            },
        )

    def test_tc43_recolectar_typescript_devuelve_archivo_y_linea(self) -> None:
        """CA-6 esc. 2 · cada nombre de TypeScript lleva su ruta relativa con «/» y la línea de la llamada."""
        raiz = self.raiz(tests={"frontend/src/a.test.ts": [it_("hdu002_esc01 · uno"), it_("hdu002_esc02 · dos")]})

        encontrados = sorted(ve.recolectar_tests(raiz), key=lambda t: t.linea)

        self.assertEqual(
            encontrados,
            [
                ve.NombreDeTest("frontend/src/a.test.ts", linea_ts(0), "hdu002_esc01 · uno"),
                ve.NombreDeTest("frontend/src/a.test.ts", linea_ts(1), "hdu002_esc02 · dos"),
            ],
        )

    def test_tc43_recolectar_typescript_ignora_lineas_comentadas(self) -> None:
        """CA-6 · rechazo · un `it(…)` dentro de `//`, de `/* … */` o de un bloque con « * » no es un test.

        Límite de A-8, que el lector no cubre: un comentario al final de una línea de código
        (`foo(); // it("hdu002_esc01_x", …)`) sigue leyéndose como test. Solo se ignoran las líneas que empiezan por
        un comentario.
        """
        raiz = self.raiz(
            tests={
                "frontend/src/x.test.ts": [
                    '// it("hdu002_esc01_x", () => {});',
                    '/* test("hdu002_esc02_y", () => {}); */',
                    '/*\n * it("hdu002_esc03_z", () => {});\n */',
                ]
            }
        )

        self.assertEqual(ve.recolectar_tests(raiz), [])

    def test_tc43_recolectar_typescript_lee_el_test_real_que_sigue_a_un_bloque_comentado(self) -> None:
        """CA-6 · el filtro de comentarios no se come lo que viene después: el `it(…)` real tras el bloque se lee."""
        raiz = self.raiz(
            tests={
                "frontend/src/x.test.ts": [
                    '/*\n * it("hdu002_esc03_comentado", () => {});\n */',
                    it_("hdu002_esc04_real"),
                ]
            }
        )

        nombres = [t.nombre for t in ve.recolectar_tests(raiz)]

        self.assertEqual(nombres, ["hdu002_esc04_real"])

    def test_tc43_recolectar_typescript_bloque_sin_asterisco_y_codigo_tras_el_cierre(self) -> None:
        """CA-6 · un bloque `/* … */` cuyas líneas interiores no empiezan por « * » se ignora entero, y el código que
        sigue a su cierre, en la misma línea o en otra, se lee.

        Sin asteriscos interiores, nada descarta las líneas del bloque salvo que el lector lo siga como bloque.
        """
        raiz = self.raiz(
            tests={
                "frontend/src/x.test.ts": [
                    '/*\n it("hdu002_esc01_dentro_sin_asterisco", () => {});\n texto\n*/',
                    '/* nota */ ' + it_("hdu002_esc02_misma_linea"),
                    '/*\n nota\n*/ ' + it_("hdu002_esc03_tras_cierre_multilinea"),
                    it_("hdu002_esc04_con_url_http://x.test/a"),
                ]
            }
        )

        nombres = [t.nombre for t in ve.recolectar_tests(raiz)]

        self.assertEqual(
            nombres,
            [
                "hdu002_esc02_misma_linea",
                "hdu002_esc03_tras_cierre_multilinea",
                "hdu002_esc04_con_url_http://x.test/a",
            ],
        )

    def test_tc43_recolectar_typescript_una_linea_con_asterisco_suelta_fuera_de_bloque_no_es_test(self) -> None:
        """CA-6 · rechazo · fuera de un bloque, una línea que empieza por « * » (resto de un comentario cortado) se descarta."""
        raiz = self.raiz(tests={"frontend/src/x.test.ts": [' * ' + it_("hdu002_esc01_suelta")]})

        self.assertEqual(ve.recolectar_tests(raiz), [])

    def test_tc43_recolectar_salta_node_modules_y_carpetas_ajenas(self) -> None:
        """CA-6 · no se leen `node_modules`, ni tests fuera de las carpetas de A-8, ni archivos que no son de test."""
        raiz = self.raiz(
            tests={
                "frontend/src/node_modules/paquete/x.test.ts": [it_("hdu002_esc04 · de una dependencia")],
                "frontend/otra/y.test.ts": [it_("hdu002_esc04 · fuera de las carpetas")],
                "frontend/src/z.ts": [it_("hdu002_esc04 · no es un archivo de test")],
                "backend/otra/test_w.py": ["test_hdu002_esc04_fuera_de_las_carpetas"],
            }
        )

        self.assertEqual(ve.recolectar_tests(raiz), [])


# ---------------------------------------------------------------------------------------------------------
# main: el contrato de la salida
# ---------------------------------------------------------------------------------------------------------


class PruebasSalida(BaseConRaiz):
    """Filas C2 y C3: código de salida, etiquetas exactas, identificadores y resumen."""

    # ----- CA-6 · lo que cuenta y falla ------------------------------------------------------------------

    def test_tc40_salida_escenario_activo_sin_test_falla_y_se_nombra(self) -> None:
        """CA-6 esc. 1 · HDU-002 activa con el esc. 4 sin test: código 1 y «FALTA HDU-002 esc. 4» con su título."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-002\n", tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3)})

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(hechos(salida, "FALTA"), ["HDU-002 esc. 4 · La requisición excede el importe presupuestado"])
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 3, 1, 8, 0, 3, 0))

    def test_tc41_salida_escenario_cubierto_pasa(self) -> None:
        """CA-6 esc. 2 · con `test_hdu002_esc04_…` y los otros tres de fase 1: código 0 y ningún «FALTA»."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-002\n", tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3, 4)})

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "FALTA"), [])
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 4, 0, 8, 0, 4, 0))

    def test_tc41_salida_test_de_una_historia_inactiva_no_es_error(self) -> None:
        """CA-6 · un test de un escenario que existe, de una historia aún no activa, no falla ni se reporta."""
        raiz = self.raiz(tests={"backend/tests/test_alta.py": nombres_hdu("HDU-001", 1)})

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(hechos(salida, "FALTA"), [])

    def test_tc42_salida_test_con_numero_sin_prefijo_esc_no_cubre(self) -> None:
        """CA-6 esc. 3 · rechazo · `test_hdu002_4_…` no nombra el escenario: sigue faltando y el pipeline falla."""
        self._comprobar_que_no_cubre("test_hdu002_4_requisicion_excede_importe")

    def test_tc42_salida_test_con_la_palabra_escenario_no_cubre(self) -> None:
        """CA-6 esc. 3 · rechazo · `test_hdu002_escenario4_…` no nombra el escenario: sigue faltando."""
        self._comprobar_que_no_cubre("test_hdu002_escenario4_requisicion_excede_importe")

    def test_tc42_salida_esc04x_no_cubre_por_el_anclaje(self) -> None:
        """CA-6 esc. 3 · rechazo · `test_hdu002_esc04x_…` no cubre el esc. 4: tras «04» no hay «_», espacio ni «·».

        Mata el mutante «PATRON_HDU sin el anclaje (?=$|[_\\s·])»: sin él, el prefijo «esc04» casaría y el esc. 4
        quedaría cubierto con código 0.
        """
        self._comprobar_que_no_cubre("test_hdu002_esc04x_requisicion_excede_importe")

    def _comprobar_que_no_cubre(self, nombre_mal_escrito: str) -> None:
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3) + [nombre_mal_escrito]},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-002 esc. 4"])
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 3, 1, 8, 0, 3, 0))

    def test_tc43_salida_it_de_typescript_cubre_el_escenario(self) -> None:
        """CA-6 esc. 2 · `it("hdu002_esc04 · …")` en un `.test.ts` cubre el esc. 4 igual que un test de Python."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={
                "backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3),
                "frontend/src/requisicion.test.ts": [it_("hdu002_esc04 · La requisición excede el importe")],
            },
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "FALTA"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 4, 0, 8, 0, 4, 0))

    def test_tc43_salida_cada_forma_de_test_de_typescript_cubre(self) -> None:
        """CA-6 esc. 2 · `test(`, `describe(` y `*.spec.ts` de e2e cubren los esc. 1 a 3; el 4 queda sin test."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={
                "frontend/src/a.test.ts": [test_("hdu002_esc01 · uno"), describe_("hdu002_esc02 · dos")],
                "frontend/e2e/b.spec.ts": [test_("hdu002_esc03 · tres")],
            },
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-002 esc. 4"])

    def test_tc43_salida_un_test_dentro_de_node_modules_no_cubre(self) -> None:
        """CA-6 · rechazo · un `.test.ts` de una dependencia en `node_modules` no cubre el escenario."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={
                "backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3),
                "frontend/src/node_modules/paquete/x.test.ts": [it_("hdu002_esc04 · de una dependencia")],
            },
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-002 esc. 4"])

    # ----- CA-7 · lo que todavía no cuenta ---------------------------------------------------------------

    def test_tc44_salida_historia_sin_ticket_se_informa_pendiente_con_su_recuento(self) -> None:
        """CA-7 esc. 1 · sin historias activas y sin tests: código 0 y «PENDIENTE» por historia, con sus escenarios."""
        raiz = self.raiz()

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertCountEqual(
            hechos(salida, "PENDIENTE"),
            [
                "HDU-001 · 5 escenarios · historia sin ticket en curso",
                "HDU-002 · 5 escenarios · historia sin ticket en curso",
                "HDU-003 · 2 escenarios · historia sin ticket en curso",
            ],
        )
        self.assertEqual(hechos(salida, "FALTA"), [])
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 0, 0, 0, 12, 0, 0, 0))

    def test_tc45_salida_fase_2_sin_iniciar_es_pendiente_y_fase_1_sin_test_falla(self) -> None:
        """CA-7 esc. 2 · HDU-002 activa, sin tests: el esc. 5 «· fase 2» es PENDIENTE y los 1 a 4 son FALTA."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-002\n")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(
            identificadores(hechos(salida, "FALTA")),
            ["HDU-002 esc. 1", "HDU-002 esc. 2", "HDU-002 esc. 3", "HDU-002 esc. 4"],
        )
        pendientes = hechos(salida, "PENDIENTE")
        self.assertIn("HDU-002 esc. 5 · fase 2 sin iniciar", pendientes)
        self.assertNotIn("HDU-002 · 5 escenarios · historia sin ticket en curso", pendientes)
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 0, 4, 8, 0, 0, 0))

    def test_tc46_salida_con_la_linea_fase_2_el_escenario_de_fase_2_pasa_a_faltar(self) -> None:
        """CA-7 esc. 2 · con «fase 2» en la lista, el esc. 5 de HDU-002 sin test es FALTA y ya no es PENDIENTE."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\nfase 2\n",
            tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3, 4)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-002 esc. 5"])
        self.assertNotIn("HDU-002 esc. 5 · fase 2 sin iniciar", hechos(salida, "PENDIENTE"))
        self.assertEqual(resumen(salida), resumen_esperado(12, 5, 4, 1, 7, 0, 4, 0))

    def test_tc47_salida_historia_1mas2_sin_marca_cuenta_como_fase_1(self) -> None:
        """CA-7 esc. 3 · HDU-002 («1+2») sin test del esc. 1, que no lleva marca: FALTA, no PENDIENTE."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 2, 3, 4)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-002 esc. 1"])

    def test_tc47_salida_historia_fase_2_sin_marca_es_pendiente(self) -> None:
        """CA-7 esc. 3 · HDU-003 (columna «2») activa y sin tests: sus escenarios sin marca son PENDIENTE y pasa.

        Mata el mutante «fase solo por la marca, sin la columna Fase»: daría FALTA y código 1.
        """
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\nHDU-003\n",
            tests={"backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3, 4)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "FALTA"), [])
        pendientes = hechos(salida, "PENDIENTE")
        self.assertIn("HDU-003 esc. 1 · fase 2 sin iniciar", pendientes)
        self.assertIn("HDU-003 esc. 2 · fase 2 sin iniciar", pendientes)
        self.assertIn("HDU-002 esc. 5 · fase 2 sin iniciar", pendientes)
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 4, 0, 8, 0, 4, 0))

    def test_tc47_salida_historia_fase_2_sin_marca_falta_cuando_la_fase_2_inicia(self) -> None:
        """CA-7 esc. 3 · con «fase 2» en la lista, HDU-003 activa y sin tests: sus dos escenarios son FALTA."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\nfase 2\n")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-003 esc. 1", "HDU-003 esc. 2"])

    def test_tc48_salida_escenarios_retirados_no_se_exigen_y_se_listan(self) -> None:
        """CA-7 esc. 4 · HDU-001 esc. 4 y 5 con « · retirado por TKT-069», sin tests: código 0 y «RETIRADO»."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-001\n",
            retiro="segmento",
            tests={"backend/tests/test_alta.py": nombres_hdu("HDU-001", 1, 2, 3)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "FALTA"), [])
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertCountEqual(
            hechos(salida, "RETIRADO"), ["HDU-001 esc. 4 · TKT-069", "HDU-001 esc. 5 · TKT-069"]
        )
        self.assertEqual(resumen(salida), resumen_esperado(12, 3, 3, 0, 7, 2, 3, 0))

    def test_tc49_salida_nota_de_retiro_en_prosa_no_esquiva_el_verificador(self) -> None:
        """CA-7 esc. 5 · rechazo · HDU-001 con la nota de retiro solo en prosa y sin tests de 4 y 5: FALTA y código 1.

        Mata el mutante «retiro por cualquier mención de retir en el bloque».
        """
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-001\n",
            retiro="nota",
            tests={"backend/tests/test_alta.py": nombres_hdu("HDU-001", 1, 2, 3)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(identificadores(hechos(salida, "FALTA")), ["HDU-001 esc. 4", "HDU-001 esc. 5"])
        self.assertEqual(hechos(salida, "RETIRADO"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 5, 3, 2, 7, 0, 3, 0))

    # ----- CA-8 · fundación, tests ajenos, inexistentes y la lista --------------------------------------

    def test_tc50_salida_tests_de_fundacion_se_admiten_y_se_cuentan(self) -> None:
        """CA-8 esc. 1 · `test_tkt003_ca10_esc01_…`, `tkt009a_ca6_…` y `"tkt008_ca3_esc02 · …"`: sin error y contados."""
        raiz = self.raiz(
            tests={
                "backend/tests/test_fundacion.py": [
                    "test_tkt003_ca10_esc01_rol_de_aplicacion",
                    "test_tkt009a_ca6_esc02_escenario_activo_sin_test",
                ],
                "frontend/src/armazon.test.ts": [it_("tkt008_ca3_esc02 · cierre de sesión")],
            }
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(hechos(salida, "FALTA"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 0, 0, 0, 12, 0, 0, 3))

    def test_tc50_salida_un_test_de_fundacion_no_cubre_ningun_escenario(self) -> None:
        """CA-8 esc. 1 · un test de fundación con «esc01» no se cuenta contra HDU-001 esc. 1: sigue faltando."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-001\n",
            tests={"backend/tests/test_x.py": ["test_tkt001_ca2_esc01_alta"] + nombres_hdu("HDU-001", 2, 3)},
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(
            identificadores(hechos(salida, "FALTA")), ["HDU-001 esc. 1", "HDU-001 esc. 4", "HDU-001 esc. 5"]
        )
        self.assertEqual(hechos(salida, "ERROR"), [])

    def test_tc51_salida_tests_sin_prefijo_de_escenario_se_ignoran(self) -> None:
        """CA-8 esc. 2 · `test_identidad_…` y `tkt004_ca11_…` sin «escNN»: ignorados, código 0, ni HDU ni fundación."""
        raiz = self.raiz(
            tests={
                "backend/tests/test_identidad.py": ["test_identidad_inicio_de_sesion", "test_tkt004_ca11_sin_escenario"],
                "frontend/src/sesion.test.ts": [it_("tkt004_ca11 · sin escenario")],
            }
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])
        self.assertEqual(resumen(salida), resumen_esperado(12, 0, 0, 0, 12, 0, 0, 0))

    def test_tc52_salida_test_de_una_historia_inexistente_es_error(self) -> None:
        """CA-8 esc. 3 · rechazo · `test_hdu099_esc01_…`: código 1 y «ERROR» con archivo:línea, test e identificador."""
        raiz = self.raiz(tests={"backend/tests/test_x.py": ["test_hdu099_esc01_x"]})

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(
            hechos(salida, "ERROR"),
            [f"backend/tests/test_x.py:{linea_py(0)} · test_hdu099_esc01_x nombra una historia que no existe (hdu099)"],
        )

    def test_tc52_salida_test_de_un_escenario_inexistente_es_error(self) -> None:
        """CA-8 esc. 3 · rechazo · `test_hdu002_esc99_…`: código 1 y «ERROR» con archivo:línea y el test."""
        raiz = self.raiz(tests={"backend/tests/test_y.py": nombres_hdu("HDU-002", 1) + ["test_hdu002_esc99_y"]})

        codigo, salida = self.correr(raiz)

        errores = hechos(salida, "ERROR")
        self.assertEqual(codigo, 1)
        self.assertEqual(len(errores), 1)
        self.assertTrue(
            errores[0].startswith(f"backend/tests/test_y.py:{linea_py(1)} · test_hdu002_esc99_y "), errores[0]
        )
        self.assertIn("escenario", errores[0])
        self.assertIn("no existe", errores[0])

    def test_tc52_salida_test_de_typescript_de_una_historia_inexistente_es_error(self) -> None:
        """CA-8 esc. 3 · rechazo · `it("hdu099_esc01 · …")` en un `.test.ts`: «ERROR» con su archivo:línea."""
        raiz = self.raiz(tests={"frontend/src/x.test.ts": [it_("hdu099_esc01 · x")]})

        codigo, salida = self.correr(raiz)

        errores = hechos(salida, "ERROR")
        self.assertEqual(codigo, 1)
        self.assertEqual(len(errores), 1)
        self.assertTrue(errores[0].startswith(f"frontend/src/x.test.ts:{linea_ts(0)} · hdu099_esc01 · x "), errores[0])
        self.assertIn("historia que no existe", errores[0])

    def test_tc53_salida_historia_que_sale_de_la_lista_es_error(self) -> None:
        """CA-8 esc. 4 · rechazo · HDU-003 está en la base del PR y no en la lista actual: código 1 y «ERROR».

        Mata el mutante «comparación con la base desactivada».
        """
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-001\n", tests={"backend/tests/test_alta.py": nombres_hdu("HDU-001", 1, 2, 3, 4, 5)})

        codigo, salida = self.correr(raiz, base="HDU-001\nHDU-003\n")

        self.assertEqual(codigo, 1)
        self.assertEqual(
            hechos(salida, "ERROR"),
            ["HDU-003 salió de tools/historias_activas.txt: una historia no sale nunca (ADR-012)"],
        )

    def test_tc53_salida_lista_igual_a_la_base_no_es_error(self) -> None:
        """CA-8 esc. 4 · la lista actual contiene todo lo de la base: sin «ERROR» y código 0."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\n")

        codigo, salida = self.correr(raiz, base="HDU-003\n")

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])

    def test_tc53_salida_historia_agregada_respecto_a_la_base_no_es_error(self) -> None:
        """CA-8 esc. 4 · agregar una historia a la lista no es una salida: sin «ERROR» y código 0."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\n")

        codigo, salida = self.correr(raiz, base=ACTIVAS_VACIAS)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])

    def test_tc53_salida_sin_base_no_compara(self) -> None:
        """CA-8 esc. 4 · sin `--activas-base` (el archivo no existía en la base del PR) no hay nada que comparar."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\n")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])

    def test_tc54_salida_fase_2_que_sale_de_la_lista_es_error(self) -> None:
        """CA-8 esc. 4 · rechazo · la línea «fase 2» está en la base y no en la lista actual: código 1 y «ERROR».

        Mata el mutante «comparación con la base desactivada».
        """
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\n")

        codigo, salida = self.correr(raiz, base="HDU-003\nfase 2\n")

        errores = hechos(salida, "ERROR")
        self.assertEqual(codigo, 1)
        self.assertEqual(len(errores), 1)
        self.assertIn("fase 2", errores[0])
        self.assertIn("tools/historias_activas.txt", errores[0])

    def test_tc54_salida_fase_2_presente_en_la_base_y_en_la_lista_no_es_error(self) -> None:
        """CA-8 esc. 4 · «fase 2» sigue en la lista y HDU-003 está cubierta: sin «ERROR» y código 0."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\nfase 2\n", tests={"backend/tests/test_c.py": nombres_hdu("HDU-003", 1, 2)})

        codigo, salida = self.correr(raiz, base="HDU-003\nfase 2\n")

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])

    # ----- Código 2 · entrada mal formada ----------------------------------------------------------------

    def test_tc55_salida_linea_invalida_en_la_lista_termina_en_2(self) -> None:
        """Códigos · rechazo · «HDU-1» en `historias_activas.txt`: código 2 y el mensaje nombra la línea."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-1\n")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("HDU-1", salida)

    def test_tc55_salida_historia_activa_inexistente_termina_en_2(self) -> None:
        """Códigos · rechazo · «HDU-099» en la lista, sin historia con ese número: código 2 y se nombra."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-099\n")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("HDU-099", salida)

    def test_tc55_salida_historia_sin_fila_en_la_tabla_termina_en_2(self) -> None:
        """Códigos · rechazo · una sección «## HDU-003 · …» sin fila en «El conjunto»: código 2 y se nombra."""
        raiz = self.raiz(historias_md=documento_historias().replace(FILA_HDU003 + "\n", ""))

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("HDU-003", salida)

    def test_tc55_salida_lista_de_activas_inexistente_termina_en_2(self) -> None:
        """Códigos · rechazo · sin `tools/historias_activas.txt` el verificador no adivina: código 2 (verificación de C3)."""
        raiz = self.raiz(activas=None)

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("historias_activas.txt", salida)


# ---------------------------------------------------------------------------------------------------------
# Fila C4 · el árbol real del repositorio
# ---------------------------------------------------------------------------------------------------------


class PruebasSobreElArbolReal(unittest.TestCase):
    """TC-56 (fila C4). A diferencia de las demás clases, no construye un árbol de ejemplo: ejecuta `main([])` sobre el
    repositorio, con `tools/historias_activas.txt` y `docs/04-historias-usuario.md` reales.

    Hoy ninguna historia está activa: todos los escenarios del documento quedan `PENDIENTE`, nada se exige y por eso el
    verificador no falla. Cuando la planificación de un sprint active una historia, estos números cambian y esta prueba
    se actualiza con ellos, en el mismo cambio. Mientras tanto, el pipeline corre el verificador sobre el árbol real
    sin romperse, y los tests de fundación (`test_tkt…_car…_esc…`) se cuentan sin cubrir ningún escenario ni ser error.
    """

    @classmethod
    def setUpClass(cls) -> None:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
            cls.codigo = ve.main([])
        cls.salida = salida.getvalue()

    def test_tc56_arbol_real_termina_en_0_sin_historias_activas(self) -> None:
        """TC-56 · CA-7 esc. 1 — sobre el árbol real el código es 0: no hay `FALTA` ni `ERROR`."""
        self.assertEqual(self.codigo, 0, self.salida)
        self.assertEqual(hechos(self.salida, "FALTA"), [], self.salida)
        self.assertEqual(hechos(self.salida, "ERROR"), [], self.salida)

    def test_tc56_arbol_real_resumen_con_todo_pendiente_y_nada_exigido(self) -> None:
        """TC-56 · CA-7 esc. 1 — el resumen cuenta todos los escenarios del documento como pendientes y no exige ninguno.

        El total sale de leer el documento real, no de un número fijo: añadir una historia no rompe la prueba.
        """
        documento = (ve.RAIZ_DEL_REPOSITORIO / "docs" / "04-historias-usuario.md").read_text(encoding="utf-8")
        total = sum(len(escenarios) for escenarios in ve.leer_historias(documento).values())
        self.assertGreater(total, 0, "el documento real debe tener escenarios")
        lineas = resumen(self.salida)
        literal = (
            f"Escenarios: {total} · exigidos 0 · cubiertos 0 · faltan 0 · pendientes {total} · retirados 0 · "
            "tests HDU 0 · tests de fundación "
        )
        # Todo es literal salvo el recuento de fundación, que crece con cada ticket.
        self.assertRegex(lineas, "^" + re.escape(literal) + r"\d+$", self.salida)

    def test_tc56_arbol_real_cuenta_los_tests_de_fundacion(self) -> None:
        """TC-56 · CA-7 esc. 1 — los tests de fundación del repositorio entran en el recuento, y ninguno es error ni cubre un escenario."""
        encontrado = re.search(r"tests de fundación (\d+)$", resumen(self.salida))
        if encontrado is None:
            self.fail(f"la salida no trae la línea de resumen:\n{self.salida}")
        contados = int(encontrado.group(1))
        reales = [t for t in ve.recolectar_tests(ve.RAIZ_DEL_REPOSITORIO) if ve.PATRON_FUNDACION.match(t.nombre)]
        self.assertGreater(len(reales), 0, "el repositorio ya tiene tests de fundación: el recuento no puede ser 0")
        self.assertEqual(contados, len(reales), self.salida)

    def test_tc56_arbol_real_cada_escenario_pendiente_se_lista_por_historia(self) -> None:
        """TC-56 · CA-7 esc. 1 — con ninguna historia activa, toda historia con escenarios sale como `PENDIENTE` y ninguna como `FALTA`."""
        pendientes = hechos(self.salida, "PENDIENTE")
        self.assertGreater(len(pendientes), 0, self.salida)
        self.assertTrue(all(linea.startswith("HDU-") for linea in pendientes), pendientes)
        self.assertEqual(hechos(self.salida, "FALTA"), [])


# ---------------------------------------------------------------------------------------------------------
# Mutación exploratoria · ramas que los mutantes de la tabla del diseño no alcanzan
# ---------------------------------------------------------------------------------------------------------

BLOQUE_DEPENDENCIAS = (
    "| De | A | Tipo | Nota |\n|---|---|---|---|\n"
    "| HDU-001 | HDU-002 | Bloquea | HDU-002 esc. 4 rechaza requisiciones sin línea base |\n"
    "| HDU-002 | HDU-003 | Continúa | La cuadrilla se da de alta después |\n"
)
CABECERA_DEL_CONJUNTO = "| # | Historia | Prioridad | Cap. | Complejidad | SP | Fase |"


class PruebasLecturaExploratoria(unittest.TestCase):
    """Cada prueba mata un mutante de `leer_historias` o `leer_activas` que sobrevivía a la suite original.

    El comentario de cada prueba nombra el mutante.
    """

    def test_tc40_leer_historias_una_tabla_con_columna_fase_fuera_de_el_conjunto_no_cuenta(self) -> None:
        """CA-6 · mutante «cualquier sección abre la búsqueda de la tabla»: una tabla con «Fase» en «Dependencias» no manda."""
        otra_tabla = "| # | Fase |\n|---|---|\n| HDU-001 | 2 |\n| HDU-002 | 2 |\n"
        documento = documento_historias().replace(BLOQUE_DEPENDENCIAS, otra_tabla)
        self.assertNotEqual(documento, documento_historias())

        historias = ve.leer_historias(documento)

        self.assertEqual({e.fase for e in historias["HDU-001"]}, {1})
        self.assertEqual({e.fase for e in historias["HDU-003"]}, {2})

    def test_tc40_leer_historias_una_segunda_tabla_dentro_de_el_conjunto_no_cuenta(self) -> None:
        """CA-6 · mutante «la tabla no se cierra»: tras la tabla principal, otra tabla de la misma sección se ignora."""
        segunda = "**Total: 27 SP · 12 escenarios.**\n\n| Historia | Cap. | Complejidad |\n|---|---|---|\n| HDU-001 | C1 | Alta |\n"
        documento = documento_historias().replace("**Total: 27 SP · 12 escenarios.**\n", segunda)
        self.assertNotEqual(documento, documento_historias())

        historias = ve.leer_historias(documento)

        self.assertEqual({e.fase for e in historias["HDU-001"]}, {1})

    def test_tc47_leer_historias_la_columna_fase_se_busca_por_su_cabecera(self) -> None:
        """CA-7 esc. 3 · mutante «la columna Fase es siempre la séptima»: con «Fase» en otra posición se lee igual."""
        filas = {
            FILA_HDU001: "| HDU-001 | 1 | Alta de obra |",
            FILA_HDU002: "| HDU-002 | 1+2 | Requisición con control de presupuesto |",
            FILA_HDU003: "| HDU-003 | 2 | Catálogo de cuadrillas |",
        }
        documento = documento_historias().replace(CABECERA_DEL_CONJUNTO, "| # | Fase | Historia |")
        for fila, nueva in filas.items():
            documento = documento.replace(fila, nueva)
        self.assertNotIn("Complejidad", documento)

        historias = ve.leer_historias(documento)

        self.assertEqual({e.fase for e in historias["HDU-001"]}, {1})
        self.assertEqual([e.fase for e in historias["HDU-002"]], [1, 1, 1, 1, 2])
        self.assertEqual({e.fase for e in historias["HDU-003"]}, {2})

    def test_tc55_leer_historias_la_tabla_sin_columna_fase_es_entrada_invalida(self) -> None:
        """Códigos · mutante «la primera tabla se lee aunque no tenga Fase»: sin la columna no hay fase que adivinar."""
        documento = documento_historias().replace(CABECERA_DEL_CONJUNTO, CABECERA_DEL_CONJUNTO.replace("Fase", "Etapa"))
        self.assertNotEqual(documento, documento_historias())

        with self.assertRaises(ve.EntradaInvalida) as contexto:
            ve.leer_historias(documento)

        self.assertIn("HDU-001", str(contexto.exception))

    def test_tc55_leer_historias_la_fila_sin_columna_fase_es_entrada_invalida(self) -> None:
        """Códigos · mutante «sin el raise de la fila corta»: una fila truncada es entrada mal formada, no un IndexError."""
        documento = documento_historias().replace(FILA_HDU003, "| HDU-003 | Catálogo de cuadrillas |")
        self.assertNotEqual(documento, documento_historias())

        with self.assertRaises(ve.EntradaInvalida) as contexto:
            ve.leer_historias(documento)

        self.assertIn("HDU-003", str(contexto.exception))

    def test_tc55_leer_historias_una_historia_con_dos_secciones_es_entrada_invalida(self) -> None:
        """Códigos · mutante «historia duplicada aceptada»: dos secciones «## HDU-001» pisarían los escenarios de la primera."""
        documento = documento_historias() + "\n## HDU-001 · Otra vez\n\n" + _escenario(1, "Un escenario repetido")

        with self.assertRaises(ve.EntradaInvalida) as contexto:
            ve.leer_historias(documento)

        self.assertIn("HDU-001", str(contexto.exception))

    def test_tc40_leer_historias_un_escenario_fuera_de_una_historia_no_se_atribuye(self) -> None:
        """CA-6 · mutantes «sin reinicio de la sección» y «sin ignorar lo anterior a la primera historia»."""
        documento = documento_historias().replace(
            "Preámbulo del documento.", "Preámbulo.\n\n**Escenario 7: ejemplo dentro del preámbulo**"
        )
        documento += "\n## Notas finales\n\n" + _escenario(9, "Un escenario que no es de HDU-003")

        historias = ve.leer_historias(documento)

        self.assertEqual([e.numero for e in historias["HDU-003"]], [1, 2])
        self.assertEqual(sum(len(e) for e in historias.values()), 12)

    def test_tc40_leer_historias_los_espacios_al_final_del_titulo_no_impiden_leerlo(self) -> None:
        """CA-6 · mutante «sin rstrip»: «**Escenario 1: …**» con espacios al final sigue siendo un escenario."""
        original = "**Escenario 1: Alta de obra con sus parámetros**"
        documento = documento_historias().replace(original, original + "   ")
        self.assertNotEqual(documento, documento_historias())

        escenario = ve.leer_historias(documento)["HDU-001"][0]

        self.assertEqual((escenario.numero, escenario.titulo), (1, "Alta de obra con sus parámetros"))

    def test_tc45_leer_historias_la_palabra_fase_2_dentro_de_un_segmento_no_marca_fase(self) -> None:
        """CA-7 esc. 2 · mutante «marca de fase por subcadena»: solo un segmento entero «fase 2» fija la fase 2."""
        documento = documento_historias().replace(
            "Código de obra duplicado", "Código duplicado detectado antes de la fase 2 de la obra"
        )
        self.assertNotEqual(documento, documento_historias())

        escenario = ve.leer_historias(documento)["HDU-001"][1]

        self.assertEqual(escenario.fase, 1)
        self.assertEqual(escenario.titulo, "Código duplicado detectado antes de la fase 2 de la obra")

    def test_tc48_leer_historias_un_segmento_que_solo_contiene_retirado_por_no_retira(self) -> None:
        """CA-7 esc. 5 · mutante «retiro por search»: el segmento debe ser exactamente «retirado por TKT-NNN»."""
        documento = documento_historias().replace(
            "Código de obra duplicado", "Código de obra duplicado · aún no retirado por TKT-069"
        )
        self.assertNotEqual(documento, documento_historias())

        escenario = ve.leer_historias(documento)["HDU-001"][1]

        self.assertIsNone(escenario.retirado_por)

    def test_tc48_leer_historias_el_titulo_no_conserva_las_marcas_de_fase_ni_de_retiro(self) -> None:
        """CA-7 esc. 4 · mutantes «conserva ` · fase N`» y «conserva ` · retirado por`»: el título sale limpio."""
        historias = ve.leer_historias(documento_historias("segmento"))

        self.assertEqual(
            historias["HDU-001"][3].titulo, "Mano de obra y avance simulados, y rotulados como tales"
        )
        self.assertEqual(historias["HDU-002"][4].titulo, "Intento de levantar una requisición sin conexión")

    def test_tc55_leer_activas_numero_de_historia_que_no_es_hdu_y_tres_cifras(self) -> None:
        """Códigos · mutante «match en lugar de fullmatch»: «HDU-0011» y «HDU-001x» no son «HDU-NNN»."""
        for linea in ("HDU-0011", "HDU-001x"):
            with self.subTest(linea=linea), self.assertRaises(ve.EntradaInvalida):
                ve.leer_activas(ACTIVAS_VACIAS + linea + "\n")

    def test_tc55_leer_activas_los_espacios_alrededor_de_la_linea_la_invalidan(self) -> None:
        """Códigos · mutante «línea con espacios aceptada»: el archivo se lee línea a línea y exacta (decisión a confirmar)."""
        for linea in ("HDU-001 ", " HDU-001", "fase 2 "):
            with self.subTest(linea=repr(linea)), self.assertRaises(ve.EntradaInvalida):
                ve.leer_activas(ACTIVAS_VACIAS + linea + "\n")

    def test_tc55_leer_activas_el_mensaje_nombra_el_numero_de_linea(self) -> None:
        """Códigos · mutante «sin número de línea»: tras tres comentarios, «texto suelto» es la línea 4."""
        with self.assertRaises(ve.EntradaInvalida) as contexto:
            ve.leer_activas(ACTIVAS_VACIAS + "texto suelto\n")

        self.assertIn("línea 4", str(contexto.exception))


class PruebasRecoleccionExploratoria(BaseConRaiz):
    """Mutantes de `recolectar_tests` que sobrevivían."""

    def test_tc43_recolectar_una_carpeta_con_nombre_de_test_no_se_lee_como_archivo(self) -> None:
        """CA-6 · mutante «sin is_file»: un directorio llamado `x.test.ts` no es un archivo de test."""
        raiz = self.raiz()
        (raiz / "frontend" / "src" / "carpeta.test.ts").mkdir(parents=True)

        self.assertEqual(ve.recolectar_tests(raiz), [])

    def test_tc43_recolectar_e2e_solo_lee_los_spec(self) -> None:
        """CA-6 · mutante «e2e lee *.ts»: bajo `frontend/e2e/` solo cuentan los `*.spec.ts`, no los auxiliares."""
        raiz = self.raiz(
            tests={
                "frontend/e2e/ayuda.ts": [it_("hdu002_esc01_oculto_en_un_auxiliar")],
                "frontend/e2e/flujo.spec.ts": [it_("hdu002_esc02_visible")],
            }
        )

        archivos = {t.archivo for t in ve.recolectar_tests(raiz)}

        self.assertEqual(archivos, {"frontend/e2e/flujo.spec.ts"})

    def test_tc43_recolectar_devuelve_los_tests_ordenados_por_archivo_y_linea(self) -> None:
        """CA-6 · mutantes «sin ordenar» y «orden inverso»: el orden no depende del que dé el sistema de archivos."""
        raiz = self.raiz(
            tests={
                "backend/tests/test_b.py": nombres_hdu("HDU-002", 1, 2),
                "backend/tests/test_a.py": nombres_hdu("HDU-002", 3, 4),
            }
        )
        recorrer = Path.rglob

        def al_reves(self_: Path, patron: str) -> Iterator[Path]:
            return iter(sorted(recorrer(self_, patron), reverse=True))

        with mock.patch.object(Path, "rglob", al_reves):
            encontrados = ve.recolectar_tests(raiz)

        self.assertEqual(
            [(t.archivo, t.linea) for t in encontrados],
            [
                ("backend/tests/test_a.py", linea_py(0)),
                ("backend/tests/test_a.py", linea_py(1)),
                ("backend/tests/test_b.py", linea_py(0)),
                ("backend/tests/test_b.py", linea_py(1)),
            ],
        )

    def test_tc43_recolectar_typescript_ignora_llamadas_de_un_objeto_o_con_prefijo(self) -> None:
        """CA-6 · mutante «sin el lookbehind»: `servidor.test("…")`, `pretest("…")` y `$it("…")` no son tests."""
        raiz = self.raiz(
            tests={
                "frontend/src/x.test.ts": [
                    'servidor.test("hdu002_esc01_de_un_objeto", () => {});',
                    'pretest("hdu002_esc02_con_prefijo", () => {});',
                    '$it("hdu002_esc03_con_dolar", () => {});',
                    it_("hdu002_esc04_el_unico"),
                ]
            }
        )

        nombres = [t.nombre for t in ve.recolectar_tests(raiz)]

        self.assertEqual(nombres, ["hdu002_esc04_el_unico"])

    def test_tc43_recolectar_typescript_lee_dos_llamadas_en_la_misma_linea(self) -> None:
        """CA-6 · mutante «solo la primera llamada de la línea»: `describe(…, () => { it(…) })` en una línea da dos nombres."""
        raiz = self.raiz(
            tests={
                "frontend/src/x.test.ts": [
                    'describe("hdu002_esc01_grupo", () => { it("hdu002_esc02_dentro", () => {}); });',
                ]
            }
        )

        nombres = [t.nombre for t in ve.recolectar_tests(raiz)]

        self.assertEqual(nombres, ["hdu002_esc01_grupo", "hdu002_esc02_dentro"])


class PruebasSalidaExploratoria(BaseConRaiz):
    """Mutantes de `clasificar`, `_informe` y `main` que sobrevivían."""

    def test_tc48_salida_un_retiro_en_una_historia_sin_ticket_se_lista_y_se_cuenta(self) -> None:
        """CA-7 esc. 4 · mutante «RETIRADO solo en historia activa»: TKT-069 retira con HDU-001 aún sin ticket."""
        raiz = self.raiz(retiro="segmento")

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertCountEqual(
            hechos(salida, "RETIRADO"), ["HDU-001 esc. 4 · TKT-069", "HDU-001 esc. 5 · TKT-069"]
        )
        self.assertIn("HDU-001 · 3 escenarios · historia sin ticket en curso", hechos(salida, "PENDIENTE"))
        self.assertEqual(resumen(salida), resumen_esperado(12, 0, 0, 0, 10, 2, 0, 0))

    def test_tc44_salida_un_test_de_una_historia_inactiva_no_la_exige_ni_la_cubre(self) -> None:
        """CA-7 esc. 1 · mutante «un escenario con test se exige aunque su historia no esté activa»."""
        raiz = self.raiz(tests={"backend/tests/test_alta.py": nombres_hdu("HDU-001", 1)})

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 0)
        self.assertEqual(resumen(salida), resumen_esperado(12, 0, 0, 0, 12, 0, 1, 0))

    def test_tc53_salida_ocho_historias_que_salen_de_la_lista_se_informan_en_orden(self) -> None:
        """CA-8 esc. 4 · mutante «sin ordenar»: ocho historias fuera de la lista, ocho errores, de menor a mayor.

        Un conjunto de ocho cadenas casi nunca sale ordenado por azar (1 entre 40 320), así que el mutante cae siempre.
        """
        raiz = self.raiz()
        nombres = [f"HDU-{n:03d}" for n in range(1, 9)]

        codigo, salida = self.correr(raiz, base="\n".join(reversed(nombres)) + "\n")

        self.assertEqual(codigo, 1)
        self.assertEqual([e.split(" ")[0] for e in hechos(salida, "ERROR")], nombres)

    def test_tc54_salida_fase_2_agregada_respecto_a_la_base_no_es_error(self) -> None:
        """CA-8 esc. 4 · mutante «fase 2 distinta de la base es error»: iniciar la fase 2 no es una salida."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-003\nfase 2\n", tests={"backend/tests/test_c.py": nombres_hdu("HDU-003", 1, 2)}
        )

        codigo, salida = self.correr(raiz, base="HDU-003\n")

        self.assertEqual(codigo, 0)
        self.assertEqual(hechos(salida, "ERROR"), [])

    def test_tc52_salida_los_errores_de_tests_salen_en_orden_de_archivo_y_linea(self) -> None:
        """CA-8 esc. 3 · mutante «hechos invertidos»: dos tests inexistentes se informan en el orden del código."""
        raiz = self.raiz(
            tests={"backend/tests/test_x.py": ["test_hdu098_esc01_primero", "test_hdu099_esc01_segundo"]}
        )

        _, salida = self.correr(raiz)

        errores = hechos(salida, "ERROR")
        self.assertEqual(len(errores), 2)
        self.assertIn("test_hdu098_esc01_primero", errores[0])
        self.assertIn("test_hdu099_esc01_segundo", errores[1])

    def test_tc55_salida_la_entrada_mal_formada_va_a_stderr_con_su_prefijo(self) -> None:
        """Códigos · mutantes «a stdout» y «sin prefijo»: el diagnóstico del código 2 sale por stderr y dice qué es."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-1\n")

        codigo, salida, error = self.correr_separado(raiz)

        self.assertEqual(codigo, 2)
        self.assertEqual(salida, "")
        self.assertTrue(error.startswith("entrada mal formada: "), error)
        self.assertIn("HDU-1", error)

    def test_tc55_salida_sin_documento_de_historias_termina_en_2(self) -> None:
        """Códigos · rechazo · mutante «sin comprobar el documento»: sin `docs/04-historias-usuario.md` el código es 2."""
        raiz = self.raiz()
        (raiz / "docs" / "04-historias-usuario.md").unlink()

        codigo, salida, error = self.correr_separado(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("04-historias-usuario.md", error)

    def test_tc55_salida_un_archivo_que_no_es_utf8_termina_en_2(self) -> None:
        """Códigos · rechazo · mutante «UnicodeDecodeError sin atrapar»: Latin-1 en la lista es entrada mal formada."""
        raiz = self.raiz()
        (raiz / "tools" / "historias_activas.txt").write_bytes("# caf\xe9\n".encode("latin-1"))

        codigo, salida, error = self.correr_separado(raiz)

        self.assertEqual(codigo, 2)
        self.assertIn("UTF-8", error)

    def test_tc55_salida_un_archivo_de_test_que_no_es_utf8_termina_en_2(self) -> None:
        """Códigos · rechazo · F001: un `test_x.py` en Latin-1 es entrada mal formada y el error nombra su ruta relativa."""
        raiz = self.raiz()
        archivo = raiz / "backend" / "tests" / "sub" / "test_x.py"
        archivo.parent.mkdir(parents=True)
        archivo.write_bytes("# caf\xe9\ndef test_hdu002_esc01_x(self):\n    pass\n".encode("latin-1"))

        codigo, salida, error = self.correr_separado(raiz)

        self.assertEqual(codigo, 2, error)
        self.assertEqual(salida, "")
        self.assertTrue(error.startswith("entrada mal formada: "), error)
        self.assertIn("UTF-8", error)
        self.assertIn("backend/tests/sub/test_x.py", error)

    def test_tc55_salida_un_archivo_de_test_de_typescript_que_no_es_utf8_termina_en_2(self) -> None:
        """Códigos · rechazo · F001: un `.test.ts` en Latin-1 también es entrada mal formada, con su ruta relativa."""
        raiz = self.raiz()
        archivo = raiz / "frontend" / "src" / "sub" / "a.test.ts"
        archivo.parent.mkdir(parents=True)
        archivo.write_bytes('// caf\xe9\nit("hdu002_esc01_x", () => {});\n'.encode("latin-1"))

        codigo, salida, error = self.correr_separado(raiz)

        self.assertEqual(codigo, 2, error)
        self.assertEqual(salida, "")
        self.assertTrue(error.startswith("entrada mal formada: "), error)
        self.assertIn("UTF-8", error)
        self.assertIn("frontend/src/sub/a.test.ts", error)

    def test_tc43_salida_un_test_comentado_de_typescript_no_cubre_el_escenario(self) -> None:
        """CA-6 esc. 2 · rechazo · F002: `// it("hdu002_esc04 · …")` y un bloque `/* … */` no cubren; el esc. 4 sigue `FALTA`."""
        raiz = self.raiz(
            activas=ACTIVAS_VACIAS + "HDU-002\n",
            tests={
                "backend/tests/test_req.py": nombres_hdu("HDU-002", 1, 2, 3),
                "frontend/src/req.test.ts": [
                    '// it("hdu002_esc04 · La requisición excede el importe", () => {});',
                    '/*\n * test("hdu002_esc04 · en un bloque", () => {});\n */',
                ],
            },
        )

        codigo, salida = self.correr(raiz)

        self.assertEqual(codigo, 1)
        self.assertEqual(hechos(salida, "FALTA"), ["HDU-002 esc. 4 · La requisición excede el importe presupuestado"])
        self.assertEqual(resumen(salida), resumen_esperado(12, 4, 3, 1, 8, 0, 3, 0))

    def test_tc53_salida_una_base_inexistente_no_se_compara(self) -> None:
        """CA-8 esc. 4 · mutante «la base se lee aunque no exista»: la ruta dada no existe, como en un PR sin el archivo."""
        raiz = self.raiz(activas=ACTIVAS_VACIAS + "HDU-003\n")

        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = ve.main(["--raiz", str(raiz), "--activas-base", str(self.directorio / "no_existe.txt")])

        self.assertEqual(codigo, 0, error.getvalue())
        self.assertEqual(hechos(salida.getvalue(), "ERROR"), [])

    def test_tc55_salida_una_base_mal_formada_termina_en_2_y_nombra_la_base(self) -> None:
        """Códigos · rechazo · mutante «sin contexto de la base»: el error dice que viene del PR base, no de la lista actual."""
        raiz = self.raiz()

        codigo, _, error = self.correr_separado(raiz, base="texto suelto\n")

        self.assertEqual(codigo, 2)
        self.assertIn("base del PR", error)

    def test_tc56_salida_sin_raiz_usa_la_del_repositorio_aunque_el_directorio_actual_sea_otro(self) -> None:
        """CA-7 esc. 1 · mutante «--raiz por defecto = directorio actual»: se resuelve desde la ubicación del script."""
        anterior = os.getcwd()
        self.addCleanup(os.chdir, anterior)
        os.chdir(self.directorio)
        salida, error = io.StringIO(), io.StringIO()

        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = ve.main([])

        self.assertNotEqual(codigo, 2, error.getvalue())
        self.assertNotIn("entrada mal formada", error.getvalue())

    def test_tc56_salida_como_script_escribe_utf8_aunque_la_consola_use_otra_codificacion(self) -> None:
        """CA-7 esc. 1 · mutante «sin reconfigurar la salida»: con `cp1252` el «·» del resumen debe salir en UTF-8."""
        raiz = self.raiz()
        entorno = dict(os.environ, PYTHONIOENCODING="cp1252")

        proceso = subprocess.run(
            [sys.executable, ve.__file__, "--raiz", str(raiz)],
            capture_output=True,
            env=entorno,
            check=False,
        )

        self.assertEqual(proceso.returncode, 0, proceso.stderr.decode("utf-8", "replace"))
        self.assertIn("Escenarios: 12 · exigidos 0".encode(), proceso.stdout)


if __name__ == "__main__":
    unittest.main()
