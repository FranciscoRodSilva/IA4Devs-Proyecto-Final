"""TKT-029a · Migración `0013` y tabla `proveedor` (fila A2): TC-04 a TC-07.

`0013` crea `proveedor`, el catálogo de proveedores (modelo de datos §9). La revisión `0012` la
ocupa `archivo` (TKT-059), así que la migración de este ticket cuelga de ella; el diseño, escrito
cuando la cabeza era `0011`, la llamaba `0012` y el orquestador la renumeró en la ejecución.

Este archivo prueba lo que el motor sostiene por su cuenta, sin pasar por ningún caso de uso: que
la cadena sigue siendo lineal y `0013` cuelga de `0012` (`TC-04`, `CA-R1`), que la migración sube,
baja y vuelve a subir sin dejar rastro (`TC-05`, `CA-R1`), que el motor rechaza con la restricción
nombrada lo que el API dejara pasar (`TC-06`, `CA-11`, invariantes 8 y 28) y que el rol de
aplicación no puede borrar proveedores (`TC-07`, `CA-10` esc. 2, `D-4`).

Los datos se escriben con el rol de aplicación, que es quien los escribe en producción. La
migración y el catálogo los ejecuta y lee el rol de migración. La fotografía del catálogo y las
ayudas siguen el patrón de `test_tkt059_migracion.py`.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0012"
REVISION_NUEVA = "0013"

CREADO_EN = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)
RFC_BASE = "XAXX010101000"
ESTADOS_ADMITIDOS = {"ACTIVO", "DESACTIVADO", "BAJA"}

# Nombre -> tipo de restricción de `pg_constraint.contype`: las seis del diseño, ni una más.
RESTRICCIONES: dict[str, str] = {
    "pk_proveedor": "p",
    "fk_proveedor_creado_por_id": "f",
    "uq_proveedor_rfc": "u",
    "ck_proveedor_estado": "c",
    "ck_proveedor_tope_consignacion_no_negativo": "c",
    "ck_proveedor_dias_semana_rango": "c",
}

# Nombre, tipo, precisión numérica, escala, nulable, valor por omisión exacto (None: sin valor por
# omisión). El orden es el del diseño («Infraestructura y esquema»).
COLUMNAS: tuple[tuple[str, str, int | None, int | None, str, str | None], ...] = (
    ("id", "uuid", None, None, "NO", None),
    ("nombre", "text", None, None, "NO", None),
    ("rfc", "text", None, None, "NO", None),
    ("estado", "text", None, None, "NO", None),
    ("tope_consignacion", "numeric", 18, 4, "YES", None),
    ("dia_corte", "smallint", 16, 0, "NO", "4"),
    ("dia_pago", "smallint", 16, 0, "NO", "6"),
    ("creado_en", "timestamp with time zone", None, None, "NO", None),
    ("creado_por_id", "uuid", None, None, "NO", None),
)

# --------------------------------------------------------------------------- ayudas


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def exigir_tabla_proveedor(conexion: Conexion) -> None:
    """La precondición de toda prueba que escribe en `proveedor`: que la migración `0013` exista."""
    fila = conexion.execute("SELECT to_regclass('public.proveedor')").fetchone()
    assert fila is not None and fila[0] is not None, (
        "Falta la migración 0013: la tabla `proveedor` no existe (TKT-029a, fila A2)"
    )


def guion_de_alembic() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))


def exigir_revision_nueva() -> None:
    """La cadena de Alembic debe conocer la revisión `0013` antes de intentar migrar hasta ella.

    `get_revision` lanza `ResolutionError` si no existe; recorrer la cadena da un fallo de
    aserción con el motivo escrito, que es la razón esperada del rojo.
    """
    conocidas = {revision.revision for revision in guion_de_alembic().walk_revisions()}
    assert REVISION_NUEVA in conocidas, (
        "Falta la migración 0013 (v0013_proveedores_catalogo.py): Alembic no la conoce "
        f"(TKT-029a, fila A2). Revisiones conocidas: {sorted(conocidas)}"
    )


def fotografia(conexion: Conexion) -> dict[str, list[tuple[Any, ...]]]:
    """Todo lo que hay en el esquema `public`, para comparar antes y después de una migración.

    Tablas, columnas (con `ordinal_position`, tipo, longitud, precisión, escala, nulabilidad y valor
    por omisión), restricciones con su definición, índices con su definición, privilegios de cada
    rol incluido `PUBLIC`, disparadores y funciones. Las restricciones `NOT NULL` (`contype = 'n'`)
    no entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad ya viene en
    `columnas`.
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


