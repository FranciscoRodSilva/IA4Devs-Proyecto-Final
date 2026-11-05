"""Estructura y catálogos de TKT-011a.

La migración `0006` crea doce tablas del módulo `presupuesto`: `empresa`, `obra`, `tipo_partida`,
`insumo`, `nivel`, `area`, `partida`, `concepto`, `precio_insumo`, `apu`, `apu_insumo` y
`apu_cargo`, con sus `CHECK`, sus `UNIQUE` y sus claves foráneas. `COLUMNAS_ESPERADAS` y las
listas de casos son tablas de datos que recorren las pruebas.

PostgreSQL real, esquema por `alembic upgrade head` y rol de aplicación para escribir; el
catálogo se lee con el rol de migración. Un rechazo comprueba el `SQLSTATE`, el nombre de la
restricción (o la columna en `23502`), la tabla, y después que la tabla no cambió.

`COLUMNAS_ESPERADAS` es copia literal de la «Tabla de nulabilidad» de
`sdd/tickets/tkt-011/design.md` (`PA-T10`): una fila por columna con su tipo, su nulabilidad y su
valor por omisión.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]
Crear = Callable[["DatosPresupuesto"], uuid.UUID]

# --------------------------------------------------------------------------- la forma esperada

# (columna, tipo, ¿admite nulo?, valor por omisión), tal como lo dice la tabla de nulabilidad.
FilaDeTabla = tuple[str, str, str, str | None]

# `information_schema.columns` entrega, para cada tipo del diseño, estas tres cifras.
TIPOS: dict[str, tuple[str, int | None, int | None]] = {
    "uuid": ("uuid", None, None),
    "text": ("text", None, None),
    "boolean": ("boolean", None, None),
    "date": ("date", None, None),
    "timestamptz": ("timestamp with time zone", None, None),
    "smallint": ("smallint", 16, 0),
    "integer": ("integer", 32, 0),
    "numeric(9,6)": ("numeric", 9, 6),
    "numeric(14,4)": ("numeric", 14, 4),
    "numeric(18,4)": ("numeric", 18, 4),
    "numeric(18,6)": ("numeric", 18, 6),
}

TABLAS_DE_NULABILIDAD: dict[str, tuple[FilaDeTabla, ...]] = {
    "empresa": (
        ("id", "uuid", "no", None),
        ("nombre", "text", "no", None),
        ("rfc", "text", "no", None),
        ("activa", "boolean", "no", None),
        ("dias_semana_laboral", "smallint", "no", "6"),
    ),
    "obra": (
        ("id", "uuid", "no", None),
        ("empresa_id", "uuid", "no", None),
        ("codigo", "text", "no", None),
        ("nombre", "text", "no", None),
        ("domicilio", "text", "no", None),
        ("tipo_contrato", "text", "no", None),
        ("retencion_destajo_pct", "numeric(9,6)", "no", None),
        ("fondo_garantia_pct", "numeric(9,6)", "no", None),
        ("iva_acreditable", "boolean", "no", None),
        ("umbral_alerta_pct", "numeric(9,6)", "sí", None),
        ("estado", "text", "no", None),
        ("creado_en", "timestamptz", "no", "now()"),
        ("creado_por_id", "uuid", "no", None),
        ("actualizado_en", "timestamptz", "sí", None),
        ("actualizado_por_id", "uuid", "sí", None),
    ),
    "tipo_partida": (
        ("id", "uuid", "no", None),
        ("clave", "text", "no", None),
        ("nombre", "text", "no", None),
    ),
    "nivel": (
        ("id", "uuid", "no", None),
        ("obra_id", "uuid", "no", None),
        ("nombre", "text", "no", None),
        ("orden", "integer", "no", None),
    ),
    "area": (
        ("id", "uuid", "no", None),
        ("nivel_id", "uuid", "no", None),
        ("nombre", "text", "no", None),
        ("tipo_unidad", "text", "no", None),
    ),
    "partida": (
        ("id", "uuid", "no", None),
        ("area_id", "uuid", "no", None),
        ("tipo_partida_id", "uuid", "no", None),
        ("orden", "integer", "no", None),
    ),
    "concepto": (
        ("id", "uuid", "no", None),
        ("obra_id", "uuid", "no", None),
        ("codigo", "text", "no", None),
        ("descripcion", "text", "no", None),
        ("unidad", "text", "no", None),
    ),
    "partida_concepto": (
        ("id", "uuid", "no", None),
        ("concepto_id", "uuid", "no", None),
        ("partida_id", "uuid", "no", None),
        ("cantidad", "numeric(14,4)", "no", None),
        ("precio_unitario", "numeric(14,4)", "no", None),
        ("importe", "numeric(18,4)", "no", None),
    ),
    "insumo": (
        ("id", "uuid", "no", None),
        ("codigo", "text", "no", None),
        ("descripcion", "text", "no", None),
        ("tipo", "text", "no", None),
        ("unidad", "text", "no", None),
        ("activo", "boolean", "no", None),
        ("creado_en_importacion", "boolean", "no", None),
    ),
    "precio_insumo": (
        ("id", "uuid", "no", None),
        ("insumo_id", "uuid", "no", None),
        ("obra_id", "uuid", "sí", None),
        ("costo_unitario", "numeric(14,4)", "no", None),
        ("vigente_desde", "date", "no", None),
        ("vigente_hasta", "date", "sí", None),
    ),
    "apu": (
        ("id", "uuid", "no", None),
        ("concepto_id", "uuid", "no", None),
        ("fecha_analisis", "date", "no", None),
        ("analista", "text", "no", None),
        ("costo_material", "numeric(14,4)", "no", None),
        ("costo_mano_obra", "numeric(14,4)", "no", None),
        ("costo_directo", "numeric(14,4)", "no", None),
        ("total_cargos", "numeric(14,4)", "no", None),
        ("total_indirectos", "numeric(14,4)", "no", None),
        ("precio_unitario", "numeric(14,4)", "no", None),
    ),
    "apu_insumo": (
        ("id", "uuid", "no", None),
        ("apu_id", "uuid", "no", None),
        ("insumo_id", "uuid", "no", None),
        ("costo_unitario", "numeric(14,4)", "no", None),
        ("rendimiento", "numeric(18,6)", "no", None),
        ("cargo", "numeric(14,4)", "no", None),
    ),
    "apu_cargo": (
        ("id", "uuid", "no", None),
        ("apu_id", "uuid", "no", None),
        ("tipo", "text", "no", None),
        ("porcentaje", "numeric(9,6)", "no", None),
        ("base_calculo", "numeric(14,4)", "no", None),
        ("importe", "numeric(14,4)", "no", None),
    ),
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

# (tabla padre, tabla hija, restricción que impide borrar al padre con hijos). Incluye las de
# precio de insumo y las de APU.
PADRES_CON_HIJOS: list[tuple[str, str, str]] = [
    ("empresa", "obra", "fk_obra_empresa_id"),
    ("obra", "nivel", "fk_nivel_obra_id"),
    ("insumo", "precio_insumo", "fk_precio_insumo_insumo_id"),
    ("obra", "precio_insumo", "fk_precio_insumo_obra_id"),
    ("concepto", "apu", "fk_apu_concepto_id"),
    ("apu", "apu_insumo", "fk_apu_insumo_apu_id"),
    ("insumo", "apu_insumo", "fk_apu_insumo_insumo_id"),
    ("apu", "apu_cargo", "fk_apu_cargo_apu_id"),
]


def _empresa_con_una_obra(datos: DatosPresupuesto) -> uuid.UUID:
    empresa_id = datos.empresa()
    datos.obra(empresa_id=empresa_id)
    return empresa_id


def _obra_con_un_nivel(datos: DatosPresupuesto) -> uuid.UUID:
    obra_id = datos.obra()
    datos.nivel(obra_id=obra_id)
    return obra_id


def _insumo_con_un_precio(datos: DatosPresupuesto) -> uuid.UUID:
    insumo_id = datos.insumo()
    datos.precio_insumo(insumo_id=insumo_id)
    return insumo_id


def _obra_con_un_precio(datos: DatosPresupuesto) -> uuid.UUID:
    obra_id = datos.obra()
    datos.precio_insumo(obra_id=obra_id)
    return obra_id


def _concepto_con_un_apu(datos: DatosPresupuesto) -> uuid.UUID:
    concepto_id = datos.concepto()
    datos.apu(concepto_id=concepto_id)
    return concepto_id


def _apu_con_un_insumo(datos: DatosPresupuesto) -> uuid.UUID:
    apu_id = datos.apu()
    datos.apu_insumo(apu_id=apu_id)
    return apu_id


def _insumo_con_un_apu_insumo(datos: DatosPresupuesto) -> uuid.UUID:
    insumo_id = datos.insumo()
    datos.apu_insumo(insumo_id=insumo_id)
    return insumo_id


def _apu_con_un_cargo(datos: DatosPresupuesto) -> uuid.UUID:
    apu_id = datos.apu()
    datos.apu_cargo(apu_id=apu_id)
    return apu_id


# Cómo crear un padre que ya tiene un hijo, indexado por la restricción que impide borrarlo;
# devuelve el `id` del padre.
PADRE_CON_UN_HIJO: dict[str, Callable[[DatosPresupuesto], uuid.UUID]] = {
    "fk_obra_empresa_id": _empresa_con_una_obra,
    "fk_nivel_obra_id": _obra_con_un_nivel,
    "fk_precio_insumo_insumo_id": _insumo_con_un_precio,
    "fk_precio_insumo_obra_id": _obra_con_un_precio,
    "fk_apu_concepto_id": _concepto_con_un_apu,
    "fk_apu_insumo_apu_id": _apu_con_un_insumo,
    "fk_apu_insumo_insumo_id": _insumo_con_un_apu_insumo,
    "fk_apu_cargo_apu_id": _apu_con_un_cargo,
}

UNIDADES = ("M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL")
ESTADOS_DE_OBRA = ("PLANEACION", "ACTIVA", "SUSPENDIDA", "CERRADA")
TIPOS_DE_INSUMO = ("MATERIAL", "MANO_OBRA", "HERRAMIENTA", "CONSUMIBLE")
TIPOS_DE_CARGO = (
    "HERRAMIENTA_MENOR",
    "ANDAMIAJE",
    "DESPERDICIO",
    "VIATICOS",
    "IVA",
    "INDIRECTOS",
    "UTILIDAD",
)

# --------------------------------------------------------------------------- ayudas


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def contar_donde(conexion: Conexion, tabla: str, columna: str, valor: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {} WHERE {} = %s").format(
            sql.Identifier(tabla), sql.Identifier(columna)
        ),
        (valor,),
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def afirmar_rechazo(error: psycopg.Error, sqlstate: str, restriccion: str, tabla: str) -> None:
    """Un rechazo de restricción: el `SQLSTATE`, el nombre de la restricción y la tabla."""
    assert error.sqlstate == sqlstate
    assert error.diag.constraint_name == restriccion
    assert error.diag.table_name == tabla


# --------------------------------------------------------------------------- TC-01


@pytest.mark.parametrize("tabla", list(COLUMNAS_ESPERADAS))
def test_tkt011_ca01_tablas_de_estructura_con_su_forma(
    tabla: str, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-01 · CA-1 esc. 1 · PA-T10 — la tabla existe con las columnas, tipos y nulabilidad del diseño."""
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT column_name, data_type, numeric_precision, numeric_scale, is_nullable, "
            "column_default FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY column_name",
            (tabla,),
        ).fetchall()

    assert filas, f"La tabla {tabla} no existe: la migración 0006 no la crea."
    assert [tuple(fila) for fila in filas] == COLUMNAS_ESPERADAS[tabla]


