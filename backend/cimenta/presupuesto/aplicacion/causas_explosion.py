"""Las causas de una explosión rechazada tal como viajan en el `detalle` (TKT-017, a3 y b1).

La comparten la confirmación y el congelado: una causa por (concepto, causa, clave de insumo, tipo de
partida), en orden de aparición.
"""

from __future__ import annotations

from cimenta.presupuesto.dominio.explosion import CausaRechazoExplosion


def detalle_de_causas(causas: tuple[CausaRechazoExplosion, ...]) -> list[dict[str, object]]:
    vistas: set[tuple[object, ...]] = set()
    detalle: list[dict[str, object]] = []
    for causa in causas:
        clave = (causa.codigo_concepto, causa.motivo, causa.clave_insumo, causa.tipo_partida_id)
        if clave in vistas:
            continue
        vistas.add(clave)
        detalle.append(
            {
                "concepto": causa.codigo_concepto,
                "causa": causa.motivo.value,
                "clave_insumo": causa.clave_insumo,
                "tipo_partida_id": causa.tipo_partida_id,
            }
        )
    return detalle
