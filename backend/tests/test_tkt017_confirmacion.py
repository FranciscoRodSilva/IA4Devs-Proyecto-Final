"""Decisiones de estado de la confirmación, en dominio puro (TKT-017a3 · F002 de la auditoría de arquitectura).

Qué decide `dominio/materializacion.py` y qué solo orquesta `aplicacion/materializacion.py`: si una
importación se puede confirmar y si la obra admite una línea base nueva son reglas (`RN-01`, `CA-A2`,
`CA-A4`, `CA-A8`), así que viven en dos funciones puras; el caso de uso las llama y convierte su
rechazo en el contrato de error. Son dos funciones, no una, por el orden de bloqueos del caso de uso:
el estado de la importación se comprueba antes de bloquear la obra y lo demás, después.

Contrato que fijan estas pruebas (en `cimenta.presupuesto.dominio.materializacion`):

- `evaluar_importacion_confirmable(estado: EstadoImportacion) -> ConfirmacionAdmitida | ConfirmacionRechazada`
- `evaluar_confirmacion_en_obra(*, estado_obra: str, congelada: LineaBaseDeObra | None,
  borrador: LineaBaseDeObra | None, reemplazar_borrador: bool, motivo_reemplazo: str | None)
  -> ConfirmacionAdmitida | ConfirmacionRechazada`
- `LineaBaseDeObra(id: UUID, version: int)`: la congelada vigente o el borrador de la obra.
- `ConfirmacionAdmitida()` y `ConfirmacionRechazada(causa: CausaRechazoConfirmacion, datos: Mapping[str, object])`.
- `CausaRechazoConfirmacion` (`StrEnum`): `IMPORTACION_CON_ERRORES`, `IMPORTACION_EN_OTRO_ESTADO`,
  `OBRA_CON_CONGELADA`, `OBRA_FUERA_DE_PLANEACION`, `REEMPLAZO_NO_CONFIRMADO`,
  `MOTIVO_REEMPLAZO_OBLIGATORIO`.

`datos` lleva los valores de dominio tal cual (`UUID`, `int`, `EstadoImportacion`, `str`): el caso de
uso los vuelve cadenas y arma el mensaje, el detalle y las acciones. El formato de la preparación no
entra aquí: se lee del JSON, en infraestructura, después de estas decisiones (paso 7 del diseño).

Orden en la obra: congelada, estado de la obra, borrador sin confirmar, motivo en blanco. Invertir
los dos primeros es el mutante `M-A5`.
"""

from __future__ import annotations

import uuid

import pytest

from cimenta.presupuesto.dominio.importacion import EstadoImportacion
from cimenta.presupuesto.dominio.materializacion import (
    CausaRechazoConfirmacion,
    ConfirmacionAdmitida,
    ConfirmacionRechazada,
    LineaBaseDeObra,
    ResultadoConfirmacion,
    evaluar_confirmacion_en_obra,
    evaluar_importacion_confirmable,
)

BORRADOR_ID = uuid.UUID("8f7e6d5c-4b3a-4291-8f7e-6d5c4b3a2918")
CONGELADA_ID = uuid.UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
MOTIVO = "Corrección de cantidades del nivel 3"


def _rechazada(causa: CausaRechazoConfirmacion, **datos: object) -> ConfirmacionRechazada:
    return ConfirmacionRechazada(causa=causa, datos=datos)


def _linea(identificador: uuid.UUID, version: int) -> LineaBaseDeObra:
    return LineaBaseDeObra(id=identificador, version=version)


def _en_obra(
    *,
    estado_obra: str = "PLANEACION",
    congelada: tuple[uuid.UUID, int] | None = None,
    borrador: tuple[uuid.UUID, int] | None = None,
    reemplazar_borrador: bool = False,
    motivo_reemplazo: str | None = None,
) -> ResultadoConfirmacion:
    return evaluar_confirmacion_en_obra(
        estado_obra=estado_obra,
        congelada=None if congelada is None else _linea(*congelada),
        borrador=None if borrador is None else _linea(*borrador),
        reemplazar_borrador=reemplazar_borrador,
        motivo_reemplazo=motivo_reemplazo,
    )


# --------------------------------------------------------------------------- la importación · CA-A2


def test_tkt017_caa02_una_importacion_validada_se_puede_confirmar() -> None:
    """CA-A2 · RN-01 — solo `VALIDADO` es confirmable."""
    assert evaluar_importacion_confirmable(EstadoImportacion.VALIDADO) == ConfirmacionAdmitida()


