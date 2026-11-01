"""Límite de intentos (TKT-057, fila 5): TC-17 a TC-22, el repositorio, con Docker.

Cubre las seis funciones de `cimenta.identidad.infraestructura.repositorio` que sostienen el límite
de intentos (`RNF-04`): `insertar_intento` con `credenciales_verificadas`, `bloquear_correo`,
`fallos_de_correo`, `fallos_de_origen`, `ultimo_exito_de_correo` y `fijar_bloqueado_hasta`. Los casos
de `abrir_sesion` y de HTTP (TC-23 a TC-37, fila 6) están al final, bajo «Fila 6».

La `Session` es la de `sesion_bd`, con el rol de aplicación. Las filas de `intento_acceso` que las
consultas deben leer se siembran con SQL directo sobre una conexión nueva en `autocommit`, para que
su rojo no dependa de `insertar_intento`; cada comprobación sobre lo que quedó en la base usa otra
conexión nueva. TC-22 usa dos conexiones reales de `motor_aplicacion` (sin `pool`, cada `Session` abre
la suya) en dos hilos, sincronizados con eventos y con tiempos máximos: nunca con `sleep`.

El símbolo de producción (`repositorio`) se importa **dentro** de cada caso, así cada uno falla por sí
solo y la recolección no se cae.
"""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import psycopg
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from contrato_error import LimiteIntentosExcedido, SesionInvalida

if TYPE_CHECKING:
    from cimenta.identidad.aplicacion.contexto import ContextoIdentidad

Conexion = psycopg.Connection[tuple[Any, ...]]

T0 = datetime(2026, 10, 30, 10, 0, tzinfo=UTC)
CORREO_DE_ANA = "ana@cimenta.test"
CORREO_DE_BETO = "beto@cimenta.test"
ORIGEN = "203.0.113.7"
OTRO_ORIGEN = "198.51.100.4"

# Cuánto se espera para dar por probado que una transacción SIGUE esperando el bloqueo, y cuánto
# para dar por perdido uno que debía llegar. El primero es la única espera "negativa" posible.
ESPERA_DE_BLOQUEO_S = 1.5
LIMITE_DE_ESPERA_S = 10.0


# --------------------------------------------------------------------------- ayudas


def sembrar_intento(
    conexion: Conexion,
    *,
    email: str,
    ocurrido_en: datetime,
    exitoso: bool = False,
    credenciales_verificadas: bool = True,
    origen_ip: str | None = None,
    usuario_id: uuid.UUID | None = None,
) -> None:
    """Una fila de `intento_acceso`, confirmada, escrita sin pasar por el repositorio."""
    conexion.execute(
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, credenciales_verificadas, "
        "ocurrido_en, origen_ip) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            uuid.uuid4(),
            email,
            usuario_id,
            exitoso,
            credenciales_verificadas,
            ocurrido_en,
            origen_ip,
        ),
    )


def minutos(n: float) -> timedelta:
    return timedelta(minutes=n)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


@pytest.fixture
def ana(sembrar_usuario: Callable[..., uuid.UUID]) -> uuid.UUID:
    return sembrar_usuario(CORREO_DE_ANA, "Clave-Ana-123", roles=("RESIDENTE",))


@pytest.fixture
def beto(sembrar_usuario: Callable[..., uuid.UUID]) -> uuid.UUID:
    return sembrar_usuario(CORREO_DE_BETO, "Clave-Beto-123", nombre="Beto Ruiz")


# --------------------------------------------------------------------------- TC-17


def test_tkt057_ca08_repositorio_insertar_intento_guarda_credenciales_verificadas(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-17 · CA-8 — insertar_intento escribe credenciales_verificadas tal como se le pasa."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    repositorio.insertar_intento(
        sesion_bd,
        email=CORREO_DE_ANA,
        usuario_id=ana,
        exitoso=True,
        credenciales_verificadas=True,
        ocurrido_en=T0,
        origen_ip=ORIGEN,
    )
    repositorio.insertar_intento(
        sesion_bd,
        email=CORREO_DE_BETO,
        usuario_id=None,
        exitoso=False,
        credenciales_verificadas=False,
        ocurrido_en=T0 + minutos(1),
        origen_ip=None,
    )
    sesion_bd.commit()

    filas = (
        lector()
        .execute(
            "SELECT email, usuario_id, exitoso, credenciales_verificadas, ocurrido_en, origen_ip "
            "FROM intento_acceso ORDER BY ocurrido_en"
        )
        .fetchall()
    )
    assert filas == [
        (CORREO_DE_ANA, ana, True, True, T0, ORIGEN),
        (CORREO_DE_BETO, None, False, False, T0 + minutos(1), None),
    ]


def test_tkt057_ca08_repositorio_insertar_intento_distingue_fallo_de_rechazo(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-17 · CA-8 — dos no-éxitos se distinguen solo por credenciales_verificadas."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    repositorio.insertar_intento(
        sesion_bd,
        email=CORREO_DE_ANA,
        usuario_id=None,
        exitoso=False,
        credenciales_verificadas=True,
        ocurrido_en=T0,
        origen_ip=ORIGEN,
    )
    repositorio.insertar_intento(
        sesion_bd,
        email=CORREO_DE_ANA,
        usuario_id=None,
        exitoso=False,
        credenciales_verificadas=False,
        ocurrido_en=T0 + minutos(1),
        origen_ip=ORIGEN,
    )
    sesion_bd.commit()

    filas = (
        lector()
        .execute(
            "SELECT ocurrido_en, exitoso, credenciales_verificadas FROM intento_acceso "
            "ORDER BY ocurrido_en"
        )
        .fetchall()
    )
    assert filas == [(T0, False, True), (T0 + minutos(1), False, False)]