# --------------------------------------------------------------------------- TC-02


def test_tkt011_ca01_claves_foraneas_sin_cascada(
    base_de_prueba: str,
    conectar: Conectar,
    estructura_esperada: dict[str, dict[str, tuple[Any, ...]]],
) -> None:
    """TC-02 · CA-1 · PA-T8 — toda clave foránea de estas tablas es `ON DELETE RESTRICT`.

    Se compara el conjunto exacto de claves foráneas con su `confdeltype`, para que una clave que
    falte no deje la afirmación vacía. Las claves esperadas son las `f` de la estructura.
    """
    claves_esperadas = {
        nombre for por_tipo in estructura_esperada.values() for nombre in por_tipo.get("f", ())
    }
    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute(
            "SELECT c.conname, c.confdeltype FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE c.contype = 'f' AND t.relnamespace = 'public'::regnamespace "
            "AND t.relname = ANY(%s) ORDER BY c.conname",
            # Las tablas de `estructura_esperada`: `partida_concepto` es de `0010` (TKT-072) y sus
            # claves las prueba `test_tkt072_esquema.py` (TC-17).
            (list(estructura_esperada),),
        ).fetchall()

    assert {str(nombre) for nombre, _ in filas} == claves_esperadas
    assert {str(tipo) for _, tipo in filas} == {"r"}


