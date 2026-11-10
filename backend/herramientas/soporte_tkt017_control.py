"""Siembra de una línea base `CONGELADA` con cifras exactas, para las pruebas del presupuesto de control (TKT-017c).

Las cifras del escenario de `HDU-001` (importe de venta de MUROS `480000.0000`, sugerido `410000.0000`) no
salen de ningún libro real: el libro de `CA-A1` suma `8329.9860`. Aquí se siembran directamente las apariciones
y sus copias mientras la línea base está `BORRADOR` (el disparador solo admite insertar copias en un
`BORRADOR`, y el rol de aplicación solo tiene `SELECT` e `INSERT` sobre `linea_base_concepto`), una fila de
`presupuesto_control` por tipo y, al final, se pasa a `CONGELADA` con el mismo `UPDATE` que usa el congelado.

Son ayudantes de prueba: ningún código de producción los importa.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from herramientas.soporte_tkt017_entorno import Entorno


class ConceptoSembrado(NamedTuple):
    """Una copia congelada: la cantidad y el precio de la aparición y su importe ya cuantizado."""

    cantidad: Decimal
    precio_unitario: Decimal
    importe: Decimal


class CifrasDeTipo(NamedTuple):
    """Los conceptos congelados de un tipo de partida y el sugerido de su fila de control."""

    clave: str
    conceptos: tuple[ConceptoSembrado, ...]
    sugerido: Decimal


class LineaBaseSembrada(NamedTuple):
    """La línea base `CONGELADA` sembrada, con las filas de control y los tipos por clave."""

    linea_base_id: uuid.UUID
    controles: dict[str, uuid.UUID]
    tipos: dict[str, uuid.UUID]
    importe_venta: Decimal


def concepto_de(importe: str) -> ConceptoSembrado:
    """Un concepto de cantidad `1.0000` cuyo precio unitario es el propio importe."""
    return ConceptoSembrado(Decimal("1.0000"), Decimal(importe), Decimal(importe))


# MUROS vende 480000.0000 en dos conceptos; las demás bolsas existen con sugerido y sin tope.
CIFRAS_ESCENARIO: tuple[CifrasDeTipo, ...] = (
    CifrasDeTipo(
        "MUROS",
        (concepto_de("300000.5000"), concepto_de("179999.5000")),
        Decimal("410000.0000"),
    ),
    CifrasDeTipo("PLAFONES_Y_CAJILLOS", (concepto_de("120000.0000"),), Decimal("95000.0000")),
    CifrasDeTipo("ENCHAPES", (), Decimal("0.0000")),
    CifrasDeTipo("GENERALES", (), Decimal("0.0000")),
)

# Datos de redondeo: cada aparición de PLAFONES vale 0.5000 × 0.0001 = 0.00005, que `cuantizar()` lleva a
# 0.0001; la suma de lo ya cuantizado es 0.0002, no los 0.0001 que daría sumar sin cuantizar.
CIFRAS_CON_REDONDEO: tuple[CifrasDeTipo, ...] = (
    CifrasDeTipo("MUROS", (concepto_de("480000.0000"),), Decimal("410000.0000")),
    CifrasDeTipo(
        "PLAFONES_Y_CAJILLOS",
        (
            ConceptoSembrado(Decimal("0.5000"), Decimal("0.0001"), Decimal("0.0001")),
            ConceptoSembrado(Decimal("0.5000"), Decimal("0.0001"), Decimal("0.0001")),
        ),
        Decimal("0.0001"),
    ),
    CifrasDeTipo("ENCHAPES", (concepto_de("12345.6789"),), Decimal("10000.0000")),
    CifrasDeTipo("GENERALES", (), Decimal("0.0000")),
)


def sembrar_congelada_con_cifras(
    entorno: Entorno, cifras: tuple[CifrasDeTipo, ...] = CIFRAS_ESCENARIO
) -> LineaBaseSembrada:
    """Una línea base versión 1 `CONGELADA` en la obra del entorno, que pasa a `ACTIVA`.

    `linea_base.importe_venta` es la suma de los importes de todas las copias. Cada tipo recibe su
    nivel, área y partida, un concepto por cada `ConceptoSembrado` con su copia, y una fila de
    `presupuesto_control` con el sugerido y sin tope, como las crea el congelado real.
    """
    datos = entorno.datos
    total = sum(
        (c.importe for cifra in cifras for c in cifra.conceptos),
        start=Decimal("0.0000"),
    )
    linea_base_id = datos.linea_base(
        estado="BORRADOR",
        obra_id=entorno.obra_id,
        creado_por_id=entorno.usuario_id,
        version=1,
        importe_venta=total,
    )
    nivel_id = datos.nivel(obra_id=entorno.obra_id)
    controles: dict[str, uuid.UUID] = {}
    tipos: dict[str, uuid.UUID] = {}
    for cifra in cifras:
        tipo_id = datos.tipo_partida(clave=cifra.clave)
        tipos[cifra.clave] = tipo_id
        partida_id = datos.partida(
            area_id=datos.area(nivel_id=nivel_id, nombre=f"Área de {cifra.clave}"),
            tipo_partida_id=tipo_id,
        )
        for numero, concepto in enumerate(cifra.conceptos, start=1):
            codigo = f"{cifra.clave}-{numero}"
            aparicion_id = datos.partida_concepto(
                concepto_id=datos.concepto(obra_id=entorno.obra_id, codigo=codigo),
                partida_id=partida_id,
                cantidad=concepto.cantidad,
                precio_unitario=concepto.precio_unitario,
                importe=concepto.importe,
            )
            datos.copia_concepto(
                linea_base_id=linea_base_id,
                partida_concepto_id=aparicion_id,
                codigo=codigo,
                cantidad=concepto.cantidad,
                precio_unitario=concepto.precio_unitario,
                importe=concepto.importe,
            )
        controles[cifra.clave] = datos.control(
            linea_base_id=linea_base_id, tipo_partida_id=tipo_id, importe_sugerido=cifra.sugerido
        )
    datos.congelar(linea_base_id)
    entorno.poner_obra_en("ACTIVA")
    return LineaBaseSembrada(linea_base_id, controles, tipos, total)
