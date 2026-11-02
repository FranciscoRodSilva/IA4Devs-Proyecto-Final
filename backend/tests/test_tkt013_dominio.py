"""Dominio del lector de catálogo (TKT-013a): TC-01 a TC-30.

Sin Docker ni openpyxl. Prueba `cimenta/presupuesto/dominio/catalogo.py` y
`lectura_catalogo.py` con filas en memoria vía el ayudante `fila(numero, *valores)`.

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    CausaHallazgo,
    Hallazgo,
    Ruta,
    ValorCelda,
)
from herramientas.soporte_tkt013 import (
    HOJA_ENITI,
    HOJA_UNION,
    RUTAS_ESPERADAS_ENITI,
    nombres_desde_ruta,
)


def fila(numero: int, *valores: ValorCelda) -> tuple[int, tuple[ValorCelda, ...]]:
    """Empaqueta `(número de fila, valores desde la columna A)` para `analizar_hoja`."""
    return (numero, valores)


def _metadatos_siete_filas() -> list[tuple[int, tuple[ValorCelda, ...]]]:
    return [fila(i, None) for i in range(1, 8)]


def _encabezado_eniti_fila8() -> tuple[int, tuple[ValorCelda, ...]]:
    return fila(8, "Código", "ENCHAPES", "Unidad", "Cantidad", "P.U.", "IMPORTE")


def _encabezado_union_fila8() -> tuple[int, tuple[ValorCelda, ...]]:
    return fila(
        8,
        "CODIGO",
        "DESCRIPCION COMPLETA",
        "UNIDAD",
        "CANTIDAD",
        "P.U.",
        "IMPORTE",
        "NOTAS",
    )


def _concepto_minimo(
    codigo: ValorCelda,
    descripcion: str = "Concepto de prueba",
    *,
    unidad: str = "M2",
    cantidad: ValorCelda = Decimal("1"),
    precio: ValorCelda = Decimal("1"),
    importe: ValorCelda = Decimal("1"),
) -> tuple[ValorCelda, ...]:
    return (codigo, descripcion, unidad, cantidad, precio, importe)


def _fila_grupo(numero: int, nombre: str) -> tuple[int, tuple[ValorCelda, ...]]:
    return fila(numero, None, nombre)


_OMITIR_DETALLE = object()


def _assert_hallazgo(
    hallazgo: Hallazgo,
    *,
    causa: CausaHallazgo,
    hoja: str | None,
    fila_esperada: int | None,
    columna: str | None,
    valor_original: str | None,
    detalle: str | None | object = _OMITIR_DETALLE,
) -> None:
    assert hallazgo.causa == causa
    assert hallazgo.hoja == hoja
    assert hallazgo.fila == fila_esperada
    assert hallazgo.columna == columna
    assert hallazgo.valor_original == valor_original
    if detalle is not _OMITIR_DETALLE:
        assert hallazgo.detalle == detalle


def _analizar(hoja: str, filas: list[tuple[int, tuple[ValorCelda, ...]]]) -> CatalogoLeido:
    from cimenta.presupuesto.dominio.lectura_catalogo import analizar_hoja

    return analizar_hoja(hoja, filas)


# --- TC-01 a TC-09: constantes, unidad, número, letra ---


def test_hdu001_esc08_unidades_admitidas_son_las_ocho_del_catalogo() -> None:
    """TC-01 · HDU-001 esc. 8 · CA-5 — las ocho unidades del invariante 27."""
    from cimenta.presupuesto.dominio.catalogo import UNIDADES_ADMITIDAS

    assert (
        frozenset({"M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"})
        == UNIDADES_ADMITIDAS
    )


@pytest.mark.parametrize(
    ("entrada", "esperada"),
    [
        ("Pza", "PZA"),
        ("pza", "PZA"),
        ("PZA", "PZA"),
        ("Ml", "ML"),
        (" m2 ", "M2"),
    ],
)
def test_hdu001_esc08_variantes_de_mayusculas_y_espacios_se_normalizan(
    entrada: str, esperada: str
) -> None:
    """TC-02 · HDU-001 esc. 8 · CA-5, CA-6."""
    from cimenta.presupuesto.dominio.lectura_catalogo import normalizar_unidad

    assert normalizar_unidad(entrada) == esperada


@pytest.mark.parametrize(
    "entrada",
    ["M2.", "M²", "M 2", "M3", ""],
)
def test_hdu001_esc08_grafia_ajena_al_catalogo_no_se_normaliza(entrada: str) -> None:
    """TC-03 · HDU-001 esc. 8 · CA-6 · PA-T12 — rechazo: no se inventa unidad."""
    from cimenta.presupuesto.dominio.lectura_catalogo import normalizar_unidad

    assert normalizar_unidad(entrada) is None


def test_hdu001_esc06_entero_y_decimal_llegan_como_tipos_base() -> None:
    """TC-04 · HDU-001 esc. 6 · CA-2, CA-12 — Cantidad y Dinero sin cuantizar."""
    from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
    from tipos_base import Cantidad, Dinero

    c16 = interpretar_numero(16, Cantidad)
    c_decimal = interpretar_numero(Decimal("16.089"), Cantidad)
    d668 = interpretar_numero(Decimal("668.69"), Dinero)

    assert isinstance(c16, Cantidad)
    assert isinstance(c_decimal, Cantidad)
    assert isinstance(d668, Dinero)
    assert c16.valor == Decimal(16)
    assert c_decimal.valor == Decimal("16.089")
    assert c_decimal.valor.as_tuple().exponent == -3
    assert d668.valor == Decimal("668.69")


@pytest.mark.parametrize(
    "entrada",
    ["#REF!", " #N/A "],
)
def test_hdu001_esc06_error_de_formula_no_es_cero(entrada: str) -> None:
    """TC-05 · HDU-001 esc. 6 · CA-7 — rechazo ERROR_DE_FORMULA, no Dinero."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
    from tipos_base import Dinero

    resultado = interpretar_numero(entrada, Dinero)
    assert resultado == CausaHallazgo.ERROR_DE_FORMULA
    assert not isinstance(resultado, Dinero)


