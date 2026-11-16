"""API de la baja de proveedores, fila F6 de TKT-029b (entrega b): `POST /api/v1/proveedores/{id}/baja` (TC-31 a TC-46).

Cubre `CA-1` a `CA-11`, `CA-13` y `CA-14` de la spec (`HDU-004` esc. 12 y 13; `RN-17`) contra PostgreSQL migrado
con `alembic upgrade head` y el rol de aplicación, por la aplicación real (`crear_aplicacion`) y un `TestClient`
HTTPS. Las órdenes de compra se siembran con `herramientas.soporte_tkt029b_ordenes` (rol de aplicación,
`cantidad_recibida` explícita) con folios `OC-T029B-NNNN`, insertados al revés del orden esperado para que un
orden por inserción o por `id` falle. Los proveedores se siembran con SQL directo, no con `POST`: así un defecto
del alta no puede tapar ni causar el fallo de la baja.

Cada rechazo comprueba el contrato de error completo con `exigir_error` (`tipo`, `codigo`, `mensaje` literal,
`errores` o `detalle`, `acciones`, la correlación de la cabecera y la validez contra el esquema del borrador) y
que no cambió nada en la base (proveedores, asientos de proveedor, órdenes y renglones). Los `403` comprueban
además el `DENEGAR` asentado. Los mensajes de `D-4` se comparan carácter por carácter con el nombre `CoPanel`.

Las ayudas (`base`, `abrir_sesion`, `cliente_espera_corta` y el contrato de error) vienen de
`herramientas.soporte_tkt017_api`; las demás (`_sembrar`, `_foto`, `_exigir_concurrencia`,
`_hacer_fallar_en_el_motor`, `creador`, `padres`, `sesion_compras_espera_corta`) son copias propias de las de
TKT-029a: ningún archivo de prueba importa a otro (nota de ejecución del diseño). `contexto_proveedores`,
`contexto_espera_corta` y `segundo_usuario` no se copian: son de los casos de uso (F5) y aquí todo entra por HTTP.

Esta prueba no importa ningún módulo nuevo de producción: todo entra por HTTP, por `/openapi.json` y por el borrador.

Mutantes que esta fila pone en rojo: la ruta sin `verificar_origen`, con `exigir_rol` antes que él, con otros
roles o `async def` (TC-39, TC-40 y su prueba de apoyo); no traducir `55P03`/`57014` en TC-42 y TC-43; un código
de estado distinto de `200`/`409`/`404` en TC-31 a TC-37 y TC-41; quitar un patrón o un límite del DTO `Motivo`
en TC-38. El mutante `M-9` (lectura sin `FOR UPDATE`) lo mata TC-30, no TC-42.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como
# F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`; aquí se exime en el archivo.
# ruff: noqa: F811

from __future__ import annotations

import inspect
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.identidad.api.dependencias import sesion_vigente, verificar_origen
from cimenta.proveedores.infraestructura import repositorio_proveedor
from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    CONTRASENA_DE_PRUEBA,
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador,
    borrador_comparable,
    cabeceras_de,
    cliente_espera_corta,  # noqa: F401
    construir_aplicacion,
    diferencias_de_forma,
    esquema_de_respuesta_200,
    exigir_denegacion,
    exigir_error,
    forma_de,
    forma_de_componente,
    iniciar_sesion,
    llamadas,
    parametros_de,
    rutas_de,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado
from herramientas.soporte_tkt017_entorno import Base
from herramientas.soporte_tkt029b_ordenes import sembrar_orden_compra

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba, SembrarUsuario

RUTA = "/api/v1/proveedores"
RUTA_BORRADOR = "/proveedores/{proveedor_id}/baja"
RFC = "XAXX010101000"
CREADO_ANTES = datetime(2026, 10, 1, 8, 15, tzinfo=UTC)
CORREO_DEL_CREADOR = "compras@cimenta.test"
CONTRASENA = "Clave-Correcta-1"
ROLES_SIN_GESTION = [
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "ALMACEN",
    "ADMINISTRACION",
]
CLAVES_DE_PROVEEDOR = {
    "id",
    "nombre",
    "rfc",
    "tope_consignacion",
    "dia_corte",
    "dia_pago",
    "estado",
    "creado_en",
}

MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_UN_CAMPO_INVALIDO = "La petición tiene 1 campo inválido."
MENSAJE_PROVEEDOR_NO_EXISTE = "El proveedor no existe."
MENSAJE_YA_DADO_DE_BAJA = "El proveedor ya está dado de baja: su estado es BAJA."
MENSAJE_DESACTIVAR_SOBRE_BAJA = "El proveedor no está activo: su estado es BAJA."
MENSAJE_BLOQUEO_VENCIDO = (
    "Otra operación está modificando este proveedor en este momento. Vuelve a intentarlo."
)
MENSAJE_TIEMPO_VENCIDO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."
MENSAJES_DE_VALIDACION = {
    "OBLIGATORIO": "El campo es obligatorio.",
    "FORMATO": "El valor no tiene el formato esperado.",
    "DEMASIADO_LARGO": "El valor excede la longitud máxima.",
}
# `D-4`: el plural desde `ACTIVO`, el singular, y las dos ramas del mensaje.
MENSAJE_UNA_ORDEN_ACTIVO = (
    "CoPanel tiene 1 orden pendiente de recibir; se puede desactivar para órdenes nuevas "
    "conservando las existentes."
)
MENSAJE_DOS_ORDENES_ACTIVO = (
    "CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes nuevas "
    "conservando las existentes."
)
MENSAJE_UNA_ORDEN_DESACTIVADO = (
    "CoPanel tiene 1 orden pendiente de recibir y ya está desactivado; la baja procede cuando "
    "esas órdenes se reciban completas o se cancelen."
)

COLUMNAS_DE_PROVEEDOR = (
    "SELECT nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, creado_en, creado_por_id "
    "FROM proveedor WHERE id = %s"
)
COLUMNAS_DE_ASIENTO = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, obra_id, regla_negocio, "
    "motivo, datos_antes, datos_despues FROM bitacora "
    "WHERE entidad_tipo = 'proveedor' AND entidad_id = %s ORDER BY accion::text"
)


# --------------------------------------------------------------------------- ayudas de la prueba


@dataclass(frozen=True)
class Padres:
    """Las filas padre de una orden de compra: obra, tipo de partida, insumo y solicitante."""

    obra: uuid.UUID
    tipo_partida: uuid.UUID
    insumo: uuid.UUID
    solicitante: uuid.UUID


@pytest.fixture
def creador(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Usuario de COMPRAS que solicita las requisiciones de las órdenes sembradas."""
    return sembrar_usuario(CORREO_DEL_CREADOR, CONTRASENA, roles=("COMPRAS",))


@pytest.fixture
def padres(datos_presupuesto: DatosPresupuesto, creador: uuid.UUID) -> Padres:
    """La obra, el tipo de partida y el insumo de las órdenes, escritos con el rol de aplicación."""
    return Padres(
        obra=datos_presupuesto.obra(codigo="OB-T029B"),
        tipo_partida=datos_presupuesto.tipo_partida(),
        insumo=datos_presupuesto.insumo_nuevo(),
        solicitante=creador,
    )


