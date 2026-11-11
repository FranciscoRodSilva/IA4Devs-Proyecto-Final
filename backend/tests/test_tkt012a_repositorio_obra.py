"""Repositorio de la obra (TKT-012a, fila A2): TC-05 a TC-08.

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` y conexión con el rol de
aplicación (`sesion_bd`, `conectar`). Prueba `cimenta/presupuesto/infraestructura/repositorio_obra.py`
(`insertar_obra`, `leer_obra_completa`, `leer_obra_por_codigo`, `listar_obras` y `empresas_activas`)
y las columnas que `tablas.obra` debe mapear tras la ampliación de A2.

Rojo de la fila A2: el módulo no existe todavía. Cada prueba importa el módulo dentro de su cuerpo,
así que la recolección no se cae y cada caso falla solo con `ModuleNotFoundError` de
`cimenta.presupuesto.infraestructura.repositorio_obra`, la razón esperada. Un error de fixture o de
entorno no cuenta como rojo: los fixtures de esta suite se construyen contra la base migrada.

Empresa única (nota de ejecución del diseño): la migración 0008 siembra «Constructora Celsius», la
única empresa activa. Las obras de estas pruebas la usan (`empresa_de_la_migracion`);
`DatosPresupuesto.obra()` sin `empresa_id` crearía una segunda empresa activa.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tipos_base import Porcentaje

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto

TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
CREADO_EN = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


@pytest.fixture
def empresa_de_la_migracion(base_de_prueba: str, conectar: Conectar) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008): la que usan las obras de estas pruebas."""
    filas = (
        conectar("aplicacion", base_de_prueba)
        .execute("SELECT id FROM empresa WHERE activa")
        .fetchall()
    )
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return filas[0][0]


def _codigos(pagina: Any) -> list[str]:
    """Los códigos de las filas de una página, en el orden que devuelve el repositorio."""
    return [fila.codigo for fila in pagina.filas]


