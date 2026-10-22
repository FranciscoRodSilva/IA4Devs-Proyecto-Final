"""Reglas puras de identidad (TKT-006, fila 2): TC-01 a TC-12.

Sin Docker. Prueba `cimenta/identidad/dominio/`: `correo.py`, `vigencia.py`, `acceso.py` y
`autorizacion.py`. El dominio decide con valores ya materializados: la vigencia compara instantes
genéricos (enteros o `datetime` con zona) con el protocolo `Ordenable`, sin importar `datetime`
(ADR-021); la hora la pone `aplicacion/` con un reloj inyectable.

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: mientras
los archivos no existan, cada caso falla por sí solo con el `ModuleNotFoundError` de
`cimenta.identidad.dominio.<archivo>` (la razón esperada) y la recolección no se cae.

Ninguna de estas reglas tiene `RN-xx` en el PRD: se trazan con `CA-n`, `M-n`, `PA-Tn` y `RNF-01`.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from contrato_error import Rol

if TYPE_CHECKING:
    from cimenta.identidad.dominio.vigencia import EstadoSesion, Ordenable

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
DOMINIO_DE_IDENTIDAD = BACKEND / "cimenta" / "identidad" / "dominio"
ARCHIVOS_DEL_DOMINIO = {"correo.py", "vigencia.py", "acceso.py", "autorizacion.py"}
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")
# Lista blanca del dominio de identidad (design, «Dominio»): nada más se importa.
IMPORTABLES = {"__future__", "dataclasses", "enum", "typing", "uuid"}
PAQUETE_PROPIO = "cimenta.identidad.dominio"

SOLICITANTE = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTRA_PERSONA = uuid.UUID("22222222-2222-4222-8222-222222222222")

INICIO = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
DOCE_HORAS = timedelta(hours=12)
TREINTA_MINUTOS = timedelta(minutes=30)
UN_SEGUNDO = timedelta(seconds=1)


def _evaluar[T: Ordenable](
    *,
    ahora: T,
    expira_en: T,
    vence_por_inactividad_en: T,
    revocada: bool = False,
    usuario_activo: bool = True,
) -> EstadoSesion:
    """Llama a `evaluar_vigencia` con una sesión sin marcas: cada caso cambia solo lo que prueba."""
    from cimenta.identidad.dominio.vigencia import evaluar_vigencia

    return evaluar_vigencia(
        ahora=ahora,
        expira_en=expira_en,
        vence_por_inactividad_en=vence_por_inactividad_en,
        revocada=revocada,
        usuario_activo=usuario_activo,
    )


def test_tkt006_ca02_correo_se_normaliza_a_minusculas() -> None:
    """TC-01 · CA-2 esc. 2 · PA-T10 — el correo se compara en minúsculas y normalizar es idempotente."""
    from cimenta.identidad.dominio.correo import normalizar_correo

    normalizado = normalizar_correo("Ana@Cimenta.TEST")

    assert normalizado == "ana@cimenta.test"
    assert normalizar_correo(normalizado) == normalizado
    assert normalizar_correo("ANA@CIMENTA.TEST") == normalizado


def test_tkt006_ca06_sesion_vigente_antes_de_ambos_limites() -> None:
    """TC-02 · CA-6 esc. 1 · RNF-01 — con holgura en la caducidad absoluta y en la inactividad, la sesión sigue vigente."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    estado = _evaluar(ahora=100, expira_en=200, vence_por_inactividad_en=150)

    assert estado is EstadoSesion.VIGENTE
    assert estado == "VIGENTE"


