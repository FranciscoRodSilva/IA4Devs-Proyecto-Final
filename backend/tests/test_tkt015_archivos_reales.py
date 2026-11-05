"""Análisis persistido contra libros reales (TKT-015a, fila A7): TC-40 a TC-42 e INV-1.

Requieren `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`; si faltan, `pytest.skip` (PA-T3).
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.dominio.importacion import TipoErrorImportacion
from herramientas.soporte_tkt013 import HOJA_UNION, leer_catalogo_bytes

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto

CODIGOS_ENITI_EN_PREPARACION = ("620014", "620045", "620050")


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)


def _fila_importacion(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> dict[str, Any]:
    with conectar("aplicacion", base) as conn:
        fila = conn.execute(
            "SELECT estado, filas_leidas, filas_validas, filas_rechazadas, preparacion "
            "FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert fila is not None
    estado, leidas, validas, rechazadas, preparacion = fila
    return {
        "estado": estado,
        "filas_leidas": leidas,
        "filas_validas": validas,
        "filas_rechazadas": rechazadas,
        "preparacion": preparacion,
    }


def _errores_db(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with conectar("aplicacion", base) as conn:
        return conn.execute(
            "SELECT hoja, fila, columna, tipo, mensaje, valor_original "
            "FROM importacion_error WHERE importacion_id = %s",
            (importacion_id,),
        ).fetchall()


def _flujo_persistido(
    fabrica: sessionmaker[Session],
    datos_presupuesto: DatosPresupuesto,
    conectar: Conectar,
    base: str,
    contenido: bytes,
) -> tuple[uuid.UUID, dict[str, Any], list[tuple[Any, ...]]]:
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    trabajo = iniciar_analisis(fabrica, importacion_id)
    resultado = analizar_contenido(contenido, trabajo.insumos_existentes)
    assert registrar_resultado(fabrica, importacion_id, resultado) is True
    fila = _fila_importacion(conectar, base, importacion_id)
    errores = _errores_db(conectar, base, importacion_id)
    return importacion_id, fila, errores


def test_hdu001_esc06_union_square_fila_a_fila(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    archivo_union: bytes,
) -> None:
    """TC-40 · CA-3 — Union Square persistido: REF_ROTA masivos, sin conceptos en preparación."""
    _, fila, errores = _flujo_persistido(
        fabrica_sesiones, datos_presupuesto, conectar, base_de_prueba, archivo_union
    )
    assert fila["estado"] == "CON_ERRORES"
    assert fila["filas_leidas"] == 4281
    assert fila["filas_validas"] == 0
    assert fila["filas_rechazadas"] == 4281
    assert fila["preparacion"] is not None
    assert len(fila["preparacion"]["conceptos"]) == 0

    assert len(errores) == 8639
    por_tipo = Counter(e[3] for e in errores)
    assert por_tipo["REF_ROTA"] == 8608
    assert por_tipo[TipoErrorImportacion.SIN_APU.value] == 31
    assert por_tipo.get(TipoErrorImportacion.SIN_CONCEPTOS.value, 0) == 0

    refs_formula = [
        e for e in errores if e[3] == "REF_ROTA" and "(causa: ERROR_DE_FORMULA)" in e[4]
    ]
    assert len(refs_formula) == 8562
    for hoja, fila_e, columna, _, _, valor in refs_formula:
        assert hoja == HOJA_UNION
        assert fila_e is not None
        assert columna in ("E", "F")
        assert valor == "#REF!"

    refs_sin_partida = [
        e for e in errores if e[3] == "REF_ROTA" and "(causa: CONCEPTO_SIN_PARTIDA)" in e[4]
    ]
    assert len(refs_sin_partida) == 5
    assert {e[1] for e in refs_sin_partida} == {12, 13, 14, 15, 16}


def test_hdu001_esc09_eniti_sin_duplicados(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    archivo_eniti: bytes,
) -> None:
    """TC-41 · CA-8 — en ENITI no hay DUPLICADO de catálogo; seis por CODIGO_EN_VARIAS_HOJAS."""
    _, _, errores = _flujo_persistido(
        fabrica_sesiones, datos_presupuesto, conectar, base_de_prueba, archivo_eniti
    )
    duplicados = [e for e in errores if e[3] == "DUPLICADO"]
    assert len(duplicados) == 6
    assert all("(causa: CODIGO_EN_VARIAS_HOJAS)" in e[4] for e in duplicados)


def test_tkt015_eniti_48_errores(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    archivo_eniti: bytes,
) -> None:
    """TC-42 · CA-10 — ENITI: 48 errores desglosados y tres códigos en la preparación."""
    _, fila, errores = _flujo_persistido(
        fabrica_sesiones, datos_presupuesto, conectar, base_de_prueba, archivo_eniti
    )
    assert fila["estado"] == "CON_ERRORES"
    assert len(errores) == 48

    por_tipo = Counter(e[3] for e in errores)
    assert por_tipo["UNIDAD_DESCONOCIDA"] == 20
    assert por_tipo["SIN_APU"] == 16
    assert por_tipo["DUPLICADO"] == 6

    refs_formula = [
        e for e in errores if e[3] == "REF_ROTA" and "(causa: ERROR_DE_FORMULA)" in e[4]
    ]
    assert len(refs_formula) == 5
    refs_sin_codigo = [
        e for e in errores if e[3] == "REF_ROTA" and "(causa: ANALISIS_SIN_CODIGO)" in e[4]
    ]
    assert len(refs_sin_codigo) == 1

    prep = fila["preparacion"]
    assert prep is not None
    assert len(prep["analisis"]) == 1
    codigos = {c["codigo"] for c in prep["conceptos"]}
    for codigo in CODIGOS_ENITI_EN_PREPARACION:
        assert codigo in codigos


def test_tkt015_inv1_conteos_de_catalogo_sin_regression(
    archivo_eniti: bytes, archivo_union: bytes
) -> None:
    """TC-INV-1 · CA-R1 — los reales siguen leyendo 5 028 y 4 281 conceptos (TKT-013)."""
    assert len(leer_catalogo_bytes(archivo_eniti).conceptos) == 5028
    assert len(leer_catalogo_bytes(archivo_union).conceptos) == 4281


def test_tkt015_e4_union_cierre_en_tiempo(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    archivo_union: bytes,
) -> None:
    """E-4 · Union — registrar_resultado completo por debajo de 10 s (umbral de escalada: 5 s/sentencia)."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    resultado = analizar_contenido(archivo_union, trabajo.insumos_existentes)

    inicio = time.perf_counter()
    assert registrar_resultado(fabrica_sesiones, importacion_id, resultado) is True
    duracion = time.perf_counter() - inicio
    assert duracion < 10.0, f"registrar_resultado Union tardó {duracion:.2f}s"

    with conectar("migracion", base_de_prueba) as mig:
        tam = mig.execute(
            "SELECT pg_column_size(preparacion), length(preparacion::text) "
            "FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert tam is not None
    pg_size, text_len = tam
    assert pg_size is not None and pg_size < 20 * 1024 * 1024
    assert text_len is not None
