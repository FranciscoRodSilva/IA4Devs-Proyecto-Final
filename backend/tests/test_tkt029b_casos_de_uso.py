"""Caso de uso de la baja de proveedores (TKT-029b, entrega b, fila F5): TC-23 a TC-30.

Prueba `dar_baja_proveedor` de `cimenta/proveedores/aplicacion/proveedores.py` contra PostgreSQL real,
con el esquema de `alembic upgrade head` y el rol de aplicación. Nada de SQLite, nada de `sleep` para
sincronizar. Las órdenes de compra se siembran con `herramientas.soporte_tkt029b_ordenes`, con
`cantidad_recibida` explícita, y sus folios tienen la forma `OC-T029B-NNNN`: las pruebas que dependen del
orden por folio las insertan al revés del orden esperado, para que un orden por inserción o por `id` falle.

Las *fixtures* son propias de este archivo, copiadas de las de TKT-029a (nota de ejecución del
diseño): ningún archivo de prueba importa a otro.

Los proveedores se siembran con SQL directo, no con `crear_proveedor`: un defecto del alta no puede tapar
ni causar el fallo de la baja. Las comprobaciones de estado y de bitácora leen las tablas con una conexión
propia del rol de aplicación, no con el repositorio.

Qué cubre cada prueba:

- `TC-23` (HDU-004 esc. 13, `CA-1`): desde `ACTIVO` sin órdenes; la fila completa y el asiento `DAR_BAJA`.
- `TC-24` (HDU-004 esc. 13, `CA-2`): desde `DESACTIVADO`; el asiento guarda el estado anterior real (`M-13`).
- `TC-25` (HDU-004 esc. 12, `CA-3`): `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` desde `ACTIVO` con una `ABIERTA` y
  una `PARCIAL`, por folio (`M-11`), con la acción `DESACTIVAR_PROVEEDOR`.
- Variantes de `TC-25` y `TC-26` (`D-4`): el número de órdenes en singular y en plural en las dos ramas del
  mensaje.
- `TC-26` (HDU-004 esc. 12, `CA-4`): desde `DESACTIVADO` con una `PARCIAL`; sin acciones (`M-10`).
- `TC-27` (HDU-004 esc. 12, `CA-7`): `BAJA` es terminal, con o sin órdenes pendientes; la desactivación sobre
  `BAJA` no cambia.
- `TC-28` (HDU-004 esc. 12, `CA-10`): proveedor inexistente.
- `TC-29` (HDU-004 esc. 13, `CA-1`): la bitácora se escribe en la misma transacción (`M-12`).
- `TC-30` (HDU-004 esc. 12, `CA-11`): dos bajas simultáneas; pasa una sola (`M-9`).

Mutantes de la fila: `M-9` (leer con `para_cambio=False`) debe poner en rojo `TC-30`; `M-10` (la acción
`DESACTIVAR_PROVEEDOR` se ofrece siempre), `TC-26`; `M-12` (asentar con una sesión propia), `TC-29`;
`M-13` (`datos_antes` con el literal `ACTIVO`), `TC-24`.
"""

from __future__ import annotations

import functools
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from cimenta.proveedores.aplicacion import proveedores
from cimenta.proveedores.aplicacion.contexto import construir_contexto
from cimenta.proveedores.infraestructura import repositorio_proveedor
from contrato_error.excepciones import ConflictoEstado, NoEncontrado
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Base, Hilo
from herramientas.soporte_tkt029b_ordenes import sembrar_orden_compra
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba, SembrarUsuario

    from cimenta.proveedores.aplicacion.contexto import ContextoProveedores

    Contexto = Callable[[], ContextoProveedores]

CORRELACION = "corr-tkt029b-f5"
ROLES_COMPRAS = frozenset({"COMPRAS"})
CORREO_DEL_CREADOR = "compras@cimenta.test"
CORREO_DEL_SEGUNDO = "compras.dos@cimenta.test"
CONTRASENA = "Clave-Correcta-1"
CREADO_ANTES = datetime(2026, 10, 1, 8, 15, tzinfo=UTC)
MENSAJE_PROVEEDOR_NO_EXISTE = "El proveedor no existe."
MENSAJE_YA_DADO_DE_BAJA = "El proveedor ya está dado de baja: su estado es BAJA."
MENSAJE_DESACTIVAR_SOBRE_BAJA = "El proveedor no está activo: su estado es BAJA."

