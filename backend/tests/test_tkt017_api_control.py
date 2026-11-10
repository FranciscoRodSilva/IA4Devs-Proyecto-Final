"""API del presupuesto de control, fila C3 de TKT-017c: `GET` y `PUT` de `/api/v1/lineas-base/{linea_base_id}/presupuesto-control`.

Cubre TC-C01, TC-C02, TC-C04 a TC-C06, TC-C11, TC-C12, TC-C14, TC-C15, TC-C19 y la parte de C3 de TC-B19 del
diseño (`CA-C1` a `CA-C6`, y `CA-C7` por la API; `HDU-001` esc. 15, 17, 22 y 23; `RN-03`, `RN-04`, `PA-03`)
contra PostgreSQL migrado con `alembic upgrade head` y el rol de aplicación, por la aplicación real
(`crear_aplicacion`) y un `TestClient` HTTPS:

- `GET /api/v1/lineas-base/{linea_base_id}/presupuesto-control` (`listar_presupuesto_control`),
- `PUT /api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}`
  (`capturar_presupuesto_control`).

La línea base `CONGELADA` se siembra con cifras exactas (`herramientas/soporte_tkt017_control.py`): MUROS vende
`480000.0000` con sugerido `410000.0000`. Donde una prueba necesita un tope ya capturado, lo deja el caso de
uso `capturar_tope` (verde desde C2) y no la propia ruta, para que el rojo de cada prueba sea el suyo y no el
de su preparación. Las respuestas se validan contra los esquemas del borrador y los valores se comparan campo
por campo; los importes viajan como cadena con cuatro decimales.

Cada rechazo comprueba el contrato de error completo, no solo el código: `tipo`, `codigo` o `motivo`,
`mensaje` literal, `detalle` con las cifras como cadena, `acciones` filtradas por el rol de quien llama, las
claves exactas del cuerpo, `correlacion_id` igual a la cabecera `X-Correlacion-Id` y la validez contra el
esquema de error del borrador. Todos comprueban además que no cambió nada en la base: ninguna fila de control,
ninguna copia, ningún asiento (salvo el `DENEGAR`, que es justo lo que un `403` debe dejar).

Rojo esperado de C3: cuando se escribió este archivo, las dos rutas, los esquemas `CapturaPresupuestoControl` y
`PresupuestoControl` y su montaje no existían, así que el enrutador respondía `404` (`NO_ENCONTRADO` con la ruta
como recurso) donde cada prueba espera `200`, `401`, `403`, `404` del recurso, `409` o `422`, y `/openapi.json`
carecía de las operaciones y de los esquemas. Lo que no exista se importa dentro del cuerpo de cada prueba y la
recolección nunca falla (riesgo `R-2`, aceptado por la persona dueña).

El MVP no tiene permiso por obra (`docs/07-especificacion-api.md`, línea 399): el caso «otra obra» de la lista
del tester de API no aplica a estas rutas y no hay prueba de IDOR por obra. Lo que sí se prueba es que el
permiso se comprueba antes que la existencia (quien no tiene rol no averigua qué líneas base existen) y que
ninguna cifra del recurso sale en un `403`.

Mutantes que este archivo debe poner en rojo: «`PUT` con `exigir_rol` antes que `verificar_origen`»
(`test_tkt017_cac05_el_origen_se_verifica_antes_que_el_rol`); «`PUT` abierto a `DIRECTOR_PROYECTOS`»
(`test_hdu001_esc23_recaptura_sin_autoridad`); «la ruta fija `confirmar_superior_a_venta` en `False`»
(`test_hdu001_esc17_tope_superior_confirmado_por_la_api`); «la ruta ignora `confirmar_superior_a_venta`»
(`test_hdu001_esc17_tope_superior_con_motivo_pero_sin_confirmar`); «`importe_tope` sin patrón» (las pruebas de
`test_tkt017_cac06_tope_mal_formado` y `test_tkt017_cac06_importe_tope_se_publica_como_cadena`); «`GET` con
`verificar_origen`» (`test_tkt017_cac01_consultar_no_exige_csrf`); «`GET` sin `exigir_rol`»
(`test_tkt017_cac01_consultar_sin_rol`).
"""

from __future__ import annotations

import copy
import inspect
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import pytest

from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    CONTRASENA_DE_PRUEBA,
    OTRO_TOKEN_CSRF,
    ROLES_DE_LECTURA,
    ROLES_SIN_LECTURA,
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador,
    cabeceras_de,
    cliente_espera_corta,  # noqa: F401
    componentes_duplicados,
    construir_aplicacion,
    contexto,  # noqa: F401
    diferencias_de_forma,
    entorno,  # noqa: F401
    esquema_de_respuesta_200,
    exigir_denegacion,
    exigir_error,
    forma_de,
    forma_de_componente,
    iniciar_sesion,
    leer,
    leer_con_par_csrf,
    llamadas,
    parametros_de,
    publicado,
    resolver,
    rutas_de,
    tipo_esperado,
    tipos_de_partida,
    validar_contra,
)
from herramientas.soporte_tkt017_control import (
    CIFRAS_CON_REDONDEO,
    LineaBaseSembrada,
    sembrar_congelada_con_cifras,
)
from herramientas.soporte_tkt017_entorno import Base, Contexto, Entorno
from tipos_base import Dinero

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, RelojDePrueba, SembrarUsuario
    from fastapi import FastAPI
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient

RUTA_LISTA = "/api/v1/lineas-base/{linea_base_id}/presupuesto-control"
RUTA_CAPTURA = "/api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}"
PATRON_DEL_TOPE = r"^\d{1,14}(\.\d{1,4})?$"

ROLES_DE_CAPTURA = ["DIRECCION_GENERAL"]
ROLES_SIN_CAPTURA = [
    "DIRECTOR_PROYECTOS",
    "COMPRAS",
    "ADMINISTRACION",
    "RESIDENTE",
    "ALMACEN",
]

MOTIVO_SUPERIOR = "Subcontrato de bastidor más caro"
MOTIVO_RECAPTURA = "Se subestimó el bastidor de los cubos de escalera"
# Sin motivo en cuatro formas: ausente, nulo, vacío y en blanco. `None` en la tupla significa «no enviarlo».
SIN_MOTIVO = [
    pytest.param("AUSENTE", id="ausente"),
    pytest.param(None, id="nulo"),
    pytest.param("", id="vacio"),
    pytest.param("   ", id="en_blanco"),
]

MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_LINEA_BASE_NO_EXISTE = "La línea base no existe."
MENSAJE_TIPO_NO_EXISTE = "El tipo de partida no existe."
MENSAJE_SIN_CONTROL = "La línea base no tiene presupuesto de control para ese tipo de partida."
MENSAJE_UN_CAMPO_INVALIDO = "La petición tiene 1 campo inválido."
MENSAJE_OBLIGATORIO = "El campo es obligatorio."
MENSAJE_FORMATO = "El valor no tiene el formato esperado."
MENSAJE_TOPE_SUPERIOR = (
    "El tope de {clave} supera su importe de venta; implicaría vender por debajo del costo tope."
)
MENSAJE_SIN_CONGELADA = (
    "La línea base está en {estado}; el tope solo se captura sobre una línea base congelada."
)
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)

# Las nueve propiedades de `PresupuestoControl` y las cuatro obligatorias del borrador.
CAMPOS_DE_CONTROL = frozenset(
    {
        "tipo_partida",
        "importe_venta",
        "importe_sugerido",
        "importe_tope",
        "capturado_por",
        "capturado_en",
        "actualizado_por",
        "actualizado_en",
        "motivo_ultimo_cambio",
    }
)
CAMPOS_OBLIGATORIOS = frozenset(
    {"tipo_partida", "importe_venta", "importe_sugerido", "importe_tope"}
)
# Lo que ningún `403` ni ningún `401` debe dejar ver de la línea base sembrada (`CIFRAS_ESCENARIO`).
CIFRAS_DEL_ESCENARIO = [
    "480000",
    "410000",
    "300000",
    "179999",
    "120000",
    "95000",
    "450000",
    "470000",
    "500000",
    "600000",
]

_SQL_CONTROL = (
    "SELECT importe_tope, importe_sugerido, capturado_por_id, capturado_en, actualizado_por_id, "
    "actualizado_en, motivo_ultimo_cambio FROM presupuesto_control WHERE id = %s"
)
_SQL_ASIENTOS = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
    "obra_id, datos_antes, datos_despues FROM bitacora WHERE accion <> 'DENEGAR' "
    "ORDER BY ocurrido_en, accion::text"
)
_SQL_RETENER_CONTROL = "SELECT id FROM presupuesto_control WHERE linea_base_id = %s AND tipo_partida_id = %s FOR UPDATE"


# --------------------------------------------------------------------------- rutas y llamadas


def ruta_lista(linea_base_id: uuid.UUID | str) -> str:
    return RUTA_LISTA.replace("{linea_base_id}", str(linea_base_id))


def ruta_captura(linea_base_id: uuid.UUID | str, tipo_partida_id: uuid.UUID | str) -> str:
    return RUTA_CAPTURA.replace("{linea_base_id}", str(linea_base_id)).replace(
        "{tipo_partida_id}", str(tipo_partida_id)
    )


def capturar_por_http(
    cliente: TestClient,
    linea_base_id: uuid.UUID | str,
    tipo_partida_id: uuid.UUID | str,
    sesion_id: uuid.UUID | None,
    cuerpo: Mapping[str, Any],
    *,
    cookie_csrf: str | None = TOKEN_CSRF,
    cabecera_csrf: str | None = TOKEN_CSRF,
) -> Any:
    """`PUT` de la captura con el par CSRF indicado; por omisión, uno válido."""
    return cliente.put(
        ruta_captura(linea_base_id, tipo_partida_id),
        json=dict(cuerpo),
        headers=cabeceras_de(sesion_id, cookie_csrf, cabecera_csrf),
    )


