"""Concurrencia del congelado, fila B2 de TKT-017b1 (TC-B08, TC-B09 y TC-B10 · CA-B6 · RN-01).

Todo el ciclo de vida de la línea base de una obra se serializa con un `SELECT ... FOR UPDATE` sobre la
fila de `obra` (`bloquear_obra`); el congelado la toma antes que la fila de la línea base. Sin ese
bloqueo, un congelado podría copiar una jerarquía que un reemplazo está borrando, o dos congelados de la
misma obra podrían leer "sin otra congelada" los dos.

`TC-B08` lanza los dos congelados a la vez con `threading.Barrier`; como su resultado depende de quién
llega primero, solo `TC-B09` y `TC-B10` demuestran el bloqueo y su orden: un hilo se pausa dentro de un
paso del repositorio (`copiar_conceptos` o `insertar_niveles`), con la obra ya bloqueada y filas sin
confirmar, y la prueba espera, mirando `pg_blocking_pids`, a que el otro hilo quede detenido en el
`SELECT ... FROM obra ... FOR UPDATE`. Ninguna espera es un `sleep` fijo: cada una sondea una condición
con un tope que hace fallar la prueba, y todo hilo pausado se libera en `finally`.

`E-5` (diseño «Experimentos previos»): el `INSERT ... SELECT` en `linea_base_concepto` pasa el `FOR
SHARE` de su disparador dentro de la transacción que ya tiene la línea base con `FOR UPDATE`. Si no
pasara, `TC-B09` se colgaría en la pausa de `copiar_conceptos` hasta el `lock_timeout` y fallaría con
`CONCURRENCIA`; si pasa, es la primera vez que el ticket lo ejercita contra el caso de uso completo.

Rojo original de B2: cuando se escribió el archivo, el módulo `congelado` y las funciones de la parte b
del repositorio no existían y cada prueba fallaba por el nombre ausente. Ese rojo ya está documentado en
`impl.md`; hoy existen y el archivo corre en verde.

Mutantes: `M-B1` (quitar el bloqueo de la obra en el congelado) debe poner en rojo `TC-B09` y
`TC-B10`; `M-B7` (quitar el `try/except DBAPIError`), la prueba del bloqueo vencido.
"""

from __future__ import annotations

import functools
import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, LiteralString

import pytest
from sqlalchemy.engine import Engine

from cimenta.presupuesto.aplicacion.contexto import construir_contexto
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from contrato_error.excepciones import (
    ConcurrenciaVencida,
    ConflictoEstado,
    ErrorContrato,
    NoEncontrado,
    RechazoRegla,
)
from herramientas.soporte_tkt017 import preparacion_sintetica_cantidad_plafon
from herramientas.soporte_tkt017_entorno import (
    LIMITE_DE_HILO,
    NOMBRE_COMPLETO_OBRA,
    Base,
    Contexto,
    Entorno,
    Hilo,
    congelar,
)
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, DatosPresupuesto, RelojDePrueba

CORRELACION = "corr-tkt017-b2c"
ROLES_DP = frozenset({"DIRECTOR_PROYECTOS"})
CODIGO_OBRA = "AP-058-25"
MOTIVO_DE_REEMPLAZO = "Corrección de cantidades del nivel 3"
MENSAJE_BLOQUEO = (
    "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo."
)
MENSAJE_RN01 = (
    "La obra {codigo} ya tiene una línea base congelada; para sustituirla hay que crear una versión "
    "nueva que marque la anterior como SUPERSEDIDA."
)
MENSAJE_CONGELADA_EN_CONFIRMACION = (
    "La obra {codigo} ya tiene una línea base congelada; no admite otra importación."
)
MENSAJE_NO_EXISTE = "La línea base no existe."

# El libro de `CA-A1` tiene dos apariciones de MUROS y PLAFONES_Y_CAJILLOS y un panel explotable.
COPIAS_DEL_LIBRO = 2
RENGLONES_DEL_LIBRO = 2
CONTROLES = 4


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
    """El contexto del rol de aplicación con sus 5 s de `lock_timeout`, construido al primer uso."""
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


