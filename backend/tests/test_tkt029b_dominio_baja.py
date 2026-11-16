"""Dominio de la baja de proveedores (TKT-029b, entrega b, fila F4): TC-20 a TC-22.

Sin Docker ni base de datos. Prueba `rechazo_de_baja` de `cimenta/proveedores/dominio/proveedor.py`,
la regla pura que decide si un proveedor admite la baja: un proveedor en `BAJA` es terminal
(`CA-7`), uno con órdenes de compra pendientes no puede darse de baja (`CA-3`, `CA-4`), y el
estado terminal precede a las órdenes pendientes.
"""

from __future__ import annotations

from cimenta.proveedores.dominio.proveedor import EstadoProveedor, RechazoBaja, rechazo_de_baja


def test_hdu004_esc12_dominio_baja_sin_ordenes_pendientes_no_se_rechaza() -> None:
    """HDU-004 esc. 12 · CA-1 · CA-2 — un proveedor ACTIVO o DESACTIVADO sin órdenes pendientes
    admite la baja: `rechazo_de_baja` devuelve None."""
    assert rechazo_de_baja(EstadoProveedor.ACTIVO, 0) is None
    assert rechazo_de_baja(EstadoProveedor.DESACTIVADO, 0) is None


def test_hdu004_esc12_dominio_baja_es_estado_terminal() -> None:
    """HDU-004 esc. 12 · CA-7 — un proveedor en BAJA se rechaza con ESTADO_TERMINAL, haya o no
    órdenes pendientes (el estado terminal precede a las órdenes pendientes)."""
    assert rechazo_de_baja(EstadoProveedor.BAJA, 0) is RechazoBaja.ESTADO_TERMINAL
    assert rechazo_de_baja(EstadoProveedor.BAJA, 3) is RechazoBaja.ESTADO_TERMINAL


def test_hdu004_esc12_dominio_ordenes_pendientes_impiden_la_baja() -> None:
    """HDU-004 esc. 12 · CA-3 · CA-4 — un proveedor ACTIVO o DESACTIVADO con al menos una orden
    pendiente se rechaza con ORDENES_PENDIENTES, desde la primera orden (borde 1)."""
    assert rechazo_de_baja(EstadoProveedor.ACTIVO, 1) is RechazoBaja.ORDENES_PENDIENTES
    assert rechazo_de_baja(EstadoProveedor.DESACTIVADO, 2) is RechazoBaja.ORDENES_PENDIENTES
