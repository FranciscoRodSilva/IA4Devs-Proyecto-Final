"""API del congelado, fila B3 de TKT-017b1: `POST /api/v1/lineas-base/{linea_base_id}/congelacion`.

Cubre TC-B01, TC-B03, TC-B04, TC-B05, TC-B06, TC-B11, TC-B17 y TC-B19 del diseño (`CA-B1` a `CA-B4`, `CA-B6`
esc. 1, `CA-B8` y `CA-R1`; `HDU-001` esc. 14 y 19; `RN-01`, `RN-04`) contra PostgreSQL migrado con `alembic
upgrade head` y el rol de aplicación, por la aplicación real (`crear_aplicacion`) y un `TestClient` HTTPS. La
línea base `BORRADOR` sale siempre de la confirmación real (`materializar_importacion`), salvo en los
rechazos de estado, donde se siembra a mano. El director y su sesión salen del inicio de sesión real.

Cada rechazo comprueba el contrato de error completo, no solo el código de estado: `tipo`, `regla` o
`codigo`, `mensaje` literal, `detalle`, `acciones`, las claves exactas del cuerpo, `correlacion_id` igual a la
cabecera `X-Correlacion-Id`, las cabeceras propias (`Retry-After`) y la validez contra el esquema de error
del borrador. Todos comprueban además que no cambió nada en la base: ninguna fila, ningún estado, ningún
asiento (salvo el `DENEGAR`, que es justo lo que el `403` debe dejar).

Rojo original de B3 (riesgo `R-2` de a3, aceptado por la persona dueña): cuando se escribió el archivo,
la ruta, el módulo `api` de presupuesto, el montaje y `importes_venta_por_tipo` no existían, y la ruta
ausente respondía `404` (`NO_ENCONTRADO` con la ruta como recurso) donde cada prueba espera `200`, `401`,
`403`, `404 linea_base`, `409` o `422`. Ese rojo ya está documentado en `impl.md`; hoy la ruta existe y el
archivo corre en verde.

TC-B17 y las rutas existentes. `test_tkt006_enrutador.py` y `test_tkt057_csrf.py` recorren la aplicación
completa que arma `crear_aplicacion`, así que cubren la ruta de congelación sin más cambios. Aquí la
protegen dos pruebas (la ruta debe estar en el recorrido, ser `def` y llevar `verificar_origen` antes que
`exigir_rol`) y la entrada de la ruta en `CUERPOS_VALIDOS` de `test_tkt057_csrf.py`, sin la cual TC-48
falla con «sin entrada».
Mutantes que este archivo debe poner en rojo: «ruta nueva sin `verificar_origen`» y «`async def`» (las dos
pruebas de TC-B17), «`exigir_rol` antes que `verificar_origen`» (`test_tkt017_cab04_el_origen_se_verifica_antes_
que_el_rol`), `M-B8` (`importes_venta_por_tipo` lee `partida_concepto` en una `CONGELADA`: TC-B01).

Pruebas añadidas en el ciclo 1 de corrección de `/sdd-revisar`: `test_tkt017_cab04_congelar_motivo_con_nul`
nació en rojo (la ruta respondía `500` porque `psycopg` rechaza el NUL del motivo al asentar la bitácora).

El MVP no tiene permiso por obra (`docs/07-especificacion-api.md`, línea 399): el caso «otra obra» de la
lista del tester de API no aplica a esta ruta y no hay prueba de IDOR por obra.
"""

from __future__ import annotations

