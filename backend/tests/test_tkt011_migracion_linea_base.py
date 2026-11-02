"""Migración y regresión de TKT-011b, fila B6: TC-47 a TC-50 y TC-INV-4b a TC-INV-6b sobre `0007`.

La migración `0007` crea siete tablas del módulo `presupuesto` (`linea_base`, `linea_base_concepto`,
`explosion_presupuesto`, `presupuesto_control`, `importacion`, `importacion_error` y
`rendimiento_observado`), dos funciones y tres disparadores. Este archivo prueba lo que la rodea: que
sube, baja y vuelve a subir sin dejar rastro (`CA-18`), que su bajada se niega a borrar una línea base
que no es `BORRADOR` (`CONGELADA` o `SUPERSEDIDA`: un presupuesto firmado que ya estuvo vigente) y no
borra nada al negarse, ni siquiera si otra sesión congela una línea base mientras la bajada
comprueba (`CA-19`, invariante 14), que cada restricción, índice y disparador lleva el nombre del
diseño (`CA-20`) y que la migración cuelga de `0006` sin cruzar fronteras ni usar flotantes (`CA-R4`
a `CA-R6`).

Como en `test_tkt011_regresion.py`, ninguna prueba afirma la cabeza de las migraciones por su número:
las que suben a una revisión la nombran explícita, y la que necesita la cadena la lee con
`ScriptDirectory`.

El ciclo y la bajada rechazada se ejecutan con el rol de migración, que es quien las ejecuta en
producción; el catálogo se lee con el mismo rol y los datos de las pruebas de bajada se siembran con el
rol de aplicación. Nunca se usa el propietario por otra vía. Los nombres esperados de `TC-50` son copia
literal del diseño, no se derivan de la migración.

La guarda niega la bajada con cualquier línea base que no sea `BORRADOR`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0006"
REVISION_NUEVA = "0007"

# Las siete tablas que entrega TKT-011b, en el orden del diseño.
TABLAS: tuple[str, ...] = (
    "linea_base",
    "linea_base_concepto",
    "explosion_presupuesto",
    "presupuesto_control",
    "importacion",
    "importacion_error",
    "rendimiento_observado",
)

# Las doce tablas de `0006`.
TABLAS_DE_0006: tuple[str, ...] = (
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

FUNCIONES: tuple[str, ...] = (
    "presupuesto_proteger_linea_base",
    "presupuesto_proteger_copia_congelada",
)

DISPARADORES: tuple[str, ...] = (
    "trg_linea_base_solo_avanza",
    "trg_linea_base_concepto_inmutable",
    "trg_explosion_presupuesto_inmutable",
)

PREFIJO_POR_TIPO = {"p": "pk_", "f": "fk_", "u": "uq_", "c": "ck_", "i": "ix_", "iu": "uq_"}

# Copia literal de las secciones «Restricciones CHECK» y «Unicidad e índices» del diseño, para las
# siete tablas. `p`, `f`, `u` y `c` llevan el nombre de la restricción; `i` es un índice que no
# respalda ninguna restricción y no es único (par: nombre, columna); `iu` es un índice único que no
# respalda ninguna restricción —el índice único parcial de la línea base congelada—.
ESTRUCTURA_ESPERADA: dict[str, dict[str, tuple[Any, ...]]] = {
    "linea_base": {
        "p": ("pk_linea_base",),
        "f": (
            "fk_linea_base_obra_id",
            "fk_linea_base_congelada_por_id",
            "fk_linea_base_creado_por_id",
        ),
        "c": ("ck_linea_base_estado", "ck_linea_base_importe_venta_no_negativo"),
        "i": (("ix_linea_base_obra_id", "obra_id"),),
        "iu": (("uq_linea_base_obra_id_congelada", "obra_id"),),
    },
    "linea_base_concepto": {
        "p": ("pk_linea_base_concepto",),
        "f": ("fk_linea_base_concepto_linea_base_id", "fk_linea_base_concepto_concepto_id"),
        "c": (
            "ck_linea_base_concepto_cantidad_no_negativo",
            "ck_linea_base_concepto_precio_unitario_no_negativo",
            "ck_linea_base_concepto_importe_no_negativo",
        ),
        "i": (("ix_linea_base_concepto_linea_base_id", "linea_base_id"),),
    },
    "explosion_presupuesto": {
        "p": ("pk_explosion_presupuesto",),
        "f": (
            "fk_explosion_presupuesto_linea_base_id",
            "fk_explosion_presupuesto_tipo_partida_id",
            "fk_explosion_presupuesto_insumo_id",
        ),
        "u": ("uq_explosion_presupuesto_linea_tipo_insumo",),
        "c": (
            "ck_explosion_presupuesto_cantidad_presupuestada_no_negativo",
            "ck_explosion_presupuesto_rendimiento_congelado_no_negativo",
            "ck_explosion_presupuesto_costo_unitario_no_negativo",
            "ck_explosion_presupuesto_importe_venta_no_negativo",
        ),
    },
    "presupuesto_control": {
        "p": ("pk_presupuesto_control",),
        "f": (
            "fk_presupuesto_control_linea_base_id",
            "fk_presupuesto_control_tipo_partida_id",
            "fk_presupuesto_control_capturado_por_id",
            "fk_presupuesto_control_actualizado_por_id",
        ),
        "u": ("uq_presupuesto_control_linea_base_id_tipo_partida_id",),
        "c": (
            "ck_presupuesto_control_importe_tope_no_negativo",
            "ck_presupuesto_control_importe_sugerido_no_negativo",
        ),
    },
    "importacion": {
        "p": ("pk_importacion",),
        "f": ("fk_importacion_obra_id", "fk_importacion_importado_por_id"),
        "c": ("ck_importacion_estado", "ck_importacion_progreso_rango"),
        "i": (("ix_importacion_obra_id", "obra_id"),),
    },
    "importacion_error": {
        "p": ("pk_importacion_error",),
        "f": ("fk_importacion_error_importacion_id",),
        "c": ("ck_importacion_error_tipo",),
        "i": (("ix_importacion_error_importacion_id", "importacion_id"),),
    },
    "rendimiento_observado": {
        "p": ("pk_rendimiento_observado",),
        "f": ("fk_rendimiento_observado_obra_id", "fk_rendimiento_observado_insumo_id"),
        "c": (
            "ck_rendimiento_observado_consumo_acumulado_no_negativo",
            "ck_rendimiento_observado_avance_acumulado_no_negativo",
            "ck_rendimiento_observado_rendimiento_no_negativo",
            "ck_rendimiento_observado_rendimiento_congelado_no_negativo",
        ),
    },
}


# --------------------------------------------------------------------------- ayudas


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def cabeza_de_las_migraciones() -> str:
    """La cabeza que dice `ScriptDirectory`, sin afirmarla por su número."""
    guion = ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas
    return cabezas[0]


def tablas_publicas(conexion: Conexion) -> list[str]:
    filas = conexion.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def disparadores_y_funciones(conexion: Conexion) -> dict[str, Any]:
    """Los disparadores no internos de las siete tablas o de las dos funciones, y las funciones.

    De cada disparador: nombre, tabla, `tgtype` y función que ejecuta. De cada función: nombre,
    `prosrc`, si es `SECURITY DEFINER` y su lenguaje.
    """
    return {
        "disparadores": [
            tuple(f)
            for f in conexion.execute(
                "SELECT t.tgname, c.relname, t.tgtype, p.proname FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid "
                "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace "
                "AND (c.relname = ANY(%s) OR p.proname = ANY(%s)) ORDER BY t.tgname",
                (list(TABLAS), list(FUNCIONES)),
            ).fetchall()
        ],
        "funciones": [
            tuple(f)
            for f in conexion.execute(
                "SELECT p.proname, p.prosrc, p.prosecdef, l.lanname FROM pg_proc p "
                "JOIN pg_language l ON l.oid = p.prolang "
                "WHERE p.pronamespace = 'public'::regnamespace AND p.proname = ANY(%s) "
                "ORDER BY p.proname",
                (list(FUNCIONES),),
            ).fetchall()
        ],
    }


def fotografia(conexion: Conexion) -> dict[str, Any]:
    """Todo lo que `0007` deja en el catálogo sobre sus siete tablas, tres disparadores y dos funciones.

    Tablas, columnas (con tipo, escala, nulabilidad y valor por omisión), restricciones con su
    definición, índices con su definición, privilegios de cada rol incluido `PUBLIC`, disparadores
    (nombre, tabla, `tgtype`, función) y funciones (`prosrc`). Las restricciones `NOT NULL`
    (`contype = 'n'`) no entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad
    ya viene en `columnas`.
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
        **disparadores_y_funciones(conexion),
        "todas_las_tablas": tablas_publicas(conexion),
    }


