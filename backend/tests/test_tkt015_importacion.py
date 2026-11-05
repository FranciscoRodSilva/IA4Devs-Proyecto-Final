"""Dominio de importación TKT-015a, fila A1: estados, interrupciones e insumos existentes."""

from __future__ import annotations

import pytest

from cimenta.presupuesto.dominio.importacion import (
    ErrorImportacion,
    EstadoImportacion,
    MotivoInterrupcion,
    TipoErrorImportacion,
    error_de_interrupcion,
    estado_tras_analisis,
    mapa_de_insumos_existentes,
    puede_analizarse,
)


def test_hdu001_esc04_estado_tras_analisis() -> None:
    """TC-01 · HDU-001 esc. 4 · M2 — sin errores VALIDADO; con SIN_APU, CON_ERRORES."""
    assert estado_tras_analisis(()) is EstadoImportacion.VALIDADO
    error = ErrorImportacion(
        tipo=TipoErrorImportacion.SIN_APU,
        hoja="CATALOGO",
        fila=10,
        columna="A",
        mensaje="ejemplo",
        valor_original="P-001",
    )
    assert estado_tras_analisis((error,)) is EstadoImportacion.CON_ERRORES


@pytest.mark.parametrize(
    ("estado", "tipos", "esperado"),
    [
        (EstadoImportacion.RECIBIDO, frozenset(), True),
        (
            EstadoImportacion.CON_ERRORES,
            frozenset({TipoErrorImportacion.PROCESO_INTERRUMPIDO}),
            True,
        ),
        (
            EstadoImportacion.CON_ERRORES,
            frozenset(
                {
                    TipoErrorImportacion.PROCESO_INTERRUMPIDO,
                    TipoErrorImportacion.REF_ROTA,
                }
            ),
            False,
        ),
        (EstadoImportacion.CON_ERRORES, frozenset({TipoErrorImportacion.REF_ROTA}), False),
        (EstadoImportacion.CON_ERRORES, frozenset(), False),
        (EstadoImportacion.ANALIZANDO, frozenset(), False),
        (EstadoImportacion.VALIDADO, frozenset(), False),
        (EstadoImportacion.CONFIRMADO, frozenset(), False),
        (EstadoImportacion.DESCARTADO, frozenset(), False),
    ],
)
def test_tkt015_estados_que_admiten_analisis(
    estado: EstadoImportacion,
    tipos: frozenset[TipoErrorImportacion],
    esperado: bool,
) -> None:
    """TC-02 · HDU-001 esc. 18 · PA-15.7 — solo RECIBIDO o CON_ERRORES solo con interrupción."""
    assert puede_analizarse(estado, tipos) is esperado


_MENSAJES_INTERRUPCION = {
    MotivoInterrupcion.REINICIO: (
        "El análisis se interrumpió porque el servidor se reinició o dejó de responder "
        "mientras analizaba. El archivo no tiene la culpa: puedes reintentar el análisis."
    ),
    MotivoInterrupcion.EXCEPCION: (
        "El análisis terminó por un error inesperado del analizador. Puedes reintentar el "
        "análisis; si se repite, el archivo puede traer algo que el analizador no sabe leer: "
        "avisa con el identificador de esta importación."
    ),
    MotivoInterrupcion.TRABAJADOR_TERMINADO: (
        "El proceso que analizaba el archivo terminó de forma abrupta. Puedes reintentar el "
        "análisis; se hará con un proceso nuevo."
    ),
    MotivoInterrupcion.ARCHIVO_ILEGIBLE: (
        "No se pudo obtener el archivo de la importación para analizarlo. Puedes reintentar el "
        "análisis; si se repite, vuelve a subir el archivo como una importación nueva."
    ),
}


@pytest.mark.parametrize("motivo", list(MotivoInterrupcion))
def test_hdu001_esc29_mensajes_de_interrupcion_distinguen_la_causa(
    motivo: MotivoInterrupcion,
) -> None:
    """TC-03 · HDU-001 esc. 29 · CA-14 y CA-15 — PROCESO_INTERRUMPIDO y mensaje exacto por motivo."""
    error = error_de_interrupcion(motivo)
    assert error.tipo is TipoErrorImportacion.PROCESO_INTERRUMPIDO
    assert error.hoja is None and error.fila is None and error.columna is None
    assert error.valor_original is None
    assert error.mensaje == _MENSAJES_INTERRUPCION[motivo]


def test_hdu001_esc29_mensajes_de_interrupcion_son_distintos() -> None:
    mensajes = {error_de_interrupcion(m).mensaje for m in MotivoInterrupcion}
    assert len(mensajes) == len(MotivoInterrupcion)


def test_tkt015_mapa_de_insumos_existentes() -> None:
    """TC-04 · HDU-001 esc. 4 · P6 — normaliza clave y gana la primera unidad."""
    resultado = mapa_de_insumos_existentes([(" canal  x ", "PZA"), ("CANAL X", "KG")])
    assert resultado == {"CANAL X": "PZA"}
