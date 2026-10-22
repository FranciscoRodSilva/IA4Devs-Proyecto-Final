"""Esquema de la bitácora (TKT-007, fila 1): TC-01 a TC-17.

La migración `v0003` crea el tipo `accion_bitacora`, la tabla `bitacora`, sus dos índices, la
restricción de formato de `regla_negocio` y revoca `UPDATE`, `DELETE` y `TRUNCATE` al rol de
aplicación: la inmutabilidad (invariante 10, RN-04) es un permiso del motor, no una disciplina.

Cada comprobación abre una conexión nueva con el rol de aplicación, o con el de migración donde
se mira el catálogo; nunca la misma que escribió. El rol de aplicación pasa por la guarda de
`conftest.py`. Los casos que escriben empiezan por `exigir_bitacora`, que convierte la ausencia
de la tabla en un fallo con nombre y no en un `UndefinedTable` sin contexto.
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg.types.json import Jsonb
from sqlalchemy.exc import DBAPIError

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]
Migrar = Callable[..., None]

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
BORRADOR = RAIZ / "docs" / "api" / "openapi.yaml"

T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
REVISION_ANTERIOR = "0002"

# Fragmento con que debe terminar `indexdef` de `pg_indexes`: lo que el modelo de datos lista.
ESPERADOS = {
    "ix_bitacora_obra_id_ocurrido_en": "USING btree (obra_id, ocurrido_en DESC)",
    "ix_bitacora_regla_negocio": "USING btree (regla_negocio) WHERE (regla_negocio IS NOT NULL)",
}

COLUMNAS_ESPERADAS = [
    ("id", "uuid", "NO"),
    ("entidad_tipo", "text", "NO"),
    ("entidad_id", "uuid", "NO"),
    ("accion", "accion_bitacora", "NO"),
    ("usuario_id", "uuid", "NO"),
    ("ocurrido_en", "timestamptz", "NO"),
    ("datos_antes", "jsonb", "YES"),
    ("datos_despues", "jsonb", "YES"),
    ("motivo", "text", "YES"),
    ("regla_negocio", "text", "YES"),
    ("obra_id", "uuid", "YES"),
]


# --------------------------------------------------------------------------- ayudas


def diferencias_de_verbos(base: Sequence[str], borrador: Sequence[str]) -> list[str]:
    """Textos que nombran cada verbo en que difieren el enum de la base y el del borrador.

    Un verbo que solo está en un lado se nombra con el lado donde está. Si los conjuntos son
    iguales y el orden no, se nombra la posición y los dos verbos que chocan. Iguales → `[]`.
    """
    diferencias: list[str] = []
    diferencias.extend(
        f"El borrador tiene {verbo} y la base no." for verbo in borrador if verbo not in base
    )
    diferencias.extend(
        f"La base tiene {verbo} y el borrador no." for verbo in base if verbo not in borrador
    )
    if not diferencias:
        diferencias.extend(
            f"Posición {posicion}: la base tiene {en_base} y el borrador {en_borrador}."
            for posicion, (en_base, en_borrador) in enumerate(zip(base, borrador, strict=True), 1)
            if en_base != en_borrador
        )
    return diferencias


def indices_ausentes(esperados: Mapping[str, str], reales: Mapping[str, str]) -> list[str]:
    """Textos que nombran cada índice esperado que falta o cuya definición no es la esperada."""
    problemas: list[str] = []
    for nombre, fragmento in esperados.items():
        if nombre not in reales:
            problemas.append(f"Falta el índice {nombre}.")
        elif not reales[nombre].endswith(fragmento):
            problemas.append(
                f"El índice {nombre} existe con la definición {reales[nombre]!r} "
                f"y debe terminar en {fragmento!r}."
            )
    return problemas


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


def privilegios_por_columna(conexion: Conexion, tabla: str, rol: str) -> set[tuple[str, str]]:
    """Pares (columna, `privilege_type`) que `attacl` concede al rol; vacío si no concede ninguno."""
    filas = conexion.execute(
        "SELECT a.attname, x.privilege_type FROM pg_attribute a "
        "CROSS JOIN LATERAL aclexplode(a.attacl) x "
        "JOIN pg_roles g ON g.oid = x.grantee "
        "WHERE a.attrelid = to_regclass(%s) AND a.attnum > 0 AND NOT a.attisdropped "
        "AND g.rolname = %s",
        (tabla, f"cimenta_{rol}"),
    ).fetchall()
    return {(str(fila[0]), str(fila[1])) for fila in filas}


def exigir_bitacora(conexion: Conexion) -> None:
    """Falla con nombre si la migración que crea `bitacora` no está aplicada."""
    fila = conexion.execute("SELECT to_regclass('bitacora') IS NOT NULL").fetchone()
    assert fila == (True,), "La tabla bitacora no existe: falta la migración v0003 (TKT-007)."


def sembrar_usuario(conexion: Conexion, correo: str) -> uuid.UUID:
    """Un usuario confirmado, para que `bitacora.usuario_id` apunte a alguien real."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", correo, "hash-de-prueba"),
    )
    return identificador


