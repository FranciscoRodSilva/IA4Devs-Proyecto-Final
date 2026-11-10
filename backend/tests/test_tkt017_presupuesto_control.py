"""Captura del tope y lectura del presupuesto de control, fila C2 de TKT-017c (CA-C1 a CA-C7 · RN-03 · RN-04 · PA-03).

Cubre `TC-C03`, `TC-C07` a `TC-C10`, `TC-C13`, `TC-C15` a `TC-C17` y la parte de `TC-C01` que corresponde al
caso de uso (la API la completa C3), más el rechazo de `TC-C04` y `TC-C06` y el `TC-C12` a nivel de caso de uso.
Corre contra PostgreSQL migrado con `alembic upgrade head` y el rol de aplicación, por `capturar_tope` del
módulo `cimenta.presupuesto.aplicacion.presupuesto_control` y `listar_presupuesto_control` del módulo
`cimenta.presupuesto.aplicacion.consulta_linea_base`.

La línea base `CONGELADA` se siembra con cifras exactas (`herramientas/soporte_tkt017_control.py`): MUROS vende
`480000.0000` con sugerido `410000.0000`. Cada rechazo comprueba el contrato de error completo con
`error.cuerpo(roles, correlacion)` y que no cambió ninguna fila: ni el tope, ni la bitácora, ni la línea base.
La concurrencia (`TC-C16` y `TC-C17`) usa `threading.Barrier` y `pg_blocking_pids`, nunca un `sleep` fijo.

Rojo esperado de C2: el módulo `presupuesto_control` y `listar_presupuesto_control` aún no existen. Los tests los
importan al llamarlos, no al cargar el archivo, así que cada prueba falla por su cuenta (`ModuleNotFoundError` o
`AttributeError`) y la colección no se rompe.

Mutantes que este archivo debe poner en rojo: `M-C2` (`TC-C09`), `M-C3` (`TC-C08`), `M-C4` (`TC-C16` y
`TC-C17`), `M-C5` (`TC-C01`), `M-C6` (`TC-C03`) y `M-C14` (cuantización del tope).

Dos pruebas son anclajes de mutantes añadidos tras la fila C4 (mutación): nacen en verde, porque el
comportamiento ya existía y la mutación mostró que ninguna prueba lo afirmaba. Son
`test_tkt017_cac01_listar_control_de_una_congelada_ignora_partida_concepto_posterior` (`M-C5`) y
`test_hdu001_esc17_tope_con_mas_de_cuatro_decimales_se_cuantiza_antes_de_comparar` (`M-C14`).
"""

from __future__ import annotations

import functools
import importlib
import threading
import uuid
from collections.abc import Callable, Sequence
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.auditoria.interfaz import consultar_bitacora
from cimenta.identidad.interfaz import UsuarioResumen
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    NoEncontrado,
    ValidacionRechazada,
)
from herramientas.soporte_tkt017_control import (
    CIFRAS_CON_REDONDEO,
    LineaBaseSembrada,
    sembrar_congelada_con_cifras,
)
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Base, Contexto, Entorno, Hilo
from herramientas.tiempo_de_prueba import esperar_hasta
from tipos_base import Dinero

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba, SembrarUsuario

CORRELACION = "corr-tkt017-c2"
ROLES_DG = frozenset({"DIRECCION_GENERAL"})
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
MOTIVO_SUPERIOR = "Subcontrato de bastidor más caro"
MOTIVO_RECAPTURA = "Se subestimó el bastidor de los cubos de escalera"
MOTIVOS_AUSENTES = [None, "", "   "]

MENSAJE_SIN_CONGELADA = (
    "La línea base está en {estado}; el tope solo se captura sobre una línea base congelada."
)
MENSAJE_TOPE_SUPERIOR = (
    "El tope de {clave} supera su importe de venta; implicaría vender por debajo del costo tope."
)
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
MENSAJE_OBLIGATORIO = "El campo es obligatorio."

_SQL_CONTROL = (
    "SELECT importe_tope, importe_sugerido, capturado_por_id, capturado_en, actualizado_por_id, "
    "actualizado_en, motivo_ultimo_cambio FROM presupuesto_control WHERE id = %s"
)
_SQL_ASIENTOS = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
    "obra_id, datos_antes, datos_despues FROM bitacora ORDER BY ocurrido_en, accion::text"
)


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


