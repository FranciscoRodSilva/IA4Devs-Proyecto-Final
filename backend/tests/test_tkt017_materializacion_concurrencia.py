"""Concurrencia de la confirmación, fila A6c de TKT-017a3 (TC-A22 y TC-A23 · CA-A10 · RN-01).

Toda la vida de la línea base de una obra se serializa con un `SELECT ... FOR UPDATE` sobre la fila de
`obra` (`bloquear_obra`, después del bloqueo de la importación). Sin ese bloqueo, dos confirmaciones
de la misma obra leen "sin borrador" las dos y escriben jerarquías que se pisan.

`TC-A22` lanza las dos confirmaciones a la vez con `threading.Barrier`; como su resultado depende de
quién llega primero, solo `TC-A23` demuestra el bloqueo: el hilo A se pausa dentro de
`insertar_niveles` (con la obra ya bloqueada y filas sin confirmar) y la prueba espera, mirando
`pg_blocking_pids`, a que el hilo B quede en espera de A. Ninguna espera es un `sleep` fijo: cada una
sondea una condición con un tope que hace fallar la prueba, y todo hilo pausado se libera en `finally`.

Las dos importaciones son libros distintos (el plafón con 12.5 / 7.3333 y con 8.0000 m2), para saber
de cuál salió la jerarquía que quedó.

Mutante `M-A1`: quitar `with_for_update()` de `bloquear_obra` debe poner en rojo `TC-A22` y `TC-A23`.
Mutante de la importación: quitar `with_for_update()` de `bloquear_importacion` debe poner en rojo
`test_tkt017_caa10_dos_confirmaciones_de_la_misma_importacion_se_serializan`.
"""

from __future__ import annotations

import functools
import threading
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, LiteralString

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from cimenta.presupuesto.dominio.materializacion import NivelNuevo
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from cimenta.presupuesto.infraestructura.preparacion_json import preparacion_a_json
from cimenta.presupuesto.interfaz import LineaBaseMaterializada, materializar_importacion
from contrato_error.excepciones import ConcurrenciaVencida, ConflictoEstado, ErrorContrato
from herramientas.soporte_tkt017 import (
    preparacion_sintetica,
    preparacion_sintetica_cantidad_plafon,
)
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt017-a6c"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
LIMITE = 10.0
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
MENSAJE_REEMPLAZO = (
    "La obra ya tiene una línea base en borrador; confirmar esta importación la reemplaza."
)
MENSAJE_ESTADO = (
    "La importación está en {estado} y no se confirma. Solo se confirma una importación VALIDADO."
)
MOTIVO = "Corrección de cantidades del nivel 3"

# Cantidad del plafón en cada libro: 7.3333 en la importación 1 y 8.0000 en la 2.
_CANTIDADES = {
    "importacion_1": ("12.5000", "7.3333"),
    "importacion_2": ("12.5000", "8.0000"),
}


# --------------------------------------------------------------------------- el entorno


