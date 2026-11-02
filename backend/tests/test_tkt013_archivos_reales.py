"""Archivos reales del lector de catálogo (TKT-013b): TC-33 a TC-37.

Requieren `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`; si faltan, `pytest.skip` (PA-T3).
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import cast

from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo, Profundidad
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    HOJA_UNION,
    RUTAS_ESPERADAS_ENITI,
    RutaNombres,
    leer_catalogo_bytes,
    nombres_desde_ruta,
)

# Traducción del patrón E-6 neutro (TKT-013a) a los nombres del archivo ENITI.
_TRADUCCION_ENITI: dict[str, str] = {
    "RAIZ_NEUTRA": "ACABADOS EN MUROS Y PLAFONES",
    "NIVEL 1": "NIVEL 1",
    "ZONA_LOBBY": "LOBBY Y PASILLO",
    "TRABAJO_MUROS": "MUROS",
    "TRABAJO_PLAFONES": "PLAFONES Y CAJILLOS",
    "TRABAJO_GENERALES": "GENERALES",
    "TRABAJO_ENCHAPES_LOBBY": "ENCHAPES",
    "ZONA_ESCALERAS": "CUBO DE ESCALERAS",
    "TRABAJO_ENCHAPES_CUBO": "ENCHAPES",
    "DEPT_101": "DEPARTAMENTO 101 TIPO E",
}


def _traducir_ruta(ruta: RutaNombres) -> RutaNombres:
    return cast(
        RutaNombres,
        tuple(None if nombre is None else _TRADUCCION_ENITI.get(nombre, nombre) for nombre in ruta),
    )


_RUTAS_REALES_ENITI: dict[int, RutaNombres] = {
    fila: _traducir_ruta(ruta) for fila, ruta in RUTAS_ESPERADAS_ENITI.items()
}
# Conceptos adicionales en ENITI real (filas 46-55, corrida «GENERALES» en DEPT 101).
for _fila in range(46, 56):
    _RUTAS_REALES_ENITI[_fila] = (
        "ACABADOS EN MUROS Y PLAFONES",
        "NIVEL 1",
        "DEPARTAMENTO 101 TIPO E",
        "GENERALES",
    )

_RUTAS_REALES_UNION_9_20: dict[int, tuple[str | None, str | None, str | None, str | None]] = {
    12: ("Muros y Plafones de Tablaroca", "Nivel 1", "Pasillos", None),
    13: ("Muros y Plafones de Tablaroca", "Nivel 1", "Pasillos", None),
    14: ("Muros y Plafones de Tablaroca", "Nivel 1", "Pasillos", None),
    15: ("Muros y Plafones de Tablaroca", "Nivel 1", "Pasillos", None),
    16: ("Muros y Plafones de Tablaroca", "Nivel 1", "Pasillos", None),
    19: ("Muros y Plafones de Tablaroca", "Nivel 1", "DPTO. 111 TIPO  3R ", "Muros"),
    20: ("Muros y Plafones de Tablaroca", "Nivel 1", "DPTO. 111 TIPO  3R ", "Muros"),
}

_PATRON_NIVEL = re.compile(r"^(nivel\s+\d+|roof garden|sotano\s+\d+)$", re.IGNORECASE)

_UNIDADES_ENITI_CA5 = {"M2": 1763, "ML": 2079, "PZA": 1186}
_UNIDADES_UNION_CA5 = {"M2": 1237, "ML": 2189, "PZA": 855}


def test_hdu001_esc05_rutas_reales_de_eniti(archivo_eniti: bytes) -> None:
    """TC-33 · HDU-001 esc. 5 · CA-3 — tabla literal filas 9-45 (E-6)."""
    cat = leer_catalogo_bytes(archivo_eniti)
    por_fila = {c.fila: c for c in cat.conceptos}
    for fila, esperada in _RUTAS_REALES_ENITI.items():
        assert nombres_desde_ruta(por_fila[fila].ruta) == esperada

    c13 = por_fila[13]
    assert c13.codigo == "620001"
    assert nombres_desde_ruta(c13.ruta) == (
        "ACABADOS EN MUROS Y PLAFONES",
        "NIVEL 1",
        "LOBBY Y PASILLO",
        "MUROS",
    )
    c29 = por_fila[29]
    assert c29.codigo == "620040-A"
    assert nombres_desde_ruta(c29.ruta)[1:] == ("NIVEL 1", "CUBO DE ESCALERAS", "ENCHAPES")
    c32 = por_fila[32]
    assert c32.codigo == "620001"
    assert nombres_desde_ruta(c32.ruta)[1:] == ("NIVEL 1", "DEPARTAMENTO 101 TIPO E", "MUROS")

    filas_nodo = {n.fila for n in cat.nodos}
    filas_concepto = {c.fila for c in cat.conceptos}
    assert filas_nodo.isdisjoint(filas_concepto)


def test_hdu001_esc05_rutas_reales_de_union_square(archivo_union: bytes) -> None:
    """TC-34 · HDU-001 esc. 5 · CA-4 — filas 9-20 y ruta del 620001 en fila 19."""
    cat = leer_catalogo_bytes(archivo_union)
    por_fila = {c.fila: c for c in cat.conceptos if c.fila <= 20}
    for fila, esperada in _RUTAS_REALES_UNION_9_20.items():
        assert nombres_desde_ruta(por_fila[fila].ruta) == esperada
    c19 = por_fila[19]
    assert c19.codigo == "620001"
    assert nombres_desde_ruta(c19.ruta)[1:] == ("Nivel 1", "DPTO. 111 TIPO  3R ", "Muros")


def test_hdu001_esc05_lee_el_catalogo_de_eniti(archivo_eniti: bytes) -> None:
    """TC-35 · HDU-001 esc. 5 · CA-1, CA-2 — conteos, primer concepto y orden."""
    from tipos_base import Cantidad, Dinero

    cat = leer_catalogo_bytes(archivo_eniti)
    assert cat.hoja == HOJA_ENITI
    assert cat.fila_encabezado == 8
    assert len(cat.conceptos) == 5028
    filas = [c.fila for c in cat.conceptos]
    assert filas == sorted(filas)

    primero = cat.conceptos[0]
    assert primero.fila == 13
    assert primero.codigo == "620001"
    assert primero.unidad == "M2"
    assert primero.cantidad == Cantidad(Decimal(repr(16.089000000000002)))
    assert primero.precio_unitario == Dinero("668.69")

    c29 = next(c for c in cat.conceptos if c.fila == 29)
    assert c29.codigo == "620040-A"

    for concepto in cat.conceptos:
        if concepto.cantidad is not None:
            assert isinstance(concepto.cantidad.valor, Decimal)


def test_hdu001_esc05_lee_el_catalogo_de_union_square(archivo_union: bytes) -> None:
    """TC-35 · HDU-001 esc. 5 · CA-2 — conteos y primer concepto."""

    cat = leer_catalogo_bytes(archivo_union)
    assert cat.hoja == HOJA_UNION
    assert cat.fila_encabezado == 8
    assert len(cat.conceptos) == 4281
    primero = cat.conceptos[0]
    assert primero.fila == 12
    assert primero.codigo == "620012"
    assert primero.cantidad is not None
    assert isinstance(primero.cantidad.valor, Decimal)


def test_hdu001_esc05_oraculo_de_profundidad_en_los_archivos_reales(
    archivo_eniti: bytes, archivo_union: bytes
) -> None:
    """TC-36 · HDU-001 esc. 5 · CA-3, CA-4, CA-9 · PA-T2 — oráculo E-8."""
    cat_eniti = leer_catalogo_bytes(archivo_eniti)
    cat_union = leer_catalogo_bytes(archivo_union)

    vocab_partidas_eniti = {
        n.nombre
        for n in cat_eniti.nodos
        if n.profundidad is Profundidad.PARTIDA and n.nombre is not None
    }
    vocab_partidas_union = {
        n.nombre
        for n in cat_union.nodos
        if n.profundidad is Profundidad.PARTIDA and n.nombre is not None
    }

    for cat in (cat_eniti, cat_union):
        for nodo in cat.nodos:
            if nodo.profundidad is Profundidad.NIVEL:
                assert nodo.nombre is not None
                assert _PATRON_NIVEL.match(nodo.nombre.strip())
            if nodo.profundidad is Profundidad.RAIZ and nodo.nombre is not None:
                assert not _PATRON_NIVEL.match(nodo.nombre.strip())
            if nodo.profundidad is Profundidad.PARTIDA and nodo.nombre is not None:
                if cat is cat_eniti:
                    assert nodo.nombre in vocab_partidas_eniti
                else:
                    assert nodo.nombre in vocab_partidas_union
        assert not any(h.causa == CausaHallazgo.PROFUNDIDAD_EXCEDIDA for h in cat.hallazgos)

    sin_partida = [h for h in cat_union.hallazgos if h.causa == CausaHallazgo.CONCEPTO_SIN_PARTIDA]
    assert [h.fila for h in sin_partida] == [12, 13, 14, 15, 16]
    assert not any(h.causa == CausaHallazgo.CONCEPTO_SIN_PARTIDA for h in cat_eniti.hallazgos)


def test_hdu001_esc08_unidades_reales_normalizadas(
    archivo_eniti: bytes, archivo_union: bytes
) -> None:
    """TC-37 · HDU-001 esc. 8 · CA-5 — conteos M2, ML, PZA y sin UNIDAD_NO_RECONOCIDA."""
    cat_eniti = leer_catalogo_bytes(archivo_eniti)
    cat_union = leer_catalogo_bytes(archivo_union)

    def contar_unidades(cat) -> Counter[str]:
        return Counter(c.unidad for c in cat.conceptos if c.unidad is not None)

    assert contar_unidades(cat_eniti) == Counter(_UNIDADES_ENITI_CA5)
    assert contar_unidades(cat_union) == Counter(_UNIDADES_UNION_CA5)
    for cat in (cat_eniti, cat_union):
        assert not any(h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA for h in cat.hallazgos)


def test_hdu001_esc06_ref_real_de_union_square(archivo_union: bytes) -> None:
    """TC-37 · HDU-001 esc. 6 · CA-7 — 8,562 ERROR_DE_FORMULA en E y F."""
    cat = leer_catalogo_bytes(archivo_union)
    refs = [h for h in cat.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA]
    assert len(refs) == 8562
    assert all(h.columna in ("E", "F") for h in refs)
    assert not any(h.columna == "D" for h in refs)
    h13 = next(h for h in refs if h.fila == 13 and h.columna == "E")
    assert h13.hoja == HOJA_UNION
    assert h13.valor_original == "#REF!"
    assert len([c for c in cat.conceptos if c.cantidad is not None]) == 4281


def test_hdu001_esc05_nombres_ilegibles_reales(archivo_eniti: bytes, archivo_union: bytes) -> None:
    """TC-37 · HDU-001 esc. 5 · CA-11 — 21 NOMBRE_ILEGIBLE en columna B."""
    ilegibles: list[Hallazgo] = []
    for contenido in (archivo_eniti, archivo_union):
        cat = leer_catalogo_bytes(contenido)
        ilegibles.extend(h for h in cat.hallazgos if h.causa == CausaHallazgo.NOMBRE_ILEGIBLE)
    assert len(ilegibles) == 21
    assert all(h.columna == "B" for h in ilegibles)
    assert all(h.valor_original == "#REF!" for h in ilegibles)
