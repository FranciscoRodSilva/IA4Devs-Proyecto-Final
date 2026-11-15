"""TKT-019 · Restricciones del esquema de `compras`: TC-04 a TC-22 (F2, salvo TC-13 y TC-14, de F4).

`0014` crea siete tablas y deja que el motor sostenga lo que el modelo de datos declara como
invariante: centro de costos (`NOT NULL`), cifras no negativas, recepción dentro de lo autorizado,
resolución completa, valores cerrados. Este archivo prueba cada garantía sin pasar por ningún caso de
uso: escribe con el rol de aplicación, que es quien escribe en producción, y lee el catálogo con el
rol de migración. Cada rechazo comprueba el `SQLSTATE` y el nombre de la restricción
(`diag.constraint_name`), o el de la columna en los `23502` (`diag.column_name`), y que la tabla no
cambió; cada rechazo lleva su control positivo en el borde, para que un `CHECK` que rechaza todo no
pase por bueno.

`TC-13` y `TC-14` (fila F4) prueban la semilla de `0015` y los límites de `folio_consecutivo`: las
dos series en cero, el bloqueo `FOR UPDATE` del rol de aplicación, y el rechazo de una serie
desconocida, de un último folio negativo y de un `INSERT` del rol de aplicación. Quedan fuera de
este archivo, por ser de otras filas, `TC-23` a `TC-26` (privilegios y disparadores, F3), `TC-27`
y `TC-29` (F4).

Los importes y las cantidades se construyen desde cadena, nunca desde `float`. Cuando una fila
viola dos `CHECK` a la vez, PostgreSQL informa el primero por orden alfabético del nombre; las
pruebas eligen valores que violan uno solo, salvo donde se anota.
"""

from __future__ import annotations

import itertools
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from psycopg.types.json import Jsonb

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]

REVISION_NUEVA = "0014"

AHORA = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
NEGATIVO = Decimal("-0.0001")
CERO = Decimal("0.0000")

TABLAS_COMPRAS: tuple[str, ...] = (
    "requisicion",
    "requisicion_renglon",
    "orden_compra",
    "orden_compra_renglon",
    "solicitud_autorizacion",
    "reprogramacion_entrega",
    "folio_consecutivo",
)

# --------------------------------------------------------------------------- ayudas


def guion_de_alembic() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(toml_file=str(BACKEND / "pyproject.toml")))


def exigir_revision(revision: str) -> None:
    """La cadena de Alembic debe conocer `revision`; si no, el rojo es esta aserción y no un error."""
    conocidas = {revision_.revision for revision_ in guion_de_alembic().walk_revisions()}
    assert revision in conocidas, (
        f"Falta la migración {revision} (v{revision}_compras_esquema.py): Alembic no la conoce "
        f"(TKT-019, fila F2). Revisiones conocidas: {sorted(conocidas)}"
    )


def exigir_tabla(conexion: Conexion, tabla: str) -> None:
    """La precondición de toda prueba que escribe en una tabla de `compras`: que la migración exista."""
    fila = conexion.execute("SELECT to_regclass(%s)", (f"public.{tabla}",)).fetchone()
    assert fila is not None and fila[0] is not None, (
        f"Falta la migración 0014: la tabla `{tabla}` no existe (TKT-019, fila F2)"
    )


def insertar(conexion: Conexion, tabla: str, valores: dict[str, Any]) -> uuid.UUID:
    conexion.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(tabla),
            sql.SQL(", ").join(sql.Identifier(columna) for columna in valores),
            sql.SQL(", ").join(sql.Placeholder() for _ in valores),
        ),
        list(valores.values()),
    )
    return uuid.UUID(str(valores["id"])) if "id" in valores else uuid.UUID(int=0)


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
    ).fetchone()
    assert fila is not None
    return int(fila[0])


# Cada rechazo es (SQLSTATE, restricción o None, columna o None).
Rechazo = tuple[str, str | None, str | None]


def intentar(
    conexion: Conexion, tabla: str, valores: dict[str, Any], rechazo: Rechazo | None
) -> None:
    """Inserta `valores`. Con `rechazo`, exige ese `SQLSTATE`, esa restricción y esa columna, y que la
    tabla no cambie; sin él, exige que la fila entre."""
    antes = contar(conexion, tabla)
    if rechazo is None:
        insertar(conexion, tabla, valores)
        assert contar(conexion, tabla) == antes + 1, "El control positivo debía insertar la fila"
        return

    sqlstate, restriccion, columna = rechazo
    with pytest.raises(psycopg.Error) as error:
        insertar(conexion, tabla, valores)

    assert error.value.sqlstate == sqlstate, str(error.value)
    if restriccion is not None:
        assert error.value.diag.constraint_name == restriccion, str(error.value)
    if columna is not None:
        assert error.value.diag.column_name == columna, str(error.value)
    assert contar(conexion, tabla) == antes, "El rechazo no debe dejar ninguna fila"


def check(restriccion: str) -> Rechazo:
    return ("23514", restriccion, None)


# --------------------------------------------------------------------------- fábricas

_folios = itertools.count(1)


@dataclass
class Entorno:
    """Las filas padre de las siete tablas, ya escritas, y la conexión del rol de aplicación."""

    conexion: Conexion
    usuario: uuid.UUID
    obra: uuid.UUID
    tipo_partida: uuid.UUID
    insumo: uuid.UUID


@pytest.fixture
def entorno(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> Entorno:
    """Un usuario, una obra, un tipo de partida y un insumo reales, escritos con el rol de aplicación.

    Solo toca tablas anteriores a `0014`: en rojo no falla aquí, falla en la aserción de la prueba.
    """
    return Entorno(
        conexion=conectar("aplicacion", base_de_prueba),
        usuario=datos_presupuesto.usuario(),
        obra=datos_presupuesto.obra(codigo="OB-T019"),
        tipo_partida=datos_presupuesto.tipo_partida(),
        insumo=datos_presupuesto.insumo_nuevo(),
    )


def exigir_compras(e: Entorno) -> None:
    for tabla in TABLAS_COMPRAS:
        exigir_tabla(e.conexion, tabla)


def fila_requisicion(e: Entorno, **cambios: Any) -> dict[str, Any]:
    """Una requisición `EVALUADA` con folio único que cumple todo; `cambios` pisa columnas."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "folio": f"REQ-{next(_folios):04d}",
        "obra_id": e.obra,
        "tipo_partida_id": e.tipo_partida,
        "solicitante_id": e.usuario,
        "estado": "EVALUADA",
        "importe_solicitado": Decimal("8000.0000"),
        "creado_en": AHORA,
        "actualizado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_requisicion_renglon(
    e: Entorno, requisicion_id: uuid.UUID, **cambios: Any
) -> dict[str, Any]:
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "requisicion_id": requisicion_id,
        "insumo_id": e.insumo,
        "cantidad": Decimal("10.0000"),
        "costo_unitario_estimado": Decimal("800.0000"),
        "importe": Decimal("8000.0000"),
    }
    valores.update(cambios)
    return valores


def fila_orden(e: Entorno, requisicion_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Una orden viva; `proveedor_id` no existe en ninguna tabla: prueba la ausencia de clave foránea."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "folio": f"OC-{next(_folios):04d}",
        "requisicion_id": requisicion_id,
        "obra_id": e.obra,
        "proveedor_id": uuid.uuid4(),
        "importe": Decimal("8000.0000"),
        "creado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_orden_renglon(e: Entorno, orden_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Sin `cantidad_recibida` ni `cantidad_excedente_autorizada`: lo decide el motor (`DEFAULT 0`)."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "orden_compra_id": orden_id,
        "insumo_id": e.insumo,
        "cantidad_ordenada": Decimal("10.0000"),
        "fecha_compromiso": date(2026, 11, 20),
        "costo_unitario": Decimal("800.0000"),
        "importe": Decimal("8000.0000"),
    }
    valores.update(cambios)
    return valores


def fila_solicitud(e: Entorno, **cambios: Any) -> dict[str, Any]:
    """Una solicitud `PENDIENTE` por `EXCEDE_PRESUPUESTO` sobre una requisición cualquiera."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "motivo": "EXCEDE_PRESUPUESTO",
        "entidad_tipo": "REQUISICION",
        "entidad_id": uuid.uuid4(),
        "obra_id": e.obra,
        "regla_negocio": "RN-03",
        "solicitante_id": e.usuario,
        "rol_autorizador": "DIRECCION_GENERAL",
        "estado": "PENDIENTE",
        "contexto": Jsonb({"disponible": "12000.0000"}),
        "creado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_reprogramacion(e: Entorno, renglon_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "orden_compra_renglon_id": renglon_id,
        "fecha_anterior": date(2026, 11, 20),
        "fecha_nueva": date(2026, 11, 27),
        "saldo_pendiente": Decimal("5.0000"),
        "motivo": "El proveedor aplazó la entrega.",
        "registrado_por_id": e.usuario,
        "ocurrido_en": AHORA,
    }
    valores.update(cambios)
    return valores


