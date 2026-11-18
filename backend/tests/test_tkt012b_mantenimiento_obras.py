"""Casos de uso de mantenimiento de la obra (TKT-012b, fila A5): TC-21 a TC-32.

Prueba `cimenta/presupuesto/aplicacion/mantenimiento_obras.py` contra PostgreSQL real (testcontainers),
con el esquema de `alembic upgrade head`, el rol de aplicación y el contexto real de
`construir_contexto`. Nada de SQLite, nada de `sleep`.

Contrato que fijan estas pruebas
--------------------------------

Firmas (ambas devuelven `None`; la ruta relee con `obtener_obra`, como el alta):

- `actualizar_obra(contexto, obra_id, cambios, usuario_id)`.
- `eliminar_obra(contexto, obra_id, usuario_id)`.

`cambios` es un `Mapping[str, ValorEditable]` (`ValorEditable = str | bool | Porcentaje | None`, de
`dominio/ciclo_vida_obra.py`): es exactamente el `propuestos` de `cambios_efectivos`. Las claves
admitidas son `nombre`, `domicilio`, `retencion_destajo_pct`, `fondo_garantia_pct`, `iva_acreditable` y
`umbral_alerta_pct`. Clave **ausente** = no se toca; `umbral_alerta_pct: None` = borrar el umbral. La
ruta lo arma con `model_fields_set` de `ObraCambios`. No hay dataclass nuevo en la capa de aplicación.

`actualizar_obra`:

- Valida el rango de los porcentajes presentes **antes de abrir la transacción** (`ValidacionRechazada`,
  `FUERA_DE_RANGO`, mismos mensajes que el alta, en el orden retención, fondo, umbral).
- Toma `FOR UPDATE` de la obra; sin fila, `NoEncontrado(recurso="obra", mensaje="La obra no existe.")`.
- Con la obra `CERRADA`: `ConflictoEstado` `ESTADO_NO_PERMITE_OPERACION`, mensaje
  `La obra {codigo} está en CERRADA y no admite esta operación.`, detalle `{"estado": "CERRADA"}` y
  `acciones` vacías.
- Sin cambios efectivos no escribe nada (ni `actualizado_en`) y no asienta.
- Con cambios escribe solo esas columnas, sella `actualizado_en` (reloj inyectado) y
  `actualizado_por_id`, y asienta `ACTUALIZAR` con `datos_antes` y `datos_despues` de los campos que
  cambiaron, `regla_negocio=None` (F002a: antes `"RN-25"`, que en el PRD es el IVA; corrección de
  aserción por decisión de la persona dueña), `obra_id`, `motivo` nulo. Los porcentajes viajan como cadena de
  escala 6 (`cuantizar().serializar()`), el booleano como booleano, el umbral borrado como `null`.
- `asentar` se importa **por nombre** en `mantenimiento_obras` y corre en la misma sesión (regla 8).

`eliminar_obra`:

- Toma `FOR UPDATE`, **después** cuenta el historial (`contar_historial`, con las fuentes del contexto) y
  solo entonces borra. Sin fila, `NoEncontrado`.
- Con historial: `ConflictoEstado` `OBRA_CON_HISTORIAL`, mensaje
  `La obra {codigo} tiene historial y no se puede eliminar.`, detalle **exactamente**
  `{"linea_base_congelada": bool, "lineas_base": int, "importaciones": int, "movimientos": int}` y
  `acciones` = las que `operaciones_admitidas(estado)` permite de entre `SUSPENDER_OBRA` y
  `CERRAR_OBRA` (en ese orden), cada una `POST` a `/api/v1/obras/{id}/suspension` o `/cierre`, con
  los roles de `ROLES_ALTA`. Desde `PLANEACION` y `SUSPENDIDA`, solo `CERRAR_OBRA`; desde `CERRADA`,
  ninguna. No hay acción `REACTIVAR_OBRA`: el borrador solo declara las dos primeras (decisión de esta
  fila, a confirmar). Sin historial: asienta `ELIMINAR` y borra.
- Asiento `ELIMINAR`: `entidad_tipo` `obra`, `entidad_id` y `obra_id` = la obra, `regla_negocio`
  `RN-01`, `motivo` nulo, `datos_antes` = la fotografía de nueve claves del `CREAR` de la obra
  (`codigo`, `nombre`, `domicilio`, `tipo_contrato`, los tres porcentajes, `iva_acreditable` y
  `estado`), `datos_despues` nulo. Sobrevive a la obra: `bitacora.obra_id` no tiene clave foránea.
- Un `DBAPIError` `23001` (otra tabla hija cuelga de la obra) se traduce **dentro del caso de uso** a
  `OBRA_CON_HISTORIAL` con el mismo mensaje, el detalle de cuatro claves del contrato
  (`movimientos` 1: al menos una fila de otro módulo; el nombre de la clave foránea **no** sale, CWE-209,
  ciclo de corrección 2) y las mismas acciones por estado (D-DIS-4). Antes de `traducir_error_del_motor`, que lo mapearía a
  `ESTADO_NO_PERMITE_OPERACION`.
- Una fuente de historial que falla propaga su error tal cual: la obra no se borra.

Rojo de la fila A5: el módulo trae esqueletos que lanzan `NotImplementedError`, así que cada prueba de
comportamiento falla por eso. Nace en verde, a propósito, la que comprueba solo la firma que el
esqueleto ya tiene.

Mutantes de la fila (A9 los corre contra la suite acumulada): asentar fuera de la transacción
(`test_..._falla_del_asiento_*`), asentar aunque nada cambie (`..._sin_cambios_reales_*`), omitir el
asiento `ELIMINAR` (`..._sin_historial_*`), ofrecer `SUSPENDER_OBRA` desde `PLANEACION`
(`..._acciones_por_estado`), contar antes del `FOR UPDATE` (`..._bloqueo_retenido_*`), traducir el
`23001` a otro código (`..._fila_de_otro_modulo_*`), `hay_historial` sin importaciones
(`..._solo_una_importacion_*`).
"""

from __future__ import annotations

import functools
import inspect
import uuid
from collections.abc import Callable, Mapping
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from psycopg import errors as errores_pg
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.aplicacion import mantenimiento_obras
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto, construir_contexto
from cimenta.presupuesto.aplicacion.historial_obra import FuenteHistorialObra
from cimenta.presupuesto.aplicacion.mantenimiento_obras import actualizar_obra, eliminar_obra
from cimenta.presupuesto.aplicacion.obras import ROLES_ALTA, DatosObraNueva, crear_obra
from cimenta.presupuesto.dominio.ciclo_vida_obra import ValorEditable
from contrato_error.excepciones import (
    ConflictoEstado,
    ErrorContrato,
    NoEncontrado,
    ValidacionRechazada,
)
from herramientas.soporte_tkt017_entorno import Base, Contexto
from tipos_base import Porcentaje

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt012b-a5"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
ROLES_DG = frozenset({"DIRECCION_GENERAL"})
ROLES_SIN_ESCRITURA = frozenset({"RESIDENTE"})
ROLES_ALTA_ESPERADOS = ("DIRECTOR_PROYECTOS", "DIRECCION_GENERAL")
TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
CODIGO = "AP-058-25"
NOMBRE_INICIAL = f"Obra {CODIGO}"
DOMICILIO_INICIAL = "Calle de prueba 1"

