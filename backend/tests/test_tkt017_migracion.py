"""TKT-017a1 · Migración `0011` (TC-A01, TC-A02)."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from sqlalchemy.exc import DBAPIError

from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

REVISION_0010 = "0010"
REVISION_0011 = "0011"

COLUMNAS_NULABLES: tuple[tuple[str, str], ...] = (
    ("area", "tipo_unidad"),
    ("apu", "fecha_analisis"),
    ("apu", "analista"),
    ("apu_cargo", "porcentaje"),
    ("apu_cargo", "base_calculo"),
)


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def sqlstate_de(error: DBAPIError) -> str | None:
    origen = error.orig
    assert isinstance(origen, psycopg.Error), repr(origen)
    return origen.sqlstate


def nulabilidad(
    conexion: Conexion, columnas: tuple[tuple[str, str], ...] = COLUMNAS_NULABLES
) -> dict[tuple[str, str], str]:
    resultado: dict[tuple[str, str], str] = {}
    for tabla, columna in columnas:
        fila = conexion.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
            (tabla, columna),
        ).fetchone()
        assert fila is not None, (tabla, columna)
        resultado[(tabla, columna)] = str(fila[0])
    return resultado


def test_tkt017_caa11_sube_y_baja_sin_nulos(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-A01 · CA-A11 esc. 1 — ciclo completo sin nulos en las cinco columnas."""
    migrar(base_vacia, REVISION_0010)
    with conectar("migracion", base_vacia) as administrador:
        antes = nulabilidad(administrador)
        for clave in COLUMNAS_NULABLES:
            assert antes[clave] == "NO", clave

    migrar(base_vacia, REVISION_0011)
    with conectar("migracion", base_vacia) as administrador:
        subida = nulabilidad(administrador)
        version_subida = version_de_alembic(administrador)
    assert version_subida == [(REVISION_0011,)]
    for clave in COLUMNAS_NULABLES:
        assert subida[clave] == "YES", clave

    migrar(base_vacia, REVISION_0010, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        tras_bajar = nulabilidad(administrador)
        version_bajada = version_de_alembic(administrador)
    assert version_bajada == [(REVISION_0010,)]
    assert tras_bajar == antes

    migrar(base_vacia, REVISION_0011)
    with conectar("migracion", base_vacia) as administrador:
        segunda = nulabilidad(administrador)
        version_final = version_de_alembic(administrador)
    assert version_final == [(REVISION_0011,)]
    assert segunda == subida


def _nulo_en(tabla: str, columna: str, datos: DatosPresupuesto) -> None:
    if tabla == "area":
        datos.area(tipo_unidad=None)
        return
    if tabla == "apu":
        datos.apu(fecha_analisis=None, analista=None)
        return
    assert tabla == "apu_cargo" and columna in ("porcentaje", "base_calculo")
    apu_id = datos.apu()
    kwargs: dict[str, Any] = {"apu_id": apu_id, "importe": Decimal("1.0000")}
    if columna == "porcentaje":
        kwargs["porcentaje"] = None
    else:
        kwargs["base_calculo"] = None
    datos.apu_cargo(**kwargs)


@pytest.mark.parametrize(
    "tabla,columna",
    [(t, c) for t, c in COLUMNAS_NULABLES],
    ids=[f"{t}.{c}" for t, c in COLUMNAS_NULABLES],
)
def test_tkt017_caa11_la_bajada_se_niega_con_nulos(
    tabla: str,
    columna: str,
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-A02 · CA-A11 esc. 2 — `downgrade` con un `NULL` responde `P0001` y no cambia la versión."""
    # `base_de_prueba` llega en la cabeza (0012): se baja a 0011 para ejercitar la guarda de 0011.
    migrar(base_de_prueba, REVISION_0011, "downgrade")
    _nulo_en(tabla, columna, datos_presupuesto)
    with conectar("migracion", base_de_prueba) as administrador:
        nulo_antes = nulabilidad(administrador)
        version_antes = version_de_alembic(administrador)
    assert version_antes == [(REVISION_0011,)]
    for clave in COLUMNAS_NULABLES:
        assert nulo_antes[clave] == "YES", clave

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, REVISION_0010, "downgrade")

    texto = str(rechazo.value)
    assert sqlstate_de(rechazo.value) == "P0001", texto
    assert "La bajada de 0011 se niega" in texto, texto
    assert f"{tabla}.{columna}" in texto, texto
    with conectar("migracion", base_de_prueba) as administrador:
        assert nulabilidad(administrador) == nulo_antes
        assert version_de_alembic(administrador) == [(REVISION_0011,)]


def test_tkt017_caa11_bloqueo_de_guarda_con_sesion_sin_confirmar(
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto_en: Callable[[str], DatosPresupuesto],
) -> None:
    """TC-A02 — la guarda toma `ACCESS EXCLUSIVE` antes de comprobar (`area.tipo_unidad`)."""
    # `base_de_prueba` llega en la cabeza (0012): se baja a 0011 para ejercitar la guarda de 0011.
    migrar(base_de_prueba, REVISION_0011, "downgrade")
    datos = datos_presupuesto_en(base_de_prueba)
    observador = conectar("migracion", base_de_prueba)

    sesion_a = conectar("aplicacion", base_de_prueba, autocommit=False)
    datos.area(tipo_unidad=None, conexion=sesion_a)
    pid_de_a = sesion_a.info.backend_pid

    def migracion_esperando_a() -> bool:
        fila = observador.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock' AND %s = ANY(pg_blocking_pids(pid))",
            (pid_de_a,),
        ).fetchone()
        return fila is not None and fila[0] > 0

    with ThreadPoolExecutor(max_workers=1) as hilos:
        bajada = hilos.submit(migrar, base_de_prueba, REVISION_0010, "downgrade")
        try:
            esperar_hasta(lambda: bajada.done() or migracion_esperando_a())
            esperaba_a = not bajada.done() and migracion_esperando_a()
        finally:
            sesion_a.commit()
        error = bajada.exception(timeout=60)

    assert esperaba_a, "La migración debía quedar esperando el bloqueo de la sesión A"
    assert isinstance(error, DBAPIError), f"Esperaba P0001, obtuve {error!r}"
    assert sqlstate_de(error) == "P0001", str(error)
    assert "La bajada de 0011 se niega" in str(error), str(error)
    assert version_de_alembic(observador) == [(REVISION_0011,)]
