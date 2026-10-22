"""Forma del asiento de la bitácora (TKT-007, fila 3): TC-23 a TC-32.

Sin Docker. Prueba `cimenta/auditoria/dominio/asiento.py`: `revisar_asiento` devuelve el `Asiento`
normalizado o todos sus defectos, en el orden de los campos, y nunca lanza (RN-04, M4, regla 1).

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: mientras
`asiento.py` no exista, cada caso falla por sí solo con el `ModuleNotFoundError` de
`cimenta.auditoria.dominio.asiento` (la razón esperada) y la recolección no se cae. Los mensajes
literales se piden por nombre con `getattr` para que la parametrización tampoco dependa del módulo.
"""

from __future__ import annotations

import ast
import importlib
import os
import re
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from cimenta.auditoria.dominio.asiento import ResultadoAsiento

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
BORRADOR = RAIZ / "docs" / "api" / "openapi.yaml"
DOMINIO_DE_AUDITORIA = BACKEND / "cimenta" / "auditoria" / "dominio"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")
# Lista blanca del dominio de auditoría (design, «Dominio»): nada más se importa.
IMPORTABLES = {"__future__", "collections.abc", "dataclasses", "enum", "re", "typing", "uuid"}
PAQUETE_PROPIO = "cimenta.auditoria.dominio"

ENTIDAD = uuid.UUID("11111111-1111-4111-8111-111111111111")
USUARIO = uuid.UUID("22222222-2222-4222-8222-222222222222")
OBRA = uuid.UUID("33333333-3333-4333-8333-333333333333")
SOLICITUD = uuid.UUID("44444444-4444-4444-8444-444444444444")

# Reglas mal formadas: la lista la comparten TC-24 y TC-31.
REGLAS_MAL_FORMADAS = [
    pytest.param("rn-03", id="minusculas"),
    pytest.param("XX-03", id="prefijo-ajeno"),
    pytest.param("RN-3", id="un-digito"),
    pytest.param("RN-033", id="tres-digitos"),
    pytest.param("RN-03 ", id="espacio-final"),
    pytest.param("RN-03\n", id="salto-de-linea-final"),
    pytest.param("RN-３０", id="digitos-de-ancho-completo"),
    pytest.param(3, id="no-es-texto"),
]

# (campo, valor, código esperado, nombre del mensaje literal) de TC-28.
FORMAS_MAL_FORMADAS = [
    pytest.param("entidad_tipo", "", "OBLIGATORIO", "MENSAJE_OBLIGATORIO", id="tipo-vacio"),
    pytest.param("entidad_tipo", "  ", "OBLIGATORIO", "MENSAJE_OBLIGATORIO", id="tipo-en-blanco"),
    pytest.param("entidad_tipo", None, "OBLIGATORIO", "MENSAJE_OBLIGATORIO", id="tipo-nulo"),
    pytest.param("entidad_tipo", 7, "FORMATO", "MENSAJE_TEXTO", id="tipo-no-es-texto"),
    pytest.param("entidad_id", None, "OBLIGATORIO", "MENSAJE_OBLIGATORIO", id="entidad-nula"),
    pytest.param("entidad_id", "x", "FORMATO", "MENSAJE_UUID", id="entidad-no-es-uuid"),
    pytest.param("motivo", "  ", "OBLIGATORIO", "MENSAJE_OBLIGATORIO", id="motivo-en-blanco"),
    pytest.param("motivo", 5, "FORMATO", "MENSAJE_TEXTO", id="motivo-no-es-texto"),
    pytest.param("obra_id", "x", "FORMATO", "MENSAJE_UUID", id="obra-no-es-uuid"),
    pytest.param(
        "datos_despues", [1], "FORMATO", "MENSAJE_DATOS_NO_OBJETO", id="datos-no-es-objeto"
    ),
    pytest.param(
        "datos_despues", {1: "a"}, "FORMATO", "MENSAJE_CLAVE_NO_CADENA", id="clave-no-es-cadena"
    ),
]


def _base() -> dict[str, object]:
    """Un asiento válido con todos sus campos: cada caso cambia solo lo que prueba."""
    return {
        "accion": "AUTORIZAR",
        "entidad_tipo": "requisicion",
        "entidad_id": ENTIDAD,
        "usuario_id": USUARIO,
        "regla_negocio": "RN-03",
        "obra_id": OBRA,
        "motivo": "Excedente autorizado por la dirección",
        "datos_antes": None,
        "datos_despues": None,
    }


