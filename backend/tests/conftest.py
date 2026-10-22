"""Arnés de pruebas de integración de CIMENTA (TKT-003).

PostgreSQL real con testcontainers, nunca SQLite. El esquema se construye con
`alembic upgrade head` a través del mismo `env.py` que la línea de comandos, y las
pruebas de permisos se conectan con el rol de aplicación: con el propietario quedarían
verdes sin verificar nada.

Un contenedor por sesión; la plantilla `cimenta_plantilla` se migra una vez y cada
prueba recibe una base copiada de ella. Sin Docker en marcha la suite falla: no se salta.
"""

import importlib
import os
import re
import secrets
import uuid
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"

ROL_MIGRACION = "cimenta_migracion"
ROL_APLICACION = "cimenta_aplicacion"
ROL_LECTURA = "cimenta_lectura"
BASE_PLANTILLA = "cimenta_plantilla"

RolDePrueba = Literal["migracion", "aplicacion", "lectura"]


class Migrar(Protocol):
    def __call__(
        self,
        base: str,
        destino: str = "head",
        sentido: Literal["upgrade", "downgrade"] = "upgrade",
        rol: str = "cimenta_migracion",
    ) -> None: ...


class Conectar(Protocol):
    def __call__(
        self, rol: RolDePrueba, base: str, autocommit: bool = True
    ) -> psycopg.Connection[tuple[Any, ...]]: ...


@dataclass(frozen=True)
class IntentoSinContrasena:
    """Resultado de un intento de entrar por TCP con una contraseña que no es la del rol."""

    rol: str
    contrasena: str
    conecto: bool
    clase: str
    mensaje: str


@dataclass(frozen=True)
class ObservacionSinContrasena:
    """Lo observado antes de fijar ninguna contraseña (CA-10 esc. 2)."""

    sin_contrasena: dict[str, bool]
    intentos: tuple[IntentoSinContrasena, ...]


def pytest_sessionstart(session: pytest.Session) -> None:
    """Convierte en error explícito el intento de apuntar la suite a SQLite (CA-9 esc. 3)."""
    for nombre, valor in os.environ.items():
        es_de_base = nombre == "DATABASE_URL" or nombre.startswith("CIMENTA_DB_")
        if es_de_base and "sqlite" in valor.lower():
            pytest.exit(
                f"Solo se admite PostgreSQL (ADR-002): la variable {nombre} apunta a SQLite.",
                returncode=2,
            )


def _imagen_postgres() -> str:
    """La única fuente de la imagen es compose.yaml: no hay segunda constante que diverja."""
    texto = (RAIZ / "compose.yaml").read_text(encoding="utf-8")
    coincidencias = re.findall(r"^\s*image:\s*(postgres:\S+)\s*$", texto, flags=re.MULTILINE)
    if len(coincidencias) != 1:
        pytest.fail(
            f"compose.yaml debe declarar exactamente una imagen postgres:<etiqueta>, "
            f"y declara {len(coincidencias)}: {coincidencias}"
        )
    return coincidencias[0]


def _abrir(
    contenedor: PostgresContainer,
    rol: str,
    contrasena: str,
    base: str,
    autocommit: bool = True,
) -> psycopg.Connection[tuple[Any, ...]]:
    return psycopg.connect(
        host=contenedor.get_container_host_ip(),
        port=int(contenedor.get_exposed_port(5432)),
        dbname=base,
        user=rol,
        password=contrasena,
        autocommit=autocommit,
        connect_timeout=15,
    )


@pytest.fixture(scope="session")
def contenedor_postgres() -> Iterator[PostgresContainer]:
    """PostgreSQL con la imagen de compose.yaml. El usuario de la imagen es el rol de migración."""
    with PostgresContainer(
        _imagen_postgres(),
        username=ROL_MIGRACION,
        password=secrets.token_urlsafe(24),
        dbname=BASE_PLANTILLA,
        driver=None,
    ) as contenedor:
        yield contenedor


@pytest.fixture(scope="session")
def _contrasenas_de_roles(contenedor_postgres: PostgresContainer) -> dict[str, str]:
    """Contraseñas conocidas por clave de rol. `credenciales` añade las dos que fija la suite."""
    return {"migracion": contenedor_postgres.password}


