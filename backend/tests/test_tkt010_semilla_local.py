"""TKT-010b · La herramienta `herramientas.semilla_local` siembra seis usuarios y 27 insumos en local.

Cubre los datos literales (TC-B01 a TC-B03), las guardas (TC-B10, TC-B10b, TC-B11 con sus nueve
casos y TC-B12), los usuarios y su convivencia con el humo (TC-B04, TC-B04b, TC-B04c, TC-B07,
TC-B16) y los insumos, precios y restricciones (TC-B05, TC-B06, TC-B06b, TC-B08, TC-B09, TC-B09b,
TC-B13 a TC-B15). TC-B10b comprueba que un entorno de conexión incompleto se niega sin traza ni
conexión; TC-B04b y TC-B04c, que ni un fallo de sentencia ni una restricción que rechaza la fila
vuelcan el hash o la contraseña. PostgreSQL real con testcontainers; la herramienta se ejecuta con
el rol de migración y las pruebas de rechazo comprueban el dato, no solo la salida.
"""

from __future__ import annotations

import functools
import os
import re
import secrets
import subprocess
import sys
import traceback
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, LiteralString

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool

from cimenta.identidad.api.esquemas import forma_de_correo
from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2
from herramientas import semilla_local

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos, y las anotaciones no se evalúan.
    from _pytest.capture import CaptureResult
    from conftest import Conectar
    from testcontainers.postgres import PostgresContainer

VARIABLE_CONTRASENA = "CIMENTA_SEMILLA_CONTRASENA"
RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
SCRIPT_DE_HUMO = RAIZ / "frontend" / "e2e" / "sembrar_usuario_humo.py"

# Costes baratos de Argon2, los mismos que fija `entorno_de_siembra`: cada derivación tarda milisegundos.
COSTES_BARATOS = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
}

# Los únicos destinos que la herramienta admite (`CA-8`). Se repiten aquí a propósito: la prueba no
# toma del módulo bajo prueba el dato contra el que lo juzga.
HOSTS_LOCALES = frozenset({"127.0.0.1", "localhost", "::1"})

# Los usuarios del humo de Playwright y del `.env.example` (`CA-R7`): ningún usuario sembrado los pisa.
CORREO_DE_HUMO = "humo.compras@cimenta.test"
CORREO_DE_PRUEBA = "prueba.compras@cimenta.test"

# Los seis usuarios del diseño (`A4`): `(numero, clave_rol, correo, nombre)`, en el orden de la tabla.
USUARIOS_ESPERADOS: tuple[tuple[int, str, str, str], ...] = (
    (1, "DIRECCION_GENERAL", "direccion_general@cimenta.test", "Dirección General · prueba local"),
    (
        2,
        "DIRECTOR_PROYECTOS",
        "director_proyectos@cimenta.test",
        "Director de Proyectos · prueba local",
    ),
    (3, "RESIDENTE", "residente@cimenta.test", "Residente de obra · prueba local"),
    (4, "COMPRAS", "compras@cimenta.test", "Compras · prueba local"),
    (5, "ALMACEN", "almacen@cimenta.test", "Almacén · prueba local"),
    (6, "ADMINISTRACION", "administracion@cimenta.test", "Administración · prueba local"),
)


# --------------------------------------------------------------------------- ayudas


def entorno_de_siembra(
    monkeypatch: pytest.MonkeyPatch,
    contenedor: PostgresContainer,
    credenciales: dict[str, str],
    base: str,
) -> str:
    """Deja el entorno como lo tendría quien siembra en local y devuelve la contraseña de siembra.

    Fija el destino (el contenedor), la contraseña del rol de migración, una contraseña de siembra
    aleatoria y costes baratos de Argon2, y borra `PGHOSTADDR` y `PGSERVICE`, que redirigen libpq.
    """
    monkeypatch.setenv("CIMENTA_DB_HOST", contenedor.get_container_host_ip())
    monkeypatch.setenv("CIMENTA_DB_PUERTO", str(contenedor.get_exposed_port(5432)))
    monkeypatch.setenv("CIMENTA_DB_NOMBRE", base)
    monkeypatch.setenv("CIMENTA_DB_CONTRASENA_MIGRACION", credenciales["migracion"])
    contrasena = secrets.token_urlsafe(16)
    monkeypatch.setenv(VARIABLE_CONTRASENA, contrasena)
    for variable, valor in COSTES_BARATOS.items():
        monkeypatch.setenv(variable, valor)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    return contrasena


class EspiaDeMotor:
    """Sustituye a `semilla_local.create_engine` y registra cada llamada.

    Con `delegar=True` entrega el motor real: sirve cuando la prueba lee después las filas que dejó
    la herramienta. Con `delegar=False` falla si alguien lo llama: sirve cuando el destino no es de
    fiar y abrir una conexión ya es el defecto.
    """

    def __init__(self, delegar: bool) -> None:
        self.llamadas: list[tuple[Any, ...]] = []
        self._real: Callable[..., Any] | None = create_engine if delegar else None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.llamadas.append(args)
        if self._real is None:
            raise RuntimeError(
                "La herramienta abrió un motor de base de datos cuando debía negarse"
            )
        return self._real(*args, **kwargs)


def espiar_motor(monkeypatch: pytest.MonkeyPatch, *, delegar: bool) -> EspiaDeMotor:
    espia = EspiaDeMotor(delegar)
    monkeypatch.setattr(semilla_local, "create_engine", espia)
    return espia


def contar(conexion: psycopg.Connection[tuple[Any, ...]], tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def id_sembrado(grupo: int, numero: int) -> uuid.UUID:
    """El identificador fijo de una fila sembrada: el prefijo de ADR-032, el grupo y el número.

    La prueba lo calcula sola, sin tomarlo de la herramienta: es el dato contra el que la juzga.
    """
    return uuid.UUID(f"c1e0a010-{grupo:04x}-4000-8000-{numero:012x}")


# Los grupos de identificador de ADR-032: usuario, asignación de rol, insumo y precio general.
GRUPO_USUARIO: Final = 2
GRUPO_ASIGNACION: Final = 3
GRUPO_INSUMO: Final = 4
GRUPO_PRECIO: Final = 5

# `id_de_x(numero)`: el identificador fijo de la fila sembrada `numero` de cada grupo.
id_de_usuario = functools.partial(id_sembrado, GRUPO_USUARIO)
id_de_asignacion = functools.partial(id_sembrado, GRUPO_ASIGNACION)
id_de_insumo = functools.partial(id_sembrado, GRUPO_INSUMO)
id_de_precio = functools.partial(id_sembrado, GRUPO_PRECIO)


def secretos_filtrados(
    excepcion: BaseException, salida: CaptureResult[str], contrasena: str
) -> list[tuple[str, str]]:
    """Los `(canal, secreto)` que aparecen en la excepción con su cadena de causas o en la salida.

    Los canales son el texto de la traza, la salida estándar y la de error; los secretos son el
    prefijo de un hash Argon2id y la contraseña de siembra. Una lista vacía significa que no hubo fuga.
    """
    canales = {
        "excepcion": "".join(traceback.format_exception(excepcion)),
        "salida": salida.out,
        "error": salida.err,
    }
    return sorted(
        {
            (canal, secreto)
            for canal, texto in canales.items()
            for secreto, marca in (("hash", "$argon2id$"), ("contrasena", contrasena))
            if marca in texto
        }
    )


def capturar_fallo(invocar: Callable[[], int]) -> tuple[BaseException | None, int | None]:
    """Invoca `invocar` y devuelve `(excepción, código)`: la excepción si falla, el código si no.

    Atrapa cualquier `BaseException`, `SystemExit` incluida, porque lo que importa es el texto que
    deja cualquier fallo, no su clase.
    """
    try:
        return None, invocar()
    except BaseException as error:  # noqa: BLE001 · lo que importa es el texto que deja cualquier fallo
        return error, None


def contrasenas_baratas() -> ContrasenasArgon2:
    """La misma clase que verifica el inicio de sesión, con costes baratos."""
    return ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(COSTES_BARATOS))


