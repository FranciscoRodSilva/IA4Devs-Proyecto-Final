"""Esquema de TKT-057 (fila 2): TC-10, TC-11, TC-12, TC-13, TC-INV-1 y TC-INV-2.

La migración `v0005` añade `intento_acceso.credenciales_verificadas boolean NOT NULL` (sin
`DEFAULT`), la restricción `ck_intento_acceso_exito_verificado` (un éxito siempre verificó
credenciales) y tres índices **parciales** que sirven a las tres lecturas del límite: fallos
verificados por `(email, ocurrido_en)`, fallos verificados por `(origen_ip, ocurrido_en)` y éxitos
por `(email, ocurrido_en)`. Los índices completos de la primera versión ya no existen: los
rechazos por bloqueo inflaban su rango (auditoría F001). Sin esa columna el límite de intentos no puede distinguir un fallo de contraseña de un rechazo por
bloqueo (`PA-T11`).

PostgreSQL real, esquema por `alembic upgrade head` y rol de aplicación: las fixtures de
`conftest.py`. Los `INSERT` de este archivo declaran la columna nueva, porque ya no tiene
`DEFAULT`. Un rechazo comprueba el SQLSTATE y el nombre de la restricción, y después que la
tabla no cambió.
"""

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]
Migrar = Callable[..., None]

COLUMNA = "credenciales_verificadas"
RESTRICCION = "ck_intento_acceso_exito_verificado"
INDICE_CORREO = "ix_intento_acceso_email_fallo_verificado"
INDICE_ORIGEN = "ix_intento_acceso_origen_ip_fallo_verificado"
INDICE_EXITO = "ix_intento_acceso_email_exito"
# Los dos índices completos que la primera versión de `v0005` creaba: los rechazos por bloqueo
# (`exitoso = false`, `credenciales_verificadas = false`) inflaban su rango y cada lectura del
# límite recorría todo el historial adversario (auditoría, F001). Ya no deben existir.
INDICES_COMPLETOS_RETIRADOS = (
    "ix_intento_acceso_email_ocurrido_en",
    "ix_intento_acceso_origen_ip_ocurrido_en",
)
REVISION_ANTERIOR = "0004"
REVISION_NUEVA = "0005"

CORREO_ANA = "ana@cimenta.test"
ORIGEN = "203.0.113.7"

INSERTAR_INTENTO = (
    "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, credenciales_verificadas, origen_ip) "
    "VALUES (%s, %s, NULL, %s, %s, %s)"
)

# Lo que `v0005` deja, leído del catálogo. La definición de la restricción y de cada índice es
# la que PostgreSQL devuelve de `pg_get_constraintdef` y de `pg_indexes.indexdef`.
ESTADO_SUBIDO: dict[str, Any] = {
    "columna": ("boolean", "NO", None),
    "restriccion": [(RESTRICCION, "CHECK ((credenciales_verificadas OR (NOT exitoso)))")],
    "indices": {
        INDICE_CORREO: (
            "CREATE INDEX ix_intento_acceso_email_fallo_verificado "
            "ON public.intento_acceso USING btree (email, ocurrido_en) "
            "WHERE ((exitoso IS FALSE) AND (credenciales_verificadas IS TRUE))"
        ),
        INDICE_ORIGEN: (
            "CREATE INDEX ix_intento_acceso_origen_ip_fallo_verificado "
            "ON public.intento_acceso USING btree (origen_ip, ocurrido_en) "
            "WHERE ((exitoso IS FALSE) AND (credenciales_verificadas IS TRUE))"
        ),
        INDICE_EXITO: (
            "CREATE INDEX ix_intento_acceso_email_exito "
            "ON public.intento_acceso USING btree (email, ocurrido_en) "
            "WHERE (exitoso IS TRUE)"
        ),
    },
}
ESTADO_BAJADO: dict[str, Any] = {"columna": None, "restriccion": [], "indices": {}}


# --------------------------------------------------------------------------- ayudas


