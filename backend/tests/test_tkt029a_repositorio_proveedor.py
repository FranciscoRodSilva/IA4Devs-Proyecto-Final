"""Repositorio de proveedores (TKT-029a, fila A3): TC-08 a TC-11.

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` (la `0013` incluida) y
conexión con el rol de aplicación (`sesion_bd`). Prueba
`cimenta/proveedores/infraestructura/repositorio_proveedor.py`: `insertar_proveedor`,
`leer_proveedor`, `leer_proveedor_por_rfc`, `listar_proveedores` y `actualizar_proveedor`.

Rojo de la fila A3: el módulo no existe todavía. Cada prueba importa el módulo dentro de su cuerpo
(o de la ayuda que lo usa), así que la recolección no se cae y cada caso falla con
`ModuleNotFoundError` de `cimenta.proveedores.infraestructura.repositorio_proveedor`, la razón
esperada. Un error de fixture o de entorno no cuenta como rojo.

Las comprobaciones de estado y de cifras leen la tabla con SQL directo, no con el repositorio que
prueban: así una lectura defectuosa no puede tapar una escritura defectuosa.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tipos_base import Dinero

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import SembrarUsuario

    from cimenta.proveedores.infraestructura.repositorio_proveedor import PaginaProveedores

CORREO_DEL_CREADOR = "compras@cimenta.test"
CONTRASENA_DEL_CREADOR = "Clave-Correcta-1"
CREADO_EN = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


@pytest.fixture
def creador(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Usuario de COMPRAS: `creado_por_id` tiene clave foránea a `usuario` (nota de ejecución del diseño)."""
    return sembrar_usuario(CORREO_DEL_CREADOR, CONTRASENA_DEL_CREADOR, roles=("COMPRAS",))


def _alta(
    sesion: Session,
    creador_id: uuid.UUID,
    *,
    nombre: str,
    rfc: str,
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
) -> uuid.UUID:
    """Inserta un proveedor con `insertar_proveedor` y confirma. Devuelve su id."""
    from cimenta.proveedores.infraestructura.repositorio_proveedor import insertar_proveedor

    proveedor_id = uuid.uuid4()
    with sesion.begin():
        insertar_proveedor(
            sesion,
            proveedor_id=proveedor_id,
            nombre=nombre,
            rfc=rfc,
            tope_consignacion=None if tope is None else Dinero(tope),
            dia_corte=dia_corte,
            dia_pago=dia_pago,
            creado_en=CREADO_EN,
            creado_por_id=creador_id,
        )
    return proveedor_id


def _listar(sesion: Session, **criterios: Any) -> PaginaProveedores:
    """Lista con `listar_proveedores` dentro de una transacción de lectura."""
    from cimenta.proveedores.infraestructura.repositorio_proveedor import listar_proveedores

    with sesion.begin():
        return listar_proveedores(sesion, **criterios)


def _ids(pagina: PaginaProveedores) -> list[uuid.UUID]:
    """Los identificadores de las filas de una página, en el orden que devuelve el repositorio."""
    return [fila.id for fila in pagina.filas]


def _fila_en_la_tabla(sesion: Session, proveedor_id: uuid.UUID) -> dict[str, Any]:
    """Lo que hay en la tabla `proveedor` para ese id, leído con SQL directo y no con el repositorio."""
    with sesion.begin():
        fila = (
            sesion.execute(
                text(
                    "SELECT nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, creado_en "
                    "FROM proveedor WHERE id = :id"
                ),
                {"id": proveedor_id},
            )
            .mappings()
            .one()
        )
    return dict(fila)


def test_tkt029a_repositorio_inserta_y_lee_el_proveedor(
    sesion_bd: Session, creador: uuid.UUID
) -> None:
    """TC-08 · HDU-004 esc. 2 · CA-1 — feliz: el proveedor se guarda con o sin tope y se lee por id y por RFC."""
    from cimenta.proveedores.infraestructura.repositorio_proveedor import (
        leer_proveedor,
        leer_proveedor_por_rfc,
    )

    sin_tope = _alta(sesion_bd, creador, nombre="CoPanel", rfc="COP010101AB1")
    con_tope = _alta(
        sesion_bd,
        creador,
        nombre="Tablaroca Sur",
        rfc="TSU010101AB2",
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )

    with sesion_bd.begin():
        con = leer_proveedor(sesion_bd, con_tope)
        assert con is not None
        assert con.id == con_tope
        assert con.nombre == "Tablaroca Sur"
        assert con.rfc == "TSU010101AB2"
        assert con.estado == "ACTIVO"
        assert con.tope_consignacion is not None
        assert con.tope_consignacion.serializar() == "300000.0000"
        # Días distintos de los de por omisión: un intercambio entre corte y pago no pasa.
        assert con.dia_corte == 2
        assert con.dia_pago == 5
        assert con.creado_en == CREADO_EN

        sin = leer_proveedor(sesion_bd, sin_tope)
        assert sin is not None
        assert sin.nombre == "CoPanel"
        assert sin.tope_consignacion is None
        assert sin.dia_corte == 4
        assert sin.dia_pago == 6
        assert sin.estado == "ACTIVO"

        por_rfc = leer_proveedor_por_rfc(sesion_bd, "TSU010101AB2")
        assert por_rfc is not None
        assert por_rfc.id == con_tope
        assert por_rfc.tope_consignacion is not None
        assert por_rfc.tope_consignacion.serializar() == "300000.0000"

        creado_por = sesion_bd.execute(
            text("SELECT creado_por_id FROM proveedor WHERE id = :id"), {"id": con_tope}
        ).scalar_one()
        assert creado_por == creador


