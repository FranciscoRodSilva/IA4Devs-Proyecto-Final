"""TKT-072 · Esquema del concepto único por obra y de su aparición por partida: TC-01 a TC-17.

La migración `0010` reduce `concepto` a código, descripción y unidad (único por obra, invariante
13), crea `partida_concepto` con la cantidad, el precio unitario y el importe de cada aparición
(único por concepto y partida, invariante 39) y hace que la copia congelada apunte a la aparición
(`linea_base_concepto.partida_concepto_id`, invariante 14).

PostgreSQL real, esquema por `alembic upgrade head`, escrituras con el rol de aplicación y catálogo
leído con el de migración. Cada rechazo comprueba el `SQLSTATE`, el nombre de la restricción, la
tabla y, después, que las filas no cambiaron. Los importes se construyen desde cadena.
"""

from __future__ import annotations

import re
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

DISPARADOR_DE_COPIAS = "trg_linea_base_concepto_inmutable"
UNIDADES = {"M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"}

# Copia literal de «Infraestructura y esquema» de `sdd/tickets/tkt-072/design.md`, no derivada de
# la migración: restricciones por nombre (sin `NOT NULL`) e índices por nombre.
RESTRICCIONES_ESPERADAS: dict[str, set[str]] = {
    "concepto": {
        "pk_concepto",
        "fk_concepto_obra_id",
        "uq_concepto_obra_id_codigo",
        "ck_concepto_unidad",
    },
    "partida_concepto": {
        "pk_partida_concepto",
        "fk_partida_concepto_concepto_id",
        "fk_partida_concepto_partida_id",
        "uq_partida_concepto_concepto_id_partida_id",
        "ck_partida_concepto_cantidad_no_negativo",
        "ck_partida_concepto_precio_unitario_no_negativo",
        "ck_partida_concepto_importe_no_negativo",
    },
    "linea_base_concepto": {
        "pk_linea_base_concepto",
        "fk_linea_base_concepto_linea_base_id",
        "fk_linea_base_concepto_partida_concepto_id",
        "ck_linea_base_concepto_cantidad_no_negativo",
        "ck_linea_base_concepto_precio_unitario_no_negativo",
        "ck_linea_base_concepto_importe_no_negativo",
    },
}
INDICES_ESPERADOS: dict[str, set[str]] = {
    "concepto": {"pk_concepto", "uq_concepto_obra_id_codigo"},
    "partida_concepto": {
        "pk_partida_concepto",
        "uq_partida_concepto_concepto_id_partida_id",
        "ix_partida_concepto_partida_id",
    },
    "linea_base_concepto": {"pk_linea_base_concepto", "ix_linea_base_concepto_linea_base_id"},
}

# (columna, tipo, precisión, escala, ¿admite nulo?, valor por omisión) de `partida_concepto`.
COLUMNAS_DE_PARTIDA_CONCEPTO: list[tuple[str, str, int | None, int | None, str, str | None]] = [
    ("cantidad", "numeric", 14, 4, "NO", None),
    ("concepto_id", "uuid", None, None, "NO", None),
    ("id", "uuid", None, None, "NO", None),
    ("importe", "numeric", 18, 4, "NO", None),
    ("partida_id", "uuid", None, None, "NO", None),
    ("precio_unitario", "numeric", 14, 4, "NO", None),
]