def sembrar_en(
    motor: Engine, contrasena: str, contrasenas: ContrasenasArgon2
) -> semilla_local.ResumenSiembra:
    """Ejecuta `semilla_local.sembrar` en su propia transacción y devuelve su resumen."""
    with motor.begin() as conexion:
        return semilla_local.sembrar(conexion, contrasena=contrasena, contrasenas=contrasenas)


def fotografia_de_usuarios(
    administrador: psycopg.Connection[tuple[Any, ...]], correos: list[str]
) -> list[tuple[str, ...]]:
    """Todas las columnas de los usuarios de `correos` y de sus asignaciones, ordenadas por `id`."""
    ids = [
        fila[0]
        for fila in administrador.execute(
            "SELECT id FROM usuario WHERE email = ANY(%s) ORDER BY id", (correos,)
        ).fetchall()
    ]
    usuarios = administrador.execute(
        "SELECT row_to_json(u)::text FROM usuario u WHERE id = ANY(%s) ORDER BY id", (ids,)
    ).fetchall()
    asignaciones = administrador.execute(
        "SELECT row_to_json(ur)::text FROM usuario_rol ur WHERE usuario_id = ANY(%s) ORDER BY id",
        (ids,),
    ).fetchall()
    return [*usuarios, *asignaciones]


@pytest.fixture
def motor_migracion(
    contenedor_postgres: PostgresContainer, credenciales: dict[str, str], base_de_prueba: str
) -> Iterator[Engine]:
    """Motor síncrono del rol de migración sobre `base_de_prueba`, sin reserva de conexiones."""
    motor = create_engine(
        URL.create(
            "postgresql+psycopg",
            username="cimenta_migracion",
            password=credenciales["migracion"],
            host=contenedor_postgres.get_container_host_ip(),
            port=int(contenedor_postgres.get_exposed_port(5432)),
            database=base_de_prueba,
        ),
        poolclass=NullPool,
    )
    try:
        yield motor
    finally:
        motor.dispose()


# --------------------------------------------------------------------------- TC-B01


def test_tkt010_ca05_los_codigos_sembrados_ya_estan_normalizados() -> None:
    """TC-B01 · CA-5 esc. 2 · M4 — los 27 códigos sembrados siguen normalizados por `codigo`.

    TKT-014b compara insumos de APU por descripción normalizada (ADR-035), no por este `codigo`;
    la semilla no pretende coincidir con el lector de APU (`PA-T1`). Aquí solo se verifica que los
    códigos `TBR-001`…`TBR-027` están recortados, en mayúsculas y son únicos.
    """

    insumos = list(semilla_local.INSUMOS)
    assert len(insumos) == 27, "La precondición son los 27 insumos del diseño"
    codigos = [insumo.codigo for insumo in insumos]
    assert [insumo.numero for insumo in insumos] == list(range(1, 28))
    assert codigos == [f"TBR-{numero:03d}" for numero in range(1, 28)]
    assert [codigo.strip().upper() for codigo in codigos] == codigos
    assert len({codigo.strip().upper() for codigo in codigos}) == 27


# --------------------------------------------------------------------------- TC-B02


def test_tkt010_car5_los_costos_son_cadenas_decimales() -> None:
    """TC-B02 · CA-R5 · regla 1 — rechazo de `float`: el dinero viaja como cadena con cuatro decimales.

    Cada costo es `str` con la forma `123.4500`, la escala de `numeric(14,4)`, y no es negativo; ni el
    tipo declarado de ningún campo de `InsumoSemilla` ni el valor de ninguna fila es `float`.
    """

    insumos = list(semilla_local.INSUMOS)
    assert len(insumos) == 27, "La precondición son los 27 insumos del diseño"
    for insumo in insumos:
        assert isinstance(insumo.costo_unitario, str), (insumo.codigo, insumo.costo_unitario)
        assert re.fullmatch(r"\d+\.\d{4}", insumo.costo_unitario), (
            insumo.codigo,
            insumo.costo_unitario,
        )
        assert Decimal(insumo.costo_unitario) >= 0, (insumo.codigo, insumo.costo_unitario)
        for campo, valor in zip(insumo._fields, insumo, strict=True):
            assert not isinstance(valor, float), (insumo.codigo, campo, valor)
    tipos_declarados = semilla_local.InsumoSemilla.__annotations__
    assert set(tipos_declarados) == set(semilla_local.InsumoSemilla._fields)
    for campo, tipo in tipos_declarados.items():
        assert "float" not in str(tipo), (campo, tipo)


# --------------------------------------------------------------------------- TC-B03


def test_tkt010_ca04_los_correos_sembrados_son_validos_para_iniciar_sesion() -> None:
    """TC-B03 · CA-4 · A4 · CA-R7 — los seis correos son los del diseño y el inicio de sesión los acepta.

    Salen de la clave del rol en minúsculas con el dominio reservado `.test`, ya cumplen la restricción
    de minúsculas de la base, `forma_de_correo` del inicio de sesión los acepta y ninguno es el del
    humo de Playwright ni el de `.env.example`.
    """

    # Control: la validación del inicio de sesión sí rechaza lo que no es un correo.
    with pytest.raises(ValueError, match="correo"):
        forma_de_correo("esto no es un correo")

    usuarios = list(semilla_local.USUARIOS)
    assert len(usuarios) == 6, "La precondición son los seis usuarios del diseño"
    assert [
        (usuario.numero, usuario.clave_rol, usuario.correo, usuario.nombre) for usuario in usuarios
    ] == list(USUARIOS_ESPERADOS)
    correos = [usuario.correo for usuario in usuarios]
    assert len(set(correos)) == 6
    for correo in correos:
        assert correo == correo.lower(), correo
        assert forma_de_correo(correo) == correo, correo
    assert CORREO_DE_HUMO not in correos
    assert CORREO_DE_PRUEBA not in correos


# --------------------------------------------------------------------------- TC-B10


