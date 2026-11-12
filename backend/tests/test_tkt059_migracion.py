"""TKT-059 · Migración `0012` y tabla `archivo`: TC-01 a TC-04.

`0012` crea `archivo`, el registro de lo que el almacén de objetos guarda (modelo de datos §12).
Este archivo prueba lo que el motor sostiene por su cuenta, sin pasar por ningún caso de uso:
los cuatro invariantes 23 a 26 y los dos `CHECK` de dominio (`TC-01`), que el rol de aplicación no
puede borrar ni vaciar la tabla (`TC-02`), que la migración sube, baja y vuelve a subir sin dejar
rastro (`TC-03`) y que la bajada se niega si hay filas (`TC-04`).

Los datos se escriben con el rol de aplicación, que es quien los escribe en producción. La
migración y el catálogo los ejecuta y lee el rol de migración. La fotografía del catálogo y las
ayudas siguen el patrón de `test_tkt072_migracion.py`.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

REVISION_ANTERIOR = "0011"
REVISION_NUEVA = "0012"

HASH = "a" * 64
CONFIRMADO_EN = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
_USUARIO = "<usuario>"  # marcador: la prueba lo sustituye por el usuario que sembró

REFERENCIAS_ADMITIDAS = {
    "AVANCE",
    "ENTRADA_ALMACEN",
    "MERMA",
    "FACTURA_PROVEEDOR",
    "IMPORTACION",
    "OBRA",
}
ESTADOS_ADMITIDOS = {"PENDIENTE", "DISPONIBLE", "CADUCADO", "ANULADO"}

# Nombre -> tipo de restricción de `pg_constraint.contype`: las nueve del diseño, ni una más.
RESTRICCIONES: dict[str, str] = {
    "pk_archivo": "p",
    "fk_archivo_subido_por_id": "f",
    "fk_archivo_anulado_por_id": "f",
    "uq_archivo_clave_objeto": "u",
    "ck_archivo_referencia_tipo": "c",
    "ck_archivo_estado": "c",
    "ck_archivo_disponible_verificado": "c",
    "ck_archivo_anulado_con_motivo": "c",
    "ck_archivo_referencia_obligatoria": "c",
}

# Nombre, tipo, longitud, nulable, fragmento del valor por omisión (None: sin valor por omisión).
COLUMNAS: tuple[tuple[str, str, int | None, str, str | None], ...] = (
    ("id", "uuid", None, "NO", None),
    ("obra_id", "uuid", None, "NO", None),
    ("referencia_tipo", "text", None, "NO", None),
    ("referencia_id", "uuid", None, "YES", None),
    ("estado", "text", None, "NO", "PENDIENTE"),
    ("clave_objeto", "text", None, "NO", None),
    ("nombre_original", "text", None, "NO", None),
    ("tipo_mime", "text", None, "YES", None),
    ("tamano_bytes", "bigint", None, "YES", None),
    ("hash_sha256", "character", 64, "YES", None),
    ("subido_por_id", "uuid", None, "NO", None),
    ("creado_en", "timestamp with time zone", None, "NO", "now()"),
    ("confirmado_en", "timestamp with time zone", None, "YES", None),
    ("anulado_por_id", "uuid", None, "YES", None),
    ("motivo_anulacion", "text", None, "YES", None),
    ("anulado_en", "timestamp with time zone", None, "YES", None),
)

# --------------------------------------------------------------------------- ayudas


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def sqlstate_de(error: DBAPIError) -> str | None:
    """El `sqlstate` del error de origen (el de PostgreSQL), no el de la envoltura de SQLAlchemy."""
    origen = error.orig
    assert isinstance(origen, psycopg.Error), repr(origen)
    return origen.sqlstate


def exigir_tabla_archivo(conexion: Conexion) -> None:
    """La precondición de toda prueba que escribe en `archivo`: que la migración `0012` exista."""
    fila = conexion.execute("SELECT to_regclass('public.archivo')").fetchone()
    assert fila is not None and fila[0] is not None, (
        "Falta la migración 0012: la tabla `archivo` no existe (TKT-059, fila 2)"
    )


def fotografia(conexion: Conexion) -> dict[str, list[tuple[Any, ...]]]:
    """Todo lo que hay en el esquema `public`, para comparar antes y después de una migración.

    Tablas, columnas (con `ordinal_position`, tipo, longitud, escala, nulabilidad y valor por
    omisión), restricciones con su definición, índices con su definición, privilegios de cada rol
    incluido `PUBLIC`, disparadores y funciones. Las restricciones `NOT NULL` (`contype = 'n'`) no
    entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad ya viene en
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