@pytest.mark.parametrize(
    ("padre", "hija", "restriccion"),
    PADRES_CON_HIJOS,
    ids=[f"{padre}_con_{hija}" for padre, hija, _ in PADRES_CON_HIJOS],
)
def test_tkt011_ca01_borrar_el_padre_con_hijos_lo_rechaza_la_clave_foranea(
    padre: str,
    hija: str,
    restriccion: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-02 · CA-1 · PA-T8 — borrar un padre con un hijo lo rechaza `ON DELETE RESTRICT`.

    PostgreSQL responde `23001` (`restrict_violation`) con `RESTRICT`, no `23503`, que es el de
    la inserción de un hijo huérfano. El padre y el hijo siguen intactos.
    """
    padre_id = PADRE_CON_UN_HIJO[restriccion](datos_presupuesto)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        # Los padres sembrados por `0008` (la empresa) cuentan en la tabla: se compara con el
        # recuento previo y se comprueba que el padre concreto sigue por su `id`.
        padres_antes = contar(aplicacion, padre)
        with pytest.raises(psycopg.errors.RestrictViolation) as rechazo:
            aplicacion.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(padre)),
                (padre_id,),
            )

        afirmar_rechazo(rechazo.value, "23001", restriccion, hija)
        assert contar(aplicacion, padre) == padres_antes
        assert contar_donde(aplicacion, padre, "id", str(padre_id)) == 1
        assert contar(aplicacion, hija) == 1


# --------------------------------------------------------------------------- TC-03


def test_tkt011_ca01_obra_sin_empresa_la_rechaza_not_null(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-03 · CA-1 esc. 2 — insertar una obra sin `empresa_id` viola `NOT NULL` sobre esa columna."""
    creado_por_id = datos_presupuesto.usuario()

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.NotNullViolation) as rechazo:
            aplicacion.execute(
                "INSERT INTO obra (id, codigo, nombre, domicilio, tipo_contrato, "
                "retencion_destajo_pct, fondo_garantia_pct, iva_acreditable, estado, creado_por_id) "
                "VALUES (%s, 'AP-058-25', 'Obra', 'Calle 1', 'PRECIO_ALZADO_MAXIMO_GARANTIZADO', "
                "0.05, 0.05, true, 'PLANEACION', %s)",
                (uuid.uuid4(), creado_por_id),
            )

        assert rechazo.value.sqlstate == "23502"
        assert rechazo.value.diag.column_name == "empresa_id"
        assert rechazo.value.diag.table_name == "obra"
        assert contar(aplicacion, "obra") == 0