@pytest.mark.parametrize("variable_vacia", [False, True], ids=["ausente", "vacia"])
def test_tkt010_ca07_sin_contrasena_no_escribe_nada(
    variable_vacia: bool,
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-B10 · CA-7 · RNF-07 · M6 — rechazo: sin contraseña de siembra, la herramienta se niega y no escribe.

    Con la variable ausente o vacía, `main()` termina con un mensaje que nombra la variable que falta,
    no abre ninguna conexión y `usuario`, `insumo` y `precio_insumo` siguen sin filas. El destino es
    local a propósito: lo que se niega es la falta de contraseña, no el host.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)
    if variable_vacia:
        monkeypatch.setenv(VARIABLE_CONTRASENA, "")
    else:
        monkeypatch.delenv(VARIABLE_CONTRASENA)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, (
        f"El host del contenedor es '{host}', que no es local: la guarda de host negaría "
        "antes que la falta de contraseña y la prueba pasaría por la razón equivocada"
    )
    espia = espiar_motor(monkeypatch, delegar=True)
    with conectar("migracion", base_de_prueba) as administrador:
        for tabla in ("usuario", "insumo", "precio_insumo"):
            assert contar(administrador, tabla) == 0, f"La precondición es {tabla} sin filas"

    with pytest.raises(SystemExit) as salida:
        semilla_local.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert VARIABLE_CONTRASENA in salida.value.code
    assert espia.llamadas == []
    with conectar("migracion", base_de_prueba) as administrador:
        filas = {
            tabla: contar(administrador, tabla) for tabla in ("usuario", "insumo", "precio_insumo")
        }
    assert filas == {"usuario": 0, "insumo": 0, "precio_insumo": 0}


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("CIMENTA_DB_CONTRASENA_MIGRACION", None),
        ("CIMENTA_DB_PUERTO", "no-es-un-puerto"),
        ("CIMENTA_DB_HOST", None),
        ("CIMENTA_DB_HOST", ""),
    ],
    ids=[
        "contrasena_de_migracion_ausente",
        "puerto_no_numerico",
        "host_ausente",
        "host_vacio",
    ],
)
def test_tkt010_ca07_un_entorno_de_conexion_incompleto_se_niega_sin_traza(
    variable: str,
    valor: str | None,
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
) -> None:
    """TC-B10b · CA-7 · RNF-07 — rechazo: un entorno de conexión incompleto se niega con mensaje, no con traza.

    Con la contraseña de siembra, pero sin `CIMENTA_DB_CONTRASENA_MIGRACION`, con un
    `CIMENTA_DB_PUERTO` que no es un número o con `CIMENTA_DB_HOST` ausente o vacío, `main()` termina
    con `SystemExit` cuyo mensaje es una cadena que nombra la variable, en lugar de dejar escapar un
    `RuntimeError` o un `ValueError` con su traza, y no abre ninguna conexión. El host que se
    comprueba como local es el del contenedor, no el de la variable: en los casos de contraseña de
    migración y de puerto, `entorno_de_siembra` sí define `CIMENTA_DB_HOST`, y solo en los de host
    la variable falta o está vacía a propósito.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, "postgres")
    if valor is None:
        monkeypatch.delenv(variable)
    else:
        monkeypatch.setenv(variable, valor)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, (
        f"El host del contenedor es '{host}', que no es local: la guarda de host negaría "
        "antes que el entorno incompleto y la prueba pasaría por la razón equivocada"
    )
    espia = espiar_motor(monkeypatch, delegar=False)

    with pytest.raises(SystemExit) as salida:
        semilla_local.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert variable in salida.value.code
    assert espia.llamadas == []


# --------------------------------------------------------------------------- TC-B11


@pytest.mark.parametrize(
    "host_remoto",
    [
        "db.ejemplo.com",
        "192.168.1.10",
        "127.0.0.1.ejemplo.com",
        "localhost.ejemplo.com",
        "LOCALHOST",
        "127.0.0.1,db.ejemplo.com",
        "0.0.0.0",  # noqa: S104
        "[::1]",
        "0:0:0:0:0:0:0:1",
    ],
)
def test_tkt010_ca08_un_host_que_no_es_local_se_niega_sin_conectar(
    host_remoto: str,
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
) -> None:
    """TC-B11 · CA-8 esc. 1 · RNF-07 · M6 — rechazo: un host que no es exactamente local se niega antes de conectar.

    Un host que no es exactamente uno de `127.0.0.1`, `localhost` o `::1` se niega: la coincidencia
    es exacta, así que `LOCALHOST`, `[::1]` y `0:0:0:0:0:0:0:1` se niegan a propósito. Con la
    contraseña de siembra presente, `main()` termina con un mensaje que nombra el host y el espía
    sobre `create_engine` no registra ninguna llamada: no se abrió ninguna conexión.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, "postgres")
    monkeypatch.setenv("CIMENTA_DB_HOST", host_remoto)
    assert host_remoto not in HOSTS_LOCALES
    espia = espiar_motor(monkeypatch, delegar=False)

    with pytest.raises(SystemExit) as salida:
        semilla_local.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert host_remoto in salida.value.code
    assert espia.llamadas == []


# --------------------------------------------------------------------------- TC-B12


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("PGHOSTADDR", "10.0.0.5"), ("PGSERVICE", "produccion")],
    ids=["pghostaddr", "pgservice"],
)
def test_tkt010_ca08_pghostaddr_o_pgservice_se_niegan_sin_conectar(
    variable: str,
    valor: str,
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
) -> None:
    """TC-B12 · CA-8 esc. 2 · RNF-07 · M6 — rechazo: lo que redirige a libpq se niega antes de conectar.

    Con `CIMENTA_DB_HOST` local, pero `PGHOSTADDR` o `PGSERVICE` definidos, libpq usaría ese destino en
    lugar del host de la URL. `main()` termina con un mensaje que nombra la variable y el espía sobre
    `create_engine` no registra ninguna llamada.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, "postgres")
    monkeypatch.setenv("CIMENTA_DB_HOST", "127.0.0.1")
    monkeypatch.setenv(variable, valor)
    espia = espiar_motor(monkeypatch, delegar=False)

    with pytest.raises(SystemExit) as salida:
        semilla_local.main()

    assert isinstance(salida.value.code, str), salida.value.code
    assert variable in salida.value.code
    assert espia.llamadas == []


# --------------------------------------------------------------------------- TC-B04


def test_tkt010_ca04_la_herramienta_siembra_un_usuario_por_rol(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-B04 · CA-4 · M2 — `main()` deja seis usuarios activos, uno por rol, con hash Argon2id verificable.

    Cada usuario tiene su identificador fijo, su correo y su nombre, está activo y sin bloqueo, tiene
    exactamente una asignación de rol y los seis roles son distintos; el hash empieza por `$argon2id$`
    y `ContrasenasArgon2` lo verifica con la contraseña del entorno (y rechaza otra). La contraseña no
    aparece ni en la salida ni en ninguna columna, y la salida lleva el resumen del diseño.
    """
    contrasena = entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, f"El host del contenedor es '{host}', que no es local"
    with conectar("migracion", base_de_prueba) as administrador:
        assert contar(administrador, "usuario") == 0, "La precondición es usuario sin filas"
        assert contar(administrador, "usuario_rol") == 0, "La precondición es usuario_rol sin filas"

    codigo = semilla_local.main()

    salida = capsys.readouterr()
    assert codigo == 0
    with conectar("migracion", base_de_prueba) as administrador:
        usuarios = administrador.execute(
            "SELECT id, nombre, email, activo, bloqueado_hasta, password_hash "
            "FROM usuario ORDER BY id"
        ).fetchall()
        asignaciones = administrador.execute(
            "SELECT ur.id, ur.usuario_id, r.clave FROM usuario_rol ur "
            "JOIN rol r ON r.id = ur.rol_id ORDER BY ur.id"
        ).fetchall()
        columnas = [
            fila[0]
            for fila in administrador.execute(
                "SELECT row_to_json(u)::text FROM usuario u ORDER BY id"
            ).fetchall()
        ]

    assert [(fila[0], fila[1], fila[2]) for fila in usuarios] == [
        (id_de_usuario(numero), nombre, correo) for numero, _, correo, nombre in USUARIOS_ESPERADOS
    ]
    assert all(fila[3] is True for fila in usuarios), "Los seis usuarios deben estar activos"
    assert all(fila[4] is None for fila in usuarios), "Ninguno debe nacer bloqueado"
    assert [(fila[0], fila[1], fila[2]) for fila in asignaciones] == [
        (id_de_asignacion(numero), id_de_usuario(numero), clave_rol)
        for numero, clave_rol, _, _ in USUARIOS_ESPERADOS
    ]
    assert len({fila[2] for fila in asignaciones}) == 6
    contrasenas = contrasenas_baratas()
    for fila in usuarios:
        huella = fila[5]
        assert huella.startswith("$argon2id$"), fila[2]
        assert contrasenas.verificar(contrasena, huella), fila[2]
        assert not contrasenas.verificar(contrasena + "x", huella), fila[2]
    assert len({fila[5] for fila in usuarios}) == 6, "Cada usuario lleva su propia sal"
    assert contrasena not in salida.out
    assert contrasena not in salida.err
    assert all(contrasena not in fila for fila in columnas)
    assert "6 usuarios, 6 asignaciones de rol, 27 insumos y 27 precios generales" in salida.out, (
        salida.out
    )


