"""Filtros de la consulta de la bitácora (TKT-007, fila 7): TC-46 a TC-48.

Sin Docker. Prueba `cimenta/auditoria/dominio/consulta.py`: `revisar_filtros` devuelve la tupla de
defectos por campo, en el orden de la firma, y nunca lanza (M6, CA-6). `desde` es inclusivo y `hasta`
exclusivo; `desde == hasta` es un rango vacío que se admite y `hasta < desde` es defecto.

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: mientras
`consulta.py` no exista, cada caso falla por sí solo con el `ModuleNotFoundError` de
`cimenta.auditoria.dominio.consulta` (la razón esperada) y la recolección no se cae. Los mensajes
literales se piden por nombre con `getattr` para que la parametrización tampoco dependa del módulo.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

# (valor de `pagina`, código esperado, nombre del mensaje literal) de TC-47.
PAGINAS_INVALIDAS = [
    pytest.param(0, "FUERA_DE_RANGO", "MENSAJE_PAGINA", id="pagina-cero"),
    pytest.param(-1, "FUERA_DE_RANGO", "MENSAJE_PAGINA", id="pagina-negativa"),
    pytest.param(True, "FORMATO", "MENSAJE_ENTERO", id="pagina-booleano"),
    pytest.param("2", "FORMATO", "MENSAJE_ENTERO", id="pagina-cadena"),
    pytest.param(1.5, "FORMATO", "MENSAJE_ENTERO", id="pagina-float"),
    pytest.param(None, "FORMATO", "MENSAJE_ENTERO", id="pagina-nula"),
]

# (valor de `tamano_pagina`, código esperado, nombre del mensaje literal) de TC-47.
TAMANOS_INVALIDOS = [
    pytest.param(0, "FUERA_DE_RANGO", "MENSAJE_TAMANO", id="tamano-cero"),
    pytest.param(-5, "FUERA_DE_RANGO", "MENSAJE_TAMANO", id="tamano-negativo"),
    pytest.param(201, "FUERA_DE_RANGO", "MENSAJE_TAMANO", id="tamano-sobre-el-maximo"),
    pytest.param(True, "FORMATO", "MENSAJE_ENTERO", id="tamano-booleano"),
    pytest.param("50", "FORMATO", "MENSAJE_ENTERO", id="tamano-cadena"),
    pytest.param(50.0, "FORMATO", "MENSAJE_ENTERO", id="tamano-float"),
]


def _filtros(**cambios: object) -> tuple[DefectoDeCampo, ...]:
    """Llama a `revisar_filtros` con todo válido y nulo, salvo lo que el caso cambia."""
    from cimenta.auditoria.dominio.consulta import revisar_filtros

    campos: dict[str, object] = {
        "pagina": 1,
        "tamano_pagina": 50,
        "regla_negocio": None,
        "entidad_tipo": None,
        "acciones": [],
        "desde": None,
        "hasta": None,
        **cambios,
    }
    return revisar_filtros(**campos)  # type: ignore[arg-type]


def _mensaje(nombre: str, modulo: str = "consulta") -> str:
    """Un `MENSAJE_*` del dominio por su nombre: el literal lo fija el diseño."""
    paquete = importlib.import_module(f"cimenta.auditoria.dominio.{modulo}")
    mensaje = getattr(paquete, nombre)
    assert isinstance(mensaje, str)
    return mensaje


def test_tkt007_ca06_constantes_de_paginacion() -> None:
    """TC-46 (constantes) · CA-6 esc. 4 — la paginación sigue al borrador: página 1, 50 por omisión, tope 200."""
    from cimenta.auditoria.dominio.consulta import (
        PAGINA_POR_OMISION,
        TAMANO_PAGINA_MAXIMO,
        TAMANO_PAGINA_POR_OMISION,
    )

    assert PAGINA_POR_OMISION == 1
    assert TAMANO_PAGINA_POR_OMISION == 50
    assert TAMANO_PAGINA_MAXIMO == 200


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({}, id="todo-nulo"),
        pytest.param({"pagina": 1, "tamano_pagina": 50}, id="por-omision"),
        pytest.param({"pagina": 7}, id="pagina-alta"),
        pytest.param({"tamano_pagina": 1}, id="tamano-minimo"),
        pytest.param({"tamano_pagina": 200}, id="tamano-maximo"),
        pytest.param({"regla_negocio": "RN-03"}, id="regla"),
        pytest.param({"entidad_tipo": "requisicion"}, id="entidad"),
        pytest.param({"acciones": ["AUTORIZAR", "RECHAZAR"]}, id="acciones"),
        pytest.param({"acciones": ["DENEGAR"]}, id="accion-denegar"),
        pytest.param({"desde": 1, "hasta": 2}, id="rango-ordenado"),
        pytest.param({"desde": 3, "hasta": 3}, id="rango-vacio-desde-igual-hasta"),
        pytest.param({"desde": 3}, id="solo-desde"),
        pytest.param({"hasta": 3}, id="solo-hasta"),
        pytest.param({"desde": T0, "hasta": T0 + timedelta(hours=1)}, id="rango-de-instantes"),
    ],
)
def test_tkt007_ca06_filtros_validos(cambios: dict[str, object]) -> None:
    """TC-46 · CA-6 esc. 4 — filtros bien formados, en sus bordes, no producen ningún defecto."""
    assert _filtros(**cambios) == ()


def test_tkt007_ca06_filtros_validos_con_todo_a_la_vez() -> None:
    """TC-46 (complemento) · CA-6 esc. 4 — todos los filtros juntos y bien formados: tupla vacía."""
    resultado = _filtros(
        pagina=2,
        tamano_pagina=200,
        regla_negocio="RN-25",
        entidad_tipo="orden_compra",
        acciones=["AUTORIZAR", "RECHAZAR"],
        desde=1,
        hasta=2,
    )

    assert resultado == ()


def test_tkt007_ca06_la_accion_se_acepta_como_miembro_del_enum() -> None:
    """TC-46 (complemento) · CA-6 — un miembro de AccionBitacora vale igual que su cadena."""
    from cimenta.auditoria.dominio.asiento import AccionBitacora

    assert _filtros(acciones=[AccionBitacora.AUTORIZAR, "RECHAZAR"]) == ()


@pytest.mark.parametrize(("valor", "codigo", "nombre_mensaje"), PAGINAS_INVALIDAS)
def test_tkt007_ca06_paginacion_invalida(valor: object, codigo: str, nombre_mensaje: str) -> None:
    """TC-47 · CA-6 esc. 5 — la página es un entero desde 1: 0 y negativos son FUERA_DE_RANGO; lo que no es entero, FORMATO."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _filtros(pagina=valor)

    assert resultado == (DefectoDeCampo("pagina", codigo, _mensaje(nombre_mensaje)),)


