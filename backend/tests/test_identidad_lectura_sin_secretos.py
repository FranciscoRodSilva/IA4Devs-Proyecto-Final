"""El rol de lectura no lee credenciales (TKT-003, fila 8, `PA-T4`, decisión D-1): TC-44 a TC-46.

`sesion.id` es el identificador opaco de la cookie (ADR-014): quien lo lea con un rol de solo
lectura puede suplantar a cualquier usuario con sesión viva. `usuario.password_hash` es el
verificador de la contraseña. Ninguno de los dos debe ser legible por `cimenta_lectura`, y lo
demás de `usuario` sí. La aplicación conserva todo su acceso: la revocación no es para ella.

Cada rechazo comprueba el SQLSTATE `42501`, no cualquier error: un `42P01` o un `42703` serían una
tabla o una columna que no existe y no probarían ningún permiso. Las consultas que no nombran
`password_hash` en la lista de columnas —`WHERE`, fila completa, `*`— también se comprueban,
porque son los canales laterales por los que un permiso por columna suele filtrarse.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]
Conexion = psycopg.Connection[tuple[Any, ...]]

CORREO = "ana@cimenta.test"
HASH_DE_PRUEBA = "hash-argon2id-de-prueba-pat4"

COLUMNAS_DE_USUARIO_LEGIBLES = (
    "id",
    "nombre",
    "email",
    "activo",
    "ultimo_acceso",
    "bloqueado_hasta",
    "creado_en",
    "creado_por_id",
    "actualizado_en",
    "actualizado_por_id",
)
COLUMNAS_DE_SESION = (
    "id",
    "usuario_id",
    "creada_en",
    "expira_en",
    "ultima_actividad",
    "revocada_en",
    "origen_ip",
    "agente_usuario",
)
PRIVILEGIOS_DE_COLUMNA = ("SELECT", "INSERT", "UPDATE", "REFERENCES")


def sqlstate_de(conexion: Conexion, sentencia: str) -> str | None:
    """SQLSTATE con que PostgreSQL rechaza la sentencia; `None` si la acepta."""
    try:
        conexion.execute(sentencia).fetchall()
    except psycopg.Error as error:
        return error.sqlstate
    return None


def sembrar_usuario_con_sesion(propietario: Conexion) -> tuple[uuid.UUID, uuid.UUID]:
    """Un usuario y una sesión viva confirmados por el propietario, para que haya qué leer."""
    usuario, sesion = uuid.uuid4(), uuid.uuid4()
    propietario.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, 'Ana Pérez', %s, %s)",
        (usuario, CORREO, HASH_DE_PRUEBA),
    )
    propietario.execute(
        "INSERT INTO sesion (id, usuario_id, expira_en) VALUES (%s, %s, %s)",
        (sesion, usuario, datetime.now(UTC) + timedelta(hours=8)),
    )
    return usuario, sesion


def test_tkt003_pat4_lectura_no_lee_sesiones(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-44 · PA-T4 · ADR-014 — el rol de lectura no lee `sesion`, cuyo `id` es la credencial.

    Con una sesión viva sembrada, `SELECT id`, `SELECT *`, `SELECT count(*)` y la lectura de una
    sola columna distinta de `id` responden `42501` cada una. La tabla no está vacía, así que un
    rechazo no se explica por falta de filas.
    """
    with conectar("migracion", base_de_prueba) as propietario:
        sembrar_usuario_con_sesion(propietario)
        sesiones_vivas = propietario.execute("SELECT count(*) FROM sesion").fetchone()
    with conectar("lectura", base_de_prueba) as lectura:
        resultados = {
            sentencia: sqlstate_de(lectura, sentencia)
            for sentencia in (
                "SELECT id FROM sesion",
                "SELECT * FROM sesion",
                "SELECT count(*) FROM sesion",
                "SELECT usuario_id FROM sesion",
            )
        }

    assert sesiones_vivas == (1,)
    assert resultados == {
        "SELECT id FROM sesion": "42501",
        "SELECT * FROM sesion": "42501",
        "SELECT count(*) FROM sesion": "42501",
        "SELECT usuario_id FROM sesion": "42501",
    }


