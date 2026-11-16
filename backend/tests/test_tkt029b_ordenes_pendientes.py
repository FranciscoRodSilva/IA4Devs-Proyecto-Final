"""TKT-029b · Órdenes pendientes de un proveedor: TC-14 a TC-19 (fila F3).

Prueba `cimenta.compras.interfaz.ordenes_pendientes_de_proveedor` y `OrdenPendiente` (CA-12) contra
PostgreSQL real, con el esquema de `alembic upgrade head` y el rol de aplicación. Las órdenes se siembran
con `herramientas.soporte_tkt029b_ordenes.sembrar_orden_compra`, con `cantidad_recibida` explícita. Los
folios `OC-T029B-NNNN` entran al revés del orden esperado, para que un orden por inserción o por `id` falle.

Qué cubre cada prueba:

- `TC-14` (HDU-004 esc. 12, CA-12 esc. 1): solo la `PARCIAL` y la `ABIERTA` del proveedor, por folio.
- `TC-15` (HDU-004 esc. 12, CA-5, CA-12): la cancelada, la cerrada con excedente y la de otro proveedor no
  son pendientes.
- `TC-16` (CA-5, D-2): una orden viva sin renglones no es pendiente.
- `TC-17` (CA-12 esc. 1): la lectura corre en `SET TRANSACTION READ ONLY` y no asigna ningún `xid`, así que
  no escribe. La transacción de control rechaza un `UPDATE`, para que la prueba no sea vacía.
- `TC-18` (CA-12 esc. 1): la lectura usa la sesión que recibe y ve lo que esa transacción no ha confirmado.
- `TC-19` (CA-12 esc. 3, CA-R2): `compras` publica solo sus dos nombres; `proveedores` no importa `compras`
  por ningún otro camino (recorrido AST); `lint-imports` en verde.

Mutantes de esta fila: `M-7` (sin `cancelada_en IS NULL`), `M-8` (sin el filtro por proveedor), `M-11`
(orden por `id` o por inserción) y `M-16` (la función abre su propia sesión), de la tabla de mutación del
diseño; y `M-17` (agrupación por orden sustituida por evaluación renglón a renglón), añadido en la revisión
y muerto por los dos tests de órdenes de dos renglones.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.compras import interfaz
from cimenta.compras.dominio.orden_compra import EstadoOrden
from cimenta.compras.interfaz import OrdenPendiente, ordenes_pendientes_de_proveedor
from herramientas.soporte_tkt029b_ordenes import sembrar_orden_compra

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]
RAIZ_PROVEEDORES = BACKEND / "cimenta" / "proveedores"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
COMPRAS = "cimenta.compras"
INTERFAZ_DE_COMPRAS = "cimenta.compras.interfaz"
NOMBRES_PUBLICADOS = ["OrdenPendiente", "ordenes_pendientes_de_proveedor"]
SQLSTATE_SOLO_LECTURA = "25006"


@dataclass(frozen=True)
class Escenario:
    """Las filas padre de una orden (usuario, obra, tipo de partida, insumo) y los dos caminos de acceso.

    `conexion` es la del rol de aplicación en autocommit, para sembrar. `motor` es el mismo rol con
    SQLAlchemy, la vía por la que la función de `compras` lee.
    """

    conexion: Conexion
    motor: Engine
    usuario: uuid.UUID
    obra: uuid.UUID
    tipo_partida: uuid.UUID
    insumo: uuid.UUID


@pytest.fixture
def escenario(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    motor_aplicacion: Engine,
) -> Escenario:
    """Las filas padre, escritas con el rol de aplicación sobre una base copiada de la plantilla migrada."""
    return Escenario(
        conexion=conectar("aplicacion", base_de_prueba),
        motor=motor_aplicacion,
        usuario=datos_presupuesto.usuario(),
        obra=datos_presupuesto.obra(codigo="OB-T029B"),
        tipo_partida=datos_presupuesto.tipo_partida(),
        insumo=datos_presupuesto.insumo_nuevo(),
    )


# --------------------------------------------------------------------------- ayudas


def _sembrar(
    escenario: Escenario,
    *,
    proveedor: uuid.UUID,
    folio: str,
    renglones: list[tuple[str, str]],
    excedente: str = "0",
    cancelada: bool = False,
    conexion: Conexion | None = None,
) -> uuid.UUID:
    """Una orden del proveedor, sembrada con la conexión de siembra o con la que se pase."""
    return sembrar_orden_compra(
        conexion if conexion is not None else escenario.conexion,
        obra_id=escenario.obra,
        tipo_partida_id=escenario.tipo_partida,
        insumo_id=escenario.insumo,
        solicitante_id=escenario.usuario,
        proveedor_id=proveedor,
        folio=folio,
        renglones=renglones,
        excedente=excedente,
        cancelada=cancelada,
    )


def _ordenes_visibles(motor: Engine) -> int:
    """Cuántas órdenes ve una conexión nueva: solo las confirmadas."""
    with motor.connect() as conexion:
        return int(conexion.execute(text("SELECT count(*) FROM orden_compra")).scalar_one())


def _importados_de_compras(nodo: ast.Import | ast.ImportFrom) -> list[str]:
    """Los módulos de `cimenta.compras` que importa el nodo, salvo su interfaz, por nombre completo."""
    if isinstance(nodo, ast.Import):
        candidatos = [alias.name for alias in nodo.names]
    elif nodo.level == 0 and nodo.module is not None:
        if nodo.module in ("cimenta", COMPRAS):
            candidatos = [f"{nodo.module}.{alias.name}" for alias in nodo.names]
        else:
            candidatos = [nodo.module]
    else:
        return []
    return [
        candidato
        for candidato in candidatos
        if (candidato == COMPRAS or candidato.startswith(COMPRAS + "."))
        and candidato != INTERFAZ_DE_COMPRAS
    ]


def _importaciones_de_compras_fuera_de_la_interfaz() -> list[str]:
    """Recorre el AST de `cimenta/proveedores/` y devuelve cada import de `compras` que no es su interfaz."""
    archivos = sorted(RAIZ_PROVEEDORES.rglob("*.py"))
    assert archivos, f"No hay archivos bajo {RAIZ_PROVEEDORES}: el recorrido no vería nada"
    hallazgos: list[str] = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                for modulo in _importados_de_compras(nodo):
                    hallazgos.append(f"{archivo.name}:{nodo.lineno} importa {modulo}")
    return hallazgos


def _nodos_de_importacion(codigo: str) -> Iterator[ast.Import | ast.ImportFrom]:
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            yield nodo


# --------------------------------------------------------------------------- TC-14 a TC-19


def test_hdu004_esc12_ordenes_pendientes_devuelve_la_parcial_y_la_abierta_por_folio(
    escenario: Escenario,
) -> None:
    """HDU-004 esc. 12 · CA-12 esc. 1 — solo la PARCIAL y la ABIERTA del proveedor, en orden de folio."""
    proveedor = uuid.uuid4()
    # Los folios entran al revés del orden esperado: un orden por inserción o por `id` no pasa.
    _sembrar(
        escenario,
        proveedor=uuid.uuid4(),
        folio="OC-T029B-0005",
        renglones=[("10.0000", "0.0000")],
    )
    _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0004",
        renglones=[("10.0000", "0.0000")],
        cancelada=True,
    )
    abierta = _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0003",
        renglones=[("10.0000", "0.0000")],
    )
    _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0002",
        renglones=[("10.0000", "10.0000")],
    )
    parcial = _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0001",
        renglones=[("10.0000", "4.0000")],
    )

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == (
        OrdenPendiente(parcial, "OC-T029B-0001", EstadoOrden.PARCIAL),
        OrdenPendiente(abierta, "OC-T029B-0003", EstadoOrden.ABIERTA),
    )


def test_hdu004_esc12_ordenes_pendientes_con_muchas_ordenes_sale_por_folio_y_no_por_id(
    escenario: Escenario,
) -> None:
    """HDU-004 esc. 12 · CA-12 esc. 1 · M-11 — con ocho órdenes, el orden por `id` aleatorio no coincide con el folio.

    El caso de TC-14 solo tiene dos órdenes pendientes y un orden por `id` lo pasaría la mitad de las
    veces. Con ocho, un orden que no sea el de folio coincide por azar una vez en 40,320.
    """
    proveedor = uuid.uuid4()
    folios = [f"OC-T029B-{n:04d}" for n in range(8, 0, -1)]
    ids_por_folio = {
        folio: _sembrar(
            escenario, proveedor=proveedor, folio=folio, renglones=[("10.0000", "0.0000")]
        )
        for folio in folios
    }

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    esperado = sorted(folios)
    assert [orden.folio for orden in resultado] == esperado
    assert [orden.id for orden in resultado] == [ids_por_folio[folio] for folio in esperado]


def test_hdu004_esc12_orden_de_dos_renglones_con_uno_completo_y_otro_sin_recibir_es_una_parcial(
    escenario: Escenario,
) -> None:
    """HDU-004 esc. 12 · CA-12 esc. 2 · M-17 — dos renglones (10 de 10 y 0 de 5) son UNA orden PARCIAL.

    El estado se deriva de todos los renglones de la orden juntos. Evaluados uno a uno, el completo
    saldría CERRADO y el otro ABIERTO, y la lectura devolvería la orden como ABIERTA o dos veces.
    """
    proveedor = uuid.uuid4()
    orden = _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0001",
        renglones=[("10.0000", "10.0000"), ("5.0000", "0.0000")],
    )

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == (OrdenPendiente(orden, "OC-T029B-0001", EstadoOrden.PARCIAL),)


def test_hdu004_esc12_orden_de_dos_renglones_sin_recibir_es_una_sola_abierta(
    escenario: Escenario,
) -> None:
    """HDU-004 esc. 12 · CA-5 · M-17 — dos renglones (10 y 5, nada recibido) son UNA orden ABIERTA, no dos."""
    proveedor = uuid.uuid4()
    orden = _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0001",
        renglones=[("10.0000", "0.0000"), ("5.0000", "0.0000")],
    )

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == (OrdenPendiente(orden, "OC-T029B-0001", EstadoOrden.ABIERTA),)


@pytest.mark.parametrize(
    ("renglones", "excedente", "cancelada", "de_otro_proveedor"),
    [
        pytest.param([("10.0000", "0.0000")], "0", True, False, id="cancelada_sin_nada_recibido"),
        pytest.param(
            [("10.0000", "12.0000")], "2", False, False, id="cerrada_con_excedente_autorizado"
        ),
        pytest.param([("10.0000", "0.0000")], "0", False, True, id="abierta_de_otro_proveedor"),
    ],
)
def test_hdu004_esc12_cancelada_cerrada_o_ajena_no_es_pendiente(
    escenario: Escenario,
    renglones: list[tuple[str, str]],
    excedente: str,
    cancelada: bool,
    de_otro_proveedor: bool,
) -> None:
    """HDU-004 esc. 12 · CA-5 y CA-12 — ni la cancelada, ni la cerrada con excedente, ni la de otro proveedor bloquean."""
    proveedor = uuid.uuid4()
    dueno = uuid.uuid4() if de_otro_proveedor else proveedor
    _sembrar(
        escenario,
        proveedor=dueno,
        folio="OC-T029B-0001",
        renglones=renglones,
        excedente=excedente,
        cancelada=cancelada,
    )

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == ()


def test_tkt029b_orden_viva_sin_renglones_no_es_pendiente(escenario: Escenario) -> None:
    """CA-5 · D-2 — una orden viva sin renglones no tiene material por recibir: no es pendiente."""
    proveedor = uuid.uuid4()
    _sembrar(escenario, proveedor=proveedor, folio="OC-T029B-0001", renglones=[])
    # La orden está viva en la tabla: el `()` lo causa la falta de renglones, no una siembra vacía.
    assert _ordenes_visibles(escenario.motor) == 1

    with Session(escenario.motor) as sesion:
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == ()


def test_tkt029b_lectura_de_pendientes_corre_en_solo_lectura_y_no_escribe(
    escenario: Escenario,
) -> None:
    """CA-12 esc. 1 — la lectura corre en `SET TRANSACTION READ ONLY` y no asigna ningún `xid`: no escribe."""
    proveedor = uuid.uuid4()
    abierta = _sembrar(
        escenario,
        proveedor=proveedor,
        folio="OC-T029B-0001",
        renglones=[("10.0000", "0.0000")],
    )

    with Session(escenario.motor) as sesion:
        sesion.execute(text("SET TRANSACTION READ ONLY"))
        assert sesion.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)
        # Una transacción que no escribió no tiene `xid` asignado; una que escribió tendría uno.
        xid = sesion.execute(text("SELECT txid_current_if_assigned()")).scalar_one()
        assert xid is None
        # Control: la transacción rechaza escrituras de verdad, así que la comprobación anterior no es vacía.
        with pytest.raises(DBAPIError) as error:
            sesion.execute(text("UPDATE orden_compra SET motivo_cancelacion = NULL WHERE false"))
        assert getattr(error.value.orig, "sqlstate", None) == SQLSTATE_SOLO_LECTURA

    assert resultado == (OrdenPendiente(abierta, "OC-T029B-0001", EstadoOrden.ABIERTA),)


def test_tkt029b_lectura_de_pendientes_usa_la_sesion_recibida(escenario: Escenario) -> None:
    """CA-12 esc. 1 — la lectura usa la sesión que recibe: ve una orden sembrada sin confirmar en esa transacción."""
    proveedor = uuid.uuid4()
    with Session(escenario.motor) as sesion:
        crudo = sesion.connection().connection.driver_connection
        assert crudo is not None
        crudo_tipado = cast(
            Conexion, crudo
        )  # driver_connection es Optional[Any] en SQLAlchemy; con la sesión abierta siempre existe
        orden = _sembrar(
            escenario,
            proveedor=proveedor,
            folio="OC-T029B-0001",
            renglones=[("10.0000", "0.0000")],
            conexion=crudo_tipado,
        )
        # Sin confirmar, otra conexión no la ve: lo que devuelva la función sale de esta transacción.
        assert _ordenes_visibles(escenario.motor) == 0

        resultado = ordenes_pendientes_de_proveedor(sesion, proveedor)

    assert resultado == (OrdenPendiente(orden, "OC-T029B-0001", EstadoOrden.ABIERTA),)


def test_tkt029b_interfaz_de_compras_publica_solo_la_lectura_y_proveedores_no_la_salta() -> None:
    """CA-12 esc. 3 · CA-R2 — `compras` publica sus dos nombres, `proveedores` solo lo importa por la interfaz y `lint-imports` está en verde."""
    assert getattr(interfaz, "__all__", None) == NOMBRES_PUBLICADOS

    # Control del detector: un recorrido que no ve ningún import no prueba nada.
    controles = [
        modulo
        for nodo in _nodos_de_importacion(
            "import cimenta.compras.dominio\n"
            "from cimenta.compras import interfaz\n"
            "from cimenta.compras.interfaz import OrdenPendiente\n"
            "from cimenta import compras\n"
        )
        for modulo in _importados_de_compras(nodo)
    ]
    assert controles == ["cimenta.compras.dominio", "cimenta.compras"]

    assert _importaciones_de_compras_fuera_de_la_interfaz() == []

    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache"],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
