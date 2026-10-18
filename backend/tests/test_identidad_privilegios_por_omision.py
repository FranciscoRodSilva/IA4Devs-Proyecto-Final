"""Privilegios por omisión (TKT-003, fila 4): TC-31, TC-32, TC-33, TC-40 y TC-41.

Una tabla que crea `cimenta_migracion` DESPUÉS de la migración debe nacer con los privilegios
de CA-5 sin que nadie haga `GRANT` tabla por tabla. Las tablas de identidad no lo prueban:
las cubre `GRANT` explícito; solo una tabla posterior detecta que falta `ALTER DEFAULT PRIVILEGES`.
"""

from collections.abc import Callable
from typing import Any

import psycopg
import pytest

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]

TABLA_POSTERIOR = "prueba_permisos"
PRIVILEGIOS_AJENOS_A_LA_APLICACION = ("TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN")


def privilegios(conexion: psycopg.Connection[tuple[Any, ...]], tabla: str, rol: str) -> set[str]:
    """Conjunto de `privilege_type` que `relacl` concede al rol; vacío si no concede ninguno."""
    filas = conexion.execute(
        "SELECT a.privilege_type FROM pg_class c "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "JOIN pg_roles g ON g.oid = a.grantee "
        "WHERE c.oid = to_regclass(%s) AND g.rolname = %s",
        (tabla, f"cimenta_{rol}"),
    ).fetchall()
    return {str(fila[0]) for fila in filas}


@pytest.fixture
def tabla_posterior(base_de_prueba: str, conectar: Conectar) -> str:
    """`prueba_permisos` creada por el rol de migración después de la migración, con una fila."""
    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(f"CREATE TABLE {TABLA_POSTERIOR} (id uuid PRIMARY KEY)")
        migracion.execute(f"INSERT INTO {TABLA_POSTERIOR} VALUES (gen_random_uuid())")
    return TABLA_POSTERIOR


def test_tkt003_ca05_esc02_tabla_posterior_nace_con_permisos(
    base_de_prueba: str, conectar: Conectar, tabla_posterior: str
) -> None:
    """TC-31 · CA-5 esc. 2 — la aplicación lee y escribe; la lectura solo lee."""
    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = privilegios(migracion, tabla_posterior, "aplicacion")
        de_lectura = privilegios(migracion, tabla_posterior, "lectura")

    assert de_aplicacion == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    assert de_lectura == {"SELECT"}


def test_tkt003_ca05_esc03_aplicacion_sin_privilegios_de_mas_en_tabla_posterior(
    base_de_prueba: str, conectar: Conectar, tabla_posterior: str
) -> None:
    """TC-32 · CA-5 esc. 3 — la aplicación nunca recibe TRUNCATE, REFERENCES, TRIGGER ni MAINTAIN.

    Precondición: la aplicación sí tiene `SELECT`. Sin ella los cuatro `false` serían ciertos
    por una tabla sin ningún privilegio, y el caso nacería en verde sin afirmar nada.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        tiene = {
            privilegio: migracion.execute(
                "SELECT has_table_privilege('cimenta_aplicacion', %s, %s)",
                (tabla_posterior, privilegio),
            ).fetchone()
            for privilegio in ("SELECT", *PRIVILEGIOS_AJENOS_A_LA_APLICACION)
        }

    assert tiene["SELECT"] == (True,)
    assert {p: tiene[p] for p in PRIVILEGIOS_AJENOS_A_LA_APLICACION} == {
        p: (False,) for p in PRIVILEGIOS_AJENOS_A_LA_APLICACION
    }


def test_tkt003_ca05_esc03_aplicacion_sin_create_en_el_esquema(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-33 · CA-5 esc. 3 — ni la aplicación ni la lectura crean objetos en `public` ni en la base.

    Nace en verde: PostgreSQL 15 y posteriores no conceden `CREATE` a `PUBLIC`. Su dependencia
    del privilegio la demuestra el mutante MP-11 (fila 9). La precondición de `USAGE` asegura
    que el caso mira el esquema y los roles correctos.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        resultado = {
            (rol, objeto, "CREATE"): migracion.execute(consulta, (f"cimenta_{rol}",)).fetchone()
            for rol in ("aplicacion", "lectura")
            for objeto, consulta in (
                ("esquema", "SELECT has_schema_privilege(%s, 'public', 'CREATE')"),
                ("base", "SELECT has_database_privilege(%s, current_database(), 'CREATE')"),
            )
        }
        con_uso = [
            migracion.execute(
                "SELECT has_schema_privilege(%s, 'public', 'USAGE')", (f"cimenta_{rol}",)
            ).fetchone()
            for rol in ("aplicacion", "lectura")
        ]

    assert con_uso == [(True,), (True,)]
    assert resultado == {
        ("aplicacion", "esquema", "CREATE"): (False,),
        ("aplicacion", "base", "CREATE"): (False,),
        ("lectura", "esquema", "CREATE"): (False,),
        ("lectura", "base", "CREATE"): (False,),
    }


def test_tkt003_ca07_esc03_lectura_no_crea_objetos(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-40 · CA-7 esc. 3 — el rol de lectura no puede crear tablas, y no queda ninguna.

    Nace en verde por la misma protección nativa que TC-33; lo ata a ella el mutante MP-11.
    """
    with (
        conectar("lectura", base_de_prueba) as lectura,
        pytest.raises(psycopg.errors.InsufficientPrivilege) as error,
    ):
        lectura.execute("CREATE TABLE desechable_tkt003 (n int)")

    assert error.value.sqlstate == "42501"
    with conectar("migracion", base_de_prueba) as migracion:
        existe = migracion.execute("SELECT to_regclass('desechable_tkt003')").fetchone()
    assert existe == (None,)


def test_tkt003_ca07_esc01_lectura_consulta_tabla_posterior(
    base_de_prueba: str, conectar: Conectar, tabla_posterior: str
) -> None:
    """TC-41 · CA-7 esc. 1 — el rol de lectura consulta una tabla creada después de la migración."""
    with conectar("lectura", base_de_prueba) as lectura:
        filas = lectura.execute(f"SELECT count(*) FROM {tabla_posterior}").fetchone()

    assert filas == (1,)