@pytest.mark.parametrize(
    ("ahora", "esperado"),
    [
        pytest.param(199, "VIGENTE", id="un-instante-antes"),
        pytest.param(200, "CADUCADA", id="en-el-limite"),
        pytest.param(201, "CADUCADA", id="despues-del-limite"),
    ],
)
def test_tkt006_ca08_caduca_al_llegar_expira_en(ahora: int, esperado: str) -> None:
    """TC-03 · CA-8 esc. 1 y 3 · RNF-01 — en el instante exacto de `expira_en` la sesión ya caducó."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    # La inactividad queda lejos: solo la caducidad absoluta decide.
    estado = _evaluar(ahora=ahora, expira_en=200, vence_por_inactividad_en=1000)

    assert estado is EstadoSesion(esperado)


@pytest.mark.parametrize(
    ("ahora", "esperado"),
    [
        pytest.param(149, "VIGENTE", id="un-instante-antes"),
        pytest.param(150, "CADUCADA", id="en-el-limite"),
        pytest.param(151, "CADUCADA", id="despues-del-limite"),
    ],
)
def test_tkt006_ca08_caduca_por_inactividad(ahora: int, esperado: str) -> None:
    """TC-04 · CA-8 esc. 2 · RNF-01 — en el instante exacto de `vence_por_inactividad_en` la sesión ya caducó."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    # La caducidad absoluta queda lejos: solo la inactividad decide.
    estado = _evaluar(ahora=ahora, expira_en=1000, vence_por_inactividad_en=150)

    assert estado is EstadoSesion(esperado)


@pytest.mark.parametrize(
    ("ahora", "expira_en", "vence_por_inactividad_en"),
    [
        pytest.param(100, 200, 150, id="todo-vigente"),
        pytest.param(250, 200, 150, id="caducada-por-ambos-limites"),
        pytest.param(150, 200, 150, id="inactividad-en-el-limite"),
        pytest.param(200, 200, 1000, id="expira-en-el-limite"),
    ],
)
def test_tkt006_ca09_revocada_prevalece(
    ahora: int, expira_en: int, vence_por_inactividad_en: int
) -> None:
    """TC-05 · CA-9 esc. 2 — una sesión revocada es REVOCADA aunque esté vigente o ya haya caducado."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    estado = _evaluar(
        ahora=ahora,
        expira_en=expira_en,
        vence_por_inactividad_en=vence_por_inactividad_en,
        revocada=True,
    )

    assert estado is EstadoSesion.REVOCADA


@pytest.mark.parametrize(
    ("ahora", "revocada"),
    [
        pytest.param(100, False, id="vigente"),
        pytest.param(250, False, id="ya-caducada"),
        pytest.param(100, True, id="tambien-revocada"),
    ],
)
def test_tkt006_ca10_usuario_desactivado_es_revocada(ahora: int, revocada: bool) -> None:
    """TC-06 · CA-10 · PA-T3 — con el usuario desactivado la sesión es REVOCADA, no CADUCADA, tenga la vigencia que tenga."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    estado = _evaluar(
        ahora=ahora,
        expira_en=200,
        vence_por_inactividad_en=150,
        revocada=revocada,
        usuario_activo=False,
    )

    assert estado is EstadoSesion.REVOCADA


def test_tkt006_ca08_vigencia_con_instantes_con_zona() -> None:
    """TC-07 · CA-8 — la vigencia se decide igual con `datetime` con zona: el dominio no importa `datetime`, el test sí."""
    from cimenta.identidad.dominio.vigencia import EstadoSesion

    expira_en = INICIO + DOCE_HORAS
    lejos = INICIO + 2 * DOCE_HORAS
    vence_por_inactividad_en = INICIO + TREINTA_MINUTOS

    # Caducidad absoluta (TC-03): la inactividad queda lejos.
    antes = _evaluar(
        ahora=expira_en - UN_SEGUNDO, expira_en=expira_en, vence_por_inactividad_en=lejos
    )
    en_el_limite = _evaluar(ahora=expira_en, expira_en=expira_en, vence_por_inactividad_en=lejos)
    # Inactividad (TC-04): la caducidad absoluta queda lejos.
    inactiva_antes = _evaluar(
        ahora=vence_por_inactividad_en - UN_SEGUNDO,
        expira_en=expira_en,
        vence_por_inactividad_en=vence_por_inactividad_en,
    )
    inactiva_en_el_limite = _evaluar(
        ahora=vence_por_inactividad_en,
        expira_en=expira_en,
        vence_por_inactividad_en=vence_por_inactividad_en,
    )
    # El mismo instante escrito en otra zona es el mismo instante: el borde no se mueve.
    centro_de_mexico = timezone(timedelta(hours=-6))
    mismo_instante_en_otra_zona = _evaluar(
        ahora=expira_en.astimezone(centro_de_mexico),
        expira_en=expira_en,
        vence_por_inactividad_en=lejos,
    )

    assert antes is EstadoSesion.VIGENTE
    assert en_el_limite is EstadoSesion.CADUCADA
    assert inactiva_antes is EstadoSesion.VIGENTE
    assert inactiva_en_el_limite is EstadoSesion.CADUCADA
    assert mismo_instante_en_otra_zona is EstadoSesion.CADUCADA