def test_hdu001_esc06_ref_en_columna_unidad_deja_unidad_nula() -> None:
    """TC-05b · HDU-001 esc. 6 · CA-7 — #REF! en columna C no queda como unidad del concepto."""
    filas = _metadatos_siete_filas() + [_encabezado_eniti_fila8()]
    filas += [
        _fila_grupo(9, "RAIZ"),
        _fila_grupo(10, "NIVEL"),
        _fila_grupo(11, "AREA"),
        _fila_grupo(12, "PART"),
        fila(13, "P-1", "desc", "#REF!", Decimal("1"), Decimal("1"), Decimal("1")),
    ]
    cat = _analizar(HOJA_ENITI, filas)
    assert len(cat.conceptos) == 1
    assert cat.conceptos[0].unidad is None
    errores_unidad = [
        h for h in cat.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA and h.columna == "C"
    ]
    assert len(errores_unidad) == 1
    assert errores_unidad[0].valor_original == "#REF!"


@pytest.mark.parametrize(
    "entrada",
    ["diez", "$ 668,69"],
)
def test_hdu001_esc06_texto_en_columna_numerica_no_es_cero(entrada: str) -> None:
    """TC-06 · HDU-001 esc. 6 · CA-8 — rechazo NO_ES_NUMERO."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
    from tipos_base import Cantidad, Dinero

    assert interpretar_numero(entrada, Cantidad) == CausaHallazgo.NO_ES_NUMERO
    assert interpretar_numero(entrada, Dinero) == CausaHallazgo.NO_ES_NUMERO


@pytest.mark.parametrize(
    "entrada",
    [None, "   "],
)
def test_hdu001_esc06_celda_vacia_no_es_cero(entrada: ValorCelda) -> None:
    """TC-07 · HDU-001 esc. 6 · CA-8 · P6 — rechazo VALOR_AUSENTE."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
    from tipos_base import Cantidad, Dinero

    assert interpretar_numero(entrada, Cantidad) == CausaHallazgo.VALOR_AUSENTE
    assert interpretar_numero(entrada, Dinero) == CausaHallazgo.VALOR_AUSENTE


