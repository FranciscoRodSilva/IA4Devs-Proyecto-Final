"""Congelado de la línea base, fila B2 de TKT-017b1 (TC-B02, TC-B07, TC-B12 y TC-B15 más el caso de uso).

Cubre `CA-B1` a `CA-B3`, `CA-B5` y `CA-B7` (`HDU-001` esc. 14, 18 y 19, `RN-01`, `RN-24`) contra PostgreSQL
migrado con `alembic upgrade head` y el rol de aplicación, por `congelar_linea_base` del módulo
`cimenta.presupuesto.aplicacion.congelado`. La línea base `BORRADOR` sale siempre de la confirmación
real (`materializar_importacion`), salvo en los rechazos de estado, donde se siembra a mano. Cada rechazo
comprueba el contrato de error completo con `error.cuerpo(roles, correlacion)` y que no cambió ninguna
fila, ningún estado ni ningún asiento (`foto_de_base` más una fotografía de las obras, las líneas base
y las tres tablas que escribe el congelado).

Las fixtures de caso de uso (`contexto`, `congelado_en_doce`) son perezosas: construyen su valor la
primera vez que una prueba lo pide y lo guardan con `functools.cache`.

Rojo original de B2 (riesgo `R-2` de a3, aceptado por la persona dueña): cuando se escribió el archivo,
el módulo `congelado` y las funciones de la parte b del repositorio no existían, y cada prueba fallaba
por el nombre ausente. Ese rojo ya está documentado en `impl.md`; hoy el módulo y las funciones existen
y el archivo corre en verde.

Pruebas añadidas en el ciclo 1 de corrección de `/sdd-revisar` (hallazgos de los auditores de b1):
el orden estable y el `IN` sin ids repetidos de `filas_explotables` nacieron en rojo (`F001` y `F003` de
SQL); la validación del motivo dentro del caso de uso y la rama `23505` del congelado (`F002` y `F004`
de código) nacieron en verde, porque ya anclan un comportamiento que existía sin prueba.

Los importes esperados son literales del diseño o del cálculo a mano (`23250.0000` = 6 × 12.5 × (420 −
50 − 60)); ninguno se recalcula con el código bajo prueba. `TC-B02` es la excepción deliberada: compara
con la función de dominio, que es lo que el criterio pide (la validada es la congelada).

La concurrencia (`TC-B08` a `TC-B10`) vive en `test_tkt017_congelado_concurrencia.py`.
Mutantes que este archivo debe poner en rojo: `M-B2` (`TC-B02`), `M-B3`, `M-B4` y `M-B5` (el camino
feliz), `M-B6` (`test_hdu001_esc19_segunda_linea_base_vigente_en_el_caso_de_uso`).
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, LiteralString, NamedTuple, cast

import psycopg
import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.presupuesto.aplicacion import congelado as caso_de_uso_congelado
from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_error_del_motor
from cimenta.presupuesto.dominio.congelado import CongeladoAdmitido
from cimenta.presupuesto.dominio.materializacion import (
    PlanMaterializacion,
    planificar_materializacion,
)
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from cimenta.presupuesto.interfaz import LineaBaseMaterializada
from contrato_error.excepciones import (
    ConflictoEstado,
    ErrorContrato,
    NoEncontrado,
    RechazoRegla,
    ValidacionRechazada,
)
from herramientas.soporte_tkt017 import (
    preparacion_alta_compartida_con_segundo_insumo,
    preparacion_dos_niveles,
    preparacion_sintetica,
    preparacion_solo_muros,
)
from herramientas.soporte_tkt017_entorno import (
    MOTIVO_DE_CONGELADO,
    NOMBRE_COMPLETO_OBRA,
    Base,
    Contexto,
    Entorno,
    congelar,
)
from tipos_base import Rendimiento

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt017-b2"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
CODIGO_OBRA = "AP-058-25"
MOTIVO = MOTIVO_DE_CONGELADO

MENSAJE_RN01 = (
    "La obra {codigo} ya tiene una línea base congelada; para sustituirla hay que crear una versión "
    "nueva que marque la anterior como SUPERSEDIDA."
)
MENSAJE_LINEA_EN_OTRO_ESTADO = (
    "La línea base está en {estado}; solo se congela una línea base en BORRADOR."
)
MENSAJE_FUERA_DE_PLANEACION = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_NO_EXISTE = "La línea base no existe."
MENSAJE_EXPLOSION = "La explosión de insumos de la importación no se puede calcular."
MENSAJE_IN001 = "La línea base congelada no se modifica."


# --------------------------------------------------------------------------- el entorno


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def entorno(datos_presupuesto: DatosPresupuesto, base: Base) -> Entorno:
    """La obra en planeación, los cuatro tipos sembrados, el director y la mano de obra registrada."""
    entorno = Entorno(datos_presupuesto, base)
    entorno.registrar_mano_obra()
    return entorno


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El `ContextoPresupuesto` de la prueba, construido al primer uso y reutilizado."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


def _estado_completo(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: la foto del soporte más las obras, las líneas base completas
    y todo lo que escribe el congelado (copias, explosión y control), con todas sus columnas."""
    return {
        "foto": base.foto(),
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "copias": base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        "explosion": base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
        "control": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
    }


def _rechazo(
    entorno: Entorno,
    contexto: Contexto,
    linea_base_id: uuid.UUID,
    *,
    motivo: str = MOTIVO,
) -> ErrorContrato:
    """Congela, espera un `ErrorContrato` y comprueba que no cambió ninguna fila ni ningún estado."""
    antes = _estado_completo(entorno.base)
    with pytest.raises(ErrorContrato) as rechazo:
        congelar(contexto(), linea_base_id, usuario_id=entorno.usuario_id, motivo=motivo)
    assert _estado_completo(entorno.base) == antes, (
        "Un rechazo no escribe: ninguna fila ni estado cambió"
    )
    return rechazo.value


def _afirmar_conflicto(error: ErrorContrato, mensaje: str, detalle: Mapping[str, object]) -> None:
    assert isinstance(error, ConflictoEstado)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONFLICTO",
        "mensaje": mensaje,
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": dict(detalle),
        "acciones": [],
        "correlacion_id": CORRELACION,
    }