@pytest.fixture
def sesion_compras_espera_corta(
    cliente_espera_corta: TestClient, sembrar_usuario: SembrarUsuario
) -> Sesion:
    """Un usuario de COMPRAS con sesión abierta contra la aplicación de `lock_timeout` de 200 ms."""
    correo = f"compras-espera-{uuid.uuid4().hex[:8]}@cimenta.test"
    usuario_id = sembrar_usuario(
        correo, CONTRASENA_DE_PRUEBA, roles=("COMPRAS",), nombre="Compras con espera"
    )
    return Sesion(usuario_id, iniciar_sesion(cliente_espera_corta, correo, CONTRASENA_DE_PRUEBA))


def _mutar(
    cliente: TestClient,
    metodo: str,
    ruta: str,
    sesion: Sesion | None,
    cuerpo: object,
    *,
    cookie_csrf: str | None = TOKEN_CSRF,
    cabecera_csrf: str | None = TOKEN_CSRF,
) -> Any:
    """Una mutación con la cookie de sesión y el par CSRF indicado (por omisión, uno válido)."""
    return cliente.request(
        metodo,
        ruta,
        json=cuerpo,
        headers=cabeceras_de(
            None if sesion is None else sesion.sesion_id, cookie_csrf, cabecera_csrf
        ),
    )


def _baja(
    cliente: TestClient, sesion: Sesion | None, proveedor_id: object, cuerpo: object, **par: Any
) -> Any:
    return _mutar(cliente, "POST", f"{RUTA}/{proveedor_id}/baja", sesion, cuerpo, **par)


def _desactivar(
    cliente: TestClient, sesion: Sesion | None, proveedor_id: object, cuerpo: object, **par: Any
) -> Any:
    return _mutar(cliente, "POST", f"{RUTA}/{proveedor_id}/desactivacion", sesion, cuerpo, **par)


def _alta(cliente: TestClient, sesion: Sesion | None, cuerpo: dict[str, Any]) -> Any:
    return _mutar(cliente, "POST", RUTA, sesion, cuerpo)


def _leer(
    cliente: TestClient,
    sesion: Sesion | None,
    ruta: str = RUTA,
    consulta: list[tuple[str, str]] | None = None,
) -> Any:
    """`GET` con la cookie de sesión y la consulta pedida, que admite parámetros repetidos."""
    return cliente.get(
        ruta,
        params=None if consulta is None else [(clave, valor) for clave, valor in consulta],
        headers=cabeceras_de(None if sesion is None else sesion.sesion_id),
    )