import functools
import inspect
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, NamedTuple, cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.infraestructura import repositorio_linea_base
from cimenta.presupuesto.interfaz import LineaBaseMaterializada
from herramientas.soporte_tkt017 import preparacion_dos_niveles
from herramientas.soporte_tkt017_api import (
    CONTRASENA_DE_PRUEBA,
    NOMBRE_DEL_DIRECTOR,
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    VENTA_POR_TIPO,
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
    exigir_denegacion,
    exigir_error,
    forma_de_componente,
    iniciar_sesion,
    llamadas,
    rutas_de,
    tipos_de_partida,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado
from herramientas.soporte_tkt017_entorno import (
    CODIGO_OBRA,
    MOTIVO_DE_CONGELADO,
    NOMBRE_COMPLETO_OBRA,
    Base,
    Contexto,
    Entorno,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, RelojDePrueba, SembrarUsuario

RUTA_CONGELACION = "/api/v1/lineas-base/{linea_base_id}/congelacion"

CORREO_DEL_DIRECTOR = "diana@cimenta.test"
MOTIVO = MOTIVO_DE_CONGELADO

MENSAJE_RN01 = (
    "La obra {codigo} ya tiene una línea base congelada; para sustituirla hay que crear una versión "
    "nueva que marque la anterior como SUPERSEDIDA."
)
MENSAJE_LINEA_EN_OTRO_ESTADO = (
    "La línea base está en {estado}; solo se congela una línea base en BORRADOR."
)
MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_NO_EXISTE = "La línea base no existe."
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_OBLIGATORIO = "El campo es obligatorio."

CON_FECHA_Y_ZONA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

RUTAS_SIN_SESION = frozenset({"GET /api/v1/sesion/csrf", "POST /api/v1/sesion"})
# B3 publica la congelación; B4, las cuatro lecturas de la línea base; C3, las dos del presupuesto de control.
IMPLEMENTADAS_DE_PRESUPUESTO = frozenset(
    {
        "congelar_linea_base",
        "listar_lineas_base",
        "obtener_linea_base",
        "listar_conceptos_linea_base",
        "obtener_explosion_insumos",
        "listar_presupuesto_control",
        "capturar_presupuesto_control",
    }
)


# --------------------------------------------------------------------------- ayudas de la prueba


def ruta_de(linea_base_id: uuid.UUID | str) -> str:
    return f"/api/v1/lineas-base/{linea_base_id}/congelacion"


def congelar_por_http(
    cliente: TestClient,
    linea_base_id: uuid.UUID | str,
    sesion_id: uuid.UUID | None,
    *,
    cuerpo: dict[str, Any] | None = None,
    cookie_csrf: str | None = TOKEN_CSRF,
    cabecera_csrf: str | None = TOKEN_CSRF,
) -> Any:
    """`POST` de la congelación con el par CSRF indicado; por omisión, uno válido y el motivo del diseño."""
    return cliente.post(
        ruta_de(linea_base_id),
        json={"motivo": MOTIVO} if cuerpo is None else cuerpo,
        headers=cabeceras_de(sesion_id, cookie_csrf, cabecera_csrf),
    )


def _estado_de_negocio(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: la foto del soporte más las obras, las líneas base completas y todo
    lo que escribe el congelado (copias, explosión y control), con todas sus columnas, y la bitácora sin los
    asientos `DENEGAR` (el `403` debe dejar uno; cualquier otro asiento sería un cambio)."""
    foto = dict(base.foto())
    conteos = dict(cast("dict[str, int]", foto.pop("filas")))
    conteos.pop("bitacora")
    return {
        "foto": foto,
        "conteos": conteos,
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "copias": base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        "explosion": base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
        "control": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
        "bitacora": base.filas("SELECT * FROM bitacora WHERE accion <> 'DENEGAR' ORDER BY id"),
    }


def exigir_conflicto_de_estado(respuesta: Any, mensaje: str, detalle: dict[str, Any]) -> None:
    exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "ESTADO_NO_PERMITE_OPERACION",
            "mensaje": mensaje,
            "detalle": detalle,
            "acciones": [],
        },
        esquema="ErrorConflictoEstado",
    )


# --------------------------------------------------------------------------- el congelado por la API


class Congelado(NamedTuple):
    """El resultado de confirmar y congelar por la API el libro de `CA-B1`."""

    borrador: LineaBaseMaterializada
    respuesta: Any
    director_id: uuid.UUID
    momento: datetime
    momento_de_la_confirmacion: datetime


@pytest.fixture
def congelado_por_api(
    entorno: Entorno,
    contexto: Contexto,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> Callable[[], Congelado]:
    """`CA-B1`: confirma el libro de 12 apariciones de MUROS y PLAFONES_Y_CAJILLOS y lo congela por HTTP.

    Lo congela un director distinto del que confirmó, diez minutos después (la sesión caduca a los treinta
    de inactividad), para que ningún valor se confunda con el de la confirmación. Se arma una sola vez.
    """

    def armar() -> Congelado:
        entorno.importacion_id = entorno.importar(preparacion=preparacion_dos_niveles())
        momento_de_la_confirmacion = reloj_de_prueba.ahora
        borrador = entorno.confirmar(contexto)
        reloj_de_prueba.avanzar(timedelta(minutes=5))
        director = abrir_sesion(nombre=NOMBRE_DEL_DIRECTOR)
        reloj_de_prueba.avanzar(timedelta(minutes=5))
        respuesta = congelar_por_http(cliente, borrador.linea_base_id, director.sesion_id)
        return Congelado(
            borrador=borrador,
            respuesta=respuesta,
            director_id=director.usuario_id,
            momento=reloj_de_prueba.ahora,
            momento_de_la_confirmacion=momento_de_la_confirmacion,
        )

    return functools.cache(armar)


# --------------------------------------------------------------------------- TC-B01 · CA-B1


def test_hdu001_esc14_congelar_la_linea_base(
    entorno: Entorno, base: Base, congelado_por_api: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-01 — `200` con la forma exacta de `LineaBase` del borrador.

    `congelada_por` es el `UsuarioResumen` del director que congeló, `congelada_en` trae zona, el importe
    viaja como cadena con cuatro decimales y `por_tipo_partida` trae las cuatro filas de `tipo_partida`
    ordenadas por `id`, con `0.0000` en ENCHAPES y GENERALES.
    """
    congelado = congelado_por_api()
    respuesta = congelado.respuesta

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    assert set(cuerpo) == {
        "id",
        "obra_id",
        "version",
        "estado",
        "importe_venta",
        "congelada_en",
        "congelada_por",
        "motivo",
        "por_tipo_partida",
    }
    assert isinstance(cuerpo["congelada_en"], str)
    assert CON_FECHA_Y_ZONA.match(cuerpo["congelada_en"]), cuerpo["congelada_en"]
    assert datetime.fromisoformat(cuerpo["congelada_en"]) == congelado.momento
    sin_fecha = {clave: valor for clave, valor in cuerpo.items() if clave != "congelada_en"}
    assert sin_fecha == {
        "id": str(congelado.borrador.linea_base_id),
        "obra_id": str(entorno.obra_id),
        "version": 1,
        "estado": "CONGELADA",
        "importe_venta": "63000.0000",
        "congelada_por": {"id": str(congelado.director_id), "nombre": NOMBRE_DEL_DIRECTOR},
        "motivo": MOTIVO,
        "por_tipo_partida": [
            {
                "tipo_partida": {"id": str(id_tipo), "clave": clave, "nombre": nombre},
                "importe_venta": VENTA_POR_TIPO[clave],
            }
            for id_tipo, clave, nombre in tipos_de_partida(base)
        ],
    }
    validar_contra("LineaBase", cuerpo)


def test_hdu001_esc14_api_congelar_copia_los_doce_conceptos_con_su_importe(
    entorno: Entorno, base: Base, congelado_por_api: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-24 — 12 copias con código, cantidad, precio e importe."""
    congelado = congelado_por_api()
    assert congelado.respuesta.status_code == 200, congelado.respuesta.text
    planeadas = base.filas(
        "SELECT pc.id, c.codigo, pc.cantidad, pc.precio_unitario, pc.importe "
        "FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s ORDER BY pc.id",
        entorno.obra_id,
    )
    copias = base.filas(
        "SELECT partida_concepto_id, codigo, cantidad, precio_unitario, importe "
        "FROM linea_base_concepto WHERE linea_base_id = %s ORDER BY partida_concepto_id",
        congelado.borrador.linea_base_id,
    )

    assert len(planeadas) == 12
    assert copias == planeadas
    assert {fila[1:] for fila in copias} == {("620040-A", "12.5000", "420.0000", "5250.0000")}


def test_hdu001_esc14_api_congelar_copia_la_explosion_y_crea_los_cuatro_controles(
    base: Base, congelado_por_api: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-24 · RN-03 — explosión por tipo e insumo; sugerido del cálculo y tope nulo."""
    congelado = congelado_por_api()
    assert congelado.respuesta.status_code == 200, congelado.respuesta.text
    linea_base_id = congelado.borrador.linea_base_id

    assert base.filas(
        "SELECT tp.clave, i.codigo, e.cantidad_presupuestada, e.rendimiento_congelado, "
        "e.costo_unitario, e.importe_venta "
        "FROM explosion_presupuesto e JOIN tipo_partida tp ON tp.id = e.tipo_partida_id "
        "JOIN insumo i ON i.id = e.insumo_id WHERE e.linea_base_id = %s ORDER BY tp.clave",
        linea_base_id,
    ) == [
        ("MUROS", "PANEL YESO 1/2", "50.5050", "0.673400", "85.5000", "4318.1775"),
        ("PLAFONES_Y_CAJILLOS", "PANEL YESO 1/2", "50.5050", "0.673400", "85.5000", "4318.1775"),
    ]
    assert base.filas(
        "SELECT tp.clave, c.importe_sugerido, c.importe_tope "
        "FROM presupuesto_control c JOIN tipo_partida tp ON tp.id = c.tipo_partida_id "
        "WHERE c.linea_base_id = %s ORDER BY tp.clave",
        linea_base_id,
    ) == [
        ("ENCHAPES", "0.0000", None),
        ("GENERALES", "0.0000", None),
        ("MUROS", "23250.0000", None),
        ("PLAFONES_Y_CAJILLOS", "23250.0000", None),
    ]


def test_hdu001_esc14_api_congelar_deja_la_linea_base_congelada_y_la_obra_activa(
    entorno: Entorno, base: Base, congelado_por_api: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-01 — `CONGELADA` con fecha, usuario y motivo; la obra, `ACTIVA`."""
    congelado = congelado_por_api()
    assert congelado.respuesta.status_code == 200, congelado.respuesta.text

    assert base.filas(
        "SELECT id, version, estado, importe_venta, congelada_en, congelada_por_id, motivo, "
        "creado_en, creado_por_id FROM linea_base WHERE obra_id = %s",
        entorno.obra_id,
    ) == [
        (
            congelado.borrador.linea_base_id,
            1,
            "CONGELADA",
            "63000.0000",
            congelado.momento,
            congelado.director_id,
            MOTIVO,
            congelado.momento_de_la_confirmacion,
            entorno.usuario_id,
        )
    ]
    assert base.filas(
        "SELECT estado, actualizado_en, actualizado_por_id FROM obra WHERE id = %s",
        entorno.obra_id,
    ) == [("ACTIVA", congelado.momento, congelado.director_id)]


def test_hdu001_esc14_api_congelar_asienta_congelar_con_rn01_y_el_motivo(
    entorno: Entorno, base: Base, congelado_por_api: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-04 — un asiento `CONGELAR` con `RN-01`, el motivo y el director de la sesión."""
    congelado = congelado_por_api()
    assert congelado.respuesta.status_code == 200, congelado.respuesta.text

    assert base.filas(
        "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
        "obra_id, datos_antes, datos_despues FROM bitacora WHERE accion = 'CONGELAR'"
    ) == [
        (
            "CONGELAR",
            "linea_base",
            congelado.borrador.linea_base_id,
            congelado.director_id,
            congelado.momento,
            "RN-01",
            MOTIVO,
            entorno.obra_id,
            {"estado": "BORRADOR"},
            {"estado": "CONGELADA", "version": 1, "importe_venta": "63000.0000"},
        )
    ]


def test_hdu001_esc14_api_el_motivo_se_guarda_sin_espacios_en_los_extremos(
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B4 — `Motivo` recorta los espacios: la respuesta, la línea base y el asiento lo traen limpio."""
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    director = abrir_sesion()

    respuesta = congelar_por_http(
        cliente,
        borrador.linea_base_id,
        director.sesion_id,
        cuerpo={"motivo": "  Firma de contrato 2026-11-04 \n"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["motivo"] == MOTIVO
    assert base.filas("SELECT motivo FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        (MOTIVO,)
    ]
    assert base.filas("SELECT motivo FROM bitacora WHERE accion = 'CONGELAR'") == [(MOTIVO,)]


def test_hdu001_esc14_el_importe_por_tipo_de_una_congelada_es_la_suma_de_las_copias(
    entorno: Entorno,
    base: Base,
    motor_aplicacion: Engine,
    congelado_por_api: Callable[[], Congelado],
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · M-B8 — tras congelar, cambiar `partida_concepto` no mueve el importe por tipo.

    El rol de aplicación sí puede modificar `partida_concepto`; la línea base congelada no puede enterarse.
    `importes_venta_por_tipo` (repositorio, fila B3) lee en una sesión propia: cuatro filas ordenadas por
    `id`, cada una con su `importe_venta`; el resultado sigue siendo la suma de las copias y no la de
    `partida_concepto`. La ruta de lectura (`obtener_linea_base`) es de b2; por eso se llama al repositorio.
    """
    congelado = congelado_por_api()
    assert congelado.respuesta.status_code == 200, congelado.respuesta.text
    esperado = [VENTA_POR_TIPO[clave] for _, clave, _ in tipos_de_partida(base)]
    base.ejecutar(
        "UPDATE partida_concepto SET importe = 999999.0000 WHERE id IN "
        "(SELECT pc.id FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s)",
        entorno.obra_id,
    )
    assert base.filas("SELECT DISTINCT importe FROM partida_concepto") == [("999999.0000",)], (
        "El cambio de partida_concepto debe haberse aplicado, o la comprobación no demuestra nada"
    )

    with Session(motor_aplicacion) as sesion:
        filas = repositorio_linea_base.importes_venta_por_tipo(
            sesion, congelado.borrador.linea_base_id
        )
        importes = [fila.importe_venta.serializar() for fila in filas]

    assert importes == esperado


# --------------------------------------------------------------------------- TC-B03 · CA-B2


def test_hdu001_esc19_segunda_linea_base_vigente(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 19 · TC-B03 · CA-B2 · RN-01 — `409` `REGLA_NEGOCIO` con la obra, la vigente y su versión 1; nada cambia.

    La obra ya está `ACTIVA` porque tiene congelada: si se comprobara el estado de la obra primero, el
    mensaje sería el de la obra fuera de planeación y no el de `SUPERSEDIDA`. Las acciones van vacías.
    """
    vigente = entorno.sembrar_congelada()
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id, version=2)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, borrador, director.sesion_id)

    exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "REGLA_NEGOCIO",
            "regla": "RN-01",
            "mensaje": MENSAJE_RN01.format(codigo=CODIGO_OBRA),
            "detalle": {
                "obra": NOMBRE_COMPLETO_OBRA,
                "linea_base_vigente_id": str(vigente),
                "version_vigente": 1,
            },
            "acciones": [],
        },
        esquema="ErrorReglaNegocio",
    )
    assert _estado_de_negocio(base) == antes


# --------------------------------------------------------------------------- TC-B04 · CA-B3


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt017_cab03_linea_base_en_otro_estado(
    estado: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B04 · CA-B3 esc. 1 — una línea base que no está en `BORRADOR` responde `409` `ESTADO_NO_PERMITE_OPERACION` con su estado."""
    if estado == "CONGELADA":
        linea_base = entorno.sembrar_congelada()
    else:
        linea_base = entorno.datos.linea_base(
            estado="SUPERSEDIDA", obra_id=entorno.obra_id, version=1
        )
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, linea_base, director.sesion_id)

    exigir_conflicto_de_estado(
        respuesta,
        MENSAJE_LINEA_EN_OTRO_ESTADO.format(estado=estado),
        {"linea_base_id": str(linea_base), "estado": estado},
    )
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize("estado_obra", ["SUSPENDIDA", "CERRADA"])
def test_tkt017_cab03_obra_en_otro_estado(
    estado_obra: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B04 · CA-B3 esc. 2 — con la obra fuera de `PLANEACION` y sin congelada responde `409` con el estado de la obra."""
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    entorno.poner_obra_en(estado_obra)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, borrador, director.sesion_id)

    exigir_conflicto_de_estado(
        respuesta,
        MENSAJE_FUERA_DE_PLANEACION.format(codigo=CODIGO_OBRA, estado=estado_obra),
        {"obra": NOMBRE_COMPLETO_OBRA, "estado_obra": estado_obra},
    )
    assert _estado_de_negocio(base) == antes


def test_tkt017_cab03_linea_base_inexistente_responde_404(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B04 · CA-B3 · CA-B6 esc. 3 — `404` `NO_ENCONTRADO` con `recurso` `linea_base`; no la ruta, que es lo que responde un enrutador sin ella."""
    entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, uuid.uuid4(), director.sesion_id)

    exigir_error(
        respuesta,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": MENSAJE_NO_EXISTE, "recurso": "linea_base"},
        esquema="ErrorNoEncontrado",
    )
    assert _estado_de_negocio(base) == antes


# --------------------------------------------------------------------------- TC-B05 · CA-B4 esc. 1


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param({}, id="sin_campo"),
        pytest.param({"motivo": ""}, id="vacio"),
        pytest.param({"motivo": "   "}, id="solo_espacios"),
    ],
)
def test_tkt017_cab04_congelar_sin_motivo(
    cuerpo: dict[str, Any],
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B05 · CA-B4 esc. 1 · RN-04 — sin campo, vacío o solo espacios: `422` `VALIDACION` con `OBLIGATORIO` en `motivo`; sigue `BORRADOR`."""
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, borrador, director.sesion_id, cuerpo=cuerpo)

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": "La petición tiene 1 campo inválido.",
            "errores": [
                {"campo": "motivo", "codigo": "OBLIGATORIO", "mensaje": MENSAJE_OBLIGATORIO}
            ],
        },
        esquema="ErrorValidacion",
    )
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador) == [("BORRADOR",)]
    assert _estado_de_negocio(base) == antes


def test_tkt017_cab04_congelar_con_motivo_de_mas_de_2000_caracteres(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B05 · CA-B4 — rechazo: 2 001 caracteres exceden `Motivo.maxLength`; `422` con `DEMASIADO_LARGO` en `motivo`."""
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(
        cliente, borrador, director.sesion_id, cuerpo={"motivo": "m" * 2001}
    )

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": "La petición tiene 1 campo inválido.",
            "errores": [
                {
                    "campo": "motivo",
                    "codigo": "DEMASIADO_LARGO",
                    "mensaje": "El valor excede la longitud máxima.",
                }
            ],
        },
        esquema="ErrorValidacion",
    )
    assert _estado_de_negocio(base) == antes


@pytest.mark.parametrize(
    "motivo",
    [
        pytest.param("a\u0000b", id="nul_en_medio"),
        pytest.param("\u0000", id="solo_nul"),
    ],
)
def test_tkt017_cab04_congelar_motivo_con_nul(
    motivo: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B05 · CA-B4 · RN-04 — rechazo: un NUL en el motivo es `422` `VALIDACION` `FORMATO` en `motivo`, no un `500`.

    PostgreSQL no guarda el carácter `U+0000` en un `text`: `psycopg` lo rechaza al ejecutar el `INSERT`
    de la bitácora, ya con la copia escrita en la transacción. La validación de `Motivo` debe pararlo
    antes de abrir ninguna transacción. La línea base es congelable de verdad (viene de la confirmación
    real), así que un `500` aquí sería el fallo del motor y no un rechazo de negocio. Sigue `BORRADOR`, la
    obra en `PLANEACION` y no hay asiento `CONGELAR`.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(
        cliente, borrador.linea_base_id, director.sesion_id, cuerpo={"motivo": motivo}
    )

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": "La petición tiene 1 campo inválido.",
            "errores": [
                {
                    "campo": "motivo",
                    "codigo": "FORMATO",
                    "mensaje": "El valor no tiene el formato esperado.",
                }
            ],
        },
        esquema="ErrorValidacion",
    )
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        ("BORRADOR",)
    ]
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("PLANEACION",)]
    assert base.filas("SELECT count(*) FROM bitacora WHERE accion = 'CONGELAR'") == [(0,)]


