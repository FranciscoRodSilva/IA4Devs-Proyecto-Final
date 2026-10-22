"""Construcción de `Accion` del contrato de error (TKT-005, fila 2): TC-03, TC-04 y TC-05.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-R4). La fila 3 amplía este archivo con la familia de excepciones; aquí solo vive lo de
la acción y su filtrado por rol (M5): nunca se ofrece una acción que daría `403`, con una
salvedad: `REINTENTAR` de una `ConcurrenciaVencida` no se filtra por rol (CA-5), porque repite la
operación que quien llama acaba de invocar.

`contrato_error` se importa dentro de las ayudas, no al principio del archivo: así cada prueba
falla por separado mientras el paquete no existe y la fila 3 puede añadir los nombres de
`excepciones.py` sin que un `ImportError` de ellos tumbe la colección de las pruebas de esta fila.
"""

import functools
import importlib
import json
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento

RAIZ = Path(__file__).resolve().parents[2]

CID = "c3d4e5f6-a7b8-4901-8cde-f01234567890"

RUTA_REQUISICION = "/api/v1/requisiciones/4d2a9f1c-3b7e-4e5a-8c6d-2f1e0a9b8c7d"

SEIS_ROLES = frozenset(
    {"DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"}
)


def todos_los_roles() -> Any:
    return importlib.import_module("contrato_error.catalogos").TODOS_LOS_ROLES


def construir_accion(**cambios: Any) -> Any:
    """Una acción válida, con los campos que la prueba quiera estropear."""
    accion = importlib.import_module("contrato_error.acciones").Accion
    valida: dict[str, Any] = {
        "clave": "VER_REQUISICION",
        "metodo": "GET",
        "ruta": RUTA_REQUISICION,
        "roles_permitidos": SEIS_ROLES,
    }
    return accion(**{**valida, **cambios})


def test_tkt005_ca09_accion_se_serializa_sin_roles() -> None:
    """TC-03 · CA-9 esc. 1 — la acción sale con tres claves y sin los roles que la ejecutan (M5)."""
    accion_de_la_clase = importlib.import_module("contrato_error.acciones").Accion
    accion = accion_de_la_clase("VER_REQUISICION", "GET", RUTA_REQUISICION, todos_los_roles())

    assert accion.como_dict() == {
        "clave": "VER_REQUISICION",
        "metodo": "GET",
        "ruta": RUTA_REQUISICION,
    }
    assert "roles_permitidos" not in accion.como_dict()


@pytest.mark.parametrize(
    ("cambios", "citado"),
    [
        pytest.param({"clave": "ver"}, "'ver'", id="clave_en_minusculas"),
        pytest.param({"clave": ""}, "''", id="clave_vacia"),
        pytest.param({"clave": "VER-REQ"}, "'VER-REQ'", id="clave_con_guion"),
        pytest.param({"metodo": "HEAD"}, "'HEAD'", id="metodo_fuera_del_catalogo"),
        pytest.param({"ruta": "api/v1/x"}, "'api/v1/x'", id="ruta_sin_barra_inicial"),
        pytest.param({"ruta": "/otra/x"}, "'/otra/x'", id="ruta_sin_prefijo_del_api"),
        pytest.param({"ruta": "/api/v1/x y"}, "'/api/v1/x y'", id="ruta_con_espacio"),
        pytest.param({"ruta": "/api/v1/x\n"}, "'/api/v1/x\\n'", id="ruta_con_salto_de_linea"),
        pytest.param({"roles_permitidos": []}, "al menos un rol", id="sin_roles"),
        pytest.param(
            {"roles_permitidos": frozenset()}, "al menos un rol", id="conjunto_de_roles_vacio"
        ),
    ],
)
def test_tkt005_ca09_accion_rechaza_forma_invalida(cambios: dict[str, Any], citado: str) -> None:
    """TC-04 · CA-9 — una acción mal formada no se puede construir y el error cita lo recibido."""
    construir_accion()

    with pytest.raises(ValueError, match=re.escape(citado)):
        construir_accion(**cambios)


def test_tkt005_ca07_rol_fuera_del_catalogo() -> None:
    """TC-04 · CA-7 esc. 3 — un rol que no es de los seis del borrador no se puede construir."""
    with pytest.raises(ValueError, match=re.escape("'GERENTE'")):
        construir_accion(roles_permitidos=["GERENTE"])


@pytest.mark.parametrize(
    ("roles_de_la_accion", "roles_de_quien_llama", "esperado"),
    [
        pytest.param({"DIRECCION_GENERAL"}, {"DIRECCION_GENERAL"}, True, id="rol_exacto"),
        pytest.param({"DIRECCION_GENERAL"}, {"COMPRAS"}, False, id="rol_insuficiente"),
        pytest.param(
            {"ADMINISTRACION"},
            {"COMPRAS", "ADMINISTRACION"},
            True,
            id="union_de_roles_ofrece_la_accion",
        ),
        pytest.param(
            {"ADMINISTRACION"}, {"COMPRAS", "RESIDENTE"}, False, id="union_sin_el_rol_requerido"
        ),
        pytest.param(
            {"DIRECCION_GENERAL"}, set(), False, id="sin_roles_conocidos_accion_restringida"
        ),
        pytest.param(SEIS_ROLES, set(), False, id="sin_roles_conocidos_accion_de_todos"),
        pytest.param(
            {"DIRECCION_GENERAL"}, {"GERENTE"}, False, id="rol_desconocido_accion_restringida"
        ),
        pytest.param(SEIS_ROLES, {"GERENTE"}, False, id="rol_desconocido_accion_de_todos"),
        pytest.param(SEIS_ROLES, {"RESIDENTE"}, True, id="accion_de_todos_los_roles"),
    ],
)
def test_tkt005_ca09_permitida_para(
    roles_de_la_accion: frozenset[str] | set[str], roles_de_quien_llama: set[str], esperado: bool
) -> None:
    """TC-05 · CA-9 esc. 2 y 4 — se ofrece solo con un rol que pueda ejecutarla; sin roles conocidos, nunca."""
    accion = construir_accion(roles_permitidos=roles_de_la_accion)

    assert accion.permitida_para(frozenset(roles_de_quien_llama)) is esperado


