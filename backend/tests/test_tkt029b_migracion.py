"""TKT-029b · Migración `0016` y el verbo `DAR_BAJA` (fila F1): TC-01 a TC-07.

`0016` añade `DAR_BAJA` al final del tipo `accion_bitacora` con `ALTER TYPE … ADD VALUE`. Su bajada
se niega con `RAISE EXCEPTION` si la bitácora tiene asientos `DAR_BAJA` (`RN-04`: la bitácora es
permanente) y, si no los tiene, recrea el tipo con los 22 verbos de `0003` sin cambiar ningún valor
de la columna `bitacora.accion` (`D-3`).

Este archivo prueba la migración como pieza de la cadena, sin pasar por ningún caso de uso: que sigue
habiendo una sola cabeza y `0016` cuelga de `0015` (`TC-01`, `CA-R1`), que el tipo queda con los 22
verbos de `0003` más `DAR_BAJA` al final y el rol de aplicación puede asentarlo sin ganar permisos
(`TC-02`, `CA-R1`, `CA-14`), cómo se comporta `ADD VALUE` dentro de una transacción en el motor de
las pruebas (`TC-03`, sonda del supuesto 5), que la bajada deja la bitácora como estaba (`TC-04`),
que se niega con asientos `DAR_BAJA` y no destruye nada (`TC-05`), que subir, bajar y volver a subir
es idempotente (`TC-06`) y que la bajada conserva los privilegios del rol de aplicación (`TC-07`).

Alembic y la sonda `TC-03` corren con el rol de migración; los asientos y las comprobaciones de
permisos, con el rol de aplicación. Los esquemas se construyen con `alembic upgrade`, nunca con
la creación automática de tablas del ORM. La fotografía del catálogo y las ayudas siguen el patrón de `test_tkt019_migracion.py`
y `test_tkt029a_migracion.py`.

`TC-08` (las cinco afirmaciones de TKT-007 que cuentan los verbos pasan de 22 a 23, `D-7`) no vive
aquí: es el cambio de esos cinco literales en `test_tkt007_dominio.py`, `test_tkt007_esquema.py` y
`test_tkt007_fronteras.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]
Fotografia = dict[str, list[tuple[Any, ...]]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0015"
REVISION_NUEVA = "0016"

OCURRIDO_EN = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)

# Los 22 verbos de `0003`, en su orden. `0016` añade `DAR_BAJA` después del último.
VERBOS_0003: list[str] = [
    "CREAR",
    "ACTUALIZAR",
    "EVALUAR",
    "BLOQUEAR",
    "AUTORIZAR",
    "RECHAZAR",
    "CANCELAR",
    "EMITIR",
    "AJUSTAR",
    "REPROGRAMAR",
    "CONGELAR",
    "RECAPTURAR",
    "DESCARTAR",
    "CONFIRMAR",
    "ANULAR",
    "SUSPENDER",
    "REACTIVAR",
    "CERRAR",
    "DESACTIVAR",
    "LIBERAR",
    "VALIDAR",
    "DENEGAR",
]
VERBOS_0016: list[str] = [*VERBOS_0003, "DAR_BAJA"]

# --------------------------------------------------------------------------- ayudas


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def guion_de_alembic() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))


def exigir_revision(revision: str) -> None:
    """La cadena de Alembic debe conocer `revision` antes de intentar migrar hasta ella.

    `get_revision` lanza `ResolutionError` si no existe; recorrer la cadena da un fallo de
    aserción con el motivo escrito, que es la razón esperada del rojo.
    """
    conocidas = {revision_.revision for revision_ in guion_de_alembic().walk_revisions()}
    assert revision in conocidas, (
        f"Falta la migración {revision} (v0016_auditoria_verbo_dar_baja.py): Alembic no la conoce "
        f"(TKT-029b, fila F1). Revisiones conocidas: {sorted(conocidas)}"
    )


def verbos_de_la_base(conexion: Conexion) -> list[str]:
    """Las etiquetas de `accion_bitacora` en el orden del tipo (`enumsortorder`)."""
    filas = conexion.execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('accion_bitacora') "
        "ORDER BY enumsortorder"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def fotografia(conexion: Conexion) -> Fotografia:
    """Todo lo que hay en el esquema `public`, para comparar antes y después de una migración.

    Tablas, columnas (con `ordinal_position`, tipo, longitud, precisión, escala, nulabilidad y valor
    por omisión), restricciones con su definición, índices con su definición, privilegios de cada
    rol incluido `PUBLIC`, disparadores y funciones. Las restricciones `NOT NULL` (`contype = 'n'`)
    no entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad ya viene en
    `columnas`. Copia de `fotografia` de `test_tkt019_migracion.py`, sin cambios.
    """

    def filas(consulta: str) -> list[tuple[Any, ...]]:
        return [tuple(f) for f in conexion.execute(consulta).fetchall()]

    return {
        "tablas": filas("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"),
        "columnas": filas(
            "SELECT table_name, ordinal_position, column_name, data_type, "
            "character_maximum_length, numeric_precision, numeric_scale, is_nullable, "
            "column_default FROM information_schema.columns WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        ),
        "restricciones": filas(
            "SELECT t.relname, c.conname, c.contype, pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND c.contype <> 'n' "
            "ORDER BY t.relname, c.conname"
        ),
        "indices": filas(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname"
        ),
        "privilegios": filas(
            "SELECT c.relname, COALESCE(g.rolname, 'PUBLIC'), a.privilege_type, a.is_grantable "
            "FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "LEFT JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE c.relnamespace = 'public'::regnamespace "
            "ORDER BY c.relname, 2, a.privilege_type"
        ),
        "disparadores": filas(
            "SELECT t.tgname, c.relname, t.tgtype, p.proname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace "
            "ORDER BY t.tgname"
        ),
        "funciones": filas(
            "SELECT proname, prosrc FROM pg_proc WHERE pronamespace = 'public'::regnamespace "
            "ORDER BY proname, prosrc"
        ),
    }


def fotografia_de_bitacora(conexion: Conexion) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    """Columnas (con su tipo), restricciones, índices, `relacl` y etiquetas del enum de `bitacora`."""
    consultas = (
        "SELECT column_name, udt_name, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = 'bitacora' ORDER BY ordinal_position",
        "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass('bitacora') ORDER BY conname",
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' AND tablename = 'bitacora' ORDER BY indexname",
        "SELECT relacl::text FROM pg_class WHERE oid = to_regclass('bitacora')",
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('accion_bitacora') "
        "ORDER BY enumsortorder",
    )
    return tuple(tuple(conexion.execute(consulta).fetchall()) for consulta in consultas)


def filas_de_bitacora(conexion: Conexion) -> list[str]:
    """Cada asiento como texto, ordenado por `id`: lo que no debe cambiar al migrar."""
    return [
        str(fila[0])
        for fila in conexion.execute("SELECT b::text FROM bitacora b ORDER BY b.id").fetchall()
    ]


def sembrar_usuario(conexion: Conexion) -> uuid.UUID:
    """Un usuario confirmado, para que `bitacora.usuario_id` apunte a alguien real."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", f"{identificador}@cimenta.test", "hash-de-prueba"),
    )
    return identificador


