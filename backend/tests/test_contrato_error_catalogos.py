"""Catálogos cerrados del contrato de error (TKT-005, fila 2): TC-01, TC-02 y TC-39.

Sin Docker: ninguna prueba de este archivo pide `contenedor_postgres` ni nada que dependa de
él (CA-R4). Los catálogos del código se comparan con los `enum` de `docs/api/openapi.yaml`
en cada ejecución: si el borrador cambia y el código no, o al revés, la deriva se ve aquí.

`contrato_error` se importa dentro de cada prueba, no al principio del archivo: TC-39 es el
oráculo del validador de esquemas y no depende del paquete, así que debe poder ejecutarse
—y nacer en verde— antes de que `contrato_error` exista.
"""

import enum
import functools
import importlib
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

RAIZ = Path(__file__).resolve().parents[2]

CID = "c3d4e5f6-a7b8-4901-8cde-f01234567890"


@functools.cache
def borrador() -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8"))


def validar_contra(esquema: str, cuerpo: object) -> None:
    raiz = {"$ref": f"#/components/schemas/{esquema}", "components": borrador()["components"]}
    Draft202012Validator(raiz, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(cuerpo)


def catalogo(nombre: str) -> type[enum.StrEnum]:
    modulo = importlib.import_module("contrato_error.catalogos")
    clase: type[enum.StrEnum] = getattr(modulo, nombre)
    return clase


def enum_del_borrador(ruta: tuple[str, ...]) -> list[Any]:
    nodo: Any = borrador()["components"]["schemas"]
    for clave in ruta:
        nodo = nodo[clave]
    assert isinstance(nodo, list)
    return nodo


PARES_CATALOGO_BORRADOR = [
    pytest.param("CodigoConflicto", ("CodigoConflicto", "enum"), id="CodigoConflicto"),
    pytest.param("Rol", ("Rol", "enum"), id="Rol"),
    pytest.param("Metodo", ("Accion", "properties", "metodo", "enum"), id="Metodo"),
    pytest.param(
        "CodigoConcurrencia",
        ("ErrorConcurrencia", "properties", "codigo", "enum"),
        id="CodigoConcurrencia",
    ),
    pytest.param(
        "CodigoValidacion",
        ("ErrorValidacion", "properties", "errores", "items", "properties", "codigo", "enum"),
        id="CodigoValidacion",
    ),
    pytest.param(
        "MotivoPermiso",
        ("ErrorPermiso", "properties", "motivo", "enum"),
        id="MotivoPermiso",
    ),
    pytest.param(
        "MotivoSesion",
        ("ErrorSesion", "properties", "motivo", "enum"),
        id="MotivoSesion",
    ),
]


@pytest.mark.parametrize(("nombre_clase", "ruta_en_el_borrador"), PARES_CATALOGO_BORRADOR)
def test_tkt005_ca04_catalogo_igual_al_borrador(
    nombre_clase: str, ruta_en_el_borrador: tuple[str, ...]
) -> None:
    """TC-01 · CA-4 esc. 2 — el catálogo del código y el enum del borrador son el mismo conjunto."""
    del_borrador = enum_del_borrador(ruta_en_el_borrador)
    clase = catalogo(nombre_clase)

    assert all(isinstance(valor, str) for valor in del_borrador)
    assert {miembro.value for miembro in clase} == set(del_borrador)
    assert len(clase) == len(del_borrador)


def test_tkt005_ca04_catalogo_de_conflicto_tiene_26_codigos() -> None:
    """TC-01 · CA-4 esc. 2 — el borrador declara 26 códigos de conflicto y el código los 26."""
    del_borrador = enum_del_borrador(("CodigoConflicto", "enum"))

    assert len(del_borrador) == 26
    assert len(catalogo("CodigoConflicto")) == 26


def test_tkt005_ca04_codigo_conflicto_rechaza_fuera_del_catalogo() -> None:
    """TC-02 · CA-4 esc. 3 — un código fuera del catálogo cerrado no se puede construir."""
    assert "SOLICITUD_YA_USADA" not in enum_del_borrador(("CodigoConflicto", "enum"))

    with pytest.raises(ValueError, match=re.escape("SOLICITUD_YA_USADA")):
        catalogo("CodigoConflicto")("SOLICITUD_YA_USADA")


CUERPO_REGLA_VALIDO: dict[str, object] = {
    "tipo": "REGLA_NEGOCIO",
    "regla": "RN-03",
    "mensaje": "La requisición excede el importe presupuestado.",
    "detalle": {"excedente": "3000.0000"},
    "acciones": [],
    "correlacion_id": CID,
}


@pytest.mark.parametrize(
    "defecto",
    [
        pytest.param({"tipo": "OTRO"}, id="tipo_ajeno"),
        pytest.param({"regla": "RN3"}, id="regla_mal_formada"),
        pytest.param({"correlacion_id": "no-es-uuid"}, id="correlacion_que_no_es_uuid"),
    ],
)
def test_tkt005_ca13_el_validador_rechaza(defecto: dict[str, object]) -> None:
    """TC-39 · M8 (CA-13) — oráculo del oráculo: el validador del borrador rechaza un cuerpo defectuoso.

    Si el validador aceptara estos tres, ninguna validación contra el borrador del plan probaría
    nada. Nace en verde: no depende de `contrato_error`.
    """
    validar_contra("ErrorReglaNegocio", CUERPO_REGLA_VALIDO)

    with pytest.raises(ValidationError):
        validar_contra("ErrorReglaNegocio", {**CUERPO_REGLA_VALIDO, **defecto})