# ---------------------------------------------------------------------------------------------
# Fila 3 · la familia de excepciones del contrato: TC-10 a TC-29 (`contrato_error.excepciones`).
#
# Un rechazo de construcción comprueba el tipo exacto de la excepción y que el mensaje cita lo
# recibido; antes de cada rechazo se construye el objeto válido, para que el rechazo se deba a lo
# que la prueba estropea y no a otra cosa. Un cuerpo se compara con el borrador OpenAPI y, además,
# por el conjunto exacto de sus claves: el borrador no declara `additionalProperties: false`.
# ---------------------------------------------------------------------------------------------

MENSAJE_RN03 = "La requisición excede el importe presupuestado del tipo de partida."
MENSAJE_CAMPO = "El campo es obligatorio."
RUTA_SOLICITUD = "/api/v1/solicitudes-autorizacion/9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b"
RUTA_TOPE = (
    "/api/v1/lineas-base/2f6c1d8e-7a3b-4c5d-9e0f-1a2b3c4d5e6f"
    "/presupuesto-control/8a7b6c5d-4e3f-4a2b-9c1d-0e9f8a7b6c5d"
)
RUTA_PAGO = "/api/v1/pagos/6c5d4e3f-2a1b-4c9d-8e7f-0a1b2c3d4e5f"

# clave -> (método, ruta, roles que pueden ejecutarla)
ACCIONES_CONOCIDAS: dict[str, tuple[str, str, frozenset[str]]] = {
    "VER_SOLICITUD_AUTORIZACION": (
        "GET",
        RUTA_SOLICITUD,
        frozenset({"COMPRAS", "DIRECCION_GENERAL"}),
    ),
    "CAPTURAR_PRESUPUESTO_CONTROL": ("PUT", RUTA_TOPE, frozenset({"DIRECCION_GENERAL"})),
    "VER_REQUISICION": ("GET", RUTA_REQUISICION, SEIS_ROLES),
    "REINTENTAR": ("POST", "/api/v1/requisiciones", SEIS_ROLES),
    "REVISAR_PAGO": ("GET", RUTA_PAGO, frozenset({"ADMINISTRACION"})),
}

CLASES_CON_MENSAJE = [
    "RechazoRegla",
    "ConflictoEstado",
    "ConcurrenciaVencida",
    "PermisoDenegado",
    "SesionInvalida",
    "LimiteIntentosExcedido",
    "NoEncontrado",
]

ESQUEMAS_DE_ERROR = [
    "ErrorReglaNegocio",
    "ErrorConflictoEstado",
    "ErrorConcurrencia",
    "ErrorValidacion",
    "ErrorPermiso",
    "ErrorSesion",
    "ErrorLimiteIntentos",
    "ErrorNoEncontrado",
]


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def clase(nombre: str) -> Any:
    """Una clase de `contrato_error.excepciones`, importada al usarla (ver el docstring del módulo)."""
    return getattr(importlib.import_module("contrato_error.excepciones"), nombre)


def accion_conocida(clave: str) -> Any:
    metodo, ruta, roles = ACCIONES_CONOCIDAS[clave]
    accion = importlib.import_module("contrato_error.acciones").Accion
    return accion(clave, metodo, ruta, roles)


def argumentos_validos(nombre: str) -> dict[str, Any]:
    """Los argumentos por nombre con los que cada clase con `mensaje` se construye sin error."""
    validos: dict[str, dict[str, Any]] = {
        "RechazoRegla": {
            "regla": "RN-03",
            "mensaje": MENSAJE_RN03,
            "detalle": {},
            "acciones": [],
        },
        "ConflictoEstado": {
            "codigo": "ESTADO_NO_PERMITE_OPERACION",
            "mensaje": "La operación no cabe en el estado actual.",
            "detalle": {},
            "acciones": [],
        },
        "ConcurrenciaVencida": {
            "codigo": "BLOQUEO_VENCIDO",
            "mensaje": "El presupuesto está en uso; vuelve a intentarlo.",
            "espera_maxima_ms": 5000,
            "reintentar_en_s": 1,
            "acciones": [accion_conocida("REINTENTAR")],
        },
        "PermisoDenegado": {
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": "Tu rol no puede hacer esto.",
            "roles_requeridos": ["DIRECCION_GENERAL"],
        },
        "SesionInvalida": {"motivo": "SIN_SESION", "mensaje": "No has iniciado sesión."},
        "LimiteIntentosExcedido": {
            "mensaje": "Demasiados intentos; espera un momento.",
            "reintentar_en_s": 30,
        },
        "NoEncontrado": {"recurso": "requisicion", "mensaje": "La requisición no existe."},
    }
    return validos[nombre]


def afirmar_json_llano(valor: object, ruta: str = "cuerpo") -> None:
    """Todo nodo del cuerpo es exactamente dict, list, str, int o bool: ni enumerados ni Decimal."""
    tipo = type(valor)
    assert tipo in (dict, list, str, int, bool), f"{ruta} es {tipo.__name__}: {valor!r}"
    if isinstance(valor, dict):
        for clave, interior in valor.items():
            assert type(clave) is str, f"La clave {clave!r} de {ruta} no es str"
            afirmar_json_llano(interior, f"{ruta}.{clave}")
    elif isinstance(valor, list):
        for posicion, interior in enumerate(valor):
            afirmar_json_llano(interior, f"{ruta}[{posicion}]")


def afirmar_cuerpo(cuerpo: dict[str, Any], esquema: str, claves: set[str]) -> None:
    """El cuerpo tiene exactamente estas claves, es JSON llano y valida contra su esquema del borrador."""
    assert set(cuerpo) == claves
    afirmar_json_llano(cuerpo)
    assert json.loads(json.dumps(cuerpo)) == cuerpo
    validar_contra(esquema, cuerpo)


def subclases_de(base: type) -> Iterator[Any]:
    subclases: list[type] = base.__subclasses__()
    for subclase in subclases:
        yield subclase
        yield from subclases_de(subclase)


@dataclass(frozen=True)
class ResultadoDePrueba:
    estado: str
    excedente: Dinero


def evaluar_de_prueba(disponible: Dinero, solicitado: Dinero) -> ResultadoDePrueba:
    """Función de regla de mentira, como las de `dominio/`: devuelve su resultado y nunca lanza."""
    if solicitado > disponible:
        return ResultadoDePrueba("BLOQUEADA", (solicitado - disponible).cuantizar())
    return ResultadoDePrueba("APROBADA", Dinero("0").cuantizar())