def _cuenta(base: Base, consulta: LiteralString, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _sembrar(
    base: Base,
    creador_id: uuid.UUID,
    *,
    nombre: str = "CoPanel",
    rfc: str = RFC,
    estado: str = "ACTIVO",
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
) -> uuid.UUID:
    """Inserta una fila en `proveedor` con SQL directo, sin pasar por el API."""
    identificador = uuid.uuid4()
    base.ejecutar(
        "INSERT INTO proveedor (id, nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, "
        "creado_en, creado_por_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        identificador,
        nombre,
        rfc,
        estado,
        None if tope is None else Decimal(tope),
        dia_corte,
        dia_pago,
        CREADO_ANTES,
        creador_id,
    )
    return identificador


def _orden(
    base: Base,
    padres: Padres,
    *,
    proveedor: uuid.UUID,
    folio: str,
    renglones: list[tuple[str, str]],
    excedente: str = "0",
    cancelada: bool = False,
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
        excedente=excedente,
        cancelada=cancelada,
    )


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: proveedores, asientos de proveedor, órdenes y renglones."""
    return {
        "proveedores": base.filas("SELECT * FROM proveedor ORDER BY id"),
        "asientos": base.filas(
            "SELECT id FROM bitacora WHERE entidad_tipo = 'proveedor' ORDER BY id"
        ),
        "ordenes": base.filas("SELECT * FROM orden_compra ORDER BY id"),
        "renglones": base.filas("SELECT * FROM orden_compra_renglon ORDER BY id"),
    }


def _ordenes_y_renglones(base: Base) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """Las filas de `orden_compra` y `orden_compra_renglon`, que la baja nunca debe tocar."""
    return (
        base.filas("SELECT * FROM orden_compra ORDER BY id"),
        base.filas("SELECT * FROM orden_compra_renglon ORDER BY id"),
    )


def _asientos_de_baja(base: Base) -> int:
    return _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DAR_BAJA'")


def _estado_de(base: Base, proveedor_id: uuid.UUID) -> str:
    fila = base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id)
    assert len(fila) == 1
    return str(fila[0][0])


def _error_de_validacion(
    respuesta: Any, campo: str, codigo: str, mensaje: str | None = None
) -> dict[str, Any]:
    return exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": MENSAJE_UN_CAMPO_INVALIDO,
            "errores": [
                {
                    "campo": campo,
                    "codigo": codigo,
                    "mensaje": mensaje if mensaje is not None else MENSAJES_DE_VALIDACION[codigo],
                }
            ],
        },
        esquema="ErrorValidacion",
    )


def _esperado(
    proveedor_id: uuid.UUID | str,
    *,
    estado: str,
    nombre: str = "CoPanel",
    rfc: str = RFC,
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
) -> dict[str, Any]:
    """El `Proveedor` del borrador sin `creado_en`, como lo devuelve el API."""
    return {
        "id": str(proveedor_id),
        "nombre": nombre,
        "rfc": rfc,
        "tope_consignacion": tope,
        "dia_corte": dia_corte,
        "dia_pago": dia_pago,
        "estado": estado,
    }


def _sin_fecha(proveedor: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in proveedor.items() if k != "creado_en"}


def _sin_sesion() -> dict[str, Any]:
    return {"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION}


def _accion_desactivar(proveedor_id: uuid.UUID) -> dict[str, str]:
    return {
        "clave": "DESACTIVAR_PROVEEDOR",
        "metodo": "POST",
        "ruta": f"{RUTA}/{proveedor_id}/desactivacion",
    }


def _exigir_ordenes_pendientes(
    respuesta: Any,
    proveedor_id: uuid.UUID,
    *,
    mensaje: str,
    ordenes: list[tuple[uuid.UUID, str, str]],
    con_accion: bool,
) -> None:
    """El `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` completo (`D-4`): nunca `REGLA_NEGOCIO`."""
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "PROVEEDOR_CON_ORDENES_ABIERTAS",
            "mensaje": mensaje,
            "detalle": {
                "ordenes": [
                    {"id": str(orden_id), "folio": folio, "estado": estado}
                    for orden_id, folio, estado in ordenes
                ]
            },
            "acciones": [_accion_desactivar(proveedor_id)] if con_accion else [],
        },
        esquema="ErrorConflicto",
    )
    validar_contra("ErrorConflictoEstado", cuerpo)
    assert "regla" not in cuerpo
    assert "retry-after" not in respuesta.headers


def _exigir_estado_terminal(respuesta: Any, *, mensaje: str) -> None:
    """El `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con `estado_actual` `BAJA` y sin acciones."""
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "ESTADO_NO_PERMITE_OPERACION",
            "mensaje": mensaje,
            "detalle": {"estado_actual": "BAJA"},
            "acciones": [],
        },
        esquema="ErrorConflicto",
    )
    validar_contra("ErrorConflictoEstado", cuerpo)
    assert "regla" not in cuerpo


# --------------------------------------------------------------------------- TC-31 · CA-1


def test_hdu004_esc13_api_baja_desde_activo_responde_200_en_baja(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-004 esc. 13 · TC-31 · CA-1 — `200` con el `Proveedor` en `BAJA`; sale del listado por omisión y sigue con `estado=BAJA` y en `GET /{id}`.

    Todos los datos se conservan: nombre, RFC, tope, días y `creado_en`. El `DAR_BAJA` lleva el motivo (sin
    los espacios de los extremos), el estado de antes (`ACTIVO`) y el de después (`BAJA`), con `regla_negocio` y
    `obra_id` nulos, escrito en la misma transacción. Otro proveedor no cambia y hay un solo asiento.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id, tope="300000.0000", dia_corte=2, dia_pago=5)
    vecino = _sembrar(base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2")
    vecino_antes = base.filas(COLUMNAS_DE_PROVEEDOR, vecino)

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "  Cerró su negocio  "})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Proveedor", cuerpo)
    assert set(cuerpo) == CLAVES_DE_PROVEEDOR
    assert _sin_fecha(cuerpo) == _esperado(
        proveedor_id, estado="BAJA", tope="300000.0000", dia_corte=2, dia_pago=5
    )
    assert datetime.fromisoformat(cuerpo["creado_en"]) == CREADO_ANTES
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", RFC, "BAJA", "300000.0000", 2, 5, CREADO_ANTES, usuario.usuario_id)
    ]
    assert base.filas(COLUMNAS_DE_ASIENTO, proveedor_id) == [
        (
            "DAR_BAJA",
            "proveedor",
            proveedor_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            "Cerró su negocio",
            {"estado": "ACTIVO"},
            {"estado": "BAJA"},
        )
    ]
    assert _asientos_de_baja(base) == 1, "Una baja, un solo asiento"
    assert base.filas(COLUMNAS_DE_PROVEEDOR, vecino) == vecino_antes, "Otro proveedor no cambia"

    por_omision = _leer(cliente, usuario)
    assert por_omision.status_code == 200, por_omision.text
    assert [p["id"] for p in por_omision.json()["elementos"]] == [str(vecino)]
    en_baja = _leer(cliente, usuario, consulta=[("estado", "BAJA")])
    assert [p["id"] for p in en_baja.json()["elementos"]] == [str(proveedor_id)]
    uno = _leer(cliente, usuario, f"{RUTA}/{proveedor_id}")
    assert uno.status_code == 200, uno.text
    assert uno.json() == cuerpo


# --------------------------------------------------------------------------- TC-32 · CA-2


def test_hdu004_esc13_api_baja_desde_desactivado_asienta_el_estado_anterior_real(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-004 esc. 13 · TC-32 · CA-2 · M-13 — `DESACTIVADO` sin órdenes pasa a `BAJA` y `datos_antes` guarda `DESACTIVADO`.

    El asiento no puede copiar el literal `ACTIVO` de la desactivación: guarda el estado leído de la fila.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(
        base, usuario.usuario_id, estado="DESACTIVADO", tope="120000.0000", dia_corte=3, dia_pago=7
    )

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Ya no surte tablaroca"})

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Proveedor", respuesta.json())
    assert _sin_fecha(respuesta.json()) == _esperado(
        proveedor_id, estado="BAJA", tope="120000.0000", dia_corte=3, dia_pago=7
    )
    assert base.filas(COLUMNAS_DE_ASIENTO, proveedor_id) == [
        (
            "DAR_BAJA",
            "proveedor",
            proveedor_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            "Ya no surte tablaroca",
            {"estado": "DESACTIVADO"},
            {"estado": "BAJA"},
        )
    ]
    assert _asientos_de_baja(base) == 1


# --------------------------------------------------------------------------- TC-33 · CA-3


def test_hdu004_esc12_api_baja_con_ordenes_pendientes_responde_409_y_ofrece_desactivar(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-33 · CA-3 · M-11 — `ACTIVO` con una `ABIERTA` y una `PARCIAL`: `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` completo.

    `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, el mensaje literal de `D-4` con
    «2 órdenes», `detalle.ordenes` con `id`, `folio` y `estado` **por folio** (la `ABIERTA` `OC-T029B-0002`
    se inserta antes que la `PARCIAL` `OC-T029B-0001`), la acción `DESACTIVAR_PROVEEDOR` con la ruta absoluta
    y el `correlacion_id` de la cabecera; válido contra `ErrorConflicto` del borrador. El proveedor sigue
    `ACTIVO` y la base no cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    abierta = _orden(
        base, padres, proveedor=proveedor_id, folio="OC-T029B-0002", renglones=[("10", "0")]
    )
    parcial = _orden(
        base, padres, proveedor=proveedor_id, folio="OC-T029B-0001", renglones=[("10", "4")]
    )
    antes = _foto(base)

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})

    _exigir_ordenes_pendientes(
        respuesta,
        proveedor_id,
        mensaje=MENSAJE_DOS_ORDENES_ACTIVO,
        ordenes=[(parcial, "OC-T029B-0001", "PARCIAL"), (abierta, "OC-T029B-0002", "ABIERTA")],
        con_accion=True,
    )
    assert _estado_de(base, proveedor_id) == "ACTIVO"
    assert _asientos_de_baja(base) == 0, "Un rechazo no asienta nada"
    assert _foto(base) == antes, "El rechazo no escribe"


# --------------------------------------------------------------------------- TC-34 · CA-4


def test_hdu004_esc12_api_baja_de_desactivado_con_orden_pendiente_responde_409_sin_acciones(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-34 · CA-4 · M-10 — `DESACTIVADO` con una `PARCIAL`: `409` con la orden listada y `acciones` vacía.

    Desactivar de nuevo respondería `409`, así que el rechazo no ofrece `DESACTIVAR_PROVEEDOR`; el mensaje
    explica por qué (`D-4`, singular). La orden `PARCIAL` tiene un renglón completo y otro con saldo; una
    segunda orden `CERRADA` no se lista. Nada cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id, estado="DESACTIVADO")
    _orden(base, padres, proveedor=proveedor_id, folio="OC-T029B-0002", renglones=[("5", "5")])
    parcial = _orden(
        base,
        padres,
        proveedor=proveedor_id,
        folio="OC-T029B-0001",
        renglones=[("10", "10"), ("5", "2")],
    )
    antes = _foto(base)

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})

    _exigir_ordenes_pendientes(
        respuesta,
        proveedor_id,
        mensaje=MENSAJE_UNA_ORDEN_DESACTIVADO,
        ordenes=[(parcial, "OC-T029B-0001", "PARCIAL")],
        con_accion=False,
    )
    assert _estado_de(base, proveedor_id) == "DESACTIVADO"
    assert _foto(base) == antes, "El rechazo no escribe"


