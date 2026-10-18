"""Uso del esquema `public` (TKT-003, hallazgo de la fila 9): el `USAGE` de los roles es propio.

PostgreSQL 15 y posteriores conceden `USAGE` sobre `public` a `PUBLIC`, así que `GRANT USAGE`
de §3 es invisible mientras nadie revoque ese privilegio ajeno: el mutante X-08 (quitar la
sentencia) dejaba la suite en verde. Este caso lo hace visible sin leer el texto de la migración.
"""

from collections.abc import Callable
from typing import Any

import psycopg

Conectar = Callable[..., psycopg.Connection[tuple[Any, ...]]]


def test_tkt003_ca05_esc03_usage_del_esquema_no_depende_de_public(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """CA-5 esc. 3 — los dos roles conservan `USAGE` sobre `public` aunque se revoque a PUBLIC.

    La base es una copia desechable de la plantilla. Precondición: tras revocar, `PUBLIC` ya no
    figura con `USAGE` en `nspacl`; sin ella el caso no distinguiría el privilegio propio del ajeno.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute("REVOKE USAGE ON SCHEMA public FROM PUBLIC")
        de_public = migracion.execute(
            "SELECT count(*) FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a "
            "WHERE n.nspname = 'public' AND a.grantee = 0 AND a.privilege_type = 'USAGE'"
        ).fetchone()
        con_uso = {
            rol: migracion.execute(
                "SELECT has_schema_privilege(%s, 'public', 'USAGE')", (f"cimenta_{rol}",)
            ).fetchone()
            for rol in ("aplicacion", "lectura")
        }

    assert de_public == (0,)
    assert con_uso == {"aplicacion": (True,), "lectura": (True,)}