def caso_de_uso_de_prueba(
    disponible: Dinero, solicitado: Dinero, detalle: dict[str, object], acciones: list[Any]
) -> ResultadoDePrueba:
    """Caso de uso de mentira: es quien convierte el resultado BLOQUEADA en la excepción."""
    resultado = evaluar_de_prueba(disponible, solicitado)
    if resultado.estado == "BLOQUEADA":
        raise clase("RechazoRegla")(
            regla="RN-03",
            mensaje=MENSAJE_RN03,
            detalle={**detalle, "excedente": resultado.excedente},
            acciones=acciones,
        )
    return resultado


@pytest.fixture
def detalle_rn03() -> dict[str, object]:
    return {
        "obra": "AP-058-25 · Union Square F2",
        "tipo_partida": "MUROS",
        "presupuestado": Dinero("45000").cuantizar(),
        "consumido": Dinero("33000").cuantizar(),
        "disponible": Dinero("12000").cuantizar(),
        "solicitado": Dinero("15000").cuantizar(),
        "excedente": Dinero("3000").cuantizar(),
    }


@pytest.fixture
def ver_solicitud() -> Any:
    return accion_conocida("VER_SOLICITUD_AUTORIZACION")


@pytest.fixture
def capturar_tope() -> Any:
    return accion_conocida("CAPTURAR_PRESUPUESTO_CONTROL")


@pytest.fixture
def ver_requisicion() -> Any:
    return accion_conocida("VER_REQUISICION")


@pytest.fixture
def reintentar() -> Any:
    return accion_conocida("REINTENTAR")


def cifras_rn03_como_cadena() -> dict[str, str]:
    return {
        "presupuestado": "45000.0000",
        "consumido": "33000.0000",
        "disponible": "12000.0000",
        "solicitado": "15000.0000",
        "excedente": "3000.0000",
    }


def test_tkt005_ca01_rechazo_regla_produce_su_cuerpo(
    detalle_rn03: dict[str, object], ver_solicitud: Any
) -> None:
    """TC-10 · CA-1 esc. 1 — el rechazo de RN-03 produce su cuerpo exacto, con las cinco cifras como cadena."""
    rechazo = clase("RechazoRegla")(
        regla="RN-03", mensaje=MENSAJE_RN03, detalle=detalle_rn03, acciones=[ver_solicitud]
    )

    cuerpo = rechazo.cuerpo(frozenset({"COMPRAS"}), CID)

    assert cuerpo == {
        "tipo": "REGLA_NEGOCIO",
        "regla": "RN-03",
        "mensaje": MENSAJE_RN03,
        "detalle": {
            "obra": "AP-058-25 · Union Square F2",
            "tipo_partida": "MUROS",
            **cifras_rn03_como_cadena(),
        },
        "acciones": [
            {"clave": "VER_SOLICITUD_AUTORIZACION", "metodo": "GET", "ruta": RUTA_SOLICITUD}
        ],
        "correlacion_id": CID,
    }
    afirmar_cuerpo(
        cuerpo,
        "ErrorReglaNegocio",
        {"tipo", "regla", "mensaje", "detalle", "acciones", "correlacion_id"},
    )
    validar_contra("DetalleExcedePresupuesto", cuerpo["detalle"])
    assert rechazo.estado_http == 409
    assert rechazo.tipo == "REGLA_NEGOCIO"
    assert rechazo.cabeceras() == {}


def test_tkt005_ca01_una_sola_excepcion_de_regla() -> None:
    """TC-11 · CA-1 esc. 3, CA-13 — hay una excepción por tipo del borrador y una sola para todas las reglas."""
    base = clase("ErrorContrato")
    rechazo = clase("RechazoRegla")
    del_borrador = {
        borrador()["components"]["schemas"][esquema]["properties"]["tipo"]["const"]
        for esquema in ESQUEMAS_DE_ERROR
    }
    clases = list(subclases_de(base))

    assert len(del_borrador) == 8
    assert {c.tipo for c in clases} == del_borrador
    assert len(clases) == 8, [c.__name__ for c in clases]
    assert [c for c in clases if c.tipo == "REGLA_NEGOCIO"] == [rechazo]
    assert rechazo.__subclasses__() == []
    assert not any(isinstance(vars(c).get("regla"), str) for c in [base, *clases])


def test_tkt005_ca01_la_funcion_de_regla_no_lanza(
    detalle_rn03: dict[str, object], ver_solicitud: Any
) -> None:
    """TC-12 · CA-1 esc. 2, PA-T1 — la función de regla devuelve BLOQUEADA y solo el caso de uso lanza."""
    rechazo = clase("RechazoRegla")
    disponible = Dinero("12000").cuantizar()
    solicitado = Dinero("15000").cuantizar()

    resultado = evaluar_de_prueba(disponible, solicitado)

    assert not isinstance(resultado, BaseException)
    assert resultado.estado == "BLOQUEADA"
    assert resultado.excedente == Dinero("3000").cuantizar()
    with pytest.raises(rechazo) as error:
        caso_de_uso_de_prueba(disponible, solicitado, detalle_rn03, [ver_solicitud])
    cuerpo = error.value.cuerpo(frozenset({"COMPRAS"}), CID)
    assert cuerpo["regla"] == "RN-03"
    assert cuerpo["detalle"]["excedente"] == "3000.0000"
    dentro = caso_de_uso_de_prueba(disponible, Dinero("12000").cuantizar(), detalle_rn03, [])
    assert dentro.estado == "APROBADA"


REGLAS_MAL_FORMADAS = [
    pytest.param("RN03", id="sin_guion"),
    pytest.param("RN-A", id="letra_en_lugar_de_digitos"),
    pytest.param("rn-03", id="minusculas"),
    pytest.param("RN-03 ", id="espacio_al_final"),
    pytest.param("RNF-13", id="requisito_no_funcional"),
    pytest.param("", id="vacia"),
    pytest.param("RN-03\n", id="salto_de_linea_al_final"),
    pytest.param("RN-٠٣", id="digitos_arabe_indicos"),
]


@pytest.mark.parametrize("valor", REGLAS_MAL_FORMADAS)
def test_tkt005_ca02_regla_mal_formada(valor: str) -> None:
    """TC-13 · CA-2 — un identificador de regla mal formado no se puede construir y el error lo cita."""
    rechazo = clase("RechazoRegla")
    argumentos = argumentos_validos("RechazoRegla")
    rechazo(**argumentos)

    with pytest.raises(ValueError, match=re.escape(repr(valor))):
        rechazo(**{**argumentos, "regla": valor})


