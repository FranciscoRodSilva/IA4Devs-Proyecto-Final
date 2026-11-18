"""Repositorio de la obra (TKT-012b, fila A3): TC-14 a TC-18 y las sondas de los supuestos 2 y 3.

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` y conexión con el rol de
aplicación (`sesion_bd`, `motor_aplicacion` y `conectar`). Prueba las cinco funciones nuevas de
`cimenta/presupuesto/infraestructura/repositorio_obra.py`.

Contrato que fijan estas pruebas (nombres y tipos):

- `bloquear_obra_completa(sesion_bd, obra_id) -> FilaObraCompleta | None`: la misma fila que
  `leer_obra_completa` (con su línea base vigente, que puede venir de un `LEFT OUTER JOIN`), pero con
  `SELECT ... FOR UPDATE` sobre `obra`. PostgreSQL rechaza `FOR UPDATE` sobre el lado nulable de un
  `OUTER JOIN`: el bloqueo se limita a `obra` (`with_for_update(of=obra)`). Sin fila, `None`.
- `actualizar_obra(sesion_bd, obra_id, campos, ahora, usuario_id) -> None`: `campos` es un
  `Mapping[str, object]` cuyas claves son nombres de columna de `obra` (`nombre`, `domicilio`,
  `retencion_destajo_pct`, `fondo_garantia_pct`, `iva_acreditable`, `umbral_alerta_pct`). Los porcentajes
  llegan como `Porcentaje` y se guardan con `cuantizar().valor`; `umbral_alerta_pct: None` escribe `NULL`.
  Solo se escriben las claves presentes y, además, `actualizado_en = ahora` y `actualizado_por_id`.
- `cambiar_estado_obra(sesion_bd, obra_id, estado, ahora, usuario_id) -> None`: escribe `estado`,
  `actualizado_en` y `actualizado_por_id`; no valida el estado de origen (lo hizo el dominio).
- `eliminar_obra(sesion_bd, obra_id) -> None`: un `DELETE` de la fila. Si una tabla hija cuelga de la
  obra, el error del motor sale tal cual (`DBAPIError` con `SQLSTATE` `23001`).
- `contar_historial_propio(sesion_bd, obra_id) -> ConteosHistorialPropio`: `NamedTuple` del repositorio
  con `lineas_base: int` (cualquier estado), `linea_base_congelada: bool` (alguna `CONGELADA`),
  `importaciones`, `niveles`, `conceptos`, `precios_insumo` (solo los de esa obra: el precio general,
  con `obra_id` nulo, no cuenta) y `rendimientos_observados`, todos `int`. Se eligió esta forma, y no
  `ConteosHistorial` del dominio, porque el conteo por tabla es lo que TC-17 exige y el dominio solo
  conoce la suma `filas_propias`; el caso de uso suma las cuatro últimas.

Ninguna función confirma la transacción: la confirma el caso de uso. Las pruebas lo comprueban leyendo
desde otra conexión antes y después de confirmar.

Rojo de la fila A3: el repositorio trae esqueletos que lanzan `NotImplementedError`, así que las pruebas
de comportamiento fallan por eso. Las tres sondas (supuestos 2 y 3) y las de restricciones de `0006`
(TC-18, por SQL directo) nacen en verde a propósito: comprueban el motor, no el código nuevo.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import errors as errores_pg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.presupuesto.infraestructura.repositorio_obra import (
    ConteosHistorialPropio,
    actualizar_obra,
    bloquear_obra_completa,
    cambiar_estado_obra,
    contar_historial_propio,
    eliminar_obra,
    insertar_obra,
    leer_obra_completa,
)
from herramientas.tiempo_de_prueba import esperar_hasta
from tipos_base import Porcentaje

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto

TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
AHORA = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
LIMITE_DE_ESPERA = 20.0
ESPERA_EN_OBRA = "%FROM obra%FOR UPDATE%"

Conexion = psycopg.Connection[tuple[Any, ...]]


# ------------------------------------------------------------------------------------ fixtures


@pytest.fixture
def empresa_de_la_migracion(lector: Conexion) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008): la que usan las obras de estas pruebas."""
    filas = lector.execute("SELECT id FROM empresa WHERE activa").fetchall()
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def lector(base_de_prueba: str, conectar: Conectar) -> Conexion:
    """Otra conexión del rol de aplicación, con autocommit: solo ve lo que ya se confirmó."""
    return conectar("aplicacion", base_de_prueba)


