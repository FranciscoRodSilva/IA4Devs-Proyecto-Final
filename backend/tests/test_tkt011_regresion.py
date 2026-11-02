"""Migración y regresión de TKT-011a: TC-16, TC-17, TC-18 y TC-INV-1 a TC-INV-6 sobre las doce tablas de la migración 0006.

La migración `0006` crea doce tablas del módulo `presupuesto`. Este archivo prueba lo que la
rodea: que sube, baja y vuelve a subir sin dejar rastro (`CA-18`), que cada restricción y cada
índice lleva el nombre del diseño (`CA-20`), que los privilegios de las tablas son los que dice
`CA-17` y que la migración no tocó nada de lo que ya estaba (`CA-R1` a `CA-R6`).

Regla del diseño para que TKT-011b no repita el problema: ninguna prueba de este archivo afirma la
cabeza de las migraciones por su número. Las que suben y comprueban versión suben a `"0006"`
explícito, y la que necesita la cadena la lee con `ScriptDirectory`.

PostgreSQL real, esquema por `alembic upgrade`, nunca por la creación automática del esquema. El catálogo se lee con el rol
de migración y la prueba de escritura rechazada usa el rol de lectura; nunca el propietario por otra
vía. Los nombres esperados de `TC-17` son copia literal del diseño, no se derivan de la migración.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]
Migrar = Callable[..., None]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0005"
REVISION_NUEVA = "0006"

# Las doce tablas que entrega TKT-011a, en el orden del diseño.
TABLAS: tuple[str, ...] = (
    "empresa",
    "obra",
    "tipo_partida",
    "insumo",
    "nivel",
    "area",
    "partida",
    "concepto",
    "precio_insumo",
    "apu",
    "apu_insumo",
    "apu_cargo",
)

PRIVILEGIOS_DE_APLICACION = {"SELECT", "INSERT", "UPDATE", "DELETE"}

PREFIJO_POR_TIPO = {"p": "pk_", "f": "fk_", "u": "uq_", "c": "ck_", "i": "ix_"}


# --------------------------------------------------------------------------- ayudas


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


def tablas_publicas(conexion: Conexion) -> list[str]:
    filas = conexion.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def fotografia(conexion: Conexion) -> dict[str, Any]:
    """Todo lo que `0006` deja en el catálogo sobre sus doce tablas.

    Tablas, columnas (con tipo, escala, nulabilidad y valor por omisión), restricciones con su
    definición, índices con su definición y privilegios de cada rol, incluido `PUBLIC`. Las
    restricciones `NOT NULL` (`contype = 'n'`) no entran: PostgreSQL 18 las registra con un nombre
    automático y su nulabilidad ya viene en `columnas`.
    """
    tablas = list(TABLAS)
    return {
        "tablas": [
            str(f[0])
            for f in conexion.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = ANY(%s) ORDER BY tablename",
                (tablas,),
            ).fetchall()
        ],
        "columnas": [
            tuple(f)
            for f in conexion.execute(
                "SELECT table_name, ordinal_position, column_name, data_type, numeric_precision, "
                "numeric_scale, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ANY(%s) "
                "ORDER BY table_name, ordinal_position",
                (tablas,),
            ).fetchall()
        ],
        "restricciones": [
            tuple(f)
            for f in conexion.execute(
                "SELECT t.relname, c.conname, c.contype, pg_get_constraintdef(c.oid) "
                "FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
                "AND c.contype <> 'n' ORDER BY t.relname, c.conname",
                (tablas,),
            ).fetchall()
        ],
        "indices": [
            tuple(f)
            for f in conexion.execute(
                "SELECT tablename, indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = ANY(%s) ORDER BY tablename, indexname",
                (tablas,),
            ).fetchall()
        ],
        "privilegios": [
            tuple(f)
            for f in conexion.execute(
                "SELECT c.relname, COALESCE(g.rolname, 'PUBLIC'), a.privilege_type, a.is_grantable "
                "FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
                "LEFT JOIN pg_roles g ON g.oid = a.grantee "
                "WHERE c.relnamespace = 'public'::regnamespace AND c.relname = ANY(%s) "
                "ORDER BY c.relname, 2, a.privilege_type",
                (tablas,),
            ).fetchall()
        ],
        "todas_las_tablas": tablas_publicas(conexion),
    }


def estructura_observada(conexion: Conexion) -> dict[str, dict[str, tuple[Any, ...]]]:
    """Restricciones (`p`, `f`, `u`, `c`) por nombre e índices sueltos (`i`) por (nombre, columna).

    Las doce tablas, por tabla. Un índice suelto con varias columnas aparece una vez por columna.
    """
    observada: dict[str, dict[str, list[Any]]] = {}
    restricciones = conexion.execute(
        "SELECT t.relname, c.contype, c.conname FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
        "AND c.contype <> 'n'",
        (list(TABLAS),),
    ).fetchall()
    for tabla, tipo, nombre in restricciones:
        observada.setdefault(str(tabla), {}).setdefault(str(tipo), []).append(str(nombre))
    # Un índice que respalda una clave primaria o una única lleva el nombre de esa restricción y
    # ya está contado arriba; los demás son los `i`, con la columna que indexan en `pg_index`.
    sueltos = conexion.execute(
        "SELECT t.relname, ic.relname, a.attname FROM pg_index i "
        "JOIN pg_class ic ON ic.oid = i.indexrelid JOIN pg_class t ON t.oid = i.indrelid "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM pg_constraint c "
        "WHERE c.conindid = i.indexrelid AND c.contype IN ('p', 'u'))",
        (list(TABLAS),),
    ).fetchall()
    for tabla, nombre, columna in sueltos:
        observada.setdefault(str(tabla), {}).setdefault("i", []).append((str(nombre), str(columna)))
    return {
        tabla: {tipo: tuple(sorted(valores)) for tipo, valores in por_tipo.items()}
        for tabla, por_tipo in observada.items()
    }


# --------------------------------------------------------------------------- TC-16


def test_tkt011_ca18_0006_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-16 · CA-18 — `upgrade 0006`, `downgrade 0005` y `upgrade 0006` dejan lo que deben.

    Tras subir, la fotografía del catálogo (tablas, columnas, restricciones con su definición,
    índices con su definición y privilegios) tiene las doce tablas; si no las tuviera, comparar
    dos fotografías vacías pasaría sin afirmar nada. Tras bajar a `0005` no queda ninguna de las
    doce, las demás tablas siguen, la fotografía está vacía y la versión es `0005`. Tras volver a
    subir, la fotografía es idéntica a la primera.
    """
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        primera = fotografia(administrador)
        version_subida = version_de_alembic(administrador)
    assert version_subida == [(REVISION_NUEVA,)]
    assert primera["tablas"] == sorted(TABLAS), (
        f"La precondición exige las doce tablas tras `upgrade {REVISION_NUEVA}`: {primera['tablas']}"
    )
    assert primera["columnas"] and primera["restricciones"] and primera["indices"], primera
    assert primera["privilegios"], "La fotografía debe incluir los privilegios de las tablas"

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        tras_bajar = fotografia(administrador)
        version_bajada = version_de_alembic(administrador)
    assert tras_bajar["tablas"] == []
    assert tras_bajar["columnas"] == []
    assert tras_bajar["restricciones"] == []
    assert tras_bajar["indices"] == []
    assert tras_bajar["privilegios"] == []
    assert version_bajada == [(REVISION_ANTERIOR,)]
    # La bajada borra las doce y ninguna otra: todo lo que existía antes de `0006` sigue.
    assert tras_bajar["todas_las_tablas"] == sorted(set(primera["todas_las_tablas"]) - set(TABLAS))

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        segunda = fotografia(administrador)
        version_final = version_de_alembic(administrador)
    assert version_final == [(REVISION_NUEVA,)]
    assert segunda == primera