@pytest.fixture(scope="session")
def migrar(contenedor_postgres: PostgresContainer, _contrasenas_de_roles: dict[str, str]) -> Migrar:
    """`alembic upgrade|downgrade` con el `env.py` real, sobre la conexión del rol indicado.

    El parámetro `rol` existe solo para TC-15. Un rol distinto del de migración exige que la
    prueba haya pedido `credenciales`, que es quien conoce su contraseña.
    """

    def _migrar(
        base: str,
        destino: str = "head",
        sentido: Literal["upgrade", "downgrade"] = "upgrade",
        rol: str = ROL_MIGRACION,
    ) -> None:
        contrasena = _contrasenas_de_roles[rol.removeprefix("cimenta_")]
        url = URL.create(
            "postgresql+psycopg",
            username=rol,
            password=contrasena,
            host=contenedor_postgres.get_container_host_ip(),
            port=int(contenedor_postgres.get_exposed_port(5432)),
            database=base,
        )
        motor = create_engine(url, poolclass=pool.NullPool)
        try:
            configuracion = Config(toml_file=str(BACKEND / "pyproject.toml"))
            with motor.begin() as conexion:
                configuracion.attributes["connection"] = conexion
                if sentido == "upgrade":
                    command.upgrade(configuracion, destino)
                else:
                    command.downgrade(configuracion, destino)
        finally:
            motor.dispose()

    return _migrar


@pytest.fixture(scope="session")
def plantilla_migrada(contenedor_postgres: PostgresContainer, migrar: Migrar) -> str:
    """Migra `cimenta_plantilla` con `alembic upgrade head`; no deja ninguna conexión abierta.

    `CREATE DATABASE … TEMPLATE` falla si queda una conexión a la plantilla.
    """
    migrar(BASE_PLANTILLA)
    return BASE_PLANTILLA


@pytest.fixture(scope="session")
def observacion_sin_contrasena(
    contenedor_postgres: PostgresContainer, plantilla_migrada: str
) -> ObservacionSinContrasena:
    """Lo que ocurre antes de que nadie fije una contraseña. Corre antes de `credenciales`."""
    roles = (ROL_APLICACION, ROL_LECTURA)
    with _abrir(contenedor_postgres, ROL_MIGRACION, contenedor_postgres.password, "postgres") as c:
        filas = c.execute(
            "SELECT rolname, rolpassword IS NULL FROM pg_authid WHERE rolname = ANY(%s)",
            (list(roles),),
        ).fetchall()
    sin_contrasena = {str(nombre): bool(nula) for nombre, nula in filas}

    intentos: list[IntentoSinContrasena] = []
    for rol in roles:
        for contrasena in ("", "cualquiera"):
            try:
                _abrir(contenedor_postgres, rol, contrasena, "postgres").close()
            except psycopg.OperationalError as error:
                intentos.append(
                    IntentoSinContrasena(rol, contrasena, False, type(error).__name__, str(error))
                )
            else:
                intentos.append(IntentoSinContrasena(rol, contrasena, True, "", "conectó"))
    return ObservacionSinContrasena(sin_contrasena, tuple(intentos))


@pytest.fixture(scope="session")
def credenciales(
    contenedor_postgres: PostgresContainer,
    observacion_sin_contrasena: ObservacionSinContrasena,
    _contrasenas_de_roles: dict[str, str],
) -> dict[str, str]:
    """Fija las contraseñas de los dos roles con la misma función que usa el script de operación."""
    herramienta = importlib.import_module("herramientas.contrasenas_roles")
    _contrasenas_de_roles["aplicacion"] = secrets.token_urlsafe(24)
    _contrasenas_de_roles["lectura"] = secrets.token_urlsafe(24)
    with _abrir(contenedor_postgres, ROL_MIGRACION, contenedor_postgres.password, "postgres") as c:
        herramienta.fijar_contrasenas(
            c,
            aplicacion=_contrasenas_de_roles["aplicacion"],
            lectura=_contrasenas_de_roles["lectura"],
        )
    return _contrasenas_de_roles


@pytest.fixture
def _registro_conexiones() -> Iterator[list[psycopg.Connection[tuple[Any, ...]]]]:
    """Conexiones abiertas por `conectar`: se cierran antes de borrar la base y al terminar."""
    abiertas: list[psycopg.Connection[tuple[Any, ...]]] = []
    yield abiertas
    _cerrar(abiertas)


def _cerrar(conexiones: list[psycopg.Connection[tuple[Any, ...]]]) -> None:
    while conexiones:
        with suppress(psycopg.Error):
            conexiones.pop().close()


def _ciclo_de_base(
    contenedor: PostgresContainer,
    registro: list[psycopg.Connection[tuple[Any, ...]]],
    plantilla: str | None,
) -> Iterator[str]:
    nombre = f"prueba_{uuid.uuid4().hex[:12]}"
    identificador = sql.Identifier(nombre)
    with _abrir(contenedor, ROL_MIGRACION, contenedor.password, "postgres") as admin:
        if plantilla is None:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(identificador))
        else:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    identificador, sql.Identifier(plantilla)
                )
            )
        try:
            yield nombre
        finally:
            _cerrar(registro)
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(identificador))


