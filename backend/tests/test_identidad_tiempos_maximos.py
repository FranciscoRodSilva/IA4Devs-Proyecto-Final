"""Tiempos máximos (TKT-003, fila 7): TC-50, TC-51 y TC-52 de CA-8, más la guarda de migración.

Los valores salen de D-2: aplicación `lock_timeout = 5s` y `statement_timeout = 15s`; lectura
`5s` y `60s`; migración, ninguno en este ticket. `ALTER ROLE … SET` solo afecta a las sesiones
nuevas, así que todos los casos abren una conexión nueva y no ejecutan ningún `SET`: una
prueba que fijara el valor en su propia sesión pasaría sin demostrar nada.

TC-51 y TC-52 duran unos 5 y 15 s por diseño: probar con valores rebajados demostraría el
mecanismo pero no el valor aprobado.
"""

import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]

TABLA_DE_BLOQUEO = "bloqueo_tkt003"
SALVAGUARDA_SEGUNDOS = 30.0


def tiempos_de_la_sesion(conexion: psycopg.Connection[tuple[Any, ...]]) -> dict[str, str]:
    """Valor con el que arranca la sesión, tal como lo muestra `SHOW`; sin ningún `SET` previo."""
    return {
        parametro: str((conexion.execute(f"SHOW {parametro}").fetchone() or ("",))[0])
        for parametro in ("lock_timeout", "statement_timeout")
    }


def test_tkt003_ca08_esc01_tiempos_fijados_en_el_rol(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-50 · CA-8 esc. 1 · RNF-16 — el rol, no la sesión, trae los tiempos máximos de D-2."""
    with (
        conectar("aplicacion", base_de_prueba) as aplicacion,
        conectar("lectura", base_de_prueba) as lectura,
    ):
        de_aplicacion = tiempos_de_la_sesion(aplicacion)
        de_lectura = tiempos_de_la_sesion(lectura)

    assert {"aplicacion": de_aplicacion, "lectura": de_lectura} == {
        "aplicacion": {"lock_timeout": "5s", "statement_timeout": "15s"},
        "lectura": {"lock_timeout": "5s", "statement_timeout": "1min"},
    }


def test_tkt003_ca08_esc01_migracion_sin_tiempos_en_este_ticket(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """CA-8 esc. 1 · D-2 — el rol de migración no lleva tiempos: una migración larga no se corta.

    Nace en verde: hoy el rol no tiene ninguno. Es la guarda de D-2 contra quien los añada al
    rol de migración (lo decide TKT-058); demostrar que puede fallar es el mutante de la fila 9.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        de_migracion = tiempos_de_la_sesion(migracion)

    assert de_migracion == {"lock_timeout": "0", "statement_timeout": "0"}


def test_tkt003_ca08_esc02_espera_de_bloqueo_se_corta(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-51 · CA-8 esc. 2 · RNF-16 — B no espera a A más de `lock_timeout`: 55P03, no 57014.

    La tabla desechable la crea el rol de migración después de la migración, así que nace con
    los privilegios por omisión de la fila 4, entre ellos `UPDATE`, que `FOR UPDATE` exige.
    A queda en espera inactiva con el bloqueo tomado y B se ejecuta en este mismo hilo.

    La salvaguarda no sincroniza nada: si no hay ningún tiempo máximo cierra A a los 30 s, B
    obtiene la fila sin error y el caso falla en lugar de colgarse.
    """
    fila = uuid.uuid4()
    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(f"CREATE TABLE {TABLA_DE_BLOQUEO} (id uuid PRIMARY KEY)")
    with conectar("aplicacion", base_de_prueba) as preparacion:
        preparacion.execute(f"INSERT INTO {TABLA_DE_BLOQUEO} VALUES (%s)", (fila,))
    consulta = f"SELECT id FROM {TABLA_DE_BLOQUEO} WHERE id = %s FOR UPDATE"

    conexion_a = conectar("aplicacion", base_de_prueba, autocommit=False)
    conexion_b = conectar("aplicacion", base_de_prueba)
    tomada = conexion_a.execute(consulta, (fila,)).fetchone()
    assert tomada == (fila,), "A debe tomar el bloqueo antes de que B lo pida"

    salvaguarda = threading.Timer(SALVAGUARDA_SEGUNDOS, conexion_a.close)
    salvaguarda.start()
    try:
        inicio = time.monotonic()
        with pytest.raises(psycopg.errors.LockNotAvailable) as error:
            conexion_b.execute(consulta, (fila,))
        espera = time.monotonic() - inicio
    finally:
        salvaguarda.cancel()

    assert error.value.sqlstate == "55P03"
    assert 4.5 <= espera <= 7.0, (
        f"B esperó {espera:.1f} s; lock_timeout debe cortarla hacia los 5 s"
    )

    conexion_a.rollback()
    assert conexion_b.execute(consulta, (fila,)).fetchone() == (fila,)


def test_tkt003_ca08_esc03_consulta_larga_se_cancela(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-52 · CA-8 esc. 3 · RNF-16 — una sentencia de 20 s se cancela hacia los 15 s: 57014."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        inicio = time.monotonic()
        with pytest.raises(psycopg.errors.QueryCanceled) as error:
            aplicacion.execute("SELECT pg_sleep(20)")
        duracion = time.monotonic() - inicio

    assert error.value.sqlstate == "57014"
    assert 14.0 <= duracion <= 18.0, (
        f"La consulta duró {duracion:.1f} s; statement_timeout debe cancelarla hacia los 15 s"
    )