def test_tkt057_ca08_repositorio_insertar_intento_exige_credenciales_verificadas(
    sesion_bd: Session,
) -> None:
    """TC-17 · CA-8 — omitir credenciales_verificadas es un error de llamada, no un valor por omisión."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    with pytest.raises(TypeError, match="credenciales_verificadas"):
        repositorio.insertar_intento(  # type: ignore[call-arg]
            sesion_bd,
            email=CORREO_DE_ANA,
            usuario_id=None,
            exitoso=False,
            ocurrido_en=T0,
            origen_ip=ORIGEN,
        )


# --------------------------------------------------------------------------- TC-18


def test_tkt057_ca03_repositorio_fallos_de_correo_ordena_y_respeta_los_extremos(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-18 · CA-3 — (desde, hasta]: desde es exclusivo, hasta inclusivo, ascendente."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    desde, hasta = T0, T0 + minutos(10)
    # Se siembran desordenados a propósito: el orden devuelto no puede ser el de inserción.
    for ocurrido_en in (
        hasta,
        T0 + minutos(1),
        desde,  # exactamente desde: queda fuera
        hasta + timedelta(microseconds=1),  # un microsegundo después de hasta: queda fuera
        desde - timedelta(microseconds=1),
        T0 + minutos(3),
    ):
        sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=ocurrido_en)

    fallos = repositorio.fallos_de_correo(sesion_bd, CORREO_DE_ANA, desde=desde, hasta=hasta)

    assert fallos == [T0 + minutos(1), T0 + minutos(3), hasta]


def test_tkt057_ca03_repositorio_fallos_de_correo_deja_fuera_lo_que_no_es_un_fallo_de_la_cuenta(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-18 · CA-3 · PA-T9 — no cuentan los éxitos, los rechazos ni las filas de otro correo."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(1))  # fallo verificado
    sembrar_intento(
        escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(2), exitoso=True, usuario_id=ana
    )
    sembrar_intento(
        escritor,
        email=CORREO_DE_ANA,
        ocurrido_en=T0 + minutos(3),
        credenciales_verificadas=False,  # rechazo por bloqueo: no es un fallo (PA-T9)
    )
    sembrar_intento(escritor, email=CORREO_DE_BETO, ocurrido_en=T0 + minutos(4))
    sembrar_intento(escritor, email="ANA@cimenta.test", ocurrido_en=T0 + minutos(5))
    sembrar_intento(
        escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(6), origen_ip=OTRO_ORIGEN
    )  # otro origen, misma cuenta: sí cuenta

    fallos = repositorio.fallos_de_correo(
        sesion_bd, CORREO_DE_ANA, desde=T0, hasta=T0 + minutos(10)
    )

    assert fallos == [T0 + minutos(1), T0 + minutos(6)]


def test_tkt057_ca03_repositorio_fallos_de_correo_sin_nada_devuelve_lista_vacia(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-18 · CA-3 — sin filas que cumplan, una lista vacía y no None."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sembrar_intento(lector(), email=CORREO_DE_BETO, ocurrido_en=T0 + minutos(1))

    fallos = repositorio.fallos_de_correo(
        sesion_bd, CORREO_DE_ANA, desde=T0, hasta=T0 + minutos(10)
    )

    assert fallos == []


# --------------------------------------------------------------------------- TC-19


def test_tkt057_ca06_repositorio_fallos_de_origen_ordena_y_respeta_los_extremos(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-19 · CA-6 — (desde, hasta]: desde es exclusivo, hasta inclusivo, ascendente."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    desde, hasta = T0, T0 + minutos(10)
    for ocurrido_en in (
        hasta,
        T0 + minutos(1),
        desde,
        hasta + timedelta(microseconds=1),
        desde - timedelta(microseconds=1),
        T0 + minutos(3),
    ):
        sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=ocurrido_en, origen_ip=ORIGEN)

    fallos = repositorio.fallos_de_origen(sesion_bd, ORIGEN, desde=desde, hasta=hasta)

    assert fallos == [T0 + minutos(1), T0 + minutos(3), hasta]


def test_tkt057_ca06_repositorio_fallos_de_origen_deja_fuera_lo_que_no_es_un_fallo_del_origen(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-19 · CA-6 · PA-T9 — no cuentan éxitos, rechazos, otros orígenes ni filas sin origen."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    # Cuentan: fallos verificados de cualquier correo desde ese origen.
    sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(1), origen_ip=ORIGEN)
    sembrar_intento(escritor, email=CORREO_DE_BETO, ocurrido_en=T0 + minutos(2), origen_ip=ORIGEN)
    sembrar_intento(
        escritor, email="nadie@cimenta.test", ocurrido_en=T0 + minutos(3), origen_ip=ORIGEN
    )
    # No cuentan.
    sembrar_intento(
        escritor,
        email=CORREO_DE_ANA,
        ocurrido_en=T0 + minutos(4),
        exitoso=True,
        usuario_id=ana,
        origen_ip=ORIGEN,
    )
    sembrar_intento(
        escritor,
        email=CORREO_DE_ANA,
        ocurrido_en=T0 + minutos(5),
        credenciales_verificadas=False,
        origen_ip=ORIGEN,
    )
    sembrar_intento(
        escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(6), origen_ip=OTRO_ORIGEN
    )
    sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(7), origen_ip=None)

    fallos = repositorio.fallos_de_origen(sesion_bd, ORIGEN, desde=T0, hasta=T0 + minutos(10))

    assert fallos == [T0 + minutos(1), T0 + minutos(2), T0 + minutos(3)]


def test_tkt057_ca06_repositorio_fallos_de_origen_sin_nada_devuelve_lista_vacia(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-19 · CA-6 — sin filas que cumplan, una lista vacía y no None."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sembrar_intento(
        lector(), email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(1), origen_ip=OTRO_ORIGEN
    )

    fallos = repositorio.fallos_de_origen(sesion_bd, ORIGEN, desde=T0, hasta=T0 + minutos(10))

    assert fallos == []


# --------------------------------------------------------------------------- TC-20


def test_tkt057_ca05_repositorio_ultimo_exito_de_correo_devuelve_el_mas_reciente_hasta_hasta(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-20 · CA-5 — el éxito más reciente con ocurrido_en <= hasta, el extremo incluido."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    for ocurrido_en in (T0 + minutos(7), T0 + minutos(1), T0 + minutos(12)):
        sembrar_intento(
            escritor,
            email=CORREO_DE_ANA,
            ocurrido_en=ocurrido_en,
            exitoso=True,
            usuario_id=ana,
        )
    # Ruido que no cuenta: fallos posteriores y el éxito de otro correo, más reciente que todos.
    sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(9))
    sembrar_intento(escritor, email=CORREO_DE_BETO, ocurrido_en=T0 + minutos(8), exitoso=True)

    assert repositorio.ultimo_exito_de_correo(
        sesion_bd, CORREO_DE_ANA, hasta=T0 + minutos(10)
    ) == T0 + minutos(7)
    assert repositorio.ultimo_exito_de_correo(
        sesion_bd, CORREO_DE_ANA, hasta=T0 + minutos(7)
    ) == T0 + minutos(7)
    assert repositorio.ultimo_exito_de_correo(
        sesion_bd, CORREO_DE_ANA, hasta=T0 + minutos(7) - timedelta(microseconds=1)
    ) == T0 + minutos(1)


def test_tkt057_ca05_repositorio_ultimo_exito_de_correo_sin_exito_devuelve_none(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-20 · CA-5 — sin éxito del correo hasta `hasta`, None: fallos, rechazos y otro correo no valen."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    escritor = lector()
    sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(1))
    sembrar_intento(
        escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(2), credenciales_verificadas=False
    )
    sembrar_intento(escritor, email=CORREO_DE_BETO, ocurrido_en=T0 + minutos(3), exitoso=True)
    # Un éxito de Ana, pero después de `hasta`.
    sembrar_intento(
        escritor, email=CORREO_DE_ANA, ocurrido_en=T0 + minutos(20), exitoso=True, usuario_id=ana
    )

    assert (
        repositorio.ultimo_exito_de_correo(sesion_bd, CORREO_DE_ANA, hasta=T0 + minutos(10)) is None
    )


# --------------------------------------------------------------------------- TC-21


def test_tkt057_ca01_repositorio_fijar_bloqueado_hasta_no_toca_actualizado_en(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-21 · CA-1 — escribe bloqueado_hasta; no es un cambio de datos del usuario (asumido)."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    antes = (
        lector()
        .execute("SELECT bloqueado_hasta, actualizado_en FROM usuario WHERE id = %s", (ana,))
        .fetchone()
    )
    assert antes is not None
    assert antes[0] is None
    hasta = T0 + minutos(15)

    repositorio.fijar_bloqueado_hasta(sesion_bd, ana, hasta)
    sesion_bd.commit()

    despues = (
        lector()
        .execute("SELECT bloqueado_hasta, actualizado_en FROM usuario WHERE id = %s", (ana,))
        .fetchone()
    )
    assert despues == (hasta, antes[1])


def test_tkt057_ca01_repositorio_fijar_bloqueado_hasta_solo_toca_al_usuario_indicado(
    sesion_bd: Session, ana: uuid.UUID, beto: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-21 · CA-1 — el UPDATE lleva WHERE id: el otro usuario conserva su bloqueo (ninguno)."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    repositorio.fijar_bloqueado_hasta(sesion_bd, ana, T0 + minutos(15))
    sesion_bd.commit()

    registros = lector().execute("SELECT id, bloqueado_hasta FROM usuario").fetchall()
    filas = {identificador: bloqueado for identificador, bloqueado in registros}
    assert filas == {ana: T0 + minutos(15), beto: None}


def test_tkt057_ca01_repositorio_fijar_bloqueado_hasta_no_confirma(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-21 · CA-1 · regla 8 — escribe en la transacción de quien llama; si esta se deshace, no queda."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    repositorio.fijar_bloqueado_hasta(sesion_bd, ana, T0 + minutos(15))
    sesion_bd.rollback()

    fila = lector().execute("SELECT bloqueado_hasta FROM usuario WHERE id = %s", (ana,)).fetchone()
    assert fila == (None,)


# --------------------------------------------------------------------------- TC-22


class _Transaccion:
    """Una transacción en su propio hilo y su propia conexión: toma el bloqueo del correo y lo retiene.

    `avanzo` se enciende cuando `bloquear_correo` regresó (la transacción tiene el bloqueo) o cuando
    falló (el error queda en `error`), de modo que ni un error ni un bloqueo perdido cuelgan la
    prueba. `soltar` es el evento con el que la prueba le dice que confirme; sin él, confirma al
    instante. Todas las esperas tienen tiempo máximo.
    """

    def __init__(
        self, motor: Engine, correo: str, *, soltar: threading.Event | None = None
    ) -> None:
        self._motor = motor
        self._correo = correo
        self._soltar = soltar
        self.avanzo = threading.Event()
        self.termino = threading.Event()
        self.error: BaseException | None = None
        self._hilo = threading.Thread(target=self._correr, daemon=True)

    def iniciar(self) -> None:
        self._hilo.start()

    def esperar_fin(self) -> None:
        if self._hilo.ident is not None:  # una transacción que nunca arrancó no se espera
            self._hilo.join(timeout=LIMITE_DE_ESPERA_S)

    def _correr(self) -> None:
        import cimenta.identidad.infraestructura.repositorio as repositorio

        try:
            with Session(self._motor) as bd:
                repositorio.bloquear_correo(bd, self._correo)
                self.avanzo.set()
                if self._soltar is not None:
                    self._soltar.wait(timeout=LIMITE_DE_ESPERA_S)
                bd.commit()
        except BaseException as fallo:
            self.error = fallo
            self.avanzo.set()
        finally:
            self.termino.set()


def test_tkt057_ca01_repositorio_bloquear_correo_serializa_las_transacciones_del_mismo_correo(
    motor_aplicacion: Engine,
) -> None:
    """TC-22 · CA-1 — la segunda transacción sobre el mismo correo espera a que la primera confirme."""
    soltar_primera = threading.Event()
    primera = _Transaccion(motor_aplicacion, CORREO_DE_ANA, soltar=soltar_primera)
    segunda = _Transaccion(motor_aplicacion, CORREO_DE_ANA)
    try:
        primera.iniciar()
        assert primera.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "La primera transacción no obtuvo el bloqueo."
        )
        assert primera.error is None, f"La primera transacción falló: {primera.error!r}"

        segunda.iniciar()
        paso_sin_esperar = segunda.avanzo.wait(ESPERA_DE_BLOQUEO_S)
        assert not paso_sin_esperar, (
            "La segunda transacción obtuvo el bloqueo del mismo correo mientras la primera "
            f"lo retenía (error: {segunda.error!r})."
        )

        soltar_primera.set()  # la primera confirma y libera el bloqueo
        assert segunda.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "La segunda transacción no obtuvo el bloqueo tras confirmar la primera."
        )
        assert segunda.error is None, f"La segunda transacción falló: {segunda.error!r}"
    finally:
        soltar_primera.set()
        primera.esperar_fin()
        segunda.esperar_fin()


def test_tkt057_ca01_repositorio_bloquear_correo_no_bloquea_a_otro_correo(
    motor_aplicacion: Engine,
) -> None:
    """TC-22 · CA-1 — mientras la primera retiene el correo de Ana, la de Beto no espera."""
    soltar_primera = threading.Event()
    primera = _Transaccion(motor_aplicacion, CORREO_DE_ANA, soltar=soltar_primera)
    otra = _Transaccion(motor_aplicacion, CORREO_DE_BETO)
    try:
        primera.iniciar()
        assert primera.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "La primera transacción no obtuvo el bloqueo."
        )
        assert primera.error is None, f"La primera transacción falló: {primera.error!r}"

        otra.iniciar()
        assert otra.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "La transacción de otro correo quedó esperando el bloqueo de Ana."
        )
        assert otra.error is None, f"La transacción de otro correo falló: {otra.error!r}"
        assert not primera.termino.is_set(), (
            "La primera ya había terminado: la prueba no probó nada."
        )
    finally:
        soltar_primera.set()
        primera.esperar_fin()
        otra.esperar_fin()


def test_tkt057_ca01_repositorio_bloquear_correo_distingue_mayusculas_porque_no_normaliza(
    motor_aplicacion: Engine,
) -> None:
    """TC-22 · CA-1 — el repositorio no normaliza: la clave es el correo que se le pasa, tal cual."""
    soltar_primera = threading.Event()
    primera = _Transaccion(motor_aplicacion, "ana@cimenta.test", soltar=soltar_primera)
    otra = _Transaccion(motor_aplicacion, "ANA@cimenta.test")
    try:
        primera.iniciar()
        assert primera.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "La primera transacción no obtuvo el bloqueo."
        )
        assert primera.error is None, f"La primera transacción falló: {primera.error!r}"

        otra.iniciar()
        assert otra.avanzo.wait(LIMITE_DE_ESPERA_S), (
            "El bloqueo normalizó el correo: normalizar es del dominio, no del repositorio."
        )
        assert otra.error is None, f"La otra transacción falló: {otra.error!r}"
    finally:
        soltar_primera.set()
        primera.esperar_fin()
        otra.esperar_fin()


# =========================================================================== Fila 6
# TC-23 a TC-37: `abrir_sesion` con el límite (aplicación) y el contrato por HTTP.
#
# Los casos de aplicación llaman a `abrir_sesion` con el contexto real de `aplicacion_identidad` (su
# `RelojDePrueba`, su configuración 5/20/15 min) y avanzan ese reloj: nunca hay `sleep`. Cada intento
# anota el instante en que ocurrió, para comparar contra `usuario.bloqueado_hasta` y contra los
# segundos que faltan. Los casos de HTTP usan `cliente` y envían el par de token CSRF que `POST /sesion`
# exige desde la fila 8.

RAIZ = Path(__file__).resolve().parents[2]
RUTA_SESION = "/api/v1/sesion"
COOKIE_CSRF = "cimenta_csrf"
CABECERA_CSRF = "X-CSRF-Token"
TOKEN_CSRF = "token-csrf-de-la-prueba"
CABECERA_CORRELACION = "X-Correlacion-Id"
CORRELACION = "corr-0057-prueba"
AGENTE_USUARIO = "Prueba/1.0"
CONTRASENA_DE_ANA = "Clave-Ana-123"
CONTRASENA_DE_BETO = "Clave-Beto-123"
CONTRASENA_EQUIVOCADA = "Clave-Equivocada-9"
CORREO_INEXISTENTE = "nadie@cimenta.test"
MENSAJE_LITERAL_DEL_LIMITE = (
    "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo."
)
MENSAJE_LITERAL_DE_CREDENCIALES = "El correo o la contraseña no son correctos."
BLOQUEO = timedelta(minutes=15)
SEGUNDO = timedelta(seconds=1)
SIN_PASO = timedelta(0)


class RelojDePrueba(Protocol):
    """Lo que estas pruebas usan de la *fixture* `reloj_de_prueba` de `conftest.py`."""

    ahora: datetime

    def __call__(self) -> datetime: ...

    def avanzar(self, delta: timedelta) -> None: ...


@dataclass(frozen=True)
class Resultado:
    """Lo que devolvió un intento (la sesión abierta o el error del contrato) y cuándo ocurrió."""

    salida: object
    instante: datetime


class ContadorDeContrasenas:
    """Envuelve las contraseñas reales y anota cada verificación (TC-24, TC-33, TC-35)."""

    def __init__(self, interior: Any) -> None:
        self._interior = interior
        self.hash_de_descarte: str = interior.hash_de_descarte
        self.verificaciones: list[tuple[str, str]] = []

    def derivar(self, contrasena: str) -> str:
        return cast("str", self._interior.derivar(contrasena))

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        self.verificaciones.append((contrasena, hash_guardado))
        return cast("bool", self._interior.verificar(contrasena, hash_guardado))


class ContrasenasEnBarrera(ContadorDeContrasenas):
    """TC-33: cada verificación espera a la otra en una barrera de dos, con tiempo máximo de 2 s.

    Sin el bloqueo de aviso, dos intentos simultáneos llegan los dos a verificar y la barrera los suelta
    juntos. Con el bloqueo, el segundo nunca llega: el primero agota la barrera, se ignora
    `BrokenBarrierError` y sigue. Ninguna espera es un `sleep`.
    """

    def __init__(self, interior: Any) -> None:
        super().__init__(interior)
        self._barrera = threading.Barrier(2, timeout=2)

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        self.verificaciones.append((contrasena, hash_guardado))
        with contextlib.suppress(threading.BrokenBarrierError):
            self._barrera.wait()
        return cast("bool", self._interior.verificar(contrasena, hash_guardado))


@functools.cache
def borrador() -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")),
    )


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador OpenAPI."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def intentar(
    contexto: ContextoIdentidad,
    reloj: RelojDePrueba,
    correo: str,
    contrasena: str = CONTRASENA_EQUIVOCADA,
    *,
    origen_ip: str = ORIGEN,
    despues: timedelta = SIN_PASO,
) -> Resultado:
    """Un `abrir_sesion`; los errores del contrato se devuelven, cualquier otro se propaga."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    instante = reloj.ahora
    salida: object
    try:
        salida = abrir_sesion(
            contexto,
            correo_escrito=correo,
            contrasena=contrasena,
            origen_ip=origen_ip,
            agente_usuario=AGENTE_USUARIO,
        )
    except (SesionInvalida, LimiteIntentosExcedido) as error:
        salida = error
    reloj.avanzar(despues)
    return Resultado(salida, instante)