@pytest.mark.parametrize(("valor", "codigo", "nombre_mensaje"), TAMANOS_INVALIDOS)
def test_tkt007_ca06_tamano_de_pagina_invalido(
    valor: object, codigo: str, nombre_mensaje: str
) -> None:
    """TC-47 · CA-6 esc. 5 — el tamaño de página es un entero de 1 a 200: fuera de rango o no entero es defecto."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _filtros(tamano_pagina=valor)

    assert resultado == (DefectoDeCampo("tamano_pagina", codigo, _mensaje(nombre_mensaje)),)


def test_tkt007_ca06_regla_mal_formada() -> None:
    """TC-48 · CA-6 esc. 5, RN-04 — una regla que no es RN-NN es FORMATO con el mensaje de la regla."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    esperado = (DefectoDeCampo("regla_negocio", "FORMATO", _mensaje("MENSAJE_REGLA", "asiento")),)

    assert _filtros(regla_negocio="rn-03") == esperado
    assert _filtros(regla_negocio="RN-3") == esperado
    assert _filtros(regla_negocio="RN-03\n") == esperado
    assert _filtros(regla_negocio="RN-３０") == esperado  # noqa: RUF001 — dígitos de ancho completo
    assert _filtros(regla_negocio=3) == esperado


def test_tkt007_ca06_rango_invertido() -> None:
    """TC-48 · CA-6 esc. 5 — hasta anterior a desde es FUERA_DE_RANGO, nombrado en `hasta`, con MENSAJE_RANGO."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _filtros(desde=5, hasta=4)

    assert resultado == (DefectoDeCampo("hasta", "FUERA_DE_RANGO", _mensaje("MENSAJE_RANGO")),)


def test_tkt007_ca06_rango_invertido_de_instantes() -> None:
    """TC-48 (complemento) · CA-6 esc. 5 — la comparación es genérica: con instantes con zona, hasta antes de desde es defecto."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _filtros(desde=T0 + timedelta(hours=1), hasta=T0)

    assert resultado == (DefectoDeCampo("hasta", "FUERA_DE_RANGO", _mensaje("MENSAJE_RANGO")),)


