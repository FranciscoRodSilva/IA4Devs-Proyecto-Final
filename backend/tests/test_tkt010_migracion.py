"""TKT-010a · La migración 0008 siembra la empresa única y los cuatro tipos de partida.

Fila A1 del diseño, fase roja. PostgreSQL real con testcontainers; el esquema sale de
`alembic upgrade head` y las comprobaciones de datos de las pruebas de rechazo leen las filas que
quedaron, no solo el código de error. La migración `0008` se carga dentro del cuerpo de cada prueba
que lee su texto: mientras el archivo no exista el rojo es «no existe» al ejecutar, no un error de
recolección.

Roles de conexión: el rol de migración lee el catálogo y las filas sembradas; el de aplicación
inserta con la fábrica `DatosPresupuesto`, igual que las pruebas de TKT-011.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]
RUTA_V0008 = BACKEND / "migraciones" / "versions" / "v0008_semilla_empresa_y_tipos_de_partida.py"

REVISION_ANTERIOR = "0007"
REVISION_NUEVA = "0008"

# Identificadores fijos del diseño: forma `c1e0a010-<grupo>-4000-8000-<número>`.
EMPRESA_ID = uuid.UUID("c1e0a010-0000-4000-8000-000000000001")
TIPO_MUROS_ID = uuid.UUID("c1e0a010-0001-4000-8000-000000000001")
EMPRESA_ESPERADA: tuple[Any, ...] = (
    EMPRESA_ID,
    "Constructora Celsius",
    "XAXX010101000",
    True,
    6,
)
TIPOS_ESPERADOS: tuple[tuple[uuid.UUID, str, str], ...] = (
    (TIPO_MUROS_ID, "MUROS", "MUROS"),
    (
        uuid.UUID("c1e0a010-0001-4000-8000-000000000002"),
        "PLAFONES_Y_CAJILLOS",
        "PLAFONES Y CAJILLOS",
    ),
    (uuid.UUID("c1e0a010-0001-4000-8000-000000000003"), "ENCHAPES", "ENCHAPES"),
    (uuid.UUID("c1e0a010-0001-4000-8000-000000000004"), "GENERALES", "GENERALES"),
)

# Las cinco tablas cuyos privilegios y restricciones la migración no debe tocar, más `usuario_rol`.
TABLAS_DE_PRIVILEGIOS: tuple[str, ...] = (
    "usuario",
    "empresa",
    "tipo_partida",
    "insumo",
    "precio_insumo",
)
TABLAS_DE_RESTRICCIONES: tuple[str, ...] = (*TABLAS_DE_PRIVILEGIOS, "usuario_rol")

# Lo que la migración no siembra (`CA-10` esc. 2 y `M7`).
TABLAS_SIN_FILAS: tuple[str, ...] = (
    "usuario",
    "usuario_rol",
    "insumo",
    "precio_insumo",
    "obra",
    "nivel",
    "area",
    "partida",
    "concepto",
    "apu",
    "linea_base",
)


# --------------------------------------------------------------------------- ayudas


def cargar_v0008() -> ModuleType:
    """Carga el archivo de la migración `0008` por su ruta; si no existe, la prueba falla diciéndolo."""
    if not RUTA_V0008.exists():
        pytest.fail(f"La migración 0008 no existe todavía: falta {RUTA_V0008.name}")
    especificacion = importlib.util.spec_from_file_location("v0008_semilla_de_prueba", RUTA_V0008)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def guion_de_alembic() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))


def cabeza_de_las_migraciones() -> str:
    """La cabeza que dice `ScriptDirectory`, sin afirmarla por su número."""
    cabezas = guion_de_alembic().get_heads()
    assert len(cabezas) == 1, cabezas
    return cabezas[0]


def version_de_alembic(conexion: Conexion) -> list[tuple[Any, ...]]:
    return conexion.execute("SELECT version_num FROM alembic_version").fetchall()


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608 · tabla fija
    assert fila is not None
    return int(fila[0])


def empresas_sembradas(conexion: Conexion) -> list[tuple[Any, ...]]:
    return [
        tuple(fila)
        for fila in conexion.execute(
            "SELECT id, nombre, rfc, activa, dias_semana_laboral FROM empresa ORDER BY id"
        ).fetchall()
    ]


def tipos_sembrados(conexion: Conexion) -> list[tuple[uuid.UUID, str, str]]:
    return [
        (fila[0], str(fila[1]), str(fila[2]))
        for fila in conexion.execute(
            "SELECT id, clave, nombre FROM tipo_partida ORDER BY id"
        ).fetchall()
    ]


def exigir_semilla_aplicada(conexion: Conexion) -> None:
    """Precondición de las pruebas de regresión y de rechazo: `0008` ya dejó su empresa y sus tipos.

    Sin ella, una prueba de «no cambia nada» o de «no siembra otra cosa» se cumpliría sin que la
    migración exista, y no probaría nada.
    """
    assert contar(conexion, "empresa") == 1, "La precondición es la empresa sembrada por 0008"
    assert contar(conexion, "tipo_partida") == 4, "La precondición son los cuatro tipos de 0008"


def sqlstate_de(error: DBAPIError) -> str | None:
    """El `sqlstate` del error de origen (el de PostgreSQL), no el de la envoltura de SQLAlchemy."""
    origen = error.orig
    assert isinstance(origen, psycopg.Error), repr(origen)
    return origen.sqlstate


def restriccion_de(error: DBAPIError) -> str | None:
    """El nombre de la restricción que PostgreSQL informa en el diagnóstico."""
    origen = error.orig
    assert isinstance(origen, psycopg.Error), repr(origen)
    return origen.diag.constraint_name


def privilegios(conexion: Conexion) -> dict[str, list[tuple[Any, ...]]]:
    """Privilegios de cada rol (incluido `PUBLIC`) sobre las cinco tablas, de tabla y de columna."""
    tablas = list(TABLAS_DE_PRIVILEGIOS)
    return {
        "tabla": [
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
        "columna": [
            tuple(f)
            for f in conexion.execute(
                "SELECT c.relname, at.attname, COALESCE(g.rolname, 'PUBLIC'), a.privilege_type, "
                "a.is_grantable FROM pg_attribute at JOIN pg_class c ON c.oid = at.attrelid "
                "CROSS JOIN LATERAL aclexplode(at.attacl) a "
                "LEFT JOIN pg_roles g ON g.oid = a.grantee "
                "WHERE c.relnamespace = 'public'::regnamespace AND c.relname = ANY(%s) "
                "AND at.attacl IS NOT NULL "
                "ORDER BY c.relname, at.attname, 3, a.privilege_type",
                (tablas,),
            ).fetchall()
        ],
    }


def restricciones(conexion: Conexion) -> list[tuple[Any, ...]]:
    """Restricciones (sin las `NOT NULL`) de las seis tablas, con su definición."""
    return [
        tuple(f)
        for f in conexion.execute(
            "SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
            "AND c.contype <> 'n' ORDER BY 1, 2",
            (list(TABLAS_DE_RESTRICCIONES),),
        ).fetchall()
    ]


# --------------------------------------------------------------------------- TC-A01


def test_tkt010_ca01_la_migracion_siembra_la_empresa_y_los_cuatro_tipos(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-A01 · CA-1 esc. 1 · PA-01 — una base recién migrada ya tiene la empresa y los cuatro tipos.

    `empresa` es exactamente la fila «Constructora Celsius», con el RFC genérico `(asumido)`, activa y
    con seis días de semana laboral por omisión de la base; `tipo_partida` son exactamente las cuatro
    ternas `(id, clave, nombre)` del diseño, con los identificadores fijos.
    """
    migrar(base_vacia)

    with conectar("migracion", base_vacia) as administrador:
        empresas = empresas_sembradas(administrador)
        tipos = tipos_sembrados(administrador)
    assert empresas == [EMPRESA_ESPERADA]
    assert tipos == sorted(TIPOS_ESPERADOS, key=lambda terna: terna[0])


