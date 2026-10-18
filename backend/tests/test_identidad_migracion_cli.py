"""Migración por la línea de comandos real (TKT-003, reapertura de la fila 3).

Los fixtures de `conftest.py` entregan a Alembic una conexión ya abierta (`attributes["connection"]`)
y hacen ellos el `commit`. La CLI no: `env.py` crea su propio motor y es Alembic quien debe confirmar.
Estas pruebas lanzan `python -m alembic` como subproceso, desde `backend/`, con el entorno
`CIMENTA_DB_*` apuntando a una base del contenedor, y comprueban el resultado con una conexión
nueva. Es la única ruta que un operador ejecuta de verdad.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from testcontainers.community.postgres import PostgresContainer

BACKEND = Path(__file__).resolve().parents[1]

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]

ROLES_DE_APLICACION = {
    ("cimenta_aplicacion", "SELECT"),
    ("cimenta_aplicacion", "INSERT"),
    ("cimenta_aplicacion", "UPDATE"),
    ("cimenta_aplicacion", "DELETE"),
    ("cimenta_lectura", "SELECT"),
}

CONSULTA_PRIVILEGIOS_POR_OMISION = (
    "SELECT g.rolname, a.privilege_type "
    "FROM pg_default_acl d "
    "JOIN pg_roles dueno ON dueno.oid = d.defaclrole "
    "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
    "CROSS JOIN LATERAL aclexplode(d.defaclacl) a "
    "JOIN pg_roles g ON g.oid = a.grantee "
    "WHERE dueno.rolname = 'cimenta_migracion' AND n.nspname = 'public' "
    "AND d.defaclobjtype = 'r' AND g.rolname IN ('cimenta_aplicacion', 'cimenta_lectura')"
)


def alembic_por_cli(
    contenedor: PostgresContainer,
    base: str,
    *argumentos: str,
    opciones_de_sesion: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Ejecuta `python -m alembic <argumentos>` desde `backend/` con el entorno de la base dada.

    `opciones_de_sesion` llega a libpq como `PGOPTIONS`: `-c role=…` hace que `current_user`
    sea otro rol sin cambiar el usuario con el que `env.py` se autentica, que es fijo.
    """
    entorno = {
        nombre: valor
        for nombre, valor in os.environ.items()
        if not nombre.startswith("CIMENTA_DB_") and nombre not in {"PGOPTIONS", "DATABASE_URL"}
    }
    entorno.update(
        {
            "CIMENTA_DB_HOST": contenedor.get_container_host_ip(),
            "CIMENTA_DB_PUERTO": str(contenedor.get_exposed_port(5432)),
            "CIMENTA_DB_NOMBRE": base,
            "CIMENTA_DB_CONTRASENA_MIGRACION": contenedor.password,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if opciones_de_sesion is not None:
        entorno["PGOPTIONS"] = opciones_de_sesion
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argumentos],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def salida(proceso: subprocess.CompletedProcess[str]) -> str:
    return f"código={proceso.returncode}\n--- stdout ---\n{proceso.stdout}\n--- stderr ---\n{proceso.stderr}"


def test_tkt003_cli_upgrade_head_persiste_version_roles_y_privilegios_por_omision(
    contenedor_postgres: PostgresContainer, base_vacia: str, conectar: Conectar
) -> None:
    """CA-2, CA-5 · M5 — `alembic upgrade head` por la CLI confirma lo que migra.

    Reproduce el defecto: la guarda de `env.py` abre la transacción implícita con
    `SELECT current_user`, Alembic no la confirma y el cierre de la conexión la deshace.
    Con el arnés de `conftest.py` no se ve porque la fixture hace `commit` por su cuenta.
    """
    cabeza = ScriptDirectory.from_config(
        Config(toml_file=str(BACKEND / "pyproject.toml"))
    ).get_current_head()

    proceso = alembic_por_cli(contenedor_postgres, base_vacia, "upgrade", "head")

    assert proceso.returncode == 0, salida(proceso)
    with conectar("migracion", base_vacia) as nueva:
        existe = nueva.execute("SELECT to_regclass('public.alembic_version')").fetchone()
        assert existe == ("alembic_version",), salida(proceso)
        versiones = nueva.execute("SELECT version_num FROM alembic_version").fetchall()
        roles = nueva.execute(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('cimenta_aplicacion', 'cimenta_lectura') AND rolcanlogin"
        ).fetchall()
        por_omision = set(nueva.execute(CONSULTA_PRIVILEGIOS_POR_OMISION).fetchall())

    assert versiones == [(cabeza,)]
    assert sorted(nombre for (nombre,) in roles) == ["cimenta_aplicacion", "cimenta_lectura"]
    assert por_omision == ROLES_DE_APLICACION


def test_tkt003_cli_downgrade_base_revierte_privilegios_por_omision_y_vacia_la_version(
    contenedor_postgres: PostgresContainer, base_de_prueba: str, conectar: Conectar
) -> None:
    """CA-2 · M5 — `alembic downgrade base` por la CLI confirma la reversión.

    Parte de una base ya migrada por el arnés, para que el caso no dependa de que la subida
    por la CLI funcione. Precondición: los privilegios por omisión existen antes de bajar; sin
    ella, «ya no hay entradas» sería cierto por una base que nunca las tuvo.
    """
    with conectar("migracion", base_de_prueba) as antes:
        assert (
            set(antes.execute(CONSULTA_PRIVILEGIOS_POR_OMISION).fetchall()) == ROLES_DE_APLICACION
        )
        assert antes.execute("SELECT count(*) FROM alembic_version").fetchone() == (1,)

    proceso = alembic_por_cli(contenedor_postgres, base_de_prueba, "downgrade", "base")

    assert proceso.returncode == 0, salida(proceso)
    with conectar("migracion", base_de_prueba) as despues:
        por_omision = despues.execute(CONSULTA_PRIVILEGIOS_POR_OMISION).fetchall()
        versiones = despues.execute("SELECT version_num FROM alembic_version").fetchall()

    assert por_omision == [], salida(proceso)
    assert versiones == [], salida(proceso)


def test_tkt003_cli_rol_distinto_del_de_migracion_se_rechaza_sin_persistir_nada(
    contenedor_postgres: PostgresContainer, base_vacia: str, conectar: Conectar
) -> None:
    """TC-15 · M5 — la CLI con `current_user = cimenta_aplicacion` aborta con el mensaje de la guarda.

    `env.py` se autentica siempre como `cimenta_migracion`; `PGOPTIONS="-c role=cimenta_aplicacion"`
    deja a la sesión con otro `current_user` y es lo que la guarda inspecciona. El rol de
    migración del contenedor es superusuario y puede asumir el otro rol.

    Puede nacer en verde: la guarda ya existe y rechaza antes de que ninguna migración corra.
    Lo ata a la ruta real que el mensaje salga del subproceso y que no quede nada en la base.
    """
    proceso = alembic_por_cli(
        contenedor_postgres,
        base_vacia,
        "upgrade",
        "head",
        opciones_de_sesion="-c role=cimenta_aplicacion",
    )

    assert proceso.returncode != 0, salida(proceso)
    assert "solo cimenta_migracion" in proceso.stderr, salida(proceso)
    assert "esta conexión es cimenta_aplicacion" in proceso.stderr, salida(proceso)
    with conectar("migracion", base_vacia) as nueva:
        existe = nueva.execute("SELECT to_regclass('public.alembic_version')").fetchone()
        por_omision = nueva.execute(CONSULTA_PRIVILEGIOS_POR_OMISION).fetchall()
    assert existe == (None,)
    assert por_omision == []
