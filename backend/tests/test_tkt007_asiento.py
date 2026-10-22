"""Asiento y DENEGAR (TKT-007, fila 4): TC-33 a TC-40, con Docker.

`asentar` y `asentar_denegacion` escriben en la `Session` que les pasan, dentro de la transacción
de quien llama, y nunca confirman (regla 8 de CLAUDE.md, RN-04). La `Session` es la de
`sesion_bd`, con el rol de aplicación; cada comprobación sobre lo que quedó en la base usa una
conexión **nueva** (`lector`), nunca la misma que escribió. Un rechazo de forma se comprueba
completo: la excepción `ValidacionRechazada`, la lista exacta de errores, el cuerpo válido contra
`ErrorValidacion` del borrador y el oyente de sentencias vacío (no se tocó la base). Un rechazo
del motor se comprueba por `sqlstate` y por `diag.constraint_name`.

Los símbolos de producción de la fila (`asentar`, `asentar_denegacion`, desde
`cimenta.auditoria.interfaz`) se importan **dentro** de cada caso: así cada uno falla por sí solo
con el `ImportError` del símbolo pedido y la recolección no se cae. Los mensajes del dominio se
piden por nombre al módulo que ya existe (fila 3); el de la zona horaria, que vive en
`aplicacion/asentar.py`, se escribe literal: es el oráculo del texto del diseño.

TC-35 en su parte de AST y TC-41 a TC-45 viven en `test_tkt007_fronteras.py`, que no pide Docker.
"""

import functools
import importlib
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from jsonschema import Draft202012Validator
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contrato_error import ValidacionRechazada

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]

RAIZ = Path(__file__).resolve().parents[2]
CID = "c3d4e5f6-a7b8-4901-8cde-f01234567890"
T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
MENSAJE_SIN_ZONA = "El momento lleva zona horaria."
RESTRICCION_DEL_ACTOR = "fk_bitacora_usuario_id"
VIOLACION_DE_CLAVE_FORANEA = "23503"

COLUMNAS = (
    "id, accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, datos_antes, "
    "datos_despues, motivo, regla_negocio, obra_id, datos_antes IS NULL"
)
NOMBRES = (
    "id",
    "accion",
    "entidad_tipo",
    "entidad_id",
    "usuario_id",
    "ocurrido_en",
    "datos_antes",
    "datos_despues",
    "motivo",
    "regla_negocio",
    "obra_id",
    "datos_antes_es_nulo",
)


# --------------------------------------------------------------------------- ayudas


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    """Valida un cuerpo contra un esquema de `components.schemas` del borrador (ayuda de TKT-005)."""
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def mensaje(nombre: str) -> str:
    """El texto de un `MENSAJE_*` del dominio; el de la zona horaria es el literal del diseño."""
    if nombre == "MENSAJE_SIN_ZONA":
        return MENSAJE_SIN_ZONA
    dominio = importlib.import_module("cimenta.auditoria.dominio.asiento")
    return str(getattr(dominio, nombre))


def sembrar_usuario(conexion: Conexion, correo: str) -> uuid.UUID:
    """Un usuario confirmado por el rol de aplicación, para que `bitacora.usuario_id` apunte a alguien."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, "Ana Pérez", correo, "hash-de-prueba"),
    )
    return identificador


def sembrar_sesion(conexion: Conexion, usuario_id: uuid.UUID) -> uuid.UUID:
    """Una fila de `sesion` viva, confirmada: la credencial que `DENEGAR` jamás debe usar como entidad."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO sesion (id, usuario_id, expira_en) VALUES (%s, %s, %s)",
        (identificador, usuario_id, datetime(2026, 10, 21, 17, 0, tzinfo=UTC)),
    )
    return identificador


def contar_asientos(conexion: Conexion) -> int:
    fila = conexion.execute("SELECT count(*) FROM bitacora").fetchone()
    assert fila is not None
    return int(fila[0])


def contar_usuarios_con_correo(conexion: Conexion, correo: str) -> int:
    fila = conexion.execute("SELECT count(*) FROM usuario WHERE email = %s", (correo,)).fetchone()
    assert fila is not None
    return int(fila[0])