# --------------------------------------------------------------------------- TC-35 · CA-5


@pytest.mark.parametrize(
    ("renglones", "excedente", "cancelada", "de_otro_proveedor"),
    [
        pytest.param([("10", "10")], "0", False, False, id="cerrada"),
        pytest.param([("10", "12")], "2", False, False, id="cerrada_con_excedente"),
        pytest.param([("10", "0")], "0", True, False, id="cancelada_sin_recibir_nada"),
        pytest.param([("10", "0")], "0", False, True, id="abierta_de_otro_proveedor"),
    ],
)
def test_hdu004_esc12_api_baja_solo_bloquean_las_ordenes_vivas_con_material_por_recibir_ordenes_que_no_bloquean(
    renglones: list[tuple[str, str]],
    excedente: str,
    cancelada: bool,
    de_otro_proveedor: bool,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-35 · CA-5 · M-3 · M-4 · M-5 · M-7 · M-8 — los cuatro ejemplos de `CA-5` que no bloquean: `200` y `BAJA`.

    `CERRADA`, `CERRADA` con excedente autorizado, `CANCELADA` (aunque no haya recibido nada) y una `ABIERTA`
    de otro proveedor (un `uuid4` que no está en `proveedor`: `orden_compra.proveedor_id` no tiene clave
    foránea) dejan al proveedor en `BAJA`, y ninguna orden cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    _orden(
        base,
        padres,
        proveedor=uuid.uuid4() if de_otro_proveedor else proveedor_id,
        folio="OC-T029B-0001",
        renglones=renglones,
        excedente=excedente,
        cancelada=cancelada,
    )
    ordenes_antes = _ordenes_y_renglones(base)

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Proveedor", respuesta.json())
    assert respuesta.json()["estado"] == "BAJA"
    assert _estado_de(base, proveedor_id) == "BAJA"
    assert _asientos_de_baja(base) == 1
    assert _ordenes_y_renglones(base) == ordenes_antes, "La baja nunca toca las órdenes de compra"


@pytest.mark.parametrize(
    ("renglones", "excedente", "estado_de_la_orden"),
    [
        pytest.param([("10", "0")], "0", "ABIERTA", id="abierta_un_renglon_sin_recibir"),
        pytest.param(
            [("10", "10"), ("5", "2")],
            "0",
            "PARCIAL",
            id="parcial_un_renglon_completo_y_otro_con_saldo",
        ),
    ],
)
def test_hdu004_esc12_api_baja_solo_bloquean_las_ordenes_vivas_con_material_por_recibir_ordenes_que_bloquean(
    renglones: list[tuple[str, str]],
    excedente: str,
    estado_de_la_orden: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-35 · CA-5 · M-3 · M-4 · M-5 · M-7 · M-8 — los dos ejemplos de `CA-5` que bloquean: `409` con su orden listada y su `estado`.

    Una `ABIERTA` de un solo renglón sin nada recibido y una `PARCIAL` con un renglón completo y otro con saldo
    responden `409` con su orden listada y su `estado`. El proveedor sigue `ACTIVO`, no se asienta nada y
    ninguna orden cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    orden_id = _orden(
        base,
        padres,
        proveedor=proveedor_id,
        folio="OC-T029B-0001",
        renglones=renglones,
        excedente=excedente,
        cancelada=False,
    )
    ordenes_antes = _ordenes_y_renglones(base)

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})

    _exigir_ordenes_pendientes(
        respuesta,
        proveedor_id,
        mensaje=MENSAJE_UNA_ORDEN_ACTIVO,
        ordenes=[(orden_id, "OC-T029B-0001", estado_de_la_orden)],
        con_accion=True,
    )
    assert _estado_de(base, proveedor_id) == "ACTIVO"
    assert _asientos_de_baja(base) == 0
    assert _ordenes_y_renglones(base) == ordenes_antes, "La baja nunca toca las órdenes de compra"


# --------------------------------------------------------------------------- TC-36 · CA-6


def test_hdu004_esc12_api_desactivar_con_ordenes_pendientes_procede_y_la_baja_sigue_rechazada(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-36 · CA-6 · M-10 — tras el `409` de la baja, desactivar procede y las órdenes quedan intactas.

    Secuencia: la baja responde `409` con una `PARCIAL` (con `cantidad_recibida` mayor que cero) y la acción
    `DESACTIVAR_PROVEEDOR`; `POST /desactivacion` responde `200` `DESACTIVADO`; el proveedor sale del listado
    por omisión; las filas de `orden_compra` y `orden_compra_renglon` son las mismas antes y después; y una
    nueva baja responde `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` con `acciones` vacía y el mensaje de
    «ya está desactivado».
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    vecino = _sembrar(base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2")
    parcial = _orden(
        base, padres, proveedor=proveedor_id, folio="OC-T029B-0001", renglones=[("10", "4")]
    )
    ordenes_antes = _ordenes_y_renglones(base)

    primera = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})
    _exigir_ordenes_pendientes(
        primera,
        proveedor_id,
        mensaje=MENSAJE_UNA_ORDEN_ACTIVO,
        ordenes=[(parcial, "OC-T029B-0001", "PARCIAL")],
        con_accion=True,
    )

    desactivada = _desactivar(cliente, usuario, proveedor_id, {"motivo": "Dejará de surtir"})
    assert desactivada.status_code == 200, desactivada.text
    assert desactivada.json()["estado"] == "DESACTIVADO"
    por_omision = _leer(cliente, usuario)
    assert [p["id"] for p in por_omision.json()["elementos"]] == [str(vecino)]
    assert _ordenes_y_renglones(base) == ordenes_antes

    segunda = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})
    _exigir_ordenes_pendientes(
        segunda,
        proveedor_id,
        mensaje=MENSAJE_UNA_ORDEN_DESACTIVADO,
        ordenes=[(parcial, "OC-T029B-0001", "PARCIAL")],
        con_accion=False,
    )
    assert _estado_de(base, proveedor_id) == "DESACTIVADO"
    assert _asientos_de_baja(base) == 0
    assert _ordenes_y_renglones(base) == ordenes_antes


# --------------------------------------------------------------------------- TC-37 · CA-7


