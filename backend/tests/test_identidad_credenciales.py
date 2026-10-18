"""Credenciales (TKT-003, fila 3): TC-60 a TC-65.

TC-64 y TC-65 no necesitan Docker: revisan archivos del repositorio.
"""

import importlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"

PREFIJO_DE_DESARROLLO = "solo-desarrollo-"
CLAVES_DE_CONEXION = {
    "CIMENTA_DB_HOST",
    "CIMENTA_DB_PUERTO",
    "CIMENTA_DB_NOMBRE",
    "CIMENTA_DB_CONTRASENA_MIGRACION",
    "CIMENTA_DB_CONTRASENA_APLICACION",
    "CIMENTA_DB_CONTRASENA_LECTURA",
}

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]


def _leer_env_example() -> dict[str, str]:
    """Pares `CLAVE=valor` de `.env.example`, sin comentarios ni líneas vacías."""
    pares: dict[str, str] = {}
    for linea in (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines():
        texto = linea.strip()
        if texto and not texto.startswith("#") and "=" in texto:
            clave, valor = texto.split("=", 1)
            pares[clave.strip()] = valor.strip()
    return pares


def _archivos_de_texto(*carpetas: Path, patrones: tuple[str, ...] = ("*.py",)) -> list[Path]:
    encontrados: list[Path] = []
    for carpeta in carpetas:
        for patron in patrones:
            encontrados.extend(
                ruta for ruta in carpeta.rglob(patron) if "__pycache__" not in ruta.parts
            )
    return sorted(encontrados)


def test_tkt003_ca10_esc01_roles_entran_con_su_contrasena(conectar: Conectar) -> None:
    """TC-60 · CA-10 esc. 1 — con la contraseña fijada, los dos roles entran por TCP, cifrada en SCRAM."""
    with conectar("aplicacion", "postgres") as aplicacion:
        assert aplicacion.execute("SELECT current_user").fetchone() == ("cimenta_aplicacion",)
    with conectar("lectura", "postgres") as lectura:
        assert lectura.execute("SELECT current_user").fetchone() == ("cimenta_lectura",)

    with conectar("migracion", "postgres") as administrador:
        filas = administrador.execute(
            "SELECT rolname, starts_with(rolpassword, 'SCRAM-SHA-256$') FROM pg_authid "
            "WHERE rolname IN ('cimenta_aplicacion', 'cimenta_lectura') ORDER BY rolname"
        ).fetchall()
    assert filas == [("cimenta_aplicacion", True), ("cimenta_lectura", True)]


def test_tkt003_ca10_esc02_sin_contrasena_no_se_entra(
    observacion_sin_contrasena: Any,
) -> None:
    """TC-61 · CA-10 esc. 2 — un rol creado sin contraseña no entra con una vacía ni con otra."""
    observacion = observacion_sin_contrasena

    assert observacion.sin_contrasena == {"cimenta_aplicacion": True, "cimenta_lectura": True}
    assert len(observacion.intentos) == 4
    assert [i.conecto for i in observacion.intentos] == [False, False, False, False]
    assert {i.clase for i in observacion.intentos} == {"OperationalError"}
    con_otra_contrasena = [i for i in observacion.intentos if i.contrasena == "cualquiera"]
    assert len(con_otra_contrasena) == 2
    for intento in con_otra_contrasena:
        assert "password authentication failed" in intento.mensaje, intento.mensaje


def test_tkt003_ca10_esc01_script_fija_desde_el_entorno(
    contenedor_postgres: Any,
    credenciales: dict[str, str],
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-62 · CA-10 esc. 1, RNF-07 — el script fija las contraseñas desde el entorno y no las imprime."""
    herramienta = importlib.import_module("herramientas.contrasenas_roles")
    monkeypatch.setenv("CIMENTA_DB_HOST", contenedor_postgres.get_container_host_ip())
    monkeypatch.setenv("CIMENTA_DB_PUERTO", str(contenedor_postgres.get_exposed_port(5432)))
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", "postgres")
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", credenciales["migracion"])
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_APLICACION", credenciales["aplicacion"])
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_LECTURA", credenciales["lectura"])

    codigo = herramienta.main()

    salida = capsys.readouterr()
    assert codigo == 0
    assert "Contraseñas fijadas" in salida.out
    for rol in ("migracion", "aplicacion", "lectura"):
        assert credenciales[rol] not in salida.out
        assert credenciales[rol] not in salida.err
    with conectar("aplicacion", "postgres") as aplicacion:
        assert aplicacion.execute("SELECT current_user").fetchone() == ("cimenta_aplicacion",)


def test_tkt003_ca10_contrasena_vacia_se_rechaza(
    credenciales: dict[str, str], conectar: Conectar
) -> None:
    """TC-63 · RNF-07 — una contraseña vacía se rechaza antes de ejecutar nada."""
    herramienta = importlib.import_module("herramientas.contrasenas_roles")

    with (
        conectar("migracion", "postgres") as administrador,
        pytest.raises(ValueError, match="cimenta_aplicacion"),
    ):
        herramienta.fijar_contrasenas(administrador, aplicacion="", lectura="x")

    with conectar("lectura", "postgres") as lectura:
        assert lectura.execute("SELECT current_user").fetchone() == ("cimenta_lectura",)
    with conectar("aplicacion", "postgres") as aplicacion:
        assert aplicacion.execute("SELECT current_user").fetchone() == ("cimenta_aplicacion",)


def test_tkt003_ca10_esc03_ningun_secreto_en_el_repositorio() -> None:
    """TC-64 · CA-10 esc. 3 — ni la migración ni las herramientas ni Compose llevan una contraseña."""
    revisados = [RAIZ / "compose.yaml"] + _archivos_de_texto(
        BACKEND / "migraciones", BACKEND / "herramientas", BACKEND / "tests"
    )
    nombres = {ruta.name for ruta in revisados}
    assert {"compose.yaml", "env.py", "v0001_identidad_roles_y_esquema.py"} <= nombres, nombres

    cadena_prohibida = "PASS" + "WORD '"
    valores = [
        valor
        for clave, valor in _leer_env_example().items()
        if clave.startswith("CIMENTA_DB_CONTRASENA_")
    ]
    assert len(valores) == 3
    assert all(valor.startswith(PREFIJO_DE_DESARROLLO) for valor in valores)

    for ruta in revisados:
        texto = ruta.read_text(encoding="utf-8")
        assert cadena_prohibida not in texto, f"{ruta} fija una contraseña en el SQL"
        for valor in valores:
            assert valor not in texto, f"{ruta} contiene una contraseña de .env.example"


def test_tkt003_ca11_esc01_env_example_define_lo_que_se_usa() -> None:
    """TC-65 · CA-11 esc. 1 — .env.example define exactamente las variables que el código lee."""
    claves = _leer_env_example()
    de_conexion = {
        clave: valor for clave, valor in claves.items() if clave.startswith("CIMENTA_DB_")
    }

    assert set(de_conexion) == CLAVES_DE_CONEXION
    assert de_conexion["CIMENTA_DB_HOST"] == "127.0.0.1"
    assert de_conexion["CIMENTA_DB_PUERTO"] == "5432"
    assert de_conexion["CIMENTA_DB_NOMBRE"] == "cimenta"
    for clave in CLAVES_DE_CONEXION - {"CIMENTA_DB_HOST", "CIMENTA_DB_PUERTO", "CIMENTA_DB_NOMBRE"}:
        assert de_conexion[clave].startswith(PREFIJO_DE_DESARROLLO), clave

    revisados = [RAIZ / "compose.yaml"] + _archivos_de_texto(
        BACKEND / "herramientas", BACKEND / "migraciones", patrones=("*.py", "*.mako")
    )
    rutas_relativas = {ruta.relative_to(RAIZ).as_posix() for ruta in revisados}
    assert {"compose.yaml", "backend/herramientas/conexion.py"} <= rutas_relativas, rutas_relativas

    usadas: set[str] = set()
    for ruta in revisados:
        usadas |= set(re.findall(r"CIMENTA_DB_[A-Z_]+", ruta.read_text(encoding="utf-8")))
    assert usadas <= CLAVES_DE_CONEXION, usadas - CLAVES_DE_CONEXION