def _hay_alguien_esperando(base: Base, patron: str) -> bool:
    """Una sesión de la base detenida por un bloqueo, con una consulta como `patron`."""
    fila = base.conexion.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND cardinality(pg_blocking_pids(pid)) > 0 AND query ILIKE %s",
        (patron,),
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def _alguien_espera_la_obra(base: Base) -> Callable[[], bool]:
    """La condición de `esperar_hasta`: alguien detenido en `SELECT ... FROM obra ... FOR UPDATE`."""
    return lambda: _hay_alguien_esperando(base, "%FROM obra%FOR UPDATE%")


def _cuenta(base: Base, consulta: LiteralString, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _pausar_el_hilo_a_en(
    monkeypatch: pytest.MonkeyPatch, paso: str
) -> tuple[threading.Event, threading.Event]:
    """Envuelve el paso del repositorio: el hilo `A` lo ejecuta y espera a que se le libere.

    Devuelve `(dentro, liberar)`: `dentro` se activa cuando A ya escribió y se pausó; `liberar` lo
    reanuda. Si nadie lo libera en `LIMITE_DE_HILO` segundos, A falla con `AssertionError` en vez de
    colgarse. El hilo `B` pasa por la envoltura sin pausarse. Si el paso no existe en el repositorio,
    `monkeypatch` falla con `AttributeError` y la prueba se detiene antes de lanzar ningún hilo.
    """
    original = getattr(repositorio_linea_base, paso)
    dentro, liberar = threading.Event(), threading.Event()

    def envoltura(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        if threading.current_thread().name == "A":
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")
        return resultado

    monkeypatch.setattr(repositorio_linea_base, paso, envoltura)
    return dentro, liberar


def _acciones(base: Base) -> list[str]:
    """Las acciones de la bitácora, ordenadas por nombre (la columna es un enum con otro orden)."""
    return sorted(str(fila[0]) for fila in base.filas("SELECT accion::text FROM bitacora"))


def _jerarquia(base: Base, entorno: Entorno) -> dict[str, list[tuple[Any, ...]]]:
    """Las nueve tablas de la jerarquía de la obra, sin la línea base (que cambia al congelar)."""
    volcado = base.volcado_de_obra(entorno.obra_id)
    volcado.pop("linea_base")
    return volcado


# --------------------------------------------------------------------------- TC-B08 · CA-B6 esc. 2


def test_tkt017_cab06_dos_congelados_simultaneos(
    entorno: Entorno, contexto: Contexto, base: Base
) -> None:
    """TC-B08 · CA-B6 esc. 2 · RN-01 — dos congelados a la vez de la misma obra: gana uno solo.

    Dos `BORRADOR` de la misma obra (la versión 1 sale de la confirmación real; la 2 se siembra). La
    perdedora espera la obra y, cuando la otra confirma, ve su congelada: responde `RN-01`, que es la
    rama determinista. `ConcurrenciaVencida` (si la espera excediera el `lock_timeout` de 5 s) es la
    rama improbable y también se admite; nunca otro error. La obra queda con una sola `CONGELADA`, una
    sola copia de conceptos, un solo control y un solo asiento `CONGELAR`. Qué línea base gana depende de
    quién llega primero: `TC-B09` y `TC-B10` son las pruebas deterministas del bloqueo.
    """
    entorno.importacion_id = entorno.importar()
    primera = entorno.confirmar(contexto).linea_base_id
    segunda = entorno.datos.linea_base(estado="BORRADOR", obra_id=entorno.obra_id, version=2)
    versiones = {primera: 1, segunda: 2}
    ctx = contexto()
    salida = threading.Barrier(2, timeout=LIMITE_DE_HILO)

    def congelar_la(linea_base_id: uuid.UUID) -> Callable[[], uuid.UUID]:
        def correr() -> uuid.UUID:
            salida.wait()
            return congelar(ctx, linea_base_id, usuario_id=entorno.usuario_id)

        return correr

    hilos = [Hilo("A", congelar_la(primera)), Hilo("B", congelar_la(segunda))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.terminar()

    ganadores = [h for h in hilos if h.error is None]
    perdedores = [h for h in hilos if h.error is not None]
    assert len(ganadores) == 1, [h.error for h in hilos]
    assert len(perdedores) == 1
    ganadora, perdedora = ganadores[0], perdedores[0]
    ganada = ganadora.exito()
    perdida = primera if ganada == segunda else segunda

    error = perdedora.error
    assert isinstance(error, ErrorContrato), (
        f"La perdedora debió dar un error del contrato: {error!r}"
    )
    assert error.estado_http == 409
    if isinstance(error, RechazoRegla):
        assert error.cuerpo(ROLES_DP, CORRELACION) == {
            "tipo": "REGLA_NEGOCIO",
            "mensaje": MENSAJE_RN01.format(codigo=CODIGO_OBRA),
            "regla": "RN-01",
            "detalle": {
                "obra": NOMBRE_COMPLETO_OBRA,
                "linea_base_vigente_id": str(ganada),
                "version_vigente": versiones[ganada],
            },
            "acciones": [],
            "correlacion_id": CORRELACION,
        }
    else:
        assert isinstance(error, ConcurrenciaVencida), error
        assert error.cuerpo(ROLES_DP, CORRELACION)["codigo"] == "BLOQUEO_VENCIDO"

    assert base.filas("SELECT id, estado FROM linea_base ORDER BY version") == [
        (primera, "CONGELADA" if ganada == primera else "BORRADOR"),
        (segunda, "CONGELADA" if ganada == segunda else "BORRADOR"),
    ]
    assert _cuenta(base, "SELECT count(*) FROM linea_base WHERE estado = 'CONGELADA'") == 1
    assert base.filas("SELECT DISTINCT linea_base_id FROM linea_base_concepto") == [(ganada,)], (
        "Solo la ganadora tiene copias"
    )
    assert _cuenta(base, "SELECT count(*) FROM linea_base_concepto") == COPIAS_DEL_LIBRO
    assert _cuenta(base, "SELECT count(*) FROM explosion_presupuesto") == RENGLONES_DEL_LIBRO
    assert base.filas("SELECT DISTINCT linea_base_id FROM presupuesto_control") == [(ganada,)]
    assert _cuenta(base, "SELECT count(*) FROM presupuesto_control") == CONTROLES
    assert base.filas("SELECT entidad_id FROM bitacora WHERE accion = 'CONGELAR'") == [(ganada,)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE entidad_id = %s", perdida) == (
        1 if perdida == primera else 0
    ), "La perdedora no deja más asiento que su CONFIRMAR, si lo tiene"
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("ACTIVA",)]


# --------------------------------------------------------------------------- TC-B09 · CA-B6 esc. 3


def test_tkt017_cab06_congelado_gana_al_reemplazo(
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B09 · CA-B6 esc. 3 · RN-01 — mientras A congela, la confirmación con reemplazo espera la obra.

    A se pausa dentro de `copiar_conceptos` con la obra bloqueada y las copias sin confirmar. B confirma
    otra importación con el reemplazo confirmado y debe quedar detenido en el `SELECT ... FOR UPDATE`
    de la obra (`pg_blocking_pids`); sin el bloqueo (`M-B1`) B no se detiene y la prueba falla al
    esperarlo. Al liberar A, B no escribe: la obra ya tiene una congelada y responde
    `ESTADO_NO_PERMITE_OPERACION`; la congelada conserva su jerarquía, sus copias y su control.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    segunda_importacion = entorno.importar(
        preparacion=preparacion_sintetica_cantidad_plafon("8.0000")
    )
    jerarquia = _jerarquia(base, entorno)
    ctx = contexto()
    dentro, liberar = _pausar_el_hilo_a_en(monkeypatch, "copiar_conceptos")
    a = Hilo("A", lambda: congelar(ctx, borrador.linea_base_id, usuario_id=entorno.usuario_id))
    b = Hilo(
        "B",
        lambda: entorno.confirmar(
            lambda: ctx,
            importacion_id=segunda_importacion,
            reemplazar_borrador=True,
            motivo_reemplazo=MOTIVO_DE_REEMPLAZO,
        ),
    )
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), "El hilo A no llegó a copiar_conceptos"
        b.start()
        espera = esperar_hasta(_alguien_espera_la_obra(base), 5.0)
        assert espera, (
            f"B no quedó esperando el bloqueo de la obra mientras A la tenía: {b.error!r}"
        )
        assert b.is_alive()
        assert _cuenta(base, "SELECT count(*) FROM linea_base_concepto") == 0, (
            "Las copias de A no se ven mientras no confirma"
        )
        assert base.filas(
            "SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id
        ) == [("BORRADOR",)]
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    assert a.exito() == borrador.linea_base_id
    assert isinstance(b.error, ConflictoEstado), b.error
    assert b.error.estado_http == 409
    assert b.error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONFLICTO",
        "mensaje": MENSAJE_CONGELADA_EN_CONFIRMACION.format(codigo=CODIGO_OBRA),
        "codigo": "ESTADO_NO_PERMITE_OPERACION",
        "detalle": {
            "obra": NOMBRE_COMPLETO_OBRA,
            "linea_base_vigente_id": str(borrador.linea_base_id),
            "version_vigente": 1,
        },
        "acciones": [],
        "correlacion_id": CORRELACION,
    }
    assert base.filas(
        "SELECT id, version, estado FROM linea_base WHERE obra_id = %s", entorno.obra_id
    ) == [(borrador.linea_base_id, 1, "CONGELADA")]
    assert _jerarquia(base, entorno) == jerarquia, "La congelada conserva su jerarquía"
    assert _cuenta(base, "SELECT count(*) FROM linea_base_concepto") == COPIAS_DEL_LIBRO
    assert _cuenta(base, "SELECT count(*) FROM explosion_presupuesto") == RENGLONES_DEL_LIBRO
    assert _cuenta(base, "SELECT count(*) FROM presupuesto_control") == CONTROLES
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", segunda_importacion) == [
        ("VALIDADO",)
    ]
    assert _acciones(base) == ["CONFIRMAR", "CONGELAR"], "B no asienta DESCARTAR ni CONFIRMAR"
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("ACTIVA",)]


