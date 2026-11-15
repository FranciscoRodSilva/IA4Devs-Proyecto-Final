"""Casos de uso del catálogo de proveedores (TKT-029a, fila A4): TC-12 a TC-20 y tres pruebas de apoyo.

Prueba `cimenta/proveedores/aplicacion/contexto.py` y `cimenta/proveedores/aplicacion/proveedores.py`
(`crear_proveedor`, `obtener_proveedor`, `listar_proveedores`, `actualizar_proveedor`,
`desactivar_proveedor`, `DatosProveedorNuevo`, `CambiosProveedor`, `ProveedoresConsultados` y
`MENSAJE_PROVEEDOR_NO_EXISTE`) contra PostgreSQL real, con el esquema de `alembic upgrade head` (la
`0013` incluida) y el rol de aplicación. Nada de SQLite, nada de `sleep` para sincronizar.

Los módulos `cimenta.proveedores.aplicacion.contexto` y `cimenta.proveedores.aplicacion.proveedores` se
importan dentro del cuerpo de cada prueba, y la *fixture* `contexto_proveedores` difiere la suya hasta
el primer uso: así un fallo de importación afecta a un solo caso y no a la recolección. Las demás
*fixtures* usan lo que ya existe (esquema, repositorio de la fila A3).

Los proveedores previos se siembran con SQL directo y no con `crear_proveedor`: así un defecto del alta no
puede tapar ni causar el fallo de la actualización o de la desactivación. Las comprobaciones de estado y
de bitácora leen las tablas con una conexión propia del rol de aplicación, no con el repositorio.

Qué cubre cada prueba:

- `TC-12` (`CA-1`): la fila y el asiento `CREAR` exactos, con las variantes de `CA-1`.
- `TC-13` (`CA-1`, regla 8): la bitácora se escribe en la misma transacción que el proveedor (`M-10`).
- `TC-14` (`CA-2`): el RFC duplicado, con el contrato de error completo (`M-3`).
- `TC-15` (`CA-3`): dos altas simultáneas con el mismo RFC; pasa una sola (`M-3`).
- `TC-16` (`CA-8`): la actualización cambia solo lo enviado y asienta `ACTUALIZAR` con antes y después.
- `TC-17` (`CA-8`): la actualización de un proveedor inexistente.
- `TC-18` (`CA-9`): la desactivación conserva todo y asienta `DESACTIVAR`.
- `TC-19` (`CA-9`): desactivar un proveedor que no está `ACTIVO`, o que no existe (`M-5`).
- `TC-20` (`CA-9`): dos desactivaciones simultáneas; la segunda espera el `FOR UPDATE` (`M-6`).
- `TC-43` (`CA-1`, `CA-2`, `CA-8`, `CA-9`, `RNF-16`): el `lock_timeout` vencido en el caso de uso (también el del
  alta, por el índice único del RFC) es `CONCURRENCIA` con la acción `REINTENTAR` y los roles de gestión (los roles no se serializan: solo se ven aquí; la prueba por HTTP está en
  `test_tkt029a_api_proveedores.py`).
- Apoyo (no están en el plan de pruebas del diseño): `obtener_proveedor` y `listar_proveedores` (`CA-6`,
  `CA-7`, que el plan solo prueba por la API en la fila B1) y las constantes de roles y de campos.

Más pruebas de esta fila: `O7` de la auditoría de código (la rama `existente is None` de `crear_proveedor`) y,
de la fila B3, la comprobación de los roles de `REINTENTAR` en `TC-43`.

Mutantes de la fila: `M-3` (quitar la rama del `23505` en `crear_proveedor`) debe poner en rojo `TC-14` y
`TC-15`; `M-6` (leer con `para_cambio=False` al desactivar), `TC-20`; `M-10` (asentar con una sesión
nueva tras confirmar), `TC-13`; `M-5` (`admite_desactivacion` deja pasar a `DESACTIVADO`), `TC-19`.
"""

from __future__ import annotations

import functools
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from psycopg.errors import LockNotAvailable, QueryCanceled
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from cimenta.proveedores.infraestructura import repositorio_proveedor
from contrato_error.excepciones import ConcurrenciaVencida, ConflictoEstado, NoEncontrado
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Base, Hilo
from herramientas.tiempo_de_prueba import esperar_hasta
from tipos_base import Dinero

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, RelojDePrueba, SembrarUsuario

    from cimenta.proveedores.aplicacion.contexto import ContextoProveedores

    Contexto = Callable[[], ContextoProveedores]

CORRELACION = "corr-tkt029a-a4"
ROLES_COMPRAS = frozenset({"COMPRAS"})
CORREO_DEL_CREADOR = "compras@cimenta.test"
CORREO_DEL_SEGUNDO = "compras.dos@cimenta.test"
CONTRASENA = "Clave-Correcta-1"
CREADO_ANTES = datetime(2026, 10, 1, 8, 15, tzinfo=UTC)
MENSAJE_PROVEEDOR_NO_EXISTE = "El proveedor no existe."
MENSAJE_BLOQUEO_VENCIDO = (
    "Otra operación está modificando este proveedor en este momento. Vuelve a intentarlo."
)
ROLES_GESTION_ESPERADOS = ("COMPRAS",)
ROLES_LECTURA_ESPERADOS = (
    "DIRECCION_GENERAL",
    "DIRECTOR_PROYECTOS",
    "RESIDENTE",
    "COMPRAS",
    "ALMACEN",
    "ADMINISTRACION",
)
CAMPOS_CAMBIABLES_ESPERADOS = frozenset({"nombre", "tope_consignacion", "dia_corte", "dia_pago"})

COLUMNAS_DE_PROVEEDOR = (
    "SELECT nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, creado_en, creado_por_id "
    "FROM proveedor WHERE id = %s"
)
COLUMNAS_DE_BITACORA = (
    "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, obra_id, motivo, "
    "datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s ORDER BY accion::text"
)


# --------------------------------------------------------------------------- el entorno


@pytest.fixture
def base(base_de_prueba: str, conectar: Conectar) -> Base:
    return Base(conectar("aplicacion", base_de_prueba))