def capturar_muros(
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    sesion: Sesion | None,
    cuerpo: Mapping[str, Any],
    **par_csrf: str | None,
) -> Any:
    return capturar_por_http(
        cliente,
        sembrada.linea_base_id,
        sembrada.tipos["MUROS"],
        None if sesion is None else sesion.sesion_id,
        cuerpo,
        **par_csrf,
    )


def con_motivo(cuerpo: dict[str, Any], motivo: str | None) -> dict[str, Any]:
    """El cuerpo con el `motivo` indicado; `"AUSENTE"` es no enviar el campo."""
    return cuerpo if motivo == "AUSENTE" else {**cuerpo, "motivo": motivo}


# --------------------------------------------------------------------------- el entorno


@pytest.fixture
def sembrada(entorno: Entorno) -> LineaBaseSembrada:
    """MUROS vende 480000.0000 con sugerido 410000.0000 y tope nulo; hay cuatro filas de control."""
    return sembrar_congelada_con_cifras(entorno)


@pytest.fixture
def direccion(abrir_sesion: Callable[..., Sesion]) -> Sesion:
    """Quien captura el tope: una persona de Dirección General con nombre."""
    return abrir_sesion(("DIRECCION_GENERAL",), nombre="Laura Méndez")


@pytest.fixture
def otra_direccion(abrir_sesion: Callable[..., Sesion]) -> Sesion:
    """Otra persona de Dirección General, para distinguir quién capturó de quién recapturó."""
    return abrir_sesion(("DIRECCION_GENERAL",), nombre="Mateo Ríos")


def dejar_tope(
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    quien: Sesion,
    importe: str,
    *,
    clave: str = "MUROS",
    motivo: str | None = None,
) -> None:
    """Deja un tope capturado con el caso de uso de C2 (no con la ruta bajo prueba)."""
    from cimenta.presupuesto.aplicacion.presupuesto_control import capturar_tope

    capturar_tope(
        contexto(),
        linea_base_id=sembrada.linea_base_id,
        tipo_partida_id=sembrada.tipos[clave],
        importe_tope=Dinero(importe),
        motivo=motivo,
        confirmar_superior_a_venta=False,
        usuario_id=quien.usuario_id,
    )


@pytest.fixture
def con_tope(
    contexto: Contexto, sembrada: LineaBaseSembrada, direccion: Sesion
) -> LineaBaseSembrada:
    """`HDU-001`: el tope de MUROS ya se capturó en 450000.0000 por `direccion`."""
    dejar_tope(contexto, sembrada, direccion, "450000.0000")
    return sembrada