def de_archivo(foto: dict[str, list[tuple[Any, ...]]], clave: str) -> list[tuple[Any, ...]]:
    """Las filas de `foto[clave]` que pertenecen a la tabla `archivo` (la tabla es el primer campo)."""
    return [fila for fila in foto[clave] if fila[0] == "archivo"]


def fila_valida(usuario_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Una fila `PENDIENTE` que cumple todo; `cambios` pisa columnas, `_USUARIO` pone el usuario."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "obra_id": uuid.uuid4(),
        "referencia_tipo": "AVANCE",
        "referencia_id": uuid.uuid4(),
        "estado": "PENDIENTE",
        "clave_objeto": f"obras/{uuid.uuid4()}/archivos/{uuid.uuid4()}",
        "nombre_original": "avance-muro-3.jpg",
        "subido_por_id": usuario_id,
    }
    valores.update(cambios)
    return {c: (usuario_id if v == _USUARIO else v) for c, v in valores.items()}


def insertar(conexion: Conexion, valores: dict[str, Any]) -> None:
    conexion.execute(
        sql.SQL("INSERT INTO archivo ({}) VALUES ({})").format(
            sql.SQL(", ").join(sql.Identifier(columna) for columna in valores),
            sql.SQL(", ").join(sql.Placeholder() for _ in valores),
        ),
        list(valores.values()),
    )


def contar(conexion: Conexion, *, clave_objeto: str | None = None) -> int:
    if clave_objeto is None:
        fila = conexion.execute("SELECT count(*) FROM archivo").fetchone()
    else:
        fila = conexion.execute(
            "SELECT count(*) FROM archivo WHERE clave_objeto = %s", (clave_objeto,)
        ).fetchone()
    assert fila is not None
    return int(fila[0])


def filas_de_archivo(conexion: Conexion) -> list[str]:
    return [
        str(f[0])
        for f in conexion.execute("SELECT a::text FROM archivo a ORDER BY a.id").fetchall()
    ]


# --------------------------------------------------------------------------- TC-01

_DISPONIBLE_COMPLETO: dict[str, Any] = {
    "estado": "DISPONIBLE",
    "tipo_mime": "image/jpeg",
    "tamano_bytes": 2048,
    "hash_sha256": HASH,
    "confirmado_en": CONFIRMADO_EN,
}
_ANULADO_COMPLETO: dict[str, Any] = {
    "estado": "ANULADO",
    "anulado_por_id": _USUARIO,
    "motivo_anulacion": "Foto del muro equivocado",
    "anulado_en": CONFIRMADO_EN,
}
_CLAVE_REPETIDA = "obras/obra-1/archivos/repetida"


def _sin(base: dict[str, Any], columna: str) -> dict[str, Any]:
    return {**base, columna: None}


