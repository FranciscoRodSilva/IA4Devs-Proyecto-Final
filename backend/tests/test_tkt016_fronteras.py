"""Inmutabilidad y pureza del dominio explosion (TKT-016, fila A6)."""

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cimenta.presupuesto.dominio.explosion import (
    ConceptoAExplotar,
    RenglonExplosion,
    calcular_explosion,
)
from herramientas.soporte_tkt016 import MUROS, analisis, concepto, insumo_material
from tipos_base import Rendimiento

_MODULO = (
    Path(__file__).resolve().parents[1] / "cimenta" / "presupuesto" / "dominio" / "explosion.py"
)
_PROHIBIDOS = {"datetime", "os", "io", "pathlib", "socket", "random"}


def test_hdu001_esc14_renglon_inmutable_sin_rendimiento_observado() -> None:
    """TC-21 · CA-9 — renglón congelado e invariante 19."""
    panel = insumo_material(clave="PANEL", rendimiento="1", costo="10")
    item = ConceptoAExplotar(
        concepto=concepto(fila=10, codigo="X", cantidad="1"),
        tipo_partida_id=MUROS,
        analisis=analisis(insumos=(panel,)),
    )
    from cimenta.presupuesto.dominio.explosion import ExplosionCalculada

    explosion = calcular_explosion((item,))
    assert isinstance(explosion, ExplosionCalculada)
    r = explosion.renglones[0]
    original = r.rendimiento_congelado
    with pytest.raises(FrozenInstanceError):
        r.rendimiento_congelado = Rendimiento("9")  # type: ignore[misc]
    assert r.rendimiento_congelado == original
    for nombre in RenglonExplosion.__dataclass_fields__:
        assert "observado" not in nombre.lower()
    assert "observado" not in calcular_explosion.__code__.co_varnames


def test_hdu001_esc14_regla_solo_importa_biblioteca_estandar_y_tipos_base() -> None:
    """TC-22 · CA-R1 — lista blanca de imports en explosion.py."""
    arbol = ast.parse(_MODULO.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                modulos.add(alias.name)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    raices = {m.split(".")[0] for m in modulos}
    assert raices.isdisjoint(_PROHIBIDOS)
    permitidos_std = {"__future__", "collections", "dataclasses", "enum", "uuid", "tipos_base"}
    assert raices <= permitidos_std | {"cimenta"}
    for mod in modulos:
        if mod.startswith("cimenta."):
            assert mod.startswith("cimenta.presupuesto.dominio.")
        elif mod != "tipos_base":
            assert mod.split(".")[0] in permitidos_std


def test_hdu001_esc14_parametros_sin_rendimiento_observado() -> None:
    """TC-21 complemento — ningún campo del renglón se llama observado."""
    campos = {f.name for f in RenglonExplosion.__dataclass_fields__.values()}
    assert campos == {
        "tipo_partida_id",
        "clave_insumo",
        "cantidad_conceptos",
        "cantidad_presupuestada",
        "rendimiento_congelado",
        "costo_unitario",
        "importe",
    }