def _estado_de_negocio(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: la foto del soporte más las obras, las líneas base, las copias y los
    controles completos, con todas sus columnas, y la bitácora sin los asientos `DENEGAR` (el `403` debe dejar
    uno; cualquier otro asiento sería un cambio)."""
    foto = dict(base.foto())
    conteos = dict(cast("dict[str, int]", foto.pop("filas")))
    conteos.pop("bitacora")
    return {
        "foto": foto,
        "conteos": conteos,
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "copias": base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        "controles": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
        "bitacora": base.filas("SELECT * FROM bitacora WHERE accion <> 'DENEGAR' ORDER BY id"),
    }


def _tope(base: Base, sembrada: LineaBaseSembrada, clave: str = "MUROS") -> str | None:
    filas = base.filas(_SQL_CONTROL, sembrada.controles[clave])
    assert len(filas) == 1
    valor = filas[0][0]
    return None if valor is None else str(valor)


def _acciones_de_bitacora(base: Base) -> list[str]:
    return [fila[0] for fila in base.filas(_SQL_ASIENTOS)]


def _leida(fila: Mapping[str, Any]) -> dict[str, Any]:
    """Una fila de `PresupuestoControl` con los nulos explícitos y las fechas como `datetime` con zona.

    Falla si la fila trae una propiedad que el borrador no declara o le falta una obligatoria. Quien
    escribe la ruta decide si publica los nulos o los omite: el contrato admite las dos formas.
    """
    assert set(fila) <= CAMPOS_DE_CONTROL, sorted(set(fila) - CAMPOS_DE_CONTROL)
    assert set(fila) >= CAMPOS_OBLIGATORIOS, sorted(CAMPOS_OBLIGATORIOS - set(fila))
    resultado: dict[str, Any] = {campo: fila.get(campo) for campo in CAMPOS_DE_CONTROL}
    for campo in ("capturado_en", "actualizado_en"):
        if resultado[campo] is not None:
            resultado[campo] = datetime.fromisoformat(str(resultado[campo]))
    return resultado


def _esperada(base: Base, clave: str, venta: str, sugerido: str, **resto: Any) -> dict[str, Any]:
    """La fila de `PresupuestoControl` con todos sus campos; lo no indicado es nulo."""
    return {
        "tipo_partida": tipo_esperado(base, clave),
        "importe_venta": venta,
        "importe_sugerido": sugerido,
        "importe_tope": None,
        "capturado_por": None,
        "capturado_en": None,
        "actualizado_por": None,
        "actualizado_en": None,
        "motivo_ultimo_cambio": None,
        **resto,
    }


def _quien(sesion: Sesion, nombre: str) -> dict[str, str]:
    return {"id": str(sesion.usuario_id), "nombre": nombre}


def _control_de_respuesta(respuesta: Any) -> dict[str, Any]:
    """Una respuesta `200` de la captura: JSON, válida contra `PresupuestoControl`, ya normalizada."""
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("PresupuestoControl", cuerpo)
    return _leida(cuerpo)


def _lista_de_respuesta(respuesta: Any) -> list[dict[str, Any]]:
    """Una respuesta `200` de la lectura: un arreglo de `PresupuestoControl`, cada elemento válido."""
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, list)
    for fila in cuerpo:
        validar_contra("PresupuestoControl", fila)
    return [_leida(fila) for fila in cuerpo]


def _exigir_validacion(respuesta: Any, campo: str, codigo: str, mensaje: str) -> None:
    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": MENSAJE_UN_CAMPO_INVALIDO,
            "errores": [{"campo": campo, "codigo": codigo, "mensaje": mensaje}],
        },
        esquema="ErrorValidacion",
    )


def _exigir_tope_superior(
    respuesta: Any, sembrada: LineaBaseSembrada, importe_tope: str, *, con_accion: bool
) -> None:
    """El `409` de `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` con su contrato completo."""
    acciones = (
        [
            {
                "clave": "CONFIRMAR_TOPE_SUPERIOR",
                "metodo": "PUT",
                "ruta": ruta_captura(sembrada.linea_base_id, sembrada.tipos["MUROS"]),
            }
        ]
        if con_accion
        else []
    )
    exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR",
            "mensaje": MENSAJE_TOPE_SUPERIOR.format(clave="MUROS"),
            "detalle": {
                "tipo_partida": "MUROS",
                "importe_venta": "480000.0000",
                "importe_tope": importe_tope,
            },
            "acciones": acciones,
        },
        esquema="ErrorConflictoEstado",
    )


def _sin_cifras(respuesta: Any, *extra: str) -> None:
    """Ni las cifras del escenario ni los identificadores aparecen en un rechazo de permiso.

    El `correlacion_id` es un UUID aleatorio: puede contener «5000» o «9500» por azar. Se quita del texto
    antes de buscar las cifras; el resto del cuerpo queda intacto.
    """
    texto = respuesta.text.replace(respuesta.headers[CABECERA_CORRELACION], "")
    assert texto != respuesta.text, "La correlación debe aparecer en el cuerpo para poder quitarla"
    for cifra_o_nombre in [*CIFRAS_DEL_ESCENARIO, *extra]:
        assert cifra_o_nombre not in texto, cifra_o_nombre
    assert "detalle" not in respuesta.json()


# --------------------------------------------------------------------------- TC-C01 · CA-C1 esc. 1


@pytest.mark.parametrize("rol", ROLES_DE_LECTURA)
def test_hdu001_esc15_consultar_las_cuatro_bolsas(
    rol: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 15 · TC-C01 · CA-C1 esc. 1 · PA-03 — los tres roles leen cuatro filas, con la venta del tipo, el sugerido y el tope nulo.

    El importe de venta del tipo es la suma de los importes **ya cuantizados** de sus copias congeladas:
    PLAFONES tiene dos apariciones de `0.5000 × 0.0001`, cada una cuantizada a `0.0001`, y vale `0.0002`
    (sumar sin cuantizar daría `0.0001`). Las cuatro suman exactamente `linea_base.importe_venta`. Las filas
    salen por `tipo_partida.id` y los importes como cadena de cuatro decimales. Sin cabecera ni cookie CSRF:
    es un `GET`; no escribe en la bitácora.
    """
    sembrada = sembrar_congelada_con_cifras(entorno, CIFRAS_CON_REDONDEO)
    lector = abrir_sesion((rol,))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(cliente, ruta_lista(sembrada.linea_base_id), lector.sesion_id)

    filas = _lista_de_respuesta(respuesta)
    assert [fila["tipo_partida"] for fila in filas] == [
        {"id": str(identificador), "clave": clave, "nombre": nombre}
        for identificador, clave, nombre in tipos_de_partida(base)
    ]
    assert {f["tipo_partida"]["clave"]: f["importe_venta"] for f in filas} == {
        "MUROS": "480000.0000",
        "PLAFONES_Y_CAJILLOS": "0.0002",
        "ENCHAPES": "12345.6789",
        "GENERALES": "0.0000",
    }
    assert {f["tipo_partida"]["clave"]: f["importe_sugerido"] for f in filas} == {
        "MUROS": "410000.0000",
        "PLAFONES_Y_CAJILLOS": "0.0001",
        "ENCHAPES": "10000.0000",
        "GENERALES": "0.0000",
    }
    suma = sum((Decimal(f["importe_venta"]) for f in filas), start=Decimal("0.0000"))
    assert str(suma) == "492345.6791"
    assert base.filas(
        "SELECT importe_venta FROM linea_base WHERE id = %s", sembrada.linea_base_id
    ) == [(str(suma),)]
    assert [
        (
            f["importe_tope"],
            f["capturado_por"],
            f["capturado_en"],
            f["actualizado_por"],
            f["actualizado_en"],
            f["motivo_ultimo_cambio"],
        )
        for f in filas
    ] == [(None, None, None, None, None, None)] * 4
    for texto in (f["importe_venta"] for f in respuesta.json()):
        assert len(texto.rsplit(".", 1)[1]) == 4
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes, (
        "Una lectura no escribe en la bitácora"
    )


def test_hdu001_esc15_consultar_el_control_de_un_borrador_devuelve_lista_vacia(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 15 · TC-C01 · CA-C1 · P-9 — una línea base en `BORRADOR` no tiene presupuesto de control: `200` con `[]`."""
    borrador_id = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id, version=1)
    lector = abrir_sesion(("DIRECCION_GENERAL",))

    respuesta = leer(cliente, ruta_lista(borrador_id), lector.sesion_id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == []
    assert base.filas("SELECT count(*) FROM presupuesto_control") == [(0,)]


def test_hdu001_esc22_consultar_el_control_recapturado(
    base: Base,
    cliente: TestClient,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    otra_direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 22 · TC-C01 · CA-C1 · CA-C4 — la lectura trae el tope, a quién capturó y a quién recapturó, con su nombre, y el motivo.

    Laura captura `450000.0000`; diez minutos después Mateo lo recaptura en `470000.0000` con motivo
    (los dos con el caso de uso de C2). Los otros tres tipos siguen con todo en nulo.
    """
    primera_vez = reloj_de_prueba.ahora
    dejar_tope(contexto, sembrada, direccion, "450000.0000")
    reloj_de_prueba.avanzar(timedelta(minutes=10))
    from cimenta.presupuesto.aplicacion.presupuesto_control import capturar_tope

    capturar_tope(
        contexto(),
        linea_base_id=sembrada.linea_base_id,
        tipo_partida_id=sembrada.tipos["MUROS"],
        importe_tope=Dinero("470000.0000"),
        motivo=MOTIVO_RECAPTURA,
        confirmar_superior_a_venta=False,
        usuario_id=otra_direccion.usuario_id,
    )
    lector = abrir_sesion(("COMPRAS",))

    filas = {
        f["tipo_partida"]["clave"]: f
        for f in _lista_de_respuesta(
            leer(cliente, ruta_lista(sembrada.linea_base_id), lector.sesion_id)
        )
    }

    assert filas["MUROS"] == _esperada(
        base,
        "MUROS",
        "480000.0000",
        "410000.0000",
        importe_tope="470000.0000",
        capturado_por=_quien(direccion, "Laura Méndez"),
        capturado_en=primera_vez,
        actualizado_por=_quien(otra_direccion, "Mateo Ríos"),
        actualizado_en=reloj_de_prueba.ahora,
        motivo_ultimo_cambio=MOTIVO_RECAPTURA,
    )
    for clave in ("PLAFONES_Y_CAJILLOS", "ENCHAPES", "GENERALES"):
        assert filas[clave]["importe_tope"] is None
        assert filas[clave]["capturado_por"] is None
        assert filas[clave]["actualizado_por"] is None


# --------------------------------------------------------------------------- TC-C02 · CA-C1 esc. 2


@pytest.mark.parametrize("rol", ROLES_SIN_LECTURA)
def test_tkt017_cac01_consultar_sin_rol(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    sembrada: LineaBaseSembrada,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-C02 · CA-C1 esc. 2 · RN-04 — sin `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS` ni `COMPRAS`: `403` `ROL_INSUFICIENTE`, sin importes, con un `DENEGAR`.

    Cuerpo exacto (sin `detalle`), `roles_requeridos` en el orden de `x-roles` del borrador. Ni las cifras
    del escenario ni los identificadores de la línea base y de los tipos aparecen en la respuesta; el único
    asiento nuevo es el `DENEGAR` a nombre de quien llamó, con `GET`, la ruta y los roles.
    """
    operacion = borrador()["paths"]["/lineas-base/{linea_base_id}/presupuesto-control"]["get"]
    assert operacion["operationId"] == "listar_presupuesto_control"
    assert operacion["x-roles"] == ROLES_DE_LECTURA, "El borrador debe fijar los tres roles"
    usuario = abrir_sesion((rol,))
    antes = _estado_de_negocio(base)
    ruta = ruta_lista(sembrada.linea_base_id)

    respuesta = leer(cliente, ruta, usuario.sesion_id)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_LECTURA,
        },
        esquema="ErrorPermiso",
    )
    _sin_cifras(
        respuesta,
        str(sembrada.linea_base_id),
        *(str(tipo) for tipo in sembrada.tipos.values()),
        "importe_venta",
        "importe_tope",
    )
    assert _estado_de_negocio(base) == antes
    exigir_denegacion(
        base,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="GET",
        ruta=ruta,
        roles_requeridos=ROLES_DE_LECTURA,
    )


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt017_cac01_consultar_sin_sesion(
    sesion: str, base: Base, cliente: TestClient, sembrada: LineaBaseSembrada
) -> None:
    """TC-C02 · CA-C1 · CA-R1 — sin sesión (o con una que no existe): `401` `SIN_SESION`, sin asiento y sin ver nada del recurso."""
    antes = _estado_de_negocio(base)
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(
        cliente,
        ruta_lista(sembrada.linea_base_id),
        uuid.uuid4() if sesion == "sesion_inexistente" else None,
    )

    exigir_error(
        respuesta,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    for cifra in CIFRAS_DEL_ESCENARIO:
        assert cifra not in respuesta.text.replace(respuesta.headers[CABECERA_CORRELACION], "")
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes, (
        "Una denegación anónima no se asienta en la bitácora"
    )


def test_tkt017_cac01_consultar_linea_base_inexistente(
    base: Base, cliente: TestClient, abrir_sesion: Callable[..., Sesion]
) -> None:
    """TC-C02 · CA-C1 · CA-C6 esc. 3 — la línea base no existe: `404` `NO_ENCONTRADO` con su `recurso` y su mensaje, no la ruta. No se asienta nada."""
    lector = abrir_sesion(("COMPRAS",))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(cliente, ruta_lista(uuid.uuid4()), lector.sesion_id)

    exigir_error(
        respuesta,
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": MENSAJE_LINEA_BASE_NO_EXISTE,
            "recurso": "linea_base",
        },
        esquema="ErrorNoEncontrado",
    )
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes


def test_tkt017_cac01_el_rol_se_comprueba_antes_que_la_existencia(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-C02 · CA-C1 · conv-seguridad — quien no tiene rol recibe `403` aunque la línea base no exista: no se averigua qué existe."""
    usuario = abrir_sesion(("RESIDENTE",))
    ruta = ruta_lista(uuid.uuid4())

    respuesta = leer(cliente, ruta, usuario.sesion_id)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_LECTURA,
        },
        esquema="ErrorPermiso",
    )
    exigir_denegacion(
        base,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="GET",
        ruta=ruta,
        roles_requeridos=ROLES_DE_LECTURA,
    )


def test_tkt017_cac01_consultar_no_exige_csrf(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    sembrada: LineaBaseSembrada,
) -> None:
    """TC-C02 · CA-R1 · RNF-05 — es un `GET`: un par CSRF que no coincide no lo rechaza ni deja un `DENEGAR`.

    Mutante «`GET` con `verificar_origen`»: respondería `403` `ORIGEN_NO_VERIFICADO`.
    """
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer_con_par_csrf(
        cliente,
        ruta_lista(sembrada.linea_base_id),
        lector.sesion_id,
        cookie_csrf=TOKEN_CSRF,
        cabecera_csrf=OTRO_TOKEN_CSRF,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert base.filas("SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == [(0,)]


def test_tkt017_cac01_consultar_con_linea_base_mal_formada(
    cliente: TestClient, abrir_sesion: Callable[..., Sesion]
) -> None:
    """TC-C15 · CA-C6 — un identificador que no es UUID en la ruta de lectura: `422` `VALIDACION` con `FORMATO` en `linea_base_id`."""
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer(cliente, ruta_lista("no-es-un-uuid"), lector.sesion_id)

    _exigir_validacion(respuesta, "linea_base_id", "FORMATO", MENSAJE_FORMATO)


# --------------------------------------------------------------------------- captura · CA-C2 y CA-C4 por la API


def test_hdu001_esc15_captura_por_la_api(
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 15 · CA-C2 · RN-03 · PA-03 — la primera captura de 450000.0000 sin motivo responde `200` con la fila ya guardada.

    La respuesta es un `PresupuestoControl` del borrador: tope en cadena de cuatro decimales, `capturado_por`
    como `UsuarioResumen` con el nombre, `capturado_en` con zona y el sugerido intacto; no hay recaptura. La
    base guarda lo mismo, los otros tres controles no se tocan y el único asiento es un `CREAR` de la fila de
    control sin regla de negocio, con el valor capturado: una consulta por `RN-03` no lo devuelve (M-C6).
    """
    control = sembrada.controles["MUROS"]
    ajenos_antes = base.filas(
        "SELECT * FROM presupuesto_control WHERE id <> %s ORDER BY id", control
    )

    respuesta = capturar_muros(cliente, sembrada, direccion, {"importe_tope": "450000.0000"})

    fila = _control_de_respuesta(respuesta)
    assert fila == _esperada(
        base,
        "MUROS",
        "480000.0000",
        "410000.0000",
        importe_tope="450000.0000",
        capturado_por=_quien(direccion, "Laura Méndez"),
        capturado_en=reloj_de_prueba.ahora,
    )
    assert base.filas(_SQL_CONTROL, control) == [
        (
            "450000.0000",
            "410000.0000",
            direccion.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            None,
        )
    ]
    assert (
        base.filas("SELECT * FROM presupuesto_control WHERE id <> %s ORDER BY id", control)
        == ajenos_antes
    )
    assert base.filas(_SQL_ASIENTOS) == [
        (
            "CREAR",
            "presupuesto_control",
            control,
            direccion.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "450000.0000"},
        )
    ]
    assert base.filas("SELECT count(*) FROM bitacora WHERE regla_negocio = 'RN-03'") == [(0,)]


def test_hdu001_esc15_captura_ignora_los_campos_que_no_son_del_cuerpo(
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    otra_direccion: Sesion,
) -> None:
    """HDU-001 esc. 15 · CA-C2 · conv-seguridad — un cuerpo con campos de la fila (`importe_sugerido`, `capturado_por`…) no los cambia.

    El resto del API ignora los campos que el DTO de entrada no declara (`Motivo`, de la congelación): aquí
    ninguno de ellos llega a la fila. `capturado_por` sigue siendo quien llama, no quien dice el cuerpo, y el
    sugerido y el importe de venta siguen siendo los del congelado.
    """
    respuesta = capturar_muros(
        cliente,
        sembrada,
        direccion,
        {
            "importe_tope": "450000.0000",
            "importe_sugerido": "1.0000",
            "importe_venta": "1.0000",
            "capturado_por": str(otra_direccion.usuario_id),
            "actualizado_por": str(otra_direccion.usuario_id),
        },
    )

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_sugerido"] == "410000.0000"
    assert fila["importe_venta"] == "480000.0000"
    assert fila["capturado_por"] == _quien(direccion, "Laura Méndez")
    assert fila["actualizado_por"] is None
    assert base.filas(
        "SELECT importe_sugerido, capturado_por_id, actualizado_por_id FROM presupuesto_control "
        "WHERE id = %s",
        sembrada.controles["MUROS"],
    ) == [("410000.0000", direccion.usuario_id, None)]


def test_hdu001_esc22_recaptura_por_la_api(
    base: Base,
    cliente: TestClient,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    otra_direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 22 · CA-C4 · RN-03 · RN-04 — recapturar 450000.0000 a 470000.0000 con motivo deja quién, cuándo y por qué.

    Laura capturó (caso de uso) y diez minutos después Mateo recaptura por la ruta. La respuesta conserva
    quién capturó y cuándo, y fija quién recapturó, cuándo y el motivo. El asiento es `RECAPTURAR` con
    `RN-03`, el valor anterior, el nuevo y el motivo, y aparece en una consulta por `RN-03` (M-C3). Una
    lectura posterior devuelve la misma fila.
    """
    control = sembrada.controles["MUROS"]
    primera_vez = reloj_de_prueba.ahora
    dejar_tope(contexto, sembrada, direccion, "450000.0000")
    reloj_de_prueba.avanzar(timedelta(minutes=10))

    respuesta = capturar_muros(
        cliente,
        sembrada,
        otra_direccion,
        {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
    )

    fila = _control_de_respuesta(respuesta)
    assert fila == _esperada(
        base,
        "MUROS",
        "480000.0000",
        "410000.0000",
        importe_tope="470000.0000",
        capturado_por=_quien(direccion, "Laura Méndez"),
        capturado_en=primera_vez,
        actualizado_por=_quien(otra_direccion, "Mateo Ríos"),
        actualizado_en=reloj_de_prueba.ahora,
        motivo_ultimo_cambio=MOTIVO_RECAPTURA,
    )
    assert base.filas(_SQL_CONTROL, control) == [
        (
            "470000.0000",
            "410000.0000",
            direccion.usuario_id,
            primera_vez,
            otra_direccion.usuario_id,
            reloj_de_prueba.ahora,
            MOTIVO_RECAPTURA,
        )
    ]
    assert base.filas(
        "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, "
        "motivo, obra_id, datos_antes, datos_despues FROM bitacora WHERE accion = 'RECAPTURAR'"
    ) == [
        (
            "RECAPTURAR",
            "presupuesto_control",
            control,
            otra_direccion.usuario_id,
            reloj_de_prueba.ahora,
            "RN-03",
            MOTIVO_RECAPTURA,
            entorno.obra_id,
            {"importe_tope": "450000.0000"},
            {"importe_tope": "470000.0000"},
        )
    ]
    assert base.filas("SELECT count(*) FROM bitacora WHERE regla_negocio = 'RN-03'") == [(1,)]
    leida = {
        f["tipo_partida"]["clave"]: f
        for f in _lista_de_respuesta(
            leer(cliente, ruta_lista(sembrada.linea_base_id), direccion.sesion_id)
        )
    }
    assert leida["MUROS"] == fila


def test_hdu001_esc22_quien_suma_direccion_a_otro_rol_captura(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    sembrada: LineaBaseSembrada,
) -> None:
    """HDU-001 esc. 22 · CA-C4 · RN-04 — el permiso es la unión de los roles: quien además de `COMPRAS` tiene `DIRECCION_GENERAL` captura."""
    usuario = abrir_sesion(("COMPRAS", "DIRECCION_GENERAL"))

    respuesta = capturar_muros(cliente, sembrada, usuario, {"importe_tope": "450000.0000"})

    assert respuesta.status_code == 200, respuesta.text
    assert _tope(base, sembrada) == "450000.0000"


@pytest.mark.parametrize("motivo", ["", "   "])
def test_hdu001_esc15_primera_captura_con_motivo_en_blanco(
    motivo: str,
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 15 · CA-C2 · RN-03 — la primera captura no exige motivo: `motivo: ""` o `"   "` responde `200`, no `422` `OBLIGATORIO`.

    Un formulario envía el campo aunque el usuario no lo llene. Con un tope válido (`450000.0000`, por debajo
    de la venta de `480000.0000`) la fila queda con `motivo_ultimo_cambio` nulo y el asiento `CREAR` sin regla
    y sin motivo. La recaptura y el tope superior confirmado con el motivo en blanco siguen dando `422`
    `OBLIGATORIO` (`test_hdu001_esc23_recaptura_sin_motivo` y `test_hdu001_esc17_confirmacion_sin_motivo`).
    """
    respuesta = capturar_muros(
        cliente, sembrada, direccion, {"importe_tope": "450000.0000", "motivo": motivo}
    )

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == "450000.0000"
    assert fila["motivo_ultimo_cambio"] is None
    assert base.filas(_SQL_CONTROL, sembrada.controles["MUROS"]) == [
        (
            "450000.0000",
            "410000.0000",
            direccion.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            None,
        )
    ]
    assert base.filas(_SQL_ASIENTOS) == [
        (
            "CREAR",
            "presupuesto_control",
            sembrada.controles["MUROS"],
            direccion.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "450000.0000"},
        )
    ]


# --------------------------------------------------------------------------- TC-C04 a TC-C06 · CA-C3


def test_hdu001_esc17_tope_superior_sin_confirmar(
    base: Base, cliente: TestClient, sembrada: LineaBaseSembrada, direccion: Sesion
) -> None:
    """HDU-001 esc. 17 · TC-C04 · CA-C3 esc. 1 · RN-03 — un tope de 500000.0000 contra una venta de 480000.0000 se detiene con `409`.

    `409` `CONFLICTO` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` con el tipo, el importe de venta **del tipo**
    (no el de la línea base, que es `600000.0000`) y el tope como cadenas de cuatro decimales. La acción
    `CONFIRMAR_TOPE_SUPERIOR` (`PUT` a la misma ruta) la ve Dirección General. El tope sigue nulo y no hay
    asiento.
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(cliente, sembrada, direccion, {"importe_tope": "500000.0000"})

    _exigir_tope_superior(respuesta, sembrada, "500000.0000", con_accion=True)
    assert _tope(base, sembrada) is None
    assert base.filas(_SQL_ASIENTOS) == []
    assert _estado_de_negocio(base) == antes


def test_hdu001_esc17_tope_superior_con_motivo_pero_sin_confirmar(
    base: Base, cliente: TestClient, sembrada: LineaBaseSembrada, direccion: Sesion
) -> None:
    """HDU-001 esc. 17 · TC-C04 · CA-C3 · RN-03 — el motivo no sustituye a la confirmación: sin `confirmar_superior_a_venta` el mismo `409`.

    Mutante «la ruta ignora `confirmar_superior_a_venta`»: guardaría el tope. Con `false` explícito y con el
    campo ausente el resultado es el mismo.
    """
    antes = _estado_de_negocio(base)

    explicito = capturar_muros(
        cliente,
        sembrada,
        direccion,
        {
            "importe_tope": "500000.0000",
            "motivo": MOTIVO_SUPERIOR,
            "confirmar_superior_a_venta": False,
        },
    )
    omitido = capturar_muros(
        cliente, sembrada, direccion, {"importe_tope": "500000.0000", "motivo": MOTIVO_SUPERIOR}
    )

    _exigir_tope_superior(explicito, sembrada, "500000.0000", con_accion=True)
    _exigir_tope_superior(omitido, sembrada, "500000.0000", con_accion=True)
    assert _estado_de_negocio(base) == antes


def test_hdu001_esc17_tope_superior_confirmado_por_la_api(
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 17 · TC-C07 · CA-C3 esc. 3 · RN-03 — con `confirmar_superior_a_venta: true` y motivo, el tope de 500000.0000 se guarda.

    La respuesta lleva el tope y el motivo en la propia fila; el asiento `CREAR` de esa primera captura
    lleva el motivo y sigue sin regla. Mutante «la ruta fija `confirmar_superior_a_venta` en `False`».
    """
    respuesta = capturar_muros(
        cliente,
        sembrada,
        direccion,
        {
            "importe_tope": "500000.0000",
            "motivo": MOTIVO_SUPERIOR,
            "confirmar_superior_a_venta": True,
        },
    )

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == "500000.0000"
    assert fila["motivo_ultimo_cambio"] == MOTIVO_SUPERIOR
    assert fila["capturado_por"] == _quien(direccion, "Laura Méndez")
    assert base.filas(_SQL_ASIENTOS) == [
        (
            "CREAR",
            "presupuesto_control",
            sembrada.controles["MUROS"],
            direccion.usuario_id,
            reloj_de_prueba.ahora,
            None,
            MOTIVO_SUPERIOR,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "500000.0000"},
        )
    ]


@pytest.mark.parametrize(
    "valor",
    [
        pytest.param("yes", id="yes"),
        pytest.param("true", id="true_como_cadena"),
        pytest.param(1, id="uno"),
        pytest.param(0, id="cero"),
        pytest.param("on", id="on"),
        pytest.param(None, id="nulo"),
    ],
)
def test_tkt017_cac06_confirmar_superior_a_venta_solo_admite_booleanos(
    valor: object,
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C3 · CA-C6 · RN-03 — la confirmación del tope superior solo admite un booleano JSON: lo demás es `422` `FORMATO`.

    Pydantic, por omisión, coacciona `"yes"`, `"on"`, `"true"`, `1` y `0` a booleano. Con un tope de
    500000.0000 (superior a la venta de 480000.0000) y motivo, un valor laxo saltaría el `409`
    `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR`: la confirmación es una decisión explícita de Dirección y no puede
    nacer de una coerción. El rechazo es sobre el campo `confirmar_superior_a_venta`; el tope sigue nulo y no
    cambia ninguna fila ni asiento.
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente,
        sembrada,
        direccion,
        {
            "importe_tope": "500000.0000",
            "motivo": MOTIVO_SUPERIOR,
            "confirmar_superior_a_venta": valor,
        },
    )

    _exigir_validacion(respuesta, "confirmar_superior_a_venta", "FORMATO", MENSAJE_FORMATO)
    assert _tope(base, sembrada) is None
    assert base.filas(_SQL_ASIENTOS) == []
    assert _estado_de_negocio(base) == antes


def test_hdu001_esc17_tope_igual_a_la_venta_no_pide_confirmacion(
    base: Base, cliente: TestClient, sembrada: LineaBaseSembrada, direccion: Sesion
) -> None:
    """HDU-001 esc. 17 · TC-C05 · CA-C3 · RN-03 — un tope igual al importe de venta del tipo no supera nada (borde, M-C1).

    `480000.0000` sin confirmar y sin motivo responde `200` y es una primera captura (`CREAR`).
    """
    respuesta = capturar_muros(cliente, sembrada, direccion, {"importe_tope": "480000.0000"})

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == "480000.0000"
    assert _tope(base, sembrada) == "480000.0000"
    assert _acciones_de_bitacora(base) == ["CREAR"]


@pytest.mark.parametrize("motivo", SIN_MOTIVO)
def test_hdu001_esc17_confirmacion_sin_motivo(
    motivo: str | None,
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """HDU-001 esc. 17 · TC-C06 · CA-C3 esc. 2 · RN-04 — confirmar que el tope supera la venta sin motivo es `422` `OBLIGATORIO` en `motivo`.

    Ausente, nulo, vacío y en blanco dan el mismo error en el campo `motivo`; el tope sigue nulo y no hay
    asiento.
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente,
        sembrada,
        direccion,
        con_motivo({"importe_tope": "500000.0000", "confirmar_superior_a_venta": True}, motivo),
    )

    _exigir_validacion(respuesta, "motivo", "OBLIGATORIO", MENSAJE_OBLIGATORIO)
    assert _tope(base, sembrada) is None
    assert base.filas(_SQL_ASIENTOS) == []
    assert _estado_de_negocio(base) == antes


# --------------------------------------------------------------------------- TC-C11 y TC-C12 · CA-C5


@pytest.mark.parametrize("rol", ROLES_SIN_CAPTURA)
def test_hdu001_esc23_recaptura_sin_autoridad(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    con_tope: LineaBaseSembrada,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 23 · TC-C11 · CA-C5 esc. 1 · RN-04 — sin `DIRECCION_GENERAL`: `403` `ROL_INSUFICIENTE` sin `detalle`, un `DENEGAR` y el tope sigue en 450000.0000.

    `DIRECTOR_PROYECTOS` es el del criterio; `COMPRAS`, `ADMINISTRACION`, `RESIDENTE` y `ALMACEN` confirman que
    la ruta no admite a nadie más. Ni las cifras del escenario ni los identificadores aparecen en el cuerpo, y
    la recaptura (con motivo y un valor distinto) no cambia nada.
    """
    operacion = borrador()["paths"][
        "/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}"
    ]["put"]
    assert operacion["operationId"] == "capturar_presupuesto_control"
    assert operacion["x-roles"] == ROLES_DE_CAPTURA, "El borrador debe fijar solo DIRECCION_GENERAL"
    usuario = abrir_sesion((rol,))
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente,
        con_tope,
        usuario,
        {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
    )

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_CAPTURA,
        },
        esquema="ErrorPermiso",
    )
    _sin_cifras(respuesta, str(con_tope.linea_base_id), *(str(t) for t in con_tope.tipos.values()))
    assert _tope(base, con_tope) == "450000.0000"
    assert _acciones_de_bitacora(base) == ["CREAR"], "No hay RECAPTURAR"
    assert _estado_de_negocio(base) == antes
    exigir_denegacion(
        base,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="PUT",
        ruta=ruta_captura(con_tope.linea_base_id, con_tope.tipos["MUROS"]),
        roles_requeridos=ROLES_DE_CAPTURA,
    )


@pytest.mark.parametrize("motivo", SIN_MOTIVO)
def test_hdu001_esc23_recaptura_sin_motivo(
    motivo: str | None,
    base: Base,
    cliente: TestClient,
    con_tope: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """HDU-001 esc. 23 · TC-C12 · CA-C5 esc. 2 · RN-04 — recapturar sin motivo es `422` `OBLIGATORIO` en `motivo`; el tope sigue en 450000.0000.

    Ausente, nulo, vacío y en blanco. No hay asiento `RECAPTURAR`: la bitácora solo trae el `CREAR` de la
    primera captura, y la fila de control queda idéntica (ni `actualizado_por` ni `actualizado_en`).
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente, con_tope, direccion, con_motivo({"importe_tope": "470000.0000"}, motivo)
    )

    _exigir_validacion(respuesta, "motivo", "OBLIGATORIO", MENSAJE_OBLIGATORIO)
    assert _tope(base, con_tope) == "450000.0000"
    assert _acciones_de_bitacora(base) == ["CREAR"]
    assert base.filas("SELECT count(*) FROM bitacora WHERE accion = 'RECAPTURAR'") == [(0,)]
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt017_cac05_recaptura_sin_sesion(
    sesion: str, base: Base, cliente: TestClient, con_tope: LineaBaseSembrada
) -> None:
    """TC-C11 · CA-C5 · CA-R1 — sin sesión (o con una que no existe), aun con un par CSRF válido: `401` `SIN_SESION`, sin asiento y sin cambios."""
    antes = _estado_de_negocio(base)
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")
    sesion_id = uuid.uuid4() if sesion == "sesion_inexistente" else None

    respuesta = capturar_por_http(
        cliente,
        con_tope.linea_base_id,
        con_tope.tipos["MUROS"],
        sesion_id,
        {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
    )

    exigir_error(
        respuesta,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes, (
        "Una denegación anónima no se asienta en la bitácora"
    )


@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt017_cac05_recaptura_sin_par_csrf(
    cookie: str | None,
    cabecera: str | None,
    base: Base,
    cliente: TestClient,
    con_tope: LineaBaseSembrada,
    direccion: Sesion,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-C11 · CA-C5 · CA-R1 · RNF-05 — sin el doble envío del token: `403` `ORIGEN_NO_VERIFICADO` y un `DENEGAR`; no se captura nada.

    Las cuatro combinaciones de `CA-9` de TKT-057. Aunque quien llama sea Dirección General con un cuerpo
    válido, la petición no se ejecuta: el tope sigue en 450000.0000.
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente,
        con_tope,
        direccion,
        {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
        cookie_csrf=cookie,
        cabecera_csrf=cabecera,
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
    assert _tope(base, con_tope) == "450000.0000"
    assert _estado_de_negocio(base) == antes
    exigir_denegacion(
        base,
        usuario_id=direccion.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="PUT",
        ruta=ruta_captura(con_tope.linea_base_id, con_tope.tipos["MUROS"]),
        roles_requeridos=[],
        motivo="ORIGEN_NO_VERIFICADO",
    )


def test_tkt017_cac05_el_origen_se_verifica_antes_que_el_rol(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    con_tope: LineaBaseSembrada,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-C11 · CA-R1 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    `verificar_origen` va antes que `exigir_rol`: un solo asiento `DENEGAR`, con motivo
    `ORIGEN_NO_VERIFICADO` y sin roles exigidos. Si el orden se invirtiera, el motivo sería `ROL_INSUFICIENTE`.
    """
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = capturar_muros(
        cliente,
        con_tope,
        usuario,
        {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
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
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="PUT",
        ruta=ruta_captura(con_tope.linea_base_id, con_tope.tipos["MUROS"]),
        roles_requeridos=[],
        motivo="ORIGEN_NO_VERIFICADO",
    )


# --------------------------------------------------------------------------- el `motivo` acotado · CA-C3, CA-C5 y CA-C6

# Los cuatro cruces de la captura: (es recaptura, confirma que supera la venta). La primera captura parte
# de un tope nulo y la recaptura, de 450000.0000; con confirmación el tope (500000.0000) supera la venta
# (480000.0000) y sin ella es el que cabe (470000.0000 en la recaptura, 450000.0000 en la primera).
CRUCES_DE_CAPTURA = [
    pytest.param(False, False, id="primera_captura"),
    pytest.param(False, True, id="primera_captura_confirmada"),
    pytest.param(True, False, id="recaptura"),
    pytest.param(True, True, id="recaptura_confirmada"),
]
LARGO_MAXIMO_DEL_MOTIVO = 2000


def _preparar_cruce(
    recaptura: bool,
    confirmar: bool,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> dict[str, Any]:
    """Deja el tope previo (450000.0000 solo en una recaptura) y devuelve el cuerpo sin `motivo`."""
    if recaptura:
        dejar_tope(contexto, sembrada, direccion, "450000.0000")
    if confirmar:
        return {"importe_tope": "500000.0000", "confirmar_superior_a_venta": True}
    return {"importe_tope": "470000.0000" if recaptura else "450000.0000"}


@pytest.mark.parametrize(
    "motivo", [pytest.param("a\u0000b", id="nul_en_medio"), pytest.param("\u0000", id="solo_nul")]
)
@pytest.mark.parametrize(("recaptura", "confirmar"), CRUCES_DE_CAPTURA)
def test_tkt017_cac06_captura_con_motivo_con_nul(
    recaptura: bool,
    confirmar: bool,
    motivo: str,
    base: Base,
    cliente: TestClient,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 · RN-04 — un NUL en el `motivo` es `422` `VALIDACION` `FORMATO` en `motivo`, no un `500`.

    PostgreSQL no guarda el carácter `U+0000` en un `text`: `psycopg` lo rechaza al escribir el motivo de
    la fila o del asiento, ya dentro de la transacción. La validación del cuerpo debe pararlo antes de
    abrir ninguna. Se prueba en la primera captura y en la recaptura, con y sin la confirmación de un tope
    superior a la venta (el motivo se guarda en los cuatro casos, aunque solo se exija en algunos). El tope
    y la bitácora quedan intactos.
    """
    cuerpo = _preparar_cruce(recaptura, confirmar, contexto, sembrada, direccion)
    tope_antes = _tope(base, sembrada)
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(cliente, sembrada, direccion, {**cuerpo, "motivo": motivo})

    _exigir_validacion(respuesta, "motivo", "FORMATO", MENSAJE_FORMATO)
    assert _tope(base, sembrada) == tope_antes
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT count(*) FROM bitacora WHERE accion = 'RECAPTURAR'") == [(0,)]


@pytest.mark.parametrize(("recaptura", "confirmar"), CRUCES_DE_CAPTURA)
def test_tkt017_cac06_captura_con_motivo_de_mas_de_2000_caracteres(
    recaptura: bool,
    confirmar: bool,
    base: Base,
    cliente: TestClient,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 — rechazo: 2 001 caracteres exceden el máximo del `motivo`; `422` `DEMASIADO_LARGO` en `motivo`.

    Es el mismo límite y el mismo código que la congelación (`Motivo.maxLength` de 2 000). El tope y la
    bitácora quedan intactos en la primera captura y en la recaptura, con y sin confirmación.
    """
    cuerpo = _preparar_cruce(recaptura, confirmar, contexto, sembrada, direccion)
    tope_antes = _tope(base, sembrada)
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente, sembrada, direccion, {**cuerpo, "motivo": "m" * (LARGO_MAXIMO_DEL_MOTIVO + 1)}
    )

    _exigir_validacion(
        respuesta, "motivo", "DEMASIADO_LARGO", "El valor excede la longitud máxima."
    )
    assert _tope(base, sembrada) == tope_antes
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize(("recaptura", "confirmar"), CRUCES_DE_CAPTURA)
def test_tkt017_cac06_captura_con_motivo_de_exactamente_2000_caracteres(
    recaptura: bool,
    confirmar: bool,
    base: Base,
    cliente: TestClient,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 — borde: un `motivo` de exactamente 2 000 caracteres se acepta y se guarda entero en la fila y en el asiento."""
    cuerpo = _preparar_cruce(recaptura, confirmar, contexto, sembrada, direccion)
    motivo = "m" * LARGO_MAXIMO_DEL_MOTIVO

    respuesta = capturar_muros(cliente, sembrada, direccion, {**cuerpo, "motivo": motivo})

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == cuerpo["importe_tope"]
    assert fila["motivo_ultimo_cambio"] == motivo
    assert base.filas(
        "SELECT accion::text FROM bitacora WHERE motivo = %s AND entidad_id = %s",
        motivo,
        sembrada.controles["MUROS"],
    ) == [("RECAPTURAR" if recaptura else "CREAR",)]


# --------------------------------------------------------------------------- TC-C13, TC-C14 y TC-C15 · CA-C6


@pytest.mark.parametrize("estado", ["BORRADOR", "SUPERSEDIDA"])
def test_tkt017_cac06_linea_base_en_borrador(
    estado: str,
    base: Base,
    cliente: TestClient,
    entorno: Entorno,
    direccion: Sesion,
) -> None:
    """TC-C13 · CA-C6 esc. 1 · RN-03 — solo se captura el tope sobre una línea base congelada: `409` `CONFLICTO` `SIN_LINEA_BASE_CONGELADA` con su estado.

    La línea base en `BORRADOR` o `SUPERSEDIDA` tiene su fila de control, para que una ruta que no
    comprobara el estado sí pudiera escribir. El estado va en el mensaje y en el detalle junto al `id` de la
    línea base; no hay acciones, y no se escribe nada.
    """
    datos = entorno.datos
    linea_base = datos.linea_base(estado=estado, obra_id=entorno.obra_id, version=1)
    tipo = entorno.tipo_muros
    datos.control(linea_base_id=linea_base, tipo_partida_id=tipo)
    antes = _estado_de_negocio(base)

    respuesta = capturar_por_http(
        cliente, linea_base, tipo, direccion.sesion_id, {"importe_tope": "100.0000"}
    )

    exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "SIN_LINEA_BASE_CONGELADA",
            "mensaje": MENSAJE_SIN_CONGELADA.format(estado=estado),
            "detalle": {"linea_base_id": str(linea_base), "estado": estado},
            "acciones": [],
        },
        esquema="ErrorConflictoEstado",
    )
    assert base.filas("SELECT importe_tope FROM presupuesto_control") == [(None,)]
    assert _estado_de_negocio(base) == antes


# Cada valor viaja tal cual en el JSON del cuerpo: `450000` es un número, no una cadena.
TOPES_MAL_FORMADOS = [
    pytest.param("-1.0000", id="negativo"),
    pytest.param("-0", id="menos_cero"),
    pytest.param("1.12345", id="cinco_decimales"),
    pytest.param(450000, id="numero_entero"),
    pytest.param(450000.5, id="numero_con_decimales"),
    pytest.param("abc", id="texto"),
    pytest.param("", id="cadena_vacia"),
    pytest.param(True, id="booleano"),
    pytest.param(None, id="nulo"),
    pytest.param("1e5", id="notacion_cientifica"),
    pytest.param(" 1", id="espacio_al_inicio"),
    pytest.param("1 ", id="espacio_al_final"),
    pytest.param("+1", id="signo_mas"),
    pytest.param("450000.0000\n", id="salto_de_linea_al_final"),
    pytest.param(".5", id="sin_entero"),
    pytest.param("1.", id="sin_decimales"),
    pytest.param("1,5", id="coma_decimal"),
    pytest.param("NaN", id="nan"),
    pytest.param("Infinity", id="infinito"),
    pytest.param("٣٣", id="digitos_arabe_indicos"),
    pytest.param("１２", id="digitos_anchos"),
    pytest.param("12.٥", id="decimal_arabe_indico"),
    pytest.param("123456789012345", id="quince_enteros"),
    pytest.param("123456789012345.0000", id="quince_enteros_con_decimales"),
    pytest.param(["450000.0000"], id="lista"),
    pytest.param({"valor": "450000.0000"}, id="objeto"),
]


@pytest.mark.parametrize("valor", TOPES_MAL_FORMADOS)
def test_tkt017_cac06_tope_mal_formado(
    valor: object,
    base: Base,
    cliente: TestClient,
    con_tope: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 esc. 2 · RN-03 — un tope negativo, con más de cuatro decimales o que no es una cadena de importe: `422` `FORMATO` en `importe_tope`.

    La forma la impone `^\\d{1,14}(\\.\\d{1,4})?$` sobre una **cadena** (`ImporteNoNegativo` del borrador): un número
    JSON, un booleano o un nulo tampoco pasan, y tampoco lo que `Decimal()` aceptaría por su cuenta (espacios,
    signo `+`, notación científica, `NaN`, un salto de línea final). El tope sigue en 450000.0000 y no cambia nada.
    """
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(
        cliente,
        con_tope,
        direccion,
        {"importe_tope": valor, "motivo": MOTIVO_RECAPTURA},
    )

    _exigir_validacion(respuesta, "importe_tope", "FORMATO", MENSAJE_FORMATO)
    assert _tope(base, con_tope) == "450000.0000"
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param({}, id="cuerpo_vacio"),
        pytest.param({"motivo": MOTIVO_RECAPTURA}, id="solo_el_motivo"),
        pytest.param({"confirmar_superior_a_venta": True}, id="solo_la_confirmacion"),
    ],
)
def test_tkt017_cac06_cuerpo_sin_importe_tope(
    cuerpo: dict[str, Any],
    base: Base,
    cliente: TestClient,
    con_tope: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 esc. 2 — un cuerpo sin `importe_tope`: `422` `OBLIGATORIO` en ese campo y el tope no cambia."""
    antes = _estado_de_negocio(base)

    respuesta = capturar_muros(cliente, con_tope, direccion, cuerpo)

    _exigir_validacion(respuesta, "importe_tope", "OBLIGATORIO", MENSAJE_OBLIGATORIO)
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize(
    ("enviado", "guardado"),
    [
        pytest.param("0.0000", "0.0000", id="cero"),
        pytest.param("0", "0.0000", id="cero_sin_decimales"),
        pytest.param("7", "7.0000", id="entero_sin_decimales"),
        pytest.param("450000.5", "450000.5000", id="un_decimal"),
        pytest.param("0.0001", "0.0001", id="minimo_paso"),
    ],
)
def test_tkt017_cac06_tope_en_los_limites_de_forma_se_guarda_con_cuatro_decimales(
    enviado: str,
    guardado: str,
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C14 · CA-C6 — borde de la forma: cero y entre uno y cuatro decimales son importes válidos; se guardan y se publican con cuatro decimales."""
    respuesta = capturar_muros(cliente, sembrada, direccion, {"importe_tope": enviado})

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == guardado
    assert _tope(base, sembrada) == guardado


def test_tkt017_cac06_tope_con_catorce_enteros_y_cuatro_decimales_cabe(
    base: Base, cliente: TestClient, sembrada: LineaBaseSembrada, direccion: Sesion
) -> None:
    """TC-C14 · CA-C6 — el máximo que admite el patrón (14 enteros y 4 decimales, 18 dígitos de `NUMERIC(18,4)`) es válido.

    Supera la venta, así que se confirma con motivo: la forma es lo que se prueba, no la regla. Se guarda
    y se publica sin perder un dígito.
    """
    respuesta = capturar_muros(
        cliente,
        sembrada,
        direccion,
        {
            "importe_tope": "99999999999999.9999",
            "motivo": MOTIVO_SUPERIOR,
            "confirmar_superior_a_venta": True,
        },
    )

    fila = _control_de_respuesta(respuesta)
    assert fila["importe_tope"] == "99999999999999.9999"
    assert _tope(base, sembrada) == "99999999999999.9999"


def _linea_base_inexistente(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), entorno.tipo_muros


def _tipo_inexistente(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return sembrar_congelada_con_cifras(entorno).linea_base_id, uuid.uuid4()


def _congelada_sin_control(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return entorno.sembrar_congelada(), entorno.tipo_muros


@pytest.mark.parametrize(
    ("preparar", "recurso", "mensaje"),
    [
        pytest.param(
            _linea_base_inexistente, "linea_base", MENSAJE_LINEA_BASE_NO_EXISTE, id="linea_base"
        ),
        pytest.param(_tipo_inexistente, "tipo_partida", MENSAJE_TIPO_NO_EXISTE, id="tipo_partida"),
        pytest.param(
            _congelada_sin_control,
            "presupuesto_control",
            MENSAJE_SIN_CONTROL,
            id="presupuesto_control",
        ),
    ],
)
def test_tkt017_cac06_tipo_o_linea_base_inexistente(
    preparar: Callable[[Entorno], tuple[uuid.UUID, uuid.UUID]],
    recurso: str,
    mensaje: str,
    base: Base,
    cliente: TestClient,
    entorno: Entorno,
    direccion: Sesion,
) -> None:
    """TC-C15 · CA-C6 esc. 3 — lo que no existe responde `404` `NO_ENCONTRADO` con el recurso que falta y su mensaje, no la ruta.

    Línea base inexistente: `linea_base`. Tipo de partida inexistente en una línea base congelada con sus
    cuatro controles: `tipo_partida`. Una congelada sin fila de control para ese tipo: `presupuesto_control`.
    No se asienta nada.
    """
    linea_base, tipo = preparar(entorno)
    antes = _estado_de_negocio(base)

    respuesta = capturar_por_http(
        cliente, linea_base, tipo, direccion.sesion_id, {"importe_tope": "100.0000"}
    )

    exigir_error(
        respuesta,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": mensaje, "recurso": recurso},
        esquema="ErrorNoEncontrado",
    )
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize("parametro", ["linea_base_id", "tipo_partida_id"])
def test_tkt017_cac06_captura_con_identificador_mal_formado(
    parametro: str,
    base: Base,
    cliente: TestClient,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C15 · CA-C6 — un identificador que no es UUID en la ruta de la captura: `422` `VALIDACION` con `FORMATO` en ese parámetro."""
    antes = _estado_de_negocio(base)
    linea_base: uuid.UUID | str = sembrada.linea_base_id
    tipo: uuid.UUID | str = sembrada.tipos["MUROS"]
    if parametro == "linea_base_id":
        linea_base = "no-es-un-uuid"
    else:
        tipo = "no-es-un-uuid"

    respuesta = capturar_por_http(
        cliente, linea_base, tipo, direccion.sesion_id, {"importe_tope": "450000.0000"}
    )

    _exigir_validacion(respuesta, parametro, "FORMATO", MENSAJE_FORMATO)
    assert _estado_de_negocio(base) == antes


# --------------------------------------------------------------------------- CA-C7 por la API


def test_tkt017_cac07_captura_por_la_api_con_bloqueo_vencido(
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    cliente_espera_corta: TestClient,
    sembrar_usuario: SembrarUsuario,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: Sesion,
) -> None:
    """TC-C17 · CA-C7 esc. 2 · RNF-16 · ADR-004 — otra sesión tiene la fila de control: `409` `CONCURRENCIA` `BLOQUEO_VENCIDO` por la API.

    Contrato completo: `Retry-After: 1`, `espera_maxima_ms` 5000 (el `lock_timeout` del rol), la acción
    `REINTENTAR` `PUT` a la ruta de ESA captura —que no se filtra por rol— y sin `regla`. No escribe nada: el
    tope sigue en 450000.0000 y la bitácora solo trae el `CREAR` de la primera captura.
    """
    dejar_tope(contexto, sembrada, direccion, "450000.0000")
    sembrar_usuario(
        "direccion.espera@cimenta.test",
        CONTRASENA_DE_PRUEBA,
        roles=("DIRECCION_GENERAL",),
        nombre="Dirección con espera",
    )
    sesion_id = iniciar_sesion(
        cliente_espera_corta, "direccion.espera@cimenta.test", CONTRASENA_DE_PRUEBA
    )
    antes = _estado_de_negocio(base)
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute(_SQL_RETENER_CONTROL, (sembrada.linea_base_id, sembrada.tipos["MUROS"]))
        respuesta = capturar_por_http(
            cliente_espera_corta,
            sembrada.linea_base_id,
            sembrada.tipos["MUROS"],
            sesion_id,
            {"importe_tope": "470000.0000", "motivo": MOTIVO_RECAPTURA},
        )
    finally:
        retenedor.rollback()

    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONCURRENCIA",
            "codigo": "BLOQUEO_VENCIDO",
            "mensaje": MENSAJE_BLOQUEO,
            "detalle": {"espera_maxima_ms": 5000},
            "acciones": [
                {
                    "clave": "REINTENTAR",
                    "metodo": "PUT",
                    "ruta": ruta_captura(sembrada.linea_base_id, sembrada.tipos["MUROS"]),
                }
            ],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo
    assert _tope(base, sembrada) == "450000.0000"
    assert _acciones_de_bitacora(base) == ["CREAR"]
    assert _estado_de_negocio(base) == antes


# --------------------------------------------------------------------------- TC-C19 · CA-C6 · lo que publica la aplicación


def _sin_all_of_de_un_elemento(nodo: Any) -> Any:
    """El borrador escribe `allOf: [{$ref: Importe}]` para añadir una descripción a un `$ref`; el comparador de
    formas no lo resuelve. Se sustituye por el propio `$ref` (la misma forma, sin la envoltura)."""
    if isinstance(nodo, list):
        return [_sin_all_of_de_un_elemento(elemento) for elemento in nodo]
    if not isinstance(nodo, dict):
        return nodo
    nuevo = {clave: _sin_all_of_de_un_elemento(valor) for clave, valor in nodo.items()}
    variantes = nuevo.get("allOf")
    if isinstance(variantes, list) and len(variantes) == 1:
        sin_envoltura = {clave: valor for clave, valor in nuevo.items() if clave != "allOf"}
        return {**sin_envoltura, **variantes[0]}
    return nuevo


def _borrador_comparable() -> dict[str, Any]:
    return cast("dict[str, Any]", _sin_all_of_de_un_elemento(copy.deepcopy(borrador())))


def test_tkt017_cac06_importe_tope_se_publica_como_cadena(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-C19 · CA-C6 · M4 — en `/openapi.json`, `CapturaPresupuestoControl.importe_tope` es `type: string` con el patrón y el `format` del borrador.

    Un `PlainValidator` sin más deja el esquema vacío (`{}`), que el generador del cliente convierte en
    `unknown` y el dinero pierde su tipo cadena. El campo es obligatorio, el cuerpo de la operación apunta al
    esquema y el patrón publicado es, carácter por carácter, el de `ImporteNoNegativo` del borrador.
    """
    del_borrador = borrador()["components"]["schemas"]["ImporteNoNegativo"]
    assert del_borrador["pattern"] == PATRON_DEL_TOPE, "El borrador debe fijar el patrón del tope"
    contrato = publicado(monkeypatch)

    esquemas = contrato["components"]["schemas"]
    assert "CapturaPresupuestoControl" in esquemas, "El contrato publicado no tiene el esquema"
    captura = esquemas["CapturaPresupuestoControl"]
    importe = resolver(contrato, captura["properties"]["importe_tope"])
    assert importe, "importe_tope se publica con un esquema vacío"
    assert importe.get("type") == "string"
    assert importe.get("pattern") == PATRON_DEL_TOPE
    assert importe.get("format") == "decimal"
    assert "importe_tope" in captura["required"]
    operacion = contrato["paths"][RUTA_CAPTURA]["put"]
    cuerpo = operacion["requestBody"]["content"]["application/json"]["schema"]
    assert cuerpo == {"$ref": "#/components/schemas/CapturaPresupuestoControl"}


def _declara_number(nodo: Any) -> bool:
    """Si un esquema, o algo dentro de él, declara `number` (o `integer`) como tipo."""
    if isinstance(nodo, list):
        return any(_declara_number(elemento) for elemento in nodo)
    if not isinstance(nodo, dict):
        return False
    tipo = nodo.get("type")
    tipos = tipo if isinstance(tipo, list) else [tipo]
    if any(t in ("number", "integer") for t in tipos):
        return True
    return any(_declara_number(valor) for valor in nodo.values())


def _referencias(nodo: Any) -> set[str]:
    """Los nombres de componente que cita un esquema, a cualquier profundidad."""
    if isinstance(nodo, list):
        return {nombre for elemento in nodo for nombre in _referencias(elemento)}
    if not isinstance(nodo, dict):
        return set()
    encontrados = {str(nodo["$ref"]).rsplit("/", 1)[-1]} if "$ref" in nodo else set()
    for valor in nodo.values():
        encontrados |= _referencias(valor)
    return encontrados


def test_tkt017_cac06_el_contrato_publicado_no_trae_el_componente_dinero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-C19 · CA-C6 · regla 1 — la anotación de `importe_tope` no deja un componente huérfano `Dinero` ni un `number` en el contrato.

    Un `Annotated[Dinero, PlainValidator(...)]` sin `WithJsonSchema` hace que Pydantic publique el tipo de
    `tipos_base` como componente (`Dinero`, con `valor: number | string`): el borrador no lo tiene y el cliente
    generado lo tiparía como número. Ningún componente que cuelgue de las operaciones de control declara
    `number`: el dinero viaja como cadena. Anti-verde vacío: se recorren los dos esquemas de control y todo lo
    que citan.
    """
    contrato = publicado(monkeypatch)
    esquemas = contrato["components"]["schemas"]
    assert "CapturaPresupuestoControl" in esquemas, "El contrato publicado no tiene el esquema"
    assert "PresupuestoControl" in esquemas, "El contrato publicado no tiene el esquema"

    pendientes = ["CapturaPresupuestoControl", "PresupuestoControl"]
    alcanzados: set[str] = set()
    while pendientes:
        nombre = pendientes.pop()
        if nombre in alcanzados:
            continue
        alcanzados.add(nombre)
        pendientes.extend(_referencias(esquemas[nombre]) - alcanzados)

    assert "Dinero" not in esquemas, "El componente huérfano Dinero no está en el borrador"
    assert "Dinero" not in alcanzados
    con_number = sorted(nombre for nombre in alcanzados if _declara_number(esquemas[nombre]))
    assert con_number == [], f"Componentes de control que declaran number: {con_number}"
    assert {"TipoPartida", "UsuarioResumen"} <= alcanzados, "Anti-verde vacío: se recorrió poco"


@pytest.mark.parametrize("esquema", ["CapturaPresupuestoControl", "PresupuestoControl"])
def test_tkt017_cac06_la_forma_publicada_de_los_esquemas_de_control_coincide_con_el_borrador(
    esquema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-C19 · CA-C1 · CA-C6 · CA-R1 — propiedades, `required`, tipos, `format` y nulabilidad de cada esquema publicado son los del borrador.

    Se comparan, con los `$ref` resueltos, el esquema y todo lo que cuelga de él (`TipoPartida`,
    `UsuarioResumen`, los importes). Anti-verde vacío: el borrador declara las propiedades que se esperan.
    Los componentes de objeto o enumerado del borrador deben existir con su nombre en el publicado, y el
    publicado no debe duplicar ninguno bajo otro nombre con la misma forma.
    """
    comparable = _borrador_comparable()
    del_borrador, componentes_borrador = forma_de_componente(comparable, esquema)
    assert del_borrador[f"{esquema}.required"], "Anti-verde vacío: el borrador declara obligatorios"
    contrato = publicado(monkeypatch)
    assert esquema in contrato["components"]["schemas"], f"El contrato publicado no tiene {esquema}"

    publicada, componentes_publicados = forma_de_componente(contrato, esquema)

    assert diferencias_de_forma(del_borrador, publicada) == []
    faltan = sorted(componentes_borrador - set(contrato["components"]["schemas"]))
    assert faltan == [], f"Faltan componentes con el nombre del borrador: {faltan}"
    assert componentes_duplicados(contrato, componentes_publicados) == []


@pytest.mark.parametrize(
    ("metodo", "publicada"),
    [
        pytest.param("get", RUTA_LISTA, id="listar_presupuesto_control"),
        pytest.param("put", RUTA_CAPTURA, id="capturar_presupuesto_control"),
    ],
)
def test_tkt017_cac06_la_respuesta_y_los_parametros_publicados_son_los_del_borrador(
    metodo: str, publicada: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-C19 · CA-C1 · CA-C6 · CA-R1 — la respuesta `200` y los parámetros de ruta de cada operación publicados son los del borrador.

    Parámetros: nombre, ubicación, obligatoriedad, tipo y `format` (UUID en la ruta). La respuesta de la
    lectura es un arreglo de `PresupuestoControl` y la de la captura, un `PresupuestoControl`.
    """
    contrato = publicado(monkeypatch)
    sin_prefijo = publicada.removeprefix("/api/v1")
    assert publicada in contrato["paths"], f"Falta {publicada} en /openapi.json"
    assert metodo in contrato["paths"][publicada], f"Falta {metodo.upper()} {publicada}"
    comparable = _borrador_comparable()

    parametros_borrador = parametros_de(comparable, sin_prefijo, metodo)
    parametros_publicados = parametros_de(contrato, publicada, metodo)
    forma_borrador, _ = forma_de(
        comparable, esquema_de_respuesta_200(comparable, sin_prefijo, metodo), "respuesta"
    )
    forma_publicada, _ = forma_de(
        contrato, esquema_de_respuesta_200(contrato, publicada, metodo), "respuesta"
    )

    assert parametros_publicados == parametros_borrador
    assert diferencias_de_forma(forma_borrador, forma_publicada) == []


# --------------------------------------------------------------------------- TC-B19 · las rutas de c


OPERACIONES_DE_CONTROL = [
    ("GET", RUTA_LISTA, "listar_presupuesto_control"),
    ("PUT", RUTA_CAPTURA, "capturar_presupuesto_control"),
]


def test_tkt017_las_dos_operaciones_de_control_estan_entre_las_de_presupuesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B19 (fila C3) · CA-R1 — el borrador lleva `TKT-017` en las dos operaciones y la aplicación las publica con su método, ruta y `operationId`.

    El conjunto exacto `(método, ruta, operationId)` de `presupuesto` lo fija `TC-B19` en
    `test_tkt017_api_congelado.py`, cuya lista `IMPLEMENTADAS_DE_PRESUPUESTO` incluye estas dos.
    """
    contrato = publicado(monkeypatch)

    for metodo, ruta, operacion in OPERACIONES_DE_CONTROL:
        del_borrador = borrador()["paths"][ruta.removeprefix("/api/v1")][metodo.lower()]
        assert del_borrador["operationId"] == operacion
        assert "TKT-017" in del_borrador["x-tickets"]
        assert ruta in contrato["paths"], f"Falta {ruta} en /openapi.json"
        assert metodo.lower() in contrato["paths"][ruta], f"Falta {metodo} {ruta} en /openapi.json"
        en_la_aplicacion = contrato["paths"][ruta][metodo.lower()]
        assert en_la_aplicacion["operationId"] == operacion
        assert "presupuesto" in en_la_aplicacion["tags"]


# --------------------------------------------------------------------------- TC-B17 de c · CA-R1


def _ruta_de_control(aplicacion: FastAPI, metodo: str, publicada: str) -> APIRoute:
    """La única `APIRoute` con ese método y esa ruta; si falta o está repetida, la prueba lo dice."""
    encontradas = [
        ruta
        for ruta in rutas_de(aplicacion.routes)
        if ruta.path == publicada and metodo in (ruta.methods or ())
    ]
    assert len(encontradas) == 1, (
        f"La aplicación debe publicar exactamente un {metodo} {publicada}; hay {len(encontradas)}"
    )
    return encontradas[0]


def test_tkt017_car1_las_rutas_de_control_estan_en_el_recorrido_de_la_aplicacion_completa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 de c · CA-R1 · RNF-05 · regla 11 — ambas son `def` y exigen sesión; el `GET` lleva un solo `exigir_rol` y el `PUT` verifica el origen antes.

    Es el recorrido de `test_tkt006_enrutador.py` y de `test_tkt057_csrf.py` hecho sobre estas dos rutas, con
    su `operation_id` del borrador. La lectura no lleva `verificar_origen`; la captura lo declara como primera
    dependencia, antes que `exigir_rol`. Mutantes «`async def`», «`GET` sin `exigir_rol`» y «`PUT` sin
    `verificar_origen`».
    """
    from cimenta.identidad.api.dependencias import sesion_vigente, verificar_origen

    aplicacion = construir_aplicacion(monkeypatch)
    lectura = _ruta_de_control(aplicacion, "GET", RUTA_LISTA)
    captura = _ruta_de_control(aplicacion, "PUT", RUTA_CAPTURA)

    assert lectura.operation_id == "listar_presupuesto_control"
    assert captura.operation_id == "capturar_presupuesto_control"
    for ruta in (lectura, captura):
        assert inspect.isfunction(ruta.endpoint)
        assert not inspect.iscoroutinefunction(ruta.endpoint), (
            f"{ruta.operation_id} no puede ser async def"
        )
        assert sesion_vigente in list(llamadas(ruta.dependant))
        roles = [
            c for c in llamadas(ruta.dependant) if getattr(c, "__name__", "") == "comprobar_rol"
        ]
        assert len(roles) == 1, f"{ruta.operation_id} debe declarar exactamente un exigir_rol"
    assert verificar_origen not in list(llamadas(lectura.dependant)), (
        "Una lectura no verifica el origen"
    )
    declaradas = [sub.call for sub in captura.dependant.dependencies]
    assert verificar_origen in declaradas, "La ruta que muta debe declarar verificar_origen"
    posicion_del_rol = next(
        posicion
        for posicion, llamada in enumerate(declaradas)
        if getattr(llamada, "__name__", "") == "comprobar_rol"
    )
    assert declaradas.index(verificar_origen) < posicion_del_rol, (
        "verificar_origen debe ir antes que exigir_rol"
    )


def test_tkt017_car1_openapi_publica_el_control_con_sesion_y_csrf_solo_donde_muta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 de c · CA-R1 · M4 — `/openapi.json` declara `sesion` en las dos operaciones y `csrf` solo en la captura."""
    contrato = publicado(monkeypatch)

    for metodo, ruta, operacion in OPERACIONES_DE_CONTROL:
        assert ruta in contrato["paths"], f"Falta {ruta} en /openapi.json"
        assert metodo.lower() in contrato["paths"][ruta], f"Falta {metodo} {ruta}"
        publicada = contrato["paths"][ruta][metodo.lower()]
        exigidos = {nombre for requisito in publicada.get("security", []) for nombre in requisito}
        assert "sesion" in exigidos, operacion
        assert ("csrf" in exigidos) == (metodo == "PUT"), operacion