@pytest.mark.parametrize("valor", REGLAS_MAL_FORMADAS)
def test_tkt005_ca02_validar_regla_rechaza_lo_mal_formado(valor: str) -> None:
    """TC-13 · CA-2 — `validar_regla` rechaza cada identificador mal formado citando el valor."""
    validar_regla = clase("validar_regla")
    assert validar_regla("RN-03") == "RN-03"

    with pytest.raises(ValueError, match=re.escape(repr(valor))):
        validar_regla(valor)


def test_tkt005_ca02_regla_que_no_es_cadena() -> None:
    """TC-13 · CA-2 — un identificador de regla que no es cadena es TypeError y nombra el tipo."""
    rechazo = clase("RechazoRegla")
    argumentos = argumentos_validos("RechazoRegla")
    rechazo(**argumentos)

    with pytest.raises(TypeError, match="int"):
        rechazo(**{**argumentos, "regla": 3})
    with pytest.raises(TypeError, match="int"):
        clase("validar_regla")(3)


def test_tkt005_ca02_reglas_validas_se_construyen() -> None:
    """TC-13 · CA-2 — RN-01 y RN-25, los extremos del PRD, son identificadores válidos."""
    rechazo = clase("RechazoRegla")
    argumentos = argumentos_validos("RechazoRegla")

    for regla in ("RN-01", "RN-25"):
        cuerpo = rechazo(**{**argumentos, "regla": regla}).cuerpo(frozenset(), CID)
        assert cuerpo["regla"] == regla


def test_tkt005_ca03_dinero_cuantizado_viaja_como_cadena(
    detalle_rn03: dict[str, object], ver_solicitud: Any
) -> None:
    """TC-14 · CA-3 esc. 1 — un Dinero cuantizado sale como cadena de cuatro decimales, no como número."""
    rechazo = clase("RechazoRegla")(
        regla="RN-03", mensaje=MENSAJE_RN03, detalle=detalle_rn03, acciones=[ver_solicitud]
    )

    cuerpo = rechazo.cuerpo(frozenset({"COMPRAS"}), CID)

    assert type(cuerpo["detalle"]["presupuestado"]) is str
    assert '"presupuestado": "45000.0000"' in json.dumps(cuerpo)
    assert "45000," not in json.dumps(cuerpo)


def test_tkt005_ca03_detalle_admite_los_tipos_del_contrato() -> None:
    """TC-14 (ampliación) · CA-3 — el detalle admite los cuatro tipos de tipos_base, UUID, bool, int, listas y mapas."""
    identificador = uuid.UUID("9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b")
    argumentos = argumentos_validos("RechazoRegla")
    detalle = {
        "importe": Dinero("45000").cuantizar(),
        "cantidad": Cantidad("5").cuantizar(),
        "rendimiento": Rendimiento("0.5").cuantizar(),
        "avance": Porcentaje("0.25").cuantizar(),
        "insumo_id": identificador,
        "bloqueada": True,
        "renglones": 3,
        "lineas": [{"n": 1, "monto": Dinero("1").cuantizar()}],
        "etiquetas": ("a", "b"),
    }

    cuerpo = clase("RechazoRegla")(**{**argumentos, "detalle": detalle}).cuerpo(frozenset(), CID)

    assert cuerpo["detalle"] == {
        "importe": "45000.0000",
        "cantidad": "5.0000",
        "rendimiento": "0.500000",
        "avance": "0.250000",
        "insumo_id": str(identificador),
        "bloqueada": True,
        "renglones": 3,
        "lineas": [{"n": 1, "monto": "1.0000"}],
        "etiquetas": ["a", "b"],
    }
    afirmar_json_llano(cuerpo)


DETALLES_NO_ADMITIDOS = [
    pytest.param({"consumido": 33000.0}, ("float", "detalle.consumido"), id="float"),
    pytest.param(
        {"desglose": {"comprometido": 1.5}},
        ("float", "detalle.desglose.comprometido"),
        id="float_anidado",
    ),
    pytest.param({"renglones": [1.5]}, ("float", "detalle.renglones[0]"), id="float_en_lista"),
    pytest.param(
        {"consumido": Decimal("33000.0000")}, ("Decimal", "detalle.consumido"), id="decimal_suelto"
    ),
    pytest.param({"x": None}, ("NoneType", "detalle.x"), id="none"),
    pytest.param({1: "a"}, ("clave", "detalle"), id="clave_que_no_es_cadena"),
    pytest.param([("consumido", 1)], ("list", "detalle"), id="detalle_que_es_lista"),
]


@pytest.mark.parametrize("nombre", ["RechazoRegla", "ConflictoEstado"])
@pytest.mark.parametrize(("detalle", "citado"), DETALLES_NO_ADMITIDOS)
def test_tkt005_ca03_detalle_rechaza_float_y_decimal(
    nombre: str, detalle: object, citado: tuple[str, str]
) -> None:
    """TC-15 · CA-3 esc. 2 — un float, un Decimal suelto o un None en el detalle no se construye y el error los nombra."""
    argumentos = argumentos_validos(nombre)
    clase(nombre)(**argumentos)

    with pytest.raises(TypeError) as error:
        clase(nombre)(**{**argumentos, "detalle": detalle})

    for fragmento in citado:
        assert fragmento in str(error.value), str(error.value)


@pytest.mark.parametrize("nombre", ["RechazoRegla", "ConflictoEstado"])
def test_tkt005_ca03_importe_sin_cuantizar_no_se_redondea(nombre: str) -> None:
    """TC-16 · CA-3 esc. 3, CA-R7 — un importe sin cuantizar falla con el error de serializar(), sin redondear."""
    argumentos = argumentos_validos(nombre)
    clase(nombre)(**{**argumentos, "detalle": {"disponible": Dinero("12000.00").cuantizar()}})

    with pytest.raises(ValueError, match="cuantizar") as error:
        clase(nombre)(**{**argumentos, "detalle": {"disponible": Dinero("12000.00005")}})

    assert "12000.0001" not in str(error.value)