COLUMNAS_DE_PROVEEDOR = (
    "SELECT id, nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, creado_en, "
    "creado_por_id FROM proveedor WHERE id = %s"
)
COLUMNAS_DE_BITACORA = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, obra_id, "
    "regla_negocio, motivo, datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s "
    "ORDER BY accion::text"
)


# --------------------------------------------------------------------------- el entorno


@dataclass(frozen=True)
class Padres:
    """Las filas padre de una orden de compra: obra, tipo de partida, insumo y solicitante."""

    obra: uuid.UUID
    tipo_partida: uuid.UUID
    insumo: uuid.UUID
    solicitante: uuid.UUID


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def contexto_proveedores(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto de `proveedores` sobre el rol de aplicación, construido al primer uso.

    Es propia de este archivo (nota de ejecución del diseño).
    """

    def construir() -> ContextoProveedores:
        return construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)

    return functools.cache(construir)


@pytest.fixture
def creador(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Usuario de COMPRAS: `creado_por_id` tiene clave foránea a `usuario`; también solicita las requisiciones."""
    return sembrar_usuario(CORREO_DEL_CREADOR, CONTRASENA, roles=("COMPRAS",))


@pytest.fixture
def segundo_usuario(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Otro usuario de COMPRAS, para distinguir quién asienta en la prueba de concurrencia."""
    return sembrar_usuario(CORREO_DEL_SEGUNDO, CONTRASENA, roles=("COMPRAS",), nombre="Luis Prieto")


@pytest.fixture
def padres(datos_presupuesto: DatosPresupuesto, creador: uuid.UUID) -> Padres:
    """La obra, el tipo de partida y el insumo de las órdenes, escritos con el rol de aplicación."""
    return Padres(
        obra=datos_presupuesto.obra(codigo="OB-T029B"),
        tipo_partida=datos_presupuesto.tipo_partida(),
        insumo=datos_presupuesto.insumo_nuevo(),
        solicitante=creador,
    )


def _sembrar(
    base: Base,
    creador_id: uuid.UUID,
    *,
    nombre: str,
    rfc: str,
    estado: str = "ACTIVO",
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
) -> uuid.UUID:
    """Inserta una fila en `proveedor` con SQL directo, sin pasar por el repositorio ni el caso de uso."""
    proveedor_id = uuid.uuid4()
    base.ejecutar(
        "INSERT INTO proveedor (id, nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, "
        "creado_en, creado_por_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        proveedor_id,
        nombre,
        rfc,
        estado,
        None if tope is None else Decimal(tope),
        dia_corte,
        dia_pago,
        CREADO_ANTES,
        creador_id,
    )
    return proveedor_id


def _orden(
    base: Base,
    padres: Padres,
    *,
    proveedor: uuid.UUID,
    folio: str,
    renglones: list[tuple[str, str]],
) -> uuid.UUID:
    """Una orden de `proveedor` con la siembra de `herramientas`, con el rol de aplicación y `cantidad_recibida` explícita."""
    return sembrar_orden_compra(
        base.conexion,
        obra_id=padres.obra,
        tipo_partida_id=padres.tipo_partida,
        insumo_id=padres.insumo,
        solicitante_id=padres.solicitante,
        proveedor_id=proveedor,
        folio=folio,
        renglones=renglones,
    )


def _cuenta(base: Base, consulta: LiteralString, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: proveedores, bitácora, órdenes y renglones."""
    return {
        "proveedores": base.filas("SELECT * FROM proveedor ORDER BY id"),
        "bitacora": base.filas("SELECT id FROM bitacora ORDER BY id"),
        "ordenes": base.filas("SELECT * FROM orden_compra ORDER BY id"),
        "renglones": base.filas("SELECT * FROM orden_compra_renglon ORDER BY id"),
    }


def _cuerpo_de_estado(estado: str, mensaje: str) -> dict[str, object]:
    """El cuerpo completo del `409` de `ESTADO_NO_PERMITE_OPERACION` que ve COMPRAS."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": mensaje,
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"estado_actual": estado},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }


def _cuerpo_de_ordenes(
    *,
    mensaje: str,
    ordenes: list[tuple[uuid.UUID, str, str]],
    acciones: list[dict[str, str]],
) -> dict[str, object]:
    """El cuerpo completo del `409` de `PROVEEDOR_CON_ORDENES_ABIERTAS` que ve COMPRAS (`D-4`)."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": mensaje,
        "codigo": "PROVEEDOR_CON_ORDENES_ABIERTAS",
        "detalle": {
            "ordenes": [
                {"id": str(orden_id), "folio": folio, "estado": estado}
                for orden_id, folio, estado in ordenes
            ]
        },
        "acciones": acciones,
        "correlacion_id": CORRELACION,
    }


def _accion_desactivar(proveedor_id: uuid.UUID) -> dict[str, str]:
    return {
        "clave": "DESACTIVAR_PROVEEDOR",
        "metodo": "POST",
        "ruta": f"/api/v1/proveedores/{proveedor_id}/desactivacion",
    }


def _hay_alguien_esperando(base: Base, patron: str) -> bool:
    """Una sesión de la base detenida por un bloqueo, con una consulta como `patron`."""
    fila = base.conexion.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND wait_event_type = 'Lock' AND cardinality(pg_blocking_pids(pid)) > 0 "
        "AND query ILIKE %s",
        (patron,),
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def _alguien_espera(base: Base, patron: str) -> Callable[[], bool]:
    """La condición de `esperar_hasta`: alguien detenido en una consulta como `patron`."""
    return lambda: _hay_alguien_esperando(base, patron)


# --------------------------------------------------------------------------- TC-23 · CA-1


def test_hdu004_esc13_baja_desde_activo_sin_ordenes_conserva_la_fila_y_asienta_dar_baja(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-23 · HDU-004 esc. 13 · CA-1 — `ACTIVO` sin órdenes pasa a `BAJA`; nada más cambia; `DAR_BAJA` lleva el motivo.

    El proveedor tiene tope y días distintos de los de omisión, para comprobar que se conservan. La fila se
    compara completa: solo `estado` cambia. El asiento es único y trae `entidad_tipo` `proveedor`, el
    usuario, el reloj inyectado, el motivo recibido, `datos_antes` `ACTIVO` y `datos_despues` `BAJA`, con
    `regla_negocio` y `obra_id` nulos. Otro proveedor no cambia.
    """
    dar_baja = proveedores.dar_baja_proveedor
    reloj_de_prueba.avanzar(timedelta(hours=3))
    ahora = reloj_de_prueba()
    proveedor_id = _sembrar(
        base,
        creador,
        nombre="CoPanel",
        rfc="XAXX010101000",
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    vecino = _sembrar(base, creador, nombre="Tablaroca Sur", rfc="TSU010101AB2")
    vecino_antes = base.filas(COLUMNAS_DE_PROVEEDOR, vecino)

    resultado = dar_baja(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        motivo="Cerró su negocio",
        usuario_id=creador,
    )

    assert resultado is None
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        (
            proveedor_id,
            "CoPanel",
            "XAXX010101000",
            "BAJA",
            "300000.0000",
            2,
            5,
            CREADO_ANTES,
            creador,
        )
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, proveedor_id) == [
        (
            "DAR_BAJA",
            "proveedor",
            proveedor_id,
            creador,
            ahora,
            None,
            None,
            "Cerró su negocio",
            {"estado": "ACTIVO"},
            {"estado": "BAJA"},
        )
    ]
    assert base.filas(COLUMNAS_DE_PROVEEDOR, vecino) == vecino_antes, "Otro proveedor no cambia"
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Una baja, un solo asiento"
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 2


# --------------------------------------------------------------------------- TC-24 · CA-2


def test_hdu004_esc13_baja_desde_desactivado_asienta_el_estado_anterior_real(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-24 · HDU-004 esc. 13 · CA-2 — `DESACTIVADO` sin órdenes pasa a `BAJA` y `datos_antes` guarda `DESACTIVADO` (`M-13`).

    El asiento no puede copiar el literal `ACTIVO` de la desactivación: guarda el estado leído de la fila.
    Con `datos_antes` fijo en `ACTIVO` (`M-13`) la prueba cae. La fila conserva todo lo demás.
    """
    dar_baja = proveedores.dar_baja_proveedor
    reloj_de_prueba.avanzar(timedelta(hours=1))
    ahora = reloj_de_prueba()
    proveedor_id = _sembrar(
        base,
        creador,
        nombre="CoPanel",
        rfc="XAXX010101000",
        estado="DESACTIVADO",
        tope="120000.0000",
        dia_corte=3,
        dia_pago=7,
    )

    dar_baja(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        motivo="Ya no surte tablaroca",
        usuario_id=creador,
    )

    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        (
            proveedor_id,
            "CoPanel",
            "XAXX010101000",
            "BAJA",
            "120000.0000",
            3,
            7,
            CREADO_ANTES,
            creador,
        )
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, proveedor_id) == [
        (
            "DAR_BAJA",
            "proveedor",
            proveedor_id,
            creador,
            ahora,
            None,
            None,
            "Ya no surte tablaroca",
            {"estado": "DESACTIVADO"},
            {"estado": "BAJA"},
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1


# --------------------------------------------------------------------------- TC-25 · CA-3


def test_hdu004_esc12_baja_con_ordenes_pendientes_se_rechaza_y_ofrece_desactivar(
    contexto_proveedores: Contexto,
    base: Base,
    padres: Padres,
    creador: uuid.UUID,
) -> None:
    """TC-25 · HDU-004 esc. 12 · CA-3 — `ACTIVO` con una `ABIERTA` y una `PARCIAL`: `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` (`M-11`).

    El contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), el `codigo` del catálogo, el mensaje
    literal de `D-4` con el nombre `CoPanel` y «2 órdenes», `detalle.ordenes` con el `id`, el `folio` y el
    `estado` de cada una **por folio** (se insertan al revés: la `ABIERTA` `OC-T029B-0002` entra antes que
    la `PARCIAL` `OC-T029B-0001`), y la acción `DESACTIVAR_PROVEEDOR` solo para quien gestiona proveedores.
    El proveedor sigue `ACTIVO` y no se asienta nada: ni fila ni bitácora ni órdenes cambian.
    """
    dar_baja = proveedores.dar_baja_proveedor
    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    abierta = _orden(
        base, padres, proveedor=proveedor_id, folio="OC-T029B-0002", renglones=[("10", "0")]
    )
    parcial = _orden(
        base, padres, proveedor=proveedor_id, folio="OC-T029B-0001", renglones=[("10", "4")]
    )
    antes = _foto(base)
    esperado = _cuerpo_de_ordenes(
        mensaje=(
            "CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes "
            "nuevas conservando las existentes."
        ),
        ordenes=[
            (parcial, "OC-T029B-0001", "PARCIAL"),
            (abierta, "OC-T029B-0002", "ABIERTA"),
        ],
        acciones=[_accion_desactivar(proveedor_id)],
    )

    with pytest.raises(ConflictoEstado) as rechazo:
        dar_baja(
            contexto_proveedores(),
            proveedor_id=proveedor_id,
            motivo="Cerró su negocio",
            usuario_id=creador,
        )

    error = rechazo.value
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    sin_gestion = error.cuerpo(frozenset({"RESIDENTE"}), CORRELACION)
    assert sin_gestion == {**esperado, "acciones": []}, (
        "Las acciones se filtran por el rol de quien llama"
    )
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [("ACTIVO",)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0, "Un rechazo no asienta nada"
    assert _foto(base) == antes, "El rechazo no escribe"


@pytest.mark.parametrize(
    ("estado", "cantidad", "mensaje", "con_accion"),
    [
        pytest.param(
            "ACTIVO",
            1,
            "CoPanel tiene 1 orden pendiente de recibir; se puede desactivar para órdenes "
            "nuevas conservando las existentes.",
            True,
            id="activo_una_orden",
        ),
        pytest.param(
            "DESACTIVADO",
            2,
            "CoPanel tiene 2 órdenes pendientes de recibir y ya está desactivado; la baja "
            "procede cuando esas órdenes se reciban completas o se cancelen.",
            False,
            id="desactivado_dos_ordenes",
        ),
    ],
)
def test_hdu004_esc12_baja_con_ordenes_pendientes_cuenta_en_singular_y_plural(
    estado: str,
    cantidad: int,
    mensaje: str,
    con_accion: bool,
    contexto_proveedores: Contexto,
    base: Base,
    padres: Padres,
    creador: uuid.UUID,
) -> None:
    """Variantes de TC-25 y TC-26 · HDU-004 esc. 12 · CA-3 · CA-4 · D-4 — «1 orden pendiente» y «2 órdenes pendientes» en cada rama.

    TC-25 prueba el plural desde `ACTIVO` y TC-26 el singular desde `DESACTIVADO`; esta prueba cierra las
    otras dos combinaciones, para que el número de órdenes y la rama del mensaje no puedan intercambiarse
    sin que algo caiga. La primera orden por folio es `PARCIAL` y las demás `ABIERTA`; se insertan al revés.
    """
    dar_baja = proveedores.dar_baja_proveedor
    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000", estado=estado)
    folios = [f"OC-T029B-{numero:04d}" for numero in range(1, cantidad + 1)]
    ids: dict[str, uuid.UUID] = {}
    for folio in reversed(folios):
        recibida = "4" if folio == folios[0] else "0"
        ids[folio] = _orden(
            base, padres, proveedor=proveedor_id, folio=folio, renglones=[("10", recibida)]
        )
    antes = _foto(base)
    esperado = _cuerpo_de_ordenes(
        mensaje=mensaje,
        ordenes=[
            (ids[folio], folio, "PARCIAL" if folio == folios[0] else "ABIERTA") for folio in folios
        ],
        acciones=[_accion_desactivar(proveedor_id)] if con_accion else [],
    )

    with pytest.raises(ConflictoEstado) as rechazo:
        dar_baja(
            contexto_proveedores(),
            proveedor_id=proveedor_id,
            motivo="Cerró su negocio",
            usuario_id=creador,
        )

    assert rechazo.value.estado_http == 409
    assert rechazo.value.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [(estado,)]
    assert _foto(base) == antes, "El rechazo no escribe"


# --------------------------------------------------------------------------- TC-26 · CA-4


def test_hdu004_esc12_baja_de_desactivado_con_orden_parcial_se_rechaza_sin_acciones(
    contexto_proveedores: Contexto,
    base: Base,
    padres: Padres,
    creador: uuid.UUID,
) -> None:
    """TC-26 · HDU-004 esc. 12 · CA-4 — `DESACTIVADO` con una `PARCIAL`: `409` con la orden listada y `acciones` vacía (`M-10`).

    Desactivar de nuevo respondería `409`, así que el rechazo no ofrece `DESACTIVAR_PROVEEDOR`; el mensaje
    explica por qué (`D-4`, singular). La orden `PARCIAL` se siembra con `cantidad_recibida` mayor que
    cero y un renglón completo, más una segunda orden `CERRADA` que no debe listarse. Nada cambia: el proveedor sigue
    `DESACTIVADO` y no hay asiento. Con la acción ofrecida siempre (`M-10`) la prueba cae.
    """
    dar_baja = proveedores.dar_baja_proveedor
    proveedor_id = _sembrar(
        base, creador, nombre="CoPanel", rfc="XAXX010101000", estado="DESACTIVADO"
    )
    _orden(base, padres, proveedor=proveedor_id, folio="OC-T029B-0002", renglones=[("5", "5")])
    parcial = _orden(
        base,
        padres,
        proveedor=proveedor_id,
        folio="OC-T029B-0001",
        renglones=[("10", "10"), ("5", "2")],
    )
    antes = _foto(base)
    esperado = _cuerpo_de_ordenes(
        mensaje=(
            "CoPanel tiene 1 orden pendiente de recibir y ya está desactivado; la baja procede "
            "cuando esas órdenes se reciban completas o se cancelen."
        ),
        ordenes=[(parcial, "OC-T029B-0001", "PARCIAL")],
        acciones=[],
    )

    with pytest.raises(ConflictoEstado) as rechazo:
        dar_baja(
            contexto_proveedores(),
            proveedor_id=proveedor_id,
            motivo="Cerró su negocio",
            usuario_id=creador,
        )

    error = rechazo.value
    assert error.estado_http == 409
    assert error.acciones == ()
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [
        ("DESACTIVADO",)
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    assert _foto(base) == antes, "El rechazo no escribe"


# --------------------------------------------------------------------------- TC-27 · CA-7


def test_hdu004_esc12_baja_de_un_proveedor_ya_dado_de_baja_es_terminal(
    contexto_proveedores: Contexto,
    base: Base,
    padres: Padres,
    creador: uuid.UUID,
) -> None:
    """TC-27 · HDU-004 esc. 12 · CA-7 — `BAJA` es terminal: `409` `ESTADO_NO_PERMITE_OPERACION` con `estado_actual` `BAJA` (`M-2`).

    Dos proveedores en `BAJA`, uno sin órdenes y otro con una `ABIERTA`: el estado terminal precede a las
    órdenes pendientes, así que ninguno responde `PROVEEDOR_CON_ORDENES_ABIERTAS`. El cuerpo completo trae
    el mensaje literal de `D-4`, `detalle` `{"estado_actual": "BAJA"}` y `acciones` vacía; no se asienta
    nada. Además, `desactivar_proveedor` sobre `BAJA` sigue respondiendo su mensaje de siempre.
    """
    dar_baja = proveedores.dar_baja_proveedor
    desactivar = proveedores.desactivar_proveedor
    sin_ordenes = _sembrar(
        base, creador, nombre="CoPanel", rfc="XAXX010101000", estado="BAJA", tope="1000.0000"
    )
    con_orden = _sembrar(base, creador, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="BAJA")
    _orden(base, padres, proveedor=con_orden, folio="OC-T029B-0001", renglones=[("10", "0")])
    antes = _foto(base)
    esperado = _cuerpo_de_estado("BAJA", MENSAJE_YA_DADO_DE_BAJA)

    for objetivo in (sin_ordenes, con_orden):
        with pytest.raises(ConflictoEstado) as rechazo:
            dar_baja(
                contexto_proveedores(),
                proveedor_id=objetivo,
                motivo="Segundo intento",
                usuario_id=creador,
            )
        error = rechazo.value
        assert error.estado_http == 409, objetivo
        assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado, objetivo
        assert error.acciones == (), objetivo
        assert _foto(base) == antes, f"El rechazo no escribe ({objetivo})"

    with pytest.raises(ConflictoEstado) as sobre_baja:
        desactivar(
            contexto_proveedores(),
            proveedor_id=sin_ordenes,
            motivo="Desactivar una baja",
            usuario_id=creador,
        )
    assert sobre_baja.value.estado_http == 409
    assert sobre_baja.value.cuerpo(ROLES_COMPRAS, CORRELACION) == _cuerpo_de_estado(
        "BAJA", MENSAJE_DESACTIVAR_SOBRE_BAJA
    )
    assert _foto(base) == antes, "La desactivación sobre BAJA tampoco escribe"
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", sin_ordenes) == [("BAJA",)]


# --------------------------------------------------------------------------- TC-28 · CA-10


def test_hdu004_esc12_baja_de_un_proveedor_inexistente(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """TC-28 · HDU-004 esc. 12 · CA-10 — `404` `NO_ENCONTRADO` con `recurso="proveedor"` y ningún asiento.

    Hay un proveedor real, para que el rechazo sea por el id y no por tabla vacía; no cambia.
    """
    dar_baja = proveedores.dar_baja_proveedor
    _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    antes = _foto(base)

    with pytest.raises(NoEncontrado) as rechazo:
        dar_baja(
            contexto_proveedores(),
            proveedor_id=uuid.uuid4(),
            motivo="No existe",
            usuario_id=creador,
        )

    error = rechazo.value
    assert error.estado_http == 404
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
        "recurso": "proveedor",
        "correlacion_id": CORRELACION,
    }
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    assert _foto(base) == antes, "El rechazo no escribe"


# --------------------------------------------------------------------------- TC-29 · CA-1, regla 8


def test_hdu004_esc13_baja_bitacora_en_la_misma_transaccion(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-29 · HDU-004 esc. 13 · CA-1 · regla 8 — si asentar falla, el proveedor sigue `ACTIVO` y no hay asiento (`M-12`).

    `asentar` se sustituye por uno que, antes de lanzar, comprueba que corre en la sesión de la baja y que
    ya ve el cambio a `BAJA` todavía sin confirmar: la bitácora se escribe en la misma transacción que el
    cambio. Al lanzar, la transacción se deshace. Con `asentar` en una sesión propia (`M-12`) no vería la
    `BAJA` sin confirmar y la prueba cae.
    """
    dar_baja = proveedores.dar_baja_proveedor

    class FallaDeBitacora(Exception):
        pass

    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    visto: dict[str, object] = {}

    def asentar_que_falla(*args: Any, **kwargs: Any) -> None:
        sesion_bd = args[0] if args else kwargs["sesion_bd"]
        visto["en_transaccion"] = sesion_bd.in_transaction()
        visto["estado_visto"] = sesion_bd.execute(
            text("SELECT estado FROM proveedor WHERE id = :id"), {"id": proveedor_id}
        ).scalar_one()
        raise FallaDeBitacora

    monkeypatch.setattr(proveedores, "asentar", asentar_que_falla)
    antes = _foto(base)

    with pytest.raises(FallaDeBitacora):
        dar_baja(
            contexto_proveedores(),
            proveedor_id=proveedor_id,
            motivo="Cerró su negocio",
            usuario_id=creador,
        )

    assert visto == {"en_transaccion": True, "estado_visto": "BAJA"}, (
        "asentar debe correr en la misma sesión, con la baja escrita y sin confirmar"
    )
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [("ACTIVO",)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    assert _foto(base) == antes, "Una baja que falla no deja ni el cambio ni el asiento"


# --------------------------------------------------------------------------- TC-30 · CA-11


def test_hdu004_esc12_dos_bajas_concurrentes(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    segundo_usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-30 · HDU-004 esc. 12 · CA-11 — dos bajas a la vez: B espera el `FOR UPDATE` y ve `BAJA` (`M-9`).

    Determinista y sin `sleep`. El hilo A se pausa dentro de `repositorio_proveedor.leer_proveedor`, en la
    llamada con `para_cambio=True`, con el `SELECT ... FOR UPDATE` ya tomado; el hilo B arranca y su
    lectura bloqueante queda detenida (la prueba lo espera sobre `pg_stat_activity` y `pg_blocking_pids`);
    con B detenido, la base sigue viendo `ACTIVO`. Se libera a A, que da de baja y confirma. B lee `BAJA` y
    responde `ESTADO_NO_PERMITE_OPERACION` con el estado actual `BAJA`. Con la lectura sin `FOR UPDATE`
    (`M-9`) A nunca llega a la pausa y la prueba cae al esperarla; si B leyera `ACTIVO` quedarían dos
    asientos `DAR_BAJA`. El hilo pausado se libera siempre en `finally`.
    """
    dar_baja = proveedores.dar_baja_proveedor
    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    ctx = contexto_proveedores()
    original = repositorio_proveedor.leer_proveedor
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A" and kwargs.get("para_cambio"):
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_proveedor, "leer_proveedor", envoltura)

    a = Hilo(
        "A",
        lambda: dar_baja(
            ctx, proveedor_id=proveedor_id, motivo="Motivo del hilo A", usuario_id=creador
        ),
    )
    b = Hilo(
        "B",
        lambda: dar_baja(
            ctx, proveedor_id=proveedor_id, motivo="Motivo del hilo B", usuario_id=segundo_usuario
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), (
            "El hilo A no llegó a leer el proveedor con FOR UPDATE"
        )
        b.start()
        espera = esperar_hasta(_alguien_espera(base, "%FROM proveedor%FOR UPDATE%"), 5.0)
        assert espera, (
            f"B no quedó esperando el bloqueo del proveedor mientras A lo tenía: {b.error!r}"
        )
        assert b.is_alive()
        assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [
            ("ACTIVO",)
        ], "La baja de A no se ve mientras no confirma"
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_COMPRAS, CORRELACION) == _cuerpo_de_estado(
        "BAJA", MENSAJE_YA_DADO_DE_BAJA
    )
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [("BAJA",)]
    assert base.filas(
        "SELECT usuario_id, motivo, datos_antes, datos_despues FROM bitacora "
        "WHERE accion = 'DAR_BAJA'"
    ) == [(creador, "Motivo del hilo A", {"estado": "ACTIVO"}, {"estado": "BAJA"})]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1