def test_hdu004_esc12_api_baja_de_un_proveedor_en_baja_es_terminal(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    padres: Padres,
) -> None:
    """HDU-004 esc. 12 · TC-37 · CA-7 · M-2 — `BAJA` es terminal: `409` `ESTADO_NO_PERMITE_OPERACION`, con o sin órdenes pendientes.

    Dos proveedores en `BAJA`, uno sin órdenes y otro con una `ABIERTA`: el estado terminal precede a las
    órdenes pendientes, así que ninguno responde `PROVEEDOR_CON_ORDENES_ABIERTAS`. El cuerpo completo trae el
    mensaje de `D-4`, `detalle` `{"estado_actual": "BAJA"}` y `acciones` vacía. Además, desactivar un
    proveedor en `BAJA` sigue respondiendo su `409` de siempre. Nada se asienta y la base no cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    sin_ordenes = _sembrar(base, usuario.usuario_id, estado="BAJA", tope="1000.0000")
    con_orden = _sembrar(
        base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="BAJA"
    )
    _orden(base, padres, proveedor=con_orden, folio="OC-T029B-0001", renglones=[("10", "0")])
    antes = _foto(base)

    for objetivo in (sin_ordenes, con_orden):
        respuesta = _baja(cliente, usuario, objetivo, {"motivo": "Segundo intento"})

        _exigir_estado_terminal(respuesta, mensaje=MENSAJE_YA_DADO_DE_BAJA)
        assert _foto(base) == antes, f"El rechazo no escribe ({objetivo})"

    sobre_baja = _desactivar(cliente, usuario, sin_ordenes, {"motivo": "Desactivar una baja"})
    _exigir_estado_terminal(sobre_baja, mensaje=MENSAJE_DESACTIVAR_SOBRE_BAJA)
    assert _foto(base) == antes, "La desactivación sobre BAJA tampoco escribe"
    assert _asientos_de_baja(base) == 0


# --------------------------------------------------------------------------- TC-38 · CA-8


CASOS_DE_MOTIVO = [
    pytest.param({}, ("motivo", "OBLIGATORIO"), id="motivo_ausente"),
    pytest.param({"motivo": "   "}, ("motivo", "OBLIGATORIO"), id="motivo_en_blanco"),
    pytest.param({"motivo": "m" * 2001}, ("motivo", "DEMASIADO_LARGO"), id="motivo_de_2001"),
    pytest.param({"motivo": "a\u0000b"}, ("motivo", "FORMATO"), id="nul_en_motivo"),
    pytest.param(
        {"motivo": 123},
        ("motivo", "FORMATO", "El valor no tiene el formato esperado."),
        id="motivo_numero_json",
    ),
    pytest.param(
        [],
        ("cuerpo", "FORMATO", "El valor no tiene el formato esperado."),
        id="cuerpo_que_no_es_objeto",
    ),
]


@pytest.mark.parametrize(("cuerpo", "esperado"), CASOS_DE_MOTIVO)
def test_hdu004_esc12_api_baja_motivo_invalido_responde_422_con_el_campo_de_la_desactivacion(
    cuerpo: object,
    esperado: tuple[str, str] | tuple[str, str, str],
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-38 · CA-8 — el motivo falta, está en blanco, pasa de 2000, lleva `NUL`, no es cadena o el cuerpo no es objeto: `422` `VALIDACION`.

    Los seis casos traen su `campo`, su `codigo` y su mensaje literales. La baja responde lo mismo que la
    desactivación para el mismo cuerpo (`Motivo` es el mismo DTO), salvo la correlación: esa comparación queda
    como refuerzo. El proveedor sigue `ACTIVO` y no se asienta nada. Sin la validación de `Motivo`, un `NUL`
    llegaría a `psycopg` y daría `500`.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    antes = _foto(base)

    respuesta = _baja(cliente, usuario, proveedor_id, cuerpo)

    _error_de_validacion(respuesta, *esperado)
    de_la_desactivacion = _desactivar(cliente, usuario, proveedor_id, cuerpo)
    assert de_la_desactivacion.status_code == 422, de_la_desactivacion.text
    assert {k: v for k, v in respuesta.json().items() if k != "correlacion_id"} == {
        k: v for k, v in de_la_desactivacion.json().items() if k != "correlacion_id"
    }, "La baja y la desactivación señalan el mismo campo"
    assert _foto(base) == antes
    assert _estado_de(base, proveedor_id) == "ACTIVO"
    assert _asientos_de_baja(base) == 0


def test_hdu004_esc12_api_baja_motivo_en_el_limite_y_recortado(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-38 · CA-8 — 2000 caracteres exactos pasan y los espacios de los extremos se recortan antes de asentar.

    `"  Cerró su negocio  "` queda asentado como `"Cerró su negocio"`; un motivo de 2000 caracteres se asienta
    completo. Los dos responden `200`: el borde del tope es 2000 tras recortar.
    """
    usuario = abrir_sesion(("COMPRAS",))
    largo = _sembrar(base, usuario.usuario_id, rfc="ABC010101AA1")
    recortado = _sembrar(base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2")

    en_el_limite = _baja(cliente, usuario, largo, {"motivo": "m" * 2000})
    con_espacios = _baja(cliente, usuario, recortado, {"motivo": "  Cerró su negocio  "})

    assert en_el_limite.status_code == 200, en_el_limite.text
    assert con_espacios.status_code == 200, con_espacios.text
    assert base.filas("SELECT motivo FROM bitacora WHERE entidad_id = %s", largo) == [("m" * 2000,)]
    assert base.filas("SELECT motivo FROM bitacora WHERE entidad_id = %s", recortado) == [
        ("Cerró su negocio",)
    ]


# --------------------------------------------------------------------------- TC-39 · CA-9


@pytest.mark.parametrize("rol", ROLES_SIN_GESTION)
def test_tkt029b_api_baja_sin_permiso(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-39 · CA-9 esc. 1 — `403` `PERMISO` `ROL_INSUFICIENTE` con `COMPRAS` como único rol exigido, sin cifras del recurso y con su `DENEGAR`.

    Los cinco roles que no gestionan el catálogo intentan la baja con un cuerpo válido. El cuerpo no trae
    `detalle` ni el nombre ni el RFC ni el tope del proveedor; el intento queda asentado como `DENEGAR` a
    nombre de quien llamó, con método, ruta concreta y roles exigidos. El proveedor queda como estaba.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id, tope="300000.0000")
    usuario = abrir_sesion((rol,))
    antes = _foto(base)
    ruta = f"{RUTA}/{proveedor_id}/baja"

    respuesta = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})

    cuerpo_de_error = exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ["COMPRAS"],
        },
        esquema="ErrorPermiso",
    )
    assert "detalle" not in cuerpo_de_error
    for cifra in ("CoPanel", RFC, "300000"):
        assert cifra not in respuesta.text, cifra
    assert _foto(base) == antes
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ROL_INSUFICIENTE",
        ruta=ruta,
        roles_requeridos=["COMPRAS"],
    )


# --------------------------------------------------------------------------- TC-40 · CA-9


