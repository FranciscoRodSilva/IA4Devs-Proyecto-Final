"""API de obras, fila A4 de TKT-012a: `crear_obra`, `listar_obras` y `obtener_obra` (TC-14 a TC-31).

Cubre `CA-1` a `CA-8` y `CA-R1` de la spec (`HDU-001` esc. 2, 3 y 14; `RN-25`, `PA-02`, `PA-18`) contra
PostgreSQL migrado con `alembic upgrade head` y el rol de aplicación, por la aplicación real
(`crear_aplicacion`) y un `TestClient` HTTPS. Las ayudas son solo las de `herramientas.soporte_tkt017_api`.

Empresa única (nota de ejecución del diseño): la migración `0008` siembra la única empresa activa y el
alta la toma. El fixture `entorno` de TKT-017 y `DatosPresupuesto.obra()` sin `empresa_id` crean otra
empresa activa, y con dos el alta responde `500` (A9). Por eso aquí **no** se usa `entorno`: las obras
previas se siembran con el `empresa_id` de la migración, y TC-31 construye `Entorno` después del alta.

Cada rechazo comprueba el contrato de error completo con `exigir_error` (`tipo`, `codigo`, `mensaje`
literal, `errores` o `detalle`, `acciones`, la correlación de la cabecera y la validez contra el esquema
del borrador) y que no cambió nada en la base. Los `403` comprueban además el `DENEGAR` asentado.

Rojo de la fila A4: las rutas `/api/v1/obras` no existen todavía, así que cada petición responde `404`
(`NO_ENCONTRADO` con la ruta como recurso) donde la prueba espera `200`, `201`, `401`, `403`, `404 obra`,
`409` o `422`, y el contrato publicado no trae `ObraNueva`, `Obra` ni `ListaObras`. Esta prueba no importa
ningún módulo nuevo de producción (todo entra por HTTP y por `/openapi.json`), así que no hay errores de
recolección ni de fixture: solo fallos de aserción por la ausencia de las rutas y los esquemas.

Hallazgos del tester que el desarrollador debe leer:

- E-2 (TC-25): con la configuración real de `manejar_validacion`, un `estado` fuera del enumerado en un
  `Query` de lista da `campo` `estado[0]` y `codigo` `VALOR_NO_PERMITIDO`. Comprobado en un experimento
  aparte (FastAPI y Pydantic con el mismo manejador), y es lo que esta prueba exige.
- E-3 (TC-30): Pydantic publica `Literal["X"]` de un solo valor como `const`, **sin `enum`**. El borrador
  declara `enum: [PRECIO_ALZADO_MAXIMO_GARANTIZADO]`, así que `tipo_contrato` necesita el respaldo del
  diseño (`json_schema_extra={"enum": [...]}`) y TC-30 lo exige.
- `actualizado_en`: el borrador lo declara `FechaHora` (cadena, no nula) y no obligatoria. Un `null` en la
  respuesta de una obra recién creada no valida contra el borrador y TC-30 compara la forma: el DTO `Obra`
  debe omitir el campo cuando no hay valor (o publicarlo sin `nulable`).

Mutantes que esta fila debe poner en rojo: `M-5` (`crear_obra` con `exigir_rol(*ROLES_LECTURA_OBRA)`) en
TC-19; ruta sin `verificar_origen` o con `exigir_rol` antes: TC-20, `..._el_origen_se_verifica_antes_...` y
`..._son_def_...`; roles ampliados en la lectura: ninguno (las lecturas admiten a los seis).
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`, `contexto`) se piden como parámetro: Ruff lo lee como
# F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`; aquí se exime en el archivo.
# ruff: noqa: F811

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from fastapi.testclient import TestClient

from herramientas.soporte_tkt017 import preparacion_dos_niveles
from herramientas.soporte_tkt017_api import (
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador,
    cabeceras_de,
    construir_aplicacion,
    contexto,  # noqa: F401
    diferencias_de_forma,
    exigir_denegacion,
    exigir_error,
    forma_de_componente,
    llamadas,
    parametros_de,
    resolver,
    rutas_de,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado
from herramientas.soporte_tkt017_entorno import Base, Contexto, Entorno, congelar

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto, RelojDePrueba

RUTA = "/api/v1/obras"
TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
ROLES_ALTA = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"]
SEIS_ROLES = [
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
]
ROLES_SIN_ALTA = ["RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"]
CLAVES_DE_OBRA = {
    "id",
    "codigo",
    "nombre",
    "domicilio",
    "tipo_contrato",
    "retencion_destajo_pct",
    "fondo_garantia_pct",
    "iva_acreditable",
    "umbral_alerta_pct",
    "estado",
    "linea_base_vigente_id",
    "creado_en",
}

MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_UN_CAMPO_INVALIDO = "La petición tiene 1 campo inválido."
MENSAJE_OBRA_NO_EXISTE = "La obra no existe."
MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."
MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."
MENSAJES_DE_VALIDACION = {
    "OBLIGATORIO": "El campo es obligatorio.",
    "FORMATO": "El valor no tiene el formato esperado.",
    "DEMASIADO_LARGO": "El valor excede la longitud máxima.",
    "VALOR_NO_PERMITIDO": "El valor no está entre los permitidos.",
    "FUERA_DE_RANGO": "El valor está fuera del rango permitido.",
}

AUSENTE = object()  # el campo no viaja en el cuerpo


# --------------------------------------------------------------------------- ayudas de la prueba


def _cuerpo(**cambios: object) -> dict[str, Any]:
    """El cuerpo de alta del borrador; `cambios` sustituye campos y `AUSENTE` los quita."""
    cuerpo: dict[str, Any] = {
        "codigo": "AP-058-25",
        "nombre": "Union Square F2",
        "domicilio": "Av. Insurgentes Sur 1458, Ciudad de México",
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": False,
        "umbral_alerta_pct": "0.150000",
    }
    for campo, valor in cambios.items():
        if valor is AUSENTE:
            del cuerpo[campo]
        else:
            cuerpo[campo] = valor
    return cuerpo


def _alta(
    cliente: TestClient,
    sesion: Sesion | None,
    cuerpo: dict[str, Any],
    *,
    cookie_csrf: str | None = TOKEN_CSRF,
    cabecera_csrf: str | None = TOKEN_CSRF,
) -> Any:
    """`POST /api/v1/obras` con la cookie de sesión y el par CSRF indicado (por omisión, uno válido)."""
    return cliente.post(
        RUTA,
        json=cuerpo,
        headers=cabeceras_de(
            None if sesion is None else sesion.sesion_id, cookie_csrf, cabecera_csrf
        ),
    )


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


def _exigir_nada_creado(base: Base) -> None:
    """Un rechazo no escribe: ni una fila en `obra` ni un asiento `CREAR`."""
    assert _cuenta(base, "SELECT count(*) FROM obra") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 0


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


def _sin_fechas(obra: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obra.items() if k not in {"creado_en", "actualizado_en"}}


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`): la que toma el alta."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


def _sembrar_obras(
    datos: DatosPresupuesto, empresa_id: uuid.UUID, estados_por_codigo: dict[str, str]
) -> dict[str, uuid.UUID]:
    """Obras previas, en el orden dado y con la empresa de la migración (no crean otra empresa activa)."""
    usuario = datos.usuario()
    return {
        codigo: datos.obra(
            codigo=codigo,
            empresa_id=empresa_id,
            creado_por_id=usuario,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=Decimal("0.100000"),
            iva_acreditable=True,
        )
        for codigo, estado in estados_por_codigo.items()
    }


def _obra_sembrada(codigo: str, obra_id: uuid.UUID, estado: str) -> dict[str, Any]:
    """La obra de `DatosPresupuesto.obra()` como la devuelve el API, sin las fechas."""
    return {
        "id": str(obra_id),
        "codigo": codigo,
        "nombre": f"Obra {codigo}",
        "domicilio": "Calle de prueba 1",
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": True,
        "umbral_alerta_pct": "0.100000",
        "estado": estado,
        "linea_base_vigente_id": None,
    }


# --------------------------------------------------------------------------- TC-14 · CA-1


@pytest.mark.parametrize("rol", ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"])
def test_hdu001_esc02_api_alta_responde_201(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    empresa_de_la_migracion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 2 · TC-14 · CA-1 · RN-25 · PA-02 — `201` con `Location` y la `Obra` exacta del borrador.

    Para Director de Proyectos y para Dirección General. Los dos porcentajes se guardan como dos valores
    distintos y vuelven con seis decimales; la obra nace en `PLANEACION` sin línea base vigente, con la
    empresa de la migración, quién la creó y cuándo, y un asiento `CREAR` (regla 8). El cuerpo con `"0.15"`
    responde `"0.150000"` y sin umbral devuelve `null`.
    """
    usuario = abrir_sesion((rol,))

    respuesta = _alta(cliente, usuario, _cuerpo())

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Obra", cuerpo)
    assert set(cuerpo) - {"actualizado_en"} == CLAVES_DE_OBRA
    obra_id = uuid.UUID(cuerpo["id"])
    assert respuesta.headers["Location"] == f"/api/v1/obras/{obra_id}"
    assert datetime.fromisoformat(cuerpo["creado_en"]) == reloj_de_prueba.ahora
    assert _sin_fechas(cuerpo) == {
        "id": str(obra_id),
        "codigo": "AP-058-25",
        "nombre": "Union Square F2",
        "domicilio": "Av. Insurgentes Sur 1458, Ciudad de México",
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": False,
        "umbral_alerta_pct": "0.150000",
        "estado": "PLANEACION",
        "linea_base_vigente_id": None,
    }
    assert base.filas(
        "SELECT codigo, retencion_destajo_pct, fondo_garantia_pct, iva_acreditable, umbral_alerta_pct, "
        "estado, empresa_id, creado_en, creado_por_id FROM obra WHERE id = %s",
        obra_id,
    ) == [
        (
            "AP-058-25",
            "0.150000",
            "0.050000",
            False,
            "0.150000",
            "PLANEACION",
            empresa_de_la_migracion,
            reloj_de_prueba.ahora,
            usuario.usuario_id,
        )
    ]
    assert base.filas(
        "SELECT entidad_tipo, entidad_id, usuario_id, obra_id, ocurrido_en FROM bitacora "
        "WHERE accion = 'CREAR'"
    ) == [("obra", obra_id, usuario.usuario_id, obra_id, reloj_de_prueba.ahora)]
    assert _cuenta(base, "SELECT count(*) FROM linea_base") == 0

    # Variante: con `"0.15"` y `"0.05"` y sin umbral, la respuesta trae seis decimales y `null`.
    segunda = _alta(
        cliente,
        usuario,
        _cuerpo(
            codigo="AP-014-26",
            retencion_destajo_pct="0.15",
            fondo_garantia_pct="0.05",
            umbral_alerta_pct=AUSENTE,
            iva_acreditable=True,
        ),
    )
    assert segunda.status_code == 201, segunda.text
    validar_contra("Obra", segunda.json())
    assert segunda.json()["retencion_destajo_pct"] == "0.150000"
    assert segunda.json()["fondo_garantia_pct"] == "0.050000"
    assert segunda.json()["umbral_alerta_pct"] is None
    assert segunda.json()["iva_acreditable"] is True


