"""Materialización de la importación, filas A6a y A6b de TKT-017a3 (TC-A10 a TC-A21).

Cubre `CA-A1` a `CA-A9` (`HDU-001` esc. 11 a 13, `RN-01`, `PA-T8`, `PA-T13`) contra PostgreSQL
migrado con `alembic upgrade head` y el rol de aplicación, por la interfaz publicada
`cimenta.presupuesto.interfaz.materializar_importacion`. Cada rechazo comprueba el contrato de error
completo con `error.cuerpo(roles, correlacion)` y, con `foto_de_base`, que no cambió ninguna fila, ninguna
marca de insumo, ningún estado ni ningún asiento de la bitácora.

Son pruebas de caja negra del caso de uso: no dependen de cómo se reparten las decisiones entre
`dominio/` y `aplicacion/`, que cubren `test_tkt017_confirmacion.py` y `test_tkt017_plan.py`.

Los importes esperados son literales de `CA-A1` (`5250.0000`, `3079.9860`, `8329.9860`): ninguno se
recalcula con la fórmula del código bajo prueba.

La concurrencia (`TC-A22` y `TC-A23`, `CA-A10`) vive en `test_tkt017_materializacion_concurrencia.py`.
"""

from __future__ import annotations

import functools
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import psycopg
import pytest
from sqlalchemy import event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto import interfaz
from cimenta.presupuesto.aplicacion import contexto as modulo_contexto
from cimenta.presupuesto.aplicacion import materializacion as modulo_materializacion
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from cimenta.presupuesto.dominio.analisis import TipoCargo
from cimenta.presupuesto.dominio.materializacion import (
    PlanMaterializacion,
    PreparacionInconsistente,
    planificar_materializacion,
)
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from cimenta.presupuesto.infraestructura import repositorio_linea_base, tablas
from cimenta.presupuesto.infraestructura.preparacion_json import preparacion_a_json
from cimenta.presupuesto.infraestructura.repositorio_linea_base import FilaLineaBase
from cimenta.presupuesto.interfaz import LineaBaseMaterializada, materializar_importacion
from contrato_error.excepciones import ErrorContrato
from herramientas.soporte_tkt017 import (
    asignacion_tipos_hdu001_esc11,
    foto_de_base,
    insumos_registrados_sinteticos,
    preparacion_con_concepto,
    preparacion_con_insumo,
    preparacion_con_partidas,
    preparacion_con_ruta,
    preparacion_con_totales,
    preparacion_dos_conceptos_con_alta_compartida,
    preparacion_sintetica,
    preparacion_sintetica_cantidad_plafon,
    preparacion_sintetica_cargos_utilidad_indirectos_altos,
    preparacion_sintetica_sin_cargo_utilidad,
    preparacion_solo_muros,
    tipos_partida_hdu001_esc11,
)
from tipos_base import Cantidad, Dinero, Rendimiento

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

Contexto = Callable[[], ContextoPresupuesto]

CORRELACION = "corr-tkt017-a6a"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
CODIGO_OBRA = "AP-058-25"
NOMBRE_COMPLETO_OBRA = "AP-058-25 · Obra AP-058-25"
CODIGO_CONCEPTO = "620040-A"

MENSAJE_NO_EXISTE = "La importación no existe."
MENSAJE_CON_ERRORES = "La importación tiene errores bloqueantes y no se confirma."
MENSAJE_ESTADO = (
    "La importación está en {estado} y no se confirma. Solo se confirma una importación VALIDADO."
)
MENSAJE_CONGELADA = (
    "La obra {codigo} ya tiene una línea base congelada; no admite otra importación."
)
MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_REEMPLAZO = (
    "La obra ya tiene una línea base en borrador; confirmar esta importación la reemplaza."
)
MENSAJE_ILEGIBLE = (
    "La preparación de la importación no se puede leer; la importación debe analizarse de nuevo."
)
MENSAJE_INSUMO_EN_CONFLICTO = (
    "El insumo {codigo} ya existe con otra unidad o tipo; la importación debe analizarse de nuevo."
)
MENSAJE_EXPLOSION = "La explosión de insumos de la importación no se puede calcular."
MENSAJE_FALTA_TIPO = "Falta el tipo de partida de esta partida."
MENSAJE_TIPO_INEXISTENTE = "El tipo de partida no existe."
MENSAJE_CLAVES_AMBIGUAS = "Hay dos claves con distinto tipo para esta partida; deja una sola."
MENSAJE_CAMPO_OBLIGATORIO = "El campo es obligatorio."


# --------------------------------------------------------------------------- el caso de uso


def _materializar(
    contexto: ContextoPresupuesto,
    importacion_id: uuid.UUID,
    *,
    asignacion: Mapping[str, uuid.UUID],
    usuario_id: uuid.UUID,
    reemplazar_borrador: bool = False,
    motivo_reemplazo: str | None = None,
) -> LineaBaseMaterializada:
    """La firma exacta de «Aplicación» en el diseño, por la interfaz publicada."""
    return materializar_importacion(
        contexto,
        importacion_id=importacion_id,
        asignacion_tipos_partida=asignacion,
        reemplazar_borrador=reemplazar_borrador,
        motivo_reemplazo=motivo_reemplazo,
        usuario_id=usuario_id,
    )


# --------------------------------------------------------------------------- el entorno


_VOLCADO: dict[str, LiteralString] = {
    "linea_base": "SELECT * FROM linea_base WHERE obra_id = %s ORDER BY id",
    "nivel": "SELECT * FROM nivel WHERE obra_id = %s ORDER BY id",
    "area": "SELECT a.* FROM area a JOIN nivel n ON n.id = a.nivel_id "
    "WHERE n.obra_id = %s ORDER BY a.id",
    "partida": "SELECT p.* FROM partida p JOIN area a ON a.id = p.area_id "
    "JOIN nivel n ON n.id = a.nivel_id WHERE n.obra_id = %s ORDER BY p.id",
    "concepto": "SELECT * FROM concepto WHERE obra_id = %s ORDER BY id",
    "partida_concepto": "SELECT pc.* FROM partida_concepto pc "
    "JOIN concepto c ON c.id = pc.concepto_id WHERE c.obra_id = %s ORDER BY pc.id",
    "apu": "SELECT a.* FROM apu a JOIN concepto c ON c.id = a.concepto_id "
    "WHERE c.obra_id = %s ORDER BY a.id",
    "apu_insumo": "SELECT ai.* FROM apu_insumo ai JOIN apu a ON a.id = ai.apu_id "
    "JOIN concepto c ON c.id = a.concepto_id WHERE c.obra_id = %s ORDER BY ai.id",
    "apu_cargo": "SELECT ac.* FROM apu_cargo ac JOIN apu a ON a.id = ac.apu_id "
    "JOIN concepto c ON c.id = a.concepto_id WHERE c.obra_id = %s ORDER BY ac.id",
}


class Base:
    """Lectura de la base de la prueba con una conexión propia del rol de aplicación."""

    def __init__(self, conexion: psycopg.Connection[tuple[Any, ...]]) -> None:
        self.conexion = conexion

    def filas(self, consulta: LiteralString, *parametros: object) -> list[tuple[Any, ...]]:
        """Las filas, con los `Decimal` como cadena para comprobar también la escala de la columna."""
        crudas = self.conexion.execute(consulta, parametros).fetchall()
        return [tuple(str(c) if isinstance(c, Decimal) else c for c in fila) for fila in crudas]

    def ejecutar(self, consulta: LiteralString, *parametros: object) -> None:
        self.conexion.execute(consulta, parametros)

    def foto(self) -> dict[str, object]:
        return foto_de_base(self.conexion)

    def volcado_de_obra(self, obra_id: uuid.UUID) -> dict[str, list[tuple[Any, ...]]]:
        """Todas las columnas de las filas de la obra en las ocho tablas de su jerarquía y su línea base."""
        return {tabla: self.filas(consulta, obra_id) for tabla, consulta in _VOLCADO.items()}