def estructura_observada(conexion: Conexion) -> dict[str, dict[str, tuple[Any, ...]]]:
    """Restricciones (`p`, `f`, `u`, `c`) por nombre e índices sueltos por (nombre, columna).

    Un índice que no respalda una clave primaria ni una única es `i` si no es único e `iu` si lo es
    (el índice único parcial). Uno con varias columnas aparece una vez por columna.
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
    sueltos = conexion.execute(
        "SELECT t.relname, ic.relname, a.attname, i.indisunique FROM pg_index i "
        "JOIN pg_class ic ON ic.oid = i.indexrelid JOIN pg_class t ON t.oid = i.indrelid "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM pg_constraint c "
        "WHERE c.conindid = i.indexrelid AND c.contype IN ('p', 'u'))",
        (list(TABLAS),),
    ).fetchall()
    for tabla, nombre, columna, unico in sueltos:
        tipo = "iu" if unico else "i"
        observada.setdefault(str(tabla), {}).setdefault(tipo, []).append(
            (str(nombre), str(columna))
        )
    return {
        tabla: {tipo: tuple(sorted(valores)) for tipo, valores in por_tipo.items()}
        for tabla, por_tipo in observada.items()
    }


def filas_de_las_copias(conexion: Conexion) -> dict[str, list[str]]:
    """Cada fila de `linea_base`, `linea_base_concepto` y `explosion_presupuesto`, como texto."""
    return {
        tabla: [
            str(f[0])
            for f in conexion.execute(f"SELECT t::text FROM {tabla} t ORDER BY t.id").fetchall()
        ]
        for tabla in ("linea_base", "linea_base_concepto", "explosion_presupuesto")
    }


def sqlstate_de(error: DBAPIError) -> str | None:
    """El `sqlstate` del error de origen (el de PostgreSQL), no el de la envoltura de SQLAlchemy."""
    origen = error.orig
    assert isinstance(origen, psycopg.Error), repr(origen)
    return origen.sqlstate


def esperar_hasta(condicion: Callable[[], bool], limite: float = 30.0) -> None:
    """Sondea `condicion` cada 50 ms hasta que se cumple o vence `limite` segundos.

    No decide si la condición debía cumplirse: quien llama afirma después lo que observó.
    """
    vence = time.monotonic() + limite
    while time.monotonic() < vence and not condicion():
        time.sleep(0.05)


# --------------------------------------------------------------------------- TC-47


def test_tkt011_ca18_0007_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-47 · CA-18 — `upgrade 0007`, `downgrade 0006` y `upgrade 0007` dejan lo que deben.

    Tras subir, la fotografía del catálogo (tablas, columnas, restricciones con su definición,
    índices con su definición, privilegios, disparadores y funciones) tiene las siete tablas, los tres
    disparadores y las dos funciones; si no los tuviera, comparar dos fotografías vacías pasaría sin
    afirmar nada. Tras bajar a `0006` no queda ninguna de las siete tablas, ni de las dos funciones, ni
    de los disparadores; las demás tablas siguen y la versión es `0006`. Tras volver a subir, la
    fotografía es idéntica a la primera.
    """
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        primera = fotografia(administrador)
        version_subida = version_de_alembic(administrador)
    assert version_subida == [(REVISION_NUEVA,)]
    assert primera["tablas"] == sorted(TABLAS), (
        f"La precondición exige las siete tablas tras `upgrade {REVISION_NUEVA}`: {primera['tablas']}"
    )
    assert [d[0] for d in primera["disparadores"]] == sorted(DISPARADORES), primera["disparadores"]
    assert [f[0] for f in primera["funciones"]] == sorted(FUNCIONES), primera["funciones"]
    assert all(f[1] for f in primera["funciones"]), "Cada función debe tener cuerpo"
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
    assert tras_bajar["disparadores"] == []
    assert tras_bajar["funciones"] == []
    assert version_bajada == [(REVISION_ANTERIOR,)]
    # La bajada borra las siete y ninguna otra: todo lo que existía antes de `0007` sigue.
    assert tras_bajar["todas_las_tablas"] == sorted(set(primera["todas_las_tablas"]) - set(TABLAS))
    assert set(TABLAS_DE_0006) <= set(tras_bajar["todas_las_tablas"])

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        segunda = fotografia(administrador)
        version_final = version_de_alembic(administrador)
    assert version_final == [(REVISION_NUEVA,)]
    assert segunda == primera