# --------------------------------------------------------------------------- TC-B06 · CA-B4 esc. 2


@pytest.mark.parametrize(
    "rol",
    [
        "DIRECCION_GENERAL",
        "COMPRAS",
        "RESIDENTE",
        "ALMACEN",
        "ADMINISTRACION",
    ],
)
def test_tkt017_cab04_congelar_sin_rol(
    rol: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-B06 · CA-B4 esc. 2 · RN-04 — la ruta es exclusiva de `DIRECTOR_PROYECTOS`: `403` `ROL_INSUFICIENTE` sin `detalle` y un `DENEGAR`.

    `DIRECCION_GENERAL` y `COMPRAS` son los del criterio; los otros tres roles confirman que la ruta no
    admite a nadie más. La línea base sigue en `BORRADOR` y el cuerpo no trae cifras del recurso.
    """
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    usuario = abrir_sesion((rol,))
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(cliente, borrador, usuario.sesion_id)

    cuerpo = exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ["DIRECTOR_PROYECTOS"],
        },
        esquema="ErrorPermiso",
    )
    assert "detalle" not in cuerpo
    assert "63000" not in respuesta.text
    assert str(borrador) not in respuesta.text
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador) == [("BORRADOR",)]
    assert _estado_de_negocio(base) == antes
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ROL_INSUFICIENTE",
        ruta=ruta_de(borrador),
        roles_requeridos=["DIRECTOR_PROYECTOS"],
    )


def test_tkt017_cab04_el_director_con_otros_roles_tambien_congela(
    entorno: Entorno,
    contexto: Contexto,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    base: Base,
) -> None:
    """TC-B06 · CA-B4 esc. 2 — el permiso es la unión de los roles: quien además de otro rol tiene `DIRECTOR_PROYECTOS` congela."""
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    usuario = abrir_sesion(("COMPRAS", "DIRECTOR_PROYECTOS"))

    respuesta = congelar_por_http(cliente, borrador.linea_base_id, usuario.sesion_id)

    assert respuesta.status_code == 200, respuesta.text
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        ("CONGELADA",)
    ]


# --------------------------------------------------------------------------- sin sesión y sin CSRF


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt017_cab04_congelar_sin_sesion(
    sesion: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
) -> None:
    """TC-B06 · CA-R1 — sin sesión (o con una que no existe), aun con un par CSRF válido: `401` `SIN_SESION`, sin asiento y sin cambios."""
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    antes = _estado_de_negocio(base)
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = congelar_por_http(
        cliente, borrador, uuid.uuid4() if sesion == "sesion_inexistente" else None
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
def test_tkt017_cab04_congelar_sin_par_csrf(
    cookie: str | None,
    cabecera: str | None,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-B06 · CA-R1 · RNF-05 — rechazo: sin el doble envío del token, `403` `ORIGEN_NO_VERIFICADO` y un `DENEGAR`; no se congela nada.

    Las cuatro combinaciones de `CA-9` de TKT-057. Aunque quien llama sea el director con una línea base
    congelable, la petición no se ejecuta.
    """
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    director = abrir_sesion()
    antes = _estado_de_negocio(base)

    respuesta = congelar_por_http(
        cliente, borrador, director.sesion_id, cookie_csrf=cookie, cabecera_csrf=cabecera
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
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador) == [("BORRADOR",)]
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=director.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=ruta_de(borrador),
        roles_requeridos=[],
    )


