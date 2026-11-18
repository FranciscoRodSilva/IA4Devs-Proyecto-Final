"""TKT-012b · Migración `0017` y el verbo `ELIMINAR` (fila A1): TC-01 a TC-04 y TC-INV-1.

`0017` añade `ELIMINAR` al final del tipo `accion_bitacora` con `ALTER TYPE … ADD VALUE`. El borrado
físico de una obra sin historial (`CA-5`, `HDU-001` esc. 20) asienta ese verbo: `CANCELAR`, `ANULAR`
y `DESCARTAR` significan otra cosa (`D-4`). Su bajada se niega con `RAISE EXCEPTION` si la bitácora
tiene asientos `ELIMINAR` (`RN-04`: la bitácora es permanente) y, si no los tiene, recrea el tipo con
los 23 verbos de `0016` sin cambiar ningún valor de la columna `bitacora.accion`.

Este archivo prueba la migración como pieza de la cadena, sin pasar por ningún caso de uso, con el
molde de `test_tkt029b_migracion.py`: que `0017` cuelga de `0016` y la cabeza es única, que el tipo
queda con los 23 verbos de `0016` más `ELIMINAR` al final y `AccionBitacora` coincide con él
(`TC-01`, `CA-5`), cómo se comporta `ADD VALUE` dentro de una transacción (`TC-02`, sonda del
supuesto 1 del diseño: `55P04`), que la bajada sin asientos `ELIMINAR` deja el tipo y la bitácora
como en `0016` (`TC-03`, `CA-R3`), que se niega con asientos `ELIMINAR` y no pierde ninguno
(`TC-04`, `CA-5`, `RN-04`) y que subir y bajar conserva el esquema de `0016` (`TC-INV-1`, `CA-R3`).

Alembic y la sonda `TC-02` corren con el rol de migración; los asientos y las comprobaciones de
permisos, con el rol de aplicación. Los esquemas se construyen con `alembic upgrade`, nunca con la
creación automática de tablas del ORM.

Las siete aserciones con «23» fijo de pruebas existentes (`test_tkt007_*`, `test_tkt029b_*`) no se
tocan aquí: las amplía el desarrollador en verde, como ampliación declarada del diseño (fila A1).
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
from sqlalchemy.exc import DBAPIError

from cimenta.auditoria.dominio.asiento import AccionBitacora

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]
Fotografia = dict[str, list[tuple[Any, ...]]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_ANTERIOR = "0016"
REVISION_NUEVA = "0017"

OCURRIDO_EN = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)

# Los 23 verbos de `0016` (los 22 de `0003` y `DAR_BAJA`), en su orden. `0017` añade `ELIMINAR`
# después del último.
VERBOS_0016: list[str] = [
    "CREAR",
    "ACTUALIZAR",
    "EVALUAR",
    "BLOQUEAR",
    "AUTORIZAR",
    "RECHAZAR",
    "CANCELAR",
    "EMITIR",
    "AJUSTAR",
    "REPROGRAMAR",
    "CONGELAR",
    "RECAPTURAR",
    "DESCARTAR",
    "CONFIRMAR",
    "ANULAR",
    "SUSPENDER",
    "REACTIVAR",
    "CERRAR",
    "DESACTIVAR",
    "LIBERAR",
    "VALIDAR",
    "DENEGAR",
    "DAR_BAJA",
]
VERBOS_0017: list[str] = [*VERBOS_0016, "ELIMINAR"]

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
    assert revision in conocidas, (
        f"Falta la migración {revision} (v0017_auditoria_verbo_eliminar.py): Alembic no la conoce "
        f"(TKT-012b, fila A1). Revisiones conocidas: {sorted(conocidas)}"
    )


def verbos_de_la_base(conexion: Conexion) -> list[str]:
    """Las etiquetas de `accion_bitacora` en el orden del tipo (`enumsortorder`)."""
    filas = conexion.execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('accion_bitacora') "
        "ORDER BY enumsortorder"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def fotografia(conexion: Conexion) -> Fotografia:
    """Todo lo que hay en el esquema `public`, para comparar antes y después de una migración.

    Tablas, columnas (con `ordinal_position`, tipo, longitud, precisión, escala, nulabilidad y valor
    por omisión), restricciones con su definición, índices con su definición, privilegios de cada
    rol incluido `PUBLIC`, disparadores y funciones. Las restricciones `NOT NULL` (`contype = 'n'`)
    no entran: PostgreSQL 18 las registra con un nombre automático y su nulabilidad ya viene en
    `columnas`. Copia de `fotografia` de `test_tkt029b_migracion.py`, sin cambios.
    """

    def filas(consulta: str) -> list[tuple[Any, ...]]:
        return [tuple(f) for f in conexion.execute(consulta).fetchall()]

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


def fotografia_de_bitacora(conexion: Conexion) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    """Columnas (con su tipo), restricciones, índices, `relacl` y etiquetas del enum de `bitacora`.

    La quinta posición (`[4]`) son las etiquetas del tipo: las cuatro primeras no deben cambiar con
    `0017`; la quinta, sí.
    """
    consultas = (
        "SELECT column_name, udt_name, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = 'bitacora' ORDER BY ordinal_position",
        "SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass('bitacora') ORDER BY conname",
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' AND tablename = 'bitacora' ORDER BY indexname",
        "SELECT relacl::text FROM pg_class WHERE oid = to_regclass('bitacora')",
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('accion_bitacora') "
        "ORDER BY enumsortorder",
    )
    return tuple(tuple(conexion.execute(consulta).fetchall()) for consulta in consultas)


def filas_de_bitacora(conexion: Conexion) -> list[str]:
    """Cada asiento como texto, ordenado por `id`: lo que no debe cambiar al migrar."""
    return [
        str(fila[0])
        for fila in conexion.execute("SELECT b::text FROM bitacora b ORDER BY b.id").fetchall()
    ]


def sembrar_usuario(conexion: Conexion) -> uuid.UUID:
    """Un usuario confirmado, para que `bitacora.usuario_id` apunte a alguien real."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", f"{identificador}@cimenta.test", "hash-de-prueba"),
    )
    return identificador


