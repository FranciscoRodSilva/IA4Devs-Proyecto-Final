"""El paquete `tipos_base` bajo mypy estricto (TKT-004, fila 4): TC-79 y TC-80.

Sin Docker (CA-13). Cada prueba copia `pyproject.toml` y `tipos_base/` a `tmp_path` y corre
mypy allí: la violación nunca se escribe en el paquete real, y la configuración que se prueba es
la del repositorio, con su `override` estricto. El caché de mypy se comparte entre pruebas en un
directorio de sesión para no pagar el arranque en frío dos veces.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".import_linter_cache")


@pytest.fixture(scope="session")
def cache_mypy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("cache_mypy")


def copiar_paquete(destino: Path) -> Path:
    """Copia la configuración del repositorio y `tipos_base/` y devuelve la copia del paquete."""
    shutil.copy(BACKEND / "pyproject.toml", destino / "pyproject.toml")
    return Path(shutil.copytree(BACKEND / "tipos_base", destino / "tipos_base", ignore=IGNORAR))


def correr_mypy(cwd: Path, cache: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", "tipos_base", "--cache-dir", str(cache)],
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def test_tkt004_ca11_tipos_base_pasa_mypy_estricto(tmp_path: Path, cache_mypy: Path) -> None:
    """TC-79 · CA-11 esc. 1 — el paquete de tipos base pasa mypy con las opciones estrictas."""
    copiar_paquete(tmp_path)

    proceso = correr_mypy(tmp_path, cache_mypy)

    salida = proceso.stdout + proceso.stderr
    assert proceso.returncode == 0, salida
    assert re.search(r"Success: no issues found in \d+ source files?", salida), salida


@pytest.mark.parametrize(
    ("anadido", "mensaje"),
    [
        ("def sin_tipos(x): return x\n", "missing a type annotation"),
        (
            "from typing import Any\n\n\ndef devuelve_any(x: Any) -> int:\n    return x\n",
            "Returning Any from function declared to return",
        ),
    ],
    ids=["funcion_sin_anotar", "any_devuelto"],
)
def test_tkt004_ca11_funcion_sin_tipos_rompe_mypy(
    tmp_path: Path, cache_mypy: Path, anadido: str, mensaje: str
) -> None:
    """TC-80 · CA-11 esc. 2 — una función sin anotar o un Any en tipos base rompe mypy."""
    paquete = copiar_paquete(tmp_path)
    numericos = paquete / "numericos.py"
    original = numericos.read_text(encoding="utf-8")
    numericos.write_text(f"{original.rstrip()}\n\n\n{anadido}", encoding="utf-8", newline="\n")

    proceso = correr_mypy(tmp_path, cache_mypy)

    salida = proceso.stdout + proceso.stderr
    assert proceso.returncode != 0, salida
    assert mensaje in salida, salida
