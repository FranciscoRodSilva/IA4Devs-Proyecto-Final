"""Inicio de sesión (TKT-006, entrega A): TC-26 y TC-27 a nivel de aplicación; con Docker salvo donde se dice.

Este archivo lo comparten dos filas del diseño. La **fila 5** escribe aquí los casos que llaman a
`abrir_sesion` directamente, con el motor del rol de aplicación y un reloj de prueba; su nombre lleva la
palabra `aplicacion` para que `pytest -k "aplicacion"` los seleccione. La **fila 7** añadirá debajo los
casos HTTP de TC-20 a TC-31 y la parte HTTP de TC-27 (`cliente` y `aplicacion_identidad`); ningún nombre
de caso HTTP debe contener la palabra `aplicacion`, o el filtro de la fila 5 lo recogería.

Contrato de error comprobado completo en cada rechazo: la excepción es `SesionInvalida` (`tipo`
`SESION`, `401`), su `motivo` es `CREDENCIALES_INVALIDAS`, su `mensaje` es el literal del diseño y su
`cuerpo(...)` tiene exactamente las claves `tipo`, `mensaje`, `motivo` y `correlacion_id`. Lo que se
verifica en la base se lee con una conexión **nueva** del rol de aplicación, nunca con la que escribió.

Los símbolos de producción (`abrir_sesion`, `ContextoIdentidad`, `UsuarioAutenticado`…) se importan
**dentro** de cada caso, no arriba ni en una *fixture*: así cada uno falla por sí solo con el
`ModuleNotFoundError` del archivo que falta y la recolección no se cae.
"""

from __future__ import annotations

import base64
import binascii
import dataclasses
import functools
import io
import json
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import psycopg
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from contrato_error import SesionInvalida

if TYPE_CHECKING:
    from cimenta.identidad.aplicacion.contexto import ContextoIdentidad

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
CONTRASENA_EQUIVOCADA = "Clave-Equivocada-9"
CORREO_INEXISTENTE = "nadie@cimenta.test"
ROL_DE_ANA = "DIRECTOR_PROYECTOS"
ORIGEN_IP = "10.0.0.7"
AGENTE_USUARIO = "Prueba/1.0"
CORRELACION = "corr-0001-prueba"
MENSAJE_LITERAL = "El correo o la contraseña no son correctos."
ESCENARIOS_DE_RECHAZO = ("correo_inexistente", "contrasena_erronea", "usuario_desactivado")


# --------------------------------------------------------------------------- ayudas de la prueba


class RelojDePrueba(Protocol):
    """Lo que estas pruebas usan de la *fixture* `reloj_de_prueba` de `conftest.py`."""

    ahora: datetime

    def __call__(self) -> datetime: ...

    def avanzar(self, delta: timedelta) -> None: ...


class _ContrasenasInterior(Protocol):
    hash_de_descarte: str

    def derivar(self, contrasena: str) -> str: ...

    def verificar(self, contrasena: str, hash_guardado: str) -> bool: ...


class ContadorDeContrasenas:
    """Envuelve las contraseñas reales y anota cada `(contrasena, hash)` que se verifica (TC-26).

    Es solo de prueba: delega en el adaptador real, así que el hash se verifica de verdad. Cumple el
    protocolo `Contrasenas` del diseño (`hash_de_descarte`, `derivar` y `verificar`).
    """

    def __init__(self, interior: _ContrasenasInterior) -> None:
        self._interior = interior
        self.hash_de_descarte: str = interior.hash_de_descarte
        self.verificaciones: list[tuple[str, str]] = []
        self.derivaciones: list[str] = []

    def derivar(self, contrasena: str) -> str:
        self.derivaciones.append(contrasena)
        return self._interior.derivar(contrasena)

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        self.verificaciones.append((contrasena, hash_guardado))
        return self._interior.verificar(contrasena, hash_guardado)


@dataclass(frozen=True)
class Intento:
    """Lo que se escribe en el formulario de inicio de sesión, y el usuario real si existe."""

    correo_escrito: str
    contrasena: str
    usuario_id: uuid.UUID | None


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


def con_contador(contexto: ContextoIdentidad) -> tuple[ContextoIdentidad, ContadorDeContrasenas]:
    """El mismo contexto con un contador sobre sus contraseñas, como en el diseño: `dataclasses.replace`."""
    contador = ContadorDeContrasenas(contexto.contrasenas)
    return dataclasses.replace(contexto, contrasenas=contador), contador


def preparar_intento(escenario: str, sembrar_usuario: SembrarUsuario) -> Intento:
    """Siembra lo que el escenario pide y devuelve lo que se escribirá en el formulario."""
    if escenario == "correo_inexistente":
        sembrar_usuario(
            CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,)
        )  # otra cuenta sí existe
        return Intento(CORREO_INEXISTENTE, CONTRASENA_DE_ANA, None)
    if escenario == "contrasena_erronea":
        ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
        return Intento(CORREO_DE_ANA, CONTRASENA_EQUIVOCADA, ana)
    if escenario == "usuario_desactivado":
        ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,), activo=False)
        return Intento(CORREO_DE_ANA, CONTRASENA_DE_ANA, ana)  # la contraseña es la correcta
    raise AssertionError(f"Escenario de rechazo desconocido: {escenario!r}")


