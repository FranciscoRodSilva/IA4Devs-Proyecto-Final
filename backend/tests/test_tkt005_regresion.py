"""Regresión del contrato de error (TKT-005, fila 8): TC-100, TC-101, TC-102, TC-105 y TC-106.

Sin Docker (CA-R4): ninguna prueba de este archivo pide una fixture que abra la base. Los casos
prueban comandos con subprocesos (`sys.executable`, `encoding="utf-8"`, `timeout`), como TKT-004.

Casi todos nacen en verde porque la garantía ya se cumple: lo que demuestra que dependen de algo
son los mutantes de `impl.md` (un paquete añadido sin regenerar `uv.lock`, un archivo con un
`import` sin usar, sin formato, con un tipo mal puesto y un `float` en una firma de dominio, un
`serializar()` que redondea, un archivo con BOM o con CRLF).

Fuera de este archivo, y por eso sin test:

- TC-103 (`uv run pytest` completo con Docker): un test que lanza la suite completa se llamaría a
  sí mismo. Es un comando de cierre y su salida va en `impl.md`.
- TC-90 y el resto de TC-105 (`verificar_docs.py`, `extraer_mermaid.py`, `unittest` de `tools/`):
  dependen de textos y archivos que llegan con la fila 9 y con `/sdd-completar` (`impl.md`,
  `delta.md`, retirada de las marcas «desde TKT-005»). Un test en la suite que falla hasta
  entonces dejaría rojo el cierre del ticket; esos comandos tienen su propio paso en el pipeline.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

import pytest

BACKEND = Path(__file__).resolve().parents[1]
RAIZ = BACKEND.parent
TESTS = BACKEND / "tests"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
BOM = b"\xef\xbb\xbf"
DEPENDENCIAS_DE_EJECUCION = {"fastapi", "pydantic", "structlog"}
DEPENDENCIAS_DE_DESARROLLO = {"jsonschema", "pyyaml"}


class Corrida(NamedTuple):
    codigo: int
    salida: str


def correr(argumentos: list[str], cwd: Path, plazo: int = 120) -> Corrida:
    proceso = subprocess.run(
        argumentos,
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=plazo,
        check=False,
    )
    return Corrida(proceso.returncode, proceso.stdout + proceso.stderr)


def uv() -> str:
    ejecutable = shutil.which("uv")
    assert ejecutable, "uv no está en el PATH: la instalación reproducible no se puede comprobar"
    return ejecutable


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def nombres_bloqueados() -> set[str]:
    bloqueo = tomllib.loads((BACKEND / "uv.lock").read_text(encoding="utf-8"))
    return {paquete["name"] for paquete in bloqueo["package"]}


@pytest.fixture
def copia_del_bloqueo(tmp_path: Path) -> Path:
    """`pyproject.toml` y `uv.lock` en una carpeta aparte: lo único que `uv lock --check` necesita."""
    destino = tmp_path / "copia"
    destino.mkdir()
    for nombre in ("pyproject.toml", "uv.lock"):
        shutil.copy(BACKEND / nombre, destino / nombre)
    return destino


def comprobar_bloqueo(carpeta: Path) -> Corrida:
    return correr([uv(), "lock", "--check", "--python", sys.executable], carpeta)


def test_tkt005_car1_lock_desactualizado_falla(copia_del_bloqueo: Path) -> None:
    """TC-100 · CA-R1 esc. 2 — un paquete añadido a pyproject.toml sin regenerar uv.lock hace fallar la comprobación."""
    # Control (anti-verde vacío): la copia tal cual está al día. Sin esto, cualquier fallo de uv
    # (sin red, sin intérprete) pasaría por un rechazo.
    control = comprobar_bloqueo(copia_del_bloqueo)
    assert control.codigo == 0, control.salida

    proyecto = copia_del_bloqueo / "pyproject.toml"
    original = proyecto.read_text(encoding="utf-8")
    modificado = original.replace("dependencies = [\n", 'dependencies = [\n    "idna>=3.0",\n', 1)
    assert modificado != original
    proyecto.write_text(modificado, encoding="utf-8", newline="\n")

    corrida = comprobar_bloqueo(copia_del_bloqueo)

    assert corrida.codigo != 0, corrida.salida
    assert "needs to be updated" in corrida.salida, corrida.salida


def test_tkt005_car1_sync_locked_no_cambia_el_lock() -> None:
    """TC-100, TC-101 · CA-R1 esc. 1 — `uv sync --locked` termina con código 0 y deja uv.lock byte a byte igual."""
    antes = huella(BACKEND / "uv.lock")

    corrida = correr([uv(), "sync", "--locked"], BACKEND)

    assert corrida.codigo == 0, corrida.salida
    assert huella(BACKEND / "uv.lock") == antes


def test_tkt005_car1_el_lock_incluye_las_dependencias_nuevas() -> None:
    """TC-101 · CA-R1 esc. 1 — FastAPI, Pydantic y structlog (y las de prueba) están declaradas y bloqueadas."""
    proyecto = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    declaradas = {
        re.split(r"[\[<>=!~ ]", dependencia, maxsplit=1)[0].lower()
        for dependencia in proyecto["project"]["dependencies"]
    }
    de_desarrollo = {
        re.split(r"[\[<>=!~ ]", dependencia, maxsplit=1)[0].lower()
        for dependencia in proyecto["dependency-groups"]["dev"]
    }
    bloqueados = nombres_bloqueados()

    assert declaradas >= DEPENDENCIAS_DE_EJECUCION
    assert de_desarrollo >= DEPENDENCIAS_DE_DESARROLLO
    assert bloqueados >= (DEPENDENCIAS_DE_EJECUCION | DEPENDENCIAS_DE_DESARROLLO)


COMANDOS_DE_CALIDAD = {
    "ruff_check": ([sys.executable, "-m", "ruff", "check", "."], "All checks passed!"),
    "ruff_format": ([sys.executable, "-m", "ruff", "format", "--check", "."], "already formatted"),
    "mypy": ([sys.executable, "-m", "mypy", "."], "Success: no issues found"),
    "verificar_float": (
        [sys.executable, "-m", "herramientas.verificar_float"],
        "hallazgos: 0",
    ),
}


@pytest.mark.parametrize("comando", sorted(COMANDOS_DE_CALIDAD))
def test_tkt005_car2_calidad_estatica_sin_hallazgos(comando: str) -> None:
    """TC-102 · CA-R2 esc. 1 — Ruff, mypy y verificar_float terminan en verde sobre backend/."""
    argumentos, esperado = COMANDOS_DE_CALIDAD[comando]

    corrida = correr(argumentos, BACKEND, plazo=300)

    assert corrida.codigo == 0, corrida.salida
    assert esperado in corrida.salida, corrida.salida


def test_tkt005_car7_serializar_sigue_rechazando_lo_sin_cuantizar() -> None:
    """TC-106 · CA-R7 — los tests de serializar() de TKT-004 (escenario ca06) siguen en verde y no son un conjunto vacío."""
    corrida = correr(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_tipos_base_redondeo.py",
            "-k",
            "ca06",
            "-v",
            "-p",
            "no:cacheprovider",
        ],
        BACKEND,
    )

    assert corrida.codigo == 0, corrida.salida
    # El que rechaza un valor con más decimales que su escala tiene que haber corrido y pasado.
    assert "test_tkt004_ca06_mas_decimales_que_la_escala PASSED" in corrida.salida, corrida.salida
    assert "test_tkt004_ca06_no_serializa_lo_que_no_cabe PASSED" in corrida.salida, corrida.salida


def archivos_nuevos_del_ticket() -> list[Path]:
    """Código y pruebas que añade el ticket, más sus artefactos de especificación."""
    encontrados = {
        *(BACKEND / "contrato_error").glob("*.py"),
        *(BACKEND / "servidor").glob("*.py"),
        *TESTS.glob("test_contrato_error_*.py"),
        *TESTS.glob("test_servidor_*.py"),
        *TESTS.glob("test_tkt005_*.py"),
        *(RAIZ / "sdd" / "tickets" / "tkt-005").glob("*.md"),
    }
    return sorted(encontrados)


def test_tkt005_car6_archivos_nuevos_sin_bom_ni_crlf() -> None:
    """TC-105 · CA-R6 esc. 2 — ningún archivo nuevo del ticket empieza con BOM ni lleva finales de línea CRLF."""
    archivos = archivos_nuevos_del_ticket()
    nombres = {a.name for a in archivos}
    # Anti-verde vacío: el recorrido ve de verdad el código y las pruebas del ticket.
    assert {"excepciones.py", "fabrica.py", "test_tkt005_regresion.py", "spec.md"} <= nombres

    con_bom = [a.relative_to(RAIZ).as_posix() for a in archivos if a.read_bytes()[:3] == BOM]
    con_crlf = [a.relative_to(RAIZ).as_posix() for a in archivos if b"\r\n" in a.read_bytes()]

    assert con_bom == []
    assert con_crlf == []
