"""Concurrencia del mantenimiento y del ciclo de vida de la obra, fila A9 de TKT-012b (TC-55 a TC-60).

Todo el mantenimiento de la obra se serializa con un `SELECT ... FOR UPDATE` sobre la fila de `obra` que
toma cada caso de uso antes de leer el estado o contar el historial (el mismo orden que el congelado de
TKT-017: obra y después línea base). Estas pruebas demuestran que ese bloqueo es real y no decorativo:
sin él, una edición escribiría sobre una obra ya cerrada, dos suspensiones pasarían las dos y un borrado
podría llevarse una obra cuya línea base se congela en ese mismo instante (RN-01, invariante 14).

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` y el rol de aplicación. Ninguna
espera es un `sleep` fijo y ninguna prueba depende del orden entre pruebas:

- **En cola.** Una conexión propia retiene `SELECT ... FOR UPDATE` sobre la obra. Se lanzan las operaciones
  de una en una y, tras cada lanzamiento, la prueba espera mirando `pg_stat_activity` y `pg_blocking_pids`
  a que esa operación quede detenida en el bloqueo. Al soltar el bloqueo, PostgreSQL las despierta en el
  orden en que se formaron, de modo que el orden de llegada es un dato de la prueba y las dos órdenes
  posibles se prueban por separado, con su resultado exacto.
- **Pausa.** Para que una operación esté *dentro* de su transacción mientras otra intenta entrar, la prueba
  envuelve un paso del repositorio y pausa el hilo `A` con un `threading.Event`; si nadie lo libera en
  `LIMITE_DE_HILO` segundos, falla en vez de colgarse.
- **Carrera libre.** `threading.Barrier` suelta las operaciones a la vez, varias corridas seguidas. Como
  quién gana depende del planificador, afirma solo lo que vale gane quien gane (el estado final coherente,
  cada ganadora con su asiento, ninguna perdedora con otra cosa que un rechazo del contrato).

«Ninguna `500`» se comprueba en el caso de uso como «todo fallo es un `ErrorContrato` de estado `409`» y,
por HTTP, con el código de la respuesta. Un `DBAPIError` o cualquier otra excepción que escape sería la
`500` del manejador global.

Mutantes que esta fila pone en rojo (A9 los corre contra la suite acumulada): leer el estado antes del
`FOR UPDATE` en las transiciones (`..._ca13_*`, `TC-39`) o en `actualizar_obra` (`..._ca4_*`); quitar el
`FOR UPDATE` de `bloquear_obra_completa` (todas las pruebas «en cola»); borrar antes de contar el
historial (`..._ca7_*`); que el borrado de la obra con una escritura ajena en curso deje pasar el `DELETE`.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`, `cliente_espera_corta`) se piden como
# parámetro: Ruff lo lee como F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`.
# ruff: noqa: F811

from __future__ import annotations

import functools
import threading
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from cimenta.presupuesto.aplicacion.ciclo_vida_obra import (
    cerrar_obra,
    reactivar_obra,
    suspender_obra,
)
from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from cimenta.presupuesto.aplicacion.mantenimiento_obras import actualizar_obra, eliminar_obra
from cimenta.presupuesto.infraestructura import repositorio_obra
from contrato_error.excepciones import ConcurrenciaVencida, ConflictoEstado, ErrorContrato
from herramientas.soporte_tkt017_api import (
    CONTRASENA_DE_PRUEBA,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    cabeceras_de,
    cliente_espera_corta,  # noqa: F401
    exigir_error,
    iniciar_sesion,
)
from herramientas.soporte_tkt017_entorno import (
    LIMITE_DE_HILO,
    Base,
    Contexto,
    Entorno,
    Hilo,
    congelar,
)
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba, SembrarUsuario

CORRELACION = "corr-tkt012b-a9"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
CODIGO = "AP-058-25"
NOMBRE_INICIAL = f"Obra {CODIGO}"
NOMBRE_NUEVO = "Nombre corregido durante la carrera"
MOTIVO = "Decisión de la dirección por falta de anticipo"
MOTIVO_DE_CONGELADO = "Firma de contrato 2026-11-04"
CORRIDAS = 6

MENSAJE_ESTADO = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_CON_HISTORIAL = "La obra {codigo} tiene historial y no se puede eliminar."
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)

# Operación del dominio -> (clave de la acción, segmento de la ruta), y qué admite cada estado (D-2).
ACCION_DE_OPERACION = {
    "SUSPENDER": ("SUSPENDER_OBRA", "suspension"),
    "REACTIVAR": ("REACTIVAR_OBRA", "reactivacion"),
    "CERRAR": ("CERRAR_OBRA", "cierre"),
}
ADMITIDAS_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR",),
    "ACTIVA": ("SUSPENDER", "CERRAR"),
    "SUSPENDIDA": ("REACTIVAR", "CERRAR"),
    "CERRADA": (),
}
# Las acciones del `409` `OBRA_CON_HISTORIAL` son solo las dos que el borrador declara.
CON_HISTORIAL_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR",),
    "ACTIVA": ("SUSPENDER", "CERRAR"),
    "SUSPENDIDA": ("CERRAR",),
    "CERRADA": (),
}

Operacion = Callable[[], object]


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto real del rol de aplicación (con sus 5 s de `lock_timeout`), construido al primer uso."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def contexto_espera_corta(motor_espera_corta: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El mismo contexto sobre `motor_espera_corta`: la sesión espera un bloqueo solo 200 ms."""
    return functools.cache(
        lambda: construir_contexto(
            proveedor_motor=lambda: motor_espera_corta, reloj=reloj_de_prueba
        )
    )


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`)."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def usuario(datos_presupuesto: DatosPresupuesto) -> uuid.UUID:
    return datos_presupuesto.usuario()


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID, usuario: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra en el estado pedido, con tres porcentajes distintos (un cruce de columnas se nota)."""
    contador = iter(range(1, 1000))

    def fabricar(*, codigo: str | None = None, estado: str = "ACTIVA") -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo if codigo is not None else f"AP-{next(contador):03d}-26",
            empresa_id=empresa_de_la_migracion,
            creado_por_id=usuario,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=Decimal("0.100000"),
            iva_acreditable=True,
        )

    return fabricar


@pytest.fixture
def entorno(datos_presupuesto: DatosPresupuesto, base: Base) -> Entorno:
    """La obra `AP-058-25` en planeación, los cuatro tipos sembrados, el director y la mano de obra."""
    entorno = Entorno(datos_presupuesto, base)
    entorno.registrar_mano_obra()
    return entorno


# --------------------------------------------------------------------------- ayudas de sincronización


def _esperando(base: Base, patron: str) -> int:
    """Cuántas sesiones de la base están detenidas por un bloqueo con una consulta como `patron`."""
    fila = base.conexion.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
        (patron,),
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def _esperando_la_obra(base: Base) -> int:
    """Cuántas sesiones esperan un `SELECT ... FROM obra ... FOR UPDATE`."""
    return _esperando(base, "%FROM obra%FOR UPDATE%")


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _hay_esperando_exactamente(base: Base, cantidad: int) -> bool:
    """La condición de `esperar_hasta`: exactamente `cantidad` sesiones esperan el `FOR UPDATE` de la obra."""
    return _esperando_la_obra(base) == cantidad


def _hay_esperando_con(base: Base, patron: str, cantidad: int) -> bool:
    return _esperando(base, patron) == cantidad


def _correr_en_cola(
    base: Base,
    retenedor: psycopg.Connection[tuple[Any, ...]],
    obra_id: uuid.UUID,
    operaciones: Sequence[tuple[str, Operacion]],
) -> list[Hilo[object]]:
    """Lanza `operaciones` de una en una contra una obra retenida y las suelta en el orden de llegada.

    Cada operación se lanza solo cuando la anterior ya está detenida en el `FOR UPDATE` de la obra
    (`pg_blocking_pids`); la prueba falla con el error del hilo si alguna no llega a detenerse. Al soltar
    el bloqueo, PostgreSQL despierta a las esperas en el orden en que se formaron.
    """
    hilos: list[Hilo[object]] = []
    retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (obra_id,))
    try:
        for indice, (nombre, funcion) in enumerate(operaciones, start=1):
            hilo: Hilo[object] = Hilo(nombre, funcion)
            hilos.append(hilo)
            hilo.start()
            esperando = esperar_hasta(
                functools.partial(_hay_esperando_exactamente, base, indice), LIMITE_DE_HILO
            )
            assert esperando, (
                f"{nombre} no quedó esperando el bloqueo de la obra (posición {indice}): "
                f"{hilo.error!r}"
            )
    finally:
        retenedor.rollback()
        for hilo in hilos:
            hilo.terminar()
    return hilos


def _carrera_libre(operaciones: Sequence[tuple[str, Operacion]]) -> list[Hilo[object]]:
    """Suelta las operaciones a la vez con una barrera y espera a que terminen."""
    salida = threading.Barrier(len(operaciones), timeout=LIMITE_DE_HILO)

    def con_barrera(funcion: Operacion) -> Operacion:
        def correr() -> object:
            salida.wait()
            return funcion()

        return correr

    hilos = [Hilo(nombre, con_barrera(funcion)) for nombre, funcion in operaciones]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.terminar()
    return hilos


def _exigir_rechazo_del_contrato(hilo: Hilo[object]) -> ConflictoEstado:
    """El hilo perdió con un `409` `CONFLICTO` del contrato: ni una excepción cruda ni otro tipo (`500`)."""
    error = hilo.error
    assert isinstance(error, ConflictoEstado), (
        f"{hilo.name} debió perder con un 409 del contrato y dio {error!r}"
    )
    assert error.estado_http == 409
    return error


def _exigir_sin_500(hilos: Sequence[Hilo[object]]) -> None:
    """Todo fallo de la carrera es un `ErrorContrato` de estado `409`: nunca una excepción cruda."""
    for hilo in hilos:
        error = hilo.error
        if error is not None:
            assert isinstance(error, ErrorContrato), f"{hilo.name} dio un 500: {error!r}"
            assert error.estado_http == 409, f"{hilo.name} dio {error.estado_http}"


# --------------------------------------------------------------------------- ayudas de contenido


def _estado(base: Base, obra_id: uuid.UUID) -> str:
    filas = base.filas("SELECT estado FROM obra WHERE id = %s", obra_id)
    assert len(filas) == 1, f"La obra {obra_id} no existe"
    return str(filas[0][0])


def _nombre(base: Base, obra_id: uuid.UUID) -> str:
    return str(base.filas("SELECT nombre FROM obra WHERE id = %s", obra_id)[0][0])


def _transiciones(base: Base, obra_id: uuid.UUID) -> list[tuple[str, str, str]]:
    """Los asientos de transición de la obra, `(verbo, antes, después)`, sin depender del orden de tiempo.

    El reloj de la prueba es fijo: dos asientos de la misma obra comparten `ocurrido_en`, así que el
    orden de llegada no se lee de la bitácora sino de los estados que cada asiento declara.
    """
    filas = base.filas(
        "SELECT accion::text, datos_antes, datos_despues FROM bitacora "
        "WHERE entidad_id = %s AND accion IN ('SUSPENDER', 'REACTIVAR', 'CERRAR')",
        obra_id,
    )
    return sorted((fila[0], fila[1]["estado"], fila[2]["estado"]) for fila in filas)


def _verbos(base: Base, obra_id: uuid.UUID) -> list[str]:
    return sorted(
        str(fila[0])
        for fila in base.filas(
            "SELECT accion::text FROM bitacora WHERE obra_id = %s AND accion <> 'DENEGAR'",
            obra_id,
        )
    )


def _acciones(obra_id: uuid.UUID, operaciones: tuple[str, ...]) -> list[dict[str, str]]:
    return [
        {
            "clave": ACCION_DE_OPERACION[operacion][0],
            "metodo": "POST",
            "ruta": f"/api/v1/obras/{obra_id}/{ACCION_DE_OPERACION[operacion][1]}",
        }
        for operacion in operaciones
    ]


def _cuerpo_estado_no_permite(
    obra_id: uuid.UUID, codigo: str, estado: str, *, con_operaciones: bool
) -> dict[str, object]:
    """El `409` `ESTADO_NO_PERMITE_OPERACION` completo que ve un Director de Proyectos."""
    admitidas = ADMITIDAS_POR_ESTADO[estado]
    return {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_ESTADO.format(codigo=codigo, estado=estado),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": (
            {"estado": estado, "operaciones_admitidas": list(admitidas)}
            if con_operaciones
            else {"estado": estado}
        ),
        "acciones": _acciones(obra_id, admitidas) if con_operaciones else [],
        "correlacion_id": CORRELACION,
    }


def _detalle_de_historial(
    *, congelada: bool = False, lineas_base: int = 0, importaciones: int = 0, movimientos: int = 0
) -> dict[str, object]:
    return {
        "linea_base_congelada": congelada,
        "lineas_base": lineas_base,
        "importaciones": importaciones,
        "movimientos": movimientos,
    }


def _cuerpo_con_historial(
    obra_id: uuid.UUID, codigo: str, estado: str, detalle: dict[str, object]
) -> dict[str, object]:
    """El `409` `OBRA_CON_HISTORIAL` completo, con las acciones que el estado admite."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_CON_HISTORIAL.format(codigo=codigo),
        "codigo": "OBRA_CON_HISTORIAL",
        "detalle": detalle,
        "acciones": _acciones(obra_id, CON_HISTORIAL_POR_ESTADO[estado]),
        "correlacion_id": CORRELACION,
    }


def _obra_con_borrador(
    entorno: Entorno, contexto: Contexto, indice: int
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Una obra en `PLANEACION` con su línea base `BORRADOR` materializada por la interfaz real.

    La de `indice` 0 es la obra del entorno; las demás se crean con su propio código, para repetir la
    carrera sin que una corrida contamine a la siguiente.
    """
    if indice == 0:
        obra_id, codigo = entorno.obra_id, CODIGO
    else:
        codigo = f"AP-9{indice:02d}-26"
        obra_id = entorno.datos.obra(codigo=codigo, creado_por_id=entorno.usuario_id)
    importacion = entorno.importar(obra_id=obra_id)
    borrador = entorno.confirmar(contexto, importacion_id=importacion)
    return obra_id, borrador.linea_base_id, codigo


# --------------------------------------------------------------------------- TC-55 · CA-7 · CA-R4


@pytest.mark.parametrize("primero", ["congelar", "eliminar"])
def test_tkt012b_ca7_congelado_y_borrado_en_cola_el_congelado_gana(
    primero: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-55 · CA-7 · CA-R4 · RN-01 — con el borrado y el congelado en cola sobre la obra, el congelado gana.

    Una obra en `PLANEACION` con una línea base `BORRADOR` materializada (con su importación y su
    jerarquía). Los dos llegan al `FOR UPDATE` de la obra y se despiertan en el orden de llegada; se
    prueban los dos órdenes. Gane quien gane el bloqueo, el congelado termina y el borrado responde `409`
    `OBRA_CON_HISTORIAL` (una línea base `BORRADOR` ya es historial, D-DIS-3): si el borrado entra
    primero, ve un `BORRADOR` y nada se borra; si entra después, ve la `CONGELADA` y el detalle lo dice
    (`linea_base_congelada`). Nunca queda una `CONGELADA` sin obra, la obra pasa a `ACTIVA` y no se
    asienta ningún `ELIMINAR`.
    """
    obra_id, linea_base_id, codigo = _obra_con_borrador(entorno, contexto, 0)
    ctx = contexto()
    operaciones: dict[str, tuple[str, Operacion]] = {
        "congelar": (
            "congelar",
            functools.partial(congelar, ctx, linea_base_id, usuario_id=entorno.usuario_id),
        ),
        "eliminar": (
            "eliminar",
            functools.partial(eliminar_obra, ctx, obra_id, entorno.usuario_id),
        ),
    }
    orden = [operaciones[primero]] + [op for nombre, op in operaciones.items() if nombre != primero]
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)

    hilos = _correr_en_cola(base, retenedor, obra_id, orden)

    por_nombre = {hilo.name: hilo for hilo in hilos}
    assert por_nombre["congelar"].error is None, por_nombre["congelar"].error
    rechazo = _exigir_rechazo_del_contrato(por_nombre["eliminar"])
    detalle = _detalle_de_historial(congelada=primero == "congelar", lineas_base=1, importaciones=1)
    assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id, codigo, "ACTIVA" if primero == "congelar" else "PLANEACION", detalle
    ), (
        "El detalle y las acciones cuentan lo que el borrado vio: la obra PLANEACION con un BORRADOR si entró primero; ACTIVA con la CONGELADA si entró después"
    )
    assert base.filas("SELECT id, estado, obra_id FROM linea_base") == [
        (linea_base_id, "CONGELADA", obra_id)
    ], "Una sola línea base, congelada y con su obra"
    assert _estado(base, obra_id) == "ACTIVA"
    assert (
        _cuenta(
            base,
            "SELECT count(*) FROM linea_base l WHERE l.estado = 'CONGELADA' "
            "AND NOT EXISTS (SELECT 1 FROM obra o WHERE o.id = l.obra_id)",
        )
        == 0
    ), "Nunca queda una CONGELADA sin obra"
    assert _verbos(base, obra_id) == ["CONFIRMAR", "CONGELAR"], "El borrado rechazado no asienta"
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0


def test_tkt012b_ca7_congelado_y_borrado_simultaneos_en_varias_corridas(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-55 · CA-7 · CA-R4 · RN-01 — soltados a la vez, en cada corrida gana el congelado y nada responde `500`.

    `CORRIDAS` obras distintas, cada una con su `BORRADOR` materializado; el borrado y el congelado de cada
    una se sueltan con una barrera. En todas: el congelado termina bien, el borrado responde `409`
    `OBRA_CON_HISTORIAL` con el contrato completo (el detalle y las acciones dependen de quién entró
    primero —`PLANEACION` y un `BORRADOR`, o `ACTIVA` y la `CONGELADA`—, así que se fijan los dos
    resultados posibles y se exige que sean coherentes entre sí), la línea base queda `CONGELADA` con su obra y el único
    asiento de la carrera es el `CONGELAR`.
    """
    ctx = contexto()
    for indice in range(CORRIDAS):
        obra_id, linea_base_id, codigo = _obra_con_borrador(entorno, contexto, indice)

        hilos = _carrera_libre(
            [
                (
                    "congelar",
                    functools.partial(congelar, ctx, linea_base_id, usuario_id=entorno.usuario_id),
                ),
                (
                    "eliminar",
                    functools.partial(eliminar_obra, ctx, obra_id, entorno.usuario_id),
                ),
            ]
        )

        por_nombre = {hilo.name: hilo for hilo in hilos}
        assert por_nombre["congelar"].error is None, (indice, por_nombre["congelar"].error)
        rechazo = _exigir_rechazo_del_contrato(por_nombre["eliminar"])
        cuerpo = rechazo.cuerpo(ROLES_DP, CORRELACION)
        congelada_vista = bool(cuerpo["detalle"]["linea_base_congelada"])  # type: ignore[index]
        assert cuerpo == _cuerpo_con_historial(
            obra_id,
            codigo,
            "ACTIVA" if congelada_vista else "PLANEACION",
            _detalle_de_historial(congelada=congelada_vista, lineas_base=1, importaciones=1),
        ), (indice, cuerpo)
        assert base.filas("SELECT estado, obra_id FROM linea_base WHERE obra_id = %s", obra_id) == [
            ("CONGELADA", obra_id)
        ], indice
        assert _estado(base, obra_id) == "ACTIVA", indice
        assert _verbos(base, obra_id) == ["CONFIRMAR", "CONGELAR"], indice
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE estado = 'ACTIVA'") == CORRIDAS


@pytest.mark.parametrize("primero", ["congelar", "eliminar"])
def test_tkt012b_ca7_http_congelado_y_borrado_en_cola_no_responden_500(
    primero: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-55 · CA-7 · CA-R4 · RN-01 — por HTTP, `DELETE` y `POST …/congelacion` en cola: `200` y `409`.

    Lo mismo que el caso de uso, por la aplicación real (`crear_aplicacion`) y un `TestClient`: el congelado
    responde `200` con la línea base `CONGELADA`; el borrado, el `409` `CONFLICTO` `OBRA_CON_HISTORIAL`
    completo y válido contra el esquema del borrador, con las acciones del estado que vio (`CERRAR_OBRA`
    si la obra seguía en `PLANEACION`; `SUSPENDER_OBRA` y `CERRAR_OBRA` si el congelado ya la activó).
    Ninguna responde `500`.
    """
    obra_id, linea_base_id, codigo = _obra_con_borrador(entorno, contexto, 0)
    director = abrir_sesion()
    cabeceras = cabeceras_de(director.sesion_id, TOKEN_CSRF, TOKEN_CSRF)
    respuestas: dict[str, Any] = {}

    def llamar_congelar() -> object:
        respuestas["congelar"] = cliente.post(
            f"/api/v1/lineas-base/{linea_base_id}/congelacion",
            json={"motivo": MOTIVO_DE_CONGELADO},
            headers=cabeceras,
        )
        return respuestas["congelar"]

    def llamar_eliminar() -> object:
        respuestas["eliminar"] = cliente.delete(f"/api/v1/obras/{obra_id}", headers=cabeceras)
        return respuestas["eliminar"]

    operaciones: dict[str, tuple[str, Operacion]] = {
        "congelar": ("congelar", llamar_congelar),
        "eliminar": ("eliminar", llamar_eliminar),
    }
    orden = [operaciones[primero]] + [op for nombre, op in operaciones.items() if nombre != primero]
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)

    hilos = _correr_en_cola(base, retenedor, obra_id, orden)

    assert all(hilo.error is None for hilo in hilos), [hilo.error for hilo in hilos]
    assert respuestas["congelar"].status_code == 200, respuestas["congelar"].text
    assert respuestas["congelar"].json()["estado"] == "CONGELADA"
    cuerpo = exigir_error(
        respuestas["eliminar"],
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "OBRA_CON_HISTORIAL",
            "mensaje": MENSAJE_CON_HISTORIAL.format(codigo=codigo),
            "detalle": _detalle_de_historial(
                congelada=primero == "congelar", lineas_base=1, importaciones=1
            ),
            "acciones": _acciones(
                obra_id,
                CON_HISTORIAL_POR_ESTADO["ACTIVA" if primero == "congelar" else "PLANEACION"],
            ),
        },
        esquema="ErrorConflictoEstado",
    )
    assert "regla" not in cuerpo
    assert _estado(base, obra_id) == "ACTIVA"
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0


# --------------------------------------------------------------------------- TC-56 · CA-7


def _insertar_hija(
    conexion: psycopg.Connection[tuple[Any, ...]],
    tipo: str,
    *,
    obra_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    usuario_id: uuid.UUID,
    ahora: Any,
) -> None:
    """La escritura de otro módulo que cuelga de la obra: `requisicion` o `importacion`, por SQL.

    `importacion` es el `INSERT` que hará `crear_importacion` (TKT-018): hoy ese caso de uso no existe en
    el código, así que no hay ruta real que llamar y la sentencia es exactamente la suya.
    """
    if tipo == "requisicion":
        conexion.execute(
            "INSERT INTO requisicion (id, obra_id, tipo_partida_id, solicitante_id, estado, "
            "importe_solicitado, creado_en, actualizado_en) "
            "VALUES (%s, %s, %s, %s, 'BORRADOR', %s, %s, %s)",
            (
                uuid.uuid4(),
                obra_id,
                tipo_partida_id,
                usuario_id,
                Decimal("1000.0000"),
                ahora,
                ahora,
            ),
        )
    else:
        conexion.execute(
            "INSERT INTO importacion (id, obra_id, archivo_id, estado, importado_por_id) "
            "VALUES (%s, %s, %s, 'RECIBIDO', %s)",
            (uuid.uuid4(), obra_id, uuid.uuid4(), usuario_id),
        )


def _hijas(base: Base, tipo: str, obra_id: uuid.UUID) -> int:
    tabla = "requisicion" if tipo == "requisicion" else "importacion"
    return _cuenta(base, f"SELECT count(*) FROM {tabla} WHERE obra_id = %s", obra_id)  # type: ignore[arg-type]


HIJAS = ["requisicion", "importacion"]


@pytest.mark.parametrize("tipo", HIJAS)
def test_tkt012b_ca7_escritura_ajena_en_curso_el_borrado_espera_y_responde_409(
    tipo: str,
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-56 · CA-7 · RN-01 — si la escritura ajena entra primero, el borrado espera y responde `409`.

    Una obra `PLANEACION` sin historial. Una conexión inserta la fila hija (requisición o importación) y
    todavía no confirma: ese `INSERT` toma `FOR KEY SHARE` sobre la fila de la obra. `eliminar_obra`
    queda detenido en su `SELECT ... FOR UPDATE` (`pg_blocking_pids`). Al confirmar la escritura, el
    borrado despierta y **no** borra: la requisición no la cuenta nadie (ninguna fuente inyectada), así
    que el `DELETE` choca con la clave foránea (`23001`) y se traduce a `OBRA_CON_HISTORIAL` con el
    detalle del contrato (`movimientos` 1: al menos una fila de otro módulo) y **sin** el nombre de la
    restricción (CWE-209, ciclo de corrección 2); la importación sí la cuenta el historial propio. La obra
    y la fila hija siguen y no se asienta `ELIMINAR`.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="PLANEACION")
    tipo_partida_id = datos_presupuesto.tipo_partida()
    escritor = conectar("aplicacion", base_de_prueba, autocommit=False)
    _insertar_hija(
        escritor,
        tipo,
        obra_id=obra_id,
        tipo_partida_id=tipo_partida_id,
        usuario_id=usuario,
        ahora=reloj_de_prueba(),
    )
    ctx = contexto()
    borrado: Hilo[object] = Hilo(
        "eliminar", functools.partial(eliminar_obra, ctx, obra_id, usuario)
    )
    try:
        borrado.start()
        esperando = esperar_hasta(
            functools.partial(_hay_esperando_exactamente, base, 1), LIMITE_DE_HILO
        )
        assert esperando, f"El borrado no esperó a la escritura ajena: {borrado.error!r}"
        assert borrado.is_alive()
    finally:
        escritor.commit()
        borrado.terminar()

    rechazo = _exigir_rechazo_del_contrato(borrado)
    detalle: dict[str, object] = (
        _detalle_de_historial(movimientos=1)
        if tipo == "requisicion"
        else _detalle_de_historial(importaciones=1)
    )
    assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id, CODIGO, "PLANEACION", detalle
    )
    assert "fk_" not in repr(rechazo.cuerpo(ROLES_DP, CORRELACION)), (
        "El nombre de la restricción no sale"
    )
    assert _estado(base, obra_id) == "PLANEACION"
    assert _hijas(base, tipo, obra_id) == 1, "La escritura ajena ganó y se conserva"
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0


@pytest.mark.parametrize("tipo", HIJAS)
def test_tkt012b_ca7_borrado_en_curso_la_escritura_ajena_falla_por_clave_foranea(
    tipo: str,
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-56 · CA-7 · R-9 · RN-01 — si el borrado entra primero, la escritura ajena falla con `23503`.

    `eliminar_obra` se pausa con la fila ya borrada y sin confirmar. La escritura ajena (requisición o
    importación) queda detenida en su `INSERT` (`pg_blocking_pids`) porque la fila de la obra la tiene un
    `DELETE` pendiente. Al confirmar el borrado, el `INSERT` falla con `ForeignKeyViolation` (`23503`) de
    su propia clave foránea: es el fallo de **quien escribe**, no una `500` de este ticket. La obra no
    existe, no queda fila hija y el asiento `ELIMINAR` conserva el código y el nombre.

    R-9 (`crear_importacion`, TKT-018, aún sin código): quien lo implemente debe traducir este `23503` a
    `404` `NO_ENCONTRADO`, o la ruta responderá `500` si pierde esta carrera.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="PLANEACION")
    tipo_partida_id = datos_presupuesto.tipo_partida()
    ctx = contexto()
    original = repositorio_obra.eliminar_obra
    dentro, liberar = threading.Event(), threading.Event()

    def eliminar_y_pausar(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "eliminar":
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo del borrado nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_obra, "eliminar_obra", eliminar_y_pausar)
    escritor_conexion = conectar("aplicacion", base_de_prueba)
    borrado: Hilo[object] = Hilo(
        "eliminar", functools.partial(eliminar_obra, ctx, obra_id, usuario)
    )
    escritura: Hilo[object] = Hilo(
        "escritura",
        functools.partial(
            _insertar_hija,
            escritor_conexion,
            tipo,
            obra_id=obra_id,
            tipo_partida_id=tipo_partida_id,
            usuario_id=usuario,
            ahora=reloj_de_prueba(),
        ),
    )
    patron = f"%INSERT INTO {'requisicion' if tipo == 'requisicion' else 'importacion'}%"
    try:
        borrado.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), (
            f"El borrado no llegó al DELETE: {borrado.error!r}"
        )
        escritura.start()
        esperando = esperar_hasta(
            functools.partial(_hay_esperando_con, base, patron, 1), LIMITE_DE_HILO
        )
        assert esperando, f"La escritura ajena no quedó esperando al borrado: {escritura.error!r}"
        assert escritura.is_alive()
    finally:
        liberar.set()
        borrado.terminar()
        escritura.terminar()

    assert borrado.error is None, borrado.error
    error = escritura.error
    assert isinstance(error, psycopg.errors.ForeignKeyViolation), (
        f"La escritura debía fallar con 23503 y dio {error!r}"
    )
    assert error.sqlstate == "23503"
    assert error.diag.constraint_name == (
        "fk_requisicion_obra_id" if tipo == "requisicion" else "fk_importacion_obra_id"
    )
    assert base.filas("SELECT id FROM obra WHERE id = %s", obra_id) == []
    assert _hijas(base, tipo, obra_id) == 0
    asientos = base.filas(
        "SELECT accion::text, datos_antes ->> 'codigo', datos_antes ->> 'nombre' FROM bitacora "
        "WHERE entidad_id = %s",
        obra_id,
    )
    assert asientos == [("ELIMINAR", CODIGO, NOMBRE_INICIAL)]


@pytest.mark.parametrize("tipo", HIJAS)
def test_tkt012b_ca7_borrado_y_escritura_ajena_simultaneos_gana_una_sola(
    tipo: str,
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-56 · CA-7 · RN-01 — soltados a la vez, gana exactamente una: o la escritura o el borrado.

    `CORRIDAS` obras sin historial; en cada una, el borrado y el `INSERT` de la fila hija se sueltan con
    una barrera. O gana la escritura (la fila hija existe y el borrado responde `409` `OBRA_CON_HISTORIAL`,
    con la obra intacta y sin asiento) o gana el borrado (la obra no existe, la escritura falla con
    `ForeignKeyViolation` y el asiento `ELIMINAR` está). Nunca las dos, nunca ninguna, nunca otro error.
    """
    ctx = contexto()
    tipo_partida_id = datos_presupuesto.tipo_partida()
    ganadas_por_la_escritura = ganadas_por_el_borrado = 0
    for indice in range(CORRIDAS):
        obra_id = fabricar_obra(codigo=f"AP-8{indice:02d}-26", estado="PLANEACION")
        conexion = conectar("aplicacion", base_de_prueba)

        hilos = _carrera_libre(
            [
                ("eliminar", functools.partial(eliminar_obra, ctx, obra_id, usuario)),
                (
                    "escritura",
                    functools.partial(
                        _insertar_hija,
                        conexion,
                        tipo,
                        obra_id=obra_id,
                        tipo_partida_id=tipo_partida_id,
                        usuario_id=usuario,
                        ahora=reloj_de_prueba(),
                    ),
                ),
            ]
        )

        por_nombre = {hilo.name: hilo for hilo in hilos}
        borrado, escritura = por_nombre["eliminar"], por_nombre["escritura"]
        existe = base.filas("SELECT id FROM obra WHERE id = %s", obra_id) != []
        if borrado.error is None:
            ganadas_por_el_borrado += 1
            assert not existe, indice
            assert isinstance(escritura.error, psycopg.errors.ForeignKeyViolation), (
                indice,
                escritura.error,
            )
            assert _hijas(base, tipo, obra_id) == 0, indice
            assert (
                _cuenta(
                    base,
                    "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR' AND entidad_id = %s",
                    obra_id,
                )
                == 1
            ), indice
        else:
            ganadas_por_la_escritura += 1
            rechazo = _exigir_rechazo_del_contrato(borrado)
            assert rechazo.codigo == "OBRA_CON_HISTORIAL", (indice, rechazo)
            assert escritura.error is None, (indice, escritura.error)
            assert existe, indice
            assert _hijas(base, tipo, obra_id) == 1, indice
            assert (
                _cuenta(
                    base,
                    "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR' AND entidad_id = %s",
                    obra_id,
                )
                == 0
            ), indice
    assert ganadas_por_la_escritura + ganadas_por_el_borrado == CORRIDAS


# --------------------------------------------------------------------------- TC-57 · CA-13


@pytest.mark.parametrize("primera", ["suspension", "cierre"])
def test_tkt012b_ca13_suspension_y_cierre_en_cola_el_resultado_es_coherente(
    primera: str,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-57 · CA-13 · D-2 — suspender y cerrar una obra `ACTIVA` en cola: los dos órdenes, con su asiento.

    Las dos transiciones llegan al `FOR UPDATE` de la obra y se despiertan en el orden de llegada.

    - **Suspensión primero:** la obra pasa `ACTIVA → SUSPENDIDA` y después `SUSPENDIDA → CERRADA` (admitida
      desde `SUSPENDIDA`): dos asientos, cada uno con el estado que vio.
    - **Cierre primero:** la obra pasa `ACTIVA → CERRADA` y la suspensión se evalúa contra `CERRADA`: `409`
      `ESTADO_NO_PERMITE_OPERACION` con el estado nuevo, sin operaciones ni acciones; un solo asiento.

    En los dos la obra termina `CERRADA` y nadie responde `500`.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    ctx = contexto()
    operaciones: dict[str, tuple[str, Operacion]] = {
        "suspension": (
            "suspension",
            functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario),
        ),
        "cierre": ("cierre", functools.partial(cerrar_obra, ctx, obra_id, MOTIVO, usuario)),
    }
    orden = [operaciones[primera]] + [op for nombre, op in operaciones.items() if nombre != primera]
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)

    hilos = _correr_en_cola(base, retenedor, obra_id, orden)

    por_nombre = {hilo.name: hilo for hilo in hilos}
    assert _estado(base, obra_id) == "CERRADA"
    if primera == "suspension":
        assert all(hilo.error is None for hilo in hilos), [hilo.error for hilo in hilos]
        assert _transiciones(base, obra_id) == [
            ("CERRAR", "SUSPENDIDA", "CERRADA"),
            ("SUSPENDER", "ACTIVA", "SUSPENDIDA"),
        ]
    else:
        assert por_nombre["cierre"].error is None, por_nombre["cierre"].error
        rechazo = _exigir_rechazo_del_contrato(por_nombre["suspension"])
        assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_estado_no_permite(
            obra_id, CODIGO, "CERRADA", con_operaciones=True
        )
        assert _transiciones(base, obra_id) == [("CERRAR", "ACTIVA", "CERRADA")], (
            "La suspensión rechazada no asienta"
        )


def test_tkt012b_ca13_suspension_y_cierre_simultaneos_en_varias_corridas(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
) -> None:
    """TC-57 · CA-13 · D-2 — soltadas a la vez, `CORRIDAS` veces: estado final coherente y cada ganadora con asiento.

    En cada obra `ACTIVA`, suspender y cerrar se sueltan con una barrera. Gane quien gane el bloqueo, la
    obra termina `CERRADA`; el cierre siempre gana (o es el último), así que siempre tiene su asiento; la
    suspensión o tiene el suyo (y entonces el cierre vio `SUSPENDIDA`) o respondió `409` con el estado
    `CERRADA` (y entonces el cierre vio `ACTIVA`). Nadie responde `500`.
    """
    ctx = contexto()
    for indice in range(CORRIDAS):
        obra_id = fabricar_obra(codigo=f"AP-7{indice:02d}-26", estado="ACTIVA")

        hilos = _carrera_libre(
            [
                ("suspension", functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario)),
                ("cierre", functools.partial(cerrar_obra, ctx, obra_id, MOTIVO, usuario)),
            ]
        )

        _exigir_sin_500(hilos)
        por_nombre = {hilo.name: hilo for hilo in hilos}
        assert por_nombre["cierre"].error is None, (indice, por_nombre["cierre"].error)
        assert _estado(base, obra_id) == "CERRADA", indice
        if por_nombre["suspension"].error is None:
            assert _transiciones(base, obra_id) == [
                ("CERRAR", "SUSPENDIDA", "CERRADA"),
                ("SUSPENDER", "ACTIVA", "SUSPENDIDA"),
            ], indice
        else:
            rechazo = _exigir_rechazo_del_contrato(por_nombre["suspension"])
            assert rechazo.codigo == "ESTADO_NO_PERMITE_OPERACION", indice
            assert rechazo.detalle == {"estado": "CERRADA", "operaciones_admitidas": []}, indice
            assert _transiciones(base, obra_id) == [("CERRAR", "ACTIVA", "CERRADA")], indice


# --------------------------------------------------------------------------- TC-58 · CA-13


def test_tkt012b_ca13_dos_suspensiones_en_cola_una_gana_y_la_otra_responde_409(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-58 · CA-13 · D-2 — dos suspensiones de una obra `ACTIVA` en cola: una `200` y la otra `409`.

    La primera en el bloqueo suspende; la segunda, ya con el bloqueo, lee `SUSPENDIDA` y se rechaza con el
    contrato completo: `ESTADO_NO_PERMITE_OPERACION`, el estado nuevo, las operaciones que sí admite
    (`REACTIVAR`, `CERRAR`) y sus acciones. Un solo asiento `SUSPENDER`. Sin el `FOR UPDATE` antes de
    leer el estado, las dos verían `ACTIVA` y asentarían las dos.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    ctx = contexto()
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)

    hilos = _correr_en_cola(
        base,
        retenedor,
        obra_id,
        [
            ("primera", functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario)),
            ("segunda", functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario)),
        ],
    )

    por_nombre = {hilo.name: hilo for hilo in hilos}
    assert por_nombre["primera"].error is None, por_nombre["primera"].error
    rechazo = _exigir_rechazo_del_contrato(por_nombre["segunda"])
    assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_estado_no_permite(
        obra_id, CODIGO, "SUSPENDIDA", con_operaciones=True
    )
    assert _estado(base, obra_id) == "SUSPENDIDA"
    assert _transiciones(base, obra_id) == [("SUSPENDER", "ACTIVA", "SUSPENDIDA")]


def test_tkt012b_ca13_dos_suspensiones_simultaneas_en_varias_corridas(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
) -> None:
    """TC-58 · CA-13 · D-2 — soltadas a la vez, `CORRIDAS` veces: exactamente una `200` y una `409`, un solo asiento."""
    ctx = contexto()
    for indice in range(CORRIDAS):
        obra_id = fabricar_obra(codigo=f"AP-6{indice:02d}-26", estado="ACTIVA")

        hilos = _carrera_libre(
            [
                ("a", functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario)),
                ("b", functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario)),
            ]
        )

        ganadoras = [hilo for hilo in hilos if hilo.error is None]
        perdedoras = [hilo for hilo in hilos if hilo.error is not None]
        assert len(ganadoras) == 1 and len(perdedoras) == 1, (
            indice,
            [hilo.error for hilo in hilos],
        )
        rechazo = _exigir_rechazo_del_contrato(perdedoras[0])
        assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_estado_no_permite(
            obra_id, f"AP-6{indice:02d}-26", "SUSPENDIDA", con_operaciones=True
        ), indice
        assert _transiciones(base, obra_id) == [("SUSPENDER", "ACTIVA", "SUSPENDIDA")], indice


# --------------------------------------------------------------------------- TC-59 · CA-4 · CA-13


@pytest.mark.parametrize("primera", ["edicion", "cierre"])
def test_tkt012b_ca4_ca13_edicion_y_cierre_en_cola(
    primera: str,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-59 · CA-4 · CA-13 · D-3 — editar y cerrar una obra `ACTIVA` en cola, en los dos órdenes.

    - **Cierre primero:** la obra queda `CERRADA` y la edición, ya con el bloqueo, lee `CERRADA` y se
      rechaza con `409` `ESTADO_NO_PERMITE_OPERACION` y el estado en el detalle. **No escribe**: el nombre
      sigue siendo el de origen, no hay asiento `ACTUALIZAR` y `actualizado_por_id` es el del cierre.
    - **Edición primero:** se aplica (una obra `ACTIVA` se edita) y el cierre llega sobre ella: nombre
      nuevo, `CERRADA`, un asiento de cada verbo.

    Sin el `FOR UPDATE` antes de leer el estado, la edición de «cierre primero» leería `ACTIVA` y
    escribiría sobre una obra cerrada.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    ctx = contexto()
    operaciones: dict[str, tuple[str, Operacion]] = {
        "edicion": (
            "edicion",
            functools.partial(actualizar_obra, ctx, obra_id, {"nombre": NOMBRE_NUEVO}, usuario),
        ),
        "cierre": ("cierre", functools.partial(cerrar_obra, ctx, obra_id, MOTIVO, usuario)),
    }
    orden = [operaciones[primera]] + [op for nombre, op in operaciones.items() if nombre != primera]
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)

    hilos = _correr_en_cola(base, retenedor, obra_id, orden)

    por_nombre = {hilo.name: hilo for hilo in hilos}
    assert por_nombre["cierre"].error is None, por_nombre["cierre"].error
    assert _estado(base, obra_id) == "CERRADA"
    if primera == "edicion":
        assert por_nombre["edicion"].error is None, por_nombre["edicion"].error
        assert _nombre(base, obra_id) == NOMBRE_NUEVO
        assert _verbos(base, obra_id) == ["ACTUALIZAR", "CERRAR"]
    else:
        rechazo = _exigir_rechazo_del_contrato(por_nombre["edicion"])
        assert rechazo.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_estado_no_permite(
            obra_id, CODIGO, "CERRADA", con_operaciones=False
        )
        assert _nombre(base, obra_id) == NOMBRE_INICIAL, "La edición perdedora no escribe"
        assert _verbos(base, obra_id) == ["CERRAR"], "La edición perdedora no asienta"


def test_tkt012b_ca4_ca13_edicion_y_cierre_simultaneos_en_varias_corridas(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    base: Base,
) -> None:
    """TC-59 · CA-4 · CA-13 · D-3 — soltados a la vez, `CORRIDAS` veces: la edición que pierde responde `409` y no escribe.

    En cada obra `ACTIVA`, editar el nombre y cerrar se sueltan con una barrera. El cierre siempre termina
    y la obra queda `CERRADA`. La edición, o gana (nombre nuevo y su asiento `ACTUALIZAR`) o pierde con el
    `409` `CERRADA` (nombre de origen y sin asiento): jamás un nombre nuevo sin su asiento ni un asiento
    sin su nombre, y nadie responde `500`.
    """
    ctx = contexto()
    for indice in range(CORRIDAS):
        obra_id = fabricar_obra(codigo=f"AP-5{indice:02d}-26", estado="ACTIVA")
        nombre_inicial = _nombre(base, obra_id)

        hilos = _carrera_libre(
            [
                (
                    "edicion",
                    functools.partial(
                        actualizar_obra, ctx, obra_id, {"nombre": NOMBRE_NUEVO}, usuario
                    ),
                ),
                ("cierre", functools.partial(cerrar_obra, ctx, obra_id, MOTIVO, usuario)),
            ]
        )

        _exigir_sin_500(hilos)
        por_nombre = {hilo.name: hilo for hilo in hilos}
        assert por_nombre["cierre"].error is None, (indice, por_nombre["cierre"].error)
        assert _estado(base, obra_id) == "CERRADA", indice
        if por_nombre["edicion"].error is None:
            assert _nombre(base, obra_id) == NOMBRE_NUEVO, indice
            assert _verbos(base, obra_id) == ["ACTUALIZAR", "CERRAR"], indice
        else:
            rechazo = _exigir_rechazo_del_contrato(por_nombre["edicion"])
            assert rechazo.codigo == "ESTADO_NO_PERMITE_OPERACION", indice
            assert rechazo.detalle == {"estado": "CERRADA"}, indice
            assert _nombre(base, obra_id) == nombre_inicial, indice
            assert _verbos(base, obra_id) == ["CERRAR"], indice


# --------------------------------------------------------------------------- TC-60 · CA-13 · RNF-16


def _reintento(operacion: str, obra_id: uuid.UUID) -> dict[str, str]:
    """La acción `REINTENTAR` de cada operación: su propio método y su propia ruta."""
    ruta = f"/api/v1/obras/{obra_id}"
    return {
        "patch": {"clave": "REINTENTAR", "metodo": "PATCH", "ruta": ruta},
        "delete": {"clave": "REINTENTAR", "metodo": "DELETE", "ruta": ruta},
        "suspension": {"clave": "REINTENTAR", "metodo": "POST", "ruta": f"{ruta}/suspension"},
        "reactivacion": {"clave": "REINTENTAR", "metodo": "POST", "ruta": f"{ruta}/reactivacion"},
        "cierre": {"clave": "REINTENTAR", "metodo": "POST", "ruta": f"{ruta}/cierre"},
    }[operacion]


# (operación, método, sufijo de la ruta, cuerpo, estado en que procede)
OPERACIONES_DE_LA_OBRA: list[tuple[str, str, str, object, str]] = [
    ("patch", "PATCH", "", {"nombre": NOMBRE_NUEVO}, "ACTIVA"),
    ("delete", "DELETE", "", None, "PLANEACION"),
    ("suspension", "POST", "/suspension", {"motivo": MOTIVO}, "ACTIVA"),
    ("reactivacion", "POST", "/reactivacion", {"motivo": MOTIVO}, "SUSPENDIDA"),
    ("cierre", "POST", "/cierre", {"motivo": MOTIVO}, "ACTIVA"),
]


@pytest.mark.parametrize(
    ("operacion", "metodo", "sufijo", "cuerpo", "estado"),
    OPERACIONES_DE_LA_OBRA,
    ids=[caso[0] for caso in OPERACIONES_DE_LA_OBRA],
)
def test_tkt012b_ca13_bloqueo_vencido_responde_409_concurrencia_con_reintentar(
    operacion: str,
    metodo: str,
    sufijo: str,
    cuerpo: object,
    estado: str,
    fabricar_obra: Callable[..., uuid.UUID],
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    cliente_espera_corta: TestClient,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-60 · CA-13 · ADR-004 · RNF-16 — con `lock_timeout` de 200 ms agotado, `55P03` es `409` `CONCURRENCIA`.

    Otra sesión tiene la fila de la obra con `FOR UPDATE` sin confirmar; la operación espera, vence el
    `lock_timeout` y el contrato completo es `CONCURRENCIA` `BLOQUEO_VENCIDO` con `espera_maxima_ms` 5000
    (el `lock_timeout` del rol), `Retry-After: 1` y la acción `REINTENTAR` con el método y la ruta **de
    esa operación**, para el Director de Proyectos. No escribe nada. Se prueban las cinco operaciones por
    HTTP: sin la traducción, el error del motor sale como `500`.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado=estado)
    correo = f"direccion-espera-{uuid.uuid4().hex[:8]}@cimenta.test"
    sembrar_usuario(correo, CONTRASENA_DE_PRUEBA, roles=("DIRECTOR_PROYECTOS",), nombre="Diana")
    sesion_id = iniciar_sesion(cliente_espera_corta, correo, CONTRASENA_DE_PRUEBA)
    cabeceras = cabeceras_de(sesion_id, TOKEN_CSRF, TOKEN_CSRF)
    antes = (
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT id, accion::text FROM bitacora ORDER BY id"),
    )
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (obra_id,))
        respuesta = cliente_espera_corta.request(
            metodo, f"/api/v1/obras/{obra_id}{sufijo}", headers=cabeceras, json=cuerpo
        )
    finally:
        retenedor.rollback()

    cuerpo_de_error = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONCURRENCIA",
            "codigo": "BLOQUEO_VENCIDO",
            "mensaje": MENSAJE_BLOQUEO,
            "detalle": {"espera_maxima_ms": 5000},
            "acciones": [_reintento(operacion, obra_id)],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo_de_error
    assert (
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT id, accion::text FROM bitacora ORDER BY id"),
    ) == antes, "La operación vencida no escribe nada"


def _llamada_del_caso_de_uso(
    operacion: str, ctx: Any, obra_id: uuid.UUID, usuario: uuid.UUID
) -> Operacion:
    """La operación de cada caso de uso, con un cuerpo válido, lista para llamarse sin argumentos."""
    return {
        "patch": functools.partial(
            actualizar_obra, ctx, obra_id, {"nombre": NOMBRE_NUEVO}, usuario
        ),
        "delete": functools.partial(eliminar_obra, ctx, obra_id, usuario),
        "suspension": functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario),
        "reactivacion": functools.partial(reactivar_obra, ctx, obra_id, MOTIVO, usuario),
        "cierre": functools.partial(cerrar_obra, ctx, obra_id, MOTIVO, usuario),
    }[operacion]


@pytest.mark.parametrize(
    ("operacion", "estado"),
    [(caso[0], caso[4]) for caso in OPERACIONES_DE_LA_OBRA],
    ids=[caso[0] for caso in OPERACIONES_DE_LA_OBRA],
)
def test_tkt012b_ca13_bloqueo_vencido_en_el_caso_de_uso_es_concurrencia_vencida(
    operacion: str,
    estado: str,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto_espera_corta: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """TC-60 · CA-13 · ADR-004 · RNF-16 — cada caso de uso traduce el `55P03` a `ConcurrenciaVencida`.

    Con `lock_timeout` de 200 ms y la obra retenida por otra sesión, el caso de uso debe lanzar
    `ConcurrenciaVencida` (`409` `CONCURRENCIA` `BLOQUEO_VENCIDO`, `Retry-After: 1`, `espera_maxima_ms`
    5000 y la acción `REINTENTAR` con el método y la ruta de esa operación). Si el `DBAPIError` del
    motor escapa sin traducir, el manejador global lo responde como `500`. Es el mismo contrato que
    `test_tkt017_cab06_congelado_con_bloqueo_vencido_en_el_caso_de_uso` fija para el congelado.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado=estado)
    ctx = contexto_espera_corta()
    antes = (
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT id, accion::text FROM bitacora ORDER BY id"),
    )
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    llamada = _llamada_del_caso_de_uso(operacion, ctx, obra_id, usuario)
    try:
        retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (obra_id,))
        with pytest.raises(Exception) as vencido:  # noqa: PT011 - se afirma el tipo justo debajo
            llamada()
    finally:
        retenedor.rollback()

    error = vencido.value
    assert isinstance(error, ConcurrenciaVencida), (
        f"El 55P03 debía traducirse a ConcurrenciaVencida y escapó {type(error).__name__}: {error}"
    )
    assert error.estado_http == 409
    assert error.cabeceras() == {"Retry-After": "1"}
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [_reintento(operacion, obra_id)],
        "correlacion_id": CORRELACION,
    }
    assert (
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT id, accion::text FROM bitacora ORDER BY id"),
    ) == antes, "La operación vencida no escribe nada"


# --------------------------------------------------------------------------- F005 · CA-13 · el reloj se lee con el bloqueo
#
# Ciclo de corrección 2, `auditor-codigo F005`: `ahora = contexto.reloj()` se leía antes de esperar el
# `FOR UPDATE`. Con dos operaciones simultáneas, la que obtiene el bloqueo después fechaba su asiento y su
# `actualizado_en` con un instante anterior al de la que ya había confirmado. El reloj se lee **dentro** de
# la transacción, con la obra ya bloqueada (como `congelado.py`). Cada prueba retiene el bloqueo con una
# operación real `A` (pausada con un `threading.Event` dentro de su transacción), lanza `B`, espera con
# `pg_blocking_pids` a que `B` quede detenida en el `FOR UPDATE`, adelanta el reloj de la prueba y suelta a
# `A`. Nada depende de `sleep` ni del planificador.

LAPSO_DE_ESPERA = timedelta(minutes=5)


def _pausar_a_dentro_de(monkeypatch: pytest.MonkeyPatch, paso: str) -> tuple[Any, Any]:
    """Envuelve `repositorio_obra.<paso>`: el hilo `A` queda pausado con la obra escrita y sin confirmar."""
    original = getattr(repositorio_obra, paso)
    dentro, liberar = threading.Event(), threading.Event()

    def pausar(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A":
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_obra, paso, pausar)
    return dentro, liberar


def _a_retiene_b_espera_y_el_reloj_avanza(
    base: Base,
    reloj: RelojDePrueba,
    operacion_a: Operacion,
    operacion_b: Operacion,
    dentro: Any,
    liberar: Any,
) -> tuple[datetime, datetime, Hilo[object], Hilo[object]]:
    """`A` dentro de su transacción, `B` esperando su `FOR UPDATE`, el reloj adelantado, `A` suelta.

    Devuelve el instante de `A`, el instante en que `B` obtiene el bloqueo (el reloj ya adelantado) y los
    dos hilos terminados.
    """
    instante_de_a = reloj()
    a: Hilo[object] = Hilo("A", operacion_a)
    b: Hilo[object] = Hilo("B", operacion_b)
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), f"A no llegó a su pausa: {a.error!r}"
        b.start()
        esperando = esperar_hasta(
            functools.partial(_hay_esperando_exactamente, base, 1), LIMITE_DE_HILO
        )
        assert esperando, f"B no quedó esperando el bloqueo de la obra: {b.error!r}"
        reloj.avanzar(LAPSO_DE_ESPERA)
        instante_de_b = reloj()
    finally:
        liberar.set()
        a.terminar()
        b.terminar()
    assert instante_de_b > instante_de_a
    return instante_de_a, instante_de_b, a, b


def _ocurrido_en(base: Base, obra_id: uuid.UUID, verbo: str, **condicion: str) -> list[datetime]:
    """El `ocurrido_en` de los asientos `verbo` de la obra que declaran `campo` en sus datos nuevos."""
    filtro = "".join(f" AND datos_despues ->> '{campo}' = %s" for campo in condicion)
    filas = base.filas(
        "SELECT ocurrido_en FROM bitacora WHERE entidad_id = %s AND accion::text = %s" + filtro,
        obra_id,
        verbo,
        *condicion.values(),
    )
    return [fila[0] for fila in filas]


def _actualizado_en(base: Base, obra_id: uuid.UUID) -> datetime:
    return base.filas("SELECT actualizado_en FROM obra WHERE id = %s", obra_id)[0][0]  # type: ignore[no-any-return]


def test_tkt012b_ca13_f005_actualizar_obra_fecha_con_el_instante_en_que_obtiene_el_bloqueo(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F005 · CA-13 · D-3 — la edición que espera el bloqueo fecha su asiento y `actualizado_en` al obtenerlo.

    `A` edita el nombre y se detiene con la obra escrita; `B` edita el domicilio y espera el `FOR UPDATE`;
    el reloj avanza cinco minutos mientras espera. Al terminar, el asiento `ACTUALIZAR` de `A` lleva su
    instante y el de `B` el del bloqueo (no el de antes de esperar), y `actualizado_en` de la obra, que
    escribió `B` al final, es ese mismo instante. Con `ahora` leído antes del bloqueo, `B` fecharía los dos
    con el instante de `A` y la bitácora contaría una historia al revés.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    ctx = contexto()
    dentro, liberar = _pausar_a_dentro_de(monkeypatch, "actualizar_obra")

    instante_de_a, instante_de_b, a, b = _a_retiene_b_espera_y_el_reloj_avanza(
        base,
        reloj_de_prueba,
        functools.partial(actualizar_obra, ctx, obra_id, {"nombre": NOMBRE_NUEVO}, usuario),
        functools.partial(
            actualizar_obra, ctx, obra_id, {"domicilio": "Domicilio de la espera"}, usuario
        ),
        dentro,
        liberar,
    )

    assert a.error is None and b.error is None, (a.error, b.error)
    assert _ocurrido_en(base, obra_id, "ACTUALIZAR", nombre=NOMBRE_NUEVO) == [instante_de_a]
    assert _ocurrido_en(base, obra_id, "ACTUALIZAR", domicilio="Domicilio de la espera") == [
        instante_de_b
    ]
    assert _actualizado_en(base, obra_id) == instante_de_b


@pytest.mark.parametrize(
    ("segunda", "verbo", "destino"),
    [
        pytest.param(reactivar_obra, "REACTIVAR", "ACTIVA", id="reactivar"),
        pytest.param(cerrar_obra, "CERRAR", "CERRADA", id="cerrar"),
    ],
)
def test_tkt012b_ca13_f005_transicion_fecha_con_el_instante_en_que_obtiene_el_bloqueo(
    segunda: Callable[..., None],
    verbo: str,
    destino: str,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F005 · CA-13 · D-2 — la transición que espera el bloqueo fecha su asiento y `actualizado_en` al obtenerlo.

    `A` suspende una obra `ACTIVA` y se detiene con el estado escrito; `B` (reactivar o cerrar, ya sobre
    `SUSPENDIDA`) espera el `FOR UPDATE`; el reloj avanza cinco minutos. El asiento de `A` lleva su
    instante, el de `B` el del bloqueo, y `actualizado_en` de la obra es el de `B`. Con `ahora` leído en
    `_transicionar` antes del bloqueo, el asiento de `B` saldría fechado igual que el de `A`.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="ACTIVA")
    ctx = contexto()
    dentro, liberar = _pausar_a_dentro_de(monkeypatch, "cambiar_estado_obra")

    instante_de_a, instante_de_b, a, b = _a_retiene_b_espera_y_el_reloj_avanza(
        base,
        reloj_de_prueba,
        functools.partial(suspender_obra, ctx, obra_id, MOTIVO, usuario),
        functools.partial(segunda, ctx, obra_id, MOTIVO, usuario),
        dentro,
        liberar,
    )

    assert a.error is None and b.error is None, (a.error, b.error)
    assert _estado(base, obra_id) == destino
    assert _ocurrido_en(base, obra_id, "SUSPENDER") == [instante_de_a]
    assert _ocurrido_en(base, obra_id, verbo) == [instante_de_b]
    assert _actualizado_en(base, obra_id) == instante_de_b


def test_tkt012b_ca13_f005_eliminar_obra_fecha_su_asiento_con_el_instante_del_bloqueo(
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    contexto: Contexto,
    reloj_de_prueba: RelojDePrueba,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F005 · CA-13 · RN-01 — el borrado que espera el bloqueo fecha su asiento `ELIMINAR` al obtenerlo.

    `A` edita el nombre de una obra `PLANEACION` sin historial y se detiene con la obra escrita; `B` la
    borra, espera el `FOR UPDATE` y el reloj avanza cinco minutos. La obra desaparece y el asiento
    `ELIMINAR` lleva el instante del bloqueo, posterior al de `ACTUALIZAR`. Con `ahora` leído antes del
    bloqueo, el borrado quedaría fechado antes de la edición que lo precedió.
    """
    obra_id = fabricar_obra(codigo=CODIGO, estado="PLANEACION")
    ctx = contexto()
    dentro, liberar = _pausar_a_dentro_de(monkeypatch, "actualizar_obra")

    instante_de_a, instante_de_b, a, b = _a_retiene_b_espera_y_el_reloj_avanza(
        base,
        reloj_de_prueba,
        functools.partial(actualizar_obra, ctx, obra_id, {"nombre": NOMBRE_NUEVO}, usuario),
        functools.partial(eliminar_obra, ctx, obra_id, usuario),
        dentro,
        liberar,
    )

    assert a.error is None and b.error is None, (a.error, b.error)
    assert base.filas("SELECT id FROM obra WHERE id = %s", obra_id) == []
    assert _ocurrido_en(base, obra_id, "ACTUALIZAR") == [instante_de_a]
    assert _ocurrido_en(base, obra_id, "ELIMINAR") == [instante_de_b]
