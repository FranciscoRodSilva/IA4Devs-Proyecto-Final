"""TKT-019 · Migraciones `0014` y `0015` y esquema de `compras`: TC-01, TC-02, TC-03, TC-28 y TC-29.

`0014` crea las siete tablas del módulo `compras` (modelo de datos §5) y `0015` siembra las dos
series de `folio_consecutivo` (`D-8`). Este archivo prueba las migraciones como piezas de la cadena,
sin pasar por ningún caso de uso: que sigue habiendo una sola cabeza y `0014` cuelga de `0013`
(`TC-01`, `CA-R1`), que sube, baja y vuelve a subir sin dejar rastro (`TC-02`, `CA-R1`), que ninguna
tabla anterior cambia (`TC-03`, `CA-R2`), que la bajada de `0014` se niega mientras haya solicitudes
de autorización (`TC-28` parte a, fila F2, `CA-R1`, `RN-04`, `D-18`), que la bajada de `0015` se
niega mientras haya folios emitidos (`TC-28` parte b, fila F4, `D-18`) y que `0015` cuelga de `0014`
y sube, baja y vuelve a subir sembrando y vaciando las dos series (`TC-29`, fila F4, `CA-R1`).

La fotografía del catálogo y las ayudas siguen el patrón de `test_tkt029a_migracion.py`. La
fotografía incluye disparadores y funciones: en la fila F2 la migración todavía no los crea, y en la
fila F3 sí. Las pruebas están escritas para pasar con las dos versiones de la migración, siempre
que la bajada limpie todo lo que la subida creó (la fotografía C debe ser idéntica a la A).
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
from psycopg.types.json import Jsonb
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    from collections.abc import Callable

    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0013"
REVISION_NUEVA = "0014"
REVISION_SEMILLA = "0015"

SERIES_SEMBRADAS: list[tuple[str, int]] = [("ORDEN_COMPRA", 0), ("REQUISICION", 0)]

TABLAS_COMPRAS: tuple[str, ...] = (
    "requisicion",
    "requisicion_renglon",
    "orden_compra",
    "orden_compra_renglon",
    "solicitud_autorizacion",
    "reprogramacion_entrega",
    "folio_consecutivo",
)
FUNCIONES_COMPRAS: tuple[str, ...] = (
    "compras_proteger_borrado_de_requisicion",
    "compras_proteger_borrado_de_renglon",
)

Fotografia = dict[str, list[tuple[Any, ...]]]

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
    archivo, fila = {
        REVISION_NUEVA: ("v0014_compras_esquema.py", "fila F2"),
        REVISION_SEMILLA: ("v0015_semilla_folios_de_compras.py", "fila F4"),
    }[revision]
    assert revision in conocidas, (
        f"Falta la migración {revision} ({archivo}): Alembic no la conoce "
        f"(TKT-019, {fila}). Revisiones conocidas: {sorted(conocidas)}"
    )


def exigir_tabla(conexion: Conexion, tabla: str) -> None:
    """La precondición de toda prueba que escribe en una tabla de `compras`: que la migración exista."""
    fila = conexion.execute("SELECT to_regclass(%s)", (f"public.{tabla}",)).fetchone()
    assert fila is not None and fila[0] is not None, (
        f"Falta la migración 0014: la tabla `{tabla}` no existe (TKT-019, fila F2)"
    )


def fotografia(conexion: Conexion) -> Fotografia:
    """Todo lo que hay en el esquema `public`, para comparar antes y después de una migración.

    Tablas, columnas (con `ordinal_position`, tipo, longitud, precisión, escala, nulabilidad y valor
    por omisión), restricciones con su definición, índices con su definición, privilegios de cada
    rol incluido `PUBLIC`, disparadores y funciones. Las restricciones `NOT NULL` (`contype = 'n'`)
    no entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad ya viene en
    `columnas`. Copia de `fotografia` de `test_tkt029a_migracion.py`, sin cambios.
    """

    def filas(consulta: str) -> list[tuple[Any, ...]]:
        return [tuple(f) for f in conexion.execute(consulta).fetchall()]  # type: ignore[arg-type]

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


# Posición de la tabla en cada clave de la fotografía: el primer campo salvo en `disparadores`, que
# empieza por el nombre del disparador y trae la tabla en el segundo.
_POSICION_DE_LA_TABLA = {
    "tablas": 0,
    "columnas": 0,
    "restricciones": 0,
    "indices": 0,
    "privilegios": 0,
    "disparadores": 1,
}


def de_compras(foto: Fotografia, clave: str) -> list[tuple[Any, ...]]:
    """Las filas de `foto[clave]` que pertenecen a una de las siete tablas de `compras`."""
    posicion = _POSICION_DE_LA_TABLA[clave]
    return [fila for fila in foto[clave] if fila[posicion] in TABLAS_COMPRAS]


def sin_compras(foto: Fotografia) -> Fotografia:
    """«Lo anterior»: la fotografía sin las siete tablas ni las dos funciones de `compras`.

    El filtro es por igualdad exacta con los nombres, no por prefijo: una tabla anterior que
    cambiara no se escondería detrás de él.
    """
    anterior: Fotografia = {}
    for clave, filas in foto.items():
        if clave == "funciones":
            anterior[clave] = [f for f in filas if f[0] not in FUNCIONES_COMPRAS]
        else:
            posicion = _POSICION_DE_LA_TABLA[clave]
            anterior[clave] = [f for f in filas if f[posicion] not in TABLAS_COMPRAS]
    return anterior


# --------------------------------------------------------------------------- TC-01


def test_tkt019_car1_0014_cuelga_de_0013_y_la_cabeza_es_unica() -> None:
    """TC-01 · CA-R1 — la cadena de migraciones tiene una sola cabeza y `0014` cuelga de `0013`.

    No afirma qué revisión es la cabeza: el siguiente ticket que migre debe poder hacerlo sin tocar
    esta prueba. No usa base de datos. Mismo patrón que `test_tkt029a_car1_0013_cuelga_de_0012_…`.
    """
    guion = guion_de_alembic()
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas

    exigir_revision(REVISION_NUEVA)
    revision = guion.get_revision(REVISION_NUEVA)
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR


# --------------------------------------------------------------------------- TC-02


def test_tkt019_car1_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-02 · CA-R1 — `upgrade 0014`, `downgrade 0013` y `upgrade 0014` dejan lo que deben.

    En `0013` no existe ninguna tabla de `compras` (fotografía A). Tras subir existen las siete
    (fotografía B). Tras bajar, la fotografía es idéntica a A y no queda ninguna columna,
    restricción, índice, privilegio ni disparador de `compras` (C == A); tras volver a subir, es
    idéntica a B (D == B).

    «C == A» exige que la bajada limpie todo lo que la subida creó. En la fila F3, que añade dos
    funciones y dos disparadores, la bajada debe además eliminar las funciones: la fotografía
    incluye `pg_proc` y sin ello C difiriría de A.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]
    for tabla in TABLAS_COMPRAS:
        assert (tabla,) not in a["tablas"], f"La precondición es 0013, sin `{tabla}`"

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        b = fotografia(administrador)
        version_b = version_de_alembic(administrador)
    assert version_b == [(REVISION_NUEVA,)]
    for tabla in TABLAS_COMPRAS:
        assert (tabla,) in b["tablas"], f"Falta `{tabla}` tras subir: {b['tablas']}"
    assert b != a

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        version_c = version_de_alembic(administrador)
        restos = {
            tabla: administrador.execute("SELECT to_regclass(%s)", (f"public.{tabla}",)).fetchone()
            for tabla in TABLAS_COMPRAS
        }
    assert version_c == [(REVISION_ANTERIOR,)]
    assert all(resto == (None,) for resto in restos.values()), (
        f"La bajada debía eliminar las siete tablas: {restos}"
    )
    for clave in _POSICION_DE_LA_TABLA:
        assert de_compras(c, clave) == [], f"La bajada dejó {clave} de `compras`"
    assert c == a

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        d = fotografia(administrador)
        version_d = version_de_alembic(administrador)
    assert version_d == [(REVISION_NUEVA,)]
    assert d == b


# --------------------------------------------------------------------------- TC-03


def test_tkt019_car2_el_esquema_anterior_no_cambia(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-03 · CA-R2 — «lo anterior» de la fotografía de `0013` y de la de `0014` es idéntico.

    «Lo anterior» es la fotografía completa sin las filas de las siete tablas de `compras` (el
    primer campo de cada fila, el segundo en los disparadores) y sin las dos funciones. Tablas,
    columnas, restricciones, índices, privilegios, disparadores y funciones de todo lo que ya
    existía quedan como estaban.

    Compara dos revisiones concretas, como `test_tkt029a_migracion.py`, y no la cabeza: un ticket
    posterior que cambie una tabla antigua con razón no debe romper esta prueba.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        antes = fotografia(administrador)

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        despues = fotografia(administrador)

    # Control: la migración sí cambió algo (si no, la comparación de abajo no probaría nada).
    assert de_compras(despues, "tablas") != []
    anterior_antes = sin_compras(antes)
    anterior_despues = sin_compras(despues)
    for clave in anterior_antes:
        assert anterior_despues[clave] == anterior_antes[clave], (
            f"La migración 0014 cambió algo anterior en `{clave}`"
        )
    assert anterior_despues == anterior_antes


# --------------------------------------------------------------------------- TC-28 (a)


def test_tkt019_car1_la_bajada_se_niega_con_solicitudes_de_autorizacion(
    base_vacia: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto_en: Callable[[str], DatosPresupuesto],
) -> None:
    """TC-28 (a) · CA-R1 · RN-04 · D-18 — con una solicitud, `downgrade 0013` lanza y no borra nada.

    Las solicitudes de autorización son permanentes (`RN-04`): la bajada de `0014` se niega con
    `RAISE EXCEPTION` si la tabla tiene filas, como la de `0003` con la bitácora. La solicitud se
    inserta con el rol de migración sobre `base_vacia` para aislar el mecanismo de la bajada del de
    los privilegios (modelo de datos §13). La versión sigue en `0014` y la solicitud, intacta.

    La parte b (la bajada de `0015` con folios emitidos) es la prueba que sigue.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        exigir_tabla(administrador, "solicitud_autorizacion")
        datos = datos_presupuesto_en(base_vacia)
        usuario = datos.usuario()
        obra = datos.obra(codigo="OB-TC28A")
        solicitud = uuid.uuid4()
        administrador.execute(
            "INSERT INTO solicitud_autorizacion (id, motivo, entidad_tipo, entidad_id, obra_id, "
            "regla_negocio, solicitante_id, rol_autorizador, estado, contexto, creado_en) "
            "VALUES (%s, 'EXCEDE_PRESUPUESTO', 'REQUISICION', %s, %s, 'RN-03', %s, "
            "'DIRECCION_GENERAL', 'PENDIENTE', %s, %s)",
            (
                solicitud,
                uuid.uuid4(),
                obra,
                usuario,
                Jsonb({"disponible": "12000.0000"}),
                datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
            ),
        )

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_vacia, REVISION_ANTERIOR, "downgrade")

    assert "solicitudes de autorización" in str(rechazo.value), str(rechazo.value)
    assert "RN-04" in str(rechazo.value), str(rechazo.value)
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)
        filas = administrador.execute("SELECT id, estado FROM solicitud_autorizacion").fetchall()
    assert version == [(REVISION_NUEVA,)], "La bajada negada debía dejar la versión en 0014"
    assert filas == [(solicitud, "PENDIENTE")], "La solicitud debía seguir ahí, sin cambios"


