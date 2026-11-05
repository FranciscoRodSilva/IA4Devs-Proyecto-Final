"""TKT-072 · La preparación de la importación no cambia: TC-22 (`CA-R3`).

TKT-072 separa el concepto de sus apariciones en el esquema, pero la preparación (`formato` 1) sigue
guardando una entrada por fila del catálogo, con su fila y su ruta (`M6`). El mismo código en dos
áreas son dos entradas con áreas distintas, y el análisis no escribe en `concepto` ni en
`partida_concepto`: eso lo hará TKT-017 al confirmar.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.infraestructura.preparacion_json import FORMATO_PREPARACION
from herramientas.soporte_tkt014 import escribir_hoja_apu_sintetica
from herramientas.soporte_tkt015 import HOJA_CATALOGO_SINTETICO

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto, LibroCatalogo


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:  # type: ignore[no-untyped-def]
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)


def _libro_con_un_codigo_en_dos_areas(libro: LibroCatalogo) -> bytes:
    """`P-001` en `ZONA A` (fila 9) y en `ZONA B` (fila 12), con su hoja de análisis.

    Las filas 10 y 11 forman una corrida posterior de dos filas: el lector las alinea a la partida y
    reemplaza el área y la partida (`E-4`).
    """
    libro.nueva_hoja(HOJA_CATALOGO_SINTETICO)
    for fila in range(1, 4):
        libro.escribir_fila(HOJA_CATALOGO_SINTETICO, fila, (None,))
    filas: tuple[tuple[int, tuple[Any, ...]], ...] = (
        (4, ("Código", "DESCRIPCION", "Unidad", "Cantidad", "P.U.", "IMPORTE")),
        (5, (None, "RAIZ SINTETICA")),
        (6, (None, "NIVEL 1")),
        (7, (None, "ZONA A")),
        (8, (None, "PARTIDA MUROS")),
        (9, ("P-001", "CONCEPTO P-001", "M2", 1, 10, 10)),
        (10, (None, "ZONA B")),
        (11, (None, "PARTIDA MUROS")),
        (12, ("P-001", "CONCEPTO P-001", "M2", 2, 10, 20)),
    )
    for numero, valores in filas:
        libro.escribir_fila(HOJA_CATALOGO_SINTETICO, numero, valores)
    escribir_hoja_apu_sintetica(libro, "APU P-001", codigo="P-001")
    return libro.bytes()


def test_tkt072_car3_la_preparacion_guarda_una_entrada_por_fila(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-22 · CA-R3 · `M6` — un código en dos áreas deja dos entradas en la preparación y nada en `concepto`."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    importacion_id: uuid.UUID = datos_presupuesto.importacion(estado="RECIBIDO")
    contenido = _libro_con_un_codigo_en_dos_areas(libro_catalogo)

    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    resultado = analizar_contenido(contenido, trabajo.insumos_existentes)
    registrar_resultado(fabrica_sesiones, importacion_id, resultado)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        fila = aplicacion.execute(
            "SELECT estado, preparacion FROM importacion WHERE id = %s", (importacion_id,)
        ).fetchone()
        conceptos = aplicacion.execute("SELECT count(*) FROM concepto").fetchone()
        apariciones = aplicacion.execute("SELECT count(*) FROM partida_concepto").fetchone()
    assert fila is not None
    estado, preparacion = fila
    assert estado == "VALIDADO"
    assert preparacion["formato"] == FORMATO_PREPARACION
    entradas = preparacion["conceptos"]
    assert len(entradas) == 2
    assert [e["fila"] for e in entradas] == [9, 12]
    assert [e["codigo"] for e in entradas] == ["P-001", "P-001"]
    areas = [e["ruta"]["area"] for e in entradas]
    assert areas[0] != areas[1], areas
    assert conceptos == (0,)
    assert apariciones == (0,)
