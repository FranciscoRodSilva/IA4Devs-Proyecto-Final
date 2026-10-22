"""Conexión del rol de aplicación y fixtures de la bitácora (TKT-007, fila 2): TC-18 a TC-22.

`url_aplicacion` y `crear_motor_aplicacion` viven en `herramientas/conexion.py` y siguen el patrón de
`url_migracion`. Las tres fixtures nuevas de `conftest.py` (`motor_aplicacion`, `sesion_bd` y
`guarda_de_aplicacion`) las escribe el tester: TC-20 a TC-22 las prueban a ellas.

Los símbolos de `herramientas.conexion` se importan dentro de cada caso, no al principio del
módulo: así, mientras no existan, falla solo TC-18 o TC-19 con el `ImportError` del símbolo pedido
y no el módulo entero en la recolección, que ocultaría TC-20 a TC-22.
"""

import ast
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

CONFTEST = Path(__file__).resolve().parent / "conftest.py"
FIXTURES_NUEVAS = {"motor_aplicacion", "sesion_bd", "guarda_de_aplicacion"}
VARIABLE_CONTRASENA = "CIMENTA_DB_CONTRASENA_APLICACION"


def _fijar_entorno(
    monkeypatch: pytest.MonkeyPatch, *, host: str, puerto: str, base: str, contrasena: str | None
) -> None:
    monkeypatch.setenv("CIMENTA_DB_HOST", host)
    monkeypatch.setenv("CIMENTA_DB_PUERTO", puerto)
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", base)
    if contrasena is None:
        monkeypatch.delenv(VARIABLE_CONTRASENA, raising=False)
    else:
        monkeypatch.setenv(VARIABLE_CONTRASENA, contrasena)


def test_tkt007_ca09_url_del_rol_de_aplicacion(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-18 · CA-9, M7 — la URL es la del rol de aplicación; sin su contraseña, falla nombrándola."""
    from herramientas.conexion import url_aplicacion

    _fijar_entorno(
        monkeypatch, host="db.interna", puerto="5433", base="cimenta_x", contrasena="s3cr3to/ñ:@"
    )

    url = url_aplicacion()

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "cimenta_aplicacion"
    assert url.password == "s3cr3to/ñ:@"
    assert url.host == "db.interna"
    assert url.port == 5433
    assert isinstance(url.port, int)
    assert url.database == "cimenta_x"

    _fijar_entorno(monkeypatch, host="db.interna", puerto="5433", base="cimenta_x", contrasena=None)
    with pytest.raises(RuntimeError) as error:
        url_aplicacion()
    assert VARIABLE_CONTRASENA in str(error.value)

    _fijar_entorno(monkeypatch, host="db.interna", puerto="5433", base="cimenta_x", contrasena="")
    with pytest.raises(RuntimeError) as vacia:
        url_aplicacion()
    assert VARIABLE_CONTRASENA in str(vacia.value)


def test_tkt007_ca09_crear_el_motor_no_conecta(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-19 · CA-9 esc. 3 — crear el motor no abre ninguna conexión; solo la primera consulta lo hace."""
    from herramientas.conexion import crear_motor_aplicacion

    _fijar_entorno(monkeypatch, host="127.0.0.1", puerto="1", base="cimenta_x", contrasena="x")

    motor = crear_motor_aplicacion()
    try:
        assert isinstance(motor, Engine)
        assert motor.url.username == "cimenta_aplicacion"
        assert motor.pool.checkedout() == 0  # type: ignore[attr-defined]
        with pytest.raises(OperationalError):
            motor.connect()
    finally:
        motor.dispose()


def test_tkt007_ca09_sesion_del_rol_de_aplicacion(sesion_bd: Session, base_de_prueba: str) -> None:
    """TC-20 · CA-9 esc. 1 — la sesión de pruebas es del rol de aplicación y de la base de la prueba."""
    assert isinstance(sesion_bd, Session)

    usuario = sesion_bd.execute(text("SELECT current_user")).scalar_one()
    base = sesion_bd.execute(text("SELECT current_database()")).scalar_one()

    assert usuario == "cimenta_aplicacion"
    assert base == base_de_prueba


def test_tkt007_ca09_la_guarda_rechaza_al_propietario(
    contenedor_postgres: PostgresContainer,
    base_de_prueba: str,
    guarda_de_aplicacion: Callable[[Engine], None],
) -> None:
    """TC-21 · CA-9 esc. 2 — un motor del rol de migración no pasa la guarda y el fallo nombra los dos roles."""
    propietario = create_engine(
        URL.create(
            "postgresql+psycopg",
            username="cimenta_migracion",
            password=contenedor_postgres.password,
            host=contenedor_postgres.get_container_host_ip(),
            port=int(contenedor_postgres.get_exposed_port(5432)),
            database=base_de_prueba,
        ),
        poolclass=pool.NullPool,
    )
    try:
        with pytest.raises(pytest.fail.Exception) as fallo:
            guarda_de_aplicacion(propietario)
    finally:
        propietario.dispose()

    mensaje = str(fallo.value)
    assert "cimenta_aplicacion" in mensaje
    assert "cimenta_migracion" in mensaje


def _es_fixture(decorador: ast.expr) -> bool:
    objetivo = decorador.func if isinstance(decorador, ast.Call) else decorador
    if isinstance(objetivo, ast.Attribute):
        return objetivo.attr == "fixture"
    return isinstance(objetivo, ast.Name) and objetivo.id == "fixture"


def _lleva_autouse(decorador: ast.expr) -> bool:
    return isinstance(decorador, ast.Call) and any(
        palabra.arg == "autouse" for palabra in decorador.keywords
    )


def test_tkt007_ca09_fixtures_nuevas_sin_autouse() -> None:
    """TC-22 · CA-9 esc. 4 — las tres fixtures nuevas existen en conftest.py y ninguna es autouse."""
    arbol = ast.parse(CONFTEST.read_text(encoding="utf-8"), filename=str(CONFTEST))
    fixtures = {
        nodo.name: decorador
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef)
        for decorador in nodo.decorator_list
        if _es_fixture(decorador)
    }

    assert sorted(FIXTURES_NUEVAS - fixtures.keys()) == []
    con_autouse = sorted(n for n in FIXTURES_NUEVAS if _lleva_autouse(fixtures[n]))
    assert con_autouse == []
