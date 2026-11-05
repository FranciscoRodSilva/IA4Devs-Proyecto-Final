"""Serialización JSON de la preparación de importación, formato 1 (TKT-015a)."""

from __future__ import annotations

from enum import StrEnum

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    AsociacionLeida,
    CargoLeido,
    InsumoLeido,
    InsumoPorCrear,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, NodoLeido, Ruta
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

FORMATO_PREPARACION = 1

_TipoCifra = Cantidad | Dinero | Rendimiento | Porcentaje


def _cifra(valor: _TipoCifra | None) -> str | None:
    if valor is None:
        return None
    return format(valor.valor, "f")


def _enum(valor: StrEnum | None) -> str | None:
    return None if valor is None else valor.value


def _fila_nodo(nodo: NodoLeido | None) -> int | None:
    return None if nodo is None else nodo.fila


def _ruta_a_json(ruta: Ruta) -> dict[str, int | None]:
    return {
        "raiz": _fila_nodo(ruta.raiz),
        "nivel": _fila_nodo(ruta.nivel),
        "area": _fila_nodo(ruta.area),
        "partida": _fila_nodo(ruta.partida),
    }


def _nodo_a_json(nodo: NodoLeido) -> dict[str, object]:
    return {
        "fila": nodo.fila,
        "profundidad": nodo.profundidad.value,
        "nombre": nodo.nombre,
    }


def _concepto_a_json(concepto: ConceptoLeido) -> dict[str, object]:
    return {
        "fila": concepto.fila,
        "codigo": concepto.codigo,
        "descripcion": concepto.descripcion,
        "unidad": concepto.unidad,
        "cantidad": _cifra(concepto.cantidad),
        "precio_unitario": _cifra(concepto.precio_unitario),
        "importe": _cifra(concepto.importe),
        "ruta": _ruta_a_json(concepto.ruta),
    }


def _insumo_analisis_a_json(insumo: InsumoLeido) -> dict[str, object]:
    return {
        "fila": insumo.fila,
        "tipo": insumo.tipo.value,
        "descripcion": insumo.descripcion,
        "clave": insumo.clave,
        "unidad": insumo.unidad,
        "costo_unitario": _cifra(insumo.costo_unitario),
        "rendimiento": _cifra(insumo.rendimiento),
        "cargo": _cifra(insumo.cargo),
    }


def _cargo_a_json(cargo: CargoLeido) -> dict[str, object]:
    return {
        "fila": cargo.fila,
        "rotulo": cargo.rotulo,
        "tipo": _enum(cargo.tipo),
        "porcentaje": _cifra(cargo.porcentaje),
        "base": _cifra(cargo.base),
        "importe": _cifra(cargo.importe),
    }


def _totales_a_json(totales: TotalesAnalisis) -> dict[str, str | None]:
    return {
        "material": _cifra(totales.material),
        "mano_obra": _cifra(totales.mano_obra),
        "costo_directo": _cifra(totales.costo_directo),
        "cargos": _cifra(totales.cargos),
        "precio_unitario": _cifra(totales.precio_unitario),
    }


def _analisis_a_json(analisis: AnalisisLeido) -> dict[str, object]:
    cab = analisis.cabecera
    return {
        "hoja": analisis.hoja,
        "fila_codigo": cab.fila_codigo,
        "codigo": cab.codigo,
        "unidad": cab.unidad,
        "fecha": cab.fecha,
        "analista": cab.analista,
        "precio_unitario_cabecera": _cifra(cab.precio_unitario),
        "precio_unitario": _cifra(analisis.precio_unitario),
        "fila_precio_unitario": analisis.fila_precio_unitario,
        "insumos": [_insumo_analisis_a_json(i) for i in analisis.insumos],
        "cargos": [_cargo_a_json(c) for c in analisis.cargos],
        "totales": _totales_a_json(analisis.totales),
    }


def _asociacion_a_json(asociacion: AsociacionLeida) -> dict[str, object]:
    return {
        "hoja": asociacion.hoja,
        "codigo": asociacion.codigo,
        "filas_catalogo": list(asociacion.filas_catalogo),
    }


def _insumo_por_crear_a_json(insumo: InsumoPorCrear) -> dict[str, object]:
    return {
        "clave": insumo.clave,
        "descripcion": insumo.descripcion,
        "unidad": insumo.unidad,
        "tipo": insumo.tipo.value,
        "creado_en_importacion": insumo.creado_en_importacion,
    }


def preparacion_a_json(preparacion: Preparacion) -> dict[str, object]:
    """Convierte una preparación de dominio al formato JSON 1 (cadena en cifras, null en ausentes)."""
    return {
        "formato": FORMATO_PREPARACION,
        "hoja_catalogo": preparacion.hoja_catalogo,
        "nodos": [_nodo_a_json(n) for n in preparacion.nodos],
        "conceptos": [_concepto_a_json(c) for c in preparacion.conceptos],
        "analisis": [_analisis_a_json(a) for a in preparacion.analisis],
        "asociaciones": [_asociacion_a_json(a) for a in preparacion.asociaciones],
        "insumos_por_crear": [_insumo_por_crear_a_json(i) for i in preparacion.insumos_por_crear],
        "filas_leidas": preparacion.filas_leidas,
        "filas_validas": preparacion.filas_validas,
        "filas_rechazadas": preparacion.filas_rechazadas,
    }
