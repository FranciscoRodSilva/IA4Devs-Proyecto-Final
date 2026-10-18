"""Permisos sobre las tablas de identidad e invariante 20 (TKT-003, fila 5).

TC-14, TC-34, TC-35, TC-36, TC-37, TC-38, TC-42 y TC-43. Un rechazo comprueba el SQLSTATE
(`42501`) y que la tabla quedó como estaba; el conjunto de privilegios se lee del catálogo, no
de lo que una conexión consiga hacer.

`intento_acceso` es una bitácora: la aplicación inserta y lee, nunca modifica, borra ni vacía
(invariante 20). `TRUNCATE` no se revoca porque ningún privilegio por omisión lo concede.
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
CORREO_INTENTO = "intento@cimenta.test"
CLAVE_DE_PRUEBA = "PRUEBA_TKT003"

LECTURA_Y_ESCRITURA = {"SELECT", "INSERT", "UPDATE", "DELETE"}
SOLO_ANEXAR = {"SELECT", "INSERT"}
SOLO_LECTURA = {"SELECT"}
SIN_PRIVILEGIO: set[str] = set()
# PA-T4 (D-1): el rol de lectura lee `usuario` solo por estas columnas; falta `password_hash`.
COLUMNAS_USUARIO_PARA_LECTURA = (
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


def privilegios(conexion: Conexion, tabla: str, rol: str) -> set[str]:
    """Conjunto de `privilege_type` que `relacl` concede al rol; vacío si no concede ninguno."""
    filas = conexion.execute(
        "SELECT a.privilege_type FROM pg_class c "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "JOIN pg_roles g ON g.oid = a.grantee "
        "WHERE c.oid = to_regclass(%s) AND g.rolname = %s",
        (tabla, f"cimenta_{rol}"),
    ).fetchall()
    return {str(fila[0]) for fila in filas}


def privilegios_por_columna(conexion: Conexion, tabla: str, rol: str) -> set[tuple[str, str]]:
    """Pares (columna, `privilege_type`) que `attacl` concede al rol; vacío si no concede ninguno.

    Es el complemento de `privilegios`: un `GRANT SELECT (columna)` no aparece en `relacl`.
    """
    filas = conexion.execute(
        "SELECT a.attname, x.privilege_type FROM pg_attribute a "
        "CROSS JOIN LATERAL aclexplode(a.attacl) x "
        "JOIN pg_roles g ON g.oid = x.grantee "
        "WHERE a.attrelid = to_regclass(%s) AND a.attnum > 0 AND NOT a.attisdropped "
        "AND g.rolname = %s",
        (tabla, f"cimenta_{rol}"),
    ).fetchall()
    return {(str(fila[0]), str(fila[1])) for fila in filas}


def sqlstate_de(conexion: Conexion, sentencia: str) -> str | None:
    """SQLSTATE con que PostgreSQL rechaza la sentencia; `None` si la acepta."""
    try:
        conexion.execute(sentencia)
    except psycopg.Error as error:
        return error.sqlstate
    return None


def insertar_usuario(conexion: Conexion, email: str) -> uuid.UUID:
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", email, "hash-de-prueba"),
    )
    return identificador


def insertar_intento(conexion: Conexion, email: str, exitoso: bool = False) -> uuid.UUID:
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso) VALUES (%s, %s, NULL, %s)",
        (identificador, email, exitoso),
    )
    return identificador


def insertar_rol_de_prueba(conexion: Conexion) -> uuid.UUID:
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO rol (id, clave, nombre) VALUES (%s, %s, 'Rol de prueba')",
        (identificador, CLAVE_DE_PRUEBA),
    )
    return identificador


def fotografia(conexion: Conexion) -> tuple[tuple[Any, ...], ...]:
    """Estructura de `public`: tablas, columnas, restricciones, índices y privilegios por tabla."""
    consultas = (
        "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public' ORDER BY 1",
        "SELECT table_name, column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = 'public' ORDER BY 1, 2",
        "SELECT conrelid::regclass::text, conname, contype, pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2",
        "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY indexname",
        "SELECT relname, relacl::text FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' ORDER BY 1",
    )
    return tuple(tuple(conexion.execute(consulta).fetchall()) for consulta in consultas)


def test_tkt003_ca02_esc04_la_aplicacion_no_puede_migrar(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-14 · CA-2 esc. 4 — el rol de aplicación no crea, altera ni borra objetos.

    `CREATE TABLE`, `ALTER TABLE usuario` y `DROP TABLE rol` responden `42501`, y la estructura
    de la base es idéntica antes y después. La fotografía incluye las cinco tablas, para que la
    igualdad no sea cierta por una base vacía.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        antes = fotografia(migracion)
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        resultados = {
            sentencia: sqlstate_de(aplicacion, sentencia)
            for sentencia in (
                "CREATE TABLE desechable_tkt003 (n int)",
                "ALTER TABLE usuario ADD COLUMN desechable_tkt003 int",
                "DROP TABLE rol",
            )
        }
    with conectar("migracion", base_de_prueba) as migracion:
        despues = fotografia(migracion)

    assert resultados == {
        "CREATE TABLE desechable_tkt003 (n int)": "42501",
        "ALTER TABLE usuario ADD COLUMN desechable_tkt003 int": "42501",
        "DROP TABLE rol": "42501",
    }
    assert despues == antes
    assert {fila[0] for fila in despues[0]} >= set(TABLAS)


def test_tkt003_ca06_esc01_aplicacion_registra_y_lee_intentos(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-34 · CA-6 esc. 1 — la aplicación inserta y lee intentos de acceso de un usuario real."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        usuario = insertar_usuario(aplicacion, CORREO_ANA)
        intento = uuid.uuid4()
        aplicacion.execute(
            "INSERT INTO intento_acceso (id, email, usuario_id, exitoso) VALUES (%s, %s, %s, true)",
            (intento, CORREO_ANA, usuario),
        )
        fila = aplicacion.execute(
            "SELECT email, usuario_id, exitoso FROM intento_acceso WHERE id = %s", (intento,)
        ).fetchone()

    assert fila == (CORREO_ANA, usuario, True)


def test_tkt003_ca06_esc02_aplicacion_no_modifica_intento(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-35 · CA-6 esc. 2 · invariante 20 — un intento registrado no se modifica.

    El `UPDATE` responde `42501` y la fila conserva `exitoso = false` y su `email`.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        intento = insertar_intento(aplicacion, CORREO_INTENTO, exitoso=False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
            aplicacion.execute("UPDATE intento_acceso SET exitoso = true WHERE id = %s", (intento,))
        fila = aplicacion.execute(
            "SELECT email, exitoso FROM intento_acceso WHERE id = %s", (intento,)
        ).fetchone()

    assert error.value.sqlstate == "42501"
    assert "intento_acceso" in str(error.value)
    assert fila == (CORREO_INTENTO, False)


def test_tkt003_ca06_esc03_aplicacion_no_borra_intento(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-36 · CA-6 esc. 3 · invariante 20 — un intento registrado no se borra.

    El `DELETE` responde `42501` y la fila sigue.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        intento = insertar_intento(aplicacion, CORREO_INTENTO)
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
            aplicacion.execute("DELETE FROM intento_acceso WHERE id = %s", (intento,))
        filas = aplicacion.execute(
            "SELECT id, email FROM intento_acceso WHERE id = %s", (intento,)
        ).fetchall()

    assert error.value.sqlstate == "42501"
    assert "intento_acceso" in str(error.value)
    assert filas == [(intento, CORREO_INTENTO)]


def test_tkt003_ca06_esc04_aplicacion_no_vacia_intentos(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-37 · CA-6 esc. 4 · invariante 20 — la aplicación no vacía la tabla con `TRUNCATE`.

    Con dos intentos, el `TRUNCATE` responde `42501` y siguen dos. Es el rechazo que no depende
    de ningún `REVOKE`: ningún privilegio por omisión concede `TRUNCATE`, y lo demuestra el
    mutante que se lo concede a la aplicación.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        primero = insertar_intento(aplicacion, CORREO_INTENTO)
        segundo = insertar_intento(aplicacion, CORREO_INTENTO)
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
            aplicacion.execute("TRUNCATE intento_acceso")
        filas = aplicacion.execute("SELECT id FROM intento_acceso").fetchall()

    assert error.value.sqlstate == "42501"
    assert "intento_acceso" in str(error.value)
    assert {fila[0] for fila in filas} == {primero, segundo}


def test_tkt003_ca07_esc02_lectura_no_escribe(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-38 · CA-7 esc. 2 · invariante 21 — el rol de lectura no escribe en `rol`.

    `INSERT`, `UPDATE`, `DELETE` y `TRUNCATE` responden `42501` cada uno, y el contenido de `rol`
    es el mismo antes y después. El caso inserta antes una fila como propietario: así el
    contenido no es vacío y un `DELETE` o `TRUNCATE` que prosperara se notaría.
    """
    consulta = "SELECT id, clave, nombre FROM rol ORDER BY clave"
    with conectar("migracion", base_de_prueba) as migracion:
        insertar_rol_de_prueba(migracion)
        antes = migracion.execute(consulta).fetchall()
    with conectar("lectura", base_de_prueba) as lectura:
        resultados = {
            verbo: sqlstate_de(lectura, sentencia)
            for verbo, sentencia in (
                (
                    "INSERT",
                    "INSERT INTO rol (id, clave, nombre) VALUES (gen_random_uuid(), 'OTRO', 'Otro')",
                ),
                ("UPDATE", f"UPDATE rol SET nombre = 'x' WHERE clave = '{CLAVE_DE_PRUEBA}'"),
                ("DELETE", f"DELETE FROM rol WHERE clave = '{CLAVE_DE_PRUEBA}'"),
                ("TRUNCATE", "TRUNCATE rol"),
            )
        }
    with conectar("migracion", base_de_prueba) as migracion:
        despues = migracion.execute(consulta).fetchall()

    assert resultados == {
        "INSERT": "42501",
        "UPDATE": "42501",
        "DELETE": "42501",
        "TRUNCATE": "42501",
    }
    assert antes != []
    assert despues == antes


