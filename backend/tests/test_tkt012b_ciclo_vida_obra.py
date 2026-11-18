"""Casos de uso de las tres transiciones de la obra (TKT-012b, fila A6): TC-33 a TC-35 y TC-37 a TC-40.

Prueba `cimenta/presupuesto/aplicacion/ciclo_vida_obra.py` contra PostgreSQL real (testcontainers), con el
esquema de `alembic upgrade head`, el rol de aplicación y el contexto real de `construir_contexto`. Nada de
SQLite, nada de `sleep` para sincronizar. TC-36 (motivo inválido, `422`) es de la API (A7) y la concurrencia
amplia es de A9; aquí solo vive TC-39, la lectura del estado tras el `FOR UPDATE`.

Contrato que fijan estas pruebas
--------------------------------

Firmas (las tres devuelven `None`; la ruta relee con `obtener_obra`, como el alta y A5):

- `suspender_obra(contexto, obra_id, motivo, usuario_id)`
- `reactivar_obra(contexto, obra_id, motivo, usuario_id)`
- `cerrar_obra(contexto, obra_id, motivo, usuario_id)`

`motivo` es `str`: llega ya validado (`Motivo`, A7); la aplicación no lo valida ni lo recorta, lo asienta
tal cual. Las tres comparten una transacción con `SELECT ... FOR UPDATE` de la obra, **antes** de leer su
estado.

Transición admitida (tabla D-2 del dominio): escribe el estado nuevo, `actualizado_en` (reloj inyectado) y
`actualizado_por_id`, y asienta en la misma sesión (regla 8) un solo asiento con `accion` `SUSPENDER`,
`REACTIVAR` o `CERRAR`; `entidad_tipo` `obra`; `entidad_id` y `obra_id` = la obra;
`datos_antes={"estado": origen}`, `datos_despues={"estado": destino}`; `motivo`; y
`regla_negocio=None`. La máquina de estados no tiene `RN` propia en el PRD y `RN-25` es el IVA por obra,
así que no se cita ninguna. **Corrección de aserción por decisión de la persona dueña (F002a de la
auditoría de cierre):** esta suite afirmaba `RN-25`; la guarda `test_tkt012b_regla_bitacora_obra.py` fija
la regla de cada verbo de obra.

Transición no admitida: `ConflictoEstado` (`409` `CONFLICTO`) `ESTADO_NO_PERMITE_OPERACION`, mensaje
`La obra {codigo} está en {estado} y no admite esta operación.`, detalle **exactamente**
`{"estado": <actual>, "operaciones_admitidas": [<verbos>]}` con los verbos de `OperacionObra`
(`SUSPENDER`, `REACTIVAR`, `CERRAR`) en el orden del enumerado, y `acciones` = una por operación admitida,
en ese orden: `SUSPENDER_OBRA` -> `/suspension`, `REACTIVAR_OBRA` -> `/reactivacion`, `CERRAR_OBRA` ->
`/cierre`, todas `POST` a `/api/v1/obras/{id}/...` y con los roles de `ROLES_ALTA`; filtradas por rol, un
residente no las ve. A diferencia del `409` `OBRA_CON_HISTORIAL` de `eliminar_obra` (que solo declara
`SUSPENDER_OBRA` y `CERRAR_OBRA`), aquí `REACTIVAR_OBRA` sí aparece desde `SUSPENDIDA`: es la salida que
la máquina admite. **A confirmar** (el borrador no lista claves para este `409`). Obra y bitácora no
cambian. Obra inexistente: `NoEncontrado(recurso="obra", mensaje="La obra no existe.")`.

Rojo de la fila A6: el módulo trae esqueletos que lanzan `NotImplementedError`, así que cada prueba de
comportamiento falla por eso. Nace en verde, a propósito, la que comprueba solo la firma.

Mutantes de la fila (A9 los corre contra la suite acumulada): leer el estado antes del `FOR UPDATE`
(`..._ca13_*`), asentar fuera de la transacción (`..._falla_del_asiento_*`), `CERRAR` desde `CERRADA` o
`SUSPENDER` desde `PLANEACION` admitidos (`..._ca9_*`), intercambiar `datos_antes` y `datos_despues` o el
verbo (`..._ca8_*`), tocar la línea base o el control (`..._ca8_ca_r4_*`), ofrecer una acción que
respondería `409` (`..._ca9_*`).
"""