def _revisar(**cambios: object) -> ResultadoAsiento:
    from cimenta.auditoria.dominio.asiento import revisar_asiento

    campos = {**_base(), **cambios}
    return revisar_asiento(
        accion=campos["accion"],
        entidad_tipo=campos["entidad_tipo"],
        entidad_id=campos["entidad_id"],
        usuario_id=campos["usuario_id"],
        regla_negocio=campos["regla_negocio"],
        obra_id=campos["obra_id"],
        motivo=campos["motivo"],
        datos_antes=campos["datos_antes"],
        datos_despues=campos["datos_despues"],
    )


def _mensaje(nombre: str) -> str:
    """Un `MENSAJE_*` del dominio por su nombre: el literal lo fija el diseño y vive en `asiento.py`."""
    modulo = importlib.import_module("cimenta.auditoria.dominio.asiento")
    mensaje = getattr(modulo, nombre)
    assert isinstance(mensaje, str)
    return mensaje


def test_tkt007_ca05_asiento_bien_formado() -> None:
    """TC-23 · CA-5 esc. 1 — un asiento completo no tiene defectos y sale normalizado."""
    from cimenta.auditoria.dominio.asiento import AccionBitacora, Asiento

    resultado = _revisar(
        datos_antes={"disponible": "9000.0000"},
        datos_despues={
            "excedente": "3000.0000",
            "solicitud_id": SOLICITUD,
            "renglones": [{"cantidad": 3, "anulado": False, "nota": None}],
        },
    )

    assert resultado.defectos == ()
    assert resultado.asiento == Asiento(
        accion=AccionBitacora.AUTORIZAR,
        entidad_tipo="requisicion",
        entidad_id=ENTIDAD,
        usuario_id=USUARIO,
        regla_negocio="RN-03",
        obra_id=OBRA,
        motivo="Excedente autorizado por la dirección",
        datos_antes={"disponible": "9000.0000"},
        datos_despues={
            "excedente": "3000.0000",
            "solicitud_id": str(SOLICITUD),
            "renglones": [{"cantidad": 3, "anulado": False, "nota": None}],
        },
    )
    assert resultado.asiento is not None
    assert isinstance(resultado.asiento.accion, AccionBitacora)
    # `False == 0` en Python: la identidad demuestra que el booleano no se volvió entero.
    datos = resultado.asiento.datos_despues
    assert datos is not None
    renglones = datos["renglones"]
    assert isinstance(renglones, list)
    renglon = renglones[0]
    assert isinstance(renglon, dict)
    assert renglon["anulado"] is False
    assert renglon["nota"] is None


@pytest.mark.parametrize("regla", REGLAS_MAL_FORMADAS)
def test_tkt007_ca05_regla_mal_formada(regla: object) -> None:
    """TC-24 · CA-5 esc. 2, RN-04 — la regla es RN-NN con dígitos ASCII y nada alrededor."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(regla_negocio=regla)

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo("regla_negocio", "FORMATO", _mensaje("MENSAJE_REGLA")),
    )


@pytest.mark.parametrize("regla", ["RN-03", "RN-25", None], ids=["RN-03", "RN-25", "nula"])
def test_tkt007_ca05_regla_bien_formada_o_ausente_pasa(regla: str | None) -> None:
    """TC-24 (complemento) · CA-5 esc. 1 — una regla RN-NN o ninguna regla no produce defecto."""
    resultado = _revisar(regla_negocio=regla)

    assert resultado.defectos == ()
    assert resultado.asiento is not None
    assert resultado.asiento.regla_negocio == regla


@pytest.mark.parametrize(
    ("campo", "valor", "ruta"),
    [
        pytest.param("datos_despues", {"importe": 12.5}, "datos_despues.importe", id="float"),
        pytest.param(
            "datos_despues",
            {"renglones": [{"precio": 1.0}]},
            "datos_despues.renglones[0].precio",
            id="float-anidado-en-lista",
        ),
        pytest.param(
            "datos_despues", {"importe": Decimal("12.50")}, "datos_despues.importe", id="decimal"
        ),
        pytest.param(
            "datos_antes", {"importe": float("nan")}, "datos_antes.importe", id="nan-en-antes"
        ),
    ],
)
def test_tkt007_ca05_float_y_decimal_rechazados(campo: str, valor: object, ruta: str) -> None:
    """TC-25 · CA-5 esc. 3, regla 1 — un float o un Decimal en datos_* es defecto con la ruta del valor."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(**{campo: valor})

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo(ruta, "FORMATO", _mensaje("MENSAJE_VALOR_NO_JSON")),
    )


