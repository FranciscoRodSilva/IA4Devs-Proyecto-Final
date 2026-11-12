"""Concurrencia de la confirmación de un archivo (TKT-059, fila 12a): TC-18, TC-18b, TC-18c y TC-18d.

`confirmar_archivo` bloquea la fila con `SELECT … FOR UPDATE` antes de hablar con el almacén (ADR-004,
RNF-16). Dos confirmaciones del mismo archivo no pasan las dos: la segunda espera y, al liberarse, ve la
fila `DISPONIBLE`. Y si la fila la retiene alguien más allá de `lock_timeout`, la respuesta es un `409`
`CONCURRENCIA` y no un `500`. Lo mismo si una sentencia agota `statement_timeout` (`57014`); y un error
de la base que no es de tiempo (cualquier otro `SQLSTATE`) no se traduce: es un `500`.

Determinista y sin `sleep`: el hilo A se pausa dentro de `metadatos` (paso 7, con la fila bloqueada) con
un `threading.Event`, y la prueba espera con `esperar_hasta` —sondeo sobre `pg_blocking_pids`— a que B
quede detenido en su `SELECT … FOR UPDATE`. El hilo pausado se libera siempre en `finally`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from herramientas.soporte_tkt017_api import CABECERA_CORRELACION, exigir_error
from herramientas.soporte_tkt017_entorno import LIMITE_DE_HILO, Hilo
from herramientas.soporte_tkt059 import (
    TIPO_XLSX,
    AlmacenContador,
    Respuesta,
    abrir_sesion_del_director,
    asientos_del_archivo,
    cliente_https,
    confirmar_por_http,
    crear_aplicacion_de_archivos,
    dar_de_alta,
    fila_de_archivo,
    libro_de_presupuesto,
    ruta_de_confirmacion,
    sembrar_director,
    subir_objeto,
)
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import Conectar, LibroCatalogo, RelojDePrueba, SembrarUsuario

    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3

MENSAJE_BLOQUEO_VENCIDO = (
    "Otra operación está confirmando este archivo en este momento. Vuelve a intentarlo."
)
MENSAJE_TIEMPO_VENCIDO = "La operación tardó más de lo permitido y se canceló. Vuelve a intentarlo."
ESPERA_A_LLEGAR_A_METADATOS = 15.0
ESPERA_A_QUE_B_SE_DETENGA = 5.0


def _alguien_espera_la_fila_del_archivo(motor: Engine) -> bool:
    """La condición de `esperar_hasta`: una sesión detenida en `SELECT … FROM archivo … FOR UPDATE`."""
    with motor.connect() as conexion:
        fila = conexion.execute(
            text(
                "SELECT 1 FROM pg_stat_activity WHERE datname = current_database() "
                "AND cardinality(pg_blocking_pids(pid)) > 0 "
                "AND query ILIKE '%FROM archivo%' AND query ILIKE '%FOR UPDATE%'"
            )
        ).first()
    return fila is not None


def _terminar(hilo: Hilo[Respuesta]) -> None:
    """Espera al hilo si llegó a arrancar: unir uno que nunca empezó lanza `RuntimeError`."""
    if hilo.ident is not None:
        hilo.terminar()


# --------------------------------------------------------------------------- TC-18


def test_tkt059_ca04_dos_confirmaciones_simultaneas(
    almacen: AlmacenS3,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-18 · CA-4 esc. 2 · ADR-004 — dos confirmaciones simultáneas del mismo archivo: las dos `200`, un solo asiento (`M-15`).

    El hilo A entra a `metadatos` con la fila bloqueada y se detiene. El hilo B confirma el mismo archivo y
    queda en espera de A: su `SELECT … FOR UPDATE` aparece bloqueado en `pg_stat_activity`. Mientras A
    sostiene la fila nadie ve el archivo `DISPONIBLE`. Al liberar a A, confirma; B se desbloquea, ve la fila
    `DISPONIBLE` y responde `200` con el mismo cuerpo, sin volver a comparar el objeto ni asentar. Sin el
    `FOR UPDATE` (`M-15`) B no se detiene y `esperar_hasta` vence.
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)
    contador = AlmacenContador(almacen)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=contador.como_almacen(), motor=motor_aplicacion, reloj=reloj_de_prueba
    )
    dentro, liberar = threading.Event(), threading.Event()
    cerradura = threading.Lock()
    pausados: list[str] = []

    def pausar_al_primero(_clave: str) -> None:
        """Solo la primera llamada a `metadatos` se pausa: es la de A, que entró con la fila bloqueada."""
        with cerradura:
            es_la_primera = not pausados
            pausados.append(threading.current_thread().name)
        if es_la_primera:
            dentro.set()
            if not liberar.wait(timeout=LIMITE_DE_HILO):
                raise AssertionError("El hilo A nunca fue liberado")

    contador.gancho_metadatos = pausar_al_primero

    with cliente_https(aplicacion) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)

        a: Hilo[Respuesta] = Hilo(
            "A", lambda: confirmar_por_http(cliente, sesion_id, archivo.archivo_id)
        )
        b: Hilo[Respuesta] = Hilo(
            "B", lambda: confirmar_por_http(cliente, sesion_id, archivo.archivo_id)
        )
        try:
            a.start()
            esperar_hasta(lambda: dentro.is_set() or not a.is_alive(), ESPERA_A_LLEGAR_A_METADATOS)
            assert dentro.is_set(), (
                "A no llegó a `metadatos` con la fila bloqueada: respondió "
                f"{None if a.resultado is None else a.resultado.status_code} "
                f"({None if a.resultado is None else a.resultado.text[:120]!r}), error {a.error!r}"
            )
            b.start()
            espera = esperar_hasta(
                lambda: _alguien_espera_la_fila_del_archivo(motor_aplicacion),
                ESPERA_A_QUE_B_SE_DETENGA,
            )
            assert espera, (
                "B no quedó detenido en `SELECT … FOR UPDATE` mientras A sostenía la fila: "
                f"B respondió {b.resultado!r}, error {b.error!r}"
            )
            assert b.is_alive()
            assert fila_de_archivo(motor_aplicacion, archivo.archivo_id)["estado"] == "PENDIENTE", (
                "La confirmación de A no se ve mientras no confirma"
            )
        finally:
            liberar.set()
            _terminar(a)
            _terminar(b)

    assert a.error is None, a.error
    assert b.error is None, b.error
    respuesta_a, respuesta_b = a.exito(), b.exito()
    assert respuesta_a.status_code == 200, respuesta_a.text
    assert respuesta_b.status_code == 200, respuesta_b.text
    assert respuesta_a.json()["estado"] == respuesta_b.json()["estado"] == "DISPONIBLE"
    assert respuesta_b.json() == respuesta_a.json()
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "DISPONIBLE"
    assert fila["tipo_mime"] == TIPO_XLSX
    asientos = asientos_del_archivo(motor_aplicacion, archivo.archivo_id, "CONFIRMAR")
    assert len(asientos) == 1
    assert fila["confirmado_en"] == asientos[0]["ocurrido_en"]
    assert contador.llamadas_metadatos == [archivo.clave], (
        "B ve la fila DISPONIBLE y no compara el objeto"
    )
    assert contador.reescrituras == [(archivo.clave, TIPO_XLSX)]


# --------------------------------------------------------------------------- TC-18b


def test_tkt059_ca04_confirmacion_con_bloqueo_vencido(
    almacen: AlmacenS3,
    motor_espera_corta: Engine,
    motor_aplicacion: Engine,
    base_de_prueba: str,
    conectar: Conectar,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-18b · CA-4 · ADR-004 · RNF-16 — otra sesión retiene la fila: `409` `CONCURRENCIA` `BLOQUEO_VENCIDO` (`M-19`).

    La aplicación corre sobre `motor_espera_corta` (el rol de aplicación con `lock_timeout` de 200 ms) y
    otra sesión tiene la fila de `archivo` con `FOR UPDATE`. El contrato es completo: `Retry-After: 1`,
    `espera_maxima_ms` 5000 (el `lock_timeout` del rol, no los 200 ms de la prueba), la acción `REINTENTAR`
    `POST` a la ruta de confirmación de ESE archivo —que no se filtra por rol— y sin `regla`. No escribe
    nada: la fila sigue `PENDIENTE`, sin `confirmado_en`, y la bitácora no recibe ningún asiento. Sin la
    traducción de `55P03` (`M-19`) la respuesta es un `500`.
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)
    aplicacion: FastAPI = crear_aplicacion_de_archivos(
        almacen=almacen, motor=motor_espera_corta, reloj=reloj_de_prueba
    )

    with cliente_https(aplicacion) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion, motor_espera_corta, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)
        retenedor = conectar("aplicacion", base_de_prueba, autocommit=False)
        try:
            retenedor.execute(
                "SELECT id FROM archivo WHERE id = %s FOR UPDATE", (archivo.archivo_id,)
            )
            respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)
        finally:
            retenedor.rollback()

    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONCURRENCIA",
            "codigo": "BLOQUEO_VENCIDO",
            "mensaje": MENSAJE_BLOQUEO_VENCIDO,
            "detalle": {"espera_maxima_ms": 5000},
            "acciones": [
                {
                    "clave": "REINTENTAR",
                    "metodo": "POST",
                    "ruta": ruta_de_confirmacion(archivo.archivo_id),
                }
            ],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "PENDIENTE"
    assert fila["confirmado_en"] is None
    assert fila["tipo_mime"] is None
    assert asientos_del_archivo(motor_aplicacion, archivo.archivo_id) == []


# --------------------------------------------------------------------------- TC-18c y TC-18d


def _bloquear_que_falla(sentencias: list[str], sqlstates: list[str]) -> Callable[..., None]:
    """Un sustituto de `repositorio.bloquear` cuyas sentencias fallan **en el motor**, no por simulación.

    Ejecuta cada sentencia en la sesión del caso de uso; el motor responde con un `SQLSTATE` real, que el
    sustituto anota en `sqlstates` antes de relanzar el error tal cual.
    """

    def bloquear(sesion_bd: Session, _archivo_id: object) -> None:
        try:
            for sentencia in sentencias:
                sesion_bd.execute(text(sentencia))
        except DBAPIError as error:
            sqlstates.append(str(getattr(error.orig, "sqlstate", None)))
            raise

    return bloquear


def test_tkt059_ca04_confirmacion_con_tiempo_de_ejecucion_vencido(
    aplicacion_archivos: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-18c · CA-4 · ADR-004 · RNF-16 — una sentencia agota `statement_timeout`: `409` `CONCURRENCIA` `TIEMPO_EJECUCION_VENCIDO`.

    El `SELECT … FOR UPDATE` se sustituye por una sentencia que vence un `statement_timeout` de 10 ms: el
    motor responde `57014` de verdad (la prueba lo comprueba). El contrato es completo: `Retry-After: 1`,
    `espera_maxima_ms` 15000 (el `statement_timeout` del rol), el mensaje del diseño, la acción
    `REINTENTAR` `POST` a la ruta de confirmación de ESE archivo y sin `regla`. No escribe nada: la fila
    sigue `PENDIENTE` y la bitácora no recibe ningún asiento. Mutantes: cambiar 15000 por otro valor, o
    traducir el `57014` como `BLOQUEO_VENCIDO`, lo hacen caer.
    """
    from cimenta.archivos.infraestructura import repositorio

    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)
    sqlstates: list[str] = []

    with cliente_https(aplicacion_archivos) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion_archivos, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)
        monkeypatch.setattr(
            repositorio,
            "bloquear",
            _bloquear_que_falla(
                ["SET LOCAL statement_timeout = '10ms'", "SELECT pg_sleep(1)"], sqlstates
            ),
        )

        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert sqlstates == ["57014"], "La sentencia debe vencer el tiempo en el motor, no simularse"
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONCURRENCIA",
            "codigo": "TIEMPO_EJECUCION_VENCIDO",
            "mensaje": MENSAJE_TIEMPO_VENCIDO,
            "detalle": {"espera_maxima_ms": 15000},
            "acciones": [
                {
                    "clave": "REINTENTAR",
                    "metodo": "POST",
                    "ruta": ruta_de_confirmacion(archivo.archivo_id),
                }
            ],
        },
        esquema="ErrorConcurrencia",
        cabeceras={"Retry-After": "1"},
    )
    assert "regla" not in cuerpo
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "PENDIENTE"
    assert fila["confirmado_en"] is None
    assert fila["tipo_mime"] is None
    assert asientos_del_archivo(motor_aplicacion, archivo.archivo_id) == []