# --------------------------------------------------------------------------- TC-04 y TC-05


def test_tkt011_ca02_dias_semana_laboral_vale_seis_por_omision(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-04 · CA-2 esc. 1 · PA-22 · PA-T2 — una empresa sin `dias_semana_laboral` guarda seis; es `smallint NOT NULL`."""
    empresa_id = datos_presupuesto.empresa()

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT dias_semana_laboral FROM empresa WHERE id = %s", (empresa_id,)
        ).fetchone()
    with conectar("migracion", base_de_prueba) as migracion:
        columna = migracion.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'empresa' "
            "AND column_name = 'dias_semana_laboral'"
        ).fetchone()

    assert guardado == (6,)
    assert columna == ("smallint", "NO")


def test_tkt011_ca02_obra_con_empresa_inexistente_la_rechaza_la_clave_foranea(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-05 · CA-2 esc. 2 · ADR-008 — una obra con un `empresa_id` que no existe viola `fk_obra_empresa_id`."""
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as rechazo:
        datos_presupuesto.obra(empresa_id=uuid.uuid4())

    afirmar_rechazo(rechazo.value, "23503", "fk_obra_empresa_id", "obra")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "obra") == 0


# --------------------------------------------------------------------------- TC-06 y TC-07


def test_tkt011_ca03_codigo_de_obra_repetido_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-06 · CA-3 esc. 1 · HDU-001 esc. 3 — dos obras `AP-058-25` violan `uq_obra_codigo`."""
    original = datos_presupuesto.obra(codigo="AP-058-25")

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.obra(codigo="AP-058-25")

    afirmar_rechazo(rechazo.value, "23505", "uq_obra_codigo", "obra")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar_donde(aplicacion, "obra", "codigo", "AP-058-25") == 1
        assert contar(aplicacion, "obra") == 1
        sigue = aplicacion.execute("SELECT id FROM obra WHERE codigo = 'AP-058-25'").fetchone()
    assert sigue == (original,)


def test_tkt011_ca03_otro_codigo_de_obra_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-07 · CA-3 esc. 2 · HDU-001 esc. 3 — `AP-059-25` entra junto a `AP-058-25`."""
    datos_presupuesto.obra(codigo="AP-058-25")
    datos_presupuesto.obra(codigo="AP-059-25")

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        codigos = aplicacion.execute("SELECT codigo FROM obra ORDER BY codigo").fetchall()
    assert codigos == [("AP-058-25",), ("AP-059-25",)]


