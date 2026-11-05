"""TKT-015b · Barrido reutilizable (fila B1): TC-43 a TC-45."""

from __future__ import annotations

import ast
import sys
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto

BACKEND = Path(__file__).resolve().parents[1]
TRABAJOS = BACKEND / "trabajos"

PROHIBIDOS = frozenset({"cimenta", "servidor", "fastapi", "structlog"})


def _modulos_importados(ruta: Path) -> set[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    encontrados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                encontrados.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            encontrados.add(nodo.module.split(".")[0])
    return encontrados


def test_tkt015_dos_barridos_simultaneos_procesan_cada_id_una_vez(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-43 · CA-16 esc. 2 · HDU-001 esc. 29 — dos barridos concurrentes, un id vencido una vez."""
    from trabajos.barrido import DefinicionBarrido, barrer

    importacion_id = datos_presupuesto.importacion(
        estado="ANALIZANDO",
        latido=datetime.now(tz=UTC) - timedelta(minutes=5),
    )
    umbral = timedelta(seconds=60)
    anotados: list[uuid.UUID] = []
    candado = threading.Lock()
    barrera = threading.Barrier(2)
    resultados: list[tuple[uuid.UUID, ...]] = []
    errores: list[BaseException] = []

    def al_vencer(_sesion: Session, ids: Sequence[uuid.UUID]) -> None:
        with candado:
            anotados.extend(ids)

    definicion = DefinicionBarrido(
        nombre="importacion_prueba",
        tabla="importacion",
        estado_intermedio="ANALIZANDO",
        estado_vencido="CON_ERRORES",
        columna_marca="latido",
        umbral=umbral,
        al_vencer=al_vencer,
    )

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
    assert anotados == [importacion_id]

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


def test_tkt015_barrido_reutilizable_con_otra_definicion(
    base_de_prueba: str,
    conectar: Conectar,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-44 · CA-17 — otra tabla y estados con el mismo mecanismo de barrido."""
    from trabajos.barrido import DefinicionBarrido, barrer

    vencida_id = uuid.uuid4()
    vigente_id = uuid.uuid4()
    ahora = datetime.now(tz=UTC)

    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(
            """
            CREATE TABLE prueba_dos_pasos (
                id uuid PRIMARY KEY,
                estado text NOT NULL,
                creado_en timestamptz NOT NULL
            )
            """
        )
        migracion.execute(
            "INSERT INTO prueba_dos_pasos (id, estado, creado_en) VALUES (%s, %s, %s)",
            (vencida_id, "PENDIENTE", ahora - timedelta(hours=2)),
        )
        migracion.execute(
            "INSERT INTO prueba_dos_pasos (id, estado, creado_en) VALUES (%s, %s, %s)",
            (vigente_id, "PENDIENTE", ahora),
        )
        migracion.commit()

    recibidos: list[uuid.UUID] = []

    def al_vencer(_sesion: Session, ids: Sequence[uuid.UUID]) -> None:
        recibidos.extend(ids)

    definicion = DefinicionBarrido(
        nombre="dos_pasos",
        tabla="prueba_dos_pasos",
        estado_intermedio="PENDIENTE",
        estado_vencido="CADUCADO",
        columna_marca="creado_en",
        umbral=timedelta(hours=1),
        al_vencer=al_vencer,
        columna_id="id",
        columna_estado="estado",
    )

    sesion = fabrica_sesiones()
    try:
        devueltos = barrer(sesion, definicion)
        sesion.commit()
    finally:
        sesion.close()

    assert devueltos == (vencida_id,)
    assert recibidos == [vencida_id]

    with conectar("aplicacion", base_de_prueba) as conn:
        estados = dict(
            conn.execute(
                "SELECT id, estado FROM prueba_dos_pasos ORDER BY creado_en",
            ).fetchall()
        )
    assert estados[vencida_id] == "CADUCADO"
    assert estados[vigente_id] == "PENDIENTE"

    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute("DROP TABLE prueba_dos_pasos")
        migracion.commit()


def test_tkt015_trabajos_solo_importa_stdlib_y_sqlalchemy() -> None:
    """TC-45 · CA-17 · CA-R2 — trabajos/ solo stdlib y sqlalchemy."""
    assert TRABAJOS.is_dir(), "falta el paquete backend/trabajos (B1 verde)"
    archivos = sorted(TRABAJOS.rglob("*.py"))
    assert archivos, "trabajos/ debe tener al menos barrido.py"

    stdlib = sys.stdlib_module_names
    for archivo in archivos:
        raices = _modulos_importados(archivo)
        for raiz in raices:
            assert raiz not in PROHIBIDOS, (archivo.name, raiz)
            assert raiz in stdlib or raiz == "sqlalchemy", (archivo.name, raiz)


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)