class Entorno:
    """Obra `AP-058-25` en planeación, los tipos de partida sembrados y un director que confirma."""

    def __init__(self, datos: DatosPresupuesto, base: Base) -> None:
        self.datos = datos
        self.base = base
        self.usuario_id = datos.usuario()
        self.obra_id = datos.obra(codigo=CODIGO_OBRA, creado_por_id=self.usuario_id)
        self.tipo_muros = datos.tipo_partida(clave="MUROS")
        self.tipo_plafon = datos.tipo_partida(clave="PLAFONES_Y_CAJILLOS")
        self.importacion_id: uuid.UUID = uuid.uuid4()

    def asignacion(self) -> dict[str, uuid.UUID]:
        """La de `CA-A1`: `MUROS EXTERIORES` → MUROS y `PLAFON` → PLAFONES_Y_CAJILLOS."""
        return {"MUROS EXTERIORES": self.tipo_muros, "PLAFON": self.tipo_plafon}

    def registrar_mano_obra(
        self,
        *,
        codigo: str = "MO-001",
        descripcion: str = "OFICIAL TABLAROQUERO",
        unidad: str = "JORNAL",
        tipo: str = "MANO_OBRA",
    ) -> uuid.UUID:
        """El insumo de mano de obra que el análisis de `preparacion_sintetica()` resuelve por descripción."""
        return self.datos.insumo(codigo=codigo, descripcion=descripcion, tipo=tipo, unidad=unidad)

    def importar(
        self,
        *,
        estado: str = "VALIDADO",
        preparacion: Preparacion | None = None,
        documento: Mapping[str, object] | None = None,
        obra_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Una importación de la obra con la preparación pedida (por omisión, la sintética de `CA-A1`).

        `RECIBIDO` y `ANALIZANDO` no admiten preparación (`ck_importacion_preparacion_tras_analisis`).
        """
        if documento is None and estado not in ("RECIBIDO", "ANALIZANDO"):
            documento = preparacion_a_json(
                preparacion if preparacion is not None else preparacion_sintetica()
            )
        return self.datos.importacion(
            obra_id=obra_id if obra_id is not None else self.obra_id,
            estado=estado,
            preparacion=documento,
            importado_por_id=self.usuario_id,
        )

    def poner_obra_en(self, estado: str) -> None:
        self.base.ejecutar("UPDATE obra SET estado = %s WHERE id = %s", estado, self.obra_id)

    def sembrar_congelada(self, *, obra_id: uuid.UUID | None = None) -> uuid.UUID:
        """Una línea base `CONGELADA` versión 1, en una obra que por eso ya está `ACTIVA`."""
        obra = obra_id if obra_id is not None else self.obra_id
        self.base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", obra)
        return self.datos.linea_base(estado="CONGELADA", obra_id=obra, version=1)

    def sembrar_borrador_con_jerarquia(
        self, *, obra_id: uuid.UUID | None = None, version: int = 1
    ) -> uuid.UUID:
        """Un borrador con una jerarquía anterior (nivel, área, partida, concepto y aparición).

        Sembrado a mano: no tiene asiento `CONFIRMAR` en la bitácora ni análisis (`P-5`).
        """
        obra = obra_id if obra_id is not None else self.obra_id
        datos = self.datos
        partida = datos.partida(area_id=datos.area(nivel_id=datos.nivel(obra_id=obra)))
        datos.partida_concepto(
            concepto_id=datos.concepto(obra_id=obra, codigo="OLD-1"), partida_id=partida
        )
        return datos.linea_base(estado="BORRADOR", obra_id=obra, version=version)

    def confirmar(
        self,
        contexto: Contexto,
        *,
        importacion_id: uuid.UUID | None = None,
        asignacion: Mapping[str, uuid.UUID] | None = None,
        reemplazar_borrador: bool = False,
        motivo_reemplazo: str | None = None,
    ) -> LineaBaseMaterializada:
        return _materializar(
            contexto(),
            importacion_id if importacion_id is not None else self.importacion_id,
            asignacion=asignacion if asignacion is not None else self.asignacion(),
            usuario_id=self.usuario_id,
            reemplazar_borrador=reemplazar_borrador,
            motivo_reemplazo=motivo_reemplazo,
        )

    def rechazo(
        self,
        contexto: Contexto,
        *,
        importacion_id: uuid.UUID | None = None,
        asignacion: Mapping[str, uuid.UUID] | None = None,
        reemplazar_borrador: bool = False,
        motivo_reemplazo: str | None = None,
    ) -> ErrorContrato:
        """Confirma, espera un `ErrorContrato` y comprueba que no cambió ninguna fila ni ningún estado."""
        antes = self.base.foto()
        with pytest.raises(ErrorContrato) as rechazo:
            self.confirmar(
                contexto,
                importacion_id=importacion_id,
                asignacion=asignacion,
                reemplazar_borrador=reemplazar_borrador,
                motivo_reemplazo=motivo_reemplazo,
            )
        assert self.base.foto() == antes, "Un rechazo no escribe: ninguna fila ni estado cambió"
        return rechazo.value


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def entorno(datos_presupuesto: DatosPresupuesto, base: Base) -> Entorno:
    """La obra, los tipos y el director; sin insumos registrados ni importación."""
    return Entorno(datos_presupuesto, base)


@pytest.fixture
def escenario(entorno: Entorno) -> Entorno:
    """`CA-A1`: la mano de obra ya registrada y la importación `VALIDADO` con el libro sintético."""
    entorno.registrar_mano_obra()
    entorno.importacion_id = entorno.importar()
    return entorno


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El `ContextoPresupuesto` de la prueba, construido al primer uso.

    Es perezoso a propósito: mientras A6a no cree `aplicacion/contexto.py`, el fallo ocurre dentro de la
    prueba (`FAILED`) y no al preparar la fixture (`ERROR`).
    """
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


# --------------------------------------------------------------------------- cuerpos esperados


def _conflicto(
    codigo: str,
    mensaje: str,
    detalle: Mapping[str, object],
    acciones: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "tipo": "CONFLICTO",
        "mensaje": mensaje,
        "codigo": codigo,
        "detalle": dict(detalle),
        "acciones": acciones if acciones is not None else [],
        "correlacion_id": CORRELACION,
    }


def _validacion(*errores: dict[str, str]) -> dict[str, object]:
    n = len(errores)
    return {
        "tipo": "VALIDACION",
        "mensaje": f"La petición tiene {n} campo inválido."
        if n == 1
        else f"La petición tiene {n} campos inválidos.",
        "errores": list(errores),
        "correlacion_id": CORRELACION,
    }


def _error_de_campo(campo: str, codigo: str, mensaje: str) -> dict[str, str]:
    return {"campo": campo, "codigo": codigo, "mensaje": mensaje}


def _afirmar_conflicto(error: ErrorContrato, esperado: dict[str, object]) -> None:
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado


def _afirmar_validacion(error: ErrorContrato, esperado: dict[str, object]) -> None:
    assert error.estado_http == 422
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado


# --------------------------------------------------------------------------- TC-A10 · CA-A1


@pytest.fixture
def confirmada_una_vez(
    escenario: Entorno, contexto: Contexto
) -> Callable[[], LineaBaseMaterializada]:
    """La confirmación feliz de `CA-A1`, ejecutada una sola vez y la primera vez que una prueba la pide."""
    return functools.cache(lambda: escenario.confirmar(contexto))


def test_hdu001_esc11_confirmar_materializa_la_jerarquia(
    escenario: Entorno, base: Base, confirmada_una_vez: Callable[[], LineaBaseMaterializada]
) -> None:
    """HDU-001 esc. 11 · RN-01 · TC-A10 — niveles, áreas, partidas, concepto y apariciones."""
    confirmada = confirmada_una_vez()
    assert confirmada.importacion_id == escenario.importacion_id
    assert confirmada.version == 1
    assert confirmada.importe_venta == Dinero("8329.9860")
    assert base.filas("SELECT id FROM linea_base WHERE obra_id = %s", escenario.obra_id) == [
        (confirmada.linea_base_id,)
    ]

    assert base.filas("SELECT nombre, orden FROM nivel WHERE obra_id = %s", escenario.obra_id) == [
        ("NIVEL 3", 1)
    ]
    assert base.filas(
        "SELECT a.nombre, a.tipo_unidad FROM area a JOIN nivel n ON n.id = a.nivel_id "
        "WHERE n.obra_id = %s ORDER BY a.nombre",
        escenario.obra_id,
    ) == [("ZONA MUROS", None), ("ZONA PLAFÓN", None)]
    assert base.filas(
        "SELECT codigo, descripcion, unidad FROM concepto WHERE obra_id = %s", escenario.obra_id
    ) == [(CODIGO_CONCEPTO, "Tablaroca en muros", "M2")]
    assert base.filas(
        "SELECT a.nombre, tp.clave, p.orden, c.codigo, pc.cantidad, pc.precio_unitario, pc.importe "
        "FROM partida_concepto pc "
        "JOIN concepto c ON c.id = pc.concepto_id "
        "JOIN partida p ON p.id = pc.partida_id "
        "JOIN tipo_partida tp ON tp.id = p.tipo_partida_id "
        "JOIN area a ON a.id = p.area_id "
        "WHERE c.obra_id = %s ORDER BY a.nombre",
        escenario.obra_id,
    ) == [
        ("ZONA MUROS", "MUROS", 1, CODIGO_CONCEPTO, "12.5000", "420.0000", "5250.0000"),
        (
            "ZONA PLAFÓN",
            "PLAFONES_Y_CAJILLOS",
            1,
            CODIGO_CONCEPTO,
            "7.3333",
            "420.0000",
            "3079.9860",
        ),
    ]


def test_hdu001_esc11_confirmar_crea_el_insumo_por_crear_y_reutiliza_la_mano_de_obra(
    escenario: Entorno, base: Base, confirmada_una_vez: Callable[[], LineaBaseMaterializada]
) -> None:
    """HDU-001 esc. 11 · TC-A10 — `PANEL YESO 1/2` nace marcado; `MO-001` ya existía y no cambia."""
    confirmada_una_vez()
    assert base.filas(
        "SELECT codigo, descripcion, unidad, tipo, activo, creado_en_importacion "
        "FROM insumo ORDER BY codigo"
    ) == [
        ("MO-001", "OFICIAL TABLAROQUERO", "JORNAL", "MANO_OBRA", True, False),
        ("PANEL YESO 1/2", "Panel de yeso 1/2", "PZA", "MATERIAL", True, True),
    ]


def test_hdu001_esc11_confirmar_crea_los_analisis_con_sus_insumos_y_cargos(
    escenario: Entorno, base: Base, confirmada_una_vez: Callable[[], LineaBaseMaterializada]
) -> None:
    """HDU-001 esc. 11 · TC-A10 — un solo `apu` por código de concepto, con el mapeo de la persona dueña."""
    confirmada_una_vez()
    assert base.filas(
        "SELECT a.fecha_analisis, a.analista, a.costo_material, a.costo_mano_obra, "
        "a.costo_directo, a.total_cargos, a.total_indirectos, a.precio_unitario "
        "FROM apu a JOIN concepto c ON c.id = a.concepto_id WHERE c.obra_id = %s",
        escenario.obra_id,
    ) == [
        (
            date(2026, 1, 15),
            "Analista ENITI",
            "200.0000",
            "100.0000",
            "300.0000",
            "50.0000",
            "60.0000",
            "420.0000",
        )
    ]
    assert base.filas(
        "SELECT i.codigo, ai.costo_unitario, ai.rendimiento, ai.cargo "
        "FROM apu_insumo ai JOIN insumo i ON i.id = ai.insumo_id "
        "JOIN apu a ON a.id = ai.apu_id JOIN concepto c ON c.id = a.concepto_id "
        "WHERE c.obra_id = %s ORDER BY i.codigo",
        escenario.obra_id,
    ) == [
        ("MO-001", "450.0000", "0.080000", "36.0000"),
        ("PANEL YESO 1/2", "85.5000", "0.673400", "57.5622"),
    ]
    assert base.filas(
        "SELECT ac.tipo, ac.porcentaje, ac.base_calculo, ac.importe "
        "FROM apu_cargo ac JOIN apu a ON a.id = ac.apu_id JOIN concepto c ON c.id = a.concepto_id "
        "WHERE c.obra_id = %s ORDER BY ac.tipo",
        escenario.obra_id,
    ) == [
        ("INDIRECTOS", None, None, "60.0000"),
        ("IVA", None, None, "40.0000"),
        ("UTILIDAD", None, None, "50.0000"),
    ]


def test_hdu001_esc11_confirmar_crea_la_linea_base_borrador_y_confirma_la_importacion(
    escenario: Entorno, base: Base, confirmada_una_vez: Callable[[], LineaBaseMaterializada]
) -> None:
    """HDU-001 esc. 11 · TC-A10 — borrador versión 1 con la suma de los importes; importación `CONFIRMADO`."""
    confirmada = confirmada_una_vez()
    assert base.filas(
        "SELECT id, version, estado, importe_venta, congelada_en, congelada_por_id, creado_por_id "
        "FROM linea_base WHERE obra_id = %s",
        escenario.obra_id,
    ) == [(confirmada.linea_base_id, 1, "BORRADOR", "8329.9860", None, None, escenario.usuario_id)]
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", escenario.importacion_id) == [
        ("CONFIRMADO",)
    ]
    assert base.filas("SELECT estado FROM obra WHERE id = %s", escenario.obra_id) == [
        ("PLANEACION",)
    ]