def test_tkt007_ca06_accion_inexistente() -> None:
    """TC-48 · CA-6 esc. 5 — un verbo fuera de los 22 es VALOR_NO_PERMITIDO en `accion`, aunque los demás sean válidos."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    esperado = (
        DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", _mensaje("MENSAJE_ACCION", "asiento")),
    )

    assert _filtros(acciones=["BORRAR"]) == esperado
    assert _filtros(acciones=["AUTORIZAR", "BORRAR"]) == esperado
    assert _filtros(acciones=["autorizar"]) == esperado
    assert _filtros(acciones=[5]) == esperado
    assert _filtros(acciones=[None]) == esperado


def test_tkt007_ca06_varias_acciones_inexistentes_dan_un_solo_defecto() -> None:
    """TC-48 (complemento) · CA-6 esc. 5 — dos verbos inexistentes producen un solo defecto de `accion`, no uno por verbo."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _filtros(acciones=["BORRAR", "QUITAR"])

    assert resultado == (
        DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", _mensaje("MENSAJE_ACCION", "asiento")),
    )


def test_tkt007_ca06_entidad_tipo_vacia() -> None:
    """TC-48 · CA-6 esc. 5 — una entidad_tipo vacía o en blanco es OBLIGATORIO; una que no es texto, FORMATO."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    obligatorio = (
        DefectoDeCampo("entidad_tipo", "OBLIGATORIO", _mensaje("MENSAJE_OBLIGATORIO", "asiento")),
    )

    assert _filtros(entidad_tipo="") == obligatorio
    assert _filtros(entidad_tipo="   ") == obligatorio
    assert _filtros(entidad_tipo=7) == (
        DefectoDeCampo("entidad_tipo", "FORMATO", _mensaje("MENSAJE_TEXTO", "asiento")),
    )


def test_tkt007_ca06_los_defectos_se_acumulan_en_orden() -> None:
    """TC-48 (complemento) · CA-6 esc. 5 — con todo mal, un defecto por campo y en el orden de la firma."""
    resultado = _filtros(
        pagina=0,
        tamano_pagina=201,
        regla_negocio="rn-03",
        entidad_tipo="",
        acciones=["BORRAR"],
        desde=5,
        hasta=4,
    )

    assert [(d.campo, d.codigo) for d in resultado] == [
        ("pagina", "FUERA_DE_RANGO"),
        ("tamano_pagina", "FUERA_DE_RANGO"),
        ("regla_negocio", "FORMATO"),
        ("entidad_tipo", "OBLIGATORIO"),
        ("accion", "VALOR_NO_PERMITIDO"),
        ("hasta", "FUERA_DE_RANGO"),
    ]


def test_tkt007_ca06_codigos_del_catalogo() -> None:
    """TC-48 (complemento) · CA-6, TKT-005 — todo código que emite la consulta existe en CodigoValidacion del contrato de error."""
    from contrato_error import CodigoValidacion

    casos: list[dict[str, object]] = [
        {"pagina": 0},
        {"pagina": "2"},
        {"tamano_pagina": 201},
        {"regla_negocio": "rn-03"},
        {"entidad_tipo": ""},
        {"entidad_tipo": 7},
        {"acciones": ["BORRAR"]},
        {"desde": 5, "hasta": 4},
    ]

    emitidos = {d.codigo for caso in casos for d in _filtros(**caso)}

    assert emitidos == {"OBLIGATORIO", "FORMATO", "VALOR_NO_PERMITIDO", "FUERA_DE_RANGO"}
    assert emitidos <= {c.value for c in CodigoValidacion}