# --------------------------------------------------------------------------- TC-08 y TC-09

# (tabla, restricción, cómo crear una fila con el valor ajeno).
FUERA_DEL_CONJUNTO: list[tuple[str, str, Crear]] = [
    ("obra", "ck_obra_estado", lambda datos: datos.obra(estado="BORRADA")),
    ("obra", "ck_obra_tipo_contrato", lambda datos: datos.obra(tipo_contrato="OTRO")),
    ("insumo", "ck_insumo_tipo", lambda datos: datos.insumo(tipo="EQUIPO")),
    ("apu_cargo", "ck_apu_cargo_tipo", lambda datos: datos.apu_cargo(tipo="PROPINA")),
]


@pytest.mark.parametrize(
    ("tabla", "restriccion", "crear"),
    FUERA_DEL_CONJUNTO,
    ids=[restriccion for _, restriccion, _ in FUERA_DEL_CONJUNTO],
)
def test_tkt011_ca08_valor_fuera_del_conjunto_cerrado_lo_rechaza_la_base(
    tabla: str,
    restriccion: str,
    crear: Crear,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-08 · CA-8 esc. 1 · ADR-030 — un valor fuera del conjunto cerrado responde `23514` con su `CHECK`."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        crear(datos_presupuesto)

    afirmar_rechazo(rechazo.value, "23514", restriccion, tabla)
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, tabla) == 0


# (tabla, columna del conjunto cerrado, valor admitido, cómo crear una fila con ese valor).
ADMITIDOS: list[tuple[str, str, str, Crear]] = [
    *[
        ("obra", "estado", estado, lambda datos, estado=estado: datos.obra(estado=estado))
        for estado in ESTADOS_DE_OBRA
    ],
    *[
        ("insumo", "tipo", tipo, lambda datos, tipo=tipo: datos.insumo(tipo=tipo))
        for tipo in TIPOS_DE_INSUMO
    ],
    *[
        ("apu_cargo", "tipo", tipo, lambda datos, tipo=tipo: datos.apu_cargo(tipo=tipo))
        for tipo in TIPOS_DE_CARGO
    ],
]


