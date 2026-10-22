"""Consulta de la bitácora (TKT-007, fila 8): TC-49 a TC-57, con Docker salvo TC-55 y TC-57.

`consultar_bitacora` lee de `bitacora` con el rol de aplicación, dentro de la transacción de quien
llama, y devuelve una `PaginaBitacora`: el más reciente primero, con desempate por `id`, `desde`
inclusivo y `hasta` exclusivo (borrador, `consultar_bitacora`; `PA-T7`). Los asientos de cada caso se
siembran con `asentar` en la `Session` de `sesion_bd` y se confirman; lo que la consulta devuelve se
compara con los identificadores que devolvió `asentar`, nunca con una copia de lo que debería haber.
Un rechazo de forma se comprueba completo: la excepción `ValidacionRechazada`, la lista exacta de
errores, el cuerpo válido contra `ErrorValidacion` del borrador y el oyente de sentencias vacío (no
se tocó la base).

Los símbolos de producción de la fila (`consultar_bitacora`, `AsientoLeido`, `PaginaBitacora`, desde
`cimenta.auditoria.interfaz`) se importan **dentro** de cada caso: así cada uno falla por sí solo con
el `ImportError` del símbolo pedido y la recolección no se cae. Los mensajes del dominio se piden por
nombre a los módulos que ya existen (filas 3 y 7); el de la zona horaria, que vive en
`aplicacion/asentar.py`, se escribe literal: es el oráculo del texto del diseño.

TC-55 y TC-57 no piden Docker. TC-56 comprueba con `EXPLAIN` que los dos índices de la fila 1 sirven
a la consulta; su complemento comprueba lo mismo sobre la sentencia que `consultar_bitacora` emite
de verdad.
"""

import functools
import importlib
import io
import json
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.routing import BaseRoute

from contrato_error import ValidacionRechazada

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]

RAIZ = Path(__file__).resolve().parents[2]
CID = "c3d4e5f6-a7b8-4901-8cde-f01234567890"
T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
HORA = timedelta(hours=1)
MENSAJE_SIN_ZONA = "El momento lleva zona horaria."
INDICE_DE_OBRA = "ix_bitacora_obra_id_ocurrido_en"
INDICE_DE_REGLA = "ix_bitacora_regla_negocio"
TOTAL_DE_MUCHOS = 5000
ASIENTOS_POR_SELECTIVIDAD = 20


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
    for modulo in ("consulta", "asiento"):
        dominio = importlib.import_module(f"cimenta.auditoria.dominio.{modulo}")
        if hasattr(dominio, nombre):
            return str(getattr(dominio, nombre))
    raise AssertionError(f"Ningún módulo del dominio de auditoría define {nombre}.")


def sembrar_usuario(conexion: Conexion, correo: str, nombre: str) -> uuid.UUID:
    """Un usuario confirmado por el rol de aplicación, para que `bitacora.usuario_id` apunte a alguien."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO usuario (id, nombre, email, password_hash) VALUES (%s, %s, %s, %s)",
        (identificador, nombre, correo, "hash-de-prueba"),
    )
    return identificador


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


def rutas_de(rutas: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Las `APIRoute` de la aplicación, también las de un `APIRouter` incluido (ayuda de TKT-005).

    Desde FastAPI 0.159 `include_router` deja una ruta perezosa con el enrutador original en
    `original_router`: sin bajar por ella, una ruta de un enrutador incluido pasaría inadvertida.
    """
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from rutas_de(original.routes)
        elif isinstance(ruta, APIRoute):
            yield ruta


def indices_del_plan(plan: object) -> set[str]:
    """Todos los `Index Name` que aparecen en un plan de `EXPLAIN (FORMAT JSON)`, a cualquier profundidad."""
    encontrados: set[str] = set()
    if isinstance(plan, dict):
        for clave, valor in plan.items():
            if clave == "Index Name" and isinstance(valor, str):
                encontrados.add(valor)
            else:
                encontrados |= indices_del_plan(valor)
    elif isinstance(plan, list):
        for elemento in plan:
            encontrados |= indices_del_plan(elemento)
    return encontrados


