"""Línea base de TKT-011b, filas B1 a B5: `linea_base`, sus copias, el control y los disparadores del invariante 14.

La migración `0007` crea `linea_base`, con `ck_linea_base_estado`,
`ck_linea_base_importe_venta_no_negativo`, el índice único parcial `uq_linea_base_obra_id_congelada`
y `trg_linea_base_solo_avanza` (fila B1), y las copias `linea_base_concepto` y
`explosion_presupuesto` con `uq_explosion_presupuesto_linea_tipo_insumo` y los disparadores
`trg_linea_base_concepto_inmutable` y `trg_explosion_presupuesto_inmutable` (fila B2). Todos
imponen el invariante 14 (`RN-01`). La fila B3 añade `presupuesto_control` con
`uq_presupuesto_control_linea_base_id_tipo_partida_id`; la fila B5, `importacion`,
`importacion_error` y `rendimiento_observado`.

Este archivo cubre TC-20, TC-21 a TC-25, TC-28, TC-29, TC-33, TC-35 a TC-42 y TC-C2, y la
medición E-13. `TABLAS_DE_NULABILIDAD`, `CON_ZONA_HORARIA`, `FUERA_DEL_CONJUNTO`, `ADMITIDOS` y
`NO_NEGATIVOS` son tablas de datos que recorren las pruebas y abarcan las siete tablas de `0007`
y, en `FUERA_DEL_CONJUNTO`, las filas de `CA-8` de `0006`. `test_tkt011_importacion.py` cubre el
resto de la importación y del rendimiento observado (TC-26, TC-27, TC-30 a TC-32 y TC-34).

PostgreSQL real, esquema por `alembic upgrade head` y rol de aplicación para escribir. Las pruebas de
`CA-16` se conectan con el rol de **migración**, a propósito: con el de aplicación el privilegio
podría rechazar antes y la prueba quedaría verde sin haber tocado el disparador. El rechazo del
disparador se afirma por su `SQLSTATE` propio, `IN001`; el prefijo `RN-01:` del mensaje; el nombre
del disparador en `diag.constraint_name`; la tabla en `diag.table_name`; y que la fila no cambió.

`TABLAS_DE_NULABILIDAD` es copia literal de la «Tabla de nulabilidad» de
`sdd/tickets/tkt-011/design.md` (`PA-T10`).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import Conectar, CopiasDeLineaBase, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]
Crear = Callable[["DatosPresupuesto"], uuid.UUID]

CODIGO_DEL_DISPARADOR = "IN001"
PREFIJO_DEL_MENSAJE = "RN-01:"
DISPARADOR_DE_LINEA_BASE = "trg_linea_base_solo_avanza"
# El disparador de cada tabla de copias del invariante 14 (fila B2).
DISPARADOR_DE_COPIAS = {
    "linea_base_concepto": "trg_linea_base_concepto_inmutable",
    "explosion_presupuesto": "trg_explosion_presupuesto_inmutable",
}
TABLAS_DE_COPIAS = tuple(DISPARADOR_DE_COPIAS)

# --------------------------------------------------------------------------- la forma esperada

# (columna, tipo, ¿admite nulo?, valor por omisión), tal como lo dice la tabla de nulabilidad.
FilaDeTabla = tuple[str, str, str, str | None]

# `information_schema.columns` entrega, para cada tipo del diseño, estas tres cifras.
TIPOS: dict[str, tuple[str, int | None, int | None]] = {
    "uuid": ("uuid", None, None),
    "text": ("text", None, None),
    "jsonb": ("jsonb", None, None),
    "timestamptz": ("timestamp with time zone", None, None),
    "integer": ("integer", 32, 0),
    "numeric(9,6)": ("numeric", 9, 6),
    "numeric(14,4)": ("numeric", 14, 4),
    "numeric(18,4)": ("numeric", 18, 4),
    "numeric(18,6)": ("numeric", 18, 6),
}

# Las siete tablas de `0007`: `linea_base` (B1), las dos copias (B2), `presupuesto_control` (B3) y
# `importacion`, `importacion_error` y `rendimiento_observado` (B5).
TABLAS_DE_NULABILIDAD: dict[str, tuple[FilaDeTabla, ...]] = {
    "linea_base": (
        ("id", "uuid", "no", None),
        ("obra_id", "uuid", "no", None),
        ("version", "integer", "no", None),
        ("estado", "text", "no", None),
        ("congelada_en", "timestamptz", "sí", None),
        ("congelada_por_id", "uuid", "sí", None),
        ("motivo", "text", "sí", None),
        ("importe_venta", "numeric(18,4)", "no", None),
        ("creado_en", "timestamptz", "no", "now()"),
        ("creado_por_id", "uuid", "no", None),
    ),
    "linea_base_concepto": (
        ("id", "uuid", "no", None),
        ("linea_base_id", "uuid", "no", None),
        ("concepto_id", "uuid", "no", None),
        ("codigo", "text", "no", None),
        ("cantidad", "numeric(14,4)", "no", None),
        ("precio_unitario", "numeric(14,4)", "no", None),
        ("importe", "numeric(18,4)", "no", None),
    ),
    "explosion_presupuesto": (
        ("id", "uuid", "no", None),
        ("linea_base_id", "uuid", "no", None),
        ("tipo_partida_id", "uuid", "no", None),
        ("insumo_id", "uuid", "no", None),
        ("cantidad_presupuestada", "numeric(14,4)", "no", None),
        ("rendimiento_congelado", "numeric(18,6)", "no", None),
        ("costo_unitario", "numeric(14,4)", "no", None),
        ("importe_venta", "numeric(18,4)", "no", None),
    ),
    "presupuesto_control": (
        ("id", "uuid", "no", None),
        ("linea_base_id", "uuid", "no", None),
        ("tipo_partida_id", "uuid", "no", None),
        ("importe_tope", "numeric(18,4)", "sí", None),
        ("importe_sugerido", "numeric(18,4)", "no", None),
        ("capturado_por_id", "uuid", "sí", None),
        ("capturado_en", "timestamptz", "sí", None),
        ("actualizado_por_id", "uuid", "sí", None),
        ("actualizado_en", "timestamptz", "sí", None),
        ("motivo_ultimo_cambio", "text", "sí", None),
    ),
    "importacion": (
        ("id", "uuid", "no", None),
        ("obra_id", "uuid", "no", None),
        ("archivo_id", "uuid", "no", None),
        ("estado", "text", "no", None),
        ("progreso", "numeric(9,6)", "sí", None),
        ("filas_leidas", "integer", "sí", None),
        ("filas_validas", "integer", "sí", None),
        ("filas_rechazadas", "integer", "sí", None),
        ("preparacion", "jsonb", "sí", None),
        ("resumen", "jsonb", "sí", None),
        ("importado_por_id", "uuid", "no", None),
        ("creado_en", "timestamptz", "no", "now()"),
        ("latido", "timestamptz", "sí", None),
    ),
    "importacion_error": (
        ("id", "uuid", "no", None),
        ("importacion_id", "uuid", "no", None),
        ("hoja", "text", "sí", None),
        ("fila", "integer", "sí", None),
        ("columna", "text", "sí", None),
        ("tipo", "text", "no", None),
        ("mensaje", "text", "no", None),
        ("valor_original", "text", "sí", None),
    ),
    "rendimiento_observado": (
        ("id", "uuid", "no", None),
        ("obra_id", "uuid", "no", None),
        ("insumo_id", "uuid", "no", None),
        ("consumo_acumulado", "numeric(14,4)", "no", None),
        ("avance_acumulado", "numeric(14,4)", "no", None),
        ("rendimiento", "numeric(18,6)", "no", None),
        ("rendimiento_congelado", "numeric(18,6)", "no", None),
        ("divergencia_pct", "numeric(9,6)", "no", None),
        ("muestra", "integer", "no", None),
        ("calculado_en", "timestamptz", "no", None),
    ),
}

# Las columnas que el diseño declara `timestamptz` (TC-20), por tabla.
CON_ZONA_HORARIA: dict[str, tuple[str, ...]] = {
    "linea_base": ("congelada_en", "creado_en"),
    "presupuesto_control": ("capturado_en", "actualizado_en"),
    "importacion": ("creado_en", "latido"),
    "rendimiento_observado": ("calculado_en",),
}

Columna = tuple[str, str, int | None, int | None, str, str | None]


def _como_el_catalogo(fila: FilaDeTabla) -> Columna:
    nombre, tipo, nulo, por_omision = fila
    tipo_catalogo, precision, escala = TIPOS[tipo]
    return (nombre, tipo_catalogo, precision, escala, "YES" if nulo == "sí" else "NO", por_omision)


COLUMNAS_ESPERADAS: dict[str, list[Columna]] = {
    tabla: sorted(_como_el_catalogo(fila) for fila in filas)
    for tabla, filas in TABLAS_DE_NULABILIDAD.items()
}

ESTADOS_DE_LINEA_BASE = ("BORRADOR", "CONGELADA", "SUPERSEDIDA")
ESTADOS_DE_IMPORTACION = (
    "RECIBIDO",
    "ANALIZANDO",
    "VALIDADO",
    "CON_ERRORES",
    "CONFIRMADO",
    "DESCARTADO",
)
TIPOS_DE_ERROR_DE_IMPORTACION = (
    "REF_ROTA",
    "UNIDAD_DESCONOCIDA",
    "SIN_APU",
    "RENDIMIENTO_AUSENTE",
    "DUPLICADO",
    "SIN_CONCEPTOS",
    "PROCESO_INTERRUMPIDO",
)

# --------------------------------------------------------------------------- ayudas


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def contar_congeladas(conexion: Conexion, obra_id: uuid.UUID) -> int:
    fila = conexion.execute(
        "SELECT count(*) FROM linea_base WHERE obra_id = %s AND estado = 'CONGELADA'", (obra_id,)
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def fila_de(conexion: Conexion, tabla: str, identificador: uuid.UUID) -> tuple[Any, ...] | None:
    """La fila completa tal como está guardada, para compararla antes y después de un rechazo."""
    fila = conexion.execute(
        sql.SQL("SELECT * FROM {} WHERE id = %s").format(sql.Identifier(tabla)), (identificador,)
    ).fetchone()
    return None if fila is None else tuple(fila)


def columnas_sin_estado(conexion: Conexion, identificador: uuid.UUID) -> tuple[Any, ...]:
    """Todas las columnas de una línea base salvo `estado`, en un orden fijo que no depende de la tabla."""
    fila = conexion.execute(
        "SELECT id, obra_id, version, congelada_en, congelada_por_id, motivo, importe_venta, "
        "creado_en, creado_por_id FROM linea_base WHERE id = %s",
        (identificador,),
    ).fetchone()
    assert fila is not None
    return tuple(fila)


def fotografia(conexion: Conexion, tabla: str) -> list[tuple[Any, ...]]:
    """Todas las filas de una tabla en un orden fijo, para comprobar que un rechazo no cambió nada."""
    filas = conexion.execute(
        sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(tabla))
    ).fetchall()
    return [tuple(fila) for fila in filas]


def insertar_copia(
    conexion: Conexion,
    linea_base_id: uuid.UUID,
    concepto_id: uuid.UUID,
    *,
    codigo: str = "620002",
) -> uuid.UUID:
    """Inserta una copia de concepto con la conexión que se pase (no con la fábrica)."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO linea_base_concepto (id, linea_base_id, concepto_id, codigo, cantidad, "
        "precio_unitario, importe) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            identificador,
            linea_base_id,
            concepto_id,
            codigo,
            Decimal("10.0000"),
            Decimal("20.0000"),
            Decimal("200.0000"),
        ),
    )
    return identificador