def insertar_asiento(conexion: Conexion, usuario_id: uuid.UUID, accion: str) -> uuid.UUID:
    """`INSERT` directo sobre `bitacora`, con el rol que reciba; devuelve el `id`."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO bitacora (id, entidad_tipo, entidad_id, accion, usuario_id, ocurrido_en, "
        "motivo) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            identificador,
            "obra",
            uuid.uuid4(),
            accion,
            usuario_id,
            OCURRIDO_EN,
            f"Asiento de prueba {accion}",
        ),
    )
    return identificador


def privilegio_de_tabla(conexion: Conexion, privilegio: str) -> bool:
    fila = conexion.execute(
        "SELECT has_table_privilege('cimenta_aplicacion', 'bitacora', %s)", (privilegio,)
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def uso_del_tipo(conexion: Conexion) -> bool:
    fila = conexion.execute(
        "SELECT has_type_privilege('cimenta_aplicacion', 'accion_bitacora', 'USAGE')"
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def exigir_privilegios_de_la_aplicacion(conexion: Conexion) -> None:
    """El rol de aplicación inserta y lee la bitácora; no actualiza, no borra, no trunca."""
    assert privilegio_de_tabla(conexion, "INSERT") is True
    assert privilegio_de_tabla(conexion, "SELECT") is True
    assert privilegio_de_tabla(conexion, "UPDATE") is False
    assert privilegio_de_tabla(conexion, "DELETE") is False
    assert privilegio_de_tabla(conexion, "TRUNCATE") is False
    assert uso_del_tipo(conexion) is True


# --------------------------------------------------------------------------- cadena


def test_tkt012b_car3_0017_cuelga_de_0016_y_la_cabeza_es_unica() -> None:
    """CA-R3 — la cadena de migraciones tiene una sola cabeza y `0017` cuelga de `0016`.

    No afirma qué revisión es la cabeza: el siguiente ticket que migre debe poder hacerlo sin tocar
    esta prueba. No usa base de datos. Mismo patrón que `test_tkt029b_car1_0016_cuelga_de_0015_…`.
    """
    guion = guion_de_alembic()
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas

    exigir_revision(REVISION_NUEVA)
    revision = guion.get_revision(REVISION_NUEVA)
    assert revision is not None
    assert revision.down_revision == REVISION_ANTERIOR


# --------------------------------------------------------------------------- TC-01


def test_hdu001_esc20_ca5_el_tipo_gana_eliminar_al_final(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-01 · HDU-001 esc. 20 · CA-5 — tras `upgrade head`, `ELIMINAR` es el verbo 24 y va al final.

    `pg_enum` de `accion_bitacora` es la lista de `0016` (los 22 de `0003` y `DAR_BAJA`) más
    `ELIMINAR` al final, sin `BEFORE` ni `AFTER`. La primera mitad de `TC-01`; la segunda
    (`AccionBitacora` coincide con el tipo) es la prueba siguiente.
    """
    with conectar("migracion", base_de_prueba) as administrador:
        assert verbos_de_la_base(administrador) == VERBOS_0017


