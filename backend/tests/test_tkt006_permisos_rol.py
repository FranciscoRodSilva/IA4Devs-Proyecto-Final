"""Rol por ruta y asiento `DENEGAR` (TKT-006, fila 10, entrega B): TC-60 a TC-64 y TC-67, con Docker.

`exigir_rol(*roles)` protege una ruta con la unión de los roles de quien llama (M7). Un `403` de un
usuario autenticado se asienta en la bitácora como `DENEGAR`, en una transacción propia, atribuido al
usuario (`entidad_tipo = 'usuario'`, `entidad_id = usuario_id`), sin `regla_negocio`, sin obra, sin
`datos_antes` y con `datos_despues = {metodo, ruta, roles_requeridos}` (M9, `RN-04`, C-1 enmendado).
Las denegaciones anónimas no entran en la bitácora. Si la bitácora falla, el `403` se mantiene y el
fallo queda en el registro técnico con la correlación de la petición (`PA-T6`).

Las rutas de prueba son de la suite, no del producto, y toman `exigir_rol` y `sesion_vigente` **desde
`cimenta.identidad.interfaz`**, que es lo que importará cualquier otro módulo. Se añaden a la aplicación
real dentro de cada caso (`agregar_rutas_de_prueba`): mientras `exigir_rol` no exista en la interfaz,
cada caso falla con su propio `ImportError` y la recolección no se cae.

Los casos TC-65 y TC-66 y la publicación en la interfaz no necesitan Docker y viven en
`test_tkt006_enrutador.py`.
"""

import functools
import io
import json
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Protocol

import psycopg
import pytest
import yaml
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parents[2]
CABECERA = "X-Correlacion-Id"
RUTA_SESION = "/api/v1/sesion"
RUTA_CIERRE = "/api/v1/sesion/cierre"
RUTA_COMPRAS = "/api/v1/prueba/compras"
RUTA_ALMACEN = "/api/v1/prueba/almacen"
RUTA_DIRECCION = "/api/v1/prueba/direccion"
RUTA_COMPRAS_O_DIRECCION = "/api/v1/prueba/compras-o-direccion"
RUTA_DE_ROLES = "/api/v1/prueba/roles"
RUTA_CON_TRANSACCION = "/api/v1/prueba/direccion-con-transaccion"
COOKIE_SESION = "cimenta_sesion"
CORREO_DE_ANA = "ana@cimenta.test"
CONTRASENA_DE_ANA = "Clave-Correcta-1"
CORREO_DE_LUIS = "luis@cimenta.test"
CORREO_DE_LA_PETICION = "transaccion-de-la-peticion@cimenta.test"
CONTRASENA_DE_LUIS = "Clave-De-Luis-2"
AGENTE_USUARIO = "Prueba/1.0"
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
CLAVES_DE_ERROR_DE_PERMISO = {"tipo", "motivo", "mensaje", "roles_requeridos", "correlacion_id"}
CLAVES_DE_ERROR_DE_SESION = {"tipo", "motivo", "mensaje", "correlacion_id"}
CLAVES_DE_DATOS_DE_LA_DENEGACION = {"metodo", "ruta", "roles_requeridos"}
MENSAJES_DE_SESION = {
    "SIN_SESION": "No hay una sesión iniciada.",
    "SESION_CADUCADA": "La sesión caducó. Inicia sesión de nuevo.",
    "SESION_REVOCADA": "La sesión ya no es válida. Inicia sesión de nuevo.",
}
COLUMNAS_DEL_ASIENTO = (
    "id",
    "accion",
    "usuario_id",
    "ocurrido_en",
    "motivo",
    "regla_negocio",
    "entidad_tipo",
    "entidad_id",
    "obra_id",
    "datos_antes_es_nulo",
    "datos_despues",
)

Conexion = psycopg.Connection[tuple[Any, ...]]
Respuesta = Any


class SembrarUsuario(Protocol):
    def __call__(
        self,
        correo: str,
        contrasena: str,
        roles: tuple[str, ...] = (),
        activo: bool = True,
        nombre: str = "Ana Torres",
    ) -> uuid.UUID: ...


class RelojDePrueba(Protocol):
    """Lo que estas pruebas usan de la *fixture* `reloj_de_prueba` de `conftest.py`."""

    ahora: datetime

    def __call__(self) -> datetime: ...

    def avanzar(self, delta: timedelta) -> None: ...


# --------------------------------------------------------------------------- ayudas de la prueba


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def lineas_json(registro: io.StringIO) -> list[dict[str, Any]]:
    """Cada línea no vacía del registro técnico, como JSON. Una que no lo sea falla la prueba."""
    lineas = [linea for linea in registro.getvalue().splitlines() if linea.strip()]
    return [json.loads(linea) for linea in lineas]


