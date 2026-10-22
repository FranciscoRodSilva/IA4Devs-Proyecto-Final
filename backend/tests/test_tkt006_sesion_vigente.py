"""Sesión vigente (TKT-006, entrega A, fila 6): `validar_sesion` y `cerrar_sesion_vigente`, con Docker.

Este archivo lo comparten dos filas del diseño. La **fila 6** escribe aquí los casos que llaman a los dos
casos de uso directamente, con el motor del rol de aplicación y un reloj de prueba, y TC-41 con sus dos
hermanos de concurrencia (dos transacciones reales). La **fila 7** añadirá debajo los casos HTTP de TC-32 a
TC-40 (`cliente` y `aplicacion_identidad`); el cierre por HTTP (TC-43 a TC-46) es de `test_tkt006_cierre.py`.

Convención de nombres, para que cada fila seleccione lo suyo:

- los casos de nivel de aplicación llevan `aplicacion` en el nombre;
- la palabra `concurrencia` aparece **solo** en los tres casos con dos transacciones (`-k "concurrencia"` es
  la verificación de la fila 6, tres veces seguidas);
- ningún caso HTTP de la fila 7 debe llevar ninguna de las dos palabras.

Contrato de error comprobado completo en cada rechazo: la excepción es `SesionInvalida` (`tipo` `SESION`,
`401`), su `motivo` es el esperado, su `mensaje` es el literal del diseño y su `cuerpo(...)` tiene exactamente
las claves `tipo`, `mensaje`, `motivo` y `correlacion_id`. Lo que se verifica en la base se lee con una
conexión **nueva** del rol de aplicación, nunca con la que escribió.

Los símbolos de producción que aún no existen (`validar_sesion`, `cerrar_sesion_vigente` y los tres mensajes
nuevos) se importan **dentro** de las ayudas y de los casos, no arriba ni en una *fixture*: así cada caso falla
por sí solo con el `ImportError` de `cimenta.identidad.aplicacion.sesiones` y la recolección no se cae.
"""

from __future__ import annotations

import functools
import io
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import psycopg
import pytest
import yaml
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy.engine import Engine

from contrato_error import SesionInvalida

if TYPE_CHECKING:
    from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado

Conexion = psycopg.Connection[tuple[Any, ...]]
SembrarUsuario = Callable[..., uuid.UUID]

# Mismo valor que `conftest.ENTORNO_DE_PRUEBA`: costes baratos de Argon2 (cada derivación, milisegundos).
ENTORNO_DE_PRUEBA = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
}
CORREO_DE_ANA = "ana@cimenta.test"
CONTRASENA_DE_ANA = "Clave-Correcta-1"
CORREO_DE_LUIS = "luis@cimenta.test"
CONTRASENA_DE_LUIS = "Clave-De-Luis-2"
ROLES_DE_ANA = ("RESIDENTE", "COMPRAS")
ORIGEN_IP = "10.0.0.7"
AGENTE_USUARIO = "Prueba/1.0"
CORRELACION = "corr-0006-prueba"
PLAZO_DEL_SONDEO_S = 10.0
MENSAJES_LITERALES = {
    "SIN_SESION": "No hay una sesión iniciada.",
    "SESION_CADUCADA": "La sesión caducó. Inicia sesión de nuevo.",
    "SESION_REVOCADA": "La sesión ya no es válida. Inicia sesión de nuevo.",
}
NOMBRE_DE_LA_CONSTANTE = {
    "SIN_SESION": "MENSAJE_SIN_SESION",
    "SESION_CADUCADA": "MENSAJE_SESION_CADUCADA",
    "SESION_REVOCADA": "MENSAJE_SESION_REVOCADA",
}


# --------------------------------------------------------------------------- ayudas de la prueba


class RelojDePrueba(Protocol):
    """Lo que estas pruebas usan de la *fixture* `reloj_de_prueba` de `conftest.py`."""

    ahora: datetime

    def __call__(self) -> datetime: ...

    def avanzar(self, delta: timedelta) -> None: ...


def crear_contexto(
    motor: Engine, reloj: RelojDePrueba, *, entorno: dict[str, str] | None = None
) -> ContextoIdentidad:
    """`ContextoIdentidad` real sobre el motor del rol de aplicación: ContrasenasArgon2 con costes baratos."""
    from sqlalchemy.orm import sessionmaker

    from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
    from cimenta.identidad.aplicacion.contexto import ContextoIdentidad
    from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2

    configuracion = ConfiguracionIdentidad.desde_entorno({**ENTORNO_DE_PRUEBA, **(entorno or {})})
    return ContextoIdentidad(
        fabrica_sesiones=lambda: sessionmaker(bind=motor, expire_on_commit=False),
        configuracion=configuracion,
        contrasenas=ContrasenasArgon2(configuracion),
        reloj=reloj,
    )