def fallar(
    contexto: ContextoIdentidad,
    reloj: RelojDePrueba,
    correo: str,
    veces: int,
    *,
    origen_ip: str = ORIGEN,
    despues: timedelta = SIN_PASO,
) -> list[Resultado]:
    """`veces` intentos con la contraseña equivocada; `despues` se avanza tras cada uno."""
    return [
        intentar(contexto, reloj, correo, origen_ip=origen_ip, despues=despues)
        for _ in range(veces)
    ]


def exigir_fallos(resultados: Sequence[Resultado]) -> None:
    """Cada intento es un `401 SESION CREDENCIALES_INVALIDAS`: el contrato de siempre, sin cambios."""
    for resultado in resultados:
        error = resultado.salida
        assert isinstance(error, SesionInvalida), (
            f"Se esperaba un 401 de credenciales inválidas; llegó {error!r}."
        )
        assert error.estado_http == 401
        assert error.motivo.value == "CREDENCIALES_INVALIDAS"
        assert error.mensaje == MENSAJE_LITERAL_DE_CREDENCIALES


def exigir_bloqueo(resultado: Resultado, *, reintentar_en_s: int) -> LimiteIntentosExcedido:
    """El contrato de error completo del `429`: tipo, estado, mensaje, cifras, cabecera y claves."""
    error = resultado.salida
    assert isinstance(error, LimiteIntentosExcedido), (
        f"Se esperaba LimiteIntentosExcedido (429); llegó {error!r}."
    )
    assert error.tipo == "LIMITE_INTENTOS"
    assert error.estado_http == 429
    assert error.mensaje == MENSAJE_LITERAL_DEL_LIMITE
    assert error.reintentar_en_s == reintentar_en_s
    assert 1 <= error.reintentar_en_s <= 900
    assert error.cuerpo(frozenset(), CORRELACION) == {
        "tipo": "LIMITE_INTENTOS",
        "mensaje": MENSAJE_LITERAL_DEL_LIMITE,
        "reintentar_en_s": reintentar_en_s,
        "correlacion_id": CORRELACION,
    }
    assert error.cabeceras() == {"Retry-After": str(reintentar_en_s)}
    return error


def exigir_sesion_abierta(resultado: Resultado, usuario_id: uuid.UUID) -> None:
    from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado

    assert isinstance(resultado.salida, UsuarioAutenticado), (
        f"Se esperaba una sesión abierta; llegó {resultado.salida!r}."
    )
    assert resultado.salida.usuario_id == usuario_id