class Congelado(NamedTuple):
    """El resultado de confirmar y congelar el libro de `CA-B1`, con lo que había justo antes."""

    borrador: LineaBaseMaterializada
    devuelto: uuid.UUID
    congelador_id: uuid.UUID
    momento_de_la_confirmacion: datetime
    momento: datetime
    jerarquia_antes: dict[str, list[tuple[Any, ...]]]
    insumos_antes: list[tuple[Any, ...]]


_SQL_INSUMOS = (
    "SELECT id, codigo, descripcion, unidad, tipo, activo, creado_en_importacion "
    "FROM insumo ORDER BY id"
)


@pytest.fixture
def congelado_en_doce(
    entorno: Entorno, contexto: Contexto, reloj_de_prueba: RelojDePrueba
) -> Callable[[], Congelado]:
    """`CA-B1`: confirma el libro de 12 apariciones de MUROS y PLAFONES_Y_CAJILLOS y lo congela.

    Lo congela un director distinto del que confirmó y dos horas después, para que ningún valor se
    confunda con el de la confirmación. Se arma una sola vez, la primera vez que una prueba lo pide.
    """

    def armar() -> Congelado:
        entorno.importacion_id = entorno.importar(preparacion=preparacion_dos_niveles())
        momento_de_la_confirmacion = reloj_de_prueba.ahora
        borrador = entorno.confirmar(contexto)
        congelador_id = entorno.datos.usuario()
        reloj_de_prueba.avanzar(timedelta(hours=2))
        jerarquia_antes = entorno.base.volcado_de_obra(entorno.obra_id)
        jerarquia_antes.pop("linea_base")
        insumos_antes = entorno.base.filas(_SQL_INSUMOS)
        devuelto = congelar(contexto(), borrador.linea_base_id, usuario_id=congelador_id)
        return Congelado(
            borrador=borrador,
            devuelto=devuelto,
            congelador_id=congelador_id,
            momento_de_la_confirmacion=momento_de_la_confirmacion,
            momento=reloj_de_prueba.ahora,
            jerarquia_antes=jerarquia_antes,
            insumos_antes=insumos_antes,
        )

    return functools.cache(armar)


# --------------------------------------------------------------------------- TC-B01 en el caso de uso · CA-B1