def exigir_error_de_permiso(respuesta: Respuesta, roles_requeridos: list[str]) -> None:
    """El contrato de error completo de un `403` por rol (CA-11, CA-12, CA-R5).

    Código, `tipo`, `motivo`, `mensaje` literal, conjunto exacto de claves —sin `detail`, sin `detalle`
    y sin cifras—, `roles_requeridos` en el orden declarado, `correlacion_id` igual a la cabecera y
    validez contra `ErrorPermiso`.
    """
    from cimenta.identidad.api.dependencias import MENSAJE_ROL_INSUFICIENTE as DE_PRODUCCION

    assert DE_PRODUCCION == MENSAJE_ROL_INSUFICIENTE
    assert respuesta.status_code == 403, respuesta.text
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert "detalle" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_PERMISO
    assert cuerpo["tipo"] == "PERMISO"
    assert cuerpo["motivo"] == "ROL_INSUFICIENTE"
    assert cuerpo["mensaje"] == MENSAJE_ROL_INSUFICIENTE
    assert cuerpo["roles_requeridos"] == roles_requeridos
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorPermiso", cuerpo)


def exigir_error_de_sesion(respuesta: Respuesta, motivo: str) -> None:
    """El contrato de error completo de un `401` de sesión: ni `403` ni `detail`."""
    assert respuesta.status_code == 401, respuesta.text
    cuerpo = respuesta.json()
    assert "detail" not in cuerpo
    assert set(cuerpo) == CLAVES_DE_ERROR_DE_SESION
    assert cuerpo["tipo"] == "SESION"
    assert cuerpo["motivo"] == motivo
    assert cuerpo["mensaje"] == MENSAJES_DE_SESION[motivo]
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA]
    validar_contra("ErrorSesion", cuerpo)


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


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


def asientos(conexion: Conexion) -> list[dict[str, Any]]:
    """Todos los asientos de la bitácora por nombre de columna. `datos_antes` solo dice si es NULL de SQL."""
    filas = conexion.execute(
        "SELECT id, accion::text, usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, "
        "entidad_id, obra_id, datos_antes IS NULL, datos_despues FROM bitacora ORDER BY ocurrido_en, id"
    ).fetchall()
    return [dict(zip(COLUMNAS_DEL_ASIENTO, fila, strict=True)) for fila in filas]


def retirar_rol(conexion: Conexion, usuario_id: uuid.UUID, clave: str) -> None:
    conexion.execute(
        "DELETE FROM usuario_rol WHERE usuario_id = %s "
        "AND rol_id = (SELECT id FROM rol WHERE clave = %s)",
        (usuario_id, clave),
    )


def existe_usuario(conexion: Conexion, correo: str) -> bool:
    fila = conexion.execute("SELECT count(*) FROM usuario WHERE email = %s", (correo,)).fetchone()
    assert fila is not None
    return int(fila[0]) == 1


def agregar_rutas_de_prueba(aplicacion: FastAPI) -> list[str]:
    """Las rutas de la suite, protegidas con lo que publica `cimenta.identidad.interfaz`.

    Devuelve la lista donde cada cuerpo de ruta anota «MÉTODO ruta» al ejecutarse: un `401` o un `403`
    la deja vacía, y eso demuestra que la dependencia cortó antes de llegar al cuerpo.
    """
    from cimenta.identidad.interfaz import exigir_rol, sesion_vigente

    ejecutadas: list[str] = []
    enrutador = APIRouter()

    def ruta_de(metodo: str, camino: str) -> Callable[[], dict[str, bool]]:
        def atender() -> dict[str, bool]:
            ejecutadas.append(f"{metodo} {camino}")
            return {"ok": True}

        return atender

    protegidas: list[tuple[str, str, tuple[str, ...]]] = [
        ("GET", RUTA_COMPRAS, ("COMPRAS",)),
        ("GET", RUTA_ALMACEN, ("ALMACEN",)),
        ("GET", RUTA_DIRECCION, ("DIRECCION_GENERAL",)),
        ("POST", RUTA_DIRECCION, ("DIRECCION_GENERAL",)),
        ("GET", RUTA_COMPRAS_O_DIRECCION, ("COMPRAS", "DIRECCION_GENERAL")),
    ]
    for metodo, camino, roles in protegidas:
        enrutador.add_api_route(
            camino,
            ruta_de(metodo, camino),
            methods=[metodo],
            name=f"{metodo.lower()}_{camino.rsplit('/', 1)[-1]}",
            dependencies=[Depends(exigir_rol(*roles))],
        )

    @enrutador.get(RUTA_DE_ROLES, dependencies=[Depends(sesion_vigente)])
    def roles_de_quien_llama(request: Request) -> list[str]:
        return sorted(request.state.roles_de_quien_llama)

    aplicacion.include_router(enrutador)
    return ejecutadas