def abrir(
    contexto: ContextoIdentidad,
    correo: str = CORREO_DE_ANA,
    contrasena: str = CONTRASENA_DE_ANA,
) -> UsuarioAutenticado:
    """Abre una sesión real con `abrir_sesion` (verde desde la fila 5) y devuelve al usuario autenticado."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    return abrir_sesion(
        contexto,
        correo_escrito=correo,
        contrasena=contrasena,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )


def validar(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> UsuarioAutenticado:
    from cimenta.identidad.aplicacion.sesiones import validar_sesion

    return validar_sesion(contexto, sesion_id)


def cerrar(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> None:
    from cimenta.identidad.aplicacion.sesiones import cerrar_sesion_vigente

    cerrar_sesion_vigente(contexto, sesion_id)


def rechazar(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> SesionInvalida:
    """Llama a `validar_sesion` esperando un `401`; devuelve la excepción capturada."""
    with pytest.raises(SesionInvalida) as capturada:
        validar(contexto, sesion_id)
    return capturada.value


def exigir_contrato_de_sesion(error: SesionInvalida, motivo: str) -> None:
    """El contrato de error completo de CA-7, CA-8, CA-9 y CA-10: tipo, estado, motivo, mensaje y claves exactas."""
    import cimenta.identidad.aplicacion.sesiones as sesiones

    literal = MENSAJES_LITERALES[motivo]
    assert error.tipo == "SESION"
    assert error.estado_http == 401
    assert error.motivo.value == motivo
    assert error.mensaje == literal
    assert getattr(sesiones, NOMBRE_DE_LA_CONSTANTE[motivo]) == literal
    cuerpo = error.cuerpo(frozenset(), CORRELACION)
    assert cuerpo == {
        "tipo": "SESION",
        "mensaje": literal,
        "motivo": motivo,
        "correlacion_id": CORRELACION,
    }
    assert set(cuerpo) == {
        "tipo",
        "mensaje",
        "motivo",
        "correlacion_id",
    }  # sin `detail`, sin `acciones`


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


def fila_de_sesion(conexion: Conexion, sesion_id: uuid.UUID) -> dict[str, Any]:
    """La fila de `sesion` por nombre de columna; falla con nombre si no existe (la fila nunca se borra)."""
    fila = conexion.execute(
        "SELECT usuario_id, creada_en, expira_en, ultima_actividad, revocada_en, origen_ip, "
        "agente_usuario FROM sesion WHERE id = %s",
        (sesion_id,),
    ).fetchone()
    assert fila is not None, f"No hay ninguna sesión con id {sesion_id}."
    nombres = (
        "usuario_id",
        "creada_en",
        "expira_en",
        "ultima_actividad",
        "revocada_en",
        "origen_ip",
        "agente_usuario",
    )
    return dict(zip(nombres, fila, strict=True))


def ultimo_acceso_de(conexion: Conexion, usuario_id: uuid.UUID) -> Any:
    fila = conexion.execute(
        "SELECT ultimo_acceso FROM usuario WHERE id = %s", (usuario_id,)
    ).fetchone()
    assert fila is not None
    return fila[0]


def desactivar(conexion: Conexion, usuario_id: uuid.UUID) -> None:
    conexion.execute("UPDATE usuario SET activo = false WHERE id = %s", (usuario_id,))


def retirar_rol(conexion: Conexion, usuario_id: uuid.UUID, clave: str) -> None:
    conexion.execute(
        "DELETE FROM usuario_rol WHERE usuario_id = %s "
        "AND rol_id = (SELECT id FROM rol WHERE clave = %s)",
        (usuario_id, clave),
    )


def conceder_rol(conexion: Conexion, usuario_id: uuid.UUID, clave: str) -> None:
    conexion.execute(
        "INSERT INTO usuario_rol (id, usuario_id, rol_id) "
        "SELECT %s, %s, rol.id FROM rol WHERE rol.clave = %s",
        (uuid.uuid4(), usuario_id, clave),
    )


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


# --------------------------------------------------------------------------- CA-6 · sesión vigente


def test_tkt006_ca06_aplicacion_validar_devuelve_usuario_y_roles_actuales(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-6 esc. 1 · M3 · M7 — `validar_sesion` devuelve al usuario con los roles de ese momento.

    Cinco minutos después de abrir: mismo usuario y misma sesión, los dos roles como `frozenset`, la caducidad
    absoluta sin cambio y la de inactividad desplazada a ahora más 30 minutos. A nivel HTTP es TC-32 (fila 7).
    """
    from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    vigente = validar(contexto, abierta.sesion_id)

    assert isinstance(vigente, UsuarioAutenticado)
    assert vigente.usuario_id == ana
    assert vigente.sesion_id == abierta.sesion_id
    assert vigente.nombre == "Ana Torres"
    assert vigente.email == CORREO_DE_ANA
    assert vigente.roles == frozenset({"COMPRAS", "RESIDENTE"})
    assert isinstance(vigente.roles, frozenset)
    assert vigente.expira_en == abierta.expira_en
    assert vigente.expira_por_inactividad_en == reloj_de_prueba.ahora + timedelta(minutes=30)