def bloqueado_hasta_de(conexion: Conexion, usuario_id: uuid.UUID) -> datetime | None:
    fila = conexion.execute(
        "SELECT bloqueado_hasta FROM usuario WHERE id = %s", (usuario_id,)
    ).fetchone()
    assert fila is not None
    return cast("datetime | None", fila[0])


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


def usuarios_con_bloqueo(conexion: Conexion) -> int:
    fila = conexion.execute(
        "SELECT count(*) FROM usuario WHERE bloqueado_hasta IS NOT NULL"
    ).fetchone()
    assert fila is not None
    return int(fila[0])


def filas_de_intento(conexion: Conexion, *, desde: datetime) -> list[dict[str, Any]]:
    """Las filas de `intento_acceso` (sin `id`) desde ese instante, por instante."""
    filas = conexion.execute(
        "SELECT email, usuario_id, exitoso, credenciales_verificadas, ocurrido_en, origen_ip "
        "FROM intento_acceso WHERE ocurrido_en >= %s ORDER BY ocurrido_en, exitoso",
        (desde,),
    ).fetchall()
    nombres = (
        "email",
        "usuario_id",
        "exitoso",
        "credenciales_verificadas",
        "ocurrido_en",
        "origen_ip",
    )
    return [dict(zip(nombres, fila, strict=True)) for fila in filas]


def bloquear_origen(contexto: ContextoIdentidad, reloj: RelojDePrueba, origen_ip: str) -> None:
    """Veinte fallos desde `origen_ip` repartidos en cinco correos inexistentes (cuatro cada uno)."""
    for numero in range(20):
        exigir_fallos(
            fallar(contexto, reloj, f"intruso{numero % 5}@cimenta.test", 1, origen_ip=origen_ip)
        )


@pytest.fixture
def contexto(aplicacion_identidad: FastAPI) -> ContextoIdentidad:
    """El contexto de identidad real de la aplicación de prueba: su reloj es `reloj_de_prueba`."""
    return cast("ContextoIdentidad", aplicacion_identidad.state.identidad)


def con_contador(contexto: ContextoIdentidad) -> tuple[ContextoIdentidad, ContadorDeContrasenas]:
    contador = ContadorDeContrasenas(contexto.contrasenas)
    return dataclasses.replace(contexto, contrasenas=contador), contador


# --------------------------------------------------------------------------- mensaje


def test_tkt057_ca01_aplicacion_el_mensaje_del_limite_es_el_literal_del_diseno() -> None:
    """TC-23 · CA-1 — `MENSAJE_LIMITE_INTENTOS` existe y es el texto del diseño, igual para toda cuenta y origen."""
    from cimenta.identidad.aplicacion import sesiones

    assert sesiones.MENSAJE_LIMITE_INTENTOS == MENSAJE_LITERAL_DEL_LIMITE


# --------------------------------------------------------------------------- TC-23


def test_tkt057_ca01_aplicacion_cinco_fallos_y_el_sexto_intento_queda_bloqueado(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-23 · CA-1 · PA-T3 — cinco 401; el sexto, 429 con lo que falta; `bloqueado_hasta` = quinto fallo + 15 min.

    Los fallos van separados un minuto, para que «la hora del quinto» no sea la del primero. El quinto
    responde 401 (lectura literal de stack §6.6) y es el que escribe `usuario.bloqueado_hasta`.
    """
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 4, despues=minutos(1)))
    assert bloqueado_hasta_de(lector(), ana) is None

    quinto = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA)
    exigir_fallos([quinto])
    assert bloqueado_hasta_de(lector(), ana) == quinto.instante + BLOQUEO

    reloj_de_prueba.ahora = quinto.instante + timedelta(seconds=90.5)
    sexto = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA)

    exigir_bloqueo(sexto, reintentar_en_s=810)  # ⌈900 − 90,5⌉
    assert bloqueado_hasta_de(lector(), ana) == quinto.instante + BLOQUEO


def test_tkt057_ca01_aplicacion_cuatro_fallos_no_bloquean(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-23 · CA-1 — el umbral es cinco: tras cuatro fallos la contraseña correcta abre sesión."""
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 4, despues=SEGUNDO))

    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA), ana
    )
    assert bloqueado_hasta_de(lector(), ana) is None


# --------------------------------------------------------------------------- TC-24


def test_tkt057_ca02_aplicacion_bloqueada_la_contrasena_correcta_no_abre_sesion_ni_se_verifica(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-24 · CA-2 · RNF-04 — bloqueada y con la contraseña correcta: 429, sin fila en `sesion` y cero hashes verificados."""
    contexto_contado, contador = con_contador(contexto)
    exigir_fallos(fallar(contexto_contado, reloj_de_prueba, CORREO_DE_ANA, 5))
    reloj_de_prueba.avanzar(timedelta(minutes=2))
    contador.verificaciones.clear()

    resultado = intentar(contexto_contado, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    exigir_bloqueo(resultado, reintentar_en_s=780)
    assert contador.verificaciones == [], (
        "El bloqueo debe decidirse antes de verificar ningún hash."
    )
    assert contar(lector(), "sesion") == 0
    assert bloqueado_hasta_de(lector(), ana) is not None


# --------------------------------------------------------------------------- TC-25


def test_tkt057_ca03_aplicacion_el_bloqueo_vence_solo_a_los_quince_minutos(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-25 · CA-3 esc. 1 — bloqueo a las 10:00; a las 10:05 y 10:10 responde 429; a las 10:15:01 abre sesión."""
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5))

    reloj_de_prueba.ahora = t + timedelta(minutes=5)
    exigir_bloqueo(intentar(contexto, reloj_de_prueba, CORREO_DE_ANA), reintentar_en_s=600)
    reloj_de_prueba.ahora = t + timedelta(minutes=10)
    exigir_bloqueo(intentar(contexto, reloj_de_prueba, CORREO_DE_ANA), reintentar_en_s=300)

    reloj_de_prueba.ahora = t + timedelta(minutes=15, seconds=1)
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA), ana
    )


def test_tkt057_ca03_aplicacion_un_segundo_antes_del_vencimiento_sigue_bloqueado(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-25 · CA-3 — a los 14:59 falta 1 s y sigue el 429; a los 15:01 ya no hay bloqueo."""
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5))

    reloj_de_prueba.ahora = t + timedelta(minutes=14, seconds=59)
    exigir_bloqueo(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA), reintentar_en_s=1
    )
    reloj_de_prueba.ahora = t + timedelta(minutes=15, seconds=1)
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA), ana
    )


# --------------------------------------------------------------------------- TC-26


def test_tkt057_ca03_aplicacion_los_intentos_rechazados_no_alargan_el_bloqueo(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-26 · CA-3 esc. 2 · PA-T9 — veinte intentos durante el bloqueo: `bloqueado_hasta` sigue en las 10:15.

    Cada uno recibe lo que falta hasta entonces; a las 10:15:01 el siguiente es un fallo corriente (401).
    """
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5))
    assert bloqueado_hasta_de(lector(), ana) == t + BLOQUEO

    for numero in range(1, 21):
        reloj_de_prueba.ahora = t + timedelta(seconds=30 * numero)
        exigir_bloqueo(
            intentar(contexto, reloj_de_prueba, CORREO_DE_ANA),
            reintentar_en_s=900 - 30 * numero,
        )

    assert bloqueado_hasta_de(lector(), ana) == t + BLOQUEO
    reloj_de_prueba.ahora = t + timedelta(minutes=15, seconds=1)
    exigir_fallos([intentar(contexto, reloj_de_prueba, CORREO_DE_ANA)])


def test_tkt057_ca03_aplicacion_el_bloqueo_con_fallos_repartidos_sigue_vigente_a_los_veinte_minutos(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """CA-3 · RNF-04 · CA-19 mutante 17 · auditoría de arquitectura F001 — la mirada hacia atrás es de dos ventanas.

    NACE EN VERDE a propósito: es una prueba de mutación y en el código real pasa. Cinco fallos de
    Ana espaciados tres minutos (t = 0, 3, 6, 9 y 12) bloquean la cuenta hasta t + 27 min. A t + 20 min
    la contraseña correcta recibe 429 con `reintentar_en_s` = 420. La consulta del límite mira
    `2 × ventana` hacia atrás (30 min), y desde ahí los cinco fallos siguen a la vista. Si se mutara a
    `ahora - ventana` (15 min), a t + 20 min solo quedarían los fallos de t = 6, 9 y 12: tres, menos
    del umbral, y la cuenta abriría sesión con el bloqueo aún vigente. Ninguna otra prueba fijaba
    esa mirada, porque todas hacen sus fallos dentro de la misma ventana.
    """
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5, despues=minutos(3)))
    reloj_de_prueba.ahora = t + minutos(20)

    resultado = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    exigir_bloqueo(resultado, reintentar_en_s=420)


# --------------------------------------------------------------------------- TC-27