def insertar_asiento(conexion: Conexion, usuario_id: uuid.UUID, accion: str) -> uuid.UUID:
    """`INSERT` directo sobre `bitacora`, con el rol que reciba; devuelve el `id`."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO bitacora (id, entidad_tipo, entidad_id, accion, usuario_id, ocurrido_en, "
        "motivo) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            identificador,
            "proveedor",
            uuid.uuid4(),
            accion,
            usuario_id,
            OCURRIDO_EN,
            f"Asiento de prueba {accion}",
        ),
    )
    return identificador


def privilegio_de_tabla(conexion: Conexion, privilegio: str) -> bool:
    fila = conexion.execute(
        "SELECT has_table_privilege('cimenta_aplicacion', 'bitacora', %s)", (privilegio,)
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def uso_del_tipo(conexion: Conexion) -> bool:
    fila = conexion.execute(
        "SELECT has_type_privilege('cimenta_aplicacion', 'accion_bitacora', 'USAGE')"
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


# --------------------------------------------------------------------------- TC-01


def test_tkt029b_car1_0016_cuelga_de_0015_y_la_cabeza_es_unica() -> None:
    """TC-01 · CA-R1 — la cadena de migraciones tiene una sola cabeza y `0016` cuelga de `0015`.

    No afirma qué revisión es la cabeza: el siguiente ticket que migre debe poder hacerlo sin tocar
    esta prueba. No usa base de datos. Mismo patrón que `test_tkt019_car1_0014_cuelga_de_0013_…`.
    """
    guion = guion_de_alembic()
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas

    exigir_revision(REVISION_NUEVA)
    revision = guion.get_revision(REVISION_NUEVA)
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR


# --------------------------------------------------------------------------- TC-02


def test_tkt029b_car1_ca14_el_tipo_gana_dar_baja_al_final_y_el_rol_de_aplicacion_lo_asienta(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-02 · CA-R1, CA-14 · invariante 10 — tras `upgrade head`, `DAR_BAJA` es el verbo 23 y se asienta.

    `pg_enum` de `accion_bitacora` es la lista de `0003` más `DAR_BAJA` al final. Con el rol de
    aplicación, en una transacción nueva (la plantilla ya está confirmada, sin el límite de `ADD
    VALUE` de `TC-03`), un `INSERT` con `accion = 'DAR_BAJA'` se acepta. El rol sigue sin `UPDATE`,
    `DELETE` ni `TRUNCATE` sobre `bitacora` (por `has_table_privilege` y con un `UPDATE` y un
    `DELETE` reales, que responden `42501`) y conserva `USAGE` sobre el tipo.
    """
    exigir_revision(REVISION_NUEVA)
    with conectar("migracion", base_de_prueba) as administrador:
        assert verbos_de_la_base(administrador) == [*VERBOS_0016, "ELIMINAR"]
        assert privilegio_de_tabla(administrador, "UPDATE") is False
        assert privilegio_de_tabla(administrador, "DELETE") is False
        assert privilegio_de_tabla(administrador, "TRUNCATE") is False
        assert privilegio_de_tabla(administrador, "INSERT") is True
        assert privilegio_de_tabla(administrador, "SELECT") is True
        assert uso_del_tipo(administrador) is True

    aplicacion = conectar("aplicacion", base_de_prueba)
    usuario = sembrar_usuario(aplicacion)
    asiento = insertar_asiento(aplicacion, usuario, "DAR_BAJA")

    with conectar("aplicacion", base_de_prueba) as otra:
        fila = otra.execute(
            "SELECT accion::text, usuario_id FROM bitacora WHERE id = %s", (asiento,)
        ).fetchone()
        assert fila == ("DAR_BAJA", usuario)
        with pytest.raises(psycopg.Error) as actualizar:
            otra.execute("UPDATE bitacora SET motivo = 'cambiado' WHERE id = %s", (asiento,))
        assert actualizar.value.sqlstate == "42501", str(actualizar.value)
        with pytest.raises(psycopg.Error) as borrar:
            otra.execute("DELETE FROM bitacora WHERE id = %s", (asiento,))
        assert borrar.value.sqlstate == "42501", str(borrar.value)
        assert otra.execute("SELECT count(*) FROM bitacora").fetchone() == (1,)