@pytest.mark.parametrize("verbo", ["BORRAR", "autorizar", "", None, 5], ids=repr)
def test_tkt007_ca05_verbo_inexistente(verbo: object) -> None:
    """TC-26 · CA-5 esc. 4 — un verbo fuera de los 22 (o con otra mayúscula) es VALOR_NO_PERMITIDO."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(accion=verbo)

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", _mensaje("MENSAJE_ACCION")),
    )


@pytest.mark.parametrize("forma", ["miembro", "cadena"])
def test_tkt007_ca05_denegar_es_un_verbo_valido(forma: str) -> None:
    """TC-26 (complemento) · CA-5, CA-4 — DENEGAR pasa como miembro del enum y como cadena."""
    from cimenta.auditoria.dominio.asiento import AccionBitacora

    verbo: object = AccionBitacora.DENEGAR if forma == "miembro" else "DENEGAR"

    resultado = _revisar(accion=verbo)

    assert resultado.defectos == ()
    assert resultado.asiento is not None
    assert resultado.asiento.accion is AccionBitacora.DENEGAR


def test_tkt007_ca04_sin_usuario() -> None:
    """TC-27 · CA-4 esc. 2 — un asiento sin usuario no se forma: nulo es OBLIGATORIO, no-UUID es FORMATO."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    nulo = _revisar(usuario_id=None)
    ajeno = _revisar(usuario_id="abc")

    assert nulo.asiento is None
    assert nulo.defectos == (
        DefectoDeCampo("usuario_id", "OBLIGATORIO", _mensaje("MENSAJE_OBLIGATORIO")),
    )
    assert ajeno.asiento is None
    assert ajeno.defectos == (DefectoDeCampo("usuario_id", "FORMATO", _mensaje("MENSAJE_UUID")),)


@pytest.mark.parametrize(("campo", "valor", "codigo", "nombre_mensaje"), FORMAS_MAL_FORMADAS)
def test_tkt007_ca05_forma_de_entidad_motivo_y_datos(
    campo: str, valor: object, codigo: str, nombre_mensaje: str
) -> None:
    """TC-28 · CA-5 — entidad, motivo, obra y datos mal formados nombran su campo, su código y su mensaje."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(**{campo: valor})

    assert resultado.asiento is None
    assert resultado.defectos == (DefectoDeCampo(campo, codigo, _mensaje(nombre_mensaje)),)


def test_tkt007_ca05_clave_no_cadena_anidada_lleva_su_ruta() -> None:
    """TC-28 (complemento) · CA-5 — una clave que no es cadena, dentro de un objeto anidado, nombra la ruta del objeto."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(datos_antes={"lineas": {1: "a"}})

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo("datos_antes.lineas", "FORMATO", _mensaje("MENSAJE_CLAVE_NO_CADENA")),
    )


# (campo, valor, ruta del defecto) de TC-58. PostgreSQL no admite U+0000 en `text` ni en `jsonb`: psycopg
# lanza `DataError`. Un texto con NUL se rechaza como FORMATO antes de llegar al motor (F001, ciclo 1).
# Para una clave con NUL la ruta es la del objeto que la contiene, como en MENSAJE_CLAVE_NO_CADENA.
NUL_EN_TEXTOS = [
    pytest.param("motivo", "Excede\x00 el presupuesto", "motivo", id="motivo"),
    pytest.param("motivo", "\x00", "motivo", id="motivo-solo-nul"),
    pytest.param("entidad_tipo", "requisicion\x00", "entidad_tipo", id="entidad-tipo"),
    pytest.param(
        "datos_despues", {"nota": "a\x00b"}, "datos_despues.nota", id="cadena-de-datos-despues"
    ),
    pytest.param("datos_antes", {"nota": "\x00"}, "datos_antes.nota", id="cadena-de-datos-antes"),
    pytest.param("datos_despues", {"a\x00b": "x"}, "datos_despues", id="clave-de-datos-despues"),
    pytest.param(
        "datos_despues",
        {"lineas": {"a\x00": 1}},
        "datos_despues.lineas",
        id="clave-anidada-en-mapa",
    ),
    pytest.param(
        "datos_despues",
        {"renglones": [{"nota": "x\x00y"}]},
        "datos_despues.renglones[0].nota",
        id="cadena-en-mapa-dentro-de-lista",
    ),
    pytest.param(
        "datos_despues",
        {"etiquetas": ["ok", "mal\x00"]},
        "datos_despues.etiquetas[1]",
        id="cadena-directa-en-lista",
    ),
    pytest.param(
        "datos_antes",
        {"a": {"b": {"c": "x\x00"}}},
        "datos_antes.a.b.c",
        id="cadena-en-mapas-anidados",
    ),
]