def test_tkt057_ca04_aplicacion_correo_inexistente_se_bloquea_y_los_rechazos_no_lo_alargan(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-27 · CA-4 · PA-T1 · PA-T11 — cinco 401, sexto 429; veinte más no lo alargan; ningún `usuario` cambia."""
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_INEXISTENTE, 5))

    exigir_bloqueo(intentar(contexto, reloj_de_prueba, CORREO_INEXISTENTE), reintentar_en_s=900)
    for numero in range(1, 21):
        reloj_de_prueba.ahora = t + timedelta(seconds=30 * numero)
        exigir_bloqueo(
            intentar(contexto, reloj_de_prueba, CORREO_INEXISTENTE),
            reintentar_en_s=900 - 30 * numero,
        )

    assert usuarios_con_bloqueo(lector()) == 0, (
        "El correo inexistente no debe tocar ningún usuario."
    )
    assert bloqueado_hasta_de(lector(), ana) is None
    reloj_de_prueba.ahora = t + timedelta(minutes=15, seconds=1)
    exigir_fallos([intentar(contexto, reloj_de_prueba, CORREO_INEXISTENTE)])


def test_tkt057_ca04_aplicacion_correo_inexistente_vence_a_la_misma_hora_que_una_cuenta_real(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-27 · CA-4 — mismo recuento, misma duración y mismo cuerpo para Ana y para un correo que no existe.

    Cada una desde su origen, para que el límite por origen no intervenga.
    """
    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5, origen_ip=ORIGEN))
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_INEXISTENTE, 5, origen_ip=OTRO_ORIGEN))

    for segundos, faltan in ((0, 900), (60, 840), (899, 1)):
        reloj_de_prueba.ahora = t + timedelta(seconds=segundos)
        real = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, origen_ip=ORIGEN)
        inexistente = intentar(contexto, reloj_de_prueba, CORREO_INEXISTENTE, origen_ip=OTRO_ORIGEN)
        exigir_bloqueo(real, reintentar_en_s=faltan)
        exigir_bloqueo(inexistente, reintentar_en_s=faltan)

    reloj_de_prueba.ahora = t + timedelta(seconds=901)
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=ORIGEN),
        ana,
    )
    exigir_fallos([intentar(contexto, reloj_de_prueba, CORREO_INEXISTENTE, origen_ip=OTRO_ORIGEN)])


# --------------------------------------------------------------------------- TC-28


def test_tkt057_ca05_aplicacion_un_inicio_correcto_reinicia_el_recuento_de_la_cuenta(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-28 · CA-5 esc. 1 — cuatro fallos, un éxito, un fallo y tres más: todos 401, la cuenta no se bloquea."""
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 4, despues=SEGUNDO))
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, despues=SEGUNDO),
        ana,
    )

    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 1 + 3, despues=SEGUNDO))


def test_tkt057_ca05_aplicacion_tras_el_exito_el_recuento_vuelve_a_contar(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-28 · CA-5 — el éxito reinicia, no perdona: cinco fallos después de él bloquean y el sexto es 429."""
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 4, despues=SEGUNDO))
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, despues=SEGUNDO),
        ana,
    )
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5, despues=SEGUNDO))

    exigir_bloqueo(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA),
        reintentar_en_s=899,
    )


# --------------------------------------------------------------------------- TC-29


def test_tkt057_ca06_aplicacion_veinte_fallos_de_un_origen_bloquean_al_origen(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-29 · CA-6 · PA-T1 — veinte fallos desde 203.0.113.7 en cinco cuentas (cuatro cada una): el 21, con credenciales correctas, 429.

    Ninguna cuenta llega a cinco, así que ninguna se bloquea por sí misma ni escribe `bloqueado_hasta`.
    """
    cuentas = [f"cuenta{numero}@cimenta.test" for numero in range(5)]
    for numero, correo in enumerate(cuentas):
        sembrar_usuario(correo, f"Clave-Cuenta-{numero}")
    for _ in range(4):
        for correo in cuentas:
            exigir_fallos(fallar(contexto, reloj_de_prueba, correo, 1, origen_ip=ORIGEN))

    resultado = intentar(contexto, reloj_de_prueba, cuentas[0], "Clave-Cuenta-0", origen_ip=ORIGEN)

    exigir_bloqueo(resultado, reintentar_en_s=900)
    assert usuarios_con_bloqueo(lector()) == 0


def test_tkt057_ca06_aplicacion_diecinueve_fallos_de_un_origen_no_bloquean(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: Callable[..., uuid.UUID],
) -> None:
    """TC-29 · CA-6 — el umbral del origen es veinte: tras diecinueve, la contraseña correcta abre sesión."""
    ids = [sembrar_usuario(f"cuenta{numero}@cimenta.test", "Clave-Ok-1") for numero in range(5)]
    for vuelta in range(4):
        for numero in range(5):
            if vuelta == 3 and numero == 4:
                continue  # el fallo número 20
            exigir_fallos(
                fallar(
                    contexto, reloj_de_prueba, f"cuenta{numero}@cimenta.test", 1, origen_ip=ORIGEN
                )
            )

    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, "cuenta4@cimenta.test", "Clave-Ok-1", origen_ip=ORIGEN),
        ids[4],
    )


# --------------------------------------------------------------------------- TC-30


def test_tkt057_ca07_aplicacion_el_bloqueo_de_un_origen_no_alcanza_a_otro_origen(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-30 · CA-7 esc. 1 — con 203.0.113.7 bloqueado, Ana entra desde 198.51.100.4.

    Antes se comprueba que desde el origen bloqueado Ana sí recibe 429: sin eso la prueba no probaría nada.
    """
    bloquear_origen(contexto, reloj_de_prueba, ORIGEN)

    exigir_bloqueo(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=ORIGEN),
        reintentar_en_s=900,
    )
    exigir_sesion_abierta(
        intentar(
            contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=OTRO_ORIGEN
        ),
        ana,
    )


def test_tkt057_ca07_aplicacion_el_bloqueo_de_un_origen_caduca_solo(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-30 · CA-7 esc. 2 — el origen quedó bloqueado a las 10:00; a las 10:15:01 entra con credenciales correctas."""
    t = reloj_de_prueba.ahora
    bloquear_origen(contexto, reloj_de_prueba, ORIGEN)
    reloj_de_prueba.ahora = t + timedelta(minutes=14, seconds=59)
    exigir_bloqueo(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=ORIGEN),
        reintentar_en_s=1,
    )

    reloj_de_prueba.ahora = t + timedelta(minutes=15, seconds=1)

    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=ORIGEN),
        ana,
    )


# --------------------------------------------------------------------------- TC-31


@pytest.mark.usefixtures("beto")
def test_tkt057_ca08_aplicacion_cada_intento_deja_su_fila_con_el_correo_normalizado(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-31 · CA-8 esc. 1 · D-4 — éxito, contraseña errónea, correo inexistente y rechazo por bloqueo: cuatro filas.

    El correo va en minúsculas aunque se escriba «Ana@Cimenta.TEST»; `exitoso` es verdadero solo en la
    primera y `credenciales_verificadas` es falso solo en la cuarta (el rechazo, anónimo: sin usuario).
    """
    exigir_fallos(
        fallar(contexto, reloj_de_prueba, CORREO_DE_BETO, 5, origen_ip=OTRO_ORIGEN)
    )  # deja a Beto bloqueado
    reloj_de_prueba.avanzar(SEGUNDO)
    inicio = reloj_de_prueba.ahora

    exito = intentar(
        contexto, reloj_de_prueba, "Ana@Cimenta.TEST", CONTRASENA_DE_ANA, despues=SEGUNDO
    )
    equivocada = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, despues=SEGUNDO)
    inexistente = intentar(contexto, reloj_de_prueba, "Nadie@Cimenta.TEST", despues=SEGUNDO)
    rechazo = intentar(contexto, reloj_de_prueba, CORREO_DE_BETO, CONTRASENA_DE_BETO)

    exigir_sesion_abierta(exito, ana)
    exigir_fallos([equivocada, inexistente])
    exigir_bloqueo(rechazo, reintentar_en_s=896)  # el bloqueo de Beto se abrió 4 s antes
    assert filas_de_intento(lector(), desde=inicio) == [
        {
            "email": CORREO_DE_ANA,
            "usuario_id": ana,
            "exitoso": True,
            "credenciales_verificadas": True,
            "ocurrido_en": exito.instante,
            "origen_ip": ORIGEN,
        },
        {
            "email": CORREO_DE_ANA,
            "usuario_id": ana,
            "exitoso": False,
            "credenciales_verificadas": True,
            "ocurrido_en": equivocada.instante,
            "origen_ip": ORIGEN,
        },
        {
            "email": "nadie@cimenta.test",
            "usuario_id": None,
            "exitoso": False,
            "credenciales_verificadas": True,
            "ocurrido_en": inexistente.instante,
            "origen_ip": ORIGEN,
        },
        {
            "email": CORREO_DE_BETO,
            "usuario_id": None,
            "exitoso": False,
            "credenciales_verificadas": False,
            "ocurrido_en": rechazo.instante,
            "origen_ip": ORIGEN,
        },
    ]


# --------------------------------------------------------------------------- TC-32