def test_hdu001_esc11_confirmar_asienta_confirmar_en_la_misma_transaccion(
    escenario: Entorno,
    base: Base,
    confirmada_una_vez: Callable[[], LineaBaseMaterializada],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 11 · RN-04 · TC-A10 — un asiento `CONFIRMAR` sin regla ni motivo, con `importacion_id`."""
    confirmada = confirmada_una_vez()
    asientos = base.filas(
        "SELECT accion, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
        "obra_id, datos_antes, datos_despues FROM bitacora"
    )
    assert asientos == [
        (
            "CONFIRMAR",
            "linea_base",
            confirmada.linea_base_id,
            escenario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            None,
            escenario.obra_id,
            None,
            {
                "importacion_id": str(escenario.importacion_id),
                "version": 1,
                "importe_venta": "8329.9860",
            },
        )
    ]


def test_hdu001_esc11_confirmar_no_crea_copias_explosion_ni_control(
    escenario: Entorno, base: Base, confirmada_una_vez: Callable[[], LineaBaseMaterializada]
) -> None:
    """HDU-001 esc. 11 · TC-A10 — las copias, la explosión y el control los crea el congelado (b), no esta fila."""
    confirmada_una_vez()
    filas = base.foto()["filas"]
    assert isinstance(filas, dict)
    assert (filas["linea_base_concepto"], filas["explosion_presupuesto"]) == (0, 0)
    assert filas["presupuesto_control"] == 0


def test_hdu001_esc11_confirmar_sin_borrador_ignora_el_reemplazo(
    escenario: Entorno, contexto: Contexto, base: Base
) -> None:
    """HDU-001 esc. 13 · diseño «Orden de comprobaciones» 6 — sin borrador, `reemplazar_borrador` no pide motivo."""
    resultado = escenario.confirmar(contexto, reemplazar_borrador=True, motivo_reemplazo=None)
    assert (resultado.version, resultado.importe_venta) == (1, Dinero("8329.9860"))
    assert base.filas("SELECT accion FROM bitacora") == [("CONFIRMAR",)]


def test_hdu001_esc11_confirmar_ignora_lo_que_pasa_en_otras_obras(
    escenario: Entorno, contexto: Contexto, base: Base
) -> None:
    """RN-01 · TC-A10 — la congelada y el borrador de OTRA obra no bloquean ni se tocan (filtro por obra)."""
    datos = escenario.datos
    otra = datos.obra(codigo="OT-001", creado_por_id=escenario.usuario_id)
    congelada_ajena = escenario.sembrar_congelada(obra_id=otra)
    otra_con_borrador = datos.obra(codigo="OT-002", creado_por_id=escenario.usuario_id)
    borrador_ajeno = escenario.sembrar_borrador_con_jerarquia(obra_id=otra_con_borrador)
    ajenas_antes = base.filas(
        "SELECT id, estado, version, importe_venta FROM linea_base WHERE id IN (%s, %s) ORDER BY id",
        congelada_ajena,
        borrador_ajeno,
    )

    resultado = escenario.confirmar(contexto)

    assert resultado.version == 1
    assert (
        base.filas(
            "SELECT id, estado, version, importe_venta FROM linea_base WHERE id IN (%s, %s) "
            "ORDER BY id",
            congelada_ajena,
            borrador_ajeno,
        )
        == ajenas_antes
    )
    assert base.filas("SELECT estado FROM obra WHERE id = %s", otra) == [("ACTIVA",)]


# --------------------------------------------------------------------------- TC-A11 · CA-A2 esc. 1


def test_hdu001_esc11_confirmar_con_errores_responde_importacion_con_errores(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 11 · TC-A11 · CA-A2 — `IMPORTACION_CON_ERRORES` y la importación sigue `CON_ERRORES`."""
    con_errores = escenario.importar(estado="CON_ERRORES")
    escenario.datos.error_importacion(importacion_id=con_errores)

    error = escenario.rechazo(contexto, importacion_id=con_errores)

    _afirmar_conflicto(
        error,
        _conflicto(
            "IMPORTACION_CON_ERRORES",
            MENSAJE_CON_ERRORES,
            {"importacion_id": str(con_errores), "estado": "CON_ERRORES"},
        ),
    )


# --------------------------------------------------------------------------- TC-A12 · CA-A2 esc. 2


@pytest.mark.parametrize("estado", ["RECIBIDO", "ANALIZANDO", "CONFIRMADO", "DESCARTADO"])
def test_tkt017_caa02_otro_estado_de_importacion(
    escenario: Entorno, contexto: Contexto, estado: str
) -> None:
    """TC-A12 · CA-A2 esc. 2 — `ESTADO_NO_PERMITE_OPERACION` con el estado actual en el detalle."""
    importacion = escenario.importar(estado=estado)

    error = escenario.rechazo(contexto, importacion_id=importacion)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ESTADO.format(estado=estado),
            {"importacion_id": str(importacion), "estado": estado},
        ),
    )


def test_tkt017_caa02_importacion_inexistente_responde_no_encontrado(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A10 · diseño «Orden de comprobaciones» 1 — sin fila, `NoEncontrado` de la importación."""
    error = escenario.rechazo(contexto, importacion_id=uuid.uuid4())

    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_NO_EXISTE,
        "recurso": "importacion",
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-A13 · CA-A3


def test_tkt017_caa03_asignacion_responde_422_falta_el_tipo(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A13 · CA-A3 esc. 1 · PA-T8 — `OBLIGATORIO` en la asignación de `PLAFON`; sigue `VALIDADO`."""
    error = escenario.rechazo(contexto, asignacion={"MUROS EXTERIORES": escenario.tipo_muros})

    _afirmar_validacion(
        error,
        _validacion(
            _error_de_campo("asignacion_tipos_partida.PLAFON", "OBLIGATORIO", MENSAJE_FALTA_TIPO)
        ),
    )
    assert escenario.base.filas(
        "SELECT estado FROM importacion WHERE id = %s", escenario.importacion_id
    ) == [("VALIDADO",)]


def test_tkt017_caa03_asignacion_responde_422_tipo_inexistente(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A13 · CA-A3 esc. 2 · PA-T8 — `VALOR_NO_PERMITIDO` con un tipo que no está en el catálogo."""
    asignacion = {**escenario.asignacion(), "PLAFON": uuid.uuid4()}

    error = escenario.rechazo(contexto, asignacion=asignacion)

    _afirmar_validacion(
        error,
        _validacion(
            _error_de_campo(
                "asignacion_tipos_partida.PLAFON", "VALOR_NO_PERMITIDO", MENSAJE_TIPO_INEXISTENTE
            )
        ),
    )


def test_tkt017_caa03_asignacion_responde_422_claves_ambiguas(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A13 · decisión 1 de la persona dueña — dos claves que normalizan igual con distinto tipo."""
    asignacion = {**escenario.asignacion(), " plafon ": escenario.tipo_muros}

    error = escenario.rechazo(contexto, asignacion=asignacion)

    _afirmar_validacion(
        error,
        _validacion(
            _error_de_campo(
                "asignacion_tipos_partida.PLAFON", "VALOR_NO_PERMITIDO", MENSAJE_CLAVES_AMBIGUAS
            )
        ),
    )


def test_tkt017_caa03_asignacion_responde_422_orden_faltantes_inexistentes_ambiguas(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A13 · CA-A3 (decisión de la persona dueña) — un error por partida: faltantes, luego inexistentes,
    luego ambiguas, y cada grupo ordenado por nombre.

    Seis partidas con nombres que no salen en este orden si se ordenara todo junto (`ALFA`, `BETA`,
    `CUBIERTA`...): fija el agrupamiento y el orden dentro de cada grupo.
    """
    muros, plafon = escenario.tipo_muros, escenario.tipo_plafon
    nombres = ("PLAFON", "MUROS EXTERIORES", "ZOCLO", "ALFA", "BETA", "CUBIERTA")
    mezcla = escenario.importar(preparacion=preparacion_con_partidas(nombres))
    asignacion = {
        "PLAFON": uuid.uuid4(),  # inexistente
        "CUBIERTA": uuid.uuid4(),  # inexistente
        "BETA": muros,  # ambigua con la clave siguiente
        " beta ": plafon,
        "MUROS EXTERIORES": muros,  # ambigua con la clave siguiente
        "muros exteriores": plafon,
        # ZOCLO y ALFA: faltantes
    }

    error = escenario.rechazo(contexto, importacion_id=mezcla, asignacion=asignacion)

    _afirmar_validacion(
        error,
        _validacion(
            _error_de_campo("asignacion_tipos_partida.ALFA", "OBLIGATORIO", MENSAJE_FALTA_TIPO),
            _error_de_campo("asignacion_tipos_partida.ZOCLO", "OBLIGATORIO", MENSAJE_FALTA_TIPO),
            _error_de_campo(
                "asignacion_tipos_partida.CUBIERTA", "VALOR_NO_PERMITIDO", MENSAJE_TIPO_INEXISTENTE
            ),
            _error_de_campo(
                "asignacion_tipos_partida.PLAFON", "VALOR_NO_PERMITIDO", MENSAJE_TIPO_INEXISTENTE
            ),
            _error_de_campo(
                "asignacion_tipos_partida.BETA", "VALOR_NO_PERMITIDO", MENSAJE_CLAVES_AMBIGUAS
            ),
            _error_de_campo(
                "asignacion_tipos_partida.MUROS EXTERIORES",
                "VALOR_NO_PERMITIDO",
                MENSAJE_CLAVES_AMBIGUAS,
            ),
        ),
    )


# --------------------------------------------------------------------------- TC-A14 · CA-A4


def _congelada_vigente(escenario: Entorno) -> Mapping[str, object]:
    vigente = escenario.sembrar_congelada()
    return {
        "obra": NOMBRE_COMPLETO_OBRA,
        "linea_base_vigente_id": str(vigente),
        "version_vigente": 1,
    }


def test_tkt017_caa04_obra_que_no_admite_linea_base_con_congelada(
    escenario: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-A14 · CA-A4 esc. 1 · RN-01 — el mensaje y el detalle son los de la vigente, no los del estado.

    Una obra con congelada está `ACTIVA`: si el caso de uso comprobara primero el estado de la obra,
    respondería «está en ACTIVA» (mutante `M-A5`).
    """
    detalle = _congelada_vigente(escenario)
    vigente = base.filas(
        "SELECT id, estado, version, importe_venta FROM linea_base WHERE obra_id = %s",
        escenario.obra_id,
    )

    error = escenario.rechazo(contexto)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION", MENSAJE_CONGELADA.format(codigo=CODIGO_OBRA), detalle
        ),
    )
    assert vigente[0][1:] == ("CONGELADA", 1, "1000000.0000")
    assert (
        base.filas(
            "SELECT id, estado, version, importe_venta FROM linea_base WHERE obra_id = %s",
            escenario.obra_id,
        )
        == vigente
    )


def test_tkt017_caa04_congelada_que_aparece_durante_la_confirmacion_responde_lo_mismo_que_la_vigente(
    escenario: Entorno, contexto: Contexto, base: Base, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CA-A4 esc. 1 · RN-01 · ADR-031 — el `23505` del índice de congelada vigente da el mismo `409`.

    Simula la carrera que el bloqueo de la obra ya impide: otra transacción congeló una línea base de la
    obra y esta confirmación no la vio. Hacen falta dos sustituciones, porque una sola no basta:
    `insertar_linea_base` siempre inserta `BORRADOR` y el índice parcial
    `uq_linea_base_obra_id_congelada` solo rechaza una segunda `CONGELADA`, y una congelada sembrada
    de antemano la vería la lectura de las líneas de la obra (y respondería por la rama del dominio,
    no por el motor). Por eso la primera lectura de las líneas de la obra devuelve vacío (lectura
    vencida) y `insertar_linea_base` intenta una `CONGELADA`, lo que el índice rechaza con `23505`.
    El rechazo es el de `CA-A4`: mismo mensaje y mismo detalle (`obra`, `linea_base_vigente_id`,
    `version_vigente`), `CONFLICTO` y no `REGLA_NEGOCIO` (en la confirmación no hay `RN-01` que citar).
    La obra sigue en `PLANEACION`: lo que se prueba es el motor, no el estado de la obra.
    """
    vigente = escenario.datos.linea_base(
        estado="CONGELADA", obra_id=escenario.obra_id, version=1, creado_por_id=escenario.usuario_id
    )
    lectura_original = repositorio_linea_base.lineas_base_de_obra
    lecturas: list[int] = []

    def lectura_vencida(sesion_bd: Session, obra_id: uuid.UUID) -> list[FilaLineaBase]:
        lecturas.append(1)
        return [] if len(lecturas) == 1 else lectura_original(sesion_bd, obra_id)

    def insertar_congelada(sesion_bd: Session, *args: object, **kwargs: object) -> None:
        sesion_bd.execute(
            text(
                "INSERT INTO linea_base (id, obra_id, version, estado, congelada_en, "
                "congelada_por_id, importe_venta, creado_por_id) "
                "VALUES (:id, :obra, 2, 'CONGELADA', now(), :usuario, 1, :usuario)"
            ),
            {"id": uuid.uuid4(), "obra": escenario.obra_id, "usuario": escenario.usuario_id},
        )

    monkeypatch.setattr(repositorio_linea_base, "lineas_base_de_obra", lectura_vencida)
    monkeypatch.setattr(repositorio_linea_base, "insertar_linea_base", insertar_congelada)

    with pytest.raises(ErrorContrato) as rechazo:
        escenario.confirmar(contexto)

    assert len(lecturas) == 2, (
        "La primera lectura es la de la confirmación; la segunda, la del rechazo"
    )
    _afirmar_conflicto(
        rechazo.value,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_CONGELADA.format(codigo=CODIGO_OBRA),
            {
                "obra": NOMBRE_COMPLETO_OBRA,
                "linea_base_vigente_id": str(vigente),
                "version_vigente": 1,
            },
        ),
    )
    assert base.filas(
        "SELECT id, estado, version FROM linea_base WHERE obra_id = %s", escenario.obra_id
    ) == [(vigente, "CONGELADA", 1)]
    assert base.filas("SELECT count(*) FROM nivel WHERE obra_id = %s", escenario.obra_id) == [(0,)]
    assert base.filas("SELECT count(*) FROM concepto WHERE obra_id = %s", escenario.obra_id) == [
        (0,)
    ]
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", escenario.importacion_id) == [
        ("VALIDADO",)
    ]
    assert base.filas("SELECT count(*) FROM bitacora") == [(0,)]


@pytest.mark.parametrize("estado_obra", ["ACTIVA", "SUSPENDIDA", "CERRADA"])
def test_tkt017_caa04_obra_que_no_admite_linea_base_fuera_de_planeacion(
    escenario: Entorno, contexto: Contexto, estado_obra: str
) -> None:
    """TC-A14 · CA-A4 esc. 2 · RN-01 — sin congelada, el estado de la obra va en el detalle."""
    escenario.poner_obra_en(estado_obra)

    error = escenario.rechazo(contexto)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_FUERA_DE_PLANEACION.format(codigo=CODIGO_OBRA, estado=estado_obra),
            {"obra": NOMBRE_COMPLETO_OBRA, "estado_obra": estado_obra},
        ),
    )


# --------------------------------------------------------------------------- orden de comprobaciones


def test_tkt017_caa02_el_estado_de_la_importacion_se_comprueba_antes_que_la_obra(
    escenario: Entorno, contexto: Contexto
) -> None:
    """Diseño «Orden de comprobaciones» 2 antes que 4 — una importación `RECIBIDO` en una obra con congelada."""
    escenario.sembrar_congelada()
    recibida = escenario.importar(estado="RECIBIDO")

    error = escenario.rechazo(contexto, importacion_id=recibida)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ESTADO.format(estado="RECIBIDO"),
            {"importacion_id": str(recibida), "estado": "RECIBIDO"},
        ),
    )


def test_tkt017_caa08_el_reemplazo_se_comprueba_antes_de_leer_la_preparacion(
    escenario: Entorno, contexto: Contexto
) -> None:
    """Diseño «Orden de comprobaciones» 6 antes que 7 — con borrador y formato ilegible, manda el reemplazo."""
    borrador = escenario.sembrar_borrador_con_jerarquia()
    ilegible = escenario.importar(
        documento={**preparacion_a_json(preparacion_sintetica()), "formato": 2}
    )

    error = escenario.rechazo(contexto, importacion_id=ilegible)

    _afirmar_conflicto(
        error,
        _conflicto(
            "REEMPLAZO_NO_CONFIRMADO",
            MENSAJE_REEMPLAZO,
            {"linea_base_borrador_id": str(borrador), "version": 1},
            [
                {
                    "clave": "CONFIRMAR_REEMPLAZO",
                    "metodo": "POST",
                    "ruta": f"/api/v1/importaciones/{ilegible}/confirmacion",
                }
            ],
        ),
    )


def test_tkt017_caa08_el_motivo_se_exige_antes_de_validar_la_asignacion(
    escenario: Entorno, contexto: Contexto
) -> None:
    """Diseño «Orden de comprobaciones» 6 antes que 8 — un reemplazo sin motivo y una asignación vacía dan un solo error."""
    escenario.sembrar_borrador_con_jerarquia()

    error = escenario.rechazo(
        contexto, asignacion={}, reemplazar_borrador=True, motivo_reemplazo=None
    )

    _afirmar_validacion(
        error,
        _validacion(_error_de_campo("motivo_reemplazo", "OBLIGATORIO", MENSAJE_CAMPO_OBLIGATORIO)),
    )


def test_tkt017_caa05_la_estructura_se_valida_antes_que_la_asignacion(
    escenario: Entorno, contexto: Contexto
) -> None:
    """Diseño «Orden de comprobaciones» 8 — con una preparación inconsistente y sin asignación, manda la preparación."""
    inconsistente = escenario.importar(preparacion=preparacion_con_ruta(nivel=None))

    error = escenario.rechazo(contexto, importacion_id=inconsistente, asignacion={})

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {
                "importacion_id": str(inconsistente),
                "motivo": "la importación debe analizarse de nuevo",
                "codigo_concepto": CODIGO_CONCEPTO,
            },
        ),
    )


# --------------------------------------------------------------------------- TC-A15 · CA-A5 esc. 1


def _sin(clave: str) -> Callable[[dict[str, object]], dict[str, object]]:
    return lambda documento: {k: v for k, v in documento.items() if k != clave}


def test_tkt017_caa05_formato_desconocido_no_escribe(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A15 · CA-A5 esc. 1 — `formato` 2: `ESTADO_NO_PERMITE_OPERACION`, «analizarse de nuevo», nada escrito."""
    ilegible = escenario.importar(
        documento={**preparacion_a_json(preparacion_sintetica()), "formato": 2}
    )

    error = escenario.rechazo(contexto, importacion_id=ilegible)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {"importacion_id": str(ilegible), "formato": 2},
        ),
    )