def fila_de_bitacora(conexion: Conexion, asiento_id: uuid.UUID) -> dict[str, Any]:
    """El asiento con ese `id`, por nombre de columna; falla con nombre si no existe."""
    fila = conexion.execute(
        f"SELECT {COLUMNAS} FROM bitacora WHERE id = %s",  # noqa: S608
        (asiento_id,),
    ).fetchone()
    assert fila is not None, f"No hay ningún asiento con id {asiento_id} en bitacora."
    return dict(zip(NOMBRES, fila, strict=True))


def afirmar_validacion_rechazada(
    rechazo: pytest.ExceptionInfo[ValidacionRechazada], esperados: list[dict[str, str]]
) -> None:
    """Contrato de error completo: lista exacta de errores, `tipo` y cuerpo válido contra el borrador."""
    errores = [e.como_dict() for e in rechazo.value.errores]
    assert errores == esperados
    cuerpo = rechazo.value.cuerpo(frozenset(), CID)
    assert cuerpo["tipo"] == "VALIDACION"
    assert cuerpo["errores"] == esperados
    validar_contra("ErrorValidacion", cuerpo)


def afirmar_clave_foranea_del_actor(rechazo: pytest.ExceptionInfo[IntegrityError]) -> None:
    """El motor rechazó el asiento sin actor real: `ForeignKeyViolation` de `fk_bitacora_usuario_id`."""
    origen = rechazo.value.orig
    assert isinstance(origen, psycopg.errors.ForeignKeyViolation)
    assert origen.sqlstate == VIOLACION_DE_CLAVE_FORANEA
    assert origen.diag.constraint_name == RESTRICCION_DEL_ACTOR


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def ana(conectar: Conectar, base_de_prueba: str) -> uuid.UUID:
    """Un usuario real, confirmado antes de que la prueba abra su `Session`."""
    return sembrar_usuario(conectar("aplicacion", base_de_prueba), "ana@cimenta.test")


