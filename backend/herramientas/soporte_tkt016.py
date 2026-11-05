"""Ayudantes de prueba para TKT-016 (explosión por tipo de partida)."""

from __future__ import annotations

from uuid import UUID

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, Ruta
from tipos_base import Cantidad, Dinero, Rendimiento

MUROS = UUID("00000000-0000-0000-0000-000000000001")
PLAFONES = UUID("00000000-0000-0000-0000-000000000002")

_RUTA_VACIA = Ruta(raiz=None, nivel=None, area=None, partida=None)


def concepto(
    *,
    fila: int,
    codigo: str,
    cantidad: str | None,
    area_nombre: str = "Área 1",
    precio_catalogo: str | None = None,
) -> ConceptoLeido:
    from cimenta.presupuesto.dominio.catalogo import NodoLeido, Profundidad

    ruta = Ruta(
        raiz=None,
        nivel=None,
        area=NodoLeido(fila=fila - 1, profundidad=Profundidad.AREA, nombre=area_nombre),
        partida=None,
    )
    return ConceptoLeido(
        fila=fila,
        codigo=codigo,
        descripcion=None,
        unidad="M2",
        cantidad=Cantidad(cantidad) if cantidad is not None else None,
        precio_unitario=Dinero(precio_catalogo) if precio_catalogo is not None else None,
        importe=None,
        ruta=ruta,
    )


def cargo(tipo: TipoCargo, importe: str) -> CargoLeido:
    return CargoLeido(
        fila=20,
        rotulo=tipo.value,
        tipo=tipo,
        porcentaje=None,
        base=None,
        importe=Dinero(importe),
    )


def insumo_material(
    *,
    clave: str,
    rendimiento: str,
    costo: str,
    unidad: str = "PZA",
    fila: int = 8,
) -> InsumoLeido:
    return InsumoLeido(
        fila=fila,
        tipo=TipoInsumo.MATERIAL,
        descripcion=clave,
        clave=clave,
        unidad=unidad,
        costo_unitario=Dinero(costo),
        rendimiento=Rendimiento(rendimiento),
        cargo=None,
    )


def insumo_mano_obra(*, clave: str, fila: int = 11) -> InsumoLeido:
    return InsumoLeido(
        fila=fila,
        tipo=TipoInsumo.MANO_OBRA,
        descripcion=clave,
        clave=clave,
        unidad="JORNAL",
        costo_unitario=None,
        rendimiento=None,
        cargo=None,
    )


def analisis(
    *,
    precio_unitario: str = "641.36",
    insumos: tuple[InsumoLeido, ...] = (),
    cargos_extra: tuple[CargoLeido, ...] = (),
    sin_utilidad: bool = False,
    sin_indirectos: bool = False,
    utilidad: str = "50.00",
    indirectos: str = "60.00",
    indirectos_sin_importe: bool = False,
    sin_precio: bool = False,
) -> AnalisisLeido:
    cargos: list[CargoLeido] = list(cargos_extra)
    if not sin_utilidad:
        cargos.append(cargo(TipoCargo.UTILIDAD, utilidad))
    if not sin_indirectos:
        if indirectos_sin_importe:
            cargos.append(
                CargoLeido(
                    fila=21,
                    rotulo="INDIRECTOS",
                    tipo=TipoCargo.INDIRECTOS,
                    porcentaje=None,
                    base=None,
                    importe=None,
                )
            )
        else:
            cargos.append(cargo(TipoCargo.INDIRECTOS, indirectos))
    cargos.append(cargo(TipoCargo.IVA, "40.00"))

    return AnalisisLeido(
        hoja="APU-TEST",
        cabecera=CabeceraLeida(
            fila_codigo=2,
            codigo="X",
            unidad="M2",
            fecha=None,
            analista=None,
            precio_unitario=Dinero(precio_unitario) if not sin_precio else None,
        ),
        insumos=insumos,
        cargos=tuple(cargos),
        fila_precio_unitario=25,
        precio_unitario=None if sin_precio else Dinero(precio_unitario),
        totales=TotalesAnalisis(None, None, None, None, None),
        hallazgos=(),
    )