def test_hdu001_esc14_congelar_devuelve_el_id_de_la_linea_base(
    congelado_en_doce: Callable[[], Congelado],
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 — el caso de uso devuelve el id de la línea base congelada."""
    congelado = congelado_en_doce()
    assert congelado.devuelto == congelado.borrador.linea_base_id


def test_hdu001_esc14_congelar_copia_los_doce_conceptos_con_su_importe(
    entorno: Entorno, base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-24 — 12 copias con código, cantidad, precio e importe."""
    congelado = congelado_en_doce()
    planeadas = base.filas(
        "SELECT pc.id, c.codigo, pc.cantidad, pc.precio_unitario, pc.importe "
        "FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s ORDER BY pc.id",
        entorno.obra_id,
    )
    copias = base.filas(
        "SELECT partida_concepto_id, codigo, cantidad, precio_unitario, importe "
        "FROM linea_base_concepto WHERE linea_base_id = %s ORDER BY partida_concepto_id",
        congelado.borrador.linea_base_id,
    )

    assert len(planeadas) == 12
    assert copias == planeadas, "Cada copia es la aparición del concepto: mismos números, mismo id"
    assert {fila[1:] for fila in copias} == {("620040-A", "12.5000", "420.0000", "5250.0000")}
    assert base.filas("SELECT count(*) FROM linea_base_concepto") == [(12,)]


def test_hdu001_esc14_congelar_copia_la_explosion_agregada_por_tipo_e_insumo(
    base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-24 — un renglón por tipo de partida e insumo explotable."""
    congelado = congelado_en_doce()
    assert base.filas(
        "SELECT tp.clave, i.codigo, e.cantidad_presupuestada, e.rendimiento_congelado, "
        "e.costo_unitario, e.importe_venta "
        "FROM explosion_presupuesto e JOIN tipo_partida tp ON tp.id = e.tipo_partida_id "
        "JOIN insumo i ON i.id = e.insumo_id WHERE e.linea_base_id = %s ORDER BY tp.clave",
        congelado.borrador.linea_base_id,
    ) == [
        ("MUROS", "PANEL YESO 1/2", "50.5050", "0.673400", "85.5000", "4318.1775"),
        ("PLAFONES_Y_CAJILLOS", "PANEL YESO 1/2", "50.5050", "0.673400", "85.5000", "4318.1775"),
    ]


def test_hdu001_esc14_congelar_crea_cuatro_controles_con_el_sugerido_y_sin_tope(
    base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-03 — uno por tipo; `0.0000` donde no hay conceptos; tope nulo."""
    congelado = congelado_en_doce()
    assert base.filas(
        "SELECT tp.clave, c.importe_sugerido, c.importe_tope "
        "FROM presupuesto_control c JOIN tipo_partida tp ON tp.id = c.tipo_partida_id "
        "WHERE c.linea_base_id = %s ORDER BY tp.clave",
        congelado.borrador.linea_base_id,
    ) == [
        ("ENCHAPES", "0.0000", None),
        ("GENERALES", "0.0000", None),
        ("MUROS", "23250.0000", None),
        ("PLAFONES_Y_CAJILLOS", "23250.0000", None),
    ]
    assert base.filas("SELECT count(*) FROM presupuesto_control") == [(4,)]


def test_hdu001_esc14_congelar_deja_la_linea_base_congelada_con_fecha_usuario_y_motivo(
    entorno: Entorno, base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-01 — `CONGELADA`; solo cambian estado, fecha, usuario y motivo."""
    congelado = congelado_en_doce()
    assert base.filas(
        "SELECT id, version, estado, importe_venta, congelada_en, congelada_por_id, motivo, "
        "creado_en, creado_por_id FROM linea_base WHERE obra_id = %s",
        entorno.obra_id,
    ) == [
        (
            congelado.borrador.linea_base_id,
            1,
            "CONGELADA",
            "63000.0000",
            congelado.momento,
            congelado.congelador_id,
            MOTIVO,
            congelado.momento_de_la_confirmacion,
            entorno.usuario_id,
        )
    ]


def test_hdu001_esc14_congelar_pasa_la_obra_a_activa(
    entorno: Entorno, base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 — la obra queda `ACTIVA`, con quién y cuándo la actualizó (M-B3)."""
    congelado = congelado_en_doce()
    assert base.filas(
        "SELECT estado, actualizado_en, actualizado_por_id FROM obra WHERE id = %s",
        entorno.obra_id,
    ) == [("ACTIVA", congelado.momento, congelado.congelador_id)]


def test_hdu001_esc14_congelar_asienta_congelar_con_rn01_en_la_misma_transaccion(
    entorno: Entorno, base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-04 — `CONGELAR` con `RN-01`, motivo y el antes y el después (M-B4)."""
    congelado = congelado_en_doce()
    assert base.filas(
        "SELECT accion, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
        "obra_id, datos_antes, datos_despues FROM bitacora WHERE accion = 'CONGELAR'"
    ) == [
        (
            "CONGELAR",
            "linea_base",
            congelado.borrador.linea_base_id,
            congelado.congelador_id,
            congelado.momento,
            "RN-01",
            MOTIVO,
            entorno.obra_id,
            {"estado": "BORRADOR"},
            {"estado": "CONGELADA", "version": 1, "importe_venta": "63000.0000"},
        )
    ]
    assert base.filas("SELECT accion FROM bitacora ORDER BY ocurrido_en") == [
        ("CONFIRMAR",),
        ("CONGELAR",),
    ]


def test_hdu001_esc14_congelar_no_toca_la_jerarquia_ni_los_insumos(
    entorno: Entorno, base: Base, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 — congelar copia; no modifica niveles, conceptos, análisis ni insumos."""
    congelado = congelado_en_doce()
    despues = base.volcado_de_obra(entorno.obra_id)
    despues.pop("linea_base")
    assert despues == congelado.jerarquia_antes
    assert base.filas(_SQL_INSUMOS) == congelado.insumos_antes
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", entorno.importacion_id) == [
        ("CONFIRMADO",)
    ]


def test_hdu001_esc14_las_copias_y_los_controles_traen_los_importes_planeados(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """HDU-001 esc. 14 · TC-B01 · CA-B1 · RN-24 — con decimales de cuatro lugares la suma de las copias es la venta.

    El libro de `CA-A1`: `12.5000 × 420.0000 = 5250.0000` y `7.3333 × 420.0000 = 3079.9860`, suma
    `8329.9860`; el sugerido de cada tipo es cantidad × (420 − 50 − 60): `3875.0000` y `2273.3230`.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)

    congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    assert base.filas(
        "SELECT codigo, cantidad, precio_unitario, importe FROM linea_base_concepto "
        "WHERE linea_base_id = %s ORDER BY cantidad DESC",
        borrador.linea_base_id,
    ) == [
        ("620040-A", "12.5000", "420.0000", "5250.0000"),
        ("620040-A", "7.3333", "420.0000", "3079.9860"),
    ]
    assert base.filas(
        "SELECT sum(importe) FROM linea_base_concepto WHERE linea_base_id = %s",
        borrador.linea_base_id,
    ) == [("8329.9860",)]
    assert base.filas(
        "SELECT importe_venta FROM linea_base WHERE id = %s", borrador.linea_base_id
    ) == [("8329.9860",)]
    assert base.filas(
        "SELECT tp.clave, c.importe_sugerido FROM presupuesto_control c "
        "JOIN tipo_partida tp ON tp.id = c.tipo_partida_id WHERE c.linea_base_id = %s "
        "ORDER BY tp.clave",
        borrador.linea_base_id,
    ) == [
        ("ENCHAPES", "0.0000"),
        ("GENERALES", "0.0000"),
        ("MUROS", "3875.0000"),
        ("PLAFONES_Y_CAJILLOS", "2273.3230"),
    ]


def test_hdu001_esc14_congelar_ignora_lo_que_pasa_en_otras_obras(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """HDU-001 esc. 14 · CA-B1 · RN-01 — la congelada y el borrador de OTRA obra no bloquean, no se copian ni se tocan.

    Sin el filtro por obra, el `INSERT ... SELECT` copiaría la aparición de la otra obra (3 copias en
    lugar de 2) y la explosión la rechazaría por no tener análisis.
    """
    datos = entorno.datos
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    ajena_con_congelada = datos.obra(codigo="OT-001", creado_por_id=entorno.usuario_id)
    congelada_ajena = entorno.sembrar_congelada(obra_id=ajena_con_congelada)
    ajena_con_borrador = datos.obra(codigo="OT-002", creado_por_id=entorno.usuario_id)
    partida = datos.partida(
        area_id=datos.area(nivel_id=datos.nivel(obra_id=ajena_con_borrador)),
        tipo_partida_id=entorno.tipo_muros,
    )
    datos.partida_concepto(
        concepto_id=datos.concepto(obra_id=ajena_con_borrador, codigo="OLD-1"), partida_id=partida
    )
    borrador_ajeno = datos.linea_base(estado="BORRADOR", obra_id=ajena_con_borrador)
    ajenas = (congelada_ajena, borrador_ajeno)
    lineas_ajenas_antes = base.filas(
        "SELECT * FROM linea_base WHERE id IN (%s, %s) ORDER BY id", *ajenas
    )
    obras_ajenas_antes = base.filas(
        "SELECT * FROM obra WHERE id IN (%s, %s) ORDER BY id",
        ajena_con_congelada,
        ajena_con_borrador,
    )

    congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    assert base.filas("SELECT count(*) FROM linea_base_concepto") == [(2,)]
    assert base.filas("SELECT count(*) FROM presupuesto_control") == [(4,)]
    assert base.filas(
        "SELECT count(*) FROM linea_base_concepto WHERE linea_base_id IN (%s, %s)", *ajenas
    ) == [(0,)]
    assert (
        base.filas("SELECT * FROM linea_base WHERE id IN (%s, %s) ORDER BY id", *ajenas)
        == lineas_ajenas_antes
    )
    assert (
        base.filas(
            "SELECT * FROM obra WHERE id IN (%s, %s) ORDER BY id",
            ajena_con_congelada,
            ajena_con_borrador,
        )
        == obras_ajenas_antes
    )


def test_hdu001_esc14_congelar_dos_veces_la_misma_linea_base_se_rechaza(
    entorno: Entorno, contexto: Contexto, congelado_en_doce: Callable[[], Congelado]
) -> None:
    """HDU-001 esc. 14 · CA-B3 — la segunda congelación de la misma línea base responde por su estado."""
    congelado = congelado_en_doce()

    error = _rechazo(entorno, contexto, congelado.borrador.linea_base_id)

    _afirmar_conflicto(
        error,
        MENSAJE_LINEA_EN_OTRO_ESTADO.format(estado="CONGELADA"),
        {"linea_base_id": str(congelado.borrador.linea_base_id), "estado": "CONGELADA"},
    )


# --------------------------------------------------------------------------- TC-B02 · CA-B1


@pytest.mark.parametrize("libro", ["sintetica", "alta_compartida_en_muros"])
def test_hdu001_esc14_la_explosion_congelada_es_la_validada(
    libro: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    sesion_bd: Session,
) -> None:
    """HDU-001 esc. 14 · TC-B02 · CA-B1 · invariante 19 — la explosión congelada es la que validó la confirmación.

    Tras confirmar y congelar, `planificar_materializacion` sobre la misma preparación da `plan.explosion`;
    sus renglones, por `(tipo_partida_id, codigo)`, son iguales a las filas de `explosion_presupuesto`
    unidas a `insumo`: cantidad, rendimiento congelado, costo e importe. En el segundo libro dos
    conceptos de MUROS usan el mismo panel con rendimientos distintos (`0.673400` y `0.500000`): el
    rendimiento congelado es el ponderado por cantidad, no el del primer concepto (M-B2).
    """
    if libro == "sintetica":
        preparacion = preparacion_sintetica()
        asignacion = entorno.asignacion()
    else:
        preparacion = preparacion_alta_compartida_con_segundo_insumo(
            rendimiento=Rendimiento("0.500000")
        )
        asignacion = {"MUROS EXTERIORES": entorno.tipo_muros, "PLAFON": entorno.tipo_muros}
    entorno.importacion_id = entorno.importar(preparacion=preparacion)
    borrador = entorno.confirmar(contexto, asignacion=asignacion)

    congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    plan = planificar_materializacion(
        preparacion,
        asignacion=asignacion,
        tipos_partida=repositorio_linea_base.tipos_partida(sesion_bd),
        insumos_registrados=repositorio_linea_base.insumos_registrados(sesion_bd),
        nuevo_id=uuid.uuid4,
    )
    assert isinstance(plan, PlanMaterializacion)
    validada = {
        (r.tipo_partida_id, r.clave_insumo): (
            r.cantidad_presupuestada.valor,
            r.rendimiento_congelado.valor,
            r.costo_unitario.valor,
            r.importe.valor,
        )
        for r in plan.explosion.renglones
    }
    congelada = {
        (fila[0], fila[1]): tuple(fila[2:])
        for fila in base.conexion.execute(
            "SELECT e.tipo_partida_id, i.codigo, e.cantidad_presupuestada, "
            "e.rendimiento_congelado, e.costo_unitario, e.importe_venta "
            "FROM explosion_presupuesto e JOIN insumo i ON i.id = e.insumo_id "
            "WHERE e.linea_base_id = %s",
            (borrador.linea_base_id,),
        ).fetchall()
    }

    assert validada, "La preparación debe explotar al menos un insumo"
    assert congelada == validada
    if libro == "alta_compartida_en_muros":
        assert base.filas(
            "SELECT cantidad_presupuestada, rendimiento_congelado, costo_unitario, importe_venta "
            "FROM explosion_presupuesto WHERE linea_base_id = %s",
            borrador.linea_base_id,
        ) == [("12.0842", "0.609286", "85.5000", "1033.1948")]


# --------------------------------------------------------------------------- TC-B03 · CA-B2


def test_hdu001_esc19_segunda_linea_base_vigente_en_el_caso_de_uso(
    entorno: Entorno, contexto: Contexto
) -> None:
    """HDU-001 esc. 19 · TC-B03 · CA-B2 · RN-01 — con una congelada vigente no se congela otra (M-B6).

    La obra ya está `ACTIVA` porque tiene congelada: si se comprobara el estado de la obra primero,
    el mensaje sería el de la obra fuera de planeación y no el de `SUPERSEDIDA`.
    """
    vigente = entorno.sembrar_congelada()
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id, version=2)

    error = _rechazo(entorno, contexto, borrador)

    assert isinstance(error, RechazoRegla)
    assert error.estado_http == 409
    esperado = {
        "tipo": "REGLA_NEGOCIO",
        "mensaje": MENSAJE_RN01.format(codigo=CODIGO_OBRA),
        "regla": "RN-01",
        "detalle": {
            "obra": NOMBRE_COMPLETO_OBRA,
            "linea_base_vigente_id": str(vigente),
            "version_vigente": 1,
        },
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert error.cuerpo(frozenset({"COMPRAS"}), CORRELACION) == esperado


# --------------------------------------------------------------------------- TC-B04 · CA-B3


@pytest.mark.parametrize("estado", ["CONGELADA", "SUPERSEDIDA"])
def test_tkt017_cab03_linea_base_en_otro_estado(
    estado: str, entorno: Entorno, contexto: Contexto
) -> None:
    """TC-B04 · CA-B3 esc. 1 — una línea base que no está en `BORRADOR` responde `ESTADO_NO_PERMITE_OPERACION`."""
    if estado == "CONGELADA":
        linea_base = entorno.sembrar_congelada()
    else:
        linea_base = entorno.datos.linea_base(
            estado="SUPERSEDIDA", obra_id=entorno.obra_id, version=1
        )

    error = _rechazo(entorno, contexto, linea_base)

    _afirmar_conflicto(
        error,
        MENSAJE_LINEA_EN_OTRO_ESTADO.format(estado=estado),
        {"linea_base_id": str(linea_base), "estado": estado},
    )


def test_tkt017_cab03_el_estado_de_la_linea_base_va_antes_que_la_otra_congelada(
    entorno: Entorno, contexto: Contexto
) -> None:
    """CA-B3 · diseño «Orden de comprobaciones del congelado» 3 y 4 — una `SUPERSEDIDA` no es `RN-01`.

    La obra tiene una congelada vigente (versión 2), pero lo que se intenta congelar es la versión 1
    `SUPERSEDIDA`: la respuesta es por su estado, no por la vigente.
    """
    entorno.poner_obra_en("ACTIVA")
    superseda = entorno.datos.linea_base(estado="SUPERSEDIDA", obra_id=entorno.obra_id, version=1)
    entorno.datos.linea_base(estado="CONGELADA", obra_id=entorno.obra_id, version=2)

    error = _rechazo(entorno, contexto, superseda)

    _afirmar_conflicto(
        error,
        MENSAJE_LINEA_EN_OTRO_ESTADO.format(estado="SUPERSEDIDA"),
        {"linea_base_id": str(superseda), "estado": "SUPERSEDIDA"},
    )


@pytest.mark.parametrize("estado_obra", ["SUSPENDIDA", "CERRADA", "ACTIVA"])
def test_tkt017_cab03_obra_en_otro_estado(
    estado_obra: str, entorno: Entorno, contexto: Contexto
) -> None:
    """TC-B04 · CA-B3 esc. 2 — con la obra fuera de `PLANEACION` y sin congelada no se congela."""
    borrador = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id)
    entorno.poner_obra_en(estado_obra)

    error = _rechazo(entorno, contexto, borrador)

    _afirmar_conflicto(
        error,
        MENSAJE_FUERA_DE_PLANEACION.format(codigo=CODIGO_OBRA, estado=estado_obra),
        {"obra": NOMBRE_COMPLETO_OBRA, "estado_obra": estado_obra},
    )


def test_tkt017_cab03_linea_base_inexistente_responde_no_encontrado(
    entorno: Entorno, contexto: Contexto
) -> None:
    """TC-B04 · diseño «Orden de comprobaciones del congelado» 1 — sin fila, `NoEncontrado` de la línea base."""
    error = _rechazo(entorno, contexto, uuid.uuid4())

    assert isinstance(error, NoEncontrado)
    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_NO_EXISTE,
        "recurso": "linea_base",
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-B05 en el caso de uso · CA-B4


def test_tkt017_cab04_congelar_sin_motivo_en_el_caso_de_uso(
    entorno: Entorno, contexto: Contexto
) -> None:
    """TC-B05 · CA-B4 esc. 1 · RN-04 — un motivo en blanco que llega al caso de uso se rechaza y todo vuelve atrás.

    La ruta lo para antes, en `Motivo`, con `422`. Este es el respaldo del caso de uso, que no confía en
    quien lo llama: la línea base es congelable de verdad, así que el rechazo llega cuando la copia, la
    explosión, los controles, el cambio de estado y la obra ya están escritos en la transacción, y quien
    lo lanza es la validación del asiento `CONGELAR`. La transacción entera se deshace: `_rechazo`
    compara cada tabla que escribe el congelado antes y después.

    Nace en verde: la validación existe, vive en `asentar` (que corre al final) y ninguna prueba la anclaba.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)

    error = _rechazo(entorno, contexto, borrador.linea_base_id, motivo="   ")

    assert isinstance(error, ValidacionRechazada)
    assert error.estado_http == 422
    assert [e.como_dict() for e in error.errores] == [
        {"campo": "motivo", "codigo": "OBLIGATORIO", "mensaje": "El campo es obligatorio."}
    ]
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 1 campo inválido.",
        "errores": [
            {"campo": "motivo", "codigo": "OBLIGATORIO", "mensaje": "El campo es obligatorio."}
        ],
        "correlacion_id": CORRELACION,
    }
    assert entorno.base.filas(
        "SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id
    ) == [("BORRADOR",)]
    assert entorno.base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [
        ("PLANEACION",)
    ]
    assert entorno.base.filas("SELECT accion::text FROM bitacora") == [("CONFIRMAR",)]


# --------------------------------------------------------------------------- TC-B03 por el índice del motor · CA-B2


def test_hdu001_esc19_el_indice_de_congelada_vigente_responde_rn01(
    entorno: Entorno,
    contexto: Contexto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HDU-001 esc. 19 · TC-B03 · CA-B2 · RN-01 · ADR-031 — si la regla no lo detiene, el índice parcial responde el mismo `RN-01`.

    La rama `23505` de `uq_linea_base_obra_id_congelada` es la red de seguridad de la comprobación del
    dominio. Para ejercitarla de verdad se deja pasar `evaluar_congelado` (el chequeo del caso de uso) y
    se siembra una congelada versión 2 junto a un borrador real versión 1: la copia, la explosión y los
    controles se escriben y el `UPDATE` que congela el borrador choca con el índice único del motor. El
    caso de uso abre entonces una transacción corta y devuelve el cuerpo exacto de `TC-B03` (obra,
    vigente y su versión 2, acciones vacías, el mensaje que manda marcar la anterior como `SUPERSEDIDA`);
    la transacción larga se deshace. Un espía sobre `traducir_error_del_motor` comprueba que el rechazo
    salió de esa rama y no de la comprobación del dominio.

    Con el bloqueo de la obra tomado primero, dos congelados reales nunca llegan a esta rama: la regla
    los serializa y el segundo ve la congelada del primero (`TC-B08` documenta que RN-01 es la rama
    determinista). Por eso esta prueba anula la regla. Nace en verde: la rama existe y no la anclaba nadie.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    entorno.poner_obra_en("ACTIVA")
    vigente = entorno.datos.linea_base(estado="CONGELADA", obra_id=entorno.obra_id, version=2)
    monkeypatch.setattr(caso_de_uso_congelado, "evaluar_congelado", lambda **_: CongeladoAdmitido())
    traduccion = caso_de_uso_congelado.traducir_error_del_motor
    del_motor: list[tuple[str | None, str | None]] = []

    def espiar(error: DBAPIError, **argumentos: Any) -> ErrorContrato | None:
        original = cast("psycopg.Error", error.orig)
        del_motor.append((original.sqlstate, original.diag.constraint_name))
        return traduccion(error, **argumentos)

    monkeypatch.setattr(caso_de_uso_congelado, "traducir_error_del_motor", espiar)

    error = _rechazo(entorno, contexto, borrador.linea_base_id)

    assert del_motor == [("23505", "uq_linea_base_obra_id_congelada")]
    assert isinstance(error, RechazoRegla)
    assert error.estado_http == 409
    esperado = {
        "tipo": "REGLA_NEGOCIO",
        "mensaje": MENSAJE_RN01.format(codigo=CODIGO_OBRA),
        "regla": "RN-01",
        "detalle": {
            "obra": NOMBRE_COMPLETO_OBRA,
            "linea_base_vigente_id": str(vigente),
            "version_vigente": 2,
        },
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert error.cuerpo(frozenset({"COMPRAS"}), CORRELACION) == esperado
    assert entorno.base.filas(
        "SELECT id, version, estado FROM linea_base WHERE obra_id = %s ORDER BY version",
        entorno.obra_id,
    ) == [(borrador.linea_base_id, 1, "BORRADOR"), (vigente, 2, "CONGELADA")]


# --------------------------------------------------------------------------- TC-B15 · CA-B1


@pytest.mark.parametrize("causa", ["sugerido_negativo", "cargo_ausente"])
def test_tkt017_cab01_explosion_imposible_al_congelar(
    causa: str, entorno: Entorno, contexto: Contexto
) -> None:
    """TC-B15 · CA-B1 · RN-24 — si `explotar_filas` rechaza las filas del borrador, no se congela nada.

    Defensivo: la confirmación ya validó la explosión, pero un `apu_cargo` corregido a mano después puede
    dejarla imposible. Libro de un solo aparición (`preparacion_solo_muros`) para que cada causa salga
    una sola vez. El sugerido negativo es una causa por tipo (`concepto` nulo); el cargo ausente, por concepto.
    """
    entorno.importacion_id = entorno.importar(preparacion=preparacion_solo_muros())
    borrador = entorno.confirmar(contexto)
    if causa == "sugerido_negativo":
        entorno.base.ejecutar("UPDATE apu_cargo SET importe = 400 WHERE tipo = 'UTILIDAD'")
        causas = [
            {
                "concepto": None,
                "causa": "SUGERIDO_NEGATIVO",
                "clave_insumo": None,
                "tipo_partida_id": str(entorno.tipo_muros),
            }
        ]
    else:
        entorno.base.ejecutar("DELETE FROM apu_cargo WHERE tipo = 'UTILIDAD'")
        causas = [
            {
                "concepto": "620040-A",
                "causa": "CARGO_AUSENTE",
                "clave_insumo": None,
                "tipo_partida_id": None,
            }
        ]

    error = _rechazo(entorno, contexto, borrador.linea_base_id)

    _afirmar_conflicto(
        error,
        MENSAJE_EXPLOSION,
        {"linea_base_id": str(borrador.linea_base_id), "causas": causas},
    )
    assert entorno.base.filas(
        "SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id
    ) == [("BORRADOR",)]


# --------------------------------------------------------------------------- TC-B12 · CA-B7

# Qué debe haberse escrito ya en la sesión, justo antes de que falle cada paso (orden de escritura
# del diseño: copias, explosión, controles, línea base, obra, asiento).
_PROGRESO_ANTES_DE_FALLAR: dict[str, dict[str, int]] = {
    "insertar_controles": {
        "copias": 2,
        "explosion": 2,
        "controles": 4,
        "congeladas": 0,
        "activas": 0,
    },
    "congelar": {"copias": 2, "explosion": 2, "controles": 4, "congeladas": 1, "activas": 0},
    "activar_obra": {"copias": 2, "explosion": 2, "controles": 4, "congeladas": 1, "activas": 1},
}


def _fallar_despues_de(monkeypatch: pytest.MonkeyPatch, paso: str) -> list[dict[str, int]]:
    """Sustituye el paso del repositorio por una función que lo ejecuta y falla ya con filas escritas.

    Devuelve la lista (una entrada por fallo) con lo que la propia sesión veía justo antes de fallar,
    para que la prueba demuestre que el fallo llega *después* de las escrituras anteriores.
    """
    original = getattr(repositorio_linea_base, paso)
    vistas: list[dict[str, int]] = []

    def cuenta(sesion_bd: Session, consulta: str) -> int:
        return int(sesion_bd.execute(text(consulta)).scalar_one())

    def falla(sesion_bd: Session, *args: Any, **kwargs: Any) -> None:
        original(sesion_bd, *args, **kwargs)
        vistas.append(
            {
                "copias": cuenta(sesion_bd, "SELECT count(*) FROM linea_base_concepto"),
                "explosion": cuenta(sesion_bd, "SELECT count(*) FROM explosion_presupuesto"),
                "controles": cuenta(sesion_bd, "SELECT count(*) FROM presupuesto_control"),
                "congeladas": cuenta(
                    sesion_bd, "SELECT count(*) FROM linea_base WHERE estado = 'CONGELADA'"
                ),
                "activas": cuenta(sesion_bd, "SELECT count(*) FROM obra WHERE estado = 'ACTIVA'"),
            }
        )
        raise RuntimeError("fallo provocado")

    monkeypatch.setattr(repositorio_linea_base, paso, falla)
    return vistas


@pytest.mark.parametrize("paso", list(_PROGRESO_ANTES_DE_FALLAR))
def test_tkt017_cab07_fallo_a_mitad_del_congelado(
    paso: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B12 · CA-B7 · RN-01 — un fallo después de copiar deja la línea base en `BORRADOR` y la base como estaba.

    El caso de uso propaga el mismo `RuntimeError`, que no es un `ErrorContrato` (el manejador genérico
    lo responde `500` sin `tipo`). Se prueba el fallo tras `insertar_controles` (el del criterio) y tras
    los dos últimos pasos de escritura, `congelar` y `activar_obra`: con la línea base ya `CONGELADA` y la
    obra ya `ACTIVA` dentro de la transacción, todo vuelve atrás y no queda asiento `CONGELAR`.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    antes = _estado_completo(base)
    vista_antes = base.volcado_de_obra(entorno.obra_id)
    vistas = _fallar_despues_de(monkeypatch, paso)

    with pytest.raises(RuntimeError, match="fallo provocado") as fallo:
        congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    assert type(fallo.value) is RuntimeError, "NotImplementedError es subclase de RuntimeError"
    assert not isinstance(fallo.value, ErrorContrato)
    assert vistas == [_PROGRESO_ANTES_DE_FALLAR[paso]]
    assert _estado_completo(base) == antes
    assert base.volcado_de_obra(entorno.obra_id) == vista_antes
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        ("BORRADOR",)
    ]
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("PLANEACION",)]
    assert base.filas("SELECT count(*) FROM linea_base_concepto") == [(0,)]
    assert base.filas("SELECT count(*) FROM explosion_presupuesto") == [(0,)]
    assert base.filas("SELECT count(*) FROM presupuesto_control") == [(0,)]
    assert base.filas("SELECT accion FROM bitacora") == [("CONFIRMAR",)]


def test_tkt017_cab06_in001_dentro_del_congelado_responde_rn01(
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B12 · CA-B6 · ADR-031 — un `IN001` del motor dentro del congelado sale como `409` `RN-01`, no como `500`.

    El paso `insertar_explosion` se envuelve para que la propia sesión ya haya pasado la línea base a
    `CONGELADA` cuando el `INSERT` llega: el disparador de inmutabilidad lo rechaza con `IN001` dentro
    de la transacción del caso de uso, que debe traducirlo (M-B7) y deshacerlo todo.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    antes = _estado_completo(base)
    original = repositorio_linea_base.insertar_explosion

    def congela_antes_de_insertar(sesion_bd: Session, *args: Any, **kwargs: Any) -> Any:
        sesion_bd.execute(
            text(
                "UPDATE linea_base SET estado = 'CONGELADA', congelada_en = now(), "
                "congelada_por_id = :usuario WHERE id = :linea_base"
            ),
            {"usuario": entorno.usuario_id, "linea_base": borrador.linea_base_id},
        )
        return original(sesion_bd, *args, **kwargs)

    monkeypatch.setattr(repositorio_linea_base, "insertar_explosion", congela_antes_de_insertar)

    with pytest.raises(ErrorContrato) as rechazo:
        congelar(contexto(), borrador.linea_base_id, usuario_id=entorno.usuario_id)

    error = rechazo.value
    assert isinstance(error, RechazoRegla)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "REGLA_NEGOCIO",
        "mensaje": MENSAJE_IN001,
        "regla": "RN-01",
        "detalle": {"tabla": "explosion_presupuesto"},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert _estado_completo(base) == antes


# --------------------------------------------------------------------------- TC-B07 · CA-B5

_ENCHAPES = "ENCHAPES"

# (sentencia, tabla, SQLSTATE, disparador). Las de `explosion_presupuesto` y el `INSERT` de la copia las
# rechaza el disparador de inmutabilidad (`IN001`); el `UPDATE` y el `DELETE` de la copia, el privilegio
# (el rol de aplicación solo tiene `SELECT` e `INSERT` sobre `linea_base_concepto`).
_SENTENCIAS_SOBRE_LAS_COPIAS: dict[str, tuple[str, str, str, str | None]] = {
    "insertar_copia": (
        "INSERT INTO linea_base_concepto (id, linea_base_id, partida_concepto_id, codigo, cantidad, "
        "precio_unitario, importe) "
        "VALUES (gen_random_uuid(), :linea_base, :aparicion, 'X-1', 1, 1, 1)",
        "linea_base_concepto",
        "IN001",
        "trg_linea_base_concepto_inmutable",
    ),
    "insertar_renglon": (
        "INSERT INTO explosion_presupuesto (id, linea_base_id, tipo_partida_id, insumo_id, "
        "cantidad_presupuestada, rendimiento_congelado, costo_unitario, importe_venta) "
        "VALUES (gen_random_uuid(), :linea_base, :enchapes, :insumo, 1, 1, 1, 1)",
        "explosion_presupuesto",
        "IN001",
        "trg_explosion_presupuesto_inmutable",
    ),
    "actualizar_renglon": (
        "UPDATE explosion_presupuesto SET cantidad_presupuestada = 999 WHERE id = :renglon",
        "explosion_presupuesto",
        "IN001",
        "trg_explosion_presupuesto_inmutable",
    ),
    "borrar_renglon": (
        "DELETE FROM explosion_presupuesto WHERE id = :renglon",
        "explosion_presupuesto",
        "IN001",
        "trg_explosion_presupuesto_inmutable",
    ),
    "actualizar_copia": (
        "UPDATE linea_base_concepto SET cantidad = 999 WHERE id = :copia",
        "linea_base_concepto",
        "42501",
        None,
    ),
    "borrar_copia": (
        "DELETE FROM linea_base_concepto WHERE id = :copia",
        "linea_base_concepto",
        "42501",
        None,
    ),
}


def _valor(base: Base, consulta: LiteralString, *parametros: object) -> Any:
    """La primera columna de la primera fila; la prueba exige que exista."""
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None, consulta
    return fila[0]


@pytest.mark.parametrize("caso", list(_SENTENCIAS_SOBRE_LAS_COPIAS))
def test_hdu001_esc18_el_motor_rechaza_tocar_las_copias(
    caso: str,
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    motor_aplicacion: Engine,
    congelado_en_doce: Callable[[], Congelado],
) -> None:
    """HDU-001 esc. 18 · TC-B07 · CA-B5 · RN-01 — sobre las copias del congelado real el motor rechaza y nada cambia.

    Con el rol de aplicación: `INSERT` en las dos tablas y `UPDATE`/`DELETE` en `explosion_presupuesto`
    responden `IN001` del disparador; `UPDATE`/`DELETE` en `linea_base_concepto`, `42501` del privilegio.
    Ninguna fila de las dos tablas cambia. El `IN001`, traducido por `traducir_error_del_motor`, es el
    `409` `REGLA_NEGOCIO` `RN-01` con la tabla en el detalle; el `42501` no se traduce (`None`: se relanza
    y responde `500`, porque sería un error de programa y no una regla).
    """
    sentencia, tabla, sqlstate, disparador = _SENTENCIAS_SOBRE_LAS_COPIAS[caso]
    linea_base_id = congelado_en_doce().borrador.linea_base_id
    parametros = {
        "linea_base": linea_base_id,
        "aparicion": _valor(
            base,
            "SELECT partida_concepto_id FROM linea_base_concepto WHERE linea_base_id = %s LIMIT 1",
            linea_base_id,
        ),
        "copia": _valor(
            base,
            "SELECT id FROM linea_base_concepto WHERE linea_base_id = %s LIMIT 1",
            linea_base_id,
        ),
        "renglon": _valor(
            base,
            "SELECT id FROM explosion_presupuesto WHERE linea_base_id = %s LIMIT 1",
            linea_base_id,
        ),
        "insumo": _valor(
            base,
            "SELECT insumo_id FROM explosion_presupuesto WHERE linea_base_id = %s LIMIT 1",
            linea_base_id,
        ),
        "enchapes": _valor(base, "SELECT id FROM tipo_partida WHERE clave = %s", _ENCHAPES),
    }
    usados = {nombre: valor for nombre, valor in parametros.items() if f":{nombre}" in sentencia}
    antes = (
        base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
    )
    assert len(antes[0]) == 12
    assert len(antes[1]) == 2

    with pytest.raises(DBAPIError) as rechazo, Session(motor_aplicacion) as sesion:
        sesion.execute(text(sentencia), usados)

    error = rechazo.value
    original = cast("psycopg.Error", error.orig)
    assert original.sqlstate == sqlstate
    if disparador is not None:
        assert original.diag.table_name == tabla
        assert original.diag.constraint_name == disparador
    else:
        assert tabla in (original.diag.message_primary or ""), "El 42501 nombra la tabla"
    assert (
        base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        base.filas("SELECT * FROM explosion_presupuesto ORDER BY id"),
    ) == antes, "Ninguna fila de las copias cambia"
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", linea_base_id) == [
        ("CONGELADA",)
    ]

    ruta = f"/api/v1/lineas-base/{linea_base_id}/congelacion"
    traducido = traducir_error_del_motor(
        error,
        ruta_reintento=ruta,
        metodo_reintento="POST",
        roles_reintento=("DIRECTOR_PROYECTOS",),
        rechazo_vigente=lambda: pytest.fail("IN001 y 42501 no consultan la línea base vigente"),
    )
    if sqlstate == "IN001":
        assert isinstance(traducido, RechazoRegla)
        assert traducido.estado_http == 409
        assert traducido.cuerpo(ROLES_DP, CORRELACION) == {
            "tipo": "REGLA_NEGOCIO",
            "mensaje": MENSAJE_IN001,
            "regla": "RN-01",
            "detalle": {"tabla": tabla},
            "acciones": [],
            "correlacion_id": CORRELACION,
        }
    else:
        assert traducido is None, "42501 llega como 500: no se disfraza de regla"


# --------------------------------------------------------------------------- consulta de filas_explotables · CA-B1

ORDEN_DE_LAS_APARICIONES = "nivel.orden, area.id, partida.orden, partida.id, concepto.codigo"


class Empate(NamedTuple):
    """Un concepto con análisis en dos partidas de la misma área y el mismo `orden`."""

    apu_id: uuid.UUID
    partidas: tuple[uuid.UUID, uuid.UUID]


def _sembrar_apariciones_empatadas(entorno: Entorno) -> Empate:
    """Dos apariciones de `620040-A` que empatan en nivel, área, `partida.orden` y código de concepto.

    Solo las distingue `partida.id`. El concepto tiene un análisis con un insumo y un cargo, para que
    `filas_explotables` consulte también `apu_insumo` y `apu_cargo` con el `id` de ese análisis.
    """
    datos = entorno.datos
    area = datos.area(nivel_id=datos.nivel(obra_id=entorno.obra_id))
    concepto = datos.concepto(obra_id=entorno.obra_id, codigo="620040-A")
    apu = datos.apu(concepto_id=concepto)
    datos.apu_insumo(apu_id=apu, insumo_id=datos.insumo(codigo="PANEL-ORDEN"))
    datos.apu_cargo(apu_id=apu)
    primera = datos.partida(area_id=area, tipo_partida_id=entorno.tipo_muros, orden=1)
    segunda = datos.partida(area_id=area, tipo_partida_id=entorno.tipo_plafon, orden=1)
    datos.partida_concepto(concepto_id=concepto, partida_id=primera)
    datos.partida_concepto(concepto_id=concepto, partida_id=segunda)
    return Empate(apu_id=apu, partidas=(primera, segunda))


def _sentencias_de_filas_explotables(motor: Engine, obra_id: uuid.UUID) -> list[tuple[str, object]]:
    """Las sentencias SQL (con sus parámetros) que emite `filas_explotables`, tal como llegan al cursor."""
    capturadas: list[tuple[str, object]] = []

    def registrar(
        conexion: object,
        cursor: object,
        sentencia: str,
        parametros: object,
        contexto: object,
        ejecutar_muchas: bool,
    ) -> None:
        capturadas.append((" ".join(sentencia.split()), parametros))

    event.listen(motor, "before_cursor_execute", registrar)
    try:
        with Session(motor) as sesion:
            repositorio_linea_base.filas_explotables(sesion, obra_id)
    finally:
        event.remove(motor, "before_cursor_execute", registrar)
    return capturadas


def test_tkt017_cab01_filas_explotables_desempata_las_apariciones_por_partida_id(
    entorno: Entorno, motor_aplicacion: Engine
) -> None:
    """CA-B1 · RN-24 — el `ORDER BY` de las apariciones es total: `partida.id` desempata entre `partida.orden` y `concepto.codigo`.

    El orden de las filas que consume `explotar_filas` decide el orden de las causas de un rechazo y el
    de los renglones de la explosión. Con dos partidas de la misma área y el mismo `orden` que llevan el
    mismo concepto, `nivel.orden, area.id, partida.orden, concepto.codigo` empata y PostgreSQL devuelve
    el orden que le dé el plan. El orden en el resultado no se puede afirmar de forma estable (un plan
    secuencial devolvería el orden de inserción aun sin el desempate), así que se afirma la sentencia
    que sale al cursor, que es lo que garantiza el orden.
    """
    _sembrar_apariciones_empatadas(entorno)

    sentencias = _sentencias_de_filas_explotables(motor_aplicacion, entorno.obra_id)

    apariciones = [sentencia for sentencia, _ in sentencias if "FROM partida_concepto" in sentencia]
    assert len(apariciones) == 1, sentencias
    assert "ORDER BY " in apariciones[0], apariciones[0]
    assert apariciones[0].rsplit("ORDER BY ", 1)[1] == ORDEN_DE_LAS_APARICIONES


def test_tkt017_cab01_filas_explotables_no_repite_el_apu_en_los_in(
    entorno: Entorno, motor_aplicacion: Engine
) -> None:
    """CA-B1 · RN-24 — un concepto en dos partidas consulta sus insumos y cargos con su `apu_id` una sola vez.

    Las dos apariciones comparten análisis; el `IN` de `apu_insumo` y el de `apu_cargo` llevan el `id`
    del análisis una vez, no una por aparición. Se afirma sobre los parámetros que llegan al cursor.
    """
    empate = _sembrar_apariciones_empatadas(entorno)

    sentencias = _sentencias_de_filas_explotables(motor_aplicacion, entorno.obra_id)

    consultas = [
        (sentencia, parametros)
        for sentencia, parametros in sentencias
        if "FROM apu_insumo" in sentencia or "FROM apu_cargo" in sentencia
    ]
    assert len(consultas) == 2, sentencias
    for sentencia, parametros in consultas:
        valores = (
            parametros.values() if isinstance(parametros, Mapping) else cast("Any", parametros)
        )
        ids = [valor for valor in valores if isinstance(valor, uuid.UUID)]
        assert ids == [empate.apu_id], sentencia