def test_tkt029a_repositorio_inexistente_devuelve_none(
    sesion_bd: Session, creador: uuid.UUID
) -> None:
    """TC-09 · CA-7 — rechazo: un id o un RFC que no existen dan `None`, no una fila ni una excepción."""
    from cimenta.proveedores.infraestructura.repositorio_proveedor import (
        leer_proveedor,
        leer_proveedor_por_rfc,
    )

    existente = _alta(sesion_bd, creador, nombre="CoPanel", rfc="COP010101AB1")

    with sesion_bd.begin():
        assert leer_proveedor(sesion_bd, uuid.uuid4()) is None
        assert leer_proveedor_por_rfc(sesion_bd, "ZZZ990101ZZ9") is None
        # Control: el RFC del proveedor que sí existe sí responde, así que el `None` anterior es real.
        encontrado = leer_proveedor_por_rfc(sesion_bd, "COP010101AB1")
        assert encontrado is not None
        assert encontrado.id == existente


def test_tkt029a_repositorio_lista_filtra_busca_ordena_y_pagina(
    sesion_bd: Session, creador: uuid.UUID
) -> None:
    """TC-10 · HDU-004 esc. 2 · CA-6 — feliz y rechazo: filtro por estado, búsqueda sin distinguir
    mayúsculas y con `%` y `_` literales, orden por nombre y luego id (D-8), y una página inalcanzable
    que da lista vacía con el total real."""
    gemelo_a = _alta(sesion_bd, creador, nombre="Acero Norte", rfc="ANO010101AB1")
    gemelo_b = _alta(sesion_bd, creador, nombre="Acero Norte", rfc="ANO010101AB2")
    cien = _alta(sesion_bd, creador, nombre="Pinturas 100%", rfc="PIC010101AB1")
    mil = _alta(sesion_bd, creador, nombre="Pinturas 1000", rfc="PIM010101AB1")
    axs = _alta(sesion_bd, creador, nombre="AceroXSur", rfc="AXS010101AB1")
    hyu = _alta(sesion_bd, creador, nombre="Herrajes Yuta", rfc="HYU980101AB3")

    # Dos proveedores pasan a DESACTIVADO con SQL directo: el rol de aplicación puede actualizar.
    with sesion_bd.begin():
        sesion_bd.execute(
            text("UPDATE proveedor SET estado = 'DESACTIVADO' WHERE id = ANY(:ids)"),
            {"ids": [axs, hyu]},
        )

    # Orden esperado de todo el catálogo: los dos «Acero Norte» por id (D-8), después «AceroXSur»,
    # «Herrajes Yuta», «Pinturas 100%» y «Pinturas 1000».
    gemelos = sorted([gemelo_a, gemelo_b])
    orden_completo = [*gemelos, axs, hyu, cien, mil]

    activos = _listar(sesion_bd, estados=frozenset({"ACTIVO"}), q=None, desplazamiento=0, limite=50)
    assert activos.total == 4
    assert _ids(activos) == [*gemelos, cien, mil]

    desactivados = _listar(
        sesion_bd, estados=frozenset({"DESACTIVADO"}), q=None, desplazamiento=0, limite=50
    )
    assert desactivados.total == 2
    assert _ids(desactivados) == [axs, hyu]

    ambos = _listar(
        sesion_bd, estados=frozenset({"ACTIVO", "DESACTIVADO"}), q=None, desplazamiento=0, limite=50
    )
    assert ambos.total == 6
    assert _ids(ambos) == orden_completo

    # Búsqueda en minúsculas contra el nombre: «acero» encuentra los dos «Acero Norte» y «AceroXSur».
    por_nombre = _listar(
        sesion_bd,
        estados=frozenset({"ACTIVO", "DESACTIVADO"}),
        q="acero",
        desplazamiento=0,
        limite=50,
    )
    assert por_nombre.total == 3
    assert _ids(por_nombre) == [*gemelos, axs]

    # Búsqueda en minúsculas contra el RFC: «hyu» solo encuentra «Herrajes Yuta» por su RFC.
    por_rfc = _listar(
        sesion_bd,
        estados=frozenset({"ACTIVO", "DESACTIVADO"}),
        q="hyu",
        desplazamiento=0,
        limite=50,
    )
    assert por_rfc.total == 1
    assert _ids(por_rfc) == [hyu]

    # «%» es texto literal: encuentra «Pinturas 100%» y no «Pinturas 1000».
    por_porcentaje = _listar(
        sesion_bd,
        estados=frozenset({"ACTIVO", "DESACTIVADO"}),
        q="100%",
        desplazamiento=0,
        limite=50,
    )
    assert por_porcentaje.total == 1
    assert _ids(por_porcentaje) == [cien]

    # «_» es texto literal: «Acero_Sur» no encuentra «AceroXSur», que solo difiere en ese carácter.
    por_guion = _listar(
        sesion_bd,
        estados=frozenset({"ACTIVO", "DESACTIVADO"}),
        q="Acero_Sur",
        desplazamiento=0,
        limite=50,
    )
    assert por_guion.total == 0
    assert _ids(por_guion) == []

    # Ventana: la segunda y la tercera del orden completo, con el total entero. Cruza el desempate por id.
    ventana = _listar(
        sesion_bd, estados=frozenset({"ACTIVO", "DESACTIVADO"}), q=None, desplazamiento=1, limite=2
    )
    assert ventana.total == 6
    assert _ids(ventana) == orden_completo[1:3]

    # Página inalcanzable: desplazamiento igual al total, o muy superior, da lista vacía y el total real.
    for desplazamiento in (6, 50):
        vacia = _listar(
            sesion_bd,
            estados=frozenset({"ACTIVO", "DESACTIVADO"}),
            q=None,
            desplazamiento=desplazamiento,
            limite=50,
        )
        assert vacia.filas == []
        assert vacia.total == 6

    # Lo mismo con un filtro de estado: el desplazamiento se cuenta sobre los activos.
    activos_vacia = _listar(
        sesion_bd, estados=frozenset({"ACTIVO"}), q=None, desplazamiento=4, limite=50
    )
    assert activos_vacia.filas == []
    assert activos_vacia.total == 4