def test_tkt005_ca04_conflicto_sin_regla() -> None:
    """TC-17 · CA-4 esc. 1 — un conflicto de SIN_LINEA_BASE_CONGELADA responde CONFLICTO y nunca lleva regla."""
    conflicto = clase("ConflictoEstado")(
        codigo="SIN_LINEA_BASE_CONGELADA",
        mensaje="La obra no tiene línea base congelada.",
        detalle={"obra": "AP-058-25 · Union Square F2"},
        acciones=[],
    )

    cuerpo = conflicto.cuerpo(frozenset({"COMPRAS"}), CID)

    assert cuerpo == {
        "tipo": "CONFLICTO",
        "codigo": "SIN_LINEA_BASE_CONGELADA",
        "mensaje": "La obra no tiene línea base congelada.",
        "detalle": {"obra": "AP-058-25 · Union Square F2"},
        "acciones": [],
        "correlacion_id": CID,
    }
    afirmar_cuerpo(
        cuerpo,
        "ErrorConflictoEstado",
        {"tipo", "codigo", "mensaje", "detalle", "acciones", "correlacion_id"},
    )
    assert "regla" not in cuerpo
    assert conflicto.estado_http == 409
    assert conflicto.cabeceras() == {}


def test_tkt005_ca04_codigo_fuera_del_catalogo_no_se_construye() -> None:
    """TC-18 · CA-4 esc. 3 — un código fuera del catálogo cerrado no construye el conflicto."""
    conflicto = clase("ConflictoEstado")
    argumentos = argumentos_validos("ConflictoEstado")
    conflicto(**argumentos)

    with pytest.raises(ValueError, match="SOLICITUD_YA_USADA"):
        conflicto(**{**argumentos, "codigo": "SOLICITUD_YA_USADA"})


def test_tkt005_ca04_conflicto_no_admite_regla() -> None:
    """TC-19 · CA-4 esc. 4 — un conflicto no admite el argumento regla: su cuerpo nunca la lleva."""
    conflicto = clase("ConflictoEstado")
    argumentos = argumentos_validos("ConflictoEstado")
    conflicto(**argumentos)

    with pytest.raises(TypeError, match="regla"):
        conflicto(**argumentos, regla="RN-03")


def test_tkt005_ca05_concurrencia_con_cabecera_y_reintentar(reintentar: Any) -> None:
    """TC-20 · CA-5 esc. 1 — el vencimiento del bloqueo lleva Retry-After, la espera máxima y REINTENTAR."""
    vencida = clase("ConcurrenciaVencida")(
        codigo="BLOQUEO_VENCIDO",
        mensaje="El presupuesto está en uso; vuelve a intentarlo.",
        espera_maxima_ms=5000,
        reintentar_en_s=1,
        acciones=[reintentar],
    )

    cuerpo = vencida.cuerpo(frozenset({"COMPRAS"}), CID)

    assert cuerpo == {
        "tipo": "CONCURRENCIA",
        "codigo": "BLOQUEO_VENCIDO",
        "mensaje": "El presupuesto está en uso; vuelve a intentarlo.",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [{"clave": "REINTENTAR", "metodo": "POST", "ruta": "/api/v1/requisiciones"}],
        "correlacion_id": CID,
    }
    afirmar_cuerpo(
        cuerpo,
        "ErrorConcurrencia",
        {"tipo", "codigo", "mensaje", "detalle", "acciones", "correlacion_id"},
    )
    assert "regla" not in cuerpo
    assert vencida.estado_http == 409
    assert vencida.cabeceras() == {"Retry-After": "1"}


@pytest.mark.parametrize(
    ("cambios", "excepcion", "citado"),
    [
        pytest.param({"acciones": ()}, ValueError, "REINTENTAR", id="sin_acciones"),
        pytest.param(
            {"acciones": ("VER_REQUISICION",)},
            ValueError,
            "REINTENTAR",
            id="sin_la_accion_reintentar",
        ),
        pytest.param({"reintentar_en_s": -1}, ValueError, "-1", id="retry_after_negativo"),
        pytest.param({"espera_maxima_ms": -1}, ValueError, "-1", id="espera_negativa"),
        pytest.param({"codigo": "OTRO"}, ValueError, "'OTRO'", id="codigo_fuera_del_catalogo"),
        pytest.param({"reintentar_en_s": True}, TypeError, "bool", id="retry_after_booleano"),
    ],
)
def test_tkt005_ca05_concurrencia_fuera_de_contrato(
    cambios: dict[str, Any], excepcion: type[Exception], citado: str
) -> None:
    """TC-21 · CA-5 esc. 2, PA-T10 — una concurrencia sin REINTENTAR o con valores fuera de rango no se construye."""
    vencida = clase("ConcurrenciaVencida")
    argumentos = argumentos_validos("ConcurrenciaVencida")
    vencida(**argumentos)
    if "acciones" in cambios:
        cambios = {**cambios, "acciones": [accion_conocida(c) for c in cambios["acciones"]]}

    with pytest.raises(excepcion, match=re.escape(citado)):
        vencida(**{**argumentos, **cambios})


def test_tkt005_ca06_validacion_con_regla() -> None:
    """TC-22 · CA-6 esc. 3 y 5 — la validación lleva su regla cuando una regla impone la forma y cuenta los errores."""
    de_campo = clase("ErrorDeCampo")
    validacion = clase("ValidacionRechazada")
    con_regla = validacion(
        errores=[
            de_campo(
                campo="tipo_partida_id", codigo="OBLIGATORIO", mensaje=MENSAJE_CAMPO, regla="RN-02"
            )
        ]
    )
    sin_regla = validacion(
        errores=[
            de_campo(campo="nombre", codigo="OBLIGATORIO", mensaje=MENSAJE_CAMPO),
            de_campo(
                campo="cantidad", codigo="FORMATO", mensaje="El valor no tiene el formato esperado."
            ),
        ]
    )

    cuerpo_con_regla = con_regla.cuerpo(frozenset(), CID)
    cuerpo_sin_regla = sin_regla.cuerpo(frozenset(), CID)

    assert cuerpo_con_regla == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 1 campo inválido.",
        "errores": [
            {
                "campo": "tipo_partida_id",
                "codigo": "OBLIGATORIO",
                "mensaje": MENSAJE_CAMPO,
                "regla": "RN-02",
            }
        ],
        "correlacion_id": CID,
    }
    assert cuerpo_sin_regla["mensaje"] == "La petición tiene 2 campos inválidos."
    assert [e["campo"] for e in cuerpo_sin_regla["errores"]] == ["nombre", "cantidad"]
    assert all("regla" not in e for e in cuerpo_sin_regla["errores"])
    for cuerpo in (cuerpo_con_regla, cuerpo_sin_regla):
        afirmar_cuerpo(cuerpo, "ErrorValidacion", {"tipo", "mensaje", "errores", "correlacion_id"})
    assert con_regla.estado_http == 422
    assert con_regla.cabeceras() == {}


