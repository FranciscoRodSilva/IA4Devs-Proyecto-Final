"""Roles y permisos (TKT-003, fila 3): TC-30."""

from collections.abc import Callable
from typing import Any

import psycopg

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]

ATRIBUTOS_ESPERADOS = {
    "rolsuper": False,
    "rolcreatedb": False,
    "rolcreaterole": False,
    "rolreplication": False,
    "rolbypassrls": False,
    "rolcanlogin": True,
}


def test_tkt003_ca05_esc01_roles_sin_atributos_de_privilegio(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-30 · CA-5 esc. 1 — los roles de aplicación y de lectura solo pueden iniciar sesión."""
    with conectar("migracion", base_de_prueba) as administrador:
        filas = administrador.execute(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
            "rolbypassrls, rolcanlogin FROM pg_roles "
            "WHERE rolname IN ('cimenta_aplicacion', 'cimenta_lectura') ORDER BY rolname"
        ).fetchall()
        membresias = administrador.execute(
            "SELECT miembro.rolname, grupo.rolname FROM pg_auth_members m "
            "JOIN pg_roles miembro ON miembro.oid = m.member "
            "JOIN pg_roles grupo ON grupo.oid = m.roleid "
            "WHERE miembro.rolname IN ('cimenta_aplicacion', 'cimenta_lectura')"
        ).fetchall()

    columnas = list(ATRIBUTOS_ESPERADOS)
    atributos = {fila[0]: dict(zip(columnas, fila[1:], strict=True)) for fila in filas}
    assert atributos == {
        "cimenta_aplicacion": ATRIBUTOS_ESPERADOS,
        "cimenta_lectura": ATRIBUTOS_ESPERADOS,
    }
    assert membresias == []
