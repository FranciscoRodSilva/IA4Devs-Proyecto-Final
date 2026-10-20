"""Fronteras del dominio con lista blanca (TKT-004, fila 5): TC-90 a TC-98.

Sin Docker (CA-13). Cada violación se escribe en una copia del árbol bajo `tmp_path` y nunca en
el árbol que se revisa; la configuración que se prueba es la `pyproject.toml` del repositorio.
`lint-imports` se identifica por el `id` del contrato (`--contract`) y no por su `name`, que es
texto libre y cambia con el contrato. Cuando se cuentan contratos, el total es el de la
configuración real: con el contrato propio y `tipos-base-puro` son quince.
"""

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
DOMINIO_DE_COMPRAS = "cimenta/compras/dominio/regla_tkt004.py"


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


def anadir(ruta: Path, texto: str) -> None:
    original = ruta.read_text(encoding="utf-8")
    escribir(ruta, f"{original.rstrip()}\n{texto}")


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


def test_tkt004_ca10_dominio_importa_estandar_y_tipos_base(copia: Path) -> None:
    """TC-90 · CA-10 esc. 1 — un dominio con decimal y tipos_base cumple los 15 contratos."""
    escribir(
        copia / DOMINIO_DE_COMPRAS,
        "from __future__ import annotations\n\n"
        "from decimal import Decimal\n\n"
        "from tipos_base import Dinero\n",
    )

    corrida = correr_linter(copia)

    assert corrida.codigo == 0, corrida.salida
    assert contratos_cumplidos_y_rotos(corrida) == (15, 0), corrida.salida


@pytest.mark.parametrize("tercero", ["requests", "numpy"])
def test_tkt004_ca10_tercero_cualquiera_rompe_el_dominio(copia: Path, tercero: str) -> None:
    """TC-91 · CA-10 esc. 2 — un tercero que no es fastapi, sqlalchemy ni pydantic rompe el dominio."""
    escribir(copia / DOMINIO_DE_COMPRAS, f"import {tercero}\n")

    corrida = correr_linter(copia, "dominio-sin-framework")

    afirmar_contrato_roto(corrida)
    assert f"cimenta.compras.dominio no puede alcanzar {tercero}" in corrida.salida, corrida.salida


def test_tkt004_ca10_framework_directo_rompe_el_dominio(copia: Path) -> None:
    """TC-92 · CA-10 esc. 3 — importar pydantic en el dominio sigue prohibido."""
    escribir(copia / DOMINIO_DE_COMPRAS, "import pydantic\n")

    corrida = correr_linter(copia, "dominio-sin-framework")

    afirmar_contrato_roto(corrida)
    assert "pydantic" in corrida.salida, corrida.salida


def test_tkt004_ca10_framework_indirecto_rompe_el_dominio(copia: Path) -> None:
    """TC-93 · CA-10 esc. 3 — tipos_base que arrastra sqlalchemy rompe al dominio que lo importa."""
    anadir(copia / "tipos_base" / "numericos.py", "import sqlalchemy\n")
    escribir(copia / DOMINIO_DE_COMPRAS, "from tipos_base import Dinero\n")

    del_dominio = correr_linter(copia, "dominio-sin-framework")
    del_paquete = correr_linter(copia, "tipos-base-puro")

    afirmar_contrato_roto(del_dominio)
    assert "no puede alcanzar sqlalchemy" in del_dominio.salida, del_dominio.salida
    assert "tipos_base" in del_dominio.salida, del_dominio.salida
    afirmar_contrato_roto(del_paquete)


def test_tkt004_ca10_dominio_no_importa_la_interfaz_de_otro_modulo(copia: Path) -> None:
    """TC-94 · CA-10, D-5 — la interfaz de otro módulo no llega al dominio, aunque el grafo la admita."""
    escribir(copia / DOMINIO_DE_COMPRAS, "from cimenta.presupuesto import interfaz\n")

    del_grafo = correr_linter(copia, "grafo-presupuesto", "solo-por-interfaz")
    del_dominio = correr_linter(copia, "dominio-sin-framework")

    assert del_grafo.codigo == 0, del_grafo.salida
    assert contratos_cumplidos_y_rotos(del_grafo) == (2, 0), del_grafo.salida
    afirmar_contrato_roto(del_dominio)
    assert "no puede alcanzar cimenta.presupuesto.interfaz" in del_dominio.salida, (
        del_dominio.salida
    )


@pytest.mark.parametrize(
    ("importado", "alcanzado"),
    [("pydantic", "pydantic"), ("cimenta.presupuesto", "cimenta.presupuesto")],
    ids=["tercero", "modulo_de_negocio"],
)
def test_tkt004_ca10_tipos_base_puro(copia: Path, importado: str, alcanzado: str) -> None:
    """TC-95 · CA-10 esc. 4 — tipos_base que importa un tercero o un módulo de negocio se rompe."""
    escribir(copia / "tipos_base" / "ajeno.py", f"import {importado}\n")

    corrida = correr_linter(copia, "tipos-base-puro")

    afirmar_contrato_roto(corrida)
    assert f"tipos_base no puede alcanzar {alcanzado}" in corrida.salida, corrida.salida


