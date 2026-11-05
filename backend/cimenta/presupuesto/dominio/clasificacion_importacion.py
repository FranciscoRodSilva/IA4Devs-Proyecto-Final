"""Clasificación de hallazgos del lector en tipos de error de importación (TKT-015a).

HDU-001 esc. 6, 7, 8, 9, 27 y 28; PA-15.1 y PA-15.2. Sin efectos secundarios.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from cimenta.presupuesto.dominio.analisis import AnalisisDelLibro, AnalisisLeido
from cimenta.presupuesto.dominio.catalogo import (
    ERRORES_DE_FORMULA,
    CatalogoLeido,
    CausaHallazgo,
    ConceptoLeido,
    Hallazgo,
)
from cimenta.presupuesto.dominio.importacion import ErrorImportacion, TipoErrorImportacion
from cimenta.presupuesto.dominio.lectura_analisis import normalizar_clave_insumo, normalizar_codigo

_COLUMNA_RENDIMIENTO = "F"

_CAUSAS_SIN_UBICACION_EN_ERROR: frozenset[CausaHallazgo] = frozenset(
    {
        CausaHallazgo.HOJA_NO_LOCALIZADA,
        CausaHallazgo.HOJA_AMBIGUA,
        CausaHallazgo.ENCABEZADO_NO_LOCALIZADO,
        CausaHallazgo.COLUMNA_NO_LOCALIZADA,
        CausaHallazgo.NINGUN_CONCEPTO,
    }
)

ESTRUCTURA_MINIMA_DEL_CATALOGO = (
    "Se espera una sola hoja cuyo nombre empiece por «Catálogo», con una fila de encabezado "
    "que lleve «Código» en la columna A y la descripción en la B, las columnas «Unidad», "
    "«Cantidad», «P.U.» e «Importe», y debajo al menos una fila con código."
)

TIPO_POR_CAUSA: Mapping[CausaHallazgo, TipoErrorImportacion] = MappingProxyType(
    {
        CausaHallazgo.HOJA_NO_LOCALIZADA: TipoErrorImportacion.SIN_CONCEPTOS,
        CausaHallazgo.HOJA_AMBIGUA: TipoErrorImportacion.SIN_CONCEPTOS,
        CausaHallazgo.ENCABEZADO_NO_LOCALIZADO: TipoErrorImportacion.SIN_CONCEPTOS,
        CausaHallazgo.COLUMNA_NO_LOCALIZADA: TipoErrorImportacion.SIN_CONCEPTOS,
        CausaHallazgo.NINGUN_CONCEPTO: TipoErrorImportacion.SIN_CONCEPTOS,
        CausaHallazgo.ERROR_DE_FORMULA: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.NO_ES_NUMERO: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.VALOR_AUSENTE: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.UNIDAD_NO_RECONOCIDA: TipoErrorImportacion.UNIDAD_DESCONOCIDA,
        CausaHallazgo.NOMBRE_ILEGIBLE: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.CONCEPTO_SIN_PARTIDA: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.PROFUNDIDAD_EXCEDIDA: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.VALOR_NEGATIVO: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.FECHA_NO_RECONOCIDA: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.CARGO_DESCONOCIDO: TipoErrorImportacion.UNIDAD_DESCONOCIDA,
        CausaHallazgo.PU_NO_CUADRA: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.PU_NO_VERIFICABLE: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.ANALISIS_SIN_CODIGO: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.CODIGO_EN_VARIAS_HOJAS: TipoErrorImportacion.DUPLICADO,
        CausaHallazgo.CODIGO_SIN_CONCEPTO: TipoErrorImportacion.REF_ROTA,
        CausaHallazgo.UNIDAD_EN_CONFLICTO: TipoErrorImportacion.UNIDAD_DESCONOCIDA,
        CausaHallazgo.TIPO_EN_CONFLICTO: TipoErrorImportacion.DUPLICADO,
    }
)


def _texto(valor: str | int | None) -> str:
    return "sin dato" if valor is None else str(valor)


def _enumerar(elementos: Sequence[str]) -> str:
    lista = list(elementos)
    if len(lista) == 0:
        return ""
    if len(lista) == 1:
        return lista[0]
    if len(lista) == 2:
        return f"{lista[0]} y {lista[1]}"
    return ", ".join(lista[:-1]) + f" y {lista[-1]}"


def _plantilla_base(causa: CausaHallazgo, hallazgo: Hallazgo) -> str:
    hoja = _texto(hallazgo.hoja)
    fila = _texto(hallazgo.fila)
    valor = _texto(hallazgo.valor_original)
    detalle = hallazgo.detalle

    match causa:
        case CausaHallazgo.HOJA_NO_LOCALIZADA:
            det = f" ({detalle})" if detalle else ""
            cuerpo = f"El libro no tiene una hoja de catálogo reconocible{det}."
        case CausaHallazgo.HOJA_AMBIGUA:
            cuerpo = (
                f"El libro tiene más de una hoja que parece de catálogo ({_texto(detalle)}); "
                "debe haber una sola."
            )
        case CausaHallazgo.ENCABEZADO_NO_LOCALIZADO:
            cuerpo = (
                f"La hoja «{hoja}» no trae ninguna fila de concepto: "
                "ninguna fila tiene «Código» en la columna A."
            )
        case CausaHallazgo.COLUMNA_NO_LOCALIZADA:
            cuerpo = (
                f"La hoja «{hoja}» no trae ninguna fila de concepto legible: "
                f"en el encabezado de la fila {fila}, la columna «{valor}» {_texto(detalle)}."
            )
        case CausaHallazgo.NINGUN_CONCEPTO:
            cuerpo = (
                f"La hoja «{hoja}» no trae ninguna fila de concepto: "
                f"debajo del encabezado de la fila {fila} no hay ninguna fila con código."
            )
        case CausaHallazgo.ERROR_DE_FORMULA:
            cuerpo = (
                f"La celda trae el error de fórmula «{valor}»: "
                "su valor no se puede leer y no se importa como cero."
            )
        case CausaHallazgo.NO_ES_NUMERO:
            cuerpo = f"La celda trae «{valor}» donde se esperaba un número."
        case CausaHallazgo.VALOR_AUSENTE:
            extra = f" ({detalle})" if detalle else ""
            cuerpo = f"La celda está vacía y se esperaba un valor{extra}."
        case CausaHallazgo.UNIDAD_NO_RECONOCIDA:
            cuerpo = (
                f"La unidad «{valor}» no está entre las ocho admitidas: "
                "M2, ML, PZA, KG, CAJA, SACO, ROLLO y JORNAL."
            )
        case CausaHallazgo.NOMBRE_ILEGIBLE:
            cuerpo = f"El nombre del nivel, área o partida trae el error de fórmula «{valor}»."
        case CausaHallazgo.CONCEPTO_SIN_PARTIDA:
            cuerpo = (
                "El concepto no cuelga de ninguna partida: su referencia a la partida que lo "
                "agrupa no existe, porque falta la fila de título."
            )
        case CausaHallazgo.PROFUNDIDAD_EXCEDIDA:
            cuerpo = (
                f"La fila de título «{valor}» excede los cuatro niveles de la jerarquía "
                "(raíz, nivel, área y partida): su referencia a un nivel de la jerarquía no existe."
            )
        case CausaHallazgo.VALOR_NEGATIVO:
            cuerpo = (
                f"La celda trae el valor negativo {valor}; "
                "el análisis de precio unitario no admite cifras negativas."
            )
        case CausaHallazgo.FECHA_NO_RECONOCIDA:
            cuerpo = f"La fecha «{valor}» no tiene la forma de una fecha."
        case CausaHallazgo.CARGO_DESCONOCIDO:
            cuerpo = (
                f"El cargo «{valor}» no está en el catálogo de cargos: herramienta menor, "
                "andamiaje, desperdicio, viáticos, IVA, indirectos y utilidad."
            )
        case CausaHallazgo.PU_NO_CUADRA:
            cuerpo = (
                f"El precio unitario del análisis no coincide con la suma de sus insumos y "
                f"cargos: {_texto(detalle)}."
            )
        case CausaHallazgo.PU_NO_VERIFICABLE:
            cuerpo = f"El precio unitario del análisis no se puede verificar: {_texto(detalle)}."
        case CausaHallazgo.ANALISIS_SIN_CODIGO:
            cuerpo = (
                f"La hoja «{hoja}» es un análisis de precio unitario sin código: "
                "no se puede asociar a ningún concepto."
            )
        case CausaHallazgo.CODIGO_EN_VARIAS_HOJAS:
            cuerpo = (
                f"El código «{valor}» tiene análisis también en la hoja {_texto(detalle)}: "
                "un concepto solo puede tener un análisis de precio unitario."
            )
        case CausaHallazgo.CODIGO_SIN_CONCEPTO:
            cuerpo = (
                f"El análisis de la hoja «{hoja}» tiene el código «{valor}», "
                "que no está en el catálogo: su referencia a un concepto no existe."
            )
        case CausaHallazgo.UNIDAD_EN_CONFLICTO:
            cuerpo = (
                f"El insumo aparece con unidades distintas ({_texto(detalle)}): "
                "un insumo tiene una sola unidad."
            )
        case CausaHallazgo.TIPO_EN_CONFLICTO:
            cuerpo = (
                f"El mismo insumo aparece como material y como mano de obra ({_texto(detalle)}): "
                "un insumo tiene un solo tipo."
            )
        case _:
            raise KeyError(causa)

    if causa in _CAUSAS_SIN_UBICACION_EN_ERROR:
        cuerpo = f"{cuerpo} {ESTRUCTURA_MINIMA_DEL_CATALOGO}"
    return cuerpo


def clasificar_hallazgo(hallazgo: Hallazgo, *, es_rendimiento: bool = False) -> ErrorImportacion:
    """Traduce un hallazgo del lector a un error persistible de importación."""
    causa = hallazgo.causa
    if causa not in TIPO_POR_CAUSA:
        raise KeyError(causa)

    if es_rendimiento and causa is CausaHallazgo.VALOR_AUSENTE:
        tipo = TipoErrorImportacion.RENDIMIENTO_AUSENTE
        cuerpo = (
            "El insumo no trae rendimiento: sin él no se puede calcular cuánto consume el concepto."
        )
    else:
        tipo = TIPO_POR_CAUSA[causa]
        cuerpo = _plantilla_base(causa, hallazgo)

    mensaje = f"{cuerpo} (causa: {causa.value})"

    if causa in _CAUSAS_SIN_UBICACION_EN_ERROR:
        hoja = hallazgo.hoja
        fila = None
        columna = None
    elif (
        causa is CausaHallazgo.VALOR_AUSENTE
        and hallazgo.detalle is not None
        and "cabecera" in hallazgo.detalle
    ):
        hoja = None
        fila = None
        columna = None
    else:
        hoja = hallazgo.hoja
        fila = hallazgo.fila
        columna = hallazgo.columna

    return ErrorImportacion(
        tipo=tipo,
        hoja=hoja,
        fila=fila,
        columna=columna,
        mensaje=mensaje,
        valor_original=hallazgo.valor_original,
    )


def es_celda_de_rendimiento(hallazgo: Hallazgo, analisis: AnalisisLeido) -> bool:
    """HDU-001 esc. 28 — VALOR_AUSENTE en la celda F de un insumo sin rendimiento."""
    if hallazgo not in analisis.hallazgos:
        return False
    if hallazgo.causa is not CausaHallazgo.VALOR_AUSENTE:
        return False
    if hallazgo.columna != _COLUMNA_RENDIMIENTO:
        return False
    if hallazgo.fila is None:
        return False
    for insumo in analisis.insumos:
        if insumo.fila == hallazgo.fila and insumo.rendimiento is None:
            return True
    return False


@dataclass(frozen=True, slots=True)
class Clasificacion:
    errores: tuple[ErrorImportacion, ...]
    filas_rechazadas: frozenset[int]
    hojas_rechazadas: frozenset[str]


def _primera_fila_del_codigo(catalogo: CatalogoLeido, codigo: str) -> int:
    norm = normalizar_codigo(codigo)
    filas = [c.fila for c in catalogo.conceptos if normalizar_codigo(c.codigo) == norm]
    if not filas:
        raise ValueError(f"código {codigo!r} no está en el catálogo")
    return min(filas)


def errores_sin_apu(
    catalogo: CatalogoLeido,
    codigos_sin_analisis: Sequence[str],
) -> tuple[ErrorImportacion, ...]:
    """HDU-001 esc. 7 · CA-4 — un SIN_APU por código sin hoja de APU."""
    hoja = catalogo.hoja or "CATALOGO"
    resultado: list[ErrorImportacion] = []
    for codigo in codigos_sin_analisis:
        fila = _primera_fila_del_codigo(catalogo, codigo)
        resultado.append(
            ErrorImportacion(
                tipo=TipoErrorImportacion.SIN_APU,
                hoja=hoja,
                fila=fila,
                columna="A",
                mensaje=(
                    f"El concepto con código «{codigo}» no tiene hoja de análisis de precio unitario. "
                    "Sin ese análisis no se puede calcular la explosión de insumos de ese concepto."
                ),
                valor_original=codigo,
            )
        )
    return tuple(resultado)


def _mensaje_duplicado_catalogo(codigo: str, conceptos: Sequence[ConceptoLeido]) -> str:
    grupos: dict[str, list[ConceptoLeido]] = defaultdict(list)
    for concepto in sorted(conceptos, key=lambda c: c.fila):
        if concepto.descripcion is None:
            continue
        clave = normalizar_clave_insumo(concepto.descripcion)
        grupos[clave].append(concepto)
    ordenados = sorted(grupos.values(), key=lambda g: g[0].fila)
    partes_grupo: list[str] = []
    for grupo in ordenados:
        texto = grupo[0].descripcion.strip() if grupo[0].descripcion else ""
        filas_g = [c.fila for c in grupo]
        if len(filas_g) == 1:
            partes_grupo.append(f"«{texto}» en la fila {filas_g[0]}")
        else:
            partes_grupo.append(f"«{texto}» en las filas {_enumerar([str(f) for f in filas_g])}")
    todas_filas = sorted(c.fila for c in conceptos if c.descripcion is not None)
    return (
        f"El código «{codigo}» aparece con descripciones distintas en las filas "
        f"{_enumerar([str(f) for f in todas_filas])}: {_enumerar(partes_grupo)}. "
        "Un código identifica un solo concepto."
    )


def detectar_duplicados(catalogo: CatalogoLeido) -> tuple[ErrorImportacion, ...]:
    """HDU-001 esc. 9 · CA-7 — mismo código con descripciones normalizadas distintas."""
    por_codigo: dict[str, list[ConceptoLeido]] = defaultdict(list)
    for concepto in catalogo.conceptos:
        if concepto.codigo in ERRORES_DE_FORMULA:
            continue
        if concepto.descripcion is None:
            continue
        clave_codigo = normalizar_codigo(concepto.codigo)
        if clave_codigo is None:
            continue
        por_codigo[clave_codigo].append(concepto)

    hoja = catalogo.hoja or "CATALOGO"
    errores: list[ErrorImportacion] = []
    for codigo in sorted(por_codigo, key=lambda c: min(x.fila for x in por_codigo[c])):
        conceptos = por_codigo[codigo]
        claves_desc = {
            normalizar_clave_insumo(c.descripcion) for c in conceptos if c.descripcion is not None
        }
        if len(claves_desc) <= 1:
            continue
        fila = min(c.fila for c in conceptos)
        errores.append(
            ErrorImportacion(
                tipo=TipoErrorImportacion.DUPLICADO,
                hoja=hoja,
                fila=fila,
                columna="A",
                mensaje=_mensaje_duplicado_catalogo(codigo, conceptos),
                valor_original=codigo,
            )
        )
    return tuple(errores)


def _filas_y_hojas_rechazadas(
    errores: Sequence[ErrorImportacion],
    catalogo: CatalogoLeido,
) -> tuple[frozenset[int], frozenset[str]]:
    hoja_cat = catalogo.hoja
    filas: set[int] = set()
    hojas: set[str] = set()
    filas_concepto = {c.fila for c in catalogo.conceptos}

    def filas_del_codigo(codigo: str) -> None:
        norm = normalizar_codigo(codigo)
        for c in catalogo.conceptos:
            if normalizar_codigo(c.codigo) == norm:
                filas.add(c.fila)

    for error in errores:
        if (error.tipo is TipoErrorImportacion.SIN_APU and error.valor_original) or (
            error.tipo is TipoErrorImportacion.DUPLICADO
            and error.hoja == hoja_cat
            and error.valor_original
        ):
            filas_del_codigo(error.valor_original)
        elif error.hoja is not None and error.hoja != hoja_cat:
            hojas.add(error.hoja)
        elif error.hoja == hoja_cat and error.fila is not None:
            filas.add(error.fila)

    return frozenset(filas & filas_concepto), frozenset(hojas)


def clasificar_libro(libro: AnalisisDelLibro) -> Clasificacion:
    """HDU-001 esc. 6–9 · M1 — clasifica hallazgos, duplicados y códigos sin APU."""
    catalogo = libro.catalogo
    errores: list[ErrorImportacion] = []

    for hallazgo in catalogo.hallazgos:
        errores.append(clasificar_hallazgo(hallazgo))

    errores.extend(detectar_duplicados(catalogo))
    errores.extend(errores_sin_apu(catalogo, libro.codigos_sin_analisis))

    for analisis in libro.analisis:
        for hallazgo in analisis.hallazgos:
            es_rend = es_celda_de_rendimiento(hallazgo, analisis)
            errores.append(clasificar_hallazgo(hallazgo, es_rendimiento=es_rend))

    for hallazgo in libro.hallazgos:
        errores.append(clasificar_hallazgo(hallazgo))

    filas, hojas = _filas_y_hojas_rechazadas(errores, catalogo)
    return Clasificacion(errores=tuple(errores), filas_rechazadas=filas, hojas_rechazadas=hojas)