@pytest.mark.parametrize(
    ("cambios", "citado"),
    [
        pytest.param({"codigo": "DESCONOCIDO"}, "'DESCONOCIDO'", id="codigo_fuera_del_enum"),
        pytest.param({"regla": "RN3"}, "'RN3'", id="regla_mal_formada"),
        pytest.param({"campo": ""}, "vacío", id="campo_vacio"),
        pytest.param({"mensaje": "  "}, "vacío", id="mensaje_en_blanco"),
    ],
)
def test_tkt005_ca06_validacion_error_de_campo_fuera_de_contrato(
    cambios: dict[str, str], citado: str
) -> None:
    """TC-23 · CA-6 — un error de campo con código, regla, campo o mensaje fuera de contrato no se construye."""
    de_campo = clase("ErrorDeCampo")
    valido = {"campo": "nombre", "codigo": "OBLIGATORIO", "mensaje": MENSAJE_CAMPO}
    de_campo(**valido)

    with pytest.raises(ValueError, match=re.escape(citado)):
        de_campo(**{**valido, **cambios})


def test_tkt005_ca06_validacion_fuera_de_contrato() -> None:
    """TC-23 · CA-6 — una validación sin errores, o con un elemento que no es ErrorDeCampo, no se construye."""
    de_campo = clase("ErrorDeCampo")
    validacion = clase("ValidacionRechazada")
    valido = de_campo(campo="nombre", codigo="OBLIGATORIO", mensaje=MENSAJE_CAMPO)
    validacion(errores=[valido])

    with pytest.raises(ValueError):
        validacion(errores=[])
    with pytest.raises(TypeError):
        validacion(errores=[valido.como_dict()])


def test_tkt005_ca07_permiso_con_roles_requeridos() -> None:
    """TC-24 · CA-7 esc. 1 — el permiso negado lleva motivo y roles requeridos, sin detalle."""
    denegado = clase("PermisoDenegado")(
        motivo="ROL_INSUFICIENTE",
        mensaje="Solo la Dirección General puede capturar el tope.",
        roles_requeridos=["DIRECCION_GENERAL"],
    )

    cuerpo = denegado.cuerpo(frozenset({"COMPRAS"}), CID)

    assert cuerpo == {
        "tipo": "PERMISO",
        "motivo": "ROL_INSUFICIENTE",
        "mensaje": "Solo la Dirección General puede capturar el tope.",
        "roles_requeridos": ["DIRECCION_GENERAL"],
        "correlacion_id": CID,
    }
    afirmar_cuerpo(
        cuerpo, "ErrorPermiso", {"tipo", "motivo", "mensaje", "roles_requeridos", "correlacion_id"}
    )
    assert denegado.estado_http == 403
    assert denegado.cabeceras() == {}


@pytest.mark.parametrize(
    "motivo", ["ROL_INSUFICIENTE", "AUTO_RESOLUCION", "NO_ES_SOLICITANTE", "ORIGEN_NO_VERIFICADO"]
)
def test_tkt005_ca07_los_cuatro_motivos_del_borrador_construyen(motivo: str) -> None:
    """TC-24 · CA-7 esc. 3 — cada uno de los cuatro motivos del borrador construye un permiso válido."""
    denegado = clase("PermisoDenegado")(
        motivo=motivo, mensaje="No puedes hacer esto.", roles_requeridos=["RESIDENTE"]
    )

    cuerpo = denegado.cuerpo(frozenset(), CID)

    assert cuerpo["motivo"] == motivo
    afirmar_cuerpo(
        cuerpo, "ErrorPermiso", {"tipo", "motivo", "mensaje", "roles_requeridos", "correlacion_id"}
    )


def test_tkt005_ca07_permiso_no_admite_detalle() -> None:
    """TC-25 · CA-7 esc. 2 — un permiso nunca lleva cifras del recurso: no admite detalle."""
    denegado = clase("PermisoDenegado")
    argumentos = argumentos_validos("PermisoDenegado")
    denegado(**argumentos)

    with pytest.raises(TypeError, match="detalle"):
        denegado(**argumentos, detalle={"importe": Dinero("1").cuantizar()})


def test_tkt005_ca07_motivo_o_rol_fuera_de_contrato() -> None:
    """TC-26 · CA-7 esc. 3 — un motivo o un rol fuera de los enumerados no construye el permiso."""
    denegado = clase("PermisoDenegado")
    argumentos = argumentos_validos("PermisoDenegado")
    denegado(**argumentos)

    with pytest.raises(ValueError, match="PROHIBIDO"):
        denegado(**{**argumentos, "motivo": "PROHIBIDO"})
    with pytest.raises(ValueError, match="GERENTE"):
        denegado(**{**argumentos, "roles_requeridos": ["GERENTE"]})


@pytest.mark.parametrize(
    ("nombre", "estado", "cabeceras", "esquema", "tipo"),
    [
        pytest.param("SesionInvalida", 401, {}, "ErrorSesion", "SESION", id="sesion"),
        pytest.param(
            "LimiteIntentosExcedido",
            429,
            {"Retry-After": "30"},
            "ErrorLimiteIntentos",
            "LIMITE_INTENTOS",
            id="limite_de_intentos",
        ),
        pytest.param(
            "NoEncontrado", 404, {}, "ErrorNoEncontrado", "NO_ENCONTRADO", id="no_encontrado"
        ),
    ],
)
def test_tkt005_ca08_sesion_limite_y_no_encontrado(
    nombre: str, estado: int, cabeceras: dict[str, str], esquema: str, tipo: str
) -> None:
    """TC-27 · CA-8 esc. 1 a 3 — sesión, límite de intentos y recurso inexistente producen su cuerpo y su cabecera."""
    argumentos = argumentos_validos(nombre)
    error = clase(nombre)(**argumentos)

    cuerpo = error.cuerpo(frozenset({"COMPRAS"}), CID)

    assert cuerpo == {"tipo": tipo, **argumentos, "correlacion_id": CID}
    afirmar_cuerpo(cuerpo, esquema, {"tipo", "correlacion_id", *argumentos})
    assert error.estado_http == estado
    assert error.cabeceras() == cabeceras