@pytest.mark.parametrize(
    ("tabla", "columna", "valor", "crear"),
    ADMITIDOS,
    ids=[f"{tabla}_{valor}" for tabla, _, valor, _ in ADMITIDOS],
)
def test_tkt011_ca08_valores_admitidos_se_aceptan(
    tabla: str,
    columna: str,
    valor: str,
    crear: Crear,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-09 · CA-8 esc. 2 — cada estado de obra, tipo de insumo y tipo de cargo del conjunto cerrado entra."""
    identificador = crear(datos_presupuesto)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                sql.Identifier(columna), sql.Identifier(tabla)
            ),
            (identificador,),
        ).fetchone()
    assert guardado == (valor,)


# --------------------------------------------------------------------------- TC-10

# (tabla, restricción, unidad ajena, cómo crear).
UNIDAD_FUERA_DEL_CATALOGO: list[tuple[str, str, str, Crear]] = [
    ("insumo", "ck_insumo_unidad", "LITRO", lambda datos: datos.insumo(unidad="LITRO")),
    ("concepto", "ck_concepto_unidad", "M3", lambda datos: datos.concepto(unidad="M3")),
]


@pytest.mark.parametrize(
    ("tabla", "restriccion", "unidad", "crear"),
    UNIDAD_FUERA_DEL_CATALOGO,
    ids=[f"{tabla}_{unidad}" for tabla, _, unidad, _ in UNIDAD_FUERA_DEL_CATALOGO],
)
def test_tkt011_ca11_unidad_fuera_del_catalogo_la_rechaza_la_base(
    tabla: str,
    restriccion: str,
    unidad: str,
    crear: Crear,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-10 · CA-11 · HDU-001 esc. 8 · invariante 27 — una unidad fuera de las ocho responde `23514`."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        crear(datos_presupuesto)

    afirmar_rechazo(rechazo.value, "23514", restriccion, tabla)
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, tabla) == 0


# Cómo crear, con una unidad dada, una fila de cada tabla que lleva unidad de medida.
CREAR_CON_UNIDAD: dict[str, Callable[[DatosPresupuesto, str], uuid.UUID]] = {
    "insumo": lambda datos, unidad: datos.insumo(codigo=f"INS-{unidad}", unidad=unidad),
    "concepto": lambda datos, unidad: datos.concepto(codigo=f"C-{unidad}", unidad=unidad),
}


@pytest.mark.parametrize("tabla", list(CREAR_CON_UNIDAD))
@pytest.mark.parametrize("unidad", UNIDADES)
def test_tkt011_ca11_las_ocho_unidades_se_aceptan_en_concepto_e_insumo(
    tabla: str,
    unidad: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-10 · CA-11 · HDU-001 esc. 8 · PA-T7 — cada una de las ocho unidades entra en un concepto y en un insumo."""
    identificador = CREAR_CON_UNIDAD[tabla](datos_presupuesto, unidad)

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardada = aplicacion.execute(
            sql.SQL("SELECT unidad FROM {} WHERE id = %s").format(sql.Identifier(tabla)),
            (identificador,),
        ).fetchone()
    assert guardada == (unidad,)


# --------------------------------------------------------------------------- TC-11 y TC-12


def test_tkt011_ca12_concepto_repetido_en_la_obra_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-11 · CA-12 esc. 1 · HDU-001 esc. 9 — dos conceptos `620001` en la obra A violan `uq_concepto_obra_id_codigo`."""
    obra_a = datos_presupuesto.obra(codigo="AP-058-25")
    original = datos_presupuesto.concepto(obra_id=obra_a, codigo="620001")

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.concepto(obra_id=obra_a, codigo="620001")

    afirmar_rechazo(rechazo.value, "23505", "uq_concepto_obra_id_codigo", "concepto")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar_donde(aplicacion, "concepto", "codigo", "620001") == 1
        assert contar(aplicacion, "concepto") == 1
        sigue = aplicacion.execute("SELECT id FROM concepto WHERE codigo = '620001'").fetchone()
    assert sigue == (original,)


def test_tkt011_ca12_el_mismo_codigo_en_otra_obra_se_acepta(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-12 · CA-12 esc. 2 · HDU-001 esc. 9 — `620001` entra en la obra B junto al de la obra A."""
    obra_a = datos_presupuesto.obra(codigo="AP-058-25")
    obra_b = datos_presupuesto.obra(codigo="AP-059-25")
    datos_presupuesto.concepto(obra_id=obra_a, codigo="620001")
    datos_presupuesto.concepto(obra_id=obra_b, codigo="620001")

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardados = aplicacion.execute(
            "SELECT obra_id, codigo FROM concepto ORDER BY obra_id"
        ).fetchall()
    assert sorted(guardados) == sorted([(obra_a, "620001"), (obra_b, "620001")])


# --------------------------------------------------------------------------- TC-13

# (tabla, columna, cómo crear una fila con ese valor en esa columna). La restricción esperada es
# `ck_<tabla>_<columna>_no_negativo`. Son las catorce columnas con `CHECK` de no negatividad que
# conserva la migración `0006`: las tres de `concepto` pasaron a `partida_concepto` en `0010` y las
# prueba `test_tkt072_esquema.py` (TC-07 y TC-08).
NO_NEGATIVOS: list[tuple[str, str, Callable[[DatosPresupuesto, Decimal], uuid.UUID]]] = [
    (
        "precio_insumo",
        "costo_unitario",
        lambda datos, valor: datos.precio_insumo(costo_unitario=valor),
    ),
    ("apu", "costo_material", lambda datos, valor: datos.apu(costo_material=valor)),
    ("apu", "costo_mano_obra", lambda datos, valor: datos.apu(costo_mano_obra=valor)),
    ("apu", "costo_directo", lambda datos, valor: datos.apu(costo_directo=valor)),
    ("apu", "total_cargos", lambda datos, valor: datos.apu(total_cargos=valor)),
    ("apu", "total_indirectos", lambda datos, valor: datos.apu(total_indirectos=valor)),
    ("apu", "precio_unitario", lambda datos, valor: datos.apu(precio_unitario=valor)),
    ("apu_insumo", "costo_unitario", lambda datos, valor: datos.apu_insumo(costo_unitario=valor)),
    ("apu_insumo", "rendimiento", lambda datos, valor: datos.apu_insumo(rendimiento=valor)),
    ("apu_insumo", "cargo", lambda datos, valor: datos.apu_insumo(cargo=valor)),
    ("apu_cargo", "porcentaje", lambda datos, valor: datos.apu_cargo(porcentaje=valor)),
    ("apu_cargo", "base_calculo", lambda datos, valor: datos.apu_cargo(base_calculo=valor)),
    ("apu_cargo", "importe", lambda datos, valor: datos.apu_cargo(importe=valor)),
    ("obra", "umbral_alerta_pct", lambda datos, valor: datos.obra(umbral_alerta_pct=valor)),
]


def negativo_minimo(tabla: str, columna: str) -> Decimal:
    """El negativo más pequeño que admite la escala de la columna: `-0.0001` en escala 4, `-0.000001` en 6."""
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
    """TC-13 · CA-13 · invariante 8 — un valor negativo en una de las catorce columnas de importes, precios, cantidades y rendimientos que conserva la migración 0006 responde `23514`."""
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
    """TC-13 · CA-13 · invariante 8 — con `0` en la misma columna la fila entra y se guarda en cero."""
    identificador = crear(datos_presupuesto, Decimal("0"))

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                sql.Identifier(columna), sql.Identifier(tabla)
            ),
            (identificador,),
        ).fetchone()
    assert guardado == (Decimal("0"),)