@pytest.fixture
def obra_conocida(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID
) -> uuid.UUID:
    """Una obra `ACTIVA` con tres porcentajes distintos: un intercambio entre columnas se nota."""
    return datos_presupuesto.obra(
        codigo="AP-058-25",
        empresa_id=empresa_de_la_migracion,
        estado="ACTIVA",
        retencion_destajo_pct=Decimal("0.150000"),
        fondo_garantia_pct=Decimal("0.050000"),
        umbral_alerta_pct=Decimal("0.100000"),
        iva_acreditable=True,
    )


# ------------------------------------------------------------------------------------ ayudas


def _fila_sql(conexion: Conexion, obra_id: uuid.UUID) -> dict[str, Any] | None:
    """Todas las columnas de la obra tal como las ve `conexion`, o `None` si no existe."""
    cursor = conexion.execute("SELECT * FROM obra WHERE id = %s", (obra_id,))
    fila = cursor.fetchone()
    if fila is None:
        return None
    assert cursor.description is not None
    return {columna.name: valor for columna, valor in zip(cursor.description, fila, strict=True)}


def _fila_obligatoria(conexion: Conexion, obra_id: uuid.UUID) -> dict[str, Any]:
    fila = _fila_sql(conexion, obra_id)
    assert fila is not None, "La obra no existe"
    return fila


def _cuenta(conexion: Conexion, consulta: str, *parametros: object) -> int:
    fila = conexion.execute(consulta, parametros).fetchone()  # type: ignore[call-overload]
    assert fila is not None
    return int(fila[0])


def _columnas_distintas(antes: dict[str, Any], despues: dict[str, Any]) -> set[str]:
    return {columna for columna in antes if antes[columna] != despues[columna]}


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def _restriccion(error: DBAPIError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _hay_alguien_esperando(lector: Conexion, patron: str) -> Callable[[], bool]:
    """La condición de `esperar_hasta`: una sesión de la base detenida por un bloqueo con ese patrón."""

    def _condicion() -> bool:
        fila = lector.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
            (patron,),
        ).fetchone()
        assert fila is not None
        return bool(fila[0])

    return _condicion


# ----------------------------------------------------------------- TC-14 · bloquear_obra_completa


def test_tkt012b_ca12_bloquear_obra_completa_de_un_id_inexistente_devuelve_none(
    sesion_bd: Session,
) -> None:
    """TC-14 · CA-12 — rechazo: sin fila, `None` (el caso de uso lanza `NoEncontrado`)."""
    with sesion_bd.begin():
        assert bloquear_obra_completa(sesion_bd, uuid.uuid4()) is None