MENSAJE_OBRA_NO_EXISTE = "La obra no existe."
MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."
MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."
MENSAJE_ESTADO = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_CON_HISTORIAL = "La obra {codigo} tiene historial y no se puede eliminar."

RUTA_DE_ACCION = {"SUSPENDER_OBRA": "suspension", "CERRAR_OBRA": "cierre"}

# Qué acciones del `409` `OBRA_CON_HISTORIAL` ofrece cada estado: las de `operaciones_admitidas(estado)`
# que el borrador declara (`SUSPENDER_OBRA` y `CERRAR_OBRA`), en ese orden.
ACCIONES_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR_OBRA",),
    "ACTIVA": ("SUSPENDER_OBRA", "CERRAR_OBRA"),
    "SUSPENDIDA": ("CERRAR_OBRA",),
    "CERRADA": (),
}

SELECT_ASIENTOS_DE_ENTIDAD = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, regla_negocio, motivo, "
    "obra_id, datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s ORDER BY ocurrido_en, id"
)


# --------------------------------------------------------------------------- dobles


class FalloDeFuente(Exception):  # noqa: N818 - es un doble de prueba, no una excepción de producción
    """El fallo que lanza una fuente caída: propio de la prueba, para distinguirlo de cualquier otro."""


class FuenteDeConteo:
    """Una fuente que dice cuántos movimientos tiene la obra y recuerda con qué la llamaron."""

    def __init__(self, nombre: str, movimientos: int) -> None:
        self.nombre = nombre
        self.movimientos = movimientos
        self.llamadas: list[tuple[Session, uuid.UUID]] = []

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        self.llamadas.append((sesion_bd, obra_id))
        return self.movimientos


class FuenteQueMiraElBloqueo(FuenteDeConteo):
    """Al contar, intenta bloquear la obra desde otra conexión sin esperar: debe fallar.

    Si el caso de uso cuenta antes de tomar el `FOR UPDATE` (o sin tomarlo), el intento sale bien y la
    prueba lo ve. `lector` es una conexión distinta de la sesión del caso de uso, en autocommit.
    """

    def __init__(self, nombre: str, movimientos: int, lector: Any) -> None:
        super().__init__(nombre, movimientos)
        self._lector = lector
        self.en_transaccion: list[bool] = []
        self.fila_bloqueada_para_otros: list[bool] = []

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        self.en_transaccion.append(sesion_bd.in_transaction())
        try:
            self._lector.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE NOWAIT", (obra_id,))
        except errores_pg.LockNotAvailable:
            self.fila_bloqueada_para_otros.append(True)
        else:
            self.fila_bloqueada_para_otros.append(False)
        return super().contar(sesion_bd, obra_id)


class FuenteCaida:
    """Una fuente cuya consulta falla: la base del módulo posterior no responde."""

    def __init__(self, nombre: str, error: Exception) -> None:
        self.nombre = nombre
        self.error = error
        self.llamadas = 0

    def contar(self, sesion_bd: Session, obra_id: uuid.UUID) -> int:
        self.llamadas += 1
        raise self.error


class FallaDeBitacora(Exception):  # noqa: N818 - es un doble de prueba, no una excepción de producción
    """El fallo del asiento que las pruebas de la misma transacción provocan a propósito."""


def _sin_motor() -> Engine:
    raise AssertionError("El rango de los porcentajes se valida antes de abrir la transacción")


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def lector(base_de_prueba: str, conectar: Conectar) -> Any:
    """Otra conexión del rol de aplicación, en autocommit, para mirar el bloqueo desde fuera."""
    return conectar("aplicacion", base_de_prueba)


@pytest.fixture
def contexto(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto real del rol de aplicación con su reloj de prueba, sin fuentes de historial."""
    return functools.cache(
        lambda: construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)
    )


@pytest.fixture
def contexto_con(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba
) -> Callable[..., ContextoPresupuesto]:
    """Construye el contexto real inyectando las fuentes de historial que la prueba pida."""

    def construir(*fuentes: FuenteHistorialObra) -> ContextoPresupuesto:
        return construir_contexto(
            proveedor_motor=lambda: motor_aplicacion,
            reloj=reloj_de_prueba,
            fuentes_historial=tuple(fuentes),
        )

    return construir


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (0008)."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return filas[0][0]


@pytest.fixture
def usuario(datos_presupuesto: DatosPresupuesto) -> uuid.UUID:
    return datos_presupuesto.usuario()


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID, usuario: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra con tres porcentajes distintos (un intercambio entre columnas se nota)."""

    def fabricar(
        *,
        codigo: str = CODIGO,
        estado: str = "ACTIVA",
        umbral: Decimal | None = Decimal("0.100000"),
    ) -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo,
            empresa_id=empresa_de_la_migracion,
            creado_por_id=usuario,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=umbral,
            iva_acreditable=True,
        )

    return fabricar


# --------------------------------------------------------------------------- ayudas


def _fila(base: Base, obra_id: uuid.UUID) -> dict[str, Any] | None:
    """Todas las columnas de la obra, con los `Decimal` como cadena para comprobar también la escala."""
    cursor = base.conexion.execute("SELECT * FROM obra WHERE id = %s", (obra_id,))
    fila = cursor.fetchone()
    if fila is None:
        return None
    assert cursor.description is not None
    return {
        columna.name: (str(valor) if isinstance(valor, Decimal) else valor)
        for columna, valor in zip(cursor.description, fila, strict=True)
    }


