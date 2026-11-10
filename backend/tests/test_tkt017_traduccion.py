"""Traducción de los `SQLSTATE` del motor, fila A5 de TKT-017 (TC-A24 · CA-B6 esc. 1 · ADR-031).

Cada caso provoca el error **real** con una `Session` del rol de aplicación sobre PostgreSQL migrado
con `alembic upgrade head` —nunca un error simulado— y pasa el `DBAPIError` que SQLAlchemy entrega al
traductor `cimenta.presupuesto.aplicacion.traduccion_motor.traducir_error_del_motor`. Se comprueba
el contrato de error completo con `cuerpo(roles, correlacion_id)`: `tipo`, `regla` o `codigo`,
`detalle`, `acciones` filtradas por rol y, en la concurrencia, la cabecera `Retry-After`.

`55P03` se provoca con `SET LOCAL lock_timeout = '200ms'` en la sesión que espera: la fixture
`motor_espera_corta` es de la fila A6c y no se usa aquí.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from cimenta.presupuesto.aplicacion.traduccion_motor import traducir_error_del_motor
from contrato_error.acciones import Accion
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    RechazoRegla,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import DatosPresupuesto

RUTA_DEL_CONGELADO = "/api/v1/lineas-base/11111111-1111-1111-1111-111111111111/congelacion"
RUTA_DE_LA_CAPTURA = "/api/v1/lineas-base/11111111-1111-1111-1111-111111111111/presupuesto-control"
ROLES_QUE_REINTENTAN = ("DIRECTOR_PROYECTOS",)
ROLES_DE_QUIEN_LLAMA = frozenset({"DIRECTOR_PROYECTOS"})
CORRELACION = "corr-tkt017-a5"

MENSAJE_IN001 = "La línea base congelada no se modifica."
MENSAJE_CONCURRENCIA = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
MENSAJE_TIEMPO_VENCIDO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."
MENSAJE_PREPARACION_ILEGIBLE = (
    "La preparación de la importación no se puede leer; la importación debe analizarse de nuevo."
)
MENSAJE_CONFLICTO = "La operación entra en conflicto con el estado actual de los datos."


# --------------------------------------------------------------------------- errores reales


def _provocar(motor: Engine, sentencia: Callable[[Session], object]) -> DBAPIError:
    """Ejecuta la sentencia en una `Session` del rol de aplicación y devuelve el error que lanza."""
    with pytest.raises(DBAPIError) as rechazo, Session(motor) as sesion:
        sentencia(sesion)
    return rechazo.value


def _insertar_copia_en_congelada(
    sesion: Session, linea_base_id: uuid.UUID, partida_concepto_id: uuid.UUID
) -> None:
    sesion.execute(
        text(
            "INSERT INTO linea_base_concepto (id, linea_base_id, partida_concepto_id, codigo, "
            "cantidad, precio_unitario, importe) "
            "VALUES (:id, :linea_base, :aparicion, '620099', 1, 1, 1)"
        ),
        {"id": uuid.uuid4(), "linea_base": linea_base_id, "aparicion": partida_concepto_id},
    )


def _in001_copia_de_concepto(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    congelada = datos.linea_base_con_copias(estado="CONGELADA")
    return _provocar(
        motor,
        lambda s: _insertar_copia_en_congelada(
            s, congelada.linea_base_id, congelada.partida_concepto_id
        ),
    )


def _in001_renglon_de_explosion(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    congelada = datos.linea_base_con_copias(estado="CONGELADA")
    insumo_nuevo = datos.insumo_nuevo()

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO explosion_presupuesto (id, linea_base_id, tipo_partida_id, insumo_id, "
                "cantidad_presupuestada, rendimiento_congelado, costo_unitario, importe_venta) "
                "VALUES (:id, :linea_base, :tipo, :insumo, 1, 1, 1, 1)"
            ),
            {
                "id": uuid.uuid4(),
                "linea_base": congelada.linea_base_id,
                "tipo": congelada.tipo_partida_id,
                "insumo": insumo_nuevo,
            },
        )

    return _provocar(motor, insertar)


def _segunda_congelada_de_la_obra(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    congelada = datos.linea_base_con_copias(estado="CONGELADA")
    usuario = datos.usuario()

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO linea_base (id, obra_id, version, estado, congelada_en, "
                "congelada_por_id, importe_venta, creado_por_id) "
                "VALUES (:id, :obra, 2, 'CONGELADA', now(), :usuario, 1, :usuario)"
            ),
            {"id": uuid.uuid4(), "obra": congelada.obra_id, "usuario": usuario},
        )

    return _provocar(motor, insertar)


def _insumo_con_codigo_repetido(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    existente = datos.insumo_nuevo()

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, "
                "creado_en_importacion) "
                "SELECT :id, codigo, 'Repetido', tipo, unidad, activo, creado_en_importacion "
                "FROM insumo WHERE id = :existente"
            ),
            {"id": uuid.uuid4(), "existente": existente},
        )

    return _provocar(motor, insertar)


def _tipo_de_partida_con_clave_repetida(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    existente = datos.tipo_partida(clave="MUROS", nombre="Muros")

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO tipo_partida (id, clave, nombre) "
                "SELECT :id, clave, 'Repetido' FROM tipo_partida WHERE id = :existente"
            ),
            {"id": uuid.uuid4(), "existente": existente},
        )

    return _provocar(motor, insertar)


def _bloqueo_vencido(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    """Una sesión congela sin confirmar; otra intenta copiar y su `FOR SHARE` espera 200 ms."""
    borrador = datos.linea_base_con_copias(estado="BORRADOR")
    with Session(motor) as congela:
        congela.execute(
            text("UPDATE linea_base SET estado = 'CONGELADA' WHERE id = :id"),
            {"id": borrador.linea_base_id},
        )

        def copiar(sesion: Session) -> None:
            sesion.execute(text("SET LOCAL lock_timeout = '200ms'"))
            _insertar_copia_en_congelada(
                sesion, borrador.linea_base_id, borrador.partida_concepto_id
            )

        error = _provocar(motor, copiar)
        congela.rollback()
    return error


def _tiempo_de_ejecucion_vencido(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    def dormir(sesion: Session) -> None:
        sesion.execute(text("SET LOCAL statement_timeout = '10ms'"))
        sesion.execute(text("SELECT pg_sleep(1)"))

    return _provocar(motor, dormir)


def _aparicion_con_partida_inexistente(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    concepto = datos.concepto(codigo="620310")

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO partida_concepto (id, concepto_id, partida_id, cantidad, "
                "precio_unitario, importe) VALUES (:id, :concepto, :partida, 1, 1, 1)"
            ),
            {"id": uuid.uuid4(), "concepto": concepto, "partida": uuid.uuid4()},
        )

    return _provocar(motor, insertar)


def _concepto_con_apariciones_que_se_borra(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    aparicion = datos.partida_concepto()

    def borrar(sesion: Session) -> None:
        sesion.execute(
            text(
                "DELETE FROM concepto WHERE id = "
                "(SELECT concepto_id FROM partida_concepto WHERE id = :aparicion)"
            ),
            {"aparicion": aparicion},
        )

    return _provocar(motor, borrar)


def _borrado_sin_privilegio(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    # E-2 de TKT-017: el rol de aplicación no tiene DELETE sobre las copias, aunque no borre nada.
    return _provocar(
        motor, lambda s: s.execute(text("DELETE FROM linea_base_concepto WHERE false"))
    )


def _costo_fuera_del_rango_de_la_columna(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    """10^10 cabe en `Dinero` (18,4) pero no en `apu.costo_material`, `numeric(14,4)`."""
    concepto = datos.concepto(codigo="620320")

    def insertar(sesion: Session) -> None:
        sesion.execute(
            text(
                "INSERT INTO apu (id, concepto_id, costo_material, costo_mano_obra, "
                "costo_directo, total_cargos, total_indirectos, precio_unitario) "
                "VALUES (:id, :concepto, CAST('10000000000.0000' AS numeric), 0, 0, 0, 0, 0)"
            ),
            {"id": uuid.uuid4(), "concepto": concepto},
        )

    return _provocar(motor, insertar)


def _uuid_ilegible(motor: Engine, datos: DatosPresupuesto) -> DBAPIError:
    return _provocar(motor, lambda s: s.execute(text("SELECT CAST('no-es-uuid' AS uuid)")))


# --------------------------------------------------------------------------- lo que se espera


@dataclass(frozen=True)
class Entorno:
    """Lo que la prueba le pasó al traductor y lo que sabe de la obra sembrada."""

    ruta: str
    metodo: str
    roles: tuple[str, ...]
    vigente: ConflictoEstado
    llamadas_a_rechazo_vigente: list[int]


def _cuerpo(resultado: ErrorContrato | None) -> dict[str, object]:
    assert resultado is not None, "El traductor devolvió None: debía traducir el error"
    return resultado.cuerpo(ROLES_DE_QUIEN_LLAMA, CORRELACION)


def _afirmar_rechazo_in001(tabla: str) -> Callable[[ErrorContrato | None, Entorno], None]:
    def afirmar(resultado: ErrorContrato | None, entorno: Entorno) -> None:
        assert isinstance(resultado, RechazoRegla)
        assert _cuerpo(resultado) == {
            "tipo": "REGLA_NEGOCIO",
            "mensaje": MENSAJE_IN001,
            "regla": "RN-01",
            "detalle": {"tabla": tabla},
            "acciones": [],
            "correlacion_id": CORRELACION,
        }
        assert resultado.estado_http == 409
        assert entorno.llamadas_a_rechazo_vigente == []

    return afirmar


def _afirmar_rechazo_de_la_vigente(resultado: ErrorContrato | None, entorno: Entorno) -> None:
    assert resultado is entorno.vigente, (
        "El traductor devuelve lo que devuelve rechazo_vigente, sin reconstruirlo"
    )
    assert entorno.llamadas_a_rechazo_vigente == [1]


def _afirmar_conflicto_por_restriccion(
    restriccion: str,
) -> Callable[[ErrorContrato | None, Entorno], None]:
    def afirmar(resultado: ErrorContrato | None, entorno: Entorno) -> None:
        assert isinstance(resultado, ConflictoEstado)
        cuerpo = _cuerpo(resultado)
        assert cuerpo == {
            "tipo": "CONFLICTO",
            "mensaje": MENSAJE_CONFLICTO,
            "codigo": "ESTADO_NO_PERMITE_OPERACION",
            "detalle": {"restriccion": restriccion},
            "acciones": [],
            "correlacion_id": CORRELACION,
        }
        assert resultado.estado_http == 409
        assert "regla" not in cuerpo, "Un CONFLICTO no lleva regla: no se inventa un RN-xx"
        assert entorno.llamadas_a_rechazo_vigente == []

    return afirmar


def _afirmar_concurrencia(
    codigo: str, espera_maxima_ms: int, mensaje: str
) -> Callable[[ErrorContrato | None, Entorno], None]:
    def afirmar(resultado: ErrorContrato | None, entorno: Entorno) -> None:
        assert isinstance(resultado, ConcurrenciaVencida)
        assert _cuerpo(resultado) == {
            "tipo": "CONCURRENCIA",
            "mensaje": mensaje,
            "codigo": codigo,
            "detalle": {"espera_maxima_ms": espera_maxima_ms},
            "acciones": [{"clave": "REINTENTAR", "metodo": entorno.metodo, "ruta": entorno.ruta}],
            "correlacion_id": CORRELACION,
        }
        assert resultado.estado_http == 409
        assert resultado.espera_maxima_ms == espera_maxima_ms
        assert resultado.reintentar_en_s == 1
        assert resultado.cabeceras() == {"Retry-After": "1"}
        assert resultado.acciones == (
            Accion("REINTENTAR", entorno.metodo, entorno.ruta, entorno.roles),
        )
        assert entorno.llamadas_a_rechazo_vigente == []

    return afirmar


def _afirmar_preparacion_ilegible(resultado: ErrorContrato | None, entorno: Entorno) -> None:
    assert isinstance(resultado, ConflictoEstado)
    assert _cuerpo(resultado) == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_PREPARACION_ILEGIBLE,
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert resultado.estado_http == 409
    assert entorno.llamadas_a_rechazo_vigente == []


def _afirmar_que_se_relanza(resultado: ErrorContrato | None, entorno: Entorno) -> None:
    assert resultado is None, "Un error ajeno al diseño no se traduce: el caso de uso lo relanza"
    assert entorno.llamadas_a_rechazo_vigente == []


Provocador = Callable[[Engine, "DatosPresupuesto"], DBAPIError]
Afirmador = Callable[[ErrorContrato | None, Entorno], None]


@dataclass(frozen=True)
class Caso:
    provocar: Provocador
    sqlstate: str
    restriccion: str | None
    afirmar: Afirmador


CASOS: dict[str, Caso] = {
    "in001_copia_de_concepto": Caso(
        _in001_copia_de_concepto,
        "IN001",
        "trg_linea_base_concepto_inmutable",
        _afirmar_rechazo_in001("linea_base_concepto"),
    ),
    "in001_renglon_de_explosion": Caso(
        _in001_renglon_de_explosion,
        "IN001",
        "trg_explosion_presupuesto_inmutable",
        _afirmar_rechazo_in001("explosion_presupuesto"),
    ),
    "23505_indice_de_congelada_vigente": Caso(
        _segunda_congelada_de_la_obra,
        "23505",
        "uq_linea_base_obra_id_congelada",
        _afirmar_rechazo_de_la_vigente,
    ),
    "23505_codigo_de_insumo": Caso(
        _insumo_con_codigo_repetido,
        "23505",
        "uq_insumo_codigo",
        _afirmar_conflicto_por_restriccion("uq_insumo_codigo"),
    ),
    "23505_clave_de_tipo_de_partida": Caso(
        _tipo_de_partida_con_clave_repetida,
        "23505",
        "uq_tipo_partida_clave",
        _afirmar_conflicto_por_restriccion("uq_tipo_partida_clave"),
    ),
    "55p03_bloqueo_vencido": Caso(
        _bloqueo_vencido,
        "55P03",
        None,
        _afirmar_concurrencia("BLOQUEO_VENCIDO", 5000, MENSAJE_CONCURRENCIA),
    ),
    "57014_tiempo_de_ejecucion_vencido": Caso(
        _tiempo_de_ejecucion_vencido,
        "57014",
        None,
        _afirmar_concurrencia("TIEMPO_EJECUCION_VENCIDO", 15000, MENSAJE_TIEMPO_VENCIDO),
    ),
    "23503_aparicion_con_partida_inexistente": Caso(
        _aparicion_con_partida_inexistente,
        "23503",
        "fk_partida_concepto_partida_id",
        _afirmar_conflicto_por_restriccion("fk_partida_concepto_partida_id"),
    ),
    "23001_concepto_con_apariciones": Caso(
        _concepto_con_apariciones_que_se_borra,
        "23001",
        "fk_partida_concepto_concepto_id",
        _afirmar_conflicto_por_restriccion("fk_partida_concepto_concepto_id"),
    ),
    "22003_valor_fuera_de_rango_de_la_columna": Caso(
        _costo_fuera_del_rango_de_la_columna, "22003", None, _afirmar_preparacion_ilegible
    ),
    "42501_borrado_sin_privilegio": Caso(
        _borrado_sin_privilegio, "42501", None, _afirmar_que_se_relanza
    ),
    "22p02_uuid_ilegible": Caso(_uuid_ilegible, "22P02", None, _afirmar_que_se_relanza),
}


def _rechazo_de_la_vigente() -> ConflictoEstado:
    """El sustituto de `rechazo_vigente`: un `ConflictoEstado` cualquiera.

    El contenido lo cubre el test del rechazo de la vigente.
    """
    return ConflictoEstado(
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje="Sustituto de rechazo_vigente.",
        detalle={},
        acciones=(),
    )


def _entorno(
    *,
    ruta: str = RUTA_DEL_CONGELADO,
    metodo: str = "POST",
    roles: tuple[str, ...] = ROLES_QUE_REINTENTAN,
) -> tuple[Entorno, Callable[[], ErrorContrato]]:
    vigente = _rechazo_de_la_vigente()
    llamadas: list[int] = []

    def rechazo_vigente() -> ErrorContrato:
        llamadas.append(1)
        return vigente

    return Entorno(ruta, metodo, roles, vigente, llamadas), rechazo_vigente


# --------------------------------------------------------------------------- las pruebas


@pytest.mark.parametrize("caso", list(CASOS), ids=list(CASOS))
def test_tkt017_cab06_traduccion_de_sqlstate(
    caso: str, motor_aplicacion: Engine, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-A24 · CA-B6 esc. 1 · RN-01 · ADR-031 — cada `SQLSTATE` real del motor se traduce a su contrato.

    `IN001` -> `REGLA_NEGOCIO` `RN-01`; `23505` del índice parcial -> lo que devuelve
    `rechazo_vigente`; `23505` de otra restricción, `23503` y `23001` -> `CONFLICTO`
    `ESTADO_NO_PERMITE_OPERACION` con la restricción; `55P03` y `57014` -> `CONCURRENCIA` con
    `Retry-After: 1` y `REINTENTAR`; `42501` y `22P02` -> `None`, para que el caso de uso relance.
    """
    esperado = CASOS[caso]
    error = esperado.provocar(motor_aplicacion, datos_presupuesto)

    # El error es real: el motor respondió con ese SQLSTATE y esa restricción.
    assert getattr(error.orig, "sqlstate", None) == esperado.sqlstate
    assert error.orig.diag.constraint_name == esperado.restriccion  # type: ignore[union-attr]

    entorno, rechazo_vigente = _entorno()
    resultado = traducir_error_del_motor(
        error,
        ruta_reintento=entorno.ruta,
        metodo_reintento=entorno.metodo,
        roles_reintento=entorno.roles,
        rechazo_vigente=rechazo_vigente,
    )

    esperado.afirmar(resultado, entorno)