def test_tkt017_caa05_formato_desconocido_sin_formato_en_el_documento(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A15 · CA-A5 esc. 1 — un documento sin `formato` se lee como formato nulo."""
    ilegible = escenario.importar(
        documento=_sin("formato")(preparacion_a_json(preparacion_sintetica()))
    )

    error = escenario.rechazo(contexto, importacion_id=ilegible)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {"importacion_id": str(ilegible), "formato": None},
        ),
    )


def test_tkt017_caa05_formato_desconocido_sin_preparacion_guardada(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A15 · CA-A5 esc. 1 — una importación `VALIDADO` sin preparación no se confirma: formato nulo.

    Inferido de «`formato` (el leído o nulo)» en «Mensajes y detalles exactos»: el diseño no nombra
    este caso con todas las letras.
    """
    sin_preparacion = escenario.datos.importacion(
        obra_id=escenario.obra_id, estado="VALIDADO", importado_por_id=escenario.usuario_id
    )

    error = escenario.rechazo(contexto, importacion_id=sin_preparacion)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {"importacion_id": str(sin_preparacion), "formato": None},
        ),
    )


def _con_fecha_de_analisis(fecha: str) -> Callable[[dict[str, object]], dict[str, object]]:
    """Sustituye la `fecha` de la cabecera del primer análisis: la de `apu.fecha_analisis`."""

    def alterar(documento: dict[str, object]) -> dict[str, object]:
        analisis = documento["analisis"]
        assert isinstance(analisis, list)
        return {**documento, "analisis": [{**analisis[0], "fecha": fecha}, *analisis[1:]]}

    return alterar


@pytest.mark.parametrize(
    ("alterar", "formato_es_1"),
    [
        # Conserva el comportamiento de a1: el `formato` del detalle es «preparación JSON», no el 1.
        pytest.param(
            lambda d: {**d, "conceptos": "no_es_lista"}, False, id="conceptos_no_es_lista"
        ),
        pytest.param(_sin("nodos"), True, id="falta_la_clave_nodos"),
        pytest.param(_sin("analisis"), True, id="falta_la_clave_analisis"),
        pytest.param(_con_fecha_de_analisis("2026-13-45"), True, id="fecha_ilegible_mes_13"),
        pytest.param(_con_fecha_de_analisis("2026-02-30"), True, id="fecha_ilegible_30_de_febrero"),
    ],
)
def test_tkt017_caa05_formato_desconocido_estructura_ilegible_con_formato_1(
    escenario: Entorno,
    contexto: Contexto,
    alterar: Callable[[dict[str, object]], dict[str, object]],
    formato_es_1: bool,
) -> None:
    """TC-A15 · CA-A5 esc. 1 — con `formato` 1, una clave ausente o un tipo inesperado también es ilegible.

    Con `formato` 1 el detalle conserva `formato: 1`: la estructura es lo ilegible, no el número
    (salvo `conceptos_no_es_lista`, que conserva el comportamiento de a1 y no afirma el valor).
    Una fecha de análisis que no existe en el calendario también es una preparación ilegible: no
    llega a la base, donde sería un `ValueError` (`500`) al convertirla en `date`.
    """
    ilegible = escenario.importar(documento=alterar(preparacion_a_json(preparacion_sintetica())))

    error = escenario.rechazo(contexto, importacion_id=ilegible)

    assert error.estado_http == 409
    cuerpo = error.cuerpo(ROLES_DP, CORRELACION)
    detalle = cuerpo.pop("detalle")
    assert isinstance(detalle, dict)
    assert set(detalle) == {"importacion_id", "formato"}
    assert detalle["importacion_id"] == str(ilegible)
    if formato_es_1:
        assert detalle["formato"] == 1
    assert cuerpo == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_ILEGIBLE,
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "acciones": [],
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- decisión 2 · PreparacionInconsistente


def _con_cantidad_uno_y_precio_maximo() -> Preparacion:
    """Cada importe cabe en NUMERIC(18,4); la suma de la línea base, no (como en `TC-A08`)."""
    base = preparacion_sintetica()
    return replace(
        base,
        conceptos=tuple(replace(c, cantidad=Cantidad("1")) for c in base.conceptos),
        analisis=(replace(base.analisis[0], precio_unitario=Dinero("99999999999999")),),
    )