def test_hdu001_esc20_ca5_accion_bitacora_tiene_eliminar_y_coincide_con_el_tipo(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-01 · HDU-001 esc. 20 · CA-5 — el enumerado de dominio `AccionBitacora` coincide con el tipo.

    `AccionBitacora.ELIMINAR` existe, es el último miembro y la lista de sus valores, en su orden,
    es la de `accion_bitacora` en la base migrada a `head`: el asiento que arma el caso de uso se
    puede escribir con un verbo que el tipo conoce.
    """
    assert "ELIMINAR" in AccionBitacora.__members__, (
        "Falta AccionBitacora.ELIMINAR en cimenta/auditoria/dominio/asiento.py (TKT-012b, A1)"
    )
    assert AccionBitacora.ELIMINAR.value == "ELIMINAR"
    assert list(AccionBitacora)[-1] is AccionBitacora.ELIMINAR
    with conectar("migracion", base_de_prueba) as administrador:
        assert [miembro.value for miembro in AccionBitacora] == verbos_de_la_base(administrador)


def test_hdu001_esc20_ca5_el_rol_de_aplicacion_asienta_eliminar_sin_ganar_permisos(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-01 · HDU-001 esc. 20 · CA-5 · invariante 10 — el rol de aplicación asienta `ELIMINAR`.

    Con el rol de aplicación, en una transacción nueva (la plantilla ya está confirmada, sin el
    límite de `ADD VALUE` de `TC-02`), un `INSERT` con `accion = 'ELIMINAR'` se acepta. El rol sigue
    sin `UPDATE`, `DELETE` ni `TRUNCATE` sobre `bitacora` (por `has_table_privilege` y con un `UPDATE`
    y un `DELETE` reales, que responden `42501`) y conserva `USAGE` sobre el tipo.
    """
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_privilegios_de_la_aplicacion(administrador)

    aplicacion = conectar("aplicacion", base_de_prueba)
    usuario = sembrar_usuario(aplicacion)
    asiento = insertar_asiento(aplicacion, usuario, "ELIMINAR")

    with conectar("aplicacion", base_de_prueba) as otra:
        fila = otra.execute(
            "SELECT accion::text, usuario_id FROM bitacora WHERE id = %s", (asiento,)
        ).fetchone()
        assert fila == ("ELIMINAR", usuario)
        with pytest.raises(psycopg.Error) as actualizar:
            otra.execute("UPDATE bitacora SET motivo = 'cambiado' WHERE id = %s", (asiento,))
        assert actualizar.value.sqlstate == "42501", str(actualizar.value)
        with pytest.raises(psycopg.Error) as borrar:
            otra.execute("DELETE FROM bitacora WHERE id = %s", (asiento,))
        assert borrar.value.sqlstate == "42501", str(borrar.value)
        assert otra.execute("SELECT count(*) FROM bitacora").fetchone() == (1,)


# --------------------------------------------------------------------------- TC-02


def test_tkt012b_ca5_sonda_eliminar_no_se_usa_en_su_transaccion_y_la_subida_no_lo_usa(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-02 · CA-5 · supuesto 1 — sonda del motor: `ADD VALUE 'ELIMINAR'` y su límite transaccional.

    Con la base en `0016`, en una transacción con el rol de migración, `ALTER TYPE accion_bitacora
    ADD VALUE 'ELIMINAR'` seguido de un `INSERT` en `bitacora` con ese verbo falla con
    `sqlstate == "55P04"` (`UnsafeNewEnumValueUsage`), igual que con `DAR_BAJA`; tras `ROLLBACK`,
    `ELIMINAR` no existe y el tipo sigue con los 23 verbos de `0016`.

    La parte que ata la sonda al ticket: la subida de `0017` se aplica sin `55P04` (no usa el valor
    en la transacción que lo añade) y deja `ELIMINAR` último, utilizable en una transacción nueva.
    La primera mitad prueba el motor y por sí sola nacería en verde; la segunda exige `0017`, y es la
    que pone la prueba en rojo hasta que la migración exista.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)

    # (a) ADD VALUE y uso en la misma transacción.
    with conectar("migracion", base_vacia, autocommit=False) as transaccion:
        transaccion.execute("ALTER TYPE accion_bitacora ADD VALUE 'ELIMINAR'")
        with pytest.raises(psycopg.Error) as uso_inseguro:
            insertar_asiento(transaccion, usuario, "ELIMINAR")
        assert uso_inseguro.value.sqlstate == "55P04", str(uso_inseguro.value)
        transaccion.rollback()
    with conectar("migracion", base_vacia) as lector:
        assert verbos_de_la_base(lector) == VERBOS_0016, "Tras ROLLBACK, ELIMINAR no debía existir"

    # (b) La subida real de 0017 no cae en la trampa y deja el verbo usable después.
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as lector:
        assert version_de_alembic(lector) == [(REVISION_NUEVA,)]
        assert verbos_de_la_base(lector) == VERBOS_0017
    with conectar("aplicacion", base_vacia) as otra:
        asiento = insertar_asiento(otra, usuario, "ELIMINAR")
        fila = otra.execute(
            "SELECT accion::text FROM bitacora WHERE id = %s", (asiento,)
        ).fetchone()
    assert fila == ("ELIMINAR",)


# --------------------------------------------------------------------------- TC-03


def test_tkt012b_car3_la_bajada_devuelve_los_23_verbos_y_deja_la_bitacora_como_estaba(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-03 · CA-R3 · invariante 10 — `upgrade 0017` y `downgrade 0016` no dejan rastro.

    Base en `0016` con tres asientos (`CREAR`, `DESACTIVAR` y `DAR_BAJA`: el último verbo que ya
    existía, que la recreación del tipo debe conservar), escritos con el rol de aplicación.
    Fotografía A del esquema completo, de `bitacora` y de sus filas. Se sube a `0017` y se baja a
    `0016`: los verbos son exactamente los 23 de `0016` en su orden, la fotografía C es igual a la A,
    las filas no cambiaron, `to_regtype('accion_bitacora_0017')` es nulo (la bajada borra el tipo
    temporal) y `alembic_version` es `0016`. El rol de aplicación conserva sus privilegios y
    `ELIMINAR` ya no existe: un `INSERT` con él responde `22P02`.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR)
    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)
    insertar_asiento(aplicacion, usuario, "CREAR")
    insertar_asiento(aplicacion, usuario, "DESACTIVAR")
    insertar_asiento(aplicacion, usuario, "DAR_BAJA")
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        bitacora_a = fotografia_de_bitacora(administrador)
        filas_a = filas_de_bitacora(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]
    assert len(filas_a) == 3
    assert bitacora_a[4] == tuple((verbo,) for verbo in VERBOS_0016)

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        assert version_de_alembic(administrador) == [(REVISION_NUEVA,)]
        assert verbos_de_la_base(administrador) == VERBOS_0017, "Control: la subida añadió el verbo"

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        bitacora_c = fotografia_de_bitacora(administrador)
        filas_c = filas_de_bitacora(administrador)
        version_c = version_de_alembic(administrador)
        verbos_c = verbos_de_la_base(administrador)
        temporal = administrador.execute(
            "SELECT to_regtype('accion_bitacora_0017') IS NULL"
        ).fetchone()
        exigir_privilegios_de_la_aplicacion(administrador)
    assert version_c == [(REVISION_ANTERIOR,)]
    assert verbos_c == VERBOS_0016
    assert temporal == (True,), "La bajada debía borrar el tipo temporal accion_bitacora_0017"
    assert bitacora_c == bitacora_a
    assert c == a
    assert filas_c == filas_a, "Los asientos existentes no debían cambiar"

    with conectar("aplicacion", base_vacia) as otra, pytest.raises(psycopg.Error) as ya_no_existe:
        insertar_asiento(otra, usuario, "ELIMINAR")
    assert ya_no_existe.value.sqlstate == "22P02", str(ya_no_existe.value)