def _fila_obligatoria(base: Base, obra_id: uuid.UUID) -> dict[str, Any]:
    fila = _fila(base, obra_id)
    assert fila is not None, "La obra no existe"
    return fila


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _instantanea(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: obras completas, líneas base, importaciones y bitácora."""
    return {
        "foto": base.foto(),
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "importaciones": base.filas("SELECT id, obra_id, estado FROM importacion ORDER BY id"),
        "requisiciones": base.filas("SELECT id, obra_id, estado FROM requisicion ORDER BY id"),
        "bitacora": base.filas("SELECT id, accion::text, entidad_id FROM bitacora ORDER BY id"),
    }


def _rechazo[E: ErrorContrato](base: Base, llamada: Callable[[], object], clase: type[E]) -> E:
    """Ejecuta `llamada`, espera `clase` y comprueba que no cambió ninguna fila ni se asentó nada."""
    antes = _instantanea(base)
    with pytest.raises(clase) as rechazo:
        llamada()
    assert _instantanea(base) == antes, "Un rechazo no escribe: ni obra, ni historial, ni bitácora"
    return rechazo.value


def _cambios(**valores: ValorEditable) -> Mapping[str, ValorEditable]:
    return valores


def _acciones_esperadas(obra_id: uuid.UUID, claves: tuple[str, ...]) -> list[dict[str, str]]:
    return [
        {
            "clave": clave,
            "metodo": "POST",
            "ruta": f"/api/v1/obras/{obra_id}/{RUTA_DE_ACCION[clave]}",
        }
        for clave in claves
    ]


def _cuerpo_con_historial(
    *,
    obra_id: uuid.UUID,
    codigo: str,
    estado: str,
    detalle: dict[str, object],
) -> dict[str, object]:
    """El cuerpo completo del `409` `OBRA_CON_HISTORIAL` que ve un Director de Proyectos."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_CON_HISTORIAL.format(codigo=codigo),
        "codigo": "OBRA_CON_HISTORIAL",
        "detalle": detalle,
        "acciones": _acciones_esperadas(obra_id, ACCIONES_POR_ESTADO[estado]),
        "correlacion_id": CORRELACION,
    }


def _detalle_de_historial(
    *, congelada: bool = False, lineas_base: int = 0, importaciones: int = 0, movimientos: int = 0
) -> dict[str, object]:
    return {
        "linea_base_congelada": congelada,
        "lineas_base": lineas_base,
        "importaciones": importaciones,
        "movimientos": movimientos,
    }


def _asientos(base: Base, entidad_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return base.filas(SELECT_ASIENTOS_DE_ENTIDAD, entidad_id)


def _insertar_requisicion(
    base: Base,
    datos: DatosPresupuesto,
    *,
    obra_id: uuid.UUID,
    solicitante_id: uuid.UUID,
    ahora: Any,
) -> uuid.UUID:
    """Una requisición `BORRADOR` insertada por SQL: la fila de otro módulo que cuelga de la obra."""
    requisicion_id = uuid.uuid4()
    base.ejecutar(
        "INSERT INTO requisicion (id, obra_id, tipo_partida_id, solicitante_id, estado, "
        "importe_solicitado, creado_en, actualizado_en) "
        "VALUES (%s, %s, %s, %s, 'BORRADOR', %s, %s, %s)",
        requisicion_id,
        obra_id,
        datos.tipo_partida(),
        solicitante_id,
        Decimal("1000.0000"),
        ahora,
        ahora,
    )
    return requisicion_id


def _asentar_que_falla(visto: dict[str, object]) -> Callable[..., None]:
    """Un `asentar` que anota cómo lo llamaron y lanza, para probar que corre en la misma transacción."""

    def asentar_que_falla(*args: Any, **kwargs: Any) -> None:
        sesion_bd = args[0] if args else kwargs["sesion_bd"]
        visto["en_transaccion"] = sesion_bd.in_transaction()
        visto["accion"] = str(kwargs["accion"])
        visto["regla_negocio"] = kwargs.get("regla_negocio")
        visto["nombre_visto"] = sesion_bd.execute(
            text("SELECT nombre FROM obra WHERE id = :id"), {"id": kwargs["entidad_id"]}
        ).scalar_one_or_none()
        raise FallaDeBitacora

    return asentar_que_falla


# --------------------------------------------------------------------------- firma (nace en verde)


def test_tkt012b_a5_las_firmas_son_las_del_diseno() -> None:
    """A5 · firma — `actualizar_obra(contexto, obra_id, cambios, usuario_id)` y `eliminar_obra(contexto, obra_id, usuario_id)`.

    Nace en verde con el esqueleto: fija nombres y orden de los parámetros que cablea A7 y que el resto
    de pruebas de este archivo usan por nombre (`usuario_id=`).
    """
    assert list(inspect.signature(actualizar_obra).parameters) == [
        "contexto",
        "obra_id",
        "cambios",
        "usuario_id",
    ]
    assert list(inspect.signature(eliminar_obra).parameters) == [
        "contexto",
        "obra_id",
        "usuario_id",
    ]
    assert ROLES_ALTA == ROLES_ALTA_ESPERADOS


# --------------------------------------------------------------------------- TC-21 · CA-1


def test_hdu001_esc20_tkt012b_ca1_actualizar_obra_cambia_nombre_y_porcentaje_y_asienta_actualizar(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-21 · CA-1 · RN-25 — feliz: cambia nombre y retención; código, tipo y estado no cambian.

    El asiento `ACTUALIZAR` lleva solo los dos campos que cambiaron, con el valor anterior y el nuevo,
    los porcentajes como cadena de escala 6 (`0.1` se guarda y se asienta como `0.100000`), sin regla
    (`None`, F002a), la obra y el usuario. El reloj avanzado distingue `actualizado_en` de la hora de la base. Ninguna otra
    obra se toca. El caso de uso no devuelve nada: la ruta relee con `obtener_obra`.
    """
    obra_id = fabricar_obra()
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    editor = datos_presupuesto.usuario()
    antes = _fila_obligatoria(base, obra_id)
    antes_de_la_otra = _fila_obligatoria(base, otra)
    reloj_de_prueba.avanzar(timedelta(hours=3))
    ahora = reloj_de_prueba()

    resultado = actualizar_obra(  # type: ignore[func-returns-value]
        contexto(),
        obra_id,
        _cambios(nombre="Union Square F2 (ampliación)", retencion_destajo_pct=Porcentaje("0.1")),
        usuario_id=editor,
    )

    assert resultado is None
    assert _fila_obligatoria(base, obra_id) == {
        **antes,
        "nombre": "Union Square F2 (ampliación)",
        "retencion_destajo_pct": "0.100000",
        "actualizado_en": ahora,
        "actualizado_por_id": editor,
    }
    despues = _fila_obligatoria(base, obra_id)
    assert (despues["codigo"], despues["tipo_contrato"], despues["estado"]) == (
        CODIGO,
        TIPO_CONTRATO,
        "ACTIVA",
    )
    assert _fila_obligatoria(base, otra) == antes_de_la_otra
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            editor,
            ahora,
            None,
            None,
            obra_id,
            {"nombre": NOMBRE_INICIAL, "retencion_destajo_pct": "0.150000"},
            {"nombre": "Union Square F2 (ampliación)", "retencion_destajo_pct": "0.100000"},
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Una edición, un solo asiento"


def test_tkt012b_ca1_actualizar_obra_cambia_los_seis_campos_y_el_asiento_los_trae_todos(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-21 · CA-1 · RN-25 — feliz: nombre, domicilio, los tres porcentajes y el IVA, a la vez.

    Cada campo cambia a un valor distinto de los otros, para que un intercambio entre columnas no pase.
    El IVA viaja como booleano en el asiento (no como cadena) y los porcentajes con escala 6.
    """
    obra_id = fabricar_obra()
    ahora = reloj_de_prueba()

    actualizar_obra(
        contexto(),
        obra_id,
        _cambios(
            nombre="Otro nombre",
            domicilio="Otro domicilio 2",
            retencion_destajo_pct=Porcentaje("0.2"),
            fondo_garantia_pct=Porcentaje("0.075"),
            iva_acreditable=False,
            umbral_alerta_pct=Porcentaje("0.3"),
        ),
        usuario_id=usuario,
    )

    fila = _fila_obligatoria(base, obra_id)
    assert (
        fila["nombre"],
        fila["domicilio"],
        fila["retencion_destajo_pct"],
        fila["fondo_garantia_pct"],
        fila["iva_acreditable"],
        fila["umbral_alerta_pct"],
    ) == ("Otro nombre", "Otro domicilio 2", "0.200000", "0.075000", False, "0.300000")
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            usuario,
            ahora,
            None,
            None,
            obra_id,
            {
                "nombre": NOMBRE_INICIAL,
                "domicilio": DOMICILIO_INICIAL,
                "retencion_destajo_pct": "0.150000",
                "fondo_garantia_pct": "0.050000",
                "iva_acreditable": True,
                "umbral_alerta_pct": "0.100000",
            },
            {
                "nombre": "Otro nombre",
                "domicilio": "Otro domicilio 2",
                "retencion_destajo_pct": "0.200000",
                "fondo_garantia_pct": "0.075000",
                "iva_acreditable": False,
                "umbral_alerta_pct": "0.300000",
            },
        )
    ]