# --------------------------------------------------------------------------- TC-17


def test_tkt011_ca20_restricciones_e_indices_con_nombre(
    base_de_prueba: str,
    conectar: Conectar,
    estructura_esperada: dict[str, dict[str, tuple[Any, ...]]],
) -> None:
    """TC-17 · CA-20 — los nombres de restricciones e índices son exactamente los del diseño.

    Compara, tabla por tabla, el conjunto exacto de `conname` por tipo (clave primaria, foránea,
    única y `CHECK`) y el de los índices que no respaldan ninguna restricción, con su columna
    indexada según `pg_index`, con la copia literal del diseño. Después, que cada nombre empieza
    por el prefijo de su tipo y que `pg_indexes` contiene exactamente los índices de las claves
    primarias, de las únicas y los `ix_`. Un nombre de más de 63 caracteres que PostgreSQL
    truncara se vería como una diferencia de conjunto.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        observada = estructura_observada(migracion)
        indices = [
            (str(tabla), str(nombre))
            for tabla, nombre in migracion.execute(
                "SELECT tablename, indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = ANY(%s)",
                (list(TABLAS),),
            ).fetchall()
        ]

    assert observada == estructura_esperada

    for tabla, por_tipo in observada.items():
        for tipo, valores in por_tipo.items():
            for valor in valores:
                nombre = valor[0] if tipo == "i" else valor
                assert nombre.startswith(PREFIJO_POR_TIPO[tipo]), (
                    f"{tabla}.{nombre} es de tipo '{tipo}' y debería empezar por "
                    f"'{PREFIJO_POR_TIPO[tipo]}'"
                )

    indices_esperados = sorted(
        [
            (tabla, nombre)
            for tabla, por_tipo in estructura_esperada.items()
            for tipo in ("p", "u")
            for nombre in por_tipo.get(tipo, ())
        ]
        + [
            (tabla, nombre)
            for tabla, por_tipo in estructura_esperada.items()
            for nombre, _columna in por_tipo.get("i", ())
        ]
    )
    assert sorted(indices) == indices_esperados


# --------------------------------------------------------------------------- TC-18


def test_tkt011_ca17_privilegios_de_las_tablas_de_estructura(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-18 · CA-17 esc. 3 y 4 en su parte — la aplicación escribe, la lectura solo lee.

    Por `aclexplode(relacl)`, en cada una de las doce tablas la aplicación tiene exactamente
    `SELECT, INSERT, UPDATE, DELETE` y la lectura exactamente `SELECT`; la aplicación no tiene
    `TRUNCATE` según `has_table_privilege`, con `SELECT` como precondición para que el `false`
    no sea el de una tabla sin ningún privilegio. Un `INSERT` real en `empresa` con el rol de
    lectura responde `42501` y la tabla no gana filas (la migración `0008` ya sembró la suya).
    """
    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = {t: privilegios(migracion, t, "aplicacion") for t in TABLAS}
        de_lectura = {t: privilegios(migracion, t, "lectura") for t in TABLAS}
        tiene_select = {
            t: migracion.execute(
                "SELECT has_table_privilege('cimenta_aplicacion', %s, 'SELECT')", (t,)
            ).fetchone()
            for t in TABLAS
        }
        tiene_truncate = {
            t: migracion.execute(
                "SELECT has_table_privilege('cimenta_aplicacion', %s, 'TRUNCATE')", (t,)
            ).fetchone()
            for t in TABLAS
        }

    assert de_aplicacion == {t: PRIVILEGIOS_DE_APLICACION for t in TABLAS}
    assert de_lectura == {t: {"SELECT"} for t in TABLAS}
    assert tiene_select == {t: (True,) for t in TABLAS}
    assert tiene_truncate == {t: (False,) for t in TABLAS}

    with conectar("migracion", base_de_prueba) as migracion:
        antes = migracion.execute("SELECT count(*) FROM empresa").fetchone()

    with (
        conectar("lectura", base_de_prueba) as lectura,
        pytest.raises(psycopg.errors.InsufficientPrivilege) as rechazo,
    ):
        lectura.execute(
            "INSERT INTO empresa (id, nombre, rfc, activa) VALUES (%s, 'Tablaroca SA', "
            "'TSA010101AB1', true)",
            (uuid.uuid4(),),
        )
    assert rechazo.value.sqlstate == "42501"
    assert "empresa" in (rechazo.value.diag.message_primary or "")

    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute("SELECT count(*) FROM empresa").fetchone()
    assert filas == antes