@pytest.mark.parametrize(
    ("cambios", "repite_clave", "rechazo"),
    [
        pytest.param(
            _sin(_DISPONIBLE_COMPLETO, "hash_sha256"),
            False,
            ("23514", "ck_archivo_disponible_verificado"),
            id="disponible_sin_hash",
        ),
        pytest.param(
            _sin(_DISPONIBLE_COMPLETO, "tamano_bytes"),
            False,
            ("23514", "ck_archivo_disponible_verificado"),
            id="disponible_sin_tamano",
        ),
        pytest.param(
            _sin(_DISPONIBLE_COMPLETO, "confirmado_en"),
            False,
            ("23514", "ck_archivo_disponible_verificado"),
            id="disponible_sin_confirmado_en",
        ),
        pytest.param(
            _sin(_ANULADO_COMPLETO, "anulado_por_id"),
            False,
            ("23514", "ck_archivo_anulado_con_motivo"),
            id="anulado_sin_autor",
        ),
        pytest.param(
            _sin(_ANULADO_COMPLETO, "motivo_anulacion"),
            False,
            ("23514", "ck_archivo_anulado_con_motivo"),
            id="anulado_sin_motivo",
        ),
        pytest.param(
            {"clave_objeto": _CLAVE_REPETIDA},
            True,
            ("23505", "uq_archivo_clave_objeto"),
            id="clave_de_objeto_repetida",
        ),
        pytest.param(
            {"referencia_tipo": "IMPORTACION", "referencia_id": None},
            False,
            ("23514", "ck_archivo_referencia_obligatoria"),
            id="importacion_sin_referencia_id",
        ),
        pytest.param(
            {"referencia_tipo": "AVANCE", "referencia_id": None},
            False,
            ("23514", "ck_archivo_referencia_obligatoria"),
            id="avance_sin_referencia_id",
        ),
        pytest.param(
            {"estado": "BORRADO"},
            False,
            ("23514", "ck_archivo_estado"),
            id="estado_fuera_del_conjunto",
        ),
        pytest.param(
            {"referencia_tipo": "COMPRA"},
            False,
            ("23514", "ck_archivo_referencia_tipo"),
            id="referencia_tipo_fuera_del_conjunto",
        ),
        pytest.param(
            {"referencia_tipo": "OBRA", "referencia_id": None},
            False,
            None,
            id="obra_admite_referencia_id_nulo",
        ),
        pytest.param(_DISPONIBLE_COMPLETO, False, None, id="disponible_completo_se_admite"),
        pytest.param(_ANULADO_COMPLETO, False, None, id="anulado_completo_se_admite"),
    ],
)
def test_tkt059_ca01_invariantes_del_archivo(
    cambios: dict[str, Any],
    repite_clave: bool,
    rechazo: tuple[str, str] | None,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-01 · CA-1 esc. 1 · invariantes 23 a 26 — el motor rechaza la fila que los rompe.

    Con el rol de aplicación: `DISPONIBLE` sin hash, sin tamaño o sin `confirmado_en`; `ANULADO` sin
    autor o sin motivo; una clave de objeto repetida; un tipo distinto de `OBRA` sin `referencia_id`;
    un estado y un `referencia_tipo` fuera de su conjunto. Cada rechazo trae su `SQLSTATE` y el
    nombre de la restricción (`diag.constraint_name`) y no deja fila. Una referencia nula con `OBRA`
    y las filas completas se admiten: sin ellas un `CHECK` que rechaza todo pasaría igual.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_archivo(aplicacion)
    usuario = datos_presupuesto.usuario()
    valores = fila_valida(usuario, **cambios)
    previas = 0
    if repite_clave:
        insertar(aplicacion, fila_valida(usuario, clave_objeto=_CLAVE_REPETIDA))
        previas = 1
    assert contar(aplicacion) == previas

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


# --------------------------------------------------------------------------- TC-02


@pytest.mark.parametrize(
    "sentencia",
    [
        pytest.param("DELETE FROM archivo WHERE id = %(id)s", id="delete"),
        pytest.param("TRUNCATE archivo", id="truncate"),
    ],
)
def test_tkt059_ca01_el_rol_de_aplicacion_no_borra_archivos(
    sentencia: str,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-02 · CA-1 esc. 2 · `PA-T59.10` — el rol de aplicación no borra ni vacía `archivo`.

    `DELETE` y `TRUNCATE` responden `42501` (privilegio insuficiente) y la fila sigue idéntica. El
    `DELETE` lo sostiene el `REVOKE` de la migración; el `TRUNCATE`, los privilegios por omisión
    de `0001`, que no lo conceden.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_archivo(aplicacion)
    fila = fila_valida(datos_presupuesto.usuario())
    insertar(aplicacion, fila)
    antes = filas_de_archivo(aplicacion)
    assert len(antes) == 1

    with pytest.raises(psycopg.Error) as error:
        aplicacion.execute(sentencia, {"id": fila["id"]})  # type: ignore[arg-type]

    assert error.value.sqlstate == "42501", str(error.value)
    assert "archivo" in str(error.value), str(error.value)
    assert filas_de_archivo(aplicacion) == antes, "La fila debía seguir ahí, sin cambios"


# --------------------------------------------------------------------------- TC-03


def _comprobar_columnas(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    columnas = de_archivo(foto, "columnas")
    # (tabla, posición, nombre, tipo, longitud, precisión, escala, nulable, valor por omisión)
    assert [(c[1], c[2]) for c in columnas] == [(i + 1, e[0]) for i, e in enumerate(COLUMNAS)], (
        f"Las columnas y su orden no son los del diseño: {[c[2] for c in columnas]}"
    )
    for real, (nombre, tipo, longitud, nulable, omision) in zip(columnas, COLUMNAS, strict=True):
        assert real[3] == tipo, f"{nombre}: tipo {real[3]}, esperaba {tipo}"
        assert real[4] == longitud, f"{nombre}: longitud {real[4]}, esperaba {longitud}"
        assert real[7] == nulable, f"{nombre}: is_nullable {real[7]}, esperaba {nulable}"
        if omision is None:
            assert real[8] is None, f"{nombre}: no debe tener valor por omisión, tiene {real[8]}"
        else:
            assert real[8] is not None and omision in real[8], (
                f"{nombre}: el valor por omisión {real[8]} debía contener {omision}"
            )


def _comprobar_restricciones(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    restricciones = {str(f[1]): (str(f[2]), str(f[3])) for f in de_archivo(foto, "restricciones")}
    assert {nombre: tipo for nombre, (tipo, _) in restricciones.items()} == RESTRICCIONES, (
        f"Las restricciones no son las nueve del diseño: {sorted(restricciones)}"
    )

    definicion = {nombre: texto for nombre, (_, texto) in restricciones.items()}
    assert "PRIMARY KEY (id)" in definicion["pk_archivo"]
    for nombre, columna in (
        ("fk_archivo_subido_por_id", "subido_por_id"),
        ("fk_archivo_anulado_por_id", "anulado_por_id"),
    ):
        assert f"FOREIGN KEY ({columna}) REFERENCES usuario(id)" in definicion[nombre], definicion[
            nombre
        ]
    assert "UNIQUE (clave_objeto)" in definicion["uq_archivo_clave_objeto"]
    assert set(re.findall(r"'([A-Z_]+)'", definicion["ck_archivo_referencia_tipo"])) == (
        REFERENCIAS_ADMITIDAS
    ), definicion["ck_archivo_referencia_tipo"]
    assert set(re.findall(r"'([A-Z_]+)'", definicion["ck_archivo_estado"])) == ESTADOS_ADMITIDOS, (
        definicion["ck_archivo_estado"]
    )
    disponible = definicion["ck_archivo_disponible_verificado"]
    for fragmento in (
        "DISPONIBLE",
        "hash_sha256 IS NOT NULL",
        "tamano_bytes IS NOT NULL",
        "confirmado_en IS NOT NULL",
    ):
        assert fragmento in disponible, f"{fragmento!r} no está en {disponible}"
    anulado = definicion["ck_archivo_anulado_con_motivo"]
    for fragmento in ("ANULADO", "anulado_por_id IS NOT NULL", "motivo_anulacion IS NOT NULL"):
        assert fragmento in anulado, f"{fragmento!r} no está en {anulado}"
    obligatoria = definicion["ck_archivo_referencia_obligatoria"]
    for fragmento in ("OBRA", "referencia_id IS NOT NULL"):
        assert fragmento in obligatoria, f"{fragmento!r} no está en {obligatoria}"

    # Ninguna clave foránea sobre la obra ni sobre el documento al que se adjunta: la obra y el
    # documento viven en módulos que `archivos` no puede importar, y un documento puede ser de
    # cualquiera de seis tablas.
    for nombre, (tipo, texto) in restricciones.items():
        if tipo == "f":
            assert "obra_id" not in texto and "referencia_id" not in texto, (nombre, texto)


def _comprobar_indices(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    indices = {str(f[1]): str(f[2]) for f in de_archivo(foto, "indices")}
    assert set(indices) == {
        "pk_archivo",
        "uq_archivo_clave_objeto",
        "ix_archivo_obra_id_estado_creado_en",
        "ix_archivo_referencia_tipo_referencia_id",
        "ix_archivo_creado_en_pendiente",
    }, sorted(indices)
    assert "(obra_id, estado, creado_en DESC)" in indices["ix_archivo_obra_id_estado_creado_en"]
    assert (
        "(referencia_tipo, referencia_id)" in (indices["ix_archivo_referencia_tipo_referencia_id"])
    )
    parcial = indices["ix_archivo_creado_en_pendiente"]
    assert "(creado_en)" in parcial, parcial
    assert "WHERE" in parcial and "estado = 'PENDIENTE'" in parcial, (
        f"El índice parcial debía tener el predicado estado = 'PENDIENTE': {parcial}"
    )
    for nombre in (
        "ix_archivo_obra_id_estado_creado_en",
        "ix_archivo_referencia_tipo_referencia_id",
    ):
        assert "WHERE" not in indices[nombre], f"{nombre} no es parcial: {indices[nombre]}"


def _comprobar_privilegios(foto: dict[str, list[tuple[Any, ...]]]) -> None:
    por_rol: dict[str, set[str]] = {}
    for _, rol, privilegio, _ in de_archivo(foto, "privilegios"):
        por_rol.setdefault(str(rol), set()).add(str(privilegio))
    assert por_rol.get("cimenta_aplicacion") == {"SELECT", "INSERT", "UPDATE"}, (
        f"El rol de aplicación debía tener SELECT, INSERT y UPDATE, sin DELETE ni TRUNCATE: "
        f"{por_rol.get('cimenta_aplicacion')}"
    )
    assert por_rol.get("cimenta_lectura") == {"SELECT"}, por_rol.get("cimenta_lectura")
    assert "PUBLIC" not in por_rol, "Ningún privilegio para PUBLIC"


def test_tkt059_ca01_la_migracion_sube_y_baja(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-03 · CA-1 esc. 3 — `upgrade 0012`, `downgrade 0011` y `upgrade 0012` dejan lo que deben.

    En `0011` no existe `archivo` (fotografía A). Tras subir existen sus dieciséis columnas con su
    tipo, su nulabilidad y su valor por omisión, las nueve restricciones con nombre, los tres
    índices (el parcial con su predicado), los privilegios del rol de aplicación sin `DELETE` ni
    `TRUNCATE` y ninguna clave foránea sobre `obra_id` ni `referencia_id`. Tras bajar, la fotografía
    es idéntica a A; tras volver a subir, idéntica a la primera subida.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]
    assert ("archivo",) not in a["tablas"], "La precondición es el esquema de 0011, sin `archivo`"

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        b = fotografia(administrador)
        version_b = version_de_alembic(administrador)
    assert version_b == [(REVISION_NUEVA,)]
    assert ("archivo",) in b["tablas"], b["tablas"]
    _comprobar_columnas(b)
    _comprobar_restricciones(b)
    _comprobar_indices(b)
    _comprobar_privilegios(b)

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        version_c = version_de_alembic(administrador)
    assert version_c == [(REVISION_ANTERIOR,)]
    assert ("archivo",) not in c["tablas"]
    assert c == a

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        d = fotografia(administrador)
        version_d = version_de_alembic(administrador)
    assert version_d == [(REVISION_NUEVA,)]
    assert d == b


# --------------------------------------------------------------------------- TC-04


def test_tkt059_ca01_la_bajada_se_niega_con_archivos(
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-04 · CA-1 esc. 3 — `downgrade` desde `0012` con una fila en `archivo` responde `P0001`.

    Bajar borraría la tabla y los objetos del almacén perderían su rastro. El texto nombra la bajada
    de `0012` y la tabla; la versión sigue en `0012`, y la fotografía del catálogo y la fila no
    cambian.
    """
    aplicacion = conectar("aplicacion", base_de_prueba)
    exigir_tabla_archivo(aplicacion)
    insertar(aplicacion, fila_valida(datos_presupuesto.usuario()))
    with conectar("migracion", base_de_prueba) as administrador:
        foto_antes = fotografia(administrador)
        version_antes = version_de_alembic(administrador)
    filas_antes = filas_de_archivo(aplicacion)
    assert version_antes == [(REVISION_NUEVA,)], "La base de pruebas debe estar en la cabeza 0012"
    assert len(filas_antes) == 1

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, REVISION_ANTERIOR, "downgrade")

    texto = str(rechazo.value)
    assert sqlstate_de(rechazo.value) == "P0001", texto
    assert "La bajada de 0012 se niega" in texto, texto
    assert "archivo" in texto, texto
    with conectar("migracion", base_de_prueba) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_NUEVA,)]
        assert fotografia(administrador) == foto_antes
    assert filas_de_archivo(aplicacion) == filas_antes