def test_tkt017_cab04_el_origen_se_verifica_antes_que_el_rol(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-B17 · CA-R1 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    `verificar_origen` va antes que `exigir_rol`: un solo asiento `DENEGAR`, con motivo
    `ORIGEN_NO_VERIFICADO` y sin roles exigidos. Si el orden se invirtiera, el motivo sería `ROL_INSUFICIENTE`.
    """
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = congelar_por_http(
        cliente, borrador, usuario.sesion_id, cookie_csrf=None, cabecera_csrf=None
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
        ruta=ruta_de(borrador),
        roles_requeridos=[],
    )


# --------------------------------------------------------------------------- TC-B11 · CA-B6 esc. 1


def test_tkt017_cab06_congelado_con_bloqueo_vencido(
    entorno: Entorno,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    cliente_espera_corta: TestClient,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-B11 · CA-B6 esc. 1 · ADR-004 · RNF-16 — otra sesión tiene la obra: `409` `CONCURRENCIA` `BLOQUEO_VENCIDO` por la API.

    Contrato completo: `Retry-After: 1`, `espera_maxima_ms` 5000 (el `lock_timeout` del rol), la acción
    `REINTENTAR` `POST` a la ruta de congelación de ESA línea base —que no se filtra por rol— y sin `regla`.
    No escribe nada: la línea base sigue en `BORRADOR` y la obra en `PLANEACION`.
    """
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    sembrar_usuario(
        CORREO_DEL_DIRECTOR,
        CONTRASENA_DE_PRUEBA,
        roles=("DIRECTOR_PROYECTOS",),
        nombre=NOMBRE_DEL_DIRECTOR,
    )
    sesion_id = iniciar_sesion(cliente_espera_corta, CORREO_DEL_DIRECTOR, CONTRASENA_DE_PRUEBA)
    antes = _estado_de_negocio(base)
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (entorno.obra_id,))
        respuesta = congelar_por_http(cliente_espera_corta, borrador, sesion_id)
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
            "acciones": [{"clave": "REINTENTAR", "metodo": "POST", "ruta": ruta_de(borrador)}],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo
    assert _estado_de_negocio(base) == antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador) == [("BORRADOR",)]
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("PLANEACION",)]