@pytest.fixture
def contexto_espera_corta(motor_espera_corta: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El mismo contexto sobre `motor_espera_corta`: la sesión espera un bloqueo solo 200 ms."""
    return functools.cache(
        lambda: construir_contexto(
            proveedor_motor=lambda: motor_espera_corta, reloj=reloj_de_prueba
        )
    )


@pytest.fixture
def sembrada(entorno: Entorno) -> LineaBaseSembrada:
    """MUROS vende 480000.0000 con sugerido 410000.0000 y tope nulo; hay cuatro filas de control."""
    return sembrar_congelada_con_cifras(entorno)


@pytest.fixture
def direccion(entorno: Entorno) -> uuid.UUID:
    """Quien captura el tope: un usuario de Dirección General."""
    return entorno.datos.usuario()


@pytest.fixture
def otra_direccion(entorno: Entorno) -> uuid.UUID:
    """Otra persona de Dirección General, para distinguir quién capturó de quién recapturó."""
    return entorno.datos.usuario()


# --------------------------------------------------------------------------- los casos de uso bajo prueba


def _ruta(linea_base_id: uuid.UUID, tipo_partida_id: uuid.UUID) -> str:
    return f"/api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}"


def _capturar(
    ctx: ContextoPresupuesto,
    linea_base_id: uuid.UUID,
    tipo_partida_id: uuid.UUID,
    importe_tope: str,
    *,
    usuario_id: uuid.UUID,
    motivo: str | None = None,
    confirmar: bool = False,
) -> uuid.UUID:
    """La firma exacta de «Aplicación» en el diseño. El módulo se importa aquí, al llamarla."""
    modulo = importlib.import_module("cimenta.presupuesto.aplicacion.presupuesto_control")
    return cast(
        "uuid.UUID",
        modulo.capturar_tope(
            ctx,
            linea_base_id=linea_base_id,
            tipo_partida_id=tipo_partida_id,
            importe_tope=Dinero(importe_tope),
            motivo=motivo,
            confirmar_superior_a_venta=confirmar,
            usuario_id=usuario_id,
        ),
    )


def _listar(ctx: ContextoPresupuesto, linea_base_id: uuid.UUID) -> Sequence[Any]:
    modulo = importlib.import_module("cimenta.presupuesto.aplicacion.consulta_linea_base")
    return cast("Sequence[Any]", modulo.listar_presupuesto_control(ctx, linea_base_id))


def _capturar_muros(
    ctx: ContextoPresupuesto,
    sembrada: LineaBaseSembrada,
    importe_tope: str,
    *,
    usuario_id: uuid.UUID,
    motivo: str | None = None,
    confirmar: bool = False,
) -> uuid.UUID:
    return _capturar(
        ctx,
        sembrada.linea_base_id,
        sembrada.tipos["MUROS"],
        importe_tope,
        usuario_id=usuario_id,
        motivo=motivo,
        confirmar=confirmar,
    )


# --------------------------------------------------------------------------- lecturas y comparaciones


def _estado_completo(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: la foto del soporte más las obras, las líneas base, los
    controles y la bitácora completos, con todas sus columnas."""
    return {
        "foto": base.foto(),
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "copias": base.filas("SELECT * FROM linea_base_concepto ORDER BY id"),
        "controles": base.filas("SELECT * FROM presupuesto_control ORDER BY id"),
        "bitacora": base.filas("SELECT * FROM bitacora ORDER BY id"),
    }


def _rechazo(base: Base, intento: Callable[[], object]) -> ErrorContrato:
    """Ejecuta el intento, espera un `ErrorContrato` y comprueba que no cambió ninguna fila."""
    antes = _estado_completo(base)
    with pytest.raises(ErrorContrato) as rechazo:
        intento()
    assert _estado_completo(base) == antes, "Un rechazo no escribe: ninguna fila ni asiento cambió"
    return rechazo.value


def _control(base: Base, control_id: uuid.UUID) -> tuple[Any, ...]:
    filas = base.filas(_SQL_CONTROL, control_id)
    assert len(filas) == 1
    return filas[0]


def _otros_controles(base: Base, control_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Las demás filas de control, completas: capturar un tipo no toca los otros tres."""
    return base.filas("SELECT * FROM presupuesto_control WHERE id <> %s ORDER BY id", control_id)


def _asientos(base: Base) -> list[tuple[Any, ...]]:
    return base.filas(_SQL_ASIENTOS)


def _afirmar_validacion_de_motivo(error: ErrorContrato) -> None:
    assert isinstance(error, ValidacionRechazada)
    assert error.estado_http == 422
    assert [e.como_dict() for e in error.errores] == [
        {"campo": "motivo", "codigo": "OBLIGATORIO", "mensaje": MENSAJE_OBLIGATORIO}
    ]
    assert error.cuerpo(ROLES_DG, CORRELACION) == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 1 campo inválido.",
        "errores": [{"campo": "motivo", "codigo": "OBLIGATORIO", "mensaje": MENSAJE_OBLIGATORIO}],
        "correlacion_id": CORRELACION,
    }


def _cuerpo_tope_superior(
    sembrada: LineaBaseSembrada, *, con_accion: bool, importe_tope: str
) -> dict[str, object]:
    return {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_TOPE_SUPERIOR.format(clave="MUROS"),
        "codigo": "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR",
        "detalle": {
            "tipo_partida": "MUROS",
            "importe_venta": "480000.0000",
            "importe_tope": importe_tope,
        },
        "acciones": (
            [
                {
                    "clave": "CONFIRMAR_TOPE_SUPERIOR",
                    "metodo": "PUT",
                    "ruta": _ruta(sembrada.linea_base_id, sembrada.tipos["MUROS"]),
                }
            ]
            if con_accion
            else []
        ),
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-C03 · CA-C2


def test_hdu001_esc15_primera_captura(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    sesion_bd: Session,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 15 · TC-C03 · CA-C2 · RN-03 · PA-03 — la primera captura guarda tope, quién y cuándo; asienta CREAR sin regla.

    MUROS vende `480000.0000`, sugerido `410000.0000`, tope nulo. Dirección captura `450000.0000` sin
    motivo: la fila guarda el tope, `capturado_por_id` y `capturado_en` (el reloj del contexto); el
    sugerido no cambia; los otros tres controles no se tocan. El asiento es `CREAR` de la fila de control,
    sin regla de negocio y con el valor capturado: una consulta por `RN-03` no lo devuelve (M-C6).
    """
    control = sembrada.controles["MUROS"]
    ajenos_antes = _otros_controles(base, control)

    devuelto = _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)

    assert devuelto == control
    assert _control(base, control) == (
        "450000.0000",
        "410000.0000",
        direccion,
        reloj_de_prueba.ahora,
        None,
        None,
        None,
    )
    assert _otros_controles(base, control) == ajenos_antes
    assert _asientos(base) == [
        (
            "CREAR",
            "presupuesto_control",
            control,
            direccion,
            reloj_de_prueba.ahora,
            None,
            None,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "450000.0000"},
        )
    ]
    assert consultar_bitacora(sesion_bd, regla_negocio="RN-03").total == 0
    assert consultar_bitacora(sesion_bd, entidad_tipo="presupuesto_control").total == 1


