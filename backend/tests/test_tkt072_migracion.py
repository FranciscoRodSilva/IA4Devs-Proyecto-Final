"""TKT-072 · Migración `0010`: TC-18 a TC-21.

`0010` separa el concepto de obra de su aparición en una partida. Este archivo prueba lo que la
rodea: que sube, baja y vuelve a subir sin dejar rastro (`CA-8` esc. 1, `TC-18`), que sus dos
guardas se niegan con `P0001` y sin tocar nada si hay datos (`TC-19` y `TC-20`) y que cada guarda
toma el bloqueo de las tablas antes de comprobar (`TC-21`).

El ciclo y las bajadas rechazadas las ejecuta el rol de migración, que es quien las ejecuta en
producción; los datos se siembran con el rol de aplicación. La fotografía del catálogo y las
ayudas siguen el patrón de `test_tkt011_migracion_linea_base.py`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

import psycopg
import pytest
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

REVISION_ANTERIOR = "0009"
REVISION_NUEVA = "0010"
FUNCION = "presupuesto_proteger_copia_congelada"

# Las cuatro tablas que toca `0010` o que cuelgan de lo que toca.
TABLAS: tuple[str, ...] = ("concepto", "partida_concepto", "linea_base_concepto", "apu")

# --------------------------------------------------------------------------- ayudas


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


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


def fotografia(conexion: Conexion) -> dict[str, Any]:
    """Todo lo que `0010` toca en el catálogo sobre `concepto`, `partida_concepto`,
    `linea_base_concepto` y `apu`.

    Tablas, columnas (con `ordinal_position`, tipo, escala, nulabilidad y valor por omisión),
    restricciones con su definición, índices con su definición, privilegios de cada rol incluido
    `PUBLIC`, disparadores (nombre, tabla, `tgtype`, función) y el `prosrc` de la función de la
    copia congelada. Las restricciones `NOT NULL` (`contype = 'n'`) no entran: PostgreSQL 18 las
    registra con un nombre automático y su nulabilidad ya viene en `columnas`.
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
        "disparadores": [
            tuple(f)
            for f in conexion.execute(
                "SELECT t.tgname, c.relname, t.tgtype, p.proname FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid "
                "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace "
                "AND c.relname = ANY(%s) ORDER BY t.tgname",
                (tablas,),
            ).fetchall()
        ],
        "funcion": [
            tuple(f)
            for f in conexion.execute(
                "SELECT proname, prosrc, prosecdef FROM pg_proc "
                "WHERE pronamespace = 'public'::regnamespace AND proname = %s",
                (FUNCION,),
            ).fetchall()
        ],
        "todas_las_tablas": [
            str(f[0])
            for f in conexion.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ).fetchall()
        ],
    }


def filas_de_las_tablas(conexion: Conexion) -> dict[str, list[str]]:
    """Cada fila de las tablas que existan de entre `TABLAS`, como texto."""
    existentes = {
        str(f[0])
        for f in conexion.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(%s)",
            (list(TABLAS),),
        ).fetchall()
    }
    return {
        tabla: [
            str(f[0])
            for f in conexion.execute(f"SELECT t::text FROM {tabla} t ORDER BY t.id").fetchall()
        ]
        for tabla in TABLAS
        if tabla in existentes
    }


def contar_filas(conexion: Conexion, tabla: str) -> int:
    assert tabla in TABLAS, tabla
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()
    assert fila is not None
    return int(fila[0])


def columnas_de(foto: dict[str, Any], tabla: str) -> list[str]:
    return [str(c[2]) for c in foto["columnas"] if c[0] == tabla]


# --------------------------------------------------------------------------- TC-18


def test_tkt072_ca08_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-18 · CA-8 esc. 1 — `upgrade 0010`, `downgrade 0009` y `upgrade 0010` dejan lo que deben.

    En `0009` no existe `partida_concepto` y `concepto` tiene nueve columnas. Tras subir, existe
    `partida_concepto` y `concepto` queda con cinco columnas; tras bajar, la fotografía es idéntica a
    la de `0009` (posiciones de columna incluidas: la bajada recrea `concepto`) y `partida_concepto`
    no existe; tras volver a subir, la fotografía es idéntica a la primera subida.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]
    assert "partida_concepto" not in a["tablas"]
    assert len(columnas_de(a, "concepto")) == 9, "La precondición es el `concepto` de `0009`"

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        b = fotografia(administrador)
        version_b = version_de_alembic(administrador)
    assert version_b == [(REVISION_NUEVA,)]
    assert "partida_concepto" in b["tablas"], b["tablas"]
    assert columnas_de(b, "concepto") == ["id", "obra_id", "codigo", "descripcion", "unidad"]
    assert [d[0] for d in b["disparadores"]] == ["trg_linea_base_concepto_inmutable"]
    assert b["funcion"] and b["funcion"][0][1], "La función de la copia debe conservar su cuerpo"

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        version_c = version_de_alembic(administrador)
    assert version_c == [(REVISION_ANTERIOR,)]
    assert "partida_concepto" not in c["tablas"]
    assert c == a

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        d = fotografia(administrador)
        version_d = version_de_alembic(administrador)
    assert version_d == [(REVISION_NUEVA,)]
    assert d == b