# --------------------------------------------------------------------------- TC-48 y TC-49


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt011_ca19_no_se_baja_con_una_linea_base_congelada(
    estado: str,
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-48 · CA-19 esc. 1 · RN-01, invariante 14 — `downgrade 0006` se niega y no borra nada.

    Con una línea base `CONGELADA` o `SUPERSEDIDA` (una `SUPERSEDIDA` es un presupuesto firmado que
    ya estuvo vigente) y sus copias (una de concepto y un renglón de explosión), la bajada lanza un
    error cuyo texto nombra «línea base CONGELADA o SUPERSEDIDA» y `RN-01`, y cuyo `sqlstate` de
    origen es `IN001`. Como `env.py` ejecuta la cadena en una transacción (E-12), la versión sigue en
    la cabeza que dice `ScriptDirectory`, las siete tablas y las dos funciones existen y las filas son
    exactamente las mismas, texto a texto.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado=estado)
    with conectar("migracion", base_de_prueba) as administrador:
        estados = administrador.execute("SELECT id, estado FROM linea_base").fetchall()
        antes = filas_de_las_copias(administrador)
        entes_antes = disparadores_y_funciones(administrador)
        version_antes = version_de_alembic(administrador)
    assert estados == [(copias.linea_base_id, estado)], f"La precondición es una {estado}"
    assert len(antes["linea_base_concepto"]) == 1 and len(antes["explosion_presupuesto"]) == 1
    assert version_antes == [(cabeza_de_las_migraciones(),)]

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, REVISION_ANTERIOR, "downgrade")

    texto = str(rechazo.value)
    assert "línea base CONGELADA o SUPERSEDIDA" in texto, texto
    assert "RN-01" in texto, texto
    assert sqlstate_de(rechazo.value) == "IN001", texto
    with conectar("migracion", base_de_prueba) as administrador:
        version = version_de_alembic(administrador)
        tablas = administrador.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename = ANY(%s) ORDER BY tablename",
            (list(TABLAS),),
        ).fetchall()
        despues = filas_de_las_copias(administrador)
        entes_despues = disparadores_y_funciones(administrador)
    assert version == [(cabeza_de_las_migraciones(),)]
    assert [str(t[0]) for t in tablas] == sorted(TABLAS)
    assert despues == antes
    assert entes_despues == entes_antes
    assert len(entes_despues["funciones"]) == len(FUNCIONES)
    assert len(entes_despues["disparadores"]) == len(DISPARADORES)