# --------------------------------------------------------------------------- TC-04


def test_tkt012b_ca5_la_bajada_se_niega_con_asientos_eliminar(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-04 · CA-5 · RN-04 — con un asiento `ELIMINAR`, `downgrade 0016` lanza y no destruye nada.

    El rechazo es el de la guarda de la migración (`RAISE EXCEPTION`, `P0001`) y no el
    `invalid input value for enum` (`22P02`) de convertir la columna sin ella. El mensaje nombra
    `ELIMINAR` y `0017`. Tras el rechazo, `alembic_version` sigue en `0017`, `ELIMINAR` sigue en el
    tipo, el tipo temporal no existe y las filas de `bitacora` son las mismas: ningún asiento se
    pierde.
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_NUEVA)
    aplicacion = conectar("aplicacion", base_vacia)
    usuario = sembrar_usuario(aplicacion)
    insertar_asiento(aplicacion, usuario, "CREAR")
    asiento_eliminar = insertar_asiento(aplicacion, usuario, "ELIMINAR")
    with conectar("migracion", base_vacia) as administrador:
        antes = filas_de_bitacora(administrador)
    assert len(antes) == 2

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_vacia, REVISION_ANTERIOR, "downgrade")

    assert "ELIMINAR" in str(rechazo.value), str(rechazo.value)
    assert "0017" in str(rechazo.value), str(rechazo.value)
    assert getattr(rechazo.value.orig, "sqlstate", None) == "P0001", (
        f"Debía rechazar la guarda (RAISE EXCEPTION), no el motor al convertir: {rechazo.value}"
    )
    with conectar("migracion", base_vacia) as administrador:
        version = version_de_alembic(administrador)
        verbos = verbos_de_la_base(administrador)
        despues = filas_de_bitacora(administrador)
        temporal = administrador.execute(
            "SELECT to_regtype('accion_bitacora_0017') IS NULL"
        ).fetchone()
        sigue_el_asiento = administrador.execute(
            "SELECT accion::text FROM bitacora WHERE id = %s", (asiento_eliminar,)
        ).fetchone()
    assert version == [(REVISION_NUEVA,)], "La bajada negada debía dejar la versión en 0017"
    assert verbos == VERBOS_0017, "ELIMINAR debía seguir en el tipo"
    assert temporal == (True,), "El rechazo no debía dejar el tipo temporal"
    assert despues == antes, "La bitácora debía quedar intacta"
    assert sigue_el_asiento == ("ELIMINAR",)