def agregar_ruta_con_transaccion_propia(aplicacion: FastAPI, motor: Engine) -> list[str]:
    """`GET /api/v1/prueba/direccion-con-transaccion`: la petición abre una transacción y la deshace.

    La primera dependencia abre una `Session`, escribe un usuario y, al terminar la petición, hace
    `rollback`. La segunda es `exigir_rol("DIRECCION_GENERAL")`, que lanza el `403`. Es el «manejador que
    deshace su propia transacción» de CA-12 esc. 2: el asiento `DENEGAR` no puede depender de ella.
    """
    from cimenta.identidad.interfaz import exigir_rol

    escritas: list[str] = []

    def transaccion_de_la_peticion() -> Iterator[Session]:
        with Session(motor) as sesion:
            sesion.execute(
                text(
                    "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
                    "VALUES (:id, 'De la petición', :email, 'sin-hash', true)"
                ),
                {"id": uuid.uuid4(), "email": CORREO_DE_LA_PETICION},
            )
            escritas.append(CORREO_DE_LA_PETICION)
            try:
                yield sesion
            finally:
                sesion.rollback()

    def atender() -> dict[str, bool]:
        return {"ok": True}

    enrutador = APIRouter()
    enrutador.add_api_route(
        RUTA_CON_TRANSACCION,
        atender,
        methods=["GET"],
        dependencies=[
            Depends(transaccion_de_la_peticion),
            Depends(exigir_rol("DIRECCION_GENERAL")),
        ],
    )
    aplicacion.include_router(enrutador)
    return escritas


def espiar_denegaciones(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Anota cada llamada a `asentar_denegacion` de la interfaz de auditoría y la deja pasar al original."""
    import cimenta.auditoria.interfaz as auditoria_interfaz

    original = auditoria_interfaz.asentar_denegacion
    llamadas: list[dict[str, Any]] = []

    def espia(sesion_bd: Session, **argumentos: Any) -> uuid.UUID:
        llamadas.append(argumentos)
        return original(sesion_bd, **argumentos)

    monkeypatch.setattr(auditoria_interfaz, "asentar_denegacion", espia)
    return llamadas


def autenticado_como(usuario_id: uuid.UUID, reloj: RelojDePrueba) -> Any:
    """El `UsuarioAutenticado` de Ana con `RESIDENTE`, como lo entrega `sesion_vigente`."""
    from cimenta.identidad.aplicacion.contexto import UsuarioAutenticado

    return UsuarioAutenticado(
        usuario_id=usuario_id,
        sesion_id=uuid.uuid4(),
        nombre="Ana Torres",
        email=CORREO_DE_ANA,
        roles=frozenset({"RESIDENTE"}),
        expira_en=reloj.ahora + timedelta(hours=12),
        expira_por_inactividad_en=reloj.ahora + timedelta(minutes=30),
    )


def registrar(contexto: Any, usuario: Any, correlacion_id: str) -> None:
    """Llama a `registrar_denegacion` con los argumentos de una denegación por rol de `GET /prueba/direccion`."""
    from cimenta.identidad.aplicacion.denegacion import registrar_denegacion

    registrar_denegacion(
        contexto,
        usuario=usuario,
        motivo="ROL_INSUFICIENTE",
        metodo="GET",
        ruta=RUTA_DIRECCION,
        roles_requeridos=("DIRECCION_GENERAL",),
        correlacion_id=correlacion_id,
    )


@pytest.fixture
def lector(conectar: Callable[..., Conexion], base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


@pytest.fixture
def sentencias(motor_aplicacion: Engine) -> Iterator[list[str]]:
    """Cada sentencia SQL que emite el motor del rol de aplicación mientras dura la prueba."""
    emitidas: list[str] = []

    def anotar(
        conexion: Any, cursor: Any, sentencia: str, parametros: Any, contexto: Any, varias: bool
    ) -> None:
        emitidas.append(sentencia)

    event.listen(motor_aplicacion, "before_cursor_execute", anotar)
    try:
        yield emitidas
    finally:
        event.remove(motor_aplicacion, "before_cursor_execute", anotar)


@dataclass(frozen=True)
class Denegacion:
    """Lo que dejó una denegación de Ana, con rol `RESIDENTE`, en `/prueba/direccion`."""

    respuesta: Respuesta
    usuario_id: uuid.UUID
    sesion_id: uuid.UUID
    ocurrida_en: datetime
    ejecutadas: list[str]


def provocar_denegacion(
    cliente: TestClient,
    aplicacion: FastAPI,
    reloj: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> Denegacion:
    """Ana, solo `RESIDENTE`, abre sesión y cinco minutos después llama a la ruta de `DIRECCION_GENERAL`."""
    ejecutadas = agregar_rutas_de_prueba(aplicacion)
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    sesion_id = iniciar_por_http(cliente)
    reloj.avanzar(timedelta(minutes=5))
    respuesta = cliente.get(RUTA_DIRECCION, headers=con_cookie(sesion_id))
    return Denegacion(respuesta, ana, sesion_id, reloj.ahora, ejecutadas)


# --------------------------------------------------------------------------- TC-60


def test_tkt006_ca06_el_permiso_es_la_union_de_los_roles(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-60 · CA-6 esc. 2 · M7 — con `COMPRAS` y `ALMACEN`, las rutas de cada uno responden `200`.

    El permiso es la unión de los roles del usuario: basta uno de los exigidos por la ruta. Una petición
    permitida no deja ningún asiento en la bitácora.
    """
    ejecutadas = agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("COMPRAS", "ALMACEN"))
    sesion_id = iniciar_por_http(cliente)

    en_compras = cliente.get(RUTA_COMPRAS, headers=con_cookie(sesion_id))
    en_almacen = cliente.get(RUTA_ALMACEN, headers=con_cookie(sesion_id))

    assert (en_compras.status_code, en_compras.json()) == (200, {"ok": True})
    assert (en_almacen.status_code, en_almacen.json()) == (200, {"ok": True})
    assert uuid.UUID(en_compras.headers[CABECERA]).version == 4
    assert ejecutadas == [f"GET {RUTA_COMPRAS}", f"GET {RUTA_ALMACEN}"]
    assert contar(lector(), "bitacora") == 0