@pytest.mark.parametrize(
    "caso", ["55p03_bloqueo_vencido", "57014_tiempo_de_ejecucion_vencido"], ids=str
)
@pytest.mark.parametrize(
    ("ruta", "metodo", "roles"),
    [
        (RUTA_DE_LA_CAPTURA, "PUT", ("DIRECCION_GENERAL", "DIRECTOR_PROYECTOS")),
        (RUTA_DEL_CONGELADO, "POST", ("DIRECCION_GENERAL",)),
    ],
    ids=["captura_put_dos_roles", "congelado_post_otro_rol"],
)
def test_tkt017_cab06_la_accion_reintentar_repite_la_operacion_que_recibio_el_traductor(
    caso: str,
    ruta: str,
    metodo: str,
    roles: tuple[str, ...],
    motor_aplicacion: Engine,
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-A24 · CA-B6 esc. 1 — `REINTENTAR` lleva el método, la ruta y los roles que el caso de uso pasó, no los de otra operación.

    Y se ofrece siempre, también a quien no tiene ninguno de los roles de la acción: repite lo que
    quien llama acaba de invocar.
    """
    error = CASOS[caso].provocar(motor_aplicacion, datos_presupuesto)
    entorno, rechazo_vigente = _entorno(ruta=ruta, metodo=metodo, roles=roles)

    resultado = traducir_error_del_motor(
        error,
        ruta_reintento=ruta,
        metodo_reintento=metodo,
        roles_reintento=roles,
        rechazo_vigente=rechazo_vigente,
    )

    assert isinstance(resultado, ConcurrenciaVencida)
    assert resultado.acciones == (Accion("REINTENTAR", metodo, ruta, roles),)
    sin_roles = resultado.cuerpo(frozenset(), CORRELACION)
    assert sin_roles["acciones"] == [{"clave": "REINTENTAR", "metodo": metodo, "ruta": ruta}]
    assert resultado.cabeceras() == {"Retry-After": "1"}
    assert entorno.llamadas_a_rechazo_vigente == []
