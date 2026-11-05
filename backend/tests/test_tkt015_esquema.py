"""Esquema TKT-015a, fila A4: migración 0009 y regresión de invariantes."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import psycopg
import pytest

from cimenta.presupuesto.dominio.importacion import EstadoImportacion, TipoErrorImportacion

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto, Migrar

Conexion = psycopg.Connection[tuple[Any, ...]]

REVISION_ANTERIOR = "0008"
REVISION_NUEVA = "0009"
RESTRICCION_PREPARACION = "ck_importacion_preparacion_tras_analisis"


def _definicion_restriccion(conexion: Conexion, nombre: str) -> str | None:
    fila = conexion.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
        (nombre,),
    ).fetchone()
    return None if fila is None else str(fila[0])


def _tiene_columna(conexion: Conexion, tabla: str, columna: str) -> bool:
    fila = conexion.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (tabla, columna),
    ).fetchone()
    return fila is not None


def _literales_check(definicion: str) -> frozenset[str]:
    """Literales entre comillas simples de un CHECK (IN o = ANY (ARRAY[…]))."""
    return frozenset(re.findall(r"'([^']+)'", definicion))


def test_tkt015_migracion_0009_reversible(
    base_vacia: str, migrar: Migrar, conectar: Conectar
) -> None:
    """TC-17 · CA-11 — 0009 reversible; el CHECK impide preparación en ANALIZANDO."""
    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        assert _tiene_columna(administrador, "importacion", "preparacion")
        assert _definicion_restriccion(administrador, RESTRICCION_PREPARACION) is not None

    migrar(base_vacia, REVISION_ANTERIOR, "downgrade")
    with conectar("migracion", base_vacia) as administrador:
        assert not _tiene_columna(administrador, "importacion", "preparacion")
        assert _definicion_restriccion(administrador, RESTRICCION_PREPARACION) is None
        version = administrador.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version == (REVISION_ANTERIOR,)

    migrar(base_vacia, REVISION_NUEVA)
    with conectar("migracion", base_vacia) as administrador:
        assert _tiene_columna(administrador, "importacion", "preparacion")


def test_tkt015_preparacion_no_nula_en_analizando_rechazada(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-17 · CA-11 — preparación con estado ANALIZANDO viola ck_importacion_preparacion_tras_analisis."""
    identificador = datos_presupuesto.importacion(estado="ANALIZANDO")
    documento = json.dumps({"formato": 1})

    with conectar("aplicacion", base_de_prueba) as aplicacion:
        with pytest.raises(psycopg.errors.CheckViolation) as rechazo:
            aplicacion.execute(
                "UPDATE importacion SET preparacion = %s::jsonb WHERE id = %s",
                (documento, identificador),
            )
        assert rechazo.value.sqlstate == "23514"
        assert rechazo.value.diag.constraint_name == RESTRICCION_PREPARACION
        guardado = aplicacion.execute(
            "SELECT preparacion FROM importacion WHERE id = %s", (identificador,)
        ).fetchone()
    assert guardado == (None,)


def test_tkt015_car3_tipos_e_invariante_13_intactos(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-18 · CA-R3 — CHECK de estado y tipo alineados al dominio; UNIQUE de concepto intacto."""
    with conectar("migracion", base_de_prueba) as migracion:
        def_estado = _definicion_restriccion(migracion, "ck_importacion_estado")
        def_tipo = _definicion_restriccion(migracion, "ck_importacion_error_tipo")
        def_concepto = _definicion_restriccion(migracion, "uq_concepto_obra_id_codigo")

    assert def_estado is not None and def_tipo is not None and def_concepto is not None
    assert {e.value for e in EstadoImportacion} == _literales_check(def_estado)
    assert {t.value for t in TipoErrorImportacion} == _literales_check(def_tipo)
    assert def_concepto == "UNIQUE (obra_id, codigo)"