@pytest.mark.parametrize(
    ("nombre", "cambios", "excepcion", "citado"),
    [
        pytest.param(
            "SesionInvalida",
            {"motivo": "EXPIRADA"},
            ValueError,
            "'EXPIRADA'",
            id="motivo_de_sesion",
        ),
        pytest.param(
            "LimiteIntentosExcedido",
            {"reintentar_en_s": -1},
            ValueError,
            "-1",
            id="espera_negativa",
        ),
        pytest.param(
            "LimiteIntentosExcedido",
            {"reintentar_en_s": 30.0},
            TypeError,
            "float",
            id="espera_con_decimales",
        ),
        pytest.param("NoEncontrado", {"recurso": ""}, ValueError, "vacío", id="recurso_vacio"),
    ],
)
def test_tkt005_ca08_sesion_limite_y_no_encontrado_fuera_de_contrato(
    nombre: str, cambios: dict[str, Any], excepcion: type[Exception], citado: str
) -> None:
    """TC-27 · CA-8 esc. 5 — un motivo de sesión, una espera o un recurso fuera de contrato no se construyen."""
    argumentos = argumentos_validos(nombre)
    clase(nombre)(**argumentos)

    with pytest.raises(excepcion, match=re.escape(citado)):
        clase(nombre)(**{**argumentos, **cambios})


def rechazo_con(acciones: list[Any], detalle: dict[str, object] | None = None) -> Any:
    return clase("RechazoRegla")(
        regla="RN-03",
        mensaje=MENSAJE_RN03,
        detalle={"obra": "AP-058-25 · Union Square F2"} if detalle is None else detalle,
        acciones=acciones,
    )


def test_tkt005_ca09_acciones_filtradas_en_el_cuerpo(
    capturar_tope: Any, ver_requisicion: Any
) -> None:
    """TC-28 · CA-9 esc. 1 — el mismo rechazo ofrece a Dirección General las dos acciones y a Compras solo una."""
    rechazo = rechazo_con([capturar_tope, ver_requisicion])

    de_direccion = rechazo.cuerpo(frozenset({"DIRECCION_GENERAL"}), CID)
    de_compras = rechazo.cuerpo(frozenset({"COMPRAS"}), CID)

    assert [a["clave"] for a in de_direccion["acciones"]] == [
        "CAPTURAR_PRESUPUESTO_CONTROL",
        "VER_REQUISICION",
    ]
    assert de_compras["acciones"] == [
        {"clave": "VER_REQUISICION", "metodo": "GET", "ruta": RUTA_REQUISICION}
    ]
    validar_contra("ErrorReglaNegocio", de_direccion)
    validar_contra("ErrorReglaNegocio", de_compras)


def test_tkt005_ca09_union_de_roles_ofrece_la_accion() -> None:
    """TC-28 · CA-9 esc. 2 — quien tiene COMPRAS y ADMINISTRACION recibe la acción que solo ADMINISTRACION ejecuta."""
    rechazo = rechazo_con([accion_conocida("REVISAR_PAGO")])

    cuerpo = rechazo.cuerpo(frozenset({"COMPRAS", "ADMINISTRACION"}), CID)
    de_solo_compras = rechazo.cuerpo(frozenset({"COMPRAS"}), CID)

    assert [a["clave"] for a in cuerpo["acciones"]] == ["REVISAR_PAGO"]
    assert de_solo_compras["acciones"] == []


def test_tkt005_ca09_nunca_se_ofrece_una_accion_que_daria_403(capturar_tope: Any) -> None:
    """TC-28 · CA-9 esc. 3 — a un RESIDENTE no se le ofrece la acción de Dirección General y el rechazo conserva su contenido."""
    rechazo = rechazo_con([capturar_tope])

    cuerpo = rechazo.cuerpo(frozenset({"RESIDENTE"}), CID)

    assert cuerpo["acciones"] == []
    assert cuerpo["regla"] == "RN-03"
    assert cuerpo["mensaje"] == MENSAJE_RN03
    assert cuerpo["detalle"] == {"obra": "AP-058-25 · Union Square F2"}
    validar_contra("ErrorReglaNegocio", cuerpo)


def test_tkt005_ca09_sin_roles_conocidos_no_se_ofrece_ninguna_accion(
    capturar_tope: Any, ver_requisicion: Any
) -> None:
    """TC-28 · CA-9 esc. 4 — sin roles conocidos no se ofrece ninguna acción, tampoco la de todos los roles."""
    rechazo = rechazo_con([capturar_tope, ver_requisicion])

    cuerpo = rechazo.cuerpo(frozenset(), CID)

    assert cuerpo["acciones"] == []
    assert cuerpo["regla"] == "RN-03"
    validar_contra("ErrorReglaNegocio", cuerpo)


@pytest.mark.parametrize(
    ("nombre", "claves_sin_roles"),
    [
        pytest.param("ConflictoEstado", [], id="conflicto_sin_roles_no_ofrece_nada"),
        # Ajustado en el ciclo de corrección 1 (arquitectura F001): REINTENTAR de una concurrencia
        # no se filtra por rol, así que sin roles conocidos sigue ofreciéndose (CA-5).
        pytest.param(
            "ConcurrenciaVencida",
            ["REINTENTAR"],
            id="concurrencia_sin_roles_conserva_reintentar",
        ),
    ],
)
def test_tkt005_ca09_el_filtrado_rige_para_toda_clase_con_acciones(
    nombre: str, claves_sin_roles: list[str], capturar_tope: Any, reintentar: Any
) -> None:
    """TC-28 (ampliación) · CA-9 — el conflicto y la concurrencia filtran sus acciones restringidas igual que la regla.

    La única excepción es `REINTENTAR` de la concurrencia (CA-5, ver `test_tkt005_ca05_reintentar_*`):
    sin roles conocidos, la concurrencia lo conserva y el conflicto no ofrece nada.
    """
    argumentos = argumentos_validos(nombre)
    error = clase(nombre)(**{**argumentos, "acciones": [capturar_tope, reintentar]})

    de_compras = error.cuerpo(frozenset({"COMPRAS"}), CID)
    sin_roles = error.cuerpo(frozenset(), CID)

    claves_de_compras = [a["clave"] for a in de_compras["acciones"]]
    assert "CAPTURAR_PRESUPUESTO_CONTROL" not in claves_de_compras
    assert claves_de_compras == ["REINTENTAR"]
    assert [a["clave"] for a in sin_roles["acciones"]] == claves_sin_roles


