"""Arnés de pruebas de integración de CIMENTA (TKT-003).

PostgreSQL real con testcontainers, nunca SQLite. El esquema se construye con
`alembic upgrade head` a través del mismo `env.py` que la línea de comandos, y las
pruebas de permisos se conectan con el rol de aplicación: con el propietario quedarían
verdes sin verificar nada.

Un contenedor por sesión; la plantilla `cimenta_plantilla` se migra una vez y cada
prueba recibe una base copiada de ella. Sin Docker en marcha la suite falla: no se salta.
"""

import importlib
import io
import os
import re
import secrets
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Protocol

import boto3
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from botocore.config import Config as ConfiguracionS3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session
from testcontainers.community.minio import MinioContainer
from testcontainers.community.postgres import PostgresContainer

if TYPE_CHECKING:
    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3
    from mypy_boto3_s3 import S3Client

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"

ROL_MIGRACION = "cimenta_migracion"
ROL_APLICACION = "cimenta_aplicacion"
ROL_LECTURA = "cimenta_lectura"
BASE_PLANTILLA = "cimenta_plantilla"

RolDePrueba = Literal["migracion", "aplicacion", "lectura"]

# Costes baratos de Argon2 (TKT-006): cada derivación tarda milisegundos en lugar de cientos.
ENTORNO_DE_PRUEBA = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
    # RNF-07 (TKT-057): `crear_aplicacion` exige la contraseña del rol de aplicación. Aquí es un valor
    # aleatorio que nunca conecta con nada: las pruebas pasan su propio motor.
    "CIMENTA_DB_CONTRASENA_APLICACION": secrets.token_urlsafe(16),
}
INICIO_DEL_RELOJ = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)


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


class SembrarUsuario(Protocol):
    def __call__(
        self,
        correo: str,
        contrasena: str,
        roles: Sequence[str] = (),
        activo: bool = True,
        nombre: str = "Ana Torres",
    ) -> uuid.UUID: ...


class RelojDePrueba:
    """Reloj que la prueba controla: `ahora` es un atributo y `avanzar` lo adelanta (TKT-006)."""

    def __init__(self, ahora: datetime) -> None:
        self.ahora = ahora

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, delta: timedelta) -> None:
        self.ahora = self.ahora + delta


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


def _motor_de_aplicacion(
    contenedor: PostgresContainer, credenciales: dict[str, str], base: str, **argumentos: Any
) -> Engine:
    """Motor síncrono del rol de aplicación sobre `base`, con NullPool; `argumentos` va a `create_engine`."""
    return create_engine(
        URL.create(
            "postgresql+psycopg",
            username=ROL_APLICACION,
            password=credenciales["aplicacion"],
            host=contenedor.get_container_host_ip(),
            port=int(contenedor.get_exposed_port(5432)),
            database=base,
        ),
        poolclass=pool.NullPool,
        **argumentos,
    )


@pytest.fixture
def motor_aplicacion(
    contenedor_postgres: PostgresContainer, credenciales: dict[str, str], base_de_prueba: str
) -> Iterator[Engine]:
    """Motor síncrono de cimenta_aplicacion sobre base_de_prueba, NullPool, con la guarda de rol."""
    motor = _motor_de_aplicacion(contenedor_postgres, credenciales, base_de_prueba)
    try:
        _exigir_motor_de_aplicacion(motor)
        yield motor
    finally:
        motor.dispose()


@pytest.fixture
def motor_espera_corta(
    contenedor_postgres: PostgresContainer, credenciales: dict[str, str], base_de_prueba: str
) -> Iterator[Engine]:
    """Motor del rol de aplicación sobre `base_de_prueba` cuya sesión espera un bloqueo solo 200 ms.

    TKT-017a3, fila A6c (`E-7`): `lock_timeout=200ms` por `connect_args`, en lugar de los 5 s del rol,
    para que una prueba de concurrencia vea el `55P03` sin esperar. Pasa por la misma guarda del rol
    de aplicación que `motor_aplicacion` y comprueba que el valor llegó a la sesión.
    """
    motor = _motor_de_aplicacion(
        contenedor_postgres,
        credenciales,
        base_de_prueba,
        connect_args={"options": "-c lock_timeout=200ms"},
    )
    try:
        _exigir_motor_de_aplicacion(motor)
        with motor.connect() as conexion:
            efectivo = conexion.execute(text("SHOW lock_timeout")).scalar_one()
        if efectivo != "200ms":
            pytest.fail(
                f"motor_espera_corta no fijó lock_timeout=200ms: la sesión tiene {efectivo}"
            )
        yield motor
    finally:
        motor.dispose()


@pytest.fixture
def sesion_bd(motor_aplicacion: Engine) -> Iterator[Session]:
    """Session síncrona del rol de aplicación. La prueba confirma o deshace; al salir se cierra."""
    with Session(motor_aplicacion) as sesion:
        yield sesion


# ----------------------------------------------------------------------------- TKT-006
# Ninguna de estas fixtures es `autouse` (TC-13 de TKT-004). Los símbolos de producción que
# aún no existen se importan dentro del cuerpo, para que la recolección no dependa de ellos.


@pytest.fixture
def reloj_de_prueba() -> RelojDePrueba:
    """Reloj controlado por la prueba, que empieza el 2026-10-21 a las 09:00 UTC."""
    return RelojDePrueba(INICIO_DEL_RELOJ)


@pytest.fixture
def sembrar_usuario(motor_aplicacion: Engine) -> SembrarUsuario:
    """Fábrica de usuarios reales: hash Argon2id con costes baratos, filas con el rol de aplicación.

    Los roles se buscan por `clave`, nunca por `id`; una clave que la semilla no tiene falla.
    """
    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(ENTORNO_DE_PRUEBA))

    def _sembrar(
        correo: str,
        contrasena: str,
        roles: Sequence[str] = (),
        activo: bool = True,
        nombre: str = "Ana Torres",
    ) -> uuid.UUID:
        usuario_id = uuid.uuid4()
        with motor_aplicacion.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
                    "VALUES (:id, :nombre, :email, :hash, :activo)"
                ),
                {
                    "id": usuario_id,
                    "nombre": nombre,
                    "email": correo,
                    "hash": contrasenas.derivar(contrasena),
                    "activo": activo,
                },
            )
            for clave in roles:
                resultado = conexion.execute(
                    text(
                        "INSERT INTO usuario_rol (id, usuario_id, rol_id) "
                        "SELECT :id, :usuario_id, rol.id FROM rol WHERE rol.clave = :clave"
                    ),
                    {"id": uuid.uuid4(), "usuario_id": usuario_id, "clave": clave},
                )
                assert resultado.rowcount == 1, (
                    f"El rol {clave!r} no existe en la semilla de `rol`."
                )
        return usuario_id

    return _sembrar


