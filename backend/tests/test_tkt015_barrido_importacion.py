"""TKT-015b · Barrido de importación (fila B2): TC-43b y TC-46 a TC-49."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.dominio.importacion import (
    MotivoInterrupcion,
    error_de_interrupcion,
)
from trabajos.barrido import barrer

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)


def _errores_db(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with conectar("aplicacion", base) as conn:
        return conn.execute(
            "SELECT hoja, fila, columna, tipo, mensaje, valor_original "
            "FROM importacion_error WHERE importacion_id = %s ORDER BY fila NULLS FIRST, columna",
            (importacion_id,),
        ).fetchall()


def _conteo_analizando_obra(conectar: Conectar, base: str, obra_id: uuid.UUID) -> int:
    with conectar("aplicacion", base) as conn:
        fila = conn.execute(
            "SELECT count(*) FROM importacion WHERE obra_id = %s AND estado = 'ANALIZANDO'",
            (obra_id,),
        ).fetchone()
    assert fila is not None
    return int(fila[0])


def test_hdu001_esc29_dos_barridos_un_solo_proceso_interrumpido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-43b · CA-16 esc. 2 · HDU-001 esc. 29 — concurrencia con gancho real, un PROCESO_INTERRUMPIDO."""
    from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion

    importacion_id = datos_presupuesto.importacion(
        estado="ANALIZANDO",
        latido=datetime.now(tz=UTC) - timedelta(minutes=5),
    )
    umbral = timedelta(seconds=60)
    definicion = definicion_barrido_importacion(umbral)
    barrera = threading.Barrier(2)
    resultados: list[tuple[uuid.UUID, ...]] = []
    errores: list[BaseException] = []

    def hilo_barrido() -> None:
        try:
            barrera.wait(timeout=10)
            sesion = fabrica_sesiones()
            try:
                devueltos = barrer(sesion, definicion)
                sesion.commit()
                resultados.append(devueltos)
            except DBAPIError as error:
                if getattr(getattr(error, "orig", None), "sqlstate", None) == "55P03":
                    errores.append(error)
                else:
                    raise
            finally:
                sesion.close()
        except BaseException as exc:
            errores.append(exc)

    hilos = [threading.Thread(target=hilo_barrido) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert not errores, errores
    assert sorted(resultados, key=len, reverse=True) == [
        (importacion_id,),
        (),
    ], resultados

    sesion = fabrica_sesiones()
    try:
        assert barrer(sesion, definicion) == ()
        sesion.commit()
    finally:
        sesion.close()

    with conectar("aplicacion", base_de_prueba) as conn:
        fila = conn.execute(
            "SELECT estado FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert fila is not None
    assert fila[0] == "CON_ERRORES"

    esperado = error_de_interrupcion(MotivoInterrupcion.REINICIO)
    errores_db = _errores_db(conectar, base_de_prueba, importacion_id)
    assert len(errores_db) == 1
    hoja, fila_n, columna, tipo, mensaje, valor = errores_db[0]
    assert hoja is None and fila_n is None and columna is None
    assert tipo == "PROCESO_INTERRUMPIDO"
    assert mensaje == esperado.mensaje
    assert valor is None


def test_hdu001_esc29_barrido_marca_la_interrumpida(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-46 · CA-15 · HDU-001 esc. 29 — latido vencido, CON_ERRORES y reintento admite iniciar_analisis."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import iniciar_analisis
    from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion

    obra_id = datos_presupuesto.obra(codigo="BR-046-25")
    umbral = timedelta(seconds=60)
    importacion_id = datos_presupuesto.importacion(
        obra_id=obra_id,
        estado="ANALIZANDO",
        latido=datetime.now(tz=UTC) - umbral * 2,
    )
    definicion = definicion_barrido_importacion(umbral)

    sesion = fabrica_sesiones()
    try:
        assert barrer(sesion, definicion) == (importacion_id,)
        sesion.commit()
    finally:
        sesion.close()

    with conectar("aplicacion", base_de_prueba) as conn:
        estado = conn.execute(
            "SELECT estado FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert estado is not None
    assert estado[0] == "CON_ERRORES"
    assert _conteo_analizando_obra(conectar, base_de_prueba, obra_id) == 0

    esperado = error_de_interrupcion(MotivoInterrupcion.REINICIO)
    errores_db = _errores_db(conectar, base_de_prueba, importacion_id)
    assert len(errores_db) == 1
    assert errores_db[0][3] == "PROCESO_INTERRUMPIDO"
    assert errores_db[0][0] is None and errores_db[0][1] is None and errores_db[0][2] is None
    assert errores_db[0][4] == esperado.mensaje

    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    assert trabajo.importacion_id == importacion_id


def test_hdu001_esc29_barrido_latido_nulo_es_vencido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-47 · CA-16 · PA-15.5 — latido nulo cuenta como vencido."""
    from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion

    importacion_id = datos_presupuesto.importacion(estado="ANALIZANDO", latido=None)
    definicion = definicion_barrido_importacion(timedelta(seconds=60))

    sesion = fabrica_sesiones()
    try:
        assert barrer(sesion, definicion) == (importacion_id,)
        sesion.commit()
    finally:
        sesion.close()

    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == 1
    with conectar("aplicacion", base_de_prueba) as conn:
        estado = conn.execute(
            "SELECT estado FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert estado == ("CON_ERRORES",)


def test_hdu001_esc29_barrido_no_toca_lo_vivo(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-48 · CA-16 esc. 1 — no altera ANALIZANDO vivo, VALIDADO ni CON_ERRORES ya cerrada."""
    from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion

    ahora = datetime.now(tz=UTC)
    viva_id = datos_presupuesto.importacion(
        estado="ANALIZANDO",
        latido=ahora - timedelta(seconds=1),
    )
    validada_id = datos_presupuesto.importacion(
        estado="VALIDADO", latido=ahora - timedelta(hours=1)
    )
    cerrada_id = datos_presupuesto.importacion(
        estado="CON_ERRORES",
        latido=ahora - timedelta(hours=1),
    )
    datos_presupuesto.error_importacion(importacion_id=cerrada_id, tipo="REF_ROTA")
    n_errores_cerrada = len(_errores_db(conectar, base_de_prueba, cerrada_id))

    definicion = definicion_barrido_importacion(timedelta(seconds=60))
    sesion = fabrica_sesiones()
    try:
        assert barrer(sesion, definicion) == ()
        sesion.commit()
    finally:
        sesion.close()

    with conectar("aplicacion", base_de_prueba) as conn:
        estados = dict(
            conn.execute(
                "SELECT id, estado FROM importacion WHERE id = ANY(%s)",
                ([viva_id, validada_id, cerrada_id],),
            ).fetchall()
        )
    assert estados[viva_id] == "ANALIZANDO"
    assert estados[validada_id] == "VALIDADO"
    assert estados[cerrada_id] == "CON_ERRORES"
    assert _errores_db(conectar, base_de_prueba, viva_id) == []
    assert len(_errores_db(conectar, base_de_prueba, cerrada_id)) == n_errores_cerrada


def test_tkt015_definicion_barrido_importacion() -> None:
    """TC-49 · CA-17 — forma de la definición y exportación en la interfaz publicada."""
    from datetime import timedelta

    from cimenta.presupuesto import interfaz
    from cimenta.presupuesto.aplicacion.barrido_importacion import (
        definicion_barrido_importacion as desde_aplicacion,
    )

    umbral = timedelta(seconds=60)
    definicion = desde_aplicacion(umbral)
    assert definicion.nombre == "importacion"
    assert definicion.tabla == "importacion"
    assert definicion.estado_intermedio == "ANALIZANDO"
    assert definicion.estado_vencido == "CON_ERRORES"
    assert definicion.columna_marca == "latido"
    assert definicion.umbral == umbral
    assert "definicion_barrido_importacion" in interfaz.__all__
    assert interfaz.definicion_barrido_importacion is desde_aplicacion