def insertar_asiento(
    conexion: Conexion,
    usuario_id: uuid.UUID | None,
    *,
    accion: str = "CREAR",
    motivo: str | None = None,
    regla_negocio: str | None = None,
    obra_id: uuid.UUID | None = None,
    entidad_id: uuid.UUID | None = None,
    datos_antes: dict[str, object] | None = None,
    datos_despues: dict[str, object] | None = None,
) -> uuid.UUID:
    """INSERT directo sobre `bitacora` con las once columnas; devuelve el `id`."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO bitacora (id, entidad_tipo, entidad_id, accion, usuario_id, ocurrido_en, "
        "datos_antes, datos_despues, motivo, regla_negocio, obra_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            identificador,
            "usuario",
            entidad_id or uuid.uuid4(),
            accion,
            usuario_id,
            T0,
            None if datos_antes is None else Jsonb(datos_antes),
            None if datos_despues is None else Jsonb(datos_despues),
            motivo,
            regla_negocio,
            obra_id,
        ),
    )
    return identificador


def contar_asientos(conexion: Conexion) -> int:
    fila = conexion.execute("SELECT count(*) FROM bitacora").fetchone()
    assert fila is not None
    return int(fila[0])


def verbos_del_borrador() -> list[str]:
    documento = yaml.safe_load(BORRADOR.read_text(encoding="utf-8"))
    return [str(v) for v in documento["components"]["schemas"]["AccionBitacora"]["enum"]]


def verbos_de_la_base(conexion: Conexion) -> list[str]:
    filas = conexion.execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid = to_regtype('accion_bitacora') "
        "ORDER BY enumsortorder"
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def fotografia_de_bitacora(conexion: Conexion) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    """Columnas, restricciones, índices, `relacl` y etiquetas del enum de `bitacora`."""
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


def cabeza_de_las_migraciones() -> str:
    guion = ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas
    return cabezas[0]


# --------------------------------------------------------------------------- TC-01 a TC-04


def test_tkt007_ca01_columnas_y_nulabilidad(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-01 · CA-1 esc. 1 — las once columnas, su tipo y su nulabilidad; ninguna con valor por omisión."""
    with conectar("migracion", base_de_prueba) as administrador:
        filas = administrador.execute(
            "SELECT column_name, udt_name, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = 'bitacora' ORDER BY ordinal_position"
        ).fetchall()

    assert [(nombre, tipo, nula) for nombre, tipo, nula, _ in filas] == COLUMNAS_ESPERADAS
    assert [nombre for nombre, _, _, por_omision in filas if por_omision is not None] == []