def test_tkt012b_ca1_actualizar_obra_un_valor_igual_al_actual_no_entra_en_el_asiento(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-21 · CA-1 — feliz: de tres campos enviados, solo el que cambia se escribe y se asienta.

    `nombre` igual, `retencion_destajo_pct` igual **en valor** (`0.15` frente a `0.150000` de la
    columna) y `domicilio` distinto: el asiento trae solo `domicilio`, y la retención sigue en `0.150000`.
    """
    obra_id = fabricar_obra()
    ahora = reloj_de_prueba()

    actualizar_obra(
        contexto(),
        obra_id,
        _cambios(
            nombre=NOMBRE_INICIAL,
            retencion_destajo_pct=Porcentaje("0.15"),
            domicilio="Domicilio nuevo 7",
        ),
        usuario_id=usuario,
    )

    fila = _fila_obligatoria(base, obra_id)
    assert fila["nombre"] == NOMBRE_INICIAL
    assert fila["retencion_destajo_pct"] == "0.150000"
    assert fila["domicilio"] == "Domicilio nuevo 7"
    assert fila["actualizado_en"] == ahora
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            usuario,
            ahora,
            None,
            None,
            obra_id,
            {"domicilio": DOMICILIO_INICIAL},
            {"domicilio": "Domicilio nuevo 7"},
        )
    ]


# --------------------------------------------------------------------------- TC-22 · CA-1 variante


@pytest.mark.parametrize("estado", ["PLANEACION", "ACTIVA", "SUSPENDIDA"])
def test_tkt012b_ca1_actualizar_obra_se_edita_en_todo_estado_salvo_cerrada(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
    estado: str,
) -> None:
    """TC-22 · CA-1 variante · D-3 — feliz: `PLANEACION`, `ACTIVA` y `SUSPENDIDA` admiten la edición.

    La obra `SUSPENDIDA` se edita sin reactivarla (D-3). Quien edita es otro usuario, el de Dirección
    General: a este nivel el rol no cuenta (lo comprueba la ruta en A7); lo que se prueba es que el
    usuario que edita queda en `actualizado_por_id` y en el asiento. El estado no cambia.
    """
    obra_id = fabricar_obra(estado=estado)
    direccion_general = datos_presupuesto.usuario()
    ahora = reloj_de_prueba()

    actualizar_obra(
        contexto(),
        obra_id,
        _cambios(nombre=f"Nombre en {estado}"),
        usuario_id=direccion_general,
    )

    fila = _fila_obligatoria(base, obra_id)
    assert fila["nombre"] == f"Nombre en {estado}"
    assert fila["estado"] == estado
    assert fila["actualizado_por_id"] == direccion_general
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            direccion_general,
            ahora,
            None,
            None,
            obra_id,
            {"nombre": NOMBRE_INICIAL},
            {"nombre": f"Nombre en {estado}"},
        )
    ]


# --------------------------------------------------------------------------- TC-23 · CA-1 variante


def test_tkt012b_ca1_actualizar_obra_umbral_none_borra_el_umbral_y_asienta(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-23 · CA-1 variante · PA-18 — feliz: `umbral_alerta_pct: None` escribe `NULL` y lo asienta.

    El asiento trae el umbral anterior y `null` después. Ausente no es `None`: la edición de otro campo
    (el nombre) conserva el umbral, que aquí vale `0.100000` hasta que se borra.
    """
    obra_id = fabricar_obra()
    actualizar_obra(contexto(), obra_id, _cambios(nombre="Solo el nombre"), usuario_id=usuario)
    assert _fila_obligatoria(base, obra_id)["umbral_alerta_pct"] == "0.100000", (
        "Una clave ausente conserva el umbral"
    )
    reloj_de_prueba.avanzar(timedelta(minutes=5))  # el borrado del umbral queda como último asiento
    ahora = reloj_de_prueba()

    actualizar_obra(contexto(), obra_id, _cambios(umbral_alerta_pct=None), usuario_id=usuario)

    assert _fila_obligatoria(base, obra_id)["umbral_alerta_pct"] is None
    assert _asientos(base, obra_id)[-1] == (
        "ACTUALIZAR",
        "obra",
        obra_id,
        usuario,
        ahora,
        None,
        None,
        obra_id,
        {"umbral_alerta_pct": "0.100000"},
        {"umbral_alerta_pct": None},
    )
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 2


def test_tkt012b_ca1_actualizar_obra_puede_fijar_el_umbral_de_una_obra_que_no_lo_tenia(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-23 · CA-1 variante — feliz: del umbral `NULL` a `0.2`, con `null` como valor anterior del asiento."""
    obra_id = fabricar_obra(umbral=None)
    ahora = reloj_de_prueba()

    actualizar_obra(
        contexto(), obra_id, _cambios(umbral_alerta_pct=Porcentaje("0.2")), usuario_id=usuario
    )

    assert _fila_obligatoria(base, obra_id)["umbral_alerta_pct"] == "0.200000"
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            usuario,
            ahora,
            None,
            None,
            obra_id,
            {"umbral_alerta_pct": None},
            {"umbral_alerta_pct": "0.200000"},
        )
    ]


# --------------------------------------------------------------------------- TC-24 · CA-1 variante


def test_tkt012b_ca1_actualizar_obra_sin_cambios_reales_no_escribe_ni_asienta(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-24 · CA-1 variante · S-2 — feliz: un cuerpo que no cambia ningún valor no deja rastro.

    Los seis campos con su valor actual (los porcentajes iguales en valor aunque con otra escala) y
    después un mapa vacío: la obra queda tal cual, **sin** `actualizado_en` ni `actualizado_por_id`
    (nadie la tocó) y sin asiento. Un asiento vacío ensuciaría la bitácora.
    """
    obra_id = fabricar_obra()
    antes = _instantanea(base)
    fila_antes = _fila_obligatoria(base, obra_id)
    assert fila_antes["actualizado_en"] is None
    assert fila_antes["actualizado_por_id"] is None

    actualizar_obra(
        contexto(),
        obra_id,
        _cambios(
            nombre=NOMBRE_INICIAL,
            domicilio=DOMICILIO_INICIAL,
            retencion_destajo_pct=Porcentaje("0.15"),
            fondo_garantia_pct=Porcentaje("0.05"),
            iva_acreditable=True,
            umbral_alerta_pct=Porcentaje("0.1"),
        ),
        usuario_id=usuario,
    )
    actualizar_obra(contexto(), obra_id, {}, usuario_id=usuario)

    assert _instantanea(base) == antes
    assert _fila_obligatoria(base, obra_id) == fila_antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


def test_tkt012b_ca1_actualizar_obra_umbral_none_sobre_umbral_nulo_no_es_un_cambio(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-24 · CA-1 variante — feliz: borrar un umbral que ya no existe no escribe ni asienta."""
    obra_id = fabricar_obra(umbral=None)
    antes = _instantanea(base)

    actualizar_obra(contexto(), obra_id, _cambios(umbral_alerta_pct=None), usuario_id=usuario)

    assert _instantanea(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- TC-25 · CA-4


def test_tkt012b_ca4_actualizar_obra_cerrada_responde_409_estado_no_permite_operacion(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-25 · CA-4 — rechazo: la obra `CERRADA` no se edita; `409` `ESTADO_NO_PERMITE_OPERACION` con el estado.

    El contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`: la máquina de estados no es una
    `RN`), `codigo` del catálogo, mensaje con el código de la obra y su estado, detalle con el estado y
    ninguna acción (una obra cerrada no admite ninguna operación; tampoco para quien no puede operar).
    El cambio pedido es válido: lo que rechaza es el estado. Obra y bitácora quedan intactas.
    """
    obra_id = fabricar_obra(estado="CERRADA")

    error = _rechazo(
        base,
        lambda: actualizar_obra(
            contexto(), obra_id, _cambios(nombre="Nombre tardío"), usuario_id=usuario
        ),
        ConflictoEstado,
    )

    esperado = {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_ESTADO.format(codigo=CODIGO, estado="CERRADA"),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"estado": "CERRADA"},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert error.cuerpo(ROLES_DG, CORRELACION) == esperado
    assert error.cuerpo(ROLES_SIN_ESCRITURA, CORRELACION) == esperado
    assert _fila_obligatoria(base, obra_id)["nombre"] == NOMBRE_INICIAL
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- TC-26 · CA-3


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        ("retencion_destajo_pct", "-0.010000", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("retencion_destajo_pct", "1.000001", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("fondo_garantia_pct", "-0.010000", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("fondo_garantia_pct", "1.000001", MENSAJE_PORCENTAJE_FUERA_DE_RANGO),
        ("umbral_alerta_pct", "-0.000001", MENSAJE_UMBRAL_NEGATIVO),
    ],
)
def test_tkt012b_ca3_actualizar_obra_porcentaje_fuera_de_rango_responde_422_sin_cambio_ni_asiento(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    campo: str,
    valor: str,
    mensaje: str,
) -> None:
    """TC-26 · CA-3 · PA-02 · PA-18 — rechazo: `422` `VALIDACION` por campo, sin cambio ni asiento.

    Junto al porcentaje inválido viaja un cambio válido (el nombre): tampoco ese se escribe, porque el
    rechazo es de toda la petición. El contrato completo: un `ErrorDeCampo` `FUERA_DE_RANGO` con el
    mensaje del diseño. Un umbral negativo y un `1.000001` son rechazos del caso de uso, no del motor
    (`CHECK` `23514`).
    """
    obra_id = fabricar_obra()

    error = _rechazo(
        base,
        lambda: actualizar_obra(
            contexto(),
            obra_id,
            _cambios(nombre="No debe escribirse", **{campo: Porcentaje(valor)}),
            usuario_id=usuario,
        ),
        ValidacionRechazada,
    )

    assert error.estado_http == 422
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 1 campo inválido.",
        "errores": [{"campo": campo, "codigo": "FUERA_DE_RANGO", "mensaje": mensaje}],
        "correlacion_id": CORRELACION,
    }
    assert _fila_obligatoria(base, obra_id)["nombre"] == NOMBRE_INICIAL
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


def test_tkt012b_ca3_actualizar_obra_el_rango_se_valida_antes_de_abrir_la_transaccion(
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-26 · CA-3 — rechazo: con los tres porcentajes fuera de rango, `422` con tres errores y sin tocar la base.

    El contexto no tiene motor (pedirlo falla): si el caso de uso abre la transacción antes de validar,
    la prueba cae con `AssertionError` y no con `ValidacionRechazada`. El orden de los errores es el del
    alta: retención, fondo, umbral. La obra ni siquiera existe: la forma se rechaza antes que el
    `404`.
    """
    contexto = construir_contexto(proveedor_motor=_sin_motor, reloj=reloj_de_prueba)

    with pytest.raises(ValidacionRechazada) as rechazo:
        actualizar_obra(
            contexto,
            uuid.uuid4(),
            _cambios(
                retencion_destajo_pct=Porcentaje("1.5"),
                fondo_garantia_pct=Porcentaje("-0.5"),
                umbral_alerta_pct=Porcentaje("-1"),
            ),
            usuario_id=uuid.uuid4(),
        )

    assert rechazo.value.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "VALIDACION",
        "mensaje": "La petición tiene 3 campos inválidos.",
        "errores": [
            {
                "campo": "retencion_destajo_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            },
            {
                "campo": "fondo_garantia_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            },
            {
                "campo": "umbral_alerta_pct",
                "codigo": "FUERA_DE_RANGO",
                "mensaje": MENSAJE_UMBRAL_NEGATIVO,
            },
        ],
        "correlacion_id": CORRELACION,
    }


def test_tkt012b_ca3_actualizar_obra_los_extremos_cero_y_uno_son_validos(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-26 · CA-3 · PA-02 · PA-18 — feliz: los bordes `1`, `0` y un umbral `0` se aceptan (rango cerrado)."""
    obra_id = fabricar_obra()

    actualizar_obra(
        contexto(),
        obra_id,
        _cambios(
            retencion_destajo_pct=Porcentaje("1"),
            fondo_garantia_pct=Porcentaje("0"),
            umbral_alerta_pct=Porcentaje("0"),
        ),
        usuario_id=usuario,
    )

    fila = _fila_obligatoria(base, obra_id)
    assert (
        fila["retencion_destajo_pct"],
        fila["fondo_garantia_pct"],
        fila["umbral_alerta_pct"],
    ) == ("1.000000", "0.000000", "0.000000")


# --------------------------------------------------------------------------- TC-27 · CA-1, regla 8


def test_tkt012b_ca1_actualizar_obra_si_falla_el_asiento_se_deshace_el_cambio(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-27 · CA-1 · regla 8 — rechazo: la bitácora se escribe en la misma transacción que el cambio.

    `asentar` se sustituye por uno que, antes de lanzar, comprueba que corre dentro de la transacción
    del caso de uso y que ve el nombre nuevo todavía sin confirmar. Al lanzar, la transacción se
    deshace: la obra conserva el nombre y no hay `actualizado_en` ni asiento. Con `asentar` en otra sesión
    tras confirmar, la obra quedaría cambiada y la prueba cae.
    """
    obra_id = fabricar_obra()
    visto: dict[str, object] = {}
    monkeypatch.setattr(mantenimiento_obras, "asentar", _asentar_que_falla(visto))
    antes = _instantanea(base)

    with pytest.raises(FallaDeBitacora):
        mantenimiento_obras.actualizar_obra(
            contexto(), obra_id, _cambios(nombre="Nombre que se deshace"), usuario_id=usuario
        )

    assert visto == {
        "en_transaccion": True,
        "accion": "ACTUALIZAR",
        "regla_negocio": None,
        "nombre_visto": "Nombre que se deshace",
    }, "asentar debe correr en la misma sesión, con el cambio hecho y sin confirmar"
    assert _instantanea(base) == antes, "Un asiento que falla deshace el cambio entero"
    fila = _fila_obligatoria(base, obra_id)
    assert fila["nombre"] == NOMBRE_INICIAL
    assert fila["actualizado_en"] is None


# --------------------------------------------------------------------------- obra inexistente


def test_tkt012b_ca12_actualizar_obra_inexistente_responde_404_y_no_asienta(
    contexto: Contexto, base: Base, usuario: uuid.UUID
) -> None:
    """CA-12 · TC-52 a nivel de caso de uso — rechazo: `NO_ENCONTRADO` con `recurso` `obra` y nada escrito."""
    error = _rechazo(
        base,
        lambda: actualizar_obra(
            contexto(), uuid.uuid4(), _cambios(nombre="Fantasma"), usuario_id=usuario
        ),
        NoEncontrado,
    )

    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_OBRA_NO_EXISTE,
        "recurso": "obra",
        "correlacion_id": CORRELACION,
    }


def test_tkt012b_ca12_eliminar_obra_inexistente_responde_404_y_no_asienta(
    contexto: Contexto, base: Base, usuario: uuid.UUID
) -> None:
    """CA-12 · TC-52 a nivel de caso de uso — rechazo: `NO_ENCONTRADO` con `recurso` `obra` y nada escrito."""
    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), uuid.uuid4(), usuario_id=usuario),
        NoEncontrado,
    )

    assert error.estado_http == 404
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_OBRA_NO_EXISTE,
        "recurso": "obra",
        "correlacion_id": CORRELACION,
    }


# --------------------------------------------------------------------------- TC-28 · CA-5


def test_hdu001_esc20_eliminar_obra_sin_historial_la_borra_y_su_asiento_conserva_la_fotografia(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    empresa_de_la_migracion: uuid.UUID,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-28 · HDU-001 esc. 20 · CA-5 · RN-01 — feliz: la obra desaparece y el asiento `ELIMINAR` queda.

    La obra recién dada de alta (`PLANEACION`, sin línea base, importación ni movimientos) se borra. El
    asiento lleva en `datos_antes` la fotografía de nueve claves (la del `CREAR`), `RN-01`, la obra y el
    usuario, sin motivo ni `datos_despues`, y sobrevive a la fila (`bitacora.obra_id` no tiene clave
    foránea). Otra obra, también sin historial, no se toca.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    otra = datos_presupuesto.obra(codigo="AP-099-26", empresa_id=empresa_de_la_migracion)
    otra_antes = _fila_obligatoria(base, otra)
    reloj_de_prueba.avanzar(timedelta(hours=2))
    ahora = reloj_de_prueba()

    resultado = eliminar_obra(contexto(), obra_id, usuario_id=usuario)  # type: ignore[func-returns-value]

    assert resultado is None
    assert _fila(base, obra_id) is None
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE codigo = %s", CODIGO) == 0
    assert _fila_obligatoria(base, otra) == otra_antes
    assert _asientos(base, obra_id) == [
        (
            "ELIMINAR",
            "obra",
            obra_id,
            usuario,
            ahora,
            "RN-01",
            None,
            obra_id,
            {
                "codigo": CODIGO,
                "nombre": NOMBRE_INICIAL,
                "domicilio": DOMICILIO_INICIAL,
                "tipo_contrato": TIPO_CONTRATO,
                "retencion_destajo_pct": "0.150000",
                "fondo_garantia_pct": "0.050000",
                "iva_acreditable": True,
                "umbral_alerta_pct": "0.100000",
                "estado": "PLANEACION",
            },
            None,
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Un borrado, un solo asiento"


def test_hdu001_esc20_eliminar_obra_sin_umbral_asienta_el_umbral_como_nulo(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-28 · CA-5 — feliz: la fotografía distingue «sin umbral» (`null`) de un umbral de cero."""
    obra_id = fabricar_obra(estado="PLANEACION", umbral=None)

    eliminar_obra(contexto(), obra_id, usuario_id=usuario)

    (asiento,) = _asientos(base, obra_id)
    assert asiento[0] == "ELIMINAR"
    assert asiento[8]["umbral_alerta_pct"] is None
    assert asiento[8]["estado"] == "PLANEACION"


def test_hdu001_esc20_eliminar_obra_libera_el_codigo_para_un_alta_nueva(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-28 · CA-5 · TC-INV-5 — feliz: tras el borrado físico, el código `AP-058-25` se da de alta otra vez.

    Con un borrado lógico, `uq_obra_codigo` lo retendría y el alta daría `CODIGO_OBRA_DUPLICADO`. La obra
    nueva tiene otro id; el asiento del borrado sigue apuntando a la vieja.
    """
    vieja = fabricar_obra(estado="PLANEACION")
    eliminar_obra(contexto(), vieja, usuario_id=usuario)

    nueva = crear_obra(
        contexto(),
        datos=DatosObraNueva(
            codigo=CODIGO,
            nombre="Obra repetida",
            domicilio=DOMICILIO_INICIAL,
            tipo_contrato=TIPO_CONTRATO,
            retencion_destajo_pct=Porcentaje("0.15"),
            fondo_garantia_pct=Porcentaje("0.05"),
            iva_acreditable=False,
            umbral_alerta_pct=None,
        ),
        usuario_id=usuario,
    )

    assert nueva != vieja
    assert _fila_obligatoria(base, nueva)["nombre"] == "Obra repetida"
    assert [fila[0] for fila in _asientos(base, vieja)] == ["ELIMINAR"]
    assert [fila[0] for fila in _asientos(base, nueva)] == ["CREAR"]


def test_hdu001_esc20_eliminar_obra_sin_historial_con_fuentes_en_cero_consulta_a_cada_una(
    contexto_con: Callable[..., ContextoPresupuesto],
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-28 · CA-5 — feliz: con fuentes inyectadas que dicen cero, la obra se borra y se las consultó a todas.

    Cada fuente se consulta una vez, con la sesión de la transacción y el `obra_id` borrado.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    compras = FuenteDeConteo("compras", 0)
    almacen = FuenteDeConteo("almacen", 0)

    eliminar_obra(contexto_con(compras, almacen), obra_id, usuario_id=usuario)

    assert _fila(base, obra_id) is None
    for fuente in (compras, almacen):
        assert [obra for _, obra in fuente.llamadas] == [obra_id], fuente.nombre
    assert [fila[0] for fila in _asientos(base, obra_id)] == ["ELIMINAR"]


def test_tkt012b_ca5_eliminar_obra_si_falla_el_asiento_no_se_borra_la_obra(
    contexto: Contexto,
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-28 · CA-5 · regla 8 — rechazo: si el asiento falla, la obra sigue ahí y no queda asiento.

    `asentar` corre en la misma sesión del borrado (anota `in_transaction`) y luego lanza. Con el asiento
    escrito aparte y el borrado ya confirmado, la obra habría desaparecido sin rastro.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    visto: dict[str, object] = {}
    monkeypatch.setattr(mantenimiento_obras, "asentar", _asentar_que_falla(visto))
    antes = _instantanea(base)

    with pytest.raises(FallaDeBitacora):
        mantenimiento_obras.eliminar_obra(contexto(), obra_id, usuario_id=usuario)

    assert visto["en_transaccion"] is True
    assert visto["accion"] == "ELIMINAR"
    assert visto["regla_negocio"] == "RN-01"
    assert _instantanea(base) == antes
    assert _fila(base, obra_id) is not None


# --------------------------------------------------------------------------- TC-29 · CA-6


def test_hdu001_esc20_eliminar_obra_con_linea_base_congelada_responde_409_obra_con_historial(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-29 · HDU-001 esc. 20 · CA-6 · RN-01 — rechazo: la obra con línea base congelada no se elimina.

    Dos líneas base (una `SUPERSEDIDA` y la `CONGELADA`) y dos importaciones: el detalle trae
    `linea_base_congelada` verdadero y las cifras reales (2 y 2, distintas de las otras tres para que un
    cruce no pase). Las acciones de una obra `ACTIVA` son `SUSPENDER_OBRA` y `CERRAR_OBRA`, cada una con
    método `POST` y la ruta de esa obra; las ve quien puede operar (Director de Proyectos y Dirección
    General) y no las ve un residente. Nada se borra y no se asienta nada.
    """
    obra_id = fabricar_obra(estado="ACTIVA")
    datos_presupuesto.linea_base(obra_id=obra_id, estado="SUPERSEDIDA", version=1)
    congelada = datos_presupuesto.linea_base(obra_id=obra_id, estado="CONGELADA", version=2)
    for _ in range(2):
        datos_presupuesto.importacion(obra_id=obra_id)

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    esperado = _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado="ACTIVA",
        detalle=_detalle_de_historial(congelada=True, lineas_base=2, importaciones=2),
    )
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == esperado
    assert error.cuerpo(ROLES_DG, CORRELACION) == esperado
    assert error.cuerpo(ROLES_SIN_ESCRITURA, CORRELACION) == {**esperado, "acciones": []}
    assert [accion.clave for accion in error.acciones] == ["SUSPENDER_OBRA", "CERRAR_OBRA"]
    assert all(
        accion.roles_permitidos == frozenset(ROLES_ALTA_ESPERADOS) for accion in error.acciones
    )
    assert _fila_obligatoria(base, obra_id)["estado"] == "ACTIVA"
    assert _cuenta(base, "SELECT count(*) FROM linea_base WHERE id = %s", congelada) == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- TC-30 · CA-6 ejemplo 2


def test_hdu001_esc20_eliminar_obra_con_solo_una_importacion_responde_409_sin_linea_base_congelada(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-30 · CA-6 ejemplo 2 · RN-01 · D-1 — rechazo: una importación basta; `linea_base_congelada` es falso.

    Dos importaciones y ninguna línea base. Es el historial «amplio» de D-1: sin mirar `importacion`
    la obra se borraría y la importación (con su archivo) quedaría sin dueño.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    for _ in range(2):
        datos_presupuesto.importacion(obra_id=obra_id)

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado="PLANEACION",
        detalle=_detalle_de_historial(importaciones=2),
    )


def test_hdu001_esc20_eliminar_obra_con_una_linea_base_borrador_tambien_tiene_historial(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-30 · CA-6 · RN-01 · D-DIS-5 `(asumido)` — rechazo: una línea base `BORRADOR` ya es historial.

    Es la obra de la prueba E2E (`M2`) y la que el congelado alcanza primero en la carrera de `CA-7`.
    Si la persona dueña confirma otra lectura de D-DIS-5, cambia esta prueba.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    datos_presupuesto.linea_base(obra_id=obra_id, estado="BORRADOR", version=1)

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado="PLANEACION",
        detalle=_detalle_de_historial(lineas_base=1),
    )


# --------------------------------------------------------------------------- TC-31 · CA-6, CA-9


@pytest.mark.parametrize("estado", ["PLANEACION", "ACTIVA", "SUSPENDIDA", "CERRADA"])
def test_hdu001_esc20_eliminar_obra_con_historial_ofrece_solo_las_acciones_que_el_estado_admite(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    estado: str,
) -> None:
    """TC-31 · CA-6 · CA-9 — rechazo: nunca se ofrece una acción que respondería `409`.

    Desde `PLANEACION` no hay suspensión (`PLANEACION → SUSPENDIDA` está prohibida): solo `CERRAR_OBRA`.
    Desde `ACTIVA`, las dos. Desde `SUSPENDIDA`, solo `CERRAR_OBRA` (suspender de nuevo se rechazaría; y
    `REACTIVAR_OBRA` no es de las acciones que declara el borrador para este `409`). Desde `CERRADA`,
    ninguna. El cuerpo completo se compara contra la lista exacta, con método y ruta.
    """
    obra_id = fabricar_obra(estado=estado)
    datos_presupuesto.importacion(obra_id=obra_id)

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado=estado,
        detalle=_detalle_de_historial(importaciones=1),
    )
    assert [accion.clave for accion in error.acciones] == list(ACCIONES_POR_ESTADO[estado])


# --------------------------------------------------------------------------- TC-32 · CA-6, D-DIS-4


def test_hdu001_esc20_eliminar_obra_con_una_fila_de_otro_modulo_traduce_el_23001_a_obra_con_historial(
    contexto: Contexto,
    base: Base,
    datos_presupuesto: DatosPresupuesto,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-32 · CA-6 · D-DIS-4 · RN-01 — rechazo: sin fuente inyectada, la clave foránea es la última barrera.

    Una requisición (`BORRADOR`) insertada por SQL cuelga de la obra y ninguna fuente la cuenta: el
    conteo da cero y el `DELETE` choca con `fk_requisicion_obra_id` (`23001`, `ON DELETE RESTRICT`).
    El caso de uso lo traduce a `409` `CONFLICTO` `OBRA_CON_HISTORIAL` (no al genérico
    `ESTADO_NO_PERMITE_OPERACION` de `traducir_error_del_motor`), con el detalle de cuatro claves del
    contrato (`movimientos` 1, sin el nombre de la restricción: CWE-209) y con las acciones del estado
    (`PLANEACION`: solo `CERRAR_OBRA`). La transacción se deshace entera: ni obra borrada ni asiento `ELIMINAR`.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    requisicion = _insertar_requisicion(
        base, datos_presupuesto, obra_id=obra_id, solicitante_id=usuario, ahora=reloj_de_prueba()
    )

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto(), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    assert error.estado_http == 409
    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado="PLANEACION",
        detalle=_detalle_de_historial(movimientos=1),
    )
    assert "fk_" not in repr(error.cuerpo(ROLES_DP, CORRELACION))
    assert "restriccion" not in repr(error.cuerpo(ROLES_DP, CORRELACION))
    assert _cuenta(base, "SELECT count(*) FROM requisicion WHERE id = %s", requisicion) == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0


# --------------------------------------------------------------------------- fuentes inyectadas


def test_hdu001_esc20_eliminar_obra_con_movimientos_de_las_fuentes_responde_409_con_su_suma(
    contexto_con: Callable[..., ContextoPresupuesto],
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-19/TC-29 integrados · CA-6 · RN-01 — rechazo: una fuente inyectada con movimientos impide el borrado.

    Sin nada propio (ni línea base ni importación), dos fuentes dicen 3 y 4 movimientos: el detalle trae
    `movimientos` 7 y el resto en cero. Sin sumar las fuentes (`hay_historial` ignorando `movimientos`)
    la obra se borraría.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    compras = FuenteDeConteo("compras", 3)
    almacen = FuenteDeConteo("almacen", 4)

    error = _rechazo(
        base,
        lambda: eliminar_obra(contexto_con(compras, almacen), obra_id, usuario_id=usuario),
        ConflictoEstado,
    )

    assert error.cuerpo(ROLES_DP, CORRELACION) == _cuerpo_con_historial(
        obra_id=obra_id,
        codigo=CODIGO,
        estado="PLANEACION",
        detalle=_detalle_de_historial(movimientos=7),
    )
    assert _fila(base, obra_id) is not None


def test_hdu001_esc20_eliminar_obra_cuenta_el_historial_con_la_obra_ya_bloqueada(
    contexto_con: Callable[..., ContextoPresupuesto],
    base: Base,
    lector: Any,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-14/TC-39 en el caso de uso · CA-7 — concurrencia: al contar, otra conexión no puede bloquear la obra.

    La fuente intenta `SELECT … FOR UPDATE NOWAIT` sobre la obra desde otra conexión mientras cuenta: el
    intento debe fallar con `LockNotAvailable`, porque el caso de uso ya tomó su `FOR UPDATE` y sigue en
    su transacción. Si cuenta antes de bloquear, el intento sale bien y la prueba cae. Es lo que cierra
    la carrera con el congelado y con una escritura de otro módulo (las pruebas de carrera real son de A9).
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    fuente = FuenteQueMiraElBloqueo("compras", 0, lector)

    eliminar_obra(contexto_con(fuente), obra_id, usuario_id=usuario)

    assert fuente.en_transaccion == [True]
    assert fuente.fila_bloqueada_para_otros == [True], (
        "La obra debe estar bloqueada con FOR UPDATE mientras se cuenta el historial"
    )
    assert len(fuente.llamadas) == 1
    assert fuente.llamadas[0][1] == obra_id
    assert _fila(base, obra_id) is None


def test_hdu001_esc20_eliminar_obra_si_una_fuente_falla_el_error_sale_y_la_obra_no_se_borra(
    contexto_con: Callable[..., ContextoPresupuesto],
    base: Base,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario: uuid.UUID,
) -> None:
    """TC-20 en el caso de uso · CA-6 · RN-01 — rechazo: una fuente caída no se lee como «cero movimientos».

    El error de la fuente sale tal cual (no es un error de contrato: es un fallo del servidor), la obra
    no se borra y no se asienta nada. La obra no tiene historial propio: sin el fallo, sí se borraría.
    """
    obra_id = fabricar_obra(estado="PLANEACION")
    error = FalloDeFuente("la base de compras no responde")
    caida = FuenteCaida("compras", error)
    antes = _instantanea(base)

    with pytest.raises(FalloDeFuente) as salido:
        eliminar_obra(
            contexto_con(FuenteDeConteo("almacen", 0), caida), obra_id, usuario_id=usuario
        )

    assert salido.value is error
    assert caida.llamadas == 1
    assert _instantanea(base) == antes
    assert _fila(base, obra_id) is not None
