"""Clasificación de hallazgos TKT-015a, fila A2a: mapa, plantillas y rendimiento."""

from __future__ import annotations

from cimenta.presupuesto.dominio.catalogo import CausaHallazgo
from cimenta.presupuesto.dominio.clasificacion_importacion import (
    ESTRUCTURA_MINIMA_DEL_CATALOGO,
    TIPO_POR_CAUSA,
    clasificar_hallazgo,
    es_celda_de_rendimiento,
)
from cimenta.presupuesto.dominio.importacion import TipoErrorImportacion
from herramientas.soporte_tkt014 import leer_apu_en_memoria
from herramientas.soporte_tkt015 import hallazgo, hallazgo_ejemplo


def test_hdu001_esc06_toda_causa_tiene_tipo_y_mensaje() -> None:
    """TC-05 · HDU-001 esc. 6 · CA-10 · M1 — las 22 causas tienen tipo y mensaje con sufijo."""
    assert set(TIPO_POR_CAUSA) == set(CausaHallazgo)
    for causa in CausaHallazgo:
        h = hallazgo_ejemplo(causa)
        error = clasificar_hallazgo(h)
        assert error.mensaje.endswith(f" (causa: {causa.value})")
        assert error.tipo is TIPO_POR_CAUSA[causa]

    sin_conceptos = {
        CausaHallazgo.HOJA_NO_LOCALIZADA,
        CausaHallazgo.HOJA_AMBIGUA,
        CausaHallazgo.ENCABEZADO_NO_LOCALIZADO,
        CausaHallazgo.COLUMNA_NO_LOCALIZADA,
        CausaHallazgo.NINGUN_CONCEPTO,
    }
    for causa in sin_conceptos:
        assert (
            clasificar_hallazgo(hallazgo_ejemplo(causa)).tipo is TipoErrorImportacion.SIN_CONCEPTOS
        )
        err = clasificar_hallazgo(hallazgo_ejemplo(causa))
        assert err.fila is None and err.columna is None

    for causa in (
        CausaHallazgo.CONCEPTO_SIN_PARTIDA,
        CausaHallazgo.PROFUNDIDAD_EXCEDIDA,
        CausaHallazgo.CODIGO_SIN_CONCEPTO,
    ):
        err = clasificar_hallazgo(hallazgo_ejemplo(causa))
        assert err.tipo is TipoErrorImportacion.REF_ROTA
        assert (
            err.fila is not None
            or err.columna is not None
            or causa is CausaHallazgo.CONCEPTO_SIN_PARTIDA
        )

    err_cab = clasificar_hallazgo(
        hallazgo(
            CausaHallazgo.VALOR_AUSENTE,
            hoja="APU",
            fila=10,
            columna="C",
            valor=None,
            detalle="sin rótulo «fecha» en la cabecera",
        )
    )
    assert err_cab.tipo is TipoErrorImportacion.REF_ROTA
    assert err_cab.hoja is None and err_cab.fila is None and err_cab.columna is None
    assert "sin rótulo «fecha» en la cabecera" in err_cab.mensaje


def test_hdu001_esc06_ref_rota_conserva_la_celda() -> None:
    """TC-06 · HDU-001 esc. 6 · CA-2 — REF_ROTA conserva ubicación y mensaje exacto."""
    h = hallazgo(
        CausaHallazgo.ERROR_DE_FORMULA, hoja="CATALOGO", fila=57, columna="F", valor="#REF!"
    )
    error = clasificar_hallazgo(h)
    assert error.tipo is TipoErrorImportacion.REF_ROTA
    assert error.hoja == "CATALOGO" and error.fila == 57 and error.columna == "F"
    assert error.valor_original == "#REF!"
    assert error.mensaje == (
        "La celda trae el error de fórmula «#REF!»: su valor no se puede leer y no se importa como cero. "
        "(causa: ERROR_DE_FORMULA)"
    )
    assert "CATALOGO" not in error.mensaje
    assert "57" not in error.mensaje


