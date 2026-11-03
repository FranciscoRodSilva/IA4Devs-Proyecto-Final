"""Lectura por rótulos de una hoja de análisis de precios unitarios (TKT-014a).

HDU-001 esc. 5 y 6; PA-T4 a PA-T10. Funciones puras sobre filas en memoria.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal
from enum import StrEnum

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    CabeceraLeida,
    CargoLeido,
    InsumoLeido,
    TipoCargo,
    TipoInsumo,
    TotalesAnalisis,
)
from cimenta.presupuesto.dominio.catalogo import (
    ERRORES_DE_FORMULA,
    CausaHallazgo,
    Hallazgo,
    ValorCelda,
)
from cimenta.presupuesto.dominio.lectura_catalogo import (
    _celda_vacia,
    _como_texto,
    _normalizar_rotulo,
    _texto_original,
    interpretar_numero,
    letra_de_columna,
    normalizar_unidad,
)
from tipos_base import Dinero, Porcentaje, Rendimiento, sumar

_COL_DESCRIPCION = 0
_COL_UNIDAD = 3
_COL_COSTO = 4
_COL_RENDIMIENTO = 5
_COL_CARGO = 6
_COL_PORCENTAJE_CARGO = 3
_COL_BASE_CARGO = 4
_COL_IMPORTE_CARGO = 6
_COL_VALOR_C = 2
_COL_VALOR_ANALISTA = 1

_PREFIJOS_DE_SUBTOTAL = ("subtotal", "total", "suma")
_TOLERANCIA_PU = Decimal("0.01")
_RE_FECHA = re.compile(r"^(\d{4}-\d{2}-\d{2})(?: 00:00:00)?$")


class _Bloque(StrEnum):
    NINGUNO = "NINGUNO"
    MATERIAL = "MATERIAL"
    MANO_OBRA = "MANO_OBRA"
    CARGOS = "CARGOS"
    VIATICOS = "VIATICOS"


def normalizar_clave_insumo(descripcion: str) -> str:
    """Decisión 1 · clave por descripción normalizada."""
    return " ".join(descripcion.split()).upper()


def normalizar_codigo(valor: ValorCelda) -> str | None:
    """PA-T4: código recortado y en mayúsculas."""
    if _celda_vacia(valor):
        return None
    return _como_texto(valor).upper()


def rotulo_normalizado(texto: str) -> str:
    return _normalizar_rotulo(texto).rstrip(":")


def tipo_de_cargo(rotulo: str) -> TipoCargo | None:
    """PA-T7: tipo por rótulo normalizado."""
    r = rotulo_normalizado(rotulo)
    if r == "herramientamenor":
        return TipoCargo.HERRAMIENTA_MENOR
    if r == "andamiaje":
        return TipoCargo.ANDAMIAJE
    if r == "desperdicio":
        return TipoCargo.DESPERDICIO
    if r == "indirectos":
        return TipoCargo.INDIRECTOS
    if r == "utilidad":
        return TipoCargo.UTILIDAD
    if r.startswith("iva"):
        return TipoCargo.IVA
    return None


def interpretar_fecha(valor: ValorCelda) -> str | CausaHallazgo:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return CausaHallazgo.VALOR_AUSENTE
    if isinstance(valor, str):
        texto = valor.strip()
        if texto in ERRORES_DE_FORMULA:
            return CausaHallazgo.ERROR_DE_FORMULA
        coincidencia = _RE_FECHA.match(texto)
        if coincidencia:
            return coincidencia.group(1)
        return CausaHallazgo.FECHA_NO_RECONOCIDA
    return CausaHallazgo.FECHA_NO_RECONOCIDA


def _valor_en(fila: tuple[ValorCelda, ...], indice: int) -> ValorCelda:
    if indice >= len(fila):
        return None
    return fila[indice]


def _texto_a(fila: tuple[ValorCelda, ...]) -> str | None:
    valor = _valor_en(fila, _COL_DESCRIPCION)
    if valor is None:
        return None
    if not isinstance(valor, str):
        return str(valor).strip() or None
    return valor.strip() or None


def _es_prefijo_subtotal(rotulo: str) -> bool:
    return any(rotulo.startswith(prefijo) for prefijo in _PREFIJOS_DE_SUBTOTAL)


def _interpretar_no_negativo[N: (Dinero, Rendimiento, Porcentaje)](
    valor: ValorCelda, tipo: type[N]
) -> N | CausaHallazgo:
    resultado = interpretar_numero(valor, tipo)
    if isinstance(resultado, CausaHallazgo):
        return resultado
    if resultado.valor < 0:
        return CausaHallazgo.VALOR_NEGATIVO
    return resultado


def _hallazgo(
    causa: CausaHallazgo,
    hoja: str,
    fila: int | None,
    columna: str | None,
    valor: ValorCelda,
    *,
    detalle: str | None = None,
) -> Hallazgo:
    return Hallazgo(
        causa=causa,
        hoja=hoja,
        fila=fila,
        columna=columna,
        valor_original=_texto_original(valor),
        detalle=detalle,
    )


def _aplicar_interpretacion[N](
    hallazgos: list[Hallazgo],
    hoja: str,
    fila: int,
    columna: str,
    valor: ValorCelda,
    interpretacion: N | CausaHallazgo,
) -> N | None:
    if isinstance(interpretacion, CausaHallazgo):
        hallazgos.append(_hallazgo(interpretacion, hoja, fila, columna, valor))
        return None
    return interpretacion


def _fila_sin_cifras_datos(fila: tuple[ValorCelda, ...]) -> bool:
    return (
        _celda_vacia(_valor_en(fila, _COL_COSTO))
        and _celda_vacia(_valor_en(fila, _COL_RENDIMIENTO))
        and _celda_vacia(_valor_en(fila, _COL_CARGO))
    )


def _fila_sin_cifras_cargo(fila: tuple[ValorCelda, ...]) -> bool:
    return (
        _celda_vacia(_valor_en(fila, _COL_PORCENTAJE_CARGO))
        and _celda_vacia(_valor_en(fila, _COL_BASE_CARGO))
        and _celda_vacia(_valor_en(fila, _COL_IMPORTE_CARGO))
    )


def _hallazgo_sin_rotulo_cabecera(hoja: str, campo: str) -> Hallazgo:
    return Hallazgo(
        causa=CausaHallazgo.VALOR_AUSENTE,
        hoja=hoja,
        fila=None,
        columna=None,
        valor_original=None,
        detalle=f"sin rótulo «{campo}» en la cabecera",
    )


def _buscar_material_y_pie(
    filas: Sequence[tuple[int, tuple[ValorCelda, ...]]],
) -> tuple[int | None, int | None]:
    fila_material: int | None = None
    fila_pie: int | None = None
    for numero, fila in filas:
        texto_a = _texto_a(fila)
        if texto_a is not None:
            rotulo = rotulo_normalizado(texto_a)
            if rotulo == "material" and fila_material is None:
                fila_material = numero
        if fila_material is not None and numero > fila_material:
            for celda in fila:
                if isinstance(celda, str) and rotulo_normalizado(celda) == "preciounitario":
                    fila_pie = numero
                    break
    return fila_material, fila_pie


def _leer_unidad_cabecera(
    hallazgos: list[Hallazgo],
    hoja: str,
    fila: int,
    valor: ValorCelda,
) -> str | None:
    if _celda_vacia(valor):
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.VALOR_AUSENTE,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(_COL_VALOR_C),
                valor_original=_texto_original(valor),
                detalle=None,
            )
        )
        return None
    if isinstance(valor, str) and valor.strip() in ERRORES_DE_FORMULA:
        hallazgos.append(_hallazgo(CausaHallazgo.ERROR_DE_FORMULA, hoja, fila, "C", valor))
        return None
    normalizada = normalizar_unidad(_como_texto(valor)) if isinstance(valor, str) else None
    if normalizada is not None:
        return normalizada
    original = _como_texto(valor)
    hallazgos.append(
        _hallazgo(
            CausaHallazgo.UNIDAD_NO_RECONOCIDA, hoja, fila, letra_de_columna(_COL_VALOR_C), valor
        )
    )
    return original


def _leer_cabecera(
    hoja: str,
    filas: Sequence[tuple[int, tuple[ValorCelda, ...]]],
    fila_material: int,
) -> tuple[CabeceraLeida, list[Hallazgo]]:
    hallazgos: list[Hallazgo] = []
    fila_codigo: int | None = None
    codigo: str | None = None
    unidad: str | None = None
    fecha: str | None = None
    analista: str | None = None
    precio_unitario: Dinero | None = None
    visto_unidad = False
    visto_fecha = False
    visto_analista = False

    for numero, fila in filas:
        if numero >= fila_material:
            break
        texto_a = _texto_a(fila)
        if texto_a is None:
            continue
        rotulo = rotulo_normalizado(texto_a)
        if rotulo == "codigo":
            fila_codigo = numero
            valor_c = _valor_en(fila, _COL_VALOR_C)
            if _celda_vacia(valor_c):
                codigo = None
            elif isinstance(valor_c, str) and valor_c.strip() in ERRORES_DE_FORMULA:
                codigo = None
                hallazgos.append(
                    _hallazgo(CausaHallazgo.ERROR_DE_FORMULA, hoja, numero, "C", valor_c)
                )
            else:
                codigo = normalizar_codigo(valor_c)
        elif rotulo == "unidad":
            visto_unidad = True
            unidad = _leer_unidad_cabecera(hallazgos, hoja, numero, _valor_en(fila, _COL_VALOR_C))
        elif rotulo == "fecha":
            visto_fecha = True
            interpretacion = interpretar_fecha(_valor_en(fila, _COL_VALOR_C))
            if isinstance(interpretacion, CausaHallazgo):
                hallazgos.append(
                    _hallazgo(
                        interpretacion,
                        hoja,
                        numero,
                        letra_de_columna(_COL_VALOR_C),
                        _valor_en(fila, _COL_VALOR_C),
                    )
                )
                fecha = None
            else:
                fecha = interpretacion
        elif rotulo == "analista":
            visto_analista = True
            valor_b = _valor_en(fila, _COL_VALOR_ANALISTA)
            if _celda_vacia(valor_b):
                hallazgos.append(
                    Hallazgo(
                        causa=CausaHallazgo.VALOR_AUSENTE,
                        hoja=hoja,
                        fila=numero,
                        columna=letra_de_columna(_COL_VALOR_ANALISTA),
                        valor_original=_texto_original(valor_b),
                        detalle=None,
                    )
                )
                analista = None
            elif isinstance(valor_b, str) and valor_b.strip() in ERRORES_DE_FORMULA:
                hallazgos.append(
                    _hallazgo(CausaHallazgo.ERROR_DE_FORMULA, hoja, numero, "B", valor_b)
                )
                analista = None
            else:
                analista = _como_texto(valor_b)
        elif rotulo == "pu":
            precio_unitario = _aplicar_interpretacion(
                hallazgos,
                hoja,
                numero,
                "C",
                _valor_en(fila, _COL_VALOR_C),
                _interpretar_no_negativo(_valor_en(fila, _COL_VALOR_C), Dinero),
            )

    if not visto_unidad:
        hallazgos.append(_hallazgo_sin_rotulo_cabecera(hoja, "unidad"))
    if not visto_fecha:
        hallazgos.append(_hallazgo_sin_rotulo_cabecera(hoja, "fecha"))
    if not visto_analista:
        hallazgos.append(_hallazgo_sin_rotulo_cabecera(hoja, "analista"))

    return (
        CabeceraLeida(
            fila_codigo=fila_codigo,
            codigo=codigo,
            unidad=unidad,
            fecha=fecha,
            analista=analista,
            precio_unitario=precio_unitario,
        ),
        hallazgos,
    )


def _leer_insumo(
    hoja: str,
    numero: int,
    fila: tuple[ValorCelda, ...],
    tipo: TipoInsumo,
    hallazgos: list[Hallazgo],
) -> InsumoLeido:
    descripcion = _texto_a(fila) or ""
    clave = normalizar_clave_insumo(descripcion)
    valor_unidad = _valor_en(fila, _COL_UNIDAD)
    unidad: str | None
    if _celda_vacia(valor_unidad):
        unidad = None
        hallazgos.append(_hallazgo(CausaHallazgo.VALOR_AUSENTE, hoja, numero, "D", valor_unidad))
    elif isinstance(valor_unidad, str) and valor_unidad.strip() in ERRORES_DE_FORMULA:
        unidad = None
        hallazgos.append(_hallazgo(CausaHallazgo.ERROR_DE_FORMULA, hoja, numero, "D", valor_unidad))
    else:
        texto_u = _como_texto(valor_unidad)
        normalizada = normalizar_unidad(texto_u)
        if normalizada is not None:
            unidad = normalizada
        else:
            unidad = texto_u.strip() if isinstance(valor_unidad, str) else _como_texto(valor_unidad)
            hallazgos.append(
                _hallazgo(CausaHallazgo.UNIDAD_NO_RECONOCIDA, hoja, numero, "D", valor_unidad)
            )
    costo = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "E",
        _valor_en(fila, _COL_COSTO),
        _interpretar_no_negativo(_valor_en(fila, _COL_COSTO), Dinero),
    )
    rendimiento = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "F",
        _valor_en(fila, _COL_RENDIMIENTO),
        _interpretar_no_negativo(_valor_en(fila, _COL_RENDIMIENTO), Rendimiento),
    )
    cargo = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "G",
        _valor_en(fila, _COL_CARGO),
        _interpretar_no_negativo(_valor_en(fila, _COL_CARGO), Dinero),
    )
    return InsumoLeido(
        fila=numero,
        tipo=tipo,
        descripcion=descripcion,
        clave=clave,
        unidad=unidad,
        costo_unitario=costo,
        rendimiento=rendimiento,
        cargo=cargo,
    )


def _leer_cargo(
    hoja: str,
    numero: int,
    fila: tuple[ValorCelda, ...],
    rotulo: str,
    tipo: TipoCargo | None,
    hallazgos: list[Hallazgo],
) -> CargoLeido:
    if tipo is None:
        hallazgos.append(_hallazgo(CausaHallazgo.CARGO_DESCONOCIDO, hoja, numero, "A", rotulo))
    porcentaje = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "D",
        _valor_en(fila, _COL_PORCENTAJE_CARGO),
        _interpretar_no_negativo(_valor_en(fila, _COL_PORCENTAJE_CARGO), Porcentaje),
    )
    base = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "E",
        _valor_en(fila, _COL_BASE_CARGO),
        _interpretar_no_negativo(_valor_en(fila, _COL_BASE_CARGO), Dinero),
    )
    importe = _aplicar_interpretacion(
        hallazgos,
        hoja,
        numero,
        "G",
        _valor_en(fila, _COL_IMPORTE_CARGO),
        _interpretar_no_negativo(_valor_en(fila, _COL_IMPORTE_CARGO), Dinero),
    )
    return CargoLeido(
        fila=numero,
        rotulo=rotulo.strip(),
        tipo=tipo,
        porcentaje=porcentaje,
        base=base,
        importe=importe,
    )


def totalizar_analisis(
    insumos: Sequence[InsumoLeido], cargos: Sequence[CargoLeido]
) -> TotalesAnalisis:
    """S1 · totales reconstruidos con precisión completa."""

    def _sumar_cargos_insumos(tipo: TipoInsumo) -> Dinero | None:
        valores: list[Dinero] = []
        for insumo in insumos:
            if insumo.tipo != tipo:
                continue
            if insumo.cargo is None:
                return None
            valores.append(insumo.cargo)
        if not valores:
            return Dinero(0)
        return sumar(valores, Dinero)

    material = _sumar_cargos_insumos(TipoInsumo.MATERIAL)
    mano_obra = _sumar_cargos_insumos(TipoInsumo.MANO_OBRA)
    if material is None or mano_obra is None:
        costo_directo: Dinero | None = None
    else:
        costo_directo = material + mano_obra

    cargos_total: Dinero | None
    importes_cargo: list[Dinero] = []
    for cargo in cargos:
        if cargo.importe is None:
            cargos_total = None
            break
        importes_cargo.append(cargo.importe)
    else:
        cargos_total = sumar(importes_cargo, Dinero) if importes_cargo else Dinero(0)

    if costo_directo is None or cargos_total is None:
        precio_unitario: Dinero | None = None
    else:
        precio_unitario = costo_directo + cargos_total

    return TotalesAnalisis(
        material=material,
        mano_obra=mano_obra,
        costo_directo=costo_directo,
        cargos=cargos_total,
        precio_unitario=precio_unitario,
    )


def verificar_precio_unitario(
    hoja: str,
    fila_pie: int,
    archivo: Dinero | None,
    original_pie: str | None,
    totales: TotalesAnalisis,
    filas_ilegibles: Sequence[int],
) -> Hallazgo | None:
    """M7 · tolerancia ±0.01 absoluta sobre Decimal exacto."""
    if archivo is None or totales.precio_unitario is None:
        detalle = "valores ilegibles en las filas: " + ", ".join(str(f) for f in filas_ilegibles)
        return Hallazgo(
            causa=CausaHallazgo.PU_NO_VERIFICABLE,
            hoja=hoja,
            fila=fila_pie,
            columna="G",
            valor_original=original_pie,
            detalle=detalle,
        )
    diferencia = totales.precio_unitario - archivo
    if abs(diferencia.valor) <= _TOLERANCIA_PU:
        return None
    return Hallazgo(
        causa=CausaHallazgo.PU_NO_CUADRA,
        hoja=hoja,
        fila=fila_pie,
        columna="G",
        valor_original=original_pie,
        detalle=(
            f"archivo {format(archivo.valor, 'f')}; "
            f"reconstruido {format(totales.precio_unitario.valor, 'f')}; "
            f"diferencia {format(diferencia.valor, 'f')}"
        ),
    )


def analizar_hoja_apu(
    hoja: str, filas: Iterable[tuple[int, tuple[ValorCelda, ...]]]
) -> AnalisisLeido | None:
    """M1–M4, M7, M8 · reconoce la hoja y devuelve el análisis leído."""
    filas_lista = list(filas)
    fila_material, fila_pie = _buscar_material_y_pie(filas_lista)
    if fila_material is None or fila_pie is None:
        return None

    hallazgos: list[Hallazgo] = []
    cabecera, hallazgos_cabecera = _leer_cabecera(hoja, filas_lista, fila_material)
    hallazgos.extend(hallazgos_cabecera)

    insumos: list[InsumoLeido] = []
    cargos: list[CargoLeido] = []
    bloque = _Bloque.NINGUNO
    filas_ilegibles: list[int] = []

    for numero, fila in filas_lista:
        if numero < fila_material or numero >= fila_pie:
            continue
        texto_a = _texto_a(fila)
        if texto_a is None:
            continue
        rotulo = rotulo_normalizado(texto_a)
        if rotulo == "material":
            bloque = _Bloque.MATERIAL
            continue
        if rotulo == "manodeobra":
            bloque = _Bloque.MANO_OBRA
            continue
        if rotulo == "costodirecto":
            bloque = _Bloque.CARGOS
            continue
        if "viaticos" in rotulo:
            bloque = _Bloque.VIATICOS
            continue
        if _es_prefijo_subtotal(rotulo):
            continue
        if bloque == _Bloque.CARGOS and rotulo in ("cargosporcentuales", "cargosindirectos"):
            continue

        sin_cifras = (
            _fila_sin_cifras_cargo(fila)
            if bloque in (_Bloque.CARGOS, _Bloque.VIATICOS)
            else _fila_sin_cifras_datos(fila)
        )
        if sin_cifras:
            if bloque == _Bloque.VIATICOS:
                bloque = _Bloque.CARGOS
            continue

        if bloque == _Bloque.MATERIAL:
            insumo = _leer_insumo(hoja, numero, fila, TipoInsumo.MATERIAL, hallazgos)
            insumos.append(insumo)
            if insumo.cargo is None:
                filas_ilegibles.append(numero)
            continue
        if bloque == _Bloque.MANO_OBRA:
            insumo = _leer_insumo(hoja, numero, fila, TipoInsumo.MANO_OBRA, hallazgos)
            insumos.append(insumo)
            if insumo.cargo is None:
                filas_ilegibles.append(numero)
            continue
        if bloque == _Bloque.VIATICOS:
            tipo_conocido = tipo_de_cargo(texto_a)
            if tipo_conocido is not None:
                bloque = _Bloque.CARGOS
                cargo = _leer_cargo(hoja, numero, fila, texto_a, tipo_conocido, hallazgos)
                cargos.append(cargo)
                if cargo.importe is None:
                    filas_ilegibles.append(numero)
                continue
            cargo = _leer_cargo(hoja, numero, fila, texto_a, TipoCargo.VIATICOS, hallazgos)
            cargos.append(cargo)
            if cargo.importe is None:
                filas_ilegibles.append(numero)
            continue
        if bloque == _Bloque.CARGOS:
            tipo = tipo_de_cargo(texto_a)
            cargo = _leer_cargo(hoja, numero, fila, texto_a, tipo, hallazgos)
            cargos.append(cargo)
            if cargo.importe is None:
                filas_ilegibles.append(numero)

    fila_pie_datos = next(f for n, f in filas_lista if n == fila_pie)
    valor_pie = _valor_en(fila_pie_datos, _COL_CARGO)
    precio_unitario = _aplicar_interpretacion(
        hallazgos,
        hoja,
        fila_pie,
        "G",
        valor_pie,
        _interpretar_no_negativo(valor_pie, Dinero),
    )
    if precio_unitario is None:
        filas_ilegibles.append(fila_pie)

    totales = totalizar_analisis(insumos, cargos)
    hallazgo_cuadre = verificar_precio_unitario(
        hoja,
        fila_pie,
        precio_unitario,
        _texto_original(valor_pie),
        totales,
        filas_ilegibles,
    )
    if hallazgo_cuadre is not None:
        hallazgos.append(hallazgo_cuadre)

    return AnalisisLeido(
        hoja=hoja,
        cabecera=cabecera,
        insumos=tuple(insumos),
        cargos=tuple(cargos),
        fila_precio_unitario=fila_pie,
        precio_unitario=precio_unitario,
        totales=totales,
        hallazgos=tuple(hallazgos),
    )
