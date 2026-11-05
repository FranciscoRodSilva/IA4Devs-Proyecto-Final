"""Ayudantes de prueba para TKT-016 (explosión por tipo de partida)."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from cimenta.presupuesto.dominio.analisis import (
    AnalisisDelLibro,
    AnalisisLeido,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido, Ruta
from cimenta.presupuesto.dominio.explosion import ConceptoAExplotar
from cimenta.presupuesto.dominio.lectura_analisis import normalizar_clave_insumo
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    LibroCatalogoPrueba,
    encabezado_eniti,
    metadatos_siete_filas,
)
from herramientas.soporte_tkt014 import escribir_hoja_apu_sintetica
from tipos_base import Cantidad, Dinero, Rendimiento

VARIABLE_ORACULO_EXPLOSION = "CIMENTA_EXPLOSION_UNION"

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


TIPO_POR_FILA_LIBRO_SINTETICO: dict[int, UUID] = {
    13: MUROS,
    14: MUROS,
    15: PLAFONES,
    16: PLAFONES,
}


def libro_explosion_sintetico(libro: LibroCatalogoPrueba) -> bytes:
    """Libro mínimo de CA-8 (design TKT-016): tres APU, catálogo ENITI y cuatro conceptos."""
    escribir_hoja_apu_sintetica(libro, "APU-A", codigo="A-01")
    escribir_hoja_apu_sintetica(
        libro,
        "APU-B",
        codigo="B-01",
        pie=Decimal("200"),
        celdas_rotas={
            (8, "E"): Decimal("12"),
            (8, "F"): Decimal("2.5"),
            (9, "A"): "MATERIAL TRES",
            (9, "E"): Decimal("7"),
            (9, "F"): Decimal("0.4"),
        },
    )
    escribir_hoja_apu_sintetica(
        libro,
        "APU-C",
        codigo="C-01",
        celdas_rotas={
            (8, "E"): Decimal("11"),
            (8, "F"): Decimal("3"),
        },
    )
    libro.nueva_hoja("RESUMEN")
    libro.nueva_hoja(HOJA_ENITI)
    metadatos_siete_filas(libro, HOJA_ENITI)
    encabezado_eniti(libro, HOJA_ENITI)
    libro.escribir_fila(HOJA_ENITI, 9, (None, "RAIZ SYN"))
    libro.escribir_fila(HOJA_ENITI, 10, (None, "NIVEL A"))
    libro.escribir_fila(HOJA_ENITI, 11, (None, "ZONA 1"))
    libro.escribir_fila(HOJA_ENITI, 12, (None, "TRABAJO X"))
    for fila, codigo, cantidad in (
        (13, "A-01", 10),
        (14, "B-01", 4),
        (15, "A-01", 6),
        (16, "C-01", 5),
    ):
        pu = 1
        libro.escribir_fila(
            HOJA_ENITI,
            fila,
            (codigo, f"Concepto {codigo}", "M2", cantidad, pu, cantidad * pu),
        )
    return libro.bytes()


def conceptos_a_explotar(
    libro: AnalisisDelLibro,
    tipo_por_fila: Mapping[int, UUID],
) -> tuple[ConceptoAExplotar, ...]:
    """Empareja conceptos del catálogo con su APU leído (soporte CA-8 / CA-10)."""
    analisis_por_hoja: dict[str, AnalisisLeido] = {a.hoja: a for a in libro.analisis}
    hoja_por_fila: dict[int, str] = {}
    for asoc in libro.asociaciones:
        for fila_cat in asoc.filas_catalogo:
            hoja_por_fila[fila_cat] = asoc.hoja

    items: list[ConceptoAExplotar] = []
    for concepto in libro.catalogo.conceptos:
        if concepto.cantidad is None:
            continue
        hoja = hoja_por_fila.get(concepto.fila)
        analisis_leido = analisis_por_hoja.get(hoja) if hoja is not None else None
        items.append(
            ConceptoAExplotar(
                concepto=concepto,
                tipo_partida_id=tipo_por_fila.get(concepto.fila),
                analisis=analisis_leido,
            )
        )
    return tuple(items)


@dataclass(frozen=True, slots=True)
class FilaOraculoExplosion:
    clave: str
    cantidad: Cantidad
    importe: Dinero


def leer_oraculo_explosion_union(ruta: Path) -> tuple[FilaOraculoExplosion, ...]:
    """CSV `clave,cantidad,importe` (P-1, CA-10)."""
    texto = ruta.read_text(encoding="utf-8")
    filas: list[FilaOraculoExplosion] = []
    for registro in csv.DictReader(io.StringIO(texto)):
        clave_raw = registro.get("clave")
        if clave_raw is None:
            continue
        clave = normalizar_clave_insumo(clave_raw)
        cantidad = Cantidad(registro["cantidad"])
        importe = Dinero(registro["importe"])
        filas.append(FilaOraculoExplosion(clave=clave, cantidad=cantidad, importe=importe))
    return tuple(filas)