COMBINACIONES_DE_CREDENCIALES = [
    pytest.param(
        *combinacion,
        id="-".join(
            nombre if valor else f"no-{nombre}"
            for nombre, valor in zip(("existe", "activo", "coincide"), combinacion, strict=True)
        ),
    )
    for combinacion in itertools.product([True, False], repeat=3)
]


@pytest.mark.parametrize(("existe", "activo", "coincide"), COMBINACIONES_DE_CREDENCIALES)
def test_tkt006_ca04_credenciales_aceptadas(existe: bool, activo: bool, coincide: bool) -> None:
    """TC-08 · CA-3, CA-4 · PA-T4 — solo (existe, activo, coincide) todos verdaderos acepta; el resto se rechaza igual."""
    from cimenta.identidad.dominio.acceso import credenciales_aceptadas

    aceptadas = credenciales_aceptadas(existe=existe, activo=activo, coincide=coincide)

    # Un desactivado con su contraseña correcta, un correo inexistente y una contraseña errónea
    # son el mismo rechazo: ninguna combinación con un `False` acepta.
    assert aceptadas is ((existe, activo, coincide) == (True, True, True))


def test_tkt006_ca13_quien_solicito_no_resuelve() -> None:
    """TC-09 · CA-13 esc. 1 — quien solicitó no resuelve lo que solicitó; es una negación sin RN-xx y no lanza."""
    from cimenta.identidad.dominio.autorizacion import MotivoNegacion, evaluar_resolucion

    # Otro objeto con el mismo valor: la comparación es por valor, no por identidad de objeto.
    mismo_valor = uuid.UUID(str(SOLICITANTE))

    resultado = evaluar_resolucion(solicitante_id=SOLICITANTE, resolutor_id=mismo_valor)

    assert resultado.permitida is False
    assert resultado.motivo is MotivoNegacion.AUTO_RESOLUCION
    assert MotivoNegacion.AUTO_RESOLUCION == "AUTO_RESOLUCION"
    assert not hasattr(resultado, "regla")
    assert "RN-" not in repr(resultado)