# --------------------------------------------------------------------------- TC-03


def _etiquetas_de_la_sonda(conexion: Conexion) -> list[str]:
    filas = conexion.execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('sonda_tkt029b') "
        "ORDER BY enumsortorder"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def test_tkt029b_car1_sonda_add_value_no_se_usa_en_su_transaccion_y_queda_al_final(
    base_vacia: str, conectar: Conectar
) -> None:
    """TC-03 · CA-R1 · supuesto 5 — sonda del motor: `ALTER TYPE … ADD VALUE` y su límite transaccional.

    **Nace en verde por diseño**: prueba el motor, no el código. Con el rol de migración sobre un
    tipo desechable `sonda_tkt029b AS ENUM ('A')` creado y confirmado antes:

    (a) en una transacción, `ADD VALUE 'B'` seguido de `SELECT 'B'::sonda_tkt029b` falla con
        `sqlstate == "55P04"` (`UnsafeNewEnumValueUsage`); tras `ROLLBACK`, `'B'` no existe;
    (b) `ADD VALUE 'B'` confirmado y usado en otra transacción funciona, y `'B'` queda último en
        `enumsortorder`;
    (c) el tipo se borra al final, pase lo que pase.

    Es la evidencia de que la migración `0016` no puede usar `DAR_BAJA` en la misma transacción
    que lo añade, y de que sin `BEFORE` ni `AFTER` el verbo nuevo queda al final.
    """
    with conectar("migracion", base_vacia) as administrador:
        administrador.execute("CREATE TYPE sonda_tkt029b AS ENUM ('A')")
    try:
        # (a) ADD VALUE y uso en la misma transacción.
        with conectar("migracion", base_vacia, autocommit=False) as transaccion:
            transaccion.execute("ALTER TYPE sonda_tkt029b ADD VALUE 'B'")
            with pytest.raises(psycopg.Error) as uso_inseguro:
                transaccion.execute("SELECT 'B'::sonda_tkt029b")
            assert uso_inseguro.value.sqlstate == "55P04", str(uso_inseguro.value)
            transaccion.rollback()
        with conectar("migracion", base_vacia) as lector:
            assert _etiquetas_de_la_sonda(lector) == ["A"], "Tras ROLLBACK, 'B' no debía existir"

        # (b) ADD VALUE confirmado y usado en otra transacción.
        with conectar("migracion", base_vacia, autocommit=False) as transaccion:
            transaccion.execute("ALTER TYPE sonda_tkt029b ADD VALUE 'B'")
            transaccion.commit()
        with conectar("migracion", base_vacia, autocommit=False) as transaccion:
            usado = transaccion.execute("SELECT 'B'::sonda_tkt029b::text").fetchone()
            transaccion.rollback()
        assert usado == ("B",)
        with conectar("migracion", base_vacia) as lector:
            assert _etiquetas_de_la_sonda(lector) == ["A", "B"], "'B' debía quedar último"
    finally:
        # (c) La sonda no deja nada, ni siquiera si una afirmación de arriba falla.
        with conectar("migracion", base_vacia) as limpieza:
            limpieza.execute("DROP TYPE IF EXISTS sonda_tkt029b")