def insertar_intento(
    conexion: Conexion,
    *,
    exitoso: bool,
    verificadas: bool,
    correo: str = CORREO_ANA,
    origen: str | None = ORIGEN,
) -> uuid.UUID:
    """INSERT directo en `intento_acceso` declarando la columna nueva; devuelve el `id`."""
    identificador = uuid.uuid4()
    conexion.execute(INSERTAR_INTENTO, (identificador, correo, exitoso, verificadas, origen))
    return identificador


def contar_intentos(conexion: Conexion) -> int:
    fila = conexion.execute("SELECT count(*) FROM intento_acceso").fetchone()
    assert fila is not None
    return int(fila[0])


def estado_de_v0005(conexion: Conexion) -> dict[str, Any]:
    """La columna, la restricción y los dos índices de `v0005`, tal como están en el catálogo."""
    columna = conexion.execute(
        "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'intento_acceso' AND column_name = %s",
        (COLUMNA,),
    ).fetchone()
    restriccion = conexion.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass('intento_acceso') AND contype = 'c' AND conname = %s",
        (RESTRICCION,),
    ).fetchall()
    indices = conexion.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' AND tablename = 'intento_acceso' AND indexname = ANY(%s)",
        ([INDICE_CORREO, INDICE_ORIGEN, INDICE_EXITO, *INDICES_COMPLETOS_RETIRADOS],),
    ).fetchall()
    return {
        "columna": None if columna is None else tuple(columna),
        "restriccion": [(str(nombre), str(definicion)) for nombre, definicion in restriccion],
        "indices": {str(nombre): str(definicion) for nombre, definicion in indices},
    }


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


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


def sqlstate_de(conexion: Conexion, sentencia: str) -> str | None:
    """SQLSTATE con que PostgreSQL rechaza la sentencia; `None` si la acepta."""
    try:
        conexion.execute(sentencia)
    except psycopg.Error as error:
        return error.sqlstate
    return None


# --------------------------------------------------------------------------- TC-10 y TC-11


def test_tkt057_ca08_un_exito_sin_credenciales_verificadas_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-10 · CA-8 — `exitoso = true` con `credenciales_verificadas = false` viola la restricción.

    Un éxito siempre verificó credenciales. El rechazo es `23514` con el nombre de
    `ck_intento_acceso_exito_verificado` y la tabla no gana ninguna fila. Después, las otras tres
    combinaciones sí pasan: un fallo de credenciales (falso, verdadero), un rechazo por bloqueo
    o por CSRF (falso, falso) y un éxito verificado (verdadero, verdadero); así la restricción
    no es más ancha de lo que dice.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
            insertar_intento(aplicacion, exitoso=True, verificadas=False)

        assert rechazo.value.sqlstate == "23514"
        assert rechazo.value.diag.constraint_name == RESTRICCION
        assert rechazo.value.diag.table_name == "intento_acceso"
        assert contar_intentos(aplicacion) == 0

        insertar_intento(aplicacion, exitoso=False, verificadas=True)
        insertar_intento(aplicacion, exitoso=False, verificadas=False)
        insertar_intento(aplicacion, exitoso=True, verificadas=True)
        guardadas = aplicacion.execute(
            f"SELECT exitoso, {COLUMNA} FROM intento_acceso ORDER BY exitoso, {COLUMNA}"
        ).fetchall()

    assert guardadas == [(False, False), (False, True), (True, True)]