def test_tkt006_ca13_resolucion_no_recibe_roles_y_su_resultado_es_inmutable() -> None:
    """TC-09 (complemento) · CA-13 — la función no recibe roles (nadie se auto-resuelve, tenga el rol que tenga) y devuelve un valor congelado."""
    from cimenta.identidad.dominio.autorizacion import ResultadoResolucion, evaluar_resolucion

    parametros = inspect.signature(evaluar_resolucion).parameters
    resultado = evaluar_resolucion(solicitante_id=SOLICITANTE, resolutor_id=SOLICITANTE)

    assert list(parametros) == ["solicitante_id", "resolutor_id"]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in parametros.values())
    assert isinstance(resultado, ResultadoResolucion)
    assert [campo.name for campo in dataclasses.fields(resultado)] == ["permitida", "motivo"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        resultado.permitida = True  # type: ignore[misc]


def test_tkt006_ca13_otra_persona_puede_resolver() -> None:
    """TC-10 · CA-13 esc. 2 y 3 — otra persona sí puede resolver: permitida, sin motivo de negación."""
    from cimenta.identidad.dominio.autorizacion import evaluar_resolucion

    # La falta de rol (esc. 3) no la decide el dominio: la función no recibe roles. La decide
    # `api/` con `rol_suficiente` y la responde como ROL_INSUFICIENTE (ver TC-62).
    resultado = evaluar_resolucion(solicitante_id=SOLICITANTE, resolutor_id=OTRA_PERSONA)

    assert resultado.permitida is True
    assert resultado.motivo is None


@pytest.mark.parametrize(
    ("de_quien_llama", "requeridos", "esperado"),
    [
        pytest.param({Rol.COMPRAS, Rol.ALMACEN}, {Rol.COMPRAS}, True, id="basta-el-primero"),
        pytest.param({Rol.COMPRAS, Rol.ALMACEN}, {Rol.ALMACEN}, True, id="basta-el-segundo"),
        pytest.param(
            {Rol.COMPRAS}, {Rol.COMPRAS, Rol.ALMACEN}, True, id="basta-uno-de-los-requeridos"
        ),
        pytest.param(
            {Rol.COMPRAS, Rol.ALMACEN}, {Rol.COMPRAS, Rol.ALMACEN}, True, id="los-dos-coinciden"
        ),
        pytest.param({Rol.RESIDENTE}, {Rol.DIRECCION_GENERAL}, False, id="rol-ajeno"),
        pytest.param(
            {Rol.RESIDENTE, Rol.ALMACEN}, {Rol.COMPRAS, Rol.ADMINISTRACION}, False, id="dos-ajenos"
        ),
        pytest.param(set(), {Rol.COMPRAS}, False, id="sin-ningun-rol"),
        pytest.param({Rol.COMPRAS}, set(), False, id="ruta-sin-roles-requeridos"),
    ],
)
def test_tkt006_ca06_permiso_es_la_union(
    de_quien_llama: set[Rol], requeridos: set[Rol], esperado: bool
) -> None:
    """TC-11 · CA-6 esc. 2, CA-11, CA-12 — el permiso efectivo es la unión de los roles: basta uno de los requeridos."""
    from cimenta.identidad.dominio.autorizacion import rol_suficiente

    # Los roles viajan como cadenas, igual que salen de `usuario_rol` y de `x-roles`.
    suficiente = rol_suficiente(
        frozenset(str(rol) for rol in de_quien_llama), frozenset(str(rol) for rol in requeridos)
    )

    assert suficiente is esperado


def _raices_prohibidas(archivo: Path) -> list[str]:
    """Módulos que `archivo` importa y no están en la lista blanca del dominio de identidad."""
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


def test_tkt006_ca13_dominio_de_identidad_puro() -> None:
    """TC-12 · CA-13 esc. 4, CA-R3 — el dominio de identidad importa solo la lista blanca y `autorizacion.py` nunca lanza."""
    archivos = sorted(DOMINIO_DE_IDENTIDAD.glob("*.py"))

    # Anti-verde vacío: con la carpeta vacía el recorrido no revisaría nada. Los cuatro módulos existen.
    assert {archivo.name for archivo in archivos} >= ARCHIVOS_DEL_DOMINIO, (
        f"Faltan archivos en cimenta/identidad/dominio/: {[a.name for a in archivos]}"
    )
    prohibidos = {archivo.name: _raices_prohibidas(archivo) for archivo in archivos}
    assert {nombre: modulos for nombre, modulos in prohibidos.items() if modulos} == {}, (
        "El dominio de identidad solo importa __future__, dataclasses, enum, typing y uuid; "
        "ni datetime, ni pwdlib, ni contrato_error"
    )

    autorizacion = DOMINIO_DE_IDENTIDAD / "autorizacion.py"
    arbol = ast.parse(autorizacion.read_text(encoding="utf-8"), filename=str(autorizacion))
    lanzamientos = [nodo.lineno for nodo in ast.walk(arbol) if isinstance(nodo, ast.Raise)]
    # `evaluar_resolucion` devuelve un resultado; quien lanza es el caso de uso (conv-dominio-python §4).
    assert lanzamientos == [], f"autorizacion.py lanza en las líneas {lanzamientos}"


def test_tkt006_ca13_contrato_dominio_sin_framework_se_cumple() -> None:
    """TC-12 (parte de lint-imports) · CA-13 esc. 4, CA-R3 — `lint-imports` cumple `dominio-sin-framework` con el dominio de identidad."""
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