# --------------------------------------------------------------------------- TC-28 (b)


def series_de_folios(conexion: Conexion) -> list[tuple[Any, ...]]:
    """Las series de `folio_consecutivo` con su último folio, ordenadas por serie."""
    filas = conexion.execute(
        "SELECT serie, ultimo FROM folio_consecutivo ORDER BY serie"
    ).fetchall()
    return [tuple(fila) for fila in filas]


def test_tkt019_car1_la_bajada_de_0015_se_niega_con_folios_emitidos(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-28 (b) · CA-R1 · RN-02 · D-18 — con un folio emitido, `downgrade 0014` lanza y no borra nada.

    Borrar el contador y volver a sembrarlo en cero reutilizaría folios (`RN-02`: los folios no se
    repiten), así que la bajada de `0015` se niega con `RAISE EXCEPTION` si algún `ultimo` es mayor
    que cero. El folio se emite con el rol de migración sobre `base_vacia`, para aislar el mecanismo
    de la bajada del de los privilegios. La versión sigue en `0015` y los contadores, intactos. El
    control positivo (sin folios emitidos, la bajada pasa) lo cubre `TC-29`.
    """
    exigir_revision(REVISION_SEMILLA)
    migrar(base_vacia, REVISION_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        exigir_tabla(administrador, "folio_consecutivo")
        sembradas = series_de_folios(administrador)
        assert sembradas == SERIES_SEMBRADAS, f"La precondición es 0015 sembrada: {sembradas}"
        emitidos = administrador.execute(
            "UPDATE folio_consecutivo SET ultimo = 1 WHERE serie = 'REQUISICION'"
        ).rowcount
        assert emitidos == 1

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_vacia, REVISION_NUEVA, "downgrade")

    assert "Ya se emitieron folios" in str(rechazo.value), str(rechazo.value)
    assert "0015" in str(rechazo.value), str(rechazo.value)
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)
        series = series_de_folios(administrador)
    assert version == [(REVISION_SEMILLA,)], "La bajada negada debía dejar la versión en 0015"
    assert series == [("ORDEN_COMPRA", 0), ("REQUISICION", 1)], (
        "Los contadores debían seguir como estaban, con el folio emitido"
    )


# --------------------------------------------------------------------------- TC-29


def test_tkt019_car1_0015_cuelga_de_0014_y_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-29 · CA-R1 · D-8 — `0015` cuelga de `0014` y siembra, vacía y vuelve a sembrar las series.

    Una sola cabeza y `0015.down_revision == "0014"` (sin afirmar que `0015` sea la cabeza: el
    siguiente ticket que migre no debe romper esta prueba). En `0014`, `folio_consecutivo` está
    vacío; en `0015` tiene exactamente `ORDEN_COMPRA` y `REQUISICION` con `ultimo = 0`; bajar a
    `0014` lo vacía (los contadores están en cero, así que la bajada no se niega); volver a subir lo
    siembra igual.
    """
    guion = guion_de_alembic()
    assert len(guion.get_heads()) == 1, guion.get_heads()
    exigir_revision(REVISION_SEMILLA)
    revision = guion.get_revision(REVISION_SEMILLA)
    assert revision is not None
    assert revision.down_revision == REVISION_NUEVA

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        version_a = version_de_alembic(administrador)
        series_a = series_de_folios(administrador)
    assert version_a == [(REVISION_NUEVA,)]
    assert series_a == [], f"`0014` no siembra nada: {series_a}"

    migrar(base_vacia, REVISION_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        version_b = version_de_alembic(administrador)
        series_b = series_de_folios(administrador)
    assert version_b == [(REVISION_SEMILLA,)]
    assert series_b == SERIES_SEMBRADAS

    migrar(base_vacia, REVISION_NUEVA, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        version_c = version_de_alembic(administrador)
        series_c = series_de_folios(administrador)
        existe = administrador.execute("SELECT to_regclass('public.folio_consecutivo')").fetchone()
    assert version_c == [(REVISION_NUEVA,)]
    assert existe is not None
    assert existe[0] is not None, "La bajada de 0015 solo vacía la tabla: la crea 0014"
    assert series_c == []

    migrar(base_vacia, REVISION_SEMILLA)
    with conectar("migracion", base_vacia) as administrador:
        version_d = version_de_alembic(administrador)
        series_d = series_de_folios(administrador)
    assert version_d == [(REVISION_SEMILLA,)]
    assert series_d == SERIES_SEMBRADAS