def test_tkt007_ca01_clave_foranea_solo_hacia_usuario(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-02 · CA-1 esc. 1 — `usuario_id` tiene clave foránea a `usuario`, `obra_id` ninguna."""
    with conectar("migracion", base_de_prueba) as administrador:
        foraneas = administrador.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = to_regclass('bitacora') AND contype = 'f'"
        ).fetchall()
        primarias = administrador.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = to_regclass('bitacora') AND contype = 'p'"
        ).fetchall()

    assert set(foraneas) == {
        ("fk_bitacora_usuario_id", "FOREIGN KEY (usuario_id) REFERENCES usuario(id)")
    }
    assert not any("obra_id" in definicion for _, definicion in foraneas)
    assert primarias == [("pk_bitacora",)]


def test_tkt007_ca01_enum_igual_al_borrador(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-03 · CA-1 esc. 2 y 4 — el enum de la base es el `AccionBitacora` del borrador, en orden."""
    with conectar("migracion", base_de_prueba) as administrador:
        de_la_base = verbos_de_la_base(administrador)
    del_borrador = verbos_del_borrador()

    assert diferencias_de_verbos(de_la_base, del_borrador) == []
    assert de_la_base == del_borrador
    assert len(de_la_base) == 22


def test_tkt007_ca01_la_diferencia_nombra_el_verbo() -> None:
    """TC-04 · CA-1 esc. 4 — el oráculo de TC-03 nombra el verbo que difiere (sin base)."""
    borrador = verbos_del_borrador()
    assert len(borrador) == 22

    sobrante = diferencias_de_verbos(borrador, [*borrador, "BORRAR"])
    assert len(sobrante) == 1
    assert "BORRAR" in sobrante[0]

    sin_denegar = [verbo for verbo in borrador if verbo != "DENEGAR"]
    faltante_en_la_base = diferencias_de_verbos(sin_denegar, borrador)
    assert len(faltante_en_la_base) == 1
    assert "DENEGAR" in faltante_en_la_base[0]
    faltante_en_el_borrador = diferencias_de_verbos(borrador, sin_denegar)
    assert len(faltante_en_el_borrador) == 1
    assert "DENEGAR" in faltante_en_el_borrador[0]

    permutado = list(borrador)
    permutado[0], permutado[1] = permutado[1], permutado[0]
    de_orden = diferencias_de_verbos(permutado, borrador)
    assert de_orden
    assert any("1" in texto and borrador[0] in texto and borrador[1] in texto for texto in de_orden)

    assert diferencias_de_verbos(borrador, borrador) == []


# --------------------------------------------------------------------------- TC-05 y TC-06


def test_tkt007_ca01_verbo_fuera_del_enum(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-05 · CA-1 esc. 2 — un verbo que no existe lo rechaza el motor y la tabla sigue vacía."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        with pytest.raises(psycopg.errors.InvalidTextRepresentation) as rechazo:
            insertar_asiento(aplicacion, usuario, accion="BORRAR")

    assert rechazo.value.sqlstate == "22P02"
    assert "accion_bitacora" in str(rechazo.value)
    with conectar("aplicacion", base_de_prueba) as otra:
        assert contar_asientos(otra) == 0


def test_tkt007_ca01_sin_usuario_autenticado(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-06 · CA-1 esc. 3 — sin usuario falla NOT NULL; con un usuario inexistente, la clave foránea."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        with pytest.raises(psycopg.errors.NotNullViolation) as nulo:
            insertar_asiento(aplicacion, None)
        with pytest.raises(psycopg.errors.ForeignKeyViolation) as inexistente:
            insertar_asiento(aplicacion, uuid.uuid4())

    assert nulo.value.sqlstate == "23502"
    assert nulo.value.diag.column_name == "usuario_id"
    assert inexistente.value.sqlstate == "23503"
    assert inexistente.value.diag.constraint_name == "fk_bitacora_usuario_id"
    with conectar("aplicacion", base_de_prueba) as otra:
        assert contar_asientos(otra) == 0


# --------------------------------------------------------------------------- TC-07 a TC-11


def test_tkt007_ca03_aplicacion_inserta_y_lee(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-07 · CA-3 esc. 1 — el rol de aplicación inserta un asiento y lo lee con sus once columnas."""
    obra = uuid.uuid4()
    entidad = uuid.uuid4()
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        identificador = insertar_asiento(
            aplicacion,
            usuario,
            accion="AUTORIZAR",
            motivo="Excedente aprobado",
            regla_negocio="RN-03",
            obra_id=obra,
            entidad_id=entidad,
            datos_antes={"disponible": "9000.0000"},
            datos_despues={"excedente": "3000.0000"},
        )

    with conectar("aplicacion", base_de_prueba) as otra:
        fila = otra.execute(
            "SELECT id, entidad_tipo, entidad_id, accion::text, usuario_id, ocurrido_en, "
            "datos_antes, datos_despues, motivo, regla_negocio, obra_id "
            "FROM bitacora WHERE id = %s",
            (identificador,),
        ).fetchone()

    assert fila == (
        identificador,
        "usuario",
        entidad,
        "AUTORIZAR",
        usuario,
        T0,
        {"disponible": "9000.0000"},
        {"excedente": "3000.0000"},
        "Excedente aprobado",
        "RN-03",
        obra,
    )


def test_tkt007_ca03_update_rechazado(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-08 · CA-3 esc. 2, inv. 10 — UPDATE responde permiso denegado y el asiento no cambia."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        identificador = insertar_asiento(aplicacion, usuario, motivo="original")
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as rechazo:
            aplicacion.execute("UPDATE bitacora SET motivo = 'otro'")

    assert rechazo.value.sqlstate == "42501"
    assert "bitacora" in str(rechazo.value)
    with conectar("aplicacion", base_de_prueba) as otra:
        fila = otra.execute(
            "SELECT motivo FROM bitacora WHERE id = %s", (identificador,)
        ).fetchone()
    assert fila == ("original",)


def test_tkt007_ca03_delete_y_truncate_rechazados(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-09 · CA-3 esc. 3, inv. 10 — DELETE y TRUNCATE responden permiso denegado; siguen los dos asientos."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        primero = insertar_asiento(aplicacion, usuario)
        insertar_asiento(aplicacion, usuario)
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as borrado:
            aplicacion.execute("DELETE FROM bitacora WHERE id = %s", (primero,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as vaciado:
            aplicacion.execute("TRUNCATE bitacora")

    assert borrado.value.sqlstate == "42501"
    assert "bitacora" in str(borrado.value)
    assert vaciado.value.sqlstate == "42501"
    assert "bitacora" in str(vaciado.value)
    with conectar("aplicacion", base_de_prueba) as otra:
        assert contar_asientos(otra) == 2


def test_tkt007_ca03_privilegios_exactos(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-10 · CA-3, PA-T4, inv. 10 — `relacl` da a la aplicación SELECT e INSERT y a la lectura SELECT."""
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_bitacora(administrador)
        de_aplicacion = privilegios(administrador, "bitacora", "aplicacion")
        de_lectura = privilegios(administrador, "bitacora", "lectura")
        columnas_de_aplicacion = privilegios_por_columna(administrador, "bitacora", "aplicacion")
        columnas_de_lectura = privilegios_por_columna(administrador, "bitacora", "lectura")

    assert de_aplicacion == {"SELECT", "INSERT"}
    assert de_lectura == {"SELECT"}
    assert columnas_de_aplicacion == set()
    assert columnas_de_lectura == set()


def test_tkt007_ca03_lectura_lee_y_no_escribe(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-11 · CA-3 esc. 4, inv. 21 — el rol de lectura cuenta el asiento y su INSERT responde 42501."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        insertar_asiento(aplicacion, usuario)

    with conectar("lectura", base_de_prueba) as lectura:
        total = lectura.execute("SELECT count(*) FROM bitacora").fetchone()
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as rechazo:
            insertar_asiento(lectura, usuario)

    assert total == (1,)
    assert rechazo.value.sqlstate == "42501"
    assert "bitacora" in str(rechazo.value)
    with conectar("aplicacion", base_de_prueba) as otra:
        assert contar_asientos(otra) == 1


# --------------------------------------------------------------------------- TC-12 y TC-13


def test_tkt007_ca07_indices_con_su_definicion(base_de_prueba: str, conectar: Conectar) -> None:
    """TC-12 · CA-7 esc. 1 — existen los dos índices, el segundo parcial, con su definición."""
    with conectar("migracion", base_de_prueba) as administrador:
        filas = administrador.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = 'bitacora'"
        ).fetchall()
    reales = {str(nombre): str(definicion) for nombre, definicion in filas}

    assert indices_ausentes(ESPERADOS, reales) == []
    assert reales["ix_bitacora_obra_id_ocurrido_en"].endswith(
        "ON public.bitacora USING btree (obra_id, ocurrido_en DESC)"
    )
    assert reales["ix_bitacora_regla_negocio"].endswith(
        "ON public.bitacora USING btree (regla_negocio) WHERE (regla_negocio IS NOT NULL)"
    )


def test_tkt007_ca07_indice_ausente_se_nombra() -> None:
    """TC-13 · CA-7 esc. 2 — el oráculo de TC-12 nombra el índice que falta o el que perdió su WHERE (sin base)."""
    completos = {
        "ix_bitacora_obra_id_ocurrido_en": (
            "CREATE INDEX ix_bitacora_obra_id_ocurrido_en ON public.bitacora "
            "USING btree (obra_id, ocurrido_en DESC)"
        ),
        "ix_bitacora_regla_negocio": (
            "CREATE INDEX ix_bitacora_regla_negocio ON public.bitacora "
            "USING btree (regla_negocio) WHERE (regla_negocio IS NOT NULL)"
        ),
    }
    assert indices_ausentes(ESPERADOS, completos) == []

    sin_el_primero = {k: v for k, v in completos.items() if k != "ix_bitacora_obra_id_ocurrido_en"}
    ausente = indices_ausentes(ESPERADOS, sin_el_primero)
    assert len(ausente) == 1
    assert "ix_bitacora_obra_id_ocurrido_en" in ausente[0]

    sin_where = {
        **completos,
        "ix_bitacora_regla_negocio": (
            "CREATE INDEX ix_bitacora_regla_negocio ON public.bitacora USING btree (regla_negocio)"
        ),
    }
    parcial = indices_ausentes(ESPERADOS, sin_where)
    assert len(parcial) == 1
    assert "ix_bitacora_regla_negocio" in parcial[0]
    assert sin_where["ix_bitacora_regla_negocio"] in parcial[0]


# --------------------------------------------------------------------------- TC-14


@pytest.mark.parametrize(
    ("regla", "rechazada"),
    [
        pytest.param("rn-03", True, id="minusculas"),
        pytest.param("RN-3", True, id="un-digito"),
        pytest.param("RN-033", True, id="tres-digitos"),
        pytest.param("XX-03", True, id="prefijo-ajeno"),
        pytest.param("RN-03 ", True, id="espacio-final"),
        pytest.param("RN-３０", True, id="digitos-de-ancho-completo"),
        pytest.param("RN-03", False, id="bien-formada"),
        pytest.param(None, False, id="nula"),
    ],
)
def test_tkt007_ca12_formato_de_regla_en_la_base(
    base_de_prueba: str, conectar: Conectar, regla: str | None, rechazada: bool
) -> None:
    """TC-14 · CA-12, S2 — el motor rechaza una regla mal formada por su restricción nombrada; `RN-03` y NULL pasan."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        if rechazada:
            with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
                insertar_asiento(aplicacion, usuario, regla_negocio=regla)
            assert rechazo.value.sqlstate == "23514"
            assert rechazo.value.diag.constraint_name == "ck_bitacora_regla_negocio_formato"
        else:
            insertar_asiento(aplicacion, usuario, regla_negocio=regla)

    with conectar("aplicacion", base_de_prueba) as otra:
        assert contar_asientos(otra) == (0 if rechazada else 1)


# --------------------------------------------------------------------------- TC-15 a TC-17


def test_tkt007_ca10_subir_bajar_subir(base_vacia: str, migrar: Migrar, conectar: Conectar) -> None:
    """TC-15 · CA-10 esc. 1 — upgrade head, downgrade 0002 y upgrade head; el catálogo de `bitacora` es el mismo."""
    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        exigir_bitacora(administrador)
        existe_el_tipo = administrador.execute(
            "SELECT to_regtype('accion_bitacora') IS NOT NULL"
        ).fetchone()
        primera = fotografia_de_bitacora(administrador)
    assert existe_el_tipo == (True,)
    assert {fila[0] for fila in primera[0]} == {nombre for nombre, _, _ in COLUMNAS_ESPERADAS}
    assert len(primera[4]) == 22

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        sin_tabla = administrador.execute("SELECT to_regclass('bitacora') IS NULL").fetchone()
        sin_tipo = administrador.execute("SELECT to_regtype('accion_bitacora') IS NULL").fetchone()
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchall()
    assert sin_tabla == (True,)
    assert sin_tipo == (True,)
    assert version == [(REVISION_ANTERIOR,)]

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        segunda = fotografia_de_bitacora(administrador)
    assert segunda == primera


def test_tkt007_ca10_una_sola_cabeza() -> None:
    """TC-16 · CA-10 esc. 2 — la cadena de migraciones tiene una sola cabeza y `0003` está en ella (sin base)."""
    guion = ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))
    cabezas = guion.get_heads()

    assert len(cabezas) == 1
    cadena = [revision.revision for revision in guion.walk_revisions("base", cabezas[0])]
    assert "0003" in cadena


def test_tkt007_ca10_la_bajada_no_borra_asientos(
    base_de_prueba: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-17 · CA-10, RN-04 — con un asiento, `downgrade 0002` lanza y la bitácora sigue intacta."""
    with conectar("aplicacion", base_de_prueba) as aplicacion:
        exigir_bitacora(aplicacion)
        usuario = sembrar_usuario(aplicacion, "ana@cimenta.test")
        insertar_asiento(aplicacion, usuario, motivo="permanente")

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, REVISION_ANTERIOR, "downgrade")

    assert "La bitácora tiene asientos" in str(rechazo.value)
    with conectar("migracion", base_de_prueba) as administrador:
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchall()
        asientos = contar_asientos(administrador)
    assert version == [(cabeza_de_las_migraciones(),)]
    assert asientos == 1