def rechazar(
    contexto: ContextoIdentidad, intento: Intento, *, origen_ip: str | None = ORIGEN_IP
) -> SesionInvalida:
    """Llama a `abrir_sesion` esperando un `401`; devuelve la excepción capturada."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    with pytest.raises(SesionInvalida) as capturada:
        abrir_sesion(
            contexto,
            correo_escrito=intento.correo_escrito,
            contrasena=intento.contrasena,
            origen_ip=origen_ip,
            agente_usuario=AGENTE_USUARIO,
        )
    return capturada.value


def cuerpo_esperado_de_credenciales() -> dict[str, object]:
    return {
        "tipo": "SESION",
        "mensaje": MENSAJE_LITERAL,
        "motivo": "CREDENCIALES_INVALIDAS",
        "correlacion_id": CORRELACION,
    }


def exigir_contrato_de_credenciales_invalidas(error: SesionInvalida) -> None:
    """El contrato de error completo de CA-3 y CA-4: tipo, estado, motivo, mensaje y claves exactas."""
    from cimenta.identidad.aplicacion.sesiones import MENSAJE_CREDENCIALES_INVALIDAS

    assert error.tipo == "SESION"
    assert error.estado_http == 401
    assert error.motivo.value == "CREDENCIALES_INVALIDAS"
    assert error.mensaje == MENSAJE_LITERAL
    assert MENSAJE_CREDENCIALES_INVALIDAS == MENSAJE_LITERAL
    cuerpo = error.cuerpo(frozenset(), CORRELACION)
    assert cuerpo == cuerpo_esperado_de_credenciales()
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


def intentos_guardados(conexion: Conexion) -> list[dict[str, Any]]:
    """Las filas de `intento_acceso` por nombre de columna, sin su `id`."""
    filas = conexion.execute(
        "SELECT email, usuario_id, exitoso, ocurrido_en, origen_ip FROM intento_acceso"
    ).fetchall()
    nombres = ("email", "usuario_id", "exitoso", "ocurrido_en", "origen_ip")
    return [dict(zip(nombres, fila, strict=True)) for fila in filas]


def sesiones_guardadas(conexion: Conexion) -> list[dict[str, Any]]:
    filas = conexion.execute(
        "SELECT id, usuario_id, creada_en, expira_en, ultima_actividad, revocada_en, origen_ip, "
        "agente_usuario FROM sesion"
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


def ultimo_acceso_de(conexion: Conexion, usuario_id: uuid.UUID) -> Any:
    fila = conexion.execute(
        "SELECT ultimo_acceso FROM usuario WHERE id = %s", (usuario_id,)
    ).fetchone()
    assert fila is not None
    return fila[0]


def hash_guardado_de(conexion: Conexion, usuario_id: uuid.UUID) -> str:
    fila = conexion.execute(
        "SELECT password_hash FROM usuario WHERE id = %s", (usuario_id,)
    ).fetchone()
    assert fila is not None
    return str(fila[0])


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


# Revisión · ciclo 1 · F3. Valores que una fila de `usuario` podría traer en `password_hash` sin ser un hash
# Argon2: texto libre, vacío y la forma de otro algoritmo. `pwdlib` lanza `UnknownHashError` con todos.
CORREO_DE_CUENTA_DANADA = "danada@cimenta.test"
HASHES_GUARDADOS_QUE_NO_SON_ARGON2 = [
    pytest.param("sin-hash", id="texto_libre"),
    pytest.param("", id="vacio"),
    pytest.param("$2b$12$" + "a" * 53, id="forma_de_bcrypt"),
]
SembrarConHashGuardado = Callable[[str, str], uuid.UUID]


@pytest.fixture
def sembrar_con_hash_guardado(motor_aplicacion: Engine) -> SembrarConHashGuardado:
    """Inserta un usuario activo con el `password_hash` exacto que se pide, con el rol de aplicación."""

    def _sembrar(correo: str, hash_guardado: str) -> uuid.UUID:
        usuario_id = uuid.uuid4()
        with motor_aplicacion.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
                    "VALUES (:id, :nombre, :email, :hash, true)"
                ),
                {
                    "id": usuario_id,
                    "nombre": "Cuenta Dañada",
                    "email": correo,
                    "hash": hash_guardado,
                },
            )
        return usuario_id

    return _sembrar


# --------------------------------------------------------------------------- TC-26


@pytest.mark.parametrize("escenario", ESCENARIOS_DE_RECHAZO)
def test_tkt006_ca03_aplicacion_verifica_un_hash_siempre(
    escenario: str,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-26 · CA-3 esc. 3 · CA-4 — exista o no el correo, se verifica exactamente un hash de Argon2id.

    Correo inexistente: contra `hash_de_descarte`. Contraseña errónea y usuario desactivado con su
    contraseña correcta: contra el hash del usuario. Nunca cero verificaciones ni dos, y `abrir_sesion`
    no deriva hashes (el de descarte se calcula al construir el adaptador, no en cada intento).
    """
    intento = preparar_intento(escenario, sembrar_usuario)
    contexto, contador = con_contador(crear_contexto(motor_aplicacion, reloj_de_prueba))

    rechazar(contexto, intento)

    esperado = (
        contador.hash_de_descarte
        if intento.usuario_id is None
        else hash_guardado_de(lector(), intento.usuario_id)
    )
    assert contador.verificaciones == [(intento.contrasena, esperado)]
    assert esperado.startswith("$argon2id$")
    assert contador.derivaciones == []