@pytest.fixture
def registro_tecnico() -> io.StringIO:
    """Destino del registro técnico de la aplicación: la prueba lee ahí lo que se registró."""
    return io.StringIO()


@pytest.fixture
def aplicacion_identidad(
    registro_tecnico: io.StringIO, motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> FastAPI:
    """La aplicación real con `identidad` montada, sobre la base de prueba y el reloj de la prueba."""
    from servidor.fabrica import crear_aplicacion

    return crear_aplicacion(
        destino_registro=registro_tecnico,
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        entorno=ENTORNO_DE_PRUEBA,
    )


@pytest.fixture
def cliente(aplicacion_identidad: FastAPI) -> Iterator[TestClient]:
    """Cliente HTTPS: con `http://`, httpx no devolvería la cookie `Secure` (TKT-006, design)."""
    with TestClient(
        aplicacion_identidad, base_url="https://testserver", raise_server_exceptions=False
    ) as cliente_http:
        yield cliente_http


# ----------------------------------------------------------------------------- TKT-011
# `DatosPresupuesto` es una fábrica, no una fixture `autouse`. Cada método inserta una fila
# válida con los valores mínimos, con el rol de aplicación, y devuelve su `id`. Las pruebas de
# rechazo sobrescriben el argumento que quieren romper y dejan el resto válido.


class CopiasDeLineaBase(NamedTuple):
    """Una línea base con una copia de concepto y un renglón de explosión, y los padres de ambos."""

    linea_base_id: uuid.UUID
    obra_id: uuid.UUID
    partida_concepto_id: uuid.UUID
    copia_id: uuid.UUID
    tipo_partida_id: uuid.UUID
    insumo_id: uuid.UUID
    renglon_id: uuid.UUID


class CopiasAnterioresA0010(NamedTuple):
    """Línea base sembrada con el esquema de `0009` (concepto con partida y cantidades en la misma fila)."""

    linea_base_id: uuid.UUID
    obra_id: uuid.UUID
    concepto_id: uuid.UUID
    copia_id: uuid.UUID
    renglon_id: uuid.UUID


class DatosPresupuesto:
    """Fábrica de filas del módulo `presupuesto`: `empresa`, `obra`, `tipo_partida`, `insumo`,
    `nivel`, `area`, `partida`, `concepto`, `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo`
    (migración `0006`) y, desde TKT-011b, las de la migración `0007` (`linea_base`,
    `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`, `importacion`,
    `importacion_error` y `rendimiento_observado`).

    Cuando una fila necesita un padre que la prueba no pasó, la fábrica crea el padre con una clave
    única (`nivel` y `concepto` crean su propia obra; `partida`, su propio tipo de partida), para que
    dos llamadas seguidas no choquen con una restricción `UNIQUE`.

    Los importes y los porcentajes se pasan como `Decimal` construido desde cadena, nunca desde
    `float`. Un argumento que vale `None` en una columna con valor por omisión de la base
    (`empresa.dias_semana_laboral`) omite la columna del `INSERT` para que la base lo decida.
    """

    def __init__(self, conexion: psycopg.Connection[tuple[Any, ...]]) -> None:
        self._conexion = conexion
        self._contador = 0

    def _insertar(self, tabla: str, valores: dict[str, Any]) -> uuid.UUID:
        identificador = uuid.uuid4()
        columnas = {"id": identificador, **valores}
        consulta = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(tabla),
            sql.SQL(", ").join(sql.Identifier(columna) for columna in columnas),
            sql.SQL(", ").join(sql.Placeholder() for _ in columnas),
        )
        self._conexion.execute(consulta, list(columnas.values()))
        return identificador

    def usuario(self, correo: str | None = None) -> uuid.UUID:
        """Un usuario activo con `password_hash = 'hash-de-prueba'`; el correo es único por llamada."""
        self._contador += 1
        return self._insertar(
            "usuario",
            {
                "nombre": "Usuario de prueba",
                "email": correo or f"usuario{self._contador}-{uuid.uuid4().hex[:8]}@cimenta.test",
                "password_hash": "hash-de-prueba",
            },
        )

    def empresa(
        self,
        *,
        nombre: str = "Constructora de prueba",
        rfc: str = "CPR010101AB1",
        activa: bool = True,
        dias_semana_laboral: int | None = None,
    ) -> uuid.UUID:
        valores: dict[str, Any] = {"nombre": nombre, "rfc": rfc, "activa": activa}
        if dias_semana_laboral is not None:
            valores["dias_semana_laboral"] = dias_semana_laboral
        return self._insertar("empresa", valores)

    def obra(
        self,
        *,
        codigo: str = "AP-058-25",
        empresa_id: uuid.UUID | None = None,
        creado_por_id: uuid.UUID | None = None,
        tipo_contrato: str = "PRECIO_ALZADO_MAXIMO_GARANTIZADO",
        estado: str = "PLANEACION",
        retencion_destajo_pct: Decimal = Decimal("0.050000"),
        fondo_garantia_pct: Decimal = Decimal("0.050000"),
        umbral_alerta_pct: Decimal | None = None,
        iva_acreditable: bool = True,
    ) -> uuid.UUID:
        """Una obra válida. Sin `empresa_id` o `creado_por_id` crea la empresa o el usuario que falta."""
        return self._insertar(
            "obra",
            {
                "empresa_id": empresa_id if empresa_id is not None else self.empresa(),
                "codigo": codigo,
                "nombre": f"Obra {codigo}",
                "domicilio": "Calle de prueba 1",
                "tipo_contrato": tipo_contrato,
                "retencion_destajo_pct": retencion_destajo_pct,
                "fondo_garantia_pct": fondo_garantia_pct,
                "iva_acreditable": iva_acreditable,
                "umbral_alerta_pct": umbral_alerta_pct,
                "estado": estado,
                "creado_por_id": creado_por_id if creado_por_id is not None else self.usuario(),
            },
        )

    def tipo_partida(self, *, clave: str = "MUROS", nombre: str = "Muros") -> uuid.UUID:
        """Un tipo de partida. Es un catálogo: si la clave ya existe —los cuatro de `PA-01` los siembra la
        migración `0008` (TKT-010)— devuelve su `id` sin insertar. Una prueba que necesite el duplicado
        lo inserta con SQL propio."""
        fila = self._conexion.execute(
            "SELECT id FROM tipo_partida WHERE clave = %s", (clave,)
        ).fetchone()
        if fila is not None:
            return uuid.UUID(str(fila[0]))
        return self._insertar("tipo_partida", {"clave": clave, "nombre": nombre})

    def insumo(
        self,
        *,
        codigo: str = "INS-001",
        descripcion: str = "Placa de yeso de 1/2 pulgada",
        tipo: str = "MATERIAL",
        unidad: str = "PZA",
        activo: bool = True,
        creado_en_importacion: bool = False,
    ) -> uuid.UUID:
        return self._insertar(
            "insumo",
            {
                "codigo": codigo,
                "descripcion": descripcion,
                "tipo": tipo,
                "unidad": unidad,
                "activo": activo,
                "creado_en_importacion": creado_en_importacion,
            },
        )

    def _obra_nueva(self) -> uuid.UUID:
        """Una obra con un código que no choca con el de otra obra de la misma prueba."""
        return self.obra(codigo=f"OB-{uuid.uuid4().hex[:8]}")

    def concepto(
        self,
        *,
        obra_id: uuid.UUID | None = None,
        codigo: str = "620001",
        descripcion: str = "Muro de tablaroca a dos caras",
        unidad: str = "M2",
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Un concepto de obra (código, descripción y unidad). Sin `obra_id` crea la obra."""
        obra = obra_id if obra_id is not None else self._obra_nueva()
        destino = conexion if conexion is not None else self._conexion
        return self._insertar_en(
            destino,
            "concepto",
            {
                "obra_id": obra,
                "codigo": codigo,
                "descripcion": descripcion,
                "unidad": unidad,
            },
        )

    def partida_concepto(
        self,
        *,
        concepto_id: uuid.UUID | None = None,
        partida_id: uuid.UUID | None = None,
        cantidad: Decimal = Decimal("100.0000"),
        precio_unitario: Decimal = Decimal("250.0000"),
        importe: Decimal = Decimal("25000.0000"),
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Aparición de un concepto en una partida. Sin `concepto_id` crea uno; sin `partida_id`, la jerarquía en la obra del concepto."""
        destino = conexion if conexion is not None else self._conexion
        if concepto_id is None:
            concepto_id = self.concepto(conexion=destino)
        if partida_id is None:
            fila = destino.execute(
                "SELECT obra_id FROM concepto WHERE id = %s", (concepto_id,)
            ).fetchone()
            assert fila is not None
            obra = uuid.UUID(str(fila[0]))
            partida_id = self.partida(
                area_id=self.area(nivel_id=self.nivel(obra_id=obra)), conexion=destino
            )
        return self._insertar_en(
            destino,
            "partida_concepto",
            {
                "concepto_id": concepto_id,
                "partida_id": partida_id,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "importe": importe,
            },
        )

    def _insertar_en(
        self, conexion: psycopg.Connection[tuple[Any, ...]], tabla: str, valores: dict[str, Any]
    ) -> uuid.UUID:
        identificador = uuid.uuid4()
        columnas = {"id": identificador, **valores}
        consulta = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(tabla),
            sql.SQL(", ").join(sql.Identifier(columna) for columna in columnas),
            sql.SQL(", ").join(sql.Placeholder() for _ in columnas),
        )
        conexion.execute(consulta, list(columnas.values()))
        return identificador

    def partida(
        self,
        *,
        area_id: uuid.UUID | None = None,
        tipo_partida_id: uuid.UUID | None = None,
        orden: int = 1,
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Una partida. Sin `area_id` crea el área que le falta; sin tipo, uno con clave única."""
        destino = conexion if conexion is not None else self._conexion
        if area_id is None:
            area_id = self.area(conexion=destino)
        if tipo_partida_id is None:
            tipo_partida_id = self._tipo_partida_nuevo()
        return self._insertar_en(
            destino,
            "partida",
            {
                "area_id": area_id,
                "tipo_partida_id": tipo_partida_id,
                "orden": orden,
            },
        )

    def area(
        self,
        *,
        nivel_id: uuid.UUID | None = None,
        nombre: str = "Sala",
        tipo_unidad: str | None = "M2",
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Un área. Sin `nivel_id` crea el nivel (y su obra) que le falta."""
        destino = conexion if conexion is not None else self._conexion
        if nivel_id is None:
            nivel_id = self.nivel(conexion=destino)
        return self._insertar_en(
            destino,
            "area",
            {
                "nivel_id": nivel_id,
                "nombre": nombre,
                "tipo_unidad": tipo_unidad,
            },
        )

    def nivel(
        self,
        *,
        obra_id: uuid.UUID | None = None,
        nombre: str = "Planta baja",
        orden: int = 1,
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Un nivel. Sin `obra_id` crea la obra que le falta."""
        destino = conexion if conexion is not None else self._conexion
        if obra_id is None:
            obra_id = self._obra_nueva()
        return self._insertar_en(
            destino,
            "nivel",
            {
                "obra_id": obra_id,
                "nombre": nombre,
                "orden": orden,
            },
        )

    def insumo_nuevo(self) -> uuid.UUID:
        """Un insumo con un código que no choca con el de otro insumo de la misma prueba."""
        return self.insumo(codigo=f"INS-{uuid.uuid4().hex[:8]}")

    def _tipo_partida_nuevo(self) -> uuid.UUID:
        """Un tipo de partida con una clave que no choca con la de otro de la misma prueba."""
        return self.tipo_partida(clave=f"TP-{uuid.uuid4().hex[:8]}")

    def precio_insumo(
        self,
        *,
        insumo_id: uuid.UUID | None = None,
        obra_id: uuid.UUID | None = None,
        costo_unitario: Decimal = Decimal("85.0000"),
        vigente_desde: date = date(2026, 10, 1),
        vigente_hasta: date | None = None,
    ) -> uuid.UUID:
        """Un precio de insumo. Sin `insumo_id` crea el insumo; sin `obra_id` es un precio general."""
        return self._insertar(
            "precio_insumo",
            {
                "insumo_id": insumo_id if insumo_id is not None else self.insumo_nuevo(),
                "obra_id": obra_id,
                "costo_unitario": costo_unitario,
                "vigente_desde": vigente_desde,
                "vigente_hasta": vigente_hasta,
            },
        )

    def apu(
        self,
        *,
        concepto_id: uuid.UUID | None = None,
        fecha_analisis: date | None = date(2026, 10, 1),
        analista: str | None = "Analista de prueba",
        costo_material: Decimal = Decimal("100.0000"),
        costo_mano_obra: Decimal = Decimal("50.0000"),
        costo_directo: Decimal = Decimal("150.0000"),
        total_cargos: Decimal = Decimal("0.0000"),
        total_indirectos: Decimal = Decimal("0.0000"),
        precio_unitario: Decimal = Decimal("150.0000"),
    ) -> uuid.UUID:
        """Un análisis de precio unitario. Sin `concepto_id` crea el concepto que le falta."""
        return self._insertar(
            "apu",
            {
                "concepto_id": concepto_id if concepto_id is not None else self.concepto(),
                "fecha_analisis": fecha_analisis,
                "analista": analista,
                "costo_material": costo_material,
                "costo_mano_obra": costo_mano_obra,
                "costo_directo": costo_directo,
                "total_cargos": total_cargos,
                "total_indirectos": total_indirectos,
                "precio_unitario": precio_unitario,
            },
        )

    def apu_insumo(
        self,
        *,
        apu_id: uuid.UUID | None = None,
        insumo_id: uuid.UUID | None = None,
        costo_unitario: Decimal = Decimal("100.0000"),
        rendimiento: Decimal = Decimal("1.000000"),
        cargo: Decimal = Decimal("100.0000"),
    ) -> uuid.UUID:
        """Un insumo dentro de un APU. Sin `apu_id` o `insumo_id` crea el que falta."""
        return self._insertar(
            "apu_insumo",
            {
                "apu_id": apu_id if apu_id is not None else self.apu(),
                "insumo_id": insumo_id if insumo_id is not None else self.insumo_nuevo(),
                "costo_unitario": costo_unitario,
                "rendimiento": rendimiento,
                "cargo": cargo,
            },
        )

    def apu_cargo(
        self,
        *,
        apu_id: uuid.UUID | None = None,
        tipo: str = "IVA",
        porcentaje: Decimal | None = Decimal("0.160000"),
        base_calculo: Decimal | None = Decimal("150.0000"),
        importe: Decimal = Decimal("24.0000"),
    ) -> uuid.UUID:
        """Un cargo de APU. Sin `apu_id` crea el APU que le falta."""
        return self._insertar(
            "apu_cargo",
            {
                "apu_id": apu_id if apu_id is not None else self.apu(),
                "tipo": tipo,
                "porcentaje": porcentaje,
                "base_calculo": base_calculo,
                "importe": importe,
            },
        )

    # ------------------------------------------------------------------ TKT-011b · parte b

    def linea_base(
        self,
        *,
        estado: str = "BORRADOR",
        obra_id: uuid.UUID | None = None,
        creado_por_id: uuid.UUID | None = None,
        version: int = 1,
        motivo: str | None = None,
        importe_venta: Decimal = Decimal("1000000.0000"),
        congelada_en: datetime | None = None,
        congelada_por_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Una línea base en el estado pedido. Sin `obra_id` o `creado_por_id` crea el que falta.

        Las que nacen `CONGELADA` o `SUPERSEDIDA` se insertan directamente con ese estado: el
        disparador `trg_linea_base_solo_avanza` no interviene en `INSERT` (CA-4). Como una
        congelada de verdad lleva quién y cuándo la congeló, esas dos reciben `congelada_en`
        (2026-10-21 12:00 UTC) y `congelada_por_id` (un usuario nuevo) si la prueba no los pasa;
        una `BORRADOR` los deja nulos salvo que la prueba los pida.
        """
        ya_congelada = estado in ("CONGELADA", "SUPERSEDIDA")
        if congelada_en is None and ya_congelada:
            congelada_en = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
        if congelada_por_id is None and ya_congelada:
            congelada_por_id = self.usuario()
        return self._insertar(
            "linea_base",
            {
                "obra_id": obra_id if obra_id is not None else self._obra_nueva(),
                "version": version,
                "estado": estado,
                "congelada_en": congelada_en,
                "congelada_por_id": congelada_por_id,
                "motivo": motivo,
                "importe_venta": importe_venta,
                "creado_por_id": creado_por_id if creado_por_id is not None else self.usuario(),
            },
        )

    def copia_concepto(
        self,
        *,
        linea_base_id: uuid.UUID | None = None,
        partida_concepto_id: uuid.UUID | None = None,
        codigo: str = "620001",
        cantidad: Decimal = Decimal("100.0000"),
        precio_unitario: Decimal = Decimal("250.0000"),
        importe: Decimal = Decimal("25000.0000"),
    ) -> uuid.UUID:
        """Una copia de concepto. Sin `linea_base_id` crea un `BORRADOR`; sin `partida_concepto_id`, concepto y aparición.

        El disparador del invariante 14 solo admite insertar copias en un `BORRADOR`: para tener
        una línea base congelada con copias, usa `linea_base_con_copias`.
        """
        if partida_concepto_id is None:
            partida_concepto_id = self.partida_concepto()
        return self._insertar(
            "linea_base_concepto",
            {
                "linea_base_id": linea_base_id if linea_base_id is not None else self.linea_base(),
                "partida_concepto_id": partida_concepto_id,
                "codigo": codigo,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "importe": importe,
            },
        )

    def renglon_explosion(
        self,
        *,
        linea_base_id: uuid.UUID | None = None,
        tipo_partida_id: uuid.UUID | None = None,
        insumo_id: uuid.UUID | None = None,
        cantidad_presupuestada: Decimal = Decimal("100.0000"),
        rendimiento_congelado: Decimal = Decimal("0.500000"),
        costo_unitario: Decimal = Decimal("85.0000"),
        importe_venta: Decimal = Decimal("8500.0000"),
    ) -> uuid.UUID:
        """Un renglón de explosión. Sin padres crea un `BORRADOR`, un tipo de partida y un insumo nuevos."""
        return self._insertar(
            "explosion_presupuesto",
            {
                "linea_base_id": linea_base_id if linea_base_id is not None else self.linea_base(),
                "tipo_partida_id": (
                    tipo_partida_id if tipo_partida_id is not None else self._tipo_partida_nuevo()
                ),
                "insumo_id": insumo_id if insumo_id is not None else self.insumo_nuevo(),
                "cantidad_presupuestada": cantidad_presupuestada,
                "rendimiento_congelado": rendimiento_congelado,
                "costo_unitario": costo_unitario,
                "importe_venta": importe_venta,
            },
        )

    def congelar(
        self,
        linea_base_id: uuid.UUID,
        *,
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> None:
        """Pasa una línea base `BORRADOR` a `CONGELADA` con `UPDATE`, igual que el congelado real (`PA-T14`).

        Con `conexion` la sentencia va en esa conexión, para que la prueba la tenga sin confirmar.
        Sin ella usa la de la fábrica, que confirma cada sentencia.
        """
        destino = conexion if conexion is not None else self._conexion
        destino.execute(
            "UPDATE linea_base SET estado = 'CONGELADA', congelada_en = now(), "
            "congelada_por_id = %s WHERE id = %s",
            (self.usuario(), linea_base_id),
        )

    def linea_base_con_copias(self, *, estado: str = "CONGELADA") -> CopiasDeLineaBase:
        """Una línea base en el estado pedido con una copia de concepto y un renglón de explosión.

        Como la aplicación solo inserta copias en un `BORRADOR`, las copias se insertan con la línea
        base en `BORRADOR` y después se le pasa el estado con `UPDATE`, igual que el congelado real
        (`BORRADOR` -> `CONGELADA` fija quién y cuándo, `PA-T14`; `SUPERSEDIDA` pasa por `CONGELADA`
        porque `BORRADOR` -> `SUPERSEDIDA` está prohibido).
        """
        if estado not in ("BORRADOR", "CONGELADA", "SUPERSEDIDA"):
            raise ValueError(f"Estado de línea base desconocido: {estado}")
        obra_id = self._obra_nueva()
        linea_base_id = self.linea_base(estado="BORRADOR", obra_id=obra_id)
        partida_concepto_id = self.partida_concepto(
            concepto_id=self.concepto(obra_id=obra_id),
            partida_id=self.partida(area_id=self.area(nivel_id=self.nivel(obra_id=obra_id))),
        )
        tipo_partida_id = self._tipo_partida_nuevo()
        insumo_id = self.insumo_nuevo()
        copia_id = self.copia_concepto(
            linea_base_id=linea_base_id, partida_concepto_id=partida_concepto_id
        )
        renglon_id = self.renglon_explosion(
            linea_base_id=linea_base_id, tipo_partida_id=tipo_partida_id, insumo_id=insumo_id
        )
        if estado in ("CONGELADA", "SUPERSEDIDA"):
            self.congelar(linea_base_id)
        if estado == "SUPERSEDIDA":
            self._conexion.execute(
                "UPDATE linea_base SET estado = 'SUPERSEDIDA' WHERE id = %s", (linea_base_id,)
            )
        return CopiasDeLineaBase(
            linea_base_id,
            obra_id,
            partida_concepto_id,
            copia_id,
            tipo_partida_id,
            insumo_id,
            renglon_id,
        )

    def concepto_anterior_a_0010(
        self,
        *,
        obra_id: uuid.UUID,
        partida_id: uuid.UUID,
        codigo: str = "620001",
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Concepto con el esquema de `0009` (partida y cantidades en la misma fila)."""
        destino = conexion if conexion is not None else self._conexion
        return self._insertar_en(
            destino,
            "concepto",
            {
                "obra_id": obra_id,
                "partida_id": partida_id,
                "codigo": codigo,
                "descripcion": "Muro de tablaroca a dos caras",
                "unidad": "M2",
                "cantidad": Decimal("100.0000"),
                "precio_unitario": Decimal("250.0000"),
                "importe": Decimal("25000.0000"),
            },
        )

    def copia_concepto_anterior_a_0010(
        self,
        *,
        linea_base_id: uuid.UUID,
        concepto_id: uuid.UUID,
        codigo: str = "620001",
        conexion: psycopg.Connection[tuple[Any, ...]] | None = None,
    ) -> uuid.UUID:
        """Copia que apunta a `concepto_id`, como en `0009`."""
        destino = conexion if conexion is not None else self._conexion
        return self._insertar_en(
            destino,
            "linea_base_concepto",
            {
                "linea_base_id": linea_base_id,
                "concepto_id": concepto_id,
                "codigo": codigo,
                "cantidad": Decimal("100.0000"),
                "precio_unitario": Decimal("250.0000"),
                "importe": Decimal("25000.0000"),
            },
        )

    def linea_base_con_copias_anterior_a_0010(
        self, *, estado: str = "CONGELADA"
    ) -> CopiasAnterioresA0010:
        """Línea base sembrada con columnas de `0009`; solo válida con revisión `0009` o anterior."""
        if estado not in ("BORRADOR", "CONGELADA", "SUPERSEDIDA"):
            raise ValueError(f"Estado de línea base desconocido: {estado}")
        obra_id = self._obra_nueva()
        linea_base_id = self.linea_base(estado="BORRADOR", obra_id=obra_id)
        partida_id = self.partida(area_id=self.area(nivel_id=self.nivel(obra_id=obra_id)))
        concepto_id = self.concepto_anterior_a_0010(obra_id=obra_id, partida_id=partida_id)
        copia_id = self.copia_concepto_anterior_a_0010(
            linea_base_id=linea_base_id, concepto_id=concepto_id
        )
        renglon_id = self.renglon_explosion(linea_base_id=linea_base_id)
        if estado in ("CONGELADA", "SUPERSEDIDA"):
            self.congelar(linea_base_id)
        if estado == "SUPERSEDIDA":
            self._conexion.execute(
                "UPDATE linea_base SET estado = 'SUPERSEDIDA' WHERE id = %s", (linea_base_id,)
            )
        return CopiasAnterioresA0010(linea_base_id, obra_id, concepto_id, copia_id, renglon_id)

    # ------------------------------------------------------------------ TKT-011b · filas B3 y B5

    def control(
        self,
        *,
        linea_base_id: uuid.UUID | None = None,
        tipo_partida_id: uuid.UUID | None = None,
        importe_tope: Decimal | None = None,
        importe_sugerido: Decimal = Decimal("500000.0000"),
        capturado_por_id: uuid.UUID | None = None,
        capturado_en: datetime | None = None,
        actualizado_por_id: uuid.UUID | None = None,
        actualizado_en: datetime | None = None,
        motivo_ultimo_cambio: str | None = None,
    ) -> uuid.UUID:
        """Un control presupuestal. Sin `linea_base_id` crea un `BORRADOR`; sin tipo, uno con clave única.

        El tope, la captura y la actualización nacen nulos: son lo que el Director de Proyectos
        captura después (`CA-5`). La prueba que los necesita los pasa.
        """
        return self._insertar(
            "presupuesto_control",
            {
                "linea_base_id": linea_base_id if linea_base_id is not None else self.linea_base(),
                "tipo_partida_id": (
                    tipo_partida_id if tipo_partida_id is not None else self._tipo_partida_nuevo()
                ),
                "importe_tope": importe_tope,
                "importe_sugerido": importe_sugerido,
                "capturado_por_id": capturado_por_id,
                "capturado_en": capturado_en,
                "actualizado_por_id": actualizado_por_id,
                "actualizado_en": actualizado_en,
                "motivo_ultimo_cambio": motivo_ultimo_cambio,
            },
        )

    def importacion(
        self,
        *,
        obra_id: uuid.UUID | None = None,
        archivo_id: uuid.UUID | None = None,
        estado: str = "RECIBIDO",
        progreso: Decimal | None = None,
        filas_leidas: int | None = None,
        filas_validas: int | None = None,
        filas_rechazadas: int | None = None,
        importado_por_id: uuid.UUID | None = None,
        latido: datetime | None = None,
        preparacion: Mapping[str, object] | None = None,
    ) -> uuid.UUID:
        """Una importación. Sin `archivo_id` usa un identificador que no corresponde a ningún archivo.

        `archivo_id` es lógico, sin clave foránea (`CA-7`): la fábrica no crea ningún archivo.
        Sin `obra_id` o `importado_por_id` crea el que falta.

        `preparacion` (TKT-017a3, fila A6a) es el documento JSON que dejó el análisis, tal como lo
        devuelve `preparacion_a_json`; la prueba que quiere un formato ilegible lo altera antes de
        pasarlo. Sin él la columna queda nula. El `CHECK` `ck_importacion_preparacion_tras_analisis` (`0009`)
        no admite preparación en `RECIBIDO` ni en `ANALIZANDO`.
        """
        return self._insertar(
            "importacion",
            {
                "obra_id": obra_id if obra_id is not None else self._obra_nueva(),
                "archivo_id": archivo_id if archivo_id is not None else uuid.uuid4(),
                "estado": estado,
                "progreso": progreso,
                "filas_leidas": filas_leidas,
                "filas_validas": filas_validas,
                "filas_rechazadas": filas_rechazadas,
                "importado_por_id": (
                    importado_por_id if importado_por_id is not None else self.usuario()
                ),
                "latido": latido,
                "preparacion": None if preparacion is None else Jsonb(dict(preparacion)),
            },
        )

    def error_importacion(
        self,
        *,
        importacion_id: uuid.UUID | None = None,
        hoja: str | None = "Presupuesto",
        fila: int | None = 12,
        columna: str | None = "C",
        tipo: str = "REF_ROTA",
        mensaje: str | None = "La referencia no existe en la hoja de insumos.",
        valor_original: str | None = None,
    ) -> uuid.UUID:
        """Un error de importación. Sin `importacion_id` crea la importación que le falta.

        `mensaje` admite `None` para que una prueba pueda mandar el nulo a la base (`CA-9`).
        """
        return self._insertar(
            "importacion_error",
            {
                "importacion_id": (
                    importacion_id if importacion_id is not None else self.importacion()
                ),
                "hoja": hoja,
                "fila": fila,
                "columna": columna,
                "tipo": tipo,
                "mensaje": mensaje,
                "valor_original": valor_original,
            },
        )

    def rendimiento_observado(
        self,
        *,
        obra_id: uuid.UUID | None = None,
        insumo_id: uuid.UUID | None = None,
        consumo_acumulado: Decimal = Decimal("120.0000"),
        avance_acumulado: Decimal = Decimal("100.0000"),
        rendimiento: Decimal = Decimal("1.200000"),
        rendimiento_congelado: Decimal = Decimal("1.000000"),
        divergencia_pct: Decimal = Decimal("0.200000"),
        muestra: int = 1,
        calculado_en: datetime = datetime(2026, 11, 1, 6, 0, tzinfo=UTC),
    ) -> uuid.UUID:
        """Una fila del rendimiento observado. Sin `obra_id` o `insumo_id` crea el que falta.

        La divergencia es relativa y puede ser negativa: una cuadrilla mejor que lo presupuestado.
        """
        return self._insertar(
            "rendimiento_observado",
            {
                "obra_id": obra_id if obra_id is not None else self._obra_nueva(),
                "insumo_id": insumo_id if insumo_id is not None else self.insumo_nuevo(),
                "consumo_acumulado": consumo_acumulado,
                "avance_acumulado": avance_acumulado,
                "rendimiento": rendimiento,
                "rendimiento_congelado": rendimiento_congelado,
                "divergencia_pct": divergencia_pct,
                "muestra": muestra,
                "calculado_en": calculado_en,
            },
        )


@pytest.fixture
def datos_presupuesto(base_de_prueba: str, conectar: Conectar) -> DatosPresupuesto:
    """La fábrica de filas de `presupuesto`, conectada como `cimenta_aplicacion` sobre `base_de_prueba`."""
    return DatosPresupuesto(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def datos_presupuesto_en(conectar: Conectar) -> Callable[[str], DatosPresupuesto]:
    """Fábrica de `presupuesto` sobre una base con nombre arbitrario (p. ej. sembrada en `0009`)."""

    def _fabrica(base: str) -> DatosPresupuesto:
        return DatosPresupuesto(conectar("aplicacion", base))

    return _fabrica


# ----------------------------------------------------------------------------- TKT-013
# Libro sintético con openpyxl en tmp_path; archivos reales por variable de entorno (PA-T3).


class LibroCatalogo:
    """Construye un .xlsx en disco para pruebas del lector (TKT-013b)."""

    def __init__(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        self._ruta = tmp_path / "catalogo_prueba.xlsx"
        self._libro = Workbook()
        hoja_default = self._libro.active
        assert hoja_default is not None
        self._libro.remove(hoja_default)

    def nueva_hoja(self, nombre: str) -> None:
        self._libro.create_sheet(nombre)

    def escribir_fila(self, hoja: str, numero: int, valores: Sequence[Any]) -> None:
        ws = self._libro[hoja]
        for indice, valor in enumerate(valores, start=1):
            ws.cell(row=numero, column=indice, value=valor)

    def bytes(self) -> bytes:
        self._libro.save(self._ruta)
        return self._ruta.read_bytes()


@pytest.fixture
def libro_catalogo(tmp_path: Path) -> LibroCatalogo:
    """Ayudante para armar libros .xlsx en el directorio temporal de la prueba."""
    return LibroCatalogo(tmp_path)


def _bytes_catalogo_real(variable: str, etiqueta: str) -> bytes:
    ruta_texto = os.environ.get(variable)
    if not ruta_texto:
        pytest.skip(
            f"{variable} no está definida: la prueba contra el archivo real se omite (PA-T3)"
        )
    ruta = Path(ruta_texto)
    if not ruta.is_file():
        pytest.skip(f"{variable}={ruta_texto!r} no existe: la prueba contra {etiqueta} se omite")
    return ruta.read_bytes()


@pytest.fixture
def archivo_eniti() -> bytes:
    """Bytes del catálogo ENITI (`CIMENTA_CATALOGO_ENITI`)."""
    return _bytes_catalogo_real("CIMENTA_CATALOGO_ENITI", "ENITI")


@pytest.fixture
def archivo_union() -> bytes:
    """Bytes del catálogo Union Square (`CIMENTA_CATALOGO_UNION`).

    Debe apuntar al libro P.U. con la hoja `CATALOGO DE CONCEPTOS` (CA-7: `#REF!` en E/F) y las hojas
    de APU (TKT-014).
    """
    return _bytes_catalogo_real("CIMENTA_CATALOGO_UNION", "Union Square")


# ----------------------------------------------------------------------------- estructura de 0006
# La estructura que el diseño fija para `0006`, tabla por tabla, con las «Restricciones CHECK» y
# «Unicidad e índices». La leen TC-02 de la suite de estructura y TC-17 de la de regresión, por la
# fixture `estructura_esperada`, para que haya una sola fuente. `p`, `f`, `u` y `c` llevan el
# nombre de la restricción. `i` es un índice que no respalda ninguna restricción y lleva el par
# (nombre del índice, columna indexada). Los índices de las claves primarias y de las únicas
# llevan el nombre de la restricción y no están en `i`.
ESTRUCTURA_ESPERADA: dict[str, dict[str, tuple[Any, ...]]] = {
    "empresa": {"p": ("pk_empresa",)},
    "obra": {
        "p": ("pk_obra",),
        "f": ("fk_obra_empresa_id", "fk_obra_creado_por_id", "fk_obra_actualizado_por_id"),
        "u": ("uq_obra_codigo",),
        "c": (
            "ck_obra_tipo_contrato",
            "ck_obra_estado",
            "ck_obra_retencion_destajo_pct_rango",
            "ck_obra_fondo_garantia_pct_rango",
            "ck_obra_umbral_alerta_pct_no_negativo",
        ),
    },
    "tipo_partida": {"p": ("pk_tipo_partida",), "u": ("uq_tipo_partida_clave",)},
    "insumo": {
        "p": ("pk_insumo",),
        "u": ("uq_insumo_codigo",),
        "c": ("ck_insumo_tipo", "ck_insumo_unidad"),
    },
    "nivel": {
        "p": ("pk_nivel",),
        "f": ("fk_nivel_obra_id",),
        "i": (("ix_nivel_obra_id", "obra_id"),),
    },
    "area": {
        "p": ("pk_area",),
        "f": ("fk_area_nivel_id",),
        "i": (("ix_area_nivel_id", "nivel_id"),),
    },
    "partida": {
        "p": ("pk_partida",),
        "f": ("fk_partida_area_id", "fk_partida_tipo_partida_id"),
        "i": (("ix_partida_area_id", "area_id"),),
    },
    "concepto": {
        "p": ("pk_concepto",),
        "f": ("fk_concepto_obra_id",),
        "u": ("uq_concepto_obra_id_codigo",),
        "c": ("ck_concepto_unidad",),
    },
    "precio_insumo": {
        "p": ("pk_precio_insumo",),
        "f": ("fk_precio_insumo_insumo_id", "fk_precio_insumo_obra_id"),
        "c": ("ck_precio_insumo_costo_unitario_no_negativo",),
        "i": (("ix_precio_insumo_insumo_id", "insumo_id"),),
    },
    "apu": {
        "p": ("pk_apu",),
        "f": ("fk_apu_concepto_id",),
        "c": (
            "ck_apu_costo_material_no_negativo",
            "ck_apu_costo_mano_obra_no_negativo",
            "ck_apu_costo_directo_no_negativo",
            "ck_apu_total_cargos_no_negativo",
            "ck_apu_total_indirectos_no_negativo",
            "ck_apu_precio_unitario_no_negativo",
        ),
        "i": (("ix_apu_concepto_id", "concepto_id"),),
    },
    "apu_insumo": {
        "p": ("pk_apu_insumo",),
        "f": ("fk_apu_insumo_apu_id", "fk_apu_insumo_insumo_id"),
        "c": (
            "ck_apu_insumo_costo_unitario_no_negativo",
            "ck_apu_insumo_rendimiento_no_negativo",
            "ck_apu_insumo_cargo_no_negativo",
        ),
        "i": (("ix_apu_insumo_apu_id", "apu_id"),),
    },
    "apu_cargo": {
        "p": ("pk_apu_cargo",),
        "f": ("fk_apu_cargo_apu_id",),
        "c": (
            "ck_apu_cargo_tipo",
            "ck_apu_cargo_porcentaje_no_negativo",
            "ck_apu_cargo_base_calculo_no_negativo",
            "ck_apu_cargo_importe_no_negativo",
        ),
        "i": (("ix_apu_cargo_apu_id", "apu_id"),),
    },
}


@pytest.fixture
def estructura_esperada() -> dict[str, dict[str, tuple[Any, ...]]]:
    """`ESTRUCTURA_ESPERADA` con cada grupo ordenado, lista para compararla con el catálogo."""
    return {
        tabla: {tipo: tuple(sorted(valores)) for tipo, valores in por_tipo.items()}
        for tabla, por_tipo in ESTRUCTURA_ESPERADA.items()
    }


# ----------------------------------------------------------------------------- TKT-059
# MinIO real con testcontainers, nunca un doble del almacén: una URL prefirmada que no se firma o no
# verifica la suma no lo prueba ningún doble. La imagen sale de compose.almacen.yaml, la única fuente,
# con el mismo patrón que la de PostgreSQL. El CORS de las pruebas lo fija la variable
# MINIO_API_CORS_ALLOW_ORIGIN del contenedor (E-5, caso c2), con un origen fijo de la SPA de pruebas.
# Sin esa variable MinIO refleja cualquier origen: TC-54 falla sin ella, y así lo demuestra M-20.

ORIGEN_SPA_DE_PRUEBA = "http://spa.prueba.test"
CLAVE_ACCESO_MINIO_DE_PRUEBA = "cimenta-prueba"
BUCKET_DE_PRUEBAS = "cimenta-pruebas"
REGION_S3 = "us-east-1"


def _imagen_minio() -> str:
    """La única fuente de la imagen es compose.almacen.yaml: una sola línea `image:` con un minio."""
    texto = (RAIZ / "compose.almacen.yaml").read_text(encoding="utf-8")
    coincidencias = re.findall(
        r"^\s*image:\s*((?:[\w.-]+/)*minio:\S+)\s*$", texto, flags=re.MULTILINE
    )
    if len(coincidencias) != 1:
        pytest.fail(
            f"compose.almacen.yaml debe declarar exactamente una imagen minio:<etiqueta>, "
            f"y declara {len(coincidencias)}: {coincidencias}"
        )
    return coincidencias[0]


def _endpoint_de(contenedor: MinioContainer) -> str:
    """La dirección con la que el anfitrión llega al contenedor de MinIO."""
    return f"http://{contenedor.get_container_host_ip()}:{contenedor.get_exposed_port(9000)}"


@pytest.fixture(scope="session")
def contenedor_minio() -> Iterator[MinioContainer]:
    """MinIO con la imagen de compose.almacen.yaml y CORS solo para ORIGEN_SPA_DE_PRUEBA (E-5, c2).

    La clave de acceso es fija y la secreta, aleatoria: ninguna es la de una base real. El contenedor
    vive una sesión.
    """
    contenedor = MinioContainer(
        _imagen_minio(),
        access_key=CLAVE_ACCESO_MINIO_DE_PRUEBA,
        secret_key=secrets.token_urlsafe(24),
    )
    contenedor.with_env("MINIO_API_CORS_ALLOW_ORIGIN", ORIGEN_SPA_DE_PRUEBA)
    with contenedor:
        yield contenedor


@pytest.fixture(scope="session")
def origen_spa() -> str:
    """El único origen que el contenedor de MinIO admite en CORS (ORIGEN_SPA_DE_PRUEBA)."""
    return ORIGEN_SPA_DE_PRUEBA


@pytest.fixture(scope="session")
def cliente_s3(contenedor_minio: MinioContainer) -> "S3Client":
    """Cliente boto3 directo contra MinIO de prueba, para sembrar objetos y firmar URL de prueba.

    Path style, región `us-east-1` y sin checksums automáticos: la suma viaja solo cuando la pide
    quien llama (`ChecksumSHA256`), que es lo que `TC-54` y `E-1` necesitan.
    """
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_de(contenedor_minio),
        region_name=REGION_S3,
        aws_access_key_id=contenedor_minio.access_key,
        aws_secret_access_key=contenedor_minio.secret_key,
        config=ConfiguracionS3(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
        ),
    )


@pytest.fixture(scope="session")
def bucket_de_pruebas(cliente_s3: "S3Client") -> str:
    """El bucket compartido de la sesión, creado una vez. Devuelve su nombre."""
    cliente_s3.create_bucket(Bucket=BUCKET_DE_PRUEBAS)
    return BUCKET_DE_PRUEBAS


@pytest.fixture
def almacen(contenedor_minio: MinioContainer, bucket_de_pruebas: str) -> "AlmacenS3":
    """El adaptador real sobre MinIO de prueba, con `endpoint=None`: el origen es el del contenedor.

    El import va dentro de la fixture: hasta que exista el adaptador (TKT-059, fila 5), solo fallan
    las pruebas que lo piden, no la colección de la suite.
    """
    from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

    return crear_almacen_s3(
        endpoint=None,
        origen=_endpoint_de(contenedor_minio),
        bucket=bucket_de_pruebas,
        clave_acceso=contenedor_minio.access_key,
        clave_secreta=contenedor_minio.secret_key,
    )
