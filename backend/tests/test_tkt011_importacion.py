"""Importación y rendimiento observado de TKT-011b, fila B5: `importacion`, `importacion_error` y `rendimiento_observado`.

La migración `0007` crea las tres tablas. La importación identifica el archivo con un `uuid` lógico
sin clave foránea (`CA-7`), su progreso va de 0 a 1 (`CA-14`) y el error de una hoja sin conceptos
no tiene fila ni columna (`CA-9`). `rendimiento_observado` nace vacío, sin escritor y sin
relación con `explosion_presupuesto` (`CA-10`, `RN-24`).

Este archivo cubre TC-26, TC-27, TC-30, TC-31, TC-32 y TC-34, y el borde de `divergencia_pct` de
TC-33. La forma de las tablas (TC-20), los conjuntos cerrados (TC-28 y TC-29) y la no negatividad
(TC-33) recorren las tablas de datos de `test_tkt011_linea_base.py`.

PostgreSQL real, esquema por `alembic upgrade head` y rol de aplicación para escribir. Las pruebas
de catálogo se conectan con el rol de migración, que es quien lee `pg_catalog` sin restricción.
Toda consulta a `pg_constraint` excluye `contype = 'n'`: PostgreSQL 18 guarda los `NOT NULL` como
restricciones, y no son claves foráneas ni restricciones de la columna que se pregunta.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]

# --------------------------------------------------------------------------- ayudas


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def fotografia(conexion: Conexion, tabla: str) -> list[tuple[Any, ...]]:
    """Todas las filas de una tabla en un orden fijo, para comprobar que una escritura ajena no cambió nada."""
    filas = conexion.execute(
        sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(tabla))
    ).fetchall()
    return [tuple(fila) for fila in filas]


def afirmar_rechazo(error: psycopg.Error, sqlstate: str, restriccion: str, tabla: str) -> None:
    """Un rechazo de restricción: el `SQLSTATE`, el nombre de la restricción y la tabla."""
    assert error.sqlstate == sqlstate
    assert error.diag.constraint_name == restriccion
    assert error.diag.table_name == tabla


def columnas_de(conexion: Conexion, tabla: str) -> list[tuple[Any, ...]]:
    """(columna, tipo, precisión, escala, ¿admite nulo?) de la tabla, por orden de nombre."""
    filas = conexion.execute(
        "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable "
        "FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY column_name",
        (tabla,),
    ).fetchall()
    return [tuple(fila) for fila in filas]


# --------------------------------------------------------------------------- TC-26


def test_tkt011_ca07_importacion_sin_clave_foranea_al_archivo(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-26 · CA-7 esc. 1 · RNF-17 — `archivo_id` es `uuid` y ninguna restricción lo toca; el archivo no se guarda en la tabla."""
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = columnas_de(migracion, "importacion")
        assert columnas, "La tabla importacion no existe: la migración 0007 no la crea."

        archivo = [fila for fila in columnas if fila[0] == "archivo_id"]
        restricciones_del_archivo = migracion.execute(
            "SELECT c.conname, c.contype FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey) "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = 'importacion' "
            "AND a.attname = 'archivo_id' AND c.contype <> 'n'"
        ).fetchall()
        claves_foraneas = migracion.execute(
            "SELECT c.conname, r.relname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_class r ON r.oid = c.confrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = 'importacion' "
            "AND c.contype = 'f' ORDER BY c.conname"
        ).fetchall()

    assert archivo == [("archivo_id", "uuid", None, None, "NO")]
    assert [tuple(fila) for fila in restricciones_del_archivo] == []
    # Las únicas claves foráneas de la importación son la obra y el usuario: ninguna al archivo.
    assert [tuple(fila) for fila in claves_foraneas] == [
        ("fk_importacion_importado_por_id", "usuario"),
        ("fk_importacion_obra_id", "obra"),
    ]