@pytest.mark.parametrize("nombre", CLASES_CON_MENSAJE)
@pytest.mark.parametrize(
    ("mensaje", "excepcion", "citado"),
    [
        pytest.param("", ValueError, "vacío", id="vacio"),
        pytest.param("   ", ValueError, "vacío", id="en_blanco"),
        pytest.param(None, TypeError, "mensaje", id="none"),
    ],
)
def test_tkt005_ca13_mensaje_obligatorio(
    nombre: str, mensaje: object, excepcion: type[Exception], citado: str
) -> None:
    """TC-29 · CA-13 — las siete clases con mensaje rechazan el vacío, el blanco y el None."""
    argumentos = argumentos_validos(nombre)
    clase(nombre)(**argumentos)

    with pytest.raises(excepcion, match=citado):
        clase(nombre)(**{**argumentos, "mensaje": mensaje})


# ---------------------------------------------------------------------------------------------
# Ciclo de corrección 1 · arquitectura F001 (Mayor): `REINTENTAR` de una concurrencia no se filtra.
#
# Decisión de diseño del orquestador: `REINTENTAR` repite la operación que quien llama acaba de
# invocar, así que se ofrece siempre —con o sin roles conocidos, con un rol ajeno al de la acción—.
# El resto de las acciones de una concurrencia sí se filtra por rol (M5), y las demás clases
# (`RechazoRegla`, `ConflictoEstado`) filtran todo como antes. Sin esto, CA-5 («ningún vencimiento
# llega al cliente sin una salida documentada») se rompe con `acciones: []`.
# ---------------------------------------------------------------------------------------------

RUTA_REINTENTAR = "/api/v1/requisiciones"


def reintentar_solo_de_compras() -> Any:
    """`REINTENTAR` cuya lista de roles no incluye a quien llama en las pruebas de abajo."""
    accion = importlib.import_module("contrato_error.acciones").Accion
    return accion("REINTENTAR", "POST", RUTA_REINTENTAR, frozenset({"COMPRAS"}))


def concurrencia_con(acciones: list[Any]) -> Any:
    argumentos = argumentos_validos("ConcurrenciaVencida")
    return clase("ConcurrenciaVencida")(**{**argumentos, "acciones": acciones})


REINTENTAR_ESPERADO = {"clave": "REINTENTAR", "metodo": "POST", "ruta": RUTA_REINTENTAR}


@pytest.mark.parametrize(
    "roles_de_quien_llama",
    [
        pytest.param(frozenset(), id="sin_roles_conocidos"),
        pytest.param(frozenset({"ALMACEN"}), id="rol_ajeno_al_de_la_accion"),
        pytest.param(frozenset({"GERENTE"}), id="rol_fuera_del_catalogo"),
        pytest.param(frozenset({"ALMACEN", "RESIDENTE"}), id="varios_roles_ajenos"),
    ],
)
def test_tkt005_ca05_reintentar_se_ofrece_aunque_el_rol_no_lo_liste(
    roles_de_quien_llama: frozenset[str],
) -> None:
    """CA-5 esc. 1 · RNF-16 · F001 — la concurrencia conserva REINTENTAR sin roles o con un rol ajeno."""
    vencida = concurrencia_con([reintentar_solo_de_compras()])

    cuerpo = vencida.cuerpo(roles_de_quien_llama, CID)

    assert cuerpo["acciones"] == [REINTENTAR_ESPERADO]
    assert vencida.cabeceras() == {"Retry-After": "1"}


@pytest.mark.parametrize(
    "roles_de_quien_llama",
    [
        pytest.param(frozenset(), id="sin_roles_conocidos"),
        pytest.param(frozenset({"ALMACEN"}), id="rol_ajeno_al_de_la_accion"),
    ],
)
def test_tkt005_ca05_concurrencia_sin_reintentar_filtrado_valida_el_esquema(
    roles_de_quien_llama: frozenset[str],
) -> None:
    """CA-5 esc. 1 · F001 — el cuerpo completo de la concurrencia, sin roles o con rol ajeno, valida contra ErrorConcurrencia."""
    vencida = concurrencia_con([reintentar_solo_de_compras()])

    cuerpo = vencida.cuerpo(roles_de_quien_llama, CID)

    assert cuerpo == {
        "tipo": "CONCURRENCIA",
        "codigo": "BLOQUEO_VENCIDO",
        "mensaje": "El presupuesto está en uso; vuelve a intentarlo.",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [REINTENTAR_ESPERADO],
        "correlacion_id": CID,
    }
    afirmar_cuerpo(
        cuerpo,
        "ErrorConcurrencia",
        {"tipo", "codigo", "mensaje", "detalle", "acciones", "correlacion_id"},
    )
    assert cuerpo["acciones"], (
        "CA-5: ningún vencimiento llega al cliente sin una salida documentada"
    )


def test_tkt005_ca05_la_segunda_accion_restringida_si_se_omite(capturar_tope: Any) -> None:
    """CA-5 · CA-9 · F001 — junto a REINTENTAR, una acción restringida de la misma concurrencia solo la ve su rol."""
    vencida = concurrencia_con([capturar_tope, reintentar_solo_de_compras()])

    de_almacen = vencida.cuerpo(frozenset({"ALMACEN"}), CID)
    sin_roles = vencida.cuerpo(frozenset(), CID)
    de_direccion = vencida.cuerpo(frozenset({"DIRECCION_GENERAL"}), CID)

    assert de_almacen["acciones"] == [REINTENTAR_ESPERADO]
    assert sin_roles["acciones"] == [REINTENTAR_ESPERADO]
    assert [a["clave"] for a in de_direccion["acciones"]] == [
        "CAPTURAR_PRESUPUESTO_CONTROL",
        "REINTENTAR",
    ]
    for cuerpo in (de_almacen, sin_roles, de_direccion):
        validar_contra("ErrorConcurrencia", cuerpo)


def test_tkt005_ca09_reintentar_de_un_conflicto_sigue_filtrado() -> None:
    """CA-9 · F001 (control, nace en verde) — la excepción de REINTENTAR es solo de la concurrencia: un conflicto lo filtra por rol."""
    conflicto = clase("ConflictoEstado")(
        **{
            **argumentos_validos("ConflictoEstado"),
            "acciones": [reintentar_solo_de_compras()],
        }
    )

    de_almacen = conflicto.cuerpo(frozenset({"ALMACEN"}), CID)
    de_compras = conflicto.cuerpo(frozenset({"COMPRAS"}), CID)

    assert de_almacen["acciones"] == []
    assert de_compras["acciones"] == [REINTENTAR_ESPERADO]