# --------------------------------------------------------------------------- TC-04


def test_tkt029b_car1_la_bajada_devuelve_los_22_verbos_y_deja_la_bitacora_como_estaba(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-04 · CA-R1 · invariante 10 · `D-3` — `upgrade head` y `downgrade 0015` no dejan rastro.

    Base en `0015` con dos asientos (`CREAR` y `DESACTIVAR`), escritos con el rol de aplicación.
    Fotografía A del esquema completo, de `bitacora` (columnas con su tipo, restricciones, índices,
    `relacl` y etiquetas del tipo) y de sus filas. Se sube a `0016` y se baja a `0015`: los verbos son
    exactamente los 22 de `0003` en su orden, la fotografía C es igual a la A, las filas no cambiaron,
    `to_regtype('accion_bitacora_0016')` es nulo (la bajada borra el tipo temporal) y
    `alembic_version` es `0015`. Y `DAR_BAJA` ya no existe: un `INSERT` con él responde `22P02`.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR)
    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)
    insertar_asiento(aplicacion, usuario, "CREAR")
    insertar_asiento(aplicacion, usuario, "DESACTIVAR")
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        bitacora_a = fotografia_de_bitacora(administrador)
        filas_a = filas_de_bitacora(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]
    assert len(filas_a) == 2
    assert bitacora_a[4] == tuple((verbo,) for verbo in VERBOS_0003)

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_NUEVA,)]
        assert verbos_de_la_base(administrador) == VERBOS_0016, "Control: la subida añadió el verbo"

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        bitacora_c = fotografia_de_bitacora(administrador)
        filas_c = filas_de_bitacora(administrador)
        version_c = version_de_alembic(administrador)
        verbos_c = verbos_de_la_base(administrador)
        temporal = administrador.execute(
            "SELECT to_regtype('accion_bitacora_0016') IS NULL"
        ).fetchone()
    assert version_c == [(REVISION_ANTERIOR,)]
    assert verbos_c == VERBOS_0003
    assert temporal == (True,), "La bajada debía borrar el tipo temporal accion_bitacora_0016"
    assert bitacora_c == bitacora_a
    assert c == a
    assert filas_c == filas_a, "Los asientos existentes no debían cambiar"

    with conectar("aplicacion", base_vacia) as otra, pytest.raises(psycopg.Error) as ya_no_existe:
        insertar_asiento(otra, usuario, "DAR_BAJA")
    assert ya_no_existe.value.sqlstate == "22P02", str(ya_no_existe.value)


# --------------------------------------------------------------------------- TC-05


