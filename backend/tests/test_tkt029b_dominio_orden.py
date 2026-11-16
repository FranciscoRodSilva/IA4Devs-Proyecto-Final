"""Dominio de órdenes de compra (TKT-029b, fila F2): TC-09 a TC-13.

Sin Docker ni base de datos. Prueba `cimenta/compras/dominio/orden_compra.py`: el estado derivado de
una orden a partir de las cantidades de sus renglones (`docs/03` §1: el estado derivable se deriva) y
la definición de «pendiente» que decide el rechazo de la baja (CA-5 y CA-12 de la spec, supuestos 1 y 2
del diseño).
"""

from __future__ import annotations

from cimenta.compras.dominio.orden_compra import (
    CantidadesRenglon,
    EstadoOrden,
    esta_pendiente,
    estado_derivado,
)
from tipos_base import Cantidad


def _renglon(ordenada: str, recibida: str) -> CantidadesRenglon:
    """Construye un renglón desde cadenas: los importes nunca pasan por float."""
    return CantidadesRenglon(ordenada=Cantidad(ordenada), recibida=Cantidad(recibida))


def test_hdu004_esc12_tc09_un_renglon_sin_recibir_es_abierta() -> None:
    """HDU-004 esc. 12 · CA-5 — una orden con un renglón de 10 y nada recibido es ABIERTA: sí bloquea la baja."""
    assert estado_derivado((_renglon("10", "0"),)) == EstadoOrden.ABIERTA


def test_hdu004_esc12_tc09_dos_renglones_sin_recibir_son_abierta() -> None:
    """HDU-004 esc. 12 · CA-5 — una orden con dos renglones sin nada recibido (10 y 5) es ABIERTA."""
    assert estado_derivado((_renglon("10", "0"), _renglon("5", "0"))) == EstadoOrden.ABIERTA


def test_hdu004_esc12_tc10_renglon_recibido_en_parte_es_parcial() -> None:
    """HDU-004 esc. 12 · CA-12 esc. 2 — un renglón de 10 con 4 recibidos hace la orden PARCIAL."""
    assert estado_derivado((_renglon("10", "4"),)) == EstadoOrden.PARCIAL


def test_hdu004_esc12_tc10_renglon_completo_y_otro_sin_recibir_es_parcial() -> None:
    """HDU-004 esc. 12 · CA-12 esc. 2 — un renglón completo (10 recibidos de 10) y otro sin nada
    recibido (0 recibidos de 5) dejan la orden PARCIAL: hay algo recibido y algo por recibir."""
    assert estado_derivado((_renglon("10", "10"), _renglon("5", "0"))) == EstadoOrden.PARCIAL


def test_hdu004_esc12_tc11_renglon_completo_es_cerrada() -> None:
    """HDU-004 esc. 12 · CA-5 — un renglón recibido exactamente como se ordenó (10 de 10) es CERRADA: no bloquea."""
    assert estado_derivado((_renglon("10", "10"),)) == EstadoOrden.CERRADA


def test_hdu004_esc12_tc11_excedente_autorizado_es_cerrada() -> None:
    """HDU-004 esc. 12 · CA-5 — un renglón recibido por encima de lo ordenado (12 de 10, excedente autorizado)
    es CERRADA: no hay saldo por recibir y la baja procede."""
    assert estado_derivado((_renglon("10", "12"),)) == EstadoOrden.CERRADA


def test_hdu004_esc12_tc11_renglon_sin_saldo_con_renglon_en_cero_es_cerrada() -> None:
    """HDU-004 esc. 12 · CA-5 — un renglón completo (10 de 10) y otro con 0 pedido y 0 recibido no dejan
    saldo: la orden es CERRADA."""
    assert estado_derivado((_renglon("10", "10"), _renglon("0", "0"))) == EstadoOrden.CERRADA


def test_tkt029b_tc12_secuencia_vacia_es_cerrada() -> None:
    """CA-5 · supuesto 2 (D-2) — una orden sin renglones no tiene material por recibir: es CERRADA."""
    assert estado_derivado(()) == EstadoOrden.CERRADA


def test_tkt029b_tc13_recibido_igual_a_ordenada_en_otra_escala_es_cerrada() -> None:
    """CA-5 · escala de Decimal — 10.0000 recibido de 10 es CERRADA: la escala de la cadena no cambia la igualdad."""
    assert estado_derivado((_renglon("10", "10.0000"),)) == EstadoOrden.CERRADA


def test_tkt029b_tc13_recibido_a_una_diezmilesima_de_la_ordenada_es_parcial() -> None:
    """CA-5 · escala de Decimal — 9.9999 recibido de 10 es PARCIAL: queda una diezmilésima por recibir y
    la comparación no redondea."""
    assert estado_derivado((_renglon("10", "9.9999"),)) == EstadoOrden.PARCIAL


def test_tkt029b_tc13_esta_pendiente_solo_para_abierta_y_parcial() -> None:
    """CA-12 · la definición de pendiente — esta_pendiente es True solo para ABIERTA y PARCIAL, y el
    mapa cubre todos los miembros de EstadoOrden, así que un miembro nuevo sin decisión rompe el test."""
    assert {estado: esta_pendiente(estado) for estado in EstadoOrden} == {
        EstadoOrden.ABIERTA: True,
        EstadoOrden.PARCIAL: True,
        EstadoOrden.CERRADA: False,
    }