def requisicion_valida(e: Entorno, **cambios: Any) -> uuid.UUID:
    return insertar(e.conexion, "requisicion", fila_requisicion(e, **cambios))


def orden_valida(e: Entorno, requisicion_id: uuid.UUID | None = None, **cambios: Any) -> uuid.UUID:
    requisicion = requisicion_id if requisicion_id is not None else requisicion_valida(e)
    return insertar(e.conexion, "orden_compra", fila_orden(e, requisicion, **cambios))


def renglon_de_orden_valido(
    e: Entorno, orden_id: uuid.UUID | None = None, **cambios: Any
) -> uuid.UUID:
    orden = orden_id if orden_id is not None else orden_valida(e)
    return insertar(e.conexion, "orden_compra_renglon", fila_orden_renglon(e, orden, **cambios))


def fila_con_padres(e: Entorno, tabla: str, **cambios: Any) -> dict[str, Any]:
    """Una fila válida de `tabla`, con sus padres ya escritos, para pisar con `cambios`."""
    if tabla == "requisicion":
        return fila_requisicion(e, **cambios)
    if tabla == "requisicion_renglon":
        return fila_requisicion_renglon(e, requisicion_valida(e), **cambios)
    if tabla == "orden_compra":
        return fila_orden(e, requisicion_valida(e), **cambios)
    if tabla == "orden_compra_renglon":
        return fila_orden_renglon(e, orden_valida(e), **cambios)
    if tabla == "reprogramacion_entrega":
        return fila_reprogramacion(e, renglon_de_orden_valido(e), **cambios)
    raise AssertionError(f"Tabla sin fábrica: {tabla}")


# --------------------------------------------------------------------------- TC-04

# Nombre, tipo, precisión, escala, nulable, valor por omisión exacto (None: sin valor por omisión).
# El orden es el del diseño («Infraestructura y esquema», sentencias 1 a 7).
Columna = tuple[str, str, int | None, int | None, str, str | None]

UUID_ = "uuid"
TEXTO = "text"
INSTANTE = "timestamp with time zone"


def _importe(nombre: str, nulable: str = "NO") -> Columna:
    return (nombre, "numeric", 18, 4, nulable, None)


def _cantidad(nombre: str, nulable: str = "NO", omision: str | None = None) -> Columna:
    return (nombre, "numeric", 14, 4, nulable, omision)


def _simple(nombre: str, tipo: str, nulable: str = "NO") -> Columna:
    return (nombre, tipo, None, None, nulable, None)


COLUMNAS: dict[str, tuple[Columna, ...]] = {
    "requisicion": (
        _simple("id", UUID_),
        _simple("folio", TEXTO, "YES"),
        _simple("obra_id", UUID_),
        _simple("tipo_partida_id", UUID_),
        _simple("solicitante_id", UUID_),
        _simple("estado", TEXTO),
        _simple("regla_bloqueo", TEXTO, "YES"),
        _importe("importe_solicitado"),
        _importe("importe_disponible", "YES"),
        _importe("importe_excedente", "YES"),
        _simple("evaluada_en", INSTANTE, "YES"),
        _simple("motivo_cancelacion", TEXTO, "YES"),
        _simple("observaciones", TEXTO, "YES"),
        _simple("creado_en", INSTANTE),
        _simple("actualizado_en", INSTANTE),
    ),
    "requisicion_renglon": (
        _simple("id", UUID_),
        _simple("requisicion_id", UUID_),
        _simple("insumo_id", UUID_),
        _cantidad("cantidad"),
        _cantidad("costo_unitario_estimado"),
        _importe("importe"),
        _cantidad("cantidad_disponible", "YES"),
    ),
    "orden_compra": (
        _simple("id", UUID_),
        _simple("folio", TEXTO),
        _simple("requisicion_id", UUID_),
        _simple("obra_id", UUID_),
        _simple("proveedor_id", UUID_),
        _importe("importe"),
        _simple("cancelada_en", INSTANTE, "YES"),
        _simple("motivo_cancelacion", TEXTO, "YES"),
        _simple("creado_en", INSTANTE),
    ),
    "orden_compra_renglon": (
        _simple("id", UUID_),
        _simple("orden_compra_id", UUID_),
        _simple("insumo_id", UUID_),
        _cantidad("cantidad_ordenada"),
        _cantidad("cantidad_recibida", omision="0"),
        _cantidad("cantidad_excedente_autorizada", omision="0"),
        _simple("fecha_compromiso", "date"),
        _cantidad("costo_unitario"),
        _importe("importe"),
    ),
    "solicitud_autorizacion": (
        _simple("id", UUID_),
        _simple("motivo", TEXTO),
        _simple("entidad_tipo", TEXTO),
        _simple("entidad_id", UUID_),
        _simple("obra_id", UUID_),
        _simple("regla_negocio", TEXTO),
        _simple("orden_compra_renglon_id", UUID_, "YES"),
        _cantidad("cantidad_excedente", "YES"),
        _simple("solicitante_id", UUID_),
        _simple("rol_autorizador", TEXTO),
        _simple("estado", TEXTO),
        _simple("resuelta_por_id", UUID_, "YES"),
        _simple("resuelta_en", INSTANTE, "YES"),
        _simple("motivo_resolucion", TEXTO, "YES"),
        _simple("contexto", "jsonb"),
        _simple("creado_en", INSTANTE),
    ),
    "reprogramacion_entrega": (
        _simple("id", UUID_),
        _simple("orden_compra_renglon_id", UUID_),
        _simple("fecha_anterior", "date"),
        _simple("fecha_nueva", "date"),
        _cantidad("saldo_pendiente"),
        _simple("motivo", TEXTO),
        _simple("registrado_por_id", UUID_),
        _simple("ocurrido_en", INSTANTE),
    ),
    "folio_consecutivo": (
        _simple("serie", TEXTO),
        ("ultimo", "bigint", 64, 0, "NO", "0"),
    ),
}

# Nombre -> tipo de `pg_constraint.contype`: las del diseño, ni una más. Los índices únicos de `pk_*`
# y `uq_*` nacen de estas restricciones; el único parcial es un índice, no una restricción.
RESTRICCIONES: dict[str, dict[str, str]] = {
    "requisicion": {
        "pk_requisicion": "p",
        "fk_requisicion_obra_id": "f",
        "fk_requisicion_tipo_partida_id": "f",
        "fk_requisicion_solicitante_id": "f",
        "uq_requisicion_folio": "u",
        "ck_requisicion_estado": "c",
        "ck_requisicion_regla_bloqueo": "c",
        "ck_requisicion_importe_solicitado_no_negativo": "c",
        "ck_requisicion_importe_excedente_no_negativo": "c",
        "ck_requisicion_folio_fuera_de_borrador": "c",
        "ck_requisicion_cancelacion_con_motivo": "c",
    },
    "requisicion_renglon": {
        "pk_requisicion_renglon": "p",
        "fk_requisicion_renglon_requisicion_id": "f",
        "fk_requisicion_renglon_insumo_id": "f",
        "ck_requisicion_renglon_cantidad_no_negativo": "c",
        "ck_requisicion_renglon_costo_unitario_estimado_no_negativo": "c",
        "ck_requisicion_renglon_importe_no_negativo": "c",
    },
    "orden_compra": {
        "pk_orden_compra": "p",
        "fk_orden_compra_requisicion_id": "f",
        "fk_orden_compra_obra_id": "f",
        "uq_orden_compra_folio": "u",
        "ck_orden_compra_importe_no_negativo": "c",
        "ck_orden_compra_cancelacion_con_motivo": "c",
    },
    "orden_compra_renglon": {
        "pk_orden_compra_renglon": "p",
        "fk_orden_compra_renglon_orden_compra_id": "f",
        "fk_orden_compra_renglon_insumo_id": "f",
        "ck_orden_compra_renglon_cantidad_ordenada_no_negativo": "c",
        "ck_orden_compra_renglon_cantidad_recibida_no_negativo": "c",
        "ck_orden_compra_renglon_excedente_autorizado_no_negativo": "c",
        "ck_orden_compra_renglon_costo_unitario_no_negativo": "c",
        "ck_orden_compra_renglon_importe_no_negativo": "c",
        "ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado": "c",
    },
    "solicitud_autorizacion": {
        "pk_solicitud_autorizacion": "p",
        "fk_solicitud_autorizacion_obra_id": "f",
        "fk_solicitud_autorizacion_orden_compra_renglon_id": "f",
        "fk_solicitud_autorizacion_solicitante_id": "f",
        "fk_solicitud_autorizacion_rol_autorizador": "f",
        "fk_solicitud_autorizacion_resuelta_por_id": "f",
        "ck_solicitud_autorizacion_motivo": "c",
        "ck_solicitud_autorizacion_entidad_tipo": "c",
        "ck_solicitud_autorizacion_estado": "c",
        "ck_solicitud_autorizacion_regla_negocio_formato": "c",
        "ck_solicitud_autorizacion_cantidad_excedente_positiva": "c",
        "ck_solicitud_autorizacion_excede_ordenado_con_renglon": "c",
        "ck_solicitud_autorizacion_resolucion_completa": "c",
    },
    "reprogramacion_entrega": {
        "pk_reprogramacion_entrega": "p",
        "fk_reprogramacion_entrega_orden_compra_renglon_id": "f",
        "fk_reprogramacion_entrega_registrado_por_id": "f",
        "ck_reprogramacion_entrega_saldo_pendiente_no_negativo": "c",
        "ck_reprogramacion_entrega_motivo_no_vacio": "c",
    },
    "folio_consecutivo": {
        "pk_folio_consecutivo": "p",
        "ck_folio_consecutivo_serie": "c",
        "ck_folio_consecutivo_ultimo_no_negativo": "c",
    },
}

