"""Lectura posicional del catálogo de conceptos (TKT-013a).

HDU-001 esc. 5, 6, 8 y 27; PA-T2, PA-T5, PA-T6, PA-T12, PA-T13. Funciones puras sobre filas en memoria.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from cimenta.presupuesto.dominio.catalogo import (
    ERRORES_DE_FORMULA,
    UNIDADES_ADMITIDAS,
    CatalogoLeido,
    CausaHallazgo,
    ConceptoLeido,
    Hallazgo,
    NodoLeido,
    Profundidad,
    Ruta,
    ValorCelda,
)
from tipos_base import Cantidad, Dinero

_PROFUNDIDADES: tuple[Profundidad, ...] = (
    Profundidad.RAIZ,
    Profundidad.NIVEL,
    Profundidad.AREA,
    Profundidad.PARTIDA,
)


@dataclass(frozen=True, slots=True)
class _Columnas:
    codigo: int
    descripcion: int
    unidad: int
    cantidad: int
    pu: int
    importe: int


def letra_de_columna(indice: int) -> str:
    """Índice desde cero a letra de Excel (HDU-001 esc. 5)."""
    if indice < 0:
        raise ValueError("índice de columna negativo")
    resultado = ""
    n = indice + 1
    while n:
        n, resto = divmod(n - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _normalizar_texto(texto: str) -> str:
    sin_bordes = texto.strip()
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", sin_bordes) if not unicodedata.combining(c)
    )
    return sin_acentos.casefold()


def _normalizar_rotulo(texto: str) -> str:
    return _normalizar_texto(texto).replace(" ", "").replace(".", "")


def normalizar_unidad(unidad: str) -> str | None:
    """PA-T12 · invariante 27: solo strip y mayúsculas."""
    candidata = unidad.strip().upper()
    if candidata in UNIDADES_ADMITIDAS:
        return candidata
    return None


def interpretar_numero[N: (Cantidad, Dinero)](
    valor: ValorCelda, tipo: type[N]
) -> N | CausaHallazgo:
    """HDU-001 esc. 6: nunca sustituye un rechazo por cero."""
    if valor is None:
        return CausaHallazgo.VALOR_AUSENTE
    if isinstance(valor, str):
        if not valor.strip():
            return CausaHallazgo.VALOR_AUSENTE
        if valor.strip() in ERRORES_DE_FORMULA:
            return CausaHallazgo.ERROR_DE_FORMULA
        return CausaHallazgo.NO_ES_NUMERO
    if isinstance(valor, bool):
        return CausaHallazgo.NO_ES_NUMERO
    try:
        return tipo(valor)
    except (TypeError, ValueError):
        return CausaHallazgo.NO_ES_NUMERO


def _texto_original(valor: ValorCelda) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return str(valor)


def _como_texto(valor: ValorCelda) -> str:
    if isinstance(valor, str):
        return valor.strip()
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, Decimal):
        if valor == valor.to_integral_value():
            return str(int(valor))
        return format(valor, "f")
    return str(valor)


def _celda_vacia(valor: ValorCelda) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    return False


def _codigo_presente(valor: ValorCelda) -> bool:
    if _celda_vacia(valor):
        return False
    if isinstance(valor, (int, Decimal)):
        return True
    if isinstance(valor, str):
        return bool(valor.strip())
    return True


def _valor_en_fila(fila: tuple[ValorCelda, ...], indice: int) -> ValorCelda:
    if indice >= len(fila):
        return None
    return fila[indice]


def elegir_hoja(nombres: Sequence[str]) -> str | Hallazgo:
    """PA-T5: hoja cuyo nombre normalizado empieza por «catalogo»."""
    candidatas = [n for n in nombres if _normalizar_texto(n).startswith("catalogo")]
    if not candidatas:
        detalle = "hojas del libro: " + ", ".join(nombres)
        return Hallazgo(
            causa=CausaHallazgo.HOJA_NO_LOCALIZADA,
            hoja=None,
            fila=None,
            columna=None,
            valor_original=None,
            detalle=detalle,
        )
    if len(candidatas) > 1:
        return Hallazgo(
            causa=CausaHallazgo.HOJA_AMBIGUA,
            hoja=None,
            fila=None,
            columna=None,
            valor_original=None,
            detalle=", ".join(candidatas),
        )
    return candidatas[0]


def catalogo_sin_conceptos(
    hallazgo: Hallazgo,
    hoja: str | None = None,
    fila_encabezado: int | None = None,
    nodos: tuple[NodoLeido, ...] = (),
) -> CatalogoLeido:
    """CA-10: resultado estructural sin conceptos."""
    return CatalogoLeido(
        hoja=hoja,
        fila_encabezado=fila_encabezado,
        nodos=nodos,
        conceptos=(),
        hallazgos=(hallazgo,),
    )


def _localizar_encabezado(
    hoja: str,
    filas: list[tuple[int, tuple[ValorCelda, ...]]],
) -> tuple[int, tuple[ValorCelda, ...]] | Hallazgo:
    for numero, valores in filas:
        celda_a = _valor_en_fila(valores, 0)
        if isinstance(celda_a, str) and _normalizar_rotulo(celda_a) == "codigo":
            return numero, valores
    return Hallazgo(
        causa=CausaHallazgo.ENCABEZADO_NO_LOCALIZADO,
        hoja=hoja,
        fila=None,
        columna="A",
        valor_original=None,
        detalle="ninguna fila tiene «Código» en la columna A",
    )


def _localizar_columnas(
    hoja: str,
    fila_encabezado: int,
    encabezado: tuple[ValorCelda, ...],
) -> _Columnas | Hallazgo:
    rotulos: dict[str, list[int]] = {}
    for indice, celda in enumerate(encabezado):
        if not isinstance(celda, str):
            continue
        clave = _normalizar_rotulo(celda)
        if not clave:
            continue
        rotulos.setdefault(clave, []).append(indice)

    codigo_idx = 0
    if rotulos.get("codigo") != [0]:
        return Hallazgo(
            causa=CausaHallazgo.COLUMNA_NO_LOCALIZADA,
            hoja=hoja,
            fila=fila_encabezado,
            columna=None,
            valor_original="codigo",
            detalle="no aparece",
        )

    descripcion_idx = codigo_idx + 1

    def _unica(clave: str, rotulo_esperado: str) -> int | Hallazgo:
        apariciones = rotulos.get(clave, [])
        if len(apariciones) == 0:
            return Hallazgo(
                causa=CausaHallazgo.COLUMNA_NO_LOCALIZADA,
                hoja=hoja,
                fila=fila_encabezado,
                columna=None,
                valor_original=rotulo_esperado,
                detalle="no aparece",
            )
        if len(apariciones) > 1:
            return Hallazgo(
                causa=CausaHallazgo.COLUMNA_NO_LOCALIZADA,
                hoja=hoja,
                fila=fila_encabezado,
                columna=None,
                valor_original=rotulo_esperado,
                detalle=f"aparece {len(apariciones)} veces",
            )
        indice = apariciones[0]
        if indice == descripcion_idx:
            return Hallazgo(
                causa=CausaHallazgo.COLUMNA_NO_LOCALIZADA,
                hoja=hoja,
                fila=fila_encabezado,
                columna=None,
                valor_original=rotulo_esperado,
                detalle="coincide con la descripción",
            )
        return indice

    unidad = _unica("unidad", "Unidad")
    if isinstance(unidad, Hallazgo):
        return unidad
    cantidad = _unica("cantidad", "Cantidad")
    if isinstance(cantidad, Hallazgo):
        return cantidad
    pu = _unica("pu", "P.U.")
    if isinstance(pu, Hallazgo):
        return pu
    importe = _unica("importe", "IMPORTE")
    if isinstance(importe, Hallazgo):
        return importe

    return _Columnas(
        codigo=codigo_idx,
        descripcion=descripcion_idx,
        unidad=unidad,
        cantidad=cantidad,
        pu=pu,
        importe=importe,
    )


def _ruta_vacia() -> Ruta:
    return Ruta(raiz=None, nivel=None, area=None, partida=None)


def _nodo_desde_fila(
    hoja: str,
    fila: int,
    profundidad: Profundidad,
    nombre_valor: ValorCelda,
    columna_desc: int,
    hallazgos: list[Hallazgo],
) -> NodoLeido:
    if isinstance(nombre_valor, str) and nombre_valor.strip() in ERRORES_DE_FORMULA:
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.NOMBRE_ILEGIBLE,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columna_desc),
                valor_original=nombre_valor,
            )
        )
        return NodoLeido(fila=fila, profundidad=profundidad, nombre=None)
    nombre = nombre_valor if isinstance(nombre_valor, str) else _como_texto(nombre_valor)
    return NodoLeido(fila=fila, profundidad=profundidad, nombre=nombre)


def _aplicar_corrida(
    hoja: str,
    corrida: list[tuple[int, ValorCelda]],
    columna_desc: int,
    *,
    primera_corrida: bool,
    ruta: Ruta,
    nodos: list[NodoLeido],
    hallazgos: list[Hallazgo],
) -> Ruta:
    if not corrida:
        return ruta

    sobrantes = len(corrida) - 4
    if sobrantes > 0:
        for fila, nombre_valor in corrida[:sobrantes]:
            nombre_texto = (
                nombre_valor if isinstance(nombre_valor, str) else _como_texto(nombre_valor)
            )
            hallazgos.append(
                Hallazgo(
                    causa=CausaHallazgo.PROFUNDIDAD_EXCEDIDA,
                    hoja=hoja,
                    fila=fila,
                    columna=letra_de_columna(columna_desc),
                    valor_original=nombre_texto
                    if isinstance(nombre_texto, str)
                    else str(nombre_texto),
                )
            )
        corrida = corrida[sobrantes:]

    if primera_corrida:
        niveles = list(_PROFUNDIDADES)
        nueva = _ruta_vacia()
        for i, (fila, nombre_valor) in enumerate(corrida):
            prof = niveles[i]
            nodo = _nodo_desde_fila(hoja, fila, prof, nombre_valor, columna_desc, hallazgos)
            nodos.append(nodo)
            if prof is Profundidad.RAIZ:
                nueva = Ruta(nodo, nueva.nivel, nueva.area, nueva.partida)
            elif prof is Profundidad.NIVEL:
                nueva = Ruta(nueva.raiz, nodo, nueva.area, nueva.partida)
            elif prof is Profundidad.AREA:
                nueva = Ruta(nueva.raiz, nueva.nivel, nodo, nueva.partida)
            else:
                nueva = Ruta(nueva.raiz, nueva.nivel, nueva.area, nodo)
        return nueva

    # Corridas posteriores: alinear a la partida (reemplazar los k niveles más profundos).
    k = len(corrida)
    base = (ruta.raiz, ruta.nivel, ruta.area, ruta.partida)
    indices = list(range(4 - k, 4))
    nueva_partes: list[NodoLeido | None] = list(base)
    for idx_pos, (fila, nombre_valor) in zip(indices, corrida, strict=True):
        prof = _PROFUNDIDADES[idx_pos]
        nodo = _nodo_desde_fila(hoja, fila, prof, nombre_valor, columna_desc, hallazgos)
        nodos.append(nodo)
        nueva_partes[idx_pos] = nodo
    for j in range(indices[-1] + 1, 4):
        nueva_partes[j] = None
    return Ruta(*nueva_partes)


def _leer_concepto(
    hoja: str,
    fila: int,
    valores: tuple[ValorCelda, ...],
    columnas: _Columnas,
    ruta: Ruta,
    hallazgos: list[Hallazgo],
) -> ConceptoLeido:
    codigo_raw = _valor_en_fila(valores, columnas.codigo)
    codigo = _como_texto(codigo_raw)
    if codigo in ERRORES_DE_FORMULA:
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.ERROR_DE_FORMULA,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.codigo),
                valor_original=codigo,
            )
        )

    desc_raw = _valor_en_fila(valores, columnas.descripcion)
    descripcion: str | None
    if _celda_vacia(desc_raw):
        descripcion = None
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.VALOR_AUSENTE,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.descripcion),
                valor_original=_texto_original(desc_raw),
            )
        )
    elif isinstance(desc_raw, str):
        descripcion = desc_raw
    else:
        descripcion = _como_texto(desc_raw)

    unidad_raw = _valor_en_fila(valores, columnas.unidad)
    unidad: str | None = None
    if _celda_vacia(unidad_raw):
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.VALOR_AUSENTE,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.unidad),
                valor_original=_texto_original(unidad_raw),
            )
        )
    elif isinstance(unidad_raw, str) and unidad_raw.strip() in ERRORES_DE_FORMULA:
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.ERROR_DE_FORMULA,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.unidad),
                valor_original=unidad_raw,
            )
        )
    else:
        texto_unidad = unidad_raw if isinstance(unidad_raw, str) else _como_texto(unidad_raw)
        normalizada = normalizar_unidad(texto_unidad)
        if normalizada is not None:
            unidad = normalizada
        else:
            unidad = texto_unidad
            hallazgos.append(
                Hallazgo(
                    causa=CausaHallazgo.UNIDAD_NO_RECONOCIDA,
                    hoja=hoja,
                    fila=fila,
                    columna=letra_de_columna(columnas.unidad),
                    valor_original=texto_unidad,
                )
            )

    cantidad: Cantidad | None = None
    res_cant = interpretar_numero(_valor_en_fila(valores, columnas.cantidad), Cantidad)
    if isinstance(res_cant, CausaHallazgo):
        hallazgos.append(
            Hallazgo(
                causa=res_cant,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.cantidad),
                valor_original=_texto_original(_valor_en_fila(valores, columnas.cantidad)),
            )
        )
    else:
        cantidad = res_cant

    precio: Dinero | None = None
    res_pu = interpretar_numero(_valor_en_fila(valores, columnas.pu), Dinero)
    if isinstance(res_pu, CausaHallazgo):
        hallazgos.append(
            Hallazgo(
                causa=res_pu,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.pu),
                valor_original=_texto_original(_valor_en_fila(valores, columnas.pu)),
            )
        )
    else:
        precio = res_pu

    importe_val: Dinero | None = None
    res_imp = interpretar_numero(_valor_en_fila(valores, columnas.importe), Dinero)
    if isinstance(res_imp, CausaHallazgo):
        hallazgos.append(
            Hallazgo(
                causa=res_imp,
                hoja=hoja,
                fila=fila,
                columna=letra_de_columna(columnas.importe),
                valor_original=_texto_original(_valor_en_fila(valores, columnas.importe)),
            )
        )
    else:
        importe_val = res_imp

    if ruta.partida is None:
        hallazgos.append(
            Hallazgo(
                causa=CausaHallazgo.CONCEPTO_SIN_PARTIDA,
                hoja=hoja,
                fila=fila,
                columna=None,
                valor_original=None,
            )
        )

    return ConceptoLeido(
        fila=fila,
        codigo=codigo,
        descripcion=descripcion,
        unidad=unidad,
        cantidad=cantidad,
        precio_unitario=precio,
        importe=importe_val,
        ruta=ruta,
    )


def analizar_hoja(
    hoja: str,
    filas: Iterable[tuple[int, tuple[ValorCelda, ...]]],
) -> CatalogoLeido:
    """Reconstruye jerarquía y conceptos desde filas ya extraídas (HDU-001 esc. 5)."""
    filas_lista = list(filas)
    enc_result = _localizar_encabezado(hoja, filas_lista)
    if isinstance(enc_result, Hallazgo):
        return catalogo_sin_conceptos(enc_result, hoja=hoja)

    fila_encabezado, encabezado = enc_result
    columnas_result = _localizar_columnas(hoja, fila_encabezado, encabezado)
    if isinstance(columnas_result, Hallazgo):
        return catalogo_sin_conceptos(columnas_result, hoja=hoja, fila_encabezado=fila_encabezado)
    columnas = columnas_result

    hallazgos: list[Hallazgo] = []
    nodos: list[NodoLeido] = []
    conceptos: list[ConceptoLeido] = []
    ruta = _ruta_vacia()
    corrida: list[tuple[int, ValorCelda]] = []
    primera_corrida = True

    for numero, valores in filas_lista:
        if numero <= fila_encabezado:
            continue

        codigo = _valor_en_fila(valores, columnas.codigo)
        nombre = _valor_en_fila(valores, columnas.descripcion)

        if not _codigo_presente(codigo) and _celda_vacia(nombre):
            continue

        if not _codigo_presente(codigo):
            corrida.append((numero, nombre))
            continue

        ruta = _aplicar_corrida(
            hoja,
            corrida,
            columnas.descripcion,
            primera_corrida=primera_corrida,
            ruta=ruta,
            nodos=nodos,
            hallazgos=hallazgos,
        )
        if corrida:
            primera_corrida = False
        corrida = []

        conceptos.append(_leer_concepto(hoja, numero, valores, columnas, ruta, hallazgos))

    if not conceptos:
        return catalogo_sin_conceptos(
            Hallazgo(
                causa=CausaHallazgo.NINGUN_CONCEPTO,
                hoja=hoja,
                fila=fila_encabezado,
                columna=None,
                valor_original=None,
            ),
            hoja=hoja,
            fila_encabezado=fila_encabezado,
            nodos=tuple(nodos),
        )

    return CatalogoLeido(
        hoja=hoja,
        fila_encabezado=fila_encabezado,
        nodos=tuple(nodos),
        conceptos=tuple(conceptos),
        hallazgos=tuple(hallazgos),
    )