@pytest.mark.parametrize(("campo", "valor", "ruta"), NUL_EN_TEXTOS)
def test_tkt007_ca05_nul_en_texto_rechazado(campo: str, valor: object, ruta: str) -> None:
    """TC-58 · CA-5 (F001) · regla 8 — un U+0000 en un texto o clave es FORMATO con la ruta, antes del motor."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(**{campo: valor})

    assert resultado.asiento is None
    assert resultado.defectos == (DefectoDeCampo(ruta, "FORMATO", _mensaje("MENSAJE_NUL")),)


def test_tkt007_ca05_nul_en_varios_campos_se_acumula_en_orden() -> None:
    """TC-58 (complemento) · CA-5 (F001) — NUL en entidad_tipo, motivo y dos datos: cuatro defectos, en el orden de los campos."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(
        entidad_tipo="a\x00",
        motivo="b\x00",
        datos_antes={"x": "c\x00"},
        datos_despues={"y": ["d\x00"]},
    )

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo("entidad_tipo", "FORMATO", _mensaje("MENSAJE_NUL")),
        DefectoDeCampo("motivo", "FORMATO", _mensaje("MENSAJE_NUL")),
        DefectoDeCampo("datos_antes.x", "FORMATO", _mensaje("MENSAJE_NUL")),
        DefectoDeCampo("datos_despues.y[0]", "FORMATO", _mensaje("MENSAJE_NUL")),
    )


def test_tkt007_ca05_texto_sin_nul_pasa_aunque_lleve_otros_controles() -> None:
    """TC-58 (complemento) · CA-5 (F001) — saltos de línea, tabuladores y acentos no son NUL: el asiento se forma intacto."""
    resultado = _revisar(
        entidad_tipo="requisición",
        motivo="Línea 1\nLínea 2\tcon tabulador",
        datos_despues={"nota": "ñandú\r\n", "clave\tcon-tab": ["ok", {"k": "v\x01"}]},
    )

    assert resultado.defectos == ()
    assert resultado.asiento is not None
    assert resultado.asiento.entidad_tipo == "requisición"
    assert resultado.asiento.motivo == "Línea 1\nLínea 2\tcon tabulador"
    assert resultado.asiento.datos_despues == {
        "nota": "ñandú\r\n",
        "clave\tcon-tab": ["ok", {"k": "v\x01"}],
    }


def test_tkt007_ca05_campos_opcionales_ausentes_pasan() -> None:
    """TC-28 (complemento) · CA-5 esc. 1 — motivo, obra, regla y datos son opcionales: ausentes, el asiento se forma."""
    resultado = _revisar(
        regla_negocio=None, obra_id=None, motivo=None, datos_antes=None, datos_despues=None
    )

    assert resultado.defectos == ()
    assert resultado.asiento is not None
    assert resultado.asiento.regla_negocio is None
    assert resultado.asiento.obra_id is None
    assert resultado.asiento.motivo is None
    assert resultado.asiento.datos_antes is None
    assert resultado.asiento.datos_despues is None


def test_tkt007_ca05_los_defectos_se_acumulan_en_orden() -> None:
    """TC-29 · CA-5 — verbo, regla y un float mal a la vez: tres defectos, en el orden de los campos."""
    from cimenta.auditoria.dominio.asiento import DefectoDeCampo

    resultado = _revisar(accion="BORRAR", regla_negocio="rn-03", datos_despues={"importe": 12.5})

    assert resultado.asiento is None
    assert resultado.defectos == (
        DefectoDeCampo("accion", "VALOR_NO_PERMITIDO", _mensaje("MENSAJE_ACCION")),
        DefectoDeCampo("regla_negocio", "FORMATO", _mensaje("MENSAJE_REGLA")),
        DefectoDeCampo("datos_despues.importe", "FORMATO", _mensaje("MENSAJE_VALOR_NO_JSON")),
    )