def de_proveedor(foto: dict[str, list[tuple[Any, ...]]], clave: str) -> list[tuple[Any, ...]]:
    """Las filas de `foto[clave]` que pertenecen a la tabla `proveedor` (la tabla es el primer campo)."""
    return [fila for fila in foto[clave] if fila[0] == "proveedor"]


def fila_valida(usuario_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Un proveedor `ACTIVO` que cumple todo; `cambios` pisa columnas. Sin días: decide el motor."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "nombre": "CoPanel",
        "rfc": RFC_BASE,
        "estado": "ACTIVO",
        "creado_en": CREADO_EN,
        "creado_por_id": usuario_id,
    }
    valores.update(cambios)
    return valores


def insertar(conexion: Conexion, valores: dict[str, Any]) -> None:
    conexion.execute(
        sql.SQL("INSERT INTO proveedor ({}) VALUES ({})").format(
            sql.SQL(", ").join(sql.Identifier(columna) for columna in valores),
            sql.SQL(", ").join(sql.Placeholder() for _ in valores),
        ),
        list(valores.values()),
    )


def contar(conexion: Conexion) -> int:
    fila = conexion.execute("SELECT count(*) FROM proveedor").fetchone()
    assert fila is not None
    return int(fila[0])


def filas_de_proveedor(conexion: Conexion) -> list[str]:
    return [
        str(f[0])
        for f in conexion.execute("SELECT p::text FROM proveedor p ORDER BY p.id").fetchall()
    ]


# --------------------------------------------------------------------------- TC-04


def test_tkt029a_car1_0013_cuelga_de_0012_y_la_cabeza_es_unica() -> None:
    """TC-04 · CA-R1 — la cadena de migraciones tiene una sola cabeza y `0013` cuelga de `0012`.

    No afirma qué revisión es la cabeza: el siguiente ticket que migre debe poder hacerlo sin tocar
    esta prueba. No usa base de datos. Mismo patrón que `test_tkt011_car4_…`.
    """
    guion = guion_de_alembic()
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas

    exigir_revision_nueva()
    revision = guion.get_revision(REVISION_NUEVA)
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR


# --------------------------------------------------------------------------- TC-05