# --------------------------------------------------------------------------- TC-INV-1 a TC-INV-6


def test_tkt011_car1_bitacora_sigue_permanente(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-INV-1 · CA-R1 · invariante 10 — la bitácora sigue siendo permanente.

    El rol de aplicación tiene exactamente `INSERT` y `SELECT` sobre `bitacora` y
    `bitacora.usuario_id` sigue siendo `NOT NULL`.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = privilegios(migracion, "bitacora", "aplicacion")
        usuario_id = migracion.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'bitacora' "
            "AND column_name = 'usuario_id'"
        ).fetchone()

    assert de_aplicacion == {"INSERT", "SELECT"}
    assert usuario_id == ("NO",)


def test_tkt011_car2_intento_acceso_solo_se_anexa(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-INV-2 · CA-R2 · invariante 20 — `intento_acceso` sigue solo anexándose.

    El rol de aplicación tiene exactamente `SELECT` e `INSERT`, sin `UPDATE` ni `DELETE`.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = privilegios(migracion, "intento_acceso", "aplicacion")

    assert de_aplicacion == {"SELECT", "INSERT"}


def test_tkt011_car3_lectura_sin_secretos_ni_escritura(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-3 · CA-R3 · invariante 21 — lo que ve el rol de lectura no cambia.

    `SELECT * FROM sesion` y `SELECT password_hash FROM usuario` con el rol de lectura responden
    `42501`. Ninguna tabla del módulo concede a la lectura algo distinto de `SELECT`, ni a nivel de
    tabla ni de columna, y tampoco ninguna otra tabla de `public`; las doce sí le conceden `SELECT`,
    para que el «nada de más» no sea el de una tabla sin privilegios.
    """
    with conectar("lectura", base_de_prueba) as lectura:
        rechazos = {
            "sesion": sqlstate_de(lectura, "SELECT * FROM sesion"),
            "password_hash": sqlstate_de(lectura, "SELECT password_hash FROM usuario"),
        }

    with conectar("migracion", base_de_prueba) as migracion:
        del_modulo = {t: privilegios(migracion, t, "lectura") for t in TABLAS}
        de_tabla = migracion.execute(
            "SELECT c.relname, a.privilege_type FROM pg_class c "
            "CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') "
            "AND g.rolname = 'cimenta_lectura' AND a.privilege_type <> 'SELECT'"
        ).fetchall()
        de_columna = migracion.execute(
            "SELECT t.relname, a.attname, x.privilege_type FROM pg_attribute a "
            "JOIN pg_class t ON t.oid = a.attrelid "
            "CROSS JOIN LATERAL aclexplode(a.attacl) x "
            "JOIN pg_roles g ON g.oid = x.grantee "
            "WHERE t.relnamespace = 'public'::regnamespace AND g.rolname = 'cimenta_lectura' "
            "AND x.privilege_type <> 'SELECT'"
        ).fetchall()

    assert rechazos == {"sesion": "42501", "password_hash": "42501"}
    assert del_modulo == {t: {"SELECT"} for t in TABLAS}
    assert de_tabla == []
    assert de_columna == []


def test_tkt011_car4_una_sola_cabeza_y_0006_cuelga_de_0005() -> None:
    """TC-INV-4 · CA-R4 — la cadena de migraciones tiene una sola cabeza y `0006` cuelga de `0005`.

    No afirma qué revisión es la cabeza: con TKT-011b la cabeza será `0007` y esta prueba debe
    seguir en verde. No usa base de datos.
    """
    guion = ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))
    cabezas = guion.get_heads()
    revision = guion.get_revision(REVISION_NUEVA)

    assert len(cabezas) == 1, cabezas
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR


def test_tkt011_car5_claves_foraneas_externas_solo_a_usuario(
    base_de_prueba: str,
    conectar: Conectar,
    estructura_esperada: dict[str, dict[str, tuple[Any, ...]]],
) -> None:
    """TC-INV-5 · CA-R5 · regla 3 de CLAUDE.md — ninguna clave foránea cruza un módulo salvo a `usuario`.

    Toda clave foránea de las doce tablas apunta a una de ellas o a `usuario`. La precondición
    exige las quince claves del diseño y que alguna apunte fuera del módulo, para que el recorrido
    no sea el de una lista vacía.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT t.relname, c.conname, p.relname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid JOIN pg_class p ON p.oid = c.confrelid "
            "WHERE c.contype = 'f' AND t.relnamespace = 'public'::regnamespace "
            "AND t.relname = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()

    numero_de_claves = sum(len(por_tipo.get("f", ())) for por_tipo in estructura_esperada.values())
    assert len(filas) == numero_de_claves
    externas = {(str(h), str(n), str(p)) for h, n, p in filas if str(p) not in TABLAS}
    assert externas, "Alguna clave foránea debe apuntar a `usuario`"
    assert {p for _, _, p in externas} == {"usuario"}, externas


def test_tkt011_car6_ningun_flotante(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-INV-6 · CA-R6 · regla 1 de CLAUDE.md — ninguna columna de las doce tablas es de punto flotante.

    Ni `real` ni `double precision`, vistos por `data_type` y por el tipo base (`float4`, `float8`).
    La precondición exige que el recorrido vea las columnas de las doce tablas y que haya columnas
    `numeric`, que son las del dinero.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = migracion.execute(
            "SELECT table_name, column_name, data_type, udt_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()

    assert {str(f[0]) for f in columnas} == set(TABLAS)
    assert any(f[2] == "numeric" for f in columnas)
    flotantes = [
        (f[0], f[1], f[2])
        for f in columnas
        if f[2] in ("real", "double precision") or f[3] in ("float4", "float8")
    ]
    assert flotantes == []