# --------------------------------------------------------------------------- TC-INV-1


def test_tkt012b_car3_sube_y_baja_conservan_el_esquema_de_0016(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-INV-1 · CA-R3 — `0017` solo cambia las etiquetas del tipo; el resto del esquema es el de `0016`.

    Fotografía A del esquema en `0016`. Tras `upgrade 0017`, la fotografía B es igual a la A (tablas,
    columnas, restricciones, índices, privilegios, disparadores y funciones) y, en `bitacora`,
    columnas, restricciones, índices y `relacl` no cambian: solo el quinto elemento, las etiquetas,
    gana `ELIMINAR`. Tras `downgrade 0016`, la C es igual a la A; y tras volver a subir, la D es
    igual a la B. Es la prueba de que la bajada no dejó nada que estorbe a la siguiente subida (por
    ejemplo, un tipo temporal que choque al volver a renombrar).
    """
    exigir_revision(REVISION_NUEVA)
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        a = fotografia(administrador)
        bitacora_a = fotografia_de_bitacora(administrador)
        version_a = version_de_alembic(administrador)
    assert version_a == [(REVISION_ANTERIOR,)]

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        b = fotografia(administrador)
        bitacora_b = fotografia_de_bitacora(administrador)
        version_b = version_de_alembic(administrador)
    assert version_b == [(REVISION_NUEVA,)]
    assert b == a, "La subida solo debía tocar las etiquetas de accion_bitacora"
    assert bitacora_b[:4] == bitacora_a[:4]
    assert bitacora_b[4] == tuple((verbo,) for verbo in VERBOS_0017)

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        c = fotografia(administrador)
        bitacora_c = fotografia_de_bitacora(administrador)
        version_c = version_de_alembic(administrador)
    assert version_c == [(REVISION_ANTERIOR,)]
    assert c == a
    assert bitacora_c == bitacora_a

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        d = fotografia(administrador)
        bitacora_d = fotografia_de_bitacora(administrador)
        version_d = version_de_alembic(administrador)
    assert version_d == [(REVISION_NUEVA,)]
    assert d == b
    assert bitacora_d == bitacora_b