@pytest.fixture
def lector(conectar: Conectar, base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


@pytest.fixture
def sentencias(motor_aplicacion: Engine) -> Iterator[list[str]]:
    """Oyente `before_cursor_execute`: anota cada sentencia que el motor envía a la base."""
    anotadas: list[str] = []

    def anotar(
        conexion: object,
        cursor: object,
        sentencia: str,
        parametros: object,
        contexto: object,
        many: bool,
    ) -> None:
        anotadas.append(sentencia)

    event.listen(motor_aplicacion, "before_cursor_execute", anotar)
    try:
        yield anotadas
    finally:
        event.remove(motor_aplicacion, "before_cursor_execute", anotar)


# --------------------------------------------------------------------------- TC-33 a TC-37


def test_tkt007_ca02_cambio_y_asiento_se_confirman_juntos(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-33 · CA-2 esc. 1 · RN-04 — el cambio y su asiento salen en la misma confirmación."""
    from cimenta.auditoria.interfaz import asentar

    beto = uuid.uuid4()
    sesion_bd.execute(
        text(
            "INSERT INTO usuario (id, nombre, email, password_hash) "
            "VALUES (:id, 'Beto Ruiz', 'beto@cimenta.test', 'hash-de-prueba')"
        ),
        {"id": beto},
    )
    asiento_id = asentar(
        sesion_bd,
        accion="CREAR",
        entidad_tipo="usuario",
        entidad_id=beto,
        usuario_id=ana,
        ocurrido_en=T0,
        motivo="Alta de prueba",
        datos_despues={"email": "beto@cimenta.test"},
    )
    sesion_bd.commit()

    verificador = lector()
    assert isinstance(asiento_id, uuid.UUID)
    assert contar_usuarios_con_correo(verificador, "beto@cimenta.test") == 1
    assert contar_asientos(verificador) == 1
    assert fila_de_bitacora(verificador, asiento_id) == {
        "id": asiento_id,
        "accion": "CREAR",
        "entidad_tipo": "usuario",
        "entidad_id": beto,
        "usuario_id": ana,
        "ocurrido_en": T0,
        "datos_antes": None,
        "datos_despues": {"email": "beto@cimenta.test"},
        "motivo": "Alta de prueba",
        "regla_negocio": None,
        "obra_id": None,
        "datos_antes_es_nulo": True,
    }


def test_tkt007_ca02_asiento_fallido_deshace_el_cambio(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-34 · CA-2 esc. 2 · RN-04 — si el asiento falla, el cambio no sobrevive a la transacción."""
    from cimenta.auditoria.interfaz import asentar

    beto = uuid.uuid4()
    sesion_bd.execute(
        text(
            "INSERT INTO usuario (id, nombre, email, password_hash) "
            "VALUES (:id, 'Beto Ruiz', 'beto@cimenta.test', 'hash-de-prueba')"
        ),
        {"id": beto},
    )

    with pytest.raises(IntegrityError) as rechazo:
        asentar(
            sesion_bd,
            accion="CREAR",
            entidad_tipo="usuario",
            entidad_id=beto,
            usuario_id=uuid.uuid4(),
            ocurrido_en=T0,
            motivo="Alta de prueba",
        )
    sesion_bd.rollback()

    afirmar_clave_foranea_del_actor(rechazo)
    verificador = lector()
    assert contar_usuarios_con_correo(verificador, "beto@cimenta.test") == 0
    assert contar_asientos(verificador) == 0


def test_tkt007_ca02_el_servicio_no_confirma(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-35 · CA-2 esc. 3 · regla 8 — asentar escribe en la transacción de quien llama y no confirma."""
    from cimenta.auditoria.interfaz import asentar

    asentar(
        sesion_bd,
        accion="CREAR",
        entidad_tipo="usuario",
        entidad_id=uuid.uuid4(),
        usuario_id=ana,
        ocurrido_en=T0,
        motivo="Alta de prueba",
    )

    dentro_de_la_transaccion = sesion_bd.execute(text("SELECT count(*) FROM bitacora")).scalar_one()
    sin_confirmar = contar_asientos(lector())
    sesion_bd.rollback()
    tras_deshacer = contar_asientos(lector())

    # El asiento sí estaba escrito en la transacción de quien llama: sin esto, 0 y 0 no probarían nada.
    assert dentro_de_la_transaccion == 1
    assert sin_confirmar == 0
    assert tras_deshacer == 0


def test_tkt007_ca05_asiento_con_regla_y_obra(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-36 · CA-5 esc. 1 · RN-04 — la regla y la obra quedan en el asiento y el importe viaja como cadena."""
    from cimenta.auditoria.interfaz import asentar

    obra = uuid.uuid4()
    requisicion = uuid.uuid4()
    asiento_id = asentar(
        sesion_bd,
        accion="AUTORIZAR",
        entidad_tipo="requisicion",
        entidad_id=requisicion,
        usuario_id=ana,
        ocurrido_en=T0,
        motivo="Excede el presupuesto de la partida",
        regla_negocio="RN-03",
        obra_id=obra,
        datos_antes={"disponible": "9000.0000"},
        datos_despues={"excedente": "3000.0000"},
    )
    sesion_bd.commit()

    verificador = lector()
    fila = fila_de_bitacora(verificador, asiento_id)
    tipo_del_importe = verificador.execute(
        "SELECT jsonb_typeof(datos_despues -> 'excedente'), datos_despues ->> 'excedente', "
        "datos_antes ->> 'disponible' FROM bitacora WHERE id = %s",
        (asiento_id,),
    ).fetchone()
    assert fila["accion"] == "AUTORIZAR"
    assert fila["regla_negocio"] == "RN-03"
    assert fila["obra_id"] == obra
    assert fila["entidad_id"] == requisicion
    assert fila["motivo"] == "Excede el presupuesto de la partida"
    assert tipo_del_importe == ("string", "3000.0000", "9000.0000")


FORMAS_RECHAZADAS = [
    pytest.param(
        {"regla_negocio": "rn-03"},
        [("regla_negocio", "FORMATO", "MENSAJE_REGLA")],
        id="regla-en-minusculas",
    ),
    pytest.param(
        {"datos_despues": {"importe": 12.5}},
        [("datos_despues.importe", "FORMATO", "MENSAJE_VALOR_NO_JSON")],
        id="importe-float",
    ),
    pytest.param(
        {"datos_antes": {"importe": Decimal("12.50")}},
        [("datos_antes.importe", "FORMATO", "MENSAJE_VALOR_NO_JSON")],
        id="importe-decimal",
    ),
    pytest.param(
        {"accion": "BORRAR"},
        [("accion", "VALOR_NO_PERMITIDO", "MENSAJE_ACCION")],
        id="verbo-inexistente",
    ),
    pytest.param(
        {"ocurrido_en": datetime(2026, 10, 21, 9, 0)},  # noqa: DTZ001 - el caso es la ausencia de zona
        [("ocurrido_en", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="momento-sin-zona",
    ),
    pytest.param(
        {"ocurrido_en": None},
        [("ocurrido_en", "OBLIGATORIO", "MENSAJE_OBLIGATORIO")],
        id="momento-nulo",
    ),
    pytest.param(
        {"regla_negocio": "RN-3", "ocurrido_en": datetime(2026, 10, 21, 9, 0)},  # noqa: DTZ001
        [
            ("regla_negocio", "FORMATO", "MENSAJE_REGLA"),
            ("ocurrido_en", "FORMATO", "MENSAJE_SIN_ZONA"),
        ],
        id="forma-y-momento-juntos-en-orden",
    ),
    # TC-59 · F001 (ciclo 1): un U+0000 lo rechaza el dominio como FORMATO antes de la primera
    # sentencia; si pasara, psycopg lanzaría DataError desde el motor.
    pytest.param(
        {"motivo": "Excede\x00 el presupuesto"},
        [("motivo", "FORMATO", "MENSAJE_NUL")],
        id="nul-en-motivo",
    ),
    pytest.param(
        {"entidad_tipo": "requisicion\x00"},
        [("entidad_tipo", "FORMATO", "MENSAJE_NUL")],
        id="nul-en-entidad-tipo",
    ),
    pytest.param(
        {"datos_despues": {"renglones": [{"nota": "x\x00y"}]}},
        [("datos_despues.renglones[0].nota", "FORMATO", "MENSAJE_NUL")],
        id="nul-en-cadena-de-datos",
    ),
    pytest.param(
        {"datos_antes": {"a\x00b": "x"}},
        [("datos_antes", "FORMATO", "MENSAJE_NUL")],
        id="nul-en-clave-de-datos",
    ),
]


@pytest.mark.parametrize(("cambios", "esperados"), FORMAS_RECHAZADAS)
def test_tkt007_ca05_rechazos_de_forma_antes_de_escribir(
    sesion_bd: Session,
    ana: uuid.UUID,
    lector: Callable[[], Conexion],
    sentencias: list[str],
    cambios: dict[str, object],
    esperados: list[tuple[str, str, str]],
) -> None:
    """TC-37 · CA-5 esc. 2, 3 y 4 · RN-04 — un asiento mal formado lanza VALIDACION sin tocar la base."""
    from cimenta.auditoria.interfaz import asentar

    argumentos: dict[str, Any] = {
        "accion": "AUTORIZAR",
        "entidad_tipo": "requisicion",
        "entidad_id": uuid.uuid4(),
        "usuario_id": ana,
        "ocurrido_en": T0,
        "regla_negocio": "RN-03",
        **cambios,
    }

    with pytest.raises(ValidacionRechazada) as rechazo:
        asentar(sesion_bd, **argumentos)

    afirmar_validacion_rechazada(
        rechazo,
        [
            {"campo": campo, "codigo": codigo, "mensaje": mensaje(nombre)}
            for campo, codigo, nombre in esperados
        ],
    )
    assert sentencias == []
    assert contar_asientos(lector()) == 0


# --------------------------------------------------------------------------- TC-38 a TC-40


def test_tkt007_ca04_denegar_atribuido_al_usuario(
    sesion_bd: Session,
    ana: uuid.UUID,
    conectar: Conectar,
    base_de_prueba: str,
    lector: Callable[[], Conexion],
) -> None:
    """TC-38 · CA-4 esc. 1 y 3 · RN-04 — DENEGAR se atribuye a quien se le denegó, no a su sesión."""
    from cimenta.auditoria.interfaz import asentar_denegacion

    sesion_de_ana = sembrar_sesion(conectar("aplicacion", base_de_prueba), ana)
    datos = {
        "metodo": "GET",
        "ruta": "/api/v1/prueba/direccion",
        "roles_requeridos": ["DIRECCION_GENERAL"],
    }

    asiento_id = asentar_denegacion(
        sesion_bd, usuario_id=ana, ocurrido_en=T0, motivo="ROL_INSUFICIENTE", datos=datos
    )
    sesion_bd.commit()

    fila = fila_de_bitacora(lector(), asiento_id)
    assert fila["accion"] == "DENEGAR"
    assert fila["entidad_tipo"] == "usuario"
    assert fila["entidad_id"] == ana
    assert fila["usuario_id"] == ana
    assert fila["motivo"] == "ROL_INSUFICIENTE"
    assert fila["ocurrido_en"] == T0
    assert fila["regla_negocio"] is None
    assert fila["obra_id"] is None
    # NULL de SQL, no el JSON null: `JSONB` de SQLAlchemy guarda None como 'null' si no se le dice.
    assert fila["datos_antes_es_nulo"] is True
    assert fila["datos_despues"] == datos
    # La sesión web es la credencial de la cookie: no es la entidad del asiento (invariante 21).
    assert fila["entidad_id"] != sesion_de_ana


def test_tkt007_ca04_denegar_no_confirma(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-39 · CA-4 esc. 1 · regla 8 — asentar_denegacion no confirma: la transacción es de quien llama."""
    from cimenta.auditoria.interfaz import asentar_denegacion

    asentar_denegacion(
        sesion_bd,
        usuario_id=ana,
        ocurrido_en=T0,
        motivo="ROL_INSUFICIENTE",
        datos={"metodo": "GET", "ruta": "/api/v1/prueba/direccion"},
    )

    dentro_de_la_transaccion = sesion_bd.execute(text("SELECT count(*) FROM bitacora")).scalar_one()
    sesion_bd.rollback()

    # Escrito en la transacción de quien llama; al deshacerla, desaparece: nadie confirmó por él.
    assert dentro_de_la_transaccion == 1
    assert contar_asientos(lector()) == 0


def test_tkt007_ca04_nunca_anonimo(
    sesion_bd: Session,
    lector: Callable[[], Conexion],
    sentencias: list[str],
) -> None:
    """TC-40 · CA-4 esc. 2 · RN-04 — un DENEGAR sin usuario no se escribe: el actor es obligatorio."""
    from cimenta.auditoria.interfaz import asentar_denegacion

    with pytest.raises(ValidacionRechazada) as rechazo:
        asentar_denegacion(
            sesion_bd,
            usuario_id=None,  # type: ignore[arg-type]
            ocurrido_en=T0,
            motivo="SIN_SESION",
            datos={"metodo": "GET", "ruta": "/api/v1/prueba/direccion"},
        )

    afirmar_validacion_rechazada(
        rechazo,
        [
            {
                "campo": "entidad_id",
                "codigo": "OBLIGATORIO",
                "mensaje": mensaje("MENSAJE_OBLIGATORIO"),
            },
            {
                "campo": "usuario_id",
                "codigo": "OBLIGATORIO",
                "mensaje": mensaje("MENSAJE_OBLIGATORIO"),
            },
        ],
    )
    assert sentencias == []
    assert contar_asientos(lector()) == 0


def test_tkt007_ca04_nunca_anonimo_usuario_inexistente(
    sesion_bd: Session, lector: Callable[[], Conexion]
) -> None:
    """TC-40 · CA-4 esc. 2 · RN-04 — un DENEGAR de un usuario que no existe lo rechaza el motor, al instante."""
    from cimenta.auditoria.interfaz import asentar_denegacion

    with pytest.raises(IntegrityError) as rechazo:
        asentar_denegacion(
            sesion_bd,
            usuario_id=uuid.uuid4(),
            ocurrido_en=T0,
            motivo="ROL_INSUFICIENTE",
            datos={"metodo": "GET", "ruta": "/api/v1/prueba/direccion"},
        )
    sesion_bd.rollback()

    # La excepción salió en la llamada y no al confirmar: `insertar_asiento` ejecuta la sentencia ya.
    afirmar_clave_foranea_del_actor(rechazo)
    assert contar_asientos(lector()) == 0