@pytest.mark.parametrize(
    ("valor", "tipo_nombre"),
    [
        (Decimal("1E-50"), "Cantidad"),
        (Decimal("1E+45"), "Dinero"),
    ],
)
def test_hdu001_esc06_numero_fuera_de_tipos_base_se_reporta(
    valor: Decimal, tipo_nombre: str
) -> None:
    """TC-08 · HDU-001 esc. 6 · CA-8 — borde NO_ES_NUMERO sin excepción."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import interpretar_numero
    from tipos_base import Cantidad, Dinero

    if tipo_nombre == "Cantidad":
        assert interpretar_numero(valor, Cantidad) == CausaHallazgo.NO_ES_NUMERO
    else:
        assert interpretar_numero(valor, Dinero) == CausaHallazgo.NO_ES_NUMERO


@pytest.mark.parametrize(
    ("indice", "letra"),
    [(0, "A"), (4, "E"), (25, "Z"), (26, "AA"), (27, "AB")],
)
def test_hdu001_esc05_letra_de_columna(indice: int, letra: str) -> None:
    """TC-09 · HDU-001 esc. 5 · CA-7."""
    from cimenta.presupuesto.dominio.lectura_catalogo import letra_de_columna

    assert letra_de_columna(indice) == letra


# --- TC-10 a TC-17: hoja, encabezado, columnas, inmutabilidad ---


@pytest.mark.parametrize(
    ("nombres", "esperada"),
    [
        (["APU 1", "CATALOGO"], "CATALOGO"),
        (["Catálogo de conceptos", "Resumen"], "Catálogo de conceptos"),
    ],
)
def test_hdu001_esc05_la_hoja_del_catalogo_se_elige_sin_distinguir_mayusculas_ni_acentos(
    nombres: list[str], esperada: str
) -> None:
    """TC-10 · HDU-001 esc. 5 · CA-1, CA-2 · PA-T5."""
    from cimenta.presupuesto.dominio.lectura_catalogo import elegir_hoja

    assert elegir_hoja(nombres) == esperada


def test_hdu001_esc27_libro_sin_hoja_de_catalogo() -> None:
    """TC-11 · HDU-001 esc. 27 · CA-10 — HOJA_NO_LOCALIZADA y cero conceptos."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import (
        catalogo_sin_conceptos,
        elegir_hoja,
    )

    eleccion = elegir_hoja(["APU 1", "RESUMEN"])
    assert isinstance(eleccion, Hallazgo)
    _assert_hallazgo(
        eleccion,
        causa=CausaHallazgo.HOJA_NO_LOCALIZADA,
        hoja=None,
        fila_esperada=None,
        columna=None,
        valor_original=None,
    )
    assert "APU 1" in (eleccion.detalle or "")
    assert "RESUMEN" in (eleccion.detalle or "")

    cat = catalogo_sin_conceptos(eleccion)
    assert cat.conceptos == ()


def test_hdu001_esc27_dos_hojas_candidatas_no_se_elige_ninguna() -> None:
    """TC-12 · HDU-001 esc. 27 · CA-10 — HOJA_AMBIGUA."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Hallazgo
    from cimenta.presupuesto.dominio.lectura_catalogo import elegir_hoja

    eleccion = elegir_hoja(["CATALOGO", "CATALOGO (2)"])
    assert isinstance(eleccion, Hallazgo)
    _assert_hallazgo(
        eleccion,
        causa=CausaHallazgo.HOJA_AMBIGUA,
        hoja=None,
        fila_esperada=None,
        columna=None,
        valor_original=None,
        detalle="CATALOGO, CATALOGO (2)",
    )


def test_hdu001_esc27_hoja_sin_encabezado() -> None:
    """TC-13 · HDU-001 esc. 27 · CA-10 — ENCABEZADO_NO_LOCALIZADO."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = _metadatos_siete_filas() + [
        fila(8, "Metadato", "Sin código"),
        _fila_grupo(9, "NIVEL A"),
    ]
    cat = _analizar(HOJA_ENITI, filas)
    assert cat.conceptos == ()
    assert len(cat.hallazgos) == 1
    h = cat.hallazgos[0]
    _assert_hallazgo(
        h,
        causa=CausaHallazgo.ENCABEZADO_NO_LOCALIZADO,
        hoja=HOJA_ENITI,
        fila_esperada=None,
        columna="A",
        valor_original=None,
    )
    assert h.detalle is not None