# --------------------------------------------------------------------------- TC-19


def _sembrar_concepto_en_0009(datos: DatosPresupuesto) -> None:
    obra = datos.obra(codigo="AP-058-25")
    partida = datos.partida(area_id=datos.area(nivel_id=datos.nivel(obra_id=obra)))
    datos.concepto_anterior_a_0010(obra_id=obra, partida_id=partida)


def _sembrar_concepto_y_copia_en_0009(datos: DatosPresupuesto) -> None:
    datos.linea_base_con_copias_anterior_a_0010(estado="BORRADOR")


@pytest.mark.parametrize(
    ("sembrar", "tablas_con_filas"),
    [
        pytest.param(_sembrar_concepto_en_0009, "concepto", id="solo_un_concepto"),
        pytest.param(
            _sembrar_concepto_y_copia_en_0009,
            "concepto y linea_base_concepto",
            id="concepto_y_copia_en_un_borrador",
        ),
    ],
)
def test_tkt072_ca08_la_subida_se_niega_con_conceptos_escritos(
    sembrar: Callable[[DatosPresupuesto], None],
    tablas_con_filas: str,
    base_vacia: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto_en: Callable[[str], DatosPresupuesto],
) -> None:
    """TC-19 · CA-8 esc. 2 · `PA-T72.8` — `upgrade 0010` con filas en `concepto` o en `linea_base_concepto` responde `P0001`.

    El texto nombra la subida, `PA-T72.8` y exactamente las tablas con filas. La versión sigue en
    `0009`, y la fotografía y las filas no cambian, texto a texto.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    sembrar(datos_presupuesto_en(base_vacia))
    with conectar("migracion", base_vacia) as administrador:
        foto_antes = fotografia(administrador)
        filas_antes = filas_de_las_tablas(administrador)
    assert filas_antes["concepto"], "La precondición es al menos un concepto escrito"

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_vacia, REVISION_NUEVA)

    texto = str(rechazo.value)
    assert sqlstate_de(rechazo.value) == "P0001", texto
    assert "La subida de 0010 se niega" in texto, texto
    assert "PA-T72.8" in texto, texto
    assert f"hay filas en {tablas_con_filas}. TKT-072" in texto, texto
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)
        foto_despues = fotografia(administrador)
        filas_despues = filas_de_las_tablas(administrador)
    assert version == [(REVISION_ANTERIOR,)]
    assert foto_despues == foto_antes
    assert filas_despues == filas_antes


# --------------------------------------------------------------------------- TC-20


def _sembrar_una_aparicion(datos: DatosPresupuesto) -> None:
    datos.partida_concepto()


def _sembrar_una_congelada_con_copias(datos: DatosPresupuesto) -> None:
    datos.linea_base_con_copias(estado="CONGELADA")


def _sembrar_solo_un_concepto(datos: DatosPresupuesto) -> None:
    datos.concepto()


@pytest.mark.parametrize(
    ("sembrar", "destino", "tablas_con_filas"),
    [
        pytest.param(
            _sembrar_una_aparicion, "0009", "partida_concepto y concepto", id="una_aparicion"
        ),
        pytest.param(
            _sembrar_una_congelada_con_copias,
            "0006",
            "partida_concepto y concepto",
            id="linea_base_congelada_hasta_0006",
        ),
        pytest.param(_sembrar_solo_un_concepto, "0009", "concepto", id="solo_un_concepto"),
    ],
)
def test_tkt072_ca08_la_bajada_se_niega_con_datos_escritos(
    sembrar: Callable[[DatosPresupuesto], None],
    destino: str,
    tablas_con_filas: str,
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-20 · CA-8 esc. 3 · `PA-T72.7`, `P-1` — `downgrade` desde `0010` con filas en `partida_concepto` o en `concepto` responde `P0001`.

    El texto nombra la bajada, `PA-T72.7` y exactamente las tablas con filas. Con una línea base
    `CONGELADA` y bajada hasta `0006`, el código no es `IN001`: la guarda de `0010` corre antes que
    la de `0007`. La versión sigue en `0010`, y la fotografía y las filas no cambian.
    """
    sembrar(datos_presupuesto)
    with conectar("migracion", base_de_prueba) as administrador:
        foto_antes = fotografia(administrador)
        filas_antes = filas_de_las_tablas(administrador)
        version_antes = version_de_alembic(administrador)
    assert version_antes == [(REVISION_NUEVA,)]
    assert filas_antes["concepto"], "La precondición es al menos un concepto escrito"

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, destino, "downgrade")

    texto = str(rechazo.value)
    assert sqlstate_de(rechazo.value) == "P0001", texto
    assert "La bajada de 0010 se niega" in texto, texto
    assert "PA-T72.7" in texto, texto
    assert f"hay filas en {tablas_con_filas}. El esquema de 0009" in texto, texto
    with conectar("migracion", base_de_prueba) as administrador:
        version = version_de_alembic(administrador)
        foto_despues = fotografia(administrador)
        filas_despues = filas_de_las_tablas(administrador)
    assert version == [(REVISION_NUEVA,)]
    assert foto_despues == foto_antes
    assert filas_despues == filas_antes