def test_tkt057_ca06_aplicacion_los_rechazos_por_bloqueo_no_cuentan_para_el_origen(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-32 · PA-T9 — 19 fallos y 30 rechazos por bloqueo desde un origen: el origen no está bloqueado.

    Tres correos llegan a cinco fallos (15) y un cuarto a cuatro (19). Contra los tres bloqueados se
    hacen diez intentos cada uno: los treinta salen 429 de la cuenta, y si contaran como fallos del
    origen, 19 + 30 lo bloquearían. Ana, de otra cuenta, entra desde ese mismo origen.
    """
    for numero in range(3):
        exigir_fallos(fallar(contexto, reloj_de_prueba, f"intruso{numero}@cimenta.test", 5))
    exigir_fallos(fallar(contexto, reloj_de_prueba, "intruso3@cimenta.test", 4))

    for numero in range(3):
        for _ in range(10):
            exigir_bloqueo(
                intentar(contexto, reloj_de_prueba, f"intruso{numero}@cimenta.test"),
                reintentar_en_s=900,
            )

    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip=ORIGEN),
        ana,
    )


def test_tkt057_ca06_aplicacion_un_exito_no_reinicia_el_recuento_del_origen(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-32 · D-3 — un inicio correcto desde el origen en medio de los fallos no los borra: el 21 sale 429."""
    for numero in range(10):
        exigir_fallos(
            fallar(
                contexto, reloj_de_prueba, f"intruso{numero % 5}@cimenta.test", 1, despues=SEGUNDO
            )
        )
    exigir_sesion_abierta(
        intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, despues=SEGUNDO),
        ana,
    )
    for numero in range(10):
        exigir_fallos(
            fallar(
                contexto, reloj_de_prueba, f"intruso{numero % 5}@cimenta.test", 1, despues=SEGUNDO
            )
        )

    resultado = intentar(contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    exigir_bloqueo(resultado, reintentar_en_s=899)


# --------------------------------------------------------------------------- TC-33


def test_tkt057_ca01_aplicacion_dos_intentos_simultaneos_con_cuatro_fallos_previos_solo_uno_cuenta(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-33 · CA-1 — dos intentos a la vez con cuatro fallos previos: un 401 y un 429; quedan cinco fallos y un rechazo.

    El doble de `verificar` espera en `Barrier(2, timeout=2)` y ignora `BrokenBarrierError`. Sin el bloqueo
    de aviso los dos llegan a verificar, la barrera los suelta juntos y los dos salen 401. Con él, el segundo
    espera la transacción del primero y nunca verifica: una sola verificación en total.
    """
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    t = reloj_de_prueba.ahora
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 4))
    con_barrera = ContrasenasEnBarrera(contexto.contrasenas)
    contexto_concurrente = dataclasses.replace(contexto, contrasenas=con_barrera)
    salida_conjunta = threading.Barrier(2, timeout=LIMITE_DE_ESPERA_S)
    salidas: list[object] = []

    def correr() -> None:
        resultado: object
        try:
            salida_conjunta.wait()
            resultado = abrir_sesion(
                contexto_concurrente,
                correo_escrito=CORREO_DE_ANA,
                contrasena=CONTRASENA_EQUIVOCADA,
                origen_ip=ORIGEN,
                agente_usuario=AGENTE_USUARIO,
            )
        except BaseException as fallo:
            resultado = fallo
        salidas.append(resultado)

    hilos = [threading.Thread(target=correr, daemon=True) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=LIMITE_DE_ESPERA_S)

    assert all(not hilo.is_alive() for hilo in hilos), "Un intento no terminó a tiempo."
    assert len(salidas) == 2
    fallos = [s for s in salidas if isinstance(s, SesionInvalida)]
    bloqueos = [s for s in salidas if isinstance(s, LimiteIntentosExcedido)]
    assert len(fallos) == 1 and len(bloqueos) == 1, f"Salidas: {salidas!r}"
    assert 1 <= bloqueos[0].reintentar_en_s <= 900
    assert len(con_barrera.verificaciones) == 1, (
        "El intento rechazado nunca debe verificar un hash."
    )
    filas = filas_de_intento(lector(), desde=t)
    assert sum(1 for f in filas if not f["exitoso"] and f["credenciales_verificadas"]) == 5
    assert sum(1 for f in filas if not f["exitoso"] and not f["credenciales_verificadas"]) == 1
    assert bloqueado_hasta_de(lector(), ana) == t + BLOQUEO


# --------------------------------------------------------------------------- TC-34


def test_tkt057_car2_aplicacion_un_fallo_de_credenciales_no_escribe_en_la_bitacora(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-34 · CA-R2 · invariante 10 — un rechazo por credenciales, sin sesión, no deja fila en `bitacora`."""
    antes = contar(lector(), "bitacora")

    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 1))

    assert contar(lector(), "bitacora") == antes


def test_tkt057_car2_aplicacion_un_rechazo_por_bloqueo_no_escribe_en_la_bitacora(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-34 · CA-R2 · invariante 10 — el rechazo por bloqueo es anónimo (usuario_id NULL) y tampoco llega a `bitacora`.

    Se exige además el 429: sin él, la prueba no habría recorrido la ruta de rechazo por bloqueo.
    """
    exigir_fallos(fallar(contexto, reloj_de_prueba, CORREO_DE_ANA, 5))
    antes = contar(lector(), "bitacora")

    exigir_bloqueo(intentar(contexto, reloj_de_prueba, CORREO_DE_ANA), reintentar_en_s=900)

    assert contar(lector(), "bitacora") == antes


# --------------------------------------------------------------------------- TC-35


@pytest.mark.parametrize("escenario", ["cuenta_existente", "correo_inexistente"])
def test_tkt057_ca02_aplicacion_cada_fallo_verifica_exactamente_un_hash(
    escenario: str,
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
) -> None:
    """TC-35 · CA-2 · RNF-03 — un fallo, incluido el quinto que abre el bloqueo, verifica un solo hash (real o de descarte).

    La verificación del hash sigue ocurriendo antes de decidir el 401, para que el tiempo no revele la cuenta.
    """
    contexto_contado, contador = con_contador(contexto)
    correo = CORREO_DE_ANA if escenario == "cuenta_existente" else CORREO_INEXISTENTE

    for numero in range(1, 6):
        exigir_fallos([intentar(contexto_contado, reloj_de_prueba, correo)])
        assert len(contador.verificaciones) == numero, (
            f"Tras el fallo {numero}: {contador.verificaciones!r}"
        )
        assert contador.verificaciones[-1][0] == CONTRASENA_EQUIVOCADA
        if escenario == "correo_inexistente":
            assert contador.verificaciones[-1][1] == contexto.contrasenas.hash_de_descarte


# --------------------------------------------------------------------------- TC-36 y TC-37 · HTTP


def iniciar_por_http(cliente: TestClient, correo: str, contrasena: str) -> Any:
    """`POST /api/v1/sesion` con el par de token CSRF coincidente."""
    return cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers={
            "User-Agent": AGENTE_USUARIO,
            "Cookie": f"{COOKIE_CSRF}={TOKEN_CSRF}",
            CABECERA_CSRF: TOKEN_CSRF,
        },
    )


def exigir_429_por_http(respuesta: Any, *, reintentar_en_s: int) -> dict[str, Any]:
    """El contrato de error completo del `429`: cuerpo, esquema del borrador, `Retry-After` y correlación."""
    assert respuesta.status_code == 429, f"{respuesta.status_code}: {respuesta.text}"
    cuerpo = cast("dict[str, Any]", respuesta.json())
    assert "detail" not in cuerpo
    assert set(cuerpo) == {"tipo", "mensaje", "reintentar_en_s", "correlacion_id"}
    validar_contra("ErrorLimiteIntentos", cuerpo)
    assert cuerpo["tipo"] == "LIMITE_INTENTOS"
    assert cuerpo["mensaje"] == MENSAJE_LITERAL_DEL_LIMITE
    assert cuerpo["reintentar_en_s"] == reintentar_en_s
    assert respuesta.headers["Retry-After"] == str(reintentar_en_s)
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    assert respuesta.headers.get_list("set-cookie") == []
    return cuerpo


def exigir_401_por_http(respuesta: Any) -> None:
    assert respuesta.status_code == 401, f"{respuesta.status_code}: {respuesta.text}"
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == "CREDENCIALES_INVALIDAS"


def test_tkt057_ca01_el_sexto_intento_responde_429_con_el_contrato_completo(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-36 · CA-1 · CA-R7 — sexto intento: 429 `LIMITE_INTENTOS`, `Retry-After` = `reintentar_en_s`, correlación y esquema del borrador."""
    t = reloj_de_prueba.ahora
    for _ in range(5):
        exigir_401_por_http(iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA))
    reloj_de_prueba.ahora = t + timedelta(seconds=90.5)

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)

    exigir_429_por_http(respuesta, reintentar_en_s=810)
    assert bloqueado_hasta_de(lector(), ana) == t + BLOQUEO


def test_tkt057_ca02_bloqueada_la_contrasena_correcta_responde_429_sin_cookie_ni_sesion(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
) -> None:
    """TC-36 · CA-2 — durante el bloqueo, la contraseña correcta: 429, sin `cimenta_sesion` y sin fila en `sesion`."""
    for _ in range(5):
        exigir_401_por_http(iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA))

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    exigir_429_por_http(respuesta, reintentar_en_s=900)
    assert "cimenta_sesion" not in cliente.cookies
    assert contar(lector(), "sesion") == 0