def test_tkt029a_repositorio_actualiza_solo_las_columnas_dadas(
    sesion_bd: Session, creador: uuid.UUID
) -> None:
    """TC-11 · CA-8 — feliz y rechazo: `UPDATE` solo de las columnas dadas, tope a `NULL` y `Dinero`
    como valor; una clave fuera de la lista admitida lanza `ValueError` y no toca la fila."""
    from cimenta.proveedores.infraestructura.repositorio_proveedor import actualizar_proveedor

    cambiado = _alta(
        sesion_bd,
        creador,
        nombre="CoPanel",
        rfc="COP010101AB1",
        tope="300000.0000",
        dia_corte=4,
        dia_pago=6,
    )
    vecino = _alta(
        sesion_bd,
        creador,
        nombre="Tablaroca Sur",
        rfc="TSU010101AB2",
        tope="100000.0000",
        dia_corte=3,
        dia_pago=5,
    )
    antes = _fila_en_la_tabla(sesion_bd, cambiado)
    antes_vecino = _fila_en_la_tabla(sesion_bd, vecino)

    # Solo el día de corte: el resto de la fila y el vecino no cambian.
    with sesion_bd.begin():
        actualizar_proveedor(sesion_bd, cambiado, {"dia_corte": 2})
    tras_corte = _fila_en_la_tabla(sesion_bd, cambiado)
    assert tras_corte == {**antes, "dia_corte": 2}
    assert _fila_en_la_tabla(sesion_bd, vecino) == antes_vecino

    # Tope a `None`: la columna queda en NULL y lo demás sigue igual.
    with sesion_bd.begin():
        actualizar_proveedor(sesion_bd, cambiado, {"tope_consignacion": None})
    tras_tope_nulo = _fila_en_la_tabla(sesion_bd, cambiado)
    assert tras_tope_nulo == {**tras_corte, "tope_consignacion": None}

    # Nombre y tope con `Dinero`: el repositorio lo escribe en la escala de la columna.
    with sesion_bd.begin():
        actualizar_proveedor(
            sesion_bd,
            cambiado,
            {"nombre": "CoPanel Norte", "tope_consignacion": Dinero("250000.0000")},
        )
    tras_nombre_y_tope = _fila_en_la_tabla(sesion_bd, cambiado)
    assert tras_nombre_y_tope == {
        **tras_tope_nulo,
        "nombre": "CoPanel Norte",
        "tope_consignacion": Decimal("250000.0000"),
    }
    assert _fila_en_la_tabla(sesion_bd, vecino) == antes_vecino

    # Rechazo: el RFC no es una clave admitida. Es un defecto del llamador y la fila no cambia.
    with pytest.raises(ValueError), sesion_bd.begin():
        actualizar_proveedor(sesion_bd, cambiado, {"rfc": "OTR010101AB9"})
    assert _fila_en_la_tabla(sesion_bd, cambiado) == tras_nombre_y_tope
