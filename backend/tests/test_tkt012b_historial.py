"""Historial de la obra por puerto inyectado (TKT-012b, fila A4): TC-19, TC-20 y la frontera con `compras`.

`presupuesto` no puede importar a los módulos que cuelgan de la obra (`compras`, `almacen`…): el
contrato `grafo-compras` lo prohíbe. Así que el conteo de movimientos entra por un puerto que esos
módulos implementarán algún día y que `servidor/` inyectará en el contexto. Estas pruebas fijan:

- `cimenta/presupuesto/aplicacion/historial_obra.py`: el `Protocol` `FuenteHistorialObra` (`nombre: str`
  y `contar(sesion_bd, obra_id) -> int`) y `contar_historial(sesion_bd, contexto, obra_id) ->
  ConteosHistorial`. Suma el conteo propio del repositorio (`filas_propias` = niveles + conceptos +
  precios de insumo + rendimientos observados) y el de cada fuente inyectada (`movimientos`). Trabaja
  con la sesión que recibe: no abre otra, no confirma y no traga el fallo de una fuente.
- `ContextoPresupuesto.fuentes_historial: tuple[FuenteHistorialObra, ...] = ()`, el último campo y con
  valor por omisión, y el parámetro `fuentes_historial` (por omisión `()`) de `construir_contexto` y de
  `montar_presupuesto`, que lo reenvían tal cual.

PostgreSQL real con testcontainers, esquema por `alembic upgrade head` y conexión con el rol de
aplicación (`sesion_bd`, `motor_aplicacion` y `conectar`). Las fuentes son dobles escritos aquí: son lo
único que se inyecta, y lo que se comprueba es qué recibe cada una y qué se hace con lo que devuelve.

Rojo de la fila A4: el módulo de producción trae esqueletos (`contar_historial` lanza
`NotImplementedError`; `construir_contexto` y `montar_presupuesto` aceptan `fuentes_historial` y lo
ignoran), así que las pruebas de comportamiento fallan por eso. Nacen en verde, a propósito, las que
comprueban solo la forma que el esqueleto ya tiene (campo y parámetros opcionales, construcción
antigua del contexto) y las de frontera, que miran el árbol y no el código nuevo.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import psycopg
import pytest
from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.api.montaje import montar_presupuesto
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from cimenta.presupuesto.aplicacion.historial_obra import (
    FuenteHistorialObra,
    contar_historial,
)
from cimenta.presupuesto.dominio.historial_obra import ConteosHistorial, hay_historial
from cimenta.presupuesto.infraestructura.repositorio_obra import eliminar_obra

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

Conexion = psycopg.Connection[tuple[Any, ...]]

BACKEND = Path(__file__).resolve().parents[1]
PRESUPUESTO = BACKEND / "cimenta" / "presupuesto"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".import_linter_cache")
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")
# Los módulos de negocio que cuelgan de la obra o la leen: `presupuesto` no importa a ninguno.
MODULOS_POSTERIORES = ("compras", "almacen", "avance", "personal", "proveedores", "analitica")


# ------------------------------------------------------------------------------- dobles y ayudas


class FalloDeFuente(Exception):  # noqa: N818 - es un doble de prueba, no una excepción de producción
    """El fallo que lanza una fuente caída: propio de la prueba, para distinguirlo de cualquier otro."""


class FuenteDeConteo:
    """Una fuente que cuenta movimientos por obra y recuerda con qué la llamaron."""

    def __init__(self, nombre: str, movimientos: Mapping[uuid.UUID, int] | int) -> None:
        self.nombre = nombre
        self._movimientos = movimientos
        self.llamadas: list[tuple[Session, uuid.UUID]] = []

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        self.llamadas.append((sesion_bd, obra_id))
        if isinstance(self._movimientos, int):
            return self._movimientos
        return self._movimientos.get(obra_id, 0)


class FuenteCaida:
    """Una fuente cuya consulta falla: la base del módulo posterior no responde."""

    def __init__(self, nombre: str, error: Exception) -> None:
        self.nombre = nombre
        self.error = error
        self.llamadas = 0

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        self.llamadas += 1
        raise self.error


def _sin_motor() -> Engine:
    raise AssertionError("contar_historial debe usar la sesión que recibe, no abrir otra")


def _contexto(
    motor: Engine,
    reloj: RelojDePrueba,
    *fuentes: FuenteHistorialObra,
) -> ContextoPresupuesto:
    return construir_contexto(
        proveedor_motor=lambda: motor, reloj=reloj, fuentes_historial=tuple(fuentes)
    )


def _cuenta(conexion: Conexion, consulta: str, *parametros: object) -> int:
    fila = conexion.execute(consulta, parametros).fetchone()  # type: ignore[call-overload]
    assert fila is not None
    return int(fila[0])


@pytest.fixture
def lector(base_de_prueba: str, conectar: Conectar) -> Conexion:
    """Otra conexión del rol de aplicación, con autocommit: solo ve lo que ya se confirmó."""
    return conectar("aplicacion", base_de_prueba)


@pytest.fixture
def empresa_de_la_migracion(lector: Conexion) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008): la que usan las obras de estas pruebas."""
    filas = lector.execute("SELECT id FROM empresa WHERE activa").fetchall()
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def obra_conocida(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID
) -> uuid.UUID:
    return datos_presupuesto.obra(codigo="AP-058-25", empresa_id=empresa_de_la_migracion)