# --------------------------------------------------------------------------- ayudas


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def filas_como_texto(conexion: Conexion, tabla: str) -> list[str]:
    """Cada fila de la tabla como texto, para comprobar que un rechazo no cambió nada."""
    filas = conexion.execute(
        sql.SQL("SELECT t::text FROM {} t ORDER BY t.id").format(sql.Identifier(tabla))
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def afirmar_rechazo(error: psycopg.Error, sqlstate: str, restriccion: str, tabla: str) -> None:
    """Un rechazo de restricción: el `SQLSTATE`, el nombre de la restricción y la tabla."""
    assert error.sqlstate == sqlstate
    assert error.diag.constraint_name == restriccion
    assert error.diag.table_name == tabla


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


def obra_con_partidas(
    datos: DatosPresupuesto, *, codigo: str = "AP-058-25", areas: tuple[str, ...] = ("Sala",)
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Una obra con un nivel, un área por nombre y una partida en cada área."""
    obra = datos.obra(codigo=codigo)
    nivel = datos.nivel(obra_id=obra)
    partidas = [datos.partida(area_id=datos.area(nivel_id=nivel, nombre=a)) for a in areas]
    return obra, partidas


# --------------------------------------------------------------------------- TC-01


def test_hdu001_esc14_un_codigo_repetido_por_area_es_un_concepto_con_dos_apariciones(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-01 · CA-1 · HDU-001 esc. 14 — `620001` en dos áreas es un concepto con dos apariciones."""
    obra, (partida_101, partida_102) = obra_con_partidas(
        datos_presupuesto, areas=("DEPARTAMENTO 101", "DEPARTAMENTO 102")
    )
    concepto = datos_presupuesto.concepto(obra_id=obra, codigo="620001")
    primera = datos_presupuesto.partida_concepto(
        concepto_id=concepto,
        partida_id=partida_101,
        cantidad=Decimal("77.3900"),
        precio_unitario=Decimal("668.6900"),
        importe=Decimal("51749.9191"),
    )
    segunda = datos_presupuesto.partida_concepto(
        concepto_id=concepto,
        partida_id=partida_102,
        cantidad=Decimal("120.0000"),
        precio_unitario=Decimal("668.6900"),
        importe=Decimal("80242.8000"),
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        conceptos = aplicacion.execute(
            "SELECT id FROM concepto WHERE obra_id = %s AND codigo = '620001'", (obra,)
        ).fetchall()
        apariciones = aplicacion.execute(
            "SELECT id, concepto_id, partida_id, cantidad, precio_unitario, importe "
            "FROM partida_concepto ORDER BY cantidad"
        ).fetchall()
    assert conceptos == [(concepto,)]
    assert apariciones == [
        (
            primera,
            concepto,
            partida_101,
            Decimal("77.3900"),
            Decimal("668.6900"),
            Decimal("51749.9191"),
        ),
        (
            segunda,
            concepto,
            partida_102,
            Decimal("120.0000"),
            Decimal("668.6900"),
            Decimal("80242.8000"),
        ),
    ]


# --------------------------------------------------------------------------- TC-02 y TC-03


def test_tkt072_ca02_codigo_repetido_en_la_obra_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-02 · CA-2 esc. 1 · invariante 13 — dos conceptos `620001` en la obra violan `uq_concepto_obra_id_codigo`."""
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    original = datos_presupuesto.concepto(obra_id=obra, codigo="620001")

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.concepto(obra_id=obra, codigo="620001")

    afirmar_rechazo(rechazo.value, "23505", "uq_concepto_obra_id_codigo", "concepto")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        sigue = aplicacion.execute("SELECT id FROM concepto WHERE codigo = '620001'").fetchall()
    assert sigue == [(original,)]


def test_tkt072_ca02_el_mismo_codigo_en_otra_obra_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-03 · CA-2 esc. 2 — `620001` entra en las obras `AP-058-25` y `AP-059-25`."""
    obra_a = datos_presupuesto.obra(codigo="AP-058-25")
    obra_b = datos_presupuesto.obra(codigo="AP-059-25")
    datos_presupuesto.concepto(obra_id=obra_a, codigo="620001")
    datos_presupuesto.concepto(obra_id=obra_b, codigo="620001")

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardados = aplicacion.execute("SELECT obra_id, codigo FROM concepto").fetchall()
    assert sorted(guardados) == sorted([(obra_a, "620001"), (obra_b, "620001")])


# --------------------------------------------------------------------------- TC-04


def test_hdu001_esc14_cada_aparicion_conserva_su_precio(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-04 · CA-3 · HDU-001 esc. 14 — `620040-A` vale 414.93 en un área y 428.19 en otra; el concepto no lleva precio."""
    obra, (partida_a, partida_b) = obra_con_partidas(
        datos_presupuesto, areas=("DEPARTAMENTO 101", "DEPARTAMENTO 102")
    )
    concepto = datos_presupuesto.concepto(obra_id=obra, codigo="620040-A")
    datos_presupuesto.partida_concepto(
        concepto_id=concepto, partida_id=partida_a, precio_unitario=Decimal("414.9300")
    )
    datos_presupuesto.partida_concepto(
        concepto_id=concepto, partida_id=partida_b, precio_unitario=Decimal("428.1900")
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        precios = aplicacion.execute(
            "SELECT partida_id, precio_unitario FROM partida_concepto WHERE concepto_id = %s",
            (concepto,),
        ).fetchall()
        columnas = aplicacion.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'concepto'"
        ).fetchall()
    assert sorted(precios) == sorted(
        [(partida_a, Decimal("414.9300")), (partida_b, Decimal("428.1900"))]
    )
    assert {str(fila[0]) for fila in columnas} == {
        "id",
        "obra_id",
        "codigo",
        "descripcion",
        "unidad",
    }


# --------------------------------------------------------------------------- TC-05


def test_tkt072_ca04_aparicion_repetida_en_la_partida_la_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-05 · CA-4 esc. 1 · invariante 39 — el mismo concepto dos veces en una partida viola `uq_partida_concepto_concepto_id_partida_id`."""
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    nivel = datos_presupuesto.nivel(obra_id=obra)
    area = datos_presupuesto.area(nivel_id=nivel)
    partida = datos_presupuesto.partida(area_id=area)
    otra_partida_del_area = datos_presupuesto.partida(area_id=area, orden=2)
    concepto = datos_presupuesto.concepto(obra_id=obra, codigo="620001")
    original = datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=partida)

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=partida)

    afirmar_rechazo(
        rechazo.value,
        "23505",
        "uq_partida_concepto_concepto_id_partida_id",
        "partida_concepto",
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        en_la_partida = aplicacion.execute(
            "SELECT id FROM partida_concepto WHERE partida_id = %s", (partida,)
        ).fetchall()
    assert en_la_partida == [(original,)]

    # Control: el mismo concepto en otra partida del mismo área sí entra.
    otra = datos_presupuesto.partida_concepto(
        concepto_id=concepto, partida_id=otra_partida_del_area
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "partida_concepto") == 2
        assert aplicacion.execute(
            "SELECT id FROM partida_concepto WHERE partida_id = %s", (otra_partida_del_area,)
        ).fetchall() == [(otra,)]


# --------------------------------------------------------------------------- TC-06


@pytest.mark.parametrize(
    ("padre", "restriccion"),
    [
        ("concepto", "fk_partida_concepto_concepto_id"),
        ("partida", "fk_partida_concepto_partida_id"),
    ],
)
def test_tkt072_ca04_aparicion_sin_padre_la_rechaza_la_base(
    padre: str,
    restriccion: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-06 · CA-4 esc. 2 — una aparición de un concepto o de una partida que no existen responde `23503`."""
    obra, (partida,) = obra_con_partidas(datos_presupuesto)
    concepto = datos_presupuesto.concepto(obra_id=obra)
    inexistente = uuid.uuid4()

    with pytest.raises(psycopg.errors.ForeignKeyViolation) as rechazo:
        if padre == "concepto":
            datos_presupuesto.partida_concepto(concepto_id=inexistente, partida_id=partida)
        else:
            datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=inexistente)

    afirmar_rechazo(rechazo.value, "23503", restriccion, "partida_concepto")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "partida_concepto") == 0


# --------------------------------------------------------------------------- TC-07 y TC-08

COLUMNAS_NO_NEGATIVAS = ["cantidad", "precio_unitario", "importe"]


@pytest.mark.parametrize("columna", COLUMNAS_NO_NEGATIVAS)
def test_tkt072_ca04_negativo_lo_rechaza_la_base(
    columna: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-07 · CA-4 esc. 3 · invariante 8 — `-0.0001` en cantidad, precio o importe responde `23514`."""
    obra, (partida,) = obra_con_partidas(datos_presupuesto)
    concepto = datos_presupuesto.concepto(obra_id=obra)

    valor: dict[str, Any] = {columna: Decimal("-0.0001")}

    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=partida, **valor)

    afirmar_rechazo(
        rechazo.value, "23514", f"ck_partida_concepto_{columna}_no_negativo", "partida_concepto"
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "partida_concepto") == 0


@pytest.mark.parametrize("columna", COLUMNAS_NO_NEGATIVAS)
def test_tkt072_ca04_cero_se_acepta(
    columna: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-08 · CA-4 esc. 3 · invariante 8 — con `0.0000` en la misma columna la fila entra."""
    obra, (partida,) = obra_con_partidas(datos_presupuesto)
    concepto = datos_presupuesto.concepto(obra_id=obra)

    valor: dict[str, Any] = {columna: Decimal("0.0000")}

    aparicion = datos_presupuesto.partida_concepto(
        concepto_id=concepto, partida_id=partida, **valor
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            sql.SQL("SELECT {} FROM partida_concepto WHERE id = %s").format(
                sql.Identifier(columna)
            ),
            (aparicion,),
        ).fetchone()
    assert guardado == (Decimal("0.0000"),)


# --------------------------------------------------------------------------- TC-09


@pytest.mark.parametrize(
    ("padre", "restriccion"),
    [
        ("concepto", "fk_partida_concepto_concepto_id"),
        ("partida", "fk_partida_concepto_partida_id"),
    ],
)
def test_tkt072_ca05_no_se_borra_un_padre_con_apariciones(
    padre: str,
    restriccion: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-09 · CA-5 · `P-2` — borrar un concepto o una partida con apariciones responde `23001` y nada cambia."""
    obra, (partida,) = obra_con_partidas(datos_presupuesto)
    concepto = datos_presupuesto.concepto(obra_id=obra)
    datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=partida)
    identificador = concepto if padre == "concepto" else partida
    tablas = ("concepto", "partida", "partida_concepto")

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        antes = {tabla: filas_como_texto(aplicacion, tabla) for tabla in tablas}

        with pytest.raises(psycopg.errors.RestrictViolation) as rechazo:
            aplicacion.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(padre)),
                (identificador,),
            )

        afirmar_rechazo(rechazo.value, "23001", restriccion, "partida_concepto")
        despues = {tabla: filas_como_texto(aplicacion, tabla) for tabla in tablas}
    assert all(len(filas) == 1 for filas in antes.values())
    assert despues == antes


# --------------------------------------------------------------------------- TC-10


def test_hdu001_esc14_la_copia_alcanza_partida_area_y_nivel(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-10 · CA-6 esc. 1 · HDU-001 esc. 14 — desde la copia se llega a la aparición, la partida, el área y el nivel."""
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra)
    nivel = datos_presupuesto.nivel(obra_id=obra, nombre="NIVEL 3")
    area = datos_presupuesto.area(nivel_id=nivel, nombre="DEPARTAMENTO 312")
    partida = datos_presupuesto.partida(area_id=area)
    concepto = datos_presupuesto.concepto(obra_id=obra, codigo="620001")
    aparicion = datos_presupuesto.partida_concepto(concepto_id=concepto, partida_id=partida)
    copia = datos_presupuesto.copia_concepto(
        linea_base_id=linea_base, partida_concepto_id=aparicion, codigo="620001"
    )

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        alcanzada = aplicacion.execute(
            "SELECT pc.id, p.id, a.nombre, n.nombre FROM linea_base_concepto c "
            "JOIN partida_concepto pc ON pc.id = c.partida_concepto_id "
            "JOIN partida p ON p.id = pc.partida_id "
            "JOIN area a ON a.id = p.area_id "
            "JOIN nivel n ON n.id = a.nivel_id WHERE c.id = %s",
            (copia,),
        ).fetchall()
    assert alcanzada == [(aparicion, partida, "DEPARTAMENTO 312", "NIVEL 3")]


# --------------------------------------------------------------------------- TC-11 y TC-12


def test_hdu001_esc18_insertar_en_la_copia_congelada_lo_rechaza_el_disparador(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-11 · CA-6 esc. 2 · HDU-001 esc. 18 · RN-01 — otra copia en una línea base `CONGELADA` responde `IN001`."""
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        antes = filas_como_texto(aplicacion, "linea_base_concepto")
        with pytest.raises(psycopg.Error) as rechazo:
            aplicacion.execute(
                "INSERT INTO linea_base_concepto (id, linea_base_id, partida_concepto_id, "
                "codigo, cantidad, precio_unitario, importe) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    uuid.uuid4(),
                    copias.linea_base_id,
                    copias.partida_concepto_id,
                    "620099",
                    Decimal("1.0000"),
                    Decimal("2.0000"),
                    Decimal("2.0000"),
                ),
            )
        despues = filas_como_texto(aplicacion, "linea_base_concepto")

    error = rechazo.value
    assert error.sqlstate == "IN001"
    assert (error.diag.message_primary or "").startswith("RN-01:")
    assert error.diag.constraint_name == DISPARADOR_DE_COPIAS
    assert error.diag.table_name == "linea_base_concepto"
    assert len(antes) == 1
    assert despues == antes


SENTENCIAS_SOBRE_LA_COPIA = {
    "UPDATE": "UPDATE linea_base_concepto SET cantidad = 999.0000 WHERE id = %s",
    "DELETE": "DELETE FROM linea_base_concepto WHERE id = %s",
    "TRUNCATE": "TRUNCATE linea_base_concepto",
}


@pytest.mark.parametrize("sentencia", list(SENTENCIAS_SOBRE_LA_COPIA))
def test_hdu001_esc18_modificar_borrar_o_truncar_la_copia_responde_42501(
    sentencia: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-12 · CA-6 esc. 2 · HDU-001 esc. 18 · RN-01 — `UPDATE`, `DELETE` y `TRUNCATE` de la aplicación sobre la copia responden `42501`."""
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    texto = SENTENCIAS_SOBRE_LA_COPIA[sentencia]
    parametros = None if sentencia == "TRUNCATE" else (copias.copia_id,)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as rechazo:
            aplicacion.execute(texto, parametros)
        intacta = aplicacion.execute(
            "SELECT cantidad, precio_unitario, importe FROM linea_base_concepto WHERE id = %s",
            (copias.copia_id,),
        ).fetchone()

    assert rechazo.value.sqlstate == "42501"
    assert "linea_base_concepto" in (rechazo.value.diag.message_primary or "")
    assert intacta == (Decimal("100.0000"), Decimal("250.0000"), Decimal("25000.0000"))


# --------------------------------------------------------------------------- TC-13


def test_hdu001_esc14_copia_sin_aparicion_la_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-13 · CA-6 esc. 3 · HDU-001 esc. 14 — una copia que apunta a una aparición inexistente responde `23503`."""
    borrador = datos_presupuesto.linea_base(estado="BORRADOR")

    with pytest.raises(psycopg.errors.ForeignKeyViolation) as rechazo:
        datos_presupuesto.copia_concepto(linea_base_id=borrador, partida_concepto_id=uuid.uuid4())

    afirmar_rechazo(
        rechazo.value,
        "23503",
        "fk_linea_base_concepto_partida_concepto_id",
        "linea_base_concepto",
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "linea_base_concepto") == 0


# --------------------------------------------------------------------------- TC-14 y TC-15


def test_tkt072_ca07_privilegios_de_concepto_aparicion_y_copia(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-14 · CA-7 esc. 1 — la aplicación y la lectura tienen exactamente los privilegios del diseño; nadie trunca."""
    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = {
            tabla: privilegios(migracion, tabla, "aplicacion")
            for tabla in ("concepto", "partida_concepto", "linea_base_concepto")
        }
        de_lectura = {
            tabla: privilegios(migracion, tabla, "lectura")
            for tabla in ("concepto", "partida_concepto", "linea_base_concepto")
        }
        selecciona = migracion.execute(
            "SELECT has_table_privilege('cimenta_aplicacion', 'partida_concepto', 'SELECT')"
        ).fetchone()
        trunca = migracion.execute(
            "SELECT has_table_privilege('cimenta_aplicacion', 'partida_concepto', 'TRUNCATE')"
        ).fetchone()

    assert de_aplicacion == {
        "concepto": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "partida_concepto": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "linea_base_concepto": {"SELECT", "INSERT"},
    }
    assert de_lectura == {
        "concepto": {"SELECT"},
        "partida_concepto": {"SELECT"},
        "linea_base_concepto": {"SELECT"},
    }
    assert selecciona == (True,), "La precondición exige SELECT sobre partida_concepto"
    assert trunca == (False,)


def test_tkt072_ca07_el_rol_de_lectura_no_escribe_apariciones(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-15 · CA-7 esc. 2 — un `INSERT` en `partida_concepto` con el rol de lectura responde `42501`."""
    obra, (partida,) = obra_con_partidas(datos_presupuesto)
    concepto = datos_presupuesto.concepto(obra_id=obra)

    with conectar("lectura", base_de_prueba) as lectura:
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as rechazo:
            lectura.execute(
                "INSERT INTO partida_concepto (id, concepto_id, partida_id, cantidad, "
                "precio_unitario, importe) VALUES (%s, %s, %s, 1.0000, 2.0000, 2.0000)",
                (uuid.uuid4(), concepto, partida),
            )
        assert contar(lectura, "partida_concepto") == 0

    assert rechazo.value.sqlstate == "42501"
    assert "partida_concepto" in (rechazo.value.diag.message_primary or "")


# --------------------------------------------------------------------------- TC-16


def test_tkt072_car1_concepto_conserva_su_unicidad_y_su_unidad(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-16 · CA-R1 · invariante 13 — `concepto` sigue siendo único por obra y código y con las ocho unidades."""
    with conectar("migracion", base_de_prueba) as migracion:
        unica = migracion.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'uq_concepto_obra_id_codigo' AND conrelid = 'concepto'::regclass"
        ).fetchone()
        unidad = migracion.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_concepto_unidad' AND conrelid = 'concepto'::regclass"
        ).fetchone()

    assert unica == ("UNIQUE (obra_id, codigo)",)
    assert unidad is not None
    assert set(re.findall(r"'([A-Z0-9]+)'::text", str(unidad[0]))) == UNIDADES


# --------------------------------------------------------------------------- TC-17


def test_tkt072_car1_restricciones_indices_y_columnas_con_nombre(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-17 · CA-R1, CA-6 · invariantes 8, 13, 14 y 39 — restricciones, índices, columnas y disparador, con su nombre."""
    tablas = list(RESTRICCIONES_ESPERADAS)
    with conectar("migracion", base_de_prueba) as migracion:
        restricciones: dict[str, set[str]] = {tabla: set() for tabla in tablas}
        for tabla, nombre in migracion.execute(
            "SELECT t.relname, c.conname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
            "AND c.contype <> 'n'",
            (tablas,),
        ).fetchall():
            restricciones[str(tabla)].add(str(nombre))
        indices: dict[str, set[str]] = {tabla: set() for tabla in tablas}
        for tabla, nombre in migracion.execute(
            "SELECT tablename, indexname FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = ANY(%s)",
            (tablas,),
        ).fetchall():
            indices[str(tabla)].add(str(nombre))
        columnas = [
            tuple(fila)
            for fila in migracion.execute(
                "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable, "
                "column_default FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'partida_concepto' "
                "ORDER BY column_name"
            ).fetchall()
        ]
        borrado = {
            str(nombre): str(tipo)
            for nombre, tipo in migracion.execute(
                "SELECT conname, confdeltype FROM pg_constraint WHERE conname = ANY(%s)",
                (
                    [
                        "fk_partida_concepto_concepto_id",
                        "fk_partida_concepto_partida_id",
                        "fk_linea_base_concepto_partida_concepto_id",
                    ],
                ),
            ).fetchall()
        }
        disparadores = migracion.execute(
            "SELECT t.tgname, c.relname, p.proname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace "
            "AND c.relname = 'linea_base_concepto'"
        ).fetchall()

    assert restricciones == RESTRICCIONES_ESPERADAS
    assert indices == INDICES_ESPERADOS
    assert columnas == COLUMNAS_DE_PARTIDA_CONCEPTO
    assert borrado == {
        "fk_partida_concepto_concepto_id": "r",
        "fk_partida_concepto_partida_id": "r",
        "fk_linea_base_concepto_partida_concepto_id": "r",
    }
    assert disparadores == [
        (DISPARADOR_DE_COPIAS, "linea_base_concepto", "presupuesto_proteger_copia_congelada")
    ]