# --------------------------------------------------------------------------- TC-B10 · CA-B6 esc. 3


def test_tkt017_cab06_reemplazo_gana_al_congelado(
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B10 · CA-B6 esc. 3 · RN-01 — mientras A reemplaza el borrador, el congelado del anterior espera la obra.

    A confirma otra importación con reemplazo y se pausa dentro de `insertar_niveles`, con el borrador
    anterior ya borrado y sin confirmar. B congela ese borrador anterior: lo lee sin bloqueo (para
    conocer su obra) y debe quedar detenido en el `SELECT ... FOR UPDATE` de la obra y no en el de la
    línea base, que va después. Al liberar A, el borrador ya no existe: B responde `NoEncontrado` de la
    línea base, no copia nada y no queda ninguna congelada.
    """
    entorno.importacion_id = entorno.importar()
    anterior = entorno.confirmar(contexto)
    segunda_importacion = entorno.importar(
        preparacion=preparacion_sintetica_cantidad_plafon("8.0000")
    )
    ctx = contexto()
    dentro, liberar = _pausar_el_hilo_a_en(monkeypatch, "insertar_niveles")
    a = Hilo(
        "A",
        lambda: entorno.confirmar(
            lambda: ctx,
            importacion_id=segunda_importacion,
            reemplazar_borrador=True,
            motivo_reemplazo=MOTIVO_DE_REEMPLAZO,
        ),
    )
    b = Hilo("B", lambda: congelar(ctx, anterior.linea_base_id, usuario_id=entorno.usuario_id))
    try:
        a.start()
        assert dentro.wait(timeout=LIMITE_DE_HILO), "El hilo A no llegó a insertar_niveles"
        b.start()
        espera = esperar_hasta(_alguien_espera_la_obra(base), 5.0)
        assert espera, (
            f"B no quedó esperando el bloqueo de la obra mientras A la tenía: {b.error!r}"
        )
        assert b.is_alive()
        assert base.filas(
            "SELECT estado FROM linea_base WHERE id = %s", anterior.linea_base_id
        ) == [("BORRADOR",)], "El borrado de A no se ve mientras no confirma"
    finally:
        liberar.set()
        a.terminar()
        b.terminar()

    assert a.error is None, a.error
    nueva = a.exito()
    assert nueva.version == 1
    assert nueva.linea_base_id != anterior.linea_base_id
    assert isinstance(b.error, NoEncontrado), b.error
    assert b.error.estado_http == 404
    assert b.error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "NO_ENCONTRADO",
        "mensaje": MENSAJE_NO_EXISTE,
        "recurso": "linea_base",
        "correlacion_id": CORRELACION,
    }
    assert base.filas("SELECT id, version, estado, importe_venta FROM linea_base") == [
        (nueva.linea_base_id, 1, "BORRADOR", "8610.0000")
    ], "Queda el borrador nuevo; ninguna congelada"
    assert _cuenta(base, "SELECT count(*) FROM linea_base_concepto") == 0
    assert _cuenta(base, "SELECT count(*) FROM explosion_presupuesto") == 0
    assert _cuenta(base, "SELECT count(*) FROM presupuesto_control") == 0
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("PLANEACION",)]
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'CONGELAR'") == 0
    assert _acciones(base) == ["CONFIRMAR", "CONFIRMAR", "DESCARTAR"]
    assert base.filas("SELECT estado FROM importacion WHERE id = %s", segunda_importacion) == [
        ("CONFIRMADO",)
    ]


# --------------------------------------------------------------------------- CA-B6 esc. 1 en el caso de uso


def test_tkt017_cab06_congelado_con_bloqueo_vencido_en_el_caso_de_uso(
    entorno: Entorno,
    contexto: Contexto,
    contexto_espera_corta: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """CA-B6 esc. 1 · ADR-004 · RNF-16 — con `lock_timeout` de 200 ms, el congelado recibe `BLOQUEO_VENCIDO`.

    Otra sesión tiene la fila de la obra con `FOR UPDATE` sin confirmar. El contrato completo:
    `CONCURRENCIA` con `espera_maxima_ms` 5000 (el `lock_timeout` del rol), `Retry-After: 1` y la acción
    `REINTENTAR` a `POST` de la ruta de congelación de ESA línea base, para el Director de Proyectos
    (`M-B7`: sin el `try/except DBAPIError` llegaría el error crudo del motor, que responde `500`).
    No escribe nada.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    antes = (
        base.foto(),
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT * FROM linea_base ORDER BY id"),
    )
    ctx = contexto_espera_corta()
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    try:
        retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (entorno.obra_id,))
        with pytest.raises(ErrorContrato) as vencido:
            congelar(ctx, borrador.linea_base_id, usuario_id=entorno.usuario_id)
    finally:
        retenedor.rollback()

    error = vencido.value
    assert isinstance(error, ConcurrenciaVencida), error
    assert error.estado_http == 409
    assert error.cabeceras() == {"Retry-After": "1"}
    assert error.cuerpo(ROLES_DP, CORRELACION) == {
        "tipo": "CONCURRENCIA",
        "mensaje": MENSAJE_BLOQUEO,
        "codigo": "BLOQUEO_VENCIDO",
        "detalle": {"espera_maxima_ms": 5000},
        "acciones": [
            {
                "clave": "REINTENTAR",
                "metodo": "POST",
                "ruta": f"/api/v1/lineas-base/{borrador.linea_base_id}/congelacion",
            }
        ],
        "correlacion_id": CORRELACION,
    }
    assert (
        base.foto(),
        base.filas("SELECT * FROM obra ORDER BY id"),
        base.filas("SELECT * FROM linea_base ORDER BY id"),
    ) == antes, "El congelado vencido no escribe nada"