class Obra:
    """Una obra en planeación con dos importaciones `VALIDADO` de libros distintos."""

    def __init__(
        self, datos: DatosPresupuesto, conexion: psycopg.Connection[tuple[Any, ...]]
    ) -> None:
        self.conexion = conexion
        self.usuario_id = datos.usuario()
        self.obra_id = datos.obra(codigo="AP-058-25", creado_por_id=self.usuario_id)
        self.tipo_muros = datos.tipo_partida(clave="MUROS")
        self.tipo_plafon = datos.tipo_partida(clave="PLAFONES_Y_CAJILLOS")
        datos.insumo(
            codigo="MO-001", descripcion="OFICIAL TABLAROQUERO", tipo="MANO_OBRA", unidad="JORNAL"
        )
        # Ya registrado, para que ninguna importación inserte un insumo: dos altas simultáneas de la
        # misma clave se esperarían por el índice único de `insumo.codigo` y dejarían de probar el
        # bloqueo de la obra (con `M-A1` el `lock_timeout` vencería igual, pero por otro bloqueo).
        datos.insumo(
            codigo="PANEL YESO 1/2",
            descripcion="Panel de yeso 1/2",
            tipo="MATERIAL",
            unidad="PZA",
        )
        self.importacion_1 = self._importar(datos, preparacion_sintetica())
        self.importacion_2 = self._importar(datos, preparacion_sintetica_cantidad_plafon("8.0000"))

    def _importar(self, datos: DatosPresupuesto, preparacion: Preparacion) -> uuid.UUID:
        return datos.importacion(
            obra_id=self.obra_id,
            estado="VALIDADO",
            preparacion=preparacion_a_json(preparacion),
            importado_por_id=self.usuario_id,
        )

    def asignacion(self) -> dict[str, uuid.UUID]:
        return {"MUROS EXTERIORES": self.tipo_muros, "PLAFON": self.tipo_plafon}

    def filas(self, consulta: LiteralString, *parametros: object) -> list[tuple[Any, ...]]:
        return self.conexion.execute(consulta, parametros).fetchall()

    def confirmar(
        self,
        contexto: ContextoPresupuesto,
        importacion_id: uuid.UUID,
        *,
        reemplazar_borrador: bool = False,
        motivo_reemplazo: str | None = None,
    ) -> LineaBaseMaterializada:
        return materializar_importacion(
            contexto,
            importacion_id=importacion_id,
            asignacion_tipos_partida=self.asignacion(),
            reemplazar_borrador=reemplazar_borrador,
            motivo_reemplazo=motivo_reemplazo,
            usuario_id=self.usuario_id,
        )

    def cantidades(self) -> list[str]:
        """Las cantidades de las apariciones de la obra, ordenadas por área."""
        filas = self.filas(
            "SELECT pc.cantidad::text FROM partida_concepto pc "
            "JOIN partida p ON p.id = pc.partida_id JOIN area a ON a.id = p.area_id "
            "JOIN nivel n ON n.id = a.nivel_id WHERE n.obra_id = %s ORDER BY a.nombre",
            self.obra_id,
        )
        return [fila[0] for fila in filas]

    def _hay_alguien_esperando(self, patron: str) -> bool:
        (cuantas,) = self.filas(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
            patron,
        )[0]
        return bool(cuantas)

    def hay_alguien_esperando_la_obra(self) -> bool:
        """Una sesión de la base detenida por un bloqueo, en su `SELECT ... FROM obra ... FOR UPDATE`."""
        return self._hay_alguien_esperando("%FROM obra%FOR UPDATE%")

    def hay_alguien_esperando_la_importacion(self) -> bool:
        """Una sesión detenida por un bloqueo, en su `SELECT ... FROM importacion ... FOR UPDATE`."""
        return self._hay_alguien_esperando("%FROM importacion%FOR UPDATE%")

    def cuenta(self, tabla: str) -> int:
        consultas: dict[str, LiteralString] = {
            "linea_base": "SELECT count(*) FROM linea_base WHERE obra_id = %s",
            "nivel": "SELECT count(*) FROM nivel WHERE obra_id = %s",
            "concepto": "SELECT count(*) FROM concepto WHERE obra_id = %s",
            "bitacora": "SELECT count(*) FROM bitacora WHERE obra_id = %s",
            "descartar": "SELECT count(*) FROM bitacora WHERE obra_id = %s AND accion = 'DESCARTAR'",
        }
        return int(self.filas(consultas[tabla], self.obra_id)[0][0])


@pytest.fixture
def obra(datos_presupuesto: DatosPresupuesto, base_de_prueba: str, conectar: Conectar) -> Obra:
    return Obra(datos_presupuesto, conectar("aplicacion", base_de_prueba))