# Nombre de la clave foránea -> (columna, tabla destino, columna destino). Todas `ON DELETE RESTRICT`.
CLAVES_FORANEAS: dict[str, tuple[str, str, str]] = {
    "fk_requisicion_obra_id": ("obra_id", "obra", "id"),
    "fk_requisicion_tipo_partida_id": ("tipo_partida_id", "tipo_partida", "id"),
    "fk_requisicion_solicitante_id": ("solicitante_id", "usuario", "id"),
    "fk_requisicion_renglon_requisicion_id": ("requisicion_id", "requisicion", "id"),
    "fk_requisicion_renglon_insumo_id": ("insumo_id", "insumo", "id"),
    "fk_orden_compra_requisicion_id": ("requisicion_id", "requisicion", "id"),
    "fk_orden_compra_obra_id": ("obra_id", "obra", "id"),
    "fk_orden_compra_renglon_orden_compra_id": ("orden_compra_id", "orden_compra", "id"),
    "fk_orden_compra_renglon_insumo_id": ("insumo_id", "insumo", "id"),
    "fk_solicitud_autorizacion_obra_id": ("obra_id", "obra", "id"),
    "fk_solicitud_autorizacion_orden_compra_renglon_id": (
        "orden_compra_renglon_id",
        "orden_compra_renglon",
        "id",
    ),
    "fk_solicitud_autorizacion_solicitante_id": ("solicitante_id", "usuario", "id"),
    "fk_solicitud_autorizacion_rol_autorizador": ("rol_autorizador", "rol", "clave"),
    "fk_solicitud_autorizacion_resuelta_por_id": ("resuelta_por_id", "usuario", "id"),
    "fk_reprogramacion_entrega_orden_compra_renglon_id": (
        "orden_compra_renglon_id",
        "orden_compra_renglon",
        "id",
    ),
    "fk_reprogramacion_entrega_registrado_por_id": ("registrado_por_id", "usuario", "id"),
}

# Índices de las siete tablas con su `indexdef` exacto: los de las llaves y los únicos, y los siete
# explícitos del diseño (sentencias 8 a 14). El único parcial lleva su `WHERE`.
INDICES: dict[str, str] = {
    "pk_requisicion": "CREATE UNIQUE INDEX pk_requisicion ON public.requisicion USING btree (id)",
    "uq_requisicion_folio": (
        "CREATE UNIQUE INDEX uq_requisicion_folio ON public.requisicion USING btree (folio)"
    ),
    "ix_requisicion_obra_id_tipo_partida_id_estado": (
        "CREATE INDEX ix_requisicion_obra_id_tipo_partida_id_estado "
        "ON public.requisicion USING btree (obra_id, tipo_partida_id, estado)"
    ),
    "pk_requisicion_renglon": (
        "CREATE UNIQUE INDEX pk_requisicion_renglon ON public.requisicion_renglon USING btree (id)"
    ),
    "ix_requisicion_renglon_requisicion_id": (
        "CREATE INDEX ix_requisicion_renglon_requisicion_id "
        "ON public.requisicion_renglon USING btree (requisicion_id)"
    ),
    "pk_orden_compra": "CREATE UNIQUE INDEX pk_orden_compra ON public.orden_compra USING btree (id)",
    "uq_orden_compra_folio": (
        "CREATE UNIQUE INDEX uq_orden_compra_folio ON public.orden_compra USING btree (folio)"
    ),
    "uq_orden_compra_requisicion_id_vigente": (
        "CREATE UNIQUE INDEX uq_orden_compra_requisicion_id_vigente "
        "ON public.orden_compra USING btree (requisicion_id) WHERE (cancelada_en IS NULL)"
    ),
    "ix_orden_compra_obra_id": (
        "CREATE INDEX ix_orden_compra_obra_id ON public.orden_compra USING btree (obra_id)"
    ),
    "pk_orden_compra_renglon": (
        "CREATE UNIQUE INDEX pk_orden_compra_renglon "
        "ON public.orden_compra_renglon USING btree (id)"
    ),
    "ix_orden_compra_renglon_orden_compra_id": (
        "CREATE INDEX ix_orden_compra_renglon_orden_compra_id "
        "ON public.orden_compra_renglon USING btree (orden_compra_id)"
    ),
    "pk_solicitud_autorizacion": (
        "CREATE UNIQUE INDEX pk_solicitud_autorizacion "
        "ON public.solicitud_autorizacion USING btree (id)"
    ),
    "ix_solicitud_autorizacion_entidad_tipo_entidad_id": (
        "CREATE INDEX ix_solicitud_autorizacion_entidad_tipo_entidad_id "
        "ON public.solicitud_autorizacion USING btree (entidad_tipo, entidad_id)"
    ),
    "pk_reprogramacion_entrega": (
        "CREATE UNIQUE INDEX pk_reprogramacion_entrega "
        "ON public.reprogramacion_entrega USING btree (id)"
    ),
    "ix_reprogramacion_entrega_orden_compra_renglon_id": (
        "CREATE INDEX ix_reprogramacion_entrega_orden_compra_renglon_id "
        "ON public.reprogramacion_entrega USING btree (orden_compra_renglon_id)"
    ),
    "pk_folio_consecutivo": (
        "CREATE UNIQUE INDEX pk_folio_consecutivo ON public.folio_consecutivo USING btree (serie)"
    ),
}


def _comprobar_columnas(conexion: Conexion, tabla: str) -> None:
    reales = conexion.execute(
        "SELECT ordinal_position, column_name, data_type, character_maximum_length, "
        "numeric_precision, numeric_scale, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY ordinal_position",
        (tabla,),
    ).fetchall()
    esperadas = COLUMNAS[tabla]
    assert [(r[0], r[1]) for r in reales] == [(i + 1, e[0]) for i, e in enumerate(esperadas)], (
        f"{tabla}: las columnas y su orden no son los del diseño: {[r[1] for r in reales]}"
    )
    for real, (nombre, tipo, precision, escala, nulable, omision) in zip(
        reales, esperadas, strict=True
    ):
        donde = f"{tabla}.{nombre}"
        assert real[2] == tipo, f"{donde}: tipo {real[2]}, esperaba {tipo}"
        assert real[3] is None, f"{donde}: no debe tener longitud máxima, tiene {real[3]}"
        assert real[4] == precision, f"{donde}: precisión {real[4]}, esperaba {precision}"
        assert real[5] == escala, f"{donde}: escala {real[5]}, esperaba {escala}"
        assert real[6] == nulable, f"{donde}: is_nullable {real[6]}, esperaba {nulable}"
        if omision is None:
            assert real[7] is None, f"{donde}: no debe tener valor por omisión, tiene {real[7]}"
        else:
            assert real[7] is not None and re.fullmatch(
                rf"\(?{omision}\)?(::\w+)?", str(real[7])
            ), f"{donde}: el valor por omisión era {real[7]} y debía ser {omision}"