def test_tkt017_caa02_una_importacion_con_errores_no_se_confirma() -> None:
    """CA-A2 esc. 1 · RN-01 — `CON_ERRORES` tiene su propia causa, distinta de la de otro estado."""
    resultado = evaluar_importacion_confirmable(EstadoImportacion.CON_ERRORES)
    assert isinstance(resultado, ConfirmacionRechazada)

    assert resultado == _rechazada(
        CausaRechazoConfirmacion.IMPORTACION_CON_ERRORES, estado=EstadoImportacion.CON_ERRORES
    )
    assert resultado.causa != CausaRechazoConfirmacion.IMPORTACION_EN_OTRO_ESTADO


@pytest.mark.parametrize(
    "estado",
    [
        EstadoImportacion.RECIBIDO,
        EstadoImportacion.ANALIZANDO,
        EstadoImportacion.CONFIRMADO,
        EstadoImportacion.DESCARTADO,
    ],
)
def test_tkt017_caa02_una_importacion_en_otro_estado_no_se_confirma(
    estado: EstadoImportacion,
) -> None:
    """CA-A2 esc. 2 · RN-01 — cualquier otro estado: `IMPORTACION_EN_OTRO_ESTADO` con el estado actual."""
    assert evaluar_importacion_confirmable(estado) == _rechazada(
        CausaRechazoConfirmacion.IMPORTACION_EN_OTRO_ESTADO, estado=estado
    )


# --------------------------------------------------------------------------- la obra · CA-A4 y CA-A8


def test_tkt017_caa01_una_obra_en_planeacion_sin_lineas_base_admite_la_confirmacion() -> None:
    """CA-A1 · RN-01 — obra en `PLANEACION`, sin congelada ni borrador: admitida (el reemplazo se ignora)."""
    assert _en_obra() == ConfirmacionAdmitida()
    assert _en_obra(reemplazar_borrador=True, motivo_reemplazo=None) == ConfirmacionAdmitida()


def test_tkt017_caa04_una_obra_con_congelada_no_admite_otra_importacion() -> None:
    """CA-A4 esc. 1 · RN-01 — `OBRA_CON_CONGELADA` con el id y la versión de la vigente."""
    assert _en_obra(estado_obra="ACTIVA", congelada=(CONGELADA_ID, 2)) == _rechazada(
        CausaRechazoConfirmacion.OBRA_CON_CONGELADA,
        linea_base_vigente_id=CONGELADA_ID,
        version_vigente=2,
    )


@pytest.mark.parametrize("estado_obra", ["PLANEACION", "ACTIVA", "SUSPENDIDA", "CERRADA"])
def test_tkt017_caa04_la_congelada_se_comprueba_antes_que_el_estado_de_la_obra(
    estado_obra: str,
) -> None:
    """CA-A4 esc. 1 · RN-01 · mutante `M-A5` — una obra con congelada está `ACTIVA`: manda la congelada.

    Si el estado de la obra se comprobara primero, una obra `ACTIVA` con congelada respondería
    `OBRA_FUERA_DE_PLANEACION`.
    """
    assert _en_obra(estado_obra=estado_obra, congelada=(CONGELADA_ID, 1)) == _rechazada(
        CausaRechazoConfirmacion.OBRA_CON_CONGELADA,
        linea_base_vigente_id=CONGELADA_ID,
        version_vigente=1,
    )


@pytest.mark.parametrize("estado_obra", ["ACTIVA", "SUSPENDIDA", "CERRADA"])
def test_tkt017_caa04_una_obra_fuera_de_planeacion_no_admite_la_confirmacion(
    estado_obra: str,
) -> None:
    """CA-A4 esc. 2 · RN-01 — sin congelada, `OBRA_FUERA_DE_PLANEACION` con el estado de la obra."""
    assert _en_obra(estado_obra=estado_obra) == _rechazada(
        CausaRechazoConfirmacion.OBRA_FUERA_DE_PLANEACION, estado_obra=estado_obra
    )


def test_tkt017_caa04_el_estado_de_la_obra_se_comprueba_antes_que_el_borrador() -> None:
    """CA-A4 · CA-A8 · RN-01 — una obra `SUSPENDIDA` con borrador sin reemplazo confirmado: manda el estado."""
    assert _en_obra(estado_obra="SUSPENDIDA", borrador=(BORRADOR_ID, 1)) == _rechazada(
        CausaRechazoConfirmacion.OBRA_FUERA_DE_PLANEACION, estado_obra="SUSPENDIDA"
    )