@pytest.fixture
def contexto(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> Callable[[], ContextoPresupuesto]:
    """El contexto del rol de aplicación con sus 5 s de `lock_timeout`, construido al primer uso."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def contexto_espera_corta(
    motor_espera_corta: Engine, reloj_de_prueba: RelojDePrueba
) -> Callable[[], ContextoPresupuesto]:
    """El mismo contexto sobre `motor_espera_corta`: la sesión espera un bloqueo solo 200 ms."""
    return functools.cache(
        lambda: construir_contexto(
            proveedor_motor=lambda: motor_espera_corta, reloj=reloj_de_prueba
        )
    )


class Hilo(threading.Thread):
    """Un hilo que guarda el resultado o la excepción de su función, sin dejarla escapar."""

    def __init__(self, nombre: str, funcion: Callable[[], LineaBaseMaterializada]) -> None:
        super().__init__(name=nombre, daemon=True)
        self._funcion = funcion
        self.resultado: LineaBaseMaterializada | None = None
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            self.resultado = self._funcion()
        except BaseException as error:
            self.error = error

    def exito(self) -> LineaBaseMaterializada:
        assert self.resultado is not None, f"El hilo {self.name} no terminó bien: {self.error!r}"
        return self.resultado

    def terminar(self) -> None:
        self.join(timeout=LIMITE)
        assert not self.is_alive(), f"El hilo {self.name} no terminó en {LIMITE} s"


def _pausar_el_hilo_a_en_insertar_niveles(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[threading.Event, threading.Event]:
    """Envuelve `insertar_niveles`: el hilo `A` escribe sus niveles y espera a que se le libere.

    Devuelve `(dentro, liberar)`: `dentro` se activa cuando A ya escribió y se pausó; `liberar` lo
    reanuda. Si nadie lo libera en `LIMITE` segundos, A falla con `AssertionError` en vez de colgarse.
    El hilo `B` pasa por la envoltura sin pausarse.
    """
    original = repositorio_linea_base.insertar_niveles
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(sesion_bd: Session, obra_id: uuid.UUID, niveles: Sequence[NivelNuevo]) -> None:
        original(sesion_bd, obra_id, niveles)
        if threading.current_thread().name == "A":
            dentro.set()
            if not liberar.wait(timeout=LIMITE):
                raise AssertionError("El hilo A nunca fue liberado")

    monkeypatch.setattr(repositorio_linea_base, "insertar_niveles", envoltura)
    return dentro, liberar


# --------------------------------------------------------------------------- TC-A22


def test_tkt017_caa10_dos_confirmaciones_simultaneas(
    obra: Obra, contexto: Callable[[], ContextoPresupuesto]
) -> None:
    """TC-A22 · CA-A10 · RN-01 — dos confirmaciones a la vez de la misma obra: gana una sola.

    La que pierde responde `REEMPLAZO_NO_CONFIRMADO` (llegó después del commit de la otra) o
    `ConcurrenciaVencida`; nunca un conflicto de restricción ni una jerarquía mezclada. Queda una
    línea base, un nivel, un concepto y las apariciones de una sola importación, y un solo `CONFIRMAR`.
    El resultado depende de quién llega primero: `TC-A23` es la prueba determinista del bloqueo.
    """
    ctx = contexto()
    salida = threading.Barrier(2, timeout=LIMITE)

    def confirmar(importacion: uuid.UUID) -> Callable[[], LineaBaseMaterializada]:
        def correr() -> LineaBaseMaterializada:
            salida.wait()
            return obra.confirmar(ctx, importacion)

        return correr

    hilos = [
        Hilo("A", confirmar(obra.importacion_1)),
        Hilo("B", confirmar(obra.importacion_2)),
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.terminar()

    ganadores = [h for h in hilos if h.error is None]
    perdedores = [h for h in hilos if h.error is not None]
    assert len(ganadores) == 1, [h.error for h in hilos]
    assert len(perdedores) == 1
    error = perdedores[0].error
    assert isinstance(error, ErrorContrato), (
        f"La perdedora debió dar un error del contrato: {error!r}"
    )
    if isinstance(error, ConflictoEstado):
        cuerpo = error.cuerpo(ROLES_DP, CORRELACION)
        assert (cuerpo["codigo"], cuerpo["mensaje"]) == (
            "REEMPLAZO_NO_CONFIRMADO",
            MENSAJE_REEMPLAZO,
        )
    else:
        assert isinstance(error, ConcurrenciaVencida)
        assert error.cuerpo(ROLES_DP, CORRELACION)["codigo"] == "BLOQUEO_VENCIDO"

    ganadora = ganadores[0]
    importacion_ganadora = obra.importacion_1 if ganadora.name == "A" else obra.importacion_2
    importacion_perdedora = obra.importacion_2 if ganadora.name == "A" else obra.importacion_1
    assert ganadora.exito().importacion_id == importacion_ganadora
    assert obra.cuenta("linea_base") == 1
    assert obra.cuenta("nivel") == 1
    assert obra.cuenta("concepto") == 1
    esperadas = _CANTIDADES["importacion_1" if ganadora.name == "A" else "importacion_2"]
    assert obra.cantidades() == list(esperadas)
    assert obra.filas("SELECT estado FROM importacion WHERE id = %s", importacion_ganadora) == [
        ("CONFIRMADO",)
    ]
    assert obra.filas("SELECT estado FROM importacion WHERE id = %s", importacion_perdedora) == [
        ("VALIDADO",)
    ]
    assert obra.cuenta("bitacora") == 1


# --------------------------------------------------------------------------- TC-A23


def test_tkt017_caa10_la_confirmacion_espera_el_bloqueo_de_la_obra(
    obra: Obra,
    contexto: Callable[[], ContextoPresupuesto],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-A23 · CA-A10 · RN-01 — mientras A tiene la obra, B espera; al soltarla, B ve el borrador de A.

    A se pausa dentro de `insertar_niveles` con la obra bloqueada y filas sin confirmar. B confirma
    otra importación de la misma obra y debe quedar detenido en el `SELECT ... FOR UPDATE` de la obra
    (`pg_blocking_pids`). Al liberar A, B no escribe: la obra ya tiene el borrador de A y B responde
    `REEMPLAZO_NO_CONFIRMADO`. Sin el bloqueo (`M-A1`) B no se detiene y la prueba falla al esperarlo.
    """
    ctx = contexto()
    dentro, liberar = _pausar_el_hilo_a_en_insertar_niveles(monkeypatch)
    a = Hilo("A", lambda: obra.confirmar(ctx, obra.importacion_1))
    b = Hilo("B", lambda: obra.confirmar(ctx, obra.importacion_2))
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE), "El hilo A no llegó a insertar_niveles"
        b.start()
        espera = esperar_hasta(obra.hay_alguien_esperando_la_obra, 5.0)
        assert espera, "B no quedó esperando el bloqueo de la obra mientras A la tenía"
        assert b.is_alive()
        assert obra.cuenta("linea_base") == 0, "Nada de A está confirmado todavía"
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    assert a.exito().importacion_id == obra.importacion_1
    assert isinstance(b.error, ConflictoEstado), b.error
    cuerpo = b.error.cuerpo(ROLES_DP, CORRELACION)
    assert (cuerpo["codigo"], cuerpo["mensaje"]) == ("REEMPLAZO_NO_CONFIRMADO", MENSAJE_REEMPLAZO)
    assert cuerpo["detalle"] == {
        "linea_base_borrador_id": str(a.exito().linea_base_id),
        "version": 1,
    }
    assert obra.cuenta("linea_base") == 1
    assert obra.cantidades() == list(_CANTIDADES["importacion_1"])
    assert obra.filas("SELECT estado FROM importacion WHERE id = %s", obra.importacion_2) == [
        ("VALIDADO",)
    ]
    assert obra.cuenta("bitacora") == 1