# --------------------------------------------------------------------------- TC-14

# (retención, fondo, umbral, restricción que lo rechaza o `None` si entra). `None` en el umbral
# es el nulo de la base.
PORCENTAJES_DE_OBRA: list[tuple[str, str, str | None, str | None]] = [
    ("0.150000", "0.050000", None, None),
    ("0.000000", "0.050000", None, None),
    ("1.000000", "0.050000", None, None),
    ("1.500000", "0.050000", None, "ck_obra_retencion_destajo_pct_rango"),
    ("1.000001", "0.050000", None, "ck_obra_retencion_destajo_pct_rango"),
    ("-0.01", "0.050000", None, "ck_obra_retencion_destajo_pct_rango"),
    ("0.050000", "0.000000", None, None),
    ("0.050000", "1.000000", None, None),
    ("0.050000", "1.000001", None, "ck_obra_fondo_garantia_pct_rango"),
    ("0.050000", "1.500000", None, "ck_obra_fondo_garantia_pct_rango"),
    ("0.050000", "-0.01", None, "ck_obra_fondo_garantia_pct_rango"),
    ("0.050000", "0.050000", "1.500000", None),
    ("0.050000", "0.050000", "-0.5", "ck_obra_umbral_alerta_pct_no_negativo"),
]


# Los casos se parten en los que entran y los que se rechazan, para que cada test tenga un único
# camino.
PORCENTAJES_ADMITIDOS: list[tuple[str, str, str | None]] = [
    (retencion, fondo, umbral)
    for retencion, fondo, umbral, restriccion in PORCENTAJES_DE_OBRA
    if restriccion is None
]
PORCENTAJES_RECHAZADOS: list[tuple[str, str, str | None, str]] = [
    (retencion, fondo, umbral, restriccion)
    for retencion, fondo, umbral, restriccion in PORCENTAJES_DE_OBRA
    if restriccion is not None
]


def _id_de_porcentajes(retencion: str, fondo: str, umbral: str | None) -> str:
    return f"retencion={retencion}_fondo={fondo}_umbral={umbral}"


