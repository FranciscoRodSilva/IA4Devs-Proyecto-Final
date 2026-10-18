"""Semilla de los seis roles de negocio (TKT-003, fila 6): TC-24, TC-25, TC-27 y TC-28.

TC-28b y TC-28c no están en el plan de pruebas: cubren la bajada de la revisión `0002` por sí
sola. TC-12 baja hasta `base`, y esa bajada elimina la tabla `rol` con sus filas aunque `0002`
no borrara nada: sin estos dos casos, una bajada vacía de la semilla pasaría desapercibida.

Los identificadores de la semilla son fijos para que todos los entornos tengan las mismas filas.
Las pruebas los comparan como datos del contrato; el código de producción buscará siempre por
`clave`, nunca por `id`.
"""

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]
Migrar = Callable[..., None]
Conexion = psycopg.Connection[tuple[Any, ...]]

CORREO_ANA = "ana@cimenta.test"

SEMILLA = (
    ("c1e0a000-0000-4000-8000-000000000001", "DIRECCION_GENERAL", "Dirección General"),
    ("c1e0a000-0000-4000-8000-000000000002", "DIRECTOR_PROYECTOS", "Director de Proyectos"),
    ("c1e0a000-0000-4000-8000-000000000003", "RESIDENTE", "Residente de obra"),
    ("c1e0a000-0000-4000-8000-000000000004", "COMPRAS", "Compras"),
    ("c1e0a000-0000-4000-8000-000000000005", "ALMACEN", "Almacén"),
    ("c1e0a000-0000-4000-8000-000000000006", "ADMINISTRACION", "Administración"),
)
ID_RESIDENTE = SEMILLA[2][0]


def filas_de_rol(conexion: Conexion) -> list[tuple[str, str, str]]:
    """`(id, clave, nombre)` de todas las filas de `rol`, ordenadas por `id`."""
    filas = conexion.execute("SELECT id::text, clave, nombre FROM rol ORDER BY id").fetchall()
    return [(str(i), str(clave), str(nombre)) for i, clave, nombre in filas]


def insertar_usuario(conexion: Conexion, email: str) -> uuid.UUID:
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", email, "hash-de-prueba"),
    )
    return identificador


def test_tkt003_ca03_esc05_clave_de_rol_duplicada(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-24 · CA-3 esc. 5 — dos roles no comparten clave.

    Insertar un `id` nuevo con la clave `RESIDENTE` responde `23505` con `uq_rol_clave`. Siguen las
    seis filas, y la de `RESIDENTE` conserva su `id` y su nombre: el rechazo no pisó el dato.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.UniqueViolation) as error:
            aplicacion.execute(
                "INSERT INTO rol (id, clave, nombre) VALUES (%s, 'RESIDENTE', 'Residente duplicado')",
                (uuid.uuid4(),),
            )
        filas = filas_de_rol(aplicacion)

    assert error.value.sqlstate == "23505"
    assert error.value.diag.constraint_name == "uq_rol_clave"
    assert len(filas) == 6
    assert [fila for fila in filas if fila[1] == "RESIDENTE"] == [SEMILLA[2]]