def test_tkt011_ca07_importacion_sin_columnas_de_nombre_ni_de_url(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-26 · CA-7 esc. 1 · ADR-016 — la importación no guarda el nombre ni la URL del archivo."""
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = columnas_de(migracion, "importacion")
        assert columnas, "La tabla importacion no existe: la migración 0007 no la crea."

        indebidas = migracion.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'importacion' "
            "AND (column_name ILIKE '%nombre%' OR column_name ILIKE '%url%') "
            "ORDER BY column_name"
        ).fetchall()

    assert [tuple(fila) for fila in indebidas] == []


def test_tkt011_ca07_latido_y_progreso_con_su_tipo_y_admiten_nulo(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-26 · CA-7 esc. 1 · RNF-17 — `latido` es `timestamptz` nulable y `progreso`, `numeric(9,6)` nulable."""
    with conectar("migracion", base_de_prueba) as migracion:
        columnas = columnas_de(migracion, "importacion")
    assert columnas, "La tabla importacion no existe: la migración 0007 no la crea."

    por_nombre = {fila[0]: fila for fila in columnas}
    assert por_nombre.get("latido") == ("latido", "timestamp with time zone", None, None, "YES")
    assert por_nombre.get("progreso") == ("progreso", "numeric", 9, 6, "YES")


# --------------------------------------------------------------------------- TC-27


def test_tkt011_ca07_archivo_inexistente_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-27 · CA-7 esc. 2 — una importación con un `archivo_id` que no corresponde a ninguna fila entra y lo conserva."""
    archivo_inexistente = uuid.uuid4()

    identificador = datos_presupuesto.importacion(archivo_id=archivo_inexistente)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT archivo_id, estado, progreso, latido FROM importacion WHERE id = %s",
            (identificador,),
        ).fetchone()
    assert guardado == (archivo_inexistente, "RECIBIDO", None, None)


# --------------------------------------------------------------------------- TC-30


def test_tkt011_ca09_sin_conceptos_sin_fila_ni_columna(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-30 · CA-9 · HDU-001 esc. 27 — un error `SIN_CONCEPTOS` con `fila` y `columna` nulas entra y las conserva nulas."""
    importacion = datos_presupuesto.importacion(estado="CON_ERRORES")

    identificador = datos_presupuesto.error_importacion(
        importacion_id=importacion,
        hoja="Resumen",
        fila=None,
        columna=None,
        tipo="SIN_CONCEPTOS",
        mensaje="La hoja no tiene conceptos.",
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT importacion_id, hoja, fila, columna, tipo, mensaje, valor_original "
            "FROM importacion_error WHERE id = %s",
            (identificador,),
        ).fetchone()
    assert guardado == (
        importacion,
        "Resumen",
        None,
        None,
        "SIN_CONCEPTOS",
        "La hoja no tiene conceptos.",
        None,
    )


def test_tkt011_ca09_error_sin_mensaje_lo_rechaza_not_null(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-30 · CA-9 · HDU-001 esc. 27 — `mensaje` sigue siendo obligatorio: un error sin él responde `23502` y no deja fila."""
    importacion = datos_presupuesto.importacion(estado="CON_ERRORES")

    with pytest.raises(psycopg.errors.NotNullViolation) as rechazo:
        datos_presupuesto.error_importacion(
            importacion_id=importacion, tipo="SIN_CONCEPTOS", fila=None, columna=None, mensaje=None
        )

    assert rechazo.value.sqlstate == "23502"
    assert rechazo.value.diag.column_name == "mensaje"
    assert rechazo.value.diag.table_name == "importacion_error"
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "importacion_error") == 0
        assert contar(aplicacion, "importacion") == 1


# --------------------------------------------------------------------------- TC-31


def test_tkt011_ca10_rendimiento_observado_vacio_y_separado(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-31 · CA-10 esc. 1 · RN-24 · invariante 19 — la tabla existe, está vacía, no se une a la explosión y el congelado no se calcula de ella."""
    with conectar("migracion", base_de_prueba) as migracion:
        tipos = migracion.execute(
            "SELECT relname, relkind FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace "
            "AND relname IN ('explosion_presupuesto', 'rendimiento_observado') ORDER BY relname"
        ).fetchall()
        assert [tuple(fila) for fila in tipos] == [
            ("explosion_presupuesto", "r"),
            ("rendimiento_observado", "r"),
        ], "Las dos deben ser tablas ordinarias (relkind = 'r'), no vistas."

        filas = contar(migracion, "rendimiento_observado")
        claves_entre_las_dos = migracion.execute(
            "SELECT t.relname, r.relname, c.conname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_class r ON r.oid = c.confrelid "
            "WHERE c.contype = 'f' AND t.relnamespace = 'public'::regnamespace "
            "AND ((t.relname = 'rendimiento_observado' AND r.relname = 'explosion_presupuesto') "
            "  OR (t.relname = 'explosion_presupuesto' AND r.relname = 'rendimiento_observado'))"
        ).fetchall()
        generadas = migracion.execute(
            "SELECT t.relname, a.attname, a.attgenerated FROM pg_attribute a "
            "JOIN pg_class t ON t.oid = a.attrelid "
            "WHERE t.relnamespace = 'public'::regnamespace "
            "AND t.relname IN ('explosion_presupuesto', 'rendimiento_observado') "
            "AND a.attname = 'rendimiento_congelado' AND NOT a.attisdropped ORDER BY t.relname"
        ).fetchall()

    assert filas == 0
    assert [tuple(fila) for fila in claves_entre_las_dos] == []
    assert [tuple(fila) for fila in generadas] == [
        ("explosion_presupuesto", "rendimiento_congelado", ""),
        ("rendimiento_observado", "rendimiento_congelado", ""),
    ]


# --------------------------------------------------------------------------- TC-32


def test_tkt011_ca10_escribir_el_observado_no_toca_la_explosion(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-32 · CA-10 esc. 2 · RN-24 — insertar en `rendimiento_observado` deja `explosion_presupuesto` igual, incluso para el mismo insumo."""
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        antes = fotografia(aplicacion, "explosion_presupuesto")
    assert len(antes) == 1, (
        "La preparación debe dejar un renglón: sin él la comparación no dice nada."
    )

    datos_presupuesto.rendimiento_observado(
        obra_id=copias.obra_id,
        insumo_id=copias.insumo_id,
        rendimiento=Decimal("0.750000"),
        rendimiento_congelado=Decimal("0.500000"),
        divergencia_pct=Decimal("0.500000"),
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        despues = fotografia(aplicacion, "explosion_presupuesto")
        observadas = aplicacion.execute(
            "SELECT insumo_id, rendimiento FROM rendimiento_observado"
        ).fetchall()
    assert despues == antes
    assert observadas == [(copias.insumo_id, Decimal("0.750000"))]


# --------------------------------------------------------------------------- TC-33 · borde


def test_tkt011_ca13_la_divergencia_puede_ser_negativa(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-33 · CA-13 · RN-24 — `divergencia_pct` no lleva `CHECK` de no negatividad: una cuadrilla mejor que lo presupuestado da negativo."""
    identificador = datos_presupuesto.rendimiento_observado(
        rendimiento=Decimal("0.400000"),
        rendimiento_congelado=Decimal("0.500000"),
        divergencia_pct=Decimal("-0.200000"),
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT divergencia_pct FROM rendimiento_observado WHERE id = %s", (identificador,)
        ).fetchone()
    assert guardado == (Decimal("-0.200000"),)


# --------------------------------------------------------------------------- TC-34

PROGRESOS_ADMITIDOS: list[Decimal | None] = [
    None,
    Decimal("0.000000"),
    Decimal("0.500000"),
    Decimal("1.000000"),
]
PROGRESOS_RECHAZADOS = [Decimal("1.000001"), Decimal("-0.000001")]


@pytest.mark.parametrize(
    "progreso", PROGRESOS_ADMITIDOS, ids=[str(progreso) for progreso in PROGRESOS_ADMITIDOS]
)
def test_tkt011_ca14_progreso_de_cero_a_uno_se_acepta(
    progreso: Decimal | None,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-34 · CA-14 · PA-02 · RNF-17 — `progreso` nulo, `0`, `0.5` y `1.000000` (los dos bordes) entran y se guardan tal cual."""
    identificador = datos_presupuesto.importacion(progreso=progreso)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT progreso FROM importacion WHERE id = %s", (identificador,)
        ).fetchone()
    assert guardado == (progreso,)


@pytest.mark.parametrize(
    "progreso", PROGRESOS_RECHAZADOS, ids=[str(progreso) for progreso in PROGRESOS_RECHAZADOS]
)
def test_tkt011_ca14_progreso_fuera_de_cero_a_uno_lo_rechaza_la_base(
    progreso: Decimal,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-34 · CA-14 · PA-02 · RNF-17 — `1.000001` y `-0.000001` responden `23514` con `ck_importacion_progreso_rango` y no dejan fila."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        datos_presupuesto.importacion(progreso=progreso)

    afirmar_rechazo(rechazo.value, "23514", "ck_importacion_progreso_rango", "importacion")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "importacion") == 0