def test_tkt010_ca04_un_fallo_de_siembra_no_vuelca_hashes_ni_contrasena(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_vacia: str,
    conectar: Conectar,
) -> None:
    """TC-B04b · CA-4 · RNF-07 — rechazo: si una sentencia falla, ni la excepción ni la salida llevan secretos.

    La base no está migrada (`relation "usuario" does not exist`). `main()` falla en la primera
    sentencia, cuyos parámetros incluyen un hash Argon2id; SQLAlchemy los vuelca en el texto de la
    excepción (`[parameters: ...]`). Ni el texto de la excepción con su cadena de causas, ni la salida
    estándar ni la de error pueden contener el prefijo `$argon2id$` ni la contraseña de siembra.
    """
    contrasena = entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_vacia)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, f"El host del contenedor es '{host}', que no es local"
    with conectar("migracion", base_vacia) as administrador:
        existe = administrador.execute("SELECT to_regclass('usuario')").fetchone()
    assert existe == (None,), "La precondición es una base sin la tabla usuario"

    excepcion, codigo = capturar_fallo(semilla_local.main)
    salida = capsys.readouterr()

    assert excepcion is not None, (
        f"Una siembra sobre una base sin migrar no puede devolver {codigo}"
    )
    filtraciones = secretos_filtrados(excepcion, salida, contrasena)
    assert filtraciones == [], "Un fallo de siembra filtró un secreto: (canal, secreto)"