# --------------------------------------------------------------------------- TC-15 · CA-2


def test_hdu001_esc03_api_codigo_duplicado(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 3 · TC-15 · CA-2 — `409` `CONFLICTO` `CODIGO_OBRA_DUPLICADO` con la obra existente y `VER_OBRA`.

    Contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, el detalle con el
    id y el «código · nombre» de la existente, y la acción `VER_OBRA` con método y ruta absoluta. El mismo
    código en minúsculas y con espacios choca igual (D-1). Nada nuevo se escribe: una fila y un `CREAR`.
    """
    usuario = abrir_sesion()
    primera = _alta(cliente, usuario, _cuerpo())
    assert primera.status_code == 201, primera.text
    existente_id = primera.json()["id"]
    obras_antes = base.filas("SELECT * FROM obra ORDER BY id")

    for intento in ("AP-058-25", "  ap-058-25 "):
        respuesta = _alta(
            cliente, usuario, _cuerpo(codigo=intento, nombre="Otra obra con el mismo código")
        )

        exigir_error(
            respuesta,
            estado=409,
            esperado={
                "tipo": "CONFLICTO",
                "codigo": "CODIGO_OBRA_DUPLICADO",
                "mensaje": "Ya existe una obra con el código AP-058-25.",
                "detalle": {
                    "obra_existente_id": existente_id,
                    "obra_existente": "AP-058-25 · Union Square F2",
                },
                "acciones": [
                    {"clave": "VER_OBRA", "metodo": "GET", "ruta": f"/api/v1/obras/{existente_id}"}
                ],
            },
            esquema="ErrorConflictoEstado",
        )
        assert base.filas("SELECT * FROM obra ORDER BY id") == obras_antes, repr(intento)

    assert _cuenta(base, "SELECT count(*) FROM obra") == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 1


# --------------------------------------------------------------------------- TC-16 · CA-4


CASOS_DE_FORMA = [
    pytest.param({"codigo": AUSENTE}, "codigo", "OBLIGATORIO", id="codigo_ausente"),
    pytest.param({"codigo": ""}, "codigo", "OBLIGATORIO", id="codigo_vacio"),
    pytest.param({"codigo": "   "}, "codigo", "OBLIGATORIO", id="codigo_en_blanco"),
    pytest.param({"codigo": "A" * 41}, "codigo", "DEMASIADO_LARGO", id="codigo_de_41"),
    pytest.param({"nombre": AUSENTE}, "nombre", "OBLIGATORIO", id="nombre_ausente"),
    pytest.param({"nombre": "   "}, "nombre", "OBLIGATORIO", id="nombre_en_blanco"),
    pytest.param({"domicilio": AUSENTE}, "domicilio", "OBLIGATORIO", id="domicilio_ausente"),
    pytest.param({"domicilio": "   "}, "domicilio", "OBLIGATORIO", id="domicilio_en_blanco"),
    pytest.param({"tipo_contrato": "OTRO"}, "tipo_contrato", "VALOR_NO_PERMITIDO", id="tipo_otro"),
    pytest.param(
        {"tipo_contrato": AUSENTE}, "tipo_contrato", "OBLIGATORIO", id="tipo_contrato_ausente"
    ),
    pytest.param(
        {"retencion_destajo_pct": AUSENTE},
        "retencion_destajo_pct",
        "OBLIGATORIO",
        id="retencion_ausente",
    ),
    pytest.param(
        {"fondo_garantia_pct": AUSENTE}, "fondo_garantia_pct", "OBLIGATORIO", id="fondo_ausente"
    ),
    pytest.param({"iva_acreditable": AUSENTE}, "iva_acreditable", "OBLIGATORIO", id="iva_ausente"),
    pytest.param({"iva_acreditable": "true"}, "iva_acreditable", "FORMATO", id="iva_cadena_true"),
    pytest.param({"iva_acreditable": 1}, "iva_acreditable", "FORMATO", id="iva_entero_1"),
    pytest.param({"iva_acreditable": "yes"}, "iva_acreditable", "FORMATO", id="iva_cadena_yes"),
    pytest.param({"codigo": "AP\u0000-1"}, "codigo", "FORMATO", id="nul_en_codigo"),
    pytest.param({"nombre": "Obra\u0000"}, "nombre", "FORMATO", id="nul_en_nombre"),
    pytest.param({"domicilio": "\u0000Calle"}, "domicilio", "FORMATO", id="nul_en_domicilio"),
    pytest.param(
        {"retencion_destajo_pct": "0.1234567"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_siete_decimales",
    ),
    pytest.param(
        {"retencion_destajo_pct": "abc"}, "retencion_destajo_pct", "FORMATO", id="retencion_texto"
    ),
    pytest.param(
        {"retencion_destajo_pct": "1e-1"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_exponente",
    ),
    pytest.param(
        {"retencion_destajo_pct": "٠.١"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_digitos_arabigo_indicos",
    ),
    pytest.param(
        {"retencion_destajo_pct": "0.15\n"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_salto_de_linea_final",
    ),
    pytest.param(
        {"retencion_destajo_pct": 1}, "retencion_destajo_pct", "FORMATO", id="retencion_numero_json"
    ),
    pytest.param({"fondo_garantia_pct": "abc"}, "fondo_garantia_pct", "FORMATO", id="fondo_texto"),
    pytest.param(
        {"fondo_garantia_pct": "0.0500001"},
        "fondo_garantia_pct",
        "FORMATO",
        id="fondo_siete_decimales",
    ),
    pytest.param({"umbral_alerta_pct": "abc"}, "umbral_alerta_pct", "FORMATO", id="umbral_texto"),
    pytest.param(
        {"umbral_alerta_pct": "0.1234567"},
        "umbral_alerta_pct",
        "FORMATO",
        id="umbral_siete_decimales",
    ),
]


@pytest.mark.parametrize(("cambios", "campo", "codigo"), CASOS_DE_FORMA)
def test_hdu001_esc02_api_forma_invalida(
    cambios: dict[str, object],
    campo: str,
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 2 · TC-16 · CA-4 — un cuerpo que no cumple la forma del contrato: `422` `VALIDACION` con el campo.

    Una fila por defecto de `CA-4`, con el `campo`, el `codigo` del catálogo y el `mensaje` literal. Un `NUL`
    se rechaza aquí y no llega al motor (en TKT-017 un `NUL` dio `500`). Un solo campo inválido a la vez, así
    que `errores` trae una entrada. No se escribe ni una fila en `obra` ni un asiento `CREAR`.
    """
    usuario = abrir_sesion()

    respuesta = _alta(cliente, usuario, _cuerpo(**cambios))

    _error_de_validacion(respuesta, campo, codigo)
    _exigir_nada_creado(base)


# --------------------------------------------------------------------------- TC-17 · CA-5


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        pytest.param(
            "retencion_destajo_pct",
            "-0.010000",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="retencion_negativa",
        ),
        pytest.param(
            "retencion_destajo_pct",
            "1.000001",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="retencion_sobre_uno",
        ),
        pytest.param(
            "fondo_garantia_pct",
            "-0.010000",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="fondo_negativo",
        ),
        pytest.param(
            "fondo_garantia_pct",
            "1.000001",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="fondo_sobre_uno",
        ),
        pytest.param(
            "umbral_alerta_pct", "-0.000001", MENSAJE_UMBRAL_NEGATIVO, id="umbral_negativo"
        ),
    ],
)
def test_hdu001_esc02_api_porcentaje_fuera_de_rango(
    campo: str,
    valor: str,
    mensaje: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 2 · TC-17 · CA-5 · PA-02 · PA-18 — un porcentaje fuera de rango: `422` `FUERA_DE_RANGO` antes del motor (`M-4`).

    El `422` lo da el caso de uso: sin él, el `CHECK` de la tabla daría `23514` y un `500`. Retención y fondo
    de 0 a 1, umbral no negativo; el mensaje es el del diseño. No se escribe nada.
    """
    usuario = abrir_sesion()

    respuesta = _alta(cliente, usuario, _cuerpo(**{campo: valor}))

    _error_de_validacion(respuesta, campo, "FUERA_DE_RANGO", mensaje)
    _exigir_nada_creado(base)


# --------------------------------------------------------------------------- TC-18 · CA-5


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"retencion_destajo_pct": "0.000000"}, id="retencion_cero"),
        pytest.param({"retencion_destajo_pct": "1.000000"}, id="retencion_uno"),
        pytest.param({"fondo_garantia_pct": "0.000000"}, id="fondo_cero"),
        pytest.param({"fondo_garantia_pct": "1.000000"}, id="fondo_uno"),
        pytest.param({"umbral_alerta_pct": "0.000000"}, id="umbral_cero"),
        pytest.param({"umbral_alerta_pct": "2.500000"}, id="umbral_sin_techo"),
    ],
)
def test_hdu001_esc02_api_bordes_de_rango_se_admiten(
    cambios: dict[str, str],
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 2 · TC-18 · CA-5 — `0.000000` y `1.000000` en retención y fondo, y `0.000000` en el umbral, dan `201` (`M-1`, `M-2`).

    Los bordes que la base admite. El umbral no tiene techo (`PA-18`: no negativo), así que `2.500000` también.
    El valor guardado es el enviado.
    """
    usuario = abrir_sesion()

    respuesta = _alta(cliente, usuario, _cuerpo(**cambios))

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Obra", cuerpo)
    for campo, valor in cambios.items():
        assert cuerpo[campo] == valor
    assert _cuenta(base, "SELECT count(*) FROM obra") == 1


# --------------------------------------------------------------------------- TC-19 · CA-6


@pytest.mark.parametrize("rol", ROLES_SIN_ALTA)
def test_tkt012a_api_alta_sin_permiso(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-19 · CA-6 — `403` `PERMISO` `ROL_INSUFICIENTE` con los roles de alta, sin cifras del recurso y con su `DENEGAR` (`M-5`).

    Residente, Compras, Almacén y Administración leen obras pero no las dan de alta. El cuerpo no trae
    `detalle` ni el código de la obra que intentaron crear; el intento queda asentado como `DENEGAR` a
    nombre de quien llamó, con método, ruta y roles exigidos. No se crea ninguna obra.
    """
    usuario = abrir_sesion((rol,))

    respuesta = _alta(cliente, usuario, _cuerpo())

    cuerpo = exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_ALTA,
        },
        esquema="ErrorPermiso",
    )
    assert "detalle" not in cuerpo
    assert "AP-058-25" not in respuesta.text
    _exigir_nada_creado(base)
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ROL_INSUFICIENTE",
        ruta=RUTA,
        roles_requeridos=ROLES_ALTA,
    )


# --------------------------------------------------------------------------- TC-20 · CA-6


@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt012a_api_alta_sin_sesion_y_sin_csrf(
    cookie: str | None,
    cabecera: str | None,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-20 · CA-6 · RNF-05 — sin sesión `401` `SESION`; con sesión de Director de Proyectos y sin el doble envío, `403` `ORIGEN_NO_VERIFICADO` con su `DENEGAR`.

    Las cuatro combinaciones de `CA-9` de TKT-057 (`SIN_PAR_VALIDO`). Sin sesión responde `401` aunque el
    par sea válido, y una denegación anónima no se asienta. Con sesión y sin par, la petición no se ejecuta
    aunque quien llama pueda dar de alta. En los dos casos no se crea nada.
    """
    anonima = _alta(cliente, None, _cuerpo())
    exigir_error(
        anonima,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    _exigir_nada_creado(base)
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0

    director = abrir_sesion()
    respuesta = _alta(cliente, director, _cuerpo(), cookie_csrf=cookie, cabecera_csrf=cabecera)

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
    _exigir_nada_creado(base)
    exigir_denegacion(
        base,
        metodo="POST",
        usuario_id=director.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=RUTA,
        roles_requeridos=[],
    )


def test_tkt012a_api_alta_el_origen_se_verifica_antes_que_el_rol(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-6 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    Apoyo de TC-20 (no está en el plan): `verificar_origen` va antes que `exigir_rol`; un solo `DENEGAR` con
    motivo `ORIGEN_NO_VERIFICADO`. Con el orden invertido el motivo sería `ROL_INSUFICIENTE`.
    """
    usuario = abrir_sesion(("COMPRAS",))

    respuesta = _alta(cliente, usuario, _cuerpo(), cookie_csrf=None, cabecera_csrf=None)

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
        ruta=RUTA,
        roles_requeridos=[],
    )


# --------------------------------------------------------------------------- TC-21 · CA-4


def test_tkt012a_api_tope_de_nombre_y_domicilio(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 2 · TC-21 · CA-4 · D-5 — `nombre` de más de 200 y `domicilio` de más de 500 caracteres: `422` `DEMASIADO_LARGO`.

    Los topes mismos (200 y 500) se admiten con `201`; uno más se rechaza con el campo y el mensaje
    literal. Un tope en `ObraNueva` que el borrador no tenía (`D-5`, aprobada).
    """
    usuario = abrir_sesion()

    for campo, tope in (("nombre", 200), ("domicilio", 500)):
        rechazada = _alta(cliente, usuario, _cuerpo(**{campo: "n" * (tope + 1)}))
        _error_de_validacion(rechazada, campo, "DEMASIADO_LARGO")
    _exigir_nada_creado(base)

    admitida = _alta(cliente, usuario, _cuerpo(nombre="n" * 200, domicilio="d" * 500))
    assert admitida.status_code == 201, admitida.text
    assert admitida.json()["nombre"] == "n" * 200
    assert admitida.json()["domicilio"] == "d" * 500


# --------------------------------------------------------------------------- TC-22 · CA-7


def test_hdu001_esc02_api_lista_seis_roles_orden_determinista(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """HDU-001 esc. 2 · TC-22 · CA-7 — cada uno de los seis roles recibe `200` con `ListaObras` y el orden por código es el mismo.

    Obras sembradas desordenadas (030, 010, 040, 020) con la empresa de la migración. Cada rol ve las
    cuatro, ordenadas por `codigo`; dos llamadas seguidas dan el mismo orden; los porcentajes viajan como
    cadena con seis decimales y `linea_base_vigente_id` es `null`. La paginación trae `pagina`,
    `tamano_pagina` y `total`; `pagina=2&tamano_pagina=2` da las dos últimas. Leer no asienta `DENEGAR`.
    """
    estados = {
        "AP-030-26": "ACTIVA",
        "AP-010-26": "PLANEACION",
        "AP-040-26": "CERRADA",
        "AP-020-26": "SUSPENDIDA",
    }
    ids = _sembrar_obras(datos_presupuesto, empresa_de_la_migracion, estados)
    ordenados = ["AP-010-26", "AP-020-26", "AP-030-26", "AP-040-26"]

    for rol in SEIS_ROLES:
        lector = abrir_sesion((rol,))

        primera = _leer(cliente, lector)
        segunda = _leer(cliente, lector)

        assert primera.status_code == 200, f"{rol}: {primera.text}"
        cuerpo = primera.json()
        validar_contra("ListaObras", cuerpo)
        assert set(cuerpo) == {"elementos", "paginacion"}, rol
        assert [obra["codigo"] for obra in cuerpo["elementos"]] == ordenados, rol
        assert cuerpo["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 4}, rol
        assert [_sin_fechas(obra) for obra in cuerpo["elementos"]] == [
            _obra_sembrada(codigo, ids[codigo], estados[codigo]) for codigo in ordenados
        ], rol
        assert all("creado_en" in obra for obra in cuerpo["elementos"]), rol
        assert segunda.status_code == 200 and segunda.json() == cuerpo, rol

    segunda_pagina = _leer(
        cliente, abrir_sesion(("COMPRAS",)), consulta=[("pagina", "2"), ("tamano_pagina", "2")]
    )
    assert segunda_pagina.status_code == 200, segunda_pagina.text
    assert [obra["codigo"] for obra in segunda_pagina.json()["elementos"]] == [
        "AP-030-26",
        "AP-040-26",
    ]
    assert segunda_pagina.json()["paginacion"] == {"pagina": 2, "tamano_pagina": 2, "total": 4}
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0


# --------------------------------------------------------------------------- TC-23 · CA-7


def test_hdu001_esc02_api_lista_filtro_por_estado(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """HDU-001 esc. 2 · TC-23 · CA-7 — `estado=ACTIVA` solo trae las activas y `estado` repetido trae la unión.

    El `total` de la paginación es el del filtro, no el de la tabla.
    """
    _sembrar_obras(
        datos_presupuesto,
        empresa_de_la_migracion,
        {
            "AP-010-26": "PLANEACION",
            "AP-020-26": "ACTIVA",
            "AP-030-26": "SUSPENDIDA",
            "AP-040-26": "ACTIVA",
        },
    )
    lector = abrir_sesion(("RESIDENTE",))

    activas = _leer(cliente, lector, consulta=[("estado", "ACTIVA")])
    union = _leer(cliente, lector, consulta=[("estado", "ACTIVA"), ("estado", "PLANEACION")])

    assert activas.status_code == 200, activas.text
    validar_contra("ListaObras", activas.json())
    assert [obra["codigo"] for obra in activas.json()["elementos"]] == ["AP-020-26", "AP-040-26"]
    assert {obra["estado"] for obra in activas.json()["elementos"]} == {"ACTIVA"}
    assert activas.json()["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 2}
    assert union.status_code == 200, union.text
    validar_contra("ListaObras", union.json())
    assert [obra["codigo"] for obra in union.json()["elementos"]] == [
        "AP-010-26",
        "AP-020-26",
        "AP-040-26",
    ]
    assert union.json()["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 3}


# --------------------------------------------------------------------------- TC-24 · CA-1


def test_tkt012a_api_campos_extra_se_ignoran(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-24 · CA-1 · D-2 — `estado`, `empresa_id`, `id` y `linea_base_vigente_id` en el cuerpo se ignoran: `201` en `PLANEACION`.

    El estado inicial y la empresa nunca salen del cliente. La obra recibe un id nuevo, la empresa de la
    migración y ninguna línea base; nada de lo enviado se guarda.
    """
    usuario = abrir_sesion()
    id_enviado, empresa_enviada, linea_enviada = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    respuesta = _alta(
        cliente,
        usuario,
        {
            **_cuerpo(),
            "estado": "ACTIVA",
            "empresa_id": str(empresa_enviada),
            "id": str(id_enviado),
            "linea_base_vigente_id": str(linea_enviada),
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Obra", cuerpo)
    assert cuerpo["estado"] == "PLANEACION"
    assert cuerpo["id"] != str(id_enviado)
    assert cuerpo["linea_base_vigente_id"] is None
    assert base.filas("SELECT id, estado, empresa_id FROM obra") == [
        (uuid.UUID(cuerpo["id"]), "PLANEACION", empresa_de_la_migracion)
    ]
    assert _cuenta(base, "SELECT count(*) FROM linea_base") == 0


# --------------------------------------------------------------------------- TC-25 · CA-7


@pytest.mark.parametrize(
    ("consulta", "campo", "codigo"),
    [
        pytest.param([("estado", "OTRO")], "estado[0]", "VALOR_NO_PERMITIDO", id="estado_otro"),
        pytest.param([("pagina", "0")], "pagina", "FUERA_DE_RANGO", id="pagina_cero"),
        pytest.param([("tamano_pagina", "0")], "tamano_pagina", "FUERA_DE_RANGO", id="tamano_cero"),
        pytest.param(
            [("tamano_pagina", "201")], "tamano_pagina", "FUERA_DE_RANGO", id="tamano_sobre_200"
        ),
    ],
)
def test_tkt012a_api_lista_parametros_invalidos(
    consulta: list[tuple[str, str]],
    campo: str,
    codigo: str,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-25 · CA-7 — un `estado` fuera del enumerado, `pagina` menor que 1 o `tamano_pagina` fuera de 1 a 200: `422` con el parámetro.

    E-2: el `campo` real de un `estado` inválido en una lista de consulta es `estado[0]` y su código es
    `VALOR_NO_PERMITIDO` (comprobado con el manejador real en un experimento aparte). No responde `500`.
    """
    lector = abrir_sesion(("COMPRAS",))

    respuesta = _leer(cliente, lector, consulta=consulta)

    _error_de_validacion(respuesta, campo, codigo)


# --------------------------------------------------------------------------- TC-26 · CA-7


@pytest.mark.parametrize("pagina", [1000, 10**30])
def test_tkt012a_api_lista_pagina_inalcanzable(
    pagina: int,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
) -> None:
    """TC-26 · CA-7 · D20 — una `pagina` más allá del final, por enorme que sea, da `200`, `elementos` vacío y el `total` real.

    `10**30` desborda el `bigint` de PostgreSQL como desplazamiento: el corte en Python evita el `500`.
    La paginación devuelve la `pagina` pedida y el tamaño por omisión.
    """
    _sembrar_obras(
        datos_presupuesto,
        empresa_de_la_migracion,
        {"AP-010-26": "PLANEACION", "AP-020-26": "ACTIVA", "AP-030-26": "ACTIVA"},
    )
    lector = abrir_sesion(("ALMACEN",))

    respuesta = _leer(cliente, lector, consulta=[("pagina", str(pagina))])

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("ListaObras", respuesta.json())
    assert respuesta.json() == {
        "elementos": [],
        "paginacion": {"pagina": pagina, "tamano_pagina": 50, "total": 3},
    }


# --------------------------------------------------------------------------- TC-27 · CA-8


def test_tkt012a_api_obtener_obra(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-27 · CA-8 — `200` con la obra completa; `linea_base_vigente_id` es `null` sin congelada y es la `CONGELADA` si la hay.

    La obra se da de alta por la API. Una `BORRADOR` no es vigente. Con una `SUPERSEDIDA` (versión 1), una
    `CONGELADA` (versión 2) y una `BORRADOR` (versión 3), la vigente es la congelada. Lo lee cualquier rol.
    """
    director = abrir_sesion()
    alta = _alta(cliente, director, _cuerpo())
    assert alta.status_code == 201, alta.text
    obra_id = uuid.UUID(alta.json()["id"])
    lector = abrir_sesion(("ADMINISTRACION",))
    ruta = f"{RUTA}/{obra_id}"

    sin_linea = _leer(cliente, lector, ruta)

    assert sin_linea.status_code == 200, sin_linea.text
    validar_contra("Obra", sin_linea.json())
    assert sin_linea.json() == alta.json()
    assert sin_linea.json()["linea_base_vigente_id"] is None

    anterior = datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra_id, version=1)
    assert _leer(cliente, lector, ruta).json()["linea_base_vigente_id"] is None
    # El disparador de RN-01 solo deja avanzar BORRADOR -> CONGELADA -> SUPERSEDIDA: la versión 1 pasa por CONGELADA.
    datos_presupuesto.congelar(anterior)
    base.ejecutar("UPDATE linea_base SET estado = 'SUPERSEDIDA' WHERE id = %s", anterior)
    base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", obra_id)
    congelada = datos_presupuesto.linea_base(estado="CONGELADA", obra_id=obra_id, version=2)
    datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra_id, version=3)

    con_linea = _leer(cliente, lector, ruta)

    assert con_linea.status_code == 200, con_linea.text
    validar_contra("Obra", con_linea.json())
    assert _sin_fechas(con_linea.json()) == {
        **_sin_fechas(alta.json()),
        "estado": "ACTIVA",
        "linea_base_vigente_id": str(congelada),
    }


# --------------------------------------------------------------------------- TC-28 · CA-8


def test_tkt012a_api_obtener_obra_inexistente_y_mal_formada(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-28 · CA-8 — una obra que no existe es `404` `NO_ENCONTRADO` con `recurso` `obra`; `/obras/abc` es `422` en `obra_id`.

    El `recurso` es `obra` y no la ruta, que es lo que responde un enrutador sin ella.
    """
    lector = abrir_sesion(("RESIDENTE",))

    inexistente = _leer(cliente, lector, f"{RUTA}/{uuid.uuid4()}")
    mal_formada = _leer(cliente, lector, f"{RUTA}/abc")

    exigir_error(
        inexistente,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": MENSAJE_OBRA_NO_EXISTE, "recurso": "obra"},
        esquema="ErrorNoEncontrado",
    )
    _error_de_validacion(mal_formada, "obra_id", "FORMATO")


# --------------------------------------------------------------------------- TC-29 · CA-7, CA-8


def test_tkt012a_api_lecturas_sin_sesion(
    base: Base,
    cliente: TestClient,
) -> None:
    """TC-29 · CA-7 · CA-8 — la lista y la consulta sin sesión responden `401` `SESION`, sin asiento `DENEGAR`."""
    for ruta in (RUTA, f"{RUTA}/{uuid.uuid4()}"):
        respuesta = _leer(cliente, None, ruta)

        exigir_error(
            respuesta,
            estado=401,
            esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
            esquema="ErrorSesion",
        )
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- TC-30 · CA-1, CA-7, CA-8


COMPONENTES_DE_OBRA = ("ObraNueva", "Obra", "ListaObras", "EstadoObra")


def test_tkt012a_api_forma_publicada_igual_al_borrador(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-30 · CA-1 · CA-7 · CA-8 — `ObraNueva`, `Obra`, `ListaObras` y `EstadoObra` publicados coinciden con el borrador.

    Propiedades, `required`, tipos, `format`, `enum` y nulabilidad con los `$ref` resueltos; los parámetros
    de `listar_obras` iguales a los del borrador; el `operationId` de las tres rutas, el `201` de la alta y
    `sesion` y `csrf` en su seguridad. E-3: `tipo_contrato` debe publicar `enum`, no `const`. Los topes de
    `D-5` (200 y 500) y el de 40 del código salen publicados; el patrón de los porcentajes es el del borrador.
    """
    contrato = contrato_publicado(monkeypatch)
    esquemas = contrato["components"]["schemas"]
    faltan = [nombre for nombre in COMPONENTES_DE_OBRA if nombre not in esquemas]
    assert faltan == [], f"El contrato publicado no trae los componentes {faltan}"

    for nombre in COMPONENTES_DE_OBRA:
        del_borrador, _ = forma_de_componente(borrador(), nombre)
        publicada, _ = forma_de_componente(contrato, nombre)
        assert diferencias_de_forma(del_borrador, publicada) == [], nombre

    assert parametros_de(contrato, "/api/v1/obras", "get") == parametros_de(
        borrador(), "/obras", "get"
    )
    assert contrato["paths"][RUTA]["post"]["operationId"] == "crear_obra"
    assert "201" in contrato["paths"][RUTA]["post"]["responses"]
    assert contrato["paths"][RUTA]["get"]["operationId"] == "listar_obras"
    assert contrato["paths"][f"{RUTA}/{{obra_id}}"]["get"]["operationId"] == "obtener_obra"
    exigidos = {
        nombre
        for requisito in contrato["paths"][RUTA]["post"].get("security", [])
        for nombre in requisito
    }
    assert {"sesion", "csrf"} <= exigidos

    propiedades = esquemas["ObraNueva"]["properties"]
    assert propiedades["codigo"]["maxLength"] == 40
    assert propiedades["nombre"]["maxLength"] == 200
    assert propiedades["domicilio"]["maxLength"] == 500
    patron_del_borrador = borrador()["components"]["schemas"]["Porcentaje"]["pattern"]
    for campo in ("retencion_destajo_pct", "fondo_garantia_pct"):
        assert resolver(contrato, propiedades[campo])["pattern"] == patron_del_borrador, campo


# --------------------------------------------------------------------------- las rutas de obra, en el recorrido


def test_tkt012a_api_las_rutas_de_obra_son_def_con_sesion_y_origen_primero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-6 · regla 11 · RNF-05 — las tres rutas existen una sola vez, son `def`, exigen sesión, y la que muta verifica el origen antes que el rol.

    Apoyo de TC-19 y TC-20 (no está en el plan): los recorridos de `test_tkt006_enrutador.py` y
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

    alta = la_ruta("POST", RUTA)
    lista = la_ruta("GET", RUTA)
    una = la_ruta("GET", f"{RUTA}/{{obra_id}}")
    for ruta in (alta, lista, una):
        assert inspect.isfunction(ruta.endpoint)
        assert not inspect.iscoroutinefunction(ruta.endpoint)
        assert sesion_vigente in list(llamadas(ruta.dependant))

    declaradas = [sub.call for sub in alta.dependant.dependencies]
    assert verificar_origen in declaradas, "La alta debe declarar verificar_origen"
    roles = [
        posicion
        for posicion, llamada in enumerate(declaradas)
        if getattr(llamada, "__name__", "") == "comprobar_rol"
    ]
    assert len(roles) == 1, "La alta debe declarar exactamente un exigir_rol"
    assert declaradas.index(verificar_origen) < roles[0]


# --------------------------------------------------------------------------- TC-31 · CA-R1


def test_hdu001_esc14_obra_creada_por_api_se_congela_y_pasa_a_activa(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    contexto: Contexto,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """HDU-001 esc. 14 · TC-31 · CA-R1 · PA-T17.8 — una obra dada de alta por `POST` se congela y pasa a `ACTIVA`.

    Regresión de invariante: con la tabla `obra` mapeada completa, el congelado de TKT-017 sigue activando
    la obra y `GET /obras/{id}` devuelve la línea base congelada como vigente. No usa el fixture `entorno`
    (crearía otra empresa activa antes del alta y el alta respondería `500`, A9): da el alta con el código
    `AP-012-26` y construye `Entorno` después, que a su vez crea la obra `AP-058-25`. Misma preparación que
    `test_tkt017_congelado.py::test_hdu001_esc14_congelar_pasa_la_obra_a_activa`, con el `obra_id` de la API.
    """
    director = abrir_sesion()
    alta = _alta(cliente, director, _cuerpo(codigo="AP-012-26", nombre="Obra por la API"))
    assert alta.status_code == 201, alta.text
    obra_id = uuid.UUID(alta.json()["id"])
    ruta = f"{RUTA}/{obra_id}"
    antes = _leer(cliente, director, ruta)
    assert antes.status_code == 200, antes.text
    assert antes.json()["estado"] == "PLANEACION"
    assert antes.json()["linea_base_vigente_id"] is None

    entorno = Entorno(datos_presupuesto, base)
    entorno.registrar_mano_obra()
    entorno.importacion_id = entorno.importar(
        preparacion=preparacion_dos_niveles(), obra_id=obra_id
    )
    linea_base = entorno.confirmar(contexto)
    congelar(contexto(), linea_base.linea_base_id, usuario_id=entorno.usuario_id)

    despues = _leer(cliente, director, ruta)

    assert despues.status_code == 200, despues.text
    validar_contra("Obra", despues.json())
    assert despues.json()["estado"] == "ACTIVA"
    assert despues.json()["linea_base_vigente_id"] == str(linea_base.linea_base_id)
    assert base.filas("SELECT estado FROM obra WHERE id = %s", obra_id) == [("ACTIVA",)]