def test_hdu001_esc27_encabezado_sin_conceptos() -> None:
    """TC-14 · HDU-001 esc. 27 · CA-10 — NINGUN_CONCEPTO."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [_fila_grupo(9, "RAIZ"), _fila_grupo(10, "NIVEL A"), _fila_grupo(11, "ZONA")]
    )
    cat = _analizar(HOJA_ENITI, filas)
    assert cat.fila_encabezado == 8
    assert cat.conceptos == ()
    h = cat.hallazgos[0]
    _assert_hallazgo(
        h,
        causa=CausaHallazgo.NINGUN_CONCEPTO,
        hoja=HOJA_ENITI,
        fila_esperada=8,
        columna=None,
        valor_original=None,
    )


@pytest.mark.parametrize(
    ("encabezado", "hoja"),
    [
        (_encabezado_eniti_fila8(), HOJA_ENITI),
        (_encabezado_union_fila8(), HOJA_UNION),
    ],
)
def test_hdu001_esc05_encabezado_con_otras_mayusculas_y_rotulos(
    encabezado: tuple[int, tuple[ValorCelda, ...]], hoja: str
) -> None:
    """TC-15 · HDU-001 esc. 5 · CA-1, CA-2 · PA-T5, PA-T6."""
    filas = (
        _metadatos_siete_filas()
        + [encabezado]
        + [
            _fila_grupo(9, "RAIZ"),
            _fila_grupo(10, "N1"),
            _fila_grupo(11, "Z1"),
            _fila_grupo(12, "P1"),
        ]
        + [fila(13, *_concepto_minimo("P-001", descripcion="Texto columna B"))]
    )
    cat = _analizar(hoja, filas)
    assert cat.fila_encabezado == 8
    assert len(cat.conceptos) == 1
    assert cat.conceptos[0].descripcion == "Texto columna B"


@pytest.mark.parametrize(
    ("encabezado", "rotulo", "detalle"),
    [
        (
            fila(8, "Código", "ENCHAPES", "Cantidad", "P.U.", "IMPORTE"),
            "Unidad",
            "no aparece",
        ),
        (
            fila(8, "Código", "ENCHAPES", "Unidad", "Cantidad", "P.U.", "IMPORTE", "IMPORTE"),
            "IMPORTE",
            "aparece 2 veces",
        ),
    ],
)
def test_hdu001_esc27_columna_que_falta_o_se_repite(
    encabezado: tuple[int, tuple[ValorCelda, ...]],
    rotulo: str,
    detalle: str,
) -> None:
    """TC-16 · HDU-001 esc. 27 · CA-10 · P8 — COLUMNA_NO_LOCALIZADA."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = _metadatos_siete_filas() + [encabezado] + [_fila_grupo(9, "RAIZ")]
    cat = _analizar(HOJA_ENITI, filas)
    assert cat.conceptos == ()
    h = cat.hallazgos[0]
    _assert_hallazgo(
        h,
        causa=CausaHallazgo.COLUMNA_NO_LOCALIZADA,
        hoja=HOJA_ENITI,
        fila_esperada=8,
        columna=None,
        valor_original=rotulo,
        detalle=detalle,
    )


def test_hdu001_esc05_el_resultado_es_inmutable() -> None:
    """TC-17 · HDU-001 esc. 5 · CA-12 · M4 — dataclasses congeladas."""
    from dataclasses import FrozenInstanceError

    from cimenta.presupuesto.dominio.catalogo import (
        CatalogoLeido,
        ConceptoLeido,
    )

    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    concepto = ConceptoLeido(
        fila=1,
        codigo="P-001",
        descripcion="x",
        unidad="M2",
        cantidad=None,
        precio_unitario=None,
        importe=None,
        ruta=ruta,
    )
    catalogo = CatalogoLeido(
        hoja=HOJA_ENITI,
        fila_encabezado=8,
        nodos=(),
        conceptos=(concepto,),
        hallazgos=(),
    )
    assert isinstance(catalogo.conceptos, tuple)
    assert isinstance(catalogo.hallazgos, tuple)

    with pytest.raises(FrozenInstanceError):
        catalogo.hoja = "otra"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        concepto.codigo = "P-002"  # type: ignore[misc]


# --- TC-18 a TC-30: jerarquía, hallazgos por fila, códigos ---


def test_hdu001_esc05_cada_fila_sin_codigo_es_un_nodo_y_nunca_un_concepto() -> None:
    """TC-18 · HDU-001 esc. 5 · CA-3 — nombres de grupo tal cual."""
    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [_fila_grupo(9, "RAIZ  X")]
        + [_fila_grupo(10, "NIVEL  con  doble")]
        + [_fila_grupo(11, "ZONA ")]
        + [_fila_grupo(12, "PARTIDA")]
        + [fila(13, *_concepto_minimo("P-001"))]
    )
    cat = _analizar(HOJA_ENITI, filas)
    filas_nodo = {n.fila for n in cat.nodos}
    filas_concepto = {c.fila for c in cat.conceptos}
    assert filas_nodo.isdisjoint(filas_concepto)
    assert cat.nodos[1].nombre == "NIVEL  con  doble"
    assert cat.nodos[2].nombre == "ZONA "