def _comprobar_columnas(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    columnas = de_proveedor(foto, "columnas")
    # (tabla, posición, nombre, tipo, longitud, precisión, escala, nulable, valor por omisión)
    assert [(c[1], c[2]) for c in columnas] == [(i + 1, e[0]) for i, e in enumerate(COLUMNAS)], (
        f"Las columnas y su orden no son los del diseño: {[c[2] for c in columnas]}"
    )
    for real, (nombre, tipo, precision, escala, nulable, omision) in zip(
        columnas, COLUMNAS, strict=True
    ):
        assert real[3] == tipo, f"{nombre}: tipo {real[3]}, esperaba {tipo}"
        assert real[4] is None, f"{nombre}: no debe tener longitud máxima, tiene {real[4]}"
        assert real[5] == precision, f"{nombre}: precisión {real[5]}, esperaba {precision}"
        assert real[6] == escala, f"{nombre}: escala {real[6]}, esperaba {escala}"
        assert real[7] == nulable, f"{nombre}: is_nullable {real[7]}, esperaba {nulable}"
        if omision is None:
            assert real[8] is None, f"{nombre}: no debe tener valor por omisión, tiene {real[8]}"
        else:
            assert real[8] is not None and re.fullmatch(
                rf"\(?{omision}\)?(::smallint)?", str(real[8])
            ), f"{nombre}: el valor por omisión era {real[8]} y debía ser {omision}"


def _comprobar_restricciones(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    restricciones = {str(f[1]): (str(f[2]), str(f[3])) for f in de_proveedor(foto, "restricciones")}
    assert {nombre: tipo for nombre, (tipo, _) in restricciones.items()} == RESTRICCIONES, (
        f"Las restricciones no son las seis del diseño: {sorted(restricciones)}"
    )

    definicion = {nombre: texto for nombre, (_, texto) in restricciones.items()}
    assert "PRIMARY KEY (id)" in definicion["pk_proveedor"], definicion["pk_proveedor"]
    llave = definicion["fk_proveedor_creado_por_id"]
    assert "FOREIGN KEY (creado_por_id) REFERENCES usuario(id)" in llave, llave
    assert "ON DELETE RESTRICT" in llave, llave
    assert "UNIQUE (rfc)" in definicion["uq_proveedor_rfc"], definicion["uq_proveedor_rfc"]
    estado = definicion["ck_proveedor_estado"]
    assert set(re.findall(r"'([A-Z_]+)'", estado)) == ESTADOS_ADMITIDOS, estado
    tope = definicion["ck_proveedor_tope_consignacion_no_negativo"]
    assert "tope_consignacion >= " in tope, tope
    dias = definicion["ck_proveedor_dias_semana_rango"]
    for columna in ("dia_corte", "dia_pago"):
        assert f"{columna} >= 1" in dias and f"{columna} <= 7" in dias, (
            f"{columna} debía acotarse entre 1 y 7 en {dias}"
        )


def test_tkt029a_car1_sube_baja_y_vuelve_a_subir(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-05 · CA-R1 — `upgrade 0013`, `downgrade 0012` y `upgrade 0013` dejan lo que deben.

    En `0012` no existe `proveedor` (fotografía A). Tras subir existen sus nueve columnas con su
    tipo, su nulabilidad y su valor por omisión (4 y 6 en los días) y las seis restricciones con
    nombre. Tras bajar, la fotografía es idéntica a A y no queda tabla ni restricción de
    `proveedor`; tras volver a subir, idéntica a la primera subida.
    """
    exigir_revision_nueva()
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        version_a = version_de_alembic(administrador)
        antes = administrador.execute("SELECT to_regclass('public.proveedor')").fetchone()
    assert version_a == [(REVISION_ANTERIOR,)]
    assert antes == (None,), "La precondición es el esquema de 0012, sin `proveedor`"
    assert ("proveedor",) not in a["tablas"]

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        b = fotografia(administrador)
        version_b = version_de_alembic(administrador)
    assert version_b == [(REVISION_NUEVA,)]
    assert ("proveedor",) in b["tablas"], b["tablas"]
    _comprobar_columnas(b)
    _comprobar_restricciones(b)

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        version_c = version_de_alembic(administrador)
        tras_bajar = administrador.execute("SELECT to_regclass('public.proveedor')").fetchone()
    assert version_c == [(REVISION_ANTERIOR,)]
    assert tras_bajar == (None,), "La bajada debía eliminar la tabla `proveedor`"
    for clave in ("columnas", "restricciones", "indices", "privilegios"):
        assert de_proveedor(c, clave) == [], f"La bajada dejó {clave} de `proveedor`"
    assert c == a

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        d = fotografia(administrador)
        version_d = version_de_alembic(administrador)
    assert version_d == [(REVISION_NUEVA,)]
    assert d == b


# --------------------------------------------------------------------------- TC-06

_RFC_AJENO = "ABC010101AB1"


@pytest.mark.parametrize(
    ("cambios", "repite_rfc", "rechazo"),
    [
        pytest.param(
            {"rfc": RFC_BASE},
            True,
            ("23505", "uq_proveedor_rfc"),
            id="rfc_repetido",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "estado": "OTRO"},
            False,
            ("23514", "ck_proveedor_estado"),
            id="estado_fuera_del_conjunto",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "tope_consignacion": Decimal("-0.0001")},
            False,
            ("23514", "ck_proveedor_tope_consignacion_no_negativo"),
            id="tope_negativo",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_corte": 0},
            False,
            ("23514", "ck_proveedor_dias_semana_rango"),
            id="dia_corte_0",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_corte": 8},
            False,
            ("23514", "ck_proveedor_dias_semana_rango"),
            id="dia_corte_8",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_pago": 0},
            False,
            ("23514", "ck_proveedor_dias_semana_rango"),
            id="dia_pago_0",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_pago": 8},
            False,
            ("23514", "ck_proveedor_dias_semana_rango"),
            id="dia_pago_8",
        ),
        # Controles positivos: sin ellos, un `CHECK` que rechaza todo pasaría igual.
        pytest.param(
            {"rfc": _RFC_AJENO, "estado": "BAJA"}, False, None, id="estado_baja_se_admite"
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "tope_consignacion": Decimal("0.0000")},
            False,
            None,
            id="tope_cero_se_admite",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "tope_consignacion": Decimal("300000.0000")},
            False,
            None,
            id="tope_positivo_se_admite",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_corte": 1, "dia_pago": 7},
            False,
            None,
            id="dias_1_y_7_se_admiten",
        ),
        pytest.param(
            {"rfc": _RFC_AJENO, "dia_corte": 7, "dia_pago": 1},
            False,
            None,
            id="dias_7_y_1_se_admiten",
        ),
    ],
)
def test_tkt029a_ca11_el_motor_rechaza_con_la_restriccion_nombrada(
    cambios: dict[str, Any],
    repite_rfc: bool,
    rechazo: tuple[str, str] | None,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-06 · CA-11 · invariantes 8 y 28 — el motor rechaza lo que el API dejara pasar.

    Con el rol de aplicación: un RFC repetido (`23505`, `uq_proveedor_rfc`); un estado fuera de los
    tres valores, un tope negativo y un día fuera de 1 a 7 en `dia_corte` o en `dia_pago` (`23514`,
    cada uno con su `CHECK`). Cada rechazo trae su `SQLSTATE` y el nombre de la restricción
    (`diag.constraint_name`) y no deja fila. El estado `BAJA`, el tope cero y positivo y los días 1
    y 7 se admiten: son los bordes de cada restricción.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_proveedor(aplicacion)
    usuario = datos_presupuesto.usuario()
    previas = 0
    if repite_rfc:
        insertar(aplicacion, fila_valida(usuario, nombre="Existente"))
        previas = 1
    assert contar(aplicacion) == previas

    valores = fila_valida(usuario, **cambios)
    if rechazo is None:
        insertar(aplicacion, valores)
        assert contar(aplicacion) == previas + 1
        return

    sqlstate, restriccion = rechazo
    with pytest.raises(psycopg.Error) as error:
        insertar(aplicacion, valores)

    assert error.value.sqlstate == sqlstate, str(error.value)
    assert error.value.diag.constraint_name == restriccion, str(error.value)
    assert contar(aplicacion) == previas, "El rechazo no debe dejar ninguna fila"


def test_tkt029a_ca11_sin_dias_el_motor_pone_4_y_6(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-06 (control positivo) · CA-11 · `RN-17` — un `INSERT` sin días entra con corte 4 y pago 6.

    El valor por omisión lo decide el motor: la fila no nombra `dia_corte` ni `dia_pago`. Además
    `tope_consignacion` queda en `NULL` (anulable) y el estado y el RFC se guardan como se dieron.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_proveedor(aplicacion)
    valores = fila_valida(datos_presupuesto.usuario())
    assert "dia_corte" not in valores and "dia_pago" not in valores
    insertar(aplicacion, valores)

    fila = aplicacion.execute(
        "SELECT estado, rfc, dia_corte, dia_pago, tope_consignacion FROM proveedor WHERE id = %s",
        (valores["id"],),
    ).fetchone()
    assert fila == ("ACTIVO", RFC_BASE, 4, 6, None)


# --------------------------------------------------------------------------- TC-07


def _privilegios(conexion: Conexion, rol: str) -> set[str]:
    """Conjunto de `privilege_type` que `relacl` de `proveedor` concede al rol; vacío si ninguno."""
    filas = conexion.execute(
        "SELECT a.privilege_type FROM pg_class c "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "JOIN pg_roles g ON g.oid = a.grantee "
        "WHERE c.oid = to_regclass('public.proveedor') AND g.rolname = %s",
        (f"cimenta_{rol}",),
    ).fetchall()
    return {str(fila[0]) for fila in filas}


def test_tkt029a_ca10_el_rol_de_aplicacion_no_borra_proveedores(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-07 · CA-10 esc. 2 · `D-4` — el rol de aplicación no puede borrar filas de `proveedor`.

    Por `aclexplode(relacl)`, la aplicación tiene exactamente `SELECT, INSERT, UPDATE` (ni `DELETE`
    ni `TRUNCATE`), la lectura exactamente `SELECT` y `PUBLIC` nada. Un `DELETE` real con el rol de
    aplicación responde `42501` (privilegio insuficiente) y la fila sigue idéntica. Los privilegios
    por omisión de `0001` conceden `DELETE` a toda tabla nueva: lo quita el `REVOKE` de la
    migración.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_proveedor(aplicacion)
    with conectar("migracion", base_de_prueba) as administrador:
        de_aplicacion = _privilegios(administrador, "aplicacion")
        de_lectura = _privilegios(administrador, "lectura")
        de_public = administrador.execute(
            "SELECT count(*) FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "WHERE c.oid = to_regclass('public.proveedor') AND a.grantee = 0"
        ).fetchone()
    assert de_aplicacion == {"SELECT", "INSERT", "UPDATE"}, de_aplicacion
    assert de_lectura == {"SELECT"}, de_lectura
    assert de_public == (0,), "Ningún privilegio para PUBLIC"

    valores = fila_valida(datos_presupuesto.usuario())
    insertar(aplicacion, valores)
    antes = filas_de_proveedor(aplicacion)
    assert len(antes) == 1

    with pytest.raises(psycopg.Error) as error:
        aplicacion.execute("DELETE FROM proveedor WHERE id = %s", (valores["id"],))

    assert error.value.sqlstate == "42501", str(error.value)
    assert "proveedor" in str(error.value), str(error.value)
    assert filas_de_proveedor(aplicacion) == antes, "La fila debía seguir ahí, sin cambios"