def plan_de(
    conexion: Conexion, sentencia: str, parametros: Mapping[str, Any] | None = None
) -> object:
    """`EXPLAIN (FORMAT JSON)` con enlace de parámetros del lado del cliente, que es lo que EXPLAIN admite."""
    cursor = psycopg.ClientCursor(conexion)
    cursor.execute(f"EXPLAIN (FORMAT JSON) {sentencia}", parametros)
    fila = cursor.fetchone()
    assert fila is not None
    return fila[0]


@dataclass(frozen=True)
class Semilla:
    """Un asiento por sembrar: lo que cambia entre un caso y otro; el resto lleva valores neutros."""

    ocurrido_en: datetime
    usuario_id: uuid.UUID
    accion: str = "CREAR"
    entidad_tipo: str = "requisicion"
    entidad_id: uuid.UUID | None = None
    regla_negocio: str | None = None
    obra_id: uuid.UUID | None = None
    motivo: str | None = None
    datos_antes: dict[str, object] | None = None
    datos_despues: dict[str, object] | None = None


Sembrar = Callable[[Sequence[Semilla]], list[uuid.UUID]]


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def ana(conectar: Conectar, base_de_prueba: str) -> uuid.UUID:
    """Un usuario real, confirmado antes de que la prueba abra su `Session`."""
    return sembrar_usuario(conectar("aplicacion", base_de_prueba), "ana@cimenta.test", "Ana Pérez")


@pytest.fixture
def beto(conectar: Conectar, base_de_prueba: str) -> uuid.UUID:
    """Un segundo usuario real, para los filtros por `usuario_id`."""
    return sembrar_usuario(conectar("aplicacion", base_de_prueba), "beto@cimenta.test", "Beto Ruiz")


@pytest.fixture
def sembrar_asientos(sesion_bd: Session) -> Sembrar:
    """Escribe cada `Semilla` con `asentar` en `sesion_bd`, confirma y devuelve los `id`, en el mismo orden."""

    def _sembrar(semillas: Sequence[Semilla]) -> list[uuid.UUID]:
        from cimenta.auditoria.interfaz import asentar

        identificadores = [
            asentar(
                sesion_bd,
                accion=semilla.accion,
                entidad_tipo=semilla.entidad_tipo,
                entidad_id=semilla.entidad_id or uuid.uuid4(),
                usuario_id=semilla.usuario_id,
                ocurrido_en=semilla.ocurrido_en,
                motivo=semilla.motivo,
                regla_negocio=semilla.regla_negocio,
                obra_id=semilla.obra_id,
                datos_antes=semilla.datos_antes,
                datos_despues=semilla.datos_despues,
            )
            for semilla in semillas
        ]
        sesion_bd.commit()
        return identificadores

    return _sembrar


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


@pytest.fixture
def emitidas(motor_aplicacion: Engine) -> Iterator[list[tuple[str, Mapping[str, Any]]]]:
    """Como `sentencias`, pero con los parámetros de cada una: sirve para repetir la sentencia en un `EXPLAIN`."""
    anotadas: list[tuple[str, Mapping[str, Any]]] = []

    def anotar(
        conexion: object,
        cursor: object,
        sentencia: str,
        parametros: Mapping[str, Any],
        contexto: object,
        many: bool,
    ) -> None:
        anotadas.append((sentencia, parametros))

    event.listen(motor_aplicacion, "before_cursor_execute", anotar)
    try:
        yield anotadas
    finally:
        event.remove(motor_aplicacion, "before_cursor_execute", anotar)


@dataclass(frozen=True)
class MuchosAsientos:
    """La base sembrada para el `EXPLAIN`: dos obras y el único instante de inicio."""

    obra_con_pocos: uuid.UUID
    obra_con_casi_todos: uuid.UUID
    inicio: datetime