def test_hdu001_esc08_unidad_desconocida() -> None:
    """TC-07 · HDU-001 esc. 8 · CA-5 — UNIDAD_DESCONOCIDA con mensaje exacto."""
    h = hallazgo(CausaHallazgo.UNIDAD_NO_RECONOCIDA, fila=57, columna="C", valor="XYZ")
    error = clasificar_hallazgo(h)
    assert error.tipo is TipoErrorImportacion.UNIDAD_DESCONOCIDA
    assert error.mensaje == (
        "La unidad «XYZ» no está entre las ocho admitidas: M2, ML, PZA, KG, CAJA, SACO, ROLLO y JORNAL. "
        "(causa: UNIDAD_NO_RECONOCIDA)"
    )


def test_hdu001_esc28_rendimiento_ausente_solo_en_la_celda_de_rendimiento() -> None:
    """TC-08 · HDU-001 esc. 28 · CA-6 — RENDIMIENTO_AUSENTE solo en F del insumo."""
    analisis = leer_apu_en_memoria(
        "APU TEST",
        celdas_rotas={(8, "F"): None, (8, "D"): None},
    )
    hallazgos_rend = [
        h for h in analisis.hallazgos if h.causa is CausaHallazgo.VALOR_AUSENTE and h.columna == "F"
    ]
    assert len(hallazgos_rend) == 1
    h_rend = hallazgos_rend[0]
    assert es_celda_de_rendimiento(h_rend, analisis)
    error = clasificar_hallazgo(h_rend, es_rendimiento=True)
    assert error.tipo is TipoErrorImportacion.RENDIMIENTO_AUSENTE
    assert error.columna == "F"
    assert error.fila == h_rend.fila

    for h in analisis.hallazgos:
        if h is h_rend:
            continue
        if h.causa is CausaHallazgo.VALOR_AUSENTE:
            assert not es_celda_de_rendimiento(h, analisis)
            assert clasificar_hallazgo(h).tipo is TipoErrorImportacion.REF_ROTA

    err_cat = clasificar_hallazgo(
        hallazgo(CausaHallazgo.VALOR_AUSENTE, hoja="CATALOGO", fila=10, columna="F")
    )
    assert err_cat.tipo is TipoErrorImportacion.REF_ROTA

    analisis_malo = leer_apu_en_memoria("APU NUM", celdas_rotas={(8, "F"): "abc"})
    for h in analisis_malo.hallazgos:
        if h.columna == "F" and h.fila == 8:
            assert clasificar_hallazgo(h).tipo is TipoErrorImportacion.REF_ROTA


def test_hdu001_esc27_hoja_sin_conceptos() -> None:
    """TC-09 · HDU-001 esc. 27 · CA-9 — SIN_CONCEPTOS para causas de hoja."""
    h_enc = hallazgo(CausaHallazgo.ENCABEZADO_NO_LOCALIZADO, hoja="VACIA", fila=5, columna="A")
    err_enc = clasificar_hallazgo(h_enc)
    assert err_enc.tipo is TipoErrorImportacion.SIN_CONCEPTOS
    assert err_enc.fila is None and err_enc.columna is None
    assert "La hoja «VACIA»" in err_enc.mensaje
    assert "«Código»" in err_enc.mensaje
    assert ESTRUCTURA_MINIMA_DEL_CATALOGO in err_enc.mensaje

    h_ning = hallazgo(CausaHallazgo.NINGUN_CONCEPTO, hoja="VACIA", fila=8, columna="A")
    err_ning = clasificar_hallazgo(h_ning)
    assert err_ning.tipo is TipoErrorImportacion.SIN_CONCEPTOS
    assert "fila 8" in err_ning.mensaje
    assert ESTRUCTURA_MINIMA_DEL_CATALOGO in err_ning.mensaje