def test_tkt003_ca03_esc06_mismo_rol_dos_veces(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-25 · CA-3 esc. 6 — un usuario no tiene el mismo rol asignado dos veces.

    Con `COMPRAS` ya asignado, repetir la pareja con otro `id` responde `23505` con
    `uq_usuario_rol_usuario_id_rol_id`, y el usuario conserva su única asignación. El rol sale de
    la semilla: con `rol` vacía no hay a quién asignar.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        compras = aplicacion.execute("SELECT id FROM rol WHERE clave = 'COMPRAS'").fetchone()
        assert compras is not None, "La tabla rol no tiene COMPRAS: la semilla no está sembrada"
        usuario = insertar_usuario(aplicacion, CORREO_ANA)
        primera = uuid.uuid4()
        aplicacion.execute(
            "INSERT INTO usuario_rol (id, usuario_id, rol_id) VALUES (%s, %s, %s)",
            (primera, usuario, compras[0]),
        )
        with pytest.raises(psycopg.errors.UniqueViolation) as error:
            aplicacion.execute(
                "INSERT INTO usuario_rol (id, usuario_id, rol_id) VALUES (%s, %s, %s)",
                (uuid.uuid4(), usuario, compras[0]),
            )
        asignaciones = aplicacion.execute(
            "SELECT id FROM usuario_rol WHERE usuario_id = %s", (usuario,)
        ).fetchall()

    assert error.value.sqlstate == "23505"
    assert error.value.diag.constraint_name == "uq_usuario_rol_usuario_id_rol_id"
    assert asignaciones == [(primera,)]


def test_tkt003_ca04_esc01_seis_roles_sembrados(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-27 · CA-4 esc. 1 — `rol` trae exactamente los seis roles del PRD §4.

    Con sus `id` fijos, sus claves y sus nombres legibles con acento. Conjunto exacto: una fila de
    más, una de menos o un nombre distinto lo rompen.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        filas = filas_de_rol(aplicacion)

    assert filas == sorted(SEMILLA)


def test_tkt003_ca04_esc02_la_siembra_no_duplica_ni_inventa(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-28 · CA-4 esc. 2 — subir, bajar y subir de nuevo deja exactamente las mismas seis filas.

    Mismos `id`, ninguna clave fuera de las seis. Se comprueba también tras la primera subida,
    para que la igualdad final no sea cierta por una semilla que nunca se sembró.
    """
    migrar(base_vacia, "0002")
    with conectar("migracion", base_vacia) as administrador:
        tras_la_primera = filas_de_rol(administrador)
    assert tras_la_primera == sorted(SEMILLA)

    migrar(base_vacia, "base", "downgrade")
    migrar(base_vacia, "0002")

    with conectar("migracion", base_vacia) as administrador:
        filas = filas_de_rol(administrador)
    assert filas == sorted(SEMILLA)
    assert {clave for _id, clave, _nombre in filas} == {clave for _id, clave, _nombre in SEMILLA}


def test_tkt003_ca04_esc02_bajar_a_0001_borra_las_seis_y_conserva_la_tabla(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-28b · CA-4 — la bajada de `0002` borra exactamente la semilla y nada más.

    Tras bajar solo hasta `0001`, `rol` existe y no tiene ninguna fila, y la versión es `0001`.
    Es lo que distingue una bajada que borra la semilla de una que la deja a `0001` para borrarla.
    """
    migrar(base_vacia, "0002")
    migrar(base_vacia, "0001", "downgrade")

    with conectar("migracion", base_vacia) as administrador:
        existe = administrador.execute("SELECT to_regclass('public.rol')").fetchone()
        filas = filas_de_rol(administrador)
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchall()

    assert existe == ("rol",)
    assert filas == []
    assert version == [("0001",)]


def test_tkt003_ca04_esc02_bajar_con_un_rol_asignado_se_rechaza(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-28c · CA-4 — no se borra un rol de negocio que un usuario tiene asignado.

    Con `COMPRAS` asignado a un usuario, bajar hasta `0001` falla con `23503` y la restricción
    `fk_usuario_rol_rol_id`; la transacción se revierte: siguen las seis filas, la asignación y la
    versión `0002`. Perder permisos en silencio sería peor que negarse a bajar.
    """
    migrar(base_vacia, "0002")
    with conectar("aplicacion", base_vacia) as aplicacion:
        compras = aplicacion.execute("SELECT id FROM rol WHERE clave = 'COMPRAS'").fetchone()
        assert compras is not None
        usuario = insertar_usuario(aplicacion, CORREO_ANA)
        aplicacion.execute(
            "INSERT INTO usuario_rol (id, usuario_id, rol_id) VALUES (%s, %s, %s)",
            (uuid.uuid4(), usuario, compras[0]),
        )

    with pytest.raises(IntegrityError) as error:
        migrar(base_vacia, "0001", "downgrade")

    origen = error.value.orig
    assert isinstance(origen, psycopg.errors.ForeignKeyViolation)
    assert origen.sqlstate == "23503"
    assert origen.diag.constraint_name == "fk_usuario_rol_rol_id"
    with conectar("migracion", base_vacia) as administrador:
        filas = filas_de_rol(administrador)
        asignaciones = administrador.execute("SELECT count(*) FROM usuario_rol").fetchone()
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchall()
    assert filas == sorted(SEMILLA)
    assert asignaciones == (1,)
    assert version == [("0002",)]