def test_tkt006_ca06_aplicacion_validar_desliza_solo_la_ultima_actividad(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-6 esc. 1 · ADR-014 — `ultima_actividad` avanza al momento de la petición y nada más cambia.

    Con una conexión nueva: `ultima_actividad` vale ahora; `creada_en`, `expira_en`, `revocada_en`, el origen,
    el agente y `usuario.ultimo_acceso` conservan lo que escribió `abrir_sesion`. Una sola fila en `sesion`.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    validar(contexto, abierta.sesion_id)

    lectura = lector()
    assert contar(lectura, "sesion") == 1
    assert fila_de_sesion(lectura, abierta.sesion_id) == {
        "usuario_id": ana,
        "creada_en": inicio,
        "expira_en": inicio + timedelta(hours=12),
        "ultima_actividad": reloj_de_prueba.ahora,
        "revocada_en": None,
        "origen_ip": ORIGEN_IP,
        "agente_usuario": AGENTE_USUARIO,
    }
    assert ultimo_acceso_de(lectura, ana) == inicio


def test_tkt006_ca06_aplicacion_validar_toca_solo_su_sesion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-6 esc. 1 — validar la sesión de Ana no desliza la actividad de ninguna otra, ni de Luis ni de otra de Ana."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sembrar_usuario(CORREO_DE_LUIS, CONTRASENA_DE_LUIS, nombre="Luis Mena")
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    de_ana = abrir(contexto)
    otra_de_ana = abrir(contexto)
    de_luis = abrir(contexto, CORREO_DE_LUIS, CONTRASENA_DE_LUIS)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    validar(contexto, de_ana.sesion_id)

    lectura = lector()
    assert fila_de_sesion(lectura, de_ana.sesion_id)["ultima_actividad"] == reloj_de_prueba.ahora
    assert fila_de_sesion(lectura, otra_de_ana.sesion_id)["ultima_actividad"] == inicio
    assert fila_de_sesion(lectura, de_luis.sesion_id)["ultima_actividad"] == inicio


def test_tkt006_ca06_aplicacion_validar_usuario_sin_roles_devuelve_conjunto_vacio(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-6 · M7 — un usuario sin ningún rol tiene sesión vigente y su conjunto de roles es vacío, no nulo."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)

    vigente = validar(contexto, abierta.sesion_id)

    assert vigente.roles == frozenset()
    assert isinstance(vigente.roles, frozenset)


# --------------------------------------------------------------------------- CA-7 · sin sesión


def test_tkt006_ca07_aplicacion_validar_sesion_inexistente_es_sin_sesion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-7 esc. 1 y 2 · M7 — un identificador que no existe es `SIN_SESION`, con el contrato completo.

    Hay una sesión real de otro usuario: la inexistente no se confunde con ella. El rechazo no escribe nada:
    ni `intento_acceso` ni la bitácora, y la sesión real conserva su actividad.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    real = abrir(contexto)
    intentos_antes = contar(lector(), "intento_acceso")
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    error = rechazar(contexto, uuid.uuid4())

    exigir_contrato_de_sesion(error, "SIN_SESION")
    lectura = lector()
    assert contar(lectura, "bitacora") == 0
    assert contar(lectura, "intento_acceso") == intentos_antes
    assert contar(lectura, "sesion") == 1
    assert fila_de_sesion(lectura, real.sesion_id)["ultima_actividad"] == inicio


# --------------------------------------------------------------------------- CA-8 · caducidades


def test_tkt006_ca08_aplicacion_validar_caduca_al_llegar_expira_en(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-8 esc. 1 · RNF-01 — en el instante exacto de `expira_en` la sesión ya caducó; un segundo antes, no.

    La inactividad se configura muy lejos (1,000 minutos) para aislar la caducidad absoluta (60 minutos). La
    fila no se borra, `revocada_en` sigue nulo y el rechazo no desliza `ultima_actividad`. HTTP: TC-36.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(
        motor_aplicacion,
        reloj_de_prueba,
        entorno={
            "CIMENTA_SESION_CADUCIDAD_MINUTOS": "60",
            "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "1000",
        },
    )
    abierta = abrir(contexto)
    assert abierta.expira_en == reloj_de_prueba.ahora + timedelta(minutes=60)
    reloj_de_prueba.ahora = abierta.expira_en - timedelta(seconds=1)
    assert validar(contexto, abierta.sesion_id).sesion_id == abierta.sesion_id
    ultima_vigente = reloj_de_prueba.ahora

    reloj_de_prueba.ahora = abierta.expira_en
    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_CADUCADA")
    lectura = lector()
    assert contar(lectura, "sesion") == 1
    fila = fila_de_sesion(lectura, abierta.sesion_id)
    assert fila["revocada_en"] is None
    assert fila["ultima_actividad"] == ultima_vigente


@pytest.mark.parametrize("paso", [timedelta(minutes=30), timedelta(minutes=31), timedelta(hours=3)])
def test_tkt006_ca08_aplicacion_validar_caduca_por_inactividad(
    paso: timedelta,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-8 esc. 2 · RNF-01 — treinta minutos sin actividad caducan la sesión aunque `expira_en` esté lejos.

    El límite exacto (30 minutos) ya caduca. La fila no se borra, `revocada_en` sigue nulo y el rechazo no
    desliza `ultima_actividad`. HTTP: TC-37.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(paso)
    assert reloj_de_prueba.ahora < abierta.expira_en

    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_CADUCADA")
    lectura = lector()
    assert contar(lectura, "sesion") == 1
    fila = fila_de_sesion(lectura, abierta.sesion_id)
    assert fila["revocada_en"] is None
    assert fila["ultima_actividad"] == inicio


def test_tkt006_ca08_aplicacion_validar_un_segundo_antes_del_limite_de_inactividad_sigue_vigente(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-8 esc. 2 (borde) — a 29 minutos y 59 segundos la sesión sigue vigente y la inactividad se renueva."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=29, seconds=59))

    vigente = validar(contexto, abierta.sesion_id)

    assert vigente.sesion_id == abierta.sesion_id
    assert vigente.expira_por_inactividad_en == reloj_de_prueba.ahora + timedelta(minutes=30)


def test_tkt006_ca08_aplicacion_la_actividad_desliza_la_inactividad_y_no_la_absoluta(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-8 esc. 3 · RNF-01 — peticiones cada 25 minutos mantienen viva la sesión hasta `expira_en`, y ni un minuto más.

    Todas vigentes y con la misma `expira_en`: la actividad no la desplaza. Al llegar `expira_en` caduca aunque
    la última petición fuera 20 minutos antes (menos que el límite de inactividad). HTTP: TC-38.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    peticiones = 0

    while reloj_de_prueba.ahora + timedelta(minutes=25) < abierta.expira_en:
        reloj_de_prueba.avanzar(timedelta(minutes=25))
        vigente = validar(contexto, abierta.sesion_id)
        assert vigente.expira_en == abierta.expira_en
        assert vigente.expira_por_inactividad_en == reloj_de_prueba.ahora + timedelta(minutes=30)
        peticiones += 1
    ultima_peticion = reloj_de_prueba.ahora
    assert peticiones >= 28
    assert abierta.expira_en - ultima_peticion < timedelta(minutes=30)

    reloj_de_prueba.ahora = abierta.expira_en
    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_CADUCADA")
    fila = fila_de_sesion(lector(), abierta.sesion_id)
    assert fila["ultima_actividad"] == ultima_peticion
    assert fila["expira_en"] == abierta.expira_en
    assert fila["revocada_en"] is None


def test_tkt006_ca08_aplicacion_validar_usa_la_inactividad_de_la_configuracion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-8 esc. 4 · PA-T2 — con 10 minutos configurados, a los 9:59 sigue vigente y a los 10:00 caduca.

    Una sesión por cada instante, para que la primera petición no renueve la actividad de la segunda.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(
        motor_aplicacion, reloj_de_prueba, entorno={"CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10"}
    )
    inicio = reloj_de_prueba.ahora
    dentro = abrir(contexto)
    fuera = abrir(contexto)

    reloj_de_prueba.ahora = inicio + timedelta(minutes=9, seconds=59)
    vigente = validar(contexto, dentro.sesion_id)
    assert vigente.expira_por_inactividad_en == reloj_de_prueba.ahora + timedelta(minutes=10)

    reloj_de_prueba.ahora = inicio + timedelta(minutes=10)
    error = rechazar(contexto, fuera.sesion_id)
    exigir_contrato_de_sesion(error, "SESION_CADUCADA")


# --------------------------------------------------------------------------- CA-9 · cerrar


def test_tkt006_ca09_aplicacion_cerrar_revoca_sin_borrar(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 esc. 1 · M4 — cerrar escribe `revocada_en` con la hora del reloj y la fila sigue existiendo.

    No toca `ultima_actividad`, `expira_en` ni el resto de la fila, y no hay otra fila:
    nunca se borra (ADR-014, CA-9 esc. 4). HTTP: TC-43 (fila 7).
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    cerrar(contexto, abierta.sesion_id)

    lectura = lector()
    assert contar(lectura, "sesion") == 1
    assert fila_de_sesion(lectura, abierta.sesion_id) == {
        "usuario_id": ana,
        "creada_en": inicio,
        "expira_en": inicio + timedelta(hours=12),
        "ultima_actividad": inicio,
        "revocada_en": reloj_de_prueba.ahora,
        "origen_ip": ORIGEN_IP,
        "agente_usuario": AGENTE_USUARIO,
    }


def test_tkt006_ca09_aplicacion_la_sesion_cerrada_ya_no_sirve(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 esc. 2 — tras cerrar, `validar_sesion` rechaza con `SESION_REVOCADA` y el contrato completo.

    El rechazo no desliza `ultima_actividad` ni pisa `revocada_en`. HTTP: TC-44 (fila 7).
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=3))
    cerrar(contexto, abierta.sesion_id)
    cerrada_en = reloj_de_prueba.ahora
    reloj_de_prueba.avanzar(timedelta(minutes=1))

    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_REVOCADA")
    fila = fila_de_sesion(lector(), abierta.sesion_id)
    assert fila["revocada_en"] == cerrada_en
    assert fila["ultima_actividad"] == inicio


def test_tkt006_ca09_aplicacion_cerrar_dos_veces_no_pisa_revocada_en(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 · ADR-014 — un segundo cierre no falla ni sobrescribe la hora del primero (`revocada_en` se escribe una vez)."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=3))
    cerrar(contexto, abierta.sesion_id)
    primera_hora = reloj_de_prueba.ahora
    reloj_de_prueba.avanzar(timedelta(minutes=7))

    cerrar(contexto, abierta.sesion_id)

    lectura = lector()
    assert contar(lectura, "sesion") == 1
    assert fila_de_sesion(lectura, abierta.sesion_id)["revocada_en"] == primera_hora


def test_tkt006_ca09_aplicacion_cerrar_una_sesion_inexistente_no_hace_nada(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 esc. 3 — cerrar un identificador que no existe no lanza, no crea filas y no cambia la sesión real.

    Rechazar «cerrar sin sesión» con `SIN_SESION` es de la dependencia de la ruta (fila 7, TC-45); el caso de
    uso solo no debe escribir donde no hay fila.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    real = abrir(contexto)
    antes = fila_de_sesion(lector(), real.sesion_id)
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    cerrar(contexto, uuid.uuid4())

    lectura = lector()
    assert contar(lectura, "sesion") == 1
    assert fila_de_sesion(lectura, real.sesion_id) == antes


def test_tkt006_ca09_aplicacion_cerrar_toca_solo_su_sesion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 — cerrar una sesión no revoca las demás del mismo usuario ni las de otro: siguen vigentes."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sembrar_usuario(CORREO_DE_LUIS, CONTRASENA_DE_LUIS, nombre="Luis Mena")
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    cerrada = abrir(contexto)
    otra_de_ana = abrir(contexto)
    de_luis = abrir(contexto, CORREO_DE_LUIS, CONTRASENA_DE_LUIS)
    reloj_de_prueba.avanzar(timedelta(minutes=3))

    cerrar(contexto, cerrada.sesion_id)

    lectura = lector()
    assert fila_de_sesion(lectura, cerrada.sesion_id)["revocada_en"] == reloj_de_prueba.ahora
    assert fila_de_sesion(lectura, otra_de_ana.sesion_id)["revocada_en"] is None
    assert fila_de_sesion(lectura, de_luis.sesion_id)["revocada_en"] is None
    assert validar(contexto, otra_de_ana.sesion_id).sesion_id == otra_de_ana.sesion_id
    assert validar(contexto, de_luis.sesion_id).sesion_id == de_luis.sesion_id


def test_tkt006_ca09_aplicacion_revocada_prevalece_sobre_caducada(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-9 esc. 2 · RNF-01 — una sesión revocada que además caducó responde `SESION_REVOCADA`, no `SESION_CADUCADA`."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=3))
    cerrar(contexto, abierta.sesion_id)
    reloj_de_prueba.ahora = abierta.expira_en + timedelta(hours=1)

    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_REVOCADA")


# --------------------------------------------------------------------------- CA-10 · usuario desactivado


def test_tkt006_ca10_aplicacion_desactivar_surte_efecto_en_la_peticion_siguiente(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-10 · M6 · PA-T3 `(asumido)` — con `usuario.activo` en falso, la petición siguiente es `SESION_REVOCADA`.

    Sin caché de estado: la petición anterior fue vigente y la siguiente, sin ninguna otra acción, ya no. La
    fila no se borra, no se desliza la actividad y `revocada_en` sigue nulo: el rechazo no escribe. HTTP: TC-40.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    reloj_de_prueba.avanzar(timedelta(minutes=2))
    validar(contexto, abierta.sesion_id)
    ultima_vigente = reloj_de_prueba.ahora
    desactivar(lector(), ana)
    reloj_de_prueba.avanzar(timedelta(minutes=1))

    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_REVOCADA")
    lectura = lector()
    assert contar(lectura, "sesion") == 1
    fila = fila_de_sesion(lectura, abierta.sesion_id)
    assert fila["ultima_actividad"] == ultima_vigente
    assert fila["revocada_en"] is None


def test_tkt006_ca10_aplicacion_desactivado_y_caducada_es_revocada(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-10 · PA-T3 — un usuario desactivado cuya sesión además caducó responde `SESION_REVOCADA`: gana la desactivación."""
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    desactivar(lector(), ana)
    reloj_de_prueba.ahora = abierta.expira_en + timedelta(hours=1)

    error = rechazar(contexto, abierta.sesion_id)

    exigir_contrato_de_sesion(error, "SESION_REVOCADA")


# --------------------------------------------------------------------------- CA-11 · roles sin caché


def test_tkt006_ca11_aplicacion_validar_lee_los_roles_en_cada_peticion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-11 · M6 · M7 · MT-10 — un rol retirado o concedido se ve en la petición siguiente, sin caché.

    Tres lecturas con la misma sesión y el mismo contexto: dos roles; retirado `COMPRAS`, solo `RESIDENTE`;
    concedido `ALMACEN`, `ALMACEN` y `RESIDENTE`. El cierre del rol retirado como `403` es de la fila 10.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abierta = abrir(contexto)
    assert validar(contexto, abierta.sesion_id).roles == frozenset({"COMPRAS", "RESIDENTE"})

    retirar_rol(lector(), ana, "COMPRAS")
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    assert validar(contexto, abierta.sesion_id).roles == frozenset({"RESIDENTE"})

    conceder_rol(lector(), ana, "ALMACEN")
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    assert validar(contexto, abierta.sesion_id).roles == frozenset({"ALMACEN", "RESIDENTE"})


# --------------------------------------------------------------------------- concurrencia · TC-41


def esperar_a_que_alguien_espere_un_bloqueo(
    observador: Conexion, esperando: Future[Any], *, propios: list[int]
) -> int:
    """Sondea `pg_stat_activity` hasta ver otro proceso de esta base esperando un bloqueo (plazo de 10 s).

    No hay pausa fija: cada vuelta consulta, y el plazo corta una espera que nunca llega. Si el hilo
    terminó antes de bloquearse, el caso falla con lo que devolvió o lanzó, no con un tiempo agotado.
    """
    limite = time.monotonic() + PLAZO_DEL_SONDEO_S
    while time.monotonic() < limite:
        fila = observador.execute(
            "SELECT pid FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock' AND pid <> ALL(%s)",
            (propios,),
        ).fetchone()
        if fila is not None:
            return int(fila[0])
        if esperando.done():
            raise AssertionError(
                "La operación terminó sin esperar el bloqueo de la otra transacción: "
                f"{esperando.exception() or esperando.result()!r}"
            )
        threading.Event().wait(0.02)
    raise AssertionError(
        f"Ningún proceso esperó un bloqueo en {PLAZO_DEL_SONDEO_S:.0f} s: las dos operaciones no se cruzaron."
    )


def test_tkt006_ca06_concurrencia_cierre_y_peticion_simultanea(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    conectar: Callable[..., Conexion],
    base_de_prueba: str,
) -> None:
    """TC-41 · CA-6 · CA-9 · objeción 5 de la spec — un cierre sin confirmar y una petición simultánea: gana el cierre.

    La conexión A (rol de aplicación, sin autocommit) revoca la sesión y no confirma. Un hilo llama a
    `validar_sesion`: lee la sesión como vigente (la lectura no espera) y su `UPDATE` de `ultima_actividad`
    queda esperando el bloqueo de fila. Cuando el sondeo de `pg_stat_activity` ve esa espera, A confirma. En
    `READ COMMITTED` PostgreSQL reevalúa el `WHERE` de la guarda `revocada_en IS NULL`, no encuentra fila y
    la petición termina con `SesionInvalida` `SESION_REVOCADA`. Ni una escritura pisa a la otra: `revocada_en`
    es el de A y `ultima_actividad` no se movió. Sin la guarda (MT-9) la petición respondería vigente.
    """
    from cimenta.identidad.aplicacion.sesiones import validar_sesion

    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    hora_del_cierre = inicio + timedelta(minutes=2)
    reloj_de_prueba.ahora = inicio + timedelta(minutes=5)
    cierre = conectar("aplicacion", base_de_prueba, autocommit=False)
    observador = conectar("aplicacion", base_de_prueba)
    ejecutor = ThreadPoolExecutor(max_workers=1)
    try:
        asentado = cierre.execute(
            "UPDATE sesion SET revocada_en = %s WHERE id = %s AND revocada_en IS NULL",
            (hora_del_cierre, abierta.sesion_id),
        )
        assert asentado.rowcount == 1
        peticion = ejecutor.submit(validar_sesion, contexto, abierta.sesion_id)

        esperar_a_que_alguien_espere_un_bloqueo(
            observador, peticion, propios=[cierre.info.backend_pid, observador.info.backend_pid]
        )
        cierre.commit()

        with pytest.raises(SesionInvalida) as capturada:
            peticion.result(timeout=PLAZO_DEL_SONDEO_S)
    finally:
        if not cierre.closed:
            cierre.rollback()
        ejecutor.shutdown(wait=True)

    exigir_contrato_de_sesion(capturada.value, "SESION_REVOCADA")
    fila = fila_de_sesion(observador, abierta.sesion_id)
    assert fila["revocada_en"] == hora_del_cierre
    assert fila["ultima_actividad"] == inicio


def test_tkt006_ca09_concurrencia_dos_cierres_no_pisan_revocada_en(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    conectar: Callable[..., Conexion],
    base_de_prueba: str,
) -> None:
    """CA-9 · ADR-014 — dos cierres simultáneos: el segundo espera, no encuentra fila y deja la hora del primero.

    A revoca con su hora y no confirma; `cerrar_sesion_vigente` (con otra hora de reloj) espera el bloqueo.
    Al confirmar A, la guarda `revocada_en IS NULL` de `revocar_sesion` ya no casa: no lanza y no sobrescribe.
    Sin esa guarda la hora final sería la del segundo cierre.
    """
    from cimenta.identidad.aplicacion.sesiones import cerrar_sesion_vigente

    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    hora_del_primero = inicio + timedelta(minutes=2)
    reloj_de_prueba.ahora = inicio + timedelta(minutes=9)
    primero = conectar("aplicacion", base_de_prueba, autocommit=False)
    observador = conectar("aplicacion", base_de_prueba)
    ejecutor = ThreadPoolExecutor(max_workers=1)
    try:
        asentado = primero.execute(
            "UPDATE sesion SET revocada_en = %s WHERE id = %s AND revocada_en IS NULL",
            (hora_del_primero, abierta.sesion_id),
        )
        assert asentado.rowcount == 1
        segundo = ejecutor.submit(cerrar_sesion_vigente, contexto, abierta.sesion_id)

        esperar_a_que_alguien_espere_un_bloqueo(
            observador, segundo, propios=[primero.info.backend_pid, observador.info.backend_pid]
        )
        primero.commit()

        resultado = segundo.result(timeout=PLAZO_DEL_SONDEO_S)
    finally:
        if not primero.closed:
            primero.rollback()
        ejecutor.shutdown(wait=True)

    assert resultado is None
    fila = fila_de_sesion(observador, abierta.sesion_id)
    assert fila["revocada_en"] == hora_del_primero
    assert fila["ultima_actividad"] == inicio


def test_tkt006_ca09_concurrencia_el_cierre_no_pisa_la_actividad_de_una_peticion_en_curso(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    conectar: Callable[..., Conexion],
    base_de_prueba: str,
) -> None:
    """CA-6 · CA-9 · ADR-014 — la petición que desliza la actividad y el cierre que revoca tocan columnas distintas.

    A desliza `ultima_actividad` y no confirma; `cerrar_sesion_vigente` espera el bloqueo. Al confirmar A, el
    cierre escribe `revocada_en` y deja la `ultima_actividad` de A: ninguna escritura sobrescribe la otra.
    """
    from cimenta.identidad.aplicacion.sesiones import cerrar_sesion_vigente

    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    inicio = reloj_de_prueba.ahora
    abierta = abrir(contexto)
    actividad_de_la_peticion = inicio + timedelta(minutes=4)
    hora_del_cierre = inicio + timedelta(minutes=9)
    reloj_de_prueba.ahora = hora_del_cierre
    peticion = conectar("aplicacion", base_de_prueba, autocommit=False)
    observador = conectar("aplicacion", base_de_prueba)
    ejecutor = ThreadPoolExecutor(max_workers=1)
    try:
        asentado = peticion.execute(
            "UPDATE sesion SET ultima_actividad = %s WHERE id = %s AND revocada_en IS NULL",
            (actividad_de_la_peticion, abierta.sesion_id),
        )
        assert asentado.rowcount == 1
        cierre = ejecutor.submit(cerrar_sesion_vigente, contexto, abierta.sesion_id)

        esperar_a_que_alguien_espere_un_bloqueo(
            observador, cierre, propios=[peticion.info.backend_pid, observador.info.backend_pid]
        )
        peticion.commit()

        cierre.result(timeout=PLAZO_DEL_SONDEO_S)
    finally:
        if not peticion.closed:
            peticion.rollback()
        ejecutor.shutdown(wait=True)

    fila = fila_de_sesion(observador, abierta.sesion_id)
    assert fila["revocada_en"] == hora_del_cierre
    assert fila["ultima_actividad"] == actividad_de_la_peticion


# =========================================================================== HTTP (fila 7, tanda 1)
#
# Todo lo que sigue entra por `GET /api/v1/sesion` (y por una ruta de prueba) con el `cliente` de
# `conftest.py`: HTTPS, el rol de aplicación y el reloj de prueba. Ningún nombre de caso lleva las
# palabras «aplicacion» ni «concurrencia». Las sesiones se abren por HTTP y, para no depender del almacén
# de cookies del cliente, cada petición posterior envía la cabecera `Cookie` a mano: `iniciar_por_http`
# vacía el almacén después de abrir. Rojo esperado: `crear_aplicacion` aún no acepta `motor`, `reloj` ni
# `entorno` (TypeError en la *fixture* `aplicacion_identidad`); con la firma pedida y sin las rutas,
# `404 NO_ENCONTRADO`.

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
RUTA_DE_PRUEBA_ROLES = "/api/v1/prueba/roles"
COOKIE_SESION = "cimenta_sesion"
CLAVES_DE_USUARIO_ACTUAL = {"id", "nombre", "email", "roles", "sesion"}
CLAVES_DE_ERROR_DE_SESION = {"tipo", "motivo", "mensaje", "correlacion_id"}
Respuesta = Any


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def exigir_error_de_sesion(respuesta: Respuesta, motivo: str) -> None:
    """El contrato de error completo de un `401` de sesión (CA-7, CA-8, CA-9, CA-10, CA-R5).

    Código, `tipo`, `motivo`, `mensaje` literal, conjunto exacto de claves, ausencia de `detail`,
    `correlacion_id` igual a la cabecera y validez contra `ErrorSesion`.
    """
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == motivo
    assert cuerpo["mensaje"] == MENSAJES_LITERALES[motivo]
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorSesion", cuerpo)


def sin_correlacion(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {clave: valor for clave, valor in cuerpo.items() if clave != "correlacion_id"}


def iniciar_por_http(
    cliente: TestClient, correo: str = CORREO_DE_ANA, contrasena: str = CONTRASENA_DE_ANA
) -> uuid.UUID:
    """Abre una sesión con `POST /api/v1/sesion`, devuelve el id de la cookie y vacía el almacén del cliente."""
    respuesta = cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers={"User-Agent": AGENTE_USUARIO},
    )
    assert respuesta.status_code == 200, respuesta.text
    galleta: SimpleCookie = SimpleCookie()
    galleta.load(respuesta.headers["set-cookie"])
    cliente.cookies.clear()
    return uuid.UUID(galleta[COOKIE_SESION].value)


def con_cookie(valor: object) -> dict[str, str]:
    """La cabecera `Cookie` con la sesión indicada."""
    return {"Cookie": f"{COOKIE_SESION}={valor}"}


def consultar(cliente: TestClient, sesion_id: uuid.UUID) -> Respuesta:
    """`GET /api/v1/sesion` con la cookie de esa sesión."""
    return cliente.get(RUTA_SESION, headers=con_cookie(sesion_id))


def instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def filas_de_sesion(conexion: Conexion) -> list[dict[str, Any]]:
    """Todas las filas de `sesion`, por nombre de columna y ordenadas por id."""
    filas = conexion.execute(
        "SELECT id, usuario_id, creada_en, expira_en, ultima_actividad, revocada_en, origen_ip, "
        "agente_usuario FROM sesion ORDER BY id"
    ).fetchall()
    nombres = (
        "id",
        "usuario_id",
        "creada_en",
        "expira_en",
        "ultima_actividad",
        "revocada_en",
        "origen_ip",
        "agente_usuario",
    )
    return [dict(zip(nombres, fila, strict=True)) for fila in filas]


def agregar_ruta_de_roles(aplicacion: FastAPI) -> None:
    """Ruta de la suite, no del producto: `GET /api/v1/prueba/roles` devuelve `roles_de_quien_llama` ordenados.

    Solo declara `Depends(sesion_vigente)`; el cuerpo lee lo que la dependencia dejó en `request.state`.
    """
    from cimenta.identidad.api.dependencias import sesion_vigente

    enrutador = APIRouter()

    @enrutador.get(RUTA_DE_PRUEBA_ROLES, dependencies=[Depends(sesion_vigente)])
    def roles_de_quien_llama(request: Request) -> list[str]:
        return sorted(request.state.roles_de_quien_llama)

    aplicacion.include_router(enrutador)


@pytest.fixture
def crear_cliente(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> Iterator[Callable[[dict[str, str]], TestClient]]:
    """Fábrica de clientes HTTPS con otra configuración: el entorno de pruebas más el que pida el caso."""
    from servidor.fabrica import crear_aplicacion

    with ExitStack() as pila:

        def _crear(entorno: dict[str, str]) -> TestClient:
            aplicacion = crear_aplicacion(
                destino_registro=io.StringIO(),
                motor=motor_aplicacion,
                reloj=reloj_de_prueba,
                entorno={**ENTORNO_DE_PRUEBA, **entorno},
            )
            return pila.enter_context(
                TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)
            )

        yield _crear


# --------------------------------------------------------------------------- TC-32


def test_tkt006_ca06_sesion_vigente_devuelve_usuario_y_roles(
    cliente: TestClient, reloj_de_prueba: RelojDePrueba, sembrar_usuario: SembrarUsuario
) -> None:
    """TC-32 · CA-6 esc. 1 · M3 — 200 con `UsuarioActual`, los dos roles ordenados y las dos caducidades.

    Cinco minutos después de abrir: la caducidad absoluta no se mueve y la de inactividad es ahora más
    30 minutos. El cuerpo tiene exactamente las cinco claves, valida contra el borrador y lleva
    `X-Correlacion-Id`.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    respuesta = consultar(cliente, sesion_id)

    assert respuesta.status_code == 200
    assert uuid.UUID(respuesta.headers[CABECERA]).version == 4
    cuerpo = respuesta.json()
    assert set(cuerpo) == CLAVES_DE_USUARIO_ACTUAL
    validar_contra("UsuarioActual", cuerpo)
    assert cuerpo["id"] == str(ana)
    assert cuerpo["nombre"] == "Ana Torres"
    assert cuerpo["email"] == CORREO_DE_ANA
    assert cuerpo["roles"] == ["COMPRAS", "RESIDENTE"]
    assert instante(cuerpo["sesion"]["expira_en"]) == inicio + timedelta(hours=12)
    assert instante(cuerpo["sesion"]["expira_por_inactividad_en"]) == (
        reloj_de_prueba.ahora + timedelta(minutes=30)
    )


def test_tkt006_ca06_la_peticion_desliza_ultima_actividad_y_nada_mas(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-32 · CA-6 esc. 1 · ADR-014 — `sesion.ultima_actividad` avanza al momento de la petición y el resto de la fila no cambia."""
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    consultar(cliente, sesion_id)

    assert filas_de_sesion(lector()) == [
        {
            "id": sesion_id,
            "usuario_id": ana,
            "creada_en": inicio,
            "expira_en": inicio + timedelta(hours=12),
            "ultima_actividad": reloj_de_prueba.ahora,
            "revocada_en": None,
            "origen_ip": "testclient",
            "agente_usuario": AGENTE_USUARIO,
        }
    ]


def test_tkt006_ca06_sesion_vigente_de_un_usuario_sin_roles(
    cliente: TestClient, sembrar_usuario: SembrarUsuario
) -> None:
    """CA-6 · M7 `(asumido)` — un usuario sin ningún rol ve su sesión: 200 con `roles` vacío, no un error.

    Consultar la propia sesión solo exige sesión vigente, no un rol concreto.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA)
    sesion_id = iniciar_por_http(cliente)

    respuesta = consultar(cliente, sesion_id)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    validar_contra("UsuarioActual", cuerpo)
    assert cuerpo["roles"] == []


# --------------------------------------------------------------------------- TC-33


def test_tkt006_ca06_roles_de_quien_llama(
    cliente: TestClient, aplicacion_identidad: FastAPI, sembrar_usuario: SembrarUsuario
) -> None:
    """TC-33 · CA-6 esc. 1 · M7 — `sesion_vigente` deja los roles de quien llama en `request.state`.

    Una ruta de la suite con `Depends(sesion_vigente)` devuelve `roles_de_quien_llama` ordenados: los
    dos roles de Ana, tal como están en la base en esa petición.
    """
    agregar_ruta_de_roles(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)

    respuesta = cliente.get(RUTA_DE_PRUEBA_ROLES, headers=con_cookie(sesion_id))

    assert respuesta.status_code == 200
    assert respuesta.json() == ["COMPRAS", "RESIDENTE"]


def test_tkt006_ca07_la_ruta_con_sesion_vigente_no_se_ejecuta_sin_cookie(
    cliente: TestClient, aplicacion_identidad: FastAPI
) -> None:
    """TC-33 · CA-7 esc. 1 — rechazo: la ruta protegida con `sesion_vigente` responde `401 SIN_SESION` y no ejecuta su cuerpo."""
    agregar_ruta_de_roles(aplicacion_identidad)

    respuesta = cliente.get(RUTA_DE_PRUEBA_ROLES)

    exigir_error_de_sesion(respuesta, "SIN_SESION")


# --------------------------------------------------------------------------- TC-34


def test_tkt006_ca07_peticion_sin_cookie(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-34 · CA-7 esc. 1 · CA-R5 — rechazo: sin cookie, `401 SIN_SESION` con el contrato completo y sin escribir nada.

    La bitácora no recibe ningún asiento: un rechazo anónimo no es un `DENEGAR`. La sesión real de otro
    usuario conserva todas sus columnas.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    iniciar_por_http(cliente)
    antes = filas_de_sesion(lector())
    intentos_antes = contar(lector(), "intento_acceso")

    respuesta = cliente.get(RUTA_SESION)

    exigir_error_de_sesion(respuesta, "SIN_SESION")
    lectura = lector()
    assert contar(lectura, "bitacora") == 0
    assert contar(lectura, "intento_acceso") == intentos_antes
    assert filas_de_sesion(lectura) == antes


# --------------------------------------------------------------------------- TC-35


def test_tkt006_ca07_cookie_inexistente_o_mal_formada(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-35 · CA-7 esc. 2 y 3 — rechazo: un UUID que no existe, «abc» y una cookie vacía responden igual: `SIN_SESION`.

    Los tres cuerpos, sin `correlacion_id`, son iguales: no se distingue «no existe» de «mal formada».
    Cada uno cumple el contrato completo. La sesión real de Ana no se toca.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    real = iniciar_por_http(cliente)
    antes = filas_de_sesion(lector())
    reloj_de_prueba.avanzar(timedelta(minutes=5))

    respuestas = [
        cliente.get(RUTA_SESION, headers=con_cookie(valor)) for valor in (uuid.uuid4(), "abc", "")
    ]

    for respuesta in respuestas:
        exigir_error_de_sesion(respuesta, "SIN_SESION")
    cuerpos = [sin_correlacion(respuesta.json()) for respuesta in respuestas]
    assert cuerpos[0] == cuerpos[1] == cuerpos[2]
    assert len({respuesta.json()["correlacion_id"] for respuesta in respuestas}) == 3
    assert filas_de_sesion(lector()) == antes
    assert consultar(cliente, real).status_code == 200


# --------------------------------------------------------------------------- TC-36


def test_tkt006_ca08_caducidad_absoluta(
    crear_cliente: Callable[[dict[str, str]], TestClient],
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-36 · CA-8 esc. 1 · RNF-01 — rechazo: en el instante exacto de `expira_en` la sesión ya caducó; un segundo antes, no.

    La inactividad se configura muy lejos (1,000 minutos) para aislar la caducidad absoluta (60
    minutos). La fila no se borra, `revocada_en` sigue nulo y el rechazo no desliza `ultima_actividad`.
    """
    cliente = crear_cliente(
        {
            "CIMENTA_SESION_CADUCIDAD_MINUTOS": "60",
            "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "1000",
        }
    )
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    expira_en = inicio + timedelta(minutes=60)
    reloj_de_prueba.ahora = expira_en - timedelta(seconds=1)
    assert consultar(cliente, sesion_id).status_code == 200
    ultima_vigente = reloj_de_prueba.ahora

    reloj_de_prueba.ahora = expira_en
    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_CADUCADA")
    filas = filas_de_sesion(lector())
    assert [fila["id"] for fila in filas] == [sesion_id]
    assert filas[0]["revocada_en"] is None
    assert filas[0]["ultima_actividad"] == ultima_vigente


# --------------------------------------------------------------------------- TC-37


def test_tkt006_ca08_caducidad_por_inactividad(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-37 · CA-8 esc. 2 · RNF-01 — rechazo: treinta minutos sin actividad caducan la sesión; el límite exacto ya caduca.

    `expira_en` está lejos. La fila no se borra, `revocada_en` sigue nulo y el rechazo no desliza
    `ultima_actividad`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=30))

    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_CADUCADA")
    filas = filas_de_sesion(lector())
    assert [fila["id"] for fila in filas] == [sesion_id]
    assert filas[0]["revocada_en"] is None
    assert filas[0]["ultima_actividad"] == inicio


def test_tkt006_ca08_un_segundo_antes_del_limite_de_inactividad_sigue_vigente(
    cliente: TestClient, reloj_de_prueba: RelojDePrueba, sembrar_usuario: SembrarUsuario
) -> None:
    """TC-37 · CA-8 esc. 2 (borde) — a 29 minutos y 59 segundos la sesión sigue vigente y devuelve su usuario."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=29, seconds=59))

    respuesta = consultar(cliente, sesion_id)

    assert respuesta.status_code == 200
    validar_contra("UsuarioActual", respuesta.json())
    assert instante(respuesta.json()["sesion"]["expira_por_inactividad_en"]) == (
        reloj_de_prueba.ahora + timedelta(minutes=30)
    )


# --------------------------------------------------------------------------- TC-38


def test_tkt006_ca08_la_actividad_desliza_la_inactividad_y_no_la_absoluta(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-38 · CA-8 esc. 3 · RNF-01 — rechazo: peticiones cada 25 minutos mantienen viva la sesión hasta `expira_en`, y ni un minuto más.

    Todas devuelven 200, con la misma `expira_en`, y hay al menos 28. Al llegar `expira_en` caduca aunque
    la última petición fuera menos de 30 minutos antes.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    expira_en = inicio + timedelta(hours=12)
    peticiones = 0

    while reloj_de_prueba.ahora + timedelta(minutes=25) < expira_en:
        reloj_de_prueba.avanzar(timedelta(minutes=25))
        respuesta = consultar(cliente, sesion_id)
        assert respuesta.status_code == 200
        assert instante(respuesta.json()["sesion"]["expira_en"]) == expira_en
        peticiones += 1
    ultima_peticion = reloj_de_prueba.ahora
    assert peticiones >= 28
    assert expira_en - ultima_peticion < timedelta(minutes=30)

    reloj_de_prueba.ahora = expira_en
    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_CADUCADA")
    fila = filas_de_sesion(lector())[0]
    assert fila["ultima_actividad"] == ultima_peticion
    assert fila["revocada_en"] is None


# --------------------------------------------------------------------------- TC-39


def test_tkt006_ca08_valores_de_la_configuracion(
    crear_cliente: Callable[[dict[str, str]], TestClient],
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-39 · CA-8 esc. 4 · PA-T2 — con 90 y 10 minutos configurados, `expira_en` y la inactividad los reflejan.

    La respuesta de `GET /api/v1/sesion` y la fila de `sesion` coinciden: `expira_en` es `creada_en`
    más 90 minutos y `expira_por_inactividad_en`, más 10.
    """
    cliente = crear_cliente(
        {
            "CIMENTA_SESION_CADUCIDAD_MINUTOS": "90",
            "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10",
        }
    )
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)

    respuesta = consultar(cliente, sesion_id)

    assert respuesta.status_code == 200
    vigencia = respuesta.json()["sesion"]
    assert instante(vigencia["expira_en"]) == inicio + timedelta(minutes=90)
    assert instante(vigencia["expira_por_inactividad_en"]) == inicio + timedelta(minutes=10)
    fila = filas_de_sesion(lector())[0]
    assert fila["expira_en"] == fila["creada_en"] + timedelta(minutes=90)


# --------------------------------------------------------------------------- TC-40


def test_tkt006_ca10_desactivar_surte_efecto_en_la_peticion_siguiente(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-40 · CA-10 · M6 · ADR-014 · PA-T3 `(asumido)` — rechazo: con `usuario.activo` falso, la siguiente petición es `SESION_REVOCADA`.

    La anterior fue 200; entre las dos solo se actualizó `usuario.activo`. La fila de `sesion` no se
    borra, `revocada_en` sigue nulo y el rechazo no desliza `ultima_actividad`.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=2))
    assert consultar(cliente, sesion_id).status_code == 200
    ultima_vigente = reloj_de_prueba.ahora
    desactivar(lector(), ana)
    reloj_de_prueba.avanzar(timedelta(minutes=1))

    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")
    filas = filas_de_sesion(lector())
    assert [fila["id"] for fila in filas] == [sesion_id]
    assert filas[0]["revocada_en"] is None
    assert filas[0]["ultima_actividad"] == ultima_vigente


def test_tkt006_ca10_desactivado_y_caducada_es_revocada(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-40 · CA-10 · PA-T3 — rechazo: un desactivado cuya sesión además caducó responde `SESION_REVOCADA`, no `SESION_CADUCADA`."""
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)
    desactivar(lector(), ana)
    reloj_de_prueba.avanzar(timedelta(hours=13))

    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")


# --------------------------------------------------------------------------- CA-9 · revocada


def test_tkt006_ca09_una_sesion_revocada_en_la_base_responde_revocada(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 esc. 2 · RNF-01 — rechazo: una sesión con `revocada_en` escrito responde `401 SESION_REVOCADA`, no 200.

    La revocación la escribe otra conexión, sin pasar por el cierre. La petición rechazada no desliza
    `ultima_actividad` ni pisa `revocada_en`.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    inicio = reloj_de_prueba.ahora
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=2))
    revocada_en = reloj_de_prueba.ahora
    lector().execute("UPDATE sesion SET revocada_en = %s WHERE id = %s", (revocada_en, sesion_id))
    reloj_de_prueba.avanzar(timedelta(minutes=1))

    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")
    fila = filas_de_sesion(lector())[0]
    assert fila["revocada_en"] == revocada_en
    assert fila["ultima_actividad"] == inicio


def test_tkt006_ca09_revocada_prevalece_sobre_caducada_por_http(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-9 esc. 2 · RNF-01 — rechazo: una sesión revocada que además caducó responde `SESION_REVOCADA`."""
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)
    lector().execute(
        "UPDATE sesion SET revocada_en = %s WHERE id = %s", (reloj_de_prueba.ahora, sesion_id)
    )
    reloj_de_prueba.avanzar(timedelta(hours=13))

    respuesta = consultar(cliente, sesion_id)

    exigir_error_de_sesion(respuesta, "SESION_REVOCADA")


# --------------------------------------------------------------------------- CA-11 · roles sin caché


def test_tkt006_ca11_retirar_un_rol_se_ve_en_la_peticion_siguiente(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-11 · M6 · M7 · MT-10 — rechazo: un rol retirado o concedido se ve en la petición siguiente, sin caché.

    Con la misma sesión: dos roles; retirado `COMPRAS`, solo `RESIDENTE`; concedido `ALMACEN`, `ALMACEN` y
    `RESIDENTE`. Lo comprueban `GET /api/v1/sesion` y los roles de quien llama de una ruta de la suite. El
    `403` del rol retirado es de la fila 10.
    """
    agregar_ruta_de_roles(aplicacion_identidad)
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)
    sesion_id = iniciar_por_http(cliente)
    assert consultar(cliente, sesion_id).json()["roles"] == ["COMPRAS", "RESIDENTE"]

    retirar_rol(lector(), ana, "COMPRAS")
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    de_la_sesion = consultar(cliente, sesion_id)
    de_la_ruta = cliente.get(RUTA_DE_PRUEBA_ROLES, headers=con_cookie(sesion_id))
    assert de_la_sesion.json()["roles"] == ["RESIDENTE"]
    assert de_la_ruta.json() == ["RESIDENTE"]

    conceder_rol(lector(), ana, "ALMACEN")
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    assert consultar(cliente, sesion_id).json()["roles"] == ["ALMACEN", "RESIDENTE"]
    assert cliente.get(RUTA_DE_PRUEBA_ROLES, headers=con_cookie(sesion_id)).json() == [
        "ALMACEN",
        "RESIDENTE",
    ]