from __future__ import annotations

import functools
import inspect
import uuid
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.aplicacion import ciclo_vida_obra
from cimenta.presupuesto.aplicacion.ciclo_vida_obra import (
    cerrar_obra,
    reactivar_obra,
    suspender_obra,
)
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from cimenta.presupuesto.aplicacion.obras import ROLES_ALTA
from contrato_error.excepciones import ConflictoEstado, ErrorContrato, NoEncontrado
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Base, Contexto, Hilo
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt012b-a6"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
ROLES_DG = frozenset({"DIRECCION_GENERAL"})
ROLES_SIN_ESCRITURA = frozenset({"RESIDENTE"})
ROLES_ALTA_ESPERADOS = ("DIRECTOR_PROYECTOS", "DIRECCION_GENERAL")
CODIGO = "AP-058-25"
NOMBRE_INICIAL = f"Obra {CODIGO}"
MOTIVO = "Falta de anticipo del cliente; se detiene la obra"
REGLA_DE_LAS_TRANSICIONES: str | None = None  # F002a: antes "RN-25", que en el PRD es el IVA

MENSAJE_OBRA_NO_EXISTE = "La obra no existe."
MENSAJE_ESTADO = "La obra {codigo} está en {estado} y no admite esta operación."

# Operación del dominio -> (clave de la acción del `409`, segmento de la ruta).
ACCION_DE_OPERACION: dict[str, tuple[str, str]] = {
    "SUSPENDER": ("SUSPENDER_OBRA", "suspension"),
    "REACTIVAR": ("REACTIVAR_OBRA", "reactivacion"),
    "CERRAR": ("CERRAR_OBRA", "cierre"),
}

# Tabla D-2: qué operaciones admite cada estado, en el orden de `OperacionObra`.
ADMITIDAS_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR",),
    "ACTIVA": ("SUSPENDER", "CERRAR"),
    "SUSPENDIDA": ("REACTIVAR", "CERRAR"),
    "CERRADA": (),
}

SELECT_ASIENTOS_DE_ENTIDAD = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
    "obra_id, datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s ORDER BY ocurrido_en, id"
)


class Transicion(Protocol):
    """La firma común de las tres funciones: así los parámetros se llaman por nombre."""

    __name__: str

    def __call__(
        self,
        contexto: ContextoPresupuesto,
        obra_id: uuid.UUID,
        motivo: str,
        usuario_id: uuid.UUID,
    ) -> None: ...


# (origen, función, destino, verbo del asiento): los cinco ejemplos de CA-8 más PLANEACION -> CERRADA (D-2).
ADMITIDAS: list[tuple[str, Transicion, str, str]] = [
    ("ACTIVA", suspender_obra, "SUSPENDIDA", "SUSPENDER"),
    ("SUSPENDIDA", reactivar_obra, "ACTIVA", "REACTIVAR"),
    ("ACTIVA", cerrar_obra, "CERRADA", "CERRAR"),
    ("SUSPENDIDA", cerrar_obra, "CERRADA", "CERRAR"),
    ("PLANEACION", cerrar_obra, "CERRADA", "CERRAR"),
]
IDS_ADMITIDAS = [f"{origen}-{verbo}" for origen, _, _, verbo in ADMITIDAS]

# Las siete combinaciones de CA-9: (origen, función).
NO_ADMITIDAS: list[tuple[str, Transicion]] = [
    ("PLANEACION", suspender_obra),
    ("PLANEACION", reactivar_obra),
    ("ACTIVA", reactivar_obra),
    ("SUSPENDIDA", suspender_obra),
    ("CERRADA", suspender_obra),
    ("CERRADA", reactivar_obra),
    ("CERRADA", cerrar_obra),
]
IDS_NO_ADMITIDAS = [f"{origen}-{funcion.__name__}" for origen, funcion in NO_ADMITIDAS]