@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt029b_api_baja_sin_sesion_y_sin_csrf(
    cookie: str | None,
    cabecera: str | None,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-40 · CA-9 esc. 2 · CA-R4 · RNF-05 — sin sesión `401` `SESION`; con sesión de COMPRAS y sin el doble envío, `403` `ORIGEN_NO_VERIFICADO` con su `DENEGAR`.

    Las cuatro combinaciones de `CA-9` de TKT-057 (`SIN_PAR_VALIDO`). Sin sesión responde `401` aunque el par
    sea válido, y una denegación anónima no se asienta. Con sesión y sin par, la petición no se ejecuta aunque
    quien llama pueda gestionar proveedores. En todos los casos el proveedor queda como estaba.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id)
    antes = _foto(base)
    ruta = f"{RUTA}/{proveedor_id}/baja"
    cuerpo = {"motivo": "Cerró su negocio"}

    anonima = _baja(cliente, None, proveedor_id, cuerpo)
    exigir_error(anonima, estado=401, esperado=_sin_sesion(), esquema="ErrorSesion")
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0

    respuesta = _baja(
        cliente, dueno, proveedor_id, cuerpo, cookie_csrf=cookie, cabecera_csrf=cabecera
    )

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ORIGEN_NO_VERIFICADO",
            "mensaje": MENSAJE_ORIGEN_NO_VERIFICADO,
            "roles_requeridos": [],
        },
        esquema="ErrorPermiso",
    )
    assert _foto(base) == antes
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=dueno.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=ruta,
        roles_requeridos=[],
    )


def test_tkt029b_api_baja_el_origen_se_verifica_antes_que_el_rol(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-9 · CA-R4 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    `verificar_origen` va antes que `exigir_rol` en la baja; un solo
    `DENEGAR` con motivo `ORIGEN_NO_VERIFICADO`. Con el orden invertido el motivo sería `ROL_INSUFICIENTE`.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id)
    usuario = abrir_sesion(("DIRECTOR_PROYECTOS",))

    respuesta = _baja(
        cliente,
        usuario,
        proveedor_id,
        {"motivo": "Cerró su negocio"},
        cookie_csrf=None,
        cabecera_csrf=None,
    )

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ORIGEN_NO_VERIFICADO",
            "mensaje": MENSAJE_ORIGEN_NO_VERIFICADO,
            "roles_requeridos": [],
        },
        esquema="ErrorPermiso",
    )
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=f"{RUTA}/{proveedor_id}/baja",
        roles_requeridos=[],
    )


def test_tkt029b_api_la_ruta_de_baja_es_def_con_sesion_y_origen_primero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-9 · CA-R4 · regla 11 · RNF-05 — `POST /proveedores/{id}/baja` existe una sola vez, es `def`, exige sesión y rol y verifica el origen antes que el rol.

    Los recorridos de `test_tkt006_enrutador.py` y
    `test_tkt057_csrf.py` ven las rutas de la aplicación completa. Mutantes: ruta sin `verificar_origen`,
    `async def` o `exigir_rol` antes que `verificar_origen`.
    """
    aplicacion = construir_aplicacion(monkeypatch)
    camino = f"{RUTA}/{{proveedor_id}}/baja"
    halladas = [
        r for r in rutas_de(aplicacion.routes) if r.path == camino and "POST" in (r.methods or ())
    ]
    assert len(halladas) == 1, f"Debe haber exactamente un POST {camino}; hay {len(halladas)}"
    ruta = halladas[0]

    assert inspect.isfunction(ruta.endpoint)
    assert not inspect.iscoroutinefunction(ruta.endpoint)
    assert sesion_vigente in list(llamadas(ruta.dependant))
    declaradas = [sub.call for sub in ruta.dependant.dependencies]
    roles = [
        posicion
        for posicion, llamada in enumerate(declaradas)
        if getattr(llamada, "__name__", "") == "comprobar_rol"
    ]
    assert len(roles) == 1, f"{ruta.path} debe declarar exactamente un exigir_rol"
    assert verificar_origen in declaradas, f"{ruta.path} debe declarar verificar_origen"
    assert declaradas.index(verificar_origen) < roles[0]


# --------------------------------------------------------------------------- TC-41 · CA-10


def test_tkt029b_api_baja_de_un_proveedor_inexistente_o_con_identificador_mal_formado(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-41 · CA-10 — un UUID que no existe: `404` `NO_ENCONTRADO` `proveedor` sin asiento; uno que no es UUID: `422` `VALIDACION` en `proveedor_id`.

    Hay un proveedor real, para que el `404` sea por el id y no por tabla vacía. El `404` es el de
    `proveedor` (no el de ruta inexistente, que es lo que responde un enrutador sin la ruta). Ninguno cambia
    la base.
    """
    usuario = abrir_sesion(("COMPRAS",))
    _sembrar(base, usuario.usuario_id)
    antes = _foto(base)

    inexistente = _baja(cliente, usuario, uuid.uuid4(), {"motivo": "No existe"})
    exigir_error(
        inexistente,
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
            "recurso": "proveedor",
        },
        esquema="ErrorNoEncontrado",
    )
    assert _foto(base) == antes
    assert _asientos_de_baja(base) == 0

    mal_formado = _baja(cliente, usuario, "no-es-uuid", {"motivo": "No existe"})
    _error_de_validacion(mal_formado, "proveedor_id", "FORMATO")
    assert _foto(base) == antes


# --------------------------------------------------------------------------- TC-42 · CA-11


def _exigir_concurrencia(
    respuesta: Any,
    proveedor_id: uuid.UUID,
    *,
    codigo: str,
    mensaje: str,
    espera_maxima_ms: int,
) -> None:
    """El `409` `CONCURRENCIA` completo del borrador: sin `regla`, con `Retry-After: 1` y `REINTENTAR` sobre la baja."""
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONCURRENCIA",
            "codigo": codigo,
            "mensaje": mensaje,
            "detalle": {"espera_maxima_ms": espera_maxima_ms},
            "acciones": [
                {"clave": "REINTENTAR", "metodo": "POST", "ruta": f"{RUTA}/{proveedor_id}/baja"}
            ],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo


def _leer_que_falla(sentencias: list[str], sqlstates: list[str]) -> Callable[..., Any]:
    """Un sustituto de `repositorio_proveedor.leer_proveedor` cuyas sentencias fallan **en el motor**.

    Solo sustituye la lectura bloqueante (`para_cambio=True`) de la baja; ejecuta cada sentencia en la sesión
    del caso de uso, anota el `SQLSTATE` real que responde el motor y relanza el error tal cual. Cualquier
    otra lectura (la que relee el proveedor tras el cambio) pasa al original.
    """
    original = repositorio_proveedor.leer_proveedor

    def leer(sesion_bd: Session, proveedor_id: uuid.UUID, *, para_cambio: bool = False) -> Any:
        if not para_cambio:
            return original(sesion_bd, proveedor_id)
        try:
            for sentencia in sentencias:
                sesion_bd.execute(text(sentencia))
        except DBAPIError as error:
            sqlstates.append(str(getattr(error.orig, "sqlstate", None)))
            raise
        raise AssertionError("La sentencia sustituta debía fallar en el motor")

    return leer


def _hacer_fallar_en_el_motor(
    monkeypatch: pytest.MonkeyPatch, sentencias: list[str], sqlstates: list[str]
) -> None:
    """Sustituye la lectura `FOR UPDATE` de la baja por `sentencias`, que fallan en el motor."""
    monkeypatch.setattr(
        repositorio_proveedor, "leer_proveedor", _leer_que_falla(sentencias, sqlstates)
    )