def _con_explosion_que_no_cabe() -> Preparacion:
    """El importe de venta cabe; la cantidad de material explotada no (como en `TC-A08`)."""
    base = preparacion_con_insumo(0, rendimiento=Rendimiento("99999999999.999999"))
    concepto = replace(base.conceptos[0], cantidad=Cantidad("9999999999.9999"))
    return replace(base, conceptos=(concepto, *base.conceptos[1:]))


_MIL_MILLONES = "100000000000000"

_PREPARACIONES_INCONSISTENTES: list[tuple[str, Callable[[], Preparacion], str, str | None]] = [
    (
        "estructura_sin_nivel",
        lambda: preparacion_con_ruta(nivel=None),
        "la importación debe analizarse de nuevo",
        CODIGO_CONCEPTO,
    ),
    (
        "mismo_codigo_con_otra_unidad",
        lambda: preparacion_con_concepto(1, unidad="PZA"),
        "concepto.unidad",
        CODIGO_CONCEPTO,
    ),
    (
        "columna_nula",
        lambda: preparacion_con_totales(material=None),
        "apu.costo_material",
        CODIGO_CONCEPTO,
    ),
    (
        "columna_que_no_cabe",
        lambda: preparacion_con_insumo(0, costo_unitario=Dinero(_MIL_MILLONES)),
        "apu_insumo.costo_unitario",
        CODIGO_CONCEPTO,
    ),
    (
        "importe_de_venta_que_no_cabe",
        _con_cantidad_uno_y_precio_maximo,
        "linea_base.importe_venta",
        None,
    ),
    ("explosion_que_no_cabe", _con_explosion_que_no_cabe, "explosion_presupuesto", None),
]


@pytest.mark.parametrize(
    ("preparacion", "motivo", "codigo_concepto"),
    [pytest.param(f, m, c, id=nombre) for nombre, f, m, c in _PREPARACIONES_INCONSISTENTES],
)
def test_tkt017_caa05_preparacion_inconsistente_responde_conflicto(
    escenario: Entorno,
    contexto: Contexto,
    preparacion: Callable[[], Preparacion],
    motivo: str,
    codigo_concepto: str | None,
) -> None:
    """TC-A08 en aplicación · CA-A5 · decisión 2 — `ESTADO_NO_PERMITE_OPERACION` con `motivo` y `codigo_concepto`.

    El código del concepto es nulo en los desbordes de los agregados (`explosion_presupuesto` y
    `linea_base.importe_venta`).
    """
    inconsistente = escenario.importar(preparacion=preparacion())

    error = escenario.rechazo(contexto, importacion_id=inconsistente)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {
                "importacion_id": str(inconsistente),
                "motivo": motivo,
                "codigo_concepto": codigo_concepto,
            },
        ),
    )


def test_tkt017_caa05_valor_que_cabe_en_dinero_pero_no_en_la_columna_del_apu(
    escenario: Entorno, contexto: Contexto
) -> None:
    """CA-A5 · deuda de a2 — `Dinero` es (18,4) y `apu.costo_material`, (14,4): PostgreSQL responde `22003`.

    El caso de uso traduce el `DBAPIError` con `traducir_error_del_motor` (A5), que responde el
    conflicto de la preparación ilegible con `detalle` vacío, y la transacción deshace todo.
    """
    desbordada = escenario.importar(
        preparacion=preparacion_con_totales(material=Dinero("100000000000.0000"))
    )

    error = escenario.rechazo(contexto, importacion_id=desbordada)

    _afirmar_conflicto(error, _conflicto("ESTADO_NO_PERMITE_OPERACION", MENSAJE_ILEGIBLE, {}))


# --------------------------------------------------------------------------- TC-A16 · CA-A5 esc. 2


def test_tkt017_caa05_explosion_rechazada_no_escribe_sugerido_negativo(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A16 · CA-A5 esc. 2 — `SUGERIDO_NEGATIVO` es una causa por tipo de partida: `concepto` nulo."""
    rechazada = escenario.importar(
        preparacion=preparacion_solo_muros(preparacion_sintetica_cargos_utilidad_indirectos_altos())
    )

    error = escenario.rechazo(
        contexto,
        importacion_id=rechazada,
        asignacion={"MUROS EXTERIORES": escenario.tipo_muros},
    )

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_EXPLOSION,
            {
                "importacion_id": str(rechazada),
                "causas": [
                    {
                        "concepto": None,
                        "causa": "SUGERIDO_NEGATIVO",
                        "clave_insumo": None,
                        "tipo_partida_id": str(escenario.tipo_muros),
                    }
                ],
            },
        ),
    )


def test_tkt017_caa05_explosion_rechazada_no_escribe_cargo_ausente(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A16 · CA-A5 esc. 2 — `CARGO_AUSENTE` es una causa por concepto: lleva el código del concepto."""
    rechazada = escenario.importar(
        preparacion=preparacion_solo_muros(preparacion_sintetica_sin_cargo_utilidad())
    )

    error = escenario.rechazo(
        contexto,
        importacion_id=rechazada,
        asignacion={"MUROS EXTERIORES": escenario.tipo_muros},
    )

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_EXPLOSION,
            {
                "importacion_id": str(rechazada),
                "causas": [
                    {
                        "concepto": CODIGO_CONCEPTO,
                        "causa": "CARGO_AUSENTE",
                        "clave_insumo": None,
                        "tipo_partida_id": None,
                    }
                ],
            },
        ),
    )


def _causa(
    concepto: str | None, causa: str, tipo_partida_id: uuid.UUID | None = None
) -> dict[str, object]:
    return {
        "concepto": concepto,
        "causa": causa,
        "clave_insumo": None,
        "tipo_partida_id": None if tipo_partida_id is None else str(tipo_partida_id),
    }


def _sin_utilidad(preparacion: Preparacion) -> Preparacion:
    return replace(
        preparacion,
        analisis=tuple(
            replace(a, cargos=tuple(c for c in a.cargos if c.tipo != TipoCargo.UTILIDAD))
            for a in preparacion.analisis
        ),
    )


def test_tkt017_caa05_explosion_rechazada_libro_completo_sugerido_negativo_una_causa_por_tipo(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A16 · CA-A5 esc. 2 — con el libro sintético completo, una causa por tipo de partida, sin concepto."""
    rechazada = escenario.importar(
        preparacion=preparacion_sintetica_cargos_utilidad_indirectos_altos()
    )

    error = escenario.rechazo(contexto, importacion_id=rechazada)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_EXPLOSION,
            {
                "importacion_id": str(rechazada),
                "causas": [
                    _causa(None, "SUGERIDO_NEGATIVO", escenario.tipo_muros),
                    _causa(None, "SUGERIDO_NEGATIVO", escenario.tipo_plafon),
                ],
            },
        ),
    )


def test_tkt017_caa05_explosion_rechazada_deduplica_causas_identicas(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A16 · CA-A5 esc. 2 (decisión de la persona dueña) — dos apariciones de `620040-A`, una sola causa.

    El explosionador devuelve una causa `CARGO_AUSENTE` por fila del catálogo; el detalle trae una por
    concepto (mismo concepto, causa, clave de insumo y tipo de partida).
    """
    rechazada = escenario.importar(preparacion=preparacion_sintetica_sin_cargo_utilidad())

    error = escenario.rechazo(contexto, importacion_id=rechazada)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_EXPLOSION,
            {
                "importacion_id": str(rechazada),
                "causas": [_causa(CODIGO_CONCEPTO, "CARGO_AUSENTE")],
            },
        ),
    )


def test_tkt017_caa05_explosion_rechazada_no_deduplica_causas_de_conceptos_distintos(
    escenario: Entorno, contexto: Contexto
) -> None:
    """TC-A16 · CA-A5 esc. 2 — la misma causa en dos conceptos distintos son dos causas, en orden del catálogo."""
    rechazada = escenario.importar(
        preparacion=_sin_utilidad(preparacion_dos_conceptos_con_alta_compartida())
    )

    error = escenario.rechazo(contexto, importacion_id=rechazada)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_EXPLOSION,
            {
                "importacion_id": str(rechazada),
                "causas": [
                    _causa(CODIGO_CONCEPTO, "CARGO_AUSENTE"),
                    _causa("620041-A", "CARGO_AUSENTE"),
                ],
            },
        ),
    )


# --------------------------------------------------------------------------- TC-A17 · CA-A6


