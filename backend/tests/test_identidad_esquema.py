"""Esquema de identidad (TKT-003, fila 5): TC-20, TC-21, TC-22, TC-23, TC-26 y TC-39.

Las cinco tablas se verifican contra el catálogo de PostgreSQL y con SQL directo del rol de
aplicación: el ticket no escribe modelos ORM (PA-T11). Un rechazo comprueba el SQLSTATE y el
nombre de la restricción, y después que la tabla no cambió.

TC-26b no está en el plan de pruebas: cubre las claves foráneas que TC-26 no nombra, entre ellas
las de auditoría que decidió el usuario (PA-T1).
"""

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]
Conexion = psycopg.Connection[tuple[Any, ...]]

TABLAS = ("usuario", "rol", "usuario_rol", "sesion", "intento_acceso")
CORREO_ANA = "ana@cimenta.test"
CORREO_NADIE = "nadie@cimenta.test"

UUID = "uuid"
TEXTO = "text"
BOOLEANO = "boolean"
CON_ZONA = "timestamp with time zone"
NO = "NO"
SI = "YES"

COLUMNAS_ESPERADAS: dict[str, set[tuple[str, str, str]]] = {
    "usuario": {
        ("id", UUID, NO),
        ("nombre", TEXTO, NO),
        ("email", TEXTO, NO),
        ("password_hash", TEXTO, NO),
        ("activo", BOOLEANO, NO),
        ("ultimo_acceso", CON_ZONA, SI),
        ("bloqueado_hasta", CON_ZONA, SI),
        ("creado_en", CON_ZONA, NO),
        ("creado_por_id", UUID, SI),
        ("actualizado_en", CON_ZONA, NO),
        ("actualizado_por_id", UUID, SI),
    },
    "rol": {
        ("id", UUID, NO),
        ("clave", TEXTO, NO),
        ("nombre", TEXTO, NO),
    },
    "usuario_rol": {
        ("id", UUID, NO),
        ("usuario_id", UUID, NO),
        ("rol_id", UUID, NO),
        ("creado_en", CON_ZONA, NO),
        ("creado_por_id", UUID, SI),
        ("actualizado_en", CON_ZONA, NO),
        ("actualizado_por_id", UUID, SI),
    },
    "sesion": {
        ("id", UUID, NO),
        ("usuario_id", UUID, NO),
        ("creada_en", CON_ZONA, NO),
        ("expira_en", CON_ZONA, NO),
        ("ultima_actividad", CON_ZONA, NO),
        ("revocada_en", CON_ZONA, SI),
        ("origen_ip", TEXTO, SI),
        ("agente_usuario", TEXTO, SI),
    },
    "intento_acceso": {
        ("id", UUID, NO),
        ("email", TEXTO, NO),
        ("usuario_id", UUID, SI),
        ("exitoso", BOOLEANO, NO),
        ("ocurrido_en", CON_ZONA, NO),
        ("origen_ip", TEXTO, SI),
    },
}

COLUMNAS_DE_AUDITORIA = ("creado_en", "creado_por_id", "actualizado_en", "actualizado_por_id")


def columnas_por_tabla(conexion: Conexion) -> dict[str, set[tuple[str, str, str]]]:
    """`(columna, tipo, nulo)` de cada una de las cinco tablas; una tabla ausente no aparece."""
    filas = conexion.execute(
        "SELECT table_name, column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (list(TABLAS),),
    ).fetchall()
    resultado: dict[str, set[tuple[str, str, str]]] = {}
    for tabla, columna, tipo, nulo in filas:
        resultado.setdefault(str(tabla), set()).add((str(columna), str(tipo), str(nulo)))
    return resultado


def insertar_usuario(conexion: Conexion, email: str) -> uuid.UUID:
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", email, "hash-de-prueba"),
    )
    return identificador


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()
    assert fila is not None
    return int(fila[0])