@pytest.mark.parametrize(
    ("retencion", "fondo", "umbral"),
    PORCENTAJES_ADMITIDOS,
    ids=[
        _id_de_porcentajes(retencion, fondo, umbral)
        for retencion, fondo, umbral in PORCENTAJES_ADMITIDOS
    ],
)
def test_tkt011_ca14_porcentaje_de_obra_en_rango_se_acepta(
    retencion: str,
    fondo: str,
    umbral: str | None,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-14 · CA-14 · PA-T5 — retención y fondo entran de 0 a 1, en sus bordes; el umbral admite nulo y cualquier valor no negativo."""
    retencion_pct = Decimal(retencion)
    fondo_pct = Decimal(fondo)
    umbral_pct = None if umbral is None else Decimal(umbral)

    identificador = datos_presupuesto.obra(
        retencion_destajo_pct=retencion_pct,
        fondo_garantia_pct=fondo_pct,
        umbral_alerta_pct=umbral_pct,
    )
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardados = aplicacion.execute(
            "SELECT retencion_destajo_pct, fondo_garantia_pct, umbral_alerta_pct "
            "FROM obra WHERE id = %s",
            (identificador,),
        ).fetchone()
    assert guardados == (retencion_pct, fondo_pct, umbral_pct)


@pytest.mark.parametrize(
    ("retencion", "fondo", "umbral", "restriccion"),
    PORCENTAJES_RECHAZADOS,
    ids=[
        _id_de_porcentajes(retencion, fondo, umbral)
        for retencion, fondo, umbral, _ in PORCENTAJES_RECHAZADOS
    ],
)
def test_tkt011_ca14_porcentaje_de_obra_fuera_de_rango(
    retencion: str,
    fondo: str,
    umbral: str | None,
    restriccion: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-14 · CA-14 · PA-T5 — fuera de 0 a 1, la retención o el fondo responden `23514`; un umbral negativo, también."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        datos_presupuesto.obra(
            retencion_destajo_pct=Decimal(retencion),
            fondo_garantia_pct=Decimal(fondo),
            umbral_alerta_pct=None if umbral is None else Decimal(umbral),
        )

    afirmar_rechazo(rechazo.value, "23514", restriccion, "obra")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "obra") == 0


# --------------------------------------------------------------------------- TC-15

# Estos dos tests necesitan `apu_cargo`, que la migración crea junto con `apu`.


def test_tkt011_ca14_porcentaje_de_cargo_sin_tope(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-15 · CA-14 — el porcentaje de un cargo de APU no tiene techo: `2.500000` entra."""
    cargo_id = datos_presupuesto.apu_cargo(porcentaje=Decimal("2.500000"))

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        guardado = aplicacion.execute(
            "SELECT porcentaje FROM apu_cargo WHERE id = %s", (cargo_id,)
        ).fetchone()
    assert guardado == (Decimal("2.500000"),)


def test_tkt011_ca14_porcentaje_negativo_de_cargo_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-15 · CA-14 · invariante 8 — `-0.000001` en el porcentaje de un cargo responde `23514`."""
    with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
        datos_presupuesto.apu_cargo(porcentaje=Decimal("-0.000001"))

    afirmar_rechazo(rechazo.value, "23514", "ck_apu_cargo_porcentaje_no_negativo", "apu_cargo")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar(aplicacion, "apu_cargo") == 0


# --------------------------------------------------------------------------- unicidad de catálogo

# Las restricciones `UNIQUE` de catálogo, `uq_tipo_partida_clave` y `uq_insumo_codigo`, rechazan
# el duplicado; TC-17 comprueba además que se llamen así.


def test_tkt011_ca20_clave_de_tipo_partida_repetida_la_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """CA-20 · invariante 6 — un segundo tipo de partida `MUROS` viola `uq_tipo_partida_clave`.

    El primer `MUROS` ya lo siembra la migración `0008` (TKT-010), así que la precondición es que
    exista uno y el `INSERT` directo del segundo lo rechaza la base sin añadir ninguna fila.
    """
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        antes = contar(aplicacion, "tipo_partida")
        assert contar_donde(aplicacion, "tipo_partida", "clave", "MUROS") == 1

        with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
            aplicacion.execute(
                "INSERT INTO tipo_partida (id, clave, nombre) VALUES (%s, 'MUROS', 'Muros')",
                (uuid.uuid4(),),
            )

        afirmar_rechazo(rechazo.value, "23505", "uq_tipo_partida_clave", "tipo_partida")
        assert contar_donde(aplicacion, "tipo_partida", "clave", "MUROS") == 1
        assert contar(aplicacion, "tipo_partida") == antes


def test_tkt011_ca20_codigo_de_insumo_repetido_lo_rechaza_la_base(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """CA-20 · invariante 13 — dos insumos `INS-001` violan `uq_insumo_codigo`."""
    datos_presupuesto.insumo(codigo="INS-001")

    with pytest.raises(psycopg.errors.UniqueViolation) as rechazo:
        datos_presupuesto.insumo(codigo="INS-001")

    afirmar_rechazo(rechazo.value, "23505", "uq_insumo_codigo", "insumo")
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        assert contar_donde(aplicacion, "insumo", "codigo", "INS-001") == 1
        assert contar(aplicacion, "insumo") == 1