def test_tkt006_ca03_aplicacion_el_hash_de_descarte_no_es_el_de_ningun_usuario(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-26 · CA-3 esc. 3 — el hash contra el que se verifica un correo inexistente es el de descarte.

    Complemento de la parametrización de arriba: un mutante que verifique siempre contra el hash de
    la primera cuenta pasaría «un hash» sin ser el de descarte. Aquí hay dos cuentas distintas y el
    correo inexistente debe usar el de descarte, no el de ninguna de ellas.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    sembrar_usuario("luis@cimenta.test", "Clave-De-Luis-2", nombre="Luis Mena")
    contexto, contador = con_contador(crear_contexto(motor_aplicacion, reloj_de_prueba))

    rechazar(contexto, Intento(CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA, None))

    guardados = {
        str(fila[0]) for fila in lector().execute("SELECT password_hash FROM usuario").fetchall()
    }
    assert len(contador.verificaciones) == 1
    verificado = contador.verificaciones[0][1]
    assert verificado == contador.hash_de_descarte
    assert verificado not in guardados


def test_tkt006_ca02_aplicacion_inicio_correcto_verifica_un_hash(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-26 · CA-2 · CA-3 esc. 3 — un inicio correcto también verifica exactamente un hash: el del usuario."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contexto, contador = con_contador(crear_contexto(motor_aplicacion, reloj_de_prueba))

    abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    assert contador.verificaciones == [(CONTRASENA_DE_ANA, hash_guardado_de(lector(), ana))]
    assert contador.derivaciones == []


@pytest.mark.parametrize("escenario", ESCENARIOS_DE_RECHAZO)
def test_tkt006_ca03_aplicacion_rechazo_con_contrato_de_error_completo(
    escenario: str,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-26 · CA-3 esc. 1 y 2 · CA-4 — SesionInvalida CREDENCIALES_INVALIDAS con su cuerpo exacto.

    Sin fila en `sesion`, `ultimo_acceso` intacto y la bitácora sin asientos: un rechazo anónimo
    no se asienta como `DENEGAR` (CA-3 esc. 1, CA-12 esc. 3).
    """
    intento = preparar_intento(escenario, sembrar_usuario)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    error = rechazar(contexto, intento)

    exigir_contrato_de_credenciales_invalidas(error)
    lectura = lector()
    assert sesiones_guardadas(lectura) == []
    assert contar(lectura, "bitacora") == 0
    if intento.usuario_id is not None:
        assert ultimo_acceso_de(lectura, intento.usuario_id) is None


def test_tkt006_ca03_aplicacion_los_tres_rechazos_son_indistinguibles(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-26 · CA-3 esc. 2 · CA-4 — correo inexistente, contraseña errónea y desactivado: el mismo cuerpo.

    Los tres cuerpos, con el mismo `correlacion_id`, son iguales: quien intenta no averigua qué cuentas
    existen ni cuáles están desactivadas. Hay una cuenta activa, otra desactivada y un correo inventado.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    baja = sembrar_usuario("baja@cimenta.test", "Clave-De-Baja-3", activo=False, nombre="Baja")
    assert ana != baja
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    errores = [
        rechazar(contexto, Intento(CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA, None)),
        rechazar(contexto, Intento(CORREO_DE_ANA, CONTRASENA_EQUIVOCADA, ana)),
        rechazar(contexto, Intento("baja@cimenta.test", "Clave-De-Baja-3", baja)),
    ]

    cuerpos = [error.cuerpo(frozenset(), CORRELACION) for error in errores]
    assert cuerpos[0] == cuerpos[1] == cuerpos[2] == cuerpo_esperado_de_credenciales()
    assert {type(error) for error in errores} == {SesionInvalida}
    assert {error.motivo for error in errores} == {errores[0].motivo}


@pytest.mark.parametrize("hash_guardado", HASHES_GUARDADOS_QUE_NO_SON_ARGON2)
def test_tkt006_ca03_aplicacion_hash_guardado_no_valido_es_credenciales_invalidas(
    hash_guardado: str,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    sembrar_con_hash_guardado: SembrarConHashGuardado,
    lector: Callable[[], Conexion],
) -> None:
    """Revisión ciclo 1 · F3 · CA-3 esc. 2 y 4 — rechazo: un `password_hash` que no es Argon2 se rechaza como cualquier otro.

    `abrir_sesion` lanza `SesionInvalida` `CREDENCIALES_INVALIDAS` con el mismo mensaje y el mismo cuerpo
    que un correo inexistente y una contraseña errónea; verifica exactamente una vez (contra el hash
    guardado, aunque no sea Argon2); y la fila de `intento_acceso` queda confirmada con `exitoso` falso y
    el usuario. Sin sesión ni asiento de bitácora. Hoy `UnknownHashError` sale dentro del `begin()`: el
    intento se deshace y la excepción no es de contrato.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    danada = sembrar_con_hash_guardado(CORREO_DE_CUENTA_DANADA, hash_guardado)
    contexto, contador = con_contador(crear_contexto(motor_aplicacion, reloj_de_prueba))

    error = rechazar(contexto, Intento(CORREO_DE_CUENTA_DANADA, CONTRASENA_DE_ANA, danada))

    exigir_contrato_de_credenciales_invalidas(error)
    assert contador.verificaciones == [(CONTRASENA_DE_ANA, hash_guardado)]
    de_ana = rechazar(contexto, Intento(CORREO_DE_ANA, CONTRASENA_EQUIVOCADA, ana))
    de_nadie = rechazar(contexto, Intento(CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA, None))
    cuerpos = [e.cuerpo(frozenset(), CORRELACION) for e in (error, de_ana, de_nadie)]
    assert cuerpos[0] == cuerpos[1] == cuerpos[2] == cuerpo_esperado_de_credenciales()
    assert error.mensaje == de_ana.mensaje == de_nadie.mensaje == MENSAJE_LITERAL
    lectura = lector()
    assert sesiones_guardadas(lectura) == []
    assert contar(lectura, "bitacora") == 0
    assert ultimo_acceso_de(lectura, danada) is None
    assert [
        fila for fila in intentos_guardados(lectura) if fila["email"] == CORREO_DE_CUENTA_DANADA
    ] == [
        {
            "email": CORREO_DE_CUENTA_DANADA,
            "usuario_id": danada,
            "exitoso": False,
            "ocurrido_en": reloj_de_prueba.ahora,
            "origen_ip": ORIGEN_IP,
        }
    ]


# --------------------------------------------------------------------------- TC-27


@pytest.mark.parametrize("escenario", ESCENARIOS_DE_RECHAZO)
def test_tkt006_ca03_aplicacion_el_intento_fallido_sobrevive(
    escenario: str,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-27 · CA-3 esc. 4 · RNF-04 — el rechazo no deshace la fila de `intento_acceso`.

    Se calcula dentro de `begin()` y se lanza fuera: una conexión nueva ve, tras capturar el `401`, una
    sola fila con `exitoso` falso, el correo tal como se escribió, el usuario (o nulo si no existe),
    la hora del reloj y el origen. La parte HTTP del mismo TC-27 la añade la fila 7.
    """
    intento = preparar_intento(escenario, sembrar_usuario)
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    rechazar(contexto, intento)

    assert intentos_guardados(lector()) == [
        {
            "email": intento.correo_escrito,
            "usuario_id": intento.usuario_id,
            "exitoso": False,
            "ocurrido_en": reloj_de_prueba.ahora,
            "origen_ip": ORIGEN_IP,
        }
    ]


def test_tkt006_ca03_aplicacion_cada_intento_fallido_deja_su_fila(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-27 · CA-3 esc. 4 · RNF-04 — tres fallos seguidos son tres filas: el conteo de TKT-057 depende de ello."""
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    for _ in range(3):
        rechazar(contexto, Intento(CORREO_DE_ANA, CONTRASENA_EQUIVOCADA, ana))
    rechazar(contexto, Intento(CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA, None))

    guardados = intentos_guardados(lector())
    assert Counter(
        (fila["email"], fila["usuario_id"], fila["exitoso"]) for fila in guardados
    ) == Counter({(CORREO_DE_ANA, ana, False): 3, (CORREO_INEXISTENTE, None, False): 1})


def test_tkt006_ca03_aplicacion_el_fallo_no_borra_el_intento_de_un_inicio_correcto_previo(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-27 · CA-2 · CA-3 esc. 4 — el historial solo se anexa: un fallo posterior conserva el intento exitoso."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)
    abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    rechazar(contexto, Intento(CORREO_DE_ANA, CONTRASENA_EQUIVOCADA, ana))

    resultados = sorted(fila["exitoso"] for fila in intentos_guardados(lector()))
    assert resultados == [False, True]


# --------------------------------------------------------------------------- CA-2 (abrir_sesion)


def test_tkt006_ca02_aplicacion_inicio_correcto_devuelve_al_usuario_autenticado(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """CA-2 esc. 1 · M2 — `abrir_sesion` devuelve el usuario, sus roles y las dos caducidades.

    Con el reloj adelantado siete minutos, para que ninguna hora salga de otro reloj que el inyectado.
    """
    from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    reloj_de_prueba.avanzar(timedelta(minutes=7))
    ahora = reloj_de_prueba.ahora
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    abierta = abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    assert isinstance(abierta, UsuarioAutenticado)
    assert abierta.usuario_id == ana
    assert abierta.nombre == "Ana Torres"
    assert abierta.email == CORREO_DE_ANA
    assert abierta.roles == frozenset({ROL_DE_ANA})
    assert isinstance(abierta.roles, frozenset)
    assert abierta.sesion_id.version == 4
    assert abierta.expira_en == ahora + timedelta(hours=12)
    assert abierta.expira_por_inactividad_en == ahora + timedelta(minutes=30)


def test_tkt006_ca02_aplicacion_inicio_correcto_escribe_la_sesion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-2 esc. 1 · ADR-014 — una fila de `sesion` con el id devuelto, confirmada y con `revocada_en` nulo."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    reloj_de_prueba.avanzar(timedelta(minutes=7))
    ahora = reloj_de_prueba.ahora
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    abierta = abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    assert sesiones_guardadas(lector()) == [
        {
            "id": abierta.sesion_id,
            "usuario_id": ana,
            "creada_en": ahora,
            "expira_en": ahora + timedelta(hours=12),
            "ultima_actividad": ahora,
            "revocada_en": None,
            "origen_ip": ORIGEN_IP,
            "agente_usuario": AGENTE_USUARIO,
        }
    ]


def test_tkt006_ca02_aplicacion_inicio_correcto_asienta_el_intento_y_el_ultimo_acceso(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-2 esc. 1 — `intento_acceso` con `exitoso` verdadero y `usuario.ultimo_acceso` actualizado."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    assert ultimo_acceso_de(lector(), ana) is None
    reloj_de_prueba.avanzar(timedelta(minutes=7))
    ahora = reloj_de_prueba.ahora
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    lectura = lector()
    assert intentos_guardados(lectura) == [
        {
            "email": CORREO_DE_ANA,
            "usuario_id": ana,
            "exitoso": True,
            "ocurrido_en": ahora,
            "origen_ip": ORIGEN_IP,
        }
    ]
    assert ultimo_acceso_de(lectura, ana) == ahora


def test_tkt006_ca02_aplicacion_correo_sin_distinguir_mayusculas(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-2 esc. 2 · PA-T10 — «Ana@Cimenta.TEST» abre la sesión del mismo usuario; el intento guarda lo escrito."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    abierta = abrir_sesion(
        contexto,
        correo_escrito="Ana@Cimenta.TEST",
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=None,
        agente_usuario=None,
    )

    assert abierta.usuario_id == ana
    assert abierta.email == CORREO_DE_ANA
    assert [fila["email"] for fila in intentos_guardados(lector())] == ["Ana@Cimenta.TEST"]
    assert [fila["origen_ip"] for fila in intentos_guardados(lector())] == [None]
    assert [
        (fila["origen_ip"], fila["agente_usuario"]) for fila in sesiones_guardadas(lector())
    ] == [(None, None)]


def test_tkt006_ca08_aplicacion_las_caducidades_salen_de_la_configuracion(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-8 esc. 4 · PA-T2 — con 90 y 10 minutos configurados, `expira_en` y la inactividad los respetan."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    ahora = reloj_de_prueba.ahora
    contexto = crear_contexto(
        motor_aplicacion,
        reloj_de_prueba,
        entorno={
            "CIMENTA_SESION_CADUCIDAD_MINUTOS": "90",
            "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10",
        },
    )

    abierta = abrir_sesion(
        contexto,
        correo_escrito=CORREO_DE_ANA,
        contrasena=CONTRASENA_DE_ANA,
        origen_ip=ORIGEN_IP,
        agente_usuario=AGENTE_USUARIO,
    )

    assert abierta.expira_en == ahora + timedelta(minutes=90)
    assert abierta.expira_por_inactividad_en == ahora + timedelta(minutes=10)
    assert [fila["expira_en"] for fila in sesiones_guardadas(lector())] == [
        ahora + timedelta(minutes=90)
    ]


def test_tkt006_ca02_aplicacion_dos_inicios_abren_dos_sesiones_distintas(
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """CA-2 esc. 3 · regla 9 — cada inicio genera su propio identificador opaco; no se reutiliza ninguno."""
    from cimenta.identidad.aplicacion.sesiones import abrir_sesion

    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contexto = crear_contexto(motor_aplicacion, reloj_de_prueba)

    primera, segunda = (
        abrir_sesion(
            contexto,
            correo_escrito=CORREO_DE_ANA,
            contrasena=CONTRASENA_DE_ANA,
            origen_ip=ORIGEN_IP,
            agente_usuario=AGENTE_USUARIO,
        )
        for _ in range(2)
    )

    assert primera.sesion_id != segunda.sesion_id
    assert {fila["id"] for fila in sesiones_guardadas(lector())} == {
        primera.sesion_id,
        segunda.sesion_id,
    }


# --------------------------------------------------------------------------- contexto (sin Docker)


def test_tkt006_car4_aplicacion_construir_contexto_no_pide_el_motor_hasta_usarlo(
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-R4 · D-2 — `construir_contexto` es perezoso: el proveedor de motor se llama al usar la fábrica, una vez.

    `fastapi dev` y `uvicorn` construyen la aplicación sin variables de base; si construir el contexto
    pidiera el motor, ese arranque fallaría. Sin Docker: el motor es una URL que nunca se conecta.
    """
    from cimenta.identidad.aplicacion.contexto import construir_contexto

    motor = create_engine("postgresql+psycopg://nadie:nada@127.0.0.1:1/ninguna")
    pedidos: list[int] = []

    def proveedor() -> Engine:
        pedidos.append(1)
        return motor

    try:
        contexto = construir_contexto(
            proveedor_motor=proveedor, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA
        )
        assert pedidos == []

        primera = contexto.fabrica_sesiones()
        segunda = contexto.fabrica_sesiones()

        assert pedidos == [1]
        assert primera is segunda
        assert primera.kw["bind"] is motor
    finally:
        motor.dispose()


def test_tkt006_ca08_aplicacion_construir_contexto_toma_configuracion_reloj_y_contrasenas(
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-8 esc. 4 · CA-3 esc. 3 — el contexto lleva la configuración del entorno, el reloj dado y el hash de descarte.

    El hash de descarte existe ya al construir (no en la primera petición) y usa los costes del entorno.
    """
    from cimenta.identidad.aplicacion.contexto import construir_contexto

    motor = create_engine("postgresql+psycopg://nadie:nada@127.0.0.1:1/ninguna")
    try:
        contexto = construir_contexto(
            proveedor_motor=lambda: motor,
            reloj=reloj_de_prueba,
            entorno={**ENTORNO_DE_PRUEBA, "CIMENTA_SESION_INACTIVIDAD_MINUTOS": "10"},
        )

        assert contexto.reloj is reloj_de_prueba
        assert contexto.configuracion.caducidad_inactividad == timedelta(minutes=10)
        assert contexto.configuracion.caducidad_absoluta == timedelta(hours=12)
        assert contexto.contrasenas.hash_de_descarte.startswith("$argon2id$v=19$m=8192,t=1,p=1$")
    finally:
        motor.dispose()


def test_tkt006_ca08_aplicacion_construir_contexto_sin_reloj_usa_el_del_sistema() -> None:
    """CA-8 — sin reloj inyectado, el contexto usa `reloj_del_sistema`, que devuelve la hora actual con zona."""
    from cimenta.identidad.aplicacion.contexto import construir_contexto
    from cimenta.identidad.aplicacion.reloj import reloj_del_sistema

    motor = create_engine("postgresql+psycopg://nadie:nada@127.0.0.1:1/ninguna")
    try:
        contexto = construir_contexto(
            proveedor_motor=lambda: motor, reloj=None, entorno=ENTORNO_DE_PRUEBA
        )

        assert contexto.reloj is reloj_del_sistema
        assert contexto.reloj().tzinfo is not None
    finally:
        motor.dispose()


def test_tkt006_car4_aplicacion_usuario_autenticado_es_inmutable(
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-R4 · M7 — `UsuarioAutenticado` es `dataclass(frozen=True, slots=True)` con sus siete campos.

    Lo que una petición recibe como «quien llama» no se puede alterar a mitad de camino.
    """
    from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado

    ahora = reloj_de_prueba.ahora
    usuario = UsuarioAutenticado(
        usuario_id=uuid.uuid4(),
        sesion_id=uuid.uuid4(),
        nombre="Ana Torres",
        email=CORREO_DE_ANA,
        roles=frozenset({ROL_DE_ANA}),
        expira_en=ahora + timedelta(hours=12),
        expira_por_inactividad_en=ahora + timedelta(minutes=30),
    )

    atributo = "roles"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(usuario, atributo, frozenset())
    assert not hasattr(usuario, "__dict__")  # slots
    assert [campo.name for campo in dataclasses.fields(UsuarioAutenticado)] == [
        "usuario_id",
        "sesion_id",
        "nombre",
        "email",
        "roles",
        "expira_en",
        "expira_por_inactividad_en",
    ]


def test_tkt006_car4_aplicacion_contexto_de_identidad_es_inmutable(
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-R4 · M7 — `ContextoIdentidad` es `dataclass(frozen=True, slots=True)` con sus cuatro campos.

    Una prueba lo cambia con `dataclasses.replace` (TC-26), nunca asignando sobre el original.
    """
    from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, construir_contexto

    motor = create_engine("postgresql+psycopg://nadie:nada@127.0.0.1:1/ninguna")
    try:
        contexto = construir_contexto(
            proveedor_motor=lambda: motor, reloj=reloj_de_prueba, entorno=ENTORNO_DE_PRUEBA
        )

        atributo = "reloj"
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(contexto, atributo, None)
        assert not hasattr(contexto, "__dict__")  # slots
        assert [campo.name for campo in dataclasses.fields(ContextoIdentidad)] == [
            "fabrica_sesiones",
            "configuracion",
            "contrasenas",
            "reloj",
        ]
    finally:
        motor.dispose()


# =========================================================================== HTTP (fila 7, tanda 1)
#
# Todo lo que sigue entra por `POST /api/v1/sesion` con el `cliente` de `conftest.py` (HTTPS, el rol de
# aplicación y el reloj de prueba). Ningún nombre de caso lleva la palabra «aplicacion». No hay token
# CSRF: exigirlo en `iniciar_sesion` es de TKT-057. Rojo esperado: `crear_aplicacion` aún no acepta
# `motor`, `reloj` ni `entorno` (TypeError en la *fixture* `aplicacion_identidad`); con la firma pedida y
# sin las rutas, `404 NO_ENCONTRADO`.

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
COOKIE_SESION = "cimenta_sesion"
CONTRASENA_SECRETA = "Clave-Secreta-987"
CLAVES_DE_USUARIO_ACTUAL = {"id", "nombre", "email", "roles", "sesion"}
CLAVES_DE_ERROR_DE_SESION = {"tipo", "motivo", "mensaje", "correlacion_id"}
CLAVES_DE_ERROR_DE_VALIDACION = {"tipo", "mensaje", "errores", "correlacion_id"}
Respuesta = Any


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def cookies_fijadas(respuesta: Respuesta) -> list[tuple[str, Morsel[str]]]:
    """Cada `Set-Cookie` de la respuesta, interpretado con la biblioteca estándar."""
    resultado: list[tuple[str, Morsel[str]]] = []
    for cabecera in respuesta.headers.get_list("set-cookie"):
        galleta: SimpleCookie = SimpleCookie()
        galleta.load(cabecera)
        resultado.extend(galleta.items())
    return resultado


def una_cookie(respuesta: Respuesta, nombre: str) -> Morsel[str]:
    """La única cookie con ese nombre que fija la respuesta; dos o ninguna es un fallo."""
    encontradas = [morsel for clave, morsel in cookies_fijadas(respuesta) if clave == nombre]
    assert len(encontradas) == 1, (
        f"Se esperaba exactamente un Set-Cookie de {nombre}; hay {len(encontradas)}: "
        f"{respuesta.headers.get_list('set-cookie')}"
    )
    return encontradas[0]


def lineas_json(registro: io.StringIO) -> list[dict[str, Any]]:
    """Cada línea no vacía del registro técnico, como JSON. Una que no lo sea falla la prueba."""
    lineas = [linea for linea in registro.getvalue().splitlines() if linea.strip()]
    return [json.loads(linea) for linea in lineas]


def iniciar_por_http(
    cliente: TestClient, correo: str, contrasena: str, *, agente: str = AGENTE_USUARIO
) -> Respuesta:
    """`POST /api/v1/sesion` con las credenciales indicadas."""
    return cliente.post(
        RUTA_SESION,
        json={"email": correo, "contrasena": contrasena},
        headers={"User-Agent": agente},
    )


def exigir_credenciales_invalidas(respuesta: Respuesta) -> None:
    """El contrato de error completo de CA-3 y CA-4 por HTTP: `401 SESION CREDENCIALES_INVALIDAS`, sin `detail`."""
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == "CREDENCIALES_INVALIDAS"
    assert cuerpo["mensaje"] == MENSAJE_LITERAL
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorSesion", cuerpo)
    assert respuesta.headers.get_list("set-cookie") == []


def sin_correlacion(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {clave: valor for clave, valor in cuerpo.items() if clave != "correlacion_id"}


def con_contador_en_la_aplicacion(aplicacion: FastAPI) -> ContadorDeContrasenas:
    """Coloca un contador sobre las contraseñas del contexto de la aplicación en marcha (`dataclasses.replace`)."""
    contexto = aplicacion.state.identidad
    contador = ContadorDeContrasenas(contexto.contrasenas)
    aplicacion.state.identidad = dataclasses.replace(contexto, contrasenas=contador)
    return contador


# --------------------------------------------------------------------------- TC-20


def test_tkt006_ca02_inicio_correcto(
    cliente: TestClient, reloj_de_prueba: RelojDePrueba, sembrar_usuario: SembrarUsuario
) -> None:
    """TC-20 · CA-2 esc. 1 · M2 — 200 con `UsuarioActual`: id, nombre, correo, roles y las dos caducidades.

    El cuerpo tiene exactamente las cinco claves, valida contra el borrador y lleva `X-Correlacion-Id`. La
    caducidad absoluta es el reloj más 12 horas y la de inactividad, más 30 minutos (valores asumidos,
    PA-T2).
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    reloj_de_prueba.avanzar(timedelta(minutes=7))
    ahora = reloj_de_prueba.ahora

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    assert respuesta.status_code == 200
    assert uuid.UUID(respuesta.headers[CABECERA]).version == 4
    cuerpo = respuesta.json()
    assert set(cuerpo) == CLAVES_DE_USUARIO_ACTUAL
    validar_contra("UsuarioActual", cuerpo)
    assert cuerpo["id"] == str(ana)
    assert cuerpo["nombre"] == "Ana Torres"
    assert cuerpo["email"] == CORREO_DE_ANA
    assert cuerpo["roles"] == [ROL_DE_ANA]
    assert set(cuerpo["sesion"]) == {"expira_en", "expira_por_inactividad_en"}
    expira_en = datetime.fromisoformat(cuerpo["sesion"]["expira_en"])
    por_inactividad = datetime.fromisoformat(cuerpo["sesion"]["expira_por_inactividad_en"])
    assert expira_en == ahora + timedelta(hours=12)
    assert por_inactividad == ahora + timedelta(minutes=30)


def test_tkt006_ca02_inicio_correcto_escribe_sesion_intento_y_ultimo_acceso(
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-20 · CA-2 esc. 1 · RNF-04 — una fila en `sesion`, otra en `intento_acceso` y `ultimo_acceso` al día.

    Leído con una conexión nueva. `sesion`: `creada_en` y `ultima_actividad` valen el reloj, `expira_en`
    más 12 horas, `revocada_en` nulo, el origen del cliente de pruebas y el agente de la petición.
    `intento_acceso`: exitoso, con el usuario y el correo tal como se escribió.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    reloj_de_prueba.avanzar(timedelta(minutes=7))
    ahora = reloj_de_prueba.ahora

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    assert respuesta.status_code == 200
    lectura = lector()
    assert sesiones_guardadas(lectura) == [
        {
            "id": uuid.UUID(una_cookie(respuesta, COOKIE_SESION).value),
            "usuario_id": ana,
            "creada_en": ahora,
            "expira_en": ahora + timedelta(hours=12),
            "ultima_actividad": ahora,
            "revocada_en": None,
            "origen_ip": "testclient",
            "agente_usuario": AGENTE_USUARIO,
        }
    ]
    assert intentos_guardados(lectura) == [
        {
            "email": CORREO_DE_ANA,
            "usuario_id": ana,
            "exitoso": True,
            "ocurrido_en": ahora,
            "origen_ip": "testclient",
        }
    ]
    assert ultimo_acceso_de(lectura, ana) == ahora


def test_tkt006_ca02_la_respuesta_no_lleva_contrasena_ni_hash(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-20 · CA-2 esc. 1 · RNF-03 — ni la contraseña ni el hash ni `password_hash` salen en el cuerpo o las cabeceras."""
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    hash_de_ana = hash_guardado_de(lector(), ana)

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    assert respuesta.status_code == 200
    visible = respuesta.text + str(dict(respuesta.headers))
    for prohibido in (CONTRASENA_DE_ANA, hash_de_ana, "$argon2", "password_hash", "contrasena"):
        assert prohibido not in visible


# --------------------------------------------------------------------------- TC-21


def test_tkt006_ca02_atributos_de_la_cookie_de_sesion(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-21 · CA-2 esc. 1 · RNF-02 — `cimenta_sesion` vale el id de la fila y lleva `HttpOnly`, `Secure`, `SameSite=Lax` y `Path=/`.

    Una sola cookie de sesión en la respuesta. `SameSite` se compara sin distinguir mayúsculas.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    cookie = una_cookie(respuesta, COOKIE_SESION)
    assert [fila["id"] for fila in sesiones_guardadas(lector())] == [uuid.UUID(cookie.value)]
    assert cookie["httponly"]
    assert cookie["secure"]
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"


# --------------------------------------------------------------------------- TC-22


def test_tkt006_ca02_correo_sin_distinguir_mayusculas(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-22 · CA-2 esc. 2 · PA-T10 — «Ana@Cimenta.TEST» abre la sesión del mismo usuario y el intento guarda lo escrito.

    El cuerpo devuelve el correo guardado, en minúsculas; `intento_acceso.email` conserva las mayúsculas.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    respuesta = iniciar_por_http(cliente, "Ana@Cimenta.TEST", CONTRASENA_DE_ANA)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    validar_contra("UsuarioActual", cuerpo)
    assert cuerpo["id"] == str(ana)
    assert cuerpo["email"] == CORREO_DE_ANA
    assert [fila["email"] for fila in intentos_guardados(lector())] == ["Ana@Cimenta.TEST"]


# --------------------------------------------------------------------------- TC-23


def test_tkt006_ca02_la_cookie_es_opaca(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-23 · CA-2 esc. 3 · regla 9 — el valor es un UUID v4 igual a `sesion.id`, sin datos del usuario ni firma.

    Sin puntos (no es un JWT ni una cookie firmada). Ni el valor ni su lectura como base64, si la admite,
    contienen el correo, el nombre ni un rol. El almacén del cliente la conserva y la reenviará.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)

    valor = una_cookie(respuesta, COOKIE_SESION).value
    identificador = uuid.UUID(valor)
    assert identificador.version == 4
    assert str(identificador) == valor
    assert [fila["id"] for fila in sesiones_guardadas(lector())] == [identificador]
    assert "." not in valor
    assert cliente.cookies.get(COOKIE_SESION) == valor
    lecturas = [valor.lower()]
    try:
        relleno = "=" * (-len(valor) % 4)
        lecturas.append(base64.urlsafe_b64decode(valor + relleno).decode("latin-1").lower())
    except (binascii.Error, ValueError):
        pass
    for lectura in lecturas:
        for dato in (CORREO_DE_ANA, "ana", "torres", ROL_DE_ANA.lower(), "director"):
            assert dato not in lectura


# --------------------------------------------------------------------------- TC-24


def test_tkt006_ca03_contrasena_equivocada(
    cliente: TestClient,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-24 · CA-3 esc. 1 · CA-R5 — rechazo: `401 SESION CREDENCIALES_INVALIDAS` con el contrato completo.

    Sin fila en `sesion` ni `Set-Cookie`; `intento_acceso` recibe una fila con `exitoso` falso y el
    usuario; la bitácora no recibe ningún asiento (un rechazo anónimo no es un `DENEGAR`).
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    respuesta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)

    exigir_credenciales_invalidas(respuesta)
    lectura = lector()
    assert sesiones_guardadas(lectura) == []
    assert contar(lectura, "bitacora") == 0
    assert [
        (fila["email"], fila["usuario_id"], fila["exitoso"]) for fila in intentos_guardados(lectura)
    ] == [(CORREO_DE_ANA, ana, False)]
    assert ultimo_acceso_de(lectura, ana) is None
    assert COOKIE_SESION not in cliente.cookies


# --------------------------------------------------------------------------- TC-25


def test_tkt006_ca03_correo_inexistente_indistinguible(
    cliente: TestClient, sembrar_usuario: SembrarUsuario, lector: Callable[[], Conexion]
) -> None:
    """TC-25 · CA-3 esc. 2 — rechazo: correo inexistente y contraseña errónea responden igual salvo `correlacion_id`.

    Mismo código, `tipo`, `motivo` y `mensaje`; los cuerpos sin `correlacion_id` son iguales; las
    cabeceras tienen los mismos nombres y la misma longitud. `intento_acceso` guarda `usuario_id` nulo
    para el correo que no existe y el usuario para el que sí.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    de_ana = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)
    de_nadie = iniciar_por_http(cliente, CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA)

    exigir_credenciales_invalidas(de_ana)
    exigir_credenciales_invalidas(de_nadie)
    assert de_ana.status_code == de_nadie.status_code
    assert sin_correlacion(de_ana.json()) == sin_correlacion(de_nadie.json())
    assert de_ana.json()["correlacion_id"] != de_nadie.json()["correlacion_id"]
    assert sorted(de_ana.headers) == sorted(de_nadie.headers)
    assert de_ana.headers["content-length"] == de_nadie.headers["content-length"]
    assert de_ana.headers["content-type"] == de_nadie.headers["content-type"]
    assert Counter(
        (fila["email"], fila["usuario_id"], fila["exitoso"])
        for fila in intentos_guardados(lector())
    ) == Counter({(CORREO_DE_ANA, ana, False): 1, (CORREO_INEXISTENTE, None, False): 1})


@pytest.mark.parametrize("hash_guardado", HASHES_GUARDADOS_QUE_NO_SON_ARGON2)
def test_tkt006_ca03_hash_guardado_no_valido_es_indistinguible_por_http(
    hash_guardado: str,
    cliente: TestClient,
    sembrar_usuario: SembrarUsuario,
    sembrar_con_hash_guardado: SembrarConHashGuardado,
    lector: Callable[[], Conexion],
) -> None:
    """Revisión ciclo 1 · F3 · CA-3 esc. 2 — rechazo: la cuenta con un hash que no es Argon2 responde `401`, no `500`.

    `401 SESION CREDENCIALES_INVALIDAS` validado contra `ErrorSesion`, sin `detail` ni `Set-Cookie`, con
    el cuerpo igual salvo `correlacion_id` al de una contraseña errónea y al de un correo inexistente, y
    las mismas cabeceras. Un `500` solo para esa cuenta enumeraría las cuentas dañadas. Sin fila en
    `sesion`; el intento queda asentado con el usuario.
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    danada = sembrar_con_hash_guardado(CORREO_DE_CUENTA_DANADA, hash_guardado)

    de_danada = iniciar_por_http(cliente, CORREO_DE_CUENTA_DANADA, CONTRASENA_DE_ANA)
    de_ana = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)
    de_nadie = iniciar_por_http(cliente, CORREO_INEXISTENTE, CONTRASENA_EQUIVOCADA)

    exigir_credenciales_invalidas(de_danada)
    exigir_credenciales_invalidas(de_ana)
    exigir_credenciales_invalidas(de_nadie)
    assert sin_correlacion(de_danada.json()) == sin_correlacion(de_ana.json())
    assert sin_correlacion(de_danada.json()) == sin_correlacion(de_nadie.json())
    assert sorted(de_danada.headers) == sorted(de_ana.headers) == sorted(de_nadie.headers)
    assert de_danada.headers["content-length"] == de_ana.headers["content-length"]
    assert de_danada.headers["content-type"] == de_ana.headers["content-type"]
    lectura = lector()
    assert sesiones_guardadas(lectura) == []
    assert contar(lectura, "bitacora") == 0
    assert Counter(
        (fila["email"], fila["usuario_id"], fila["exitoso"]) for fila in intentos_guardados(lectura)
    ) == Counter(
        {
            (CORREO_DE_CUENTA_DANADA, danada, False): 1,
            (CORREO_DE_ANA, ana, False): 1,
            (CORREO_INEXISTENTE, None, False): 1,
        }
    )


# --------------------------------------------------------------------------- TC-27 (HTTP)


@pytest.mark.parametrize("escenario", ESCENARIOS_DE_RECHAZO)
def test_tkt006_ca03_el_intento_fallido_sobrevive_al_401(
    escenario: str,
    cliente: TestClient,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-27 · CA-3 esc. 4 · RNF-04 — tras el `401` por HTTP, `intento_acceso` conserva la fila del intento.

    El rechazo se lanza fuera de la transacción: una conexión nueva ve una sola fila con `exitoso` falso,
    el correo tal como se escribió, el usuario (o nulo), la hora del reloj y el origen de la petición.
    """
    intento = preparar_intento(escenario, sembrar_usuario)

    respuesta = iniciar_por_http(cliente, intento.correo_escrito, intento.contrasena)

    exigir_credenciales_invalidas(respuesta)
    assert intentos_guardados(lector()) == [
        {
            "email": intento.correo_escrito,
            "usuario_id": intento.usuario_id,
            "exitoso": False,
            "ocurrido_en": reloj_de_prueba.ahora,
            "origen_ip": "testclient",
        }
    ]


# --------------------------------------------------------------------------- TC-28


def test_tkt006_ca04_usuario_desactivado_no_inicia(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-28 · CA-4 · PA-T4 — rechazo: un desactivado con su contraseña correcta recibe el mismo `401` que una errónea.

    Cuerpo igual al de la contraseña equivocada salvo `correlacion_id`; sin fila en `sesion`; una sola
    verificación de hash por intento, la del desactivado contra su propio hash; `intento_acceso` con
    `exitoso` falso y el usuario.
    """
    baja = sembrar_usuario("baja@cimenta.test", "Clave-De-Baja-3", activo=False, nombre="Baja")
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contador = con_contador_en_la_aplicacion(aplicacion_identidad)

    desactivado = iniciar_por_http(cliente, "baja@cimenta.test", "Clave-De-Baja-3")
    equivocada = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)

    exigir_credenciales_invalidas(desactivado)
    exigir_credenciales_invalidas(equivocada)
    assert sin_correlacion(desactivado.json()) == sin_correlacion(equivocada.json())
    assert [contrasena for contrasena, _ in contador.verificaciones] == [
        "Clave-De-Baja-3",
        CONTRASENA_EQUIVOCADA,
    ]
    lectura = lector()
    assert contador.verificaciones[0][1] == hash_guardado_de(lectura, baja)
    assert sesiones_guardadas(lectura) == []
    assert [
        (fila["email"], fila["usuario_id"], fila["exitoso"])
        for fila in intentos_guardados(lectura)
        if fila["email"] == "baja@cimenta.test"
    ] == [("baja@cimenta.test", baja, False)]


# --------------------------------------------------------------------------- TC-29

CASOS_DE_FORMA = [
    pytest.param(
        {"email": "no-es-un-correo", "contrasena": CONTRASENA_DE_ANA},
        "email",
        "FORMATO",
        id="correo_sin_arroba",
    ),
    pytest.param(
        {"email": "Ana <ana@cimenta.test>", "contrasena": CONTRASENA_DE_ANA},
        "email",
        "FORMATO",
        id="correo_con_nombre_y_signos",
    ),
    pytest.param(
        {"email": " ana@cimenta.test", "contrasena": CONTRASENA_DE_ANA},
        "email",
        "FORMATO",
        id="correo_con_espacio_al_inicio",
    ),
    pytest.param(
        {"email": "ana@cimenta.test ", "contrasena": CONTRASENA_DE_ANA},
        "email",
        "FORMATO",
        id="correo_con_espacio_al_final",
    ),
    pytest.param(
        {"email": CORREO_DE_ANA, "contrasena": ""},
        "contrasena",
        "OBLIGATORIO",
        id="contrasena_vacia",
    ),
    pytest.param({"contrasena": CONTRASENA_DE_ANA}, "email", "OBLIGATORIO", id="sin_correo"),
    pytest.param({"email": CORREO_DE_ANA}, "contrasena", "OBLIGATORIO", id="sin_contrasena"),
]


@pytest.mark.parametrize(("enviado", "campo", "codigo"), CASOS_DE_FORMA)
def test_tkt006_ca05_forma_invalida(
    enviado: dict[str, str],
    campo: str,
    codigo: str,
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-29 · CA-5 · PA-T5 `(asumido)` — rechazo: `422 VALIDACION` con el campo infractor y su código; nada se verifica ni se escribe.

    El cuerpo tiene exactamente `tipo`, `mensaje`, `errores` y `correlacion_id`, sin `detail`, y valida
    contra `ErrorValidacion`. Un cuerpo mal formado no verifica ningún hash ni se asienta en
    `intento_acceso` ni abre sesión; la contraseña enviada no vuelve en la respuesta.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))
    contador = con_contador_en_la_aplicacion(aplicacion_identidad)

    respuesta = cliente.post(RUTA_SESION, json=enviado)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_VALIDACION
    assert cuerpo["tipo"] == "VALIDACION"
    assert [(error["campo"], error["codigo"]) for error in cuerpo["errores"]] == [(campo, codigo)]
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorValidacion", cuerpo)
    if enviado.get("contrasena"):
        assert enviado["contrasena"] not in respuesta.text
    assert contador.verificaciones == []
    lectura = lector()
    assert sesiones_guardadas(lectura) == []
    assert intentos_guardados(lectura) == []
    assert contar(lectura, "bitacora") == 0
    assert respuesta.headers.get_list("set-cookie") == []


# --------------------------------------------------------------------------- TC-30


def test_tkt006_ca15_la_contrasena_no_viaja(
    cliente: TestClient,
    registro_tecnico: io.StringIO,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-30 · CA-15 esc. 3 · conv-seguridad §6 — rechazo: ni la contraseña ni un hash aparecen en una respuesta ni en el registro.

    Con una contraseña equivocada y después la correcta, ni ese texto ni `$argon2` ni el hash guardado
    figuran en ningún cuerpo, cabecera o línea del registro técnico (que solo anota método, ruta y estado).
    """
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_SECRETA, roles=(ROL_DE_ANA,))
    hash_de_ana = hash_guardado_de(lector(), ana)

    equivocada = iniciar_por_http(cliente, CORREO_DE_ANA, "Clave-Secreta-986")
    correcta = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_SECRETA)

    assert equivocada.status_code == 401
    assert correcta.status_code == 200
    registro = registro_tecnico.getvalue()
    assert registro.strip(), "el registro técnico debe tener las líneas de las peticiones"
    visibles = [
        equivocada.text + str(dict(equivocada.headers)),
        correcta.text + str(dict(correcta.headers)),
        registro,
    ]
    for texto in visibles:
        for prohibido in (CONTRASENA_SECRETA, "Clave-Secreta-986", "$argon2", hash_de_ana):
            assert prohibido not in texto


# --------------------------------------------------------------------------- TC-31


def test_tkt006_ca12_denegaciones_anonimas_fuera_de_la_bitacora(
    cliente: TestClient,
    registro_tecnico: io.StringIO,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-31 · CA-12 esc. 3 · RNF-13 — rechazo: los `401` anónimos van a `intento_acceso` y al registro, no a la bitácora.

    Un inicio con contraseña errónea y un `GET /api/v1/sesion` sin cookie: la bitácora sigue vacía,
    `intento_acceso` tiene la fila del intento y el registro técnico tiene una línea `peticion_atendida`
    con `estado` 401 y el `correlacion_id` de cada respuesta.
    """
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=(ROL_DE_ANA,))

    inicio = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_EQUIVOCADA)
    consulta = cliente.get(RUTA_SESION)

    assert inicio.status_code == 401
    assert consulta.status_code == 401
    lectura = lector()
    assert contar(lectura, "bitacora") == 0
    assert [fila["exitoso"] for fila in intentos_guardados(lectura)] == [False]
    atendidas = {
        (linea["metodo"], linea["ruta"], linea["estado"], linea["correlacion_id"])
        for linea in lineas_json(registro_tecnico)
        if linea["event"] == "peticion_atendida"
    }
    assert {
        ("POST", RUTA_SESION, 401, inicio.headers[CABECERA]),
        ("GET", RUTA_SESION, 401, consulta.headers[CABECERA]),
    } <= atendidas