TRES_FUNCIONES: list[Transicion] = [suspender_obra, reactivar_obra, cerrar_obra]
IDS_TRES_FUNCIONES = [funcion.__name__ for funcion in TRES_FUNCIONES]


class FallaDeBitacora(Exception):  # noqa: N818 - es un doble de prueba, no una excepción de producción
    """El fallo del asiento que la prueba de la misma transacción provoca a propósito."""


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto real del rol de aplicación con su reloj de prueba."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008)."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return filas[0][0]


@pytest.fixture
def usuario(datos_presupuesto: DatosPresupuesto) -> uuid.UUID:
    return datos_presupuesto.usuario()


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID, usuario: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra en el estado pedido, con tres porcentajes distintos."""

    def fabricar(*, codigo: str = CODIGO, estado: str = "ACTIVA") -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo,
            empresa_id=empresa_de_la_migracion,
            creado_por_id=usuario,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=Decimal("0.100000"),
            iva_acreditable=True,
        )

    return fabricar


# --------------------------------------------------------------------------- ayudas


def _fila(base: Base, obra_id: uuid.UUID) -> dict[str, Any]:
    """Todas las columnas de la obra, con los `Decimal` como cadena para comprobar también la escala."""
    cursor = base.conexion.execute("SELECT * FROM obra WHERE id = %s", (obra_id,))
    fila = cursor.fetchone()
    assert fila is not None, "La obra no existe"
    assert cursor.description is not None
    return {
        columna.name: (str(valor) if isinstance(valor, Decimal) else valor)
        for columna, valor in zip(cursor.description, fila, strict=True)
    }


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _instantanea(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: obras completas, líneas base, importaciones y bitácora."""
    return {
        "foto": base.foto(),
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "importaciones": base.filas("SELECT id, obra_id, estado FROM importacion ORDER BY id"),
        "bitacora": base.filas("SELECT id, accion::text, entidad_id FROM bitacora ORDER BY id"),
    }


def _rechazo[E: ErrorContrato](base: Base, llamada: Callable[[], object], clase: type[E]) -> E:
    """Ejecuta `llamada`, espera `clase` y comprueba que no cambió ninguna fila ni se asentó nada."""
    antes = _instantanea(base)
    with pytest.raises(clase) as rechazo:
        llamada()
    assert _instantanea(base) == antes, "Un rechazo no escribe: ni obra, ni historial, ni bitácora"
    return rechazo.value