@pytest.fixture
def muchos_asientos(conectar: Conectar, base_de_prueba: str, ana: uuid.UUID) -> MuchosAsientos:
    """5,000 asientos por el rol de aplicación, selectivos, con estadísticas puestas por el propietario.

    Los 20 primeros son de la obra pequeña y sin regla; los 20 siguientes llevan `RN-03` y son de la
    otra obra; el resto es de la otra obra y sin regla. Un índice solo se prefiere a recorrer la tabla
    si el filtro deja pocas filas, y con 20 de 5,000 las deja.
    """
    obra_con_pocos = uuid.uuid4()
    obra_con_casi_todos = uuid.uuid4()
    aplicacion = conectar("aplicacion", base_de_prueba)
    aplicacion.execute(
        "INSERT INTO bitacora (id, entidad_tipo, entidad_id, accion, usuario_id, ocurrido_en, "
        "regla_negocio, obra_id) "
        "SELECT gen_random_uuid(), 'requisicion', gen_random_uuid(), 'CREAR', %(ana)s, "
        "%(inicio)s::timestamptz + make_interval(secs => g), "
        "CASE WHEN g BETWEEN 21 AND 40 THEN 'RN-03' END, "
        "CASE WHEN g <= 20 THEN %(pocos)s::uuid ELSE %(muchos)s::uuid END "
        "FROM generate_series(1, %(total)s) AS g",
        {
            "ana": ana,
            "inicio": T0,
            "pocos": obra_con_pocos,
            "muchos": obra_con_casi_todos,
            "total": TOTAL_DE_MUCHOS,
        },
    )
    conectar("migracion", base_de_prueba).execute("ANALYZE bitacora")
    # Sin esto, un plan sin índice podría deberse a una tabla que no se sembró como se creía.
    conteos = aplicacion.execute(
        "SELECT count(*), count(*) FILTER (WHERE obra_id = %s), "
        "count(*) FILTER (WHERE regla_negocio = 'RN-03') FROM bitacora",
        (obra_con_pocos,),
    ).fetchone()
    assert conteos == (TOTAL_DE_MUCHOS, ASIENTOS_POR_SELECTIVIDAD, ASIENTOS_POR_SELECTIVIDAD)
    return MuchosAsientos(obra_con_pocos, obra_con_casi_todos, T0)


# --------------------------------------------------------------------------- TC-49 a TC-52


def test_tkt007_ca06_filtro_por_obra_y_fechas(
    sesion_bd: Session, ana: uuid.UUID, sembrar_asientos: Sembrar
) -> None:
    """TC-49 · CA-6 esc. 1 · RN-04 — `desde` entra, `hasta` no, y la otra obra queda fuera."""
    from cimenta.auditoria.interfaz import consultar_bitacora

    o1, o2 = uuid.uuid4(), uuid.uuid4()
    en_t0, en_1h, en_2h, en_3h, de_otra_obra = sembrar_asientos(
        [
            Semilla(ocurrido_en=T0, usuario_id=ana, obra_id=o1),
            Semilla(ocurrido_en=T0 + HORA, usuario_id=ana, obra_id=o1),
            Semilla(ocurrido_en=T0 + 2 * HORA, usuario_id=ana, obra_id=o1),
            Semilla(ocurrido_en=T0 + 3 * HORA, usuario_id=ana, obra_id=o1),
            Semilla(ocurrido_en=T0 + HORA, usuario_id=ana, obra_id=o2),
        ]
    )

    pagina = consultar_bitacora(sesion_bd, obra_id=o1, desde=T0 + HORA, hasta=T0 + 3 * HORA)

    # Exactamente dos, el más reciente primero: el de `desde` entra, el de `hasta` y el de O2 no.
    assert [a.id for a in pagina.elementos] == [en_2h, en_1h]
    assert pagina.total == 2
    assert {en_t0, en_3h, de_otra_obra}.isdisjoint(a.id for a in pagina.elementos)