def test_tkt012b_ca1_bloquear_obra_completa_devuelve_la_obra_con_su_linea_base_vigente(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-14 · CA-1 — feliz: la misma fila que `leer_obra_completa`, con y sin línea base vigente.

    Con la línea base `CONGELADA` la consulta pasa por un `OUTER JOIN`: un `FOR UPDATE` sin limitarlo a
    `obra` lo rechaza el motor.
    """
    vigente = datos_presupuesto.linea_base(obra_id=obra_conocida, estado="CONGELADA", version=1)
    sin_vigente = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)

    with sesion_bd.begin():
        fila = bloquear_obra_completa(sesion_bd, obra_conocida)
        vacia = bloquear_obra_completa(sesion_bd, sin_vigente)

    assert fila is not None
    assert fila.id == obra_conocida
    assert fila.codigo == "AP-058-25"
    assert fila.nombre == "Obra AP-058-25"
    assert fila.domicilio == "Calle de prueba 1"
    assert fila.tipo_contrato == TIPO_CONTRATO
    assert fila.retencion_destajo_pct.serializar() == "0.150000"
    assert fila.fondo_garantia_pct.serializar() == "0.050000"
    assert fila.umbral_alerta_pct is not None
    assert fila.umbral_alerta_pct.serializar() == "0.100000"
    assert fila.iva_acreditable is True
    assert fila.estado == "ACTIVA"
    assert fila.linea_base_vigente_id == vigente
    assert fila.actualizado_en is None
    assert vacia is not None
    assert vacia.id == sin_vigente
    assert vacia.estado == "PLANEACION"
    assert vacia.linea_base_vigente_id is None


def test_tkt012b_ca13_bloquear_obra_completa_toma_for_update_y_la_segunda_sesion_espera(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-14 · CA-13 — concurrencia: la segunda sesión espera hasta que la primera confirma.

    La primera toma el bloqueo, lanza a la segunda y comprueba, con `pg_blocking_pids`, que quedó
    detenida en el `SELECT ... FROM obra ... FOR UPDATE`; mientras tanto cambia el estado por SQL y
    confirma. La segunda, ya liberada, lee el estado nuevo: lo que se decide tras el bloqueo es lo
    vigente. Sin sleeps: cada espera sondea una condición con un tope.
    """
    obra_id = datos_presupuesto.obra(
        codigo="AP-058-25", empresa_id=empresa_de_la_migracion, estado="ACTIVA"
    )
    adquirido = threading.Event()
    resultado: dict[str, Any] = {}

    def segunda_sesion() -> None:
        try:
            with Session(motor_aplicacion) as sesion_b, sesion_b.begin():
                fila = bloquear_obra_completa(sesion_b, obra_id)
                resultado["estado"] = None if fila is None else fila.estado
                adquirido.set()
        except BaseException as error:  # noqa: BLE001 - se informa al hilo principal
            resultado["error"] = error

    hilo = threading.Thread(target=segunda_sesion, daemon=True)
    try:
        with Session(motor_aplicacion) as primera, primera.begin():
            fila = bloquear_obra_completa(primera, obra_id)
            assert fila is not None
            assert fila.estado == "ACTIVA"

            hilo.start()
            esperando = esperar_hasta(
                _hay_alguien_esperando(lector, ESPERA_EN_OBRA), LIMITE_DE_ESPERA
            )
            assert esperando, "La segunda sesión no quedó detenida en el FOR UPDATE de obra"
            assert not adquirido.is_set(), "La segunda sesión obtuvo el bloqueo sin esperar"

            primera.execute(
                text("UPDATE obra SET estado = 'SUSPENDIDA' WHERE id = :id"), {"id": obra_id}
            )
    finally:
        if hilo.ident is not None:
            hilo.join(LIMITE_DE_ESPERA)

    assert not hilo.is_alive()
    assert "error" not in resultado, resultado.get("error")
    assert adquirido.is_set()
    assert resultado["estado"] == "SUSPENDIDA"


# ------------------------------------------------------------ sondas de los supuestos 2 y 3


def test_tkt012b_supuesto2_for_update_de_obra_bloquea_el_insert_de_una_fila_hija(
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    base_de_prueba: str,
    conectar: Conectar,
    lector: Conexion,
) -> None:
    """Supuesto 2 del diseño — sonda: `FOR UPDATE` sobre `obra` hace esperar al `INSERT` de una hija.

    Es lo que vuelve segura la carrera entre el borrado y la escritura de otro módulo: el `INSERT`
    toma `FOR KEY SHARE` sobre la obra por la clave foránea y choca con `FOR UPDATE`. Se usa SQL
    directo, no el repositorio: nace en verde porque comprueba el motor.
    """
    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    creador = datos_presupuesto.usuario()
    escritor = conectar("aplicacion", base_de_prueba)
    insertada = threading.Event()
    resultado: dict[str, Any] = {}

    def insertar_hija() -> None:
        try:
            escritor.execute(
                "INSERT INTO linea_base (id, obra_id, version, estado, importe_venta, creado_por_id) "
                "VALUES (%s, %s, 1, 'BORRADOR', 1000000, %s)",
                (uuid.uuid4(), obra_id, creador),
            )
            insertada.set()
        except BaseException as error:  # noqa: BLE001 - se informa al hilo principal
            resultado["error"] = error

    hilo = threading.Thread(target=insertar_hija, daemon=True)
    try:
        with Session(motor_aplicacion) as bloqueadora, bloqueadora.begin():
            bloqueadora.execute(
                text("SELECT id FROM obra WHERE id = :id FOR UPDATE"), {"id": obra_id}
            )
            hilo.start()
            esperando = esperar_hasta(
                _hay_alguien_esperando(lector, "%INSERT INTO linea_base%"), LIMITE_DE_ESPERA
            )
            assert esperando, "El INSERT de la hija no quedó detenido por el FOR UPDATE de la obra"
            assert not insertada.is_set()
    finally:
        if hilo.ident is not None:
            hilo.join(LIMITE_DE_ESPERA)

    assert "error" not in resultado, resultado.get("error")
    assert insertada.is_set()
    assert _cuenta(lector, "SELECT count(*) FROM linea_base WHERE obra_id = %s", obra_id) == 1


def test_tkt012b_supuesto3_delete_de_obra_con_hija_responde_23001_y_no_23503(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """Supuesto 3 del diseño — sonda: `DELETE FROM obra` con una hija responde `23001`, no `23503`.

    El caso de uso traduce `23001` a `OBRA_CON_HISTORIAL`; `23503` (`foreign_key_violation`) es lo que
    daría una clave `NO ACTION`, y no lo es. Se ejecuta por SQLAlchemy porque así lo verá el caso de uso.
    """
    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    datos_presupuesto.linea_base(obra_id=obra_id)

    with pytest.raises(DBAPIError) as info, sesion_bd.begin():
        sesion_bd.execute(text("DELETE FROM obra WHERE id = :id"), {"id": obra_id})

    assert _sqlstate(info.value) == "23001"
    assert _restriccion(info.value) == "fk_linea_base_obra_id"


# ----------------------------------------------------------- TC-15 · actualizar y cambiar estado


def test_tkt012b_ca1_actualizar_obra_escribe_solo_lo_indicado_y_sella_quien_y_cuando(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-15 · CA-1 · RN-25 — feliz: solo cambian las columnas indicadas más quién y cuándo.

    Ninguna otra columna de la obra ni ninguna otra obra se toca (un `UPDATE` sin `WHERE` lo delataría),
    y la función no confirma: desde otra conexión el cambio no se ve hasta que el caso de uso confirma.
    """
    editor = datos_presupuesto.usuario()
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    antes = _fila_obligatoria(lector, obra_conocida)
    antes_de_la_otra = _fila_obligatoria(lector, otra)

    with sesion_bd.begin():
        actualizar_obra(
            sesion_bd,
            obra_conocida,
            {
                "nombre": "Union Square F2 (ampliación)",
                "retencion_destajo_pct": Porcentaje("0.100000"),
            },
            AHORA,
            editor,
        )
        assert _fila_obligatoria(lector, obra_conocida) == antes, (
            "La función confirmó la transacción"
        )

    despues = _fila_obligatoria(lector, obra_conocida)
    assert _columnas_distintas(antes, despues) == {
        "nombre",
        "retencion_destajo_pct",
        "actualizado_en",
        "actualizado_por_id",
    }
    assert despues["nombre"] == "Union Square F2 (ampliación)"
    assert despues["retencion_destajo_pct"] == Decimal("0.100000")
    assert despues["actualizado_en"] == AHORA
    assert despues["actualizado_por_id"] == editor
    assert _fila_obligatoria(lector, otra) == antes_de_la_otra


def test_tkt012b_ca1_actualizar_obra_con_todos_los_campos_cuantiza_con_half_up(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-15 · CA-1 — feliz: cada clave llega a su columna y los porcentajes se cuantizan HALF_UP.

    Tres valores distintos, con más de 6 decimales: `0.1234565` queda `0.123457` (mitad hacia arriba).
    PostgreSQL redondea igual al guardar un `NUMERIC(9,6)`, así que esta prueba fija el resultado, no
    distingue si `cuantizar()` se llamó o no. El código, el tipo de contrato y el estado no se mueven.
    """
    antes = _fila_obligatoria(lector, obra_conocida)

    with sesion_bd.begin():
        actualizar_obra(
            sesion_bd,
            obra_conocida,
            {
                "nombre": "Nombre nuevo",
                "domicilio": "Domicilio nuevo 22",
                "retencion_destajo_pct": Porcentaje("0.1234565"),
                "fondo_garantia_pct": Porcentaje("0.0555555"),
                "umbral_alerta_pct": Porcentaje("0.2000004"),
                "iva_acreditable": False,
            },
            AHORA,
            datos_presupuesto.usuario(),
        )

    despues = _fila_obligatoria(lector, obra_conocida)
    assert despues["nombre"] == "Nombre nuevo"
    assert despues["domicilio"] == "Domicilio nuevo 22"
    assert despues["retencion_destajo_pct"] == Decimal("0.123457")
    assert despues["fondo_garantia_pct"] == Decimal("0.055556")
    assert despues["umbral_alerta_pct"] == Decimal("0.200000")
    assert despues["iva_acreditable"] is False
    for intacta in (
        "codigo",
        "tipo_contrato",
        "estado",
        "empresa_id",
        "creado_en",
        "creado_por_id",
    ):
        assert despues[intacta] == antes[intacta], intacta


def test_tkt012b_ca1_actualizar_obra_con_umbral_none_lo_borra_y_un_campo_ausente_lo_conserva(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-15 · CA-1 variante — `umbral_alerta_pct: None` escribe `NULL`; sin la clave se conserva."""
    editor = datos_presupuesto.usuario()

    with sesion_bd.begin():
        actualizar_obra(sesion_bd, obra_conocida, {"nombre": "Solo el nombre"}, AHORA, editor)
    conservado = _fila_obligatoria(lector, obra_conocida)
    assert conservado["umbral_alerta_pct"] == Decimal("0.100000")
    assert conservado["nombre"] == "Solo el nombre"

    with sesion_bd.begin():
        actualizar_obra(sesion_bd, obra_conocida, {"umbral_alerta_pct": None}, AHORA, editor)
    borrado = _fila_obligatoria(lector, obra_conocida)
    assert borrado["umbral_alerta_pct"] is None
    assert borrado["nombre"] == "Solo el nombre"

    with sesion_bd.begin():
        actualizar_obra(
            sesion_bd, obra_conocida, {"umbral_alerta_pct": Porcentaje("0.250000")}, AHORA, editor
        )
    assert _fila_obligatoria(lector, obra_conocida)["umbral_alerta_pct"] == Decimal("0.250000")


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        ("ACTIVA", "SUSPENDIDA"),
        ("SUSPENDIDA", "ACTIVA"),
        ("ACTIVA", "CERRADA"),
        ("SUSPENDIDA", "CERRADA"),
        ("PLANEACION", "CERRADA"),
    ],
)
def test_tkt012b_ca8_cambiar_estado_obra_escribe_el_estado_y_sella_quien_y_cuando(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
    origen: str,
    destino: str,
) -> None:
    """TC-15 · CA-8 — feliz: solo cambian `estado`, `actualizado_en` y `actualizado_por_id`.

    No toca otra obra y no confirma. El repositorio no valida el origen: eso ya lo hizo el dominio.
    """
    editor = datos_presupuesto.usuario()
    obra_id = datos_presupuesto.obra(
        codigo="AP-058-25", empresa_id=empresa_de_la_migracion, estado=origen
    )
    otra = datos_presupuesto.obra(
        codigo="AP-099-26", empresa_id=empresa_de_la_migracion, estado=origen
    )
    antes = _fila_obligatoria(lector, obra_id)
    antes_de_la_otra = _fila_obligatoria(lector, otra)

    with sesion_bd.begin():
        cambiar_estado_obra(sesion_bd, obra_id, destino, AHORA, editor)
        assert _fila_obligatoria(lector, obra_id) == antes, "La función confirmó la transacción"

    despues = _fila_obligatoria(lector, obra_id)
    assert _columnas_distintas(antes, despues) == {"estado", "actualizado_en", "actualizado_por_id"}
    assert despues["estado"] == destino
    assert despues["actualizado_en"] == AHORA
    assert despues["actualizado_por_id"] == editor
    assert _fila_obligatoria(lector, otra) == antes_de_la_otra


def test_tkt012b_car4_cambiar_estado_obra_no_toca_la_linea_base_ni_sus_copias(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    lector: Conexion,
) -> None:
    """TC-15 · CA-R4 — regresión: cerrar una obra con línea base congelada no altera ese historial."""
    copias = datos_presupuesto.linea_base_con_copias(estado="CONGELADA")
    consulta = (
        "SELECT estado, version, congelada_en, congelada_por_id, importe_venta "
        "FROM linea_base WHERE id = %s"
    )
    antes = lector.execute(consulta, (copias.linea_base_id,)).fetchone()
    assert antes is not None
    assert antes[0] == "CONGELADA"

    with sesion_bd.begin():
        cambiar_estado_obra(
            sesion_bd, copias.obra_id, "CERRADA", AHORA, datos_presupuesto.usuario()
        )

    assert lector.execute(consulta, (copias.linea_base_id,)).fetchone() == antes
    assert (
        _cuenta(
            lector,
            "SELECT count(*) FROM linea_base_concepto WHERE linea_base_id = %s",
            copias.linea_base_id,
        )
        == 1
    )
    assert _fila_obligatoria(lector, copias.obra_id)["estado"] == "CERRADA"


# ------------------------------------------------------------------ TC-16 · eliminar_obra


def test_tkt012b_ca5_eliminar_obra_borra_la_fila_y_libera_el_codigo(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-16 · CA-5 · HDU-001 esc. 20 — feliz: la fila desaparece, el código queda libre y nada más se borra.

    La función no confirma (la fila sigue visible desde otra conexión hasta el `commit`). Con el código
    liberado, `uq_obra_codigo` ya no estorba un alta con el mismo código.
    """
    obra_id = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    otra = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    antes_de_la_otra = _fila_obligatoria(lector, otra)

    with sesion_bd.begin():
        eliminar_obra(sesion_bd, obra_id)
        assert _fila_sql(lector, obra_id) is not None, "La función confirmó la transacción"

    assert _fila_sql(lector, obra_id) is None
    assert _fila_obligatoria(lector, otra) == antes_de_la_otra
    assert _cuenta(lector, "SELECT count(*) FROM obra WHERE codigo = %s", "AP-099-26") == 0

    nueva = uuid.uuid4()
    with sesion_bd.begin():
        insertar_obra(
            sesion_bd,
            obra_id=nueva,
            empresa_id=empresa_de_la_migracion,
            codigo="AP-099-26",
            nombre="Alta con el código liberado",
            domicilio="Calle de prueba 2",
            tipo_contrato=TIPO_CONTRATO,
            retencion_destajo_pct=Porcentaje("0.050000"),
            fondo_garantia_pct=Porcentaje("0.050000"),
            iva_acreditable=True,
            umbral_alerta_pct=None,
            creado_en=AHORA,
            creado_por_id=datos_presupuesto.usuario(),
        )
    releida = leer_obra_completa(sesion_bd, nueva)
    assert releida is not None
    assert releida.codigo == "AP-099-26"


@pytest.mark.parametrize(
    ("hija", "tabla", "restriccion"),
    [
        (lambda d, o: d.linea_base(obra_id=o), "linea_base", "fk_linea_base_obra_id"),
        (lambda d, o: d.importacion(obra_id=o), "importacion", "fk_importacion_obra_id"),
        (lambda d, o: d.nivel(obra_id=o), "nivel", "fk_nivel_obra_id"),
    ],
    ids=["linea_base", "importacion", "nivel"],
)
def test_tkt012b_ca6_eliminar_obra_con_una_hija_responde_23001_y_no_borra_nada(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
    hija: Callable[[DatosPresupuesto, uuid.UUID], object],
    tabla: str,
    restriccion: str,
) -> None:
    """TC-16 · CA-6 · CA-R3 · RN-01 — rechazo: con una hija, `DELETE` responde `23001` con su restricción.

    El error del motor sale tal cual (el caso de uso lo traduce a `OBRA_CON_HISTORIAL`). La obra, su
    hija y su código siguen intactos: el rechazo no deja un borrado a medias.
    """
    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    hija(datos_presupuesto, obra_id)
    antes = _fila_obligatoria(lector, obra_id)
    hijas_antes = _cuenta(lector, f"SELECT count(*) FROM {tabla} WHERE obra_id = %s", obra_id)  # noqa: S608
    assert hijas_antes == 1

    with pytest.raises(DBAPIError) as info, sesion_bd.begin():
        eliminar_obra(sesion_bd, obra_id)

    assert _sqlstate(info.value) == "23001"
    assert _restriccion(info.value) == restriccion
    assert _fila_obligatoria(lector, obra_id) == antes
    assert (
        _cuenta(lector, f"SELECT count(*) FROM {tabla} WHERE obra_id = %s", obra_id)  # noqa: S608
        == hijas_antes
    )
    with pytest.raises(errores_pg.UniqueViolation) as duplicado:
        datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    assert duplicado.value.diag.constraint_name == "uq_obra_codigo"


# ------------------------------------------------------------ TC-17 · contar_historial_propio


def _ninguno() -> ConteosHistorialPropio:
    return ConteosHistorialPropio(
        lineas_base=0,
        linea_base_congelada=False,
        importaciones=0,
        niveles=0,
        conceptos=0,
        precios_insumo=0,
        rendimientos_observados=0,
    )


def test_tkt012b_ca6_contar_historial_propio_de_una_obra_sin_nada_es_cero_en_todo(
    sesion_bd: Session,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-17 · CA-5 — feliz: una obra recién creada no tiene historial propio en ninguna tabla."""
    with sesion_bd.begin():
        assert contar_historial_propio(sesion_bd, obra_conocida) == _ninguno()


@pytest.mark.parametrize(
    ("construir", "esperado"),
    [
        (
            lambda d, o: d.linea_base(obra_id=o, estado="BORRADOR"),
            {"lineas_base": 1, "linea_base_congelada": False},
        ),
        (
            lambda d, o: d.linea_base(obra_id=o, estado="CONGELADA"),
            {"lineas_base": 1, "linea_base_congelada": True},
        ),
        (
            lambda d, o: d.linea_base(obra_id=o, estado="SUPERSEDIDA"),
            {"lineas_base": 1, "linea_base_congelada": False},
        ),
        (lambda d, o: d.importacion(obra_id=o), {"importaciones": 1}),
        (lambda d, o: d.nivel(obra_id=o), {"niveles": 1}),
        (lambda d, o: d.concepto(obra_id=o), {"conceptos": 1}),
        (lambda d, o: d.precio_insumo(obra_id=o), {"precios_insumo": 1}),
        (lambda d, o: d.rendimiento_observado(obra_id=o), {"rendimientos_observados": 1}),
    ],
    ids=[
        "linea_base_borrador",
        "linea_base_congelada",
        "linea_base_supersedida",
        "importacion",
        "nivel",
        "concepto",
        "precio_insumo",
        "rendimiento_observado",
    ],
)
def test_tkt012b_ca6_contar_historial_propio_cuenta_cada_tabla_por_separado(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    construir: Callable[[DatosPresupuesto, uuid.UUID], object],
    esperado: dict[str, Any],
) -> None:
    """TC-17 · CA-6 · RN-01 — feliz: una fila en una sola tabla mueve solo su conteo.

    `linea_base_congelada` es verdadero solo con una línea base `CONGELADA`: ni `BORRADOR` ni
    `SUPERSEDIDA` lo encienden, aunque las dos cuentan como línea base.
    """
    construir(datos_presupuesto, obra_conocida)

    with sesion_bd.begin():
        conteos = contar_historial_propio(sesion_bd, obra_conocida)

    assert conteos == _ninguno()._replace(**esperado)


def test_tkt012b_ca6_contar_historial_propio_filtra_por_obra_y_no_cuenta_el_precio_general(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-17 · CA-6 — feliz: conteos distintos por tabla, solo de esta obra, sin el precio general.

    Dos, tres, cuatro, cinco, seis y siete filas: un conteo cruzado entre tablas no pasa. Otra obra con
    una fila en cada tabla y un precio general (`obra_id` nulo) no suman.
    """
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    datos_presupuesto.linea_base(obra_id=otra, estado="BORRADOR")
    datos_presupuesto.importacion(obra_id=otra)
    datos_presupuesto.nivel(obra_id=otra)
    datos_presupuesto.concepto(obra_id=otra)
    datos_presupuesto.precio_insumo(obra_id=otra)
    datos_presupuesto.rendimiento_observado(obra_id=otra)
    datos_presupuesto.precio_insumo(obra_id=None)

    datos_presupuesto.linea_base(obra_id=obra_conocida, estado="SUPERSEDIDA", version=1)
    datos_presupuesto.linea_base(obra_id=obra_conocida, estado="CONGELADA", version=2)
    for _ in range(3):
        datos_presupuesto.importacion(obra_id=obra_conocida)
    for orden in range(1, 5):
        datos_presupuesto.nivel(obra_id=obra_conocida, nombre=f"Nivel {orden}", orden=orden)
    for numero in range(5):
        datos_presupuesto.concepto(obra_id=obra_conocida, codigo=f"C{numero}")
    for _ in range(6):
        datos_presupuesto.precio_insumo(obra_id=obra_conocida)
    for _ in range(7):
        datos_presupuesto.rendimiento_observado(obra_id=obra_conocida)

    with sesion_bd.begin():
        conteos = contar_historial_propio(sesion_bd, obra_conocida)

    assert conteos == ConteosHistorialPropio(
        lineas_base=2,
        linea_base_congelada=True,
        importaciones=3,
        niveles=4,
        conceptos=5,
        precios_insumo=6,
        rendimientos_observados=7,
    )


# ------------------------------------------------------ TC-18 · restricciones de 0006 siguen


@pytest.mark.parametrize(
    ("columna", "valor", "restriccion"),
    [
        ("retencion_destajo_pct", Decimal("1.000001"), "ck_obra_retencion_destajo_pct_rango"),
        ("retencion_destajo_pct", Decimal("-0.000001"), "ck_obra_retencion_destajo_pct_rango"),
        ("fondo_garantia_pct", Decimal("1.000001"), "ck_obra_fondo_garantia_pct_rango"),
        ("fondo_garantia_pct", Decimal("-0.000001"), "ck_obra_fondo_garantia_pct_rango"),
        ("umbral_alerta_pct", Decimal("-0.000001"), "ck_obra_umbral_alerta_pct_no_negativo"),
        ("estado", "BORRADA", "ck_obra_estado"),
        ("tipo_contrato", "OTRO_CONTRATO", "ck_obra_tipo_contrato"),
    ],
)
def test_tkt012b_car3_las_restricciones_de_0006_rechazan_por_sql_directo(
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
    columna: str,
    valor: object,
    restriccion: str,
) -> None:
    """TC-18 · CA-R3 — rechazo: los `CHECK` de `obra` siguen siendo la última barrera.

    Se llega al motor saltándose el API y el repositorio, con la conexión del rol de aplicación.
    """
    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)
    antes = _fila_obligatoria(lector, obra_id)

    consulta = sql.SQL("UPDATE obra SET {} = %s WHERE id = %s").format(sql.Identifier(columna))
    with pytest.raises(errores_pg.CheckViolation) as info:
        lector.execute(consulta, (valor, obra_id))

    assert info.value.diag.constraint_name == restriccion
    assert _fila_obligatoria(lector, obra_id) == antes


def test_tkt012b_car3_uq_obra_codigo_rechaza_un_codigo_repetido_por_sql_directo(
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-18 · CA-R3 — rechazo: `uq_obra_codigo` impide dos obras con el mismo código."""
    datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)

    with pytest.raises(errores_pg.UniqueViolation) as info:
        datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)

    assert info.value.diag.constraint_name == "uq_obra_codigo"
    assert _cuenta(lector, "SELECT count(*) FROM obra WHERE codigo = %s", "AP-058-25") == 1


def test_tkt012b_car3_los_bordes_de_los_rangos_de_0006_se_aceptan(
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-18 · CA-R3 — borde: 0 y 1 son porcentajes válidos y el umbral 0 también (`>=`, no `>`)."""
    obra_id = datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)

    lector.execute(
        "UPDATE obra SET retencion_destajo_pct = 1, fondo_garantia_pct = 0, umbral_alerta_pct = 0 "
        "WHERE id = %s",
        (obra_id,),
    )

    fila = _fila_obligatoria(lector, obra_id)
    assert fila["retencion_destajo_pct"] == Decimal("1.000000")
    assert fila["fondo_garantia_pct"] == Decimal("0.000000")
    assert fila["umbral_alerta_pct"] == Decimal("0.000000")


def test_tkt012b_car3_actualizar_obra_con_un_porcentaje_fuera_de_rango_lo_rechaza_el_motor(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-18 · CA-R3 — rechazo: aunque el API valide antes, el `UPDATE` del repositorio no se salta el `CHECK`.

    El repositorio escribe lo que recibe (la validación de rango es del caso de uso); el motor es la
    última barrera, y el cambio no deja nada a medias.
    """
    antes = _fila_obligatoria(lector, obra_conocida)

    with pytest.raises(DBAPIError) as info, sesion_bd.begin():
        actualizar_obra(
            sesion_bd,
            obra_conocida,
            {"retencion_destajo_pct": Porcentaje("1.500000")},
            AHORA,
            datos_presupuesto.usuario(),
        )

    assert _sqlstate(info.value) == "23514"
    assert _restriccion(info.value) == "ck_obra_retencion_destajo_pct_rango"
    assert _fila_obligatoria(lector, obra_conocida) == antes


def test_tkt012b_car3_cambiar_estado_obra_a_un_estado_desconocido_lo_rechaza_el_motor(
    sesion_bd: Session,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-18 · CA-R3 — rechazo: `ck_obra_estado` frena un estado que el dominio no conoce."""
    antes = _fila_obligatoria(lector, obra_conocida)

    with pytest.raises(DBAPIError) as info, sesion_bd.begin():
        cambiar_estado_obra(sesion_bd, obra_conocida, "BORRADA", AHORA, datos_presupuesto.usuario())

    assert _sqlstate(info.value) == "23514"
    assert _restriccion(info.value) == "ck_obra_estado"
    assert _fila_obligatoria(lector, obra_conocida) == antes
