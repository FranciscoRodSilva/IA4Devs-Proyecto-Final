"""Esquema de identidad (TKT-006, fila 8): TC-54 a TC-57.

`CA-16` compara la semilla de `rol` que siembra `v0002` con el enum `Rol` de `contrato_error`: si
una de las dos listas cambia sin la otra, la suite falla nombrando la clave que difiere.
`CA-17` exige que la base, y no solo el código, rechace un correo con mayúsculas: la migración
`v0004` añade `ck_usuario_email_minusculas` (S2, `PA-T10`), con su bajada.

Cada comprobación abre una conexión nueva con el rol de aplicación, o con el de migración donde
se mira el catálogo. El rol de aplicación pasa por la guarda de `conftest.py`.
"""

import uuid
from collections.abc import Callable, Iterable
from typing import Any

import psycopg
import pytest

from contrato_error.catalogos import Rol

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]
Migrar = Callable[..., None]

RESTRICCION = "ck_usuario_email_minusculas"
REVISION_ANTERIOR = "0003"


# --------------------------------------------------------------------------- ayudas


def diferencias_de_roles(de_la_base: Iterable[str], del_enum: Iterable[str]) -> list[str]:
    """Textos que nombran cada clave en que difieren la semilla de `rol` y el enum `Rol`.

    Una clave que solo está en un lado se nombra con el lado donde está. Iguales → `[]`.
    """
    en_la_base = set(de_la_base)
    en_el_enum = set(del_enum)
    diferencias = [
        f"El enum Rol tiene {clave} y la semilla de rol no."
        for clave in sorted(en_el_enum - en_la_base)
    ]
    diferencias.extend(
        f"La semilla de rol tiene {clave} y el enum Rol no."
        for clave in sorted(en_la_base - en_el_enum)
    )
    return diferencias


def claves_de_rol(conexion: Conexion) -> list[str]:
    filas = conexion.execute("SELECT clave FROM rol ORDER BY clave").fetchall()
    return [str(fila[0]) for fila in filas]


def restriccion_de_correo(conexion: Conexion) -> list[tuple[str, str]]:
    """Pares (nombre, definición) de las restricciones `CHECK` de `usuario` con ese nombre."""
    filas = conexion.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass('usuario') AND contype = 'c' AND conname = %s",
        (RESTRICCION,),
    ).fetchall()
    return [(str(nombre), str(definicion)) for nombre, definicion in filas]


def insertar_usuario(conexion: Conexion, correo: str) -> uuid.UUID:
    """INSERT directo en `usuario` con las columnas obligatorias; devuelve el `id`."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Torres", correo, "hash-de-prueba"),
    )
    return identificador


def contar_usuarios(conexion: Conexion) -> int:
    fila = conexion.execute("SELECT count(*) FROM usuario").fetchone()
    assert fila is not None
    return int(fila[0])


# --------------------------------------------------------------------------- TC-54 y TC-55


def test_tkt006_ca16_semilla_igual_al_enum(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-54 · CA-16 esc. 1 — las claves de `rol` sembradas por v0002 son las seis del enum `Rol`."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        de_la_base = claves_de_rol(aplicacion)

    del_enum = {rol.value for rol in Rol}
    assert len(del_enum) == 6
    assert set(de_la_base) == del_enum
    assert len(de_la_base) == len(set(de_la_base))
    assert diferencias_de_roles(de_la_base, del_enum) == []


def test_tkt006_ca16_la_diferencia_nombra_la_clave() -> None:
    """TC-55 · CA-16 esc. 2 — el oráculo de TC-54 nombra la clave que sobra o falta (sin base)."""
    del_enum = {rol.value for rol in Rol}
    assert len(del_enum) == 6
    assert diferencias_de_roles(del_enum, del_enum) == []

    enum_con_una_mas = [*del_enum, "GERENTE"]
    de_mas = diferencias_de_roles(del_enum, enum_con_una_mas)
    assert len(de_mas) == 1
    assert "GERENTE" in de_mas[0]
    assert "enum" in de_mas[0]

    enum_sin_almacen = [clave for clave in del_enum if clave != "ALMACEN"]
    de_menos = diferencias_de_roles(del_enum, enum_sin_almacen)
    assert len(de_menos) == 1
    assert "ALMACEN" in de_menos[0]
    assert "semilla" in de_menos[0]

    assert "GERENTE" not in " ".join(de_menos)
    assert "ALMACEN" not in " ".join(de_mas)


# --------------------------------------------------------------------------- TC-56 y TC-57


@pytest.mark.parametrize(
    "correo",
    [
        pytest.param("Ana@Cimenta.test", id="mayuscula-inicial"),
        pytest.param("ANA@CIMENTA.TEST", id="todo-en-mayusculas"),
        pytest.param("ana@Cimenta.test", id="mayuscula-en-el-dominio"),
    ],
)
def test_tkt006_ca17_la_base_rechaza_un_correo_con_mayusculas(
    base_de_prueba: str, conectar: Conectar, correo: str
) -> None:
    """TC-56 · CA-17 esc. 1, S2 — el motor rechaza un correo con mayúsculas por su restricción; el mismo en minúsculas pasa."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
            insertar_usuario(aplicacion, correo)

        assert rechazo.value.sqlstate == "23514"
        assert rechazo.value.diag.constraint_name == RESTRICCION
        assert rechazo.value.diag.table_name == "usuario"
        assert contar_usuarios(aplicacion) == 0

        insertar_usuario(aplicacion, correo.lower())

    with conectar("aplicacion", base_de_prueba) as otra:
        filas = otra.execute("SELECT email FROM usuario").fetchall()
    assert filas == [(correo.lower(),)]


def test_tkt006_ca17_la_migracion_se_revierte(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-57 · CA-17, CA-R2 — upgrade head, downgrade a 0003 y upgrade head: la restricción va y viene."""
    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        tras_subir = restriccion_de_correo(administrador)
    assert tras_subir == [(RESTRICCION, "CHECK ((email = lower(email)))")], (
        f"Tras `upgrade head` debe existir {RESTRICCION}: falta la migración v0004 (TKT-006)."
    )

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        tras_bajar = restriccion_de_correo(administrador)
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchall()
        usuario_sigue = administrador.execute(
            "SELECT to_regclass('usuario') IS NOT NULL"
        ).fetchone()
    assert tras_bajar == []
    assert version == [(REVISION_ANTERIOR,)]
    assert usuario_sigue == (True,)

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        tras_resubir = restriccion_de_correo(administrador)
    assert tras_resubir == tras_subir