def test_tkt017_caa06_insumo_reutilizado_o_en_conflicto_reutiliza_el_igual(
    escenario: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-A17 · CA-A6 esc. 1 · PA-T13 — mismo código, unidad y tipo: un solo insumo y su marca intacta."""
    existente = escenario.datos.insumo(
        codigo="PANEL YESO 1/2",
        descripcion="Panel yeso media pulgada",
        tipo="MATERIAL",
        unidad="PZA",
        creado_en_importacion=False,
    )

    escenario.confirmar(contexto)

    assert base.filas(
        "SELECT id, descripcion, unidad, tipo, activo, creado_en_importacion FROM insumo "
        "WHERE codigo = 'PANEL YESO 1/2'"
    ) == [(existente, "Panel yeso media pulgada", "PZA", "MATERIAL", True, False)]
    assert base.filas("SELECT count(*) FROM apu_insumo WHERE insumo_id = %s", existente) == [(1,)]
    assert base.filas("SELECT count(*) FROM insumo") == [(2,)]


@pytest.mark.parametrize(
    ("unidad_registrada", "tipo_registrado"),
    [
        pytest.param("M2", "MATERIAL", id="otra_unidad"),
        pytest.param("PZA", "MANO_OBRA", id="otro_tipo"),
    ],
)
def test_tkt017_caa06_insumo_reutilizado_o_en_conflicto_responde_conflicto_con_los_dos_lados(
    escenario: Entorno, contexto: Contexto, unidad_registrada: str, tipo_registrado: str
) -> None:
    """TC-A17 · CA-A6 esc. 2 · PA-T13 — el insumo por crear existe con otra unidad o tipo: nada se escribe."""
    escenario.datos.insumo(
        codigo="PANEL YESO 1/2",
        descripcion="Panel yeso media pulgada",
        tipo=tipo_registrado,
        unidad=unidad_registrada,
        creado_en_importacion=False,
    )

    error = escenario.rechazo(contexto)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_INSUMO_EN_CONFLICTO.format(codigo="PANEL YESO 1/2"),
            {
                "codigo": "PANEL YESO 1/2",
                "unidad_importacion": "PZA",
                "tipo_importacion": "MATERIAL",
                "unidad_registrada": unidad_registrada,
                "tipo_registrado": tipo_registrado,
            },
        ),
    )


def test_tkt017_caa06_catalogo_con_insumos_de_herramienta_y_consumible_no_impide_confirmar(
    escenario: Entorno, base: Base, contexto: Contexto
) -> None:
    """CA-A6 · F101 · `ck_insumo_tipo` — el catálogo admite cuatro tipos y confirmar los lee todos.

    El lector de libros produce solo `MATERIAL` y `MANO_OBRA`, pero la base admite además `HERRAMIENTA`
    y `CONSUMIBLE`: un insumo de esos tipos, registrado a mano o por otra vía, no puede hacer que
    `insumos_registrados` falle con `ValueError` ni dejar la confirmación en un `500`.
    """
    escenario.datos.insumo(
        codigo="HR-001", descripcion="ANDAMIO METALICO", tipo="HERRAMIENTA", unidad="PZA"
    )
    escenario.datos.insumo(
        codigo="CO-001", descripcion="CINTA DE PAPEL", tipo="CONSUMIBLE", unidad="ROLLO"
    )

    confirmada = escenario.confirmar(contexto)

    assert confirmada.version == 1
    assert confirmada.importe_venta == Dinero("8329.9860")
    assert base.filas(
        "SELECT codigo, tipo, unidad, creado_en_importacion FROM insumo ORDER BY codigo"
    ) == [
        ("CO-001", "CONSUMIBLE", "ROLLO", False),
        ("HR-001", "HERRAMIENTA", "PZA", False),
        ("MO-001", "MANO_OBRA", "JORNAL", False),
        ("PANEL YESO 1/2", "MATERIAL", "PZA", True),
    ]


@pytest.mark.parametrize("tipo_registrado", ["HERRAMIENTA", "CONSUMIBLE"])
def test_tkt017_caa06_insumo_registrado_como_herramienta_o_consumible_es_conflicto_de_tipo(
    escenario: Entorno, contexto: Contexto, tipo_registrado: str
) -> None:
    """CA-A6 esc. 2 · F101 · PA-T13 — el insumo por crear existe con un tipo que el lector no produce.

    El conflicto de tipo informa el tipo registrado tal como está en la base, también `HERRAMIENTA` y
    `CONSUMIBLE`; nada se escribe.
    """
    escenario.datos.insumo(
        codigo="PANEL YESO 1/2",
        descripcion="Panel yeso media pulgada",
        tipo=tipo_registrado,
        unidad="PZA",
        creado_en_importacion=False,
    )

    error = escenario.rechazo(contexto)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_INSUMO_EN_CONFLICTO.format(codigo="PANEL YESO 1/2"),
            {
                "codigo": "PANEL YESO 1/2",
                "unidad_importacion": "PZA",
                "tipo_importacion": "MATERIAL",
                "unidad_registrada": "PZA",
                "tipo_registrado": tipo_registrado,
            },
        ),
    )


def test_tkt017_caa06_insumo_reutilizado_o_en_conflicto_registrado_por_descripcion(
    entorno: Entorno, contexto: Contexto
) -> None:
    """TC-A17 · CA-A6 — el insumo ya registrado se resuelve por descripción; con otra unidad, el código es el suyo."""
    entorno.registrar_mano_obra(unidad="PZA")
    entorno.importacion_id = entorno.importar()

    error = entorno.rechazo(contexto)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_INSUMO_EN_CONFLICTO.format(codigo="MO-001"),
            {
                "codigo": "MO-001",
                "unidad_importacion": "JORNAL",
                "tipo_importacion": "MANO_OBRA",
                "unidad_registrada": "PZA",
                "tipo_registrado": "MANO_OBRA",
            },
        ),
    )


def test_tkt017_caa06_insumos_registrados_con_la_misma_descripcion_gana_el_primero_por_codigo(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """CA-A6 · deuda de a2 — dos registrados que normalizan igual: gana el de menor `codigo`.

    Los perdedores se insertan antes que el ganador y con otra unidad: sin `ORDER BY codigo` en
    `insumos_registrados`, el primero que devuelve PostgreSQL es un perdedor y la confirmación
    respondería `InsumoEnConflicto`.
    """
    for codigo, descripcion in [
        ("MO-004", "oficial tablaroquero"),
        ("MO-002", " OFICIAL   TABLAROQUERO "),
        ("MO-006", "Oficial Tablaroquero"),
        ("MO-003", "OFICIAL\tTABLAROQUERO"),
        ("MO-005", "oficial  tablaroquero"),
    ]:
        entorno.registrar_mano_obra(codigo=codigo, descripcion=descripcion, unidad="PZA")
    ganador = entorno.registrar_mano_obra(codigo="MO-001", descripcion="OFICIAL TABLAROQUERO")
    entorno.importacion_id = entorno.importar()

    entorno.confirmar(contexto)

    assert base.filas(
        "SELECT ai.insumo_id FROM apu_insumo ai JOIN insumo i ON i.id = ai.insumo_id "
        "WHERE i.tipo = 'MANO_OBRA'"
    ) == [(ganador,)]


# --------------------------------------------------------------------------- TC-A19 · CA-A8 esc. 1


def test_hdu001_esc13_reemplazo_sin_confirmar(escenario: Entorno, contexto: Contexto) -> None:
    """HDU-001 esc. 13 · TC-A19 · CA-A8 esc. 1 — `REEMPLAZO_NO_CONFIRMADO`; la jerarquía anterior intacta.

    Las acciones se filtran por rol: el Director de Proyectos ve `CONFIRMAR_REEMPLAZO` y Compras no.
    """
    borrador = escenario.sembrar_borrador_con_jerarquia()

    error = escenario.rechazo(contexto)

    accion = {
        "clave": "CONFIRMAR_REEMPLAZO",
        "metodo": "POST",
        "ruta": f"/api/v1/importaciones/{escenario.importacion_id}/confirmacion",
    }
    comun = {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_REEMPLAZO,
        "codigo": "REEMPLAZO_NO_CONFIRMADO",
        "detalle": {"linea_base_borrador_id": str(borrador), "version": 1},
        "correlacion_id": CORRELACION,
    }
    assert error.estado_http == 409
    assert error.cuerpo(frozenset({"DIRECTOR_PROYECTOS"}), CORRELACION) == {
        **comun,
        "acciones": [accion],
    }
    assert error.cuerpo(frozenset({"COMPRAS"}), CORRELACION) == {**comun, "acciones": []}
    assert escenario.base.filas(
        "SELECT count(*) FROM concepto WHERE obra_id = %s", escenario.obra_id
    ) == [(1,)]


def test_hdu001_esc13_reemplazo_sin_confirmar_aunque_traiga_motivo(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A19 — el motivo solo cuenta si `reemplazar_borrador` es verdadero."""
    borrador = escenario.sembrar_borrador_con_jerarquia()

    error = escenario.rechazo(
        contexto, reemplazar_borrador=False, motivo_reemplazo="Corrección de cantidades del nivel 3"
    )

    cuerpo = error.cuerpo(ROLES_DP, CORRELACION)
    assert (cuerpo["tipo"], cuerpo["codigo"]) == ("CONFLICTO", "REEMPLAZO_NO_CONFIRMADO")
    assert cuerpo["detalle"] == {"linea_base_borrador_id": str(borrador), "version": 1}


# --------------------------------------------------------------------------- TC-A20 · CA-A8 esc. 2


@pytest.mark.parametrize("motivo", [None, "", "   "], ids=["nulo", "vacio", "en_blanco"])
def test_hdu001_esc13_reemplazo_sin_motivo(
    escenario: Entorno, contexto: Contexto, motivo: str | None
) -> None:
    """HDU-001 esc. 13 · TC-A20 · CA-A8 esc. 2 — `422` `OBLIGATORIO` en `motivo_reemplazo`; nada se borra."""
    escenario.sembrar_borrador_con_jerarquia()

    error = escenario.rechazo(contexto, reemplazar_borrador=True, motivo_reemplazo=motivo)

    _afirmar_validacion(
        error,
        _validacion(_error_de_campo("motivo_reemplazo", "OBLIGATORIO", MENSAJE_CAMPO_OBLIGATORIO)),
    )


# --------------------------------------------------------------------------- contexto e interfaz


def test_tkt017_caa01_la_interfaz_publica_el_contexto_y_el_caso_de_uso() -> None:
    """TC-A10 · «Aplicación» — `interfaz.py` exporta `ContextoPresupuesto`, `LineaBaseMaterializada` y `materializar_importacion`."""
    assert interfaz.ContextoPresupuesto is modulo_contexto.ContextoPresupuesto
    assert interfaz.LineaBaseMaterializada is modulo_materializacion.LineaBaseMaterializada
    assert interfaz.materializar_importacion is modulo_materializacion.materializar_importacion


def test_tkt017_caa01_el_contexto_no_abre_el_motor_hasta_el_primer_uso() -> None:
    """«Aplicación» · contexto.py — la fábrica de sesiones es perezosa, igual que `ContextoIdentidad`."""
    llamadas: list[str] = []

    def proveedor() -> Engine:
        llamadas.append("motor")
        raise AssertionError("El motor no se pide al construir el contexto")

    contexto = construir_contexto(proveedor_motor=proveedor, reloj=None)

    assert llamadas == []
    assert callable(contexto.fabrica_sesiones)


def test_tkt017_caa01_el_contexto_usa_el_reloj_del_sistema_en_utc_por_omision() -> None:
    """«Aplicación» · contexto.py — sin reloj inyectado, `datetime.now(UTC)`: aware y en UTC."""

    def sin_motor() -> Engine:
        raise AssertionError("El reloj por omisión no necesita el motor")

    contexto = construir_contexto(proveedor_motor=sin_motor, reloj=None)

    ahora = contexto.reloj()

    assert ahora.tzinfo is not None
    assert ahora.utcoffset() == UTC.utcoffset(None)
    assert abs((datetime.now(UTC) - ahora).total_seconds()) < 5


# --------------------------------------------------------------------------- deuda de a2 que cae en dominio


def _planificar(preparacion: Preparacion) -> object:
    return planificar_materializacion(
        preparacion,
        asignacion=asignacion_tipos_hdu001_esc11(),
        tipos_partida=tipos_partida_hdu001_esc11(),
        insumos_registrados=insumos_registrados_sinteticos(),
        nuevo_id=uuid.uuid4,
    )


@pytest.mark.parametrize("indice_insumo", [0, 1], ids=["material", "mano_de_obra"])
@pytest.mark.parametrize(
    ("campo", "negativo", "columna"),
    [
        pytest.param("costo_unitario", Dinero("-1.0000"), "apu_insumo.costo_unitario", id="costo"),
        pytest.param(
            "rendimiento", Rendimiento("-0.010000"), "apu_insumo.rendimiento", id="rendimiento"
        ),
        pytest.param("cargo", Dinero("-1.0000"), "apu_insumo.cargo", id="cargo"),
    ],
)
def test_tkt017_caa05_valor_negativo_en_apu_insumo_es_preparacion_inconsistente(
    indice_insumo: int, campo: str, negativo: Dinero | Rendimiento, columna: str
) -> None:
    """TC-A08 · CA-A5 · deuda de a2 — `CHECK >= 0` de `apu_insumo` tiene su contraparte en dominio.

    Un valor negativo se rechaza como `PreparacionInconsistente` con el nombre de la columna y el
    código del concepto, antes de la explosión y sin llegar a la base (ahí sería `23514`, un `500`).
    """
    preparacion = preparacion_con_insumo(indice_insumo, **{campo: negativo})

    assert _planificar(preparacion) == PreparacionInconsistente(
        motivo=columna, codigo_concepto=CODIGO_CONCEPTO
    )


@pytest.mark.parametrize(
    ("indice_insumo", "campo", "cero"),
    [
        pytest.param(0, "costo_unitario", Dinero("0.0000"), id="material_costo"),
        pytest.param(0, "cargo", Dinero("0.0000"), id="material_cargo"),
        pytest.param(1, "costo_unitario", Dinero("0.0000"), id="mano_de_obra_costo"),
        pytest.param(1, "rendimiento", Rendimiento("0.000000"), id="mano_de_obra_rendimiento"),
        pytest.param(1, "cargo", Dinero("0.0000"), id="mano_de_obra_cargo"),
    ],
)
def test_tkt017_caa05_cero_en_apu_insumo_es_valido(
    indice_insumo: int, campo: str, cero: Dinero | Rendimiento
) -> None:
    """TC-A08 · CA-A5 · deuda de a2 — el `CHECK >= 0` admite el cero: una columna en cero planifica.

    Protege el borde de `_no_negativa` (`<` por `<=` rechazaría un insumo gratuito o sin rendimiento),
    columna por columna. El rendimiento cero de un material no está: la explosión lo rechaza por su
    propia regla (`RENDIMIENTO_NO_POSITIVO`), no por el `CHECK`.
    """
    preparacion = preparacion_con_insumo(indice_insumo, **{campo: cero})

    assert isinstance(_planificar(preparacion), PlanMaterializacion)


def test_tkt017_caa05_costo_negativo_no_llega_a_la_base(
    escenario: Entorno, contexto: Contexto
) -> None:
    """CA-A5 · deuda de a2 — en aplicación, el costo negativo es un `409` de la preparación, no un `23514`."""
    negativa = escenario.importar(
        preparacion=preparacion_con_insumo(1, costo_unitario=Dinero("-450.0000"))
    )

    error = escenario.rechazo(contexto, importacion_id=negativa)

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            MENSAJE_ILEGIBLE,
            {
                "importacion_id": str(negativa),
                "motivo": "apu_insumo.costo_unitario",
                "codigo_concepto": CODIGO_CONCEPTO,
            },
        ),
    )