def test_tkt017_caa10_dos_confirmaciones_de_la_misma_importacion_se_serializan(
    obra: Obra,
    contexto: Callable[[], ContextoPresupuesto],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-A23 · CA-A10 · RN-01 — B confirma la misma importación que A: espera la importación y la ve `CONFIRMADO`.

    A se pausa dentro de `insertar_niveles` con la importación y la obra bloqueadas. B pide la misma
    importación con el reemplazo confirmado y su motivo: debe quedar detenido en el `SELECT ... FROM
    importacion ... FOR UPDATE` (`pg_blocking_pids`). Al liberar A, B lee `CONFIRMADO` y se rechaza
    antes de tocar la obra: sin el bloqueo de la importación, B habría leído `VALIDADO`, esperado a la
    obra, y habría descartado el borrador de A para confirmar la misma importación otra vez.
    """
    ctx = contexto()
    dentro, liberar = _pausar_el_hilo_a_en_insertar_niveles(monkeypatch)
    a = Hilo("A", lambda: obra.confirmar(ctx, obra.importacion_1))
    b = Hilo(
        "B",
        lambda: obra.confirmar(
            ctx, obra.importacion_1, reemplazar_borrador=True, motivo_reemplazo=MOTIVO
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE), "El hilo A no llegó a insertar_niveles"
        b.start()
        espera = esperar_hasta(obra.hay_alguien_esperando_la_importacion, 5.0)
        assert espera, "B no quedó esperando el bloqueo de la importación mientras A la tenía"
        assert b.is_alive()
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    assert a.exito().importacion_id == obra.importacion_1
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_ESTADO.format(estado="CONFIRMADO"),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"importacion_id": str(obra.importacion_1), "estado": "CONFIRMADO"},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert obra.cuenta("linea_base") == 1
    assert obra.cuenta("descartar") == 0
    assert obra.cuenta("bitacora") == 1
    assert obra.cantidades() == list(_CANTIDADES["importacion_1"])


def test_tkt017_caa10_la_confirmacion_espera_el_bloqueo_de_la_obra_y_vence(
    obra: Obra,
    contexto: Callable[[], ContextoPresupuesto],
    contexto_espera_corta: Callable[[], ContextoPresupuesto],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-A23 · CA-A10 · ADR-004 · RNF-16 — con `lock_timeout` de 200 ms, B recibe `BLOQUEO_VENCIDO`.

    El contrato completo: `CONCURRENCIA` con `espera_maxima_ms` 5000 (el `lock_timeout` del rol),
    `Retry-After: 1` y la acción `REINTENTAR` a `POST` de la ruta de confirmación de B, que se ve con
    cualquier rol. B no escribe nada; A termina bien.
    """
    dentro, liberar = _pausar_el_hilo_a_en_insertar_niveles(monkeypatch)
    a = Hilo("A", lambda: obra.confirmar(contexto(), obra.importacion_1))
    b = Hilo("B", lambda: obra.confirmar(contexto_espera_corta(), obra.importacion_2))
    contexto()
    contexto_espera_corta()
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE), "El hilo A no llegó a insertar_niveles"
        b.start()
        b.terminar()
    finally:
        liberar.set()
        a.terminar()

    assert isinstance(b.error, ConcurrenciaVencida), b.error
    assert b.error.estado_http == 409
    assert b.error.cabeceras() == {"Retry-After": "1"}
    ruta = f"/api/v1/importaciones/{obra.importacion_2}/confirmacion"
    reintentar = {"clave": "REINTENTAR", "metodo": "POST", "ruta": ruta}
    esperado = {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [reintentar],
        "correlacion_id": CORRELACION,
    }
    assert b.error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert b.error.cuerpo(frozenset({"COMPRAS"}), CORRELACION) == esperado

    assert a.error is None, a.error
    assert obra.cuenta("linea_base") == 1
    assert obra.cantidades() == list(_CANTIDADES["importacion_1"])
    assert obra.filas("SELECT estado FROM importacion WHERE id = %s", obra.importacion_2) == [
        ("VALIDADO",)
    ]
    assert obra.cuenta("bitacora") == 1


def test_tkt017_caa10_motor_espera_corta_es_del_rol_de_aplicacion_con_200_ms(
    motor_espera_corta: Engine,
) -> None:
    """A6c · `E-7` — la fixture entrega una sesión del rol de aplicación con `lock_timeout` de 200 ms."""
    with motor_espera_corta.connect() as conexion:
        usuario, espera = conexion.execute(
            text("SELECT current_user, current_setting('lock_timeout')")
        ).one()
    assert (usuario, espera) == ("cimenta_aplicacion", "200ms")