@pytest.mark.parametrize("motivo", ["", "   "])
def test_hdu001_esc15_primera_captura_con_motivo_en_blanco(
    motivo: str,
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 15 · CA-C2 · RN-03 — la primera captura no exige motivo: uno vacío o en blanco se admite como si no se hubiera enviado.

    Un formulario que manda `motivo: ""` o `"   "` en una primera captura válida (tope de `450000.0000`, por
    debajo de la venta de `480000.0000`) no recibe `OBLIGATORIO`: el motivo en blanco no es un motivo. La fila
    guarda el tope con `motivo_ultimo_cambio` nulo y el asiento `CREAR` queda sin regla y **sin motivo**
    (`asentar` rechaza un texto en blanco, así que el caso de uso debe pasarle `None`). La recaptura y el tope
    superior confirmado con el motivo en blanco siguen siendo `OBLIGATORIO` (pruebas de `TC-C06` y `TC-C12`).
    """
    control = sembrada.controles["MUROS"]

    devuelto = _capturar_muros(
        contexto(), sembrada, "450000.0000", usuario_id=direccion, motivo=motivo
    )

    assert devuelto == control
    assert _control(base, control) == (
        "450000.0000",
        "410000.0000",
        direccion,
        reloj_de_prueba.ahora,
        None,
        None,
        None,
    )
    assert _asientos(base) == [
        (
            "CREAR",
            "presupuesto_control",
            control,
            direccion,
            reloj_de_prueba.ahora,
            None,
            None,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "450000.0000"},
        )
    ]


# --------------------------------------------------------------------------- TC-C04 a nivel de caso de uso · CA-C3


def test_hdu001_esc17_tope_superior_sin_confirmar(
    base: Base, contexto: Contexto, sembrada: LineaBaseSembrada, direccion: uuid.UUID
) -> None:
    """HDU-001 esc. 17 · TC-C04 · CA-C3 · RN-03 — un tope de 500000.0000 contra una venta de 480000.0000 se detiene.

    `409` `CONFLICTO` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` con el tipo, el importe de venta del tipo (no
    el de la línea base, que es `600000.0000`) y el tope como cadenas de cuatro decimales. La acción
    `CONFIRMAR_TOPE_SUPERIOR` (`PUT` a la misma ruta) solo la ve Dirección General. Ni tope ni asiento.
    """
    error = _rechazo(
        base,
        lambda: _capturar_muros(contexto(), sembrada, "500000.0000", usuario_id=direccion),
    )

    assert isinstance(error, ConflictoEstado)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DG, CORRELACION) == _cuerpo_tope_superior(
        sembrada, con_accion=True, importe_tope="500000.0000"
    )
    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_tope_superior(
        sembrada, con_accion=False, importe_tope="500000.0000"
    ), "El Director de Proyectos no ve una acción que le respondería 403"
    assert _control(base, sembrada.controles["MUROS"])[0] is None
    assert _asientos(base) == []


def test_hdu001_esc17_recaptura_superior_a_la_venta_sin_confirmar(
    base: Base, contexto: Contexto, sembrada: LineaBaseSembrada, direccion: uuid.UUID
) -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 — la recaptura por encima de la venta, aun con motivo, también exige confirmar.

    Con un tope previo de `450000.0000`, recapturar `500000.0000` con motivo pero sin confirmar responde
    el mismo `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` (la venta se compara con el tope nuevo, no con el
    anterior); el tope sigue en `450000.0000` y no hay asiento `RECAPTURAR`.
    """
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)

    error = _rechazo(
        base,
        lambda: _capturar_muros(
            contexto(),
            sembrada,
            "500000.0000",
            usuario_id=direccion,
            motivo=MOTIVO_RECAPTURA,
        ),
    )

    assert isinstance(error, ConflictoEstado)
    assert error.cuerpo(ROLES_DG, CORRELACION) == _cuerpo_tope_superior(
        sembrada, con_accion=True, importe_tope="500000.0000"
    )
    assert _control(base, sembrada.controles["MUROS"])[0] == "450000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR"]


@pytest.mark.parametrize("motivo", MOTIVOS_AUSENTES)
def test_hdu001_esc17_confirmacion_sin_motivo(
    motivo: str | None,
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
) -> None:
    """HDU-001 esc. 17 · TC-C06 · CA-C3 · RN-04 — confirmar que el tope supera la venta sin motivo es `422` `OBLIGATORIO`.

    Nulo, vacío y en blanco dan el mismo error en el campo `motivo`; el tope sigue nulo y no hay asiento.
    """
    error = _rechazo(
        base,
        lambda: _capturar_muros(
            contexto(),
            sembrada,
            "500000.0000",
            usuario_id=direccion,
            motivo=motivo,
            confirmar=True,
        ),
    )

    _afirmar_validacion_de_motivo(error)
    assert _control(base, sembrada.controles["MUROS"])[0] is None
    assert _asientos(base) == []


def test_hdu001_esc17_tope_superior_confirmado(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 17 · TC-C07 · CA-C3 · RN-03 — con confirmación y motivo el tope de 500000.0000 se guarda.

    El motivo queda en la propia fila (`motivo_ultimo_cambio`) y en el asiento `CREAR` de esa primera
    captura, que sigue sin regla de negocio.
    """
    control = sembrada.controles["MUROS"]

    _capturar_muros(
        contexto(),
        sembrada,
        "500000.0000",
        usuario_id=direccion,
        motivo=MOTIVO_SUPERIOR,
        confirmar=True,
    )

    assert _control(base, control) == (
        "500000.0000",
        "410000.0000",
        direccion,
        reloj_de_prueba.ahora,
        None,
        None,
        MOTIVO_SUPERIOR,
    )
    assert _asientos(base) == [
        (
            "CREAR",
            "presupuesto_control",
            control,
            direccion,
            reloj_de_prueba.ahora,
            None,
            MOTIVO_SUPERIOR,
            entorno.obra_id,
            None,
            {"tipo_partida": "MUROS", "importe_tope": "500000.0000"},
        )
    ]


def test_hdu001_esc17_tope_igual_a_la_venta_no_pide_confirmacion(
    base: Base, contexto: Contexto, sembrada: LineaBaseSembrada, direccion: uuid.UUID
) -> None:
    """HDU-001 esc. 17 · TC-C05 · CA-C3 · RN-03 — un tope igual al importe de venta del tipo no supera nada (borde, M-C1).

    `480000.0000` sin confirmar y sin motivo se guarda; es una primera captura (`CREAR`).
    """
    control = sembrada.controles["MUROS"]

    _capturar_muros(contexto(), sembrada, "480000.0000", usuario_id=direccion)

    assert _control(base, control)[0] == "480000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR"]


def test_hdu001_esc17_tope_con_mas_de_cuatro_decimales_se_cuantiza_antes_de_comparar(
    base: Base, contexto: Contexto, sembrada: LineaBaseSembrada, direccion: uuid.UUID
) -> None:
    """HDU-001 esc. 17 · CA-C3 · RN-03 · PA-23 — el tope se cuantiza a cuatro decimales (`ROUND_HALF_UP`) antes de compararlo con la venta (M-C14).

    Anclaje de mutante: nace en verde, porque el comportamiento ya existe. La API solo admite cuatro
    decimales, pero el caso de uso recibe un `Dinero`: `480000.00005` pasa a `480000.0001`, supera la
    venta de `480000.0000` y exige confirmar, con el tope cuantizado en el detalle; `480000.00004` pasa a
    `480000.0000`, no supera nada y se guarda sin confirmar con la escala de la columna.
    """
    control = sembrada.controles["MUROS"]

    error = _rechazo(
        base,
        lambda: _capturar_muros(contexto(), sembrada, "480000.00005", usuario_id=direccion),
    )

    assert isinstance(error, ConflictoEstado)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DG, CORRELACION) == _cuerpo_tope_superior(
        sembrada, con_accion=True, importe_tope="480000.0001"
    )
    assert _control(base, control)[0] is None

    _capturar_muros(contexto(), sembrada, "480000.00004", usuario_id=direccion)

    assert _control(base, control)[0] == "480000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR"]


# --------------------------------------------------------------------------- TC-C08 a TC-C10 · CA-C4


def test_hdu001_esc22_recaptura_del_tope(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    otra_direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
    sesion_bd: Session,
    entorno: Entorno,
) -> None:
    """HDU-001 esc. 22 · TC-C08 · CA-C4 · RN-03 · RN-04 — recapturar 450000.0000 a 470000.0000 deja quién, cuándo y por qué.

    La fila conserva quién capturó y cuándo, y fija quién recapturó (otra persona), cuándo (un día
    después) y el motivo. El asiento es `RECAPTURAR` con `RN-03`, el valor anterior, el nuevo y el motivo,
    y aparece en una consulta de la bitácora por `RN-03` (M-C3).
    """
    control = sembrada.controles["MUROS"]
    primera_vez = reloj_de_prueba.ahora
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    reloj_de_prueba.avanzar(timedelta(days=1))

    devuelto = _capturar_muros(
        contexto(),
        sembrada,
        "470000.0000",
        usuario_id=otra_direccion,
        motivo=MOTIVO_RECAPTURA,
    )

    assert devuelto == control
    assert _control(base, control) == (
        "470000.0000",
        "410000.0000",
        direccion,
        primera_vez,
        otra_direccion,
        reloj_de_prueba.ahora,
        MOTIVO_RECAPTURA,
    )
    recapturas = [fila for fila in _asientos(base) if fila[0] == "RECAPTURAR"]
    assert recapturas == [
        (
            "RECAPTURAR",
            "presupuesto_control",
            control,
            otra_direccion,
            reloj_de_prueba.ahora,
            "RN-03",
            MOTIVO_RECAPTURA,
            entorno.obra_id,
            {"importe_tope": "450000.0000"},
            {"importe_tope": "470000.0000"},
        )
    ]
    por_regla = consultar_bitacora(sesion_bd, regla_negocio="RN-03")
    assert por_regla.total == 1
    assert [(a.accion.value, a.entidad_id) for a in por_regla.elementos] == [
        ("RECAPTURAR", control)
    ]


def test_hdu001_esc22_bajar_el_tope_es_recaptura(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 22 · TC-C09 · CA-C4 · RN-03 — bajar el tope a 440000.0000 también es `RECAPTURAR` con `RN-03` (M-C2)."""
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    reloj_de_prueba.avanzar(timedelta(hours=1))

    _capturar_muros(
        contexto(), sembrada, "440000.0000", usuario_id=direccion, motivo=MOTIVO_RECAPTURA
    )

    assert _control(base, control)[0] == "440000.0000"
    recapturas = [fila for fila in _asientos(base) if fila[0] == "RECAPTURAR"]
    assert [(f[5], f[8], f[9]) for f in recapturas] == [
        ("RN-03", {"importe_tope": "450000.0000"}, {"importe_tope": "440000.0000"})
    ]


def test_hdu001_esc22_mismo_valor_deja_otro_asiento(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 22 · TC-C10 · CA-C4 · RN-03 — recapturar 470000.0000 de nuevo deja un segundo `RECAPTURAR`."""
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    for _ in range(2):
        reloj_de_prueba.avanzar(timedelta(hours=1))
        _capturar_muros(
            contexto(),
            sembrada,
            "470000.0000",
            usuario_id=direccion,
            motivo=MOTIVO_RECAPTURA,
        )

    assert _control(base, control)[0] == "470000.0000"
    recapturas = [fila for fila in _asientos(base) if fila[0] == "RECAPTURAR"]
    assert [(f[5], f[8], f[9]) for f in recapturas] == [
        ("RN-03", {"importe_tope": "450000.0000"}, {"importe_tope": "470000.0000"}),
        ("RN-03", {"importe_tope": "470000.0000"}, {"importe_tope": "470000.0000"}),
    ]


@pytest.mark.parametrize("motivo", MOTIVOS_AUSENTES)
def test_hdu001_esc23_recaptura_sin_motivo(
    motivo: str | None,
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
) -> None:
    """HDU-001 esc. 23 · TC-C12 · CA-C5 · RN-04 — recapturar sin motivo es `422` `OBLIGATORIO`; el tope y los asientos no cambian.

    Con el tope en `450000.0000`, una recaptura dentro de la venta (sin confirmación que exigir) y sin
    motivo —nulo, vacío o en blanco— se rechaza; la fila queda como estaba y no hay ningún `RECAPTURAR`.
    """
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    fila_antes = _control(base, control)

    error = _rechazo(
        base,
        lambda: _capturar_muros(
            contexto(), sembrada, "470000.0000", usuario_id=direccion, motivo=motivo
        ),
    )

    _afirmar_validacion_de_motivo(error)
    assert _control(base, control) == fila_antes
    assert fila_antes[0] == "450000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR"]


# --------------------------------------------------------------------------- TC-C13 y TC-C15 · CA-C6


@pytest.mark.parametrize("estado", ["BORRADOR", "SUPERSEDIDA"])
def test_tkt017_cac06_linea_base_en_borrador(
    estado: str,
    base: Base,
    contexto: Contexto,
    entorno: Entorno,
    direccion: uuid.UUID,
) -> None:
    """TC-C13 · CA-C6 esc. 1 · RN-03 — solo se captura el tope sobre una línea base congelada.

    Una línea base en `BORRADOR` o `SUPERSEDIDA` responde `409` `CONFLICTO` `SIN_LINEA_BASE_CONGELADA`
    con su estado en el mensaje y en el detalle. La línea tiene su fila de control, para que un caso de
    uso que no comprobara el estado sí pudiera escribir; no se escribe nada.
    """
    datos = entorno.datos
    linea_base = datos.linea_base(estado=estado, obra_id=entorno.obra_id, version=1)
    tipo = entorno.tipo_muros
    datos.control(linea_base_id=linea_base, tipo_partida_id=tipo)

    error = _rechazo(
        base,
        lambda: _capturar(contexto(), linea_base, tipo, "100.0000", usuario_id=direccion),
    )

    assert isinstance(error, ConflictoEstado)
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DG, CORRELACION) == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_SIN_CONGELADA.format(estado=estado),
        "codigo": "SIN_LINEA_BASE_CONGELADA",
        "detalle": {"linea_base_id": str(linea_base), "estado": estado},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert base.filas("SELECT importe_tope FROM presupuesto_control") == [(None,)]


def _linea_base_inexistente(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), entorno.tipo_muros


def _tipo_inexistente(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return sembrar_congelada_con_cifras(entorno).linea_base_id, uuid.uuid4()


def _congelada_sin_control(entorno: Entorno) -> tuple[uuid.UUID, uuid.UUID]:
    return entorno.sembrar_congelada(), entorno.tipo_muros


@pytest.mark.parametrize(
    ("preparar", "recurso", "mensaje"),
    [
        pytest.param(
            _linea_base_inexistente, "linea_base", "La línea base no existe.", id="linea_base"
        ),
        pytest.param(
            _tipo_inexistente, "tipo_partida", "El tipo de partida no existe.", id="tipo_partida"
        ),
        pytest.param(
            _congelada_sin_control,
            "presupuesto_control",
            "La línea base no tiene presupuesto de control para ese tipo de partida.",
            id="presupuesto_control",
        ),
    ],
)
def test_tkt017_cac06_tipo_o_linea_base_inexistente(
    preparar: Callable[[Entorno], tuple[uuid.UUID, uuid.UUID]],
    recurso: str,
    mensaje: str,
    base: Base,
    contexto: Contexto,
    entorno: Entorno,
    direccion: uuid.UUID,
) -> None:
    """TC-C15 · CA-C6 esc. 3 — lo que no existe responde `NoEncontrado` con el recurso que falta.

    Línea base inexistente: `linea_base`. Tipo de partida inexistente en una línea base congelada con
    sus cuatro controles: `tipo_partida` (se comprueba antes de buscar la fila de control). Una congelada
    sin fila de control para ese tipo: `presupuesto_control`.
    """
    linea_base, tipo = preparar(entorno)

    error = _rechazo(
        base,
        lambda: _capturar(contexto(), linea_base, tipo, "100.0000", usuario_id=direccion),
    )

    assert isinstance(error, NoEncontrado)
    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DG, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": mensaje,
        "recurso": recurso,
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-C16 · CA-C7


def test_tkt017_cac07_recapturas_simultaneas(
    base: Base,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
    otra_direccion: uuid.UUID,
) -> None:
    """TC-C16 · CA-C7 esc. 1 · RN-03 — dos recapturas a la vez se aplican una tras otra, y la segunda parte de lo que dejó la primera.

    El tope es `450000.0000`; dos hilos, soltados por una `Barrier`, lo recapturan a `460000.0000` y a
    `470000.0000`. El bloqueo de la fila las serializa: hay dos asientos `RECAPTURAR` y el valor anterior
    del que quedó segundo es el valor nuevo del primero (sin bloqueo, los dos dirían `450000.0000`). El
    tope final es el del segundo. Qué hilo gana depende de quién llega primero, así que la prueba no lo fija.
    """
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    ctx = contexto()
    salida = threading.Barrier(2, timeout=LIMITE_DE_HILO)

    def recapturar(importe: str, usuario_id: uuid.UUID) -> Callable[[], uuid.UUID]:
        def correr() -> uuid.UUID:
            salida.wait()
            return _capturar_muros(
                ctx, sembrada, importe, usuario_id=usuario_id, motivo=MOTIVO_RECAPTURA
            )

        return correr

    hilos = [
        Hilo("A", recapturar("460000.0000", direccion)),
        Hilo("B", recapturar("470000.0000", otra_direccion)),
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.terminar()

    assert [hilo.error for hilo in hilos] == [None, None]
    assert [hilo.exito() for hilo in hilos] == [control, control]
    asientos = base.filas(
        "SELECT usuario_id, datos_antes, datos_despues, regla_negocio FROM bitacora "
        "WHERE accion = 'RECAPTURAR'"
    )
    assert len(asientos) == 2
    assert {fila[3] for fila in asientos} == {"RN-03"}
    primero = next(fila for fila in asientos if fila[1] == {"importe_tope": "450000.0000"})
    segundo = next(fila for fila in asientos if fila is not primero)
    assert segundo[1] == primero[2], "La segunda recaptura parte del valor que dejó la primera"
    assert {primero[2]["importe_tope"], segundo[2]["importe_tope"]} == {
        "460000.0000",
        "470000.0000",
    }
    assert {primero[0], segundo[0]} == {direccion, otra_direccion}
    assert base.filas(
        "SELECT importe_tope, actualizado_por_id FROM presupuesto_control WHERE id = %s", control
    ) == [(segundo[2]["importe_tope"], segundo[0])]


# --------------------------------------------------------------------------- TC-C17 · CA-C7


def _alguien_espera_el_control(base: Base) -> Callable[[], bool]:
    """La condición de `esperar_hasta`: una sesión detenida en `SELECT ... FROM presupuesto_control ... FOR UPDATE`."""

    def espera() -> bool:
        fila = base.conexion.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND cardinality(pg_blocking_pids(pid)) > 0 "
            "AND query ILIKE '%FROM presupuesto_control%FOR UPDATE%'"
        ).fetchone()
        assert fila is not None
        return bool(fila[0])

    return espera


_SQL_RETENER_CONTROL = "SELECT id FROM presupuesto_control WHERE linea_base_id = %s AND tipo_partida_id = %s FOR UPDATE"


def test_tkt017_cac07_recaptura_espera_el_bloqueo(
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
) -> None:
    """TC-C17 · CA-C7 esc. 2 · RN-03 · ADR-004 — mientras otra sesión tiene la fila de control, la recaptura espera y termina al liberarla.

    La sesión retenedora toma la fila con `SELECT ... FOR UPDATE`. La recaptura queda detenida en su
    propio `SELECT ... FOR UPDATE` (`pg_blocking_pids`, sin pausa fija) y no escribe nada mientras espera
    (M-C4); al liberar, termina y deja el tope y su asiento.
    """
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    ctx = contexto()
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    retenedor.execute(_SQL_RETENER_CONTROL, (sembrada.linea_base_id, sembrada.tipos["MUROS"]))
    hilo = Hilo(
        "A",
        lambda: _capturar_muros(
            ctx, sembrada, "470000.0000", usuario_id=direccion, motivo=MOTIVO_RECAPTURA
        ),
    )
    try:
        hilo.start()
        espera = esperar_hasta(_alguien_espera_el_control(base), 5.0)
        assert espera, f"La recaptura no quedó esperando el bloqueo de la fila: {hilo.error!r}"
        assert hilo.is_alive()
        assert _control(base, control)[0] == "450000.0000"
        assert [fila[0] for fila in _asientos(base)] == ["CREAR"]
    finally:
        retenedor.rollback()
        hilo.terminar()

    assert hilo.error is None, hilo.error
    assert hilo.exito() == control
    assert _control(base, control)[0] == "470000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR", "RECAPTURAR"]


def test_tkt017_cac07_recaptura_con_bloqueo_vencido(
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    contexto: Contexto,
    contexto_espera_corta: Contexto,
    sembrada: LineaBaseSembrada,
    direccion: uuid.UUID,
) -> None:
    """TC-C17 · CA-C7 esc. 2 · RNF-16 · ADR-004 — si venció la espera, `409` `CONCURRENCIA` con `REINTENTAR` y sin asiento.

    Con `lock_timeout` de 200 ms y la fila retenida por otra sesión, el contrato completo es
    `BLOQUEO_VENCIDO` con `espera_maxima_ms` 5000 (el `lock_timeout` del rol), la cabecera
    `Retry-After: 1` y la acción `REINTENTAR` (`PUT` a la ruta de esa captura) aun para Dirección General.
    El tope sigue en `450000.0000` y la bitácora no cambia.
    """
    control = sembrada.controles["MUROS"]
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=direccion)
    ctx = contexto_espera_corta()
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    antes = _estado_completo(base)
    try:
        retenedor.execute(_SQL_RETENER_CONTROL, (sembrada.linea_base_id, sembrada.tipos["MUROS"]))
        with pytest.raises(ErrorContrato) as vencido:
            _capturar_muros(
                ctx, sembrada, "470000.0000", usuario_id=direccion, motivo=MOTIVO_RECAPTURA
            )
    finally:
        retenedor.rollback()

    error = vencido.value
    assert isinstance(error, ConcurrenciaVencida), error
    assert error.estado_http == 409
    assert error.cabeceras() == {"Retry-After": "1"}
    assert error.cuerpo(ROLES_DG, CORRELACION) == {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [
            {
                "clave": "REINTENTAR",
                "metodo": "PUT",
                "ruta": _ruta(sembrada.linea_base_id, sembrada.tipos["MUROS"]),
            }
        ],
        "correlacion_id": CORRELACION,
    }
    assert _estado_completo(base) == antes, "La recaptura vencida no escribe nada"
    assert _control(base, control)[0] == "450000.0000"
    assert [fila[0] for fila in _asientos(base)] == ["CREAR"]


# --------------------------------------------------------------------------- lectura · TC-C01 a nivel de caso de uso


def test_hdu001_esc15_listar_presupuesto_control(
    base: Base, contexto: Contexto, entorno: Entorno
) -> None:
    """HDU-001 esc. 15 · TC-C01 · CA-C1 · PA-03 — cuatro filas por tipo, con la venta del tipo, el sugerido y el tope nulo.

    El importe de venta del tipo es la suma de los importes **ya cuantizados** de sus copias congeladas:
    PLAFONES tiene dos apariciones de `0.5000 × 0.0001`, cada una cuantizada a `0.0001`, y vale `0.0002`
    (sumar sin cuantizar daría `0.0001`). Las cuatro suman exactamente `linea_base.importe_venta`. Las filas
    salen por `tipo_partida.id`, con el tope y quién lo capturó en nulo.
    """
    sembrada = sembrar_congelada_con_cifras(entorno, CIFRAS_CON_REDONDEO)

    filas = _listar(contexto(), sembrada.linea_base_id)

    tipos = base.filas("SELECT id, clave, nombre FROM tipo_partida ORDER BY id")
    assert len(tipos) == 4
    assert [
        (f.tipo_partida.id, f.tipo_partida.clave, f.tipo_partida.nombre) for f in filas
    ] == tipos
    assert {f.tipo_partida.clave: f.importe_venta.serializar() for f in filas} == {
        "MUROS": "480000.0000",
        "PLAFONES_Y_CAJILLOS": "0.0002",
        "ENCHAPES": "12345.6789",
        "GENERALES": "0.0000",
    }
    assert {f.tipo_partida.clave: f.importe_sugerido.serializar() for f in filas} == {
        "MUROS": "410000.0000",
        "PLAFONES_Y_CAJILLOS": "0.0001",
        "ENCHAPES": "10000.0000",
        "GENERALES": "0.0000",
    }
    suma = sum((f.importe_venta.valor for f in filas), start=Decimal("0.0000"))
    assert base.filas(
        "SELECT importe_venta FROM linea_base WHERE id = %s", sembrada.linea_base_id
    ) == [(str(suma),)]
    assert str(suma) == "492345.6791"
    assert [
        (f.importe_tope, f.capturado_por, f.capturado_en, f.actualizado_por, f.actualizado_en)
        for f in filas
    ] == [(None, None, None, None, None)] * 4
    assert {f.motivo_ultimo_cambio for f in filas} == {None}


def test_tkt017_cac01_listar_control_de_una_congelada_ignora_partida_concepto_posterior(
    base: Base, contexto: Contexto, entorno: Entorno
) -> None:
    """TC-C01 · CA-C1 · M-C5 — tras congelar, cambiar `partida_concepto` no mueve el importe de venta de ningún tipo.

    Anclaje de mutante: nace en verde, porque el comportamiento ya existe. El rol de aplicación sí puede
    modificar `partida_concepto`; la línea base congelada no puede enterarse. La venta por tipo sigue
    siendo la suma de las copias ya cuantizadas (`0.0002` en PLAFONES, que sumado sin cuantizar o desde
    `partida_concepto` daría otra cifra) y las cuatro siguen sumando `linea_base.importe_venta`.
    """
    sembrada = sembrar_congelada_con_cifras(entorno, CIFRAS_CON_REDONDEO)
    base.ejecutar(
        "UPDATE partida_concepto SET importe = 999999.0000 WHERE id IN "
        "(SELECT pc.id FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s)",
        entorno.obra_id,
    )
    assert base.filas("SELECT DISTINCT importe FROM partida_concepto") == [("999999.0000",)], (
        "El cambio de partida_concepto debe haberse aplicado, o la comprobación no demuestra nada"
    )

    filas = _listar(contexto(), sembrada.linea_base_id)

    assert {f.tipo_partida.clave: f.importe_venta.serializar() for f in filas} == {
        "MUROS": "480000.0000",
        "PLAFONES_Y_CAJILLOS": "0.0002",
        "ENCHAPES": "12345.6789",
        "GENERALES": "0.0000",
    }
    suma = sum((f.importe_venta.valor for f in filas), start=Decimal("0.0000"))
    assert base.filas(
        "SELECT importe_venta FROM linea_base WHERE id = %s", sembrada.linea_base_id
    ) == [(str(suma),)]
    assert str(suma) == "492345.6791"


def test_hdu001_esc15_listar_presupuesto_control_en_borrador_es_vacio(
    base: Base, contexto: Contexto, entorno: Entorno
) -> None:
    """HDU-001 esc. 15 · CA-C1 · P-9 — una línea base en `BORRADOR` no tiene presupuesto de control: la lectura es `[]`."""
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)

    assert list(_listar(contexto(), borrador.linea_base_id)) == []
    assert base.filas("SELECT count(*) FROM presupuesto_control") == [(0,)]


def test_hdu001_esc15_listar_presupuesto_control_linea_base_inexistente(contexto: Contexto) -> None:
    """HDU-001 esc. 15 · CA-C1 — una línea base que no existe responde `NoEncontrado` de la línea base."""
    with pytest.raises(NoEncontrado) as rechazo:
        _listar(contexto(), uuid.uuid4())

    assert rechazo.value.estado_http == 404
    assert rechazo.value.cuerpo(ROLES_DG, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": "La línea base no existe.",
        "recurso": "linea_base",
        "correlacion_id": CORRELACION,
    }


def test_tkt017_cac01_listar_presupuesto_control_nombra_a_quien_capturo_y_recapturo(
    contexto: Contexto,
    sembrada: LineaBaseSembrada,
    sembrar_usuario: SembrarUsuario,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-C1 · CA-C2 · CA-C4 — tras capturar y recapturar, la lectura trae a quién capturó y a quién recapturó, con su nombre.

    `capturado_por` y `actualizado_por` son `UsuarioResumen` con el `id` y el nombre (por la interfaz de
    identidad); el tope, los momentos y el motivo salen de la propia fila. Los otros tres tipos siguen
    con todo en nulo.
    """
    laura = sembrar_usuario(
        "laura.mendez@cimenta.test",
        "Contrasena-de-prueba-1",
        ("DIRECCION_GENERAL",),
        nombre="Laura Méndez",
    )
    mateo = sembrar_usuario(
        "mateo.rios@cimenta.test",
        "Contrasena-de-prueba-2",
        ("DIRECCION_GENERAL",),
        nombre="Mateo Ríos",
    )
    primera_vez = reloj_de_prueba.ahora
    _capturar_muros(contexto(), sembrada, "450000.0000", usuario_id=laura)
    reloj_de_prueba.avanzar(timedelta(days=1))
    _capturar_muros(contexto(), sembrada, "470000.0000", usuario_id=mateo, motivo=MOTIVO_RECAPTURA)

    filas = {f.tipo_partida.clave: f for f in _listar(contexto(), sembrada.linea_base_id)}

    muros = filas["MUROS"]
    assert muros.importe_tope.serializar() == "470000.0000"
    assert muros.importe_venta.serializar() == "480000.0000"
    assert muros.importe_sugerido.serializar() == "410000.0000"
    assert muros.capturado_por == UsuarioResumen(id=laura, nombre="Laura Méndez")
    assert muros.actualizado_por == UsuarioResumen(id=mateo, nombre="Mateo Ríos")
    assert muros.capturado_en == primera_vez
    assert muros.actualizado_en == reloj_de_prueba.ahora
    assert muros.motivo_ultimo_cambio == MOTIVO_RECAPTURA
    for clave in ("PLAFONES_Y_CAJILLOS", "ENCHAPES", "GENERALES"):
        ajena = filas[clave]
        assert (ajena.importe_tope, ajena.capturado_por, ajena.actualizado_por) == (None,) * 3