# =========================================================================== FILA A6b
# Reemplazo del borrador y atomicidad (TC-A18 y TC-A21 · CA-A7 y CA-A9 · HDU-001 esc. 12 y 13).

MOTIVO = "Corrección de cantidades del nivel 3"
# «Orden de borrado del reemplazo» del diseño: de las hojas a la raíz, un `DELETE` por tabla.
_DELETE_DE_LAS_HOJAS_A_LA_RAIZ = [
    "apu_cargo",
    "apu_insumo",
    "apu",
    "partida_concepto",
    "concepto",
    "partida",
    "area",
    "nivel",
    "linea_base",
]
_SQL_INSUMOS = (
    "SELECT id, codigo, descripcion, unidad, tipo, activo, creado_en_importacion "
    "FROM insumo ORDER BY id"
)


def _ids(volcado: Mapping[str, list[tuple[Any, ...]]]) -> dict[str, set[uuid.UUID]]:
    return {tabla: {fila[0] for fila in filas} for tabla, filas in volcado.items()}


def _sentencias_delete(motor: Engine) -> list[str]:
    """Registra desde ahora cada `DELETE` que el motor ejecuta; devuelve la lista viva."""
    sentencias: list[str] = []

    def escuchar(conexion: Any, cursor: Any, sentencia: str, *resto: Any) -> None:
        if sentencia.lstrip().upper().startswith("DELETE"):
            sentencias.append(sentencia)

    event.listen(motor, "before_cursor_execute", escuchar)
    return sentencias


def _tablas_borradas(sentencias: list[str]) -> list[str]:
    coincidencias = [re.match(r"\s*DELETE\s+FROM\s+(\w+)", s, re.IGNORECASE) for s in sentencias]
    return [m.group(1) for m in coincidencias if m is not None]


class Reemplazo:
    """Una obra con un borrador real (importación 1 confirmada) y una importación 2 que lo reemplaza."""

    def __init__(self, escenario: Entorno, contexto: Contexto, reloj: RelojDePrueba) -> None:
        self.escenario = escenario
        self.contexto = contexto
        self.reloj = reloj
        self.importacion_1 = escenario.importacion_id
        self.momento_de_la_primera = reloj.ahora
        self.primera = escenario.confirmar(contexto)
        self.antes = escenario.base.volcado_de_obra(escenario.obra_id)
        self.insumos_antes = escenario.base.filas(_SQL_INSUMOS)
        # El mismo libro con la cantidad del plafón corregida: mismos códigos que la importación 1,
        # así que el `concepto` nuevo solo cabe si el anterior ya se borró (`uq_concepto_obra_id_codigo`).
        self.importacion_2 = escenario.importar(
            preparacion=preparacion_sintetica_cantidad_plafon("8.0000")
        )
        reloj.avanzar(timedelta(hours=1))
        self.momento_del_reemplazo = reloj.ahora

    def reemplazar(self, *, motivo: str | None = MOTIVO) -> LineaBaseMaterializada:
        return self.escenario.confirmar(
            self.contexto,
            importacion_id=self.importacion_2,
            reemplazar_borrador=True,
            motivo_reemplazo=motivo,
        )


@pytest.fixture
def reemplazo(
    escenario: Entorno, contexto: Contexto, reloj_de_prueba: RelojDePrueba
) -> Callable[[], Reemplazo]:
    """El borrador real y la importación que lo reemplaza, armados al primer uso (ver `contexto`)."""
    return functools.cache(lambda: Reemplazo(escenario, contexto, reloj_de_prueba))


def test_hdu001_esc13_reemplazo_confirmado(reemplazo: Callable[[], Reemplazo]) -> None:
    """HDU-001 esc. 13 · TC-A21 · CA-A9 — se borra el borrador y toda su jerarquía; la nueva es versión 1."""
    r = reemplazo()
    e, base = r.escenario, r.escenario.base

    nueva = r.reemplazar()

    assert nueva.importacion_id == r.importacion_2
    assert nueva.version == 1
    assert nueva.importe_venta == Dinero("8610.0000")
    despues = base.volcado_de_obra(e.obra_id)
    # Ninguna fila de la jerarquía anterior queda, en ninguna de las ocho tablas ni en `linea_base`.
    for tabla, ids_anteriores in _ids(r.antes).items():
        assert ids_anteriores, f"la importación 1 debía haber creado filas en {tabla}"
        assert not ids_anteriores & _ids(despues)[tabla], f"quedaron filas anteriores en {tabla}"
    assert base.filas(
        "SELECT id, version, estado, importe_venta FROM linea_base WHERE obra_id = %s", e.obra_id
    ) == [(nueva.linea_base_id, 1, "BORRADOR", "8610.0000")]
    assert {t: len(f) for t, f in despues.items() if t != "linea_base"} == {
        "nivel": 1,
        "area": 2,
        "partida": 2,
        "concepto": 1,
        "partida_concepto": 2,
        "apu": 1,
        "apu_insumo": 2,
        "apu_cargo": 3,
    }
    assert base.filas(
        "SELECT a.nombre, pc.cantidad, pc.importe FROM partida_concepto pc "
        "JOIN partida p ON p.id = pc.partida_id JOIN area a ON a.id = p.area_id "
        "JOIN nivel n ON n.id = a.nivel_id WHERE n.obra_id = %s ORDER BY a.nombre",
        e.obra_id,
    ) == [("ZONA MUROS", "12.5000", "5250.0000"), ("ZONA PLAFÓN", "8.0000", "3360.0000")]


def test_hdu001_esc13_reemplazo_confirmado_conserva_insumos_e_importacion_anterior(
    reemplazo: Callable[[], Reemplazo],
) -> None:
    """HDU-001 esc. 13 · TC-A21 · CA-A9 — los insumos anteriores no se tocan y la importación 1 sigue `CONFIRMADO`."""
    r = reemplazo()
    base = r.escenario.base

    r.reemplazar()

    assert len(r.insumos_antes) == 2
    assert base.filas(_SQL_INSUMOS) == r.insumos_antes
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", r.importacion_1) == [
        ("CONFIRMADO",)
    ]
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", r.importacion_2) == [
        ("CONFIRMADO",)
    ]


def test_hdu001_esc13_reemplazo_confirmado_asienta_descartar_y_confirmar(
    reemplazo: Callable[[], Reemplazo],
) -> None:
    """HDU-001 esc. 13 · RN-04 · TC-A21 · CA-A9 — `DESCARTAR` con motivo, sin regla, y `CONFIRMAR` de la nueva."""
    r = reemplazo()
    e = r.escenario

    nueva = r.reemplazar()

    por_accion = (
        "SELECT entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, obra_id, "
        "datos_antes, datos_despues FROM bitacora WHERE accion = %s ORDER BY ocurrido_en"
    )
    assert e.base.filas(por_accion, "DESCARTAR") == [
        (
            "linea_base",
            r.primera.linea_base_id,
            e.usuario_id,
            r.momento_del_reemplazo,
            None,
            MOTIVO,
            e.obra_id,
            {"estado": "BORRADOR", "version": 1, "importacion_id": str(r.importacion_1)},
            None,
        )
    ]
    assert e.base.filas(por_accion, "CONFIRMAR") == [
        (
            "linea_base",
            r.primera.linea_base_id,
            e.usuario_id,
            r.momento_de_la_primera,
            None,
            None,
            e.obra_id,
            None,
            {"importacion_id": str(r.importacion_1), "version": 1, "importe_venta": "8329.9860"},
        ),
        (
            "linea_base",
            nueva.linea_base_id,
            e.usuario_id,
            r.momento_del_reemplazo,
            None,
            None,
            e.obra_id,
            None,
            {"importacion_id": str(r.importacion_2), "version": 1, "importe_venta": "8610.0000"},
        ),
    ]


def test_hdu001_esc13_reemplazo_confirmado_borra_de_las_hojas_a_la_raiz_sin_tocar_copias_ni_control(
    reemplazo: Callable[[], Reemplazo], motor_aplicacion: Engine
) -> None:
    """HDU-001 esc. 13 · TC-A21 · «Orden de borrado del reemplazo» — nueve `DELETE`, en ese orden.

    Nunca se emite `DELETE` sobre `linea_base_concepto`, `explosion_presupuesto`,
    `presupuesto_control`, `insumo` ni `precio_insumo` (mutante `M-A6`: el rol de aplicación no tiene
    `DELETE` sobre las copias y PostgreSQL responde `42501`, un `500`).
    """
    r = reemplazo()
    sentencias = _sentencias_delete(motor_aplicacion)

    r.reemplazar()

    assert _tablas_borradas(sentencias) == _DELETE_DE_LAS_HOJAS_A_LA_RAIZ