@pytest.fixture
def base_de_prueba(
    contenedor_postgres: PostgresContainer,
    plantilla_migrada: str,
    _registro_conexiones: list[psycopg.Connection[tuple[Any, ...]]],
) -> Iterator[str]:
    """Una base copiada de la plantilla migrada: esquema, permisos y privilegios por omisión."""
    yield from _ciclo_de_base(contenedor_postgres, _registro_conexiones, plantilla_migrada)


@pytest.fixture
def base_vacia(
    contenedor_postgres: PostgresContainer,
    plantilla_migrada: str,
    _registro_conexiones: list[psycopg.Connection[tuple[Any, ...]]],
) -> Iterator[str]:
    """Una base sin ninguna tabla de CIMENTA, en el mismo clúster, donde los roles ya existen."""
    yield from _ciclo_de_base(contenedor_postgres, _registro_conexiones, None)


def _exigir_rol_de_aplicacion(conexion: psycopg.Connection[tuple[Any, ...]]) -> None:
    fila = conexion.execute(
        "SELECT current_user, r.rolsuper, pg_has_role(current_user, 'cimenta_migracion', 'MEMBER') "
        "FROM pg_roles r WHERE r.rolname = current_user"
    ).fetchone()
    assert fila is not None
    actual, superusuario, miembro_de_migracion = fila
    if actual != "cimenta_aplicacion" or superusuario or miembro_de_migracion:
        conexion.close()
        pytest.fail(
            f"La conexión de pruebas no es la del rol de aplicación (cimenta_aplicacion): es "
            f"{actual}. Con el propietario, las pruebas de permisos quedan verdes sin verificar "
            f"nada."
        )
    if not conexion.autocommit:
        conexion.rollback()


@pytest.fixture
def conectar(
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    _registro_conexiones: list[psycopg.Connection[tuple[Any, ...]]],
) -> Conectar:
    """Conexión por TCP como `cimenta_<rol>`. La de aplicación pasa antes por la guarda."""

    def _conectar(
        rol: RolDePrueba, base: str, autocommit: bool = True
    ) -> psycopg.Connection[tuple[Any, ...]]:
        conexion = _abrir(
            contenedor_postgres, f"cimenta_{rol}", credenciales[rol], base, autocommit
        )
        _registro_conexiones.append(conexion)
        if rol == "aplicacion":
            _exigir_rol_de_aplicacion(conexion)
        return conexion

    return _conectar


def _exigir_motor_de_aplicacion(motor: Engine) -> None:
    """Misma guarda que _exigir_rol_de_aplicacion, para un motor de SQLAlchemy."""
    with motor.connect() as conexion:
        fila = conexion.execute(
            text(
                "SELECT current_user, r.rolsuper, "
                "pg_has_role(current_user, 'cimenta_migracion', 'MEMBER') "
                "FROM pg_roles r WHERE r.rolname = current_user"
            )
        ).one()
    actual, superusuario, miembro_de_migracion = fila
    if actual != ROL_APLICACION or superusuario or miembro_de_migracion:
        motor.dispose()
        pytest.fail(
            f"El motor de pruebas no es el del rol de aplicación (cimenta_aplicacion): es {actual}. "
            "Con el propietario, las pruebas de permisos quedan verdes sin verificar nada."
        )


@pytest.fixture
def guarda_de_aplicacion() -> Callable[[Engine], None]:
    """La guarda, para que una prueba demuestre que rechaza al propietario (CA-9 esc. 2)."""
    return _exigir_motor_de_aplicacion


@pytest.fixture
def motor_aplicacion(
    contenedor_postgres: PostgresContainer, credenciales: dict[str, str], base_de_prueba: str
) -> Iterator[Engine]:
    """Motor síncrono de cimenta_aplicacion sobre base_de_prueba, NullPool, con la guarda de rol."""
    motor = create_engine(
        URL.create(
            "postgresql+psycopg",
            username=ROL_APLICACION,
            password=credenciales["aplicacion"],
            host=contenedor_postgres.get_container_host_ip(),
            port=int(contenedor_postgres.get_exposed_port(5432)),
            database=base_de_prueba,
        ),
        poolclass=pool.NullPool,
    )
    try:
        _exigir_motor_de_aplicacion(motor)
        yield motor
    finally:
        motor.dispose()


@pytest.fixture
def sesion_bd(motor_aplicacion: Engine) -> Iterator[Session]:
    """Session síncrona del rol de aplicación. La prueba confirma o deshace; al salir se cierra."""
    with Session(motor_aplicacion) as sesion:
        yield sesion