def test_tkt057_ca08_un_intento_sin_la_columna_lo_rechaza_not_null_y_no_queda_default(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-11 · CA-8 — insertar sin `credenciales_verificadas` viola `NOT NULL`; no queda `DEFAULT`.

    La migración añade la columna con `DEFAULT true` para no reescribir la tabla y se lo quita en
    la misma migración: toda inserción posterior debe declararla. El rechazo es `23502` sobre
    esa columna, la tabla no gana ninguna fila y el catálogo no guarda ningún valor por omisión.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.NotNullViolation) as rechazo:
            aplicacion.execute(
                "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, origen_ip) "
                "VALUES (%s, %s, NULL, false, %s)",
                (uuid.uuid4(), CORREO_ANA, ORIGEN),
            )

        assert rechazo.value.sqlstate == "23502"
        assert rechazo.value.diag.column_name == COLUMNA
        assert rechazo.value.diag.table_name == "intento_acceso"
        assert contar_intentos(aplicacion) == 0

    with conectar("migracion", base_de_prueba) as migracion:
        columna = migracion.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'intento_acceso' AND column_name = %s",
            (COLUMNA,),
        ).fetchone()
    assert columna == ("NO", None)


# --------------------------------------------------------------------------- TC-12


def test_tkt057_ca08_las_filas_de_la_version_anterior_quedan_verificadas(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-12 · CA-8 — las filas escritas con `0004` valen `true` tras subir a `0005`.

    Antes de esta migración no existía el rechazo por bloqueo: toda fila de `intento_acceso`
    nació de verificar unas credenciales, con éxito o sin él. El caso sube a `0004`, inserta un
    éxito y un fallo sin la columna (que aún no existe), sube a `head` y exige `true` en las dos,
    con los mismos `id`, correo y resultado, y la versión de Alembic en `0005`.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_ANTERIOR,)]

    exito = uuid.uuid4()
    fallo = uuid.uuid4()
    with conectar("aplicacion", base_vacia) as aplicacion:
        for identificador, exitoso in ((exito, True), (fallo, False)):
            aplicacion.execute(
                "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, origen_ip) "
                "VALUES (%s, %s, NULL, %s, %s)",
                (identificador, CORREO_ANA, exitoso, ORIGEN),
            )

    migrar(base_vacia)
    with conectar("aplicacion", base_vacia) as aplicacion:
        filas = aplicacion.execute(
            f"SELECT id, email, exitoso, {COLUMNA} FROM intento_acceso ORDER BY exitoso"
        ).fetchall()
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)

    assert filas == [(fallo, CORREO_ANA, False, True), (exito, CORREO_ANA, True, True)]
    assert version == [(REVISION_NUEVA,)]


# --------------------------------------------------------------------------- TC-13