def _historial_propio_distinto(datos: DatosPresupuesto, obra_id: uuid.UUID) -> None:
    """Dos líneas base (una congelada), tres importaciones y 4 + 5 + 6 + 7 filas propias.

    Seis cifras distintas: un conteo cruzado entre tablas o una suma que olvide una no pasa.
    """
    datos.linea_base(obra_id=obra_id, estado="SUPERSEDIDA", version=1)
    datos.linea_base(obra_id=obra_id, estado="CONGELADA", version=2)
    for _ in range(3):
        datos.importacion(obra_id=obra_id)
    for orden in range(1, 5):
        datos.nivel(obra_id=obra_id, nombre=f"Nivel {orden}", orden=orden)
    for numero in range(5):
        datos.concepto(obra_id=obra_id, codigo=f"C{numero}")
    for _ in range(6):
        datos.precio_insumo(obra_id=obra_id)
    for _ in range(7):
        datos.rendimiento_observado(obra_id=obra_id)


# ---------------------------------------------------------------- TC-19 · contar_historial suma


def test_tkt012b_ca6_contar_historial_suma_las_fuentes_inyectadas_y_la_propia(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-19 · CA-6 · RN-01 · HDU-001 esc. 20 — feliz: `movimientos` suma las fuentes; lo propio, la base.

    Dos fuentes con 2 y 5 movimientos de esta obra (y 100 de otra, que no cuentan): `movimientos` es 7.
    Del lado propio, 2 líneas base (una congelada), 3 importaciones y `filas_propias` = 4 + 5 + 6 + 7 = 22.
    """
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    _historial_propio_distinto(datos_presupuesto, obra_conocida)
    datos_presupuesto.nivel(obra_id=otra)
    compras = FuenteDeConteo("compras", {obra_conocida: 2, otra: 100})
    almacen = FuenteDeConteo("almacen", {obra_conocida: 5, otra: 100})
    contexto = _contexto(motor_aplicacion, reloj_de_prueba, compras, almacen)

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos == ConteosHistorial(
        lineas_base=2,
        linea_base_congelada=True,
        importaciones=3,
        filas_propias=22,
        movimientos=7,
    )


@pytest.mark.parametrize(
    ("por_fuente", "esperado"),
    [((3,), 3), ((3, 4), 7), ((0, 0), 0), ((0, 6), 6), ((1, 1, 1), 3)],
    ids=["una", "dos", "dos_en_cero", "una_en_cero_y_otra_no", "tres"],
)
def test_tkt012b_ca6_contar_historial_movimientos_es_la_suma_exacta_de_lo_que_dice_cada_fuente(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    por_fuente: tuple[int, ...],
    esperado: int,
) -> None:
    """TC-19 · CA-6 — feliz: la suma ni se queda con la mayor, ni con la primera, ni cuenta fuentes.

    El lado propio vale una importación, para comprobar que los movimientos no se mezclan con él.
    """
    datos_presupuesto.importacion(obra_id=obra_conocida)
    fuentes = tuple(FuenteDeConteo(f"fuente-{i}", n) for i, n in enumerate(por_fuente))
    contexto = _contexto(motor_aplicacion, reloj_de_prueba, *fuentes)

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos == ConteosHistorial(
        lineas_base=0,
        linea_base_congelada=False,
        importaciones=1,
        filas_propias=0,
        movimientos=esperado,
    )


def test_tkt012b_ca6_contar_historial_sin_fuentes_movimientos_es_cero_y_lo_propio_se_cuenta(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-19 · CA-6 — feliz: con el contexto por omisión (sin `fuentes_historial`), `movimientos` es 0.

    Es el estado de hoy, cuando ningún módulo posterior publica su fuente. Lo propio sigue contándose.
    """
    _historial_propio_distinto(datos_presupuesto, obra_conocida)
    contexto = construir_contexto(proveedor_motor=lambda: motor_aplicacion)

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos == ConteosHistorial(
        lineas_base=2,
        linea_base_congelada=True,
        importaciones=3,
        filas_propias=22,
        movimientos=0,
    )


def test_tkt012b_ca5_contar_historial_de_una_obra_vacia_sin_fuentes_es_cero_y_no_hay_historial(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-19 · CA-5 · RN-01 — feliz: una obra recién creada, sin fuentes, queda en ceros y se puede borrar."""
    contexto = construir_contexto(proveedor_motor=lambda: motor_aplicacion)

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos == ConteosHistorial(
        lineas_base=0,
        linea_base_congelada=False,
        importaciones=0,
        filas_propias=0,
        movimientos=0,
    )
    assert hay_historial(conteos) is False


def test_tkt012b_ca6_contar_historial_un_movimiento_externo_basta_para_que_haya_historial(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-19 · CA-6 · RN-01 — rechazo: sin nada propio, una sola fuente con un movimiento ya impide borrar.

    Lo que el diseño pide: `hay_historial` no ignora los movimientos de las fuentes inyectadas.
    """
    contexto = _contexto(
        motor_aplicacion,
        reloj_de_prueba,
        FuenteDeConteo("compras", 0),
        FuenteDeConteo("almacen", 1),
    )

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos.movimientos == 1
    assert conteos.filas_propias == 0
    assert conteos.lineas_base == 0
    assert conteos.importaciones == 0
    assert hay_historial(conteos) is True


@pytest.mark.parametrize(
    ("estado", "congelada"),
    [("BORRADOR", False), ("CONGELADA", True), ("SUPERSEDIDA", False)],
)
def test_tkt012b_ca6_contar_historial_lleva_la_bandera_de_linea_base_congelada_del_repositorio(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    estado: str,
    congelada: bool,
) -> None:
    """TC-19 · CA-6 — feliz: solo una línea base `CONGELADA` enciende `linea_base_congelada`.

    Alimenta el detalle del `409 OBRA_CON_HISTORIAL`; las tres cuentan como línea base.
    """
    datos_presupuesto.linea_base(obra_id=obra_conocida, estado=estado)
    contexto = _contexto(motor_aplicacion, reloj_de_prueba, FuenteDeConteo("compras", 0))

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)

    assert conteos.lineas_base == 1
    assert conteos.linea_base_congelada is congelada


def test_tkt012b_ca6_contar_historial_pregunta_a_cada_fuente_una_vez_con_su_sesion_y_su_obra(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-19 · CA-6 — feliz: cada fuente recibe la sesión del llamador y el `obra_id` consultado, una vez.

    La sesión importa: la fuente cuenta dentro de la transacción que ya tiene la obra bloqueada.
    """
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    compras = FuenteDeConteo("compras", 1)
    almacen = FuenteDeConteo("almacen", 1)
    contexto = _contexto(motor_aplicacion, reloj_de_prueba, compras, almacen)

    with sesion_bd.begin():
        contar_historial(sesion_bd, contexto, obra_conocida)
        contar_historial(sesion_bd, contexto, otra)

    for fuente in (compras, almacen):
        assert len(fuente.llamadas) == 2
        assert [obra for _, obra in fuente.llamadas] == [obra_conocida, otra]
        assert all(sesion is sesion_bd for sesion, _ in fuente.llamadas)


def test_tkt012b_ca6_contar_historial_trabaja_con_la_sesion_recibida_y_no_abre_otra(
    sesion_bd: Session,
    reloj_de_prueba: RelojDePrueba,
    datos_presupuesto: DatosPresupuesto,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-19 · CA-6 · regla 8 — feliz: ni pide el motor del contexto, ni confirma, ni escribe.

    El proveedor de motor falla si alguien lo usa: abrir otra sesión leería sin el bloqueo del llamador.
    """
    datos_presupuesto.importacion(obra_id=obra_conocida)
    filas_antes = _cuenta(lector, "SELECT count(*) FROM bitacora")
    contexto = construir_contexto(
        proveedor_motor=_sin_motor,
        reloj=reloj_de_prueba,
        fuentes_historial=(FuenteDeConteo("compras", 1),),
    )

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)
        assert conteos.importaciones == 1
        assert _cuenta(lector, "SELECT count(*) FROM bitacora") == filas_antes

    assert _cuenta(lector, "SELECT count(*) FROM bitacora") == filas_antes
    assert _cuenta(lector, "SELECT count(*) FROM obra WHERE id = %s", obra_conocida) == 1


# ------------------------------------------------------- TC-19 · el campo y los parámetros del contexto


def test_tkt012b_ca6_contexto_presupuesto_sigue_construyendose_con_sus_dos_campos_de_siempre(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> None:
    """TC-19 · CA-R3 — regresión: `ContextoPresupuesto(fabrica_sesiones=…, reloj=…)` (como hace la semilla local).

    Nace en verde: el campo nuevo es opcional y la construcción antigua no se rompe, ni por nombre ni por posición.
    """
    from sqlalchemy.orm import sessionmaker

    def fabrica() -> sessionmaker[Session]:
        return sessionmaker(bind=motor_aplicacion)

    por_nombre = ContextoPresupuesto(fabrica_sesiones=fabrica, reloj=reloj_de_prueba)
    por_posicion = ContextoPresupuesto(fabrica, reloj_de_prueba)

    for contexto in (por_nombre, por_posicion):
        assert contexto.fabrica_sesiones is fabrica
        assert contexto.reloj is reloj_de_prueba


def test_tkt012b_ca6_contexto_presupuesto_sin_fuentes_las_tiene_vacias() -> None:
    """TC-19 · CA-6 — feliz: sin `fuentes_historial` el contexto trae una tupla vacía, no `None`."""
    contexto = ContextoPresupuesto(
        fabrica_sesiones=lambda: pytest.fail("no se usa"), reloj=lambda: pytest.fail("no se usa")
    )

    assert contexto.fuentes_historial == ()
    assert isinstance(contexto.fuentes_historial, tuple)


def test_tkt012b_ca6_fuentes_historial_es_el_ultimo_campo_del_contexto_y_trae_su_valor_por_omision() -> (
    None
):
    """TC-19 · CA-6 — regresión: el campo va al final y con valor por omisión `()`.

    Si no fuera el último con valor por omisión, `ContextoPresupuesto(fabrica, reloj)` se rompería.
    """
    campos = dataclasses.fields(ContextoPresupuesto)

    assert [campo.name for campo in campos] == ["fabrica_sesiones", "reloj", "fuentes_historial"]
    assert campos[-1].default == ()
    assert campos[0].default is dataclasses.MISSING
    assert campos[1].default is dataclasses.MISSING


@pytest.mark.parametrize("funcion", [construir_contexto, montar_presupuesto])
def test_tkt012b_ca6_fuentes_historial_es_un_parametro_opcional_por_nombre_con_valor_vacio(
    funcion: Callable[..., object],
) -> None:
    """TC-19 · CA-6 — regresión: `construir_contexto` y `montar_presupuesto` aceptan `fuentes_historial=()`.

    `servidor/fabrica.py` no pasa nada hoy y debe seguir funcionando; por eso el parámetro es opcional.
    """
    parametros = inspect.signature(funcion).parameters

    assert "fuentes_historial" in parametros
    assert parametros["fuentes_historial"].default == ()
    assert parametros["fuentes_historial"].kind is inspect.Parameter.KEYWORD_ONLY


def test_tkt012b_ca6_construir_contexto_sin_fuentes_deja_el_campo_vacio(
    motor_aplicacion: Engine,
) -> None:
    """TC-19 · CA-6 — feliz: la llamada de siempre, sin `fuentes_historial`, deja `()`."""
    contexto = construir_contexto(proveedor_motor=lambda: motor_aplicacion)

    assert contexto.fuentes_historial == ()


def test_tkt012b_ca6_construir_contexto_guarda_las_fuentes_en_el_orden_recibido(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> None:
    """TC-19 · CA-6 — feliz: el contexto lleva las fuentes inyectadas, las mismas y en ese orden."""
    compras = FuenteDeConteo("compras", 1)
    almacen = FuenteDeConteo("almacen", 1)

    contexto = construir_contexto(
        proveedor_motor=lambda: motor_aplicacion,
        reloj=reloj_de_prueba,
        fuentes_historial=(compras, almacen),
    )

    assert isinstance(contexto.fuentes_historial, tuple)
    assert len(contexto.fuentes_historial) == 2
    assert contexto.fuentes_historial[0] is compras
    assert contexto.fuentes_historial[1] is almacen
    assert contexto.reloj is reloj_de_prueba


def test_tkt012b_ca6_construir_contexto_con_fuentes_sigue_sin_abrir_el_motor() -> None:
    """TC-19 · CA-6 — regresión: inyectar fuentes no rompe la perezosa de la fábrica de sesiones."""
    llamadas: list[str] = []

    def proveedor() -> Engine:
        llamadas.append("motor")
        raise AssertionError("El motor no se pide al construir el contexto")

    contexto = construir_contexto(
        proveedor_motor=proveedor, fuentes_historial=(FuenteDeConteo("compras", 1),)
    )

    assert llamadas == []
    assert len(contexto.fuentes_historial) == 1


def test_tkt012b_ca6_montar_presupuesto_reenvia_las_fuentes_al_contexto_de_la_aplicacion() -> None:
    """TC-19 · CA-6 — feliz: `montar_presupuesto(..., fuentes_historial=…)` las deja en `app.state.presupuesto`.

    Es el único punto por el que `servidor/` inyectará la fuente de un módulo posterior.
    """
    compras = FuenteDeConteo("compras", 1)
    almacen = FuenteDeConteo("almacen", 1)
    aplicacion = FastAPI()

    montar_presupuesto(
        aplicacion,
        proveedor_motor=_sin_motor,
        reloj=None,
        fuentes_historial=(compras, almacen),
    )

    contexto = aplicacion.state.presupuesto
    assert isinstance(contexto, ContextoPresupuesto)
    assert len(contexto.fuentes_historial) == 2
    assert contexto.fuentes_historial[0] is compras
    assert contexto.fuentes_historial[1] is almacen


def test_tkt012b_ca6_montar_presupuesto_sin_fuentes_monta_un_contexto_con_el_campo_vacio() -> None:
    """TC-19 · CA-6 — feliz: la llamada de `servidor/fabrica.py` de hoy (sin fuentes) sigue valiendo."""
    aplicacion = FastAPI()

    montar_presupuesto(aplicacion, proveedor_motor=_sin_motor, reloj=None)

    assert aplicacion.state.presupuesto.fuentes_historial == ()


# ------------------------------------------------------ TC-20 · una fuente que falla no deja pasar


@pytest.mark.parametrize(
    "orden",
    ["cae_la_primera", "cae_la_de_en_medio", "cae_la_ultima", "cae_la_unica_con_las_demas_en_cero"],
)
def test_tkt012b_ca6_contar_historial_propaga_el_fallo_de_una_fuente_tal_cual(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    obra_conocida: uuid.UUID,
    orden: str,
) -> None:
    """TC-20 · CA-6 · RN-01 — rechazo: si una fuente lanza, `contar_historial` lanza lo mismo.

    En cualquier posición, y aunque las demás fuentes digan 0 y la obra no tenga nada propio: una fuente
    que no responde nunca se lee como «cero movimientos». Se propaga la misma excepción, sin envolver y
    sin devolver un `ConteosHistorial`.
    """
    error = FalloDeFuente("la base de compras no responde")
    caida = FuenteCaida("compras", error)
    bien = [FuenteDeConteo("almacen", 0), FuenteDeConteo("avance", 0)]
    fuentes: dict[str, tuple[FuenteHistorialObra, ...]] = {
        "cae_la_primera": (caida, bien[0], bien[1]),
        "cae_la_de_en_medio": (bien[0], caida, bien[1]),
        "cae_la_ultima": (bien[0], bien[1], caida),
        "cae_la_unica_con_las_demas_en_cero": (caida,),
    }
    contexto = _contexto(motor_aplicacion, reloj_de_prueba, *fuentes[orden])

    with pytest.raises(FalloDeFuente) as info, sesion_bd.begin():
        contar_historial(sesion_bd, contexto, obra_conocida)

    assert info.value is error
    assert info.value.__cause__ is None
    assert caida.llamadas == 1


def test_tkt012b_ca6_el_fallo_de_una_fuente_no_se_compensa_con_lo_que_dicen_las_otras(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    obra_conocida: uuid.UUID,
) -> None:
    """TC-20 · CA-6 — rechazo: ni una fuente con muchos movimientos ni una con historial propio lo ocultan.

    Otra fuente (que se consulta antes) dice 9 movimientos: el fallo igual manda, y no se devuelve un
    conteo parcial que la persona leería como completo.
    """
    contexto = _contexto(
        motor_aplicacion,
        reloj_de_prueba,
        FuenteDeConteo("almacen", 9),
        FuenteCaida("compras", FalloDeFuente("sin respuesta")),
    )

    with pytest.raises(FalloDeFuente), sesion_bd.begin():
        contar_historial(sesion_bd, contexto, obra_conocida)


def test_tkt012b_ca6_si_la_fuente_falla_el_llamador_no_llega_a_borrar_la_obra(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-20 · CA-6 · RN-01 — rechazo: con el patrón del caso de uso (contar, decidir, borrar), no se borra.

    La obra no tiene nada propio, así que sin fuentes sí se borraría. Con una fuente caída el error
    sale de `contar_historial` antes del `eliminar_obra`: la obra y su código siguen intactos y no
    se asienta nada. (El caso de uso real y su `409` se prueban en A5.)
    """
    contexto = _contexto(
        motor_aplicacion, reloj_de_prueba, FuenteCaida("compras", FalloDeFuente("sin respuesta"))
    )
    asientos_antes = _cuenta(lector, "SELECT count(*) FROM bitacora")
    borrado = False

    def intentar_borrar() -> None:
        nonlocal borrado
        with sesion_bd.begin():
            conteos = contar_historial(sesion_bd, contexto, obra_conocida)
            if not hay_historial(conteos):
                eliminar_obra(sesion_bd, obra_conocida)
                borrado = True

    with pytest.raises(FalloDeFuente):
        intentar_borrar()

    assert borrado is False
    assert _cuenta(lector, "SELECT count(*) FROM obra WHERE id = %s", obra_conocida) == 1
    assert _cuenta(lector, "SELECT count(*) FROM bitacora") == asientos_antes


def test_tkt012b_ca5_con_fuentes_sanas_y_sin_historial_el_mismo_patron_si_borra(
    sesion_bd: Session,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    obra_conocida: uuid.UUID,
    lector: Conexion,
) -> None:
    """TC-20 · CA-5 — contraste: la misma secuencia con fuentes que responden 0 sí borra la obra.

    Sin este caso, «no borra» podría deberse a cualquier otra cosa y no al fallo de la fuente.
    """
    contexto = _contexto(
        motor_aplicacion,
        reloj_de_prueba,
        FuenteDeConteo("compras", 0),
        FuenteDeConteo("almacen", 0),
    )

    with sesion_bd.begin():
        conteos = contar_historial(sesion_bd, contexto, obra_conocida)
        assert not hay_historial(conteos)
        eliminar_obra(sesion_bd, obra_conocida)

    assert _cuenta(lector, "SELECT count(*) FROM obra WHERE id = %s", obra_conocida) == 0


# ------------------------------------------------------------- frontera: `compras` no entra en presupuesto


class Corrida(NamedTuple):
    codigo: int
    salida: str


def _correr_linter(cwd: Path, *contratos: str) -> Corrida:
    argumentos = [argumento for c in contratos for argumento in ("--contract", c)]
    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache", *argumentos],
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    return Corrida(proceso.returncode, proceso.stdout + proceso.stderr)


def _contratos(corrida: Corrida) -> tuple[int, int]:
    resumen = RESUMEN.search(corrida.salida)
    assert resumen, corrida.salida
    return int(resumen.group(1)), int(resumen.group(2))


def _modulos_importados(archivo: Path) -> set[str]:
    """Nombre completo de cada módulo que el archivo importa, con los relativos ya resueltos."""
    paquete = list(archivo.relative_to(BACKEND).with_suffix("").parts[:-1])
    modulos: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))):
        if isinstance(nodo, ast.Import):
            modulos.update(nombre.name for nombre in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete[: len(paquete) - (nodo.level - 1)]
                modulo = ".".join([*base, *(nodo.module.split(".") if nodo.module else [])])
            else:
                modulo = nodo.module or ""
            modulos.add(modulo)
            modulos.update(f"{modulo}.{nombre.name}" for nombre in nodo.names)
    return modulos


def _importa_a(modulos: set[str], posteriores: tuple[str, ...]) -> list[str]:
    return sorted(
        modulo
        for modulo in modulos
        if any(
            modulo == f"cimenta.{posterior}" or modulo.startswith(f"cimenta.{posterior}.")
            for posterior in posteriores
        )
    )


def test_tkt012b_ca6_el_puerto_y_el_contexto_no_importan_ningun_modulo_posterior() -> None:
    """A4 · frontera (AST) — el puerto vive en `presupuesto` y no depende de quien lo implementará.

    Nace en verde con el esqueleto: es una regresión. Sin esto, la salida fácil sería importar la interfaz
    de `compras` desde `historial_obra.py`, que es justo lo que el puerto existe para evitar.
    """
    archivos = {
        "historial_obra": PRESUPUESTO / "aplicacion" / "historial_obra.py",
        "contexto": PRESUPUESTO / "aplicacion" / "contexto.py",
        "montaje": PRESUPUESTO / "api" / "montaje.py",
    }
    for nombre, archivo in archivos.items():
        assert archivo.is_file(), f"Falta {nombre}: {archivo}"  # anti-verde vacío
        assert _importa_a(_modulos_importados(archivo), MODULOS_POSTERIORES) == [], nombre


def test_tkt012b_ca6_ningun_archivo_de_presupuesto_importa_un_modulo_posterior() -> None:
    """A4 · frontera (AST) — ni el puerto ni nada de `presupuesto` conoce a `compras`, `almacen`…

    Nace en verde: es la arista que el grafo de `docs/02-arquitectura.md` §5 no tiene.
    """
    archivos = sorted(PRESUPUESTO.rglob("*.py"))
    assert len(archivos) > 20, f"El recorrido no examinó el módulo: {len(archivos)} archivos"
    nombres = {archivo.name for archivo in archivos}
    assert {"contexto.py", "historial_obra.py", "montaje.py", "obras.py"} <= nombres

    infractores = {
        str(archivo.relative_to(BACKEND)): importados
        for archivo in archivos
        if (importados := _importa_a(_modulos_importados(archivo), MODULOS_POSTERIORES))
    }

    assert infractores == {}


def test_tkt012b_ca6_lint_imports_no_ve_compras_en_presupuesto_en_el_arbol_real() -> None:
    """A4 · frontera — `grafo-compras` y `solo-por-interfaz` se cumplen con el árbol real.

    Nace en verde: es lo que la fila A4 verifica con `lint-imports` («no aparece `compras` en `presupuesto`»).
    """
    corrida = _correr_linter(BACKEND, "grafo-compras", "solo-por-interfaz")

    assert corrida.codigo == 0, corrida.salida
    assert _contratos(corrida) == (2, 0), corrida.salida


def test_tkt012b_ca6_grafo_compras_rechaza_que_presupuesto_importe_compras(tmp_path: Path) -> None:
    """A4 · frontera — el contrato muerde: un archivo de `presupuesto` que importa `compras` lo rompe.

    Se escribe en una copia del árbol bajo `tmp_path`, nunca en el árbol que se revisa. Es lo que
    demuestra que el verde de la prueba anterior significa algo.
    """
    copia = tmp_path / "copia"
    copia.mkdir()
    shutil.copy(BACKEND / "pyproject.toml", copia / "pyproject.toml")
    for paquete in ("cimenta", "tipos_base", "herramientas", "trabajos"):
        origen = BACKEND / paquete
        if origen.is_dir():
            shutil.copytree(origen, copia / paquete, ignore=IGNORAR)
    infractor = copia / "cimenta" / "presupuesto" / "aplicacion" / "x_tkt012b.py"
    infractor.write_text(
        '"""Violación a propósito: presupuesto no puede importar compras."""\n\n'
        "import cimenta.compras.interfaz  # noqa: F401\n",
        encoding="utf-8",
        newline="\n",
    )

    corrida = _correr_linter(copia, "grafo-compras")

    assert corrida.codigo == 1, corrida.salida
    assert _contratos(corrida) == (0, 1), corrida.salida
    assert "cimenta.presupuesto.aplicacion.x_tkt012b" in corrida.salida, corrida.salida