def test_tkt029b_api_baja_con_bloqueo_vencido(
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    cliente_espera_corta: TestClient,
    sesion_compras_espera_corta: Sesion,
) -> None:
    """TC-42 · CA-11 esc. 2 · RNF-16 — otra sesión retiene la fila: la baja responde `409` `CONCURRENCIA` `BLOQUEO_VENCIDO`.

    La aplicación corre sobre el rol de aplicación con `lock_timeout` de 200 ms y otra sesión tiene la fila de
    `proveedor` con `FOR UPDATE`. El contrato es completo: `Retry-After: 1`, `espera_maxima_ms` 5000 (el
    `lock_timeout` del rol, no los 200 ms de la prueba), el mensaje literal, la acción `REINTENTAR` `POST` a
    la ruta de la baja de ESE proveedor y sin `regla`. No escribe nada: el proveedor sigue `ACTIVO` y no hay
    `DAR_BAJA`. Esta prueba no distingue el mutante `M-9` (lectura sin `FOR UPDATE`): el `UPDATE` posterior
    también espera y vence el mismo `lock_timeout`, con la misma respuesta. Ese mutante lo mata TC-30, en el caso de uso.
    """
    proveedor_id = _sembrar(base, sesion_compras_espera_corta.usuario_id)
    antes = _foto(base)

    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute("SELECT id FROM proveedor WHERE id = %s FOR UPDATE", (proveedor_id,))
        respuesta = _baja(
            cliente_espera_corta,
            sesion_compras_espera_corta,
            proveedor_id,
            {"motivo": "Cerró su negocio"},
        )
    finally:
        retenedor.rollback()

    _exigir_concurrencia(
        respuesta,
        proveedor_id,
        codigo="BLOQUEO_VENCIDO",
        mensaje=MENSAJE_BLOQUEO_VENCIDO,
        espera_maxima_ms=5000,
    )
    assert _foto(base) == antes, "Un bloqueo vencido no cambia el proveedor ni asienta nada"
    assert _estado_de(base, proveedor_id) == "ACTIVO"
    assert _asientos_de_baja(base) == 0


# --------------------------------------------------------------------------- TC-43 · CA-11 · RNF-16


def test_tkt029b_api_baja_tiempo_de_ejecucion_vencido_es_concurrencia(
    base: Base,
    cliente_espera_corta: TestClient,
    sesion_compras_espera_corta: Sesion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-43 · CA-11 esc. 2 · RNF-16 — una sentencia agota `statement_timeout` (`57014`): `409` `CONCURRENCIA` `TIEMPO_EJECUCION_VENCIDO`.

    La lectura `FOR UPDATE` de la baja se sustituye por una sentencia que vence un `statement_timeout` de
    10 ms: el motor responde `57014` de verdad (la prueba lo comprueba). El contrato es completo: `Retry-After:
    1`, `espera_maxima_ms` 15000 (el `statement_timeout` del rol), el mensaje del diseño, la acción `REINTENTAR`
    de la propia baja y sin `regla`. No escribe nada. Mutantes: traducir el `57014` como `BLOQUEO_VENCIDO`, o
    cambiar 15000 por 5000.
    """
    proveedor_id = _sembrar(base, sesion_compras_espera_corta.usuario_id)
    antes = _foto(base)
    sqlstates: list[str] = []
    _hacer_fallar_en_el_motor(
        monkeypatch, ["SET LOCAL statement_timeout = '10ms'", "SELECT pg_sleep(1)"], sqlstates
    )

    respuesta = _baja(
        cliente_espera_corta,
        sesion_compras_espera_corta,
        proveedor_id,
        {"motivo": "Cerró su negocio"},
    )

    assert sqlstates == ["57014"], "La sentencia debe vencer el tiempo en el motor, no simularse"
    _exigir_concurrencia(
        respuesta,
        proveedor_id,
        codigo="TIEMPO_EJECUCION_VENCIDO",
        mensaje=MENSAJE_TIEMPO_VENCIDO,
        espera_maxima_ms=15000,
    )
    assert _foto(base) == antes, "Un tiempo vencido no cambia el proveedor ni asienta nada"


def test_tkt029b_api_baja_error_de_base_ajeno_al_tiempo_es_un_500_sin_traducir(
    base: Base,
    cliente_espera_corta: TestClient,
    sesion_compras_espera_corta: Sesion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-43 · CA-11 · RNF-16 — un error de la base que no es `55P03` ni `57014` no se traduce: `500` del contrato.

    La sentencia sustituta falla con una división entre cero real (`22012`). El caso de uso no la convierte en
    `CONCURRENCIA` ni en ningún `409`: la relanza y la respuesta es el `500` genérico, solo `mensaje` y
    `correlacion_id` (el de la cabecera), sin `Retry-After`, sin el nombre de la excepción, el `SQLSTATE` ni el
    texto del motor. No escribe nada.
    """
    proveedor_id = _sembrar(base, sesion_compras_espera_corta.usuario_id)
    antes = _foto(base)
    sqlstates: list[str] = []
    _hacer_fallar_en_el_motor(monkeypatch, ["SELECT 1 / 0"], sqlstates)

    respuesta = _baja(
        cliente_espera_corta,
        sesion_compras_espera_corta,
        proveedor_id,
        {"motivo": "Cerró su negocio"},
    )

    assert sqlstates == ["22012"], "El motor debe responder con un SQLSTATE que no es de tiempo"
    assert respuesta.status_code == 500, respuesta.text
    assert "retry-after" not in respuesta.headers
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "correlacion_id"}
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    for pista in (
        "CONCURRENCIA",
        "DataError",
        "DBAPIError",
        "DivisionByZero",
        "division by zero",
        "22012",
        "Traceback",
        "psycopg",
        "sqlalchemy",
        "cimenta.",
    ):
        assert pista not in respuesta.text
    assert _foto(base) == antes, "Un error ajeno al tiempo no cambia el proveedor ni asienta nada"


# --------------------------------------------------------------------------- TC-44 · CA-13