def test_tkt003_ca03_esc01_columnas_y_tipos_del_modelo(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-20 · CA-3 esc. 1 — cada tabla tiene exactamente las columnas del modelo de datos.

    Conjunto exacto de `(columna, tipo, nulo)`: una columna de más o de menos, un tipo distinto o
    un `NOT NULL` que falta lo rompen. Toda clave primaria es una sola columna `id` de tipo `uuid`
    y lleva el nombre `pk_<tabla>`.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = columnas_por_tabla(migracion)
        claves = migracion.execute(
            "SELECT c.relname, k.conname, a.attname, format_type(a.atttypid, a.atttypmod) "
            "FROM pg_constraint k "
            "JOIN pg_class c ON c.oid = k.conrelid "
            "JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = ANY(k.conkey) "
            "WHERE k.contype = 'p' AND c.relnamespace = 'public'::regnamespace "
            "AND c.relname = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()

    assert columnas == COLUMNAS_ESPERADAS
    assert {tuple(fila) for fila in claves} == {
        (tabla, f"pk_{tabla}", "id", UUID) for tabla in TABLAS
    }


def test_tkt003_ca03_esc02_auditoria_solo_en_usuario_y_usuario_rol(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-21 · CA-3 esc. 2 — solo `usuario` y `usuario_rol` llevan columnas de auditoría.

    Llevan las cuatro, con los dos `*_por_id` nulos permitidos (la siembra y el primer usuario no
    tienen autor). `rol`, `sesion` e `intento_acceso` no llevan ninguna. La precondición exige que
    las cinco tablas existan: sin ella, «ninguna columna de auditoría» sería cierto por vacío.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = columnas_por_tabla(migracion)

    assert set(columnas) == set(TABLAS)
    auditoria = {
        tabla: {nombre: nulo for nombre, _tipo, nulo in conjunto if nombre in COLUMNAS_DE_AUDITORIA}
        for tabla, conjunto in columnas.items()
    }
    con_auditoria = {
        "creado_en": NO,
        "creado_por_id": SI,
        "actualizado_en": NO,
        "actualizado_por_id": SI,
    }
    assert auditoria == {
        "usuario": con_auditoria,
        "usuario_rol": con_auditoria,
        "rol": {},
        "sesion": {},
        "intento_acceso": {},
    }


def test_tkt003_ca03_esc03_intento_con_correo_inexistente(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-22 · CA-3 esc. 3 — un intento de acceso con un correo que no existe se registra.

    `usuario_id` es nulo: quien se equivoca de correo no tiene usuario, y el intento se guarda
    igual. La fecha la pone la tabla.
    """
    identificador = uuid.uuid4()
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        aplicacion.execute(
            "INSERT INTO intento_acceso (id, email, usuario_id, exitoso) VALUES (%s, %s, NULL, false)",
            (identificador, CORREO_NADIE),
        )
        fila = aplicacion.execute(
            "SELECT email, usuario_id, exitoso, ocurrido_en IS NOT NULL "
            "FROM intento_acceso WHERE id = %s",
            (identificador,),
        ).fetchone()

    assert fila == (CORREO_NADIE, None, False, True)


def test_tkt003_ca03_esc04_correo_duplicado(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-23 · CA-3 esc. 4 — dos usuarios no comparten correo.

    La segunda inserción responde `23505` con `uq_usuario_email`, y queda una sola fila.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        primero = insertar_usuario(aplicacion, CORREO_ANA)
        with pytest.raises(psycopg.errors.UniqueViolation) as error:
            insertar_usuario(aplicacion, CORREO_ANA)
        filas = aplicacion.execute(
            "SELECT id FROM usuario WHERE email = %s", (CORREO_ANA,)
        ).fetchall()

    assert error.value.sqlstate == "23505"
    assert error.value.diag.constraint_name == "uq_usuario_email"
    assert filas == [(primero,)]


def test_tkt003_ca03_esc07_claves_foraneas_a_la_nada(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-26 · CA-3 esc. 7 — una fila no apunta a un rol ni a un usuario que no existen.

    `usuario_rol` con un `rol_id` inexistente responde `23503` con `fk_usuario_rol_rol_id`;
    `sesion` con un `usuario_id` inexistente, con `fk_sesion_usuario_id`. Las dos tablas siguen
    vacías. El usuario de `usuario_rol` sí existe, para que falle solo la clave que se prueba.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        usuario = insertar_usuario(aplicacion, CORREO_ANA)
        rechazos: dict[str, tuple[str | None, str | None]] = {}
        for tabla, sentencia, parametros in (
            (
                "usuario_rol",
                "INSERT INTO usuario_rol (id, usuario_id, rol_id) VALUES (%s, %s, %s)",
                (uuid.uuid4(), usuario, uuid.uuid4()),
            ),
            (
                "sesion",
                "INSERT INTO sesion (id, usuario_id, expira_en) "
                "VALUES (%s, %s, now() + interval '1 hour')",
                (uuid.uuid4(), uuid.uuid4()),
            ),
        ):
            try:
                aplicacion.execute(sentencia, parametros)
            except psycopg.Error as error:
                rechazos[tabla] = (error.sqlstate, error.diag.constraint_name)
        filas = {tabla: contar(aplicacion, tabla) for tabla in ("usuario_rol", "sesion")}

    assert rechazos == {
        "usuario_rol": ("23503", "fk_usuario_rol_rol_id"),
        "sesion": ("23503", "fk_sesion_usuario_id"),
    }
    assert filas == {"usuario_rol": 0, "sesion": 0}


CLAVES_FORANEAS_RESTANTES = {
    "fk_usuario_creado_por_id": (
        "usuario",
        "INSERT INTO usuario (id, nombre, email, password_hash, creado_por_id) "
        "VALUES (%(id)s, 'Luis', 'luis@cimenta.test', 'h', %(ajeno)s)",
    ),
    "fk_usuario_actualizado_por_id": (
        "usuario",
        "INSERT INTO usuario (id, nombre, email, password_hash, actualizado_por_id) "
        "VALUES (%(id)s, 'Luis', 'luis@cimenta.test', 'h', %(ajeno)s)",
    ),
    "fk_usuario_rol_usuario_id": (
        "usuario_rol",
        "INSERT INTO usuario_rol (id, usuario_id, rol_id) VALUES (%(id)s, %(ajeno)s, %(rol)s)",
    ),
    "fk_usuario_rol_creado_por_id": (
        "usuario_rol",
        "INSERT INTO usuario_rol (id, usuario_id, rol_id, creado_por_id) "
        "VALUES (%(id)s, %(usuario)s, %(rol)s, %(ajeno)s)",
    ),
    "fk_usuario_rol_actualizado_por_id": (
        "usuario_rol",
        "INSERT INTO usuario_rol (id, usuario_id, rol_id, actualizado_por_id) "
        "VALUES (%(id)s, %(usuario)s, %(rol)s, %(ajeno)s)",
    ),
    "fk_intento_acceso_usuario_id": (
        "intento_acceso",
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso) "
        "VALUES (%(id)s, 'luis@cimenta.test', %(ajeno)s, false)",
    ),
}


@pytest.mark.parametrize("restriccion", list(CLAVES_FORANEAS_RESTANTES))
def test_tkt003_ca03_esc07_claves_foraneas_de_auditoria_y_de_usuario(
    base_de_prueba: str, conectar: Conectar, restriccion: str
) -> None:
    """TC-26b · CA-3 esc. 7, PA-T1 — ninguna otra clave foránea admite un usuario o rol ajeno.

    Cubre las seis que TC-26 no nombra: `creado_por_id` y `actualizado_por_id` de `usuario` y de
    `usuario_rol`, `usuario_rol.usuario_id` e `intento_acceso.usuario_id`. Responde `23503` con el
    nombre de la restricción y la tabla no gana ninguna fila. El rol y el usuario que sí existen
    los pone el caso para que falle solo la clave que se prueba.
    """
    tabla, sentencia = CLAVES_FORANEAS_RESTANTES[restriccion]
    rol = uuid.uuid4()
    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(
            "INSERT INTO rol (id, clave, nombre) VALUES (%s, 'PRUEBA_TKT003', 'Rol de prueba')",
            (rol,),
        )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        usuario = insertar_usuario(aplicacion, CORREO_ANA)
        antes = contar(aplicacion, tabla)
        with pytest.raises(psycopg.errors.ForeignKeyViolation) as error:
            aplicacion.execute(
                sentencia,
                {"id": uuid.uuid4(), "ajeno": uuid.uuid4(), "rol": rol, "usuario": usuario},
            )
        despues = contar(aplicacion, tabla)

    assert error.value.sqlstate == "23503"
    assert error.value.diag.constraint_name == restriccion
    assert despues == antes


def test_tkt003_ca05_esc01_migracion_es_propietaria(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-39 · CA-5 esc. 1 — el propietario de las cinco tablas es `cimenta_migracion`.

    Es el rol sobre el que `ALTER DEFAULT PRIVILEGES` declaró los permisos: si otro rol creara
    una tabla, esta nacería sin ellos. La aplicación y la lectura no poseen nada.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT tablename, tableowner FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()

    assert dict(filas) == {tabla: "cimenta_migracion" for tabla in TABLAS}
