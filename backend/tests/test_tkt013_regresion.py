"""Regresión TKT-013a: TC-INV-1 y TC-INV-2 (fronteras y float en dominio)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"


def test_tkt013_car1_lint_imports_sin_violaciones_nuevas() -> None:
    """TC-INV-1 · CA-R1 · reglas 2 y 3 — import-linter en verde con el dominio nuevo."""
    proceso = subprocess.run(
        [sys.executable, "-c", LINTER],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    salida = proceso.stdout + proceso.stderr
    assert proceso.returncode == 0, salida
    assert "0 broken" in salida or "Contracts: 16 kept" in salida


def test_tkt013_car2_verificar_float_dominio_presupuesto() -> None:
    """TC-INV-2 · CA-R2 · regla 1 — sin float en firmas de presupuesto/dominio/."""
    proceso = subprocess.run(
        [sys.executable, "-m", "herramientas.verificar_float"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    assert "hallazgos: 0" in proceso.stdout
