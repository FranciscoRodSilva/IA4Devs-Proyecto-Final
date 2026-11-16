"""Siembra de órdenes de compra para las pruebas de TKT-029b (fila F3). Solo lo importan las pruebas.

`sembrar_orden_compra` escribe, con la conexión que recibe, una requisición `CONVERTIDA`, su orden de
compra y los renglones de la orden. Cumple lo que `0014` exige: el folio es obligatorio fuera de
`BORRADOR`, la `cantidad_recibida` de cada renglón es explícita (su `DEFAULT` es 0) y no supera lo
ordenado más el excedente autorizado (`ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado`).

No abre transacción ni confirma: la transacción la decide quien llama, como `asentar`. Con una
conexión `autocommit`, cada sentencia se confirma sola. Las cantidades y los importes se construyen
desde cadena, nunca desde `float`.

Vive fuera de los archivos de prueba para que ninguno importe a otro (nota de ejecución del diseño de
TKT-029b). Es de apoyo de pruebas: ningún código de producción lo importa.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import psycopg

Conexion = psycopg.Connection[tuple[Any, ...]]

INSTANTE = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
FECHA_COMPROMISO = date(2026, 11, 20)
COSTO_UNITARIO = Decimal("800.0000")
MOTIVO_DE_CANCELACION = "Cancelada en la prueba: el proveedor no entrega."
_ESCALA_IMPORTE = Decimal("0.0001")
_PREFIJO_FOLIO_ORDEN = "OC-"
_PREFIJO_FOLIO_REQUISICION = "REQ-"


def sembrar_orden_compra(
    conexion: Conexion,
    *,
    obra_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    insumo_id: uuid.UUID,
    solicitante_id: uuid.UUID,
    proveedor_id: uuid.UUID,
    folio: str,
    renglones: Sequence[tuple[str, str]],
    excedente: str = "0",
    cancelada: bool = False,
) -> uuid.UUID:
    """Siembra una requisición `CONVERTIDA` y su orden de compra; devuelve el `id` de la orden.

    `renglones` son pares `(cantidad_ordenada, cantidad_recibida)` en cadena, en el orden en que se
    insertan. `excedente` es la `cantidad_excedente_autorizada` de cada renglón. Con `cancelada`, la
    orden lleva `cancelada_en` y `motivo_cancelacion`. El folio de la requisición es `REQ-` seguido del
    sufijo del folio de la orden, que es lo que sigue a `OC-`.
    """
    if not folio.startswith(_PREFIJO_FOLIO_ORDEN):
        raise ValueError(
            f"El folio de una orden de prueba empieza por {_PREFIJO_FOLIO_ORDEN!r}: {folio!r}"
        )
    autorizado_extra = Decimal(excedente)
    cantidades = [(Decimal(ordenada), Decimal(recibida)) for ordenada, recibida in renglones]
    importes = [(ordenada * COSTO_UNITARIO).quantize(_ESCALA_IMPORTE) for ordenada, _ in cantidades]
    importe_total = sum(importes, Decimal("0.0000"))
    requisicion_id = uuid.uuid4()
    orden_id = uuid.uuid4()
    folio_requisicion = _PREFIJO_FOLIO_REQUISICION + folio.removeprefix(_PREFIJO_FOLIO_ORDEN)

    conexion.execute(
        "INSERT INTO requisicion (id, folio, obra_id, tipo_partida_id, solicitante_id, estado, "
        "importe_solicitado, creado_en, actualizado_en) "
        "VALUES (%s, %s, %s, %s, %s, 'CONVERTIDA', %s, %s, %s)",
        (
            requisicion_id,
            folio_requisicion,
            obra_id,
            tipo_partida_id,
            solicitante_id,
            importe_total,
            INSTANTE,
            INSTANTE,
        ),
    )
    conexion.execute(
        "INSERT INTO orden_compra (id, folio, requisicion_id, obra_id, proveedor_id, importe, "
        "cancelada_en, motivo_cancelacion, creado_en) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            orden_id,
            folio,
            requisicion_id,
            obra_id,
            proveedor_id,
            importe_total,
            INSTANTE if cancelada else None,
            MOTIVO_DE_CANCELACION if cancelada else None,
            INSTANTE,
        ),
    )
    for (ordenada, recibida), importe in zip(cantidades, importes, strict=True):
        conexion.execute(
            "INSERT INTO orden_compra_renglon (id, orden_compra_id, insumo_id, cantidad_ordenada, "
            "cantidad_recibida, cantidad_excedente_autorizada, fecha_compromiso, costo_unitario, "
            "importe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                uuid.uuid4(),
                orden_id,
                insumo_id,
                ordenada,
                recibida,
                autorizado_extra,
                FECHA_COMPROMISO,
                COSTO_UNITARIO,
                importe,
            ),
        )
    return orden_id