def test_tkt003_ca05_esc03_privilegios_exactos_en_identidad(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-42 · CA-5 esc. 3, invariantes 20 y 21, PA-T4 — los privilegios de cada tabla, y solo esos.

    Igualdad de conjuntos leída de `relacl` (por tabla) y de `attacl` (por columna): un
    `TRUNCATE`, `REFERENCES`, `TRIGGER` o `MAINTAIN` de más, o un `UPDATE` y `DELETE` sobre
    `intento_acceso`, rompen la igualdad. Aplicación: `SELECT, INSERT, UPDATE, DELETE` en
    `usuario`, `rol`, `usuario_rol` y `sesion`; `SELECT, INSERT` en `intento_acceso`; ningún
    privilegio por columna. Lectura: `SELECT` en `rol`, `usuario_rol` e `intento_acceso`; nada
    por tabla en `sesion` ni en `usuario`; y sobre `usuario` solo `SELECT` por columna en las diez
    que no son `password_hash`.

    Ajuste de la fila 8 (D-1, `PA-T4`), hecho por el tester en el rojo de esa fila: antes la
    lectura esperaba `{SELECT}` sobre las cinco tablas y ninguna columna.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        por_tabla = {
            (tabla, rol): privilegios(migracion, tabla, rol)
            for tabla in TABLAS
            for rol in ("aplicacion", "lectura")
        }
        por_columna = {
            (tabla, rol): privilegios_por_columna(migracion, tabla, rol)
            for tabla in TABLAS
            for rol in ("aplicacion", "lectura")
        }

    de_lectura_por_tabla = {
        tabla: SIN_PRIVILEGIO if tabla in ("usuario", "sesion") else SOLO_LECTURA
        for tabla in TABLAS
    }
    esperados_por_tabla = {
        (tabla, "aplicacion"): SOLO_ANEXAR if tabla == "intento_acceso" else LECTURA_Y_ESCRITURA
        for tabla in TABLAS
    } | {(tabla, "lectura"): de_lectura_por_tabla[tabla] for tabla in TABLAS}
    esperados_por_columna: dict[tuple[str, str], set[tuple[str, str]]] = {
        (tabla, rol): set() for tabla in TABLAS for rol in ("aplicacion", "lectura")
    }
    esperados_por_columna[("usuario", "lectura")] = {
        (columna, "SELECT") for columna in COLUMNAS_USUARIO_PARA_LECTURA
    }
    assert por_tabla == esperados_por_tabla
    assert por_columna == esperados_por_columna


def test_tkt003_ca07_esc01_lectura_consulta_rol(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-43 · CA-7 esc. 1 — el rol de lectura consulta `rol` y ve lo que el propietario confirmó.

    El caso confirma una fila como propietario y exige que la lectura cuente las mismas filas,
    al menos una: leer una tabla vacía sin error no probaría nada.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        insertar_rol_de_prueba(migracion)
        del_propietario = migracion.execute("SELECT count(*) FROM rol").fetchone()
    with conectar("lectura", base_de_prueba) as lectura:
        de_lectura = lectura.execute("SELECT count(*) FROM rol").fetchone()

    assert del_propietario is not None
    assert del_propietario[0] >= 1
    assert de_lectura == del_propietario