# --------------------------------------------------------------------------- TC-A02


def test_tkt010_ca01_una_obra_referencia_la_empresa_sembrada(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-A02 · CA-1 esc. 2 — una obra con el `empresa_id` de la empresa sembrada entra sin crearla.

    Con el rol de aplicación, la inserción no falla por clave foránea y la empresa sigue siendo la
    única: la obra apunta a la sembrada, no a una creada por la fábrica.
    """
    with conectar("migracion", base_de_prueba) as administrador:
        assert contar(administrador, "empresa") == 1, (
            "La precondición es la empresa sembrada por 0008"
        )

    obra_id = datos_presupuesto.obra(empresa_id=EMPRESA_ID)

    with conectar("migracion", base_de_prueba) as administrador:
        obras = administrador.execute(
            "SELECT id FROM obra WHERE empresa_id = %s", (EMPRESA_ID,)
        ).fetchall()
        empresas = contar(administrador, "empresa")
    assert obras == [(obra_id,)]
    assert empresas == 1


# --------------------------------------------------------------------------- TC-A03


def test_tkt010_ca02_la_siembra_no_sobrescribe_una_empresa_cambiada(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-A03 · CA-2 esc. 1 · M5 — rechazo: una fila existente con otros valores se deja intacta.

    Con la empresa renombrada «Otra Constructora» y un tipo con otro nombre, se vuelven a ejecutar las
    dos sentencias de `_SUBIDA` de `0008` sobre la misma conexión. `ON CONFLICT DO NOTHING` deja las
    filas como estaban: una empresa con el nombre cambiado, cuatro tipos y el nombre cambiado intacto.
    """
    v0008 = cargar_v0008()

    with conectar("migracion", base_de_prueba) as administrador:
        renombrada = administrador.execute("UPDATE empresa SET nombre = 'Otra Constructora'")
        assert renombrada.rowcount == 1, "La precondición es la empresa sembrada por 0008"
        retocado = administrador.execute(
            "UPDATE tipo_partida SET nombre = 'Muros retocados' WHERE clave = 'MUROS'"
        )
        assert retocado.rowcount == 1, "La precondición es el tipo MUROS sembrado por 0008"

        for sentencia in v0008._SUBIDA:
            administrador.execute(sentencia)

        empresas = empresas_sembradas(administrador)
        tipos = tipos_sembrados(administrador)
    assert [(fila[0], fila[1]) for fila in empresas] == [(EMPRESA_ID, "Otra Constructora")]
    assert len(tipos) == 4
    assert (TIPO_MUROS_ID, "MUROS", "Muros retocados") in tipos


# --------------------------------------------------------------------------- TC-A04


def test_tkt010_ca02_bajar_y_subir_no_duplica(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-A04 · CA-2 esc. 2 · CA-R2 — bajar una revisión y subir de nuevo deja lo mismo, sin duplicar.

    Tras la primera subida hay una empresa y cuatro tipos. La bajada a `0007` los elimina y deja los
    seis `rol` de `0002`. La segunda subida vuelve a dejar una empresa y cuatro tipos, con los
    mismos identificadores.
    """
    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        assert empresas_sembradas(administrador) == [EMPRESA_ESPERADA], "La precondición es 0008"
        antes_empresas = empresas_sembradas(administrador)
        antes_tipos = tipos_sembrados(administrador)
    assert len(antes_tipos) == 4

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        sin_empresas = contar(administrador, "empresa")
        sin_tipos = contar(administrador, "tipo_partida")
        roles = contar(administrador, "rol")
        version = version_de_alembic(administrador)
    assert (sin_empresas, sin_tipos) == (0, 0)
    assert roles == 6
    assert version == [(REVISION_ANTERIOR,)]

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        despues_empresas = empresas_sembradas(administrador)
        despues_tipos = tipos_sembrados(administrador)
    assert despues_empresas == antes_empresas
    assert despues_tipos == antes_tipos


# --------------------------------------------------------------------------- TC-A05


@pytest.mark.parametrize(
    ("referencia", "restriccion"),
    [
        pytest.param("obra", "fk_obra_empresa_id", id="obra_con_la_empresa_sembrada"),
        pytest.param("partida", "fk_partida_tipo_partida_id", id="partida_con_el_tipo_muros"),
    ],
)
def test_tkt010_ca03_la_bajada_se_niega_si_lo_sembrado_esta_en_uso(
    base_de_prueba: str,
    migrar: Migrar,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    referencia: str,
    restriccion: str,
) -> None:
    """TC-A05 · CA-3 · S2 — rechazo: la bajada de 0008 se niega, sin borrar nada, si algo usa lo sembrado.

    Con una obra que apunta a la empresa sembrada, o una partida que apunta al tipo `MUROS` sembrado,
    `downgrade 0007` falla con `23001` (`ON DELETE RESTRICT`) y nombra la restricción. La versión
    sigue en la cabeza y la empresa, los cuatro tipos y la fila que los usa siguen presentes.
    """
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_semilla_aplicada(administrador)

    if referencia == "obra":
        usada_id = datos_presupuesto.obra(empresa_id=EMPRESA_ID)
    else:
        usada_id = datos_presupuesto.partida(tipo_partida_id=TIPO_MUROS_ID)

    # Se cuenta después de crear la fila que referencia: la fábrica de la partida crea su propia
    # empresa (partida → obra → empresa), y lo que se vigila es que la bajada fallida no borre ninguna.
    with conectar("migracion", base_de_prueba) as administrador:
        empresas_antes = contar(administrador, "empresa")

    with pytest.raises(DBAPIError) as rechazo:
        migrar(base_de_prueba, REVISION_ANTERIOR, "downgrade")

    texto = str(rechazo.value)
    assert sqlstate_de(rechazo.value) == "23001", texto
    assert restriccion_de(rechazo.value) == restriccion, texto
    with conectar("migracion", base_de_prueba) as administrador:
        version = version_de_alembic(administrador)
        empresas = [fila[0] for fila in empresas_sembradas(administrador)]
        tipos = tipos_sembrados(administrador)
        usadas = administrador.execute(
            f"SELECT id FROM {referencia} WHERE id = %s",  # noqa: S608 · tabla fija por parámetro
            (usada_id,),
        ).fetchall()
    assert version == [(cabeza_de_las_migraciones(),)]
    assert EMPRESA_ID in empresas
    assert len(empresas) == empresas_antes
    assert tipos == sorted(TIPOS_ESPERADOS, key=lambda terna: terna[0])
    assert usadas == [(usada_id,)]


# --------------------------------------------------------------------------- TC-A06


def test_tkt010_ca10_la_migracion_no_siembra_usuarios_ni_insumos(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-A06 · CA-10 esc. 2 · M7 — rechazo: la migración no siembra usuarios, insumos ni obras.

    Con `0008` aplicada (empresa y tipos presentes), `usuario`, `usuario_rol`, `insumo`,
    `precio_insumo`, `obra`, `nivel`, `area`, `partida`, `concepto`, `apu` y `linea_base` tienen cero
    filas: producción nunca recibe credenciales conocidas ni un catálogo inventado.
    """
    with conectar("migracion", base_de_prueba) as administrador:
        exigir_semilla_aplicada(administrador)
        conteos = {tabla: contar(administrador, tabla) for tabla in TABLAS_SIN_FILAS}
    assert conteos == dict.fromkeys(TABLAS_SIN_FILAS, 0)


# --------------------------------------------------------------------------- TC-A07


def test_tkt010_car2_una_sola_cabeza_y_0008_cuelga_de_0007() -> None:
    """TC-A07 · CA-R2 — hay una sola cabeza de migraciones y `0008` cuelga de `0007`.

    No afirma qué revisión es la cabeza: una migración futura no debe romper esta prueba.
    """
    guion = guion_de_alembic()
    cabezas = guion.get_heads()
    assert len(cabezas) == 1, cabezas

    revisiones = {revision.revision: revision for revision in guion.walk_revisions()}
    assert REVISION_NUEVA in revisiones, "La revisión 0008 no existe todavía"
    assert revisiones[REVISION_NUEVA].down_revision == REVISION_ANTERIOR


# --------------------------------------------------------------------------- TC-INV-A1


def test_tkt010_car3_los_privilegios_no_cambian(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-INV-A1 · CA-R3 · invariante 21 — la migración no cambia ningún privilegio.

    Fotografía de los privilegios de los tres roles (y de `PUBLIC`) sobre `usuario`, `empresa`,
    `tipo_partida`, `insumo` y `precio_insumo`, a nivel de tabla y de columna, en `0007` y en la
    cabeza: son iguales. Con el rol de lectura, `SELECT password_hash FROM usuario` responde `42501`.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        antes = privilegios(administrador)
    assert antes["tabla"], "La precondición es que 0007 deja privilegios que comparar"

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        exigir_semilla_aplicada(administrador)
        despues = privilegios(administrador)
    assert despues == antes

    lectura = conectar("lectura", base_vacia)
    with pytest.raises(psycopg.Error) as rechazo:
        lectura.execute("SELECT password_hash FROM usuario")
    assert rechazo.value.sqlstate == "42501"


# --------------------------------------------------------------------------- TC-INV-A2


def test_tkt010_car4_las_restricciones_no_cambian(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-INV-A2 · CA-R4 · invariantes 8 y 27 — la migración no añade, quita ni cambia restricciones.

    Fotografía de `(tabla, restricción, definición)` de `usuario`, `empresa`, `tipo_partida`,
    `insumo`, `precio_insumo` y `usuario_rol` en `0007` y en la cabeza: son iguales, de modo que los
    datos sembrados caben en las restricciones sin relajar ninguna.
    """
    migrar(base_vacia, REVISION_ANTERIOR)
    with conectar("migracion", base_vacia) as administrador:
        antes = restricciones(administrador)
    assert antes, "La precondición es que 0007 deja restricciones que comparar"

    migrar(base_vacia)
    with conectar("migracion", base_vacia) as administrador:
        exigir_semilla_aplicada(administrador)
        despues = restricciones(administrador)
    assert despues == antes
