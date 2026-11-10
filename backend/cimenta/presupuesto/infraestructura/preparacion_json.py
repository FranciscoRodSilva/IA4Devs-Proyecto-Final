"""Serialización JSON de la preparación de importación, formato 1 (TKT-015a)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    AsociacionLeida,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    InsumoPorCrear,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, NodoLeido, Profundidad, Ruta
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

FORMATO_PREPARACION = 1


class FormatoPreparacionDesconocido(Exception):
    """El documento no es una preparación persistida en formato 1."""

    def __init__(self, formato: object) -> None:
        super().__init__(str(formato))
        self.formato = formato


def _cifra(valor: Cantidad | Dinero | Rendimiento | Porcentaje | None) -> str | None:
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


def _exigir_mapa(obj: object, contexto: str) -> Mapping[str, object]:
    if not isinstance(obj, Mapping):
        raise FormatoPreparacionDesconocido(contexto)
    return obj


def _exigir_lista(obj: object, contexto: str) -> list[object]:
    if not isinstance(obj, list):
        raise FormatoPreparacionDesconocido(contexto)
    return obj


def _exigir_cadena(obj: object, contexto: str) -> str:
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    return obj


def _exigir_cadena_opcional(obj: object | None) -> str | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(obj)
    return obj


def _exigir_entero(obj: object, contexto: str) -> int:
    if not isinstance(obj, int):
        raise FormatoPreparacionDesconocido(contexto)
    return obj


def _exigir_entero_opcional(obj: object | None) -> int | None:
    if obj is None:
        return None
    if not isinstance(obj, int):
        raise FormatoPreparacionDesconocido(obj)
    return obj


def _exigir_bool(obj: object, contexto: str) -> bool:
    if not isinstance(obj, bool):
        raise FormatoPreparacionDesconocido(contexto)
    return obj


def _cantidad_desde_json(obj: object | None, contexto: str) -> Cantidad | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    return Cantidad(obj)


def _dinero_desde_json(obj: object | None, contexto: str) -> Dinero | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    return Dinero(obj)


def _rendimiento_desde_json(obj: object | None, contexto: str) -> Rendimiento | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    return Rendimiento(obj)


def _porcentaje_desde_json(obj: object | None, contexto: str) -> Porcentaje | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    return Porcentaje(obj)


def _enum_desde_json[E: StrEnum](obj: object, enum: type[E], contexto: str) -> E | None:
    if obj is None:
        return None
    if not isinstance(obj, str):
        raise FormatoPreparacionDesconocido(contexto)
    try:
        return enum(obj)
    except ValueError as e:
        raise FormatoPreparacionDesconocido(obj) from e


def _nodo_desde_json(obj: object) -> NodoLeido:
    ctx = "nodo de preparación JSON"
    m = _exigir_mapa(obj, ctx)
    fila = _exigir_entero(m["fila"], ctx)
    profundidad = Profundidad(str(m["profundidad"]))
    nombre = m.get("nombre")
    if nombre is not None and not isinstance(nombre, str):
        raise FormatoPreparacionDesconocido(obj)
    return NodoLeido(fila=fila, profundidad=profundidad, nombre=nombre)


def _ruta_desde_json(obj: object, nodos_por_fila: Mapping[int, NodoLeido]) -> Ruta:
    ctx = "ruta de preparación JSON"
    m = _exigir_mapa(obj, ctx)

    def nodo_de_clave(clave: str) -> NodoLeido | None:
        raw = m.get(clave)
        if raw is None:
            return None
        fila = _exigir_entero(raw, f"{ctx} · {clave}")
        try:
            return nodos_por_fila[fila]
        except KeyError as e:
            raise FormatoPreparacionDesconocido(f"fila de ruta {clave}={fila}") from e

    return Ruta(
        raiz=nodo_de_clave("raiz"),
        nivel=nodo_de_clave("nivel"),
        area=nodo_de_clave("area"),
        partida=nodo_de_clave("partida"),
    )


def _concepto_desde_json(obj: object, nodos_por_fila: Mapping[int, NodoLeido]) -> ConceptoLeido:
    ctx = "concepto de preparación JSON"
    m = _exigir_mapa(obj, ctx)
    return ConceptoLeido(
        fila=_exigir_entero(m["fila"], ctx),
        codigo=_exigir_cadena(m["codigo"], ctx),
        descripcion=_exigir_cadena_opcional(m.get("descripcion")),
        unidad=_exigir_cadena_opcional(m.get("unidad")),
        cantidad=_cantidad_desde_json(m.get("cantidad"), ctx),
        precio_unitario=_dinero_desde_json(m.get("precio_unitario"), ctx),
        importe=_dinero_desde_json(m.get("importe"), ctx),
        ruta=_ruta_desde_json(m["ruta"], nodos_por_fila),
    )


def _insumo_analisis_desde_json(obj: object) -> InsumoLeido:
    ctx = "insumo de análisis JSON"
    m = _exigir_mapa(obj, ctx)
    return InsumoLeido(
        fila=_exigir_entero(m["fila"], ctx),
        tipo=TipoInsumo(str(m["tipo"])),
        descripcion=_exigir_cadena(m["descripcion"], ctx),
        clave=_exigir_cadena(m["clave"], ctx),
        unidad=_exigir_cadena_opcional(m.get("unidad")),
        costo_unitario=_dinero_desde_json(m.get("costo_unitario"), ctx),
        rendimiento=_rendimiento_desde_json(m.get("rendimiento"), ctx),
        cargo=_dinero_desde_json(m.get("cargo"), ctx),
    )


def _cargo_desde_json(obj: object) -> CargoLeido:
    ctx = "cargo de análisis JSON"
    m = _exigir_mapa(obj, ctx)
    return CargoLeido(
        fila=_exigir_entero(m["fila"], ctx),
        rotulo=_exigir_cadena(m["rotulo"], ctx),
        tipo=_enum_desde_json(m.get("tipo"), TipoCargo, ctx),
        porcentaje=_porcentaje_desde_json(m.get("porcentaje"), ctx),
        base=_dinero_desde_json(m.get("base"), ctx),
        importe=_dinero_desde_json(m.get("importe"), ctx),
    )


def _totales_desde_json(obj: object) -> TotalesAnalisis:
    ctx = "totales de análisis JSON"
    m = _exigir_mapa(obj, ctx)
    return TotalesAnalisis(
        material=_dinero_desde_json(m.get("material"), ctx),
        mano_obra=_dinero_desde_json(m.get("mano_obra"), ctx),
        costo_directo=_dinero_desde_json(m.get("costo_directo"), ctx),
        cargos=_dinero_desde_json(m.get("cargos"), ctx),
        precio_unitario=_dinero_desde_json(m.get("precio_unitario"), ctx),
    )


def _cabecera_desde_json(analisis: Mapping[str, object]) -> CabeceraLeida:
    ctx = "cabecera de análisis JSON"
    fecha = _exigir_cadena_opcional(analisis.get("fecha"))
    if fecha is not None:
        date.fromisoformat(fecha)
    return CabeceraLeida(
        fila_codigo=_exigir_entero_opcional(analisis.get("fila_codigo")),
        codigo=_exigir_cadena_opcional(analisis.get("codigo")),
        unidad=_exigir_cadena_opcional(analisis.get("unidad")),
        fecha=fecha,
        analista=_exigir_cadena_opcional(analisis.get("analista")),
        precio_unitario=_dinero_desde_json(analisis.get("precio_unitario_cabecera"), ctx),
    )


def _analisis_desde_json(obj: object) -> AnalisisLeido:
    ctx = "análisis JSON"
    m = _exigir_mapa(obj, ctx)
    cab = _cabecera_desde_json(m)
    insumos = tuple(_insumo_analisis_desde_json(i) for i in _exigir_lista(m["insumos"], ctx))
    cargos = tuple(_cargo_desde_json(c) for c in _exigir_lista(m["cargos"], ctx))
    return AnalisisLeido(
        hoja=_exigir_cadena(m["hoja"], ctx),
        cabecera=cab,
        insumos=insumos,
        cargos=cargos,
        fila_precio_unitario=_exigir_entero(m["fila_precio_unitario"], ctx),
        precio_unitario=_dinero_desde_json(m.get("precio_unitario"), ctx),
        totales=_totales_desde_json(m["totales"]),
        hallazgos=(),
    )


def _asociacion_desde_json(obj: object) -> AsociacionLeida:
    ctx = "asociación JSON"
    m = _exigir_mapa(obj, ctx)
    filas = _exigir_lista(m["filas_catalogo"], ctx)
    return AsociacionLeida(
        hoja=_exigir_cadena(m["hoja"], ctx),
        codigo=_exigir_cadena(m["codigo"], ctx),
        filas_catalogo=tuple(_exigir_entero(f, f"{ctx} · fila_catalogo") for f in filas),
    )


def _insumo_por_crear_desde_json(obj: object) -> InsumoPorCrear:
    ctx = "insumo por crear JSON"
    m = _exigir_mapa(obj, ctx)
    return InsumoPorCrear(
        clave=_exigir_cadena(m["clave"], ctx),
        descripcion=_exigir_cadena(m["descripcion"], ctx),
        unidad=_exigir_cadena(m["unidad"], ctx),
        tipo=TipoInsumo(str(m["tipo"])),
        creado_en_importacion=_exigir_bool(m["creado_en_importacion"], ctx),
    )


def preparacion_desde_json(documento: Mapping[str, object]) -> Preparacion:
    """Reconstruye una preparación persistida en formato 1. `hallazgos` quedan vacíos.

    Un formato distinto de 1, una clave ausente o un tipo inesperado lanzan
    `FormatoPreparacionDesconocido`; nunca `KeyError` ni `TypeError`.
    """
    if documento.get("formato") != FORMATO_PREPARACION:
        raise FormatoPreparacionDesconocido(documento.get("formato"))
    try:
        return _preparacion_formato_1(documento)
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise FormatoPreparacionDesconocido(documento.get("formato")) from error


def _preparacion_formato_1(documento: Mapping[str, object]) -> Preparacion:
    ctx = "preparación JSON"
    hoja = documento.get("hoja_catalogo")
    if hoja is not None and not isinstance(hoja, str):
        raise FormatoPreparacionDesconocido(hoja)
    nodos_lista = tuple(_nodo_desde_json(n) for n in _exigir_lista(documento["nodos"], ctx))
    nodos_por_fila = {n.fila: n for n in nodos_lista}
    if len(nodos_por_fila) != len(nodos_lista):
        raise FormatoPreparacionDesconocido("nodos con fila duplicada")
    conceptos = tuple(
        _concepto_desde_json(c, nodos_por_fila) for c in _exigir_lista(documento["conceptos"], ctx)
    )
    analisis = tuple(_analisis_desde_json(a) for a in _exigir_lista(documento["analisis"], ctx))
    asociaciones = tuple(
        _asociacion_desde_json(a) for a in _exigir_lista(documento["asociaciones"], ctx)
    )
    insumos_por_crear = tuple(
        _insumo_por_crear_desde_json(i) for i in _exigir_lista(documento["insumos_por_crear"], ctx)
    )
    return Preparacion(
        hoja_catalogo=hoja,
        nodos=nodos_lista,
        conceptos=conceptos,
        analisis=analisis,
        asociaciones=asociaciones,
        insumos_por_crear=insumos_por_crear,
        filas_leidas=_exigir_entero(documento["filas_leidas"], ctx),
        filas_validas=_exigir_entero(documento["filas_validas"], ctx),
        filas_rechazadas=_exigir_entero(documento["filas_rechazadas"], ctx),
    )


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