def insertar_renglon(
    conexion: Conexion, linea_base_id: uuid.UUID, tipo_partida_id: uuid.UUID, insumo_id: uuid.UUID
) -> uuid.UUID:
    """Inserta un renglón de explosión con la conexión que se pase (no con la fábrica)."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO explosion_presupuesto (id, linea_base_id, tipo_partida_id, insumo_id, "
        "cantidad_presupuestada, rendimiento_congelado, costo_unitario, importe_venta) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            identificador,
            linea_base_id,
            tipo_partida_id,
            insumo_id,
            Decimal("10.0000"),
            Decimal("0.250000"),
            Decimal("85.0000"),
            Decimal("850.0000"),
        ),
    )
    return identificador


def afirmar_rechazo(error: psycopg.Error, sqlstate: str, restriccion: str, tabla: str) -> None:
    """Un rechazo de restricción: el `SQLSTATE`, el nombre de la restricción y la tabla."""
    assert error.sqlstate == sqlstate
    assert error.diag.constraint_name == restriccion
    assert error.diag.table_name == tabla


def afirmar_rechazo_del_disparador(error: psycopg.Error, disparador: str, tabla: str) -> None:
    """El rechazo de un disparador del invariante 14: `IN001`, `RN-01:`, su nombre y su tabla.

    El `SQLSTATE` es el propio del proyecto, no el `P0001` de un `RAISE` sin código ni el `23001`
    o el `23503` de una clave foránea. El nombre del disparador viaja en `constraint_name`, igual
    que el de una restricción.
    """
    assert error.sqlstate == CODIGO_DEL_DISPARADOR
    mensaje = error.diag.message_primary
    assert mensaje is not None, "El disparador rechazó sin mensaje."
    assert mensaje.startswith(PREFIJO_DEL_MENSAJE), mensaje
    assert error.diag.constraint_name == disparador
    assert error.diag.table_name == tabla
    assert error.diag.schema_name == "public"


# --------------------------------------------------------------------------- TC-20


@pytest.mark.parametrize("tabla", list(COLUMNAS_ESPERADAS))
def test_tkt011_ca01_tablas_de_linea_base_e_importacion_con_su_forma(
    tabla: str, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-20 · CA-1 esc. 1 · PA-T10 — la tabla existe con las columnas, tipos y nulabilidad del diseño."""
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable, "
            "column_default FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY column_name",
            (tabla,),
        ).fetchall()

    assert filas, f"La tabla {tabla} no existe: la migración 0007 no la crea."
    assert [tuple(fila) for fila in filas] == COLUMNAS_ESPERADAS[tabla]