@pytest.fixture
def contexto_proveedores(motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto de `proveedores` sobre el rol de aplicación, construido al primer uso.

    Es propia de este archivo (nota de ejecución del diseño): no es el `contexto` de presupuesto. El
    módulo se importa al llamarla y no al armar la *fixture*, para que su ausencia sea un fallo de la
    prueba y no un error de preparación.
    """

    def construir() -> ContextoProveedores:
        from cimenta.proveedores.aplicacion.contexto import construir_contexto

        return construir_contexto(proveedor_motor=lambda: motor_aplicacion, reloj=reloj_de_prueba)

    return functools.cache(construir)


@pytest.fixture
def contexto_espera_corta(motor_espera_corta: Engine, reloj_de_prueba: RelojDePrueba) -> Contexto:
    """El contexto de `proveedores` sobre el rol de aplicación con `lock_timeout` de 200 ms (`TC-43`)."""

    def construir() -> ContextoProveedores:
        from cimenta.proveedores.aplicacion.contexto import construir_contexto

        return construir_contexto(proveedor_motor=lambda: motor_espera_corta, reloj=reloj_de_prueba)

    return functools.cache(construir)


@pytest.fixture
def creador(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Usuario de COMPRAS: `creado_por_id` tiene clave foránea a `usuario` (nota de ejecución del diseño)."""
    return sembrar_usuario(CORREO_DEL_CREADOR, CONTRASENA, roles=("COMPRAS",))


@pytest.fixture
def segundo_usuario(sembrar_usuario: SembrarUsuario) -> uuid.UUID:
    """Otro usuario de COMPRAS, para distinguir quién asienta en las pruebas de concurrencia."""
    return sembrar_usuario(CORREO_DEL_SEGUNDO, CONTRASENA, roles=("COMPRAS",), nombre="Luis Prieto")


def _datos(**cambios: Any) -> Any:
    """Un `DatosProveedorNuevo` válido; `cambios` sustituye campos. Se importa dentro de la función para que un fallo de importación no rompa la recolección."""
    from cimenta.proveedores.aplicacion.proveedores import DatosProveedorNuevo

    valores: dict[str, Any] = {
        "nombre": "CoPanel",
        "rfc": "XAXX010101000",
        "tope_consignacion": None,
        "dia_corte": 4,
        "dia_pago": 6,
    }
    valores.update(cambios)
    return DatosProveedorNuevo(**valores)


def _cambios(presentes: set[str], **valores: Any) -> Any:
    """Un `CambiosProveedor`; `presentes` dice qué campos se aplican y `valores` qué traen."""
    from cimenta.proveedores.aplicacion.proveedores import CambiosProveedor

    return CambiosProveedor(presentes=frozenset(presentes), **valores)


def _sembrar(
    base: Base,
    creador_id: uuid.UUID,
    *,
    nombre: str,
    rfc: str,
    estado: str = "ACTIVO",
    tope: str | None = None,
    dia_corte: int = 4,
    dia_pago: int = 6,
) -> uuid.UUID:
    """Inserta una fila en `proveedor` con SQL directo, sin pasar por el repositorio ni el caso de uso."""
    proveedor_id = uuid.uuid4()
    base.ejecutar(
        "INSERT INTO proveedor (id, nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, "
        "creado_en, creado_por_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        proveedor_id,
        nombre,
        rfc,
        estado,
        None if tope is None else Decimal(tope),
        dia_corte,
        dia_pago,
        CREADO_ANTES,
        creador_id,
    )
    return proveedor_id


def _cuenta(base: Base, consulta: LiteralString, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: todas las filas de `proveedor` y los ids de la bitácora."""
    return {
        "proveedores": base.filas("SELECT * FROM proveedor ORDER BY id"),
        "bitacora": base.filas("SELECT id FROM bitacora ORDER BY id"),
    }


def _cuerpo_de_duplicado(*, rfc: str, nombre: str, existente_id: uuid.UUID) -> dict[str, object]:
    """El cuerpo completo del `409` de `RFC_DUPLICADO` que ve COMPRAS: sin acciones (D-2)."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": f"Ya existe un proveedor con el RFC {rfc}.",
        "codigo": "RFC_DUPLICADO",
        "detalle": {
            "proveedor_existente_id": str(existente_id),
            "proveedor_existente": f"{nombre} · {rfc}",
        },
        "acciones": [],
        "correlacion_id": CORRELACION,
    }


def _cuerpo_de_estado(estado: str) -> dict[str, object]:
    """El cuerpo completo del `409` de `ESTADO_NO_PERMITE_OPERACION` al desactivar."""
    return {
        "tipo": "CONFLICTO",
        "mensaje": f"El proveedor no está activo: su estado es {estado}.",
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {"estado_actual": estado},
        "acciones": [],
        "correlacion_id": CORRELACION,
    }


def _hay_alguien_esperando(base: Base, patron: str) -> bool:
    """Una sesión de la base detenida por un bloqueo, con una consulta como `patron`."""
    fila = base.conexion.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND wait_event_type = 'Lock' AND cardinality(pg_blocking_pids(pid)) > 0 "
        "AND query ILIKE %s",
        (patron,),
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def _alguien_espera(base: Base, patron: str) -> Callable[[], bool]:
    """La condición de `esperar_hasta`: alguien detenido en una consulta como `patron`."""
    return lambda: _hay_alguien_esperando(base, patron)


# --------------------------------------------------------------------------- TC-12 · CA-1


def test_hdu004_esc02_alta_guarda_el_proveedor_y_asienta_crear(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-12 · HDU-004 esc. 2 · CA-1 · RN-17 — una fila `ACTIVO` con 4 y 6 y un asiento `CREAR` con el dato exacto.

    El reloj se adelanta para que `creado_en` y `ocurrido_en` sean los del reloj inyectado y no la hora
    de la base. Variantes de `CA-1`: tope `"300000.0000"` con días 2 y 5 (distintos de los de omisión,
    para que un intercambio entre corte y pago no pase), un tope sin decimales que se guarda en la escala
    de la columna, y un tope en cero, que se guarda como `0.0000` y no como `NULL`.
    """
    from cimenta.proveedores.aplicacion.proveedores import crear_proveedor

    reloj_de_prueba.avanzar(timedelta(hours=3))
    ahora = reloj_de_prueba()

    proveedor_id = crear_proveedor(contexto_proveedores(), datos=_datos(), usuario_id=creador)

    assert isinstance(proveedor_id, uuid.UUID)
    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", "XAXX010101000", "ACTIVO", None, 4, 6, ahora, creador)
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, proveedor_id) == [
        (
            "CREAR",
            "proveedor",
            proveedor_id,
            creador,
            ahora,
            None,
            None,
            None,
            {
                "nombre": "CoPanel",
                "rfc": "XAXX010101000",
                "estado": "ACTIVO",
                "tope_consignacion": None,
                "dia_corte": 4,
                "dia_pago": 6,
            },
        )
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1, "Un alta, un solo asiento"

    # Variante: tope con escala completa y días distintos de los de omisión.
    con_tope = crear_proveedor(
        contexto_proveedores(),
        datos=_datos(
            nombre="Tablaroca Sur",
            rfc="TSU010101AB2",
            tope_consignacion=Dinero("300000.0000"),
            dia_corte=2,
            dia_pago=5,
        ),
        usuario_id=creador,
    )
    assert base.filas(COLUMNAS_DE_PROVEEDOR, con_tope) == [
        ("Tablaroca Sur", "TSU010101AB2", "ACTIVO", "300000.0000", 2, 5, ahora, creador)
    ]
    assert base.filas("SELECT datos_despues FROM bitacora WHERE entidad_id = %s", con_tope) == [
        (
            {
                "nombre": "Tablaroca Sur",
                "rfc": "TSU010101AB2",
                "estado": "ACTIVO",
                "tope_consignacion": "300000.0000",
                "dia_corte": 2,
                "dia_pago": 5,
            },
        )
    ]

    # Variante: tope sin decimales, cuantizado a la escala de la columna en la fila y en la bitácora.
    sin_decimales = crear_proveedor(
        contexto_proveedores(),
        datos=_datos(
            nombre="Pinturas Norte", rfc="PNO010101AB3", tope_consignacion=Dinero("300000")
        ),
        usuario_id=creador,
    )
    assert base.filas("SELECT tope_consignacion FROM proveedor WHERE id = %s", sin_decimales) == [
        ("300000.0000",)
    ]
    asiento = base.filas("SELECT datos_despues FROM bitacora WHERE entidad_id = %s", sin_decimales)
    assert asiento[0][0]["tope_consignacion"] == "300000.0000"

    # Variante: un tope en cero es un tope (no consigna nada), no la ausencia de tope.
    en_cero = crear_proveedor(
        contexto_proveedores(),
        datos=_datos(nombre="Herrajes Cero", rfc="HCE010101AB4", tope_consignacion=Dinero("0")),
        usuario_id=creador,
    )
    assert base.filas("SELECT tope_consignacion FROM proveedor WHERE id = %s", en_cero) == [
        ("0.0000",)
    ]
    asiento_cero = base.filas("SELECT datos_despues FROM bitacora WHERE entidad_id = %s", en_cero)
    assert asiento_cero[0][0]["tope_consignacion"] == "0.0000"
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 4
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 4


# --------------------------------------------------------------------------- TC-13 · CA-1, regla 8


def test_hdu004_esc02_alta_bitacora_en_la_misma_transaccion(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-13 · HDU-004 esc. 2 · CA-1 · regla 8 — si asentar falla, no queda el proveedor (`M-10`).

    `asentar` se sustituye por uno que, antes de lanzar, comprueba que corre en la sesión del alta y que
    ve el proveedor todavía sin confirmar: la bitácora se escribe en la misma transacción que el cambio.
    Al lanzar, la transacción se deshace y no queda fila en `proveedor` ni en `bitacora`. Con `asentar`
    en una sesión nueva tras confirmar (`M-10`) el proveedor quedaría guardado y la prueba cae.
    """
    from cimenta.proveedores.aplicacion import proveedores

    class FallaDeBitacora(Exception):
        pass

    visto: dict[str, object] = {}

    def asentar_que_falla(*args: Any, **kwargs: Any) -> None:
        sesion_bd = args[0] if args else kwargs["sesion_bd"]
        visto["en_transaccion"] = sesion_bd.in_transaction()
        visto["proveedores_vistos"] = sesion_bd.execute(
            text("SELECT count(*) FROM proveedor WHERE rfc = 'XAXX010101000'")
        ).scalar_one()
        raise FallaDeBitacora

    monkeypatch.setattr(proveedores, "asentar", asentar_que_falla)
    antes = _foto(base)

    with pytest.raises(FallaDeBitacora):
        proveedores.crear_proveedor(contexto_proveedores(), datos=_datos(), usuario_id=creador)

    assert visto == {"en_transaccion": True, "proveedores_vistos": 1}, (
        "asentar debe correr en la misma sesión, con el proveedor insertado y sin confirmar"
    )
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 0
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0
    assert _foto(base) == antes, "Un alta que falla no deja ninguna fila"


# --------------------------------------------------------------------------- TC-14 · CA-2


def test_hdu004_esc03_alta_rfc_duplicado(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """TC-14 · HDU-004 esc. 3 · CA-2 · INV-28 — `409` `RFC_DUPLICADO` con el proveedor existente y sin acciones (`M-3`).

    El contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo` del catálogo, el detalle
    con el id y el «nombre · RFC» del proveedor que ya existe (no el del intento) y `acciones` vacía
    para cualquier rol, porque no hay acción `VER_PROVEEDOR` (D-2). La unicidad es del motor: sin la
    rama del `23505` (`M-3`) saldría la excepción cruda del motor. Un rechazo no escribe: ni una fila en
    `proveedor` ni un segundo `CREAR`, y la fila existente no cambia. La variante en minúsculas la
    resuelve el DTO (D-1), así que aquí el caso de uso ya recibe el RFC normalizado.
    """
    from cimenta.proveedores.aplicacion.proveedores import (
        ROLES_LECTURA,
        crear_proveedor,
    )

    existente_id = crear_proveedor(
        contexto_proveedores(),
        datos=_datos(nombre="CoPanel", rfc="XAXX010101000", tope_consignacion=Dinero("300000")),
        usuario_id=creador,
    )
    antes = _foto(base)
    esperado = _cuerpo_de_duplicado(
        rfc="XAXX010101000", nombre="CoPanel", existente_id=existente_id
    )

    with pytest.raises(ConflictoEstado) as rechazo:
        crear_proveedor(
            contexto_proveedores(),
            datos=_datos(
                nombre="Otro nombre con el mismo RFC",
                rfc="XAXX010101000",
                tope_consignacion=None,
                dia_corte=1,
                dia_pago=2,
            ),
            usuario_id=creador,
        )

    error = rechazo.value
    assert error.estado_http == 409
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    # Sin acción para nadie: ni la gestión ni quien solo lee reciben `VER_PROVEEDOR` (D-2).
    assert error.acciones == ()
    for rol in ROLES_LECTURA:
        assert error.cuerpo(frozenset({rol}), CORRELACION) == esperado, rol

    assert _foto(base) == antes, "El rechazo no escribe"
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 1
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CREAR'") == 1
    assert base.filas(COLUMNAS_DE_PROVEEDOR, existente_id)[0][:6] == (
        "CoPanel",
        "XAXX010101000",
        "ACTIVO",
        "300000.0000",
        4,
        6,
    ), "El proveedor existente no cambia"


def test_hdu004_esc03_alta_rfc_duplicado_sin_fila_visible_relanza_el_error(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O7 de la auditoría · HDU-004 esc. 3 · CA-2 — un `23505` de `uq_proveedor_rfc` sin fila visible se relanza tal cual, no como `409`.

    Documenta la rama `existente is None` de `crear_proveedor`: si tras el `23505` la búsqueda por RFC no
    encuentra ninguna fila (la que chocó se borró entre las dos transacciones), el caso de uso no inventa un
    `RFC_DUPLICADO` sin proveedor existente que enseñar: relanza el `DBAPIError` original, con su
    `SQLSTATE` y su restricción. El alta que falla no deja ninguna fila ni asiento.
    """
    from cimenta.proveedores.aplicacion.proveedores import crear_proveedor

    crear_proveedor(contexto_proveedores(), datos=_datos(), usuario_id=creador)
    antes = _foto(base)
    consultados: list[str] = []

    def sin_fila_visible(_sesion_bd: object, rfc: str) -> None:
        consultados.append(rfc)

    monkeypatch.setattr(repositorio_proveedor, "leer_proveedor_por_rfc", sin_fila_visible)

    with pytest.raises(DBAPIError) as rechazo:
        crear_proveedor(
            contexto_proveedores(),
            datos=_datos(nombre="Otro nombre con el mismo RFC"),
            usuario_id=creador,
        )

    original: Any = rechazo.value.orig
    assert getattr(original, "sqlstate", None) == "23505"
    assert getattr(getattr(original, "diag", None), "constraint_name", None) == "uq_proveedor_rfc"
    assert consultados == ["XAXX010101000"], "Busca al existente por el RFC del intento, una vez"
    assert _foto(base) == antes, "El rechazo no escribe"


@pytest.mark.parametrize(
    ("clase_de_error", "codigo"),
    [
        pytest.param(QueryCanceled, "TIEMPO_EJECUCION_VENCIDO", id="57014"),
        pytest.param(LockNotAvailable, "BLOQUEO_VENCIDO", id="55P03"),
    ],
)
def test_hdu004_esc03_alta_rfc_duplicado_con_lectura_vencida_es_concurrencia(
    clase_de_error: type[Exception],
    codigo: str,
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-43 · HDU-004 esc. 3 · RNF-16 · M-14c — si la búsqueda del RFC duplicado vence (`57014` o `55P03`), es `CONCURRENCIA`, no `RFC_DUPLICADO` ni la excepción cruda.

    El `23505` de `uq_proveedor_rfc` manda al caso de uso a la rama de la búsqueda. Si esa búsqueda lanza un
    `DBAPIError` con `57014` (`statement_timeout`) o `55P03` (`lock_timeout`), el error tiene que atravesar
    `_traducir_concurrencia` y salir como `ConcurrenciaVencida` con el `codigo` de su `SQLSTATE`, con la causa
    en `__cause__`. Con la búsqueda fuera del gestor (`M-14c`) el `DBAPIError` escapa crudo y esta prueba cae.
    No escribe nada: ni fila ni asiento.
    """
    from cimenta.proveedores.aplicacion.proveedores import crear_proveedor

    _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    antes = _foto(base)
    consultados: list[str] = []
    causa = OperationalError(
        "SELECT id FROM proveedor WHERE rfc = %s",
        None,
        clase_de_error("cancelado en la búsqueda del RFC"),
    )

    def busqueda_vencida(_sesion_bd: object, rfc: str) -> None:
        consultados.append(rfc)
        raise causa

    monkeypatch.setattr(repositorio_proveedor, "leer_proveedor_por_rfc", busqueda_vencida)

    with pytest.raises(ConcurrenciaVencida) as vencido:
        crear_proveedor(
            contexto_proveedores(),
            datos=_datos(nombre="Otro nombre con el mismo RFC"),
            usuario_id=creador,
        )

    error = vencido.value
    assert error.__cause__ is causa, "La causa es la búsqueda vencida, no el 23505"
    assert getattr(getattr(causa.__context__, "orig", None), "sqlstate", None) == "23505", (
        "La búsqueda corre dentro de la rama del 23505 de uq_proveedor_rfc"
    )
    assert consultados == ["XAXX010101000"], "Busca al existente por el RFC del intento, una vez"
    assert error.estado_http == 409
    assert error.codigo.value == codigo
    cuerpo = error.cuerpo(ROLES_COMPRAS, CORRELACION)
    assert cuerpo["tipo"] == "CONCURRENCIA"
    assert cuerpo["codigo"] == codigo
    assert _foto(base) == antes, "Un rechazo por concurrencia no escribe"


# --------------------------------------------------------------------------- TC-15 · CA-3


def test_hdu004_esc03_dos_altas_concurrentes_mismo_rfc(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    segundo_usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-15 · HDU-004 esc. 3 · CA-3 · `uq_proveedor_rfc` — dos altas con el mismo RFC: pasa una sola (`M-3`).

    Determinista y sin `sleep`. El hilo A se pausa dentro de `repositorio_proveedor.insertar_proveedor`,
    con la fila ya insertada y sin confirmar; el hilo B arranca y su `INSERT` queda detenido en el índice
    único (la prueba lo espera con `esperar_hasta` sobre `pg_stat_activity` y `pg_blocking_pids`);
    entonces se libera a A, que confirma. B recibe la violación `23505` y responde `RFC_DUPLICADO` con el
    proveedor de A, no un `500` ni otro código. El hilo pausado se libera siempre en `finally`.

    Requiere que el caso de uso llame a `repositorio_proveedor.insertar_proveedor` por el módulo, no por
    un nombre importado: es lo que permite la envoltura (mismo patrón que `repositorio_obra` en TKT-012a).
    """
    from cimenta.proveedores.aplicacion import proveedores

    rfc = "CPN010101AB9"
    ctx = contexto_proveedores()
    original = repositorio_proveedor.insertar_proveedor
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A":
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_proveedor, "insertar_proveedor", envoltura)

    a = Hilo(
        "A",
        lambda: proveedores.crear_proveedor(
            ctx, datos=_datos(nombre="Proveedor del hilo A", rfc=rfc), usuario_id=creador
        ),
    )
    b = Hilo(
        "B",
        lambda: proveedores.crear_proveedor(
            ctx, datos=_datos(nombre="Proveedor del hilo B", rfc=rfc), usuario_id=segundo_usuario
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), "El hilo A no llegó a insertar el proveedor"
        b.start()
        espera = esperar_hasta(_alguien_espera(base, "%INSERT INTO proveedor (%"), 5.0)
        assert espera, (
            f"B no quedó detenido en el índice único mientras A tenía la fila sin confirmar: {b.error!r}"
        )
        assert b.is_alive()
        assert _cuenta(base, "SELECT count(*) FROM proveedor") == 0, (
            "La fila de A no se ve mientras no confirma"
        )
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    proveedor_de_a = a.exito()
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_COMPRAS, CORRELACION) == _cuerpo_de_duplicado(
        rfc=rfc, nombre="Proveedor del hilo A", existente_id=proveedor_de_a
    )
    assert base.filas("SELECT id, rfc, nombre, creado_por_id FROM proveedor") == [
        (proveedor_de_a, rfc, "Proveedor del hilo A", creador)
    ]
    assert base.filas("SELECT entidad_id, usuario_id FROM bitacora WHERE accion = 'CREAR'") == [
        (proveedor_de_a, creador)
    ]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1


# --------------------------------------------------------------------------- TC-16 · CA-8


def test_tkt029a_actualizar_cambia_solo_lo_enviado_y_asienta(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-16 · CA-8 — solo los campos presentes cambian; `ACTUALIZAR` lleva el antes y el después de esos campos.

    `dia_corte` 2 y tope `"250000.0000"` sobre un proveedor sin tope: el asiento trae exactamente esos
    dos campos con su valor anterior y el nuevo; RFC, estado, nombre, `dia_pago` y `creado_en` quedan
    intactos. Variantes: un campo con valor pero fuera de `presentes` no se aplica; el tope presente y
    `None` deja la columna en `NULL`; un proveedor `DESACTIVADO` admite el cambio y sigue
    `DESACTIVADO` (D-3).
    """
    from cimenta.proveedores.aplicacion.proveedores import actualizar_proveedor

    reloj_de_prueba.avanzar(timedelta(hours=2))
    ahora = reloj_de_prueba()
    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")

    actualizar_proveedor(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        cambios=_cambios(
            {"dia_corte", "tope_consignacion"}, dia_corte=2, tope_consignacion=Dinero("250000")
        ),
        usuario_id=creador,
    )

    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", "XAXX010101000", "ACTIVO", "250000.0000", 2, 6, CREADO_ANTES, creador)
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, proveedor_id) == [
        (
            "ACTUALIZAR",
            "proveedor",
            proveedor_id,
            creador,
            ahora,
            None,
            None,
            {"dia_corte": 4, "tope_consignacion": None},
            {"dia_corte": 2, "tope_consignacion": "250000.0000"},
        )
    ]

    # Variante: un valor que viaja pero no está en `presentes` no se aplica ni se asienta.
    reloj_de_prueba.avanzar(timedelta(minutes=2))
    momento_dia_pago = reloj_de_prueba()
    actualizar_proveedor(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        cambios=_cambios({"dia_pago"}, nombre="Nombre que no debe aplicarse", dia_pago=7),
        usuario_id=creador,
    )
    assert base.filas("SELECT nombre, dia_pago FROM proveedor WHERE id = %s", proveedor_id) == [
        ("CoPanel", 7)
    ]
    assert base.filas(
        "SELECT datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s AND ocurrido_en = %s",
        proveedor_id,
        momento_dia_pago,
    ) == [({"dia_pago": 6}, {"dia_pago": 7})]

    # Variante: el tope presente y `None` deja la columna en NULL, con el valor anterior en `datos_antes`.
    antes_de_nulo = _cuenta(
        base, "SELECT count(*) FROM bitacora WHERE entidad_id = %s", proveedor_id
    )
    reloj_de_prueba.avanzar(timedelta(minutes=5))
    momento_nulo = reloj_de_prueba()
    actualizar_proveedor(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        cambios=_cambios({"tope_consignacion"}, tope_consignacion=None),
        usuario_id=creador,
    )
    assert base.filas(
        "SELECT tope_consignacion, nombre, dia_corte, dia_pago FROM proveedor WHERE id = %s",
        proveedor_id,
    ) == [(None, "CoPanel", 2, 7)]
    assert base.filas(
        "SELECT datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s AND ocurrido_en = %s",
        proveedor_id,
        momento_nulo,
    ) == [({"tope_consignacion": "250000.0000"}, {"tope_consignacion": None})]
    assert (
        _cuenta(base, "SELECT count(*) FROM bitacora WHERE entidad_id = %s", proveedor_id)
        == antes_de_nulo + 1
    )

    # Variante (D-3): un proveedor DESACTIVADO también admite el cambio de datos.
    desactivado = _sembrar(
        base,
        creador,
        nombre="Proveedor retirado",
        rfc="RET010101AB1",
        estado="DESACTIVADO",
        tope="100000.0000",
    )
    actualizar_proveedor(
        contexto_proveedores(),
        proveedor_id=desactivado,
        cambios=_cambios({"nombre"}, nombre="Proveedor retirado y renombrado"),
        usuario_id=creador,
    )
    assert base.filas(COLUMNAS_DE_PROVEEDOR, desactivado) == [
        (
            "Proveedor retirado y renombrado",
            "RET010101AB1",
            "DESACTIVADO",
            "100000.0000",
            4,
            6,
            CREADO_ANTES,
            creador,
        )
    ]
    assert base.filas(
        "SELECT accion::text, datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s",
        desactivado,
    ) == [
        (
            "ACTUALIZAR",
            {"nombre": "Proveedor retirado"},
            {"nombre": "Proveedor retirado y renombrado"},
        )
    ]


@pytest.mark.parametrize(
    "presentes",
    [
        pytest.param(set(), id="presentes_vacio"),
        pytest.param({"rfc"}, id="solo_clave_ajena_rfc"),
        pytest.param({"estado"}, id="solo_clave_ajena_estado"),
        pytest.param({"dia_corte", "estado"}, id="campo_valido_mas_clave_ajena"),
    ],
)
def test_tkt029a_actualizar_rechaza_presentes_vacio_o_ajeno(
    presentes: set[str],
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
) -> None:
    """F003 · CA-8 — `presentes` vacío o con claves fuera de `CAMPOS_CAMBIABLES` lanza `ValueError` sin escribir.

    Un `PATCH` sin campos cambiables o con el RFC o el estado no debe llegar a la base: el caso de uso lo
    rechaza antes de abrir la transacción, así que la fila queda como estaba y no hay asiento `ACTUALIZAR`
    (ni siquiera uno con `datos_antes` y `datos_despues` vacíos). Una clave ajena junto a un campo válido
    también se rechaza entera: no se aplica el campo válido a medias.
    """
    from cimenta.proveedores.aplicacion.proveedores import actualizar_proveedor

    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    antes = _foto(base)
    fila_antes = base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id)

    with pytest.raises(ValueError):
        actualizar_proveedor(
            contexto_proveedores(),
            proveedor_id=proveedor_id,
            cambios=_cambios(presentes, dia_corte=2),
            usuario_id=creador,
        )

    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == fila_antes, "La fila no cambia"
    assert _foto(base) == antes, "El rechazo no escribe"
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0, "Ni un asiento ACTUALIZAR"


# --------------------------------------------------------------------------- TC-17 · CA-8


def test_tkt029a_actualizar_inexistente(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """TC-17 · CA-8 — `404` `NO_ENCONTRADO` con `recurso="proveedor"` y ningún asiento.

    Hay un proveedor real, para que el rechazo sea por el id y no por tabla vacía; no cambia.
    """
    from cimenta.proveedores.aplicacion.proveedores import (
        MENSAJE_PROVEEDOR_NO_EXISTE as mensaje_del_modulo,
    )
    from cimenta.proveedores.aplicacion.proveedores import actualizar_proveedor

    assert mensaje_del_modulo == MENSAJE_PROVEEDOR_NO_EXISTE
    _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    antes = _foto(base)

    with pytest.raises(NoEncontrado) as rechazo:
        actualizar_proveedor(
            contexto_proveedores(),
            proveedor_id=uuid.uuid4(),
            cambios=_cambios({"dia_corte"}, dia_corte=2),
            usuario_id=creador,
        )

    error = rechazo.value
    assert error.estado_http == 404
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
        "recurso": "proveedor",
        "correlacion_id": CORRELACION,
    }
    assert _foto(base) == antes, "El rechazo no escribe"
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 0


# --------------------------------------------------------------------------- TC-18 · CA-9


def test_hdu004_esc12_desactivar_conserva_todo_y_asienta(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-18 · HDU-004 esc. 12 · CA-9 — pasa a `DESACTIVADO`; nada más cambia; `DESACTIVAR` lleva el motivo.

    El proveedor tiene tope y días distintos de los de omisión, para comprobar que se conservan. El
    asiento trae el motivo recibido (sin cambios), `datos_antes` `ACTIVO` y `datos_despues`
    `DESACTIVADO`, con el reloj inyectado.
    """
    from cimenta.proveedores.aplicacion.proveedores import desactivar_proveedor

    reloj_de_prueba.avanzar(timedelta(hours=1))
    ahora = reloj_de_prueba()
    proveedor_id = _sembrar(
        base,
        creador,
        nombre="CoPanel",
        rfc="XAXX010101000",
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    otro = _sembrar(base, creador, nombre="Tablaroca Sur", rfc="TSU010101AB2")
    vecino_antes = base.filas(COLUMNAS_DE_PROVEEDOR, otro)

    desactivar_proveedor(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        motivo="Entregó material fuera de especificación",
        usuario_id=creador,
    )

    assert base.filas(COLUMNAS_DE_PROVEEDOR, proveedor_id) == [
        ("CoPanel", "XAXX010101000", "DESACTIVADO", "300000.0000", 2, 5, CREADO_ANTES, creador)
    ]
    assert base.filas(COLUMNAS_DE_BITACORA, proveedor_id) == [
        (
            "DESACTIVAR",
            "proveedor",
            proveedor_id,
            creador,
            ahora,
            None,
            "Entregó material fuera de especificación",
            {"estado": "ACTIVO"},
            {"estado": "DESACTIVADO"},
        )
    ]
    assert base.filas(COLUMNAS_DE_PROVEEDOR, otro) == vecino_antes, "Otro proveedor no cambia"
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1
    assert _cuenta(base, "SELECT count(*) FROM proveedor") == 2


# --------------------------------------------------------------------------- TC-19 · CA-9


def test_hdu004_esc12_desactivar_un_desactivado_o_inexistente(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """TC-19 · HDU-004 esc. 12 · CA-9 — solo un `ACTIVO` se desactiva (`M-5`); un inexistente es `404`.

    El contrato completo del `409`: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), `codigo`
    `ESTADO_NO_PERMITE_OPERACION`, `detalle` con el `estado_actual` real y `acciones` vacía. Se prueba
    sobre un proveedor que acaba de desactivarse (segunda desactivación) y sobre uno en `BAJA`; en ambos
    la fila queda como estaba y no hay asiento nuevo. Con una regla que dejara pasar a `DESACTIVADO`
    (`M-5`) la segunda desactivación se asentaría y la prueba cae.
    """
    from cimenta.proveedores.aplicacion.proveedores import desactivar_proveedor

    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    en_baja = _sembrar(
        base, creador, nombre="Proveedor dado de baja", rfc="BAJ010101AB1", estado="BAJA"
    )

    desactivar_proveedor(
        contexto_proveedores(),
        proveedor_id=proveedor_id,
        motivo="Primera desactivación",
        usuario_id=creador,
    )
    antes = _foto(base)
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DESACTIVAR'") == 1

    for objetivo, estado in ((proveedor_id, "DESACTIVADO"), (en_baja, "BAJA")):
        with pytest.raises(ConflictoEstado) as rechazo:
            desactivar_proveedor(
                contexto_proveedores(),
                proveedor_id=objetivo,
                motivo="Segundo intento",
                usuario_id=creador,
            )
        error = rechazo.value
        assert error.estado_http == 409, estado
        assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == _cuerpo_de_estado(estado), estado
        assert _foto(base) == antes, f"El rechazo no escribe ({estado})"

    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", en_baja) == [("BAJA",)]
    assert base.filas(
        "SELECT motivo FROM bitacora WHERE entidad_id = %s AND accion = 'DESACTIVAR'", proveedor_id
    ) == [("Primera desactivación",)]

    # Inexistente: `404`, sin asiento ni cambio.
    with pytest.raises(NoEncontrado) as inexistente:
        desactivar_proveedor(
            contexto_proveedores(),
            proveedor_id=uuid.uuid4(),
            motivo="No existe",
            usuario_id=creador,
        )
    assert inexistente.value.estado_http == 404
    assert inexistente.value.cuerpo(ROLES_COMPRAS, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
        "recurso": "proveedor",
        "correlacion_id": CORRELACION,
    }
    assert _foto(base) == antes, "El rechazo no escribe (inexistente)"


# --------------------------------------------------------------------------- TC-20 · CA-9


def test_hdu004_esc12_dos_desactivaciones_concurrentes(
    contexto_proveedores: Contexto,
    base: Base,
    creador: uuid.UUID,
    segundo_usuario: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-20 · HDU-004 esc. 12 · CA-9 — dos desactivaciones a la vez: B espera el `FOR UPDATE` y ve `DESACTIVADO` (`M-6`).

    Determinista y sin `sleep`. El hilo A se pausa dentro de `repositorio_proveedor.leer_proveedor`, en la
    llamada con `para_cambio=True`, con el `SELECT ... FOR UPDATE` ya tomado; el hilo B arranca y su
    lectura bloqueante queda detenida (la prueba lo espera sobre `pg_stat_activity` y `pg_blocking_pids`);
    entonces se libera a A, que desactiva y confirma. B lee `DESACTIVADO` y responde
    `ESTADO_NO_PERMITE_OPERACION`. Con la lectura sin `FOR UPDATE` (`M-6`) A nunca llega a la pausa y la
    prueba cae al esperarla; si B leyera `ACTIVO` quedarían dos asientos `DESACTIVAR`. El hilo pausado se
    libera siempre en `finally`.
    """
    from cimenta.proveedores.aplicacion import proveedores

    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    ctx = contexto_proveedores()
    original = repositorio_proveedor.leer_proveedor
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A" and kwargs.get("para_cambio"):
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_proveedor, "leer_proveedor", envoltura)

    a = Hilo(
        "A",
        lambda: proveedores.desactivar_proveedor(
            ctx, proveedor_id=proveedor_id, motivo="Motivo del hilo A", usuario_id=creador
        ),
    )
    b = Hilo(
        "B",
        lambda: proveedores.desactivar_proveedor(
            ctx, proveedor_id=proveedor_id, motivo="Motivo del hilo B", usuario_id=segundo_usuario
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), (
            "El hilo A no llegó a leer el proveedor con FOR UPDATE"
        )
        b.start()
        espera = esperar_hasta(_alguien_espera(base, "%FROM proveedor%FOR UPDATE%"), 5.0)
        assert espera, (
            f"B no quedó esperando el bloqueo del proveedor mientras A lo tenía: {b.error!r}"
        )
        assert b.is_alive()
        assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [
            ("ACTIVO",)
        ], "La desactivación de A no se ve mientras no confirma"
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_COMPRAS, CORRELACION) == _cuerpo_de_estado("DESACTIVADO")
    assert base.filas("SELECT estado FROM proveedor WHERE id = %s", proveedor_id) == [
        ("DESACTIVADO",)
    ]
    assert base.filas(
        "SELECT usuario_id, motivo, datos_antes, datos_despues FROM bitacora "
        "WHERE accion = 'DESACTIVAR'"
    ) == [(creador, "Motivo del hilo A", {"estado": "ACTIVO"}, {"estado": "DESACTIVADO"})]
    assert _cuenta(base, "SELECT count(*) FROM bitacora") == 1


# --------------------------------------------------------------------------- TC-43 · CA-8 · CA-9 · RNF-16


@pytest.mark.parametrize("operacion", ["actualizar", "desactivar"])
def test_tkt029a_bloqueo_vencido_en_el_caso_de_uso_ofrece_reintentar_a_gestion(
    operacion: str,
    contexto_espera_corta: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    creador: uuid.UUID,
) -> None:
    """TC-43 · CA-8 · CA-9 · RNF-16 — otra sesión retiene la fila: `ConcurrenciaVencida` `BLOQUEO_VENCIDO` con `REINTENTAR` para COMPRAS (`M-13`).

    El contexto corre sobre el rol de aplicación con `lock_timeout` de 200 ms y otra sesión tiene la fila
    de `proveedor` con `FOR UPDATE`. El caso de uso lanza `ConcurrenciaVencida` (no el `DBAPIError`
    crudo): `codigo` `BLOQUEO_VENCIDO`, `espera_maxima_ms` 5000 (el `lock_timeout` del rol, no los 200 ms
    de la prueba), `reintentar_en_s` 1 y una sola acción `REINTENTAR` con el método y la ruta de ESA
    operación y `COMPRAS` como único rol que la ejecuta. El cuerpo no lleva `regla` y la acción llega
    también a quien no es de gestión. Nada cambia: ni la fila ni la bitácora. La causa raíz se conserva
    en `__cause__` (el `DBAPIError` del driver, `55P03`) para el diagnóstico.
    """
    from cimenta.proveedores.aplicacion import proveedores

    proveedor_id = _sembrar(base, creador, nombre="CoPanel", rfc="XAXX010101000")
    antes = _foto(base)
    ctx = contexto_espera_corta()
    metodo, ruta = (
        ("PATCH", f"/api/v1/proveedores/{proveedor_id}")
        if operacion == "actualizar"
        else ("POST", f"/api/v1/proveedores/{proveedor_id}/desactivacion")
    )

    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute("SELECT id FROM proveedor WHERE id = %s FOR UPDATE", (proveedor_id,))
        with pytest.raises(ConcurrenciaVencida) as vencido:
            if operacion == "actualizar":
                proveedores.actualizar_proveedor(
                    ctx,
                    proveedor_id=proveedor_id,
                    cambios=_cambios({"dia_corte"}, dia_corte=2),
                    usuario_id=creador,
                )
            else:
                proveedores.desactivar_proveedor(
                    ctx, proveedor_id=proveedor_id, motivo="Ya no surte", usuario_id=creador
                )
    finally:
        retenedor.rollback()

    error = vencido.value
    causa = error.__cause__
    assert isinstance(causa, DBAPIError), causa
    assert getattr(causa.orig, "sqlstate", None) == "55P03", causa.orig
    assert error.estado_http == 409
    assert error.codigo.value == "BLOQUEO_VENCIDO"
    assert error.espera_maxima_ms == 5000
    assert error.reintentar_en_s == 1
    assert error.cabeceras() == {"Retry-After": "1"}
    assert [(a.clave, a.metodo.value, a.ruta, a.roles_permitidos) for a in error.acciones] == [
        ("REINTENTAR", metodo, ruta, frozenset({"COMPRAS"}))
    ]
    esperado = {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO_VENCIDO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [{"clave": "REINTENTAR", "metodo": metodo, "ruta": ruta}],
        "correlacion_id": CORRELACION,
    }
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    assert error.cuerpo(frozenset({"RESIDENTE"}), CORRELACION) == esperado
    assert _foto(base) == antes, "Un bloqueo vencido no escribe"


def test_hdu004_esc03_alta_con_bloqueo_vencido_en_el_caso_de_uso_ofrece_reintentar_a_gestion(
    contexto_espera_corta: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
    creador: uuid.UUID,
) -> None:
    """HDU-004 esc. 3 · TC-43 · CA-1 · CA-2 · RNF-16 — otra sesión inserta el mismo RFC sin confirmar: `ConcurrenciaVencida` `BLOQUEO_VENCIDO` con `REINTENTAR` para COMPRAS (`M-13`).

    El contexto corre sobre el rol de aplicación con `lock_timeout` de 200 ms. Una segunda conexión inserta
    un proveedor con el mismo RFC y no confirma; el `INSERT` del alta espera en `uq_proveedor_rfc` hasta
    que vence el tiempo. El caso de uso lanza `ConcurrenciaVencida` (no el `DBAPIError` crudo ni
    `ConflictoEstado` `RFC_DUPLICADO`: no hay un proveedor confirmado que mostrar): `codigo`
    `BLOQUEO_VENCIDO`, `espera_maxima_ms` 5000, `reintentar_en_s` 1 y una sola acción `REINTENTAR` `POST`
    a `/api/v1/proveedores` con `COMPRAS` como único rol. El cuerpo no lleva `regla` y la acción llega
    también a quien no es de gestión. La causa raíz se conserva en `__cause__` (`55P03`). No escribe:
    ni fila ni asiento (el retenedor hace `rollback`). El `23505` de un RFC ya confirmado sigue siendo
    `RFC_DUPLICADO` (`TC-14` y `TC-15`, que esta fila no toca).
    """
    from cimenta.proveedores.aplicacion import proveedores

    antes = _foto(base)
    ctx = contexto_espera_corta()

    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute(
            "INSERT INTO proveedor (id, nombre, rfc, estado, tope_consignacion, dia_corte, dia_pago, "
            "creado_en, creado_por_id) VALUES (%s, %s, %s, 'ACTIVO', NULL, 4, 6, %s, %s)",
            (uuid.uuid4(), "Alta sin confirmar", "XAXX010101000", CREADO_ANTES, creador),
        )
        with pytest.raises(ConcurrenciaVencida) as vencido:
            proveedores.crear_proveedor(ctx, datos=_datos(), usuario_id=creador)
    finally:
        retenedor.rollback()

    error = vencido.value
    causa = error.__cause__
    assert isinstance(causa, DBAPIError), causa
    assert getattr(causa.orig, "sqlstate", None) == "55P03", causa.orig
    assert error.estado_http == 409
    assert error.codigo.value == "BLOQUEO_VENCIDO"
    assert error.espera_maxima_ms == 5000
    assert error.reintentar_en_s == 1
    assert error.cabeceras() == {"Retry-After": "1"}
    assert [(a.clave, a.metodo.value, a.ruta, a.roles_permitidos) for a in error.acciones] == [
        ("REINTENTAR", "POST", "/api/v1/proveedores", frozenset({"COMPRAS"}))
    ]
    esperado = {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO_VENCIDO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [{"clave": "REINTENTAR", "metodo": "POST", "ruta": "/api/v1/proveedores"}],
        "correlacion_id": CORRELACION,
    }
    assert error.cuerpo(ROLES_COMPRAS, CORRELACION) == esperado
    assert error.cuerpo(frozenset({"RESIDENTE"}), CORRELACION) == esperado
    assert _foto(base) == antes, "Un alta con bloqueo vencido no escribe"


# --------------------------------------------------------------------------- apoyo · CA-7


def test_tkt029a_obtener_proveedor(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """Apoyo · CA-7 — `obtener_proveedor` devuelve la fila completa, también `DESACTIVADO`, y un inexistente es `404`.

    El plan de pruebas solo prueba la lectura por la API (fila B1); aquí se fija el caso de uso. No
    escribe: ni bitácora ni cambios.
    """
    from cimenta.proveedores.aplicacion.proveedores import obtener_proveedor

    activo = _sembrar(
        base,
        creador,
        nombre="CoPanel",
        rfc="XAXX010101000",
        tope="300000.0000",
        dia_corte=2,
        dia_pago=5,
    )
    desactivado = _sembrar(
        base, creador, nombre="Proveedor retirado", rfc="RET010101AB1", estado="DESACTIVADO"
    )
    antes = _foto(base)

    fila = obtener_proveedor(contexto_proveedores(), activo)
    assert fila.id == activo
    assert fila.nombre == "CoPanel"
    assert fila.rfc == "XAXX010101000"
    assert fila.estado == "ACTIVO"
    assert fila.tope_consignacion is not None
    assert fila.tope_consignacion.serializar() == "300000.0000"
    assert (fila.dia_corte, fila.dia_pago) == (2, 5)
    assert fila.creado_en == CREADO_ANTES

    retirado = obtener_proveedor(contexto_proveedores(), desactivado)
    assert retirado.estado == "DESACTIVADO"
    assert retirado.tope_consignacion is None

    with pytest.raises(NoEncontrado) as inexistente:
        obtener_proveedor(contexto_proveedores(), uuid.uuid4())
    assert inexistente.value.estado_http == 404
    assert inexistente.value.cuerpo(ROLES_COMPRAS, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_PROVEEDOR_NO_EXISTE,
        "recurso": "proveedor",
        "correlacion_id": CORRELACION,
    }
    assert _foto(base) == antes, "Leer no escribe"


# --------------------------------------------------------------------------- apoyo · CA-6


def test_tkt029a_listar_recorta_q_y_calcula_el_desplazamiento(
    contexto_proveedores: Contexto, base: Base, creador: uuid.UUID
) -> None:
    """Apoyo · CA-6 · D-8 · D-9 — `listar_proveedores` pagina por número de página, recorta `q` y trata el blanco como «sin filtro».

    Cinco proveedores: tres `ACTIVO` (de «Acero Norte» a «Pinturas Sur») y dos `DESACTIVADO`. La página 2
    de tamaño 2 es el desplazamiento 2 del orden por nombre; `q` con espacios alrededor equivale a `q`
    recortado, y `q` solo de espacios equivale a no filtrar. Una página inalcanzable da `elementos` vacía
    con el total real. `ProveedoresConsultados.elementos` es una tupla.
    """
    from cimenta.proveedores.aplicacion.proveedores import listar_proveedores

    ids = {
        nombre: _sembrar(base, creador, nombre=nombre, rfc=rfc, estado=estado)
        for nombre, rfc, estado in (
            ("Acero Norte", "ANO010101AB1", "ACTIVO"),
            ("Herrajes Yuta", "HYU980101AB3", "DESACTIVADO"),
            ("Pinturas Sur", "PSU010101AB1", "ACTIVO"),
            ("Tablaroca Sur", "TSU010101AB2", "ACTIVO"),
            ("Vidrios Este", "VES010101AB1", "DESACTIVADO"),
        )
    }
    todos = frozenset({"ACTIVO", "DESACTIVADO"})
    contexto = contexto_proveedores()

    segunda = listar_proveedores(contexto, estados=todos, q=None, pagina=2, tamano_pagina=2)
    assert isinstance(segunda.elementos, tuple)
    assert [f.id for f in segunda.elementos] == [ids["Pinturas Sur"], ids["Tablaroca Sur"]]
    assert (segunda.pagina, segunda.tamano_pagina, segunda.total) == (2, 2, 5)

    solo_activos = listar_proveedores(
        contexto, estados=frozenset({"ACTIVO"}), q=None, pagina=1, tamano_pagina=50
    )
    assert [f.nombre for f in solo_activos.elementos] == [
        "Acero Norte",
        "Pinturas Sur",
        "Tablaroca Sur",
    ]
    assert solo_activos.total == 3

    con_espacios = listar_proveedores(
        contexto, estados=todos, q="  sur  ", pagina=1, tamano_pagina=50
    )
    assert [f.nombre for f in con_espacios.elementos] == ["Pinturas Sur", "Tablaroca Sur"]
    assert con_espacios.total == 2

    en_blanco = listar_proveedores(contexto, estados=todos, q="   ", pagina=1, tamano_pagina=50)
    assert en_blanco.total == 5
    assert len(en_blanco.elementos) == 5

    inalcanzable = listar_proveedores(contexto, estados=todos, q=None, pagina=10, tamano_pagina=2)
    assert inalcanzable.elementos == ()
    assert inalcanzable.total == 5
    assert inalcanzable.pagina == 10


# --------------------------------------------------------------------------- apoyo · constantes


def test_tkt029a_roles_y_campos_cambiables_del_caso_de_uso() -> None:
    """Apoyo — las constantes de «Aplicación» sin otra lectura posible: roles en el orden de `x-roles` y campos cambiables.

    Sin base de datos. `ROLES_GESTION` es solo COMPRAS; `ROLES_LECTURA` son los seis roles en el orden del
    borrador; `CAMPOS_CAMBIABLES` no contiene el RFC ni el estado, que un `PATCH` no puede tocar.
    """
    from cimenta.proveedores.aplicacion.proveedores import (
        CAMPOS_CAMBIABLES,
        ROLES_GESTION,
        ROLES_LECTURA,
    )
    from cimenta.proveedores.aplicacion.proveedores import (
        MENSAJE_PROVEEDOR_NO_EXISTE as mensaje_del_modulo,
    )

    assert ROLES_GESTION == ROLES_GESTION_ESPERADOS
    assert ROLES_LECTURA == ROLES_LECTURA_ESPERADOS
    assert CAMPOS_CAMBIABLES == CAMPOS_CAMBIABLES_ESPERADOS
    assert mensaje_del_modulo == MENSAJE_PROVEEDOR_NO_EXISTE