def test_tkt017_caa04_la_congelada_se_comprueba_antes_que_el_borrador() -> None:
    """CA-A4 · CA-A8 · RN-01 — con congelada y borrador a la vez, manda la congelada."""
    assert _en_obra(
        estado_obra="ACTIVA", congelada=(CONGELADA_ID, 3), borrador=(BORRADOR_ID, 4)
    ) == _rechazada(
        CausaRechazoConfirmacion.OBRA_CON_CONGELADA,
        linea_base_vigente_id=CONGELADA_ID,
        version_vigente=3,
    )


@pytest.mark.parametrize("motivo", [None, MOTIVO], ids=["sin_motivo", "con_motivo"])
def test_tkt017_caa08_un_borrador_sin_reemplazo_confirmado_se_rechaza(motivo: str | None) -> None:
    """CA-A8 esc. 1 · RN-01 — `REEMPLAZO_NO_CONFIRMADO` con el id y la versión del borrador.

    El motivo solo cuenta si el reemplazo se confirma.
    """
    assert _en_obra(
        borrador=(BORRADOR_ID, 1), reemplazar_borrador=False, motivo_reemplazo=motivo
    ) == _rechazada(
        CausaRechazoConfirmacion.REEMPLAZO_NO_CONFIRMADO,
        linea_base_borrador_id=BORRADOR_ID,
        version=1,
    )


@pytest.mark.parametrize(
    "motivo", [None, "", "   ", "\t\n "], ids=["nulo", "vacio", "blanco", "tab"]
)
def test_tkt017_caa08_un_reemplazo_confirmado_sin_motivo_se_rechaza(motivo: str | None) -> None:
    """CA-A8 esc. 2 · RN-01 — `MOTIVO_REEMPLAZO_OBLIGATORIO`, sin más datos que la causa."""
    assert _en_obra(
        borrador=(BORRADOR_ID, 1), reemplazar_borrador=True, motivo_reemplazo=motivo
    ) == _rechazada(CausaRechazoConfirmacion.MOTIVO_REEMPLAZO_OBLIGATORIO)


@pytest.mark.parametrize("motivo", [MOTIVO, "  x  "], ids=["motivo", "motivo_con_espacios"])
def test_tkt017_caa09_un_reemplazo_confirmado_con_motivo_se_admite(motivo: str) -> None:
    """CA-A9 · RN-01 — borrador, reemplazo confirmado y motivo con texto: admitida."""
    assert (
        _en_obra(borrador=(BORRADOR_ID, 2), reemplazar_borrador=True, motivo_reemplazo=motivo)
        == ConfirmacionAdmitida()
    )


def test_tkt017_caa08_el_motivo_no_se_exige_si_no_hay_borrador() -> None:
    """CA-A8 · diseño «Orden de comprobaciones» 6 — sin borrador, `reemplazar_borrador` se ignora."""
    assert _en_obra(reemplazar_borrador=True, motivo_reemplazo="   ") == ConfirmacionAdmitida()


def test_tkt017_caa08_el_reemplazo_sin_confirmar_va_antes_que_el_motivo() -> None:
    """CA-A8 · diseño «Orden de comprobaciones» 6 — sin confirmar el reemplazo no se mira el motivo."""
    resultado = _en_obra(borrador=(BORRADOR_ID, 1), reemplazar_borrador=False, motivo_reemplazo="")

    assert isinstance(resultado, ConfirmacionRechazada)
    assert resultado.causa == CausaRechazoConfirmacion.REEMPLAZO_NO_CONFIRMADO


# --------------------------------------------------------------------------- el contrato del módulo


@pytest.mark.parametrize(
    "decision",
    [evaluar_importacion_confirmable, evaluar_confirmacion_en_obra],
    ids=["importacion", "obra"],
)
def test_tkt017_caa02_las_decisiones_citan_la_regla_que_implementan(
    decision: object,
) -> None:
    """Convenciones · «Cada regla lleva su identificador» — el docstring dice `Implementa RN-01`."""
    documentacion = decision.__doc__

    assert documentacion is not None
    assert "Implementa RN-01" in documentacion


def test_tkt017_caa04_el_rechazo_es_un_valor_inmutable() -> None:
    """Dominio puro — `ConfirmacionRechazada` y `LineaBaseDeObra` son valores: no se modifican."""
    rechazada = _rechazada(CausaRechazoConfirmacion.OBRA_FUERA_DE_PLANEACION, estado_obra="CERRADA")
    linea = _linea(BORRADOR_ID, 1)

    with pytest.raises(AttributeError):
        rechazada.causa = CausaRechazoConfirmacion.OBRA_CON_CONGELADA  # type: ignore[misc]
    with pytest.raises(AttributeError):
        linea.version = 2  # type: ignore[misc]