def test_tkt010_ca04_un_check_que_rechaza_la_fila_no_vuelca_el_hash(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-B04c · CA-4 · RNF-07 — rechazo: si una restricción rechaza la fila del usuario, no se vuelca el hash.

    PostgreSQL añade `DETAIL: Failing row contains (...)` con todas las columnas de la fila rechazada,
    `password_hash` incluido, y ese texto llega a la excepción aunque `hide_parameters` oculte los
    parámetros. Con un `CHECK (false)` añadido a `usuario`, `main()` termina con `SystemExit` y un
    mensaje sin el hash; ni la excepción con su cadena de causas ni la salida llevan `$argon2id$` ni
    la contraseña de siembra, y `usuario` sigue sin filas.
    """
    contrasena = entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, f"El host del contenedor es '{host}', que no es local"
    with conectar("migracion", base_de_prueba) as administrador:
        assert contar(administrador, "usuario") == 0, "La precondición es usuario sin filas"
        administrador.execute("ALTER TABLE usuario ADD CONSTRAINT ck_prueba_siembra CHECK (false)")

    excepcion, codigo = capturar_fallo(semilla_local.main)
    salida = capsys.readouterr()

    assert excepcion is not None, f"Una siembra que la base rechaza no puede devolver {codigo}"
    filtraciones = secretos_filtrados(excepcion, salida, contrasena)
    assert filtraciones == [], (
        "Una restricción que rechaza la fila filtró un secreto: (canal, secreto)"
    )
    assert isinstance(excepcion, SystemExit), f"Se esperaba SystemExit y salió {excepcion!r}"
    assert isinstance(excepcion.code, str), excepcion.code
    with conectar("migracion", base_de_prueba) as administrador:
        assert contar(administrador, "usuario") == 0, "La transacción debe deshacerse entera"


# --------------------------------------------------------------------------- TC-B07


def test_tkt010_ca06_un_usuario_con_otro_hash_no_se_modifica(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B07 · CA-6 esc. 2 · A6 — rechazo: sembrar otra vez no sobrescribe el hash de un usuario existente.

    Tras sembrar, el hash de `COMPRAS` se cambia a mano; una segunda siembra con la contraseña del
    entorno lo deja como estaba. Los otros cinco hashes siguen verificando con la contraseña, no se
    duplica ninguna fila y el resumen sigue contando los seis usuarios y sus seis asignaciones.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()
    sembrar_en(motor_migracion, contrasena, contrasenas)
    compras = id_de_usuario(4)
    with conectar("migracion", base_de_prueba) as administrador:
        administrador.execute(
            "UPDATE usuario SET password_hash = 'hash-cambiado-a-mano' WHERE id = %s", (compras,)
        )
        cambiado = administrador.execute(
            "SELECT password_hash FROM usuario WHERE id = %s", (compras,)
        ).fetchone()
    assert cambiado == ("hash-cambiado-a-mano",), "La precondición es el hash cambiado a mano"

    resumen = sembrar_en(motor_migracion, contrasena, contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        huellas = dict(
            administrador.execute("SELECT id, password_hash FROM usuario ORDER BY id").fetchall()
        )
        filas = (contar(administrador, "usuario"), contar(administrador, "usuario_rol"))
    assert huellas[compras] == "hash-cambiado-a-mano"
    for numero in (1, 2, 3, 5, 6):
        assert contrasenas.verificar(contrasena, huellas[id_de_usuario(numero)]), numero
    assert filas == (6, 6)
    assert (resumen.usuarios, resumen.asignaciones) == (6, 6)


# --------------------------------------------------------------------------- TC-B16


def test_tkt010_car7_el_humo_no_toca_a_los_usuarios_sembrados(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-B16 · CA-R7 — el script de humo de Playwright convive con los seis usuarios sembrados.

    Tras sembrar, se fotografían los seis usuarios y sus asignaciones (todas las columnas). El script
    `frontend/e2e/sembrar_usuario_humo.py` corre como proceso aparte contra la misma base, termina con
    código 0, no cambia la fotografía y deja su propio usuario con exactamente el rol `COMPRAS`: siete
    usuarios en total.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)
    host = contenedor_postgres.get_container_host_ip()
    assert host in HOSTS_LOCALES, f"El host del contenedor es '{host}', que no es local"
    assert semilla_local.main() == 0
    correos = [correo for _, _, correo, _ in USUARIOS_ESPERADOS]
    with conectar("migracion", base_de_prueba) as administrador:
        antes = fotografia_de_usuarios(administrador, correos)
        assert len(antes) == 12, "La precondición son seis usuarios y seis asignaciones"
    entorno = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        "PYTHONUTF8": "1",
        "CIMENTA_HUMO_CORREO": CORREO_DE_HUMO,
        "CIMENTA_HUMO_CONTRASENA": secrets.token_urlsafe(16),
    }

    proceso = subprocess.run(  # noqa: S603 · el intérprete y el script son del repositorio
        [sys.executable, str(SCRIPT_DE_HUMO)],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert proceso.returncode == 0, proceso.stderr
    with conectar("migracion", base_de_prueba) as administrador:
        despues = fotografia_de_usuarios(administrador, correos)
        roles_de_humo = administrador.execute(
            "SELECT r.clave FROM usuario u JOIN usuario_rol ur ON ur.usuario_id = u.id "
            "JOIN rol r ON r.id = ur.rol_id WHERE u.email = %s",
            (CORREO_DE_HUMO,),
        ).fetchall()
        total_usuarios = contar(administrador, "usuario")
    assert despues == antes
    assert roles_de_humo == [("COMPRAS",)]
    assert total_usuarios == 7


# --------------------------------------------------------------------------- TKT-012a · fila B5: sembrador de humo parametrizado

CORREO_DE_HUMO_DIRECTOR = "humo.director@cimenta.test"


def sembrar_humo(correo: str, **extra: str) -> subprocess.CompletedProcess[str]:
    """Ejecuta `sembrar_usuario_humo.py` como proceso aparte, como lo hace `preparacion-global.ts`.

    Hereda el entorno ya preparado por `entorno_de_siembra` (destino y rol de migración), fija el correo
    y una contraseña aleatoria de humo y añade `extra` (`CIMENTA_HUMO_ROL`, `CIMENTA_HUMO_NOMBRE`).
    Quita cualquier `CIMENTA_HUMO_*` del entorno de quien ejecuta, para que no se cuele un valor real.
    """
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("CIMENTA_HUMO_")}
    entorno.update(
        {
            "PYTHONPATH": str(BACKEND),
            "PYTHONUTF8": "1",
            "CIMENTA_HUMO_CORREO": correo,
            "CIMENTA_HUMO_CONTRASENA": secrets.token_urlsafe(16),
            **extra,
        }
    )
    return subprocess.run(  # noqa: S603 · el intérprete y el script son del repositorio
        [sys.executable, str(SCRIPT_DE_HUMO)],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_tkt012a_b5_el_humo_siembra_el_rol_de_cimenta_humo_rol(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TKT-012a B5 · CA-13 — con `CIMENTA_HUMO_ROL=DIRECTOR_PROYECTOS` el usuario de humo tiene ese rol y solo ese.

    Sin esa variable el sembrador deja `COMPRAS` (TC-B16 lo comprueba y no cambia): el humo de TKT-008
    sigue igual. Con la variable, el usuario de humo del Director de Proyectos puede dar de alta una obra.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)

    proceso = sembrar_humo(CORREO_DE_HUMO_DIRECTOR, CIMENTA_HUMO_ROL="DIRECTOR_PROYECTOS")

    assert proceso.returncode == 0, proceso.stderr
    with conectar("migracion", base_de_prueba) as administrador:
        roles = administrador.execute(
            "SELECT r.clave FROM usuario u JOIN usuario_rol ur ON ur.usuario_id = u.id "
            "JOIN rol r ON r.id = ur.rol_id WHERE u.email = %s",
            (CORREO_DE_HUMO_DIRECTOR,),
        ).fetchall()
    assert roles == [("DIRECTOR_PROYECTOS",)]


def test_tkt012a_b5_el_humo_siembra_el_nombre_de_cimenta_humo_nombre(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_postgres: PostgresContainer,
    credenciales: dict[str, str],
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TKT-012a B5 · CA-13 — con `CIMENTA_HUMO_NOMBRE` el usuario de humo se llama como se pidió.

    Sin la variable el nombre fijo «Humo Compras» no describiría al usuario del Director de Proyectos.
    """
    entorno_de_siembra(monkeypatch, contenedor_postgres, credenciales, base_de_prueba)

    proceso = sembrar_humo(
        CORREO_DE_HUMO_DIRECTOR, CIMENTA_HUMO_NOMBRE="Nombre pedido por el entorno"
    )

    assert proceso.returncode == 0, proceso.stderr
    with conectar("migracion", base_de_prueba) as administrador:
        nombres = administrador.execute(
            "SELECT nombre FROM usuario WHERE email = %s", (CORREO_DE_HUMO_DIRECTOR,)
        ).fetchall()
    assert nombres == [("Nombre pedido por el entorno",)]


# --------------------------------------------------------------------------- fila B3: insumos y precios

VIGENTE_DESDE_ESPERADA = date(2026, 1, 1)

# Los 27 insumos del diseño (`A5`): `(codigo, descripcion, unidad, costo_unitario)`, en el orden de la
# tabla. Se repiten a propósito: la prueba no toma del módulo bajo prueba el dato contra el que lo juzga.
INSUMOS_ESPERADOS: tuple[tuple[str, str, str, str], ...] = (
    ("TBR-001", "Panel de yeso regular de 12.7 mm, 1.22 x 2.44 m", "PZA", "168.5000"),
    (
        "TBR-002",
        "Panel de yeso resistente a la humedad de 12.7 mm, 1.22 x 2.44 m",
        "PZA",
        "239.0000",
    ),
    ("TBR-003", "Panel de yeso resistente al fuego de 15.9 mm, 1.22 x 2.44 m", "PZA", "285.0000"),
    ("TBR-004", "Panel de cemento de 12.7 mm, 1.22 x 2.44 m", "PZA", "452.0000"),
    ("TBR-005", "Poste metálico calibre 26 de 6.35 cm x 3.05 m", "PZA", "58.4000"),
    ("TBR-006", "Canal de amarre calibre 26 de 6.35 cm x 3.05 m", "PZA", "49.9000"),
    ("TBR-007", "Poste metálico calibre 20 de 9.20 cm x 3.05 m", "PZA", "96.7000"),
    ("TBR-008", "Canal listón calibre 26 x 3.05 m", "PZA", "38.5000"),
    ("TBR-009", "Canaleta de carga calibre 22 x 3.05 m", "PZA", "44.2000"),
    ("TBR-010", "Ángulo de amarre calibre 26 x 3.05 m", "PZA", "31.8000"),
    ("TBR-011", "Esquinero metálico de 3.05 m", "PZA", "27.6000"),
    ("TBR-012", "Alambre galvanizado calibre 12", "KG", "42.0000"),
    ("TBR-013", "Tornillo para panel de yeso de 1 pulgada, caja de 1000", "CAJA", "145.0000"),
    ("TBR-014", "Tornillo de 7/16 pulgada con punta de broca, caja de 1000", "CAJA", "160.0000"),
    ("TBR-015", "Taquete de expansión con clavo de 1/4 pulgada, caja de 100", "CAJA", "95.0000"),
    ("TBR-016", "Compuesto en polvo para juntas, saco de 20 kg", "SACO", "245.0000"),
    ("TBR-017", "Cinta de papel para juntas de 5 cm x 75 m", "ROLLO", "52.0000"),
    ("TBR-018", "Cinta de malla de fibra de vidrio de 5 cm x 90 m", "ROLLO", "68.0000"),
    ("TBR-019", "Cinta de refuerzo para panel de cemento de 10 cm x 45 m", "ROLLO", "210.0000"),
    ("TBR-020", "Mortero de acabado para panel de cemento, saco de 22.7 kg", "SACO", "289.0000"),
    ("TBR-021", "Malla de fibra de vidrio para panel de cemento", "M2", "18.5000"),
    ("TBR-022", "Colchoneta aislante de fibra de vidrio de 7.6 cm", "M2", "64.0000"),
    ("TBR-023", "Perfil de remate en J calibre 26 x 3.05 m", "PZA", "35.0000"),
    ("TBR-024", "Cinta de espuma para sellado acústico de 6 mm x 30 m", "ROLLO", "85.0000"),
    ("TBR-025", "Plafón reticular de fibra mineral de 61 x 61 cm", "PZA", "41.5000"),
    ("TBR-026", "Tee principal para suspensión de plafón de 3.66 m", "PZA", "52.3000"),
    ("TBR-027", "Banda de refuerzo galvanizada calibre 20 de 15 cm", "ML", "47.0000"),
)


def fotografia_sembrada(
    administrador: psycopg.Connection[tuple[Any, ...]],
) -> dict[str, list[str]]:
    """Todas las columnas de las filas sembradas de las cuatro tablas, ordenadas por `id`.

    Cada fila viaja como el JSON que PostgreSQL arma con `row_to_json`: cualquier columna que la
    segunda siembra tocara, hasta una marca de tiempo, cambiaría el texto.
    """
    grupos = {
        "usuario": [id_de_usuario(numero) for numero in range(1, 7)],
        "usuario_rol": [id_de_asignacion(numero) for numero in range(1, 7)],
        "insumo": [id_de_insumo(numero) for numero in range(1, 28)],
        "precio_insumo": [id_de_precio(numero) for numero in range(1, 28)],
    }
    return {
        tabla: [
            fila[0]
            for fila in administrador.execute(
                sql.SQL(
                    "SELECT row_to_json(t)::text FROM {} t WHERE id = ANY(%s) ORDER BY id"
                ).format(sql.Identifier(tabla)),
                (ids,),
            ).fetchall()
        ]
        for tabla, ids in grupos.items()
    }


# Una consulta por tabla de las filas ajenas de TC-B06b, en el orden `usuario`, `insumo`, `usuario_rol`.
CONSULTAS_DE_AJENAS: Final[tuple[LiteralString, ...]] = (
    "SELECT row_to_json(t)::text FROM usuario t WHERE id = %s",
    "SELECT row_to_json(t)::text FROM insumo t WHERE id = %s",
    "SELECT row_to_json(t)::text FROM usuario_rol t WHERE id = %s",
)


def fotografia_de_ajenas(
    administrador: psycopg.Connection[tuple[Any, ...]],
    usuario: uuid.UUID,
    insumo: uuid.UUID,
    asignacion: uuid.UUID,
) -> list[list[tuple[Any, ...]]]:
    """Cada fila ajena como el JSON que PostgreSQL arma con `row_to_json`, en el orden de las consultas."""
    return [
        administrador.execute(consulta, (identificador,)).fetchall()
        for consulta, identificador in zip(
            CONSULTAS_DE_AJENAS, (usuario, insumo, asignacion), strict=True
        )
    ]


def exigir_siembra_completa(administrador: psycopg.Connection[tuple[Any, ...]]) -> None:
    """Precondición de las pruebas de rechazo: la siembra dejó los 27 insumos y sus 27 precios.

    Sin ella, una restricción que rechaza algo ajeno a la siembra pasaría aunque la herramienta no
    sembrara nada.
    """
    assert contar(administrador, "insumo") == 27, "La precondición son los 27 insumos sembrados"
    assert contar(administrador, "precio_insumo") == 27, (
        "La precondición son los 27 precios generales sembrados"
    )


def rechazo_de_la_base(
    conexion: psycopg.Connection[tuple[Any, ...]],
    sentencia: LiteralString,
    parametros: tuple[Any, ...],
) -> psycopg.Error:
    """Ejecuta una sentencia que la base debe rechazar, devuelve el error y deshace la transacción."""
    with pytest.raises(psycopg.Error) as rechazo:
        conexion.execute(sentencia, parametros)
    conexion.rollback()
    return rechazo.value


# --------------------------------------------------------------------------- TC-B05


def test_tkt010_ca05_veintisiete_insumos_con_su_precio_general(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B05 · CA-5 esc. 1 · M3 — 27 insumos de material, cada uno con su precio general vigente.

    Cada insumo lleva su identificador fijo, su código, su descripción y su unidad, es `MATERIAL`,
    está activo y no nació de una importación. Hay 27 precios, uno por insumo, sin obra, vigentes
    desde 2026-01-01 y sin fecha de fin, con el costo exacto del diseño como `Decimal`.
    """
    contrasenas = contrasenas_baratas()
    assert len(INSUMOS_ESPERADOS) == 27, "La precondición son los 27 insumos del diseño"

    sembrar_en(motor_migracion, secrets.token_urlsafe(16), contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        insumos = administrador.execute(
            "SELECT id, codigo, descripcion, tipo, unidad, activo, creado_en_importacion "
            "FROM insumo ORDER BY codigo"
        ).fetchall()
        precios = administrador.execute(
            "SELECT p.id, p.insumo_id, p.obra_id, p.costo_unitario, p.vigente_desde, p.vigente_hasta "
            "FROM precio_insumo p JOIN insumo i ON i.id = p.insumo_id ORDER BY i.codigo"
        ).fetchall()
        total_precios = contar(administrador, "precio_insumo")
    assert insumos == [
        (id_de_insumo(numero), codigo, descripcion, "MATERIAL", unidad, True, False)
        for numero, (codigo, descripcion, unidad, _) in enumerate(INSUMOS_ESPERADOS, start=1)
    ]
    assert precios == [
        (
            id_de_precio(numero),
            id_de_insumo(numero),
            None,
            Decimal(costo),
            VIGENTE_DESDE_ESPERADA,
            None,
        )
        for numero, (_, _, _, costo) in enumerate(INSUMOS_ESPERADOS, start=1)
    ]
    assert total_precios == 27, "Un precio por insumo y ninguno más"


# --------------------------------------------------------------------------- TC-B06


def test_tkt010_ca06_ejecutar_dos_veces_no_duplica(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B06 · CA-6 esc. 1 · M5 — rechazo de duplicado: la segunda siembra no cambia ninguna fila.

    Se siembra dos veces en transacciones separadas. La fotografía completa de las filas sembradas de
    `usuario`, `usuario_rol`, `insumo` y `precio_insumo` (todas las columnas, ordenadas por `id`) es
    idéntica tras la primera y tras la segunda, y los dos resúmenes cuentan seis usuarios, seis
    asignaciones, 27 insumos y 27 precios.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()

    primero = sembrar_en(motor_migracion, contrasena, contrasenas)
    with conectar("migracion", base_de_prueba) as administrador:
        despues_de_la_primera = fotografia_sembrada(administrador)
    segundo = sembrar_en(motor_migracion, contrasena, contrasenas)
    with conectar("migracion", base_de_prueba) as administrador:
        despues_de_la_segunda = fotografia_sembrada(administrador)
        totales = {
            tabla: contar(administrador, tabla)
            for tabla in ("usuario", "usuario_rol", "insumo", "precio_insumo")
        }

    assert {tabla: len(filas) for tabla, filas in despues_de_la_primera.items()} == {
        "usuario": 6,
        "usuario_rol": 6,
        "insumo": 27,
        "precio_insumo": 27,
    }
    assert despues_de_la_segunda == despues_de_la_primera
    assert totales == {"usuario": 6, "usuario_rol": 6, "insumo": 27, "precio_insumo": 27}
    assert primero == (6, 6, 27, 27)
    assert segundo == (6, 6, 27, 27)


# --------------------------------------------------------------------------- TC-B08


def test_tkt010_ca06_un_insumo_con_otra_unidad_no_se_modifica(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B08 · CA-6 esc. 3 — rechazo: sembrar otra vez no devuelve a su valor a un insumo cambiado.

    Tras sembrar, `TBR-001` pasa de `PZA` a `KG`; una segunda siembra lo deja en `KG`, con
    exactamente un precio general y sin que se duplique el insumo.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()
    sembrar_en(motor_migracion, contrasena, contrasenas)
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_siembra_completa(administrador)
        original = administrador.execute(
            "SELECT unidad FROM insumo WHERE codigo = 'TBR-001'"
        ).fetchall()
        assert original == [("PZA",)], "La precondición es TBR-001 sembrado en PZA"
        administrador.execute("UPDATE insumo SET unidad = 'KG' WHERE codigo = 'TBR-001'")

    sembrar_en(motor_migracion, contrasena, contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        unidades = administrador.execute(
            "SELECT unidad FROM insumo WHERE codigo = 'TBR-001'"
        ).fetchall()
        precios_generales = administrador.execute(
            "SELECT count(*) FROM precio_insumo WHERE insumo_id = %s AND obra_id IS NULL",
            (id_de_insumo(1),),
        ).fetchone()
        total_insumos = contar(administrador, "insumo")
    assert unidades == [("KG",)]
    assert precios_generales == (1,)
    assert total_insumos == 27


# --------------------------------------------------------------------------- TC-B09


def test_tkt010_ca06_un_insumo_con_precio_general_no_recibe_otro(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B09 · CA-6 esc. 3 · M3 — rechazo: un insumo que ya tiene precio general no recibe un segundo.

    Tras sembrar, el precio sembrado de `TBR-002` se sustituye por otro con identificador nuevo y
    costo `250.0000`. Con el identificador sembrado ausente, solo la condición `NOT EXISTS` evita que
    la segunda siembra añada otro: `TBR-002` conserva exactamente un precio general, el insertado.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()
    sembrar_en(motor_migracion, contrasena, contrasenas)
    precio_nuevo = uuid.uuid4()
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_siembra_completa(administrador)
        borrados = administrador.execute(
            "DELETE FROM precio_insumo WHERE id = %s RETURNING insumo_id", (id_de_precio(2),)
        ).fetchall()
        assert borrados == [(id_de_insumo(2),)], "La precondición es el precio sembrado de TBR-002"
        administrador.execute(
            "INSERT INTO precio_insumo (id, insumo_id, obra_id, costo_unitario, vigente_desde) "
            "VALUES (%s, %s, NULL, %s, %s)",
            (precio_nuevo, id_de_insumo(2), Decimal("250.0000"), VIGENTE_DESDE_ESPERADA),
        )

    sembrar_en(motor_migracion, contrasena, contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        generales = administrador.execute(
            "SELECT id, costo_unitario FROM precio_insumo WHERE insumo_id = %s AND obra_id IS NULL",
            (id_de_insumo(2),),
        ).fetchall()
        total_precios = contar(administrador, "precio_insumo")
    assert generales == [(precio_nuevo, Decimal("250.0000"))]
    assert total_precios == 27


def test_tkt010_ca06_una_fila_ajena_con_la_misma_unica_no_se_toca(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B06b · CA-6 esc. 1 · A6 — rechazo: una fila ajena que choca por una única distinta de `id` se respeta.

    Tras sembrar, el usuario 4 (`COMPRAS`) y el insumo `TBR-001` se sustituyen por filas ajenas con
    identificador nuevo y el mismo correo y el mismo código, y la asignación de rol del usuario 3 por
    otra con identificador nuevo para el mismo usuario y rol. La segunda siembra no lanza ninguna
    excepción (un `ON CONFLICT (id)` fallaría por la restricción única), no modifica ni duplica las
    filas ajenas y el resumen cuenta solo lo que sigue presente con el identificador sembrado.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()
    sembrar_en(motor_migracion, contrasena, contrasenas)
    usuario_ajeno = uuid.uuid4()
    insumo_ajeno = uuid.uuid4()
    asignacion_ajena = uuid.uuid4()
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_siembra_completa(administrador)
        borradas = administrador.execute(
            "DELETE FROM usuario_rol WHERE id = ANY(%s) RETURNING id",
            ([id_de_asignacion(3), id_de_asignacion(4)],),
        ).fetchall()
        assert len(borradas) == 2, (
            "La precondición son las asignaciones sembradas de los usuarios 3 y 4"
        )
        borrados = administrador.execute(
            "DELETE FROM usuario WHERE id = %s RETURNING email", (id_de_usuario(4),)
        ).fetchall()
        assert borrados == [("compras@cimenta.test",)], "La precondición es el usuario 4 sembrado"
        administrador.execute(
            "DELETE FROM precio_insumo WHERE id = %s RETURNING id", (id_de_precio(1),)
        )
        borrados = administrador.execute(
            "DELETE FROM insumo WHERE id = %s RETURNING codigo", (id_de_insumo(1),)
        ).fetchall()
        assert borrados == [("TBR-001",)], "La precondición es el insumo TBR-001 sembrado"
        administrador.execute(
            "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
            "VALUES (%s, 'Compras ajeno', 'compras@cimenta.test', 'hash-ajeno', true)",
            (usuario_ajeno,),
        )
        administrador.execute(
            "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, "
            "creado_en_importacion) VALUES (%s, 'TBR-001', 'Panel ajeno', 'MATERIAL', 'KG', "
            "true, false)",
            (insumo_ajeno,),
        )
        administrador.execute(
            "INSERT INTO usuario_rol (id, usuario_id, rol_id) "
            "SELECT %s, %s, id FROM rol WHERE clave = 'RESIDENTE'",
            (asignacion_ajena, id_de_usuario(3)),
        )
        ajenas_antes = fotografia_de_ajenas(
            administrador, usuario_ajeno, insumo_ajeno, asignacion_ajena
        )
        assert all(len(filas) == 1 for filas in ajenas_antes), (
            "La precondición son tres filas ajenas"
        )

    resumen = sembrar_en(motor_migracion, contrasena, contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        ajenas_despues = fotografia_de_ajenas(
            administrador, usuario_ajeno, insumo_ajeno, asignacion_ajena
        )
        con_el_correo = administrador.execute(
            "SELECT id FROM usuario WHERE email = 'compras@cimenta.test'"
        ).fetchall()
        con_el_codigo = administrador.execute(
            "SELECT id FROM insumo WHERE codigo = 'TBR-001'"
        ).fetchall()
        del_usuario_3 = administrador.execute(
            "SELECT id FROM usuario_rol WHERE usuario_id = %s", (id_de_usuario(3),)
        ).fetchall()
        sembradas_ausentes = administrador.execute(
            "SELECT (SELECT count(*) FROM usuario WHERE id = %s), "
            "(SELECT count(*) FROM insumo WHERE id = %s), "
            "(SELECT count(*) FROM precio_insumo WHERE insumo_id = ANY(%s))",
            (id_de_usuario(4), id_de_insumo(1), [id_de_insumo(1), insumo_ajeno]),
        ).fetchone()
        totales = {
            tabla: contar(administrador, tabla)
            for tabla in ("usuario", "usuario_rol", "insumo", "precio_insumo")
        }
    assert ajenas_despues == ajenas_antes
    assert con_el_correo == [(usuario_ajeno,)]
    assert con_el_codigo == [(insumo_ajeno,)]
    assert del_usuario_3 == [(asignacion_ajena,)]
    assert sembradas_ausentes == (0, 0, 0)
    assert totales == {"usuario": 6, "usuario_rol": 5, "insumo": 27, "precio_insumo": 26}
    # Asignaciones: las sembradas de los usuarios 1, 2, 5 y 6 más la ajena del 3; el usuario ajeno
    # que sustituye al 4 no tiene ninguna. El resumen cuenta por identificador sembrado, no por
    # correo, código ni usuario: las asignaciones sembradas 3 y 4 no existen, así que son cuatro.
    assert resumen == (5, 4, 26, 26)


def test_tkt010_ca06_un_segundo_precio_general_no_cambia_el_resumen(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B09b · CA-6 esc. 3 — rechazo: el resumen cuenta insumos con precio general, no filas de precio.

    Tras sembrar, `TBR-001` recibe un segundo precio general (identificador nuevo). La siguiente
    siembra no añade ni quita nada y su resumen sigue contando 27 precios generales sembrados (uno por
    insumo), aunque la tabla tenga ahora 28 filas.
    """
    contrasena = secrets.token_urlsafe(16)
    contrasenas = contrasenas_baratas()
    sembrar_en(motor_migracion, contrasena, contrasenas)
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_siembra_completa(administrador)
        administrador.execute(
            "INSERT INTO precio_insumo (id, insumo_id, obra_id, costo_unitario, vigente_desde) "
            "VALUES (%s, %s, NULL, %s, %s)",
            (uuid.uuid4(), id_de_insumo(1), Decimal("169.0000"), VIGENTE_DESDE_ESPERADA),
        )
        assert contar(administrador, "precio_insumo") == 28, "La precondición es un segundo precio"

    resumen = sembrar_en(motor_migracion, contrasena, contrasenas)

    with conectar("migracion", base_de_prueba) as administrador:
        total_precios = contar(administrador, "precio_insumo")
        generales_de_tbr_001 = administrador.execute(
            "SELECT count(*) FROM precio_insumo WHERE insumo_id = %s AND obra_id IS NULL",
            (id_de_insumo(1),),
        ).fetchone()
    assert total_precios == 28, "La siembra no debe añadir ni quitar precios"
    assert generales_de_tbr_001 == (2,)
    assert resumen == (6, 6, 27, 27)


# --------------------------------------------------------------------------- TC-B13


def test_tkt010_ca09_unidad_fuera_del_catalogo_sigue_rechazada(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B13 · CA-9 esc. 1 · INV-27 — rechazo: con la siembra aplicada, una unidad `LITRO` se rechaza.

    El rol de aplicación intenta insertar un insumo con unidad `LITRO`: la base responde `23514` con
    `ck_insumo_unidad` y `insumo` sigue con los 27 sembrados.
    """
    sembrar_en(motor_migracion, secrets.token_urlsafe(16), contrasenas_baratas())

    with conectar("aplicacion", base_de_prueba, autocommit=False) as aplicacion:
        exigir_siembra_completa(aplicacion)
        aplicacion.rollback()
        error = rechazo_de_la_base(
            aplicacion,
            "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, "
            "creado_en_importacion) VALUES (%s, 'TBR-900', 'Pintura vinilica', 'MATERIAL', "
            "'LITRO', true, false)",
            (uuid.uuid4(),),
        )
        restantes = contar(aplicacion, "insumo")
    assert error.sqlstate == "23514"
    assert error.diag.constraint_name == "ck_insumo_unidad"
    assert restantes == 27


# --------------------------------------------------------------------------- TC-B14


@pytest.mark.parametrize(
    ("tabla", "sentencia", "parametros", "sqlstate", "restriccion"),
    [
        pytest.param(
            "insumo",
            "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, "
            "creado_en_importacion) VALUES (%s, 'TBR-001', 'Otro panel', 'MATERIAL', 'PZA', "
            "true, false)",
            (uuid.UUID("c1e0a010-00ff-4000-8000-000000000001"),),
            "23505",
            "uq_insumo_codigo",
            id="codigo_repetido",
        ),
        pytest.param(
            "precio_insumo",
            "INSERT INTO precio_insumo (id, insumo_id, obra_id, costo_unitario, vigente_desde) "
            "VALUES (%s, %s, NULL, %s, '2026-01-01')",
            (
                uuid.UUID("c1e0a010-00ff-4000-8000-000000000002"),
                id_de_insumo(3),
                Decimal("-1.0000"),
            ),
            "23514",
            "ck_precio_insumo_costo_unitario_no_negativo",
            id="costo_negativo",
        ),
        pytest.param(
            "usuario",
            "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
            "VALUES (%s, 'Ana', 'Ana@Cimenta.TEST', 'hash-de-prueba', true)",
            (uuid.UUID("c1e0a010-00ff-4000-8000-000000000003"),),
            "23514",
            "ck_usuario_email_minusculas",
            id="correo_con_mayusculas",
        ),
    ],
)
def test_tkt010_ca09_codigo_costo_y_correo_siguen_rechazados(
    tabla: str,
    sentencia: LiteralString,
    parametros: tuple[Any, ...],
    sqlstate: str,
    restriccion: str,
    motor_migracion: Engine,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-B14 · CA-9 esc. 2 · INV-8 — rechazo: lo sembrado no relaja código único, costo ni correo.

    Con la siembra aplicada, el rol de aplicación intenta un insumo con el código `TBR-001`, un precio
    general de `TBR-003` con costo `-1.0000` y un usuario `Ana@Cimenta.TEST`. La base responde con el
    código SQLSTATE y la restricción del diseño, y la tabla conserva su recuento previo.
    """
    sembrar_en(motor_migracion, secrets.token_urlsafe(16), contrasenas_baratas())

    with conectar("aplicacion", base_de_prueba, autocommit=False) as aplicacion:
        exigir_siembra_completa(aplicacion)
        antes = contar(aplicacion, tabla)
        aplicacion.rollback()
        error = rechazo_de_la_base(aplicacion, sentencia, parametros)
        despues = contar(aplicacion, tabla)
    assert (error.sqlstate, error.diag.constraint_name) == (sqlstate, restriccion)
    assert despues == antes


# --------------------------------------------------------------------------- TC-B15


def test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio(
    motor_migracion: Engine, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-B15 · CA-10 esc. 1 · M7 — rechazo: la siembra no toca nada fuera de su alcance.

    Tras sembrar (con sus 27 insumos como precondición), `obra`, `nivel`, `area`, `partida`,
    `concepto`, `apu` y `linea_base` siguen sin filas; `empleado`, `proveedor` y `rol_oficio` no
    existen todavía, y ninguna tabla del esquema `public` lleva `simulad` en su nombre.
    """
    sembrar_en(motor_migracion, secrets.token_urlsafe(16), contrasenas_baratas())

    with conectar("migracion", base_de_prueba) as administrador:
        exigir_siembra_completa(administrador)
        tablas_vacias = ("obra", "nivel", "area", "partida", "concepto", "apu", "linea_base")
        filas = {tabla: contar(administrador, tabla) for tabla in tablas_vacias}
        sin_tabla = {
            tabla: administrador.execute("SELECT to_regclass(%s)", (tabla,)).fetchone()
            for tabla in ("empleado", "proveedor", "rol_oficio")
        }
        # Control positivo: la consulta sí encuentra una tabla con `simulad` en el nombre, así que
        # la lista vacía de abajo significa que no hay ninguna y no que la consulta no ve nada.
        consulta_simuladas = (
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename LIKE '%simulad%'"
        )
        administrador.execute("CREATE TABLE x_simulada (id integer)")
        try:
            control = administrador.execute(consulta_simuladas).fetchall()
        finally:
            administrador.execute("DROP TABLE x_simulada")
        simuladas = administrador.execute(consulta_simuladas).fetchall()
    assert control == [("x_simulada",)], "El control positivo no encontró la tabla creada"
    assert filas == dict.fromkeys(tablas_vacias, 0)
    assert sin_tabla == {"empleado": (None,), "proveedor": (None,), "rol_oficio": (None,)}
    assert simuladas == []