def test_hdu001_esc05_primera_corrida_de_cuatro_llena_la_ruta() -> None:
    """TC-19 · HDU-001 esc. 5 · CA-3 · PA-T2."""
    from cimenta.presupuesto.dominio.catalogo import Profundidad

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "RAIZ_A"),
            _fila_grupo(10, "NIVEL_A"),
            _fila_grupo(11, "AREA_A"),
            _fila_grupo(12, "PART_A"),
            fila(13, *_concepto_minimo("P-001")),
            fila(14, *_concepto_minimo("P-002")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    prof_por_fila = {n.fila: n.profundidad for n in cat.nodos}
    assert prof_por_fila[9] == Profundidad.RAIZ
    assert prof_por_fila[10] == Profundidad.NIVEL
    assert prof_por_fila[11] == Profundidad.AREA
    assert prof_por_fila[12] == Profundidad.PARTIDA
    for c in cat.conceptos:
        r = c.ruta
        assert r.raiz is not None and r.raiz.fila == 9
        assert r.nivel is not None and r.nivel.fila == 10
        assert r.area is not None and r.area.fila == 11
        assert r.partida is not None and r.partida.fila == 12


def _filas_patron_eniti_neutro() -> list[tuple[int, tuple[ValorCelda, ...]]]:
    """Patrón E-6 filas 9-45 con nombres neutros (misma forma de corridas y conceptos)."""
    filas = _metadatos_siete_filas() + [_encabezado_eniti_fila8()]
    por_fila: dict[int, tuple[int, tuple[ValorCelda, ...]]] = {}
    grupos: list[tuple[int, str]] = [
        (9, "RAIZ_NEUTRA"),
        (10, "NIVEL 1"),
        (11, "ZONA_LOBBY"),
        (12, "TRABAJO_MUROS"),
        (15, "TRABAJO_PLAFONES"),
        (20, "TRABAJO_GENERALES"),
        (24, "TRABAJO_ENCHAPES_LOBBY"),
        (27, "ZONA_ESCALERAS"),
        (28, "TRABAJO_ENCHAPES_CUBO"),
        (30, "DEPT_101"),
        (31, "TRABAJO_MUROS"),
        (38, "TRABAJO_PLAFONES"),
        (44, "TRABAJO_GENERALES"),
    ]
    conceptos: list[tuple[int, ValorCelda]] = [
        (13, 620001),
        (14, 620003),
        (16, 620010),
        (17, 620011),
        (18, 620014),
        (19, 620015),
        (21, 620016),
        (22, 620018),
        (23, 620019),
        (25, 620040),
        (26, 620041),
        (29, "620040-A"),
        (32, 620001),
        (33, 620002),
        (34, 620003),
        (35, 620004),
        (36, 620005),
        (37, 620006),
        (39, 620010),
        (40, 620012),
        (41, 620013),
        (42, 620014),
        (43, 620015),
        (45, 620016),
    ]
    for num, nombre in grupos:
        por_fila[num] = _fila_grupo(num, nombre)
    for num, codigo in conceptos:
        por_fila[num] = fila(num, *_concepto_minimo(codigo, descripcion=f"Desc {codigo}"))
    filas.extend(por_fila[n] for n in sorted(por_fila))
    return filas


def test_hdu001_esc05_patron_de_corridas_de_eniti() -> None:
    """TC-20 · HDU-001 esc. 5 · CA-3 · PA-T2 — patrón E-6 filas 9-45."""
    cat = _analizar(HOJA_ENITI, _filas_patron_eniti_neutro())
    por_fila = {c.fila: c for c in cat.conceptos}
    assert set(por_fila) == set(RUTAS_ESPERADAS_ENITI)
    for fila_num, esperada in RUTAS_ESPERADAS_ENITI.items():
        assert nombres_desde_ruta(por_fila[fila_num].ruta) == esperada
    # Partida sola en fila 15 y área+partida 27-28 quedan reflejadas en rutas 16+ y 29.
    assert nombres_desde_ruta(por_fila[16].ruta)[3] == "TRABAJO_PLAFONES"
    assert nombres_desde_ruta(por_fila[29].ruta)[2:] == ("ZONA_ESCALERAS", "TRABAJO_ENCHAPES_CUBO")


def _filas_patron_union_neutro() -> list[tuple[int, tuple[ValorCelda, ...]]]:
    filas = _metadatos_siete_filas() + [_encabezado_union_fila8()]
    filas += [
        _fila_grupo(9, "RAIZ_UNION"),
        _fila_grupo(10, "Nivel 1"),
        _fila_grupo(11, "Zona Pasillos"),
    ]
    for num, codigo in [
        (12, 620012),
        (13, 620015),
        (14, 620016),
        (15, 620017),
        (16, 620031),
    ]:
        filas.append(
            fila(
                num,
                codigo,
                f"Desc {codigo}",
                "M2",
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
                None,
            )
        )
    filas += [_fila_grupo(17, "Depto 111"), _fila_grupo(18, "Trabajo Muros")]
    filas += [
        fila(19, 620001, "Desc 620001", "M2", Decimal("1"), Decimal("1"), Decimal("1"), None),
        fila(20, 620002, "Desc 620002", "M2", Decimal("1"), Decimal("1"), Decimal("1"), None),
    ]
    return filas


def test_hdu001_esc05_patron_de_corridas_de_union_square() -> None:
    """TC-21 · HDU-001 esc. 5 · CA-4, CA-9 · PA-T2 — patrón E-6 filas 9-20."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    cat = _analizar(HOJA_UNION, _filas_patron_union_neutro())
    por_fila = {c.fila: c for c in cat.conceptos}
    for fila_num in (12, 13, 14, 15, 16):
        assert por_fila[fila_num].ruta.partida is None
        assert nombres_desde_ruta(por_fila[fila_num].ruta) == (
            "RAIZ_UNION",
            "Nivel 1",
            "Zona Pasillos",
            None,
        )
    assert nombres_desde_ruta(por_fila[19].ruta) == (
        "RAIZ_UNION",
        "Nivel 1",
        "Depto 111",
        "Trabajo Muros",
    )
    sin_partida = [h for h in cat.hallazgos if h.causa == CausaHallazgo.CONCEPTO_SIN_PARTIDA]
    assert [h.fila for h in sin_partida] == [12, 13, 14, 15, 16]


def test_hdu001_esc05_concepto_sin_partida_se_reporta_sin_inventarla() -> None:
    """TC-22 · HDU-001 esc. 5 · CA-9 · PA-T13 — hallazgo por concepto 12-16."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    cat = _analizar(HOJA_UNION, _filas_patron_union_neutro())
    hallazgos = [h for h in cat.hallazgos if h.causa == CausaHallazgo.CONCEPTO_SIN_PARTIDA]
    assert len(hallazgos) == 5
    for h in hallazgos:
        _assert_hallazgo(
            h,
            causa=CausaHallazgo.CONCEPTO_SIN_PARTIDA,
            hoja=HOJA_UNION,
            fila_esperada=h.fila,
            columna=None,
            valor_original=None,
        )
        assert h.fila in (12, 13, 14, 15, 16)
        concepto = next(c for c in cat.conceptos if c.fila == h.fila)
        assert concepto.ruta.partida is None
    assert len(cat.nodos) == 5


def test_hdu001_esc05_nombre_ilegible_conserva_su_posicion() -> None:
    """TC-23 · HDU-001 esc. 5 · CA-11 — NOMBRE_ILEGIBLE en corrida posterior."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo, Profundidad

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "RAIZ_A"),
            _fila_grupo(10, "NIVEL_A"),
            _fila_grupo(11, "AREA_A"),
            _fila_grupo(12, "PART_A"),
            fila(13, *_concepto_minimo("P-001")),
            _fila_grupo(14, "NIVEL B"),
            _fila_grupo(15, "#REF!"),
            _fila_grupo(16, "TRABAJO Y"),
            fila(17, *_concepto_minimo("P-002")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    concepto = cat.conceptos[-1]
    r = concepto.ruta
    assert r.partida is not None and r.partida.nombre == "TRABAJO Y"
    assert r.area is not None and r.area.nombre is None and r.area.profundidad == Profundidad.AREA
    ilegibles = [h for h in cat.hallazgos if h.causa == CausaHallazgo.NOMBRE_ILEGIBLE]
    assert len(ilegibles) == 1
    _assert_hallazgo(
        ilegibles[0],
        causa=CausaHallazgo.NOMBRE_ILEGIBLE,
        hoja=HOJA_ENITI,
        fila_esperada=15,
        columna="B",
        valor_original="#REF!",
    )


def test_hdu001_esc05_filas_vacias_no_son_nodos_ni_cortan_la_corrida() -> None:
    """TC-24 · HDU-001 esc. 5 · CA-11 · P5 · PA-T7."""
    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "RAIZ_A"),
            _fila_grupo(10, "NIVEL_A"),
            fila(11, None, None, None, None, None, None),
            fila(12, "", "", "", "", "", ""),
            fila(13, None, "", None, Decimal("999"), None, None),
            _fila_grupo(14, "AREA_A"),
            _fila_grupo(15, "PART_A"),
            fila(16, *_concepto_minimo("P-001")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    assert cat.hallazgos == ()
    r = cat.conceptos[0].ruta
    assert r.raiz is not None and r.raiz.nombre == "RAIZ_A"
    assert r.nivel is not None and r.nivel.nombre == "NIVEL_A"
    assert r.area is not None and r.area.nombre == "AREA_A"
    assert r.partida is not None and r.partida.nombre == "PART_A"


def test_hdu001_esc05_corrida_de_mas_de_cuatro_filas() -> None:
    """TC-25 · HDU-001 esc. 5 · CA-3 · PA-T2 — PROFUNDIDAD_EXCEDIDA y cuatro últimas."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "RAIZ_A"),
            _fila_grupo(10, "NIVEL_A"),
            _fila_grupo(11, "AREA_A"),
            _fila_grupo(12, "PART_A"),
            fila(13, *_concepto_minimo("P-001")),
            _fila_grupo(14, "SOBRA_1"),
            _fila_grupo(15, "NUEVA_R"),
            _fila_grupo(16, "NUEVA_N"),
            _fila_grupo(17, "NUEVA_A"),
            _fila_grupo(18, "NUEVA_P"),
            fila(19, *_concepto_minimo("P-002")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    excedida = [h for h in cat.hallazgos if h.causa == CausaHallazgo.PROFUNDIDAD_EXCEDIDA]
    assert len(excedida) == 1
    _assert_hallazgo(
        excedida[0],
        causa=CausaHallazgo.PROFUNDIDAD_EXCEDIDA,
        hoja=HOJA_ENITI,
        fila_esperada=14,
        columna="B",
        valor_original="SOBRA_1",
    )
    r = cat.conceptos[-1].ruta
    assert nombres_desde_ruta(r) == ("NUEVA_R", "NUEVA_N", "NUEVA_A", "NUEVA_P")


def test_hdu001_esc05_corrida_final_sin_conceptos_se_descarta() -> None:
    """TC-26 · HDU-001 esc. 5 · P5 — corrida al cierre sin hallazgo."""
    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "RAIZ_A"),
            _fila_grupo(10, "NIVEL_A"),
            _fila_grupo(11, "AREA_A"),
            _fila_grupo(12, "PART_A"),
            fila(13, *_concepto_minimo("P-001")),
            _fila_grupo(14, "COLA_A"),
            _fila_grupo(15, "COLA_B"),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    filas_nodo = {n.fila for n in cat.nodos}
    assert 14 not in filas_nodo and 15 not in filas_nodo
    assert cat.hallazgos == ()


def test_hdu001_esc05_codigo_conserva_su_forma() -> None:
    """TC-27 · HDU-001 esc. 5 · CA-1."""
    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "R"),
            _fila_grupo(10, "N"),
            _fila_grupo(11, "A"),
            _fila_grupo(12, "P"),
            fila(13, 620001, "d", "M2", Decimal("1"), Decimal("1"), Decimal("1")),
            fila(14, Decimal("620001.0"), "d", "M2", Decimal("1"), Decimal("1"), Decimal("1")),
            fila(15, "620040-A", "d", "M2", Decimal("1"), Decimal("1"), Decimal("1")),
            fila(16, " 620002 ", "d", "M2", Decimal("1"), Decimal("1"), Decimal("1")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    codigos = [c.codigo for c in cat.conceptos]
    assert codigos == ["620001", "620001", "620040-A", "620002"]


def test_hdu001_esc08_unidad_desconocida_se_conserva_y_se_reporta() -> None:
    """TC-28 · HDU-001 esc. 8 · CA-6 — UNIDAD_NO_RECONOCIDA y m2 normalizado."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "R"),
            _fila_grupo(10, "N"),
            _fila_grupo(11, "A"),
            _fila_grupo(12, "P"),
            fila(13, "P-001", "d", "M2.", Decimal("1"), Decimal("1"), Decimal("1")),
            fila(14, "P-002", "d", "M²", Decimal("1"), Decimal("1"), Decimal("1")),
            fila(15, "P-003", "d", " m2 ", Decimal("1"), Decimal("1"), Decimal("1")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    c1, c2, c3 = cat.conceptos
    assert c1.unidad == "M2."
    assert c2.unidad == "M²"
    assert c3.unidad == "M2"
    desconocidas = [h for h in cat.hallazgos if h.causa == CausaHallazgo.UNIDAD_NO_RECONOCIDA]
    assert len(desconocidas) == 2
    _assert_hallazgo(
        desconocidas[0],
        causa=CausaHallazgo.UNIDAD_NO_RECONOCIDA,
        hoja=HOJA_ENITI,
        fila_esperada=13,
        columna="C",
        valor_original="M2.",
    )
    _assert_hallazgo(
        desconocidas[1],
        causa=CausaHallazgo.UNIDAD_NO_RECONOCIDA,
        hoja=HOJA_ENITI,
        fila_esperada=14,
        columna="C",
        valor_original="M²",
    )


def test_hdu001_esc06_ref_en_precio_e_importe_se_reporta_por_columna() -> None:
    """TC-29 · HDU-001 esc. 6 · CA-7 — ERROR_DE_FORMULA en E y F."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
    from tipos_base import Cantidad

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "R"),
            _fila_grupo(10, "N"),
            _fila_grupo(11, "A"),
            _fila_grupo(12, "P"),
            fila(13, "P-001", "d", "M2", Decimal("16.089"), "#REF!", "#REF!"),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    c = cat.conceptos[0]
    assert isinstance(c.cantidad, Cantidad)
    assert c.precio_unitario is None
    assert c.importe is None
    formulas = [h for h in cat.hallazgos if h.causa == CausaHallazgo.ERROR_DE_FORMULA]
    assert len(formulas) == 2
    _assert_hallazgo(
        formulas[0],
        causa=CausaHallazgo.ERROR_DE_FORMULA,
        hoja=HOJA_ENITI,
        fila_esperada=13,
        columna="E",
        valor_original="#REF!",
    )
    _assert_hallazgo(
        formulas[1],
        causa=CausaHallazgo.ERROR_DE_FORMULA,
        hoja=HOJA_ENITI,
        fila_esperada=13,
        columna="F",
        valor_original="#REF!",
    )