# --------------------------------------------------------------------------- TC-B17 · CA-R1


def la_ruta_de_congelacion(aplicacion: FastAPI) -> APIRoute:
    """La única `APIRoute` `POST` de la congelación; si falta o está repetida, la prueba lo dice."""
    encontradas = [
        ruta
        for ruta in rutas_de(aplicacion.routes)
        if ruta.path == RUTA_CONGELACION and "POST" in (ruta.methods or ())
    ]
    assert len(encontradas) == 1, (
        f"La aplicación debe publicar exactamente un POST {RUTA_CONGELACION}; hay {len(encontradas)}"
    )
    return encontradas[0]


def test_tkt017_car1_la_ruta_de_congelacion_esta_en_el_recorrido_de_la_aplicacion_completa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 · CA-R1 · regla 11 — la ruta nueva es `def`, exige sesión y los recorridos de `test_tkt006_enrutador` la ven.

    Ninguna ruta, manejador ni dependencia de la aplicación es `async def`; las únicas rutas sin sesión
    siguen siendo las dos de la lista cerrada. Anti-verde vacío: la ruta de congelación sí está en el
    recorrido, con `sesion_vigente` en su cadena. Mutante «`async def`»: la ruta quedaría en
    `corrutinas_registradas`.
    """
    from cimenta.identidad.api.dependencias import sesion_vigente

    aplicacion = construir_aplicacion(monkeypatch)

    ruta = la_ruta_de_congelacion(aplicacion)
    assert inspect.isfunction(ruta.endpoint)
    assert not inspect.iscoroutinefunction(ruta.endpoint)
    assert sesion_vigente in list(llamadas(ruta.dependant))
    corrutinas = [
        r.endpoint.__name__
        for r in rutas_de(aplicacion.routes)
        if inspect.iscoroutinefunction(r.endpoint)
    ]
    assert corrutinas == []
    dependencias_asincronas = sorted(
        {
            llamada.__name__
            for r in rutas_de(aplicacion.routes)
            for llamada in llamadas(r.dependant)
            if inspect.isfunction(llamada) and inspect.iscoroutinefunction(llamada)
        }
    )
    assert dependencias_asincronas == []
    sin_sesion = {
        f"{metodo} {r.path}"
        for r in rutas_de(aplicacion.routes)
        if not any(llamada is sesion_vigente for llamada in llamadas(r.dependant))
        for metodo in r.methods or ()
    }
    assert sin_sesion == RUTAS_SIN_SESION


def test_tkt017_car1_la_ruta_que_muta_verifica_el_origen_antes_que_el_rol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 · CA-R1 · RNF-05 — `verificar_origen` es la primera dependencia de la ruta y `exigir_rol` va después.

    Es el recorrido de `test_tkt057_csrf.py` (toda ruta que muta tiene la verificación de origen en su
    cadena) más el orden que ese recorrido no mira. Mutante «ruta nueva sin `verificar_origen`»: la ruta
    quedaría fuera de la cadena. Las dependencias de nivel superior se listan en el orden en que se declararon.
    """
    from cimenta.identidad.api.dependencias import verificar_origen

    aplicacion = construir_aplicacion(monkeypatch)
    ruta = la_ruta_de_congelacion(aplicacion)

    declaradas = [sub.call for sub in ruta.dependant.dependencies]
    assert verificar_origen in declaradas, "La ruta que muta debe declarar verificar_origen"
    roles = [
        posicion
        for posicion, llamada in enumerate(declaradas)
        if getattr(llamada, "__name__", "") == "comprobar_rol"
    ]
    assert len(roles) == 1, "La ruta debe declarar exactamente un exigir_rol"
    assert declaradas.index(verificar_origen) < roles[0], (
        "verificar_origen debe ir antes que exigir_rol"
    )
    sin_verificar = [
        f"{metodo} {r.path}"
        for r in rutas_de(aplicacion.routes)
        for metodo in sorted({"POST", "PUT", "PATCH", "DELETE"} & set(r.methods or ()))
        if verificar_origen not in list(llamadas(r.dependant))
        and not any(
            getattr(llamada, "__name__", "") == "credenciales_con_origen_verificado"
            for llamada in llamadas(r.dependant)
        )
    ]
    assert sin_verificar == []


