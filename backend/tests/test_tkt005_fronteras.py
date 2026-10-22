"""Fronteras del contrato de error (TKT-005, fila 3): TC-30 a TC-33.

Sin Docker (CA-R4). TC-30 importa `contrato_error` en un proceso limpio y mira lo que de verdad
se cargó, también lo indirecto: `contrato_error` queda fuera de `root_packages` de `import-linter`
(D-2), así que su pureza no la vigila ningún contrato. TC-31 a TC-33 reutilizan el esquema de
TKT-004: cada violación se escribe en una copia del árbol bajo `tmp_path` y nunca en el árbol que
se revisa, y `lint-imports` se identifica por el `id` del contrato.

TC-31 a TC-33 nacen en verde: la lista blanca de `dominio-sin-framework` ya rechaza cualquier
paquete externo, exista o no. Lo que demuestra que dependen de algo es el mutante MT-21b (añadir
`contrato_error` a `permitidos`), que pone en rojo a TC-31.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".import_linter_cache")
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")
DOMINIO_DE_COMPRAS = "cimenta/compras/dominio/regla_tkt005.py"
APLICACION_DE_COMPRAS = "cimenta/compras/aplicacion/caso_tkt005.py"

# El proceso limpio mide lo que carga importar `contrato_error` y su excepción de regla: lo que
# había en `sys.modules` antes (el intérprete y `json`) no cuenta.
PROGRAMA = """
import json
import sys

antes = set(sys.modules)
import contrato_error
from contrato_error import RechazoRegla

cargados = set(sys.modules) - antes
print(json.dumps({
    "raices": sorted({nombre.partition(".")[0] for nombre in cargados}),
    "modulos": sorted(cargados),
}))
"""


class Corrida(NamedTuple):
    codigo: int
    salida: str


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    """Copia de lo que `lint-imports` necesita: configuración, módulos, tipos base y el contrato."""
    destino = tmp_path / "copia"
    destino.mkdir()
    shutil.copy(BACKEND / "pyproject.toml", destino / "pyproject.toml")
    for paquete in ("cimenta", "tipos_base", "herramientas"):
        shutil.copytree(BACKEND / paquete, destino / paquete, ignore=IGNORAR)
    return destino


def escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8", newline="\n")


def correr_linter(cwd: Path, *contratos: str) -> Corrida:
    argumentos = [argumento for c in contratos for argumento in ("--contract", c)]
    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache", *argumentos],
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    return Corrida(proceso.returncode, proceso.stdout + proceso.stderr)


def contratos_cumplidos_y_rotos(corrida: Corrida) -> tuple[int, int]:
    resumen = RESUMEN.search(corrida.salida)
    assert resumen, corrida.salida
    return int(resumen.group(1)), int(resumen.group(2))


def afirmar_contrato_roto(corrida: Corrida) -> None:
    """El único contrato pedido terminó roto: código 1 y `0 kept, 1 broken`."""
    assert corrida.codigo == 1, corrida.salida
    assert contratos_cumplidos_y_rotos(corrida) == (0, 1), corrida.salida


def test_tkt005_ca13_contrato_error_solo_carga_estandar_y_tipos_base() -> None:
    """TC-30 · CA-13, CA-R3 esc. 3, PA-T3 — importar contrato_error carga solo la biblioteca estándar y tipos_base."""
    proceso = subprocess.run(
        [sys.executable, "-c", PROGRAMA],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    assert proceso.returncode == 0, proceso.stderr
    cargado = json.loads(proceso.stdout.strip().splitlines()[-1])
    ajenos = [
        raiz
        for raiz in cargado["raices"]
        if raiz not in sys.stdlib_module_names and raiz not in {"contrato_error", "tipos_base"}
    ]
    assert ajenos == [], (
        f"contrato_error arrastra paquetes que no son de la biblioteca estándar: {ajenos}"
    )
    # Anti-verde vacío: lo que se mide es de verdad la importación de la excepción de regla.
    assert "contrato_error" in cargado["raices"]
    assert "contrato_error.excepciones" in cargado["modulos"]
    assert "tipos_base" in cargado["raices"]


def test_tkt005_car3_dominio_no_importa_contrato_error(copia: Path) -> None:
    """TC-31 · CA-R3, PA-T1 — un dominio que importa contrato_error rompe dominio-sin-framework."""
    escribir(copia / DOMINIO_DE_COMPRAS, "from contrato_error import RechazoRegla\n")

    corrida = correr_linter(copia, "dominio-sin-framework")

    afirmar_contrato_roto(corrida)
    assert "cimenta.compras.dominio no puede alcanzar contrato_error" in corrida.salida, (
        corrida.salida
    )


@pytest.mark.parametrize("framework", ["fastapi", "pydantic", "structlog"])
def test_tkt005_car3_dominio_no_importa_framework(copia: Path, framework: str) -> None:
    """TC-32 · CA-R3 esc. 2 — importar fastapi, pydantic o structlog desde dominio/ rompe dominio-sin-framework."""
    escribir(copia / DOMINIO_DE_COMPRAS, f"import {framework}\n")

    corrida = correr_linter(copia, "dominio-sin-framework")

    afirmar_contrato_roto(corrida)
    assert f"cimenta.compras.dominio no puede alcanzar {framework}" in corrida.salida, (
        corrida.salida
    )


def test_tkt005_car3_aplicacion_puede_lanzar_el_rechazo(copia: Path) -> None:
    """TC-33 · CA-R3 esc. 1 y 3 — la aplicacion/ de un módulo importa RechazoRegla sin romper ninguno de los 15 contratos."""
    escribir(copia / APLICACION_DE_COMPRAS, "from contrato_error import RechazoRegla\n")

    corrida = correr_linter(copia)

    assert corrida.codigo == 0, corrida.salida
    assert contratos_cumplidos_y_rotos(corrida) == (15, 0), corrida.salida
    assert "ignore_imports" not in (BACKEND / "pyproject.toml").read_text(encoding="utf-8")