def test_tkt057_ca08_la_migracion_se_revierte_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-13 · CA-8 — `upgrade head`, `downgrade 0004` y `upgrade head` dejan lo que deben.

    Tras subir: la columna es `boolean NOT NULL` sin `DEFAULT`, la restricción tiene la
    definición `CHECK (credenciales_verificadas OR NOT exitoso)` y existen los tres índices
    parciales (fallos verificados por correo, fallos verificados por origen y éxitos por correo)
    con su predicado literal; los dos índices completos de la primera versión ya no existen. Tras
    bajar a `0004` no queda ninguno de los cinco objetos, la tabla sigue y la versión es `0004`.
    Tras volver a subir, el catálogo es idéntico al de la primera vez.
    """
    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        tras_subir = estado_de_v0005(administrador)
    assert tras_subir == ESTADO_SUBIDO, (
        f"Tras `upgrade head` debe existir lo de v0005 (TKT-057): {tras_subir}"
    )

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        tras_bajar = estado_de_v0005(administrador)
        version = version_de_alembic(administrador)
        tabla_sigue = administrador.execute(
            "SELECT to_regclass('intento_acceso') IS NOT NULL"
        ).fetchone()
    assert tras_bajar == ESTADO_BAJADO
    assert version == [(REVISION_ANTERIOR,)]
    assert tabla_sigue == (True,)

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        tras_resubir = estado_de_v0005(administrador)
        version_final = version_de_alembic(administrador)
    assert tras_resubir == tras_subir
    assert version_final == [(REVISION_NUEVA,)]


# --------------------------------------------------------------------------- TC-INV-1


def test_tkt057_car1_aplicacion_solo_anexa_intentos_tambien_la_columna_nueva(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-1 · CA-R1, CA-8 esc. 2 · invariante 20 — `intento_acceso` solo se anexa.

    El rol de aplicación tiene exactamente `INSERT` y `SELECT` sobre la tabla (leído de
    `relacl`) y ningún privilegio por columna. Con una fila real, un `UPDATE` y un `DELETE`
    responden `42501`, también el `UPDATE` de la columna nueva, y la fila queda como estaba: el
    recuento y el bloqueo nunca se hacen editando ni borrando filas.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        intento = insertar_intento(aplicacion, exitoso=False, verificadas=True)
        antes = aplicacion.execute(
            "SELECT id, email, exitoso, credenciales_verificadas FROM intento_acceso"
        ).fetchall()
        resultados = {
            "UPDATE exitoso": sqlstate_de(
                aplicacion, f"UPDATE intento_acceso SET exitoso = true WHERE id = '{intento}'"
            ),
            "UPDATE columna nueva": sqlstate_de(
                aplicacion,
                f"UPDATE intento_acceso SET {COLUMNA} = false WHERE id = '{intento}'",
            ),
            "DELETE": sqlstate_de(aplicacion, f"DELETE FROM intento_acceso WHERE id = '{intento}'"),
        }
        despues = aplicacion.execute(
            "SELECT id, email, exitoso, credenciales_verificadas FROM intento_acceso"
        ).fetchall()

    with conectar("migracion", base_de_prueba) as migracion:
        de_tabla = privilegios(migracion, "intento_acceso", "aplicacion")
        por_columna = migracion.execute(
            "SELECT a.attname FROM pg_attribute a "
            "CROSS JOIN LATERAL aclexplode(a.attacl) x "
            "JOIN pg_roles g ON g.oid = x.grantee "
            "WHERE a.attrelid = to_regclass('intento_acceso') AND a.attnum > 0 "
            "AND NOT a.attisdropped AND g.rolname = 'cimenta_aplicacion'"
        ).fetchall()

    assert antes == [(intento, CORREO_ANA, False, True)]
    assert resultados == {
        "UPDATE exitoso": "42501",
        "UPDATE columna nueva": "42501",
        "DELETE": "42501",
    }
    assert despues == antes
    assert de_tabla == {"SELECT", "INSERT"}
    assert por_columna == []


# --------------------------------------------------------------------------- TC-INV-2


def test_tkt057_car3_lectura_no_ve_sesion_ni_password_hash_y_si_bloqueado_hasta(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-2 · CA-R3 · invariante 21 — lo que ve el rol de solo lectura no cambia.

    Con un usuario real bloqueado, el rol de lectura lee `usuario.bloqueado_hasta` y recibe el
    mismo instante que el propietario; `SELECT` sobre `sesion` y sobre `usuario.password_hash`
    responden `42501`. La migración `v0005` no concede ni revoca nada a este rol.
    """
    usuario = uuid.uuid4()
    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(
            "INSERT INTO usuario (id, nombre, email, password_hash, bloqueado_hasta) "
            "VALUES (%s, 'Ana Torres', %s, 'hash-de-prueba', "
            "timestamptz '2026-10-30 12:00:00+00')",
            (usuario, CORREO_ANA),
        )
        del_propietario = migracion.execute(
            "SELECT bloqueado_hasta FROM usuario WHERE id = %s", (usuario,)
        ).fetchone()
        tablas_de_lectura = privilegios(migracion, "sesion", "lectura")

    with conectar("lectura", base_de_prueba) as lectura:
        de_lectura = lectura.execute(
            "SELECT bloqueado_hasta FROM usuario WHERE id = %s", (usuario,)
        ).fetchone()
        rechazos = {
            "sesion": sqlstate_de(lectura, "SELECT * FROM sesion"),
            "password_hash": sqlstate_de(lectura, "SELECT password_hash FROM usuario"),
        }

    assert del_propietario is not None
    assert del_propietario[0] is not None
    assert de_lectura == del_propietario
    assert rechazos == {"sesion": "42501", "password_hash": "42501"}
    assert tablas_de_lectura == set()