def _filas_de_la_matriz(
    ana: uuid.UUID, beto: uuid.UUID
) -> tuple[list[Semilla], uuid.UUID, uuid.UUID]:
    """Seis asientos que se distinguen por regla, usuario, tipo de entidad, entidad y acción."""
    requisicion_1, orden_1, requisicion_2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    semillas = [
        Semilla(T0, ana, "AUTORIZAR", "requisicion", requisicion_1, "RN-03"),
        Semilla(T0 + timedelta(minutes=1), beto, "RECHAZAR", "requisicion", requisicion_1, "RN-03"),
        Semilla(T0 + timedelta(minutes=2), ana, "AUTORIZAR", "orden_compra", orden_1, "RN-07"),
        Semilla(T0 + timedelta(minutes=3), beto, "CREAR", "orden_compra", orden_1, None),
        Semilla(T0 + timedelta(minutes=4), ana, "CREAR", "requisicion", requisicion_2, None),
        Semilla(T0 + timedelta(minutes=5), beto, "RECHAZAR", "requisicion", requisicion_2, "RN-07"),
    ]
    return semillas, requisicion_1, orden_1


# Qué asientos (por posición en `_filas_de_la_matriz`) devuelve cada combinación de filtros.
# `{"entidad": "requisicion_1"}` y similares se resuelven dentro del caso, porque el UUID nace ahí.
FILTROS_Y_SU_CONJUNTO = [
    pytest.param({"regla_negocio": "RN-03"}, {0, 1}, id="solo-regla-03"),
    pytest.param({"regla_negocio": "RN-07"}, {2, 5}, id="solo-regla-07"),
    pytest.param({"entidad_tipo": "orden_compra"}, {2, 3}, id="solo-tipo-de-entidad"),
    pytest.param({"entidad_id": "requisicion_1"}, {0, 1}, id="solo-entidad-id"),
    pytest.param(
        {"entidad_tipo": "requisicion", "entidad_id": "orden_1"},
        set(),
        id="tipo-y-entidad-que-no-coinciden-dan-la-interseccion-vacia",
    ),
    pytest.param({"accion": ["AUTORIZAR", "RECHAZAR"]}, {0, 1, 2, 5}, id="dos-acciones"),
    pytest.param({"accion": ["CREAR"]}, {3, 4}, id="una-accion"),
    pytest.param({"usuario": "beto"}, {1, 3, 5}, id="solo-usuario"),
    pytest.param(
        {"regla_negocio": "RN-07", "usuario": "beto", "accion": ["RECHAZAR"]},
        {5},
        id="tres-filtros-combinados-son-la-interseccion",
    ),
    pytest.param(
        {"regla_negocio": "RN-03", "usuario": "ana"},
        {0},
        id="regla-y-usuario",
    ),
    pytest.param({}, {0, 1, 2, 3, 4, 5}, id="sin-filtros-devuelve-todo"),
]


@pytest.mark.parametrize(("filtros", "esperados"), FILTROS_Y_SU_CONJUNTO)
def test_tkt007_ca06_filtro_por_regla_y_demas(
    sesion_bd: Session,
    ana: uuid.UUID,
    beto: uuid.UUID,
    sembrar_asientos: Sembrar,
    filtros: dict[str, Any],
    esperados: set[int],
) -> None:
    """TC-50 · CA-6 esc. 2 · RN-04 — cada filtro devuelve su conjunto, y combinados, la intersección."""
    from cimenta.auditoria.interfaz import consultar_bitacora

    semillas, requisicion_1, orden_1 = _filas_de_la_matriz(ana, beto)
    identificadores = sembrar_asientos(semillas)
    resolver: dict[str, Any] = {
        "requisicion_1": requisicion_1,
        "orden_1": orden_1,
        "ana": ana,
        "beto": beto,
    }
    argumentos: dict[str, Any] = {}
    for nombre, valor in filtros.items():
        if nombre == "usuario":
            argumentos["usuario_id"] = resolver[valor]
        elif nombre == "entidad_id":
            argumentos["entidad_id"] = resolver[valor]
        else:
            argumentos[nombre] = valor

    pagina = consultar_bitacora(sesion_bd, **argumentos)

    assert {a.id for a in pagina.elementos} == {identificadores[i] for i in esperados}
    assert pagina.total == len(esperados)