def test_tkt059_ca04_error_de_base_ajeno_al_tiempo_es_un_500_sin_traducir(
    aplicacion_archivos: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-18d · CA-4 · RNF-16 — un error de la base que no es `55P03` ni `57014` no se traduce: `500` del contrato.

    La sentencia sustituta falla con una división entre cero real (`22012`). El caso de uso no la
    convierte en `CONCURRENCIA` ni en ningún `409`: la relanza y la respuesta es el `500` genérico, solo
    `mensaje` y `correlacion_id` (el de la cabecera), sin el nombre de la excepción, el `SQLSTATE` ni el
    texto del motor. La fila sigue `PENDIENTE` y no se asienta nada. Mutante: traducir todo `DBAPIError`
    a `CONCURRENCIA` lo hace caer.
    """
    from cimenta.archivos.infraestructura import repositorio

    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)
    sqlstates: list[str] = []

    with cliente_https(aplicacion_archivos) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion_archivos, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)
        monkeypatch.setattr(
            repositorio,
            "bloquear",
            _bloquear_que_falla(["SELECT 1 / 0"], sqlstates),
        )

        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert sqlstates == ["22012"], "El motor debe responder con un SQLSTATE que no es de tiempo"
    assert respuesta.status_code == 500, respuesta.text
    assert "retry-after" not in respuesta.headers
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "correlacion_id"}
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    for pista in (
        "CONCURRENCIA",
        "DataError",
        "DBAPIError",
        "DivisionByZero",
        "division by zero",
        "22012",
        "Traceback",
        "psycopg",
        "sqlalchemy",
        "cimenta.",
    ):
        assert pista not in respuesta.text
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "PENDIENTE"
    assert fila["confirmado_en"] is None
    assert asientos_del_archivo(motor_aplicacion, archivo.archivo_id) == []