def test_tkt011_ca19_solo_con_borradores_la_bajada_elimina_las_tablas(
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-49 · CA-19 esc. 2 — solo con borradores, la bajada elimina las siete tablas y sus funciones.

    Con solo líneas base `BORRADOR` (una con sus copias y otra sin ellas), `downgrade 0006` termina:
    ninguna de las siete tablas, ni de las dos funciones, ni de los disparadores existe, la versión
    es `0006` y los datos de las tablas de `0006` (las obras de las dos líneas base) siguen ahí, sin
    cambios. Un borrador no es un presupuesto firmado, así que la guarda no lo protege.
    """
    datos_presupuesto.linea_base_con_copias(estado="BORRADOR")
    datos_presupuesto.linea_base()
    with conectar("migracion", base_de_prueba) as administrador:
        estados = administrador.execute("SELECT estado FROM linea_base ORDER BY id").fetchall()
        obras_antes = administrador.execute("SELECT id FROM obra ORDER BY id").fetchall()
        copias_antes = administrador.execute(
            "SELECT (SELECT count(*) FROM linea_base_concepto), "
            "(SELECT count(*) FROM explosion_presupuesto)"
        ).fetchone()
    assert estados == [("BORRADOR",), ("BORRADOR",)], "La precondición es solo BORRADOR"
    assert len(obras_antes) == 2
    assert copias_antes == (1, 1), "La precondición es una línea base con copias y otra sin ellas"

    migrar(base_de_prueba, REVISION_ANTERIOR, "downgrade")

    with conectar("migracion", base_de_prueba) as administrador:
        version = version_de_alembic(administrador)
        restantes = fotografia(administrador)
        obras_despues = administrador.execute("SELECT id FROM obra ORDER BY id").fetchall()
    assert version == [(REVISION_ANTERIOR,)]
    assert restantes["tablas"] == []
    assert restantes["disparadores"] == []
    assert restantes["funciones"] == []
    assert obras_despues == obras_antes


def test_tkt011_ca19_la_guarda_toma_el_bloqueo_antes_de_comprobar(
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """CA-19 esc. 3 · RN-01, invariante 14 — la guarda toma el bloqueo antes de comprobar.

    La sesión A (rol de aplicación, sin confirmar) pasa un `BORRADOR` a `CONGELADA`. Mientras tanto,
    en un hilo, corre `downgrade 0006` con el rol de migración. El hilo debe quedar esperando a A
    (visto en `pg_stat_activity` y `pg_blocking_pids`, con un sondeo de tiempo máximo, sin una espera
    fija). Cuando A confirma, la bajada debe terminar con `IN001`: la guarda ve la `CONGELADA` ya
    confirmada. La versión sigue en la cabeza, las siete tablas existen, la línea base sigue
    `CONGELADA` y las copias son las mismas.

    Sin el `LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` de la guarda, esta comprobación usa su
    instantánea anterior (ve un `BORRADOR`), el `DROP TABLE` espera a A y, al confirmar esta, borra
    una `CONGELADA` recién congelada: la bajada termina sin error.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="BORRADOR")
    observador = conectar("migracion", base_de_prueba)
    copias_antes = {
        tabla: filas
        for tabla, filas in filas_de_las_copias(observador).items()
        if tabla != "linea_base"
    }
    assert len(copias_antes["linea_base_concepto"]) == 1
    assert len(copias_antes["explosion_presupuesto"]) == 1

    sesion_a = conectar("aplicacion", base_de_prueba, autocommit=False)
    datos_presupuesto.congelar(copias.linea_base_id, conexion=sesion_a)
    pid_de_a = sesion_a.info.backend_pid

    def bajada_esperando_a() -> bool:
        fila = observador.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock' AND %s = ANY(pg_blocking_pids(pid))",
            (pid_de_a,),
        ).fetchone()
        return fila is not None and fila[0] > 0

    with ThreadPoolExecutor(max_workers=1) as hilos:
        bajada = hilos.submit(migrar, base_de_prueba, REVISION_ANTERIOR, "downgrade")
        try:
            esperar_hasta(lambda: bajada.done() or bajada_esperando_a())
            esperaba_a = not bajada.done() and bajada_esperando_a()
        finally:
            sesion_a.commit()
        error = bajada.exception(timeout=60)

    assert esperaba_a, "La bajada debía quedar esperando el bloqueo de la sesión A"
    assert isinstance(error, DBAPIError), (
        f"La bajada debía fallar con IN001 y terminó con {error!r}"
    )
    assert sqlstate_de(error) == "IN001", str(error)
    assert "RN-01" in str(error), str(error)
    version = version_de_alembic(observador)
    tablas = observador.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename = ANY(%s) ORDER BY tablename",
        (list(TABLAS),),
    ).fetchall()
    estados = observador.execute("SELECT id, estado FROM linea_base").fetchall()
    copias_despues = {
        tabla: filas
        for tabla, filas in filas_de_las_copias(observador).items()
        if tabla != "linea_base"
    }
    entes = disparadores_y_funciones(observador)
    assert version == [(cabeza_de_las_migraciones(),)]
    assert [str(t[0]) for t in tablas] == sorted(TABLAS)
    assert estados == [(copias.linea_base_id, "CONGELADA")]
    assert copias_despues == copias_antes
    assert len(entes["funciones"]) == len(FUNCIONES)
    assert len(entes["disparadores"]) == len(DISPARADORES)