def test_tkt007_ca06_orden_con_desempate_estable(
    sesion_bd: Session, ana: uuid.UUID, sembrar_asientos: Sembrar
) -> None:
    """TC-51 · CA-6 esc. 3 · PA-T7 — con el mismo instante, el orden lo fija el `id` y las páginas no repiten ni pierden."""
    from cimenta.auditoria.interfaz import consultar_bitacora

    # Seis en el mismo instante y uno posterior: con seis empatados, un orden sin desempate coincidiría
    # por azar con el esperado una vez de cada 720.
    semillas = [Semilla(ocurrido_en=T0, usuario_id=ana) for _ in range(6)]
    semillas.append(Semilla(ocurrido_en=T0 + timedelta(seconds=1), usuario_id=ana))
    identificadores = sembrar_asientos(semillas)
    instante_de = dict(zip(identificadores, (s.ocurrido_en for s in semillas), strict=True))
    esperado = sorted(identificadores, key=lambda i: (instante_de[i], i), reverse=True)

    paginas = [
        consultar_bitacora(sesion_bd, pagina=numero, tamano_pagina=1) for numero in range(1, 8)
    ]
    concatenadas = [a.id for pagina in paginas for a in pagina.elementos]

    assert concatenadas == esperado
    assert len(set(concatenadas)) == len(identificadores)
    assert concatenadas[0] == identificadores[-1]  # el de T0 + 1 s es el más reciente
    assert all(len(pagina.elementos) == 1 for pagina in paginas)
    assert consultar_bitacora(sesion_bd, pagina=8, tamano_pagina=1).elementos == ()


def test_tkt007_ca06_paginacion_por_desplazamiento(
    sesion_bd: Session, ana: uuid.UUID, sembrar_asientos: Sembrar
) -> None:
    """TC-52 · CA-6 esc. 4 — la página 2 de 50 son los elementos 51 a 100, y `total` cuenta todos."""
    from cimenta.auditoria.interfaz import PaginaBitacora, consultar_bitacora

    identificadores = sembrar_asientos(
        [Semilla(ocurrido_en=T0 + timedelta(seconds=i), usuario_id=ana) for i in range(120)]
    )
    mas_reciente_primero = list(reversed(identificadores))

    por_omision = consultar_bitacora(sesion_bd)
    segunda = consultar_bitacora(sesion_bd, pagina=2, tamano_pagina=50)
    tercera = consultar_bitacora(sesion_bd, pagina=3, tamano_pagina=50)
    cuarta = consultar_bitacora(sesion_bd, pagina=4, tamano_pagina=50)

    assert isinstance(segunda, PaginaBitacora)
    assert [a.id for a in segunda.elementos] == mas_reciente_primero[50:100]
    assert (segunda.pagina, segunda.tamano_pagina, segunda.total) == (2, 50, 120)
    assert (por_omision.pagina, por_omision.tamano_pagina, por_omision.total) == (1, 50, 120)
    assert [a.id for a in por_omision.elementos] == mas_reciente_primero[:50]
    assert [a.id for a in tercera.elementos] == mas_reciente_primero[100:]
    assert len(tercera.elementos) == 20
    assert (tercera.pagina, tercera.total) == (3, 120)
    assert cuarta.elementos == ()
    assert (cuarta.pagina, cuarta.total) == (4, 120)


