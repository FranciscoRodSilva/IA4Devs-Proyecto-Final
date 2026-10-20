"""La regla 1 de CLAUDE.md contra `float` (TKT-004, fila 4): TC-70 a TC-78 y TC-81 a TC-83.

Los casos de BOM se numeraron antes como los de mypy (CA-11, `test_tipos_base_mypy.py`) y pasaron
a TC-82 y TC-83 para que ningún identificador de TKT-004 se repita.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-13). Las violaciones se generan en `tmp_path`, nunca en el árbol que revisa
`herramientas.verificar_float`: si vivieran allí, la propia comprobación fallaría siempre.
El módulo se importa dentro de cada prueba, no al cargar el archivo, para que cada escenario
falle por su cuenta mientras la herramienta no exista.

`Decimal(0.1)` no lo marca el verificador sino `RUF032` de Ruff (TC-78). Un alias como
`Tasa = float` usado como anotación no se detecta: es un hueco declarado (PA-T14) y no tiene
test, porque una prueba de un comportamiento que no existe sería falsa.
"""

import contextlib
import importlib
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
DOMINIO_DEMO = "cimenta/demo/dominio/reglas.py"


def escribir(tmp_path: Path, ruta_relativa: str, codigo: str) -> Path:
    """Crea el archivo con sus directorios, en UTF-8 y con saltos de línea `\\n`."""
    ruta = tmp_path / ruta_relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(codigo, encoding="utf-8", newline="\n")
    return ruta


def lineas(*texto: str) -> str:
    """Une las líneas con `\\n`: así el número de línea de cada caso se lee a simple vista."""
    return "\n".join(texto) + "\n"


def ejecutar_verificador(raiz: Path) -> int:
    """Llama a `verificar_float.main` en proceso; la salida se lee con `capsys`."""
    modulo = importlib.import_module("herramientas.verificar_float")
    codigo: int = modulo.main(["--raiz", str(raiz)])
    return codigo


def hallazgos_de(salida: str, ruta_relativa: str) -> list[tuple[int, str]]:
    """Pares (línea, descripción) de las líneas de salida que citan `ruta_relativa:línea:`."""
    patron = re.compile(rf"{re.escape(ruta_relativa)}:(\d+):(.*)")
    return [(int(m.group(1)), m.group(2)) for ln in salida.splitlines() if (m := patron.search(ln))]


