"""Ningún asiento de obra cita una regla que el PRD no respalda (TKT-012b, ciclo de corrección, hallazgo F002a).

`actualizar_obra` y las tres transiciones (`SUSPENDER`, `REACTIVAR`, `CERRAR`) asentaban
`regla_negocio="RN-25"`. En el PRD, `RN-25` es el tratamiento del IVA por obra (`docs/01-descripcion-producto.md`):
ni la edición de un nombre ni la máquina de estados lo implementan, y la bitácora no admite `UPDATE` ni
`DELETE`, así que la cita falsa quedaría grabada para siempre. La persona dueña decidió: `regla_negocio=None`
en esos cuatro asientos (`asentar` lo admite: la columna `bitacora.regla_negocio` es nula). La máquina de
estados sigue sin `RN` propia en el PRD (hallazgo F002b, decisión aparte).

Esta prueba es la guarda de esa decisión, por HTTP, con la aplicación real, PostgreSQL migrado con
`alembic upgrade head` y el rol de aplicación:

- cada verbo de obra asienta la regla esperada: `None` en `CREAR`, `ACTUALIZAR`, `SUSPENDER`, `REACTIVAR` y
  `CERRAR`; `RN-01` en `ELIMINAR`;
- después de recorrer todos los verbos, el conjunto de reglas citadas por asientos de obra es un subconjunto
  de `{RN-01}` y `RN-25` no aparece;
- el código de producción de los dos módulos no trae el literal `"RN-25"` (comprobación de AST de las
  constantes, sin docstrings).

Corrección de aserción por decisión de la persona dueña, declarada: las pruebas de A5 y A6 que afirmaban
`RN-25` (`test_tkt012b_mantenimiento_obras.py`, `test_tkt012b_ciclo_vida_obra.py`) pasan a afirmar `None`.

`CREAR` no cita regla hoy (`obras.py` no pasa `regla_negocio`; el encargo de la fila decía `RN-01`, pero el
código y `test_tkt012a_alta_obra.py` afirman `None`): la guarda conserva ese comportamiento.

Rojo esperado: los cuatro verbos con `RN-25` asientan `RN-25` en lugar de `None`; el conjunto citado incluye
`RN-25`; el AST encuentra el literal. Nacen en verde, a propósito: `CREAR` y `ELIMINAR`, que conservan su regla.

Mutantes que esta fila pone en rojo: volver a `"RN-25"` en cualquiera de los cuatro verbos; citar `RN-25`
solo en una de las transiciones; cambiar `RN-01` de `ELIMINAR`.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como F811.
# ruff: noqa: F811

from __future__ import annotations

import ast
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from herramientas.soporte_tkt017_api import (
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    cabeceras_de,
)
from herramientas.soporte_tkt017_entorno import Base

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto

BACKEND = Path(__file__).resolve().parents[1]
RUTA = "/api/v1/obras"
MOTIVO = "Decisión de la dirección por falta de anticipo"
# Las reglas del PRD que respaldan algún asiento de obra: solo `RN-01` (no se borra una obra con historial).
REGLAS_RESPALDADAS = {"RN-01"}
REGLA_QUE_NO_RESPALDA = "RN-25"
# Verbo -> regla que el asiento debe citar. `None` es la ausencia de cita.
REGLA_DE_CADA_VERBO: dict[str, str | None] = {
    "CREAR": None,
    "ACTUALIZAR": None,
    "SUSPENDER": None,
    "REACTIVAR": None,
    "CERRAR": None,
    "ELIMINAR": "RN-01",
}
ARCHIVOS_DE_PRODUCCION = (
    BACKEND / "cimenta" / "presupuesto" / "aplicacion" / "mantenimiento_obras.py",
    BACKEND / "cimenta" / "presupuesto" / "aplicacion" / "ciclo_vida_obra.py",
)


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`): la que toma el alta."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra sin línea base ni importaciones, en el estado pedido."""
    creador = datos_presupuesto.usuario()
    contador = iter(range(1, 100))

    def fabricar(*, estado: str) -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=f"AP-{next(contador):03d}-26",
            empresa_id=empresa_de_la_migracion,
            creado_por_id=creador,
            estado=estado,
        )

    return fabricar


def _llamar(
    cliente: TestClient, metodo: str, ruta: str, sesion: Sesion, cuerpo: object | None = None
) -> Any:
    cabeceras = cabeceras_de(sesion.sesion_id, TOKEN_CSRF, TOKEN_CSRF)
    if cuerpo is None:
        return cliente.request(metodo, ruta, headers=cabeceras)
    return cliente.request(metodo, ruta, json=cuerpo, headers=cabeceras)