# --------------------------------------------------------------------------- TC-53 y TC-54

SIN_ZONA = datetime(2026, 10, 21, 9, 0)  # noqa: DTZ001 - el caso es la ausencia de zona

RECHAZOS_DE_LA_CONSULTA = [
    pytest.param(
        {"pagina": 0},
        [("pagina", "FUERA_DE_RANGO", "MENSAJE_PAGINA")],
        id="pagina-cero",
    ),
    pytest.param(
        {"tamano_pagina": 0},
        [("tamano_pagina", "FUERA_DE_RANGO", "MENSAJE_TAMANO")],
        id="tamano-cero",
    ),
    pytest.param(
        {"tamano_pagina": 201},
        [("tamano_pagina", "FUERA_DE_RANGO", "MENSAJE_TAMANO")],
        id="tamano-sobre-el-maximo",
    ),
    pytest.param(
        {"regla_negocio": "rn-03"},
        [("regla_negocio", "FORMATO", "MENSAJE_REGLA")],
        id="regla-en-minusculas",
    ),
    pytest.param(
        {"desde": T0 + HORA, "hasta": T0},
        [("hasta", "FUERA_DE_RANGO", "MENSAJE_RANGO")],
        id="rango-invertido",
    ),
    pytest.param(
        {"accion": ["BORRAR"]},
        [("accion", "VALOR_NO_PERMITIDO", "MENSAJE_ACCION")],
        id="verbo-inexistente",
    ),
    pytest.param(
        {"desde": SIN_ZONA},
        [("desde", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="desde-sin-zona",
    ),
    pytest.param(
        {"hasta": SIN_ZONA},
        [("hasta", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="hasta-sin-zona",
    ),
    pytest.param(
        {"desde": SIN_ZONA, "hasta": SIN_ZONA},
        [("desde", "FORMATO", "MENSAJE_SIN_ZONA"), ("hasta", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="los-dos-sin-zona-se-nombran-en-orden",
    ),
    pytest.param(
        {"desde": SIN_ZONA, "hasta": T0, "pagina": 0},
        [("desde", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="desde-sin-zona-sale-solo-aunque-haya-otro-campo-mal",
    ),
    pytest.param(
        {"desde": T0, "hasta": SIN_ZONA, "pagina": 0},
        [("hasta", "FORMATO", "MENSAJE_SIN_ZONA")],
        id="hasta-sin-zona-con-desde-con-zona-no-compara-instantes",
    ),
    pytest.param(
        {"pagina": 0, "tamano_pagina": 0, "regla_negocio": "RN-3"},
        [
            ("pagina", "FUERA_DE_RANGO", "MENSAJE_PAGINA"),
            ("tamano_pagina", "FUERA_DE_RANGO", "MENSAJE_TAMANO"),
            ("regla_negocio", "FORMATO", "MENSAJE_REGLA"),
        ],
        id="varios-defectos-a-la-vez-en-orden",
    ),
]


@pytest.mark.parametrize(("argumentos", "esperados"), RECHAZOS_DE_LA_CONSULTA)
def test_tkt007_ca06_rechazos_sin_tocar_la_base(
    sesion_bd: Session,
    sentencias: list[str],
    argumentos: dict[str, Any],
    esperados: list[tuple[str, str, str]],
) -> None:
    """TC-53 · CA-6 esc. 5 · RN-04 — un filtro mal formado lanza VALIDACION antes de emitir ninguna sentencia."""
    from cimenta.auditoria.interfaz import consultar_bitacora

    with pytest.raises(ValidacionRechazada) as rechazo:
        consultar_bitacora(sesion_bd, **argumentos)

    afirmar_validacion_rechazada(
        rechazo,
        [
            {"campo": campo, "codigo": codigo, "mensaje": mensaje(nombre)}
            for campo, codigo, nombre in esperados
        ],
    )
    # Ni el recuento ni la lectura: validar es lo primero y no abre ni una transacción.
    assert sentencias == []


def test_tkt007_ca06_asiento_leido_completo(
    sesion_bd: Session, ana: uuid.UUID, sembrar_asientos: Sembrar
) -> None:
    """TC-54 · CA-6 · M6 — la consulta devuelve las once columnas de lo escrito, con tipos de dominio."""
    from cimenta.auditoria.interfaz import (
        AccionBitacora,
        AsientoLeido,
        asentar_denegacion,
        consultar_bitacora,
    )

    obra, requisicion = uuid.uuid4(), uuid.uuid4()
    datos_de_la_denegacion = {"metodo": "GET", "ruta": "/api/v1/prueba/direccion"}
    autorizado = sembrar_asientos(
        [
            Semilla(
                ocurrido_en=T0,
                usuario_id=ana,
                accion="AUTORIZAR",
                entidad_id=requisicion,
                regla_negocio="RN-03",
                obra_id=obra,
                motivo="Excede el presupuesto de la partida",
                datos_antes={"disponible": "9000.0000"},
                datos_despues={"excedente": "3000.0000"},
            )
        ]
    )[0]
    denegado = asentar_denegacion(
        sesion_bd,
        usuario_id=ana,
        ocurrido_en=T0 + timedelta(minutes=5),
        motivo="ROL_INSUFICIENTE",
        datos=datos_de_la_denegacion,
    )
    sesion_bd.commit()

    pagina = consultar_bitacora(sesion_bd)

    assert pagina.total == 2
    assert isinstance(pagina.elementos, tuple)
    assert pagina.elementos == (
        AsientoLeido(
            id=denegado,
            entidad_tipo="usuario",
            entidad_id=ana,
            accion=AccionBitacora.DENEGAR,
            usuario_id=ana,
            ocurrido_en=T0 + timedelta(minutes=5),
            datos_antes=None,
            datos_despues=datos_de_la_denegacion,
            motivo="ROL_INSUFICIENTE",
            regla_negocio=None,
            obra_id=None,
        ),
        AsientoLeido(
            id=autorizado,
            entidad_tipo="requisicion",
            entidad_id=requisicion,
            accion=AccionBitacora.AUTORIZAR,
            usuario_id=ana,
            ocurrido_en=T0,
            datos_antes={"disponible": "9000.0000"},
            datos_despues={"excedente": "3000.0000"},
            motivo="Excede el presupuesto de la partida",
            regla_negocio="RN-03",
            obra_id=obra,
        ),
    )
    for leido in pagina.elementos:
        # `AccionBitacora` es un `StrEnum`: la cadena `"DENEGAR"` también cumpliría `==`, y no es un miembro.
        assert isinstance(leido.accion, AccionBitacora)
        assert leido.ocurrido_en.utcoffset() is not None


# --------------------------------------------------------------------------- TC-55 a TC-57


def test_tkt007_ca06_la_consulta_no_es_una_ruta() -> None:
    """TC-55 · CA-6 esc. 6 — la consulta se publica por la interfaz y ninguna ruta HTTP la monta todavía."""
    fabrica = importlib.import_module("servidor.fabrica")
    aplicacion = fabrica.crear_aplicacion(destino_registro=io.StringIO())

    rutas_api = [ruta.path for ruta in rutas_de(aplicacion.routes)]
    todas_las_rutas = [str(getattr(ruta, "path", "")) for ruta in aplicacion.routes]
    archivos_de_api = sorted(
        p.name
        for p in (RAIZ / "backend" / "cimenta" / "auditoria" / "api").iterdir()
        if p.is_file()
    )

    # Sin esta aserción, una aplicación sin ninguna ruta cumpliría «ninguna contiene bitacora».
    assert todas_las_rutas
    assert not [ruta for ruta in (*rutas_api, *todas_las_rutas) if "bitacora" in ruta.lower()]
    assert archivos_de_api == ["__init__.py"]


def test_tkt007_ca11_los_indices_se_usan(
    conectar: Conectar, base_de_prueba: str, muchos_asientos: MuchosAsientos
) -> None:
    """TC-56 · CA-11 · S1 — con datos selectivos, el planificador usa los dos índices de la bitácora."""
    aplicacion = conectar("aplicacion", base_de_prueba)
    desde, hasta = muchos_asientos.inicio, muchos_asientos.inicio + HORA

    plan_por_obra = plan_de(
        aplicacion,
        "SELECT * FROM bitacora "
        f"WHERE obra_id = '{muchos_asientos.obra_con_pocos}' "  # noqa: S608
        f"AND ocurrido_en >= '{desde.isoformat()}' AND ocurrido_en < '{hasta.isoformat()}' "
        "ORDER BY ocurrido_en DESC, id DESC LIMIT 50",
    )
    plan_por_regla = plan_de(
        aplicacion,
        "SELECT * FROM bitacora WHERE regla_negocio = 'RN-03' "
        "ORDER BY ocurrido_en DESC, id DESC LIMIT 50",
    )

    assert INDICE_DE_OBRA in indices_del_plan(plan_por_obra), json.dumps(plan_por_obra)
    assert INDICE_DE_REGLA in indices_del_plan(plan_por_regla), json.dumps(plan_por_regla)


def test_tkt007_ca11_la_consulta_publicada_usa_los_indices(
    conectar: Conectar,
    base_de_prueba: str,
    sesion_bd: Session,
    emitidas: list[tuple[str, Mapping[str, Any]]],
    muchos_asientos: MuchosAsientos,
) -> None:
    """TC-56 (complemento) · CA-11 · S1 — la sentencia que `consultar_bitacora` emite de verdad usa esos índices."""
    from cimenta.auditoria.interfaz import consultar_bitacora

    consultar_bitacora(
        sesion_bd,
        obra_id=muchos_asientos.obra_con_pocos,
        desde=muchos_asientos.inicio,
        hasta=muchos_asientos.inicio + HORA,
    )
    por_obra = [e for e in emitidas if e[0].lstrip().upper().startswith("SELECT BITACORA.")]
    emitidas.clear()
    consultar_bitacora(sesion_bd, regla_negocio="RN-03")
    por_regla = [e for e in emitidas if e[0].lstrip().upper().startswith("SELECT BITACORA.")]
    sesion_bd.rollback()

    # La lectura de la página, no el recuento: es la que ordena y limita.
    assert len(por_obra) == 1
    assert len(por_regla) == 1
    aplicacion = conectar("aplicacion", base_de_prueba)
    indices_por_obra = indices_del_plan(plan_de(aplicacion, *por_obra[0]))
    indices_por_regla = indices_del_plan(plan_de(aplicacion, *por_regla[0]))
    assert INDICE_DE_OBRA in indices_por_obra, por_obra[0][0]
    assert INDICE_DE_REGLA in indices_por_regla, por_regla[0][0]


def test_tkt007_ca08_interfaz_completa() -> None:
    """TC-57 · CA-8 esc. 1 — la interfaz publica exactamente los seis nombres del diseño."""
    from cimenta.auditoria import interfaz
    from cimenta.auditoria.interfaz import AsientoLeido, PaginaBitacora, consultar_bitacora

    nombres = {
        "AccionBitacora",
        "AsientoLeido",
        "PaginaBitacora",
        "asentar",
        "asentar_denegacion",
        "consultar_bitacora",
    }

    assert set(interfaz.__all__) == nombres
    assert all(hasattr(interfaz, nombre) for nombre in nombres)
    assert (AsientoLeido, PaginaBitacora, consultar_bitacora) == (
        interfaz.AsientoLeido,
        interfaz.PaginaBitacora,
        interfaz.consultar_bitacora,
    )