def _asientos(base: Base, entidad_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return base.filas(SELECT_ASIENTOS_DE_ENTIDAD, entidad_id)


def _asiento_esperado(
    *,
    verbo: str,
    obra_id: uuid.UUID,
    usuario: uuid.UUID,
    ocurrido_en: Any,
    origen: str,
    destino: str,
) -> tuple[Any, ...]:
    """El asiento de una transición, en el orden de columnas de `SELECT_ASIENTOS_DE_ENTIDAD`."""
    return (
        verbo,
        "obra",
        obra_id,
        usuario,
        ocurrido_en,
        REGLA_DE_LAS_TRANSICIONES,
        MOTIVO,
        obra_id,
        {"estado": origen},
        {"estado": destino},
    )


def _acciones_esperadas(obra_id: uuid.UUID, estado: str) -> list[dict[str, str]]:
    """Una acción por operación que el estado admite: método y ruta reales de la obra."""
    return [
        {
            "clave": ACCION_DE_OPERACION[operacion][0],
            "metodo": "POST",
            "ruta": f"/api/v1/obras/{obra_id}/{ACCION_DE_OPERACION[operacion][1]}",
        }
        for operacion in ADMITIDAS_POR_ESTADO[estado]
    ]


def _cuerpo_estado_no_permite(obra_id: uuid.UUID, estado: str) -> dict[str, object]:
    """El cuerpo completo del `409` que ve un Director de Proyectos."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_ESTADO.format(codigo=CODIGO, estado=estado),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"estado": estado, "operaciones_admitidas": list(ADMITIDAS_POR_ESTADO[estado])},
        "acciones": _acciones_esperadas(obra_id, estado),
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- firma (nace en verde)


def test_tkt012b_a6_las_firmas_son_las_del_diseno() -> None:
    """A6 · firma — `(contexto, obra_id, motivo, usuario_id) -> None` en las tres transiciones.

    Nace en verde con el esqueleto: fija nombres y orden de los parámetros que cablea A7 (el `Motivo` ya
    validado llega como `str`) y que el resto de pruebas de este archivo usan por nombre (`usuario_id=`).
    """
    for funcion in TRES_FUNCIONES:
        firma = inspect.signature(funcion)
        assert list(firma.parameters) == ["contexto", "obra_id", "motivo", "usuario_id"], (
            funcion.__name__
        )
        assert firma.return_annotation in (None, "None"), funcion.__name__
    assert ROLES_ALTA == ROLES_ALTA_ESPERADOS


# --------------------------------------------------------------------------- TC-33 · CA-8


@pytest.mark.parametrize(
    ("origen", "operacion", "destino", "verbo"),
    [caso for caso in ADMITIDAS if caso[0] != "PLANEACION"],
    ids=[ident for ident in IDS_ADMITIDAS if not ident.startswith("PLANEACION")],
)
def test_hdu001_esc20_tkt012b_ca8_transicion_admitida_cambia_el_estado_y_asienta_el_verbo(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    origen: str,
    operacion: Transicion,
    destino: str,
    verbo: str,
) -> None:
    """TC-33 · HDU-001 esc. 20 · CA-8 · RN-25 — feliz: cada transición admitida cambia el estado y se asienta.

    El asiento lleva el verbo, el estado anterior y el nuevo, el motivo, la obra y el usuario, sin regla (`regla_negocio` nula, F002a).
    Un solo asiento por transición. `actualizado_en` toma el reloj inyectado (avanzado, para distinguirlo
    de la hora de la base) y `actualizado_por_id` al usuario; ninguna otra columna cambia, y otra obra, del
    mismo estado, no se toca. La función no devuelve nada: la ruta relee con `obtener_obra`.
    """
    obra_id = fabricar_obra(estado=origen)
    otra = datos_presupuesto.obra(
        codigo="AP-099-26", empresa_id=empresa_de_la_migracion, estado=origen
    )
    antes = _fila(base, obra_id)
    antes_de_la_otra = _fila(base, otra)
    reloj_de_prueba.avanzar(timedelta(hours=3))
    ahora = reloj_de_prueba()

    resultado = operacion(  # type: ignore[func-returns-value]
        contexto(), obra_id, MOTIVO, usuario_id=usuario
    )

    assert resultado is None
    assert _fila(base, obra_id) == {
        **antes,
        "estado": destino,
        "actualizado_en": ahora,
        "actualizado_por_id": usuario,
    }
    assert _fila(base, otra) == antes_de_la_otra
    assert _asientos(base, obra_id) == [
        _asiento_esperado(
            verbo=verbo,
            obra_id=obra_id,
            usuario=usuario,
            ocurrido_en=ahora,
            origen=origen,
            destino=destino,
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Una transición, un solo asiento"


# --------------------------------------------------------------------------- TC-37 · CA-8 (D-2)


def test_hdu001_esc20_tkt012b_ca8_cerrar_una_obra_en_planeacion_asienta_cerrar(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-37 · CA-8 ejemplo añadido · D-2 · D-DIS-6 · RN-25 — feliz: `PLANEACION → CERRADA` está admitida.

    Una obra que nunca se activó se cierra con motivo. Es la transición que se probaría rota si el
    dominio exigiera pasar por `ACTIVA`. El asiento trae `PLANEACION` como estado anterior.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    ahora = reloj_de_prueba()

    cerrar_obra(contexto(), obra_id, MOTIVO, usuario_id=usuario)

    assert _fila(base, obra_id)["estado"] == "CERRADA"
    assert _asientos(base, obra_id) == [
        _asiento_esperado(
            verbo="CERRAR",
            obra_id=obra_id,
            usuario=usuario,
            ocurrido_en=ahora,
            origen="PLANEACION",
            destino="CERRADA",
        )
    ]


# --------------------------------------------------------------------------- TC-34 · CA-8 variante


def test_hdu001_esc20_tkt012b_ca8_direccion_general_opera_igual_en_toda_la_cadena(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-34 · CA-8 variante — feliz: otro usuario (el de Dirección General) suspende, reactiva y cierra.

    A este nivel el rol no cuenta (lo comprueba la ruta en A7); lo que se prueba es que quien opera
    queda en `actualizado_por_id` y en los tres asientos, distintos del creador de la obra, y que la
    cadena `ACTIVA → SUSPENDIDA → ACTIVA → CERRADA` es admitida de punta a punta. El reloj avanza entre
    pasos para que el orden de los asientos sea el de la operación.
    """
    obra_id = fabricar_obra(estado="ACTIVA")
    direccion_general = datos_presupuesto.usuario()
    cadena: list[tuple[Transicion, str, str, str]] = [
        (suspender_obra, "SUSPENDER", "ACTIVA", "SUSPENDIDA"),
        (reactivar_obra, "REACTIVAR", "SUSPENDIDA", "ACTIVA"),
        (cerrar_obra, "CERRAR", "ACTIVA", "CERRADA"),
    ]
    esperados = []

    for operacion, verbo, origen, destino in cadena:
        reloj_de_prueba.avanzar(timedelta(minutes=10))
        ahora = reloj_de_prueba()
        operacion(contexto(), obra_id, MOTIVO, usuario_id=direccion_general)
        esperados.append(
            _asiento_esperado(
                verbo=verbo,
                obra_id=obra_id,
                usuario=direccion_general,
                ocurrido_en=ahora,
                origen=origen,
                destino=destino,
            )
        )
        assert _fila(base, obra_id)["estado"] == destino

    fila = _fila(base, obra_id)
    assert fila["actualizado_por_id"] == direccion_general
    assert _asientos(base, obra_id) == esperados


# --------------------------------------------------------------------------- TC-35 · CA-9


@pytest.mark.parametrize(("origen", "operacion"), NO_ADMITIDAS, ids=IDS_NO_ADMITIDAS)
def test_tkt012b_ca9_transicion_no_admitida_responde_409_estado_no_permite_operacion(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    origen: str,
    operacion: Transicion,
) -> None:
    """TC-35 · CA-9 · D-2 — rechazo: las siete combinaciones que la máquina no admite.

    El contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`: no hay `RN` de la máquina de estados),
    `codigo` del catálogo, mensaje con el código de la obra y su estado, y detalle con el estado actual y
    las operaciones que **sí** admite (la tabla D-2, no la solicitada). Las acciones son una por operación
    admitida, con método y ruta reales de la obra, y nunca incluyen la que se acaba de rechazar. Las ven
    el Director de Proyectos y Dirección General; el residente recibe el mismo cuerpo sin acciones. Obra
    y bitácora quedan intactas.
    """
    obra_id = fabricar_obra(estado=origen)

    error = _rechazo(
        base,
        lambda: operacion(contexto(), obra_id, MOTIVO, usuario_id=usuario),
        ConflictoEstado,
    )

    esperado = _cuerpo_estado_no_permite(obra_id, origen)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert error.cuerpo(ROLES_DG, CORRELACION) == esperado
    assert error.cuerpo(ROLES_SIN_ESCRITURA, CORRELACION) == {**esperado, "acciones": []}
    assert all(
        accion.roles_permitidos == frozenset(ROLES_ALTA_ESPERADOS) for accion in error.acciones
    )
    assert _fila(base, obra_id)["estado"] == origen
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


def test_tkt012b_ca9_ninguna_transicion_ofrece_una_accion_que_responderia_409(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-35 · CA-9 · objeción 5 de la spec — rechazo: cada acción ofrecida es una transición que se admite.

    Para cada combinación no admitida, la clave de cada acción corresponde a una operación del estado
    actual: se comprueba contra la tabla D-2 literal, sin pasar por el helper de cuerpos. Desde `CERRADA`
    no hay ninguna.
    """
    claves_por_estado = {
        "PLANEACION": ["CERRAR_OBRA"],
        "ACTIVA": ["SUSPENDER_OBRA", "CERRAR_OBRA"],
        "SUSPENDIDA": ["REACTIVAR_OBRA", "CERRAR_OBRA"],
        "CERRADA": [],
    }
    # `codigo` es único: cada combinación lleva su propia obra, con un código distinto.
    for indice, (origen, operacion) in enumerate(NO_ADMITIDAS):
        obra_id = fabricar_obra(codigo=f"AP-{indice:03d}-26", estado=origen)
        with pytest.raises(ConflictoEstado) as rechazo:
            operacion(contexto(), obra_id, MOTIVO, usuario_id=usuario)
        assert [accion.clave for accion in rechazo.value.acciones] == claves_por_estado[origen], (
            f"{origen} {operacion.__name__}"
        )
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- obra inexistente · CA-12


@pytest.mark.parametrize("operacion", TRES_FUNCIONES, ids=IDS_TRES_FUNCIONES)
def test_tkt012b_ca12_transicion_de_obra_inexistente_responde_404_y_no_asienta(
    contexto: Contexto, base: Base, usuario: uuid.UUID, operacion: Transicion
) -> None:
    """CA-12 a nivel de caso de uso — rechazo: `NO_ENCONTRADO` con `recurso` `obra` y nada escrito."""
    error = _rechazo(
        base,
        lambda: operacion(contexto(), uuid.uuid4(), MOTIVO, usuario_id=usuario),
        NoEncontrado,
    )

    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_OBRA_NO_EXISTE,
        "recurso": "obra",
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-38 · CA-8, CA-R4


def test_tkt012b_ca8_ca_r4_las_transiciones_no_tocan_la_linea_base_ni_el_control(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-38 · CA-8 · CA-R4 · RN-01 — regresión: suspender, reactivar y cerrar no pierden ningún dato histórico.

    Una obra `ACTIVA` con su jerarquía (nivel y concepto), una línea base `CONGELADA` con un renglón de
    explosión y un control presupuestal, y una importación. Tras recorrer `ACTIVA → SUSPENDIDA → ACTIVA →
    CERRADA`, esas filas están **idénticas, columna por columna**, y la obra solo cambió de estado y de
    quién y cuándo la tocó. La línea base sigue `CONGELADA` (el cierre no la supersede ni la borra).
    """
    obra_id = fabricar_obra(estado="ACTIVA")
    linea_base = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra_id)
    muros = datos_presupuesto.tipo_partida(clave="MUROS")
    datos_presupuesto.nivel(obra_id=obra_id)
    datos_presupuesto.concepto(obra_id=obra_id)
    datos_presupuesto.renglon_explosion(linea_base_id=linea_base, tipo_partida_id=muros)
    datos_presupuesto.control(linea_base_id=linea_base, tipo_partida_id=muros)
    datos_presupuesto.congelar(linea_base)
    datos_presupuesto.importacion(obra_id=obra_id)

    def historia() -> dict[str, object]:
        return {
            "jerarquia": base.volcado_de_obra(obra_id),
            "explosion": base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
            "control": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
            "importaciones": base.filas("SELECT * FROM importacion ORDER BY id"),
        }

    historia_antes = historia()
    obra_antes = _fila(base, obra_id)
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", linea_base) == [("CONGELADA",)]

    for operacion in (suspender_obra, reactivar_obra, cerrar_obra):
        reloj_de_prueba.avanzar(timedelta(minutes=10))  # el orden de los asientos es el del reloj
        operacion(contexto(), obra_id, MOTIVO, usuario_id=usuario)

    assert historia() == historia_antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", linea_base) == [("CONGELADA",)]
    obra_despues = _fila(base, obra_id)
    assert obra_despues["estado"] == "CERRADA"
    cambiaron = {"estado", "actualizado_en", "actualizado_por_id"}
    assert {k: v for k, v in obra_despues.items() if k not in cambiaron} == {
        k: v for k, v in obra_antes.items() if k not in cambiaron
    }
    assert [fila[0] for fila in _asientos(base, obra_id)] == ["SUSPENDER", "REACTIVAR", "CERRAR"]


# --------------------------------------------------------------------------- TC-39 · CA-13


def _alguien_espera_la_obra(base: Base) -> bool:
    """Una sesión de la base detenida por un bloqueo, en un `SELECT ... FROM obra ... FOR UPDATE`."""
    fila = base.conexion.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
        ("%FROM obra%FOR UPDATE%",),
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


@pytest.mark.parametrize(
    ("estado_que_deja_la_ganadora", "operacion", "verbo", "destino", "operaciones_admitidas"),
    [
        ("CERRADA", suspender_obra, "SUSPENDER", None, []),
        ("SUSPENDIDA", suspender_obra, "SUSPENDER", None, ["REACTIVAR", "CERRAR"]),
        ("SUSPENDIDA", reactivar_obra, "REACTIVAR", "ACTIVA", None),
    ],
    ids=["suspender-tras-cierre", "suspender-tras-suspension", "reactivar-tras-suspension"],
)
def test_tkt012b_ca13_la_transicion_que_espero_el_bloqueo_se_evalua_contra_el_estado_nuevo(
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    estado_que_deja_la_ganadora: str,
    operacion: Transicion,
    verbo: str,
    destino: str | None,
    operaciones_admitidas: list[str] | None,
) -> None:
    """TC-39 · CA-13 · D-2 — concurrencia: el estado se lee tras el `FOR UPDATE`, no antes.

    La obra está `ACTIVA`. Una conexión propia (la «ganadora») toma `FOR UPDATE` y cambia el estado sin
    confirmar; el hilo `B` llama a la transición y se detiene en el bloqueo (se comprueba en
    `pg_stat_activity`, sin dormir). Al confirmar la ganadora, `B` despierta:

    - Si leyó el estado antes del bloqueo, vería `ACTIVA` y haría lo que `ACTIVA` admite: suspender una
      obra ya `CERRADA` (o ya `SUSPENDIDA`) o rechazar una reactivación que ahora es legítima.
    - Si lo lee después, evalúa contra el estado nuevo: `suspender` tras un cierre o una suspensión se
      rechaza con el estado nuevo y sus operaciones, y `reactivar` tras una suspensión se admite.

    Nunca `500`: el resultado es un rechazo del contrato o un éxito, y la obra queda en el estado que la
    máquina impone.
    """
    obra_id = fabricar_obra(estado="ACTIVA")
    ctx = contexto()
    ganadora = conectar("aplicacion", base_de_prueba, autocommit=False)
    ganadora.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (obra_id,))
    ganadora.execute(
        "UPDATE obra SET estado = %s WHERE id = %s", (estado_que_deja_la_ganadora, obra_id)
    )
    ahora = reloj_de_prueba()

    hilo = Hilo("B", lambda: operacion(ctx, obra_id, MOTIVO, usuario_id=usuario))
    hilo.start()
    esperar_hasta(lambda: not hilo.is_alive() or _alguien_espera_la_obra(base), LIMITE_DE_HILO)
    assert hilo.is_alive(), f"B debía esperar el bloqueo de la obra y terminó con {hilo.error!r}"
    assert _alguien_espera_la_obra(base)
    assert _fila(base, obra_id)["estado"] == "ACTIVA", "La ganadora aún no confirmó"
    ganadora.commit()
    hilo.terminar()

    if destino is None:
        error = hilo.error
        assert isinstance(error, ConflictoEstado), f"B debió rechazarse y dio {error!r}"
        assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_estado_no_permite(
            obra_id, estado_que_deja_la_ganadora
        )
        assert error.detalle == {
            "estado": estado_que_deja_la_ganadora,
            "operaciones_admitidas": operaciones_admitidas,
        }
        assert _fila(base, obra_id)["estado"] == estado_que_deja_la_ganadora
        assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    else:
        assert hilo.error is None, f"B debió admitirse contra el estado nuevo y dio {hilo.error!r}"
        assert _fila(base, obra_id)["estado"] == destino
        assert _asientos(base, obra_id) == [
            _asiento_esperado(
                verbo=verbo,
                obra_id=obra_id,
                usuario=usuario,
                ocurrido_en=ahora,
                origen=estado_que_deja_la_ganadora,
                destino=destino,
            )
        ]