def test_tkt017_cab06_congelado_espera_el_bloqueo_de_la_obra_y_continua(
    entorno: Entorno,
    contexto: Contexto,
    base: Base,
    base_de_prueba: str,
    conectar: Conectar,
) -> None:
    """CA-B6 esc. 1 · ADR-004 — si la obra se libera dentro del `lock_timeout`, el congelado espera y termina bien.

    Otra sesión tiene la fila de la obra; el congelado queda detenido en su `SELECT ... FOR UPDATE`
    (`pg_blocking_pids`) y, al liberarla, congela. Distingue una espera del bloqueo de un rechazo.
    """
    entorno.importacion_id = entorno.importar()
    borrador = entorno.confirmar(contexto)
    ctx = contexto()
    retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
    retenedor.execute("SELECT id FROM obra WHERE id = %s FOR UPDATE", (entorno.obra_id,))
    hilo = Hilo("A", lambda: congelar(ctx, borrador.linea_base_id, usuario_id=entorno.usuario_id))
    try:
        hilo.start()
        espera = esperar_hasta(_alguien_espera_la_obra(base), 5.0)
        assert espera, f"El congelado no quedó esperando el bloqueo de la obra: {hilo.error!r}"
        assert hilo.is_alive()
        assert base.filas(
            "SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id
        ) == [("BORRADOR",)]
    finally:
        retenedor.rollback()
        hilo.terminar()

    assert hilo.error is None, hilo.error
    assert hilo.exito() == borrador.linea_base_id
    assert base.filas("SELECT estado FROM linea_base WHERE id = %s", borrador.linea_base_id) == [
        ("CONGELADA",)
    ]
    assert base.filas("SELECT estado FROM obra WHERE id = %s", entorno.obra_id) == [("ACTIVA",)]