def test_tkt012a_repositorio_inserta_y_lee_la_obra_completa(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-05 · HDU-001 esc. 2 · CA-1 — feliz: la obra se guarda con sus parámetros y se lee completa."""
    from cimenta.presupuesto.infraestructura.repositorio_obra import (
        insertar_obra,
        leer_obra_completa,
    )

    creador = datos_presupuesto.usuario()
    obra_id = uuid.uuid4()
    with sesion_bd.begin():
        insertar_obra(
            sesion_bd,
            obra_id=obra_id,
            empresa_id=empresa_de_la_migracion,
            codigo="AP-058-25",
            nombre="Union Square F2",
            domicilio="Calle de prueba 1",
            tipo_contrato=TIPO_CONTRATO,
            retencion_destajo_pct=Porcentaje("0.150000"),
            fondo_garantia_pct=Porcentaje("0.050000"),
            iva_acreditable=False,
            umbral_alerta_pct=Porcentaje("0.100000"),
            creado_en=CREADO_EN,
            creado_por_id=creador,
        )

    fila = leer_obra_completa(sesion_bd, obra_id)
    assert fila is not None
    assert fila.id == obra_id
    assert fila.codigo == "AP-058-25"
    assert fila.nombre == "Union Square F2"
    assert fila.domicilio == "Calle de prueba 1"
    assert fila.tipo_contrato == TIPO_CONTRATO
    # Tres porcentajes distintos: un intercambio entre retención, fondo y umbral no pasa.
    assert fila.retencion_destajo_pct.serializar() == "0.150000"
    assert fila.fondo_garantia_pct.serializar() == "0.050000"
    assert fila.umbral_alerta_pct is not None
    assert fila.umbral_alerta_pct.serializar() == "0.100000"
    assert fila.iva_acreditable is False
    assert fila.estado == "PLANEACION"
    assert fila.linea_base_vigente_id is None
    assert fila.creado_en == CREADO_EN
    assert fila.actualizado_en is None

    # `FilaObraCompleta` no expone la empresa ni quién creó la obra: se comprueban en la fila guardada.
    empresa, creado_por = sesion_bd.execute(
        text("SELECT empresa_id, creado_por_id FROM obra WHERE id = :id"), {"id": obra_id}
    ).one()
    assert empresa == empresa_de_la_migracion
    assert creado_por == creador


def test_tkt012a_repositorio_vigente_es_la_congelada(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-06 · CA-8 — feliz: con una línea base BORRADOR y otra CONGELADA, la vigente es la congelada."""
    from cimenta.presupuesto.infraestructura.repositorio_obra import (
        leer_obra_completa,
        leer_obra_por_codigo,
    )

    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    datos_presupuesto.linea_base(obra_id=obra_id, estado="BORRADOR", version=1)
    congelada = datos_presupuesto.linea_base(obra_id=obra_id, estado="CONGELADA", version=2)

    por_id = leer_obra_completa(sesion_bd, obra_id)
    por_codigo = leer_obra_por_codigo(sesion_bd, "AP-058-25")
    assert por_id is not None
    assert por_codigo is not None
    assert por_id.linea_base_vigente_id == congelada
    assert por_codigo.linea_base_vigente_id == congelada


def test_tkt012a_repositorio_lista_ordenada_filtrada_y_pagina_vacia(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-07 · HDU-001 esc. 2 · CA-7 — feliz y borde: orden por código, filtro por uno y dos estados,
    y una página que no alcanza filas da lista vacía con el total real."""
    from cimenta.presupuesto.infraestructura.repositorio_obra import listar_obras

    # Se insertan fuera de orden de código: el orden lo pone la consulta, no la inserción.
    datos_presupuesto.obra(codigo="AP-003", empresa_id=empresa_de_la_migracion, estado="ACTIVA")
    datos_presupuesto.obra(codigo="AP-001", empresa_id=empresa_de_la_migracion, estado="PLANEACION")
    datos_presupuesto.obra(codigo="AP-002", empresa_id=empresa_de_la_migracion, estado="ACTIVA")

    todas = listar_obras(sesion_bd, estados=None, desplazamiento=0, limite=50)
    assert todas.total == 3
    assert _codigos(todas) == ["AP-001", "AP-002", "AP-003"]

    activas = listar_obras(sesion_bd, estados=frozenset({"ACTIVA"}), desplazamiento=0, limite=50)
    assert activas.total == 2
    assert _codigos(activas) == ["AP-002", "AP-003"]

    dos_estados = listar_obras(
        sesion_bd, estados=frozenset({"ACTIVA", "PLANEACION"}), desplazamiento=0, limite=50
    )
    assert dos_estados.total == 3
    assert _codigos(dos_estados) == ["AP-001", "AP-002", "AP-003"]

    # Ventana: desplazamiento 1 y límite 1 da la segunda obra del orden, con el total completo.
    ventana = listar_obras(sesion_bd, estados=None, desplazamiento=1, limite=1)
    assert ventana.total == 3
    assert _codigos(ventana) == ["AP-002"]

    # Página inalcanzable: desplazamiento igual o mayor que el total, sin filas y con el total real.
    for desplazamiento in (3, 10):
        vacia = listar_obras(sesion_bd, estados=None, desplazamiento=desplazamiento, limite=50)
        assert vacia.filas == []
        assert vacia.total == 3

    # Filtro sin coincidencias: total cero y página vacía, sin error.
    ninguna = listar_obras(sesion_bd, estados=frozenset({"CERRADA"}), desplazamiento=0, limite=50)
    assert ninguna.filas == []
    assert ninguna.total == 0


def test_tkt012a_repositorio_empresas_activas_devuelve_hasta_dos(
    sesion_bd: Session,
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-08 · CA-1 (A9) — feliz: `empresas_activas` devuelve como mucho dos, por orden de id."""
    from cimenta.presupuesto.infraestructura.repositorio_obra import empresas_activas

    assert empresas_activas(sesion_bd) == [empresa_de_la_migracion]

    # Una empresa inactiva no cuenta.
    datos_presupuesto.empresa(activa=False)
    assert empresas_activas(sesion_bd) == [empresa_de_la_migracion]

    segunda = datos_presupuesto.empresa(activa=True)
    assert empresas_activas(sesion_bd) == sorted([empresa_de_la_migracion, segunda])

    # Con tres activas devuelve solo dos: las primeras por id, no dos cualesquiera.
    tercera = datos_presupuesto.empresa(activa=True)
    dos = empresas_activas(sesion_bd)
    assert len(dos) == 2
    assert dos == sorted([empresa_de_la_migracion, segunda, tercera])[:2]

    # Sin ninguna activa, lista vacía.
    conectar("aplicacion", base_de_prueba).execute("UPDATE empresa SET activa = false")
    assert empresas_activas(sesion_bd) == []