def test_tkt057_ca04_el_429_de_un_correo_inexistente_es_igual_al_de_una_cuenta_real(
    cliente: TestClient, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """TC-37 · CA-4 — mismas claves, mismo `mensaje` y mismo `reintentar_en_s` por HTTP, exista o no el correo."""
    for correo in (CORREO_DE_ANA, CORREO_INEXISTENTE):
        for _ in range(5):
            exigir_401_por_http(iniciar_por_http(cliente, correo, CONTRASENA_EQUIVOCADA))
    reloj_de_prueba.avanzar(timedelta(seconds=90))

    real = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)
    inexistente = iniciar_por_http(cliente, CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA)

    cuerpo_real = exigir_429_por_http(real, reintentar_en_s=810)
    cuerpo_inexistente = exigir_429_por_http(inexistente, reintentar_en_s=810)
    assert set(cuerpo_inexistente) == set(cuerpo_real)
    assert cuerpo_inexistente["mensaje"] == cuerpo_real["mensaje"]
    assert cuerpo_inexistente["tipo"] == cuerpo_real["tipo"]


# --------------------------------------------------------------------------- ciclo de corrección 1
# F001 de arquitectura: el instante de un intento se lee con el candado ya tomado.
# F001 de SQL: las tres lecturas del límite usan índices parciales y no recorren los rechazos.


class _RelojEspiado:
    """Reloj que anota cada lectura en una bitácora compartida con el espía del candado."""

    def __init__(self, interior: RelojDePrueba, orden: list[str]) -> None:
        self._interior = interior
        self._orden = orden

    def __call__(self) -> datetime:
        self._orden.append("reloj")
        return self._interior()


