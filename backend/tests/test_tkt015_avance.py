"""TKT-015b · Progreso de lectura y callback al_avanzar (fila B3): TC-50 y TC-51."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from cimenta.presupuesto.dominio.importacion import progreso_de_lectura
from herramientas.soporte_tkt014 import escribir_hoja_apu_sintetica
from herramientas.soporte_tkt015 import libro_sintetico
from tipos_base import Porcentaje

if TYPE_CHECKING:
    from conftest import LibroCatalogo


@pytest.mark.parametrize("posicion_catalogo", [0, 2])
def test_tkt015_lector_con_avance_no_cambia_el_resultado_cuatro_hojas(
    libro_catalogo: LibroCatalogo,
    posicion_catalogo: int,
) -> None:
    """TC-50 · CA-R1 · CA-13 — cuatro hojas; el catálogo puede ir en distinta posición."""
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto

    insumos: dict[str, str] = {}
    contenido = libro_sintetico(
        libro_catalogo,
        conceptos=3,
        codigos=("P-001", "P-002", "P-003"),
        posicion_catalogo=posicion_catalogo,
    )
    sin_callback = leer_libro_presupuesto(contenido, insumos)
    llamadas: list[tuple[int, int]] = []

    def registrar(leidas: int, totales: int) -> None:
        llamadas.append((leidas, totales))

    con_callback = leer_libro_presupuesto(contenido, insumos, al_avanzar=registrar)
    assert con_callback == sin_callback
    assert llamadas == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_tkt015_lector_con_avance_tres_apu_sin_catalogo(libro_catalogo: LibroCatalogo) -> None:
    """TC-50 · CA-R1 — sin hoja de catálogo, tres hojas APU."""
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto

    insumos: dict[str, str] = {}
    for codigo in ("P-001", "P-002", "P-003"):
        nombre = f"APU {codigo}"
        escribir_hoja_apu_sintetica(libro_catalogo, nombre, codigo=codigo)
    contenido = libro_catalogo.bytes()
    llamadas: list[tuple[int, int]] = []
    leer_libro_presupuesto(
        contenido,
        insumos,
        al_avanzar=lambda leidas, totales: llamadas.append((leidas, totales)),
    )
    assert llamadas == [(1, 3), (2, 3), (3, 3)]


def test_tkt015_lector_con_avance_contenido_invalido_sin_llamadas() -> None:
    """TC-50 · CA-R1 — libro inválido no invoca el callback."""
    from cimenta.presupuesto.infraestructura.lector_catalogo import leer_libro_presupuesto

    llamadas: list[tuple[int, int]] = []
    leer_libro_presupuesto(
        b"",
        {},
        al_avanzar=lambda leidas, totales: llamadas.append((leidas, totales)),
    )
    assert llamadas == []


@pytest.mark.parametrize(
    ("leidas", "totales", "esperado"),
    [
        (0, 5, Decimal("0")),
        (5, 5, Decimal("0.9")),
        (1, 3, Decimal("0.300000")),
        (4, 7, Decimal("0.514285")),
        (7, 5, Decimal("0.9")),
        (1, 0, Decimal("0")),
    ],
)
def test_hdu001_esc04_progreso_de_lectura(
    leidas: int,
    totales: int,
    esperado: Decimal,
) -> None:
    """TC-51 · CA-13 — escala y ROUND_DOWN en el avance parcial."""
    obtenido = progreso_de_lectura(leidas, totales)
    assert isinstance(obtenido, Porcentaje)
    assert obtenido.valor == esperado
