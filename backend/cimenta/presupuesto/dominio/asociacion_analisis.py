"""Asociación de hojas APU con el catálogo e insumos por crear (TKT-014b).

HDU-001 esc. 5, 7, 9 y 10; M5, M6. Sin framework ni E/S.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from cimenta.presupuesto.dominio.analisis import (
    AnalisisDelLibro,
    AnalisisLeido,
    AsociacionLeida,
    InsumoPorCrear,
    TipoInsumo,
)
from cimenta.presupuesto.dominio.catalogo import (
    UNIDADES_ADMITIDAS,
    CatalogoLeido,
    CausaHallazgo,
    Hallazgo,
)
from cimenta.presupuesto.dominio.lectura_analisis import normalizar_codigo


def asociar_analisis(
    analisis: Sequence[AnalisisLeido],
    catalogo: CatalogoLeido,
) -> tuple[tuple[AsociacionLeida, ...], tuple[str, ...], tuple[Hallazgo, ...]]:
    """Implementa M5. Asociaciones, códigos del catálogo sin APU y hallazgos."""
    indice: dict[str, list[int]] = defaultdict(list)
    orden_codigos: list[str] = []
    vistos_indice: set[str] = set()
    for concepto in catalogo.conceptos:
        clave = normalizar_codigo(concepto.codigo)
        if clave is None:
            continue
        indice[clave].append(concepto.fila)
        if clave not in vistos_indice:
            vistos_indice.add(clave)
            orden_codigos.append(clave)

    hojas_por_codigo: dict[str, list[str]] = defaultdict(list)
    for item in analisis:
        codigo = item.cabecera.codigo
        if codigo is not None:
            hojas_por_codigo[codigo].append(item.hoja)

    asociaciones: list[AsociacionLeida] = []
    hallazgos: list[Hallazgo] = []
    codigos_con_analisis: set[str] = set()

    for item in analisis:
        hoja = item.hoja
        cab = item.cabecera
        codigo = cab.codigo
        if codigo is None:
            if cab.fila_codigo is None:
                hallazgos.append(
                    Hallazgo(
                        causa=CausaHallazgo.ANALISIS_SIN_CODIGO,
                        hoja=hoja,
                        fila=None,
                        columna=None,
                        valor_original=None,
                        detalle="sin rótulo «código»",
                    )
                )
            else:
                hallazgos.append(
                    Hallazgo(
                        causa=CausaHallazgo.ANALISIS_SIN_CODIGO,
                        hoja=hoja,
                        fila=cab.fila_codigo,
                        columna="C",
                        valor_original=None,
                    )
                )
            continue

        codigos_con_analisis.add(codigo)
        hojas = hojas_por_codigo[codigo]
        if len(hojas) > 1:
            otras = ", ".join(n for n in hojas if n != hoja)
            hallazgos.append(
                Hallazgo(
                    causa=CausaHallazgo.CODIGO_EN_VARIAS_HOJAS,
                    hoja=hoja,
                    fila=cab.fila_codigo,
                    columna="C",
                    valor_original=codigo,
                    detalle=otras,
                )
            )
            continue

        filas_cat = indice.get(codigo)
        if filas_cat is None:
            hallazgos.append(
                Hallazgo(
                    causa=CausaHallazgo.CODIGO_SIN_CONCEPTO,
                    hoja=hoja,
                    fila=cab.fila_codigo,
                    columna="C",
                    valor_original=codigo,
                )
            )
            continue

        asociaciones.append(
            AsociacionLeida(hoja=hoja, codigo=codigo, filas_catalogo=tuple(filas_cat))
        )

    sin_analisis = tuple(c for c in orden_codigos if c not in codigos_con_analisis)
    return tuple(asociaciones), sin_analisis, tuple(hallazgos)


def _ocurrencias_admitidas(
    analisis: Sequence[AnalisisLeido],
) -> list[tuple[str, str, str, TipoInsumo, int, str]]:
    resultado: list[tuple[str, str, str, TipoInsumo, int, str]] = []
    for item in analisis:
        for insumo in item.insumos:
            if insumo.unidad is None or insumo.unidad not in UNIDADES_ADMITIDAS:
                continue
            resultado.append(
                (
                    insumo.clave,
                    insumo.descripcion,
                    insumo.unidad,
                    insumo.tipo,
                    insumo.fila,
                    item.hoja,
                )
            )
    return resultado


def proponer_insumos(
    analisis: Sequence[AnalisisLeido],
    insumos_existentes: Mapping[str, str],
) -> tuple[tuple[InsumoPorCrear, ...], tuple[Hallazgo, ...]]:
    """Implementa M6. Insumos por crear y hallazgos de conflicto."""
    ocurrencias = _ocurrencias_admitidas(analisis)
    hallazgos: list[Hallazgo] = []
    propuestos: list[InsumoPorCrear] = []
    vistos_clave: set[str] = set()

    claves_orden: list[str] = []
    for clave, _, _, _, _, _ in ocurrencias:
        if clave not in vistos_clave:
            vistos_clave.add(clave)
            claves_orden.append(clave)

    for clave in claves_orden:
        ocurrencias_clave = [o for o in ocurrencias if o[0] == clave]
        unidades = {o[2] for o in ocurrencias_clave}
        tipos = {o[3] for o in ocurrencias_clave}
        desc = ocurrencias_clave[0][1].strip()
        unidad_primera = ocurrencias_clave[0][2]
        tipo_primero = ocurrencias_clave[0][3]

        if clave in insumos_existentes:
            unidad_existente = insumos_existentes[clave]
            for _c, _d, unidad, _t, fila, hoja in ocurrencias_clave:
                if unidad != unidad_existente:
                    hallazgos.append(
                        Hallazgo(
                            causa=CausaHallazgo.UNIDAD_EN_CONFLICTO,
                            hoja=hoja,
                            fila=fila,
                            columna="D",
                            valor_original=unidad,
                            detalle=f"{clave}: existente {unidad_existente}",
                        )
                    )
            continue

        if len(unidades) > 1:
            detalle_partes = "; ".join(
                f"{hoja} fila {fila} {unidad}"
                for _c, _d, unidad, _t, fila, hoja in ocurrencias_clave
            )
            detalle = f"{clave}: {detalle_partes}"
            for _c, _d, unidad, _t, fila, hoja in ocurrencias_clave:
                hallazgos.append(
                    Hallazgo(
                        causa=CausaHallazgo.UNIDAD_EN_CONFLICTO,
                        hoja=hoja,
                        fila=fila,
                        columna="D",
                        valor_original=unidad,
                        detalle=detalle,
                    )
                )
            continue

        if len(tipos) > 1:
            detalle_partes = "; ".join(
                f"{hoja} fila {fila} {tipo.value}"
                for _c, _d, _u, tipo, fila, hoja in ocurrencias_clave
            )
            detalle = f"{clave}: {detalle_partes}"
            for _c, _d, _u, tipo, fila, hoja in ocurrencias_clave:
                hallazgos.append(
                    Hallazgo(
                        causa=CausaHallazgo.TIPO_EN_CONFLICTO,
                        hoja=hoja,
                        fila=fila,
                        columna="A",
                        valor_original=tipo.value,
                        detalle=detalle,
                    )
                )
            continue

        propuestos.append(
            InsumoPorCrear(
                clave=clave,
                descripcion=desc,
                unidad=unidad_primera,
                tipo=tipo_primero,
            )
        )

    return tuple(propuestos), tuple(hallazgos)


def consolidar_libro(
    catalogo: CatalogoLeido,
    analisis: Sequence[AnalisisLeido],
    insumos_existentes: Mapping[str, str],
) -> AnalisisDelLibro:
    """Arma el resultado del libro: asociación primero, luego insumos."""
    asociaciones, sin_analisis, hall_asoc = asociar_analisis(analisis, catalogo)
    insumos, hall_insumos = proponer_insumos(analisis, insumos_existentes)
    return AnalisisDelLibro(
        catalogo=catalogo,
        analisis=tuple(analisis),
        asociaciones=asociaciones,
        codigos_sin_analisis=sin_analisis,
        insumos_por_crear=insumos,
        hallazgos=hall_asoc + hall_insumos,
    )