def test_tkt006_ca06_tener_un_rol_no_da_los_de_otras_rutas(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-60 · CA-6 esc. 2 — rechazo: con `COMPRAS` y `ALMACEN`, la ruta de `DIRECCION_GENERAL` sigue prohibida.

    La unión es de los roles que se tienen, no de todos: sin este caso, una comprobación que dejara
    pasar a cualquiera con dos o más roles saldría verde.
    """
    ejecutadas = agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("COMPRAS", "ALMACEN"))
    sesion_id = iniciar_por_http(cliente)

    respuesta = cliente.get(RUTA_DIRECCION, headers=con_cookie(sesion_id))

    exigir_error_de_permiso(respuesta, ["DIRECCION_GENERAL"])
    assert ejecutadas == []


def test_tkt006_ca06_un_solo_rol_no_alcanza_para_la_ruta_de_otro(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-60 · CA-6 esc. 2 — rechazo: con solo `COMPRAS`, `ALMACEN` es `403` y `COMPRAS` sigue siendo `200`."""
    agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("COMPRAS",))
    sesion_id = iniciar_por_http(cliente)

    permitida = cliente.get(RUTA_COMPRAS, headers=con_cookie(sesion_id))
    prohibida = cliente.get(RUTA_ALMACEN, headers=con_cookie(sesion_id))

    assert permitida.status_code == 200
    exigir_error_de_permiso(prohibida, ["ALMACEN"])