def test_hdu001_esc13_reemplazo_confirmado_no_toca_otra_obra(
    escenario: Entorno, contexto: Contexto, reloj_de_prueba: RelojDePrueba
) -> None:
    """HDU-001 esc. 13 · TC-A21 · CA-A9 — el borrado filtra por la obra: la jerarquía y el borrador de otra no cambian.

    La otra obra tiene una importación confirmada de verdad (con su asiento `CONFIRMAR`) y el mismo
    código de concepto `620040-A`: un `DELETE` sin el filtro de la obra se la llevaría.
    """
    otra = escenario.datos.obra(codigo="OT-001", creado_por_id=escenario.usuario_id)
    escenario.confirmar(contexto, importacion_id=escenario.importar(obra_id=otra))
    r = Reemplazo(escenario, contexto, reloj_de_prueba)
    ajena_antes = escenario.base.volcado_de_obra(otra)
    asientos_ajenos = escenario.base.filas("SELECT * FROM bitacora WHERE obra_id = %s", otra)

    r.reemplazar()

    assert all(ajena_antes.values()), "la otra obra debía tener filas en todas las tablas"
    assert escenario.base.volcado_de_obra(otra) == ajena_antes
    assert (
        escenario.base.filas("SELECT * FROM bitacora WHERE obra_id = %s", otra) == asientos_ajenos
    )


def test_hdu001_esc13_reemplazo_confirmado_borrador_sin_asiento_deja_importacion_nula(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A21 · `P-5` — un borrador sembrado sin `CONFIRMAR` da `importacion_id` nulo.

    La otra obra sí tiene un `CONFIRMAR`: la lectura del asiento filtra por la línea base, no por la
    obra ni por la bitácora entera.
    """
    otra = escenario.datos.obra(codigo="OT-001", creado_por_id=escenario.usuario_id)
    escenario.confirmar(contexto, importacion_id=escenario.importar(obra_id=otra))
    borrador = escenario.sembrar_borrador_con_jerarquia()

    escenario.confirmar(contexto, reemplazar_borrador=True, motivo_reemplazo=MOTIVO)

    assert escenario.base.filas(
        "SELECT datos_antes, motivo, regla_negocio FROM bitacora WHERE accion = 'DESCARTAR' "
        "AND entidad_id = %s",
        borrador,
    ) == [({"estado": "BORRADOR", "version": 1, "importacion_id": None}, MOTIVO, None)]


def test_hdu001_esc13_reemplazo_confirmado_la_version_se_calcula_despues_del_borrado(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A21 · CA-A9 — `COALESCE(MAX(version), 0) + 1` sobre lo que queda tras borrar.

    Con `SUPERSEDIDA` 1 y 2 y el borrador en la versión 3, la nueva es la 3: si se calculara antes del
    borrado saldría la 4.
    """
    datos = escenario.datos
    datos.linea_base(estado="SUPERSEDIDA", obra_id=escenario.obra_id, version=1)
    datos.linea_base(estado="SUPERSEDIDA", obra_id=escenario.obra_id, version=2)
    borrador = escenario.sembrar_borrador_con_jerarquia(version=3)

    resultado = escenario.confirmar(contexto, reemplazar_borrador=True, motivo_reemplazo=MOTIVO)

    assert resultado.version == 3
    assert escenario.base.filas(
        "SELECT version, estado FROM linea_base WHERE obra_id = %s ORDER BY version",
        escenario.obra_id,
    ) == [(1, "SUPERSEDIDA"), (2, "SUPERSEDIDA"), (3, "BORRADOR")]
    assert escenario.base.filas(
        "SELECT datos_antes FROM bitacora WHERE accion = 'DESCARTAR' AND entidad_id = %s", borrador
    ) == [({"estado": "BORRADOR", "version": 3, "importacion_id": None},)]


def test_hdu001_esc13_sin_borrador_la_version_sale_1(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A21 — sin borrador ni líneas base la versión es 1 y no hay asiento `DESCARTAR`.

    Regresión del camino de A6a que A6b reescribe con `version_siguiente`: nace en verde.
    """
    resultado = escenario.confirmar(contexto, reemplazar_borrador=True, motivo_reemplazo=MOTIVO)

    assert resultado.version == 1
    assert escenario.base.filas("SELECT accion FROM bitacora") == [("CONFIRMAR",)]


def test_hdu001_esc13_sin_borrador_la_version_sigue_a_las_supersedidas(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A21 — sin borrador y con `SUPERSEDIDA` 1 y 2, la nueva es la 3.

    Regresión del camino de A6a que A6b reescribe con `version_siguiente`: nace en verde.
    """
    escenario.datos.linea_base(estado="SUPERSEDIDA", obra_id=escenario.obra_id, version=1)
    escenario.datos.linea_base(estado="SUPERSEDIDA", obra_id=escenario.obra_id, version=2)

    resultado = escenario.confirmar(contexto)

    assert resultado.version == 3


def test_hdu001_esc13_reemplazo_con_fila_que_referencia_el_borrador_no_borra_nada(
    escenario: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 13 · TC-A21 · `E-2` — una copia sembrada a mano frena el borrado con `23001`.

    El traductor del motor lo responde `ESTADO_NO_PERMITE_OPERACION` con la restricción, y la
    transacción deshace también los `DELETE` de `apu_cargo`, `apu_insumo` y `apu`, que ya se habían
    ejecutado (el paso 4, `partida_concepto`, es el que falla).
    """
    datos = escenario.datos
    sembrado = datos.linea_base_con_copias(estado="BORRADOR")
    (concepto_id,) = escenario.base.filas(
        "SELECT concepto_id FROM partida_concepto WHERE id = %s", sembrado.partida_concepto_id
    )[0]
    apu_id = datos.apu(concepto_id=concepto_id)
    datos.apu_insumo(apu_id=apu_id)
    datos.apu_cargo(apu_id=apu_id)
    otra_importacion = escenario.importar(obra_id=sembrado.obra_id)

    error = escenario.rechazo(
        contexto,
        importacion_id=otra_importacion,
        reemplazar_borrador=True,
        motivo_reemplazo=MOTIVO,
    )

    _afirmar_conflicto(
        error,
        _conflicto(
            "ESTADO_NO_PERMITE_OPERACION",
            "La operación entra en conflicto con el estado actual de los datos.",
            {"restriccion": "fk_linea_base_concepto_partida_concepto_id"},
        ),
    )
    assert escenario.base.filas("SELECT count(*) FROM apu WHERE id = %s", apu_id) == [(1,)]


@pytest.mark.parametrize("causa", ["asignacion_invalida", "formato_ilegible"])
def test_hdu001_esc13_reemplazo_rechazado_antes_de_borrar_no_borra_nada(
    escenario: Entorno, contexto: Contexto, causa: str
) -> None:
    """HDU-001 esc. 13 · TC-A21 · «Orden de comprobaciones» — todo rechazo va antes de la primera escritura.

    Con el reemplazo confirmado y su motivo, una asignación inválida (`422`) o una preparación ilegible
    (`409`) dejan el borrador, su jerarquía y la bitácora intactos: el `DELETE` no se emitió.
    """
    escenario.sembrar_borrador_con_jerarquia()
    documento = preparacion_a_json(preparacion_sintetica())
    if causa == "formato_ilegible":
        documento = {**documento, "formato": 2}
    importacion = escenario.importar(documento=documento)
    asignacion: dict[str, uuid.UUID] | None = {} if causa == "asignacion_invalida" else None

    error = escenario.rechazo(
        contexto,
        importacion_id=importacion,
        asignacion=asignacion,
        reemplazar_borrador=True,
        motivo_reemplazo=MOTIVO,
    )

    if causa == "asignacion_invalida":
        _afirmar_validacion(
            error,
            _validacion(
                _error_de_campo(
                    "asignacion_tipos_partida.MUROS EXTERIORES", "OBLIGATORIO", MENSAJE_FALTA_TIPO
                ),
                _error_de_campo(
                    "asignacion_tipos_partida.PLAFON", "OBLIGATORIO", MENSAJE_FALTA_TIPO
                ),
            ),
        )
    else:
        _afirmar_conflicto(
            error,
            _conflicto(
                "ESTADO_NO_PERMITE_OPERACION",
                MENSAJE_ILEGIBLE,
                {"importacion_id": str(importacion), "formato": 2},
            ),
        )


# --------------------------------------------------------------------------- TC-A18 · CA-A7


def _fallo_en_insertar_linea_base(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Sustituye `insertar_linea_base` por una función que falla ya con filas escritas en la sesión.

    Devuelve la lista (niveles, conceptos) que la sesión veía justo antes de fallar, para que la
    prueba demuestre que el fallo llega *después* de insertar niveles y conceptos.
    """
    vistas: list[tuple[int, int]] = []

    def falla(sesion_bd: Session, *args: object, **kwargs: object) -> None:
        niveles = len(sesion_bd.execute(select(tablas.nivel.c.id)).all())
        conceptos = len(sesion_bd.execute(select(tablas.concepto.c.id)).all())
        vistas.append((niveles, conceptos))
        raise RuntimeError("fallo provocado")

    monkeypatch.setattr(repositorio_linea_base, "insertar_linea_base", falla)
    return vistas


def test_hdu001_esc12_fallo_a_mitad_no_deja_nada(
    escenario: Entorno, contexto: Contexto, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HDU-001 esc. 12 · TC-A18 · CA-A7 — un fallo tras escribir niveles y conceptos no deja ninguna fila ni asiento.

    El caso de uso propaga el mismo `RuntimeError`, que no es un `ErrorContrato` (el manejador genérico
    lo responde 500 sin `tipo`). Regresión de A6a: la transacción única ya lo cumple, nace en verde.
    """
    vistas = _fallo_en_insertar_linea_base(monkeypatch)
    antes = escenario.base.foto()

    with pytest.raises(RuntimeError, match="fallo provocado") as fallo:
        escenario.confirmar(contexto)

    assert type(fallo.value) is RuntimeError
    assert not isinstance(fallo.value, ErrorContrato)
    assert vistas
    assert vistas[0][0] >= 1
    assert vistas[0][1] >= 1
    assert escenario.base.foto() == antes
    assert escenario.base.filas(
        "SELECT estado FROM importacion WHERE id = %s", escenario.importacion_id
    ) == [("VALIDADO",)]


def test_hdu001_esc12_fallo_a_mitad_del_reemplazo_no_deja_nada(
    reemplazo: Callable[[], Reemplazo], monkeypatch: pytest.MonkeyPatch
) -> None:
    """HDU-001 esc. 12 y 13 · TC-A18 · CA-A7 — un fallo después del borrado y del `DESCARTAR` los deshace.

    El borrador y su jerarquía siguen ahí, no hay asiento `DESCARTAR` ni `CONFIRMAR` nuevo y la
    importación 2 sigue `VALIDADO`.
    """
    r = reemplazo()
    e = r.escenario
    vistas = _fallo_en_insertar_linea_base(monkeypatch)
    antes = e.base.foto()

    with pytest.raises(RuntimeError, match="fallo provocado") as fallo:
        r.reemplazar()

    assert type(fallo.value) is RuntimeError, "NotImplementedError es subclase de RuntimeError"
    assert vistas
    assert vistas[0][0] >= 1
    assert vistas[0][1] >= 1
    assert e.base.foto() == antes
    assert e.base.volcado_de_obra(e.obra_id) == r.antes
    assert e.base.filas("SELECT accion FROM bitacora") == [("CONFIRMAR",)]
    assert e.base.filas("SELECT estado FROM importacion WHERE id = %s", r.importacion_2) == [
        ("VALIDADO",)
    ]