def correr(argumentos: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argumentos,
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def test_tkt004_ca09_dominio_sin_float_pasa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-70 · CA-9 esc. 1 · regla 1 — un dominio anotado con los tipos base termina con 0."""
    escribir(
        tmp_path,
        DOMINIO_DEMO,
        lineas(
            "from dataclasses import dataclass",
            "",
            "from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento",
            "",
            "",
            "@dataclass(frozen=True)",
            "class Partida:",
            "    importe: Dinero",
            "",
            "",
            "def disponible(presupuestado: Dinero, consumido: Dinero) -> Dinero:",
            "    return presupuestado",
            "",
            "",
            "def volumen(cantidad: Cantidad, rendimiento: Rendimiento) -> Cantidad:",
            "    return cantidad",
            "",
            "",
            "def avance(medido: Cantidad, alcance: Cantidad) -> Porcentaje | None:",
            "    return None",
        ),
    )

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "archivos revisados: 1; hallazgos: 0" in salida


def test_tkt004_ca09_float_en_parametro_y_retorno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-71 · CA-9 esc. 2 · regla 1 — un float en un parámetro y en el retorno se cita con línea."""
    escribir(
        tmp_path,
        DOMINIO_DEMO,
        lineas(
            '"""Reglas de prueba."""',
            "",
            "def disponible(presupuestado: float) -> float:",
            "    return presupuestado",
        ),
    )

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    hallazgos = hallazgos_de(salida, DOMINIO_DEMO)
    assert codigo == 1
    assert len(hallazgos) == 2, salida
    assert {linea for linea, _ in hallazgos} == {3}
    assert any("el parámetro presupuestado de disponible" in donde for _, donde in hallazgos)
    assert any("el retorno de disponible" in donde for _, donde in hallazgos)
    assert "hallazgos: 2" in salida


@pytest.mark.parametrize("con_futuro", [False, True], ids=["sin_futuro", "con_futuro"])
@pytest.mark.parametrize(
    ("anotacion", "importa"),
    [
        ("float | None", None),
        ("Optional[float]", "from typing import Optional"),
        ("list[float]", None),
        ("dict[str, float]", None),
        ("'float'", None),
    ],
    ids=["union", "optional", "lista", "diccionario", "cadena"],
)
def test_tkt004_ca09_float_compuesto_o_en_cadena(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    anotacion: str,
    importa: str | None,
    con_futuro: bool,
) -> None:
    """TC-72 · CA-9 esc. 3 · regla 1 — el float escondido en una anotación compuesta se marca."""
    cuerpo: list[str] = []
    if con_futuro:
        cuerpo.append("from __future__ import annotations")
    if importa is not None:
        cuerpo.append(importa)
    cuerpo.append("")
    cuerpo.append(f"def f(x: {anotacion}) -> None:")
    linea_esperada = len(cuerpo)
    cuerpo.append("    return None")
    escribir(tmp_path, DOMINIO_DEMO, lineas(*cuerpo))

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    hallazgos = hallazgos_de(salida, DOMINIO_DEMO)
    assert codigo == 1
    assert [linea for linea, _ in hallazgos] == [linea_esperada], salida
    assert "el parámetro x de f" in hallazgos[0][1]


def test_tkt004_ca09_float_en_campo_de_dataclass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-73 · CA-9 esc. 4 · regla 1 — `tasa: float` en una dataclass se marca por su campo."""
    escribir(
        tmp_path,
        DOMINIO_DEMO,
        lineas(
            "from dataclasses import dataclass",
            "",
            "@dataclass",
            "class Interes:",
            "    tasa: float",
        ),
    )

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    hallazgos = hallazgos_de(salida, DOMINIO_DEMO)
    assert codigo == 1
    assert len(hallazgos) == 1, salida
    assert hallazgos[0][0] == 5
    assert "la anotación de tasa" in hallazgos[0][1]


def test_tkt004_ca09_cubre_tipos_base(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-74 · CA-9 esc. 6 · regla 1 — la regla alcanza también al paquete de tipos base."""
    escribir(tmp_path, "tipos_base/x.py", lineas("def f(x: float) -> None:", "    return None"))

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    hallazgos = hallazgos_de(salida, "tipos_base/x.py")
    assert codigo == 1
    assert [linea for linea, _ in hallazgos] == [1], salida


def test_tkt004_ca09_no_revisa_api_ni_infraestructura(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-75 · CA-9 esc. 7 · regla 1 — un float en api/ o infraestructura/ queda fuera del alcance."""
    con_float = lineas("def f(x: float) -> float:", "    return x")
    escribir(tmp_path, "cimenta/demo/api/rutas.py", con_float)
    escribir(tmp_path, "cimenta/demo/infraestructura/repo.py", con_float)
    escribir(tmp_path, DOMINIO_DEMO, lineas("def g(x: int) -> int:", "    return x"))

    codigo = ejecutar_verificador(tmp_path)

    salida = capsys.readouterr().out
    assert codigo == 0, salida
    assert "archivos revisados: 1; hallazgos: 0" in salida
    assert "rutas.py" not in salida
    assert "repo.py" not in salida


def test_tkt004_ca09_sin_archivos_no_da_verde(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-76 · CA-9 · regla 1 — sin nada que revisar termina con 2 y lo dice por stderr."""
    codigo = ejecutar_verificador(tmp_path)

    capturado = capsys.readouterr()
    assert codigo == 2
    assert "ningún archivo que revisar" in capturado.err


def test_tkt004_ca09_comando_documentado_sobre_el_arbol_real() -> None:
    """TC-77 · CA-9 esc. 1 · regla 1 — el comando documentado pasa sobre el código real."""
    proceso = correr([sys.executable, "-m", "herramientas.verificar_float"], cwd=BACKEND)

    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    resumen = re.search(r"archivos revisados: (\d+); hallazgos: 0", proceso.stdout)
    assert resumen is not None, proceso.stdout
    # Diez dominio/__init__.py y los dos archivos de tipos_base.
    assert int(resumen.group(1)) >= 12


def test_tkt004_ca09_decimal_desde_literal_float(tmp_path: Path) -> None:
    """TC-78 · CA-9 esc. 5 · regla 1 — RUF032 marca `Decimal(0.1)` y no `Decimal("0.1")`."""
    shutil.copy(BACKEND / "pyproject.toml", tmp_path / "pyproject.toml")
    escribir(
        tmp_path,
        DOMINIO_DEMO,
        lineas(
            "from decimal import Decimal",
            "",
            "X = Decimal(0.1)",
            'Y = Decimal("0.1")',
        ),
    )

    proceso = correr(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "concise", "."],
        cwd=tmp_path,
    )

    salida = proceso.stdout + proceso.stderr
    # Ruff imprime la ruta con el separador del sistema: se acepta `/` y `\`.
    marcas = {
        (int(m.group(1)), m.group(2)) for m in re.finditer(r"reglas\.py:(\d+):\d+: (\w+)", salida)
    }
    assert (3, "RUF032") in marcas, salida
    assert (4, "RUF032") not in marcas, salida


def _ejecutar_como_comando(raiz: Path) -> subprocess.CompletedProcess[str]:
    return correr(
        [sys.executable, "-m", "herramientas.verificar_float", "--raiz", str(raiz)], cwd=BACKEND
    )


def _escribir_con_bom(tmp_path: Path, ruta_relativa: str, codigo: str) -> Path:
    """Escribe el archivo como lo guardan algunos editores de Windows: UTF-8 con BOM."""
    ruta = tmp_path / ruta_relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"\xef\xbb\xbf" + codigo.encode("utf-8"))
    return ruta