def test_tkt017_car1_openapi_publica_la_congelacion_con_sesion_y_csrf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 · CA-R1 · M4 — `/openapi.json` declara `sesion` y `csrf` en la congelación y el cuerpo `Motivo` acotado."""
    publicado = contrato_publicado(monkeypatch)

    operacion = publicado["paths"][RUTA_CONGELACION]["post"]

    exigidos = {nombre for requisito in operacion.get("security", []) for nombre in requisito}
    assert {"sesion", "csrf"} <= exigidos
    esquema = operacion["requestBody"]["content"]["application/json"]["schema"]
    motivo = publicado["components"]["schemas"][esquema["$ref"].rsplit("/", 1)[-1]]
    assert motivo["required"] == ["motivo"]
    assert motivo["properties"]["motivo"]["minLength"] == 1
    assert motivo["properties"]["motivo"]["maxLength"] == 2000


# --------------------------------------------------------------------------- TC-B19 · CA-B8, CA-R1


def test_tkt017_operation_id_de_las_rutas_de_presupuesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B19 · CA-B8 · CA-R1 — el conjunto `(método, ruta, operationId)` de `presupuesto` es el del borrador para TKT-017.

    En el patrón de TC-52 de `test_tkt006_enrutador.py`: el cliente TypeScript se genera de los
    `operationId`. Solo cuentan las operaciones de TKT-017 ya implementadas (`IMPLEMENTADAS_DE_PRESUPUESTO`;
    C3 añade las suyas). Las publicadas son las de la etiqueta `presupuesto`, que el borrador asigna a
    cada operación de línea base. La fila B3 publica `congelar_linea_base`; la B4, las cuatro lecturas.
    """
    esperadas = {
        (metodo.upper(), f"/api/v1{ruta}", operacion["operationId"])
        for ruta, elemento in borrador()["paths"].items()
        for metodo, operacion in elemento.items()
        if metodo in {"get", "post", "put", "patch", "delete"}
        and "TKT-017" in operacion.get("x-tickets", [])
        and operacion["operationId"] in IMPLEMENTADAS_DE_PRESUPUESTO
    }
    assert {operacion for _, _, operacion in esperadas} == IMPLEMENTADAS_DE_PRESUPUESTO, (
        "Anti-verde vacío: el borrador debe tener cada operación implementada con TKT-017 en x-tickets"
    )
    assert ("POST", RUTA_CONGELACION, "congelar_linea_base") in esperadas
    contrato = contrato_publicado(monkeypatch)

    publicadas = {
        (metodo.upper(), ruta, operacion["operationId"])
        for ruta, elemento in contrato["paths"].items()
        for metodo, operacion in elemento.items()
        if "presupuesto" in operacion.get("tags", [])
    }
    assert publicadas == esperadas