def test_tkt019_ca01_tablas_columnas_restricciones_e_indices(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-04 · CA-1, CA-10 · RN-02 — las siete tablas, con lo que el diseño declara y nada más.

    Por tabla: las columnas en orden con tipo, precisión, escala, nulabilidad y valor por omisión
    exactos (`numeric` 18,4 en importes y 14,4 en precios y cantidades, `date` en las fechas de
    negocio, `timestamp with time zone` en los instantes, `bigint` en `ultimo`, `jsonb` en `contexto`,
    `DEFAULT 0` en `cantidad_recibida`, `cantidad_excedente_autorizada` y `ultimo`); el mapa exacto
    `conname -> contype`; cada clave foránea con su tabla destino y `ON DELETE RESTRICT`; ninguna
    columna `USER-DEFINED` (ningún `ENUM`, ADR-030); y el conjunto exacto de índices con su
    `indexdef`, el único parcial con su `WHERE (cancelada_en IS NULL)`.

    No comprueba privilegios ni disparadores: son de la fila F3 (`TC-23` a `TC-26`).
    """
    exigir_revision(REVISION_NUEVA)
    with conectar("migracion", base_de_prueba) as administrador:
        tablas = {
            str(f[0])
            for f in administrador.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ).fetchall()
        }
        faltan = sorted(set(TABLAS_COMPRAS) - tablas)
        assert not faltan, f"Faltan tablas de `compras` (TKT-019, fila F2): {faltan}"

        for tabla in TABLAS_COMPRAS:
            _comprobar_columnas(administrador, tabla)

        restricciones = administrador.execute(
            "SELECT t.relname, c.conname, c.contype, pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
            "AND c.contype <> 'n'",
            (list(TABLAS_COMPRAS),),
        ).fetchall()
        for tabla in TABLAS_COMPRAS:
            reales = {str(f[1]): str(f[2]) for f in restricciones if f[0] == tabla}
            assert reales == RESTRICCIONES[tabla], (
                f"{tabla}: las restricciones no son las del diseño. "
                f"Sobran {sorted(set(reales) - set(RESTRICCIONES[tabla]))}, "
                f"faltan {sorted(set(RESTRICCIONES[tabla]) - set(reales))}, "
                f"o cambia su tipo: {reales}"
            )
        definiciones = {str(f[1]): str(f[3]) for f in restricciones}
        for nombre, (columna, destino, columna_destino) in CLAVES_FORANEAS.items():
            assert definiciones[nombre] == (
                f"FOREIGN KEY ({columna}) REFERENCES {destino}({columna_destino}) "
                "ON DELETE RESTRICT"
            ), f"{nombre}: {definiciones[nombre]}"
        assert {n for n, t in ((str(f[1]), str(f[2])) for f in restricciones) if t == "f"} == set(
            CLAVES_FORANEAS
        ), "Las claves foráneas no son las 16 del diseño"

        enumerados = administrador.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ANY(%s) AND data_type = 'USER-DEFINED'",
            (list(TABLAS_COMPRAS),),
        ).fetchall()
        assert enumerados == [], f"Ninguna columna debe ser un ENUM (ADR-030): {enumerados}"

        indices = {
            str(f[0]): str(f[1])
            for f in administrador.execute(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = ANY(%s)",
                (list(TABLAS_COMPRAS),),
            ).fetchall()
        }
        assert indices == INDICES, (
            f"Los índices no son los del diseño. Sobran {sorted(set(indices) - set(INDICES))}, "
            f"faltan {sorted(set(INDICES) - set(indices))}, "
            f"difieren {sorted(n for n in set(indices) & set(INDICES) if indices[n] != INDICES[n])}"
        )


# --------------------------------------------------------------------------- TC-05


def test_tkt019_ca01_borrar_una_obra_con_requisicion_responde_23001(entorno: Entorno) -> None:
    """TC-05 · CA-1 · D-4 — con una requisición colgada, `DELETE FROM obra` responde `23001`.

    `ON DELETE RESTRICT` explícito en todas las claves foráneas. El `23001` (`restrict_violation`)
    es el de borrar un padre con hijos; el `23503` es el de insertar un hijo huérfano. La obra sigue.
    """
    exigir_compras(entorno)
    requisicion_valida(entorno)

    with pytest.raises(psycopg.Error) as error:
        entorno.conexion.execute("DELETE FROM obra WHERE id = %s", (entorno.obra,))

    assert error.value.sqlstate == "23001", str(error.value)
    assert error.value.diag.constraint_name == "fk_requisicion_obra_id", str(error.value)
    assert entorno.conexion.execute(
        "SELECT count(*) FROM obra WHERE id = %s", (entorno.obra,)
    ).fetchone() == (1,), "La obra debía seguir ahí"


# --------------------------------------------------------------------------- TC-06


@pytest.mark.parametrize(
    ("tabla", "columna"),
    [
        pytest.param("requisicion", "obra_id", id="requisicion_sin_obra"),
        pytest.param("requisicion", "tipo_partida_id", id="requisicion_sin_tipo_de_partida"),
        pytest.param("orden_compra", "obra_id", id="orden_sin_obra"),
    ],
)
def test_tkt019_ca02_el_motor_exige_el_centro_de_costos(
    tabla: str, columna: str, entorno: Entorno
) -> None:
    """TC-06 · CA-2 · RN-02 · INV-1 — sin obra o sin tipo de partida, el motor responde `23502`.

    Una requisición con `obra_id` nulo, una con `tipo_partida_id` nulo y una orden con `obra_id`
    nulo: cada una se rechaza con `23502` sobre la columna exacta y no deja fila. El control positivo
    de cada tabla está en `test_tkt019_ca02_con_centro_de_costos_la_fila_entra`.
    """
    exigir_compras(entorno)
    valores = fila_con_padres(entorno, tabla, **{columna: None})
    intentar(entorno.conexion, tabla, valores, ("23502", None, columna))


@pytest.mark.parametrize("tabla", ["requisicion", "orden_compra"])
def test_tkt019_ca02_con_centro_de_costos_la_fila_entra(tabla: str, entorno: Entorno) -> None:
    """TC-06 (control positivo) · CA-2 — la requisición y la orden con obra y tipo de partida entran."""
    exigir_compras(entorno)
    intentar(entorno.conexion, tabla, fila_con_padres(entorno, tabla), None)


# --------------------------------------------------------------------------- TC-07

_MOTIVO = "La obra reprogramó el frente."


@pytest.mark.parametrize(
    ("cambios", "rechazo"),
    [
        pytest.param({"estado": "BORRADOR", "folio": None}, None, id="borrador_sin_folio"),
        pytest.param({"estado": "EVALUADA"}, None, id="evaluada"),
        pytest.param({"estado": "BLOQUEADA"}, None, id="bloqueada"),
        pytest.param({"estado": "AUTORIZADA"}, None, id="autorizada"),
        pytest.param({"estado": "RECHAZADA"}, None, id="rechazada"),
        pytest.param(
            {"estado": "CANCELADA", "motivo_cancelacion": _MOTIVO}, None, id="cancelada_con_motivo"
        ),
        pytest.param({"estado": "CONVERTIDA"}, None, id="convertida"),
        pytest.param(
            {"estado": "SIN_EFECTO"}, check("ck_requisicion_estado"), id="estado_desconocido"
        ),
        pytest.param(
            {"estado": "evaluada"}, check("ck_requisicion_estado"), id="estado_en_minusculas"
        ),
        pytest.param({"estado": None}, ("23502", None, "estado"), id="estado_nulo"),
    ],
)
def test_tkt019_ca03_estados_de_la_requisicion(
    cambios: dict[str, Any], rechazo: Rechazo | None, entorno: Entorno
) -> None:
    """TC-07 · CA-3 · RN-04 — la requisición admite los siete estados y ninguno más.

    Los siete valores entran (`BORRADOR` con `folio` nulo y `CANCELADA` con su motivo: son los dos
    que la fila exige distinto, `D-15` y `D-16`); `RECHAZADA` y `CANCELADA` son valores distintos.
    `"SIN_EFECTO"` y `"evaluada"` en minúsculas se rechazan con `23514` sobre `ck_requisicion_estado`
    y el estado nulo con `23502` sobre la columna `estado`.
    """
    exigir_compras(entorno)
    intentar(entorno.conexion, "requisicion", fila_requisicion(entorno, **cambios), rechazo)


# --------------------------------------------------------------------------- TC-08


@pytest.mark.parametrize(
    ("cambios", "rechazo"),
    [
        pytest.param(
            {"estado": "EVALUADA", "folio": None},
            check("ck_requisicion_folio_fuera_de_borrador"),
            id="evaluada_sin_folio",
        ),
        pytest.param(
            {"estado": "CANCELADA", "folio": "REQ-X", "motivo_cancelacion": None},
            check("ck_requisicion_cancelacion_con_motivo"),
            id="cancelada_sin_motivo",
        ),
        pytest.param(
            {"estado": "BLOQUEADA", "regla_bloqueo": "REGLA"},
            check("ck_requisicion_regla_bloqueo"),
            id="regla_bloqueo_desconocida",
        ),
        pytest.param(
            {"estado": "BLOQUEADA", "regla_bloqueo": "RN-07"},
            check("ck_requisicion_regla_bloqueo"),
            id="regla_bloqueo_distinta_de_rn_03",
        ),
        # Controles positivos: sin ellos, un `CHECK` que rechaza todo pasaría igual.
        pytest.param({"estado": "BORRADOR", "folio": None}, None, id="borrador_sin_folio_entra"),
        pytest.param(
            {"estado": "CANCELADA", "motivo_cancelacion": _MOTIVO}, None, id="cancelada_con_motivo"
        ),
        pytest.param(
            {"estado": "BLOQUEADA", "regla_bloqueo": "RN-03"}, None, id="bloqueada_por_rn_03"
        ),
        pytest.param({"estado": "EVALUADA", "regla_bloqueo": None}, None, id="evaluada_sin_regla"),
    ],
)
def test_tkt019_ca03_folio_motivo_y_regla_segun_estado(
    cambios: dict[str, Any], rechazo: Rechazo | None, entorno: Entorno
) -> None:
    """TC-08 · CA-3 · D-15, D-16 — el folio, el motivo y la regla dependen del estado.

    Fuera de `BORRADOR` el folio es obligatorio (`ck_requisicion_folio_fuera_de_borrador`); una
    requisición `CANCELADA` lleva su motivo (`ck_requisicion_cancelacion_con_motivo`); y
    `regla_bloqueo` solo admite `RN-03` o nulo (`ck_requisicion_regla_bloqueo`). Los cuatro
    controles (borrador sin folio, cancelada con motivo, bloqueada por `RN-03` y evaluada sin regla)
    entran.
    """
    exigir_compras(entorno)
    intentar(entorno.conexion, "requisicion", fila_requisicion(entorno, **cambios), rechazo)


# --------------------------------------------------------------------------- TC-09

# (tabla, columna, restricción). El nombre del excedente autorizado se aparta del patrón: el nombre
# completo tendría 65 caracteres y PostgreSQL lo truncaría a 63.
CIFRAS: list[tuple[str, str, str]] = [
    ("requisicion", "importe_solicitado", "ck_requisicion_importe_solicitado_no_negativo"),
    ("requisicion", "importe_excedente", "ck_requisicion_importe_excedente_no_negativo"),
    ("requisicion_renglon", "cantidad", "ck_requisicion_renglon_cantidad_no_negativo"),
    (
        "requisicion_renglon",
        "costo_unitario_estimado",
        "ck_requisicion_renglon_costo_unitario_estimado_no_negativo",
    ),
    ("requisicion_renglon", "importe", "ck_requisicion_renglon_importe_no_negativo"),
    ("orden_compra", "importe", "ck_orden_compra_importe_no_negativo"),
    (
        "orden_compra_renglon",
        "cantidad_ordenada",
        "ck_orden_compra_renglon_cantidad_ordenada_no_negativo",
    ),
    (
        "orden_compra_renglon",
        "cantidad_recibida",
        "ck_orden_compra_renglon_cantidad_recibida_no_negativo",
    ),
    (
        "orden_compra_renglon",
        "cantidad_excedente_autorizada",
        "ck_orden_compra_renglon_excedente_autorizado_no_negativo",
    ),
    (
        "orden_compra_renglon",
        "costo_unitario",
        "ck_orden_compra_renglon_costo_unitario_no_negativo",
    ),
    ("orden_compra_renglon", "importe", "ck_orden_compra_renglon_importe_no_negativo"),
    (
        "reprogramacion_entrega",
        "saldo_pendiente",
        "ck_reprogramacion_entrega_saldo_pendiente_no_negativo",
    ),
]
_IDS_CIFRAS = [f"{tabla}.{columna}" for tabla, columna, _ in CIFRAS]


@pytest.mark.parametrize(("tabla", "columna", "restriccion"), CIFRAS, ids=_IDS_CIFRAS)
def test_tkt019_ca04_ninguna_cifra_es_negativa(
    tabla: str, columna: str, restriccion: str, entorno: Entorno
) -> None:
    """TC-09 · CA-4 · INV-8 — `-0.0001` en cualquier importe, precio o cantidad se rechaza con `23514`.

    Una columna por caso, con su restricción nombrada `ck_<tabla>_<columna>_no_negativo` (la del
    excedente autorizado se aparta del patrón por el límite de 63 caracteres). En
    `cantidad_ordenada` el valor negativo viola además la recepción dentro de lo autorizado
    (`0 <= -0.0001` es falso): PostgreSQL informa el primero por orden alfabético, y
    `ck_..._cantidad_ordenada_no_negativo` precede a `ck_..._recibida_dentro_...`.
    """
    exigir_compras(entorno)
    valores = fila_con_padres(entorno, tabla, **{columna: NEGATIVO})
    intentar(entorno.conexion, tabla, valores, check(restriccion))


@pytest.mark.parametrize(("tabla", "columna", "restriccion"), CIFRAS, ids=_IDS_CIFRAS)
def test_tkt019_ca04_el_cero_se_admite_en_cada_cifra(
    tabla: str, columna: str, restriccion: str, entorno: Entorno
) -> None:
    """TC-09 (control positivo) · CA-4 — `0.0000` entra en cada columna: el borde es `>= 0`, no `> 0`."""
    exigir_compras(entorno)
    assert restriccion.startswith(f"ck_{tabla}_")
    valores = fila_con_padres(entorno, tabla, **{columna: CERO})
    intentar(entorno.conexion, tabla, valores, None)


# --------------------------------------------------------------------------- TC-10


def test_tkt019_ca04_el_disponible_admite_negativos(entorno: Entorno) -> None:
    """TC-10 · CA-4 · INV-8 — `importe_disponible` y `cantidad_disponible` admiten valores negativos.

    Son la cifra del momento de evaluar: una excepción autorizada puede dejar el consumido por
    encima del tope y el disponible, negativo (decisión de la persona dueña, 2026-11-14). Se
    guardan y se leen iguales.
    """
    exigir_compras(entorno)
    requisicion = requisicion_valida(entorno, importe_disponible=Decimal("-1500.0000"))
    renglon = insertar(
        entorno.conexion,
        "requisicion_renglon",
        fila_requisicion_renglon(entorno, requisicion, cantidad_disponible=Decimal("-3.5000")),
    )

    importe = entorno.conexion.execute(
        "SELECT importe_disponible FROM requisicion WHERE id = %s", (requisicion,)
    ).fetchone()
    cantidad = entorno.conexion.execute(
        "SELECT cantidad_disponible FROM requisicion_renglon WHERE id = %s", (renglon,)
    ).fetchone()
    assert importe == (Decimal("-1500.0000"),)
    assert cantidad == (Decimal("-3.5000"),)


# --------------------------------------------------------------------------- TC-11


def test_tkt019_ca04_cantidad_fuera_de_escala_responde_22003(entorno: Entorno) -> None:
    """TC-11 · CA-4 — diez dígitos enteros no caben en `numeric(14,4)` y el motor responde `22003`."""
    exigir_compras(entorno)
    requisicion = requisicion_valida(entorno)
    valores = fila_requisicion_renglon(entorno, requisicion, cantidad=Decimal("10000000000.0000"))
    intentar(entorno.conexion, "requisicion_renglon", valores, ("22003", None, None))


@pytest.mark.parametrize(
    ("cantidad", "guardada"),
    [
        pytest.param(Decimal("9999999999.9999"), Decimal("9999999999.9999"), id="maximo_cabe"),
        pytest.param(Decimal("-0.00004"), Decimal("0.0000"), id="quinto_decimal_se_redondea"),
    ],
)
def test_tkt019_ca04_la_escala_del_motor_redondea_y_no_rechaza(
    cantidad: Decimal, guardada: Decimal, entorno: Entorno
) -> None:
    """TC-11 · CA-4 — el máximo cabe y un quinto decimal se redondea en silencio.

    `9999999999.9999` entra. `-0.00004` se guarda como `0.0000`: `numeric(14,4)` redondea antes de
    comprobar el `CHECK`, así que el motor no lo ve negativo. Documenta el comportamiento: rechazar
    decimales de más es del API de TKT-021 y siguientes (`ImporteNoNegativo`), no del esquema.
    """
    exigir_compras(entorno)
    requisicion = requisicion_valida(entorno)
    renglon = insertar(
        entorno.conexion,
        "requisicion_renglon",
        fila_requisicion_renglon(entorno, requisicion, cantidad=cantidad),
    )
    fila = entorno.conexion.execute(
        "SELECT cantidad FROM requisicion_renglon WHERE id = %s", (renglon,)
    ).fetchone()
    assert fila == (guardada,)


# --------------------------------------------------------------------------- TC-12


def test_tkt019_ca05_la_requisicion_con_folio_repetido_responde_23505(entorno: Entorno) -> None:
    """TC-12 · CA-5 · RN-02 — dos requisiciones con el mismo folio: `23505` sobre `uq_requisicion_folio`."""
    exigir_compras(entorno)
    requisicion_valida(entorno, folio="REQ-REPETIDO")
    valores = fila_requisicion(entorno, folio="REQ-REPETIDO")
    intentar(entorno.conexion, "requisicion", valores, ("23505", "uq_requisicion_folio", None))


def test_tkt019_ca05_la_orden_con_folio_repetido_responde_23505(entorno: Entorno) -> None:
    """TC-12 · CA-5 · RN-02 — dos órdenes con el mismo folio: `23505` sobre `uq_orden_compra_folio`.

    Cada orden cuelga de su propia requisición, para que solo choque el folio y no el índice único
    parcial de la requisición (`D-5`).
    """
    exigir_compras(entorno)
    orden_valida(entorno, folio="OC-REPETIDO")
    valores = fila_orden(entorno, requisicion_valida(entorno), folio="OC-REPETIDO")
    intentar(entorno.conexion, "orden_compra", valores, ("23505", "uq_orden_compra_folio", None))


def test_tkt019_ca05_dos_borradores_sin_folio_no_chocan(entorno: Entorno) -> None:
    """TC-12 (control positivo) · CA-5 · D-15 — los `NULL` del folio de un borrador son distintos."""
    exigir_compras(entorno)
    for _ in range(2):
        intentar(
            entorno.conexion,
            "requisicion",
            fila_requisicion(entorno, estado="BORRADOR", folio=None),
            None,
        )
    fila = entorno.conexion.execute(
        "SELECT count(*) FROM requisicion WHERE estado = 'BORRADOR' AND folio IS NULL"
    ).fetchone()
    assert fila == (2,)


# --------------------------------------------------------------------------- TC-13 y TC-14

SERIES_SEMBRADAS: list[tuple[str, int]] = [("ORDEN_COMPRA", 0), ("REQUISICION", 0)]


def series_de_folios(conexion: Conexion) -> list[tuple[Any, ...]]:
    """Las series de `folio_consecutivo` con su último folio, ordenadas por serie."""
    filas = conexion.execute(
        "SELECT serie, ultimo FROM folio_consecutivo ORDER BY serie"
    ).fetchall()
    return [tuple(fila) for fila in filas]


def exigir_series_sembradas(conexion: Conexion) -> None:
    """La precondición de toda prueba que escribe sobre una serie: que `0015` la haya sembrado.

    Sin ella, un `UPDATE` sobre una tabla vacía no toca ninguna fila y el rojo sería un «no lanzó»
    sin explicación; así es una aserción con el motivo escrito.
    """
    series = series_de_folios(conexion)
    assert series == SERIES_SEMBRADAS, (
        f"Falta la migración 0015 (v0015_semilla_folios_de_compras.py): `folio_consecutivo` "
        f"debía tener {SERIES_SEMBRADAS} y tiene {series} (TKT-019, fila F4)"
    )


def test_tkt019_ca05_series_sembradas_y_bloqueables(entorno: Entorno) -> None:
    """TC-13 · CA-5 · RN-02 — `0015` deja las dos series en cero y el rol de aplicación las bloquea y avanza.

    En una transacción, `SELECT ultimo … FOR UPDATE` devuelve `(0,)` y `UPDATE … SET ultimo = ultimo
    + 1 … RETURNING ultimo` devuelve `(1,)`. Tras confirmar, `REQUISICION` vale 1 y `ORDEN_COMPRA`
    sigue en 0: cada serie es independiente.
    """
    exigir_compras(entorno)
    assert series_de_folios(entorno.conexion) == SERIES_SEMBRADAS, (
        "Falta la migración 0015: `folio_consecutivo` debía tener exactamente ORDEN_COMPRA y "
        "REQUISICION con ultimo = 0 (TKT-019, fila F4)"
    )

    with entorno.conexion.transaction():
        bloqueada = entorno.conexion.execute(
            "SELECT ultimo FROM folio_consecutivo WHERE serie = 'REQUISICION' FOR UPDATE"
        ).fetchone()
        assert bloqueada == (0,)
        avanzada = entorno.conexion.execute(
            "UPDATE folio_consecutivo SET ultimo = ultimo + 1 WHERE serie = 'REQUISICION' "
            "RETURNING ultimo"
        ).fetchone()
        assert avanzada == (1,)

    assert series_de_folios(entorno.conexion) == [("ORDEN_COMPRA", 0), ("REQUISICION", 1)]


def test_tkt019_ca05_serie_desconocida_y_ultimo_negativo(
    entorno: Entorno, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-14 · CA-5 · CA-11 · D-17 — una serie ajena, un último negativo y un `INSERT` de la aplicación se rechazan.

    La serie `ENTRADA_ALMACEN` se inserta con el rol de migración (excepción declarada del diseño,
    «Notas de ejecución»): el de aplicación ya no tiene `INSERT` sobre `folio_consecutivo`, y con él
    el rechazo sería de privilegio y no del `CHECK`. Con el rol de migración: `23514` sobre
    `ck_folio_consecutivo_serie`. Con el de aplicación: `UPDATE … SET ultimo = -1` →
    `23514` sobre `ck_folio_consecutivo_ultimo_no_negativo` y `INSERT` de una serie →
    `42501` (sin restricción: es un privilegio). Ninguno cambia la tabla.
    """
    exigir_compras(entorno)
    exigir_series_sembradas(entorno.conexion)

    with conectar("migracion", base_de_prueba) as administrador:
        intentar(
            administrador,
            "folio_consecutivo",
            {"serie": "ENTRADA_ALMACEN", "ultimo": 0},
            check("ck_folio_consecutivo_serie"),
        )

    with pytest.raises(psycopg.Error) as negativo:
        entorno.conexion.execute(
            "UPDATE folio_consecutivo SET ultimo = %s WHERE serie = 'REQUISICION'", (-1,)
        )
    assert negativo.value.sqlstate == "23514", str(negativo.value)
    assert negativo.value.diag.constraint_name == "ck_folio_consecutivo_ultimo_no_negativo"

    intentar(
        entorno.conexion,
        "folio_consecutivo",
        {"serie": "REQUISICION", "ultimo": 0},
        ("42501", None, None),
    )
    assert series_de_folios(entorno.conexion) == SERIES_SEMBRADAS, (
        "Nada de lo anterior debía escribir"
    )


def test_tkt019_ca05_serie_valida_y_ultimo_cero_entran(
    entorno: Entorno, base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-14 (control positivo) · CA-5 — el borde que el rechazo vigila sí entra.

    Con el rol de migración, una serie válida entra (se borra `ORDEN_COMPRA` y se vuelve a insertar:
    la clave primaria impide duplicar una serie viva). Con el de aplicación, `ultimo = 0`, el borde
    de `ck_folio_consecutivo_ultimo_no_negativo`, se acepta sobre una serie que ya estaba en 5.
    """
    exigir_compras(entorno)
    exigir_series_sembradas(entorno.conexion)

    with conectar("migracion", base_de_prueba) as administrador:
        administrador.execute("DELETE FROM folio_consecutivo WHERE serie = 'ORDEN_COMPRA'")
        intentar(administrador, "folio_consecutivo", {"serie": "ORDEN_COMPRA", "ultimo": 0}, None)

    entorno.conexion.execute("UPDATE folio_consecutivo SET ultimo = 5 WHERE serie = 'REQUISICION'")
    reiniciada = entorno.conexion.execute(
        "UPDATE folio_consecutivo SET ultimo = 0 WHERE serie = 'REQUISICION' RETURNING ultimo"
    ).fetchone()
    assert reiniciada == (0,)
    assert series_de_folios(entorno.conexion) == SERIES_SEMBRADAS


# --------------------------------------------------------------------------- TC-15

_RESUELTA = {
    "motivo_resolucion": "Dirección General autoriza el excedente.",
    "resuelta_en": AHORA,
}


def _resolucion(e: Entorno, **cambios: Any) -> dict[str, Any]:
    return {**_RESUELTA, "resuelta_por_id": e.usuario, **cambios}


@pytest.mark.parametrize("estado", ["AUTORIZADA", "RECHAZADA"])
@pytest.mark.parametrize(
    "falta",
    ["motivo_resolucion", "resuelta_por_id", "resuelta_en"],
)
def test_tkt019_ca06_la_resolucion_exige_motivo_actor_y_momento(
    estado: str, falta: str, entorno: Entorno
) -> None:
    """TC-15 · CA-6 · RN-04 · INV-9 — resolver sin motivo, sin actor o sin momento se rechaza.

    `AUTORIZADA` y `RECHAZADA`, cada una sin `motivo_resolucion`, sin `resuelta_por_id` o sin
    `resuelta_en`: `23514` sobre `ck_solicitud_autorizacion_resolucion_completa` (`D-11`). Seis
    casos: el `CHECK` completo del invariante 9, no solo el motivo.
    """
    exigir_compras(entorno)
    valores = fila_solicitud(entorno, estado=estado, **_resolucion(entorno, **{falta: None}))
    intentar(
        entorno.conexion,
        "solicitud_autorizacion",
        valores,
        check("ck_solicitud_autorizacion_resolucion_completa"),
    )


def test_tkt019_ca06_un_estado_fuera_de_los_tres_se_rechaza(entorno: Entorno) -> None:
    """TC-15 · CA-6 — `"CANCELADA"` no es un estado de la solicitud: `23514` sobre `ck_..._estado`.

    Lleva la resolución completa para que solo falle el estado (`ck_..._estado` precede por
    orden alfabético a `ck_..._resolucion_completa`).
    """
    exigir_compras(entorno)
    valores = fila_solicitud(entorno, estado="CANCELADA", **_resolucion(entorno))
    intentar(
        entorno.conexion,
        "solicitud_autorizacion",
        valores,
        check("ck_solicitud_autorizacion_estado"),
    )


@pytest.mark.parametrize(
    "estado",
    [
        pytest.param("PENDIENTE", id="pendiente_sin_resolucion"),
        pytest.param("AUTORIZADA", id="autorizada_resuelta"),
        pytest.param("RECHAZADA", id="rechazada_resuelta"),
    ],
)
def test_tkt019_ca06_los_tres_estados_entran_con_lo_que_les_toca(
    estado: str, entorno: Entorno
) -> None:
    """TC-15 (control positivo) · CA-6 — `PENDIENTE` sin nada de resolución y las otras dos con los tres campos."""
    exigir_compras(entorno)
    resolucion = {} if estado == "PENDIENTE" else _resolucion(entorno)
    valores = fila_solicitud(entorno, estado=estado, **resolucion)
    intentar(entorno.conexion, "solicitud_autorizacion", valores, None)


# --------------------------------------------------------------------------- TC-16

_EXCEDE_ORDENADO = "ck_solicitud_autorizacion_excede_ordenado_con_renglon"


@pytest.mark.parametrize(
    ("motivo", "con_renglon", "cantidad", "rechazo"),
    [
        pytest.param(
            "EXCEDE_ORDENADO",
            False,
            Decimal("1.0000"),
            check(_EXCEDE_ORDENADO),
            id="ordenado_sin_renglon",
        ),
        pytest.param(
            "EXCEDE_ORDENADO", True, None, check(_EXCEDE_ORDENADO), id="ordenado_sin_cantidad"
        ),
        pytest.param(
            "EXCEDE_ORDENADO", False, None, check(_EXCEDE_ORDENADO), id="ordenado_sin_ninguno"
        ),
        pytest.param(
            "EXCEDE_PRESUPUESTO", True, None, check(_EXCEDE_ORDENADO), id="presupuesto_con_renglon"
        ),
        pytest.param(
            "EXCEDE_PRESUPUESTO",
            False,
            Decimal("1.0000"),
            check(_EXCEDE_ORDENADO),
            id="presupuesto_con_cantidad",
        ),
        pytest.param(
            "EXCEDE_PRESUPUESTO",
            True,
            Decimal("1.0000"),
            check(_EXCEDE_ORDENADO),
            id="presupuesto_con_los_dos",
        ),
        # Controles positivos.
        pytest.param(
            "EXCEDE_ORDENADO", True, Decimal("0.0001"), None, id="ordenado_con_los_dos_en_el_borde"
        ),
        pytest.param("EXCEDE_PRESUPUESTO", False, None, None, id="presupuesto_sin_ninguno"),
    ],
)
def test_tkt019_ca07_excede_ordenado_apunta_a_su_renglon(
    motivo: str,
    con_renglon: bool,
    cantidad: Decimal | None,
    rechazo: Rechazo | None,
    entorno: Entorno,
) -> None:
    """TC-16 · CA-7 · RN-07 · PA-16 — `EXCEDE_ORDENADO` lleva renglón y cantidad, y solo él.

    Con `EXCEDE_ORDENADO`, falta el renglón, la cantidad o los dos: `23514`. Con otro motivo, sobra
    el renglón, la cantidad o los dos: el mismo `23514` (el `CHECK` es de doble sentido). Controles:
    `EXCEDE_ORDENADO` con los dos y la cantidad en `0.0001` entra, y `EXCEDE_PRESUPUESTO` sin
    ninguno también.
    """
    exigir_compras(entorno)
    renglon = renglon_de_orden_valido(entorno)
    valores = fila_solicitud(
        entorno,
        motivo=motivo,
        orden_compra_renglon_id=renglon if con_renglon else None,
        cantidad_excedente=cantidad,
    )
    intentar(entorno.conexion, "solicitud_autorizacion", valores, rechazo)


# --------------------------------------------------------------------------- TC-17


@pytest.mark.parametrize(
    ("cambios", "con_renglon", "rechazo"),
    [
        pytest.param(
            {"motivo": "OTRO"},
            False,
            check("ck_solicitud_autorizacion_motivo"),
            id="motivo_desconocido",
        ),
        pytest.param(
            {"entidad_tipo": "requisicion"},
            False,
            check("ck_solicitud_autorizacion_entidad_tipo"),
            id="entidad_tipo_en_minusculas",
        ),
        pytest.param(
            {"regla_negocio": "RN3"},
            False,
            check("ck_solicitud_autorizacion_regla_negocio_formato"),
            id="regla_sin_guion",
        ),
        pytest.param(
            {"regla_negocio": "RN-003"},
            False,
            check("ck_solicitud_autorizacion_regla_negocio_formato"),
            id="regla_con_tres_digitos",
        ),
        pytest.param(
            {"regla_negocio": "rn-03"},
            False,
            check("ck_solicitud_autorizacion_regla_negocio_formato"),
            id="regla_en_minusculas",
        ),
        pytest.param(
            {"rol_autorizador": "GERENTE"},
            False,
            ("23503", "fk_solicitud_autorizacion_rol_autorizador", None),
            id="rol_que_no_existe",
        ),
        pytest.param(
            {"motivo": "EXCEDE_ORDENADO", "cantidad_excedente": CERO},
            True,
            check("ck_solicitud_autorizacion_cantidad_excedente_positiva"),
            id="cantidad_excedente_cero",
        ),
        pytest.param({"contexto": None}, False, ("23502", None, "contexto"), id="contexto_nulo"),
        # Controles positivos: los cuatro motivos, las dos entidades y las reglas del borde.
        pytest.param({"motivo": "EXCEDE_PRESUPUESTO"}, False, None, id="motivo_excede_presupuesto"),
        pytest.param(
            {"motivo": "EXCEDE_CONSIGNACION"}, False, None, id="motivo_excede_consignacion"
        ),
        pytest.param({"motivo": "TRABAJO_EXTRA"}, False, None, id="motivo_trabajo_extra"),
        pytest.param(
            {"motivo": "EXCEDE_ORDENADO", "cantidad_excedente": Decimal("1.0000")},
            True,
            None,
            id="motivo_excede_ordenado",
        ),
        pytest.param({"entidad_tipo": "REQUISICION"}, False, None, id="entidad_requisicion"),
        pytest.param({"entidad_tipo": "ORDEN_COMPRA"}, False, None, id="entidad_orden_compra"),
        pytest.param({"regla_negocio": "RN-15"}, False, None, id="regla_rn_15"),
        pytest.param({"rol_autorizador": "DIRECTOR_PROYECTOS"}, False, None, id="rol_que_existe"),
    ],
)
def test_tkt019_ca07_valores_cerrados_de_la_solicitud(
    cambios: dict[str, Any], con_renglon: bool, rechazo: Rechazo | None, entorno: Entorno
) -> None:
    """TC-17 · CA-7 · D-2, D-12, D-13 — la solicitud solo admite los valores cerrados del diseño.

    `motivo = "OTRO"`, `entidad_tipo = "requisicion"` (minúsculas, a diferencia de la bitácora),
    `regla_negocio` que no es `RN-NN` (`"RN3"`, `"RN-003"`, `"rn-03"`), un `rol_autorizador` que no
    existe en `rol` (`23503`, clave foránea), una `cantidad_excedente` en cero y un `contexto` nulo
    (`23502`). Controles: los cuatro motivos, las dos entidades, `RN-15` y un rol que existe entran.
    """
    exigir_compras(entorno)
    if con_renglon:
        cambios = {**cambios, "orden_compra_renglon_id": renglon_de_orden_valido(entorno)}
    intentar(
        entorno.conexion, "solicitud_autorizacion", fila_solicitud(entorno, **cambios), rechazo
    )


# --------------------------------------------------------------------------- TC-18


def _leer_renglon(e: Entorno, renglon: uuid.UUID) -> tuple[Decimal, Decimal]:
    fila = e.conexion.execute(
        "SELECT cantidad_recibida, cantidad_excedente_autorizada "
        "FROM orden_compra_renglon WHERE id = %s",
        (renglon,),
    ).fetchone()
    assert fila is not None
    return fila[0], fila[1]


def test_tkt019_ca08_recien_insertado_lo_recibido_y_el_excedente_valen_cero(
    entorno: Entorno,
) -> None:
    """TC-18 · CA-8 — `cantidad_recibida` y `cantidad_excedente_autorizada` nacen en `0.0000` (`DEFAULT 0`)."""
    exigir_compras(entorno)
    renglon = renglon_de_orden_valido(entorno)
    assert _leer_renglon(entorno, renglon) == (Decimal("0.0000"), Decimal("0.0000"))


_RECIBIDA_DENTRO = "ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado"
_EXCEDENTE_NEGATIVO = "ck_orden_compra_renglon_excedente_autorizado_no_negativo"


@pytest.mark.parametrize(
    ("recibida", "excedente", "rechazo"),
    [
        pytest.param(
            Decimal("10.0001"), CERO, check(_RECIBIDA_DENTRO), id="recibe_de_mas_sin_excedente"
        ),
        pytest.param(
            Decimal("12.0001"), Decimal("2.0000"), check(_RECIBIDA_DENTRO), id="pasa_del_excedente"
        ),
        pytest.param(CERO, NEGATIVO, check(_EXCEDENTE_NEGATIVO), id="excedente_negativo"),
        # Controles positivos en el borde.
        pytest.param(Decimal("10.0000"), CERO, None, id="recibe_exactamente_lo_ordenado"),
        pytest.param(Decimal("12.0000"), Decimal("2.0000"), None, id="recibe_hasta_el_excedente"),
    ],
)
def test_tkt019_ca08_recibir_de_mas_solo_con_excedente_autorizado(
    recibida: Decimal, excedente: Decimal, rechazo: Rechazo | None, entorno: Entorno
) -> None:
    """TC-18 · CA-8 · RN-07 · INV-2 — lo recibido solo pasa de lo ordenado por el excedente autorizado.

    Por `UPDATE` sobre un renglón con `cantidad_ordenada = 10`: recibir `10.0001` sin excedente se
    rechaza con `23514` sobre `ck_orden_compra_renglon_recibida_dentro_de_lo_autorizado`; `10.0000`
    entra; con excedente `2`, `12.0000` entra y `12.0001` se rechaza; un excedente negativo se
    rechaza sobre `ck_orden_compra_renglon_excedente_autorizado_no_negativo`. Tras un rechazo, el
    renglón conserva sus cifras (`0.0000` y `0.0000`).
    """
    exigir_compras(entorno)
    renglon = renglon_de_orden_valido(entorno)
    actualizar = (
        "UPDATE orden_compra_renglon SET cantidad_recibida = %s, "
        "cantidad_excedente_autorizada = %s WHERE id = %s"
    )

    if rechazo is None:
        entorno.conexion.execute(actualizar, (recibida, excedente, renglon))
        assert _leer_renglon(entorno, renglon) == (recibida, excedente)
        return

    sqlstate, restriccion, _ = rechazo
    with pytest.raises(psycopg.Error) as error:
        entorno.conexion.execute(actualizar, (recibida, excedente, renglon))
    assert error.value.sqlstate == sqlstate, str(error.value)
    assert error.value.diag.constraint_name == restriccion, str(error.value)
    assert _leer_renglon(entorno, renglon) == (Decimal("0.0000"), Decimal("0.0000"))


# --------------------------------------------------------------------------- TC-19


def test_tkt019_ca09_la_orden_sin_clave_al_proveedor_ni_estado(entorno: Entorno) -> None:
    """TC-19 · CA-9 · RN-06 — `proveedor_id` es referencia lógica y la orden no guarda su estado.

    En `pg_constraint` ninguna clave foránea de `orden_compra` cubre `proveedor_id` (modelo de datos
    §2: una clave invertiría la arista `proveedores -> compras`); la tabla no tiene `estado` ni
    ninguna columna cuyo nombre contenga `cierre` (el estado se deriva de las cantidades); sí tiene
    `cancelada_en` y `motivo_cancelacion`. Una orden con un `proveedor_id` que no existe entra.
    """
    exigir_compras(entorno)
    columnas = {
        str(f[0])
        for f in entorno.conexion.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'orden_compra'"
        ).fetchall()
    }
    cubiertas = {
        str(f[0])
        for f in entorno.conexion.execute(
            "SELECT a.attname FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) "
            "WHERE c.conrelid = to_regclass('public.orden_compra') AND c.contype = 'f'"
        ).fetchall()
    }
    assert "proveedor_id" in columnas
    assert "proveedor_id" not in cubiertas, f"Columnas con clave foránea: {sorted(cubiertas)}"
    assert "estado" not in columnas, "El estado de la orden se deriva, no se guarda"
    assert [c for c in columnas if "cierre" in c] == [], "No hay motivo de cierre"
    assert {"cancelada_en", "motivo_cancelacion"} <= columnas

    intentar(
        entorno.conexion,
        "orden_compra",
        fila_orden(entorno, requisicion_valida(entorno), proveedor_id=uuid.uuid4()),
        None,
    )


# --------------------------------------------------------------------------- TC-20

_CANCELACION = "ck_orden_compra_cancelacion_con_motivo"


@pytest.mark.parametrize(
    ("cambios", "rechazo"),
    [
        pytest.param(
            {"cancelada_en": AHORA, "motivo_cancelacion": None},
            check(_CANCELACION),
            id="cancelacion_sin_motivo",
        ),
        pytest.param(
            {"cancelada_en": None, "motivo_cancelacion": "Sin cancelar."},
            check(_CANCELACION),
            id="motivo_sin_cancelacion",
        ),
        pytest.param({}, None, id="orden_viva"),
        pytest.param(
            {"cancelada_en": AHORA, "motivo_cancelacion": "El proveedor no entrega."},
            None,
            id="orden_cancelada_con_motivo",
        ),
    ],
)
def test_tkt019_ca09_cancelacion_con_motivo(
    cambios: dict[str, Any], rechazo: Rechazo | None, entorno: Entorno
) -> None:
    """TC-20 · CA-9 · D-1 — la cancelación y su motivo van juntos, en los dos sentidos.

    Solo `cancelada_en` o solo `motivo_cancelacion`: `23514` sobre
    `ck_orden_compra_cancelacion_con_motivo`. Controles: ninguno de los dos (orden viva) y los dos
    entran.
    """
    exigir_compras(entorno)
    valores = fila_orden(entorno, requisicion_valida(entorno), **cambios)
    intentar(entorno.conexion, "orden_compra", valores, rechazo)


# --------------------------------------------------------------------------- TC-21


def test_tkt019_ca09_una_orden_vigente_por_requisicion(entorno: Entorno) -> None:
    """TC-21 · CA-9 · D-5 — como mucho una orden viva por requisición; una cancelada no estorba.

    Una segunda orden viva de la misma requisición se rechaza con `23505`; el `constraint_name` es el
    del índice único parcial `uq_orden_compra_requisicion_id_vigente`. Tras cancelar la primera
    (`UPDATE` con `cancelada_en` y motivo), la segunda entra: §14 permite `CONVERTIDA -> EVALUADA` y
    reconvertir.
    """
    exigir_compras(entorno)
    requisicion = requisicion_valida(entorno)
    primera = orden_valida(entorno, requisicion)

    segunda = fila_orden(entorno, requisicion)
    intentar(
        entorno.conexion,
        "orden_compra",
        segunda,
        ("23505", "uq_orden_compra_requisicion_id_vigente", None),
    )

    entorno.conexion.execute(
        "UPDATE orden_compra SET cancelada_en = %s, motivo_cancelacion = %s WHERE id = %s",
        (AHORA, "Se reconvierte la requisición.", primera),
    )
    intentar(entorno.conexion, "orden_compra", segunda, None)
    vivas = entorno.conexion.execute(
        "SELECT count(*) FROM orden_compra WHERE requisicion_id = %s AND cancelada_en IS NULL",
        (requisicion,),
    ).fetchone()
    assert vivas == (1,)


# --------------------------------------------------------------------------- TC-22


@pytest.mark.parametrize(
    ("motivo", "rechazo"),
    [
        pytest.param(None, ("23502", None, "motivo"), id="motivo_nulo"),
        pytest.param("", check("ck_reprogramacion_entrega_motivo_no_vacio"), id="motivo_vacio"),
        pytest.param(
            "   ", check("ck_reprogramacion_entrega_motivo_no_vacio"), id="motivo_solo_espacios"
        ),
    ],
)
def test_tkt019_ca10_la_reprogramacion_exige_motivo(
    motivo: str | None, rechazo: Rechazo, entorno: Entorno
) -> None:
    """TC-22 · CA-10 · RN-06 — toda reprogramación guarda su motivo.

    `motivo` nulo: `23502` sobre la columna `motivo`. Vacío o solo espacios: `23514` sobre
    `ck_reprogramacion_entrega_motivo_no_vacio`. Ninguno deja fila.
    """
    exigir_compras(entorno)
    valores = fila_reprogramacion(entorno, renglon_de_orden_valido(entorno), motivo=motivo)
    intentar(entorno.conexion, "reprogramacion_entrega", valores, rechazo)


def test_tkt019_ca10_la_reprogramacion_completa_entra_y_se_lee_igual(entorno: Entorno) -> None:
    """TC-22 (control positivo) · CA-10 — fecha anterior, fecha nueva, saldo, motivo, actor y momento se guardan tal cual."""
    exigir_compras(entorno)
    valores = fila_reprogramacion(entorno, renglon_de_orden_valido(entorno))
    intentar(entorno.conexion, "reprogramacion_entrega", valores, None)

    fila = entorno.conexion.execute(
        "SELECT orden_compra_renglon_id, fecha_anterior, fecha_nueva, saldo_pendiente, motivo, "
        "registrado_por_id, ocurrido_en FROM reprogramacion_entrega WHERE id = %s",
        (valores["id"],),
    ).fetchone()
    assert fila == (
        valores["orden_compra_renglon_id"],
        date(2026, 11, 20),
        date(2026, 11, 27),
        Decimal("5.0000"),
        "El proveedor aplazó la entrega.",
        entorno.usuario,
        AHORA,
    )
