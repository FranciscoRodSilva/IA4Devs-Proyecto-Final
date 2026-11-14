"""API del catálogo de proveedores, fila B1 de TKT-029a: las cinco operaciones y su contrato (TC-21 a TC-40 y TC-42).

Cubre `CA-1` a `CA-10` y `CA-R2` de la spec (`HDU-004` esc. 2, 3 y 12; `RN-17`) contra PostgreSQL migrado con
`alembic upgrade head` y el rol de aplicación, por la aplicación real (`crear_aplicacion`) y un `TestClient`
HTTPS. Las ayudas son solo las de `herramientas.soporte_tkt017_api`, con `borrador_comparable()` porque
`ProveedorNuevo.dia_corte` y `dia_pago` usan `allOf: [$ref DiaSemana]`, que `aplanar` no resuelve.

Operaciones del borrador que cubre: `crear_proveedor`, `listar_proveedores`, `obtener_proveedor`,
`actualizar_proveedor` y `desactivar_proveedor`. `dar_baja_proveedor` es de TKT-029b y **no** se publica
(`TC-40` lo exige). El catálogo es global, sin obra: no hay caso de «otra obra» (IDOR) en esta fila. La
concurrencia (`CA-3`, bloqueo de la desactivación) se prueba en los casos de uso (`TC-15`, `TC-20`).

Cada rechazo comprueba el contrato de error completo con `exigir_error` (`tipo`, `codigo`, `mensaje` literal,
`errores` o `detalle`, `acciones`, la correlación de la cabecera y la validez contra el esquema del
borrador) y que no cambió nada en la base. Los `403` comprueban además el `DENEGAR` asentado. El dinero
viaja como cadena JSON (`"300000.0000"`), nunca como número.

Los proveedores previos se siembran con SQL directo y no con `POST`: así un defecto del alta no puede tapar
ni causar el fallo de las demás pruebas.

Rojo de la fila B1: las rutas `/api/v1/proveedores` no existen todavía, así que cada petición responde
`404` (`NO_ENCONTRADO` con la ruta como recurso) donde la prueba espera `200`, `201`, `401`, `403`, `404
proveedor`, `409` o `422`, y el contrato publicado no trae `ProveedorNuevo`, `ProveedorCambios`, `Proveedor`,
`ListaProveedores` ni `EstadoProveedor`. Esta prueba no importa ningún módulo nuevo de producción (todo
entra por HTTP y por `/openapi.json`), así que no hay errores de recolección ni de fixture: solo fallos de
aserción por la ausencia de las rutas y los esquemas.

Mutantes que esta fila debe poner en rojo: `M-4` (`crear_proveedor` con `exigir_rol(*ROLES_LECTURA)`) en
TC-25; `M-11` (`ProveedorCambios` sin el `model_validator`) en TC-33; `M-12` (docstring de `Motivo` distinta
entre `proveedores` y `presupuesto`) en TC-42; una ruta sin `verificar_origen`, con `exigir_rol` antes que
él, o `async def`: TC-26 y las dos pruebas de apoyo del recorrido de rutas.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como
# F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`; aquí se exime en el archivo.
# ruff: noqa: F811

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from fastapi.testclient import TestClient

from herramientas.soporte_tkt017_api import (
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador_comparable,
    cabeceras_de,
    componentes_duplicados,
    construir_aplicacion,
    diferencias_de_forma,
    exigir_denegacion,
    exigir_error,
    forma_de_componente,
    llamadas,
    parametros_de,
    rutas_de,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado
from herramientas.soporte_tkt017_entorno import Base

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import RelojDePrueba

RUTA = "/api/v1/proveedores"
RFC = "XAXX010101000"
CREADO_ANTES = datetime(2026, 10, 1, 8, 15, tzinfo=UTC)
SEIS_ROLES = [
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
]
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
MENSAJES_DE_VALIDACION = {
    "OBLIGATORIO": "El campo es obligatorio.",
    "FORMATO": "El valor no tiene el formato esperado.",
    "DEMASIADO_LARGO": "El valor excede la longitud máxima.",
    "VALOR_NO_PERMITIDO": "El valor no está entre los permitidos.",
    "FUERA_DE_RANGO": "El valor está fuera del rango permitido.",
}

AUSENTE = object()  # el campo no viaja en el cuerpo

COLUMNAS_DE_PROVEEDOR = (
    "SELECT nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, creado_en, creado_por_id "
    "FROM proveedor WHERE id = %s"
)
COLUMNAS_DE_ASIENTO = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, obra_id, motivo, "
    "datos_antes, datos_despues FROM bitacora WHERE entidad_tipo = 'proveedor' AND entidad_id = %s "
    "ORDER BY accion::text"
)


# --------------------------------------------------------------------------- ayudas de la prueba


def _cuerpo(**cambios: object) -> dict[str, Any]:
    """El cuerpo de alta mínimo del borrador; `cambios` sustituye campos y `AUSENTE` los quita."""
    cuerpo: dict[str, Any] = {"nombre": "CoPanel", "rfc": RFC}
    for campo, valor in cambios.items():
        if valor is AUSENTE:
            cuerpo.pop(campo, None)
        else:
            cuerpo[campo] = valor
    return cuerpo


def _rfc(n: int) -> str:
    """Un RFC válido y distinto por `n` (3 letras, 6 dígitos y 3 alfanuméricos)."""
    return f"ABC0101{n:02d}AA1"


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


def _alta(cliente: TestClient, sesion: Sesion | None, cuerpo: dict[str, Any], **par: Any) -> Any:
    return _mutar(cliente, "POST", RUTA, sesion, cuerpo, **par)


def _cambiar(
    cliente: TestClient, sesion: Sesion | None, proveedor_id: object, cuerpo: object, **par: Any
) -> Any:
    return _mutar(cliente, "PATCH", f"{RUTA}/{proveedor_id}", sesion, cuerpo, **par)


def _desactivar(
    cliente: TestClient, sesion: Sesion | None, proveedor_id: object, cuerpo: object, **par: Any
) -> Any:
    return _mutar(cliente, "POST", f"{RUTA}/{proveedor_id}/desactivacion", sesion, cuerpo, **par)


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
    nombre: str,
    rfc: str,
    estado: str = "ACTIVO",
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
    proveedor_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Inserta una fila en `proveedor` con SQL directo, sin pasar por el API."""
    identificador = proveedor_id if proveedor_id is not None else uuid.uuid4()
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


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: todas las filas de `proveedor` y los asientos de proveedor."""
    return {
        "proveedores": base.filas("SELECT * FROM proveedor ORDER BY id"),
        "asientos": base.filas(
            "SELECT id FROM bitacora WHERE entidad_tipo = 'proveedor' ORDER BY id"
        ),
    }


def _exigir_nada_creado(base: Base) -> None:
    """Un rechazo no escribe: ni una fila en `proveedor` ni un asiento de proveedor."""
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE entidad_tipo = 'proveedor'") == 0


def _error_de_validacion(
    respuesta: Any, campo: str, codigo: str, mensaje: str | None = None
) -> None:
    exigir_error(
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
    nombre: str,
    rfc: str,
    *,
    estado: str = "ACTIVO",
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


# --------------------------------------------------------------------------- TC-21 · CA-1


def test_hdu004_esc02_api_alta_responde_201(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-004 esc. 2 · TC-21 · CA-1 · RN-17 — `201` con `Location` y el `Proveedor` exacto del borrador.

    Sin días ni tope el proveedor nace `ACTIVO` con corte jueves (4) y pago sábado (6), tope `null`, quién lo
    creó y cuándo (el reloj inyectado) y un asiento `CREAR` en la misma transacción (regla 8). Aparece en
    `GET /proveedores` sin indicar estado. Variantes: tope `"300000.0000"` y `"300000"` (los dos vuelven
    como cadena con cuatro decimales, nunca como número), días 2 y 5, y tope `null` explícito.
    """
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = _alta(cliente, usuario, _cuerpo())

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Proveedor", cuerpo)
    assert set(cuerpo) == CLAVES_DE_PROVEEDOR
    proveedor_id = uuid.UUID(cuerpo["id"])
    assert respuesta.headers["Location"] == f"{RUTA}/{proveedor_id}"
    assert datetime.fromisoformat(cuerpo["creado_en"]) == reloj_de_prueba.ahora
    assert _sin_fecha(cuerpo) == _esperado(proveedor_id, "CoPanel", RFC)
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", RFC, "ACTIVO", None, 4, 6, reloj_de_prueba.ahora, usuario.usuario_id)
    ]
    assert base.filas(COLUMNAS_DE_ASIENTO, proveedor_id) == [
        (
            "CREAR",
            "proveedor",
            proveedor_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            None,
            {
                "nombre": "CoPanel",
                "rfc": RFC,
                "estado": "ACTIVO",
                "tope_consignacion": None,
                "dia_corte": 4,
                "dia_pago": 6,
            },
        )
    ]
    listada = _leer(cliente, usuario)
    assert listada.status_code == 200, listada.text
    assert [p["id"] for p in listada.json()["elementos"]] == [str(proveedor_id)]

    # Variantes de CA-1: cada una con su RFC.
    variantes: list[tuple[dict[str, Any], str | None, int, int]] = [
        (_cuerpo(rfc=_rfc(1), tope_consignacion="300000.0000"), "300000.0000", 4, 6),
        (_cuerpo(rfc=_rfc(2), tope_consignacion="300000"), "300000.0000", 4, 6),
        (_cuerpo(rfc=_rfc(3), dia_corte=2, dia_pago=5), None, 2, 5),
        (_cuerpo(rfc=_rfc(4), tope_consignacion=None), None, 4, 6),
    ]
    for cuerpo_enviado, tope, corte, pago in variantes:
        creada = _alta(cliente, usuario, cuerpo_enviado)
        assert creada.status_code == 201, creada.text
        validar_contra("Proveedor", creada.json())
        assert _sin_fecha(creada.json()) == _esperado(
            creada.json()["id"],
            "CoPanel",
            cuerpo_enviado["rfc"],
            tope=tope,
            dia_corte=corte,
            dia_pago=pago,
        )
        assert creada.json()["tope_consignacion"] is None or isinstance(
            creada.json()["tope_consignacion"], str
        )
        assert base.filas(
            "SELECT tope_consignacion, dia_corte, dia_pago FROM proveedor WHERE id = %s",
            uuid.UUID(creada.json()["id"]),
        ) == [(tope, corte, pago)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 5


# --------------------------------------------------------------------------- TC-22 · CA-2


def test_hdu004_esc03_api_rfc_duplicado(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 3 · TC-22 · CA-2 · D-2 · D-1 — `409` `CONFLICTO` `RFC_DUPLICADO` con el proveedor existente y sin acciones.

    Contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, `detalle` con el id
    y el «nombre · RFC» del existente y `acciones` vacía (no existe una acción `VER_PROVEEDOR`). El mismo RFC
    en minúsculas y con espacios choca igual: el mensaje trae el RFC normalizado. Nada nuevo se escribe: una
    fila y un `CREAR`.
    """
    usuario = abrir_sesion(("COMPRAS",))
    primera = _alta(cliente, usuario, _cuerpo())
    assert primera.status_code == 201, primera.text
    existente_id = primera.json()["id"]
    antes = _foto(base)

    for intento in (RFC, " xaxx010101000 "):
        respuesta = _alta(cliente, usuario, _cuerpo(nombre="Otro nombre", rfc=intento))

        exigir_error(
            respuesta,
            estado=409,
            esperado={
                "tipo": "CONFLICTO",
                "codigo": "RFC_DUPLICADO",
                "mensaje": f"Ya existe un proveedor con el RFC {RFC}.",
                "detalle": {
                    "proveedor_existente_id": existente_id,
                    "proveedor_existente": f"CoPanel · {RFC}",
                },
                "acciones": [],
            },
            esquema="ErrorConflictoEstado",
        )
        assert _foto(base) == antes, repr(intento)

    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 1


# --------------------------------------------------------------------------- TC-23 · CA-4


CASOS_DE_FORMA = [
    pytest.param({"nombre": AUSENTE}, "nombre", "OBLIGATORIO", id="nombre_ausente"),
    pytest.param({"nombre": ""}, "nombre", "OBLIGATORIO", id="nombre_vacio"),
    pytest.param({"nombre": "   "}, "nombre", "OBLIGATORIO", id="nombre_en_blanco"),
    pytest.param({"nombre": "Co\u0000Panel"}, "nombre", "FORMATO", id="nul_en_nombre"),
    pytest.param({"rfc": AUSENTE}, "rfc", "OBLIGATORIO", id="rfc_ausente"),
    pytest.param({"rfc": "XAXX01010100"}, "rfc", "FORMATO", id="rfc_corto"),
    pytest.param({"rfc": "XAXX0101010001"}, "rfc", "FORMATO", id="rfc_largo"),
    pytest.param({"rfc": "1AXX010101000"}, "rfc", "FORMATO", id="rfc_empieza_con_digito"),
    pytest.param({"rfc": "XAXX01O101000"}, "rfc", "FORMATO", id="rfc_letra_O_en_la_fecha"),
    pytest.param({"rfc": 123}, "rfc", "FORMATO", id="rfc_numero_json"),
    pytest.param({"rfc": "XAXX010101000\u0000"}, "rfc", "FORMATO", id="nul_en_rfc"),
    pytest.param({"rfc": "XAXX010101000\n"}, "rfc", "FORMATO", id="rfc_salto_de_linea_final"),
    pytest.param({"rfc": "XAXX0101٠1000"}, "rfc", "FORMATO", id="rfc_digito_arabigo_indico"),
    pytest.param({"rfc": "ßAX010101000"}, "rfc", "FORMATO", id="rfc_eszett_se_expande"),
    pytest.param({"rfc": "ıAX010101000"}, "rfc", "FORMATO", id="rfc_i_sin_punto"),
    pytest.param({"rfc": "ſAX010101000"}, "rfc", "FORMATO", id="rfc_s_larga"),
    pytest.param({"dia_corte": 0}, "dia_corte", "FUERA_DE_RANGO", id="dia_corte_cero"),
    pytest.param({"dia_corte": 8}, "dia_corte", "FUERA_DE_RANGO", id="dia_corte_ocho"),
    pytest.param({"dia_pago": 0}, "dia_pago", "FUERA_DE_RANGO", id="dia_pago_cero"),
    pytest.param({"dia_pago": 8}, "dia_pago", "FUERA_DE_RANGO", id="dia_pago_ocho"),
    pytest.param({"dia_corte": "4"}, "dia_corte", "FORMATO", id="dia_corte_cadena"),
    pytest.param({"dia_pago": "6"}, "dia_pago", "FORMATO", id="dia_pago_cadena"),
    pytest.param({"dia_corte": 4.5}, "dia_corte", "FORMATO", id="dia_corte_decimal"),
    pytest.param({"dia_pago": 4.5}, "dia_pago", "FORMATO", id="dia_pago_decimal"),
    pytest.param({"dia_corte": True}, "dia_corte", "FORMATO", id="dia_corte_booleano"),
    pytest.param({"dia_pago": True}, "dia_pago", "FORMATO", id="dia_pago_booleano"),
    pytest.param({"tope_consignacion": "-1"}, "tope_consignacion", "FORMATO", id="tope_negativo"),
    pytest.param(
        {"tope_consignacion": "1.00001"}, "tope_consignacion", "FORMATO", id="tope_cinco_decimales"
    ),
    pytest.param(
        {"tope_consignacion": 300000}, "tope_consignacion", "FORMATO", id="tope_numero_json"
    ),
    pytest.param({"tope_consignacion": "1e3"}, "tope_consignacion", "FORMATO", id="tope_exponente"),
    pytest.param(
        {"tope_consignacion": "٣"}, "tope_consignacion", "FORMATO", id="tope_digito_arabigo_indico"
    ),
    pytest.param(
        {"tope_consignacion": "1\n"}, "tope_consignacion", "FORMATO", id="tope_salto_de_linea_final"
    ),
    pytest.param(
        {"tope_consignacion": "123456789012345"},
        "tope_consignacion",
        "FORMATO",
        id="tope_quince_enteros",
    ),
]


@pytest.mark.parametrize(("cambios", "campo", "codigo"), CASOS_DE_FORMA)
def test_hdu004_esc02_api_forma_invalida(
    cambios: dict[str, object],
    campo: str,
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 2 · TC-23 · CA-4 — un cuerpo que no cumple la forma del contrato: `422` `VALIDACION` con el campo.

    Una fila por defecto de `CA-4`, con el `campo`, el `codigo` del catálogo y el `mensaje` literal. Un `NUL`,
    un salto de línea final o un dígito no ASCII se rechazan aquí y no llegan al motor (en TKT-017 un `NUL`
    dio `500`). `Strict` rechaza la cadena `"4"`, el decimal `4.5` y el booleano `true` como día (E-10). Un
    solo campo inválido a la vez, así que `errores` trae una entrada. No se escribe ni una fila en `proveedor`
    ni un asiento de proveedor.
    """
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = _alta(cliente, usuario, _cuerpo(**cambios))

    _error_de_validacion(respuesta, campo, codigo)
    _exigir_nada_creado(base)


# --------------------------------------------------------------------------- TC-24 · CA-4


def test_tkt029a_api_tope_del_nombre(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-24 · CA-4 · HDU-004 esc. 2 · D-5 — `nombre` de 200 caracteres tras recortar se admite; de 201, `422` `DEMASIADO_LARGO`.

    El tope se mide después de quitar los espacios de los extremos: 200 letras con un espacio a cada lado
    miden 202 en bruto y se admiten, y se guardan recortadas. Un `maxLength: 200` en `ProveedorNuevo.nombre`
    que el borrador no tenía (`D-5`, aprobada).
    """
    usuario = abrir_sesion(("COMPRAS",))

    rechazada = _alta(cliente, usuario, _cuerpo(nombre="n" * 201))
    _error_de_validacion(rechazada, "nombre", "DEMASIADO_LARGO")
    _exigir_nada_creado(base)

    admitida = _alta(cliente, usuario, _cuerpo(nombre="n" * 200, rfc=_rfc(1)))
    assert admitida.status_code == 201, admitida.text
    assert admitida.json()["nombre"] == "n" * 200

    recortada = _alta(cliente, usuario, _cuerpo(nombre=" " + "m" * 200 + " ", rfc=_rfc(2)))
    assert recortada.status_code == 201, recortada.text
    assert recortada.json()["nombre"] == "m" * 200
    assert base.filas("SELECT nombre FROM proveedor WHERE rfc = %s", _rfc(2)) == [("m" * 200,)]


def test_tkt029a_api_rfc_con_enie_minuscula_se_normaliza_a_mayuscula(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-23 · CA-4 · D-1 · F001 — la `ñ` minúscula sigue siendo válida y el RFC se guarda en mayúsculas.

    Guarda de regresión de la corrección de `F001`: al rechazar todo carácter fuera de
    `[A-Za-zÑñ&0-9]` (`ß`, `ı`, `ſ` se expandían con `upper()`), la `ñ` no puede caer con ellos.
    `ñax010101000` se guarda y se devuelve como `ÑAX010101000`, igual que las letras ASCII en minúscula.
    """
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = _alta(cliente, usuario, _cuerpo(rfc="ñax010101000"))

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Proveedor", cuerpo)
    assert cuerpo["rfc"] == "ÑAX010101000"
    assert base.filas("SELECT rfc FROM proveedor WHERE id = %s", uuid.UUID(cuerpo["id"])) == [
        ("ÑAX010101000",)
    ]


# --------------------------------------------------------------------------- TC-25 · CA-5


SIN_PERMISO = [
    *(pytest.param(rol, "alta", id=f"{rol}_alta") for rol in ROLES_SIN_GESTION),
    pytest.param("DIRECTOR_PROYECTOS", "cambio", id="DIRECTOR_PROYECTOS_cambio"),
    pytest.param("DIRECTOR_PROYECTOS", "desactivacion", id="DIRECTOR_PROYECTOS_desactivacion"),
]


def _peticion(operacion: str, proveedor_id: uuid.UUID) -> tuple[str, str, dict[str, Any]]:
    """Método, ruta concreta y cuerpo válido de cada mutación."""
    if operacion == "alta":
        return "POST", RUTA, _cuerpo(nombre="Tablaroca Sur", rfc="TSU010101AB2")
    if operacion == "cambio":
        return "PATCH", f"{RUTA}/{proveedor_id}", {"dia_corte": 2}
    return (
        "POST",
        f"{RUTA}/{proveedor_id}/desactivacion",
        {"motivo": "Ya no surte tablaroca"},
    )


@pytest.mark.parametrize(("rol", "operacion"), SIN_PERMISO)
def test_tkt029a_api_mutaciones_sin_permiso(
    rol: str,
    operacion: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-25 · CA-5 · M-4 — `403` `PERMISO` `ROL_INSUFICIENTE` con `COMPRAS` como único rol exigido, sin cifras del recurso y con su `DENEGAR`.

    Los cinco roles que no gestionan el catálogo intentan el alta; Director de Proyectos intenta además el
    cambio y la desactivación. El cuerpo no trae `detalle` ni el nombre ni el RFC del proveedor; el intento
    queda asentado como `DENEGAR` a nombre de quien llamó, con método, ruta concreta y roles exigidos. El
    proveedor existente queda como estaba y no se crea ninguna fila.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id, nombre="CoPanel", rfc=RFC, tope="300000.0000")
    usuario = abrir_sesion((rol,))
    antes = _foto(base)
    metodo, ruta, cuerpo = _peticion(operacion, proveedor_id)

    respuesta = _mutar(cliente, metodo, ruta, usuario, cuerpo)

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
    for cifra in ("CoPanel", RFC, "300000", "Tablaroca Sur", "TSU010101AB2"):
        assert cifra not in respuesta.text, cifra
    assert _foto(base) == antes
    exigir_denegacion(
        base,
        metodo=metodo,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ROL_INSUFICIENTE",
        ruta=ruta,
        roles_requeridos=["COMPRAS"],
    )


# --------------------------------------------------------------------------- TC-26 · CA-5, CA-R2


@pytest.mark.parametrize("operacion", ["alta", "cambio", "desactivacion"])
@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt029a_api_mutaciones_sin_sesion_y_sin_csrf(
    operacion: str,
    cookie: str | None,
    cabecera: str | None,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-26 · CA-5 · CA-R2 · RNF-05 — sin sesión `401` `SESION`; con sesión de COMPRAS y sin el doble envío, `403` `ORIGEN_NO_VERIFICADO` con su `DENEGAR`.

    Las tres mutaciones por las cuatro combinaciones de `CA-9` de TKT-057 (`SIN_PAR_VALIDO`). Sin sesión
    responde `401` aunque el par sea válido, y una denegación anónima no se asienta. Con sesión y sin par, la
    petición no se ejecuta aunque quien llama pueda gestionar proveedores. En todos los casos el proveedor
    existente queda como estaba y no se crea nada.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id, nombre="CoPanel", rfc=RFC)
    antes = _foto(base)
    metodo, ruta, cuerpo = _peticion(operacion, proveedor_id)

    anonima = _mutar(cliente, metodo, ruta, None, cuerpo)
    exigir_error(anonima, estado=401, esperado=_sin_sesion(), esquema="ErrorSesion")
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0

    respuesta = _mutar(
        cliente, metodo, ruta, dueno, cuerpo, cookie_csrf=cookie, cabecera_csrf=cabecera
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
        metodo=metodo,
        usuario_id=dueno.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=ruta,
        roles_requeridos=[],
    )


@pytest.mark.parametrize("operacion", ["alta", "cambio", "desactivacion"])
def test_tkt029a_api_el_origen_se_verifica_antes_que_el_rol(
    operacion: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-5 · CA-R2 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    Apoyo de TC-26 (no está en el plan): `verificar_origen` va antes que `exigir_rol` en las tres mutaciones;
    un solo `DENEGAR` con motivo `ORIGEN_NO_VERIFICADO`. Con el orden invertido el motivo sería
    `ROL_INSUFICIENTE`.
    """
    dueno = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, dueno.usuario_id, nombre="CoPanel", rfc=RFC)
    usuario = abrir_sesion(("DIRECTOR_PROYECTOS",))
    metodo, ruta, cuerpo = _peticion(operacion, proveedor_id)

    respuesta = _mutar(cliente, metodo, ruta, usuario, cuerpo, cookie_csrf=None, cabecera_csrf=None)

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
        metodo=metodo,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=ruta,
        roles_requeridos=[],
    )


# --------------------------------------------------------------------------- TC-27 · CA-6


def test_hdu004_esc02_api_lista_por_omision_solo_activos(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 2 · TC-27 · CA-6 · D-8 · E-2 · M-8 — cada uno de los seis roles recibe `200` con solo los `ACTIVO`, y el orden es el mismo.

    Cuatro activos, un desactivado y uno en baja, sembrados desordenados. El orden es `nombre` ascendente y
    `id` como desempate (dos proveedores se llaman igual y se insertan en el orden contrario al de su id);
    dos llamadas seguidas dan lo mismo. La paginación trae `pagina`, `tamano_pagina` y `total` del filtro, y
    `pagina=2&tamano_pagina=2` da los dos últimos. Los importes viajan como cadena. Leer no asienta `DENEGAR`.
    """
    dueno = abrir_sesion(("COMPRAS",))
    id_uno = uuid.UUID("00000000-0000-4000-8000-000000000001")
    id_dos = uuid.UUID("00000000-0000-4000-8000-000000000002")
    zinc = _sembrar(
        base,
        dueno.usuario_id,
        nombre="Zinc y Perfiles",
        rfc="ZYP010101AA1",
        dia_corte=2,
        dia_pago=5,
    )
    madera = _sembrar(
        base, dueno.usuario_id, nombre="Madera Norte", rfc="MAN010101BB2", tope="300000.0000"
    )
    _sembrar(base, dueno.usuario_id, nombre="Acero Sur", rfc="ACS020202CC3", proveedor_id=id_dos)
    _sembrar(base, dueno.usuario_id, nombre="Acero Sur", rfc="ACS010101CC3", proveedor_id=id_uno)
    _sembrar(
        base, dueno.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="DESACTIVADO"
    )
    _sembrar(base, dueno.usuario_id, nombre="Aislantes Baja", rfc="AIB010101DD4", estado="BAJA")
    esperados = [
        _esperado(id_uno, "Acero Sur", "ACS010101CC3"),
        _esperado(id_dos, "Acero Sur", "ACS020202CC3"),
        _esperado(madera, "Madera Norte", "MAN010101BB2", tope="300000.0000"),
        _esperado(zinc, "Zinc y Perfiles", "ZYP010101AA1", dia_corte=2, dia_pago=5),
    ]

    for rol in SEIS_ROLES:
        lector = abrir_sesion((rol,))

        primera = _leer(cliente, lector)
        segunda = _leer(cliente, lector)

        assert primera.status_code == 200, f"{rol}: {primera.text}"
        cuerpo = primera.json()
        validar_contra("ListaProveedores", cuerpo)
        assert set(cuerpo) == {"elementos", "paginacion"}, rol
        assert [_sin_fecha(p) for p in cuerpo["elementos"]] == esperados, rol
        assert {p["estado"] for p in cuerpo["elementos"]} == {"ACTIVO"}, rol
        assert all(
            datetime.fromisoformat(p["creado_en"]) == CREADO_ANTES for p in cuerpo["elementos"]
        ), rol
        assert cuerpo["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 4}, rol
        assert segunda.status_code == 200 and segunda.json() == cuerpo, rol

    segunda_pagina = _leer(
        cliente, abrir_sesion(("ALMACEN",)), consulta=[("pagina", "2"), ("tamano_pagina", "2")]
    )
    assert segunda_pagina.status_code == 200, segunda_pagina.text
    assert [_sin_fecha(p) for p in segunda_pagina.json()["elementos"]] == esperados[2:]
    assert segunda_pagina.json()["paginacion"] == {"pagina": 2, "tamano_pagina": 2, "total": 4}
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0


# --------------------------------------------------------------------------- TC-28 · CA-6


def test_hdu004_esc12_api_lista_filtro_y_busqueda(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-28 · CA-6 · D-9 · M-7 — filtro por estado, búsqueda sin distinguir mayúsculas y `%` y `_` como texto literal.

    `estado=DESACTIVADO` solo trae los desactivados; `estado` repetido trae la unión; `estado=BAJA` trae las
    bajas. `q` busca por parte del nombre o del RFC, también combinada con el estado. `q=100%` encuentra
    «Pinturas 100%» y no «Pinturas 1000»; `q=_` solo encuentra «Acero_Sur» y no «AceroXSur»; `q=%` solo
    encuentra el nombre que lleva ese signo. Una `q` en blanco equivale a no filtrar. El `total` es el del
    filtro, no el de la tabla.
    """
    dueno = abrir_sesion(("COMPRAS",))
    copanel = _sembrar(base, dueno.usuario_id, nombre="CoPanel", rfc=RFC)
    tablaroca = _sembrar(
        base, dueno.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="DESACTIVADO"
    )
    cien = _sembrar(base, dueno.usuario_id, nombre="Pinturas 100%", rfc="PIN010101AA1")
    mil = _sembrar(base, dueno.usuario_id, nombre="Pinturas 1000", rfc="PIN020202BB2")
    guion = _sembrar(base, dueno.usuario_id, nombre="Acero_Sur", rfc="ACE010101CC3")
    equis = _sembrar(base, dueno.usuario_id, nombre="AceroXSur", rfc="ACX010101DD4")
    baja = _sembrar(
        base, dueno.usuario_id, nombre="Proveedor Baja", rfc="BAJ010101EE5", estado="BAJA"
    )
    lector = abrir_sesion(("RESIDENTE",))

    def ids(consulta: list[tuple[str, str]]) -> tuple[set[str], int]:
        respuesta = _leer(cliente, lector, consulta=consulta)
        assert respuesta.status_code == 200, f"{consulta}: {respuesta.text}"
        validar_contra("ListaProveedores", respuesta.json())
        return (
            {p["id"] for p in respuesta.json()["elementos"]},
            respuesta.json()["paginacion"]["total"],
        )

    assert ids([("estado", "DESACTIVADO")]) == ({str(tablaroca)}, 1)
    assert ids([("estado", "BAJA")]) == ({str(baja)}, 1)
    assert ids([("estado", "ACTIVO"), ("estado", "DESACTIVADO")]) == (
        {str(i) for i in (copanel, tablaroca, cien, mil, guion, equis)},
        6,
    )
    assert ids([("q", "copan")]) == ({str(copanel)}, 1)
    assert ids([("q", "xaxx0101")]) == ({str(copanel)}, 1)
    assert ids([("q", "  copan  ")]) == ({str(copanel)}, 1)
    assert ids([("q", "tsu010101ab")]) == (set(), 0), "Por omisión solo los ACTIVO"
    assert ids([("q", "tsu010101ab"), ("estado", "DESACTIVADO")]) == ({str(tablaroca)}, 1)
    assert ids([("q", "100%")]) == ({str(cien)}, 1)
    assert ids([("q", "%")]) == ({str(cien)}, 1)
    assert ids([("q", "_")]) == ({str(guion)}, 1)
    assert ids([("q", "Acero_Sur")]) == ({str(guion)}, 1)
    assert ids([("q", "   ")]) == (ids([]))
    assert ids([]) == ({str(i) for i in (copanel, cien, mil, guion, equis)}, 5)


# --------------------------------------------------------------------------- TC-29 · CA-6


@pytest.mark.parametrize(
    ("consulta", "campo", "codigo"),
    [
        pytest.param([("estado", "OTRO")], "estado[0]", "VALOR_NO_PERMITIDO", id="estado_otro"),
        pytest.param([("pagina", "0")], "pagina", "FUERA_DE_RANGO", id="pagina_cero"),
        pytest.param([("tamano_pagina", "0")], "tamano_pagina", "FUERA_DE_RANGO", id="tamano_cero"),
        pytest.param(
            [("tamano_pagina", "201")], "tamano_pagina", "FUERA_DE_RANGO", id="tamano_sobre_200"
        ),
        pytest.param([("q", "a\u0000b")], "q", "FORMATO", id="q_con_nul"),
        pytest.param([("q", "a" * 201)], "q", "DEMASIADO_LARGO", id="q_de_201"),
    ],
)
def test_tkt029a_api_lista_parametros_invalidos(
    consulta: list[tuple[str, str]],
    campo: str,
    codigo: str,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-29 · CA-6 · D-9 — un `estado` fuera del enumerado, `pagina` menor que 1, `tamano_pagina` fuera de 1 a 200 o una `q` con `NUL` o de más de 200: `422` con el parámetro.

    E-2: el `campo` de un `estado` inválido en una lista de consulta es `estado[0]` y su código es
    `VALOR_NO_PERMITIDO` (comprobado en TKT-012a con el manejador real). Una `q` con `NUL` no llega al
    motor, que respondería `500` (lección de TKT-017). Ninguno responde `500`.
    """
    lector = abrir_sesion(("COMPRAS",))

    respuesta = _leer(cliente, lector, consulta=consulta)

    _error_de_validacion(respuesta, campo, codigo)


# --------------------------------------------------------------------------- TC-30 · CA-6


@pytest.mark.parametrize("pagina", [1000, 10**30])
def test_tkt029a_api_lista_pagina_inalcanzable(
    pagina: int,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-30 · CA-6 · D20 — una `pagina` más allá del final, por enorme que sea, da `200`, `elementos` vacío y el `total` real.

    `10**30` desborda el `bigint` de PostgreSQL como desplazamiento: el corte en Python evita el `500`. La
    paginación devuelve la `pagina` pedida y el tamaño por omisión.
    """
    dueno = abrir_sesion(("COMPRAS",))
    for n in range(3):
        _sembrar(base, dueno.usuario_id, nombre=f"Proveedor {n}", rfc=_rfc(n))
    lector = abrir_sesion(("ALMACEN",))

    respuesta = _leer(cliente, lector, consulta=[("pagina", str(pagina))])

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("ListaProveedores", respuesta.json())
    assert respuesta.json() == {
        "elementos": [],
        "paginacion": {"pagina": pagina, "tamano_pagina": 50, "total": 3},
    }


# --------------------------------------------------------------------------- TC-31 · CA-7


def test_tkt029a_api_obtener_proveedor(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-31 · CA-7 — `200` con el proveedor completo, también `DESACTIVADO`; inexistente `404`; no UUID `422`; sin sesión `401`.

    El `404` es `NO_ENCONTRADO` con `recurso` `proveedor` (no la ruta, que es lo que responde un enrutador
    sin ella); `/proveedores/abc` es `422` `FORMATO` en `proveedor_id`. La lista y la consulta sin sesión
    responden `401` `SESION` sin asiento `DENEGAR`. Lo lee cualquier rol.
    """
    dueno = abrir_sesion(("COMPRAS",))
    activo = _sembrar(
        base,
        dueno.usuario_id,
        nombre="CoPanel",
        rfc=RFC,
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    desactivado = _sembrar(
        base, dueno.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="DESACTIVADO"
    )
    lector = abrir_sesion(("ADMINISTRACION",))

    uno = _leer(cliente, lector, f"{RUTA}/{activo}")
    otro = _leer(cliente, lector, f"{RUTA}/{desactivado}")

    assert uno.status_code == 200, uno.text
    validar_contra("Proveedor", uno.json())
    assert set(uno.json()) == CLAVES_DE_PROVEEDOR
    assert _sin_fecha(uno.json()) == _esperado(
        activo, "CoPanel", RFC, tope="300000.0000", dia_corte=2, dia_pago=5
    )
    assert datetime.fromisoformat(uno.json()["creado_en"]) == CREADO_ANTES
    assert otro.status_code == 200, otro.text
    validar_contra("Proveedor", otro.json())
    assert _sin_fecha(otro.json()) == _esperado(
        desactivado, "Tablaroca Sur", "TSU010101AB2", estado="DESACTIVADO"
    )

    exigir_error(
        _leer(cliente, lector, f"{RUTA}/{uuid.uuid4()}"),
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
            "recurso": "proveedor",
        },
        esquema="ErrorNoEncontrado",
    )
    _error_de_validacion(_leer(cliente, lector, f"{RUTA}/abc"), "proveedor_id", "FORMATO")
    for ruta in (RUTA, f"{RUTA}/{activo}"):
        exigir_error(
            _leer(cliente, None, ruta), estado=401, esperado=_sin_sesion(), esquema="ErrorSesion"
        )
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0


# --------------------------------------------------------------------------- TC-32 · CA-8


def test_tkt029a_api_actualizar_proveedor(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-32 · CA-8 · RN-17 · D-3 · D-6 — `200` con el proveedor actualizado y un `ACTUALIZAR` con los valores de antes y de después.

    `dia_corte` 2 y tope `"250000.0000"` sobre un proveedor sin tope: el asiento trae exactamente esos dos
    campos. El RFC y el estado no cambian aunque el cuerpo traiga `"rfc"` y `"estado"` además del día
    (campos extra ignorados). Un `DESACTIVADO` también admite el cambio y sigue `DESACTIVADO`. Un tope
    presente y `null` deja la columna en `NULL`.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id, nombre="CoPanel", rfc=RFC)

    respuesta = _cambiar(
        cliente,
        usuario,
        proveedor_id,
        {
            "dia_corte": 2,
            "tope_consignacion": "250000.0000",
            "rfc": "ZZZ990101AA1",
            "estado": "BAJA",
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Proveedor", respuesta.json())
    assert _sin_fecha(respuesta.json()) == _esperado(
        proveedor_id, "CoPanel", RFC, tope="250000.0000", dia_corte=2
    )
    assert datetime.fromisoformat(respuesta.json()["creado_en"]) == CREADO_ANTES
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", RFC, "ACTIVO", "250000.0000", 2, 6, CREADO_ANTES, usuario.usuario_id)
    ]
    assert base.filas(COLUMNAS_DE_ASIENTO, proveedor_id) == [
        (
            "ACTUALIZAR",
            "proveedor",
            proveedor_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            {"dia_corte": 4, "tope_consignacion": None},
            {"dia_corte": 2, "tope_consignacion": "250000.0000"},
        )
    ]

    # Variante: un tope presente y `null` deja la columna en NULL.
    sin_tope = _cambiar(cliente, usuario, proveedor_id, {"tope_consignacion": None})
    assert sin_tope.status_code == 200, sin_tope.text
    assert sin_tope.json()["tope_consignacion"] is None
    assert base.filas(
        "SELECT tope_consignacion, dia_corte FROM proveedor WHERE id = %s", proveedor_id
    ) == [(None, 2)]

    # Variante: un DESACTIVADO también admite el cambio de sus datos (D-3) y sigue desactivado.
    desactivado = _sembrar(
        base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2", estado="DESACTIVADO"
    )
    cambiado = _cambiar(
        cliente, usuario, desactivado, {"nombre": "Tablaroca del Sur", "dia_pago": 7}
    )
    assert cambiado.status_code == 200, cambiado.text
    validar_contra("Proveedor", cambiado.json())
    assert _sin_fecha(cambiado.json()) == _esperado(
        desactivado, "Tablaroca del Sur", "TSU010101AB2", estado="DESACTIVADO", dia_pago=7
    )
    assert base.filas(
        "SELECT nombre, estado, dia_pago FROM proveedor WHERE id = %s", desactivado
    ) == [("Tablaroca del Sur", "DESACTIVADO", 7)]


# --------------------------------------------------------------------------- TC-33 · CA-8


CASOS_DE_CAMBIO_INVALIDO = [
    pytest.param({}, "cuerpo", "FORMATO", id="cuerpo_vacio"),
    pytest.param({"rfc": "XAXX010101000"}, "cuerpo", "FORMATO", id="solo_campos_desconocidos"),
    pytest.param({"dia_corte": 0}, "dia_corte", "FUERA_DE_RANGO", id="dia_corte_cero"),
    pytest.param({"dia_corte": 8}, "dia_corte", "FUERA_DE_RANGO", id="dia_corte_ocho"),
    pytest.param({"dia_pago": 0}, "dia_pago", "FUERA_DE_RANGO", id="dia_pago_cero"),
    pytest.param({"dia_pago": 8}, "dia_pago", "FUERA_DE_RANGO", id="dia_pago_ocho"),
    pytest.param({"dia_corte": "4"}, "dia_corte", "FORMATO", id="dia_corte_cadena"),
    pytest.param({"dia_corte": None}, "dia_corte", "FORMATO", id="dia_corte_nulo"),
    pytest.param({"dia_pago": None}, "dia_pago", "FORMATO", id="dia_pago_nulo"),
    pytest.param({"tope_consignacion": "-1"}, "tope_consignacion", "FORMATO", id="tope_negativo"),
    pytest.param({"nombre": ""}, "nombre", "OBLIGATORIO", id="nombre_vacio"),
    pytest.param({"nombre": None}, "nombre", "FORMATO", id="nombre_nulo"),
    pytest.param({"nombre": "Co\u0000Panel"}, "nombre", "FORMATO", id="nul_en_nombre"),
    pytest.param({"nombre": "n" * 201}, "nombre", "DEMASIADO_LARGO", id="nombre_de_201"),
]


@pytest.mark.parametrize(("cuerpo", "campo", "codigo"), CASOS_DE_CAMBIO_INVALIDO)
def test_tkt029a_api_actualizar_cuerpo_invalido(
    cuerpo: dict[str, object],
    campo: str,
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-33 · CA-8 · D-6 · M-11 · E-5 · E-6 — un cuerpo sin ninguna propiedad conocida o con un valor inválido: `422` con el campo, y el proveedor no cambia.

    `{}` y `{"rfc": ...}` (solo campos desconocidos, que se ignoran) cuentan como cuerpo vacío y salen con
    `campo` `cuerpo` (E-5: la `loc` del validador del modelo es el cuerpo entero). `null` explícito en
    `nombre` o en un día es `422` y no se escribe `NULL` (E-6: el campo es opcional pero no anulable). Ningún
    caso asienta `ACTUALIZAR` ni cambia la fila.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(
        base,
        usuario.usuario_id,
        nombre="CoPanel",
        rfc=RFC,
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    antes = _foto(base)

    respuesta = _cambiar(cliente, usuario, proveedor_id, cuerpo)

    _error_de_validacion(respuesta, campo, codigo)
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ACTUALIZAR'") == 0


# --------------------------------------------------------------------------- TC-34 · CA-8


def test_tkt029a_api_actualizar_inexistente(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-34 · CA-8 — cambiar un proveedor que no existe: `404` `NO_ENCONTRADO` con `recurso` `proveedor` y ningún asiento."""
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = _cambiar(cliente, usuario, uuid.uuid4(), {"dia_corte": 2})

    exigir_error(
        respuesta,
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
            "recurso": "proveedor",
        },
        esquema="ErrorNoEncontrado",
    )
    _exigir_nada_creado(base)


# --------------------------------------------------------------------------- TC-35 · CA-9


def test_hdu004_esc12_api_desactivar(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-004 esc. 12 · TC-35 · CA-9 · M-8 — `200` con `DESACTIVADO`; sale de la lista por omisión y sigue en `estado=DESACTIVADO` y en `GET /proveedores/{id}`.

    Todos sus datos se conservan: nombre, RFC, tope, días y `creado_en`. El `DESACTIVAR` lleva el motivo
    (sin los espacios de los extremos), el estado de antes y el de después, escrito en la misma transacción.
    Otro proveedor no cambia.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(
        base,
        usuario.usuario_id,
        nombre="CoPanel",
        rfc=RFC,
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    vecino = _sembrar(base, usuario.usuario_id, nombre="Tablaroca Sur", rfc="TSU010101AB2")
    vecino_antes = base.filas(COLUMNAS_DE_PROVEEDOR, vecino)

    respuesta = _desactivar(cliente, usuario, proveedor_id, {"motivo": "  Ya no surte tablaroca  "})

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Proveedor", respuesta.json())
    assert _sin_fecha(respuesta.json()) == _esperado(
        proveedor_id,
        "CoPanel",
        RFC,
        estado="DESACTIVADO",
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    assert datetime.fromisoformat(respuesta.json()["creado_en"]) == CREADO_ANTES
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", RFC, "DESACTIVADO", "300000.0000", 2, 5, CREADO_ANTES, usuario.usuario_id)
    ]
    assert base.filas(COLUMNAS_DE_ASIENTO, proveedor_id) == [
        (
            "DESACTIVAR",
            "proveedor",
            proveedor_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            "Ya no surte tablaroca",
            {"estado": "ACTIVO"},
            {"estado": "DESACTIVADO"},
        )
    ]
    assert base.filas(COLUMNAS_DE_PROVEEDOR, vecino) == vecino_antes

    por_omision = _leer(cliente, usuario)
    assert [p["id"] for p in por_omision.json()["elementos"]] == [str(vecino)]
    desactivados = _leer(cliente, usuario, consulta=[("estado", "DESACTIVADO")])
    assert [p["id"] for p in desactivados.json()["elementos"]] == [str(proveedor_id)]
    uno = _leer(cliente, usuario, f"{RUTA}/{proveedor_id}")
    assert uno.status_code == 200, uno.text
    assert uno.json() == respuesta.json()


# --------------------------------------------------------------------------- TC-36 · CA-9


@pytest.mark.parametrize(
    ("cuerpo", "codigo"),
    [
        pytest.param({}, "OBLIGATORIO", id="motivo_ausente"),
        pytest.param({"motivo": "   "}, "OBLIGATORIO", id="motivo_en_blanco"),
        pytest.param({"motivo": "m" * 2001}, "DEMASIADO_LARGO", id="motivo_de_2001"),
        pytest.param({"motivo": "Ya no\u0000 surte"}, "FORMATO", id="nul_en_motivo"),
    ],
)
def test_hdu004_esc12_api_desactivar_sin_motivo(
    cuerpo: dict[str, object],
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-36 · CA-9 — el motivo falta, está en blanco, pasa de 2000 caracteres o lleva `NUL`: `422` `VALIDACION` en `motivo`.

    El proveedor sigue `ACTIVO` y no se asienta nada.
    """
    usuario = abrir_sesion(("COMPRAS",))
    proveedor_id = _sembrar(base, usuario.usuario_id, nombre="CoPanel", rfc=RFC)
    antes = _foto(base)

    respuesta = _desactivar(cliente, usuario, proveedor_id, cuerpo)

    _error_de_validacion(respuesta, "motivo", codigo)
    assert _foto(base) == antes
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [("ACTIVO",)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DESACTIVAR'") == 0


# --------------------------------------------------------------------------- TC-37 · CA-9


def test_hdu004_esc12_api_desactivar_un_desactivado_o_inexistente(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-004 esc. 12 · TC-37 · CA-9 · M-5 — desactivar lo que no está `ACTIVO`: `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado actual; inexistente `404`.

    Contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, `detalle` con el
    `estado_actual` real y `acciones` vacía. Se prueba sobre un proveedor que acaba de desactivarse (segunda
    desactivación) y sobre uno en `BAJA`; en ambos la fila queda como estaba y no hay asiento nuevo. Un
    proveedor inexistente es `404` con `recurso` `proveedor` y tampoco asienta.
    """
    usuario = abrir_sesion(("COMPRAS",))
    activo = _sembrar(base, usuario.usuario_id, nombre="CoPanel", rfc=RFC)
    en_baja = _sembrar(
        base, usuario.usuario_id, nombre="Proveedor Baja", rfc="BAJ010101EE5", estado="BAJA"
    )
    primera = _desactivar(cliente, usuario, activo, {"motivo": "Primera desactivación"})
    assert primera.status_code == 200, primera.text
    antes = _foto(base)
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DESACTIVAR'") == 1

    for objetivo, estado in ((activo, "DESACTIVADO"), (en_baja, "BAJA")):
        respuesta = _desactivar(cliente, usuario, objetivo, {"motivo": "Otra vez"})

        exigir_error(
            respuesta,
            estado=409,
            esperado={
                "tipo": "CONFLICTO",
                "codigo": "ESTADO_NO_PERMITE_OPERACION",
                "mensaje": f"El proveedor no está activo: su estado es {estado}.",
                "detalle": {"estado_actual": estado},
                "acciones": [],
            },
            esquema="ErrorConflictoEstado",
        )
        assert _foto(base) == antes, estado

    inexistente = _desactivar(cliente, usuario, uuid.uuid4(), {"motivo": "No existe"})
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


# --------------------------------------------------------------------------- TC-38 · CA-10


def test_tkt029a_ca10_no_existe_ninguna_ruta_delete_de_proveedores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-38 · CA-10 esc. 1 — el enrutador de la aplicación no tiene ninguna ruta `DELETE` bajo `/api/v1/proveedores`.

    Control positivo (anti-verde vacío): sí encuentra las cinco rutas de este ticket y ninguna otra, así que
    la ausencia de `DELETE` no se debe a que el recorrido no vea las rutas de proveedores. `/baja` es de
    TKT-029b y no existe todavía.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    rutas = {
        (metodo, ruta.path)
        for ruta in rutas_de(aplicacion.routes)
        if ruta.path.startswith(RUTA)
        for metodo in (ruta.methods or ())
    }

    assert rutas == {
        ("POST", RUTA),
        ("GET", RUTA),
        ("GET", f"{RUTA}/{{proveedor_id}}"),
        ("PATCH", f"{RUTA}/{{proveedor_id}}"),
        ("POST", f"{RUTA}/{{proveedor_id}}/desactivacion"),
    }
    assert not [metodo for metodo, _ in rutas if metodo == "DELETE"]


def test_tkt029a_api_las_rutas_de_proveedores_son_def_con_sesion_y_origen_primero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-5 · CA-R2 · regla 11 · RNF-05 — las cinco rutas existen una sola vez, son `def`, exigen sesión y rol, y las que mutan verifican el origen antes que el rol.

    Apoyo de TC-25 y TC-26 (no está en el plan): los recorridos de `test_tkt006_enrutador.py` y
    `test_tkt057_csrf.py` ven las rutas de la aplicación completa. Mutantes: ruta sin `verificar_origen`,
    `async def` o `exigir_rol` antes que `verificar_origen`.
    """
    import inspect

    from cimenta.identidad.api.dependencias import sesion_vigente, verificar_origen

    aplicacion = construir_aplicacion(monkeypatch)
    rutas = list(rutas_de(aplicacion.routes))

    def la_ruta(metodo: str, camino: str) -> Any:
        halladas = [r for r in rutas if r.path == camino and metodo in (r.methods or ())]
        assert len(halladas) == 1, (
            f"Debe haber exactamente un {metodo} {camino}; hay {len(halladas)}"
        )
        return halladas[0]

    por_proveedor = f"{RUTA}/{{proveedor_id}}"
    mutaciones = [
        la_ruta("POST", RUTA),
        la_ruta("PATCH", por_proveedor),
        la_ruta("POST", f"{por_proveedor}/desactivacion"),
    ]
    lecturas = [la_ruta("GET", RUTA), la_ruta("GET", por_proveedor)]
    for ruta in (*mutaciones, *lecturas):
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
    for ruta in mutaciones:
        declaradas = [sub.call for sub in ruta.dependant.dependencies]
        assert verificar_origen in declaradas, f"{ruta.path} debe declarar verificar_origen"
        posicion_del_rol = next(
            posicion
            for posicion, llamada in enumerate(declaradas)
            if getattr(llamada, "__name__", "") == "comprobar_rol"
        )
        assert declaradas.index(verificar_origen) < posicion_del_rol


# --------------------------------------------------------------------------- TC-39 · CA-1


def test_tkt029a_api_alta_ignora_campos_extra(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-39 · CA-1 · D-6 — `estado`, `id` y `creado_en` en el cuerpo se ignoran: `201` `ACTIVO` con id nuevo y `creado_en` del reloj.

    Lo que el cliente no decide (el estado inicial, el identificador, cuándo se creó) nunca sale del cuerpo.
    """
    usuario = abrir_sesion(("COMPRAS",))
    id_enviado = uuid.uuid4()

    respuesta = _alta(
        cliente,
        usuario,
        {
            **_cuerpo(),
            "estado": "DESACTIVADO",
            "id": str(id_enviado),
            "creado_en": "2020-01-01T00:00:00Z",
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Proveedor", cuerpo)
    assert cuerpo["estado"] == "ACTIVO"
    assert cuerpo["id"] != str(id_enviado)
    assert datetime.fromisoformat(cuerpo["creado_en"]) == reloj_de_prueba.ahora
    assert base.filas("SELECT id, estado, creado_en FROM proveedor") == [
        (uuid.UUID(cuerpo["id"]), "ACTIVO", reloj_de_prueba.ahora)
    ]


# --------------------------------------------------------------------------- TC-40 · CA-1, CA-6 a CA-9


COMPONENTES_DE_PROVEEDOR = [
    "ProveedorNuevo",
    "ProveedorCambios",
    "Proveedor",
    "ListaProveedores",
    "EstadoProveedor",
    "Motivo",
    "MetaPagina",
]
OPERACIONES_DE_PROVEEDOR = {
    "crear_proveedor",
    "listar_proveedores",
    "obtener_proveedor",
    "actualizar_proveedor",
    "desactivar_proveedor",
}


@pytest.mark.parametrize("esquema", COMPONENTES_DE_PROVEEDOR)
def test_tkt029a_api_forma_publicada_igual_al_borrador(
    esquema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-40 · CA-1 · CA-6 a CA-9 · D-7 — cada esquema publicado coincide con el del borrador y no hay componentes duplicados.

    Se compara contra `borrador_comparable()`, nunca contra `borrador()`: `ProveedorNuevo.dia_corte` y
    `dia_pago` usan `allOf` de un solo elemento, que `aplanar` no resuelve. Propiedades, `required`, tipos,
    `format`, `enum` y nulabilidad con los `$ref` resueltos. Los componentes de objeto o enumerado del
    borrador deben existir con su nombre. `Motivo` y `MetaPagina` ya los publica `presupuesto`: aquí se
    comprueba, además, que las rutas de proveedores están publicadas, para que la forma compartida se lea
    tal como la ven las operaciones de este ticket.
    """
    contrato = contrato_publicado(monkeypatch)
    assert RUTA in contrato["paths"], "El contrato publicado no trae las rutas de proveedores"
    comparable = borrador_comparable()
    del_borrador, componentes_borrador = forma_de_componente(comparable, esquema)
    assert del_borrador[f"{esquema}.type"], "Anti-verde vacío: el borrador declara el tipo"
    esquemas = contrato["components"]["schemas"]
    assert esquema in esquemas, f"El contrato publicado no tiene {esquema}"

    publicada, componentes_publicados = forma_de_componente(contrato, esquema)

    assert diferencias_de_forma(del_borrador, publicada) == []
    faltan = sorted(componentes_borrador - set(esquemas))
    assert faltan == [], f"Faltan componentes con el nombre del borrador: {faltan}"
    assert componentes_duplicados(contrato, componentes_publicados) == []


def test_tkt029a_api_operaciones_publicadas_igual_al_borrador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-40 · CA-1 · CA-6 a CA-9 · E-2 · E-3 — los cinco `operationId` están publicados, `dar_baja_proveedor` no, y los parámetros de la lista son los del borrador.

    Los parámetros de `listar_proveedores` (`estado`, `q`, `pagina`, `tamano_pagina`) se comparan con
    `parametros_de`, incluido el `default` de `estado` (E-2: `["ACTIVO"]`). La alta publica el `201` y exige
    `sesion` y `csrf`. `dar_baja_proveedor` y su ruta `/baja` son de TKT-029b y no se publican.
    """
    contrato = contrato_publicado(monkeypatch)
    publicados = {
        operacion.get("operationId")
        for ruta, operaciones in contrato["paths"].items()
        if ruta.startswith(RUTA)
        for operacion in operaciones.values()
    }
    assert publicados == OPERACIONES_DE_PROVEEDOR
    assert f"{RUTA}/{{proveedor_id}}/baja" not in contrato["paths"]

    comparable = borrador_comparable()
    assert parametros_de(contrato, RUTA, "get") == parametros_de(comparable, "/proveedores", "get")
    assert parametros_de(contrato, RUTA, "get")["estado"]["default"] == ["ACTIVO"]
    assert "201" in contrato["paths"][RUTA]["post"]["responses"]
    exigidos = {
        nombre
        for requisito in contrato["paths"][RUTA]["post"].get("security", [])
        for nombre in requisito
    }
    assert {"sesion", "csrf"} <= exigidos


# --------------------------------------------------------------------------- TC-42 · CA-R2


def test_tkt029a_api_las_copias_se_publican_fusionadas(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-42 · CA-R2 · D-7 · M-12 — `MetaPagina` y `Motivo` se publican con su nombre, una sola vez, y los usan proveedores y presupuesto.

    En el `/openapi.json` publicado, `MetaPagina` y `Motivo` existen con ese nombre y su forma coincide con
    la del borrador; `ListaProveedores.paginacion` y `ListaConceptosLineaBase.paginacion` apuntan los dos a
    `#/components/schemas/MetaPagina`; el cuerpo de `desactivar_proveedor` y el de `congelar_linea_base`
    apuntan los dos a `#/components/schemas/Motivo`; y **ningún** nombre de `components.schemas` contiene
    `__` (un componente partido con prefijo de módulo, que ocurre si las copias locales divergen en forma o
    en docstring). Detecta cualquier divergencia futura entre las copias de `proveedores` y `presupuesto`.
    """
    contrato = contrato_publicado(monkeypatch)
    esquemas = contrato["components"]["schemas"]
    assert "ListaProveedores" in esquemas, "El contrato publicado no trae ListaProveedores"
    comparable = borrador_comparable()

    for nombre in ("MetaPagina", "Motivo"):
        assert nombre in esquemas, f"El contrato publicado no trae {nombre}"
        del_borrador, _ = forma_de_componente(comparable, nombre)
        publicada, _ = forma_de_componente(contrato, nombre)
        assert diferencias_de_forma(del_borrador, publicada) == [], nombre

    metapagina = {"$ref": "#/components/schemas/MetaPagina"}
    assert esquemas["ListaProveedores"]["properties"]["paginacion"] == metapagina
    assert esquemas["ListaConceptosLineaBase"]["properties"]["paginacion"] == metapagina

    def cuerpo_de(operacion_id: str) -> object:
        for operaciones in contrato["paths"].values():
            for operacion in operaciones.values():
                if operacion.get("operationId") == operacion_id:
                    return operacion["requestBody"]["content"]["application/json"]["schema"]
        raise AssertionError(f"La operación {operacion_id} no está publicada")

    motivo = {"$ref": "#/components/schemas/Motivo"}
    assert cuerpo_de("desactivar_proveedor") == motivo
    assert cuerpo_de("congelar_linea_base") == motivo
    partidos = sorted(nombre for nombre in esquemas if "__" in nombre)
    assert partidos == [], f"Componentes partidos con prefijo de módulo: {partidos}"