# --------------------------------------------------------------------------- TC-21


def _sembrar_sin_confirmar_en_0009(datos: DatosPresupuesto, sesion_a: Conexion) -> tuple[str, str]:
    """Sesión A escribe un concepto de `0009` sin confirmar; devuelve su tabla y la guarda esperada."""
    obra = datos.obra(codigo="AP-058-25")
    partida = datos.partida(area_id=datos.area(nivel_id=datos.nivel(obra_id=obra)))
    datos.concepto_anterior_a_0010(obra_id=obra, partida_id=partida, conexion=sesion_a)
    return "concepto", "La subida de 0010 se niega"


def _sembrar_sin_confirmar_en_0010(datos: DatosPresupuesto, sesion_a: Conexion) -> tuple[str, str]:
    """Sesión A escribe un concepto y su aparición de `0010` sin confirmar."""
    datos.partida_concepto(conexion=sesion_a)
    return "partida_concepto", "La bajada de 0010 se niega"


@pytest.mark.parametrize("sentido", ["subida", "bajada"])
def test_tkt072_ca08_la_guarda_toma_el_bloqueo_antes_de_comprobar(
    sentido: str,
    request: pytest.FixtureRequest,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto_en: Callable[[str], DatosPresupuesto],
) -> None:
    """TC-21 · CA-8 esc. 2 y 3 — cada guarda toma el bloqueo de sus tablas antes de comprobar.

    La sesión A (rol de aplicación, sin confirmar) escribe un dato que la guarda debe ver. Mientras
    tanto, en un hilo, corre la migración con el rol de migración y debe quedar esperando a A
    (visto en `pg_stat_activity` y `pg_blocking_pids`, con un sondeo de tiempo máximo, sin una
    espera fija). Cuando A confirma, la migración falla con `P0001` y el texto de su guarda; la
    versión no cambia y la fila de A sigue ahí.

    Sin el `LOCK TABLE`, la comprobación vería la instantánea vacía y el `DROP` posterior
    borraría el dato recién confirmado, o la migración terminaría sin error.
    """
    direccion: Literal["upgrade", "downgrade"]
    if sentido == "subida":
        base = str(request.getfixturevalue("base_vacia"))
        migrar(base, REVISION_ANTERIOR)
        version_esperada, destino, direccion = REVISION_ANTERIOR, REVISION_NUEVA, "upgrade"
    else:
        base = str(request.getfixturevalue("base_de_prueba"))
        version_esperada, destino, direccion = REVISION_NUEVA, REVISION_ANTERIOR, "downgrade"
    datos = datos_presupuesto_en(base)
    observador = conectar("migracion", base)

    sesion_a = conectar("aplicacion", base, autocommit=False)
    if sentido == "subida":
        tabla, texto_de_la_guarda = _sembrar_sin_confirmar_en_0009(datos, sesion_a)
    else:
        tabla, texto_de_la_guarda = _sembrar_sin_confirmar_en_0010(datos, sesion_a)
    pid_de_a = sesion_a.info.backend_pid

    def migracion_esperando_a() -> bool:
        fila = observador.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock' AND %s = ANY(pg_blocking_pids(pid))",
            (pid_de_a,),
        ).fetchone()
        return fila is not None and fila[0] > 0

    with ThreadPoolExecutor(max_workers=1) as hilos:
        migracion = hilos.submit(migrar, base, destino, direccion)
        try:
            esperar_hasta(lambda: migracion.done() or migracion_esperando_a())
            esperaba_a = not migracion.done() and migracion_esperando_a()
        finally:
            sesion_a.commit()
        error = migracion.exception(timeout=60)

    assert esperaba_a, "La migración debía quedar esperando el bloqueo de la sesión A"
    assert isinstance(error, DBAPIError), (
        f"La migración debía fallar con P0001 y terminó con {error!r}"
    )
    assert sqlstate_de(error) == "P0001", str(error)
    assert texto_de_la_guarda in str(error), str(error)
    assert version_de_alembic(observador) == [(version_esperada,)]
    assert contar_filas(observador, tabla) == 1, "El dato confirmado por A debía sobrevivir"
    if sentido == "subida":
        fila = observador.execute(
            "SELECT cantidad, precio_unitario, importe FROM concepto"
        ).fetchone()
        assert fila == (
            Decimal("100.0000"),
            Decimal("250.0000"),
            Decimal("25000.0000"),
        ), "El concepto conserva sus cuatro columnas de `0009`"