# --------------------------------------------------------------------------- TC-40 · CA-8, regla 8


def _asentar_que_falla(visto: dict[str, object]) -> Callable[..., None]:
    """Un `asentar` que anota cómo lo llamaron y lanza, para probar que corre en la misma transacción."""

    def asentar_que_falla(*args: Any, **kwargs: Any) -> None:
        sesion_bd: Session = args[0] if args else kwargs["sesion_bd"]
        visto["en_transaccion"] = sesion_bd.in_transaction()
        visto["accion"] = str(kwargs["accion"])
        visto["regla_negocio"] = kwargs.get("regla_negocio")
        visto["motivo"] = kwargs.get("motivo")
        visto["obra_id"] = kwargs.get("obra_id")
        visto["datos_antes"] = kwargs.get("datos_antes")
        visto["datos_despues"] = kwargs.get("datos_despues")
        visto["estado_visto"] = sesion_bd.execute(
            text("SELECT estado FROM obra WHERE id = :id"), {"id": kwargs["entidad_id"]}
        ).scalar_one_or_none()
        raise FallaDeBitacora

    return asentar_que_falla


@pytest.mark.parametrize(("origen", "operacion", "destino", "verbo"), ADMITIDAS, ids=IDS_ADMITIDAS)
def test_tkt012b_ca8_si_falla_el_asiento_se_deshace_la_transicion(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
    origen: str,
    operacion: Transicion,
    destino: str,
    verbo: str,
) -> None:
    """TC-40 · CA-8 · regla 8 de CLAUDE.md — rechazo: la bitácora se escribe en la misma transacción.

    `asentar` se sustituye por uno que, antes de lanzar, anota con qué lo llamaron: dentro de la
    transacción del caso de uso, con el verbo, sin regla (`None`), el motivo, la obra, los estados antes y después, y
    viendo el estado nuevo todavía sin confirmar. Al lanzar, la transacción se deshace: la obra conserva
    el estado de origen, sin `actualizado_en`, y no hay asiento. Con `asentar` en otra sesión tras confirmar,
    la obra quedaría transicionada y la prueba cae.
    """
    obra_id = fabricar_obra(estado=origen)
    visto: dict[str, object] = {}
    monkeypatch.setattr(ciclo_vida_obra, "asentar", _asentar_que_falla(visto))
    antes = _instantanea(base)

    with pytest.raises(FallaDeBitacora):
        operacion(contexto(), obra_id, MOTIVO, usuario_id=usuario)

    assert visto == {
        "en_transaccion": True,
        "accion": verbo,
        "regla_negocio": REGLA_DE_LAS_TRANSICIONES,
        "motivo": MOTIVO,
        "obra_id": obra_id,
        "datos_antes": {"estado": origen},
        "datos_despues": {"estado": destino},
        "estado_visto": destino,
    }, "asentar debe correr en la misma sesión, con la transición hecha y sin confirmar"
    assert _instantanea(base) == antes, "Un asiento que falla deshace la transición entera"
    fila = _fila(base, obra_id)
    assert fila["estado"] == origen
    assert fila["actualizado_en"] is None
    assert fila["actualizado_por_id"] is None