def test_tkt029b_car1_la_bajada_se_niega_con_asientos_dar_baja(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-05 · CA-R1 esc. 2 · RN-04 · `D-3` — con un asiento `DAR_BAJA`, `downgrade 0015` lanza y no destruye nada.

    El rechazo es el de la guarda de la migración (`RAISE EXCEPTION`, `P0001`) y no el
    `invalid input value for enum` (`22P02`) de convertir la columna sin ella. El mensaje nombra
    `DAR_BAJA` y `0016`. Tras el rechazo, `alembic_version` sigue en `0016`, `DAR_BAJA` sigue en el
    tipo, el tipo temporal no existe y las filas de `bitacora` son las mismas.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)
    insertar_asiento(aplicacion, usuario, "CREAR")
    asiento_baja = insertar_asiento(aplicacion, usuario, "DAR_BAJA")
    with conectar("migracion", base_vacia) as administrador:
        antes = filas_de_bitacora(administrador)
    assert len(antes) == 2

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_vacia, REVISION_ANTERIOR, "downgrade")

    assert "DAR_BAJA" in str(rechazo.value), str(rechazo.value)
    assert "0016" in str(rechazo.value), str(rechazo.value)
    assert getattr(rechazo.value.orig, "sqlstate", None) == "P0001", (
        f"Debía rechazar la guarda (RAISE EXCEPTION), no el motor al convertir: {rechazo.value}"
    )
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)
        verbos = verbos_de_la_base(administrador)
        despues = filas_de_bitacora(administrador)
        temporal = administrador.execute(
            "SELECT to_regtype('accion_bitacora_0016') IS NULL"
        ).fetchone()
        sigue_el_asiento = administrador.execute(
            "SELECT accion::text FROM bitacora WHERE id = %s", (asiento_baja,)
        ).fetchone()
    assert version == [(REVISION_NUEVA,)], "La bajada negada debía dejar la versión en 0016"
    assert verbos == VERBOS_0016, "DAR_BAJA debía seguir en el tipo"
    assert temporal == (True,), "El rechazo no debía dejar el tipo temporal"
    assert despues == antes, "La bitácora debía quedar intacta"
    assert sigue_el_asiento == ("DAR_BAJA",)


# --------------------------------------------------------------------------- TC-06


def test_tkt029b_car1_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-06 · CA-R1 — `upgrade 0016`, `downgrade 0015` y `upgrade 0016` dejan lo mismo.

    La fotografía del esquema, la de `bitacora` y la lista de verbos tras la segunda subida son
    iguales a las de la primera. Es la prueba de que la bajada no dejó nada que estorbe a la
    siguiente subida (por ejemplo, un tipo temporal que choque al volver a renombrar).
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        primera = fotografia(administrador)
        bitacora_primera = fotografia_de_bitacora(administrador)
        verbos_primera = verbos_de_la_base(administrador)
        version_primera = version_de_alembic(administrador)
    assert version_primera == [(REVISION_NUEVA,)]
    assert verbos_primera == VERBOS_0016

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_ANTERIOR,)]
        assert verbos_de_la_base(administrador) == VERBOS_0003, "Control: la bajada quitó el verbo"

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        segunda = fotografia(administrador)
        bitacora_segunda = fotografia_de_bitacora(administrador)
        verbos_segunda = verbos_de_la_base(administrador)
        version_segunda = version_de_alembic(administrador)
    assert version_segunda == [(REVISION_NUEVA,)]
    assert verbos_segunda == verbos_primera
    assert bitacora_segunda == bitacora_primera
    assert segunda == primera


# --------------------------------------------------------------------------- TC-07


def test_tkt029b_car1_tras_la_bajada_el_rol_de_aplicacion_conserva_sus_privilegios(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-07 · CA-R1 · invariante 10 — la bajada no abre ni cierra permisos sobre la bitácora.

    Tras `downgrade 0015`, el rol de aplicación conserva `INSERT` y `SELECT` sobre `bitacora`,
    sigue sin `UPDATE`, `DELETE` ni `TRUNCATE`, y tiene `USAGE` sobre el tipo recreado. Se comprueba
    por catálogo y con operaciones reales: un asiento `CREAR` entra, y un `UPDATE` y un `DELETE`
    responden `42501`.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")

    with conectar("migracion", base_vacia) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_ANTERIOR,)]
        assert privilegio_de_tabla(administrador, "INSERT") is True
        assert privilegio_de_tabla(administrador, "SELECT") is True
        assert privilegio_de_tabla(administrador, "UPDATE") is False
        assert privilegio_de_tabla(administrador, "DELETE") is False
        assert privilegio_de_tabla(administrador, "TRUNCATE") is False
        assert uso_del_tipo(administrador) is True

    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)
    asiento = insertar_asiento(aplicacion, usuario, "CREAR")
    with pytest.raises(psycopg.Error) as actualizar:
        aplicacion.execute("UPDATE bitacora SET motivo = 'cambiado' WHERE id = %s", (asiento,))
    assert actualizar.value.sqlstate == "42501", str(actualizar.value)
    with pytest.raises(psycopg.Error) as borrar:
        aplicacion.execute("DELETE FROM bitacora WHERE id = %s", (asiento,))
    assert borrar.value.sqlstate == "42501", str(borrar.value)
    assert aplicacion.execute("SELECT count(*) FROM bitacora").fetchone() == (1,)