def test_tkt006_ca06_una_ruta_con_varios_roles_acepta_a_cualquiera_de_ellos(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-60 · CA-6 esc. 2 — `exigir_rol("COMPRAS", "DIRECCION_GENERAL")` deja pasar a cualquiera de los dos y a nadie más.

    Quien solo tiene `DIRECCION_GENERAL` entra; quien solo tiene `ALMACEN` recibe `403` con los dos roles
    exigidos en el orden en que se declararon, y el asiento los repite.
    """
    agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("DIRECCION_GENERAL",))
    sembrar_usuario(CORREO_DE_LUIS, CONTRASENA_DE_LUIS, roles=("ALMACEN",), nombre="Luis Mena")
    de_ana = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    de_luis = iniciar_por_http(cliente, CORREO_DE_LUIS, CONTRASENA_DE_LUIS)

    entra = cliente.get(RUTA_COMPRAS_O_DIRECCION, headers=con_cookie(de_ana))
    no_entra = cliente.get(RUTA_COMPRAS_O_DIRECCION, headers=con_cookie(de_luis))

    assert entra.status_code == 200
    exigir_error_de_permiso(no_entra, ["COMPRAS", "DIRECCION_GENERAL"])
    (asiento,) = asientos(lector())
    assert asiento["datos_despues"]["roles_requeridos"] == ["COMPRAS", "DIRECCION_GENERAL"]


# --------------------------------------------------------------------------- TC-61


def test_tkt006_ca11_retirar_un_rol_surte_efecto(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-61 · CA-11 · M6 · M7 — rechazo: retirado `COMPRAS`, la siguiente petición con la misma cookie es `403`.

    Con la misma sesión: `200` en `/prueba/compras`; se borra la fila de `usuario_rol`; la siguiente es
    `403` `PERMISO` `ROL_INSUFICIENTE` con `roles_requeridos == ["COMPRAS"]`, contrato completo y sin
    cifras. La ruta de roles de quien llama ya no lista `COMPRAS`, y el cuerpo de la ruta no se ejecutó
    la segunda vez.
    """
    ejecutadas = agregar_rutas_de_prueba(aplicacion_identidad)
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE", "COMPRAS"))
    sesion_id = iniciar_por_http(cliente)
    antes = cliente.get(RUTA_COMPRAS, headers=con_cookie(sesion_id))
    assert (antes.status_code, antes.json()) == (200, {"ok": True})

    retirar_rol(lector(), ana, "COMPRAS")
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    despues = cliente.get(RUTA_COMPRAS, headers=con_cookie(sesion_id))
    roles = cliente.get(RUTA_DE_ROLES, headers=con_cookie(sesion_id))

    exigir_error_de_permiso(despues, ["COMPRAS"])
    assert roles.status_code == 200
    assert roles.json() == ["RESIDENTE"]
    assert ejecutadas == [f"GET {RUTA_COMPRAS}"]


# --------------------------------------------------------------------------- TC-62


def test_tkt006_ca12_rol_insuficiente_asentado_como_denegar(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-62 · CA-12 esc. 1 · CA-13 esc. 3 · RN-04 — `RESIDENTE` en la ruta de `DIRECCION_GENERAL`: `403` y un asiento `DENEGAR`.

    La falta de rol la decide `api/` con `ROL_INSUFICIENTE`, no `AUTO_RESOLUCION`. La bitácora tiene
    **una** fila: acción `DENEGAR`, el usuario autenticado, el momento de la petición, el motivo, sin
    `regla_negocio`, `entidad_tipo` `usuario`, `entidad_id` el propio usuario, sin obra y `datos_antes`
    NULL de SQL. El cuerpo de la ruta no se ejecutó.
    """
    denegacion = provocar_denegacion(
        cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario
    )

    exigir_error_de_permiso(denegacion.respuesta, ["DIRECCION_GENERAL"])
    assert denegacion.ejecutadas == []
    filas = asientos(lector())
    assert len(filas) == 1
    fila = filas[0]
    assert fila["accion"] == "DENEGAR"
    assert fila["usuario_id"] == denegacion.usuario_id
    assert fila["ocurrido_en"] == denegacion.ocurrida_en
    assert fila["motivo"] == "ROL_INSUFICIENTE"
    assert fila["regla_negocio"] is None
    assert fila["entidad_tipo"] == "usuario"
    assert fila["entidad_id"] == denegacion.usuario_id
    assert fila["obra_id"] is None
    assert fila["datos_antes_es_nulo"] is True


def test_tkt006_ca12_los_datos_del_asiento_denegar(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-62 · CA-12 esc. 1 · MT-21 — `datos_despues` tiene exactamente `{metodo, ruta, roles_requeridos}`.

    Sin `correlacion_id`: la correlación no se asienta en la bitácora (API §2.7), va al registro técnico.
    """
    provocar_denegacion(cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario)

    (fila,) = asientos(lector())

    assert isinstance(fila["datos_despues"], dict)
    assert set(fila["datos_despues"]) == CLAVES_DE_DATOS_DE_LA_DENEGACION
    assert fila["datos_despues"] == {
        "metodo": "GET",
        "ruta": RUTA_DIRECCION,
        "roles_requeridos": ["DIRECCION_GENERAL"],
    }


def test_tkt006_ca12_el_asiento_no_lleva_correlacion_ni_la_credencial_de_la_cookie(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-62 · CA-12 esc. 1 · conv-seguridad §2 — ningún campo del asiento trae la correlación ni el id de la sesión.

    El identificador de la sesión es la credencial de la cookie y el rol de lectura lee la bitácora
    (invariante 21): no puede aparecer en ella, ni en `datos_despues` ni en ninguna otra columna.
    """
    denegacion = provocar_denegacion(
        cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario
    )

    (fila,) = asientos(lector())

    texto = json.dumps(fila, default=str, ensure_ascii=False)
    assert denegacion.respuesta.headers[CABECERA] not in texto
    assert str(denegacion.sesion_id) not in texto
    assert "correlacion" not in texto


def test_tkt006_ca12_denegar_solo_inserta_en_la_bitacora(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    sentencias: list[str],
) -> None:
    """TC-62 · CA-R1 · invariante 10 — rechazo: el asiento `DENEGAR` emite un `INSERT` y ningún `UPDATE` ni `DELETE` sobre `bitacora`.

    Para que la ausencia signifique algo, el `INSERT INTO bitacora` sí aparece entre las sentencias.
    """
    agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    sesion_id = iniciar_por_http(cliente)
    reloj_de_prueba.avanzar(timedelta(minutes=5))
    del sentencias[:]

    respuesta = cliente.get(RUTA_DIRECCION, headers=con_cookie(sesion_id))

    assert respuesta.status_code == 403
    emitidas = "\n".join(sentencias)
    assert re.search(r"INSERT\s+INTO\s+bitacora\b", emitidas, re.IGNORECASE)
    assert not re.search(r"UPDATE\s+bitacora\b", emitidas, re.IGNORECASE)
    assert not re.search(r"DELETE\s+FROM\s+bitacora\b", emitidas, re.IGNORECASE)


def test_tkt006_ca12_el_asiento_lleva_el_metodo_y_la_ruta_de_la_peticion(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-62 · CA-12 esc. 1 — `metodo` y `ruta` salen de la petición real, y la `ruta` no arrastra la cadena de consulta.

    Un `POST` a la misma ruta asienta `"POST"` y, un minuto después, un `GET` con `?token=…` asienta solo el camino: nada de
    lo que viaje en la consulta entra a la bitácora.
    """
    agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    sesion_id = iniciar_por_http(cliente)

    por_post = cliente.post(RUTA_DIRECCION, headers=con_cookie(sesion_id))
    reloj_de_prueba.avanzar(timedelta(minutes=1))
    con_consulta = cliente.get(
        f"{RUTA_DIRECCION}?token=secreto-de-consulta", headers=con_cookie(sesion_id)
    )

    exigir_error_de_permiso(por_post, ["DIRECCION_GENERAL"])
    exigir_error_de_permiso(con_consulta, ["DIRECCION_GENERAL"])
    filas = asientos(lector())
    assert [fila["datos_despues"]["metodo"] for fila in filas] == ["POST", "GET"]
    assert [fila["datos_despues"]["ruta"] for fila in filas] == [RUTA_DIRECCION, RUTA_DIRECCION]
    assert "secreto-de-consulta" not in json.dumps(filas, default=str)


def test_tkt006_ca12_cada_denegacion_deja_su_asiento_y_a_nombre_de_quien_se_denego(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-62 · CA-12 esc. 1 — dos denegaciones de Ana y una de Luis son tres asientos, cada uno a nombre del suyo.

    La atribución sale del usuario autenticado de cada petición: `usuario_id` y `entidad_id` coinciden en
    cada fila y no se mezclan entre usuarios.
    """
    agregar_rutas_de_prueba(aplicacion_identidad)
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    luis = sembrar_usuario(
        CORREO_DE_LUIS, CONTRASENA_DE_LUIS, roles=("ALMACEN",), nombre="Luis Mena"
    )
    de_ana = iniciar_por_http(cliente, CORREO_DE_ANA, CONTRASENA_DE_ANA)
    de_luis = iniciar_por_http(cliente, CORREO_DE_LUIS, CONTRASENA_DE_LUIS)

    for sesion_id in (de_ana, de_luis, de_ana):
        reloj_de_prueba.avanzar(timedelta(minutes=1))
        assert cliente.get(RUTA_DIRECCION, headers=con_cookie(sesion_id)).status_code == 403

    filas = asientos(lector())
    assert [(fila["usuario_id"], fila["entidad_id"]) for fila in filas] == [
        (ana, ana),
        (luis, luis),
        (ana, ana),
    ]
    assert all(fila["accion"] == "DENEGAR" for fila in filas)


def test_tkt006_ca12_una_denegacion_llama_una_vez_a_la_bitacora_con_los_argumentos_del_contrato(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-62 · CA-12 esc. 1 · C-1 — `asentar_denegacion` se llama una vez, por la interfaz y con los cuatro argumentos del contrato.

    `usuario_id`, `ocurrido_en` del reloj, `motivo` y `datos`: ni sesión web ni correlación (C-1 enmendado).
    """
    llamadas = espiar_denegaciones(monkeypatch)

    denegacion = provocar_denegacion(
        cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario
    )

    assert denegacion.respuesta.status_code == 403
    assert len(llamadas) == 1
    assert set(llamadas[0]) == {"usuario_id", "ocurrido_en", "motivo", "datos"}
    assert llamadas[0]["usuario_id"] == denegacion.usuario_id
    assert llamadas[0]["ocurrido_en"] == denegacion.ocurrida_en
    assert llamadas[0]["motivo"] == "ROL_INSUFICIENTE"
    assert dict(llamadas[0]["datos"]) == {
        "metodo": "GET",
        "ruta": RUTA_DIRECCION,
        "roles_requeridos": ["DIRECCION_GENERAL"],
    }


# --------------------------------------------------------------------------- TC-63


def test_tkt006_ca12_denegar_en_transaccion_propia(
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    sesion_bd: Session,
    reloj_de_prueba: RelojDePrueba,
    lector: Callable[[], Conexion],
) -> None:
    """TC-63 · CA-12 esc. 2 — rechazo: `registrar_denegacion` persiste aunque la transacción exterior se deshaga.

    Una `Session` exterior abre su transacción e inserta un usuario; dentro de ella se llama a
    `registrar_denegacion`; la exterior hace `rollback`. Desde una conexión nueva: el asiento `DENEGAR`
    está —ya antes del `rollback`, porque se confirmó por su cuenta— y el usuario de la exterior no.
    """
    contexto = aplicacion_identidad.state.identidad
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    de_ana = autenticado_como(ana, reloj_de_prueba)
    correo_exterior = "exterior@cimenta.test"

    sesion_bd.execute(
        text(
            "INSERT INTO usuario (id, nombre, email, password_hash, activo) "
            "VALUES (:id, 'Exterior', :email, 'sin-hash', true)"
        ),
        {"id": uuid.uuid4(), "email": correo_exterior},
    )
    registrar(contexto, de_ana, "corr-0006-63")
    antes_del_rollback = lector()
    asentado_antes = [fila["accion"] for fila in asientos(antes_del_rollback)]
    exterior_visible_antes = existe_usuario(antes_del_rollback, correo_exterior)
    sesion_bd.rollback()

    despues = lector()
    assert asentado_antes == ["DENEGAR"]
    assert exterior_visible_antes is False
    assert [fila["accion"] for fila in asientos(despues)] == ["DENEGAR"]
    assert asientos(despues)[0]["usuario_id"] == ana
    assert existe_usuario(despues, correo_exterior) is False


def test_tkt006_ca12_denegar_persiste_aunque_la_peticion_deshaga_la_suya(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
) -> None:
    """TC-63 · CA-12 esc. 2 — por HTTP: la petición escribe un usuario, el `403` salta y deshace; el asiento sigue.

    La ruta de la suite declara antes de `exigir_rol` una dependencia que abre una transacción, escribe y
    la deshace al terminar. Tras el `403`: el asiento `DENEGAR` persiste y el usuario de la petición no.
    """
    escritas = agregar_ruta_con_transaccion_propia(aplicacion_identidad, motor_aplicacion)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    sesion_id = iniciar_por_http(cliente)

    respuesta = cliente.get(RUTA_CON_TRANSACCION, headers=con_cookie(sesion_id))

    exigir_error_de_permiso(respuesta, ["DIRECCION_GENERAL"])
    assert escritas == [CORREO_DE_LA_PETICION]
    conexion = lector()
    assert [fila["accion"] for fila in asientos(conexion)] == ["DENEGAR"]
    assert existe_usuario(conexion, CORREO_DE_LA_PETICION) is False


# --------------------------------------------------------------------------- TC-64


def test_tkt006_ca12_si_la_bitacora_falla_sigue_en_403(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    registro_tecnico: io.StringIO,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-64 · CA-12 esc. 4 · PA-T6 — rechazo: si `asentar_denegacion` lanza, la respuesta sigue siendo el `403` de TC-62.

    No es `200` ni `500`. El fallo queda en el registro técnico como `denegacion_no_asentada`, con el
    `correlacion_id` de la respuesta, el nivel `error` y el usuario; la bitácora no recibe ninguna fila.
    """
    import cimenta.auditoria.interfaz as auditoria_interfaz

    def falla(sesion_bd: Session, **argumentos: Any) -> uuid.UUID:
        raise RuntimeError("bitácora caída")

    monkeypatch.setattr(auditoria_interfaz, "asentar_denegacion", falla)

    denegacion = provocar_denegacion(
        cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario
    )

    exigir_error_de_permiso(denegacion.respuesta, ["DIRECCION_GENERAL"])
    assert denegacion.ejecutadas == []
    assert contar(lector(), "bitacora") == 0
    no_asentadas = [
        linea
        for linea in lineas_json(registro_tecnico)
        if linea["event"] == "denegacion_no_asentada"
    ]
    assert len(no_asentadas) == 1
    assert no_asentadas[0]["correlacion_id"] == denegacion.respuesta.headers[CABECERA]
    assert no_asentadas[0]["level"] == "error"
    assert no_asentadas[0]["usuario_id"] == str(denegacion.usuario_id)


def test_tkt006_ca12_el_fallo_de_la_bitacora_se_registra_sin_el_texto_de_la_excepcion(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    registro_tecnico: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-64 · CA-12 esc. 4 · conv-seguridad §6 — el registro lleva el tipo de la excepción y no su mensaje.

    El mensaje de una excepción de la base puede traer valores sensibles; el registro técnico del
    proyecto resume la excepción por tipo y marcos (RNF-13). La línea tiene `RuntimeError` y no
    contiene el texto «bitácora caída».
    """
    import cimenta.auditoria.interfaz as auditoria_interfaz

    def falla(sesion_bd: Session, **argumentos: Any) -> uuid.UUID:
        raise RuntimeError("bitácora caída")

    monkeypatch.setattr(auditoria_interfaz, "asentar_denegacion", falla)

    provocar_denegacion(cliente, aplicacion_identidad, reloj_de_prueba, sembrar_usuario)

    (linea,) = [
        linea
        for linea in lineas_json(registro_tecnico)
        if linea["event"] == "denegacion_no_asentada"
    ]
    assert [excepcion["tipo"] for excepcion in linea["excepciones"]][0] == "RuntimeError"
    assert "caída" not in json.dumps(lineas_json(registro_tecnico), ensure_ascii=False)


def test_tkt006_ca12_registrar_denegacion_no_propaga_el_fallo_de_la_bitacora(
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    reloj_de_prueba: RelojDePrueba,
    registro_tecnico: io.StringIO,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-64 · CA-12 esc. 4 · MT-14 — a nivel de aplicación: `registrar_denegacion` no lanza aunque la bitácora lance.

    Sin pasar por HTTP: la función absorbe el fallo, lo registra con la correlación que recibió y no deja
    ninguna fila.
    """
    import cimenta.auditoria.interfaz as auditoria_interfaz

    def falla(sesion_bd: Session, **argumentos: Any) -> uuid.UUID:
        raise RuntimeError("bitácora caída")

    monkeypatch.setattr(auditoria_interfaz, "asentar_denegacion", falla)
    ana = sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    de_ana = autenticado_como(ana, reloj_de_prueba)

    registrar(aplicacion_identidad.state.identidad, de_ana, "corr-0006-64")

    assert contar(lector(), "bitacora") == 0
    (linea,) = [
        linea
        for linea in lineas_json(registro_tecnico)
        if linea["event"] == "denegacion_no_asentada"
    ]
    assert linea["correlacion_id"] == "corr-0006-64"


# --------------------------------------------------------------------------- TC-67


@pytest.mark.parametrize(
    "cookie",
    [None, "inexistente", "mal_formada"],
    ids=["sin_cookie", "uuid_inexistente", "mal_formada"],
)
def test_tkt006_ca12_sin_sesion_en_ruta_con_rol_es_401_sin_bitacora(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
    cookie: str | None,
) -> None:
    """TC-67 · CA-12 esc. 3 — rechazo: sin sesión, la ruta con rol responde `401 SIN_SESION`, nunca `403`, y no asienta nada.

    Sin cookie, con un UUID que no existe y con un valor mal formado. La denegación es anónima: no hay a
    quién atribuirla, así que ni `asentar_denegacion` se llama ni la bitácora recibe filas. El cuerpo de
    la ruta no se ejecuta.
    """
    llamadas = espiar_denegaciones(monkeypatch)
    ejecutadas = agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    cabeceras = (
        {} if cookie is None else con_cookie(uuid.uuid4() if cookie == "inexistente" else "abc")
    )

    respuesta = cliente.get(RUTA_DIRECCION, headers=cabeceras)

    exigir_error_de_sesion(respuesta, "SIN_SESION")
    assert ejecutadas == []
    assert llamadas == []
    assert contar(lector(), "bitacora") == 0


@pytest.mark.parametrize("estado", ["caducada", "revocada"])
def test_tkt006_ca12_sesion_caducada_o_revocada_en_ruta_con_rol_es_401_sin_bitacora(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
    estado: str,
) -> None:
    """TC-67 · CA-12 esc. 3 · M7 — rechazo: el `401` va antes que el `403` también con la sesión caducada o cerrada.

    Ana solo tiene `RESIDENTE`, así que con sesión vigente recibiría `403`; con la sesión caducada por
    inactividad o cerrada recibe el `401` que corresponde, y nada se asienta.
    """
    llamadas = espiar_denegaciones(monkeypatch)
    ejecutadas = agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))
    sesion_id = iniciar_por_http(cliente)
    if estado == "caducada":
        reloj_de_prueba.avanzar(timedelta(minutes=31))
    else:
        assert cliente.post(RUTA_CIERRE, headers=con_cookie(sesion_id)).status_code == 204

    respuesta = cliente.get(RUTA_DIRECCION, headers=con_cookie(sesion_id))

    exigir_error_de_sesion(
        respuesta, "SESION_CADUCADA" if estado == "caducada" else "SESION_REVOCADA"
    )
    assert ejecutadas == []
    assert llamadas == []
    assert contar(lector(), "bitacora") == 0


def test_tkt006_ca12_credenciales_erroneas_y_ruta_con_rol_sin_cookie_no_asientan(
    cliente: TestClient,
    aplicacion_identidad: FastAPI,
    sembrar_usuario: SembrarUsuario,
    lector: Callable[[], Conexion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-67 · CA-12 esc. 3 · RNF-04 — las dos denegaciones anónimas: el intento fallido va a `intento_acceso`, ninguna a la bitácora.

    Un inicio con contraseña errónea y una petición sin cookie a la ruta con rol: `401` las dos,
    `intento_acceso` con la fila del intento y la bitácora vacía.
    """
    llamadas = espiar_denegaciones(monkeypatch)
    agregar_rutas_de_prueba(aplicacion_identidad)
    sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=("RESIDENTE",))

    inicio = cliente.post(
        RUTA_SESION, json={"email": CORREO_DE_ANA, "contrasena": "Clave-Equivocada-9"}
    )
    consulta = cliente.get(RUTA_DIRECCION)

    assert inicio.status_code == 401
    exigir_error_de_sesion(consulta, "SIN_SESION")
    conexion = lector()
    assert contar(conexion, "bitacora") == 0
    assert contar(conexion, "intento_acceso") == 1
    assert llamadas == []
