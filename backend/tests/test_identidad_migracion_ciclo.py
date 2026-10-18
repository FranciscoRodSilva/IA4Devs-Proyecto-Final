"""Ciclo de migración hasta la semilla (TKT-003, fila 6): TC-10, TC-12 y TC-13.

Las tres pruebas migran hasta la revisión `0002` y no hasta la cabeza: el conjunto exacto de
tablas y la fotografía del catálogo siguen siendo ciertos cuando otro ticket añada tablas con
una revisión posterior. Parten de `base_vacia`, una base sin ninguna tabla de CIMENTA en el mismo
clúster, donde los roles de PostgreSQL ya existen: es el caso que distingue una subida que
converge de una que solo funciona la primera vez.

La fotografía incluye las filas de `rol`: una bajada que dejara la semilla a medias, o una
subida que la duplicara, cambiaría la fotografía aunque el esquema fuera el mismo.
"""

from collections.abc import Callable
from typing import Any

import psycopg

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]
Migrar = Callable[..., None]
Conexion = psycopg.Connection[tuple[Any, ...]]
Fotografia = tuple[tuple[tuple[Any, ...], ...], ...]

REVISION_DE_LA_SEMILLA = "0002"
TABLAS_DE_IDENTIDAD = {
    "alembic_version",
    "intento_acceso",
    "rol",
    "sesion",
    "usuario",
    "usuario_rol",
}
ROLES_DE_POSTGRESQL = ("cimenta_migracion", "cimenta_aplicacion", "cimenta_lectura")
ROLES_DE_LA_APLICACION = ("cimenta_aplicacion", "cimenta_lectura")

CONSULTAS_DE_LA_FOTOGRAFIA = (
    "SELECT table_name, column_name, data_type, is_nullable, column_default "
    "FROM information_schema.columns WHERE table_schema = 'public' ORDER BY 1, 2",
    "SELECT conrelid::regclass::text, conname, contype, pg_get_constraintdef(oid) "
    "FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2",
    "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2",
    "SELECT relname, relacl::text FROM pg_class "
    "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' ORDER BY 1",
    "SELECT d.defaclobjtype::text, r.rolname, d.defaclacl::text "
    "FROM pg_default_acl d JOIN pg_roles r ON r.oid = d.defaclrole ORDER BY 1, 2",
    "SELECT nspacl::text FROM pg_namespace WHERE nspname = 'public'",
    "SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, "
    "rolreplication, rolbypassrls, rolconnlimit FROM pg_roles "
    "WHERE rolname IN ('cimenta_aplicacion', 'cimenta_lectura') ORDER BY 1",
    "SELECT r.rolname, s.setconfig::text FROM pg_db_role_setting s "
    "JOIN pg_roles r ON r.oid = s.setrole "
    "WHERE r.rolname IN ('cimenta_aplicacion', 'cimenta_lectura') ORDER BY 1",
    "SELECT id::text, clave, nombre FROM rol ORDER BY clave",
)


def fotografia(conexion: Conexion) -> Fotografia:
    """Catálogo de `public` y de los dos roles, más las filas de `rol`, como una tupla ordenada.

    Columnas, restricciones, índices, `relacl` de cada tabla, privilegios por omisión, `nspacl`
    de `public`, atributos de los roles, sus ajustes en `pg_db_role_setting` y la semilla.
    """
    return tuple(
        tuple(conexion.execute(consulta).fetchall()) for consulta in CONSULTAS_DE_LA_FOTOGRAFIA
    )


def tablas_de_public(conexion: Conexion) -> set[str]:
    filas = conexion.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ).fetchall()
    return {str(nombre) for (nombre,) in filas}


def versiones(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def test_tkt003_ca02_esc01_migracion_inicial_sobre_base_vacia(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-10 · CA-2 esc. 1 — la subida sobre una base vacía deja las cinco tablas y los roles de PostgreSQL.

    Hasta `0002`, no hasta la cabeza: el conjunto de tablas es exacto y debe seguir siéndolo cuando
    otro ticket añada las suyas. `alembic_version` queda con la fila `0002`.
    """
    migrar(base_vacia, REVISION_DE_LA_SEMILLA)

    with conectar("migracion", base_vacia) as administrador:
        tablas = tablas_de_public(administrador)
        roles = administrador.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (list(ROLES_DE_POSTGRESQL),)
        ).fetchall()
        version = versiones(administrador)

    assert tablas == TABLAS_DE_IDENTIDAD
    assert sorted(nombre for (nombre,) in roles) == sorted(ROLES_DE_POSTGRESQL)
    assert version == [(REVISION_DE_LA_SEMILLA,)]


def test_tkt003_ca02_esc02_bajada_y_subida_sin_residuos(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-12 · CA-2 esc. 2, PA-T8 — `downgrade base` no deja nada y `upgrade` reconstruye lo mismo.

    Tras bajar solo queda `alembic_version`, sin filas; ningún privilegio por omisión; `public` y
    ninguna tabla nombran ya a los dos roles. Tras volver a subir, la fotografía del catálogo y de
    la semilla es idéntica a la primera. La precondición exige que la fotografía incluya las cinco
    tablas y las seis filas de `rol`: sin ella, la igualdad sería cierta para un esquema vacío.
    """
    migrar(base_vacia, REVISION_DE_LA_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        primera = fotografia(administrador)
    assert {tabla for tabla, *_ in primera[0]} == TABLAS_DE_IDENTIDAD
    assert len(primera[-1]) == 6

    migrar(base_vacia, "base", "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        tablas = tablas_de_public(administrador)
        filas_de_version = versiones(administrador)
        por_omision = administrador.execute("SELECT count(*) FROM pg_default_acl").fetchone()
        en_el_esquema = administrador.execute(
            "SELECT g.rolname FROM pg_namespace n "
            "CROSS JOIN LATERAL aclexplode(n.nspacl) a "
            "JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE n.nspname = 'public' AND g.rolname = ANY(%s)",
            (list(ROLES_DE_LA_APLICACION),),
        ).fetchall()
        en_las_tablas = administrador.execute(
            "SELECT c.relname, g.rolname FROM pg_class c "
            "CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE c.relnamespace = 'public'::regnamespace AND g.rolname = ANY(%s)",
            (list(ROLES_DE_LA_APLICACION),),
        ).fetchall()

    assert tablas == {"alembic_version"}
    assert filas_de_version == []
    assert por_omision == (0,)
    assert en_el_esquema == []
    assert en_las_tablas == []

    migrar(base_vacia, REVISION_DE_LA_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        segunda = fotografia(administrador)

    assert segunda == primera


def test_tkt003_ca02_esc03_aplicar_de_nuevo_no_cambia_nada(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-13 · CA-2 esc. 3 — aplicar otra vez la misma revisión no modifica ninguna tabla ni dato.

    La segunda subida termina sin error; la fotografía, que incluye las seis filas de `rol`, es
    la misma, y la versión sigue siendo `0002`.
    """
    migrar(base_vacia, REVISION_DE_LA_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        antes = fotografia(administrador)
    assert {tabla for tabla, *_ in antes[0]} == TABLAS_DE_IDENTIDAD
    assert len(antes[-1]) == 6

    migrar(base_vacia, REVISION_DE_LA_SEMILLA)

    with conectar("migracion", base_vacia) as administrador:
        despues = fotografia(administrador)
        version = versiones(administrador)
    assert despues == antes
    assert version == [(REVISION_DE_LA_SEMILLA,)]