def test_tkt003_pat4_catalogo_lectura_sin_privilegio_en_sesion(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-44 (catálogo) · PA-T4 — `has_*_privilege` niega a la lectura todo sobre `sesion`.

    Ni `SELECT` por tabla ni ningún privilegio de columna, en ninguna de las ocho columnas: un
    `GRANT SELECT (id)` olvidado aparecería aquí aunque ninguna consulta lo ejercitara.
    """
    with conectar("migracion", base_de_prueba) as propietario:
        por_tabla = propietario.execute(
            "SELECT has_table_privilege('cimenta_lectura', 'sesion', 'SELECT')"
        ).fetchone()
        por_columna = {
            (columna, privilegio): propietario.execute(
                "SELECT has_column_privilege('cimenta_lectura', 'sesion', %s, %s)",
                (columna, privilegio),
            ).fetchone()
            for columna in COLUMNAS_DE_SESION
            for privilegio in PRIVILEGIOS_DE_COLUMNA
        }

    assert por_tabla == (False,)
    assert por_columna == {
        (columna, privilegio): (False,)
        for columna in COLUMNAS_DE_SESION
        for privilegio in PRIVILEGIOS_DE_COLUMNA
    }


def test_tkt003_pat4_lectura_no_lee_password_hash(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-45 · PA-T4 — el rol de lectura no lee `usuario.password_hash`, ni directa ni lateralmente.

    `SELECT password_hash` y `SELECT *` responden `42501`, como pide el diseño. También lo hacen
    los canales que no la nombran en la lista de columnas pero la leen: un `WHERE` que sirve de
    oráculo (`password_hash LIKE 'hash%'`) y la fila completa (`SELECT usuario FROM usuario`).
    """
    with conectar("migracion", base_de_prueba) as propietario:
        sembrar_usuario_con_sesion(propietario)
    with conectar("lectura", base_de_prueba) as lectura:
        resultados = {
            sentencia: sqlstate_de(lectura, sentencia)
            for sentencia in (
                "SELECT password_hash FROM usuario",
                "SELECT * FROM usuario",
                "SELECT id FROM usuario WHERE password_hash LIKE 'hash%'",
                "SELECT usuario FROM usuario",
            )
        }

    assert resultados == {
        "SELECT password_hash FROM usuario": "42501",
        "SELECT * FROM usuario": "42501",
        "SELECT id FROM usuario WHERE password_hash LIKE 'hash%'": "42501",
        "SELECT usuario FROM usuario": "42501",
    }


def test_tkt003_pat4_catalogo_lectura_sin_privilegio_en_password_hash(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-45 (catálogo) · PA-T4 — `has_column_privilege` niega a la lectura `password_hash`.

    Ningún privilegio de columna sobre `password_hash` y tampoco `SELECT` por tabla sobre
    `usuario`: con `SELECT` por tabla, `has_column_privilege` respondería `true` para todas las
    columnas, incluida esta.
    """
    with conectar("migracion", base_de_prueba) as propietario:
        por_tabla = propietario.execute(
            "SELECT has_table_privilege('cimenta_lectura', 'usuario', 'SELECT')"
        ).fetchone()
        por_privilegio = {
            privilegio: propietario.execute(
                "SELECT has_column_privilege('cimenta_lectura', 'usuario', 'password_hash', %s)",
                (privilegio,),
            ).fetchone()
            for privilegio in PRIVILEGIOS_DE_COLUMNA
        }

    assert por_tabla == (False,)
    assert por_privilegio == {privilegio: (False,) for privilegio in PRIVILEGIOS_DE_COLUMNA}


def test_tkt003_pat4_lectura_lee_el_resto_de_usuario(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-46 · PA-T4 — el rol de lectura sigue leyendo las diez columnas de `usuario` que no son secretas.

    `SELECT id, nombre, email, activo` y la lista completa sin `password_hash` se aceptan y
    devuelven lo mismo que ve el propietario, con una fila al menos: leer una tabla vacía sin
    error no probaría nada. `count(*)` también se acepta. El catálogo confirma `SELECT` por
    columna en cada una de las diez, y ningún `INSERT`, `UPDATE` ni `REFERENCES`.

    Nace en verde, porque hoy la lectura lee todo; su papel es impedir que la fila 8 revoque de
    más (un `REVOKE` sin su `GRANT` por columna). Su dependencia queda demostrada por ese mutante.
    """
    corto = "SELECT id, nombre, email, activo FROM usuario ORDER BY email"
    completo = f"SELECT {', '.join(COLUMNAS_DE_USUARIO_LEGIBLES)} FROM usuario ORDER BY email"
    with conectar("migracion", base_de_prueba) as propietario:
        usuario, _ = sembrar_usuario_con_sesion(propietario)
        del_propietario_corto = propietario.execute(corto).fetchall()
        del_propietario_completo = propietario.execute(completo).fetchall()
        por_columna = {
            (columna, privilegio): propietario.execute(
                "SELECT has_column_privilege('cimenta_lectura', 'usuario', %s, %s)",
                (columna, privilegio),
            ).fetchone()
            for columna in COLUMNAS_DE_USUARIO_LEGIBLES
            for privilegio in PRIVILEGIOS_DE_COLUMNA
        }
    with conectar("lectura", base_de_prueba) as lectura:
        de_lectura_corto = lectura.execute(corto).fetchall()
        de_lectura_completo = lectura.execute(completo).fetchall()
        cuenta = lectura.execute("SELECT count(*) FROM usuario").fetchone()

    assert del_propietario_corto == [(usuario, "Ana Pérez", CORREO, True)]
    assert de_lectura_corto == del_propietario_corto
    assert de_lectura_completo == del_propietario_completo
    assert cuenta == (1,)
    assert por_columna == {
        (columna, privilegio): (privilegio == "SELECT",)
        for columna in COLUMNAS_DE_USUARIO_LEGIBLES
        for privilegio in PRIVILEGIOS_DE_COLUMNA
    }


def test_tkt003_pat4_aplicacion_conserva_su_acceso_a_usuario_y_sesion(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-46 (sin regresión) · PA-T4 — la aplicación sigue leyendo `password_hash` y `sesion`.

    Sobre `usuario` y `sesion` hace `INSERT`, `SELECT` —de `password_hash` y de `id`—, `UPDATE`
    y `DELETE`. Si la revocación se aplicara al rol equivocado, o a `PUBLIC`, el inicio de sesión
    de TKT-006 no podría verificar la contraseña ni encontrar la sesión. Nace en verde: hoy nadie
    revoca nada.
    """
    sesion = uuid.uuid4()
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        usuario = uuid.uuid4()
        aplicacion.execute(
            "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, 'Ana', %s, %s)",
            (usuario, CORREO, HASH_DE_PRUEBA),
        )
        aplicacion.execute(
            "INSERT INTO sesion (id, usuario_id, expira_en) VALUES (%s, %s, %s)",
            (sesion, usuario, datetime.now(UTC) + timedelta(hours=8)),
        )
        hash_leido = aplicacion.execute(
            "SELECT password_hash FROM usuario WHERE id = %s", (usuario,)
        ).fetchone()
        todo_usuario = aplicacion.execute("SELECT * FROM usuario WHERE id = %s", (usuario,))
        columnas_de_usuario = [columna.name for columna in todo_usuario.description or []]
        sesion_leida = aplicacion.execute("SELECT id FROM sesion WHERE id = %s", (sesion,))
        sesion_leida_fila = sesion_leida.fetchone()
        aplicacion.execute("UPDATE usuario SET password_hash = 'otro' WHERE id = %s", (usuario,))
        aplicacion.execute("UPDATE sesion SET origen_ip = '10.0.0.1' WHERE id = %s", (sesion,))
        borradas = aplicacion.execute("DELETE FROM sesion WHERE id = %s", (sesion,)).rowcount
        borrados = aplicacion.execute("DELETE FROM usuario WHERE id = %s", (usuario,)).rowcount

    assert hash_leido == (HASH_DE_PRUEBA,)
    assert "password_hash" in columnas_de_usuario
    assert sesion_leida_fila == (sesion,)
    assert (borradas, borrados) == (1, 1)


def test_tkt003_pat4_catalogo_aplicacion_conserva_todas_las_columnas(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-46 (catálogo, sin regresión) · PA-T4 — la aplicación conserva `SELECT`, `INSERT` y `UPDATE`.

    `has_column_privilege` responde `true` para las once columnas de `usuario` —`password_hash`
    incluida— y las ocho de `sesion`. Es la comprobación que no depende de qué consulta se
    ejercite, y la que cae si la revocación alcanza a `PUBLIC` o al rol de aplicación.
    """
    columnas_de_usuario = (*COLUMNAS_DE_USUARIO_LEGIBLES, "password_hash")
    with conectar("migracion", base_de_prueba) as propietario:
        reales = {
            (tabla, columna, privilegio): propietario.execute(
                "SELECT has_column_privilege('cimenta_aplicacion', %s, %s, %s)",
                (tabla, columna, privilegio),
            ).fetchone()
            for tabla, columnas in (
                ("usuario", columnas_de_usuario),
                ("sesion", COLUMNAS_DE_SESION),
            )
            for columna in columnas
            for privilegio in ("SELECT", "INSERT", "UPDATE")
        }

    assert len(reales) == (11 + 8) * 3
    assert all(valor == (True,) for valor in reales.values()), {
        clave: valor for clave, valor in reales.items() if valor != (True,)
    }