# --------------------------------------------------------------------------- TC-50


def test_tkt011_ca20_restricciones_indices_y_disparadores_con_nombre(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-50 · CA-20 — los nombres de restricciones, índices y disparadores son los del diseño.

    Compara, tabla por tabla, el conjunto exacto de `conname` por tipo (clave primaria, foránea,
    única y `CHECK`) y el de los índices que no respaldan ninguna restricción, con su columna
    indexada según `pg_index`, con la copia literal del diseño. Después, que cada nombre empieza por el
    prefijo de su tipo, que `pg_indexes` contiene exactamente los índices de las claves primarias, de
    las únicas y los sueltos, y que los tres disparadores de las siete tablas son exactamente los del
    diseño, todos con prefijo `trg_`. Un nombre de más de 63 caracteres que PostgreSQL truncara se vería
    como una diferencia de conjunto. Las dos funciones son `SECURITY INVOKER`: `prosecdef` es falso.
    """
    esperada = {
        tabla: {tipo: tuple(sorted(valores)) for tipo, valores in por_tipo.items()}
        for tabla, por_tipo in ESTRUCTURA_ESPERADA.items()
    }
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
        disparadores = [
            (str(nombre), str(tabla))
            for nombre, tabla in migracion.execute(
                "SELECT t.tgname, c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace "
                "AND c.relname = ANY(%s)",
                (list(TABLAS),),
            ).fetchall()
        ]
        funciones = disparadores_y_funciones(migracion)["funciones"]

    assert observada == esperada
    assert [(f[0], f[2]) for f in funciones] == [(n, False) for n in sorted(FUNCIONES)], funciones

    for tabla, por_tipo in observada.items():
        for tipo, valores in por_tipo.items():
            for valor in valores:
                nombre = valor[0] if tipo in ("i", "iu") else valor
                assert nombre.startswith(PREFIJO_POR_TIPO[tipo]), (
                    f"{tabla}.{nombre} es de tipo '{tipo}' y debería empezar por "
                    f"'{PREFIJO_POR_TIPO[tipo]}'"
                )

    indices_esperados = sorted(
        [
            (tabla, nombre)
            for tabla, por_tipo in esperada.items()
            for tipo in ("p", "u")
            for nombre in por_tipo.get(tipo, ())
        ]
        + [
            (tabla, nombre)
            for tabla, por_tipo in esperada.items()
            for tipo in ("i", "iu")
            for nombre, _columna in por_tipo.get(tipo, ())
        ]
    )
    assert sorted(indices) == indices_esperados

    assert sorted(nombre for nombre, _tabla in disparadores) == sorted(DISPARADORES)
    assert all(nombre.startswith("trg_") for nombre, _tabla in disparadores), disparadores
    assert sorted(disparadores) == [
        ("trg_explosion_presupuesto_inmutable", "explosion_presupuesto"),
        ("trg_linea_base_concepto_inmutable", "linea_base_concepto"),
        ("trg_linea_base_solo_avanza", "linea_base"),
    ]


# --------------------------------------------------------------------------- TC-INV-4b a TC-INV-6b


def test_tkt011_car4_0007_cuelga_de_0006() -> None:
    """TC-INV-4b · CA-R4 — la cadena tiene una sola cabeza y `0007` cuelga de `0006`.

    No afirma qué revisión es la cabeza: una migración futura no debe ponerla en rojo. No usa base de
    datos. La cadena desde la base hasta la cabeza contiene `0007`.
    """
    guion = ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))
    cabezas = guion.get_heads()
    revision = guion.get_revision(REVISION_NUEVA)

    assert len(cabezas) == 1, cabezas
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR
    cadena = [r.revision for r in guion.walk_revisions("base", cabezas[0])]
    assert REVISION_NUEVA in cadena and REVISION_ANTERIOR in cadena


def test_tkt011_car5_claves_foraneas_de_las_siete_tablas_solo_al_modulo_o_a_usuario(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-5b · CA-R5 · regla 3 de CLAUDE.md — ninguna clave foránea cruza un módulo salvo a `usuario`.

    Toda clave foránea de las siete tablas apunta a una de ellas, a una de las doce de `0006` o a
    `usuario`. La precondición exige las diecisiete claves del diseño y que haya de los tres
    destinos, para que el recorrido no sea el de una lista vacía.
    """
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT t.relname, c.conname, p.relname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid JOIN pg_class p ON p.oid = c.confrelid "
            "WHERE c.contype = 'f' AND t.relnamespace = 'public'::regnamespace "
            "AND t.relname = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()

    numero_de_claves = sum(len(por_tipo.get("f", ())) for por_tipo in ESTRUCTURA_ESPERADA.values())
    assert numero_de_claves == 17
    assert len(filas) == numero_de_claves
    destinos = {str(p) for _, _, p in filas}
    assert destinos & set(TABLAS), "Alguna clave foránea debe apuntar a las siete tablas"
    assert destinos & set(TABLAS_DE_0006), "Alguna clave foránea debe apuntar a las doce de 0006"
    assert "usuario" in destinos, "Alguna clave foránea debe apuntar a `usuario`"
    permitidos = set(TABLAS) | set(TABLAS_DE_0006) | {"usuario"}
    ajenos = sorted((str(h), str(n), str(p)) for h, n, p in filas if str(p) not in permitidos)
    assert ajenos == [], ajenos


def test_tkt011_car6_ningun_flotante_en_las_siete_tablas(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-6b · CA-R6 · regla 1 de CLAUDE.md — ninguna columna de las siete tablas es de punto flotante.

    Ni `real` ni `double precision`, vistos por `data_type` y por el tipo base (`float4`, `float8`).
    La precondición exige que el recorrido vea las columnas de las siete tablas y que haya columnas
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