def _hacer(
    verbo: str,
    cliente: TestClient,
    sesion: Sesion,
    fabricar_obra: Callable[..., uuid.UUID],
) -> uuid.UUID:
    """Ejecuta el verbo por HTTP sobre una obra en el estado de origen y devuelve la obra afectada."""
    if verbo == "CREAR":
        respuesta = _llamar(
            cliente,
            "POST",
            RUTA,
            sesion,
            {
                "codigo": "AP-900-26",
                "nombre": "Obra de la guarda",
                "domicilio": "Calle de prueba 2",
                "tipo_contrato": "PRECIO_ALZADO_MAXIMO_GARANTIZADO",
                "retencion_destajo_pct": "0.15",
                "fondo_garantia_pct": "0.05",
                "iva_acreditable": True,
            },
        )
        assert respuesta.status_code == 201, respuesta.text
        return uuid.UUID(respuesta.json()["id"])
    if verbo == "ACTUALIZAR":
        obra_id = fabricar_obra(estado="ACTIVA")
        respuesta = _llamar(
            cliente, "PATCH", f"{RUTA}/{obra_id}", sesion, {"nombre": "Nombre nuevo"}
        )
    elif verbo == "SUSPENDER":
        obra_id = fabricar_obra(estado="ACTIVA")
        respuesta = _llamar(
            cliente, "POST", f"{RUTA}/{obra_id}/suspension", sesion, {"motivo": MOTIVO}
        )
    elif verbo == "REACTIVAR":
        obra_id = fabricar_obra(estado="SUSPENDIDA")
        respuesta = _llamar(
            cliente, "POST", f"{RUTA}/{obra_id}/reactivacion", sesion, {"motivo": MOTIVO}
        )
    elif verbo == "CERRAR":
        obra_id = fabricar_obra(estado="ACTIVA")
        respuesta = _llamar(cliente, "POST", f"{RUTA}/{obra_id}/cierre", sesion, {"motivo": MOTIVO})
    else:
        assert verbo == "ELIMINAR"
        obra_id = fabricar_obra(estado="PLANEACION")
        respuesta = _llamar(cliente, "DELETE", f"{RUTA}/{obra_id}", sesion)
    assert respuesta.status_code in {200, 204}, respuesta.text
    return obra_id


@pytest.mark.parametrize("verbo", list(REGLA_DE_CADA_VERBO))
def test_tkt012b_f002a_el_asiento_de_cada_verbo_de_obra_cita_la_regla_que_le_corresponde(
    verbo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """F002a · HDU-001 esc. 20 · RN-01 — `CREAR`, `ACTUALIZAR` y las transiciones no citan regla; `ELIMINAR`, `RN-01`.

    Un solo asiento por verbo y por obra, en la misma transacción que el cambio, con `regla_negocio` nula
    donde el PRD no respalda ninguna regla. `RN-25` (IVA por obra) no describe la edición de un nombre ni
    el cambio de estado, y la bitácora no se corrige después.
    """
    sesion = abrir_sesion()

    obra_id = _hacer(verbo, cliente, sesion, fabricar_obra)

    assert base.filas(
        "SELECT regla_negocio FROM bitacora WHERE entidad_id = %s AND accion::text = %s",
        obra_id,
        verbo,
    ) == [(REGLA_DE_CADA_VERBO[verbo],)], (
        f"El asiento {verbo} de obra cita una regla que no corresponde"
    )


def test_tkt012b_f002a_ningun_asiento_de_obra_cita_una_regla_que_el_prd_no_respalda(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """F002a · RN-25 del PRD es el IVA — recorrer todos los verbos deja en la bitácora solo reglas respaldadas.

    Tras crear, editar, suspender, reactivar, cerrar y eliminar, el conjunto de reglas citadas por los
    asientos de `entidad_tipo = 'obra'` está dentro de `{RN-01}` y `RN-25` no figura. Cubre también un
    verbo nuevo que alguien asiente con una cita copiada de otro: la prueba no enumera verbos, mira todos.
    """
    sesion = abrir_sesion()
    for verbo in REGLA_DE_CADA_VERBO:
        _hacer(verbo, cliente, sesion, fabricar_obra)

    citadas = {
        fila[0]
        for fila in base.filas(
            "SELECT regla_negocio FROM bitacora WHERE entidad_tipo = 'obra' "
            "AND regla_negocio IS NOT NULL"
        )
    }

    assert REGLA_QUE_NO_RESPALDA not in citadas
    assert citadas <= REGLAS_RESPALDADAS, (
        f"Citas sin respaldo en el PRD: {citadas - REGLAS_RESPALDADAS}"
    )
    assert base.filas(
        "SELECT count(DISTINCT accion) FROM bitacora WHERE entidad_tipo = 'obra'"
    ) == [(6,)], "La guarda debe haber recorrido los seis verbos de obra"


@pytest.mark.parametrize("ruta", ARCHIVOS_DE_PRODUCCION, ids=lambda ruta: ruta.name)
def test_tkt012b_f002a_el_codigo_de_obra_no_trae_el_literal_rn_25(ruta: Path) -> None:
    """F002a — ninguna constante de `mantenimiento_obras.py` ni de `ciclo_vida_obra.py` vale `"RN-25"`.

    Comprobación de AST de las constantes de texto sin contar los docstrings (la prosa puede nombrar la
    regla de la edición de parámetros). Atrapa un asiento que cita `RN-25` por una constante intermedia,
    como `_REGLA_DE_LAS_TRANSICIONES`, que la guarda por HTTP no distingue de otra.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    docstrings = {
        id(nodo.body[0].value)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and nodo.body
        and isinstance(nodo.body[0], ast.Expr)
        and isinstance(nodo.body[0].value, ast.Constant)
    }
    literales = [
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant)
        and nodo.value == REGLA_QUE_NO_RESPALDA
        and id(nodo) not in docstrings
    ]

    assert literales == [], f"{ruta.name} cita {REGLA_QUE_NO_RESPALDA} en las líneas {literales}"