@pytest.mark.parametrize("tabla", list(CON_ZONA_HORARIA))
def test_tkt011_ca01_marcas_de_tiempo_con_zona_horaria(
    tabla: str, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-20 · CA-1 · PA-T10 — `congelada_en`, `capturado_en`, `actualizado_en`, `creado_en`, `latido` y `calculado_en` son `timestamptz`, nunca `timestamp` sin zona."""
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = ANY(%s) "
            "ORDER BY column_name",
            (tabla, list(CON_ZONA_HORARIA[tabla])),
        ).fetchall()

    assert [tuple(fila) for fila in filas] == [
        (columna, "timestamp with time zone") for columna in sorted(CON_ZONA_HORARIA[tabla])
    ]


# --------------------------------------------------------------------------- TC-21 y TC-22


def test_tkt011_ca04_segunda_linea_base_congelada_la_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-21 · CA-4 esc. 1 · HDU-001 esc. 19 · invariante 5 — una segunda `CONGELADA` de la obra viola el índice único parcial."""
    obra_id = datos_presupuesto.obra(codigo="AP-058-25")
    original = datos_presupuesto.linea_base(estado="CONGELADA", obra_id=obra_id, version=1)

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.linea_base(estado="CONGELADA", obra_id=obra_id, version=2)

    afirmar_rechazo(rechazo.value, "23505", "uq_linea_base_obra_id_congelada", "linea_base")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar_congeladas(aplicacion, obra_id) == 1
        assert contar(aplicacion, "linea_base") == 1
        sigue = aplicacion.execute(
            "SELECT id FROM linea_base WHERE obra_id = %s AND estado = 'CONGELADA'", (obra_id,)
        ).fetchone()
    assert sigue == (original,)


def test_tkt011_ca04_congelada_junto_a_supersedida_y_borrador(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-22 · CA-4 esc. 2 · invariante 5 — la obra A guarda las tres y la obra B guarda su propia `CONGELADA`."""
    obra_a = datos_presupuesto.obra(codigo="AP-058-25")
    obra_b = datos_presupuesto.obra(codigo="AP-059-25")

    datos_presupuesto.linea_base(estado="SUPERSEDIDA", obra_id=obra_a, version=1)
    datos_presupuesto.linea_base(estado="CONGELADA", obra_id=obra_a, version=2)
    datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra_a, version=3)
    datos_presupuesto.linea_base(estado="CONGELADA", obra_id=obra_b, version=1)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardadas = aplicacion.execute("SELECT obra_id, estado FROM linea_base").fetchall()
    assert sorted(guardadas) == sorted(
        [
            (obra_a, "SUPERSEDIDA"),
            (obra_a, "CONGELADA"),
            (obra_a, "BORRADOR"),
            (obra_b, "CONGELADA"),
        ]
    )


# --------------------------------------------------------------------------- TC-28 y TC-29

# (tabla, restricción, cómo crear una fila con el valor ajeno al conjunto). Las seis filas de
# `CA-8` más `tipo_contrato`; las de obra, insumo y cargo de APU son de `0006` y ya las prueba
# TKT-011a (TC-08): aquí se prueban juntas, como pide la spec.
FUERA_DEL_CONJUNTO: list[tuple[str, str, Crear]] = [
    (
        "importacion",
        "ck_importacion_estado",
        lambda datos: datos.importacion(estado="TERMINADA"),
    ),
    (
        "importacion_error",
        "ck_importacion_error_tipo",
        lambda datos: datos.error_importacion(tipo="OTRO"),
    ),
    ("linea_base", "ck_linea_base_estado", lambda datos: datos.linea_base(estado="ABIERTA")),
    ("obra", "ck_obra_estado", lambda datos: datos.obra(estado="BORRADA")),
    ("insumo", "ck_insumo_tipo", lambda datos: datos.insumo(tipo="EQUIPO")),
    ("apu_cargo", "ck_apu_cargo_tipo", lambda datos: datos.apu_cargo(tipo="PROPINA")),
    ("obra", "ck_obra_tipo_contrato", lambda datos: datos.obra(tipo_contrato="OTRO")),
]


@pytest.mark.parametrize(
    ("tabla", "restriccion", "crear"),
    FUERA_DEL_CONJUNTO,
    ids=[restriccion for _, restriccion, _ in FUERA_DEL_CONJUNTO],
)
def test_tkt011_ca08_los_siete_conjuntos_cerrados_responden_23514(
    tabla: str,
    restriccion: str,
    crear: Crear,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-28 · CA-8 esc. 1 · ADR-030 — un valor fuera del conjunto cerrado responde `23514` con su `ck_…` y no deja fila."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        crear(datos_presupuesto)

    afirmar_rechazo(rechazo.value, "23514", restriccion, tabla)
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, tabla) == 0


def test_tkt011_ca08_los_siete_rechazos_comparten_el_mismo_sqlstate(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-28 · CA-8 esc. 1 — «el mismo» mecanismo: el conjunto de `SQLSTATE` observados es exactamente `{"23514"}`.

    Las siete filas en una sola base. Una fila que entrara, o que fallara por otra causa (tabla
    inexistente, `NOT NULL`), añadiría un valor al conjunto.
    """
    observados: set[str] = set()
    sin_rechazo: list[str] = []
    cambiaron: list[str] = []
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        for tabla, restriccion, crear in FUERA_DEL_CONJUNTO:
            antes = contar(aplicacion, tabla) if _existe(aplicacion, tabla) else 0
            try:
                crear(datos_presupuesto)
            except psycopg.Error as rechazo:
                observados.add(str(rechazo.sqlstate))
            else:
                sin_rechazo.append(restriccion)
            if _existe(aplicacion, tabla) and contar(aplicacion, tabla) != antes:
                cambiaron.append(tabla)

    assert sin_rechazo == []
    assert cambiaron == []
    assert observados == {"23514"}


def _existe(conexion: Conexion, tabla: str) -> bool:
    """¿Existe la tabla en `public`? Sin ella `contar` lanzaría `42P01` y ocultaría el motivo del rojo."""
    fila = conexion.execute("SELECT to_regclass(%s)", (f"public.{tabla}",)).fetchone()
    return fila is not None and fila[0] is not None


# (tabla, columna del conjunto cerrado, valor admitido, cómo crear una fila con ese valor).
def _linea_base_en(estado: str) -> Crear:
    return lambda datos: datos.linea_base(estado=estado)


def _importacion_en(estado: str) -> Crear:
    return lambda datos: datos.importacion(estado=estado)


def _error_de_tipo(tipo: str) -> Crear:
    return lambda datos: datos.error_importacion(tipo=tipo)


ADMITIDOS: list[tuple[str, str, str, Crear]] = [
    *[
        ("importacion", "estado", estado, _importacion_en(estado))
        for estado in ESTADOS_DE_IMPORTACION
    ],
    *[
        ("importacion_error", "tipo", tipo, _error_de_tipo(tipo))
        for tipo in TIPOS_DE_ERROR_DE_IMPORTACION
    ],
    *[("linea_base", "estado", estado, _linea_base_en(estado)) for estado in ESTADOS_DE_LINEA_BASE],
]


@pytest.mark.parametrize(
    ("tabla", "columna", "valor", "crear"),
    ADMITIDOS,
    ids=[f"{tabla}_{valor}" for tabla, _, valor, _ in ADMITIDOS],
)
def test_tkt011_ca08_estados_y_tipos_admitidos_se_aceptan(
    tabla: str,
    columna: str,
    valor: str,
    crear: Crear,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-29 · CA-8 esc. 2 — cada estado de importación, tipo de error y estado de línea base entra y se guarda tal cual."""
    identificador = crear(datos_presupuesto)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                sql.Identifier(columna), sql.Identifier(tabla)
            ),
            (identificador,),
        ).fetchone()
    assert guardado == (valor,)


# --------------------------------------------------------------------------- TC-33

# (tabla, columna, cómo crear una fila con ese valor en esa columna). La restricción esperada es
# `ck_<tabla>_<columna>_no_negativo`. Las copias se crean sobre una línea base `BORRADOR`. Son las
# catorce columnas de b: `divergencia_pct` no está porque una divergencia puede ser negativa.
NO_NEGATIVOS: list[tuple[str, str, Callable[[DatosPresupuesto, Decimal], uuid.UUID]]] = [
    (
        "linea_base",
        "importe_venta",
        lambda datos, valor: datos.linea_base(importe_venta=valor),
    ),
    (
        "linea_base_concepto",
        "cantidad",
        lambda datos, valor: datos.copia_concepto(cantidad=valor),
    ),
    (
        "linea_base_concepto",
        "precio_unitario",
        lambda datos, valor: datos.copia_concepto(precio_unitario=valor),
    ),
    (
        "linea_base_concepto",
        "importe",
        lambda datos, valor: datos.copia_concepto(importe=valor),
    ),
    (
        "explosion_presupuesto",
        "cantidad_presupuestada",
        lambda datos, valor: datos.renglon_explosion(cantidad_presupuestada=valor),
    ),
    (
        "explosion_presupuesto",
        "rendimiento_congelado",
        lambda datos, valor: datos.renglon_explosion(rendimiento_congelado=valor),
    ),
    (
        "explosion_presupuesto",
        "costo_unitario",
        lambda datos, valor: datos.renglon_explosion(costo_unitario=valor),
    ),
    (
        "explosion_presupuesto",
        "importe_venta",
        lambda datos, valor: datos.renglon_explosion(importe_venta=valor),
    ),
    (
        "presupuesto_control",
        "importe_tope",
        lambda datos, valor: datos.control(importe_tope=valor),
    ),
    (
        "presupuesto_control",
        "importe_sugerido",
        lambda datos, valor: datos.control(importe_sugerido=valor),
    ),
    (
        "rendimiento_observado",
        "consumo_acumulado",
        lambda datos, valor: datos.rendimiento_observado(consumo_acumulado=valor),
    ),
    (
        "rendimiento_observado",
        "avance_acumulado",
        lambda datos, valor: datos.rendimiento_observado(avance_acumulado=valor),
    ),
    (
        "rendimiento_observado",
        "rendimiento",
        lambda datos, valor: datos.rendimiento_observado(rendimiento=valor),
    ),
    (
        "rendimiento_observado",
        "rendimiento_congelado",
        lambda datos, valor: datos.rendimiento_observado(rendimiento_congelado=valor),
    ),
]


def negativo_minimo(tabla: str, columna: str) -> Decimal:
    """El negativo más pequeño que admite la escala de la columna: `-0.0001` en escala 4."""
    tipo = next(fila[1] for fila in TABLAS_DE_NULABILIDAD[tabla] if fila[0] == columna)
    escala = TIPOS[tipo][2]
    assert escala is not None, f"{tabla}.{columna} no es numérica: no tiene escala"
    return -Decimal(1).scaleb(-escala)


@pytest.mark.parametrize(
    ("tabla", "columna", "crear"),
    NO_NEGATIVOS,
    ids=[f"{tabla}.{columna}" for tabla, columna, _ in NO_NEGATIVOS],
)
def test_tkt011_ca13_negativo_lo_rechaza_la_base(
    tabla: str,
    columna: str,
    crear: Callable[[DatosPresupuesto, Decimal], uuid.UUID],
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-33 · CA-13 · invariante 8 — `-0.0001` en la columna responde `23514` con su `ck_<tabla>_<columna>_no_negativo`."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        crear(datos_presupuesto, negativo_minimo(tabla, columna))

    afirmar_rechazo(rechazo.value, "23514", f"ck_{tabla}_{columna}_no_negativo", tabla)
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, tabla) == 0


@pytest.mark.parametrize(
    ("tabla", "columna", "crear"),
    NO_NEGATIVOS,
    ids=[f"{tabla}.{columna}" for tabla, columna, _ in NO_NEGATIVOS],
)
def test_tkt011_ca13_cero_es_el_borde_que_la_base_acepta(
    tabla: str,
    columna: str,
    crear: Callable[[DatosPresupuesto, Decimal], uuid.UUID],
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-33 · CA-13 · invariante 8 — con `0` en la misma columna la fila entra y se guarda en cero."""
    identificador = crear(datos_presupuesto, Decimal("0"))

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                sql.Identifier(columna), sql.Identifier(tabla)
            ),
            (identificador,),
        ).fetchone()
    assert guardado == (Decimal("0"),)


# --------------------------------------------------------------------------- TC-40

# Las filas de `CA-16` que el disparador rechaza, más `CONGELADA` -> `CONGELADA` sin cambios: el
# `UPDATE` que no cambia nada tampoco es una transición admitida.
TRANSICIONES_RECHAZADAS: list[tuple[str, str]] = [
    ("CONGELADA", "BORRADOR"),
    ("SUPERSEDIDA", "CONGELADA"),
    ("SUPERSEDIDA", "BORRADOR"),
    ("BORRADOR", "SUPERSEDIDA"),
    ("CONGELADA", "CONGELADA"),
]

# Las dos filas de `CA-16` que el disparador acepta: la línea base solo avanza.
TRANSICIONES_ACEPTADAS: list[tuple[str, str]] = [
    ("BORRADOR", "CONGELADA"),
    ("CONGELADA", "SUPERSEDIDA"),
]


@pytest.mark.parametrize(
    ("desde", "hasta"),
    TRANSICIONES_RECHAZADAS,
    ids=[f"{desde}_a_{hasta}" for desde, hasta in TRANSICIONES_RECHAZADAS],
)
def test_tkt011_ca16_transicion_de_la_linea_base_se_rechaza(
    desde: str,
    hasta: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-40 · CA-16 esc. 1 · RN-01 · PA-T14 — una transición que no avanza responde `IN001` y deja la fila igual.

    Con el rol de migración, que es el dueño de la tabla: así el rechazo es del disparador y no de
    un privilegio.
    """
    identificador = datos_presupuesto.linea_base(estado=desde)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = fila_de(migracion, "linea_base", identificador)
        assert antes is not None

        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute(
                "UPDATE linea_base SET estado = %s WHERE id = %s", (hasta, identificador)
            )

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_LINEA_BASE, "linea_base")
        assert fila_de(migracion, "linea_base", identificador) == antes


@pytest.mark.parametrize(
    ("desde", "hasta"),
    TRANSICIONES_ACEPTADAS,
    ids=[f"{desde}_a_{hasta}" for desde, hasta in TRANSICIONES_ACEPTADAS],
)
def test_tkt011_ca16_transicion_de_la_linea_base_se_acepta(
    desde: str,
    hasta: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-40 · CA-16 esc. 1 · RN-01 — `BORRADOR` -> `CONGELADA` y `CONGELADA` -> `SUPERSEDIDA` avanzan; solo cambia el estado."""
    identificador = datos_presupuesto.linea_base(estado=desde)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = columnas_sin_estado(migracion, identificador)

        migracion.execute("UPDATE linea_base SET estado = %s WHERE id = %s", (hasta, identificador))

        despues = columnas_sin_estado(migracion, identificador)
        estado = migracion.execute(
            "SELECT estado FROM linea_base WHERE id = %s", (identificador,)
        ).fetchone()

    assert estado == (hasta,)
    assert despues == antes


def test_tkt011_ca16_al_congelar_se_fijan_sus_datos_en_la_misma_sentencia(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-40 · CA-16 · PA-T14 — el `UPDATE` que congela puede fijar `congelada_en`, `congelada_por_id` e `importe_venta`."""
    identificador = datos_presupuesto.linea_base(estado="BORRADOR")
    congeladora = datos_presupuesto.usuario()
    momento = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)

    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(
            "UPDATE linea_base SET estado = 'CONGELADA', congelada_en = %s, "
            "congelada_por_id = %s, importe_venta = %s WHERE id = %s",
            (momento, congeladora, Decimal("1234567.8900"), identificador),
        )
        guardado = migracion.execute(
            "SELECT estado, congelada_en, congelada_por_id, importe_venta FROM linea_base "
            "WHERE id = %s",
            (identificador,),
        ).fetchone()

    assert guardado == ("CONGELADA", momento, congeladora, Decimal("1234567.8900"))


def test_tkt011_ca16_un_borrador_se_edita_sin_que_intervenga_el_disparador(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-40 · CA-16 · RN-01 — `BORRADOR` no está protegido: el disparador deja pasar cualquier cambio de columnas mientras la línea base no se congela."""
    identificador = datos_presupuesto.linea_base(estado="BORRADOR", motivo=None)

    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute(
            "UPDATE linea_base SET version = 2, motivo = 'Reimportación', importe_venta = %s "
            "WHERE id = %s",
            (Decimal("500.0000"), identificador),
        )
        guardado = migracion.execute(
            "SELECT estado, version, motivo, importe_venta FROM linea_base WHERE id = %s",
            (identificador,),
        ).fetchone()

    assert guardado == ("BORRADOR", 2, "Reimportación", Decimal("500.0000"))


# --------------------------------------------------------------------------- TC-41

_OTRO_MOMENTO = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)

# (columna, cómo obtener un valor distinto del que guarda la fila). Son las ocho columnas, además de
# `id` y `estado`, que una línea base ya congelada no puede cambiar.
CAMBIOS_PROHIBIDOS: list[tuple[str, Callable[[DatosPresupuesto], Any]]] = [
    ("obra_id", lambda datos: datos.obra(codigo="AP-059-25")),
    ("version", lambda datos: 2),
    ("motivo", lambda datos: "Motivo distinto"),
    ("importe_venta", lambda datos: Decimal("1.0000")),
    ("congelada_en", lambda datos: _OTRO_MOMENTO),
    ("congelada_por_id", lambda datos: datos.usuario()),
    ("creado_en", lambda datos: _OTRO_MOMENTO),
    ("creado_por_id", lambda datos: datos.usuario()),
]


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
@pytest.mark.parametrize(
    ("columna", "valor_distinto"),
    CAMBIOS_PROHIBIDOS,
    ids=[columna for columna, _ in CAMBIOS_PROHIBIDOS],
)
def test_tkt011_ca16_una_congelada_no_cambia_mas_que_su_estado(
    estado: str,
    columna: str,
    valor_distinto: Callable[[DatosPresupuesto], Any],
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-41 · CA-16 esc. 2 · RN-01 · PA-T6 — cambiar cualquier columna de una línea base que no es borrador responde `IN001`.

    `CONGELADA` es el caso de la spec; `SUPERSEDIDA` comparte la regla 3 del diseño y se prueba con
    la misma tabla de columnas.
    """
    identificador = datos_presupuesto.linea_base(estado=estado, motivo="Motivo original")
    nuevo = valor_distinto(datos_presupuesto)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = fila_de(migracion, "linea_base", identificador)
        assert antes is not None

        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute(
                sql.SQL("UPDATE linea_base SET {} = %s WHERE id = %s").format(
                    sql.Identifier(columna)
                ),
                (nuevo, identificador),
            )

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_LINEA_BASE, "linea_base")
        assert fila_de(migracion, "linea_base", identificador) == antes


@pytest.mark.parametrize(
    ("columna", "valor_distinto"),
    CAMBIOS_PROHIBIDOS,
    ids=[columna for columna, _ in CAMBIOS_PROHIBIDOS],
)
def test_tkt011_ca16_al_superseder_una_congelada_no_se_cambia_otra_columna(
    columna: str,
    valor_distinto: Callable[[DatosPresupuesto], Any],
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-41 · CA-16 esc. 2 · RN-01 — `CONGELADA` -> `SUPERSEDIDA` es válida, pero no si en la misma sentencia cambia otra columna (por ejemplo `importe_venta`).

    Es el caso en que la transición sola se aceptaría: solo la comparación de columnas del
    disparador lo rechaza.
    """
    identificador = datos_presupuesto.linea_base(estado="CONGELADA", motivo="Motivo original")
    nuevo = valor_distinto(datos_presupuesto)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = fila_de(migracion, "linea_base", identificador)
        assert antes is not None

        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute(
                sql.SQL(
                    "UPDATE linea_base SET estado = 'SUPERSEDIDA', {} = %s WHERE id = %s"
                ).format(sql.Identifier(columna)),
                (nuevo, identificador),
            )

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_LINEA_BASE, "linea_base")
        assert fila_de(migracion, "linea_base", identificador) == antes


# --------------------------------------------------------------------------- TC-42 sin copias


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt011_ca16_no_se_borra_una_linea_base_que_no_es_borrador(
    estado: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-42 · CA-16 esc. 3 · RN-01 — borrar una `CONGELADA` o una `SUPERSEDIDA` sin copias responde `IN001`.

    Sin copias, ninguna clave foránea interviene: el rechazo es del disparador y no es ni `23001`
    ni `23503`.
    """
    identificador = datos_presupuesto.linea_base(estado=estado)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = fila_de(migracion, "linea_base", identificador)
        assert antes is not None

        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute("DELETE FROM linea_base WHERE id = %s", (identificador,))

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_LINEA_BASE, "linea_base")
        assert fila_de(migracion, "linea_base", identificador) == antes
        assert contar(migracion, "linea_base") == 1


def test_tkt011_ca16_un_borrador_sin_copias_se_borra(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-42 · CA-16 esc. 3 — borrar un `BORRADOR` sin copias se acepta: el disparador solo protege las líneas base que no son `BORRADOR`."""
    borrador = datos_presupuesto.linea_base(estado="BORRADOR")
    otra = datos_presupuesto.linea_base(estado="BORRADOR")

    with conectar("migracion", base_de_prueba) as migracion:
        migracion.execute("DELETE FROM linea_base WHERE id = %s", (borrador,))

        assert fila_de(migracion, "linea_base", borrador) is None
        assert fila_de(migracion, "linea_base", otra) is not None
        assert contar(migracion, "linea_base") == 1


# --------------------------------------------------------------------------- TC-25


def test_tkt011_ca06_explosion_repetida_la_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-25 · CA-6 esc. 1 · invariante 19 — la terna (L, MUROS, I) repetida viola la unicidad.

    Sobre un `BORRADOR`, para que el disparador del invariante 14 no intervenga.
    """
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR")
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    insumo = datos_presupuesto.insumo()
    original = datos_presupuesto.renglon_explosion(
        linea_base_id=linea_base, tipo_partida_id=muros, insumo_id=insumo
    )

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.renglon_explosion(
            linea_base_id=linea_base, tipo_partida_id=muros, insumo_id=insumo
        )

    afirmar_rechazo(
        rechazo.value,
        "23505",
        "uq_explosion_presupuesto_linea_tipo_insumo",
        "explosion_presupuesto",
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "explosion_presupuesto") == 1
        sigue = aplicacion.execute("SELECT id FROM explosion_presupuesto").fetchone()
    assert sigue == (original,)


def test_tkt011_ca06_otro_tipo_de_partida_para_el_mismo_insumo_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-25 · CA-6 esc. 1 — la terna (L, ENCHAPES, I) entra aunque (L, MUROS, I) ya exista."""
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR")
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    enchapes = datos_presupuesto.tipo_partida(clave="ENCHAPES")
    insumo = datos_presupuesto.insumo()
    datos_presupuesto.renglon_explosion(
        linea_base_id=linea_base, tipo_partida_id=muros, insumo_id=insumo
    )

    datos_presupuesto.renglon_explosion(
        linea_base_id=linea_base, tipo_partida_id=enchapes, insumo_id=insumo
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardadas = aplicacion.execute(
            "SELECT linea_base_id, tipo_partida_id, insumo_id FROM explosion_presupuesto"
        ).fetchall()
    assert sorted(guardadas) == sorted(
        [(linea_base, muros, insumo), (linea_base, enchapes, insumo)]
    )


# --------------------------------------------------------------------------- TC-23 y TC-24


def test_tkt011_ca05_control_repetido_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-23 · CA-5 esc. 1 · invariante 6 — el par (L, MUROS) repetido viola la unicidad y el original no cambia."""
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR")
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    original = datos_presupuesto.control(
        linea_base_id=linea_base, tipo_partida_id=muros, importe_sugerido=Decimal("750000.0000")
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        antes = fila_de(aplicacion, "presupuesto_control", original)
    assert antes is not None

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.control(
            linea_base_id=linea_base, tipo_partida_id=muros, importe_sugerido=Decimal("1.0000")
        )

    afirmar_rechazo(
        rechazo.value,
        "23505",
        "uq_presupuesto_control_linea_base_id_tipo_partida_id",
        "presupuesto_control",
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "presupuesto_control") == 1
        assert fila_de(aplicacion, "presupuesto_control", original) == antes


def test_tkt011_ca05_otro_tipo_de_partida_para_la_misma_linea_base_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-23 · CA-5 esc. 1 — el par (L, ENCHAPES) entra aunque (L, MUROS) ya exista."""
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR")
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    enchapes = datos_presupuesto.tipo_partida(clave="ENCHAPES")
    datos_presupuesto.control(linea_base_id=linea_base, tipo_partida_id=muros)

    datos_presupuesto.control(linea_base_id=linea_base, tipo_partida_id=enchapes)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardados = aplicacion.execute(
            "SELECT linea_base_id, tipo_partida_id FROM presupuesto_control"
        ).fetchall()
    assert sorted(guardados) == sorted([(linea_base, muros), (linea_base, enchapes)])


def test_tkt011_ca05_el_mismo_tipo_de_partida_en_otra_linea_base_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-23 · CA-5 esc. 1 — el par es (línea base, tipo): MUROS en otra línea base no choca con el de L."""
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    primera = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra, version=1)
    segunda = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra, version=2)
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    datos_presupuesto.control(linea_base_id=primera, tipo_partida_id=muros)

    datos_presupuesto.control(linea_base_id=segunda, tipo_partida_id=muros)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "presupuesto_control") == 2


def test_tkt011_ca05_tope_y_auditoria_admiten_nulo(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-24 · CA-5 esc. 2 — un control sin tope ni captura entra, y la actualización también admite nulo."""
    identificador = datos_presupuesto.control(
        importe_tope=None,
        capturado_por_id=None,
        capturado_en=None,
        actualizado_por_id=None,
        actualizado_en=None,
        motivo_ultimo_cambio=None,
        importe_sugerido=Decimal("250000.0000"),
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT importe_tope, importe_sugerido, capturado_por_id, capturado_en, "
            "actualizado_por_id, actualizado_en, motivo_ultimo_cambio "
            "FROM presupuesto_control WHERE id = %s",
            (identificador,),
        ).fetchone()
    assert guardado == (None, Decimal("250000.0000"), None, None, None, None, None)


# --------------------------------------------------------------------------- TC-35 y TC-36

Sentencia = Callable[[Conexion, "DatosPresupuesto", "CopiasDeLineaBase"], None]


def _insert_en_linea_base_concepto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    insertar_copia(conexion, copias.linea_base_id, copias.concepto_id, codigo="620099")


def _insert_en_explosion_presupuesto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    # Un insumo nuevo, para que la terna no se repita: el rechazo que se afirma es el del disparador.
    insumo = datos.insumo_nuevo()
    insertar_renglon(conexion, copias.linea_base_id, copias.tipo_partida_id, insumo)


def _update_sobre_linea_base_concepto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    conexion.execute(
        "UPDATE linea_base_concepto SET cantidad = %s WHERE id = %s",
        (Decimal("999.0000"), copias.copia_id),
    )


def _delete_sobre_linea_base_concepto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    conexion.execute("DELETE FROM linea_base_concepto WHERE id = %s", (copias.copia_id,))


def _update_sobre_explosion_presupuesto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    conexion.execute(
        "UPDATE explosion_presupuesto SET cantidad_presupuestada = %s WHERE id = %s",
        (Decimal("999.0000"), copias.renglon_id),
    )


def _delete_sobre_explosion_presupuesto(
    conexion: Conexion, datos: DatosPresupuesto, copias: CopiasDeLineaBase
) -> None:
    conexion.execute("DELETE FROM explosion_presupuesto WHERE id = %s", (copias.renglon_id,))


# Las seis sentencias de `CA-15`: (nombre, tabla afectada, qué ejecutar).
SEIS_SENTENCIAS: list[tuple[str, str, Sentencia]] = [
    ("insert_en_linea_base_concepto", "linea_base_concepto", _insert_en_linea_base_concepto),
    ("insert_en_explosion_presupuesto", "explosion_presupuesto", _insert_en_explosion_presupuesto),
    ("update_sobre_linea_base_concepto", "linea_base_concepto", _update_sobre_linea_base_concepto),
    ("delete_sobre_linea_base_concepto", "linea_base_concepto", _delete_sobre_linea_base_concepto),
    (
        "update_sobre_explosion_presupuesto",
        "explosion_presupuesto",
        _update_sobre_explosion_presupuesto,
    ),
    (
        "delete_sobre_explosion_presupuesto",
        "explosion_presupuesto",
        _delete_sobre_explosion_presupuesto,
    ),
]


def _afirmar_que_el_disparador_rechaza(
    sentencia: Sentencia,
    tabla: str,
    estado: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos: DatosPresupuesto,
) -> None:
    """La sentencia, con el rol de migración sobre una línea base en `estado` con copias, responde `IN001`."""
    copias = datos.linea_base_con_copias(estado=estado)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = {nombre: fotografia(migracion, nombre) for nombre in TABLAS_DE_COPIAS}
        assert all(len(filas) == 1 for filas in antes.values()), (
            "La preparación debe dejar una copia en cada tabla"
        )

        with pytest.raises(psycopg.Error) as rechazo:
            sentencia(migracion, datos, copias)

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_COPIAS[tabla], tabla)
        despues = {nombre: fotografia(migracion, nombre) for nombre in TABLAS_DE_COPIAS}
    assert despues == antes


@pytest.mark.parametrize(
    ("tabla", "sentencia"),
    [(tabla, sentencia) for _, tabla, sentencia in SEIS_SENTENCIAS],
    ids=[nombre for nombre, _, _ in SEIS_SENTENCIAS],
)
def test_tkt011_ca15_copia_de_linea_base_congelada_la_rechaza_el_disparador(
    tabla: str,
    sentencia: Sentencia,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-35 · CA-15 esc. 1 · RN-01 · HDU-001 esc. 18 — INSERT, UPDATE y DELETE sobre las copias de una `CONGELADA` responden `IN001`.

    Con el rol de migración, a propósito: con el de aplicación el privilegio rechazaría antes.
    """
    _afirmar_que_el_disparador_rechaza(
        sentencia, tabla, "CONGELADA", base_de_prueba, conectar, datos_presupuesto
    )


@pytest.mark.parametrize(
    ("tabla", "sentencia"),
    [(tabla, sentencia) for _, tabla, sentencia in SEIS_SENTENCIAS],
    ids=[nombre for nombre, _, _ in SEIS_SENTENCIAS],
)
def test_tkt011_ca15_copia_de_linea_base_supersedida_la_rechaza_el_disparador(
    tabla: str,
    sentencia: Sentencia,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-36 · CA-15 esc. 2 · RN-01 · PA-T6 — las mismas seis sentencias sobre una `SUPERSEDIDA` también responden `IN001`."""
    _afirmar_que_el_disparador_rechaza(
        sentencia, tabla, "SUPERSEDIDA", base_de_prueba, conectar, datos_presupuesto
    )


# --------------------------------------------------------------------------- TC-37


@pytest.mark.parametrize("tabla", TABLAS_DE_COPIAS)
@pytest.mark.parametrize("sentido", ["congelada_a_borrador", "borrador_a_congelada"])
def test_tkt011_ca15_mover_una_copia_entre_lineas_base_lo_rechaza_el_disparador(
    tabla: str,
    sentido: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-37 · CA-15 esc. 1 · RN-01 — cambiar `linea_base_id` de una copia desde o hacia una `CONGELADA` responde `IN001`.

    Mover una copia es un `UPDATE` que afecta a dos líneas base: basta que una esté congelada.
    """
    congelada = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    borrador = datos_presupuesto.linea_base_con_copias(estado="BORRADOR")
    de_la_congelada = {
        "linea_base_concepto": congelada.copia_id,
        "explosion_presupuesto": congelada.renglon_id,
    }[tabla]
    del_borrador = {
        "linea_base_concepto": borrador.copia_id,
        "explosion_presupuesto": borrador.renglon_id,
    }[tabla]
    if sentido == "congelada_a_borrador":
        movida, destino = de_la_congelada, borrador.linea_base_id
    else:
        movida, destino = del_borrador, congelada.linea_base_id

    with conectar("migracion", base_de_prueba) as migracion:
        antes = {nombre: fotografia(migracion, nombre) for nombre in TABLAS_DE_COPIAS}

        with pytest.raises(psycopg.Error) as rechazo:
            migracion.execute(
                sql.SQL("UPDATE {} SET linea_base_id = %s WHERE id = %s").format(
                    sql.Identifier(tabla)
                ),
                (destino, movida),
            )

        afirmar_rechazo_del_disparador(rechazo.value, DISPARADOR_DE_COPIAS[tabla], tabla)
        despues = {nombre: fotografia(migracion, nombre) for nombre in TABLAS_DE_COPIAS}
    assert despues == antes


# --------------------------------------------------------------------------- TC-38


@pytest.mark.parametrize("tabla", TABLAS_DE_COPIAS)
def test_tkt011_ca15_borrador_se_prepara_sin_el_disparador(
    tabla: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-38 · CA-15 esc. 3 · RN-01 — INSERT, UPDATE y DELETE sobre las copias de un `BORRADOR` terminan sin error.

    `BORRADOR` no está protegido: el disparador deja pasar INSERT, UPDATE y DELETE sobre sus copias. Se prueba con el rol de migración; la aplicación no tiene UPDATE ni DELETE sobre `linea_base_concepto` (CA-17).
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="BORRADOR")
    existente = copias.copia_id if tabla == "linea_base_concepto" else copias.renglon_id
    columna = "cantidad" if tabla == "linea_base_concepto" else "cantidad_presupuestada"

    with conectar("migracion", base_de_prueba) as migracion:
        if tabla == "linea_base_concepto":
            nueva = insertar_copia(migracion, copias.linea_base_id, copias.concepto_id)
        else:
            insumo = datos_presupuesto.insumo_nuevo()
            nueva = insertar_renglon(
                migracion, copias.linea_base_id, copias.tipo_partida_id, insumo
            )
        assert contar(migracion, tabla) == 2

        migracion.execute(
            sql.SQL("UPDATE {} SET {} = %s WHERE id = %s").format(
                sql.Identifier(tabla), sql.Identifier(columna)
            ),
            (Decimal("777.0000"), existente),
        )
        cambiada = migracion.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                sql.Identifier(columna), sql.Identifier(tabla)
            ),
            (existente,),
        ).fetchone()
        assert cambiada == (Decimal("777.0000"),)

        migracion.execute(
            sql.SQL("DELETE FROM {} WHERE id = ANY(%s)").format(sql.Identifier(tabla)),
            ([existente, nueva],),
        )
        assert contar(migracion, tabla) == 0


# --------------------------------------------------------------------------- TC-39


def test_tkt011_ca15_el_congelado_ocurre_en_una_transaccion(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-39 · CA-15 esc. 4 · RN-01 — en una sola transacción se insertan las copias, se congela y, desde ahí, la línea base rechaza más copias.

    Con el rol de aplicación y `autocommit=False`, como lo hará TKT-017. La tercera copia responde
    `IN001`; `ROLLBACK TO SAVEPOINT` deja la transacción viva y el `COMMIT` conserva lo anterior.
    """
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra)
    concepto = datos_presupuesto.concepto(obra_id=obra)
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    placa = datos_presupuesto.insumo(codigo="INS-PLACA")
    perfil = datos_presupuesto.insumo(codigo="INS-PERFIL")

    transaccion = conectar("aplicacion", base_de_prueba, autocommit=False)
    primera = insertar_copia(transaccion, linea_base, concepto, codigo="620001")
    segunda = insertar_copia(transaccion, linea_base, concepto, codigo="620002")
    renglon_placa = insertar_renglon(transaccion, linea_base, muros, placa)
    renglon_perfil = insertar_renglon(transaccion, linea_base, muros, perfil)
    transaccion.execute("UPDATE linea_base SET estado = 'CONGELADA' WHERE id = %s", (linea_base,))

    transaccion.execute("SAVEPOINT antes_de_la_tercera")
    with pytest.raises(psycopg.Error) as rechazo:
        insertar_copia(transaccion, linea_base, concepto, codigo="620003")
    afirmar_rechazo_del_disparador(
        rechazo.value, DISPARADOR_DE_COPIAS["linea_base_concepto"], "linea_base_concepto"
    )
    transaccion.execute("ROLLBACK TO SAVEPOINT antes_de_la_tercera")
    transaccion.commit()

    with conectar("aplicacion", base_de_prueba) as otra:
        estado = otra.execute(
            "SELECT estado FROM linea_base WHERE id = %s", (linea_base,)
        ).fetchone()
        copias = otra.execute(
            "SELECT id FROM linea_base_concepto WHERE linea_base_id = %s", (linea_base,)
        ).fetchall()
        renglones = otra.execute(
            "SELECT id FROM explosion_presupuesto WHERE linea_base_id = %s", (linea_base,)
        ).fetchall()
    assert estado == ("CONGELADA",)
    assert sorted(copias) == sorted([(primera,), (segunda,)])
    assert sorted(renglones) == sorted([(renglon_placa,), (renglon_perfil,)])


# --------------------------------------------------------------------------- TC-C2


def test_tkt011_ca15_una_copia_concurrente_no_entra_tras_el_congelado(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-C2 · CA-15 esc. 4 · M5 · RN-01 — una copia que llega mientras otra transacción congela no puede leer el estado (`55P03`) y, tras el commit, se rechaza.

    A congela sin confirmar. B, con `lock_timeout` corto, no puede leer el estado (`FOR SHARE`):
    responde `55P03`. Si leyera `BORRADOR` sin esperar, la copia entraría después del congelado.
    """
    copias = datos_presupuesto.linea_base_con_copias(estado="BORRADOR")
    linea_base = copias.linea_base_id

    a = conectar("aplicacion", base_de_prueba, autocommit=False)
    b = conectar("aplicacion", base_de_prueba)
    a.execute("UPDATE linea_base SET estado = 'CONGELADA' WHERE id = %s", (linea_base,))
    b.execute("SET lock_timeout = '200ms'")

    with pytest.raises(psycopg.errors.LockNotAvailable) as espera:
        insertar_copia(b, linea_base, copias.concepto_id, codigo="620077")
    assert espera.value.sqlstate == "55P03"

    a.commit()

    with pytest.raises(psycopg.Error) as rechazo:
        insertar_copia(b, linea_base, copias.concepto_id, codigo="620077")
    afirmar_rechazo_del_disparador(
        rechazo.value, DISPARADOR_DE_COPIAS["linea_base_concepto"], "linea_base_concepto"
    )

    estado = b.execute("SELECT estado FROM linea_base WHERE id = %s", (linea_base,)).fetchone()
    originales = b.execute(
        "SELECT id FROM linea_base_concepto WHERE linea_base_id = %s", (linea_base,)
    ).fetchall()
    renglones = b.execute(
        "SELECT id FROM explosion_presupuesto WHERE linea_base_id = %s", (linea_base,)
    ).fetchall()
    assert estado == ("CONGELADA",)
    assert originales == [(copias.copia_id,)]
    assert renglones == [(copias.renglon_id,)]


# --------------------------------------------------------------------------- TC-42 con copias

# (tabla de copias, la clave foránea que protege al `BORRADOR` que las tiene).
CLAVE_DE_LAS_COPIAS = [
    ("linea_base_concepto", "fk_linea_base_concepto_linea_base_id"),
    ("explosion_presupuesto", "fk_explosion_presupuesto_linea_base_id"),
]


@pytest.mark.parametrize(
    ("tabla", "restriccion"), CLAVE_DE_LAS_COPIAS, ids=[tabla for tabla, _ in CLAVE_DE_LAS_COPIAS]
)
def test_tkt011_ca16_un_borrador_con_copias_no_se_borra(
    tabla: str,
    restriccion: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-42 · CA-16 esc. 3 · PA-T8 — borrar un `BORRADOR` que tiene copias responde `23001` con la clave foránea de la copia.

    No es `IN001`: el disparador de `linea_base` deja pasar el `BORRADOR` y es `ON DELETE RESTRICT`
    quien lo detiene.
    """
    # Solo la copia de la tabla bajo prueba: con las dos, PostgreSQL informa la primera clave que viola.
    borrador = datos_presupuesto.linea_base(estado="BORRADOR")
    if tabla == "linea_base_concepto":
        datos_presupuesto.copia_concepto(linea_base_id=borrador)
    else:
        datos_presupuesto.renglon_explosion(linea_base_id=borrador)
    tablas = ("linea_base", *TABLAS_DE_COPIAS)

    with conectar("migracion", base_de_prueba) as migracion:
        antes = {nombre: fotografia(migracion, nombre) for nombre in tablas}

        with pytest.raises(psycopg.errors.RestrictViolation) as rechazo:
            migracion.execute("DELETE FROM linea_base WHERE id = %s", (borrador,))

        afirmar_rechazo(rechazo.value, "23001", restriccion, tabla)
        despues = {nombre: fotografia(migracion, nombre) for nombre in tablas}
    assert despues == antes


# --------------------------------------------------------------------------- E-13

COPIAS_DE_UNA_OBRA_REAL = 5000
RENGLONES_DE_UNA_OBRA_REAL = 300
STATEMENT_TIMEOUT_DEL_ROL = 15.0


def test_tkt011_ca15_e13_congelar_una_obra_real_cabe_en_el_tiempo_del_rol(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """E-13 · CA-15 · M5 — 5,000 copias, 300 renglones y el congelado, en una transacción, caben en el `statement_timeout` de 15 s del rol.

    El `FOR SHARE` del disparador se paga por fila. Si una sola sentencia pasara de 15 s, el rol la
    cancelaría con `57014` y habría que rediseñar el disparador (`/sdd-escalar`). La duración
    medida va en el mensaje de la aserción y en la salida estándar (`pytest -s`).
    """
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra)
    concepto = datos_presupuesto.concepto(obra_id=obra)
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    with conectar("aplicacion", base_de_prueba) as preparacion:
        preparacion.execute(
            "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, "
            "creado_en_importacion) SELECT gen_random_uuid(), 'E13-' || g, 'Insumo de volumen', "
            "'MATERIAL', 'PZA', true, false FROM generate_series(1, %s) AS g",
            (RENGLONES_DE_UNA_OBRA_REAL,),
        )

    transaccion = conectar("aplicacion", base_de_prueba, autocommit=False)
    limite = transaccion.execute("SHOW statement_timeout").fetchone()
    assert limite == ("15s",), "El rol de aplicación debe llevar el statement_timeout de 15 s"

    duraciones: dict[str, float] = {}
    inicio = time.perf_counter()
    try:
        paso = time.perf_counter()
        transaccion.execute(
            "INSERT INTO linea_base_concepto (id, linea_base_id, concepto_id, codigo, cantidad, "
            "precio_unitario, importe) SELECT gen_random_uuid(), %s, %s, 'C-' || g, 1.0000, "
            "10.0000, 10.0000 FROM generate_series(1, %s) AS g",
            (linea_base, concepto, COPIAS_DE_UNA_OBRA_REAL),
        )
        duraciones["copias"] = time.perf_counter() - paso

        paso = time.perf_counter()
        transaccion.execute(
            "INSERT INTO explosion_presupuesto (id, linea_base_id, tipo_partida_id, insumo_id, "
            "cantidad_presupuestada, rendimiento_congelado, costo_unitario, importe_venta) "
            "SELECT gen_random_uuid(), %s, %s, i.id, 1.0000, 0.500000, 10.0000, 5.0000 "
            "FROM insumo i WHERE i.codigo LIKE 'E13-%%'",
            (linea_base, muros),
        )
        duraciones["explosion"] = time.perf_counter() - paso

        paso = time.perf_counter()
        transaccion.execute(
            "UPDATE linea_base SET estado = 'CONGELADA' WHERE id = %s", (linea_base,)
        )
        transaccion.commit()
        duraciones["congelado"] = time.perf_counter() - paso
    except psycopg.errors.QueryCanceled as cancelada:
        pytest.fail(
            f"E-13: el statement_timeout de {STATEMENT_TIMEOUT_DEL_ROL:.0f} s canceló una sentencia "
            f"(57014) tras {time.perf_counter() - inicio:.2f} s; hay que escalar el diseño: {cancelada}"
        )
    total = time.perf_counter() - inicio
    medida = (
        f"E-13: {COPIAS_DE_UNA_OBRA_REAL} copias en {duraciones['copias']:.3f} s, "
        f"{RENGLONES_DE_UNA_OBRA_REAL} renglones en {duraciones['explosion']:.3f} s, "
        f"congelado en {duraciones['congelado']:.3f} s; total {total:.3f} s"
    )
    print(medida)

    with conectar("aplicacion", base_de_prueba) as otra:
        estado = otra.execute(
            "SELECT estado FROM linea_base WHERE id = %s", (linea_base,)
        ).fetchone()
        copias = otra.execute(
            "SELECT count(*), sum(importe) FROM linea_base_concepto WHERE linea_base_id = %s",
            (linea_base,),
        ).fetchone()
        renglones = otra.execute(
            "SELECT count(*), count(DISTINCT insumo_id), sum(importe_venta) "
            "FROM explosion_presupuesto WHERE linea_base_id = %s",
            (linea_base,),
        ).fetchone()
    assert estado == ("CONGELADA",)
    assert copias == (COPIAS_DE_UNA_OBRA_REAL, Decimal("50000.0000")), medida
    assert renglones == (
        RENGLONES_DE_UNA_OBRA_REAL,
        RENGLONES_DE_UNA_OBRA_REAL,
        Decimal("1500.0000"),
    ), medida
    assert max(duraciones.values()) < STATEMENT_TIMEOUT_DEL_ROL, medida
    assert total < STATEMENT_TIMEOUT_DEL_ROL, medida