# --------------------------------------------------------------------------- TC-B20 · CA-B8, CA-R1


def test_tkt017_cab08_los_enums_de_linea_base_publicados_coinciden_con_el_borrador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B20 · CA-B8 · CA-R1 — `estado` y `TipoPartida.clave` publican el `enum` del borrador, valor por valor.

    El cliente TypeScript se genera de `/openapi.json`: con `string` en lugar del enumerado, el
    cliente deja pasar un estado o una clave que el contrato no admite. Validar la respuesta
    contra el borrador no lo detecta, porque `string` también cumple el enumerado.
    """
    del_borrador, _ = forma_de_componente(borrador(), "LineaBase")
    enums_del_borrador = {
        ruta: valores for ruta, valores in del_borrador.items() if ruta.endswith(".enum")
    }
    assert set(enums_del_borrador) == {
        "LineaBase.estado.enum",
        "LineaBase.por_tipo_partida[].tipo_partida.clave.enum",
    }, "Anti-verde vacío: el borrador debe declarar los dos enumerados de la línea base"
    assert enums_del_borrador["LineaBase.estado.enum"] == ["BORRADOR", "CONGELADA", "SUPERSEDIDA"]

    publicado, _ = forma_de_componente(contrato_publicado(monkeypatch), "LineaBase")

    enums_publicados = {ruta: publicado.get(ruta) for ruta in enums_del_borrador}
    assert enums_publicados == enums_del_borrador


def test_tkt017_cab08_la_forma_de_linea_base_publicada_coincide_con_el_borrador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B20 · CA-B8 · CA-R1 — propiedades, `required`, tipos y componentes de `LineaBase` publicados son los del borrador.

    Se comparan, con los `$ref` resueltos, `LineaBase` y todo lo que cuelga de ella (`TipoPartida`,
    `UsuarioResumen`, los renglones de `por_tipo_partida`). Los componentes de objeto o enumerado
    del borrador deben existir con su nombre en el publicado, y el publicado no debe duplicar
    ninguno bajo otro nombre con la misma forma.
    """
    del_borrador, componentes_borrador = forma_de_componente(borrador(), "LineaBase")
    contrato = contrato_publicado(monkeypatch)
    publicado, componentes_publicados = forma_de_componente(contrato, "LineaBase")

    diferencias = diferencias_de_forma(del_borrador, publicado)
    assert diferencias == []

    assert componentes_borrador <= set(contrato["components"]["schemas"]), (
        f"Faltan componentes con el nombre del borrador: {sorted(componentes_borrador - set(contrato['components']['schemas']))}"
    )
    duplicados = componentes_duplicados(contrato, componentes_publicados)
    assert duplicados == []


def test_tkt017_la_fabrica_documenta_el_montaje_de_presupuesto() -> None:
    """TC-B17 · fila B3 — el docstring de `servidor/fabrica.py` dice que desde TKT-017b también monta `cimenta.presupuesto.api.montaje`."""
    import servidor.fabrica as fabrica

    documentacion = fabrica.__doc__ or ""
    assert "cimenta.presupuesto.api.montaje" in documentacion
    assert "TKT-017b" in documentacion
