"""Migración y arnés (TKT-003, fila 3): TC-11, TC-15, TC-16 y TC-18."""

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]
Migrar = Callable[..., None]


def test_tkt003_pat8_subida_con_roles_ya_existentes_en_el_cluster(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-11 · CA-2, PA-T8 — la subida corrige los atributos de un rol que ya existía.

    Los roles son del clúster: la plantilla ya los creó, y alguien le dio un atributo de más.
    La migración los converge con ALTER ROLE en lugar de heredarlo.
    """
    with conectar("migracion", base_vacia) as administrador:
        existentes = administrador.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('cimenta_aplicacion', 'cimenta_lectura')"
        ).fetchall()
        assert sorted(nombre for (nombre,) in existentes) == [
            "cimenta_aplicacion",
            "cimenta_lectura",
        ]
        administrador.execute("ALTER ROLE cimenta_lectura CREATEDB")
        try:
            migrar(base_vacia)
            fila = administrador.execute(
                "SELECT rolcreatedb FROM pg_roles WHERE rolname = 'cimenta_lectura'"
            ).fetchone()
        finally:
            administrador.execute("ALTER ROLE cimenta_lectura NOCREATEDB")

    assert fila == (False,)


def test_tkt003_guarda_solo_migra_el_rol_de_migracion(
    base_vacia: str, migrar: Migrar, conectar: Conectar, credenciales: dict[str, str]
) -> None:
    """TC-15 · M5 — Alembic se niega a migrar con un rol que no sea cimenta_migracion.

    Los privilegios por omisión solo cubren las tablas que crea ese rol: otro rol dejaría
    tablas sin permisos para la aplicación y ninguna prueba de las tablas viejas lo notaría.
    """
    with pytest.raises(RuntimeError) as excinfo:
        migrar(base_vacia, rol="cimenta_aplicacion")

    assert "solo cimenta_migracion" in str(excinfo.value)
    assert "cimenta_aplicacion" in str(excinfo.value)
    with conectar("migracion", base_vacia) as administrador:
        fila = administrador.execute("SELECT to_regclass('public.alembic_version')").fetchone()
    assert fila == (None,)


def test_tkt003_ca09_esc01_esquema_por_alembic_y_conexion_de_aplicacion(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-16 · CA-9 esc. 1 — el esquema sale de alembic upgrade head y la conexión es la de aplicación."""
    cabeza = ScriptDirectory.from_config(
        Config(toml_file=str(BACKEND / "pyproject.toml"))
    ).get_current_head()
    with conectar("migracion", base_de_prueba) as administrador:
        versiones = administrador.execute("SELECT version_num FROM alembic_version").fetchall()
    assert versiones == [(cabeza,)]

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        fila = aplicacion.execute("SELECT current_user").fetchone()
    assert fila == ("cimenta_aplicacion",)


def test_tkt003_rnf07_sin_variable_no_hay_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-18 · RNF-07 — sin contraseña de migración en el entorno no se construye ninguna URL."""
    conexion = importlib.import_module("herramientas.conexion")
    monkeypatch.setenv("CIMENTA_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("CIMENTA_DB_PUERTO", "5432")
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "cimenta")

    monkeypatch.delenv("CIMENTA_DB_CONTRASENA_MIGRACION", raising=False)
    with pytest.raises(RuntimeError, match="CIMENTA_DB_CONTRASENA_MIGRACION"):
        conexion.url_migracion()

    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", "")
    with pytest.raises(RuntimeError, match="CIMENTA_DB_CONTRASENA_MIGRACION"):
        conexion.url_migracion()