@pytest.mark.parametrize(
    ("contrato", "archivo", "contenido", "fragmento"),
    [
        (
            "esqueleto-modulos",
            "cimenta/extra/__init__.py",
            '"""Fuera del esqueleto."""\n',
            "cimenta.extra",
        ),
        ("dominio-sin-framework", DOMINIO_DE_COMPRAS, "import fastapi\n", "fastapi"),
        (
            "solo-por-interfaz",
            "cimenta/compras/aplicacion/x.py",
            "import cimenta.presupuesto.dominio\n",
            "cimenta.presupuesto.dominio",
        ),
    ],
    ids=["modulo_extra", "dominio_con_fastapi", "dominio_de_otro_modulo"],
)
def test_tkt004_car3_contratos_de_tkt002_siguen_vigentes(
    copia: Path, contrato: str, archivo: str, contenido: str, fragmento: str
) -> None:
    """TC-96 · CA-R3 — cada contrato de TKT-002 sigue rompiéndose ante su violación."""
    escribir(copia / archivo, contenido)

    corrida = correr_linter(copia, contrato)

    afirmar_contrato_roto(corrida)
    assert fragmento in corrida.salida, corrida.salida


@pytest.mark.parametrize(
    ("bloque", "mensaje"),
    [
        ('origen = ["cimenta.*.nada"]\n', "Ningún módulo coincide"),
        ('origen = ["cimenta.compras.inexistente"]\n', "no existe"),
        ('origen = ["cimenta.*.dominio"]\npermitidos = ["tipos_inexistente"]\n', "no existe"),
    ],
    ids=["comodin_sin_coincidencia", "origen_inexistente", "permitido_inexistente"],
)
def test_tkt004_ca10_comodin_sin_coincidencia_no_da_verde(
    copia: Path, bloque: str, mensaje: str
) -> None:
    """TC-97 · CA-10 — una configuración que no alcanza nada rompe la ejecución, no da verde."""
    anadir(
        copia / "pyproject.toml",
        '\n[[tool.importlinter.contracts]]\nid = "verde-vacio"\nname = "Contrato de prueba"\n'
        f'type = "lista_blanca"\n{bloque}',
    )

    corrida = correr_linter(copia, "verde-vacio")

    assert corrida.codigo != 0, corrida.salida
    assert mensaje in corrida.salida, corrida.salida
    assert "KEPT" not in corrida.salida, corrida.salida


@pytest.mark.parametrize(
    "importacion",
    ["import tipos_basefoo\n", "from tipos_basefoo import Dinero\n"],
    ids=["import_directo", "import_desde"],
)
def test_tkt004_ca10_prefijo_de_permitido_no_es_permitido(copia: Path, importacion: str) -> None:
    """TC-99 · CA-10 — un paquete cuyo nombre solo empieza como `tipos_base` rompe el dominio."""
    escribir(copia / DOMINIO_DE_COMPRAS, importacion)

    corrida = correr_linter(copia, "dominio-sin-framework")

    afirmar_contrato_roto(corrida)
    assert "cimenta.compras.dominio no puede alcanzar tipos_basefoo" in corrida.salida, (
        corrida.salida
    )


def test_tkt004_ca10_modulo_con_prefijo_de_permitido_rompe_el_contrato(copia: Path) -> None:
    """TC-100 · CA-10 — `cimenta.presupuestox` no es `cimenta.presupuesto` ni cuelga de él."""
    escribir(copia / "cimenta/presupuestox/__init__.py", '"""Nombre que empieza como otro."""\n')
    escribir(copia / DOMINIO_DE_COMPRAS, "import cimenta.presupuestox\n")
    anadir(
        copia / "pyproject.toml",
        '\n[[tool.importlinter.contracts]]\nid = "permitido-con-prefijo"\nname = "Contrato de prueba"\n'
        'type = "lista_blanca"\norigen = ["cimenta.compras.dominio"]\n'
        'permitidos = ["cimenta.presupuesto"]\n',
    )

    corrida = correr_linter(copia, "permitido-con-prefijo")

    afirmar_contrato_roto(corrida)
    assert "cimenta.compras.dominio no puede alcanzar cimenta.presupuestox" in corrida.salida, (
        corrida.salida
    )


def test_tkt004_ca10_arbol_real() -> None:
    """TC-98 · CA-10, CA-R3 — el árbol real cumple los 15 contratos."""
    corrida = correr_linter(BACKEND)

    assert corrida.codigo == 0, corrida.salida
    assert contratos_cumplidos_y_rotos(corrida) == (15, 0), corrida.salida