def test_hdu004_esc12_api_baja_nunca_borra_y_el_rfc_de_una_baja_sigue_ocupado(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-44 · CA-13 — el rol de aplicación no puede `DELETE` en `proveedor`; tras la baja, el RFC sigue ocupado.

    Dado un proveedor dado de baja por la propia API (no sembrado en `BAJA`), `POST /proveedores` con su RFC
    responde `409` `CONFLICTO` `RFC_DUPLICADO` con el proveedor existente en el detalle, y la fila sigue en
    `proveedor` con su RFC. La baja es lógica: nunca hay borrado físico.
    """
    assert (
        _cuenta(
            base, "SELECT has_table_privilege('cimenta_aplicacion', 'proveedor', 'DELETE')::int"
        )
        == 0
    ), "El rol de aplicación no puede borrar proveedores"
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id)
    dada_de_baja = _baja(cliente, usuario, proveedor_id, {"motivo": "Cerró su negocio"})
    assert dada_de_baja.status_code == 200, dada_de_baja.text
    antes = _foto(base)

    respuesta = _alta(cliente, usuario, {"nombre": "Otro nombre", "rfc": RFC})

    exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "RFC_DUPLICADO",
            "mensaje": f"Ya existe un proveedor con el RFC {RFC}.",
            "detalle": {
                "proveedor_existente_id": str(proveedor_id),
                "proveedor_existente": f"CoPanel · {RFC}",
            },
            "acciones": [],
        },
        esquema="ErrorConflictoEstado",
    )
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM proveedor WHERE rfc = %s", RFC) == 1
    assert _estado_de(base, proveedor_id) == "BAJA"


# --------------------------------------------------------------------------- TC-45 · CA-14


def _operacion_del_borrador() -> dict[str, Any]:
    operacion = borrador()["paths"][RUTA_BORRADOR]["post"]
    assert operacion["operationId"] == "dar_baja_proveedor"
    return dict(operacion)


def test_tkt029b_borrador_declara_la_baja_con_su_ticket_sus_respuestas_y_su_409_completo() -> None:
    """TC-45 · CA-14 · D-11 — `dar_baja_proveedor` declara `x-tickets` `TKT-029b`, sus seis respuestas, el `409` con sus cabeceras y un ejemplo válido.

    `x-reglas` vacío (los rechazos son `CONFLICTO`, no `RN-xx`), `x-roles` `COMPRAS`, `x-escenarios` los dos de
    la historia (`D-6`). El `409` en línea trae `Retry-After` y `X-Correlacion-Id` (las mismas del `$ref`
    `Conflicto`), su ejemplo valida contra `ErrorConflicto` y lista las dos órdenes que su mensaje cuenta
    (`OC-AP05825-0017` `PARCIAL` y `OC-AP05825-0021` `ABIERTA`). La descripción dice que la baja procede
    desde `ACTIVO` y `DESACTIVADO`, que desde `BAJA` responde `ESTADO_NO_PERMITE_OPERACION`, que
    `DESACTIVAR_PROVEEDOR` se ofrece solo desde `ACTIVO` y que el vencimiento de un bloqueo es `CONCURRENCIA`
    con `Retry-After`. `AccionBitacora` termina en `DAR_BAJA`.
    """
    operacion = _operacion_del_borrador()

    assert operacion["x-tickets"] == ["TKT-029b"]
    assert operacion["x-reglas"] == []
    assert operacion["x-roles"] == ["COMPRAS"]
    assert operacion["x-escenarios"] == ["HDU-004 esc. 12", "HDU-004 esc. 13"]
    assert set(operacion["responses"]) == {"200", "401", "403", "404", "409", "422"}
    assert operacion["security"] == [{"sesion": [], "csrf": []}]

    conflicto = operacion["responses"]["409"]
    assert set(conflicto["headers"]) == {"X-Correlacion-Id", "Retry-After"}
    ejemplo = conflicto["content"]["application/json"]["example"]
    validar_contra("ErrorConflicto", ejemplo)
    assert ejemplo["codigo"] == "PROVEEDOR_CON_ORDENES_ABIERTAS"
    assert [(o["folio"], o["estado"]) for o in ejemplo["detalle"]["ordenes"]] == [
        ("OC-AP05825-0017", "PARCIAL"),
        ("OC-AP05825-0021", "ABIERTA"),
    ]
    assert "2 órdenes" in ejemplo["mensaje"], "El ejemplo lista las órdenes que su mensaje cuenta"

    descripcion = " ".join(str(operacion["description"]).split())
    for texto in (
        "ACTIVO",
        "DESACTIVADO",
        "BAJA",
        "ESTADO_NO_PERMITE_OPERACION",
        "DESACTIVAR_PROVEEDOR",
        "CONCURRENCIA",
        "Retry-After",
    ):
        assert texto in descripcion, f"La descripción de la baja no menciona {texto}"
    verbos = borrador()["components"]["schemas"]["AccionBitacora"]["enum"]
    assert verbos[-1] == "DAR_BAJA"


def test_tkt029b_borrador_la_desactivacion_ya_no_se_admite_siempre() -> None:
    """TC-45 · CA-14 · D-11 — la descripción de `desactivar_proveedor` deja de decir «Se admite siempre».

    Dice que se admite tenga o no órdenes pendientes, siempre que el proveedor esté `ACTIVO`: sobre `BAJA` o
    `DESACTIVADO` responde `409`, y «siempre» contradecía ese `409`.
    """
    operacion = borrador()["paths"]["/proveedores/{proveedor_id}/desactivacion"]["post"]
    assert operacion["operationId"] == "desactivar_proveedor"

    descripcion = " ".join(str(operacion["description"]).split())

    assert "Se admite siempre" not in descripcion
    assert "ACTIVO" in descripcion
    assert "órdenes pendientes" in descripcion


# --------------------------------------------------------------------------- TC-46 · CA-14


def test_tkt029b_api_baja_publicada_igual_al_borrador(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-46 · CA-14 — `dar_baja_proveedor` está en `/openapi.json` bajo su ruta, exige `sesion` y `csrf`, recibe `Motivo` y responde `Proveedor` con la forma del borrador.

    Se compara contra `borrador_comparable()`: el `operationId` publicado, el `proveedor_id` de la ruta
    (`parametros_de`), el cuerpo `Motivo`, la respuesta `200` con `diferencias_de_forma == []` y la forma de
    los dos componentes que usa.
    """
    contrato = contrato_publicado(monkeypatch)
    ruta = f"{RUTA}/{{proveedor_id}}/baja"
    assert ruta in contrato["paths"], "El contrato publicado no trae la ruta de la baja"
    publicada = contrato["paths"][ruta]["post"]
    comparable = borrador_comparable()

    assert publicada["operationId"] == "dar_baja_proveedor"
    exigidos = {nombre for requisito in publicada.get("security", []) for nombre in requisito}
    assert {"sesion", "csrf"} <= exigidos
    assert publicada["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Motivo"
    }
    assert publicada["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Proveedor"
    }
    assert parametros_de(contrato, ruta, "post") == parametros_de(comparable, RUTA_BORRADOR, "post")

    del_borrador, _ = forma_de(
        comparable, esquema_de_respuesta_200(comparable, RUTA_BORRADOR, "post"), "200"
    )
    de_lo_publicado, _ = forma_de(contrato, esquema_de_respuesta_200(contrato, ruta, "post"), "200")
    assert del_borrador["200.type"], "Anti-verde vacío: el borrador declara el tipo de la respuesta"
    assert diferencias_de_forma(del_borrador, de_lo_publicado) == []
    for esquema in ("Proveedor", "Motivo"):
        forma_borrador, _ = forma_de_componente(comparable, esquema)
        forma_publicada, _ = forma_de_componente(contrato, esquema)
        assert diferencias_de_forma(forma_borrador, forma_publicada) == [], esquema
