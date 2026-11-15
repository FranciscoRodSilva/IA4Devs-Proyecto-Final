"""Dominio de proveedores (TKT-029a, fila A1): TC-01 a TC-03.

Sin Docker ni base de datos. Prueba `cimenta/proveedores/dominio/proveedor.py`: la normalización
del RFC (supuesto 1 de la spec, `D-1` del diseño), la única regla de desactivación (CA-9) y los
días por omisión de RN-17.

Los símbolos de `cimenta.proveedores.dominio.proveedor` se importan dentro de cada caso, no al principio
del módulo, para que un fallo de importación afecte a un solo caso y no a la recolección.
"""

from __future__ import annotations


def test_hdu004_esc03_dominio_normaliza_el_rfc() -> None:
    """HDU-004 esc. 3 · CA-2 · supuesto 1 (D-1) — el RFC se recorta solo de espacios y pasa a
    mayúsculas antes de validar su forma; el salto de línea final se conserva para que el patrón
    lo rechace con 422 (CA-4)."""
    from cimenta.proveedores.dominio.proveedor import normalizar_rfc

    assert normalizar_rfc("  xaxx010101000 ") == "XAXX010101000"
    assert normalizar_rfc("ñaxx010101000") == "ÑAXX010101000"
    assert normalizar_rfc("XAXX010101000\n") == "XAXX010101000\n"


def test_hdu004_esc12_dominio_solo_activo_admite_desactivacion() -> None:
    """HDU-004 esc. 12 · CA-9 · RN-17 no aplica — solo un proveedor ACTIVO admite la desactivación;
    un DESACTIVADO o un BAJA la rechazan (el caso de uso responde 409 ESTADO_NO_PERMITE_OPERACION)."""
    from cimenta.proveedores.dominio.proveedor import EstadoProveedor, admite_desactivacion

    assert admite_desactivacion(EstadoProveedor.ACTIVO) is True
    assert admite_desactivacion(EstadoProveedor.DESACTIVADO) is False
    assert admite_desactivacion(EstadoProveedor.BAJA) is False


def test_hdu004_esc02_dominio_dias_por_omision_rn17() -> None:
    """HDU-004 esc. 2 · RN-17 · CA-1 — por omisión el corte es el día 4 (jueves) y el pago el día 6
    (sábado, ISO 8601 con 1 = lunes); los estados son exactamente ACTIVO, DESACTIVADO y BAJA."""
    from cimenta.proveedores.dominio.proveedor import (
        DIA_CORTE_POR_OMISION,
        DIA_PAGO_POR_OMISION,
        EstadoProveedor,
    )

    assert DIA_CORTE_POR_OMISION == 4
    assert DIA_PAGO_POR_OMISION == 6
    assert {estado.value for estado in EstadoProveedor} == {"ACTIVO", "DESACTIVADO", "BAJA"}