def test_tkt004_ca09_archivo_con_bom_sin_float_pasa(tmp_path: Path) -> None:
    """TC-82 · CA-9 · regla 1 — un archivo UTF-8 con BOM se analiza: sin traceback y con 0."""
    _escribir_con_bom(
        tmp_path,
        DOMINIO_DEMO,
        lineas("from tipos_base import Dinero", "", "def f(x: Dinero) -> Dinero:", "    return x"),
    )

    proceso = _ejecutar_como_comando(tmp_path)

    assert "Traceback" not in proceso.stderr, proceso.stderr
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    assert "archivos revisados: 1; hallazgos: 0" in proceso.stdout


def test_tkt004_ca09_archivo_con_bom_y_float_se_marca_en_su_linea(tmp_path: Path) -> None:
    """TC-83 · CA-9 · regla 1 — con BOM el float se encuentra igual y en la misma línea que sin él."""
    _escribir_con_bom(
        tmp_path,
        DOMINIO_DEMO,
        lineas('"""Reglas de prueba."""', "", "def f(x: float) -> None:", "    return None"),
    )

    proceso = _ejecutar_como_comando(tmp_path)

    assert "Traceback" not in proceso.stderr, proceso.stderr
    assert proceso.returncode == 1, proceso.stdout + proceso.stderr
    assert [linea for linea, _ in hallazgos_de(proceso.stdout, DOMINIO_DEMO)] == [3], proceso.stdout


def test_tkt004_ca09_error_de_sintaxis_falla_con_ruta_y_linea_sin_traceback(tmp_path: Path) -> None:
    """TC-81 · CA-9 · regla 1 — un archivo que no se puede analizar da 1, cita ruta y línea y no vuelca traceback."""
    escribir(tmp_path, DOMINIO_DEMO, lineas("x = 1", "y = 2", "def f(:", "    return None"))

    proceso = _ejecutar_como_comando(tmp_path)

    salida = proceso.stdout + proceso.stderr
    assert "Traceback" not in salida, salida
    assert proceso.returncode == 1, salida
    assert re.search(rf"{re.escape(DOMINIO_DEMO)}:3\b", salida), salida


def test_tkt004_ca09_directorio_con_nombre_de_modulo_da_hallazgo_sin_traceback(
    tmp_path: Path,
) -> None:
    """TC-81b · CA-9 · regla 1 — un directorio `x.py` bajo dominio/ no se puede leer: hallazgo en la línea 1 y código 1."""
    (tmp_path / "cimenta" / "demo" / "dominio" / "x.py").mkdir(parents=True)

    proceso = _ejecutar_como_comando(tmp_path)

    salida = proceso.stdout + proceso.stderr
    assert "Traceback" not in salida, salida
    assert proceso.returncode == 1, salida
    hallazgos = hallazgos_de(proceso.stdout, "cimenta/demo/dominio/x.py")
    assert [linea for linea, _ in hallazgos] == [1], salida
    assert "hallazgos: 1" in proceso.stdout, salida


@contextlib.contextmanager
def _bloquear_lectura(ruta: Path) -> Iterator[None]:
    """Hace ilegible `ruta` mientras dura el bloque, sin privilegios; cede si la plataforma no lo permite."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        crear = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        crear.restype = wintypes.HANDLE
        crear.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        generico_lectura, sin_compartir, abrir_existente = 0x80000000, 0, 3
        asa = crear(str(ruta), generico_lectura, sin_compartir, None, abrir_existente, 0, None)
        if asa in (None, wintypes.HANDLE(-1).value):
            pytest.skip("no se pudo bloquear el archivo con acceso exclusivo")
        try:
            yield
        finally:
            ctypes.WinDLL("kernel32").CloseHandle(wintypes.HANDLE(asa))
    else:
        ruta.chmod(0o000)
        if os.access(ruta, os.R_OK):
            ruta.chmod(0o600)
            pytest.skip("el proceso lee archivos sin permiso (¿root?)")
        try:
            yield
        finally:
            ruta.chmod(0o600)


def test_tkt004_ca09_archivo_ilegible_da_hallazgo_sin_traceback(tmp_path: Path) -> None:
    """TC-81c · CA-9 · regla 1 — un archivo del dominio al que se le niega la lectura: hallazgo en la línea 1 y código 1."""
    ruta = escribir(tmp_path, DOMINIO_DEMO, lineas("def f(x: int) -> int:", "    return x"))

    with _bloquear_lectura(ruta):
        proceso = _ejecutar_como_comando(tmp_path)

    salida = proceso.stdout + proceso.stderr
    assert "Traceback" not in salida, salida
    assert proceso.returncode == 1, salida
    assert [linea for linea, _ in hallazgos_de(proceso.stdout, DOMINIO_DEMO)] == [1], salida