def test_hdu001_esc06_texto_en_cantidad_y_precio_se_reporta_por_columna() -> None:
    """TC-30 · HDU-001 esc. 6 · CA-8 — NO_ES_NUMERO en D y E."""
    from cimenta.presupuesto.dominio.catalogo import CausaHallazgo

    filas = (
        _metadatos_siete_filas()
        + [_encabezado_eniti_fila8()]
        + [
            _fila_grupo(9, "R"),
            _fila_grupo(10, "N"),
            _fila_grupo(11, "A"),
            _fila_grupo(12, "P"),
            fila(13, "P-001", "d", "M2", "diez", "$ 668,69", Decimal("1")),
        ]
    )
    cat = _analizar(HOJA_ENITI, filas)
    c = cat.conceptos[0]
    assert c.cantidad is None
    assert c.precio_unitario is None
    assert c.ruta.partida is not None
    numericos = [h for h in cat.hallazgos if h.causa == CausaHallazgo.NO_ES_NUMERO]
    assert len(numericos) == 2
    _assert_hallazgo(
        numericos[0],
        causa=CausaHallazgo.NO_ES_NUMERO,
        hoja=HOJA_ENITI,
        fila_esperada=13,
        columna="D",
        valor_original="diez",
    )
    _assert_hallazgo(
        numericos[1],
        causa=CausaHallazgo.NO_ES_NUMERO,
        hoja=HOJA_ENITI,
        fila_esperada=13,
        columna="E",
        valor_original="$ 668,69",
    )