def test_tkt007_ca05_todos_los_campos_mal_siguen_el_orden_del_diseno() -> None:
    """TC-29 (complemento) · CA-5 — con los nueve campos mal, el orden es el de la firma de revisar_asiento."""
    resultado = _revisar(
        accion="BORRAR",
        entidad_tipo=None,
        entidad_id=None,
        usuario_id=None,
        regla_negocio="rn-03",
        obra_id="x",
        motivo="  ",
        datos_antes={"a": 1.5},
        datos_despues={"b": Decimal("1")},
    )

    assert resultado.asiento is None
    assert [d.campo for d in resultado.defectos] == [
        "accion",
        "entidad_tipo",
        "entidad_id",
        "usuario_id",
        "regla_negocio",
        "obra_id",
        "motivo",
        "datos_antes.a",
        "datos_despues.b",
    ]


def test_tkt007_ca01_enum_del_dominio_igual_al_borrador() -> None:
    """TC-30 · CA-1 esc. 4 — AccionBitacora del dominio tiene los 22 verbos del borrador, en su orden y con name == value."""
    from cimenta.auditoria.dominio.asiento import AccionBitacora

    documento = yaml.safe_load(BORRADOR.read_text(encoding="utf-8"))
    verbos_del_borrador = documento["components"]["schemas"]["AccionBitacora"]["enum"]

    assert len(verbos_del_borrador) == 22
    assert [miembro.value for miembro in AccionBitacora] == verbos_del_borrador
    assert all(miembro.name == miembro.value for miembro in AccionBitacora)


def test_tkt007_ca05_codigos_del_catalogo() -> None:
    """TC-31 · CA-5, TKT-005 — todo código que el dominio emite existe en CodigoValidacion del contrato de error."""
    from contrato_error import CodigoValidacion

    casos: list[dict[str, object]] = [
        {"accion": "BORRAR"},
        {"entidad_tipo": ""},
        {"entidad_tipo": 7},
        {"entidad_id": None},
        {"entidad_id": "x"},
        {"usuario_id": None},
        {"usuario_id": "abc"},
        {"obra_id": "x"},
        {"motivo": "  "},
        {"regla_negocio": "rn-03"},
        {"datos_despues": [1]},
        {"datos_despues": {1: "a"}},
        {"datos_despues": {"importe": 12.5}},
    ]

    emitidos = {d.codigo for caso in casos for d in _revisar(**caso).defectos}

    assert emitidos == {"OBLIGATORIO", "FORMATO", "VALOR_NO_PERMITIDO"}
    assert emitidos <= {c.value for c in CodigoValidacion}


def _raices_prohibidas(archivo: Path) -> list[str]:
    """Módulos que `archivo` importa y no están en la lista blanca del dominio de auditoría."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    importados: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level > 0:
                continue  # importación relativa: el propio paquete
            importados.append(nodo.module or "")
    return [
        modulo
        for modulo in importados
        if modulo not in IMPORTABLES and not modulo.startswith(PAQUETE_PROPIO)
    ]


def test_tkt007_ca08_dominio_de_auditoria_puro() -> None:
    """TC-32 · CA-8, CA-R3 — el dominio de auditoría importa solo la lista blanca y dominio-sin-framework se cumple."""
    archivos = sorted(DOMINIO_DE_AUDITORIA.glob("*.py"))

    # Anti-verde vacío: con la carpeta vacía el recorrido no revisaría nada. El módulo de la fila existe.
    assert "asiento.py" in {archivo.name for archivo in archivos}, (
        f"Falta cimenta/auditoria/dominio/asiento.py: {[a.name for a in archivos]}"
    )
    prohibidos = {archivo.name: _raices_prohibidas(archivo) for archivo in archivos}
    assert {nombre: modulos for nombre, modulos in prohibidos.items() if modulos} == {}, (
        "El dominio de auditoría solo importa __future__, collections.abc, dataclasses, enum, re, "
        "typing y uuid; ni datetime, ni contrato_error, ni tipos_base, ni sqlalchemy"
    )

    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache", "--contract", "dominio-sin-framework"],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    salida = proceso.stdout + proceso.stderr
    resumen = RESUMEN.search(salida)
    assert proceso.returncode == 0, salida
    assert resumen is not None, salida
    assert (int(resumen.group(1)), int(resumen.group(2))) == (1, 0), salida