def test_tkt057_ca01_aplicacion_el_reloj_se_lee_despues_de_tomar_el_candado_del_correo(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-1 · RNF-04 · auditoría F001 — `contexto.reloj()` se invoca después de `bloquear_correo`, nunca antes.

    Con el instante leído antes del candado, dos intentos simultáneos de la misma cuenta pueden
    ordenarse al revés de sus instantes: el que espera el candado consulta con `ocurrido_en <= su
    ahora` y no ve la fila que el otro escribió con un instante posterior. El orden de las llamadas
    es lo que cierra esa ventana, y se comprueba sin hilos.
    """
    import cimenta.identidad.infraestructura.repositorio as repositorio
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    orden: list[str] = []
    real = repositorio.bloquear_correo

    def espia(bd: Session, correo: str) -> None:
        orden.append("bloquear_correo")
        real(bd, correo)

    monkeypatch.setattr(repositorio, "bloquear_correo", espia)
    contexto_espiado = dataclasses.replace(contexto, reloj=_RelojEspiado(reloj_de_prueba, orden))

    with pytest.raises(SesionInvalida):
        abrir_sesion(
            contexto_espiado,
            correo_escrito=CORREO_DE_ANA,
            contrasena=CONTRASENA_EQUIVOCADA,
            origen_ip=ORIGEN,
            agente_usuario=AGENTE_USUARIO,
        )

    assert orden.count("bloquear_correo") == 1, f"Un solo candado por intento: {orden}"
    assert "reloj" in orden, f"abrir_sesion no leyó el reloj: {orden}"
    assert orden[0] == "bloquear_correo", (
        f"El reloj se leyó antes de tomar el candado del correo: {orden}"
    )
    assert orden.index("reloj") > orden.index("bloquear_correo")


def test_tkt057_ca01_aplicacion_el_intento_que_espera_el_candado_ve_el_fallo_que_le_precedio(
    contexto: ContextoIdentidad,
    reloj_de_prueba: RelojDePrueba,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-1 · RNF-04 · auditoría F001 — el sexto intento concurrente no verifica contraseña.

    Se reproduce la carrera sin hilos. Hay cuatro fallos verificados de Ana. Mientras el sexto
    intento espera el candado, el quinto confirma su fallo con un instante posterior (T+1 s) y el
    reloj llega a T+2 s. Con el instante leído antes del candado (T) el sexto no ve ese fallo,
    cuenta cuatro y verifica la contraseña correcta; leído después, cuenta cinco y responde 429
    con 899 s, sin verificar ningún hash y sin abrir sesión.
    """
    import cimenta.identidad.infraestructura.repositorio as repositorio

    t = reloj_de_prueba.ahora
    escritor = lector()
    for segundos in (4, 3, 2, 1):
        sembrar_intento(
            escritor,
            email=CORREO_DE_ANA,
            ocurrido_en=t - timedelta(seconds=segundos),
            origen_ip=ORIGEN,
        )
    real = repositorio.bloquear_correo

    def candado_tras_el_quinto_fallo(bd: Session, correo: str) -> None:
        # Lo que ocurrió mientras este intento esperaba: el quinto fallo confirmó y el tiempo avanzó.
        sembrar_intento(escritor, email=CORREO_DE_ANA, ocurrido_en=t + SEGUNDO, origen_ip=ORIGEN)
        reloj_de_prueba.ahora = t + 2 * SEGUNDO
        real(bd, correo)

    monkeypatch.setattr(repositorio, "bloquear_correo", candado_tras_el_quinto_fallo)
    contexto_contado, contador = con_contador(contexto)

    resultado = intentar(contexto_contado, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    exigir_bloqueo(resultado, reintentar_en_s=899)
    assert contador.verificaciones == [], (
        "El sexto intento verificó una contraseña pese al bloqueo."
    )
    assert contar(lector(), "sesion") == 0


# --------------------------------------------------------------------------- planes de consulta

RECHAZOS_POR_BLOQUEO = 2000
FALLOS_VERIFICADOS = 5
CORREO_ADVERSARIO = "intruso@cimenta.test"


def _sembrar_historial_adversario(
    conexion: Conexion, *, email: str, origen_ip: str | None, ocurrido_en: datetime
) -> None:
    """Un éxito antiguo, cinco fallos verificados y 2 000 rechazos por bloqueo, más recientes que ambos.

    Los rechazos (`exitoso = false`, `credenciales_verificadas = false`) son lo que infla el rango de
    un índice completo por `(email, ocurrido_en)`: hay que recorrerlos para llegar a los fallos.
    """
    conexion.execute(
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, credenciales_verificadas, "
        "ocurrido_en, origen_ip) VALUES (gen_random_uuid(), %s, NULL, true, true, %s, %s)",
        (email, ocurrido_en - timedelta(hours=1), origen_ip),
    )
    conexion.execute(
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, credenciales_verificadas, "
        "ocurrido_en, origen_ip) "
        "SELECT gen_random_uuid(), %s, NULL, false, true, %s + n * interval '1 second', %s "
        "FROM generate_series(1, %s) AS n",
        (email, ocurrido_en - timedelta(minutes=30), origen_ip, FALLOS_VERIFICADOS),
    )
    conexion.execute(
        "INSERT INTO intento_acceso (id, email, usuario_id, exitoso, credenciales_verificadas, "
        "ocurrido_en, origen_ip) "
        "SELECT gen_random_uuid(), %s, NULL, false, false, %s + n * interval '1 second', %s "
        "FROM generate_series(1, %s) AS n",
        (email, ocurrido_en - timedelta(minutes=20), origen_ip, RECHAZOS_POR_BLOQUEO),
    )


def _nodos_del_plan(nodo: dict[str, Any]) -> list[dict[str, Any]]:
    """El nodo y todos sus descendientes (incluidos los `InitPlan`), en preorden."""
    nodos = [nodo]
    for hijo in nodo.get("Plans", []):
        nodos.extend(_nodos_del_plan(hijo))
    return nodos


def _consulta_fallos_de_correo(bd: Session, hasta: datetime) -> object:
    import cimenta.identidad.infraestructura.repositorio as repositorio

    return repositorio.fallos_de_correo(
        bd, CORREO_DE_ANA, desde=hasta - timedelta(minutes=40), hasta=hasta
    )


def _consulta_fallos_de_origen(bd: Session, hasta: datetime) -> object:
    import cimenta.identidad.infraestructura.repositorio as repositorio

    return repositorio.fallos_de_origen(
        bd, ORIGEN, desde=hasta - timedelta(minutes=40), hasta=hasta
    )


def _consulta_ultimo_exito(bd: Session, hasta: datetime) -> object:
    import cimenta.identidad.infraestructura.repositorio as repositorio

    return repositorio.ultimo_exito_de_correo(bd, CORREO_DE_ANA, hasta=hasta)


@pytest.mark.parametrize(
    ("consulta", "indice", "filas_maximas"),
    [
        (
            _consulta_fallos_de_correo,
            "ix_intento_acceso_email_fallo_verificado",
            FALLOS_VERIFICADOS,
        ),
        (
            _consulta_fallos_de_origen,
            "ix_intento_acceso_origen_ip_fallo_verificado",
            FALLOS_VERIFICADOS,
        ),
        (_consulta_ultimo_exito, "ix_intento_acceso_email_exito", 1),
    ],
    ids=["fallos_de_correo", "fallos_de_origen", "ultimo_exito_de_correo"],
)
def test_tkt057_rnf04_las_lecturas_del_limite_usan_su_indice_parcial_y_no_leen_los_rechazos(
    consulta: Callable[[Session, datetime], object],
    indice: str,
    filas_maximas: int,
    sesion_bd: Session,
    conectar: Callable[..., Conexion],
    base_de_prueba: str,
) -> None:
    """RNF-04 · auditoría SQL F001 — cada lectura del límite entra por su índice parcial y toca solo lo que cuenta.

    Se siembran, para un correo y para un origen, un éxito, cinco fallos verificados y 2 000
    rechazos por bloqueo más recientes que ambos. La sentencia que emite el repositorio se captura
    tal cual y se explica con `EXPLAIN (ANALYZE, FORMAT JSON)`: el plan debe nombrar el índice
    parcial esperado, y ningún nodo puede descartar filas con un filtro (`Rows Removed by Filter`)
    ni devolver más filas que las que cuentan. Con índices completos, el plan recorre los rechazos.
    Se desactiva el barrido secuencial solo para que la elección sea entre índices y no dependa del
    tamaño de la tabla; no hay medida de tiempo.
    """
    t = T0 + timedelta(hours=2)
    with conectar("aplicacion", base_de_prueba) as escritor:
        _sembrar_historial_adversario(
            escritor, email=CORREO_DE_ANA, origen_ip=None, ocurrido_en=t - timedelta(minutes=1)
        )
        _sembrar_historial_adversario(
            escritor,
            email=CORREO_ADVERSARIO,
            origen_ip=ORIGEN,
            ocurrido_en=t - timedelta(minutes=1),
        )
    with conectar("migracion", base_de_prueba) as propietario:
        propietario.execute("ANALYZE intento_acceso")

    capturadas: list[tuple[str, Any]] = []

    def capturar(
        _conexion: Any, _cursor: Any, sentencia: str, parametros: Any, *_resto: Any
    ) -> None:
        capturadas.append((sentencia, parametros))

    motor = sesion_bd.get_bind()
    event.listen(motor, "before_cursor_execute", capturar)
    try:
        consulta(sesion_bd, t)
    finally:
        event.remove(motor, "before_cursor_execute", capturar)
    selects = [(s, p) for s, p in capturadas if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1, f"La lectura debe emitir una sola sentencia SELECT: {capturadas!r}"
    sentencia, parametros = selects[0]

    with conectar("aplicacion", base_de_prueba) as explicador:
        explicador.execute("SET enable_seqscan = off")
        fila = explicador.execute(
            "EXPLAIN (ANALYZE, FORMAT JSON) " + sentencia, parametros
        ).fetchone()
    assert fila is not None
    nodos = _nodos_del_plan(fila[0][0]["Plan"])
    de_indice = [n for n in nodos if "Index Name" in n]

    assert [n["Index Name"] for n in de_indice] == [indice], (
        f"Se esperaba el índice parcial {indice}; el plan usó "
        f"{[n.get('Index Name') for n in de_indice]} ({[n['Node Type'] for n in nodos]})."
    )
    assert [n["Node Type"] for n in nodos if n["Node Type"] == "Seq Scan"] == []
    descartadas = {
        n["Node Type"]: n["Rows Removed by Filter"]
        for n in nodos
        if n.get("Rows Removed by Filter")
    }
    assert descartadas == {}, f"El plan descarta filas con un filtro: {descartadas}"
    leidas = sum(int(n["Actual Rows"]) * int(n["Actual Loops"]) for n in de_indice)
    assert leidas <= filas_maximas, (
        f"El índice entregó {leidas} filas; solo cuentan {filas_maximas} (los rechazos no cuentan)."
    )


# --------------------------------------------------------------------------- ciclo de corrección 1 · F003
# El origen de un intento es una cubeta: una dirección IPv4 tal cual, un prefijo /64 en IPv6 y la
# cubeta fija «desconocido» sin cliente. Sin eso, quien tiene un /64 entero (2^64 direcciones) o
# un cliente sin dirección esquiva el límite de veinte fallos por origen.

PUERTO_DE_PRUEBA = 50000


def cliente_desde(aplicacion: FastAPI, host: str | None) -> TestClient:
    """Un cliente HTTPS cuyo `request.client.host` es `host`; con `None`, la petición no trae cliente."""
    return TestClient(
        aplicacion,
        base_url="https://testserver",
        client=None if host is None else (host, PUERTO_DE_PRUEBA),  # type: ignore[arg-type]
        raise_server_exceptions=False,
    )


def fallar_por_http(aplicacion: FastAPI, hosts: Sequence[str | None]) -> None:
    """Un fallo por HTTP desde cada `host`, repartidos en cinco correos inexistentes (cuatro cada uno)."""
    for numero, host in enumerate(hosts):
        respuesta = iniciar_por_http(
            cliente_desde(aplicacion, host),
            f"intruso{numero % 5}@cimenta.test",
            CONTRASENA_EQUIVOCADA,
        )
        exigir_401_por_http(respuesta)


def origenes_guardados(conexion: Conexion) -> set[str | None]:
    filas = conexion.execute("SELECT DISTINCT origen_ip FROM intento_acceso").fetchall()
    return {fila[0] for fila in filas}


def test_tkt057_ca06_http_veinte_fallos_desde_ipv6_del_mismo_64_bloquean_el_intento_21(
    aplicacion_identidad: FastAPI, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """CA-6 · RNF-04 · auditoría de seguridad F003 — veinte direcciones del mismo /64 comparten el límite del origen.

    Veinte fallos desde veinte direcciones distintas de `2001:db8::/64`, repartidos en cinco cuentas
    (ninguna llega a cinco): el intento 21, desde otra dirección del mismo /64 y con la contraseña
    correcta de Ana, responde 429 con el contrato completo. Todas las filas guardan la cubeta,
    no la dirección. Sin agrupar, cada dirección es un origen con un solo fallo y el 21 abre sesión.
    """
    fallar_por_http(aplicacion_identidad, [f"2001:db8::{numero + 1:x}" for numero in range(20)])

    respuesta = iniciar_por_http(
        cliente_desde(aplicacion_identidad, "2001:db8::ffff"), CORREO_DE_ANA, CONTRASENA_DE_ANA
    )

    exigir_429_por_http(respuesta, reintentar_en_s=900)
    assert origenes_guardados(lector()) == {"2001:db8::/64"}


def test_tkt057_ca07_http_dos_ipv6_de_64_distintos_no_comparten_cubeta(
    aplicacion_identidad: FastAPI, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """CA-7 · RNF-04 · auditoría de seguridad F003 — el bloqueo de un /64 no alcanza al /64 vecino.

    Antes se comprueba que el primer /64 queda bloqueado (429): sin eso la prueba no probaría nada.
    Después Ana, con su contraseña correcta, entra desde otro /64 y cada fila guarda su propia cubeta.
    """
    fallar_por_http(aplicacion_identidad, [f"2001:db8:0:1::{numero + 1:x}" for numero in range(20)])
    exigir_429_por_http(
        iniciar_por_http(
            cliente_desde(aplicacion_identidad, "2001:db8:0:1::ffff"),
            CORREO_DE_ANA,
            CONTRASENA_DE_ANA,
        ),
        reintentar_en_s=900,
    )

    respuesta = iniciar_por_http(
        cliente_desde(aplicacion_identidad, "2001:db8:0:2::1"), CORREO_DE_ANA, CONTRASENA_DE_ANA
    )

    assert respuesta.status_code == 200, respuesta.text
    assert origenes_guardados(lector()) == {"2001:db8:0:1::/64", "2001:db8:0:2::/64"}


def test_tkt057_ca06_http_sin_cliente_el_origen_es_una_cubeta_fija_y_tambien_se_bloquea(
    aplicacion_identidad: FastAPI, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """CA-6 · RNF-04 · auditoría de seguridad F003 — una petición sin `request.client` no esquiva el límite.

    Veinte fallos sin cliente en cinco cuentas y el 21, con la contraseña correcta, responde 429. Todas las
    filas guardan «desconocido»; con `None` el origen queda sin límite y el 21 abre sesión.
    """
    fallar_por_http(aplicacion_identidad, [None] * 20)

    respuesta = iniciar_por_http(
        cliente_desde(aplicacion_identidad, None), CORREO_DE_ANA, CONTRASENA_DE_ANA
    )

    exigir_429_por_http(respuesta, reintentar_en_s=900)
    assert origenes_guardados(lector()) == {"desconocido"}


def test_tkt057_ca06_aplicacion_la_cubeta_ipv6_es_un_origen_como_cualquier_otro(
    contexto: ContextoIdentidad, reloj_de_prueba: RelojDePrueba, ana: uuid.UUID
) -> None:
    """CA-6 · CA-7 · auditoría de seguridad F003 — `abrir_sesion` recibe la cubeta ya resuelta y no la interpreta.

    NACE EN VERDE a propósito: es regresión de la frontera entre capas. Veinte fallos desde la cubeta
    `2001:db8::/64` bloquean el 21 (429) y no alcanzan a la cubeta vecina `2001:db8:0:1::/64`, donde
    Ana entra. Fija que agrupar es cosa de la capa HTTP (`origen_de`) y que la aplicación sigue
    tratando el origen como un texto opaco.
    """
    bloquear_origen(contexto, reloj_de_prueba, "2001:db8::/64")

    exigir_bloqueo(
        intentar(
            contexto, reloj_de_prueba, CORREO_DE_ANA, CONTRASENA_DE_ANA, origen_ip="2001:db8::/64"
        ),
        reintentar_en_s=900,
    )
    exigir_sesion_abierta(
        intentar(
            contexto,
            reloj_de_prueba,
            CORREO_DE_ANA,
            CONTRASENA_DE_ANA,
            origen_ip="2001:db8:0:1::/64",
        ),
        ana,
    )
